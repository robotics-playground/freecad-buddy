"""In-FreeCAD tests for the export writers and the FreeCAD-side verify legs (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Golden values are analytic (box 10x20x30 -> volume
6000, 6 faces, 12 edges, 1 solid), never captured from the implementation. Covers the
``export_step`` -> ``verify_export_step`` round-trip (volume +-0.1%, exact counts, banner), that
``export_stl`` and ``export_3mf`` share one tessellation (identical facet count), that every
export result carries ``verified: false``, the self-read facts, and the bad ``export_id`` /
``doc`` INVALID_INPUT boundary.
"""

import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import FreeCAD as App
import Part

from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.usecases import exports, shim
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.exports import ExportRegistry

BOX_L = 10.0
BOX_W = 20.0
BOX_H = 30.0
ANALYTIC_VOLUME = BOX_L * BOX_W * BOX_H  # 6000 mm^3
ANALYTIC_FACES = 6
ANALYTIC_EDGES = 12
ANALYTIC_SOLIDS = 1
AP242_FILE_SCHEMA_PREFIX = "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING"
STEP_PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/Part/STEP"
INCH_UNIT = "CONVERSION_BASED_UNIT('INCH'"


class _ExportFixture(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.exports = ExportRegistry()
        self.handle = self.registry.document_create("export_tools")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))
        self.tmp = Path(tempfile.mkdtemp(prefix="FCB_TMP_export_test_"))

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _add_box(self, name="Box"):
        box = self.document.addObject("Part::Box", name)
        box.Length = BOX_L
        box.Width = BOX_W
        box.Height = BOX_H
        self.document.recompute()
        return box


class ExportStepTest(_ExportFixture):
    def test_export_step_reports_verified_false(self):
        self._add_box()
        path = str(self.tmp / "box.step")
        content = exports.export_step(self.registry, self.exports, doc=self.handle, path=path)[
            "structured_content"
        ]
        self.assertFalse(content["verified"])
        self.assertGreater(content["bytes"], 0)
        self.assertTrue(Path(path).exists())

    def test_verify_export_step_round_trip_passes_with_banner(self):
        self._add_box()
        path = str(self.tmp / "box.step")
        export_id = exports.export_step(self.registry, self.exports, doc=self.handle, path=path)[
            "structured_content"
        ]["export_id"]

        envelope = exports.verify_export_step(
            self.registry, self.exports, doc=self.handle, export_id=export_id
        )
        content = envelope["structured_content"]
        self.assertEqual(content["verdict"], "OK")
        self.assertEqual(envelope["status"], "OK")
        by_id = {c["id"]: c for c in content["checks"]}
        volume = by_id["export_step.volume"]
        self.assertLessEqual(abs(volume["measured"] - ANALYTIC_VOLUME) / ANALYTIC_VOLUME, 0.001)
        self.assertTrue(by_id["export_step.topology_counts"]["passed"])
        self.assertEqual(content["banner"]["freecad_version"], _freecad_version())
        self.assertIn("element_map_version", content["banner"])

    def test_verify_export_step_detects_dropped_solid(self):
        self._add_box()
        path = str(self.tmp / "box.step")
        export_id = exports.export_step(self.registry, self.exports, doc=self.handle, path=path)[
            "structured_content"
        ]["export_id"]
        # Corrupt the recorded source so the re-import deviates: pretend the source had 2 solids.
        self.exports._by_id[export_id]["source"]["solids"] = 2

        envelope = exports.verify_export_step(
            self.registry, self.exports, doc=self.handle, export_id=export_id
        )
        self.assertNotEqual(envelope["status"], "OK")
        self.assertIsNotNone(envelope["detail"])


