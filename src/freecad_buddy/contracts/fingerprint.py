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
            f"cannot compare fingerprints: serializer tag missing/mismatch ({ser_a!r} vs {ser_b!r})"
        )

    dig_a = a.get("digest")
    dig_b = b.get("digest")
    if dig_a is None or dig_b is None:
        raise ValueError(f"cannot compare fingerprints: digest missing ({dig_a!r} vs {dig_b!r})")

    return dig_a == dig_b


# Mass-property keys compared exactly — stable to the last bit across a render. ``bbox`` is
# excluded: FreeCAD's ``Shape.BoundBox`` is computed from the current tessellation, so refining
# the mesh (which a render or export does) shifts the approximate bounds. ``com`` is excluded from
# the EXACT set for the same reason and compared with a tolerance below, because OCCT evaluates
# ``CenterOfMass`` over a curved solid's triangulation rather than its analytic surfaces.
_INVARIANT_MASSPROP_KEYS = ("volume", "area", "principal_moments")

# How far a centre of mass may move before it counts as a mutation, in millimetres.
#
# ``com`` cannot simply be dropped: volume, area and the principal moments are ALL invariant under
# a translation, so the centre of mass is the only thing in this record that notices a part being
# moved. Measured: rendering a plain ``Part::Cut`` hollow sleeve (9 mm outer, 5 mm bore, 16 mm
# long) moves its reported com from [0.0, 0.0, 8.0] to [0.020376, 0.0, 8.0] while volume, area and
# moments stay bit-identical — the render refines the triangulation the value is integrated over.
# A flat-faced part shows no such shift, which is why this only surfaced on turned geometry.
#
# The band is 0.05 mm: above the measured 0.0204 mm jitter, and the same linear tolerance the G3
# specs already declare for a dimension. Anything a caller would call "moved" is far larger, and
# anything this absorbs is smaller than the tolerance every downstream assertion works to.
_COM_TOLERANCE_MM = 0.05


def massprops_equal(a: dict, b: dict) -> bool:
    """Compare two FingerprintRecords geometrically: volume/area/moments exactly, COM to a band.

    Unlike ``fingerprints_equal`` (which compares the ``digest`` over raw BRep bytes), this
    ignores both the serialized shape bytes and the tessellation-derived bounding box. OCCT
    re-lays-out a shape's BRep bytes the first time a freshly-loaded shape is touched (e.g. by a
    render), and a render/export refines the tessellation so ``bbox`` and the centre of mass of a
    curved solid shift — yet the exact geometric invariants stay identical. Use this for a
    read-only check where a render must not alter the geometry but may perturb the serialization
    or the tessellation.
    """

    def _invariants(record: dict) -> dict:
        result = {}
        for entry in record.get("objects", []):
            mp = entry.get("massprops") or {}
            result[entry["name"]] = {k: mp.get(k) for k in _INVARIANT_MASSPROP_KEYS}
        return result

    if _invariants(a) != _invariants(b):
        return False

    def _centres(record: dict) -> dict:
        return {
            entry["name"]: (entry.get("massprops") or {}).get("com")
            for entry in record.get("objects", [])
        }

    centres_a, centres_b = _centres(a), _centres(b)
    if set(centres_a) != set(centres_b):
        return False
    return all(_com_within_band(centres_a[name], centres_b[name]) for name in centres_a)


def _com_within_band(a: object, b: object) -> bool:
    """Whether two centres of mass agree within ``_COM_TOLERANCE_MM`` on every axis.

    A missing or malformed value falls back to exact equality: an object whose centre of mass
    could not be read is not silently treated as unchanged.
    """
    if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)) or len(a) != len(b):
        return a == b
    try:
        return all(abs(float(x) - float(y)) <= _COM_TOLERANCE_MM for x, y in zip(a, b))
    except (TypeError, ValueError):
        return a == b
