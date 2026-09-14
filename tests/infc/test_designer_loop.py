"""In-FreeCAD tests for the designer loop against real geometry (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Where ``tests/external/test_designer_loop.py`` proves
the control flow against a scripted backend, these drive real plans through the production mutation
bracket and measure real shapes with ``benchmarks.harness.assertions.evaluate``. That is what makes
the four load-bearing claims falsifiable rather than asserted:

* convergence is declared by the geometry ∧ visual verdict, not by an iteration count;
* exhausting the cap is a FAILURE, reported as one;
* the document is rebound after a mutation that closes and reopens it (DW-71);
* a corrupted plan is detected by MEASURING the produced artifact, never by reading the plan —
  proven by driving the same corruption twice, once with the measurement and once with the plan
  text swapped out, and showing that only the measurement separates them.

Also pins the G3 fault suite's resolvability: every ``planted_op`` a case declares resolves to a
callable. That is the DW-73 gap, and the G2 history is that leaving it unpinned left a whole suite
unscoreable for months.
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
FAULT_DIR = REPO_ROOT / "benchmarks" / "g3" / "fault-injection"
if str(FAULT_DIR) not in sys.path:
    sys.path.insert(0, str(FAULT_DIR))

import planted_plans  # noqa: E402
import score_g3_infc as scorer  # noqa: E402

from benchmarks.harness import assertions  # noqa: E402
from freecad_buddy.contracts import (  # noqa: E402
    MAX_REPAIRS,
    VISUAL_CHECK_ID,
    VISUAL_UNAVAILABLE_CODE,
)
from freecad_buddy.usecases import confirm, designer_loop  # noqa: E402
from freecad_buddy.usecases.documents import DocumentRegistry  # noqa: E402

# The mounting-plate spec's own compiled assertions, read from the case file rather than restated:
# they were authored before any designer code existed (AD-19), and a copy here could drift from the
# contract the gate grades against.
PLATE_SPEC = "g3-dev-001-mounting-plate"

EXTRA_TOOLS = {"plan_shape": planted_plans.shape_step}


def passing_visual(_doc, geometry_passed):
    """A visual leg that passes whenever geometry did — the conjunction's second leg, satisfied.

    Used only where a test needs to reach the CONVERGED branch. It asserts nothing about a real
    judge: no test here claims a model passed a part, which is an operator measurement.
    """
    return {
        "id": VISUAL_CHECK_ID,
        "measured": [],
        "measured_kind": "text",
        "expected": True,
        "tolerance": None,
        "passed": bool(geometry_passed),
        "detail": None if geometry_passed else {"code": "visual.not_run", "message": "skipped"},
    }


def unavailable_visual(_doc, _geometry_passed):
    """The fail-closed visual leg: no vision backend, so the part is not done."""
    return {
        "id": VISUAL_CHECK_ID,
        "measured": None,
        "measured_kind": None,
        "expected": True,
        "tolerance": None,
        "passed": False,
        "detail": {
            "code": VISUAL_UNAVAILABLE_CODE,
            "message": "no vision backend in this process",
        },
    }


class _LoopTestCase(unittest.TestCase):
    """Shared setup: an auto-approve posture, a fresh document, and a guaranteed teardown."""

    def setUp(self):
        import FreeCAD as App

        self._App = App
        self._pre_open = set(App.listDocuments())
        self._previous_posture = confirm.set_auto_approve(True)
        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create(label=self.id().rsplit(".", 1)[-1])[
            "structured_content"
        ]["doc"]

    def tearDown(self):
        confirm.set_auto_approve(self._previous_posture)
        for name in set(self._App.listDocuments()) - self._pre_open:
            self._App.closeDocument(name)

    def drive(self, plan, checks, visual, **kwargs):
        """Run the loop over real geometry with the fault suite's shape builder available."""
        return designer_loop.run_designer_loop(
            self.registry,
            plan,
            checks,
            assertions.evaluate,
            visual,
            doc=self.handle,
            extra_tools=EXTRA_TOOLS,
            **kwargs,
        )

    def spec_checks(self, spec_ref=PLATE_SPEC):
        """The referenced dev spec's compiled checks and anchor frame."""
        return scorer._spec_assertions(spec_ref)


