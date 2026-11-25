"""In-FreeCAD tests for the TNP guard's Layer-1 and Layer-2 audit passes (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. The fixtures build a PartDesign body whose pad carries
a real element map (measured: 30 entries); a ``Part::Box`` has ``ElementMapSize == 0`` and would
exercise neither layer. Covers each I/O-matrix row, the op-written-value exemption in both
directions, and the end-to-end rollback a ``DROPPED`` finding must produce.
"""

import glob
import os
import shutil
import unittest

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.usecases import confirm, shim, sketches, tnp_guard, transaction
from freecad_buddy.usecases.documents import DocumentRegistry, temp_dir
from freecad_buddy.usecases.fingerprint import fingerprint

SQUARE = 20.0
PAD_LENGTH = 10.0
FILLET_RADIUS = 1.0
FILLET_EDGES = ["Edge1", "Edge2", "Edge3", "Edge4"]

# Snapshots live in the session workdir, not the OS temp directory (AD-25). Globbing the OS temp
# directory here would now match nothing and this leak check would pass without measuring.
_SNAPSHOT_GLOB = os.path.join(temp_dir(), "FCB_TMP_snap_*")


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

    def test_a_sketch_axis_reference_passes_rather_than_reading_as_unresolvable(self):
        """A sketch axis is a pseudo-element, so ``getElement`` cannot resolve it.

        ``PartDesign::Pad.ReferenceAxis`` normally holds ``(Sketch, ['N_Axis'])``, which
        ``FeatureSketchBased.cpp:1322-1340`` resolves through ``getAxis``, never ``getElement``.
        Grading it by shape resolution reported ``BROKEN`` on a healthy, ``Up-to-date`` Pad, and
        because ``post_verify`` fails on a flagged audit that false positive rolled back correct
        mutations on any document whose pad carries a reference axis.
        """
        self.pad.ReferenceAxis = (self.sketch, ["N_Axis"])
        self.document.recompute()
        self.assertTrue(self.pad.isValid())
        self.assertEqual(list(self.pad.State), ["Up-to-date"])

        snapshot = tnp_guard.snapshot_references(self.document)
        findings = self._findings(self._audit(snapshot), "Pad", "ReferenceAxis")

        self.assertTrue(findings, "the reference must still be graded, not skipped entirely")
        self.assertEqual({f["verdict"] for f in findings}, {"PASS"})

    def test_every_named_sketch_axis_form_is_exempt_from_shape_resolution(self):
        """The exemption covers all three named axes, not just the N_Axis that exposed it.

        Asserted on the predicate rather than on an audit verdict, because padding along the
        in-plane V/H axes is geometrically degenerate: FreeCAD fails the recompute and Layer 0
        reports that genuine error, which would mask what this test is about. ``Axis<N>`` is
        covered by ``test_an_indexed_construction_axis_is_exempt_when_the_sketch_has_one``.
        """
        record = {"owner": "Pad", "prop": "ReferenceAxis", "target": self.sketch.Name}
        for axis in ("V_Axis", "H_Axis", "N_Axis"):
            with self.subTest(axis=axis):
                self.assertIsNone(
                    tnp_guard._resolve_element(self.sketch.Shape, axis),
                    f"{axis} must be unresolvable, or this test proves nothing",
                )
                self.assertTrue(tnp_guard._is_sketch_axis(self.document, record, axis))

    def test_an_indexed_construction_axis_is_exempt_when_the_sketch_has_one(self):
        # FeatureSketchBased.cpp:1334-1340 also accepts "Axis<N>" for the sketch's construction
        # axes. The predicate is asserted directly: this fixture's sketch carries no construction
        # geometry, so FreeCAD rejects the reference itself with "Invalid shape name Axis0".
        record = {"owner": "Pad", "prop": "ReferenceAxis", "target": self.sketch.Name}

        self.assertTrue(tnp_guard._is_sketch_axis(self.document, record, "Axis0"))
        self.assertTrue(tnp_guard._is_sketch_axis(self.document, record, "Axis12"))
        self.assertFalse(tnp_guard._is_sketch_axis(self.document, record, "AxisFoo"))
        self.assertFalse(tnp_guard._is_sketch_axis(self.document, record, "Axis"))

    def test_an_axis_name_on_a_non_sketch_target_is_still_resolved(self):
        # The exemption is scoped to Sketcher:: targets; an element that merely shares the name
        # on another object must still be graded, or the fix would blind the guard.
        record = {"owner": "Pad", "prop": "ReferenceAxis", "target": self.pad.Name}

        self.assertFalse(tnp_guard._is_sketch_axis(self.document, record, "N_Axis"))

    def test_an_unresolvable_non_axis_subelement_on_a_sketch_is_still_broken(self):
        # The exemption is scoped to the axis forms; an ordinary element name that stops
        # resolving must still be caught, or the fix would blind the guard on sketch targets.
        record = {"owner": "Pad", "prop": "ReferenceAxis", "target": self.sketch.Name}

        self.assertFalse(tnp_guard._is_sketch_axis(self.document, record, "Edge9999"))

    def test_a_reference_whose_target_object_is_gone_is_broken_rather_than_passing(self):
        """The resolution check used to read a missing target as "nothing to compare".

        ``_grade_resolution`` resolved the target and only graded when a shape came back, so a
        record whose target name is unchanged but whose object no longer exists produced no
        finding at all. Whether anything else caught it depended on FreeCAD marking the owner
        invalid, which for a ``FeatureDressUp`` is the silent case this guard exists to cover.
        """
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        record = next(r for r in snapshot if r["owner"] == "Fillet")
        absent = {**record, "target": "NoSuchObject"}
        self.assertIsNone(self.document.getObject("NoSuchObject"))

        finding = tnp_guard._grade_resolution(self.document, absent, record["entries"][0])

        self.assertIsNotNone(finding, "a reference to a deleted object must not grade PASS")
        self.assertEqual(finding["verdict"], "BROKEN")
        self.assertEqual(finding["layer"], 1)
        self.assertIn("no longer in the document", finding["detail"])

    def test_a_target_that_is_present_but_shapeless_stays_unchecked(self):
        # A shapeless object has no elements to resolve against and never did, so the widened
        # guard must not turn that into a BROKEN verdict.
        self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        record = next(r for r in snapshot if r["owner"] == "Fillet")
        shapeless = self.document.addObject("App::FeaturePython", "Shapeless")
        self.document.recompute()
        self.assertIsNone(getattr(shapeless, "Shape", None))

        finding = tnp_guard._grade_resolution(
            self.document, {**record, "target": "Shapeless"}, record["entries"][0]
        )

        self.assertIsNone(finding)

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


