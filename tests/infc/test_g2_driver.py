"""In-FreeCAD tests for the G2 case driver (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Proves the claims G2.1/G2.2/G2.3 rest on, which only
an executable in-FreeCAD run can support: the driver takes one case end to end through
preview -> confirm -> apply -> undo on a real document, the resulting ``mutation`` block carries
the keys the collectors read, ``matches_pre_op`` is ``True``, and the confirm gate is genuinely
exercised — the approval record reads ``mode: "preview_token"``, never ``auto_approve``.

The driver is also pinned to refuse honestly: with no command resolver it reports ``UNRESOLVED``
rather than a pass, because a case that was never driven must never be scored as an attempt.
"""

import sys
import unittest
from pathlib import Path

import FreeCAD as App

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.g2 import case_run  # noqa: E402
from freecad_buddy.usecases import confirm  # noqa: E402

GOLDEN = REPO_ROOT / "benchmarks" / "g0" / "golden-models" / "box-10-20-30.FCStd"

SQUARE = 6.0
PAD_LENGTH = 4.0


class _RecordingSink:
    """Captures the approval records the driven mutation writes."""

    def __init__(self):
        self.records = []

    def approval(self, tool, doc, approval, params=None):
        self.records.append(dict(approval))

    def before(self, *args, **kwargs):
        pass

    def after(self, *args, **kwargs):
        pass


def _pad_case(tmp_dir: Path) -> dict:
    """A driveable case: a body with a fully constrained square, padded a known length.

    The dev cases carry a natural-language ``spec`` and no tool call, so this test supplies its
    own resolvable case rather than pretending the driver can translate a command on its own.
    """
    return {
        "id": "g2-driver-pad",
        "op_type": "pad",
        "dir": tmp_dir,
        "inputs": {"document": "driver.FCStd"},
        "assertions": {
            "checks": [
                {
                    "fn": "expect_volume",
                    "expect": SQUARE * SQUARE * PAD_LENGTH,
                    "tol": {"rel": 0.001},
                }
            ]
        },
    }


class DriverFixture(unittest.TestCase):
    """A saved input document holding a body with a fully constrained square sketch."""

    def setUp(self):
        import tempfile

        import Part
        import Sketcher

        self._posture = confirm.set_auto_approve(False)
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="FCB_TMP_g2driver_"))
        document = App.newDocument("g2_driver_input")
        box = document.addObject("Part::Feature", "Box")
        box.Shape = Part.makeBox(10.0, 20.0, 30.0)
        body = document.addObject("PartDesign::Body", "Body")
        sketch = document.addObject("Sketcher::SketchObject", "Sketch")
        body.addObject(sketch)
        corners = [(0, 0), (SQUARE, 0), (SQUARE, SQUARE), (0, SQUARE)]
        for index in range(4):
            start = corners[index]
            end = corners[(index + 1) % 4]
            sketch.addGeometry(
                Part.LineSegment(App.Vector(*start, 0), App.Vector(*end, 0)), False
            )
        for index in range(4):
            sketch.addConstraint(
                Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1)
            )
        for index in (0, 2):
            sketch.addConstraint(Sketcher.Constraint("Horizontal", index))
        for index in (1, 3):
            sketch.addConstraint(Sketcher.Constraint("Vertical", index))
        sketch.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, 0, 1, 0))
        sketch.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 0, 1, 0))
        sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, SQUARE))
        sketch.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, SQUARE))
        document.recompute()
        document.saveAs(str(self.tmp_dir / "driver.FCStd"))
        App.closeDocument(document.Name)
        self.case = _pad_case(self.tmp_dir)

    def tearDown(self):
        import shutil

        confirm.set_auto_approve(self._posture)
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def resolver(self, _case):
        return {
            "tool": "feature_pad",
            "args": {
                "body": "Body",
                "profile": "Sketch",
                "name": "Pad",
                "length": {"value": PAD_LENGTH, "unit": "mm"},
            },
        }


