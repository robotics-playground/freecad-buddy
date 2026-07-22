"""Render-probe ladder + Gui-free screenshot use-case tests (no FreeCAD).

The render ladder reports ``none`` with a reason when ``FreeCADGui`` is absent. The
``query_screenshot`` use case is proven against a fake ``RenderPort`` and a fake document/registry:
scene-spec assembly (include/exclude/style/focus), custom-quaternion validation, the
``available:false`` envelope, coherent fail-closed validation, the temp-PNG lifecycle, and the
loop-2 fixes — the port receives the resolved document, the focus echo drops the sub-element part
on fallback, a raising post-render fingerprint cleans up the temp, and incoherent selectors are
rejected.
"""

from __future__ import annotations

import os

import pytest

from freecad_buddy.adapters import render_probe
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.contracts import RenderPort, RenderResult, SceneSpec
from freecad_buddy.usecases import screenshot
from freecad_buddy.usecases.documents import ValidationError

# ---- fakes -----------------------------------------------------------------------------------


class _FakeShape:
    def __init__(self, faces=0):
        self._faces = faces

    def isNull(self):  # noqa: N802 - FreeCAD API name
        return False

    @property
    def Faces(self):  # noqa: N802 - FreeCAD API name
        return list(range(self._faces))


class _FakeObject:
    def __init__(self, name, shape=None):
        self.Name = name
        if shape is not None:
            self.Shape = shape


class _FakeDocument:
    def __init__(self, objects):
        self._objects = {obj.Name: obj for obj in objects}

    @property
    def Objects(self):  # noqa: N802 - FreeCAD API name
        return list(self._objects.values())

    def getObject(self, name):  # noqa: N802 - FreeCAD API name
        return self._objects.get(name)


class _FakeRegistry:
    """Minimal ``with_document`` stand-in that binds a handle to a fixed document."""

    def __init__(self, document, handle="fcb-doc:fake"):
        self._document = document
        self._handle = handle

    def with_document(self, doc, fn):
        if doc != self._handle:
            raise ValidationError(f"unknown or stale document handle: {doc}")
        return fn(self._handle, self._document)


class _FakeRenderPort:
    """Records the scene and the document it was handed; writes a canned non-empty PNG."""

    def __init__(self, available=True, reason=None, focused=True, write_bytes=b"PNG"):
        self._available = available
        self._reason = reason
        self._focused = focused
        self._write_bytes = write_bytes
        self.last_document = None
        self.last_scene: SceneSpec | None = None
        self.last_out_path: str | None = None

    def available(self):
        return (self._available, self._reason)

    def render(self, document, scene, out_path):
        self.last_document = document
        self.last_scene = scene
        self.last_out_path = out_path
        if self._write_bytes is not None:
            with open(out_path, "wb") as handle:
                handle.write(self._write_bytes)
        rendered = [name for name in scene.objects if document.getObject(name) is not None]
        return RenderResult(rendered_objects=rendered, focused=self._focused)


_FP_A = {"schema": "fcb.fingerprint/1", "serializer": "exportBrep", "objects": [], "digest": "d"}


@pytest.fixture(autouse=True)
def _stub_fingerprint(monkeypatch):
    """Fingerprint before == after by default; individual tests override for mismatch cases."""
    monkeypatch.setattr(screenshot, "fingerprint", lambda document: dict(_FP_A))


def _doc(*objects):
    return _FakeDocument(list(objects))


def _run(document, view=None, port=None, handle="fcb-doc:fake"):
    """Dispatch ``query_screenshot`` through the error boundary so exceptions become statuses."""
    port = port or _FakeRenderPort()
    registry = _FakeRegistry(document, handle)
    methods = MethodRegistry()
    methods.register(
        RpcMethod(
            name="query_screenshot",
            handler=lambda **p: screenshot.query_screenshot(registry, port, **p),
            mutating=False,
        )
    )
    params = {"doc": handle}
    if view is not None:
        params["view"] = view
    envelope = methods.dispatch("query_screenshot", params)
    return envelope, port


# ---- ladder ----------------------------------------------------------------------------------


def test_render_capability_reports_none_with_reason_when_gui_absent():
    render_probe.render_capability.cache_clear()
    mode, reason = render_probe.render_capability()
    assert mode == "none"
    assert reason  # a non-empty explanation (no FreeCAD / no FreeCADGui)
    assert render_probe.render_capability_flag() == "none"


def test_render_port_protocol_shape():
    assert isinstance(render_probe.OffscreenRenderPort(), RenderPort)


# ---- scene assembly --------------------------------------------------------------------------


