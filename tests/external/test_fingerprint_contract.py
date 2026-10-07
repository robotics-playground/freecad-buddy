"""FreeCAD-free tests for the fingerprint module surface.

Confirms the ``fingerprint`` module imports without FreeCAD present (ring discipline: FreeCAD
is imported lazily inside functions) and that its pure quantization helper is deterministic.
The behavioral fingerprint tests (stability / sensitivity / cross-tag) run in-FreeCAD.
"""

from __future__ import annotations

import hashlib
import math
import random
from types import SimpleNamespace

from freecad_buddy.usecases import fingerprint


def test_fingerprint_module_imports_without_freecad():
    assert callable(fingerprint.fingerprint)
    assert callable(fingerprint._serialize)
    assert callable(fingerprint._massprops)


class _NullShape:
    def isNull(self):
        return True


class _Object:
    def __init__(self, name, type_id, **attributes):
        self.Name = name
        self.TypeId = type_id
        self.__dict__.update(attributes)


class _Document:
    def __init__(self, *objects):
        self.Objects = list(objects)


def test_an_object_with_a_null_shape_enters_the_digest_as_empty_bytes_and_zero_massprops():
    spreadsheet = _Object("Sheet", "Spreadsheet::Sheet")
    without = fingerprint.fingerprint(_Document(spreadsheet))

    record = fingerprint.fingerprint(
        _Document(spreadsheet, _Object("Pad", "PartDesign::Pad", Shape=_NullShape()))
    )

    assert record["objects"] == [
        {
            "name": "Pad",
            "brep_sha256": hashlib.sha256(b"").hexdigest(),
            "massprops": {
                "volume": 0.0,
                "area": 0.0,
                "bbox": [0.0] * 6,
                "com": [0.0] * 3,
                "principal_moments": [0.0] * 3,
                "inertia": [0.0] * 6,
                "quantum": 1e-6,
            },
        }
    ]
    assert record["digest"] != without["digest"]


def test_objects_without_a_shape_and_null_datums_stay_out_of_the_record():
    record = fingerprint.fingerprint(
        _Document(
            _Object("Sheet", "Spreadsheet::Sheet"),
            _Object("XY_Plane", "App::Plane", Shape=_NullShape()),
        )
    )

    assert record["objects"] == []


def test_quantize_snaps_to_fixed_step_deterministically():
    assert fingerprint.Q == 1e-6
    snapped = fingerprint._quantize(1.0 + 4e-7)
    assert snapped == fingerprint._quantize(1.0)  # sub-quantum jitter is erased
    assert fingerprint._quantize(2.000002) != fingerprint._quantize(2.0)


def test_should_keep_nine_digits_below_the_largest_diagonal_component_when_rounding_a_tensor():
    # Arrange
    drawer_part = (1.7e8, 1.2e8, 9e7, 3e6, 0.0, 0.0)
    small_part = (2.5e-3, 1e-3, 5e-4, 0.0, 0.0, 0.0)
    off_diagonal_ignored = (10.0, 10.0, 10.0, -5e6, 0.0, 0.0)

    # Act
    steps = [
        fingerprint._tensor_step(tensor)
        for tensor in (drawer_part, small_part, off_diagonal_ignored)
    ]

    # Assert
    assert steps == [10.0**-1, 10.0**-12, 10.0**-8]


def test_should_keep_one_step_when_the_scale_jitters_just_below_a_power_of_ten():
    # Arrange
    # A 6 x 10 x 10 mm box: Ixx = 600 * (10^2 + 10^2) / 12 = 10000.0 exactly, Iyy = Izz = 6800.
    # One ulp below, log10 still rounds to 4.0; 1e-15 below, the size of the integration's
    # last-bit jitter, it rounds below 4.0, where a step without the boundary shift drops 10x.
    scales = (10000.0, math.nextafter(10000.0, 0.0), 10000.0 * (1 - 1e-15))

    # Act
    steps = [fingerprint._tensor_step((scale, 6800.0, 6800.0, 0.0, 0.0, 0.0)) for scale in scales]

    # Assert
    assert steps == [10.0**-5] * len(scales)


def test_should_take_the_lower_step_when_the_scale_is_below_the_shifted_boundary():
    # Arrange
    # The shifted boundary sits at 10000 * (1 - 2.3e-9); 1e-8 below 10000 lies under it.
    tensor = (10000.0 * (1 - 1e-8), 6800.0, 6800.0, 0.0, 0.0, 0.0)

    # Act
    step = fingerprint._tensor_step(tensor)

    # Assert
    assert step == 10.0**-6


def test_should_fall_back_to_q_when_the_tensor_has_no_finite_non_zero_scale():
    # Arrange
    diagonals = (
        (0.0, 0.0, 0.0),
        (float("nan"), 1.0, 1.0),
        (1.0, float("nan"), 1.0),
        (1.0, 1.0, float("inf")),
    )

    # Act
    steps = [fingerprint._tensor_step((*diagonal, 0.0, 0.0, 0.0)) for diagonal in diagonals]

    # Assert
    assert steps == [fingerprint.Q] * len(diagonals)


