"""Pure tests for the sweep harness's result readers (no FreeCAD required).

The results are built by the server's own ``_to_call_result``, so a change to the wire shape of a
tool fails here before it fails a sweep run.
"""

import sys
from pathlib import Path

from mcp import types

from freecad_buddy.adapters.mcp_server import _to_call_result

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "automation"))

import run_mcp_e2e  # noqa: E402


def _envelope(status: str, *, detail=None, text_blocks=None) -> dict:
    envelope = {
        "schema": "fcb.result-envelope/1",
        "status": status,
        "detail": detail,
        "structured_content": {"doc": "fcb-doc:D", "total_objects": 3, "shown": 2},
        "text": "3 objects, 2 shown.",
    }
    if text_blocks is not None:
        envelope["text_blocks"] = text_blocks
    return envelope


def test_should_read_the_status_line_when_the_tool_sends_no_structured_content():
    # Arrange
    result = _to_call_result(_envelope("OK", text_blocks=["v [BODY] Body"]), structured=False)

    # Act
    status = run_mcp_e2e._status(result)

    # Assert
    assert status == "OK"


def test_should_read_the_refusal_status_when_a_text_only_tool_refuses():
    # Arrange
    detail = {"code": "INVALID_INPUT", "message": "unknown or stale document handle", "data": {}}
    result = _to_call_result(_envelope("INVALID_INPUT", detail=detail), structured=False)

    # Act
    status = run_mcp_e2e._status(result)

    # Assert
    assert status == "INVALID_INPUT"


def test_should_read_the_envelope_status_when_the_tool_sends_structured_content():
    # Arrange
    result = _to_call_result(_envelope("SPEC_FAILED"))

    # Act
    status = run_mcp_e2e._status(result)

    # Assert
    assert status == "SPEC_FAILED"


def test_should_return_no_status_when_the_input_schema_gate_rejects_the_call():
    # Arrange
    rejection = "Input validation error: 'max_nodes' was unexpected"
    result = types.CallToolResult(
        content=[types.TextContent(type="text", text=rejection)], isError=True
    )

    # Act
    status = run_mcp_e2e._status(result)

    # Assert
    assert status == "NO_STATUS"


def test_should_list_only_top_level_names_when_the_tree_follows_status_and_framing_lines():
    # Arrange
    tree = "v [BODY] Body\n`-- v [PAD] Pad *tip\n- [FEATURE] Box"
    envelope = _envelope("OK", text_blocks=[tree])
    envelope["framing"] = {"fits": True, "ratio": 0.6, "checked": "computed"}
    result = _to_call_result(envelope, structured=False)

    # Act
    names = run_mcp_e2e._tree_names(result)

    # Assert
    assert names == ["Body", "Box"]


def test_should_run_the_fcb_env_python_when_fcb_env_is_set(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setenv("FCB_ENV", str(tmp_path))

    # Act
    python, child = run_mcp_e2e._fcb_env()

    # Assert
    assert python == str(tmp_path / "python.exe")
    assert child["PYTHONPATH"] == str(tmp_path / "Library" / "bin")
