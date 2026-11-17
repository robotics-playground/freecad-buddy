"""TC-07 agent-driven scenarios for phase P6, one function per step group: p6_tc07.py <name> [arg ...].
FreeCAD runs with the default settings (auto-approve on, script_exec on). Every MCP call is logged
to evidence/<tag>-mcp.jsonl through p5_lib.Run5. The GUI steps (Show All, Fit All fallback, capture)
run through p1_gui.py / p2_gui.py; the agent reads every capture."""

import json
import os
import sys
from pathlib import Path

from p5_lib import Run5

EVIDENCE = Path(__file__).resolve().parent
REPO = EVIDENCE.parents[4]
GOLDEN = REPO / "benchmarks" / "g0" / "golden-models"
FAULT = REPO / "benchmarks" / "g0" / "fault-injection"
EV = str(EVIDENCE)


def out(label, value):
    print(f"CHECK {label}: {json.dumps(value, ensure_ascii=False)[:2500]}")


def sc(result):
    return result.get("structured_content") or {}


def msg(result):
    detail = result.get("detail")
    return detail.get("message") if isinstance(detail, dict) else None


def checks(result):
    return {c.get("id"): c for c in (sc(result).get("checks") or [])}


def ev(name):
    return str(EVIDENCE / name)


def open_golden(run, path, label="given open"):
    r = run.call("document_open", {"path": str(path)}, label)
    doc = sc(r).get("doc")
    t = run.call("query_tree_summary", {"doc": doc}, f"{label} tree")
    text = t.get("text") or json.dumps(t)
    first = text.strip().splitlines()[0] if text.strip() else ""
    print("TREE FIRST LINE:", first)
    return doc, t


def reimport(run, label, path, kind):
    r = run.call("document_create", {"label": label}, "reimport create")
    doc = sc(r)["doc"]
    if kind == "step":
        code = f"o = doc.addObject('Part::Feature', 'Reimport'); o.Shape = Part.read(r'{path}'); doc.recompute()"
    else:
        code = f"import Mesh; o = doc.addObject('Mesh::Feature', 'Reimport'); o.Mesh = Mesh.Mesh(r'{path}'); doc.recompute()"
    run.call("script_exec", {"doc": doc, "code": code}, f"reimport {kind}")
    m = run.call("query_mass_properties", {"doc": doc, "object": "Reimport"}, "reimport mass")
    out("reimport volume", [m.get("status"), sc(m).get("volume")])
    print("H_RT", doc)
    return doc, m


def cmd_call(tag, tool, args_json, label="call"):
    with Run5(tag, limit=6000) as run:
        run.call(tool, json.loads(args_json), label)


def cmd_fit(tag, doc):
    with Run5(tag) as run:
        run.call("view_fit_viewport", {"doc": doc}, "fit")


def cmd_close(tag, *docs):
    with Run5(tag) as run:
        for doc in docs:
            run.call("document_close", {"doc": doc}, "cleanup close")
        r = run.call("document_list", {}, "cleanup list")
        out("open documents", [(d.get("doc"), d.get("name"), d.get("label")) for d in sc(r).get("documents", [])])


def cmd_list(tag):
    with Run5(tag) as run:
        r = run.call("document_list", {}, "list")
        out("open documents", [(d.get("doc"), d.get("name"), d.get("label")) for d in sc(r).get("documents", [])])


def cmd_open(tag, name, folder="golden"):
    path = GOLDEN / name if folder == "golden" else FAULT / folder / name
    with Run5(tag) as run:
        doc, _ = open_golden(run, path)
        print("DOC", doc)


def cmd_t04(doc, obj):
    with Run5("tc-07-04", limit=3000) as run:
        m1 = run.call("query_mass_properties", {"doc": doc, "object": obj}, "then mass before")
        r = run.call("verify_recompute", {"doc": doc}, "when verify_recompute")
        m2 = run.call("query_mass_properties", {"doc": doc, "object": obj}, "then mass after")
        s = sc(r)
        out("status/detail", [r.get("status"), r.get("detail")])
        out("checks", s.get("checks"))
        out("failing_objects", (s.get("subject") or {}).get("failing_objects"))
        out("text", r.get("text"))
        out("volume before/after", [sc(m1).get("volume"), sc(m2).get("volume")])
        out("banner", s.get("banner"))


def size(path):
    p = Path(path)
    return p.stat().st_size if p.exists() else None


