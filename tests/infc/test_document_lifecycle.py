"""In-FreeCAD document-lifecycle and capability-probe tests (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Validates the ``DocumentRegistry`` round-trip,
explicit-handle enforcement through the dispatch boundary, and the live shim probes.
"""

import builtins
import os
import shutil
import stat
import tempfile
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

    def test_a_handle_to_a_document_closed_outside_the_registry_is_invalid_input(self):
        # The GUI's File > Close goes straight to closeDocument; the registry never sees it.
        handle = self.registry.document_create("gui_closed")["structured_content"]["doc"]
        document = self.registry.with_document(handle, lambda h, d: d)
        other = self.registry.document_create("gui_kept")["structured_content"]["doc"]
        self.registry.rebind(other, document)
        App.closeDocument(document.Name)
        methods = MethodRegistry()
        methods.register(
            RpcMethod(
                name="document_recompute", handler=self.registry.document_recompute, mutating=True
            )
        )

        envelope = methods.dispatch("document_recompute", {"doc": handle})

        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertIn(f"unknown or stale document handle: {handle}", envelope["detail"]["message"])
        self.assertNotIn(handle, self.registry._by_handle, "the stale handle survived")
        self.assertNotIn(
            other, self.registry._by_handle, "an alias of the closed document survived"
        )

    def test_rebinding_a_handle_moves_every_alias_of_the_replaced_document(self):
        # A snapshot restore replaces the document object; an alias left on the dead original
        # would be refused as stale on its next use.
        handle = self.registry.document_create("original")["structured_content"]["doc"]
        original = self.registry.with_document(handle, lambda h, d: d)
        alias = self.registry.document_create("alias")["structured_content"]["doc"]
        self.registry.rebind(alias, original)
        replacement = App.newDocument("replacement")

        self.registry.rebind(handle, replacement)

        self.assertIs(self.registry.with_document(alias, lambda h, d: d), replacement)


class SaveTargetTest(unittest.TestCase):
    """``document_save`` and ``document_create`` refuse a bad target before anything is written."""

    def setUp(self):
        self.registry = DocumentRegistry()
        self.folder = tempfile.mkdtemp()
        self.methods = MethodRegistry()
        self.methods.register(
            RpcMethod(name="document_save", handler=self.registry.document_save, mutating=True)
        )
        self.methods.register(
            RpcMethod(name="document_create", handler=self.registry.document_create, mutating=True)
        )

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)
        for entry in os.listdir(self.folder):
            os.chmod(os.path.join(self.folder, entry), stat.S_IWRITE | stat.S_IREAD)
        shutil.rmtree(self.folder)

    def _handle(self, label="save_target"):
        return self.registry.document_create(label)["structured_content"]["doc"]

    def test_save_as_reports_the_label_freecad_set_from_the_file_stem(self):
        handle = self._handle("Bản vẽ ✓")
        path = os.path.join(self.folder, "new-part.FCStd")

        envelope = self.methods.dispatch("document_save", {"doc": handle, "path": path})

        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(envelope["structured_content"]["label"], "new-part")
        self.assertEqual(
            os.path.normcase(envelope["structured_content"]["path"]), os.path.normcase(path)
        )

    def test_save_as_reports_the_path_freecad_actually_wrote(self):
        handle = self._handle()
        path = os.path.join(self.folder, "no-extension")

        envelope = self.methods.dispatch("document_save", {"doc": handle, "path": path})

        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(envelope["structured_content"]["path"], path + ".FCStd")
        self.assertTrue(os.path.isfile(path + ".FCStd"))

    def test_a_missing_folder_is_refused_and_never_created(self):
        handle = self._handle()
        missing = os.path.join(self.folder, "no-such-dir")

        envelope = self.methods.dispatch(
            "document_save", {"doc": handle, "path": os.path.join(missing, "out.FCStd")}
        )

        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertIn(missing, envelope["detail"]["message"])
        self.assertFalse(os.path.exists(missing), "the refused save created the folder")

    def test_a_directory_path_is_refused_and_nothing_is_written(self):
        handle = self._handle()
        directory = os.path.join(self.folder, "a-directory")
        os.mkdir(directory)

        envelope = self.methods.dispatch("document_save", {"doc": handle, "path": directory})

        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertIn(directory, envelope["detail"]["message"])
        self.assertFalse(os.path.exists(directory + ".FCStd"), "FreeCAD wrote a sibling file")

    def _saved_handle(self) -> tuple[str, str]:
        """A document already saved to ``first.FCStd``; return its handle and that path."""
        handle = self._handle()
        first = os.path.join(self.folder, "first.FCStd")
        self.assertEqual(
            self.methods.dispatch("document_save", {"doc": handle, "path": first})["status"], "OK"
        )
        return handle, first

    def _read_only_file(self, name: str) -> str:
        path = os.path.join(self.folder, name)
        with open(path, "wb") as stream:
            stream.write(b"not overwritten")
        os.chmod(path, stat.S_IREAD)
        return path

    def _assert_read_only_target_refused(self, given_name: str):
        handle, first = self._saved_handle()
        locked = self._read_only_file("locked.FCStd")

        envelope = self.methods.dispatch(
            "document_save", {"doc": handle, "path": os.path.join(self.folder, given_name)}
        )

        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertIn(locked, envelope["detail"]["message"])
        document = self.registry.with_document(handle, lambda h, d: d)
        self.assertEqual(os.path.normcase(document.FileName), os.path.normcase(first))

    def test_a_read_only_target_is_refused_and_the_file_name_is_unchanged(self):
        self._assert_read_only_target_refused("locked.FCStd")

    def test_a_read_only_target_named_without_the_extension_is_refused(self):
        self._assert_read_only_target_refused("locked")

    def test_a_read_only_target_named_with_a_trailing_dot_is_refused(self):
        self._assert_read_only_target_refused("locked.")

    def test_a_plain_save_to_a_read_only_file_is_invalid_input_naming_it(self):
        handle, first = self._saved_handle()
        os.chmod(first, stat.S_IREAD)

        envelope = self.methods.dispatch("document_save", {"doc": handle})

        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertIn(os.path.normcase(first), os.path.normcase(envelope["detail"]["message"]))

    def test_a_failed_save_as_restores_the_file_name_and_label(self):
        handle, first = self._saved_handle()
        path = os.path.join(self.folder, "out.FCStd")
        real = self.registry.with_document(handle, lambda h, d: d)
        label = real.Label
        self.registry.rebind(handle, _SaveAsFailsAfterRenaming(real))

        envelope = self.methods.dispatch("document_save", {"doc": handle, "path": path})

        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertIn(path, envelope["detail"]["message"])
        self.assertEqual(os.path.normcase(real.FileName), os.path.normcase(first))
        self.assertEqual(real.Label, label)

    def test_create_with_a_missing_folder_is_refused_and_creates_no_document(self):
        missing = os.path.join(self.folder, "no-such-dir")
        before = set(App.listDocuments())

        envelope = self.methods.dispatch(
            "document_create", {"label": "doomed", "path": os.path.join(missing, "out.FCStd")}
        )

        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertIn(missing, envelope["detail"]["message"])
        self.assertEqual(set(App.listDocuments()), before)
        self.assertFalse(os.path.exists(missing))

    def test_create_with_a_path_reports_the_label_and_path(self):
        path = os.path.join(self.folder, "created.FCStd")

        envelope = self.methods.dispatch("document_create", {"label": "Bản vẽ", "path": path})

        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(envelope["structured_content"]["label"], "created")
        self.assertEqual(
            os.path.normcase(envelope["structured_content"]["path"]), os.path.normcase(path)
        )


