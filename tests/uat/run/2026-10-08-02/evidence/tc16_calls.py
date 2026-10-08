"""Call one freecad-buddy tool over the live HTTP bridge and record its raw result.

Usage: uv run python tc16_calls.py <log.jsonl> <label> <tool> '<json args>'

Appends one JSON line to <log.jsonl>: label, tool, args, wall-clock seconds, every raw content
block, each block's character count, isError and structuredContent. Prints the first block (the
JSON envelope) and the counts. Sizes are taken from the raw blocks, which is what an agent's
context pays for.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ENDPOINT = "http://127.0.0.1:8765/mcp"


async def main() -> int:
    log_path, label, tool, raw_args = sys.argv[1:5]
    args = json.loads(raw_args)
    async with streamablehttp_client(ENDPOINT, timeout=600, sse_read_timeout=600) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            started = time.perf_counter()
            result = await session.call_tool(tool, args)
            elapsed = time.perf_counter() - started
    blocks = [block.text for block in result.content if hasattr(block, "text")]
    record = {
        "label": label,
        "tool": tool,
        "args": args,
        "seconds": round(elapsed, 3),
        "blocks": blocks,
        "chars": [len(block) for block in blocks],
        "is_error": result.isError,
        "structured": result.structuredContent,
    }
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"[{label}] {tool} {elapsed:.2f}s chars={record['chars']} isError={result.isError}")
    for block in blocks:
        print(block)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
