"""mcp_cache_proxy against real fake MCP upstreams (stdio and streamable HTTP subprocesses)."""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from mcp import StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.memory import create_connected_server_and_client_session

REPO_ROOT = Path(__file__).resolve().parents[2]
FAKE_UPSTREAM = Path(__file__).with_name("fake_mcp_upstream.py")
sys.path.insert(0, str(REPO_ROOT / "scripts" / "automation"))

import mcp_cache_proxy as proxy_module  # noqa: E402
from mcp_cache_proxy import CacheProxy, Upstream, UpstreamSpec  # noqa: E402


# Every scenario has this bound, so a call that never answers fails the test instead of blocking.
SCENARIO_BOUND_SECONDS = 30.0
CLOSE_BOUND_SECONDS = 15.0


def _fake_arguments(tools_file: Path, marker: Path) -> list[str]:
    count_file = marker.with_name("executions.txt")
    return [
        str(FAKE_UPSTREAM),
        "--tools-file",
        str(tools_file),
        "--marker",
        str(marker),
        "--count-file",
        str(count_file),
    ]


def _executions(marker: Path) -> int:
    count_file = marker.with_name("executions.txt")
    return len(count_file.read_text(encoding="utf-8").splitlines()) if count_file.exists() else 0


@pytest.fixture(autouse=True)
def fast_in_flight_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(proxy_module, "IN_FLIGHT_PROBE_SECONDS", 0.3)


def _stdio_spec(tools_file: Path, marker: Path) -> UpstreamSpec:
    parameters = StdioServerParameters(
        command=sys.executable, args=_fake_arguments(tools_file, marker)
    )
    return UpstreamSpec("fake", None, lambda: stdio_client(parameters))


def _unreachable_spec() -> UpstreamSpec:
    parameters = StdioServerParameters(command="fcb-command-that-does-not-exist", args=[])
    return UpstreamSpec("fake", None, lambda: stdio_client(parameters))


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class HttpFake:
    def __init__(self, tools_file: Path, marker: Path) -> None:
        self.port = _free_port()
        self._arguments = [*_fake_arguments(tools_file, marker), "--port", str(self.port)]
        self._process: subprocess.Popen | None = None

    def start(self) -> None:
        self._process = subprocess.Popen([sys.executable, *self._arguments])
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if proxy_module._port_is_open(self.port):
                return
            time.sleep(0.1)
        raise RuntimeError("fake HTTP upstream did not open its port")

    def stop(self) -> None:
        if self._process is not None:
            if sys.platform == "win32":
                # The venv python.exe is a launcher; kill() would leave its child serving the port.
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self._process.pid)], capture_output=True
                )
            self._process.kill()
            self._process.wait()
            self._process = None

    def spec(self) -> UpstreamSpec:
        url = f"http://127.0.0.1:{self.port}/mcp"
        return UpstreamSpec(
            "fake", proxy_module.port_probe(self.port), lambda: streamable_http_client(url)
        )


@pytest.fixture
def tools_file(tmp_path: Path) -> Path:
    path = tmp_path / "tools.json"
    path.write_text(json.dumps(["echo", "fail", "flaky"]), encoding="utf-8")
    return path


@pytest.fixture
def marker(tmp_path: Path) -> Path:
    return tmp_path / "flaky.marker"


@pytest.fixture
def http_fake(tools_file: Path, marker: Path):
    fake = HttpFake(tools_file, marker)
    fake.start()
    yield fake
    fake.stop()


