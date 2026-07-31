"""Confirm-gate contract tests that run without FreeCAD (external / pytest).

Covers the published ``confirm`` schema shape, the absence of ``autoApprove`` from every
published schema, the token codec's reject paths, the auto-approve posture, and the ring-import
legality of the two new confirm modules by AST. The gate's behaviour against a live document is
in ``tests/infc/test_confirm_gate.py``; nothing here needs FreeCAD.
"""

from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path

import pytest

from freecad_buddy.adapters.marshal import InlineExecutor, Marshal
from freecad_buddy.adapters.mcp_server import Capabilities, registered_tools
from freecad_buddy.hosts.headless.entry import build_registry
from freecad_buddy.usecases import confirm
from freecad_buddy.usecases.capabilities import auto_approve_enabled
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "freecad_buddy"

DOC = "fcb-doc:test"
TOOL = "feature_pad"
ARGS = {"body": "Body", "name": "Pad", "length": {"value": 5.0, "unit": "mm"}}
FINGERPRINT = "a" * 64


def _tools() -> dict:
    caps = Capabilities(allow_exec=False)
    registry = build_registry(DocumentRegistry(), caps, Marshal(InlineExecutor()))
    return {t.name: t for t in registered_tools(registry, caps)}


def _mutation_schemas() -> dict:
    return {
        name: tool.inputSchema
        for name, tool in _tools().items()
        if name.startswith(("sketch_", "feature_"))
    }


def _token(**overrides) -> str:
    payload = {
        "doc": DOC,
        "tool": TOOL,
        "args_digest": confirm.args_digest(ARGS),
        "fingerprint_before": FINGERPRINT,
        "exp": int(time.time()) + 900,
    }
    payload.update(overrides)
    return confirm.mint_preview_token(payload)


def _verify(token, **overrides):
    kwargs = {
        "tool": TOOL,
        "args": ARGS,
        "doc_handle": DOC,
        "fingerprint_now": FINGERPRINT,
    }
    kwargs.update(overrides)
    return confirm.verify_confirm({"preview_id": token}, **kwargs)


# -- published schema -------------------------------------------------------------------------


def test_every_mutation_tool_declares_the_narrowed_confirm_shape():
    schemas = _mutation_schemas()
    assert len(schemas) == 18, f"expected 18 geometry-mutation tools, got {sorted(schemas)}"
    for name, schema in schemas.items():
        block = schema["properties"]["confirm"]
        assert set(block["properties"]) == {"preview_id", "elicitation_action"}, name
        assert block["additionalProperties"] is False, name
        assert block["required"] == ["preview_id"], name
        assert block["properties"]["elicitation_action"]["enum"] == ["accept"], name


def test_auto_approve_appears_in_no_published_schema():
    """The posture is operator-set; a schema advertising it would invite a self-approving call."""
    for name, tool in _tools().items():
        text = json.dumps(tool.inputSchema)
        assert "autoApprove" not in text, f"{name} publishes autoApprove"
        assert "auto_approve" not in text, f"{name} publishes auto_approve"


def test_document_undo_is_on_the_surface_and_takes_no_confirm():
    tool = _tools()["document_undo"]
    assert "confirm" not in tool.inputSchema["properties"]
    assert tool.inputSchema["required"] == ["doc"]
    assert tool.inputSchema["additionalProperties"] is False


# -- the codec --------------------------------------------------------------------------------


def test_a_freshly_minted_token_verifies_and_reports_the_token_mode():
    record = _verify(_token())
    assert record["mode"] == "preview_token"
    assert record["tool"] == TOOL
    assert record["doc"] == DOC
    assert record["args_digest"] == confirm.args_digest(ARGS)
    assert record["fingerprint_before"] == FINGERPRINT


def test_a_missing_confirm_is_rejected():
    with pytest.raises(ValidationError, match="requires a confirm"):
        confirm.verify_confirm(
            None, tool=TOOL, args=ARGS, doc_handle=DOC, fingerprint_now=FINGERPRINT
        )


@pytest.mark.parametrize(
    "value",
    [{}, {"preview_id": 7}, {"preview_id": None}, "fcb-preview:x", 7],
)
def test_a_malformed_confirm_is_rejected(value):
    with pytest.raises(ValidationError):
        confirm.verify_confirm(
            value, tool=TOOL, args=ARGS, doc_handle=DOC, fingerprint_now=FINGERPRINT
        )


def test_a_non_accept_elicitation_action_is_rejected():
    with pytest.raises(ValidationError, match="elicitation_action"):
        confirm.verify_confirm(
            {"preview_id": _token(), "elicitation_action": "decline"},
            tool=TOOL,
            args=ARGS,
            doc_handle=DOC,
            fingerprint_now=FINGERPRINT,
        )


def test_a_client_supplied_autoapprove_is_rejected_not_honoured():
    """The flag is not a wire field, so a confirm carrying it fails the shape check outright."""
    with pytest.raises(ValidationError, match="does not declare"):
        confirm.verify_confirm(
            {"autoApprove": True},
            tool=TOOL,
            args=ARGS,
            doc_handle=DOC,
            fingerprint_now=FINGERPRINT,
        )


def test_a_forged_signature_is_rejected():
    body = _token().rsplit(".", 1)[0]
    with pytest.raises(ValidationError, match="invalid signature"):
        _verify(f"{body}.{'A' * 43}")


