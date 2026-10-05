"""In-FreeCAD test that the ``verify_export_step`` fault scorer clears the G0 bars (unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Imports the committed export scorer, runs its STEP leg
over the committed export-fault suite, and asserts sensitivity >=0.95, false_alarm <=0.05, no
missed defect or false alarm, and that the schema-lie case is detected. The mesh legs need the
third-party oracles and are asserted in ``tests/external/test_export_fault_score.py``. This test
does not write validators.yaml (that persistence is the scorer's ``main`` entry).
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCORER_DIR = REPO_ROOT / "benchmarks" / "g0" / "export-fault-injection"
sys.path.insert(0, str(SCORER_DIR))

import score_export_verify as scorer  # noqa: E402


class ExportStepFaultScoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = scorer.score()["verify_export_step"]

    def test_should_meet_sensitivity_and_false_alarm_bars_when_step_leg_scored(self):
        # Arrange
        result = self.result

        # Act
        sensitivity, false_alarm = result["sensitivity"], result["false_alarm"]

        # Assert
        self.assertGreaterEqual(sensitivity, 0.95, result["rows"])
        self.assertLessEqual(false_alarm, 0.05, result["rows"])

    def test_should_have_no_missed_defect_or_false_alarm_when_step_leg_scored(self):
        # Arrange
        rows = self.result["rows"]

        # Act
        wrong = [row for row in rows if row[2] in ("MISSED", "FALSE_ALARM")]

        # Assert
        self.assertEqual(wrong, [], rows)

    def test_should_detect_schema_lie_when_step_leg_scored(self):
        # Arrange
        rows = self.result["rows"]

        # Act
        outcomes = {row[0]: row[2] for row in rows}

        # Assert
        self.assertEqual(outcomes.get("g0-export-step-schema-lie"), "DETECTED", rows)


if __name__ == "__main__":
    unittest.main()
