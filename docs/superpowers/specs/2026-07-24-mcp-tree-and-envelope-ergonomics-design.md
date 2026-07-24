# MCP Tree & Envelope Ergonomics — Design

**Date:** 2026-07-24
**Status:** Approved (brainstorm), ready for implementation plan
**Scope:** Read-only query surface (`query_tree_summary`) + the shared result envelope (`text` field). Also records two fixes already shipped this session (screenshot dirty-doc handling, 1920 render default).

## Problem

Driving the live GUI (h96max PCB, 201-object assembly) surfaced three ergonomics failures:

1. **Tree dump is unusable at scale.** `query_tree_summary` returns a flat list of every object. On the real doc that was 54 KB / 201 nodes — it **exceeded the tool-result token limit**, forcing a subagent + file-parse just to learn which objects to render. ~90 of those rows were datum clutter (App::Plane/Line/Point/Origin) nobody navigates.
2. **No `Visibility` in the tree.** To learn which parts were enabled (vs hidden), each candidate had to be fetched individually via `query_object`. The single most-needed field for a render decision was absent from the tree.
3. **Containment/duplication invisible.** The doc held two copies of every part — a standalone `App::Part`/`Body` and an `App::Link` instance inside the `Assembly`. Nothing in the output signalled the duplication or the assembly membership; it was reverse-engineered from TypeIds and label suffixes.

Separately, every result envelope ships its payload up to three times: MCP's top-level `structuredContent`, the contract's `structured_content`, and `text` — where `text` is `mirror_text(structured)`, a re-serialized JSON *copy* of the same object. The `text` field carries no signal a machine client doesn't already have in `structured_content`, and it inflates context.

## Goals

- An agent can get the object tree **effectively**: small by default, drill-down on demand, no context blow-up.
- An agent can understand the **assembly structure** (containment, link-instances vs standalone parts, visibility, per-node errors) from one call.
- The envelope `text` field carries a **human/LLM summary**, not a JSON re-dump.

Non-goals: changing the wire types of other query tools; changing the render pipeline (already handled); a graph/query language over the tree.

## Design

### 1. `query_tree_summary` — depth-controlled, filterable, nested

Replace the flat all-objects dump with an explore-then-expand model.

**Parameters**

| Param | Type | Default | Meaning |
|-------|------|---------|---------|
| `doc` | handle | — | required |
| `depth` | int ≥ 1 | `1` | how many levels to expand. `depth=1` = top-level containers only. |
| `root` | object name | none | expand the subtree under this object instead of the document roots |
| `filters` | object | see below | AND-stacked node filters |

**Filters (all optional, AND-stacked — a node must pass every provided filter):**

| Filter | Type | Purpose |
|--------|------|---------|
| `types` | string[] | include only these TypeIds |
| `exclude_types` | string[] | drop these TypeIds. **Defaults to the datum/origin clutter set** (`App::Plane`, `App::Line`, `App::Point`, `App::Origin`) so the common case is clean; pass an explicit `exclude_types` (or `[]`) to override. |
| `renderable_only` | bool | shape-bearing objects only — reuses the renderer's skip-set (`_NON_RENDER_TYPE_PREFIXES` / `_NON_RENDER_TYPES` from `usecases/screenshot.py`), i.e. "what I would screenshot" |
| `visible_only` | bool | `Visibility == true` only |
| `name_pattern` | string | substring/regex match on `name` or `label` |

Filtering prunes a node from the output; a pruned parent still expands its surviving descendants (filtering hides nodes, not whole subtrees, unless a subtree has no surviving nodes).

**Depth controls both `children` and `links` expansion.** At the depth boundary a node's descendants are not listed — only their counts are reported. Expanding deeper (higher `depth`, or `root` at that node) materializes the arrays.

**Node shape — sparse (a field appears only when it carries a value):**

Always present (core identity + the load-bearing render signal):
- `name`, `label`, `type`, `visibility`

