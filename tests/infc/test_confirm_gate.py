"""In-FreeCAD tests for the mutation confirm gate (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Covers every confirm row of the I/O matrix against a
live document: the accepted token minted by a real ``preview_dry_run``, the missing, malformed,
forged, expired, wrong-document, wrong-operation, wrong-argument, stale-state and replayed
rejections, the operator auto-approve posture, a client-supplied ``autoApprove`` being refused
rather than honoured, the lifecycle-op exemption, and that a rejected call wrote no snapshot and
opened no transaction.

The gate fires for both tool families, so the rejection rows are exercised through a
``feature_*`` and a ``sketch_*`` tool alike.
"""

import glob
import json
import os
import tempfile
import time
import unittest

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.adapters.audit_log import AuditSink
from freecad_buddy.hosts.tool_catalog import preview_op_table
from freecad_buddy.usecases import confirm, features, preview, sketches, transaction
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError, temp_dir
from freecad_buddy.usecases.fingerprint import fingerprint

SQUARE = 10.0
PAD_LENGTH = 5.0
PAD_VOLUME = SQUARE * SQUARE * PAD_LENGTH

# Snapshots live in the session workdir, not the OS temp directory (AD-25). Globbing the OS temp
# directory here would now match nothing and this leak check would pass without measuring.
_SNAPSHOT_GLOB = os.path.join(temp_dir(), "FCB_TMP_snap_*")

PAD_ARGS = {
    "body": "Body",
    "profile": "Sketch",
    "name": "Pad",
    "length": {"value": PAD_LENGTH, "unit": "mm"},
}


def _snapshot_leftovers():
    """Every reserved-prefix snapshot directory currently on disk."""
    return sorted(glob.glob(_SNAPSHOT_GLOB))


class _GateFixture(unittest.TestCase):
    """A live body with a fully constrained square sketch, gated fail-closed by default."""

    def setUp(self):
        for path in _snapshot_leftovers():
            for name in os.listdir(path):
                os.remove(os.path.join(path, name))
            os.rmdir(path)
        self._posture = confirm.set_auto_approve(False)
        self.registry = DocumentRegistry()
        created = self.registry.document_create("confirm_gate")
        self.handle = created["structured_content"]["doc"]
        self.document = self.registry.with_document(self.handle, lambda h, d: d)
        self._build()

    def tearDown(self):
        confirm.set_auto_approve(self._posture)
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _build(self):
        body = self.document.addObject("PartDesign::Body", "Body")
        sketch = self.document.addObject("Sketcher::SketchObject", "Sketch")
        body.addObject(sketch)
        corners = [(0, 0), (SQUARE, 0), (SQUARE, SQUARE), (0, SQUARE)]
        for index in range(4):
            start = corners[index]
            end = corners[(index + 1) % 4]
            sketch.addGeometry(
                Part.LineSegment(App.Vector(*start, 0), App.Vector(*end, 0)), False
            )
        for index in range(4):
            sketch.addConstraint(Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1))
        for index in (0, 2):
            sketch.addConstraint(Sketcher.Constraint("Horizontal", index))
        for index in (1, 3):
            sketch.addConstraint(Sketcher.Constraint("Vertical", index))
        sketch.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, 0, 1, 0))
        sketch.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 0, 1, 0))
        sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, SQUARE))
        sketch.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, SQUARE))
        self.document.recompute()
        self.assertTrue(sketch.FullyConstrained, "fixture sketch is not fully constrained")

    # -- helpers ---------------------------------------------------------------------------

    def object_names(self):
        return [obj.Name for obj in self.document.Objects]

    def preview_pad(self, **overrides):
        """Run a real ``preview_dry_run`` for the pad and return its structured content."""
        args = dict(PAD_ARGS, **overrides)
        envelope = preview.preview_dry_run(
            self.registry,
            preview_op_table(),
            None,
            doc=self.handle,
            operation={"tool": "feature_pad", "args": args},
            render="off",
        )
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        return envelope["structured_content"]

    def pad(self, confirm_value, **overrides):
        return features.feature_pad(
            self.registry, doc=self.handle, confirm=confirm_value, **dict(PAD_ARGS, **overrides)
        )

    def assert_refused_without_touching_the_document(self, call, *args, **kwargs):
        """Assert the call is refused, wrote no snapshot, and left the document unchanged.

        The snapshot is what discriminates: ``run_mutation`` mints one before it opens its
        transaction, so a snapshot path handed out at all proves the bracket ran and the gate
        fired too late.
        """
        before = self.object_names()
        real_snapshot_path = transaction.temp_snapshot_path
        minted = []

        def counting_snapshot_path(doc):
            minted.append(doc)
            return real_snapshot_path(doc)

        transaction.temp_snapshot_path = counting_snapshot_path
        try:
            with self.assertRaises(ValidationError) as excinfo:
                call(*args, **kwargs)
        finally:
            transaction.temp_snapshot_path = real_snapshot_path

        self.assertEqual(minted, [], "the mutation bracket opened and wrote a snapshot")
        self.assertEqual(self.object_names(), before, "the refused call changed the document")
        self.assertEqual(_snapshot_leftovers(), [])
        self.assertEqual(
            self.document.UndoCount, 0, "the refused call left a transaction on the undo stack"
        )
        return str(excinfo.exception)


