"""External-process structural checker for the G2 fault suite (run under uv).

Validates the suite's shape without scoring it: that every case parses, declares a validator, pairs
``fault.kind`` with ``fault.expectation``, names a ``planted_op`` that resolves to a callable, and
carries a materialized fixture. It computes each validator's ``validator_sha`` over its sources and
the cases targeting it, so the registry's currency check has a value to compare against.

It does NOT produce sensitivity or false-alarm numbers, and never writes a ``last_run`` block.
Planting a fault means running its ``planted_op`` through the production mutation path, which needs
a live FreeCAD document; this process runs outside FreeCAD and has none. Reporting a rate from here
would mean reporting a number no run produced, so the scoring path refuses and names the scorer
that can do it:

    FREECAD_BUDDY_RUN_FAULT_SCORER=1 FreeCADCmd benchmarks/g2/fault-injection/score_g2_infc.py

Exits 0 when the suite is structurally sound, 1 when it is not.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

VALIDATORS_YAML = REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml"

# The source files whose bytes make up each validator's ``validator_sha``. A score stales the
# moment any of them changes, so a citation can never outlive the code it was measured over.
_USECASES = SRC / "freecad_buddy" / "usecases"
VALIDATOR_SOURCES = {
    "assertions": (
        REPO_ROOT / "benchmarks" / "harness" / "assertions.py",
        _USECASES / "assertions.py",
        _USECASES / "verify.py",
        SRC / "freecad_buddy" / "contracts" / "numbers.py",
    ),
    "run_mutation": (
        _USECASES / "transaction.py",
        SRC / "freecad_buddy" / "contracts" / "fingerprint.py",
        _USECASES / "result_projection.py",
    ),
    "fingerprint": (_USECASES / "fingerprint.py",),
    "audit_references": (_USECASES / "tnp_guard.py", _USECASES / "result_projection.py"),
    "verify_sketch": (_USECASES / "verify.py",),
}


class SuiteError(SystemExit):
    """A malformed / degenerate fault suite — exit non-zero with a clean message, never write."""


def _load_case(case_yaml: Path) -> dict:
    data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SuiteError(f"{case_yaml}: case.yaml must be a mapping, got {type(data).__name__}")
    data["dir"] = case_yaml.parent
    return data


def _suite_case_files() -> list[Path]:
    """Every G2 fault ``case.yaml``, ordered by its suite-relative POSIX path.

    The exact-name filter keeps the set platform-independent: ``rglob`` is case-insensitive on
    Windows, so a miscased ``Case.YAML`` would otherwise be scored and hashed there and not on
    Linux CI.
    """
    return sorted(
        (p for p in HERE.rglob("case.yaml") if p.name == "case.yaml"),
        key=lambda p: p.relative_to(HERE).as_posix(),
    )


def _validator_name(case: dict) -> str:
    """The validator a case targets, read from its ``targets_validator`` declaration."""
    declared = case.get("targets_validator")
    if not isinstance(declared, str) or not declared:
        raise SuiteError(f"case {case.get('id', '<no id>')!r}: missing 'targets_validator'")
    return declared.split("@", 1)[0]


def _validator_sha(name: str) -> str:
    """SHA-256 over a validator's sources and the cases scored against it.

    The suite is part of the validator: a score-preserving case edit changes the population the
    committed sensitivity was measured over, so it must stale the run too. Each case contributes
    its suite-relative path and its bytes, length-prefixed so the concatenation is unambiguous.

    A validator with no cases digests its sources under an explicit empty-suite marker, so its
    digest is never the source-only hash a populated suite could also produce.

    :param name: the validator whose digest is computed.
    :raises SuiteError: the validator is unknown, or a source file or case is unreadable.
    """
    sources = VALIDATOR_SOURCES.get(name)
    if sources is None:
        raise SuiteError(f"unknown validator {name!r} (no source set declared)")
    digest = hashlib.sha256()
    for path in sources:
        try:
            digest.update(path.read_bytes())
        except OSError as exc:
            raise SuiteError(f"unreadable validator source {path}: {exc}") from exc
    cases = [p for p in _suite_case_files() if _validator_name(_load_case(p)) == name]
    if not cases:
        digest.update(b"\x00no-fault-suite")
        return digest.hexdigest()
    for case_yaml in cases:
        identity = case_yaml.relative_to(HERE).as_posix().encode("utf-8")
        try:
            content = case_yaml.read_bytes()
        except OSError as exc:
            raise SuiteError(f"unreadable case {case_yaml}: {exc}") from exc
        digest.update(len(identity).to_bytes(4, "big"))
        digest.update(identity)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _partition(cases: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split cases into (planted defects, clean controls), rejecting a mis-tagged case.

    ``fault.kind`` and ``fault.expectation`` must agree, or the case is silently mis-partitioned
    and both bars are measured over the wrong population.
    """
    for case in cases:
        fault = case.get("fault")
        if not isinstance(fault, dict):
            raise SuiteError(f"case {case.get('id', '<no id>')!r}: 'fault' must be a mapping")
        kind = fault.get("kind")
        expectation = fault.get("expectation")
        if (kind == "planted_defect") != (expectation == "DETECT") or (kind == "clean_control") != (
            expectation == "PASS_CLEAN"
        ):
            raise SuiteError(
                f"case {case.get('id', '<no id>')!r}: fault.kind {kind!r} disagrees with "
                f"expectation {expectation!r} (planted_defect<->DETECT, clean_control<->PASS_CLEAN)"
            )
    planted = [c for c in cases if c["fault"]["expectation"] == "DETECT"]
    controls = [c for c in cases if c["fault"]["expectation"] == "PASS_CLEAN"]
    return planted, controls