class _ReadRecorder:
    """Delegates to a real object, recording the name of every attribute read through it."""

    def __init__(self, inner):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "reads", [])

    def __getattr__(self, name):
        object.__getattribute__(self, "reads").append(name)
        return getattr(object.__getattribute__(self, "_inner"), name)


class PropertyReadTest(_BodyFixture):
    def test_should_never_read_a_non_link_value_when_snapshotting_references(self):
        # Arrange
        fillet = self._add_fillet()
        recorder = _ReadRecorder(fillet)
        document = type("_OneObjectDocument", (), {"Objects": [recorder]})()
        reference_types = tnp_guard._LINK_SUB_TYPES | {tnp_guard._EXPRESSION_ENGINE_TYPE}
        # The owner's ElementMapVersion is read once one of its link properties passes the filter.
        expected_non_reference_reads = {"ElementMapVersion"}

        # Act
        records = tnp_guard.snapshot_references(document)

        # Assert
        self.assertIn("Base", [record["prop"] for record in records])
        non_reference_reads = {
            name
            for name in recorder.reads
            if name in fillet.PropertiesList
            and fillet.getTypeIdOfProperty(name) not in reference_types
        }
        self.assertNotIn("Shape", recorder.reads)
        self.assertLessEqual(non_reference_reads, expected_non_reference_reads)


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


class ExpressionBindingTest(unittest.TestCase):
    """An ``ExpressionEngine`` binding is a reference record keyed by its property path."""

    BOUND_RECORD = "ExpressionEngine[Length]"
    REMOVED = {("Box", BOUND_RECORD)}

    def setUp(self):
        self.document = App.newDocument("tnp_expression")
        varset = self.document.addObject("App::VarSet", "Params")
        varset.addProperty("App::PropertyLength", "width", "Parameters", "")
        varset.width = 12.0
        self.box = self.document.addObject("Part::Box", "Box")
        self.box.setExpression("Length", "Params.width")
        self.document.recompute()

    def tearDown(self):
        App.closeDocument(self.document.Name)

    def _verdicts(self, audit):
        return [f["verdict"] for f in audit["findings"] if f["prop"] == self.BOUND_RECORD]

    def test_Should_pass_When_the_op_reports_it_removed_the_binding(self):
        # Arrange
        snapshot = tnp_guard.snapshot_references(self.document)
        self.box.setExpression("Length", None)
        written = tnp_guard.snapshot_references(self.document)
        self.document.recompute()

        # Act
        audit = tnp_guard.audit_references(
            self.document, snapshot, written, removed_bindings=self.REMOVED
        )

        # Assert
        self.assertEqual(audit["status"], "CLEAN")
        self.assertEqual(self._verdicts(audit), ["PASS"])

    def test_Should_flag_broken_When_the_op_removed_a_binding_without_reporting_it(self):
        # Arrange
        snapshot = tnp_guard.snapshot_references(self.document)
        self.box.setExpression("Length", None)
        written = tnp_guard.snapshot_references(self.document)
        self.document.recompute()

        # Act
        audit = tnp_guard.audit_references(self.document, snapshot, written)

        # Assert
        self.assertEqual(self._verdicts(audit), ["BROKEN"])

    def test_Should_flag_broken_When_a_binding_vanishes_after_the_op_wrote_it(self):
        # Arrange
        snapshot = tnp_guard.snapshot_references(self.document)
        written = tnp_guard.snapshot_references(self.document)
        self.box.setExpression("Length", None)
        self.document.recompute()

        # Act
        audit = tnp_guard.audit_references(
            self.document, snapshot, written, removed_bindings=self.REMOVED
        )

        # Assert
        self.assertEqual(audit["status"], "FLAGGED")
        self.assertEqual(self._verdicts(audit), ["BROKEN"])

    def test_Should_flag_broken_When_no_written_reading_is_given(self):
        # Arrange
        snapshot = tnp_guard.snapshot_references(self.document)
        self.box.setExpression("Length", None)
        self.document.recompute()

        # Act
        audit = tnp_guard.audit_references(self.document, snapshot, removed_bindings=self.REMOVED)

        # Assert
        self.assertEqual(self._verdicts(audit), ["BROKEN"])

    def test_Should_flag_broken_When_the_owner_of_the_binding_is_removed(self):
        # Arrange
        snapshot = tnp_guard.snapshot_references(self.document)
        self.document.removeObject("Box")
        written = tnp_guard.snapshot_references(self.document)
        self.document.recompute()

        # Act
        audit = tnp_guard.audit_references(
            self.document, snapshot, written, removed_bindings=self.REMOVED
        )

        # Assert
        self.assertEqual(self._verdicts(audit), ["BROKEN"])

    def test_Should_stay_clean_When_a_binding_is_added_or_replaced(self):
        # Arrange
        snapshot = tnp_guard.snapshot_references(self.document)
        self.box.setExpression("Length", "Params.width * 2")
        self.box.setExpression("Height", "Params.width")
        written = tnp_guard.snapshot_references(self.document)
        self.document.recompute()

        # Act
        audit = tnp_guard.audit_references(self.document, snapshot, written)

        # Assert
        self.assertEqual(audit["status"], "CLEAN")


def _plane_name(shape, axis, value):
    """The name of the face of ``shape`` that lies in the plane ``coordinate[axis] == value``."""
    for index, face in enumerate(shape.Faces, start=1):
        box = face.BoundBox
        low = (box.XMin, box.YMin, box.ZMin)[axis]
        high = (box.XMax, box.YMax, box.ZMax)[axis]
        if abs(low - value) < 1e-6 and abs(high - value) < 1e-6:
            return f"Face{index}"
    raise AssertionError(f"no face lies at coordinate {axis} == {value}")


