"""Result envelope: the shape every tool/RPC/job/harness result returns.

``mirror_text`` is the single generator of the human-readable text mirror so
``ResultEnvelope.text`` can never diverge from ``structured_content``.

``framing_warning`` is the single generator of the framing warning sentence, for the same
reason: a sentence each tool appended for itself would drift tool by tool, and an agent that
learned to recognize one wording would miss the others.
"""

from __future__ import annotations

import re
from typing import Literal, TypedDict

from freecad_buddy.contracts.render import FramingVerdict
from freecad_buddy.contracts.status import ErrorDetail, TerminalStatus


# Extra slack, as a fraction of the viewport extent, granted to a ``fits: False`` verdict before it
# earns the warning sentence. AD-32 deferred this as a tuning knob against the risk of "a
# hair-trigger warning on every call". Calibration says the knob is not needed, so it is zero — a
# measured result, not an unconsidered default:
#
#   - A correct ``fitAll`` cannot trip the warning. ``fitAll`` frames the bounding *sphere* of the
#     bounding box (FreeCAD states this at ``View3DInventorViewer.cpp:4571-4573``), so the model
#     lands at ``largest_extent / space_diagonal`` of the viewport — 0.58 for a cube, 0.81 for a
#     40x25x15 plate, 0.99 for a 100x10x10 bar, approaching but never reaching 1.0 as the part
#     degenerates toward a line. A fit never overflows, so it never produces the false warning
#     this tolerance was reserved for. That was the whole hair-trigger risk.
#   - The only other candidate is one pixel of ``short`` rounding in ``getPointOnViewport``
#     (``View3DInventorViewer.cpp:3821-3822``). Suppressing it needs at least 1/800 of an 800px
#     viewport, and any such tolerance also suppresses a genuine one-pixel overflow — which story
#     8.2 ruled is a miss, and AD-30 requires the containment test stay exact.
#
# So a non-zero value here would buy nothing and cost exactness. Raise it only against a measured
# stream of false warnings, and record that measurement here.
NEAR_MISS_TOLERANCE = 0.0

# Longest string ``summary_text`` prints in full, set by tool-contracts.md T-13. A longer
# string, for example a ``script_exec`` ``stdout``, a long ``value_repr`` or a deep file
# path, is elided because ``structured_content`` already carries it in full.
INLINE_STRING_LIMIT = 80

# Every character ``str.splitlines`` treats as a line boundary: a value holding one cannot sit on
# the single ``key: value`` line the text mirror promises.
_LINE_BREAK = re.compile("[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]")


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
    # Raw text the MCP adapter sends as extra content blocks after the JSON block; never part of
    # the JSON block or structuredContent, so a multi-line body stays unescaped.
    text_blocks: list[str]
    # FreeCAD's display precision when the call ran; the MCP adapter rounds every float to it and
    # drops the key, so it is never part of the JSON block or structuredContent. ``None`` when the
    # operator turned rounding off: every float stays raw.
    display_decimals: int | None


def summary_text(structured_content: dict) -> str:
    """Compact human mirror of ``structured_content``: one ``key: value`` line per top-level key.

    Scalars render inline; a nested dict renders ``key: {N fields}`` and a list ``key: [N items]``
    — a signal of shape, never a full JSON dump. A string longer than ``INLINE_STRING_LIMIT``
    characters, or holding a line break (any ``str.splitlines`` boundary), renders
    ``key: <N chars>``: ``structured_content`` already carries it, so a copy here only
    doubles the characters the agent reads.
    """
    lines = []
    for key in sorted(structured_content):
        value = structured_content[key]
        if isinstance(value, str) and (
            len(value) > INLINE_STRING_LIMIT or _LINE_BREAK.search(value)
        ):
            lines.append(f"{key}: <{len(value)} chars>")
        elif isinstance(value, dict):
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

    A miss whose ``ratio`` is within ``NEAR_MISS_TOLERANCE`` of exactly filling the viewport earns
    no sentence. That tolerance is calibrated to zero, so today every miss warns; the check is the
    seam a future measured tolerance turns on, not a live filter. A ``ratio`` of ``None`` always
    warns — it means a coordinate was discarded as implausible, which is a gross overflow.

    This is the **only** place the sentence text exists. No tool's own summary function may
    append it: ``text`` is hand-written per tool, so a second copy is how two tools end up
    warning in two wordings an agent must both learn.
    """
    if framing is None or framing.get("fits") is not False:
        return None
    ratio = framing.get("ratio")
    if NEAR_MISS_TOLERANCE and ratio is not None and ratio <= 1.0 + NEAR_MISS_TOLERANCE:
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
