# ui.py <ws.json> <mode> <arg>: print center of element (screen coords) matching role/label, or dump text
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8")); mode = sys.argv[2]; arg = sys.argv[3] if len(sys.argv) > 3 else ""
def center(e):
    f = e.get("frame") or e.get("bounds") or {}
    return f"{f['x'] + f['w']//2} {f['y'] + f['h']//2}" if f else ""
for e in d["elements"]:
    l = e.get("label") or ""
    if mode == "tree" and e.get("role") == "TreeItem" and l == arg: print(center(e)); break
    if mode == "button" and e.get("role") == "Button" and l == arg and (e.get("frame") or {}).get("y", 0) > 200: print(center(e)); break
    if mode == "text" and (e.get("value") or "").startswith("Checked object"): print(e["value"]); break
if mode == "bodyunder":
    docs = [e for e in d["elements"] if e.get("role") == "TreeItem" and (e.get("label") or "") == arg]
    if docs:
        dy = docs[0]["frame"]["y"]
        bodies = sorted((e for e in d["elements"] if e.get("role") == "TreeItem" and e.get("label") == "Body" and 0 < e["frame"]["y"] - dy < 40), key=lambda e: e["frame"]["y"])
        if bodies: print(center(bodies[0]))
