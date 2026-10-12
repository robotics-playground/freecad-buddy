"""MCP surface, dispatch, and audit tests that run without FreeCAD.

Covers the tool surface, schema/docstring presence, the ``script_exec`` env-flag gate, the
dispatch error boundary, the call-tool result wrapping, and audit-line validity. The
in-FreeCAD lifecycle and probe behavior lives in ``tests/infc/``.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
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
    _to_call_result,
    build_server,
    registered_tools,
)
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod, is_audited
from freecad_buddy.contracts import ANCHOR_FRAME_KINDS, summary_text
from freecad_buddy.hosts.headless.entry import build_registry
from freecad_buddy.hosts.tool_catalog import READ_ONLY_PROFILE, SCRIPT_EXEC_SPEC, tool_specs
from freecad_buddy.usecases import confirm
from freecad_buddy.usecases.capabilities import SCRIPT_EXEC_WARNING
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
    "feature_body_create",
}


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _registry(caps: Capabilities) -> MethodRegistry:
    # A no-op marshal path: build_registry only needs a Marshal to wrap handlers; the surface
    # tests never invoke the FreeCAD-touching handlers.
    return build_registry(DocumentRegistry(), caps, Marshal(InlineExecutor()))


def test_tools_list_exec_off_lists_document_and_query_tools():
    caps = Capabilities(script_exec=False)
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
    assert "view_fit_viewport" in names
    assert "script_exec" not in names
    assert names == (
        EXPECTED_DOCUMENT_TOOLS
        | EXPECTED_QUERY_TOOLS
        | EXPECTED_VERIFY_TOOLS
        | EXPECTED_EXPORT_TOOLS
        | EXPECTED_SKETCH_TOOLS
        | EXPECTED_FEATURE_TOOLS
        | {"query_capabilities", "query_screenshot", "view_fit_viewport", "preview_dry_run"}
    )


def test_query_tools_require_doc_and_reject_unknown_keys():
    caps = Capabilities(script_exec=False)
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
    caps = Capabilities(script_exec=False)
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


def test_view_fit_viewport_is_the_confirm_exempt_mutating_shape():
    """AD-31's wire shape, enforced rather than assumed.

    ``mutating`` with no ``confirm`` is the whole difference between this tool and a gated
    geometry mutation, and the only thing keeping it out of the assistant surface is its absence
    from the opt-in allow-list. A schema built through ``_feature_schema`` would silently acquire
    ``confirm`` and start demanding a ``preview_id`` for a camera move.
    """
    # Arrange
    spec = {spec.name: spec for spec in tool_specs()}["view_fit_viewport"]

    # Act
    schema = spec.input_schema

    # Assert
    assert spec.mutating is True
    assert "confirm" not in schema["properties"]
    assert set(schema["properties"]) == {"doc"}
    assert schema["required"] == ["doc"]
    assert schema["additionalProperties"] is False
    assert spec.audit_event == "mutation"
    assert "view_fit_viewport" not in READ_ONLY_PROFILE


def test_view_fit_viewport_is_audited_by_dispatch():
    """``mutating=True`` alone must qualify it for the audit bracket; ``is_audited`` is unchanged.

    Declaring the tool non-mutating to dodge the confirm question would silently drop every camera
    move from the audit log — the opposite of AD-31's intent.
    """
    # Arrange
    caps = Capabilities(script_exec=False)
    method = _registry(caps).get("view_fit_viewport")

    # Act
    audited = is_audited(method)

    # Assert
    assert audited is True


def test_dispatch_view_fit_with_unknown_handle_is_invalid_input():
    # Arrange
    registry = _registry(Capabilities(script_exec=False))

    # Act
    envelope = registry.dispatch("view_fit_viewport", {"doc": "fcb-doc:missing"})

    # Assert
    assert envelope["status"] == "INVALID_INPUT"


def test_dispatch_query_with_unknown_handle_is_invalid_input():
    caps = Capabilities(script_exec=False)
    registry = _registry(caps)
    envelope = registry.dispatch("query_object", {"doc": "fcb-doc:missing", "object": "Box"})
    assert envelope["status"] == "INVALID_INPUT"


def test_verify_tools_require_doc_and_reject_unknown_keys():
    caps = Capabilities(script_exec=False)
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}
    for name in EXPECTED_VERIFY_TOOLS:
        schema = tools[name].inputSchema
        assert schema["additionalProperties"] is False, f"{name} allows extra keys"
        assert "doc" in schema["required"], f"{name} does not require doc"
    assert "checks" in tools["verify_shape"].inputSchema["properties"]
    assert "sketch" in tools["verify_sketch"].inputSchema["required"]


def test_should_declare_a_closed_anchor_frame_when_verify_shape_lists_its_input_schema():
    # Arrange
    caps = Capabilities(script_exec=False)
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}

    # Act
    frame = tools["verify_shape"].inputSchema["properties"]["anchor_frame"]

    # Assert
    assert frame["required"] == ["kind"]
    assert frame["properties"]["kind"]["enum"] == sorted(ANCHOR_FRAME_KINDS)
    assert frame["additionalProperties"] is False


def test_dispatch_verify_recompute_with_unknown_handle_is_invalid_input():
    caps = Capabilities(script_exec=False)
    registry = _registry(caps)
    envelope = registry.dispatch("verify_recompute", {"doc": "fcb-doc:missing"})
    assert envelope["status"] == "INVALID_INPUT"


def test_export_tools_require_doc_path_and_reject_unknown_keys():
    caps = Capabilities(script_exec=False)
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}
    for name in EXPECTED_EXPORT_TOOLS:
        schema = tools[name].inputSchema
        assert schema["additionalProperties"] is False, f"{name} allows extra keys"
        assert "doc" in schema["required"], f"{name} does not require doc"
        assert "path" in schema["required"], f"{name} does not require path"
    assert tools["export_step"].inputSchema["properties"]["ap"]["enum"] == ["AP214", "AP242"]


def test_verify_export_tools_require_export_id():
    caps = Capabilities(script_exec=False)
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}
    for name in ("verify_export_step", "verify_export_stl", "verify_export_3mf"):
        schema = tools[name].inputSchema
        assert schema["additionalProperties"] is False, f"{name} allows extra keys"
        assert "export_id" in schema["required"], f"{name} does not require export_id"
        assert "doc" in schema["required"], f"{name} does not require doc"


def test_export_tools_document_verified_false():
    caps = Capabilities(script_exec=False)
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}
    for name in EXPECTED_EXPORT_TOOLS:
        assert "verified" in tools[name].description


def test_dispatch_export_with_unknown_handle_is_invalid_input():
    caps = Capabilities(script_exec=False)
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


# Tools whose payload travels in extra text blocks; they declare no outputSchema so a client
# that prefers structuredContent still shows the agent those blocks.
TEXT_BLOCK_TOOLS = {"query_tree_summary"}


def test_every_tool_has_input_output_schema_and_docstring():
    caps = Capabilities.from_env({})
    tools = registered_tools(_registry(caps), caps)
    for tool in tools:
        assert tool.inputSchema, f"{tool.name} missing inputSchema"
        assert tool.inputSchema.get("type") == "object"
        assert tool.description, f"{tool.name} missing docstring/description"
        if tool.name in TEXT_BLOCK_TOOLS:
            assert tool.outputSchema is None, f"{tool.name} must not declare an outputSchema"
            continue
        assert tool.outputSchema, f"{tool.name} missing outputSchema"
        assert "status" in tool.outputSchema["properties"], f"{tool.name} outputSchema not envelope"


def test_tool_names_use_underscore_no_dots():
    caps = Capabilities(script_exec=True)
    tools = registered_tools(_registry(caps), caps)
    for tool in tools:
        assert "." not in tool.name, f"dot in tool name {tool.name} (illegal on the wire)"
        assert "-" not in tool.name


def _listed_tool_names(caps: Capabilities) -> set[str]:
    return {tool.name for tool in registered_tools(_registry(caps), caps)}


def test_Should_list_script_exec_and_not_debug_exec_When_no_exec_variable_is_set():
    # Arrange
    caps = Capabilities.from_env({})

    # Act
    names = _listed_tool_names(caps)

    # Assert
    assert "script_exec" in names
    assert "debug_exec" not in names


@pytest.mark.parametrize("value", ["0", "", "true"])
def test_Should_not_list_script_exec_When_the_switch_is_not_exactly_one(value):
    # Arrange
    caps = Capabilities.from_env({"FREECAD_BUDDY_SCRIPT_EXEC": value})

    # Act
    names = _listed_tool_names(caps)

    # Assert
    assert "script_exec" not in names


def test_Should_deny_and_audit_a_direct_script_exec_call_When_the_switch_is_off(tmp_path):
    # Arrange
    audit_path = tmp_path / "audit.jsonl"
    caps = Capabilities.from_env({"FREECAD_BUDDY_SCRIPT_EXEC": "0"})
    target = build_server(_registry(caps), caps, AuditSink(audit_path))

    # Act
    result = _call_tool_via_server(target, "script_exec", {"doc": "fcb-doc:D", "code": "1+1"})

    # Assert
    assert result.structuredContent["status"] == "INVALID_INPUT"
    message = result.structuredContent["detail"]["message"]
    for switch in (
        "FREECAD_BUDDY_SCRIPT_EXEC",
        "ScriptExec",
        "FREECAD_BUDDY_UNATTENDED=1",
        "FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1",
    ):
        assert switch in message
    records = _audit_records(audit_path)
    assert [(r["event"], r["tool"]) for r in records] == [("exec", "script_exec")] * 2
    assert records[0]["code"] == "1+1"
    assert records[1]["verify_verdict"] == "INVALID_INPUT"


def test_Should_not_list_script_exec_When_the_run_is_marked_unattended():
    # Arrange
    caps = Capabilities.from_env({"FREECAD_BUDDY_UNATTENDED": "1"})

    # Act
    names = _listed_tool_names(caps)

    # Assert
    assert "script_exec" not in names


def test_Should_list_script_exec_When_an_unattended_run_opts_in():
    # Arrange
    caps = Capabilities.from_env(
        {"FREECAD_BUDDY_UNATTENDED": "1", "FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED": "1"}
    )

    # Act
    names = _listed_tool_names(caps)

    # Assert
    assert "script_exec" in names


def test_Should_not_list_script_exec_When_the_switch_is_off_in_an_opted_in_unattended_run():
    # Arrange
    caps = Capabilities.from_env(
        {
            "FREECAD_BUDDY_SCRIPT_EXEC": "0",
            "FREECAD_BUDDY_UNATTENDED": "1",
            "FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED": "1",
        }
    )

    # Act
    names = _listed_tool_names(caps)

    # Assert
    assert "script_exec" not in names


@pytest.mark.parametrize(
    ("environ", "expected_count"),
    [({}, 1), ({"FREECAD_BUDDY_SCRIPT_EXEC": "0"}, 0)],
)
def test_Should_log_the_script_exec_warning_once_When_exec_is_on(
    environ, expected_count, caplog, tmp_path
):
    # Arrange
    caps = Capabilities.from_env(environ)

    # Act
    with caplog.at_level(logging.WARNING, logger="freecad_buddy.mcp_server"):
        build_server(MethodRegistry(), caps, AuditSink(tmp_path / "audit.jsonl"))

    # Assert
    warnings = [r for r in caplog.records if r.getMessage() == SCRIPT_EXEC_WARNING]
    assert len(warnings) == expected_count


def test_Should_list_script_exec_When_the_unattended_marker_is_not_exactly_one():
    # Arrange
    caps = Capabilities.from_env({"FREECAD_BUDDY_UNATTENDED": "true"})

    # Act
    names = _listed_tool_names(caps)

    # Assert
    assert "script_exec" in names


def test_Should_not_list_script_exec_When_in_service_mode_with_every_switch_on():
    # Arrange
    environ = {"FREECAD_BUDDY_SCRIPT_EXEC": "1", "FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED": "1"}
    caps = Capabilities.from_env(environ, service_mode=True)

    # Act
    names = _listed_tool_names(caps)

    # Assert
    assert "script_exec" not in names


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
    sink.before("exec", "script_exec", "fcb-doc:abc", {"code": "1+1"})
    sink.after("exec", "script_exec", "fcb-doc:abc", {"code": "1+1"}, "OK")

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
    caps = Capabilities(script_exec=False)
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


def test_should_offer_focus_expand_depth_and_reveal_filters_when_listing_the_tree_tool():
    # Arrange
    caps = Capabilities(script_exec=False)

    # Act
    tools = {t.name: t for t in registered_tools(_registry(caps), caps)}

    # Assert
    props = tools["query_tree_summary"].inputSchema["properties"]
    assert props["depth"]["default"] == 1
    assert props["depth"]["minimum"] == 1
    assert props["focus"]["type"] == "string"
    assert props["expand"]["items"] == {"type": "string"}
    assert sorted(props["filters"]["properties"]) == ["name_pattern", "types"]
    assert props["filters"]["additionalProperties"] is False
    assert "root" not in props
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
    server = build_server(registry, Capabilities(script_exec=False), AuditSink(audit_path))
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


def _audit_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_a_call_refused_before_the_bracket_gets_one_pair_written_after_it_ran(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    seen_while_running: list[list[dict]] = []

    def _refuse():
        seen_while_running.append(_audit_records(audit_path))
        raise ValidationError("precheck refused the pad")

    server, _ = _suspect_server({"feature_pad": (True, _refuse)}, audit_path)

    result = _call_tool_via_server(server, "feature_pad", {"doc": "fcb-doc:D"})

    assert result.structuredContent["status"] == "INVALID_INPUT"
    assert seen_while_running == [[]]
    records = _audit_records(audit_path)
    assert [r["event"] for r in records] == ["mutation", "mutation"]
    assert records[0]["fingerprint_before"] is None
    assert records[1]["verify_verdict"] == "INVALID_INPUT"


def test_a_call_whose_envelope_carries_a_mutation_block_gets_no_adapter_lines(tmp_path):
    audit_path = tmp_path / "audit.jsonl"

    def _bracketed():
        envelope = _ok_envelope()
        envelope["structured_content"] = {"mutation": {"schema": "fcb.mutation/2"}}
        return envelope

    server, _ = _suspect_server({"feature_pad": (True, _bracketed)}, audit_path)

    _call_tool_via_server(server, "feature_pad", {"doc": "fcb-doc:D"})

    assert _audit_records(audit_path) == []


def test_build_server_installs_its_audit_sink_as_the_sink_run_mutation_writes_through(tmp_path):
    audit = AuditSink(tmp_path / "audit.jsonl")
    previous = confirm.set_approval_sink(None)
    try:
        build_server(MethodRegistry(), Capabilities(script_exec=False), audit)

        assert confirm.host_audit_sink() is audit
    finally:
        confirm.set_approval_sink(previous)


def test_a_script_exec_call_writes_its_before_line_before_the_code_runs(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    seen_while_running: list[list[dict]] = []

    def _exec(**_params):
        seen_while_running.append(_audit_records(audit_path))
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
    server = build_server(registry, Capabilities(script_exec=True), AuditSink(audit_path))

    _call_tool_via_server(server, "script_exec", {"doc": "fcb-doc:D", "code": "1+1"})

    assert len(seen_while_running) == 1
    assert [(r["event"], r.get("code")) for r in seen_while_running[0]] == [("exec", "1+1")]
    records = _audit_records(audit_path)
    assert [r["event"] for r in records] == ["exec", "exec"]
    assert "verify_verdict" not in records[0]
    assert records[1]["verify_verdict"] == "OK"


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
    """Build the production catalog with ``script_exec`` on a short budget and a stub body."""
    from freecad_buddy.hosts import tool_catalog

    monkeypatch.setattr(
        tool_catalog,
        "SCRIPT_EXEC_SPEC",
        dataclasses.replace(tool_catalog.SCRIPT_EXEC_SPEC, timeout_s=_BUDGET),
    )
    monkeypatch.setattr(tool_catalog.script_exec_uc, "script_exec", exec_body)
    return tool_catalog.build_inline_handlers(
        DocumentRegistry(),
        tool_catalog.ExportRegistry(),
        Capabilities(script_exec=True),
        Marshal(InlineExecutor()),
        render_port=object(),
    )


def test_script_exec_overrunning_its_budget_times_out_via_the_real_catalog(monkeypatch, release):
    registry = _catalog_with_short_exec(
        monkeypatch, lambda _registry, _doc, _code: release.wait(30.0)
    )
    started = time.monotonic()

    envelope = registry.dispatch("script_exec", {"doc": "fcb-doc:D", "code": "pass"})

    elapsed = time.monotonic() - started
    assert envelope["status"] == "TIMEOUT"
    assert envelope["detail"]["data"]["marshal_timeout"] is True
    assert elapsed < _BUDGET * 5, f"timeout took {elapsed}s for a {_BUDGET}s budget"
    assert not release.is_set(), "exec body finished on its own; the test proves nothing"


def test_only_script_exec_runs_off_the_main_thread(monkeypatch):
    """A non-exec tool must stay on the caller's thread; only ``script_exec`` may be threaded."""
    from freecad_buddy.hosts import tool_catalog

    seen: dict[str, int] = {}
    monkeypatch.setattr(
        tool_catalog.queries,
        "query_tree_summary",
        lambda *_a, **_k: {"thread": seen.setdefault("query_tree_summary", threading.get_ident())},
    )
    registry = _catalog_with_short_exec(
        monkeypatch,
        lambda _registry, _doc, _code: {
            "thread": seen.setdefault("script_exec", threading.get_ident())
        },
    )

    registry.dispatch("script_exec", {"doc": "fcb-doc:D", "code": "pass"})
    registry.dispatch("query_tree_summary", {"doc": "fcb-doc:D"})

    assert seen["script_exec"] != threading.get_ident(), "script_exec did not run on a worker"
    assert seen["query_tree_summary"] == threading.get_ident(), (
        "a non-exec tool ran off the main thread"
    )


