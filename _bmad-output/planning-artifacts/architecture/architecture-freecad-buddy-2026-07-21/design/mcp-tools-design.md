---
title: MCP Tool Catalog Design — Phases 0–2
status: final
date: '2026-11-24'
ad-refs: [AD-1, AD-2, AD-4, AD-5, AD-6, AD-7, AD-8, AD-9, AD-10, AD-11, AD-12, AD-13, AD-17, AD-20, AD-27]
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

Implementation-ready catalog of the FreeCAD Buddy MCP tool surface for Phases 0–2. Tool names use the wire convention: underscore + namespace prefix (`query_`, `document_`, `export_`, `verify_`, `sketch_`, `feature_`, `preview_`; `script_exec` is the one tool with no prefix); dot form is docs shorthand only (spine Consistency Conventions). All tool implementations live in `usecases/`, schemas and envelopes in `contracts/` (AD-1); identical implementations serve GUI (via RPC listener) and headless hosts (AD-2).

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

Every tool returns the contracts-owned `ResultEnvelope` as MCP `structuredContent` validated by its per-tool `outputSchema`, plus a human-readable `text` summary in `content` (spine convention "Tool results"). The `text` field is a per-tool one-line summary of `structured_content` — counts, headline values, and error flags (e.g. `"201 objects, 4 shown."`, `"Body 'pcb': volume 8642.85 mm³, 15 faces."`) — never a JSON re-dump; a tool without a bespoke summary falls back to a compact `key: value` flattening (`summary_text`). A string longer than 80 characters, or holding a line break, renders as `key: <N chars>`, because `structured_content` already carries it. A tool whose payload is a long text body (today only `query_tree_summary`) puts it in the optional `text_blocks: list[str]` and is registered with `RpcMethod.structured_output=False`. Such a tool declares no `outputSchema` and its result is one plain `TextContent`: a `<STATUS>: <text>` line (`detail.message` in place of `text` when the status is not OK), a `framing: <fits|does not fit|unknown>, ratio <r>, <checked>[, <stale_reason>]` line when the envelope has `framing`, then each `text_blocks` entry. There is no JSON block and no `structuredContent`: Claude Code shows the agent only `structuredContent` when a result carries it and drops every content block, so the tree would never reach the agent. No namespace defines a variant envelope.

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
    "images": { "type": "array", "description": "ImageRef[], capability-gated (AD-10)" },
    "text_blocks": { "type": "array", "items": { "type": "string" }, "description": "raw text bodies sent as content[1..]; absent from the JSON block and structuredContent" }
  },
  "required": ["status", "structured_content", "text"]
}}}
```

- The status set is closed (AD-17); Phase 0–2 use-case outcomes emit `OK | SPEC_FAILED | RECOMPUTE_ERROR | INVALID_INPUT`; the transport layer additionally emits `TIMEOUT` (marshal timeout) and `WORKER_CRASHED` (RPC listener unreachable) from Phase 0 — see integration-mcp-freecad.md §7; `OOM_KILLED` is reserved vocabulary with no producer. The schema binds from Phase 0.
- Verification payloads reuse the contracts `ValidationReport` shape with its banner (FreeCAD version, `ElementMapVersion`, validator sensitivity where citable).
- Renders follow AD-10 budgets: ≤1920 px, `audience:["user"]`, `resource_link` preferred over inline base64.

### 1.4 Mutation protocol fields (AD-5, AD-6, AD-7)

Every mutation tool (column **Mut** = yes below) except `script_exec` (observe-only bracket, §5 rule 4) executes the AD-5 bracket (geohash snapshot → `openTransaction` → typed op → `recompute()` → post-verify → commit; on failure abort + re-hash-proven rollback) and returns a common `mutation` block inside `result`:

```json
{ "mutation": {
  "schema": "fcb.mutation/2",
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

Fingerprints carry their serializer tag; cross-tag comparison is banned (AD-6). `tnp_audit` reports `UNSUPPORTED`, never clean, when the element map probe fails (AD-7, AD-11). From Phase 2, mutation tools additionally accept an optional `confirm` object (§4) tying execution to a `preview_dry_run` + elicitation acceptance (AD-10). Every host runs the operator auto-approve posture by default: a mutation without `confirm` applies in one call and its `approval` audit line carries `mode: "auto_approve"` and `source: "FREECAD_BUDDY_AUTO_APPROVE"`. With `FREECAD_BUDDY_AUTO_APPROVE=0` set before the host starts, a mutation without a valid `confirm` is refused.

**Lifecycle ops** (`document_save`, `document_close`, `document_recompute`, `document_undo`) change document state but carry no new geometric intent: they are audit-logged and serialized with the single-writer rule (AD-20) but are exempt from the preview/confirm gate. `document_undo` is verified by fingerprint comparison (AD-6; gate G2.3). A `feature_set_parameters` call that writes only `Visibility` and carries no `confirm` is display state: it runs the AD-5 bracket and writes an `approval` line with `mode: "display_state"`, but is confirm-exempt in both postures. A call that also writes any other property keeps the gate, and the carve-out stays `Visibility` only: a `Label` or `Placement` write changes the model's content and keeps the gate. A call that carries a `confirm` takes the token path.

## 2. Tool Inventory

**Mut** = mutates the target document (drives AD-5 protocol + Phase 2 confirm gate). *(L)* = lifecycle op, confirm-exempt per §1.4.

**Shipped** = present in `hosts/tool_catalog.py:tool_specs()` today. **planned** = specified here, not yet registered — a planned row is a design commitment, never evidence of a shipped tool. `tool_specs()` is the authority: if this table and that function disagree, the function wins and this table is the bug (AD-4 makes the typed tool list plus `script_exec` the entire AI mutation surface; `script_exec` is the one shipped tool outside `tool_specs()`, registered from `SCRIPT_EXEC_SPEC`, and any other unlisted shipped tool is an inventory defect).

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
| `document_object_delete` | 2 | Delete objects under AD-5; refuses when objects outside the set depend on them unless `with_dependents`; a Body takes its Group, Origin and Origin features (§3.7.2) | yes |

### `query_` — read-only introspection (zero mutation; Phase 1 assistant surface, G1.6)

| Tool | Phase | Purpose | Mut |
| --- | --- | --- | --- |
| `query_tree_summary` | 0 | Plain-text containment tree in the shape of the Model panel, line-capped (G1.3 large-tree safe) | no |
| `query_object` | 0 | One object: type, label, properties, error state + `getStatusString()` | no |
| `query_mass_properties` | 0 | Volume/area/bbox/COM + topology counts + `is_valid` for one object, or for 1 to 50 objects (`objects`) | no |
| `query_interference` | 1 | Common volume and minimum distance for object pairs (`objects`: every pair, or `pairs`); `boolean_failed` flags a boolean that returned nothing at distance 0 and that a fuse cross-check could not prove to be plain contact, so an empty result never reads as no overlap (numbers only, AD-35) | no |
| `query_section` | 1 | Cross-section of one object at a plane: wire counts, length, area, bounding box and optional capped polylines; a plane that misses is `OK` with `wires` 0; `area` is null when unmeasured, never 0 (numbers only, AD-35) | no |
| `query_dependencies` | 0 | `InList`/`OutList` dependency edges for object or whole doc (whole-doc `edges` capped at `max_edges`, truncation flagged) | no |
| `query_sketch_info` | 0 | Sketch geometry + constraint listing (types, names, values, driving flags) | no |
| `query_placement` | 0 | Local + global placement of an object | no |
| `query_capabilities` | 0 | Runtime capability probes (AD-11): FreeCAD version, `ElementMapVersion`, element-map availability, render capability, `script_exec` state | no |
| `query_screenshot` | 0 | Capability-gated render to PNG (`resource_link`, ≤1920 px) with **view control**: include/exclude objects, per-object transparency/color override, focus-on-element camera framing, highlight (§3.9). Constructed-scene render — never mutates document or user viewport; renders a document with a pending/broken recompute (`render.dirty_document: true`) rather than hard-failing. Reports unavailable when no GL — never fails hard | no |
| `query_tree_children` | 1 | Paged expansion of a single node's children (offset/limit within one level); `query_tree_summary` owns focus/expand/depth/reveal navigation — **planned** | no |
| `query_parameters` | 1 | VarSet properties, aliased Spreadsheet cells and every expression binding of the document, each list capped at 500 rows with totals; an unreadable value is null with a reason (numbers only, AD-35) | no |

### `export_` — artifact output (AD-9: each pairs with its `verify_export_*`)

| Tool | Phase | Purpose | Mut |
| --- | --- | --- | --- |
| `export_step` | 0 | Write STEP AP214/AP242, `write.step.unit=MM` pinned per call | no |
| `export_stl` | 0 | Write STL via `MeshPart.meshFromShape` (linear + angular deflection); several objects merge into one mesh | no |
| `export_3mf` | 0 | Write 3MF from the same single tessellation source as STL; one named mesh object per object | no |

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
| `feature_loft` | 2 | Additive or subtractive loft through a profile sketch and section sketches (§3.7.3) | yes |
| `feature_sweep` | 2 | Additive or subtractive sweep of a profile sketch along a spine (§3.7.3) | yes |
| `feature_hole` | 2 | PartDesign Hole (thread metadata is hint-only for verification) | yes |
| `feature_fillet` | 2 | Fillet selected edges (selector objects) | yes |
| `feature_chamfer` | 2 | Chamfer selected edges | yes |
| `feature_pattern` | 2 | Linear/polar pattern of features | yes |
| `feature_mirror` | 2 | Mirror features across plane/datum | yes |
| `feature_datum` | 2 | Create datum plane/axis/point/CS (TNP-defensive referencing) | yes |
| `feature_part_primitive` | 2 | Part box/cylinder/cone/sphere/torus at document level, outside any Body; optional placement (§3.7.5) | yes |
| `feature_part_boolean` | 2 | Part cut/fuse/common of top-level solids; refuses untrusted or too-complex inputs, rolls back an empty or invalid result (§3.7.5) | yes |
| `feature_set_parameters` | 2 | Edit object properties / driving dimensions, a `Placement` or `AttachmentOffset` (`{base, rotation}`), and string properties including `Label` | yes |
| `feature_parameters_define` | 2 | Create a VarSet when missing and add or update typed parameters on it (`length`, `angle`, `float`, `integer`, `bool`, `string`); refuses a name the expression parser reads as a unit or constant | yes |
| `feature_set_expression` | 2 | Bind or clear expressions on numeric property paths (`Length`, `.Constraints.<name>`, `.AttachmentOffset.Base.z`), all items in one transaction; refuses a binding FreeCAD would store wrongly (a unit of another dimension, an infinite value, a dead path, a text that crashes the parser) | yes |

### `preview_` — dry-run channel (AD-10)

| Tool | Phase | Purpose | Mut |
| --- | --- | --- | --- |
| `preview_dry_run` | 2 | Execute proposed op on `FCB_TMP_` copy-doc; return structured diff + optional render; no live-doc mutation | no |

### Escape route — `script_exec` (AD-4)

| Tool | Phase | Purpose | Mut |
| --- | --- | --- | --- |
| `script_exec` | 0 | Agent Python exec inside FreeCAD for operations no typed tool covers (listed gaps); observe-only AD-5 bracket (automatic transaction, fingerprint, `changed`, `new_errors`, no rollback; TIMEOUT: AD-27); see §5 | yes |

### Counts & G0.2

Specified vs shipped. "Shipped" = returned by `hosts/tool_catalog.py:tool_specs()`.

| Namespace | P0 | P1 | P2 | P3 | Specified | Shipped |
| --- | --- | --- | --- | --- | --- | --- |
| `document_` | 6 | — | 2 | — | 8 | 8 |
| `query_` | 8 | 4 | — | — | 12 | 11 (`query_tree_children` planned) |
| `export_` | 3 | — | — | — | 3 | 3 |
| `verify_` | 7 | — | 1 | — | 8 | 6 (`verify_fingerprint`, `verify_references` planned) |
| `sketch_` | — | — | 8 | — | 8 | 8 |
| `feature_` | — | — | 17 | — | 17 | 17 |
| `preview_` | — | — | 1 | — | 1 | 1 |
| `view_` | — | — | — | — | 1 | 1 |
| **AI-visible total** (typed tools) | | | | | **58** | **55** |
| `script_exec` (escape route, outside `tool_specs()`) | 1 | — | — | — | 1 | 1 |

**G0.2 satisfied:** Phase 0 = **17** tools across `query_`/`document_`/`export_` (8+6+3) — ≥15 on the gate's literal namespace set; **24 AI-visible** including `verify_`, plus `script_exec` (registered by default, gated by §5, kept outside `tool_specs()` so the G0.2 count is unchanged) = 25 registered specs at P0. Every tool ships JSON `inputSchema` + `outputSchema` + docstring (G0.2 pass rule), except that a `text_blocks` tool (`query_tree_summary`) ships no `outputSchema`.

The three planned tools are Phase 1/2 scope and their absence is expected at this point in the build; they are listed so the table cannot be misread as a shipped inventory. `tool_specs()` returns **55**; with `SCRIPT_EXEC_SPEC` that is 56 registered specs.

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

The document tree as plain text in the shape of FreeCAD's Model panel (G1.3 context-overflow guard by explore-then-expand plus a line cap). The tree travels in the envelope's `text_blocks` (§1.3) and reaches the client as `content[1]`; `structured_content` carries only the counts.

**Line.** `<prefix><v|-> [<CODE>] <Name>[ "<Label>"][ (+N)][ *tip][ !<status>]`. `v` = `Visibility` true (the App value; FreeCAD syncs it with the view provider both ways). The label appears only when it differs from the name. `(+N)` = N children not shown; a node opened only along a path ends `(+N more)`, N excluding the shown child. `*tip` = the Tip of its Body. `!<status>` = a genuine `getStatusString()` error. A Label is whitespace-collapsed and its `"` escaped as `\"`, so each object stays on one line. An `App::Link` (or `App::LinkPython`) line ends `-> <target>` and has no children. Connectors: `|-- ` for a middle child, `` `-- `` for the last; prefix `|   ` below a middle child, four spaces below the last.

**Type code.** The `TypeId` after `::` in capitals (a `TypeId` without `::` in capitals as it is), except a fixed override table: `PartDesign::Plane`→`DPLANE`, `App::Plane`→`PLANE`, `App::Line`→`AXIS`, `PartDesign::Line`→`DLINE`, `App::Point`→`POINT`, `PartDesign::Point`→`DPOINT`, `Sketcher::SketchObject`→`SKETCH`, `PartDesign::FeatureBase`→`BASE`, `PartDesign::Body`→`BODY`, `App::Origin`→`ORIGIN`, `App::Link`→`LINK`. A code is not unique (`Part::Plane` and `App::Plane` are both `PLANE`; `Part::Fillet` and `PartDesign::Fillet` are both `FILLET`). The table lives in `usecases/tree_text.py`; `skills/freecad-fundamentals/references/tree-codes.md` publishes it, and `tests/external/test_tree_text.py` fails when the two differ.

**Children (containment, not `OutList`).** Each rule copies a FreeCAD view provider's `claimChildren` (`docs/references/FreeCAD/src`). An origin group (Body, `App::Part`) lists its `Origin` first, then `Group`, leaving out each member that another member claims (`ViewProviderGeoFeatureGroupExtension.cpp:78-108`). A group lists `Group`; an `App::LinkGroup` lists `ElementList`. An `App::Origin` lists `OriginFeatures`. `Part::Boolean` lists `Base`, `Tool`; `Part::MultiFuse`/`Part::MultiCommon` list `Shapes`; `PartDesign::Loft` lists its profile and `Sections`, `PartDesign::Pipe` its profile, `Sections`, `Spine` and `AuxiliarySpine` (2D objects only, as the source filters); `PartDesign::MultiTransform` lists `Transformations`. Any other sketch-based feature lists its `Profile` when it is a sketch. Top level = objects no other object holds as a child. A containment cycle is cut where it repeats. Dependencies stay in `query_dependencies`.

**Views.** Without `focus`, every top-level object is listed. With `focus`, the first line is `path: <A> > <B> > <Name>` and only that node's subtree follows. `depth` = levels open below the start: with `focus` the start is that object (`depth` 1 = it and its children); without `focus` the start is the document (`depth` 1 = the top level, collapsed). `expand` opens each named node one level and opens its ancestors only along the path. `filters.name_pattern` (regex over `"Name Label"`) and `filters.types` (codes in any case, or `TypeId`s matched exactly; both filters given = a match passes both) select matches inside the start subtree; each match is shown on its opened path, not opened itself unless `expand` names it, and every other line stays collapsed (`depth` does not open levels). With 0 matches the tree shows the start level only.

**Bounds and errors.** 200 tree lines; past that the last line is `... <K> more lines; narrow with focus or a smaller depth` and `truncated` is true. An unknown `focus` or `expand` name → `INVALID_INPUT` "unknown object: <name>"; an `expand` name outside the `focus` subtree → `INVALID_INPUT` "<name> is outside focus <focus>"; `depth < 1` or an invalid `name_pattern` → `INVALID_INPUT`.

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "focus": { "type": "string", "description": "object Name; show only its subtree under a 'path:' line" },
    "expand": { "type": "array", "items": { "type": "string" }, "description": "object Names to open one level; ancestors open only along the path" },
    "depth": { "type": "integer", "default": 1, "minimum": 1, "description": "levels open below the start (focus, or the top level)" },
    "filters": { "type": "object", "additionalProperties": false, "properties": {
      "types": { "type": "array", "items": { "type": "string" }, "description": "tree codes (PAD) or TypeIds" },
      "name_pattern": { "type": "string", "description": "regex searched over 'Name Label'" }
    } }
  }, "required": ["doc"], "additionalProperties": false },
  "outputSchema-result": { "type": "object", "properties": {
    "doc": { "type": "string" }, "total_objects": { "type": "integer" },
    "shown": { "type": "integer", "description": "tree lines shown, at most 200" },
    "truncated": { "type": "boolean" },
    "matches": { "type": "integer", "description": "present only when filters are given" }
  }, "required": ["doc", "total_objects", "shown", "truncated"] } }
```

The envelope's `text_blocks` holds one entry, the tree text (optional `path:` line, tree lines, steering line); the adapter sends it as `content[1]`.

`text`: `"<total_objects> objects, <shown> shown."`, with `, truncated` before the period when the cap cut the tree. When objects in the start subtree are in error, shown or not, the period is followed by ` Errors: <Name>: <status>; <Name>: <status>`.

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

### 3.2.2 `query_mass_properties`

Mass data per object by immutable `Name`. Exactly one of `object` and `objects` is required; both or neither → `INVALID_INPUT`, as is an `objects` list that is empty, longer than 50, or holds a non-string. A name that does not exist, or an empty name, fails the whole call with `INVALID_INPUT`. With `object` → one record; an object with no shape → `INVALID_INPUT`. With `objects` → `{objects: [record, ...]}` in input order, one record per name, duplicates kept; an object with no shape, or an empty shape (a compound with no sub-shapes), gives `{name, shape: null}` and the call stays `OK`. The `object` path keeps its existing response for an empty compound. A record keeps `volume` and `com` null for a non-solid. `is_valid` is `Shape.isValid()`; the solid count stays in `counts.solids` (it appears once). The input schema carries no top-level `oneOf` for the one-of rule, because some MCP clients reject it; the use case enforces it.

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "object": { "type": "string" },
    "objects": { "type": "array", "items": { "type": "string" }, "minItems": 1, "maxItems": 50 }
  }, "required": ["doc"], "additionalProperties": false },
  "$defs": { "MassRecord": { "type": "object", "properties": {
    "name": { "type": "string" }, "solid": { "type": "boolean" },
    "volume": { "oneOf": [{ "$ref": "#/$defs/Quantity" }, { "type": "null" }] },
    "area": { "$ref": "#/$defs/Quantity" },
    "bbox": { "type": "object", "description": "xmin, xmax, ymin, ymax, zmin, zmax, each a Quantity in mm" },
    "com": { "oneOf": [{ "type": "object", "description": "x, y, z, each a Quantity in mm" }, { "type": "null" }] },
    "counts": { "type": "object", "description": "faces, edges, vertices, solids (integers)" },
    "is_valid": { "type": "boolean" }
  }, "required": ["name", "solid", "volume", "area", "bbox", "com", "counts", "is_valid"] } },
  "outputSchema-objects": { "type": "object", "properties": {
    "objects": { "type": "array", "items": { "oneOf": [
      { "$ref": "#/$defs/MassRecord" },
      { "type": "object", "properties": { "name": { "type": "string" }, "shape": { "type": "null" } },
        "required": ["name", "shape"] } ] } }
  }, "required": ["objects"] } }
