"""Fault scorer for ``verify_render_tone`` (AD-34).

Run in the external uv environment -- the oracle decodes PNGs with stdlib only, so no FreeCAD
and no GUI stack is needed::

    uv run python benchmarks/g0/render-fault-injection/score_render_tone.py

For every ``case.yaml`` in this suite the scorer runs ``verify_render_tone`` over the committed
``render.png`` and records the DETECT / PASS_CLEAN outcome. A planted case is detected when the
verdict fails; a clean control is a false alarm when it fails. Computes sensitivity / false-alarm
plus a Wilson CI, hashes the validator source into ``validator_sha``, and merges ONLY the
``verify_render_tone`` block into ``_registry/validators.yaml`` through the shared
read-merge-write, so no other validator's block is clobbered.
"""

from __future__ import annotations

import hashlib
import os
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# The export scorer owns the shared read-merge-write for validators.yaml; import it by path so
# every scorer writes through one merge-writer.
_EXPORT_SCORER_DIR = REPO_ROOT / "benchmarks" / "g0" / "export-fault-injection"
if str(_EXPORT_SCORER_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPORT_SCORER_DIR))

from freecad_buddy.usecases import stats  # noqa: E402
from freecad_buddy.usecases.render_tone import verify_render_tone  # noqa: E402
from score_export_verify import merge_validators_yaml  # noqa: E402

VALIDATORS_YAML = REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml"
VALIDATOR_SOURCES = (SRC / "freecad_buddy" / "usecases" / "render_tone.py",)

SENSITIVITY_BAR = 0.95
FALSE_ALARM_BAR = 0.05
MIN_PLANTED = 5
MIN_CONTROLS = 1

VALIDATOR = "verify_render_tone"


class SuiteError(SystemExit):
    """A malformed / degenerate fault suite — exit non-zero with a clean message, never write."""


def _load_case(case_yaml: Path) -> dict:
    """Parse the fixed render ``case.yaml`` shape (id, validator, expectation, render file)."""
    case: dict = {"dir": case_yaml.parent}
    for raw in case_yaml.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or raw[0] in " \t":
            continue
        key, _, value = raw.strip().partition(":")
        key, value = key.strip(), value.strip().strip("'\"")
        if key == "id":
            case["id"] = value
        elif key == "targets_validator":
            case["validator"] = value
        elif key == "expectation":
            case["expectation"] = value
        elif key == "render_file":
            case["render_file"] = value
    return case


def _score_case(case: dict) -> bool:
    """Return whether the oracle flags ``case`` (a failing tone verdict)."""
    return not verify_render_tone(str(case["dir"] / case["render_file"]))["passed"]


def _validator_sha() -> str:
    """SHA-256 over the concatenated validator source files."""
    hasher = hashlib.sha256()
    for path in VALIDATOR_SOURCES:
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def score() -> dict:
    """Run the oracle over the committed suite; return the aggregate result plus per-case rows.

    Raises ``SuiteError`` on a degenerate partition: ``false_alarm`` is vacuously 0 with no
    controls and ``sensitivity`` vacuously 1 over a thin planted arm, so the bars must never be
    evaluated over one.
    """
    cases = [_load_case(p) for p in sorted(HERE.rglob("case.yaml"))]
    cases = [c for c in cases if c.get("validator") == VALIDATOR]

    planted = [c for c in cases if c["expectation"] == "DETECT"]
    controls = [c for c in cases if c["expectation"] == "PASS_CLEAN"]
    if len(planted) < MIN_PLANTED or len(controls) < MIN_CONTROLS:
        raise SuiteError(
            f"degenerate suite for {VALIDATOR}: need >={MIN_PLANTED} planted + "
            f">={MIN_CONTROLS} controls, have planted={len(planted)} "
            f"controls={len(controls)} — the bars would be vacuous"
        )

    detected = 0
    flagged = 0
    rows = []
    for case in cases:
        failed = _score_case(case)
        is_defect = case["expectation"] == "DETECT"
        if is_defect and failed:
            detected += 1
            outcome = "DETECTED"
        elif is_defect:
            outcome = "MISSED"
        elif failed:
            flagged += 1
            outcome = "FALSE_ALARM"
        else:
            outcome = "PASS_CLEAN"
        rows.append((case["id"], case["expectation"], outcome))

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
    """Render the ``verify_render_tone`` validators.yaml block."""
    wilson = run["wilson_ci"]
    return (
        f"{VALIDATOR}:\n"
        "  suite: g0/render-fault-injection/\n"
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


def main() -> int:
    result = score()
    sensitivity = result["sensitivity"]
    false_alarm = result["false_alarm"]
    wilson = result["wilson_ci"]

    for case_id, expectation, outcome in result["rows"]:
        sys.stderr.write(f"  {case_id:36s} {expectation:11s} {outcome}\n")
    sys.stderr.write(
        f"\n  planted={result['planted']} detected={result['detected']} "
        f"sensitivity={sensitivity:.3f}\n"
        f"  controls={result['controls']} flagged={result['flagged']} "
        f"false_alarm={false_alarm:.3f}\n"
        f"  wilson_ci=[{wilson['low']:.3f}, {wilson['high']:.3f}]\n"
    )

    today = date.today().isoformat()
    run = {
        "run_id": f"rt-{today}-1",
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
    merged = merge_validators_yaml(
        VALIDATORS_YAML.read_text(encoding="utf-8"),
        {VALIDATOR: _render_block(_validator_sha(), run)},
    )
    VALIDATORS_YAML.write_text(merged, encoding="utf-8")
    sys.stderr.write(f"  wrote {VALIDATORS_YAML}\n")

    if sensitivity < SENSITIVITY_BAR or false_alarm > FALSE_ALARM_BAR:
        sys.stderr.write("  BARS NOT MET: sensitivity<0.95 or false_alarm>0.05\n")
        return 1
    return 0


_RUN_FLAG = "FREECAD_BUDDY_RUN_RENDER_SCORER"


def _run_requested_in(env: Mapping[str, str]) -> bool:
    """Whether ``env`` carries the explicit scoring-run opt-in."""
    return env.get(_RUN_FLAG) == "1"


def _run_requested() -> bool:
    """Whether an explicit opt-in asked for a scoring run (import never scores)."""
    return __name__ == "__main__" or _run_requested_in(os.environ)


if _run_requested():
    sys.exit(main())
