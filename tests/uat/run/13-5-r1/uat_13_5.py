"""TC-07-11 / TC-07-12 MCP steps for Story 13-5, run 13-5-r1, against the fcb-desktop proxy."""
import json, os, shutil, sys, zipfile, re
sys.path.insert(0, r"D:\Work\Personal\Sources\fcb-verify-13-5\tests\uat\runner")
from mcp_client import McpClient

HOST = r"D:\Work\Personal\Sources\fcb-verify-13-5\tests\uat\run\13-5-r1\evidence"
CT = "/repo/tests/uat/run/13-5-r1/evidence"
LOG = []


def call(c, tool, args, step):
    r = c.call(tool, args)
    LOG.append({"step": step, "tool": tool, "args": args, "result": r})
    st = r.get("status") if isinstance(r, dict) else None
    det = json.dumps(r.get("detail"))[:200] if isinstance(r, dict) else str(r)[:200]
    print(f"[{step}] {tool} -> {st} {det}")
    return r


def sc(r):
    return r.get("structured_content") or {}


def short(r):
    return [(ch["id"], ch["passed"], ch.get("measured")) for ch in sc(r).get("checks", [])]


def msg(r):
    return (r.get("detail") or {}).get("message")


BUILD = (
    "a = doc.addObject('Part::Box', 'BoxA'); a.Label = 'Alpha'; b = doc.addObject('Part::Cylinder', 'Cyl'); "
    "b.Label = 'Beta'; b.Placement.Base = App.Vector(30, 0, 0); c = doc.addObject('Part::Sphere', 'Sph'); "
    "c.Label = 'Gamma'; c.Placement.Base = App.Vector(0, 60, 0); doc.recompute()"
)
NAMES = ["BoxA", "Cyl", "Sph"]
OUT = {}
with McpClient("http://127.0.0.1:18765/mcp") as c:
    caps = sc(call(c, "query_capabilities", {}, "pre"))
    OUT["freecad_version"] = caps.get("freecad_version")
    # ---- TC-07-11
    H = sc(call(c, "document_create", {"label": "tc07_three_bodies"}, "11.given"))["doc"]
    call(c, "script_exec", {"doc": H, "code": BUILD}, "11.given")
    OUT["tree"] = call(c, "query_tree_summary", {"doc": H}, "11.given")
    call(c, "view_fit_viewport", {"doc": H}, "11.given")
    ids = {}
    for fmt in ("step", "stl", "3mf"):
        w = call(c, f"export_{fmt}", {"doc": H, "path": f"{CT}/tc-07-11-three.{fmt}", "objects": NAMES}, "11.when")
        OUT[f"11.write.{fmt}"] = {"status": w["status"], "verified": sc(w).get("verified"), "objects": sc(w).get("objects")}
        ids[fmt] = sc(w)["export_id"]
    for fmt in ("step", "stl", "3mf"):
        v = call(c, f"verify_export_{fmt}", {"doc": H, "export_id": ids[fmt]}, "11.then")
        OUT[f"11.verify.{fmt}"] = {"status": v["status"], "checks": short(v)}
    for fmt in ("step", "stl", "3mf"):
        w = call(c, f"export_{fmt}", {"doc": H, "path": f"{CT}/tc-07-11-omitted.{fmt}"}, "11.omitted")
        v = call(c, f"verify_export_{fmt}", {"doc": H, "export_id": sc(w)["export_id"]}, "11.omitted")
        OUT[f"11.omitted.{fmt}"] = {"write": w["status"], "objects": sc(w).get("objects"), "verify": v["status"], "checks": short(v)}
    # planted wrong file: Beta (Cyl) is 20 mm tall in the file, 10 mm in the document
    HB = sc(call(c, "document_create", {"label": "tc07_planted_source"}, "11.planted"))["doc"]
    call(c, "script_exec", {"doc": HB, "code": BUILD.replace("doc.recompute()", "b.Height = 20; doc.recompute()")}, "11.planted")
    for fmt in ("step", "3mf"):
        call(c, f"export_{fmt}", {"doc": HB, "path": f"{CT}/tc-07-11-wrong.{fmt}", "objects": NAMES}, "11.planted")
        w = call(c, f"export_{fmt}", {"doc": H, "path": f"{CT}/tc-07-11-planted.{fmt}", "objects": NAMES}, "11.planted")
        shutil.copyfile(os.path.join(HOST, f"tc-07-11-wrong.{fmt}"), os.path.join(HOST, f"tc-07-11-planted.{fmt}"))
        v = call(c, f"verify_export_{fmt}", {"doc": H, "export_id": sc(w)["export_id"]}, "11.planted")
        OUT[f"11.planted.{fmt}"] = {
            "status": v["status"],
            "failed": [ch["id"] for ch in sc(v).get("checks", []) if not ch["passed"]],
            "message": msg(v),
        }
    call(c, "document_close", {"doc": HB}, "11.planted")
    r = call(c, "export_step", {"doc": H, "path": f"{CT}/tc-07-11-bad.step", "objects": ["BoxA", "NoSuchObject"]}, "11.unknown")
    OUT["11.unknown"] = {"status": r["status"], "message": msg(r), "file_exists": os.path.exists(os.path.join(HOST, "tc-07-11-bad.step"))}
    HE = sc(call(c, "document_create", {"label": "tc07_empty"}, "11.empty"))["doc"]
    r = call(c, "export_step", {"doc": HE, "path": f"{CT}/tc-07-11-empty.step"}, "11.empty")
    OUT["11.empty"] = {"status": r["status"], "message": msg(r)}
    call(c, "document_close", {"doc": HE}, "11.empty")
    HRT = sc(call(c, "document_create", {"label": "tc07_11_rt"}, "11.reimport"))["doc"]
    call(c, "script_exec", {"doc": HRT, "code": f"o = doc.addObject('Part::Feature', 'Reimport'); o.Shape = Part.read(r'{CT}/tc-07-11-three.step'); doc.recompute()"}, "11.reimport")
    OUT["11.reimport"] = sc(call(c, "query_mass_properties", {"doc": HRT, "object": "Reimport"}, "11.reimport"))
    call(c, "document_close", {"doc": HRT}, "11.reimport")
    OUT["handles"] = {"H": H}
    # ---- TC-07-12
    H1 = sc(call(c, "document_open", {"path": "/repo/benchmarks/g0/golden-models/box-10-20-30.FCStd"}, "12.given"))["doc"]
    w = call(c, "export_step", {"doc": H1, "path": f"{CT}/tc-07-12-default.step"}, "12.when")
    v = call(c, "verify_export_step", {"doc": H1, "export_id": sc(w)["export_id"]}, "12.then")
    OUT["12.single"] = {"write": w["status"], "objects": sc(w).get("objects"), "verify": v["status"], "checks": short(v)}
    w0 = call(c, "export_step", {"doc": H1, "path": f"{CT}/tc-07-12-default-empty-list.step", "objects": []}, "12.empty_list")
    OUT["12.empty_list"] = {"write": w0["status"], "objects": sc(w0).get("objects")}
    H2 = sc(call(c, "document_create", {"label": "tc07_two_objects"}, "12.two"))["doc"]
    call(c, "script_exec", {"doc": H2, "code": "doc.addObject('Part::Box', 'BoxA'); b = doc.addObject('Part::Box', 'BoxB'); b.Placement.Base = App.Vector(20, 0, 0); doc.recompute()"}, "12.two")
    w = call(c, "export_step", {"doc": H2, "path": f"{CT}/tc-07-12-default-compound.step"}, "12.two")
    v = call(c, "verify_export_step", {"doc": H2, "export_id": sc(w)["export_id"]}, "12.two")
    OUT["12.two"] = {"write": w["status"], "objects": sc(w).get("objects"), "verify": v["status"], "checks": short(v)}
    call(c, "script_exec", {"doc": H2, "code": "doc.getObject('BoxB').Visibility = False"}, "12.hidden")
    w = call(c, "export_step", {"doc": H2, "path": f"{CT}/tc-07-12-default-compound.step"}, "12.hidden")
    OUT["12.hidden"] = {"write": w["status"], "objects": sc(w).get("objects")}
    HRT = sc(call(c, "document_create", {"label": "tc07_12_rt"}, "12.reimport"))["doc"]
    call(c, "script_exec", {"doc": HRT, "code": f"o = doc.addObject('Part::Feature', 'Reimport'); o.Shape = Part.read(r'{CT}/tc-07-12-default.step'); doc.recompute()"}, "12.reimport")
    OUT["12.reimport"] = sc(call(c, "query_mass_properties", {"doc": HRT, "object": "Reimport"}, "12.reimport"))
    call(c, "view_fit_viewport", {"doc": HRT}, "12.visual")
    OUT["handles"].update({"H1": H1, "H2": H2, "HRT12": HRT})


def prod(p):
    return re.findall(r"PRODUCT\('[^']*','([^']*)'", open(p, errors="replace").read())


OUT["11.step_products"] = prod(os.path.join(HOST, "tc-07-11-three.step"))
with zipfile.ZipFile(os.path.join(HOST, "tc-07-11-three.3mf")) as z:
    OUT["11.3mf_object_tags"] = re.findall(r"<object[^>]*>", z.read("3D/3dmodel.model").decode())
json.dump(LOG, open(os.path.join(HOST, "mcp-log.json"), "w"), indent=1, default=str)
json.dump(OUT, open(os.path.join(HOST, "summary.json"), "w"), indent=1, default=str)
print(json.dumps(OUT, indent=1, default=str)[:15000])
