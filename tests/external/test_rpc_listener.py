"""RpcListener loopback tests: handshake, token, framing, timeout->suspect, robustness.

Every I/O-matrix row runs over a real localhost socket with a fake registry (no FreeCAD). The
executor is injected to exercise the real cross-thread marshal, the single-dedicated-thread
inline path (the double-marshal regression guard), and the trivial inline path.
"""

from __future__ import annotations

import json
import logging
import queue
import socket
import struct
import sys
import threading
import time

from freecad_buddy.adapters import rpc_listener
from freecad_buddy.adapters.marshal import Marshal
from freecad_buddy.adapters.rpc_client import RpcClient
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.adapters.rpc_listener import RpcListener
from freecad_buddy.contracts.rpc import RPC_BUSY_MESSAGE
from freecad_buddy.hosts.tool_catalog import SCRIPT_EXEC_SPEC
from freecad_buddy.usecases import confirm
from freecad_buddy.usecases.documents import ValidationError

TOKEN = "test-token-value"


class ThreadedExecutor:
    """Runs each submitted callable on its own worker thread (real cross-thread marshal)."""

    def submit(self, fn):
        threading.Thread(target=fn, daemon=True).start()


class SingleThreadExecutor:
    """Runs submitted callables inline on ONE dedicated worker thread, FIFO.

    Mimics the Qt main thread: a second ``marshal.call`` on this thread would block waiting for
    work only this thread can run — a deadlock. Proves the listener registry is un-marshaled.
    """

    def __init__(self):
        self._q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while True:
            fn = self._q.get()
            if fn is None:
                return
            fn()

    def submit(self, fn):
        self._q.put(fn)


class BlockingExecutor:
    """Never runs the callable — forces a marshal timeout."""

    def submit(self, fn):
        pass


class RecordingAudit:
    def __init__(self):
        self.before_calls = []
        self.after_calls = []

    def before(self, event, tool, doc, params):
        self.before_calls.append((event, tool, doc))

    def after(self, event, tool, doc, params, verdict):
        self.after_calls.append((event, tool, doc, verdict))


def _ok_envelope(structured=None):
    structured = structured or {}
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": "{}",
    }


def _fake_registry():
    """Registry with UN-MARSHALED handlers returning OK envelopes directly."""
    reg = MethodRegistry()
    reg.register(
        RpcMethod(
            name="document_create",
            handler=lambda **p: _ok_envelope(),
            mutating=True,
            timeout_s=0.5,
        )
    )
    reg.register(
        RpcMethod(
            name="document_recompute",
            handler=lambda **p: _ok_envelope(),
            mutating=True,
            timeout_s=0.5,
        )
    )
    reg.register(
        RpcMethod(
            name="query_object",
            handler=lambda **p: _ok_envelope(),
            mutating=False,
            timeout_s=0.5,
        )
    )
    reg.register(
        RpcMethod(
            name="document_list",
            handler=lambda **p: _ok_envelope(),
            mutating=False,
            timeout_s=0.5,
        )
    )
    return reg


def _start_listener(registry, executor, tmp_path, *, audit=None):
    marshal = Marshal(executor)
    listener = RpcListener(
        registry,
        marshal,
        TOKEN,
        contract_version="1",
        freecad_version="1.1.1",
        capabilities={"gui": True},
        appdata_dir=str(tmp_path),
        audit=audit,
    )
    host, port = listener.start_threaded()
    return listener, host, port


