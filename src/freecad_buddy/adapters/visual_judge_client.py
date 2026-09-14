"""Vision-judge client: builds the judge request, reads its credential, parses its verdict.

The transport is **injected**, exactly as the ReAct adapter's chat transport is (decision 011).
That is not indirection for its own sake: it keeps a model SDK and an HTTP dependency out of the
repo, it lets CI exercise the whole request-build / response-parse path against a scripted double
with no credential, and it means the operator's live run and the offline run drive identical code.
A ``VisionTransport`` is any callable taking the assembled request mapping and returning the
model's reply text.

**The credential is read from the environment and nowhere else.** No key in the repo, in a
fixture, in a test, or in CI. ``available()`` reports the absent-credential state rather than
raising, so the caller's fail-closed rule turns it into ``visual.unavailable`` — the part is not
done, and no test asserts a passing verdict without one.

**Temperature is 0 and is not a parameter.** AD-21 and ``benchmarks/g3/gate.yaml``'s
``visual_judge:`` block both pin it; a caller able to raise it could make the same part pass on a
re-run, which would make the G3.7 number unreproducible.
"""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Callable

from freecad_buddy.contracts import JudgeVerdict, VisualSet
from freecad_buddy.usecases.verify_visual import JudgeUnavailable

# The credential this client reads, and nothing else. Named for the judge rather than for a
# provider so an operator pointing the transport at a different backend sets one variable.
CREDENTIAL_ENV = "FREECAD_BUDDY_JUDGE_API_KEY"

# The model id the judge runs under, overridable so an operator can pin the exact vision model
# their run used without editing code. It is checked against every actor descriptor at preflight
# (``benchmarks/runner.py`` ``_preflight_judge_independence``), so an override that collides with
# the actor is refused before any call is made.
MODEL_ENV = "FREECAD_BUDDY_JUDGE_MODEL"
DEFAULT_MODEL = "vision-judge-independent"

# Pinned, not configurable (AD-21). A judge that could be run warmer would give a different answer
# on a re-run of the same part, and the G3.7 verdict would stop being reproducible.
TEMPERATURE = 0

# The instruction the judge answers under. Part of the validator: editing it stales the recorded
# sensitivity the same way editing a fault case does (``_registry/validators.yaml`` hash rule), so
# it is a module constant rather than a caller's argument.
RUBRIC = (
    "You are an independent visual judge for a CAD part. You are NOT the agent that built it.\n"
    "You are given the part's spec text, a checklist derived from that spec, a 3D isometric "
    "render, zero or more focus views, and a dimensioned engineering drawing carrying front, top "
    "and right projections.\n"
    "\n"
    "Judge whether the part shown matches the spec. Check every checklist item. Report a finding "
    "for each mismatch you see, including a dimension callout on the drawing that disagrees with "
    "the spec text.\n"
    "\n"
    "Rules:\n"
    "- Judge only what is visible. Do not assume a feature you cannot see is present or absent.\n"
    "- A mirrored part, a missing feature, a feature on the wrong face, and grossly wrong "
    "proportions are each a blocking finding.\n"
    "- A difference that is only a rendering or shading artefact is not a finding.\n"
    "- When the spec is symmetric, either handedness is correct and is not a finding.\n"
    "\n"
    'Answer with one JSON object and nothing else: {"pass": bool, "findings": [{"view": one of '
    '"iso"|"focus"|"front"|"top"|"right", "observation": str, "severity": '
    '"blocking"|"advisory"}]}.\n'
    "Set pass to false if and only if you reported at least one blocking finding."
)

# The reply is model output, so it may carry prose around the JSON object even under an explicit
# instruction. The fenced form is tried first, then a bare object, before giving up — a client that
# refused a correct verdict wrapped in a code fence would report a working judge as unreachable.
_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_BARE_JSON = re.compile(r"(\{.*\})", re.DOTALL)

VisionTransport = Callable[[dict], str]


class JudgeTransportError(JudgeUnavailable):
    """The judge could not be reached, or answered something that is not a verdict.

    Raised for a transport failure, an absent credential at call time, and an unparseable reply
    alike: each means no verdict was obtained, and the caller's fail-closed rule treats them
    identically. They are distinguished only by the message, for the operator reading the log.

    Subclasses the use case's ``JudgeUnavailable`` so ``verify_visual`` catches it by type rather
    than through its catch-all: an unreachable judge is the leg's named degradation, and it should
    not be reported with the same wording as a client bug.
    """


