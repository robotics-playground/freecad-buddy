"""In-FreeCAD tests for ``preview_dry_run`` (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. The fixtures build a PartDesign body (sketch -> pad),
the shape that carries a real element map, and preview a fillet against it. Covers every
I/O-matrix row: the measured deltas, the live-document-unchanged proof, TempDoc cleanup on the
success/failure/exception paths, the rejected-tool paths, the metric-object selection rule, the
projections of the op's own ``post_verify`` block, and the audit record.

``_leftovers`` builds its glob from ``preview._TEMPDOC_PREFIX`` rather than restating the string,
so a preview that abandoned the reserved prefix leaks INTO the sweep instead of out of it.
"""

import glob
import os
import shutil
import tempfile
import unittest

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.hosts.tool_catalog import preview_op_table
from freecad_buddy.usecases import confirm, preview, queries, shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

SQUARE = 10.0
PAD_LENGTH = 5.0
FILLET_RADIUS = 1.0

# Analytic reference values for the fixture, derived from the geometry rather than captured from
# the implementation: a 10x10x5 pad is 500 mm^3 with 6 faces, 12 edges and 8 vertices; filleting
# one edge at r=1 replaces that edge with a cylindrical face, adding 1 face, 3 edges, 2 vertices.
PAD_VOLUME = 500.0
PAD_AREA = 400.0
PAD_COUNTS = {"faces": 6, "edges": 12, "vertices": 8, "solids": 1}
FILLET_COUNTS = {"faces": 7, "edges": 15, "vertices": 10, "solids": 1}


def _leftovers():
    """Every reserved-prefix preview directory currently on disk."""
    return set(glob.glob(os.path.join(tempfile.gettempdir(), preview._TEMPDOC_PREFIX + "*")))


def _fillet_op(radius=FILLET_RADIUS, edge="Edge1", name="Fillet"):
    return {
        "tool": "feature_fillet",
        "args": {
            "body": "Body",
            "base": "Pad",
            "name": name,
            "radius": {"value": radius, "unit": "mm"},
            "edges": [{"kind": "mapped_name", "object": "Pad", "mapped_name": edge}],
        },
    }


class _PreviewFixture(unittest.TestCase):
    """A live PartDesign body (sketch -> pad) plus the catalog's real op table."""

    def setUp(self):
        self._leftovers_before = _leftovers()
        # Deliberately left fail-closed: a preview must reach its own operation without a
        # confirm, because it is what mints the token an apply presents.
        self._posture = confirm.set_auto_approve(False)
        self.registry = DocumentRegistry()
        created = self.registry.document_create("preview_live")
        self.handle = created["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))
        self.op_table = preview_op_table()
        self._build()

    def tearDown(self):
        confirm.set_auto_approve(self._posture)
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)
        for path in _leftovers() - self._leftovers_before:
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

    def _preview(self, operation=None, table=None, **kwargs):
        return preview.preview_dry_run(
            self.registry,
            self.op_table if table is None else table,
            kwargs.pop("render_port", None),
            doc=self.handle,
            operation=_fillet_op() if operation is None else operation,
            **kwargs,
        )

    def _diff(self, **kwargs):
        envelope = self._preview(**kwargs)
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        return envelope["structured_content"]["diff"]

    def _new_leftovers(self):
        return _leftovers() - self._leftovers_before