```

### 3.2.3 `query_interference`

Pair measurement by immutable `Name`; read-only, numbers only (AD-35: no pass or "no interference" verdict). Each shape is the object's own `Shape`, in the frame of its container: a feature inside a `PartDesign::Body` is measured in the Body's local frame (name the Body, not its features), and a part inside an `App::Part` in the Part's frame; no container placement is applied, and an `App::Link` is measured through its own shape. A pair is measured only when both shapes are trusted: valid (`isValid()`), made only of solids (a `Compound` or `CompSolid` of solids is accepted; a shell, face, wire or mesh shell is not), and each solid with a positive volume (a reversed solid, such as `Part::Reverse` output, has a negative one). OCC reads a reversed solid as the material outside its faces, finds no inner distance solution for an invalid solid, and a shell encloses no volume, so each can turn a real overlap into an empty `common` with a positive distance. An untrusted pair is `boolean_failed` true with `common_volume` and `min_distance` both null (decision 26), so `boolean_failed` also covers a pair the kernels were never run on; a script reading `common().Volume` and `distToShape()` returns numbers for such a pair and the tool returns null by design. Validity is checked once per object. Not detected: solids that overlap each other inside one `Compound`, and a self-intersecting solid that passes `isValid()`. Booleans and the distance run on copies of the shapes, because `Shape.common` clears a BREP flag on its inputs and would change a fresh fingerprint digest. Exactly one of `objects` (2 to 20 names, every pair measured, in order `(i, j)` with `i < j`) and `pairs` (1 to 100 `[a, b]` pairs, input order) is required; both or neither, a repeated name in `objects`, a pair of one name twice, or a list outside its bounds → `INVALID_INPUT`. A name that does not exist fails the whole call with `INVALID_INPUT` "unknown object: <name>". An object with no shape, a null shape or an empty shape fails the call with `INVALID_INPUT` naming it, because a skipped object would read as no overlap. `common_volume` is the volume of `Shape.common`; `min_distance` is `distToShape` and is 0 when the shapes touch or overlap. `Shape.common` runs first; a positive common volume proves distance 0, so `distToShape` (slow on large compounds) runs only when `common` gives no volume. A `common` that raises or returns an empty compound, with the distance 0 or unknown, is not proof of no overlap. With the distance unknown it sets `boolean_failed` true and `common_volume` null (`min_distance` is then null; this widens the T-2 contract, where `min_distance` is a non-null Quantity; `min_distance` is also null for an untrusted pair). With the distance at most 1e-7 mm (contact) a fuse cross-check runs on the same copies, after the face-product bound and inside the call deadline: the fuse of the two trusted solids is valid, its volume equals the sum of the two volumes within 1e-12 of that sum, and no solid lies inside the other, so the pair touches without overlap and reads `common_volume` 0, `boolean_failed` false (Epic 13 decision 41). The fuse uses the same intersection step as `common`, so on two nearly tangent surfaces it can miss an overlap too: two spheres with the outer one 1e-6 mm larger and shifted 1e-6 mm give an empty `common` and a fuse of two unmerged solids with the summed volume. A second check is a separate kernel call: a point 1e-4 mm under a face of each shape (at most eight faces per solid) is classified against the solids of the other shape whose bounding box holds it, and a point strictly inside refuses the proof (0.15 s for 384 and 384 faces). A solid nested in another with no probe point inside (a shell thinner than 1e-4 mm), an overlap that only faces after the first eight of a solid, or points away from the sampled point of each face, would show, and a self-intersecting solid that passes `isValid()` are not detected. A fuse that raises, is invalid, has no finite volume or loses volume (a solid inside another, an overlap above the tolerance) leaves `boolean_failed` true and `common_volume` null: the overlap is unmeasured, never zero. Two solids that touch at a face, an edge or a vertex give an empty `common` at distance 0 in FreeCAD 1.1 and read as zero overlap through the fuse. Measured as (sum - fuse) / sum on touching pairs: 1e-16 for boxes, 1e-14 at most for offsets up to 1e5 mm and sizes 1 to 1,000 mm, 3.5e-13 for a filleted box; pairs with BSpline faces or an offset far above the size reach 1e-10 and stay unmeasured (`boolean_failed` true). Two boxes of 100 mm overlapping by 1e-7 mm (1e-3 mm^3, `common` empty) give 3.3e-10 and read `boolean_failed` true. Known limit: the volume gap of the fuse is two thirds of a sub-tolerance overlap, so an overlap of less than 1.5e-12 of the summed volume (3e-3 mm^3 for two boxes of 1,000 mm) reads as touching, and for a small part against a large one the limit follows the large part (1.5e-3 mm^3 for a 1 mm^3 pin in a 1e9 mm^3 block). The fuse took 0.35 s for a pair of 384 faces each, against 19 s for `distToShape` on that pair. `distToShape` collects every contact solution and costs more with more contacts (a lid on a row of 100 unit boxes 13.6 s, on 200 boxes 108 s, below the face-product limit). `distToShape` runs for every trusted pair whose `common` gives no volume, and that cost is not bounded. A section plus the fuse proof could skip it for touching pairs (1.4 s for the 200 boxes), but across a small gap at an edge, a vertex or a curved surface the section finds the boundaries and the fuse keeps two solids whose volumes sum, so the proof reads contact for a real gap (edge gap 1.5e-7 mm, sphere gap 2e-7 mm, edge gap 1e-3 mm on shapes with a tolerance of 1e-2); that shortcut is not used. A non-empty `common` of trusted solids with zero volume gives `common_volume` 0 and `boolean_failed` false. With a positive distance the shapes are disjoint: `common_volume` 0, `boolean_failed` false.

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "objects": { "type": "array", "items": { "type": "string" }, "minItems": 2, "maxItems": 20,
                 "description": "every pair is measured" },
    "pairs": { "type": "array", "items": { "type": "array", "items": { "type": "string" },
               "minItems": 2, "maxItems": 2 }, "minItems": 1, "maxItems": 100 }
  }, "required": ["doc"], "additionalProperties": false },
  "outputSchema-result": { "type": "object", "properties": {
    "pairs": { "type": "array", "items": { "type": "object", "properties": {
      "a": { "type": "string" }, "b": { "type": "string" },
      "common_volume": { "oneOf": [{ "$ref": "#/$defs/Quantity" }, { "type": "null" }] },
      "min_distance": { "oneOf": [{ "$ref": "#/$defs/Quantity" }, { "type": "null" }] },
      "boolean_failed": { "type": "boolean" } },
      "required": ["a", "b", "common_volume", "min_distance", "boolean_failed"] } }
  }, "required": ["pairs"] } }
```