def _rotation(axis, angle):
    """Rotation matrix about ``axis`` by ``angle`` radians (Rodrigues); columns are unit axes."""
    norm = math.sqrt(sum(component * component for component in axis))
    x, y, z = (component / norm for component in axis)
    cosine, sine = math.cos(angle), math.sin(angle)
    versine = 1 - cosine
    return [
        [cosine + x * x * versine, x * y * versine - z * sine, x * z * versine + y * sine],
        [y * x * versine + z * sine, cosine + y * y * versine, y * z * versine - x * sine],
        [z * x * versine - y * sine, z * y * versine + x * sine, cosine + z * z * versine],
    ]


def _tensor(moments, rotation):
    """``R·diag(moments)·Rᵀ`` in ``[Ixx, Iyy, Izz, Ixy, Ixz, Iyz]`` order."""
    full = [
        [sum(rotation[i][k] * moments[k] * rotation[j][k] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]
    return (full[0][0], full[1][1], full[2][2], full[0][1], full[0][2], full[1][2])


def _largest_error(eigenvalues, moments):
    return max(
        abs(measured - expected)
        for measured, expected in zip(eigenvalues, sorted(moments, reverse=True), strict=True)
    )


# Moments on the scale of the drawer's riser_zone (step 0.1), rotated so Ixy, Ixz and Iyz are all
# non-zero. The repeated pair is a cylinder or revolved part; the triple a sphere or tilted cube.
_TILT = _rotation((1.0, 2.0, 3.0), 0.7)
_EIGENVALUE_CASES = {
    "distinct": (1.7e8, 1.2e8, 9e7),
    "repeated pair": (1.7e8, 1.7e8, 9e7),
    "triple": (1.7e8, 1.7e8, 1.7e8),
}


def test_should_return_the_moments_descending_when_the_tensor_is_rotated():
    # Arrange
    tensors = {label: _tensor(moments, _TILT) for label, moments in _EIGENVALUE_CASES.items()}

    # Act
    errors = {
        label: _largest_error(fingerprint._eigenvalues(tensor), _EIGENVALUE_CASES[label])
        for label, tensor in tensors.items()
    }

    # Assert
    for label, tensor in tensors.items():
        assert all(tensor[3:]), label
        assert errors[label] <= 1e-5 * fingerprint._tensor_step(tensor), label


def test_should_stay_far_inside_the_step_when_the_tensor_carries_last_bit_noise():
    # Arrange
    draws = random.Random(11)
    noisy = {
        label: [
            tuple(
                component * (1 + draws.uniform(-2e-16, 2e-16))
                for component in _tensor(moments, _TILT)
            )
            for _ in range(500)
        ]
        for label, moments in _EIGENVALUE_CASES.items()
    }

    # Act
    worst = {
        label: max(
            _largest_error(fingerprint._eigenvalues(tensor), _EIGENVALUE_CASES[label])
            for tensor in tensors
        )
        for label, tensors in noisy.items()
    }

    # Assert
    for label, moments in _EIGENVALUE_CASES.items():
        step = fingerprint._tensor_step(_tensor(moments, _TILT))
        assert worst[label] <= 1e-5 * step, (label, worst[label])


def test_should_return_the_sorted_diagonal_when_the_tensor_is_diagonal():
    # Arrange
    tensor = (1.0, 3.0, 2.0, 0.0, 0.0, 0.0)

    # Act
    eigenvalues = fingerprint._eigenvalues(tensor)

    # Assert
    assert eigenvalues == (3.0, 2.0, 1.0)


def test_should_not_overflow_when_an_off_diagonal_component_exceeds_1e154():
    # Arrange
    # A float ``**`` raises OverflowError on 1e155 ** 2; ``*`` returns inf. The x/y block
    # [[1, 1e155], [1e155, 1]] has eigenvalues 1 +- 1e155, which round to +-1e155.
    tensor = (1.0, 1.0, 1.0, 1e155, 0.0, 0.0)

    # Act
    eigenvalues = fingerprint._eigenvalues(tensor)

    # Assert
    assert eigenvalues == (1e155, 1.0, -1e155)


def _vector(column):
    return SimpleNamespace(x=column[0], y=column[1], z=column[2])


def test_should_rebuild_the_tensor_and_volume_when_given_principal_properties():
    # Arrange
    moments = (5.0e4, 3.0e4, 1.0e4)
    volume = 1000.0
    rotation = _rotation((1.0, -1.0, 2.0), 0.4)
    props = {
        "Moments": moments,
        "FirstAxisOfInertia": _vector([row[0] for row in rotation]),
        "SecondAxisOfInertia": _vector([row[1] for row in rotation]),
        "ThirdAxisOfInertia": _vector([row[2] for row in rotation]),
        "RadiusOfGyration": tuple(math.sqrt(moment / volume) for moment in moments),
    }

    # Act
    measured_volume, tensor = fingerprint._principal_tensor(props)

    # Assert
    for measured, expected in zip(tensor, _tensor(moments, rotation), strict=True):
        assert abs(measured - expected) <= 1e-9 * moments[0]
    assert abs(measured_volume - volume) <= 1e-12 * volume


def test_should_give_zero_volume_when_every_radius_of_gyration_is_zero():
    # Arrange
    unit = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    props = {
        "Moments": (0.0, 0.0, 0.0),
        "FirstAxisOfInertia": _vector(unit[0]),
        "SecondAxisOfInertia": _vector(unit[1]),
        "ThirdAxisOfInertia": _vector(unit[2]),
        "RadiusOfGyration": (0.0, 0.0, 0.0),
    }

    # Act
    volume, tensor = fingerprint._principal_tensor(props)

    # Assert
    assert volume == 0.0
    assert tensor == (0.0,) * 6
