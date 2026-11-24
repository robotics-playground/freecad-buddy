"""``verify_shape`` check schema: typed per-fn branches generated from the contract key tables."""

from __future__ import annotations

import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

from freecad_buddy.contracts import (
    ASSERTION_FNS,
    CHECK_COMMON_KEYS,
    CHECK_OPTIONAL_KEYS,
    CHECK_REQUIRED_KEYS,
    SHAPE_CHECK_FNS,
    VERIFY_SHAPE_FNS,
)
from freecad_buddy.hosts.tool_catalog import tool_specs
from freecad_buddy.usecases.assertions import validate_check
from freecad_buddy.usecases.documents import ValidationError
from freecad_buddy.usecases.verify import _validate_shape_check

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmarks import runner  # noqa: E402

_HOLE = {"hole": {"diameter": 5.0}}

VALID_EXPECT = {
    "is_valid_solid": True,
    "count_cylindrical_holes": 2,
    "hole_diameter": 5.0,
    "hole_position": [1.0, 2.0],
    "hole_spacing": [10.0, 15.0],
    "hole_through": True,
    "distance_between": 3.0,
    "angle_between": 90.0,
    "expect_bbox": [10.0, 20.0, 30.0],
    "expect_extent": 40.0,
    "expect_volume": 6000.0,
    "expect_solid_count": 1,
    "expect_valid": True,
    "expect_watertight": True,
}

VALID_KEY_VALUES = {
    "tol": {"abs": 0.1, "rel": None},
    "select": {"diameter": 5.0, "axis": [0, 0, 1]},
    "select_a": _HOLE,
    "select_b": _HOLE,
    "direction": [0, 0, 1],
    "pattern": "linear",
}


BENCHMARKS = Path(__file__).resolve().parents[2] / "benchmarks"


def _corpus_checks() -> list:
    checks = []
    # G0 and G3 grade through verify_shape; G2 cases use the harness's own extended vocabulary.
    for case in sorted([*BENCHMARKS.glob("g0/**/case.yaml"), *BENCHMARKS.glob("g3/**/case.yaml")]):
        if "heldout" in case.parts:
            continue
        assertions = (yaml.safe_load(case.read_text(encoding="utf-8")) or {}).get("assertions")
        if isinstance(assertions, dict):
            checks.extend(assertions.get("checks") or [])
    return checks


def _input_schema() -> dict:
    return next(spec for spec in tool_specs() if spec.name == "verify_shape").input_schema


def _schema_errors(check: dict) -> list:
    validator = jsonschema.Draft202012Validator(_input_schema())
    return list(validator.iter_errors({"doc": "fcb-doc:1", "checks": [check]}))


def _minimal_check(fn: str) -> dict:
    check = {"fn": fn, "expect": VALID_EXPECT[fn]}
    for key in CHECK_REQUIRED_KEYS.get(fn, frozenset()):
        check[key] = VALID_KEY_VALUES[key]
    return check


def test_Should_cover_every_vocabulary_fn_When_reading_the_contract_tables():
    # Arrange
    target = VERIFY_SHAPE_FNS

    # Act
    keyed = set(CHECK_OPTIONAL_KEYS)

    # Assert
    assert target == ASSERTION_FNS | SHAPE_CHECK_FNS
    assert keyed == set(target)
    assert set(VALID_EXPECT) == set(target)


@pytest.mark.parametrize("fn", sorted(VERIFY_SHAPE_FNS))
def test_Should_accept_the_minimal_check_When_the_fn_is_in_the_vocabulary(fn):
    # Arrange
    check = _minimal_check(fn)

    # Act
    errors = _schema_errors(check)

    # Assert
    assert errors == []


@pytest.mark.parametrize("fn", sorted(VERIFY_SHAPE_FNS))
def test_Should_reject_a_key_the_fn_does_not_take_When_the_check_carries_it(fn):
    # Arrange
    check = {**_minimal_check(fn), "bogus": 1}

    # Act
    errors = _schema_errors(check)

    # Assert
    assert errors


