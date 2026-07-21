"""Result envelope (design §4). Every tool/RPC/job/harness result returns this shape.

``mirror_text`` is the single generator of the §12.3 human-readable text mirror so
``ResultEnvelope.text`` can never diverge from ``structured_content``.
"""

from __future__ import annotations

import json
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


def mirror_text(structured_content: dict) -> str:
    """Deterministic human-readable mirror of ``structured_content`` (§12.3).

    Sole producer of ``ResultEnvelope.text``; the round-trip test regenerates and
    compares. Sorted keys keep the mirror stable across dict insertion order.
    """
    return json.dumps(structured_content, sort_keys=True, indent=2, ensure_ascii=False)
