"""RpcClient tests: round-trip against a real listener, discovery selection, never-raises.

The client runs in the external process, so the tests exercise it against a real socket and
assert it synthesizes an envelope (never raises) on every failure path.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import sys
import threading

from freecad_buddy.adapters.marshal import Marshal
from freecad_buddy.adapters.rpc_client import RpcClient, _channel_error_envelope, discover
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.adapters.rpc_listener import RpcListener

TOKEN = "client-test-token"


class ThreadedExecutor:
    def submit(self, fn):
        threading.Thread(target=fn, daemon=True).start()


def _ok_envelope():
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": {"handle": "fcb-doc:1"},
        "text": "{}",
    }


def _registry():
    reg = MethodRegistry()
    reg.register(
        RpcMethod(name="document_create", handler=lambda **p: _ok_envelope(), mutating=True)
    )
    return reg


def _start_listener(tmp_path):
    listener = RpcListener(
        _registry(),
        Marshal(ThreadedExecutor()),
        TOKEN,
        freecad_version="1.1.1",
        appdata_dir=str(tmp_path),
    )
    listener.start_threaded()
    return listener


# -- round trip ------------------------------------------------------------------------------


def test_client_discovers_connects_and_calls(tmp_path):
    listener = _start_listener(tmp_path)
    try:
        client = RpcClient(appdata_dir=str(tmp_path))
        env = client.call("document_create", {"label": "x"})
        assert env["status"] == "OK"
        assert env["structured_content"]["handle"] == "fcb-doc:1"
        client.close()
    finally:
        listener.stop()


# -- channel-error mapping -------------------------------------------------------------------


def test_channel_error_maps_version_mismatch_to_invalid_input():
    env = _channel_error_envelope({"code": -32004, "message": "contract version unsupported"})
    assert env["status"] == "INVALID_INPUT"


def test_channel_error_unmapped_code_falls_back_to_worker_crashed():
    env = _channel_error_envelope({"code": -32099, "message": "weird"})
    assert env["status"] == "WORKER_CRASHED"
    assert env["detail"]["data"]["rpc"] == "unreachable"


# -- discovery -------------------------------------------------------------------------------


def test_discover_none_when_no_file(tmp_path):
    assert discover(appdata_dir=str(tmp_path)) is None


def test_discover_skips_dead_pid(tmp_path):
    # A child that has exited and been reaped has a pid no live process holds; a fixed small pid
    # does not work, because pid 2 is the always-alive kernel thread daemon on Linux.
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    disco = tmp_path / "freecad-buddy"
    disco.mkdir(parents=True)
    record = {"schema": 1, "pid": child.pid, "host": "127.0.0.1", "port": 1, "token": "t"}
    (disco / f"rpc-{child.pid}.json").write_text(json.dumps(record), encoding="utf-8")
    assert discover(appdata_dir=str(tmp_path)) is None


def test_call_no_listener_is_worker_crashed(tmp_path):
    client = RpcClient(appdata_dir=str(tmp_path))
    env = client.call("document_create", {})
    assert env["status"] == "WORKER_CRASHED"
    assert env["detail"]["data"]["rpc"] == "unreachable"


# -- never raises (loop-1 fix c) -------------------------------------------------------------


def _write_record(tmp_path, record):
    disco = tmp_path / "freecad-buddy"
    disco.mkdir(parents=True, exist_ok=True)
    (disco / f"rpc-{os.getpid()}.json").write_text(json.dumps(record), encoding="utf-8")


def test_missing_host_in_record_is_worker_crashed_no_raise(tmp_path):
    _write_record(tmp_path, {"schema": 1, "pid": os.getpid(), "port": 1234, "token": "t"})
    env = RpcClient(appdata_dir=str(tmp_path)).call("document_create", {})
    assert env["status"] == "WORKER_CRASHED"


def test_non_int_port_in_record_is_worker_crashed_no_raise(tmp_path):
    _write_record(
        tmp_path,
        {"schema": 1, "pid": os.getpid(), "host": "127.0.0.1", "port": "nope", "token": "t"},
    )
    env = RpcClient(appdata_dir=str(tmp_path)).call("document_create", {})
    assert env["status"] == "WORKER_CRASHED"


def test_garbage_after_handshake_is_envelope_not_raise(tmp_path):
    """A listener that accepts, completes the handshake, then sends a non-JSON line."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    host, port = sock.getsockname()
    _write_record(
        tmp_path, {"schema": 1, "pid": os.getpid(), "host": host, "port": port, "token": TOKEN}
    )

    def _serve():
        conn, _ = sock.accept()
        buf = b""
        while b"\n" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                conn.close()
                return
            buf += chunk
        # Reply to rpc_hello with a valid result, then send garbage on the next read.
        hello = {"jsonrpc": "2.0", "id": 1, "result": {"contract_version": "1"}}
        conn.sendall((json.dumps(hello) + "\n").encode())
        # Read the call frame then answer with a non-JSON line.
        buf = b""
        while b"\n" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
        conn.sendall(b"not json at all{{{\n")
        conn.close()

    server_thread = threading.Thread(target=_serve, daemon=True)
    server_thread.start()
    try:
        env = RpcClient(appdata_dir=str(tmp_path)).call("document_create", {})
        assert env["status"] in ("WORKER_CRASHED", "TIMEOUT")
    finally:
        sock.close()


