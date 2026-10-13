"""Two-process headless host: the front's RPC hop to the worker, its lifecycle, and its imports.

The listener, client and shutdown cases run without FreeCAD over a real localhost socket and
real child processes. The end-to-end case and the import probes need an interpreter that can
``import FreeCAD`` (the fcb env) and skip elsewhere.
"""

from __future__ import annotations

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

from freecad_buddy.adapters.marshal import InlineExecutor, Marshal
from freecad_buddy.adapters.rpc_client import RpcClient
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.adapters.rpc_listener import RpcListener
from freecad_buddy.contracts import DEFAULT_DISPLAY_DECIMALS
from freecad_buddy.hosts.headless.entry import WorkerClient, shut_down_worker
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
    target = WorkerClient(client, _ExitedProcess())

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
client = WorkerClient(RpcClient(endpoint={"host": "127.0.0.1", "port": 1, "token": "t"}), Exited())
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
