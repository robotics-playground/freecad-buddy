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

``fitted: true`` is a measurement, never "the call ran": the fit re-projects through the camera it
wrote and reports ``SPEC_FAILED`` when that projection contradicts it (AD-31).

Contains no ``FreeCADGui``/Qt import. The view arrives as an opaque object from the host-injected
``ViewportPort`` and is only duck-typed (``getCamera``, ``fitAll``, ``boxZoom``,
``getPointOnViewport``, ``getSize``).
"""

from __future__ import annotations

from freecad_buddy.contracts import FramingVerdict, ResultEnvelope, ViewportPort
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
from freecad_buddy.usecases.framing import (
    ProjectedHull,
    measure_framing,
    model_bounds,
    projected_hull,
)

_AUDIT_SINK: object = None

# Fraction of the binding viewport axis the model is framed to fill. 0.95 leaves a 5% margin:
# enough that the part never reads as clipped and a small camera nudge does not push a corner
# outside, while still filling the screen. Measured on a 40x40x800 bar and a 40x25x15 plate in
# top, front and isometric views; at 1.0 both touched the edge, at 0.90 the empty border was
# plainly visible.
_FILL_FRACTION = 0.95

# Floor on each side of the zoom box, as a fraction of that viewport dimension. ``boxZoom`` returns
# without moving the camera for a 0x0 box (``NavigationStyle.cpp:599``), so a model measured as
# a sub-pixel dot would otherwise be left as a dot; the floor keeps the zoom one the view acts on.
_MIN_ZOOM_BOX_FRACTION = 0.01


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
    than guess; the fit is never redirected and the named document is never activated. A document
    with nothing measurable on screen (only datums, for example) returns ``SPEC_FAILED`` with
    ``view_fit.nothing_to_frame`` and no ``framing`` block; no camera is touched.

    ``OK`` requires the post-fit re-projection to agree: a fit whose own measurement says the model
    still overflows returns ``SPEC_FAILED`` carrying that verdict as a top-level ``framing`` block.
    There is no second attempt — a contradiction is an honest failure, and the camera stays where
    the fit left it, which is still the best framing the tool achieved.

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
        _require_same_document(document, viewport_port)
        if _nothing_to_frame(document):
            return _refused_envelope(
                "view_fit.nothing_to_frame",
                "no visible object to frame; datum planes are infinite and are not measured",
            )

        camera_before = _read_camera(view)
        try:
            verdict = _fit_all(view, document)
        except _AnimationRefused as refused:
            return _refused_envelope("view_fit.animation", str(refused))
        except Exception as exc:  # noqa: BLE001 - a view that refuses the fit is a stated reason
            return _failed_envelope(f"the view refused the fit: {type(exc).__name__}: {exc}")

        _audit(audit_sink, handle, {"doc": handle}, camera_before)
        if verdict.get("fits") is True:
            return _fitted_envelope(_name_of(document), camera_before)
        if verdict.get("checked") == "unavailable":
            return _unverified_envelope(verdict)
        return _not_framed_envelope(verdict)

    return registry.with_document(doc, fit)


def _fit_all(view: object, document: object) -> FramingVerdict:
    """Orient isometrically, frame the model to ``_FILL_FRACTION``, and measure the result.

    Three passes inside one suspended block, which is what lets the fit verify itself (AD-30):

    1. ``viewIsometric`` then a plain ``fitAll(1.0)``, so the camera is in a *known* state and the
       model is on screen, and ``projected_hull`` through it boxes the measured set's corners.
    2. ``boxZoom`` on that hull, expanded about its centre by ``1 / _FILL_FRACTION``. ``boxZoom``
       pans the box centre to the view centre and scales by the larger axis quotient
       (``NavigationStyle.cpp:584-620``), so the measured model is centred and its binding axis
       lands on the requested fill. ``fitAll`` cannot do this pass: it centres on the Coin scene
       box, which includes a drawn datum plane the measurement leaves out, so a pad beside a datum
       plane was zoomed to 95 % off-centre and overflowed.
    3. ``measure_framing`` through the camera pass 2 just wrote. Its verdict is the one the caller
       gets, and it is what makes ``fitted: true`` a measurement rather than a report that the
       call ran.

    Passes 1 and 3 measure with the *same* corners and projection the framing verdict uses. An
    analytic estimate of the same quantity was the defect: it underestimated the projected extent
    by 1.155x on a cube and overestimated it by 0.856x on a 40x40x800 bar, so compact parts were
    zoomed past the edge while the tool reported success.

    The measurement is only sound because animation is suspended: with animation on, the
    orientation and ``fitAll`` writes land after this call returns, so the pass-1 hull and pass 3
    would both read the pre-fit camera. That is why a toggle that exists and refuses is a refusal
    rather than a degraded fit.

    The camera is oriented isometrically first — the standard TOP/FRONT/RIGHT corner view, which
    shows all three dimensions at once. A fit exists to show the human the work, and a top view
    down a tall bar shows only its end face however well it is zoomed.
    """
    with _animation_suspended(view):
        _view_isometric(view)
        _fit_all_known_state(view)
        box = _zoom_box(_hull(document, view))
        if box is not None:
            view.boxZoom(*box)
        return _measure(document, view)


def _measure(document: object, view: object) -> FramingVerdict:
    """``measure_framing``, with an unreadable document reported rather than raised.

    ``measure_framing`` reads ``document.Objects`` unguarded — correct on its own path, where the
    caller already resolved a live document. Here the same raise would be reported as "the view
    refused the fit", blaming the view for a document it never saw.
    """
    try:
        return measure_framing(document, view)
    except Exception as exc:  # noqa: BLE001 - an unreadable document is a stated reason
        return {
            "fits": None,
            "ratio": None,
            "checked": "unavailable",
            "stale_reason": f"the document's model could not be read: {type(exc).__name__}",
        }


def _nothing_to_frame(document: object) -> bool:
    """Whether ``document`` has nothing the fit could measure, checked before the camera moves.

    Without this a datum-only document zooms onto nothing and pass 3 has no box to grade. A box
    with zero size on all three axes (a sketch holding one point) is nothing too: it projects to
    one pixel, so the fit would report ``OK`` beside a ratio of ``0.0``. A document that cannot be
    read at all is not "nothing": the fit runs, and ``_measure`` names the read failure in the
    verdict.
    """
    try:
        box = model_bounds(document)
    except Exception:  # noqa: BLE001 - an unreadable document is reported by the fit's own verdict
        return False
    return box is None or all(box[axis + 3] - box[axis] == 0.0 for axis in range(3))


def _hull(document: object, view: object) -> ProjectedHull | None:
    """``projected_hull``, with any read failure meaning "no hull" rather than a raise.

    ``None`` skips pass 2 only. The plain ``fitAll(1.0)`` already ran, so a model the camera was
    pointed away from is still recovered with FreeCAD's own margin, and pass 3 names whatever
    could not be read.
    """
    try:
        return projected_hull(document, view)
    except Exception:  # noqa: BLE001 - pass 3 reports the failure; pass 2 is skipped
        return None


def _zoom_box(hull: ProjectedHull | None) -> tuple[int, int, int, int] | None:
    """The ``boxZoom(XMin, YMin, XMax, YMax)`` box that frames ``hull`` to ``_FILL_FRACTION``.

    The hull is expanded about its centre by ``1 / _FILL_FRACTION`` on both axes, so the larger
    axis quotient ``boxZoom`` scales by is the hull's binding ratio over ``_FILL_FRACTION``. Each
    side is floored at ``_MIN_ZOOM_BOX_FRACTION`` of its viewport dimension.
    ``getPointOnViewport`` is Y-up and ``boxZoom`` Y-down (it centres on
    ``height - (ymin + ymax) / 2``), so Y is flipped. ``boxZoom`` parses ``short`` integers, so
    the corners are rounded.
    """
    if hull is None:
        return None
    half_width = (
        max((hull.xmax - hull.xmin) / _FILL_FRACTION, _MIN_ZOOM_BOX_FRACTION * hull.width) / 2
    )
    half_height = (
        max((hull.ymax - hull.ymin) / _FILL_FRACTION, _MIN_ZOOM_BOX_FRACTION * hull.height) / 2
    )
    centre_x = (hull.xmin + hull.xmax) / 2
    centre_y = hull.height - (hull.ymin + hull.ymax) / 2
    return (
        round(centre_x - half_width),
        round(centre_y - half_height),
        round(centre_x + half_width),
        round(centre_y + half_height),
    )


class _AnimationRefused(Exception):
    """The view has an animation toggle that refused, so the fit cannot verify its own camera."""


class _Unsuspended:
    """ "Nothing was suspended, so there is nothing to restore" — distinct from any bool setting.

    A sentinel rather than ``None`` because ``None`` would also be the natural spelling of "the
    previous setting could not be read", and conflating the two is what left animation switched
    off in the human's viewer after an unreadable ``isAnimationEnabled``.
    """


_UNSUSPENDED = _Unsuspended()


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

    Suspension is a **precondition**, not a nicety, because the fit now re-projects through the
    camera it wrote: with animation on, that projection reads the pre-fit camera and would grade a
    fit that had not happened yet. A toggle that is *present and refuses* therefore raises
    ``_AnimationRefused`` before any camera is touched. A view with **no** toggle at all is a
    different case — nothing is animating, so the fit proceeds.

    The previous setting is restored even when the fit raises: this is the human's viewer, and a
    fit must not leave their navigation animation switched off.
    """

    def __init__(self, view: object) -> None:
        self._view = view
        self._previous: bool | None | _Unsuspended = _UNSUSPENDED

    def __enter__(self) -> None:
        suspend = getattr(self._view, "setAnimationEnabled", None)
        if suspend is None:
            return
        try:
            previous = bool(self._view.isAnimationEnabled())
        except Exception:  # noqa: BLE001 - an unreadable setting is restored to the safe default
            previous = True
        try:
            suspend(False)
        except Exception as exc:
            raise _AnimationRefused(
                "the view refused to suspend camera animation, so the fit cannot verify the "
                f"camera it writes: {type(exc).__name__}: {exc}"
            ) from exc
        self._previous = previous

    def __exit__(self, *_exc: object) -> None:
        if self._previous is _UNSUSPENDED:
            return
        try:
            self._view.setAnimationEnabled(self._previous)
        except Exception:  # noqa: BLE001 - restoring is best-effort; the fit itself already landed
            pass


