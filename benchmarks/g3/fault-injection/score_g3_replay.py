"""Operator-run replay scorer for the G3 corrupted-plan suite (G3.E.3, G3.E.4).

Run it in an interpreter that has FreeCAD and ``mcp`` (the micromamba env, or a CI headless
leg)::

    python benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.1.x
    python benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.0.x --check \
        --frames-check benchmarks/g3/fault-injection/frames-reference.json

The scorer spawns the headless H1 host over stdio and reaches FreeCAD only through its MCP
tools: every plan step is previewed with ``preview_dry_run`` and then confirmed (AD-5), and every
part is graded with ``verify_shape`` using its spec's ``checks`` and ``anchor_frame``. Nothing
here imports a use case or reads a verdict off the plan (AD-13); detection comes from the
measured checks alone.

Each planted case is built twice: planted, and reverted. The reverted plan replaces the planted
step's args with the case's ``faithful_args``, or, where the defect spans more than one step,
applies its ``faithful_steps`` (step index to replacement ``{tool, args}``, or null to drop the
step). Each control is built once. Classification:

- A planted build is DETECTED when a check of its ``detected_by`` fn failed without an
  ``invalid_input.*`` code; otherwise it is MISSED and listed.
- A control or reverted build is a FALSE_ALARM when its verdict is not ``OK``.
- A plan step that does not return ``OK``, or a reverted build that does not grade ``OK``, makes
  the whole case INVALID_INPUT: it is listed, excluded from both rates, and the run exits
  non-zero.

The resolved anchor frame of every control and reverted build is written to
``G3.E.3.<leg>.json``; ``--frames-check REF`` compares it with a committed reference.
Sensitivity, false alarm and a Wilson CI are merged into ``validators.yaml`` as the
``spec_assertions`` block unless ``--check`` is passed or a case is INVALID_INPUT.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
G3_ROOT = HERE.parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
SUITE_ROOT = HERE / "corrupted-plan"
DEV_ROOT = G3_ROOT / "dev"
VALIDATORS_YAML = REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml"
ARTIFACTS = REPO_ROOT / "benchmarks" / "gate-artifacts" / "g3"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
_EXPORT_SCORER_DIR = REPO_ROOT / "benchmarks" / "g0" / "export-fault-injection"
if str(_EXPORT_SCORER_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPORT_SCORER_DIR))

from freecad_buddy.usecases import stats  # noqa: E402
from score_export_verify import merge_validators_yaml  # noqa: E402

VALIDATOR = "spec_assertions"
SENSITIVITY_BAR = 0.95
FALSE_ALARM_BAR = 0.05
LEGS = ("1.0.x", "1.1.x")
# The measurement sources behind verify_shape's §7.2 checks, and this scorer, which classifies
# what they measure. Mirrored byte for byte by
# runner._VALIDATOR_SOURCES["spec_assertions"], so a clean tree reads as CURRENT.
VALIDATOR_SOURCES = (
    SRC / "freecad_buddy" / "usecases" / "assertions.py",
    SRC / "freecad_buddy" / "usecases" / "verify.py",
    HERE / "score_g3_replay.py",
)
# Frame kinds whose entity is an object Name. A largest_planar_face entity is a mapped face name
# whose hasher tag differs between sessions, so it is never compared.
NAMED_FRAME_KINDS = frozenset({"base_sketch_plane", "named_datum"})
# Frame coordinates are compared at 1e-6 mm: far below any tolerance a check uses, and far above
# the float noise two OCC builds leave in a face centroid.
FRAME_DECIMALS = 6
INVALID_CODE_PREFIX = "invalid_input"

DETECTED, MISSED = "DETECTED", "MISSED"
PASS_CLEAN, FALSE_ALARM = "PASS_CLEAN", "FALSE_ALARM"
INVALID_INPUT = "INVALID_INPUT"


class ReplayError(Exception):
    """A plan step did not return ``OK``; ``doc`` is the handle opened before it, if any."""

    def __init__(self, message: str, doc: str | None):
        super().__init__(message)
        self.doc = doc


# -- suite -----------------------------------------------------------------------------------


def suite_case_files(root: Path = SUITE_ROOT) -> list[Path]:
    """Every ``case.yaml`` under ``root`` by exact name, ordered by suite-relative POSIX path."""
    return sorted(
        (p for p in root.rglob("case.yaml") if p.name == "case.yaml"),
        key=lambda p: p.relative_to(root).as_posix(),
    )


def _targets_validator(case: dict) -> bool:
    declared = case.get("targets_validator")
    return isinstance(declared, str) and declared.split("@", 1)[0] == VALIDATOR


def load_cases(root: Path = SUITE_ROOT) -> list[dict]:
    """The corrupted-plan cases that target ``spec_assertions``."""
    cases = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in suite_case_files(root)]
    return [case for case in cases if _targets_validator(case)]


def load_spec(spec_ref: str) -> dict:
    return yaml.safe_load((DEV_ROOT / spec_ref / "case.yaml").read_text(encoding="utf-8"))


def is_planted(case: dict) -> bool:
    return (case.get("fault") or {}).get("expectation") == "DETECT"


def reverted_plan(case: dict) -> list[dict]:
    """The case's plan with its ``faithful_args`` or ``faithful_steps`` applied."""
    plan = copy.deepcopy(case["plan"])
    if "faithful_args" in case:
        plan[case["planted_step"]]["args"] = copy.deepcopy(case["faithful_args"])
        return plan
    replacements = {int(index): step for index, step in case["faithful_steps"].items()}
    reverted = [copy.deepcopy(replacements.get(i, step)) for i, step in enumerate(plan)]
    return [step for step in reverted if step is not None]


