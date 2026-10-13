"""GUI proxy identity (AD-2, AD-24): ``GET /healthz`` and the watchdog that ends an orphan."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys

import pytest
from mcp.server.lowlevel import Server
from starlette.testclient import TestClient

from freecad_buddy.adapters.rpc_client import RpcClient
from freecad_buddy.contracts.rpc import MCP_PROXY_SERVICE
from freecad_buddy.hosts.gui_external import entry

TOKEN = "healthz-secret-token"


class _Exited(Exception):
    pass


class _StopWatching(Exception):
    pass


class _PinnedClient:
    def __init__(self, pid: int) -> None:
        self.pinned_record = {"pid": pid, "token": TOKEN}


class _UnpinnedClient:
    """Never pinned; ends the watchdog loop after ``checks`` reads so the test can return."""

    def __init__(self, checks: int) -> None:
        self.checks_left = checks

    @property
    def pinned_record(self):
        if self.checks_left == 0:
            raise _StopWatching
        self.checks_left -= 1
        return None


def _pinned_client(tmp_path) -> RpcClient:
    disco = tmp_path / "freecad-buddy"
    disco.mkdir(parents=True)
    record = {"schema": 1, "pid": os.getpid(), "host": "127.0.0.1", "port": 1, "token": TOKEN}
    (disco / f"rpc-{os.getpid()}.json").write_text(json.dumps(record), encoding="utf-8")
    client = RpcClient(appdata_dir=str(tmp_path), pin=True)
    client.pin()
    return client


def test_should_name_the_service_pid_and_session_without_the_token_when_healthz_is_called(
    tmp_path,
):
    # Arrange
    app = entry.build_app(Server("test"), _pinned_client(tmp_path))

    # Act
    response = TestClient(app).get("/healthz")

    # Assert
    body = response.json()
    assert response.status_code == 200
    assert body["service"] == MCP_PROXY_SERVICE
    assert body["freecad_pid"] == os.getpid()
    assert body["session_id"] == hashlib.sha256(TOKEN.encode("utf-8")).hexdigest()[:16]
    assert TOKEN not in response.text


def test_should_report_no_pid_when_the_proxy_is_not_pinned(tmp_path):
    # Arrange
    client = RpcClient(appdata_dir=str(tmp_path), pin=True)

    # Act
    body = entry.health(client)

    # Assert
    assert body == {"service": MCP_PROXY_SERVICE, "freecad_pid": None, "session_id": None}


def test_should_log_once_and_exit_when_the_pinned_freecad_is_gone(monkeypatch, caplog):
    # Arrange
    freecad = subprocess.Popen([sys.executable, "-c", "pass"])
    freecad.wait()
    exit_codes: list[int] = []

    def _exit(code: int) -> None:
        exit_codes.append(code)
        raise _Exited

    monkeypatch.setattr(entry, "_WATCHDOG_INTERVAL_S", 0.01)
    monkeypatch.setattr(entry, "_EXIT_GRACE_S", 0.0)
    monkeypatch.setattr(entry.os, "_exit", _exit)
    monkeypatch.setattr(entry.logging, "shutdown", lambda: None)

    # Act
    with caplog.at_level(logging.INFO, logger=entry.logger.name), pytest.raises(_Exited):
        entry.exit_when_freecad_exits(_PinnedClient(freecad.pid), 8765)

    # Assert
    records = [r for r in caplog.records if r.name == entry.logger.name]
    assert exit_codes == [0]
    assert len(records) == 1
    assert f"pid {freecad.pid} has exited" in records[0].getMessage()


def test_should_keep_running_when_the_proxy_is_not_pinned(monkeypatch):
    # Arrange
    exit_codes: list[int] = []
    monkeypatch.setattr(entry, "_WATCHDOG_INTERVAL_S", 0.01)
    monkeypatch.setattr(entry, "_EXIT_GRACE_S", 0.0)
    monkeypatch.setattr(entry.os, "_exit", exit_codes.append)
    client = _UnpinnedClient(checks=5)

    # Act
    with pytest.raises(_StopWatching):
        entry.exit_when_freecad_exits(client, 8765)

    # Assert
    assert client.checks_left == 0
    assert exit_codes == []
