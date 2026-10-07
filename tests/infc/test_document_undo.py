"""In-FreeCAD tests for ``document_undo`` (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Covers mutate -> undo -> fingerprint comparison, the
empty-stack and undo-unavailable refusals, the recompute the undo does not perform on its own,
and the did-not-restore report.

The FreeCAD semantics these tests pin were confirmed against the source and by live probe:
``Document::undo`` runs no recompute (``App/Document.cpp:174-225``), ``Document.undo()`` from
Python is guarded by ``getAvailableUndos()`` so an empty stack raises nothing and returns
``None`` (``App/DocumentPyImp.cpp:657-665``), and ``getAvailableUndos`` counts an open
transaction (``App/Document.cpp:792-795``) so ``UndoCount`` is only meaningful outside a bracket.
"""

import unittest

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.usecases import confirm, result_projection, transaction
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
from freecad_buddy.usecases.fingerprint import fingerprint

BOX_L = 10.0
BOX_W = 20.0
BOX_H = 30.0
BOX_VOLUME = BOX_L * BOX_W * BOX_H
RESIZED_L = 50.0
RESIZED_VOLUME = RESIZED_L * BOX_W * BOX_H


class _UndoFixture(unittest.TestCase):
    """A registry holding one document carrying a single box."""

    def setUp(self):
        self._posture = confirm.set_auto_approve(True)
        self.registry = DocumentRegistry()
        created = self.registry.document_create("document_undo")
        self.handle = created["structured_content"]["doc"]
        self.document = self.registry.with_document(self.handle, lambda h, d: d)

    def tearDown(self):
        confirm.set_auto_approve(self._posture)
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def add_box(self, name="Box"):
        box = self.document.addObject("Part::Box", name)
        box.Length, box.Width, box.Height = BOX_L, BOX_W, BOX_H
        self.document.recompute()
        return box

    def run_mutation(self, label, op):
        """Commit one mutation through the real AD-5 bracket and return its envelope."""
        document, envelope = transaction.run_mutation(self.document, self.handle, label, op)
        self.registry.rebind(self.handle, document)
        self.document = document
        return envelope

    def object_names(self):
        return sorted(obj.Name for obj in self.document.Objects)


class RefusalTest(_UndoFixture):
    def test_a_fresh_document_with_an_empty_stack_is_refused_not_reported_as_undone(self):
        """``Document.undo()`` is a silent no-op on an empty stack, so the count is checked."""
        self.assertEqual(self.document.UndoCount, 0)

        with self.assertRaises(ValidationError) as excinfo:
            self.registry.document_undo(doc=self.handle)

        self.assertIn("nothing to undo", str(excinfo.exception))

    def test_a_document_with_an_open_transaction_is_refused_rather_than_undoing_the_wrong_one(
        self,
    ):
        """An open transaction makes both readings name a transaction ``undo()`` will not revert.

        ``getAvailableUndoNames`` prepends the open transaction (``App/Document.cpp:318-330``)
        and ``getAvailableUndos`` counts it (``App/Document.cpp:791-794``), while ``undo()``
        commits it first and then reverts the transaction beneath it
        (``App/Document.cpp:188-195``). Undoing here would revert one transaction and report a
        different one, so the call is refused. This bridge always closes its own brackets; an
        open transaction comes from the GUI, a macro, or another workbench.
        """
        self.add_box()
        self.run_mutation("resize box", _resize_box)
        committed = self.object_names()

        self.document.openTransaction("someone else's edit")
        self.document.addObject("Part::Cylinder", "Cylinder")

        try:
            with self.assertRaises(ValidationError) as excinfo:
                self.registry.document_undo(doc=self.handle)

            self.assertIn("open transaction", str(excinfo.exception))
            self.assertNotEqual(
                self.object_names(),
                committed,
                "the refusal must leave the open transaction's work in place",
            )
        finally:
            self.document.abortTransaction()

    def test_a_document_reporting_undo_unavailable_is_refused_before_anything_is_claimed(self):
        """A document whose undo cannot be switched on would restore nothing, so it is named.

        ``document_undo`` calls ``shim.enable_undo`` first, which turns the stack back on where
        the build honours the setter, so the refusal is reached only where the write does not
        take. That is simulated here rather than skipped, because the refusal is the branch that
        keeps a no-op from being reported as a successful undo.
        """
        self.add_box()

        class _UndoRefusingDocument:
            """A document whose ``UndoMode`` write is accepted and then ignored."""

            UndoMode = 0

            def __init__(self, real):
                object.__setattr__(self, "_real", real)

            def __getattr__(self, name):
                return getattr(self._real, name)

            def __setattr__(self, name, value):
                if name != "UndoMode":
                    setattr(self._real, name, value)

        self.registry.rebind(self.handle, _UndoRefusingDocument(self.document))

        with self.assertRaises(ValidationError) as excinfo:
            self.registry.document_undo(doc=self.handle)

        self.assertIn("undo is unavailable", str(excinfo.exception))

    def test_switching_undo_off_discards_the_stack_so_the_undo_is_refused_not_faked(self):
        """Writing ``UndoMode = 0`` clears the recorded transactions; turning it back on does
        not bring them back, so the call must refuse rather than report an undo of nothing."""
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)
        self.assertEqual(self.document.UndoCount, 1)

        self.document.UndoMode = 0
        self.assertEqual(self.document.UndoMode, 0, "the build ignored the UndoMode write")
        self.assertEqual(self.document.UndoCount, 0, "the stack survived the mode write")

        with self.assertRaises(ValidationError) as excinfo:
            self.registry.document_undo(doc=self.handle)

        self.assertIn("nothing to undo", str(excinfo.exception))
        self.assertIn("Cyl", self.object_names(), "the refused undo removed the object anyway")

    def test_an_unknown_handle_is_refused(self):
        with self.assertRaises(ValidationError):
            self.registry.document_undo(doc="fcb-doc:missing")

    def test_a_missing_handle_is_refused(self):
        with self.assertRaises(ValidationError):
            self.registry.document_undo()

    def test_a_refused_undo_leaves_the_document_untouched(self):
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)
        before = fingerprint(self.document)["digest"]
        names_before = self.object_names()

        self.document.UndoMode = 0
        with self.assertRaises(ValidationError):
            self.registry.document_undo(doc=self.handle)
        self.document.UndoMode = 1

        self.assertEqual(fingerprint(self.document)["digest"], before)
        self.assertEqual(self.object_names(), names_before)


