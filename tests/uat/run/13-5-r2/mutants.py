"""Revert each round-2 fix in the copy, run the export tests, report the red ones, restore."""
import json, os, pathlib, re, subprocess, sys

ROOT = pathlib.Path(r"D:\Work\Personal\Sources\fcb-verify-13-5")
S = pathlib.Path(__file__).parent
FC = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
EX = "src/freecad_buddy/usecases/exports.py"
SH = "src/freecad_buddy/usecases/shim.py"
OR = "src/freecad_buddy/adapters/export_oracle.py"

MUTANTS = {
    "D-1 content types kept as written": [(EX, '''                elif info.filename == _3MF_CONTENT_TYPES_PART:
                    data = _unique_content_types(data.decode("utf-8")).encode("utf-8")
''', "")],
    "RT-1 own Visibility only (groups ignored)": [(EX, "not _is_shown(obj):", 'not getattr(obj, "Visibility", True):')],
    "RT-2 mirror consumes its source": [(EX, '''    if obj.TypeId == "Part::Mirroring":
        return []
''', "")],
    "RT-3/RT-6 control characters kept, old character references": [
        (EX, "    return escape(three_mf_object_name(text), _ATTRIBUTE_ESCAPES)",
         '    return escape(text, {\'"\': "&quot;", "\\n": "&#10;", "\\r": "&#13;", "\\t": "&#9;"})')],
    "RT-4 shared shape not copied": [(SH, "feature.Shape = shape.copy()", "feature.Shape = shape")],
    "RT-4+RT-5 writer back to Import.export(objects)": [(EX, '''                step_names = shim.export_step_objects(
                    [(obj.Label or obj.Name, shape) for obj, shape in zip(objs, shapes)],
                    document.Name,
                    path,
                )''', '''                import Import

                Import.export(objs, path, exportHidden=True, legacy=False, keepPlacement=False)
                step_names = [obj.Label or obj.Name for obj in objs]''')],
    "RT-7 whole shape graded (solid + loose face)": [(EX, "        solid_shapes.append(solids[0] if len(solids) == 1 else _one_shape(solids))",
                                                      "        solid_shapes.append(shape)")],
    "L-1 STEP name check not added": [(EX, '            checks.append(_object_names_check(entry["path"], source["objects"]))\n', "")],
    "r2 STEP escapes not decoded": [(EX, "        _STEP_ESCAPE.sub(lambda match: _STEP_ESCAPED[match.group(0)], name)", "        name")],
    "r2 wrapped lines not joined": [(EX, '        text = handle.read().replace("\\r", "").replace("\\n", "")', "        text = handle.read()")],
    "r2 root product not named after document": [(SH, 'with _scratch_document(f"{document_name}_export") as doc:',
                                                  'with _scratch_document("FCB_TMP_step_write") as doc:')],
}

INFC = S / "run_infc_export.py"
EXT = ["tests/external/test_export_oracle.py", "tests/external/test_exports_3mf_names.py",
       "tests/external/test_exports_step_names.py", "tests/external/test_mcp_surface.py"]


def run_infc():
    out = subprocess.run([FC, "-u", str(S / "cfg" / "um.cfg"), "-s", str(S / "cfg" / "sm.cfg"), str(INFC)],
                         cwd=ROOT, capture_output=True, text=True, errors="replace")
    text = out.stdout + out.stderr
    summary = re.findall(r"INFC_RESULT .*", text)
    return summary, re.findall(r"INFC_RED (\S+)", text)


def run_ext():
    out = subprocess.run(["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", *EXT],
                         cwd=ROOT, capture_output=True, text=True, errors="replace")
    text = out.stdout + out.stderr
    return re.findall(r"\d+ (?:passed|failed)[^\n]*", text)[-1:], re.findall(r"^FAILED (\S+)", text, re.M)


results = {}
only = sys.argv[1:]
for name, edits in [("baseline", [])] + list(MUTANTS.items()):
    if only and name != "baseline" and not any(o in name for o in only):
        continue
    originals = {}
    try:
        for path, old, new in edits:
            p = ROOT / path
            text = originals.setdefault(path, p.read_text(encoding="utf-8")) if path not in originals else p.read_text(encoding="utf-8")
            assert text.count(old) == 1, f"{name}: anchor count {text.count(old)} in {path}"
            p.write_text(text.replace(old, new), encoding="utf-8")
        infc = run_infc()
        ext = run_ext()
    finally:
        for path, text in originals.items():
            (ROOT / path).write_text(text, encoding="utf-8")
    results[name] = {"infc": infc, "external": ext}
    print(f"### {name}\n  infc {infc[0]} red={infc[1]}\n  ext  {ext[0]} red={ext[1]}", flush=True)
json.dump(results, open(S / "mutants.json", "w"), indent=1)
print(subprocess.run(["git", "status", "--short", "src"], cwd=ROOT, capture_output=True, text=True).stdout or "src clean")
