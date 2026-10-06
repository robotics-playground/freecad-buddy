---
title: MCP Tool Catalog Design — Phases 0–2
status: final
date: '2026-07-21'
ad-refs: [AD-1, AD-2, AD-4, AD-5, AD-6, AD-7, AD-8, AD-9, AD-10, AD-11, AD-12, AD-13, AD-17, AD-20]
sources:
  - ../ARCHITECTURE-SPINE.md
  - ../../../../specs/spec-freecad-buddy/phase-gates.md
  - ../../../research/technical-freecad-features-and-functionalities-research-2026-07-21.md
  - ../../../research/technical-sketch-dof-programmatic-query-research-2026-07-20.md
  - ../../../research/technical-geometry-to-spec-assertions-research-2026-07-20.md
  - ../../../research/technical-headless-preview-diff-channel-research-2026-07-20.md
  - ../../../research/technical-python-execution-sandbox-policy-research-2026-07-20.md
---

# MCP Tool Catalog Design — Phases 0–2

Implementation-ready catalog of the FreeCAD Buddy MCP tool surface for Phases 0–2. Tool names use the wire convention: underscore + namespace prefix (`query_`, `document_`, `export_`, `verify_`, `sketch_`, `feature_`, `preview_`, `debug_`); dot form is docs shorthand only (spine Consistency Conventions). All tool implementations live in `usecases/`, schemas and envelopes in `contracts/` (AD-1); identical implementations serve GUI (via RPC listener) and headless hosts (AD-2).

## 1. Cross-Cutting Contracts

### 1.1 Document handles (AD-20)

- Every tool input carries an explicit `doc` handle (opaque string, e.g. `"fcb-doc:7f3a…"`). `ActiveDocument` is never an implicit target.
- Only `document_create`, `document_open`, and `document_list` omit `doc` (they mint or enumerate handles).
- Documents open/close only through `document_*` tools — the harness included.
- Preview TempDocs use reserved prefix `FCB_TMP_`, are flagged transient, and are cleaned only by `preview_dry_run` (their creator).

### 1.2 Sub-element selectors (spine convention; AD-7, AD-13)

Model-level sub-elements (faces/edges) are addressed by selector objects — never stored bare indexed names:

```json
{ "$defs": {
  "Selector": { "oneOf": [
    { "type": "object", "properties": {
        "kind": { "const": "mapped_name" },
        "object": { "type": "string", "description": "immutable object Name" },
        "mapped_name": { "type": "string", "description": "TNP mapped element name" },
        "element_map_version": { "type": "integer" } },
      "required": ["kind", "object", "mapped_name", "element_map_version"] },
    { "type": "object", "properties": {
        "kind": { "const": "geometric" },
        "object": { "type": "string" },
        "element_type": { "enum": ["face", "edge", "vertex"] },
        "query": { "type": "object", "description": "geometric predicate: surface_type, radius{value,tol}, axis_dir, nearest_point…" },
        "expect": { "enum": ["one", "many"] } },
      "required": ["kind", "object", "query"] }
  ]},
  "Quantity": { "type": "object",
    "properties": { "value": { "type": "number" }, "unit": { "type": "string", "description": "explicit, e.g. mm, deg" } },
    "required": ["value", "unit"] }
}}
```

A caller-supplied bare `Face6` is resolved to a mapped name at call time and never persisted. Inside a sketch, geometry is addressed by sketch-local `geo_id` (returned by `sketch_add_geometry`) — sketch geo ids are solver-stable and not TNP-exposed.

### 1.3 Result envelope & error surface (AD-17)

Every tool returns the contracts-owned `ResultEnvelope` as MCP `structuredContent` validated by its per-tool `outputSchema`, plus a human-readable `text` summary in `content` (spine convention "Tool results"). The `text` field is a per-tool one-line summary of `structured_content` — counts, headline values, and error flags (e.g. `"201 objects, 4 shown."`, `"Body 'pcb': volume 8642.85 mm³, 15 faces."`) — never a JSON re-dump; a tool without a bespoke summary falls back to a compact `key: value` flattening (`summary_text`). No namespace defines a variant envelope.

The envelope shape is contracts-owned (`fcb.result-envelope/1`, see data-contracts-design.md §4) — this catalog consumes it, never redefines it:

```json
{ "$defs": { "ResultEnvelope": {
  "type": "object",
  "properties": {
    "schema": { "const": "fcb.result-envelope/1" },
    "status": { "enum": ["OK", "SPEC_FAILED", "RECOMPUTE_ERROR", "TIMEOUT", "OOM_KILLED", "WORKER_CRASHED", "INVALID_INPUT"] },
    "detail": { "type": ["object", "null"], "description": "ErrorDetail — machine code + required human message on non-OK; constraint diagnostics as {solver_id (1-based), name} per Constraints[id-1]" },
    "structured_content": { "type": "object", "description": "tool-specific payload, per-tool schema below (called `result` in §3 fragments); echoes the doc handle (AD-20)" },
    "text": { "type": "string", "description": "per-tool one-line human summary of structured_content (counts/headline/error flags); never a JSON re-dump" },
    "images": { "type": "array", "description": "ImageRef[], capability-gated (AD-10)" }
  },
  "required": ["status", "structured_content", "text"]
}}}
```

- The status set is closed (AD-17); Phase 0–2 use-case outcomes emit `OK | SPEC_FAILED | RECOMPUTE_ERROR | INVALID_INPUT`; the transport layer additionally emits `TIMEOUT` (marshal timeout) and `WORKER_CRASHED` (RPC listener unreachable) from Phase 0 — see integration-mcp-freecad.md §7; `OOM_KILLED` is reserved vocabulary with no producer. The schema binds from Phase 0.
- Verification payloads reuse the contracts `ValidationReport` shape with its banner (FreeCAD version, `ElementMapVersion`, validator sensitivity where citable).
- Renders follow AD-10 budgets: ≤1920 px, `audience:["user"]`, `resource_link` preferred over inline base64.

