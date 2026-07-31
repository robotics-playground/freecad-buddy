"""External-process fault scorer for the five validators the G2 criteria cite (run under uv).

Scores ``assertions``, ``run_mutation``, ``fingerprint``, ``audit_references`` and
``verify_sketch`` against the fault suites that target them, computing sensitivity / false alarm
with ``usecases/stats.py`` and merge-writing each block into ``_registry/validators.yaml`` with
its ``validator_sha``. Each suite is routed to its validator by the ``targets_validator`` key its
cases declare, so a case moved between suites follows its validator rather than a hardcoded map.

Every case's defect is planted by running its ``planted_op`` through the production mutation path,
which needs a live FreeCAD document and a driving actor. This scorer runs outside FreeCAD, so it
scores what it can measure without one and reports the rest as uncollected — a validator that
could not be exercised is written with a zero sensitivity and fails its bar honestly rather than
being credited with a score no run produced.

Exits non-zero when any scored validator misses sensitivity >=0.95 / false_alarm <=0.05, or when
any cited validator could not be scored at all.
"""

from __future__ import annotations

import datetime
import hashlib
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
_EXPORT_SCORER_DIR = REPO_ROOT / "benchmarks" / "g0" / "export-fault-injection"
if str(_EXPORT_SCORER_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPORT_SCORER_DIR))

from freecad_buddy.usecases import stats  # noqa: E402
from score_export_verify import merge_validators_yaml  # noqa: E402

VALIDATORS_YAML = REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml"

SENSITIVITY_BAR = 0.95
FALSE_ALARM_BAR = 0.05

# The source files whose bytes make up each validator's ``validator_sha``. A score stales the
# moment any of them changes, so a citation can never outlive the code it was measured over.
_USECASES = SRC / "freecad_buddy" / "usecases"
VALIDATOR_SOURCES = {
    "assertions": (REPO_ROOT / "benchmarks" / "harness" / "assertions.py",),
    "run_mutation": (_USECASES / "transaction.py",),
    "fingerprint": (_USECASES / "fingerprint.py",),
    "audit_references": (_USECASES / "tnp_guard.py",),
    "verify_sketch": (_USECASES / "verify.py",),
}

_HEADER = (
    "# Per-validator fault-suite binding (validation-harness-design.md §6).\n"
    "# A score is citable only while validator_sha matches the working tree "
    "(edit the validator to stale it).\n"
)


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
        if (kind == "planted_defect") != (expectation == "DETECT") or (
            kind == "clean_control"
        ) != (expectation == "PASS_CLEAN"):
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


def score() -> dict[str, dict]:
    """Score every cited validator over the cases that target it.

    Returns ``{validator: result}``. Each result carries the planted/control counts, how many
    cases are materialized, the detected/flagged tallies and the resulting rates. Detection
    requires driving each case's ``planted_op`` through the live mutation path, which this
    out-of-FreeCAD process cannot do, so ``detected`` stays 0 and the validator fails its bar
    rather than being credited with an unmeasured score.
    """
    by_validator: dict[str, list[dict]] = {}
    for case_yaml in _suite_case_files():
        case = _load_case(case_yaml)
        by_validator.setdefault(_validator_name(case), []).append(case)

    results: dict[str, dict] = {}
    for name in sorted(VALIDATOR_SOURCES):
        cases = by_validator.get(name, [])
        if not cases:
            results[name] = {
                "planted": 0,
                "controls": 0,
                "materialized": 0,
                "detected": 0,
                "flagged": 0,
                "sensitivity": 0.0,
                "false_alarm": 0.0,
                "wilson_ci": stats.wilson_ci(0, 0),
                "reason": "no fault case targets this validator",
            }
            continue
        planted, controls = _partition(cases)
        materialized = sum(1 for case in cases if _fixture_materialized(case))
        detected = 0
        flagged = 0
        results[name] = {
            "planted": len(planted),
            "controls": len(controls),
            "materialized": materialized,
            "detected": detected,
            "flagged": flagged,
            "sensitivity": stats.sensitivity(detected, len(planted)),
            "false_alarm": stats.false_alarm(flagged, len(controls)),
            "wilson_ci": stats.wilson_ci(detected, len(planted)),
            "reason": (
                "planted_op requires a live in-FreeCAD mutation run; not driven by this "
                "out-of-FreeCAD scorer"
            ),
        }
    return results