class ConvergenceByVerdictTest(_LoopTestCase):
    """Convergence is the geometry ∧ visual verdict, never the iteration count."""

    def test_a_faithful_plan_converges_on_the_verdict_with_no_repairs(self):
        checks, frame = self.spec_checks()
        record = self.drive(
            planted_plans.faithful_mounting_plate(),
            checks,
            passing_visual,
            run_id="infc-converge",
            anchor_frame=frame,
        )
        self.assertEqual(record["status"], "CONVERGED")
        self.assertTrue(record["converged"])
        self.assertEqual(record["repairs_used"], 0)
        last = record["iterations"][-1]
        self.assertTrue(last["geometry_pass"], msg=last["discrepancy"])
        self.assertTrue(last["visual_pass"])

    def test_a_correct_part_is_not_done_when_the_visual_leg_is_unavailable(self):
        """The conjunction's second leg blocks done even on a part whose geometry is right."""
        checks, frame = self.spec_checks()
        record = self.drive(
            planted_plans.faithful_mounting_plate(),
            checks,
            unavailable_visual,
            run_id="infc-visual-unavailable",
            anchor_frame=frame,
        )
        self.assertTrue(record["iterations"][0]["geometry_pass"])
        self.assertFalse(record["converged"])
        self.assertNotEqual(record["status"], "CONVERGED")
        self.assertEqual(record["iterations"][0]["visual_detail"]["code"], VISUAL_UNAVAILABLE_CODE)


class CapIsFailureTest(_LoopTestCase):
    """Hitting the repair cap is a failure, never a finish."""

    def test_a_part_that_never_satisfies_the_spec_reports_cap_exhausted(self):
        checks, frame = self.spec_checks()

        def repairer(plan, discrepancy, judge_findings):
            # A repairer that keeps proposing the same wrong plan, so the run reaches the cap.
            self.assertTrue(discrepancy, "the repairer must be handed the discrepancy vector")
            return plan

        record = self.drive(
            planted_plans.wrong_hole_diameter(),
            checks,
            passing_visual,
            repairer=repairer,
            run_id="infc-cap",
            anchor_frame=frame,
        )
        self.assertEqual(record["status"], "CAP_EXHAUSTED")
        self.assertFalse(record["converged"])
        self.assertEqual(record["repairs_used"], MAX_REPAIRS)
        self.assertIn("FAILURE, not a finish", record["detail"])

    def test_the_cap_is_the_declared_constant(self):
        """The cap is a gate criterion, not a tuning knob: G3.1 measures "within <=3"."""
        self.assertEqual(MAX_REPAIRS, 3)


class DocumentRebindTest(_LoopTestCase):
    """The loop holds the rebound document, never a closed handle (DW-71)."""

    def test_the_loop_holds_the_document_the_registry_holds_after_every_step(self):
        checks, frame = self.spec_checks()
        record = self.drive(
            planted_plans.faithful_mounting_plate(),
            checks,
            passing_visual,
            run_id="infc-rebind",
            anchor_frame=frame,
        )
        # The document the loop measured is the one the registry still resolves, and it is alive:
        # a closed handle raises on any attribute read.
        resolved = self.registry.with_document(self.handle, lambda _h, document: document)
        self.assertTrue(resolved.Objects)
        self.assertTrue(record["iterations"][0]["executed_steps"])

    def test_a_rolled_back_mutation_leaves_a_usable_document(self):
        """A step that fails post-verify rolls back; the loop must keep measuring, not crash.

        The plan asks for a builder that does not exist, so ``shape_step`` raises inside the
        bracket and the mutation takes its rollback path. What the loop must NOT do is carry on
        with a dead handle.
        """
        plan = planted_plans._plan(
            PLATE_SPEC,
            [{"tool": "plan_shape", "args": {"builder": "no_such_builder"}}],
            "a step that cannot be applied",
        )
        checks, frame = self.spec_checks()
        record = self.drive(
            plan, checks, unavailable_visual, run_id="infc-rollback", anchor_frame=frame
        )
        self.assertIsNotNone(record["iterations"][0]["step_failure"])
        self.assertFalse(record["converged"])
        resolved = self.registry.with_document(self.handle, lambda _h, document: document)
        self.assertIsNotNone(resolved.Name)


