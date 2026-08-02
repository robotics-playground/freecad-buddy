"""External (pytest) tests for the feature wire contract, catalog registration, and ring purity.

Everything here is stdlib-only and FreeCAD-free: the contract types, the generated schema, the
tool specs' hand-authored input schemas, and the guarantee that no ``feature_*`` name entered the
read-only assistant profile.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import jsonschema
import pytest

from freecad_buddy import contracts
from freecad_buddy.contracts import feature as feature_contract
from freecad_buddy.hosts.tool_catalog import READ_ONLY_PROFILE, tool_specs

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPO_ROOT / "src" / "freecad_buddy" / "contracts" / "jsonschema" / "feature-state.schema.json"
)
FEATURES_SOURCE = REPO_ROOT / "src" / "freecad_buddy" / "usecases" / "features.py"

FEATURE_TOOLS = {
    "feature_pad",
    "feature_pocket",
    "feature_revolve",
    "feature_hole",
    "feature_fillet",
    "feature_chamfer",
    "feature_pattern",
    "feature_mirror",
    "feature_datum",
    "feature_set_parameters",
    "feature_body_create",
}


def _specs_by_name():
    return {spec.name: spec for spec in tool_specs()}


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _full_state() -> dict:
    return {
        "schema": "fcb.feature-state/1",
        "feature": "TopPad",
        "readable": True,
        "body": "Body",
        "is_tip": True,
        "shape_summary": {
            "volume": 640.0,
            "area": 496.0,
            "bbox": [8.0, 16.0, 5.0],
            "solid_count": 1,
            "face_count": 6,
            "edge_count": 12,
            "vertex_count": 8,
            "is_valid": True,
        },
    }


# --------------------------------------------------------------------------- #
# contract types
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name",
    ["FeatureState", "ShapeSummary", "PatternKind", "DatumKind", "ExtrudeType"],
)
def test_every_feature_type_is_exported_from_the_contracts_package(name):
    assert name in contracts.__all__
    assert getattr(contracts, name) is getattr(feature_contract, name)


def test_pattern_kind_matches_the_catalog_vocabulary():
    catalog = set(_specs_by_name()["feature_pattern"].input_schema["properties"]["kind"]["enum"])
    assert set(feature_contract.PatternKind.__args__) == catalog


def test_datum_kind_matches_the_catalog_vocabulary():
    catalog = set(_specs_by_name()["feature_datum"].input_schema["properties"]["kind"]["enum"])
    assert set(feature_contract.DatumKind.__args__) == catalog


def test_the_contracts_ring_imports_nothing_outside_the_standard_library():
    tree = ast.parse((REPO_ROOT / "src" / "freecad_buddy" / "contracts" / "feature.py").read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"__future__", "typing"}


# --------------------------------------------------------------------------- #
# generated schema
# --------------------------------------------------------------------------- #


def test_feature_state_schema_is_generated_and_identified():
    schema = _schema()
    assert schema["$id"] == "fcb.feature-state/1"
    assert schema["title"] == "FeatureState"


def test_feature_state_schema_requires_only_the_identity_of_the_block():
    # The grading fields are absent on the unreadable path, so a feature a rollback removed can
    # still report a block that validates.
    assert set(_schema()["required"]) == {"schema", "feature", "readable"}


def test_a_full_feature_state_validates_and_a_bare_object_does_not():
    validator = jsonschema.Draft202012Validator(_schema())
    good = _full_state()
    assert validator.is_valid(good)
    assert not validator.is_valid({})
    assert not validator.is_valid({**good, "schema": "fcb.feature-state/2"})
    assert not validator.is_valid({**good, "is_tip": "yes"})


def test_an_unreadable_feature_state_validates_against_its_own_schema():
    validator = jsonschema.Draft202012Validator(_schema())
    unreadable = {"schema": "fcb.feature-state/1", "feature": "Gone", "readable": False}
    assert validator.is_valid(unreadable)
    assert not validator.is_valid({"schema": "fcb.feature-state/1", "feature": "Gone"})


def test_a_shape_summary_missing_a_measurement_is_rejected():
    validator = jsonschema.Draft202012Validator(_schema())
    state = _full_state()
    for field in list(state["shape_summary"]):
        partial = dict(state)
        partial["shape_summary"] = {
            k: v for k, v in state["shape_summary"].items() if k != field
        }
        assert not validator.is_valid(partial), field


def test_the_shape_summary_required_set_is_the_whole_measurement_vocabulary():
    summary = _schema()["$defs"]["ShapeSummary"]
    assert set(summary["required"]) == set(summary["properties"])


def test_an_ungradeable_feature_reports_unreadable_rather_than_a_null_summary(monkeypatch):
    # `readable: True` promises the summary is present. A verify envelope the feature path could
    # not grade must yield `readable: False`, not a block whose `shape_summary` a consumer
    # dereferences into a KeyError.
    from freecad_buddy.usecases import features

    monkeypatch.setattr(
        features.verify,
        "verify_shape",
        lambda registry, doc=None, object=None: {  # noqa: A002 - the verify_shape parameter name
            "schema": "fcb.result-envelope/1",
            "status": "SPEC_FAILED",
            "structured_content": {},
        },
    )

    state = features._feature_state(object(), "doc", "Gone")

    assert state["readable"] is False
    assert "shape_summary" not in state
    assert jsonschema.Draft202012Validator(_schema()).is_valid(state)


def test_the_capability_banner_carries_the_partdesign_probe():
    schema = json.loads(
        (
            REPO_ROOT
            / "src"
            / "freecad_buddy"
            / "contracts"
            / "jsonschema"
            / "capability-banner.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert "partdesign_available" in schema["required"]
    assert schema["properties"]["partdesign_available"] == {"type": "boolean"}


# --------------------------------------------------------------------------- #
# catalog registration
# --------------------------------------------------------------------------- #


def test_every_feature_tool_is_registered_as_mutating():
    specs = _specs_by_name()
    assert FEATURE_TOOLS <= set(specs)
    for name in FEATURE_TOOLS:
        assert specs[name].mutating is True, name
        assert specs[name].audit_event == "mutation", name


def test_the_catalog_registers_exactly_the_expected_feature_tools():
    registered = {spec.name for spec in tool_specs() if spec.name.startswith("feature_")}
    assert registered == FEATURE_TOOLS


def test_every_feature_tool_requires_a_doc_handle_and_rejects_unknown_keys():
    specs = _specs_by_name()
    for name in FEATURE_TOOLS:
        schema = specs[name].input_schema
        assert schema["additionalProperties"] is False, name
        assert "doc" in schema["required"], name
        assert schema["properties"]["doc"]["type"] == "string", name


def test_every_feature_tool_accepts_an_optional_unenforced_confirm():
    specs = _specs_by_name()
    for name in FEATURE_TOOLS:
        schema = specs[name].input_schema
        assert "confirm" in schema["properties"], name
        assert "confirm" not in schema["required"], name


def test_every_creating_feature_tool_requires_an_intent_bearing_name():
    specs = _specs_by_name()
    for name in FEATURE_TOOLS - {"feature_set_parameters"}:
        schema = specs[name].input_schema
        assert "name" in schema["required"], name


def test_every_feature_tool_has_a_non_empty_description():
    specs = _specs_by_name()
    for name in FEATURE_TOOLS:
        assert specs[name].description.strip(), name


def test_no_feature_tool_entered_the_read_only_profile():
    # The Phase-1 assistant profile's G1.6 guarantee is zero mutation tools.
    assert not (FEATURE_TOOLS & READ_ONLY_PROFILE)
    assert not any(name.startswith("feature_") for name in READ_ONLY_PROFILE)


def test_feature_body_create_takes_a_name_and_an_optional_base_feature():
    """The Body creator needs no body argument — it is what produces one."""
    schema = _specs_by_name()["feature_body_create"].input_schema

    assert set(schema["properties"]) == {"doc", "name", "base_feature", "confirm"}
    assert schema["required"] == ["doc", "name"]
    assert schema["properties"]["base_feature"]["type"] == "string"
    assert "body" not in schema["properties"]


def test_the_dress_up_tools_take_a_selector_list_for_their_edges():
    specs = _specs_by_name()
    for name in ("feature_fillet", "feature_chamfer"):
        edges = specs[name].input_schema["properties"]["edges"]
        assert edges["type"] == "array"
        assert edges["minItems"] == 1
        assert edges["items"]["required"] == ["kind", "object"]
        assert "edges" in specs[name].input_schema["required"], name


def test_the_pattern_tool_documents_the_polar_step_so_an_agent_does_not_off_by_one_it():
    description = _specs_by_name()["feature_pattern"].description
    assert "angle/occurrences" in description
    assert "occurrences-1" in description


# --------------------------------------------------------------------------- #
# ring purity and version discipline
# --------------------------------------------------------------------------- #


def test_the_use_case_ring_authors_no_transaction_of_its_own():
    # Every mutation runs through run_mutation; a feature tool that opened its own transaction
    # would sit outside the rollback proof.
    source = FEATURES_SOURCE.read_text(encoding="utf-8")
    for banned in ("openTransaction", "commitTransaction", "abortTransaction"):
        assert banned not in source, banned


def test_the_use_case_ring_never_targets_the_active_document():
    assert "ActiveDocument" not in FEATURES_SOURCE.read_text(encoding="utf-8")


def test_no_one_point_one_only_extrude_property_is_referenced():
    # SideType, Type2, Offset2 and the second-direction taper/face/shape properties are absent
    # from the 1.0.x floor leg; using any of them would break that blocking CI leg.
    source = FEATURES_SOURCE.read_text(encoding="utf-8")
    for banned in ("SideType", "Type2", "Offset2", "TaperAngle2", "UpToFace2", "UpToShape2"):
        assert banned not in source, banned


def test_symmetric_extrusion_goes_through_the_shim_rather_than_a_direct_write():
    # Midplane is the property present on both legs, and the shim owns the write so the
    # divergence never leaks into the use-case ring.
    source = FEATURES_SOURCE.read_text(encoding="utf-8")
    assert "shim.extrude_symmetric" in source
    assert "Midplane" not in source


def test_no_extrude_type_enum_is_indexed_numerically():
    # One enum position is a deprecation tombstone on the newer leg and a live member on the
    # older one, so an index would select a different value per build.
    source = FEATURES_SOURCE.read_text(encoding="utf-8")
    assert "TwoLengths" not in source
    assert "setEnums" not in source


def test_every_enumerated_assignment_is_checked_against_the_live_enumeration():
    source = FEATURES_SOURCE.read_text(encoding="utf-8")
    assert "shim.enum_values" in source
    for prop in ("Type", "DepthType", "ThreadType", "HoleCutType", "ChamferType", "Mode"):
        assert f'"{prop}"' in source, prop


def test_the_shim_exposes_the_partdesign_probe_and_its_cross_leg_accessors():
    from freecad_buddy.usecases import shim

    for name in ("partdesign_available", "extrude_symmetric", "enum_values"):
        assert callable(getattr(shim, name)), name


def test_the_partdesign_probe_is_warmed_with_the_other_capability_probes():
    source = (REPO_ROOT / "src" / "freecad_buddy" / "usecases" / "shim.py").read_text(
        encoding="utf-8"
    )
    warm = source.split("def warm_capability_probes")[1].split("def ")[0]
    assert "partdesign_available()" in warm