def _fold(digest, identity: str, path: Path) -> None:
    """Add ``path`` under ``identity``, both length-prefixed so the concatenation is unambiguous."""
    name, content = identity.encode("utf-8"), path.read_bytes()
    digest.update(len(name).to_bytes(4, "big"))
    digest.update(name)
    digest.update(len(content).to_bytes(8, "big"))
    digest.update(content)


def validator_sha(root: Path = SUITE_ROOT, dev_root: Path = DEV_ROOT) -> str:
    """SHA-256 over the measurement sources, the cases scored and the specs that grade them.

    After the sources (this scorer included, since it classifies the result) come the selected
    cases by suite-relative path, then each distinct dev spec a selected case names, by
    ``dev/<spec_ref>/case.yaml`` in sorted order. A suite with no case adds an explicit
    empty-suite marker instead. runner.py mirrors this byte for byte.
    """
    digest = hashlib.sha256()
    for path in VALIDATOR_SOURCES:
        digest.update(path.read_bytes())
    selected = []
    for path in suite_case_files(root):
        case = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if _targets_validator(case):
            selected.append((path, case.get("spec_ref")))
    if not selected:
        digest.update(b"\x00no-fault-suite")
        return digest.hexdigest()
    for path, _ in selected:
        _fold(digest, path.relative_to(root).as_posix(), path)
    for spec_ref in sorted({str(spec_ref) for _, spec_ref in selected}):
        _fold(digest, f"dev/{spec_ref}/case.yaml", dev_root / spec_ref / "case.yaml")
    return digest.hexdigest()


# -- replay ----------------------------------------------------------------------------------


async def call(session, tool: str, args: dict) -> dict:
    """Call one MCP tool and return its result envelope."""
    result = await session.call_tool(tool, args)
    if result.structuredContent:
        return result.structuredContent
    text = "".join(getattr(block, "text", "") for block in result.content)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"status": "NO_JSON", "detail": {"message": text[:400]}}


def bind(value, doc: str | None):
    """``value`` with every ``'$doc'`` replaced by the document handle."""
    if value == "$doc":
        return doc
    if isinstance(value, dict):
        return {key: bind(item, doc) for key, item in value.items()}
    if isinstance(value, list):
        return [bind(item, doc) for item in value]
    return value


def _graded_object(plan: list[dict]) -> str | None:
    """The last feature a plan creates: the Body's tip, which carries the finished part."""
    graded = None
    for step in plan:
        tool = step["tool"]
        if tool.startswith("feature_") and tool not in ("feature_body_create", "feature_datum"):
            graded = step["args"].get("name")
    return graded