class CorruptedPlanDetectionTest(_LoopTestCase):
    """Detection comes from measuring the artifact, never from reading the plan."""

    def _violation_for(self, build_plan, spec_ref=PLATE_SPEC, preferred=None):
        checks, frame = self.spec_checks(spec_ref)
        record = self.drive(
            build_plan(),
            checks,
            unavailable_visual,
            run_id=f"infc-detect-{build_plan.__name__}",
            anchor_frame=frame,
        )
        return designer_loop.detect_spec_violation(
            record["iterations"][0]["checks"], preferred=preferred
        )

    def test_a_wrong_diameter_is_caught_by_the_diameter_measurement(self):
        violation = self._violation_for(
            planted_plans.wrong_hole_diameter, preferred="hole_diameter"
        )
        self.assertIsNotNone(violation)
        self.assertEqual(violation["check_id"], "assert.hole_diameter")
        # The measured value is the part's, not the plan's: a plan-reading detector could not
        # produce it.
        self.assertIsNotNone(violation["measured"])

    def test_a_faithful_plan_produces_no_violation(self):
        self.assertIsNone(self._violation_for(planted_plans.faithful_mounting_plate))

    def test_a_within_band_deviation_is_not_flagged(self):
        """The calibration control: 0.04 mm oversize is inside the 0.05 mm band."""
        self.assertIsNone(self._violation_for(planted_plans.tolerance_edge_hole))

    def test_detection_survives_a_plan_whose_text_says_nothing_about_the_corruption(self):
        """The load-bearing test: the same corruption, with every plan-text clue removed.

        The plan's ``rationale`` and every step's ``intent`` are stripped, so a detector reading
        the plan has nothing left to read. The violation must still be found, because it is found
        by measuring the part. A detector that inspected the plan would pass the fault suite while
        catching no real deviant part (AD-13).
        """
        plan = planted_plans.wrong_hole_diameter()
        plan["rationale"] = None
        plan["spec_text"] = ""
        for step in plan["steps"]:
            step.pop("intent", None)

        checks, frame = self.spec_checks()
        record = self.drive(
            plan, checks, unavailable_visual, run_id="infc-detect-blind", anchor_frame=frame
        )
        violation = designer_loop.detect_spec_violation(
            record["iterations"][0]["checks"], preferred="hole_diameter"
        )
        self.assertIsNotNone(violation, "the violation must be found by measuring the artifact")
        self.assertEqual(violation["check_id"], "assert.hole_diameter")

    def test_a_geometry_preserving_reorder_is_not_flagged(self):
        """The discriminating control: same reorder as pocket-before-pad, same geometry.

        A guard that flagged any reorder would fail here; only measuring the produced part
        separates this from its paired defect.
        """
        self.assertIsNone(
            self._violation_for(planted_plans.equivalent_step_order, "g3-dev-012-clamp-pad-slot")
        )

    def test_the_paired_ordering_defect_is_flagged(self):
        violation = self._violation_for(
            planted_plans.pocket_before_pad, "g3-dev-012-clamp-pad-slot"
        )
        self.assertIsNotNone(violation)


class PlantedPlanResolutionTest(unittest.TestCase):
    """Every ``planted_op`` a driveable G3 case declares resolves to a callable (DW-73)."""

    def setUp(self):
        self.cases = [
            case
            for suite_dir in scorer.DRIVEN_SUITES.values()
            for case in scorer.load_cases(suite_dir)
        ]

    def test_the_driven_suites_hold_the_expected_case_count(self):
        # 14 corrupted-plan + 7 assertions. The 8 visual-judge cases are not driven here.
        self.assertEqual(len(self.cases), 21)

    def test_every_planted_op_resolves_to_a_callable(self):
        unresolved = []
        for case in self.cases:
            try:
                op = planted_plans.resolve(case["planted_op"])
            except KeyError:
                unresolved.append((case["id"], case["planted_op"]))
                continue
            if not callable(op):
                unresolved.append((case["id"], case["planted_op"]))
        self.assertEqual(unresolved, [])

    def test_every_planted_op_returns_an_approved_plan_naming_a_resolvable_builder(self):
        problems = []
        for case in self.cases:
            plan = planted_plans.resolve(case["planted_op"])()
            if plan.get("approved") is not True:
                problems.append((case["id"], "plan is not approved"))
            for step in plan.get("steps") or []:
                builder = (step.get("args") or {}).get("builder")
                if builder is not None and builder not in planted_plans.BUILDERS:
                    problems.append((case["id"], f"unknown builder {builder!r}"))
        self.assertEqual(problems, [])

    def test_every_case_spec_ref_names_a_dev_case_with_checks(self):
        problems = []
        for case in self.cases:
            try:
                checks, _frame = scorer._spec_assertions(case["spec_ref"])
            except SystemExit as exc:
                problems.append((case["id"], str(exc)))
                continue
            if not checks:
                problems.append((case["id"], "no checks parsed"))
        self.assertEqual(problems, [])
