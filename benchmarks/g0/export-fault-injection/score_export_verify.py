"""Fault scorer for the export verifiers.

For every ``case.yaml`` in this suite the scorer runs the case's target verifier over the
committed exported file and records the DETECT / PASS_CLEAN outcome. The mesh verifiers
(``verify_export_stl``/``verify_export_3mf``) run their trimesh/second-oracle/lib3mf legs
directly against the committed ``.stl``/``.3mf`` — no FreeCAD needed to re-read a written mesh.
``verify_export_step`` re-imports the committed ``.step`` into a fresh document, so it is scored
only when FreeCAD is importable. Whichever verifiers this environment can score are merged into
``_registry/validators.yaml`` — the existing ``verify_shape`` block and any verifier block this
run did not touch are preserved (load-merge, never full-clobber).

Per verifier the scorer computes sensitivity / false-alarm + a Wilson CI, hashes the validator
sources into ``validator_sha``, and exits non-zero when any scored verifier misses the bars. No
single CI leg has both FreeCAD and the oracles, so a run scores the subset it can and preserves
the rest; the union is covered across the uv and FreeCADCmd legs.
"""

from __future__ import annotations

import datetime
import hashlib
import os
import sys
from collections.abc import Mapping
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from freecad_buddy.usecases import stats  # noqa: E402

VALIDATORS_YAML = REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml"
VALIDATOR_SOURCES = (
    SRC / "freecad_buddy" / "usecases" / "exports.py",
    SRC / "freecad_buddy" / "adapters" / "export_oracle.py",
    SRC / "freecad_buddy" / "adapters" / "export_verdict.py",
)

SENSITIVITY_BAR = 0.95
FALSE_ALARM_BAR = 0.05
MIN_PLANTED = 10
MIN_CONTROLS = 1


class SuiteError(SystemExit):
    """A malformed / degenerate fault suite — exit non-zero with a clean message, never write."""


def _parse_scalar(text: str):
    text = text.strip()
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if text.startswith("[") and text.endswith("]"):
        return [_parse_scalar(part) for part in text[1:-1].split(",") if part.strip()]
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text.strip("'\"")


def _load_case(case_yaml: Path) -> dict:
    """Parse the fixed export ``case.yaml`` shape (id, validator, format, expectation, source)."""
    case: dict = {"dir": case_yaml.parent, "source": {}, "tess": {}}
    section = None
    for raw in case_yaml.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indented = raw[0] in " \t"
        key, _, value = raw.strip().partition(":")
        key = key.strip()
        value = value.strip()
        if not indented:
            section = None
            if key in ("source", "tess") and value == "":
                section = key
            elif key == "id":
                case["id"] = value
            elif key == "targets_validator":
                case["validator"] = value
            elif key == "format":
                case["format"] = value
            elif key == "expectation":
                case["expectation"] = value
            elif key == "export_file":
                case["export_file"] = value
        elif section:
            case[section][key] = _parse_scalar(value)
    return case


def _mesh_band(case: dict) -> float:
    from freecad_buddy.usecases import exports

    source = case["source"]
    area = source.get("area")
    if area is None:
        lx, ly, lz = source["bbox"]
        area = 2.0 * (lx * ly + lx * lz + ly * lz)
    return exports.mesh_volume_band(case["tess"]["linear"], area)


def _score_mesh_case(case: dict) -> bool:
    """Return whether the mesh verifier flags ``case`` (non-OK verdict), reading the file only."""
    from freecad_buddy.adapters import export_oracle, export_verdict

    path = str(case["dir"] / case["export_file"])
    source = case["source"]
    band = _mesh_band(case)
    facts = {
        "self_read": {"facets": 0, "vertices": 0, "bbox": source["bbox"]},
        "recorded": {"facets": 0, "vertices": 0},
        "path": path,
        "volume_band": band,
        "tess": case["tess"],
    }
    # Route every oracle leg through safe_oracle exactly as the production host handler does, so a
    # leg that raises becomes a failed leg (→ FAIL) rather than being blanket-scored DETECT — a
    # clean control that raised for an unrelated reason must surface as a false alarm, not masked.
    if case["format"] == "stl":
        legs = [
            export_oracle.safe_oracle(
                "trimesh_stl", lambda: export_oracle.stl_oracle(path, source["volume"], band)
            ),
            export_oracle.safe_oracle(
                "stdlib_stl", lambda: export_oracle.StdlibStlOracle().check(path)
            ),
        ]
    else:
        legs = [
            export_oracle.safe_oracle(
                "lib3mf",
                lambda: export_oracle.mesh3mf_oracle(path, source["is_mm"], source["volume"], band),
            ),
        ]
    envelope = export_verdict.assemble_export_verdict(legs, facts, banner={})
    return envelope["status"] != "OK"


