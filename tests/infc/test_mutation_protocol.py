"""In-FreeCAD tests for the mutation protocol and the TNP guard (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Covers the commit path, the post-verify failure path,
an op that raises, the forced hash-mismatch that escalates to the snapshot restore, the
``UNSUPPORTED`` capability gate, snapshot cleanup, and that no transaction is left open. Expected
values are analytic (hand-computed box geometry, the pre-mutation fingerprint the wrapper itself
captured before the op ran), never captured from a verify tool.
"""

import glob
import hashlib
import os
import unittest

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.contracts import fingerprints_equal
from freecad_buddy.usecases import confirm, shim, tnp_guard, transaction, verify
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError, temp_dir
from freecad_buddy.usecases.fingerprint import fingerprint

BOX_L = 10.0
BOX_W = 20.0
BOX_H = 30.0
CYL_R = 5.0
CYL_H = 20.0

# Snapshots live in the session workdir, not the OS temp directory (AD-25). Globbing the OS temp
# directory here would now match nothing and this leak check would pass without measuring.
_SNAPSHOT_GLOB = os.path.join(temp_dir(), "FCB_TMP_snap_*")


def _snapshot_leftovers():
    """Every reserved-prefix snapshot directory currently on disk."""
    return sorted(glob.glob(_SNAPSHOT_GLOB))


class _MutationFixture(unittest.TestCase):
    def setUp(self):
        for path in _snapshot_leftovers():
            for name in os.listdir(path):
                os.remove(os.path.join(path, name))
            os.rmdir(path)
        self.registry = DocumentRegistry()
        created = self.registry.document_create("mutation_protocol")
        self.handle = created["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))
        self._add_box()

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _add_box(self):
        box = self.document.addObject("Part::Box", "Box")
        box.Length = BOX_L
        box.Width = BOX_W
        box.Height = BOX_H
        self.document.recompute()
        return box

    def _add_padded_body(self):
        """A Body holding a fully constrained 20x30 sketch padded 10 mm."""
        body = self.document.addObject("PartDesign::Body", "Body")
        sketch = self.document.addObject("Sketcher::SketchObject", "Profile")
        body.addObject(sketch)
        corners = [(0, 0), (20, 0), (20, 30), (0, 30)]
        for index in range(4):
            start = corners[index]
            end = corners[(index + 1) % 4]
            sketch.addGeometry(Part.LineSegment(App.Vector(*start, 0), App.Vector(*end, 0)), False)
        for index in range(4):
            sketch.addConstraint(Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1))
        for index in (0, 2):
            sketch.addConstraint(Sketcher.Constraint("Horizontal", index))
        for index in (1, 3):
            sketch.addConstraint(Sketcher.Constraint("Vertical", index))
        sketch.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, 0, 1, 0))
        sketch.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 0, 1, 0))
        sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 20))
        sketch.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 30))
        pad = self.document.addObject("PartDesign::Pad", "Pad")
        body.addObject(pad)
        pad.Profile = sketch
        pad.Length = 10
        self.document.recompute()
        self.assertTrue(pad.isValid())

    def _run(self, label, op, document=None):
        return transaction.run_mutation(document or self.document, self.handle, label, op)


def _add_cylinder(document):
    """A well-formed op: add a valid cylinder and report it as touched."""
    cylinder = document.addObject("Part::Cylinder", "Cyl")
    cylinder.Radius = CYL_R
    cylinder.Height = CYL_H
    return ["Cyl"]


def _raise_after_add(document):
    """An op that adds an object then raises, leaving the transaction to the wrapper."""
    document.addObject("Part::Sphere", "Sph")
    raise RuntimeError("planted op failure")


def _add_with_undo_disabled(document):
    """The #6031 pattern: undo is switched off mid-transaction, so abort restores nothing."""
    document.UndoMode = 0
    document.addObject("Part::Sphere", "Sph6031")
    raise RuntimeError("planted #6031 rollback-boundary failure")


