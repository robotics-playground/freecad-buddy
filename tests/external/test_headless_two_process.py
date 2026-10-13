"""Two-process headless host: the front's RPC hop to the worker, its lifecycle, and its imports.

The listener, client, shutdown, bound and quarantine cases run without FreeCAD over a real
localhost socket and real child processes. The end-to-end cases and the import probes need an
interpreter that can ``import FreeCAD`` (the fcb env) and skip elsewhere.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from mcp import types

from freecad_buddy.adapters.audit_log import AuditSink
from freecad_buddy.adapters.marshal import InlineExecutor, Marshal
from freecad_buddy.adapters.mcp_server import Capabilities, build_server
from freecad_buddy.adapters.rpc_client import RpcClient
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.adapters.rpc_listener import RpcListener
from freecad_buddy.contracts import DEFAULT_DISPLAY_DECIMALS
from freecad_buddy.contracts.rpc import RPC_BUSY_MESSAGE
from freecad_buddy.hosts.headless.entry import WorkerClient, shut_down_worker
from freecad_buddy.hosts.rpc_proxy import build_proxy_registry, call_budgets
from freecad_buddy.hosts.tool_catalog import SCRIPT_EXEC_SPEC
from freecad_buddy.usecases import shim

TOKEN = "two-process-test-token"
FREECAD_IMPORTABLE = importlib.util.find_spec("FreeCAD") is not None
needs_freecad = pytest.mark.skipif(
    not FREECAD_IMPORTABLE, reason="needs an interpreter that can import FreeCAD"
)
SERVE_ARGS = ["-m", "freecad_buddy.hosts.main", "serve", "--transport", "stdio", "--mode", "inline"]


def _ok_envelope() -> dict:
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": {"answer": 42},
        "text": "answer: 42",
    }


def _registry() -> MethodRegistry:
    registry = MethodRegistry()
    registry.register(RpcMethod(name="query_object", handler=lambda **_params: _ok_envelope()))
    return registry


def _serve_inline(listener: RpcListener) -> tuple[dict, threading.Thread]:
    host, port = listener.bind()
    thread = threading.Thread(target=listener.serve_forever_inline, daemon=True)
    thread.start()
    return {"host": host, "port": port, "token": TOKEN}, thread


class _RecordingClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.closed = False

    def call(self, method: str, params: dict | None = None) -> dict:
        self.calls.append(method)
        return _ok_envelope()

    def close(self) -> None:
        self.closed = True


class _ExitedProcess:
    def poll(self) -> int:
        return 3


# -- listener and client ---------------------------------------------------------------------


def test_should_serve_an_endpoint_client_and_write_no_discovery_file_when_discovery_is_off(
    tmp_path,
):
    # Arrange
    listener = RpcListener(
        _registry(),
        Marshal(InlineExecutor()),
        TOKEN,
        appdata_dir=tmp_path,
        discovery=False,
    )
    endpoint, thread = _serve_inline(listener)
    target = RpcClient(endpoint=endpoint, read_timeout_s=None)

    # Act
    envelope = target.call("query_object", {})
    target.close()
    listener.stop()
    thread.join(timeout=5)

    # Assert
    assert envelope["status"] == "OK"
    assert envelope["structured_content"] == {"answer": 42}
    assert list(tmp_path.rglob("*")) == []
    assert not thread.is_alive()


def test_should_end_the_serving_thread_when_stop_runs_while_it_waits_in_accept(tmp_path):
    # Arrange
    listener = RpcListener(
        _registry(), Marshal(InlineExecutor()), TOKEN, appdata_dir=tmp_path, discovery=False
    )
    _endpoint, thread = _serve_inline(listener)
    time.sleep(0.5)

    # Act
    listener.stop()
    thread.join(timeout=5)

    # Assert
    assert not thread.is_alive()


def test_should_refuse_the_call_when_the_endpoint_token_is_wrong(tmp_path):
    # Arrange
    listener = RpcListener(
        _registry(), Marshal(InlineExecutor()), TOKEN, appdata_dir=tmp_path, discovery=False
    )
    endpoint, thread = _serve_inline(listener)
    target = RpcClient(endpoint={**endpoint, "token": "wrong-token"})

    # Act
    envelope = target.call("query_object", {})
    listener.stop()
    thread.join(timeout=5)

    # Assert
    assert envelope["status"] == "WORKER_CRASHED"
    assert envelope["detail"]["message"] == "handshake rejected"


def test_should_return_the_restart_message_without_rpc_when_the_worker_has_exited():
    # Arrange
    client = _RecordingClient()
    target = WorkerClient(client, _ExitedProcess(), {"query_object": 30.0})

    # Act
    envelope = target.call("query_object", {})

    # Assert
    assert envelope["status"] == "WORKER_CRASHED"
    assert envelope["detail"]["message"] == (
        "headless worker exited with code 3; restart the headless host"
    )
    assert client.calls == []


_IMPORTABLE_FREECAD_STUB = """
class _Group:
    def GetBool(self, name, default):
        return True

    def GetInt(self, name, default):
        return 7