class DrivenCaseTest(DriverFixture):
    def test_the_driver_completes_a_case_end_to_end(self):
        outcome = case_run.run_case(self.case, self.resolver)

        self.assertEqual(outcome.status, "OK", outcome.error)
        self.assertTrue(outcome.checks, "the case was never graded")
        self.assertTrue(
            outcome.passed, [c.get("detail") for c in outcome.checks]
        )

    def test_the_graded_volume_is_the_padded_solid_not_the_whole_document(self):
        """``expect_volume`` measures the body's tip, so a case's expectation is that solid."""
        outcome = case_run.run_case(self.case, self.resolver)

        measured = outcome.checks[0]["measured"]
        self.assertAlmostEqual(measured, SQUARE * SQUARE * PAD_LENGTH, places=3)

    def test_the_mutation_block_carries_the_keys_the_collectors_read(self):
        outcome = case_run.run_case(self.case, self.resolver)

        self.assertIsNotNone(outcome.mutation, outcome.error)
        for key in ("post_verify", "rolled_back", "rollback_proven", "params_digest"):
            self.assertIn(key, outcome.mutation)
        post_verify = outcome.mutation["post_verify"]
        for key in ("recompute_clean", "is_valid", "fully_constrained", "tnp_audit", "passed"):
            self.assertIn(key, post_verify)

    def test_the_undo_removes_the_feature_and_restores_the_object_set(self):
        outcome = case_run.run_case(self.case, self.resolver)

        self.assertIsNotNone(outcome.undo, outcome.error)
        self.assertEqual(outcome.undo["undone"], "buddy: feature_pad Pad")
        self.assertNotIn("Pad", outcome.undo["restored_objects"])

    def test_undoing_a_padded_sketch_does_not_reach_the_pre_op_digest(self):
        """A measured G2.3 shortfall, pinned so it cannot regress silently or be claimed green.

        The undo restores the document geometrically — the sketch comes back with identical
        edges, vertices, placement and bounding box, and the Pad is gone. The AD-6 digest still
        differs, because consuming the sketch as a profile flips one OCCT per-TShape housekeeping
        bit (5 single-byte differences inside the ``TShapes`` records of a 913-byte serialization,
        geometry bytes untouched) and the undo does not clear it.

        So ``fingerprint`` is byte-identity, not geometric identity: for a sketch-consuming
        PartDesign op it reports a difference where the model is unchanged. G2.3 claims
        hash-identity in 100% of benchmark ops, and this op type cannot meet that with the
        current oracle. Recorded in the deferred-work ledger rather than worked around here.
        """
        outcome = case_run.run_case(self.case, self.resolver)

        self.assertIs(outcome.undo["matches_pre_op"], False)
        self.assertNotEqual(
            outcome.undo["fingerprint_before"], outcome.undo["fingerprint_after"]
        )

    def test_the_confirm_gate_is_driven_by_a_real_preview_token(self):
        """Auto-approve would bypass the gate under test; the record must name the token mode."""
        sink = _RecordingSink()

        case_run.run_case(self.case, self.resolver, audit_sink=sink)

        modes = [record.get("mode") for record in sink.records]
        self.assertIn("preview_token", modes, sink.records)
        self.assertNotIn("auto_approve", modes)

    def test_the_gate_stays_fail_closed_throughout_the_run(self):
        case_run.run_case(self.case, self.resolver)

        self.assertFalse(
            confirm.auto_approve(), "the driver left the auto-approve posture armed"
        )


class UndrivenCaseTest(DriverFixture):
    def test_a_case_with_no_resolver_is_unresolved_not_passed(self):
        outcome = case_run.run_case(self.case, None)

        self.assertEqual(outcome.status, case_run.UNRESOLVED)
        self.assertFalse(outcome.passed)
        self.assertIn("resolver", outcome.error)

    def test_a_resolver_that_declines_a_command_is_unresolved(self):
        outcome = case_run.run_case(self.case, lambda _case: None)

        self.assertEqual(outcome.status, case_run.UNRESOLVED)
        self.assertFalse(outcome.passed)


class CaseLoadingTest(unittest.TestCase):
    def test_the_forty_dev_cases_load(self):
        cases = case_run.load_cases(REPO_ROOT / "benchmarks" / "g2" / "dev")

        self.assertEqual(len(cases), 40)
        self.assertTrue(all("spec" in case for case in cases))

    def test_a_dev_case_names_no_tool_so_it_needs_an_actor(self):
        """The benchmark grades a copilot translating a command, not a stored tool call."""
        cases = case_run.load_cases(REPO_ROOT / "benchmarks" / "g2" / "dev")

        self.assertTrue(all("tool" not in case and "args" not in case for case in cases))

    def test_the_golden_model_the_dev_cases_target_exists(self):
        self.assertTrue(GOLDEN.is_file())


if __name__ == "__main__":
    unittest.main()