class SupportFollowTest(_BodyFixture):
    """A witness move that FreeCAD attributes to the same element riding its moved support."""

    AXIS_X = 0
    AXIS_Z = 2

    def _attach_datum(self, face):
        datum = self.document.addObject("PartDesign::Plane", "DatumPlane")
        self.body.addObject(datum)
        datum.AttachmentSupport = [(self.pad, (face,))]
        datum.MapMode = "FlatFace"
        self.document.recompute()
        return datum

    def _attach_datum_to_top_face(self):
        return self._attach_datum(_plane_name(self.pad.Shape, self.AXIS_Z, PAD_LENGTH))

    def _datum_findings(self, snapshot):
        audit = self._audit(snapshot)
        return audit, self._findings(audit, "DatumPlane", "AttachmentSupport")

    def _datum_record(self, snapshot):
        return next(r for r in snapshot if r["owner"] == "DatumPlane")

    def _constrain_square(self):
        """Pin the sketch square so its width is a driving dimension; return its index."""
        for constraint in (
            Sketcher.Constraint("Horizontal", 0),
            Sketcher.Constraint("Vertical", 1),
            Sketcher.Constraint("Horizontal", 2),
            Sketcher.Constraint("Vertical", 3),
            Sketcher.Constraint("Coincident", 0, 1, -1, 1),
        ):
            self.sketch.addConstraint(constraint)
        width_index = self.sketch.addConstraint(
            Sketcher.Constraint("DistanceX", 0, 1, 0, 2, SQUARE)
        )
        self.sketch.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, SQUARE))
        self.document.recompute()
        return width_index

    def _grow_pad(self):
        self.pad.Length = PAD_LENGTH + 5.0
        self.document.recompute()

    def test_Should_pass_the_datum_When_pad_length_moves_the_face_it_is_attached_to(self):
        # Arrange
        datum = self._attach_datum_to_top_face()
        snapshot = tnp_guard.snapshot_references(self.document)
        self._grow_pad()

        # Act
        audit, findings = self._datum_findings(snapshot)

        # Assert
        self.assertAlmostEqual(datum.Placement.Base.z, PAD_LENGTH + 5.0, places=6)
        self.assertEqual(audit["status"], "CLEAN")
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("PASS", 2)])
        self.assertIn("descends from the same source element", findings[0]["detail"])

    def test_Should_pass_the_datum_When_a_sketch_width_change_moves_the_face(self):
        # Arrange
        width_index = self._constrain_square()
        datum = self._attach_datum(_plane_name(self.pad.Shape, self.AXIS_X, SQUARE))
        snapshot = tnp_guard.snapshot_references(self.document)
        datum_x_before = datum.Placement.Base.x
        self.sketch.setDatum(width_index, App.Units.Quantity(f"{SQUARE + 10.0} mm"))
        self.document.recompute()

        # Act
        audit, findings = self._datum_findings(snapshot)

        # Assert
        self.assertGreater(self.pad.Shape.BoundBox.XMax, SQUARE + 1.0, "the face must have moved")
        self.assertAlmostEqual(datum.Placement.Base.x, datum_x_before + 10.0, places=6)
        self.assertEqual(audit["status"], "CLEAN")
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("PASS", 2)])

    def test_Should_pass_an_external_geometry_edge_When_pad_length_moves_it(self):
        # Arrange
        reference = self.document.addObject("Sketcher::SketchObject", "ExternalSketch")
        self.body.addObject(reference)
        reference.AttachmentSupport = [(self._origin_plane(), ("",))]
        reference.MapMode = "FlatFace"
        self.document.recompute()
        top_edge = next(
            f"Edge{index}"
            for index, edge in enumerate(self.pad.Shape.Edges, start=1)
            if abs(edge.BoundBox.ZMin - PAD_LENGTH) < 1e-6
            and abs(edge.BoundBox.ZMax - PAD_LENGTH) < 1e-6
        )
        reference.addExternal(self.pad.Name, top_edge)
        self.document.recompute()
        snapshot = tnp_guard.snapshot_references(self.document)
        self._grow_pad()

        # Act
        audit = self._audit(snapshot)
        findings = self._findings(audit, "ExternalSketch", "ExternalGeometry")

        # Assert
        self.assertEqual(audit["status"], "CLEAN")
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("PASS", 2)])

    def test_Should_pass_a_pad_profile_face_When_pad_length_moves_it(self):
        # Arrange
        top_face = _plane_name(self.pad.Shape, self.AXIS_Z, PAD_LENGTH)
        second = self.document.addObject("PartDesign::Pad", "Pad2")
        self.body.addObject(second)
        second.Profile = (self.pad, [top_face])
        second.Length = 3.0
        self.document.recompute()
        self.assertEqual(list(second.State), ["Up-to-date"])
        snapshot = tnp_guard.snapshot_references(self.document)
        self._grow_pad()

        # Act
        audit = self._audit(snapshot)
        findings = self._findings(audit, "Pad2", "Profile")

        # Assert
        self.assertEqual(audit["status"], "CLEAN")
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("PASS", 2)])

    def test_Should_pass_the_moving_fillet_edge_and_still_break_renumbered_ones_When_pad_grows(
        self,
    ):
        # Arrange
        fillet = self._add_fillet()
        snapshot = tnp_guard.snapshot_references(self.document)
        self._grow_pad()

        # Act
        audit = self._audit(snapshot)
        findings = self._findings(audit, "Fillet", "Base")

        # Assert
        self.assertFalse(fillet.isValid(), "FreeCAD itself marks the renumbered fillet invalid")
        moved = [f for f in findings if "Edge4" in f["detail"]]
        self.assertEqual([(f["verdict"], f["layer"]) for f in moved], [("PASS", 2)])
        broken = [f for f in findings if f["verdict"] == "BROKEN"]
        self.assertTrue(broken, "FreeCAD renumbers Edge1 and Edge2; a real break must still report")
        self.assertNotIn("REPOINTED", [f["verdict"] for f in findings])
        self.assertEqual(audit["status"], "FLAGGED")

    def test_Should_flag_repointed_When_the_element_moved_farther_than_its_support(self):
        # Arrange
        self._attach_datum_to_top_face()
        snapshot = tnp_guard.snapshot_references(self.document)
        entry = self._datum_record(snapshot)["entries"][0]
        entry["witness"] = (entry["witness"][0],) + tuple(v - 500.0 for v in entry["witness"][1:])
        self._grow_pad()

        # Act
        _, findings = self._datum_findings(snapshot)

        # Assert
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("REPOINTED", 1)])
        self.assertIn("witness moved", findings[0]["detail"])

    def test_Should_flag_repointed_When_the_witness_moved_and_the_support_did_not(self):
        # Arrange
        self._attach_datum_to_top_face()
        snapshot = tnp_guard.snapshot_references(self.document)
        entry = self._datum_record(snapshot)["entries"][0]
        entry["witness"] = (entry["witness"][0],) + tuple(v + 5.0 for v in entry["witness"][1:])

        # Act
        _, findings = self._datum_findings(snapshot)

        # Assert
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("REPOINTED", 1)])
        self.assertIn("witness moved", findings[0]["detail"])

    def test_Should_flag_repointed_When_the_mapped_name_changed_although_the_support_moved(self):
        # Arrange
        self._attach_datum_to_top_face()
        snapshot = tnp_guard.snapshot_references(self.document)
        self._datum_record(snapshot)["entries"][0]["mapped"] = ";planted;:Hff:7,F"
        self._grow_pad()

        # Act
        _, findings = self._datum_findings(snapshot)

        # Assert
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("REPOINTED", 1)])
        self.assertIn("different element", findings[0]["detail"])

    def test_Should_flag_repointed_When_one_side_has_no_history_although_the_support_moved(self):
        # Arrange
        self._attach_datum_to_top_face()
        snapshot = tnp_guard.snapshot_references(self.document)
        self._datum_record(snapshot)["entries"][0]["history"] = None
        self._grow_pad()

        # Act
        _, findings = self._datum_findings(snapshot)

        # Assert
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("REPOINTED", 1)])

    def test_Should_flag_repointed_When_the_history_source_differs_although_the_support_moved(self):
        # Arrange
        self._attach_datum_to_top_face()
        snapshot = tnp_guard.snapshot_references(self.document)
        self._datum_record(snapshot)["entries"][0]["history"] = (0, "planted")
        self._grow_pad()

        # Act
        _, findings = self._datum_findings(snapshot)

        # Assert
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("REPOINTED", 1)])

    def test_Should_flag_repointed_When_the_support_witness_is_not_a_number(self):
        # Arrange
        self._attach_datum_to_top_face()
        snapshot = tnp_guard.snapshot_references(self.document)
        record = self._datum_record(snapshot)
        support = record["target_witness"]
        record["target_witness"] = support[:4] + (float("nan"),) + support[5:]
        self._grow_pad()

        # Act
        _, findings = self._datum_findings(snapshot)

        # Assert
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("REPOINTED", 1)])

    def test_Should_pass_the_datum_When_the_written_reading_is_taken_before_recompute(self):
        # Arrange
        datum = self._attach_datum_to_top_face()
        snapshot = tnp_guard.snapshot_references(self.document)
        self.pad.Length = PAD_LENGTH + 5.0
        written = tnp_guard.snapshot_references(self.document)
        self.document.recompute()

        # Act
        audit = self._audit(snapshot, written)
        findings = self._findings(audit, datum.Name, "AttachmentSupport")

        # Assert
        self.assertEqual(audit["status"], "CLEAN")
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("PASS", 2)])

    def test_Should_record_the_whole_support_shape_witness_When_snapshotting_a_link(self):
        # Arrange
        self._attach_datum_to_top_face()

        # Act
        snapshot = tnp_guard.snapshot_references(self.document)

        # Assert
        record = self._datum_record(snapshot)
        self.assertEqual(record["target_witness"][0], "Solid")
        self.assertEqual(record["target_witness"][6], PAD_LENGTH)

    def test_Should_flag_repointed_When_the_element_moved_against_the_direction_of_its_support(
        self,
    ):
        # Arrange
        self._attach_datum_to_top_face()
        snapshot = tnp_guard.snapshot_references(self.document)
        entry = self._datum_record(snapshot)["entries"][0]
        witness = list(entry["witness"])
        # The face really rises 5 mm; a snapshot 10 mm higher makes the element appear to fall 5 mm.
        witness[3] += 2 * 5.0
        witness[6] += 2 * 5.0
        entry["witness"] = tuple(witness)
        self._grow_pad()

        # Act
        _, findings = self._datum_findings(snapshot)

        # Assert
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("REPOINTED", 1)])

    def test_Should_flag_repointed_When_the_element_moved_along_an_axis_the_support_did_not(self):
        # Arrange
        self._attach_datum_to_top_face()
        snapshot = tnp_guard.snapshot_references(self.document)
        entry = self._datum_record(snapshot)["entries"][0]
        witness = list(entry["witness"])
        witness[1] -= 5.0
        witness[4] -= 5.0
        entry["witness"] = tuple(witness)
        self._grow_pad()

        # Act
        _, findings = self._datum_findings(snapshot)

        # Assert
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("REPOINTED", 1)])

    def test_Should_grade_against_the_written_support_When_the_op_wrote_the_reference(self):
        # Arrange
        datum = self._attach_datum_to_top_face()
        snapshot = tnp_guard.snapshot_references(self.document)
        self.pad.Length = PAD_LENGTH + 5.0
        written = tnp_guard.snapshot_references(self.document)
        record = self._datum_record(written)
        support = record["target_witness"]
        record["target_witness"] = support[:4] + (float("nan"),) + support[5:]
        self.document.recompute()

        # Act
        findings = self._findings(self._audit(snapshot, written), datum.Name, "AttachmentSupport")

        # Assert
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("REPOINTED", 1)])

    def test_Should_pass_the_datum_When_the_pad_grows_toward_the_negative_side(self):
        # Arrange
        self.pad.Reversed = True
        self.document.recompute()
        datum = self._attach_datum(_plane_name(self.pad.Shape, self.AXIS_Z, -PAD_LENGTH))
        snapshot = tnp_guard.snapshot_references(self.document)
        self._grow_pad()

        # Act
        audit, findings = self._datum_findings(snapshot)

        # Assert
        self.assertAlmostEqual(datum.Placement.Base.z, -(PAD_LENGTH + 5.0), places=6)
        self.assertEqual(audit["status"], "CLEAN")
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("PASS", 2)])

    def test_Should_return_no_witness_When_the_support_shape_cannot_be_read(self):
        # Arrange
        class _UnreadableShape:
            @property
            def Shape(self):
                raise RuntimeError("shape unreadable")

        # Act
        witness = tnp_guard._support_witness(_UnreadableShape())

        # Assert
        self.assertIsNone(witness)

    def test_Should_pass_the_datum_When_the_pad_shrinks(self):
        # Arrange
        self._attach_datum_to_top_face()
        snapshot = tnp_guard.snapshot_references(self.document)
        self.pad.Length = PAD_LENGTH - 5.0
        self.document.recompute()

        # Act
        audit, findings = self._datum_findings(snapshot)

        # Assert
        self.assertEqual(audit["status"], "CLEAN")
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("PASS", 2)])

    def test_Should_pass_the_datum_When_a_midplane_pad_grows_on_both_sides(self):
        # Arrange
        self.pad.Midplane = True
        self.document.recompute()
        datum = self._attach_datum(_plane_name(self.pad.Shape, self.AXIS_Z, PAD_LENGTH / 2))
        snapshot = tnp_guard.snapshot_references(self.document)
        self._grow_pad()

        # Act
        audit, findings = self._datum_findings(snapshot)

        # Assert
        self.assertAlmostEqual(datum.Placement.Base.z, (PAD_LENGTH + 5.0) / 2, places=6)
        self.assertEqual(audit["status"], "CLEAN")
        self.assertEqual([(f["verdict"], f["layer"]) for f in findings], [("PASS", 2)])

    def test_Should_keep_a_whole_object_link_record_When_its_target_shape_cannot_be_read(self):
        # Arrange
        class _Target:
            Name = "Target"

            @property
            def Shape(self):
                raise RuntimeError("shape unreadable")

        target = _Target()

        class _Owner:
            Name = "Owner"
            PropertiesList = ["Support"]
            Support = (target, [""])

            def getTypeIdOfProperty(self, prop):
                return "App::PropertyLinkSub"

        document = type("_OneOwnerDocument", (), {"Objects": [_Owner()]})()

        # Act
        records = tnp_guard.snapshot_references(document)

        # Assert
        self.assertEqual([(r["owner"], r["prop"]) for r in records], [("Owner", "Support")])
        self.assertIsNone(records[0]["target_witness"])


