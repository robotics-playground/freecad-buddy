"""ReAct adapter contract tests (external / pytest).

Drive ``ReactAdapter`` against a ``ScriptedChat`` double replaying recorded assistant turns, with
``dispatch`` wired to a fake registry. Cover the I/O matrix rows: a well-formed call dispatches +
the mirror is appended; a final-answer turn ends the loop; a malformed block re-prompts exactly
once then terminates with the typed ``INVALID_INPUT`` on ``ReactResult.error``; an unknown/
off-profile tool is dispatched through the registry and the loop CONTINUES (recovery); a question
to the user re-prompts once; the iteration cap yields ``final_answer=None``; the system prompt
renders the injected schemas; and the prompt built from the REAL read-only schemas carries no
geometry-mutation tool.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from benchmarks.harness.react_backend import readonly_tool_schemas  # noqa: E402
from freecad_buddy.adapters.react_adapter import ReactAdapter, ReactResult  # noqa: E402

_TOOL_SCHEMAS = {
    "query_tree_summary": {
        "type": "object",
        "properties": {"doc": {"type": "string"}, "max_nodes": {"type": "integer"}},
        "required": ["doc"],
    },
    "verify_recompute": {
        "type": "object",
        "properties": {"doc": {"type": "string"}},
        "required": ["doc"],
    },
}
_TOOL_DESCRIPTIONS = {
    "query_tree_summary": "Bounded feature-tree summary.",
    "verify_recompute": "Recompute and report failing objects.",
}

_GEOMETRY_MUTATION_TOOLS = frozenset(
    {
        "sketch_create",
        "sketch_edit",
        "feature_pad",
        "feature_pocket",
        "preview_apply",
        "document_create",
        "document_save",
        "debug_exec",
    }
)


class _ScriptedChat:
    """Replays a fixed list of assistant turns; records the message list handed to each call."""

    def __init__(self, turns: list[str]) -> None:
        self._turns = turns
        self._i = 0
        self.calls: list[list[dict]] = []

    def __call__(self, messages: list[dict]) -> str:
        self.calls.append([dict(m) for m in messages])
        turn = self._turns[self._i] if self._i < len(self._turns) else ""
        self._i += 1
        return turn


def _ok_envelope(name: str) -> dict:
    structured = {"tool": name, "result": "ok"}
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": {"code": "ok", "message": ""},
        "structured_content": structured,
        "text": f"{name} OK",
    }


class _RecordingDispatch:
    """Dispatch double recording every ``(name, args)`` and returning an OK mirror envelope."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, name: str, args: dict) -> dict:
        self.calls.append((name, args))
        return _ok_envelope(name)


def _adapter(turns: list[str], dispatch=None, **kw) -> tuple[ReactAdapter, _RecordingDispatch]:
    dispatch = dispatch or _RecordingDispatch()
    adapter = ReactAdapter(
        tool_schemas=_TOOL_SCHEMAS,
        tool_descriptions=_TOOL_DESCRIPTIONS,
        chat=_ScriptedChat(turns),
        dispatch=dispatch,
        **kw,
    )
    return adapter, dispatch


def test_well_formed_call_dispatches_and_appends_mirror():
    turns = [
        '```json\n{"tool": "query_tree_summary", "args": {"doc": "d"}}\n```',
        "Pad is in error.",
    ]
    adapter, dispatch = _adapter(turns)
    result = adapter.answer("which object is broken?")
    assert result.final_answer == "Pad is in error."
    assert result.error is None
    assert dispatch.calls == [("query_tree_summary", {"doc": "d"})]
    assert result.tool_calls == [("query_tree_summary", {"doc": "d"})]


def test_final_answer_ends_the_loop():
    adapter, dispatch = _adapter(["No tool needed. The answer is Pad."])
    result = adapter.answer("q")
    assert result.final_answer == "No tool needed. The answer is Pad."
    assert dispatch.calls == []


def test_malformed_reprompts_once_then_typed_invalid_input():
    chat = _ScriptedChat(
        [
            "```json\n{not valid json}\n```",
            "```json\n{still not valid}\n```",
        ]
    )
    adapter = ReactAdapter(
        tool_schemas=_TOOL_SCHEMAS,
        tool_descriptions=_TOOL_DESCRIPTIONS,
        chat=chat,
        dispatch=_RecordingDispatch(),
    )
    result = adapter.answer("q")
    assert result.final_answer is None
    assert isinstance(result.error, dict)
    assert result.error["status"] == "INVALID_INPUT"
    assert result.error["detail"]["code"] == "invalid_input.malformed_tool_call"
    # Exactly one re-prompt: two assistant turns consumed, and the re-prompt is in the transcript.
    assert len(chat.calls) == 2
    reprompts = [
        m
        for msgs in chat.calls
        for m in msgs
        if m["role"] == "user" and "malformed" in m["content"]
    ]
    assert len(reprompts) == 1