The one-line text counts a pair as overlapping only when its volume is non-zero at the result's display rounding, so the text and the numbers agree. It is a count line (`N pair(s), K overlapping, F boolean failed.`) plus one line per failed or overlapping pair. The call budget is 60 s. A pair whose face counts multiply to more than 150,000 is refused before any measurement with status `INVALID_INPUT` and `detail.code` `interference.too_complex`, naming the pair: `distToShape` holds the interpreter lock, so the 60 s marshal timeout cannot stop it (two 900-box compounds blocked the worker for minutes in the container). The limit comes from interleaved box compounds one millimetre apart, the slowest layout found: 129,600 → 9.5 s, 230,400 → 17.8 s, 360,000 → 29.4 s on a development host. A second limit is a deadline: between pairs the call reads a monotonic clock, and once 40 s have passed it stops and returns the same status and code with the message "stopped after k of n pairs; measure fewer pairs per call". The worst case is the 40 s deadline plus one pair at the per-pair limit (about 12 s), under the 60 s budget. Face counts are a poor cost proxy across layouts (87-face plates about 12 µs per unit, dense boxes about 80 µs), so the sum is bounded by time. 190 pairs of the 87-face plates run in 5.5 to 17 s and are measured. `Shape.common` and `distToShape` cost grows with face count: 190 pairs of 81-hole plates took 5.5 s disjoint and 17.1 s overlapping on a development host; a single `distToShape` between two 200-box compounds took 45 s.

### 3.2.4 `query_section`

Cross-section of one object by immutable `Name`; read-only, numbers only (AD-35). The plane is `normal . p = offset` in the frame of the object's container, like `query_interference`: the object's own `Placement` is applied (the shape is `obj.Shape`) and the container's is not, so a feature inside a `PartDesign::Body` is cut in the Body's local frame. `normal` is `"x"`, `"y"`, `"z"` or a finite non-zero `[nx, ny, nz]` (normalised by the tool, so `[0, 0, 5]` and `"z"` give one plane); `offset` is a mm Quantity. The cut is `Shape.section` of a copy of the shape with a plane face that spans the shape, and the wires come from `Part.sortEdges`. `Shape.slice` is not used: in FreeCAD 1.1.4 it returns no wires for a plane within 1e-5 mm of a face of a box and for the plane on its bottom face (offsets 0, 1e-9, 1e-7, 1e-6 and 1e-5 from the bottom, and 30 - 1e-5 from the top, read as a miss; 1e-4 from either face and the top face itself read correctly), and an empty list would read as a plane that misses. `Shape.section` gave one closed wire at every probed offset (0, 1e-9, 1e-7, 1e-6, 1e-4, 15, 30 - 1e-6, 30, 30 + 1e-7) and a miss at 31. It is wrong when the plane coincides with a planar face, because it then returns every edge of the face, inner ones included: on a mesh-derived box the one wire was open and 82.4 mm long (true perimeter 60 mm), and on the floor of a void the closed wires bounded 300 mm^2 while the area read 400. A plane within 1e-7 mm (`Precision::Confusion`), or within the face's own `Tolerance` when that is larger (a box with tolerance 1e-5 cut 1e-6 mm from a face gave the same open wire), of a planar face of the shape, with that face's normal parallel to it closely enough to stay within that distance across the face, therefore returns `INVALID_INPUT` with `detail.code` `section.plane_on_face` and the message "the plane lies on a face of <object>; offset it by a small amount". A planar BSpline or Bezier face (a box after `toNurbs()`) is found with `Shape.findPlane()`; other curved faces are not tried. The check runs after the trust check, so an invalid shape reads `section.untrusted_shape`. A plane 1e-6 mm or more from the face is cut when the tolerances are the default 1e-7. The tool refuses a shape the kernel cannot be trusted on, because its empty result would pass for a miss: an invalid shape, a solid with non-positive volume (a reversed solid) and a shape with no face (a wire or edge cuts to points) return `INVALID_INPUT` with `detail.code` `section.untrusted_shape`. A valid shell or face is cut: `wires`, `closed_wires`, `length` and `bbox` are measured and `area` is null. A shape above 3,000 faces, or whose BSpline and Bezier faces have a pole load above 640,000 (the sum over those faces of the square of `NbUPoles * NbVPoles`; 800 poles in one face), returns `INVALID_INPUT` with `detail.code` `section.too_complex`. Both are read on the object's own shape before the copy and `isValid` (a shape of 240,000 faces took 9.6 s to copy and 42 s to check). Surfaces of extrusion or revolution over a BSpline curve are not counted (not measured). Unknown name, a name with no shape, a null shape or an empty shape, a malformed plane or malformed points → `INVALID_INPUT` naming the cause.