### 1.4 Mutation protocol fields (AD-5, AD-6, AD-7)

Every mutation tool (column **Mut** = yes below) executes the AD-5 bracket (geohash snapshot → `openTransaction` → typed op → `recompute()` → post-verify → commit; on failure abort + re-hash-proven rollback) and returns a common `mutation` block inside `result`:

```json
{ "mutation": {
  "schema": "fcb.mutation/2",
  "transaction_id": "string",
  "fingerprint_before": { "digest": "sha256…", "serializer": "exportBinary|exportBrep" },
  "fingerprint_after":  { "digest": "…", "serializer": "…" },
  "changed": [ { "name": "Pocket003", "volume": 47120.4, "area": 46010.2, "com": [55.2, 67.1, 19.3] } ],
  "post_verify": { "recompute_clean": true, "is_valid": true,
                   "fully_constrained": true,
                   "tnp_audit": { "status": "CLEAN|FLAGGED|UNSUPPORTED", "element_map_version": "string",
                                  "counts": { "PASS": 42 }, "findings": [] } },
  "rolled_back": false, "rollback_proven": null
}}
```

Fingerprints carry their serializer tag; cross-tag comparison is banned (AD-6). `tnp_audit` reports `UNSUPPORTED`, never clean, when the element map probe fails (AD-7, AD-11). From Phase 2, mutation tools additionally accept an optional `confirm` object (§4.8) tying execution to a `preview_dry_run` + elicitation acceptance (AD-10); headless without confirmation is fail-closed unless `autoApprove` is set, and every auto-approval is audit-logged.

**Lifecycle ops** (`document_save`, `document_close`, `document_recompute`, `document_undo`) change document state but carry no new geometric intent: they are audit-logged and serialized with the single-writer rule (AD-20) but are exempt from the preview/confirm gate. `document_undo` is verified by fingerprint comparison (AD-6; gate G2.3). A `feature_set_parameters` call that writes only `Visibility` is display state: it runs the AD-5 bracket and is audit-logged, but is confirm-exempt. A call that also writes any other property keeps the gate.

## 2. Tool Inventory

**Mut** = mutates the target document (drives AD-5 protocol + Phase 2 confirm gate). *(L)* = lifecycle op, confirm-exempt per §1.4.

**Shipped** = present in `hosts/tool_catalog.py:tool_specs()` today. **planned** = specified here, not yet registered — a planned row is a design commitment, never evidence of a shipped tool. `tool_specs()` is the authority: if this table and that function disagree, the function wins and this table is the bug (AD-4 makes the typed tool list the entire AI mutation surface, so an unlisted shipped tool is an inventory defect).

### `document_` — lifecycle & targeting (AD-20)

| Tool | Phase | Purpose | Mut |
| --- | --- | --- | --- |
| `document_create` | 0 | Create a new document; mint and return its handle | yes *(L)* |
| `document_open` | 0 | Open an `.FCStd` file; return handle | yes *(L)* |
| `document_save` | 0 | Save / save-as by handle | yes *(L)* |
| `document_close` | 0 | Close by handle; releases handle | yes *(L)* |
| `document_list` | 0 | List open documents with handles, labels, transient flags | no |
| `document_recompute` | 0 | Full recompute; report touched objects + per-object error states | yes *(L)* |
| `document_undo` | 2 | Bridge-owned undo of the last committed transaction; fingerprint-verified (G2.3) | yes *(L)* |
| `document_object_delete` | 2 | Delete an object (and report orphaned dependents) under AD-5 — **planned** | yes |

### `query_` — read-only introspection (zero mutation; Phase 1 assistant surface, G1.6)

| Tool | Phase | Purpose | Mut |
| --- | --- | --- | --- |
| `query_tree_summary` | 0 | Bounded, summarized feature-tree overview (G1.3 large-tree safe) | no |
| `query_object` | 0 | One object: type, label, properties, error state + `getStatusString()` | no |
| `query_mass_properties` | 0 | Volume/area/bbox/COM/inertia + topology counts for an object | no |
| `query_dependencies` | 0 | `InList`/`OutList` dependency edges for object or whole doc (whole-doc `edges` capped at `max_edges`, truncation flagged) | no |
| `query_sketch_info` | 0 | Sketch geometry + constraint listing (types, names, values, driving flags) | no |
| `query_placement` | 0 | Local + global placement of an object | no |
| `query_capabilities` | 0 | Runtime capability probes (AD-11): FreeCAD version, `ElementMapVersion`, element-map availability, render capability, `debug_exec` state | no |
| `query_screenshot` | 0 | Capability-gated render to PNG (`resource_link`, ≤1920 px) with **view control**: include/exclude objects, per-object transparency/color override, focus-on-element camera framing, highlight (§3.9). Constructed-scene render — never mutates document or user viewport; renders a document with a pending/broken recompute (`render.dirty_document: true`) rather than hard-failing. Reports unavailable when no GL — never fails hard | no |
| `query_tree_children` | 1 | Paged expansion of a single node's children (offset/limit within one level); `query_tree_summary` owns depth/root/filter navigation — **planned** | no |
| `query_parameters` | 1 | Driving dimensions / VarSet-or-Spreadsheet parameters and expressions (shim façade, AD-11) — **planned** | no |

### `export_` — artifact output (AD-9: each pairs with its `verify_export_*`)