class CommitPathTest(_MutationFixture):
    def test_passing_op_commits_and_reports_both_fingerprints(self):
        before = fingerprint(self.document)
        _, envelope = self._run("add cylinder", _add_cylinder)

        self.assertEqual(envelope["status"], "OK")
        self.assertIsNone(envelope["detail"])
        block = envelope["structured_content"]["mutation"]
        self.assertEqual(block["schema"], "fcb.mutation/1")
        self.assertEqual(block["transaction_id"], "0")
        self.assertEqual(block["fingerprint_before"]["digest"], before["digest"])
        self.assertNotEqual(block["fingerprint_after"]["digest"], before["digest"])
        self.assertFalse(block["rolled_back"])
        self.assertIsNone(block["rollback_proven"])
        self.assertTrue(block["post_verify"]["passed"])
        self.assertIsNone(block["post_verify"]["explanation"])

    def test_commit_leaves_the_new_object_on_the_document(self):
        self._run("add cylinder", _add_cylinder)
        self.assertIn("Cyl", [obj.Name for obj in self.document.Objects])

    def test_commit_deletes_the_snapshot_and_leaves_no_open_transaction(self):
        self._run("add cylinder", _add_cylinder)
        self.assertEqual(_snapshot_leftovers(), [])
        self.assertFalse(self.document.HasPendingTransaction)


class RollbackProofTest(_MutationFixture):
    def test_raising_op_rolls_back_and_proves_it_by_rehash(self):
        before = fingerprint(self.document)
        document, envelope = self._run("raising op", _raise_after_add)

        self.assertEqual(envelope["status"], "SPEC_FAILED")
        self.assertIsNotNone(envelope["detail"])
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertEqual(block["rollback_proven"], "rolled_back_verified")
        self.assertTrue(fingerprints_equal(fingerprint(document), before))
        self.assertNotIn("Sph", [obj.Name for obj in document.Objects])

    def test_the_exception_message_becomes_the_human_readable_explanation(self):
        _, envelope = self._run("raising op", _raise_after_add)
        explanation = envelope["structured_content"]["mutation"]["post_verify"]["explanation"]
        self.assertIn("planted op failure", explanation)
        self.assertIn("RuntimeError", explanation)

    def test_hash_mismatch_escalates_to_the_snapshot_restore_and_reports_the_path(self):
        before = fingerprint(self.document)
        document, envelope = self._run("6031 pattern", _add_with_undo_disabled)

        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertEqual(block["rollback_proven"], "rolled_back_via_snapshot")
        self.assertIsNotNone(block["snapshot_path"])
        self.assertTrue(fingerprints_equal(fingerprint(document), before))
        self.assertNotIn("Sph6031", [obj.Name for obj in document.Objects])

    def test_a_snapshot_restore_of_a_body_document_is_proven_on_mass_properties(self):
        # Reopening the snapshot re-serializes every shape, so a PartDesign document never gets
        # its B-rep digest back; the restore must still be provable.
        self._add_padded_body()
        before = fingerprint(self.document)
        real_equal = transaction.fingerprints_equal
        calls = []

        def once_unequal(left, right):
            calls.append(1)
            return False if len(calls) == 1 else real_equal(left, right)

        transaction.fingerprints_equal = once_unequal
        try:
            document, envelope = self._run("forced restore", _raise_after_add)
        finally:
            transaction.fingerprints_equal = real_equal

        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"], block["post_verify"]["explanation"])
        self.assertEqual(block["rollback_proven"], "rolled_back_via_snapshot")
        self.assertNotEqual(fingerprint(document)["digest"], before["digest"])
        self.assertNotIn("Sph", [obj.Name for obj in document.Objects])
        self.assertEqual(
            [entry["name"] for entry in fingerprint(document)["objects"]],
            [entry["name"] for entry in before["objects"]],
        )

    def test_a_raising_op_reports_the_audit_it_never_ran_as_unsupported(self):
        _, envelope = self._run("raising op", _raise_after_add)

        audit = envelope["structured_content"]["mutation"]["post_verify"]["tnp_audit"]
        self.assertEqual(audit["status"], "UNSUPPORTED")
        self.assertEqual(audit["findings"], [])

    def test_snapshot_restore_preserves_the_document_label(self):
        label = self.document.Label
        document, _ = self._run("6031 pattern", _add_with_undo_disabled)
        self.assertEqual(document.Label, label)

    def test_rollback_deletes_the_snapshot_on_both_proof_paths(self):
        document, _ = self._run("raising op", _raise_after_add)
        self.assertEqual(_snapshot_leftovers(), [])
        self._run("6031 pattern", _add_with_undo_disabled, document=document)
        self.assertEqual(_snapshot_leftovers(), [])

    def test_rollback_leaves_no_open_transaction(self):
        document, _ = self._run("raising op", _raise_after_add)
        self.assertFalse(document.HasPendingTransaction)

    def test_an_unprovable_rollback_never_claims_restoration_and_keeps_the_snapshot(self):
        """A snapshot that cannot reproduce the pre-state must report, not assert, restoration."""
        restore = transaction._restore_from_snapshot

        def _restore_to_a_divergent_state(document, snapshot_path):
            # Restore, then plant an extra object so the re-asserted hash cannot match.
            restored = restore(document, snapshot_path)
            restored.addObject("Part::Sphere", "Unrestorable")
            restored.recompute()
            return restored

        transaction._restore_from_snapshot = _restore_to_a_divergent_state
        try:
            document, envelope = self._run("6031 pattern", _add_with_undo_disabled)
        finally:
            transaction._restore_from_snapshot = restore

        block = envelope["structured_content"]["mutation"]
        self.assertEqual(envelope["status"], "SPEC_FAILED")
        self.assertFalse(block["rolled_back"])
        self.assertIsNone(block["rollback_proven"])
        self.assertIn("could not be proven", block["post_verify"]["explanation"])
        self.assertTrue(os.path.isfile(block["snapshot_path"]))
        del document