Present only when non-empty / non-null / non-zero:
- `error` — the object's `getStatusString()` when it did not compute cleanly (e.g. `"Broken link in: Reference1"`); omitted when clean.
- `children` — structural (non-Link) child nodes, listed only when expanded at this depth.
- `children_count` — count of structural children; omitted when `0`.
- `links` — `App::Link` instance child nodes, listed only when expanded at this depth. **Links are a separate category from `children`** so an assembly's link-instances don't mix with its structural children.
- `links_count` — count of `App::Link` children; omitted when `0`.

Rationale for separating `links`: an `Assembly` (or any container) holds its placed instances as `App::Link` objects distinct from its structural/feature children. Keeping them in a separate array makes "these are the assembly members" legible without type-sniffing every child.

**Envelope-level structured_content fields:**
- `doc`, `total_objects` (full count in the document), `returned_nodes` (count after depth+filter), `depth`, `filters_applied` (echo of the effective filters incl. defaulted `exclude_types`), `tree` (the node array).

**Example** — `query_tree_summary(doc, depth=2, filters={renderable_only: true})` on the h96max doc:

```json
{
  "schema": "fcb.result-envelope/1",
  "status": "OK",
  "structured_content": {
    "doc": "fcb-doc:…",
    "total_objects": 201,
    "returned_nodes": 14,
    "depth": 2,
    "filters_applied": { "renderable_only": true, "exclude_types": ["App::Plane","App::Line","App::Point","App::Origin"] },
    "tree": [
      {
        "name": "Assembly", "label": "h96max-mainboard", "type": "Assembly::AssemblyObject", "visibility": true,
        "links_count": 11,
        "links": [
          { "name": "pcb",     "label": "pcb001",    "type": "App::Link", "visibility": true },
          { "name": "USB_3_0", "label": "USB 3.001", "type": "App::Link", "visibility": true },
          { "name": "HDMI",    "label": "HDMI001",   "type": "App::Link", "visibility": true },
          { "name": "RJ45",    "label": "RJ001",     "type": "App::Link", "visibility": true }
        ],
        "children_count": 2,
        "children": [
          { "name": "Joint002", "label": "Master Sketch004", "type": "App::FeaturePython", "visibility": true, "error": "Broken link in: Reference1" }
        ]
      },
      { "name": "Body", "label": "pcb",     "type": "PartDesign::Body", "visibility": true, "children_count": 7 },
      { "name": "_1",   "label": "USB 3.0", "type": "App::Part",        "visibility": true, "children_count": 4 }
    ]
  },
  "text": "h96max-board: 201 objects. Assembly 'h96max-mainboard' = 11 link-instances (all visible) + 2 joints (Joint002 broken: Reference1). 10 standalone parts also visible — duplicates of the assembly links. Showing 2 levels, renderable-only."
}
```

Sparse rule visible above: the `pcb`/`USB_3_0` leaves carry only the 4 core fields; `Body`/`_1` show `children_count` but no `children` array (unexpanded at the depth boundary); `Joint002` carries `error`; a healthy joint would not.

**Duplicate hint.** Standalone-vs-linked duplication is surfaced in the `text` summary (see §2), not as a structured field — the agent reads it from the summary rather than the tool computing a formal duplicate graph. (Deferred: a structured `duplicate_of` cross-reference, if a later need arises.)

**Tree payload is an untyped structured dict (decided 2026-07-24).** The tree node/summary shape ships as a plain `dict` inside `ResultEnvelope.structured_content`, covered by the in-FreeCAD behavioral tests — NOT by a generated `fcb.tree/1` JSON schema. This deviates from the earlier "contracts-owned typed contract" intent below: the sparse, recursive, filter-dependent node shape (fields present or absent per depth/state) is awkward to pin as a single static TypedDict, and the same untyped-payload posture already covers `query_object`'s heterogeneous `properties`. A typed `contracts/tree.py` + drift-checked schema can be added later if a cross-file consumer needs it.

### 2. Envelope `text` — per-tool human summary (all tools)

Replace the generic `mirror_text(structured) = json.dumps(structured)` with a **per-tool summary string**: one line of human/LLM-readable signal, never a JSON re-dump.

