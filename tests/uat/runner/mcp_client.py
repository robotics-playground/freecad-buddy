"""Synchronous MCP client for the GUI proxy on ``:8765``.

The MCP SDK is async and its HTTP transport must be entered and left by one task, so one
background thread owns an event loop and a single task that holds the session and serves the
calls queued from the runner's thread.
"""

import asyncio
import concurrent.futures
import threading

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ENDPOINT = "http://127.0.0.1:8765/mcp"
CONNECT_TIMEOUT_S = 30.0
# The GUI proxy gives every forwarded call a fixed 130 s read timeout; wait a little longer so a
# proxy TIMEOUT reaches the runner as an envelope, not as a client-side timeout.
CALL_TIMEOUT_S = 140.0


def to_result(call_result):
    """The value a scenario checks: ``structuredContent``, else the text blocks.

    A tool without an output schema (``query_tree_summary``) and an MCP schema refusal
    (``Input validation error: ...``) carry no ``structuredContent``; they become
    ``{"text": <joined text blocks>, "is_error": <isError>}``.
    """
    if call_result.structuredContent is not None:
        return call_result.structuredContent
    text = "".join(block.text for block in call_result.content if block.type == "text")
    return {"text": text, "is_error": bool(call_result.isError)}


class McpClient:
    def __init__(self, url=ENDPOINT):
        self._url = url
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._requests = None
        self._served = None

    def __enter__(self):
        self._thread.start()
        ready = concurrent.futures.Future()
        self._served = asyncio.run_coroutine_threadsafe(self._serve(ready), self._loop)
        try:
            ready.result(CONNECT_TIMEOUT_S)
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc_info):
        if self._requests is not None:
            self._loop.call_soon_threadsafe(self._requests.put_nowait, None)
            try:
                self._served.result(CONNECT_TIMEOUT_S)
            except BaseException:
                pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(CONNECT_TIMEOUT_S)

    async def _serve(self, ready):
        try:
            async with streamablehttp_client(self._url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._requests = asyncio.Queue()
                    ready.set_result(None)
                    while (request := await self._requests.get()) is not None:
                        tool, args, reply = request
                        try:
                            reply.set_result(to_result(await session.call_tool(tool, args)))
                        except Exception as exc:
                            reply.set_exception(exc)
        except BaseException as exc:
            if not ready.done():
                ready.set_exception(exc)
            raise

    def _ended(self):
        cause = None if self._served.cancelled() else self._served.exception()
        return ConnectionError(f"MCP session to {self._url} has ended: {cause!r}")

    def call(self, tool, args):
        """Call ``tool``; raise at once when the session task has ended instead of waiting."""
        if self._served.done():
            raise self._ended()
        reply = concurrent.futures.Future()
        self._loop.call_soon_threadsafe(self._requests.put_nowait, (tool, args, reply))
        done, _ = concurrent.futures.wait(
            [reply, self._served], CALL_TIMEOUT_S, concurrent.futures.FIRST_COMPLETED
        )
        if reply in done:
            return reply.result()
        if self._served in done:
            raise self._ended()
        raise TimeoutError(f"{tool} gave no answer in {CALL_TIMEOUT_S:.0f} s")