class _FailingDocument:
    """Delegates to a real document, raising ``_PlantedFailure`` from one named method.

    Injects an I/O or kernel failure at a single bracket step without touching the module under
    test, so the wrapper sees a document whose ``saveCopy``/``commitTransaction`` behaves like a
    full disk or a kernel refusal.
    """

    def __init__(self, inner, method):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_method", method)

    def __getattr__(self, item):
        if item == object.__getattribute__(self, "_method"):
            raise _PlantedFailure(f"planted {item} failure")
        return getattr(object.__getattribute__(self, "_inner"), item)

    def __setattr__(self, item, value):
        setattr(object.__getattribute__(self, "_inner"), item, value)


class _PlantedFailure(RuntimeError):
    """The failure the bracket-guard tests inject."""


class BracketGuardTest(_MutationFixture):
    """Every step of the bracket that can raise must still return a terminal envelope.

    Covers the calls outside the op/recompute/post_verify try: the ``saveCopy`` snapshot write,
    the fingerprints on both sides of the bracket, and the commit. Each must close the
    transaction (R5), release or report the snapshot (R6) and hand the caller an envelope.
    """

    def _assert_the_audit_that_ran_is_reported(self, block):
        """A commit failure comes after a passing post-verify, so its audit did run."""
        if not shim.element_map_available():
            self.skipTest("element map unavailable; the audit reports UNSUPPORTED by design")
        self.assertEqual(block["post_verify"]["tnp_audit"]["status"], "CLEAN")

    def _assert_closed_failure(self, envelope, document):
        self.assertEqual(envelope["status"], "SPEC_FAILED")
        self.assertIsNotNone(envelope["detail"])
        self.assertFalse(document.HasPendingTransaction)
        block = envelope["structured_content"]["mutation"]
        self.assertFalse(block["post_verify"]["passed"])
        self.assertIn("planted", block["post_verify"]["explanation"])
        return block

    def test_a_failing_savecopy_returns_an_envelope_and_leaks_no_snapshot(self):
        before = fingerprint(self.document)
        document, envelope = self._run(
            "unwritable snapshot",
            _add_cylinder,
            document=_FailingDocument(self.document, "saveCopy"),
        )

        block = self._assert_closed_failure(envelope, self.document)
        # The fingerprint was taken before saveCopy failed, so the block reports it.
        self.assertEqual(block["fingerprint_before"]["digest"], before["digest"])
        self.assertEqual(_snapshot_leftovers(), [])
        self.assertNotIn("Cyl", [obj.Name for obj in self.document.Objects])
        del document

    def test_a_failing_post_commit_fingerprint_is_reported_rather_than_raised(self):
        """The commit already happened, so the envelope must report it, not claim a rollback."""
        before = fingerprint(self.document)
        real = transaction.fingerprint
        calls = {"n": 0}

        def _fail_after_the_first(document):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise _PlantedFailure("planted post-commit fingerprint failure")
            return real(document)

        transaction.fingerprint = _fail_after_the_first
        try:
            document, envelope = self._run("post-commit hash", _add_cylinder)
        finally:
            transaction.fingerprint = real

        block = self._assert_closed_failure(envelope, document)
        self._assert_the_audit_that_ran_is_reported(block)
        # The mutation is committed and cannot be undone from here, so it must not be reported
        # as rolled back, and the after-fingerprint it could not take stays absent.
        self.assertFalse(block["rolled_back"])
        self.assertIsNone(block["rollback_proven"])
        self.assertIsNone(block["fingerprint_after"])
        self.assertEqual(block["fingerprint_before"]["digest"], before["digest"])
        self.assertIn("Cyl", [obj.Name for obj in document.Objects])
        # R6: the document diverged from the snapshot's state, so the snapshot is kept and named.
        self.assertIsNotNone(block["snapshot_path"])
        self.assertTrue(os.path.isfile(block["snapshot_path"]))

    def test_a_failing_pre_bracket_fingerprint_returns_an_envelope_and_opens_no_transaction(self):
        real = transaction.fingerprint

        def _always_fails(document):
            raise _PlantedFailure("planted pre-bracket fingerprint failure")

        transaction.fingerprint = _always_fails
        try:
            document, envelope = self._run("pre-bracket hash", _add_cylinder)
        finally:
            transaction.fingerprint = real

        self.assertEqual(envelope["status"], "SPEC_FAILED")
        self.assertFalse(document.HasPendingTransaction)
        self.assertEqual(_snapshot_leftovers(), [])
        self.assertNotIn("Cyl", [obj.Name for obj in document.Objects])

    def test_a_failing_commit_closes_the_transaction_and_rolls_back(self):
        """R5: a commit that raises must not leave the transaction open for the next one to eat."""
        before = fingerprint(self.document)
        document, envelope = self._run(
            "failing commit",
            _add_cylinder,
            document=_FailingDocument(self.document, "commitTransaction"),
        )

        block = self._assert_closed_failure(envelope, self.document)
        self._assert_the_audit_that_ran_is_reported(block)
        self.assertTrue(fingerprints_equal(fingerprint(self.document), before))
        self.assertNotIn("Cyl", [obj.Name for obj in self.document.Objects])
        self.assertEqual(_snapshot_leftovers(), [])
        del document