def _fit_all_known_state(view: object) -> None:
    """``fitAll(1.0)``, falling back to the no-argument form for a view that takes none.

    ``fitAll`` takes an optional factor (``View3DPy.cpp:484-492``), but the view is duck-typed
    here and an older or stubbed one may accept no argument at all. A ``TypeError`` from the arity
    is retried bare rather than reported as a refused fit; both forms frame the same camera.
    """
    try:
        view.fitAll(1.0)
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


def _require_same_document(document: object, viewport_port: ViewportPort) -> None:
    """Raise unless the one document on screen is ``document``.

    The on-screen name comes from the port's session-wide ``showing_document_name``, never from
    the view: ``view(document)`` is resolved through the target's own ``Name``, so comparing that
    view's document against the target compares a name with itself and can never fire. That
    tautology is what let a fit rewrite the camera of the document the human was looking at.

    ``None`` proceeds. An unreadable on-screen name — no viewport, a focused sub-window that is
    not a 3D view — is no evidence of a mismatch, and refusing on it would make the tool unusable
    wherever the name cannot be read.

    Both names go in the message: an agent told only "wrong document" cannot tell which of its
    handles is stale. The named document is never activated and no camera is touched; the caller
    decides which handle it meant.
    """
    target = _name_of(document)
    showing = viewport_port.showing_document_name()
    if showing is None or target is None or showing == target:
        return
    raise ValidationError(
        f"the live viewport is showing '{showing}', not the targeted '{target}'; "
        f"call view_fit_viewport with the handle for '{showing}', or open a 3D view "
        f"for '{target}'"
    )


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


