from tc14lib import *


def title():
    pid, win = ids()
    for w in cua("list_windows", {"pid": pid}).get("windows", []):
        if w["window_id"] == win:
            return w["title"]


def digest(env):
    s = sc(env)
    for k in ("fingerprint", "digest", "brep_sha256", "shape_digest"):
        if k in s:
            return s[k]
    return json.dumps(s, sort_keys=True)


async def body(m, log):
    o = await m.call("document_open", {"path": BOX})
    h = sc(o).get("doc")
    log.check("Given document_open OK", o.get("status") == "OK", h)
    log.note(f"show all {menu(['View', 'Visibility', 'Show All Objects'])}")
    v0 = await m.call("verify_shape", {"doc": h})
    log.note(f"verify_shape before: {v0.get('status')} keys={sorted(sc(v0))} {json.dumps(sc(v0))[:600]}")
    fp_before = digest(v0)
    mp0 = await m.call("query_mass_properties", {"doc": h, "object": "Box"})
    log.check("Given volume 6000 within 0.1%", abs(float(vol(mp0) or 0) - 6000.0) <= 6.0, vol(mp0))
    dl0 = await m.call("document_list", {})
    t0 = title()
    log.note(f"modified state before: title={t0!r} document_list={json.dumps(sc(dl0))[:400]}")
    f = await m.call("view_fit_viewport", {"doc": h})
    log.note(f"fit {f.get('status')}")
    v1 = await m.call("verify_shape", {"doc": h})
    log.check("Then fingerprint unchanged", digest(v1) == fp_before, f"{str(digest(v1))[:120]} vs {str(fp_before)[:120]}")
    mp1 = await m.call("query_mass_properties", {"doc": h, "object": "Box"})
    log.check("Then volume unchanged 6000 within 0.1%", abs(float(vol(mp1) or 0) - 6000.0) <= 6.0, vol(mp1))
    dl1 = await m.call("document_list", {})
    t1 = title()
    log.check("Then modified state unchanged by the fit", t1 == t0 and sc(dl1) == sc(dl0), f"title {t0!r}->{t1!r}")
    vr = await m.call("verify_recompute", {"doc": h})
    log.note(f"verify_recompute {vr.get('status')} {json.dumps(sc(vr))[:400]}")
    log.check("Then verify_recompute reports no pending recompute/error", vr.get("status") == "OK", vr.get("status"))
    shot("tc-14-16-after.png")
    print("HANDLE", h)


go("tc-14-16", body)
