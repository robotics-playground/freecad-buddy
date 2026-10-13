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

from freecad_buddy.adapters.audit_log import AuditSink, default_audit_path
from freecad_buddy.adapters.mcp_server import (
    Capabilities,
    build_server,
    configure_stderr_logging,
    serve_stdio,
)
from freecad_buddy.adapters.rpc_client import RpcClient, _worker_crashed
from freecad_buddy.contracts import ResultEnvelope
from freecad_buddy.hosts.rpc_proxy import build_proxy_registry

logger = logging.getLogger("freecad_buddy.hosts.headless")

_WORKER_MODULE = "freecad_buddy.hosts.headless.worker"
_WORKER_HOST = "127.0.0.1"
_SHUTDOWN_GRACE_S = 5.0


class WorkerClient:
    """The worker's ``RpcClient``, which stops calling once the worker process has exited."""

    def __init__(self, client: RpcClient, process: subprocess.Popen) -> None:
        self._client = client
        self._process = process

    def call(self, method: str, params: dict | None = None) -> ResultEnvelope:
        code = self._process.poll()
        if code is not None:
            return _worker_crashed(
                f"headless worker exited with code {code}; restart the headless host",
                unreachable=True,
            )
        return self._client.call(method, params)

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

    client = WorkerClient(RpcClient(endpoint=endpoint, read_timeout_s=None), worker)
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