class HappyPathTest(_PreviewFixture):
    def test_an_additive_op_reports_its_measured_count_and_volume_deltas(self):
        diff = self._diff()
        for key, before in PAD_COUNTS.items():
            self.assertEqual(diff["counts"][key]["before"], before, key)
            self.assertEqual(diff["counts"][key]["after"], FILLET_COUNTS[key], key)
            self.assertEqual(diff["counts"][key]["delta"], FILLET_COUNTS[key] - before, key)
        self.assertAlmostEqual(diff["deltas"]["volume"]["before"], PAD_VOLUME, places=6)
        self.assertLess(diff["deltas"]["volume"]["delta"], 0.0)
        self.assertAlmostEqual(diff["deltas"]["area"]["before"], PAD_AREA, places=6)

    def test_the_envelope_carries_a_preview_id_and_an_expiry(self):
        envelope = self._preview()
        content = envelope["structured_content"]
        self.assertTrue(content["preview_id"].startswith("fcb-preview:"))
        self.assertTrue(content["expires_at"].endswith("+00:00"))

    def test_should_leave_the_preview_id_out_of_the_text_when_a_preview_succeeds(self):
        # Arrange
        operation = _fillet_op()

        # Act
        envelope = self._preview(operation=operation)

        # Assert
        self.assertNotIn(envelope["structured_content"]["preview_id"], envelope["text"])
        self.assertNotIn("fcb-preview:", envelope["text"])

    def test_the_preview_id_and_expiry_are_envelope_siblings_not_diff_fields(self):
        content = self._preview()["structured_content"]
        self.assertNotIn("preview_id", content["diff"])
        self.assertNotIn("expires_at", content["diff"])

    def test_the_diff_names_the_op_the_live_doc_and_the_before_fingerprint(self):
        diff = self._diff()
        self.assertEqual(diff["schema"], "fcb.geometry-diff/2")
        self.assertEqual(diff["op"], {"tool": "feature_fillet"})
        self.assertEqual(diff["doc"]["handle"], self.handle)
        self.assertEqual(len(diff["fingerprint_before"]), 64)

    def test_every_dimension_carries_explicit_units(self):
        deltas = self._diff()["deltas"]
        self.assertEqual(deltas["volume"]["units"], "mm^3")
        self.assertEqual(deltas["area"]["units"], "mm^2")
        self.assertEqual(deltas["bbox"]["units"], "mm")
        self.assertEqual(deltas["com"]["units"], "mm")

    def test_the_new_object_the_op_created_is_reported(self):
        diff = self._diff()
        self.assertEqual(diff["new"], ["Fillet"])
        self.assertEqual(diff["deleted"], [])

    def test_the_same_op_previewed_twice_produces_identical_deltas_and_counts(self):
        first = self._diff()
        second = self._diff()
        self.assertEqual(first["deltas"], second["deltas"])
        self.assertEqual(first["counts"], second["counts"])


class LiveDocumentUntouchedTest(_PreviewFixture):
    def test_a_successful_preview_leaves_the_live_geometry_unchanged(self):
        before = queries.shape_metrics(self.pad.Shape)
        self._diff()
        after = queries.shape_metrics(self.document.getObject("Pad").Shape)
        self.assertEqual(before["counts"], after["counts"])
        self.assertAlmostEqual(before["volume"], after["volume"], places=9)

    def test_a_successful_preview_adds_no_object_to_the_live_document(self):
        before = [o.Name for o in self.document.Objects]
        self._diff()
        self.assertEqual([o.Name for o in self.document.Objects], before)

    def test_a_preview_that_did_change_the_live_geometry_reports_a_failure(self):
        """The live-unchanged guard is only falsifiable against an op that DOES leak.

        Nothing else in a correct preview mutates the live document, so a test that asserts only
        the outcome stays green whether or not the guard runs. This injects the leak.
        """
        live_doc = self.document
        handle = self.handle

        def leaking_op(registry, doc=None, **kwargs):  # noqa: ARG001
            live_doc.getObject("Pad").Length = PAD_LENGTH + 3.0
            live_doc.recompute()
            return {
                "schema": "fcb.result-envelope/1",
                "status": "OK",
                "detail": None,
                "structured_content": {},
                "text": "",
            }

        envelope = preview.preview_dry_run(
            self.registry,
            {"feature_fillet": leaking_op},
            None,
            doc=handle,
            operation=_fillet_op(),
        )
        self.assertNotEqual(envelope["status"], "OK")
        self.assertEqual(envelope["detail"]["code"], "preview.failed")
        self.assertIsNone(envelope["structured_content"]["preview_id"])


