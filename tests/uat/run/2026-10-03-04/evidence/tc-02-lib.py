"""TC-02 executor helpers: one MCP session per scenario, every call logged to JSONL.

Used by tc-02-run.py. Only cua-driver touches the window; MCP goes over http://127.0.0.1:8765/mcp.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from mcp import ClientSession

EVIDENCE = Path(__file__).resolve().parent
RUN_DIR = EVIDENCE.parent
PROJECT_ROOT = Path("D:/Work/Personal/Sources/freecad-buddy")
GOLDEN = f"{PROJECT_ROOT.as_posix()}/benchmarks/g0/golden-models"
EV = EVIDENCE.as_posix()


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


def fitall() -> dict:
    state = snapshot()
    pid, _ = ids()
    for element in find(state, role="Button", label="Fit All"):
        result = cua("click", {"pid": pid, "element_token": element["element_token"]})
        time.sleep(1.0)
        return {"clicked": "Fit All", "effect": result.get("effect"), "route": result.get("route"), "raw": result}
    return {"error": "no Fit All button", "count": state.get("element_count")}


def tree_items(state: dict, label: str) -> list[dict]:
    return [e for e in state.get("elements", [])
            if (e.get("label") or "") == label and "Item" in (e.get("role") or "") and e.get("role") != "MenuItem"]


def click_tree(label: str, index: int = 0) -> dict:
    state = snapshot()
    pid, _ = ids()
    items = tree_items(state, label)
    if len(items) <= index:
        return {"error": f"no tree item {label!r}", "roles": sorted({e.get('role') for e in state.get('elements', [])})}
    result = cua("click", {"pid": pid, "element_token": items[index]["element_token"]})
    time.sleep(0.5)
    return {"clicked": label, "role": items[index].get("role"), "effect": result.get("effect"), "route": result.get("route"), "raw": result}


def toggle_visibility(label: str) -> dict:
    """Select the tree item through cua-driver, then press Space (FreeCAD's Std_ToggleVisibility)."""
    clicked = click_tree(label)
    pid, win = ids()
    key = cua("press_key", {"pid": pid, "window_id": win, "key": "space"})
    time.sleep(0.8)
    return {"click": {k: clicked.get(k) for k in ("clicked", "role", "effect", "route", "error")},
            "key": {k: key.get(k) for k in ("effect", "route", "error", "refusal")}}


def close_popups() -> list:
    pid, win = ids()
    listing = cua("list_windows", {"pid": pid})
    closed = []
    for window in listing.get("windows", []):
        if window["window_id"] != win:
            cua("press_key", {"pid": pid, "window_id": window["window_id"], "key": "escape"})
            closed.append(window["window_id"])
    return closed


def show_all() -> dict:
    """FreeCAD's own View > Visibility > Show All Objects (active document)."""
    pid, win = ids()
    result = cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["View", "Visibility", "Show All Objects"]})
    time.sleep(1.0)
    popups = close_popups()
    return {"effect": result.get("effect"), "route": result.get("route"), "refusal": result.get("refusal"), "popups_closed": popups}


def shot(name: str) -> dict:
    pid, win = ids()
    path = f"{EV}/{name}"
    result = cua("get_window_state", {"pid": pid, "window_id": win, "screenshot_out_file": path})
    return {"file": path, "exists": Path(path).exists(), "window_title": _title(result)}


def _title(state: dict) -> str | None:
    tree = state.get("tree_markdown") or ""
    return tree.splitlines()[0][:200] if tree else None


class Log:
    def __init__(self, name: str):
        self.path = EVIDENCE / f"{name}.jsonl"
        self.path.write_text("", encoding="utf-8")
        self.checks: list[str] = []

    def write(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def check(self, name: str, ok: bool, detail: object = "") -> bool:
        line = f"{'PASS' if ok else 'FAIL'} | {name} | {detail}"
        self.checks.append(line)
        self.write({"check": name, "ok": bool(ok), "detail": detail})
        print(line)
        return ok

    def note(self, text: str) -> None:
        self.write({"note": text})
        print("NOTE", text)


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
        envelope_record = envelope if isinstance(envelope, dict) else {"_value": envelope}
        self.log.write({
            "tool": tool, "args": args, "isError": bool(getattr(result, "isError", False)),
            "seconds": round(time.time() - started, 3), "envelope": envelope_record,
        })
        if isinstance(envelope, dict):
            envelope["_isError"] = bool(getattr(result, "isError", False))
        return envelope

    async def mutate(self, doc: str, tool: str, args: dict) -> dict:
        op_args = {k: v for k, v in args.items() if k != "doc"}
        preview = await self.call("preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": op_args}})
        preview_id = (preview.get("structured_content") or {}).get("preview_id")
        if not preview_id:
            return {"status": "PREVIEW_FAILED", "preview": preview}
        return await self.call(tool, {**op_args, "doc": doc, "confirm": {"preview_id": preview_id, "elicitation_action": "accept"}})


def sc(envelope: dict) -> dict:
    return envelope.get("structured_content") or {}