async def replay(session, plan: list[dict]) -> str:
    """Run ``plan`` step by step, each mutation previewed then confirmed; return the doc handle.

    :raises ReplayError: a step's preview or call did not return ``OK``.
    """
    doc = None
    for index, step in enumerate(plan):
        tool, args = step["tool"], bind(step["args"], doc)
        if tool == "document_create":
            envelope = await call(session, tool, args)
            doc = (envelope.get("structured_content") or {}).get("doc")
        else:
            operation = {"tool": tool, "args": {k: v for k, v in args.items() if k != "doc"}}
            preview = await call(
                session, "preview_dry_run", {"doc": doc, "operation": operation, "render": "off"}
            )
            preview_id = (preview.get("structured_content") or {}).get("preview_id")
            if not preview_id:
                raise ReplayError(
                    f"step {index} {tool}: preview {preview.get('status')} {preview.get('detail')}",
                    doc,
                )
            confirm = {"preview_id": preview_id, "elicitation_action": "accept"}
            envelope = await call(session, tool, {**args, "confirm": confirm})
        if envelope.get("status") != "OK":
            raise ReplayError(
                f"step {index} {tool}: {envelope.get('status')} {envelope.get('detail')}", doc
            )
    return doc


async def build(session, plan: list[dict], spec: dict) -> dict:
    """Replay ``plan`` and grade the part with ``spec``'s checks in its anchor frame.

    :returns: ``{status, checks, frame, freecad_version}``, or ``{error}`` when the replay or the
        grading call failed.
    """
    try:
        doc = await replay(session, plan)
    except ReplayError as exc:
        if exc.doc:
            await call(session, "document_close", {"doc": exc.doc})
        return {"error": str(exc)}
    try:
        envelope = await call(
            session,
            "verify_shape",
            {
                "doc": doc,
                "object": _graded_object(plan),
                "checks": spec["assertions"]["checks"],
                "anchor_frame": spec["assertions"]["anchor_frame"],
            },
        )
    finally:
        await call(session, "document_close", {"doc": doc})
    content = envelope.get("structured_content") or {}
    if not isinstance(content.get("checks"), list):
        return {"error": f"verify_shape: {envelope.get('status')} {envelope.get('detail')}"}
    banner = content.get("banner") or {}
    return {
        "status": envelope.get("status"),
        "checks": content["checks"],
        "frame": banner.get("anchor_frame"),
        "freecad_version": banner.get("freecad_version"),
    }


# -- classification ----------------------------------------------------------------------------


def _measured_failure(check: dict) -> bool:
    code = str((check.get("detail") or {}).get("code") or "")
    return not check.get("passed") and not code.startswith(INVALID_CODE_PREFIX)


def classify_planted(result: dict, detected_by: str) -> str:
    """DETECTED when a ``detected_by`` check failed with a measured value, else MISSED."""
    check_id = f"assert.{detected_by}"
    hit = any(c.get("id") == check_id and _measured_failure(c) for c in result["checks"])
    return DETECTED if hit else MISSED


def classify_control(result: dict) -> str:
    """PASS_CLEAN when the clean build's verdict is ``OK``, else FALSE_ALARM."""
    return PASS_CLEAN if result.get("status") == "OK" else FALSE_ALARM


def score_case(case: dict, planted: dict | None, clean: dict) -> dict:
    """Classify one case from its builds.

    ``planted`` is ``None`` for a control. A build carrying ``error``, or a reverted build whose
    verdict is not ``OK``, makes the case INVALID_INPUT.
    """
    row = {"case": case["id"], "spec_ref": case["spec_ref"], "planted": None, "clean": None}
    errors = [b["error"] for b in (planted, clean) if b is not None and "error" in b]
    if errors:
        return {**row, "outcome": INVALID_INPUT, "reason": "; ".join(errors)}
    row["clean"] = classify_control(clean)
    if planted is None:
        return {**row, "outcome": row["clean"]}
    if row["clean"] != PASS_CLEAN:
        failed = [c.get("id") for c in clean["checks"] if not c.get("passed")]
        return {
            **row,
            "outcome": INVALID_INPUT,
            "reason": f"reverted build is {clean.get('status')}, not OK: {failed}",
        }
    row["planted"] = classify_planted(planted, case["detected_by"])
    return {**row, "outcome": row["planted"]}