class VisualJudgeClient:
    """A ``JudgeClient`` that sends the standard visual set to a vision model at temperature 0.

    Holds no HTTP machinery of its own: ``transport`` is the injected callable that performs the
    request. Constructing one is free and takes no credential — the credential is read at
    ``available()`` and at call time, so a client built in a process that later gains a key does
    not need rebuilding, and one built in CI reports honestly that it has none.
    """

    def __init__(
        self,
        transport: VisionTransport,
        model: str | None = None,
        max_image_bytes: int = 5 * 1024 * 1024,
    ) -> None:
        """
        :param transport: the callable that performs the model request and returns its reply text.
        :param model: the judge's model id; defaults to ``$FREECAD_BUDDY_JUDGE_MODEL`` then
            ``DEFAULT_MODEL``.
        :param max_image_bytes: the per-image size beyond which an image is refused rather than
            sent. A judge API that rejects an oversized payload returns a transport error that
            reads like an unreachable judge, which would hide a fixable problem behind a
            fail-closed verdict.
        """
        self._transport = transport
        self._model = model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
        self._max_image_bytes = max_image_bytes

    @property
    def model(self) -> str:
        """The model id this client judges under; compared against every actor at preflight."""
        return self._model

    def available(self) -> tuple[bool, str | None]:
        """Return ``(is_available, reason)``: whether a credential is present in the environment.

        Reports rather than raises, so a run with no key produces a ``visual.unavailable`` verdict
        naming the missing variable instead of a traceback. It deliberately does NOT probe the
        backend: a reachability probe would cost a call per part and could still be stale by the
        time the real call goes out, and the real call already fails closed.
        """
        if not os.environ.get(CREDENTIAL_ENV):
            return False, (
                f"no judge credential: {CREDENTIAL_ENV} is not set in the environment, so no "
                f"image was sent to a vision model and no visual verdict exists"
            )
        return True, None

    def judge(self, visual_set: VisualSet) -> JudgeVerdict:
        """Send ``visual_set`` to the judge and return the parsed verdict mapping.

        The returned mapping is NOT validated here — validation belongs to the caller, which owns
        the schema and must reject a malformed verdict as an error rather than a fail. This method
        guarantees only that something JSON-shaped came back; ``{"nonsense": 1}`` is returned as-is
        and the caller's ``validate_verdict`` raises on it.

        :raises JudgeTransportError: the credential is absent, an image could not be read or is
            oversized, the transport raised, or the reply carried no JSON object.
        """
        credential = os.environ.get(CREDENTIAL_ENV)
        if not credential:
            raise JudgeTransportError(
                f"{CREDENTIAL_ENV} is not set; no image was sent and no verdict was obtained"
            )

        request = self.build_request(visual_set, credential)
        try:
            reply = self._transport(request)
        except Exception as exc:  # noqa: BLE001 - every transport failure is one unreachable judge
            raise JudgeTransportError(
                f"the judge transport raised {exc.__class__.__name__}: {exc}"
            ) from exc
        return _parse_verdict(reply)

    def build_request(self, visual_set: VisualSet, credential: str) -> dict:
        """Assemble the request the transport sends: model, temperature, credential, content.

        Public because it is the half of the client worth testing without a backend: CI asserts
        the temperature is 0, that every image in the set is attached, and that the credential came
        from the environment rather than from a literal.

        :raises JudgeTransportError: an image is unreadable or larger than ``max_image_bytes``.
        """
        content: list[dict] = [{"type": "text", "text": RUBRIC}]
        content.append({"type": "text", "text": f"SPEC:\n{visual_set['spec_text']}"})
        content.append(
            {
                "type": "text",
                "text": "CHECKLIST:\n" + "\n".join(f"- {item}" for item in visual_set["checklist"]),
            }
        )
        for image in visual_set["images"]:
            content.append({"type": "text", "text": f"VIEW: {image['view']}"})
            content.append(
                {
                    "type": "image",
                    "media_type": image["media_type"],
                    "data": self._encode(image["path"]),
                }
            )
        return {
            "model": self._model,
            "temperature": TEMPERATURE,
            "credential": credential,
            "content": content,
        }

    def _encode(self, path: str) -> str:
        """Read an image and return it base64-encoded.

        :raises JudgeTransportError: the file is unreadable or exceeds ``max_image_bytes``.
        """
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
        except OSError as exc:
            raise JudgeTransportError(f"judge image {path} is unreadable: {exc}") from exc
        if len(raw) > self._max_image_bytes:
            raise JudgeTransportError(
                f"judge image {path} is {len(raw)} bytes, over the {self._max_image_bytes}-byte "
                f"limit; sending it would return a transport error that reads like an "
                f"unreachable judge"
            )
        return base64.b64encode(raw).decode("ascii")


def _parse_verdict(reply: object) -> JudgeVerdict:
    """Extract the JSON object from a model reply, fenced or bare.

    :raises JudgeTransportError: the reply is not text, carries no JSON object, or the object does
        not parse.
    """
    if not isinstance(reply, str):
        raise JudgeTransportError(f"the judge returned {type(reply).__name__}, not reply text")
    for pattern in (_FENCED_JSON, _BARE_JSON):
        match = pattern.search(reply)
        if match is None:
            continue
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
    raise JudgeTransportError(f"the judge reply carried no parseable JSON object: {reply[:200]!r}")


__all__ = [
    "CREDENTIAL_ENV",
    "DEFAULT_MODEL",
    "MODEL_ENV",
    "RUBRIC",
    "TEMPERATURE",
    "JudgeTransportError",
    "VisionTransport",
    "VisualJudgeClient",
]