class PostVerifyFailureTest(_MutationFixture):
    def test_an_object_failing_isvalid_fails_post_verify_and_rolls_back(self):
        before = fingerprint(self.document)

        def op(document):
            # A pad with no profile cannot execute, so it stays invalid after the recompute.
            document.addObject("PartDesign::Pad", "BadPad")
            return ["BadPad"]

        document, envelope = self._run("invalid pad", op)

        self.assertNotEqual(envelope["status"], "OK")
        block = envelope["structured_content"]["mutation"]
        self.assertFalse(block["post_verify"]["passed"])
        self.assertTrue(block["rolled_back"])
        self.assertIsNotNone(block["post_verify"]["explanation"])
        self.assertTrue(fingerprints_equal(fingerprint(document), before))

    def test_an_unconstrained_sketch_hard_fails_post_verify_and_names_the_sketch(self):
        before = fingerprint(self.document)

        def op(document):
            sketch = document.addObject("Sketcher::SketchObject", "LooseSketch")
            sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0)), False)
            return ["LooseSketch"]

        document, envelope = self._run("loose sketch", op)

        block = envelope["structured_content"]["mutation"]
        self.assertFalse(block["post_verify"]["passed"])
        self.assertFalse(block["post_verify"]["fully_constrained"])
        self.assertIn("LooseSketch", block["post_verify"]["explanation"])
        self.assertTrue(block["rolled_back"])
        self.assertTrue(fingerprints_equal(fingerprint(document), before))

    def test_recompute_failure_classes_as_recompute_error(self):
        def op(document):
            document.addObject("PartDesign::Pad", "BadPad")
            return ["BadPad"]

        _, envelope = self._run("invalid pad", op)
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        self.assertFalse(
            envelope["structured_content"]["mutation"]["post_verify"]["recompute_clean"]
        )


