---
title: 'Story 1.5 — Read-Only Query Tools'
type: 'feature'
created: '2026-07-22'
status: 'done'
baseline_revision: '75da922788be85d42ab12780d68b48c90c615f17'
final_revision: '8d6fc15'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/project-context.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** Story 1.4 landed the MCP surface, the document registry, and `query_capabilities`, but the model is otherwise opaque: no way to read the feature tree, an object's properties/error state, mass properties, dependency edges, sketch geometry/constraints, or placements. Every Phase-1 assistant flow and the G0 gate's "17 query/document/export tools" count depend on this read-only surface (mcp-tools §2 `query_`).

**Approach:** Add the six Phase-0 read-only `query_*` tools to `usecases/queries.py` (`query_tree_summary`, `query_object`, `query_mass_properties`, `query_dependencies`, `query_sketch_info`, `query_placement`), each targeting a document by explicit handle through the existing `DocumentRegistry`, returning a `ResultEnvelope` with a per-tool `structured_content` payload. Register them in `build_registry` as non-mutating (`mutating=False`, un-audited) tools. `query_tree_summary` is large-tree-safe via a `max_nodes` hard cap + `truncated` flag. All tools are strictly read-only: no `recompute()`, no property writes, no viewport touch — document state is unchanged across any call.

## Boundaries & Constraints

**Always:**
- Ring discipline (AD-1): tool impls live in `usecases/queries.py` (stdlib + FreeCAD App API only, FreeCAD imported lazily inside functions); registration in `hosts/headless/entry.py`. `check_imports.py` stays green.
- Explicit handle only (AD-20): every query takes a `doc` handle resolved through `DocumentRegistry`; a missing/stale/unknown handle → `INVALID_INPUT` via the existing `ValidationError` → dispatch boundary. `ActiveDocument` is never targeted. Resolve the object by immutable `Name`; never key logic on `Label`.
- Strictly read-only: no `recompute()`, no transaction, no property mutation, no `Visibility`/viewport change. The document fingerprint before a query equals the fingerprint after. Tools are `mutating=False` and NOT audit-logged (audit is mutation/exec only).
- Reuse existing infrastructure: return the contracts-owned `ResultEnvelope` (`fcb.result-envelope/1`) built with the module's `_ok_envelope`/`mirror_text` helpers; the shared envelope `outputSchema`; each tool's `structured_content` matches the mcp-tools §3.2 / §2 documented result shape. No new wire types, no new jsonschema files.
- Units are explicit `{ "value": <number>, "unit": <str> }` Quantity objects on every dimensional field (mass properties, sketch constraint values, placement angle) — internal units mm/deg (project-context Units).
- Large-tree safety (mcp-tools §3.2): `query_tree_summary` accepts `max_depth` (default 2) and `max_nodes` (default 100, hard cap); output carries `total_objects` and `truncated` (true when the cap clipped the tree). Never emit a raw unbounded dump.
- Error states: object error is reported via `getStatusString()` (string, or null when clean), never inferred from raw `State` flags in the tool's public payload.
- In-FreeCAD behavior is tested under FreeCADCmd in `tests/infc/` (stdlib `unittest`); the surface/registration/schema/read-only-guarantee behaviors that need no live FreeCAD are tested in `tests/external/` under pytest.

**Block If:**
- The installed FreeCAD build exposes no usable mass-properties API on `Part.Shape` (neither `Shape.Volume`/`Shape.Area`/`Shape.BoundBox`/`Shape.CenterOfMass` nor an equivalent) so `query_mass_properties` cannot be implemented against a real solid — HALT with the probed API surface. (Do not fabricate values.)

