"""Mutation-protocol wire types: the ``mutation`` result block and its nested blocks.

Field names reuse the shared audit vocabulary (``fingerprint_before``/``fingerprint_after``,
``verify_verdict``, ``params_digest``) rather than introducing synonyms. Stdlib only.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from freecad_buddy.contracts.fingerprint import FingerprintRecord
from freecad_buddy.contracts.status import TerminalStatus

RefVerdict = Literal[
    "PASS",
    "BROKEN",
    "REPOINTED",
    "DROPPED",
    "UNSUPPORTED",
    "RE_BASELINED",
]

TnpStatus = Literal["CLEAN", "FLAGGED", "UNSUPPORTED"]

RollbackProof = Literal["rolled_back_verified", "rolled_back_via_snapshot"]


class RefFinding(TypedDict, total=False):
    owner: str  # required
    prop: str  # required
    mapped_before: str | None
    state_after: str | None
    verdict: RefVerdict  # required
    layer: int  # required
    detail: str | None


class TnpAuditBlock(TypedDict, total=False):
    status: TnpStatus  # required
    element_map_version: str | None  # required; None ⇔ no element map
    findings: list[RefFinding]  # required


class PostVerifyBlock(TypedDict, total=False):
    recompute_clean: bool  # required
    is_valid: bool  # required
    fully_constrained: bool | None  # None ⇔ no sketch involved
    tnp_audit: TnpAuditBlock  # required
    passed: bool  # required
    explanation: str | None


class MutationBlock(TypedDict, total=False):
    schema: Literal["fcb.mutation/1"]
    transaction_id: str  # required
    fingerprint_before: FingerprintRecord  # required
    fingerprint_after: FingerprintRecord | None  # required
    post_verify: PostVerifyBlock  # required
    rolled_back: bool  # required
    rollback_proven: RollbackProof | None  # required; None ⇔ no rollback ran
    snapshot_path: str | None
    verify_verdict: TerminalStatus | None
    params_digest: str | None
