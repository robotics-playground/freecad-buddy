"""In-FreeCAD tests for the export writers and the FreeCAD-side verify legs (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Golden values are analytic (box 10x20x30 -> volume
6000, 6 faces, 12 edges, 1 solid), never captured from the implementation. Covers the
``export_step`` -> ``verify_export_step`` round-trip (volume +-0.1%, exact counts, banner), that
``export_stl`` and ``export_3mf`` share one tessellation (identical facet count), that every
export result carries ``verified: false``, the self-read facts, and the bad ``export_id`` /
``doc`` INVALID_INPUT boundary.
"""

import tempfile
import unittest
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

    def test_no_selection_with_multiple_objects_is_invalid_input(self):
        self._add_box("BoxA")
        self._add_box("BoxB")
        methods = self._mesh_methods()
        envelope = methods.dispatch(
            "export_stl", {"doc": self.handle, "path": str(self.tmp / "b.stl")}
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
