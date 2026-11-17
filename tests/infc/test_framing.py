"""In-FreeCAD framing tests: the measured box is in document coordinates (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. A feature inside a moved container carries its shape in
the container's coordinates, so its ``Shape.BoundBox`` alone is the wrong box to project through
the live camera. Golden boxes are analytic: a 60x40x10 pad turned 30 deg about Z and moved to
(30, 20, 10) spans x 10..30+60cos30, y 20..20+60sin30+40cos30, z 10..20. The measured box is the
container placement applied to the local box's corners, so it is exact for that pad (the local
box is the pad) and conservative for a cylinder of radius 10 turned 45 deg: the local box's
corners reach 10*sqrt(2) on x and y where the cylinder itself reaches 10.
"""

import math
import unittest

import FreeCAD as App
import Mesh
import Part

from freecad_buddy.usecases import framing
from freecad_buddy.usecases.documents import DocumentRegistry

PAD_L = 60.0
PAD_W = 40.0
PAD_H = 10.0
ANGLE = math.radians(30.0)
CYLINDER_R = 10.0
CYLINDER_H = 5.0


class ModelBoundsTest(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        handle = self.registry.document_create("framing")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(handle, lambda h, d: (h, d))

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def test_should_measure_the_global_box_when_the_body_is_moved_and_rotated(self):
        # Arrange
        body = self.document.addObject("PartDesign::Body", "Body")
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        corners = ((0, 0, 0), (PAD_L, 0, 0), (PAD_L, PAD_W, 0), (0, PAD_W, 0))
        for index, start in enumerate(corners):
            end = corners[(index + 1) % len(corners)]
            sketch.addGeometry(Part.LineSegment(App.Vector(*start), App.Vector(*end)), False)
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = sketch
        pad.Length = PAD_H
        body.Placement = App.Placement(
            App.Vector(30, 20, 10), App.Rotation(App.Vector(0, 0, 1), 30)
        )
        self.document.recompute()
        expected = (
            30.0 - PAD_W * math.sin(ANGLE),
            20.0,
            10.0,
            30.0 + PAD_L * math.cos(ANGLE),
            20.0 + PAD_L * math.sin(ANGLE) + PAD_W * math.cos(ANGLE),
            10.0 + PAD_H,
        )

        # Act
        measured = framing.model_bounds(self.document)

        # Assert
        for actual, wanted in zip(measured, expected):
            self.assertAlmostEqual(actual, wanted, places=4, msg=f"measured {measured}")

    def test_should_measure_the_global_box_when_a_mesh_sits_in_a_moved_part(self):
        # Arrange
        mesh = self.document.addObject("Mesh::Feature", "Mesh")
        mesh.Mesh = Mesh.createBox(10, 10, 10)
        container = self.document.addObject("App::Part", "Part")
        container.addObject(mesh)
        container.Placement = App.Placement(App.Vector(100, 0, 0), App.Rotation())
        self.document.recompute()

        # Act
        measured = framing.model_bounds(self.document)

        # Assert
        for actual, wanted in zip(measured, (95.0, -5.0, -5.0, 105.0, 5.0, 5.0)):
            self.assertAlmostEqual(actual, wanted, places=4, msg=f"measured {measured}")

    def test_should_measure_the_rotated_local_box_when_a_cylinder_sits_in_a_rotated_part(self):
        # Arrange
        cylinder = self.document.addObject("Part::Cylinder", "Cylinder")
        cylinder.Radius = CYLINDER_R
        cylinder.Height = CYLINDER_H
        container = self.document.addObject("App::Part", "Part")
        container.addObject(cylinder)
        container.Placement = App.Placement(App.Vector(), App.Rotation(App.Vector(0, 0, 1), 45))
        self.document.recompute()
        reach = CYLINDER_R * math.sqrt(2.0)
        expected = (-reach, -reach, 0.0, reach, reach, CYLINDER_H)

        # Act
        measured = framing.model_bounds(self.document)

        # Assert
        for actual, wanted in zip(measured, expected):
            self.assertAlmostEqual(actual, wanted, places=4, msg=f"measured {measured}")


if __name__ == "__main__":
    unittest.main()