class NotMeasuredTest(_MutationFixture):
    def _block_from_failed_shape_with_a_touched_sketch(self):
        """Drive the ``verify_shape`` raise path with a sketch also in ``touched``.

        The op touches both a shape-bearing object and a sketch. ``verify_shape`` is made to
        raise, so the block returns before the sketch loop runs.
        """

        def op(document):
            cylinder = document.addObject("Part::Cylinder", "Cyl")
            cylinder.Radius = CYL_R
            cylinder.Height = CYL_H
            document.addObject("Sketcher::SketchObject", "Untouched")
            return ["Cyl", "Untouched"]

        real = verify.verify_shape

        def _always_fails(*args, **kwargs):
            raise ValidationError("planted verify_shape failure")

        verify.verify_shape = _always_fails
        try:
            _, envelope = self._run("shape raises", op)
        finally:
            verify.verify_shape = real

        return envelope["structured_content"]["mutation"]

    def _block_from_raised_verify_sketch(self):
        """Drive the ``verify_sketch`` raise path so no shape is graded on that step."""

        def op(document):
            document.addObject("Sketcher::SketchObject", "Ungraded")
            return ["Ungraded"]

        real = verify.verify_sketch

        def _always_fails(*args, **kwargs):
            raise ValidationError("planted verify_sketch failure")

        verify.verify_sketch = _always_fails
        try:
            _, envelope = self._run("sketch raises", op)
        finally:
            verify.verify_sketch = real

        return envelope["structured_content"]["mutation"]

    def _block_from_successful_mutation(self):
        _, envelope = self._run("add cylinder", _add_cylinder)
        return envelope["structured_content"]["mutation"]

    def test_a_shape_failure_reports_the_sketch_grade_as_not_measured(self):
        """The sketch loop never ran, so its verdict is unmeasured rather than inapplicable.

        ``None`` means no sketch was involved. Reporting it here would claim a measurement of a
        sketch the op touched but never graded.
        """
        block = self._block_from_failed_shape_with_a_touched_sketch()

        self.assertEqual(block["post_verify"]["fully_constrained"], "not_measured")

    def test_a_sketch_grading_failure_reports_validity_as_not_measured(self):
        block = self._block_from_raised_verify_sketch()

        self.assertEqual(block["post_verify"]["is_valid"], "not_measured")

    def test_a_successful_mutation_reports_real_booleans(self):
        # Pins the boundary: the sentinel must not leak onto a path that did measure.
        block = self._block_from_successful_mutation()

        self.assertIsInstance(block["post_verify"]["is_valid"], bool)
        self.assertIsInstance(block["post_verify"]["fully_constrained"], (bool, type(None)))