class ExportStepSchemaTest(_ExportFixture):
    def setUp(self):
        super().setUp()
        self.step_preferences = App.ParamGet(STEP_PARAM_PATH)
        self.saved_scheme = (
            self.step_preferences.GetString("Scheme")
            if "Scheme" in self.step_preferences.GetStrings()
            else None
        )
        self.saved_unit = Part.exportUnits()["write.step.unit"]

    def tearDown(self):
        if self.saved_scheme is None:
            self.step_preferences.RemString("Scheme")
        else:
            self.step_preferences.SetString("Scheme", self.saved_scheme)
        shim.restore_step_config(self.saved_unit)
        super().tearDown()

    def _export(self, name, **params):
        path = str(self.tmp / name)
        export_id = exports.export_step(
            self.registry, self.exports, doc=self.handle, path=path, **params
        )["structured_content"]["export_id"]
        return path, export_id

    def _verify(self, export_id):
        envelope = exports.verify_export_step(
            self.registry, self.exports, doc=self.handle, export_id=export_id
        )
        by_id = {c["id"]: c for c in envelope["structured_content"]["checks"]}
        return envelope, by_id

    def test_should_write_ap242_file_schema_and_pass_schema_check_when_ap242_requested(self):
        # Arrange
        self._add_box()

        # Act
        path, export_id = self._export("box.step", ap="AP242")
        envelope, by_id = self._verify(export_id)

        # Assert
        self.assertTrue(_file_schema_text(path).startswith(AP242_FILE_SCHEMA_PREFIX))
        self.assertEqual(envelope["status"], "OK")
        self.assertTrue(by_id["export_step.schema"]["passed"])

    def test_should_write_ap242_file_schema_when_ap_omitted(self):
        # Arrange
        self._add_box()

        # Act
        path, export_id = self._export("box.step")
        envelope, by_id = self._verify(export_id)

        # Assert
        self.assertTrue(_file_schema_text(path).startswith(AP242_FILE_SCHEMA_PREFIX))
        self.assertEqual(envelope["status"], "OK")
        self.assertTrue(by_id["export_step.schema"]["passed"])

    def test_should_write_automotive_design_when_ap214_follows_an_ap242_export(self):
        # Arrange
        self._add_box()
        self._export("first.step", ap="AP242")

        # Act
        path, export_id = self._export("second.step", ap="AP214")
        envelope, by_id = self._verify(export_id)

        # Assert
        self.assertTrue(_file_schema_text(path).startswith("AUTOMOTIVE_DESIGN"))
        self.assertEqual(envelope["status"], "OK")
        self.assertTrue(by_id["export_step.schema"]["passed"])

    def test_should_fail_schema_check_when_recorded_ap_differs_from_file(self):
        # Arrange
        self._add_box()
        _, export_id = self._export("box.step", ap="AP214")
        self.exports._by_id[export_id]["ap"] = "AP242"

        # Act
        envelope, by_id = self._verify(export_id)

        # Assert
        self.assertNotEqual(envelope["status"], "OK")
        self.assertFalse(by_id["export_step.schema"]["passed"])
        self.assertEqual(by_id["export_step.schema"]["measured"], "AUTOMOTIVE_DESIGN")

    def test_should_fail_schema_check_with_null_measured_when_file_has_no_file_schema(self):
        # Arrange
        self._add_box()
        path, export_id = self._export("box.step", ap="AP242")
        lines = Path(path).read_text(encoding="ascii").splitlines(keepends=True)
        header_end = next(i for i, line in enumerate(lines) if line.startswith("ENDSEC;"))
        start = next(i for i, line in enumerate(lines) if line.startswith("FILE_SCHEMA"))
        Path(path).write_text("".join(lines[:start] + lines[header_end:]), encoding="ascii")

        # Act
        envelope, by_id = self._verify(export_id)

        # Assert
        self.assertNotEqual(envelope["status"], "OK")
        self.assertFalse(by_id["export_step.schema"]["passed"])
        self.assertIsNone(by_id["export_step.schema"]["measured"])

    def test_should_restore_occ_default_schema_when_scheme_preference_unset(self):
        # Arrange
        self._add_box()
        self.step_preferences.RemString("Scheme")
        self._export("bridge.step", ap="AP242")
        plain_path = str(self.tmp / "plain.step")

        # Act
        Part.makeBox(BOX_L, BOX_W, BOX_H).exportStep(plain_path)

        # Assert
        self.assertTrue(_file_schema_text(plain_path).startswith("AUTOMOTIVE_DESIGN"))

    def test_should_restore_occ_default_schema_when_export_step_raises(self):
        # Arrange
        self._add_box()
        self.step_preferences.RemString("Scheme")
        with self.assertRaisesRegex(Exception, "Writing of STEP failed"):
            self._export("missing-folder/bridge.step", ap="AP242")
        plain_path = str(self.tmp / "plain.step")

        # Act
        Part.makeBox(BOX_L, BOX_W, BOX_H).exportStep(plain_path)

        # Assert
        self.assertTrue(_file_schema_text(plain_path).startswith("AUTOMOTIVE_DESIGN"))

    def test_should_restore_scheme_preference_when_it_is_supported(self):
        # Arrange
        self._add_box()
        self.step_preferences.SetString("Scheme", "AP242DIS")
        self._export("bridge.step", ap="AP214")
        plain_path = str(self.tmp / "plain.step")

        # Act
        Part.makeBox(BOX_L, BOX_W, BOX_H).exportStep(plain_path)

        # Assert
        self.assertTrue(_file_schema_text(plain_path).startswith(AP242_FILE_SCHEMA_PREFIX))

    def test_should_restore_occ_default_schema_when_scheme_preference_unsupported(self):
        # Arrange
        self._add_box()
        self.step_preferences.SetString("Scheme", "AP242")
        self._export("bridge.step", ap="AP242")
        plain_path = str(self.tmp / "plain.step")

        # Act
        Part.makeBox(BOX_L, BOX_W, BOX_H).exportStep(plain_path)

        # Assert
        self.assertTrue(_file_schema_text(plain_path).startswith("AUTOMOTIVE_DESIGN"))

    def test_should_leave_scheme_preference_unchanged_when_exporting(self):
        # Arrange
        self._add_box()
        sentinel = "FCB_SENTINEL_SCHEME"
        self.step_preferences.SetString("Scheme", sentinel)

        # Act
        self._export("ap242.step", ap="AP242")
        self._export("ap214.step", ap="AP214")

        # Assert
        self.assertEqual(self.step_preferences.GetString("Scheme"), sentinel)

    def test_should_restore_prior_step_unit_and_write_bridge_file_in_mm_when_exporting(self):
        # Arrange
        self._add_box()
        Part.setStaticValue("write.step.unit", "INCH")
        plain_path = str(self.tmp / "plain.step")

        # Act
        bridge_path, _ = self._export("bridge.step", ap="AP242")
        Part.makeBox(BOX_L, BOX_W, BOX_H).exportStep(plain_path)

        # Assert
        self.assertEqual(Part.exportUnits()["write.step.unit"], "INCH")
        self.assertNotIn(INCH_UNIT, Path(bridge_path).read_text(encoding="ascii"))
        self.assertIn(INCH_UNIT, Path(plain_path).read_text(encoding="ascii"))

    def test_should_restore_prior_step_unit_when_export_step_raises(self):
        # Arrange
        self._add_box()
        Part.setStaticValue("write.step.unit", "INCH")

        # Act
        with self.assertRaisesRegex(Exception, "Writing of STEP failed"):
            self._export("missing-folder/bridge.step", ap="AP242")

        # Assert
        self.assertEqual(Part.exportUnits()["write.step.unit"], "INCH")