`wires` counts the section wires, `closed_wires` those with `isClosed()`, `length` sums their lengths. `area` is the area of `Shape.common` of the plane face and the shape, so holes and islands are right, and it is checked against the area of the face that `FaceMakerBullseye` builds from the closed wires (holes respected): the two must agree within a relative 5e-3 (the two differ by 7e-4 on a NURBS cylinder of radius 10, 314.157 against 313.931, and by 33% on the floor of a void, 400 against 300). It is 0 only when `wires` is 0. It is null, never 0, when wires exist and the shape is not solids only (a shell or a face), when any wire is open, when there are more than 300 wires (`common` and `FaceMakerBullseye` both grow with the square of the wire count), when `common` raises or returns nothing, when no face can be built from the wires, or when the two areas disagree: the area is unmeasured. The check does not catch a section that the kernel loses in both calls: on a valid 30-turn coil spring, `section` returns 50 of 60 crossings and `common` misses the same regions, so both give 157 mm^2 against about 188; the pole load limit refuses that spring. `bbox` is the optimal bounding box of the section edges (`Shape.optimalBoundingBox()`; `BoundBox` bounds a BSpline edge by its poles and read -12.08 for a NURBS circle of radius 10), in the `query_mass_properties` record shape, null when `wires` is 0. A plane that misses the shape is `OK` with `wires` 0, `closed_wires` 0, `area` 0, `length` 0 and `bbox` null. Not detected: solids that overlap or touch each other inside one `Compound` pass `isValid()`; `area` counts each solid (two stacked boxes cut on their shared face read twice one face) and touching solids share edges, so `Part.sortEdges` merges them into one wire group (two boxes side by side cut at mid height gave one closed and one open wire, and a length 10 mm short of the sum of the squares).

With `points`, each wire is discretised with `deflection` (a mm Quantity, at least 1e-6 of the shape's bounding-box diagonal; `discretize(Deflection=0)` never returns, so a smaller value is `INVALID_INPUT`) into `polylines`, one `[[x, y, z], ...]` list per wire in mm and in wire order. `max_points` (2 to 5000, default 1000; a polyline of one point is not a line) caps the points over all wires: a wire is cut at the cap, no wire starts with fewer than 2 points left, and `truncated` is true when any point or wire is left out.

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "object": { "type": "string" },
    "plane": { "type": "object", "properties": {
      "normal": { "oneOf": [ { "enum": ["x", "y", "z"] },
                  { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 } ] },
      "offset": { "$ref": "#/$defs/Quantity" } },
      "required": ["normal", "offset"], "additionalProperties": false },
    "points": { "type": "object", "properties": {
      "deflection": { "$ref": "#/$defs/Quantity" },
      "max_points": { "type": "integer", "minimum": 2, "maximum": 5000, "default": 1000 } },
      "required": ["deflection"], "additionalProperties": false }
  }, "required": ["doc", "object", "plane"], "additionalProperties": false },
  "outputSchema-result": { "type": "object", "properties": {
    "wires": { "type": "integer" }, "closed_wires": { "type": "integer" },
    "length": { "$ref": "#/$defs/Quantity" },
    "area": { "oneOf": [{ "$ref": "#/$defs/Quantity" }, { "type": "null" }] },
    "bbox": { "oneOf": [{ "type": "object", "description": "xmin, xmax, ymin, ymax, zmin, zmax, each a Quantity in mm" }, { "type": "null" }] },
    "polylines": { "type": "array", "items": { "type": "array", "items": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 } } },
    "truncated": { "type": "boolean" }
  }, "required": ["wires", "closed_wires", "length", "area", "bbox"] } }
```

The one-line text is `N wire(s), K closed, length L mm, area A mm^2.` (`area unmeasured` when null), plus `Polylines truncated at max_points.` when `truncated`. The call budget is 60 s. `Shape.isValid`, `Shape.section`, `Shape.common` and `FaceMakerBullseye` hold the interpreter lock, so the 60 s marshal timeout cannot stop them, and three limits bound the cost before the work (whole tool call on a development host unless noted). Face limit, 3,000 (cost on one solid grows with the square of the face count): regular prism 1,002 faces 1.0 s, 2,002 faces 3.1 s, 3,002 faces 6.1 s; plate with hexagonal holes 1,806 faces 3.0 s, 3,006 faces 7.1 s, 4,206 faces 13 s; a 5,000-face prism 27 s, an 8,406-face plate 42.6 s and a 9,992-face prism 95.7 s (red team). Pole load limit, 640,000 (`Shape.section` on a swept BSpline face grows with the square of its poles, with 3 faces): coil spring of 3 turns, 246 poles, 0.8 s; 5 turns, 414 poles, 1.9 s; 10 turns, 822 poles, 7.8 s; 30 turns 112 s; 60 turns 210 s (red team). 1,000 NURBS cylinders (3,000 faces, 20,000 poles in all, load 135,000) took 11.8 s. Wire limit for the area, 300: `common` on separate boxes 1,600 wires 4.7 s, 3,200 wires 16 s; a plate with 3,000 holes 21 s, 9,000 holes 103 s; `FaceMakerBullseye` on separate cylinders 100 wires 0.11 s, 300 wires 0.91 s, 600 wires 7.9 s. Measured at the limits: prism of 3,000 faces 6.1 s; plate with 495 holes (2,976 faces, area skipped) 4.7 s; plate with 290 holes (1,746 faces, area measured) 4.6 s; that plate beside a 5-turn spring 5.4 s; a spring at the pole limit about 8 s. One call stays under about 10 s. The pole load refusal names the measured load and the limit. The cut runs on a copy of the shape so the document's shapes are never modified.

### 3.2.5 `query_parameters`

```json
{ "inputSchema": { "type": "object", "properties": { "doc": { "type": "string" } },
    "required": ["doc"], "additionalProperties": false },
  "result": { "type": "object", "properties": {
    "varsets": { "type": "array", "items": { "object": "Name", "label": "Label",
      "parameters": "[{name, type, value, unit, group, description, reason?}]" } },
    "spreadsheets": { "type": "array", "items": { "object": "Name", "label": "Label",
      "parameters": "[{name (alias), cell, contents, value, unit, reason?}]" } },
    "bindings": { "type": "array", "items": "{object, path, expression}" },
    "totals": { "type": "object", "description": "varset_parameters, spreadsheet_parameters, bindings: every row, cut or not" },
    "truncated": { "type": "boolean" } } } }
```

Read-only, values as stored (AD-35). `varsets` holds every property of each `App::VarSet` except the ones every VarSet has (`ExpressionEngine`, `Label`, `Label2`, `Visibility`, read from `shim.varset_builtin_properties()`). `type` is the wire name (`length`, `angle`, `float`, `integer`, `bool`, `string`) for the six property types `feature_parameters_define` writes, else the FreeCAD type id. A `Quantity` is read in `mm` for a length and `deg` for an angle, else in the preferred unit of the active unit schema (so the unit of a force or mass can differ between users, and the value is always in the unit named beside it); a dimensionless quantity and every non-quantity value have `unit` null. `spreadsheets` holds the aliased cells of each `Spreadsheet::Sheet`; a cell with no alias is not a named parameter and is left out. `bindings` holds every `(path, expression)` pair of every object's `ExpressionEngine`, sketch constraint paths such as `.Constraints.width` included. A value that cannot be reported (a non-finite number, a vector, a failed formula) is `null` with a `reason`, never 0. `Spreadsheet.get` returns a failed formula's error as the string `ERR: ...`, so a cell whose contents start with `=` and whose value starts with `ERR: ` is read as an error, while a text cell holding those words is not. Each list holds at most 500 rows; `totals` counts all rows and `truncated` is true when any total exceeds 500. The call reads property values without a recompute and writes nothing, so a touched object stays touched and the document fingerprint is unchanged. The one-line text is `N VarSet parameter(s) in K VarSet(s), M spreadsheet parameter(s), B binding(s).`, followed by ` Lists truncated at 500 rows.` when `truncated` is true.

### 3.3 `verify_shape`

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "object": { "type": "string", "description": "immutable Name; optional only when the document has one shape-bearing object" },
    "checks": { "type": "array", "items": { "oneOf": [ "<one branch per fn, see Check schema>" ] },
      "description": "{fn, expect, ...}; each fn takes only its own keys; omit = measurement-only report" },
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

**Check schema.** `checks.items` is a `oneOf` with one branch per `fn` of the fourteen above (`hole_spacing` has two: a pitch form with `expect` a number or a list and no pair, and a pair form with `select_a` and `select_b` holes, one distance and no `select`). Each branch has `fn` as a `const`, a typed `expect`, the keys that `fn` takes and `additionalProperties: false`. The key sets come from `contracts/assertions.py` (`CHECK_OPTIONAL_KEYS`, `CHECK_REQUIRED_KEYS`), the same tables `usecases/assertions.py` and `usecases/verify.py` validate against. The value types are written twice, as JSON Schema in `hosts/tool_catalog.py` and as Python in `usecases/assertions.py`; `tests/external/test_verify_shape_schema.py` checks that both accept and refuse the same checks. The failure text for a rejected check is only "is not valid under any of the given schemas"; `items.description` lists the keys of each `fn`. `expect_extent` requires `direction`; `distance_between` and `angle_between` require `select_a` and `select_b`. `{"type": "is_valid_solid"}` fails schema validation before dispatch. `oneOf` sits on the array items, never at the schema top level.

**Object resolution.** `object` stays optional. When it is omitted and the document holds exactly one shape-bearing object (a non-null `Shape`; the origin axes, planes and point do not count), that object is measured. When it holds more than one, the call returns `INVALID_INPUT` with `detail.code = verify_shape.object_required` the message `object is required: document has N shape objects: <Name (Label)>, ...` (first 10, then `+K more`) and `detail.objects` listing every candidate Name. A PartDesign Body with its sketch and pad counts as three. A document with no shape-bearing object keeps the earlier `ValidationError`.

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

**Selection.** `export_step`, `export_stl` and `export_3mf` take one or several `objects`. Omitted `objects` selects every visible solid object that no other such object consumes. An object is visible when it and every Body or Part that holds it has `Visibility` set (hiding a group in the GUI leaves its children's own flag set). An object is consumed when another candidate names it in a link property (boolean operands, a compound's `Links`, a Body's or Part's `Group`, and so on). An attachment, an expression reference and every link of a mirror do not consume their target, so a mirror's source exports beside the mirror. A document that holds exactly one object exports it whatever its visibility. A named selection is exported as given: naming a Body and one of its features exports both. With several objects each holds a solid, only its solids are written (a loose face or wire is left out of the file and of the recorded facts), and one without a solid is `INVALID_INPUT` ("object has no solid: <Name>"); one named object keeps the earlier rule ("object has no shape: <Name>" for a null shape). The result lists the exported object `Name`s in `objects`. Several objects: STEP writes one product per object named by its `Label`; 3MF writes one mesh object per object with `name` = `Label`; STL writes one merged mesh. One object is written as before and carries no name. Shapes are written in the coordinates of `obj.Shape`: an `App::Part` placement above the object is not applied, for one object or several.

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
- `feature_set_parameters`: a value outside the property's type family — a `Quantity` or number for a quantity property, a number for a unitless float property, an integer for an integer property, a boolean for `App::PropertyBool`, a member string for `App::PropertyEnumeration`, a `{base: {x, y, z}, rotation: {axis, angle}}` object for `App::PropertyPlacement` (omitted keys keep their value), a string for `App::PropertyString`. A read-only property is refused, which covers the `Placement` of an attached object (write its `AttachmentOffset`) and of a feature inside a Body (move the Body, or the `AttachmentOffset` of the feature's sketch); an `AttachmentOffset` of an unattached object is refused with `parameters.not_attached`, a string FreeCAD would cut with `parameters.invalid_string` (the same code `feature_parameters_define` uses), and a rotation axis FreeCAD cannot normalise exactly, or an `axis` without an `angle` while the current rotation is zero, is refused. Any other property type (for example `Part::PropertyPartShape`) is refused. The message names `<feature>.<prop>` and its type.
- `feature_loft`: `sections` empty, repeating a sketch or holding the `profile` (`loft.invalid_sections`); a section with a different wire count from the profile, which FreeCAD raises at recompute (`loft.wire_count_mismatch`); `closed: true` with fewer than 2 `sections`, which FreeCAD resets without a message, `FeatureLoft.cpp:209` (`loft.closed_needs_sections`); a sketch with no wire; a non-boolean flag; `subtractive: true` in a Body with no solid (`loft.nothing_to_subtract`).
- `feature_sweep`: a `spine` that is the `profile`, a Body, a selector that does not resolve to an Edge, or a whole object that is not an edge, a wire or a compound of those (`sweep.invalid_spine`, also for a selector that does not resolve); a `mode` other than `standard` or `frenet` (`sweep.invalid_mode`); a string `spine` that is not a sketch; `subtractive: true` in a Body with no solid (`sweep.nothing_to_subtract`); a non-boolean flag.
- `feature_part_primitive`: a field the kind does not take or lacks, a size at or below 0, a cone with both radii 0, a torus with `radius2` not below `radius1` (§3.7.5).
- `feature_part_boolean`: `tools` empty, above 20 or repeating an input, an input inside a Body or `App::Part`, an input that is reversed, invalid or not made of solids, inputs above the measured cost limits (§3.7.5).
- `feature_fillet` / `feature_chamfer`: a `base` that is not the Body's `Tip`; the message names the Tip. The dress-up builds from its base alone, so a base below the Tip would drop every later feature. FreeCAD's GUI allows this; the bridge refuses it.

**`feature_set_parameters` after validation.** After the bracket opens, a written value of any family (quantity, number, boolean, enumeration, placement, string except `Label`) that the recompute still changes (an expression or a Python feature drives it, or the property clamps it) fails the call as `RECOMPUTE_ERROR` `parameters.value_overwritten` and rolls back; the rollback proof reads the written properties back, because the AD-6 fingerprint does not see them (decisions 32, 46). Result fields: `feature` and `feature_state` as for every `feature_*` tool, `label: {requested, stored}` when `Label` is written (FreeCAD makes labels unique), and `undo_steps`. A call whose parameters are all placements or strings the object already holds opens no transaction: it returns `OK` with `unchanged` (the names) and `undo_steps: 0`, no `mutation` block and no `feature_state`; like the no-change results of `feature_parameters_define` and `feature_set_expression` it runs before the confirm gate, because it has no effect to authorize. `Label` is exempt from the read-back because FreeCAD makes labels unique (unless the `DuplicateLabels` preference is on); the stored label is reported. The transaction is named `set parameters on <object> <n>`, with a per-process counter, so the call's own undo step can be told from an earlier one.

### 3.7.1 `feature_parameters_define`

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "varset": { "type": "string", "description": "VarSet object Name; created when missing" },
    "parameters": { "type": "array", "minItems": 1, "maxItems": 100, "items": { "type": "object", "properties": {
      "name": { "type": "string", "pattern": "^[A-Za-z_][A-Za-z0-9_]*$" },
      "type": { "enum": ["length", "angle", "float", "integer", "bool", "string"] },
      "value": {},
      "group": { "type": "string", "default": "Parameters" },
      "description": { "type": "string" } },
      "required": ["name", "type", "value"], "additionalProperties": false } },
    "confirm": { "$ref": "#/$defs/Confirm" }
  }, "required": ["doc", "varset", "parameters"], "additionalProperties": false },
  "outputSchema-result": { "type": "object", "properties": {
    "varset": { "type": "string" },
    "added": { "type": "array", "items": { "type": "string" } },
    "updated": { "type": "array", "items": { "type": "string" } },
    "unchanged": { "type": "array", "items": { "type": "string" } },
    "undo_steps": { "type": "integer", "description": "1 when the call recorded an undo step, 0 when it changed nothing" },
    "mutation": { "$ref": "#/$defs/MutationBlock", "description": "absent when the call changed nothing and opened no transaction" }
  }, "required": ["varset", "added", "updated", "unchanged", "undo_steps"] } }
```

