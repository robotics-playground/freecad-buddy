import subprocess, pathlib, sys
ROOT = pathlib.Path(r"D:\Work\Personal\Sources\fcb-verify-13-7")
S = pathlib.Path(sys.argv[1])
Q = "src/freecad_buddy/usecases/queries.py"; C = "src/freecad_buddy/hosts/tool_catalog.py"
M = {
 "a_empty_reads_zero": [(Q, "    if not empty:\n        return 0.0, distance, False\n    return None, distance, True", "    if not empty:\n        return 0.0, distance, False\n    return 0.0, distance, False")],
 "b_drop_readonly": [(C, '        "query_mass_properties",\n        "query_interference",\n', '        "query_mass_properties",\n')],
 "c_accept_self_pair": [(Q, "        if pair[0] == pair[1]:\n            raise ValidationError(f\"a pair must name two different objects: {pair[0]}\")\n", "")],
 "d_swap_ab": [(Q, '"a": name_a,\n                    "b": name_b,', '"a": name_b,\n                    "b": name_a,')],
 "e1_code_bound_21": [(Q, "_MAX_INTERFERENCE_OBJECTS = 20", "_MAX_INTERFERENCE_OBJECTS = 21")],
 "e2_schema_bound_21": [(C, '"minItems": 2,\n                        "maxItems": 20,\n                        "description": "every pair is measured"', '"minItems": 2,\n                        "maxItems": 21,\n                        "description": "every pair is measured"')],
}
FC = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
for name, edits in M.items():
    originals = {}
    for path, old, new in edits:
        p = ROOT / path; text = originals.setdefault(path, p.read_text(encoding="utf-8"))
        assert text.count(old) == 1, (name, path)
        p.write_text(text.replace(old, new), encoding="utf-8")
    try:
        infc = subprocess.run([FC, "-u", str(S/"fccfg/user.cfg"), "-s", str(S/"fccfg/system.cfg"), str(S/"run_interf.py")], capture_output=True, text=True, cwd=ROOT)
        out = infc.stdout + infc.stderr
        red = [l for l in out.splitlines() if l.startswith(("RED:", "RESULT", "QUERIES"))]
        ext = subprocess.run(["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", "tests/external/test_mcp_surface.py", "tests/external/test_assistant_readonly_profile.py"], capture_output=True, text=True, cwd=ROOT)
        ext_fail = [l for l in ext.stdout.splitlines() if l.startswith("FAILED") or " passed" in l or " failed" in l]
        gs = subprocess.run(["uv", "run", "python", "scripts/gen_schemas.py", "--check"], capture_output=True, text=True, cwd=ROOT)
        print(f"### {name}\n" + "\n".join(red + ext_fail) + f"\ngen_schemas --check exit={gs.returncode}\n", flush=True)
    finally:
        for path, text in originals.items():
            (ROOT / path).write_text(text, encoding="utf-8")
subprocess.run(["git", "-C", str(ROOT), "status", "--short", "src"])
