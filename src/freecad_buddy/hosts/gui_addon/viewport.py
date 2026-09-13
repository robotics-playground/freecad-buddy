"""``ViewportPort`` implementation for the GUI addon: the one host with a live 3D view.

AD-29 places the live camera in a GUI host rather than in ``adapters/``, so the single Qt
exemption on ``adapters/render_probe.py`` is not widened and ``usecases/`` stays Gui-free. The
port is structural, not a subclass: conformance is proved by ``isinstance`` against the
``@runtime_checkable`` Protocol.
"""

from __future__ import annotations


class GuiViewportPort:
    """Resolves a document's live 3D view through ``FreeCADGui.getDocument(<Name>)``.

    ``available`` and ``view`` are per document and never fall back to
    ``FreeCADGui.ActiveDocument``: a viewport belongs to whichever document the GUI has active, so
    answering from it would describe a document the caller never named (the AD-20 implicit-target
    ban). ``showing_document_name`` is session-wide by design and reads the focused Qt MDI
    sub-window, which is a source independent of any target handle and still names no banned
    attribute.
    """

    def available(self, document: object) -> tuple[bool, str | None]:
        """Return ``(True, None)`` when ``document`` has an open 3D view, else ``(False, reason)``.

        Unavailable is fail-honest: a tuple with a stated reason, never an exception and never a
        fabricated verdict. The three unavailable reasons stay distinguishable, because a caller
        that cannot tell "this process has no GUI" from "this document has no view" cannot report
        the capability honestly:

        * no ``FreeCADGui`` in this interpreter (``FreeCADCmd``, the headless host) — a process
          that can render offscreen still has no live view;
        * no GUI document for this handle's ``Name``;
        * a GUI document whose ``ActiveView`` is ``None``.
        """
        gui = _import_gui()
        if gui is None:
            return (False, "no FreeCADGui in this interpreter: no live viewport")
        name = _document_name(document)
        if name is None:
            return (False, f"not a resolved document handle: {type(document).__name__}")
        try:
            view = gui.getDocument(name).ActiveView
        except Exception:  # noqa: BLE001 - no GUI document for this handle is a reason, not a failure
            return (False, f"no GUI document for '{name}'")
        if view is None:
            return (False, f"document '{name}' has no open 3D view")
        return (True, None)

    def view(self, document: object) -> object | None:
        """Return ``document``'s ``ActiveView``, or ``None`` when it has none. Never raises."""
        gui = _import_gui()
        name = _document_name(document)
        if gui is None or name is None:
            return None
        try:
            return gui.getDocument(name).ActiveView
        except Exception:  # noqa: BLE001 - callers branch on available(); view degrades to None
            return None

    def showing_document_name(self) -> str | None:
        """The ``Name`` of the document the focused 3D sub-window belongs to, or ``None``.

        Takes no document on purpose: ``view(document)`` resolves through the passed handle's own
        ``Name``, so a guard comparing that view's document against the target compares a name
        with itself. This reads the focused Qt MDI sub-window instead — a source the target handle
        does not reach.

        The route is ``FreeCADGui.getMainWindow()`` (``ApplicationPy.cpp:345`` returns a wrapped
        ``QMainWindow``), whose central widget is the ``QMdiArea``
        (``MainWindow.cpp:448``), whose ``activeSubWindow`` hosts the focused view. That widget is
        a shiboken-wrapped C++ ``Gui::View3DInventor`` carrying no Python document attribute, so
        the name comes from matching it against each open document's own view widget: a document
        whose ``ActiveView.graphicsView()`` sits inside the focused sub-window is the document on
        screen.

        ``None`` for every miss — no GUI, no MDI area, no focused sub-window, a focused sub-window
        that is not a 3D view (``StartView``, a spreadsheet, a TechDraw page), or any raise. An
        unreadable name is no evidence of a mismatch, so callers proceed rather than refuse.
        """
        gui = _import_gui()
        if gui is None:
            return None
        try:
            focused = _focused_sub_window_widget(gui)
            if focused is None:
                return None
            return _document_owning(gui, focused)
        except Exception:  # noqa: BLE001 - an unreadable on-screen name is None, never a raise
            return None


def _focused_sub_window_widget(gui: object) -> object | None:
    """The widget the focused ``QMdiSubWindow`` hosts, or ``None`` at any missing hop."""
    main_window = gui.getMainWindow()
    if main_window is None:
        return None
    mdi_area = main_window.centralWidget()
    if mdi_area is None or not hasattr(mdi_area, "activeSubWindow"):
        return None
    sub_window = mdi_area.activeSubWindow()
    if sub_window is None:
        return None
    return sub_window.widget()


def _document_owning(gui: object, focused: object) -> str | None:
    """The open document whose 3D view lives inside ``focused``, or ``None`` when none does.

    Widget identity rather than the sub-window title: the title carries the document ``Label``
    (``MDIView.cpp:523``), and ``Label`` is not ``Name``. Comparing a label against a name would
    refuse on a renamed document and pass on two documents sharing a label.
    """
    import FreeCAD

    for name in FreeCAD.listDocuments():
        try:
            viewer = gui.getDocument(name).ActiveView.graphicsView()
        except Exception:  # noqa: BLE001 - a document with no readable 3D view is not the match
            continue
        if viewer is not None and _is_inside(focused, viewer):
            return name
    return None


def _is_inside(container: object, widget: object) -> bool:
    """Whether ``widget`` is ``container`` or is hosted somewhere below it.

    ``graphicsView()`` (``View3DPy.cpp:2628``) returns the viewer *inside* the view widget, not
    the view widget itself, so the sub-window's own widget is an ancestor rather than the same
    object. ``isAncestorOf`` is the Qt answer; the identity check ahead of it covers a build
    whose sub-window hosts the viewer directly.
    """
    if container is widget:
        return True
    try:
        return bool(container.isAncestorOf(widget))
    except Exception:  # noqa: BLE001 - a widget that cannot answer is not a match
        return False


def _import_gui() -> object | None:
    """The ``FreeCADGui`` module, or ``None`` in an interpreter that has none.

    Imported function-locally inside a guard so this module loads cleanly with no GUI, matching
    the ``bootstrap.py`` pattern.
    """
    try:
        import FreeCADGui
    except Exception:  # noqa: BLE001 - no GUI is a capability answer, not a failure
        return None
    return FreeCADGui


def _document_name(document: object) -> str | None:
    """``document``'s resolved ``Name``, or ``None`` when the handle carries none.

    The view is always resolved from this ``Name``, never from ``FreeCADGui.ActiveDocument``.
    """
    name = getattr(document, "Name", None)
    return name if isinstance(name, str) else None
