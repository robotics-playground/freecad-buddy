"""In-FreeCAD fault scorer for the G3 validators whose faults the designer loop can plant.

Run under FreeCADCmd with the scoring opt-in set, so importing this module for its helpers never
starts a scoring run::

    FREECAD_BUDDY_RUN_FAULT_SCORER=1 FreeCADCmd score_g3_infc.py
    $env:FREECAD_BUDDY_RUN_FAULT_SCORER="1"; FreeCADCmd score_g3_infc.py

Two suites are driven — ``corrupted-plan/`` (targeting ``corrupted_plan``) and ``assertions/``
(targeting ``g3_assertions``). For every case in them: resolve the case's ``planted_op`` in
``planted_plans.REGISTRY``, drive the plan it returns through
``usecases.designer_loop.run_designer_loop``, and read the verdict from
``designer_loop.detect_spec_violation`` over the checks the case's ``spec_ref`` declares.

The two validators measure different things over the same mechanism: ``corrupted_plan`` asks
whether the LOOP notices that the part it built violates its spec, and ``g3_assertions`` asks
whether the assertion PRIMITIVES catch a wrong part. Both read the same measurement, which is the
point — a loop that checks its own output and a measurement that can see the defect are the two
halves G3.4 needs, and folding them into one number would let a strong half carry a weak one.

The ``visual-judge/`` suite is NOT driven: its verdict needs a credentialed vision call, which
decision 017 keeps out of unattended CI. Its cases stay ``fixture: pending`` and its validator
stays ``not_scored``.

**Detection measures the produced artifact.** The plan is never inspected. A planted defect is
DETECTED when an assertion over the part the loop built failed; a clean control is PASS_CLEAN when
every assertion passed. This is the distinction the whole suite exists to make: a scorer that read
``corruption_class`` off the case would report perfect sensitivity while measuring nothing.

The **geometry leg only** is scored here. The visual leg needs a live vision call, so this scorer
wires a visual leg that reports ``visual.unavailable`` — the honest fail-closed state, which means
every run ends ``CAP_EXHAUSTED`` rather than ``CONVERGED``. That does not affect what these two
validators measure: ``detect_spec_violation`` reads the geometry checks, and a clean control's
geometry passing is exactly what a false alarm would contradict. The registry row says so rather
than implying a judged run.

Writes one ``<validator>.json`` beside this file per driven suite, for the external scorer to
read, so the uv-side ``score_g3_validators.py`` records a measured number instead of
``not_scored``.

pyyaml is an external-process dependency (AD-12); this scorer runs inside FreeCADCmd and parses the
small fixed ``case.yaml`` shape itself.
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from collections.abc import Mapping
from pathlib import Path

HERE = Path(__file__).resolve().parent
G3_ROOT = HERE.parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
for path in (str(SRC), str(REPO_ROOT), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)

import planted_plans  # noqa: E402

from benchmarks.harness import assertions  # noqa: E402
from freecad_buddy.contracts import VISUAL_CHECK_ID, VISUAL_UNAVAILABLE_CODE  # noqa: E402
from freecad_buddy.usecases import confirm, designer_loop  # noqa: E402

# The suites this scorer drives: validator name -> its case directory. ``visual-judge`` is absent
# on purpose (see the module docstring).
DRIVEN_SUITES = {
    "corrupted_plan": HERE / "corrupted-plan",
    "g3_assertions": HERE / "assertions",
}

DEV_DIR = G3_ROOT / "dev"


def results_path(validator: str) -> Path:
    """Where the external scorer reads one validator's per-case outcomes from."""
    return HERE / f"{validator}.json"


class SuiteError(SystemExit):
    """A malformed / degenerate fault suite — exit non-zero with a clean message, never write."""