| Tool | Phase | Purpose | Mut |
| --- | --- | --- | --- |
| `export_step` | 0 | Write STEP AP214/AP242, `write.step.unit=MM` pinned per call | no |
| `export_stl` | 0 | Write STL via `MeshPart.meshFromShape` (linear + angular deflection) | no |
| `export_3mf` | 0 | Write 3MF from the same single tessellation source as STL | no |

### `verify_` — deterministic verification (read-only; AD-13: never the producing agent)

| Tool | Phase | Purpose | Mut |
| --- | --- | --- | --- |
| `verify_shape` | 0 | Measure a shape against the closed assertion vocabulary in a declared anchor frame (G0.3 golden models; §7.2 primitives for G3) | no |
| `verify_recompute` | 0 | Assert no object left in error state after recompute | no |
| `verify_sketch` | 0 | AD-8 pass signal: `FullyConstrained` + DoF + solver diagnostics (used by G2.5) | no |
| `verify_fingerprint` | 0 | Compute/compare AD-6 document fingerprint (undo proof, G2.3) — **planned**; `usecases/fingerprint.py` exists and is called internally, but no `verify_fingerprint` tool is registered | no |
| `verify_export_step` | 0 | Re-import STEP; volume ±0.1 %, `isValid`, topology counts equal (G0.5) | no |
| `verify_export_stl` | 0 | trimesh + second oracle (admesh or Phase 0 fallback); disagreement = fail | no |
| `verify_export_3mf` | 0 | lib3mf + trimesh + FreeCAD self-read (self-read leg via RPC) | no |
| `verify_references` | 2 | Standalone TNP reference audit (AD-7 Layers 0–2) between mutations — **planned**; the audit runs inside AD-5 today (`usecases/tnp_guard.py`), just not as a standalone tool | no |

### `sketch_` — sketch mutations (Phase 2; AI mutation path per AD-4)

| Tool | Phase | Purpose | Mut |
| --- | --- | --- | --- |
| `sketch_create` | 2 | New sketch on base plane / datum / planar-face selector | yes |
| `sketch_add_geometry` | 2 | Add typed geometry (line/arc/circle/point…); returns `geo_id`s | yes |
| `sketch_remove_geometry` | 2 | Remove geometry by `geo_id` | yes |
| `sketch_add_constraint` | 2 | Add typed constraints; returns 1-based ids + post-solve state | yes |
| `sketch_remove_constraint` | 2 | Remove constraint by id/name | yes |
| `sketch_set_datum` | 2 | Change a dimensional constraint value | yes |
| `sketch_toggle_construction` | 2 | Toggle construction mode on geometry | yes |
| `sketch_add_external_geometry` | 2 | Project model edge into sketch (selector-addressed; TNP-audited) | yes |

### `feature_` — solid features (Phase 2; intent-bearing names per spine convention)

| Tool | Phase | Purpose | Mut |
| --- | --- | --- | --- |
| `feature_body_create` | 2 | Create a PartDesign Body — the container every later `feature_*` targets | yes |
| `feature_pad` | 2 | Pad a sketch profile | yes |
| `feature_pocket` | 2 | Pocket from a sketch profile | yes |
| `feature_revolve` | 2 | Revolution from profile + axis | yes |
| `feature_hole` | 2 | PartDesign Hole (thread metadata is hint-only for verification) | yes |
| `feature_fillet` | 2 | Fillet selected edges (selector objects) | yes |
| `feature_chamfer` | 2 | Chamfer selected edges | yes |
| `feature_pattern` | 2 | Linear/polar pattern of features | yes |
| `feature_mirror` | 2 | Mirror features across plane/datum | yes |
| `feature_datum` | 2 | Create datum plane/axis/point/CS (TNP-defensive referencing) | yes |
| `feature_set_parameters` | 2 | Edit feature properties / driving dimensions (parameter-editability path) | yes |

### `preview_` — dry-run channel (AD-10)

| Tool | Phase | Purpose | Mut |
| --- | --- | --- | --- |
| `preview_dry_run` | 2 | Execute proposed op on `FCB_TMP_` copy-doc; return structured diff + optional render; no live-doc mutation | no |

### `debug_` — operator-only (AD-4; never an AI surface)

| Tool | Phase | Purpose | Mut |
| --- | --- | --- | --- |
| `debug_exec` | 0 | Trusted-operator Python exec for bring-up/CI-authored scripts; see §5 | yes |

### Counts & G0.2

Specified vs shipped. "Shipped" = returned by `hosts/tool_catalog.py:tool_specs()`.

| Namespace | P0 | P1 | P2 | P3 | Specified | Shipped |
| --- | --- | --- | --- | --- | --- | --- |
| `document_` | 6 | — | 2 | — | 8 | 7 (`document_object_delete` planned) |
| `query_` | 8 | 2 | — | — | 10 | 8 (`query_tree_children`, `query_parameters` planned) |
| `export_` | 3 | — | — | — | 3 | 3 |
| `verify_` | 7 | — | 1 | — | 8 | 6 (`verify_fingerprint`, `verify_references` planned) |
| `sketch_` | — | — | 8 | — | 8 | 8 |
| `feature_` | — | — | 11 | — | 11 | 11 |
| `preview_` | — | — | 1 | — | 1 | 1 |
| `view_` | — | — | — | — | 1 | 1 |
| **AI-visible total** | | | | | **50** | **45** |
| `debug_` (operator-only) | 1 | — | — | — | 1 | 1 |

**G0.2 satisfied:** Phase 0 = **17** tools across `query_`/`document_`/`export_` (8+6+3) — ≥15 on the gate's literal namespace set; **24 AI-visible** including `verify_`, plus operator-only `debug_exec` (unregistered by default, never counted in the AI-visible registry) = 25 registered specs at P0. Every tool ships JSON `inputSchema` + `outputSchema` + docstring (G0.2 pass rule).

