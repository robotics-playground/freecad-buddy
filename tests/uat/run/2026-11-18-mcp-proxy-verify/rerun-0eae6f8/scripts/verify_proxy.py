"""Independent verifier probes for scripts/automation/mcp_cache_proxy.py (unmodified source).

    uv run --no-sync --project <repo> python verify_proxy.py <repo> <outdir> [probe ...]
"""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
SELECTED = set(sys.argv[3:])
HERE = Path(__file__).resolve().parent
FAKE = HERE / "fake_counting_upstream.py"
sys.path.insert(0, str(REPO / "scripts" / "automation"))

import mcp_cache_proxy as pm  # noqa: E402
from mcp import StdioServerParameters, types  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from mcp.client.streamable_http import streamable_http_client  # noqa: E402
from mcp.shared.memory import create_connected_server_and_client_session  # noqa: E402

LOG: list[str] = []


def log(text: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {text}"
    print(line, flush=True)
    LOG.append(line)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def counts(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def pid_alive(pid: int) -> bool:
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True
    ).stdout
    return str(pid) in out


class Http:
    def __init__(self, count_file: Path) -> None:
        self.port = free_port()
        self.count_file = count_file
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        self.process = subprocess.Popen(
            [sys.executable, str(FAKE), "--count-file", str(self.count_file), "--port", str(self.port)],
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if pm._port_is_open(self.port):
                return
            time.sleep(0.1)
        raise RuntimeError("no port")

    def stop(self) -> None:
        if self.process is not None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.process.pid)], capture_output=True)
            self.process.kill()
            self.process.wait()
            self.process = None

    def spec(self) -> pm.UpstreamSpec:
        url = f"http://127.0.0.1:{self.port}/mcp"
        return pm.UpstreamSpec("fake-http", pm.port_probe(self.port), lambda: streamable_http_client(url))


def stdio_spec(count_file: Path) -> pm.UpstreamSpec:
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(FAKE), "--count-file", str(count_file)]
    )
    return pm.UpstreamSpec("fake-stdio", None, lambda: stdio_client(parameters))


async def with_client(proxy: pm.CacheProxy, body):
    async with create_connected_server_and_client_session(proxy.server) as client:
        return await body(client)


def text(result: types.CallToolResult) -> str:
    return result.content[0].text.replace("\n", " | ")


async def timed_call(client, name, arguments, timeout):
    started = time.monotonic()
    try:
        result = await asyncio.wait_for(client.call_tool(name, arguments), timeout)
        return f"answered in {time.monotonic() - started:.1f}s isError={result.isError} text={text(result)[:160]}"
    except TimeoutError:
        return f"NO ANSWER after {timeout}s (hang)"


async def probe_crash_after_send(kind: str, delay: float, tmp: Path) -> None:
    """C1: the tool runs (count +1), then the upstream dies. Count must stay 1, answer isError."""
    count_file = tmp / f"crash-{kind}-{delay}.txt"
    http = None
    if kind == "http":
        http = Http(count_file)
        http.start()
        spec = http.spec()
    else:
        spec = stdio_spec(count_file)
    upstream = pm.Upstream(spec)
    proxy = pm.CacheProxy(upstream, "fake", tmp / f"cache-{kind}.json")

    async def body(client):
        warm = await timed_call(client, "pid", {}, 20)
        outcome = await timed_call(client, "count_crash", {"delay": delay}, 40)
        return warm, outcome

    try:
        warm, outcome = await with_client(proxy, body)
    finally:
        await asyncio.wait_for(upstream.close(), 10)
        if http:
            http.stop()
    crash_count = sum(1 for line in counts(count_file) if line.startswith("count_crash"))
    log(f"C1 crash-after-send transport={kind} delay={delay}: warm={warm}")
    log(f"C1   count_crash -> {outcome}")
    log(f"C1   count_crash executions={crash_count} (must be 1)")


async def probe_hang(kind: str, tmp: Path) -> None:
    count_file = tmp / f"hang-{kind}.txt"
    http = None
    if kind == "http":
        http = Http(count_file)
        http.start()
        spec = http.spec()
    else:
        spec = stdio_spec(count_file)
    upstream = pm.Upstream(spec)
    proxy = pm.CacheProxy(upstream, "fake", tmp / f"cache-hang-{kind}.json")

    async def body(client):
        return await timed_call(client, "count_hang", {}, 30)

    try:
        outcome = await with_client(proxy, body)
    finally:
        try:
            await asyncio.wait_for(upstream.close(), 10)
        except TimeoutError:
            log("HANG   upstream.close() did not finish in 10s")
        if http:
            http.stop()
    log(f"HANG transport={kind}: count_hang -> {outcome}")


