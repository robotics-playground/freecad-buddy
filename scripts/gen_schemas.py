"""Deterministic TypedDict -> JSON-Schema (Draft 2020-12) generator for contracts/.

Emits one ``*.schema.json`` per top-level wire type into
``src/freecad_buddy/contracts/jsonschema/``. Stdlib only; runs FreeCAD-free in the uv
external env (AC#2).

Determinism: ``json.dumps(sort_keys=True, indent=2)`` + a single trailing newline;
stable ``$defs`` ordering; no timestamps/paths in output.

Required fields: the contract TypedDicts are all ``total=False`` (additive evolution),
so ``__required_keys__`` is empty. The prose-required fields are carried in an explicit
``REQUIRED_FIELDS`` manifest, transcribed verbatim from the design's ``# required``
annotations (§2/§3/§4/§5/§6/§7/§8/§9/§10/§12.2/§12.7), and emitted as the schema
``required`` array. A wire root or ``$def`` that validates ``{}`` for a required field
is a defect.

Self-consistency GUARD: after building each schema object the generator asserts
``set(required) ⊆ set(properties)`` for every root and ``$def`` and raises on a manifest
entry naming a field not in the emitted properties (catches manifest typos/drift).

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
from freecad_buddy.contracts.diff import GeometryDiff
from freecad_buddy.contracts.envelope import ResultEnvelope
from freecad_buddy.contracts.fingerprint import FingerprintRecord
from freecad_buddy.contracts.job import JobStatus
from freecad_buddy.contracts.report import ValidationReport

# Wire roots: (filename stem, TypedDict). One schema file each.
WIRE_ROOTS: list[tuple[str, Any]] = [
    ("result-envelope", ResultEnvelope),
    ("validation-report", ValidationReport),
    ("job-status", JobStatus),
    ("audit-record", AuditRecord),
    ("geometry-diff", GeometryDiff),
    ("fingerprint", FingerprintRecord),
]

# Required-field manifest (type name -> required field names), transcribed from the
# design's "# required" prose. Covers every wire root AND every emitted embedded $def.
REQUIRED_FIELDS: dict[str, list[str]] = {
    # roots
    "ResultEnvelope": ["schema", "status", "structured_content", "text"],
    "ValidationReport": ["schema", "banner", "checks", "verdict"],
    "JobStatus": ["schema", "state"],
    "AuditRecord": ["schema", "ts", "actor", "event"],
    "GeometryDiff": ["schema", "deltas", "counts", "validity", "tnp_precheck"],
    "FingerprintRecord": ["schema", "serializer", "objects", "digest"],
    # embedded $defs
    "ErrorDetail": ["message"],
    "ReportBanner": ["freecad_version", "element_map_version"],
    "Check": ["passed"],
    "DocHandle": ["handle"],
    "ObjectFingerprint": ["name", "brep_sha256", "massprops"],
    "MassProps": ["volume", "area", "bbox", "com", "principal_moments", "quantum"],
    "GeometricSelector": ["kind", "object", "element_type"],
    "MappedNameSelector": ["kind", "object", "mapped_name", "element_map_version"],
}

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
    defs[name] = body


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
    """Return {filename: serialized-schema-text} for every wire root."""
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
