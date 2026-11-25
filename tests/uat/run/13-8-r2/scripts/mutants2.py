import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path("D:/Work/Personal/Sources/fcb-verify-13-8/src/freecad_buddy/usecases/queries.py")
FREECADCMD = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"

MUTANTS = {
    "a_slice_not_section": [(
        "        edges = shape.section(plane_face).Edges\n"
        "        wires = [Part.Wire(group) for group in Part.sortEdges(edges)]\n",
        "        import FreeCAD\n"
        "        wires = shape.slice(FreeCAD.Vector(*normal), offset)\n"
        "        edges = [edge for wire in wires for edge in wire.Edges]\n",
    )],
    "b_area_zero_not_null": [(
        "        else:\n            area = None\n",
        "        else:\n            area = 0.0\n",
    )],
    "c_no_face_limit": [(
        "        if face_count > _MAX_SECTION_FACES:\n",
        "        if False:\n",
    )],
    "d1_no_max_points_cap": [(
        "        kept = vertices[:remaining]\n",
        "        kept = vertices\n",
    )],
    "d2_no_truncated_flag": [(
        "        if remaining < 2:\n            return polylines, True\n",
        "        if remaining < 2:\n            return polylines, False\n",
    ), (
        "        if len(kept) < len(vertices):\n            return polylines, True\n",
        "        if len(kept) < len(vertices):\n            return polylines, False\n",
    )],
    "e_no_deflection_floor": [(
        "            if request[0] < floor:\n",
        "            if False:\n",
    )],
    "f_no_shape_copy": [(
        "        shape = _copied_queryable_shape(document, object)\n",
        "        shape = _named_shape(document, object)\n",
    )],
    "rt1a_face_limit_10000": [("_MAX_SECTION_FACES = 3000\n", "_MAX_SECTION_FACES = 10_000\n")],
    "rt1b_no_pole_guard": [(
        "        if pole_load > _MAX_BSPLINE_POLE_LOAD:\n", "        if False:\n",
    )],
    "rt2_area_wires_1500": [("_MAX_AREA_WIRES = 300\n", "_MAX_AREA_WIRES = 1500\n")],
    "rt3a_no_area_cross_check": [(
        "            area = _checked_section_area(shape, plane_face, wires)\n",
        "            area = _section_area(shape, plane_face)\n",
    )],
    "rt3b_open_wire_allowed": [(
        "solids_only and closed == len(wires) and len(wires)", "solids_only and len(wires)",
    )],
    "rt3ab_both": [(
        "            area = _checked_section_area(shape, plane_face, wires)\n",
        "            area = _section_area(shape, plane_face)\n",
    ), (
        "solids_only and closed == len(wires) and len(wires)", "solids_only and len(wires)",
    )],
    "rt4_loose_bbox": [(
        "Part.Compound(edges).optimalBoundingBox()", "Part.Compound(edges).BoundBox",
    )],
    "rt5_no_plane_on_face": [(
        "            on_face = _plane_on_face(shape, normal, offset)\n",
        "            on_face = False\n",
    )],
    "rt5b_no_face_tolerance": [(
        "        tolerance = max(_COINCIDENT_TOLERANCE_MM, face.Tolerance)\n",
        "        tolerance = _COINCIDENT_TOLERANCE_MM\n",
    )],
    "rt5c_no_bspline_plane": [(
        "    if surface.TypeId in _BSPLINE_SURFACE_TYPES:\n        return face.findPlane()\n", "",
    )],}
# Only the input-validation test runs for e: without the floor, the malformed-points test reaches
# discretize on the straight edges of a box section, which returns, so nothing hangs.
ONLY = {"e_no_deflection_floor": "test_Should_raise_When_the_plane_or_points_are_malformed"}

original = TARGET.read_bytes().decode("utf-8")
cfg = HERE.parent / "cfg"
try:
    for name, edits in MUTANTS.items():
        if len(sys.argv) > 1 and not any(name.startswith(a) for a in sys.argv[1:]):
            continue
        text = original
        for old, new in edits:
            assert text.count(old) == 1, (name, old)
            text = text.replace(old, new)
        TARGET.write_bytes(text.encode("utf-8"))
        env = dict(os.environ)
        env.pop("ONLY_TEST", None)
        if name in ONLY:
            env["ONLY_TEST"] = ONLY[name]
        done = subprocess.run(
            [FREECADCMD, "-u", str(cfg / "user.cfg"), "-s", str(cfg / "system.cfg"),
             str(HERE / "run_section.py")],
            capture_output=True, text=True, env=env, timeout=1500,
        )
        lines = [ln for ln in (done.stdout + done.stderr).splitlines() if ln.startswith(("RED", "RESULT"))]
        print(f"== {name}")
        for line in lines:
            print("  " + line)
finally:
    TARGET.write_bytes(original.encode("utf-8"))
