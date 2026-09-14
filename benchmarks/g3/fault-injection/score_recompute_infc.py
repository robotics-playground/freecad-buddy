"""In-FreeCAD fault scorer for ``verify_recompute`` (the ``recompute/`` suite).

Run under FreeCADCmd with the scoring opt-in set, so importing this module for its helpers never
starts a scoring run::

    FREECAD_BUDDY_RUN_FAULT_SCORER=1 FreeCADCmd score_recompute_infc.py

Separate from ``score_g3_infc.py`` because the two measure different things by different means.
That scorer drives a PLAN through ``designer_loop.run_designer_loop`` and reads a geometry
assertion verdict. ``verify_recompute`` grades DOCUMENT STATE, not geometry: there is no plan, no
spec to violate and no assertion to evaluate. A case here builds a document through the production
mutation bracket, plants its fault through another bracket, and reads the validator's own verdict.

**Detection is the validator's verdict, never the case's declaration.** A case is DETECTED when
``verify_recompute`` returns ``RECOMPUTE_ERROR``, and a control is PASS_CLEAN when it returns
``OK``. Reading ``fault.kind`` off the case would report perfect sensitivity while measuring
nothing — the defect the registry exists to prevent.

Writes ``verify_recompute.json`` beside this file for the uv-side ``score_g3_validators.py`` to
read, the same handoff ``score_g3_infc.py`` uses: the measurement needs FreeCAD, and the registry
write needs pyyaml, which AD-12 keeps out of FreeCAD's bundled Python.
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
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
for path in (str(SRC), str(REPO_ROOT), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)

import planted_recomputes  # noqa: E402

VALIDATOR = "verify_recompute"
SUITE_DIR = HERE / "recompute"

# The verdict ``verify_recompute`` returns when it finds an object in an error state. Detection is
# this string and nothing else, so a case cannot be graded by what it claims about itself.
RECOMPUTE_ERROR = "RECOMPUTE_ERROR"


class SuiteError(SystemExit):
    """A malformed / degenerate fault suite — exit non-zero with a clean message, never write."""


def _scalar(text: str, key: str) -> str | None:
    """The value of a top-level ``key: value`` line, unquoted, or ``None``."""
    match = re.search(rf"^{key}:\s*(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip().strip("'\"") if match else None


def _load_case(case_yaml: Path) -> dict:
    """Parse the fixed recompute ``case.yaml`` shape.

    pyyaml is an external-process dependency (AD-12) and this runs inside FreeCADCmd, so the small
    fixed shape is parsed here rather than loaded.

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
    return {
        "id": case_id,
        "expectation": expectation,
        "planted_op": planted_op,
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


def _mutate(registry, handle: str, label: str, op) -> dict:
    """Run ``op`` through the production mutation bracket and rebind the document it returns.

    The rebind is mandatory: the snapshot-restore rollback path closes and reopens the document, so
    a handle left pointing at the original object would address a closed one (DW-71). Every planted
    fault here runs after at least one bracket that may have taken that path.
    """
    from freecad_buddy.usecases import transaction

    document = registry.with_document(handle, lambda _handle, doc: doc)
    rebound, envelope = transaction.run_mutation(
        document, handle, label, op, tool="plant_recompute_fault", params={"label": label}
    )
    registry.rebind(handle, rebound)
    return envelope


def _build_fixture(registry, handle: str, fixture: str) -> list[str]:
    """Build one case's starting document and return the status of each bracket it ran.

    ``parameter_edit`` is driven through ``usecases.parameters`` rather than a bare builder,
    because G3.3's editability path IS the parameter facade: declaring a driving dimension and
    writing a new value is the production scenario the criterion cites this validator for, and a
    control that only pretended to do it would prove nothing about that leg.
    """
    from freecad_buddy.usecases import parameters

    if fixture == "parameter_edit":
        statuses = [_mutate(registry, handle, "build box", planted_recomputes.build_box)["status"]]
        statuses.append(
            parameters.declare(
                registry,
                doc=handle,
                name=planted_recomputes.PARAMETER_NAME,
                value=planted_recomputes.PARAMETER_VALUE,
                unit="mm",
                drives=["Box.Height"],
            )["status"]
        )
        statuses.append(
            parameters.set_value(
                registry,
                doc=handle,
                name=planted_recomputes.PARAMETER_NAME,
                value=planted_recomputes.PARAMETER_EDITED_VALUE,
                unit="mm",
            )["status"]
        )
        return statuses

    brackets = planted_recomputes.BUILDERS.get(fixture)
    if brackets is None:
        known = sorted(planted_recomputes.BUILDERS)
        raise SuiteError(f"no fixture named {fixture!r} (known: {known})")
    return [_mutate(registry, handle, label, builder)["status"] for label, builder in brackets]


def run_case(case: dict) -> tuple[bool, str]:
    """Build the case's document, plant its fault, and read the validator's verdict.

    Returns ``(detected, verdict)`` where ``detected`` is the validator reporting
    ``RECOMPUTE_ERROR`` and ``verdict`` is the short string the per-case table prints.

    :raises planted_recomputes.PlanNotDriveable: the fixture failed in a way the case did not
        declare, so whatever the validator then reads is not the state the case meant to plant.
    """
    import FreeCAD as App

    from freecad_buddy.usecases import verify
    from freecad_buddy.usecases.documents import DocumentRegistry

    op_name = case["planted_op"]
    plant = planted_recomputes.resolve(op_name)
    fixture = planted_recomputes.FIXTURES.get(op_name)
    if fixture is None:
        raise SuiteError(f"planted_op {op_name!r} declares no fixture")

    registry = DocumentRegistry()
    handle = registry.document_create(label=case["id"])["structured_content"]["doc"]
    try:
        fixture_statuses = _build_fixture(registry, handle, fixture)
        expected_failing = fixture in planted_recomputes.EXPECTED_FAILING_FIXTURES
        unexpected = [s for s in fixture_statuses if s != "OK"]
        if unexpected and not expected_failing:
            raise planted_recomputes.PlanNotDriveable(
                f"fixture {fixture!r} did not build: bracket statuses {fixture_statuses}"
            )
        if expected_failing and all(s == "OK" for s in fixture_statuses):
            # The control measures what a FAILED mutation's rollback left behind. A fixture that
            # unexpectedly succeeded never produced that state, so grading the validator against it
            # would measure a different document than the case declares.
            raise planted_recomputes.PlanNotDriveable(
                f"fixture {fixture!r} was expected to fail its bracket and every status was OK: "
                f"{fixture_statuses}"
            )

        plant_status = _mutate(registry, handle, f"plant {op_name}", plant)["status"]

        envelope = verify.verify_recompute(registry, doc=handle)
        content = envelope["structured_content"]
        verdict = content["verdict"]
        failing = content["subject"]["failing_objects"]
        detected = verdict == RECOMPUTE_ERROR
        return detected, f"plant={plant_status}/{verdict}/{','.join(failing) or '-'}"
    finally:
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)


