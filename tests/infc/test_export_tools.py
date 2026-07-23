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

import FreeCAD as App

from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.usecases import exports
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.exports import ExportRegistry

BOX_L = 10.0
BOX_W = 20.0
BOX_H = 30.0
ANALYTIC_VOLUME = BOX_L * BOX_W * BOX_H  # 6000 mm^3
ANALYTIC_FACES = 6
ANALYTIC_EDGES = 12
ANALYTIC_SOLIDS = 1


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

    def test_ap242_and_mm_pinned(self):
        self._add_box()
        path = str(self.tmp / "box.step")
        exports.export_step(self.registry, self.exports, doc=self.handle, path=path, ap="AP242")
        from freecad_buddy.usecases import shim

        self.assertEqual(shim.step_schema(), "AP242")


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


if __name__ == "__main__":
    unittest.main()
