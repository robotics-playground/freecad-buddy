"""External (pytest) tests for the VarSet parameter tools: catalog entries and the reserved names.

FreeCAD-free: the tool specs' input schemas, the reserved-name list against FreeCAD's expression
lexer source, and the skill text that names unit symbols.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.hosts.tool_catalog import READ_ONLY_PROFILE, preview_op_table, tool_specs
from freecad_buddy.usecases.documents import CodedValidationError, ValidationError
from freecad_buddy.usecases.features import _EXPRESSION_RESERVED_NAMES
from freecad_buddy.usecases.parameter_types import PARAMETER_PROPERTY_TYPES

REPO_ROOT = Path(__file__).resolve().parents[2]
LEXER_SOURCE = REPO_ROOT / "docs" / "references" / "FreeCAD" / "src" / "App" / "Expression.l"
PARAMETERS_SKILL = REPO_ROOT / "skills" / "parametric-patterns" / "SKILL.md"

_LEXER_TOKEN = re.compile(r'^"([^"]+)"\s+COUNTCHARS;[^\n]*return (?:UNIT|CONSTANT);', re.MULTILINE)


_ENVELOPE_SCHEMA = json.loads(
    (
        REPO_ROOT
        / "src"
        / "freecad_buddy"
        / "contracts"
        / "jsonschema"
        / "result-envelope.schema.json"
    ).read_text(encoding="utf-8")
)


def _spec(name: str):
    return {spec.name: spec for spec in tool_specs()}[name]


def test_Should_list_every_ascii_unit_and_constant_of_the_lexer_When_checking_reserved_names():
    # Arrange
    if not LEXER_SOURCE.exists():
        pytest.skip("docs/references/FreeCAD is not checked out")
    source = LEXER_SOURCE.read_text(encoding="utf-8", errors="replace")

    # Act
    lexer_names = set(_LEXER_TOKEN.findall(source))
    ascii_names = {name for name in lexer_names if re.fullmatch(r"[A-Za-z]+", name)}

    # Assert
    assert len(ascii_names) > 100
    assert ascii_names - _EXPRESSION_RESERVED_NAMES == set()


def test_Should_name_only_lexer_symbols_When_checking_the_reserved_name_list_for_extras():
    # Arrange
    if not LEXER_SOURCE.exists():
        pytest.skip("docs/references/FreeCAD is not checked out")
    source = LEXER_SOURCE.read_text(encoding="utf-8", errors="replace")

    # Act
    lexer_names = set(_LEXER_TOKEN.findall(source))

    # Assert
    assert _EXPRESSION_RESERVED_NAMES - lexer_names == set()


def test_Should_cover_every_symbol_the_skill_names_When_the_skill_lists_unit_symbols():
    # Arrange
    text = PARAMETERS_SKILL.read_text(encoding="utf-8")
    bullet = re.search(r"Never name a variable after a \*\*unit symbol\*\* \((.*?)\)", text, re.S)

    # Act
    assert bullet is not None
    symbols = set(re.findall(r"`([^`]+)`", bullet.group(1)))

    # Assert
    assert {"W", "T", "A", "V", "N", "C", "K"} <= symbols
    assert symbols - _EXPRESSION_RESERVED_NAMES == set()


def test_Should_require_doc_varset_and_parameters_When_reading_the_define_schema():
    # Arrange
    spec = _spec("feature_parameters_define")

    # Act
    schema = spec.input_schema

    # Assert
    assert spec.mutating is True
    assert schema["required"] == ["doc", "varset", "parameters"]
    item = schema["properties"]["parameters"]["items"]
    assert item["required"] == ["name", "type", "value"]
    assert set(item["properties"]["type"]["enum"]) == set(PARAMETER_PROPERTY_TYPES)
    assert item["properties"]["name"]["pattern"] == "^[A-Za-z_][A-Za-z0-9_]*$"


def test_Should_accept_a_contract_request_and_refuse_a_bad_one_When_validating_the_schema():
    # Arrange
    schema = _spec("feature_parameters_define").input_schema
    good = {
        "doc": "d",
        "varset": "Params",
        "parameters": [{"name": "w", "type": "length", "value": {"value": 1, "unit": "mm"}}],
    }
    empty = {**good, "parameters": []}
    unknown_type = {**good, "parameters": [{"name": "w", "type": "vector", "value": 1}]}

    # Act
    jsonschema.validate(good, schema)

    # Assert
    for bad in (empty, unknown_type):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)


def test_Should_reach_the_define_tool_through_the_preview_table_When_building_the_op_table():
    # Act
    table = preview_op_table()

    # Assert
    assert "feature_parameters_define" in table


def test_Should_keep_the_query_read_only_and_the_define_out_of_the_profile_When_listing_tools():
    # Assert
    assert _spec("query_parameters").mutating is False
    assert "query_parameters" in READ_ONLY_PROFILE
    assert "feature_parameters_define" not in READ_ONLY_PROFILE


class _CodeMethod(Exception):
    def code(self):
        return "not a string"


class _IntCode(ValidationError):
    code = 5


def _dispatch_raising(error):
    def handler(**_params):
        raise error

    methods = MethodRegistry()
    methods.register(RpcMethod(name="probe", handler=handler, mutating=False))
    return methods.dispatch("probe", {})


@pytest.mark.parametrize(
    "error",
    [
        OSError(5, "access denied"),
        _CodeMethod("boom"),
        _IntCode("bad"),
        CodedValidationError("", "x"),
    ],
    ids=["os-error-int-code", "code-method", "validation-error-int-code", "empty-code"],
)
def test_Should_keep_the_status_as_the_code_When_the_error_is_not_a_project_refusal(error):
    # Act
    envelope = _dispatch_raising(error)

    # Assert
    code = envelope["detail"]["code"]
    assert code == envelope["status"]
    json.dumps(envelope)
    jsonschema.validate(envelope, _ENVELOPE_SCHEMA)


def test_Should_put_the_refusal_code_in_the_detail_When_a_coded_validation_error_is_raised():
    # Act
    envelope = _dispatch_raising(CodedValidationError("parameters.invalid_string", "bad text"))

    # Assert
    assert envelope["status"] == "INVALID_INPUT"
    assert envelope["detail"]["code"] == "parameters.invalid_string"