def cmd_t05(doc, obj):
    with Run5("tc-07-05", limit=3000) as run:
        p242, p214 = ev("tc-07-05-ap242.step"), ev("tc-07-05-ap214.step")
        a = run.call("export_step", {"doc": doc, "path": p242, "objects": [obj], "ap": "AP242"}, "when export AP242")
        b = run.call("export_step", {"doc": doc, "path": p214, "objects": [obj], "ap": "AP214"}, "when export AP214")
        out("statuses", [a.get("status"), b.get("status")])
        out("verified", [sc(a).get("verified"), sc(b).get("verified")])
        ida, idb = sc(a).get("export_id"), sc(b).get("export_id")
        out("export_ids", [ida, idb, str(ida).startswith("fcb-export:"), str(idb).startswith("fcb-export:"), ida != idb])
        out("bytes vs stat 242", [sc(a).get("bytes"), size(p242)])
        out("bytes vs stat 214", [sc(b).get("bytes"), size(p214)])
        t242 = Path(p242).read_text(errors="replace")
        t214 = Path(p214).read_text(errors="replace")
        out("grep 242", [t242.count("AP242_MANAGED_MODEL_BASED_3D_ENGINEERING"), t242.count("AUTOMOTIVE_DESIGN")])
        out("grep 214", [t214.count("AUTOMOTIVE_DESIGN")])
        out("FILE_SCHEMA lines", [ln for ln in (t242 + t214).splitlines() if "FILE_SCHEMA" in ln])
        for label, eid in (("242", ida), ("214", idb)):
            v = run.call("verify_export_step", {"doc": doc, "export_id": eid}, f"then verify {label}")
            out(f"verify {label}", [v.get("status"), checks(v).get("export_step.schema")])
        c = run.call("export_step", {"doc": doc, "path": ev("tc-07-05-ap203.step"), "objects": [obj], "ap": "AP203"},
                     "then ap AP203")
        out("AP203", [c, size(ev("tc-07-05-ap203.step"))])
        out("text 242", [a.get("text"), f"STEP export written -> {p242}."])
        out("text equal", a.get("text") == f"STEP export written -> {p242}.")
        rt, m = reimport(run, "tc-07-05_rt", p242, "step")
        vol = (sc(m).get("volume") or {}).get("value")
        out("reimport within 0.1% of 6000", [vol, vol is not None and abs(vol - 6000) <= 6])


def cmd_t06(doc, obj):
    with Run5("tc-07-06", limit=3000) as run:
        pstl, p3mf = ev("tc-07-06-same.stl"), ev("tc-07-06-same.3mf")
        a = run.call("export_stl", {"doc": doc, "path": pstl, "objects": [obj], "linear": 0.1, "angular": 0.5},
                     "when export_stl")
        b = run.call("export_3mf", {"doc": doc, "path": p3mf, "objects": [obj], "linear": 0.1, "angular": 0.5},
                     "when export_3mf")
        out("statuses", [a.get("status"), b.get("status")])
        out("facets stl/3mf", [sc(a).get("facets"), sc(b).get("facets"), sc(a).get("facets") == sc(b).get("facets")])
        out("verified", [sc(a).get("verified"), sc(b).get("verified")])
        out("sizes", [size(pstl), size(p3mf)])
        va = run.call("verify_export_stl", {"doc": doc, "export_id": sc(a).get("export_id")}, "then verify stl")
        vb = run.call("verify_export_3mf", {"doc": doc, "export_id": sc(b).get("export_id")}, "then verify 3mf")
        out("verify statuses", [va.get("status"), vb.get("status")])
        out("self_read.facet_count stl", checks(va).get("self_read.facet_count"))
        out("self_read.facet_count 3mf", checks(vb).get("self_read.facet_count"))
        z = run.call("export_stl", {"doc": doc, "path": ev("tc-07-06-zero.stl"), "objects": [obj], "linear": 0.1,
                                    "angular": 0}, "then angular 0")
        out("angular 0", [z.get("status"), msg(z), size(ev("tc-07-06-zero.stl"))])
        reimport(run, "tc-07-06_rt", pstl, "stl")


