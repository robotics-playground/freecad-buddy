"""In-FreeCAD tests for the G2 planted-op registry and scorer (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Pins the two properties that make the G2 fault suite
scorable at all: every ``planted_op`` a case names resolves to a callable, and a planted defect is
actually detected while its paired clean control is not.

The detection tests drive the ops through the same production mutation bracket the scorer uses, so
a regression in ``run_mutation``, ``tnp_guard`` or the assertion grader surfaces here rather than
only in a benchmark run.
"""

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
FAULT_DIR = REPO_ROOT / "benchmarks" / "g2" / "fault-injection"
if str(FAULT_DIR) not in sys.path:
    sys.path.insert(0, str(FAULT_DIR))

import planted_ops  # noqa: E402
import score_g2_infc as scorer  # noqa: E402


class PlantedOpResolutionTest(unittest.TestCase):
    """Every ``planted_op`` a case declares must resolve; the ledger's DW-73 gap."""

    def setUp(self):
        self.cases = scorer.load_cases()

    def test_the_suite_holds_the_expected_case_count(self):
        self.assertEqual(len(self.cases), 28)

    def test_every_planted_op_resolves_to_a_callable(self):
        unresolved = []
        for case in self.cases:
            try:
                op = planted_ops.resolve(case["planted_op"])
            except KeyError:
                unresolved.append((case["id"], case["planted_op"]))
                continue
            if not callable(op):
                unresolved.append((case["id"], case["planted_op"]))
        self.assertEqual(unresolved, [], f"planted_op names resolving to nothing: {unresolved}")

    def test_every_case_yaml_planted_op_is_in_the_registry(self):
        """Read the declarations from the YAML directly, not through the loader's parsing."""
        declared = set()
        for path in FAULT_DIR.rglob("case.yaml"):
            if path.name != "case.yaml":
                continue
            match = re.search(r"^planted_op:\s*(\S+)", path.read_text(encoding="utf-8"), re.M)
            self.assertIsNotNone(match, f"{path} declares no planted_op")
            declared.add(match.group(1))
        self.assertEqual(declared - set(planted_ops.REGISTRY), set())

    def test_the_registry_declares_no_op_no_case_names(self):
        """A registry entry nothing names is dead weight that no run would ever exercise."""
        named = {case["planted_op"] for case in self.cases}
        self.assertEqual(set(planted_ops.REGISTRY) - named, set())

    def test_every_undriveable_op_is_a_real_registry_entry_with_a_reason(self):
        for name, reason in planted_ops.UNDRIVEABLE.items():
            self.assertIn(name, planted_ops.REGISTRY, name)
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
        for name in ("fingerprint", "verify_sketch"):
            self.assertIn("reason", self.results[name], name)

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