The five planned tools are Phase 1/2 scope and their absence is expected at this point in the build; they are listed so the table cannot be misread as a shipped inventory. `tool_specs()` returns **45**; with `DEBUG_EXEC_SPEC` that is 46 registered specs.

Not in this table, by design: the `internal=True` RPC-only methods (`export_self_read_stl`, `export_self_read_3mf`). They carry the `export_` prefix and exist because the mesh oracles live outside FreeCAD (AD-9/AD-12), but they are never MCP tools and never reach the AI surface (spine Conventions, "Internal RPC methods").

## 3. Load-Bearing Tool Schemas

Fragments show `result` payloads; each is wrapped in the `ResultEnvelope` (§1.3). `$defs` from §1.2 apply.

### 3.1 `document_create`

```json
{ "inputSchema": { "type": "object", "properties": {
    "label": { "type": "string" },
    "path": { "type": "string", "description": "optional .FCStd save target" }
  }, "required": ["label"] },
  "outputSchema-result": { "type": "object", "properties": {
    "doc": { "type": "string", "description": "opaque handle — required by every subsequent call (AD-20)" },
    "name": { "type": "string", "description": "immutable FreeCAD document Name" },
    "label": { "type": "string", "description": "with a path: the file stem, as FreeCAD's saveAs sets it" },
    "path": { "type": "string", "description": "with a path: the file written (FreeCAD appends .FCStd when missing)" },
    "fingerprint": { "$ref": "#/$defs/Fingerprint", "description": "empty-doc baseline (AD-6)" }
  }, "required": ["doc", "name"] } }
```

A save target is checked before FreeCAD writes. A directory, a missing parent folder, and an existing read-only file each return `INVALID_INPUT` naming the path; a refused call opens no document. `document_save` with a `path` follows the same rules and reports the resulting `label` and `path` too.

### 3.2 `query_tree_summary`

Depth-bounded, filterable, nested tree walk (G1.3 context-overflow guard by explore-then-expand, not a flat node cap). `depth` expands N levels from the document roots (or from `root`); at the depth boundary a node reports only its counts. Children are partitioned into structural `children` and `App::Link` instance `links`. `filters` AND-stacks; `exclude_types` defaults to the datum/origin clutter set. A node that fails `types`, `name_pattern` or `renderable_only` is dropped, and its matching descendants, searched at any depth, take its place, each `Name` once. A node that fails `visible_only` or `exclude_types` drops its whole subtree, and a failing `App::Link` hoists nothing. Nodes are sparse — a field appears only when it carries a value; `name`/`label`/`type`/`visibility` are always present.

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "depth": { "type": "integer", "default": 1, "minimum": 1, "description": "levels to expand; 1 = top containers only" },
    "root": { "type": "string", "description": "expand the subtree under this object instead of the document roots" },
    "filters": { "type": "object", "additionalProperties": false, "properties": {
      "types": { "type": "array", "items": { "type": "string" } },
      "exclude_types": { "type": "array", "items": { "type": "string" }, "description": "defaults to App::Plane/Line/Point/Origin" },
      "renderable_only": { "type": "boolean" },
      "visible_only": { "type": "boolean" },
      "name_pattern": { "type": "string" }
    } }
  }, "required": ["doc"] },
  "outputSchema-result": { "type": "object", "properties": {
    "doc": { "type": "string" }, "total_objects": { "type": "integer" },
    "returned_nodes": { "type": "integer", "description": "emitted node count after depth + filter" },
    "depth": { "type": "integer" }, "filters_applied": { "type": "object" },
    "tree": { "type": "array", "items": { "type": "object", "properties": {
      "name": { "type": "string" }, "label": { "type": "string" },
      "type": { "type": "string", "description": "e.g. PartDesign::Pad" },
      "visibility": { "type": "boolean" },
      "error": { "type": "string", "description": "getStatusString() — present only when in error state" },
      "children_count": { "type": "integer", "description": "present only when non-zero" },
      "children": { "type": "array", "description": "structural children; present only when expanded and non-empty" },
      "links_count": { "type": "integer", "description": "App::Link children; present only when non-zero" },
      "links": { "type": "array", "description": "App::Link instances; present only when expanded and non-empty" }
    }, "required": ["name", "label", "type", "visibility"] } }
  }, "required": ["doc", "total_objects", "returned_nodes", "depth", "tree"] } }
```

### 3.2.1 `query_dependencies`

Dependency links by immutable `Name`. With `object` → `{object, in_list, out_list}` from `InList`/`OutList` (unbounded; per-object edge sets are small). Without `object` → the whole-doc `edges` array over every object's `OutList`, kept in document/`OutList` order and capped at `max_edges`: the first `max_edges` edges are returned, `total_edges` is the full count, `returned_edges` is `min(total_edges, max_edges)`, and `truncated` is set when the full count exceeds the cap. A consumer that hits the cap scopes down via per-object mode (this is a forward cap, not an offset/limit cursor — `query_tree_children` owns paging). `max_edges < 1` → `INVALID_INPUT`.

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "object": { "type": "string", "description": "immutable Name; omit = whole-document edges" },
    "max_edges": { "type": "integer", "minimum": 1, "default": 2000, "description": "whole-doc edge cap; ignored in per-object mode" }
  }, "required": ["doc"] },
  "outputSchema-per-object": { "type": "object", "properties": {
    "object": { "type": "string" },
    "in_list": { "type": "array", "items": { "type": "string" } },
    "out_list": { "type": "array", "items": { "type": "string" } }
  }, "required": ["object", "in_list", "out_list"] },
  "outputSchema-whole-doc": { "type": "object", "properties": {
    "edges": { "type": "array", "items": { "type": "object", "properties": {
      "from": { "type": "string" }, "to": { "type": "string" } }, "required": ["from", "to"] },
      "description": "first max_edges OutList edges in document order" },
    "total_edges": { "type": "integer", "description": "full OutList edge count before the cap" },
    "returned_edges": { "type": "integer", "description": "min(total_edges, max_edges)" },
    "truncated": { "type": "boolean", "description": "true when total_edges > max_edges" }
  }, "required": ["edges", "total_edges", "returned_edges", "truncated"] } }
```

