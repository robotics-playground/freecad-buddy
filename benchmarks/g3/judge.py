"""Visual-judge seam for the G3 visual leg (AD-21) — the stub story 4.4 replaces.

The judge's *contract* is what Story 4.1 owes: the verdict shape, the fail-closed rule, and the
independence requirement. The vision client behind it is 4.4's work. No repo code sends an image
to a model API today, so this module answers every call with an honest
``visual.unavailable`` — the part is NOT done, and no bypass exists short of an audit-logged
operator waiver (verification-design.md §7a, "Degradation (fail-closed)").

The verdict shape is fixed here so the fault cases under ``fault-injection/visual-judge/`` were
authored against a schema that already existed, which is the whole point of an entry gate: a
judge cannot be graded by measures written after it.

FreeCAD-free and dependency-free to import; the scorer and the gate tests both read it.
"""

from __future__ import annotations

# The wrapped check id the visual leg reports under (verification-design.md §7a).
CHECK_ID = "visual.judge"

# The code a fail-closed verdict carries when no vision backend answered.
UNAVAILABLE_CODE = "visual.unavailable"

# The severities a finding may carry. `blocking` fails the part on its own; `advisory` is
# diagnostic input for the repair loop. A finding outside this set is a malformed verdict.
SEVERITIES = frozenset({"blocking", "advisory"})

# The views the standard visual set names (verification-design.md §7a "Inputs"). A finding must
# attribute itself to one of them, or the repair loop cannot tell the agent where to look.
VIEWS = frozenset({"iso", "focus", "front", "top", "right"})

# The legibility floor for judge-directed images (AD-21). Recorded, not enforced here: both
# render caps that would need raising live in shipped code (usecases/screenshot.py:34 and
# hosts/tool_catalog.py:202-203) and raising them is 4.3/4.4 work, not 4.1's.
MIN_PAGE_WIDTH_PX = 2048


class JudgeUnavailable(Exception):
    """No vision backend answered. Fail-closed: the part is not done."""


class VerdictSchemaError(Exception):
    """A verdict does not match ``{pass, findings:[{view, observation, severity}]}``."""


def validate_verdict(verdict) -> dict:
    """Return ``verdict`` when it matches the judge schema; raise ``VerdictSchemaError`` if not.

    Story 4.4's real client returns model output, which is untrusted: a verdict missing its
    ``pass`` field, or carrying a finding with no view, would otherwise be read as a pass by a
    caller doing ``verdict.get("pass")``. Validation is therefore the seam's job, not the
    caller's, and it exists before the client does.

    :param verdict: the mapping a judge backend returned.
    """
    if not isinstance(verdict, dict):
        raise VerdictSchemaError(f"verdict must be a mapping, got {type(verdict).__name__}")
    if "pass" not in verdict:
        raise VerdictSchemaError("verdict declares no 'pass'")
    if not isinstance(verdict["pass"], bool):
        raise VerdictSchemaError(f"verdict 'pass' must be a bool, got {verdict['pass']!r}")
    findings = verdict.get("findings")
    if not isinstance(findings, list):
        raise VerdictSchemaError(f"verdict 'findings' must be a list, got {findings!r}")
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise VerdictSchemaError(f"findings[{index}] must be a mapping, got {finding!r}")
        for field in ("view", "observation", "severity"):
            value = finding.get(field)
            if not isinstance(value, str) or not value.strip():
                raise VerdictSchemaError(f"findings[{index}] has no non-empty '{field}'")
        if finding["view"] not in VIEWS:
            raise VerdictSchemaError(
                f"findings[{index}] view {finding['view']!r} is outside {sorted(VIEWS)}"
            )
        if finding["severity"] not in SEVERITIES:
            raise VerdictSchemaError(
                f"findings[{index}] severity {finding['severity']!r} is outside "
                f"{sorted(SEVERITIES)}"
            )
    return verdict


def unavailable_verdict(reason: str) -> dict:
    """The fail-closed verdict: ``pass: False`` plus one blocking finding naming the reason.

    Shaped so a caller that only reads ``pass`` still gets the right answer, and a caller that
    reads findings learns why. Never returns ``pass: True``.
    """
    return validate_verdict(
        {
            "pass": False,
            "findings": [
                {
                    "view": "iso",
                    "observation": f"{UNAVAILABLE_CODE}: {reason}",
                    "severity": "blocking",
                }
            ],
        }
    )


class StubJudge:
    """The judge seam before a vision client exists — always unavailable, never a pass.

    Story 4.4 swaps this for a client that calls a vision model at temperature 0 under a separate
    model id from the actor. Until then ``judge`` raises, and ``judge_or_unavailable`` returns the
    fail-closed verdict, so a caller cannot mistake "no judge" for "judge passed it".
    """

    reason = (
        "no vision backend is wired: the visual judge client is Story 4.4 work, so no image has "
        "been sent to a model and no visual verdict exists"
    )

    def judge(self, images, spec_text, checklist) -> dict:  # noqa: ARG002 - the 4.4 signature
        """Raise ``JudgeUnavailable``. The signature is the seam 4.4 implements against.

        :param images: the standard visual set (3D iso render, focus views, TechDraw projections).
        :param spec_text: the written spec the part is judged against.
        :param checklist: the structured checklist derived from that spec.
        """
        raise JudgeUnavailable(self.reason)

    def judge_or_unavailable(self, images, spec_text, checklist) -> dict:
        """``judge`` with the fail-closed verdict substituted for the exception."""
        try:
            return validate_verdict(self.judge(images, spec_text, checklist))
        except JudgeUnavailable as exc:
            return unavailable_verdict(str(exc))


__all__ = [
    "CHECK_ID",
    "MIN_PAGE_WIDTH_PX",
    "SEVERITIES",
    "UNAVAILABLE_CODE",
    "VIEWS",
    "JudgeUnavailable",
    "StubJudge",
    "VerdictSchemaError",
    "unavailable_verdict",
    "validate_verdict",
]
