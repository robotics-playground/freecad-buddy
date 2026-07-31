"""MCP surface, dispatch, and audit tests that run without FreeCAD.

Covers the tool surface, schema/docstring presence, the ``debug_exec`` env-flag gate, the
dispatch error boundary, the call-tool result wrapping, and audit-line validity. The
in-FreeCAD lifecycle and probe behavior lives in ``tests/infc/``.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import threading
import time
from pathlib import Path

import jsonschema
import pytest

from freecad_buddy.adapters.audit_log import AuditSink
from freecad_buddy.adapters.marshal import (
    InlineExecutor,
    Marshal,
    MarshalTimeout,
    ThreadExecutor,
)
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
    "document_undo",
}

EXPECTED_QUERY_TOOLS = {
    "query_tree_summary",
    "query_object",
    "query_mass_properties",
    "query_dependencies",
    "query_sketch_info",
    "query_placement",
}

EXPECTED_VERIFY_TOOLS = {
    "verify_shape",
    "verify_sketch",
    "verify_recompute",
    "verify_export_step",
    "verify_export_stl",
    "verify_export_3mf",
}

EXPECTED_EXPORT_TOOLS = {
    "export_step",
    "export_stl",
    "export_3mf",
}

EXPECTED_SKETCH_TOOLS = {
    "sketch_create",
    "sketch_add_geometry",
    "sketch_remove_geometry",
    "sketch_add_constraint",
    "sketch_remove_constraint",
    "sketch_set_datum",
    "sketch_toggle_construction",
    "sketch_add_external_geometry",
}

EXPECTED_FEATURE_TOOLS = {
    "feature_pad",
    "feature_pocket",
    "feature_revolve",
    "feature_hole",
    "feature_fillet",
    "feature_chamfer",
    "feature_pattern",
    "feature_mirror",
    "feature_datum",
    "feature_set_parameters",
}


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _registry(caps: Capabilities) -> MethodRegistry:
    # A no-op marshal path: build_registry only needs a Marshal to wrap handlers; the surface
    # tests never invoke the FreeCAD-touching handlers.
    return build_registry(DocumentRegistry(), caps, Marshal(InlineExecutor()))


def test_tools_list_exec_off_lists_document_and_query_tools():
    caps = Capabilities(allow_exec=False)
    tools = registered_tools(_registry(caps), caps)
    names = {t.name for t in tools}

    assert EXPECTED_DOCUMENT_TOOLS <= names
    assert EXPECTED_QUERY_TOOLS <= names
    assert EXPECTED_VERIFY_TOOLS <= names
    assert EXPECTED_EXPORT_TOOLS <= names
    assert EXPECTED_SKETCH_TOOLS <= names
    assert EXPECTED_FEATURE_TOOLS <= names
    assert "query_capabilities" in names
    assert "query_screenshot" in names
    assert "debug_exec" not in names
    assert names == (
        EXPECTED_DOCUMENT_TOOLS
        | EXPECTED_QUERY_TOOLS
        | EXPECTED_VERIFY_TOOLS
        | EXPECTED_EXPORT_TOOLS
        | EXPECTED_SKETCH_TOOLS
        | EXPECTED_FEATURE_TOOLS
        | {"query_capabilities", "query_screenshot", "preview_dry_run"}
    )


def test_query_tools_require_doc_and_reject_unknown_keys():
    caps = Capabilities(allow_exec=False)
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}
    for name in EXPECTED_QUERY_TOOLS:
        schema = tools[name].inputSchema
        assert schema["additionalProperties"] is False, f"{name} allows extra keys"
        if name == "query_dependencies":
            assert schema["required"] == ["doc"]
            assert "object" in schema["properties"]
        else:
            assert "doc" in schema["required"], f"{name} does not require doc"


def test_screenshot_schema_is_tightened_on_view_and_selectors():
    caps = Capabilities(allow_exec=False)
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}
    schema = tools["query_screenshot"].inputSchema
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["doc"]
    view = schema["properties"]["view"]
    assert view["additionalProperties"] is False
    for selector in ("focus", "highlight"):
        sel = view["properties"][selector]
        assert sel["additionalProperties"] is False
        assert sel["properties"]["element_type"]["enum"] == ["face", "edge", "vertex"]
        assert "index" in sel["properties"]
        assert "mapped_name" in sel["properties"]
        assert sel["required"] == ["object"]
    assert view["properties"]["width"]["maximum"] == 1920
    assert view["properties"]["height"]["maximum"] == 1920
    assert view["properties"]["width"]["default"] == 1920
    assert view["properties"]["height"]["default"] == 1920


def test_dispatch_query_with_unknown_handle_is_invalid_input():
    caps = Capabilities(allow_exec=False)
    registry = _registry(caps)
    envelope = registry.dispatch("query_object", {"doc": "fcb-doc:missing", "object": "Box"})
    assert envelope["status"] == "INVALID_INPUT"


def test_verify_tools_require_doc_and_reject_unknown_keys():
    caps = Capabilities(allow_exec=False)
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}
    for name in EXPECTED_VERIFY_TOOLS:
        schema = tools[name].inputSchema
        assert schema["additionalProperties"] is False, f"{name} allows extra keys"
        assert "doc" in schema["required"], f"{name} does not require doc"
    assert "checks" in tools["verify_shape"].inputSchema["properties"]
    assert "sketch" in tools["verify_sketch"].inputSchema["required"]


def test_dispatch_verify_recompute_with_unknown_handle_is_invalid_input():
    caps = Capabilities(allow_exec=False)
    registry = _registry(caps)
    envelope = registry.dispatch("verify_recompute", {"doc": "fcb-doc:missing"})
    assert envelope["status"] == "INVALID_INPUT"


def test_export_tools_require_doc_path_and_reject_unknown_keys():
    caps = Capabilities(allow_exec=False)
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}
    for name in EXPECTED_EXPORT_TOOLS:
        schema = tools[name].inputSchema
        assert schema["additionalProperties"] is False, f"{name} allows extra keys"
        assert "doc" in schema["required"], f"{name} does not require doc"
        assert "path" in schema["required"], f"{name} does not require path"
    assert tools["export_step"].inputSchema["properties"]["ap"]["enum"] == ["AP214", "AP242"]


def test_verify_export_tools_require_export_id():
    caps = Capabilities(allow_exec=False)
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}
    for name in ("verify_export_step", "verify_export_stl", "verify_export_3mf"):
        schema = tools[name].inputSchema
        assert schema["additionalProperties"] is False, f"{name} allows extra keys"
        assert "export_id" in schema["required"], f"{name} does not require export_id"
        assert "doc" in schema["required"], f"{name} does not require doc"


def test_export_tools_document_verified_false():
    caps = Capabilities(allow_exec=False)
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}
    for name in EXPECTED_EXPORT_TOOLS:
        assert "verified" in tools[name].description


def test_dispatch_export_with_unknown_handle_is_invalid_input():
    caps = Capabilities(allow_exec=False)
    registry = _registry(caps)
    for name, args in (
        ("export_step", {"doc": "fcb-doc:missing", "path": "x.step"}),
        ("export_stl", {"doc": "fcb-doc:missing", "path": "x.stl"}),
        ("export_3mf", {"doc": "fcb-doc:missing", "path": "x.3mf"}),
        ("verify_export_step", {"doc": "fcb-doc:missing", "export_id": "nope"}),
        ("verify_export_stl", {"doc": "fcb-doc:missing", "export_id": "nope"}),
        ("verify_export_3mf", {"doc": "fcb-doc:missing", "export_id": "nope"}),
    ):
        envelope = registry.dispatch(name, args)
        assert envelope["status"] == "INVALID_INPUT", name


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


def test_tree_summary_schema_has_depth_root_filters():
    caps = Capabilities(allow_exec=False)
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}
    schema = tools["query_tree_summary"].inputSchema
    props = schema["properties"]
    assert props["depth"]["default"] == 1
    assert props["depth"]["minimum"] == 1
    assert "root" in props
    fprops = props["filters"]["properties"]
    for key in ("types", "exclude_types", "renderable_only", "visible_only", "name_pattern"):
        assert key in fprops
    assert props["filters"]["additionalProperties"] is False
    assert "max_nodes" not in props


_BUDGET = 0.2


@pytest.fixture
def release():
    """An event set at teardown so a deliberately blocked body never outlives its test."""
    event = threading.Event()
    yield event
    event.set()


def test_thread_executor_marshal_returns_value_under_budget():
    marshal = Marshal(ThreadExecutor())
    assert marshal.call(lambda: 21 * 2, 5.0) == 42


def test_thread_executor_marshal_reraises_same_exception_instance():
    marshal = Marshal(ThreadExecutor())
    raised = ValidationError("bad handle")

    def _boom():
        raise raised

    with pytest.raises(ValidationError) as excinfo:
        marshal.call(_boom, 5.0)
    assert excinfo.value is raised


def test_thread_executor_marshal_times_out_promptly_while_body_still_runs(release):
    marshal = Marshal(ThreadExecutor())
    started = time.monotonic()

    with pytest.raises(MarshalTimeout):
        marshal.call(lambda: release.wait(30.0), _BUDGET)

    elapsed = time.monotonic() - started
    assert elapsed < _BUDGET * 5, f"timeout took {elapsed}s for a {_BUDGET}s budget"
    assert not release.is_set(), "body finished on its own; the test proves nothing"


def _suspect_server(behaviors: dict, audit_path: Path):
    """Build a server whose stub tools return canned envelopes, recording every invocation.

    ``behaviors`` maps tool name to ``(mutating, envelope_factory)``. The returned ``calls``
    list records each tool name that actually reached its handler.
    """
    calls: list[str] = []
    registry = MethodRegistry()
    for name, (mutating, factory) in behaviors.items():

        def _handler(_name=name, _factory=factory, **_params):
            calls.append(_name)
            return _factory()

        registry.register(RpcMethod(name=name, handler=_handler, mutating=mutating))
    server = build_server(registry, Capabilities(allow_exec=False), AuditSink(audit_path))
    return server, calls


def _timeout_envelope() -> dict:
    raise MarshalTimeout(f"marshaled call exceeded {_BUDGET}s")


def _ok_envelope() -> dict:
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": {},
        "text": "{}",
    }


def _mutate_ok_envelope() -> dict:
    return _ok_envelope()


def _suspect_fixture(tmp_path: Path):
    return _suspect_server(
        {
            "slow_mutate": (True, _timeout_envelope),
            "fast_mutate": (True, _mutate_ok_envelope),
            "slow_read": (False, _timeout_envelope),
            "read": (False, _ok_envelope),
            "failing_read": (
                False,
                lambda: {
                    "schema": "fcb.result-envelope/1",
                    "status": "INVALID_INPUT",
                    "detail": {"code": "INVALID_INPUT", "message": "nope", "data": {}},
                    "structured_content": {},
                    "text": "{}",
                },
            ),
        },
        tmp_path / "audit.jsonl",
    )


def test_marshal_timeout_returns_timeout_envelope_and_marks_doc_suspect(tmp_path):
    server, calls = _suspect_fixture(tmp_path)

    result = _call_tool_via_server(server, "slow_mutate", {"doc": "fcb-doc:D"})

    envelope = result.structuredContent
    assert envelope["status"] == "TIMEOUT"
    assert envelope["detail"]["data"]["marshal_timeout"] is True
    assert envelope["detail"]["data"]["maybe_still_running"] is True
    assert "may still be running" in envelope["detail"]["message"]
    assert "do not blind-retry" in envelope["detail"]["message"]
    assert calls == ["slow_mutate"]

    records = [
        json.loads(line)
        for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2
    assert "fingerprint_before" in records[0]
    assert records[1]["verify_verdict"] == "TIMEOUT"


def test_mutating_call_on_suspect_doc_is_refused_without_reaching_the_handler(tmp_path):
    server, calls = _suspect_fixture(tmp_path)
    _call_tool_via_server(server, "slow_mutate", {"doc": "fcb-doc:D"})
    calls.clear()

    result = _call_tool_via_server(server, "fast_mutate", {"doc": "fcb-doc:D"})

    assert result.structuredContent["status"] == "INVALID_INPUT"
    assert "document-suspect" in result.structuredContent["detail"]["message"]
    assert calls == []

    records = [
        json.loads(line)
        for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert "fingerprint_before" in records[-2]
    assert records[-1]["verify_verdict"] == "INVALID_INPUT"


def test_ok_read_on_suspect_doc_clears_the_flag(tmp_path):
    server, calls = _suspect_fixture(tmp_path)
    _call_tool_via_server(server, "slow_mutate", {"doc": "fcb-doc:D"})

    assert (
        _call_tool_via_server(server, "read", {"doc": "fcb-doc:D"}).structuredContent["status"]
        == "OK"
    )
    calls.clear()

    result = _call_tool_via_server(server, "fast_mutate", {"doc": "fcb-doc:D"})
    assert result.structuredContent["status"] == "OK"
    assert calls == ["fast_mutate"]


def test_read_on_a_different_doc_does_not_clear_the_flag(tmp_path):
    server, calls = _suspect_fixture(tmp_path)
    _call_tool_via_server(server, "slow_mutate", {"doc": "fcb-doc:D"})
    _call_tool_via_server(server, "read", {"doc": "fcb-doc:OTHER"})
    calls.clear()

    result = _call_tool_via_server(server, "fast_mutate", {"doc": "fcb-doc:D"})
    assert result.structuredContent["status"] == "INVALID_INPUT"
    assert calls == []


def test_read_returning_non_ok_leaves_the_flag_set(tmp_path):
    server, calls = _suspect_fixture(tmp_path)
    _call_tool_via_server(server, "slow_mutate", {"doc": "fcb-doc:D"})
    _call_tool_via_server(server, "failing_read", {"doc": "fcb-doc:D"})
    calls.clear()

    result = _call_tool_via_server(server, "fast_mutate", {"doc": "fcb-doc:D"})
    assert result.structuredContent["status"] == "INVALID_INPUT"
    assert calls == []


def test_timed_out_non_mutating_call_sets_no_suspect_flag(tmp_path):
    server, calls = _suspect_fixture(tmp_path)
    timed_out = _call_tool_via_server(server, "slow_read", {"doc": "fcb-doc:D"}).structuredContent
    assert timed_out["status"] == "TIMEOUT"
    assert "not marked suspect" in timed_out["detail"]["message"], (
        "a read timeout must not tell the operator the document is suspect"
    )
    calls.clear()

    result = _call_tool_via_server(server, "fast_mutate", {"doc": "fcb-doc:D"})
    assert result.structuredContent["status"] == "OK"
    assert calls == ["fast_mutate"]


def test_timeout_without_a_doc_marks_only_the_doc_less_slot(tmp_path):
    server, calls = _suspect_fixture(tmp_path)
    _call_tool_via_server(server, "slow_mutate", {})
    calls.clear()

    assert (
        _call_tool_via_server(server, "fast_mutate", {}).structuredContent["status"]
        == "INVALID_INPUT"
    )
    assert (
        _call_tool_via_server(server, "fast_mutate", {"doc": "fcb-doc:D"}).structuredContent[
            "status"
        ]
        == "OK"
    )
    assert calls == ["fast_mutate"]


def test_non_string_doc_is_rejected_before_it_keys_the_suspect_set(tmp_path):
    server, calls = _suspect_fixture(tmp_path)
    result = _call_tool_via_server(server, "fast_mutate", {"doc": 7})
    assert result.structuredContent["status"] == "INVALID_INPUT"
    assert "doc handle must be a string" in result.structuredContent["detail"]["message"]
    assert calls == []


def test_rejected_doc_never_reaches_the_audit_log(tmp_path):
    schema = _load_schema("audit-record.schema.json")
    audit_path = tmp_path / "audit.jsonl"
    server, _calls = _suspect_fixture(tmp_path)

    for bad in (7, [], {"handle": "x"}, 1.5):
        _call_tool_via_server(server, "fast_mutate", {"doc": bad})

    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert records, "the rejected calls must still be audited"
    for record in records:
        jsonschema.validate(instance=record, schema=schema)
        assert "doc" not in record, "a non-string handle must not be written to the audit log"


def test_suspect_state_is_per_server(tmp_path):
    first, _ = _suspect_fixture(tmp_path)
    second, calls = _suspect_fixture(tmp_path / "second")
    _call_tool_via_server(first, "slow_mutate", {"doc": "fcb-doc:D"})

    assert (
        _call_tool_via_server(second, "fast_mutate", {"doc": "fcb-doc:D"}).structuredContent[
            "status"
        ]
        == "OK"
    )
    assert calls == ["fast_mutate"]


def _catalog_with_short_exec(monkeypatch, exec_body):
    """Build the production catalog with ``debug_exec`` on a short budget and a stub body."""
    from freecad_buddy.hosts import tool_catalog

    monkeypatch.setattr(
        tool_catalog,
        "DEBUG_EXEC_SPEC",
        dataclasses.replace(tool_catalog.DEBUG_EXEC_SPEC, timeout_s=_BUDGET),
    )
    monkeypatch.setattr(tool_catalog.debug_exec_uc, "debug_exec", exec_body)
    return tool_catalog.build_inline_handlers(
        DocumentRegistry(),
        tool_catalog.ExportRegistry(),
        Capabilities(allow_exec=True),
        Marshal(InlineExecutor()),
        render_port=object(),
    )


def test_debug_exec_overrunning_its_budget_times_out_through_the_real_catalog(monkeypatch, release):
    registry = _catalog_with_short_exec(
        monkeypatch, lambda _registry, _doc, _code: release.wait(30.0)
    )
    started = time.monotonic()

    envelope = registry.dispatch("debug_exec", {"doc": "fcb-doc:D", "code": "pass"})

    elapsed = time.monotonic() - started
    assert envelope["status"] == "TIMEOUT"
    assert envelope["detail"]["data"]["marshal_timeout"] is True
    assert elapsed < _BUDGET * 5, f"timeout took {elapsed}s for a {_BUDGET}s budget"
    assert not release.is_set(), "exec body finished on its own; the test proves nothing"


def test_only_debug_exec_runs_off_the_main_thread(monkeypatch):
    """A non-exec tool must stay on the caller's thread; only ``debug_exec`` may be threaded."""
    from freecad_buddy.hosts import tool_catalog

    seen: dict[str, int] = {}
    monkeypatch.setattr(
        tool_catalog.queries,
        "query_tree_summary",
        lambda *_a, **_k: seen.setdefault("query_tree_summary", threading.get_ident()),
    )
    registry = _catalog_with_short_exec(
        monkeypatch,
        lambda _registry, _doc, _code: seen.setdefault("debug_exec", threading.get_ident()),
    )

    registry.dispatch("debug_exec", {"doc": "fcb-doc:D", "code": "pass"})
    registry.dispatch("query_tree_summary", {"doc": "fcb-doc:D"})

    assert seen["debug_exec"] != threading.get_ident(), "debug_exec did not run on a worker"
    assert seen["query_tree_summary"] == threading.get_ident(), (
        "a non-exec tool ran off the main thread"
    )
