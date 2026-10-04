"""TC-06-09: query_screenshot is read-only on a clean golden document (box-10-20-30)."""
import glob, os, time
from tc06lib import *

WD = "C:/Users/thuan/freecad-buddy-workdir/tmp"
GOLD = "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"


def shots():
    return set(glob.glob(WD + "/FCB_TMP_shot_*.png")) | set(glob.glob(os.environ.get("TEMP", "") + "/FCB_TMP_shot_*.png"))


async def body(m, log):
    await close_all(m, log)
    op = await m.call("document_open", {"path": GOLD})
    doc = sc(op).get("doc")
    log.check("Given: document_open returns a handle", op.get("status") == "OK" and bool(doc), short(op))
    pid, win = ids()
    time.sleep(1.0)
    sa = cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["View", "Visibility", "Show All Objects"]})
    time.sleep(1.0)
    log.note(f"golden Box opens hidden (known fixture defect): View>Visibility>Show All Objects -> {sa.get('route') or sa}")
    vr0 = await m.call("verify_recompute", {"doc": doc})
    log.note("verify_recompute before: " + json.dumps(sc(vr0))[:500])
    tree0 = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.note("tree before: " + json.dumps(sc(tree0).get("tree")))
    mp0 = await m.call("query_mass_properties", {"doc": doc, "object": "Box"})
    before_shots = shots()
    rs = []
    for view, png in (({"camera": "iso"}, "tc-06-09-iso.png"),
                      ({"camera": "top", "styles": [{"object": "Box", "color": [0, 1, 0], "transparency": 50}]}, "tc-06-09-top-green.png"),
                      ({"camera": "front", "focus": {"object": "Box", "element_type": "face", "index": 2}}, "tc-06-09-front-focus.png")):
        r, _ = await render(m, doc, view, png)
        rs.append(r)
        log.check(f"render {png}: OK, dirty_document false", r.get("status") == "OK" and (sc(r).get("render") or {}).get("dirty_document") is False, {"status": r.get("status"), "render": sc(r).get("render")})
    r4, _ = await render(m, doc, {"camera": "top"}, "tc-06-09-top-unstyled.png")
    mp1 = await m.call("query_mass_properties", {"doc": doc, "object": "Box"})
    tree1 = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    v0, v1 = sc(mp0).get("volume"), sc(mp1).get("volume")
    log.check("volume unchanged and == 6000", v0 == v1 and (v1 or {}).get("value") == 6000.0, {"before": v0, "after": v1})
    c0 = sc(mp0).get("com") or sc(mp0).get("center_of_mass")
    c1 = sc(mp1).get("com") or sc(mp1).get("center_of_mass")
    log.check("centre of mass unchanged", c0 == c1 and c0 is not None, {"before": c0, "after": c1, "keys": sorted(sc(mp1).keys())})
    log.check("tree unchanged incl. visibility", sc(tree0).get("tree") == sc(tree1).get("tree"), "")
    vr1 = await m.call("verify_recompute", {"doc": doc})
    log.note("verify_recompute after: " + json.dumps(sc(vr1))[:500])
    log.check("verify_recompute after: no touched/error object (same as before)", sc(vr1) == sc(vr0) or "touched" not in json.dumps(sc(vr1)).lower(), json.dumps(sc(vr1))[:200])
    new = shots() - before_shots
    links = {os.path.normpath(link(r)) for r in rs + [r4] if link(r)}
    log.check("no orphan temp PNG beyond the returned links", {os.path.normpath(p) for p in new} <= links, {"new": sorted(new), "links": sorted(links)})
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK", fit.get("status") == "OK", short(fit, 300))
    time.sleep(1.0)
    log.note(f"after shot: {shot('tc-06-09-after.png')}")

go("tc-06-09", body)
