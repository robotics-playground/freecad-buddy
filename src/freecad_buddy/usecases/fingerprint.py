"""The single document fingerprint oracle.

``fingerprint(doc)`` produces a ``FingerprintRecord``: a SHA-256 ``digest`` over per-object
serialized shape bytes and a quantized mass-property tuple (objects ordered by immutable
``Name``). Both the per-object B-rep hash and the mass-property tuple are recorded on each
entry so a diff can inspect either. The serializer is shim-probed (``exportBinary`` when
exposed, else ``exportBrep``) and tagged on every record; comparing across tags is banned
(``contracts.fingerprints_equal`` raises). An object with a null ``Shape`` is recorded with the
hash of empty bytes and zeroed mass properties; an object with no ``Shape`` attribute is skipped.

An unchanged shape is not serialized and integrated again: each document keeps its last entry per
object together with the ``TopoShape`` it was computed from, and reuses the entry while the
current shape ``isEqual`` that one (same TShape, location and orientation). The cache holds the
shape, so its TShape cannot be freed and its address reused by a different shape. ``fresh=True``
computes every entry anew; the rollback proofs use it.

Mass properties of a shape that has solids come from its solids, combined with the parallel-axis
rule, because a ``Compound`` exposes no centre of mass, inertia matrix or principal moments. The
record carries the inertia tensor as well as its eigenvalues: the principal moments of a solid
rotated or mirrored about its centre of mass do not change, its tensor does. The tensor itself
does not change, and the record stays equal, under a 180 degree rotation about a principal axis
through the centre of mass, a point reflection through the centre of mass, a mirror through a
plane through the centre of mass normal to a principal axis, any rotation of a solid with three
equal moments (a cube, a sphere), and a rotation of an axisymmetric part about its axis; that
limit is accepted.
Stdlib + FreeCAD App API only; FreeCAD is imported lazily.
"""

from __future__ import annotations

import hashlib
import io
import math
import os
import tempfile
from collections import OrderedDict

from freecad_buddy.contracts import FingerprintRecord, MassProps
from freecad_buddy.usecases import shim
from freecad_buddy.usecases.documents import temp_dir

Q = 1e-6

# Significant digits ``principal_moments`` and ``inertia`` keep: ``_tensor_step`` rounds them to
# 10^(floor(log10(s) + 1e-9) - INERTIA_DIGITS), ``s`` the object's largest diagonal component, so
# the step is about 1e-10 to 1e-9 of ``s``. Both jitter in their last bits: the integration over
# the B-rep a recompute rebuilds rounds differently. On a copy of kiwibox-drawer.FCStd, 12 abort +
# recompute cycles over 4 features moved them by up to 1.8e-7 on riser_zone, whose s is ~1.7e8:
# 1.1e-15 of s, and 1.8e-6 of its 0.1 step. That rounding-boundary crossing rate matches what area
# shows at ``Q`` (1.8e-12 / 1e-6). More digits shrink the step towards the jitter itself; fewer
# round away a small part's rotation.
INERTIA_DIGITS = 9


class SerializerUnavailable(RuntimeError):
    """Raised when the build exposes neither ``exportBinary`` nor ``exportBrep`` on a shape."""


def _quantize(value: float, step: float = Q) -> float:
    """Round ``value`` to the caller's ``step`` (default ``Q``); non-finite floors to 0.0.

    A degenerate shape can yield ``nan``/``inf`` mass properties; coercing them to ``0.0`` keeps
    the record JSON-serializable and the digest deterministic.
    """
    number = float(value)
    if not math.isfinite(number):
        return 0.0
    return round(number / step) * step


def _tensor_step(tensor: tuple[float, ...]) -> float:
    """Quantization step for ``tensor`` and its eigenvalues: ``INERTIA_DIGITS`` below its scale.

    The scale ``s`` is the largest absolute diagonal component. A step relative to ``s`` keeps a
    small part's rotation visible, where a fixed absolute step would round it away. When ``s`` is
    0 or not finite there is no scale, and the step is ``Q``.
    """
    diagonal = [abs(component) for component in tensor[:3]]
    # ``max`` skips a ``nan`` that is not first, so finiteness is checked on every component.
    if not all(math.isfinite(component) for component in diagonal) or max(diagonal) == 0.0:
        return Q
    scale = max(diagonal)
    # ``+ 1e-9`` moves each step boundary from s = 10^k down to s = 10^k·(1 − 2.3e-9). Round
    # dimensions put ``s`` exactly on a power of ten (a 6 x 10 x 10 mm box has s = 10000.0); with
    # the boundary there, last-bit jitter in ``s`` flips the step 10x and changes the record.
    return 10.0 ** (math.floor(math.log10(scale) + 1e-9) - INERTIA_DIGITS)


