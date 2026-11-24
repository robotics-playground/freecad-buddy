"""FreeCAD-free tests for reading product names back from a written multi-object STEP file."""

from __future__ import annotations

from pathlib import Path

import pytest

from freecad_buddy.usecases import exports


def _write_step(path: Path, products: list[str]) -> None:
    """Write a file with the product lines OCCT writes, one per name, in the text form given."""
    lines = ["ISO-10303-21;", "DATA;"]
    lines += [f"#{index} = PRODUCT({name},{name},'',(#99));" for index, name in enumerate(products)]
    lines += ["ENDSEC;", "END-ISO-10303-21;"]
    path.write_text("\n".join(lines), encoding="utf-8")


def _entries(*names: str) -> list[dict]:
    return [{"name": f"O{index}", "step_name": name} for index, name in enumerate(names)]


def test_Should_pass_When_every_recorded_name_is_a_product_name(tmp_path):
    # Arrange
    path = tmp_path / "a.step"
    _write_step(path, ["'root'", "'Alpha'", "'Beta'"])

    # Act
    target = exports._object_names_check(str(path), _entries("Alpha", "Beta"))

    # Assert
    assert target["passed"] is True


def test_Should_fail_and_name_the_missing_product_When_a_recorded_name_is_absent(tmp_path):
    # Arrange
    path = tmp_path / "a.step"
    _write_step(path, ["'root'", "'Alpha'"])

    # Act
    target = exports._object_names_check(str(path), _entries("Alpha", "Beta"))

    # Assert
    assert target["passed"] is False
    assert "Beta" in target["detail"]["message"]


def test_Should_fail_When_two_objects_share_a_name_and_the_file_holds_one_product(tmp_path):
    # Arrange
    path = tmp_path / "a.step"
    _write_step(path, ["'root'", "'Same'"])

    # Act
    target = exports._object_names_check(str(path), _entries("Same", "Same"))

    # Assert
    assert target["passed"] is False


def test_Should_pass_When_two_objects_share_a_name_and_the_file_holds_two_products(tmp_path):
    # Arrange
    path = tmp_path / "a.step"
    _write_step(path, ["'root'", "'Same'", "'Same'"])

    # Act
    target = exports._object_names_check(str(path), _entries("Same", "Same"))

    # Assert
    assert target["passed"] is True


def test_Should_join_a_name_the_writer_wrapped_across_lines(tmp_path):
    # Arrange
    path = tmp_path / "a.step"
    long_name = "L" * 120
    wrapped = "'" + long_name[:71] + "\n" + long_name[71:] + "'"
    _write_step(path, ["'root'", wrapped])

    # Act
    target = exports._object_names_check(str(path), _entries(long_name))

    # Assert
    assert target["passed"] is True


@pytest.mark.parametrize(
    ("written", "label"),
    [
        ("'Al''pha'", "Al'pha"),
        ("'back\\\\slash'", "back\\slash"),
        ("'tab\\T\\here'", "tab\there"),
        ("'line\\N\\break'", "line\nbreak"),
        ("'\\\\N\\\\'", "\\N\\"),
    ],
)
def test_Should_decode_the_escape_the_writer_used_When_a_name_has_a_special_character(
    tmp_path, written, label
):
    # Arrange
    path = tmp_path / "a.step"
    _write_step(path, ["'root'", written])

    # Act
    target = exports._object_names_check(str(path), _entries(label))

    # Assert
    assert target["passed"] is True, target["measured"]