def ParamGet(path):
    return _Group()
"""


def test_should_return_the_default_precision_and_not_load_freecad_when_freecad_is_not_loaded(
    monkeypatch, tmp_path
):
    # Arrange
    (tmp_path / "FreeCAD.py").write_text(_IMPORTABLE_FREECAD_STUB, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "FreeCAD", raising=False)

    # Act
    decimals = shim.display_decimals()

    # Assert
    assert decimals == DEFAULT_DISPLAY_DECIMALS
    assert "FreeCAD" not in sys.modules


# -- shutdown --------------------------------------------------------------------------------


def _stub_worker(code: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE)


def test_should_return_zero_when_the_worker_exits_on_stdin_eof(caplog):
    # Arrange
    worker = _stub_worker("import sys; sys.stdin.read()")
    client = _RecordingClient()

    # Act
    with caplog.at_level(logging.INFO, logger="freecad_buddy.hosts.headless"):
        code = shut_down_worker(worker, client, grace_s=10.0)

    # Assert
    assert code == 0
    assert client.closed
    assert worker.returncode == 0
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


def test_should_end_the_worker_and_return_one_when_it_ignores_stdin_eof(caplog):
    # Arrange
    worker = _stub_worker("import time; time.sleep(60)")
    client = _RecordingClient()

    # Act
    with caplog.at_level(logging.INFO, logger="freecad_buddy.hosts.headless"):
        code = shut_down_worker(worker, client, grace_s=0.5)

    # Assert
    assert code == 1
    assert worker.poll() is not None
    assert len([r for r in caplog.records if r.levelno >= logging.ERROR]) == 1


def test_should_return_one_with_one_error_log_when_the_worker_exits_with_a_non_zero_code(caplog):
    # Arrange
    worker = _stub_worker("import sys; sys.stdin.read(); sys.exit(3)")
    client = _RecordingClient()

    # Act
    with caplog.at_level(logging.INFO, logger="freecad_buddy.hosts.headless"):
        code = shut_down_worker(worker, client, grace_s=10.0)

    # Assert
    assert code == 1
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert "code 3" in errors[0].getMessage()


@pytest.mark.skipif(FREECAD_IMPORTABLE, reason="this interpreter can import FreeCAD")
def test_should_exit_two_with_the_worker_message_when_freecad_cannot_be_imported():
    # Arrange
    command = [sys.executable, *SERVE_ARGS]

    # Act
    result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)

    # Assert
    assert result.returncode == 2
    assert b"headless host requires `import FreeCAD`" in result.stderr
    assert result.stdout == b""


# -- bound and quarantine --------------------------------------------------------------------

# A listener on its process main thread, as in the worker. Each body holds the GIL in C for the
# `seconds` it is given, so only a separate process can bound it.
_GIL_WORKER = """
import json, re, sys, threading, time
from freecad_buddy.adapters.marshal import InlineExecutor, Marshal
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.adapters.rpc_listener import RpcListener

