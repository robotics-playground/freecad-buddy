"""Shared tool catalog: the single source of the RPC/MCP tool surface.

One catalog serves every host. ``tool_specs()`` returns the ordered ``ToolSpec`` list (names,
schemas, timeouts, mutating/audit metadata) and each spec knows how to build its handler from
the use-case registries.

``build_inline_handlers`` builds a ``MethodRegistry`` from the catalog. When a ``Marshal`` is
passed each handler is wrapped in ``marshal.call`` (the headless inline host, whose
``InlineExecutor`` is a same-thread no-op); when ``marshal`` is ``None`` the handler calls the
use case directly (the listener path, where the ``RpcListener`` owns the single ``marshal.call``
and a second layer would deadlock the Qt main thread).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from freecad_buddy.adapters import export_oracle, export_verdict
from freecad_buddy.adapters.marshal import Marshal
from freecad_buddy.adapters.mcp_server import Capabilities, exec_registered
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.usecases import debug_exec as debug_exec_uc
from freecad_buddy.usecases import exports, queries, verify
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.exports import ExportRegistry

_DOC_SCHEMA = {"type": "string", "description": "opaque fcb-doc handle"}

# HandlerFactory returns the raw, un-marshaled handler for a tool given the use-case
# registries and capabilities. ``build_inline_handlers`` optionally wraps its result in
# ``marshal.call``.
HandlerFactory = Callable[[DocumentRegistry, ExportRegistry, Capabilities], Callable[..., dict]]


@dataclass(frozen=True)
class ToolSpec:
    """A tool's wire metadata plus a factory for its un-marshaled handler."""

    name: str
    make_handler: HandlerFactory
    input_schema: dict
    description: str
    timeout_s: float
    mutating: bool = False
    audit_event: str = "mutation"


def _mesh_verify_handler(doc_registry, export_registry, marshal: Marshal | None, fmt):
    """Build the merged mesh-verify handler (FreeCAD self-read leg + oracle legs).

    The self-read leg touches FreeCAD; when a ``marshal`` is given it runs through it, otherwise
    it is called directly (the listener marshals the whole dispatch). The oracle legs read the
    written file without FreeCAD.
    """
    self_read_uc = {
        "stl": exports.export_self_read_stl,
        "3mf": exports.export_self_read_3mf,
    }[fmt]

    def handler(**params):
        def _self_read():
            return self_read_uc(doc_registry, export_registry, **params)

        self_read = marshal.call(_self_read, 120.0) if marshal is not None else _self_read()
        facts = self_read["structured_content"]
        source = facts["source"]
        band = facts["volume_band"]
        path = facts["path"]
        if fmt == "stl":
            oracle_legs = [
                export_oracle.safe_oracle(
                    "trimesh_stl", lambda: export_oracle.stl_oracle(path, source["volume"], band)
                ),
                export_oracle.safe_oracle(
                    "stdlib_stl", lambda: export_oracle.StdlibStlOracle().check(path)
                ),
            ]
        else:
            oracle_legs = [
                export_oracle.safe_oracle(
                    "lib3mf",
                    lambda: export_oracle.mesh3mf_oracle(
                        path, source["is_mm"], source["volume"], band
                    ),
                ),
            ]
        return export_verdict.assemble_export_verdict(oracle_legs, facts, facts["banner"])

    return handler


_EXPORT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "doc": _DOC_SCHEMA,
        "path": {"type": "string"},
        "objects": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["doc", "path"],
    "additionalProperties": False,
}
_MESH_EXPORT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "doc": _DOC_SCHEMA,
        "path": {"type": "string"},
        "objects": {"type": "array", "items": {"type": "string"}},
        "linear": {"type": "number"},
        "angular": {"type": "number"},
    },
    "required": ["doc", "path"],
    "additionalProperties": False,
}
_VERIFY_EXPORT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"doc": _DOC_SCHEMA, "export_id": {"type": "string"}},
    "required": ["doc", "export_id"],
    "additionalProperties": False,
}
_EXPORT_STEP_INPUT_SCHEMA = {
    **_EXPORT_INPUT_SCHEMA,
    "properties": {
        **_EXPORT_INPUT_SCHEMA["properties"],
        "ap": {"enum": ["AP214", "AP242"], "default": "AP242"},
    },
}


def _doc_method(attr, timeout, schema, description, *, mutating):
    """A ``ToolSpec`` whose handler forwards straight to a ``DocumentRegistry`` method."""

    def make(doc_registry, export_registry, caps):  # noqa: ARG001
        return getattr(doc_registry, attr)

    return ToolSpec(
        name=attr,
        make_handler=make,
        input_schema=schema,
        description=description,
        timeout_s=timeout,
        mutating=mutating,
    )