def _principal_moments(shape: object) -> tuple[float, float, float]:
    """Return the three principal moments of inertia of a shape that has no solids.

    Prefers ``Shape.PrincipalProperties['Moments']`` when the build exposes it, else derives
    the eigen-ordered diagonal of ``Shape.MatrixOfInertia``. Falls back to the sorted matrix
    diagonal when the full matrix is unavailable, keeping the value deterministic and
    quantized downstream.
    """
    props = getattr(shape, "PrincipalProperties", None)
    if isinstance(props, dict):
        moments = props.get("Moments")
        if moments is not None:
            return tuple(float(m) for m in moments)[:3]

    matrix = getattr(shape, "MatrixOfInertia", None)
    if matrix is not None:
        diag = sorted((float(matrix.A11), float(matrix.A22), float(matrix.A33)), reverse=True)
        return diag[0], diag[1], diag[2]

    return 0.0, 0.0, 0.0


def _serialize(shape: object) -> bytes:
    """Serialize ``shape`` to deterministic bytes via the shim-probed serializer.

    Uses ``exportBinary`` when the build exposes it (OCCT BinTools, byte-deterministic for an
    unchanged in-memory shape) — the Python binding writes to a filename, so the bytes are
    read back from a reserved-prefix temp file. Otherwise ``exportBrep`` writes to a byte
    stream. Raises ``SerializerUnavailable`` when neither path exists.
    """
    if shim.export_binary_available():
        fd, path = tempfile.mkstemp(prefix="FCB_TMP_fp_", suffix=".bin", dir=temp_dir())
        os.close(fd)
        try:
            shape.exportBinary(path)
            with open(path, "rb") as handle:
                return handle.read()
        finally:
            os.remove(path)

    export_brep = getattr(shape, "exportBrep", None)
    if export_brep is None:
        raise SerializerUnavailable(
            "shape exposes neither exportBinary nor exportBrep; cannot fingerprint"
        )
    buffer = io.BytesIO()
    export_brep(buffer)
    return buffer.getvalue()


def _center_of_mass(shape: object) -> tuple[float, float, float]:
    """Return the centre of mass, falling back to the bounding-box centre for compounds.

    ``CenterOfMass`` is undefined on some shape types (compounds, empty shapes); the bbox
    centre is a deterministic substitute in that case.
    """
    com = getattr(shape, "CenterOfMass", None)
    if com is not None:
        return float(com.x), float(com.y), float(com.z)
    bb = shape.BoundBox
    return (
        float(bb.XMin + bb.XMax) / 2,
        float(bb.YMin + bb.YMax) / 2,
        float(bb.ZMin + bb.ZMax) / 2,
    )


def _inertia_components(matrix: object) -> tuple[float, ...]:
    """``[Ixx, Iyy, Izz, Ixy, Ixz, Iyz]`` from a ``Base.Matrix`` holding an OCC inertia matrix.

    OCC stores the products of inertia negated in the off-diagonal elements; they are kept as
    stored, so the six values are the elements of the inertia tensor itself.
    """
    return (
        float(matrix.A11),
        float(matrix.A22),
        float(matrix.A33),
        float(matrix.A12),
        float(matrix.A13),
        float(matrix.A23),
    )


