"""Call query_tree_summary over the live GUI bridge for each spec matrix case and record raw blocks.

Opens the document given on the command line (a copy), runs every case, and writes one JSON record
per case with the number of content blocks, the parsed JSON block and the raw tree block, so the
report can check that the tree is never inside the JSON block or structuredContent.

    uv run python tests/uat/run/2026-10-08-01/evidence/tree_calls.py <document copy> <out json>
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ENDPOINT = "http://127.0.0.1:8765/mcp"

CASES = [
    ("top-level", {}),
    ("focus-body", {"focus": "front_plate_piece"}),
    ("expand-deep", {"expand": ["sma_boss"]}),
    ("focus-expand-sample", {"focus": "front_plate_piece", "expand": ["sma_boss"]}),
    ("call-128-shape", {"focus": "front_plate_piece", "depth": 3}),
    ("cross-body-base", {"focus": "tray_piece", "depth": 3}),
    ("reveal-name", {"filters": {"name_pattern": "joint2.*"}}),
    ("reveal-code", {"focus": "tray_piece", "filters": {"types": ["DPLANE"]}}),
    ("no-match", {"filters": {"name_pattern": "zzz"}}),
    ("all-open", {"depth": 6}),
    ("bad-name", {"focus": "nope"}),
]


async def main(document: str, out: str) -> None:
    records = []
    async with streamablehttp_client(ENDPOINT) as (read, write, _), ClientSession(
        read, write
    ) as session:
        await session.initialize()
        opened = await session.call_tool("document_open", {"path": document})
        handle = json.loads(opened.content[0].text)["structured_content"]["doc"]
        for name, args in CASES:
            result = await session.call_tool("query_tree_summary", {"doc": handle, **args})
            blocks = [block.text for block in result.content if hasattr(block, "text")]
            json_block = json.loads(blocks[0])
            records.append(
                {
                    "case": name,
                    "args": args,
                    "blocks": len(blocks),
                    "json_block": json_block,
                    "json_block_chars": len(blocks[0]),
                    "structured_keys": sorted((result.structuredContent or {}).keys()),
                    "tree": blocks[1] if len(blocks) > 1 else None,
                    "total_chars": sum(len(block) for block in blocks),
                }
            )
        await session.call_tool("document_close", {"doc": handle})
    with open(out, "w", encoding="utf-8") as handle_out:
        json.dump(records, handle_out, indent=2, ensure_ascii=False)
    for record in records:
        print(
            f"{record['case']}: status={record['json_block']['status']} "
            f"blocks={record['blocks']} total_chars={record['total_chars']}"
        )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
