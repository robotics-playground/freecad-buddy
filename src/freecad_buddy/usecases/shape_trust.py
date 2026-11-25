"""Whether a shape is one the boolean and distance kernels can be trusted on.

Stdlib only: the shapes are read through their FreeCAD attributes, never imported.
"""

from __future__ import annotations

import math


def solid_volumes(shape: object):
    """Yield the signed volume of each solid in ``shape``, and ``None`` for any other content.

    A ``Compound`` or ``CompSolid`` is walked; a shell, face, wire or edge yields ``None``. A solid
    with reversed orientation reports a negative volume (``Part::Reverse``).
    """
    if shape.ShapeType == "Solid":
        yield float(shape.Volume)
    elif shape.ShapeType in ("Compound", "CompSolid"):
        for sub in shape.SubShapes:
            yield from solid_volumes(sub)
    else:
        yield None


def is_measurable_solid(shape: object) -> bool:
    """Whether the boolean and distance kernels can be trusted on ``shape``.

    True only for a valid shape made of solids that all have a positive volume. OCC reads a
    reversed solid as the material outside its faces, finds no inner distance solution for an
    invalid solid, and a shell encloses no volume, so each of those can turn a real overlap into
    an empty ``common`` with a positive distance.
    """
    try:
        volumes = list(solid_volumes(shape))
        return (
            bool(volumes)
            and all(
                volume is not None and volume > 0 and math.isfinite(volume) for volume in volumes
            )
            and bool(shape.isValid())
        )
    except Exception:  # noqa: BLE001 -- a shape the kernel cannot even inspect is not measurable
        return False
