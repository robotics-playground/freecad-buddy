"""Judge-drawing contract: the wire result of ``techdraw_for_judge`` and the rasterizer seam.

``techdraw_for_judge`` composes one SVG sheet from the view-level SVG the headless ``TechDraw``
App module returns (decision 016 — page export lives in ``TechDrawGui`` and is unreachable
without the GUI), then rasterizes that sheet for the visual judge. The raster step needs Qt,
which ``usecases/`` may not import, so it arrives as a host-injected ``SvgRasterPort`` exactly
as the 3D render arrives as a ``RenderPort``.

Stdlib only; no FreeCAD, Gui, or Qt import.
"""

from __future__ import annotations

from typing import Literal, Protocol, TypedDict, runtime_checkable

# The three orthographic views the G3 standard visual set names (verification-design.md §7a).
# Fixed here rather than in the use case because the judge's finding vocabulary
# (``benchmarks/g3/judge.py`` ``VIEWS``) already names exactly these, and a fourth view would
# produce findings the judge schema rejects.
SheetView = Literal["front", "top", "right"]


class DimensionCallout(TypedDict, total=False):
    """One dimension annotation placed on the sheet, and where its number came from.

    ``parameter`` is the driving-parameter name the value was read from, never a measurement of
    the produced geometry. That provenance is the whole reason the callout exists: a number
    re-derived from the view would agree with the part however wrong the part was, so the judge's
    dimension cross-check could never catch a spec-to-assertion mistranslation.

    ``text`` is the string actually drawn, read back from the ``TechDraw`` dimension object on
    the TempDoc rather than re-formatted here, so the document object and the drawn glyphs cannot
    disagree.
    """

    view: SheetView  # required
    parameter: str  # required
    value: float  # required
    text: str  # required
    # ``distance`` is the only member today, and deliberately so. The other headless dimension
    # helper, ``TechDraw.makeExtentDim``, measures the *view's* own projected extent, so a callout
    # built from one would be read off the produced geometry — the one thing a judge callout must
    # never be. A second member is added when a second parameter-sourced kind exists, not to mirror
    # the FreeCAD API surface.
    kind: Literal["distance"]  # required


class DrawingSheet(TypedDict, total=False):
    """The composed judge sheet: where the files are, how wide, and what it claims.

    ``svg_path`` and ``png_path`` both live under the session workdir so the session-start sweep
    owns them. ``png_path`` is ``None`` only when ``available`` is false — a sheet that could not
    be rasterized is reported unavailable, never as a smaller image, because the judge's
    ``page_width_px`` floor exists to keep callouts legible and a silent downgrade would fail
    correct parts for an unreported reason.

    ``views`` names the projections composed onto the sheet, so a caller can tell a three-view
    sheet from one a failed projection left short.
    """

    schema: Literal["fcb.drawing-sheet/1"]  # required
    available: bool  # required
    reason: str | None  # required
    svg_path: str | None  # required
    png_path: str | None  # required
    page_width_px: int  # required
    page_height_px: int  # required
    views: list[SheetView]  # required
    callouts: list[DimensionCallout]  # required


@runtime_checkable
class SvgRasterPort(Protocol):
    """The Qt-side capability the host injects; the use case depends only on this shape.

    Two methods, both Qt concerns the ``usecases/`` ring may not reach itself: turning the composed
    sheet into a raster, and letting a pending Qt-driven computation make progress.
    """

    def available(self) -> tuple[bool, str | None]:
        """Return ``(is_available, reason)``; ``reason`` is set only when unavailable."""

    def settle(self) -> None:
        """Let any pending Qt work advance; a no-op where no event loop is running.

        ``DrawViewPart`` builds its projected geometry through a hidden-line-removal pass that is
        **asynchronous whenever a Qt application object exists** — which is every GUI process, and
        any headless process that has brought Qt up. In that state ``viewPartAsSvg`` returns an
        empty string until the pass finishes, and **no property reports that it has not**:
        ``State`` reads ``['Up-to-date']`` throughout (measured on FreeCAD 1.1.1, and the same
        silent-empty outcome decision 016 records as R3-01). An empty SVG raises nothing, so a
        caller that did not wait would hand the judge a blank sheet and fail a correct part for a
        reason no assertion reports.

        The caller therefore polls ``viewPartAsSvg`` and calls this between attempts. It must not
        block on a fixed sleep: under ``FreeCADCmd`` with no event loop the pass is synchronous and
        the first read already succeeds, so a sleep would be pure latency on the leg that does not
        need it.
        """

    def rasterize(self, svg: str, out_path: str, width: int, height: int) -> None:
        """Render ``svg`` to ``out_path`` as a PNG exactly ``width`` x ``height`` pixels.

        The size is the caller's, not a scale factor: the use case has already sized the sheet to
        clear the judge's legibility floor, and a port that silently fitted the image to the SVG's
        own millimetre size would undo that. Raises on any failure — a port must never return
        having written nothing, because the caller reports a written sheet.
        """


__all__ = ["DimensionCallout", "DrawingSheet", "SheetView", "SvgRasterPort"]