def test_should_write_compact_json_when_an_envelope_becomes_the_text_content():
    # Arrange
    envelope = {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": {"mutation": {"changed": [{"name": "Pad", "com": [1.0, 2.0]}]}},
        "text": "Mutation committed; fingerprint 3f2a.",
    }

    # Act
    text = _to_call_result(envelope).content[0].text

    # Assert
    assert text == json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)
    assert "\n" not in text
    assert ": " not in text


def test_should_send_each_text_block_as_its_own_content_when_the_envelope_carries_them():
    # Arrange
    tree = "v [BODY] Body\n`-- v [PAD] Pad *tip"
    envelope = {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": {"doc": "fcb-doc:D", "shown": 2},
        "text": "3 objects, 2 shown.",
        "text_blocks": [tree, "second"],
    }

    # Act
    result = _to_call_result(envelope)

    # Assert
    first = json.loads(result.content[0].text)
    assert "text_blocks" not in first
    assert "text_blocks" not in result.structuredContent
    assert first == result.structuredContent
    assert [block.text for block in result.content[1:]] == [tree, "second"]
    assert all(block.type == "text" for block in result.content)
    assert "text_blocks" in envelope


def _tree_server(envelope: dict):
    registry = MethodRegistry()
    registry.register(
        RpcMethod(name="tree_tool", handler=lambda **_p: dict(envelope), structured_output=False)
    )
    return build_server(registry, Capabilities(script_exec=False), AuditSink(Path("unused.jsonl")))