def _query_method(name, fn, timeout, schema, description):
    """A ``ToolSpec`` for a read-only query use case taking the doc registry."""

    def make(doc_registry, export_registry, caps):  # noqa: ARG001
        return lambda **p: fn(doc_registry, **p)

    return ToolSpec(
        name=name,
        make_handler=make,
        input_schema=schema,
        description=description,
        timeout_s=timeout,
        mutating=False,
    )


def _export_method(name, fn, timeout, schema, description, *, mutating):
    """A ``ToolSpec`` for an export use case taking both registries."""

    def make(doc_registry, export_registry, caps):  # noqa: ARG001
        return lambda **p: fn(doc_registry, export_registry, **p)

    return ToolSpec(
        name=name,
        make_handler=make,
        input_schema=schema,
        description=description,
        timeout_s=timeout,
        mutating=mutating,
    )


def _mesh_verify_spec(name, fmt, description):
    def make(doc_registry, export_registry, caps):  # noqa: ARG001
        return _mesh_verify_handler(doc_registry, export_registry, None, fmt)

    return ToolSpec(
        name=name,
        make_handler=make,
        input_schema=_VERIFY_EXPORT_INPUT_SCHEMA,
        description=description,
        timeout_s=120.0,
        mutating=False,
    )


def _capabilities_spec():
    def make(doc_registry, export_registry, caps):  # noqa: ARG001
        return lambda: queries.query_capabilities(exec_enabled=exec_registered(caps))

    return ToolSpec(
        name="query_capabilities",
        make_handler=make,
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        description="Runtime capability probes: version, element_map, serializer, "
        "varset backend, render, exec state.",
        timeout_s=30.0,
        mutating=False,
    )


DEBUG_EXEC_SPEC = ToolSpec(
    name="debug_exec",
    make_handler=lambda doc_registry, export_registry, caps: (
        lambda **params: debug_exec_uc.debug_exec(
            doc_registry, params.get("doc"), params.get("code", "")
        )
    ),
    input_schema={
        "type": "object",
        "properties": {"doc": _DOC_SCHEMA, "code": {"type": "string"}},
        "required": ["doc", "code"],
        "additionalProperties": False,
    },
    description="Operator-only Python exec for bring-up. Off unless "
    "FREECAD_BUDDY_ALLOW_EXEC=1; every call is audit-logged.",
    timeout_s=30.0,
    mutating=True,
    audit_event="exec",
)