def _principal_tensor(props: dict) -> tuple[float, tuple[float, ...]]:
    """Return a solid's volume and its inertia tensor about its centre of mass.

    Rebuilt from one ``PrincipalProperties`` integration: the tensor is ``Σk λk·ak·akᵀ`` over the
    ``Moments`` λ and the unit ``First/Second/ThirdAxisOfInertia`` a, which is the matrix
    ``MatrixOfInertia`` returns, products of inertia negated included. ``RadiusOfGyration`` is
    ``rk = sqrt(λk / v)``, so the volume is ``λk / rk²`` on the axis with the largest ``rk``, the
    best-conditioned one, and 0 when every ``rk`` is 0 (a solid with no enclosed volume).

    ``MatrixOfInertia`` and ``Volume`` are not read: each is one more integration over the solid.
    Reading both from ``PrincipalProperties`` saves one integration per solid, which took the
    fingerprint of kiwibox-drawer.FCStd from 7.32 s to 5.81 s.
    """
    tensor = [0.0] * 6
    axes = (
        props["FirstAxisOfInertia"],
        props["SecondAxisOfInertia"],
        props["ThirdAxisOfInertia"],
    )
    for moment, axis in zip(props["Moments"], axes, strict=True):
        x, y, z = float(axis.x), float(axis.y), float(axis.z)
        outer = (x * x, y * y, z * z, x * y, x * z, y * z)
        tensor = [sum_ + float(moment) * term for sum_, term in zip(tensor, outer)]
    radii = [float(radius) for radius in props["RadiusOfGyration"]]
    widest = max(range(3), key=lambda index: radii[index])
    if not radii[widest] > 0.0:
        return 0.0, tuple(tensor)
    return float(props["Moments"][widest]) / radii[widest] ** 2, tuple(tensor)


# Jacobi converges quadratically: with distinct or two equal moments the off-diagonal elements
# reach exactly 0 in at most 6 sweeps (20,000 random rotations and scales, 2e-16 noise). With
# three equal moments (a sphere, a tilted cube) a rotation no longer moves the diagonal by one ulp,
# so the off-diagonal elements, already below the diagonal's rounding, shrink only about 3x per
# sweep and never reach 0; the diagonal is already exact to its rounding there. The bound ends
# that case and a tensor holding a non-finite value.
_JACOBI_SWEEPS = 50


def _eigenvalues(tensor: tuple[float, ...]) -> tuple[float, float, float]:
    """Eigenvalues of the symmetric 3x3 ``tensor`` (``_inertia_components`` order), descending.

    Cyclic Jacobi rotations: each rotation zeroes one off-diagonal element, and sweeps over the
    pairs (0, 1), (0, 2), (1, 2) repeat until every off-diagonal element is 0, at most
    ``_JACOBI_SWEEPS`` times. Jacobi keeps the error near the rounding of the tensor itself for
    distinct, repeated and triple eigenvalues. The trigonometric closed form does not: with two
    equal moments (a cylinder, a revolved part) its ``acos`` near ±1 turned 2e-16 relative noise
    into an error of 0.86 on moments of 1.7e8, more than eight steps of 0.1.
    """
    xx, yy, zz, xy, xz, yz = tensor
    matrix = [[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]]
    for _ in range(_JACOBI_SWEEPS):
        # ``x * x``, not ``x ** 2``: a float ``**`` raises OverflowError above 1.34e154, ``*``
        # returns inf and the sweep bound ends the loop.
        off_diagonal = (matrix[0][1], matrix[0][2], matrix[1][2])
        if sum(element * element for element in off_diagonal) == 0.0:
            break
        for p, q in ((0, 1), (0, 2), (1, 2)):
            _jacobi_rotate(matrix, p, q)
    first, second, third = sorted((matrix[0][0], matrix[1][1], matrix[2][2]), reverse=True)
    return first, second, third


def _jacobi_rotate(matrix: list[list[float]], p: int, q: int) -> None:
    """Rotate the symmetric 3x3 ``matrix`` in place in the (p, q) plane so ``matrix[p][q]`` is 0.

    Numerical Recipes form: ``t = tan(angle)`` is the smaller root, so the rotation angle is at
    most 45 degrees, and the other row is updated through ``tau = sin / (1 + cos)``.
    """
    element = matrix[p][q]
    if element == 0.0:
        return
    theta = (matrix[q][q] - matrix[p][p]) / (2.0 * element)
    t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta * theta + 1.0))
    cosine = 1.0 / math.sqrt(t * t + 1.0)
    sine = t * cosine
    tau = sine / (1.0 + cosine)
    matrix[p][p] -= t * element
    matrix[q][q] += t * element
    matrix[p][q] = matrix[q][p] = 0.0
    r = 3 - p - q
    rp, rq = matrix[r][p], matrix[r][q]
    matrix[r][p] = matrix[p][r] = rp - sine * (rq + tau * rp)
    matrix[r][q] = matrix[q][r] = rq + sine * (rp - tau * rq)