def test_should_send_one_plain_text_block_when_the_tool_has_no_structured_output():
    # Arrange
    tree = "v [BODY] Body\n`-- v [PAD] Pad *tip"
    envelope = {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": {"doc": "fcb-doc:D", "total_objects": 3, "shown": 2},
        "text": "3 objects, 2 shown.",
        "text_blocks": [tree],
        "framing": {
            "fits": True,
            "ratio": 0.6068376068376068,
            "checked": "cached",
            "stale_reason": "served from cache",
        },
    }
    server = _tree_server(envelope)

    # Act
    result = _call_tool_via_server(server, "tree_tool", {})

    # Assert
    assert result.structuredContent is None
    assert result.isError is False
    assert [block.text for block in result.content] == [
        "OK: 3 objects, 2 shown.\n"
        "framing: fits, ratio 0.61, cached, served from cache\n"
        "v [BODY] Body\n"
        "`-- v [PAD] Pad *tip"
    ]


def test_should_state_the_status_and_message_when_a_plain_text_tool_fails():
    # Arrange
    envelope = {
        "schema": "fcb.result-envelope/1",
        "status": "INVALID_INPUT",
        "detail": {"code": "INVALID_INPUT", "message": "unknown object: Pad", "data": {}},
        "structured_content": {},
        "text": "",
    }
    server = _tree_server(envelope)

    # Act
    result = _call_tool_via_server(server, "tree_tool", {})

    # Assert
    assert result.isError is True
    assert [block.text for block in result.content] == ["INVALID_INPUT: unknown object: Pad"]


