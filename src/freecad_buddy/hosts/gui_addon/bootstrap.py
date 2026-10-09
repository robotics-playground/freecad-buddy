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
import socket
import subprocess
import threading
from pathlib import Path

from freecad_buddy.adapters.audit_log import AuditSink, default_audit_path
from freecad_buddy.adapters.marshal import Marshal
from freecad_buddy.adapters.render_probe import OffscreenRenderPort
from freecad_buddy.adapters.rpc_listener import RpcListener
from freecad_buddy.hosts.gui_addon import managed_venv
from freecad_buddy.hosts.gui_addon.pump import QtMainThreadExecutor
from freecad_buddy.hosts.gui_addon.viewport import GuiViewportPort
from freecad_buddy.hosts.tool_catalog import build_inline_handlers
from freecad_buddy.usecases.capabilities import (
    AUTO_APPROVE_WARNING,
    Capabilities,
    auto_approve_enabled,
    exec_registered,
)
from freecad_buddy.usecases import shim
from freecad_buddy.usecases.documents import DocumentRegistry, sweep_temp_dir
from freecad_buddy.usecases.exports import ExportRegistry
from freecad_buddy.usecases.operator_settings import (
    AUDIT_LOG_VARIABLE,
    OPERATOR_VARIABLES,
    WORKDIR_VARIABLE,
    PreferenceValues,
    environment_overrides,
    resolve_env_overlay,
)

logger = logging.getLogger("freecad_buddy.hosts.gui_addon.bootstrap")

_MCP_HOST = "127.0.0.1"
_MCP_PORT = 8765

_listener: RpcListener | None = None
_mcp_proxy: subprocess.Popen | None = None
_provisioner: threading.Thread | None = None
_cancel_provisioning = threading.Event()
# The operator variables the environment set before the preferences were added to it.
_startup_overrides: dict[str, str] | None = None


def _user_app_data_dir() -> Path | None:
    try:
        import FreeCAD

        return Path(FreeCAD.getUserAppDataDir())
    except Exception:  # noqa: BLE001 - no FreeCAD data dir: callers fall back to cwd
        return None


def _data_dir() -> Path:
    """``<FreeCAD user app data>/freecad-buddy``: logs, discovery files, audit log, workdir."""
    base = _user_app_data_dir()
    return base / "freecad-buddy" if base is not None else Path("freecad-buddy")


def _managed_venv_dir() -> Path:
    """``<FreeCAD user app data>/FreeCADBuddy/venv``: the proxy venv a release install builds."""
    base = _user_app_data_dir()
    return (base if base is not None else Path()) / "FreeCADBuddy" / "venv"


