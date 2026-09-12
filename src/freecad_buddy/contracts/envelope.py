"""Result envelope: the shape every tool/RPC/job/harness result returns.

``mirror_text`` is the single generator of the human-readable text mirror so
``ResultEnvelope.text`` can never diverge from ``structured_content``.

``framing_warning`` is the single generator of the framing warning sentence, for the same
reason: a sentence each tool appended for itself would drift tool by tool, and an agent that
learned to recognize one wording would miss the others.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from freecad_buddy.contracts.render import FramingVerdict
from freecad_buddy.contracts.status import ErrorDetail, TerminalStatus


class ImageRef(TypedDict, total=False):
    kind: Literal["resource_link", "inline"]
    uri: str
    mime_type: str
    data_b64: str
    audience: list[str]
    label: str


class ResultEnvelope(TypedDict, total=False):
    schema: Literal["fcb.result-envelope/1"]
    status: TerminalStatus  # required
    detail: ErrorDetail | None  # required non-null unless status == "OK"
    structured_content: dict  # required
    text: str  # required; human-readable mirror of structured_content
    images: list[ImageRef]
    framing: FramingVerdict | None


def summary_text(structured_content: dict) -> str:
    """Compact human mirror of ``structured_content``: one ``key: value`` line per top-level key.

    Scalars render inline; a nested dict renders ``key: {N fields}`` and a list ``key: [N items]``
    — a signal of shape, never a full JSON dump.
    """
    lines = []
    for key in sorted(structured_content):
        value = structured_content[key]
        if isinstance(value, dict):
            lines.append(f"{key}: {{{len(value)} fields}}")
        elif isinstance(value, list):
            lines.append(f"{key}: [{len(value)} items]")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def mirror_text(structured_content: dict) -> str:
    """Backward-compatible alias of ``summary_text`` (the generic fallback mirror)."""
    return summary_text(structured_content)


def framing_warning(framing: FramingVerdict | None) -> str | None:
    """The one warning sentence a ``FramingVerdict`` earns, or ``None`` when it earns none.

    Returned only for ``fits: False`` — the state an agent must act on. ``True`` needs no
    sentence, and ``None`` (``checked: "unavailable"``) is a measurement failure the structured
    block already states; turning it into prose would read as a framing problem it is not.

    This is the **only** place the sentence text exists. No tool's own summary function may
    append it: ``text`` is hand-written per tool, so a second copy is how two tools end up
    warning in two wordings an agent must both learn.
    """
    if framing is None or framing.get("fits") is not False:
        return None
    return (
        "Warning: the model does not fully fit the live viewport, so the human is seeing only "
        "part of it. Call view_fit_viewport to fit it, if they need to see this change."
    )


def with_framing_text(text: str, framing: FramingVerdict | None) -> str:
    """``text`` with the framing warning appended when ``framing`` earns one.

    Appended to the finished string rather than regenerated from ``structured_content``: every
    real tool hand-writes ``text``, so regenerating it would replace a tool's own summary with
    the generic mirror.
    """
    sentence = framing_warning(framing)
    return f"{text}\n\n{sentence}" if sentence else text