def _solid_mass_properties(
    shape: object, solids: list
) -> tuple[float, tuple[float, ...], tuple[float, ...]]:
    """Return the volume, centre of mass and inertia tensor about it of ``solids`` combined.

    Each solid is integrated twice: ``CenterOfMass``, and ``PrincipalProperties`` for its volume
    and its tensor about its own centre of mass in document axes (``_principal_tensor``). With
    density 1, ``V = Σv``, ``C = Σv·c / V`` and ``T = Σ[M + v·(|d|²·E − d·dᵀ)]`` for
    ``d = c − C``; the ``−d·dᵀ`` term matches OCC's negated off-diagonals. A zero total volume has
    no mass-weighted centre, so the centre falls back to ``_center_of_mass(shape)``.
    """
    measured = []
    for solid in solids:
        center = solid.CenterOfMass
        volume, own = _principal_tensor(solid.PrincipalProperties)
        measured.append((volume, (float(center.x), float(center.y), float(center.z)), own))
    total = sum(volume for volume, _, _ in measured)
    if total == 0.0:
        com = _center_of_mass(shape)
    else:
        com = tuple(
            sum(volume * center[axis] for volume, center, _ in measured) / total
            for axis in range(3)
        )
    tensor = [0.0] * 6
    for volume, center, own in measured:
        dx, dy, dz = center[0] - com[0], center[1] - com[1], center[2] - com[2]
        squared = dx * dx + dy * dy + dz * dz
        shift = (
            volume * (squared - dx * dx),
            volume * (squared - dy * dy),
            volume * (squared - dz * dz),
            -volume * dx * dy,
            -volume * dx * dz,
            -volume * dy * dz,
        )
        tensor = [sum_ + matrix + offset for sum_, matrix, offset in zip(tensor, own, shift)]
    return total, com, tuple(tensor)


def _massprops(shape: object) -> MassProps:
    """Return the quantized mass-property cross-oracle tuple for ``shape``.

    A shape with solids, a single ``Solid`` included, takes volume, centre of mass, inertia
    tensor and principal moments (the tensor's eigenvalues) from its solids. A shape with no
    solids (sketch, wire, face, shell) keeps its own ``Volume``, ``_center_of_mass`` and
    ``_principal_moments``, and its own ``MatrixOfInertia`` when its type exposes one, else six
    zeros. ``area`` is always ``shape.Area`` and ``bbox`` always ``shape.BoundBox``. Volume,
    area, bbox and centre are rounded to ``Q``; the moments and the tensor to the object's
    ``_tensor_step``, so small numeric jitter does not change the record.

    The tensor separates a rotation or mirror about the centre of mass that the moments cannot,
    except where the tensor itself does not change: a 180 degree rotation about a principal axis
    through the centre of mass, a point reflection through the centre of mass, a mirror through
    a plane through the centre of mass normal to a principal axis, any rotation of a solid with
    three equal moments, and a rotation of an axisymmetric part about its axis.
    """
    bb = shape.BoundBox
    bbox = [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax]
    solids = shape.Solids
    if solids:
        volume, com, inertia = _solid_mass_properties(shape, solids)
        moments = _eigenvalues(inertia)
    else:
        volume = float(shape.Volume)
        com = _center_of_mass(shape)
        moments = _principal_moments(shape)
        matrix = getattr(shape, "MatrixOfInertia", None)
        inertia = (0.0,) * 6 if matrix is None else _inertia_components(matrix)
    step = _tensor_step(inertia)
    return {
        "volume": _quantize(volume),
        "area": _quantize(float(shape.Area)),
        "bbox": [_quantize(v) for v in bbox],
        "com": [_quantize(c) for c in com],
        "principal_moments": [_quantize(m, step) for m in moments],
        "inertia": [_quantize(component, step) for component in inertia],
        "quantum": Q,
    }


# The entry a null shape contributes. A real serialization is never empty, so the empty-bytes hash
# cannot match a real shape, and the fields keep the str / MassProps types fcb.fingerprint/1
# declares.
_NULL_SHAPE_SHA256 = hashlib.sha256(b"").hexdigest()


