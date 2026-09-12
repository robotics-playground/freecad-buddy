"""``ViewportPort`` contract + GUI-host implementation tests (no FreeCAD).

Covers the story 8.1 I/O matrix: Protocol conformance proved by arity as well as by name, the
fail-honest ``(False, reason)`` answers with their reasons distinguished, the AD-20 rule that the
answer is always for the passed document (the fake raises on any ``ActiveDocument`` read), and
the GUI-host injection at the ``build_inline_handlers`` wiring seam. Every FreeCAD and Qt object
here is a fake, because this leg runs in an interpreter with neither installed.
"""

from __future__ import annotations

import inspect
import sys
import types

import pytest

from freecad_buddy.contracts import RenderPort, ViewportPort
from freecad_buddy.hosts.gui_addon.viewport import GuiViewportPort

# ---- fakes -----------------------------------------------------------------------------------


class _FakeDocument:
    """A resolved App document handle; only ``Name`` is read by the port."""

    def __init__(self, name):
        self.Name = name


class _FakeGuiDocument:
    def __init__(self, active_view):
        self.ActiveView = active_view


class _FakeGui:
    """Stand-in for the ``FreeCADGui`` module: maps a document Name to its GUI document.

    ``ActiveDocument`` raises rather than returning a value, so a port that consulted the
    process-global active document fails the test instead of quietly passing it. The real
    checker cannot catch that read today — ``check_imports.FREECAD_MODULE_ALIASES`` omits
    ``FreeCADGui`` (story 8.5's scope) — so this fake is the guard.
    """

    def __init__(self, documents):
        self._documents = documents
        self.requested_names = []

    def getDocument(self, name):  # noqa: N802 - FreeCAD API name
        self.requested_names.append(name)
        try:
            return self._documents[name]
        except KeyError:
            raise NameError(f"no document '{name}'") from None

    @property
    def ActiveDocument(self):  # noqa: N802 - FreeCAD API name
        raise AssertionError(
            "FreeCADGui.ActiveDocument was read; the view must resolve from the passed "
            "document's Name (AD-20)"
        )


def _install_gui(monkeypatch, documents):
    """Put a fake ``FreeCADGui`` on ``sys.modules`` so the port's local import resolves to it."""
    gui = _FakeGui(documents)
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    return gui


# ---- conformance -----------------------------------------------------------------------------


def test_viewport_port_protocol_shape():
    assert isinstance(GuiViewportPort(), ViewportPort)


def test_viewport_port_methods_take_a_document_argument():
    # runtime_checkable isinstance matches method NAMES only, so it would accept a port whose
    # available()/view() take no document. The per-document answer is this story's whole point.
    for method_name in ("available", "view"):
        protocol_params = list(inspect.signature(getattr(ViewportPort, method_name)).parameters)
        impl_params = list(inspect.signature(getattr(GuiViewportPort, method_name)).parameters)
        assert protocol_params == ["self", "document"], method_name
        assert impl_params == ["self", "document"], method_name


def test_viewport_port_is_not_a_render_port_extension():
    assert not issubclass(ViewportPort, RenderPort)
    assert not issubclass(RenderPort, ViewportPort)


# ---- availability ----------------------------------------------------------------------------


def test_available_true_when_the_document_has_an_open_view(monkeypatch):
    view = object()
    gui = _install_gui(monkeypatch, {"Part": _FakeGuiDocument(view)})
    target = GuiViewportPort()
    document = _FakeDocument("Part")
    assert target.available(document) == (True, None)
    assert target.view(document) is view
    assert gui.requested_names == ["Part", "Part"]


def test_available_false_naming_the_document_when_it_has_no_view(monkeypatch):
    _install_gui(monkeypatch, {"Part": _FakeGuiDocument(None)})
    target = GuiViewportPort()
    document = _FakeDocument("Part")
    available, reason = target.available(document)
    assert available is False
    assert "Part" in reason
    assert "no open 3D view" in reason
    assert target.view(document) is None


def test_available_false_naming_the_missing_gui_when_freecadgui_is_absent(monkeypatch):
    # ``None`` in sys.modules makes ``import FreeCADGui`` raise ImportError even where a real
    # FreeCAD is installed, so this case is the headless answer on every machine.
    monkeypatch.setitem(sys.modules, "FreeCADGui", None)
    target = GuiViewportPort()
    document = _FakeDocument("Part")
    available, reason = target.available(document)
    assert available is False
    assert "FreeCADGui" in reason
    assert target.view(document) is None


def test_available_false_naming_the_document_when_no_gui_document_exists(monkeypatch):
    _install_gui(monkeypatch, {})
    target = GuiViewportPort()
    document = _FakeDocument("Part")
    available, reason = target.available(document)
    assert available is False
    assert "no GUI document" in reason
    assert "Part" in reason
    assert target.view(document) is None


def test_the_three_unavailable_reasons_are_distinguishable(monkeypatch):
    document = _FakeDocument("Part")
    target = GuiViewportPort()

    monkeypatch.setitem(sys.modules, "FreeCADGui", None)
    _no_gui = target.available(document)[1]
    _install_gui(monkeypatch, {})
    _no_document = target.available(document)[1]
    _install_gui(monkeypatch, {"Part": _FakeGuiDocument(None)})
    _no_view = target.available(document)[1]

    assert len({_no_gui, _no_document, _no_view}) == 3


