"""In-FreeCAD view-controlled screenshot tests (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py`` on the render CI leg (xvfb + software GL). Proves the
real ``OffscreenRenderPort``: a known box renders to a non-empty PNG, the document fingerprint is
unchanged (read-only), include/exclude/focus are honored, and — the loop-2 regression — a
screenshot of document A's handle renders A's objects even while an empty document B is the
``ActiveDocument`` (the port renders the passed handle, never ``ActiveDocument``). GL-requiring
assertions are skip-guarded when the render ladder reports ``none``.
"""

import math
import os
import tempfile
import unittest

import FreeCAD as App

from freecad_buddy.adapters import render_probe
from freecad_buddy.adapters.render_probe import OffscreenRenderPort, render_capability
from freecad_buddy.contracts import massprops_equal
from freecad_buddy.contracts.render import SceneSpec, StyleSpec
from freecad_buddy.usecases import framing, screenshot
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
from freecad_buddy.usecases.fingerprint import fingerprint
from freecad_buddy.usecases.render_tone import verify_render_tone

BOX_L = 10.0
BOX_W = 20.0
BOX_H = 30.0


def _render_available() -> bool:
    return render_capability()[0] != "none"


class ScreenshotTest(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.port = OffscreenRenderPort()
        self.handle = self.registry.document_create("screenshot")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))
        self.box = self.document.addObject("Part::Box", "Box")
        self.box.Length = BOX_L
        self.box.Width = BOX_W
        self.box.Height = BOX_H
        self.document.recompute()

    def _close_all(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def tearDown(self):
        self._close_all()

    def _shot(self, handle=None, view=None):
        return screenshot.query_screenshot(
            self.registry, self.port, doc=handle or self.handle, view=view
        )

    def test_render_unavailable_reports_available_false_with_reason(self):
        if _render_available():
            self.skipTest("render context present; unavailable path not exercised")
        envelope = self._shot()
        self.assertEqual(envelope["status"], "OK")
        render = envelope["structured_content"]["render"]
        self.assertFalse(render["available"])
        self.assertIsNotNone(render["reason"])
        self.assertNotIn("images", envelope)

    def test_known_box_renders_non_empty_png(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        envelope = self._shot()
        self.assertEqual(envelope["status"], "OK")
        link = envelope["structured_content"]["render"]["resource_link"]
        self.assertTrue(os.path.exists(link))
        self.assertGreater(os.path.getsize(link), 0)
        self.assertIn("Box", envelope["structured_content"]["scene"]["rendered_objects"])
        os.remove(link)

    def test_render_is_read_only_fingerprint_unchanged(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        before = fingerprint(self.document)
        envelope = self._shot()
        after = fingerprint(self.document)
        self.assertEqual(envelope["status"], "OK")
        # OCCT re-serializes a loaded shape's BRep bytes the first time a render touches it, so the
        # raw digest legitimately shifts while the geometry is unchanged; assert the geometric
        # invariants (the same read-only contract the render use case enforces), not the digest.
        self.assertTrue(massprops_equal(before, after))
        link = envelope["structured_content"]["render"].get("resource_link")
        if link and os.path.exists(link):
            os.remove(link)

    def test_include_exclude_honored(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        other = self.document.addObject("Part::Box", "Other")
        other.Length = 5.0
        self.document.recompute()
        envelope = self._shot(view={"include": ["Box"]})
        rendered = envelope["structured_content"]["scene"]["rendered_objects"]
        self.assertEqual(rendered, ["Box"])

    def test_default_set_honors_visibility(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        hidden = self.document.addObject("Part::Box", "Hidden")
        hidden.Length = 5.0
        self.document.recompute()
        hidden.Visibility = False
        # default set (no include) omits the hidden object...
        default_rendered = self._shot()["structured_content"]["scene"]["rendered_objects"]
        self.assertIn("Box", default_rendered)
        self.assertNotIn("Hidden", default_rendered)
        # ...but an explicit include still renders it.
        included = self._shot(view={"include": ["Hidden"]})["structured_content"]["scene"][
            "rendered_objects"
        ]
        self.assertEqual(included, ["Hidden"])

    def test_focus_frames_a_face(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        envelope = self._shot(view={"focus": {"object": "Box", "element_type": "face", "index": 0}})
        self.assertEqual(envelope["status"], "OK")
        focused_on = envelope["structured_content"]["scene"]["focused_on"]
        self.assertEqual(focused_on["object"], "Box")
        link = envelope["structured_content"]["render"].get("resource_link")
        if link and os.path.exists(link):
            os.remove(link)

    def test_multi_document_renders_passed_handle_not_active_document(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        # Open an empty document B AFTER A so B is the ActiveDocument.
        empty = self.registry.document_create("screenshot_empty")
        empty_handle = empty["structured_content"]["doc"]
        _, doc_b = self.registry.with_document(empty_handle, lambda h, d: (h, d))
        App.setActiveDocument(doc_b.Name)
        self.assertIs(App.ActiveDocument, doc_b)

        envelope = self._shot(handle=self.handle)  # A's handle, while B is active
        self.assertEqual(envelope["status"], "OK")
        rendered = envelope["structured_content"]["scene"]["rendered_objects"]
        self.assertIn("Box", rendered)  # A's object, proving the passed handle was rendered
        link = envelope["structured_content"]["render"].get("resource_link")
        if link and os.path.exists(link):
            os.remove(link)

    def test_dirty_document_renders_with_note_not_error(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        # Build a genuinely broken-recompute object: a Part::Cut whose Tool is removed leaves the
        # Cut perpetually in error (a linked-object break, like a dangling Joint reference). Such a
        # document is self-unstable — fingerprint()'s .Shape read re-triggers the failing recompute,
        # so two consecutive fingerprints differ on their own with no render between, and the strict
        # before==after guard would misread that churn as a render mutation. A dirty doc must still
        # render (with a note), not hard-error.
        base = self.document.addObject("Part::Box", "CutBase")
        tool = self.document.addObject("Part::Box", "CutTool")
        tool.Placement.Base.z = 5.0
        cut = self.document.addObject("Part::Cut", "Cut")
        cut.Base = base
        cut.Tool = tool
        self.document.recompute()
        self.document.removeObject(tool.Name)  # Cut now references a removed Tool -> broken
        envelope = self._shot(view={"include": ["Box"]})
        self.assertEqual(envelope["status"], "OK")
        self.assertTrue(envelope["structured_content"]["render"]["dirty_document"])
        link = envelope["structured_content"]["render"]["resource_link"]
        self.assertTrue(link and os.path.getsize(link) > 0)
        os.remove(link)

    def test_clean_document_reports_not_dirty(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        envelope = self._shot()
        self.assertEqual(envelope["status"], "OK")
        self.assertFalse(envelope["structured_content"]["render"]["dirty_document"])
        link = envelope["structured_content"]["render"].get("resource_link")
        if link and os.path.exists(link):
            os.remove(link)

    def test_partdesign_default_render_skips_body_and_datum(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        import Part

        body = self.document.addObject("PartDesign::Body", "Body")
        sketch = body.newObject("Sketcher::SketchObject", "PadSketch")
        for start, end in (
            ((0, 0, 0), (10, 0, 0)),
            ((10, 0, 0), (10, 10, 0)),
            ((10, 10, 0), (0, 10, 0)),
            ((0, 10, 0), (0, 0, 0)),
        ):
            sketch.addGeometry(
                Part.LineSegment(App.Vector(*start), App.Vector(*end)), False
            )
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = sketch
        pad.Length = 5.0
        self.document.recompute()

        # A default render must render the Pad while skipping the Body container and the origin
        # datum features, whose headless Coin subgraph faults and corrupts the renderer.
        envelope = self._shot()
        self.assertEqual(envelope["status"], "OK")
        rendered = envelope["structured_content"]["scene"]["rendered_objects"]
        self.assertIn("Pad", rendered)
        self.assertNotIn("Body", rendered)
        self.assertFalse(any(name.startswith(("X_Axis", "Y_Axis", "Z_Axis")) for name in rendered))
        link = envelope["structured_content"]["render"].get("resource_link")
        self.assertTrue(link and os.path.getsize(link) > 0)
        os.remove(link)

    def test_should_draw_the_tip_under_the_body_name_when_include_names_a_body(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        # Arrange
        _padded_body(self.document)
        view = {"include": ["Body"], "width": 200, "height": 200}

        # Act
        envelope = self._shot(view=view)

        # Assert
        render = envelope["structured_content"]["render"]
        self.assertEqual(envelope["structured_content"]["scene"]["rendered_objects"], ["Body"])
        self.assertFalse(render["empty_scene"])
        self.assertGreater(_drawn_pixels(render["resource_link"]), 1000, "the Body PNG is blank")
        os.remove(render["resource_link"])

    def test_should_paint_the_tip_with_the_accent_when_the_highlight_names_the_included_body(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        from PySide import QtGui

        # Arrange
        _padded_body(self.document)
        view = {"include": ["Body"], "highlight": {"object": "Body"}, "width": 200, "height": 200}

        # Act
        envelope = self._shot(view=view)

        # Assert
        link = envelope["structured_content"]["render"]["resource_link"]
        self.addCleanup(os.remove, link)
        color = QtGui.QImage(link).pixelColor(100, 100)
        red, blue = color.red(), color.blue()
        self.assertGreater(red, blue + 40, f"the Tip is not accent-hued: {(red, blue)}")

    def test_should_report_an_empty_scene_when_the_included_body_has_no_tip(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        # Arrange
        self.document.addObject("PartDesign::Body", "Body")
        self.document.recompute()

        # Act
        envelope = self._shot(view={"include": ["Body"]})

        # Assert
        render = envelope["structured_content"]["render"]
        self.assertTrue(render["empty_scene"])
        self.assertIsNone(render["resource_link"])
        self.assertEqual(envelope["structured_content"]["scene"]["rendered_objects"], [])

    def test_should_report_an_empty_scene_when_every_included_subgraph_is_empty(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        # Arrange: a sketch with no geometry builds a subgraph with an empty bounding box.
        self.document.addObject("Sketcher::SketchObject", "EmptySketch")
        self.document.recompute()

        # Act
        envelope = self._shot(view={"include": ["EmptySketch"]})

        # Assert
        render = envelope["structured_content"]["render"]
        self.assertTrue(render["empty_scene"])
        self.assertIsNone(render["resource_link"])
        self.assertNotIn("images", envelope)
        self.assertEqual(envelope["structured_content"]["scene"]["rendered_objects"], [])

    def test_should_leave_a_hidden_object_hidden_when_an_include_renders_it(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        # Arrange
        self.box.Visibility = False

        # Act
        envelope = self._shot(view={"include": ["Box"]})

        # Assert
        self.assertEqual(envelope["structured_content"]["scene"]["rendered_objects"], ["Box"])
        self.assertFalse(self.box.Visibility, "the render un-hid the live object")
        os.remove(envelope["structured_content"]["render"]["resource_link"])

    def test_should_restore_visibility_when_the_render_raises_after_building_a_subgraph(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        import FreeCADGui

        # Arrange: the real call un-hides the object, then the render fails.
        self.box.Visibility = False
        real = FreeCADGui.subgraphFromObject

        def build_then_fail(obj):
            real(obj)
            raise RuntimeError("planted render failure")

        FreeCADGui.subgraphFromObject = build_then_fail
        self.addCleanup(setattr, FreeCADGui, "subgraphFromObject", real)
        scene = SceneSpec(
            objects=["Box"], orientation=screenshot._CAMERA_QUATS["iso"], width=64, height=64
        )
        handle, path = tempfile.mkstemp(suffix=".png")
        os.close(handle)
        self.addCleanup(os.remove, path)

        # Act
        with self.assertRaises(RuntimeError):
            self.port.render(self.document, scene, path)

        # Assert
        self.assertFalse(self.box.Visibility, "a raising render left the live object un-hidden")


def _padded_body(document):
    """A ``PartDesign::Body`` whose Tip is a 10x10x5 pad, plus a datum plane beside it."""
    body = document.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "PadSketch")
    _add_square(sketch)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = 5.0
    body.newObject("PartDesign::Plane", "DatumPlane")
    document.recompute()
    return body


def _add_square(sketch, size=10.0):
    """Add a closed ``size`` square of line segments to ``sketch``."""
    import Part

    corners = ((0, 0, 0), (size, 0, 0), (size, size, 0), (0, size, 0))
    for index, start in enumerate(corners):
        end = corners[(index + 1) % len(corners)]
        sketch.addGeometry(Part.LineSegment(App.Vector(*start), App.Vector(*end)), False)


def _drawn_pixels(path):
    """How many pixels of the PNG at ``path`` differ from its top-left (background) pixel."""
    from PySide import QtGui

    image = QtGui.QImage(path)
    background = image.pixel(0, 0)
    return sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if image.pixel(x, y) != background
    )


_SKETCH_EDGE_COLOR_KEY = "SketchEdgeColor"
_WHITE = 0xFFFFFFFF
_SKETCH_LINE_RGB = (0x21, 0x25, 0x29)


def _pixel(path, x, y):
    """The packed RGB value of pixel (``x``, ``y``) in the PNG at ``path``."""
    from PySide import QtGui

    return QtGui.QImage(path).pixel(x, y)


def _pixels_of(path, rgb):
    """How many pixels of the PNG at ``path`` are exactly the color ``rgb``."""
    from PySide import QtGui

    image = QtGui.QImage(path)
    wanted = QtGui.QColor(*rgb).rgb()
    return sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if image.pixel(x, y) == wanted
    )


class DefaultSetTest(unittest.TestCase):
    """The default (no-``include``) set draws visible sketches and meshes, never datums."""

    def setUp(self):
        self.registry = DocumentRegistry()
        self.port = OffscreenRenderPort()
        self.handle = self.registry.document_create("screenshot_default")["structured_content"][
            "doc"
        ]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _shot(self, **view):
        return screenshot.query_screenshot(
            self.registry,
            self.port,
            doc=self.handle,
            view={"width": 200, "height": 200, **view},
        )

    def test_should_draw_a_visible_sketch_when_it_is_the_only_object(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        # Arrange: FreeCAD's default sketch edge color, white on the white render background.
        _pin_view_color(self, _SKETCH_EDGE_COLOR_KEY, _WHITE)
        _add_square(self.document.addObject("Sketcher::SketchObject", "Sketch"))
        self.document.recompute()

        # Act
        envelope = self._shot()

        # Assert
        render = envelope["structured_content"]["render"]
        self.addCleanup(os.remove, render["resource_link"])
        self.assertEqual(envelope["structured_content"]["scene"]["rendered_objects"], ["Sketch"])
        self.assertFalse(render["empty_scene"])
        self.assertGreater(
            _pixels_of(render["resource_link"], _SKETCH_LINE_RGB), 0, "no #212529 sketch line"
        )
        # The camera frames the square's bbox, so its centre is the image centre.
        self.assertEqual(
            _pixel(render["resource_link"], 100, 100),
            _pixel(render["resource_link"], 0, 0),
            "the closed sketch's inside is filled",
        )

    def test_should_draw_the_style_color_when_a_style_colors_the_sketch(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        # Arrange
        _pin_view_color(self, _SKETCH_EDGE_COLOR_KEY, _WHITE)
        _add_square(self.document.addObject("Sketcher::SketchObject", "Sketch"))
        self.document.recompute()
        styles = [{"object": "Sketch", "color": [1.0, 0.0, 0.0]}]

        # Act
        envelope = self._shot(styles=styles)

        # Assert
        link = envelope["structured_content"]["render"]["resource_link"]
        self.addCleanup(os.remove, link)
        self.assertGreater(_pixels_of(link, (255, 0, 0)), 0, "no red sketch line")
        self.assertEqual(_pixels_of(link, _SKETCH_LINE_RGB), 0, "the fixed color beat the style")

    def test_should_leave_out_a_hidden_sketch_when_the_default_set_is_built(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        # Arrange
        sketch = self.document.addObject("Sketcher::SketchObject", "Sketch")
        _add_square(sketch)
        box = self.document.addObject("Part::Box", "Box")
        self.document.recompute()
        sketch.Visibility = False

        # Act
        envelope = self._shot()

        # Assert
        self.assertEqual(envelope["structured_content"]["scene"]["rendered_objects"], [box.Name])
        os.remove(envelope["structured_content"]["render"]["resource_link"])

    def test_should_draw_a_mesh_when_it_is_the_only_object(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        import Mesh

        # Arrange
        mesh = self.document.addObject("Mesh::Feature", "Mesh")
        mesh.Mesh = Mesh.createBox(10.0, 20.0, 30.0)
        self.document.recompute()

        # Act
        envelope = self._shot()

        # Assert
        render = envelope["structured_content"]["render"]
        self.assertEqual(envelope["structured_content"]["scene"]["rendered_objects"], ["Mesh"])
        self.assertGreater(_drawn_pixels(render["resource_link"]), 1000, "the mesh PNG is blank")
        os.remove(render["resource_link"])

    def test_should_leave_out_every_datum_flavour_when_it_derives_from_a_datum_base(self):
        # Arrange
        body = self.document.addObject("PartDesign::Body", "Body")
        datums = [
            self.document.addObject("Part::DatumPlane", "PartPlane"),
            body.newObject("PartDesign::Line", "DatumLine"),
            body.newObject("PartDesign::Point", "DatumPoint"),
            body.newObject("PartDesign::CoordinateSystem", "DatumCS"),
        ]
        self.document.recompute()

        # Act
        renderable = {obj.TypeId: screenshot.is_default_renderable(obj) for obj in datums}

        # Assert
        self.assertEqual(
            renderable,
            {
                "Part::DatumPlane": False,
                "PartDesign::Line": False,
                "PartDesign::Point": False,
                "PartDesign::CoordinateSystem": False,
            },
        )

    def test_should_measure_and_draw_only_the_pad_when_a_datum_plane_shares_the_body(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        # Arrange
        _padded_body(self.document)
        self.document.getObject("PadSketch").Visibility = False

        # Act
        measured = framing.union_bbox(
            [obj for obj in self.document.Objects if screenshot.is_default_renderable(obj)]
        )
        envelope = self._shot()

        # Assert
        for actual, expected in zip(measured, (0.0, 0.0, 0.0, 10.0, 10.0, 5.0)):
            self.assertAlmostEqual(actual, expected, places=4, msg=f"measured {measured}")
        self.assertEqual(envelope["structured_content"]["scene"]["rendered_objects"], ["Pad"])
        os.remove(envelope["structured_content"]["render"]["resource_link"])


class EmptySceneTest(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.port = OffscreenRenderPort()
        handle = self.registry.document_create("screenshot_empty_scene")
        self.handle = handle["structured_content"]["doc"]

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def test_empty_document_reports_empty_scene_without_an_image(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        before = set(_temp_shot_files())
        envelope = screenshot.query_screenshot(self.registry, self.port, doc=self.handle)

        self.assertEqual(envelope["status"], "OK")
        render = envelope["structured_content"]["render"]
        self.assertTrue(render["empty_scene"])
        self.assertIsNone(render["resource_link"])
        self.assertEqual(envelope["structured_content"]["scene"]["rendered_objects"], [])
        # A blank PNG would still be a PNG; the contract is that no image is produced at all.
        self.assertNotIn("images", envelope)
        self.assertEqual(set(_temp_shot_files()) - before, set())

    def test_populated_document_is_not_an_empty_scene(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        _, document = self.registry.with_document(self.handle, lambda h, d: (h, d))
        box = document.addObject("Part::Box", "Box")
        box.Length, box.Width, box.Height = BOX_L, BOX_W, BOX_H
        document.recompute()

        envelope = screenshot.query_screenshot(self.registry, self.port, doc=self.handle)
        render = envelope["structured_content"]["render"]
        self.assertFalse(render["empty_scene"])
        self.assertIn("images", envelope)
        self.assertTrue(os.path.getsize(render["resource_link"]) > 0)
        os.remove(render["resource_link"])


def _temp_shot_files():
    """The screenshot temp PNGs currently on disk, so a leaked file is detectable."""
    directory = tempfile.gettempdir()
    try:
        return [name for name in os.listdir(directory) if name.startswith("FCB_TMP_shot_")]
    except OSError:
        return []


_ROOT = math.sqrt(2.0) / 2.0

# Expected camera quaternions (x, y, z, w) transcribed from FreeCAD's ``src/Gui/Camera.cpp``.
_CAMERA_CPP_QUATS = {
    "iso": (0.424708, 0.17592, 0.339851, 0.820473),
    "front": (_ROOT, 0.0, 0.0, _ROOT),
    "top": (0.0, 0.0, 0.0, 1.0),
    "bottom": (1.0, 0.0, 0.0, 0.0),
    "right": (0.5, 0.5, 0.5, 0.5),
    "left": (-0.5, 0.5, 0.5, -0.5),
    "back": (0.0, _ROOT, _ROOT, 0.0),
}

_SQUARED_TOLERANCE = 1e-6


def _normalized(quat):
    """Scale ``quat`` to unit length so the squared-distance metric measures rotation alone."""
    norm = math.sqrt(sum(component * component for component in quat))
    return tuple(component / norm for component in quat)


def _same_rotation(lhs, rhs, tolerance=_SQUARED_TOLERANCE):
    """Whether two quaternions encode the same rotation, ignoring sign (q and -q).

    Mirrors ``Camera::rotationsMatch`` -- the squared distance ``2 * (1 - |dot|)`` must be within
    ``tolerance`` -- but normalizes first, because that identity measures rotation only for unit
    quaternions and the stored presets are 6-decimal roundings.
    """
    lhs, rhs = _normalized(lhs), _normalized(rhs)
    dot = sum(a * b for a, b in zip(lhs, rhs))
    return 2.0 * (1.0 - abs(dot)) <= tolerance


def _aligned(lhs, rhs):
    """Return ``rhs`` negated when that is the sign closer to ``lhs``, so components compare.

    At ``dot == 0`` the two are orthogonal and neither sign is closer; the un-negated ``rhs`` is
    returned and the caller's component assertion reports the mismatch.
    """
    dot = sum(a * b for a, b in zip(lhs, rhs))
    return rhs if dot >= 0.0 else tuple(-component for component in rhs)


class CameraPresetTest(unittest.TestCase):
    def test_every_preset_matches_camera_cpp(self):
        self.assertEqual(set(screenshot._CAMERA_QUATS), set(_CAMERA_CPP_QUATS))
        for preset, expected in _CAMERA_CPP_QUATS.items():
            actual = screenshot._CAMERA_QUATS[preset]
            self.assertTrue(
                _same_rotation(actual, expected),
                f"camera preset {preset!r} is {actual}, expected {expected} (up to sign)",
            )

    def test_every_preset_is_a_unit_quaternion(self):
        for preset, quat in screenshot._CAMERA_QUATS.items():
            self.assertEqual(len(quat), 4, f"camera preset {preset!r} is not 4 components: {quat}")
            norm = math.sqrt(sum(component * component for component in quat))
            self.assertAlmostEqual(norm, 1.0, places=5, msg=f"preset {preset!r} norm is {norm}")

    def test_every_preset_component_matches_camera_cpp(self):
        """Catch digit-level transcription drift that is too small to move the rotation."""
        for preset, expected in _CAMERA_CPP_QUATS.items():
            actual = screenshot._CAMERA_QUATS[preset]
            self.assertEqual(
                len(actual), len(expected), f"camera preset {preset!r} has wrong arity"
            )
            for index, (component, want) in enumerate(zip(actual, _aligned(actual, expected))):
                self.assertAlmostEqual(
                    component,
                    want,
                    places=6,
                    msg=f"camera preset {preset!r} component {index} is {component}, "
                    f"expected {want}",
                )

    def test_presets_are_pairwise_distinct_rotations(self):
        presets = sorted(screenshot._CAMERA_QUATS)
        for i, left in enumerate(presets):
            for right in presets[i + 1 :]:
                self.assertFalse(
                    _same_rotation(screenshot._CAMERA_QUATS[left], screenshot._CAMERA_QUATS[right]),
                    f"camera presets {left!r} and {right!r} encode the same rotation",
                )

    def test_front_and_right_resolve_to_different_orientations(self):
        front = screenshot._orientation({"camera": "front"})
        right = screenshot._orientation({"camera": "right"})
        self.assertFalse(_same_rotation(front, right))

    def test_default_camera_is_isometric(self):
        self.assertTrue(_same_rotation(screenshot._orientation({}), _CAMERA_CPP_QUATS["iso"]))

    def test_unknown_preset_rejected(self):
        with self.assertRaises(ValidationError):
            screenshot._orientation({"camera": "bogus"})


_VIEWPORTS = ((1920, 1920), (1920, 1080), (1080, 1920))

# Camera quaternions used to frame from several directions; the framing must hold for each.
_FRAMING_ORIENTATIONS = {
    "top": (0.0, 0.0, 0.0, 1.0),
    "front": (_ROOT, 0.0, 0.0, _ROOT),
    "iso": (0.424708, 0.17592, 0.339851, 0.820473),
}

# The bbox must span 1/1.2 of the frame along whichever axis binds: the ~20% margin _frame_bbox
# promises. Derived from the grow factor, not captured from the implementation.
_EXPECTED_OCCUPANCY = 1.0 / 1.2


def _framed_occupancy(orientation, bbox, width, height):
    """Frame ``bbox`` and return its (u, v) extents in normalized screen space.

    Projecting the framed corners back through the camera's own view volume measures what the
    image actually shows, so a camera that over-zooms, under-zooms, or clips is visible here --
    which asserting the raw ``height`` field alone cannot detect.
    """
    from pivy import coin

    camera = coin.SoOrthographicCamera()
    camera.orientation.setValue(coin.SbRotation(*orientation))
    viewport = coin.SbViewportRegion(width, height)
    render_probe._frame_bbox(coin, camera, bbox, viewport)

    volume = camera.getViewVolume(width / height)
    us, vs = [], []
    for x in (bbox.XMin, bbox.XMax):
        for y in (bbox.YMin, bbox.YMax):
            for z in (bbox.ZMin, bbox.ZMax):
                screen = volume.projectToScreen(coin.SbVec3f(x, y, z))
                u, v, _ = screen.getValue()
                us.append(u)
                vs.append(v)
    return (max(us) - min(us)), (max(vs) - min(vs)), camera


def _bound_box(xmin, ymin, zmin, xmax, ymax, zmax):
    return App.BoundBox(xmin, ymin, zmin, xmax, ymax, zmax)


class FocusFramingTest(unittest.TestCase):
    """``_frame_bbox`` must leave the requested margin, on every orientation and viewport.

    Pure Coin math -- no rasterization -- so these run on a leg with no render capability.
    """

    def test_bbox_fills_the_requested_fraction_of_the_frame(self):
        bbox = _bound_box(0.0, 0.0, 0.0, BOX_L, BOX_W, BOX_H)
        for width, height in _VIEWPORTS:
            for name, orientation in _FRAMING_ORIENTATIONS.items():
                span_u, span_v, _ = _framed_occupancy(orientation, bbox, width, height)
                self.assertAlmostEqual(
                    max(span_u, span_v),
                    _EXPECTED_OCCUPANCY,
                    places=3,
                    msg=f"{name} at {width}x{height} spans {max(span_u, span_v)}, "
                    f"expected {_EXPECTED_OCCUPANCY}",
                )

    def test_framing_never_clips_the_bbox(self):
        """No corner may fall outside the frame -- the proxy-cube framing clipped on iso views."""
        bbox = _bound_box(0.0, 0.0, 0.0, BOX_L, BOX_W, BOX_H)
        for width, height in _VIEWPORTS:
            for name, orientation in _FRAMING_ORIENTATIONS.items():
                span_u, span_v, _ = _framed_occupancy(orientation, bbox, width, height)
                self.assertLessEqual(
                    max(span_u, span_v), 1.0, f"{name} at {width}x{height} clips the bbox"
                )

    def test_framing_is_translation_invariant(self):
        """An off-origin bbox frames exactly as the same box at the origin."""
        at_origin = _bound_box(0.0, 0.0, 0.0, BOX_L, BOX_W, BOX_H)
        offset = _bound_box(100.0, -50.0, 5.0, 100.0 + BOX_L, -50.0 + BOX_W, 5.0 + BOX_H)
        for name, orientation in _FRAMING_ORIENTATIONS.items():
            _, _, origin_camera = _framed_occupancy(orientation, at_origin, 1920, 1920)
            _, _, offset_camera = _framed_occupancy(orientation, offset, 1920, 1920)
            self.assertAlmostEqual(
                origin_camera.height.getValue(),
                offset_camera.height.getValue(),
                places=4,
                msg=f"{name} framing depends on bbox position",
            )

    def test_framing_varies_with_orientation(self):
        """A sphere-based framing is orientation-invariant; a projected one is not."""
        bbox = _bound_box(0.0, 0.0, 0.0, BOX_L, BOX_W, BOX_H)
        heights = {
            name: _framed_occupancy(orientation, bbox, 1920, 1920)[2].height.getValue()
            for name, orientation in _FRAMING_ORIENTATIONS.items()
        }
        self.assertNotAlmostEqual(
            heights["top"],
            heights["front"],
            places=3,
            msg=f"framing ignores orientation (sphere circumscription?): {heights}",
        )

    def test_top_view_height_is_the_grown_in_plane_extent(self):
        """Looking down -Z at a 10x20x30 box, the binding extent is the 20 mm Y span."""
        bbox = _bound_box(0.0, 0.0, 0.0, BOX_L, BOX_W, BOX_H)
        _, _, camera = _framed_occupancy(_FRAMING_ORIENTATIONS["top"], bbox, 1920, 1920)
        self.assertAlmostEqual(camera.height.getValue(), BOX_W * 1.2, places=3)

    def test_flat_bbox_frames_its_two_real_axes(self):
        """A zero-thickness face still frames tightly, with no NaN from the degenerate axis."""
        bbox = _bound_box(0.0, 0.0, 0.0, BOX_L, BOX_W, 0.0)
        span_u, span_v, camera = _framed_occupancy(_FRAMING_ORIENTATIONS["top"], bbox, 1920, 1920)
        self.assertAlmostEqual(max(span_u, span_v), _EXPECTED_OCCUPANCY, places=3)
        self.assertTrue(math.isfinite(camera.height.getValue()))

    def test_degenerate_bbox_keeps_a_positive_finite_height(self):
        """An edge seen end-on projects to nothing; the clamp must keep the camera valid."""
        bbox = _bound_box(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        _, _, camera = _framed_occupancy(_FRAMING_ORIENTATIONS["top"], bbox, 1920, 1920)
        value = camera.height.getValue()
        self.assertTrue(math.isfinite(value))
        self.assertGreaterEqual(value, 1e-3)
        self.assertGreater(camera.farDistance.getValue(), camera.nearDistance.getValue())


_STYLE_COLOR = (0.1, 0.2, 0.3)
_STYLE_TRANSPARENCY = 0.8
_COIN_DEFAULT_TRANSPARENCY = 0.0


def _wrapped_material(style, is_highlight, base_color=None):
    """Call ``_wrap_style`` on a bare subgraph and read back the prepended material.

    Returns ``(wrapped, diffuse, transparency, is_override)`` where ``wrapped`` says whether a
    separator was added; the three material values are ``None`` when the subgraph came back
    unwrapped. The values are copied out while the wrapper is still referenced, because a Coin node
    whose only owner is a dropped parent is freed with it.
    """
    from pivy import coin

    subgraph = coin.SoSeparator()
    result = render_probe._wrap_style(coin, subgraph, style, is_highlight, base_color)
    if result is subgraph:
        return False, None, None, None
    material = result.getChild(0)
    return (
        True,
        material.diffuseColor.getValues()[0].getValue(),
        material.transparency.getValues()[0],
        bool(material.isOverride()),
    )


def _ignored_fields(style, is_highlight):
    """The names of the prepended material's fields that ``_wrap_style`` marked ignored."""
    from pivy import coin

    result = render_probe._wrap_style(coin, coin.SoSeparator(), style, is_highlight)
    material = result.getChild(0)
    return {name for name in render_probe._MATERIAL_FIELDS if getattr(material, name).isIgnored()}


class WrapStyleTest(unittest.TestCase):
    """``_wrap_style`` composes the highlight accent with the requested style transparency.

    Pure Coin node manipulation -- no rasterization -- so these run on a leg with no render
    capability.
    """

    def _assert_diffuse(self, actual, expected):
        self.assertEqual(len(actual), len(expected), f"diffuse arity {actual}")
        for index, (component, want) in enumerate(zip(actual, expected)):
            self.assertAlmostEqual(
                component, want, places=5, msg=f"diffuse component {index} is {component}"
            )

    def test_styled_and_highlighted_keeps_accent_hue_and_style_transparency(self):
        style = StyleSpec(object="Box", color=_STYLE_COLOR, transparency=_STYLE_TRANSPARENCY)
        wrapped, diffuse, transparency, is_override = _wrapped_material(style, True)
        self.assertTrue(wrapped)
        self._assert_diffuse(diffuse, render_probe._ACCENT_COLOR)
        self.assertAlmostEqual(transparency, _STYLE_TRANSPARENCY, places=5)
        self.assertTrue(is_override)

    def test_highlighted_with_transparency_only_style(self):
        style = StyleSpec(object="Box", transparency=0.5)
        wrapped, diffuse, transparency, _ = _wrapped_material(style, True)
        self.assertTrue(wrapped)
        self._assert_diffuse(diffuse, render_probe._ACCENT_COLOR)
        self.assertAlmostEqual(transparency, 0.5, places=5)

    def test_highlighted_without_style_uses_accent_and_default_transparency(self):
        wrapped, diffuse, transparency, _ = _wrapped_material(None, True)
        self.assertTrue(wrapped)
        self._assert_diffuse(diffuse, render_probe._ACCENT_COLOR)
        self.assertAlmostEqual(transparency, _COIN_DEFAULT_TRANSPARENCY, places=5)

    def test_styled_only_uses_the_style_color_and_transparency(self):
        style = StyleSpec(object="Box", color=_STYLE_COLOR, transparency=_STYLE_TRANSPARENCY)
        wrapped, diffuse, transparency, is_override = _wrapped_material(style, False)
        self.assertTrue(wrapped)
        self._assert_diffuse(diffuse, _STYLE_COLOR)
        self.assertAlmostEqual(transparency, _STYLE_TRANSPARENCY, places=5)
        self.assertTrue(is_override)

    def test_should_override_only_transparency_when_the_style_has_no_color(self):
        # Arrange
        style = StyleSpec(object="Box", transparency=0.5)

        # Act
        wrapped, _, transparency, is_override = _wrapped_material(style, False)
        ignored = _ignored_fields(style, False)

        # Assert
        self.assertTrue(wrapped)
        self.assertAlmostEqual(transparency, 0.5, places=5)
        self.assertTrue(is_override, "a material that does not override loses to the object's own")
        self.assertIn("diffuseColor", ignored, "an unwritten diffuse would force Coin's grey")
        self.assertNotIn("transparency", ignored)

    def test_should_ignore_transparency_when_the_style_sets_only_a_color(self):
        # Arrange
        style = StyleSpec(object="Box", color=_STYLE_COLOR)

        # Act
        ignored = _ignored_fields(style, False)

        # Assert
        self.assertIn("transparency", ignored, "an unwritten transparency would force opaque")
        self.assertNotIn("diffuseColor", ignored)

    def test_should_ignore_every_field_but_the_accent_when_only_highlighted(self):
        # Act
        ignored = _ignored_fields(None, True)

        # Assert
        self.assertEqual(ignored, set(render_probe._MATERIAL_FIELDS) - {"diffuseColor"})

    def test_color_only_style_leaves_transparency_at_the_coin_default(self):
        style = StyleSpec(object="Box", color=_STYLE_COLOR)
        wrapped, diffuse, transparency, _ = _wrapped_material(style, False)
        self.assertTrue(wrapped)
        self._assert_diffuse(diffuse, _STYLE_COLOR)
        self.assertAlmostEqual(transparency, _COIN_DEFAULT_TRANSPARENCY, places=5)

    def test_no_style_and_no_highlight_returns_the_subgraph_unwrapped(self):
        self.assertFalse(_wrapped_material(None, False)[0])

    def test_empty_style_on_a_plain_object_returns_the_subgraph_unwrapped(self):
        self.assertFalse(_wrapped_material(StyleSpec(object="Box"), False)[0])

    def test_should_override_with_the_base_color_when_there_is_no_style_or_highlight(self):
        # Act
        wrapped, diffuse, _, is_override = _wrapped_material(None, False, _BASE_COLOR)

        # Assert
        self.assertTrue(wrapped)
        self._assert_diffuse(diffuse, _BASE_COLOR)
        self.assertTrue(is_override)

    def test_should_use_the_style_color_when_a_style_color_meets_a_base_color(self):
        # Arrange
        style = StyleSpec(object="Sketch", color=_STYLE_COLOR)

        # Act
        _, diffuse, _, _ = _wrapped_material(style, False, _BASE_COLOR)

        # Assert
        self._assert_diffuse(diffuse, _STYLE_COLOR)

    def test_should_use_the_accent_when_a_highlight_meets_a_base_color(self):
        # Act
        _, diffuse, _, _ = _wrapped_material(None, True, _BASE_COLOR)

        # Assert
        self._assert_diffuse(diffuse, render_probe._ACCENT_COLOR)

    def test_should_keep_the_base_color_when_the_style_sets_only_transparency(self):
        # Arrange
        style = StyleSpec(object="Sketch", transparency=0.5)

        # Act
        _, diffuse, transparency, _ = _wrapped_material(style, False, _BASE_COLOR)

        # Assert
        self._assert_diffuse(diffuse, _BASE_COLOR)
        self.assertAlmostEqual(transparency, 0.5, places=5)


_BASE_COLOR = (0.4, 0.5, 0.6)


class _CubeGui:
    """A ``FreeCADGui`` stand-in whose every subgraph is a cube, so no GL context is needed."""

    @staticmethod
    def subgraphFromObject(_obj):  # noqa: N802 - mirrors the FreeCADGui API name
        from pivy import coin

        return coin.SoCube()


class SubgraphLineColorTest(unittest.TestCase):
    """``_add_subgraphs`` gives an unstyled sketch the fixed line color and leaves a solid alone.

    Pure Coin node manipulation over a stand-in GUI -- no rasterization -- so these run on a leg
    with no render capability.
    """

    def setUp(self):
        self.document = App.newDocument("screenshot_line_color")
        self.document.addObject("Part::Box", "Box")
        _add_square(self.document.addObject("Sketcher::SketchObject", "Sketch"))
        self.document.recompute()

    def tearDown(self):
        App.closeDocument(self.document.Name)

    def _first_child(self, name):
        """Add ``name``'s subgraph to a fresh root; return (is the bare cube, override diffuse).

        The diffuse is ``None`` when the cube was added unwrapped. Values are copied out while the
        root still owns the nodes, because Coin frees a child with its dropped parent.
        """
        from pivy import coin

        root = coin.SoSeparator()
        scene = SceneSpec(
            objects=[name], orientation=screenshot._CAMERA_QUATS["iso"], width=64, height=64
        )
        live = render_probe._LiveState(_CubeGui, self.document, "offscreen")
        viewport = coin.SbViewportRegion(64, 64)
        render_probe._add_subgraphs(_CubeGui, coin, root, self.document, scene, viewport, live)
        child = root.getChild(0)
        if child.isOfType(coin.SoCube.getClassTypeId()):
            return True, None
        return False, child.getChild(0).diffuseColor.getValues()[0].getValue()

    def test_should_add_the_solid_unwrapped_when_it_has_no_style(self):
        # Act
        bare, diffuse = self._first_child("Box")

        # Assert
        self.assertTrue(bare, f"the solid gained a material override: {diffuse}")

    def test_should_override_the_sketch_with_the_fixed_line_color_when_it_has_no_style(self):
        # Act
        bare, diffuse = self._first_child("Sketch")

        # Assert
        self.assertFalse(bare)
        expected = tuple(channel / 255.0 for channel in _SKETCH_LINE_RGB)
        for actual, want in zip(diffuse, expected):
            self.assertAlmostEqual(actual, want, places=5)


_RED_SHAPE_COLOR = 0xE61A1AFF


def _pin_view_color(test, key, packed_rgba):
    """Set the View color preference ``key`` for one test and restore it on cleanup.

    A headless view provider takes its colors from these preferences, so pinning one fixes the
    color every subgraph built during the test is drawn with.
    """
    preferences = App.ParamGet(_VIEW_PREFERENCES)
    if key in preferences.GetUnsigneds():
        test.addCleanup(preferences.SetUnsigned, key, preferences.GetUnsigned(key))
    else:
        test.addCleanup(preferences.RemUnsigned, key)
    preferences.SetUnsigned(key, packed_rgba)


class StyleReachesThePixelsTest(unittest.TestCase):
    """The prepended material must survive Coin traversal and change the rendered image."""

    def setUp(self):
        self.registry = DocumentRegistry()
        self.port = OffscreenRenderPort()
        handle = self.registry.document_create("screenshot_pixels")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(handle, lambda h, d: (h, d))
        box = self.document.addObject("Part::Box", "Box")
        box.Length, box.Width, box.Height = BOX_L, BOX_W, BOX_H
        self.document.recompute()

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _center_pixel(self, styles, highlight):
        """Render the box with ``styles``/``highlight`` and return the center pixel (r, g, b)."""
        from PySide import QtGui

        scene = SceneSpec(
            objects=["Box"],
            orientation=screenshot._CAMERA_QUATS["iso"],
            width=200,
            height=200,
            styles=styles,
            highlight=highlight,
        )
        handle, path = tempfile.mkstemp(suffix=".png")
        os.close(handle)
        try:
            self.port.render(self.document, scene, path)
            color = QtGui.QImage(path).pixelColor(100, 100)
            return color.red(), color.green(), color.blue()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_style_and_highlight_change_the_rendered_pixels(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        plain = self._center_pixel([], None)
        styled = self._center_pixel([StyleSpec(object="Box", color=(0.0, 0.0, 1.0))], None)
        highlighted = self._center_pixel([StyleSpec(object="Box", color=(0.0, 0.0, 1.0))], "Box")

        self.assertNotEqual(plain, styled, "the style override never reached the image")
        self.assertGreater(styled[2], styled[0], f"styled render is not blue-dominant: {styled}")
        self.assertGreater(
            highlighted[0], highlighted[2], f"highlight is not accent-hued: {highlighted}"
        )

    def test_should_change_the_pixels_and_keep_the_hue_when_a_style_sets_only_transparency(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        # Arrange: a red shape color, so "hue kept" is a channel order the grey default breaks.
        _pin_view_color(self, _SHAPE_COLOR_KEY, _RED_SHAPE_COLOR)
        plain = self._center_pixel([], None)

        # Act
        transparent = self._center_pixel([StyleSpec(object="Box", transparency=0.85)], None)

        # Assert
        self.assertNotEqual(plain, transparent, "the transparency never reached the image")
        self.assertGreater(plain[0], plain[2] + 20, f"the pinned color did not render: {plain}")
        # At 85 % over a white ground the red lead shrinks to ~13/255; the coupled-override defect
        # renders the face exactly grey, a lead of 0.
        self.assertGreater(
            transparent[0], transparent[2] + 5, f"transparency repainted the hue: {transparent}"
        )


_TONE_VIEWPORT = 240

# A quaternion no preset uses, so `custom` exercises the orientation path rather than a preset.
_CUSTOM_QUAT = (0.2, 0.3, 0.1, 0.9273618)

# The golden box takes its color from the `DefaultShapeColor` preference, falling back to FreeCAD's
# stock (0.8, 0.8, 0.9) when the profile has none (App/Material.cpp getDefaultAppearance). Left
# unpinned, the sweep grades the running profile rather than the rig: a customised steel-blue
# profile and a fresh one differ by ~33/255 on `right`. Pinning the stock value makes every leg
# render the brightest default material, the one that sets the band's ceiling.
_VIEW_PREFERENCES = "User parameter:BaseApp/Preferences/View"
_SHAPE_COLOR_KEY = "DefaultShapeColor"
_STOCK_SHAPE_COLOR = 0xCCCCE6FF

# `iso`'s tone under the shipped rig and the stock material, measured on llvmpipe (FreeCAD 1.1.3).
# The same rig reproduced the Windows GPU leg's `iso` within 0.3/255 for a shared material. This
# pins the tone so a later lighting change cannot drift it unnoticed in either direction.
_ISO_TONE = (126.8, 126.8, 135.5)
_ISO_TOLERANCE = 6

# The band's black end, asserted directly by the deliberately one-sided regression guard below.
_BLACK_END = 20


class CameraToneTest(unittest.TestCase):
    """Every named camera plus ``custom`` must render a face separable from the background.

    A headlight aimed exactly along the view axis leaves an axis-aligned camera's visible face
    anti-parallel to the light, degenerating the diffuse term until ambient alone saturates the
    face to pure white. The band below is two-sided on purpose: asserting only "not black" passes
    that white-face defect, and asserting only "not white" would re-admit the black-face defect
    that the ambient term was originally added to fix.
    """

    def setUp(self):
        self.view_preferences = App.ParamGet(_VIEW_PREFERENCES)
        self.saved_shape_color = (
            self.view_preferences.GetUnsigned(_SHAPE_COLOR_KEY)
            if _SHAPE_COLOR_KEY in self.view_preferences.GetUnsigneds()
            else None
        )
        # Registered before the change, so the profile is restored even if a later setUp line
        # raises and tearDown never runs.
        self.addCleanup(self._restore_shape_color)
        self.view_preferences.SetUnsigned(_SHAPE_COLOR_KEY, _STOCK_SHAPE_COLOR)
        self.registry = DocumentRegistry()
        self.port = OffscreenRenderPort()
        handle = self.registry.document_create("screenshot_tone")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(handle, lambda h, d: (h, d))
        box = self.document.addObject("Part::Box", "Box")
        box.Length, box.Width, box.Height = BOX_L, BOX_W, BOX_H
        self.document.recompute()

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _restore_shape_color(self):
        if self.saved_shape_color is None:
            self.view_preferences.RemUnsigned(_SHAPE_COLOR_KEY)
        else:
            self.view_preferences.SetUnsigned(_SHAPE_COLOR_KEY, self.saved_shape_color)

    def _render_verdict(self, orientation):
        """Render the golden box at ``orientation`` and return the shared oracle's verdict.

        The sweep grades through ``verify_render_tone`` rather than re-deriving the rule here, so
        this test and the ``g0/render-fault-injection`` suite that measures the oracle's
        sensitivity cannot drift apart.
        """
        scene = SceneSpec(
            objects=["Box"],
            orientation=orientation,
            width=_TONE_VIEWPORT,
            height=_TONE_VIEWPORT,
        )
        handle, path = tempfile.mkstemp(suffix=".png")
        os.close(handle)
        try:
            self.port.render(self.document, scene, path)
            return verify_render_tone(path)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def _camera_orientations(self):
        """Every named camera preset plus an explicit ``custom`` quaternion."""
        cameras = dict(screenshot._CAMERA_QUATS)
        cameras["custom"] = _CUSTOM_QUAT
        return cameras

    def test_every_camera_renders_a_face_inside_the_tone_band(self):
        if not _render_available():
            self.skipTest("no render context on this leg")
        for name, orientation in sorted(self._camera_orientations().items()):
            with self.subTest(camera=name):
                verdict = self._render_verdict(orientation)
                self.assertTrue(
                    verdict["passed"],
                    f"{name} failed the tone band: {'; '.join(verdict['reasons'])} "
                    f"(tone {verdict['tone']}, background {verdict['background']}, "
                    f"{verdict['samples']} samples, {verdict['coverage']:.1%} coverage)",
                )

    def test_front_camera_is_no_longer_a_white_rectangle(self):
        """The reproducer: `front` rendered rgb(255,255,255), identical to the background."""
        if not _render_available():
            self.skipTest("no render context on this leg")
        verdict = self._render_verdict(screenshot._CAMERA_QUATS["front"])
        tone = verdict["tone"]
        self.assertNotEqual(tuple(round(value) for value in tone), (255, 255, 255))
        self.assertTrue(verdict["passed"], f"front tone {tone}: {verdict['reasons']}")

    def test_iso_tone_is_pinned(self):
        """`iso` holds its measured tone -- a lighting change must not drift it unnoticed."""
        if not _render_available():
            self.skipTest("no render context on this leg")
        tone = self._render_verdict(screenshot._CAMERA_QUATS["iso"])["tone"]
        for channel, (value, expected) in enumerate(zip(tone, _ISO_TONE)):
            self.assertAlmostEqual(
                value,
                expected,
                delta=_ISO_TOLERANCE,
                msg=f"iso channel {channel} is {value:.1f}, expected ~{expected} "
                f"(measured tone {_ISO_TONE}, got {tone})",
            )

    def test_no_face_renders_black(self):
        """A "not black" assertion must still pass -- closing the white end opened no black end.

        This is deliberately the one-sided test that let the defect ship. It is kept as a
        regression guard: on its own it proves nothing, but a failure here would mean the fix
        traded one saturated end for the other.
        """
        if not _render_available():
            self.skipTest("no render context on this leg")
        for name, orientation in sorted(self._camera_orientations().items()):
            with self.subTest(camera=name):
                tone = self._render_verdict(orientation)["tone"]
                self.assertTrue(
                    all(value >= _BLACK_END for value in tone),
                    f"{name} rendered near-black: {tone}",
                )


if __name__ == "__main__":
    unittest.main()
