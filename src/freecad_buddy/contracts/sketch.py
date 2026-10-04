"""Sketch wire vocabulary: dimensional quantities, constraint refs, and the sketch state block.

Constraint ids on the wire are 1-based solver ids naming ``Constraints[id-1]``; the FreeCAD
Python API is 0-based. Geometry is addressed by sketch-local 0-based ``geo_id``. Stdlib only.
"""

from __future__ import annotations

from typing import Literal, TypedDict

GeometryKind = Literal[
    "line_segment",
    "circle",
    "arc_of_circle",
    "point",
]

ConstraintType = Literal[
    "Coincident",
    "Horizontal",
    "Vertical",
    "Parallel",
    "Perpendicular",
    "Tangent",
    "Equal",
    "Symmetric",
    "PointOnObject",
    "Block",
    "Distance",
    "DistanceX",
    "DistanceY",
    "Radius",
    "Diameter",
    "Angle",
]

# PointPos (Sketcher GeoEnum): 0 none (the edge itself), 1 start, 2 end, 3 mid.
PointPos = Literal[0, 1, 2, 3]


class Quantity(TypedDict):
    value: float
    unit: str


class ConstraintRef(TypedDict, total=False):
    id: int  # required; 1-based solver id
    name: str
    type: str


class GeometrySpec(TypedDict, total=False):
    kind: GeometryKind  # required
    start: list[float]
    end: list[float]
    center: list[float]
    radius: Quantity
    start_angle: Quantity
    end_angle: Quantity
    construction: bool


class ConstraintSpec(TypedDict, total=False):
    type: ConstraintType  # required
    first: int  # required
    first_pos: PointPos
    second: int
    second_pos: PointPos
    third: int
    third_pos: PointPos
    value: Quantity
    name: str
    driving: bool


class SketchState(TypedDict, total=False):
    schema: Literal["fcb.sketch-state/1"]
    sketch: str  # required
    readable: bool  # required; False when the sketch could not be graded
    dof: int  # required
    fully_constrained: bool  # required
    geometry_count: int  # required
    constraint_count: int  # required
    conflicting: list[ConstraintRef]
    redundant: list[ConstraintRef]
    partially_redundant: list[ConstraintRef]
    malformed: list[ConstraintRef]
    solver_status_code: int  # sk.solve() return code; 0 is a clean solve