def _scalar(text: str, key: str) -> str | None:
    """The value of a top-level ``key: value`` line, unquoted, or ``None``."""
    match = re.search(rf"^{key}:\s*(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip().strip("'\"") if match else None


def _load_case(case_yaml: Path) -> dict:
    """Parse the fixed G3 corrupted-plan ``case.yaml`` shape.

    :raises SuiteError: a required key is missing or the kind/expectation pair disagrees.
    """
    text = case_yaml.read_text(encoding="utf-8")
    case_id = _scalar(text, "id")
    if not case_id:
        raise SuiteError(f"{case_yaml}: no 'id'")
    kind = _scalar(text, "  kind") or _scalar(text, "kind")
    expectation = _scalar(text, "  expectation") or _scalar(text, "expectation")
    if (kind == "planted_defect") != (expectation == "DETECT") or (kind == "clean_control") != (
        expectation == "PASS_CLEAN"
    ):
        raise SuiteError(
            f"case {case_id!r}: fault.kind {kind!r} disagrees with expectation {expectation!r} "
            "(planted_defect<->DETECT, clean_control<->PASS_CLEAN)"
        )
    planted_op = _scalar(text, "planted_op")
    if not planted_op:
        raise SuiteError(f"case {case_id!r}: no 'planted_op'")
    spec_ref = _scalar(text, "spec_ref")
    if not spec_ref:
        raise SuiteError(f"case {case_id!r}: no 'spec_ref'")
    return {
        "id": case_id,
        "expectation": expectation,
        "planted_op": planted_op,
        "spec_ref": spec_ref,
        "detected_by": _scalar(text, "detected_by"),
        "dir": case_yaml.parent,
    }


def load_cases(suite_dir: Path) -> list[dict]:
    """Every case under ``suite_dir``, parsed, ordered by suite-relative path."""
    files = sorted(
        (p for p in suite_dir.rglob("case.yaml") if p.name == "case.yaml"),
        key=lambda p: p.relative_to(suite_dir).as_posix(),
    )
    return [_load_case(path) for path in files]


def _spec_assertions(spec_ref: str) -> tuple[list, dict | None]:
    """The ``checks`` and ``anchor_frame`` the referenced dev spec declares.

    Read from the spec's own ``case.yaml``, never restated here: the assertions were compiled
    before any designer code existed (AD-19), and a copy in the scorer could drift from the
    contract the gate grades against.

    :raises SuiteError: the spec is absent or declares no checks.
    """
    case_yaml = DEV_DIR / spec_ref / "case.yaml"
    if not case_yaml.is_file():
        raise SuiteError(f"spec_ref {spec_ref!r} names no dev case: {case_yaml}")
    text = case_yaml.read_text(encoding="utf-8")
    checks = _parse_checks(text)
    if not checks:
        raise SuiteError(f"spec {spec_ref!r} declares no assertions.checks")
    return checks, _parse_anchor_frame(text)


_CHECK_LINE = re.compile(r"^\s*-\s*\{(.+)\}\s*$")


def _parse_checks(text: str) -> list[dict]:
    """Parse the ``assertions.checks`` flow-mapping list out of a dev ``case.yaml``.

    Every G3 dev case writes one check per line as a YAML flow mapping, so a line regex plus a
    JSON-ish value parse covers the whole set. A case that ever stops using that shape fails here
    loudly rather than being scored against a partial check list.
    """
    inside = False
    checks: list[dict] = []
    for line in text.splitlines():
        if re.match(r"^\s*checks:\s*$", line):
            inside = True
            continue
        if inside:
            match = _CHECK_LINE.match(line)
            if match is None:
                if line.strip() and not line.startswith(" "):
                    break
                continue
            checks.append(_parse_flow_mapping(match.group(1)))
    return checks


def _parse_anchor_frame(text: str) -> dict | None:
    """Parse the ``anchor_frame`` flow mapping out of a dev ``case.yaml``, or ``None``."""
    match = re.search(r"^\s*anchor_frame:\s*\{(.+)\}\s*$", text, re.MULTILINE)
    return _parse_flow_mapping(match.group(1)) if match else None


def _parse_flow_mapping(body: str) -> dict:
    """Parse one ``{k: v, k: v}`` body into a dict, converting each value by YAML's scalar rules.

    Handles the nested ``tol: {abs: 0.05}`` the checks carry by splitting on commas that are not
    inside braces or brackets.
    """
    result: dict = {}
    for part in _split_top_level(body):
        key, _, raw = part.partition(":")
        result[key.strip()] = _parse_value(raw.strip())
    return result


def _split_top_level(body: str) -> list[str]:
    """Split ``body`` on commas that are not nested inside braces or brackets."""
    parts: list[str] = []
    depth = 0
    current = ""
    for char in body:
        if char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        current += char
    if current.strip():
        parts.append(current)
    return parts


def _parse_value(raw: str):
    """Convert one YAML scalar / flow value: bool, null, number, list, mapping, or string."""
    if raw.startswith("{") and raw.endswith("}"):
        return _parse_flow_mapping(raw[1:-1])
    if raw.startswith("[") and raw.endswith("]"):
        return [_parse_value(item.strip()) for item in _split_top_level(raw[1:-1])]
    lowered = raw.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~", ""):
        return None
    try:
        return int(raw) if re.fullmatch(r"-?\d+", raw) else float(raw)
    except ValueError:
        return raw.strip("'\"")


def _unavailable_visual(_doc, _geometry_passed) -> dict:
    """The fail-closed visual leg this scorer runs with: no live judge call is made.

    Decision 017 keeps the credentialed vision call out of unattended CI, so the honest state here
    is ``visual.unavailable`` — which blocks done, exactly as the shipped rule requires. Returning
    a pass to let runs converge would make every corrupted-plan run look judged when none was.
    """
    return {
        "id": VISUAL_CHECK_ID,
        "measured": None,
        "measured_kind": None,
        "expected": True,
        "tolerance": None,
        "passed": False,
        "detail": {
            "code": VISUAL_UNAVAILABLE_CODE,
            "message": (
                "the fault scorer makes no live judge call (decision 017), so the visual leg is "
                "fail-closed and only the geometry leg is scored here"
            ),
            "objects": [],
        },
    }


def run_case(case: dict) -> tuple[bool, str]:
    """Drive one case's plan through the loop; return ``(detected, verdict)``.

    ``detected`` is what ``detect_spec_violation`` concluded over the assertions measured on the
    produced artifact. ``verdict`` is the short string the per-case table prints.
    """
    import FreeCAD as App

    from freecad_buddy.usecases.documents import DocumentRegistry

    build_plan = planted_plans.resolve(case["planted_op"])
    plan = build_plan()
    checks, anchor_frame = _spec_assertions(case["spec_ref"])

    registry = DocumentRegistry()
    handle = registry.document_create(label=case["id"])["structured_content"]["doc"]
    previous = confirm.set_auto_approve(True)
    try:
        record = designer_loop.run_designer_loop(
            registry,
            plan,
            checks,
            assertions.evaluate,
            _unavailable_visual,
            doc=handle,
            run_id=case["id"],
            anchor_frame=anchor_frame,
            extra_tools={"plan_shape": planted_plans.shape_step},
        )
        iteration = record["iterations"][0]
        # ``detected_by`` is a reporting preference, never a detection condition: the case is
        # detected when ANY assertion over the produced part failed, and naming the case's own
        # assertion lets the table say which measurement it was authored around.
        violation = designer_loop.detect_spec_violation(
            iteration["checks"], preferred=case["detected_by"]
        )
        detected = violation is not None
        caught_by = violation["check_id"] if violation else "-"
        return detected, f"{record['status']}/{caught_by}"
    finally:
        confirm.set_auto_approve(previous)
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)


