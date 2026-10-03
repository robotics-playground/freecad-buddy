"""Deterministic TypedDict -> JSON-Schema (Draft 2020-12) generator for contracts/.

Emits one ``*.schema.json`` per top-level wire type into
``src/freecad_buddy/contracts/jsonschema/``. Stdlib only; runs FreeCAD-free in the uv
external env.

Determinism: ``json.dumps(sort_keys=True, indent=2)`` + a single trailing newline;
stable ``$defs`` ordering; no timestamps/paths in output.

Required fields: the contract TypedDicts are all ``total=False`` (additive evolution),
so ``__required_keys__`` is empty. The prose-required fields are carried in an explicit
``REQUIRED_FIELDS`` manifest and emitted as the schema
``required`` array. A wire root or ``$def`` that validates ``{}`` for a required field
is a defect.

Conditionals: cross-field rules that ``required`` cannot express are carried in an
explicit ``CONDITIONALS`` manifest and emitted as a Draft-2020-12 ``if``/``then`` pair on
the wire root. The ``then`` clause reuses the target field's own emitted fragment with
any null branch dropped.

Self-consistency GUARD: after building each schema object the generator asserts
``set(required) ⊆ set(properties)`` for every root and ``$def`` and raises on a manifest
entry naming a field not in the emitted properties (catches manifest typos/drift). The
same guard covers every field named by ``CONDITIONALS``, whose entries must also carry
the full spec key set and name a wire root.

``--check`` regenerates in-memory and diffs against disk (drift = exit 1), and also
fails on an orphan ``*.schema.json`` on disk not in the freshly-generated set.
"""

from __future__ import annotations

import json
import sys
import types
import typing
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

from freecad_buddy.contracts.audit import AuditRecord
from freecad_buddy.contracts.capabilities import CapabilityBanner
from freecad_buddy.contracts.diff import GeometryDiff
from freecad_buddy.contracts.envelope import ResultEnvelope
from freecad_buddy.contracts.feature import FeatureState
from freecad_buddy.contracts.fingerprint import FingerprintRecord
from freecad_buddy.contracts.job import JobStatus
from freecad_buddy.contracts.mutation import MutationBlock
from freecad_buddy.contracts.report import ValidationReport
from freecad_buddy.contracts.sketch import SketchState

# Wire roots: (filename stem, TypedDict). One schema file each.
WIRE_ROOTS: list[tuple[str, Any]] = [
    ("result-envelope", ResultEnvelope),
    ("validation-report", ValidationReport),
    ("job-status", JobStatus),
    ("audit-record", AuditRecord),
    ("geometry-diff", GeometryDiff),
    ("fingerprint", FingerprintRecord),
    ("capability-banner", CapabilityBanner),
    ("mutation", MutationBlock),
    ("sketch-state", SketchState),
    ("feature-state", FeatureState),
]