### 3.3 `verify_shape`

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "object": { "type": "string", "description": "immutable Name; omit = the document's first object" },
    "checks": { "type": "array", "items": { "type": "object" },
      "description": "{fn, expect, tol?, select?, select_a?, select_b?, direction?}; omit = measurement-only report" },
    "anchor_frame": { "type": "object", "properties": {
      "kind": { "enum": ["base_sketch_plane", "largest_planar_face", "named_datum"] },
      "ref": { "type": ["string", "null"], "description": "object Name, else unique Label; null for largest_planar_face" }
    }, "required": ["kind"], "additionalProperties": false,
      "description": "omit = global frame" }
  }, "required": ["doc"], "additionalProperties": false },
  "result": "ValidationReport (AD-17): one Check {id, measured, expected, tolerance, passed, detail} per entry; banner.anchor_frame records the resolved frame" }
```

**Vocabulary.** `fn` is closed: the eleven `verification-design.md` §7.2 primitives
(`is_valid_solid`, `count_cylindrical_holes`, `hole_diameter`, `hole_position`, `hole_spacing`,
`hole_through`, `distance_between`, `angle_between`, `expect_bbox`, `expect_extent`,
`expect_volume`), named in `contracts.ASSERTION_FNS` and measured by `usecases/assertions.py`, plus
`expect_solid_count`, `expect_valid` and `expect_watertight`. A §7.2 check id is `assert.<fn>`.
Selector, `hole_diameter` and empty-match semantics follow `benchmarks/g3/README.md` §Assertion
vocabulary. `expect_bbox` compares sorted extents measured in the frame; `expect_extent` measures
along one frame `direction`.

**Anchor frame.** `base_sketch_plane` and `named_datum` resolve `ref` to that object's global
placement. `largest_planar_face` takes the largest planar face (ties: lowest centroid Z, then
lowest mapped name; without mapped names, lowest centroid X, then Y), with its origin at the face
centroid, +Z from the face into the part, and in-plane X along document X projected onto the face
(document Y when that projection is degenerate). The shape is measured in document coordinates.

**Failures.** An unknown `fn`, a key the `fn` does not take, a sub-element index selector
(`Face6`), a wrong `expect` arity or a malformed `anchor_frame` raises `ValidationError` →
envelope `INVALID_INPUT`. A selector that matches nothing, or a frame that does not resolve, fails
that check with `detail.code = invalid_input.unsupported_assertion` (verdict `INVALID_INPUT`);
checks that do not need the frame are still measured. Any other failed check → `SPEC_FAILED`.
Tolerances default to linear ±0.05 mm, angle ±0.1°, volume ±1 %, and are never tighter than
`Shape.getTolerance` (spine numeric-tolerance convention).

### 3.4 `verify_sketch` (shape per DoF research §5; AD-8)

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" }, "sketch": { "type": "string", "description": "sketch object Name" }
  }, "required": ["doc", "sketch"] },
  "outputSchema-result": { "type": "object", "properties": {
    "dof": { "type": "integer" },
    "fully_constrained": { "type": "boolean", "description": "FullyConstrained when solve() returned 0, else false; PASS rule in verification-design.md §4.2 (AD-8)" },
    "geometry_count": { "type": "integer" }, "constraint_count": { "type": "integer" },
    "conflicting": { "type": "array", "items": { "$ref": "#/$defs/ConstraintRef" } },
    "redundant": { "type": "array", "items": { "$ref": "#/$defs/ConstraintRef" }, "description": "non-empty is a HARD FAIL, as in FreeCAD (AD-8)" },
    "partially_redundant": { "type": "array", "items": { "$ref": "#/$defs/ConstraintRef" }, "description": "WARN only, never FAIL (AD-8)" },
    "malformed": { "type": "array", "items": { "$ref": "#/$defs/ConstraintRef" } },
    "degenerate_geometry_count": { "type": "integer" },
    "open_vertices": { "type": "integer" },
    "under_constrained_elements": { "type": "array", "description": "(geo_id, pos_id) pairs from getGeometryWithDependentParameters — repair-loop input" },
    "solver_status_code": { "type": "integer", "description": "must be 0 to PASS; never a DoF signal (AD-8)" },
    "verdict": { "enum": ["PASS", "FAIL", "WARN"] }
  }, "required": ["dof", "fully_constrained", "verdict"] } }
```

`ConstraintRef` = `{ "id": 1-based solver id, "name": Constraints[id-1].Name, "type": constraint type }` (spine error convention). Tool recomputes before reading; never infers DoF from `solve() == 0`.

### 3.5 `export_step` + `verify_export_step` (AD-9 pair)

