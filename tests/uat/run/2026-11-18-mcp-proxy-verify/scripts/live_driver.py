"""Live verifier: drive both proxies exactly as .mcp.json starts them, across container lifecycle.

    uv run --no-sync --project <repo> python live_driver.py <repo> <outdir>
"""

from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes as wt
import json
import subprocess
import sys
import time
import urllib.request
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
LOG = open(OUT / "live.log", "a", encoding="utf-8")
T0 = time.monotonic()
CALLS = {"freecad-buddy-docker": ("query_capabilities", {}), "cua-driver-docker": ("list_windows", {})}


def log(text: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} +{time.monotonic() - T0:7.1f}s {text}"
    print(line, flush=True)
    LOG.write(line + "\n")
    LOG.flush()


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def process_table() -> list[tuple[int, int, str]]:
    kernel = ctypes.windll.kernel32
    snapshot = kernel.CreateToolhelp32Snapshot(0x2, 0)
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    rows = []
    ok = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
    while ok:
        rows.append((entry.th32ProcessID, entry.th32ParentProcessID, entry.szExeFile))
        ok = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    kernel.CloseHandle(snapshot)
    return rows


def descendants(root_pids: set[int], table) -> list[tuple[int, int, str]]:
    found, frontier = [], set(root_pids)
    while frontier:
        children = [row for row in table if row[1] in frontier and row[0] not in root_pids]
        frontier = {row[0] for row in children} - {row[0] for row in found}
        found.extend(row for row in children if row[0] in frontier)
    return found


def sh(command: str, timeout: float = 1800) -> str:
    log(f"$ {command}")
    completed = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=REPO)
    tail = (completed.stdout + completed.stderr).strip().splitlines()[-4:]
    log(f"  exit={completed.returncode} {' | '.join(tail)[:400]}")
    return completed.stdout


def healthz() -> dict | None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:18765/healthz", timeout=3) as response:
            return json.loads(response.read())
    except Exception:
        return None


class Client:
    def __init__(self, server: str) -> None:
        self.server = server
        self.notifications: list[str] = []
        self.stack = AsyncExitStack()
        self.session: ClientSession | None = None
        self.stderr = open(OUT / f"proxy-{server}-{int(time.time())}.stderr.log", "w", encoding="utf-8")

    async def start(self) -> None:
        config = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"][self.server]
        parameters = StdioServerParameters(command=config["command"], args=config["args"], cwd="C:\\")
        started = time.monotonic()

        async def on_message(message) -> None:
            if isinstance(message, types.ServerNotification):
                self.notifications.append(type(message.root).__name__)
                log(f"[{self.server}] WIRE notification {message.root.method}")

        streams = await self.stack.enter_async_context(stdio_client(parameters, errlog=self.stderr))
        self.session = await self.stack.enter_async_context(
            ClientSession(streams[0], streams[1], message_handler=on_message)
        )
        await self.session.initialize()
        initialized = time.monotonic() - started
        tools = await self.session.list_tools()
        log(f"[{self.server}] initialize {initialized:.2f}s, tools/list {time.monotonic() - started:.2f}s -> {len(tools.tools)} tools")

    async def tools(self) -> int:
        return len((await self.session.list_tools()).tools)

    async def call(self, label: str, timeout: float = 120) -> None:
        name, arguments = CALLS[self.server]
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(self.session.call_tool(name, arguments), timeout)
        except TimeoutError:
            log(f"[{self.server}] {label}: {name} NO ANSWER after {timeout}s (HANG)")
            return
        text = result.content[0].text.replace("\n", " | ") if result.content else ""
        log(
            f"[{self.server}] {label}: {name} {time.monotonic() - started:.1f}s isError={result.isError} "
            f"structured={'yes' if result.structuredContent else 'no'} text={text[:300]}"
        )

    async def close(self) -> None:
        await self.stack.aclose()


