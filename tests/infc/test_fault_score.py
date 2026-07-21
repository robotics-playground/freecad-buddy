"""In-FreeCAD test that the ``verify_shape`` fault scorer clears the G0 bars (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Imports the committed scorer, runs it over the
committed fault suite, and asserts sensitivity >=0.95, false_alarm <=0.05, every planted
DETECT case is detected, and the clean control passes. This test does not write
validators.yaml (that persistence is the scorer's ``main`` entry, exercised separately).
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCORER_DIR = REPO_ROOT / "benchmarks" / "g0" / "fault-injection"
sys.path.insert(0, str(SCORER_DIR))

import score_verify_shape as scorer  # noqa: E402


class FaultScoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = scorer.score()

    def test_meets_sensitivity_and_false_alarm_bars(self):
        self.assertGreaterEqual(self.result["sensitivity"], 0.95, self.result["rows"])
        self.assertLessEqual(self.result["false_alarm"], 0.05, self.result["rows"])

    def test_every_planted_defect_is_detected(self):
        missed = [row for row in self.result["rows"] if row[3] == "MISSED"]
        self.assertEqual(missed, [], f"planted defects missed: {missed}")

    def test_clean_control_passes(self):
        false_alarms = [row for row in self.result["rows"] if row[3] == "FALSE_ALARM"]
        self.assertEqual(false_alarms, [], f"clean controls flagged: {false_alarms}")
        controls = [row for row in self.result["rows"] if row[1] == "PASS_CLEAN"]
        self.assertGreaterEqual(len(controls), 1)


if __name__ == "__main__":
    unittest.main()