class AxisShiftsTest(unittest.TestCase):
    BOX = ("Solid", 0.0, 0.0, 0.0, 20.0, 20.0, 10.0)

    def test_Should_return_zero_shifts_When_both_witnesses_are_equal(self):
        # Arrange
        before = after = self.BOX

        # Act
        result = tnp_guard._axis_shifts(before, after)

        # Assert
        self.assertEqual(result, ((0.0, 0.0), (0.0, 0.0), (0.0, 0.0)))

    def test_Should_return_the_signed_face_shifts_When_the_maximum_face_moved(self):
        # Arrange
        after = ("Solid", 0.0, 0.0, 0.0, 20.0, 20.0, 15.0)

        # Act
        result = tnp_guard._axis_shifts(self.BOX, after)

        # Assert
        self.assertEqual(result, ((0.0, 0.0), (0.0, 0.0), (0.0, 5.0)))

    def test_Should_return_the_signed_face_shifts_When_only_the_minimum_face_moved(self):
        # Arrange
        after = ("Solid", 0.0, 0.0, -5.0, 20.0, 20.0, 10.0)

        # Act
        result = tnp_guard._axis_shifts(self.BOX, after)

        # Assert
        self.assertEqual(result, ((0.0, 0.0), (0.0, 0.0), (-5.0, 0.0)))

    def test_Should_return_none_When_a_side_is_unreadable(self):
        # Arrange
        before, after = self.BOX, None

        # Act
        result = tnp_guard._axis_shifts(before, after)

        # Assert
        self.assertIsNone(result)

    def test_Should_return_none_When_the_shape_type_changed(self):
        # Arrange
        after = ("Compound",) + self.BOX[1:]

        # Act
        result = tnp_guard._axis_shifts(self.BOX, after)

        # Assert
        self.assertIsNone(result)

    def test_Should_return_none_When_a_component_is_not_finite(self):
        # Arrange
        not_a_number = ("Solid", float("nan")) + self.BOX[2:]
        infinite = ("Solid", float("inf")) + self.BOX[2:]

        # Act
        results = [
            tnp_guard._axis_shifts(self.BOX, not_a_number),
            tnp_guard._axis_shifts(self.BOX, infinite),
        ]

        # Assert
        self.assertEqual(results, [None, None])


