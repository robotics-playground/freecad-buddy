"""In-FreeCAD tests for the TNP guard's Layer-1 and Layer-2 audit passes (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. The fixtures build a PartDesign body whose pad carries
a real element map (measured: 30 entries); a ``Part::Box`` has ``ElementMapSize == 0`` and would
exercise neither layer. Covers each I/O-matrix row, the op-written-value exemption in both
directions, and the end-to-end rollback a ``DROPPED`` finding must produce.
"""

import glob
import os
import shutil
import tempfile
import unittest

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.usecases import shim, tnp_guard, transaction
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.fingerprint import fingerprint

SQUARE = 20.0
PAD_LENGTH = 10.0
FILLET_RADIUS = 1.0
FILLET_EDGES = ["Edge1", "Edge2", "Edge3", "Edge4"]

_SNAPSHOT_GLOB = os.path.join(tempfile.gettempdir(), "FCB_TMP_snap_*")


def _snapshot_leftovers():
    """Every reserved-prefix snapshot directory currently on disk."""
    return set(glob.glob(_SNAPSHOT_GLOB))


class _BodyFixture(unittest.TestCase):
    """A PartDesign body: sketch -> pad -> fillet, the shape that carries a real element map."""

    def setUp(self):
        if not shim.element_map_available():
            self.skipTest("element map unavailable; the guard reports UNSUPPORTED by design")
        self._snapshots_before = _snapshot_leftovers()
        self.registry = DocumentRegistry()
        created = self.registry.document_create("tnp_guard")
        self.handle = created["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))
        self._build()

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)
        # Remove only the snapshots this test minted. The unprovable-rollback case in
        # test_mutation_protocol deliberately keeps its own, so a global sweep would delete a
        # directory another suite still asserts on.
        for path in _snapshot_leftovers() - self._snapshots_before:
            shutil.rmtree(path, ignore_errors=True)

    def _build(self):
        self.body = self.document.addObject("PartDesign::Body", "Body")
        self.sketch = self.document.addObject("Sketcher::SketchObject", "Sketch")
        self.body.addObject(self.sketch)
        corners = [
            (0, 0, SQUARE, 0),
            (SQUARE, 0, SQUARE, SQUARE),
            (SQUARE, SQUARE, 0, SQUARE),
            (0, SQUARE, 0, 0),
        ]
        for x1, y1, x2, y2 in corners:
            self.sketch.addGeometry(
                Part.LineSegment(App.Vector(x1, y1, 0), App.Vector(x2, y2, 0)), False
            )
        for index in range(4):
            self.sketch.addConstraint(
                Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1)
            )
        self.document.recompute()

        self.pad = self.document.addObject("PartDesign::Pad", "Pad")
        self.body.addObject(self.pad)
        self.pad.Profile = self.sketch
        self.pad.Length = PAD_LENGTH
        self.document.recompute()

    def _origin_plane(self):
        """The body origin's XY plane. OriginFeatures runs axes 0-2, then planes 3-5."""
        planes = [f for f in self.body.Origin.OriginFeatures if f.TypeId == "App::Plane"]
        self.assertTrue(planes, "a PartDesign body origin exposes three App::Plane children")
        return planes[0]

    def _add_fillet(self, edges=None):
        fillet = self.document.addObject("PartDesign::Fillet", "Fillet")
        self.body.addObject(fillet)
        fillet.Base = (self.pad, list(edges if edges is not None else FILLET_EDGES))
        fillet.Radius = FILLET_RADIUS
        self.document.recompute()
        return fillet

    def _audit(self, snapshot, written=None):
        return tnp_guard.audit_references(self.document, snapshot, written)

    def _findings(self, audit, owner=None, prop=None):
        return [
            finding
            for finding in audit["findings"]
            if (owner is None or finding["owner"] == owner)
            and (prop is None or finding["prop"] == prop)
        ]