def score_suite(validator: str, suite_dir: Path) -> dict:
    """Drive every case in one suite and tally the two bars over what actually ran."""
    rows: list[dict] = []
    skipped: list[dict] = []
    planted = controls = detected = flagged = 0

    for case in load_cases(suite_dir):
        reason = planted_plans.UNDRIVEABLE.get(case["planted_op"])
        if reason:
            # ``expectation`` travels with the skip so a consumer can tell an excluded DEFECT
            # from an excluded control. G3.4's bar counts authored defects, and a skip record that
            # lost which kind it was would shrink that denominator invisibly.
            skipped.append({"id": case["id"], "expectation": case["expectation"], "reason": reason})
            continue
        try:
            is_detected, verdict = run_case(case)
        except planted_plans.PlanNotDriveable as exc:
            skipped.append(
                {"id": case["id"], "expectation": case["expectation"], "reason": str(exc)}
            )
            continue
        except SuiteError:
            raise
        except Exception as exc:  # noqa: BLE001 - a case that crashed was never graded
            skipped.append(
                {
                    "id": case["id"],
                    "expectation": case["expectation"],
                    "reason": f"the run raised {type(exc).__name__}: {exc}",
                }
            )
            sys.stderr.write(f"  !! {case['id']}: {traceback.format_exc()}\n")
            continue

        is_defect = case["expectation"] == "DETECT"
        if is_defect:
            planted += 1
            outcome = "DETECTED" if is_detected else "MISSED"
            detected += int(is_detected)
        else:
            controls += 1
            outcome = "FALSE_ALARM" if is_detected else "PASS_CLEAN"
            flagged += int(is_detected)
        rows.append(
            {
                "id": case["id"],
                "expectation": case["expectation"],
                "detected_by": case["detected_by"],
                "verdict": verdict,
                "outcome": outcome,
            }
        )

    return {
        "validator": validator,
        "planted": planted,
        "controls": controls,
        "detected": detected,
        "flagged": flagged,
        "rows": rows,
        "skipped": skipped,
        # Stated on the artifact so the external scorer cannot record a judged run it did not see.
        "visual_leg": "fail-closed; no live judge call (decision 017). Geometry leg only.",
    }


