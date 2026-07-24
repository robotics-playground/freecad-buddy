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
from freecad_buddy.adapters.render_probe import OffscreenRenderPort, render_capability_flag
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.contracts import RenderPort
from freecad_buddy.usecases import debug_exec as debug_exec_uc
from freecad_buddy.usecases import exports, queries, screenshot, verify
from freecad_buddy.usecases.capabilities import Capabilities, exec_registered
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.exports import ExportRegistry

_DOC_SCHEMA = {"type": "string", "description": "opaque fcb-doc handle"}

# HandlerFactory returns the raw, un-marshaled handler for a tool given the use-case registries,
# capabilities, and the host-injected ``RenderPort``. ``build_inline_handlers`` optionally wraps
# its result in ``marshal.call``.
HandlerFactory = Callable[
    [DocumentRegistry, ExportRegistry, Capabilities, RenderPort], Callable[..., dict]
]


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

_SELECTOR_SCHEMA = {
    "type": "object",
    "properties": {
        "object": {"type": "string"},
        "element_type": {"enum": ["face", "edge", "vertex"]},
        "index": {"type": "integer", "minimum": 0},
        "mapped_name": {"type": "string"},
    },
    "required": ["object"],
    "additionalProperties": False,
}
_SCREENSHOT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "doc": _DOC_SCHEMA,
        "view": {
            "type": "object",
            "properties": {
                "include": {"type": "array", "items": {"type": "string"}},
                "exclude": {"type": "array", "items": {"type": "string"}},
                "styles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "object": {"type": "string"},
                            "transparency": {"type": "integer", "minimum": 0, "maximum": 100},
                            "color": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 3,
                                "maxItems": 3,
                            },
                        },
                        "required": ["object"],
                        "additionalProperties": False,
                    },
                },
                "focus": _SELECTOR_SCHEMA,
                "highlight": _SELECTOR_SCHEMA,
                "camera": {
                    "enum": ["iso", "front", "top", "right", "left", "back", "bottom", "custom"],
                    "default": "iso",
                },
                "custom_orientation": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 4,
                    "maxItems": 4,
                },
                "width": {"type": "integer", "default": 1920, "maximum": 1920},
                "height": {"type": "integer", "default": 1920, "maximum": 1920},
            },
            "additionalProperties": False,
        },
    },
    "required": ["doc"],
    "additionalProperties": False,
}


def _doc_method(attr, timeout, schema, description, *, mutating):
    """A ``ToolSpec`` whose handler forwards straight to a ``DocumentRegistry`` method."""

    def make(doc_registry, export_registry, caps, render_port):  # noqa: ARG001
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

    def make(doc_registry, export_registry, caps, render_port):  # noqa: ARG001
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

    def make(doc_registry, export_registry, caps, render_port):  # noqa: ARG001
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
    def make(doc_registry, export_registry, caps, render_port):  # noqa: ARG001
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
    def make(doc_registry, export_registry, caps, render_port):  # noqa: ARG001
        return lambda: queries.query_capabilities(
            exec_enabled=exec_registered(caps), render=render_capability_flag()
        )

    return ToolSpec(
        name="query_capabilities",
        make_handler=make,
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        description="Runtime capability probes: version, element_map, serializer, "
        "varset backend, render, exec state.",
        timeout_s=30.0,
        mutating=False,
    )


def _screenshot_spec():
    def make(doc_registry, export_registry, caps, render_port):  # noqa: ARG001
        return lambda **p: screenshot.query_screenshot(doc_registry, render_port, **p)

    return ToolSpec(
        name="query_screenshot",
        make_handler=make,
        input_schema=_SCREENSHOT_INPUT_SCHEMA,
        description="Read-only view-controlled render: constructed scene (include/exclude/"
        "styles/focus/highlight/camera) to a PNG resource_link; never mutates the document.",
        timeout_s=60.0,
        mutating=False,
    )


# The read-only assistant profile (G1.6): an explicit allow-list of tool names the Phase-1
# assistant may register. It is NOT a `mutating=False` negation — `document_open`/`close`
# carry `mutating=True` (they open/close documents) yet perform no geometry mutation and the
# assistant needs `document_open` to load the fixture it answers about. The allow-list names the
# seven read-only queries, the three read-only verifiers, and the three non-geometry
# document-lifecycle tools; every geometry-mutation tool (`sketch_*`/`feature_*`/`preview_*`/
# `document_create`/`document_save`/`debug_exec`) is absent by construction.
# Four read-only (`mutating=False`) tools are also deliberately excluded: `verify_export_step`/
# `_stl`/`_3mf` require an `export_id` from a prior export (a mutation the read-only assistant
# cannot perform, so they are inert here), and `query_screenshot` is a render the text-QA
# assistant does not need under the G1.3 latency budget.
READ_ONLY_PROFILE = frozenset(
    {
        "query_capabilities",
        "query_tree_summary",
        "query_object",
        "query_mass_properties",
        "query_dependencies",
        "query_sketch_info",
        "query_placement",
        "verify_shape",
        "verify_sketch",
        "verify_recompute",
        "document_open",
        "document_close",
        "document_list",
    }
)


