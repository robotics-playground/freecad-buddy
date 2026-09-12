"""Framing read: does the targeted document's model fit the live viewport (Gui-free).

``read_framing`` projects the 8 corners of the union bounding box of the document's visible
shape-bearing objects through the live view's ``getPointOnViewport`` and tests containment
against ``getSize()``. ``fits`` is false **iff any** corner falls outside the viewport
rectangle — exact, never heuristic (AD-30), so two implementations cannot disagree about the
same scene.

The measured object set comes from ``screenshot.is_default_renderable``, the render's own
predicate. Re-deriving a second "visible shape-bearing" filter here is exactly how the render
and the framing warning end up describing different scenes.

Contains no ``FreeCADGui``/Qt/pivy import. The view arrives as an opaque object from the
host-injected ``ViewportPort`` and is only duck-typed (``getPointOnViewport``, ``getSize``).
"""

from __future__ import annotations

import math

from freecad_buddy.contracts import FramingVerdict, ViewportPort
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.screenshot import is_default_renderable

# ``getPointOnViewport`` casts its result through an unchecked ``short()``
# (``View3DInventorViewer.cpp:3821-3822``), so a corner far off screen wraps sign and a wrapped
# value would read as inside. Any coordinate whose magnitude exceeds this multiple of the
# corresponding viewport dimension is treated as outside and the coordinate discarded. The
# multiple is a stated constant, not a per-implementer judgement (AD-30/AD-32).
_IMPLAUSIBLE_FACTOR = 4

# ``(xmin, ymin, zmin, xmax, ymax, zmax)`` — raw floats, never a FreeCAD ``BoundBox``.
Bounds = tuple[float, float, float, float, float, float]


def union_bbox(objects: list) -> Bounds | None:
    """Fold the objects' shape bounding boxes into one ``(xmin, ymin, zmin, xmax, ymax, zmax)``.

    Returns ``None`` when no object contributes a readable box. Folds raw floats rather than
    holding a FreeCAD ``BoundBox``, so the union step is stdlib-pure and unit-testable with no
    FreeCAD present. A shape whose box cannot be read or is non-finite is skipped rather than
    poisoning the union with a NaN that would make every containment test false.
    """
    boxes = [box for box in (_object_bounds(obj) for obj in objects) if box is not None]
    if not boxes:
        return None
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        min(box[2] for box in boxes),
        max(box[3] for box in boxes),
        max(box[4] for box in boxes),
        max(box[5] for box in boxes),
    )


def _object_bounds(obj: object) -> Bounds | None:
    """``obj``'s shape bounding box as six finite floats, or ``None`` when it has none."""
    box = getattr(getattr(obj, "Shape", None), "BoundBox", None)
    if box is None:
        return None
    try:
        values = (
            float(box.XMin),
            float(box.YMin),
            float(box.ZMin),
            float(box.XMax),
            float(box.YMax),
            float(box.ZMax),
        )
    except (AttributeError, TypeError, ValueError):
        return None
    return values if all(math.isfinite(value) for value in values) else None


def corners(box: Bounds) -> list[tuple[float, float, float]]:
    """The 8 corners of ``(xmin, ymin, zmin, xmax, ymax, zmax)`` in world coordinates."""
    xmin, ymin, zmin, xmax, ymax, zmax = box
    return [(x, y, z) for x in (xmin, xmax) for y in (ymin, ymax) for z in (zmin, zmax)]


def containment(
    projected: list[tuple[float, float]], size: tuple[int, int]
) -> tuple[bool, list[tuple[float, float]], int]:
    """Whether every projected corner lies inside ``size``, plus the corners worth measuring.

    Containment is **inclusive**: a corner at exactly ``x == width`` is the last visible pixel
    column, not the first invisible one, so a model framed perfectly to the edge reports
    ``fits: True``.

    A coordinate whose magnitude exceeds ``_IMPLAUSIBLE_FACTOR`` times its viewport dimension
    wrapped through the ``short()`` cast and carries no usable value: its corner is outside and
    is left out of the returned list, so no ratio is computed from it.

    :returns: ``(fits, kept, discarded)`` where ``kept`` holds only the corners with both
        coordinates plausible and ``discarded`` counts the rest. ``fits`` is ``False`` when any
        corner was discarded or fell outside.
    """
    width, height = size
    fits = True
    kept: list[tuple[float, float]] = []
    discarded = 0
    for x, y in projected:
        if abs(x) > _IMPLAUSIBLE_FACTOR * width or abs(y) > _IMPLAUSIBLE_FACTOR * height:
            fits = False
            discarded += 1
            continue
        kept.append((x, y))
        if not (0 <= x <= width and 0 <= y <= height):
            fits = False
    return fits, kept, discarded


