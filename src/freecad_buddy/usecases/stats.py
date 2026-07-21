"""FreeCAD-free rate statistics for validator scoring.

Closed-form Wilson score interval and the two rate helpers the fault scorer reports.
Stdlib math only, so this module imports under pytest in the external process without
FreeCAD present.
"""

from __future__ import annotations

import math

from freecad_buddy.contracts import WilsonCI

Z_95 = 1.96


def wilson_ci(k: int, n: int, z: float = Z_95) -> WilsonCI:
    """Return the Wilson score interval for ``k`` successes in ``n`` trials.

    ``rate`` is the point estimate ``k/n`` and ``low``/``high`` bound it at confidence ``z``
    (default 95%). A zero-``n`` interval degrades to ``rate=0`` over ``[0, 1]``. Raises
    ``ValueError`` when ``n`` is negative or ``k`` is outside ``[0, n]``.
    """
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"invalid Wilson inputs: k={k}, n={n}")
    if n == 0:
        return {"rate": 0.0, "low": 0.0, "high": 1.0, "n": 0, "r": 0}
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return {
        "rate": p,
        "low": max(0.0, center - half),
        "high": min(1.0, center + half),
        "n": n,
        "r": k,
    }


def sensitivity(detected: int, planted: int) -> float:
    """Return ``detected / planted``, or ``0.0`` when no defects were planted."""
    if planted <= 0:
        return 0.0
    return detected / planted


def false_alarm(flagged: int, controls: int) -> float:
    """Return ``flagged / controls``, or ``0.0`` when there are no clean controls."""
    if controls <= 0:
        return 0.0
    return flagged / controls
