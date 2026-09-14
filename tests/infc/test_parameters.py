"""In-FreeCAD tests for the driving-parameter facade and the G3.3 editability test (story 4.6).

Runs via ``FreeCADCmd tests/run_tests.py``. The claims this suite has to be able to falsify are
the ones the spec's acceptance criteria state:

- a declared parameter is reachable through the facade under its intent-bearing name, on whichever
  backend the probe selected, and the backend is recorded rather than silently chosen;
- a parameter change recomputes clean AND the measured dimension reflects the new value;
- a parameter the model ignores is reported non-editable rather than passing on a clean recompute;
- a change that breaks the part is reported with its failing value and is not counted as editable.

The ignored-parameter case is built by hand, not through :func:`parameters.declare` — the facade
refuses to create one, which is the point, so the only way to test the detector is to plant the
defect the facade prevents.

Expected geometry is analytic — a box's own dimensions — never captured from a verify tool.
"""

import unittest

import FreeCAD as App
import Part

from benchmarks.harness import editability
from freecad_buddy.contracts import PARAMETER_OBJECT_NAME
from freecad_buddy.usecases import parameters, shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

# The fixture part: a box driven by three named dimensions. Chosen so each parameter drives a
# different extent, so a change to one moves exactly one bounding-box side and the movement leg
# cannot pass by coincidence.
PLATE_LENGTH = 80.0
PLATE_WIDTH = 60.0
PLATE_THICKNESS = 6.0


class ParameterFacadeTest(unittest.TestCase):
    """The facade surface: declare, read back, write, and the names it refuses."""

    def setUp(self):
        self.registry = DocumentRegistry()
        created = self.registry.document_create("parameters")
        self.handle = created["structured_content"]["doc"]
        self.document().addObject("Part::Box", "Plate")
        self.document().recompute()

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def document(self):
        return self.registry.with_document(self.handle, lambda _h, d: d)

    def declare_plate(self):
        """Declare the three plate dimensions, each driving the box property it names."""
        for name, value, prop in (
            ("plate_length", PLATE_LENGTH, "Length"),
            ("plate_width", PLATE_WIDTH, "Width"),
            ("plate_thickness", PLATE_THICKNESS, "Height"),
        ):
            envelope = parameters.declare(
                self.registry,
                doc=self.handle,
                name=name,
                value=value,
                unit="mm",
                drives=[f"Plate.{prop}"],
            )
            self.assertEqual(envelope["status"], "OK", envelope.get("detail"))

    def test_Should_expose_every_declared_dimension_under_its_name_When_read_back(self):
        # Arrange
        self.declare_plate()

        # Act
        surface = parameters.list_parameters(self.registry, self.handle)

        # Assert
        self.assertEqual(surface["holder"], PARAMETER_OBJECT_NAME)
        self.assertEqual(
            {p["name"]: p["value"] for p in surface["parameters"]},
            {
                "plate_length": PLATE_LENGTH,
                "plate_width": PLATE_WIDTH,
                "plate_thickness": PLATE_THICKNESS,
            },
        )

    def test_Should_report_the_probed_backend_When_the_surface_is_read(self):
        # Arrange
        self.declare_plate()
        probed, _reason = shim.varset_probe()

        # Act
        surface = parameters.list_parameters(self.registry, self.handle)

        # Assert: the surface reports the backend that is actually holding the parameters, and it
        # is the one the probe selected. A silent switch between the two legs fails here rather
        # than turning up as an editability rate nobody can read.
        self.assertEqual(surface["backend"], probed)
        self.assertIn(surface["backend"], ("varset", "spreadsheet"))

    def test_Should_drive_the_bound_feature_property_When_a_parameter_is_declared(self):
        # Arrange
        self.declare_plate()

        # Act
        shape = self.document().getObject("Plate").Shape

        # Assert
        self.assertAlmostEqual(shape.BoundBox.XLength, PLATE_LENGTH, places=6)
        self.assertAlmostEqual(shape.BoundBox.YLength, PLATE_WIDTH, places=6)
        self.assertAlmostEqual(shape.BoundBox.ZLength, PLATE_THICKNESS, places=6)

    def test_Should_move_the_geometry_When_a_declared_parameter_is_written(self):
        # Arrange
        self.declare_plate()
        new_thickness = 9.0

        # Act
        envelope = parameters.set_value(
            self.registry, doc=self.handle, name="plate_thickness", value=new_thickness, unit="mm"
        )

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        shape = self.document().getObject("Plate").Shape
        self.assertAlmostEqual(shape.BoundBox.ZLength, new_thickness, places=6)

    def test_Should_refuse_a_name_carrying_no_intent_When_declared(self):
        # Arrange
        anonymous = "d1"

        # Act
        act = lambda: parameters.declare(  # noqa: E731 - a thunk, so Assert applies the matcher
            self.registry, doc=self.handle, name=anonymous, value=6.0, drives=["Plate.Height"]
        )

        # Assert
        with self.assertRaises(ValidationError) as raised:
            act()
        self.assertIn("carries no intent", str(raised.exception))

    def test_Should_refuse_a_parameter_that_drives_nothing_When_declared(self):
        # Arrange
        drives_nothing = []

        # Act
        act = lambda: parameters.declare(  # noqa: E731
            self.registry,
            doc=self.handle,
            name="plate_thickness",
            value=6.0,
            drives=drives_nothing,
        )

        # Assert: the facade never creates the blob-with-variables case decision 018 measures for.
        with self.assertRaises(ValidationError) as raised:
            act()
        self.assertIn("drive at least one feature property", str(raised.exception))

    def test_Should_refuse_a_write_to_an_undeclared_parameter_When_set(self):
        # Arrange
        self.declare_plate()
        undeclared = "bore_diameter"

        # Act
        act = lambda: parameters.set_value(  # noqa: E731
            self.registry, doc=self.handle, name=undeclared, value=12.0, unit="mm"
        )

        # Assert
        with self.assertRaises(ValidationError) as raised:
            act()
        self.assertIn("declares no driving parameter", str(raised.exception))


