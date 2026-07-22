"""In-FreeCADCmd evidence proof (stdlib unittest, discovered by tests/run_tests.py).

Runs ``collect_evidence_infc`` on the live bridge and asserts the G0.3 (golden ±0.1%) and
G0.5 (STEP round-trip: volume ±0.1% ∧ isValid ∧ equal topology counts) evidence reports
derive an ``OK`` verdict. Skip-guards when the golden fixtures are absent.
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
COLLECTOR_DIR = REPO_ROOT / "benchmarks" / "g0"
GOLDEN_DIR = COLLECTOR_DIR / "golden-models"
for _p in (str(SRC), str(REPO_ROOT), str(COLLECTOR_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@unittest.skipUnless(
    (GOLDEN_DIR / "expected.yaml").is_file() and any(GOLDEN_DIR.glob("*.FCStd")),
    "golden fixtures absent",
)
class G0EvidenceTest(unittest.TestCase):
    def test_g0_3_golden_report_ok(self):
        import collect_evidence_infc as collector

        report = collector.collect_g0_3()
        self.assertEqual(report["verdict"], "OK", report["checks"])
        self.assertTrue(all(c["passed"] for c in report["checks"]))

    def test_g0_5_step_roundtrip_report_ok(self):
        import collect_evidence_infc as collector

        report = collector.collect_g0_5()
        self.assertEqual(report["verdict"], "OK", report["checks"])
        self.assertTrue(all(c["passed"] for c in report["checks"]))


if __name__ == "__main__":
    unittest.main()
