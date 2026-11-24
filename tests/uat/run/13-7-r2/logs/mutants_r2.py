import subprocess, pathlib, sys
ROOT = pathlib.Path(r"D:\Work\Personal\Sources\fcb-verify-13-7")
S = pathlib.Path(sys.argv[1])
Q = "src/freecad_buddy/usecases/queries.py"
M = {
 "RT1_drop_isValid": [(Q, "            and bool(shape.isValid())\n", "")],
 "RT2_allow_negative_solid": [(Q, "volume is not None and volume > 0 and math.isfinite(volume)", "volume is not None and volume != 0 and math.isfinite(volume)")],
 "RT3_trust_shell": [(Q, "    else:\n        yield None\n", "    else:\n        yield float(shape.Volume)\n")],
 "RT4_text_unrounded": [(Q, 'if pair.get("common_volume") and shim.displayed(pair["common_volume"]["value"])', 'if (pair.get("common_volume") or {}).get("value")')],
 "F1_no_copy": [(Q, "    return shape.copy()\n", "    return shape\n")],
 "e1_bound_21": [(Q, "_MAX_INTERFERENCE_OBJECTS = 20", "_MAX_INTERFERENCE_OBJECTS = 21")],
 "guard_off": [(Q, "if face_counts[name_a] * face_counts[name_b] > _MAX_PAIR_FACE_PRODUCT:", "if False:")],
 "deadline_off": [(Q, "if clock() - started > _CALL_DEADLINE_SECONDS:", "if False:")],
 "trust_rule_off": [(Q, "if measurable[name_a] and measurable[name_b]:\n                volume", "if True:\n                volume")],
}
FC = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
for name, edits in M.items():
    originals = {}
    for path, old, new in edits:
        p = ROOT / path; raw = originals.setdefault(path, p.read_bytes())
        text = raw.decode("utf-8")
        assert text.count(old) == 1, (name, path, text.count(old))
        p.write_bytes(text.replace(old, new).encode("utf-8"))
    try:
        out = subprocess.run([FC, "-u", str(S/"fccfg/user.cfg"), "-s", str(S/"fccfg/system.cfg"), str(S/"run_interf.py")], capture_output=True, text=True, cwd=ROOT)
        lines = [l for l in (out.stdout + out.stderr).splitlines() if l.startswith(("RED:", "RESULT"))]
        print(f"### {name}\n" + "\n".join(lines) + "\n", flush=True)
    finally:
        for path, raw in originals.items():
            (ROOT / path).write_bytes(raw)
print(subprocess.run(["git", "-C", str(ROOT), "status", "--short", "src"], capture_output=True, text=True).stdout or "src clean")