- Rationale: a machine client already has the data in `structured_content` (and MCP's `structuredContent`); a client that reads only `content`/`text` should get *signal* — counts, the headline value, error flags — not a redundant blob. Cuts context waste and makes the `content` block useful.
- **Scope: all ~23 tools.** Each tool owns a small summary builder that turns its own `structured_content` into one line. Examples:
  - `query_tree_summary`: `"h96max-board: 201 objects. Assembly … 11 link-instances … Joint002 broken."`
  - `query_mass_properties`: `"Body 'pcb': volume 8642.85 mm³, 15 faces, watertight solid."`
  - `query_screenshot`: `"Rendered 11 objects (iso, 1920×1920). Document dirty (pending/broken recompute)."`
  - `verify_recompute`: `"RECOMPUTE_ERROR: 3 failing objects (Assembly, Joints, Joint002: broken link)."`
  - `verify_shape`: `"SPEC_FAILED: volume 8642.85 mm³ vs expected 6000 (rel 0.44)."`
- Structure: `mirror_text` stops being the single generic producer. The envelope builder accepts a `summary` string; each usecase's `_ok_envelope`/`_error_envelope` passes the tool-specific summary. A shared fallback (compact `key: value` flattening) covers any envelope that does not supply one, so no tool ever regresses to a raw JSON dump.
- Error envelopes summarize the failure (status + the decisive reason), not the machine detail.

### 3. Already shipped this session (recorded, not re-implemented)

- **Screenshot renders dirty/broken-recompute documents.** The read-only guard (`massprops before == after`) hard-errored on a document whose own pending/broken recompute churned geometry between fingerprints. Fix: `_document_is_dirty(document)` (checks `obj.State` for `Touched`/`Invalid`/`Error`); a dirty document skips the mutation assertion and renders with `render.dirty_document: true`; a clean document keeps the strict read-only guard. (`usecases/screenshot.py`; 2 infc tests; 77/77 pass.)
- **Render default + cap raised to 1920×1920.** `_MAX_DIM`/`_DEFAULT_WIDTH`/`_DEFAULT_HEIGHT` and the `tool_catalog` schema `width`/`height` default+maximum moved from 800/600/1024 to 1920. (`test_mcp_surface` updated; 26/26 pass.)

## Impact / touch points

- `usecases/queries.py` — `query_tree_summary` rewrite (depth, filters, nesting, links split, sparse nodes, inline error, visibility).
- ~~`contracts/tree.py` (new or extended) — the `fcb.tree/1` node + envelope TypedDicts; generated JSON schema regenerated + drift-checked.~~ **Not built** — the tree payload ships as an untyped structured dict (see the decision note in §1); no `fcb.tree/1` schema, no drift check on the node shape.
- `hosts/tool_catalog.py` — `query_tree_summary` input schema (add `depth`, `root`, `filters`); the `renderable_only` filter shares the renderer's skip-set (factor that set to a spot both modules import, respecting ring direction — the set is data, place it where `usecases/` can own it and `screenshot.py` already lives).
- `contracts/envelope.py` — envelope builder accepts a `summary`; `mirror_text` demoted to the generic fallback.
- All ~23 tool usecases — each supplies its one-line summary builder.
- Tests: `tests/infc/` (tree against a real multi-level doc: depth, filters, links/children split, sparse fields, error surfacing, visibility) and `tests/external/` (schema surface, per-tool summary strings, envelope fallback).

## Open decisions carried forward (deferred, not blocking)

- Structured `duplicate_of` cross-reference on nodes (currently only the `text` hint).
- Whether `name_pattern` is substring or full regex (implementation detail; default substring, regex if cheap).

## Testing strategy

- **Tree:** build a fixture doc with an Assembly of App::Link instances over standalone Bodies plus a deliberately broken link (mirrors h96max). Assert: `depth=1` returns only roots with counts; `depth=2` expands one level; `links` vs `children` correctly partitioned; `renderable_only` and `exclude_types` default prune datums; `visible_only` filters hidden objects; sparse fields omitted when empty; `error` present only on the broken node; `visibility` present on every node.
- **Envelope:** each tool's summary asserted against a known result; the generic fallback asserted for an envelope with no supplied summary; no envelope emits a full JSON dump in `text`.
- Ordering: contracts/schema first (fail honestly against a stub), then usecase, then host schema, per the ring-inward build order.