def _fixture_materialized(case: dict) -> bool:
    """Whether the case's pre-mutation input document is present on disk."""
    fixture = case.get("fixture")
    if not isinstance(fixture, str) or fixture == "pending":
        return False
    return (case["dir"] / fixture).is_file()


def _op_names() -> set[str]:
    """The ``planted_op`` names that resolve to a callable.

    ``planted_ops`` imports FreeCAD, which this process does not have, so the registry's keys are
    read from its source rather than by importing it. The in-FreeCAD scorer resolves the same names
    through the real module; this check exists so a case naming an op nobody implemented is caught
    without FreeCAD.
    """
    source = (HERE / "planted_ops.py").read_text(encoding="utf-8")
    body = source.partition("REGISTRY = {")[2].partition("}")[0]
    return set(re.findall(r'^\s*"([^"]+)":', body, re.MULTILINE))


def check_suite() -> dict[str, dict]:
    """Check every cited validator's suite structurally; return ``{validator: result}``.

    Each result carries the planted/control counts, how many cases carry a materialized fixture,
    and any ``problems`` found. No rate is computed: see the module docstring.
    """
    by_validator: dict[str, list[dict]] = {}
    for case_yaml in _suite_case_files():
        case = _load_case(case_yaml)
        by_validator.setdefault(_validator_name(case), []).append(case)

    known_ops = _op_names()
    results: dict[str, dict] = {}
    for name in sorted(VALIDATOR_SOURCES):
        cases = by_validator.get(name, [])
        if not cases:
            results[name] = {
                "planted": 0,
                "controls": 0,
                "materialized": 0,
                "problems": ["no fault case targets this validator"],
            }
            continue
        planted, controls = _partition(cases)
        problems: list[str] = []
        for case in cases:
            case_id = case.get("id", "<no id>")
            op = case.get("planted_op")
            if not isinstance(op, str) or not op:
                problems.append(f"{case_id}: names no planted_op")
            elif op not in known_ops:
                problems.append(f"{case_id}: planted_op {op!r} resolves to no callable")
            if not _fixture_materialized(case):
                problems.append(f"{case_id}: fixture is not materialized")
        results[name] = {
            "planted": len(planted),
            "controls": len(controls),
            "materialized": sum(1 for case in cases if _fixture_materialized(case)),
            "problems": problems,
        }
    return results


_IN_FREECAD_SCORER = (
    "FREECAD_BUDDY_RUN_FAULT_SCORER=1 FreeCADCmd benchmarks/g2/fault-injection/score_g2_infc.py"
)


def main(argv: list[str] | None = None) -> int:
    """Check the G2 fault suite's structure and refuse to score it.

    Prints the per-validator case counts and any structural problem, then names the in-FreeCAD
    scorer that produces the actual rates. Returns 1 when any validator's suite is malformed.
    """
    argv = sys.argv[1:] if argv is None else argv
    results = check_suite()

    failed = False
    for name, result in results.items():
        sys.stderr.write(
            f"  {name:18s} planted={result['planted']:2d} controls={result['controls']:2d} "
            f"materialized={result['materialized']:2d}\n"
        )
        for problem in result["problems"]:
            sys.stderr.write(f"  {'':18s} {problem}\n")
        # A validator with no suite is a real gap in the benchmark, but it is not a malformed
        # case, so it is reported without failing the structural check.
        if [p for p in result["problems"] if not p.startswith("no fault case targets")]:
            failed = True

    sys.stderr.write(
        "\n  NOT SCORED HERE: planting a fault means running its planted_op through the "
        "production\n  mutation path, which needs a live FreeCAD document. This process has none, "
        "so no\n  sensitivity, false_alarm or wilson_ci is computed and validators.yaml is not "
        "written.\n"
        f"  Run the in-FreeCAD scorer for the real numbers:\n    {_IN_FREECAD_SCORER}\n"
    )

    if failed:
        sys.stderr.write("\n  SUITE MALFORMED: see the problems listed above\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