async def probe_parallel(tmp: Path) -> None:
    """C2: parallel calls across a lost session: restart, down for good, crash mid-flight."""
    count_file = tmp / "parallel.txt"
    http = Http(count_file)
    http.start()
    pm.LIVENESS_IDLE_SECONDS = 3600.0
    upstream = pm.Upstream(http.spec())
    proxy = pm.CacheProxy(upstream, "fake", tmp / "cache-par.json")
    opened = {"n": 0}
    original = upstream._spec.open_transport

    def counting():
        opened["n"] += 1
        return original()

    upstream._spec = pm.UpstreamSpec("fake-http", pm.port_probe(http.port), counting)

    async def body(client):
        await client.call_tool("pid", {})
        http.stop()
        http.start()
        before = opened["n"]
        restart = await asyncio.gather(
            *(timed_call(client, "pid", {}, 40) for _ in range(6))
        )
        log(f"C2 restart: 6 parallel -> {restart}")
        log(f"C2 restart: transports opened during the 6 calls = {opened['n'] - before} (1 = one reconnect)")
        http.stop()
        down = await asyncio.gather(*(timed_call(client, "pid", {}, 40) for _ in range(6)))
        log(f"C2 down for good: 6 parallel -> {down}")
        http.start()
        await client.call_tool("pid", {})
        mixed = await asyncio.gather(
            timed_call(client, "count_crash", {"delay": 1.0}, 40),
            *(timed_call(client, "slow", {"seconds": 3}, 40) for _ in range(3)),
        )
        log(f"C2 crash mid-flight with 3 slow calls in flight -> {mixed}")

    try:
        await with_client(proxy, body)
    finally:
        await asyncio.wait_for(upstream.close(), 10)
        http.stop()


async def probe_retire_leak(tmp: Path) -> None:
    """_retire with a call in flight: process lives until the call ends, then is gone."""
    count_file = tmp / "retire.txt"
    upstream = pm.Upstream(stdio_spec(count_file))
    pid = (await upstream.call_tool("pid", {})).structuredContent["pid"]
    connection = upstream._current
    task = asyncio.ensure_future(upstream.call_tool("slow", {"seconds": 3}))
    await asyncio.sleep(1.0)
    await upstream._retire(connection)
    alive_during = pid_alive(pid)
    result = await asyncio.wait_for(task, 20)
    await asyncio.sleep(2.0)
    alive_after = pid_alive(pid)
    log(
        f"RETIRE stdio fake pid={pid}: in_flight call answered isError={result.isError}, "
        f"alive while in flight={alive_during} (want True), alive 2s after={alive_after} (want False), "
        f"connection.in_flight={connection.in_flight} owner.done={connection.owner.done()}"
    )
    # Hung call case: retire while a hung call is in flight.
    upstream2 = pm.Upstream(stdio_spec(count_file))
    pid2 = (await upstream2.call_tool("pid", {})).structuredContent["pid"]
    connection2 = upstream2._current
    hung = asyncio.ensure_future(upstream2.call_tool("count_hang", {}))
    await asyncio.sleep(1.0)
    await upstream2._retire(connection2)
    await asyncio.sleep(2.0)
    log(f"RETIRE hung call: fake pid={pid2} alive 2s after retire={pid_alive(pid2)}, hung call done={hung.done()}")
    hung.cancel()
    await asyncio.gather(hung, return_exceptions=True)
    await asyncio.sleep(2.0)
    log(f"RETIRE hung call after cancelling the waiter: alive={pid_alive(pid2)} in_flight={connection2.in_flight}")
    await upstream2._close(connection2)
    await asyncio.sleep(1.0)
    log(f"RETIRE hung call after explicit _close: alive={pid_alive(pid2)}")


async def probe_port_closed_loop(tmp: Path) -> None:
    """C3: refresh_loop with a closed probe port never opens a transport; also cua spec probe port."""
    opened = {"n": 0}

    def opener():
        opened["n"] += 1
        raise AssertionError("must not open")

    upstream = pm.Upstream(pm.UpstreamSpec("x", pm.port_probe(free_port()), opener))
    proxy = pm.CacheProxy(upstream, "x", tmp / "c3.json")
    loop = asyncio.ensure_future(proxy.refresh_loop(port_closed_delay=0.01))
    calls = []
    for _ in range(20):
        result = await proxy._upstream.call_tool("x", {}) if False else None
        calls.append(result)
    await asyncio.sleep(3.0)
    loop.cancel()
    await asyncio.gather(loop, return_exceptions=True)
    log(f"C3 refresh_loop 3s at 10ms poll with port closed: transports opened={opened['n']} (want 0)")
    log("C3 probes: freecad=healthz_probe(18765), cua=port_probe(6901)")


