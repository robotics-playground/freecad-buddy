"""Fit the targeted document's model into its own live viewport (Gui-free).

``view_fit_viewport`` is the one tool that moves the human's camera. It is confirm-exempt — the
camera is not geometry, so there is nothing to preview and nothing to roll back — but it is
audited, and the audit line carries the verbatim pre-fit camera string so the move is
reconstructable (AD-31).

The record is written here rather than by the dispatch bracket because neither dispatch site has
camera knowledge: teaching one to read a camera would put Gui knowledge in an adapter and give
every tool a field it does not have. ``confirm.audit_approval`` is the shipped precedent for a
usecase writing its own record for something dispatch cannot see. The dispatch bracket still
writes its own generic before/after lines, so a fit is audited twice: once generically, once with
the camera.

Contains no ``FreeCADGui``/Qt import. The view arrives as an opaque object from the host-injected
``ViewportPort`` and is only duck-typed (``getCamera``, ``fitAll``).
"""

from __future__ import annotations

import math

from freecad_buddy.contracts import ResultEnvelope, ViewportPort
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
from freecad_buddy.usecases.framing import Bounds, union_bbox
from freecad_buddy.usecases.screenshot import is_default_renderable

_AUDIT_SINK: object = None

# Fraction of the binding viewport axis the model is framed to fill. 0.95 leaves a 5% margin:
# enough that the part never reads as clipped and a small camera nudge does not push a corner
# outside, while still filling the screen. Measured on a 40x40x800 bar and a 40x25x15 plate in
# top, front and isometric views; at 1.0 both touched the edge, at 0.90 the empty border was
# plainly visible.
_FILL_FRACTION = 0.95

# Floor on the computed fitAll factor. A factor at or below zero is refused outright by
# ``viewAll`` (``View3DInventorViewer.cpp:4463``), so a degenerate measurement must never
# produce one; this keeps the call a no-op zoom rather than a silently skipped fit.
_MIN_FIT_FACTOR = 0.01


def set_audit_sink(sink: object) -> object:
    """Install the sink camera-move records are written to; return the one it replaced.

    The wired handlers take no sink argument of their own (``HandlerFactory`` has no sink
    parameter), so the host installs one here exactly as it installs the approval sink.
    """
    global _AUDIT_SINK
    previous = _AUDIT_SINK
    _AUDIT_SINK = sink
    return previous