class AcceptedTokenTest(_GateFixture):
    def test_a_token_from_a_preview_of_the_same_op_lets_the_mutation_run(self):
        token = self.preview_pad()["preview_id"]

        envelope = self.pad({"preview_id": token})

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIn("Pad", self.object_names())
        self.assertAlmostEqual(
            self.document.getObject("Pad").Shape.Volume, PAD_VOLUME, places=6
        )

    def test_the_accepted_call_carries_the_full_mutation_block(self):
        token = self.preview_pad()["preview_id"]

        block = self.pad({"preview_id": token})["structured_content"]["mutation"]

        self.assertTrue(block["post_verify"]["passed"])
        self.assertFalse(block["rolled_back"])
        self.assertNotEqual(
            block["fingerprint_before"]["digest"], block["fingerprint_after"]["digest"]
        )

    def test_an_explicit_accept_action_is_honoured(self):
        token = self.preview_pad()["preview_id"]

        envelope = self.pad({"preview_id": token, "elicitation_action": "accept"})

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))

    def test_the_advertised_expiry_is_the_one_carried_inside_the_token(self):
        structured = self.preview_pad()
        payload = confirm.decode_preview_token(structured["preview_id"])

        self.assertEqual(
            payload["exp"], int(_isoformat_to_epoch(structured["expires_at"])),
            "the advertised deadline and the enforced one are different values",
        )

    def test_the_token_binds_to_the_document_state_the_preview_measured(self):
        structured = self.preview_pad()
        payload = confirm.decode_preview_token(structured["preview_id"])

        self.assertEqual(payload["doc"], self.handle)
        self.assertEqual(payload["tool"], "feature_pad")
        self.assertEqual(payload["fingerprint_before"], fingerprint(self.document)["digest"])


def _isoformat_to_epoch(text):
    from datetime import datetime

    return datetime.fromisoformat(text).timestamp()


class SpentTokenTest(_GateFixture):
    """A token authorizes one mutation, not every mutation that leaves the digest still."""

    def test_a_token_accepted_once_is_refused_the_second_time(self):
        token = self.preview_pad()["preview_id"]
        self.assertEqual(self.pad({"preview_id": token})["status"], "OK")

        with self.assertRaises(ValidationError) as caught:
            self.pad({"preview_id": token})

        self.assertIn("already", str(caught.exception))

    def test_a_replay_is_refused_even_when_the_mutation_left_the_digest_unmoved(self):
        """The state check cannot see this replay: it compares equal on both attempts.

        A mutation writing a property the value it already holds commits without moving the
        document digest, so the fingerprint the token signs still matches. Only the spent-token
        record refuses the second call.
        """
        pad = self.pad({"preview_id": self.preview_pad()["preview_id"]})
        self.assertEqual(pad["status"], "OK")
        args = {"feature": "Pad", "parameters": {"Length": {"value": PAD_LENGTH, "unit": "mm"}}}
        envelope = preview.preview_dry_run(
            self.registry,
            preview_op_table(),
            None,
            doc=self.handle,
            operation={"tool": "feature_set_parameters", "args": args},
            render="off",
        )
        token = envelope["structured_content"]["preview_id"]
        digest_before = fingerprint(self.document)["digest"]

        first = features.feature_set_parameters(
            self.registry, doc=self.handle, confirm={"preview_id": token}, **args
        )

        self.assertEqual(first["status"], "OK", first.get("detail"))
        self.assertEqual(
            fingerprint(self.document)["digest"],
            digest_before,
            "this fixture only tests replay if the mutation leaves the digest unmoved",
        )
        with self.assertRaises(ValidationError):
            features.feature_set_parameters(
                self.registry, doc=self.handle, confirm={"preview_id": token}, **args
            )

    def test_a_refused_mutation_does_not_spend_its_token(self):
        """The token is spent by an authorized mutation, not by a call that failed after it."""
        token = self.preview_pad()["preview_id"]
        with self.assertRaises(ValidationError):
            self.pad({"preview_id": token}, name="")

        self.assertEqual(self.pad({"preview_id": token})["status"], "OK")

    def test_two_previews_of_the_same_op_mint_distinct_tokens(self):
        """Without a unique id per token the two are byte-identical, so spending one would
        pre-spend the other."""
        first = self.preview_pad()["preview_id"]
        second = self.preview_pad()["preview_id"]

        self.assertNotEqual(first, second)