```json
{ "export_step.inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "objects": { "type": "array", "items": { "type": "string" }, "description": "object Names; omit = all visible solids" },
    "path": { "type": "string" },
    "ap": { "enum": ["AP214", "AP242"], "default": "AP242" },
    "unit": { "const": "MM", "description": "pinned per call — ambient defaults never trusted (AD-9)" }
  }, "required": ["doc", "path"] },
  "export_step.outputSchema-result": { "type": "object", "properties": {
    "export_id": { "type": "string" }, "path": { "type": "string" }, "bytes": { "type": "integer" },
    "verified": { "const": false, "description": "export completes ONLY via verify_export_step (AD-9)" }
  }, "required": ["export_id", "path", "verified"] } }
```

```json
{ "verify_export_step.inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string", "description": "source document (AD-20)" },
    "export_id": { "type": "string", "description": "from export_step; binds the pair" }
  }, "required": ["doc", "export_id"] },
  "verify_export_step.outputSchema-result": { "type": "object", "properties": {
    "reimport": { "type": "object", "properties": {
      "volume_rel_error": { "type": "number", "description": "pass ≤ 0.001 (±0.1 %)" },
      "is_valid": { "type": "boolean" },
      "topology_counts_equal": { "type": "boolean" } } },
    "verdict": { "enum": ["PASS", "FAIL"] },
    "banner": { "type": "object" }
  }, "required": ["reimport", "verdict"] } }
```

`verify_export_stl`/`verify_export_3mf` share this pair shape; their oracle blocks list per-oracle results (trimesh + second oracle; lib3mf + trimesh + FreeCAD self-read) and any independent-oracle disagreement forces `verdict: "FAIL"`; mesh volume tolerance derives from the deflection used at tessellation, never ±0.1 % (AD-9). Oracles run in the external process; the FreeCAD self-read leg runs in-FreeCAD via RPC (AD-9, AD-12).

### 3.6 `sketch_add_constraint`

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" }, "sketch": { "type": "string" },
    "constraints": { "type": "array", "items": { "type": "object", "properties": {
      "type": { "enum": ["Coincident", "Horizontal", "Vertical", "Parallel", "Perpendicular", "Tangent", "Equal", "Symmetric", "PointOnObject", "Block", "Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"] },
      "first": { "type": "integer", "description": "sketch geo_id (from sketch_add_geometry)" },
      "first_pos": { "type": "integer", "description": "PointPos: 0 none, 1 start, 2 end, 3 mid" },
      "second": { "type": "integer", "description": "omit for single-point DistanceX/DistanceY (first, first_pos, value)" }, "second_pos": { "type": "integer", "description": "requires second" },
      "third": { "type": "integer" }, "third_pos": { "type": "integer" },
      "value": { "$ref": "#/$defs/Quantity", "description": "dimensional constraints only" },
      "name": { "type": "string", "description": "intent-bearing constraint name" },
      "driving": { "type": "boolean", "default": true }
    }, "required": ["type", "first"] } },
    "confirm": { "$ref": "#/$defs/Confirm" }
  }, "required": ["doc", "sketch", "constraints"] },
  "outputSchema-result": { "type": "object", "properties": {
    "constraint_ids": { "type": "array", "items": { "type": "integer" }, "description": "1-based" },
    "sketch_state": { "type": "object", "description": "embedded verify_sketch summary post-op (dof, fully_constrained, diagnostics)" },
    "mutation": { "$ref": "#/$defs/MutationBlock" }
  }, "required": ["constraint_ids", "sketch_state", "mutation"] } }
```

If the added constraints make the sketch conflicting, malformed or fully redundant, FreeCAD marks the sketch in error, AD-5 post-verify step 1 fails → automatic proven rollback, envelope `status: "RECOMPUTE_ERROR"` with FreeCAD's status string, which names the offending constraints, in the explanation. A sketch that solves but is not fully constrained fails post-verify step 3 → rollback with `status: "SPEC_FAILED"`.

`sketch_add_geometry` places a `point` from `start` or `center`; giving both is `INVALID_INPUT`.

### 3.7 `feature_pad`

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "body": { "type": "string", "description": "target PartDesign Body Name" },
    "profile": { "type": "string", "description": "sketch Name" },
    "length": { "$ref": "#/$defs/Quantity" },
    "second_length": { "$ref": "#/$defs/Quantity", "description": "second side, opposite the first; sets SideType 'Two sides', Type2 'Length', Length2" },
    "reversed": { "type": "boolean", "default": false },
    "midplane": { "type": "boolean", "default": false },
    "up_to": { "type": "string", "default": "Length", "description": "extrude Type, checked against the live enumeration (Pad: Length, UpToLast, UpToFirst, UpToFace, UpToShape; Pocket has ThroughAll in place of UpToLast)" },
    "up_to_face": { "$ref": "#/$defs/Selector" },
    "name": { "type": "string", "description": "intent-bearing feature name (tree reads like a build plan)" },
    "confirm": { "$ref": "#/$defs/Confirm" }
  }, "required": ["doc", "body", "profile", "name"] },
  "outputSchema-result": { "type": "object", "properties": {
    "feature": { "type": "string", "description": "created feature Name" },
    "shape_summary": { "type": "object", "description": "post-op volume/bbox/counts" },
    "mutation": { "$ref": "#/$defs/MutationBlock" }
  }, "required": ["feature", "mutation"] } }
```

All `feature_*` tools follow this shape: selectors for sub-element references, `Quantity` for every dimension, mandatory intent-bearing `name`, common `mutation` block.

Refusals that every `feature_*` tool returns as `INVALID_INPUT` before the bracket opens (AD-17):

