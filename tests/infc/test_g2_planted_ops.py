"""In-FreeCAD tests for the G2 planted-op registry and scorer (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Pins the two properties that make the G2 fault suite
scorable at all: every ``planted_op`` a case names resolves to a callable, and a planted defect is
actually detected while its paired clean control is not.

The detection tests drive the ops through the same production mutation bracket the scorer uses, so
a regression in ``run_mutation``, ``tnp_guard``, the assertion grader or ``verify_sketch`` surfaces
here rather than only in a benchmark run.
"""

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
FAULT_DIR = REPO_ROOT / "benchmarks" / "g2" / "fault-injection"
for _path in (FAULT_DIR, FAULT_DIR / "sketch"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import planted_ops  # noqa: E402
import planted_sketches  # noqa: E402
import score_g2_infc as scorer  # noqa: E402

# The suite spans two op registries: planted_ops for the geometry/reference/rollback families and
# planted_sketches for the verify_sketch family. The scorer resolves a name against both, so the
# tests that police resolution have to search the same union.
OP_MODULES = (planted_ops, planted_sketches)


def _registered(name):
    """The callable ``name`` denotes in any suite registry, or ``None``."""
    for module in OP_MODULES:
        if name in module.REGISTRY:
            return module.REGISTRY[name]
    return None


class PlantedOpResolutionTest(unittest.TestCase):
    """Every ``planted_op`` a case declares must resolve; the ledger's DW-73 gap."""

    def setUp(self):
        self.cases = scorer.load_cases()

    def test_the_suite_holds_the_expected_case_count(self):
        self.assertEqual(len(self.cases), 48)

    def test_every_planted_op_resolves_to_a_callable(self):
        unresolved = [
            (case["id"], case["planted_op"])
            for case in self.cases
            if not callable(_registered(case["planted_op"]))
        ]
        self.assertEqual(unresolved, [], f"planted_op names resolving to nothing: {unresolved}")

    def test_every_case_yaml_planted_op_is_in_a_registry(self):
        """Read the declarations from the YAML directly, not through the loader's parsing."""
        declared = set()
        for path in FAULT_DIR.rglob("case.yaml"):
            if path.name != "case.yaml":
                continue
            match = re.search(r"^planted_op:\s*(\S+)", path.read_text(encoding="utf-8"), re.M)
            self.assertIsNotNone(match, f"{path} declares no planted_op")
            declared.add(match.group(1))
        registered = set().union(*(set(module.REGISTRY) for module in OP_MODULES))
        self.assertEqual(declared - registered, set())

    def test_the_registry_declares_no_op_no_case_names(self):
        """A registry entry nothing names is dead weight that no run would ever exercise."""
        named = {case["planted_op"] for case in self.cases}
        registered = set().union(*(set(module.REGISTRY) for module in OP_MODULES))
        self.assertEqual(registered - named, set())

    def test_every_undriveable_op_is_a_real_registry_entry_with_a_reason(self):
        for name, reason in planted_ops.UNDRIVEABLE.items():
            self.assertIn(name, planted_ops.REGISTRY, name)
            self.assertGreater(len(reason), 40, f"{name}: the reason must say what was measured")

    def test_every_undriveable_sketch_signal_carries_its_measurement(self):
        """The sketch suite's undriveable entries name a SIGNAL, not an op.

        ``MalformedConstraints`` and ``PartiallyRedundantConstraints`` are never populated by any
        route reachable on FreeCAD 1.1.0, so there is no callable to register — the entry exists to
        record what was measured instead of letting the gap pass unstated. Each must therefore name
        the build it was measured on, and must not collide with a registered op name.
        """
        for name, reason in planted_sketches.UNDRIVEABLE.items():
            self.assertNotIn(name, planted_sketches.REGISTRY, f"{name} names a driveable op")
            self.assertIn("FreeCAD 1.1.0", reason, f"{name}: name the build measured")
            self.assertGreater(len(reason), 40, f"{name}: the reason must say what was measured")

    def test_every_assertions_case_declares_its_commanded_parameters(self):
        """A case graded by assertions with no CHECKS entry would silently read as a pass."""
        missing = [
            case["id"]
            for case in self.cases
            if case["validator"] == "assertions" and not planted_ops.CHECKS.get(case["id"])
        ]
        self.assertEqual(missing, [])


class _CaseDrivingTest(unittest.TestCase):
    """Drives one named case through the scorer's own path."""

    def setUp(self):
        import FreeCAD as App

        self._app = App
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def tearDown(self):
        for name in list(self._app.listDocuments().keys()):
            self._app.closeDocument(name)

    def drive(self, case_id):
        case = next(c for c in scorer.load_cases() if c["id"] == case_id)
        return scorer._run_case(case)


class PlantedDefectDetectionTest(_CaseDrivingTest):
    """A planted defect is detected; its paired clean control is not.

    Each pair shares a fixture and an operation and differs only in the parameter or the reference
    the op writes, so a test passing on both sides means the grader separated them on the fault
    rather than on anything else about the document.
    """

    def test_a_pocket_at_the_wrong_depth_is_detected(self):
        detected, verdict = self.drive("g2-fault-wrong-param-pocket-depth")
        self.assertTrue(detected, verdict)

    def test_a_pocket_at_the_commanded_depth_is_not_flagged(self):
        detected, verdict = self.drive("g2-fault-wrong-param-correct-pocket")
        self.assertFalse(detected, verdict)

    def test_a_hole_at_the_wrong_diameter_is_detected(self):
        detected, verdict = self.drive("g2-fault-wrong-param-hole-diameter")
        self.assertTrue(detected, verdict)

    def test_a_hole_inside_the_declared_tolerance_is_not_flagged(self):
        """The same measurement as the wrong-diameter case, 0.5 micron off instead of 0.2 mm."""
        detected, verdict = self.drive("g2-fault-wrong-param-within-tolerance")
        self.assertFalse(detected, verdict)

    def test_a_pattern_with_the_wrong_count_is_detected(self):
        detected, verdict = self.drive("g2-fault-wrong-param-pattern-count")
        self.assertTrue(detected, verdict)

    def test_a_pattern_with_the_wrong_spacing_is_detected(self):
        """The count is right and only the pitch is wrong, so counting alone cannot catch it."""
        detected, verdict = self.drive("g2-fault-wrong-param-pattern-spacing")
        self.assertTrue(detected, verdict)

    def test_a_pattern_at_the_commanded_count_and_pitch_is_not_flagged(self):
        detected, verdict = self.drive("g2-fault-wrong-param-correct-pattern")
        self.assertFalse(detected, verdict)

    def test_a_reference_repointed_to_a_congruent_twin_is_detected(self):
        """The twin's witness coincides, so only the ancestry cross-check separates them."""
        detected, verdict = self.drive("g2-fault-coincidental-witness-match")
        self.assertTrue(detected, verdict)

    def test_a_reference_left_on_its_original_element_is_not_flagged(self):
        detected, verdict = self.drive("g2-fault-coincidental-genuine-match")
        self.assertFalse(detected, verdict)

    def test_a_deleted_attachment_support_is_detected(self):
        detected, verdict = self.drive("g2-fault-tnp-b-attachment-support-deleted")
        self.assertTrue(detected, verdict)

    def test_a_dressup_edge_removed_as_intended_is_not_flagged(self):
        """The same shape of change as a silent drop; the op wrote it, so it is the target."""
        detected, verdict = self.drive("g2-fault-dressup-intended-edge-removal")
        self.assertFalse(detected, verdict)

    def test_a_succeeding_op_commits_without_a_rollback(self):
        detected, verdict = self.drive("g2-fault-rollback-successful-op-no-rollback")
        self.assertFalse(detected, verdict)

    def test_a_failing_op_aborts_and_proves_the_restoration(self):
        """The bracket must roll back AND prove it by re-hashing, not merely abort."""
        detected, verdict = self.drive("g2-fault-rollback-failing-op-abort-clean")
        self.assertFalse(detected, verdict)
        self.assertIn("rolled_back_verified", verdict)


class SketchDefectDetectionTest(_CaseDrivingTest):
    """``verify_sketch`` grades the policy of verification-design.md §4.2, not one property.

    Each test names the property signal it turns on, and the pairs are chosen so that an
    implementation reading a single property passes one side and fails the other.
    """

    def test_an_unconstrained_line_is_detected(self):
        """The plainest under-constraint: dof rises to 4 and FullyConstrained goes False."""
        detected, verdict = self.drive("g2-fault-sketch-under-unconstrained-line")
        self.assertTrue(detected, verdict)

    def test_a_missing_radius_dimension_is_detected(self):
        """One degree of freedom on a sketch whose every element is still placed."""
        detected, verdict = self.drive("g2-fault-sketch-under-missing-radius")
        self.assertTrue(detected, verdict)

    def test_a_contradicting_dimension_is_detected_although_it_reports_fully_constrained(self):
        """The case the PASS signal alone misses: FullyConstrained is True while dof is -1."""
        detected, verdict = self.drive("g2-fault-sketch-over-contradicting-width")
        self.assertTrue(detected, verdict)
        self.assertIn("fc=True", verdict)
        self.assertIn("dof=-1", verdict)

    def test_a_bad_index_constraint_is_detected(self):
        detected, verdict = self.drive("g2-fault-sketch-badindex-second-slot")
        self.assertTrue(detected, verdict)

    def test_a_zero_length_segment_is_detected_although_every_constraint_signal_reads_clean(self):
        """dof is 0, FullyConstrained is True, nothing conflicts: only degeneracy separates it."""
        detected, verdict = self.drive("g2-fault-sketch-degenerate-zero-length-segment")
        self.assertTrue(detected, verdict)
        self.assertIn("dof=0", verdict)
        self.assertIn("fc=True", verdict)

    def test_a_short_segment_above_the_tolerance_is_not_flagged(self):
        """The discriminating pair for the zero-length case: 1 um instead of 1 nm, nothing else."""
        detected, verdict = self.drive("g2-fault-sketch-control-short-segment-above-tolerance")
        self.assertFalse(detected, verdict)

    def test_a_redundant_duplicate_dimension_is_not_flagged(self):
        """§4.2 makes redundancy WARN-never-fail, and FreeCAD marks such a sketch isValid False."""
        detected, verdict = self.drive("g2-fault-sketch-control-redundant-duplicate-dimension")
        self.assertFalse(detected, verdict)
        self.assertIn("red=1", verdict)

    def test_a_fully_constrained_sketch_passes_cleanly(self):
        detected, verdict = self.drive("g2-fault-sketch-control-resize-width")
        self.assertFalse(detected, verdict)


class SketchGradingReadsTheValidatorTest(_CaseDrivingTest):
    """Detection is ``verify_sketch``'s own verdict, taken where the fault still exists.

    Two measured properties of FreeCAD 1.1.0 make the placement of that reading load-bearing, and
    both would silently corrupt the score rather than fail loudly.
    """

    def _case(self, case_id):
        return next(c for c in scorer.load_cases() if c["id"] == case_id)

    def test_a_conflicting_sketch_is_graded_by_verify_sketch_not_by_the_recompute_sweep(self):
        """``post_verify`` short-circuits at ``_invalid_objects`` before the sketch loop here.

        The bracket reports ``fully_constrained: not_measured`` for this fault, so a scorer reading
        the mutation status would credit ``verify_sketch`` with a catch the recompute sweep made.
        The sketch branch must produce its own non-OK verdict instead.
        """
        import FreeCAD as App

        from freecad_buddy.usecases import transaction
        from freecad_buddy.usecases.documents import DocumentRegistry

        case = self._case("g2-fault-sketch-over-contradicting-width")
        captured = {}
        op = scorer._grade_sketch_inside_bracket(
            planted_sketches.resolve(case["planted_op"]), captured
        )
        registry = DocumentRegistry()
        handle = registry.document_open(str(case["dir"] / "fixture.FCStd"))
        handle = handle["structured_content"]["doc"]
        document = registry.with_document(handle, lambda _h, d: d)
        document, envelope = transaction.run_mutation(document, handle, case["planted_op"], op)
        registry.rebind(handle, document)

        block = (envelope.get("structured_content") or {}).get("mutation") or {}
        post_verify = block.get("post_verify") or {}
        self.assertEqual(post_verify.get("fully_constrained"), "not_measured")
        self.assertNotEqual(captured.get("status"), "OK", captured)
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def test_reading_after_the_bracket_returns_would_measure_the_restored_sketch(self):
        """A failing post_verify rolls back, and the restored sketch is clean.

        Pins why the reading is taken inside the bracket: the very same planted defect reads as a
        perfectly healthy sketch once ``run_mutation`` has returned, so a post-hoc reading would
        report a 0.0 sensitivity measured over a document that no longer holds the fault.
        """
        import FreeCAD as App

        from freecad_buddy.usecases import transaction, verify
        from freecad_buddy.usecases.documents import DocumentRegistry

        case = self._case("g2-fault-sketch-under-unconstrained-line")
        registry = DocumentRegistry()
        handle = registry.document_open(str(case["dir"] / "fixture.FCStd"))
        handle = handle["structured_content"]["doc"]
        document = registry.with_document(handle, lambda _h, d: d)
        document, envelope = transaction.run_mutation(
            document, handle, case["planted_op"], planted_sketches.resolve(case["planted_op"])
        )
        registry.rebind(handle, document)
        self.assertNotEqual(envelope.get("status"), "OK")

        after = registry.with_document(
            handle, lambda _h, d: verify.read_sketch(d, planted_sketches.SKETCH_NAME)
        )
        self.assertEqual(after["status"], "OK")
        subject = (after.get("structured_content") or {}).get("subject") or {}
        self.assertEqual(subject.get("dof"), 0)
        self.assertTrue(subject.get("fully_constrained"))
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)