class FollowsSupportTest(unittest.TestCase):
    WITNESS = ("Face", 0.0, 0.0, 10.0, 20.0, 20.0, 10.0)
    HISTORY = (7, "g1;SKT")
    GREW_UP_FIVE = ((0.0, 0.0), (0.0, 0.0), (0.0, 5.0))
    GREW_DOWN_FIVE = ((0.0, 0.0), (0.0, 0.0), (-5.0, 0.0))
    SHRANK_FIVE = ((0.0, 0.0), (0.0, 0.0), (0.0, -5.0))

    def _entry(self, shift=(0.0, 0.0, 0.0), mapped=";a;", history=HISTORY):
        dx, dy, dz = shift
        witness = (
            self.WITNESS[0],
            self.WITNESS[1] + dx,
            self.WITNESS[2] + dy,
            self.WITNESS[3] + dz,
            self.WITNESS[4] + dx,
            self.WITNESS[5] + dy,
            self.WITNESS[6] + dz,
        )
        return {
            "mapped": mapped,
            "indexed": "Face6",
            "missing": False,
            "witness": witness,
            "history": history,
        }

    def test_Should_excuse_the_move_When_the_same_element_moved_with_its_support(self):
        # Arrange
        before, after = self._entry(), self._entry(shift=(0.0, 0.0, 5.0))

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_UP_FIVE, 1e-7)

        # Assert
        self.assertTrue(result)

    def test_Should_excuse_the_move_When_the_support_grew_on_its_minimum_side(self):
        # Arrange
        before, after = self._entry(), self._entry(shift=(0.0, 0.0, -5.0))

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_DOWN_FIVE, 1e-7)

        # Assert
        self.assertTrue(result)

    def test_Should_excuse_the_move_When_the_support_shrank(self):
        # Arrange
        before, after = self._entry(), self._entry(shift=(0.0, 0.0, -5.0))

        # Act
        result = tnp_guard._follows_support(before, after, self.SHRANK_FIVE, 1e-7)

        # Assert
        self.assertTrue(result)

    def test_Should_not_excuse_the_move_When_the_support_did_not_change(self):
        # Arrange
        before, after = self._entry(), self._entry(shift=(0.0, 0.0, 0.5))
        unmoved = ((0.0, 0.0), (0.0, 0.0), (0.0, 0.0))

        # Act
        result = tnp_guard._follows_support(before, after, unmoved, 1.0)

        # Assert
        self.assertFalse(result)

    def test_Should_not_excuse_the_move_When_the_support_shift_is_unknown(self):
        # Arrange
        before, after = self._entry(), self._entry(shift=(0.0, 0.0, 5.0))

        # Act
        result = tnp_guard._follows_support(before, after, None, 1e-7)

        # Assert
        self.assertFalse(result)

    def test_Should_not_excuse_the_move_When_the_element_moved_beyond_the_support(self):
        # Arrange
        before, after = self._entry(), self._entry(shift=(0.0, 0.0, 6.0))

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_UP_FIVE, 1e-7)

        # Assert
        self.assertFalse(result)

    def test_Should_not_excuse_the_move_When_it_runs_along_an_axis_the_support_did_not_move_on(
        self,
    ):
        # Arrange
        before, after = self._entry(), self._entry(shift=(5.0, 0.0, 0.0))

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_UP_FIVE, 1e-7)

        # Assert
        self.assertFalse(result)

    def test_Should_not_excuse_the_move_When_it_runs_against_the_direction_of_the_support(self):
        # Arrange
        before, after = self._entry(), self._entry(shift=(0.0, 0.0, -5.0))

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_UP_FIVE, 1e-7)

        # Assert
        self.assertFalse(result)

    def test_Should_not_excuse_the_move_When_neither_side_has_a_history(self):
        # Arrange
        before = self._entry(history=None)
        after = self._entry(shift=(0.0, 0.0, 5.0), history=None)

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_UP_FIVE, 1e-7)

        # Assert
        self.assertFalse(result)

    def test_Should_not_excuse_the_move_When_neither_side_has_a_mapped_name(self):
        # Arrange
        before = self._entry(mapped=None)
        after = self._entry(shift=(0.0, 0.0, 5.0), mapped=None)

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_UP_FIVE, 1e-7)

        # Assert
        self.assertFalse(result)

    def test_Should_not_excuse_the_move_When_the_history_source_differs(self):
        # Arrange
        before = self._entry()
        after = self._entry(shift=(0.0, 0.0, 5.0), history=(8, "other"))

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_UP_FIVE, 1e-7)

        # Assert
        self.assertFalse(result)

    def test_Should_not_excuse_the_move_When_the_history_source_name_carries_a_counter(self):
        # Arrange
        source = (1, "#60:3;:M3;CUT;:H1:8,E")
        before = self._entry(history=source)
        after = self._entry(shift=(0.0, 0.0, 5.0), history=source)

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_UP_FIVE, 1e-7)

        # Assert
        self.assertFalse(result)

    def test_Should_not_excuse_the_move_When_the_lineage_holds_a_counter(self):
        # Arrange
        before = dict(self._entry(), lineage_counter=True)
        after = dict(self._entry(shift=(0.0, 0.0, 5.0)), lineage_counter=True)

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_UP_FIVE, 1e-7)

        # Assert
        self.assertFalse(result)

    def test_Should_not_excuse_the_move_When_a_bare_name_has_split_siblings_before(self):
        # Arrange
        before = dict(self._entry(), split_siblings=True)
        after = self._entry(shift=(0.0, 0.0, 5.0))

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_UP_FIVE, 1e-7)

        # Assert
        self.assertFalse(result)

    def test_Should_not_excuse_the_move_When_a_bare_name_has_split_siblings_after(self):
        # Arrange
        before = self._entry()
        after = dict(self._entry(shift=(0.0, 0.0, 5.0)), split_siblings=True)

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_UP_FIVE, 1e-7)

        # Assert
        self.assertFalse(result)

    def test_Should_not_excuse_the_move_When_the_mapped_name_carries_a_positional_counter(self):
        # Arrange
        name = ";#60:3;:M3;CUT;:H1:8,E"
        before = self._entry(mapped=name)
        after = self._entry(shift=(0.0, 0.0, 5.0), mapped=name)

        # Act
        result = tnp_guard._follows_support(before, after, self.GREW_UP_FIVE, 1e-7)

        # Assert
        self.assertFalse(result)