class ExportMeshTest(_ExportFixture):
    def test_stl_and_3mf_share_one_tessellation(self):
        self._add_box()
        stl = exports.export_stl(
            self.registry, self.exports, doc=self.handle, path=str(self.tmp / "b.stl")
        )["structured_content"]
        tmf = exports.export_3mf(
            self.registry, self.exports, doc=self.handle, path=str(self.tmp / "b.3mf")
        )["structured_content"]
        self.assertEqual(stl["facets"], tmf["facets"])
        self.assertFalse(stl["verified"])
        self.assertFalse(tmf["verified"])

    def test_self_read_stl_returns_facts(self):
        self._add_box()
        export_id = exports.export_stl(
            self.registry, self.exports, doc=self.handle, path=str(self.tmp / "b.stl")
        )["structured_content"]["export_id"]
        content = exports.export_self_read_stl(
            self.registry, self.exports, doc=self.handle, export_id=export_id
        )["structured_content"]
        self.assertEqual(content["self_read"]["facets"], content["recorded"]["facets"])
        self.assertEqual(content["self_read"]["vertices"], content["recorded"]["vertices"])
        self.assertGreater(content["self_read"]["facets"], 0)
        self.assertIn("volume_band", content)
        self.assertIn("banner", content)

    def test_self_read_3mf_returns_facts(self):
        self._add_box()
        export_id = exports.export_3mf(
            self.registry, self.exports, doc=self.handle, path=str(self.tmp / "b.3mf")
        )["structured_content"]["export_id"]
        content = exports.export_self_read_3mf(
            self.registry, self.exports, doc=self.handle, export_id=export_id
        )["structured_content"]
        self.assertGreater(content["self_read"]["facets"], 0)

    def test_mesh_volume_band_is_not_step_tolerance(self):
        box_area = 2.0 * (BOX_L * BOX_W + BOX_L * BOX_H + BOX_W * BOX_H)
        band = exports.mesh_volume_band(0.1, box_area)
        self.assertNotEqual(band, ANALYTIC_VOLUME * 0.001)
        self.assertGreater(band, 0)