class EditabilityProbeTest(unittest.TestCase):
    """Decision 018's three legs, each proven by a case that must fail on exactly one of them."""

    def setUp(self):
        self.registry = DocumentRegistry()
        created = self.registry.document_create("editability")
        self.handle = created["structured_content"]["doc"]

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def document(self):
        return self.registry.with_document(self.handle, lambda _h, d: d)

    def build_driven_plate(self):
        """A box whose thickness is genuinely driven by a declared parameter."""
        document = self.document()
        document.addObject("Part::Box", "Plate")
        document.recompute()
        for name, value, prop in (
            ("plate_length", PLATE_LENGTH, "Length"),
            ("plate_thickness", PLATE_THICKNESS, "Height"),
        ):
            parameters.declare(
                self.registry,
                doc=self.handle,
                name=name,
                value=value,
                unit="mm",
                drives=[f"Plate.{prop}"],
            )

    def test_Should_report_editable_When_the_change_recomputes_and_the_dimension_moves(self):
        # Arrange
        self.build_driven_plate()

        # Act
        result = editability.probe_part(self.registry, self.handle, "driven-plate")

        # Assert: the selected parameter is the first in surface order (decision 018 §1), the
        # change is +10% floored at 0.5 mm (§2), and all three legs hold.
        self.assertEqual(result["parameter"], "plate_length")
        self.assertAlmostEqual(result["value_after"], PLATE_LENGTH * 1.1, places=6)
        self.assertTrue(result["recompute_clean"])
        self.assertTrue(result["valid_solid"])
        self.assertTrue(result["dimension_moved"])
        self.assertTrue(result["editable"])
        self.assertIsNone(result["failure"])

    def test_Should_move_the_measured_geometry_When_the_parameter_is_changed(self):
        # Arrange
        self.build_driven_plate()

        # Act
        editability.probe_part(self.registry, self.handle, "driven-plate")

        # Assert: the part itself carries the new length, which is the claim "the dimension moved"
        # makes. Reading the property back instead would pass whether or not anything consumed it.
        shape = self.document().getObject("Plate").Shape
        self.assertAlmostEqual(shape.BoundBox.XLength, editability.change_for(PLATE_LENGTH), 6)

    def test_Should_report_non_editable_When_the_parameter_drives_nothing(self):
        # Arrange: planted by hand. `parameters.declare` refuses to build this, so the only way to
        # exercise the detector is to write the holder directly — exactly the shape a part whose
        # expression binding was later broken would be left in.
        document = self.document()
        plate = document.addObject("Part::Box", "Plate")
        plate.Length, plate.Width, plate.Height = PLATE_LENGTH, PLATE_WIDTH, PLATE_THICKNESS
        holder_type = "App::VarSet" if shim.varset_available() else "Spreadsheet::Sheet"
        holder = document.addObject(holder_type, PARAMETER_OBJECT_NAME)
        holder.addProperty("App::PropertyLength", "plate_thickness", "Driving", "")
        holder.plate_thickness = PLATE_THICKNESS
        document.recompute()

        # Act
        result = editability.probe_part(self.registry, self.handle, "ignored-parameter")

        # Assert: the recompute is perfectly clean and the part is a valid solid — the two legs a
        # "recompute without errors" test would read — and the verdict is still non-editable.
        self.assertTrue(result["recompute_clean"])
        self.assertTrue(result["valid_solid"])
        self.assertFalse(result["dimension_moved"])
        self.assertFalse(result["editable"])
        self.assertEqual(result["failure"], "ignored")

    def test_Should_report_non_editable_with_the_failing_value_When_the_change_breaks_the_part(
        self,
    ):
        # Arrange: a pocket cut as deep as the stock. Growing its depth by 10% cuts past the far
        # face, which leaves the PartDesign feature in error rather than producing a bigger part.
        self.build_broken_on_growth()

        # Act
        result = editability.probe_part(self.registry, self.handle, "breaks-on-growth")

        # Assert
        self.assertFalse(result["editable"])
        self.assertIn(result["failure"], ("recompute_error", "invalid_solid"))
        self.assertAlmostEqual(result["value_after"], editability.change_for(self.CUT_WIDTH), 6)
        self.assertIn(str(result["value_after"]), str(result["detail"]))

    # The cut width that leaves a sliver of the fixed-length stock, and which +10 % grows past the
    # stock's whole length — so the change turns a valid solid into a null one.
    CUT_WIDTH = 75.0

    def build_broken_on_growth(self):
        """A part a +10 % change on its first parameter makes invalid.

        The parameter drives the length of a ``Part::Cut``'s tool box, which removes material from
        one end of an ``PLATE_LENGTH``-long stock. At 75 mm a 5 mm sliver survives; grown to
        82.5 mm the cut consumes the whole stock, and a cut that removes everything produces a
        null shape rather than a solid.
        """
        document = self.document()
        stock = document.addObject("Part::Box", "Stock")
        stock.Length, stock.Width, stock.Height = PLATE_LENGTH, PLATE_WIDTH, PLATE_THICKNESS
        tool = document.addObject("Part::Box", "Tool")
        tool.Length, tool.Width, tool.Height = self.CUT_WIDTH, PLATE_WIDTH, PLATE_THICKNESS
        cut = document.addObject("Part::Cut", "Plate")
        cut.Base, cut.Tool = stock, tool
        document.recompute()
        parameters.declare(
            self.registry,
            doc=self.handle,
            name="cut_length",
            value=self.CUT_WIDTH,
            unit="mm",
            drives=["Tool.Length"],
        )

    def test_Should_report_non_editable_When_the_part_exposes_no_parameter(self):
        # Arrange
        document = self.document()
        plate = document.addObject("Part::Feature", "Plate")
        plate.Shape = Part.makeBox(PLATE_LENGTH, PLATE_WIDTH, PLATE_THICKNESS)
        document.recompute()

        # Act
        result = editability.probe_part(self.registry, self.handle, "no-parameter")

        # Assert: a part with no driving dimension is not skipped, it fails (decision 018 §1).
        self.assertFalse(result["editable"])
        self.assertEqual(result["failure"], "no_parameter")


