import re
from tc08lib import *  # noqa


async def body(m, log):
    doc = await body_sketch(m, "TC0801")
    si = await m.call("query_sketch_info", {"doc": doc, "sketch": "Sketch"})
    log.check("Given query_sketch_info fully_constrained true", sc(si).get("fully_constrained") is True, short(si))
    pid, win = ids()
    st = cua("get_window_state", {"pid": pid, "window_id": win, "include_screenshot": False})
    fa = [e for e in st.get("elements", []) if e.get("role") == "Button" and e.get("label") == "Fit All"]
    log.check("Precondition P6 (with a 3D view open): Fit All toolbar button has element_token", bool(fa and fa[0].get("element_token")), fa[:1])
    await frame_shot(m, doc, "tc-08-01-before.png")

    pr = await preview(m, doc, "feature_pad", PAD30)
    d = diff(pr)
    log.write({"preview_sc": sc(pr)})
    log.check("status OK, detail null, diff.schema fcb.geometry-diff/1",
              pr.get("status") == "OK" and pr.get("detail") is None and d.get("schema") == "fcb.geometry-diff/1",
              f"{pr.get('status')} {pr.get('detail')} {d.get('schema')}")
    dv = (d.get("deltas") or {}).get("volume") or {}
    log.check("deltas.volume before 0.0 after 12000.0 delta 12000.0 units mm^3",
              near(dv.get("after"), 12000.0) and abs(float(dv.get("before") or 0)) < 1e-9 and near(dv.get("delta"), 12000.0)
              and dv.get("units") == "mm^3", dv)
    de = d.get("deltas") or {}
    log.check("area mm^2, bbox mm, com mm",
              (de.get("area") or {}).get("units") == "mm^2" and (de.get("bbox") or {}).get("units") == "mm"
              and (de.get("com") or {}).get("units") == "mm",
              {k: (de.get(k) or {}).get("units") for k in ("area", "bbox", "com")})
    c = d.get("counts") or {}
    log.check("counts.solids 0->1 delta 1; faces.delta 6",
              (c.get("solids") or {}).get("before") == 0 and (c.get("solids") or {}).get("after") == 1
              and (c.get("solids") or {}).get("delta") == 1 and (c.get("faces") or {}).get("delta") == 6,
              {"solids": c.get("solids"), "faces": c.get("faces")})
    log.check("touched contains Pad, new contains Pad, deleted []",
              "Pad" in (d.get("touched") or []) and "Pad" in (d.get("new") or []) and d.get("deleted") == [],
              {"touched": d.get("touched"), "new": d.get("new"), "deleted": d.get("deleted")})
    v = d.get("validity") or {}
    log.check("validity is_valid true, recompute_clean true, status OK, explanation null",
              v.get("is_valid") is True and v.get("recompute_clean") is True and v.get("status") == "OK"
              and v.get("explanation") is None, v)
    t = d.get("tnp_precheck") or {}
    log.check("tnp_precheck.status in CLEAN/FLAGGED/UNSUPPORTED and element_map_version present",
              t.get("status") in ("CLEAN", "FLAGGED", "UNSUPPORTED") and "element_map_version" in t, t)
    pid_ = token(pr) or ""
    exp = sc(pr).get("expires_at") or ""
    log.check("preview_id starts fcb-preview: ; expires_at ISO-8601 UTC",
              pid_.startswith("fcb-preview:") and bool(re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|\+00:00)$", exp)),
              {"preview_id": pid_[:40], "expires_at": exp})
    tr = await names(m, doc)
    log.check("live tree has no Pad after preview (corroborating)", "Pad" not in tr, tr)
    await frame_shot(m, doc, "tc-08-01-after.png")
    log.write({"doc": doc})
    print("DOC", doc)


go("tc-08-01", body)
