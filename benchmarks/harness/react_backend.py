"""ReAct ``Backend`` wrapper: plug the ring-pure ReAct adapter into the 2.2 actor-run.

The adapter (``adapters/react_adapter.py``) is ring-pure and takes its tool schemas as data; this
module — ``benchmarks/`` non-ring tooling, like ``harness/actor.py`` — is the composition layer
that reads the read-only schemas from ``hosts/tool_catalog`` (the one place allowed to import a
host), filters them to the ``READ_ONLY_PROFILE`` allow-list, and hands them to the adapter. It
wires the adapter's ``dispatch`` to the actor's ``invoke`` so the ReAct path drives the identical
tool registry the 2.2 actor uses. ``ScriptedChat`` is the offline chat double: it replays recorded
assistant turns per case (fresh per repeat so a repeated case is not starved of turns).
"""

from __future__ import annotations

from freecad_buddy.adapters.react_adapter import ReactAdapter
from freecad_buddy.hosts.tool_catalog import READ_ONLY_PROFILE, tool_specs

from benchmarks.harness.actor import AnswerResult, ToolInvoker


def readonly_tool_schemas() -> dict[str, dict]:
    """The read-only allow-list's tool name → ``input_schema`` map, from the shared catalog."""
    return {s.name: s.input_schema for s in tool_specs() if s.name in READ_ONLY_PROFILE}


def readonly_tool_descriptions() -> dict[str, str]:
    """The read-only allow-list's tool name → description map, from the shared catalog."""
    return {s.name: s.description for s in tool_specs() if s.name in READ_ONLY_PROFILE}


class ScriptedChat:
    """Offline chat double: replays a per-case list of recorded assistant turns.

    ``scripts`` maps a case id to the ordered assistant texts the model would emit for that case.
    Each ``for_case`` returns a fresh callable holding its own turn cursor, so grading a case ×R
    replays the full recording every repeat instead of exhausting one shared cursor. A call past the
    end of the recording returns an empty string (an empty final answer), never raising.
    """

    def __init__(self, scripts: dict[str, list[str]]) -> None:
        self._scripts = scripts

    def for_case(self, case_id: str):
        turns = list(self._scripts.get(case_id, []))
        cursor = {"i": 0}

        def chat(_messages: list[dict]) -> str:
            i = cursor["i"]
            cursor["i"] = i + 1
            return turns[i] if i < len(turns) else ""

        return chat


class ReactBackend:
    """A 2.2 ``Backend`` adapting ``ReactAdapter`` to ``answer(case_id, question, tools, invoke)``.

    ``chat_for`` yields the per-case chat callable (the ``ScriptedChat.for_case`` double offline, a
    live OpenAI-compatible client when operator-supplied). The read-only schemas + descriptions are
    read from the shared catalog once and injected into every adapter, so the ReAct path renders the
    same surface the production server exposes.
    """

    def __init__(self, chat_for) -> None:
        self._chat_for = chat_for
        self._schemas = readonly_tool_schemas()
        self._descriptions = readonly_tool_descriptions()

    def answer(
        self, case_id: str, question: str, tools: list[str], invoke: ToolInvoker
    ) -> AnswerResult:
        adapter = ReactAdapter(
            tool_schemas=self._schemas,
            tool_descriptions=self._descriptions,
            chat=self._chat_for(case_id),
            dispatch=invoke,
        )
        result = adapter.answer(question)
        return AnswerResult(final_answer=result.final_answer, tool_calls=[])


__all__ = [
    "ReactBackend",
    "ScriptedChat",
    "readonly_tool_descriptions",
    "readonly_tool_schemas",
]
