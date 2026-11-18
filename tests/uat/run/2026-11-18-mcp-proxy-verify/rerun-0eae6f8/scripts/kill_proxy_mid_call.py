"""Live P8: hard-kill FreeCAD while a long script_exec runs through the proxy; the call must answer."""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
T0 = time.monotonic()


def log(text: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} +{time.monotonic() - T0:6.1f}s {text}"
    print(line, flush=True)
    with open(OUT / "live.log", "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


async def main() -> None:
    config = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["freecad-buddy-docker"]
    parameters = StdioServerParameters(command=config["command"], args=config["args"], cwd="C:\\")
    errlog = open(OUT / "proxy-p8.stderr.log", "w", encoding="utf-8")
    async with stdio_client(parameters, errlog=errlog) as streams, ClientSession(*streams) as session:
        await session.initialize()
        created = await session.call_tool("document_create", {"label": "ProxyKill"})
        doc = created.structuredContent["structured_content"]["doc"]
        code = "import time\ntime.sleep(25)\nresult = 1"
        task = asyncio.ensure_future(session.call_tool("script_exec", {"doc": doc, "code": code}))
        await asyncio.sleep(5)
        killed = subprocess.run(
            "docker exec fcb-desktop pkill -9 -f freecad_buddy.hosts.main",
            shell=True, capture_output=True, text=True,
        )
        killed_at = time.monotonic()
        log(f"P8 in-container MCP proxy hard-killed during a 40 s script_exec (pkill exit={killed.returncode})")
        try:
            result = await asyncio.wait_for(task, 60)
            log(
                f"P8 answered {time.monotonic() - killed_at:.1f}s after the kill: isError={result.isError} "
                f"text={result.content[0].text[:260]!r}"
            )
        except TimeoutError:
            log("P8 NO ANSWER 60 s after the kill (HANG)")
        follow = await session.call_tool("query_capabilities", {})
        log(f"P8 next call: isError={follow.isError} text={follow.content[0].text[:160]!r}")
    errlog.close()


asyncio.run(main())
