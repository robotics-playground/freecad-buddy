"""Deterministic judge double: replays fixed verdicts so CI can prove the wiring without a key.

The same discipline decision 010 fixed for the G1 actor and ``ScriptedBackend``: the live model
call is operator-gated and never a green CI job, so everything around it — the request build, the
schema validation, the fail-closed path, the legibility gate and the report shape — is exercised
offline against a double that replays recorded answers.

**This double deliberately does not stand in for model quality.** It replays whatever verdict its
script carries, including ``pass: True``. A green run against it means "the machinery is correct",
never "the judge passes the part" — exactly the distinction decision 010 draws. The measured
sensitivity number therefore cannot come from here, and ``_registry/validators.yaml`` records
``not_scored`` until an operator produces one.

Lives in ``benchmarks/`` (outermost tooling) beside ``actor.py`` for the same reason that module
does: it is harness code, never imported by the shipped package.
"""

from __future__ import annotations

from freecad_buddy.contracts import JudgeVerdict, VisualSet
from freecad_buddy.usecases.verify_visual import JudgeUnavailable


class ScriptedJudgeUnavailable(JudgeUnavailable):
    """The scripted judge holds no verdict for this set — the offline unreachable-judge path.

    Subclasses the use case's ``JudgeUnavailable`` so the CI run exercises the SAME fail-closed
    branch the live client's transport failure takes. A double raising an unrelated class would
    prove a catch-all path that production never reaches.
    """


class ScriptedJudge:
    """Offline ``JudgeClient`` double: replays one recorded verdict per checklist key.

    ``script`` maps a key to the verdict to return for it. The key is the first checklist entry,
    which is what a benchmark case declares per part — keying on the document name instead would
    make the double follow FreeCAD's naming rather than the case's identity.

    A key absent from the script raises ``ScriptedJudgeUnavailable``, so the unreachable-judge path
    is reachable in CI without a network. ``available`` reports a configurable state for the same
    reason: the no-credential branch must be provable too.
    """

    def __init__(self, script: dict[str, JudgeVerdict], available_reason: str | None = None):
        """
        :param script: the recorded verdicts, keyed by the case's first checklist entry.
        :param available_reason: when set, ``available`` reports unavailable with this reason. The
            live client reports exactly this when its credential is absent.
        """
        self._script = script
        self._available_reason = available_reason
        self.calls: list[VisualSet] = []

    def available(self) -> tuple[bool, str | None]:
        """Return ``(is_available, reason)``; unavailable only when one was configured."""
        if self._available_reason is not None:
            return False, self._available_reason
        return True, None

    def judge(self, visual_set: VisualSet) -> JudgeVerdict:
        """Return the recorded verdict for ``visual_set``, recording the call.

        The full set is recorded rather than a summary of it, so a test can assert the judge was
        handed the drawing sheet and every rendered view — the thing a wiring bug would drop.

        :raises ScriptedJudgeUnavailable: no verdict is recorded for this set.
        """
        self.calls.append(visual_set)
        key = _script_key(visual_set)
        if key not in self._script:
            raise ScriptedJudgeUnavailable(
                f"no recorded verdict for {key!r}; the scripted judge replays verdicts and "
                f"invents none"
            )
        return self._script[key]


def _script_key(visual_set: VisualSet) -> str:
    """The script key for a set: its first checklist entry, or ``""`` when it carries none."""
    checklist = visual_set.get("checklist") or []
    return checklist[0] if checklist else ""


__all__ = ["ScriptedJudge", "ScriptedJudgeUnavailable"]
