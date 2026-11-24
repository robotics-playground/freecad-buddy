import pytest

from freecad_buddy.contracts.envelope import summary_text


def test_summary_text_flattens_scalars_inline():
    out = summary_text({"status": "OK", "volume": 8642.85, "solid": True})
    assert "status: OK" in out
    assert "volume: 8642.85" in out
    assert "solid: True" in out


def test_summary_text_summarizes_containers_not_dumps_them():
    out = summary_text({"tree": [1, 2, 3], "banner": {"a": 1, "b": 2}})
    assert "tree: [3 items]" in out
    assert "banner: {2 fields}" in out
    assert "[1, 2, 3]" not in out  # NOT a raw dump


def test_Should_render_string_inline_When_it_has_exactly_80_characters():
    # Arrange
    value = "a" * 80

    # Act
    result = summary_text({"name": value})

    # Assert
    assert result == f"name: {value}"


def test_Should_render_char_count_When_string_has_81_characters():
    # Arrange
    value = "a" * 81

    # Act
    result = summary_text({"name": value})

    # Assert
    assert result == "name: <81 chars>"


def test_Should_render_char_count_When_short_string_has_a_newline():
    # Arrange
    value = "a\nb"

    # Act
    result = summary_text({"stdout": value})

    # Assert
    assert result == "stdout: <3 chars>"


@pytest.mark.parametrize(
    "line_break",
    ["\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"],
)
def test_Should_render_char_count_When_short_string_has_a_line_break(line_break):
    # Arrange
    value = f"50%{line_break}100%"

    # Act
    result = summary_text({"stdout": value})

    # Assert
    assert result == "stdout: <8 chars>"


def test_Should_count_characters_not_bytes_When_string_is_non_ascii():
    # Arrange
    inline_value = "é" * 80
    elided_value = "é" * 81

    # Act
    inline_result = summary_text({"name": inline_value})
    elided_result = summary_text({"name": elided_value})

    # Assert
    assert inline_result == f"name: {inline_value}"
    assert elided_result == "name: <81 chars>"


def test_Should_hold_long_strings_once_When_content_is_script_exec_shaped():
    # Arrange
    value_repr = "Part.Solid " * 20
    stdout = "line one\nline two\n"
    content = {
        "doc": "Unnamed",
        "stdout": stdout,
        "value_repr": value_repr,
        "fingerprint_after": None,
    }

    # Act
    result = summary_text(content)

    # Assert
    assert result == (
        "doc: Unnamed\n"
        "fingerprint_after: None\n"
        f"stdout: <{len(stdout)} chars>\n"
        f"value_repr: <{len(value_repr)} chars>"
    )
    assert "Part.Solid" not in result
    assert "line one" not in result


def test_Should_render_non_string_scalars_inline_When_they_are_numbers_booleans_or_none():
    # Arrange
    content = {"count": 7, "ratio": 0.25, "solid": False, "missing": None}

    # Act
    result = summary_text(content)

    # Assert
    assert result == "count: 7\nmissing: None\nratio: 0.25\nsolid: False"


def test_Should_render_shape_signal_When_a_container_holds_long_strings():
    # Arrange
    content = {"rows": ["x" * 200], "meta": {"note": "y" * 200}}

    # Act
    result = summary_text(content)

    # Assert
    assert result == "meta: {1 fields}\nrows: [1 items]"