def test_include_list_renders_only_named_objects():
    document = _doc(_FakeObject("Body", _FakeShape()), _FakeObject("Base", _FakeShape()))
    envelope, port = _run(document, {"include": ["Body"]})
    assert envelope["status"] == "OK"
    assert port.last_scene.objects == ["Body"]
    assert envelope["structured_content"]["scene"]["rendered_objects"] == ["Body"]


def test_exclude_drops_named_object_from_all_visible():
    document = _doc(_FakeObject("Body", _FakeShape()), _FakeObject("Base", _FakeShape()))
    envelope, port = _run(document, {"exclude": ["Base"]})
    assert port.last_scene.objects == ["Body"]


def test_style_override_maps_transparency_and_color():
    document = _doc(_FakeObject("Base", _FakeShape()))
    _, port = _run(
        document,
        {"styles": [{"object": "Base", "transparency": 80, "color": [0.1, 0.2, 0.3]}]},
    )
    style = port.last_scene.styles[0]
    assert style.object == "Base"
    assert style.transparency == pytest.approx(0.8)
    assert style.color == pytest.approx((0.1, 0.2, 0.3))


def test_camera_custom_missing_orientation_is_invalid_input():
    document = _doc(_FakeObject("Body", _FakeShape()))
    envelope, _ = _run(document, {"camera": "custom"})
    assert envelope["status"] == "INVALID_INPUT"


def test_camera_custom_valid_quaternion_threads_through():
    document = _doc(_FakeObject("Body", _FakeShape()))
    _, port = _run(document, {"camera": "custom", "custom_orientation": [0.0, 0.0, 0.0, 1.0]})
    assert port.last_scene.orientation == (0.0, 0.0, 0.0, 1.0)


def test_render_unavailable_is_ok_with_reason_and_no_link():
    document = _doc(_FakeObject("Body", _FakeShape()))
    port = _FakeRenderPort(available=False, reason="no FreeCADGui")
    envelope, _ = _run(document, port=port)
    assert envelope["status"] == "OK"
    render = envelope["structured_content"]["render"]
    assert render["available"] is False
    assert render["reason"] == "no FreeCADGui"
    assert "resource_link" not in render
    assert "images" not in envelope


def test_unknown_handle_is_invalid_input():
    document = _doc(_FakeObject("Body", _FakeShape()))
    envelope, _ = _run(document, handle="fcb-doc:fake")
    # A handle the fake registry does not know raises via with_document → INVALID_INPUT.
    registry = _FakeRegistry(document, "fcb-doc:fake")
    methods = MethodRegistry()
    methods.register(
        RpcMethod(
            name="query_screenshot",
            handler=lambda **p: screenshot.query_screenshot(registry, _FakeRenderPort(), **p),
            mutating=False,
        )
    )
    missing = methods.dispatch("query_screenshot", {"doc": "fcb-doc:missing"})
    assert missing["status"] == "INVALID_INPUT"


# ---- regression (a)-(f): validation + lifecycle + echo ---------------------------------------


def test_nonexistent_include_name_is_invalid_input():
    document = _doc(_FakeObject("Body", _FakeShape()))
    envelope, _ = _run(document, {"include": ["Ghost"]})
    assert envelope["status"] == "INVALID_INPUT"


def test_nonexistent_selector_name_is_invalid_input():
    document = _doc(_FakeObject("Body", _FakeShape()))
    envelope, _ = _run(document, {"focus": {"object": "Ghost"}})
    assert envelope["status"] == "INVALID_INPUT"


def test_render_raises_removes_temp_png_and_surfaces_error(monkeypatch):
    document = _doc(_FakeObject("Body", _FakeShape()))
    seen = {}

    class _Boom(_FakeRenderPort):
        def render(self, doc, scene, out_path):
            seen["path"] = out_path
            with open(out_path, "wb") as handle:
                handle.write(b"partial")
            raise RuntimeError("gl exploded")

    envelope, _ = _run(document, port=_Boom())
    assert envelope["status"] != "OK"
    assert not os.path.exists(seen["path"])


def test_empty_output_file_is_not_ok_and_temp_removed():
    document = _doc(_FakeObject("Body", _FakeShape()))
    port = _FakeRenderPort(write_bytes=b"")  # writes a 0-byte file
    envelope, port = _run(document, port=port)
    assert envelope["status"] != "OK"
    assert not os.path.exists(port.last_out_path)


def test_absent_output_file_is_not_ok_and_temp_removed():
    document = _doc(_FakeObject("Body", _FakeShape()))
    port = _FakeRenderPort(write_bytes=None)  # never writes the file
    envelope, port = _run(document, port=port)
    assert envelope["status"] != "OK"
    assert not os.path.exists(port.last_out_path)


def test_partial_sub_element_selector_is_invalid_input():
    document = _doc(_FakeObject("Body", _FakeShape()))
    envelope, _ = _run(document, {"focus": {"object": "Body", "element_type": "face"}})
    assert envelope["status"] == "INVALID_INPUT"