def test_handshake_rejected_is_worker_crashed(tmp_path):
    """A listener that accepts then replies with a JSON-RPC error to the handshake."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    host, port = sock.getsockname()
    _write_record(
        tmp_path, {"schema": 1, "pid": os.getpid(), "host": host, "port": port, "token": TOKEN}
    )

    def _serve():
        conn, _ = sock.accept()
        buf = b""
        while b"\n" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                conn.close()
                return
            buf += chunk
        reject = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "auth"}}
        conn.sendall((json.dumps(reject) + "\n").encode())
        conn.close()

    threading.Thread(target=_serve, daemon=True).start()
    try:
        env = RpcClient(appdata_dir=str(tmp_path)).call("document_create", {})
        assert env["status"] == "WORKER_CRASHED"
        assert env["detail"]["data"]["rpc"] == "unreachable"
    finally:
        sock.close()


def test_should_log_one_warning_naming_the_method_when_the_connection_drops_in_flight(
    tmp_path, caplog
):
    # Arrange
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    host, port = sock.getsockname()

    def _serve():
        conn, _ = sock.accept()
        reader = conn.makefile("rb")
        reader.readline()
        hello = {"jsonrpc": "2.0", "id": 1, "result": {"contract_version": "1"}}
        conn.sendall((json.dumps(hello) + "\n").encode())
        reader.readline()
        reader.close()
        conn.close()

    server_thread = threading.Thread(target=_serve, daemon=True)
    server_thread.start()
    target = RpcClient(endpoint={"host": host, "port": port, "token": TOKEN})

    # Act
    with caplog.at_level(logging.INFO, logger="freecad_buddy.rpc_client"):
        envelope = target.call("document_create", {})
    sock.close()

    # Assert
    records = [r for r in caplog.records if r.name == "freecad_buddy.rpc_client"]
    assert envelope["status"] == "WORKER_CRASHED"
    assert envelope["detail"]["message"] == "listener connection dropped"
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert records[0].getMessage().startswith("listener connection dropped during document_create")
    assert records[0].exc_info is None


# -- pinned client (AD-2) ---------------------------------------------------------------------


def _handle_listener(handle: str, served: list[str], token: str = TOKEN):
    """A listener without a discovery file whose ``document_create`` answers ``handle``."""

    def _create(**params):
        served.append(handle)
        return {**_ok_envelope(), "structured_content": {"handle": handle}}

    registry = MethodRegistry()
    registry.register(RpcMethod(name="document_create", handler=_create, mutating=True))
    listener = RpcListener(
        registry, Marshal(ThreadedExecutor()), token, freecad_version="1.1.1", discovery=False
    )
    host, port = listener.start_threaded()
    return listener, {"schema": 1, "pid": 0, "host": host, "port": port, "token": token}


def _write_pid_record(tmp_path, record, mtime, name=None):
    disco = tmp_path / "freecad-buddy"
    disco.mkdir(parents=True, exist_ok=True)
    path = disco / (name or f"rpc-{record['pid']}.json")
    path.write_text(json.dumps(record), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def _pinned_then_newer_record(tmp_path, pinned_freecad):
    """Pin a client to listener A, then add a newer record for listener B and drop the link."""
    served: list[str] = []
    listener_a, record_a = _handle_listener("A", served)
    listener_b, record_b = _handle_listener("B", served)
    _write_pid_record(tmp_path, {**record_a, "pid": pinned_freecad.pid}, mtime=1_000_000)
    target = RpcClient(appdata_dir=str(tmp_path), pin=True)
    target.call("document_create", {})
    _write_pid_record(tmp_path, {**record_b, "pid": os.getpid()}, mtime=2_000_000)
    target.close()
    return target, served, (listener_a, listener_b)


def test_should_reconnect_only_to_the_pinned_record_when_a_newer_record_appears(tmp_path):
    # Arrange
    freecad = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    target, served, listeners = _pinned_then_newer_record(tmp_path, freecad)

    # Act
    try:
        envelope = target.call("document_create", {})
    finally:
        target.close()
        for listener in listeners:
            listener.stop()
        freecad.kill()
        freecad.wait()

    # Assert
    assert envelope["structured_content"]["handle"] == "A"
    assert served == ["A", "A"]
    assert target.pinned_record["pid"] == freecad.pid


def test_should_return_worker_crashed_and_not_adopt_when_the_pinned_pid_is_gone(tmp_path):
    # Arrange
    freecad = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    target, served, listeners = _pinned_then_newer_record(tmp_path, freecad)
    freecad.kill()
    freecad.wait()

    # Act
    try:
        envelope = target.call("document_create", {})
    finally:
        target.close()
        for listener in listeners:
            listener.stop()

    # Assert
    assert envelope["status"] == "WORKER_CRASHED"
    assert f"pid {freecad.pid}" in envelope["detail"]["message"]
    assert served == ["A"]


def test_should_not_connect_to_a_newer_record_with_the_pinned_pid_and_another_token(tmp_path):
    # Arrange
    freecad = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    served: list[str] = []
    listener_a, record_a = _handle_listener("A", served)
    listener_b, record_b = _handle_listener("B", served, token="restarted-session-token")
    _write_pid_record(tmp_path, {**record_a, "pid": freecad.pid}, mtime=1_000_000)
    target = RpcClient(appdata_dir=str(tmp_path), pin=True)
    target.call("document_create", {})
    _write_pid_record(
        tmp_path,
        {**record_b, "pid": freecad.pid},
        mtime=2_000_000,
        name=f"rpc-{freecad.pid}-restarted.json",
    )
    target.close()

    # Act
    try:
        envelope = target.call("document_create", {})
    finally:
        target.close()
        listener_a.stop()
        listener_b.stop()
        freecad.kill()
        freecad.wait()

    # Assert
    assert envelope["structured_content"]["handle"] == "A"
    assert served == ["A", "A"]