class Conn:
    """Minimal NDJSON client for the tests."""

    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.settimeout(5)
        self.buf = bytearray()
        self._id = 0

    def send_raw(self, line: str):
        self.sock.sendall(line.encode("utf-8") + b"\n")

    def send(self, obj: dict):
        self.sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))

    def recv(self):
        while True:
            nl = self.buf.find(b"\n")
            if nl != -1:
                raw = bytes(self.buf[:nl])
                del self.buf[: nl + 1]
                return json.loads(raw.decode("utf-8"))
            chunk = self.sock.recv(65536)
            if not chunk:
                return None
            self.buf.extend(chunk)

    def recv_maybe_closed(self):
        try:
            return self.recv()
        except (OSError, json.JSONDecodeError):
            return None

    def hello(self, token=TOKEN, version="1"):
        self._id += 1
        self.send(
            {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "rpc_hello",
                "params": {"contract_version": version, "token": token},
            }
        )
        return self.recv()

    def call(self, method, params=None):
        self._id += 1
        self.send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})
        return self.recv()

    def close(self):
        self.sock.close()


# -- handshake matrix ------------------------------------------------------------------------


def test_handshake_ok_returns_hello_result(tmp_path):
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    try:
        conn = Conn(host, port)
        resp = conn.hello()
        assert "result" in resp
        assert resp["result"]["contract_version"] == "1"
        assert resp["result"]["freecad_version"] == "1.1.1"
        assert resp["result"]["capabilities"]["gui"] is True
        conn.close()
    finally:
        listener.stop()


def test_first_frame_not_hello_is_no_handshake_error(tmp_path):
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    try:
        conn = Conn(host, port)
        conn.send({"jsonrpc": "2.0", "id": 1, "method": "document_list", "params": {}})
        resp = conn.recv()
        assert resp["error"]["code"] == -32002
        assert conn.recv_maybe_closed() is None
        conn.close()
    finally:
        listener.stop()


def test_bad_token_is_auth_error(tmp_path):
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    try:
        conn = Conn(host, port)
        resp = conn.hello(token="wrong")
        assert resp["error"]["code"] == -32000
        assert conn.recv_maybe_closed() is None
        conn.close()
    finally:
        listener.stop()


def test_version_mismatch_lists_supported(tmp_path):
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    try:
        conn = Conn(host, port)
        resp = conn.hello(version="99")
        assert resp["error"]["code"] == -32004
        assert resp["error"]["data"]["supported"] == ["1"]
        conn.close()
    finally:
        listener.stop()


# -- normal dispatch -------------------------------------------------------------------------


def test_normal_tool_call_returns_ok_envelope(tmp_path):
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    try:
        conn = Conn(host, port)
        conn.hello()
        resp = conn.call("document_create", {"label": "x"})
        assert resp["result"]["status"] == "OK"
        conn.close()
    finally:
        listener.stop()


def test_unknown_method_is_invalid_input(tmp_path):
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    try:
        conn = Conn(host, port)
        conn.hello()
        resp = conn.call("no_such_method", {})
        assert resp["result"]["status"] == "INVALID_INPUT"
        conn.close()
    finally:
        listener.stop()


# -- double-marshal regression (loop-1 fix a) ------------------------------------------------


def test_mutating_call_on_single_thread_executor_returns_ok_not_timeout(tmp_path):
    """The registry is un-marshaled + the executor is one dedicated thread: no deadlock."""
    listener, host, port = _start_listener(_fake_registry(), SingleThreadExecutor(), tmp_path)
    try:
        conn = Conn(host, port)
        conn.hello()
        resp = conn.call("document_create", {"label": "x", "doc": "fcb-doc:a"})
        assert resp["result"]["status"] == "OK"
        conn.close()
    finally:
        listener.stop()


def test_double_marshaled_handler_on_single_thread_times_out(tmp_path):
    """If a handler ITSELF re-marshals on the same single thread, it deadlocks -> TIMEOUT.

    Locks in why the listener registry must be un-marshaled.
    """
    executor = SingleThreadExecutor()
    marshal = Marshal(executor)
    reg = MethodRegistry()

    def _self_marshaling(**p):
        # Second marshal.call on the one worker thread: the outer call already occupies it.
        return marshal.call(lambda: _ok_envelope(), 0.5)

    reg.register(RpcMethod(name="document_create", handler=_self_marshaling, mutating=True))
    listener = RpcListener(reg, marshal, TOKEN, appdata_dir=str(tmp_path))
    host, port = listener.start_threaded()
    try:
        conn = Conn(host, port)
        conn.hello()
        resp = conn.call("document_create", {"label": "x"})
        assert resp["result"]["status"] == "TIMEOUT"
        conn.close()
    finally:
        listener.stop()