def cmd_t07(doc, obj):
    with Run5("tc-07-07", limit=3000) as run:
        path = ev("tc-07-07-rt.step")
        e = run.call("export_step", {"doc": doc, "path": path, "objects": [obj]}, "when export_step")
        eid = sc(e).get("export_id")
        v = run.call("verify_export_step", {"doc": doc, "export_id": eid}, "when verify_export_step")
        s, c = sc(v), checks(v)
        out("status/verdict", [v.get("status"), s.get("verdict")])
        out("check ids", [x.get("id") for x in s.get("checks") or []])
        out("schema", c.get("export_step.schema"))
        out("volume", c.get("export_step.volume"))
        vol = (c.get("export_step.volume") or {}).get("measured")
        out("volume within 0.1% of 15214.6018", isinstance(vol, (int, float)) and abs(vol - 15214.6018) <= 15.2146)
        out("valid", c.get("export_step.valid"))
        out("topology", c.get("export_step.topology_counts"))
        out("subject", [s.get("subject"), eid, path])
        lst = run.call("document_list", {}, "then document_list")
        out("FCB_TMP names", [d.get("name") for d in sc(lst).get("documents", []) if str(d.get("name", "")).startswith("FCB_TMP_")])
        out("all docs", [(d.get("doc"), d.get("name")) for d in sc(lst).get("documents", [])])
        rt, m = reimport(run, "tc-07-07_rt", path, "step")
        rv = (sc(m).get("volume") or {}).get("value")
        out("reimport within 0.1% of 15214.6018", [rv, rv is not None and abs(rv - 15214.6018) <= 15.2146])


def cmd_t08(doc, obj):
    with Run5("tc-07-08", limit=3000) as run:
        path = ev("tc-07-08-legs.stl")
        e = run.call("export_stl", {"doc": doc, "path": path, "objects": [obj]}, "when export_stl")
        eid = sc(e).get("export_id")
        v = run.call("verify_export_stl", {"doc": doc, "export_id": eid}, "when verify_export_stl")
        s, c = sc(v), checks(v)
        out("status", v.get("status"))
        ids = [x.get("id") for x in s.get("checks") or []]
        out("check ids", ids)
        for group in (["trimesh_stl.watertight", "trimesh_stl.winding_consistent", "trimesh_stl.is_volume",
                       "trimesh_stl.volume_band", "trimesh_stl.euler"],
                      ["stl2.facets", "stl2.manifold_edge_pairing", "stl2.local_winding", "stl2.non_degenerate"]):
            out("present " + group[0].split(".")[0], {g: g in ids for g in group})
        out("self_read", [c.get("self_read.facet_count"), c.get("self_read.vertex_count")])
        out("oracle.agreement", c.get("oracle.agreement"))
        out("volume_band / expected (2/3)*0.1*2200", [s.get("volume_band"), 2 / 3 * 0.1 * 2200])
        out("trimesh_stl.volume_band", c.get("trimesh_stl.volume_band"))
        out("tess", s.get("tess"))
        out("export result keys", sorted(sc(e)))
        print("EID", eid)


def cmd_t08b(doc, obj, eid):
    with Run5("tc-07-08", limit=3000) as run:
        path = ev("tc-07-08-legs.stl")
        data = Path(path).read_bytes()
        Path(path).write_bytes(data[:100])
        out("truncated size", size(path))
        v = run.call("verify_export_stl", {"doc": doc, "export_id": eid}, "then verify truncated")
        out("truncated verify", [v.get("status"), msg(v), [(x.get("id"), x.get("passed")) for x in sc(v).get("checks") or []]])
        e = run.call("export_stl", {"doc": doc, "path": path, "objects": [obj]}, "then re-export intact")
        out("re-export", [e.get("status"), sc(e).get("bytes"), size(path)])


def cmd_t09(doc, obj):
    with Run5("tc-07-09", limit=3000) as run:
        path = ev("tc-07-09-legs.3mf")
        e = run.call("export_3mf", {"doc": doc, "path": path, "objects": [obj]}, "when export_3mf")
        v = run.call("verify_export_3mf", {"doc": doc, "export_id": sc(e).get("export_id")}, "when verify_export_3mf")
        s, c = sc(v), checks(v)
        out("status", v.get("status"))
        ids = [x.get("id") for x in s.get("checks") or []]
        out("check ids", ids)
        for want in (["lib3mf.parses", "lib3mf.unit_millimeter", "lib3mf.manifold_and_oriented", "lib3mf.metadata_present"],
                     ["trimesh_3mf.watertight", "trimesh_3mf.winding_consistent", "trimesh_3mf.is_volume",
                      "trimesh_3mf.volume_band", "trimesh_3mf.euler"]):
            out("present", {g: g in ids for g in want})
        for k in ("lib3mf.unit_millimeter", "lib3mf.manifold_and_oriented", "lib3mf.metadata_present",
                  "self_read.facet_count", "self_read.vertex_count", "oracle.agreement", "trimesh_3mf.volume_band"):
            out(k, c.get(k))
        out("volume_band / expected", [s.get("volume_band"), 2 / 3 * 0.1 * 785.398])
        measured = (c.get("trimesh_3mf.volume_band") or {}).get("measured")
        out("measured within band of 1570.7963", [measured, measured is not None and abs(measured - 1570.7963) <= (s.get("volume_band") or 0)])