Type map: `length` to `App::PropertyLength` (value `{value, unit: "mm"}`, not negative), `angle` to `App::PropertyAngle` (`{value, unit: "deg"}`, within +-360), because both property types clamp a value outside their bounds without an error (probed on 1.1.4: -5 mm reads 0 mm, 720 deg reads 360 deg), so the tool refuses it instead of storing a changed value; `float` to `App::PropertyFloat` (finite number; an integer beyond double range is refused), `integer` to `App::PropertyInteger` (integer within +-2,147,483,647, not a boolean: the property stores a C `long`, 32 bits on Windows, and a larger value raised `OverflowError` in FreeCAD 1.1.4), `bool` to `App::PropertyBool`, `string` to `App::PropertyString`. The VarSet is created when missing (Name `varset`; Label `varset` too, with a numeric suffix added by FreeCAD when another object already has that Label). A name the VarSet lacks is added under `group` (default `Parameters`); one it holds with the same type is updated. `added`, `updated` and `unchanged` name the parameters in request order and appear on an `OK` result only, with `undo_steps`; the call carries no `feature` and no `feature_state`, because a VarSet has no shape. A property that already holds the requested value is `unchanged` and is not written, because FreeCAD records no undo step for some same-value writes (a string: the next `document_undo` then reverts the step before the call, which deleted a user object in a probe). A call whose parameters are all unchanged opens no transaction, writes no snapshot, needs no `confirm` (the gate runs only for a call that writes) and has no `mutation` block: it returns `OK` with `undo_steps` 0, and `undo_steps` 0 means `document_undo` would revert an earlier step. A call that changes something records one step (`undo_steps` 1, or 0 when the document stays at undo mode 0) and lists the unchanged names too. `group` and `description` are set when a parameter is created and never after, because FreeCAD does not undo them (probed: `document_undo` reported `matches_pre_op` true and left them changed). The mutation touches the VarSet; an object bound to it is checked by the recompute sweep (an invalid object fails the call) and its geometry change appears in `mutation.changed`.

Refusals, all `INVALID_INPUT` before the bracket opens, with `detail.code` (AD-17):

- `parameters.unit_symbol_name`: the name is a unit or constant to FreeCAD's expression lexer. FreeCAD adds such a property without error, but `<VarSet>.<name>` then fails with `Failed to parse expression` in every expression (probed on 1.1.4 with `W`, `True`, `A`; `W2`, `min2` and `A1` parse). The list is every ASCII `UNIT` and `CONSTANT` token of `src/App/Expression.l` (116 names, among them `W T A V N C K J H F S m g s mm deg in e pi`), and `tests/external/test_parameters_contract.py` checks it against that file.
- `parameters.reserved_name`: a name a VarSet or an expression already uses. That is a property every VarSet has, read from a probe (`Label`, `Label2`, `Visibility`, `ExpressionEngine` on 1.1.4); an attribute of the VarSet object, read from the same probe (a property named `TypeId` would shadow it); and the names the bracket and the fingerprint read from every object (`Shape`, `ElementMapVersion`: a VarSet property named `Shape` made `post_verify` treat the VarSet as a solid and the call always ended `SPEC_FAILED`), and the names `ObjectIdentifier::resolveProperty` answers itself before it looks up a property (`_shape`, `_pla`, `_matrix`, `__pla`, `__matrix`, `_self`, `_app`, `_part`, `_re`, `_py`, `_math`, `_coll`, `_gui`, `_cq`), so `<VarSet>._pla` reads the placement and never a parameter. The call is also refused when the probe read no built-in property.
- `parameters.unit_symbol_name` also applies to the VarSet name, new or existing (`W.width` fails to parse as well).
- `parameters.invalid_string`: a `string` value, `group` or `description` holds a character FreeCAD cuts or rewrites, named in the message by code point and index: NUL (the value is cut at it); the C0 controls other than tab, line feed and carriage return, U+007F to U+0084, U+0086 to U+009F, U+FDD0 to U+FDEF and the last two code points of every plane (these read back as `_` after a save and reopen, which is how a snapshot restore reads them; measured by saving and reopening every code point on 1.1.4); and a lone surrogate.
- `parameters.metadata_immutable`: `group` or `description` given for an existing parameter with another value.
- `parameters.duplicate_name`: one name twice in the request.
- `parameters.not_a_varset`: `varset` names an object that is not an `App::VarSet`.
- `parameters.type_conflict`: an existing property of another type than the request.
- `parameters.bound_by_expression`: an update of a property that an expression binds, because the next recompute applies the expression over the written value (probed: written 99 mm, read 20 mm after the recompute) and `updated` would name a value that did not stick.
- Without a code: a malformed name (a trailing newline included), type, value, unit or group, a value outside the bounds above, an update of a property with `ReadOnly` status, an empty list or one above 100, and a build without `App::VarSet` (`varset_available()` false).

The refusals are raised as `ParameterRefusal` (a `CodedValidationError`, a `ValidationError` carrying `code`) and `rpc_dispatch` maps one onto `INVALID_INPUT` with that `detail.code`, like every other tool's refusal, so `preview_dry_run` meets the same error. The dispatcher reads `code` from `CodedValidationError` only and only when it is a non-empty string; any other exception keeps its status as `detail.code` (an `OSError` from `script_exec` has an integer `code` that would break the envelope schema).

Rollback proof: the shape fingerprint (AD-6) holds no VarSet property, so a parameters-only mutation leaves its digest unchanged and an abort that restored nothing would still compare equal. `run_mutation` therefore takes a `state_probe`; for this tool it reads, before the bracket and after an abort, every property of the VarSet (type, group, documentation, value, bound expression), or `None` while the object does not exist; the value of a Python-object or link property is not compared, because its repr carries an address (only its presence and type are). The rollback is `rolled_back_verified` only when the reading matches; otherwise the document is restored from the snapshot and read again, and a reading that still differs is `SPEC_FAILED` with `rolled_back` false. The general gap (a change to a VarSet or Spreadsheet that no shape reflects is invisible to the fingerprint and to `mutation.changed`) is open for an architecture decision.

### 3.7.2 `document_object_delete`

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "objects": { "type": "array", "minItems": 1, "items": { "type": "string" }, "description": "object Names; a Body also takes its Group members, its Origin and the Origin features" },
    "with_dependents": { "type": "boolean", "default": false },
    "confirm": { "$ref": "#/$defs/Confirm" }
  }, "required": ["doc", "objects"], "additionalProperties": false },
  "outputSchema-result": { "type": "object", "properties": {
    "deleted": { "type": "array", "items": { "type": "string" }, "description": "every removed object Name, document order" },
    "dependents": { "type": "array", "items": { "type": "string" }, "description": "the ones removed only because with_dependents was true" },
    "mutation": { "$ref": "#/$defs/MutationBlock" }
  }, "required": ["deleted", "dependents"] } }