# -- timeout -> suspect -> clear (loop-1 fix d) ----------------------------------------------


def test_marshal_timeout_returns_timeout_and_marks_suspect(tmp_path):
    listener, host, port = _start_listener(_fake_registry(), BlockingExecutor(), tmp_path)
    try:
        conn = Conn(host, port)
        conn.hello()
        # BlockingExecutor never runs the callable -> marshal.call times out.
        resp = conn.call("document_create", {"label": "x", "doc": "fcb-doc:a"})
        assert resp["result"]["status"] == "TIMEOUT"
        assert resp["result"]["detail"]["data"]["maybe_still_running"] is True
        # Next mutation on the same doc is refused.
        resp2 = conn.call("document_recompute", {"doc": "fcb-doc:a"})
        assert resp2["result"]["status"] == "INVALID_INPUT"
        assert "document-suspect" in resp2["result"]["detail"]["message"]
        conn.close()
    finally:
        listener.stop()


class TimeoutThenRunExecutor:
    """First submit blocks (timeout); afterwards runs callables on a dedicated thread."""

    def __init__(self):
        self._live = SingleThreadExecutor()
        self._first = True

    def submit(self, fn):
        if self._first:
            self._first = False
            return
        self._live.submit(fn)


def test_suspect_clears_only_on_read_of_same_handle(tmp_path):
    listener, host, port = _start_listener(_fake_registry(), TimeoutThenRunExecutor(), tmp_path)
    try:
        conn = Conn(host, port)
        conn.hello()
        # Timeout doc A (mutating) -> A suspect.
        resp = conn.call("document_create", {"label": "x", "doc": "fcb-doc:A"})
        assert resp["result"]["status"] == "TIMEOUT"
        # A successful read on doc B does NOT clear A.
        conn.call("query_object", {"doc": "fcb-doc:B", "object": "Box"})
        resp_a = conn.call("document_recompute", {"doc": "fcb-doc:A"})
        assert resp_a["result"]["status"] == "INVALID_INPUT"
        # A read on A clears A.
        conn.call("query_object", {"doc": "fcb-doc:A", "object": "Box"})
        resp_a2 = conn.call("document_recompute", {"doc": "fcb-doc:A"})
        assert resp_a2["result"]["status"] == "OK"
        conn.close()
    finally:
        listener.stop()


# -- malformed-frame isolation (loop-1 fix b) ------------------------------------------------


def test_non_dict_params_is_invalid_input_then_next_frame_served(tmp_path):
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    try:
        conn = Conn(host, port)
        conn.hello()
        conn.send({"jsonrpc": "2.0", "id": 1, "method": "document_create", "params": [1, 2]})
        resp = conn.recv()
        assert resp["result"]["status"] == "INVALID_INPUT"
        # The accept loop survived: a valid frame is still served.
        resp2 = conn.call("document_create", {"label": "x"})
        assert resp2["result"]["status"] == "OK"
        conn.close()
    finally:
        listener.stop()


def test_non_json_line_is_invalid_input_then_next_frame_served(tmp_path):
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    try:
        conn = Conn(host, port)
        conn.hello()
        conn.send_raw("this is not json{{{")
        resp = conn.recv()
        assert resp["result"]["status"] == "INVALID_INPUT"
        resp2 = conn.call("document_create", {"label": "x"})
        assert resp2["result"]["status"] == "OK"
        conn.close()
    finally:
        listener.stop()


