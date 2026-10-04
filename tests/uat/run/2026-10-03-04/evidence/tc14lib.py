"""TC-14 executor helpers: one MCP session, every call logged to JSONL, mutations via preview+confirm.

Only cua-driver touches the window; MCP goes over http://127.0.0.1:8765/mcp.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EVIDENCE = Path(__file__).resolve().parent
EV = EVIDENCE.as_posix()
GOLDEN = "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models"
BOX = f"{GOLDEN}/box-10-20-30.FCStd"


def ids() -> tuple[int, int]:
    data = json.loads((EVIDENCE / "fc.json").read_text())
    return int(data["pid"]), int(data["window_id"])


def cua(tool: str, payload: dict, timeout: int = 60) -> dict:
    out = subprocess.run(["cua-driver", tool], input=json.dumps(payload), capture_output=True, text=True,
                         timeout=timeout, encoding="utf-8")
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return {"_raw": out.stdout[-2000:], "_err": out.stderr[-2000:]}


def menu(path: list[str]) -> dict:
    pid, win = ids()
    result = cua("invoke_menu", {"pid": pid, "window_id": win, "path": path})
    time.sleep(0.7)
    return {k: result.get(k) for k in ("effect", "route", "error", "refusal")}


def click_button(label: str) -> dict:
    pid, win = ids()
    state = cua("get_window_state", {"pid": pid, "window_id": win, "include_screenshot": False})
    for element in state.get("elements", []):
        if element.get("role") == "Button" and element.get("label") == label:
            result = cua("click", {"pid": pid, "element_token": element["element_token"]})
            time.sleep(1.0)
            return {"clicked": label, "effect": result.get("effect"), "route": result.get("route")}
    return {"error": f"no Button {label!r}"}


def shot(name: str) -> dict:
    pid, win = ids()
    path = f"{EV}/{name}"
    cua("get_window_state", {"pid": pid, "window_id": win, "screenshot_out_file": path})
    return {"file": path, "exists": Path(path).exists()}


def q(value, unit="mm"):
    return {"value": value, "unit": unit}


def rect_profile(w, h):
    pts = [(0, 0), (w, 0), (w, h), (0, h)]
    geometry = [{"kind": "line_segment", "start": list(pts[i]), "end": list(pts[(i + 1) % 4])} for i in range(4)]
    constraints = [
        {"type": "Coincident", "first": i, "first_pos": 2, "second": (i + 1) % 4, "second_pos": 1} for i in range(4)
    ] + [
        {"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2},
        {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
        {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": q(w)},
        {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": q(h)},
        {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
    ]
    return geometry, constraints


class Log:
    def __init__(self, name: str):
        self.path = EVIDENCE / f"{name}.jsonl"
        self.path.write_text("", encoding="utf-8")

    def write(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def check(self, name: str, ok, detail: object = "") -> None:
        line = f"{'PASS' if ok else 'FAIL'} | {name} | {detail}"
        self.write({"check": name, "ok": bool(ok), "detail": detail})
        print(line)

    def note(self, text: str) -> None:
        self.write({"note": text})
        print("NOTE", text)


class Mcp:
    def __init__(self, session: ClientSession, log: Log):
        self.session = session
        self.log = log

    async def call(self, tool: str, args: dict) -> dict:
        started = time.time()
        try:
            result = await self.session.call_tool(tool, args)
        except Exception as exc:  # transport-level error is evidence too
            envelope = {"_exception": f"{type(exc).__name__}: {exc}"}
            self.log.write({"tool": tool, "args": args, "envelope": envelope})
            return envelope
        text = "".join(block.text for block in result.content if hasattr(block, "text"))
        try:
            envelope = json.loads(text)
        except json.JSONDecodeError:
            envelope = {"_raw": text}
        self.log.write({"tool": tool, "args": args, "isError": bool(getattr(result, "isError", False)),
                        "seconds": round(time.time() - started, 3), "envelope": envelope})
        return envelope

    async def mutate(self, doc: str, tool: str, args: dict) -> dict:
        preview = await self.call("preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": args}})
        preview_id = (preview.get("structured_content") or {}).get("preview_id")
        if not preview_id:
            return {"status": "PREVIEW_FAILED", "preview": preview}
        return await self.call(tool, {**args, "doc": doc,
                                      "confirm": {"preview_id": preview_id, "elicitation_action": "accept"}})

    async def bar(self, doc: str, w=40, d=40, length=800) -> dict:
        """Body + fully constrained w x d rectangle on XY + pad ``length``."""
        out = {}
        out["body"] = (await self.mutate(doc, "feature_body_create", {"name": "Body"})).get("status")
        out["sketch"] = (await self.mutate(doc, "sketch_create", {"name": "BarProfile", "body": "Body",
                                                                  "plane": "XY"})).get("status")
        geometry, constraints = rect_profile(w, d)
        out["geometry"] = (await self.mutate(doc, "sketch_add_geometry", {
            "sketch": "BarProfile", "geometry": geometry, "constraints": constraints})).get("status")
        out["pad"] = (await self.mutate(doc, "feature_pad", {"body": "Body", "profile": "BarProfile",
                                                             "name": "Bar", "length": q(length)})).get("status")
        return out


def sc(envelope: dict) -> dict:
    return envelope.get("structured_content") or {}


def fr(envelope: dict) -> dict:
    return envelope.get("framing") or {}


def vol(envelope: dict):
    v = sc(envelope).get("volume")
    return v.get("value") if isinstance(v, dict) else v


def go(name: str, body) -> None:
    async def main():
        log = Log(name)
        async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await body(Mcp(session, log), log)

    asyncio.run(main())
    sys.stdout.flush()
