"""Deterministic FreeCADCmd generator for the 30 broken-recompute fixtures.

Run under FreeCADCmd with ``FREECAD_BUDDY_BUILD_BROKEN_DOCS=1`` in the environment — POSIX
``FREECAD_BUDDY_BUILD_BROKEN_DOCS=1 FreeCADCmd build_broken_docs.py``, PowerShell
``$env:FREECAD_BUDDY_BUILD_BROKEN_DOCS=1; FreeCADCmd build_broken_docs.py``. Importing the module
never builds. Each fixture carries a REAL broken recompute on a fixed failing object ``Name``:
after ``doc.recompute()`` that object has a non-empty ``getStatusString()``. The ``tests/infc``
self-check opens each committed fixture, recomputes, and asserts the named object is genuinely
in error.

Four break kinds are repeated across the 30 cases with distinct object names + parameters
(a handful of reliable kinds suffices — G1.2 requires each fixture to break genuinely on its
named object, not 30 distinct kinds):

  - ``overconstrained`` -- a sketch with two conflicting DistanceX constraints on one line.
  - ``broken_expression`` -- a box whose ``Height`` binds an expression to a non-existent object.
  - ``pad_missing_sketch`` -- a PartDesign Pad whose profile sketch was removed.
  - ``cut_missing_tool``  -- a Part::Cut whose Tool object was removed.

Fixtures are written next to their ``case.yaml`` as ``<case-id>/fixture.FCStd``. No timestamps.
"""

from __future__ import annotations

import os
from pathlib import Path

import FreeCAD as App
import Part
import Sketcher

HERE = Path(__file__).resolve().parent

_SQUARE = (
    ((0, 0, 0), (10, 0, 0)),
    ((10, 0, 0), (10, 10, 0)),
    ((10, 10, 0), (0, 10, 0)),
    ((0, 10, 0), (0, 0, 0)),
)


def _overconstrained(doc, obj_name: str, first: float, second: float) -> None:
    """A sketch line pinned to two conflicting DistanceX values -> conflicting constraints."""
    sk = doc.addObject("Sketcher::SketchObject", obj_name)
    sk.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0)), False)
    sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, first))
    sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, second))


def _broken_expression(doc, obj_name: str, missing: str) -> None:
    """A box whose Height expression references a non-existent object -> binding error."""
    box = doc.addObject("Part::Box", obj_name)
    box.setExpression("Height", f"{missing}.Width")


def _pad_missing_sketch(doc, obj_name: str, length: float) -> None:
    """A PartDesign Pad whose profile sketch is removed after the pad is built -> no object."""
    body = doc.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "ProfileSketch")
    for start, end in _SQUARE:
        sk.addGeometry(Part.LineSegment(App.Vector(*start), App.Vector(*end)), False)
    doc.recompute()
    pad = body.newObject("PartDesign::Pad", obj_name)
    pad.Profile = sk
    pad.Length = length
    doc.recompute()
    doc.removeObject(sk.Name)


def _cut_missing_tool(doc, obj_name: str, tool_height: float) -> None:
    """A Part::Cut whose Tool box is removed after the cut is built -> linked-object error."""
    base = doc.addObject("Part::Box", f"{obj_name}Base")
    tool = doc.addObject("Part::Box", f"{obj_name}Tool")
    tool.Height = tool_height
    cut = doc.addObject("Part::Cut", obj_name)
    cut.Base = base
    cut.Tool = tool
    doc.recompute()
    doc.removeObject(tool.Name)


