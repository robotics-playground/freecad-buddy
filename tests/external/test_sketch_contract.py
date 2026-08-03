"""External (pytest) tests for the sketch wire contract, catalog registration, and ring purity.

Everything here is stdlib-only and FreeCAD-free: the contract types, the generated schema, the
tool specs' hand-authored input schemas, and the guarantee that no ``sketch_*`` name entered the
read-only assistant profile.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from freecad_buddy import contracts
from freecad_buddy.contracts import sketch as sketch_contract
from freecad_buddy.hosts.tool_catalog import READ_ONLY_PROFILE, tool_specs

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPO_ROOT / "src" / "freecad_buddy" / "contracts" / "jsonschema" / "sketch-state.schema.json"
)

SKETCH_TOOLS = {
    "sketch_create",
    "sketch_add_geometry",
    "sketch_remove_geometry",
    "sketch_add_constraint",
    "sketch_remove_constraint",
    "sketch_set_datum",
    "sketch_toggle_construction",
    "sketch_add_external_geometry",
}


def _specs_by_name():
    return {spec.name: spec for spec in tool_specs()}


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# contract types
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name",
    [
        "SketchState",
        "ConstraintRef",
        "Quantity",
        "GeometrySpec",
        "ConstraintSpec",
        "GeometryKind",
        "ConstraintType",
        "PointPos",
    ],
)
def test_every_sketch_type_is_exported_from_the_contracts_package(name):
    assert name in contracts.__all__
    assert getattr(contracts, name) is getattr(sketch_contract, name)


def test_point_pos_matches_the_verified_sketcher_enum():
    # GeoEnum.h: none=0, start=1, end=2, mid=3.
    assert set(sketch_contract.PointPos.__args__) == {0, 1, 2, 3}


def test_constraint_type_matches_the_catalog_vocabulary():
    catalog = set(
        _specs_by_name()["sketch_add_constraint"].input_schema["properties"]["constraints"][
            "items"
        ]["properties"]["type"]["enum"]
    )
    assert set(sketch_contract.ConstraintType.__args__) == catalog


def test_geometry_kind_matches_the_catalog_vocabulary():
    catalog = set(
        _specs_by_name()["sketch_add_geometry"].input_schema["properties"]["geometry"]["items"][
            "properties"
        ]["kind"]["enum"]
    )
    assert set(sketch_contract.GeometryKind.__args__) == catalog


# --------------------------------------------------------------------------- #
# generated schema
# --------------------------------------------------------------------------- #


def test_sketch_state_schema_is_generated_and_identified():
    schema = _schema()
    assert schema["$id"] == "fcb.sketch-state/1"
    assert schema["title"] == "SketchState"


def test_sketch_state_schema_requires_the_load_bearing_fields():
    # The grading fields are absent on the unreadable path, so only the identity of the block is
    # unconditionally required.
    assert set(_schema()["required"]) == {"schema", "sketch", "readable"}


def test_a_full_sketch_state_validates_and_a_bare_object_does_not():
    validator = jsonschema.Draft202012Validator(_schema())
    good = {
        "schema": "fcb.sketch-state/1",
        "sketch": "Rect",
        "readable": True,
        "dof": 0,
        "fully_constrained": True,
        "geometry_count": 4,
        "constraint_count": 11,
        "conflicting": [],
        "redundant": [{"id": 12, "name": "Extra", "type": "Horizontal"}],
        "partially_redundant": [],
        "malformed": [],
    }
    assert validator.is_valid(good)
    assert not validator.is_valid({})
    assert not validator.is_valid({**good, "schema": "fcb.sketch-state/2"})
    assert not validator.is_valid({**good, "dof": "zero"})


def test_an_unreadable_sketch_state_validates_against_its_own_schema():
    validator = jsonschema.Draft202012Validator(_schema())
    unreadable = {"schema": "fcb.sketch-state/1", "sketch": "Gone", "readable": False}
    assert validator.is_valid(unreadable)
    assert not validator.is_valid({"schema": "fcb.sketch-state/1", "sketch": "Gone"})


def test_a_subject_without_grading_fields_reports_unreadable(monkeypatch):
    # `readable: True` promises the grading fields are present. A verify envelope that carried no
    # subject used to yield `readable: True` with nothing to grade, so a consumer that checked
    # `readable` before reading `dof` got a KeyError from a block that passed its own schema.
    from freecad_buddy.usecases import sketches

    monkeypatch.setattr(
        sketches.verify,
        "verify_sketch",
        lambda registry, doc=None, sketch=None: {
            "schema": "fcb.result-envelope/1",
            "status": "SPEC_FAILED",
            "structured_content": {},
        },
    )

    state = sketches._sketch_state(object(), "doc", "Rect")

    assert state["readable"] is False
    assert "dof" not in state
    assert jsonschema.Draft202012Validator(_schema()).is_valid(state)


def test_ids_are_suppressed_on_every_non_committed_outcome():
    # An unproven rollback reports `rolled_back: False` with the snapshot kept
    # (transaction.py:501-517), so gating on that flag alone reported mid-transaction ids for
    # geometry that may not exist. Only a committed mutation leaves them addressable.
    from freecad_buddy.usecases import sketches

    def envelope(status, rolled_back):
        return {
            "schema": "fcb.result-envelope/1",
            "status": status,
            "structured_content": {"mutation": {"rolled_back": rolled_back}},
        }

    assert sketches._ids_survived(envelope("OK", False)) is True
    assert sketches._ids_survived(envelope("SPEC_FAILED", True)) is False
    assert sketches._ids_survived(envelope("SPEC_FAILED", False)) is False
    assert sketches._ids_survived(envelope("RECOMPUTE_ERROR", False)) is False


def test_constraint_refs_require_a_one_based_id():
    validator = jsonschema.Draft202012Validator(_schema())
    base = {
        "schema": "fcb.sketch-state/1",
        "sketch": "S",
        "readable": True,
        "dof": 0,
        "fully_constrained": True,
        "geometry_count": 0,
        "constraint_count": 0,
    }
    assert validator.is_valid({**base, "conflicting": [{"id": 1}]})
    assert not validator.is_valid({**base, "conflicting": [{"name": "unnamed"}]})


# --------------------------------------------------------------------------- #
# catalog registration
# --------------------------------------------------------------------------- #


def test_all_eight_sketch_tools_are_registered_as_mutating():
    specs = _specs_by_name()
    assert SKETCH_TOOLS <= set(specs)
    for name in SKETCH_TOOLS:
        assert specs[name].mutating is True, name
        assert specs[name].audit_event == "mutation", name


def test_every_sketch_tool_requires_a_doc_handle_and_rejects_unknown_keys():
    specs = _specs_by_name()
    for name in SKETCH_TOOLS:
        schema = specs[name].input_schema
        assert schema["additionalProperties"] is False, name
        assert "doc" in schema["required"], name
        assert schema["properties"]["doc"]["type"] == "string", name


def test_every_sketch_tool_accepts_an_optional_unenforced_confirm():
    specs = _specs_by_name()
    for name in SKETCH_TOOLS:
        schema = specs[name].input_schema
        assert "confirm" in schema["properties"], name
        assert "confirm" not in schema["required"], name


def test_every_sketch_tool_carries_a_description():
    specs = _specs_by_name()
    for name in SKETCH_TOOLS:
        assert specs[name].description.strip(), name


def test_a_selector_input_uses_the_contracts_kind_discriminator():
    # contracts/document.py spells the discriminator `kind`; the mcp-tools `by` variant is not
    # the binding shape (AD-17: contracts own the wire types).
    specs = _specs_by_name()
    for name, field in (("sketch_create", "face"), ("sketch_add_external_geometry", "edge")):
        selector = specs[name].input_schema["properties"][field]
        assert "kind" in selector["properties"], name
        assert "by" not in selector["properties"], name
        assert selector["required"] == ["kind", "object"], name


def test_dimensional_inputs_are_explicit_unit_quantities():
    specs = _specs_by_name()
    value = specs["sketch_set_datum"].input_schema["properties"]["value"]
    assert set(value["required"]) == {"value", "unit"}
    constraint_value = specs["sketch_add_constraint"].input_schema["properties"]["constraints"][
        "items"
    ]["properties"]["value"]
    assert set(constraint_value["required"]) == {"value", "unit"}


def test_the_point_pos_enum_in_the_catalog_matches_the_verified_values():
    items = _specs_by_name()["sketch_add_constraint"].input_schema["properties"]["constraints"][
        "items"
    ]
    for field in ("first_pos", "second_pos", "third_pos"):
        assert items["properties"][field]["enum"] == [0, 1, 2, 3], field


def test_sketch_add_geometry_accepts_constraints_in_the_same_call():
    # Geometry alone always rolls back (DoF > 0), so a shape reaches FullyConstrained only when
    # its constraints travel in the same transaction.
    schema = _specs_by_name()["sketch_add_geometry"].input_schema
    assert "constraints" in schema["properties"]
    assert "constraints" not in schema["required"]


# --------------------------------------------------------------------------- #
# read-only profile guarantee (G1.6)
# --------------------------------------------------------------------------- #


def test_no_sketch_tool_entered_the_read_only_profile():
    assert not (SKETCH_TOOLS & READ_ONLY_PROFILE)
    assert not any(name.startswith("sketch_") for name in READ_ONLY_PROFILE)


def test_the_read_only_profile_still_names_zero_mutating_tools():
    specs = _specs_by_name()
    geometry_mutators = {
        name for name, spec in specs.items() if spec.mutating and name.startswith("sketch_")
    }
    assert geometry_mutators == SKETCH_TOOLS
    assert not (geometry_mutators & READ_ONLY_PROFILE)


# --------------------------------------------------------------------------- #
# ring purity
# --------------------------------------------------------------------------- #


def test_the_sketch_contract_module_imports_no_freecad_and_no_third_party():
    source = (
        REPO_ROOT / "src" / "freecad_buddy" / "contracts" / "sketch.py"
    ).read_text(encoding="utf-8")
    for banned in ("import FreeCAD", "import Part", "import Sketcher", "import pydantic"):
        assert banned not in source


def test_the_sketch_use_case_imports_freecad_only_inside_functions():
    source = (
        REPO_ROOT / "src" / "freecad_buddy" / "usecases" / "sketches.py"
    ).read_text(encoding="utf-8")
    for line in source.splitlines():
        if line.startswith(("import ", "from ")):
            assert "FreeCAD" not in line
            assert not line.startswith(("import Part", "import Sketcher"))


def test_the_sketch_use_case_never_opens_a_transaction_itself():
    source = (
        REPO_ROOT / "src" / "freecad_buddy" / "usecases" / "sketches.py"
    ).read_text(encoding="utf-8")
    for banned in ("openTransaction", "commitTransaction", "abortTransaction"):
        assert banned not in source
    assert "run_mutation" in source


def test_every_sketch_tool_rebinds_the_document_through_the_one_bracket_helper():
    source = (
        REPO_ROOT / "src" / "freecad_buddy" / "usecases" / "sketches.py"
    ).read_text(encoding="utf-8")
    # One helper owns the call contract, so `rebind` is called exactly once in the module and
    # every tool reaches it through `_sketch_mutation`.
    assert source.count("registry.rebind(") == 1
    assert source.count("run_mutation(") == 1
    for name in SKETCH_TOOLS:
        assert f"def {name}(" in source


def test_sketch_create_takes_an_optional_body():
    """A profile sketch can name the Body that will consume it; omitting it is still valid."""
    schema = {spec.name: spec for spec in tool_specs()}["sketch_create"].input_schema

    assert schema["properties"]["body"]["type"] == "string"
    assert "body" not in schema["required"]


def test_a_length_field_accepts_only_millimetres():
    schema = _specs_by_name()["sketch_add_geometry"].input_schema
    radius = schema["properties"]["geometry"]["items"]["properties"]["radius"]

    assert radius["properties"]["unit"]["enum"] == ["mm"]


def test_an_angle_field_accepts_only_degrees():
    schema = _specs_by_name()["sketch_add_geometry"].input_schema
    start = schema["properties"]["geometry"]["items"]["properties"]["start_angle"]

    assert start["properties"]["unit"]["enum"] == ["deg"]


def test_a_constraint_value_accepts_either_unit():
    """The dimension depends on the constraint's type, resolved at call time.

    ``_ANGLE_TYPES`` takes degrees and ``_LENGTH_TYPES`` millimetres, so narrowing this field to
    one unit would refuse a call the use case accepts.
    """
    schema = _specs_by_name()["sketch_set_datum"].input_schema

    assert sorted(schema["properties"]["value"]["properties"]["unit"]["enum"]) == ["deg", "mm"]


def test_no_quantity_field_leaves_its_unit_unconstrained():
    """Walks every tool spec rather than a hand-listed set, so a new field cannot skip the rule."""
    offenders = []

    def walk(node, path):
        if not isinstance(node, dict):
            return
        properties = node.get("properties")
        if isinstance(properties, dict):
            unit = properties.get("unit")
            if isinstance(unit, dict) and "enum" not in unit:
                offenders.append(path)
            for key, child in properties.items():
                walk(child, f"{path}.{key}")
        items = node.get("items")
        if isinstance(items, dict):
            walk(items, f"{path}[]")

    for spec in tool_specs():
        walk(spec.input_schema, spec.name)

    assert offenders == []
