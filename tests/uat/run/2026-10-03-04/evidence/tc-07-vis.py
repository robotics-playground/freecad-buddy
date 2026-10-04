"""TC-07 visual step: [Show All Objects] -> view_fit_viewport (MCP) -> FreeCAD Fit All fallback -> window capture.
usage: uv run python tc-07-vis.py <tag> <doc-handle> <png-name> [showall] [guifit]"""
import asyncio, json, sys, time, subprocess, importlib.util
spec = importlib.util.spec_from_file_location("lib", "tc-07-lib.py"); lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)
tag, doc, png = sys.argv[1:4]; flags = sys.argv[4:]
fc = json.load(open("fc.json")); pid, win = fc["pid"], fc["window_id"]
def cua(tool, payload):
    out = subprocess.run(["cua-driver", tool], input=json.dumps(payload), capture_output=True, text=True, timeout=60)
    try: return json.loads(out.stdout)
    except Exception: return {"_raw": out.stdout, "_err": out.stderr}
async def main():
    async with lib.Session(tag) as s:
        if "showall" in flags:
            r = cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["View", "Visibility", "Show All Objects"]})
            time.sleep(0.8)
            for _ in range(3):
                cua("press_key", {"pid": pid, "window_id": win, "key": "escape"}); time.sleep(0.2)
            s.results.append(("NOTE showall", True, f"View>Visibility>Show All Objects -> {r.get('effect')} {r.get('route')} {r.get('error') or ''}"))
            print("showall:", json.dumps(r)[:300])
        f = await s.call("view_fit_viewport", {"doc": doc})
        ok = f.get("status") == "OK"
        s.check(f"visual: view_fit_viewport {{doc}} OK [{png}]", ok, [f.get("status"), lib.sc(f) or f.get("detail")])
        if not ok or "guifit" in flags:
            out = subprocess.run(["uv", "run", "python", "gui.py", "fitall"], capture_output=True, text=True)
            s.results.append(("NOTE guifit", True, "FreeCAD Fit All toolbar: " + out.stdout.strip()[:300]))
            print("gui fitall:", out.stdout.strip()[:300])
        time.sleep(1.0)
        r = cua("get_window_state", {"pid": pid, "window_id": win, "screenshot_out_file": lib.EV + "/" + png, "include_screenshot": True})
        print("shot:", png, r.get("window_title"), r.get("_err", "")[:200])
        wins = cua("list_windows", {"pid": pid}).get("windows", [])
        s.results.append(("NOTE windows", True, json.dumps([(w["window_id"], w["title"]) for w in wins])))
        print("windows:", [(w["window_id"], w["title"]) for w in wins])
asyncio.run(main())
