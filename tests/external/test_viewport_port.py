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


# ---- the MDI chain the on-screen name is read from -------------------------------------------


class _FakeWidget:
    """A Qt widget that answers ``isAncestorOf`` from an explicit containment set."""

    def __init__(self, contains=()):
        self._contains = list(contains)

    def isAncestorOf(self, widget):  # noqa: N802 - Qt API name
        return widget in self._contains


class _FakeSubWindow:
    def __init__(self, widget):
        self._widget = widget

    def widget(self):
        return self._widget


class _FakeMdiArea:
    def __init__(self, active):
        self._active = active

    def activeSubWindow(self):  # noqa: N802 - Qt API name
        return self._active


class _FakeMainWindow:
    def __init__(self, central):
        self._central = central

    def centralWidget(self):  # noqa: N802 - Qt API name
        return self._central


class _FakeView3D:
    """A document's live view; ``graphicsView`` returns the viewer widget inside it."""

    def __init__(self, viewer):
        self._viewer = viewer

    def graphicsView(self):  # noqa: N802 - FreeCAD API name
        return self._viewer


def _install_freecad(monkeypatch, names):
    """Stub ``FreeCAD`` so the port can enumerate the open documents by ``Name``."""
    freecad = types.ModuleType("FreeCAD")
    freecad.listDocuments = lambda: {name: object() for name in names}
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)
    return freecad


def _install_screen(monkeypatch, *, focused_document, documents):
    """Wire a fake GUI whose focused MDI sub-window hosts ``focused_document``'s viewer.

    ``documents`` is the ordered list of open document Names; each gets its own viewer widget, and
    only the focused one's viewer sits inside the focused sub-window's widget. ``focused_document``
    of ``None`` focuses a sub-window hosting no document's viewer — the non-3D case.
    """
    viewers = {name: _FakeWidget() for name in documents}
    hosted = [viewers[focused_document]] if focused_document is not None else []
    gui = _install_gui(
        monkeypatch,
        {name: _FakeGuiDocument(_FakeView3D(viewers[name])) for name in documents},
    )
    gui.getMainWindow = lambda: _FakeMainWindow(
        _FakeMdiArea(_FakeSubWindow(_FakeWidget(contains=hosted)))
    )
    _install_freecad(monkeypatch, documents)
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


# ---- the on-screen document name -------------------------------------------------------------


def test_showing_document_name_takes_no_document():
    # The whole point of the method: a per-document accessor cannot answer "which document is on
    # screen", because it resolves through the name it is handed and compares that name to itself.
    for source in (ViewportPort, GuiViewportPort):
        params = list(inspect.signature(source.showing_document_name).parameters)
        assert params == ["self"], source


def test_showing_document_name_names_the_focused_sub_windows_document(monkeypatch):
    # Arrange
    _install_screen(monkeypatch, focused_document="DocB", documents=["DocA", "DocB"])
    target = GuiViewportPort()

    # Act
    showing = target.showing_document_name()

    # Assert
    assert showing == "DocB", "the answer must not depend on which document a caller asks about"


def test_showing_document_name_is_none_when_the_focused_sub_window_is_not_a_3d_view(monkeypatch):
    # A StartView, a spreadsheet or a TechDraw page hosts no document's 3D viewer.
    # Arrange
    _install_screen(monkeypatch, focused_document=None, documents=["DocA", "DocB"])
    target = GuiViewportPort()

    # Act
    showing = target.showing_document_name()

    # Assert
    assert showing is None


@pytest.mark.parametrize(
    "main_window",
    [
        pytest.param(None, id="no main window"),
        pytest.param(_FakeMainWindow(None), id="no central widget"),
        pytest.param(_FakeMainWindow(object()), id="central widget is not an MDI area"),
        pytest.param(_FakeMainWindow(_FakeMdiArea(None)), id="no focused sub-window"),
    ],
)
def test_showing_document_name_is_none_when_a_hop_in_the_chain_is_missing(monkeypatch, main_window):
    # Arrange
    gui = _install_gui(monkeypatch, {})
    gui.getMainWindow = lambda: main_window
    _install_freecad(monkeypatch, [])
    target = GuiViewportPort()

    # Act
    showing = target.showing_document_name()

    # Assert
    assert showing is None


def test_showing_document_name_is_none_rather_than_raising_when_the_gui_raises(monkeypatch):
    # Arrange
    def _explode():
        raise RuntimeError("the main window is being torn down")

    gui = _install_gui(monkeypatch, {})
    gui.getMainWindow = _explode
    _install_freecad(monkeypatch, [])
    target = GuiViewportPort()

    # Act
    showing = target.showing_document_name()

    # Assert
    assert showing is None, "an unreadable name is None, never a raise the caller must handle"


def test_showing_document_name_is_none_without_freecadgui(monkeypatch):
    # Arrange
    monkeypatch.setitem(sys.modules, "FreeCADGui", None)
    target = GuiViewportPort()

    # Act
    showing = target.showing_document_name()

    # Assert
    assert showing is None


def test_showing_document_name_skips_a_document_whose_view_cannot_be_read(monkeypatch):
    """A document with no readable 3D view is not the match, and does not abort the search."""
    # Arrange
    viewer = _FakeWidget()
    gui = _install_gui(
        monkeypatch,
        {"Broken": _FakeGuiDocument(None), "DocB": _FakeGuiDocument(_FakeView3D(viewer))},
    )
    gui.getMainWindow = lambda: _FakeMainWindow(
        _FakeMdiArea(_FakeSubWindow(_FakeWidget(contains=[viewer])))
    )
    _install_freecad(monkeypatch, ["Broken", "DocB"])
    target = GuiViewportPort()

    # Act
    showing = target.showing_document_name()

    # Assert
    assert showing == "DocB"


def test_showing_document_name_never_reads_the_active_document(monkeypatch):
    # The fake's ActiveDocument raises, so a port that consulted it fails here. AD-20 bans the
    # implicit target in every ring, and R2-02 is exactly the defect that ban exists to prevent.
    # Arrange
    _install_screen(monkeypatch, focused_document="DocA", documents=["DocA"])
    target = GuiViewportPort()

    # Act
    showing = target.showing_document_name()

    # Assert
    assert showing == "DocA"


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
