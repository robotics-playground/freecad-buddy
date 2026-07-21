"""FreeCAD-free test that the oracle-side export fault scorer clears the G0 bars.

Runs in the uv leg. Imports the committed scorer, scores the mesh verifiers over the committed
export-fault suite, and asserts sensitivity >=0.95, false_alarm <=0.05, every planted DETECT is
detected, and the clean control passes. The STEP verifier needs FreeCAD, so it is scored in the
FreeCADCmd leg and only the oracle-checkable verifiers are asserted here. This test does not
write validators.yaml (that persistence is the scorer's ``main`` entry).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCORER_DIR = REPO_ROOT / "benchmarks" / "g0" / "export-fault-injection"
sys.path.insert(0, str(SCORER_DIR))

import score_export_verify as scorer  # noqa: E402

ORACLE_VERIFIERS = ("verify_export_stl", "verify_export_3mf")


def _results() -> dict:
    return scorer.score()


def test_oracle_verifiers_are_scored():
    results = _results()
    for verifier in ORACLE_VERIFIERS:
        assert verifier in results, f"{verifier} not scored in the uv leg"


def test_each_oracle_verifier_meets_bars():
    results = _results()
    for verifier in ORACLE_VERIFIERS:
        result = results[verifier]
        assert result["sensitivity"] >= 0.95, (verifier, result["rows"])
        assert result["false_alarm"] <= 0.05, (verifier, result["rows"])


def test_every_planted_defect_detected_and_control_passes():
    results = _results()
    for verifier in ORACLE_VERIFIERS:
        rows = results[verifier]["rows"]
        assert not [r for r in rows if r[2] == "MISSED"], (verifier, rows)
        assert not [r for r in rows if r[2] == "FALSE_ALARM"], (verifier, rows)
        assert [r for r in rows if r[1] == "PASS_CLEAN"], verifier


def test_merge_preserves_verify_shape_block():
    text = (REPO_ROOT / "benchmarks" / "_registry" / "validators.yaml").read_text(encoding="utf-8")
    rendered = {"verify_export_stl": "verify_export_stl:\n  suite: x\n"}
    merged = scorer.merge_validators_yaml(text, rendered)
    assert "verify_shape:" in merged
    assert "suite: g0/fault-injection/" in merged
