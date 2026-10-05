"""Fingerprint record shape and comparison helper.

``fingerprints_equal`` raises on incomparable records (serializer-tag mismatch or a
missing serializer/digest on either side) so cross-tag comparison never yields a
"changed" verdict and an absent digest never compares equal by omission.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class MassProps(TypedDict):
    volume: float
    area: float
    bbox: list[float]
    com: list[float]
    principal_moments: list[float]
    quantum: float


class ObjectFingerprint(TypedDict):
    name: str
    brep_sha256: str
    massprops: MassProps


class FingerprintRecord(TypedDict):
    schema: Literal["fcb.fingerprint/1"]
    serializer: Literal["exportBinary", "exportBrep"]  # required
    objects: list[ObjectFingerprint]
    digest: str


def fingerprints_equal(a: dict, b: dict) -> bool:
    """Compare two FingerprintRecords by ``digest`` iff their ``serializer`` tags match.

    Raises ``ValueError`` when the records are incomparable: either serializer tag is
    missing/None, the tags differ, or either digest is missing/None. Comparable and
    equal-tagged records return ``digest`` equality.
    """
    ser_a = a.get("serializer")
    ser_b = b.get("serializer")
    if ser_a is None or ser_b is None or ser_a != ser_b:
        raise ValueError(
            "cannot compare fingerprints: serializer tag missing/mismatch "
            f"({ser_a!r} vs {ser_b!r})"
        )

    dig_a = a.get("digest")
    dig_b = b.get("digest")
    if dig_a is None or dig_b is None:
        raise ValueError(
            "cannot compare fingerprints: digest missing "
            f"({dig_a!r} vs {dig_b!r})"
        )

    return dig_a == dig_b


# Mass-property keys that are true geometric invariants — stable across a render. ``bbox`` is
# excluded: FreeCAD's ``Shape.BoundBox`` is computed from the current tessellation, so refining
# the mesh (which a render or export does) shifts the approximate bounds while the exact geometry
# (volume, area, centre of mass, principal moments) is unchanged.
_INVARIANT_MASSPROP_KEYS = ("volume", "area", "com", "principal_moments")


def massprops_equal(a: dict, b: dict) -> bool:
    """Compare two FingerprintRecords by exact geometry: per-object volume/area/COM/moments.

    Unlike ``fingerprints_equal`` (which compares the ``digest`` over raw BRep bytes), this
    ignores both the serialized shape bytes and the tessellation-derived bounding box. OCCT
    re-lays-out a shape's BRep bytes the first time a freshly-loaded shape is touched (e.g. by a
    render), and a render/export refines the tessellation so ``bbox`` shifts — yet the exact
    geometric invariants stay identical. Use this for a read-only check where a render must not
    alter the geometry but may perturb the serialization or the tessellation.

    It is also the snapshot-restore rollback proof in ``run_mutation``: reopening the snapshot
    file re-serializes every shape, so the digest cannot match there. Records whose object-name
    sets differ are unequal.
    """

    def _invariants(record: dict) -> dict:
        result = {}
        for entry in record.get("objects", []):
            mp = entry.get("massprops") or {}
            result[entry["name"]] = {k: mp.get(k) for k in _INVARIANT_MASSPROP_KEYS}
        return result

    return _invariants(a) == _invariants(b)
