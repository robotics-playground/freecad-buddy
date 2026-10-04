"""TC-99 baseline: open the golden box, make it visible, fit, capture tc-99-<MM>-before.png.

usage: tc-99-baseline.py <MM> [--fit gui]
Prints the doc handle and every step result as JSON. Only cua-driver touches the window.
"""
import json, subprocess, sys, time
from pathlib import Path

E = Path(__file__).resolve().parent
ROOT = E.parents[4]
GOLDEN = str(ROOT / "benchmarks/g0/golden-models/box-10-20-30.FCStd").replace("\\", "/")
MM = sys.argv[1]
GUI_FIT = "--fit" in sys.argv and sys.argv[sys.argv.index("--fit") + 1] == "gui"
fc = json.loads((E / "fc.json").read_text())
PID, WIN = fc["pid"], fc["window_id"]
log = {}


def fcb(tool, args):
    r = subprocess.run(["uv", "run", "python", str(ROOT / "_automation/uat/fcb.py"), tool, json.dumps(args)],
                       capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    return json.loads(r.stdout)


def cua(tool, payload):
    r = subprocess.run(["cua-driver", tool], input=json.dumps(payload), capture_output=True, text=True, timeout=60)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"_raw": r.stdout[:300]}


def snap():
    return cua("get_window_state", {"pid": PID, "window_id": WIN, "include_screenshot": False})


def find(state, role, label, ymin=None):
    for e in state.get("elements", []):
        f = e.get("frame") or {}
        if e.get("role") == role and e.get("label") == label and (ymin is None or f.get("y", 0) >= ymin):
            return e
    return None


def value_cell(state, name):
    rows = [e for e in state.get("elements", []) if e.get("role") == "TreeItem"]
    for i, e in enumerate(rows):
        if e.get("label") == name and i + 1 < len(rows) and abs(rows[i + 1]["frame"]["y"] - e["frame"]["y"]) < 3:
            return rows[i + 1]
    return None


opened = fcb("document_open", {"path": GOLDEN})
H = opened["structured_content"]["doc"]
log["open"] = opened["status"]
time.sleep(1)
r = cua("invoke_menu", {"pid": PID, "window_id": WIN, "path": ["View", "Visibility", "Show All Objects"]})
log["show_all"] = {k: r.get(k) for k in ("effect", "route", "delivery", "refusal")}
time.sleep(1)
tree = fcb("query_tree_summary", {"doc": H})["structured_content"]["tree"]
log["box_visible"] = [n.get("visibility") for n in tree if n["name"] == "Box"]
if GUI_FIT:
    s = snap()
    btn = find(s, "Button", "Fit All")
    log["fit"] = {"gui_fitall": cua("click", {"pid": PID, "element_token": btn["element_token"]}).get("route")}
else:
    f = fcb("view_fit_viewport", {"doc": H})
    log["fit"] = {"status": f["status"], "framing": f.get("framing")}
    if f["status"] != "OK":
        btn = find(snap(), "Button", "Fit All")
        log["fit"]["gui_fitall"] = cua("click", {"pid": PID, "element_token": btn["element_token"]}).get("route")
time.sleep(1)
out = str(E / f"tc-99-{MM}-before.png").replace("\\", "/")
cua("get_window_state", {"pid": PID, "window_id": WIN, "screenshot_out_file": out})
log["before_png"] = out
log["doc"] = H
print(json.dumps(log, default=str))