def cmd_t10(doc, obj):
    with Run5("tc-07-10", limit=3000) as run:
        pc, pf = ev("tc-07-10-coarse.stl"), ev("tc-07-10-fine.stl")
        c = run.call("export_stl", {"doc": doc, "path": pc, "objects": [obj], "linear": 0.5, "angular": 1.0}, "when coarse")
        f = run.call("export_stl", {"doc": doc, "path": pf, "objects": [obj], "linear": 0.01, "angular": 0.1}, "when fine")
        vc = run.call("verify_export_stl", {"doc": doc, "export_id": sc(c).get("export_id")}, "when verify coarse")
        vf = run.call("verify_export_stl", {"doc": doc, "export_id": sc(f).get("export_id")}, "when verify fine")
        out("facets coarse/fine", [sc(c).get("facets"), sc(f).get("facets"), (sc(f).get("facets") or 0) > (sc(c).get("facets") or 0)])
        out("verify statuses", [vc.get("status"), vf.get("status")])
        bc, bf = sc(vc).get("volume_band"), sc(vf).get("volume_band")
        out("bands coarse/fine/ratio", [bc, bf, bc / bf if bc and bf else None, 2 / 3 * 0.5 * 1256.64, 2 / 3 * 0.01 * 1256.64])
        out("fine trimesh_stl.volume_band", checks(vf).get("trimesh_stl.volume_band"))
        cc = checks(vc).get("trimesh_stl.volume_band")
        out("coarse trimesh_stl.volume_band", cc)
        out("coarse measured < 4188.7902 and passed", [(cc or {}).get("measured", 1e9) < 4188.7902, (cc or {}).get("passed")])
        fl = run.call("export_stl", {"doc": doc, "path": ev("tc-07-10-floor.stl"), "objects": [obj], "linear": 0.00001},
                      "then floor")
        out("floor", [fl.get("status"), msg(fl), Path(ev("tc-07-10-floor.stl")).exists()])


def cmd_t11(doc, obj):
    with Run5("tc-07-11", limit=3000) as run:
        rows = []
        for tool, ext in (("export_step", "step"), ("export_stl", "stl"), ("export_3mf", "3mf")):
            r = run.call(tool, {"doc": doc, "path": ev(f"tc-07-11-multi.{ext}"), "objects": [obj, obj]}, f"when {tool} multi")
            rows.append([tool, r.get("status"), msg(r)])
        out("multi", rows)
        out("message equal", [m == "export supports a single object; got multiple" for _, _, m in rows])
        out("multi files exist", [Path(ev(f"tc-07-11-multi.{e}")).exists() for e in ("step", "stl", "3mf")])
        u = run.call("export_step", {"doc": doc, "path": ev("tc-07-11-unknown.step"), "objects": ["NoSuchObject"]},
                     "then unknown object")
        out("unknown", [u.get("status"), msg(u), Path(ev("tc-07-11-unknown.step")).exists()])
        e = run.call("document_create", {"label": "tc07_11_empty"}, "then create empty")
        edoc = sc(e).get("doc")
        x = run.call("export_step", {"doc": edoc, "path": ev("tc-07-11-empty.step")}, "then export empty doc")
        out("empty", [x.get("status"), msg(x), Path(ev("tc-07-11-empty.step")).exists()])
        run.call("document_close", {"doc": edoc}, "close the empty scratch document")