class SnapshotWitnessTest(_BodyFixture):
    def test_a_pad_carries_a_populated_element_map(self):
        self.assertGreater(self.pad.Shape.ElementMapSize, 0)

    def test_an_indexed_entry_resolves_its_mapped_shadow_at_capture_time(self):
        self._add_fillet()
        record = self._record("Fillet", "Base")

        self.assertEqual([e["indexed"] for e in record["entries"]], FILLET_EDGES)
        for entry in record["entries"]:
            self.assertTrue(entry["mapped"], "link properties store indexed names; resolve them")
            self.assertTrue(entry["mapped"].startswith(";") or "#" in entry["mapped"])

    def test_an_entry_captures_a_type_and_bounding_box_witness(self):
        self._add_fillet()
        entry = self._record("Fillet", "Base")["entries"][0]

        self.assertIsNotNone(entry["witness"])
        self.assertEqual(entry["witness"][0], "Edge")
        self.assertEqual(len(entry["witness"]), 7)

    def test_an_entry_captures_its_source_ancestry(self):
        self._add_fillet()
        entry = self._record("Fillet", "Base")["entries"][0]

        self.assertIsNotNone(entry["history"])
        self.assertEqual(len(entry["history"]), 2)
        self.assertIsInstance(entry["history"][0], int)
        self.assertIsInstance(entry["history"][1], str)

    def test_a_whole_object_link_captures_an_empty_entry_name(self):
        plane = self.document.addObject("PartDesign::Plane", "DatumPlane")
        self.body.addObject(plane)
        plane.AttachmentSupport = [(self._origin_plane(), ("",))]
        plane.MapMode = "FlatFace"
        self.document.recompute()

        record = self._record("DatumPlane", "AttachmentSupport")
        self.assertEqual(record["entries"][0]["indexed"], "")
        self.assertFalse(record["entries"][0]["missing"])

    def _record(self, owner, prop):
        records = [
            r
            for r in tnp_guard.snapshot_references(self.document)
            if r["owner"] == owner and r["prop"] == prop
        ]
        self.assertEqual(len(records), 1, f"expected exactly one {owner}.{prop} record")
        return records[0]


