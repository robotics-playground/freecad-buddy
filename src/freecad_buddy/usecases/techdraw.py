"""``techdraw_for_judge``: the dimensioned front/top/right sheet the visual judge reads.

The sheet is **composed, not exported**. Decision 016 measured that both page exporters live in
``TechDrawGui`` (``AppTechDrawGuiPy.cpp:56,59``), which raises ``Cannot load Gui module in console
application`` under ``FreeCADCmd``; the headless ``TechDraw`` App module registers no
``exportPage*`` name at all. Epic 5's headless service must re-execute the visual verdict, so a
GUI-only drawing path would leave that service unable to reproduce its own result. This module
therefore places the view-level SVG the headless module *does* return onto one canvas itself.

Everything is built on a TempDoc copy of the part's shape under the reserved ``FCB_TMP_`` prefix
and discarded on every path, so the part document's ``fingerprint()`` is byte-identical across the
call and no TechDraw object is ever written into it.

Stdlib + FreeCAD App API only. Rasterization needs Qt, which this ring may not import, so it
arrives as a host-injected ``SvgRasterPort``.


Sheet layout convention
-----------------------

FreeCAD lays out no sheet for us, so the frame, scale and placement below are this story's
contract rather than FreeCAD's.

* **Coordinate frame.** The canvas is one SVG user unit per millimetre, y-down. Every fragment
  ``TechDraw.viewPartAsSvg`` returns is in view-local millimetres, y-up, centred on the view's own
  origin, so each is wrapped in ``<g transform="translate(cx, cy) scale(s, -s)">`` — the negative
  y factor converts y-up model space to y-down canvas space, ``s`` is the one sheet-wide scale
  below, and the translate puts the view's centre at its assigned cell centre.
* **Placement.** First-angle-style three-cell row, left to right: front, top, right. A row rather
  than the draughting convention's L-shape because the judge reads each view independently and a
  row keeps every cell the same size and the sheet's aspect ratio predictable.
* **Scale.** One scale for the whole sheet, so proportions are comparable *between* views — a
  per-view fit would make a small part and a large one look alike, which is exactly the
  "grossly wrong proportions" fault the judge's suite plants. The scale is the largest that fits
  every view inside its cell with ``_CELL_MARGIN_MM`` of margin, and it is **stated on the sheet**
  as a ratio: a judge checking proportions against a declared size needs a declared value, not
  only relative sizes.
* **Callouts.** Composed here, not by FreeCAD. The ``TechDraw`` dimension objects on the TempDoc
  carry the same strings (read back through ``getText()``), but their *rendering* lives in
  ``TechDrawGui``'s QGraphics layer and is unreachable headless (DW-118), so the glyphs the judge
  reads are drawn by this module.

  An axis-bearing dimension becomes a **bar spanning the extent it measures**, offset clear of the
  silhouette, on a view whose picture plane contains that axis. Both halves are load-bearing.
  *Placement* is a claim: by drawing convention a dimension attached to a view describes that
  view, and a vision judge reads drawings by that convention, so a thickness callout never sits on
  the top view, which looks straight down the thickness axis. *Span* is the association: the bar's
  length is the measurement, which ties a number to the edge it measures without the witness lines
  and arrowheads the Gui-only machinery would provide.

  A callout naming no axis — a diameter, a pitch, an inset — has no extent to span and stays a
  plain caption in the band below its view. Drawing a bar for it would assert a span the parameter
  never declared.
"""

from __future__ import annotations

import os
import re
import secrets
import tempfile
from dataclasses import dataclass

from freecad_buddy.contracts import (
    DimensionCallout,
    DrawingSheet,
    ImageRef,
    ResultEnvelope,
    SvgRasterPort,
    massprops_equal,
)
from freecad_buddy.usecases import shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError, temp_dir
from freecad_buddy.usecases.fingerprint import fingerprint

_TEMPDOC_PREFIX = "FCB_TMP_td_"