@pytest.fixture
def cache_path(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "fake.json"


@asynccontextmanager
async def _client(proxy: CacheProxy, notifications: list | None = None):
    async def collect(message) -> None:
        if notifications is not None and not isinstance(message, Exception):
            notifications.append(message)

    async with create_connected_server_and_client_session(
        proxy.server, message_handler=collect
    ) as session:
        yield session


def _names(result: types.ListToolsResult) -> list[str]:
    return [tool.name for tool in result.tools]


def _text(result: types.CallToolResult) -> str:
    return result.content[0].text


def _tool_list_changed_count(notifications: list) -> int:
    return sum(
        isinstance(message, types.ServerNotification)
        and isinstance(message.root, types.ToolListChangedNotification)
        for message in notifications
    )


def _run(scenario):
    return asyncio.run(asyncio.wait_for(scenario(), SCENARIO_BOUND_SECONDS))


def _run_and_close(target: CacheProxy, scenario):
    async def wrapped():
        try:
            return await asyncio.wait_for(scenario(), SCENARIO_BOUND_SECONDS)
        finally:
            await asyncio.wait_for(target._upstream.close(), CLOSE_BOUND_SECONDS)

    return asyncio.run(wrapped())


def test_should_serve_cached_tools_when_upstream_is_down(cache_path: Path) -> None:
    # Arrange
    cache_path.parent.mkdir(parents=True)
    cached = [{"name": "cached_tool", "inputSchema": {"type": "object"}}]
    cache_path.write_text(json.dumps(cached), encoding="utf-8")
    target = CacheProxy(Upstream(_unreachable_spec(), 5), "fake", cache_path)

    async def act() -> list[str]:
        async with _client(target) as client:
            return _names(await client.list_tools())

    # Act
    names = _run(act)

    # Assert
    assert names == ["cached_tool"]


def test_should_serve_empty_list_and_declare_list_changed_when_cache_is_missing(
    cache_path: Path,
) -> None:
    # Arrange
    target = CacheProxy(Upstream(_unreachable_spec(), 5), "fake", cache_path)

    async def act() -> list[str]:
        async with _client(target) as client:
            return _names(await client.list_tools())

    # Act
    names = _run(act)

    # Assert
    assert names == []
    assert target.initialization_options().capabilities.tools.listChanged is True


def test_should_return_error_with_start_commands_when_upstream_is_down_at_call_time(
    cache_path: Path,
) -> None:
    # Arrange
    target = CacheProxy(Upstream(_unreachable_spec(), 5), "fake", cache_path)

    async def act() -> types.CallToolResult:
        async with _client(target) as client:
            return await client.call_tool("echo", {})

    # Act
    result = _run(act)

    # Assert
    assert result.isError is True
    text = _text(result)
    assert "docker compose -f tests/close-loop/docker/compose.yaml up -d --build" in text
    assert "docker exec -u cua fcb-desktop fcb-freecad start" in text
    assert "freecad_pid" in text


def test_should_pass_structured_content_and_is_error_through_when_upstream_answers(
    tools_file: Path, marker: Path, cache_path: Path
) -> None:
    # Arrange
    target = CacheProxy(Upstream(_stdio_spec(tools_file, marker)), "fake", cache_path)

    async def act() -> tuple[types.CallToolResult, types.CallToolResult]:
        async with _client(target) as client:
            ok = await client.call_tool("echo", {"value": 7})
            failed = await client.call_tool("fail", {})
            return ok, failed

    # Act
    ok, failed = _run_and_close(target, act)

    # Assert
    assert ok.structuredContent == {"tool": "echo", "arguments": {"value": 7}}
    assert _text(ok) == "human text"
    assert not ok.isError
    assert failed.isError is True
    assert failed.structuredContent == {"error": "boom"}


def test_should_rewrite_cache_and_send_list_changed_when_upstream_list_changes(
    tools_file: Path, marker: Path, cache_path: Path
) -> None:
    # Arrange
    notifications: list = []
    target = CacheProxy(Upstream(_stdio_spec(tools_file, marker)), "fake", cache_path)

    async def act() -> tuple[list[str], list[str]]:
        async with _client(target, notifications) as client:
            await client.list_tools()
            await target.refresh_once()
            await target.refresh_once()
            first = _names(await client.list_tools())
            tools_file.write_text(json.dumps(["echo", "added"]), encoding="utf-8")
            await target.refresh_once()
            await asyncio.sleep(0.2)
            return first, _names(await client.list_tools())

    # Act
    first, second = _run_and_close(target, act)

    # Assert
    assert first == ["echo", "fail", "flaky"]
    assert second == ["echo", "added"]
    cached_names = [tool["name"] for tool in json.loads(cache_path.read_text(encoding="utf-8"))]
    assert cached_names == ["echo", "added"]
    assert _tool_list_changed_count(notifications) == 2


@pytest.mark.parametrize(
    "idle_seconds", [3600.0, 0.0], ids=["session-terminated-reply", "liveness-ping"]
)
def test_should_reconnect_and_answer_when_http_session_is_lost(
    http_fake: HttpFake,
    cache_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    idle_seconds: float,
) -> None:
    # Arrange
    monkeypatch.setattr(proxy_module, "LIVENESS_IDLE_SECONDS", idle_seconds)
    target = CacheProxy(Upstream(http_fake.spec()), "fake", cache_path)

    async def act() -> types.CallToolResult:
        async with _client(target) as client:
            await client.call_tool("echo", {})
            http_fake.stop()
            http_fake.start()
            return await client.call_tool("echo", {"after": "restart"})

    # Act
    result = _run_and_close(target, act)

    # Assert
    assert not result.isError
    assert result.structuredContent == {"tool": "echo", "arguments": {"after": "restart"}}


def test_should_answer_both_calls_when_two_parallel_calls_meet_a_lost_session(
    http_fake: HttpFake, cache_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(proxy_module, "LIVENESS_IDLE_SECONDS", 3600.0)
    target = CacheProxy(Upstream(http_fake.spec()), "fake", cache_path)

    async def act() -> list[types.CallToolResult]:
        async with _client(target) as client:
            await client.call_tool("echo", {})
            http_fake.stop()
            http_fake.start()
            return await asyncio.gather(
                client.call_tool("echo", {"n": 1}), client.call_tool("echo", {"n": 2})
            )

    # Act
    results = _run_and_close(target, act)

    # Assert
    assert [result.isError for result in results] == [False, False]
    assert sorted(result.structuredContent["arguments"]["n"] for result in results) == [1, 2]


def test_should_report_unknown_outcome_and_not_resend_when_stream_breaks_after_send(
    tools_file: Path, marker: Path, cache_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(proxy_module, "LIVENESS_IDLE_SECONDS", 3600.0)
    target = CacheProxy(Upstream(_stdio_spec(tools_file, marker)), "fake", cache_path)

    async def act() -> tuple[types.CallToolResult, types.CallToolResult]:
        async with _client(target) as client:
            await client.call_tool("echo", {})
            crashed = await client.call_tool("flaky", {})
            recovered = await client.call_tool("flaky", {})
            return crashed, recovered

    # Act
    crashed, recovered = _run_and_close(target, act)

    # Assert
    assert crashed.isError is True
    assert "may or may not have run" in _text(crashed)
    assert not recovered.isError
    assert recovered.structuredContent == {"tool": "flaky", "arguments": {}}


def test_should_not_start_a_transport_when_upstream_probe_fails() -> None:
    # Arrange
    opened: list[int] = []

    def open_transport():
        opened.append(1)
        raise AssertionError("transport must not start while the port is closed")

    target = Upstream(UpstreamSpec("fake", lambda: None, open_transport))

    async def act() -> None:
        await target.list_tools()

    # Act
    def run() -> None:
        _run(act)

    # Assert
    with pytest.raises(proxy_module.UpstreamPortClosed):
        run()
    assert opened == []


def test_should_keep_stdout_to_protocol_messages_when_proxy_starts(tmp_path: Path) -> None:
    # Arrange
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "automation" / "mcp_cache_proxy.py"),
        "--server",
        "freecad-buddy-docker",
        "--cache-dir",
        str(tmp_path),
    ]
    request = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        }
    )

    # Act
    completed = subprocess.run(
        command, input=request + "\n", capture_output=True, text=True, timeout=60
    )

    # Assert
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["result"]["capabilities"]["tools"]["listChanged"] is True