# Required-field manifest (type name -> required field names).
# Covers every wire root AND every emitted embedded $def.
REQUIRED_FIELDS: dict[str, list[str]] = {
    # roots
    "ResultEnvelope": ["schema", "status", "structured_content", "text"],
    "ValidationReport": ["schema", "banner", "checks", "verdict"],
    "JobStatus": ["schema", "state"],
    "AuditRecord": ["schema", "ts", "actor", "event"],
    "GeometryDiff": ["schema", "deltas", "counts", "validity", "tnp_precheck"],
    "FingerprintRecord": ["schema", "serializer", "objects", "digest"],
    "CapabilityBanner": [
        "freecad_version",
        "element_map_available",
        "serializer",
        "varset_backend",
        "render",
        "sketcher_available",
        "partdesign_available",
        "enums",
        "exec_enabled",
    ],
    "MutationBlock": [
        "transaction_id",
        "fingerprint_before",
        "fingerprint_after",
        "post_verify",
        "rolled_back",
        "rollback_proven",
    ],
    # embedded $defs
    "ErrorDetail": ["message"],
    # All four are required-and-nullable: a verdict that omitted `checked` would let a reader
    # take a cached `fits` for a fresh one, which is the failure AD-32 exists to prevent.
    "FramingVerdict": ["fits", "ratio", "checked", "stale_reason"],
    "PostVerifyBlock": ["recompute_clean", "is_valid", "fully_constrained", "tnp_audit", "passed"],
    "TnpAuditBlock": ["status", "element_map_version", "findings"],
    "RefFinding": ["owner", "prop", "verdict", "layer"],
    "ReportBanner": ["freecad_version", "element_map_version"],
    "AnchorFrame": ["kind"],
    "Check": ["passed"],
    "WilsonCI": ["rate", "low", "high", "n", "r"],
    "DocHandle": ["handle"],
    "ObjectFingerprint": ["name", "brep_sha256", "massprops"],
    "MassProps": ["volume", "area", "bbox", "com", "principal_moments", "quantum"],
    "GeometricSelector": ["kind", "object", "element_type"],
    "MappedNameSelector": ["kind", "object", "mapped_name", "element_map_version"],
    # GeometryDiff's nested blocks. Every one carries a required list: a $def without one
    # validates `{}`, which lets the preview emit any shape and the schema still pass.
    "ScalarDelta": ["before", "after", "delta", "units"],
    "CountDelta": ["before", "after", "delta"],
    "BBoxDelta": ["before", "after", "center_shift", "units"],
    "ComDelta": ["before", "after", "shift", "units"],
    "DiffDeltas": ["volume", "area", "bbox", "com"],
    "DiffCounts": ["faces", "edges", "vertices", "solids"],
    "RecomputeError": ["object", "error"],
    "DiffValidity": [
        "is_valid",
        "recompute_clean",
        "recompute_errors",
        "pre_existing_errors",
        "status",
        "explanation",
    ],
    "DiffRender": ["available", "reason"],
    # The grading fields are present only when `readable` is true; a sketch a rollback
    # destroyed reports `readable: false` and carries no grade.
    "SketchState": ["schema", "sketch", "readable"],
    "ConstraintRef": ["id"],
    # The shape summary is present only when `readable` is true; a feature a rollback removed
    # reports `readable: false` and carries no summary.
    "FeatureState": ["schema", "feature", "readable"],
    "ShapeSummary": [
        "volume",
        "area",
        "bbox",
        "solid_count",
        "face_count",
        "edge_count",
        "vertex_count",
        "is_valid",
    ],
}

# Types emitted with ``additionalProperties: false``. A closed type rejects an unknown field
# rather than silently defaulting the real one, which is a breaking change for any producer
# sending an extra key — so closure is opt-in per type rather than a blanket default.
CLOSED_TYPES: frozenset[str] = frozenset(
    {"MutationBlock", "PostVerifyBlock", "TnpAuditBlock", "RefFinding"}
)

# Conditional manifest (wire-root type name -> conditional spec). Each entry binds
# "some entry of an array field carries a discriminator value" to "a field of a nested
# object is required and non-null", emitted as a Draft-2020-12 ``if``/``then`` pair.
CONDITIONALS: dict[str, dict[str, Any]] = {
    "ValidationReport": {
        "when_array_fields": ["checks", "warnings"],
        "entry_field": "measured_kind",
        "entry_value": "rate",
        "then_object_field": "banner",
        "then_required_field": "wilson_ci",
    },
}

_CONDITIONAL_SPEC_KEYS = frozenset(
    {
        "when_array_fields",
        "entry_field",
        "entry_value",
        "then_object_field",
        "then_required_field",
    }
)

_UNION_ORIGINS = (Union, types.UnionType)


def _is_union(origin: Any) -> bool:
    return origin is Union or origin is types.UnionType


def _flatten_literal(members: list[Any], out: list[Any]) -> None:
    """Collect Literal string/scalar members, flattening nested Literals recursively."""
    for m in members:
        nested = get_args(m)
        if nested and get_origin(m) is Literal:
            _flatten_literal(list(nested), out)
        else:
            out.append(m)