- `feature_pad` / `feature_pocket`: `second_length` together with `midplane: true`; `up_to: "TwoLengths"` (or its `"?TwoLengths"` spelling), which FreeCAD 1.1 keeps only as a tombstone member — the message names `second_length` as the replacement.
- `feature_set_parameters`: a value outside the property's type family — a `Quantity` or number for a quantity property, a number for a unitless float property, an integer for an integer property, a boolean for `App::PropertyBool`, a member string for `App::PropertyEnumeration`. Any other property type (for example `Part::PropertyPartShape`) is refused. The message names `<feature>.<prop>` and its type.
- `feature_fillet` / `feature_chamfer`: a `base` that is not the Body's `Tip`; the message names the Tip. The dress-up builds from its base alone, so a base below the Tip would drop every later feature. FreeCAD's GUI allows this; the bridge refuses it.

### 3.8 `preview_dry_run` (AD-10)

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string", "description": "live document (never mutated by this tool)" },
    "operation": { "type": "object", "properties": {
      "tool": { "type": "string", "description": "any registered sketch_/feature_/document_object_delete mutation tool" },
      "args": { "type": "object", "description": "that tool's input, minus doc/confirm" }
    }, "required": ["tool", "args"] },
    "render": { "enum": ["auto", "off"], "default": "auto", "description": "capability-gated (GUI saveImage / Xvfb / omit)" }
  }, "required": ["doc", "operation"] },
  "outputSchema-result": { "type": "object", "properties": {
    "preview_id": { "type": "string", "description": "pass back as confirm.preview_id on apply" },
    "diff": { "type": "object", "properties": {
      "volume_delta": { "$ref": "#/$defs/Quantity" }, "area_delta": { "$ref": "#/$defs/Quantity" },
      "bbox_before": {}, "bbox_after": {}, "com_shift": { "$ref": "#/$defs/Quantity" },
      "counts_delta": { "type": "object", "properties": { "faces": {}, "edges": {}, "solids": {} } },
      "nodes": { "type": "object", "properties": { "touched": { "type": "array" }, "new": { "type": "array" }, "deleted": { "type": "array" } } },
      "validity": { "type": "object", "properties": { "is_valid": { "type": "boolean" }, "recompute_clean": { "type": "boolean" }, "recompute_log": { "type": "array" } } },
      "tnp_precheck": { "type": "object", "description": "AD-7-style re-resolve check on the copy" }
    }, "required": ["volume_delta", "bbox_after", "counts_delta", "nodes", "validity", "tnp_precheck"],
       "description": "mandatory payload — confirmation never waits on pixels (AD-10)" },
    "renders": { "type": "array", "items": { "type": "object", "properties": {
      "kind": { "enum": ["before", "after"] },
      "resource_link": { "type": "string", "description": "preferred; ≤1920 px, audience:[user]" } } },
      "description": "optional, capability-gated" },
    "expires_at": { "type": "string", "description": "TempDoc + preview_id lifetime; TempDoc prefix FCB_TMP_, cleaned by this tool (AD-20)" }
  }, "required": ["preview_id", "diff"] } }
```

Field list of `diff` is the Phase 2 UX-locked schema (spine Deferred) — it must reuse the contracts-owned audit-record vocabulary; the fragment above is the design baseline for that lock. `preview_dry_run` also accepts an optional `view` object (§3.9) passed through to its before/after renders — e.g. focus the camera on the edge being filleted.

### 3.9 `query_screenshot` — view-controlled render

The agent (or the human it serves) reduces visual noise by **composing the scene**, not by mutating the model: the render path builds its own Coin scene graph per call (integration-mcp-freecad.md §6), so nothing here touches `Visibility` properties, the document, or the user's live viewport. Non-mutating by construction; registered in the Phase 1 read-only profile.

A document with a pending or broken recompute (a `Touched`/`Invalid`/`Error` object) is self-unstable — reading `.Shape` while fingerprinting re-triggers the failing recompute, so the render's before==after mutation guard cannot distinguish a render mutation from that pre-existing churn. When the document is dirty the guard is skipped and the render proceeds with `render.dirty_document: true`; a clean document keeps the strict read-only assertion. A broken object with a null shape is signalled by `obj.State`, not a mass-property diff.

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "view": { "type": "object", "properties": {
      "include": { "type": "array", "items": { "type": "string" },
                   "description": "object Names to render; omit = the default set: every visible object with a non-null shape, visible sketches and meshes with facets included, Bodies and datums left out. A Body name draws its Tip and is reported under the Body name; a Body with no Tip draws nothing" },
      "exclude": { "type": "array", "items": { "type": "string" },
                   "description": "object Names dropped from the scene (hide = not added)" },
      "styles": { "type": "array", "items": { "type": "object", "properties": {
        "object": { "type": "string" },
        "transparency": { "type": "integer", "minimum": 0, "maximum": 100,
                          "description": "material override on this object's subgraph" },
        "color": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 }
      }, "required": ["object"] },
        "description": "de-emphasize context parts (e.g. transparency 80) so the subject reads clearly" },
      "focus": { "$ref": "#/$defs/Selector",
                 "description": "camera frames this sub-element's bbox (+margin) instead of the whole scene; falls back to whole-object when the selector names an object only" },
      "highlight": { "$ref": "#/$defs/Selector",
                     "description": "accent-color the target element (distinct override material)" },
      "camera": { "enum": ["iso", "front", "top", "right", "left", "back", "bottom", "custom"], "default": "iso" },
      "custom_orientation": { "type": "array", "items": { "type": "number" }, "minItems": 4, "maxItems": 4,
                              "description": "quaternion; required when camera == custom" },
      "width": { "type": "integer", "default": 1920, "maximum": 1920 },
      "height": { "type": "integer", "default": 1920, "maximum": 1920 }
    } }
  }, "required": ["doc"] },
  "outputSchema-result": { "type": "object", "properties": {
    "render": { "type": "object", "properties": {
      "resource_link": { "type": "string" },
      "available": { "type": "boolean" },
      "reason": { "type": ["string", "null"], "description": "why unavailable (no GL / no FreeCADGui)" },
      "dirty_document": { "type": "boolean", "description": "true when rendered against a document with a pending/broken recompute; the read-only mutation guard was skipped" },
      "empty_scene": { "type": "boolean", "description": "true when no object in the scene draws anything (none resolved, or every subgraph has an empty bounding box); no image is written and resource_link is null" }
    }, "required": ["available"] },
    "scene": { "type": "object", "properties": {
      "rendered_objects": { "type": "array", "items": { "type": "string" },
                            "description": "the scene's object Names whose subgraph drew something; a name whose subgraph has an empty bounding box, or a Body with no Tip, is left out" },
      "focused_on": { "type": ["object", "null"], "description": "resolved focus selector echo" }
    } }
  }, "required": ["render"] } }
```