def _score_step_case(case: dict) -> bool:
    """Return whether ``verify_export_step`` flags ``case``; re-imports the committed STEP."""
    import Part

    from freecad_buddy.usecases import exports

    path = str(case["dir"] / case["export_file"])
    source = {k: case["source"][k] for k in ("volume", "faces", "edges", "solids")}
    shape = Part.Shape()
    shape.read(path)
    checks = exports._step_checks(shape, source)
    return any(not c["passed"] for c in checks)


def _freecad_available() -> bool:
    try:
        import FreeCAD  # noqa: F401
    except ImportError:
        return False
    return True


def _oracles_available() -> bool:
    try:
        import lib3mf  # noqa: F401
        import trimesh  # noqa: F401
    except ImportError:
        return False
    return True


def _validator_sha() -> str:
    """SHA-256 over the concatenated export-verifier source files."""
    hasher = hashlib.sha256()
    for path in VALIDATOR_SOURCES:
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _score_validator(validator: str, cases: list[dict], scorer) -> dict:
    """Run ``scorer`` over ``cases`` for one validator; return its aggregate result + rows.

    Raises ``SuiteError`` when the validator has fewer than ``MIN_PLANTED`` planted cases or
    fewer than ``MIN_CONTROLS`` controls: ``false_alarm`` is vacuously 0 with no controls and
    ``sensitivity`` is vacuously 1 over a thin planted arm, so the bars must never be evaluated
    over a degenerate partition.
    """
    planted = [c for c in cases if c["expectation"] == "DETECT"]
    controls = [c for c in cases if c["expectation"] == "PASS_CLEAN"]
    if len(planted) < MIN_PLANTED or len(controls) < MIN_CONTROLS:
        raise SuiteError(
            f"degenerate suite for {validator}: need >={MIN_PLANTED} planted + "
            f">={MIN_CONTROLS} controls, have planted={len(planted)} "
            f"controls={len(controls)} — the bars would be vacuous"
        )
    detected = 0
    flagged = 0
    rows = []
    for case in cases:
        non_ok = scorer(case)
        is_defect = case["expectation"] == "DETECT"
        if is_defect and non_ok:
            detected += 1
            outcome = "DETECTED"
        elif is_defect:
            outcome = "MISSED"
        elif non_ok:
            flagged += 1
            outcome = "FALSE_ALARM"
        else:
            outcome = "PASS_CLEAN"
        rows.append((case["id"], case["expectation"], outcome))
    return {
        "validator": validator,
        "rows": rows,
        "planted": len(planted),
        "controls": len(controls),
        "detected": detected,
        "flagged": flagged,
        "sensitivity": stats.sensitivity(detected, len(planted)),
        "false_alarm": stats.false_alarm(flagged, len(controls)),
        "wilson_ci": stats.wilson_ci(detected, len(planted)),
    }


def score() -> dict:
    """Score every export verifier this environment can run; return per-validator results.

    Groups the committed cases by ``targets_validator`` and scores the mesh verifiers when the
    oracles are importable and the STEP verifier when FreeCAD is importable. Returns a dict
    keyed by validator name; verifiers this environment cannot score are absent.
    """
    cases = [_load_case(p) for p in sorted(HERE.rglob("case.yaml"))]
    by_validator: dict[str, list[dict]] = {}
    for case in cases:
        by_validator.setdefault(case["validator"], []).append(case)

    results: dict[str, dict] = {}
    if _oracles_available():
        for validator in ("verify_export_stl", "verify_export_3mf"):
            if validator in by_validator:
                results[validator] = _score_validator(
                    validator, by_validator[validator], _score_mesh_case
                )
    if _freecad_available():
        if "verify_export_step" in by_validator:
            results["verify_export_step"] = _score_validator(
                "verify_export_step", by_validator["verify_export_step"], _score_step_case
            )
    return results


def _render_block(validator: str, sha: str, run: dict) -> str:
    """Render one ``verify_export_*`` validators.yaml block."""
    wilson = run["wilson_ci"]
    return (
        f"{validator}:\n"
        "  suite: g0/export-fault-injection/\n"
        f'  validator_sha: "{sha}"\n'
        "  last_run:\n"
        f"    run_id: {run['run_id']}\n"
        f"    sensitivity: {run['sensitivity']}\n"
        f"    false_alarm: {run['false_alarm']}\n"
        f"    date: {run['date']}\n"
        "    wilson_ci:\n"
        f"      rate: {wilson['rate']}\n"
        f"      low: {wilson['low']}\n"
        f"      high: {wilson['high']}\n"
        f"      n: {wilson['n']}\n"
        f"      r: {wilson['r']}\n"
    )