class SplitSiblingTest(_BodyFixture):
    """A bare ``;:U`` name is piece 1; it is positional only while indexed siblings exist."""

    def _fillet_names(self):
        fillet = self._add_fillet()
        return fillet, {indexed: mapped for mapped, indexed in fillet.Shape.ElementMap.items()}

    def _bare_element(self, fillet, names, with_siblings):
        stems = tnp_guard._split_sibling_stems(fillet.Shape)
        for indexed, mapped in names.items():
            if ";:U;" in mapped and (mapped.split(";:U;")[0] in stems) == with_siblings:
                return indexed
        self.fail("the fillet carries no bare ;:U element with siblings=%s" % with_siblings)

    def test_Should_mark_a_bare_name_When_indexed_siblings_share_its_stem(self):
        # Arrange
        fillet, names = self._fillet_names()
        indexed = self._bare_element(fillet, names, with_siblings=True)

        # Act
        entry = tnp_guard._capture_entry(fillet, indexed)

        # Assert
        self.assertTrue(entry["split_siblings"], names[indexed])

    def test_Should_not_mark_a_bare_name_When_no_indexed_sibling_shares_its_stem(self):
        # Arrange
        fillet, names = self._fillet_names()
        indexed = self._bare_element(fillet, names, with_siblings=False)

        # Act
        entry = tnp_guard._capture_entry(fillet, indexed)

        # Assert
        self.assertFalse(entry["split_siblings"], names[indexed])

    def test_Should_not_mark_a_pad_face_When_the_name_carries_the_fixed_index_zero(self):
        # Arrange
        top_face = _plane_name(self.pad.Shape, 2, PAD_LENGTH)

        # Act
        entry = tnp_guard._capture_entry(self.pad, top_face)

        # Assert
        self.assertNotIn("split_siblings", entry)

    def test_Should_detect_siblings_When_the_stem_has_an_indexed_marker(self):
        # Arrange
        stems = frozenset(["#26:1"])
        stems_from_shape = tnp_guard._split_sibling_stems(
            type("_Shape", (), {"ElementMap": {"#26:1;:G2;XTR;:H1:7,F": "Face2"}})()
        )

        # Act
        results = [
            tnp_guard._has_split_siblings("#26:1;:U;FLT;:H1:7,E", stems),
            tnp_guard._has_split_siblings("#26:2;:U;FLT;:H1:7,E", stems),
            tnp_guard._has_split_siblings("#26:1;:G0;XTR;:H1:8,F", stems),
            tnp_guard._has_split_siblings(None, stems),
            tnp_guard._has_split_siblings("#26:1;:G;XTR;:H1:7,F", stems_from_shape),
        ]

        # Assert
        self.assertEqual(results, [True, False, False, False, True])

    def test_Should_cache_the_stems_per_target_name_When_two_targets_share_one_walk(self):
        # Arrange
        fillet, names = self._fillet_names()
        indexed = self._bare_element(fillet, names, with_siblings=True)
        shared = {}
        pad_face_with_bare_marker = "Face1"

        # Act
        tnp_guard._capture_entry(self.pad, pad_face_with_bare_marker, shared)
        entry = tnp_guard._capture_entry(fillet, indexed, shared)

        # Assert
        self.assertTrue(entry["split_siblings"])
        self.assertEqual(sorted(shared), ["Fillet", "Pad"])