def _schema_for(tp: Any, defs: dict[str, dict]) -> dict:
    """Map a type annotation to a JSON-Schema fragment, registering nested $defs."""
    if typing.is_typeddict(tp):
        _register_def(tp, defs)
        return {"$ref": f"#/$defs/{tp.__name__}"}

    origin = get_origin(tp)

    if origin is Literal:
        members: list[Any] = []
        _flatten_literal(list(get_args(tp)), members)
        if len(members) == 1:
            return {"const": members[0]}
        return {"enum": members}

    if _is_union(origin):
        args = [a for a in get_args(tp) if a is not type(None)]
        has_none = len(args) != len(get_args(tp))
        subs = [_schema_for(a, defs) for a in args]
        if has_none:
            subs.append({"type": "null"})
        if len(subs) == 1:
            return subs[0]
        return {"anyOf": subs}

    if tp in (dict, typing.Dict):  # noqa: UP006 - runtime identity check
        return {"type": "object"}
    if origin in (dict,):
        return {"type": "object"}

    if origin in (list,):
        (item,) = get_args(tp) or (Any,)
        return {"type": "array", "items": _schema_for(item, defs)}
    if tp is list:
        return {"type": "array"}

    if tp in (tuple, typing.Tuple):  # noqa: UP006 - runtime identity check
        return {"type": "array"}
    if origin is tuple:
        args = get_args(tp)
        if args == ():
            return {"type": "array", "maxItems": 0}
        if args[-1] is Ellipsis:
            if len(args) != 2 or Ellipsis in args[:-1]:
                raise ValueError(f"unsupported Ellipsis placement in {tp!r}")
            return {"type": "array", "items": _schema_for(args[0], defs)}
        if Ellipsis in args:
            raise ValueError(f"unsupported Ellipsis placement in {tp!r}")
        return {
            "type": "array",
            "prefixItems": [_schema_for(a, defs) for a in args],
            "minItems": len(args),
            "maxItems": len(args),
        }

    if tp in (set, frozenset, typing.Set, typing.FrozenSet):  # noqa: UP006 - runtime identity check
        return {"type": "array", "uniqueItems": True}
    if origin in (set, frozenset):
        return {
            "type": "array",
            "uniqueItems": True,
            "items": _schema_for(get_args(tp)[0], defs),
        }

    scalar = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
    }
    if tp in scalar:
        return dict(scalar[tp])

    if tp is Any:
        return {}

    return {}


def _properties_and_required(tp: Any, defs: dict[str, dict]) -> tuple[dict, list[str]]:
    hints = get_type_hints(tp, include_extras=False)
    properties = {name: _schema_for(ann, defs) for name, ann in hints.items()}
    required = list(REQUIRED_FIELDS.get(tp.__name__, []))

    missing = [f for f in required if f not in properties]
    if missing:
        raise ValueError(
            f"REQUIRED_FIELDS['{tp.__name__}'] names field(s) not in properties: "
            f"{missing} (properties: {sorted(properties)})"
        )
    return properties, required


def _register_def(tp: Any, defs: dict[str, dict]) -> None:
    name = tp.__name__
    if name in defs:
        return
    defs[name] = {}  # placeholder to break recursion cycles
    properties, required = _properties_and_required(tp, defs)
    body: dict = {"type": "object", "properties": properties}
    if required:
        body["required"] = required
    if name in CLOSED_TYPES:
        body["additionalProperties"] = False
    defs[name] = body


def _conditional(name: str, properties: dict, defs: dict[str, dict]) -> dict | None:
    """Build the ``if``/``then`` pair for a type, or ``None`` if it has no entry.

    Raises ``ValueError`` when the manifest entry lacks a spec key, names no array
    field at all, an array field absent from ``properties``, a field that is not
    array-typed, an array whose items or an object field that is not a ``$ref``,
    an entry field absent from the array item's ``$def``, an entry value outside
    that entry field's emitted enum, or an object field whose ``$def`` lacks the
    required field.
    """
    spec = CONDITIONALS.get(name)
    if spec is None:
        return None

    absent_keys = sorted(_CONDITIONAL_SPEC_KEYS - set(spec))
    if absent_keys:
        raise ValueError(f"CONDITIONALS['{name}'] is missing spec key(s): {absent_keys}")

    def _ref_props(fragment: dict, what: str) -> dict:
        ref = fragment.get("$ref")
        if not isinstance(ref, str):
            raise ValueError(
                f"CONDITIONALS['{name}'] targets {what}, which is not a $ref to a $def: {fragment}"
            )
        return defs.get(ref.rsplit("/", 1)[-1], {}).get("properties", {})

    def _non_null(fragment: dict) -> dict:
        """Return ``fragment`` with any ``anyOf`` null branch dropped.

        A fragment whose only branch was the null one would leave nothing to require, which no
        conditional can express; the caller's field is optional-and-nullable, so at least one
        non-null branch always survives.
        """
        branches = [b for b in fragment.get("anyOf", ()) if b != {"type": "null"}]
        if len(branches) == 1:
            return branches[0]
        return {"anyOf": branches}

    def _enum_members(fragment: dict) -> list[Any]:
        if "const" in fragment:
            return [fragment["const"]]
        if "enum" in fragment:
            return list(fragment["enum"])
        members: list[Any] = []
        for sub in fragment.get("anyOf", ()):
            members.extend(_enum_members(sub))
        return members

    array_fields = list(spec["when_array_fields"])
    if not array_fields:
        raise ValueError(f"CONDITIONALS['{name}'] names no array field in 'when_array_fields'")

    antecedents: list[dict] = []
    for field in array_fields:
        if field not in properties:
            raise ValueError(
                f"CONDITIONALS['{name}'] names array field '{field}' not in "
                f"properties: {sorted(properties)}"
            )
        if properties[field].get("type") != "array":
            raise ValueError(
                f"CONDITIONALS['{name}'] names array field '{field}' whose emitted "
                f"property is not array-typed: {properties[field]}"
            )
        item_props = _ref_props(properties[field].get("items", {}), f"items of '{field}'")
        if spec["entry_field"] not in item_props:
            raise ValueError(
                f"CONDITIONALS['{name}'] names entry field "
                f"'{spec['entry_field']}' not in items of '{field}': "
                f"{sorted(item_props)}"
            )
        members = _enum_members(item_props[spec["entry_field"]])
        if spec["entry_value"] not in members:
            raise ValueError(
                f"CONDITIONALS['{name}'] names entry value "
                f"{spec['entry_value']!r} not among '{spec['entry_field']}' enum "
                f"members of '{field}': {members}"
            )
        antecedents.append(
            {
                "properties": {
                    field: {
                        "contains": {
                            "properties": {spec["entry_field"]: {"const": spec["entry_value"]}},
                            "required": [spec["entry_field"]],
                            "type": "object",
                        },
                        "type": "array",
                    }
                },
                "required": [field],
            }
        )

    obj_field = spec["then_object_field"]
    if obj_field not in properties:
        raise ValueError(
            f"CONDITIONALS['{name}'] names object field '{obj_field}' not in "
            f"properties: {sorted(properties)}"
        )
    obj_props = _ref_props(properties[obj_field], f"object field '{obj_field}'")
    req_field = spec["then_required_field"]
    if req_field not in obj_props:
        raise ValueError(
            f"CONDITIONALS['{name}'] names required field '{req_field}' not in "
            f"'{obj_field}' properties: {sorted(obj_props)}"
        )

    return {
        "if": {"anyOf": antecedents},
        "then": {
            "properties": {
                obj_field: {
                    "properties": {req_field: _non_null(obj_props[req_field])},
                    "required": [req_field],
                    "type": "object",
                }
            },
            "required": [obj_field],
        },
    }