def test_a_handle_without_a_name_reports_a_stated_reason_not_a_raw_attribute_error(monkeypatch):
    _install_gui(monkeypatch, {"Part": _FakeGuiDocument(object())})
    target = GuiViewportPort()
    available, reason = target.available(object())
    assert available is False
    assert "AttributeError" not in reason
    assert "has no attribute" not in reason
    assert "document handle" in reason


# ---- per-document targeting ------------------------------------------------------------------


def test_available_answers_for_the_passed_document_not_the_visible_one(monkeypatch):
    # DocB is the one with an open view; asking about DocA must answer for DocA. The fake's
    # ActiveDocument raises, so a port that consulted it fails here rather than passing.
    gui = _install_gui(
        monkeypatch,
        {"DocA": _FakeGuiDocument(None), "DocB": _FakeGuiDocument(object())},
    )
    available, _reason = GuiViewportPort().available(_FakeDocument("DocA"))
    assert available is False
    assert gui.requested_names == ["DocA"]


def test_view_returns_the_passed_documents_view_and_not_the_other_ones(monkeypatch):
    view_a = object()
    view_b = object()
    gui = _install_gui(
        monkeypatch,
        {"DocA": _FakeGuiDocument(view_a), "DocB": _FakeGuiDocument(view_b)},
    )
    resolved = GuiViewportPort().view(_FakeDocument("DocA"))
    assert resolved is view_a
    assert resolved is not view_b
    assert gui.requested_names == ["DocA"]


def test_the_fake_gui_active_document_raises_so_the_guard_has_teeth(monkeypatch):
    # Proves the guard above is real: reading ActiveDocument on the fake does fail.
    gui = _install_gui(monkeypatch, {})
    with pytest.raises(AssertionError):
        _ = gui.ActiveDocument


# ---- GUI-host injection ----------------------------------------------------------------------


def _install_qt(monkeypatch):
    """Stub ``PySide.QtCore`` so ``hosts.gui_addon.pump`` imports without Qt installed.

    ``pump`` subclasses ``QtCore.QObject`` and calls ``QEvent.registerEventType()`` at module
    import, so the stub must supply both before ``bootstrap`` can be imported at all.
    """

    class _QEvent:
        Type = staticmethod(lambda value: value)

        def __init__(self, *args):
            pass

        @staticmethod
        def registerEventType():  # noqa: N802 - Qt API name
            return 1000

    class _QObject:
        def __init__(self, *args, **kwargs):
            pass

    class _QCoreApplication:
        @staticmethod
        def instance():
            return None

        @staticmethod
        def postEvent(receiver, event):
            pass

    qtcore = types.ModuleType("PySide.QtCore")
    qtcore.QEvent = _QEvent
    qtcore.QObject = _QObject
    qtcore.QCoreApplication = _QCoreApplication
    pyside = types.ModuleType("PySide")
    pyside.QtCore = qtcore
    monkeypatch.setitem(sys.modules, "PySide", pyside)
    monkeypatch.setitem(sys.modules, "PySide.QtCore", qtcore)


def test_gui_addon_injects_a_live_viewport_port_at_the_wiring_seam(monkeypatch, tmp_path):
    """``start_bridge`` must hand ``build_inline_handlers`` a real ``ViewportPort``.

    This is the only behavioral change in story 8.1 that reaches a running process, so without
    this test replacing the injection with ``None`` would pass the whole suite.
    """
    _install_qt(monkeypatch)
    monkeypatch.setenv("FREECAD_BUDDY_LOG_FILE", str(tmp_path / "addon.log"))
    monkeypatch.setenv("FREECAD_BUDDY_NO_AUTO_MCP", "1")

    from freecad_buddy.hosts.gui_addon import bootstrap

    captured = {}

    def _capture(*args, **kwargs):
        captured.update(kwargs)
        return "registry"

    class _FakeListener:
        def __init__(self, *args, **kwargs):
            pass

        def start_threaded(self):
            return ("127.0.0.1", 1234)

    monkeypatch.setattr(bootstrap, "build_inline_handlers", _capture)
    monkeypatch.setattr(bootstrap, "RpcListener", _FakeListener)
    monkeypatch.setattr(bootstrap, "_register_shutdown", lambda: None)
    monkeypatch.setattr(bootstrap, "_start_mcp_proxy", lambda: None)
    monkeypatch.setattr(bootstrap, "_listener", None)

    try:
        bootstrap.start_bridge()
    finally:
        bootstrap._listener = None

    assert "viewport_port" in captured, "the GUI host must pass viewport_port by keyword"
    assert isinstance(captured["viewport_port"], ViewportPort)
    assert captured["viewport_port"] is not None


def test_headless_host_injects_no_viewport_port(monkeypatch):
    """The headless host has no live view, so it must state ``viewport_port=None``."""
    from freecad_buddy.hosts.headless import entry

    captured = {}

    def _capture(*args, **kwargs):
        captured.update(kwargs)
        return "registry"

    monkeypatch.setattr(entry, "build_inline_handlers", _capture)
    entry.build_registry(object(), object(), object())

    assert "viewport_port" in captured, "the headless host must state the no-viewport case"
    assert captured["viewport_port"] is None
