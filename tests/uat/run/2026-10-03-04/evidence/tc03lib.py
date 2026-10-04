"""TC-03 executor helpers: one MCP session per scenario, every call logged to JSONL.

Host runs FREECAD_BUDDY_AUTO_APPROVE=1 (TC-03 precondition), so mutations are sent without confirm.
Only cua-driver touches the window; MCP goes over http://127.0.0.1:8765/mcp.
"""

from __future__ import annotations

import asyncio
import glob
import json
import os
import subprocess
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EVIDENCE = Path(__file__).resolve().parent
EV = EVIDENCE.as_posix()
ENDPOINT = "http://127.0.0.1:8765/mcp"


def ids() -> tuple[int, int]:
    data = json.loads((EVIDENCE / "fc.json").read_text())
    return int(data["pid"]), int(data["window_id"])


def cua(tool: str, payload: dict, timeout: int = 60) -> dict:
    out = subprocess.run(
        ["cua-driver", tool], input=json.dumps(payload), capture_output=True, text=True,
        timeout=timeout, encoding="utf-8",
    )
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return {"_raw": out.stdout[-2000:], "_err": out.stderr[-2000:]}


def snapshot(screenshot: bool = False) -> dict:
    pid, win = ids()
    return cua("get_window_state", {"pid": pid, "window_id": win, "include_screenshot": screenshot})


def find(state: dict, role: str | None = None, label: str | None = None, contains: str | None = None):
    hits = []
    for element in state.get("elements", []):
        if role and element.get("role") != role:
            continue
        lab = element.get("label") or ""
        if label is not None and lab != label:
            continue
        if contains is not None and contains not in lab:
            continue
        hits.append(element)
    return hits


def click_button(label: str) -> dict:
    state = snapshot()
    pid, _ = ids()
    for element in find(state, role="Button", label=label):
        result = cua("click", {"pid": pid, "element_token": element["element_token"]})
        time.sleep(1.0)
        return {"clicked": label, "effect": result.get("effect"), "route": result.get("route")}
    return {"error": f"no Button {label!r}", "count": state.get("element_count")}


def fitall() -> dict:
    return click_button("Fit All")


def tree_items(state: dict, label: str) -> list[dict]:
    return [e for e in state.get("elements", [])
            if (e.get("label") or "") == label and "Item" in (e.get("role") or "") and e.get("role") != "MenuItem"]


def snap_temp() -> list[str]:
    temp = os.environ.get("TEMP") or os.environ.get("TMP") or ""
    return sorted(glob.glob(os.path.join(temp, "FCB_TMP_snap_*")))


def shot(name: str) -> dict:
    pid, win = ids()
    path = f"{EV}/{name}"
    result = cua("get_window_state", {"pid": pid, "window_id": win, "screenshot_out_file": path})
    tree = result.get("tree_markdown") or ""
    return {"file": path, "exists": Path(path).exists(), "title": tree.splitlines()[0][:120] if tree else None}


