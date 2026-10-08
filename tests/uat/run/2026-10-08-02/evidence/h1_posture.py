"""Drive one H1 headless host (fcb env, stdio, inline) under a controlled auto-approve posture.

Usage (from the repo uv env):
  uv run python h1_posture.py fixture <out.FCStd> <audit.jsonl> <stderr.log> <calls.jsonl>
  uv run python h1_posture.py run <label> <posture> <audit.jsonl> <stderr.log> <calls.jsonl> <fixture.FCStd> [--forged]

posture: "unset" removes FREECAD_BUDDY_AUTO_APPROVE from the child env; any other value is set
verbatim. "fixture" builds a body + fully constrained 20x20 mm sketch and saves it. "run" opens
the saved fixture in a fresh process and calls feature_pad with no confirm; with --forged it
repeats the call carrying confirm.preview_id "fcb-preview:forged.AAAA".
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

FCB_ENV = os.path.expandvars(r"%USERPROFILE%\micromamba\envs\fcb")
FCB_PYTHON = os.path.join(FCB_ENV, "python.exe")
VARIABLE = "FREECAD_BUDDY_AUTO_APPROVE"

SQUARE = {
    "geometry": [
        {"kind": "line_segment", "start": [-10, -10], "end": [10, -10]},
        {"kind": "line_segment", "start": [10, -10], "end": [10, 10]},
        {"kind": "line_segment", "start": [10, 10], "end": [-10, 10]},
        {"kind": "line_segment", "start": [-10, 10], "end": [-10, -10]},
    ],
    "constraints": [
        {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1, "second_pos": 1},
        {"type": "Coincident", "first": 1, "first_pos": 2, "second": 2, "second_pos": 1},
        {"type": "Coincident", "first": 2, "first_pos": 2, "second": 3, "second_pos": 1},
        {"type": "Coincident", "first": 3, "first_pos": 2, "second": 0, "second_pos": 1},
        {"type": "Horizontal", "first": 0},
        {"type": "Horizontal", "first": 2},
        {"type": "Vertical", "first": 1},
        {"type": "Vertical", "first": 3},
        {"type": "Symmetric", "first": 0, "first_pos": 1, "second": 2, "second_pos": 1, "third": -1, "third_pos": 1},
        {"type": "Distance", "first": 0, "value": {"value": 20, "unit": "mm"}},
        {"type": "Distance", "first": 1, "value": {"value": 20, "unit": "mm"}},
    ],
}
PAD = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": {"value": 30, "unit": "mm"}}
FORGED = {"preview_id": "fcb-preview:forged.AAAA"}


def child_env(posture: str, audit: str) -> dict:
    env = dict(os.environ)
    env.pop(VARIABLE, None)
    if posture != "unset":
        env[VARIABLE] = posture
    lib_bin = os.path.join(FCB_ENV, "Library", "bin")
    lib_lib = os.path.join(FCB_ENV, "Library", "lib")
    env["PYTHONPATH"] = lib_bin
    env["PATH"] = os.pathsep.join([lib_bin, lib_lib, env.get("PATH", "")])
    env["FREECAD_BUDDY_AUDIT_LOG"] = audit
    return env


class Recorder:
    def __init__(self, session: ClientSession, calls_path: str, label: str) -> None:
        self.session = session
        self.calls_path = calls_path
        self.label = label

    async def call(self, step: str, tool: str, args: dict) -> dict:
        started = time.perf_counter()
        result = await self.session.call_tool(tool, args)
        elapsed = time.perf_counter() - started
        blocks = [block.text for block in result.content if hasattr(block, "text")]
        envelope = result.structuredContent or {}
        record = {
            "label": f"{self.label}/{step}",
            "tool": tool,
            "args": args,
            "seconds": round(elapsed, 3),
            "is_error": result.isError,
            "status": envelope.get("status"),
            "detail": envelope.get("detail"),
            "structured": envelope,
            "blocks": blocks,
        }
        with open(self.calls_path, "a", encoding="utf-8") as log:
            log.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"[{record['label']}] {tool} status={record['status']} detail={record['detail']!r}")
        return envelope


async def fixture(out: str, audit: str, stderr_path: str, calls: str) -> int:
    params = StdioServerParameters(
        command=FCB_PYTHON,
        args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio", "--mode", "inline"],
        env=child_env("1", audit),
    )
    with open(stderr_path, "w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                rec = Recorder(session, calls, "fixture")
                created = await rec.call("create", "document_create", {"label": "posture_fixture"})
                doc = created["structured_content"]["doc"]
                await rec.call("body", "feature_body_create", {"doc": doc, "name": "Body"})
                await rec.call(
                    "sketch", "sketch_create", {"doc": doc, "name": "Sketch", "plane": "XY", "body": "Body"}
                )
                await rec.call("geom", "sketch_add_geometry", {"doc": doc, "sketch": "Sketch", **SQUARE})
                info = await rec.call("info", "query_sketch_info", {"doc": doc, "sketch": "Sketch"})
                print("fully_constrained:", info.get("structured_content", {}).get("fully_constrained"))
                await rec.call("save", "document_save", {"doc": doc, "path": out})
                await rec.call("close", "document_close", {"doc": doc})
    return 0


async def run(label: str, posture: str, audit: str, stderr_path: str, calls: str, fixture_path: str, forged: bool) -> int:
    env = child_env(posture, audit)
    print(f"[{label}] child {VARIABLE} present={VARIABLE in env} value={env.get(VARIABLE)!r} audit={audit}")
    params = StdioServerParameters(
        command=FCB_PYTHON,
        args=["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio", "--mode", "inline"],
        env=env,
    )
    with open(stderr_path, "w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                rec = Recorder(session, calls, label)
                opened = await rec.call("open", "document_open", {"path": fixture_path})
                doc = opened["structured_content"]["doc"]
                await rec.call("pad-noconfirm", "feature_pad", {"doc": doc, **PAD})
                if forged:
                    await rec.call("pad-forged", "feature_pad", {"doc": doc, **PAD, "confirm": FORGED})
                await rec.call("tree", "query_tree_summary", {"doc": doc})
                await rec.call("close", "document_close", {"doc": doc})
    return 0


def main() -> int:
    mode = sys.argv[1]
    if mode == "fixture":
        return asyncio.run(fixture(*sys.argv[2:6]))
    label, posture, audit, stderr_path, calls, fixture_path = sys.argv[2:8]
    return asyncio.run(run(label, posture, audit, stderr_path, calls, fixture_path, "--forged" in sys.argv[8:]))


if __name__ == "__main__":
    sys.exit(main())
