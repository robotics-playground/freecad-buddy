import time
from tc08lib import *  # noqa

EV = str(EVIDENCE).replace("\\", "/")
WANT = ("this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as "
        "confirm.preview_id")


def mn(obj, name):
    return {"kind": "mapped_name", "object": obj, "mapped_name": name}


CALLS = [
    ("feature_pad", {"body": "Body", "profile": "Sketch", "name": "Pad2", "length": q(30)}),
    ("feature_pocket", {"body": "Body", "profile": "Sketch", "name": "Pocket", "length": q(5)}),
    ("feature_revolve", {"body": "Body", "profile": "Sketch", "name": "Revolution", "axis": mn("Sketch", "Edge1"),
                         "angle": {"value": 90, "unit": "deg"}}),
    ("feature_hole", {"body": "Body", "profile": "Sketch", "name": "Hole", "diameter": q(5), "depth": q(5)}),
    ("feature_fillet", {"body": "Body", "base": "Fillet", "name": "Fillet2", "edges": [mn("Fillet", "Edge2")], "radius": q(1)}),
    ("feature_chamfer", {"body": "Body", "base": "Fillet", "name": "Chamfer", "edges": [mn("Fillet", "Edge2")], "size": q(1)}),
    ("feature_pattern", {"body": "Body", "name": "LinearPattern", "kind": "linear", "originals": ["Pad"],
                         "direction": mn("Sketch", "Edge1"), "length": q(50), "occurrences": 2}),
    ("feature_mirror", {"body": "Body", "name": "Mirrored", "mirror_plane": mn("Fillet", "Face1"), "originals": ["Pad"]}),
    ("feature_datum", {"body": "Body", "name": "DatumPlane", "kind": "plane", "attachment": mn("Fillet", "Face6")}),
    ("feature_body_create", {"name": "Body2"}),
    ("feature_set_parameters", {"feature": "Pad", "parameters": {"Length": q(35)}}),
    ("sketch_create", {"name": "Sketch2", "plane": "XZ"}),
    ("sketch_add_geometry", {"sketch": "Sketch", "geometry": [{"kind": "point", "center": [5, 5]}],
                             "constraints": [{"type": "DistanceX", "first": -1, "first_pos": 1, "second": 4, "second_pos": 1, "value": q(5)},
                                             {"type": "DistanceY", "first": -1, "first_pos": 1, "second": 4, "second_pos": 1, "value": q(5)}]}),
    ("sketch_remove_geometry", {"sketch": "Sketch", "geo_ids": [0]}),
    ("sketch_add_constraint", {"sketch": "Sketch", "constraints": [{"type": "Horizontal", "first": 0}]}),
    ("sketch_remove_constraint", {"sketch": "Sketch", "constraints": [5]}),
    ("sketch_set_datum", {"sketch": "Sketch", "constraint": 9, "value": q(25)}),
    ("sketch_toggle_construction", {"sketch": "Sketch", "geo_ids": [0]}),
    ("sketch_add_external_geometry", {"sketch": "Sketch", "edge": mn("Fillet", "Edge1")}),
]


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0817", pad=30)
    _, fl = await apply(m, doc, "feature_fillet", {"body": "Body", "base": "Pad", "name": "Fillet",
                                                   "edges": [mn("Pad", "Edge1")], "radius": q(3)})
    log.check("Given fillet (3 mm on Pad Edge1) committed", fl.get("status") == "OK", short(fl))
    t0 = await m.call("query_tree_summary", {"doc": doc, "depth": 4})
    n0 = await names(m, doc, 4)
    log.check("Given tree depth 4 lists Body, Sketch, Pad, Fillet", all(x in n0 for x in ("Body", "Sketch", "Pad", "Fillet")), n0)
    await frame_shot(m, doc, "tc-08-17-before.png")
    results = {}
    for tool, args in CALLS:
        r = await call_with(m, doc, tool, args, MISSING)
        results[tool] = {"status": r.get("status"), "message": msg(r)[:300]}
    log.write({"no_confirm_results": results})
    for t, r in results.items():
        print(t, r["status"], r["message"][:110])
    log.check("all 19 refused, none OK", len(results) == 19 and all(r["status"] != "OK" for r in results.values()),
              {t: r["status"] for t, r in results.items()})
    odd = {t: r["message"] for t, r in results.items() if r["message"] != WANT}
    log.check("identical message on all 19", not odd, odd or "all identical")
    rn = await call_with(m, doc, "feature_pad", CALLS[0][1], None)
    log.check("confirm:null same as absent (same message)", rn.get("status") != "OK" and msg(rn) == WANT,
              {"status": rn.get("status"), "message": msg(rn)[:300]})
    t1 = await m.call("query_tree_summary", {"doc": doc, "depth": 4})
    log.check("tree after all 19 calls identical to Given", json.dumps(sc(t0).get("tree")) == json.dumps(sc(t1).get("tree")),
              await names(m, doc, 4))
    time.sleep(0.5)
    await frame_shot(m, doc, "tc-08-17-after.png")
    sv = await m.call("document_save", {"doc": doc, "path": EV + "/tc-08-17-save.FCStd"})
    ex = await m.call("export_stl", {"doc": doc, "objects": ["Pad"], "path": EV + "/tc-08-17-export.stl"})
    log.check("document_save and export_stl succeed WITHOUT confirm",
              sv.get("status") == "OK" and ex.get("status") == "OK" and os.path.exists(EV + "/tc-08-17-save.FCStd")
              and os.path.exists(EV + "/tc-08-17-export.stl"),
              {"save": short(sv), "export": short(ex)})
    sch = json.loads((EVIDENCE / "tc-08-tools-schemas.json").read_text(encoding="utf-8"))
    conf = sorted(n for n, s in sch.items() if "confirm" in (s.get("properties") or {}))
    log.check("tools/list: confirm in exactly 19 input schemas, the documented set",
              len(conf) == 19 and set(conf) == {t for t, _ in CALLS}, {"count": len(conf), "tools": conf})
    sample = []
    for tool, args in (("feature_body_create", {"name": "Body2"}), ("sketch_create", {"name": "Sketch2", "plane": "XZ"}),
                       ("feature_set_parameters", {"feature": "Pad", "parameters": {"Length": q(35)}})):
        p, a = await apply(m, doc, tool, args)
        sample.append((tool, p.get("status"), a.get("status"), msg(a)[:150]))
    log.check("3 of the 19 work once previewed (preview + token -> OK)", all(s[2] == "OK" for s in sample), sample)
    print("DOC", doc)


go("tc-08-17", body)
