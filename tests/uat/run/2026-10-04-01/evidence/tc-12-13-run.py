"""TC-12-13 executor, UAT run 2026-10-04-01. Phases: setup | given | stale | cleanup.

Every MCP call is appended raw to tc-12-13-mcp.jsonl with its elapsed time.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EVIDENCE = Path(__file__).resolve().parent
GOLD = "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/"
ENDPOINT = "http://127.0.0.1:8765/mcp"
LOG = EVIDENCE / "tc-12-13-mcp.jsonl"
HANDLES = EVIDENCE / "tc-12-13-handles.json"


async def call(session: ClientSession, tool: str, args: dict, step: str) -> dict:
    started = time.perf_counter()
    result = await session.call_tool(tool, args)
    elapsed = round(time.perf_counter() - started, 3)
    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    try:
        envelope = json.loads(text)
    except json.JSONDecodeError:
        envelope = {"_raw": text, "_isError": result.isError}
    row = {"t": time.strftime("%H:%M:%S"), "step": step, "tool": tool, "args": args, "elapsed_s": elapsed, "envelope": envelope}
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    print(json.dumps(row)[:900])
    return envelope


def sc(envelope: dict) -> dict:
    return envelope.get("structured_content") or {}


async def main(phase: str) -> None:
    async with streamablehttp_client(ENDPOINT) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()
            if phase == "setup":
                b = await call(s, "document_open", {"path": GOLD + "cylinder-r5-h20.FCStd"}, "setup-open-B")
                HANDLES.write_text(json.dumps({"B": sc(b)["doc"]}))
            elif phase == "given":
                h = json.loads(HANDLES.read_text())
                a = await call(s, "document_open", {"path": GOLD + "box-10-20-30.FCStd"}, "setup-open-A")
                h["A"] = sc(a)["doc"]
                HANDLES.write_text(json.dumps(h))
                await call(s, "document_list", {}, "given-list")
                await call(s, "query_tree_summary", {"doc": h["A"]}, "given-tree-A")
                await call(s, "query_tree_summary", {"doc": h["B"]}, "given-tree-B")
                await call(s, "query_mass_properties", {"doc": h["B"], "object": "Cylinder"}, "given-mass-B-original")
                await call(s, "document_list", {}, "when-record-handles")
            elif phase == "stale":
                h = json.loads(HANDLES.read_text())
                await call(s, "query_tree_summary", {"doc": h["A"]}, "stale-tree")
                await call(s, "query_mass_properties", {"doc": h["A"]}, "stale-mass-as-written")
                await call(s, "query_mass_properties", {"doc": h["A"], "object": "Box"}, "stale-mass-with-object")
                await call(s, "query_screenshot", {"doc": h["A"]}, "stale-screenshot")
                await call(s, "document_close", {"doc": h["A"]}, "stale-close")
                await call(s, "document_list", {}, "final-list")
                await call(s, "query_mass_properties", {"doc": h["B"]}, "final-mass-B-as-written")
                await call(s, "query_mass_properties", {"doc": h["B"], "object": "Cylinder"}, "final-mass-B-with-object")
                await call(s, "query_capabilities", {}, "listener-intact")
                await call(s, "view_fit_viewport", {"doc": h["B"]}, "fit-B")
            elif phase == "cleanup":
                h = json.loads(HANDLES.read_text())
                await call(s, "document_close", {"doc": h["B"]}, "cleanup-close-B")
                await call(s, "document_list", {}, "cleanup-list")


asyncio.run(main(sys.argv[1]))
