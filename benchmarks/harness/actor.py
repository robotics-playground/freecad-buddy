"""Actor-loop primitives that drive a question through the read-only tool surface.

The ``Backend`` protocol is the seam between an eval question and a final answer: given the
question, the names of the available read-only tools, and an ``invoke`` callable that dispatches
a tool through the profile registry, a backend returns its final answer plus the tool calls it
made. ``Actor`` owns the profile ``MethodRegistry``, exposes the tool names, records every
dispatch, and returns the backend's answer alongside the recorded calls so the harness can grade
the answer and assert on the tool surface actually used (e.g. summarized-tree, not a raw dump).

``ScriptedBackend`` is the offline test double: it replays a recorded answer per question id and
the tool names that answer was derived from, so the whole harness — grader wiring, escalation,
report build — runs deterministically in CI without a live model. A live backend (Claude Code /
Desktop over MCP) plugs into the same ``Backend`` protocol and is operator-gated; it is never
constructed in unattended CI.

This module lives in ``benchmarks/`` (outermost, non-ring external tooling) because it imports
the read-only profile builder from ``hosts/tool_catalog`` and an adapter may not import a host.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol


@dataclass(frozen=True)
class ToolCall:
    """One tool dispatch the actor recorded: the tool name and the arguments it was called with."""

    name: str
    args: dict


@dataclass(frozen=True)
class AnswerResult:
    """A backend's response to one question: its final answer text and the tool calls it made.

    ``final_answer`` is ``None`` when the backend produced no parseable final answer — the harness
    grades that as a typed failure, never a crash. ``tool_calls`` is the ordered list of dispatches
    the backend requested through ``invoke``.
    """

    final_answer: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


ToolInvoker = Callable[[str, dict], dict]


class Backend(Protocol):
    """Drive a case's question to a final answer over the read-only tool surface.

    ``case_id`` is the stable identifier of the case under evaluation (so a recorded double can key
    its reply); ``tools`` is the list of available tool names (the read-only allow-list);
    ``invoke`` dispatches a named tool with its arguments and returns the tool's result envelope. A
    live model-backed backend runs its own reasoning loop here; the scripted double replays a
    recording.
    """

    def answer(
        self, case_id: str, question: str, tools: list[str], invoke: ToolInvoker
    ) -> AnswerResult: ...


class Actor:
    """Runs a ``Backend`` against a read-only profile registry, recording every tool dispatch."""

    def __init__(self, registry) -> None:
        self._registry = registry

    def tool_names(self) -> list[str]:
        return self._registry.names()

    def run(self, backend: Backend, case_id: str, question: str) -> AnswerResult:
        """Drive ``backend`` for one case; return its answer with the calls it made recorded.

        The ``invoke`` handed to the backend dispatches through the profile registry (the same
        surface production uses) and appends each call to the recorded list, so the returned
        ``AnswerResult.tool_calls`` always reflects what the backend actually invoked — the harness
        asserts on it (summarized-tree used, no raw dump).
        """
        recorded: list[ToolCall] = []

        def invoke(name: str, args: dict) -> dict:
            recorded.append(ToolCall(name=name, args=dict(args)))
            return self._registry.dispatch(name, args)

        result = backend.answer(case_id, question, self.tool_names(), invoke)
        merged = list(recorded)
        merged.extend(c for c in result.tool_calls if c not in recorded)
        return AnswerResult(final_answer=result.final_answer, tool_calls=merged)


class ScriptedBackend:
    """Offline ``Backend`` double: replays a recorded (answer, tool-call names) per case id.

    ``script`` maps a case id to ``{"answer": str | None, "tools": [name, ...]}``. On ``answer``
    the backend invokes each named tool in order (through the actor's ``invoke``, so the dispatch
    is real and recorded) and returns the recorded answer. A case id absent from the script yields
    a ``None`` final answer (the malformed/no-answer path). Args passed to each tool are empty by
    default; a script entry may carry ``"args": {name: {...}}`` to drive a specific dispatch.
    """

    def __init__(self, script: dict) -> None:
        self._script = script

    def answer(
        self, case_id: str, question: str, tools: list[str], invoke: ToolInvoker
    ) -> AnswerResult:
        entry = self._script.get(case_id)
        if entry is None:
            return AnswerResult(final_answer=None, tool_calls=[])
        args_by_tool = entry.get("args", {})
        for name in entry.get("tools", []):
            if name in tools:
                invoke(name, args_by_tool.get(name, {}))
        return AnswerResult(final_answer=entry.get("answer"), tool_calls=[])


__all__ = [
    "AnswerResult",
    "Actor",
    "Backend",
    "ScriptedBackend",
    "ToolCall",
    "ToolInvoker",
]
