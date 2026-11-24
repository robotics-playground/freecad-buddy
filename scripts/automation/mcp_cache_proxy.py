"""Stdio MCP proxy that keeps a container-backed MCP server visible while the container is down.

Claude Code connects an MCP server once at start and never retries a failed stdio server. The
container servers (`freecad-buddy-docker`, `cua-driver-docker`) are down at that moment whenever
the `fcb-desktop` container is stopped. This proxy always starts, answers `tools/list` from a local
cache file, and forwards `tools/call` to the real upstream when it is reachable.

    uv run --no-sync --project <repo> python scripts/automation/mcp_cache_proxy.py --server <name>

stdout is the MCP protocol channel: everything else goes to stderr.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import socket
import sys
import time
import urllib.request
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.session import ServerSession
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import McpError

LOGGER = logging.getLogger("mcp_cache_proxy")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = REPO_ROOT / ".cache" / "mcp-proxy"

CONNECT_TIMEOUT_SECONDS = 20.0
# A session idle longer than this is pinged before a call, so a dead transport is found while the
# request has not been sent yet and the call can still be retried safely.
LIVENESS_IDLE_SECONDS = 5.0
LIVENESS_PING_TIMEOUT_SECONDS = 3.0
# While the upstream is down a poll is one TCP connect or one local HTTP GET, so a short fixed delay
# is cheap.
PORT_CLOSED_POLL_SECONDS = 5.0
# While a call runs, the upstream is probed this often. The SDK ends a streamable-HTTP call with no
# answer when the upstream dies, so this probe is the only end of such a call; a call that runs long
# but whose upstream stays up is never cut.
IN_FLIGHT_PROBE_SECONDS = 2.0
IN_FLIGHT_PROBE_FAILURES = 2
CONNECT_RETRY_DELAYS_SECONDS = (5.0, 10.0, 20.0, 30.0)
CONNECTED_POLL_SECONDS = 60.0
SESSION_TERMINATED_CODE = 32600
CACHE_REPLACE_ATTEMPTS = 10

START_COMMANDS = (
    "1. docker compose -f tests/close-loop/docker/compose.yaml up -d --build\n"
    "2. docker exec -u cua fcb-desktop fcb-freecad start\n"
    "3. wait until http://127.0.0.1:18765/healthz shows a number in freecad_pid"
)


class UpstreamUnavailable(Exception):
    """No session to the upstream exists, and nothing of the request was sent."""


class UpstreamPortClosed(UpstreamUnavailable):
    """The upstream probe fails, so the container or the server in it is down."""


class _NotDelivered(Exception):
    """The upstream answered that the session is gone, so it never processed the request."""


class _ConnectionEnded(Exception):
    """The upstream connection ended before the answer to a sent request arrived."""


class OutcomeUnknown(Exception):
    """The connection failed after the request was sent, so the tool may have run."""


@dataclass(frozen=True)
class UpstreamSpec:
    """`probe` returns an identity string while the upstream is up and None while it is down. A
    changed identity means the upstream restarted, so a session opened before is dead."""

    name: str
    probe: Callable[[], str | None] | None
    open_transport: Callable[[], AbstractAsyncContextManager[Any]]


def _port_is_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def port_probe(port: int) -> Callable[[], str | None]:
    return lambda: "open" if _port_is_open(port) else None


def healthz_probe(port: int) -> Callable[[], str | None]:
    """The container publishes the port while FreeCAD is down, so only /healthz tells that the
    FreeCAD proxy runs; its session id changes when FreeCAD restarts."""

    def probe() -> str | None:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1.0) as reply:
                body = json.load(reply)
        except (OSError, ValueError):
            return None
        if isinstance(body, dict) and isinstance(body.get("freecad_pid"), int):
            return str(body.get("session_id"))
        return None

    return probe


def _docker_cua_transport() -> AbstractAsyncContextManager[Any]:
    parameters = StdioServerParameters(
        command="docker",
        args=["exec", "-i", "-u", "cua", "fcb-desktop", "fcb-cua-mcp"],
    )
    return stdio_client(parameters)


UPSTREAMS: dict[str, UpstreamSpec] = {
    "freecad-buddy-docker": UpstreamSpec(
        name="freecad-buddy-docker",
        probe=healthz_probe(18765),
        open_transport=lambda: streamable_http_client("http://127.0.0.1:18765/mcp"),
    ),
    "cua-driver-docker": UpstreamSpec(
        name="cua-driver-docker",
        probe=port_probe(6901),
        open_transport=_docker_cua_transport,
    ),
}


def _describe(error: BaseException) -> str:
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    return f"{type(error).__name__}: {error}"


def _is_session_terminated(error: McpError) -> bool:
    return error.error.code == SESSION_TERMINATED_CODE and "Session terminated" in str(error)


@dataclass
class _Connection:
    session: ClientSession
    owner: asyncio.Task[None]
    stop: asyncio.Event
    identity: str | None
    in_flight: int = 0
    retired: bool = False


class Upstream:
    """One persistent MCP client session to the real server, reconnected on demand.

    The session lives in a task of its own because the transports use anyio task groups, which must
    be entered and exited by the same task. The cua-driver process keeps element tokens in memory
    per connection, so the session must outlive a single call. A replaced connection is closed only
    after its in-flight calls finish: closing it earlier leaves a parallel call without an answer.
    """

    def __init__(
        self, spec: UpstreamSpec, connect_timeout: float = CONNECT_TIMEOUT_SECONDS
    ) -> None:
        self._spec = spec
        self._connect_timeout = connect_timeout
        self._lock = asyncio.Lock()
        self._current: _Connection | None = None
        self._last_used = 0.0
        self.instructions: str | None = None

    async def _own(self, ready: asyncio.Future[ClientSession], stop: asyncio.Event) -> None:
        try:
            async with self._spec.open_transport() as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    initialized = await session.initialize()
                    self.instructions = initialized.instructions or None
                    ready.set_result(session)
                    await stop.wait()
        except asyncio.CancelledError:
            if not ready.done():
                ready.cancel()
            raise
        except Exception as error:
            if not ready.done():
                ready.set_exception(error)

    async def _ensure(self) -> _Connection:
        async with self._lock:
            if self._current is not None:
                return self._current
            identity = await self._probe()
            if self._spec.probe is not None and identity is None:
                raise UpstreamPortClosed(
                    "the upstream does not answer its probe "
                    "(the container or the server in it is not running)"
                )
            ready: asyncio.Future[ClientSession] = asyncio.get_running_loop().create_future()
            stop = asyncio.Event()
            owner = asyncio.create_task(self._own(ready, stop))
            try:
                session = await asyncio.wait_for(ready, self._connect_timeout)
            except (Exception, asyncio.CancelledError) as error:
                stop.set()
                owner.cancel()
                await asyncio.gather(owner, return_exceptions=True)
                if isinstance(error, asyncio.CancelledError):
                    raise
                raise UpstreamUnavailable(_describe(error)) from error
            self._current = _Connection(session, owner, stop, identity)
            self._last_used = time.monotonic()
            return self._current

    async def _probe(self) -> str | None:
        if self._spec.probe is None:
            return None
        return await asyncio.to_thread(self._spec.probe)

    async def _watch(self, connection: _Connection) -> None:
        """Return when the upstream of a running call is gone: owner task ended, or probe failed."""
        failures = 0
        while not connection.owner.done():
            await asyncio.wait({connection.owner}, timeout=IN_FLIGHT_PROBE_SECONDS)
            if self._spec.probe is None:
                continue
            same = await self._probe() == connection.identity
            failures = 0 if same else failures + 1
            if failures >= IN_FLIGHT_PROBE_FAILURES:
                return

    async def _retire(self, connection: _Connection) -> None:
        async with self._lock:
            if self._current is connection:
                self._current = None
            connection.retired = True
        if connection.in_flight == 0:
            await self._close(connection)

    async def _close(self, connection: _Connection) -> None:
        connection.stop.set()
        try:
            await asyncio.wait_for(connection.owner, 5.0)
        except Exception:
            LOGGER.debug("upstream owner task ended with an error", exc_info=True)

    async def _is_alive(self, connection: _Connection) -> bool:
        try:
            await asyncio.wait_for(connection.session.send_ping(), LIVENESS_PING_TIMEOUT_SECONDS)
        except McpError as error:
            return not _is_session_terminated(error)
        except Exception:
            return False
        return True

    async def list_tools(self) -> list[dict[str, Any]]:
        connection = await self._ensure()
        tools: list[types.Tool] = []
        try:
            cursor: str | None = None
            while True:
                page = await connection.session.list_tools(cursor)
                tools.extend(page.tools)
                cursor = page.nextCursor
                if cursor is None:
                    break
        except Exception as error:
            await self._retire(connection)
            raise UpstreamUnavailable(_describe(error)) from error
        self._last_used = time.monotonic()
        return [tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in tools]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None) -> types.CallToolResult:
        """Forward one call. Retries once only when the request provably was not delivered."""
        connection = await self._ensure()
        if self._spec.probe is not None and await self._probe() != connection.identity:
            await self._retire(connection)
            connection = await self._ensure()
        elif time.monotonic() - self._last_used > LIVENESS_IDLE_SECONDS:
            if not await self._is_alive(connection):
                await self._retire(connection)
                connection = await self._ensure()
        try:
            return await self._send(connection, name, arguments)
        except _NotDelivered:
            await self._retire(connection)
        connection = await self._ensure()
        try:
            return await self._send(connection, name, arguments)
        except _NotDelivered as error:
            await self._retire(connection)
            raise UpstreamUnavailable(f"session lost twice: {error}") from error

    async def _send(
        self, connection: _Connection, name: str, arguments: dict[str, Any] | None
    ) -> types.CallToolResult:
        # `send_request` skips the client's own output-schema validation, so the upstream result
        # reaches Claude Code exactly as the upstream built it.
        request = types.ClientRequest(
            types.CallToolRequest(
                params=types.CallToolRequestParams(name=name, arguments=arguments)
            )
        )
        connection.in_flight += 1
        try:
            result = await self._answer_or_connection_end(connection, request)
        except _ConnectionEnded as error:
            await self._retire(connection)
            raise OutcomeUnknown(str(error)) from error
        except McpError as error:
            if _is_session_terminated(error):
                raise _NotDelivered(str(error)) from error
            if error.error.code == types.CONNECTION_CLOSED:
                await self._retire(connection)
                raise OutcomeUnknown(str(error)) from error
            return _error_result(f"upstream rejected the call: {error}")
        except Exception as error:
            await self._retire(connection)
            raise OutcomeUnknown(_describe(error)) from error
        finally:
            connection.in_flight -= 1
            if connection.retired and connection.in_flight == 0:
                await self._close(connection)
        self._last_used = time.monotonic()
        return result

    async def _answer_or_connection_end(
        self, connection: _Connection, request: types.ClientRequest
    ) -> types.CallToolResult:
        request_task = asyncio.ensure_future(
            connection.session.send_request(request, types.CallToolResult)
        )
        watcher = asyncio.ensure_future(self._watch(connection))
        try:
            await asyncio.wait({request_task, watcher}, return_when=asyncio.FIRST_COMPLETED)
            if not request_task.done():
                raise _ConnectionEnded("the upstream connection ended while the call was running")
            return request_task.result()
        finally:
            for task in (request_task, watcher):
                task.cancel()
            await asyncio.gather(request_task, watcher, return_exceptions=True)

    async def close(self) -> None:
        connection = self._current
        if connection is not None:
            await self._retire(connection)


def _error_result(text: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], isError=True)


def _unavailable_text(server_name: str, cause: str) -> str:
    return (
        f"{server_name} is not reachable: {cause}. The request was not sent. "
        f"Start the container, then call again (no Claude Code restart needed):\n{START_COMMANDS}"
    )


def _unknown_outcome_text(server_name: str, cause: str) -> str:
    return (
        f"{server_name} lost the connection after the request was sent ({cause}). "
        "The tool may or may not have run, so the proxy did not send it again. Check the state "
        "first (a query tool for freecad-buddy, a fresh get_window_state for cua-driver), then "
        "decide whether to repeat the call."
    )


class CacheProxy:
    """The MCP server Claude Code talks to: tools/list from cache, tools/call to the upstream."""

    def __init__(self, upstream: Upstream, server_name: str, cache_path: Path) -> None:
        self._upstream = upstream
        self._server_name = server_name
        self._cache_path = cache_path
        self._tools = self._read_cache()
        # The initialize result is sent once per client session, before any upstream connection
        # exists while the container is down, so the upstream text is read back from the last run.
        self._instructions_path = cache_path.with_name(f"{cache_path.stem}.instructions.txt")
        self._client_session: ServerSession | None = None
        self.server: Server[Any] = Server(
            f"{server_name}-cache-proxy", instructions=self._read_instructions()
        )
        self.server.list_tools()(self._handle_list_tools)
        self.server.request_handlers[types.CallToolRequest] = self._handle_call_tool

    def initialization_options(self):
        return self.server.create_initialization_options(NotificationOptions(tools_changed=True))

    def _read_cache(self) -> list[dict[str, Any]]:
        try:
            tools = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if not isinstance(tools, list):
                raise TypeError("cache root is not a list")
            for tool in tools:
                types.Tool.model_validate(tool)
        except FileNotFoundError:
            return []
        except (OSError, ValueError, TypeError):
            LOGGER.warning("ignoring cache %s: not a tool list", self._cache_path)
            return []
        return tools

    def _read_instructions(self) -> str | None:
        try:
            # Bytes, so a line ending in the upstream text comes back unchanged.
            return self._instructions_path.read_bytes().decode("utf-8") or None
        except (OSError, ValueError):
            return None

    def _write_cache(self, tools: list[dict[str, Any]]) -> None:
        self._replace_file(self._cache_path, json.dumps(tools, indent=2))

    @staticmethod
    def _replace_file(path: Path, text: str, newline: str | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(text, encoding="utf-8", newline=newline)
        # Windows refuses a replace while another process replaces or reads the same target.
        for attempt in range(CACHE_REPLACE_ATTEMPTS):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == CACHE_REPLACE_ATTEMPTS - 1:
                    temporary.unlink(missing_ok=True)
                    raise
                time.sleep(0.02 * (attempt + 1))

    async def _handle_list_tools(self) -> list[types.Tool]:
        self._client_session = self.server.request_context.session
        return [types.Tool.model_validate(tool) for tool in self._tools]

    async def _handle_call_tool(self, request: types.CallToolRequest) -> types.ServerResult:
        self._client_session = self.server.request_context.session
        params = request.params
        try:
            result = await self._upstream.call_tool(params.name, params.arguments)
        except UpstreamUnavailable as error:
            result = _error_result(_unavailable_text(self._server_name, str(error)))
        except OutcomeUnknown as error:
            result = _error_result(_unknown_outcome_text(self._server_name, str(error)))
        return types.ServerResult(result)

    def _cache_instructions(self) -> None:
        instructions = self._upstream.instructions
        if instructions == self._read_instructions():
            return
        try:
            if instructions is None:
                self._instructions_path.unlink(missing_ok=True)
            else:
                self._replace_file(self._instructions_path, instructions, newline="")
        except OSError:
            # The tool list is the relay's main job; a failed text write must not block it.
            LOGGER.warning("could not update %s", self._instructions_path, exc_info=True)

    async def refresh_once(self) -> None:
        tools = await self._upstream.list_tools()
        # The replace retries with time.sleep; a thread keeps the event loop free for tool calls.
        await asyncio.to_thread(self._cache_instructions)
        if tools == self._tools:
            return
        self._write_cache(tools)
        self._tools = tools
        LOGGER.info("tool list changed: %d tools, sending tools/list_changed", len(tools))
        if self._client_session is not None:
            try:
                await self._client_session.send_tool_list_changed()
            except Exception:
                LOGGER.warning("could not send tools/list_changed", exc_info=True)

    async def refresh_loop(
        self,
        port_closed_delay: float = PORT_CLOSED_POLL_SECONDS,
        retry_delays: tuple[float, ...] = CONNECT_RETRY_DELAYS_SECONDS,
        connected_delay: float = CONNECTED_POLL_SECONDS,
    ) -> None:
        failures = 0
        while True:
            try:
                await self.refresh_once()
            except UpstreamPortClosed:
                failures = 0
                delay = port_closed_delay
            except Exception as error:
                # The loop is the only way a cache gets filled, so no error may end it.
                if isinstance(error, UpstreamUnavailable):
                    LOGGER.info("upstream not ready: %s", error)
                else:
                    LOGGER.exception("refresh cycle failed")
                delay = retry_delays[min(failures, len(retry_delays) - 1)]
                failures += 1
            else:
                failures = 0
                delay = connected_delay
            await asyncio.sleep(delay)


async def serve(server_name: str, cache_dir: Path) -> None:
    upstream = Upstream(UPSTREAMS[server_name])
    proxy = CacheProxy(upstream, server_name, cache_dir / f"{server_name}.json")
    refresher = asyncio.ensure_future(proxy.refresh_loop())
    try:
        async with stdio_server() as (read_stream, write_stream):
            await proxy.server.run(read_stream, write_stream, proxy.initialization_options())
    finally:
        refresher.cancel()
        await asyncio.gather(refresher, return_exceptions=True)
        await upstream.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--server", required=True, choices=sorted(UPSTREAMS))
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.WARNING)
    asyncio.run(serve(arguments.server, arguments.cache_dir))


if __name__ == "__main__":
    main()
