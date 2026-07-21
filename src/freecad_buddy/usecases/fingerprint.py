"""The single document fingerprint oracle.

``fingerprint(doc)`` produces a ``FingerprintRecord``: a SHA-256 ``digest`` over per-object
serialized shape bytes and a quantized mass-property tuple (objects ordered by immutable
``Name``). Both the per-object B-rep hash and the mass-property tuple are recorded on each
entry so a diff can inspect either. The serializer is shim-probed (``exportBinary`` when
exposed, else ``exportBrep``) and tagged on every record; comparing across tags is banned
(``contracts.fingerprints_equal`` raises). Objects with a null or absent ``Shape`` are
skipped, never hashed. Stdlib + FreeCAD App API only; FreeCAD is imported lazily.
"""

from __future__ import annotations

import hashlib
import io
import math
import os
import tempfile

from freecad_buddy.contracts import FingerprintRecord, MassProps
from freecad_buddy.usecases import shim

Q = 1e-6


class SerializerUnavailable(RuntimeError):
    """Raised when the build exposes neither ``exportBinary`` nor ``exportBrep`` on a shape."""


def _quantize(value: float) -> float:
    """Round ``value`` to the fixed quantization step ``Q`` (1e-6); non-finite floors to 0.0.

    A degenerate shape can yield ``nan``/``inf`` mass properties; coercing them to ``0.0`` keeps
    the record JSON-serializable and the digest deterministic.
    """
    number = float(value)
    if not math.isfinite(number):
        return 0.0
    return round(number / Q) * Q


def _principal_moments(shape: object) -> tuple[float, float, float]:
    """Return the three principal moments of inertia as a deterministic triple.

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
        fd, path = tempfile.mkstemp(prefix="FCB_TMP_fp_", suffix=".bin")
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


def _massprops(shape: object) -> MassProps:
    """Return the quantized mass-property cross-oracle tuple for ``shape``.

    Every component (volume, area, bbox extents, centre of mass, principal moments) is rounded
    to the fixed quantization step ``Q`` so small numeric jitter does not change the record.
    """
    bb = shape.BoundBox
    com = _center_of_mass(shape)
    bbox = [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax]
    return {
        "volume": _quantize(float(shape.Volume)),
        "area": _quantize(float(shape.Area)),
        "bbox": [_quantize(v) for v in bbox],
        "com": [_quantize(c) for c in com],
        "principal_moments": [_quantize(m) for m in _principal_moments(shape)],
        "quantum": Q,
    }


def fingerprint(doc: object) -> FingerprintRecord:
    """Return the ``FingerprintRecord`` for ``doc``.

    Iterates ``doc.Objects`` in immutable ``Name`` order, skipping objects with a null or
    absent ``Shape``. Each surviving object contributes ``{name, brep_sha256, massprops}``; the
    record ``digest`` is the SHA-256 over the repr of the ordered entries. The serializer tag
    is shim-probed once and stamped on the record.
    """
    entries: list[dict] = []
    for obj in sorted(doc.Objects, key=lambda o: o.Name):
        shape = getattr(obj, "Shape", None)
        is_null = getattr(shape, "isNull", None)
        if shape is None or (is_null is not None and is_null()):
            continue
        raw = _serialize(shape)
        entries.append(
            {
                "name": obj.Name,
                "brep_sha256": hashlib.sha256(raw).hexdigest(),
                "massprops": _massprops(shape),
            }
        )
    digest_material = repr([(e["name"], e["brep_sha256"], e["massprops"]) for e in entries]).encode(
        "utf-8"
    )
    return {
        "schema": "fcb.fingerprint/1",
        "serializer": shim.serializer_tag(),
        "objects": entries,
        "digest": hashlib.sha256(digest_material).hexdigest(),
    }