class UndriveableCaseTest(unittest.TestCase):
    """An op with no reachable trigger refuses rather than reporting a convenient verdict."""

    def test_the_silent_dressup_drop_refuses_to_pretend(self):
        import FreeCAD as App

        document = App.newDocument("undriveable_probe")
        try:
            with self.assertRaises(planted_ops.OpNotDriveable):
                planted_ops.drop_dressup_edge_silently(document)
        finally:
            App.closeDocument(document.Name)


class ScorerHonestyTest(unittest.TestCase):
    """The scorer never presents an unmeasured validator as a measured zero."""

    @classmethod
    def setUpClass(cls):
        cls.results = scorer.score()

    def test_a_validator_with_no_case_is_reported_not_scored(self):
        self.assertIn("reason", self.results["fingerprint"])

    def test_the_sketch_validator_is_scored_over_its_own_suite(self):
        """``verify_sketch`` carried no fault case for months (DW-98); never regress there."""
        result = self.results["verify_sketch"]
        self.assertNotIn("reason", result, result.get("reason"))
        self.assertGreaterEqual(result["planted"], 10, result["rows"])
        self.assertGreater(result["controls"], 0, result["rows"])

    def test_a_validator_with_no_driveable_planted_case_is_reported_not_scored(self):
        """sensitivity(0, 0) is 0.0, which must never read as 'every defect was missed'."""
        for name, result in self.results.items():
            if result["planted"] == 0:
                self.assertIn("reason", result, f"{name} scored a rate over zero planted cases")

    def test_every_skipped_case_carries_a_reason(self):
        for name, result in self.results.items():
            for case_id, reason in result["skipped"]:
                self.assertTrue(reason.strip(), f"{name}/{case_id} was skipped with no reason")

    def test_the_scored_validators_meet_their_bars(self):
        """Only validators the run actually measured are held to the bars."""
        for name, result in self.results.items():
            if result.get("reason"):
                continue
            self.assertGreaterEqual(result["sensitivity"], 0.95, f"{name}: {result['rows']}")
            self.assertLessEqual(result["false_alarm"], 0.05, f"{name}: {result['rows']}")

    def test_at_least_one_validator_is_genuinely_scored(self):
        """The suite exists to produce a number; a run scoring nothing is a regression."""
        scored = [name for name, r in self.results.items() if not r.get("reason")]
        self.assertTrue(scored, "no validator was scored at all")

    def test_no_planted_case_is_silently_dropped(self):
        """Every case is either scored or explicitly skipped with a reason."""
        cases = scorer.load_cases()
        accounted = sum(len(r["rows"]) + len(r["skipped"]) for r in self.results.values())
        self.assertEqual(accounted, len(cases))


if __name__ == "__main__":
    unittest.main()