```

A dependent is an object outside the delete set whose `OutList` holds a deleted object (a pad of a deleted sketch, the next feature of a deleted pad through `BaseFeature`, an object an expression binds to a deleted VarSet). A member container (any object with `App::GroupExtension`: `PartDesign::Body`, `App::Part`, `App::DocumentObjectGroup` and their subclasses, except a `PartDesign::Boolean`) that holds the object only in its `Group` is not a dependent, unless an expression on the container names the object (the expression fails once the object is gone). Any other holder is a dependent, a `PartDesign::Boolean` included: its `Group` is its operand list, and a Boolean that kept a deleted tool Body would keep its volume. With `with_dependents` false any dependent refuses the call, `INVALID_INPUT` with `detail.code` `delete.has_dependents`, naming the dependents, before the bracket opens. With true the closure of dependents (dependents of dependents too, and what a dependent Body owns) is deleted. An `App::Origin` or an Origin feature named without the Body or Part that owns it is refused with `delete.origin_object`. An unknown name or an empty list is `INVALID_INPUT` without a code. A deleted `App::Link` array (or `App::LinkPython`) takes its `ElementList` elements with it, as the GUI delete does (`ViewProviderLink::onDelete`). When the deleted feature is visible, its `BaseFeature` is made visible, as `PartDesign::ViewProvider::onDelete` does (after a Tip delete that is the new Tip), and the result lists it in `touched`. A child of a deleted `App::Part` or group is not deleted; it stays in the document outside the group. An `App::Part` or `Part::LocalCoordinateSystem` takes its origin objects like a Body.

A feature of a Body that survives goes through `Body.removeObject` before `Document.removeObject`, so `Tip` moves to the previous solid feature (`Body.cpp` `Body::removeObject`); objects are removed latest first. The next feature of a deleted feature holds it in `BaseFeature`, so it is a dependent: deleting a feature in the middle of a Body needs `with_dependents` and takes every later feature with it (`Body::removeObject`'s relink of the next feature never runs for a survivor).

The deleted names appear in `mutation.changed` with `volume` null (AD-6). `touched` names the deleted objects and each surviving Body that lost a member, so `post_verify` runs `verify_shape` on that Body.

TNP audit: a deleted object that owned a reference (a pad's `Profile`, an expression binding) would grade `BROKEN` as a vanished owner. `run_mutation` takes the set of names the op deletes on purpose and `audit_references` excuses a record whose owner is in that set and absent from the document, in the manner of decision 014 (the exemption is keyed to what the op wrote). An owner that vanished any other way stays `BROKEN`.

Rollback proof: the shape fingerprint holds no VarSet, Body or Origin, so a delete of shape-less objects leaves its digest unchanged. `state_probe` reads, per object, name, label, type, the names it depends on and, for a Body, `Tip` and `Group`; an abort that restored an object without its dependency reads as unproven and falls back to the snapshot.

Undo: one transaction, one `document_undo` restores the objects, `Group`, `Tip`, `BaseFeature`, links and Visibility (measured on FreeCAD 1.1.4 for a Tip delete, a profile-sketch delete with dependents and a whole-Body delete). FreeCAD restores an object's `ExpressionEngine` text but not its dependency on the bound object: after the undo `OutList` lacks the target and a change to the source no longer drives the property (measured: `Pad.Length = VS.L`; `VS.L` 3 to 7 left the pad at 3). The same happens after `abortTransaction`. `shim.relink_expressions` clears and sets each binding of the objects the undo or the abort restored; it records no undo step and leaves the redo stack (measured: `UndoCount`, `RedoCount` equal before and after). A binding that cannot be set again is cleared by the failed attempt and is listed, with its text, in the `errors` of `document_undo`; after an abort the rollback proof reads the dependency back and falls back to the snapshot restore when it is missing.

`preview_dry_run` accepts the tool: `preview_op_table` reads the object-edit spec list beside the `sketch_` and `feature_` lists.

### 3.7.3 `feature_set_expression`

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "expressions": { "type": "array", "minItems": 1, "maxItems": 100, "items": { "type": "object", "properties": {
      "object": { "type": "string", "description": "object Name" },
      "path": { "type": "string", "description": "numeric property path, e.g. Length, .Constraints.width, .AttachmentOffset.Base.z, .Placement.Base.y" },
      "expression": { "type": ["string", "null"], "description": "expression text; null clears the binding" } },
      "required": ["object", "path", "expression"], "additionalProperties": false } },
    "confirm": { "$ref": "#/$defs/Confirm" }
  }, "required": ["doc", "expressions"], "additionalProperties": false },
  "outputSchema-result": { "type": "object", "properties": {
    "bound": { "type": "array", "items": { "type": "object", "description": "{object, path, value, reason?}" } },
    "cleared": { "type": "array", "items": { "type": "object" } },
    "unchanged": { "type": "array", "items": { "type": "object" } },
    "undo_steps": { "type": "integer", "description": "undo steps the call added: 1, or 0 when it changed nothing" },
    "mutation": { "$ref": "#/$defs/MutationBlock", "description": "absent when the call changed nothing and opened no transaction" }
  }, "required": ["bound", "cleared", "unchanged", "undo_steps"] } }
```

