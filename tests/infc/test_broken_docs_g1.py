"""In-FreeCAD broken-doc self-check (stdlib unittest, discovered by tests/run_tests.py).

Opens each committed G1 broken-doc ``fixture.FCStd``, recomputes, and asserts the case's named
``expected.object`` exists and is genuinely in error (``getStatusString()`` non-empty) — an
independent self-check that every committed fixture really breaks on its named object (G1.2
requires *the* failing object). Opens documents via raw ``App.openDocument`` (a raw open in a
test is acceptable here); every opened doc is closed.
"""

import sys
import unittest
from pathlib import Path

import FreeCAD as App
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BROKEN_DIR = REPO_ROOT / "benchmarks" / "g1" / "dev" / "broken-docs"

sys.path.insert(0, str(BROKEN_DIR))
import build_broken_docs as gen  # noqa: E402

EXPECTED_COUNT = 30


def _load_case(case_id: str) -> dict:
    return yaml.safe_load((BROKEN_DIR / case_id / "case.yaml").read_text(encoding="utf-8"))


class BrokenDocsG1Test(unittest.TestCase):
    def test_each_committed_fixture_is_broken_on_its_named_object(self):
        """Open, recompute, assert the named object is in error (non-empty status string)."""
        for case_id in gen.CASES:
            case = _load_case(case_id)
            expected_object = case["expected"]["object"]
            fcstd = BROKEN_DIR / case_id / "fixture.FCStd"
            self.assertTrue(fcstd.is_file(), f"missing committed fixture {fcstd}")
            doc = App.openDocument(str(fcstd))
            try:
                doc.recompute()
                obj = doc.getObject(expected_object)
                self.assertIsNotNone(
                    obj, f"{case_id}: expected object {expected_object!r} not in document"
                )
                status = obj.getStatusString()
                self.assertTrue(
                    status,
                    f"{case_id}: object {expected_object!r} is not in error "
                    f"(empty getStatusString())",
                )
            finally:
                App.closeDocument(doc.Name)

    def test_case_set_equality_and_count(self):
        case_dirs = {p.parent.name for p in BROKEN_DIR.rglob("case.yaml")}
        generator_ids = set(gen.CASES)
        committed = {p.parent.name for p in BROKEN_DIR.rglob("fixture.FCStd")}
        self.assertEqual(case_dirs, generator_ids, "case dirs vs generator CASES")
        self.assertEqual(committed, generator_ids, "committed fixtures vs generator CASES")
        self.assertEqual(len(generator_ids), EXPECTED_COUNT, "expected exactly 30 cases")


if __name__ == "__main__":
    unittest.main()
