from tc08lib import *  # noqa
from tc08h1 import h1

SETLEN40 = {"feature": "Pad", "parameters": {"Length": {"value": 40, "unit": "mm"}}}


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0805", pad=30)
    qs = await m.call("query_screenshot", {"doc": doc, "view": {"camera": "iso"}})
    has_link = "resource_link" in json.dumps(qs) or "resource" in json.dumps(sc(qs))
    log.check("Given GUI host query_screenshot iso OK with resource_link", qs.get("status") == "OK" and has_link,
              {"status": qs.get("status"), "sc_keys": sorted(sc(qs))})
    await frame_shot(m, doc, "tc-08-05-before.png")

    off = await preview(m, doc, "feature_set_parameters", SETLEN40, render="off")
    auto = await preview(m, doc, "feature_set_parameters", SETLEN40, render="auto")
    log.write({"off_render": diff(off).get("render"), "auto_render": diff(auto).get("render")})
    async with h1(log, "tc-08-05-h1", str(EVIDENCE / "tc-08-05-h1.stderr.log")) as hm:
        hdoc = await body_sketch(hm, "TC0805H1", pad=30)
        hmp = await hm.call("query_mass_properties", {"doc": hdoc, "object": "Pad"})
        log.note(f"H1 Given: Pad volume {vol(hmp)}")
        head = await preview(hm, hdoc, "feature_set_parameters", SETLEN40)
        log.write({"headless_render": diff(head).get("render"), "headless_status": head.get("status")})
    rs = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_set_parameters", "args": SETLEN40},
                                           "render": "sometimes"})

    log.check("render:off -> diff.render == {available:false, reason:'off'}",
              diff(off).get("render") == {"available": False, "reason": "off"}, diff(off).get("render"))
    log.check("headless default render -> reason 'no render port'",
              (diff(head).get("render") or {}).get("reason") == "no render port", diff(head).get("render"))
    log.check("'off' never on a call without render:off",
              (diff(auto).get("render") or {}).get("reason") != "off" and (diff(head).get("render") or {}).get("reason") != "off",
              {"auto": diff(auto).get("render"), "headless": diff(head).get("render")})
    log.check("render:off call and headless call both envelope OK", off.get("status") == "OK" and head.get("status") == "OK",
              {"off": off.get("status"), "headless": head.get("status")})
    log.check("render:auto on GUI host -> diff.render.available true", (diff(auto).get("render") or {}).get("available") is True,
              diff(auto).get("render"))
    log.check("render:'sometimes' rejected by schema (enum auto/off)",
              rs.get("status") != "OK" and ("enum" in json.dumps(rs).lower() or "validation" in json.dumps(rs).lower()
                                            or "not one of" in json.dumps(rs)), short(rs, 400))
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("live GUI Pad still 12000.0 after three previews (corroborating)", near(vol(mp), 12000.0), vol(mp))
    await frame_shot(m, doc, "tc-08-05-after.png")
    print("DOC", doc)


go("tc-08-05", body)
