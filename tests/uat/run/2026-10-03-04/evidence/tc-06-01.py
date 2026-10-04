"""TC-06-01: MCP render matches the live viewport (60x40x5 PartDesign plate)."""
import time, subprocess
from tc06lib import *


async def body(m, log):
    await close_all(m, log)
    doc = sc(await m.call("document_create", {"label": "TC0601"})).get("doc")
    await apply(m, doc, "feature_body_create", {"name": "PlateBody"})
    await apply(m, doc, "sketch_create", {"name": "PlateProfile", "body": "PlateBody", "plane": "XY"})
    g, c = rect_profile(0, 0, 60, 40)
    await apply(m, doc, "sketch_add_geometry", {"sketch": "PlateProfile", "geometry": g, "constraints": c})
    _, pad = await apply(m, doc, "feature_pad", {"body": "PlateBody", "profile": "PlateProfile", "name": "PlatePad", "length": q(5)})
    log.check("fixture: PlatePad committed", pad.get("status") == "OK", short(pad))
    dl = await m.call("document_list", {})
    log.check("Given: document_list returns a handle", any(d["doc"] == doc for d in sc(dl).get("documents", [])), doc)
    ts = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.check("Given: query_tree_summary names PlatePad", "PlatePad" in json.dumps(sc(ts)), "")
    mp0 = await m.call("query_mass_properties", {"doc": doc})
    log.check("Given (literal): query_mass_properties {doc} returns volume+bbox", mp0.get("status") == "OK", short(mp0))
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "PlatePad"})
    s = sc(mp)
    log.check("Given: mass properties volume + bbox", s.get("volume") is not None and s.get("bbox") is not None,
              {"volume": s.get("volume"), "bbox": s.get("bbox")})
    # When: GUI camera through toolbar buttons
    pid, win = ids()
    pre = cua("get_window_state", {"pid": pid, "window_id": win, "screenshot_out_file": f"{EVIDENCE.as_posix()}/tc-06-01-pre.png"})
    labels = sorted({e.get("label") for e in pre.get("elements", []) if e.get("role") == "Button" and e.get("label")})
    log.note("toolbar Button labels: " + json.dumps(labels))
    for label in ("Standard Views", "Isometric"):
        hits = [e for e in pre.get("elements", []) if e.get("role") == "Button" and e.get("label") == label]
        log.note(f"button {label!r}: {len(hits)} hit(s)")
    iso = click_button("Standard Views")
    log.note(f"Standard Views toolbar click (default action = viewIsometric per Python console): {iso}")
    fa = gui_fit()
    log.note(f"Fit All toolbar click: {fa}")
    # visual Then: fit first (MCP fit, the TC default), then both captures
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK", fit.get("status") == "OK", short(fit, 500))
    time.sleep(1.0)
    r, out = await render(m, doc, {"camera": "iso", "include": ["PlatePad"]}, "tc-06-01-mcp.png")
    log.check("render status OK", r.get("status") == "OK", short(r))
    log.check("scene.rendered_objects contains PlatePad", "PlatePad" in (objs(r) or []), objs(r))
    log.note(f"render block: {sc(r).get('render')}")
    shot("tc-06-01-viewport.png")
    shot("tc-06-01-after.png")
    # default render too (no include) for leak check
    r2, _ = await render(m, doc, {"camera": "iso"}, "tc-06-01-mcp-default.png")
    log.check("default render: no Body/Sketch/Origin leaked into rendered_objects",
              not any(n in (objs(r2) or []) for n in ("PlateBody", "PlateProfile", "Origin")) and not any(
                  str(n).startswith(("Origin", "X_Axis", "Y_Axis", "Z_Axis", "XY_Plane", "XZ_Plane", "YZ_Plane")) for n in (objs(r2) or [])),
              objs(r2))
    if out:
        log.note(f"mcp png stats: {png_stats(out)}")
    aa = subprocess.run(["powershell", "-NoProfile", "-c", "Select-String AntiAliasing \"$env:APPDATA/FreeCAD/v1-1/user.cfg\" | % Line"], capture_output=True, text=True).stdout.strip()
    log.note(f"AntiAliasing in user.cfg: {aa!r}")
    log.note(f"doc handle {doc} left open for visual review")

go("tc-06-01", body)
