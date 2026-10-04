"""Open a transaction the way a human does: double-click Pad in FreeCAD's tree (Pad task panel). cua-driver only."""
import json, time
from tc03lib import cua, expand, ids, model_items, snapshot, shot

out = {"expand": expand("Body")}
time.sleep(1.0)
items = model_items(snapshot(), "Pad")
pid, win = ids()
if items:
    f = items[0]["frame"]
    scale = 1568 / 1775
    x, y = round((f["x"] + 60) * scale), round((f["y"] + f["h"] / 2) * scale)
    out["pad_frame"] = f
    r = cua("double_click", {"pid": pid, "window_id": win, "x": x, "y": y, "delivery_mode": "foreground"})
    out["double_click"] = {"xy": [x, y], "effect": r.get("effect"), "route": r.get("route")}
    time.sleep(2.5)
else:
    out["error"] = "no Pad tree item"
out["shot"] = shot("tc-08-21-opentx-panel.png")
print(json.dumps(out))