# case-id -> (failing object Name, builder). Order fixed for determinism. 30 cases:
# 8 overconstrained, 8 broken_expression, 7 pad_missing_sketch, 7 cut_missing_tool.
CASES: dict[str, tuple[str, object]] = {
    # --- overconstrained sketches (conflicting constraints) ---
    "oc-bracket-plate": ("BracketPlate", lambda d: _overconstrained(d, "BracketPlate", 10.0, 20.0)),
    "oc-mount-slot": ("MountSlot", lambda d: _overconstrained(d, "MountSlot", 15.0, 25.0)),
    "oc-rib-profile": ("RibProfile", lambda d: _overconstrained(d, "RibProfile", 8.0, 12.0)),
    "oc-flange-outline": (
        "FlangeOutline",
        lambda d: _overconstrained(d, "FlangeOutline", 30.0, 45.0),
    ),
    "oc-lever-arm": ("LeverArm", lambda d: _overconstrained(d, "LeverArm", 40.0, 55.0)),
    "oc-gasket-ring": ("GasketRing", lambda d: _overconstrained(d, "GasketRing", 22.0, 33.0)),
    "oc-shim-plate": ("ShimPlate", lambda d: _overconstrained(d, "ShimPlate", 5.0, 9.0)),
    "oc-cover-panel": ("CoverPanel", lambda d: _overconstrained(d, "CoverPanel", 60.0, 80.0)),
    # --- broken expression bindings (missing referenced object) ---
    "be-spacer-height": (
        "SpacerHeight",
        lambda d: _broken_expression(d, "SpacerHeight", "DatumPlane"),
    ),
    "be-standoff": ("Standoff", lambda d: _broken_expression(d, "Standoff", "BaseSketch")),
    "be-boss-post": ("BossPost", lambda d: _broken_expression(d, "BossPost", "MasterBox")),
    "be-riser-block": ("RiserBlock", lambda d: _broken_expression(d, "RiserBlock", "RefCyl")),
    "be-pillar": ("Pillar", lambda d: _broken_expression(d, "Pillar", "ParamHub")),
    "be-lug": ("Lug", lambda d: _broken_expression(d, "Lug", "SketchProfile")),
    "be-pedestal": ("Pedestal", lambda d: _broken_expression(d, "Pedestal", "DrivingBox")),
    "be-tab": ("Tab", lambda d: _broken_expression(d, "Tab", "AnchorPad")),
    # --- PartDesign pad whose base sketch was deleted ---
    "pd-panel-pad": ("PanelPad", lambda d: _pad_missing_sketch(d, "PanelPad", 10.0)),
    "pd-web-pad": ("WebPad", lambda d: _pad_missing_sketch(d, "WebPad", 6.0)),
    "pd-boss-pad": ("BossPad", lambda d: _pad_missing_sketch(d, "BossPad", 12.0)),
    "pd-rib-pad": ("RibPad", lambda d: _pad_missing_sketch(d, "RibPad", 4.0)),
    "pd-plinth-pad": ("PlinthPad", lambda d: _pad_missing_sketch(d, "PlinthPad", 20.0)),
    "pd-wall-pad": ("WallPad", lambda d: _pad_missing_sketch(d, "WallPad", 8.0)),
    "pd-flange-pad": ("FlangePad", lambda d: _pad_missing_sketch(d, "FlangePad", 5.0)),
    # --- Part::Cut whose tool was deleted ---
    "cut-housing-bore": ("HousingBore", lambda d: _cut_missing_tool(d, "HousingBore", 5.0)),
    "cut-bracket-slot": ("BracketSlot", lambda d: _cut_missing_tool(d, "BracketSlot", 8.0)),
    "cut-plate-pocket": ("PlatePocket", lambda d: _cut_missing_tool(d, "PlatePocket", 3.0)),
    "cut-block-hole": ("BlockHole", lambda d: _cut_missing_tool(d, "BlockHole", 6.0)),
    "cut-body-recess": ("BodyRecess", lambda d: _cut_missing_tool(d, "BodyRecess", 4.0)),
    "cut-cap-notch": ("CapNotch", lambda d: _cut_missing_tool(d, "CapNotch", 7.0)),
    "cut-frame-cutout": ("FrameCutout", lambda d: _cut_missing_tool(d, "FrameCutout", 9.0)),
}


def _save(case_id: str, base_dir: Path) -> Path:
    obj_name, builder = CASES[case_id]
    doc = App.newDocument(case_id.replace("-", "_"))
    builder(doc)
    doc.recompute()
    obj = doc.getObject(obj_name)
    if obj is None or not obj.getStatusString():
        raise RuntimeError(f"{case_id}: object {obj_name!r} is not in error after recompute")
    case_dir = base_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    target = case_dir / "fixture.FCStd"
    doc.saveAs(str(target))
    App.closeDocument(doc.Name)
    return target


def build_all(base_dir: Path | None = None) -> list[Path]:
    base_dir = base_dir or HERE
    return [_save(case_id, base_dir) for case_id in CASES]


_BUILD_FLAG = "FREECAD_BUDDY_BUILD_BROKEN_DOCS"


def _build_requested() -> bool:
    """Whether an explicit opt-in asked for a fixture rebuild (import never does)."""
    return os.environ.get(_BUILD_FLAG) == "1"


if _build_requested():
    for path in build_all():
        print(f"wrote {path}")