class RejectionTest(_GateFixture):
    def test_a_missing_confirm_is_refused_and_nothing_is_created(self):
        message = self.assert_refused_without_touching_the_document(self.pad, None)
        self.assertIn("requires a confirm", message)

    def test_a_missing_confirm_is_refused_on_a_sketch_tool_too(self):
        message = self.assert_refused_without_touching_the_document(
            sketches.sketch_create,
            self.registry,
            doc=self.handle,
            name="Sketch2",
            plane="XY",
        )
        self.assertIn("requires a confirm", message)

    def test_a_destructive_sketch_tool_is_refused_without_a_confirm(self):
        """``sketch_remove_geometry`` executed unconfirmed before the gate existed (DW-85)."""
        message = self.assert_refused_without_touching_the_document(
            sketches.sketch_remove_geometry,
            self.registry,
            doc=self.handle,
            sketch="Sketch",
            geo_ids=[0],
        )
        self.assertIn("requires a confirm", message)
        self.assertEqual(len(self.document.getObject("Sketch").Geometry), 4)

    def test_an_empty_confirm_object_is_refused(self):
        self.assert_refused_without_touching_the_document(self.pad, {})

    def test_a_non_accept_elicitation_action_is_refused(self):
        token = self.preview_pad()["preview_id"]
        message = self.assert_refused_without_touching_the_document(
            self.pad, {"preview_id": token, "elicitation_action": "cancel"}
        )
        self.assertIn("elicitation_action", message)

    def test_a_non_string_preview_id_is_refused(self):
        self.assert_refused_without_touching_the_document(self.pad, {"preview_id": 7})

    def test_a_forged_token_is_refused(self):
        token = self.preview_pad()["preview_id"]
        body = token.rsplit(".", 1)[0]
        message = self.assert_refused_without_touching_the_document(
            self.pad, {"preview_id": f"{body}.{'A' * 43}"}
        )
        self.assertIn("signature", message)

    def test_a_token_with_no_signature_at_all_is_refused(self):
        message = self.assert_refused_without_touching_the_document(
            self.pad, {"preview_id": "fcb-preview:not-a-real-token"}
        )
        self.assertIn("malformed", message)

    def test_a_document_whose_state_cannot_be_read_is_refused_not_crashed(self):
        """A gate that cannot read the state it compares against rejects, per the fail-closed rule.

        Escaping as anything other than ``ValidationError`` maps to ``RECOMPUTE_ERROR`` at
        ``rpc_dispatch.py`` rather than to the ``INVALID_INPUT`` every gate failure produces.
        """
        token = self.preview_pad()["preview_id"]
        import freecad_buddy.usecases.fingerprint as fingerprint_module

        real = fingerprint_module.fingerprint

        def unreadable(document):
            raise fingerprint_module.SerializerUnavailable("no serializer on this build")

        fingerprint_module.fingerprint = unreadable
        try:
            with self.assertRaises(ValidationError) as caught:
                confirm.gate_mutation(
                    self.document,
                    self.handle,
                    "feature_pad",
                    {"doc": self.handle, "confirm": {"preview_id": token}},
                )
        finally:
            fingerprint_module.fingerprint = real

        self.assertIn("cannot read the state", str(caught.exception))

    def test_an_expired_token_is_refused_naming_the_expiry(self):
        payload = confirm.decode_preview_token(self.preview_pad()["preview_id"])
        payload["exp"] = int(time.time()) - 1
        message = self.assert_refused_without_touching_the_document(
            self.pad, {"preview_id": confirm.mint_preview_token(payload)}
        )
        self.assertIn("expired", message)

    def test_a_token_minted_for_another_document_is_refused(self):
        payload = confirm.decode_preview_token(self.preview_pad()["preview_id"])
        payload["doc"] = "fcb-doc:someone-elses-document"
        message = self.assert_refused_without_touching_the_document(
            self.pad, {"preview_id": confirm.mint_preview_token(payload)}
        )
        self.assertIn("different document", message)

    def test_a_token_minted_for_another_tool_is_refused(self):
        payload = confirm.decode_preview_token(self.preview_pad()["preview_id"])
        payload["tool"] = "feature_pocket"
        message = self.assert_refused_without_touching_the_document(
            self.pad, {"preview_id": confirm.mint_preview_token(payload)}
        )
        self.assertIn("feature_pocket", message)

    def test_a_token_minted_for_different_arguments_is_refused(self):
        token = self.preview_pad()["preview_id"]
        message = self.assert_refused_without_touching_the_document(
            self.pad, {"preview_id": token}, length={"value": 9.0, "unit": "mm"}
        )
        self.assertIn("different arguments", message)

    def test_a_stale_document_is_refused_naming_the_state_not_the_token(self):
        token = self.preview_pad()["preview_id"]
        # Change the document behind the token's back, the way a second client would. A new
        # shape-bearing object moves the fingerprint without touching the sketch the token names.
        box = self.document.addObject("Part::Box", "Interloper")
        box.Length = box.Width = box.Height = 1.0
        self.document.recompute()

        message = self.assert_refused_without_touching_the_document(
            self.pad, {"preview_id": token}
        )

        self.assertIn("changed since the preview", message)
        self.assertNotIn("signature", message)

    def test_replaying_an_accepted_token_after_the_apply_is_refused(self):
        token = self.preview_pad()["preview_id"]
        self.assertEqual(self.pad({"preview_id": token})["status"], "OK")

        # The same token, the same arguments, the same document — only the state has moved.
        with self.assertRaises(ValidationError) as excinfo:
            self.pad({"preview_id": token})

        # Two independent reasons refuse this call: the token is spent, and the fingerprint moved
        # with the apply. The spent check runs first, so it is the one that reports. A replay
        # whose mutation left the digest unmoved is covered by SpentTokenTest, where the state
        # check compares equal and the spent record is the only thing refusing.
        self.assertIn("already authorized", str(excinfo.exception))