class UndoRestoresTest(_UndoFixture):
    def test_undoing_a_committed_mutation_removes_what_the_op_added(self):
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)
        self.assertIn("Cyl", self.object_names())

        envelope = self.registry.document_undo(doc=self.handle)

        self.assertEqual(envelope["status"], "OK")
        self.assertNotIn("Cyl", self.object_names())

    def test_the_undo_reports_the_transaction_it_undid_by_name(self):
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)

        structured = self.registry.document_undo(doc=self.handle)["structured_content"]

        self.assertEqual(structured["undone"], "buddy: add cylinder")

    def test_a_deeper_stack_names_the_newest_transaction_not_the_oldest(self):
        """``UndoNames`` is most-recent-first, so a depth-1 stack cannot tell the ends apart."""
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)
        self.run_mutation("resize box", _resize_box)
        self.assertEqual(self.document.UndoCount, 2)

        structured = self.registry.document_undo(doc=self.handle)["structured_content"]

        self.assertEqual(structured["undone"], "buddy: resize box")
        self.assertIn("Cyl", self.object_names(), "the older transaction was undone instead")

    def test_a_property_edit_is_restored_to_its_pre_mutation_value(self):
        box = self.add_box()
        self.run_mutation("resize box", _resize_box)
        self.assertAlmostEqual(box.Shape.Volume, RESIZED_VOLUME, places=6)

        self.registry.document_undo(doc=self.handle)

        self.assertAlmostEqual(self.document.getObject("Box").Shape.Volume, BOX_VOLUME, places=6)

    def test_the_undo_recomputes_so_the_reported_state_is_not_stale(self):
        """``Document::undo`` never recomputes; without one the shape read back is the old one."""
        self.add_box()
        self.run_mutation("resize box", _resize_box)

        self.registry.document_undo(doc=self.handle)

        box = self.document.getObject("Box")
        self.assertNotIn("Touched", list(box.State), "the undo left the object un-recomputed")
        self.assertAlmostEqual(box.Shape.Volume, BOX_VOLUME, places=6)

    def test_a_property_edit_undo_restores_the_exact_pre_mutation_fingerprint(self):
        self.add_box()
        pre_op = fingerprint(self.document)["digest"]
        self.run_mutation("resize box", _resize_box)
        self.assertNotEqual(fingerprint(self.document)["digest"], pre_op)

        structured = self.registry.document_undo(doc=self.handle, expect_fingerprint=pre_op)[
            "structured_content"
        ]

        self.assertTrue(
            structured["matches_pre_op"],
            f"undo did not restore the pre-op digest: {structured}",
        )
        self.assertEqual(structured["fingerprint_after"], pre_op)

    def test_the_undo_count_falls_by_one(self):
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)
        before = self.document.UndoCount

        structured = self.registry.document_undo(doc=self.handle)["structured_content"]

        self.assertEqual(structured["undo_count"], before - 1)