@pytest.mark.parametrize("fn", sorted(VERIFY_SHAPE_FNS))
def test_Should_reject_a_wrongly_typed_expect_When_the_fn_is_typed(fn):
    # Arrange
    check = {**_minimal_check(fn), "expect": {"not": "valid"}}

    # Act
    errors = _schema_errors(check)

    # Assert
    assert errors


@pytest.mark.parametrize(
    ("fn", "key"),
    sorted((fn, key) for fn, keys in CHECK_REQUIRED_KEYS.items() for key in keys),
)
def test_Should_reject_the_check_When_a_required_key_is_missing(fn, key):
    # Arrange
    check = _minimal_check(fn)
    del check[key]

    # Act
    errors = _schema_errors(check)

    # Assert
    assert errors


@pytest.mark.parametrize(
    "check",
    [
        {"type": "is_valid_solid"},
        {"fn": "expect_genus", "expect": 0},
        {"expect": True},
        {"fn": "is_valid_solid"},
    ],
)
def test_Should_reject_the_check_When_it_is_not_a_closed_vocabulary_check(check):
    # Arrange
    target = check

    # Act
    errors = _schema_errors(target)

    # Assert
    assert errors


@pytest.mark.parametrize(
    ("fn", "key"),
    sorted(
        (fn, key) for fn, keys in CHECK_OPTIONAL_KEYS.items() for key in keys if fn in ASSERTION_FNS
    ),
)
def test_Should_agree_with_the_use_case_When_a_table_key_is_given(fn, key):
    # Arrange
    check = _minimal_check(fn)
    check[key] = VALID_KEY_VALUES[key]
    if key in ("select_a", "select_b"):
        check["select_a"] = check["select_b"] = _HOLE
        check["expect"] = 10.0

    # Act
    schema_errors = _schema_errors(check)
    validate_check(check)

    # Assert
    assert schema_errors == []


@pytest.mark.parametrize("fn", sorted(ASSERTION_FNS))
def test_Should_agree_with_the_use_case_When_a_key_outside_the_table_is_given(fn):
    # Arrange
    check = {**_minimal_check(fn), "bogus": 1}

    # Act
    def act():
        validate_check(check)

    # Assert
    with pytest.raises(ValidationError):
        act()
    assert _schema_errors(check)
    assert "bogus" not in CHECK_COMMON_KEYS | CHECK_OPTIONAL_KEYS[fn]


@pytest.mark.parametrize(
    ("fn", "key"),
    sorted((fn, key) for fn, keys in CHECK_REQUIRED_KEYS.items() for key in keys),
)
def test_Should_agree_with_the_use_case_When_a_required_key_is_missing(fn, key):
    # Arrange
    check = _minimal_check(fn)
    del check[key]

    # Act
    def act():
        validate_check(check)

    # Assert
    with pytest.raises(ValidationError):
        act()
    assert _schema_errors(check)


def test_Should_keep_object_optional_When_reading_the_input_schema():
    # Arrange
    schema = _input_schema()

    # Act
    required = schema["required"]

    # Assert
    assert required == ["doc"]
    assert "oneOf" not in schema


@pytest.mark.parametrize(
    "check",
    [
        {
            "fn": "hole_spacing",
            "expect": 10.0,
            "select_a": {"face": {"normal": [0, 0, 1]}},
            "select_b": _HOLE,
        },
        {"fn": "hole_spacing", "expect": [10.0], "select_a": _HOLE, "select_b": _HOLE},
        {"fn": "hole_spacing", "expect": 10.0, "select_a": _HOLE},
        {"fn": "hole_spacing", "expect": 10.0, "select": {}, "select_a": _HOLE, "select_b": _HOLE},
        {"fn": "expect_extent", "expect": 1.0, "direction": [0, 0, 0]},
        {"fn": "count_cylindrical_holes", "expect": 1, "select": {"axis": [0, 0, 0]}},
        {"fn": "expect_bbox", "expect": [1, 2, 3], "tol": {"abs": -1}},
        {"fn": "expect_valid", "expect": 1},
        {"fn": "expect_solid_count", "expect": "2"},
    ],
)
def test_Should_reject_the_check_in_both_schema_and_use_case_When_a_value_is_invalid(check):
    # Arrange
    fn = check["fn"]

    # Act
    schema_errors = _schema_errors(check)

    # Assert
    assert schema_errors, fn
    if fn in ASSERTION_FNS:
        with pytest.raises(ValidationError):
            validate_check(check)


