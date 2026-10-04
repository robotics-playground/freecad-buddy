"""Open an exported file in the FreeCAD GUI exactly as a user would: File > Open..., type the path,
accept the importer's settings dialog, then set the isometric view. Touches no bridge code.
usage: uv run python tc-07-guiopen.py <absolute path>   -> prints JSON {windows_before, steps, windows_after}"""
import json, subprocess, sys, time
fc = json.load(open("fc.json")); PID, WIN = fc["pid"], fc["window_id"]
def cua(tool, payload, timeout=60):
    try:
        out = subprocess.run(["cua-driver", tool], input=json.dumps(payload), capture_output=True, text=True, timeout=timeout)
        return json.loads(out.stdout) if out.stdout.strip().startswith("{") else {"_raw": out.stdout[:300], "_err": out.stderr[:300]}
    except subprocess.TimeoutExpired:
        return {"_timeout": True}
def windows():
    return [(w["window_id"], w["title"]) for w in cua("list_windows", {"pid": PID}).get("windows", [])]
steps = []
path = sys.argv[1].replace("/", "\\")
before = windows()
menu = subprocess.Popen(["cua-driver", "invoke_menu"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
menu.stdin.write(json.dumps({"pid": PID, "window_id": WIN, "path": ["File", "Open…"]})); menu.stdin.close()
dlg = None
for _ in range(30):
    time.sleep(0.5)
    for wid, title in windows():
        if title == "Open document": dlg = wid
    if dlg: break
steps.append(("open dialog", dlg))
if dlg:
    steps.append(("type", cua("type_text", {"pid": PID, "window_id": dlg, "text": path, "delivery_mode": "foreground"}).get("effect")))
    time.sleep(0.5)
    steps.append(("enter", cua("press_key", {"pid": PID, "window_id": dlg, "key": "return", "delivery_mode": "foreground"}).get("effect")))
    for _ in range(40):
        time.sleep(0.5)
        ws = windows()
        extra = [(w, t) for w, t in ws if w != WIN]
        if not extra: break
        for wid, title in extra:
            if title != "Open document":
                steps.append(("accept dialog", title, cua("press_key", {"pid": PID, "window_id": wid, "key": "return", "delivery_mode": "foreground"}).get("effect")))
                time.sleep(1.5)
try:
    menu.wait(timeout=10)
except subprocess.TimeoutExpired:
    menu.kill()
steps.append(("menu result", (menu.stdout.read() or "")[:200]))
time.sleep(1)
steps.append(("iso", cua("invoke_menu", {"pid": PID, "window_id": WIN, "path": ["View", "Standard Views", "Axonometric", "Isometric"]}).get("effect")))
time.sleep(0.5)
for _ in range(4):
    cua("press_key", {"pid": PID, "window_id": WIN, "key": "escape"}); time.sleep(0.3)
print(json.dumps({"file": path, "windows_before": before, "steps": steps, "windows_after": windows()}, ensure_ascii=False))