DEBUG_EXEC_SPEC = ToolSpec(
    name="debug_exec",
    make_handler=lambda doc_registry, export_registry, caps, render_port: (
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
        _screenshot_spec(),
        _query_method(
            "query_tree_summary",
            queries.query_tree_summary,
            30.0,
            {
                "type": "object",
                "properties": {
                    "doc": _DOC_SCHEMA,
                    "depth": {"type": "integer", "default": 1, "minimum": 1},
                    "root": {"type": "string"},
                    "filters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "types": {"type": "array", "items": {"type": "string"}},
                            "exclude_types": {"type": "array", "items": {"type": "string"}},
                            "renderable_only": {"type": "boolean"},
                            "visible_only": {"type": "boolean"},
                            "name_pattern": {"type": "string"},
                        },
                    },
                },
                "required": ["doc"],
                "additionalProperties": False,
            },
            "Depth-bounded, filterable feature-tree summary with nesting of children/App::Link.",
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
                "properties": {
                    "doc": _DOC_SCHEMA,
                    "object": {"type": "string"},
                    "max_edges": {"type": "integer", "minimum": 1, "default": 2000},
                },
                "required": ["doc"],
                "additionalProperties": False,
            },
            "Dependency links by Name: in/out lists for an object, or whole-doc edges "
            "capped at max_edges (truncation flagged).",
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
    render_port: RenderPort | None = None,
) -> MethodRegistry:
    """Build a ``MethodRegistry`` from the shared catalog.

    ``marshal`` given → each handler is wrapped in ``marshal.call`` (headless inline host).
    ``marshal`` is ``None`` → handlers call the use case directly (the listener owns the single
    ``marshal.call`` and a second layer would deadlock the Qt main thread). ``render_port``
    defaults to a fresh ``OffscreenRenderPort`` (the one render capability serves every host).
    """
    port = render_port if render_port is not None else OffscreenRenderPort()
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
        raw = spec.make_handler(doc_registry, export_registry, caps, port)
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

    # The FreeCAD self-read legs of the mesh verifiers are exposed as RPC methods (not MCP tools)
    # so the external proxy can run the third-party oracle legs on its own side (AD-9/AD-12: the
    # oracles must not run inside FreeCAD) and RPC only this FreeCAD-side leg here.
    for leg_name, leg_fn in (
        ("export_self_read_stl", exports.export_self_read_stl),
        ("export_self_read_3mf", exports.export_self_read_3mf),
    ):
        raw = (lambda fn: lambda **p: fn(doc_registry, export_registry, **p))(leg_fn)
        methods.register(
            RpcMethod(
                name=leg_name,
                handler=wrap(raw, 120.0),
                input_schema=_VERIFY_EXPORT_INPUT_SCHEMA,
                description="FreeCAD self-read leg for mesh export verification (internal).",
                timeout_s=120.0,
                mutating=False,
                internal=True,
            )
        )
    return methods


def build_readonly_profile(
    doc_registry: DocumentRegistry,
    export_registry: ExportRegistry,
    caps: Capabilities,
    marshal: Marshal | None,
    render_port: RenderPort | None = None,
) -> MethodRegistry:
    """Build the read-only assistant ``MethodRegistry`` from the ``READ_ONLY_PROFILE`` allow-list.

    Builds the full catalog registry via ``build_inline_handlers`` (so each tool is wired exactly
    as the production server wires it), then re-registers only the methods whose name is in the
    allow-list. Every geometry-mutation tool is absent because it is not in the allow-list —
    ``debug_exec`` is excluded even when exec is enabled. The returned registry is the same shape
    the MCP server consumes, so the assistant drives the identical tool surface (no private path).
    """
    full = build_inline_handlers(doc_registry, export_registry, caps, marshal, render_port)
    profile = MethodRegistry()
    for method in full.methods():
        if method.name in READ_ONLY_PROFILE:
            profile.register(method)
    return profile


__all__ = [
    "DEBUG_EXEC_SPEC",
    "READ_ONLY_PROFILE",
    "ToolSpec",
    "build_inline_handlers",
    "build_readonly_profile",
    "tool_specs",
]