def _log_file_path() -> Path:
    """The addon log path from ``FREECAD_BUDDY_LOG_FILE``, else FreeCAD user appdata.

    GUI-mode addon logs otherwise reach only FreeCAD's Report View. A file handler mirrors them
    to disk so they can be read without the GUI. The default sits under the user's FreeCAD data
    dir alongside the RPC discovery file.
    """
    override = os.environ.get("FREECAD_BUDDY_LOG_FILE")
    if override:
        return Path(override)
    return _data_dir() / "addon.log"


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
    # Before the sweep and the capability read: both take their settings from the environment.
    preferences = _apply_operator_settings()
    # Session start is the only safe moment to clear temp artifacts: a render link the previous
    # session returned may still have been being read when that call completed (AD-25).
    logger.info("session-start sweep removed %s leftover temp artifact(s)", sweep_temp_dir())
    caps = Capabilities.from_env(dict(os.environ))
    if auto_approve_enabled(caps):
        logger.warning(AUTO_APPROVE_WARNING)
    executor = QtMainThreadExecutor()
    marshal = Marshal(executor)
    # Called directly, never through the marshal: start_bridge already runs on the Qt main
    # thread, and QtMainThreadExecutor.submit posts an event only that thread's event loop can
    # deliver. Marshaling here queued an event and then blocked the one thread able to dispatch
    # it, so the warm-up burned its whole budget and the probes never ran.
    try:
        shim.warm_capability_probes()
    except Exception:  # noqa: BLE001 - warm-up is best-effort; degrade to lazy probing
        logger.warning("capability-probe warm-up failed; probing lazily", exc_info=True)
    doc_registry = DocumentRegistry()
    registry = build_inline_handlers(
        doc_registry,
        ExportRegistry(),
        caps,
        None,
        OffscreenRenderPort(),
        viewport_port=GuiViewportPort(),
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
    _start_mcp_proxy(preferences.uv_path)
    return listener


def _apply_operator_settings() -> PreferenceValues:
    """Add the preference page values to ``os.environ`` where no variable is set, and log them.

    The MCP proxy child inherits the environment, so it sees the same effective settings.
    """
    global _startup_overrides
    preferences = shim.read_operator_preferences()
    _startup_overrides = environment_overrides(os.environ)
    overlay = resolve_env_overlay(os.environ, preferences, _data_dir())
    os.environ.update(overlay)
    # No preference sets the workdir; an empty audit log field leaves the default path.
    defaulted = {WORKDIR_VARIABLE}
    if not preferences.audit_log_path:
        defaulted.add(AUDIT_LOG_VARIABLE)

    def source(name: str) -> str:
        if name in overlay:
            return "default" if name in defaulted else "preference"
        return "env" if name in _startup_overrides else "unset"

    effective = ", ".join(
        f"{name}={os.environ.get(name, '')!r} ({source(name)})" for name in OPERATOR_VARIABLES
    )
    logger.info("operator settings: %s, uv path %r", effective, preferences.uv_path)
    return preferences


def startup_overrides() -> dict[str, str]:
    """The operator variables set by the environment FreeCAD started with.

    Before the bridge starts, ``os.environ`` is still that environment; after, it also holds the
    preference values, so the snapshot taken at start answers instead.
    """
    if _startup_overrides is not None:
        return dict(_startup_overrides)
    return environment_overrides(os.environ)


def _port_open(host: str, port: int) -> bool:
    """Whether something already accepts a TCP connection at ``host:port``."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.3)
        return probe.connect_ex((host, port)) == 0


_SERVE_ARGS = ["-m", "freecad_buddy.hosts.main", "serve", "--mode", "rpc", "--transport", "http"]
# Written by scripts/build_addon.py into the addon root: one line, the absolute repo path.
_REPO_ROOT_MARKER = "repo-root.txt"


def _discover_external_python(here: Path | None = None) -> Path | None:
    """Find the external interpreter that can run the MCP proxy, from the addon's own location.

    The proxy imports ``mcp``/FastMCP, which AD-12 forbids inside FreeCAD's bundled Python, so it
    must run in a DIFFERENT interpreter. That interpreter is discovered — not configured — by
    walking from this package's install path to the repo root and probing the standard venv the
    project ships (``.venv``/``venv``). Zero env vars: install the addon (a junction to the repo
    package, or a ``build_addon.py`` copy carrying the ``repo-root.txt`` marker), open FreeCAD, and
    the repo ``.venv`` is found automatically.

    Returns the venv python whose ``freecad_buddy`` + ``mcp`` are importable, or ``None``.
    """
    # bootstrap.py is <root>/src/freecad_buddy/hosts/gui_addon/bootstrap.py — parents[4] is the
    # repo root when installed as an editable src junction. A built copy lives at
    # <Mod>/FreeCADBuddy/freecad_buddy/... and shares no ancestor with the repo, so it finds the
    # repo only through the marker build_addon.py writes into the addon root (parents[3]).
    here = here or Path(__file__).resolve()
    roots: list[Path] = []
    if len(here.parents) > 4:
        roots.append(here.parents[4])
    if len(here.parents) > 3:
        try:
            marked = (here.parents[3] / _REPO_ROOT_MARKER).read_text(encoding="utf-8-sig").strip()
        except (OSError, UnicodeDecodeError):  # a bad marker must never break start_bridge
            marked = ""
        if marked:
            roots.append(Path(marked))
    for override in (os.environ.get("FREECAD_BUDDY_REPO"), os.environ.get("FREECAD_BUDDY_SRC")):
        if override:
            base = Path(override)
            roots.append(base.parent.parent if base.name == "freecad_buddy" else base)

    # On Windows prefer pythonw.exe (the GUI/windowless interpreter): the console python re-execs
    # through a launcher that opens its own console window even under CREATE_NO_WINDOW, so
    # pythonw.exe is what actually keeps the background proxy silent. Fall back to python.exe.
    if os.name == "nt":
        subdir, names = "Scripts", ("pythonw.exe", "python.exe")
    else:
        subdir, names = "bin", ("python",)
    seen: set[Path] = set()
    for root in roots:
        for venv in (".venv", "venv"):
            for name in names:
                candidate = root / venv / subdir / name
                if candidate in seen:
                    continue
                seen.add(candidate)
                if candidate.is_file():
                    return candidate
    return None


def _addon_root() -> Path:
    """``<addon>``: bootstrap.py is ``<addon>/freecad_buddy/hosts/gui_addon/bootstrap.py``."""
    return Path(__file__).resolve().parents[3]


def _mcp_proxy_command(uv: Path | None, wheel: Path | None) -> list[str] | None:
    """Resolve an MCP-proxy launch command that needs no provisioning, or ``None``.

    Resolution order:
      1. ``FREECAD_BUDDY_MCP_CMD`` — explicit space-separated command, used verbatim (override;
         the preference page sets it when the variable is unset).
      2. **Auto-discovered venv python** next to the installed addon → run the serve module
         directly. This is the dev install: a repo junction or a ``build_addon.py`` copy.
      3. ``FREECAD_BUDDY_REPO``/``FREECAD_BUDDY_SRC`` + ``uv`` → ``uv run`` fallback.
      4. The managed venv, when it was provisioned from the bundled ``wheel``.
    ``None`` leaves the caller to provision the managed venv or report why it cannot.
    """
    explicit = os.environ.get("FREECAD_BUDDY_MCP_CMD")
    if explicit:
        return explicit.split()

    python = _discover_external_python()
    if python is not None:
        return [str(python), *_SERVE_ARGS]

    repo = os.environ.get("FREECAD_BUDDY_REPO") or os.environ.get("FREECAD_BUDDY_SRC")
    if repo and uv:
        repo_root = Path(repo)
        if repo_root.name == "freecad_buddy":
            repo_root = repo_root.parent.parent
        return [str(uv), "run", "--project", str(repo_root), "freecad-buddy",
                "serve", "--mode", "rpc", "--transport", "http"]

    venv = _managed_venv_dir()
    if wheel is not None and managed_venv.is_current(venv, wheel):
        return [str(managed_venv.venv_python(venv)), *_SERVE_ARGS]
    return None


def _start_mcp_proxy(uv_path: str) -> None:
    """Spawn the external MCP HTTP proxy so opening FreeCAD is the only step to reach the bridge.

    Skips when ``FREECAD_BUDDY_NO_AUTO_MCP`` is set or port 8765 is already served. A release
    install without a current managed venv provisions it on a daemon thread and spawns the proxy
    when that finishes, so the GUI start never waits on ``uv``. The child inherits the operator's
    env (so the exec flag and ``FREECAD_BUDDY_RPC_DIR`` carry through) and is terminated in
    ``stop_bridge``.
    """
    global _provisioner
    if os.environ.get("FREECAD_BUDDY_NO_AUTO_MCP"):
        logger.info("FREECAD_BUDDY_NO_AUTO_MCP set; not auto-starting the MCP proxy")
        return
    if _port_open(_MCP_HOST, _MCP_PORT):
        logger.info("MCP proxy already on http://%s:%s/mcp; not spawning", _MCP_HOST, _MCP_PORT)
        return
    uv = managed_venv.find_uv(uv_path)
    logger.info("uv: %s", uv if uv is not None else "not found")
    wheel = managed_venv.bundled_wheel(_addon_root())
    command = _mcp_proxy_command(uv, wheel)
    if command is not None:
        _spawn_mcp_proxy(command)
        return
    if wheel is not None and uv is not None:
        _cancel_provisioning.clear()
        _provisioner = threading.Thread(
            target=_provision_and_spawn,
            args=(uv, wheel),
            name="freecad-buddy-provision",
            daemon=True,
        )
        _provisioner.start()
        return
    if wheel is not None:
        logger.warning(
            "MCP proxy not started: uv not found. Install uv, or set its path in Edit > "
            "Preferences > FreeCAD Buddy > uv path, then restart FreeCAD. The RPC listener is up."
        )
        return
    logger.info(
        "MCP proxy not auto-started: no .venv/venv interpreter found next to the addon, no bundled "
        "wheel and no MCP command. Create the project venv (uv sync) so the addon can find it, or "
        "set the MCP command in Edit > Preferences > FreeCAD Buddy. The RPC listener is up; start "
        "the proxy manually (serve --mode rpc) to reach it over MCP in the meantime."
    )


def _provision_and_spawn(uv: Path, wheel: Path) -> None:
    """Provisioning thread: build the managed venv, then spawn the proxy from it."""
    venv = _managed_venv_dir()
    log_path = _log_file_path().parent / "provision.log"
    logger.info(
        "provisioning the MCP proxy venv at %s from %s; log: %s", venv, wheel.name, log_path
    )
    try:
        ready = managed_venv.provision(uv, wheel, venv, log_path, _cancel_provisioning)
    except Exception:  # noqa: BLE001 - provisioning must never take the listener down
        logger.exception("MCP proxy venv provisioning failed; the RPC listener is still up")
        return
    if not ready or _cancel_provisioning.is_set():
        return
    logger.info("MCP proxy venv ready at %s", venv)
    if _port_open(_MCP_HOST, _MCP_PORT):
        logger.info("MCP proxy already on http://%s:%s/mcp; not spawning", _MCP_HOST, _MCP_PORT)
        return
    _spawn_mcp_proxy([str(managed_venv.venv_python(venv)), *_SERVE_ARGS])


def _spawn_mcp_proxy(command: list[str]) -> None:
    global _mcp_proxy
    try:
        proxy_log = _log_file_path().parent / "mcp-proxy.log"
        logfile = open(proxy_log, "w", encoding="utf-8")  # noqa: SIM115 - child owns it for its life
        _mcp_proxy = subprocess.Popen(  # noqa: S603 - operator-configured launch command
            command, **managed_venv.no_window_kwargs(logfile)
        )
        logger.info(
            "spawned MCP proxy (pid %s) -> http://%s:%s/mcp; proxy log: %s",
            _mcp_proxy.pid, _MCP_HOST, _MCP_PORT, proxy_log,
        )
    except Exception:  # noqa: BLE001 - a failed proxy spawn must not break the listener/GUI start
        logger.exception("failed to spawn the MCP proxy; the RPC listener is still up")
        _mcp_proxy = None


def stop_bridge() -> None:
    """Stop provisioning, the MCP proxy (if spawned) and the listener; clear the singletons."""
    global _listener, _mcp_proxy, _provisioner
    # Joined before the proxy teardown: a provisioning thread that finishes now spawns the proxy,
    # and only after the join is that child visible here to terminate.
    _cancel_provisioning.set()
    if _provisioner is not None:
        _provisioner.join(timeout=10)
        _provisioner = None
    if _mcp_proxy is not None:
        try:
            _mcp_proxy.terminate()
            _mcp_proxy.wait(timeout=5)
        except Exception:  # noqa: BLE001 - best-effort child teardown
            try:
                _mcp_proxy.kill()
            except Exception:  # noqa: BLE001
                logger.debug("could not kill the MCP proxy child", exc_info=True)
        _mcp_proxy = None
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