async def watch_spawns(clients: list[Client], seconds: float) -> None:
    """C3 live: sample the process tree under this driver every 50 ms; list every docker.exe seen."""
    me = {__import__("os").getpid()}
    seen: dict[int, str] = {}
    end = time.monotonic() + seconds
    samples = 0
    while time.monotonic() < end:
        for pid, parent, exe in descendants(me, process_table()):
            if exe.lower().startswith("docker") and pid not in seen:
                seen[pid] = f"{exe} parent={parent}"
        samples += 1
        await asyncio.sleep(0.05)
    tree = [f"{exe}:{pid}" for pid, _, exe in descendants(me, process_table())]
    log(f"C3 live: {seconds:.0f}s container down, {samples} samples, docker processes spawned under proxies: {len(seen)} {seen}")
    log(f"C3 live: process tree under driver now: {tree}")


async def wait_health(limit: float = 300) -> bool:
    end = time.monotonic() + limit
    while time.monotonic() < end:
        body = healthz()
        if body and isinstance(body.get("freecad_pid"), int):
            log(f"healthz ready: {body.get('service')} freecad_pid={body.get('freecad_pid')}")
            return True
        await asyncio.sleep(2)
    log("healthz NOT ready")
    return False


async def start_freecad() -> None:
    for attempt in range(1, 31):
        out = sh("docker exec -u cua fcb-desktop fcb-session-env", timeout=60) if False else ""
        result = subprocess.run(
            "docker exec -u cua fcb-desktop fcb-freecad start", shell=True, capture_output=True, text=True, timeout=180
        )
        log(f"fcb-freecad start attempt {attempt}: exit={result.returncode} {(result.stdout + result.stderr).strip()[-200:]!r}")
        if result.returncode == 0 and await wait_health(120):
            return
        await asyncio.sleep(5)


async def main() -> None:
    phase = sys.argv[3] if len(sys.argv) > 3 else "all"
    log(f"=== live driver phase={phase}")
    if phase in ("all", "lifecycle"):
        clients = [Client("freecad-buddy-docker"), Client("cua-driver-docker")]
        for client in clients:
            await client.start()
        for client in clients:
            await client.call("P1 container down")
        await watch_spawns(clients, 120)
        log(f"stderr of proxies during down period: see proxy-*.stderr.log")
        sh("uv run python scripts/build_addon.py --release")
        sh("docker compose -f tests/close-loop/docker/compose.yaml up -d --build")
        immediate = subprocess.run(
            "docker exec -u cua fcb-desktop fcb-freecad start", shell=True, capture_output=True, text=True, timeout=180
        )
        log(f"fcb-freecad start right after compose up: exit={immediate.returncode} {(immediate.stdout + immediate.stderr).strip()[-300:]!r}")
        if not await wait_health(60):
            await start_freecad()
        for client in clients:
            await client.call("P2 container up, same proxy")
        # D1 live: stop FreeCAD and call within the 5 s liveness window.
        await clients[0].call("P3a warm call before stop")
        sh("docker exec -u cua fcb-desktop fcb-freecad stop", timeout=120)
        await clients[0].call("P3b call right after fcb-freecad stop", timeout=90)
        await asyncio.sleep(7)
        await clients[0].call("P3c call after >5s idle with FreeCAD stopped", timeout=90)
        await start_freecad()
        for client in clients:
            await client.call("P3d after FreeCAD restart, same proxy")
        for client in clients:
            log(f"[{client.server}] notifications seen: {client.notifications}")
            await client.close()
    if phase in ("all", "fresh"):
        for name in ("freecad-buddy-docker", "cua-driver-docker"):
            (REPO / ".cache" / "mcp-proxy" / f"{name}.json").unlink(missing_ok=True)
        log("cache files deleted")
        clients = [Client("freecad-buddy-docker"), Client("cua-driver-docker")]
        for client in clients:
            await client.start()
        end = time.monotonic() + 120
        while time.monotonic() < end and not all(c.notifications for c in clients):
            await asyncio.sleep(1)
        for client in clients:
            log(f"[{client.server}] fresh: notifications={client.notifications} tools now={await client.tools()}")
            await client.call("P4 fresh cache")
            await client.close()
    log("=== done")


asyncio.run(main())