def test_a_payload_edited_after_signing_is_rejected():
    """Re-encoding a tampered payload without the secret cannot produce a matching signature."""
    import base64

    prefix, rest = _token().split(":", 1)
    encoded_body, signature = rest.split(".", 1)
    payload = json.loads(base64.urlsafe_b64decode(encoded_body + "==").decode("utf-8"))
    payload["tool"] = "feature_pocket"
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    tampered = base64.urlsafe_b64encode(body).decode().rstrip("=")
    with pytest.raises(ValidationError, match="invalid signature"):
        _verify(f"{prefix}:{tampered}.{signature}")


def test_an_expired_token_is_rejected_naming_the_expiry():
    with pytest.raises(ValidationError, match="expired"):
        _verify(_token(exp=int(time.time()) - 1))


def test_a_token_for_another_document_is_rejected_naming_the_document():
    with pytest.raises(ValidationError, match="different document"):
        _verify(_token(doc="fcb-doc:other"))


def test_a_token_for_another_tool_is_rejected_naming_the_operation():
    with pytest.raises(ValidationError, match="feature_pad"):
        _verify(_token(), tool="feature_pocket")


def test_a_token_for_other_arguments_is_rejected():
    with pytest.raises(ValidationError, match="different arguments"):
        _verify(_token(), args={**ARGS, "length": {"value": 9.0, "unit": "mm"}})


def test_a_changed_document_is_rejected_naming_the_state_not_the_token():
    with pytest.raises(ValidationError, match="changed since the preview") as excinfo:
        _verify(_token(), fingerprint_now="b" * 64)
    assert "signature" not in str(excinfo.value)


def test_the_expiry_is_checked_against_a_caller_supplied_clock():
    token = _token(exp=1_000)
    assert _verify(token, now=999.0)["mode"] == "preview_token"
    with pytest.raises(ValidationError, match="expired"):
        _verify(token, now=1_001.0)


def test_args_digest_ignores_key_order_but_not_values():
    assert confirm.args_digest({"a": 1, "b": 2}) == confirm.args_digest({"b": 2, "a": 1})
    assert confirm.args_digest({"a": 1}) != confirm.args_digest({"a": 2})


# -- the operator posture ---------------------------------------------------------------------


def test_capabilities_reads_the_auto_approve_flag_exactly_one():
    assert Capabilities.from_env({"FREECAD_BUDDY_AUTO_APPROVE": "1"}).auto_approve is True
    assert Capabilities.from_env({"FREECAD_BUDDY_AUTO_APPROVE": "0"}).auto_approve is False
    assert Capabilities.from_env({"FREECAD_BUDDY_AUTO_APPROVE": "true"}).auto_approve is False
    assert Capabilities.from_env({}).auto_approve is False
    assert auto_approve_enabled(Capabilities(allow_exec=False, auto_approve=True)) is True


def test_the_auto_approve_posture_approves_without_a_token():
    record = confirm.verify_confirm(
        None,
        tool=TOOL,
        args=ARGS,
        doc_handle=DOC,
        fingerprint_now=None,
        auto_approve=True,
    )
    assert record["mode"] == "auto_approve"
    assert record["args_digest"] == confirm.args_digest(ARGS)


def test_building_the_catalog_applies_the_posture_to_the_process():
    previous = confirm.set_auto_approve(False)
    try:
        build_registry(
            DocumentRegistry(),
            Capabilities(allow_exec=False, auto_approve=True),
            Marshal(InlineExecutor()),
        )
        assert confirm.auto_approve() is True
        build_registry(
            DocumentRegistry(),
            Capabilities(allow_exec=False, auto_approve=False),
            Marshal(InlineExecutor()),
        )
        assert confirm.auto_approve() is False
    finally:
        confirm.set_auto_approve(previous)


def test_building_the_readonly_profile_does_not_touch_the_posture():
    """The profile build wires handlers; it must not re-arm or disarm the process gate.

    ``build_readonly_profile`` builds the full catalog internally, so a posture applied on every
    build would let a profile construction with unrelated capabilities silently flip the gate for
    the mutation surface the main host is already serving.
    """
    from freecad_buddy.hosts.tool_catalog import build_readonly_profile
    from freecad_buddy.usecases.exports import ExportRegistry

    previous = confirm.set_auto_approve(False)
    try:
        build_readonly_profile(
            DocumentRegistry(),
            ExportRegistry(),
            Capabilities(allow_exec=False, auto_approve=True),
            Marshal(InlineExecutor()),
        )
        assert confirm.auto_approve() is False
    finally:
        confirm.set_auto_approve(previous)


# -- ring legality ----------------------------------------------------------------------------


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_contracts_confirm_imports_stdlib_only():
    for module in _imported_modules(SRC / "contracts" / "confirm.py"):
        root = module.split(".")[0]
        assert root in sys.stdlib_module_names or module.startswith("freecad_buddy.contracts"), (
            f"contracts/confirm.py imports {module}"
        )


def test_usecases_confirm_imports_nothing_outward_and_nothing_third_party():
    for module in _imported_modules(SRC / "usecases" / "confirm.py"):
        root = module.split(".")[0]
        assert not module.startswith(("freecad_buddy.adapters", "freecad_buddy.hosts")), (
            f"usecases/confirm.py imports outward: {module}"
        )
        assert (
            root in sys.stdlib_module_names
            or module.startswith("freecad_buddy.")
            or root in {"FreeCAD", "Part", "Sketcher", "PartDesign", "Mesh", "MeshPart"}
        ), f"usecases/confirm.py imports third-party {module}"