class MultiObjectExportTest(_ExportFixture):
    """Several objects, or none named, export to one file per format (tool-contracts T-5)."""

    def _add_three_bodies(self):
        alpha = self._add_box("BoxA")
        alpha.Label = "Alpha"
        beta = self.document.addObject("Part::Cylinder", "Cyl")
        beta.Label = "Beta"
        beta.Placement.Base = App.Vector(30, 0, 0)
        gamma = self.document.addObject("Part::Sphere", "Sph")
        gamma.Label = "Gamma"
        gamma.Placement.Base = App.Vector(0, 60, 0)
        self.document.recompute()
        return ["BoxA", "Cyl", "Sph"]

    def _export(self, tool, name, **params):
        path = str(self.tmp / name)
        envelope = tool(self.registry, self.exports, doc=self.handle, path=path, **params)
        return path, envelope

    def _verify_step(self, written):
        return exports.verify_export_step(
            self.registry,
            self.exports,
            doc=self.handle,
            export_id=written["structured_content"]["export_id"],
        )

    def _step_product_names(self, path):
        text = Path(path).read_text(errors="replace")
        return re.findall(r"PRODUCT\('[^']*','([^']*)'", text)

    def test_Should_pass_with_one_volume_check_per_object_When_three_objects_go_to_step(self):
        # Arrange
        names = self._add_three_bodies()
        path, written = self._export(exports.export_step, "three.step", objects=names)

        # Act
        target = self._verify_step(written)

        # Assert
        by_id = {c["id"]: c for c in target["structured_content"]["checks"]}
        self.assertEqual(target["status"], "OK")
        self.assertEqual(written["structured_content"]["objects"], names)
        for name in names:
            self.assertTrue(by_id[f"export_step.object_volume:{name}"]["passed"])
        self.assertTrue(by_id["export_step.objects_matched"]["passed"])
        products = self._step_product_names(path)
        for label in ("Alpha", "Beta", "Gamma"):
            self.assertIn(label, products)

    def test_Should_fail_and_name_the_object_When_one_recorded_object_volume_is_wrong(self):
        # Arrange
        names = self._add_three_bodies()
        _path, written = self._export(exports.export_step, "three.step", objects=names)
        export_id = written["structured_content"]["export_id"]
        self.exports._by_id[export_id]["source"]["objects"][1]["volume"] *= 2

        # Act
        target = self._verify_step(written)

        # Assert
        failed = [c["id"] for c in target["structured_content"]["checks"] if not c["passed"]]
        self.assertNotEqual(target["status"], "OK")
        self.assertIn("export_step.object_volume:Cyl", failed)
        self.assertNotIn("export_step.object_volume:BoxA", failed)
        self.assertIn("export_step.object_volume:Cyl", target["detail"]["message"])

    def test_Should_match_objects_in_order_When_one_object_holds_several_solids(self):
        # Arrange
        first = self.document.addObject("Part::Box", "B1")
        second = self.document.addObject("Part::Box", "B2")
        second.Placement.Base = App.Vector(50, 0, 0)
        fuse = self.document.addObject("Part::Fuse", "Fuse")
        fuse.Base = first
        fuse.Tool = second
        lone = self.document.addObject("Part::Sphere", "Sph")
        lone.Placement.Base = App.Vector(0, 80, 0)
        self.document.recompute()
        _path, written = self._export(exports.export_step, "fuse.step", objects=["Fuse", "Sph"])
        export_id = written["structured_content"]["export_id"]

        # Act
        target = self._verify_step(written)

        # Assert
        recorded = self.exports._by_id[export_id]["source"]["objects"]
        self.assertEqual(recorded[0]["solids"], 2)
        self.assertEqual(target["status"], "OK")

    def test_Should_export_only_the_body_and_free_solids_When_objects_are_omitted(self):
        # Arrange
        body = self.document.addObject("PartDesign::Body", "Body")
        sketch = body.newObject("Sketcher::SketchObject", "Sk")
        sketch.AttachmentSupport = (self.document.getObject("XY_Plane"), [""])
        sketch.MapMode = "FlatFace"
        corners = [(0, 0), (10, 0), (10, 10), (0, 10)]
        for index, (x, y) in enumerate(corners):
            nx, ny = corners[(index + 1) % 4]
            sketch.addGeometry(Part.LineSegment(App.Vector(x, y, 0), App.Vector(nx, ny, 0)))
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = sketch
        pad.Length = 5
        body.newObject("PartDesign::AdditiveBox", "Extra")
        free = self._add_box("Free")
        free.Placement.Base = App.Vector(40, 0, 0)
        left = self.document.addObject("Part::Box", "Left")
        right = self.document.addObject("Part::Box", "Right")
        right.Placement.Base = App.Vector(0, 40, 0)
        fuse = self.document.addObject("Part::Fuse", "Fuse")
        fuse.Base = left
        fuse.Tool = right
        self.document.recompute()

        # Act
        _path, target = self._export(exports.export_step, "all.step")

        # Assert
        self.assertEqual(target["structured_content"]["objects"], ["Body", "Free", "Fuse"])

    def test_Should_keep_a_solid_that_only_an_expression_or_attachment_references_When_omitted(
        self,
    ):
        # Arrange
        base = self._add_box("Base")
        driven = self._add_box("Driven")
        driven.Placement.Base = App.Vector(30, 0, 0)
        driven.setExpression("Length", "Base.Length")
        attached = self.document.addObject("Part::Cylinder", "Attached")
        attached.Placement.Base = App.Vector(0, 40, 0)
        attached.AttachmentSupport = [(base, "Face1")]
        self.document.recompute()

        # Act
        _path, target = self._export(exports.export_step, "all.step")

        # Assert
        self.assertEqual(target["structured_content"]["objects"], ["Base", "Driven", "Attached"])

    def test_Should_export_the_sole_object_When_it_is_hidden_and_objects_are_omitted(self):
        # Arrange
        box = self._add_box("Only")
        box.Visibility = False

        # Act
        _path, target = self._export(exports.export_step, "only.step")

        # Assert
        self.assertEqual(target["structured_content"]["objects"], ["Only"])

    def test_Should_fail_the_match_check_When_a_recorded_object_holds_more_solids(self):
        # Arrange
        names = self._add_three_bodies()
        _path, written = self._export(exports.export_step, "three.step", objects=names)
        export_id = written["structured_content"]["export_id"]
        self.exports._by_id[export_id]["source"]["objects"][0]["solids"] = 2

        # Act
        target = self._verify_step(written)

        # Assert
        by_id = {c["id"]: c for c in target["structured_content"]["checks"]}
        self.assertNotEqual(target["status"], "OK")
        self.assertFalse(by_id["export_step.objects_matched"]["passed"])

    def test_Should_leave_no_file_When_naming_the_3mf_objects_fails(self):
        # Arrange
        names = self._add_three_bodies()
        path = self.tmp / "failed.3mf"

        # Act
        with mock.patch.object(exports, "_name_3mf_objects", side_effect=RuntimeError("boom")):
            act = lambda: exports.export_3mf(  # noqa: E731
                self.registry, self.exports, doc=self.handle, path=str(path), objects=names
            )
            with self.assertRaises(RuntimeError):
                act()

        # Assert
        self.assertFalse(path.exists())

    def test_Should_record_one_facet_count_per_object_When_touching_objects_go_to_stl(self):
        # Arrange
        first = self._add_box("First")
        second = self._add_box("Second")
        second.Placement.Base = App.Vector(BOX_L, 0, 0)
        self.document.recompute()

        # Act
        _path, written = self._export(exports.export_stl, "touch.stl", objects=["First", "Second"])
        export_id = written["structured_content"]["export_id"]
        target = exports.export_self_read_stl(
            self.registry, self.exports, doc=self.handle, export_id=export_id
        )["structured_content"]

        # Assert
        self.assertEqual(target["facet_counts"], [12, 12])
        self.assertEqual(target["self_read"]["facets"], 24)
        self.assertEqual(first.Shape.Volume + second.Shape.Volume, target["source"]["volume"])

    def _add_body_with_box(self, name):
        body = self.document.addObject("PartDesign::Body", name)
        body.newObject("PartDesign::AdditiveBox", f"{name}Box")
        self.document.recompute()
        return body

    def test_Should_export_only_the_cut_When_a_boolean_hides_two_bodies_in_the_gui_way(self):
        # Arrange
        first = self._add_body_with_box("B1")
        second = self._add_body_with_box("B2")
        second.Placement.Base = App.Vector(5, 0, 0)
        cut = self.document.addObject("Part::Cut", "Cut")
        cut.Base = first
        cut.Tool = second
        first.Visibility = False
        second.Visibility = False
        self.document.recompute()

        # Act
        _path, target = self._export(exports.export_step, "cut.step")

        # Assert
        self.assertEqual(target["structured_content"]["objects"], ["Cut"])

    def test_Should_skip_the_tip_of_a_hidden_body_When_objects_are_omitted(self):
        # Arrange
        body = self._add_body_with_box("Hidden")
        body.Visibility = False
        self._add_box("Shown")

        # Act
        _path, target = self._export(exports.export_step, "shown.step")

        # Assert
        self.assertEqual(target["structured_content"]["objects"], ["Shown"])

    def test_Should_skip_a_solid_inside_a_hidden_part_When_objects_are_omitted(self):
        # Arrange
        part = self.document.addObject("App::Part", "Asm")
        inner = self._add_box("Inner")
        part.addObject(inner)
        part.Visibility = False
        self._add_box("Shown")

        # Act
        _path, target = self._export(exports.export_step, "shown.step")

        # Assert
        self.assertEqual(target["structured_content"]["objects"], ["Shown"])

    def test_Should_export_a_visible_mirror_source_with_the_mirror_When_objects_are_omitted(self):
        # Arrange
        box = self._add_box("Source")
        mirror = self.document.addObject("Part::Mirroring", "Mirror")
        mirror.Source = box
        mirror.Base = App.Vector(20, 0, 0)
        mirror.Normal = App.Vector(1, 0, 0)
        self.document.recompute()

        # Act
        _path, target = self._export(exports.export_step, "mirror.step")

        # Assert
        self.assertEqual(target["structured_content"]["objects"], ["Source", "Mirror"])

    def test_Should_name_each_object_and_verify_When_two_objects_share_one_shape(self):
        # Arrange
        box = self._add_box("Box")
        copy = self.document.addObject("Part::Feature", "Copy")
        copy.Shape = box.Shape
        copy.Placement.Base = App.Vector(40, 0, 0)
        self.document.recompute()
        path, written = self._export(exports.export_step, "shared.step", objects=["Box", "Copy"])

        # Act
        target = self._verify_step(written)

        # Assert
        by_id = {c["id"]: c for c in target["structured_content"]["checks"]}
        products = self._step_product_names(path)
        self.assertEqual(target["status"], "OK")
        self.assertIn("Box", products)
        self.assertIn("Copy", products)
        self.assertTrue(by_id["export_step.object_names"]["passed"])

    def test_Should_write_what_it_recorded_When_a_selected_part_holds_a_hidden_child(self):
        # Arrange
        part = self.document.addObject("App::Part", "Asm")
        shown = self._add_box("In1")
        hidden = self._add_box("In2")
        hidden.Placement.Base = App.Vector(30, 0, 0)
        part.addObject(shown)
        part.addObject(hidden)
        hidden.Visibility = False
        free = self.document.addObject("Part::Sphere", "Free")
        free.Placement.Base = App.Vector(0, 60, 0)
        self.document.recompute()
        _path, written = self._export(exports.export_step, "asm.step", objects=["Asm", "Free"])

        # Act
        target = self._verify_step(written)

        # Assert
        recorded = self.exports._by_id[written["structured_content"]["export_id"]]["source"]
        self.assertEqual(recorded["objects"][0]["solids"], 1)
        self.assertAlmostEqual(recorded["objects"][0]["volume"], ANALYTIC_VOLUME, places=6)
        self.assertEqual(target["status"], "OK")

    def test_Should_grade_only_the_solids_When_an_object_holds_a_solid_and_a_loose_face(self):
        # Arrange
        mixed = self.document.addObject("Part::Feature", "Mixed")
        mixed.Shape = Part.makeCompound([Part.makeBox(10, 10, 10), Part.makePlane(5, 5)])
        lone = self.document.addObject("Part::Sphere", "Sph")
        lone.Placement.Base = App.Vector(0, 60, 0)
        self.document.recompute()
        _path, written = self._export(exports.export_step, "mixed.step", objects=["Mixed", "Sph"])

        # Act
        target = self._verify_step(written)

        # Assert
        recorded = self.exports._by_id[written["structured_content"]["export_id"]]["source"]
        self.assertAlmostEqual(recorded["objects"][0]["volume"], 1000.0, places=6)
        self.assertEqual(recorded["objects"][0]["faces"], 6)
        self.assertEqual(recorded["faces"], 6 + 1)
        self.assertEqual(target["status"], "OK")

    def test_Should_fail_the_name_check_When_a_recorded_product_name_is_not_in_the_file(self):
        # Arrange
        names = self._add_three_bodies()
        _path, written = self._export(exports.export_step, "three.step", objects=names)
        export_id = written["structured_content"]["export_id"]
        self.exports._by_id[export_id]["source"]["objects"][2]["step_name"] = "Delta"

        # Act
        target = self._verify_step(written)

        # Assert
        by_id = {c["id"]: c for c in target["structured_content"]["checks"]}
        self.assertNotEqual(target["status"], "OK")
        self.assertFalse(by_id["export_step.object_names"]["passed"])
        self.assertIn("Delta", by_id["export_step.object_names"]["detail"]["message"])

    def test_Should_export_a_compound_and_not_its_visible_children_When_objects_are_omitted(self):
        # Arrange
        first = self._add_box("Child1")
        second = self._add_box("Child2")
        second.Placement.Base = App.Vector(30, 0, 0)
        compound = self.document.addObject("Part::Compound", "Cmp")
        compound.Links = [first, second]
        self.document.recompute()

        # Act
        _path, target = self._export(exports.export_step, "cmp.step")

        # Assert
        self.assertEqual(target["structured_content"]["objects"], ["Cmp"])

    def test_Should_pass_the_name_check_When_labels_are_long_or_hold_special_characters(self):
        # Arrange
        labels = ["L" * 120, "tab\there", "line\nbreak", "Al'pha\\x", "Khoi ø — 1"]
        names = []
        for index, label in enumerate(labels):
            box = self._add_box(f"Obj{index}")
            box.Label = label
            box.Placement.Base = App.Vector(30 * index, 0, 0)
            names.append(f"Obj{index}")
        self.document.recompute()
        _path, written = self._export(exports.export_step, "labels.step", objects=names)

        # Act
        target = self._verify_step(written)

        # Assert
        by_id = {c["id"]: c for c in target["structured_content"]["checks"]}
        self.assertTrue(
            by_id["export_step.object_names"]["passed"], by_id["export_step.object_names"]
        )
        self.assertEqual(target["status"], "OK")

    def test_Should_name_the_product_after_the_object_name_When_a_label_is_empty(self):
        # Arrange
        first = self._add_box("Blank")
        first.Label = ""
        second = self._add_box("Other")
        second.Placement.Base = App.Vector(30, 0, 0)
        self.document.recompute()
        path, written = self._export(exports.export_step, "blank.step", objects=["Blank", "Other"])

        # Act
        target = self._verify_step(written)

        # Assert
        self.assertEqual(target["status"], "OK")
        self.assertIn("Blank", self._step_product_names(path))

    def test_Should_name_the_root_product_after_the_document_When_several_objects_go_to_step(self):
        # Arrange
        names = self._add_three_bodies()

        # Act
        path, _written = self._export(exports.export_step, "root.step", objects=names)

        # Assert
        products = self._step_product_names(path)
        self.assertTrue(any(name.startswith(self.document.Name) for name in products), products)
        self.assertFalse(any(name.startswith("FCB_TMP") for name in products), products)

    def test_Should_record_the_file_name_When_a_3mf_label_holds_a_tab(self):
        # Arrange
        first = self._add_box("Tabbed")
        first.Label = "a\tb"
        second = self._add_box("Other")
        second.Placement.Base = App.Vector(30, 0, 0)
        self.document.recompute()
        _path, written = self._export(exports.export_3mf, "tab.3mf", objects=["Tabbed", "Other"])
        export_id = written["structured_content"]["export_id"]

        # Act
        target = exports.export_self_read_3mf(
            self.registry, self.exports, doc=self.handle, export_id=export_id
        )["structured_content"]

        # Assert
        self.assertEqual([o["file_name"] for o in target["objects"]], ["a b", "Other"])

    def test_Should_skip_a_hidden_object_When_objects_are_omitted(self):
        # Arrange
        self._add_box("Shown")
        hidden = self._add_box("Hidden")
        hidden.Visibility = False

        # Act
        _path, target = self._export(exports.export_step, "shown.step")

        # Assert
        self.assertEqual(target["structured_content"]["objects"], ["Shown"])

    def test_Should_refuse_When_no_visible_solid_exists(self):
        # Arrange
        self.document.addObject("Part::Feature", "Empty")
        self.document.addObject("Part::Feature", "AlsoEmpty")
        self.document.recompute()

        # Act
        act = lambda: self._export(exports.export_step, "none.step")  # noqa: E731

        # Assert
        with self.assertRaisesRegex(exports.ValidationError, "no visible solid"):
            act()

    def test_Should_refuse_and_write_nothing_When_one_selected_name_is_unknown(self):
        # Arrange
        self._add_box("BoxA")
        path = self.tmp / "x.step"

        # Act
        act = lambda: exports.export_step(  # noqa: E731
            self.registry, self.exports, doc=self.handle, path=str(path), objects=["BoxA", "Nope"]
        )

        # Assert
        with self.assertRaisesRegex(exports.ValidationError, "unknown object: Nope"):
            act()
        self.assertFalse(path.exists())

    def test_Should_refuse_naming_the_object_When_a_selected_object_has_no_solid(self):
        # Arrange
        self._add_box("BoxA")
        sketch = self.document.addObject("Sketcher::SketchObject", "Flat")
        sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(5, 0, 0)))
        self.document.recompute()

        # Act
        act = lambda: self._export(  # noqa: E731
            exports.export_step, "x.step", objects=["BoxA", "Flat"]
        )

        # Assert
        with self.assertRaisesRegex(exports.ValidationError, "object has no solid: Flat"):
            act()

    def test_Should_export_once_When_a_name_is_repeated(self):
        # Arrange
        self._add_box("BoxA")

        # Act
        _path, target = self._export(exports.export_step, "dup.step", objects=["BoxA", "BoxA"])

        # Assert
        export_id = target["structured_content"]["export_id"]
        self.assertEqual(target["structured_content"]["objects"], ["BoxA"])
        self.assertNotIn("objects", self.exports._by_id[export_id]["source"])

    def test_Should_keep_the_single_object_check_ids_When_one_object_is_verified(self):
        # Arrange
        self._add_box("BoxA")
        _path, written = self._export(exports.export_step, "one.step", objects=["BoxA"])

        # Act
        target = self._verify_step(written)

        # Assert
        ids = {c["id"] for c in target["structured_content"]["checks"]}
        self.assertEqual(
            ids,
            {
                "export_step.volume",
                "export_step.valid",
                "export_step.topology_counts",
                "export_step.schema",
            },
        )

    def test_Should_write_millimetres_and_the_schema_When_several_objects_go_to_step(self):
        # Arrange
        names = self._add_three_bodies()
        saved_unit = Part.exportUnits()["write.step.unit"]
        self.addCleanup(shim.restore_step_config, saved_unit)
        Part.setStaticValue("write.step.unit", "INCH")

        # Act
        path, written = self._export(exports.export_step, "pinned.step", objects=names, ap="AP242")

        # Assert
        self.assertNotIn(INCH_UNIT, Path(path).read_text(errors="replace"))
        self.assertEqual(Part.exportUnits()["write.step.unit"], "INCH")
        by_id = {c["id"]: c for c in self._verify_step(written)["structured_content"]["checks"]}
        self.assertTrue(by_id["export_step.schema"]["passed"])

    def test_Should_write_one_merged_mesh_When_three_objects_go_to_stl(self):
        # Arrange
        import Mesh

        names = self._add_three_bodies()
        singles = 0
        for name in names:
            _p, one = self._export(exports.export_stl, f"{name}.stl", objects=[name])
            singles += one["structured_content"]["facets"]

        # Act
        path, target = self._export(exports.export_stl, "all.stl", objects=names)

        # Assert
        export_id = target["structured_content"]["export_id"]
        source = self.exports._by_id[export_id]["source"]
        self.assertEqual(target["structured_content"]["facets"], singles)
        self.assertEqual(Mesh.Mesh(path).CountFacets, singles)
        self.assertAlmostEqual(
            source["volume"], sum(o["volume"] for o in source["objects"]), places=6
        )

    def test_Should_self_read_the_recorded_counts_When_three_objects_go_to_3mf(self):
        # Arrange
        names = self._add_three_bodies()
        _path, written = self._export(exports.export_3mf, "all.3mf", objects=names)
        export_id = written["structured_content"]["export_id"]

        # Act
        target = exports.export_self_read_3mf(
            self.registry, self.exports, doc=self.handle, export_id=export_id
        )["structured_content"]

        # Assert
        self.assertEqual(target["self_read"]["facets"], target["recorded"]["facets"])
        self.assertEqual(target["self_read"]["vertices"], target["recorded"]["vertices"])
        self.assertEqual([o["name"] for o in target["objects"]], names)

    def test_Should_name_each_mesh_object_by_label_When_three_objects_go_to_3mf(self):
        # Arrange
        names = self._add_three_bodies()

        # Act
        path, _written = self._export(exports.export_3mf, "all.3mf", objects=names)

        # Assert
        with zipfile.ZipFile(path) as archive:
            model = archive.read("3D/3dmodel.model").decode("utf-8")
        found = re.findall(r'<object id="\d+" type="model" name="([^"]*)"', model)
        self.assertEqual(found, ["Alpha", "Beta", "Gamma"])