# The three orthographic directions the G3 standard visual set names, each with the explicit
# XDirection that pins the view's in-plane rotation. XDirection is not optional: a DrawViewPart
# whose Direction is parallel to FreeCAD's default X logs "failed to create projection CS" and
# falls back to a coordinate system this module did not choose, so the right view would be rotated
# by an amount no caller declared. Measured on FreeCAD 1.1.1.
_VIEW_DIRECTIONS: tuple[tuple[str, tuple[float, float, float], tuple[float, float, float]], ...] = (
    ("front", (0.0, -1.0, 0.0), (1.0, 0.0, 0.0)),
    ("top", (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    ("right", (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
)

# Sheet geometry in millimetres. A3 landscape proportions: three equal cells in a row, with the
# band below each cell reserved for that view's callouts.
_SHEET_WIDTH_MM = 420.0
_SHEET_HEIGHT_MM = 297.0
_CELL_MARGIN_MM = 20.0
_CALLOUT_BAND_MM = 60.0
_CALLOUT_LINE_MM = 9.0
_LABEL_HEIGHT_MM = 12.0

# Dimension-bar geometry in millimetres: the clearance from the silhouette to the first bar, the
# spacing between stacked bars on the same side, and the half-length of an end tick. The gap must
# exceed the tick so a bar's ticks never touch the drawn part.
_DIM_BAR_GAP_MM = 10.0
_DIM_BAR_PITCH_MM = 11.0
_DIM_TICK_MM = 2.0

# The judge's legibility floor (AD-21, ``benchmarks/g3/judge.py`` MIN_PAGE_WIDTH_PX). Below it the
# dimension cross-check degrades to noise. This is deliberately NOT the user-facing render cap in
# ``usecases/screenshot.py`` (_MAX_DIM = 1920): judge images travel straight to the judge API
# rather than through client context, so they neither use nor widen that budget.
_MIN_PAGE_WIDTH_PX = 2048

# Stroke width in millimetres for the composed line art. ``viewPartAsSvg`` stamps 0.7 on its own
# fragments; the frame and callout rules match it so the sheet reads as one drawing.
_STROKE_MM = 0.7

# A view whose projected extent is below this in millimetres is degenerate — an edge seen end-on,
# or a projection that drew nothing — and cannot set the sheet scale without collapsing it.
_MIN_EXTENT_MM = 1e-6

# How many times a pending hidden-line-removal pass is nudged before the view is declared blank.
# Two attempts sufficed for an 80x60x6 plate on FreeCAD 1.1.1 with a QApplication up, and the port
# yields ~10 ms per attempt, so this is a ~30 s per-view ceiling against a measured ~20 ms need.
# The margin is deliberately large in one direction only: HLR cost scales with the part's edge
# count and a real G3 part is far more complex than the measured plate, an over-generous ceiling
# only costs time on a part that was going to fail anyway, and an under-generous one produces a
# blank sheet that fails a correct part for a reason no assertion reports.
_MAX_SETTLE_ATTEMPTS = 3000

# The SVG elements ``viewPartAsSvg`` draws projected edges with. Both are needed: TechDraw emits a
# full circle as ``<circle>`` rather than as a path, so a view whose outline is entirely circular
# carries no ``<path>`` at all. Measured on FreeCAD 1.1.1 across box, cylinder, washer, sphere,
# cone and torus in three projections each — every end-on circular view (cylinder/top, washer/top,
# sphere/top, cone/top) returns only ``<circle>``, torus/top returns both, and every other view
# returns only ``<path>``. Polling for ``<path>`` alone therefore rejected finished, correct
# geometry as an unfinished HLR pass, and no turned part could be drawn end-on.
_GEOMETRY_TAGS = ("<path", "<circle")

# The property groups on a VarSet/Spreadsheet façade that hold driving parameters, and the base
# properties every FreeCAD object carries. Parameters are identified by exclusion of the latter so
# a façade that groups its parameters differently is still read.
_BASE_PROPERTIES = frozenset({"ExpressionEngine", "Label", "Label2", "Visibility"})

# Which model axis each view's picture plane contains, from _VIEW_DIRECTIONS. A view displays a
# dimension only when that dimension's axis is one of the two in its plane: looking down an axis
# collapses it, so a caption naming it under that view claims something the picture cannot show.
_VIEW_PLANE_AXES: dict[str, frozenset[str]] = {
    "front": frozenset({"x", "z"}),  # looking along -Y
    "top": frozenset({"x", "y"}),  # looking along +Z
    "right": frozenset({"y", "z"}),  # looking along +X
}

# Each view's two in-plane axes as ``(horizontal, vertical)`` on the drawn sheet, so a dimension
# bar spans the right screen direction. Confirmed against the projections FreeCAD
# actually returned for an 80(x) x 60(y) x 6(z) plate on FreeCAD 1.1.1: front measured 80 wide by
# 6 tall (x horizontal, z vertical), top 80 by 60 (x, y), right 60 by 6 (y, z). Derived from the
# same direction-and-XDirection pairs in _VIEW_DIRECTIONS, so the two must change together.
_VIEW_SCREEN_AXES: dict[str, tuple[str, str]] = {
    "front": ("x", "z"),
    "top": ("x", "y"),
    "right": ("y", "z"),
}

# Axis-bearing words in a driving-parameter name, mapped to the model axis they name. Derived from
# the name rather than from the produced geometry, which keeps the whole callout path
# intent-sourced: measuring the shape to decide placement would reintroduce exactly the
# geometry-agreement the parameter-sourcing rule exists to prevent.
#
# The vocabulary is the one the G3 spec set actually uses (surveyed across benchmarks/g3/dev/).
# Words in that set that name no axis — diameter, radius, pitch, spacing, bore — are deliberately
# absent: a hole diameter is in-plane in every view that shows the hole, so forcing it onto an
# axis would invent a claim the drawing does not make.
_AXIS_WORDS: dict[str, str] = {
    "length": "x",
    "width": "y",
    "depth": "y",
    "thickness": "z",
    "height": "z",
}

# The object a part exposes its driving parameters on. Story 4.6 owns the façade that writes it;
# this module only reads. The name is the contract between the two stories.
_PARAMETER_OBJECT_NAMES = ("Parameters",)


class TechDrawUnavailable(RuntimeError):
    """The headless TechDraw module or the SVG rasterizer is not usable on this build."""


@dataclass(frozen=True)
class _PlacedView:
    """One projection built on the TempDoc, ready for the compositor.

    ``fragment`` is the bare ``<g>...</g>`` string ``viewPartAsSvg`` returned, in view-local
    millimetres and y-up. ``width``/``height`` are that fragment's own extent in millimetres, read
    back out of its path data — the compositor needs it to pick one scale for the whole sheet, and
    the ``DrawViewPart`` does not report a projected extent of its own.
    """

    name: str
    fragment: str
    width: float
    height: float

    @property
    def is_measurable(self) -> bool:
        """Whether this view's extent can take part in choosing the sheet scale.

        A view seen exactly edge-on has no height. That is a valid projection of a flat part, not
        a failure, but it cannot constrain a scale without driving it to zero.
        """
        return self.width > _MIN_EXTENT_MM and self.height > _MIN_EXTENT_MM


def techdraw_for_judge(
    registry: DocumentRegistry,
    raster_port: SvgRasterPort,
    doc: str | None = None,
    page_width_px: int | None = None,
) -> ResultEnvelope:
    """Compose the judge's dimensioned three-view sheet for ``doc`` and rasterize it.

    Returns an ``OK`` envelope whose structured content is a ``DrawingSheet``. A build with no
    TechDraw module or no rasterizer still returns ``OK`` with ``available: false`` and a reason —
    unavailability is a reported capability, not a call error — and the caller's fail-closed rule
    (``visual.unavailable``, the part is not done) applies to that flag.

    The part document is never written: the drawing is built on a TempDoc holding a copy of the
    part's shape, and ``fingerprint(doc)`` is asserted identical before and after.

    :param page_width_px: the raster width; floored at 2048 px (AD-21). A caller asking for less
        gets the floor rather than a smaller image, because a callout the judge cannot read fails
        a correct part for a reason no assertion reports.
    :raises ValidationError: the handle is unknown, the document carries no shape to draw, or it
        exposes no driving parameters to source dimensions from.
    """
    width_px = _page_width(page_width_px)

    def build(_handle: str, document: object) -> ResultEnvelope:
        available, reason = _capability(raster_port)
        if not available:
            return _ok_envelope(_unavailable_sheet(reason), None)

        subject = _subject_object(document)
        parameters = _driving_parameters(document)
        if not parameters:
            raise ValidationError(
                f"{document.Name} exposes no driving parameters, so dimensions cannot be "
                "parameter-sourced. Reading them off the produced geometry is banned: the drawing "
                "would then agree with the part however wrong the part was."
            )

        before = fingerprint(document)
        sheet = _compose_and_rasterize(subject.Shape, parameters, raster_port, width_px)
        _assert_unchanged(document, before)
        image: ImageRef = {
            "kind": "resource_link",
            "uri": sheet["png_path"],
            "mime_type": "image/png",
            "audience": ["assistant"],
        }
        return _ok_envelope(sheet, image)

    return registry.with_document(doc, build)


# ------------------------------------------------------------------------------------------
# Capability and inputs
# ------------------------------------------------------------------------------------------


def _capability(raster_port: SvgRasterPort) -> tuple[bool, str | None]:
    """Whether both halves of the path exist: the headless module and a rasterizer."""
    if not shim.techdraw_available():
        return False, (
            "the headless TechDraw App module is unavailable or has lost one of the entry points "
            "decision 016 measured (projectToSVG, viewPartAsSvg, makeExtentDim, makeDistanceDim)"
        )
    return raster_port.available()


def _page_width(requested: int | None) -> int:
    """Floor the requested raster width at the judge's legibility minimum.

    :raises ValidationError: ``requested`` is not a positive integer.
    """
    if requested is None:
        return _MIN_PAGE_WIDTH_PX
    if not isinstance(requested, int) or isinstance(requested, bool):
        raise ValidationError(f"page_width_px must be an integer: {requested!r}")
    if requested <= 0:
        raise ValidationError(f"page_width_px must be positive: {requested!r}")
    return max(requested, _MIN_PAGE_WIDTH_PX)


def _subject_object(document: object) -> object:
    """Return the one object whose shape the sheet draws.

    Picks the last shape-bearing, non-datum object, matching the grader's own choice
    (``benchmarks/harness/assertions.py`` ``_graded_shape``) so the judge and the geometry leg
    describe the same solid. Datum features are excluded for the reason ``fingerprint`` excludes
    them: an ``App::Plane`` is infinite, and projecting one produces no drawing.

    :raises ValidationError: the document carries no shape to draw.
    """
    candidates = [obj for obj in document.Objects if _is_drawable(obj)]
    if not candidates:
        raise ValidationError(f"{document.Name} carries no shape-bearing object to draw")
    return candidates[-1]


_DATUM_TYPE_PREFIXES = ("App::Origin", "App::Line", "App::Plane", "App::Point")


def _is_drawable(obj: object) -> bool:
    """Whether ``obj`` bears a non-null shape and is not construction geometry."""
    if str(getattr(obj, "TypeId", "")).startswith(_DATUM_TYPE_PREFIXES):
        return False
    shape = getattr(obj, "Shape", None)
    is_null = getattr(shape, "isNull", None)
    return shape is not None and not (is_null is not None and is_null())


def _driving_parameters(document: object) -> list[tuple[str, float]]:
    """Read the part's named driving parameters, in the order the build reports them.

    FreeCAD returns ``PropertiesList`` sorted by name rather than by declaration, so the order is
    alphabetical in practice. It is not re-sorted here: the order only decides which view a callout
    lands under, and every callout names its own parameter, so the judge reads the pairing from the
    text rather than from the position.

    Reads the VarSet (or Spreadsheet-backed) façade Story 4.6 owns; this module never writes it.
    A property whose value carries no magnitude is skipped rather than coerced: a string or a bool
    parameter is a real thing to declare, and inventing a number for it would put a fabricated
    callout on the sheet.
    """
    parameters: list[tuple[str, float]] = []
    for name in _PARAMETER_OBJECT_NAMES:
        holder = document.getObject(name)
        if holder is None:
            continue
        for prop in holder.PropertiesList:
            if prop in _BASE_PROPERTIES:
                continue
            value = _magnitude(getattr(holder, prop, None))
            if value is not None:
                parameters.append((prop, value))
    return parameters


def _magnitude(raw: object) -> float | None:
    """Return ``raw`` as a millimetre magnitude, or ``None`` when it carries none.

    A FreeCAD ``App::PropertyLength`` reads back as a ``Quantity`` carrying its unit, so the
    magnitude is taken from ``.Value`` when present; a plain float passes through. A bool is
    rejected explicitly — it is a ``float`` subclass in Python and would otherwise become a
    ``1.00`` callout.
    """
    if isinstance(raw, bool):
        return None
    value = getattr(raw, "Value", raw)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _assert_unchanged(document: object, before: dict) -> None:
    """Assert the part document is geometrically identical to ``before``.

    Compares mass properties rather than the raw digest for the reason the screenshot path does:
    OCCT re-lays-out a shape's serialization the first time something copies it, so the bytes can
    change while the geometry does not. A real mutation still moves the mass properties.

    :raises ValidationError: the drawing changed the part document.
    """
    if not massprops_equal(before, fingerprint(document)):
        raise ValidationError(
            "techdraw_for_judge mutated the part document (geometry changed); the drawing must be "
            "built entirely on the TempDoc copy"
        )


# ------------------------------------------------------------------------------------------
# The TempDoc build
# ------------------------------------------------------------------------------------------


def _compose_and_rasterize(
    shape: object,
    parameters: list[tuple[str, float]],
    raster_port: SvgRasterPort,
    width_px: int,
) -> DrawingSheet:
    """Build the views on a TempDoc, compose the sheet, rasterize it, and discard the TempDoc.

    The TempDoc and both output files are cleaned up on every path. A failure partway through the
    build leaves no document and no file: a leaked TempDoc is adopted by ``document_list`` and
    surfaced to the caller mislabeled, and a leaked temp file outlives the session that could
    explain it.
    """
    import FreeCAD

    document = FreeCAD.newDocument(f"{_TEMPDOC_PREFIX}{secrets.token_hex(8)}")
    svg_path: str | None = None
    png_path: str | None = None
    try:
        views = _build_views(document, shape, raster_port)
        callouts = _build_callouts(document, views, parameters)
        svg, height_px = _compose_sheet(views, callouts, width_px)
        svg_path = _write_svg(svg)
        png_path = _write_png(raster_port, svg, width_px, height_px)
        return {
            "schema": "fcb.drawing-sheet/1",
            "available": True,
            "reason": None,
            "svg_path": svg_path,
            "png_path": png_path,
            "page_width_px": width_px,
            "page_height_px": height_px,
            "views": [view.name for view in views],
            "callouts": callouts,
        }
    except BaseException:
        _remove(svg_path)
        _remove(png_path)
        raise
    finally:
        _discard(document)


def _build_views(document: object, shape: object, raster_port: SvgRasterPort) -> list[_PlacedView]:
    """Build the three projections on ``document`` and return each one's placed view.

    The subject is a copy of the part's shape on a plain ``Part::Feature``, not a link back to the
    part document — the TempDoc must be destroyable without reaching into the document being
    drawn.

    :raises TechDrawUnavailable: a projection produced no geometry within the settle budget.
    """
    import FreeCAD
    import TechDraw

    subject = document.addObject("Part::Feature", "Subject")
    subject.Shape = shape.copy()
    page = document.addObject("TechDraw::DrawPage", "Page")
    page.Template = document.addObject("TechDraw::DrawSVGTemplate", "Template")

    views: list[_PlacedView] = []
    for name, direction, x_direction in _VIEW_DIRECTIONS:
        view = document.addObject("TechDraw::DrawViewPart", f"View_{name}")
        view.Source = [subject]
        view.Direction = FreeCAD.Vector(*direction)
        view.XDirection = FreeCAD.Vector(*x_direction)
        page.addView(view)
        document.recompute()
        fragment = _await_view_svg(TechDraw, view, name, raster_port)
        width, height = _fragment_extent(fragment)
        views.append(_PlacedView(name=name, fragment=fragment, width=width, height=height))
    return views


def _await_view_svg(techdraw_module, view: object, name: str, raster_port: SvgRasterPort) -> str:
    """Read a built view's SVG, waiting for the hidden-line-removal pass when one is pending.

    **An empty SVG is a real, silent outcome, and the whole reason this is a loop.** A
    ``DrawViewPart``'s projected geometry is computed by an HLR pass that runs asynchronously
    whenever a Qt application object exists — every GUI process, and any headless process that has
    brought Qt up. Until it finishes, ``viewPartAsSvg`` returns an empty string and raises nothing.
    Decision 016 records the same outcome measured in the GUI (R3-01); the measurement that pins it
    here is FreeCAD 1.1.1 with a ``QApplication`` up, where a view's SVG went from 0 bytes to 308
    bytes of real path geometry after two ``settle()`` calls.

    **Neither ``recompute()`` returning nor ``State`` is a usable signal** — ``State`` read
    ``['Up-to-date']`` on every failing attempt in that same measurement. The SVG's own content is
    therefore the completion signal, which is what this polls on.

    A bare ``FreeCADCmd`` process with no event loop computes HLR synchronously and satisfies the
    first read, so the loop costs it nothing.

    :raises TechDrawUnavailable: no drawn geometry arrived within ``_MAX_SETTLE_ATTEMPTS``.
    """
    for _attempt in range(_MAX_SETTLE_ATTEMPTS):
        fragment = techdraw_module.viewPartAsSvg(view)
        if fragment and any(tag in fragment for tag in _GEOMETRY_TAGS):
            return fragment
        raster_port.settle()
    raise TechDrawUnavailable(
        f"the {name} projection produced no drawn geometry after {_MAX_SETTLE_ATTEMPTS} settle "
        "attempts; the hidden-line-removal pass did not finish and the sheet would be blank"
    )


def _build_callouts(
    document: object,
    views: list[_PlacedView],
    parameters: list[tuple[str, float]],
) -> list[DimensionCallout]:
    """Create a TechDraw dimension per driving parameter and return what the sheet must draw.

    Every dimension is created with ``Arbitrary = True`` and its ``FormatSpec`` set to the
    parameter's value, which makes the object's own text the parameter rather than a measurement
    of the projected geometry. That is the point of the whole mechanism: a callout re-derived from
    the view would agree with the part however wrong the part was, so the judge's dimension
    cross-check — the only check that can catch a spec-to-assertion mistranslation — would always
    pass.

    The drawn string is then read back out of the object with ``getText()`` rather than
    re-formatted here, so the document object and the glyphs on the sheet cannot disagree.

    **Each callout goes under a view that actually displays its axis** — see
    :func:`_view_for_parameter`. Placement is not presentational: by drawing convention a caption
    beneath a view is a claim about that view, and a vision judge reads drawings by that
    convention, so a thickness caption under the one projection that cannot show thickness is a
    false claim the sheet makes about itself.
    """
    import FreeCAD
    import TechDraw

    callouts: list[DimensionCallout] = []
    for index, (parameter, value) in enumerate(parameters):
        placed = _view_for_parameter(parameter, views, index)
        view = document.getObject(f"View_{placed.name}")
        dimension = TechDraw.makeDistanceDim(
            view, "DistanceX", FreeCAD.Vector(0.0, 0.0, 0.0), FreeCAD.Vector(value, 0.0, 0.0)
        )
        dimension.Arbitrary = True
        dimension.FormatSpec = _format_value(value)
        document.recompute()
        callouts.append(
            {
                "view": placed.name,
                "parameter": parameter,
                "value": value,
                "text": str(dimension.getText()),
                "kind": "distance",
            }
        )
    return callouts


def _parameter_axis(parameter: str) -> str | None:
    """The model axis a driving-parameter name declares, or ``None`` when it names none.

    Read from the name, never from the produced geometry: measuring the shape to decide where a
    caption goes would reintroduce the geometry-agreement that parameter-sourcing exists to
    prevent. ``plate_thickness`` yields ``"z"``; ``hole_diameter`` yields ``None``, because a
    diameter is in-plane in every view that shows the hole and naming an axis for it would invent
    a claim the drawing does not make.

    Matching is on whole words after splitting the name on non-alphabetic characters, so
    ``plate_length`` and ``PlateLength`` both resolve while ``wavelength`` does not.
    """
    for word in _split_words(parameter):
        axis = _AXIS_WORDS.get(word)
        if axis is not None:
            return axis
    return None


def _split_words(name: str) -> list[str]:
    """Split a parameter name into lowercase words, handling snake_case and camelCase alike.

    Story 4.6 owns the façade that names these and has not fixed a spelling convention, so both
    are read rather than betting on one.
    """
    words: list[str] = []
    current: list[str] = []
    for char in name:
        if not char.isalpha():
            if current:
                words.append("".join(current).lower())
                current = []
            continue
        if char.isupper() and current:
            words.append("".join(current).lower())
            current = [char]
            continue
        current.append(char)
    if current:
        words.append("".join(current).lower())
    return words


def _view_for_parameter(parameter: str, views: list[_PlacedView], index: int) -> _PlacedView:
    """Pick the view whose picture plane displays ``parameter``'s axis.

    A caption under a drawing view is a spatial claim about that view — that is what engineering
    drawings mean by convention, and a vision judge reads them by that convention. So a thickness
    callout must not sit under the top view, which looks straight down the thickness axis and
    cannot show it. Placing it there makes every clean sheet carry one false claim, which matters
    most in the fault suite: the wrong-dimension-callout case's clean controls are supposed to be
    callout-correct, and controls that all mispair a callout inflate the judge's false-alarm rate
    against the very measurement the visual leg exists to provide.

    A parameter naming no axis (a diameter, a pitch, a spacing) is spread round-robin over the
    views instead. That is a presentational choice and stays one: such a dimension is in-plane
    wherever its feature appears, so no placement asserts an axis the view cannot show.

    Falls back to the round-robin position when the named axis is in no view's plane, which the
    three fixed orthographic directions make unreachable today — every axis lies in two of the
    three planes — but which a fourth view or a changed direction set would open.
    """
    axis = _parameter_axis(parameter)
    if axis is not None:
        showing = [view for view in views if axis in _VIEW_PLANE_AXES.get(view.name, frozenset())]
        if showing:
            # Spread across the views that can legitimately show this axis, so a part whose
            # parameters share one axis does not stack every caption under one view.
            return showing[index % len(showing)]
    return views[index % len(views)]


def _format_value(value: float) -> str:
    """Render a parameter value as the callout string: two decimals, millimetres implied."""
    return f"{value:.2f}"


def _discard(document: object) -> None:
    """Close the TempDoc, swallowing every failure.

    Runs on the success, failure and exception paths alike. A failed close must not mask the
    outcome being reported, and a TempDoc left open is adopted by ``document_list`` and shown to
    the caller as one of their own documents.
    """
    import FreeCAD

    try:
        FreeCAD.closeDocument(document.Name)
    except Exception:  # noqa: BLE001 - a failed close must not mask the drawing's outcome
        pass


# ------------------------------------------------------------------------------------------
# The SVG compositor
# ------------------------------------------------------------------------------------------


def _fragment_extent(fragment: str) -> tuple[float, float]:
    """Return the ``(width, height)`` in millimetres of the geometry in an SVG fragment.

    ``viewPartAsSvg`` returns straight ``<path d="M x y L x y">`` segments in view-local
    millimetres, so the extent is the span of the coordinate pairs. Circular edges arrive as
    ``<circle cx cy r>`` instead and are read separately — a view whose outline is entirely
    circular (any turned part seen end-on) has no ``d`` attribute at all, and measuring only paths
    would report it as zero-extent. That is not harmless: ``_sheet_scale`` would then pick a scale
    from the other two views alone and the circle could overflow its cell.

    A fragment whose coordinates cannot be read yields a zero extent, which ``_sheet_scale`` then
    ignores rather than letting it collapse the sheet scale to zero.
    """
    xs: list[float] = []
    ys: list[float] = []
    for chunk in fragment.split('d="')[1:]:
        body = chunk.split('"')[0]
        numbers = _numbers(body)
        xs.extend(numbers[0::2])
        ys.extend(numbers[1::2])
    for centre_x, centre_y, radius in _circles(fragment):
        xs.extend((centre_x - radius, centre_x + radius))
        ys.extend((centre_y - radius, centre_y + radius))
    if not xs or not ys:
        return 0.0, 0.0
    return max(xs) - min(xs), max(ys) - min(ys)


# One ``<circle>`` element's centre and radius. TechDraw writes the three attributes in this order
# and quotes each, so a single expression reads them without an XML parse this ring cannot afford.
_CIRCLE_ELEMENT = re.compile(
    r'<circle[^>]*\bcx="(-?[\d.eE+]+)"[^>]*\bcy="(-?[\d.eE+]+)"[^>]*\br="(-?[\d.eE+]+)"'
)


def _circles(fragment: str) -> list[tuple[float, float, float]]:
    """Every ``<circle>`` in ``fragment`` as ``(cx, cy, r)``, skipping any it cannot parse."""
    circles: list[tuple[float, float, float]] = []
    for centre_x, centre_y, radius in _CIRCLE_ELEMENT.findall(fragment):
        try:
            circles.append((float(centre_x), float(centre_y), float(radius)))
        except ValueError:
            continue
    return circles


def _numbers(body: str) -> list[float]:
    """Parse every numeric token out of an SVG path ``d`` body, dropping the command letters."""
    values: list[float] = []
    for token in body.replace(",", " ").split():
        try:
            values.append(float(token))
        except ValueError:
            continue
    return values


def _sheet_scale(views: list[_PlacedView]) -> float:
    """The one scale every view is drawn at: the largest that fits all three in their cells.

    A single sheet-wide scale rather than a per-view fit, so the judge can compare proportions
    *between* views. Per-view fitting would draw a 5 mm part and a 500 mm part the same size, which
    is precisely the "grossly wrong proportions" fault the judge's suite plants.
    """
    cell_width = _SHEET_WIDTH_MM / len(views)
    usable_width = cell_width - 2 * _CELL_MARGIN_MM
    usable_height = _SHEET_HEIGHT_MM - _CALLOUT_BAND_MM - _LABEL_HEIGHT_MM - 2 * _CELL_MARGIN_MM
    scales = [
        min(usable_width / view.width, usable_height / view.height)
        for view in views
        if view.is_measurable
    ]
    return min(scales) if scales else 1.0


def _compose_sheet(
    views: list[_PlacedView],
    callouts: list[DimensionCallout],
    width_px: int,
) -> tuple[str, int]:
    """Place the view fragments and their callouts on one canvas; return ``(svg, height_px)``.

    The canvas is sized in millimetres and the ``width``/``height`` attributes in pixels, with a
    ``viewBox`` mapping one to the other, so the rasterizer's output size and the drawing's
    millimetre geometry are independent — the sheet can be re-rasterized at any size without
    recomposing it.
    """
    height_px = round(width_px * _SHEET_HEIGHT_MM / _SHEET_WIDTH_MM)
    scale = _sheet_scale(views)
    cell_width = _SHEET_WIDTH_MM / len(views)
    drawing_height = _SHEET_HEIGHT_MM - _CALLOUT_BAND_MM

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" height="{height_px}" '
        f'viewBox="0 0 {_SHEET_WIDTH_MM:g} {_SHEET_HEIGHT_MM:g}">',
        f'<rect x="0" y="0" width="{_SHEET_WIDTH_MM:g}" height="{_SHEET_HEIGHT_MM:g}" '
        f'fill="#ffffff"/>',
    ]
    for index, view in enumerate(views):
        centre_x = cell_width * (index + 0.5)
        centre_y = _LABEL_HEIGHT_MM + (drawing_height - _LABEL_HEIGHT_MM) / 2
        parts.append(
            f'<g transform="translate({centre_x:.4f},{centre_y:.4f}) '
            f'scale({scale:.6f},{-scale:.6f})">{view.fragment}</g>'
        )
        parts.append(
            _text(centre_x, _LABEL_HEIGHT_MM * 0.75, view.name.upper(), _LABEL_HEIGHT_MM * 0.6)
        )
        parts.extend(_callout_lines(view, callouts, centre_x, centre_y, drawing_height, scale))
    parts.append(
        f'<rect x="{_STROKE_MM:g}" y="{_STROKE_MM:g}" '
        f'width="{_SHEET_WIDTH_MM - 2 * _STROKE_MM:g}" '
        f'height="{_SHEET_HEIGHT_MM - 2 * _STROKE_MM:g}" '
        f'fill="none" stroke="#000000" stroke-width="{_STROKE_MM:g}"/>'
    )
    # Every view is drawn at this one ratio, and the sheet says so. A judge asked whether the
    # proportions match a stated size otherwise has only relative sizes to go on and no declared
    # value to check them against; with the scale stated it can read a length off the drawing.
    parts.append(
        _text(
            _SHEET_WIDTH_MM / 2,
            _SHEET_HEIGHT_MM - _CALLOUT_LINE_MM,
            f"ALL VIEWS SCALE {_scale_ratio(scale)} — DIMENSIONS IN MM",
            _CALLOUT_LINE_MM * 0.7,
        )
    )
    parts.append("</svg>")
    return "".join(parts), height_px


def _scale_ratio(scale: float) -> str:
    """Render a scale factor as a drawing-conventional ratio, such as ``1.25:1`` or ``1:2``.

    Drawings state scale as a ratio, not a decimal multiplier, and a judge reading the sheet reads
    that convention. Factors at or above 1 are written ``n:1`` (enlarged); below 1 they are
    inverted to ``1:n`` (reduced), so the printed number stays greater than one either way.
    """
    if scale <= 0:
        return "1:1"
    if scale >= 1.0:
        return f"{scale:.6g}:1"
    return f"1:{1.0 / scale:.6g}"


def _callout_lines(
    view: _PlacedView,
    callouts: list[DimensionCallout],
    centre_x: float,
    centre_y: float,
    band_top: float,
    scale: float,
) -> list[str]:
    """The dimension bars and captions for one view's cell.

    An axis-bearing callout is drawn the way a drawing draws one: a bar spanning the silhouette's
    measured extent, a tick at each end, and the caption on the bar. That is what ties
    ``plate_length = 80.00`` to the edge it measures — a judge cross-checking a callout against
    the drawing otherwise has to guess which feature the number belongs to.

    **The bar is placed clear of the silhouette, never across it.** A first attempt ran a leader
    from the caption band up to a far edge and produced long diagonals that crossed the part and
    each other — visible immediately in the rendered sheet and invisible to every assertion. A bar
    that spans the extent it measures, offset just outside the silhouette, cannot do that: its
    length *is* the measurement, so it has nowhere misleading to go.

    A callout naming no axis (a diameter, an inset) has no extent to span, so it stays a plain
    caption in the band below. Drawing a bar for it would assert a span the name never declared.

    Ticks rather than arrowheads: arrowheads need the graphical dimension machinery that lives in
    ``TechDrawGui`` and is unreachable headless (DW-118), and a tick carries the same "this is
    where the measurement ends" meaning at this size.
    """
    lines: list[str] = []
    own = [callout for callout in callouts if callout["view"] == view.name]
    horizontal, vertical = _VIEW_SCREEN_AXES[view.name]
    half_width = view.width * scale / 2
    half_height = view.height * scale / 2

    plain: list[DimensionCallout] = []
    horizontal_bars = 0
    vertical_bars = 0
    for callout in own:
        axis = _parameter_axis(callout["parameter"])
        label = f"{callout['parameter']} = {callout['text']}"
        if axis == horizontal:
            offset = _DIM_BAR_GAP_MM + horizontal_bars * _DIM_BAR_PITCH_MM
            lines.extend(
                _horizontal_bar(centre_x, centre_y + half_height + offset, half_width, label)
            )
            horizontal_bars += 1
        elif axis == vertical:
            offset = _DIM_BAR_GAP_MM + vertical_bars * _DIM_BAR_PITCH_MM
            lines.extend(
                _vertical_bar(centre_x - half_width - offset, centre_y, half_height, label)
            )
            vertical_bars += 1
        else:
            plain.append(callout)

    for index, callout in enumerate(plain):
        y = band_top + _CALLOUT_LINE_MM * (index + 1)
        label = f"{callout['parameter']} = {callout['text']}"
        lines.append(_text(centre_x, y, label, _CALLOUT_LINE_MM * 0.7))
    return lines


def _horizontal_bar(centre_x: float, y: float, half_width: float, label: str) -> list[str]:
    """A dimension bar spanning the silhouette's width at ``y``, captioned above it."""
    left, right = centre_x - half_width, centre_x + half_width
    tick = _DIM_TICK_MM
    return [
        f'<line x1="{left:.4f}" y1="{y:.4f}" x2="{right:.4f}" y2="{y:.4f}" '
        f'stroke="#000000" stroke-width="{_STROKE_MM * 0.5:g}"/>',
        f'<line x1="{left:.4f}" y1="{y - tick:.4f}" x2="{left:.4f}" y2="{y + tick:.4f}" '
        f'stroke="#000000" stroke-width="{_STROKE_MM * 0.5:g}"/>',
        f'<line x1="{right:.4f}" y1="{y - tick:.4f}" x2="{right:.4f}" y2="{y + tick:.4f}" '
        f'stroke="#000000" stroke-width="{_STROKE_MM * 0.5:g}"/>',
        _text(centre_x, y - tick * 1.2, label, _CALLOUT_LINE_MM * 0.7),
    ]


def _vertical_bar(x: float, centre_y: float, half_height: float, label: str) -> list[str]:
    """A dimension bar spanning the silhouette's height at ``x``, captioned along it.

    The caption is rotated onto the bar, which is what keeps a tall thin dimension readable
    without widening the cell to fit horizontal text beside it.
    """
    top, bottom = centre_y - half_height, centre_y + half_height
    tick = _DIM_TICK_MM
    return [
        f'<line x1="{x:.4f}" y1="{top:.4f}" x2="{x:.4f}" y2="{bottom:.4f}" '
        f'stroke="#000000" stroke-width="{_STROKE_MM * 0.5:g}"/>',
        f'<line x1="{x - tick:.4f}" y1="{top:.4f}" x2="{x + tick:.4f}" y2="{top:.4f}" '
        f'stroke="#000000" stroke-width="{_STROKE_MM * 0.5:g}"/>',
        f'<line x1="{x - tick:.4f}" y1="{bottom:.4f}" x2="{x + tick:.4f}" y2="{bottom:.4f}" '
        f'stroke="#000000" stroke-width="{_STROKE_MM * 0.5:g}"/>',
        f'<g transform="rotate(-90 {x - tick * 1.2:.4f} {centre_y:.4f})">'
        f"{_text(x - tick * 1.2, centre_y, label, _CALLOUT_LINE_MM * 0.7)}</g>",
    ]


def _text(x: float, y: float, content: str, size: float) -> str:
    """One centred SVG text element, with the content XML-escaped."""
    escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<text x="{x:.4f}" y="{y:.4f}" font-family="sans-serif" font-size="{size:.4f}" '
        f'fill="#000000" text-anchor="middle">{escaped}</text>'
    )


# ------------------------------------------------------------------------------------------
# Output files
# ------------------------------------------------------------------------------------------


def _write_svg(svg: str) -> str:
    """Write the composed sheet to a reserved-prefix temp file inside the session workdir."""
    fd, path = tempfile.mkstemp(prefix=f"{_TEMPDOC_PREFIX}sheet_", suffix=".svg", dir=temp_dir())
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(svg)
    return path


def _write_png(raster_port: SvgRasterPort, svg: str, width_px: int, height_px: int) -> str:
    """Rasterize the sheet and return the PNG path; a port that wrote nothing is a failure.

    :raises TechDrawUnavailable: the rasterizer returned without writing a usable image.
    """
    fd, path = tempfile.mkstemp(prefix=f"{_TEMPDOC_PREFIX}sheet_", suffix=".png", dir=temp_dir())
    os.close(fd)
    try:
        raster_port.rasterize(svg, path, width_px, height_px)
        if not os.path.exists(path) or os.path.getsize(path) <= 0:
            raise TechDrawUnavailable("the rasterizer produced an empty or missing PNG")
    except BaseException:
        _remove(path)
        raise
    return path


def _remove(path: str | None) -> None:
    """Remove ``path`` if present, swallowing an already-gone file."""
    if path is None:
        return
    try:
        os.remove(path)
    except OSError:
        pass


# ------------------------------------------------------------------------------------------
# Envelope
# ------------------------------------------------------------------------------------------


def _unavailable_sheet(reason: str | None) -> DrawingSheet:
    """The no-capability sheet: nothing drawn, the reason named, no image path."""
    return {
        "schema": "fcb.drawing-sheet/1",
        "available": False,
        "reason": reason,
        "svg_path": None,
        "png_path": None,
        "page_width_px": 0,
        "page_height_px": 0,
        "views": [],
        "callouts": [],
    }


def summarize_drawing_sheet(sheet: DrawingSheet) -> str:
    """One-line summary: what was drawn and at what width, or why nothing was."""
    if not sheet.get("available", False):
        return f"Judge drawing unavailable: {sheet.get('reason')}."
    views = ", ".join(sheet.get("views") or [])
    return (
        f"Composed a {sheet.get('page_width_px')}px sheet with {views} projections and "
        f"{len(sheet.get('callouts') or [])} parameter-sourced callout(s)."
    )


def _ok_envelope(sheet: DrawingSheet, image: ImageRef | None) -> ResultEnvelope:
    """Build the OK envelope; ``image`` is ``None`` when no sheet was rasterized."""
    envelope: ResultEnvelope = {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": sheet,
        "text": summarize_drawing_sheet(sheet),
    }
    if image is not None:
        envelope["images"] = [image]
    return envelope


__all__ = ["TechDrawUnavailable", "summarize_drawing_sheet", "techdraw_for_judge"]