def _render_block(name: str, sha: str, run: dict, suite: str) -> str:
    """Render one validator's ``validators.yaml`` block for the shared merge-writer.

    A validator whose score was not measured carries ``not_scored`` naming why. Without it the
    block is indistinguishable from a real measurement: a zero sensitivity beside a date, a run id
    and a Wilson interval reads as "measured and scored zero", and an ``n: 0`` interval spanning
    ``[0, 1]`` reads as evidence rather than as its absence.
    """
    wilson = run["wilson_ci"]
    block = (
        f"{name}:\n"
        f"  suite: {suite}\n"
        f'  validator_sha: "{sha}"\n'
        "  last_run:\n"
        f"    run_id: {run['run_id']}\n"
        f"    sensitivity: {run['sensitivity']}\n"
        f"    false_alarm: {run['false_alarm']}\n"
        f"    date: {run['date']}\n"
    )
    if run.get("not_scored"):
        block += f"    not_scored: {run['not_scored']}\n"
    return block + (
        "    wilson_ci:\n"
        f"      rate: {wilson['rate']}\n"
        f"      low: {wilson['low']}\n"
        f"      high: {wilson['high']}\n"
        f"      n: {wilson['n']}\n"
        f"      r: {wilson['r']}\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Score the five G2 validators; write their blocks unless ``--check`` is passed.

    ``--check`` computes and asserts the bars WITHOUT writing ``validators.yaml``, so CI verifies
    the committed scores against the current suites while the working tree stays clean.
    """
    argv = sys.argv[1:] if argv is None else argv
    check_only = "--check" in argv
    results = score()

    today = datetime.date.today().isoformat()
    rendered: dict[str, str] = {}
    failed = False
    for name, result in results.items():
        sys.stderr.write(
            f"  {name:18s} planted={result['planted']:2d} controls={result['controls']:2d} "
            f"materialized={result['materialized']:2d} detected={result['detected']:2d} "
            f"sensitivity={result['sensitivity']:.3f} false_alarm={result['false_alarm']:.3f}\n"
        )
        if result.get("reason"):
            sys.stderr.write(f"  {'':18s} NOT SCORED: {result['reason']}\n")
        wilson = result["wilson_ci"]
        run = {
            "run_id": f"g2-{today}-1",
            "sensitivity": round(result["sensitivity"], 4),
            "false_alarm": round(result["false_alarm"], 4),
            "date": today,
            "not_scored": result.get("reason") or "",
            "wilson_ci": {
                "rate": round(wilson["rate"], 4),
                "low": round(wilson["low"], 4),
                "high": round(wilson["high"], 4),
                "n": wilson["n"],
                "r": wilson["r"],
            },
        }
        rendered[name] = _render_block(name, _validator_sha(name), run, "g2/fault-injection/")
        if result["sensitivity"] < SENSITIVITY_BAR or result["false_alarm"] > FALSE_ALARM_BAR:
            failed = True

    if not check_only:
        existing = (
            VALIDATORS_YAML.read_text(encoding="utf-8") if VALIDATORS_YAML.exists() else _HEADER
        )
        VALIDATORS_YAML.write_text(
            merge_validators_yaml(existing, rendered), encoding="utf-8"
        )
        sys.stderr.write(f"  wrote {VALIDATORS_YAML}\n")
    else:
        sys.stderr.write("  --check: validators.yaml not written\n")

    if failed:
        sys.stderr.write("  BARS NOT MET: sensitivity<0.95 or false_alarm>0.05\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
