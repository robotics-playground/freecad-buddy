"""Shared helpers for the TC-13 / TC-12-12..15 executors (UAT run 2026-10-03-04).

MCP over HTTP (persistent session) + cua-driver window-targeted, background-only GUI calls.
Every call is appended to a JSONL log so the evidence holds the raw envelopes.
"""

from __future__ import annotations

import json
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EVIDENCE = Path(__file__).resolve().parent
ROOT = "D:/Work/Personal/Sources/freecad-buddy"
GOLD = ROOT + "/benchmarks/g0/golden-models/"
ENDPOINT = "http://127.0.0.1:8765/mcp"


def ids() -> tuple[int, int]:
    data = json.loads((EVIDENCE / "fc.json").read_text())
    return int(data["pid"]), int(data["window_id"])


class Log:
    def __init__(self, name: str):
        self.path = EVIDENCE / name
        self.path.write_text("", encoding="utf-8")

    def __call__(self, kind: str, **fields):
        fields = {"t": time.strftime("%H:%M:%S"), "kind": kind, **fields}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(fields, default=str) + "\n")
        brief = json.dumps(fields, default=str)
        print(brief[:1500])


def cua(tool: str, payload: dict, timeout: int = 90) -> dict:
    out = subprocess.run(
        ["cua-driver", tool], input=json.dumps(payload), capture_output=True, text=True, timeout=timeout
    )
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return {"_raw": out.stdout[-2000:], "_err": out.stderr[-2000:]}


def snap(shot: str | None = None) -> dict:
    pid, win = ids()
    payload = {"pid": pid, "window_id": win}
    if shot:
        payload["screenshot_out_file"] = str(EVIDENCE / shot).replace("\\", "/")
    else:
        payload["include_screenshot"] = False
    return cua("get_window_state", payload)


def elements(state: dict, role: str | None = None, label: str | None = None, contains: str | None = None):
    found = []
    for element in state.get("elements", []):
        if role and element.get("role") != role:
            continue
        lab = element.get("label") or ""
        if label is not None and lab != label:
            continue
        if contains is not None and contains not in lab:
            continue
        found.append(element)
    return found


def tree_items(state: dict) -> list[str]:
    return [e.get("label") for e in elements(state, role="TreeItem")]


def click_token(token: str, **extra) -> dict:
    pid, _ = ids()
    return cua("click", {"pid": pid, "element_token": token, **extra})


def click_label(role: str, label: str, **extra) -> dict:
    state = snap()
    match = [e for e in elements(state, role=role, label=label) if (e.get("frame") or {}).get("y", 99) > 40]
    match = match or elements(state, role=role, label=label)
    if not match:
        return {"error": f"no {role} labelled {label!r}"}
    result = click_token(match[0]["element_token"], **extra)
    result["_token"] = match[0]["element_token"]
    return result


def menu(path: list[str]) -> dict:
    pid, win = ids()
    return cua("invoke_menu", {"pid": pid, "window_id": win, "path": path})


def fitall() -> dict:
    return click_label("Button", "Fit All")


def slim(result: dict) -> dict:
    return {k: v for k, v in result.items() if k in ("effect", "route", "error", "escalation", "_token", "delivery", "code", "message", "_raw", "_err")}


@asynccontextmanager
async def mcp_session():
    async with streamablehttp_client(ENDPOINT) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def call(session: ClientSession, tool: str, args: dict, log: Log | None = None) -> dict:
    started = time.perf_counter()
    result = await session.call_tool(tool, args)
    elapsed = round(time.perf_counter() - started, 3)
    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    try:
        envelope = json.loads(text)
    except json.JSONDecodeError:
        envelope = {"_raw": text}
    if log:
        log("mcp", tool=tool, args=args, elapsed_s=elapsed, envelope=envelope)
    return envelope


async def mutate(session, doc: str, tool: str, args: dict, log: Log | None = None) -> dict:
    op_args = {k: v for k, v in args.items() if k != "doc"}
    preview = await call(session, "preview_dry_run", {"doc": doc, "operation": {"tool": tool, "args": op_args}}, log)
    pid = (preview.get("structured_content") or {}).get("preview_id")
    return await call(session, tool, {**args, "confirm": {"preview_id": pid, "elicitation_action": "accept"}}, log)


def sc(envelope: dict) -> dict:
    return envelope.get("structured_content") or {}


def write_result(file: str, row: dict) -> None:
    path = EVIDENCE / file
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    rows = [r for r in rows if r["id"] != row["id"]] + [row]
    rows.sort(key=lambda r: r["id"])
    path.write_text(json.dumps(rows, indent=1), encoding="utf-8")


def menu_retry(path: list[str], tries: int = 6, wait: float = 5.0) -> dict:
    """invoke_menu needs a foreground popup; while the desktop is in use it is refused, so retry."""
    result = {}
    for attempt in range(tries):
        snap()
        result = menu(path)
        result["_attempt"] = attempt + 1
        if result.get("status") != "refused":
            return result
        time.sleep(wait)
    return result