class ClientSuppliedAutoApproveTest(_GateFixture):
    def test_a_client_supplied_autoapprove_is_refused_not_honoured(self):
        message = self.assert_refused_without_touching_the_document(
            self.pad, {"autoApprove": True}
        )
        self.assertIn("does not declare", message)

    def test_a_client_supplied_autoapprove_beside_a_valid_token_is_still_refused(self):
        token = self.preview_pad()["preview_id"]
        self.assert_refused_without_touching_the_document(
            self.pad, {"preview_id": token, "autoApprove": True}
        )


class AutoApprovePostureTest(_GateFixture):
    def setUp(self):
        super().setUp()
        confirm.set_auto_approve(True)

    def test_a_mutation_runs_with_no_confirm_under_the_operator_posture(self):
        envelope = self.pad(None)

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertAlmostEqual(
            self.document.getObject("Pad").Shape.Volume, PAD_VOLUME, places=6
        )

    def test_the_posture_does_not_survive_being_turned_back_off(self):
        confirm.set_auto_approve(False)
        self.assert_refused_without_touching_the_document(self.pad, None)


class ApprovalAuditTest(_GateFixture):
    """The approval record every accepted and auto-approved call must write."""

    class _RecordingSink:
        def __init__(self):
            self.records = []

        def approval(self, tool, doc, approval, params=None):
            self.records.append((tool, doc, dict(approval), params))

        def before(self, *args, **kwargs):
            pass

        def after(self, *args, **kwargs):
            pass

    def setUp(self):
        super().setUp()
        self.sink = self._RecordingSink()
        self._previous_sink = confirm.set_approval_sink(self.sink)

    def tearDown(self):
        confirm.set_approval_sink(self._previous_sink)
        super().tearDown()

    def test_an_accepted_token_writes_an_approval_record_naming_the_token_mode(self):
        token = self.preview_pad()["preview_id"]
        digest_before = fingerprint(self.document)["digest"]

        self.pad({"preview_id": token})

        self.assertEqual(len(self.sink.records), 1, self.sink.records)
        approvals = [r for r in self.sink.records if r[2]["mode"] == "preview_token"]
        self.assertEqual(len(approvals), 1, self.sink.records)
        tool, doc, record, params = approvals[0]
        self.assertEqual(tool, "feature_pad")
        self.assertEqual(doc, self.handle)
        self.assertEqual(record["fingerprint_before"], digest_before)
        self.assertTrue(record["args_digest"])
        # The call's own params reach the sink, so the approval line can carry the same
        # params_digest as the mutation's before/after lines and be joined to them.
        self.assertIsNotNone(params, "the approval cannot be joined to the call it authorized")
        self.assertEqual(params["doc"], self.handle)

    def test_an_auto_approved_call_records_that_it_was_automatic_and_what_it_covered(self):
        confirm.set_auto_approve(True)

        self.pad(None)

        self.assertEqual(len(self.sink.records), 1, self.sink.records)
        approvals = [r for r in self.sink.records if r[2]["mode"] == "auto_approve"]
        self.assertEqual(len(approvals), 1, self.sink.records)
        record = approvals[0][2]
        self.assertEqual(record["tool"], "feature_pad")
        self.assertTrue(record["args_digest"], "the approval names no params digest")

    def test_an_auto_approved_call_writes_three_lines_an_auditor_can_join(self):
        directory = tempfile.mkdtemp(prefix="FCB_TMP_gate_")
        path = os.path.join(directory, "audit.jsonl")
        confirm.set_approval_sink(AuditSink(path))
        confirm.set_auto_approve(True)
        digest_before = fingerprint(self.document)["digest"]
        try:
            envelope = features.feature_body_create(self.registry, doc=self.handle, name="Bracket")
            with open(path, encoding="utf-8") as handle:
                records = [json.loads(line) for line in handle]
        finally:
            os.remove(path)
            os.rmdir(directory)

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(
            [(r["event"], r["tool"]) for r in records],
            [
                ("approval", "feature_body_create"),
                ("mutation", "feature_body_create"),
                ("mutation", "feature_body_create"),
            ],
        )
        self.assertEqual(len({r["params_digest"] for r in records}), 1, records)
        self.assertEqual({r["fingerprint_before"] for r in records}, {digest_before})

    def test_a_preview_writes_no_approval_record(self):
        """A preview authorizes nothing and applies nothing, so it appends no approval line.

        The sink's contract covers an authorized geometry mutation; a preview runs the op on a
        throwaway copy that is discarded before the envelope is built.
        """
        self.preview_pad()

        self.assertEqual(self.sink.records, [])

    def test_a_refused_call_writes_no_approval_record(self):
        self.assert_refused_without_touching_the_document(self.pad, None)

        self.assertEqual(self.sink.records, [])

    def test_an_unwritable_sink_does_not_abort_an_authorized_mutation(self):
        class _Broken:
            def approval(self, *_args):
                raise OSError("audit volume is full")

        confirm.set_approval_sink(_Broken())
        token = self.preview_pad()["preview_id"]

        self.assertEqual(self.pad({"preview_id": token})["status"], "OK")