class TempDocCleanupTest(_PreviewFixture):
    def test_a_successful_preview_leaves_no_open_tempdoc(self):
        self._diff()
        self.assertEqual(list(App.listDocuments().keys()), [self.document.Name])

    def test_a_successful_preview_leaves_no_reserved_prefix_directory(self):
        self._diff()
        self.assertEqual(self._new_leftovers(), set())

    def test_a_failing_op_still_leaves_no_tempdoc_or_directory(self):
        envelope = self._preview(operation=_fillet_op(radius=500.0))
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(list(App.listDocuments().keys()), [self.document.Name])
        self.assertEqual(self._new_leftovers(), set())

    def test_an_op_that_raises_still_leaves_no_tempdoc_or_directory(self):
        def exploding_op(registry, doc=None, **kwargs):  # noqa: ARG001
            raise RuntimeError("op blew up mid-preview")

        with self.assertRaises(RuntimeError):
            preview.preview_dry_run(
                self.registry,
                {"feature_fillet": exploding_op},
                None,
                doc=self.handle,
                operation=_fillet_op(),
            )
        self.assertEqual(list(App.listDocuments().keys()), [self.document.Name])
        self.assertEqual(self._new_leftovers(), set())

    def test_document_list_after_a_preview_holds_no_tempdoc_handle(self):
        self._diff()
        listing = self.registry.document_list()["structured_content"]["documents"]
        names = [entry["name"] for entry in listing]
        self.assertEqual(names, [self.document.Name])
        self.assertFalse([n for n in names if n.startswith(preview._TEMPDOC_PREFIX)])

    def test_the_tempdoc_handle_is_released_from_the_registry(self):
        before = len(self.registry.document_list()["structured_content"]["documents"])
        self._diff()
        after = len(self.registry.document_list()["structured_content"]["documents"])
        self.assertEqual(before, after)


class ReservedPrefixTest(_PreviewFixture):
    def test_the_tempdoc_prefix_is_the_reserved_one(self):
        self.assertEqual(preview._TEMPDOC_PREFIX, "FCB_TMP_prev_")
        self.assertTrue(preview._TEMPDOC_PREFIX.startswith("FCB_TMP_"))

    def test_the_minted_temp_path_carries_the_reserved_prefix_in_both_dir_and_stem(self):
        path = preview._tempdoc_path()
        try:
            directory = os.path.dirname(path)
            self.assertTrue(os.path.basename(directory).startswith("FCB_TMP_prev_"), directory)
            self.assertTrue(os.path.basename(path).startswith("FCB_TMP_prev_"), path)
            self.assertTrue(path.endswith(".FCStd"))
            self.assertFalse(os.path.exists(path), "saveCopy must write a file that does not exist")
        finally:
            shutil.rmtree(os.path.dirname(path), ignore_errors=True)

    def test_the_tempdoc_the_preview_opens_is_named_with_the_reserved_prefix(self):
        """The reopened document takes its Name from the file stem, so the prefix must be there."""
        seen = []
        real_open = self.registry.document_open

        def spy(path):
            envelope = real_open(path)
            seen.append(envelope["structured_content"]["name"])
            return envelope

        self.registry.document_open = spy
        try:
            self._diff()
        finally:
            self.registry.document_open = real_open
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0].startswith("FCB_TMP_prev_"), seen[0])

    def test_the_removal_guard_spares_a_directory_outside_the_reserved_prefix(self):
        directory = tempfile.mkdtemp(prefix="not_reserved_")
        path = os.path.join(directory, "keep.FCStd")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("x")
        try:
            preview._remove_tempdir(path)
            self.assertTrue(os.path.exists(path), "a non-reserved directory must not be emptied")
        finally:
            shutil.rmtree(directory, ignore_errors=True)


