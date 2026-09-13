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
``ViewportPort`` and is only duck-typed (``getCamera``, ``fitAll``, ``getPointOnViewport``,
``getSize``).
"""

from __future__ import annotations

import math

from freecad_buddy.contracts import FramingVerdict, ResultEnvelope, ViewportPort
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
from freecad_buddy.usecases.framing import measure_framing

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
        _require_same_document(document, view)

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

    1. ``viewIsometric`` then a plain ``fitAll(1.0)``, so the camera is in a *known* state, and
       ``measure_framing`` through it reports how much of the binding axis the model then fills.
    2. ``fitAll(factor)`` with ``factor = ratio / _FILL_FRACTION``. ``fitAll(f)`` scales the scene
       box by ``f`` before framing its space diagonal (``View3DInventorViewer.cpp:4467-4488``), so
       the on-screen extent scales as ``1/f`` relative to ``fitAll(1.0)`` and the measured ratio
       lands exactly on the requested fill.
    3. ``measure_framing`` again, through the camera pass 2 just wrote. Its verdict is the one the
       caller gets, and it is what makes ``fitted: true`` a measurement rather than a report that
       the call ran.

    Passes 1 and 3 measure with the *same* routine the framing verdict uses. An analytic estimate
    of the same quantity was the defect: it underestimated the projected extent by 1.155x on a cube
    and overestimated it by 0.856x on a 40x40x800 bar, so compact parts were zoomed past the edge
    while the tool reported success.

    The measurement is only sound because animation is suspended: with animation on, both camera
    writes land after this call returns and pass 3 would re-read the pre-fit camera. That is why
    a toggle that exists and refuses is a refusal rather than a degraded fit.

    The camera is oriented isometrically first — the standard TOP/FRONT/RIGHT corner view, which
    shows all three dimensions at once. A fit exists to show the human the work, and a top view
    down a tall bar shows only its end face however well it is zoomed.
    """
    with _animation_suspended(view):
        _view_isometric(view)
        _fit_all_with_factor(view, 1.0)
        factor = _correction_factor(_measure(document, view))
        if factor is not None:
            _fit_all_with_factor(view, factor)
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


def _correction_factor(verdict: FramingVerdict) -> float | None:
    """The ``fitAll`` factor that moves the measured ratio onto ``_FILL_FRACTION``.

    ``None`` only when the pass-1 measurement produced no ratio at all — every corner implausible,
    no readable bbox, an unreadable ``getSize``. The plain ``fitAll(1.0)`` already ran, so a model
    the camera was pointed away from is still recovered; only the margin is FreeCAD's own rather
    than the requested one.

    A measured ``0.0`` is a measurement, not a failure to measure: it says the model projects to a
    sub-pixel dot, which is the case most in need of correction. Treating it as unusable left the
    dot on screen and reported ``fitted: true``. ``_MIN_FIT_FACTOR`` floors the resulting zoom, so
    the factor stays one ``viewAll`` will act on.
    """
    ratio = verdict.get("ratio")
    if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) or not math.isfinite(ratio):
        return None
    return max(ratio / _FILL_FRACTION, _MIN_FIT_FACTOR)


class _AnimationRefused(Exception):
    """The view has an animation toggle that refused, so the fit cannot verify its own camera."""


class _Unsuspended:
    """"Nothing was suspended, so there is nothing to restore" — distinct from any bool setting.

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