def score() -> dict[str, dict]:
    """Drive every suite this scorer owns; return ``{validator: result}``."""
    return {
        validator: score_suite(validator, suite_dir)
        for validator, suite_dir in sorted(DRIVEN_SUITES.items())
    }


def main(argv: list[str] | None = None) -> int:
    """Drive every suite, print the per-case table, and write one results file per validator.

    ``--check`` drives nothing and writes nothing; it only asserts every case resolves to a
    callable, which is the structural half CI can run without FreeCAD geometry time.
    """
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        unresolved = [
            case["id"]
            for suite_dir in DRIVEN_SUITES.values()
            for case in load_cases(suite_dir)
            if case["planted_op"] not in planted_plans.REGISTRY
        ]
        if unresolved:
            sys.stderr.write(f"  planted_op resolves to no callable for: {unresolved}\n")
            return 1
        sys.stderr.write("  --check: every planted_op resolves; nothing driven, nothing written\n")
        return 0

    for validator, result in sorted(score().items()):
        for row in result["rows"]:
            sys.stderr.write(
                f"  {row['id']:52s} {row['expectation']:11s} {row['verdict']:34s} "
                f"{row['outcome']}\n"
            )
        for entry in result["skipped"]:
            sys.stderr.write(f"  {entry['id']:52s} NOT DRIVEABLE: {entry['reason']}\n")
        sys.stderr.write(
            f"  {validator:16s} planted={result['planted']:2d} "
            f"controls={result['controls']:2d} detected={result['detected']:2d} "
            f"flagged={result['flagged']:2d}\n"
        )
        path = results_path(validator)
        path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        sys.stderr.write(f"  wrote {path}\n")
    return 0


_RUN_FLAG = "FREECAD_BUDDY_RUN_FAULT_SCORER"


def _run_requested_in(env: Mapping[str, str]) -> bool:
    """Whether ``env`` carries the explicit scoring-run opt-in."""
    return env.get(_RUN_FLAG) == "1"


def _run_requested() -> bool:
    """Whether direct execution or an explicit opt-in asked for a scoring run.

    An import never scores. FreeCADCmd sets ``__name__`` to the file stem rather than
    ``"__main__"``, so the launched-script path is matched against ``sys.argv[1]`` too.
    """
    if _run_requested_in(os.environ):
        return True
    if __name__ == "__main__":
        return True
    if len(sys.argv) > 1:
        try:
            return Path(sys.argv[1]).resolve() == Path(__file__).resolve()
        except OSError:
            return False
    return False


if _run_requested():
    sys.exit(main())
