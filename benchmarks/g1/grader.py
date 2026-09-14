"""Independent deterministic expected-findings grader (FreeCAD-free, stdlib-only).

The grader decides whether a candidate answer correctly diagnoses a case by matching the
answer text against the case's independently hand-authored expected findings — never by asking
the actor and never with a live model. It is CI-reproducible (no network, no LLM) and is the
validator whose sensitivity ``gate faults g1`` scores.

Pass rule (G1.2 "*the* failing object + cause named"): a candidate answer PASSES iff it
mentions the expected failing object identity (case-normalized, whole-token) AND at least one of
the expected cause keywords (substring). Both must hold — naming the object without the cause,
or the cause without the object, is a FAIL. Cause matching is substring, not negation-aware
(see ``_mentions_cause``); negation-robust grading is deferred to the model grader.

``GraderClient`` is the seam a model-backed grader (for fuzzier G1.1 answer-quality judgment)
plugs into later (Stories 2.2/2.3); ``DeterministicGrader`` is the shipped implementation and no
live-model call ships in this story.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class GraderVerdict:
    """The structured verdict a grader returns (harness §8): pass_, matched_expected, rationale.

    ``pass_`` is the terminal pass/fail; ``matched_expected`` records whether the expected
    findings were located in the answer (identical to ``pass_`` for the deterministic grader,
    but kept distinct so a future model grader can pass on rubric grounds while noting a
    partial expected-findings match); ``rationale`` is a human-readable one-liner.
    """

    pass_: bool
    matched_expected: bool
    rationale: str


@runtime_checkable
class GraderClient(Protocol):
    """The grader seam. A model-backed grader implements the same ``grade`` signature."""

    def grade(self, question: str, answer: str, rubric: str, expected: dict) -> GraderVerdict: ...


def _normalize(text: str) -> str:
    """Lowercase and collapse non-alphanumeric runs to single spaces for identity matching."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _mentions_object(answer_norm: str, obj: str) -> bool:
    """Whether the normalized answer names ``obj`` as a whole token run.

    Object identity is matched on the immutable ``Name`` (case-normalized). A bare substring
    would let ``Pad`` match ``Padding``; the space-padded compare pins a whole-token mention.
    """
    obj_norm = _normalize(obj)
    if not obj_norm:
        return False
    return f" {obj_norm} " in f" {answer_norm} "


def _mentions_cause(answer_norm: str, keywords: list[str]) -> bool:
    """Whether the normalized answer contains at least one expected cause keyword (whole-token).

    A keyword matches on whole-token boundaries in the normalized answer: a single-word keyword
    (``tool``) must appear as its own token, not inside a longer word (``toolbar``/``tooltip``); a
    multi-word keyword (``missing tool``) matches as a contiguous token run. Matching is NOT
    negation-aware: an answer that mentions a cause keyword only to deny it ("it is NOT an
    expression problem") still matches. Negation-robust cause grading is explicitly out of scope
    for the deterministic grader and deferred to the model-backed grader behind ``GraderClient``
    (see docs/decisions/009). The planted fault suite therefore does not claim to catch negated
    causes.
    """
    padded = f" {answer_norm} "
    for keyword in keywords:
        keyword_norm = _normalize(keyword)
        if keyword_norm and f" {keyword_norm} " in padded:
            return True
    return False


def _cause_keywords(expected: dict) -> list[str]:
    """Extract a non-empty list of non-empty cause keyword strings, or raise on a malformed case.

    A case whose ``cause_keywords`` is absent/empty/blank would make the cause never matchable —
    silently FAILing every answer (a control then false-alarms, or the score is vacuous). That is
    an authoring error, surfaced loudly rather than degraded into a silent all-FAIL case.
    """
    raw = expected.get("cause_keywords")
    if raw is None:
        raise ValueError(f"expected {expected.get('object')!r}: missing 'cause_keywords'")
    items = raw if isinstance(raw, list) else [raw]
    keywords = [str(k).strip() for k in items if str(k).strip()]
    if not keywords:
        raise ValueError(f"expected {expected.get('object')!r}: 'cause_keywords' is empty")
    return keywords


class DeterministicGrader:
    """Rubric-keyed matcher of the named failing object + cause. Independent of the actor."""

    def grade(self, question: str, answer: str, rubric: str, expected: dict) -> GraderVerdict:
        """Grade ``answer`` against ``expected`` = ``{object, cause_keywords, ...}``.

        Returns a FAIL verdict when the expected object identity is absent, or when none of the
        expected cause keywords appear. Both an object mention AND a cause keyword are required
        to PASS. Raises ``ValueError`` on a malformed ``expected`` (blank ``object`` or empty
        ``cause_keywords``) rather than silently FAILing — a malformed case is an authoring bug.
        The ``question``/``rubric`` inputs are part of the seam signature (a model grader uses
        them); the deterministic matcher reads only ``expected`` + ``answer``.
        """
        if not isinstance(expected, dict):
            raise ValueError(
                f"expected must be a mapping with 'object' + 'cause_keywords', got "
                f"{type(expected).__name__} (G1.1 list-of-strings findings are not gradeable by "
                f"the deterministic grader — that is the model-grader's path)"
            )
        obj = str(expected.get("object", "")).strip()
        if not obj:
            raise ValueError("expected 'object' is required and must be non-blank")
        keywords = _cause_keywords(expected)

        answer_norm = _normalize(answer or "")
        has_object = _mentions_object(answer_norm, obj)
        has_cause = _mentions_cause(answer_norm, keywords)
        passed = has_object and has_cause

        if passed:
            rationale = f"names failing object '{obj}' and a matching cause keyword"
        elif not has_object and not has_cause:
            rationale = f"missing failing object '{obj}' and any cause keyword"
        elif not has_object:
            rationale = f"missing the failing object '{obj}'"
        else:
            rationale = "names the object but no expected cause keyword"

        return GraderVerdict(pass_=passed, matched_expected=passed, rationale=rationale)