def cmd_t12(doc):
    with Run5("tc-07-12", limit=3000) as run:
        path, comp = ev("tc-07-12-default.step"), ev("tc-07-12-default-compound.step")
        a = run.call("export_step", {"doc": doc, "path": path}, "when export objects omitted")
        h2 = sc(run.call("document_create", {"label": "tc07_two_objects"}, "when create H2")).get("doc")
        run.call("script_exec", {"doc": h2, "code": "doc.addObject('Part::Box', 'BoxA'); b = doc.addObject('Part::Box', 'BoxB'); "
                                 "b.Placement.Base = App.Vector(20, 0, 0); doc.recompute()"}, "when build two boxes")
        b = run.call("export_step", {"doc": h2, "path": comp}, "when export H2 objects omitted")
        out("first export", [a.get("status"), sorted(sc(a))])
        v = run.call("verify_export_step", {"doc": doc, "export_id": sc(a).get("export_id")}, "then verify first")
        out("verify", [v.get("status"), checks(v).get("export_step.volume")])
        out("H2 export", [b.get("status"), msg(b)])
        out("H2 message equal", msg(b) == "document has multiple objects; specify 'objects' with the one to export")
        out("compound file exists", Path(comp).exists())
        c = run.call("export_step", {"doc": doc, "path": ev("tc-07-12-empty-objects.step"), "objects": []}, "then objects []")
        out("objects []", [c.get("status"), {k: v for k, v in sc(c).items() if k != "export_id"},
                           {k: v for k, v in sc(a).items() if k != "export_id"}])
        out("text first / objects[]", [a.get("text"), c.get("text")])
        reimport(run, "tc-07-12_rt", path, "step")
        print("H2", h2)


def cmd_t13(h1, o1, h2, o2):
    with Run5("tc-07-13", limit=3000) as run:
        g = run.call("verify_shape", {"doc": h1, "object": o1, "checks": [
            {"fn": "expect_volume", "expect": 15214.6018, "tol": {"rel": 0.001}},
            {"fn": "expect_solid_count", "expect": 1}, {"fn": "expect_watertight", "expect": True}]}, "when grade genus-1")
        path = ev("tc-07-13-genus.stl")
        e = run.call("export_stl", {"doc": h1, "path": path, "objects": [o1]}, "when export genus STL")
        v = run.call("verify_export_stl", {"doc": h1, "export_id": sc(e).get("export_id")}, "when verify genus STL")
        c = run.call("verify_shape", {"doc": h2, "object": o2, "checks": [
            {"fn": "expect_volume", "expect": 2000.0, "tol": {"rel": 0.001}},
            {"fn": "expect_solid_count", "expect": 2}]}, "when grade compound")
        m = run.call("query_mass_properties", {"doc": h2, "object": o2}, "when compound mass")
        out("genus grade", [g.get("status"), checks(g).get("assert.expect_volume"), [(x.get("id"), x.get("passed")) for x in sc(g).get("checks") or []]])
        out("genus stl verify", [v.get("status"), checks(v).get("trimesh_stl.euler")])
        out("compound grade", [c.get("status"), checks(c).get("shape.solid_count"), checks(c).get("assert.expect_volume")])
        out("compound mass", [m.get("status"), "com" in sc(m), sc(m).get("com"), sorted(sc(m))])
        w = run.call("verify_shape", {"doc": h2, "object": o2, "checks": [{"fn": "expect_watertight", "expect": True}]},
                     "then compound watertight")
        out("compound watertight", [w.get("status"), checks(w).get("shape.watertight")])


def cmd_t14(doc, obj):
    with Run5("tc-07-14", limit=3000) as run:
        upath = ev("tc-07-14 exports/boîte-立方体.step").replace("/", "\\")
        lpath = ev("tc-07-14 exports/" + "a" * 200 + ".step").replace("/", "\\")
        a = run.call("export_step", {"doc": doc, "path": upath, "objects": [obj]}, "when unicode export")
        b = run.call("export_step", {"doc": doc, "path": lpath, "objects": [obj]}, "when long-name export")
        out("unicode export", [a.get("status"), msg(a)])
        out("unicode file exists", [Path(upath).exists(), sorted(p.name for p in Path(upath).parent.iterdir())[:5]])
        out("path echoed", [sc(a).get("path"), sc(a).get("path") == upath])
        va = run.call("verify_export_step", {"doc": doc, "export_id": sc(a).get("export_id")}, "then verify unicode")
        out("unicode verify", [va.get("status"), (sc(va).get("subject") or {}).get("path") == upath, (sc(va).get("subject") or {}).get("path")])
        out("bytes vs stat", [sc(a).get("bytes"), size(upath)])
        out("long export", [b.get("status"), msg(b), len(lpath), os.path.exists("\\\\?\\" + lpath)])
        if b.get("status") == "OK":
            vb = run.call("verify_export_step", {"doc": doc, "export_id": sc(b).get("export_id")}, "then verify long")
            out("long verify", [vb.get("status"), msg(vb)])
        reimport(run, "tc-07-14_rt", upath, "step")


