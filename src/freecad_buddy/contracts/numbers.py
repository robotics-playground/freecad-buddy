"""Display rounding: every float an agent reads, at FreeCAD's display precision.

FreeCAD shows a quantity with the ``Decimals`` unit preference (``BaseApp/Preferences/Units``,
default 2). Kernel and solver noise lies far below that step — the Sketcher solver stops at
``convergence(1e-10)`` (``GCS.cpp:484``) and the OCC tolerance is 1e-7 — so without rounding a
raw ``5.999999998`` reaches the agent where the GUI shows ``6.00 mm``. Rounding is in decimal
places of the internal units; no unit is switched.

A verdict compares ``displayed_deviation`` with its raw band. Rounding the measured and expected
values separately would fail a correct part whose two values straddle a rounding boundary, and
rounding the band would widen a declared tolerance.

``decimals`` of ``None`` means rounding is turned off: values, and the deviation a verdict
compares, stay raw.
"""

from __future__ import annotations

import math

DEFAULT_DISPLAY_DECIMALS = 2

# Below this magnitude a value is noise and reads as zero: kernel arithmetic leaves residues near
# 1e-16 (a volume delta of -4.28e-16 was captured in UAT), and the solver converges to 1e-10. The
# smallest real values a result carries sit well above it: the OCC shape tolerance 1e-7 and a
# moment of inertia near 3e-8.
_ZERO_FLOOR = 1e-9

# A real value below the display step keeps this many significant digits instead of reading as a
# false zero.
_TINY_SIGNIFICANT_DIGITS = 3

# Echoed tolerances keep their declared value: ``rel 0.005`` must not read as ``0.01``.
_RAW_KEYS = frozenset({"tolerance", "tol"})


def round_display(value: float, decimals: int | None) -> float:
    """``value`` as FreeCAD displays it with ``decimals`` places.

    A non-finite value, or any value when ``decimals`` is ``None``, is returned unchanged. A
    magnitude below ``_ZERO_FLOOR`` (``-0.0`` included) becomes ``0.0``, and any other value that
    would round to zero keeps three significant digits.
    """
    if decimals is None or not math.isfinite(value):
        return value
    if abs(value) < _ZERO_FLOOR:
        return 0.0
    rounded = round(value, decimals)
    if rounded != 0.0:
        return rounded
    return float(f"{value:.{_TINY_SIGNIFICANT_DIGITS}g}")


def round_floats(obj, decimals: int | None):
    """A copy of ``obj`` with every float, at any depth, passed through ``round_display``.

    The subtree under a ``tolerance`` or ``tol`` key is kept as it is. Integers and booleans keep
    their type; tuples become lists, as JSON encodes them. ``decimals`` of ``None`` returns ``obj``
    itself.
    """
    if decimals is None:
        return obj
    if isinstance(obj, float):
        return round_display(obj, decimals)
    if isinstance(obj, dict):
        return {
            key: item if key in _RAW_KEYS else round_floats(item, decimals)
            for key, item in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [round_floats(item, decimals) for item in obj]
    return obj


def displayed_deviation(measured: float, expected: float, decimals: int | None) -> float:
    """``|measured - expected|`` from the raw operands, rounded once for display.

    A check passes when this is at most its raw band.
    """
    return round_display(abs(float(measured) - float(expected)), decimals)