token, served_path = sys.argv[1], sys.argv[2]


def record(line):
    with open(served_path, "a", encoding="utf-8") as served:
        served.write(line + "\\n")


def hold_gil(seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        # A catastrophic backtrack: the regex engine keeps the GIL for the whole match.
        re.match(r"(a+)+$", "a" * 20 + "b")


def handler(name):
    def run(seconds=0.0, **_params):
        record(name)
        hold_gil(seconds)
        record(name + " returned")
        return {"schema": "fcb.result-envelope/1", "status": "OK", "detail": None,
                "structured_content": {}, "text": "{}"}
    return run


def stop_on_stdin_eof(listener):
    sys.stdin.read()
    listener.stop()


registry = MethodRegistry()
for name in ("read", "slow_read", "slow_mutate"):
    registry.register(RpcMethod(name=name, handler=handler(name)))
listener = RpcListener(registry, Marshal(InlineExecutor()), token, discovery=False)
_host, port = listener.bind()
print(json.dumps({"port": port}), flush=True)
threading.Thread(target=stop_on_stdin_eof, args=(listener,), daemon=True).start()
listener.serve_forever_inline()
"""

BUDGET_S = 0.5
BUDGETS = {"read": 5.0, "slow_read": BUDGET_S, "slow_mutate": BUDGET_S}
DOC = "fcb-doc:1"


@pytest.fixture
def gil_worker(tmp_path):
    """A ``WorkerClient`` on a GIL-holding stub worker, and the file the worker logs bodies to."""
    served = tmp_path / "served.log"
    served.touch()
    process = subprocess.Popen(
        [sys.executable, "-c", _GIL_WORKER, TOKEN, str(served)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    port = json.loads(process.stdout.readline())["port"]
    rpc = RpcClient(
        endpoint={"host": "127.0.0.1", "port": port, "token": TOKEN}, read_timeout_s=None
    )
    client = WorkerClient(rpc, process, BUDGETS)
    yield client, served
    shut_down_worker(process, client, grace_s=10.0)


def _served(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _wait_until_returned(client: WorkerClient, path: Path, name: str) -> None:
    """Wait until the worker logs that ``name`` returned, then for its answer to the probe."""
    deadline = time.monotonic() + 15.0
    while f"{name} returned" not in _served(path):
        if time.monotonic() > deadline:
            pytest.fail(f"the worker never returned from {name}")
        time.sleep(0.05)
    while not client._client.reconnect_answered():
        if time.monotonic() > deadline:
            pytest.fail(f"the worker returned from {name} but never answered the probe")
        time.sleep(0.05)


def _forward(client: WorkerClient, name: str):
    return lambda **params: client.call(name, params)


def _front_server(client: WorkerClient, audit_path: Path):
    methods = MethodRegistry()
    for name, mutating in (("read", False), ("slow_read", False), ("slow_mutate", True)):
        methods.register(RpcMethod(name=name, handler=_forward(client, name), mutating=mutating))
    return build_server(methods, Capabilities(script_exec=False), AuditSink(audit_path))


def _call_tool(server, name: str, arguments: dict) -> dict:
    handler = server.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name=name, arguments=arguments),
    )
    return asyncio.run(handler(request)).root.structuredContent


def _timed(fn):
    started = time.monotonic()
    result = fn()
    return result, time.monotonic() - started


def test_should_give_each_forwarded_method_a_budget_when_the_budgets_are_built():
    # Arrange
    registry = build_proxy_registry(_RecordingClient(), Capabilities(script_exec=True))
    self_read_legs = ["export_self_read_stl", "export_self_read_3mf"]

    # Act
    budgets = call_budgets()

    # Assert
    assert set(registry.names()) | set(self_read_legs) <= set(budgets)
    assert budgets["export_self_read_stl"] == budgets["verify_export_stl"]
    assert budgets["export_self_read_3mf"] == budgets["verify_export_3mf"]


def test_should_return_the_worker_envelope_when_the_body_ends_within_its_budget(gil_worker):
    # Arrange
    target, served = gil_worker
    params = {"doc": DOC, "seconds": 0.1}

    # Act
    envelope = target.call("slow_read", params)

    # Assert
    assert envelope["status"] == "OK"
    assert _served(served) == ["slow_read", "slow_read returned"]


def test_should_time_out_within_a_second_of_the_budget_when_a_body_holds_the_gil(gil_worker):
    # Arrange
    target, _served_path = gil_worker
    params = {"doc": DOC, "seconds": 3.0}

    # Act
    envelope, elapsed_s = _timed(lambda: target.call("slow_read", params))

    # Assert
    assert envelope["status"] == "TIMEOUT"
    assert envelope["detail"]["data"] == {"marshal_timeout": True, "maybe_still_running": True}
    assert BUDGET_S <= elapsed_s < BUDGET_S + 1.0


def test_should_time_out_without_marking_the_doc_suspect_when_a_read_overruns(gil_worker, tmp_path):
    # Arrange
    client, served = gil_worker
    target = _front_server(client, tmp_path / "audit.jsonl")

    # Act
    timed_out = _call_tool(target, "slow_read", {"doc": DOC, "seconds": 1.5})
    _wait_until_returned(client, served, "slow_read")
    mutated = _call_tool(target, "slow_mutate", {"doc": DOC})

    # Assert
    assert timed_out["status"] == "TIMEOUT"
    assert timed_out["detail"]["data"]["marshal_timeout"] is True
    assert timed_out["detail"]["data"]["maybe_still_running"] is True
    assert "no mutation was attempted" in timed_out["detail"]["message"]
    assert mutated["status"] == "OK"


def test_should_refuse_mutations_until_a_read_clears_the_doc_when_a_mutation_overruns(
    gil_worker, tmp_path
):
    # Arrange
    client, served = gil_worker
    target = _front_server(client, tmp_path / "audit.jsonl")

    # Act
    timed_out = _call_tool(target, "slow_mutate", {"doc": DOC, "seconds": 1.5})
    _wait_until_returned(client, served, "slow_mutate")
    refused = _call_tool(target, "slow_mutate", {"doc": DOC})
    read = _call_tool(target, "read", {"doc": DOC})
    mutated = _call_tool(target, "slow_mutate", {"doc": DOC})

    # Assert
    assert timed_out["status"] == "TIMEOUT"
    assert "the document is now suspect" in timed_out["detail"]["message"]
    assert refused["status"] == "INVALID_INPUT"
    assert "document-suspect" in refused["detail"]["message"]
    assert read["status"] == "OK"
    assert mutated["status"] == "OK"
    assert _served(served) == [
        "slow_mutate",
        "slow_mutate returned",
        "read",
        "read returned",
        "slow_mutate",
        "slow_mutate returned",
    ]


def test_should_refuse_at_once_without_dispatch_when_an_abandoned_body_runs(gil_worker):
    # Arrange
    target, served = gil_worker
    target.call("slow_read", {"doc": DOC, "seconds": 2.0})

    # Act
    same_doc, same_doc_s = _timed(lambda: target.call("read", {"doc": DOC}))
    other_doc, other_doc_s = _timed(lambda: target.call("slow_mutate", {"doc": "fcb-doc:2"}))

    # Assert
    for refusal, elapsed_s in ((same_doc, same_doc_s), (other_doc, other_doc_s)):
        assert refusal["status"] == "TIMEOUT"
        assert refusal["detail"]["data"] == {"quarantined": True}
        assert "not dispatched" in refusal["detail"]["message"]
        assert elapsed_s < 0.5
    assert _served(served) == ["slow_read"]


def test_should_serve_the_next_call_when_the_abandoned_body_has_returned(gil_worker):
    # Arrange
    target, served = gil_worker
    target.call("slow_read", {"doc": DOC, "seconds": 1.5})
    _wait_until_returned(target, served, "slow_read")

    # Act
    envelope = target.call("read", {"doc": DOC})

    # Assert
    assert envelope["status"] == "OK"
    assert _served(served) == ["slow_read", "slow_read returned", "read", "read returned"]


def test_should_answer_busy_while_the_abandoned_body_runs_and_lift_the_quarantine_after_it_returns(
    gil_worker,
):
    # Arrange
    front, served = gil_worker
    # Two busy answers (0.2 s grace each) and the probe's 0.1 s re-ask wait take at least 0.5 s
    # before the refusal; a 1.5 s budget keeps that refusal short of the 2x escalation.
    target = WorkerClient(front._client, front._process, {**BUDGETS, "slow_read": 1.5})
    target.call("slow_read", {"doc": DOC, "seconds": 4.0})
    second = RpcClient(endpoint=front._client._endpoint)

    # Act
    busy = second.call("read", {"doc": DOC})
    # The front's own probe has had its busy answer by now, so this refusal follows from it.
    quarantined = target.call("read", {"doc": DOC})
    _wait_until_returned(target, served, "slow_read")
    after_return = target.call("read", {"doc": DOC})
    second.close()

    # Assert
    assert busy["status"] == "WORKER_CRASHED"
    assert busy["detail"]["message"] == RPC_BUSY_MESSAGE
    assert quarantined["status"] == "TIMEOUT"
    assert quarantined["detail"]["data"] == {"quarantined": True}
    assert "not dispatched" in quarantined["detail"]["message"]
    assert after_return["status"] == "OK"
    assert _served(served) == ["slow_read", "slow_read returned", "read", "read returned"]


def test_should_tell_the_operator_to_restart_the_host_when_the_body_runs_past_twice_its_budget(
    gil_worker,
):
    # Arrange
    target, served = gil_worker
    target.call("slow_read", {"doc": DOC, "seconds": 3.0})
    time.sleep(BUDGET_S + 0.2)

    # Act
    escalated, escalated_s = _timed(lambda: target.call("read", {"doc": DOC}))
    _wait_until_returned(target, served, "slow_read")
    after_return = target.call("read", {"doc": DOC})

    # Assert
    assert escalated["status"] == "WORKER_CRASHED"
    assert escalated["detail"]["data"] == {"quarantined": True}
    assert "restart the headless host" in escalated["detail"]["message"]
    assert escalated_s < 0.5
    assert after_return["status"] == "OK"
    assert _served(served) == ["slow_read", "slow_read returned", "read", "read returned"]


# -- end to end (FreeCAD) --------------------------------------------------------------------


def _child_env(tmp_path: Path) -> dict:
    env = dict(os.environ)
    env.pop("FREECAD_BUDDY_UNATTENDED", None)
    env["FREECAD_BUDDY_SCRIPT_EXEC"] = "1"
    env["FREECAD_BUDDY_AUDIT_LOG"] = str(tmp_path / "audit.jsonl")
    return env


class _StdioSession:
    """Newline-delimited JSON-RPC over the host's stdin and stdout."""

    def __init__(self, process: subprocess.Popen) -> None:
        self._process = process
        self._next_id = 0

    def notify(self, method: str, params: dict | None = None) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def request(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        self._write(
            {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params or {}}
        )
        while True:
            line = self._process.stdout.readline()
            if not line:
                pytest.fail(f"the host closed stdout before it answered {method}; see stderr.log")
            message = json.loads(line)
            if message.get("id") == self._next_id:
                return message["result"]

    def _write(self, message: dict) -> None:
        self._process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        self._process.stdin.flush()


def _in_process_tool_names(env: dict) -> list[str]:
    from freecad_buddy.adapters.mcp_server import Capabilities, registered_tools
    from freecad_buddy.hosts.headless.worker import build_registry
    from freecad_buddy.usecases import confirm
    from freecad_buddy.usecases.documents import DocumentRegistry

    caps = Capabilities.from_env(env)
    posture = confirm.auto_approve()
    try:
        registry = build_registry(DocumentRegistry(), caps, Marshal(InlineExecutor()))
    finally:
        confirm.set_auto_approve(posture)
    return [tool.name for tool in registered_tools(registry, caps)]


def _audit_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@needs_freecad
def test_should_serve_the_single_process_surface_and_exit_zero_when_driven_over_stdio(tmp_path):
    # Arrange
    env = _child_env(tmp_path)
    expected_names = _in_process_tool_names(env)
    with open(tmp_path / "stderr.log", "wb") as stderr:
        process = subprocess.Popen(
            [sys.executable, *SERVE_ARGS],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            env=env,
        )
        session = _StdioSession(process)

        # Act
        try:
            initialized = session.request(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "two-process-test", "version": "0"},
                },
            )
            session.notify("notifications/initialized")
            listed = session.request("tools/list")
            capabilities = session.request(
                "tools/call", {"name": "query_capabilities", "arguments": {}}
            )
            created = session.request(
                "tools/call", {"name": "document_create", "arguments": {"label": "TwoProcess"}}
            )
            doc = created["structuredContent"]["structured_content"]["doc"]
            body = session.request(
                "tools/call",
                {"name": "feature_body_create", "arguments": {"doc": doc, "name": "Body"}},
            )
            executed = session.request(
                "tools/call",
                {
                    "name": "script_exec",
                    "arguments": {"doc": doc, "code": "print('hi')\nresult = 6*7"},
                },
            )
            process.stdin.close()
            exit_code = process.wait(timeout=30)
            trailing_stdout = process.stdout.read()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    audit = _audit_records(tmp_path / "audit.jsonl")

    # Assert
    assert initialized["serverInfo"]["name"] == "freecad-buddy"
    assert [tool["name"] for tool in listed["tools"]] == expected_names
    assert capabilities["structuredContent"]["status"] == "OK"
    assert created["structuredContent"]["status"] == "OK"
    assert body["structuredContent"]["status"] == "OK"
    assert executed["structuredContent"]["status"] == "OK"
    assert executed["structuredContent"]["structured_content"]["stdout"] == "hi\n"
    assert executed["structuredContent"]["structured_content"]["value_repr"] == "42"
    assert exit_code == 0
    assert trailing_stdout == b""
    # The front writes the adapter pairs (document_create, script_exec); the worker writes the
    # approval and the bracket pair of the geometry mutation, which carry real fingerprints.
    assert [(record["event"], record["tool"]) for record in audit] == [
        ("mutation", "document_create"),
        ("mutation", "document_create"),
        ("approval", "feature_body_create"),
        ("mutation", "feature_body_create"),
        ("mutation", "feature_body_create"),
        ("exec", "script_exec"),
        ("exec", "script_exec"),
    ]
    assert audit[4]["fingerprint_before"] is not None
    assert audit[4]["fingerprint_after"] is not None
    assert audit[4]["verify_verdict"] == "OK"
    assert audit[5]["code"] == audit[6]["code"] == "print('hi')\nresult = 6*7"
    assert audit[6]["verify_verdict"] == "OK"