def test_unhashable_doc_is_invalid_input_then_next_frame_served(tmp_path):
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    try:
        conn = Conn(host, port)
        conn.hello()
        conn.send(
            {"jsonrpc": "2.0", "id": 1, "method": "document_create", "params": {"doc": ["x"]}}
        )
        resp = conn.recv()
        assert resp["result"]["status"] == "INVALID_INPUT"
        resp2 = conn.call("document_create", {"label": "x"})
        assert resp2["result"]["status"] == "OK"
        conn.close()
    finally:
        listener.stop()


# -- audit (loop-1 fix) ----------------------------------------------------------------------


def test_listener_audits_mutating_calls(tmp_path):
    audit = RecordingAudit()
    listener, host, port = _start_listener(
        _fake_registry(), ThreadedExecutor(), tmp_path, audit=audit
    )
    try:
        conn = Conn(host, port)
        conn.hello()
        conn.call("document_create", {"label": "x", "doc": "fcb-doc:a"})
        conn.call("query_object", {"doc": "fcb-doc:a", "object": "Box"})
        time.sleep(0.05)
        assert audit.before_calls == [("mutation", "document_create", "fcb-doc:a")]
        assert audit.after_calls == [("mutation", "document_create", "fcb-doc:a", "OK")]
        conn.close()
    finally:
        listener.stop()


def test_listener_installs_its_audit_sink_as_the_sink_run_mutation_writes_through(tmp_path):
    audit = RecordingAudit()
    previous = confirm.set_approval_sink(None)
    listener, _, _ = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path, audit=audit)
    try:
        assert confirm.host_audit_sink() is audit
    finally:
        listener.stop()
        confirm.set_approval_sink(previous)


def test_listener_leaves_a_bracketed_mutation_to_write_its_own_audit_lines(tmp_path):
    audit = RecordingAudit()
    registry = MethodRegistry()
    registry.register(
        RpcMethod(
            name="feature_pad",
            handler=lambda **p: _ok_envelope({"mutation": {"schema": "fcb.mutation/2"}}),
            mutating=True,
            timeout_s=0.5,
        )
    )
    listener, host, port = _start_listener(registry, ThreadedExecutor(), tmp_path, audit=audit)
    try:
        conn = Conn(host, port)
        conn.hello()
        conn.call("feature_pad", {"doc": "fcb-doc:a"})
        time.sleep(0.05)
        assert audit.before_calls == []
        assert audit.after_calls == []
        conn.close()
    finally:
        listener.stop()


def test_listener_writes_the_before_line_of_a_refused_call_after_it_ran(tmp_path):
    audit = RecordingAudit()
    order = []
    audit_before = audit.before

    def _record_before(*args):
        order.append("before")
        audit_before(*args)

    audit.before = _record_before

    def _refuse(**_params):
        order.append("handler")
        raise ValidationError("precheck refused the pad")

    registry = MethodRegistry()
    registry.register(RpcMethod(name="feature_pad", handler=_refuse, mutating=True, timeout_s=0.5))
    listener, host, port = _start_listener(registry, ThreadedExecutor(), tmp_path, audit=audit)
    try:
        conn = Conn(host, port)
        conn.hello()
        response = conn.call("feature_pad", {"doc": "fcb-doc:a"})
        time.sleep(0.05)
        assert response["result"]["status"] == "INVALID_INPUT"
        assert order == ["handler", "before"]
        assert audit.after_calls == [("mutation", "feature_pad", "fcb-doc:a", "INVALID_INPUT")]
        conn.close()
    finally:
        listener.stop()


