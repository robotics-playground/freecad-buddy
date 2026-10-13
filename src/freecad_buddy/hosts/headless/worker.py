"""Headless FreeCAD worker: the tool registry behind an RPC listener on the main thread.

The headless front spawns this module with its own interpreter and is its only client (AD-2).
The front writes the session token as the first line of this process's stdin. This process
answers with one ``{"port": N}`` line on its stdout and writes nothing else there. Stdin EOF
means the front has ended: the listener stops and this process exits.

Stdlib and FreeCAD only: this process never imports ``mcp`` (AD-12). Calls run inline through
``Marshal(InlineExecutor())``, so inline dispatch is main-thread execution. The front writes the
adapter audit pairs; this process writes only the records the mutation bracket and the camera fit
write themselves, to the same file.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading

from freecad_buddy.adapters.audit_log import AuditSink, default_audit_path
from freecad_buddy.adapters.marshal import InlineExecutor, Marshal
from freecad_buddy.adapters.render_probe import OffscreenRenderPort
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry
from freecad_buddy.adapters.rpc_listener import RpcListener
from freecad_buddy.hosts.tool_catalog import build_inline_handlers
from freecad_buddy.usecases import confirm, shim, view_fit
from freecad_buddy.usecases.capabilities import Capabilities, exec_registered
from freecad_buddy.usecases.documents import DocumentRegistry, sweep_temp_dir
from freecad_buddy.usecases.exports import ExportRegistry

logger = logging.getLogger("freecad_buddy.hosts.headless.worker")


class FreeCADUnavailable(RuntimeError):
    """Raised when the interpreter cannot ``import FreeCAD``."""


def verify_freecad_importable() -> None:
    """Confirm the host is viable; raise ``FreeCADUnavailable`` when FreeCAD cannot be imported."""
    try:
        import FreeCAD  # noqa: F401
    except ImportError as exc:
        raise FreeCADUnavailable(
            "headless host requires `import FreeCAD` in this interpreter; it failed"
        ) from exc


def build_registry(
    registry: DocumentRegistry, caps: Capabilities, marshal: Marshal
) -> MethodRegistry:
    """Register the tool surface, each handler marshaled onto the FreeCAD thread.

    ``viewport_port=None`` is stated, not defaulted by omission: this host has no live 3D view, so
    the framing capability is unavailable here even though the offscreen render probe may report
    itself available (AD-29 — the two predicates are independent).
    """
    return build_inline_handlers(
        registry,
        ExportRegistry(),
        caps,
        marshal,
        OffscreenRenderPort(),
        viewport_port=None,
    )


def _configure_stderr_logging() -> None:
    # The same format as ``mcp_server.configure_stderr_logging``, which this process cannot import
    # because that module imports ``mcp``.
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("freecad_buddy")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _stop_on_stdin_eof(listener: RpcListener) -> None:
    sys.stdin.buffer.read()
    listener.stop()


def run() -> int:
    """Build the H1 registry and serve it to the front over RPC until the front closes stdin."""
    # Keep the pipe the front reads for the port line alone. Every other write to stdout, from
    # Python or from FreeCAD's C++ console, goes to stderr, so it can neither corrupt that line
    # nor fill a pipe nobody reads after it.
    port_pipe = os.fdopen(os.dup(1), "w", encoding="utf-8")
    os.dup2(2, 1)
    _configure_stderr_logging()
    try:
        verify_freecad_importable()
    except FreeCADUnavailable as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    token = sys.stdin.buffer.readline().decode("ascii").strip()
    if not token:
        logger.error("no session token on stdin; the headless front has gone")
        return 1

    # Session start is the only safe moment to clear temp artifacts: a render link the previous
    # session returned may still have been being read when that call completed (AD-25).
    logger.info("session-start sweep removed %s leftover temp artifact(s)", sweep_temp_dir())
    caps = Capabilities.from_env(dict(os.environ))
    try:
        shim.warm_capability_probes()
    except Exception:  # noqa: BLE001 - warm-up is best-effort; degrade to lazy probing
        logger.warning("capability-probe warm-up failed; probing lazily", exc_info=True)
    marshal = Marshal(InlineExecutor())
    methods = build_registry(DocumentRegistry(), caps, marshal)
    audit = AuditSink(default_audit_path().resolve())
    confirm.set_approval_sink(audit)
    view_fit.set_audit_sink(audit)
    listener = RpcListener(
        methods,
        marshal,
        token,
        freecad_version=shim.freecad_version(),
        capabilities={"gui": False, "qt_loop": False, "exec_enabled": exec_registered(caps)},
        discovery=False,
    )
    _host, port = listener.bind()
    port_pipe.write(json.dumps({"port": port}) + "\n")
    port_pipe.close()

    threading.Thread(
        target=_stop_on_stdin_eof, args=(listener,), name="fcb-stdin", daemon=True
    ).start()
    try:
        listener.serve_forever_inline()
    except KeyboardInterrupt:
        listener.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
