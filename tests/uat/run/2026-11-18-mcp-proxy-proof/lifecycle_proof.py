"""One proxy process per server, kept running while the container goes down, up, and restarts.

Phase 1: container down, cache present. Phase 2: container and FreeCAD started, same processes.
Phase 3: container restarted (FreeCAD restarted), same processes: reconnect after a lost session.
"""

import asyncio
from contextlib import AsyncExitStack
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parents[4]
COMPOSE = ["docker", "compose", "-f", str(REPO / "tests/close-loop/docker/compose.yaml")]
CALLS = {"freecad-buddy-docker": "query_capabilities", "cua-driver-docker": "list_windows"}


def run(*command: str) -> None:
    subprocess.run(command, check=True, capture_output=True, cwd=REPO)


def start_freecad() -> None:
    """Start FreeCAD once the desktop session exists (`fcb-session-env` fails before that)."""
    deadline = time.monotonic() + 180
    while subprocess.run(
        ["docker", "exec", "-u", "cua", "fcb-desktop", "fcb-session-env"], capture_output=True
    ).returncode:
        if time.monotonic() > deadline:
            raise RuntimeError("desktop session did not start")
        time.sleep(3)
    subprocess.run(
        ["docker", "exec", "-u", "cua", "fcb-desktop", "fcb-freecad", "start"], capture_output=True
    )
    wait_for_freecad()


def wait_for_freecad() -> None:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            body = json.load(urllib.request.urlopen("http://127.0.0.1:18765/healthz", timeout=2))
            if isinstance(body.get("freecad_pid"), int):
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("FreeCAD did not report freecad_pid")


async def call(session: ClientSession, tool: str) -> str:
    started = time.monotonic()
    result = await session.send_request(
        types.ClientRequest(
            types.CallToolRequest(params=types.CallToolRequestParams(name=tool, arguments={}))
        ),
        types.CallToolResult,
    )
    text = result.content[0].text[:160].replace("\n", " | ")
    return (
        f"{tool}: {time.monotonic() - started:.1f}s isError={result.isError} "
        f"structuredContent={'yes' if result.structuredContent else 'no'} text={text}"
    )


async def main() -> None:
    sessions: dict[str, ClientSession] = {}

    async with AsyncExitStack() as stack:
        run(*COMPOSE, "stop")
        for name in CALLS:
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
                    name,
                ],
                cwd="C:\\",
            )
            read, write = await stack.enter_async_context(stdio_client(parameters))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            sessions[name] = session
        print("PHASE 1: container down")
        for name, session in sessions.items():
            tools = await session.list_tools()
            print(f"  {name}: tools/list -> {len(tools.tools)} cached tools")
            print("  " + await call(session, CALLS[name]))
        print("PHASE 2: start container and FreeCAD, same proxy processes")
        run(*COMPOSE, "up", "-d")
        start_freecad()
        for name, session in sessions.items():
            print("  " + name + " " + await call(session, CALLS[name]))
        print("PHASE 3: restart container and FreeCAD, same proxy processes")
        run(*COMPOSE, "restart")
        start_freecad()
        for name, session in sessions.items():
            print("  " + name + " " + await call(session, CALLS[name]))


if __name__ == "__main__":
    asyncio.run(main())
    print("DONE")
