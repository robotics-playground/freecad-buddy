"""In-FreeCAD tests for the verify-core validators and the fingerprint oracle (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Golden values are analytic (hand-computed box
volume/bbox), never captured from the implementation under test. Covers fingerprint
stability/sensitivity/cross-tag, ``verify_shape`` golden-pass / defect-fail / null-shape,
``verify_sketch`` pass / under-constrained / redundant-warn / not-a-sketch, ``verify_recompute``
broken-object report + banner, and the bad-handle ``INVALID_INPUT`` boundary.
"""

import os
import tempfile
import unittest

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.contracts import fingerprints_equal
from freecad_buddy.usecases import assertions, fingerprint, verify
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

BOX_L = 10.0
BOX_W = 20.0
BOX_H = 30.0
ANALYTIC_VOLUME = BOX_L * BOX_W * BOX_H  # 6000 mm^3


class _DocFixture(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create("verify_tools")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _add_box(self, name="Box", length=BOX_L, width=BOX_W, height=BOX_H):
        box = self.document.addObject("Part::Box", name)
        box.Length = length
        box.Width = width
        box.Height = height
        self.document.recompute()
        return box


class FingerprintTest(_DocFixture):
    def test_stable_digest_across_two_hashes_of_unchanged_doc(self):
        self._add_box()
        first = fingerprint.fingerprint(self.document)
        second = fingerprint.fingerprint(self.document)
        self.assertEqual(first["digest"], second["digest"])
        self.assertIn(first["serializer"], ("exportBinary", "exportBrep"))
        self.assertTrue(fingerprints_equal(first, second))

    def test_one_micron_length_change_changes_digest(self):
        box = self._add_box()
        before = fingerprint.fingerprint(self.document)["digest"]
        box.Length = BOX_L + 1e-3  # 1 micron = 1e-3 mm
        self.document.recompute()
        after = fingerprint.fingerprint(self.document)["digest"]
        self.assertNotEqual(before, after)

    def test_added_hole_changes_digest(self):
        self._add_box()
        before = fingerprint.fingerprint(self.document)["digest"]
        cut = self.document.addObject("Part::Feature", "Holed")
        cut.Shape = Part.makeBox(BOX_L, BOX_W, BOX_H).cut(
            Part.makeCylinder(2.0, BOX_H, App.Vector(5, 10, 0))
        )
        self.document.recompute()
        after = fingerprint.fingerprint(self.document)["digest"]
        self.assertNotEqual(before, after)

    def test_mirror_changes_digest(self):
        base = self.document.addObject("Part::Feature", "Wedge")
        base.Shape = Part.makeBox(10, 20, 30).cut(Part.makeBox(5, 5, 5))
        self.document.recompute()
        before = fingerprint.fingerprint(self.document)["digest"]
        base.Shape = base.Shape.mirror(App.Vector(0, 0, 0), App.Vector(1, 0, 0))
        self.document.recompute()
        after = fingerprint.fingerprint(self.document)["digest"]
        self.assertNotEqual(before, after)

    def test_cross_tag_comparison_raises(self):
        self._add_box()
        record = fingerprint.fingerprint(self.document)
        other_tag = "exportBrep" if record["serializer"] == "exportBinary" else "exportBinary"
        cross = dict(record)
        cross["serializer"] = other_tag
        with self.assertRaises(ValueError):
            fingerprints_equal(record, cross)

    def test_null_shape_object_is_skipped(self):
        self._add_box()
        self.document.addObject("Part::Feature", "Empty")  # present but null Shape
        self.document.recompute()
        record = fingerprint.fingerprint(self.document)
        names = {entry["name"] for entry in record["objects"]}
        self.assertIn("Box", names)
        self.assertNotIn("Empty", names)

    def test_infinite_datum_planes_are_skipped(self):
        # A PartDesign Body auto-creates an App::Origin whose App::Plane children are infinite:
        # XZ_Plane.Area is 8.000000000000003e+100. Hashing them makes rollback unprovable, and
        # they carry no model geometry.
        self.document.addObject("PartDesign::Body", "Body")
        self.document.recompute()
        names = {entry["name"] for entry in fingerprint.fingerprint(self.document)["objects"]}
        for datum in ("XY_Plane", "XZ_Plane", "YZ_Plane", "X_Axis", "Y_Axis", "Z_Axis"):
            self.assertNotIn(datum, names, f"{datum} must not be hashed")

    def test_a_body_survives_a_save_reload_round_trip(self):
        """The snapshot-restore rollback path re-hashes after saveCopy + reopen.

        An infinite plane's 1e100-magnitude coordinates lose their low-order bits through that
        round trip, so hashing one makes every rollback on a Body-bearing document fail its own
        proof.
        """
        self.document.addObject("PartDesign::Body", "Body")
        self.document.recompute()
        before = fingerprint.fingerprint(self.document)

        snapshot = os.path.join(tempfile.gettempdir(), "FCB_TMP_roundtrip_probe.FCStd")
        self.addCleanup(lambda: os.path.exists(snapshot) and os.remove(snapshot))
        self.document.saveCopy(snapshot)
        reopened = App.openDocument(snapshot)
        try:
            self.assertEqual(before["digest"], fingerprint.fingerprint(reopened)["digest"])
        finally:
            App.closeDocument(reopened.Name)


class VerifyShapeTest(_DocFixture):
    def test_golden_pass_within_band_and_banner_present(self):
        self._add_box()
        envelope = verify.verify_shape(
            self.registry,
            doc=self.handle,
            object="Box",
            checks=[
                {"fn": "expect_volume", "expect": ANALYTIC_VOLUME, "tol": {"rel": 0.001}},
                {"fn": "expect_bbox", "expect": [BOX_L, BOX_W, BOX_H], "tol": {"rel": 0.001}},
                {"fn": "expect_solid_count", "expect": 1},
                {"fn": "expect_valid", "expect": True},
                {"fn": "expect_watertight", "expect": True},
            ],
        )
        content = envelope["structured_content"]
        self.assertEqual(content["verdict"], "OK")
        self.assertEqual(envelope["status"], "OK")
        self.assertTrue(all(c["passed"] for c in content["checks"]))
        self.assertEqual(content["banner"]["freecad_version"], _freecad_version())
        self.assertIn("element_map_version", content["banner"])

    def test_defect_fails_with_spec_failed(self):
        self._add_box(length=12.0)  # volume 7200 vs reference 6000
        envelope = verify.verify_shape(
            self.registry,
            doc=self.handle,
            object="Box",
            checks=[{"fn": "expect_volume", "expect": ANALYTIC_VOLUME, "tol": {"rel": 0.001}}],
        )
        content = envelope["structured_content"]
        self.assertEqual(content["verdict"], "SPEC_FAILED")
        self.assertFalse(content["checks"][0]["passed"])
        # Envelope contract: a non-OK status carries a non-null detail naming the failed check.
        self.assertEqual(envelope["status"], "SPEC_FAILED")
        self.assertIsNotNone(envelope["detail"])
        self.assertEqual(envelope["detail"]["code"], "SPEC_FAILED")
        self.assertIn("assert.expect_volume", envelope["detail"]["message"])

    def test_checkless_call_reports_measured_facts(self):
        self._add_box()
        content = verify.verify_shape(self.registry, doc=self.handle, object="Box")[
            "structured_content"
        ]
        self.assertEqual(content["verdict"], "OK")
        by_id = {c["id"]: c for c in content["checks"]}
        self.assertNotIn("expected", by_id["shape.volume"])
        self.assertLessEqual(
            abs(by_id["shape.volume"]["measured"] - ANALYTIC_VOLUME) / ANALYTIC_VOLUME, 0.001
        )

    def test_null_shape_is_invalid_input(self):
        self.document.addObject("Part::Feature", "Empty")
        self.document.recompute()
        envelope = _verify_dispatch(self.registry).dispatch(
            "verify_shape", {"doc": self.handle, "object": "Empty"}
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_unknown_object_is_invalid_input(self):
        envelope = _verify_dispatch(self.registry).dispatch(
            "verify_shape", {"doc": self.handle, "object": "Nope"}
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_malformed_bbox_expect_is_invalid_input(self):
        self._add_box()
        envelope = _verify_dispatch(self.registry).dispatch(
            "verify_shape",
            {
                "doc": self.handle,
                "object": "Box",
                "checks": [{"fn": "expect_bbox", "expect": [10, 20]}],
            },
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_should_compare_sorted_extents_when_expect_bbox_lists_them_in_another_order(self):
        # Arrange
        self._add_box()
        reordered = {"fn": "expect_bbox", "expect": [BOX_H, BOX_L, BOX_W], "tol": {"rel": 0.001}}
        wrong_length = {"fn": "expect_bbox", "expect": [BOX_L, BOX_W, 60.0], "tol": {"rel": 0.001}}

        # Act
        content = verify.verify_shape(
            self.registry, doc=self.handle, object="Box", checks=[reordered, wrong_length]
        )["structured_content"]

        # Assert
        self.assertEqual([c["passed"] for c in content["checks"]], [True, False])
        for measured, expected in zip(content["checks"][0]["measured"], [BOX_L, BOX_W, BOX_H]):
            self.assertAlmostEqual(measured, expected, places=6)

    def test_shape_floor_missing_tolerance_attr_is_benign_zero(self):
        self.assertEqual(assertions.shape_floor(_FakeShape(tolerance=None)), 0.0)

    def test_shape_floor_raising_tolerance_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            assertions.shape_floor(_FakeShape(tolerance="raise"))

    def test_is_watertight_raising_isclosed_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            verify._is_watertight(_FakeShape(solids=1, is_closed="raise"))

    def test_is_watertight_multi_solid_is_real_false(self):
        self.assertFalse(verify._is_watertight(_FakeShape(solids=2, is_closed="raise")))

    def test_absent_isclosed_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            verify._is_watertight(_FakeShape(solids=1, is_closed=None))

    def test_shape_floor_clamps_comparison_to_tolerance_floor(self):
        band, note = assertions._floored(0.01, 0.5)
        self.assertEqual(band, 0.5)
        self.assertIn("clamped to shape tolerance floor", note)

    def test_gettolerance_raise_through_dispatch_is_invalid_input(self):
        self._add_box()
        with _patched_require_shape(_FakeShape(solids=1, tolerance="raise", is_closed=True)):
            envelope = _verify_dispatch(self.registry).dispatch(
                "verify_shape",
                {
                    "doc": self.handle,
                    "object": "Box",
                    "checks": [{"fn": "expect_volume", "expect": 6000, "tol": {"rel": 0.001}}],
                },
            )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_isclosed_raise_through_dispatch_is_invalid_input(self):
        self._add_box()
        with _patched_require_shape(_FakeShape(solids=1, tolerance=0.0, is_closed="raise")):
            envelope = _verify_dispatch(self.registry).dispatch(
                "verify_shape",
                {
                    "doc": self.handle,
                    "object": "Box",
                    "checks": [{"fn": "expect_watertight", "expect": True}],
                },
            )
        self.assertEqual(envelope["status"], "INVALID_INPUT")


class VerifySketchTest(_DocFixture):
    def _fully_constrained_sketch(self, name="Sketch"):
        sk = self.document.addObject("Sketcher::SketchObject", name)
        sk.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(40, 0, 0)), False)
        sk.addConstraint(Sketcher.Constraint("Coincident", -1, 1, 0, 1))  # start at origin
        sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 40.0))
        sk.addConstraint(Sketcher.Constraint("DistanceY", 0, 1, 0, 2, 0.0))
        self.document.recompute()
        return sk

    def test_fully_constrained_sketch_passes(self):
        self._fully_constrained_sketch()
        content = verify.verify_sketch(self.registry, doc=self.handle, sketch="Sketch")[
            "structured_content"
        ]
        self.assertEqual(content["verdict"], "OK")
        self.assertTrue(content["subject"]["fully_constrained"])
        self.assertEqual(content["subject"]["dof"], 0)

    def test_under_constrained_sketch_hard_fails(self):
        sk = self.document.addObject("Sketcher::SketchObject", "Loose")
        sk.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(40, 0, 0)), False)
        self.document.recompute()
        content = verify.verify_sketch(self.registry, doc=self.handle, sketch="Loose")[
            "structured_content"
        ]
        self.assertEqual(content["verdict"], "SPEC_FAILED")
        self.assertGreater(content["subject"]["dof"], 0)
        self.assertFalse(content["checks"][0]["passed"])

    def test_redundant_constraint_is_warning_never_fails(self):
        sk = self._fully_constrained_sketch("Redundant")
        sk.addConstraint(Sketcher.Constraint("Horizontal", 0))  # duplicate -> redundant
        self.document.recompute()
        content = verify.verify_sketch(self.registry, doc=self.handle, sketch="Redundant")[
            "structured_content"
        ]
        self.assertEqual(content["verdict"], "OK")
        warning_ids = {w["id"] for w in content.get("warnings", [])}
        self.assertIn("sketch.redundant", warning_ids)

    def test_non_sketch_is_invalid_input(self):
        self._add_box()
        envelope = _verify_dispatch(self.registry).dispatch(
            "verify_sketch", {"doc": self.handle, "sketch": "Box"}
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")


class VerifyRecomputeTest(_DocFixture):
    def test_clean_document_is_ok(self):
        self._add_box()
        content = verify.verify_recompute(self.registry, doc=self.handle)["structured_content"]
        self.assertEqual(content["verdict"], "OK")
        self.assertEqual(content["subject"]["failing_objects"], [])
        self.assertEqual(content["banner"]["freecad_version"], _freecad_version())

    def test_broken_object_reports_name_and_status(self):
        # A Part::Cut with no Base/Tool leaves the object Invalid after recompute.
        self.document.addObject("Part::Cut", "Broken")
        content = verify.verify_recompute(self.registry, doc=self.handle)["structured_content"]
        self.assertEqual(content["verdict"], "RECOMPUTE_ERROR")
        self.assertIn("Broken", content["subject"]["failing_objects"])
        self.assertIn("banner", content)
        failed = [c for c in content["checks"] if not c["passed"]]
        self.assertTrue(any("Broken" in c["detail"]["message"] for c in failed))


class BadHandleTest(_DocFixture):
    def test_missing_handle_is_invalid_input(self):
        for name, params in (
            ("verify_shape", {"doc": "fcb-doc:missing", "object": "Box"}),
            ("verify_sketch", {"doc": "fcb-doc:missing", "sketch": "Sketch"}),
            ("verify_recompute", {"doc": "fcb-doc:missing"}),
        ):
            envelope = _verify_dispatch(self.registry).dispatch(name, params)
            self.assertEqual(envelope["status"], "INVALID_INPUT", name)


class _FakeShape:
    """Duck-typed stand-in for a Part shape exposing the measurement surface DW-32 guards.

    ``tolerance``/``is_closed`` accept ``"raise"`` to force the corresponding call to raise,
    ``None`` to omit the attribute, or a value to return; ``solids`` sets the solid count.
    """

    def __init__(self, solids: int = 1, tolerance=0.0, is_closed=True):
        self.Solids = [object()] * solids
        if tolerance is not None:
            self.getTolerance = self._tolerance_getter(tolerance)
        if is_closed is not None:
            self.isClosed = self._is_closed(is_closed)

    @staticmethod
    def _tolerance_getter(value):
        def getter(mode):
            if value == "raise":
                raise RuntimeError("OCC tolerance failure")
            return value

        return getter

    @staticmethod
    def _is_closed(value):
        def is_closed():
            if value == "raise":
                raise RuntimeError("check failed, shape may be empty")
            return value

        return is_closed


class _patched_require_shape:
    """Context manager forcing ``verify._require_shape`` to return ``shape``."""

    def __init__(self, shape):
        self._shape = shape
        self._original = None

    def __enter__(self):
        self._original = verify._require_shape
        verify._require_shape = lambda obj, name: self._shape
        return self

    def __exit__(self, *exc):
        verify._require_shape = self._original
        return False


def _freecad_version() -> str:
    return ".".join(str(part) for part in App.Version()[:3])


def _verify_dispatch(registry: DocumentRegistry) -> MethodRegistry:
    methods = MethodRegistry()
    for name, fn in (
        ("verify_shape", verify.verify_shape),
        ("verify_sketch", verify.verify_sketch),
        ("verify_recompute", verify.verify_recompute),
    ):
        methods.register(
            RpcMethod(
                name=name,
                handler=(lambda _fn: lambda **p: _fn(registry, **p))(fn),
                mutating=False,
            )
        )
    return methods


if __name__ == "__main__":
    unittest.main()