class _SaveAsFailsAfterRenaming:
    """A document whose ``saveAs`` renames it as ``Document::saveAs`` does, then fails to write."""

    def __init__(self, real):
        object.__setattr__(self, "_real", real)

    def __getattr__(self, name):
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        setattr(self._real, name, value)

    def saveAs(self, path):  # noqa: N802 - mirrors the FreeCAD API name
        self._real.FileName = path
        self._real.Label = "renamed"
        raise OSError("disk full")


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


class DisplayDecimalsTest(unittest.TestCase):
    """The ``Decimals`` unit preference, read on every call; the user's own value is restored."""

    def setUp(self):
        self.units = App.ParamGet("User parameter:BaseApp/Preferences/Units")
        self.had_decimals = "Decimals" in self.units.GetInts()
        self.saved = self.units.GetInt("Decimals")
        self.buddy = App.ParamGet(shim.BUDDY_PARAM_PATH)
        self.had_round = shim.ROUND_TO_DISPLAY_KEY in self.buddy.GetBools()
        self.saved_round = self.buddy.GetBool(shim.ROUND_TO_DISPLAY_KEY, True)

    def tearDown(self):
        if self.had_decimals:
            self.units.SetInt("Decimals", self.saved)
        else:
            self.units.RemInt("Decimals")
        if self.had_round:
            self.buddy.SetBool(shim.ROUND_TO_DISPLAY_KEY, self.saved_round)
        else:
            self.buddy.RemBool(shim.ROUND_TO_DISPLAY_KEY)

    def _dispatch_value(self, registry):
        envelope = registry.dispatch("stub", {})
        return envelope["display_decimals"]

    def test_should_stamp_the_new_precision_when_the_preference_changes_between_two_calls(self):
        # Arrange
        registry = MethodRegistry()
        registry.register(RpcMethod(name="stub", handler=lambda: {"status": "OK"}))
        self.units.SetInt("Decimals", 2)
        first = self._dispatch_value(registry)
        self.units.SetInt("Decimals", 4)

        # Act
        second = self._dispatch_value(registry)

        # Assert
        self.assertEqual((first, second), (2, 4))
        self.assertEqual(shim.displayed(5.12345), 5.1235)

    def test_should_read_two_decimals_when_the_preference_is_missing(self):
        # Arrange
        self.units.RemInt("Decimals")

        # Act
        decimals = shim.display_decimals()

        # Assert
        self.assertEqual(decimals, 2)

    def test_should_read_two_decimals_when_the_preference_is_negative(self):
        # Arrange
        self.units.SetInt("Decimals", -3)

        # Act
        decimals = shim.display_decimals()

        # Assert
        self.assertEqual(decimals, 2)

    def test_should_stamp_no_precision_when_round_to_display_is_off(self):
        # Arrange
        registry = MethodRegistry()
        registry.register(RpcMethod(name="stub", handler=lambda: {"status": "OK"}))
        self.units.SetInt("Decimals", 2)
        self.buddy.SetBool(shim.ROUND_TO_DISPLAY_KEY, False)

        # Act
        decimals = self._dispatch_value(registry)

        # Assert
        self.assertIsNone(decimals)
        self.assertEqual(shim.displayed(5.999999998), 5.999999998)

    def test_should_round_when_round_to_display_is_missing(self):
        # Arrange
        self.units.SetInt("Decimals", 2)
        self.buddy.RemBool(shim.ROUND_TO_DISPLAY_KEY)

        # Act
        decimals = shim.display_decimals()

        # Assert
        self.assertEqual(decimals, 2)


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


if __name__ == "__main__":
    unittest.main()
