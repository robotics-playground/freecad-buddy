"""Headless host front: MCP over stdio, FreeCAD in a worker child process.

This process serves MCP over stdio and never imports FreeCAD. It spawns one worker
(``hosts/headless/worker.py``) with this interpreter, hands it a per-session token on the
worker's stdin, reads the worker's port from the worker's stdout, and forwards every tool call
to the worker's RPC listener (AD-2, AD-3). FreeCAD never releases the GIL during a C++ operation,
so only a separate process can observe a call that runs too long. Stdout carries only the MCP
protocol; logs go to stderr.

When the MCP client closes stdin, this process closes the worker's stdin, which stops the worker.
A worker still running 5 s later is ended and the host exits 1, as it does when the worker exits
with a non-zero code. A worker that exits on its own is not restarted: every later call returns
``WORKER_CRASHED``.

If the interpreter cannot ``import FreeCAD`` the worker exits 2 with a message on stderr, and so
does this process.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import subprocess
import sys
import time

from freecad_buddy.adapters.audit_log import AuditSink, default_audit_path
from freecad_buddy.adapters.mcp_server import (
    Capabilities,
    build_server,
    configure_stderr_logging,
    serve_stdio,
)
from freecad_buddy.adapters.rpc_client import RpcClient, _worker_crashed
from freecad_buddy.contracts import ResultEnvelope, mirror_text
from freecad_buddy.hosts.rpc_proxy import build_proxy_registry, call_budgets

logger = logging.getLogger("freecad_buddy.hosts.headless")

_WORKER_MODULE = "freecad_buddy.hosts.headless.worker"
_WORKER_HOST = "127.0.0.1"
_SHUTDOWN_GRACE_S = 5.0


def _envelope(status: str, message: str, data: dict) -> ResultEnvelope:
    structured: dict = {}
    return {
        "schema": "fcb.result-envelope/1",
        "status": status,  # type: ignore[typeddict-item]
        "detail": {"code": status, "message": message, "data": data},  # type: ignore[typeddict-item]
        "structured_content": structured,
        "text": mirror_text(structured),
    }


class _AbandonedCall:
    """A call whose budget ran out while its body still runs in the worker."""

    def __init__(self, method: str, budget_s: float) -> None:
        self.method = method
        self.budget_s = budget_s
        self.timed_out_at = time.monotonic()

    def refusal(self) -> ResultEnvelope:
        data = {"quarantined": True}
        if time.monotonic() - self.timed_out_at >= self.budget_s:
            return _envelope(
                "WORKER_CRASHED",
                f"not dispatched: a timed-out {self.method} call has run past twice its "
                f"{self.budget_s:g} s budget in the headless worker; the session recovers on its "
                "own if the call returns, else restart the headless host, which discards unsaved "
                "open documents",
                data,
            )
        return _envelope(
            "TIMEOUT",
            f"not dispatched: the session is quarantined while a timed-out {self.method} call "
            "still runs in the headless worker; call again after it returns",
            data,
        )


class WorkerClient:
    """The worker's ``RpcClient``, bounded per call and quarantined after a timeout (AD-27).

    Each call waits for the worker's reply for at most its method budget from ``budgets``. A
    call that runs out returns ``TIMEOUT`` and leaves its body running in the worker; until that
    body returns, every call is refused without dispatch. The refusal becomes ``WORKER_CRASHED``
    once the body has run its budget a second time, but the worker is never ended, so no open
    document is lost. Once the worker has exited, every call returns ``WORKER_CRASHED``.
    """

    def __init__(
        self, client: RpcClient, process: subprocess.Popen, budgets: dict[str, float]
    ) -> None:
        self._client = client
        self._process = process
        self._budgets = budgets
        self._abandoned: _AbandonedCall | None = None

    def call(self, method: str, params: dict | None = None) -> ResultEnvelope:
        code = self._process.poll()
        if code is not None:
            return _worker_crashed(
                f"headless worker exited with code {code}; restart the headless host",
                unreachable=True,
            )
        if self._abandoned is not None:
            if not self._client.reconnect_answered():
                return self._abandoned.refusal()
            self._abandoned = None
        budget_s = self._budgets[method]
        envelope = self._client.call(method, params, read_timeout_s=budget_s)
        # The worker's inline marshal never times out, so a TIMEOUT is this client's read timeout.
        if envelope.get("status") != "TIMEOUT":
            return envelope
        # Connect now, so the worker answers as soon as the abandoned body returns.
        if not self._client.reconnect_answered():
            self._abandoned = _AbandonedCall(method, budget_s)
        return _envelope(
            "TIMEOUT",
            f"the headless worker did not answer {method} within its {budget_s:g} s budget",
            {"marshal_timeout": True, "maybe_still_running": True},
        )

    def close(self) -> None:
        self._client.close()


def _connect_worker(worker: subprocess.Popen) -> dict | None:
    """Send the worker its token and read its port; ``None`` when the worker exits first."""
    token = secrets.token_urlsafe(32)
    try:
        worker.stdin.write((token + "\n").encode("ascii"))
        worker.stdin.flush()
    except OSError:
        # The worker exited before it read the token; the empty port line below reports it.
        pass
    line = worker.stdout.readline()
    worker.stdout.close()
    if not line:
        return None
    return {"host": _WORKER_HOST, "port": json.loads(line)["port"], "token": token}


def shut_down_worker(
    worker: subprocess.Popen, client: WorkerClient, grace_s: float = _SHUTDOWN_GRACE_S
) -> int:
    """Close the RPC connection and the worker's stdin, then wait for the worker to exit.

    Returns 0 when it exits with code 0 within ``grace_s``. A worker that exits with another code,
    or that is still running and gets ended, is logged once at ERROR and returns 1.
    """
    client.close()
    try:
        worker.stdin.close()
    except OSError:
        pass
    try:
        code = worker.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        logger.error("headless worker still running %.0f s after shutdown; ending it", grace_s)
        worker.kill()
        worker.wait()
        return 1
    if code != 0:
        logger.error("headless worker exited with code %s", code)
        return 1
    return 0


def run(argv: list[str] | None = None) -> int:  # noqa: ARG001 - reserved for future flags
    """Spawn the FreeCAD worker and serve the MCP surface over stdio, forwarding to the worker."""
    configure_stderr_logging()
    worker = subprocess.Popen(
        [sys.executable, "-m", _WORKER_MODULE], stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    endpoint = _connect_worker(worker)
    if endpoint is None:
        return worker.wait()

    client = WorkerClient(RpcClient(endpoint=endpoint, read_timeout_s=None), worker, call_budgets())
    caps = Capabilities.from_env(dict(os.environ))
    audit_path = default_audit_path().resolve()
    logger.info("audit log: %s", audit_path)
    server = build_server(build_proxy_registry(client, caps), caps, AuditSink(audit_path))

    logger.info("freecad-buddy headless MCP server starting (stdio)")
    try:
        asyncio.run(serve_stdio(server))
        logger.info("MCP client closed stdin; stopping the headless worker")
    except KeyboardInterrupt:
        logger.info("headless MCP server interrupted; shutting down")
    except Exception:
        logger.exception("headless MCP server terminated with an error")
        shut_down_worker(worker, client)
        return 1
    return shut_down_worker(worker, client)