def tool_specs() -> list[ToolSpec]:
    """The ordered tool surface, excluding ``debug_exec`` (gated via ``DEBUG_EXEC_SPEC``)."""
    return [
        _doc_method(
            "document_create",
            30.0,
            {
                "type": "object",
                "properties": {"label": {"type": "string"}, "path": {"type": "string"}},
                "required": ["label"],
                "additionalProperties": False,
            },
            "Create a new document; mint and return its opaque handle.",
            mutating=True,
        ),
        _doc_method(
            "document_open",
            60.0,
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
            "Open an .FCStd file; return its opaque handle.",
            mutating=True,
        ),
        _doc_method(
            "document_save",
            120.0,
            {
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA, "path": {"type": "string"}},
                "required": ["doc"],
                "additionalProperties": False,
            },
            "Save (or save-as) the document named by its handle.",
            mutating=True,
        ),
        _doc_method(
            "document_close",
            30.0,
            {
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA},
                "required": ["doc"],
                "additionalProperties": False,
            },
            "Close the document by handle; releases the handle.",
            mutating=True,
        ),
        _doc_method(
            "document_recompute",
            120.0,
            {
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA},
                "required": ["doc"],
                "additionalProperties": False,
            },
            "Full recompute; report touched-object count and per-object error states.",
            mutating=True,
        ),
        _doc_method(
            "document_list",
            30.0,
            {"type": "object", "properties": {}, "additionalProperties": False},
            "List open documents with handle, name, label, and transient flag.",
            mutating=False,
        ),
        _capabilities_spec(),
        _query_method(
            "query_tree_summary",
            queries.query_tree_summary,
            30.0,
            {
                "type": "object",
                "properties": {
                    "doc": _DOC_SCHEMA,
                    "max_nodes": {"type": "integer", "default": 100, "minimum": 0},
                },
                "required": ["doc"],
                "additionalProperties": False,
            },
            "Bounded feature-tree summary; caps nodes and flags truncation.",
        ),
        _query_method(
            "query_object",
            queries.query_object,
            30.0,
            {
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA, "object": {"type": "string"}},
                "required": ["doc", "object"],
                "additionalProperties": False,
            },
            "Report an object's name, label, type, property values, and error state.",
        ),
        _query_method(
            "query_mass_properties",
            queries.query_mass_properties,
            30.0,
            {
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA, "object": {"type": "string"}},
                "required": ["doc", "object"],
                "additionalProperties": False,
            },
            "Volume, area, bbox, centre of mass, and topology counts of a shape.",
        ),
        _query_method(
            "query_dependencies",
            queries.query_dependencies,
            30.0,
            {
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA, "object": {"type": "string"}},
                "required": ["doc"],
                "additionalProperties": False,
            },
            "Dependency links by Name: in/out lists for an object, or whole-doc edges.",
        ),
        _query_method(
            "query_sketch_info",
            queries.query_sketch_info,
            30.0,
            {
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA, "sketch": {"type": "string"}},
                "required": ["doc", "sketch"],
                "additionalProperties": False,
            },
            "List a sketch's geometry and constraints with driving flags.",
        ),
        _query_method(
            "query_placement",
            queries.query_placement,
            30.0,
            {
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA, "object": {"type": "string"}},
                "required": ["doc", "object"],
                "additionalProperties": False,
            },
            "Report an object's local and global placement (position, axis, angle).",
        ),
        _query_method(
            "verify_shape",
            verify.verify_shape,
            60.0,
            {
                "type": "object",
                "properties": {
                    "doc": _DOC_SCHEMA,
                    "object": {"type": "string"},
                    "checks": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["doc"],
                "additionalProperties": False,
            },
            "Measure a shape against expect_volume/bbox/solid_count/valid/watertight.",
        ),
        _query_method(
            "verify_sketch",
            verify.verify_sketch,
            60.0,
            {
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA, "sketch": {"type": "string"}},
                "required": ["doc", "sketch"],
                "additionalProperties": False,
            },
            "Grade a sketch: PASS iff FullyConstrained after recompute (AD-8).",
        ),
        _query_method(
            "verify_recompute",
            verify.verify_recompute,
            120.0,
            {
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA},
                "required": ["doc"],
                "additionalProperties": False,
            },
            "Recompute and report failing objects with their status strings.",
        ),
        _export_method(
            "export_step",
            exports.export_step,
            120.0,
            _EXPORT_STEP_INPUT_SCHEMA,
            "Write a shape to STEP (unit=MM, AP pinned); result verified:false.",
            mutating=True,
        ),
        _export_method(
            "export_stl",
            exports.export_stl,
            120.0,
            _MESH_EXPORT_INPUT_SCHEMA,
            "Write a shape to binary STL from one tessellation; result verified:false.",
            mutating=True,
        ),
        _export_method(
            "export_3mf",
            exports.export_3mf,
            120.0,
            _MESH_EXPORT_INPUT_SCHEMA,
            "Write a shape to 3MF from one tessellation; result verified:false.",
            mutating=True,
        ),
        _export_method(
            "verify_export_step",
            exports.verify_export_step,
            120.0,
            _VERIFY_EXPORT_INPUT_SCHEMA,
            "Re-import a written STEP and grade volume/isValid/counts against source.",
            mutating=False,
        ),
        _mesh_verify_spec(
            "verify_export_stl",
            "stl",
            "Verify a written STL: trimesh + second oracle + FreeCAD self-read merged.",
        ),
        _mesh_verify_spec(
            "verify_export_3mf",
            "3mf",
            "Verify a written 3MF: lib3mf + trimesh + FreeCAD self-read merged.",
        ),
    ]


def build_inline_handlers(
    doc_registry: DocumentRegistry,
    export_registry: ExportRegistry,
    caps: Capabilities,
    marshal: Marshal | None,
) -> MethodRegistry:
    """Build a ``MethodRegistry`` from the shared catalog.

    ``marshal`` given → each handler is wrapped in ``marshal.call`` (headless inline host).
    ``marshal`` is ``None`` → handlers call the use case directly (the listener owns the single
    ``marshal.call`` and a second layer would deadlock the Qt main thread).
    """
    methods = MethodRegistry()

    def wrap(raw, timeout_s):
        if marshal is None:
            return raw

        def handler(**params):
            return marshal.call(lambda: raw(**params), timeout_s)

        return handler

    specs = list(tool_specs())
    if exec_registered(caps):
        specs.append(DEBUG_EXEC_SPEC)

    for spec in specs:
        raw = spec.make_handler(doc_registry, export_registry, caps)
        methods.register(
            RpcMethod(
                name=spec.name,
                handler=wrap(raw, spec.timeout_s),
                input_schema=spec.input_schema,
                description=spec.description,
                timeout_s=spec.timeout_s,
                mutating=spec.mutating,
                audit_event=spec.audit_event,
            )
        )
    return methods


__all__ = [
    "DEBUG_EXEC_SPEC",
    "ToolSpec",
    "build_inline_handlers",
    "tool_specs",
]
