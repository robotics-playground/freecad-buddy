"""Call script_exec once over MCP HTTP and dump the raw CallToolResult as JSON."""

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:18765/mcp"
CODE = (
    "for i in range(5):\n"
    "    print('stdout line %d of the 13-1 live check, padded to exceed eighty characters' % i)\n"
    "result = ['value_repr element %02d' % i for i in range(10)]\n"
)


async def main(out_path: str) -> None:
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            assert "script_exec" in names, names
            created = await session.call_tool("document_create", {"label": "Verify131"})
            doc = created.structuredContent["structured_content"]["doc"]
            args = {"doc": doc, "code": CODE}
            result = await session.call_tool("script_exec", args)
            dumped = result.model_dump(mode="json")
            with open(out_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "document_create": created.model_dump(mode="json"),
                        "request": {"tool": "script_exec", "arguments": args},
                        "response": dumped,
                    },
                    handle,
                    indent=2,
                )
            print(json.dumps(dumped, indent=2)[:4000])


asyncio.run(main(sys.argv[1]))
