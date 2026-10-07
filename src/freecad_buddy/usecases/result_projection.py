"""Project the full mutation block onto its wire shape, and hold the full records it drops.

The bracket builds a full block: whole ``FingerprintRecord``s, every TNP finding, PASS included.
Every check and the audit log read that block. A tool result carries only its projection
(``fcb.mutation/2``): fingerprint digests, the objects whose geometry changed, and the non-PASS
findings with a count per verdict. The full records stay in a bounded digest-keyed cache, which
``document_undo`` reads to compare an expected digest by geometry.

Stdlib only: imports ``contracts/`` alone, so the replay script and the external tests run it
without FreeCAD.
"""

from __future__ import annotations

from collections import Counter, OrderedDict

from freecad_buddy.contracts import (
    ChangedObject,
    FingerprintRecord,
    MutationBlock,
    TnpAuditBlock,
    WireFingerprint,
    massprops_changed,
)

# One record of a 184-object drawer is about 75 KB, so 64 records hold about 5 MB. An undo
# targets one of the last few mutations; an evicted digest falls back to byte comparison.
_CACHE_SIZE = 64

_records: OrderedDict[str, FingerprintRecord] = OrderedDict()


def remember(record: FingerprintRecord) -> None:
    """Hold ``record`` under its digest, evicting the least recently used past the bound."""
    digest = record["digest"]
    _records[digest] = record
    _records.move_to_end(digest)
    while len(_records) > _CACHE_SIZE:
        _records.popitem(last=False)


def recall(digest: str) -> FingerprintRecord | None:
    """Return the record held under ``digest``, or ``None`` when it was never held or evicted."""
    record = _records.get(digest)
    if record is not None:
        _records.move_to_end(digest)
    return record


def wire_fingerprint(record: FingerprintRecord | None) -> WireFingerprint | None:
    """Remember ``record`` and return its wire form, ``{digest, serializer}``."""
    if record is None:
        return None
    remember(record)
    return {"digest": record["digest"], "serializer": record["serializer"]}


def wire_audit(full: TnpAuditBlock) -> TnpAuditBlock:
    """Return the audit with a count per verdict and the non-PASS findings only."""
    findings = full.get("findings") or []
    return {
        "status": full["status"],
        "element_map_version": full.get("element_map_version"),
        "counts": dict(Counter(finding["verdict"] for finding in findings)),
        "findings": [finding for finding in findings if finding["verdict"] != "PASS"],
    }


def changed_objects(
    before: FingerprintRecord | None, after: FingerprintRecord | None, failed: bool
) -> list[ChangedObject]:
    """Return one entry per object whose geometric invariants differ between the two records.

    An entry carries the object's after values, ``None`` for an object that exists only before.
    A ``failed`` mutation also carries both sides' ``MassProps``, ``None`` on the missing side,
    so an unproven rollback shows what it left. Without both records nothing can be compared.
    """
    if before is None or after is None:
        return []
    massprops_before = {entry["name"]: entry["massprops"] for entry in before["objects"]}
    massprops_after = {entry["name"]: entry["massprops"] for entry in after["objects"]}
    changed: list[ChangedObject] = []
    for name in massprops_changed(before, after):
        massprops = massprops_after.get(name)
        entry: ChangedObject = {
            "name": name,
            "volume": massprops["volume"] if massprops else None,
            "area": massprops["area"] if massprops else None,
            "com": massprops["com"] if massprops else None,
        }
        if failed:
            entry["before"] = massprops_before.get(name)
            entry["after"] = massprops
        changed.append(entry)
    return changed


def project_mutation(full: dict) -> MutationBlock:
    """Return the ``fcb.mutation/2`` wire block for a full (``fcb.mutation/1``-shaped) block.

    Both fingerprint records are remembered. ``transaction_id``, ``verify_verdict`` and
    ``params_digest`` are dropped: the audit log records them from the full block.
    """
    before = full.get("fingerprint_before")
    after = full.get("fingerprint_after")
    post_verify = dict(full["post_verify"])
    post_verify["tnp_audit"] = wire_audit(post_verify["tnp_audit"])
    failed = bool(full["rolled_back"]) or not post_verify.get("passed", False)
    block: MutationBlock = {
        "schema": "fcb.mutation/2",
        "fingerprint_before": wire_fingerprint(before),
        "fingerprint_after": wire_fingerprint(after),
        "changed": changed_objects(before, after, failed),
        "post_verify": post_verify,
        "rolled_back": full["rolled_back"],
        "rollback_proven": full["rollback_proven"],
        "touched": list(full.get("touched") or []),
    }
    if full.get("snapshot_path") is not None:
        block["snapshot_path"] = full["snapshot_path"]
    return block