def _not_framed_envelope(verdict: FramingVerdict) -> ResultEnvelope:
    """The fit ran, re-projected, and the model still does not fit: an honest failure, not a retry.

    This is AD-32's single carve-out to the omit-on-non-``OK`` rule. The verdict is freshly
    ``"computed"``, it is the *cause* of the status rather than a leftover, and ``ratio`` lives
    nowhere else in the contract — so the block rides the envelope. ``with_framing`` returns a
    non-``OK`` envelope untouched, so nothing strips it and nothing attaches a second copy.

    The number stays out of ``text`` and ``detail.message``: the ratio reaches the caller through
    the block, and a hand-written copy is a second place for it to drift.
    """
    reason = (
        "the fit ran and the model still does not fit the live viewport; "
        "read the framing block for the measured overflow"
    )
    envelope = _refused_envelope("view_fit.not_framed", reason)
    return {**envelope, "framing": verdict}


def _unverified_envelope(verdict: FramingVerdict) -> ResultEnvelope:
    """The fit ran and its own measurement could not answer, so the result is unverified.

    Distinct from ``view_fit.not_framed``, which states a *measured* overflow. Nothing was measured
    here — every corner implausible, no readable bbox, an unreadable size — so claiming the model
    "does not fit" would name a cause the verdict does not support. The block still rides the
    envelope: ``stale_reason`` is the only place the failure is named.
    """
    reason = (
        "the fit ran but could not verify its own result; "
        f"read the framing block for why: {verdict.get('stale_reason')}"
    )
    envelope = _refused_envelope("view_fit.unverified", reason)
    return {**envelope, "framing": verdict}


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