class ReportedComparisonTest(_UndoFixture):
    def test_without_a_pre_op_digest_the_comparison_is_reported_as_unknown(self):
        """This call never saw the pre-mutation state, so it must not claim a match."""
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)

        envelope = self.registry.document_undo(doc=self.handle)

        self.assertIsNone(envelope["structured_content"]["matches_pre_op"])
        self.assertIn("no pre-op digest supplied", envelope["text"])

    def test_both_digests_are_reported_alongside_the_verdict(self):
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)

        structured = self.registry.document_undo(doc=self.handle)["structured_content"]

        self.assertEqual(len(structured["fingerprint_before"]), 64)
        self.assertEqual(len(structured["fingerprint_after"]), 64)
        self.assertNotEqual(structured["fingerprint_before"], structured["fingerprint_after"])

    def test_a_digest_that_does_not_match_is_reported_false_never_claimed_restored(self):
        """A wrong expectation must produce a measured ``false``, not an exception or a claim.

        The string form compares bytes only, and a byte difference does not prove the undo
        failed, so the text states the measurement and never claims a failed restore.
        """
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)

        envelope = self.registry.document_undo(doc=self.handle, expect_fingerprint="0" * 64)
        structured = envelope["structured_content"]

        self.assertEqual(envelope["status"], "OK")
        self.assertIs(structured["matches_pre_op"], False)
        self.assertNotIn("did NOT restore", envelope["text"])
        self.assertIn("byte comparison", envelope["text"])
        self.assertIn("held no record", envelope["text"])
        self.assertNotIn("FingerprintRecord", envelope["text"])
        self.assertEqual(structured["fingerprint_after"], fingerprint(self.document)["digest"])

    def test_a_string_that_is_not_a_digest_is_refused_before_the_undo(self):
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)
        count = self.document.UndoCount
        for bad in ("abc", "z" * 64, "0" * 63, "A" * 64):
            with self.assertRaises(ValidationError, msg=repr(bad)) as caught:
                self.registry.document_undo(doc=self.handle, expect_fingerprint=bad)
            self.assertIn(repr(bad), str(caught.exception))

        self.assertEqual(self.document.UndoCount, count)
        self.assertIn("Cyl", self.object_names())

    def test_the_restored_object_set_is_reported_beside_the_digests(self):
        """A digest mismatch from a re-serialized shape is told apart from a missing object."""
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)

        structured = self.registry.document_undo(doc=self.handle)["structured_content"]

        self.assertEqual(structured["restored_objects"], ["Box"])

    def test_a_non_string_expectation_is_refused_rather_than_reported_as_not_restored(self):
        """A caller type error must not read as the undo having failed to restore.

        A non-string ``expect_fingerprint`` can never equal a digest, so accepting one would
        report ``matches_pre_op: false`` for what is a malformed request.
        """
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)
        before = fingerprint(self.document)["digest"]

        with self.assertRaises(ValidationError) as caught:
            self.registry.document_undo(doc=self.handle, expect_fingerprint=12345)

        self.assertIn("expect_fingerprint", str(caught.exception))
        self.assertEqual(fingerprint(self.document)["digest"], before)
        self.assertIn("Cyl", self.object_names())


class RecomputeSweepTest(_UndoFixture):
    def test_an_undo_whose_recompute_leaves_an_object_invalid_is_not_reported_ok(self):
        """The mandatory recompute is swept exactly as ``document_recompute`` sweeps its own.

        An undo that leaves the document broken must not be reported as an ``OK`` undo whose
        digest merely happened not to match the expectation. The broken object is added outside
        any transaction after the commit, so the undo leaves it in place rather than removing it.
        """
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)

        self.document.addObject("Part::Fillet", "BadFillet")
        self.document.recompute()
        self.assertIn("Invalid", list(self.document.getObject("BadFillet").State))

        envelope = self.registry.document_undo(doc=self.handle)

        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        names = [error["name"] for error in envelope["structured_content"]["errors"]]
        self.assertEqual(names, ["BadFillet"])
        self.assertIn("BadFillet", envelope["structured_content"]["restored_objects"])

    def test_a_clean_undo_reports_no_errors(self):
        """The sweep must not turn an ordinary successful undo into a failure."""
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)

        envelope = self.registry.document_undo(doc=self.handle)

        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(envelope["structured_content"]["errors"], [])


