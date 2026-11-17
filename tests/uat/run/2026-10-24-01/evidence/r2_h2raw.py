"""One raw MCP call on the :8765 proxy, logged with isError, whether structuredContent is null and the
text blocks, then tools/list again: r2_h2raw.py <tag> <tool> '<json>'. Appends to evidence/<tag>-h2raw.jsonl."""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EVIDENCE = Path(__file__).resolve().parent


async def main():
    tag, tool, args = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            raw = await session.call_tool(tool, args)
            after = (await session.list_tools()).tools
    entry = {"mcp": tool, "args": args, "is_error": bool(raw.isError),
             "structured_content_is_null": raw.structuredContent is None,
             "text": [b.text for b in raw.content if getattr(b, "type", "") == "text"],
             "tools_list_after_count": len(after)}
    with (EVIDENCE / f"{tag}-h2raw.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps(entry, ensure_ascii=False))


asyncio.run(main())
