"""GUI addon bootstrap: build the bridge and start the RPC listener.

``start_bridge`` (idempotent, module singleton) wires the Qt main-thread executor, the marshal,
the **un-marshaled** listener registry (the listener owns the single ``marshal.call``), a
per-session token, the audit sink, and the ``RpcListener``. ``stop_bridge`` is registered on
FreeCAD shutdown so the listener + discovery file don't leak.
"""

from __future__ import annotations

import atexit
import logging
import os
import secrets
from pathlib import Path

from freecad_buddy.adapters.audit_log import AuditSink, default_audit_path
from freecad_buddy.adapters.marshal import Marshal
from freecad_buddy.adapters.render_probe import OffscreenRenderPort
from freecad_buddy.adapters.rpc_listener import RpcListener
from freecad_buddy.hosts.gui_addon.pump import QtMainThreadExecutor
from freecad_buddy.hosts.tool_catalog import build_inline_handlers
from freecad_buddy.usecases.capabilities import Capabilities, exec_registered
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.exports import ExportRegistry

logger = logging.getLogger("freecad_buddy.hosts.gui_addon.bootstrap")

_listener: RpcListener | None = None


def _log_file_path() -> Path:
    """The addon log path from ``FREECAD_BUDDY_LOG_FILE``, else FreeCAD user appdata.

    GUI-mode addon logs otherwise reach only FreeCAD's Report View. A file handler mirrors them
    to disk so they can be read without the GUI. The default sits under the user's FreeCAD data
    dir alongside the RPC discovery file.
    """
    override = os.environ.get("FREECAD_BUDDY_LOG_FILE")
    if override:
        return Path(override)
    try:
        import FreeCAD

        base = Path(FreeCAD.getUserAppDataDir()) / "freecad-buddy"
    except Exception:  # noqa: BLE001 - no FreeCAD data dir: fall back to cwd
        base = Path("freecad-buddy")
    return base / "addon.log"


def _configure_file_logging() -> None:
    """Attach a file handler to the ``freecad_buddy`` logger so addon errors land on disk."""
    path = _log_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("freecad_buddy")
    if not any(isinstance(h, logging.FileHandler) for h in root.handlers):
        root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)


def _freecad_version() -> str:
    try:
        import FreeCAD

        return ".".join(str(p) for p in FreeCAD.Version()[:3])
    except Exception:  # noqa: BLE001 - version is informational only
        return "unknown"


def start_bridge() -> RpcListener:
    """Build the bridge and start the listener. Idempotent: returns the running listener."""
    global _listener
    if _listener is not None:
        return _listener

    _configure_file_logging()
    caps = Capabilities.from_env(dict(os.environ))
    executor = QtMainThreadExecutor()
    marshal = Marshal(executor)
    doc_registry = DocumentRegistry()
    registry = build_inline_handlers(
        doc_registry, ExportRegistry(), caps, None, OffscreenRenderPort()
    )
    token = secrets.token_urlsafe(32)
    audit = AuditSink(default_audit_path())
    capabilities = {
        "gui": True,
        "qt_loop": True,
        "exec_enabled": exec_registered(caps),
    }
    port_env = os.environ.get("FREECAD_BUDDY_RPC_PORT")
    try:
        port = int(port_env) if port_env else 0
    except ValueError:
        logger.warning("FREECAD_BUDDY_RPC_PORT=%r is not an integer; using ephemeral", port_env)
        port = 0

    listener = RpcListener(
        registry,
        marshal,
        token,
        port=port,
        freecad_version=_freecad_version(),
        capabilities=capabilities,
        audit=audit,
    )
    host, bound_port = listener.start_threaded()
    logger.info("freecad-buddy RPC listener started on %s:%s", host, bound_port)
    _listener = listener
    _register_shutdown()
    return listener


def stop_bridge() -> None:
    """Stop the listener and clear the singleton."""
    global _listener
    if _listener is None:
        return
    _listener.stop()
    _listener = None


def _register_shutdown() -> None:
    """Prefer FreeCAD's ``aboutToQuit`` signal; fall back to ``atexit``."""
    try:
        from PySide import QtCore

        app = QtCore.QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(stop_bridge)
            return
    except Exception:  # noqa: BLE001 - no Qt app: fall back to atexit
        logger.debug("no Qt application for aboutToQuit; using atexit", exc_info=True)
    atexit.register(stop_bridge)
