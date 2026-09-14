"""Ring-pure ReAct adapter: drive an OpenAI-compatible model over the read-only tool surface.

The adapter renders the injected tool schemas + descriptions into a system prompt, runs the
ReAct loop (the model emits one fenced ```json {tool, args}``` block → the adapter parses it →
dispatches through the injected registry callable → appends the ``ResultEnvelope.text`` mirror →
repeats until the model emits prose with no tool-call block), and enforces the parser/safety
contract. It imports ``contracts`` (for the typed ``INVALID_INPUT`` envelope) + stdlib only; the
chat-completion transport and the tool-dispatch callable are both injected, so the adapter carries
no HTTP/model dependency and is exercised offline against a scripted chat double.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from freecad_buddy.contracts import ResultEnvelope, mirror_text

ChatCompletion = Callable[[list[dict]], str]
ToolInvoker = Callable[[str, dict], dict]

DEFAULT_MAX_ITERATIONS = 8

_FENCED_JSON = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)

_MALFORMED_REPROMPT = (
    "Your tool call was malformed. Resend exactly one fenced ```json block containing a JSON "
    'object of the form {"tool": "<name>", "args": {...}}, or give your final answer as plain '
    "prose with no fenced block."
)
_QUESTION_REPROMPT = (
    "Do not ask the user a question. Either call a read-only tool via one fenced ```json block "
    'of the form {"tool": "<name>", "args": {...}}, or give your final answer as prose.'
)


@dataclass
class ReactResult:
    """The adapter's outcome: the final answer, the recorded dispatches, and an optional error.

    ``final_answer`` is the model's closing prose, or ``None`` when the loop terminated without one
    (malformed twice, question twice, or the iteration cap). ``tool_calls`` is the ordered list of
    ``(name, args)`` the adapter dispatched. ``error`` carries the typed ``INVALID_INPUT`` envelope
    on the malformed-terminal path (else ``None``) so the caller can observe the client-contract
    failure.
    """

    final_answer: str | None
    tool_calls: list[tuple[str, dict]] = field(default_factory=list)
    error: ResultEnvelope | None = None


def _render_system_prompt(tool_schemas: dict[str, dict], tool_descriptions: dict[str, str]) -> str:
    """Render the read-only tool surface into the ReAct system prompt from the injected schemas."""
    lines = [
        "You answer questions about a FreeCAD model using read-only tools.",
        "",
        "To call a tool, emit exactly one fenced json block of the form:",
        "```json",
        '{"tool": "<name>", "args": {...}}',
        "```",
        "Emit at most one tool call per turn. When you are done, reply with your final answer as "
        "plain prose and no fenced block. Never ask the user a question.",
        "",
        "Available tools:",
    ]
    for name in sorted(tool_schemas):
        description = tool_descriptions.get(name, "")
        schema = json.dumps(tool_schemas[name], sort_keys=True)
        lines.append(f"- {name}: {description}")
        lines.append(f"  input_schema: {schema}")
    return "\n".join(lines)


def _last_fenced_block(text: str) -> str | None:
    """The content of the last fenced ```json block in ``text``, or ``None`` if there is none."""
    matches = _FENCED_JSON.findall(text)
    return matches[-1] if matches else None


def _parse_tool_call(block: str) -> tuple[str, dict] | None:
    """Parse a fenced-block body into ``(tool, args)`` if it is a well-formed tool-call shape.

    A well-formed shape is a JSON object with a string ``tool`` and an ``args`` that is a dict or
    absent (defaulting to ``{}``). The allow-list is NOT consulted here — an unknown tool name is
    still a valid shape and is dispatched through the registry. Returns ``None`` when the body is
    unparseable JSON, not an object, or has a missing/non-string ``tool``.
    """
    try:
        payload = json.loads(block)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    tool = payload.get("tool")
    if not isinstance(tool, str):
        return None
    args = payload.get("args", {})
    if not isinstance(args, dict):
        return None
    return tool, args


def _is_question(text: str) -> bool:
    """Whether ``text`` reads as a question to the user rather than a final answer."""
    return "?" in text


def _malformed_envelope() -> ResultEnvelope:
    """The typed terminal ``INVALID_INPUT`` envelope for a twice-malformed tool call."""
    structured = {"reason": "tool call was malformed after one re-prompt"}
    return {
        "schema": "fcb.result-envelope/1",
        "status": "INVALID_INPUT",
        "detail": {
            "code": "invalid_input.malformed_tool_call",
            "message": "tool call was malformed after one re-prompt",
        },
        "structured_content": structured,
        "text": mirror_text(structured),
    }


def _dispatch_mirror(envelope: dict) -> str:
    """The transcript mirror for a dispatched envelope.

    Returns the envelope's own ``text`` mirror. When the dispatch did not succeed and that mirror
    carries no recovery signal, prepends the status and ``detail.message`` so the model can tell the
    call failed and why (e.g. an unknown tool name) and recover on the next turn.
    """
    text = envelope.get("text", "")
    status = envelope.get("status")
    if status in (None, "OK"):
        return text
    detail = envelope.get("detail") or {}
    message = detail.get("message", "")
    reason = f"[{status}] {message}".rstrip()
    return f"{reason}\n{text}" if text else reason


class ReactAdapter:
    """Runs the ReAct loop over an injected chat transport and read-only tool registry."""

    def __init__(
        self,
        tool_schemas: dict[str, dict],
        tool_descriptions: dict[str, str],
        chat: ChatCompletion,
        dispatch: ToolInvoker,
        *,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self._chat = chat
        self._dispatch = dispatch
        self._max_iterations = max_iterations
        self._system_prompt = _render_system_prompt(tool_schemas, tool_descriptions)

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    def answer(self, question: str) -> ReactResult:
        """Drive the model to a final answer, dispatching each tool call through the registry.

        A missing fenced block ends the loop with the model's prose as the final answer. A
        well-formed tool call (any string ``tool``) is dispatched and its mirror appended, then the
        loop continues — an unknown tool yields the registry's typed ``INVALID_INPUT`` mirror, from
        which the model may recover. A malformed block re-prompts once, then terminates with the
        typed ``INVALID_INPUT`` envelope surfaced on ``ReactResult.error``. A question to the user
        re-prompts once, then terminates with ``final_answer=None``.
        """
        messages: list[dict] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": question},
        ]
        tool_calls: list[tuple[str, dict]] = []
        malformed_reprompted = False
        question_reprompted = False

        for _ in range(self._max_iterations):
            assistant_text = self._chat(messages) or ""
            messages.append({"role": "assistant", "content": assistant_text})
            block = _last_fenced_block(assistant_text)

            if block is None:
                if _is_question(assistant_text):
                    if question_reprompted:
                        return ReactResult(final_answer=None, tool_calls=tool_calls)
                    question_reprompted = True
                    messages.append({"role": "user", "content": _QUESTION_REPROMPT})
                    continue
                return ReactResult(final_answer=assistant_text, tool_calls=tool_calls)

            parsed = _parse_tool_call(block)
            if parsed is None:
                if malformed_reprompted:
                    return ReactResult(
                        final_answer=None,
                        tool_calls=tool_calls,
                        error=_malformed_envelope(),
                    )
                malformed_reprompted = True
                messages.append({"role": "user", "content": _MALFORMED_REPROMPT})
                continue

            name, args = parsed
            tool_calls.append((name, args))
            envelope = self._dispatch(name, args)
            messages.append({"role": "user", "content": _dispatch_mirror(envelope)})

        return ReactResult(final_answer=None, tool_calls=tool_calls)


__all__ = [
    "ChatCompletion",
    "ReactAdapter",
    "ReactResult",
    "ToolInvoker",
    "DEFAULT_MAX_ITERATIONS",
]
