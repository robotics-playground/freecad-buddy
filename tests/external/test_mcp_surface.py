"""MCP surface, dispatch, and audit tests that run without FreeCAD.

Covers the tool surface, schema/docstring presence, the ``debug_exec`` env-flag gate, the
dispatch error boundary, the call-tool result wrapping, and audit-line validity. The
in-FreeCAD lifecycle and probe behavior lives in ``tests/infc/``.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import jsonschema

from freecad_buddy.adapters.audit_log import AuditSink
from freecad_buddy.adapters.marshal import InlineExecutor, Marshal
from freecad_buddy.adapters.mcp_server import (
    Capabilities,
    build_server,
    registered_tools,
)
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.hosts.headless.entry import build_registry
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "src" / "freecad_buddy" / "contracts" / "jsonschema"

EXPECTED_DOCUMENT_TOOLS = {
    "document_create",
    "document_open",
    "document_save",
    "document_close",
    "document_list",
    "document_recompute",
}


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _registry(caps: Capabilities) -> MethodRegistry:
    # A no-op marshal path: build_registry only needs a Marshal to wrap handlers; the surface
    # tests never invoke the FreeCAD-touching handlers.
    return build_registry(DocumentRegistry(), caps, Marshal(InlineExecutor()))


def test_tools_list_exec_off_lists_six_document_plus_query():
    caps = Capabilities(allow_exec=False)
    tools = registered_tools(_registry(caps), caps)
    names = {t.name for t in tools}

    assert EXPECTED_DOCUMENT_TOOLS <= names
    assert "query_capabilities" in names
    assert "debug_exec" not in names
    assert names == EXPECTED_DOCUMENT_TOOLS | {"query_capabilities"}


def test_every_tool_has_input_output_schema_and_docstring():
    caps = Capabilities(allow_exec=False)
    tools = registered_tools(_registry(caps), caps)
    for tool in tools:
        assert tool.inputSchema, f"{tool.name} missing inputSchema"
        assert tool.inputSchema.get("type") == "object"
        assert tool.outputSchema, f"{tool.name} missing outputSchema"
        assert "status" in tool.outputSchema["properties"], f"{tool.name} outputSchema not envelope"
        assert tool.description, f"{tool.name} missing docstring/description"


def test_tool_names_use_underscore_no_dots():
    caps = Capabilities(allow_exec=True)
    tools = registered_tools(_registry(caps), caps)
    for tool in tools:
        assert "." not in tool.name, f"dot in tool name {tool.name} (illegal on the wire)"
        assert "-" not in tool.name


def test_debug_exec_present_when_flag_set():
    caps = Capabilities(allow_exec=True)
    tools = registered_tools(_registry(caps), caps)
    names = {t.name for t in tools}
    assert "debug_exec" in names


def test_debug_exec_absent_in_service_mode_even_when_flag_set():
    caps = Capabilities(allow_exec=True, service_mode=True)
    tools = registered_tools(_registry(caps), caps)
    assert "debug_exec" not in {t.name for t in tools}


def test_capabilities_from_env_reads_flag_exactly_one():
    assert Capabilities.from_env({"FREECAD_BUDDY_ALLOW_EXEC": "1"}).allow_exec is True
    assert Capabilities.from_env({"FREECAD_BUDDY_ALLOW_EXEC": "0"}).allow_exec is False
    assert Capabilities.from_env({"FREECAD_BUDDY_ALLOW_EXEC": "true"}).allow_exec is False
    assert Capabilities.from_env({}).allow_exec is False


def test_dispatch_maps_validation_error_to_invalid_input():
    registry = MethodRegistry()

    def _raises(**_params):
        raise ValidationError("bad handle")

    registry.register(RpcMethod(name="document_save", handler=_raises, mutating=True))
    envelope = registry.dispatch("document_save", {"doc": "fcb-doc:missing"})

    assert envelope["status"] == "INVALID_INPUT"
    assert envelope["schema"] == "fcb.result-envelope/1"
    assert envelope["detail"]["message"] == "bad handle"
    assert envelope["detail"]["data"]["exception"] == "ValidationError"


def test_dispatch_unknown_method_is_invalid_input():
    registry = MethodRegistry()
    envelope = registry.dispatch("nope", {})
    assert envelope["status"] == "INVALID_INPUT"


def test_dispatch_unexpected_exception_is_recompute_error():
    registry = MethodRegistry()

    def _boom(**_params):
        raise RuntimeError("freecad blew up")

    registry.register(RpcMethod(name="document_recompute", handler=_boom, mutating=True))
    envelope = registry.dispatch("document_recompute", {"doc": "x"})

    assert envelope["status"] == "RECOMPUTE_ERROR"
    assert envelope["detail"]["data"]["unexpected"] is True


def test_dispatch_returns_valid_result_envelope(tmp_path):
    registry = MethodRegistry()
    registry.register(
        RpcMethod(
            name="query_capabilities",
            handler=lambda: {
                "schema": "fcb.result-envelope/1",
                "status": "OK",
                "detail": None,
                "structured_content": {"render": "none"},
                "text": "{}",
            },
        )
    )
    envelope = registry.dispatch("query_capabilities", {})
    jsonschema.validate(instance=envelope, schema=_load_schema("result-envelope.schema.json"))


def test_audit_sink_appends_valid_mutation_and_exec_lines(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    sink = AuditSink(audit_path)

    sink.before("mutation", "document_create", "fcb-doc:abc", {"label": "part"})
    sink.after("mutation", "document_create", "fcb-doc:abc", {"label": "part"}, "OK")
    sink.before("exec", "debug_exec", "fcb-doc:abc", {"code": "1+1"})
    sink.after("exec", "debug_exec", "fcb-doc:abc", {"code": "1+1"}, "OK")

    schema = _load_schema("audit-record.schema.json")
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    events = []
    for line in lines:
        record = json.loads(line)
        jsonschema.validate(instance=record, schema=schema)
        assert record["schema"] == "fcb.audit-record/1"
        events.append(record["event"])
    assert events == ["mutation", "mutation", "exec", "exec"]


def test_audit_sink_is_append_only_never_truncates(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    sink = AuditSink(audit_path)
    sink.before("mutation", "document_save", "fcb-doc:1", {})
    first = audit_path.read_text(encoding="utf-8")
    sink.before("mutation", "document_close", "fcb-doc:1", {})
    second = audit_path.read_text(encoding="utf-8")
    assert second.startswith(first)
    assert len(second.splitlines()) == 2


def test_marshal_inline_runs_and_returns():
    marshal = Marshal(InlineExecutor())
    assert marshal.call(lambda: 21 * 2, 5.0) == 42


def test_marshal_propagates_handler_exception():
    marshal = Marshal(InlineExecutor())
    try:
        marshal.call(lambda: (_ for _ in ()).throw(ValidationError("x")), 5.0)
    except ValidationError:
        return
    raise AssertionError("expected ValidationError to propagate")


def test_serve_rpc_mode_returns_deferral_error():
    from freecad_buddy.hosts.main import main

    assert main(["serve", "--mode", "rpc"]) == 2


def _call_tool_via_server(server, tool_name: str, arguments: dict):
    from mcp import types

    handler = server.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name=tool_name, arguments=arguments),
    )
    result = asyncio.run(handler(request))
    return result.root


def _server_with_stub(status: str, structured: dict):
    registry = MethodRegistry()
    registry.register(
        RpcMethod(
            name="stub_tool",
            handler=lambda **_p: {
                "schema": "fcb.result-envelope/1",
                "status": status,
                "detail": None if status == "OK" else {"message": "boom"},
                "structured_content": structured,
                "text": json.dumps(structured),
            },
        )
    )
    caps = Capabilities(allow_exec=False)
    audit = AuditSink(Path("unused-audit.jsonl"))
    return build_server(registry, caps, audit)


def test_call_tool_ok_status_is_not_error():
    server = _server_with_stub("OK", {"render": "none"})
    result = _call_tool_via_server(server, "stub_tool", {})
    assert result.isError is False
    assert result.structuredContent["status"] == "OK"


def test_call_tool_non_ok_status_sets_is_error():
    server = _server_with_stub("INVALID_INPUT", {})
    result = _call_tool_via_server(server, "stub_tool", {})
    assert result.isError is True
    assert result.structuredContent["status"] == "INVALID_INPUT"