def _boolean_loop(seconds: float) -> str:
    """``script_exec`` code that runs OCC booleans, which hold the GIL in C++, for ``seconds``."""
    return (
        "import time\n"
        f"deadline = time.monotonic() + {seconds}\n"
        "box = Part.makeBox(10, 10, 10)\n"
        "while time.monotonic() < deadline:\n"
        "    box.cut(Part.makeCylinder(3, 10)).fuse(Part.makeSphere(4))\n"
    )


@needs_freecad
def test_should_bound_a_script_exec_body_held_in_freecad_cpp_when_driven_over_stdio(tmp_path):
    # Arrange
    budget_s = SCRIPT_EXEC_SPEC.timeout_s
    body_s = budget_s + 4.0
    with open(tmp_path / "stderr.log", "wb") as stderr:
        process = subprocess.Popen(
            [sys.executable, *SERVE_ARGS],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            env=_child_env(tmp_path),
        )
        session = _StdioSession(process)
        try:
            session.request(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "two-process-test", "version": "0"},
                },
            )
            session.notify("notifications/initialized")
            created = session.request(
                "tools/call", {"name": "document_create", "arguments": {"label": "Bound"}}
            )
            doc = created["structuredContent"]["structured_content"]["doc"]

            # Act
            started = time.monotonic()
            timed_out = session.request(
                "tools/call",
                {"name": "script_exec", "arguments": {"doc": doc, "code": _boolean_loop(body_s)}},
            )
            timed_out_s = time.monotonic() - started
            refused, refused_s = _timed(
                lambda: session.request("tools/call", {"name": "document_list", "arguments": {}})
            )
            time.sleep(max(0.0, started + body_s + 3.0 - time.monotonic()))
            served, served_s = _timed(
                lambda: session.request("tools/call", {"name": "document_list", "arguments": {}})
            )
            process.stdin.close()
            exit_code = process.wait(timeout=30)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    # Assert
    assert timed_out["structuredContent"]["status"] == "TIMEOUT"
    assert timed_out["structuredContent"]["detail"]["data"]["marshal_timeout"] is True
    assert budget_s <= timed_out_s < budget_s + 1.0
    assert refused["structuredContent"]["status"] == "TIMEOUT"
    assert refused["structuredContent"]["detail"]["data"] == {"quarantined": True}
    assert refused_s < 1.0
    assert served["structuredContent"]["status"] == "OK"
    listed = served["structuredContent"]["structured_content"]["documents"]
    assert doc in [document["doc"] for document in listed]
    assert served_s < 5.0
    assert exit_code == 0