class NullShapeFingerprintTest(_MutationFixture):
    def test_an_object_with_a_null_shape_enters_the_digest(self):
        # A feature whose shape went null (a broken Tip) must not vanish from the fingerprint,
        # or a rollback that left it broken would hash equal to the pre-mutation state.
        before = fingerprint(self.document)
        self.document.addObject("Sketcher::SketchObject", "Empty")
        self.document.recompute()

        after = fingerprint(self.document)

        self.assertNotEqual(after["digest"], before["digest"])
        entry = next(e for e in after["objects"] if e["name"] == "Empty")
        self.assertEqual(entry["brep_sha256"], hashlib.sha256(b"").hexdigest())
        self.assertEqual(entry["massprops"]["volume"], 0.0)


class SerializerTagTest(_MutationFixture):
    def test_cross_tag_comparison_propagates_the_contract_value_error(self):
        record = fingerprint(self.document)
        other_tag = "exportBrep" if record["serializer"] == "exportBinary" else "exportBinary"
        mismatched = dict(record, serializer=other_tag)
        with self.assertRaises(ValueError):
            fingerprints_equal(record, mismatched)


class TnpGuardTest(_MutationFixture):
    def test_snapshot_records_a_sketch_external_geometry_reference(self):
        sketch = self.document.addObject("Sketcher::SketchObject", "Ext")
        sketch.AttachmentSupport = [(self.document.getObject("Box"), ["Face1"])]
        self.document.recompute()

        records = tnp_guard.snapshot_references(self.document)
        attachment = [r for r in records if r["prop"] == "AttachmentSupport"]
        self.assertEqual(len(attachment), 1)
        self.assertEqual(attachment[0]["owner"], "Ext")
        self.assertEqual(attachment[0]["target"], "Box")
        self.assertEqual(attachment[0]["entries"][0]["indexed"], "Face1")

    def test_clean_document_audits_clean(self):
        audit = tnp_guard.audit_references(
            self.document, tnp_guard.snapshot_references(self.document)
        )
        if shim.element_map_available():
            self.assertEqual(audit["status"], "CLEAN")
            self.assertEqual(audit["findings"], [])
        else:
            self.assertEqual(audit["status"], "UNSUPPORTED")

    def test_layer_zero_flags_an_invalid_object(self):
        if not shim.element_map_available():
            self.skipTest("element map unavailable; the guard reports UNSUPPORTED by design")
        snapshot = tnp_guard.snapshot_references(self.document)
        self.document.addObject("PartDesign::Pad", "BadPad")
        self.document.recompute()

        audit = tnp_guard.audit_references(self.document, snapshot)
        self.assertEqual(audit["status"], "FLAGGED")
        self.assertEqual([f["verdict"] for f in audit["findings"]], ["BROKEN"])
        self.assertEqual(audit["findings"][0]["owner"], "BadPad")
        self.assertEqual(audit["findings"][0]["layer"], 0)

    def test_unsupported_reports_no_pass_when_the_element_map_is_unavailable(self):
        sketch = self.document.addObject("Sketcher::SketchObject", "Ext")
        sketch.AttachmentSupport = [(self.document.getObject("Box"), ["Face1"])]
        self.document.recompute()
        snapshot = tnp_guard.snapshot_references(self.document)

        probe = shim.element_map_available
        shim.element_map_available = lambda: False
        try:
            audit = tnp_guard.audit_references(self.document, snapshot)
        finally:
            shim.element_map_available = probe

        self.assertEqual(audit["status"], "UNSUPPORTED")
        self.assertTrue(audit["findings"])
        self.assertEqual({f["verdict"] for f in audit["findings"]}, {"UNSUPPORTED"})

    def test_mutation_reports_unsupported_in_its_tnp_block_without_failing_on_that_alone(self):
        probe = shim.element_map_available
        shim.element_map_available = lambda: False
        try:
            _, envelope = self._run("add cylinder", _add_cylinder)
        finally:
            shim.element_map_available = probe

        block = envelope["structured_content"]["mutation"]
        self.assertEqual(envelope["status"], "OK")
        self.assertTrue(block["post_verify"]["passed"])
        self.assertEqual(block["post_verify"]["tnp_audit"]["status"], "UNSUPPORTED")


