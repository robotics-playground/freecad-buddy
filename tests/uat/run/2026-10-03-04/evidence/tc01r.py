"""TC-01 re-run helpers (UAT run 2026-10-03-04, src at bece7ac). Background delivery only.

Usage (uv run python tc01r.py ...):
    mcp <tag> <tool> '<json>'   one MCP call over :8765; envelope appended to tc-01r-<tag>-mcp.jsonl
    open <tag>                 document_open box-10-20-30, Show All Objects (invoke_menu), view_fit_viewport
    fit <tag> <doc>            view_fit_viewport {doc}
    closeall <tag>             document_close every open document
    showall                    View > Visibility > Show All Objects through invoke_menu, then list windows
    windows                    list_windows for the live pid
    fitshot <png>              FreeCAD's Fit All toolbar button by element_token, then a window capture
    shot <png>                 window capture only
PID / WIN come from evidence/fc.json.
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
BOX = "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"
ENDPOINT = "http://127.0.0.1:8765/mcp"


def ids() -> tuple[int, int]:
    data = json.loads((EVIDENCE / "fc.json").read_text())
    return int(data["pid"]), int(data["window_id"])


def cua(tool: str, payload: dict, timeout: int = 60) -> dict:
    out = subprocess.run(["cua-driver", tool], input=json.dumps(payload), capture_output=True,
                         text=True, timeout=timeout, encoding="utf-8")
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return {"_raw": out.stdout[-1500:], "_err": out.stderr[-1500:]}


def slim(result: dict) -> dict:
    keep = ("effect", "route", "error", "refusal", "status", "escalation", "code", "message", "_raw", "_err")
    return {k: v for k, v in result.items() if k in keep}


def windows() -> list:
    pid, _ = ids()
    return [{k: w.get(k) for k in ("window_id", "title", "bounds", "is_on_screen")}
            for w in cua("list_windows", {"pid": pid}).get("windows", [])]


def showall() -> dict:
    pid, win = ids()
    result = cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["View", "Visibility", "Show All Objects"]})
    time.sleep(1.0)
    return {"invoke_menu": slim(result), "windows_after": windows()}


def fitall() -> dict:
    pid, win = ids()
    state = cua("get_window_state", {"pid": pid, "window_id": win, "include_screenshot": False})
    for element in state.get("elements", []):
        if element.get("role") == "Button" and element.get("label") == "Fit All":
            result = cua("click", {"pid": pid, "element_token": element["element_token"]})
            time.sleep(1.0)
            return {"clicked": "Fit All", **slim(result)}
    return {"error": "no Fit All button", "element_count": state.get("element_count")}


def shot(name: str) -> dict:
    pid, win = ids()
    path = (EVIDENCE / name).as_posix()
    Path(path).unlink(missing_ok=True)
    result = cua("get_window_state", {"pid": pid, "window_id": win, "screenshot_out_file": path})
    return {"file": name, "exists": Path(path).exists(), "error": result.get("error") or result.get("_err")}


async def _mcp(tag: str, calls: list[tuple[str, dict]]) -> list:
    out = []
    async with streamablehttp_client(ENDPOINT) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for tool, args in calls:
                started = time.perf_counter()
                result = await session.call_tool(tool, args)
                text = "".join(b.text for b in result.content if hasattr(b, "text"))
                try:
                    env = json.loads(text)
                except json.JSONDecodeError:
                    env = {"_raw": text}
                row = {"t": time.strftime("%H:%M:%S"), "tool": tool, "args": args,
                       "elapsed_s": round(time.perf_counter() - started, 3), "envelope": env}
                with (EVIDENCE / f"tc-01r-{tag}-mcp.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row) + "\n")
                out.append(env)
    return out


def mcp(tag: str, tool: str, args: dict) -> dict:
    return asyncio.run(_mcp(tag, [(tool, args)]))[0]


def brief(env: dict) -> dict:
    return {k: env.get(k) for k in ("status", "detail", "structured_content", "framing", "text", "_raw") if env.get(k) is not None}


def main() -> int:
    cmd, *rest = sys.argv[1:] or ["help"]
    if cmd == "mcp":
        print(json.dumps(brief(mcp(rest[0], rest[1], json.loads(rest[2] if len(rest) > 2 else "{}"))), indent=1)[:4000])
    elif cmd == "open":
        env = mcp(rest[0], "document_open", {"path": BOX})
        doc = (env.get("structured_content") or {}).get("doc")
        print("open:", env.get("status"), doc)
        print("showall:", json.dumps(showall()))
        fit = mcp(rest[0], "view_fit_viewport", {"doc": doc})
        print("fit:", json.dumps(brief(fit)))
    elif cmd == "fit":
        print(json.dumps(brief(mcp(rest[0], "view_fit_viewport", {"doc": rest[1]}))))
    elif cmd == "closeall":
        docs = (mcp(rest[0], "document_list", {}).get("structured_content") or {}).get("documents", [])
        for d in docs:
            env = mcp(rest[0], "document_close", {"doc": d.get("doc") or d.get("handle")})
            print("close", d.get("label"), env.get("status"), env.get("detail"))
        print("remaining:", (mcp(rest[0], "document_list", {}).get("structured_content") or {}).get("documents"))
    elif cmd == "showall":
        print(json.dumps(showall()))
    elif cmd == "windows":
        print(json.dumps(windows()))
    elif cmd == "fitshot":
        print(json.dumps(fitall()))
        print(json.dumps(shot(rest[0])))
    elif cmd == "shot":
        print(json.dumps(shot(rest[0])))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
