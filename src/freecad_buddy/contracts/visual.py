"""Visual-judge contract: the verdict wire type, the visual set it is measured over, and the seam.

The verdict shape is not invented here. ``benchmarks/g3/judge.py`` fixed
``{pass, findings: [{view, observation, severity}]}`` at the G3 entry gate, before any vision
client existed, so the fault cases under ``fault-injection/visual-judge/`` were authored against
a schema that already existed. This module restates that shape as a wire type and **re-derives
nothing**: the vocabulary constants below are asserted equal to the seam's by
``tests/external/test_verify_visual.py``, so a drift between the two breaks a test rather than
silently splitting the schema the cases were graded against.

``JudgeClient`` is the seam the live vision client implements. It lives here, in the innermost
ring, for the reason ``RenderPort`` does: the use case must depend on the *shape* of a judge, not
on a model SDK. The client itself is an adapter (``adapters/visual_judge_client.py``) because it
carries a third-party HTTP dependency and a credential read.

Stdlib only; no FreeCAD, Gui, Qt, or model SDK import.
"""

from __future__ import annotations

from typing import Literal, Protocol, TypedDict, runtime_checkable

# The wrapped check id the visual leg reports under (verification-design.md §7a). Same literal as
# ``benchmarks/g3/judge.py`` CHECK_ID.
VISUAL_CHECK_ID = "visual.judge"

# The code a fail-closed verdict carries when no vision backend answered, no image was legible, or
# the drawing could not be built. Same literal as the seam's UNAVAILABLE_CODE.
VISUAL_UNAVAILABLE_CODE = "visual.unavailable"

# The legibility floor for judge-directed images (AD-21). Judge images travel straight to the judge
# API rather than through client context, so the user-facing render budget
# (``usecases/screenshot.py`` ``_MAX_DIM``) neither governs them nor is widened by them.
MIN_JUDGE_IMAGE_WIDTH_PX = 2048

# A finding attributes itself to one of the standard visual set's views, or the repair loop cannot
# tell the agent where to look. Same members as the seam's ``VIEWS``.
JudgeView = Literal["iso", "focus", "front", "top", "right"]

# ``blocking`` fails the part on its own; ``advisory`` is diagnostic input for the repair loop.
FindingSeverity = Literal["blocking", "advisory"]


class JudgeFinding(TypedDict, total=False):
    """One observation the judge attributes to one view of the standard visual set."""

    view: JudgeView  # required
    observation: str  # required
    severity: FindingSeverity  # required


# The judge's structured answer: the conjunctive pass flag plus its findings. Declared
# functionally because ``pass`` is a reserved word and cannot be a class-body field name. The wire
# key stays literally ``pass``: the fault cases and the seam's ``validate_verdict`` both read
# ``verdict["pass"]``, so renaming it would make the schema the cases were authored against and the
# schema the client validates two different things.
JudgeVerdict = TypedDict(
    "JudgeVerdict",
    {"pass": bool, "findings": list[JudgeFinding]},
    total=False,
)


class JudgeImage(TypedDict, total=False):
    """One image in the standard visual set, with the width the legibility gate measures.

    ``width_px`` is the image's real pixel width as produced, never a requested size: the ≥2048 px
    floor exists so callouts stay readable, and a gate reading a requested width would pass an
    image the renderer silently produced smaller.
    """

    view: JudgeView  # required
    path: str  # required
    width_px: int  # required
    media_type: str  # required


class VisualSet(TypedDict, total=False):
    """The standard visual set assembled for one judge call, or the reason it is incomplete.

    ``complete`` is false whenever any leg is missing — no render capability, no drawing sheet, or
    an image below the legibility floor. The caller's fail-closed rule applies to that flag: an
    incomplete set is never judged, because a verdict read from a partial set would be reported
    with the same confidence as one read from the full set.
    """

    schema: Literal["fcb.visual-set/1"]  # required
    complete: bool  # required
    reason: str | None  # required
    images: list[JudgeImage]  # required
    spec_text: str  # required
    checklist: list[str]  # required


@runtime_checkable
class JudgeClient(Protocol):
    """The vision-judge capability the caller injects; the use case depends only on this shape.

    A live client calls a vision model at temperature 0 under a model id distinct from the actor's;
    the CI double replays fixed verdicts. Both raise ``JudgeUnavailable`` rather than returning a
    verdict they could not obtain — "no answer" must never be spelled the same way as "pass".
    """

    def available(self) -> tuple[bool, str | None]:
        """Return ``(is_available, reason)``; ``reason`` is set only when unavailable."""

    def judge(self, visual_set: VisualSet) -> JudgeVerdict:
        """Return the model's verdict for ``visual_set``.

        The returned mapping is untrusted model output and is validated by the caller before any
        field is read. Raises on transport failure, a missing credential, or a timeout; it must
        never substitute a verdict of its own for an answer it did not receive.
        """


__all__ = [
    "FindingSeverity",
    "JudgeClient",
    "JudgeFinding",
    "JudgeImage",
    "JudgeVerdict",
    "JudgeView",
    "MIN_JUDGE_IMAGE_WIDTH_PX",
    "VISUAL_CHECK_ID",
    "VISUAL_UNAVAILABLE_CODE",
    "VisualSet",
]