def test_listener_writes_the_before_line_of_a_script_exec_call_before_it_runs(tmp_path):
    audit = RecordingAudit()
    order = []
    audit_before = audit.before

    def _record_before(*args):
        order.append("before")
        audit_before(*args)

    audit.before = _record_before

    def _exec(**_params):
        order.append("handler")
        return _ok_envelope()

    registry = MethodRegistry()
    registry.register(
        RpcMethod(
            name=SCRIPT_EXEC_SPEC.name,
            handler=_exec,
            mutating=SCRIPT_EXEC_SPEC.mutating,
            audit_event=SCRIPT_EXEC_SPEC.audit_event,
            timeout_s=SCRIPT_EXEC_SPEC.timeout_s,
        )
    )
    listener, host, port = _start_listener(registry, ThreadedExecutor(), tmp_path, audit=audit)
    try:
        conn = Conn(host, port)
        conn.hello()
        conn.call("script_exec", {"doc": "fcb-doc:a", "code": "1+1"})
        time.sleep(0.05)
        assert order == ["before", "handler"]
        assert audit.before_calls == [("exec", "script_exec", "fcb-doc:a")]
        assert audit.after_calls == [("exec", "script_exec", "fcb-doc:a", "OK")]
        conn.close()
    finally:
        listener.stop()


# -- discovery -------------------------------------------------------------------------------


def test_discovery_file_written_0600_and_deleted_on_stop(tmp_path):
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    disco_dir = tmp_path / "freecad-buddy"
    files = list(disco_dir.glob("rpc-*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8"))
    assert record["host"] == host
    assert record["port"] == port
    assert record["token"] == TOKEN
    listener.stop()
    assert list(disco_dir.glob("rpc-*.json")) == []


# -- connection-end logging ------------------------------------------------------------------

_LISTENER_LOGGER = "freecad_buddy.rpc_listener"


def _listener_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == _LISTENER_LOGGER]


_BUSY_LOG = "refused a second client: a session is active"


def _after_handler_returned(caplog, host, port) -> list[logging.LogRecord]:
    """The listener's records once it has finished the previous connection.

    A probe's hello is accepted only after the previous session's serving loop has returned and
    written its log line; a busy refusal means it has not yet, so the probe tries again. The
    probes' own lines are cut off.
    """
    deadline = time.monotonic() + 5.0
    while True:
        probe = Conn(host, port)
        accepted = "result" in probe.hello()
        records = [r for r in _listener_records(caplog) if r.getMessage() != _BUSY_LOG]
        probe.close()
        if accepted:
            return records
        assert time.monotonic() < deadline, "the previous session never ended"