class CopyRouteTest(_PreviewFixture):
    """The saveCopy route is chosen because it preserves mapped names; copyObject rehashes them."""

    def setUp(self):
        super().setUp()
        if not shim.element_map_available():
            self.skipTest("element map unavailable; mapped-name stability is unobservable")

    def _reopen_copy(self):
        path = preview._tempdoc_path()
        self.document.saveCopy(path)
        copy = App.openDocument(path)
        return copy, path

    def test_the_copy_preserves_every_mapped_name_verbatim(self):
        copy, path = self._reopen_copy()
        try:
            live = self.pad.Shape
            copied = copy.getObject("Pad").Shape
            for element in ("Face1", "Face6", "Edge1", "Vertex1"):
                self.assertEqual(
                    live.getElementMappedName(element),
                    copied.getElementMappedName(element),
                    element,
                )
        finally:
            App.closeDocument(copy.Name)
            shutil.rmtree(os.path.dirname(path), ignore_errors=True)

    def test_the_copy_preserves_object_names_in_order(self):
        copy, path = self._reopen_copy()
        try:
            self.assertEqual(
                [o.Name for o in copy.Objects], [o.Name for o in self.document.Objects]
            )
        finally:
            App.closeDocument(copy.Name)
            shutil.rmtree(os.path.dirname(path), ignore_errors=True)

    def test_the_reopened_copy_recomputes_clean(self):
        copy, path = self._reopen_copy()
        try:
            self.assertEqual(copy.recompute(), 0)
            for obj in copy.Objects:
                self.assertNotIn("Invalid", list(obj.State), obj.Name)
                self.assertNotIn("Error", list(obj.State), obj.Name)
        finally:
            App.closeDocument(copy.Name)
            shutil.rmtree(os.path.dirname(path), ignore_errors=True)

    def test_copy_object_rehashes_the_mapped_names_the_copy_route_preserves(self):
        """Keeps the rejected route's defect asserted rather than only recorded in prose."""
        before = self.pad.Shape.getElementMappedName("Face6")
        self.document.copyObject(self.pad, True)
        self.document.recompute()
        duplicate = self.document.getObject("Pad001")
        self.assertIsNotNone(duplicate)
        self.assertNotEqual(duplicate.Shape.getElementMappedName("Face6"), before)


class RejectedOperationTest(_PreviewFixture):
    def test_an_unknown_tool_name_is_invalid_input(self):
        with self.assertRaises(ValidationError):
            self._preview(operation={"tool": "feature_bogus", "args": {}})

    def test_a_non_mutation_tool_is_invalid_input(self):
        with self.assertRaises(ValidationError):
            self._preview(operation={"tool": "query_mass_properties", "args": {}})

    def test_script_exec_is_not_previewable(self):
        self.assertNotIn("script_exec", self.op_table)
        with self.assertRaises(ValidationError):
            self._preview(operation={"tool": "script_exec", "args": {"code": "1"}})

    def test_a_missing_operation_is_invalid_input(self):
        with self.assertRaises(ValidationError):
            preview.preview_dry_run(self.registry, self.op_table, None, doc=self.handle)

    def test_an_operation_without_a_tool_name_is_invalid_input(self):
        with self.assertRaises(ValidationError):
            self._preview(operation={"args": {}})

    def test_an_operation_carrying_its_own_doc_is_invalid_input(self):
        op = _fillet_op()
        op["args"]["doc"] = "fcb-doc:someone-elses"
        with self.assertRaises(ValidationError):
            self._preview(operation=op)

    def test_a_rejected_tool_creates_no_tempdoc(self):
        with self.assertRaises(ValidationError):
            self._preview(operation={"tool": "feature_bogus", "args": {}})
        self.assertEqual(self._new_leftovers(), set())
        self.assertEqual(list(App.listDocuments().keys()), [self.document.Name])

    def test_bad_args_for_a_real_tool_leave_no_tempdoc(self):
        with self.assertRaises(ValidationError):
            self._preview(operation=_fillet_op(radius=-5.0))
        self.assertEqual(self._new_leftovers(), set())
        self.assertEqual(list(App.listDocuments().keys()), [self.document.Name])


class FailingOperationTest(_PreviewFixture):
    """An op that fails on the copy is a successful preview reporting a failing diff."""

    def test_a_failing_op_still_returns_an_ok_envelope(self):
        envelope = self._preview(operation=_fillet_op(radius=500.0))
        self.assertEqual(envelope["status"], "OK")
        self.assertIsNotNone(envelope["structured_content"]["preview_id"])

    def test_a_failing_op_reports_the_ops_terminal_status(self):
        diff = self._diff(operation=_fillet_op(radius=500.0))
        self.assertEqual(diff["validity"]["status"], "RECOMPUTE_ERROR")

    def test_a_failing_op_never_reports_is_valid_false_without_a_reason(self):
        diff = self._diff(operation=_fillet_op(radius=500.0))
        validity = diff["validity"]
        self.assertFalse(validity["is_valid"])
        self.assertTrue(
            validity["explanation"] or validity["recompute_errors"],
            "is_valid:false must carry an explanation or a named recompute error",
        )
        self.assertIn("BRep_API", validity["explanation"])

    def test_a_failing_op_names_the_object_its_recompute_broke(self):
        diff = self._diff(operation=_fillet_op(radius=500.0))
        names = [entry["object"] for entry in diff["validity"]["recompute_errors"]]
        self.assertEqual(names, ["Fillet"])

    def test_a_successful_op_reports_ok_and_no_explanation(self):
        validity = self._diff()["validity"]
        self.assertEqual(validity["status"], "OK")
        self.assertIsNone(validity["explanation"])
        self.assertEqual(validity["recompute_errors"], [])