**Never:**
- No mutation of any kind, no `recompute()` inside a query (if the model is dirty, report what is currently stored; do not refresh it).
- No new `query_` tools beyond the six in scope: `query_capabilities` already shipped (Story 1.4); `query_screenshot`/render is Story 1.9; `query_tree_children`/`query_parameters` are Phase 1.
- No new contract types or jsonschema files; no per-tool `outputSchema` divergence from the shared envelope schema (the documented result shape lives in `structured_content`, validated by the story's tests, not by a new wire schema).
- No selector resolution engine and no stored bare sub-element names — `query_sketch_info` reports sketch-local geometry/constraint listings only (geometry by index/`geo_id`, constraints by 1-based solver id); it does not resolve TNP mapped names.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| tree summary, small doc | `query_tree_summary{doc}` on a doc with a few objects | `status=OK`; `structured_content` = `{nodes:[{name,label,type,children_count,error}], total_objects, truncated:false}` | — |
| tree summary, cap hit | `query_tree_summary{doc, max_nodes:1}` on a multi-object doc | `nodes` length ≤ 1; `truncated:true`; `total_objects` = full count | — |
| object properties | `query_object{doc, object}` on an existing object | `status=OK`; `{name,label,type,properties:{...},error}` where `error` is `getStatusString()` or null | — |
| object not found | `query_object{doc, object:"Nope"}` | `INVALID_INPUT` | fail-closed |
| mass properties | `query_mass_properties{doc, object}` on a solid | `{name, volume:{value,unit}, area:{value,unit}, bbox, com:{...}, counts:{faces,edges,solids}}`, all dimensional fields carry units | — |
| mass props, no shape | `query_mass_properties{doc, object}` on an object with no `Shape` | `INVALID_INPUT` (object has no queryable geometry) | fail-closed |
| dependencies (object) | `query_dependencies{doc, object}` | `{object, in_list:[names], out_list:[names]}` | — |
| dependencies (whole doc) | `query_dependencies{doc}` (no object) | `{edges:[{from,to}]}` for every object's OutList | — |
| sketch info | `query_sketch_info{doc, sketch}` on a Sketcher::SketchObject | `{sketch, geometry:[{index,type,construction}], constraints:[{id,type,name,value,driving}]}`, values carry units | — |
| sketch info, not a sketch | `query_sketch_info{doc, sketch}` on a non-sketch object | `INVALID_INPUT` | fail-closed |
| placement | `query_placement{doc, object}` | `{object, local:{position,axis,angle:{value,unit}}, global:{...}}` | — |
| stale/unknown/missing handle | any query with a bad or omitted `doc` | `INVALID_INPUT` | fail-closed |
| read-only guarantee | any query on a doc | document fingerprint before == after; no object added/removed/recomputed | — |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/queries.py` -- EXTEND. Add the six read-only query functions. Each takes a `DocumentRegistry` + `doc` handle (resolve via `registry.with_document(doc, fn)` so the read runs under the registry lock without touching privates) plus tool params, and returns `ResultEnvelope`. Reuse a local `_ok_envelope` helper (mirror the one in `documents.py`) or import the shared builder. Raise `ValidationError` (from `usecases.documents`) for unknown object / non-sketch / no-shape so dispatch maps them to `INVALID_INPUT`. FreeCAD imported lazily where a type check is needed (mostly attribute access suffices — no direct import required).
- `src/freecad_buddy/hosts/headless/entry.py` -- EXTEND `build_registry`: register the six tools as `RpcMethod(mutating=False)` with hand-authored `inputSchema` (each requires `doc`; `query_tree_summary` adds optional `max_depth`/`max_nodes`; the object-scoped tools require their `object`/`sketch` field; `query_dependencies.object` optional; `additionalProperties:false`), the shared envelope `outputSchema` (via `_tool_for`), and a one-line description. Handlers wrap `registry`-bound query functions via the existing `marshaled` helper.
- `tests/external/test_mcp_surface.py` -- UPDATE the `tools/list` expectation: the exec-off surface now includes the six new query tools (fix `test_tools_list_exec_off_lists_six_document_plus_query`'s exact-set assertion). Add a check that each new tool has `doc` in its `inputSchema.required` and `additionalProperties:false`. Assert dispatch of a query with a bad handle → `INVALID_INPUT` (registry-backed, real handler).
- `tests/infc/test_query_tools.py` -- NEW stdlib `unittest` under FreeCADCmd. Build a small real document (a box + a fully-constrained sketch), then assert: tree summary shape + `truncated` under a low `max_nodes`; `query_object` properties + null error on a clean object; `query_mass_properties` volume within ±0.1% of the analytic box volume with correct units and topology counts; `query_dependencies` object + whole-doc edges; `query_sketch_info` geometry + constraint listing with driving flags; `query_placement` local/global; unknown object / non-sketch / no-shape → `INVALID_INPUT`; and a read-only guarantee (object count and a fingerprint-ish signature unchanged across a full query sweep, no recompute triggered).

## Tasks & Acceptance

**Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)**
  - Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md` (if present; else the project-context distillation governs).
  - Re-read `mcp-tools-design.md` §1.1 (handles), §1.2 (selectors/Quantity), §1.3 (envelope), §2 (`query_` inventory), §3.2 (`query_tree_summary` schema); `data-contracts-design.md` (ResultEnvelope/DocHandle); `component-design.md` (ring placement of `query_` in usecases).
  - Re-read `project-context.md` "Architecture Ring & Import Rules", "FreeCAD API Traps" (ActiveDocument banned, Name vs Label, no read without recompute assumptions), "Wire & Schema Rules", "Units".
  - Load `typescript-clean-code` (naming/commenting discipline, applied to Python).
  - Read the Story 1.4 spec's Design Notes + `usecases/queries.py`, `usecases/documents.py`, `hosts/headless/entry.py`, `tests/infc/test_document_lifecycle.py`, `tests/external/test_mcp_surface.py` for the established pattern.

**Execution:**
- [x] `src/freecad_buddy/usecases/queries.py` -- add `query_tree_summary`, `query_object`, `query_mass_properties`, `query_dependencies`, `query_sketch_info`, `query_placement`; registry-resolved, read-only, unit-carrying, `ValidationError` on bad object/sketch/shape. -- read-only model observability (AD-20, mcp-tools §2).
- [x] `src/freecad_buddy/hosts/headless/entry.py` -- register the six tools in `build_registry` (`mutating=False`, per-tool inputSchema, `additionalProperties:false`, docstring). -- surface exposure / G0.2 tool count.
- [x] `tests/infc/test_query_tools.py` -- FreeCADCmd suite over a real box + sketch: every tool's shape, the mass-props golden (±0.1%), the cap/`truncated` path, the `INVALID_INPUT` cases, and the read-only guarantee. -- AC coverage (non-tautological: golden volume from analytic box, not from the impl).
- [x] `tests/external/test_mcp_surface.py` -- update the exact tool-set assertion; assert the new tools' schemas require `doc` and reject unknown keys; bad-handle dispatch → `INVALID_INPUT`. -- surface/schema regression guard.

**Final Task: Quality Checks**
- [x] `uv run python scripts/check_imports.py` -- rings clean.
- [x] `uv run ruff check .` -- clean (T201 print-ban honored).
- [x] `uv run ruff format` (changed files) -- formatted.
- [x] `uv run pytest tests/external -q` -- all green.
- [x] `"FreeCADCmd" tests/run_tests.py` -- infc query suite + prior lifecycle/probe suites green (local FreeCAD 1.1). If FreeCADCmd is unavailable locally, report it and rely on the CI legs.

**Acceptance Criteria:**
- Given `tools/list` with `FREECAD_BUDDY_ALLOW_EXEC` unset, when enumerated, then the surface lists the six `document_*` + `query_capabilities` + the six new `query_*` tools, each with a JSON `inputSchema` requiring `doc` (except `query_dependencies` where `object` is optional), the shared envelope `outputSchema`, a description, and underscore names.
- Given an open document with a box and a fully-constrained sketch, when each of the six query tools is called with the correct handle and object, then each returns `status=OK` with the documented `structured_content` shape; `query_mass_properties` volume matches the analytic box volume within ±0.1% and carries explicit units; `query_sketch_info` lists the constraints with their driving flags.
- Given `query_tree_summary` with `max_nodes` smaller than the object count, when called, then `nodes` is capped, `truncated=true`, and `total_objects` reports the full count.
- Given a query with a missing, stale, or unknown `doc` handle, or an unknown object / non-sketch object / object without a `Shape`, when dispatched, then the result is `INVALID_INPUT` (fail-closed); `ActiveDocument` is never targeted.
- Given any query call, when it completes, then the document is unchanged — no object added/removed, no `recompute()` triggered, no property or viewport mutation (read-only guarantee).

## Spec Change Log

## Review Triage Log

### 2026-07-22 — Review pass (follow-up)
- intent_gap: 0
- bad_spec: 0
- patch: 2: (high 0, medium 0, low 2)
- defer: 3
- reject: 13
- addressed_findings:
  - `[low]` `[patch]` `query_placement` guarded only an *exception* from `getGlobalPlacement()`; a build returning `None` (not raising) fell through to `_placement_dict(None)` → `AttributeError` → `RECOMPUTE_ERROR`. Added a `None`-return guard that falls back to the local placement, matching the docstring's "when available, else the local placement".
  - `[low]` `[patch]` `query_sketch_info` dropped a constraint's `value` entirely when its `Type` was neither a known angle nor a known length type, so a dimensional-but-unlisted constraint lost information silently. Now emits the raw value with `unit: null` (`_quantity(value, None)`) so the number survives even when the unit is unknown.
- deferred_findings:
  - non-solid `query_mass_properties` (shell/wire) reports volume 0 / non-volumetric `CenterOfMass` and a degenerate compound can raise `RECOMPUTE_ERROR` instead of fail-closed `INVALID_INPUT` — real robustness gap, unverified branch, not a spec'd requirement (edge matrix only covers "no Shape").
  - `_json_safe` has no recursion depth / cycle bound — hostile or scripted-object cyclic property value could `RecursionError`; no live object triggers it in Phase 0.
  - `query_dependencies` whole-doc `edges` uncapped (already logged under a prior 1.5 entry; re-surfaced, not re-logged).
- rejected (noise / by-design / spec-sanctioned): `getGlobalPlacement` broad-except "masks side effects" (fallback is spec'd); mm-unit "asserted not derived" (internal units ARE mm/deg by project-context); `query_object` property getters "break read-only" (spec explicitly returns property values; exceptions already swallowed); negative `max_nodes` "silent 0" (schema `minimum:0` blocks at wire); sketch `type(geo).__name__` "brittle" (spec says type name); `object` param shadow + `TypeError`→`INVALID_INPUT` "masks bugs" (by-design dispatch contract); read holds mutation lock (by-design per Design Notes); `Touched`→clean "stale shape" (query must not recompute — reporting stored values is spec'd); `truncated = total > len(nodes)` vs `> cap` (equal in every real path); `_quantity` non-numeric raise (→ `INVALID_INPUT`, handled). Plus the AttributeError-crash edge cases the Edge-Case reviewer enumerated (`document.Objects` None, missing `.Name`, `None` dep, etc.) — none reachable on a live FreeCAD document; direct-attribute access on real objects is the established 1.4 pattern.

### 2026-07-22 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 11: (high 1, medium 5, low 5)
- defer: 2
- reject: 2
- addressed_findings:
  - `[high]` `[patch]` `query_sketch_info` labeled every constraint `.Value` `"mm"`, but `Angle`/`AngleViaPoint` constraints store radians — a 90° angle was reported as `{value: 1.5708, unit: "mm"}` (wrong unit and unconverted). Added `_constraint_quantity` mapping angle types to degrees and only length types (`Distance*`/`Radius`/`Diameter`) to mm; dimensionless constraints now omit `value`. Added an `Angle` constraint to the infc fixture asserting `deg` and 90.0.
  - `[medium]` `[patch]` `query_mass_properties` no-Shape guard only caught attribute-absent objects; a present-but-null `Shape` (empty `Part::Feature`, open wire) skipped it and crashed `Volume`/`CenterOfMass` → `RECOMPUTE_ERROR` instead of `INVALID_INPUT`. Guard now also rejects `shape.isNull()`. Added a null-shape infc test asserting `INVALID_INPUT`.
  - `[medium]` `[patch]` `query_object` read every property with `getattr(...,None)`, which only swallows `AttributeError`; a proxy/computed getter raising anything else sank the whole query as `RECOMPUTE_ERROR`. Added `_read_property` wrapping each read in try/except → `None` on failure.
  - `[medium]` `[patch]` `query_sketch_info` sketch detection was a `hasattr(Geometry) and hasattr(Constraints)` duck-type; a non-Sketcher lookalike passed the gate then crashed. Switched to `TypeId.startswith("Sketcher::")` (stays ring-clean — no `import Sketcher`).
  - `[medium]` `[patch]` `query_tree_summary` advertised `max_depth` in its schema and signature but never used it (flat `Objects` source), shipping a dead knob. Removed `max_depth` from the signature and the input schema; added `minimum: 0` to `max_nodes`.
  - `[medium]` `[patch]` the read-only infc test sampled only `Shape.Volume`/`Placement.Base`. Strengthened the before/after signature to include each object's `State` tuple (surfaces `Touched`/`Invalid` a query must not introduce). (A `document.Modified` assertion was tried but that attribute does not exist on FreeCAD 1.1 `App.Document`; `State` is the correct signal.)
  - `[low]` `[patch]` `query_placement` called `getGlobalPlacement()` unguarded (can raise for `App::Link`/nested objects → `RECOMPUTE_ERROR`) and assumed a `Placement` attribute. Now falls back to local placement on failure and raises `INVALID_INPUT` for a placement-less object.
  - `[low]` `[patch]` `driving` was emitted `True` for geometric constraints that carry no `Driving` concept. Now emitted only when the constraint exposes `Driving`, as a plain `bool`.
  - `[low]` `[patch]` `max_nodes` reaching `int()` as `inf`/`nan` raised `OverflowError`/`ValueError` → `RECOMPUTE_ERROR`. `_node_cap` now maps a non-integer `max_nodes` to `INVALID_INPUT`.
  - `[low]` `[patch]` a degenerate shape could yield `nan`/`inf` mass properties, serializing to invalid JSON. `_quantity` now coerces non-finite values to `None`.
  - `[low]` `[patch]` (folded into the placement patch) a placement-less object hit `AttributeError` → `RECOMPUTE_ERROR`; now `INVALID_INPUT`.

## Design Notes

- **Read runs under the registry lock, not a bare resolve.** Use `registry.with_document(doc, fn)` (added in 1.4) so a query resolves the handle and reads under the single-writer lock, consistent with the lifecycle ops and safe against a concurrent close. The `fn` receives `(handle, document)`; do the read and return the envelope inside it.
- **Structured payload, not new contract types.** Per mcp-tools §1.3 the per-tool result is the documented shape inside `structured_content`; the wire-validated `outputSchema` stays the shared `fcb.result-envelope/1`. This matches the 1.4 precedent (`query_capabilities` returns an ad-hoc dict). AD-17 "contracts-owned wire types" is satisfied by the envelope; the query payloads are tool-specific content, schema-checked by the story's tests. Do not add `query-*.schema.json`.
- **No recompute in a reader.** project-context warns that many pass/verify signals are only valid after `doc.recompute()` — but a *query* must not recompute (that is a state change and breaks the read-only guarantee). Report the currently-stored values; a dirty model is the caller's concern. `getStatusString()` reflects the last stored state, which is correct for a read.
- **Mass properties source.** Read `obj.Shape` (Part `TopoShape`): `Shape.Volume`, `Shape.Area`, `Shape.BoundBox` (`XMin…ZMax`), `Shape.CenterOfMass`, and `len(Shape.Faces)/Edges/Solids` for counts. Wrap each dimensional field as `{value, unit}` with `mm`/`mm^2`/`mm^3` as appropriate. An object with no `Shape` attribute → `ValidationError` → `INVALID_INPUT`.
- **Sketch info is sketch-local.** For a `Sketcher::SketchObject`: `sketch.Geometry` enumerated by index (type name + `Construction` flag), `sketch.Constraints` by 1-based solver id (`Type`, `Name`, `Value` where the constraint carries one, and driving = `not constraint.Driving is False` — dimensional constraints expose `Driving`). No TNP/mapped-name resolution here.
- **Example envelope (query_tree_summary):**
  ```python
  {"schema": "fcb.result-envelope/1", "status": "OK", "detail": None,
   "structured_content": {"nodes": [{"name": "Box", "label": "Box", "type": "Part::Box",
                                     "children_count": 0, "error": None}],
                          "total_objects": 1, "truncated": False},
   "text": "..."}
  ```

## Verification

**Commands:**
- `uv run python scripts/check_imports.py` -- expected: `check_imports OK` (queries stay in usecases; no mcp/Qt leak).
- `uv run ruff check .` -- expected: clean.
- `uv run pytest tests/external -q` -- expected: all pass, including the updated surface assertion.
- `"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" tests/run_tests.py` -- expected: `test_query_tools` + prior infc suites green.

**Manual checks:**
- Over a running `uv run freecad-buddy serve --transport stdio --mode inline`, `tools/list` shows the six new `query_*` tools; calling `query_tree_summary` on an open doc returns a bounded node list with `truncated`.

## Auto Run Result

Status: done (follow-up review pass over the already-implemented story).

**Change summary:** Fresh adversarial + edge-case review of the six read-only `query_*` tools shipped in `f5a5d7d`. Two low-severity robustness patches applied to `usecases/queries.py`; three findings deferred; the rest rejected as by-design or spec-sanctioned. No spec amendment, no code re-derivation, no intent gap.

**Files changed this pass:**
- `src/freecad_buddy/usecases/queries.py` — (1) `query_placement` now falls back to the local placement when `getGlobalPlacement()` *returns* `None` (previously only an exception was caught, so a `None` return crashed `_placement_dict`). (2) `query_sketch_info` now emits an unrecognized dimensional constraint's raw value with `unit: null` instead of dropping it.
- `_bmad-output/implementation-artifacts/deferred-work.md` — two NEW entries (non-solid mass-properties handling; `_json_safe` unbounded recursion). The uncapped-`edges` finding was already logged from a prior 1.5 pass and not re-logged.

**Review findings breakdown:** intent_gap 0 · bad_spec 0 · patch 2 (low 2, applied) · defer 3 (2 new + 1 pre-existing) · reject 13.

**Verification performed:**
- `uv run python scripts/check_imports.py` → `check_imports OK`.
- `uv run ruff check src/freecad_buddy/usecases/queries.py` → `All checks passed!`; `uv run ruff format` → no change.
- `uv run pytest tests/external -q` → 111 passed.
- `FreeCADCmd tests/run_tests.py` (FreeCAD 1.1.1, local) → 26 tests, all OK (includes the full `test_query_tools` suite; the `INVALID_INPUT` cases print expected `ValidationError` tracebacks and pass). Note: `run_tests.py` writes its summary to stderr, which git-bash detaches from FreeCADCmd — the suite was re-run via a discovery-diagnostic wrapper to capture the `Ran 26 tests ... OK` line and exit 0.

**Residual risks:** the three deferred items (non-solid mass properties returning volume 0 / possible OCC raise as `RECOMPUTE_ERROR`; `_json_safe` recursion unbounded against hostile/scripted property values; uncapped whole-doc dependency edges) are unreachable on well-formed Phase-0 documents but are real forward-looking gaps for Phase-1 assistant traffic.