def _ok_envelope_with(structured: dict) -> dict:
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": "",
    }


def test_should_regenerate_the_summary_text_from_rounded_content_when_it_was_generated():
    # Arrange
    structured = {"volume_band": 0.123456789, "verdict": "OK"}
    envelope = {**_ok_envelope_with(structured), "text": summary_text(structured)}

    # Act
    result = _to_call_result(envelope)

    # Assert
    assert result.structuredContent["text"] == "verdict: OK\nvolume_band: 0.12"
    assert json.loads(result.content[0].text)["text"] == "verdict: OK\nvolume_band: 0.12"


def test_should_keep_a_hand_written_text_when_it_is_not_the_generated_summary():
    # Arrange
    envelope = {**_ok_envelope_with({"volume": 5.999999998}), "text": "Pad: volume 6.0 mm^3."}

    # Act
    result = _to_call_result(envelope)

    # Assert
    assert result.structuredContent["text"] == "Pad: volume 6.0 mm^3."


def _server_returning(envelope: dict):
    registry = MethodRegistry()
    registry.register(RpcMethod(name="stub_tool", handler=lambda **_p: dict(envelope)))
    return build_server(registry, Capabilities(script_exec=False), AuditSink(Path("unused.jsonl")))


def test_should_round_to_the_envelope_decimals_and_drop_the_key_when_a_result_is_wrapped():
    # Arrange
    envelope = {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": {
            "checks": [{"measured": 5.12345, "tolerance": {"rel": 0.005}}],
            "start": [-0.0, 1234.567891],
        },
        "text": "Shape OK.",
        "display_decimals": 4,
    }

    # Act
    result = _to_call_result(envelope)

    # Assert
    expected = {
        "checks": [{"measured": 5.1235, "tolerance": {"rel": 0.005}}],
        "start": [0.0, 1234.5679],
    }
    first = json.loads(result.content[0].text)
    assert first["structured_content"] == expected
    assert result.structuredContent["structured_content"] == expected
    assert "display_decimals" not in first
    assert "display_decimals" not in result.structuredContent
    assert envelope["structured_content"]["checks"][0]["measured"] == 5.12345


