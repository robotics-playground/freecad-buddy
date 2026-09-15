"""Scripted ``Backend``: replay a recorded plan over the read-only tool surface.

The offline actor-run needs a deterministic driver, not an agent. This module is that driver: each
case carries a recorded plan — an ordered list of ``(tool, args)`` calls followed by the final
answer text — and the backend dispatches the calls through the actor's ``invoke`` and returns the
answer. No loop decides anything; the plan is data.

That is the whole point. An agent loop in ``benchmarks/`` would be the thing the architecture
forbids (AD-35): a gate runner **drives** an actor, it never **is** one. The live path is an
operator running their own agent against the bridge over MCP, and this double stands in for it
offline so the escalation, the report build and the Wilson CI are exercised end-to-end without a
model, a credential, or a reasoning loop anywhere in this repository.

``benchmarks/`` is non-ring tooling, so reading the shared tool catalog here is legal — this module
is the composition layer that resolves the read-only allow-list, exactly as ``harness/actor.py``
composes the profile registry.
"""

from __future__ import annotations

from freecad_buddy.hosts.tool_catalog import READ_ONLY_PROFILE, tool_specs

from benchmarks.harness.actor import AnswerResult, ToolInvoker

# One recorded step: the tool to call and the arguments to call it with.
PlanStep = tuple[str, dict]

# A case's recording: the steps to dispatch, then the answer text to return.
Plan = tuple[list[PlanStep], str]


def readonly_tool_names() -> list[str]:
    """The read-only allow-list, resolved from the shared catalog."""
    return [s.name for s in tool_specs() if s.name in READ_ONLY_PROFILE]


class ScriptedBackend:
    """A ``Backend`` that replays one recorded plan per case.

    ``plans`` maps a case id to its ``([(tool, args), ...], final_answer)`` recording. A case with
    no recording dispatches nothing and answers with an empty string — an empty final answer the
    grader fails honestly, never an exception that would read as a harness defect.

    A step naming a tool outside the read-only allow-list is refused rather than dispatched: the
    offline double must exercise the same surface the live path is limited to, or the run proves
    nothing about that surface.
    """

    def __init__(self, plans: dict[str, Plan]) -> None:
        self._plans = plans
        self._allowed = set(readonly_tool_names())

    def answer(
        self, case_id: str, question: str, tools: list[str], invoke: ToolInvoker
    ) -> AnswerResult:
        """Dispatch the case's recorded steps, then return its recorded answer."""
        steps, final_answer = self._plans.get(case_id, ([], ""))
        for tool, args in steps:
            if tool not in self._allowed:
                raise ValueError(
                    f"scripted plan for {case_id} names {tool!r}, which is outside the read-only "
                    f"allow-list; the offline double may only drive the surface the live path has"
                )
            invoke(tool, args)
        return AnswerResult(final_answer=final_answer, tool_calls=[])


__all__ = ["Plan", "PlanStep", "ScriptedBackend", "readonly_tool_names"]