All items run in one AD-5 transaction. A row of `bound`, `cleared` or `unchanged` is `{object, path, value}`: `value` is the property's value read after the recompute, as `{value, unit}` for a quantity or a scalar, null with a `reason` when it cannot be read (AD-35). An item that clears a path with no binding on its property, or gives the stored text, is `unchanged`; a call whose every item is `unchanged` opens no transaction and has no `mutation` block, because FreeCAD records no undo step for it and `document_undo` would revert an earlier step (`undo_steps: 0`). A text that FreeCAD stores as the expression already bound (`a*2` for `a * 2`), and a clear by another spelling of the stored path (`.Constraints[2]` for `.Constraints.<name>`), are told apart from a real change only by reading the bindings before and after the write; such an item is `unchanged` too, and a call made only of them has a `mutation` block with `undo_steps: 0`. `undo_steps` is 1 when the call's own transaction heads the document's undo list afterwards, else 0. Each call names its transaction with a running number, because the document's step count stops growing at 20 steps and cannot show a new step. A call made only of `unchanged` items on a document with touched objects can still record a step (the bracket's recompute writes inside the transaction), and `undo_steps` then reads 1.

`path` matches `^\.?[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*|\[[0-9]+\])*$` and must resolve, through `evalExpression`, to a number, a quantity or a bool. A numeric leaf of a Placement (`.AttachmentOffset.Base.z`, `.Placement.Base.x`) and a sketch datum (`.Constraints.<name>`, `.Constraints[<index>]`) qualify; a whole Placement, a Shape, a string or a list does not. A touched sketch is verified like every sketch mutation, so it must be fully constrained. A clear checks only that the object exists, so a binding on a path that no longer resolves, or on a property that is not numeric, can still be removed.

Refusals, all `INVALID_INPUT` before the bracket opens, with `detail.code` (AD-17); FreeCAD accepts each of these cases without an error (probed on 1.1.4):

- `expression.invalid_path`: the path does not match the pattern, names no property, resolves to nothing (`Length.x` is stored and never applies), or ends in `.Value` (FreeCAD stores `.Length.Value` as a second binding that `Length` ignores, and it evaluates to a plain number, which hides a unit mismatch).
- `expression.unsupported_property`: the path resolves to a value that is not a number, a quantity or a bool (`Placement`, `Shape`, `Label`, `Constraints`), its property has `ReadOnly` status, the object is a spreadsheet (FreeCAD ignores a binding on a cell and drops it on save; set the cell contents), the property is a shape (`.Shape.Volume`), or the property is `AttachmentOffset` of an object that is not attached (FreeCAD hides and ignores it, `AttachExtension.cpp`).
- `expression.invalid_text`: empty, longer than 400 characters, or holding a character FreeCAD cuts or rewrites (the set of `feature_parameters_define`). The limit exists because FreeCAD ends the process while it parses a long chained expression: `1*` x 600 terms (1,200 characters) and `1&&` x 550 crash, `1+` x 900 crashes; 400 characters allow 200 two-character terms.
- `expression.invalid_expression`: a parse error or an unresolved reference (`Nope.x` is stored and fails the recompute), or a text that does not evaluate to a number. The message is FreeCAD's.
- `expression.not_finite`: the expression evaluates to `inf` or `nan` (`1 mm / 0` is stored and reads `inf mm`).
- `expression.unit_mismatch`: a quantity of another dimension than the property (`5 deg` on a length is stored and reads `5 deg`), or a dimensioned quantity on a property that holds a plain number (`5 mm` on a float reads `5.0`, the unit lost). A plain number or a dimensionless quantity takes the property's unit.
- `expression.not_integer`: a fraction bound to an integer property, which FreeCAD rounds (`2.5` reads `3`).
- `expression.range_unsupported`: the text holds a cell range (`A1:B2`, `Sheet.A1:Sheet.B2`, `$A$1:$B$2`). FreeCAD evaluates a range cell by cell while the call holds the interpreter lock: `sum(C1:ZZ16384)+sum(C1:ZZ16384)` (31 characters) held one call for 1,087 s, so the character limit bounds parsing and this refusal bounds evaluation. A ternary that compares two cell references matches too.
- `expression.value_out_of_range`: FreeCAD would not keep the value. `setPathValue` skips the range a plain assignment enforces, so a `App::PropertyLength` below 0 and an `App::PropertyAngle` beyond +-360 are refused by type (a pad of -5 mm flips below its sketch), and any other root property is probed: the value is assigned to a scratch object of the same type and read back (a revolution angle of 400 reads 360; an integer past int32 reads back changed). The same code is raised after the recompute, with status `RECOMPUTE_ERROR` and a rollback, when a binding anywhere in the document reads another value than its expression evaluates to and did not before the call (an existing binding that a new one drives out of range).
- `expression.duplicate_path`: one object and path twice in the request (a leading dot is the same path). Two spellings of one stored binding are found inside the bracket, which aborts the call.
- Without an `expression.*` code: an unknown object, a malformed item or key, and a list outside 1 to 100.

Every refusal above checks one item against the document as it is before the call. A value that turns infinite or wrong only because another item of the same batch, or an existing binding that the call drives, changed an input is caught after the bracket's recompute (`recompute_check` of `run_mutation`): the call rolls back with `RECOMPUTE_ERROR` and `detail.code` `expression.not_finite` or `expression.value_out_of_range`. The op itself does not recompute, because the bracket reads the written references right after it, and a recompute inside the op would hide a silent edge drop from the TNP audit.

A dependency cycle is refused by FreeCAD at `setExpression` (`cyclic reference`, `creates a cyclic dependency`) and ends the call with status `RECOMPUTE_ERROR` and `detail.code` `expression.cycle` (the op raises `transaction.RecomputeFailure(code, message)`, which the bracket maps to that status and code). A binding that fails the recompute leaves the object invalid. Both abort the whole call inside the bracket: the transaction is aborted, the document is verified against the pre-call state, and the first `rolled_back_*` proof applies. The shape fingerprint (AD-6) holds no binding, so the proof also reads every object's `ExpressionEngine` back (`state_probe`, as `feature_parameters_define` does).

TNP guard: a binding is a reference record `ExpressionEngine[<path>]`. A new binding is not in the snapshot and a replaced one grades `PASS`. A cleared one is absent from the live reading; it grades `PASS` only when this op reported removing it (`removed_bindings`, the `(owner, record)` pairs the op filled while it wrote), the op's post-op reading lacks it too and its owner still exists (the written-value rule of decision 014), never because the owner was touched. A binding that disappears during the recompute, a binding another tool removes (`sketch_remove_geometry` on a constraint that carries one still grades `BROKEN`, as before), an owner removed from the document, and a call that passes no written reading all grade as before.

The bracket also closes the application-level transaction after every commit and abort (`shim.close_pending_transaction`). `Document::openTransaction` only names the application's active transaction and the document's own opens on the first change, so an op that wrote nothing left it open and the next change by any caller joined it (`document_undo` then refused).

### 3.7.4 `feature_loft` and `feature_sweep`

```json
{ "feature_loft": { "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "body": { "type": "string", "description": "target PartDesign Body Name" },
    "profile": { "type": "string", "description": "first section: sketch Name" },
    "sections": { "type": "array", "items": { "type": "string" }, "minItems": 1, "description": "further section sketch Names, in loft order; each has the same number of wires as the profile" },
    "ruled": { "type": "boolean", "default": false },
    "closed": { "type": "boolean", "default": false, "description": "join the last section back to the profile; needs 2 or more sections" },
    "subtractive": { "type": "boolean", "default": false },
    "name": { "type": "string" },
    "confirm": { "$ref": "#/$defs/Confirm" }
  }, "required": ["doc", "body", "profile", "sections", "name"] } },
  "feature_sweep": { "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "body": { "type": "string", "description": "target PartDesign Body Name" },
    "profile": { "type": "string", "description": "sketch Name" },
    "spine": { "oneOf": [ { "type": "string", "description": "spine sketch Name" }, { "$ref": "#/$defs/Selector", "description": "one Edge (mapped_name), or a whole edge or wire object (mapped_name omitted)" } ] },
    "mode": { "enum": ["standard", "frenet"], "default": "standard" },
    "subtractive": { "type": "boolean", "default": false },
    "name": { "type": "string" },
    "confirm": { "$ref": "#/$defs/Confirm" }
  }, "required": ["doc", "body", "profile", "spine", "name"] } } }
```

Both tools create one feature inside one AD-5 bracket and return `feature`, `feature_state` and the common `mutation` block, like `feature_pad`. `subtractive` selects the type: `PartDesign::AdditiveLoft` or `SubtractiveLoft`; `PartDesign::AdditivePipe` or `SubtractivePipe`. The loft writes `Profile`, `Sections` (each `(sketch, [""])`), `Ruled` and `Closed`; the sweep writes `Profile`, `Spine` (`(object, [""])` for a sketch name or a whole object, `(object, [Edge])` for an edge) and `Mode`.

`mode` names map to the members of the `Mode` enumeration that `FeaturePipe.cpp:60` declares (`Standard`, `Fixed`, `Frenet`, `Auxiliary`, `Binormal`); the member is read from the live enumeration, never by index. `Fixed`, `Auxiliary` and `Binormal` are not offered: `Auxiliary` needs a second spine and `Binormal` a vector.

Every sketch the call names must be fully constrained: AD-5 post-verify step 3 runs `verify_sketch` on all sketches, so a spine or section sketch with free degrees of freedom fails the call with `SPEC_FAILED` and rollback, unless its shape is already degenerate, which the result check below reports first as `RECOMPUTE_ERROR`. A recompute that gives no solid (an open profile, an open section) gives `RECOMPUTE_ERROR` with a proven rollback.

FreeCAD reports several degenerate results as up to date, so the tools check the new feature's own shape after the recompute and fail the call with `RECOMPUTE_ERROR`, `detail.code` `loft.invalid_result` or `sweep.invalid_result`, and a proven rollback when: the shape is null or `isValid()` is false; it holds other than one solid; or it adds (additive) or removes (subtractive) no volume, which covers a spine in the profile plane (volume 0), a spine that climbs and falls back along itself, and a subtractive cut that misses the Body. When every input edge is analytic and the result has at most 300 faces, the Boolean-operation check (`Shape.check(True)`) also runs, because it finds self-intersections that `isValid()` misses (a profile wider than the bend of its spine); `GeomAbs_` continuity notes are ignored. In FreeCAD 1.1.4 the closed lofts tried (3, 4, 6, 8 and 12 sections around a ring, circles or squares, smooth or ruled) built no shape, an invalid solid or a self-intersecting solid, except 8 squares smooth around a ring, which builds a valid solid that the tool accepts, so `closed: true` is usually refused as `loft.invalid_result`. The Boolean-operation check does not run otherwise (any BSpline-like input edge, or in the Body's earlier shape), because it holds the interpreter lock for a time that follows the geometry, not the face count (a 1,002-face loft 18.6 s; a 3-face sweep along a 25-turn helix of 770 poles did not finish in 50 s), so a self-intersecting result built from BSpline inputs is not detected. A subtractive call in a Body with no solid is `INVALID_INPUT` `loft.nothing_to_subtract` or `sweep.nothing_to_subtract`, before the bracket. After a committed call the profile, section and spine sketches are hidden, as the GUI does (a Part object used as a spine is left as it was); one `document_undo` shows them again.

Two refusals protect the bridge, because the OCC builds hold the interpreter lock and the 120 s marshal timeout cannot stop them. Both are `INVALID_INPUT` with a `detail.code`, before the bracket:

- `loft.too_complex` and `sweep.too_complex`. A loft section has a size: its edges, a BSpline edge counting its poles. ThruSections time grows with the square of the larger section of each pair of neighbours, so loft cost is the sum over consecutive sections (the profile first; the last back to the first when `closed`) of the larger size squared; the limit is 1,000,000, and the number of sections is limited on its own to 500. Sweep cost is the profile's units times the spine's units, a profile edge counting its poles (1 for any other curve) and a spine edge counting 1 plus its poles divided by ten, rounded down; the limit is 3,000. Measured on FreeCAD 1.1.4 (a development host). Loft recompute, smooth: circle to 1,000-gon 9.3 s and to 1,400-gon 20 s (a circle to an n-gon is the slowest layout); two 1,000-gons 5.7 s, two 1,400-gons 11 s, two 2,000-gons 24 s; 40 sections of 200 edges 4.6 s; 500 sections of 16 edges 0.64 s; 100 circles 0.09 s, 500 circles 1.6 s, 1,500 circles 19 s. Whole loft call at the limit: circle to 1,000-gon 13.2 s, two 1,000-gons 10.6 s, 500 sections of 44-gons (966,064, both limits; the slowest accepted loft) 13.7 s, 24 sections of 200 edges 5.2 s. Sweep recompute: 100 profile edges along 100 spine lines 5.8 s, 200 along 200 69 s, a circle along 5,000 lines 4.2 s (10,000 lines took 32 s through the tool), 250 edges along a 25-turn helix of 392 poles 18 s, a 200-pole BSpline profile along a 20-turn helix 1.3 s. Whole sweep call at the limit: a circle along 3,000 lines 9.3 s, 30 edges along 100 lines 2.5 s, 8 along 375 lines 2.3 s, 35 along a 25-turn helix of 770 poles (2,730) 1.1 s. The earlier edge-count model accepted two 3,999-gons, which took 111 s. Face count and edge count alone predict cost poorly, which is why a BSpline counts its poles and loft cost is quadratic.
- `sweep.degenerate_spine`. A BSpline spine that doubles back on itself has a point of zero velocity, and an `AdditivePipe` over one held the interpreter for more than 280 s (8 points through `x = 0.5 i cos(0.3 i)`, probed on 1.1.4; a spine of straight edges that reverse at a corner did not hang). Only BSpline-like spine edges are sampled (a line or an analytic curve cannot reverse), at 400 parameters each, or eight per pole when that is more (a long helix turns a quarter turn between two of 400 samples after about 100 turns, and a 120-turn `Part::Helix` builds valid in 0.85 s), for at most 100 such edges and 100,000 samples in all (more is `sweep.too_complex`), and the cost check runs first; two consecutive tangents with a negative dot product, or a sample with no tangent, refuse the call. A BSpline edge that turns more than 90 degrees between two samples is refused for the same reason. A zero-velocity point without a reversal is not detected. The reversing BSpline reads dot = -1.0; a helix, a sine curve, a hairpin, a circle and a 100-segment polyline stay above 0.98.

`preview_dry_run` accepts both tools: `preview_op_table` derives the table from the `feature_` spec list.

### 3.7.5 `feature_part_primitive` and `feature_part_boolean`

```json
{ "feature_part_primitive": { "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "kind": { "enum": ["box", "cylinder", "cone", "sphere", "torus"] },
    "name": { "type": "string" },
    "length": { "$ref": "#/$defs/Quantity", "description": "box" },
    "width": { "$ref": "#/$defs/Quantity", "description": "box" },
    "height": { "$ref": "#/$defs/Quantity", "description": "box, cylinder, cone" },
    "radius": { "$ref": "#/$defs/Quantity", "description": "cylinder, sphere" },
    "radius1": { "$ref": "#/$defs/Quantity", "description": "cone base radius; torus ring radius" },
    "radius2": { "$ref": "#/$defs/Quantity", "description": "cone top radius; torus tube radius" },
    "placement": { "type": "object", "description": "{base: {x, y, z}, rotation: {axis, angle}}; an omitted key keeps the default of a new object" },
    "confirm": { "$ref": "#/$defs/Confirm" }
  }, "required": ["doc", "kind", "name"] } },
  "feature_part_boolean": { "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "operation": { "enum": ["cut", "fuse", "common"] },
    "base": { "type": "string", "description": "top-level object Name" },
    "tools": { "type": "array", "items": { "type": "string" }, "minItems": 1, "maxItems": 20 },
    "name": { "type": "string" },
    "refine": { "type": "boolean", "default": true },
    "confirm": { "$ref": "#/$defs/Confirm" }
  }, "required": ["doc", "operation", "base", "tools", "name"] } } }
```

Both tools run in one AD-5 bracket, return `feature` and `feature_state` like every `feature_*` tool, and never call the PartDesign gate: they need only the `Part` module. They build `Part::` objects at document level, outside any Body. `preview_dry_run` accepts both.

