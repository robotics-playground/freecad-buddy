"""FreeCAD-free unit tests for the rate-statistics helpers.

Wilson CI values are checked against the closed-form expressions computed independently here;
the rate helpers are checked including their zero-denominator guards.
"""

from __future__ import annotations

import math

from freecad_buddy.usecases import stats


def _wilson_reference(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return p, max(0.0, center - half), min(1.0, center + half)


def test_wilson_ci_matches_closed_form_on_partial_success():
    result = stats.wilson_ci(8, 10)

    rate, low, high = _wilson_reference(8, 10)
    assert result["rate"] == rate
    assert math.isclose(result["low"], low, rel_tol=1e-12)
    assert math.isclose(result["high"], high, rel_tol=1e-12)
    assert result["n"] == 10
    assert result["r"] == 8


def test_wilson_ci_all_success_upper_bound_is_one_lower_below_one():
    result = stats.wilson_ci(11, 11)

    assert result["rate"] == 1.0
    assert result["high"] == 1.0
    assert result["low"] < 1.0  # a small n never proves certainty


def test_wilson_ci_zero_trials_is_full_unit_interval():
    result = stats.wilson_ci(0, 0)

    assert result == {"rate": 0.0, "low": 0.0, "high": 1.0, "n": 0, "r": 0}


def test_wilson_ci_rejects_out_of_range_inputs():
    for k, n in ((3, 2), (-1, 5), (0, -1)):
        try:
            stats.wilson_ci(k, n)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for k={k}, n={n}")


def test_sensitivity_and_false_alarm_arithmetic():
    assert stats.sensitivity(11, 11) == 1.0
    assert stats.sensitivity(9, 10) == 0.9
    assert stats.false_alarm(0, 1) == 0.0
    assert stats.false_alarm(1, 4) == 0.25


def test_rate_helpers_guard_zero_denominator():
    assert stats.sensitivity(0, 0) == 0.0
    assert stats.false_alarm(0, 0) == 0.0
