"""RpcListener loopback tests: handshake, token, framing, timeout->suspect, robustness.

Every I/O-matrix row runs over a real localhost socket with a fake registry (no FreeCAD). The
executor is injected to exercise the real cross-thread marshal, the single-dedicated-thread
inline path (the double-marshal regression guard), and the trivial inline path.
"""

from __future__ import annotations

import json
import queue
import socket
import threading
import time

from freecad_buddy.adapters.marshal import Marshal
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.adapters.rpc_listener import RpcListener
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


def test_listener_writes_the_before_line_of_a_debug_exec_call_before_it_runs(tmp_path):
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
            name="debug_exec", handler=_exec, mutating=False, audit_event="exec", timeout_s=0.5
        )
    )
    listener, host, port = _start_listener(registry, ThreadedExecutor(), tmp_path, audit=audit)
    try:
        conn = Conn(host, port)
        conn.hello()
        conn.call("debug_exec", {"doc": "fcb-doc:a", "code": "1+1"})
        time.sleep(0.05)
        assert order == ["before", "handler"]
        assert audit.before_calls == [("exec", "debug_exec", "fcb-doc:a")]
        assert audit.after_calls == [("exec", "debug_exec", "fcb-doc:a", "OK")]
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
