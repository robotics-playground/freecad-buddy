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
}
# Only the input-validation test runs for e: without the floor, the malformed-points test reaches
# discretize on the straight edges of a box section, which returns, so nothing hangs.
ONLY = {"e_no_deflection_floor": "test_Should_raise_When_the_plane_or_points_are_malformed"}

original = TARGET.read_bytes().decode("utf-8")
cfg = HERE / "cfg"
try:
    for name, edits in MUTANTS.items():
        if len(sys.argv) > 1 and name not in sys.argv[1:]:
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
            capture_output=True, text=True, env=env, timeout=600,
        )
        lines = [ln for ln in (done.stdout + done.stderr).splitlines() if ln.startswith(("RED", "RESULT"))]
        print(f"== {name}")
        for line in lines:
            print("  " + line)
finally:
    TARGET.write_bytes(original.encode("utf-8"))