def tally(rows: list[dict]) -> dict:
    """Sensitivity over planted cases and false alarm over controls plus reverted builds."""
    valid = [row for row in rows if row["outcome"] != INVALID_INPUT]
    planted = [row for row in valid if row["planted"] is not None]
    detected = sum(1 for row in planted if row["planted"] == DETECTED)
    controls = len(valid)
    flagged = sum(1 for row in valid if row["clean"] == FALSE_ALARM)
    return {
        "planted": len(planted),
        "detected": detected,
        "controls": controls,
        "flagged": flagged,
        "sensitivity": stats.sensitivity(detected, len(planted)),
        "false_alarm": stats.false_alarm(flagged, controls),
        "wilson_ci": stats.wilson_ci(detected, len(planted)),
        "missed": [row["case"] for row in planted if row["planted"] != DETECTED],
        "false_alarms": [row["case"] for row in valid if row["clean"] == FALSE_ALARM],
        "invalid": [row["case"] for row in rows if row["outcome"] == INVALID_INPUT],
    }


def bars_met(totals: dict) -> bool:
    return (
        not totals["invalid"]
        and totals["planted"] > 0
        and totals["sensitivity"] >= SENSITIVITY_BAR
        and totals["false_alarm"] <= FALSE_ALARM_BAR
    )


# -- frames ------------------------------------------------------------------------------------


def comparable_frame(frame: dict | None) -> dict:
    """The frame fields two legs must agree on: kind, rounded origin and axes, named entity."""
    frame = frame or {}

    def rounded(vector):
        if vector is None:
            return None
        return [round(float(v), FRAME_DECIMALS) + 0.0 for v in vector]

    fields = {
        "kind": frame.get("kind"),
        "origin": rounded(frame.get("origin")),
        "axes": [rounded(axis) for axis in frame["axes"]] if frame.get("axes") else None,
    }
    if frame.get("kind") in NAMED_FRAME_KINDS:
        fields["entity"] = frame.get("entity")
    return fields


def compare_frames(reference: dict, frames: dict) -> list[str]:
    """One line per drift between two ``{build: frame}`` maps, naming the build and the field."""
    drifts = []
    for build_id in sorted(set(reference) | set(frames)):
        if build_id not in frames:
            drifts.append(f"{build_id}: no frame on this leg")
            continue
        if build_id not in reference:
            drifts.append(f"{build_id}: not in the reference")
            continue
        expected = comparable_frame(reference[build_id])
        measured = comparable_frame(frames[build_id])
        for field in sorted(set(expected) | set(measured)):
            if expected.get(field) != measured.get(field):
                drifts.append(
                    f"{build_id}: {field} {measured.get(field)!r} != {expected.get(field)!r}"
                )
    return drifts


# -- registry ----------------------------------------------------------------------------------


def render_block(sha: str, totals: dict, run_id: str, today: str) -> str:
    wilson = totals["wilson_ci"]
    return (
        f"{VALIDATOR}:\n"
        "  suite: g3/fault-injection/corrupted-plan/\n"
        f'  validator_sha: "{sha}"\n'
        "  last_run:\n"
        f"    run_id: {run_id}\n"
        f"    sensitivity: {round(totals['sensitivity'], 4)}\n"
        f"    false_alarm: {round(totals['false_alarm'], 4)}\n"
        f"    date: {today}\n"
        f"    planted: {totals['planted']}\n"
        f"    controls: {totals['controls']}\n"
        "    wilson_ci:\n"
        f"      rate: {round(wilson['rate'], 4)}\n"
        f"      low: {round(wilson['low'], 4)}\n"
        f"      high: {round(wilson['high'], 4)}\n"
        f"      n: {wilson['n']}\n"
        f"      r: {wilson['r']}\n"
    )


# -- host --------------------------------------------------------------------------------------


def _server_params(run_dir: Path):
    """Spawn the H1 host in this interpreter, with FreeCAD's library dir importable."""
    from mcp.client.stdio import StdioServerParameters

    prefix = Path(sys.prefix)
    # conda-forge FreeCAD puts FreeCAD.pyd in Library/bin on Windows and FreeCAD.so in lib on
    # Linux; neither is on the default module path.
    freecad_dirs = [d for d in (prefix / "Library" / "bin", prefix / "lib") if d.is_dir()]
    child = dict(os.environ)
    python_path = [str(SRC), *map(str, freecad_dirs), child.get("PYTHONPATH", "")]
    child["PYTHONPATH"] = os.pathsep.join(part for part in python_path if part)
    child["PATH"] = os.pathsep.join(
        [*map(str, freecad_dirs), str(prefix / "Library" / "lib"), child.get("PATH", "")]
    )
    child["FREECAD_BUDDY_AUDIT_LOG"] = str(run_dir / "audit.jsonl")
    return StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "freecad_buddy.hosts.main",
            "serve",
            "--mode",
            "inline",
            "--transport",
            "stdio",
        ],
        env=child,
    )


