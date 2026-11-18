"""Live D1 case: one freecad proxy process; FreeCAD stopped, then a call at once; FreeCAD restarted."""

import asyncio
import subprocess
import time
from contextlib import AsyncExitStack

from lifecycle_proof import REPO, call, run, start_freecad

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

NAME = "freecad-buddy-docker"


async def main() -> None:
    start_freecad()
    parameters = StdioServerParameters(
        command="uv",
        args=["run", "--no-sync", "--project", str(REPO), "python",
              str(REPO / "scripts/automation/mcp_cache_proxy.py"), "--server", NAME],
        cwd="C:\\",
    )
    async with AsyncExitStack() as stack:
        read, write = await stack.enter_async_context(stdio_client(parameters))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        print("before stop:", await call(session, "query_capabilities"), flush=True)
        run("docker", "exec", "-u", "cua", "fcb-desktop", "fcb-freecad", "stop")
        stopped = time.monotonic()
        print("immediately after stop:",
              await asyncio.wait_for(call(session, "query_capabilities"), 60), flush=True)
        print(f"answered {time.monotonic() - stopped:.1f}s after stop", flush=True)
        start_freecad()
        print("after FreeCAD restart:", await call(session, "query_capabilities"), flush=True)


asyncio.run(main())
print("DONE")
