"""External (pytest) tests for ``feature_set_expression``: its catalog entry and input schema.

FreeCAD-free: the tool spec's input schema and the preview table.
"""

from __future__ import annotations

import jsonschema
import pytest

from freecad_buddy.hosts.tool_catalog import preview_op_table, tool_specs
from freecad_buddy.usecases.features import _CELL_RANGE, _EXPRESSION_PATH


def _spec():
    return {spec.name: spec for spec in tool_specs()}["feature_set_expression"]


def _item(**extra):
    return {"object": "Box", "path": "Length", "expression": "Params.width", **extra}


def test_Should_require_doc_and_expressions_When_reading_the_schema():
    # Arrange
    spec = _spec()

    # Act
    schema = spec.input_schema

    # Assert
    assert spec.mutating is True
    assert schema["required"] == ["doc", "expressions"]
    item = schema["properties"]["expressions"]["items"]
    assert item["required"] == ["object", "path", "expression"]
    assert item["additionalProperties"] is False
    assert item["properties"]["expression"]["type"] == ["string", "null"]


def test_Should_accept_a_bind_and_a_clear_and_refuse_a_bad_request_When_validating_the_schema():
    # Arrange
    schema = _spec().input_schema
    bind = {"doc": "d", "expressions": [_item()]}
    clear = {"doc": "d", "expressions": [_item(expression=None)]}
    empty = {"doc": "d", "expressions": []}
    too_many = {"doc": "d", "expressions": [_item()] * 101}
    unknown_key = {"doc": "d", "expressions": [_item(extra=1)]}
    missing_expression = {"doc": "d", "expressions": [{"object": "Box", "path": "Length"}]}

    # Act
    jsonschema.validate(bind, schema)
    jsonschema.validate(clear, schema)

    # Assert
    for bad in (empty, too_many, unknown_key, missing_expression):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)


@pytest.mark.parametrize(
    "path",
    [
        "Length",
        ".Constraints.width",
        ".AttachmentOffset.Base.z",
        "Placement.Base.y",
        "Constraints[0]",
    ],
)
def test_Should_match_the_path_pattern_When_the_path_is_a_property_path(path):
    # Act
    matched = _EXPRESSION_PATH.fullmatch(path)

    # Assert
    assert matched is not None


@pytest.mark.parametrize("path", ["", " Length", "Length.", "Length..x", "1Length", "a b", "a[x]"])
def test_Should_not_match_the_path_pattern_When_the_path_is_malformed(path):
    # Act
    matched = _EXPRESSION_PATH.fullmatch(path)

    # Assert
    assert matched is None


def test_Should_reach_the_expression_tool_through_the_preview_table_When_building_the_op_table():
    # Act
    table = preview_op_table()

    # Assert
    assert "feature_set_expression" in table


@pytest.mark.parametrize(
    "text",
    [
        "sum(A1:B2)",
        "sum(Sheet.A1:Sheet.B2)",
        "sum($A$1:$B$2)",
        "sum( C1 : ZZ16384 )",
        "sum(<<My Sheet>>.A1:<<My Sheet>>.B2)",
        "sum(Doc#Sheet.A1:Doc#Sheet.B2)",
    ],
)
def test_Should_match_the_range_pattern_When_the_text_holds_a_cell_range(text):
    # Act
    matched = _CELL_RANGE.search(text)

    # Assert
    assert matched is not None


@pytest.mark.parametrize("text", ["Sheet.A1 * 2 mm", "Params.width * 2", "1 ? 2 : 3", "A1 + B2"])
def test_Should_not_match_the_range_pattern_When_the_text_has_single_cells_only(text):
    # Act
    matched = _CELL_RANGE.search(text)

    # Assert
    assert matched is None