def _spec_for(transport: str, request, tools_file: Path, marker: Path) -> UpstreamSpec:
    if transport == "http":
        return request.getfixturevalue("http_fake").spec()
    return _stdio_spec(tools_file, marker)


@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_should_answer_once_with_unknown_outcome_when_upstream_dies_after_send(
    transport: str, tools_file: Path, marker: Path, cache_path: Path, request: pytest.FixtureRequest
) -> None:
    # Arrange
    spec = _spec_for(transport, request, tools_file, marker)
    target = CacheProxy(Upstream(spec), "fake", cache_path)

    async def act() -> types.CallToolResult:
        async with _client(target) as client:
            return await client.call_tool("die", {})

    # Act
    result = _run_and_close(target, act)

    # Assert
    assert result.isError is True
    assert "may or may not have run" in _text(result)
    assert _executions(marker) == 1


@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_should_answer_every_call_when_upstream_crashes_with_three_calls_in_flight(
    transport: str, tools_file: Path, marker: Path, cache_path: Path, request: pytest.FixtureRequest
) -> None:
    # Arrange
    spec = _spec_for(transport, request, tools_file, marker)
    target = CacheProxy(Upstream(spec), "fake", cache_path)

    async def act() -> list[types.CallToolResult]:
        async with _client(target) as client:
            return await asyncio.gather(*(client.call_tool("die", {}) for _ in range(3)))

    # Act
    results = _run_and_close(target, act)

    # Assert
    assert [result.isError for result in results] == [True, True, True]
    assert _executions(marker) == 3


