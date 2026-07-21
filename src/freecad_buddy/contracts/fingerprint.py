"""Fingerprint record (design §10, AD-6). Contracts owns only the record SHAPE.

``fingerprints_equal`` raises on incomparable records (serializer-tag mismatch or a
missing serializer/digest on either side) — cross-tag comparison is a programming
error, never a "changed" verdict, and an absent digest must never compare equal by
omission.
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