class LayerOneTest(_BodyFixture):
    def test_an_unchanged_document_audits_clean_with_every_entry_passing(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)

        audit = self._audit(snapshot)
        self.assertEqual(audit["status"], "CLEAN")
        self.assertEqual({f["verdict"] for f in audit["findings"]}, {"PASS"})

    def test_a_silently_dropped_entry_is_dropped_at_layer_one(self):
        fillet = self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        fillet.Base = (self.pad, FILLET_EDGES[:3])
        self.document.recompute()

        audit = self._audit(snapshot)
        findings = self._findings(audit, "Fillet", "Base")
        self.assertEqual(audit["status"], "FLAGGED")
        self.assertEqual([f["verdict"] for f in findings], ["DROPPED"])
        self.assertEqual(findings[0]["layer"], 1)
        self.assertIn("3", findings[0]["detail"])
        self.assertIn("4", findings[0]["detail"])

    def test_a_silent_drop_survives_a_layer_zero_only_audit_unflagged(self):
        """The FeatureDressUp trap: the fillet stays valid, so an error sweep sees nothing."""
        fillet = self._add_fillet()
        fillet.Base = (self.pad, FILLET_EDGES[:3])
        self.document.recompute()

        self.assertTrue(fillet.isValid())
        self.assertEqual(fillet.getStatusString(), "Valid")

    def test_a_gained_entry_is_flagged_rather_than_passing_silently(self):
        fillet = self._add_fillet(FILLET_EDGES[:3])
        snapshot = tnp_guard.snapshot_references(self.document)
        fillet.Base = (self.pad, FILLET_EDGES)
        self.document.recompute()

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        self.assertEqual([f["verdict"] for f in findings], ["REPOINTED"])

    def test_a_reference_whose_mapped_name_changed_is_repointed_at_layer_one(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        for record in snapshot:
            if record["owner"] == "Fillet":
                record["entries"][0]["mapped"] = ";planted;:Hff:7,E"

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        repointed = [f for f in findings if f["verdict"] == "REPOINTED"]
        self.assertEqual(len(repointed), 1)
        self.assertEqual(repointed[0]["layer"], 1)
        self.assertEqual(repointed[0]["mapped_before"], ";planted;:Hff:7,E")

    def test_a_reference_whose_witness_moved_is_repointed_at_layer_one(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        for record in snapshot:
            if record["owner"] == "Fillet":
                witness = record["entries"][0]["witness"]
                record["entries"][0]["witness"] = (witness[0],) + tuple(
                    value + 5.0 for value in witness[1:]
                )

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        repointed = [f for f in findings if f["verdict"] == "REPOINTED"]
        self.assertEqual(len(repointed), 1)
        self.assertEqual(repointed[0]["layer"], 1)
        self.assertIn("witness moved", repointed[0]["detail"])

    def test_a_witness_within_the_element_tolerance_is_not_a_move(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        for record in snapshot:
            if record["owner"] == "Fillet":
                witness = record["entries"][0]["witness"]
                record["entries"][0]["witness"] = (witness[0],) + tuple(
                    value + 1e-12 for value in witness[1:]
                )

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        self.assertEqual({f["verdict"] for f in findings}, {"PASS"})

    def test_a_nan_witness_component_reads_as_moved_rather_than_equal(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        for record in snapshot:
            if record["owner"] == "Fillet":
                witness = record["entries"][0]["witness"]
                record["entries"][0]["witness"] = (witness[0], float("nan")) + witness[2:]

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        self.assertIn("REPOINTED", [f["verdict"] for f in findings])

    def test_a_one_sided_witness_is_graded_rather_than_skipped(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        for record in snapshot:
            if record["owner"] == "Fillet":
                record["entries"][0]["witness"] = None

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        self.assertIn("REPOINTED", [f["verdict"] for f in findings])

    def test_a_reference_that_stops_resolving_is_broken_at_layer_one(self):
        fillet = self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        fillet.Base = (self.pad, FILLET_EDGES[:3] + ["Edge9999"])
        self.document.recompute()

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        layer_one = [f for f in findings if f["verdict"] == "BROKEN" and f["layer"] == 1]
        self.assertEqual(len(layer_one), 1)
        self.assertIn("Edge9999", layer_one[0]["detail"])
        self.assertIn("no longer resolves", layer_one[0]["detail"])

    def test_a_missing_marked_entry_is_reported_once_rather_than_by_both_layers(self):
        """FreeCAD marks an invalidated link '?Edge1'; Layer 0 owns that entry's verdict alone.

        Measured on this fixture: shrinking the pad leaves Edge1 and Edge2 missing while Edge3 and
        Edge4 survive. Only the missing pair belongs to Layer 0, so the assertion is that neither
        is re-graded above it — not that the record produces Layer-0 findings exclusively, which
        would also hold if a surviving entry's verdict were being suppressed.
        """
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        self.pad.Length = 1.0
        self.document.recompute()

        live = tnp_guard.snapshot_references(self.document)
        marked = [
            r for r in live if r["owner"] == "Fillet" and any(e["missing"] for e in r["entries"])
        ]
        self.assertTrue(marked, "shrinking the pad below the fillet radius invalidates its links")
        missing = [e["indexed"] for e in marked[0]["entries"] if e["missing"]]

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        for name in missing:
            layers = {f["layer"] for f in findings if name in f["detail"]}
            self.assertEqual(layers, {0}, f"{name} must be reported by Layer 0 alone")

    def test_a_missing_entry_does_not_suppress_a_repoint_on_the_same_record(self):
        """The Layer-0 skip is per entry, so a mixed record still has its re-point graded.

        Suppressing the whole record traded a double count for a missed finding: the missing entry
        is Layer 0's to report, but the entry beside it that moved is Layer 1's, and only a
        per-entry skip reports each once.
        """
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        self.pad.Length = 1.0
        self.document.recompute()

        live = tnp_guard.snapshot_references(self.document)
        marked = [
            r for r in live if r["owner"] == "Fillet" and any(e["missing"] for e in r["entries"])
        ]
        self.assertTrue(marked, "shrinking the pad below the fillet radius invalidates its links")
        surviving = [i for i, e in enumerate(marked[0]["entries"]) if not e["missing"]]
        self.assertTrue(surviving, "the fixture needs one entry that is not missing")

        # Move the witness of an entry FreeCAD did NOT mark missing, so the record carries both.
        index = surviving[0]
        for record in snapshot:
            if record["owner"] == "Fillet" and len(record["entries"]) > index:
                witness = record["entries"][index]["witness"]
                if witness is not None:
                    record["entries"][index]["witness"] = (witness[0],) + tuple(
                        value + 500.0 for value in witness[1:]
                    )

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        self.assertIn(0, {f["layer"] for f in findings}, "Layer 0 still reports the missing entry")
        self.assertIn(
            "REPOINTED",
            [f["verdict"] for f in findings],
            "the moved entry beside the missing one must still be graded",
        )

    def test_a_record_whose_every_entry_is_missing_is_left_to_layer_zero(self):
        # Grading the empty remainder would emit a "names no element" PASS for a record Layer 0
        # has already reported in full. Driven by marking every live entry missing, because the
        # pad-shrink fixture invalidates only two of the fillet's four edges.
        fillet = self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        self.pad.Length = 1.0
        self.document.recompute()

        real_snapshot = tnp_guard.snapshot_references

        def all_missing(document):
            records = real_snapshot(document)
            for record in records:
                if record["owner"] == fillet.Name:
                    for entry in record["entries"]:
                        entry["missing"] = True
            return records

        tnp_guard.snapshot_references = all_missing
        try:
            findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        finally:
            tnp_guard.snapshot_references = real_snapshot

        self.assertEqual({f["layer"] for f in findings}, {0})
        self.assertNotIn("PASS", [f["verdict"] for f in findings])

    def test_a_deleted_snapshot_owner_is_broken_at_layer_one(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        self.document.removeObject("Fillet")
        self.document.recompute()

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        self.assertEqual([f["verdict"] for f in findings], ["BROKEN"])
        self.assertEqual(findings[0]["layer"], 1)
        self.assertIn("no longer present", findings[0]["detail"])

    def test_an_element_map_version_bump_re_baselines_without_failing(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        for record in snapshot:
            if record["owner"] == "Fillet":
                record["element_map_version"] = "0.0.0"

        audit = self._audit(snapshot)
        findings = self._findings(audit, "Fillet", "Base")
        self.assertIn("RE_BASELINED", [f["verdict"] for f in findings])
        self.assertEqual(audit["status"], "CLEAN")

    def test_a_re_baseline_annotates_the_record_without_hiding_a_concurrent_drop(self):
        fillet = self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        for record in snapshot:
            if record["owner"] == "Fillet":
                record["element_map_version"] = "0.0.0"
        fillet.Base = (self.pad, FILLET_EDGES[:1])
        self.document.recompute()

        audit = self._audit(snapshot)
        verdicts = [f["verdict"] for f in self._findings(audit, "Fillet", "Base")]
        self.assertIn("RE_BASELINED", verdicts)
        self.assertIn(
            "DROPPED",
            verdicts,
            "a version bump annotates the record; it must not suppress the count check",
        )
        self.assertEqual(audit["status"], "FLAGGED")


class WrittenValueExemptionTest(_BodyFixture):
    def test_a_drop_the_op_did_not_write_is_dropped_even_when_the_op_wrote_the_property(self):
        fillet = self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        written = tnp_guard.snapshot_references(self.document)

        fillet.Base = (self.pad, FILLET_EDGES[:3])
        self.document.recompute()

        findings = self._findings(self._audit(snapshot, written), "Fillet", "Base")
        self.assertEqual(
            [f["verdict"] for f in findings],
            ["DROPPED"],
            "a value the op did not write must not be exempted by ownership",
        )

    def test_an_intended_removal_the_op_itself_wrote_passes(self):
        fillet = self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)

        fillet.Base = (self.pad, FILLET_EDGES[:3])
        written = tnp_guard.snapshot_references(self.document)
        self.document.recompute()

        findings = self._findings(self._audit(snapshot, written), "Fillet", "Base")
        self.assertEqual({f["verdict"] for f in findings}, {"PASS"})
        self.assertEqual(len(findings), 3, "one finding per surviving entry")

    def test_an_op_written_value_that_freecad_then_changed_is_not_exempt(self):
        fillet = self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)

        fillet.Base = (self.pad, FILLET_EDGES[:3])
        written = tnp_guard.snapshot_references(self.document)
        fillet.Base = (self.pad, FILLET_EDGES[:2])
        self.document.recompute()

        findings = self._findings(self._audit(snapshot, written), "Fillet", "Base")
        self.assertEqual([f["verdict"] for f in findings], ["DROPPED"])

    def test_the_exemption_never_covers_a_reference_that_stopped_resolving(self):
        """The layer is asserted, not merely the verdict.

        An op-written entry naming a missing element also invalidates its owner, so Layer 0
        reports a ``BROKEN`` for the same property. A verdict-only assertion would pass even with
        the per-entry resolution check removed from the exempt path.
        """
        fillet = self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)

        fillet.Base = (self.pad, ["Edge1", "Edge2", "Edge9999"])
        written = tnp_guard.snapshot_references(self.document)
        self.document.recompute()

        findings = self._findings(self._audit(snapshot, written), "Fillet", "Base")
        layer_one_broken = [f for f in findings if f["verdict"] == "BROKEN" and f["layer"] == 1]
        self.assertEqual(
            len(layer_one_broken),
            1,
            "an op-written reference that does not resolve is still graded BROKEN by Layer 1",
        )
        self.assertIn("Edge9999", layer_one_broken[0]["detail"])

    def test_the_exemption_never_covers_a_witness_that_moved_under_an_op_written_name(self):
        """The op writes three edge names; the geometry they bind to then moves 99 mm."""
        fillet = self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)

        fillet.Base = (self.pad, FILLET_EDGES[:3])
        written = tnp_guard.snapshot_references(self.document)
        for record in written:
            if record["owner"] == "Fillet":
                for entry in record["entries"]:
                    witness = entry["witness"]
                    entry["witness"] = (witness[0],) + tuple(v + 99.0 for v in witness[1:])
        self.document.recompute()

        findings = self._findings(self._audit(snapshot, written), "Fillet", "Base")
        repointed = [f for f in findings if f["verdict"] == "REPOINTED"]
        self.assertEqual(
            len(repointed),
            3,
            "the exemption excuses the entry count only; every entry still runs the diff",
        )
        self.assertEqual({f["layer"] for f in repointed}, {1})
        self.assertIn("witness moved", repointed[0]["detail"])

    def test_the_exemption_never_covers_a_mapped_name_that_changed(self):
        fillet = self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)

        fillet.Base = (self.pad, FILLET_EDGES[:3])
        written = tnp_guard.snapshot_references(self.document)
        for record in written:
            if record["owner"] == "Fillet":
                record["entries"][0]["mapped"] = ";planted;:Hff:7,E"
        self.document.recompute()

        findings = self._findings(self._audit(snapshot, written), "Fillet", "Base")
        repointed = [f for f in findings if f["verdict"] == "REPOINTED"]
        self.assertEqual(len(repointed), 1)
        self.assertEqual(repointed[0]["layer"], 1)
        self.assertIn("maps to a different element", repointed[0]["detail"])

    def test_the_exemption_never_covers_a_divergent_ancestry_at_layer_two(self):
        fillet = self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)

        fillet.Base = (self.pad, FILLET_EDGES[:3])
        written = tnp_guard.snapshot_references(self.document)
        for record in written:
            if record["owner"] == "Fillet":
                record["entries"][0]["history"] = (999999, "planted;SKT")
        self.document.recompute()

        findings = self._findings(self._audit(snapshot, written), "Fillet", "Base")
        repointed = [f for f in findings if f["verdict"] == "REPOINTED"]
        self.assertEqual(len(repointed), 1)
        self.assertEqual(repointed[0]["layer"], 2)
        self.assertIn("different source", repointed[0]["detail"])


class LayerTwoTest(_BodyFixture):
    def test_an_ambiguous_entry_with_matching_ancestry_passes_at_layer_two(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        self.assertEqual({f["verdict"] for f in findings}, {"PASS"})
        self.assertEqual({f["layer"] for f in findings}, {2})

    def test_an_ambiguous_entry_with_divergent_ancestry_is_repointed_at_layer_two(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        for record in snapshot:
            if record["owner"] == "Fillet":
                record["entries"][0]["history"] = (999999, "planted;SKT")

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        repointed = [f for f in findings if f["verdict"] == "REPOINTED"]
        self.assertEqual(len(repointed), 1)
        self.assertEqual(repointed[0]["layer"], 2)
        self.assertIn("different source", repointed[0]["detail"])

    def test_an_absent_history_abstains_and_leaves_the_layer_one_verdict_standing(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        for record in snapshot:
            if record["owner"] == "Fillet":
                record["entries"][0]["history"] = None

        findings = self._findings(self._audit(snapshot), "Fillet", "Base")
        self.assertEqual({f["verdict"] for f in findings}, {"PASS"})

    def test_layer_two_compares_only_the_source_pair_not_the_intermediates(self):
        """getElementHistory's third member is rebuild-order sensitive, so only the pair counts."""
        self._add_fillet()
        entry = [r for r in tnp_guard.snapshot_references(self.document) if r["owner"] == "Fillet"][
            0
        ]["entries"][0]
        raw = self.pad.Shape.getElementHistory(entry["mapped"])

        self.assertEqual(len(raw), 3)
        self.assertEqual(entry["history"], (raw[0], raw[1]))

    def test_a_no_op_recompute_leaves_every_reference_passing(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        self.document.recompute()

        audit = self._audit(snapshot)
        self.assertEqual(audit["status"], "CLEAN")


class NoMappedHalfTest(_BodyFixture):
    def test_a_box_reference_with_no_element_map_is_never_broken_for_the_missing_mapped_name(self):
        box = self.document.addObject("Part::Box", "Box")
        box.Length = box.Width = box.Height = 5.0
        self.document.recompute()
        sketch = self.document.addObject("Sketcher::SketchObject", "BoxSketch")
        sketch.AttachmentSupport = [(box, ("Face1",))]
        sketch.MapMode = "FlatFace"
        self.document.recompute()

        self.assertEqual(box.Shape.ElementMapSize, 0)
        snapshot = tnp_guard.snapshot_references(self.document)
        record = [r for r in snapshot if r["owner"] == "BoxSketch"][0]
        self.assertIsNone(record["entries"][0]["mapped"])

        findings = self._findings(self._audit(snapshot), "BoxSketch", "AttachmentSupport")
        self.assertEqual([f["verdict"] for f in findings], ["PASS"])


class TargetIdentityTest(_BodyFixture):
    def _two_boxes(self):
        first = self.document.addObject("Part::Box", "BoxA")
        second = self.document.addObject("Part::Box", "BoxB")
        for box in (first, second):
            box.Length = box.Width = box.Height = 5.0
        self.document.recompute()
        return first, second

    def test_a_link_repointed_to_a_different_object_is_flagged(self):
        """Two boxes with identical geometry have no mapped name and no history to tell apart."""
        first, second = self._two_boxes()
        sketch = self.document.addObject("Sketcher::SketchObject", "Attached")
        sketch.AttachmentSupport = [(first, ("Face1",))]
        sketch.MapMode = "FlatFace"
        self.document.recompute()
        snapshot = tnp_guard.snapshot_references(self.document)

        sketch.AttachmentSupport = [(second, ("Face1",))]
        self.document.recompute()

        findings = self._findings(self._audit(snapshot), "Attached", "AttachmentSupport")
        self.assertEqual([f["verdict"] for f in findings], ["REPOINTED"])
        self.assertEqual(findings[0]["layer"], 1)
        self.assertIn("different object", findings[0]["detail"])

    def test_a_multi_target_link_property_audits_clean_when_nothing_changed(self):
        """A PropertyLinkSubList emits one record per target, so identity must include it."""
        first, second = self._two_boxes()
        sketch = self.document.addObject("Sketcher::SketchObject", "MultiAttached")
        sketch.AttachmentSupport = [(first, ("Face1",)), (second, ("Face2",))]
        self.document.recompute()

        records = [
            r
            for r in tnp_guard.snapshot_references(self.document)
            if r["owner"] == "MultiAttached" and r["prop"] == "AttachmentSupport"
        ]
        self.assertEqual(
            [r["target"] for r in records],
            ["BoxA", "BoxB"],
            "one record per (target, subs) pair",
        )

        audit = self._audit(records)
        findings = self._findings(audit, "MultiAttached", "AttachmentSupport")
        self.assertEqual(
            [f["verdict"] for f in findings],
            ["PASS", "PASS"],
            "an unchanged multi-target link must grade every target, and none REPOINTED",
        )

    def test_a_reordered_multi_target_link_pairs_each_target_with_itself(self):
        """Both references survive the reorder, so pairing by position would flag two false
        re-points; pairing by target reports neither."""
        first, second = self._two_boxes()
        second.Length = second.Width = second.Height = 12.0
        second.Placement.Base = App.Vector(40, 0, 0)
        sketch = self.document.addObject("Sketcher::SketchObject", "MultiAttached")
        sketch.AttachmentSupport = [(first, ("Face1",)), (second, ("Face1",))]
        self.document.recompute()
        snapshot = [
            r for r in tnp_guard.snapshot_references(self.document) if r["owner"] == "MultiAttached"
        ]

        sketch.AttachmentSupport = [(second, ("Face1",)), (first, ("Face1",))]
        self.document.recompute()

        audit = self._audit(snapshot)
        findings = self._findings(audit, "MultiAttached", "AttachmentSupport")
        self.assertEqual(
            [f["verdict"] for f in findings],
            ["PASS", "PASS"],
            "reordering the targets of a link changes no reference",
        )
        self.assertEqual(audit["status"], "CLEAN")

    def test_a_multi_target_link_grades_each_target_against_its_own_snapshot(self):
        first, second = self._two_boxes()
        third = self.document.addObject("Part::Box", "BoxC")
        third.Length = third.Width = third.Height = 5.0
        sketch = self.document.addObject("Sketcher::SketchObject", "MultiAttached")
        sketch.AttachmentSupport = [(first, ("Face1",)), (second, ("Face2",))]
        self.document.recompute()
        snapshot = [
            r for r in tnp_guard.snapshot_references(self.document) if r["owner"] == "MultiAttached"
        ]

        sketch.AttachmentSupport = [(first, ("Face1",)), (third, ("Face2",))]
        self.document.recompute()

        findings = self._findings(self._audit(snapshot), "MultiAttached", "AttachmentSupport")
        self.assertEqual([f["verdict"] for f in findings], ["PASS", "REPOINTED"])
        self.assertIn("BoxB -> BoxC", findings[1]["detail"])


class WholeObjectLinkTest(_BodyFixture):
    def test_a_whole_object_link_passes_before_the_resolution_check(self):
        plane = self.document.addObject("PartDesign::Plane", "DatumPlane")
        self.body.addObject(plane)
        plane.AttachmentSupport = [(self._origin_plane(), ("",))]
        plane.MapMode = "FlatFace"
        self.document.recompute()
        snapshot = tnp_guard.snapshot_references(self.document)

        audit = self._audit(snapshot)
        findings = self._findings(audit, "DatumPlane", "AttachmentSupport")
        self.assertEqual([f["verdict"] for f in findings], ["PASS"])
        self.assertIn("names no element", findings[0]["detail"])


class CapabilityGateTest(_BodyFixture):
    def test_an_unavailable_element_map_reports_unsupported_with_no_pass_finding(self):
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)

        probe = shim.element_map_available
        shim.element_map_available = lambda: False
        try:
            audit = self._audit(snapshot)
        finally:
            shim.element_map_available = probe

        self.assertEqual(audit["status"], "UNSUPPORTED")
        self.assertTrue(audit["findings"])
        self.assertNotIn("PASS", [f["verdict"] for f in audit["findings"]])


class WitnessReadFailureTest(_BodyFixture):
    def test_an_unreadable_witness_yields_no_witness_rather_than_raising(self):
        self.assertIsNone(tnp_guard._witness(object()))

    def test_an_unresolvable_element_yields_none_rather_than_raising(self):
        self.assertIsNone(tnp_guard._resolve_element(self.pad.Shape, "Edge9999"))

    def test_a_target_with_no_shape_captures_an_unresolved_entry(self):
        entry = tnp_guard._capture_entry(object(), "Edge1")
        self.assertEqual(entry["indexed"], "Edge1")
        self.assertIsNone(entry["witness"])
        self.assertIsNone(entry["history"])

    def test_hash_code_is_never_the_witness(self):
        """ShapeMapHasher.h hashes the TShape pointer plus Location, so it moves on rebuild."""
        source = tnp_guard._witness.__code__.co_names
        self.assertNotIn("hashCode", source)


class _DroppingDocument:
    """Delegates to a real document, dropping one fillet edge on the first ``recompute``.

    Stands in for ``FeatureDressUp::getContinuousEdges``, which erases a requested edge with no
    error and no return value. The drop lands in the window ``run_mutation`` opens between the
    op's post-op capture and ``post_verify``, so the op itself never writes the shorter list.
    """

    def __init__(self, document, owner, value):
        object.__setattr__(self, "_document", document)
        object.__setattr__(self, "_owner", owner)
        object.__setattr__(self, "_value", value)
        object.__setattr__(self, "_calls", 0)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_document"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_document"), name, value)

    def recompute(self, *args, **kwargs):
        document = object.__getattribute__(self, "_document")
        result = document.recompute(*args, **kwargs)
        calls = object.__getattribute__(self, "_calls") + 1
        object.__setattr__(self, "_calls", calls)
        if calls == 1:
            owner = document.getObject(object.__getattribute__(self, "_owner"))
            owner.Base = object.__getattribute__(self, "_value")
        return result


class MutationRollbackTest(_BodyFixture):
    """A DROPPED finding must fail the mutation, roll it back, and say why."""

    def _rebind(self):
        created = self.registry.document_create("tnp_rollback")
        handle = created["structured_content"]["doc"]
        self.registry.rebind(handle, self.document)
        return handle

    def test_a_drop_the_op_never_wrote_rolls_the_mutation_back_with_a_proven_restore(self):
        self._add_fillet()
        handle = self._rebind()
        before = fingerprint(self.document)
        dropping = _DroppingDocument(self.document, "Fillet", (self.pad, list(FILLET_EDGES[:3])))

        def edit_the_radius(document):
            document.getObject("Fillet").Radius = FILLET_RADIUS + 0.5
            return ["Fillet"]

        _, envelope = transaction.run_mutation(
            dropping, handle, "planted silent drop", edit_the_radius
        )

        self.assertEqual(envelope["status"], "SPEC_FAILED")
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertIsNotNone(block["rollback_proven"])
        self.assertEqual(block["fingerprint_after"]["digest"], before["digest"])
        explanation = block["post_verify"]["explanation"]
        self.assertIn("Fillet", explanation)
        self.assertIn("Base", explanation)
        self.assertIn("DROPPED", explanation)

    def test_an_op_that_writes_the_shorter_list_itself_commits(self):
        self._add_fillet()
        handle = self._rebind()

        def remove_an_edge(document):
            document.getObject("Fillet").Base = (self.pad, list(FILLET_EDGES[:3]))
            return ["Fillet"]

        _, envelope = transaction.run_mutation(
            self.document, handle, "intended removal", remove_an_edge
        )

        audit = envelope["structured_content"]["mutation"]["post_verify"]["tnp_audit"]
        flagged = [
            f
            for f in audit["findings"]
            if f["owner"] == "Fillet" and f["verdict"] not in ("PASS", "RE_BASELINED")
        ]
        self.assertEqual(flagged, [], "the op wrote the shorter list, so it is the intended target")
        self.assertEqual(envelope["status"], "OK")