class ExportBadInputTest(_ExportFixture):
    def _dispatch(self):
        methods = MethodRegistry()
        reg, exp = self.registry, self.exports
        specs = (
            ("export_step", lambda **p: exports.export_step(reg, exp, **p)),
            ("verify_export_step", lambda **p: exports.verify_export_step(reg, exp, **p)),
            ("export_self_read_stl", lambda **p: exports.export_self_read_stl(reg, exp, **p)),
        )
        for name, fn in specs:
            methods.register(RpcMethod(name=name, handler=fn, mutating=False))
        return methods

    def test_bad_export_id_is_invalid_input(self):
        self._add_box()
        envelope = self._dispatch().dispatch(
            "verify_export_step", {"doc": self.handle, "export_id": "nope"}
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_unknown_doc_is_invalid_input(self):
        envelope = self._dispatch().dispatch(
            "export_step", {"doc": "fcb-doc:missing", "path": str(self.tmp / "x.step")}
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_export_id_bound_to_other_doc_is_invalid_input(self):
        self._add_box()
        export_id = exports.export_stl(
            self.registry, self.exports, doc=self.handle, path=str(self.tmp / "b.stl")
        )["structured_content"]["export_id"]
        other = self.registry.document_create("other")["structured_content"]["doc"]
        envelope = self._dispatch().dispatch(
            "export_self_read_stl", {"doc": other, "export_id": export_id}
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_verify_export_step_rejects_non_step_export_id(self):
        self._add_box()
        stl_id = exports.export_stl(
            self.registry, self.exports, doc=self.handle, path=str(self.tmp / "b.stl")
        )["structured_content"]["export_id"]
        envelope = self._dispatch().dispatch(
            "verify_export_step", {"doc": self.handle, "export_id": stl_id}
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_zero_deflection_is_invalid_input(self):
        self._add_box()
        methods = MethodRegistry()
        methods.register(
            RpcMethod(
                name="export_stl",
                handler=lambda **p: exports.export_stl(self.registry, self.exports, **p),
                mutating=True,
            )
        )
        envelope = methods.dispatch(
            "export_stl", {"doc": self.handle, "path": str(self.tmp / "b.stl"), "linear": 0}
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def _mesh_methods(self):
        methods = MethodRegistry()
        methods.register(
            RpcMethod(
                name="export_stl",
                handler=lambda **p: exports.export_stl(self.registry, self.exports, **p),
                mutating=True,
            )
        )
        return methods

    def test_non_finite_deflection_is_invalid_input(self):
        self._add_box()
        methods = self._mesh_methods()
        envelope = methods.dispatch(
            "export_stl",
            {"doc": self.handle, "path": str(self.tmp / "b.stl"), "linear": float("inf")},
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_null_shape_object_is_invalid_input(self):
        self.document.addObject("Part::Feature", "Empty")
        self.document.recompute()
        methods = self._mesh_methods()
        envelope = methods.dispatch(
            "export_stl",
            {"doc": self.handle, "path": str(self.tmp / "b.stl"), "objects": ["Empty"]},
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")


def _freecad_version() -> str:
    return ".".join(str(part) for part in App.Version()[:3])


def _file_schema_text(path: str) -> str:
    """Return the quoted text of the STEP header's ``FILE_SCHEMA``, read straight from the file."""
    header = Path(path).read_text(encoding="ascii").split("DATA;", 1)[0]
    quoted = header.split("FILE_SCHEMA", 1)[1]
    return quoted.split("'")[1]


class StepVolumeVerdictTest(unittest.TestCase):
    """The STEP volume check compares the once-rounded deviation with its raw ±0.1 % band.

    The spec's verdict rows, each with an expected volume whose ±0.1 % band lets the row show
    its rule: (row, measured, expected, passed).
    """

    ROWS = [
        ("noise", 5.999999998, 6.0, True),
        ("straddle", 6.0150001, 6.015, True),
        ("edge", 60.064, 60.0, True),
        ("tight", 1.004, 1.0, False),
    ]

    def setUp(self):
        patcher = mock.patch.object(shim, "display_decimals", return_value=2)
        patcher.start()
        self.addCleanup(patcher.stop)

    def volume_check(self, measured, expected):
        source = {"volume": expected, "faces": 6, "edges": 12, "solids": 1}
        return exports._step_checks(Part.makeBox(1, 1, measured), source)[0]

    def test_should_take_the_matrix_verdicts_when_the_step_volume_is_checked(self):
        # Arrange
        rows = self.ROWS

        # Act
        checks = {row: self.volume_check(measured, expected) for row, measured, expected, _ in rows}

        # Assert
        for row, _, _, passed in rows:
            with self.subTest(row=row):
                self.assertIs(checks[row]["passed"], passed, checks[row]["detail"])
        self.assertEqual(checks["edge"]["detail"]["message"], "|60.06 - 60.0| = 0.06 <= 0.06")
        self.assertEqual(checks["tight"]["tolerance"], {"rel": 0.001})


if __name__ == "__main__":
    unittest.main()