class PreExistingBreakageTest(_PreviewFixture):
    """Breakage that predates the preview never flips the op's own verdict."""

    def _break_an_unrelated_object(self):
        extrusion = self.document.addObject("Part::Extrusion", "BadExtrude")
        extrusion.Base = None
        self.document.recompute()
        return extrusion

    def test_a_successful_op_stays_valid_when_an_unrelated_object_is_already_broken(self):
        self._break_an_unrelated_object()
        validity = self._diff()["validity"]
        self.assertTrue(validity["is_valid"])
        self.assertTrue(validity["recompute_clean"])

    def test_recompute_errors_never_names_an_object_the_op_did_not_touch(self):
        broken = self._break_an_unrelated_object()
        validity = self._diff()["validity"]
        names = [entry["object"] for entry in validity["recompute_errors"]]
        self.assertNotIn(broken.Name, names)

    def test_pre_existing_breakage_appears_in_its_own_field(self):
        broken = self._break_an_unrelated_object()
        validity = self._diff()["validity"]
        names = [entry["object"] for entry in validity["pre_existing_errors"]]
        self.assertIn(broken.Name, names)

    def test_a_clean_document_reports_no_pre_existing_errors(self):
        self.assertEqual(self._diff()["validity"]["pre_existing_errors"], [])

    def test_discounting_pre_existing_breakage_never_hides_a_real_op_failure(self):
        """The discount must not rescue an op that broke something itself."""
        broken = self._break_an_unrelated_object()
        validity = self._diff(operation=_fillet_op(radius=500.0))["validity"]
        self.assertFalse(validity["is_valid"], "the op's own failure must survive the discount")
        self.assertEqual(validity["status"], "RECOMPUTE_ERROR")
        names = [entry["object"] for entry in validity["recompute_errors"]]
        self.assertIn("Fillet", names)
        self.assertNotIn(broken.Name, names)
        self.assertIn(broken.Name, [e["object"] for e in validity["pre_existing_errors"]])


class TouchedProvenanceTest(_PreviewFixture):
    """``touched`` is what the op reported touching, not every object that survived."""

    def test_touched_excludes_the_origin_features_the_op_never_wrote(self):
        touched = self._diff()["touched"]
        for untouched in ("X_Axis", "Y_Axis", "Z_Axis", "XY_Plane", "XZ_Plane", "YZ_Plane"):
            self.assertNotIn(untouched, touched)
        self.assertNotIn("Origin001", touched)
        self.assertNotIn("Origin", touched)

    def test_touched_is_not_the_surviving_name_set(self):
        diff = self._diff()
        survivors = {o.Name for o in self.document.Objects}
        self.assertNotEqual(set(diff["touched"]), survivors)
        self.assertLess(len(diff["touched"]), len(survivors))

    def test_touched_names_the_feature_the_op_created(self):
        self.assertIn("Fillet", self._diff()["touched"])

    def test_touched_holds_only_names_that_still_exist_on_the_copy(self):
        diff = self._diff()
        self.assertTrue(set(diff["touched"]).issubset(set(diff["touched"]) | set(diff["new"])))
        for name in diff["touched"]:
            self.assertNotIn(name, diff["deleted"])


