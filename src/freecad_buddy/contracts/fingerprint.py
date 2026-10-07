"""Fingerprint record shape and comparison helper.

``fingerprints_equal`` raises on incomparable records (serializer-tag mismatch or a
missing serializer/digest on either side) so cross-tag comparison never yields a
"changed" verdict and an absent digest never compares equal by omission.
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


class MassProps(TypedDict):
    volume: float
    area: float
    bbox: list[float]
    com: list[float]
    principal_moments: list[float]
    # Ixx, Iyy, Izz, Ixy, Ixz, Iyz about ``com`` in document axes, the elements of OCC's
    # ``MatrixOfInertia``: the off-diagonals are the negated products of inertia (Ixy = -∫xy dm).
    # Optional because records written before it existed lack it; ``massprops_equal`` never treats
    # a missing tensor as equal. It and ``principal_moments`` are not rounded to ``quantum`` but to
    # a per-object step 9 digits below the largest diagonal component, because they jitter in the
    # last bits of their magnitude.
    inertia: NotRequired[list[float]]
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
# (volume, area, centre of mass, principal moments, inertia tensor) is unchanged. ``inertia`` is
# here because principal moments are eigenvalues: a rotation or mirror about the centre of mass
# keeps them and changes only the tensor.
_INVARIANT_MASSPROP_KEYS = ("volume", "area", "com", "principal_moments", "inertia")


def massprops_equal(a: dict, b: dict) -> bool:
    """Compare two FingerprintRecords by exact geometry: per-object volume/area/COM/moments/inertia.

    Unlike ``fingerprints_equal`` (which compares the ``digest`` over raw BRep bytes), this
    ignores both the serialized shape bytes and the tessellation-derived bounding box. OCCT
    re-lays-out a shape's BRep bytes the first time a freshly-loaded shape is touched (e.g. by a
    render), and a render/export refines the tessellation so ``bbox`` shifts — yet the exact
    geometric invariants stay identical. Use this for a read-only check where a render must not
    alter the geometry but may perturb the serialization or the tessellation.

    It is also the snapshot-restore rollback proof in ``run_mutation``: reopening the snapshot
    file re-serializes every shape, so the digest cannot match there. Records whose object-name
    sets differ are unequal, and an entry without ``inertia`` (a record written before the field
    existed) is unequal to every entry, itself included, so no comparison is equal by omission.

    Limit: a change that leaves the inertia tensor unchanged compares equal; mass properties
    cannot see it. That is a 180 degree rotation about a principal axis through the centre of
    mass, a point reflection through the centre of mass, a mirror through a plane through the
    centre of mass normal to a principal axis, any rotation of a solid with three equal moments
    (a cube, a sphere), and a rotation of an axisymmetric part about its axis. A compound with no
    solids (a multi-wire or point-bearing sketch, a compound of faces) records zero moments and a
    zero tensor, so any rotation of it compares equal.
    """

    def _invariants(record: dict) -> dict:
        result = {}
        for entry in record.get("objects", []):
            mp = entry.get("massprops") or {}
            result[entry["name"]] = {k: mp.get(k) for k in _INVARIANT_MASSPROP_KEYS}
        return result

    left = _invariants(a)
    right = _invariants(b)
    if any(mp["inertia"] is None for mp in (*left.values(), *right.values())):
        return False
    return left == right