def score_suite() -> dict:
    """Drive every case in the recompute suite and tally the two bars over what actually ran."""
    rows: list[dict] = []
    skipped: list[dict] = []
    planted = controls = detected = flagged = 0

    for case in load_cases(SUITE_DIR):
        reason = planted_recomputes.UNDRIVEABLE.get(case["planted_op"])
        if reason:
            skipped.append({"id": case["id"], "expectation": case["expectation"], "reason": reason})
            continue
        try:
            is_detected, verdict = run_case(case)
        except planted_recomputes.PlanNotDriveable as exc:
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

        if case["expectation"] == "DETECT":
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
        "validator": VALIDATOR,
        "planted": planted,
        "controls": controls,
        "detected": detected,
        "flagged": flagged,
        "rows": rows,
        "skipped": skipped,
    }


def results_path() -> Path:
    """Where the external scorer reads the per-case outcomes from."""
    return HERE / f"{VALIDATOR}.json"


def main(argv: list[str] | None = None) -> int:
    """Drive the suite, print the per-case table, and write the results file.

    ``--check`` drives nothing and writes nothing; it only asserts every case resolves to a
    callable with a declared fixture, which is the structural half CI can run without geometry
    time.
    """
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        unresolved = [
            case["id"]
            for case in load_cases(SUITE_DIR)
            if case["planted_op"] not in planted_recomputes.REGISTRY
            or case["planted_op"] not in planted_recomputes.FIXTURES
        ]
        if unresolved:
            sys.stderr.write(f"  planted_op resolves to no callable/fixture for: {unresolved}\n")
            return 1
        sys.stderr.write("  --check: every planted_op resolves; nothing driven, nothing written\n")
        return 0

    result = score_suite()
    for row in result["rows"]:
        sys.stderr.write(
            f"  {row['id']:56s} {row['expectation']:11s} {row['verdict']:44s} {row['outcome']}\n"
        )
    for entry in result["skipped"]:
        sys.stderr.write(f"  {entry['id']:56s} NOT DRIVEABLE: {entry['reason'][:110]}\n")
    sys.stderr.write(
        f"  {VALIDATOR:18s} planted={result['planted']:2d} controls={result['controls']:2d} "
        f"detected={result['detected']:2d} flagged={result['flagged']:2d}\n"
    )
    path = results_path()
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
