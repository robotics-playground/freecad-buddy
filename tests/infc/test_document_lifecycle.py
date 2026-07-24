"""In-FreeCAD document-lifecycle and capability-probe tests (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Validates the ``DocumentRegistry`` round-trip,
explicit-handle enforcement through the dispatch boundary, and the live shim probes.
"""

import unittest

import FreeCAD as App

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


if __name__ == "__main__":
    unittest.main()