def _reset(sock: socket.socket) -> None:
    """Close with a TCP reset, as a client process that exits without a clean shutdown does."""
    linger = struct.pack("HH" if sys.platform == "win32" else "ii", 1, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
    sock.close()


def _slow_registry(seconds: float, started: threading.Event) -> MethodRegistry:
    def slow(**_params):
        started.set()
        time.sleep(seconds)
        return _ok_envelope()

    registry = MethodRegistry()
    registry.register(RpcMethod(name="slow_read", handler=slow, timeout_s=5.0))
    return registry


def test_should_log_one_warning_without_traceback_when_the_first_frame_is_not_json(
    tmp_path, caplog
):
    # Arrange
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    conn = Conn(host, port)

    # Act
    with caplog.at_level(logging.INFO, logger=_LISTENER_LOGGER):
        conn.send_raw("not json at all{{{")
        response = conn.recv()
        conn.close()
        records = _after_handler_returned(caplog, host, port)
    listener.stop()

    # Assert
    assert response["error"]["code"] == -32002
    assert [(r.levelno, r.getMessage()) for r in records] == [
        (logging.WARNING, "first frame was not valid JSON; closing")
    ]
    assert all(r.exc_info is None for r in records)


def test_should_log_one_info_line_without_traceback_when_the_client_resets_its_connection(
    tmp_path, caplog
):
    # Arrange
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    conn = Conn(host, port)
    conn.hello()

    # Act
    with caplog.at_level(logging.INFO, logger=_LISTENER_LOGGER):
        _reset(conn.sock)
        records = _after_handler_returned(caplog, host, port)
    listener.stop()

    # Assert
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert records[0].getMessage().startswith("client reset the connection")
    assert records[0].exc_info is None


def test_should_log_one_info_line_when_the_client_closes_its_connection_cleanly(tmp_path, caplog):
    # Arrange
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    conn = Conn(host, port)
    conn.hello()

    # Act
    with caplog.at_level(logging.INFO, logger=_LISTENER_LOGGER):
        conn.sock.shutdown(socket.SHUT_RDWR)
        conn.close()
        records = _after_handler_returned(caplog, host, port)
    listener.stop()

    # Assert
    assert [(r.levelno, r.getMessage(), r.exc_info) for r in records] == [
        (logging.INFO, "client closed the connection", None)
    ]


def test_should_log_one_warning_without_traceback_when_a_frame_is_cut_off(tmp_path, caplog):
    # Arrange
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    conn = Conn(host, port)
    conn.hello()

    # Act
    with caplog.at_level(logging.INFO, logger=_LISTENER_LOGGER):
        conn.sock.sendall(b'{"jsonrpc": "2.0", "id": 2, "method": "document_list"')
        conn.sock.shutdown(socket.SHUT_WR)
        conn.close()
        records = _after_handler_returned(caplog, host, port)
    listener.stop()

    # Assert
    assert [(r.levelno, r.getMessage(), r.exc_info) for r in records] == [
        (
            logging.WARNING,
            "frame read failed; closing connection: connection closed mid-frame",
            None,
        )
    ]


def test_should_log_one_warning_without_traceback_when_a_frame_is_not_utf8(tmp_path, caplog):
    # Arrange
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    conn = Conn(host, port)
    conn.hello()

    # Act
    with caplog.at_level(logging.INFO, logger=_LISTENER_LOGGER):
        conn.sock.sendall(b"\xff\xfe\n")
        closed = conn.recv_maybe_closed()
        conn.close()
        records = _after_handler_returned(caplog, host, port)
    listener.stop()

    # Assert
    assert closed is None
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert records[0].getMessage().startswith("frame read failed; closing connection:")
    assert records[0].exc_info is None


def test_should_log_one_warning_and_end_the_connection_when_the_client_goes_before_the_reply(
    tmp_path, caplog
):
    # Arrange
    started = threading.Event()
    listener, host, port = _start_listener(
        _slow_registry(0.5, started), ThreadedExecutor(), tmp_path
    )
    conn = Conn(host, port)
    conn.hello()

    # Act
    with caplog.at_level(logging.INFO, logger=_LISTENER_LOGGER):
        conn.send({"jsonrpc": "2.0", "id": 2, "method": "slow_read", "params": {}})
        # Windows drops received bytes on a reset, so reset only once the call is being served.
        started.wait(5)
        _reset(conn.sock)
        records = _after_handler_returned(caplog, host, port)
    listener.stop()

    # Assert
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert records[0].getMessage().startswith("could not send the reply; the client has gone")
    assert records[0].exc_info is None


# -- one client session at a time (AD-26) ----------------------------------------------------


def test_should_refuse_a_second_client_as_busy_within_a_second_when_a_session_is_active(
    tmp_path,
):
    # Arrange
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    session = Conn(host, port)
    session.hello()
    second = Conn(host, port)

    # Act
    started = time.monotonic()
    refusal = second.hello()
    elapsed_s = time.monotonic() - started
    closed = second.recv_maybe_closed()
    served = session.call("document_list")
    second.close()
    session.close()
    listener.stop()

    # Assert
    assert refusal["error"] == {"code": -32000, "message": RPC_BUSY_MESSAGE}
    assert elapsed_s < 1.0
    assert closed is None
    assert served["result"]["status"] == "OK"


def test_should_refuse_as_auth_failed_when_a_second_client_has_a_bad_token_during_a_session(
    tmp_path,
):
    # Arrange
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    session = Conn(host, port)
    session.hello()
    second = Conn(host, port)

    # Act
    refusal = second.hello(token="wrong")
    second.close()
    session.close()
    listener.stop()

    # Assert
    assert refusal["error"] == {"code": -32000, "message": "auth failed"}


def test_should_accept_the_next_client_when_the_session_has_ended(tmp_path):
    # Arrange
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    first = Conn(host, port)
    first.hello()
    first.close()
    second = Conn(host, port)

    # Act
    accepted = second.hello()
    served = second.call("document_list")
    second.close()
    listener.stop()

    # Assert
    assert "result" in accepted
    assert served["result"]["status"] == "OK"


def test_should_close_a_silent_connection_and_serve_others_when_the_hello_deadline_passes(
    tmp_path, caplog, monkeypatch
):
    # Arrange
    monkeypatch.setattr(rpc_listener, "_HELLO_TIMEOUT_S", 0.3)
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    silent = Conn(host, port)
    other = Conn(host, port)

    # Act
    with caplog.at_level(logging.INFO, logger=_LISTENER_LOGGER):
        accepted = other.hello()
        closed = silent.recv_maybe_closed()
        records = _listener_records(caplog)
    other.close()
    silent.close()
    listener.stop()

    # Assert
    assert "result" in accepted
    assert closed is None
    assert [(r.levelno, r.getMessage(), r.exc_info) for r in records] == [
        (logging.WARNING, "no rpc_hello within 0.3 s; closing", None)
    ]


def test_should_return_worker_crashed_naming_the_busy_bridge_when_the_client_hello_is_refused(
    tmp_path,
):
    # Arrange
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    session = Conn(host, port)
    session.hello()
    target = RpcClient(endpoint={"host": host, "port": port, "token": TOKEN})

    # Act
    envelope = target.call("document_list", {})
    target.close()
    session.close()
    listener.stop()

    # Assert
    assert envelope["status"] == "WORKER_CRASHED"
    assert envelope["detail"]["message"] == RPC_BUSY_MESSAGE
    assert envelope["detail"]["data"] == {}


def test_should_refuse_as_version_mismatch_when_a_second_client_sends_a_wrong_version(
    tmp_path,
):
    # Arrange
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    session = Conn(host, port)
    session.hello()
    second = Conn(host, port)

    # Act
    refusal = second.hello(version="99")
    second.close()
    session.close()
    listener.stop()

    # Assert
    assert refusal["error"]["code"] == -32004
    assert refusal["error"]["message"] == "contract version unsupported"


def test_should_serve_a_session_idle_past_the_hello_deadline(tmp_path, caplog, monkeypatch):
    # Arrange
    monkeypatch.setattr(rpc_listener, "_HELLO_TIMEOUT_S", 0.3)
    listener, host, port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    session = Conn(host, port)
    session.hello()

    # Act
    with caplog.at_level(logging.INFO, logger=_LISTENER_LOGGER):
        time.sleep(0.6)
        served = session.call("document_list")
        records = _listener_records(caplog)
    session.close()
    listener.stop()

    # Assert
    assert served["result"]["status"] == "OK"
    assert not [r for r in records if r.getMessage().startswith("no rpc_hello")]


def test_should_accept_a_client_that_arrives_while_the_closed_session_finishes_its_last_call(
    tmp_path,
):
    # Arrange
    started = threading.Event()
    listener, host, port = _start_listener(
        _slow_registry(0.05, started), ThreadedExecutor(), tmp_path
    )
    first = Conn(host, port)
    first.hello()
    first.send({"jsonrpc": "2.0", "id": 2, "method": "slow_read", "params": {}})
    started.wait(5)
    first.close()
    second = Conn(host, port)

    # Act
    accepted = second.hello()
    second.close()
    listener.stop()

    # Assert
    assert "result" in accepted


def test_should_end_the_idle_serving_thread_when_stop_runs(tmp_path):
    # Arrange
    listener, _host, _port = _start_listener(_fake_registry(), ThreadedExecutor(), tmp_path)
    serving = listener._thread

    # Act
    listener.stop()
    serving.join(timeout=5)

    # Assert
    assert not serving.is_alive()