`feature_part_primitive` makes one `Part::Box`, `Cylinder`, `Cone`, `Sphere` or `Torus` named `name` (Name and Label). Each kind takes only its own fields (`length`, `width`, `height` for a box; `radius`, `height` for a cylinder; `radius1`, `radius2`, `height` for a cone; `radius` for a sphere; `radius1`, `radius2` for a torus); the others are refused. The `Angle*` properties stay at FreeCAD's full-turn default. `placement` uses the value shape of `feature_set_parameters` and its parser.

`feature_part_boolean` builds, for one tool, `Part::Cut`, `Part::Fuse` or `Part::Common`; for several tools, `Part::MultiFuse` or `Part::MultiCommon` over the base then the tools (the common is the intersection of all). A cut by several tools is a `Part::Cut` of the base by a `Part::MultiFuse` named `<name>_tools`. `Refine` is set from `refine` on every object made, because FreeCAD otherwise reads it from the user preference `Mod/Part/Boolean/RefineModel`. The inputs and the intermediate fuse get `Visibility` false inside the transaction, as `ViewProviderBoolean.cpp` does in a GUI session, so a headless call reads the same and `document_undo` restores it.

Refusals (`INVALID_INPUT`, before the bracket, with a `detail.code`):

- `part_primitive.fields`: a field the kind does not take, or a field it needs is missing. `part_primitive.dimension`: a size at or below 0 (a cone radius may be 0), a cone with both radii 0, a torus with `radius2` not below `radius1`.
- `part_boolean.invalid_input`: `tools` not a list of 1 to 20 Names, or an input named twice (the base inside `tools`).
- `part_boolean.not_top_level`: an input whose `getParentGeoFeatureGroup()` is not `None` (a Body feature, a sketch inside a Body, a member of an `App::Part`). A Body itself is allowed.
- `part_boolean.untrusted_shape`: an input that is not valid, not made only of solids, or holds a solid of volume 0 or less. On FreeCAD 1.1.4 a reversed solid made `Part::Cut` return 1500 where 500 is right and `Part::Fuse` return 500 where 1500 is right, and a self-intersecting solid made `Part::Common` return an empty compound, all with status `Valid`. The check is `usecases/shape_trust.py`, shared with `query_interference`.
- `part_boolean.too_complex`: inputs above 3,000 faces in total, or above 1,000 base-solid by tool-solid pairs. Face count alone does not bound the cost: a box cut by 1,000 disjoint cylinders (3,006 faces) took 8.9 s, the common of two families of 36 crossing cylinders (216 faces, 1,296 pairs) took 37.7 s, and the OCC call holds the interpreter lock, so the 120 s timeout cannot stop it. The worst measured case under both limits is about 22 s.

FreeCAD reports an empty or invalid boolean result as up to date (a common of disjoint or touching solids and a cut that removes everything give a `Compound` with no solid and status `Valid`), so after the recompute the tool checks the result and ends `RECOMPUTE_ERROR` with a proven rollback: `part_boolean.empty_result` for no solid or a solid of volume 0 or less, `part_boolean.invalid_result` when `isValid()` is false. A fuse of disjoint solids gives several solids and is accepted. The rollback proof reads the `Visibility` of every object back, because the AD-6 fingerprint sees shapes only.

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

A sketch with no style `color` and no highlight renders its lines in #212529, whatever its own line colour or the `SketchEdgeColor` preference. FreeCAD's default sketch line is white, which does not show on the white render background. A style `color` or a highlight still sets the colour.

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
    "elicitation_action": { "enum": ["accept"], "description": "recorded outcome; decline/cancel never reach the mutation tool" }
  },
  "required": ["preview_id"], "additionalProperties": false
} }
```

`Confirm` carries no auto-approve field: the posture is the operator env var `FREECAD_BUDDY_AUTO_APPROVE`, read once at host start, and a client-sent `autoApprove` is refused as an undeclared field. The posture is on by default in every host; `FREECAD_BUDDY_AUTO_APPROVE=0` makes every mutation a confirm-required call, except the display-state carve-out (§1.4). A call that sends `confirm` takes the full token check in every posture: a stale, expired or forged `preview_id` is refused, and an accepted one is logged `preview_token`. Phase 2 policy: mutation tool called without valid `confirm` in a confirm-required context → `INVALID_INPUT`, no execution. GUI panel and MCP elicitation produce the `accept`. `preview_dry_run` stays available in both postures. Apply re-runs the operation on the live document under AD-5 — the preview result is never "promoted" to the live doc.

## 5. `script_exec` Registration Rules (AD-4)

1. **On by default.** Registered unless the operator sets `FREECAD_BUDDY_SCRIPT_EXEC` to a value other than `1`, or — GUI host, variable unset — clears the **Allow script_exec** preference (`ScriptExec`). When off it is *unregistered*: absent from `tools/list`, not present-and-refusing.
2. **Unattended runs.** With `FREECAD_BUDDY_UNATTENDED=1` it is unregistered unless `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`. Both variables are read once at start, env only; exactly `"1"` is on.
3. **Typed tools first.** Excluded from `preview_dry_run.operation.tool`, from the confirm flow, from the read-only assistant profile, and from every benchmark and gate toolset. G1.6/registry introspection must show zero mutation tools *and* no `script_exec` in the read-only profile. `FREECAD_BUDDY_AUTO_APPROVE` does not gate it; an operator who wants per-call control turns `ScriptExec` off.
4. **Observe-only bracket (AD-5).** The bridge fingerprints, opens its transaction before the script runs, recomputes unless `recompute` is false, commits, fingerprints again, and lists `changed` and `new_errors`. No post-verify or TNP audit, and no rollback for a call that finishes inside its time budget: the changes stay. Statuses: `OK`; `RECOMPUTE_ERROR` when new objects are in error (the message names them); `INVALID_INPUT` with `detail.code` `exec.python_error` (`data.exception`, `data.traceback`) when the script raised, partial changes kept (the one `INVALID_INPUT` where the code ran; `detail.code` tells it from a refusal before execution); `TIMEOUT` as AD-27. `changed` lists the objects whose geometric invariants differ (AD-6); a property-only change is not listed. The transaction is named `script_exec ` plus the first non-blank code line, stripped and cut to 80 characters (`script_exec` alone when no line is non-blank). After the commit the bridge commits the application-level transaction when one is still open: a read-only script, or one that changed only another document, leaves it open, and the next change by any caller would join it and take its name. A script that opens its own transaction splits the undo history, so one `document_undo` then reverts only the last part (`undo_steps` counts the entries). A script that commits the bridge transaction and then writes leaves those writes unrecorded; a script that closes its document leaves a stale handle (`OK`, `fingerprint_after` null, `changed` and `new_errors` empty). A script that changes another document leaves `changed` empty and `undo_steps` 0 for `doc`; the other document holds one entry named after the script, and its own `document_undo` reverts it. `undo_steps` 0 means one `document_undo` would revert an earlier step; it is counted by aligning the undo list before and after, so it has two limits: repeated names can undercount (a script that calls `doc.undo()` and whose first line matches an earlier entry on a short stack), and a full stack (20 entries) can overcount (20 reported for a call that added 2). A full stack whose 20 entries all carry one name gives `undo_steps` null with a note, because a write and a read-only script leave the same list. A script that calls `doc.undo()` (the undone entries are gone from the list) gets a note that `document_undo` cannot restore the state before the call, an exception to "one `document_undo` reverts the script"; a script that clears the undo list or sets `UndoMode` 0 gets `undo_steps` 0 with a note that says so. The captured stdout survives `sys.stdout.close()`, and every conversion of a script-owned object to text after the commit (`repr(result)`, `str(exception)`) catches `BaseException`, so a `SystemExit` there never reaches the serve loop. A failed bracket phase has its own result: `fingerprint_before` failing gives `SPEC_FAILED` (`exec.bracket_failed`, `data.phase` `fingerprint_before`) and the script is not run; the recompute, the commit, `fingerprint_after` or the reads that follow (`observe`) failing after the script gives `RECOMPUTE_ERROR` (`exec.bracket_failed`, `data.phase`), the changes stay and `fingerprint_after` is null (it keeps its value for `observe`). A failing read before the script (`invalid_objects`, the undo list) gives `SPEC_FAILED` with `data.phase` `observe_before`. When the recompute and the commit both fail, `data.phase` names the first and the message names both. `undo_steps` is the smaller of two list alignments (a full stack drops its oldest entry; a script that undid entries and recorded its own keeps the tail), and is null when the undo list cannot be read. The handler catches `BaseException` around the script, so `SystemExit` gives `INVALID_INPUT` and never ends the serve loop. The `script_exec` envelope skips the AD-32 framing cache (one projection per call), because a `Visibility` change does not move the fingerprint the cache keys on. With `recompute` false no recompute runs: `changed`, `new_errors` and `fingerprint_after` read the objects as the script left them, so `new_errors` can be empty and the status `OK` on a document that fails at its next recompute. When the script raised, the bracket still recomputes (unless `recompute` is false), commits and fingerprints; `INVALID_INPUT` takes precedence over `RECOMPUTE_ERROR`, `new_errors` still lists the objects, and `data.bracket_phase` names a bracket phase (`recompute`, `commit`, `fingerprint_after` or `observe`) that failed as well, with its exception text in `data.bracket_message`. The note "the changes it made so far are kept" appears only when `changed` is not empty. The commit runs even when the recompute raised, so no transaction stays open. With `recompute` unset the bracket recomputes whenever any object of the document is Touched, so a read-only probe on a document with a Touched object recomputes it: such a probe passes `recompute: false`. `mutating=True`, so a `TIMEOUT` marks the document suspect and the call writes an audit pair.
5. **Audited.** Every call appends a `before` record carrying the full source ahead of execution, and an `after` record (AD-17).
6. **Not a sandbox.** Namespace reduction (FreeCAD API globals only) is hygiene, never described as a security boundary; this repository ships no isolation boundary, so the operator's environment is the only one (AD-35, exec-sandbox research Finding 1).
7. Input `{ "doc": handle, "code": string, "recompute"?: boolean }` (`recompute` defaults to true); result `{ "doc", "stdout", "value_repr", "fingerprint_before", "fingerprint_after", "changed", "new_errors", "undo_steps" }`. The result is flat (it has no `mutation` block): both fingerprints are top-level bare digest strings, as in the other flat lifecycle tools (both come from one call, so they share one serializer), so the AD-32 framing cache key keeps reading `fingerprint_after`; `changed` entries are shaped as in the §1.4 `mutation` block. `value_repr` is `<repr failed: <Type>: <message>>` (and a note names it) when the repr of `result` raises, as it does for an object the script deleted; the status stays as the bracket decides. The fields are present for every call that ran the script (`OK`, `RECOMPUTE_ERROR`, `INVALID_INPUT` with `exec.python_error`). A refusal before execution, `SPEC_FAILED` from the `fingerprint_before` phase and a `TIMEOUT` carry none of them. It requires an explicit doc handle (AD-20).

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