@pytest.mark.parametrize(
    "check",
    [
        {"fn": "hole_spacing", "expect": [10.0, 15.0]},
        {"fn": "hole_spacing", "expect": 10.0, "select": _HOLE["hole"]},
        {"fn": "hole_spacing", "expect": 10.0, "select_a": _HOLE, "select_b": _HOLE},
        {"fn": "expect_volume", "expect": 1.0, "tol": None},
        {"fn": "count_cylindrical_holes", "expect": 0},
    ],
)
def test_Should_accept_the_check_in_both_schema_and_use_case_When_it_is_valid(check):
    # Arrange
    target = check

    # Act
    schema_errors = _schema_errors(target)
    validate_check(target)

    # Assert
    assert schema_errors == []


def test_Should_accept_every_stored_benchmark_check_When_validated_against_the_schema():
    # Arrange
    checks = _corpus_checks()

    # Act
    rejected = [check for check in checks if _schema_errors(check)]

    # Assert
    assert len(checks) >= 20
    assert rejected == []


@pytest.mark.parametrize("name", ["verify_shape", "assertions", "spec_assertions"])
def test_Should_change_the_validator_hash_When_the_check_key_tables_are_edited(
    name, tmp_path, monkeypatch
):
    # Arrange
    tables = Path(__file__).resolve().parents[2] / "src/freecad_buddy/contracts/assertions.py"
    edited = tmp_path / "assertions.py"
    edited.write_bytes(tables.read_bytes() + b"\n# edit\n")
    swapped = tuple(edited if path == tables else path for path in runner._VALIDATOR_SOURCES[name])
    before = runner._validator_src_hasher(name)
    monkeypatch.setitem(runner._VALIDATOR_SOURCES, name, swapped)

    # Act
    after = runner._validator_src_hasher(name)

    # Assert
    assert before
    assert after != before


@pytest.mark.parametrize(
    "check",
    [
        {"fn": "expect_solid_count", "expect": 1.0},
        {"fn": "count_cylindrical_holes", "expect": 2.0},
    ],
)
def test_Should_accept_an_integral_float_When_the_fn_takes_an_integer(check):
    # Arrange
    target = check

    # Act
    schema_errors = _schema_errors(target)
    if target["fn"] in SHAPE_CHECK_FNS:
        _validate_shape_check(target)
    else:
        validate_check(target)

    # Assert
    assert schema_errors == []


@pytest.mark.parametrize("expect", [1.5, True, "1"])
def test_Should_refuse_a_non_integral_expect_When_the_fn_counts_solids(expect):
    # Arrange
    check = {"fn": "expect_solid_count", "expect": expect}

    # Act
    def act():
        _validate_shape_check(check)

    # Assert
    with pytest.raises(ValidationError):
        act()
    assert _schema_errors(check)


def test_Should_mark_required_keys_and_name_the_index_selector_ban_When_reading_the_description():
    # Arrange
    items = _input_schema()["properties"]["checks"]["items"]

    # Act
    description = items["description"]

    # Assert
    assert "expect_extent {expect*, direction*, tol}" in description
    assert "hole_spacing {expect*, pattern, select, tol}" in description
    assert "hole_spacing {expect*, pattern, select_a*, select_b*, tol}" in description
    assert "Face3" in description
    assert "AD-13" in description