class EditabilityCollectorTest(unittest.TestCase):
    """The G3.3 criterion report: the bar comes from the gate, the denominator from the parts."""

    CRITERION = {"id": "G3.3", "pass_rule": ">=90% recompute without errors"}

    def result(self, part, editable, failure=None):
        return {
            "schema": "fcb.editability-result/1",
            "part": part,
            "parameter": "plate_thickness",
            "editable": editable,
            "failure": failure,
        }

    def test_Should_pass_When_the_editable_rate_clears_the_gates_own_bar(self):
        # Arrange
        results = [self.result(f"p{i}", True) for i in range(10)]

        # Act
        report = editability.collect_g3_3(self.CRITERION, results)

        # Assert
        self.assertEqual(report["verdict"], "OK")
        self.assertTrue(report["checks"][0]["passed"])

    def test_Should_fail_When_an_ignored_parameter_drags_the_rate_below_the_bar(self):
        # Arrange: eight parts rebuild and two parameters drive nothing, so the rate is 0.8 and
        # the bar is 0.9. A criterion reading only "recompute without errors" would score this
        # 10/10 and pass, because a parameter nothing references recomputes perfectly cleanly.
        results = [self.result(f"p{i}", True) for i in range(8)]
        results.extend(self.result(f"p{i}", False, "ignored") for i in (8, 9))

        # Act
        report = editability.collect_g3_3(self.CRITERION, results)

        # Assert
        self.assertFalse(report["checks"][0]["passed"])
        self.assertIn("ignored", report["checks"][0]["detail"]["message"])

    def test_Should_refuse_to_report_a_rate_When_no_part_was_probed(self):
        # Arrange
        nothing_probed = []

        # Act
        report = editability.collect_g3_3(self.CRITERION, nothing_probed)

        # Assert: an empty run is an uncollected criterion, never a vacuous 0/0 pass.
        self.assertEqual(report["verdict"], "INVALID_INPUT")
        self.assertFalse(report["checks"][0]["passed"])