Typical agent patterns: *isolate* (`include: [Body]`), *context-ghost* (`styles: [{object: BasePlate, transparency: 85}]` while inspecting the flange), *element zoom* (`focus: {kind: "geometric", object: Body, query: {surface_type: Cylinder, radius: {value: 2.5, tol: 0.2}}}` to frame one hole), *before/after fillet check* (`preview_dry_run` with `view.focus` on the target edge). AD-10 budgets and `audience:["user"]` annotation apply unchanged.

## 4. Confirmation Flow (AD-10) — `$defs.Confirm`

```json
{ "Confirm": { "type": "object", "properties": {
    "preview_id": { "type": "string", "description": "from preview_dry_run" },
    "elicitation_action": { "enum": ["accept"], "description": "recorded outcome; decline/cancel never reach the mutation tool" },
    "autoApprove": { "type": "boolean", "description": "headless only; explicit operator flag; every use audit-logged" }
} } }
```

Phase 2 policy: mutation tool called without valid `confirm` in a confirm-required context → `INVALID_INPUT`, no execution. GUI panel and MCP elicitation produce the `accept`; headless is fail-closed unless `autoApprove`. Apply re-runs the operation on the live document under AD-5 — the preview result is never "promoted" to the live doc.

## 5. `debug_exec` Registration Rules (AD-4)

1. **Off by default.** Registered into the MCP tool list only when the human operator sets `FREECAD_BUDDY_ALLOW_EXEC=1` at server start. When off it is *unregistered* — absent from `tools/list`, not merely erroring.
2. **Never an AI mutation path.** Excluded from `preview_dry_run.operation.tool`, from the confirm flow, and from every benchmark/harness agent toolset. G1.6/registry introspection must show zero mutation tools *and* no `debug_exec` in AI-facing registries.
3. **Audited.** Every call appended to the append-only audit log (code, timestamp, caller, doc handle, resulting fingerprint) — from Phase 0 (AD-17).
4. **Not a sandbox.** Namespace reduction (FreeCAD API globals only) is hygiene, never described as a security boundary; this repository ships no isolation boundary, so the operator's environment is the only one (AD-35, exec-sandbox research Finding 1).
5. **Never enabled in an unattended run:** the flag is a human act, and no agent may set it.
6. Input `{ "doc": handle, "code": string }`; result `{ "stdout", "value_repr", "fingerprint_after" }`. It still requires an explicit doc handle (AD-20) and its mutations are audit-logged, though it bypasses AD-5 typing by definition — which is exactly why it is operator-only.

## 6. Registration & Phasing Rules

- The tool registry is phase-profiled: the Phase 1 assistant profile registers `query_` + `verify_` + `document_list`/`document_open`(read-intent) only — zero mutation tools (G1.6). Phase 2 profile adds `sketch_`/`feature_`/`preview_`/remaining `document_` tools behind the confirm gate.
- One MCP low-level `Server` object serves both transports (stdio headless, streamable HTTP in-GUI; SSE never) per AD-3; stderr-only logging on the server path.
- All schemas live in `contracts/` (stdlib-only, AD-1/AD-12); use-case implementations are host-agnostic (AD-2).

## 7. Conflicts & Design Decisions

- **No AD conflicts identified.** Two deliberate interpretations, recorded per spine instructions:
  1. **Lifecycle-op exemption (§1.4):** `document_save/close/recompute/undo` are mutations for serialization/audit purposes but exempt from the AD-5 snapshot bracket and Phase 2 preview gate (no new geometric intent; `undo` is itself the AD-5 rollback mechanism, proven by AD-6 fingerprints per G2.3). AD-5's "every mutation" is read as "every geometry-intent mutation"; 
  2. **G0.2 counting:** the gate text counts `query_`/`document_`/`export_`; this catalog meets ≥15 (17: 8 `query_` + 6 `document_` + 3 `export_`) within those namespaces alone, so the stricter reading holds; with Phase 0 `verify_` the AI-visible count is 24.

## 8. Phase-5 tools (forward pointer — designed at the G5-robot gate)

Robot-description export and part sourcing (AD-22/AD-23) add, at Phase 5, to the same
`export_`/`verify_` conventions: `export_urdf`, `export_sdf` (each carrying `verified: false`
until its pair passes) and `verify_export_urdf`, `verify_export_sdf` (re-parse + schema-valid +
kinematic-tree sanity + inertials + mesh-resolve, orchestrated external-side like the AD-9 mesh
oracles, with the in-FreeCAD assembly/inertial reads via RPC); plus part sourcing/import tools on
the `document_`/import path (AD-20). Full schemas live in
[Robot-Description Export & Part Sourcing Design](robot-description-and-sourcing-design.md) §5;
empirically-gated items (CROSS-vs-XML build path, catalog choice) land at the G5-robot entry gate.
