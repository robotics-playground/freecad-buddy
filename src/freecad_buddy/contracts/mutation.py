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


class _RefFindingRequired(TypedDict):
    owner: str
    prop: str
    verdict: RefVerdict
    layer: int


class RefFinding(_RefFindingRequired, total=False):
    mapped_before: str | None
    state_after: str | None
    detail: str | None


class _TnpAuditRequired(TypedDict):
    status: TnpStatus
    element_map_version: str | None  # None ⇔ no element map
    findings: list[RefFinding]


class TnpAuditBlock(_TnpAuditRequired, total=False):
    pass


class _PostVerifyRequired(TypedDict):
    recompute_clean: bool
    is_valid: bool
    fully_constrained: bool | None  # None ⇔ no sketch involved
    tnp_audit: TnpAuditBlock
    passed: bool


class PostVerifyBlock(_PostVerifyRequired, total=False):
    explanation: str | None


class _MutationRequired(TypedDict):
    transaction_id: str
    fingerprint_before: FingerprintRecord
    fingerprint_after: FingerprintRecord | None
    post_verify: PostVerifyBlock
    rolled_back: bool
    rollback_proven: RollbackProof | None  # None ⇔ no rollback ran


class MutationBlock(_MutationRequired, total=False):
    schema: Literal["fcb.mutation/1"]
    snapshot_path: str | None
    verify_verdict: TerminalStatus | None
    params_digest: str | None
    touched: list[str]  # Names the op reported creating or modifying
