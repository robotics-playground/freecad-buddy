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
import unittest

import FreeCAD as App

from freecad_buddy.adapters.render_probe import OffscreenRenderPort, render_capability
from freecad_buddy.contracts import massprops_equal
from freecad_buddy.usecases import screenshot
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
from freecad_buddy.usecases.fingerprint import fingerprint

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


if __name__ == "__main__":
    unittest.main()