def test_should_answer_not_reachable_when_http_port_closes_right_after_a_call(
    http_fake: HttpFake, cache_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(proxy_module, "LIVENESS_IDLE_SECONDS", 3600.0)
    target = CacheProxy(Upstream(http_fake.spec()), "fake", cache_path)

    async def act() -> types.CallToolResult:
        async with _client(target) as client:
            await client.call_tool("echo", {})
            http_fake.stop()
            return await client.call_tool("echo", {})

    # Act
    result = _run_and_close(target, act)

    # Assert
    assert result.isError is True
    assert "not reachable" in _text(result)


def test_should_open_one_transport_when_parallel_calls_meet_a_lost_session(
    http_fake: HttpFake, cache_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(proxy_module, "LIVENESS_IDLE_SECONDS", 3600.0)
    opened: list[int] = []
    real = http_fake.spec()

    def counting_open():
        opened.append(1)
        return real.open_transport()

    target = CacheProxy(Upstream(UpstreamSpec("fake", None, counting_open)), "fake", cache_path)

    async def act() -> None:
        async with _client(target) as client:
            await client.call_tool("echo", {})
            http_fake.stop()
            http_fake.start()
            await asyncio.gather(*(client.call_tool("echo", {"n": n}) for n in range(4)))

    # Act
    _run_and_close(target, act)

    # Assert
    assert len(opened) == 2


def test_should_reconnect_before_send_when_idle_stdio_upstream_died(
    tools_file: Path, marker: Path, cache_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setattr(proxy_module, "LIVENESS_IDLE_SECONDS", 0.0)
    target = CacheProxy(Upstream(_stdio_spec(tools_file, marker)), "fake", cache_path)

    async def act() -> types.CallToolResult:
        async with _client(target) as client:
            await client.call_tool("exit_soon", {})
            await asyncio.sleep(1.0)
            return await client.call_tool("echo", {"after": "death"})

    # Act
    result = _run_and_close(target, act)

    # Assert
    assert not result.isError
    assert result.structuredContent == {"tool": "echo", "arguments": {"after": "death"}}


def test_should_keep_refreshing_when_one_refresh_cycle_raises(cache_path: Path) -> None:
    # Arrange
    target = CacheProxy(Upstream(_unreachable_spec(), 5), "fake", cache_path)
    cycles: list[int] = []

    async def failing_then_counting() -> None:
        cycles.append(1)
        if len(cycles) == 1:
            raise OSError("disk full")

    target.refresh_once = failing_then_counting

    async def act() -> None:
        loop = asyncio.ensure_future(target.refresh_loop(0.01, (0.01,), 0.01))
        await asyncio.sleep(0.5)
        loop.cancel()
        await asyncio.gather(loop, return_exceptions=True)

    # Act
    _run(act)

    # Assert
    assert len(cycles) >= 3


def test_should_write_cache_without_error_when_two_writers_share_one_path(
    cache_path: Path,
) -> None:
    # Arrange
    writers = [CacheProxy(Upstream(_unreachable_spec(), 5), "fake", cache_path) for _ in range(2)]
    errors: list[Exception] = []

    def write_many(writer: CacheProxy) -> None:
        for number in range(100):
            try:
                writer._write_cache([{"name": f"tool{number}", "inputSchema": {"type": "object"}}])
            except Exception as error:
                errors.append(error)

    threads = [threading.Thread(target=write_many, args=(writer,)) for writer in writers]

    # Act
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)

    # Assert
    assert errors == []
    assert not list(cache_path.parent.glob("*.tmp"))


@pytest.mark.parametrize("content", ["[1, 2]", '[{"x": 1}]', "{}", "not json", ""])
def test_should_treat_cache_as_empty_when_file_is_not_a_tool_list(
    content: str, cache_path: Path
) -> None:
    # Arrange
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(content, encoding="utf-8")
    target = CacheProxy(Upstream(_unreachable_spec(), 5), "fake", cache_path)

    async def act() -> list[str]:
        async with _client(target) as client:
            return _names(await client.list_tools())

    # Act
    names = _run(act)

    # Assert
    assert names == []


def _refreshed_proxy(
    tools_file: Path, marker: Path, cache_path: Path, instructions: str | None
) -> CacheProxy:
    extra = [] if instructions is None else ["--instructions", instructions]
    parameters = StdioServerParameters(
        command=sys.executable, args=[*_fake_arguments(tools_file, marker), *extra]
    )
    target = CacheProxy(
        Upstream(UpstreamSpec("fake", None, lambda: stdio_client(parameters))), "fake", cache_path
    )
    _run_and_close(target, target.refresh_once)
    return target


def _next_start_instructions(cache_path: Path) -> str | None:
    return (
        CacheProxy(Upstream(_unreachable_spec(), 5), "fake", cache_path)
        .initialization_options()
        .instructions
    )


def test_Should_serve_cached_upstream_instructions_When_a_later_proxy_starts_with_the_upstream_down(
    tools_file: Path, marker: Path, cache_path: Path
) -> None:
    # Arrange
    instructions = "Use typed tools first."

    # Act
    first = _refreshed_proxy(tools_file, marker, cache_path, instructions)

    # Assert
    assert first.initialization_options().instructions is None
    assert _next_start_instructions(cache_path) == instructions


def test_Should_serve_the_new_text_When_the_upstream_instructions_change(
    tools_file: Path, marker: Path, cache_path: Path
) -> None:
    # Arrange
    _refreshed_proxy(tools_file, marker, cache_path, "old text")

    # Act
    _refreshed_proxy(tools_file, marker, cache_path, "new text")

    # Assert
    assert _next_start_instructions(cache_path) == "new text"


def test_Should_serve_no_instructions_When_the_upstream_stops_sending_them(
    tools_file: Path, marker: Path, cache_path: Path
) -> None:
    # Arrange
    _refreshed_proxy(tools_file, marker, cache_path, "old text")

    # Act
    _refreshed_proxy(tools_file, marker, cache_path, None)

    # Assert
    assert _next_start_instructions(cache_path) is None


@pytest.mark.parametrize("content", [b"", bytes([0xFF, 0xFE, 0x80])], ids=["empty", "not-utf8"])
def test_Should_serve_no_instructions_When_the_cache_file_is_unusable(
    cache_path: Path, content: bytes
) -> None:
    # Arrange
    instructions_path = cache_path.with_name("fake.instructions.txt")
    instructions_path.parent.mkdir(parents=True)
    instructions_path.write_bytes(content)

    # Act
    instructions = _next_start_instructions(cache_path)

    # Assert
    assert instructions is None


def test_Should_serve_the_text_unchanged_When_the_upstream_text_has_crlf_line_endings(
    tools_file: Path, marker: Path, cache_path: Path
) -> None:
    # Arrange
    instructions = "line one\r\nline two"

    # Act
    _refreshed_proxy(tools_file, marker, cache_path, instructions)

    # Assert
    assert _next_start_instructions(cache_path) == instructions


def test_Should_correct_the_file_When_another_relay_rewrote_it_after_this_relay_started(
    tools_file: Path, marker: Path, cache_path: Path
) -> None:
    # Arrange
    _refreshed_proxy(tools_file, marker, cache_path, "current text")
    other_relay_text = "text from another upstream version"

    class _OtherRelayWrites(CacheProxy):
        async def refresh_once(self) -> None:
            cache_path.with_name("fake.instructions.txt").write_bytes(other_relay_text.encode())
            await super().refresh_once()

    parameters = StdioServerParameters(
        command=sys.executable,
        args=[*_fake_arguments(tools_file, marker), "--instructions", "current text"],
    )
    target = _OtherRelayWrites(
        Upstream(UpstreamSpec("fake", None, lambda: stdio_client(parameters))), "fake", cache_path
    )

    # Act
    _run_and_close(target, target.refresh_once)

    # Assert
    assert _next_start_instructions(cache_path) == "current text"


def test_Should_keep_the_event_loop_responsive_When_the_instructions_path_cannot_be_replaced(
    tools_file: Path, marker: Path, cache_path: Path
) -> None:
    # Arrange
    cache_path.with_name("fake.instructions.txt").mkdir(parents=True)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[*_fake_arguments(tools_file, marker), "--instructions", "some text"],
    )
    target = CacheProxy(
        Upstream(UpstreamSpec("fake", None, lambda: stdio_client(parameters))), "fake", cache_path
    )
    longest_stall = 0.0

    async def ticker() -> None:
        nonlocal longest_stall
        previous = time.monotonic()
        while True:
            await asyncio.sleep(0.01)
            now = time.monotonic()
            longest_stall = max(longest_stall, now - previous - 0.01)
            previous = now

    async def act() -> None:
        await target.refresh_once()  # connect first, so the timed part is only the cache write
        watcher = asyncio.ensure_future(ticker())
        try:
            for _ in range(3):
                await target.refresh_once()
        finally:
            watcher.cancel()

    # Act
    _run_and_close(target, act)

    # Assert
    assert longest_stall < 0.2
    assert [tool["name"] for tool in json.loads(cache_path.read_text(encoding="utf-8"))] == [
        "echo",
        "fail",
        "flaky",
    ]