def build_schema(stem: str, tp: Any) -> dict:
    defs: dict[str, dict] = {}
    properties, required = _properties_and_required(tp, defs)
    schema: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"fcb.{stem}/1",
        "title": tp.__name__,
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    if tp.__name__ in CLOSED_TYPES:
        schema["additionalProperties"] = False
    conditional = _conditional(tp.__name__, properties, defs)
    if conditional:
        clash = sorted(schema.keys() & conditional.keys())
        if clash:
            raise ValueError(
                f"CONDITIONALS['{tp.__name__}'] would overwrite existing schema key(s): {clash}"
            )
        schema.update(conditional)
    if defs:
        schema["$defs"] = defs
    return schema


def _serialize(schema: dict) -> str:
    return json.dumps(schema, sort_keys=True, indent=2) + "\n"


def _output_dir() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "src"
        / "freecad_buddy"
        / "contracts"
        / "jsonschema"
    )


def generate() -> dict[str, str]:
    """Return {filename: serialized-schema-text} for every wire root.

    :raises ValueError: ``CONDITIONALS`` names a type that is not a wire root.
    """
    orphans = sorted(set(CONDITIONALS) - {tp.__name__ for _, tp in WIRE_ROOTS})
    if orphans:
        raise ValueError(f"CONDITIONALS names non-wire-root type(s) {orphans}")
    out: dict[str, str] = {}
    for stem, tp in WIRE_ROOTS:
        out[f"{stem}.schema.json"] = _serialize(build_schema(stem, tp))
    return out


def write(out_dir: Path | None = None) -> None:
    out_dir = out_dir or _output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in generate().items():
        (out_dir / name).write_text(text, encoding="utf-8", newline="\n")


def check(out_dir: Path | None = None) -> list[str]:
    """Return a list of drift/orphan problem strings; empty means clean."""
    out_dir = out_dir or _output_dir()
    expected = generate()
    problems: list[str] = []

    for name, text in expected.items():
        path = out_dir / name
        if not path.exists():
            problems.append(f"missing schema: {name}")
            continue
        if path.read_text(encoding="utf-8") != text:
            problems.append(f"drift: {name}")

    for path in sorted(out_dir.glob("*.schema.json")):
        if path.name not in expected:
            problems.append(f"orphan schema: {path.name}")

    return problems


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        problems = check()
        if problems:
            for p in problems:
                print(p)
            return 1
        print("gen_schemas --check OK")
        return 0

    write()
    print("gen_schemas: wrote schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