def test_should_round_to_two_decimals_when_the_envelope_carries_no_display_decimals():
    # Arrange
    envelope = _ok_envelope_with({"value": 5.999999998})

    # Act
    result = _to_call_result(envelope)

    # Assert
    assert result.structuredContent["structured_content"] == {"value": 6.0}


def test_should_keep_every_float_raw_when_the_envelope_turns_rounding_off():
    # Arrange
    envelope = {**_ok_envelope_with({"value": 5.999999998}), "display_decimals": None}

    # Act
    result = _to_call_result(envelope)

    # Assert
    assert result.structuredContent["structured_content"] == {"value": 5.999999998}
    assert "display_decimals" not in result.structuredContent


def test_should_keep_the_stamped_rounding_off_when_a_proxy_dispatches_a_freecad_envelope(
    monkeypatch,
):
    # Arrange
    from freecad_buddy.usecases import shim

    monkeypatch.setattr(shim, "display_decimals", lambda: 2)
    envelope = {**_ok_envelope_with({"value": 5.999999998}), "display_decimals": None}
    server = _server_returning(envelope)

    # Act
    result = _call_tool_via_server(server, "stub_tool", {})

    # Assert
    assert result.structuredContent["structured_content"]["value"] == 5.999999998


def test_should_follow_the_live_preference_when_it_changes_between_two_calls(monkeypatch):
    # Arrange
    from freecad_buddy.usecases import shim

    server = _server_returning(_ok_envelope_with({"value": 5.12345}))
    monkeypatch.setattr(shim, "display_decimals", lambda: 2)
    first = _call_tool_via_server(server, "stub_tool", {})
    monkeypatch.setattr(shim, "display_decimals", lambda: 4)

    # Act
    second = _call_tool_via_server(server, "stub_tool", {})

    # Assert
    assert first.structuredContent["structured_content"]["value"] == 5.12
    assert second.structuredContent["structured_content"]["value"] == 5.1235


