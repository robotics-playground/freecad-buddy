"""Start the proxy the way .mcp.json does and drive it as a client: time, list, notifications, calls.

uv run python drive_proxy.py --server NAME [--call TOOL JSON]... [--watch SECONDS] [--cwd DIR]
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parents[4]
parser = argparse.ArgumentParser()
parser.add_argument("--server", required=True)
parser.add_argument("--call", nargs=2, action="append", default=[], metavar=("TOOL", "JSON"))
parser.add_argument("--watch", type=float, default=0)
parser.add_argument("--cwd", default="C:\\")
arguments = parser.parse_args()


async def main() -> None:
    parameters = StdioServerParameters(
        command="uv",
        args=[
            "run",
            "--no-sync",
            "--project",
            str(REPO),
            "python",
            str(REPO / "scripts/automation/mcp_cache_proxy.py"),
            "--server",
            arguments.server,
        ],
        cwd=arguments.cwd,
    )
    events: list[str] = []

    async def on_message(message) -> None:
        if isinstance(message, types.ServerNotification):
            events.append(f"{time.strftime('%H:%M:%S')} notification {message.root.method}")
            print(events[-1], flush=True)

    started = time.monotonic()
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write, message_handler=on_message) as session:
            initialized = await session.initialize()
            print(
                f"initialize ok in {time.monotonic() - started:.2f}s; "
                f"tools.listChanged={initialized.capabilities.tools.listChanged}",
                flush=True,
            )
            listed = await session.list_tools()
            print(
                f"tools/list ok at {time.monotonic() - started:.2f}s: {len(listed.tools)} tools",
                flush=True,
            )
            print("  " + ", ".join(tool.name for tool in listed.tools[:8]), flush=True)
            for tool, raw in arguments.call:
                begun = time.monotonic()
                result = await session.send_request(
                    types.ClientRequest(
                        types.CallToolRequest(
                            params=types.CallToolRequestParams(name=tool, arguments=json.loads(raw))
                        )
                    ),
                    types.CallToolResult,
                )
                print(f"call {tool} in {time.monotonic() - begun:.2f}s isError={result.isError}")
                print(
                    "  structuredContent keys:", list((result.structuredContent or {}).keys())[:8]
                )
                print("  text:", result.content[0].text[:600].replace("\n", " | "), flush=True)
            if arguments.watch:
                await asyncio.sleep(arguments.watch)
                relisted = await session.list_tools()
                print(f"after watch: {len(relisted.tools)} tools; notifications={len(events)}")


asyncio.run(main())