class UndoCountInsideABracketTest(_UndoFixture):
    def test_undo_count_overstates_by_one_inside_an_open_transaction(self):
        """``getAvailableUndos`` counts the open transaction, so the count is read outside one.

        The count is what ``document_undo`` refuses on, so a reading taken inside a bracket would
        see a transaction that has not been committed and could not be undone.
        """
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)
        committed = self.document.UndoCount
        self.assertEqual(committed, 1)

        self.document.openTransaction("probe: open")
        try:
            # The transaction is allocated on its first recorded change, not at openTransaction,
            # so an open but untouched bracket is not counted yet.
            self.assertEqual(self.document.UndoCount, committed)
            self.document.getObject("Box").Length = 42.0
            self.assertEqual(
                self.document.UndoCount,
                committed + 1,
                "an open transaction is not counted by this build",
            )
        finally:
            self.document.abortTransaction()
            self.document.recompute()

        self.assertEqual(self.document.UndoCount, committed)


def _add_cylinder(document):
    """A well-formed op: add a valid cylinder and report it as touched."""
    cylinder = document.addObject("Part::Cylinder", "Cyl")
    cylinder.Radius = 5.0
    cylinder.Height = 20.0
    return ["Cyl"]


def _resize_box(document):
    """A well-formed op: drive the existing box to a new length."""
    box = document.getObject("Box")
    box.Length = RESIZED_L
    return ["Box"]


if __name__ == "__main__":
    unittest.main()