def cmd_t15(doc, obj):
    with Run5("tc-07-15", limit=3000) as run:
        path = ev("tc-07-15-over.stl")
        rows = []
        results = []
        for label, linear in (("coarse", 0.5), ("fine", 0.01), ("coarse again", 0.5)):
            r = run.call("export_stl", {"doc": doc, "path": path, "objects": [obj], "linear": linear}, f"when {label}")
            results.append(r)
            rows.append([label, r.get("status"), sc(r).get("bytes"), size(path), sc(r).get("facets"), sc(r).get("export_id")])
            if label == "fine":
                stale = run.call("verify_export_stl", {"doc": doc, "export_id": sc(results[0]).get("export_id")},
                                 "then stale coarse id after fine write")
                out("stale verify", [stale.get("status"), msg(stale), checks(stale).get("self_read.facet_count")])
        out("writes [label, status, bytes, stat, facets, export_id]", rows)
        b1, b2 = rows[0][2], rows[1][2]
        out("after fine stat == B2, != B1+B2", [rows[1][3] == b2, rows[1][3] != (b1 or 0) + (b2 or 0)])
        out("third bytes == B1, facets == coarse", [rows[2][2] == b1, rows[2][4] == rows[0][4]])
        out("ids distinct", len({r[5] for r in rows}) == 3)
        reimport(run, "tc-07-15_rt", path, "stl")


def cmd_t16(doc, obj):
    with Run5("tc-07-16", limit=3000) as run:
        calls = [
            ("export_step", {"path": ev("tc-07-16-fail-multi.step"), "objects": [obj, obj]}),
            ("export_step", {"path": ev("tc-07-16-fail-unknown.step"), "objects": ["NoSuchObject"]}),
            ("export_stl", {"path": ev("tc-07-16-fail-defl.stl"), "objects": [obj], "linear": 0.00001}),
            ("export_3mf", {"path": ev("tc-07-16-fail-defl.3mf"), "objects": [obj], "angular": 0.0}),
            ("export_step", {"path": ev("tc-07-16-no-such-dir/x.step").replace("/", "\\"), "objects": [obj]}),
        ]
        rows = []
        for tool, args in calls:
            r = run.call(tool, {"doc": doc, **args}, f"when {tool} {Path(args['path']).name}")
            rows.append([tool, Path(args["path"]).name, r.get("status"), msg(r), "export_id" in sc(r)])
        out("failures [tool, file, status, message, has export_id]", rows)
        out("fail files", sorted(p.name for p in EVIDENCE.glob("tc-07-16-fail-*")))
        out("no-such-dir exists", (EVIDENCE / "tc-07-16-no-such-dir").exists())
        ok = run.call("export_step", {"doc": doc, "path": ev("tc-07-16-fail-multi.step"), "objects": [obj]}, "then recovery export")
        out("recovery", [ok.get("status"), Path(ev("tc-07-16-fail-multi.step")).exists(), size(ev("tc-07-16-fail-multi.step"))])
        reimport(run, "tc-07-16_rt", ev("tc-07-16-fail-multi.step"), "step")


def cmd_t17(doc, obj):
    with Run5("tc-07-17", limit=3000) as run:
        rows = []
        for tool in ("verify_export_step", "verify_export_stl", "verify_export_3mf"):
            r = run.call(tool, {"doc": doc, "export_id": "fcb-export:bogus"}, f"when {tool} bogus")
            rows.append([tool, r.get("status"), msg(r), ((r.get("detail") or {}).get("data") or {}).get("exception")])
        out("bogus [tool, status, message, exception]", rows)
        out("message equal", [x[2] == "unknown or stale export_id: fcb-export:bogus" for x in rows])
        e = run.call("export_stl", {"doc": doc, "path": ev("tc-07-17-stale.stl"), "objects": [obj]}, "when export stale STL")
        eid = sc(e).get("export_id")
        run.call("document_close", {"doc": doc}, "when close H")
        h2 = sc(run.call("document_open", {"path": str(GOLDEN / "box-10-20-30.FCStd")}, "when reopen as H2")).get("doc")
        s = run.call("verify_export_stl", {"doc": h2, "export_id": eid}, "when verify old id against H2")
        out("export", [e.get("status"), eid])
        out("reopened", [h2, h2 != doc, s.get("status"), msg(s)])
        out("reopened message shape", [str(msg(s)).startswith("export_id "), "does not belong to document" in str(msg(s))])
        z = run.call("verify_export_step", {"doc": h2, "export_id": ""}, "then empty export_id")
        out("empty", [z.get("status"), msg(z), z.get("text") if "status" not in z else None])
        q = run.call("query_capabilities", {}, "then no crash", quiet=True)
        out("query_capabilities", q.get("status"))
        print("H2", h2)