def _null_massprops() -> MassProps:
    """Zeroed mass properties for an object whose ``Shape`` is null."""
    return {
        "volume": 0.0,
        "area": 0.0,
        "bbox": [0.0] * 6,
        "com": [0.0] * 3,
        "principal_moments": [0.0] * 3,
        "inertia": [0.0] * 6,
        "quantum": Q,
    }


# Datum features carry construction geometry, not model shape. They are excluded because an
# App::Plane is INFINITE: a PartDesign Body's auto-created XZ_Plane spans +/-1e100 with
# Area == 8.000000000000003e+100, and a float of that magnitude loses its low-order bits through
# saveCopy + reopen. Hashing one makes the snapshot-restore rollback proof fail on any document
# holding a Body, because the re-hash after the restore can never match. The same four types are
# excluded from the tree summary and the default render set.
_DATUM_TYPE_PREFIXES = ("App::Origin", "App::Line", "App::Plane", "App::Point")


def _is_datum(obj: object) -> bool:
    """Whether ``obj`` is a datum feature rather than model geometry."""
    return str(getattr(obj, "TypeId", "")).startswith(_DATUM_TYPE_PREFIXES)


# Per document ``Name``: the last entry of each object and the shape it was computed from. Bounded
# to the four most recently fingerprinted documents, least recently used first out: each held shape
# keeps its B-rep in memory.
_ENTRY_CACHE: OrderedDict[str, dict[str, tuple[object, dict]]] = OrderedDict()
_CACHED_DOCUMENTS = 4


def _entry(name: str, shape: object, cached: tuple[object, dict] | None) -> dict:
    """Return ``name``'s entry, reusing ``cached`` when its shape ``isEqual`` ``shape``."""
    if cached is not None and cached[0].isEqual(shape):
        return cached[1]
    raw = _serialize(shape)
    return {
        "name": name,
        "brep_sha256": hashlib.sha256(raw).hexdigest(),
        "massprops": _massprops(shape),
    }


def fingerprint(doc: object, fresh: bool = False) -> FingerprintRecord:
    """Return the ``FingerprintRecord`` for ``doc``.

    Iterates ``doc.Objects`` in immutable ``Name`` order, skipping objects with no ``Shape`` and
    every datum feature (see ``_DATUM_TYPE_PREFIXES``). Each surviving object contributes
    ``{name, brep_sha256, massprops}``; the record ``digest`` is the SHA-256 over the repr of the
    ordered entries. The serializer tag is shim-probed once and stamped on the record.

    An object whose ``Shape`` is null contributes the hash of empty bytes and zeroed mass
    properties. Skipping it would let a feature whose shape went null, such as a Tip whose
    recompute failed, hash equal to the state before it broke, so a rollback that left it broken
    would be proven. A null shape is never cached.

    A non-null shape reuses the entry cached for the object when the cached shape ``isEqual`` the
    current one. The cache for ``doc`` is replaced by this call's entries, so a removed object
    drops out of it.

    :param fresh: compute every entry anew, without reading the cache.
    """
    previous = {} if fresh else _ENTRY_CACHE.get(doc.Name, {})
    current: dict[str, tuple[object, dict]] = {}
    entries: list[dict] = []
    for obj in sorted(doc.Objects, key=lambda o: o.Name):
        if _is_datum(obj):
            continue
        shape = getattr(obj, "Shape", None)
        if shape is None:
            continue
        is_null = getattr(shape, "isNull", None)
        if is_null is not None and is_null():
            entries.append(
                {
                    "name": obj.Name,
                    "brep_sha256": _NULL_SHAPE_SHA256,
                    "massprops": _null_massprops(),
                }
            )
            continue
        entry = _entry(obj.Name, shape, previous.get(obj.Name))
        current[obj.Name] = (shape, entry)
        entries.append(entry)
    _ENTRY_CACHE[doc.Name] = current
    _ENTRY_CACHE.move_to_end(doc.Name)
    while len(_ENTRY_CACHE) > _CACHED_DOCUMENTS:
        _ENTRY_CACHE.popitem(last=False)
    digest_material = repr([(e["name"], e["brep_sha256"], e["massprops"]) for e in entries]).encode(
        "utf-8"
    )
    return {
        "schema": "fcb.fingerprint/1",
        "serializer": shim.serializer_tag(),
        "objects": entries,
        "digest": hashlib.sha256(digest_material).hexdigest(),
    }