class Log:
    def __init__(self, name: str):
        self.name = name
        self.path = EVIDENCE / f"{name}-mcp.jsonl"
        self.path.write_text("", encoding="utf-8")
        self.checks: list[str] = []

    def write(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def check(self, name: str, ok: bool | None, detail: object = "") -> bool | None:
        verdict = "NOT RUN" if ok is None else ("PASS" if ok else "FAIL")
        line = f"{verdict} | {name} | {detail}"
        self.checks.append(line)
        self.write({"check": name, "verdict": verdict, "detail": detail})
        print(line)
        return ok

    def note(self, text: str) -> None:
        self.write({"note": text})
        self.checks.append(f"NOTE | {text}")
        print("NOTE", text)

    def save(self) -> None:
        (EVIDENCE / f"{self.name}-checks.txt").write_text("\n".join(self.checks) + "\n", encoding="utf-8")


class Mcp:
    def __init__(self, session: ClientSession, log: Log):
        self.session = session
        self.log = log

    async def call(self, tool: str, args: dict) -> dict:
        started = time.time()
        result = await self.session.call_tool(tool, args)
        text = "".join(block.text for block in result.content if hasattr(block, "text"))
        try:
            envelope = json.loads(text)
        except json.JSONDecodeError:
            envelope = {"_raw": text}
        if not isinstance(envelope, dict):
            envelope = {"_value": envelope}
        is_error = bool(getattr(result, "isError", False))
        self.log.write({"tool": tool, "args": args, "isError": is_error,
                        "seconds": round(time.time() - started, 3), "envelope": envelope})
        envelope["_isError"] = is_error
        return envelope

    async def fit(self, doc: str) -> dict:
        envelope = await self.call("view_fit_viewport", {"doc": doc})
        record = {"view_fit_viewport": envelope.get("status"), "detail": envelope.get("detail")}
        if envelope.get("status") != "OK":
            record["gui_fitall"] = fitall()
        self.log.write({"fit": record})
        return record


def sc(envelope: dict) -> dict:
    return envelope.get("structured_content") or {}


def mut(envelope: dict) -> dict:
    return sc(envelope).get("mutation") or {}


def pv(envelope: dict) -> dict:
    return mut(envelope).get("post_verify") or {}


def schema_reject(envelope: dict) -> bool:
    raw = envelope.get("_raw") or ""
    return envelope.get("_isError") is True and "status" not in envelope and "validation" in raw.lower()


def short(envelope: dict, n: int = 300) -> str:
    keep = {k: envelope.get(k) for k in ("status", "detail", "_raw") if envelope.get(k) is not None}
    return json.dumps(keep, ensure_ascii=False)[:n]


async def run(name: str, body) -> None:
    log = Log(name)
    async with streamablehttp_client(ENDPOINT) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await body(Mcp(session, log), log)
    log.save()


RECT_GEOMETRY = [
    {"kind": "line_segment", "start": [0, 0], "end": [60, 0]},
    {"kind": "line_segment", "start": [60, 0], "end": [60, 40]},
    {"kind": "line_segment", "start": [60, 40], "end": [0, 40]},
    {"kind": "line_segment", "start": [0, 40], "end": [0, 0]},
]


def rect_constraints(width: float = 60, depth: float = 40, names: bool = True) -> list[dict]:
    width_c = {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2,
               "value": {"value": width, "unit": "mm"}}
    depth_c = {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2,
               "value": {"value": depth, "unit": "mm"}}
    if names:
        width_c["name"] = "PlateWidth"
        depth_c["name"] = "PlateDepth"
    return [
        {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1},
        {"type": "Coincident", "first": 1, "first_pos": 2, "second": 2, "second_pos": 1},
        {"type": "Coincident", "first": 2, "first_pos": 2, "second": 3, "second_pos": 1},
        {"type": "Coincident", "first": 3, "first_pos": 2, "second": 0, "second_pos": 1},
        {"type": "Horizontal", "first": 0},
        {"type": "Horizontal", "first": 2},
        {"type": "Vertical", "first": 1},
        {"type": "Vertical", "first": 3},
        {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
        width_c,
        depth_c,
    ]


def rect_geometry(width: float = 60, depth: float = 40) -> list[dict]:
    return [
        {"kind": "line_segment", "start": [0, 0], "end": [width, 0]},
        {"kind": "line_segment", "start": [width, 0], "end": [width, depth]},
        {"kind": "line_segment", "start": [width, depth], "end": [0, depth]},
        {"kind": "line_segment", "start": [0, depth], "end": [0, 0]},
    ]


async def new_doc(m: Mcp, label: str) -> str:
    envelope = await m.call("document_create", {"label": label})
    return sc(envelope)["doc"]


async def rect_sketch(m: Mcp, doc: str, name: str = "PlateProfile", body: str | None = None,
                      width: float = 60, depth: float = 40) -> dict:
    args = {"doc": doc, "name": name, "plane": "XY"}
    if body:
        args["body"] = body
    await m.call("sketch_create", args)
    return await m.call("sketch_add_geometry", {"doc": doc, "sketch": name,
                                                "geometry": rect_geometry(width, depth),
                                                "constraints": rect_constraints(width, depth)})


async def plate(m: Mcp, doc: str) -> dict:
    """PlateBody / PlateProfile (60 x 40, 11 constraints) / PlatePad 5 mm."""
    await m.call("feature_body_create", {"doc": doc, "name": "PlateBody"})
    await rect_sketch(m, doc, "PlateProfile", body="PlateBody")
    return await m.call("feature_pad", {"doc": doc, "body": "PlateBody", "profile": "PlateProfile",
                                        "name": "PlatePad", "length": {"value": 5, "unit": "mm"}})


def go(name: str, body) -> None:
    asyncio.run(run(name, body))


def model_items(state: dict, label: str) -> list[dict]:
    """Model-tree rows only (the property editor below also exposes TreeItem rows)."""
    return [e for e in state.get("elements", []) if e.get("role") == "TreeItem" and e.get("label") == label
            and (e.get("frame") or {}).get("y", 9999) < 760]


def in_edit() -> bool:
    return bool([e for e in find(snapshot(), role="Button", label="Close") if (e.get("frame") or {}).get("y", 0) > 300])


def zoom_out(times: int = 1) -> list:
    """View > Zoom > Zoom Out. The submenu's actions are not in UIA, so click its 2nd row by pixel."""
    pid, win = ids()
    out = []
    for _ in range(times):
        cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["View", "Zoom"]})
        time.sleep(0.6)
        popups = [w for w in cua("list_windows", {"pid": pid}).get("windows", [])
                  if w["window_id"] != win and w["bounds"]["height"] < 120]
        if not popups:
            out.append("no zoom popup")
            continue
        r = cua("click", {"pid": pid, "window_id": popups[0]["window_id"], "x": 70, "y": 45})
        out.append(r.get("effect"))
        time.sleep(0.8)
        for w in cua("list_windows", {"pid": pid}).get("windows", []):
            if w["window_id"] != win:
                cua("press_key", {"pid": pid, "window_id": w["window_id"], "key": "escape"})
    return out