def cmd_t18(doc, obj):
    with Run5("tc-07-18", limit=3000) as run:
        paths = {f: ev(f"tc-07-18-x.{f}") for f in ("step", "stl", "3mf")}
        ids = {}
        for f in ("step", "stl", "3mf"):
            r = run.call(f"export_{f}", {"doc": doc, "path": paths[f], "objects": [obj]}, f"given export {f}")
            ids[f] = sc(r).get("export_id")
            out(f"given {f}", [r.get("status"), ids[f]])
        before = {f: size(p) for f, p in paths.items()}
        out("sizes before", before)
        rows = []
        for verifier, foreign in (("step", "stl"), ("step", "3mf"), ("stl", "step"), ("stl", "3mf"), ("3mf", "step"), ("3mf", "stl")):
            r = run.call(f"verify_export_{verifier}", {"doc": doc, "export_id": ids[foreign]}, f"when {verifier} with {foreign} id")
            rows.append([verifier, foreign, r.get("status"), msg(r), "checks" in sc(r), sc(r)])
            expect = f"export_id {ids[foreign]} is not a {verifier} export"
            out(f"{verifier}<-{foreign}", [r.get("status"), msg(r), msg(r) == expect, "checks" in sc(r), sc(r)])
        own = []
        for f in ("step", "stl", "3mf"):
            r = run.call(f"verify_export_{f}", {"doc": doc, "export_id": ids[f]}, f"then {f} own id")
            own.append([f, r.get("status")])
        out("own", own)
        out("sizes after == before", [{f: size(p) for f, p in paths.items()}, {f: size(p) for f, p in paths.items()} == before])
        reimport(run, "tc-07-18_rt", paths["step"], "step")


def cmd_t19():
    with Run5("tc-07-19", limit=3000) as run:
        ha, ta = open_golden(run, GOLDEN / "box-10-20-30.FCStd", "given open HA")
        hb, tb = open_golden(run, GOLDEN / "sphere-r10.FCStd", "given open HB")
        lst = run.call("document_list", {}, "given list")
        out("list", [d.get("doc") for d in sc(lst).get("documents", [])] + [ha, hb])
        pa, pb = ev("tc-07-19-own.step"), ev("tc-07-19-own-b.step")
        e = run.call("export_step", {"doc": ha, "path": pa, "objects": ["Box"]}, "when export HA")
        ea = sc(e).get("export_id")
        x = run.call("verify_export_step", {"doc": hb, "export_id": ea}, "when verify EID_A against HB")
        out("crossed", [x.get("status"), msg(x), msg(x) == f"export_id {ea} does not belong to document {hb}",
                        "checks" in sc(x), "subject" in sc(x), sc(x)])
        ok = run.call("verify_export_step", {"doc": ha, "export_id": ea}, "then correct pairing")
        out("correct pairing", ok.get("status"))
        eb = sc(run.call("export_step", {"doc": hb, "path": pb, "objects": ["Sphere"]}, "then export HB")).get("export_id")
        y = run.call("verify_export_step", {"doc": ha, "export_id": eb}, "then verify EID_B against HA")
        out("symmetric", [y.get("status"), msg(y), msg(y) == f"export_id {eb} does not belong to document {ha}"])
        ra = run.call("verify_recompute", {"doc": ha}, "then recompute HA")
        rb = run.call("verify_recompute", {"doc": hb}, "then recompute HB")
        out("recompute", [ra.get("status"), rb.get("status")])
        rt, m = reimport(run, "tc-07-19_rt", pa, "step")
        print("HA", ha, "HB", hb)


def tree_object(tree):
    lines = [ln for ln in (tree.get("text") or "").splitlines() if ln.startswith("- [")]
    return lines[0].split("] ", 1)[1].strip() if lines else None


