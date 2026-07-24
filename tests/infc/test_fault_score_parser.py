"""In-FreeCAD tests for the ``verify_shape`` fault scorer flow-mapping parser (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. The scorer imports FreeCAD at module top, so this
test lives in the ``tests/infc/`` world; it exercises only the pure string helpers
``_parse_check`` and ``_iter_flow_mappings``.
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCORER_DIR = REPO_ROOT / "benchmarks" / "g0" / "fault-injection"
sys.path.insert(0, str(SCORER_DIR))

import score_verify_shape as scorer  # noqa: E402


class ParseCheckTest(unittest.TestCase):
    def test_single_line(self):
        body = "fn: expect_volume, expect: 6000, tol: {rel: 0.001}"
        self.assertEqual(
            scorer._parse_check(body),
            {"fn": "expect_volume", "expect": 6000, "tol": {"rel": 0.001}},
        )

    def test_list_expect(self):
        body = "fn: expect_bbox, expect: [10, 20, 30], tol: {rel: 0.001}"
        check = scorer._parse_check(body)
        self.assertEqual(check["expect"], [10, 20, 30])
        self.assertEqual(check["tol"], {"rel": 0.001})

    def test_abs_tol(self):
        body = "fn: expect_x, tol: {abs: 0.01}"
        self.assertEqual(scorer._parse_check(body)["tol"], {"abs": 0.01})

    def test_substring_not_corrupted(self):
        body = "fn: expect_relief, expect: 5"
        self.assertEqual(scorer._parse_check(body)["fn"], "expect_relief")

    def test_malformed_tol_raises(self):
        with self.assertRaises(ValueError):
            scorer._parse_check("fn: x, tol: 0.001")


class IterFlowMappingsTest(unittest.TestCase):
    def test_multi_line_mapping_parses_like_single_line(self):
        text = (
            "assertions:\n"
            "  checks:\n"
            "    - {fn: expect_volume,\n"
            "       expect: 6000,\n"
            "       tol: {rel: 0.001}}\n"
        )
        blocks = scorer._iter_flow_mappings(text)
        self.assertEqual(len(blocks), 1)
        single = "fn: expect_volume, expect: 6000, tol: {rel: 0.001}"
        self.assertEqual(scorer._parse_check(blocks[0]), scorer._parse_check(single))

    def test_nested_brace_yields_one_block(self):
        text = "assertions:\n  checks:\n    - {fn: x, meta: {a: {b: 1}}}\n"
        blocks = scorer._iter_flow_mappings(text)
        self.assertEqual(len(blocks), 1)
        self.assertIn("meta: {a: {b: 1}}", blocks[0])

    def test_real_fixture_parses_expected_checks(self):
        fixture = SCORER_DIR / "clean-control" / "case.yaml"
        text = fixture.read_text(encoding="utf-8")
        checks = [scorer._parse_check(flow) for flow in scorer._iter_flow_mappings(text)]
        self.assertEqual(
            checks,
            [
                {"fn": "expect_volume", "expect": 6000, "tol": {"rel": 0.001}},
                {"fn": "expect_bbox", "expect": [10, 20, 30], "tol": {"rel": 0.001}},
                {"fn": "expect_solid_count", "expect": 1},
            ],
        )

    def test_inline_comment_brace_is_not_a_phantom_check(self):
        text = "assertions:\n  checks:\n    - {fn: x, expect: 1}  # note {brace}\n"
        self.assertEqual(scorer._iter_flow_mappings(text), ["fn: x, expect: 1"])

    def test_no_checks_region_raises(self):
        with self.assertRaises(ValueError):
            scorer._iter_flow_mappings("id: foo\nexpectation: DETECT\n")

    def test_unterminated_mapping_raises(self):
        with self.assertRaises(ValueError):
            scorer._iter_flow_mappings("checks:\n  - {fn: x, expect: 1\n")


if __name__ == "__main__":
    unittest.main()