def test_degenerate_custom_orientation_is_invalid_input():
    document = _doc(_FakeObject("Body", _FakeShape()))
    envelope, _ = _run(document, {"camera": "custom", "custom_orientation": [0.0, 0.0, 0.0, 0.0]})
    assert envelope["status"] == "INVALID_INPUT"


def test_highlight_sub_element_echoes_whole_object_only():
    document = _doc(_FakeObject("Body", _FakeShape()))
    _, port = _run(
        document,
        {"highlight": {"object": "Body", "element_type": "face", "index": 0}},
    )
    # Highlight is whole-object: the scene carries only the object Name, no sub-element accent.
    assert port.last_scene.highlight == "Body"


# ---- loop-2 regressions (g)-(j) --------------------------------------------------------------


def test_g_render_receives_resolved_document_not_global_or_none():
    body = _FakeObject("Body", _FakeShape())
    document = _doc(body)
    _, port = _run(document, {"include": ["Body"]})
    assert port.last_document is document
    assert port.last_document is not None


def test_h_focus_fallback_echoes_object_only():
    # The port signals focused=False (camera fell back to whole-object framing).
    body = _FakeObject("Body", _FakeShape(faces=1))
    document = _doc(body)
    port = _FakeRenderPort(focused=False)
    envelope, _ = _run(
        document,
        {"focus": {"object": "Body", "element_type": "face", "index": 0}},
        port=port,
    )
    focused_on = envelope["structured_content"]["scene"]["focused_on"]
    assert focused_on == {"object": "Body"}
    assert "element_type" not in focused_on
    assert "index" not in focused_on


def test_h_focus_sub_framed_echoes_full_selector():
    body = _FakeObject("Body", _FakeShape(faces=1))
    document = _doc(body)
    port = _FakeRenderPort(focused=True)
    envelope, _ = _run(
        document,
        {"focus": {"object": "Body", "element_type": "face", "index": 0}},
        port=port,
    )
    focused_on = envelope["structured_content"]["scene"]["focused_on"]
    assert focused_on == {"object": "Body", "element_type": "face", "index": 0}


def test_i_post_render_fingerprint_raise_removes_temp_and_surfaces_error(monkeypatch):
    document = _doc(_FakeObject("Body", _FakeShape()))
    port = _FakeRenderPort()

    # before uses exportBrep; after uses exportBinary → fingerprints_equal raises ValueError.
    calls = {"n": 0}

    def _flip(document_arg):
        calls["n"] += 1
        tag = "exportBrep" if calls["n"] == 1 else "exportBinary"
        return {"schema": "fcb.fingerprint/1", "serializer": tag, "objects": [], "digest": "d"}

    monkeypatch.setattr(screenshot, "fingerprint", _flip)
    envelope, port = _run(document, port=port)
    assert envelope["status"] != "OK"
    assert not os.path.exists(port.last_out_path)


def test_j_selector_with_mapped_name_and_element_is_invalid_input():
    document = _doc(_FakeObject("Body", _FakeShape()))
    envelope, _ = _run(
        document,
        {"focus": {"object": "Body", "mapped_name": "Face1", "element_type": "face", "index": 0}},
    )
    assert envelope["status"] == "INVALID_INPUT"


def test_j_non_string_mapped_name_is_invalid_input():
    document = _doc(_FakeObject("Body", _FakeShape()))
    envelope, _ = _run(document, {"focus": {"object": "Body", "mapped_name": 123}})
    assert envelope["status"] == "INVALID_INPUT"


def test_mutation_detected_removes_temp_and_is_not_ok(monkeypatch):
    document = _doc(_FakeObject("Body", _FakeShape()))
    port = _FakeRenderPort()

    calls = {"n": 0}

    def _changing(document_arg):
        calls["n"] += 1
        return {
            "schema": "fcb.fingerprint/1",
            "serializer": "exportBrep",
            "objects": [],
            "digest": f"digest-{calls['n']}",
        }

    monkeypatch.setattr(screenshot, "fingerprint", _changing)
    envelope, port = _run(document, port=port)
    assert envelope["status"] != "OK"
    assert not os.path.exists(port.last_out_path)


def test_successful_render_returns_image_ref_and_cleans_side_state():
    document = _doc(_FakeObject("Body", _FakeShape()))
    envelope, port = _run(document, {"include": ["Body"]})
    assert envelope["status"] == "OK"
    image = envelope["images"][0]
    assert image["kind"] == "resource_link"
    assert image["mime_type"] == "image/png"
    assert image["audience"] == ["user"]
    assert image["uri"] == port.last_out_path
    assert os.path.exists(port.last_out_path)
    os.remove(port.last_out_path)
