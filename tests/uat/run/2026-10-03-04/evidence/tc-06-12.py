"""TC-06-12: anti-aliasing tracks the user's preference. Doc TC0610 (BoxPad 10x20x30, long straight silhouette edges)."""
import subprocess, time, sys
from tc06lib import *

TAG = sys.argv[1] if len(sys.argv) > 1 else ""


async def body(m, log):
    caps = await m.call("query_capabilities", {})
    log.check("Given: render == gui_constructed", sc(caps).get("render") == "gui_constructed", sc(caps).get("render"))
    aa = subprocess.run(["powershell", "-NoProfile", "-c", "Select-String AntiAliasing \"$env:APPDATA/FreeCAD/v1-1/user.cfg\" | % Line"], capture_output=True, text=True).stdout.strip()
    log.note(f"user.cfg AntiAliasing line (file on disk; FreeCAD writes it on exit): {aa!r}")
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0610"][0]
    pid, win = ids()
    cua("click", {"pid": pid, "window_id": win, "x": 450, "y": 860, "delivery_mode": "foreground"})  # deselect: click empty viewport
    time.sleep(0.8)
    print(click_button("Standard Views"))
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK", fit.get("status") == "OK", short(fit, 300))
    time.sleep(1.0)
    r, p = await render(m, doc, {"camera": "iso"}, f"tc-06-12-mcp{TAG}.png")
    log.check("render OK", r.get("status") == "OK", short(r))
    log.note(f"viewport shot: {shot(f'tc-06-12-viewport{TAG}.png')}")
    log.note(f"after shot: {shot(f'tc-06-12-after{TAG}.png')}")

go(f"tc-06-12{TAG}", body)