def test_should_keep_the_stamped_decimals_when_a_proxy_dispatches_a_freecad_envelope(monkeypatch):
    # Arrange
    from freecad_buddy.usecases import shim

    monkeypatch.setattr(shim, "display_decimals", lambda: 2)
    server = _server_returning({**_ok_envelope_with({"value": 5.12345}), "display_decimals": 4})

    # Act
    result = _call_tool_via_server(server, "stub_tool", {})

    # Assert
    assert result.structuredContent["structured_content"]["value"] == 5.1235


def test_should_pass_the_live_display_precision_to_the_oracle_when_headless_verifies_a_mesh(
    monkeypatch,
):
    # Arrange
    from freecad_buddy.adapters import export_oracle, export_verdict
    from freecad_buddy.hosts import tool_catalog
    from freecad_buddy.usecases import shim

    seen = {}

    def stl_oracle(path, expected_volume, volume_band, decimals):
        seen["decimals"] = decimals
        return {"oracle": "trimesh_stl", "checks": [], "ok": True}

    self_read = {
        "structured_content": {
            "source": {"volume": 1000.0, "is_mm": True},
            "volume_band": 0.5,
            "path": "part.stl",
            "banner": {},
        }
    }
    monkeypatch.setattr(shim, "display_decimals", lambda: 4)
    monkeypatch.setattr(tool_catalog.exports, "export_self_read_stl", lambda *_a, **_k: self_read)
    monkeypatch.setattr(export_oracle, "stl_oracle", stl_oracle)
    monkeypatch.setattr(
        export_oracle.StdlibStlOracle,
        "check",
        lambda _self, _path: {"oracle": "stdlib_stl", "checks": [], "ok": True},
    )
    monkeypatch.setattr(export_verdict, "assemble_export_verdict", lambda *_a: {"status": "OK"})
    handler = tool_catalog._mesh_verify_handler(DocumentRegistry(), None, None, "stl")

    # Act
    handler(doc="fcb-doc:D", export_id="e1")

    # Assert
    assert seen["decimals"] == 4