def view_fit_viewport(
    registry: DocumentRegistry,
    viewport_port: ViewportPort | None,
    doc: str | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Fit ``doc``'s model into ``doc``'s own live viewport, and audit the camera it replaced.

    The view is resolved per document through the injected port, never from the process-global
    active document: fitting whichever document the GUI happens to show would move a camera the
    caller never named (the AD-20 implicit-target ban).

    A host with no viewport, or a document whose viewport is unavailable, returns a non-``OK``
    envelope naming the reason and touches no camera. A viewport that is showing a different
    document raises ``ValidationError`` naming **both** documents, so the agent can act rather
    than guess; the fit is never redirected and the named document is never activated.

    :param audit_sink: sink exposing ``camera``; defaults to the host-installed one.
    :raises ValidationError: the handle is missing, unknown, or names a document the live
        viewport is not showing.
    """

    def fit(handle: str, document: object) -> ResultEnvelope:
        # The handle is resolved first, so a bad handle is INVALID_INPUT on every host rather than
        # being masked by the headless "no viewport" answer. A caller cannot fix a stale handle it
        # was never told about.
        if viewport_port is None:
            return _unavailable_envelope("this host has no live viewport: no camera to fit")
        available, reason = viewport_port.available(document)
        if not available:
            return _unavailable_envelope(reason or "the viewport reported itself unavailable")
        view = viewport_port.view(document)
        if view is None:
            return _unavailable_envelope(f"'{_name_of(document)}' has no live 3D view to fit")
        _require_same_document(document, view)

        camera_before = _read_camera(view)
        try:
            _fit_all(view, document)
        except Exception as exc:  # noqa: BLE001 - a view that refuses the fit is a stated reason
            return _failed_envelope(f"the view refused the fit: {type(exc).__name__}: {exc}")

        _audit(audit_sink, handle, {"doc": handle}, camera_before)
        return _fitted_envelope(_name_of(document), camera_before)

    return registry.with_document(doc, fit)


def _fit_all(view: object, document: object) -> None:
    """Orient isometrically and frame the model, filling the viewport to ``_FILL_FRACTION``.

    **This cannot measure its own result, so it does not try.** The fit runs on the Qt main thread
    inside the marshal, which is the thread that applies camera changes: ``viewIsometric`` starts a
    ``NavigationAnimation`` through Qt signals (``NavigationAnimator.cpp:45-57``) and
    ``viewBoundBox`` animates too (``View3DInventorViewer.cpp:4821``), so both land only once this
    call returns and the event loop runs again. Any projection taken here reads the camera as it
    was *before* the fit, which is why a measure-then-correct loop silently converged on the wrong
    framing and still reported success.

    The framing is therefore computed from geometry, which needs no feedback. ``fitAll(factor)``
    scales the scene box by ``factor`` and frames the result
    (``View3DInventorViewer.cpp:4467-4488``), and the framing is sphere-based — the camera height
    becomes the box's space diagonal (``cam->viewBoundingBox``). A part therefore lands at
    ``silhouette / diagonal`` of the viewport, which is 0.58 for a cube but only 0.05 for a
    40x40x800 bar. Passing ``factor = silhouette / diagonal / _FILL_FRACTION`` cancels exactly
    that shrinkage and leaves the requested margin.

    The camera is oriented isometrically first — the standard TOP/FRONT/RIGHT corner view, which
    shows all three dimensions at once. A fit exists to show the human the work, and a top view
    down a tall bar shows only its end face however well it is zoomed.
    """
    factor = _fill_factor(document)
    with _animation_suspended(view):
        _view_isometric(view)
        _fit_all_with_factor(view, factor)


class _animation_suspended:  # noqa: N801 - a context manager reads as a statement, not a class
    """Turn the view's camera animation off for the fit, and restore it afterwards.

    This is what makes a fit land within its own call. Both camera writes animate by default:
    ``viewIsometric`` starts a ``NavigationAnimation`` and ``viewBoundBox`` calls
    ``animatedViewAll`` when animation is enabled (``View3DInventorViewer.cpp:4821``). An
    animation advances on the Qt event loop — the loop this code is blocking while it runs inside
    the marshal — so both would land only after the call returned, and the agent's next call would
    see a camera the fit never observed. With animation off, ``setAnimationEnabled`` stops
    anything already in flight and the camera is written synchronously
    (``NavigationStyle.cpp:1660-1666``).

    The previous setting is restored even when the fit raises: this is the human's viewer, and a
    fit must not leave their navigation animation switched off.
    """

    def __init__(self, view: object) -> None:
        self._view = view
        self._previous: bool | None = None

    def __enter__(self) -> None:
        try:
            self._previous = bool(self._view.isAnimationEnabled())
            self._view.setAnimationEnabled(False)
        except Exception:  # noqa: BLE001 - a view without the toggle still fits, just animated
            self._previous = None

    def __exit__(self, *_exc: object) -> None:
        if self._previous is None:
            return
        try:
            self._view.setAnimationEnabled(self._previous)
        except Exception:  # noqa: BLE001 - restoring is best-effort; the fit itself already landed
            pass


def _fill_factor(document: object) -> float:
    """The ``fitAll`` factor that leaves ``_FILL_FRACTION`` of the binding axis filled.

    ``1.0`` (a plain fit) whenever the geometry cannot be measured, so an unreadable document
    still gets framed rather than refused.
    """
    box = _document_bounds(document)
    if box is None:
        return 1.0
    xmin, ymin, zmin, xmax, ymax, zmax = box
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
    diagonal = math.sqrt(dx * dx + dy * dy + dz * dz)
    if diagonal <= 0.0:
        return 1.0
    # The isometric silhouette of a box is bounded by its largest face diagonal: looking down a
    # cube corner, the widest thing on screen is a face diagonal, never the space diagonal the
    # sphere framing reserves room for. Using the largest of the three keeps the whole model
    # inside for any of the eight isometric corners, so no orientation clips.
    silhouette = max(
        math.sqrt(dx * dx + dy * dy),
        math.sqrt(dy * dy + dz * dz),
        math.sqrt(dx * dx + dz * dz),
    )
    return max(silhouette / diagonal / _FILL_FRACTION, _MIN_FIT_FACTOR)


def _document_bounds(document: object) -> Bounds | None:
    """The union bbox of the document's visible shape-bearing objects, or ``None``."""
    try:
        return union_bbox([obj for obj in document.Objects if is_default_renderable(obj)])
    except Exception:  # noqa: BLE001 - an unreadable document degrades to a plain fit
        return None


def _fit_all_with_factor(view: object, factor: float) -> None:
    """``fitAll(factor)``, falling back to the no-argument form for a view that takes none.

    ``fitAll`` takes an optional factor (``View3DPy.cpp:484-492``), but the view is duck-typed
    here and an older or stubbed one may accept no argument at all. A ``TypeError`` from the arity
    is retried bare rather than reported as a refused fit: the bare call still frames the model,
    just with the sphere's own margin instead of the requested one.
    """
    try:
        view.fitAll(factor)
    except TypeError:
        view.fitAll()






def _view_isometric(view: object) -> None:
    """Swing the camera to isometric so an edge-on model shows its real extent.

    A view that does not expose the orientation is left pointing where it was: the fit still
    frames the model from the camera the human already chose, which is worse framing for a tall
    part but never a failed fit.
    """
    try:
        view.viewIsometric()
    except Exception:  # noqa: BLE001 - orientation is a nicety; the zoom below is the fit
        pass



def _require_same_document(document: object, view: object) -> None:
    """Raise unless ``view`` is showing ``document``.

    The port resolves a view through ``getDocument(<Name>)``, so a view handed back for document A
    belongs to A. The failure this guards is the other direction: a view that carries its own
    document name and that name is not the one the call targeted. Both names go in the message —
    an agent told only "wrong document" cannot tell which of its handles is stale.
    """
    target = _name_of(document)
    showing = _name_of(_view_document(view))
    if showing is None or target is None or showing == target:
        return
    raise ValidationError(
        f"the live viewport is showing '{showing}', not the targeted '{target}'; "
        f"call view_fit_viewport with the handle for '{showing}', or open a 3D view "
        f"for '{target}'"
    )


def _view_document(view: object) -> object | None:
    """The App document a view reports as its own, or ``None`` when it reports none.

    A ``View3DInventor`` exposes its Gui document as ``Document``, whose ``Document`` in turn is
    the App document. Both hops are optional: a view that names neither is not evidence of a
    mismatch, so the caller treats an unreadable name as "no contradiction".
    """
    gui_document = getattr(view, "Document", None)
    if gui_document is None:
        return None
    return getattr(gui_document, "Document", gui_document)


def _name_of(document: object | None) -> str | None:
    """``document``'s resolved ``Name``, or ``None`` when it carries none."""
    name = getattr(document, "Name", None)
    return name if isinstance(name, str) else None


def _read_camera(view: object) -> str | None:
    """The view's verbatim camera string, or ``None`` when it has no readable one.

    Best-effort by design: a camera the view will not hand over must not block the fit the caller
    asked for. The field is then omitted from the audit line rather than fabricated.
    """
    try:
        camera = view.getCamera()
    except Exception:  # noqa: BLE001 - an unreadable camera omits the field, never blocks the fit
        return None
    return camera if isinstance(camera, str) else None


def _audit(sink: object, handle: str, params: dict, camera_before: str | None) -> None:
    """Append one camera-move audit line, preferring a caller-supplied sink over the host's.

    A sink that cannot write must not convert a completed fit into a raised exception, so a write
    failure is swallowed here.
    """
    target = sink if sink is not None else _AUDIT_SINK
    if target is None:
        return
    try:
        target.camera("view_fit_viewport", handle, params, camera_before)
    except Exception:  # noqa: BLE001 - an unwritable audit sink must not abort the fit
        pass


def _fitted_envelope(name: str | None, camera_before: str | None) -> ResultEnvelope:
    structured = {
        "fitted": True,
        "document": name,
        "camera_recorded": camera_before is not None,
    }
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": f"fitted the live viewport to '{name}'",
    }


def _unavailable_envelope(reason: str) -> ResultEnvelope:
    """No camera was moved because there was none to move. Degrades honestly, never silently."""
    return _refused_envelope("view_fit.no_viewport", reason)


def _failed_envelope(reason: str) -> ResultEnvelope:
    """A live view was found and still would not fit."""
    return _refused_envelope("view_fit.failed", reason)


def _refused_envelope(code: str, reason: str) -> ResultEnvelope:
    structured = {"fitted": False, "reason": reason}
    return {
        "schema": "fcb.result-envelope/1",
        "status": "SPEC_FAILED",
        "detail": {"code": code, "message": reason},
        "structured_content": structured,
        "text": reason,
    }


__all__ = ["set_audit_sink", "view_fit_viewport"]
