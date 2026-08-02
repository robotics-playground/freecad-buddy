"""Shared tool catalog: the single source of the RPC/MCP tool surface.

One catalog serves every host. ``tool_specs()`` returns the ordered ``ToolSpec`` list (names,
schemas, timeouts, mutating/audit metadata) and each spec knows how to build its handler from
the use-case registries.

``build_inline_handlers`` builds a ``MethodRegistry`` from the catalog. When a ``Marshal`` is
passed each handler is wrapped in ``marshal.call`` (the headless inline host, whose
``InlineExecutor`` is a same-thread no-op); when ``marshal`` is ``None`` the handler calls the
use case directly (the listener path, where the ``RpcListener`` owns the single ``marshal.call``
and a second layer would deadlock the Qt main thread). ``debug_exec`` is the one exception on
the inline host: it gets a further bounded layer that runs the exec body on a worker thread so
its declared budget is enforced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from freecad_buddy.adapters import export_oracle, export_verdict
from freecad_buddy.adapters.marshal import Marshal, ThreadExecutor
from freecad_buddy.adapters.render_probe import OffscreenRenderPort, render_capability_flag
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.contracts import RenderPort
from freecad_buddy.usecases import debug_exec as debug_exec_uc
from freecad_buddy.usecases import (
    confirm,
    exports,
    features,
    preview,
    queries,
    screenshot,
    sketches,
    verify,
)
from freecad_buddy.usecases.capabilities import (
    Capabilities,
    auto_approve_enabled,
    exec_registered,
)
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


_QUANTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": "number"},
        "unit": {"type": "string", "description": "explicit unit, e.g. mm or deg"},
    },
    "required": ["value", "unit"],
    "additionalProperties": False,
}
# The contracts Selector (contracts/document.py); sketch tools resolve the mapped_name variant.
_SUBELEMENT_SELECTOR_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"enum": ["mapped_name", "geometric"]},
        "object": {"type": "string", "description": "immutable object Name"},
        "mapped_name": {"type": "string"},
        "element_map_version": {"type": "integer"},
        "element_type": {"enum": ["face", "edge", "vertex"]},
        "query": {"type": "object"},
    },
    "required": ["kind", "object"],
    "additionalProperties": False,
}
# The confirm gate's wire shape. `autoApprove` is deliberately absent: the posture is an
# operator-set environment flag carried on the capability record, and a client that could ask for
# it on the wire would be self-approving its own mutation.
_CONFIRM_SCHEMA = {
    "type": "object",
    "description": (
        "required: this mutation is refused without it. Call preview_dry_run for the same tool "
        "and arguments on the same document, then pass back the preview_id it returned. Omit "
        "only against a host running the operator auto-approve posture."
    ),
    "properties": {
        "preview_id": {
            "type": "string",
            "description": "the signed token preview_dry_run returned for this exact operation",
        },
        "elicitation_action": {
            "enum": ["accept"],
            "description": "recorded outcome; decline/cancel never reach a mutation tool",
        },
    },
    "required": ["preview_id"],
    "additionalProperties": False,
}
_GEOMETRY_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"enum": ["line_segment", "circle", "arc_of_circle", "point"]},
        "start": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 3},
        "end": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 3},
        "center": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 3},
        "radius": _QUANTITY_SCHEMA,
        "start_angle": _QUANTITY_SCHEMA,
        "end_angle": _QUANTITY_SCHEMA,
        "construction": {"type": "boolean", "default": False},
    },
    "required": ["kind"],
    "additionalProperties": False,
}
_CONSTRAINT_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {
            "enum": [
                "Coincident",
                "Horizontal",
                "Vertical",
                "Parallel",
                "Perpendicular",
                "Tangent",
                "Equal",
                "Symmetric",
                "PointOnObject",
                "Block",
                "Distance",
                "DistanceX",
                "DistanceY",
                "Radius",
                "Diameter",
                "Angle",
            ]
        },
        "first": {"type": "integer", "description": "sketch geo_id; -1 HAxis, -2 VAxis"},
        "first_pos": {
            "enum": [0, 1, 2, 3],
            "description": "PointPos: 0 none, 1 start, 2 end, 3 mid",
        },
        "second": {"type": "integer"},
        "second_pos": {"enum": [0, 1, 2, 3]},
        "third": {"type": "integer"},
        "third_pos": {"enum": [0, 1, 2, 3]},
        "value": _QUANTITY_SCHEMA,
        "name": {"type": "string", "description": "intent-bearing constraint name"},
        "driving": {"type": "boolean", "default": True},
    },
    "required": ["type", "first"],
    "additionalProperties": False,
}
_CONSTRAINT_REF_SCHEMA = {
    "anyOf": [
        {"type": "integer", "minimum": 1, "description": "1-based solver id"},
        {"type": "string", "description": "constraint Name"},
    ]
}


def _sketch_schema(properties, required):
    """A sketch tool input schema: doc handle, the tool's own fields, and the confirm gate.

    ``confirm`` is not in ``required``: it is mandatory for a client, but a host running the
    operator auto-approve posture accepts a call without one, and the specs are built before the
    capability record is read. The gate's requirement is stated in ``_CONFIRM_SCHEMA`` instead.
    """
    return {
        "type": "object",
        "properties": {"doc": _DOC_SCHEMA, **properties, "confirm": _CONFIRM_SCHEMA},
        "required": ["doc", *required],
        "additionalProperties": False,
    }


def _sketch_method(name, fn, schema, description):
    """A ``ToolSpec`` for a sketch mutation use case.

    The handler passes no ``audit_sink``: ``HandlerFactory`` has no sink parameter, and the MCP
    server already writes a before/after record for every ``mutating`` tool.
    """

    def make(doc_registry, export_registry, caps, render_port):  # noqa: ARG001
        return lambda **p: fn(doc_registry, **p)

    return ToolSpec(
        name=name,
        make_handler=make,
        input_schema=schema,
        description=description,
        timeout_s=120.0,
        mutating=True,
    )


def _sketch_specs():
    """The eight ``sketch_*`` mutation specs, in catalog order."""
    return [
        _sketch_method(
            "sketch_create",
            sketches.sketch_create,
            _sketch_schema(
                {
                    "name": {"type": "string"},
                    "plane": {"enum": ["XY", "XZ", "YZ"]},
                    "face": _SUBELEMENT_SELECTOR_SCHEMA,
                    "body": {
                        "type": "string",
                        "description": "PartDesign Body Name to adopt the sketch into",
                    },
                },
                ["name"],
            ),
            "Create a sketch on a base plane (XY/XZ/YZ) or attached to a planar face. "
            "A new sketch is empty, so it commits fully constrained. Pass 'body' to place it "
            "inside the Body that will consume it.",
        ),
        _sketch_method(
            "sketch_add_geometry",
            sketches.sketch_add_geometry,
            _sketch_schema(
                {
                    "sketch": {"type": "string"},
                    "geometry": {
                        "type": "array",
                        "items": _GEOMETRY_SPEC_SCHEMA,
                        "minItems": 1,
                    },
                    "constraints": {
                        "type": "array",
                        "items": _CONSTRAINT_SPEC_SCHEMA,
                        "description": "applied in the same transaction as the geometry",
                    },
                },
                ["sketch", "geometry"],
            ),
            "Add typed geometry; returns 0-based geo_ids. Geometry alone leaves the sketch "
            "under-constrained, which post-verify rolls back (geometry included) — send the "
            "constraints that pin it in the same call.",
        ),
        _sketch_method(
            "sketch_remove_geometry",
            sketches.sketch_remove_geometry,
            _sketch_schema(
                {
                    "sketch": {"type": "string"},
                    "geo_ids": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 0},
                        "minItems": 1,
                    },
                },
                ["sketch", "geo_ids"],
            ),
            "Remove sketch geometry by 0-based geo_id; FreeCAD drops its dependent constraints.",
        ),
        _sketch_method(
            "sketch_add_constraint",
            sketches.sketch_add_constraint,
            _sketch_schema(
                {
                    "sketch": {"type": "string"},
                    "constraints": {
                        "type": "array",
                        "items": _CONSTRAINT_SPEC_SCHEMA,
                        "minItems": 1,
                    },
                },
                ["sketch", "constraints"],
            ),
            "Add typed constraints; returns 1-based solver ids. A conflicting or malformed set "
            "rolls back with the offending ids named; redundant constraints warn only.",
        ),
        _sketch_method(
            "sketch_remove_constraint",
            sketches.sketch_remove_constraint,
            _sketch_schema(
                {
                    "sketch": {"type": "string"},
                    "constraints": {
                        "type": "array",
                        "items": _CONSTRAINT_REF_SCHEMA,
                        "minItems": 1,
                    },
                },
                ["sketch", "constraints"],
            ),
            "Remove constraints named by 1-based solver id or by name.",
        ),
        _sketch_method(
            "sketch_set_datum",
            sketches.sketch_set_datum,
            _sketch_schema(
                {
                    "sketch": {"type": "string"},
                    "constraint": _CONSTRAINT_REF_SCHEMA,
                    "value": _QUANTITY_SCHEMA,
                },
                ["sketch", "constraint", "value"],
            ),
            "Change a driving dimensional constraint's value; mm for lengths, deg for angles.",
        ),
        _sketch_method(
            "sketch_toggle_construction",
            sketches.sketch_toggle_construction,
            _sketch_schema(
                {
                    "sketch": {"type": "string"},
                    "geo_ids": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 0},
                        "minItems": 1,
                    },
                },
                ["sketch", "geo_ids"],
            ),
            "Toggle construction mode on the named 0-based sketch geometry.",
        ),
        _sketch_method(
            "sketch_add_external_geometry",
            sketches.sketch_add_external_geometry,
            _sketch_schema(
                {"sketch": {"type": "string"}, "edge": _SUBELEMENT_SELECTOR_SCHEMA},
                ["sketch", "edge"],
            ),
            "Project a model edge into a sketch as external geometry, addressed by a selector.",
        ),
    ]


def _feature_schema(properties, required):
    """A feature tool input schema: doc handle, the tool's own fields, and the confirm gate.

    ``confirm`` is not in ``required``: it is mandatory for a client, but a host running the
    operator auto-approve posture accepts a call without one, and the specs are built before the
    capability record is read. The gate's requirement is stated in ``_CONFIRM_SCHEMA`` instead.
    """
    return {
        "type": "object",
        "properties": {"doc": _DOC_SCHEMA, **properties, "confirm": _CONFIRM_SCHEMA},
        "required": ["doc", *required],
        "additionalProperties": False,
    }


def _feature_method(name, fn, schema, description):
    """A ``ToolSpec`` for a feature mutation use case.

    ``reversed`` is a wire field whose name shadows a builtin, so the handler forwards the raw
    keyword dict rather than binding it positionally.
    """

    def make(doc_registry, export_registry, caps, render_port):  # noqa: ARG001
        return lambda **p: fn(doc_registry, **p)

    return ToolSpec(
        name=name,
        make_handler=make,
        input_schema=schema,
        description=description,
        timeout_s=120.0,
        mutating=True,
    )


_EDGE_SELECTOR_LIST_SCHEMA = {
    "type": "array",
    "items": _SUBELEMENT_SELECTOR_SCHEMA,
    "minItems": 1,
    "description": "edges on the base feature; an edge FreeCAD would silently drop is rejected",
}
_FEATURE_NAME_SCHEMA = {
    "type": "string",
    "description": "intent-bearing feature name; becomes the Label and the object Name",
}
_EXTRUDE_PROPERTIES = {
    "body": {"type": "string", "description": "target PartDesign Body Name"},
    "profile": {"type": "string", "description": "sketch Name"},
    "name": _FEATURE_NAME_SCHEMA,
    "length": _QUANTITY_SCHEMA,
    "second_length": _QUANTITY_SCHEMA,
    "up_to": {"type": "string", "description": "extrude Type; validated against the live enum"},
    "up_to_face": _SUBELEMENT_SELECTOR_SCHEMA,
    "reversed": {"type": "boolean", "default": False},
    "midplane": {"type": "boolean", "default": False},
    "taper_angle": _QUANTITY_SCHEMA,
}


def _feature_specs():
    """The ``feature_*`` mutation specs, in catalog order."""
    return [
        _feature_method(
            "feature_pad",
            features.feature_pad,
            _feature_schema(_EXTRUDE_PROPERTIES, ["body", "profile", "name"]),
            "Pad a sketch profile into a Body. up_to defaults to 'Length', which requires a "
            "positive length; midplane straddles the profile plane instead of moving the solid.",
        ),
        _feature_method(
            "feature_pocket",
            features.feature_pocket,
            _feature_schema(_EXTRUDE_PROPERTIES, ["body", "profile", "name"]),
            "Cut a pocket from a sketch profile. up_to='ThroughAll' cuts the whole body; the "
            "value is checked against this build's live Pocket Type enumeration.",
        ),
        _feature_method(
            "feature_revolve",
            features.feature_revolve,
            _feature_schema(
                {
                    "body": {"type": "string"},
                    "profile": {"type": "string"},
                    "name": _FEATURE_NAME_SCHEMA,
                    "axis": {
                        **_SUBELEMENT_SELECTOR_SCHEMA,
                        "description": "the profile sketch's V_Axis/H_Axis/N_Axis, or an edge",
                    },
                    "angle": _QUANTITY_SCHEMA,
                    "second_angle": _QUANTITY_SCHEMA,
                    "up_to": {"type": "string"},
                    "reversed": {"type": "boolean", "default": False},
                    "midplane": {"type": "boolean", "default": False},
                },
                ["body", "profile", "name", "axis"],
            ),
            "Revolve a sketch profile about an axis. The axis sets ReferenceAxis, from which "
            "FreeCAD computes the read-only Base/Axis. Angles are in degrees.",
        ),
        _feature_method(
            "feature_hole",
            features.feature_hole,
            _feature_schema(
                {
                    "body": {"type": "string"},
                    "profile": {"type": "string"},
                    "name": _FEATURE_NAME_SCHEMA,
                    "diameter": _QUANTITY_SCHEMA,
                    "depth": _QUANTITY_SCHEMA,
                    "depth_type": {"type": "string", "description": "Dimension or ThroughAll"},
                    "thread_type": {"type": "string"},
                    "cut_type": {"type": "string"},
                    "cut_diameter": _QUANTITY_SCHEMA,
                    "cut_depth": _QUANTITY_SCHEMA,
                    "reversed": {"type": "boolean", "default": False},
                },
                ["body", "profile", "name"],
            ),
            "Drill a PartDesign Hole from a sketch profile. thread_type is applied first because "
            "FreeCAD re-populates the legal cut_type set from it.",
        ),
        _feature_method(
            "feature_fillet",
            features.feature_fillet,
            _feature_schema(
                {
                    "body": {"type": "string"},
                    "base": {"type": "string", "description": "feature carrying the edges"},
                    "name": _FEATURE_NAME_SCHEMA,
                    "edges": _EDGE_SELECTOR_LIST_SCHEMA,
                    "radius": _QUANTITY_SCHEMA,
                },
                ["body", "base", "name", "edges", "radius"],
            ),
            "Fillet named edges. An edge without exactly two adjacent faces, or whose faces meet "
            "tangentially, is rejected — FreeCAD would drop it and commit a smaller fillet.",
        ),
        _feature_method(
            "feature_chamfer",
            features.feature_chamfer,
            _feature_schema(
                {
                    "body": {"type": "string"},
                    "base": {"type": "string"},
                    "name": _FEATURE_NAME_SCHEMA,
                    "edges": _EDGE_SELECTOR_LIST_SCHEMA,
                    "size": _QUANTITY_SCHEMA,
                    "second_size": _QUANTITY_SCHEMA,
                    "angle": _QUANTITY_SCHEMA,
                    "chamfer_type": {"type": "string"},
                },
                ["body", "base", "name", "edges", "size"],
            ),
            "Chamfer named edges. chamfer_type is checked against the live enumeration; the same "
            "silent-drop edge check as feature_fillet applies.",
        ),
        _feature_method(
            "feature_pattern",
            features.feature_pattern,
            _feature_schema(
                {
                    "body": {"type": "string"},
                    "name": _FEATURE_NAME_SCHEMA,
                    "kind": {"enum": ["linear", "polar"]},
                    "originals": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "feature Names; defaults to the Body Tip",
                    },
                    "direction": _SUBELEMENT_SELECTOR_SCHEMA,
                    "axis": _SUBELEMENT_SELECTOR_SCHEMA,
                    "length": _QUANTITY_SCHEMA,
                    "angle": _QUANTITY_SCHEMA,
                    "occurrences": {"type": "integer", "minimum": 2},
                    "mode": {"type": "string"},
                    "reversed": {"type": "boolean", "default": False},
                },
                ["body", "name", "kind", "occurrences"],
            ),
            "Linear or polar pattern. occurrences counts the original. A polar pattern over a "
            "full turn steps by angle/occurrences, not angle/(occurrences-1).",
        ),
        _feature_method(
            "feature_mirror",
            features.feature_mirror,
            _feature_schema(
                {
                    "body": {"type": "string"},
                    "name": _FEATURE_NAME_SCHEMA,
                    "mirror_plane": _SUBELEMENT_SELECTOR_SCHEMA,
                    "originals": {"type": "array", "items": {"type": "string"}},
                },
                ["body", "name", "mirror_plane"],
            ),
            "Mirror features across a datum plane, base plane or planar face; originals default "
            "to the Body Tip.",
        ),
        _feature_method(
            "feature_datum",
            features.feature_datum,
            _feature_schema(
                {
                    "body": {"type": "string"},
                    "name": _FEATURE_NAME_SCHEMA,
                    "kind": {"enum": ["plane", "axis", "point", "cs"]},
                    "attachment": _SUBELEMENT_SELECTOR_SCHEMA,
                    "map_mode": {"type": "string", "default": "FlatFace"},
                    "offset": _QUANTITY_SCHEMA,
                },
                ["body", "name", "kind", "attachment"],
            ),
            "Create a datum plane/axis/point/coordinate system attached via AttachmentSupport "
            "and MapMode, offset along its local Z.",
        ),
        _feature_method(
            "feature_body_create",
            features.feature_body_create,
            _feature_schema(
                {"name": _FEATURE_NAME_SCHEMA},
                ["name"],
            ),
            "Create an empty PartDesign Body, the container every feature_* tool builds into. "
            "It holds no solid until a feature is added.",
        ),
        _feature_method(
            "feature_set_parameters",
            features.feature_set_parameters,
            _feature_schema(
                {
                    "feature": {"type": "string"},
                    "parameters": {
                        "type": "object",
                        "description": "property name -> Quantity, number, boolean or enum "
                        "string; validated against the live feature",
                    },
                },
                ["feature", "parameters"],
            ),
            "Edit a feature's driving properties and re-verify the solid in the same "
            "transaction. Unknown, read-only or wrong-unit values are rejected before it opens.",
        ),
    ]


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
_PREVIEW_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "doc": _DOC_SCHEMA,
        "operation": {
            "type": "object",
            "properties": {
                "tool": {
                    "type": "string",
                    "description": "a registered sketch_/feature_ mutation tool",
                },
                "args": {
                    "type": "object",
                    "description": "that tool's input, minus doc/confirm",
                },
            },
            "required": ["tool", "args"],
            "additionalProperties": False,
        },
        "render": {"enum": ["auto", "off"], "default": "auto"},
        "view": _SCREENSHOT_INPUT_SCHEMA["properties"]["view"],
    },
    "required": ["doc", "operation"],
    "additionalProperties": False,
}


def preview_op_table() -> dict:
    """The ``{tool name: use-case function}`` table ``preview_dry_run`` may run.

    Derived from the catalog's own ``sketch_*``/``feature_*`` spec lists intersected with the
    matching module-level use-case functions, so a tool registered without becoming previewable
    (or the reverse) is a mismatch the tests catch rather than a hand-maintained name list that
    drifts. ``debug_exec`` is excluded structurally: it is in neither spec list and carries
    neither name prefix.

    The entries are the bare use-case functions, not the wired handlers: the handlers close over
    the live registry, while the preview must supply its own document handle at call time.
    """
    table = {}
    for spec in (*_sketch_specs(), *_feature_specs()):
        module = sketches if spec.name.startswith("sketch_") else features
        fn = getattr(module, spec.name, None)
        if fn is not None:
            table[spec.name] = fn
    return table


def _preview_spec():
    """The ``preview_dry_run`` spec, closing over the op table built here.

    The table is built inside this factory rather than being threaded through
    ``HandlerFactory``: widening that signature would touch every other spec factory for one
    consumer.
    """
    op_table = preview_op_table()

    def make(doc_registry, export_registry, caps, render_port):  # noqa: ARG001
        return lambda **p: preview.preview_dry_run(doc_registry, op_table, render_port, **p)

    return ToolSpec(
        name="preview_dry_run",
        make_handler=make,
        input_schema=_PREVIEW_INPUT_SCHEMA,
        description="Run a proposed sketch_/feature_ mutation on a throwaway copy of the "
        "document and return a structured geometry diff plus a preview_id. The live "
        "document is never mutated.",
        timeout_s=180.0,
        mutating=False,
        audit_event="preview",
    )


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
            "document_undo",
            120.0,
            {
                "type": "object",
                "properties": {
                    "doc": _DOC_SCHEMA,
                    "expect_fingerprint": {
                        "type": ["string", "object"],
                        "description": "the pre-mutation fingerprint to compare the result "
                        "against; without it matches_pre_op is null. A digest string matches "
                        "byte-exactly. A whole FingerprintRecord also matches on the per-object "
                        "geometric invariants, which an op that consumed a shape as a profile "
                        "changes the serialization of without changing the geometry",
                    },
                },
                "required": ["doc"],
                "additionalProperties": False,
            },
            "Undo the last committed transaction, recompute, and report the before/after "
            "fingerprints. Refuses when the undo stack is empty or undo is unavailable; "
            "restoration is reported as a measured comparison, never assumed.",
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
        *_sketch_specs(),
        *_feature_specs(),
        _preview_spec(),
    ]


def build_inline_handlers(
    doc_registry: DocumentRegistry,
    export_registry: ExportRegistry,
    caps: Capabilities,
    marshal: Marshal | None,
    render_port: RenderPort | None = None,
    apply_posture: bool = True,
) -> MethodRegistry:
    """Build a ``MethodRegistry`` from the shared catalog.

    ``marshal`` given → each handler is wrapped in ``marshal.call`` (headless inline host).
    ``marshal`` is ``None`` → handlers call the use case directly (the listener owns the single
    ``marshal.call`` and a second layer would deadlock the Qt main thread). ``render_port``
    defaults to a fresh ``OffscreenRenderPort`` (the one render capability serves every host).

    With a ``marshal``, ``debug_exec`` alone gets an inner bounded marshal so its body runs on a
    worker thread and its budget is enforced; every other tool stays on the calling thread.

    The auto-approve posture is applied to the process here rather than closed into each mutation
    handler: it describes the host, not the tool, and the mutation use cases read it at the point
    they gate. ``apply_posture`` is False for a registry built as a component of another one (the
    read-only profile), because the posture belongs to the host that serves calls, not to every
    registry construction — a second build must never re-arm or disarm the gate for the first.
    """
    if apply_posture:
        confirm.set_auto_approve(auto_approve_enabled(caps))
    port = render_port if render_port is not None else OffscreenRenderPort()
    methods = MethodRegistry()
    bounded = Marshal(ThreadExecutor()) if marshal is not None else None

    def wrap(raw, timeout_s):
        if marshal is None:
            return raw

        def handler(**params):
            return marshal.call(lambda: raw(**params), timeout_s)

        return handler

    def bound_off_main_thread(raw, timeout_s):
        """Run ``raw`` on a worker thread, raising ``MarshalTimeout`` once the budget elapses."""
        if bounded is None:
            return raw

        def handler(**params):
            return bounded.call(lambda: raw(**params), timeout_s)

        return handler

    specs = list(tool_specs())
    if exec_registered(caps):
        specs.append(DEBUG_EXEC_SPEC)

    for spec in specs:
        raw = spec.make_handler(doc_registry, export_registry, caps, port)
        if spec.name == "debug_exec":
            raw = bound_off_main_thread(raw, spec.timeout_s)
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

    The auto-approve posture is not applied: this build is a means of wiring handlers, not a host
    taking over the process, and every mutation tool is filtered out of the result anyway.
    """
    full = build_inline_handlers(
        doc_registry, export_registry, caps, marshal, render_port, apply_posture=False
    )
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