class SplitPieceCounterTest(_BodyFixture):
    """A positional piece counter in the mapped name never lets a move pass as support-following."""

    PLATE_LENGTH = 40.0
    PLATE_WIDTH = 10.0
    PLATE_THICKNESS = 10.0
    EDITED_LENGTH = 60.0

    def _rectangle(self, name, x_min, y_min, x_max, y_max, attach=None):
        sketch = self.document.addObject("Sketcher::SketchObject", name)
        self.plate.addObject(sketch)
        if attach is not None:
            sketch.AttachmentSupport = [(attach, "")]
            sketch.MapMode = "FlatFace"
        corners = [
            (x_min, y_min, x_max, y_min),
            (x_max, y_min, x_max, y_max),
            (x_max, y_max, x_min, y_max),
            (x_min, y_max, x_min, y_min),
        ]
        for x1, y1, x2, y2 in corners:
            sketch.addGeometry(
                Part.LineSegment(App.Vector(x1, y1, 0), App.Vector(x2, y2, 0)), False
            )
        for index in range(4):
            sketch.addConstraint(Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1))
        return sketch

    def _build_slotted_plate(self, pass_through=0):
        """A plate whose length drives a groove pattern; the groove count changes with it.

        ``pass_through`` bottom holes follow the pattern and leave its top elements unchanged, so
        FreeCAD hashes the older mapped name and each history step shows one feature less.
        """
        self.plate = self.document.addObject("PartDesign::Body", "Plate")
        xy_plane = next(f for f in self.plate.Origin.OriginFeatures if f.TypeId == "App::Plane")
        sketch = self._rectangle("PlateSketch", 0, 0, self.PLATE_LENGTH, self.PLATE_WIDTH, xy_plane)
        for constraint in (
            Sketcher.Constraint("Horizontal", 0),
            Sketcher.Constraint("Horizontal", 2),
            Sketcher.Constraint("Vertical", 1),
            Sketcher.Constraint("Vertical", 3),
            Sketcher.Constraint("Coincident", 0, 1, -1, 1),
        ):
            sketch.addConstraint(constraint)
        length_index = sketch.addConstraint(
            Sketcher.Constraint("DistanceX", 0, 1, 0, 2, self.PLATE_LENGTH)
        )
        sketch.renameConstraint(length_index, "L")
        sketch.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, self.PLATE_WIDTH))
        pad = self.document.addObject("PartDesign::Pad", "PlatePad")
        self.plate.addObject(pad)
        pad.Profile = sketch
        pad.Length = self.PLATE_THICKNESS
        self.document.recompute()
        groove_sketch = self._rectangle(
            "GrooveSketch",
            8,
            -1,
            10,
            self.PLATE_WIDTH + 1,
            xy_plane,
        )
        groove_sketch.AttachmentOffset = App.Placement(
            App.Vector(0, 0, self.PLATE_THICKNESS), App.Rotation()
        )
        groove = self.document.addObject("PartDesign::Pocket", "Groove")
        self.plate.addObject(groove)
        groove.Profile = groove_sketch
        groove.Length = 2.0
        self.document.recompute()
        pattern = self.document.addObject("PartDesign::LinearPattern", "GroovePattern")
        self.plate.addObject(pattern)
        pattern.Originals = [groove]
        pattern.Direction = (sketch, ["H_Axis"])
        pattern.setExpression("Length", "PlateSketch.Constraints.L - 12 mm")
        pattern.setExpression("Occurrences", "floor(PlateSketch.Constraints.L / 13 mm)")
        self.document.recompute()
        self.plate.Tip = pattern
        last = pattern
        for index in range(pass_through):
            hole_sketch = self._rectangle(
                f"HoleSketch{index}", 1 + 3 * index, 1, 2 + 3 * index, 2, xy_plane
            )
            hole = self.document.addObject("PartDesign::Pocket", f"Hole{index}")
            self.plate.addObject(hole)
            hole.Profile = hole_sketch
            hole.Length = 1.0
            hole.Reversed = True
            self.document.recompute()
            self.plate.Tip = hole
            last = hole
        return last

    def _strip_edge(self, pattern):
        """The top edge of the strip between the first and second groove (x 10 to 22)."""
        return next(
            f"Edge{index}"
            for index, edge in enumerate(pattern.Shape.Edges, start=1)
            if abs(edge.BoundBox.YMin - self.PLATE_WIDTH) < 1e-6
            and abs(edge.BoundBox.ZMin - self.PLATE_THICKNESS) < 1e-6
            and abs(edge.BoundBox.XMin - 10.0) < 1e-6
            and abs(edge.BoundBox.XMax - 22.0) < 1e-6
        )

    def _datum_verdicts_after_length_edit(self, pass_through):
        last = self._build_slotted_plate(pass_through)
        edge = self._strip_edge(last)
        datum = self.document.addObject("PartDesign::Point", "DatumPoint")
        self.plate.addObject(datum)
        datum.AttachmentSupport = [(last, (edge,))]
        datum.MapMode = "CenterOfMass"
        self.document.recompute()
        posture = confirm.set_auto_approve(True)
        self.addCleanup(confirm.set_auto_approve, posture)
        envelope = sketches.sketch_set_datum(
            self.registry,
            doc=self.handle,
            sketch="PlateSketch",
            constraint="L",
            value={"value": self.EDITED_LENGTH, "unit": "mm"},
        )
        audit = envelope["structured_content"]["mutation"]["post_verify"]["tnp_audit"]
        findings = [f for f in audit["findings"] if f["owner"] == "DatumPoint"]
        return envelope, audit, [f["verdict"] for f in findings]

    def test_Should_flag_repointed_When_a_pattern_edit_changes_the_split_piece_count(self):
        # Arrange
        pass_through = 0

        # Act
        envelope, audit, verdicts = self._datum_verdicts_after_length_edit(pass_through)

        # Assert
        self.assertIn("REPOINTED", verdicts)
        self.assertNotEqual(audit["status"], "CLEAN")
        self.assertEqual(envelope["status"], "SPEC_FAILED")

    def test_Should_flag_repointed_When_the_counter_is_hidden_behind_two_pass_through_features(
        self,
    ):
        # Arrange
        pass_through = 2

        # Act
        envelope, audit, verdicts = self._datum_verdicts_after_length_edit(pass_through)

        # Assert
        self.assertIn("REPOINTED", verdicts)
        self.assertNotEqual(audit["status"], "CLEAN")
        self.assertEqual(envelope["status"], "SPEC_FAILED")