class LifecycleExemptionTest(_GateFixture):
    """Lifecycle ops carry no geometric intent and are confirm-exempt per mcp-tools §1.4."""

    def test_document_recompute_runs_with_no_confirm(self):
        self.assertEqual(
            self.registry.document_recompute(doc=self.handle)["status"], "OK"
        )

    def test_document_save_runs_with_no_confirm(self):
        path = os.path.join(tempfile.mkdtemp(prefix="FCB_TMP_gate_"), "gate.FCStd")
        try:
            self.assertEqual(
                self.registry.document_save(doc=self.handle, path=path)["status"], "OK"
            )
        finally:
            if os.path.exists(path):
                os.remove(path)
            os.rmdir(os.path.dirname(path))

    def test_document_undo_runs_with_no_confirm(self):
        confirm.set_auto_approve(True)
        self.pad(None)
        confirm.set_auto_approve(False)

        self.assertEqual(self.registry.document_undo(doc=self.handle)["status"], "OK")

    def test_document_list_runs_with_no_confirm(self):
        self.assertEqual(self.registry.document_list()["status"], "OK")


class PreviewExemptionTest(_GateFixture):
    """A preview must reach its own operation fail-closed: it is what mints the token."""

    def test_a_preview_runs_under_the_fail_closed_posture(self):
        self.assertFalse(confirm.auto_approve())

        structured = self.preview_pad()

        self.assertTrue(structured["preview_id"].startswith("fcb-preview:"))
        self.assertAlmostEqual(
            structured["diff"]["deltas"]["volume"]["delta"], PAD_VOLUME, places=6
        )

    def test_the_preview_leaves_the_live_document_untouched_and_still_gated(self):
        before = self.object_names()

        self.preview_pad()

        self.assertEqual(self.object_names(), before)
        self.assert_refused_without_touching_the_document(self.pad, None)

    def test_the_exemption_does_not_outlive_the_preview_call(self):
        self.preview_pad()

        self.assert_refused_without_touching_the_document(self.pad, None)

    def test_an_exemption_left_open_by_a_raising_op_is_still_released(self):
        with self.assertRaises(ValidationError):
            with confirm.preview_exemption():
                raise ValidationError("planted failure inside the exemption")

        self.assert_refused_without_touching_the_document(self.pad, None)


if __name__ == "__main__":
    unittest.main()
