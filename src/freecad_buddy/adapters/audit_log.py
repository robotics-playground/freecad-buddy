"""Append-only ``fcb.audit-record/1`` JSON-lines sink.

Every lifecycle mutation and every ``debug_exec`` call appends one record before execution and
one after. Lifecycle operations use ``event:"mutation"`` and ``debug_exec`` uses
``event:"exec"``. The file is opened in append mode; this sink never truncates, rotates, or
reads it.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from freecad_buddy.contracts import AuditRecord


def default_audit_path() -> Path:
    """The audit-log path from ``FREECAD_BUDDY_AUDIT_LOG``, or a cwd-relative default."""
    return Path(os.environ.get("FREECAD_BUDDY_AUDIT_LOG", "freecad-buddy-audit.jsonl"))


def _digest(params: dict) -> str:
    # ``default=repr`` keeps the digest from raising on a non-JSON-serializable argument so an
    # audit line is always writable.
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False, default=repr).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class AuditSink:
    """Serializes ``AuditRecord`` lines to an append-only file (one JSON object per line)."""

    def __init__(self, path: str | Path, actor: str = "operator") -> None:
        self._path = Path(path)
        self._actor = actor
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, record: AuditRecord) -> None:
        line = json.dumps(record, sort_keys=True, ensure_ascii=False)
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def _record(self, event: str, tool: str, doc: str | None, params: dict) -> AuditRecord:
        record: AuditRecord = {
            "schema": "fcb.audit-record/1",
            "ts": datetime.now(timezone.utc).isoformat(),
            "actor": self._actor,
            "event": event,  # type: ignore[typeddict-item]
            "tool": tool,
            "params_digest": _digest(params),
        }
        if doc:
            record["doc"] = {"handle": doc}
        # The exec path is the highest-risk one: persist the executed source, not only its digest,
        # so an audit line can reproduce what ran (security-and-service §1).
        if event == "exec":
            code = params.get("code")
            if isinstance(code, str):
                record["code"] = code
        return record

    def before(
        self,
        event: str,
        tool: str,
        doc: str | None,
        params: dict,
        fingerprint_before: str | None = None,
    ) -> None:
        """Append the pre-execution record for a mutation or exec call.

        ``fingerprint_before`` is the pre-mutation fingerprint digest; a caller that has not
        fingerprinted the document (a lifecycle op, or ``debug_exec``) omits it and the field
        records ``None``.
        """
        record = self._record(event, tool, doc, params)
        record["fingerprint_before"] = fingerprint_before
        self._write(record)

    def after(
        self,
        event: str,
        tool: str,
        doc: str | None,
        params: dict,
        verdict: str | None,
        fingerprint_before: str | None = None,
        fingerprint_after: str | None = None,
        rollback: dict | None = None,
    ) -> None:
        """Append the post-execution record, carrying the resulting envelope status.

        ``fingerprint_before``/``fingerprint_after`` are the mutation's real digests and
        ``rollback`` the rollback outcome block (``{rolled_back, rollback_proven, explanation}``);
        a caller that ran no mutation bracket omits them and the fields record ``None``.
        """
        record = self._record(event, tool, doc, params)
        record["fingerprint_before"] = fingerprint_before
        record["fingerprint_after"] = fingerprint_after
        record["verify_verdict"] = verdict  # type: ignore[typeddict-item]
        record["rollback"] = rollback
        self._write(record)