async def probe_long_call(tmp: Path) -> None:
    """A legitimate 60 s call on a healthy upstream must not be cut; count probes in flight and idle."""
    count_file = tmp / "long.txt"
    http = Http(count_file)
    http.start()
    probes = {"n": 0}
    real_probe = pm.port_probe(http.port)

    def counting_probe():
        probes["n"] += 1
        return real_probe()

    url = f"http://127.0.0.1:{http.port}/mcp"
    upstream = pm.Upstream(pm.UpstreamSpec("fake-http", counting_probe, lambda: streamable_http_client(url)))
    proxy = pm.CacheProxy(upstream, "fake", tmp / "cache-long.json")

    async def body(client):
        await client.call_tool("pid", {})
        before = probes["n"]
        outcome = await timed_call(client, "slow", {"seconds": 60}, 120)
        during = probes["n"] - before
        idle_start = probes["n"]
        await asyncio.sleep(20)
        idle = probes["n"] - idle_start
        return outcome, during, idle

    try:
        outcome, during, idle = await with_client(proxy, body)
    finally:
        await asyncio.wait_for(upstream.close(), 10)
        http.stop()
    log(f"LONG http slow 60s healthy upstream -> {outcome}")
    log(f"LONG probes during the 60s call={during} (2s period -> about 30 + 1 pre-send), probes during 20s idle={idle} (want 0)")


async def probe_cache(tmp: Path) -> None:
    for label, content in (("garbage", "{not json"), ("empty", ""), ("dict", "{}"), ("ints", "[1, 2]"), ("bad-tool", '[{"x": 1}]')):
        path = tmp / f"cache-{label}.json"
        path.write_text(content, encoding="utf-8")
        try:
            proxy = pm.CacheProxy(pm.Upstream(pm.UpstreamSpec("x", pm.port_probe(free_port()), lambda: None)), "x", path)
        except Exception as error:
            log(f"CACHE {label}: constructor CRASH {type(error).__name__}: {error}")
            continue

        async def body(client):
            try:
                return f"tools/list ok: {len((await client.list_tools()).tools)} tools"
            except Exception as error:
                return f"tools/list error: {type(error).__name__}: {str(error)[:120]}"

        log(f"CACHE {label}: constructor ok, {await with_client(proxy, body)}")


async def probe_refresh_loop_survives(tmp: Path) -> None:
    """refresh_loop must keep running when the cache write fails once (e.g. Windows file lock)."""
    count_file = tmp / "loop.txt"
    upstream = pm.Upstream(stdio_spec(count_file))
    proxy = pm.CacheProxy(upstream, "fake", tmp / "loop-cache.json")
    calls = {"n": 0}
    original = proxy._write_cache

    def failing(tools):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError(13, "simulated: file in use by another process")
        original(tools)

    proxy._write_cache = failing
    loop = asyncio.ensure_future(proxy.refresh_loop(connected_delay=0.2))
    await asyncio.sleep(8.0)
    state = "running" if not loop.done() else f"DEAD: {loop.exception()!r}"
    log(f"LOOP after one failed cache write: refresh_loop {state}; write attempts={calls['n']}; cache exists={proxy._cache_path.exists()}")
    loop.cancel()
    await asyncio.gather(loop, return_exceptions=True)
    await upstream.close()


def probe_concurrent_writers(tmp: Path) -> None:
    """Two proxy processes for the same server share one `.tmp` name: do replaces collide?"""
    path = tmp / "shared" / "freecad-buddy-docker.json"
    proxies = [
        pm.CacheProxy(pm.Upstream(pm.UpstreamSpec("x", pm.port_probe(1), lambda: None)), "x", path) for _ in range(2)
    ]
    errors: list[str] = []
    tools = [{"name": f"t{i}", "inputSchema": {"type": "object"}, "description": "d" * 2000} for i in range(50)]

    def worker(proxy):
        for _ in range(200):
            try:
                proxy._write_cache(tools)
            except Exception as error:
                errors.append(type(error).__name__)

    threads = [threading.Thread(target=worker, args=(p,)) for p in proxies]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    final_ok = json.loads(path.read_text(encoding="utf-8")) == tools
    summary = {name: errors.count(name) for name in set(errors)}
    log(f"CONCURRENT two writers x200 same cache path: errors={summary} final file valid={final_ok}")


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "tmp"
    tmp.mkdir(exist_ok=True)
    probes = {
        "crash": lambda: [
            probe_crash_after_send("stdio", 0.0, tmp),
            probe_crash_after_send("http", 0.0, tmp),
            probe_crash_after_send("http", 1.0, tmp),
        ],
        "hang": lambda: [probe_hang("stdio", tmp), probe_hang("http", tmp)],
        "parallel": lambda: [probe_parallel(tmp)],
        "retire": lambda: [probe_retire_leak(tmp)],
        "c3": lambda: [probe_port_closed_loop(tmp)],
        "cache": lambda: [probe_cache(tmp)],
        "long": lambda: [probe_long_call(tmp)],
        "loop": lambda: [probe_refresh_loop_survives(tmp)],
    }
    for name, make in probes.items():
        if SELECTED and name not in SELECTED:
            continue
        for coroutine in make():
            try:
                await coroutine
            except Exception as error:
                log(f"PROBE {name} raised {type(error).__name__}: {error}")
    if not SELECTED or "concurrent" in SELECTED:
        probe_concurrent_writers(tmp)
    (OUT / f"verify-{'-'.join(sorted(SELECTED)) or 'all'}.log").write_text("\n".join(LOG) + "\n", encoding="utf-8")


asyncio.run(main())
