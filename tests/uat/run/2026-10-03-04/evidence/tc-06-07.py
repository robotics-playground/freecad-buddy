"""TC-06-07: camera custom requires exactly four numbers. Fixture: L-block (as TC-06-02)."""
import time
from tc06lib import *
from PIL import Image, ImageChops


async def lblock(m, label):
    doc = sc(await m.call("document_create", {"label": label})).get("doc")
    await apply(m, doc, "feature_body_create", {"name": "Body"})
    await apply(m, doc, "sketch_create", {"name": "BaseProfile", "body": "Body", "plane": "XY"})
    g, c = rect_profile(0, 0, 30, 20)
    await apply(m, doc, "sketch_add_geometry", {"sketch": "BaseProfile", "geometry": g, "constraints": c})
    await apply(m, doc, "feature_pad", {"body": "Body", "profile": "BaseProfile", "name": "Base", "length": q(10)})
    await apply(m, doc, "sketch_create", {"name": "TowerProfile", "body": "Body", "plane": "XY"})
    g, c = rect_profile(0, 0, 10, 10)
    await apply(m, doc, "sketch_add_geometry", {"sketch": "TowerProfile", "geometry": g, "constraints": c})
    _, p = await apply(m, doc, "feature_pad", {"body": "Body", "profile": "TowerProfile", "name": "Tower", "length": q(25)})
    return doc, p


async def body(m, log):
    await close_all(m, log)
    doc, p = await lblock(m, "TC0607")
    log.check("Given: document_list returns a handle (L-block built)", p.get("status") == "OK" and bool(doc), doc)
    q4 = [0.424708, 0.17592, 0.339851, 0.820473]
    r1, c = await render(m, doc, {"camera": "custom", "custom_orientation": q4}, "tc-06-07-custom.png")
    ri, i = await render(m, doc, {"camera": "iso"}, "tc-06-07-iso.png")
    log.check("valid quaternion -> OK + link", r1.get("status") == "OK" and bool(link(r1)), short(r1))
    if c and i:
        d = ImageChops.difference(Image.open(c).convert("RGB"), Image.open(i).convert("RGB")).getbbox()
        log.check("custom quaternion render == iso render (pixel diff bbox None)", d is None, d)
    r2 = await m.call("query_screenshot", {"doc": doc, "view": {"camera": "custom"}})
    log.check("missing orientation -> INVALID_INPUT exact detail", r2.get("status") == "INVALID_INPUT" and "camera 'custom' requires custom_orientation (a 4-float quaternion)" in detail_text(r2), short(r2, 220))
    r3 = await m.call("query_screenshot", {"doc": doc, "view": {"camera": "custom", "custom_orientation": [0.0, 0.0, 1.0]}})
    log.check("3 numbers rejected (schema minItems 4)", "too short" in json.dumps(r3) or r3.get("status") == "INVALID_INPUT", short(r3, 220))
    r4 = await m.call("query_screenshot", {"doc": doc, "view": {"camera": "custom", "custom_orientation": [0, 0, 0, 1, 0]}})
    log.check("5 numbers rejected (schema maxItems 4)", "too long" in json.dumps(r4) or r4.get("status") == "INVALID_INPUT", short(r4, 220))
    r5 = await m.call("query_screenshot", {"doc": doc, "view": {"camera": "custom", "custom_orientation": [0, 0, 0, 0]}})
    log.check("zero quaternion -> INVALID_INPUT 'custom_orientation is degenerate (zero norm)'", r5.get("status") == "INVALID_INPUT" and "custom_orientation is degenerate (zero norm)" in detail_text(r5), short(r5, 220))
    log.note(f"Standard Views (isometric): {click_button('Standard Views')}")
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK (Isometric)", fit.get("status") == "OK", short(fit, 300))
    time.sleep(1.0)
    log.note(f"after shot: {shot('tc-06-07-after.png')}")

go("tc-06-07", body)