def hull_ratio(
    kept: list[tuple[float, float]], discarded: int, size: tuple[int, int]
) -> float | None:
    """The larger of the two ``extent / viewport_extent`` quotients over the corners' 2D hull.

    ``1.0`` exactly fills the viewport, ``< 1.0`` leaves margin, ``> 1.0`` overflows.

    ``None`` whenever ``discarded`` is non-zero: a discarded coordinate has no measurable
    fraction, and fabricating a ratio from the survivors would report a wildly wrong camera as a
    hair's-breadth miss.
    """
    if discarded or not kept:
        return None
    width, height = size
    xs = [x for x, _ in kept]
    ys = [y for _, y in kept]
    return max((max(xs) - min(xs)) / width, (max(ys) - min(ys)) / height)


def read_framing(
    registry: DocumentRegistry, viewport_port: ViewportPort | None, doc: str | None = None
) -> FramingVerdict | None:
    """Measure whether ``doc``'s visible model fits its live viewport.

    Returns ``None`` when the document has no viewport at all (no port injected, or the port
    reports unavailable). That is AD-32 state 1 — the block is omitted entirely, never reported
    as ``unavailable`` — which keeps ``checked: "unavailable"`` meaning exactly one thing: a
    viewport existed and the projection could not be completed.

    Every other failure returns ``fits: None`` with ``checked: "unavailable"`` and a named
    ``stale_reason``. ``fits`` is never a guess.
    """
    if viewport_port is None:
        return None

    def read(_handle: str, document: object) -> FramingVerdict | None:
        available, _reason = viewport_port.available(document)
        if not available:
            return None
        view = viewport_port.view(document)
        if view is None:
            return None
        return _verdict(document, view)

    return registry.with_document(doc, read)


def _verdict(document: object, view: object) -> FramingVerdict:
    """Project the union bbox through ``view`` and grade containment into a ``FramingVerdict``."""
    box = union_bbox([obj for obj in document.Objects if is_default_renderable(obj)])
    if box is None:
        return _unavailable("no visible shape-bearing objects to measure")

    try:
        size = _viewport_size(view)
    except Exception as exc:  # noqa: BLE001 - an unreadable viewport is a stated reason
        return _unavailable(f"viewport size unreadable: {type(exc).__name__}")
    if size is None:
        return _unavailable("viewport reported a zero dimension: nothing to measure against")

    try:
        projected = [_project(view, corner) for corner in corners(box)]
    except Exception as exc:  # noqa: BLE001 - a raising projection is a stated reason
        return _unavailable(f"projection failed: {type(exc).__name__}")

    fits, kept, discarded = containment(projected, size)
    if not kept:
        return _unavailable("every projected corner was an implausible magnitude")
    return {
        "fits": fits,
        "ratio": hull_ratio(kept, discarded, size),
        "checked": "computed",
        "stale_reason": None,
    }


def _viewport_size(view: object) -> tuple[int, int] | None:
    """``view.getSize()`` as a positive ``(width, height)``, or ``None`` when unusable.

    No ``devicePixelRatio`` correction: ``getSize()`` and ``getPointOnViewport`` share one
    render-manager pixel space, and the DPI divide lives only in ``toQPoint``, which this path
    never calls. A zero dimension is rejected here so the ratio never divides by zero.
    """
    width, height = view.getSize()
    width, height = int(width), int(height)
    return (width, height) if width > 0 and height > 0 else None


def _project(view: object, corner: tuple[float, float, float]) -> tuple[float, float]:
    """Project one world-space corner to viewport coordinates through the live view.

    Passed as three floats rather than a ``FreeCAD.Vector`` so this module needs no FreeCAD
    import and the view stays duck-typed. The returned coordinates are deliberately unclamped —
    a value outside ``[0, w] x [0, h]`` is what makes the containment test possible.
    """
    x, y = view.getPointOnViewport(corner[0], corner[1], corner[2])
    return (float(x), float(y))


def _unavailable(reason: str) -> FramingVerdict:
    """A verdict that names why the projection could not answer; ``fits`` is never a guess."""
    return {"fits": None, "ratio": None, "checked": "unavailable", "stale_reason": reason}


__all__ = ["containment", "corners", "hull_ratio", "read_framing", "union_bbox"]