class TnpPrecheckTest(_PreviewFixture):
    def test_the_precheck_carries_the_closed_status_vocabulary(self):
        status = self._diff()["tnp_precheck"]["status"]
        self.assertIn(status, ("CLEAN", "FLAGGED", "UNSUPPORTED"))

    def test_the_precheck_is_the_copys_own_audit_block_verbatim(self):
        block = self._diff()["tnp_precheck"]
        self.assertEqual(sorted(block), ["counts", "element_map_version", "findings", "status"])
        self.assertEqual([f for f in block["findings"] if f["verdict"] == "PASS"], [])

    def test_an_op_that_produced_no_post_verify_is_unsupported_never_clean(self):
        """ "we did not look" and "we looked and saw nothing" are different answers (AD-7)."""
        self.assertTrue(
            shim.element_map_available(),
            "this test is meaningful only where the map IS available",
        )

        def blockless_op(registry, doc=None, **kwargs):  # noqa: ARG001
            return {
                "schema": "fcb.result-envelope/1",
                "status": "OK",
                "detail": None,
                "structured_content": {},
                "text": "",
            }

        envelope = preview.preview_dry_run(
            self.registry,
            {"feature_fillet": blockless_op},
            None,
            doc=self.handle,
            operation=_fillet_op(),
        )
        block = envelope["structured_content"]["diff"]["tnp_precheck"]
        self.assertEqual(block["status"], "UNSUPPORTED")
        self.assertNotEqual(block["status"], "CLEAN")
        self.assertEqual(sorted(block), ["counts", "element_map_version", "findings", "status"])
        self.assertEqual(block["counts"], {})

    def test_no_finding_claims_pass_when_the_audit_did_not_run(self):
        block = preview._unrun_audit()
        self.assertEqual(block["status"], "UNSUPPORTED")
        self.assertEqual([f for f in block["findings"] if f.get("verdict") == "PASS"], [])


class MetricSelectionTest(_PreviewFixture):
    """The diff measures model results only: no container echo, no consumed base, no datum."""

    def test_a_partdesign_chain_measures_only_its_tip(self):
        fillet = self.document.addObject("PartDesign::Fillet", "Fillet")
        self.body.addObject(fillet)
        fillet.Base = (self.pad, ["Edge1"])
        fillet.Radius = FILLET_RADIUS
        self.document.recompute()
        self.assertEqual(preview.metric_objects(self.document), ["Fillet"])

    def test_the_body_container_is_not_measured_beside_its_tip(self):
        names = preview.metric_objects(self.document)
        self.assertEqual(names, ["Pad"])
        self.assertNotIn("Body", names)

    def test_no_origin_feature_is_measured(self):
        names = preview.metric_objects(self.document)
        for origin in ("X_Axis", "XY_Plane", "XZ_Plane", "YZ_Plane", "Origin001"):
            self.assertNotIn(origin, names)

    def test_a_partdesign_datum_plane_is_not_measured(self):
        for type_id, name in (
            ("PartDesign::Plane", "DatumPlane"),
            ("PartDesign::Line", "DatumLine"),
            ("PartDesign::Point", "DatumPoint"),
            ("PartDesign::CoordinateSystem", "LCS"),
        ):
            datum = self.document.addObject(type_id, name)
            self.body.addObject(datum)
        self.document.recompute()
        names = preview.metric_objects(self.document)
        self.assertEqual(names, ["Pad"])

    def test_a_datum_does_not_cancel_the_real_area_delta(self):
        """A datum contributes area 8e+100 to both sides, which would cancel to exactly 0.0."""
        datum = self.document.addObject("PartDesign::Plane", "DatumPlane")
        self.body.addObject(datum)
        self.document.recompute()
        area = self._diff()["deltas"]["area"]
        self.assertNotEqual(area["delta"], 0.0)
        self.assertLess(area["delta"], 0.0)
        self.assertAlmostEqual(area["before"], PAD_AREA, places=6)

    def test_two_loose_solids_are_both_measured(self):
        doc = App.newDocument("loose")
        try:
            doc.addObject("Part::Box", "Box")
            second = doc.addObject("Part::Box", "Box2")
            second.Placement.Base = App.Vector(20, 0, 0)
            doc.recompute()
            self.assertEqual(preview.metric_objects(doc), ["Box", "Box2"])
        finally:
            App.closeDocument(doc.Name)

    def test_a_boolean_supersedes_the_operands_it_consumed(self):
        """Visibility is not a usable filter here: Part::Cut leaves Box.Visibility True."""
        doc = App.newDocument("boolean")
        try:
            base = doc.addObject("Part::Box", "Box")
            tool = doc.addObject("Part::Box", "Box2")
            tool.Placement.Base = App.Vector(5, 0, 0)
            cut = doc.addObject("Part::Cut", "Cut")
            cut.Base = base
            cut.Tool = tool
            doc.recompute()
            self.assertEqual(preview.metric_objects(doc), ["Cut"])
            self.assertTrue(base.Visibility, "the consumed operand is still visible")
        finally:
            App.closeDocument(doc.Name)

    def test_a_multifuse_link_list_supersedes_its_members(self):
        doc = App.newDocument("fuse")
        try:
            first = doc.addObject("Part::Box", "Box")
            second = doc.addObject("Part::Box", "Box2")
            second.Placement.Base = App.Vector(5, 0, 0)
            fusion = doc.addObject("Part::MultiFuse", "Fusion")
            fusion.Shapes = [first, second]
            doc.recompute()
            self.assertEqual(preview.metric_objects(doc), ["Fusion"])
        finally:
            App.closeDocument(doc.Name)

    def test_metric_objects_sums_the_tip_volume_once(self):
        metrics = preview.document_metrics(self.document)
        self.assertAlmostEqual(metrics["volume"], PAD_VOLUME, places=6)
        self.assertEqual(metrics["counts"], PAD_COUNTS)