async def score_suite(session, cases: list[dict]) -> tuple[list[dict], dict]:
    """Build and classify every case; return the per-case rows and the clean builds' frames."""
    rows, frames = [], {}
    for case in cases:
        spec = load_spec(case["spec_ref"])
        planted = None
        if is_planted(case):
            planted = await build(session, case["plan"], spec)
            if "faithful_args" in case or "faithful_steps" in case:
                clean = await build(session, reverted_plan(case), spec)
            else:
                clean = {"error": "the planted case carries no faithful_args or faithful_steps"}
            build_id = f"{case['id']}#reverted"
        else:
            clean = await build(session, case["plan"], spec)
            build_id = case["id"]
        if "error" not in clean:
            frames[build_id] = {"spec_ref": case["spec_ref"], **(clean["frame"] or {})}
        row = score_case(case, planted, clean)
        row["builds"] = {"planted": planted, "clean": clean}
        rows.append(row)
        sys.stderr.write(f"  {case['id']:52s} {row['outcome']:14s} {row.get('reason', '')}\n")
    return rows, frames


async def _run(run_dir: Path, cases: list[dict]) -> tuple[list[dict], dict]:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    with open(run_dir / "server.stderr.log", "w", encoding="utf-8") as errlog:
        async with stdio_client(_server_params(run_dir), errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await score_suite(session, cases)


def _freecad_version(rows: list[dict]) -> str | None:
    for row in rows:
        for build_result in row["builds"].values():
            if build_result and build_result.get("freecad_version"):
                return build_result["freecad_version"]
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--leg", required=True, choices=LEGS, help="CI leg the evidence names")
    parser.add_argument("--run", dest="run_id", help="run id (default g3r-<date>-<leg>)")
    parser.add_argument("--check", action="store_true", help="do not write validators.yaml")
    parser.add_argument("--frames-check", type=Path, help="reference frames file to compare")
    args = parser.parse_args(argv)

    today = date.today().isoformat()
    run_id = args.run_id or f"g3r-{today}-{args.leg}"
    run_dir = ARTIFACTS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    rows, frames = asyncio.run(_run(run_dir, load_cases()))
    with open(run_dir / "cases.jsonl", "w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row) + "\n")
    evidence = {"leg": args.leg, "freecad_version": _freecad_version(rows), "frames": frames}
    evidence_path = run_dir / f"G3.E.3.{args.leg}.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )

    totals = tally(rows)
    sys.stderr.write(
        f"  planted={totals['planted']} detected={totals['detected']} "
        f"controls={totals['controls']} flagged={totals['flagged']} "
        f"sensitivity={totals['sensitivity']:.3f} false_alarm={totals['false_alarm']:.3f}\n"
    )
    for label in ("missed", "false_alarms", "invalid"):
        if totals[label]:
            sys.stderr.write(f"  {label.upper()}: {', '.join(totals[label])}\n")
    sys.stderr.write(f"  evidence: {evidence_path}\n")

    failed = not bars_met(totals)
    if args.frames_check is not None:
        reference = json.loads(args.frames_check.read_text(encoding="utf-8"))["frames"]
        drifts = compare_frames(reference, frames)
        for drift in drifts:
            sys.stderr.write(f"  FRAME DRIFT {drift}\n")
        sys.stderr.write(f"  frames-check: {'FAIL' if drifts else 'OK'} vs {args.frames_check}\n")
        failed = failed or bool(drifts)

    if args.check or totals["invalid"]:
        sys.stderr.write("  validators.yaml not written\n")
    else:
        block = render_block(validator_sha(), totals, run_id, today)
        VALIDATORS_YAML.write_text(
            merge_validators_yaml(VALIDATORS_YAML.read_text(encoding="utf-8"), {VALIDATOR: block}),
            encoding="utf-8",
            newline="\n",
        )
        sys.stderr.write(f"  wrote {VALIDATORS_YAML}\n")
    if failed:
        sys.stderr.write("  BARS NOT MET, a case is INVALID_INPUT, or a frame drifted\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