class WitnessMeshTest(unittest.TestCase):
    """The witness reads the exact geometry, never the display mesh a view may have built."""

    def test_Should_read_the_exact_extreme_When_the_curved_face_was_tessellated(self):
        # Arrange
        cylinder = Part.makeCylinder(3.0, 15.0, App.Vector(10.0, 5.0, 0.0))
        face = cylinder.Faces[0]
        exact_witness = tnp_guard._witness(face)
        face.tessellate(0.5)

        # Act
        witness = tnp_guard._witness(face)

        # Assert
        self.assertGreater(face.BoundBox.YMin, 2.0 + 1e-4, "tessellation must shift BoundBox")
        self.assertEqual(witness, exact_witness)
        self.assertAlmostEqual(witness[2], 2.0, places=9)


class PositionalCounterTest(unittest.TestCase):
    def test_Should_detect_the_counter_When_the_name_carries_a_FreeCAD_split_marker(self):
        # Arrange
        names = [
            "#60:3;:M3;CUT;:Hcc3:8,E",
            "#60;:M;CUT;:Hcc3:8,E",
            "g1;:G2;XTR;:Hcc3:8,F",
            "g1;:G#73;CUT;:Hcc3:a,V",
            "g1;:MG;FLT;:Hcc3:8,F",
            "g1;:MG4;FLT;:Hcc3:8,F",
            "g1;:U2;:Hcc3:8,V",
            "g1;:U3;FLT;:Hcc3:8,E",
            "g1;D1a2;:Hcc3:8,F",
            "g1;:G10#64;CUT;:Hcc3:c,E",
            "g1;:U12;FLT;:Hcc3:8,E",
            "g1;:G0#5;CUT;:Hcc3:a,F",
            "g1;:G00#5;CUT;:Hcc3:a,F",
            "g1;K2;:Hcc3:8,F",
            "g1;:I4;:Hcc3:8,F",
        ]

        # Act
        results = [tnp_guard._has_positional_counter(name) for name in names]

        # Assert
        self.assertEqual(results, [True] * len(names))

    def test_Should_not_detect_a_counter_When_the_name_has_only_tag_and_operation_markers(self):
        # Arrange
        names = [
            "g1;SKT;:Hcc3:8,F",
            "#60;:H1a:8,F;XTR;:Hcc5,F",
            "g12;:L;FLT;:T5,E",
            "g1;:G0;XTR;:Hcc3:8,F",
            "g1;:G00;XTR;:Hcc3:8,F",
            "g1;:G;XTR;:Hcc3:8,F",
            "g1;:U;XTR;:Hcc3:8,E",
            "g1;:X2;:C3,F",
            "g1;D1ax;:Hcc3:8,F",
            "",
        ]

        # Act
        results = [tnp_guard._has_positional_counter(name) for name in names]

        # Assert
        self.assertEqual(results, [False] * len(names))
