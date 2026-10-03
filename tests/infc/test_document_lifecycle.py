"""In-FreeCAD document-lifecycle and capability-probe tests (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Validates the ``DocumentRegistry`` round-trip,
explicit-handle enforcement through the dispatch boundary, and the live shim probes.
"""

import builtins
import math
import unittest

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.usecases import queries, shim
from freecad_buddy.usecases.documents import DocumentRegistry


class DocumentLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()

    def _close_all(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def tearDown(self):
        self._close_all()

    def test_create_save_close_round_trip(self):
        created = self.registry.document_create("lifecycle_part")
        self.assertEqual(created["status"], "OK")
        handle = created["structured_content"]["doc"]
        self.assertTrue(handle.startswith("fcb-doc:"))
        name = created["structured_content"]["name"]
        self.assertIn(name, App.listDocuments())

        import os
        import tempfile

        path = os.path.join(tempfile.mkdtemp(), "lifecycle_part.FCStd")
        saved = self.registry.document_save(doc=handle, path=path)
        self.assertEqual(saved["status"], "OK")
        self.assertTrue(os.path.isfile(path))

        closed = self.registry.document_close(doc=handle)
        self.assertEqual(closed["status"], "OK")
        self.assertNotIn(name, App.listDocuments())

    def test_recompute_returns_ok(self):
        created = self.registry.document_create("recompute_doc")
        handle = created["structured_content"]["doc"]
        result = self.registry.document_recompute(doc=handle)
        self.assertEqual(result["status"], "OK")
        self.assertIn("touched", result["structured_content"])

    def test_document_list_reports_open_handles(self):
        a = self.registry.document_create("doc_a")["structured_content"]["doc"]
        b = self.registry.document_create("doc_b")["structured_content"]["doc"]
        listed = self.registry.document_list()
        self.assertEqual(listed["status"], "OK")
        handles = {d["doc"] for d in listed["structured_content"]["documents"]}
        self.assertEqual(handles, {a, b})

    def test_reopen_same_path_reuses_handle(self):
        import os
        import tempfile

        path = os.path.join(tempfile.mkdtemp(), "reopen.FCStd")
        first = self.registry.document_create("reopen_doc", path=path)["structured_content"]["doc"]
        second = self.registry.document_open(path)["structured_content"]["doc"]
        self.assertEqual(first, second)

        listed = self.registry.document_list()["structured_content"]["documents"]
        self.assertEqual(len([d for d in listed if d["doc"] == first]), 1)

        # Closing the single handle leaves no dangling alias resolving to a closed document.
        self.assertEqual(self.registry.document_close(doc=first)["status"], "OK")
        stale = self._dispatch_with_save().dispatch("document_save", {"doc": second})
        self.assertEqual(stale["status"], "INVALID_INPUT")

    def test_active_document_never_targeted(self):
        # A document created outside the registry becomes ActiveDocument; a save that omits the
        # handle must not touch it and fails closed.
        App.newDocument("orphan_active")
        self.assertIsNotNone(App.ActiveDocument)
        dispatch = self._dispatch_with_save()
        envelope = dispatch.dispatch("document_save", {})
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    # -- explicit-handle enforcement via the dispatch boundary --------------------------

    def _dispatch_with_save(self) -> MethodRegistry:
        methods = MethodRegistry()
        methods.register(
            RpcMethod(name="document_save", handler=self.registry.document_save, mutating=True)
        )
        methods.register(
            RpcMethod(name="document_close", handler=self.registry.document_close, mutating=True)
        )
        return methods

    def test_unknown_handle_maps_to_invalid_input(self):
        methods = self._dispatch_with_save()
        envelope = methods.dispatch("document_save", {"doc": "fcb-doc:does-not-exist"})
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertIn("unknown", envelope["detail"]["message"])

    def test_missing_handle_maps_to_invalid_input(self):
        methods = self._dispatch_with_save()
        envelope = methods.dispatch("document_close", {})
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertIn("missing", envelope["detail"]["message"])

    def test_stale_handle_after_close_maps_to_invalid_input(self):
        handle = self.registry.document_create("stale_doc")["structured_content"]["doc"]
        self.registry.document_close(doc=handle)
        methods = self._dispatch_with_save()
        envelope = methods.dispatch("document_save", {"doc": handle})
        self.assertEqual(envelope["status"], "INVALID_INPUT")


class CapabilityProbeTest(unittest.TestCase):
    def test_query_capabilities_reports_live_probes(self):
        envelope = queries.query_capabilities(exec_enabled=False)
        self.assertEqual(envelope["status"], "OK")
        content = envelope["structured_content"]

        self.assertRegex(content["freecad_version"], r"^\d+\.\d+")
        self.assertIsInstance(content["element_map_available"], bool)
        self.assertIn(content["serializer"], ("exportBinary", "exportBrep"))
        self.assertIn(content["varset_backend"], ("varset", "spreadsheet"))
        self.assertEqual(content["render"], "none")
        self.assertFalse(content["exec_enabled"])

    def test_exec_enabled_flag_is_echoed(self):
        envelope = queries.query_capabilities(exec_enabled=True)
        self.assertTrue(envelope["structured_content"]["exec_enabled"])

    def test_every_validated_property_reports_its_live_enumeration(self):
        enums = shim.property_enums()

        for type_id, prop in (
            ("PartDesign::Pad", "Type"),
            ("PartDesign::Pocket", "Type"),
            ("PartDesign::Revolution", "Type"),
            ("PartDesign::Hole", "ThreadType"),
            ("PartDesign::Hole", "HoleCutType"),
            ("PartDesign::Hole", "DepthType"),
            ("PartDesign::Chamfer", "ChamferType"),
            ("PartDesign::LinearPattern", "Mode"),
            ("PartDesign::LinearPattern", "TransformMode"),
            ("PartDesign::PolarPattern", "Mode"),
        ):
            with self.subTest(type_id=type_id, prop=prop):
                self.assertIn(type_id, enums)
                self.assertIn(prop, enums[type_id])
                self.assertTrue(enums[type_id][prop])

    def test_the_reported_values_match_the_live_reading(self):
        """Asserted against the live probe, never a hardcoded list."""
        import FreeCAD

        document = FreeCAD.newDocument("enum_probe", hidden=True)
        try:
            probe = document.addObject("PartDesign::LinearPattern", "Probe")
            live = list(probe.getEnumerationsOfProperty("Mode"))
        finally:
            FreeCAD.closeDocument(document.Name)

        self.assertEqual(shim.property_enums()["PartDesign::LinearPattern"]["Mode"], live)

    def test_a_disabled_marker_value_is_reported_unfiltered(self):
        # Pad.Type carries '?TwoLengths' on this build. Measured: assigning it succeeds and it
        # reads back unchanged, so it is a legal value rather than a member to filter away.
        values = shim.property_enums()["PartDesign::Pad"]["Type"]

        self.assertTrue(
            any(value.startswith("?") for value in values),
            f"expected a '?'-prefixed member in {values}",
        )

    def test_the_banner_carries_the_enums_block(self):
        self.assertIn("enums", shim.capability_banner())

    def test_shim_probes_never_raise(self):
        # probes must resolve on the live build without version-string branching.
        self.assertIsInstance(shim.element_map_available(), bool)
        self.assertIsInstance(shim.export_binary_available(), bool)
        self.assertIsInstance(shim.serializer_tag(), str)
        self.assertIsInstance(shim.varset_backend(), str)
        self.assertRegex(shim.freecad_version(), r"^\d+\.\d+")

    def test_element_map_available_is_pure_exposure_probe(self):
        # A build exposing the element-map API reports True even when a fresh box has an empty
        # map: pure exposure, not populated-map non-emptiness.
        result = shim.element_map_available()
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_warm_capability_probes_is_idempotent_and_leaves_no_temp_doc(self):
        # Clear the probe caches so warming actually re-runs varset_backend (which opens and
        # closes a throwaway document); a cache hit would exercise nothing.
        shim.varset_backend.cache_clear()
        shim.varset_available.cache_clear()
        shim.warm_capability_probes()
        self.assertNotIn("FCB_TMP_varset_probe", App.listDocuments())
        shim.varset_backend.cache_clear()
        shim.varset_available.cache_clear()
        shim.warm_capability_probes()
        self.assertNotIn("FCB_TMP_varset_probe", App.listDocuments())


class SketcherProbeRecoveryTest(unittest.TestCase):
    """The Sketcher probe must not let one failed import disable sketching for the process."""

    def setUp(self):
        self._real_import = builtins.__import__
        shim._sketcher_probed_ok = False

    def tearDown(self):
        builtins.__import__ = self._real_import
        shim._sketcher_probed_ok = False

    def _fail_sketcher_import(self):
        """Make ``import Sketcher`` raise the way a partially-initialised module would."""

        def guard(name, *args, **kwargs):
            if name == "Sketcher":
                raise ImportError("Sketcher is not fully initialised yet")
            return self._real_import(name, *args, **kwargs)

        builtins.__import__ = guard

    def test_a_transient_import_failure_does_not_disable_sketching_for_the_process(self):
        self._fail_sketcher_import()
        self.assertFalse(shim.sketcher_available())

        builtins.__import__ = self._real_import
        self.assertTrue(shim.sketcher_available())

    def test_warming_the_probes_through_a_failed_import_still_recovers(self):
        self._fail_sketcher_import()
        shim.warm_capability_probes()
        self.assertFalse(shim.sketcher_available())

        builtins.__import__ = self._real_import
        self.assertTrue(shim.sketcher_available())
        self.assertTrue(shim.capability_banner()["sketcher_available"])

    def test_the_success_is_cached_so_the_hot_path_does_not_reimport(self):
        self.assertTrue(shim.sketcher_available())

        self._fail_sketcher_import()
        self.assertTrue(shim.sketcher_available())


class RedundantOnlySketchTest(unittest.TestCase):
    """``redundant_only_sketch`` must read the sketch's own state, not the recompute log."""

    def setUp(self):
        self.doc = App.newDocument("FCB_redundant_probe")

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _right_angle_sketch(self, name):
        """A sketch whose only fault is redundancy: horizontal + vertical + a 90-degree angle.

        The angle repeats what the two orientation constraints already fix, so ``solve()``
        reports ``-2`` and FreeCAD writes the ``Sketch with redundant constraints`` log line.
        Returns the sketch and the index of the redundant angle constraint.
        """
        sketch = self.doc.addObject("Sketcher::SketchObject", name)
        first = sketch.addGeometry(
            Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0)), False
        )
        second = sketch.addGeometry(
            Part.LineSegment(App.Vector(0, 0, 0), App.Vector(0, 10, 0)), False
        )
        sketch.addConstraint(Sketcher.Constraint("Coincident", first, 1, second, 1))
        sketch.addConstraint(Sketcher.Constraint("Horizontal", first))
        sketch.addConstraint(Sketcher.Constraint("Vertical", second))
        angle = sketch.addConstraint(
            Sketcher.Constraint("Angle", first, 1, second, 1, math.pi / 2.0)
        )
        self.doc.recompute()
        return sketch, angle

    def test_a_genuinely_redundant_sketch_is_reported(self):
        sketch, _ = self._right_angle_sketch("Redundant")

        self.assertFalse(sketch.isValid())
        self.assertTrue(shim.redundant_only_sketch(sketch))

    def test_a_conflicting_sketch_is_not_reported(self):
        sketch = self.doc.addObject("Sketcher::SketchObject", "Conflicting")
        edge = sketch.addGeometry(
            Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0)), False
        )
        sketch.addConstraint(Sketcher.Constraint("DistanceX", edge, 1, edge, 2, 10.0))
        sketch.addConstraint(Sketcher.Constraint("DistanceX", edge, 1, edge, 2, 20.0))
        self.doc.recompute()

        self.assertFalse(sketch.isValid())
        self.assertFalse(shim.redundant_only_sketch(sketch))

    def test_a_stale_redundant_log_does_not_mask_the_current_fault(self):
        """The log keeps the redundant prefix after the redundancy itself is gone.

        The recompute log is written per recompute and only refreshed when the object
        recomputes again, so a sketch edited into a different fault still reports the old
        message. The probe must read the sketch's live solver state instead.
        """
        sketch, angle = self._right_angle_sketch("Stale")
        self.assertTrue(str(sketch.getStatusString()).startswith("Sketch with redundant"))

        # Drop the redundant angle, then over-constrain the sketch a different way. Solving
        # refreshes the sketch's own diagnostics but leaves the recompute log untouched.
        sketch.delConstraint(angle)
        third = sketch.addGeometry(
            Part.LineSegment(App.Vector(0, 0, 0), App.Vector(5, 5, 0)), False
        )
        sketch.addConstraint(Sketcher.Constraint("Coincident", third, 1, 0, 1))
        sketch.addConstraint(Sketcher.Constraint("Angle", 0, 1, third, 1, math.radians(80.0)))
        sketch.addConstraint(Sketcher.Constraint("Horizontal", third))
        sketch.solve()

        self.assertTrue(str(sketch.getStatusString()).startswith("Sketch with redundant"))
        self.assertEqual(list(sketch.RedundantConstraints), [])
        self.assertFalse(shim.redundant_only_sketch(sketch))

    def test_a_non_sketch_object_is_never_reported(self):
        box = self.doc.addObject("Part::Box", "Box")
        self.doc.recompute()

        self.assertFalse(shim.redundant_only_sketch(box))


if __name__ == "__main__":
    unittest.main()