def edit_open(label: str) -> dict:
    """FreeCAD's own sketch edit: double-click the tree item (cua-driver), pixel fallback."""
    state = snapshot()
    pid, win = ids()
    items = model_items(state, label)
    if not items:
        return {"error": f"no TreeItem {label!r}"}
    frame = items[0]["frame"]
    scale = 1568 / 1775
    x, y = round((frame["x"] + 90) * scale), round((frame["y"] + frame["h"] / 2) * scale)
    for _attempt in range(3):
        result = cua("double_click", {"pid": pid, "window_id": win, "x": x, "y": y, "delivery_mode": "foreground"})
        time.sleep(2.0)
        opened = in_edit()
        if opened:
            break
    return {"double_click": label, "xy": [x, y], "effect": result.get("effect"), "route": result.get("route"),
            "edit_open": opened}


def edit_close() -> dict:
    """Leave sketch edit with the Tasks panel Close button (never the title-bar Close)."""
    state = snapshot()
    pid, _ = ids()
    for element in find(state, role="Button", label="Close"):
        if (element.get("frame") or {}).get("y", 0) > 300:
            result = cua("click", {"pid": pid, "element_token": element["element_token"]})
            time.sleep(1.0)
            return {"clicked": "Tasks Close", "effect": result.get("effect"), "route": result.get("route")}
    return {"error": "no Tasks Close button (not in edit mode)"}


def expand(label: str) -> dict:
    """Expand a collapsed tree item by clicking its arrow (pixel; UIA expand is ignored by FreeCAD's tree)."""
    state = snapshot()
    pid, win = ids()
    items = model_items(state, label)
    if not items:
        return {"error": f"no TreeItem {label!r}"}
    frame = items[0]["frame"]
    scale = 1568 / 1775
    x, y = round((frame["x"] - 12) * scale), round((frame["y"] + frame["h"] / 2) * scale)
    before = len([e for e in state.get("elements", []) if e.get("role") == "TreeItem"])
    for _ in range(3):
        result = cua("click", {"pid": pid, "window_id": win, "x": x, "y": y})
        time.sleep(1.0)
        after = len([e for e in snapshot().get("elements", []) if e.get("role") == "TreeItem"])
        if after > before:
            break
    return {"expand": label, "xy": [x, y], "effect": result.get("effect"), "items_before": before, "items_after": after}


def edit_capture(label: str, png: str, fit: bool = True, parent: str | None = None, wide: bool = True) -> dict:
    record = {}
    state = snapshot()
    if parent and not model_items(state, label):
        for one in ([parent] if isinstance(parent, str) else parent):
            if model_items(snapshot(), one):
                record.setdefault("expand", []).append(expand(one))
    record["open"] = edit_open(label)
    if not record["open"].get("edit_open"):
        record["error"] = "sketch edit did not open"
        return record
    pid, win = ids()
    if wide:
        record["frame_wide"] = cua("set_window_frame", {"pid": pid, "window_id": win, "x": 0, "y": 0,
                                                        "width": 2560, "height": 1380}).get("effect")
        time.sleep(1.0)
    if fit:
        record["fitall"] = fitall()
    record["shot"] = shot(png)
    if wide:
        record["frame_restore"] = cua("set_window_frame", {"pid": pid, "window_id": win, "x": 0, "y": 0,
                                                           "width": 1775, "height": 1380}).get("effect")
        time.sleep(1.0)
    record["close"] = edit_close()
    time.sleep(1.0)
    record["closed"] = not in_edit()
    return record
