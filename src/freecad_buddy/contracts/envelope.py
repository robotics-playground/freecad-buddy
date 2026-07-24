"""Result envelope: the shape every tool/RPC/job/harness result returns.

``mirror_text`` is the single generator of the human-readable text mirror so
``ResultEnvelope.text`` can never diverge from ``structured_content``.
"""

from __future__ import annotations

from typing import Literal, TypedDict

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
