"""Confirmation shapes: the wire ``confirm`` object and the signed preview-token payload.

``Confirm`` is what a client sends on a mutation call. ``PreviewTokenPayload`` is what a
``preview_id`` carries once decoded: its own identity, the operation, document and document state
the preview measured, plus the moment the token stops being accepted. ``jti`` is what makes two
previews of the same operation on an unchanged document distinguishable — without it their
payloads are equal and they sign to the same token. Shapes only — the codec that signs and
verifies a token lives in ``usecases/confirm.py``.
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


class Confirm(TypedDict, total=False):
    preview_id: str
    elicitation_action: Literal["accept"]


class PreviewTokenPayload(TypedDict):
    jti: str
    doc: str
    tool: str
    args_digest: str
    fingerprint_before: str
    exp: int


class ApprovalRecord(TypedDict):
    mode: Literal["preview_token", "auto_approve", "preview_copy", "display_state"]
    tool: str
    doc: str
    args_digest: str
    fingerprint_before: str | None
    source: NotRequired[str]
