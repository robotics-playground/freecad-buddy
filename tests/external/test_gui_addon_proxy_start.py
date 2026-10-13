"""The addon's MCP-proxy start when port 8765 is already served (AD-2, AD-24).

Each case points the addon at a stub HTTP server on a free port. The addon never reuses a served
port: it waits only for a proxy whose FreeCAD is gone, and every other holder is an ERROR.
"""

from __future__ import annotations

import json
import logging
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from freecad_buddy.contracts.rpc import MCP_PROXY_SERVICE
from freecad_buddy.usecases.operator_settings import PreferenceValues

_JOIN_S = 15.0
# Well under the 10 s orphan wait and over the 1 s health probe: a run this short did not wait.
_NO_WAIT_S = 3.0


def _stub_server(status: int, body: dict | None) -> ThreadingHTTPServer:
    """An HTTP server on a free port that answers every GET with ``status`` and ``body``."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server API name
            payload = json.dumps(body).encode("utf-8") if body is not None else b"not found"
            self.send_response(status)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _stop(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _dead_pid() -> int:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


@pytest.fixture
def bootstrap(monkeypatch, stub_qt):
    from freecad_buddy.hosts.gui_addon import bootstrap

    monkeypatch.delenv("FREECAD_BUDDY_NO_AUTO_MCP", raising=False)
    monkeypatch.setattr(bootstrap, "_provisioner", None)
    monkeypatch.setattr(bootstrap, "_cancel_provisioning", threading.Event())
    monkeypatch.setattr(bootstrap, "_mcp_proxy_command", lambda uv, wheel: ["proxy"])
    return bootstrap


@pytest.fixture
def spawned(monkeypatch, bootstrap):
    commands: list[list[str]] = []
    monkeypatch.setattr(bootstrap, "_spawn_mcp_proxy", commands.append)
    return commands


def _start_and_join(bootstrap) -> None:
    bootstrap._start_mcp_proxy("")
    if bootstrap._provisioner is not None:
        bootstrap._provisioner.join(timeout=_JOIN_S)


def _errors(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]


def test_should_spawn_the_proxy_when_the_port_is_free(monkeypatch, bootstrap, spawned):
    # Arrange
    monkeypatch.setattr(bootstrap, "_MCP_PORT", _free_port())

    # Act
    _start_and_join(bootstrap)

    # Assert
    assert spawned == [["proxy"]]


@pytest.mark.parametrize("orphan_proxy", [True, False], ids=["orphan-proxy", "no-healthz"])
def test_should_wait_and_then_spawn_when_the_holder_frees_the_port(
    monkeypatch, bootstrap, spawned, caplog, orphan_proxy
):
    # Arrange
    if orphan_proxy:
        server = _stub_server(200, {"service": MCP_PROXY_SERVICE, "freecad_pid": _dead_pid()})
    else:
        server = _stub_server(404, None)
    monkeypatch.setattr(bootstrap, "_MCP_PORT", server.server_address[1])
    threading.Timer(0.5, _stop, args=(server,)).start()

    # Act
    with caplog.at_level(logging.INFO, logger=bootstrap.logger.name):
        _start_and_join(bootstrap)

    # Assert
    assert spawned == [["proxy"]]
    assert _errors(caplog) == []


def test_should_log_one_error_and_not_spawn_when_an_orphan_proxy_keeps_the_port(
    monkeypatch, bootstrap, spawned, caplog
):
    # Arrange
    server = _stub_server(200, {"service": MCP_PROXY_SERVICE, "freecad_pid": _dead_pid()})
    monkeypatch.setattr(bootstrap, "_MCP_PORT", server.server_address[1])
    monkeypatch.setattr(bootstrap, "_ORPHAN_EXIT_WAIT_S", 0.5)

    # Act
    try:
        with caplog.at_level(logging.INFO, logger=bootstrap.logger.name):
            _start_and_join(bootstrap)
    finally:
        _stop(server)

    # Assert
    assert spawned == []
    errors = _errors(caplog)
    assert len(errors) == 1
    assert "orphan MCP proxy" in errors[0]


def test_should_log_one_error_at_once_and_not_spawn_when_an_unpinned_proxy_holds_the_port(
    monkeypatch, bootstrap, spawned, caplog
):
    # Arrange
    server = _stub_server(200, {"service": MCP_PROXY_SERVICE, "freecad_pid": None})
    monkeypatch.setattr(bootstrap, "_MCP_PORT", server.server_address[1])
    started = time.monotonic()

    # Act
    try:
        with caplog.at_level(logging.INFO, logger=bootstrap.logger.name):
            _start_and_join(bootstrap)
    finally:
        _stop(server)

    # Assert
    assert time.monotonic() - started < _NO_WAIT_S
    assert spawned == []
    errors = _errors(caplog)
    assert len(errors) == 1
    assert "serves no FreeCAD" in errors[0]


def test_should_log_one_error_naming_the_pid_when_another_freecads_proxy_holds_the_port(
    monkeypatch, bootstrap, spawned, caplog
):
    # Arrange
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    server = _stub_server(200, {"service": MCP_PROXY_SERVICE, "freecad_pid": other.pid})
    monkeypatch.setattr(bootstrap, "_MCP_PORT", server.server_address[1])

    # Act
    try:
        with caplog.at_level(logging.INFO, logger=bootstrap.logger.name):
            _start_and_join(bootstrap)
    finally:
        _stop(server)
        other.kill()
        other.wait()

    # Assert
    assert spawned == []
    errors = _errors(caplog)
    assert len(errors) == 1
    assert f"pid {other.pid}" in errors[0]


@pytest.mark.parametrize(
    ("status", "body"),
    [(404, None), (200, {"service": "some-other-service"})],
    ids=["no-healthz", "other-service"],
)
def test_should_log_one_error_and_not_spawn_when_a_foreign_server_keeps_the_port(
    monkeypatch, bootstrap, spawned, caplog, status, body
):
    # Arrange
    server = _stub_server(status, body)
    monkeypatch.setattr(bootstrap, "_MCP_PORT", server.server_address[1])
    monkeypatch.setattr(bootstrap, "_ORPHAN_EXIT_WAIT_S", 0.5)

    # Act
    try:
        with caplog.at_level(logging.INFO, logger=bootstrap.logger.name):
            _start_and_join(bootstrap)
    finally:
        _stop(server)

    # Assert
    assert spawned == []
    errors = _errors(caplog)
    assert len(errors) == 1
    assert "held by another program" in errors[0]


def test_should_log_one_error_and_not_spawn_when_the_holder_never_answers_http(
    monkeypatch, bootstrap, spawned, caplog
):
    # Arrange
    silent = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    silent.bind(("127.0.0.1", 0))
    silent.listen(8)
    monkeypatch.setattr(bootstrap, "_MCP_PORT", silent.getsockname()[1])
    monkeypatch.setattr(bootstrap, "_ORPHAN_EXIT_WAIT_S", 0.5)

    # Act
    try:
        with caplog.at_level(logging.INFO, logger=bootstrap.logger.name):
            _start_and_join(bootstrap)
    finally:
        silent.close()

    # Assert
    assert spawned == []
    errors = _errors(caplog)
    assert len(errors) == 1
    assert "held by another program" in errors[0]


def test_should_start_the_listener_when_a_foreign_server_holds_the_port(
    monkeypatch, tmp_path, bootstrap, spawned
):
    # Arrange
    started = []

    class _FakeListener:
        def __init__(self, *args, **kwargs):
            pass

        def start_threaded(self):
            started.append(True)
            return ("127.0.0.1", 1234)

    server = _stub_server(404, None)
    monkeypatch.setattr(bootstrap, "_MCP_PORT", server.server_address[1])
    monkeypatch.setattr(bootstrap, "_ORPHAN_EXIT_WAIT_S", 0.5)
    monkeypatch.setenv("FREECAD_BUDDY_LOG_FILE", str(tmp_path / "addon.log"))
    monkeypatch.setattr(bootstrap, "build_inline_handlers", lambda *args, **kwargs: None)
    monkeypatch.setattr(bootstrap, "RpcListener", _FakeListener)
    monkeypatch.setattr(bootstrap, "_register_shutdown", lambda: None)
    monkeypatch.setattr(bootstrap, "_apply_operator_settings", lambda: PreferenceValues())
    monkeypatch.setattr(bootstrap, "_listener", None)

    # Act
    try:
        listener = bootstrap.start_bridge()
        bootstrap._provisioner.join(timeout=_JOIN_S)
    finally:
        bootstrap._listener = None
        _stop(server)

    # Assert
    assert started == [True]
    assert isinstance(listener, _FakeListener)
    assert spawned == []


def test_should_cancel_the_orphan_wait_when_the_bridge_stops(
    monkeypatch, bootstrap, spawned, caplog
):
    # Arrange
    server = _stub_server(200, {"service": MCP_PROXY_SERVICE, "freecad_pid": _dead_pid()})
    monkeypatch.setattr(bootstrap, "_MCP_PORT", server.server_address[1])
    monkeypatch.setattr(bootstrap, "_mcp_proxy", None)
    monkeypatch.setattr(bootstrap, "_listener", None)

    # Act
    try:
        with caplog.at_level(logging.INFO, logger=bootstrap.logger.name):
            bootstrap._start_mcp_proxy("")
            waiting = bootstrap._provisioner
            started = time.monotonic()
            bootstrap.stop_bridge()
            stopped_after = time.monotonic() - started
    finally:
        _stop(server)

    # Assert
    assert stopped_after < _NO_WAIT_S
    assert not waiting.is_alive()
    assert spawned == []
    assert _errors(caplog) == []


def test_should_not_spawn_when_the_bridge_stops_after_the_port_frees(
    monkeypatch, bootstrap, spawned
):
    # Arrange
    def _port_freed_during_quit():
        bootstrap._cancel_provisioning.set()
        return True

    monkeypatch.setattr(bootstrap, "_mcp_port_free", _port_freed_during_quit)

    # Act
    bootstrap._spawn_when_port_frees("")

    # Assert
    assert spawned == []