def test_malformed_then_recovers_is_not_terminal():
    turns = [
        "```json\n{bad}\n```",
        '```json\n{"tool": "verify_recompute", "args": {"doc": "d"}}\n```',
        "Pad failed.",
    ]
    adapter, dispatch = _adapter(turns)
    result = adapter.answer("q")
    assert result.final_answer == "Pad failed."
    assert result.error is None
    assert dispatch.calls == [("verify_recompute", {"doc": "d"})]


def test_unknown_tool_dispatches_and_loop_continues():
    turns = [
        '```json\n{"tool": "query_full_tree", "args": {"doc": "d"}}\n```',
        "Recovered: Pad is in error.",
    ]
    dispatch = _RecordingDispatch()
    adapter, _ = _adapter(turns, dispatch=dispatch)
    result = adapter.answer("q")
    # An unknown/off-profile tool is a valid SHAPE: dispatched through the registry, mirror
    # appended, loop continues so the model recovers on the next turn. NOT the terminal path.
    assert dispatch.calls == [("query_full_tree", {"doc": "d"})]
    assert result.final_answer == "Recovered: Pad is in error."
    assert result.error is None


def test_question_to_user_reprompts_once_then_no_answer():
    chat = _ScriptedChat(
        [
            "Which document should I inspect?",
            "And which object did you mean?",
        ]
    )
    adapter = ReactAdapter(
        tool_schemas=_TOOL_SCHEMAS,
        tool_descriptions=_TOOL_DESCRIPTIONS,
        chat=chat,
        dispatch=_RecordingDispatch(),
    )
    result = adapter.answer("q")
    assert result.final_answer is None
    assert result.error is None
    reprompts = [
        m
        for msgs in chat.calls
        for m in msgs
        if m["role"] == "user" and "Do not ask the user a question" in m["content"]
    ]
    assert len(reprompts) == 1


def test_max_iteration_cap_yields_no_final_answer():
    tool_turn = '```json\n{"tool": "verify_recompute", "args": {"doc": "d"}}\n```'
    adapter, dispatch = _adapter([tool_turn] * 20, max_iterations=3)
    result = adapter.answer("q")
    assert result.final_answer is None
    assert len(dispatch.calls) == 3


def test_system_prompt_renders_injected_schemas():
    adapter, _ = _adapter(["done"])
    prompt = adapter.system_prompt
    for name in _TOOL_SCHEMAS:
        assert name in prompt
    # A schema property from an injected schema is rendered into the prompt.
    assert "max_nodes" in prompt


def test_prompt_from_real_readonly_schemas_has_no_geometry_mutation_tool():
    schemas = readonly_tool_schemas()
    descriptions = {name: "" for name in schemas}
    adapter = ReactAdapter(
        tool_schemas=schemas,
        tool_descriptions=descriptions,
        chat=_ScriptedChat(["done"]),
        dispatch=_RecordingDispatch(),
    )
    prompt = adapter.system_prompt

    from freecad_buddy.hosts.tool_catalog import READ_ONLY_PROFILE, tool_specs

    excluded_mutating = {
        spec.name for spec in tool_specs() if spec.mutating
    } - READ_ONLY_PROFILE
    # document_open/close are the only mutating tools deliberately in the profile (geometry-inert);
    # every other mutating tool the catalog defines must be excluded and unrenderable.
    assert excluded_mutating, "expected at least one excluded mutating tool"
    for mutation_tool in excluded_mutating | _GEOMETRY_MUTATION_TOOLS:
        assert mutation_tool not in schemas
        assert mutation_tool not in prompt
    # The read-only queries the assistant needs ARE present.
    assert "query_tree_summary" in prompt
    assert "verify_recompute" in prompt


def test_result_is_dataclass_with_error_field():
    result = ReactResult(final_answer="x")
    assert result.error is None
    assert result.tool_calls == []


class _FailingDispatch:
    """Dispatch double returning a typed INVALID_INPUT unknown-method envelope for any call."""

    def __call__(self, name: str, args: dict) -> dict:
        return {
            "schema": "fcb.result-envelope/1",
            "status": "INVALID_INPUT",
            "detail": {"code": "INVALID_INPUT", "message": f"unknown method: {name}"},
            "structured_content": {},
            "text": "{}",
        }


def test_failed_dispatch_mirror_carries_recovery_signal():
    turns = ['```json\n{"tool": "bogus_tool", "args": {}}\n```', "recovered final answer"]
    chat = _ScriptedChat(turns)
    adapter = ReactAdapter(
        tool_schemas=_TOOL_SCHEMAS,
        tool_descriptions=_TOOL_DESCRIPTIONS,
        chat=chat,
        dispatch=_FailingDispatch(),
    )
    result = adapter.answer("q")

    assert result.final_answer == "recovered final answer"
    # The second chat call sees the dispatched mirror; on a non-OK status it must carry the status
    # and detail.message so the model can recover, not just the empty "{}" text mirror.
    recovery_turn_messages = chat.calls[1]
    mirror = recovery_turn_messages[-1]["content"]
    assert "INVALID_INPUT" in mirror
    assert "unknown method: bogus_tool" in mirror