class EmptyDocumentTest(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create("empty")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def test_a_document_with_no_shape_bearing_object_reports_zeroed_metrics(self):
        metrics = preview.document_metrics(self.document)
        self.assertEqual(metrics["volume"], 0.0)
        self.assertEqual(metrics["area"], 0.0)
        self.assertEqual(metrics["counts"], {"faces": 0, "edges": 0, "vertices": 0, "solids": 0})
        self.assertEqual(metrics["bbox"], [0.0] * 6)

    def test_an_empty_document_previews_with_zero_valued_deltas_not_absent_keys(self):
        def creating_op(registry, doc=None, **kwargs):  # noqa: ARG001
            return {
                "schema": "fcb.result-envelope/1",
                "status": "OK",
                "detail": None,
                "structured_content": {"mutation": {"touched": [], "post_verify": None}},
                "text": "",
            }

        envelope = preview.preview_dry_run(
            self.registry,
            {"feature_pad": creating_op},
            None,
            doc=self.handle,
            operation={"tool": "feature_pad", "args": {}},
        )
        diff = envelope["structured_content"]["diff"]
        for key in ("faces", "edges", "vertices", "solids"):
            self.assertIn(key, diff["counts"])
            self.assertEqual(diff["counts"][key]["delta"], 0)
        for key in ("volume", "area", "bbox", "com"):
            self.assertIn(key, diff["deltas"])


class DeletedObjectTest(_PreviewFixture):
    def test_an_op_that_removes_an_object_reports_it_deleted(self):
        def deleting_op(registry, doc=None, **kwargs):  # noqa: ARG001
            copy = registry.with_document(doc, lambda h, d: d)
            copy.removeObject("Pad")
            copy.recompute()
            return {
                "schema": "fcb.result-envelope/1",
                "status": "OK",
                "detail": None,
                "structured_content": {"mutation": {"touched": ["Pad"], "post_verify": None}},
                "text": "",
            }

        envelope = preview.preview_dry_run(
            self.registry,
            {"feature_pad": deleting_op},
            None,
            doc=self.handle,
            operation={"tool": "feature_pad", "args": {}},
        )
        diff = envelope["structured_content"]["diff"]
        self.assertIn("Pad", diff["deleted"])
        self.assertNotIn("Pad", diff["touched"])
        self.assertEqual(diff["counts"]["solids"]["after"], 0)


class RenderTest(_PreviewFixture):
    def test_render_off_is_an_explicit_opt_out_not_a_missing_capability(self):
        block = self._diff(render="off")["render"]
        self.assertFalse(block["available"])
        self.assertEqual(block["reason"], "off")

    def test_an_unavailable_render_is_not_an_error(self):
        class _Unavailable:
            def available(self):
                return False, "no GL in this process"

        envelope = self._preview(render_port=_Unavailable())
        self.assertEqual(envelope["status"], "OK")
        block = envelope["structured_content"]["diff"]["render"]
        self.assertFalse(block["available"])
        self.assertEqual(block["reason"], "no GL in this process")

    def test_the_diff_is_complete_without_a_render(self):
        diff = self._diff(render="off")
        for key in ("deltas", "counts", "validity", "tnp_precheck"):
            self.assertIn(key, diff)

    def test_no_image_bytes_travel_inside_the_diff(self):
        block = self._diff()["render"]
        self.assertEqual(sorted(block), ["available", "reason"])


class SharedShapeMetricsTest(_PreviewFixture):
    """``queries.shape_metrics`` is the one reader; ``query_mass_properties`` keeps its shape."""

    def test_shape_metrics_reads_the_vertex_count_mass_properties_never_did(self):
        metrics = queries.shape_metrics(self.pad.Shape)
        self.assertEqual(metrics["counts"]["vertices"], PAD_COUNTS["vertices"])

    def test_query_mass_properties_now_reports_vertices_alongside_the_existing_counts(self):
        envelope = queries.query_mass_properties(self.registry, doc=self.handle, object="Pad")
        counts = envelope["structured_content"]["counts"]
        self.assertEqual(counts, PAD_COUNTS)

    def test_query_mass_properties_still_reports_null_com_for_a_compound(self):
        """A compound of solids IS a solid but has no CenterOfMass; the bbox centre
        must not ship."""
        compound = self.document.addObject("Part::Feature", "Compound")
        box = Part.makeBox(2, 3, 4)
        compound.Shape = Part.makeCompound([box, box.copy().translate(App.Vector(5, 0, 0))])
        self.document.recompute()
        metrics = queries.shape_metrics(compound.Shape)
        self.assertTrue(metrics["solid"], "a compound of two solids reports len(Solids) == 2")
        self.assertFalse(metrics["com_readable"], "and has no readable CenterOfMass")
        envelope = queries.query_mass_properties(self.registry, doc=self.handle, object="Compound")
        self.assertIsNone(envelope["structured_content"]["com"])

    def test_query_mass_properties_still_reports_null_volume_for_a_non_solid(self):
        shell = self.document.addObject("Part::Feature", "Shell")
        shell.Shape = Part.makeBox(1, 1, 1).Shells[0]
        self.document.recompute()
        envelope = queries.query_mass_properties(self.registry, doc=self.handle, object="Shell")
        self.assertIsNone(envelope["structured_content"]["volume"])

    def test_query_mass_properties_reports_a_real_com_for_a_plain_solid(self):
        envelope = queries.query_mass_properties(self.registry, doc=self.handle, object="Pad")
        com = envelope["structured_content"]["com"]
        self.assertIsNotNone(com)
        self.assertAlmostEqual(com["x"]["value"], SQUARE / 2, places=6)

    def test_shape_metrics_gives_an_open_shape_a_summable_number_never_none(self):
        """A ScalarDelta carries four non-optional floats, so no reading may be ``None``."""
        metrics = queries.shape_metrics(Part.makeBox(1, 1, 1).Faces[0])
        self.assertFalse(metrics["solid"])
        self.assertEqual(metrics["volume"], 0.0)
        self.assertGreater(metrics["area"], 0.0)
        self.assertEqual(len(metrics["com"]), 3)
        for value in metrics["com"]:
            self.assertIsInstance(value, float)


class AuditTest(_PreviewFixture):
    class _Sink:
        def __init__(self):
            self.records = []

        def before(self, event, tool, doc, params, **kwargs):
            self.records.append(("before", event, tool, doc))

        def after(self, event, tool, doc, params, verdict, **kwargs):
            self.records.append(("after", event, tool, doc, verdict))

    def test_a_preview_writes_a_before_and_an_after_record_with_the_preview_event(self):
        sink = self._Sink()
        self._preview(audit_sink=sink)
        self.assertEqual(len(sink.records), 2)
        self.assertEqual(sink.records[0][:3], ("before", "preview", "feature_fillet"))
        self.assertEqual(sink.records[1][:3], ("after", "preview", "feature_fillet"))
        self.assertEqual(sink.records[1][4], "OK")

    def test_an_unwritable_sink_does_not_abort_the_preview(self):
        class _Broken:
            def before(self, *args, **kwargs):
                raise OSError("disk full")

            def after(self, *args, **kwargs):
                raise OSError("disk full")

        envelope = self._preview(audit_sink=_Broken())
        self.assertEqual(envelope["status"], "OK")

    def test_no_sink_writes_no_record_and_still_succeeds(self):
        self.assertEqual(self._preview(audit_sink=None)["status"], "OK")


if __name__ == "__main__":
    unittest.main()
