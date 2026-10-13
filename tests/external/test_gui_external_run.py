"""``entry.run`` as a real process: it pins its FreeCAD at start and exits with it (AD-2)."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

# Imports, uvicorn start-up and the first bind take a few seconds on a cold Windows runner.
_START_TIMEOUT_S = 30.0
# The watchdog polls once a second and exits one grace second later; the rest is process teardown.
_EXIT_WITHIN_S = 3.5


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _healthz(port: int) -> dict:
    deadline = time.monotonic() + _START_TIMEOUT_S
    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as reply:
                return json.loads(reply.read())
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def test_should_name_its_freecad_and_exit_with_it_when_run_as_a_process(tmp_path):
    # Arrange
    freecad = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    disco = tmp_path / "freecad-buddy"
    disco.mkdir()
    record = {"schema": 1, "pid": freecad.pid, "host": "127.0.0.1", "port": 1, "token": "t"}
    (disco / f"rpc-{freecad.pid}.json").write_text(json.dumps(record), encoding="utf-8")
    port = _free_port()
    proxy = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"from freecad_buddy.hosts.gui_external.entry import run; run(port={port})",
        ],
        env={**os.environ, "FREECAD_BUDDY_RPC_DIR": str(tmp_path)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        health = _healthz(port)

        # Act
        freecad.kill()
        freecad.wait()
        killed = time.monotonic()
        proxy.wait(timeout=_EXIT_WITHIN_S + 5)
        exited_after = time.monotonic() - killed
    finally:
        freecad.kill()
        proxy.kill()
        proxy.wait()

    # Assert
    assert health["freecad_pid"] == freecad.pid
    assert exited_after < _EXIT_WITHIN_S
    assert not _port_open(port)
