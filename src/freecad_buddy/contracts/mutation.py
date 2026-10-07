"""Mutation-protocol wire types: the ``mutation`` result block and its nested blocks.

Field names reuse the shared audit vocabulary (``fingerprint_before``/``fingerprint_after``)
rather than introducing synonyms. The block is the wire projection of the full block the bracket
builds. The audit log records both fingerprint digests, ``verify_verdict`` and ``params_digest``;
a tool result carries neither the full fingerprint records nor those two fields. Stdlib only.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from freecad_buddy.contracts.fingerprint import MassProps

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

# A field whose step never ran. Distinct from None, which means the step ran and found the
# question inapplicable — no sketch was involved.
NotMeasured = Literal["not_measured"]
NOT_MEASURED: NotMeasured = "not_measured"


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
    counts: dict[str, int]  # findings per verdict, PASS included
    findings: list[RefFinding]  # the non-PASS findings only


class TnpAuditBlock(_TnpAuditRequired, total=False):
    pass


class _PostVerifyRequired(TypedDict):
    recompute_clean: bool
    is_valid: bool | NotMeasured
    fully_constrained: bool | None | NotMeasured  # None ⇔ no sketch involved
    tnp_audit: TnpAuditBlock
    passed: bool


class PostVerifyBlock(_PostVerifyRequired, total=False):
    explanation: str | None


class WireFingerprint(TypedDict):
    digest: str
    serializer: Literal["exportBinary", "exportBrep"]


class _ChangedObjectRequired(TypedDict):
    name: str
    # The values after the mutation; None when the object exists only before it.
    volume: float | None
    area: float | None
    com: list[float] | None


class ChangedObject(_ChangedObjectRequired, total=False):
    # Present only on a failed or rolled-back mutation; None on the side the object is missing.
    before: MassProps | None
    after: MassProps | None


class _MutationRequired(TypedDict):
    fingerprint_before: WireFingerprint | None  # None ⇔ the pre-mutation fingerprint failed
    fingerprint_after: WireFingerprint | None
    changed: list[ChangedObject]  # objects whose geometric invariants differ, by name
    post_verify: PostVerifyBlock
    rolled_back: bool
    rollback_proven: RollbackProof | None  # None ⇔ no rollback ran


class MutationBlock(_MutationRequired, total=False):
    schema: Literal["fcb.mutation/2"]
    snapshot_path: str  # present only when a snapshot was kept or restored from
    touched: list[str]  # Names the op reported creating or modifying
