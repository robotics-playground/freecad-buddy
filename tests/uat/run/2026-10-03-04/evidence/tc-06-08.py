"""TC-06-08: resolution default and cap. Doc TC0607 (L-block)."""
import time
from tc06lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0607"][0]
    log.check("Given: PIL reads PNG sizes", True, "uv run --with pillow")
    r1, a = await render(m, doc, {"camera": "iso"}, "tc-06-08-default.png")
    r2, b = await render(m, doc, {"camera": "iso", "width": 640, "height": 480}, "tc-06-08-640x480.png")
    r3, c = await render(m, doc, {"camera": "iso", "width": 4096, "height": 4096}, "tc-06-08-4096.png")
    r4 = await m.call("query_screenshot", {"doc": doc, "view": {"camera": "iso", "width": 0}})
    r5, e = await render(m, doc, {"width": 1920, "height": 1920}, "tc-06-08-1920.png")
    r6, f = await render(m, doc, {"width": 800}, "tc-06-08-w800.png")
    log.check("default is (1920, 1920)", a and png_size(a) == (1920, 1920), png_size(a) if a else None)
    log.check("640x480 honored", b and png_size(b) == (640, 480), png_size(b) if b else None)
    log.check("4096x4096 refused (schema maximum 1920), not clamped", r3.get("status") != "OK" and ("maximum" in json.dumps(r3) or r3.get("status") == "INVALID_INPUT"), short(r3, 200))
    log.check("width 0 -> INVALID_INPUT", r4.get("status") == "INVALID_INPUT" or "minimum" in json.dumps(r4), short(r4, 200))
    log.check("exactly 1920 accepted, PNG (1920,1920)", r5.get("status") == "OK" and e and png_size(e) == (1920, 1920), png_size(e) if e else short(r5))
    log.check("only width 800 -> OK, PNG (800, 1920)", r6.get("status") == "OK" and f and png_size(f) == (800, 1920), png_size(f) if f else short(r6))
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK", fit.get("status") == "OK", short(fit, 300))
    time.sleep(1.0)
    log.note(f"after shot: {shot('tc-06-08-after.png')}")

go("tc-06-08", body)