def _split_blocks(text: str) -> dict[str, str]:
    """Split validators.yaml into ``{top_key: block_text}``, preserving leading comments.

    A block starts at a column-0 ``key:`` line and runs until the next column-0 key. The file's
    leading comment lines are attached to the first block under the key ``__header__``.
    """
    blocks: dict[str, str] = {}
    header: list[str] = []
    current_key = None
    current: list[str] = []
    seen_key = False
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\n")
        is_top = stripped and stripped[0] not in " \t#" and ":" in stripped
        if is_top:
            if current_key is not None:
                blocks[current_key] = "".join(current)
            current_key = stripped.split(":", 1)[0].strip()
            current = [line]
            seen_key = True
        elif not seen_key:
            header.append(line)
        else:
            current.append(line)
    if current_key is not None:
        blocks[current_key] = "".join(current)
    if header:
        blocks["__header__"] = "".join(header)
    return blocks


def merge_validators_yaml(text: str, rendered: dict[str, str]) -> str:
    """Return ``text`` with each ``rendered`` block replacing/appending its validator, else kept.

    The leading comment header and every validator block not in ``rendered`` (notably
    ``verify_shape``) are preserved verbatim; only the supplied blocks are rewritten or added.
    """
    blocks = _split_blocks(text)
    header = blocks.pop("__header__", "")
    ordered: list[str] = []
    for key, block in blocks.items():
        ordered.append(rendered.get(key, block).rstrip("\n"))
    for key, block in rendered.items():
        if key not in blocks:
            ordered.append(block.rstrip("\n"))
    body = "\n\n".join(ordered)
    return f"{header.rstrip(chr(10))}\n\n{body}\n" if header else f"{body}\n"


def main() -> int:
    results = score()
    if not results:
        sys.stderr.write(
            "  no export verifier could be scored here (need trimesh+lib3mf or FreeCAD)\n"
        )
        return 1

    sha = _validator_sha()
    today = datetime.date.today().isoformat()
    rendered: dict[str, str] = {}
    failed = False

    for validator, result in results.items():
        for case_id, expectation, outcome in result["rows"]:
            sys.stderr.write(f"  {validator:20s} {case_id:28s} {expectation:11s} {outcome}\n")
        sensitivity = result["sensitivity"]
        false_alarm = result["false_alarm"]
        wilson = result["wilson_ci"]
        sys.stderr.write(
            f"  {validator}: sensitivity={sensitivity:.3f} false_alarm={false_alarm:.3f} "
            f"wilson=[{wilson['low']:.3f}, {wilson['high']:.3f}]\n"
        )
        run = {
            "run_id": f"er-{today}-1",
            "sensitivity": round(sensitivity, 4),
            "false_alarm": round(false_alarm, 4),
            "date": today,
            "wilson_ci": {
                "rate": round(wilson["rate"], 4),
                "low": round(wilson["low"], 4),
                "high": round(wilson["high"], 4),
                "n": wilson["n"],
                "r": wilson["r"],
            },
        }
        rendered[validator] = _render_block(validator, sha, run)
        if sensitivity < SENSITIVITY_BAR or false_alarm > FALSE_ALARM_BAR:
            failed = True

    merged = merge_validators_yaml(VALIDATORS_YAML.read_text(encoding="utf-8"), rendered)
    VALIDATORS_YAML.write_text(merged, encoding="utf-8")
    sys.stderr.write(f"  wrote {VALIDATORS_YAML} ({', '.join(results)})\n")

    if failed:
        sys.stderr.write("  BARS NOT MET: sensitivity<0.95 or false_alarm>0.05\n")
        return 1
    return 0


_RUN_FLAG = "FREECAD_BUDDY_RUN_EXPORT_SCORER"


def _run_requested_in(env: Mapping[str, str]) -> bool:
    """Whether ``env`` carries the explicit scoring-run opt-in."""
    return env.get(_RUN_FLAG) == "1"


def _run_requested() -> bool:
    """Whether an explicit opt-in asked for a scoring run (import never scores)."""
    return __name__ == "__main__" or _run_requested_in(os.environ)


if _run_requested():
    sys.exit(main())
