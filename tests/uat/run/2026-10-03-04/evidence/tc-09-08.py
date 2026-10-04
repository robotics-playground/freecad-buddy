import os

from tc09lib import *  # noqa


async def body(m, log):
    doc, obj = await scene(m, log, "tc-09-08")
    a = await m.call("verify_shape", {"doc": doc, "object": obj})
    b = await m.call("verify_shape", {"doc": doc, "object": obj, "checks": None})
    c = await m.call("verify_shape", {"doc": doc, "object": obj, "checks": []})
    da = await m.call("query_tree_summary", {"doc": doc})
    dn = await m.call("query_tree_summary", {"doc": doc, "depth": None})
    ea = await m.call("export_step", {"doc": doc, "path": f"{EV}/tc-09-08-n.step"})
    en = await m.call("export_step", {"doc": doc, "path": f"{EV}/tc-09-08-n2.step", "ap": None})
    ca = sc(a).get("checks") or []
    ids_a = [x.get("id") for x in ca]
    log.check("checks absent -> OK, five checks, no 'expected' key", a.get("status") == "OK" and len(ca) == 5 and all("expected" not in x for x in ca),
              {"status": a.get("status"), "ids": ids_a, "expected_keys": [("expected" in x) for x in ca]})
    log.check("checks null -> protocol rejection", is_reject(b), raw(b) or short(b))
    cc = sc(c).get("checks") or []
    log.check("checks [] -> OK, same five ids as absent", c.get("status") == "OK" and [x.get("id") for x in cc] == ids_a,
              {"status": c.get("status"), "ids": [x.get("id") for x in cc]})
    s = sc(da)
    log.check("depth absent -> OK, returned_nodes == root count", da.get("status") == "OK" and s.get("returned_nodes") == len(s.get("tree") or []),
              (s.get("returned_nodes"), len(s.get("tree") or [])))
    log.check("depth null -> protocol rejection", is_reject(dn), raw(dn) or short(dn))
    path = f"{EV}/tc-09-08-n.step"
    n242 = open(path, encoding="latin-1").read().count("AP242") if os.path.exists(path) else None
    head = ""
    if os.path.exists(path):
        head = [ln for ln in open(path, encoding="latin-1").read().splitlines() if "FILE_SCHEMA" in ln or "AP2" in ln][:3]
    log.check("ap absent -> default AP242: grep -c AP242 non-zero", ea.get("status") == "OK" and bool(n242),
              {"status": ea.get("status"), "count_AP242": n242, "schema_lines": head})
    log.check("ap null -> protocol rejection", is_reject(en), raw(en) or short(en))
    log.check("ap null wrote no n2 file", not os.path.exists(f"{EV}/tc-09-08-n2.step"), "")
    log.check("consistency: absent=default, null=reject in all 3 pairs",
              a.get("status") == "OK" and da.get("status") == "OK" and ea.get("status") == "OK" and is_reject(b) and is_reject(dn) and is_reject(en), "")
    await frame_shot(m, doc, "tc-09-08-after.png")


go("tc-09-08", body)
