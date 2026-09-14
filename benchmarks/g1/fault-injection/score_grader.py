"""External-process fault scorer for the independent deterministic grader (run under uv).

For every ``case.yaml`` in this suite the scorer runs ``DeterministicGrader.grade`` over the
planted ``candidate_answer`` against the case's ``expected_findings`` and records the
DETECT / PASS_CLEAN outcome. A planted confident-wrong answer (``expectation: DETECT``) is
DETECTED when the grader verdict is FAIL (``pass_ == False`` — the grader correctly rejects the
wrong diagnosis); a clean-correct control (``expectation: PASS_CLEAN``) is a FALSE ALARM when
the grader FAILs it. Computes ``sensitivity``/``false_alarm`` + a Wilson CI, hashes the grader
source, the rubric and the fault suite into ``validator_sha``, and merge-writes ONLY the ``grader``
block of ``_registry/validators.yaml`` via the shared ``merge_validators_yaml`` (preserving every
``verify_*`` block). Prints a per-case table to stderr and exits non-zero when the bars are unmet.

Unlike the G0 scorers this runs under uv (text cases, no geometry) — so it imports the shared
``merge_validators_yaml`` and the FreeCAD-free ``stats`` module directly.
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
# The grader lives one level up; import it by path.
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
# The export scorer owns the shared read-merge-write for validators.yaml; import it by path so
# every scorer writes through one merge-writer and none full-clobbers another's blocks.
_EXPORT_SCORER_DIR = REPO_ROOT / "benchmarks" / "g0" / "export-fault-injection"
if str(_EXPORT_SCORER_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPORT_SCORER_DIR))

from freecad_buddy.usecases import stats  # noqa: E402
from grader import DeterministicGrader  # noqa: E402
from score_export_verify import merge_validators_yaml  # noqa: E402

VALIDATORS_YAML = REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml"
GRADER_SOURCE = HERE.parent / "grader.py"
RUBRIC = HERE.parent / "rubric.md"

SENSITIVITY_BAR = 0.95
FALSE_ALARM_BAR = 0.05
MIN_PLANTED = 10
MIN_CONTROLS = 1

_HEADER = (
    "# Per-validator fault-suite binding (validation-harness-design.md §6).\n"
    "# A score is citable only while validator_sha matches the working tree "
    "(edit the validator to stale it).\n"
)


def _load_case(case_yaml: Path) -> dict:
    data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SuiteError(f"{case_yaml}: case.yaml must be a mapping, got {type(data).__name__}")
    data["dir"] = case_yaml.parent
    return data


def _suite_case_files() -> list[Path]:
    """The suite's ``case.yaml`` files, ordered by their suite-relative POSIX path.

    The exact-name filter keeps the set platform-independent: ``rglob`` is case-insensitive on
    Windows, so a miscased ``Case.YAML`` would otherwise be scored and hashed there and not on
    Linux CI.
    """
    return sorted(
        (p for p in HERE.rglob("case.yaml") if p.name == "case.yaml"),
        key=lambda p: p.relative_to(HERE).as_posix(),
    )


def _validator_sha() -> str:
    """SHA-256 over the grader source, the rubric it encodes, AND the fault suite.

    The rubric is part of the validator: a rubric edit changes the pass rule the deterministic
    grader is meant to encode, so it must stale the sensitivity run (validation-harness §6/§8).
    The fault suite is part of it too: a score-preserving case edit changes what the committed
    sensitivity was measured over, so it must stale the run as well. Each case contributes its
    suite-relative POSIX path and its bytes, each length-prefixed so the concatenation is
    unambiguous — an added, removed, renamed, or edited case all change the digest, and no case
    can spell another case's path inside its own bytes to collide with a different suite.

    Raises ``SuiteError`` when the rubric is missing, the suite holds no cases, or a case cannot
    be read. An empty suite would otherwise digest to the source-only hash, which is a value the
    registry has already carried, so a deleted suite would read as current instead of stale.
    """
    if not RUBRIC.is_file():
        raise SuiteError(f"rubric not found: {RUBRIC} (the rubric is part of the validator)")
    cases = _suite_case_files()
    if not cases:
        raise SuiteError(f"no case.yaml found under {HERE} (the suite is part of the validator)")
    digest = hashlib.sha256()
    digest.update(GRADER_SOURCE.read_bytes())
    digest.update(RUBRIC.read_bytes())
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


class SuiteError(SystemExit):
    """A malformed / degenerate fault suite — exit non-zero with a clean message, never write."""


def _require(case: dict, key: str) -> object:
    if key not in case:
        raise SuiteError(f"case {case.get('id', '<no id>')!r}: missing '{key}'")
    return case[key]


def score() -> dict:
    """Grade every committed case; return the aggregate scoring result + per-case rows.

    Raises ``SuiteError`` (clean non-zero exit, no write) on a degenerate or malformed suite:
    a case missing a required key, a ``fault.kind``/``expectation`` mismatch (a mis-tagged case
    would be silently mis-partitioned), or fewer than ``MIN_PLANTED`` defects / ``MIN_CONTROLS``
    controls — because ``false_alarm`` is vacuously 0 with no controls and ``sensitivity`` is
    vacuously 1 for an all-reject grader, so the bars must never be evaluated over an empty arm.
    """
    grader = DeterministicGrader()
    if not RUBRIC.is_file():
        raise SuiteError(f"rubric not found: {RUBRIC} (the rubric is part of the validator)")
    rubric = RUBRIC.read_text(encoding="utf-8")
    cases = [_load_case(p) for p in _suite_case_files()]

    for case in cases:
        fault = _require(case, "fault")
        _require(case, "candidate_answer")
        expected = _require(case, "expected_findings")
        if not isinstance(fault, dict):
            raise SuiteError(f"case {case.get('id', '<no id>')!r}: 'fault' must be a mapping")
        if not isinstance(expected, dict):
            raise SuiteError(
                f"case {case.get('id', '<no id>')!r}: 'expected_findings' must be a mapping"
            )
        kind = fault.get("kind")
        expectation = fault.get("expectation")
        # kind and expectation must agree, or the case is silently mis-partitioned below.
        if (kind == "planted_defect") != (expectation == "DETECT") or (kind == "clean_control") != (
            expectation == "PASS_CLEAN"
        ):
            raise SuiteError(
                f"case {case.get('id', '<no id>')!r}: fault.kind {kind!r} disagrees with "
                f"expectation {expectation!r} (planted_defect<->DETECT, clean_control<->PASS_CLEAN)"
            )

    planted = [c for c in cases if c["fault"]["expectation"] == "DETECT"]
    controls = [c for c in cases if c["fault"]["expectation"] == "PASS_CLEAN"]
    if len(planted) < MIN_PLANTED or len(controls) < MIN_CONTROLS:
        raise SuiteError(
            f"degenerate suite: need >={MIN_PLANTED} planted + >={MIN_CONTROLS} controls, "
            f"have planted={len(planted)} controls={len(controls)} — the bars would be vacuous"
        )

    detected = 0
    flagged = 0
    rows = []
    for case in cases:
        try:
            verdict = grader.grade(
                case.get("question_ref", ""),
                case["candidate_answer"],
                rubric,
                case["expected_findings"],
            )
        except ValueError as exc:
            raise SuiteError(
                f"case {case.get('id', '<no id>')!r}: malformed expected — {exc}"
            ) from exc
        # The grader FAILing an answer (pass_ == False) is a "rejection". A planted-wrong answer
        # is DETECTED when rejected; a clean control is a FALSE ALARM when rejected.
        rejected = not verdict.pass_
        is_defect = case["fault"]["expectation"] == "DETECT"
        if is_defect and rejected:
            detected += 1
            outcome = "DETECTED"
        elif is_defect:
            outcome = "MISSED"
        elif rejected:
            flagged += 1
            outcome = "FALSE_ALARM"
        else:
            outcome = "PASS_CLEAN"
        rows.append((case["id"], case["fault"]["expectation"], verdict.pass_, outcome))

    return {
        "rows": rows,
        "planted": len(planted),
        "controls": len(controls),
        "detected": detected,
        "flagged": flagged,
        "sensitivity": stats.sensitivity(detected, len(planted)),
        "false_alarm": stats.false_alarm(flagged, len(controls)),
        "wilson_ci": stats.wilson_ci(detected, len(planted)),
    }


def _render_block(sha: str, run: dict) -> str:
    """Render the ``grader`` validators.yaml block (merged via ``merge_validators_yaml``)."""
    wilson = run["wilson_ci"]
    return (
        "grader:\n"
        "  suite: g1/fault-injection/\n"
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


def _committed_score_drift(run: dict) -> str | None:
    """Return why the committed ``grader`` block is stale vs the fresh run, or None if current.

    ``--check`` verifies the score already committed to ``validators.yaml`` — the committed
    ``validator_sha`` must equal the current ``sha256(grader.py + rubric.md + fault suite)`` and
    the committed ``sensitivity``/``false_alarm`` must equal the freshly computed values. A
    garbage or stale committed block is caught here in CI, not left to a later gate-verdict
    recompute.
    """
    if not VALIDATORS_YAML.exists():
        return f"{VALIDATORS_YAML} does not exist"
    data = yaml.safe_load(VALIDATORS_YAML.read_text(encoding="utf-8"))
    block = data.get("grader") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        return "no 'grader' block committed"
    if block.get("validator_sha") != _validator_sha():
        return "committed validator_sha != sha256(grader.py + rubric.md + fault suite case.yaml)"
    committed = block.get("last_run") or {}
    if committed.get("sensitivity") != run["sensitivity"]:
        return f"committed sensitivity {committed.get('sensitivity')} != {run['sensitivity']}"
    if committed.get("false_alarm") != run["false_alarm"]:
        return f"committed false_alarm {committed.get('false_alarm')} != {run['false_alarm']}"
    return None


def main(argv: list[str] | None = None) -> int:
    """Score the grader; write the ``grader`` block unless ``--check`` is passed.

    ``--check`` computes and asserts the bars WITHOUT writing ``validators.yaml`` — CI runs it so
    the committed score is verified against the current suite while the working tree stays clean
    (a drifting/garbage score is then caught by the bars, not by a silent overwrite).
    """
    argv = sys.argv[1:] if argv is None else argv
    check_only = "--check" in argv
    result = score()
    rows = result["rows"]
    sensitivity = result["sensitivity"]
    false_alarm = result["false_alarm"]
    wilson = result["wilson_ci"]

    for case_id, expectation, passed, outcome in rows:
        sys.stderr.write(f"  {case_id:34s} {expectation:11s} pass={str(passed):5s} {outcome}\n")
    sys.stderr.write(
        f"\n  planted={result['planted']} detected={result['detected']} "
        f"sensitivity={sensitivity:.3f}\n"
        f"  controls={result['controls']} flagged={result['flagged']} "
        f"false_alarm={false_alarm:.3f}\n"
        f"  wilson_ci=[{wilson['low']:.3f}, {wilson['high']:.3f}]\n"
    )

    today = datetime.date.today().isoformat()
    run = {
        "run_id": f"gr-{today}-1",
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
    if not check_only:
        existing = (
            VALIDATORS_YAML.read_text(encoding="utf-8") if VALIDATORS_YAML.exists() else _HEADER
        )
        merged = merge_validators_yaml(existing, {"grader": _render_block(_validator_sha(), run)})
        VALIDATORS_YAML.write_text(merged, encoding="utf-8")
        sys.stderr.write(f"  wrote {VALIDATORS_YAML}\n")
    else:
        drift = _committed_score_drift(run)
        if drift:
            sys.stderr.write(f"  COMMITTED SCORE STALE: {drift}\n")
            return 1
        sys.stderr.write("  --check: committed score matches; validators.yaml not written\n")

    if sensitivity < SENSITIVITY_BAR or false_alarm > FALSE_ALARM_BAR:
        sys.stderr.write("  BARS NOT MET: sensitivity<0.95 or false_alarm>0.05\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