_FRONT_PROBE = """
import json, sys
from freecad_buddy.adapters.audit_log import AuditSink
from freecad_buddy.adapters.mcp_server import Capabilities, build_server
from freecad_buddy.adapters.rpc_client import RpcClient
from freecad_buddy.hosts.headless.entry import WorkerClient
from freecad_buddy.hosts.rpc_proxy import build_proxy_registry

class Exited:
    def poll(self):
        return 1

caps = Capabilities.from_env({})
rpc = RpcClient(endpoint={"host": "127.0.0.1", "port": 1, "token": "t"})
client = WorkerClient(rpc, Exited(), {})
registry = build_proxy_registry(client, caps)
build_server(registry, caps, AuditSink(sys.argv[1]))
registry.dispatch("query_capabilities", {})
registry.dispatch("no_such_tool", {})
print(json.dumps(sorted(sys.modules)))
"""

_WORKER_PROBE = """
import json, sys
from freecad_buddy.adapters.marshal import InlineExecutor, Marshal
from freecad_buddy.hosts.headless import worker
from freecad_buddy.usecases.capabilities import Capabilities
from freecad_buddy.usecases.documents import DocumentRegistry

worker.verify_freecad_importable()
worker.build_registry(DocumentRegistry(), Capabilities.from_env({}), Marshal(InlineExecutor()))
print(json.dumps(sorted(sys.modules)))
"""


def _probe_modules(code: str, *args: str) -> set[str]:
    result = subprocess.run(
        [sys.executable, "-c", code, *args], capture_output=True, check=True, timeout=120
    )
    return set(json.loads(result.stdout.decode("utf-8").strip().splitlines()[-1]))


@needs_freecad
def test_should_hold_no_freecad_when_the_front_has_built_its_stack(tmp_path):
    # Arrange
    audit_path = str(tmp_path / "audit.jsonl")

    # Act
    modules = _probe_modules(_FRONT_PROBE, audit_path)

    # Assert
    assert "mcp" in modules
    assert "FreeCAD" not in modules


@needs_freecad
def test_should_hold_no_mcp_when_the_worker_has_built_its_registry():
    # Arrange
    code = _WORKER_PROBE

    # Act
    modules = _probe_modules(code)

    # Assert
    assert "FreeCAD" in modules
    assert not [name for name in modules if name == "mcp" or name.startswith("mcp.")]
