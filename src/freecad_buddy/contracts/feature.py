"""Feature wire vocabulary: the created-feature state block and its shape summary.

Dimensions on the wire are ``Quantity`` objects; feature angles carry ``deg``. Every logic key
is the immutable ``Name``; the caller-supplied intent-bearing name becomes the ``Label``.
Stdlib only.
"""

from __future__ import annotations

from typing import Literal, TypedDict

PatternKind = Literal["linear", "polar"]

DatumKind = Literal["plane", "axis", "point", "cs"]

# Extrude Type values shared by Pad and Pocket. The live enum is the authority — each value is
# validated against ``getEnumerationsOfProperty`` at call time, because the two blocking FreeCAD
# legs spell and order the enum differently.
ExtrudeType = Literal["Length", "ThroughAll", "UpToFirst", "UpToLast", "UpToFace"]


class ShapeSummary(TypedDict, total=False):
    volume: float  # required
    area: float  # required
    bbox: list[float]  # required; [XLength, YLength, ZLength]
    solid_count: int  # required
    face_count: int  # required
    edge_count: int  # required
    vertex_count: int  # required
    is_valid: bool  # required


class FeatureState(TypedDict, total=False):
    schema: Literal["fcb.feature-state/1"]
    feature: str  # required
    readable: bool  # required; False when the feature could not be graded
    body: str
    is_tip: bool
    shape_summary: ShapeSummary
