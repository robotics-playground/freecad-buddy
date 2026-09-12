"""``ViewportPort`` implementation for the GUI addon: the one host with a live 3D view.

AD-29 places the live camera in a GUI host rather than in ``adapters/``, so the single Qt
exemption on ``adapters/render_probe.py`` is not widened and ``usecases/`` stays Gui-free. The
port is structural, not a subclass: conformance is proved by ``isinstance`` against the
``@runtime_checkable`` Protocol.
"""

from __future__ import annotations


class GuiViewportPort:
    """Resolves a document's live 3D view through ``FreeCADGui.getDocument(<Name>)``.

    Both answers are per document and never fall back to ``FreeCADGui.ActiveDocument``: a
    viewport belongs to whichever document the GUI has active, so answering from it would
    describe a document the caller never named (the AD-20 implicit-target ban).
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