class ExpectFingerprintRecordTest(_UndoFixture):
    """`expect_fingerprint` accepting a whole record, so restoration can be judged by geometry."""

    def test_a_record_expectation_matches_when_the_digest_matches(self):
        self.add_box()
        pre_op = fingerprint(self.document)
        self.run_mutation("resize box", _resize_box)

        envelope = self.registry.document_undo(doc=self.handle, expect_fingerprint=pre_op)

        self.assertTrue(envelope["structured_content"]["matches_pre_op"], envelope)
        self.assertIn("restored the pre-op state", envelope["text"])

    def test_a_record_expectation_matches_on_geometry_when_the_bytes_differ(self):
        """Consuming a sketch as a profile makes OCCT store the edge several ways.

        Undo removes the feature but leaves the extra representations, so the BRep bytes differ
        while volume, area, centre of mass, principal moments and inertia tensor are unchanged. A
        digest-only expectation reports that as a failed restore; a record expectation does not.
        """
        pre_op = self._pad_a_sketch()
        self.assertNotEqual(fingerprint(self.document)["digest"], pre_op["digest"])

        structured = self.registry.document_undo(doc=self.handle, expect_fingerprint=pre_op)[
            "structured_content"
        ]

        self.assertNotEqual(
            structured["fingerprint_after"],
            pre_op["digest"],
            "fixture must reproduce the byte divergence",
        )
        self.assertTrue(
            structured["matches_pre_op"],
            f"geometry was restored but the record expectation reported otherwise: {structured}",
        )

    def test_should_match_on_the_cached_record_when_a_published_digest_differs_in_bytes(self):
        """The bracket published the pre-op digest, so the undo compares its held record."""
        # Arrange
        published = self._pad_a_sketch(published=True)["digest"]

        # Act
        envelope = self.registry.document_undo(doc=self.handle, expect_fingerprint=published)

        # Assert
        self.assertNotEqual(envelope["structured_content"]["fingerprint_after"], published)
        self.assertIs(envelope["structured_content"]["matches_pre_op"], True, envelope)
        self.assertIn("restored the pre-op state", envelope["text"])
        self.assertNotIn("FingerprintRecord", envelope["text"])

    def test_should_compare_as_its_digest_when_the_expectation_is_a_wire_fingerprint(self):
        # Arrange
        wire = self._pad_a_sketch(published=True)

        # Act
        envelope = self.registry.document_undo(doc=self.handle, expect_fingerprint=wire)

        # Assert
        self.assertIs(envelope["structured_content"]["matches_pre_op"], True, envelope)

    def test_should_refuse_before_the_undo_when_a_wire_fingerprint_names_another_serializer(
        self,
    ):
        # Arrange
        wire = self._pad_a_sketch(published=True)
        count = self.document.UndoCount
        foreign = {**wire, "serializer": "someOtherTag"}

        # Act
        def act():
            return self.registry.document_undo(doc=self.handle, expect_fingerprint=foreign)

        # Assert
        with self.assertRaises(ValidationError) as caught:
            act()
        self.assertIn("serializer", str(caught.exception))
        self.assertEqual(self.document.UndoCount, count)

    def test_should_refuse_before_the_undo_when_a_wire_fingerprint_digest_is_missing_or_not_hex(
        self,
    ):
        # Arrange
        wire = self._pad_a_sketch(published=True)
        count = self.document.UndoCount
        malformed = {
            "missing digest": {"serializer": wire["serializer"]},
            "non-hex digest": {**wire, "digest": "z" * 64},
        }

        # Act
        def act(expected):
            return self.registry.document_undo(doc=self.handle, expect_fingerprint=expected)

        # Assert
        for label, expected in malformed.items():
            with self.assertRaises(ValidationError, msg=label):
                act(expected)
        self.assertEqual(self.document.UndoCount, count)

    def test_should_state_the_byte_measurement_when_no_record_is_held_for_the_digest(self):
        """No record is held for the digest, so only bytes are compared, and the text says so."""
        # Arrange
        pre_op = self._pad_a_sketch()
        result_projection._records.clear()

        # Act
        envelope = self.registry.document_undo(doc=self.handle, expect_fingerprint=pre_op["digest"])

        # Assert
        self.assertIs(envelope["structured_content"]["matches_pre_op"], False)
        self.assertNotIn("did NOT restore", envelope["text"])
        self.assertIn("byte comparison", envelope["text"])
        self.assertIn("held no record", envelope["text"])
        self.assertNotIn("FingerprintRecord", envelope["text"])

    def _pad_a_sketch(self, published: bool = False) -> dict:
        """Pad a circle sketch through the bracket; return the pre-pad record.

        ``published`` returns the ``fingerprint_before`` the mutation result carries instead.
        """
        body = self.document.addObject("PartDesign::Body", "Body")
        sketch = self.document.addObject("Sketcher::SketchObject", "Sketch")
        body.addObject(sketch)
        sketch.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 5.0), False)
        sketch.addConstraint(Sketcher.Constraint("Radius", 0, 5.0))
        # Post-verify grades the profile a pad consumes, so it must be fully constrained.
        sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
        self.document.recompute()
        pre_op = fingerprint(self.document)

        def _pad(document):
            pad = document.addObject("PartDesign::Pad", "Pad")
            document.getObject("Body").addObject(pad)
            pad.Profile = document.getObject("Sketch")
            pad.Length = 10.0
            return ["Pad"]

        envelope = self.run_mutation("pad the sketch", _pad)
        if published:
            return envelope["structured_content"]["mutation"]["fingerprint_before"]
        return pre_op

    def test_a_record_expectation_still_reports_a_real_geometry_change(self):
        """The cross-oracle must not turn every mismatch into a pass."""
        self.add_box()
        pre_op = fingerprint(self.document)
        self.run_mutation("add cylinder", _add_cylinder)

        envelope = self.registry.document_undo(
            doc=self.handle, expect_fingerprint=_mutated_record(pre_op)
        )

        self.assertFalse(envelope["structured_content"]["matches_pre_op"], envelope)
        self.assertIn("did NOT restore", envelope["text"])
        self.assertNotIn("byte comparison", envelope["text"])

    def test_a_malformed_expectation_is_still_refused(self):
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)
        for bad in (12345, ["not", "a", "record"], {"no": "objects key"}):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                self.registry.document_undo(doc=self.handle, expect_fingerprint=bad)

    def test_a_record_that_cannot_be_compared_is_refused_before_the_undo(self):
        """An incomparable record would read as ``matches_pre_op: false`` for a caller error."""
        self.add_box()
        self.run_mutation("add cylinder", _add_cylinder)
        good = fingerprint(self.document)
        count = self.document.UndoCount
        malformed = {
            "no serializer": {"objects": [], "digest": "0" * 64},
            "foreign serializer": {**good, "serializer": "someOtherTag"},
            "non-string digest": {**good, "digest": 0},
            "entry not an object": {**good, "objects": ["Box"]},
            "entry without massprops": {**good, "objects": [{"name": "Box"}]},
            "entry without name": {**good, "objects": [{"massprops": {}}]},
        }
        for label, bad in malformed.items():
            with self.assertRaises(ValidationError, msg=label):
                self.registry.document_undo(doc=self.handle, expect_fingerprint=bad)

        self.assertEqual(self.document.UndoCount, count)
        self.assertIn("Cyl", self.object_names())


def _mutated_record(record: dict) -> dict:
    """Return ``record`` with one object's volume changed, so it cannot match the document."""
    clone = {**record, "objects": [dict(entry) for entry in record["objects"]]}
    massprops = dict(clone["objects"][0]["massprops"])
    massprops["volume"] = massprops["volume"] + 1000.0
    clone["objects"][0] = {**clone["objects"][0], "massprops": massprops}
    clone["digest"] = "0" * 64
    return clone
