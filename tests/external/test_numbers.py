"""Display rounding: every row of the spec's I/O matrix that the contracts ring can express."""

import math

import pytest

from freecad_buddy.contracts.numbers import displayed_deviation, round_display, round_floats

ROUND_DISPLAY_CASES = [
    pytest.param(5.999999998, 2, 6.0, id="solver-noise"),
    pytest.param(6.0000001, 2, 6.0, id="kernel-gap"),
    pytest.param(1234.5678, 2, 1234.57, id="real-value"),
    pytest.param(3.3e-8, 2, 3.3e-8, id="tiny-real"),
    pytest.param(3.33333e-8, 2, 3.33e-8, id="tiny-real-keeps-three-significant-digits"),
    pytest.param(-4.281973375071899e-16, 2, 0.0, id="noise-at-zero"),
    pytest.param(-0.0, 2, 0.0, id="negative-zero"),
    pytest.param(5.12345, 4, 5.1235, id="preference-4"),
]


@pytest.mark.parametrize(("value", "decimals", "expected"), ROUND_DISPLAY_CASES)
def test_should_return_the_displayed_value_when_a_float_is_rounded(value, decimals, expected):
    # Arrange
    target = round_display

    # Act
    out = target(value, decimals)

    # Assert
    assert out == expected
    assert math.copysign(1.0, out) == math.copysign(1.0, expected)


@pytest.mark.parametrize("value", [math.inf, -math.inf], ids=["inf", "-inf"])
def test_should_keep_the_value_when_it_is_infinite(value):
    # Arrange
    decimals = 2

    # Act
    out = round_display(value, decimals)

    # Assert
    assert out == value


def test_should_keep_nan_when_the_value_is_nan():
    # Arrange
    value = math.nan

    # Act
    out = round_display(value, 2)

    # Assert
    assert math.isnan(out)


def test_should_round_every_nested_float_and_keep_other_types_when_a_body_is_walked():
    # Arrange
    body = {
        "count": 3,
        "flag": True,
        "name": "Pad",
        "none": None,
        "volume": 1234.5678,
        "bbox": [0.0, -0.0, 6.0000001],
        "com": (1.004, 2.0, 3.3e-8),
        "nested": {"checks": [{"measured": 5.999999998, "expected": 6}]},
    }

    # Act
    out = round_floats(body, 2)

    # Assert
    assert out == {
        "count": 3,
        "flag": True,
        "name": "Pad",
        "none": None,
        "volume": 1234.57,
        "bbox": [0.0, 0.0, 6.0],
        "com": [1.0, 2.0, 3.3e-8],
        "nested": {"checks": [{"measured": 6.0, "expected": 6}]},
    }
    assert type(out["count"]) is int
    assert type(out["flag"]) is bool
    assert type(out["nested"]["checks"][0]["expected"]) is int


@pytest.mark.parametrize("key", ["tolerance", "tol"])
def test_should_keep_the_echoed_tolerance_raw_when_a_body_is_walked(key):
    # Arrange
    body = {"checks": [{"measured": 5.999999998, key: {"rel": 0.005, "abs": 0.0123456}}]}

    # Act
    out = round_floats(body, 2)

    # Assert
    assert out == {"checks": [{"measured": 6.0, key: {"rel": 0.005, "abs": 0.0123456}}]}


def test_should_leave_the_input_unchanged_when_a_body_is_walked():
    # Arrange
    body = {"values": [5.999999998]}

    # Act
    round_floats(body, 2)

    # Assert
    assert body == {"values": [5.999999998]}


VERDICT_CASES = [
    pytest.param(5.999999998, 6, 0.05, 2e-09, True, id="noise"),
    pytest.param(6.0150001, 6.015, 0.001, 1e-07, True, id="straddle"),
    pytest.param(6.054, 6.0, 0.05, 0.05, True, id="edge"),
    pytest.param(6.004, 6.0, 0.001, 0.004, False, id="tight"),
]


@pytest.mark.parametrize(("measured", "expected", "band", "deviation", "passed"), VERDICT_CASES)
def test_should_compare_the_once_rounded_deviation_with_the_raw_band_when_a_verdict_is_taken(
    measured, expected, band, deviation, passed
):
    # Arrange
    decimals = 2

    # Act
    out = displayed_deviation(measured, expected, decimals)

    # Assert
    assert out == deviation
    assert (out <= band) is passed


def test_should_keep_every_value_raw_when_rounding_is_off():
    # Arrange
    body = {"values": [5.999999998, -4.281973375071899e-16]}

    # Act
    value = round_display(5.999999998, None)
    walked = round_floats(body, None)
    deviation = displayed_deviation(6.054, 6.0, None)

    # Assert
    assert value == 5.999999998
    assert walked is body
    assert deviation == abs(6.054 - 6.0)
    assert deviation > 0.05
