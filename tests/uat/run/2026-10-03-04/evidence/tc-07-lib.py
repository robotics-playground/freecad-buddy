"""Shared MCP client for TC-07 scenario scripts (UAT run 2026-10-03-04).

Each scenario script does:  lib = load(); async with lib.Session("tc-07-MM") as s: env = await s.call(tool, args)
Every call and its full envelope is appended to evidence/tc-07-MM-mcp.jsonl.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ENDPOINT = "http://127.0.0.1:8765/mcp"
EVIDENCE = Path(__file__).resolve().parent
EV = str(EVIDENCE).replace("\\", "/")
ROOT = "D:/Work/Personal/Sources/freecad-buddy"
GOLD = ROOT + "/benchmarks/g0/golden-models"


class Session:
    def __init__(self, tag: str):
        self.tag = tag
        self.log = open(EVIDENCE / f"{tag}-mcp.jsonl", "a", encoding="utf-8")
        self.results: list[tuple[str, bool, str]] = []

    async def __aenter__(self):
        self._cm = streamablehttp_client(ENDPOINT)
        read, write, _ = await self._cm.__aenter__()
        self._sess = ClientSession(read, write)
        await self._sess.__aenter__()
        await self._sess.initialize()
        return self

    async def __aexit__(self, *exc):
        await self._sess.__aexit__(*exc)
        await self._cm.__aexit__(*exc)
        self.log.close()
        with open(EVIDENCE / f"{self.tag}-checks.txt", "a", encoding="utf-8") as f:
            for name, ok, note in self.results:
                f.write(f"{'PASS' if ok else 'FAIL'}\t{name}\t{note}\n")

    async def call(self, tool: str, args: dict) -> dict:
        t0 = time.time()
        result = await self._sess.call_tool(tool, args)
        text = "".join(b.text for b in result.content if hasattr(b, "text"))
        try:
            env = json.loads(text)
        except json.JSONDecodeError:
            env = {"_raw": text}
        if isinstance(env, dict):
            env["_isError"] = bool(result.isError)
        self.log.write(json.dumps({"t": round(t0, 3), "dt": round(time.time() - t0, 3), "tool": tool,
                                   "args": args, "envelope": env}, ensure_ascii=False) + "\n")
        self.log.flush()
        return env

    def check(self, name: str, ok: bool, note: object = "") -> bool:
        note_s = note if isinstance(note, str) else json.dumps(note, ensure_ascii=False)
        self.results.append((name, bool(ok), note_s))
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {note_s[:300]}")
        return bool(ok)

    async def open(self, path: str) -> tuple[str, str | None]:
        env = await self.call("document_open", {"path": path})
        doc = env["structured_content"]["doc"]
        tree = await self.call("query_tree_summary", {"doc": doc})
        nodes = tree["structured_content"]["tree"]
        return doc, (nodes[0]["name"] if nodes else None)


def sc(env: dict) -> dict:
    return env.get("structured_content") or {}


def checks(env: dict) -> dict:
    return {c["id"]: c for c in (sc(env).get("checks") or [])}