class ParameterBannerTest(unittest.TestCase):
    """The probe result reaches the report banner, so a backend switch between legs is visible."""

    def setUp(self):
        self.registry = DocumentRegistry()
        created = self.registry.document_create("banner")
        self.handle = created["structured_content"]["doc"]
        document = self.registry.with_document(self.handle, lambda _h, d: d)
        plate = document.addObject("Part::Feature", "Plate")
        plate.Shape = Part.makeBox(PLATE_LENGTH, PLATE_WIDTH, PLATE_THICKNESS)
        document.recompute()

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def test_Should_record_the_probed_backend_When_a_verify_report_is_built(self):
        # Arrange
        from freecad_buddy.usecases import verify

        expected, _reason = shim.varset_probe()

        # Act
        envelope = verify.verify_shape(self.registry, doc=self.handle, object="Plate")

        # Assert
        banner = envelope["structured_content"]["banner"]
        self.assertEqual(banner["varset_backend"], expected)

    def test_Should_name_the_reason_When_the_probe_falls_back_to_the_spreadsheet(self):
        # Arrange
        backend, reason = shim.varset_probe()

        # Assert: a fallback is never silent. On both supported legs the probe selects VarSet, so
        # this asserts the invariant rather than the fallback path itself — no environment
        # available to this repository exercises the Spreadsheet backend.
        if backend == "spreadsheet":
            self.assertTrue(reason, "a fallback must name what it could not do")
        else:
            self.assertIsNone(reason)
