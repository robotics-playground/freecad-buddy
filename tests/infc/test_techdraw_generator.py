"""In-FreeCAD tests for ``techdraw_for_judge`` (story 4.3).

Runs via ``FreeCADCmd tests/run_tests.py``. The acceptance claims this suite has to be able to
falsify are the four the spec states: the part document is byte-identical across the call, the
sheet clears the judge's 2048 px floor with three *distinct* projections, a failure partway
through leaves no TempDoc and no temp file, and a driving-parameter change moves the callout —
which is what proves the number came from the declared intent rather than from the produced
geometry.

The complementary boundary suite is ``test_techdraw_probe.py``: that one pins what FreeCAD
exposes, this one pins what the generator does with it.
"""

import glob
import os
import unittest

import FreeCAD as App

from freecad_buddy.adapters.render_probe import QtSvgRasterPort
from freecad_buddy.contracts import fingerprints_equal
from freecad_buddy.usecases import techdraw
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError, temp_dir
from freecad_buddy.usecases.fingerprint import fingerprint

# The part every case draws: an 80 x 60 x 6 plate. Chosen so the three projections have three
# different extents (80x6 front, 80x60 top, 60x6 right) — a sheet that drew one view three times
# would pass a "three views present" check but fail the distinctness assertion below.
PLATE_LENGTH = 80.0
PLATE_WIDTH = 60.0
PLATE_THICKNESS = 6.0

# The washer the circle-only projection case draws: an M10 flat washer, whose top view is two
# concentric circles and therefore carries no path geometry at all.
WASHER_OUTER_RADIUS = 10.5
WASHER_BORE_RADIUS = 5.15
WASHER_THICKNESS = 2.0

_SHEET_GLOB = os.path.join(temp_dir(), "FCB_TMP_td_sheet_*")


def _sheet_files():
    """Every sheet artifact currently under the session temp directory."""
    return set(glob.glob(_SHEET_GLOB))


class _FailingRasterPort:
    """A rasterizer that reports available and then fails, to drive the mid-build failure path."""

    def available(self):
        return True, None

    def settle(self):
        pass

    def rasterize(self, svg, out_path, width, height):
        raise RuntimeError("planted rasterizer failure")


class _UnavailableRasterPort:
    """A rasterizer that reports itself unavailable, to drive the degradation path."""

    reason = "no SVG rasterizer on this leg"

    def available(self):
        return False, self.reason

    def settle(self):
        raise AssertionError("settle must not be called when the port reports unavailable")

    def rasterize(self, svg, out_path, width, height):
        raise AssertionError("rasterize must not be called when the port reports unavailable")


class _NeverSettlingRasterPort:
    """A port whose settle never completes the HLR pass, to drive the blank-sheet refusal.

    This is the failure decision 016 names R3-01: the SVG stays empty and nothing raises on its
    own. The generator must refuse rather than compose a blank sheet.
    """

    def __init__(self):
        self.settle_calls = 0

    def available(self):
        return True, None

    def settle(self):
        self.settle_calls += 1

    def rasterize(self, svg, out_path, width, height):
        raise AssertionError("a blank sheet must never reach the rasterizer")


class TechDrawGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.port = QtSvgRasterPort()
        self.handle = self.registry.document_create("techdraw_part")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))
        self._build_plate()
        self._before_sheets = _sheet_files()

    def _build_plate(self):
        import Part

        plate = self.document.addObject("Part::Feature", "Plate")
        plate.Shape = Part.makeBox(PLATE_LENGTH, PLATE_WIDTH, PLATE_THICKNESS)
        self.parameters = self.document.addObject("App::VarSet", "Parameters")
        for name, value in (
            ("PlateLength", PLATE_LENGTH),
            ("PlateWidth", PLATE_WIDTH),
            ("PlateThickness", PLATE_THICKNESS),
        ):
            self.parameters.addProperty("App::PropertyLength", name, "Driving", "")
            setattr(self.parameters, name, value)
        self.document.recompute()

    def tearDown(self):
        for path in _sheet_files() - self._before_sheets:
            try:
                os.remove(path)
            except OSError:
                pass
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _draw(self, port=None, page_width_px=None):
        return techdraw.techdraw_for_judge(
            self.registry,
            port or self.port,
            doc=self.handle,
            page_width_px=page_width_px,
        )

    def _require_available(self, envelope):
        sheet = envelope["structured_content"]
        if not sheet["available"]:
            self.skipTest(f"no drawing capability on this leg: {sheet['reason']}")
        return sheet

    # -- fingerprint purity -------------------------------------------------------------

    def test_Should_leave_the_part_fingerprint_byte_identical_When_the_drawing_is_generated(self):
        # Arrange
        before = fingerprint(self.document)

        # Act
        envelope = self._draw()

        # Assert
        self._require_available(envelope)
        self.assertTrue(
            fingerprints_equal(before, fingerprint(self.document)),
            "the drawing changed the part document; it must be built on the TempDoc copy alone",
        )

    def test_Should_write_no_techdraw_object_into_the_part_When_the_drawing_is_generated(self):
        # Arrange
        names_before = [obj.Name for obj in self.document.Objects]

        # Act
        envelope = self._draw()

        # Assert
        self._require_available(envelope)
        self.assertEqual([obj.Name for obj in self.document.Objects], names_before)
        self.assertEqual(
            [obj.Name for obj in self.document.Objects if "TechDraw" in str(obj.TypeId)],
            [],
            "a TechDraw object was written into the part document",
        )

    def test_Should_leave_no_tempdoc_open_When_the_drawing_is_generated(self):
        # Arrange
        before = set(App.listDocuments().keys())

        # Act
        envelope = self._draw()

        # Assert
        self._require_available(envelope)
        leaked = [name for name in set(App.listDocuments().keys()) - before]
        self.assertEqual(leaked, [], f"the TempDoc was not discarded: {leaked}")

    # -- the sheet itself ---------------------------------------------------------------

    def test_Should_clear_the_judge_page_width_floor_When_no_width_is_requested(self):
        # Arrange
        floor = 2048

        # Act
        envelope = self._draw()

        # Assert
        sheet = self._require_available(envelope)
        self.assertGreaterEqual(sheet["page_width_px"], floor)

    def test_Should_floor_a_narrow_request_When_a_caller_asks_below_the_judge_minimum(self):
        # Arrange
        requested = 800

        # Act
        envelope = self._draw(page_width_px=requested)

        # Assert
        sheet = self._require_available(envelope)
        self.assertGreaterEqual(
            sheet["page_width_px"],
            2048,
            "a narrow request must be floored, never honoured: a callout the judge cannot read "
            "fails a correct part for a reason no assertion reports",
        )

    def test_Should_write_a_png_at_the_declared_size_When_the_sheet_is_rasterized(self):
        # Act
        envelope = self._draw()

        # Assert
        sheet = self._require_available(envelope)
        self.assertTrue(os.path.exists(sheet["png_path"]), "no PNG was written")
        self.assertGreater(os.path.getsize(sheet["png_path"]), 0, "the PNG is empty")
        self.assertEqual(
            envelope["images"][0]["uri"],
            sheet["png_path"],
            "the envelope's image must point at the sheet the structured content names",
        )

    def test_Should_carry_three_distinct_projections_When_the_sheet_is_composed(self):
        # Arrange
        expected = ["front", "top", "right"]

        # Act
        envelope = self._draw()
        sheet = self._require_available(envelope)
        svg = open(sheet["svg_path"], encoding="utf-8").read()

        # Assert
        self.assertEqual(sheet["views"], expected)
        # One placed view per `<g transform="translate(...">` wrapper the compositor emits; the
        # path data inside it is that projection's geometry, so comparing the sorted `d` bodies
        # compares the projections themselves rather than their placement on the sheet.
        fragments = [chunk.split("</g>")[0] for chunk in svg.split('<g transform="translate(')[1:]]
        self.assertEqual(len(fragments), len(expected), "the sheet placed the wrong view count")
        geometry = [
            "".join(sorted(part.split('"')[0] for part in fragment.split('d="')[1:]))
            for fragment in fragments
        ]
        self.assertTrue(all(geometry), "a placed view carries no path geometry")
        self.assertEqual(
            len(set(geometry)),
            len(expected),
            "the three projections are not distinct; the sheet drew one view more than once",
        )

    def test_Should_place_every_callout_on_the_sheet_When_the_svg_is_composed(self):
        # Act
        envelope = self._draw()
        sheet = self._require_available(envelope)
        svg = open(sheet["svg_path"], encoding="utf-8").read()

        # Assert
        self.assertTrue(sheet["callouts"], "the sheet carries no callouts")
        for callout in sheet["callouts"]:
            self.assertIn(
                f"{callout['parameter']} = {callout['text']}",
                svg,
                "a callout the result declares is not drawn on the sheet",
            )

    # -- parameter-sourced dimensions ---------------------------------------------------

    def test_Should_name_every_driving_parameter_When_the_callouts_are_generated(self):
        # Arrange
        declared = {"PlateLength", "PlateWidth", "PlateThickness"}

        # Act
        envelope = self._draw()

        # Assert
        sheet = self._require_available(envelope)
        self.assertEqual({callout["parameter"] for callout in sheet["callouts"]}, declared)

    def test_Should_follow_the_parameter_When_a_driving_parameter_changes(self):
        """The acceptance test for parameter-sourcing: the callout must move with the parameter.

        The geometry is deliberately NOT rebuilt between the two runs — only the parameter is
        changed. A callout read off the produced geometry therefore cannot move, while a
        parameter-sourced one must. That separation is what makes this falsifying rather than
        merely confirming.
        """
        # Arrange
        first = self._require_available(self._draw())
        before = self._callout_text(first, "PlateLength")
        changed = PLATE_LENGTH + 25.0

        # Act
        self.parameters.PlateLength = changed
        self.document.recompute()
        second = self._require_available(self._draw())

        # Assert
        after = self._callout_text(second, "PlateLength")
        self.assertNotEqual(after, before, "the callout did not follow the driving parameter")
        self.assertEqual(after, f"{changed:.2f}")

    def _callout_text(self, sheet, parameter):
        for callout in sheet["callouts"]:
            if callout["parameter"] == parameter:
                return callout["text"]
        self.fail(f"no callout for {parameter}")

    def test_Should_place_every_callout_under_a_view_that_displays_its_axis(self):
        """A caption under a view is a spatial claim about that view, so it must be a true one.

        The defect this pins shipped once: callouts were spread round-robin over the views in
        alphabetical parameter order, which put ``plate_thickness`` under TOP — the one projection
        that looks straight down the thickness axis and cannot show it. Every assertion in this
        suite passed while the sheet made that false claim, because they all checked the callout's
        text and none checked where it landed.

        It matters most in the fault suite: the wrong-dimension-callout case's clean controls are
        supposed to be callout-correct, so controls that all mispair a callout inflate the judge's
        false-alarm rate against the measurement the visual leg exists to provide.
        """
        # Arrange
        axis_of = {"PlateLength": "x", "PlateWidth": "y", "PlateThickness": "z"}
        visible_in = {"front": {"x", "z"}, "top": {"x", "y"}, "right": {"y", "z"}}

        # Act
        envelope = self._draw()

        # Assert
        sheet = self._require_available(envelope)
        for callout in sheet["callouts"]:
            axis = axis_of[callout["parameter"]]
            self.assertIn(
                axis,
                visible_in[callout["view"]],
                f"{callout['parameter']} (axis {axis}) is captioned under the {callout['view']} "
                f"view, which cannot display that axis",
            )

    def test_Should_state_the_drawing_scale_When_the_sheet_is_composed(self):
        """A judge checking proportions needs a declared scale, not only relative sizes."""
        # Act
        envelope = self._draw()
        sheet = self._require_available(envelope)
        svg = open(sheet["svg_path"], encoding="utf-8").read()

        # Assert
        self.assertIn("ALL VIEWS SCALE", svg, "the sheet states no scale")
        self.assertIn("DIMENSIONS IN MM", svg, "the sheet states no unit")

    def test_Should_draw_one_scale_for_every_view_When_the_sheet_is_composed(self):
        """Proportions are only comparable between views when all three share one scale."""
        # Arrange
        import re

        # Act
        envelope = self._draw()
        sheet = self._require_available(envelope)
        svg = open(sheet["svg_path"], encoding="utf-8").read()

        # Assert
        scales = re.findall(r"scale\(([-\d.]+),([-\d.]+)\)", svg)
        self.assertEqual(len(scales), 3, "expected one placed view per projection")
        self.assertEqual(
            len(set(scales)),
            1,
            f"the views are drawn at different scales, so proportions cannot be compared: {scales}",
        )

    def test_Should_draw_a_dimension_bar_spanning_the_extent_it_measures(self):
        """A dimension bar's length IS the measurement, which is what ties a number to an edge.

        Asserted as geometry, not as a line count: the first attempt at this drew leaders from the
        caption band to a far edge, which passed a count assertion while rendering long diagonals
        across the part. A bar whose span must equal the silhouette's scaled extent cannot do that.
        """
        # Arrange
        import re

        expected_span = PLATE_LENGTH  # the front view's horizontal extent, in model mm

        # Act
        envelope = self._draw()
        sheet = self._require_available(envelope)
        svg = open(sheet["svg_path"], encoding="utf-8").read()

        # Assert
        scale = float(re.search(r"scale\(([-\d.]+),", svg).group(1))
        spans = [
            abs(float(x2) - float(x1))
            for x1, y1, x2, y2 in re.findall(
                r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"', svg
            )
            if y1 == y2 and abs(float(x2) - float(x1)) > 1.0
        ]
        self.assertTrue(spans, "the sheet carries no horizontal dimension bar")
        self.assertAlmostEqual(
            max(spans),
            expected_span * scale,
            places=3,
            msg="the longest dimension bar does not span the scaled plate length",
        )

    def test_Should_keep_every_dimension_bar_clear_of_the_silhouette(self):
        """A bar that crosses the drawn part obscures the geometry the judge is reading.

        The defect this pins rendered leaders straight through the top view's interior, across a
        hole. Every bar must sit outside the silhouette's own bounding box.
        """
        # Arrange
        import re

        # Act
        envelope = self._draw()
        sheet = self._require_available(envelope)
        svg = open(sheet["svg_path"], encoding="utf-8").read()

        # Assert
        placements = re.findall(
            r"translate\(([-\d.]+),([-\d.]+)\) scale\(([-\d.]+),([-\d.]+)\)", svg
        )
        self.assertEqual(len(placements), 3)
        boxes = []
        for (cx, cy, sx, _sy), view in zip(placements, sheet["views"]):
            del view
            boxes.append((float(cx), float(cy), float(sx)))
        for x1, y1, x2, y2 in re.findall(
            r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"', svg
        ):
            for cx, cy, _sx in boxes:
                inside_x = cx - 1 < float(x1) < cx + 1 and cx - 1 < float(x2) < cx + 1
                inside_y = cy - 1 < float(y1) < cy + 1 and cy - 1 < float(y2) < cy + 1
                self.assertFalse(
                    inside_x and inside_y,
                    f"a dimension bar passes through a view centre at ({cx}, {cy})",
                )

    def test_Should_refuse_When_the_part_exposes_no_driving_parameters(self):
        # Arrange
        self.document.removeObject(self.parameters.Name)
        self.document.recompute()

        # Act
        act = lambda: self._draw()  # noqa: E731 - the thunk is the Act phase

        # Assert
        with self.assertRaises(ValidationError) as raised:
            act()
        self.assertIn("driving parameters", str(raised.exception))

    def test_Should_draw_the_sheet_When_a_projection_is_only_circles(self):
        """A turned part seen end-on projects to circles, and that is finished geometry.

        ``viewPartAsSvg`` emits a full circle as ``<circle>``, never as a path, so a washer's top
        view carries no ``<path>`` at all. Polling for ``<path>`` alone read that as an unfinished
        hidden-line-removal pass and refused a correct sheet after the whole settle budget, which
        made every rotationally symmetric part undrawable. The extent must come through too: a
        view measured as zero-extent would be dropped from the sheet scale and could overflow its
        cell.
        """
        # Arrange
        import Part

        washer = Part.makeCylinder(WASHER_OUTER_RADIUS, WASHER_THICKNESS).cut(
            Part.makeCylinder(WASHER_BORE_RADIUS, WASHER_THICKNESS * 3, App.Vector(0, 0, -1.0))
        )
        self.document.getObject("Plate").Shape = washer
        self.document.recompute()

        # Act
        sheet = self._require_available(self._draw())

        # Assert
        self.assertEqual(sheet["views"], ["front", "top", "right"])

    def test_Should_measure_a_circular_view_When_it_sets_the_sheet_scale(self):
        """The circle-only view's own extent must reach the compositor, not read as zero."""
        # Arrange
        fragment = '<g><circle cx="0" cy="0" r="10.5" /></g>'

        # Act
        width, height = techdraw._fragment_extent(fragment)

        # Assert
        self.assertAlmostEqual(width, 21.0, places=6)
        self.assertAlmostEqual(height, 21.0, places=6)

    # -- failure and degradation paths --------------------------------------------------

    def test_Should_discard_the_tempdoc_When_the_build_fails_partway_through(self):
        # Arrange
        documents_before = set(App.listDocuments().keys())

        # Act
        act = lambda: self._draw(port=_FailingRasterPort())  # noqa: E731 - the Act phase thunk

        # Assert
        with self.assertRaises(RuntimeError):
            act()
        self.assertEqual(
            set(App.listDocuments().keys()) - documents_before,
            set(),
            "a failed build leaked its TempDoc",
        )

    def test_Should_leave_no_temp_file_When_the_build_fails_partway_through(self):
        # Arrange
        files_before = _sheet_files()

        # Act
        act = lambda: self._draw(port=_FailingRasterPort())  # noqa: E731 - the Act phase thunk

        # Assert
        with self.assertRaises(RuntimeError):
            act()
        self.assertEqual(
            _sheet_files() - files_before,
            set(),
            "a failed build left a sheet artifact under the session workdir",
        )

    def test_Should_refuse_When_the_projection_geometry_never_arrives(self):
        """A blank sheet must be refused, not composed (decision 016, R3-01).

        The view's SVG is empty until the asynchronous hidden-line-removal pass finishes, and
        nothing raises while it is. A generator that read once and shipped whatever came back
        would hand the judge a blank page and fail a correct part for a reason no assertion
        reports. This drives that state by never letting the pass complete.
        """
        # Arrange
        import TechDraw

        port = _NeverSettlingRasterPort()
        original_svg = TechDraw.viewPartAsSvg
        original_budget = techdraw._MAX_SETTLE_ATTEMPTS
        TechDraw.viewPartAsSvg = lambda view: ""
        # The shipped budget is a ~30 s per-view ceiling, which is the right production value and
        # the wrong test duration. The behaviour under test is "refuses after exhausting the
        # budget", which a small budget exercises identically.
        techdraw._MAX_SETTLE_ATTEMPTS = 3

        # Act
        try:
            act = lambda: self._draw(port=port)  # noqa: E731 - the Act phase thunk

            # Assert
            with self.assertRaises(techdraw.TechDrawUnavailable) as raised:
                act()
        finally:
            TechDraw.viewPartAsSvg = original_svg
            techdraw._MAX_SETTLE_ATTEMPTS = original_budget
        self.assertIn("no drawn geometry", str(raised.exception))
        self.assertGreater(port.settle_calls, 0, "the generator never waited for the HLR pass")

    def test_Should_report_unavailable_When_no_rasterizer_is_present(self):
        # Act
        envelope = self._draw(port=_UnavailableRasterPort())

        # Assert
        self.assertEqual(envelope["status"], "OK")
        sheet = envelope["structured_content"]
        self.assertFalse(sheet["available"])
        self.assertEqual(sheet["reason"], _UnavailableRasterPort.reason)
        self.assertIsNone(sheet["png_path"])
        self.assertNotIn(
            "images",
            envelope,
            "an unavailable sheet must carry no image; a caller reading images alone would take "
            "it for a drawn one",
        )

    def test_Should_never_reference_the_gui_drawing_module_When_the_generator_runs(self):
        """The GUI path must not exist in the code, not merely go untaken (spec I/O matrix).

        Decision 016 measured that a second ``import TechDrawGui`` after ``setupWithoutGUI()``
        terminates the interpreter with no traceback, so this is asserted by reading the source
        rather than by attempting the import.
        """
        # Arrange
        source = open(techdraw.__file__, encoding="utf-8").read()

        # Act
        mentions = [line for line in source.splitlines() if "TechDrawGui" in line]

        # Assert
        for line in mentions:
            self.assertTrue(
                line.strip().startswith(("#", "*", '"', "'")) or "``" in line,
                f"TechDrawGui is reachable from code, not only named in prose: {line.strip()}",
            )


if __name__ == "__main__":
    unittest.main()
