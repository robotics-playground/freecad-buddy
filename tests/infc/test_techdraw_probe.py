"""In-FreeCAD probe for the headless TechDraw capability boundary (decision 016).

Story 4.1's spike verdict is a claim about what FreeCAD exposes where: page export lives in the
``TechDrawGui`` module and is unreachable headless, while the ``TechDraw`` App module offers
view-level SVG plus dimension helpers. A prose claim cannot fail when a FreeCAD upgrade moves the
boundary, so the claim is asserted here instead — under ``FreeCADCmd``, against the installed
build, over a known solid whose projection has a known extent.

Runs via ``FreeCADCmd tests/run_tests.py``. ``tests/external`` is pytest and cannot import
FreeCAD, so this probe belongs nowhere else.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import FreeCAD as App
import Part

# A 30 x 20 x 10 block. Projected down -Z its silhouette is the 30 x 20 face, so a projection that
# silently returned an empty or degenerate result cannot pass the extent assertions below.
_BLOCK = (30.0, 20.0, 10.0)

# The three orthographic directions the G3 visual set names (front / top / right).
_VIEW_DIRECTIONS = {
    "front": (0.0, -1.0, 0.0),
    "top": (0.0, 0.0, 1.0),
    "right": (1.0, 0.0, 0.0),
}

# The headless entry points decision 016 rests on, registered in
# docs/references/FreeCAD/src/Mod/TechDraw/App/AppTechDrawPy.cpp.
_REQUIRED_APP_ENTRY_POINTS = (
    "projectToSVG",
    "viewPartAsSvg",
    "makeExtentDim",
    "makeDistanceDim",
)

# ``makeExtentDim`` returns a DrawViewDimExtent, NOT the DrawViewDimension that
# ``makeDistanceDim`` returns — they are separate document object classes. Measured on
# FreeCAD 1.1.1 (Libs 1.1.1R20260414); pinned because 4.3 reads this object's properties.
_EXTENT_DIM_TYPE_ID = "TechDraw::DrawViewDimExtent"
_DISTANCE_DIM_TYPE_ID = "TechDraw::DrawViewDimension"


class HeadlessTechDrawBoundaryTest(unittest.TestCase):
    """Assert the boundary decision 016 records, both halves of it."""

    @classmethod
    def setUpClass(cls):
        cls.block = Part.makeBox(*_BLOCK)

    def test_Should_be_unimportable_When_TechDrawGui_is_requested_in_a_fresh_console(self):
        """``TechDrawGui`` must fail to import in a console process that has loaded nothing else.

        Measured in a FRESH ``FreeCADCmd`` subprocess, not in this one. Whether the import
        succeeds in the current interpreter depends on what ran before it: in a bare process it
        raises ``Cannot load Gui module in console application``, but after the rest of
        ``tests/infc`` has run it succeeds, because something earlier in the suite brings the Gui
        machinery up. An in-process assertion therefore measures test ordering rather than the
        build, and passes or fails depending on which other tests ran.
        """
        # Arrange
        script = (
            "import sys\n"
            "try:\n"
            "    __import__('TechDrawGui')\n"
            "    print('IMPORTED')\n"
            "except ImportError as exc:\n"
            "    print('IMPORT_ERROR:' + str(exc))\n"
        )
        script_path = Path(tempfile.mkdtemp(prefix="fcb-techdraw-probe-")) / "probe.py"
        script_path.write_text(script, encoding="utf-8")

        # Act
        try:
            completed = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=300,
            )
        finally:
            shutil.rmtree(script_path.parent, ignore_errors=True)

        # Assert
        self.assertNotIn(
            "IMPORTED",
            completed.stdout,
            "TechDrawGui imported in a fresh FreeCADCmd process: decision 016 claims page export "
            "is GUI-only, so 4.3 may now call exportPageAsSvg directly — re-open the decision",
        )
        self.assertIn("IMPORT_ERROR:", completed.stdout, completed.stderr)

    def test_Should_register_no_page_exporter_When_the_headless_module_is_inspected(self):
        """The order-independent half of the boundary, and the one 4.3's design rests on.

        Whether ``TechDrawGui`` can be imported in a given process varies with what loaded before
        it. What does not vary is that the headless ``TechDraw`` App module registers no
        ``exportPage*`` name at all (``AppTechDrawPy.cpp:124-171``) — so there is no headless page
        exporter to call however the Gui module behaves.
        """
        # Arrange
        import TechDraw

        # Act
        page_exporters = sorted(name for name in dir(TechDraw) if name.startswith("exportPage"))

        # Assert
        self.assertEqual(
            page_exporters,
            [],
            "the headless TechDraw module now registers a page exporter; 4.3 no longer needs to "
            "compose a page from view-level SVG — re-open decision 016",
        )

    def test_Should_expose_the_headless_entry_points_When_TechDraw_App_module_is_imported(self):
        # Arrange
        import TechDraw

        # Act
        missing = [name for name in _REQUIRED_APP_ENTRY_POINTS if not hasattr(TechDraw, name)]

        # Assert
        self.assertEqual(
            missing,
            [],
            "decision 016 rests on these App-module entry points being present headless",
        )

    def test_Should_produce_non_empty_svg_When_projectToSVG_runs_on_a_known_solid(self):
        # Arrange
        import TechDraw

        # Act
        svgs = {
            view: TechDraw.projectToSVG(self.block, App.Vector(*direction))
            for view, direction in _VIEW_DIRECTIONS.items()
        }

        # Assert
        for view, svg in svgs.items():
            self.assertIsInstance(svg, str, f"{view} projection is not a string")
            self.assertTrue(svg.strip(), f"{view} projection is empty")
            # A projection that drew nothing still returns well-formed wrapper markup, so the
            # presence of a path element is what distinguishes real output from an empty sheet.
            self.assertIn("<path", svg, f"{view} projection carries no path geometry")

    def test_Should_project_the_expected_silhouette_When_the_block_is_viewed_down_Z(self):
        """A non-empty SVG is not enough: the projection must carry the block's real extent."""
        # Arrange
        import TechDraw

        length, width, _height = _BLOCK

        # Act
        visible_g0, _visible_g1, _hidden_g0, _hidden_g1 = TechDraw.project(
            self.block, App.Vector(0.0, 0.0, 1.0)
        )

        # Assert
        bound_box = visible_g0.BoundBox
        self.assertAlmostEqual(bound_box.XLength, length, places=3)
        self.assertAlmostEqual(bound_box.YLength, width, places=3)

    def test_Should_build_a_view_and_dimension_When_the_headless_page_path_is_driven(self):
        """The document-object path: DrawPage + DrawViewPart + a dimension, no GUI involved.

        This is what 4.3 drives for ``viewPartAsSvg`` and the dimension callouts. The page object
        itself is constructible headless — only its *export* is not, which is the distinction
        decision 016 draws.
        """
        # Arrange
        import TechDraw

        document = App.newDocument("techdraw_probe")
        try:
            body = document.addObject("Part::Feature", "Block")
            body.Shape = self.block
            page = document.addObject("TechDraw::DrawPage", "Page")
            template = document.addObject("TechDraw::DrawSVGTemplate", "Template")
            page.Template = template
            view = document.addObject("TechDraw::DrawViewPart", "View")
            view.Source = [body]
            view.Direction = App.Vector(0.0, 0.0, 1.0)
            page.addView(view)
            document.recompute()

            # Act
            svg = TechDraw.viewPartAsSvg(view)
            extent_dim = TechDraw.makeExtentDim(view, [], 0)
            distance_dim = TechDraw.makeDistanceDim(
                view, "DistanceX", App.Vector(0.0, 0.0, 0.0), App.Vector(_BLOCK[0], 0.0, 0.0)
            )
            document.recompute()

            # Assert
            self.assertTrue(svg.strip(), "viewPartAsSvg returned nothing for a built view")
            self.assertEqual(
                str(getattr(extent_dim, "TypeId", "")),
                _EXTENT_DIM_TYPE_ID,
                "makeExtentDim did not produce the extent-dimension object 4.3 annotates with",
            )
            self.assertEqual(
                str(getattr(distance_dim, "TypeId", "")),
                _DISTANCE_DIM_TYPE_ID,
                "makeDistanceDim did not produce the dimension object 4.3 annotates with",
            )
        finally:
            App.closeDocument(document.Name)


if __name__ == "__main__":
    unittest.main()