def cmd_t20():
    with Run5("tc-07-20", limit=3000) as run:
        h, t = open_golden(run, FAULT / "wrong-volume" / "fixture.FCStd", "when open wrong-volume")
        o = tree_object(t)
        a = run.call("verify_shape", {"doc": h, "object": o, "checks": [{"fn": "expect_volume", "expect": 6000, "tol": {"rel": 0.001}}]},
                     "when grade wrong-volume")
        h2, t2 = open_golden(run, FAULT / "non-watertight-open-shell" / "fixture.FCStd", "when open open-shell")
        o2 = tree_object(t2)
        b = run.call("verify_shape", {"doc": h2, "object": o2, "checks": [{"fn": "expect_watertight", "expect": True},
                                                                         {"fn": "expect_solid_count", "expect": 1}]},
                     "when grade open-shell")
        out("objects", [o, o2])
        out("wrong-volume", [a.get("status"), checks(a).get("assert.expect_volume"), a.get("detail")])
        out("open-shell", [b.get("status"), checks(b).get("shape.watertight"), checks(b).get("shape.solid_count"), b.get("detail")])
        bare = run.call("verify_shape", {"doc": h, "object": o}, "then bare checks on wrong-volume")
        out("bare", [bare.get("status"), [(x.get("id"), x.get("measured"), x.get("passed")) for x in sc(bare).get("checks") or []]])
        hc, tc = open_golden(run, FAULT / "clean-control" / "fixture.FCStd", "then open clean-control")
        oc = tree_object(tc)
        c = run.call("verify_shape", {"doc": hc, "object": oc, "checks": [
            {"fn": "expect_volume", "expect": 6000, "tol": {"rel": 0.001}},
            {"fn": "expect_bbox", "expect": [10, 20, 30], "tol": {"rel": 0.001}},
            {"fn": "expect_solid_count", "expect": 1}]}, "then grade clean-control")
        out("clean-control", [oc, c.get("status"), [(x.get("id"), x.get("passed")) for x in sc(c).get("checks") or []]])
        ew = run.call("export_stl", {"doc": h, "path": ev("tc-07-20-wrong-volume.stl"), "objects": [o]}, "then export wrong-volume STL")
        eo = run.call("export_stl", {"doc": h2, "path": ev("tc-07-20-open-shell.stl"), "objects": [o2]}, "then export open-shell STL")
        out("exports", [[ew.get("status"), msg(ew)], [eo.get("status"), msg(eo)]])
        run.call("document_close", {"doc": hc}, "close clean-control (scratch for its Then)")
        print("H", h, "H2", h2)


def cmd_t21(doc, obj):
    closed = {"OK", "SPEC_FAILED", "RECOMPUTE_ERROR", "TIMEOUT", "OOM_KILLED", "WORKER_CRASHED", "INVALID_INPUT"}
    with Run5("tc-07-21", limit=3000) as run:
        statuses = []
        writes, verifies = {}, {}
        for f in ("step", "stl", "3mf"):
            p = ev(f"tc-07-21-pair.{f}")
            w = run.call(f"export_{f}", {"doc": doc, "path": p, "objects": [obj]}, f"when export {f}")
            writes[f] = w
            statuses.append(w.get("status"))
            out(f"write {f}", [w.get("status"), sc(w).get("verified"), w.get("text"), str(w.get("text")).endswith(f"export written -> {p}."),
                               "checks" in sc(w), w.get("schema"), sc(w).get("schema"), sorted(sc(w))])
        for f in ("step", "stl", "3mf"):
            v = run.call(f"verify_export_{f}", {"doc": doc, "export_id": sc(writes[f]).get("export_id")}, f"when verify {f}")
            verifies[f] = v
            statuses.append(v.get("status"))
            out(f"verify {f}", [v.get("status"), v.get("schema"), sc(v).get("schema"), sc(v).get("verdict"),
                                all(x.get("passed") for x in sc(v).get("checks") or []), len(sc(v).get("checks") or [])])
        pstl = ev("tc-07-21-pair.stl")
        before = json.dumps(writes["stl"], sort_keys=True)
        Path(pstl).write_bytes(b"")
        out("truncated size", size(pstl))
        t = run.call("verify_export_stl", {"doc": doc, "export_id": sc(writes["stl"]).get("export_id")}, "then verify truncated stl")
        statuses.append(t.get("status"))
        out("truncated verify", [t.get("status"), msg(t)])
        out("write result unchanged", json.dumps(writes["stl"], sort_keys=True) == before)
        out("statuses / closed", [statuses, all(s in closed for s in statuses)])
        reimport(run, "tc-07-21_rt", ev("tc-07-21-pair.step"), "step")


def cmd_rt(tag, label, path, kind):
    with Run5(tag, limit=3000) as run:
        reimport(run, label, path, kind)


if __name__ == "__main__":
    globals()["cmd_" + sys.argv[1]](*sys.argv[2:])
