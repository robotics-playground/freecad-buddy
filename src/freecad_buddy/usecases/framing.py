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
from dataclasses import dataclass

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

# The readable three of AD-32's four-tuple: ``(geometry, camera, viewport_size)``. A component
# the process could not read cheaply is ``None`` here and named in the served verdict's reason.
# The fourth, the active view, is not a value — see ``_CacheEntry.view``.
_CacheKey = tuple[str | None, str | None, str | None]


@dataclass(frozen=True)
class _CacheEntry:
    """One measured verdict, the key it was measured under, and the view it was measured in.

    ``view`` is AD-32's fourth key component, held as the object rather than reduced to a value.
    ``View3DInventor`` exposes no name getter, and an address-derived id is unsound: a dead
    view's address is reused, so a *different* view would compare equal to the one measured. The
    reference both keeps the identity honest and makes the comparison an ``is``.
    """

    key: _CacheKey
    verdict: FramingVerdict
    view: object


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
    ``fits: True``. The test is exact and carries no tolerance of its own (AD-30): one pixel
    outside is outside. The near-miss tolerance lives on the *warning sentence*, not on this
    verdict — see ``contracts.envelope.NEAR_MISS_TOLERANCE``.

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
    registry: DocumentRegistry,
    viewport_port: ViewportPort | None,
    doc: str | None = None,
    geometry: str | None = None,
) -> FramingVerdict | None:
    """Measure whether ``doc``'s visible model fits its live viewport.

    Returns ``None`` when the document has no viewport at all (no port injected, or the port
    reports unavailable). That is AD-32 state 1 — the block is omitted entirely, never reported
    as ``unavailable`` — which keeps ``checked: "unavailable"`` meaning exactly one thing: a
    viewport existed and the projection could not be completed.

    Every other failure returns ``fits: None`` with ``checked: "unavailable"`` and a named
    ``stale_reason``. ``fits`` is never a guess.

    :param geometry: the caller's cheap geometry digest — the fingerprint a mutation already
        computed. ``None`` on the pure-query path, where no digest is available cheaply, and a
        cache hit is then reported ``checked: "cached"`` naming the geometry component as
        unverified rather than claiming a freshness the bridge cannot prove. ``fingerprint()``
        is never called here: it serializes every shape and would cost more than the projection
        this cache exists to avoid.
    """
    if viewport_port is None:
        return None

    def read(handle: str, document: object) -> FramingVerdict | None:
        available, _reason = viewport_port.available(document)
        if not available:
            return None
        view = viewport_port.view(document)
        if view is None:
            return None
        return _cached_verdict(handle, document, view, geometry)

    return registry.with_document(doc, read)


def _cached_verdict(
    handle: str, document: object, view: object, geometry: str | None
) -> FramingVerdict:
    """``measure_framing``, served from the cache when nothing in the four-tuple key moved.

    The projection is a GUI round trip per tool result, which the ≤15 s tool budget cannot
    afford on every call. The key is AD-32's four-tuple — geometry digest, camera string,
    viewport size, active view — and a component the process cannot read cheaply is never
    silently treated as unchanged: it is named in ``stale_reason`` on the served verdict.

    A *geometry-only* trigger is the specific mistake this shape avoids. A window resize or a
    splitter drag changes ``getSize()`` while the camera node is untouched, so a geometry-only
    cache would keep serving ``fits: true`` for a viewport that now clips the model.
    """
    key, unread = _cache_key(view, geometry)
    entry = _CACHE.get(handle)
    if entry is not None and entry.view is view and entry.key == key:
        return _as_cached(entry.verdict, unread)
    verdict = measure_framing(document, view)
    _CACHE.put(handle, key, verdict, view)
    return verdict


def _cache_key(view: object, geometry: str | None) -> tuple[_CacheKey, list[str]]:
    """``view``'s readable key components, plus the names of the ones that could not be read.

    A component that raised, or that the caller had no cheap value for, enters the key as
    ``None`` **and** is named in the returned list. Both halves matter: ``None`` keeps two
    unreadable reads comparing equal so the cache still serves, and the name is what stops that
    served verdict being reported as fresh.

    The fourth component, the active view, is compared by identity against
    ``_CacheEntry.view`` rather than reduced to a value here.

    An unreadable ``getSize`` is not in the unread list because it cannot reach a served verdict:
    the projection needs the size too, so a size the process cannot read makes the whole verdict
    ``unavailable``, which ``_as_cached`` never re-stamps.
    """
    unread: list[str] = []
    if geometry is None:
        unread.append("geometry")
    camera = _read_component(view, "getCamera")
    if camera is None:
        unread.append("camera")
    return (geometry, camera, _read_component(view, "getSize")), unread


def _read_component(view: object, method: str) -> str | None:
    """One cache-key component read off the view, or ``None`` when it cannot be read cheaply.

    Every component is a scalar GUI read that costs far less than the 8-corner projection. A
    read that raises is not an error here — the caller names it unread and serves a cached
    verdict, which is AD-32's escape clause. The value is reduced to its ``repr`` so the key
    stays hashable whatever shape the view hands back.
    """
    try:
        value = getattr(view, method)()
    except Exception:  # noqa: BLE001 - an unreadable component is named, never fatal
        return None
    return repr(value)


def _as_cached(verdict: FramingVerdict, unread: list[str]) -> FramingVerdict:
    """``verdict`` re-stamped ``checked: "cached"``, naming any component that went unverified.

    An ``unavailable`` verdict keeps its own ``checked`` and reason: it never measured anything,
    so calling it "cached" would imply a stored measurement that does not exist.
    """
    if verdict.get("checked") == "unavailable":
        return verdict
    reason = (
        f"served from cache; unverified key component(s): {', '.join(unread)}" if unread else None
    )
    return {**verdict, "checked": "cached", "stale_reason": reason}


class _FramingCache:
    """The last verdict per document handle, with the key and the view it was measured under.

    One entry per handle, overwritten on every recompute — a verdict for a key that moved has no
    further use, so nothing is evicted by age or size, and at most one view reference is held per
    open document. The tool-call boundary processes one call at a time, so this needs no lock
    (the shape ``adapters/mcp_server.py:_SuspectDocuments`` already ships).
    """

    def __init__(self) -> None:
        self._entries: dict[str, _CacheEntry] = {}

    def get(self, handle: str) -> _CacheEntry | None:
        return self._entries.get(handle)

    def put(self, handle: str, key: _CacheKey, verdict: FramingVerdict, view: object) -> None:
        self._entries[handle] = _CacheEntry(key=key, verdict=verdict, view=view)

    def clear(self) -> None:
        self._entries.clear()


_CACHE = _FramingCache()


def reset_cache() -> None:
    """Drop every cached verdict. The cache is process-global, so a test must start from empty."""
    _CACHE.clear()


def measure_framing(document: object, view: object) -> FramingVerdict:
    """Project the union bbox through ``view`` and grade containment into a ``FramingVerdict``.

    Public because the viewport fit frames the model with this same measurement (AD-30): a second
    analytic estimate of the on-screen extent is how a fit ends up reporting success beside a
    verdict that contradicts it. The fit calls this before and after its zoom; the framing read
    calls it through the cache.
    """
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


__all__ = [
    "containment",
    "corners",
    "hull_ratio",
    "measure_framing",
    "read_framing",
    "reset_cache",
    "union_bbox",
]
