"""Audit record: an append-only JSON-lines entry.

Reuses the shared vocabulary (``fingerprint_before/after``, ``params_digest``, and the
diff's ``touched/new/deleted`` naming) rather than introducing synonyms.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from freecad_buddy.contracts.document import DocHandle
from freecad_buddy.contracts.status import TerminalStatus


class AuditRecord(TypedDict, total=False):
    schema: Literal["fcb.audit-record/1"]
    ts: str  # required
    actor: str  # required
    event: Literal["mutation", "exec", "preview", "approval", "rollback"]  # required
    tool: str
    doc: DocHandle
    params_digest: str
    code: str  # exec source (security-and-service §1): the executed code, for the exec event only
    fingerprint_before: str | None
    fingerprint_after: str | None
    verify_verdict: TerminalStatus | None
    verify_report_ref: str | None
    approval: dict | None
    rollback: dict | None