class UndoProbeTest(_MutationFixture):
    def test_enable_undo_reports_the_state_the_document_actually_holds(self):
        self.document.UndoMode = 0
        self.assertTrue(shim.enable_undo(self.document))
        self.assertEqual(self.document.UndoMode, 1)


class AuditRecordTest(_MutationFixture):
    class _RecordingSink:
        def __init__(self):
            self.lines = []

        def before(self, event, tool, doc, params, fingerprint_before=None):
            self.lines.append(("before", event, tool, doc, fingerprint_before))

        def after(
            self,
            event,
            tool,
            doc,
            params,
            verdict,
            fingerprint_before=None,
            fingerprint_after=None,
            rollback=None,
        ):
            self.lines.append(
                (
                    "after",
                    event,
                    tool,
                    doc,
                    verdict,
                    fingerprint_before,
                    fingerprint_after,
                    rollback,
                )
            )

    def test_a_committed_mutation_writes_both_digests(self):
        sink = self._RecordingSink()
        before = fingerprint(self.document)
        transaction.run_mutation(
            self.document,
            self.handle,
            "add cylinder",
            _add_cylinder,
            audit_sink=sink,
            tool="feature_pad",
            params={"length": 5},
        )

        pre, post = sink.lines
        self.assertEqual(pre[:4], ("before", "mutation", "feature_pad", self.handle))
        self.assertEqual(pre[4], before["digest"])
        self.assertEqual(post[4], "OK")
        self.assertEqual(post[5], before["digest"])
        self.assertIsNotNone(post[6])
        self.assertNotEqual(post[6], before["digest"])
        self.assertFalse(post[7]["rolled_back"])

    def test_a_rolled_back_mutation_writes_the_rollback_block_and_both_digests(self):
        sink = self._RecordingSink()
        before = fingerprint(self.document)
        transaction.run_mutation(
            self.document,
            self.handle,
            "raising op",
            _raise_after_add,
            audit_sink=sink,
            tool="feature_pad",
            params={},
        )

        post = sink.lines[-1]
        self.assertEqual(post[5], before["digest"])
        self.assertEqual(post[6], before["digest"])
        self.assertTrue(post[7]["rolled_back"])
        self.assertEqual(post[7]["rollback_proven"], "rolled_back_verified")
        self.assertIn("planted op failure", post[7]["explanation"])

    def test_with_no_sink_passed_the_lines_go_to_the_host_sink(self):
        sink = self._RecordingSink()
        previous = confirm.set_approval_sink(sink)
        try:
            transaction.run_mutation(
                self.document, self.handle, "add cylinder", _add_cylinder, tool="feature_pad"
            )
        finally:
            confirm.set_approval_sink(previous)

        self.assertEqual([line[0] for line in sink.lines], ["before", "after"])

    def test_a_preview_copy_writes_no_mutation_lines_to_the_host_sink(self):
        sink = self._RecordingSink()
        previous = confirm.set_approval_sink(sink)
        try:
            with confirm.preview_exemption():
                transaction.run_mutation(
                    self.document, self.handle, "add cylinder", _add_cylinder, tool="feature_pad"
                )
        finally:
            confirm.set_approval_sink(previous)

        self.assertEqual(sink.lines, [])

    def test_a_setup_failure_still_writes_both_lines(self):
        # The adapters skip their own pair for an envelope carrying a mutation block, so every
        # path that returns one must write the pair itself.
        sink = self._RecordingSink()
        real = transaction.fingerprint

        def _always_fails(document):
            raise RuntimeError("planted pre-bracket fingerprint failure")

        transaction.fingerprint = _always_fails
        try:
            transaction.run_mutation(
                self.document,
                self.handle,
                "pre-bracket hash",
                _add_cylinder,
                audit_sink=sink,
                tool="feature_pad",
            )
        finally:
            transaction.fingerprint = real

        pre, post = sink.lines
        self.assertEqual(pre, ("before", "mutation", "feature_pad", self.handle, None))
        self.assertEqual(post[4], "SPEC_FAILED")
        self.assertIsNone(post[5])


if __name__ == "__main__":
    unittest.main()
