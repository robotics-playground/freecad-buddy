---
title: 'Story 3.3: Sketch Tools'
type: 'feature'
epic: 3
story: '3-3-sketch-tools'
created: '2026-07-31'
status: 'done'
baseline_revision: 'a66eb3d'
final_revision: '7d9642e'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** Story 3.2 landed `run_mutation()` but shipped no caller — `grep sketch_ src/` returns only the `READ_ONLY_PROFILE` comment naming `sketch_*` as tools that must be absent. No AI-facing path can create or constrain a sketch, so G2.1's five sketch commands and G2.5 (`FullyConstrained` ≥90 %) have nothing to measure, and `run_mutation`'s snapshot-restore return value has no call site to rebind it (DW-71, a live footgun this story inherits).

**Approach:** Land `usecases/sketches.py` with the eight `sketch_*` tools from `mcp-tools-design.md` §2, each executing its typed op through `run_mutation()` and returning a `sketch_state` block (the embedded `verify_sketch` summary) beside the common `mutation` block. Add contracts-owned sketch wire types, a `DocumentRegistry.rebind()` so the snapshot-restore path cannot leave a call site holding a closed document, and register the tools in the catalog with an optional `confirm` field accepted-but-unenforced (enforcement is Story 3.7).

## Boundaries & Constraints

**Always:**
- Every `sketch_*` tool executes through `transaction.run_mutation()` — no `openTransaction`, `recompute`, or geometry write outside it (AD-5). The op callable returns the touched object Names; the sketch it touched must be in that list so `post_verify` step 3 grades it.
- The resolved document is passed into `run_mutation`, never a handle: `DocumentRegistry.with_document()` holds a non-reentrant lock (`documents.py:100`) and re-entering it deadlocks.
- `run_mutation` returns `(document, envelope)`; the returned document **must** be rebound into the registry before the tool returns, because the snapshot-restore path closes and reopens the document (DW-71). Every tool call site does this, without exception.
- Sketch geometry is addressed by sketch-local `geo_id` ints (solver-stable, not TNP-exposed); model sub-elements only by the contracts `Selector`. Constraint ids on the wire are **1-based** solver ids mapped to `Constraints[id-1].Name`; the FreeCAD Python API is **0-based**, so every id crosses that boundary exactly once, in one documented helper.
- Every FreeCAD Sketcher call matches the verified source (`docs/references/FreeCAD/src/Mod/Sketcher/App/`): `PointPos` is `none=0,start=1,end=2,mid=3` (`GeoEnum.h:86-92`); `-1` is HAxis with `pos=none` and RootPoint with `pos=start`, `-2` is VAxis (`GeoEnum.h:69-76`); `evaluateConstraints()` returns **True when constraints are invalid** (`SketchObject.pyi:904-910`); the attachment property is `AttachmentSupport` with `MapMode` (`AttachExtension.h:92-93`), accessed through `shim.py`.
- Dimensional values arrive as `Quantity` `{value, unit}` and are converted explicitly before `setDatum`/`Constraint(...)`: a **bare float angle is radians** in the FreeCAD API (`SketchObjectPyImp.cpp:884`), while the wire unit is `deg`. Never pass an unconverted wire number.
- Typed input is validated against the verified constraint arities before any FreeCAD call (`ConstraintPyImp.cpp:198-800`): `Radius`/`Diameter`/`Weight` take `(type, geoId, value)` only; `Coincident` takes only the 5-tuple `(type, g1, p1, g2, p2)` — there is no 2-geo form; `Equal`/`Parallel`/`Perpendicular` are geo-only pairs. An arity violation is `INVALID_INPUT` before the transaction opens, not a solver crash inside it.
- A conflicting, malformed, or non-zero-DoF post-state hard-fails `post_verify` and rolls back automatically (already `transaction.py:222-242`); the tool surfaces the solver diagnostics as named 1-based constraint refs in `detail`. Redundant / partially-redundant constraints warn and never fail.
- Ring purity: `usecases/` is stdlib + FreeCAD App only, version-sensitive calls through `shim.py`, every new wire type in `contracts/` with a regenerated schema (AD-1/AD-12/AD-17). `check_imports.py` stays green.
- Status values come from the existing closed set. No new status strings, no envelope variant.

**Block If:**
- The contracts `Selector` discriminator cannot be reconciled: `data-contracts-design.md:235-253` spells it `kind: "geometric"|"mapped_name"` while `mcp-tools-design.md:35-46` spells it `by: "geo_query"|"mapped_name"`. Resolve by using the **contracts** shape (`contracts/document.py` is the binding owner of wire types per AD-17) and recording the reconcile in the Spec Change Log. HALT only if `contracts/document.py` turns out to define neither.
- A sketch tool cannot reach `FullyConstrained` for a benchmark-representative input without inventing solver behaviour not present in the verified source.

**Never:**
- Do not implement or enforce the confirm gate, `preview_dry_run`, or elicitation (Stories 3.6/3.7). Accept `confirm` as an optional, unvalidated passthrough field in the input schema so 3.7 can enforce it without a schema change, and record it in the audit params.
- Do not implement TNP Layer 1/2 (Story 3.5) or any `feature_*` tool (Story 3.4).
- Do not add any `sketch_*` name to `READ_ONLY_PROFILE` — that profile's G1.6 guarantee is zero mutation tools.
- Do not open, read, or reference `benchmarks/g2/heldout/`.
- Do not use `ActiveDocument`; every call takes an explicit handle.
- Do not capture expected test values from `verify_sketch` output — golden values are analytic (AD-13).
- Do not auto-remove redundant constraints inside a tool (`autoRemoveRedundants()` is an explicit separate repair, `verification-design.md:203`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Create on base plane | `sketch_create(doc, name, plane="XY")` | New `Sketcher::SketchObject` with the verified XY rotation; committed; `sketch_state` reports `dof=0`, `fully_constrained=true` (an empty sketch has no DoF); `mutation` block present | No error expected |
| Create on planar face | `sketch_create` with a `Selector` naming a planar face | Sketch attached via `AttachmentSupport` + `MapMode="FlatFace"` | Non-planar or ambiguous match → `INVALID_INPUT`, no transaction opened |
| Add geometry | `sketch_add_geometry` with a list of typed primitives on an existing sketch | Returns `geo_ids` (0-based FreeCAD indices returned verbatim as sketch-local ids); the sketch is left under-constrained | Under-constrained sketch fails `post_verify` → automatic rollback (see next row) |
| Under-constrained after op | Any sketch op leaving `DoF > 0` | `post_verify` step 3 hard-fails → abort → recompute → re-hash proof; envelope `SPEC_FAILED`, `rolled_back=true`, explanation naming the sketch and its DoF | Reported, not raised |
| Add constraints to full constraint | `sketch_add_constraint` with the set that drives `DoF` to 0 | `constraint_ids` returned **1-based**; `sketch_state.fully_constrained=true`; envelope `OK` | No error expected |
| Conflicting constraint set | A constraint set producing non-empty `ConflictingConstraints` | Automatic rollback; `detail` carries the conflicting ids as `{solver_id (1-based), name}` refs; status `SPEC_FAILED` | Reported with named diagnostics |
| Redundant constraint | Set producing `RedundantConstraints` but `DoF == 0` | Commits; `sketch_state` carries the redundant ids as warnings; not a failure | Warning only |
| Bad constraint arity | `{type:"Radius", first:0, second:1}` or `Coincident` without both pos ids | `INVALID_INPUT` **before** `openTransaction`; document untouched, no snapshot written | Validated pre-bracket |
| Bad geo_id | `first` naming a `geo_id` outside the sketch (and not −1/−2) | `INVALID_INPUT` pre-bracket | Validated pre-bracket |
| Set datum | `sketch_set_datum(constraint=<1-based id or name>, value={value:30,unit:"mm"})` | Datum applied via `setDatum`; recompute; `sketch_state` re-read | Non-driving or non-dimensional target → `INVALID_INPUT`; unit mismatch (`deg` on a length) → `INVALID_INPUT` |
| Angle datum | `value={value:45,unit:"deg"}` | Converted to radians before the API call; sketch measures 45° | A raw 45 passed as radians would be a silent 2578° error — the conversion is asserted by test |
| Remove geometry | `sketch_remove_geometry(geo_ids=[2])` | Geometry and its dependent constraints removed by FreeCAD; sketch re-verified | If removal leaves the sketch under-constrained → rollback per the DoF rule |
| External geometry | `sketch_add_external_geometry` with a `Selector` on a model edge | Edge projected; `ExternalGeometry` LinkSubList grows; the TNP snapshot taken by `run_mutation` covers it | Unresolvable selector → `INVALID_INPUT`; a `Missing` external flag surfaces as a Layer-0 recompute error → rollback |
| Snapshot-restore path ran | A failing op whose abort does not restore the hash | `run_mutation` returns the reopened document; the tool **rebinds** it into the registry before returning; a subsequent call on the same handle operates on the live document | Registry left holding a closed document would be the DW-71 defect — asserted by test |
| Sketch not found | `sketch` names a non-existent or non-`Sketcher::` object | `INVALID_INPUT` naming the object | Pre-bracket |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/sketches.py` -- NEW. The eight `sketch_*` use cases + shared `_sketch_op` bracket helper. Placement fixed by `component-design.md:39` (P2, use-case ring).
- `src/freecad_buddy/contracts/sketch.py` -- NEW. `SketchState`, `ConstraintRef`, `ConstraintSpec`, `GeometrySpec`, `Quantity`, geometry-kind and constraint-type literals. Nothing sketch-shaped exists in `contracts/` today (only `PostVerifyBlock.fully_constrained`).
- `src/freecad_buddy/contracts/__init__.py:25-33,63-115` -- import block + `__all__`; every new contract symbol must land in both.
- `src/freecad_buddy/contracts/document.py:235-253` -- the authoritative `Selector` union (`kind` discriminator). Reuse; do not re-declare the mcp-tools `by` variant.
- `src/freecad_buddy/usecases/transaction.py:417-425` -- `run_mutation(document, handle, label, op, audit_sink=None, tool="", params=None) -> (document, envelope)`. `op` takes the document and returns `list[str]` of touched Names (`:464`).
- `src/freecad_buddy/usecases/transaction.py:222-242` -- `post_verify` step 3 already requires `FullyConstrained` on every touched `Sketcher::*`; sketch tools inherit the rollback, they do not re-implement it.
- `src/freecad_buddy/usecases/documents.py:92,100,121` -- `DocumentRegistry`, its non-reentrant `_lock`, `with_document()`. Needs a new `rebind(handle, document)` (DW-71).
- `src/freecad_buddy/usecases/verify.py:354` -- `verify_sketch(registry, doc, sketch) -> ResultEnvelope`; its `subject`/`checks`/`warnings` are the source of `sketch_state`. Reuse, never re-read the properties directly.
- `src/freecad_buddy/usecases/queries.py:480-533` -- `query_sketch_info` and `_construction_flag`/`_constraint_quantity`/`_quantity` helpers; geometry-kind naming and the 1-based constraint id convention already live here. Reuse.
- `src/freecad_buddy/usecases/shim.py:82-160` -- capability probes; add a Sketcher probe here and wire it into `warm_capability_probes` (`:143`) and `capability_banner` (`:184`).
- `src/freecad_buddy/hosts/tool_catalog.py:212-225,341` -- `_query_method` and the `tool_specs()` list: the registration pattern (hand-authored inline `input_schema`, `mutating` flag). Mutating sketch specs need a variant that threads the audit sink.
- `src/freecad_buddy/hosts/tool_catalog.py:301-317` -- `READ_ONLY_PROFILE`; its comment names `sketch_*` as necessarily absent. Leave unchanged; the profile test must keep proving it.
- `src/freecad_buddy/adapters/mcp_server.py:33-40,164-210` -- shared `_RESULT_ENVELOPE_SCHEMA` outputSchema (no per-tool outputSchema), the audit path for `mutating` tools, and the suspect-document gate that refuses mutations after a marshal timeout.
- `src/freecad_buddy/adapters/rpc_dispatch.py:90-110` -- the single error boundary: `ValidationError`/`TypeError`/`ValueError`/`KeyError` → `INVALID_INPUT`. Raise `ValidationError` for bad input rather than hand-building envelopes.
- `docs/references/FreeCAD/src/Mod/Sketcher/App/SketchObject.pyi:85-410` -- verified `addGeometry`/`delGeometry`/`addConstraint`/`delConstraint`/`toggleConstruction`/`setDatum`/`renameConstraint`/`addExternal` signatures.
- `docs/references/FreeCAD/src/Mod/Sketcher/App/ConstraintPyImp.cpp:198-800` -- verified constraint constructor arities; `Constraint.h:52-77` the type-name enum.
- `docs/references/FreeCAD/src/Mod/Sketcher/App/GeoEnum.h:69-92` -- `PointPos` values and negative geo-id meanings.
- `benchmarks/g2/dev/g2-dev-00{1..5}-sketch/case.yaml` -- the five sketch commands these tools must be able to satisfy (rectangle, circle, square-on-face, triangle on XZ, slot). Their `fn`s are already graded by `benchmarks/harness/assertions.py`.
- `tests/infc/test_verify_tools.py:232-239` -- `_fully_constrained_sketch()`, the canonical constrained-sketch recipe; the template for in-FreeCAD tests.
- `tests/infc/test_mutation_protocol.py:37-62` -- the in-FreeCAD fixture idiom (registry → `document_create` → handle) and the snapshot-leftover assertion helper.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- DW-71 (rebind, closed by this story), DW-72/DW-73 (G2 scorer; explicitly deferred to when driveable tools land — assess, do not silently skip).

## Tasks & Acceptance

**Execution:**
- [ ] **Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)** -- Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md`; read `_bmad-output/project-context.md`; read `mcp-tools-design.md` §1.2/§2/§3.6 and `verification-design.md` §4 (verify_sketch). Confirm every Sketcher API used against `docs/references/FreeCAD/src/Mod/Sketcher/App/` before writing code — never from memory.
- [x] `src/freecad_buddy/contracts/sketch.py` + `contracts/__init__.py` -- Add `SketchState`, `ConstraintRef`, `Quantity`, and the geometry-kind / constraint-type literals as TypedDict/Literal, stdlib only; export them -- the wire vocabulary must be contracts-owned before a producer exists (AD-17), and `sketch_state` is currently an untyped `{"type":"object"}` in the design catalog.
- [x] `src/freecad_buddy/contracts/jsonschema/` via `scripts/gen_schemas.py` -- Register the new wire root and regenerate -- the drift check fails CI otherwise.
- [x] `src/freecad_buddy/usecases/documents.py` -- Add `rebind(handle, document)` -- closes DW-71; without it the first post-rollback call touches a closed document.
- [x] `src/freecad_buddy/usecases/shim.py` -- Add a Sketcher capability probe and wire it into `warm_capability_probes` + `capability_banner` -- version-sensitive availability is probed, never version-compared (AD-11).
- [x] `src/freecad_buddy/usecases/sketches.py` -- Implement the eight tools (`sketch_create`, `sketch_add_geometry`, `sketch_remove_geometry`, `sketch_add_constraint`, `sketch_remove_constraint`, `sketch_set_datum`, `sketch_toggle_construction`, `sketch_add_external_geometry`) over one shared bracket helper that validates input, calls `run_mutation`, rebinds the returned document, and attaches `sketch_state` -- the story's substance; each is a `run_mutation` caller, never a transaction author.
- [x] `src/freecad_buddy/hosts/tool_catalog.py` -- Register the eight specs with hand-authored input schemas (`Selector`/`Quantity` refs, optional `confirm` passthrough), `mutating=True`, and audit wiring; leave `READ_ONLY_PROFILE` untouched -- registration is how the tools become reachable, and the profile guarantee must survive.
- [x] `benchmarks/_registry/validators.yaml` + `benchmarks/runner.py` -- Assess whether DW-72's G2 fault scorer can now land given a driveable mutation tool; wire it if the sketch tools make it reachable, otherwise record precisely why it still blocks on `feature_*` -- a G2 pass rate may not be quoted while nothing scores it, so this must be resolved or explicitly re-deferred, never skipped.
- [x] `tests/infc/test_sketch_tools.py` -- stdlib `unittest` covering every I/O-matrix row: the five benchmark sketch shapes reaching `FullyConstrained`, the deg→rad datum conversion, each pre-bracket validation rejection, the conflicting-set rollback with named diagnostics, and a forced snapshot-restore asserting the registry was rebound -- the rollback and rebind paths cannot be proven by inspection.
- [x] `tests/external/test_sketch_contract.py` -- pytest over the new contract types, schema drift, ring-import discipline, and that no `sketch_*` name entered `READ_ONLY_PROFILE` -- contracts and the profile are stdlib-only and testable outside FreeCAD.
- [x] **Final Task: Quality Checks** -- Run `python scripts/check_imports.py`, `uv run python scripts/gen_schemas.py --check`, `uv run pytest tests/external`, `uv run python scripts/check_provenance.py`, `uv run ruff check`, and the in-FreeCAD suite via `FreeCADCmd tests/run_tests.py`.

**Acceptance Criteria:**
- Given each of the five `benchmarks/g2/dev/*-sketch` commands driven through the typed tools, when the sequence completes, then the sketch reports `FullyConstrained == True` and the geometry counts the case asserts, with every step committed through `run_mutation`.
- Given a tool whose op forces the snapshot-restore rollback path, when the tool returns, then the registry resolves the handle to the reopened live document and the next tool call on that handle succeeds.
- Given the registered tool set, when the catalog is introspected, then all eight `sketch_*` tools are present with `mutating=True` and none appears in `READ_ONLY_PROFILE`.
- Given any `sketch_*` call, when it succeeds, then the envelope carries both a `mutation` block and a `sketch_state` block whose `fully_constrained` agrees with `post_verify.fully_constrained`.

## Spec Change Log

- **Selector discriminator reconciled to the contracts shape.** `data-contracts-design.md:235-253` spells it `kind: "geometric"|"mapped_name"` while `mcp-tools-design.md:35-46` spells it `by: "geo_query"|"mapped_name"`. `contracts/document.py` defines the `kind` form, so per AD-17 that is the binding shape and the sketch tools' `face`/`edge` inputs use it. The `geometric` variant is rejected with `INVALID_INPUT` by the sketch tools until a geometric-query resolver exists; only `mapped_name` resolves today. Pinned by `tests/external/test_sketch_contract.test_a_selector_input_uses_the_contracts_kind_discriminator`.

- **`sketch_add_geometry` gained an optional `constraints` field.** The Design Notes assumed a caller reaches a constrained state "by sending geometry and constraints in one `sketch_add_geometry` + `sketch_add_constraint` pair". Measured on FreeCAD 1.1.1: that pair is unreachable, because the first call's `post_verify` step 3 hard-fails on `DoF > 0` and the rollback **removes the geometry** (verified: `GeometryCount == 0` after the rolled-back add). No `sketch_add_constraint` can then reference geo ids that no longer exist, so the Block-If "a sketch tool cannot reach `FullyConstrained` for a benchmark-representative input" was live. Resolved without inventing solver behaviour by letting the geometry and the constraints that pin it execute in one `run_mutation` bracket: `sketch_add_geometry(..., constraints=[...])` applies both inside the same transaction, reusing the same pre-validated `_apply_constraints` path `sketch_add_constraint` uses. No new tool, no new status, no change to the bracket. All five `benchmarks/g2/dev/*-sketch` shapes reach `FullyConstrained` this way.

- **Redundant constraints no longer fail the mutation.** The I/O matrix row "Redundant constraint → Commits; warnings; not a failure" and AD-8's warn-only rule were both violated in practice: `SketchObject::execute()` returns an error for `solve() == -2` (`SketchObject.cpp:228-233`), so a redundant sketch reports `isValid() == False` and gets no shape. That tripped `post_verify` step 1 (`RECOMPUTE_ERROR`) and, once step 1 was fixed, the TNP Layer-0 sweep (`SPEC_FAILED`, `BROKEN`). Added `shim.redundant_only_sketch(obj)`, which matches the exact source-verified `"Sketch with redundant constraints"` message prefix — the message emitted for `-2` alone, distinct from conflicting (`-3`), over-constrained (`-4`) and malformed (`-5`) — and both generic validity sweeps now defer such a sketch to the AD-8-aware grader. A conflicting, malformed or loose sketch still hard-fails unchanged.

- **A conflicting constraint set reports `RECOMPUTE_ERROR`, not `SPEC_FAILED`.** The I/O matrix row specifies `SPEC_FAILED`. A conflicting sketch genuinely fails FreeCAD's recompute, so `post_verify` step 1 catches it first and `_rollback_status` (pre-existing, Story 3.2) maps an unclean recompute to `RECOMPUTE_ERROR`. Both are in the closed status set, both are non-OK, both roll back, and both carry the named 1-based diagnostics. The status label was treated as over-specified rather than changing Story 3.2's mapping; the test asserts the substance and accepts either label.

- **`verify_sketch`'s report subject was widened to the `verification-design.md` §4.1 field set.** It previously carried only `sketch`/`dof`/`fully_constrained`, which is not enough to build a `sketch_state` block. It now also reports `geometry_count`, `constraint_count`, and `conflicting`/`malformed`/`redundant`/`partially_redundant` as `{id, name, type}` refs via the new `verify.constraint_refs` helper — the one place the 1-based-to-0-based boundary is crossed. Additive only; the sketch tools embed this subject rather than re-reading sketch properties.

- **The `run_mutation` audit sink is not threaded from the tool catalog.** Each `sketch_*` use case accepts an optional `audit_sink`, but `HandlerFactory` has no sink parameter and adding one would change a signature shared by every host. The MCP server already writes a before/after audit record for every `mutating=True` tool with the same `params_digest`, so registered sketch calls are audited; the richer per-mutation record (both fingerprint digests, the rollback block) is available to any caller that passes a sink directly and is covered by `EnvelopeShapeTest.test_the_audit_params_carry_the_confirm_passthrough`.

- **`capabilities.CapabilityBanner` gained a required `sketcher_available` field** carrying the new shim probe, so `query_capabilities` reports whether the sketch tools can run at all.

## Review Triage Log

### 2026-07-31 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 11: (high 3, medium 6, low 2)
- defer: 3: (medium 2, low 1)
- reject: 8: (low 8)
- addressed_findings:
  - `[high]` `[patch]` every tool validated its input **inside** the transaction, so a malformed request wrote a `saveCopy` snapshot, opened a transaction and returned a rolled-back `SPEC_FAILED` instead of the `INVALID_INPUT` four I/O-matrix rows specify — added a `precheck` callback that `_sketch_mutation` runs inside the resolved-document closure before `run_mutation`, and wired it into all eight tools.
  - `[high]` `[patch]` `_sketch_mutation` rebound the document only on the normal return, so a `run_mutation` that raised after the snapshot restore closed and reopened the document left the registry holding a deleted object — the exact DW-71 footgun the story claims to close. The rebind now runs in a `finally`.
  - `[high]` `[patch]` the Layer-0 redundancy skip in `tnp_guard.audit_references` was unconditional, so a sketch that had redundant constraints **and** a broken reference was skipped entirely and the mutation committed with a genuinely broken object — the skip now applies only when the snapshot recorded no references for that object.
  - `[medium]` `[patch]` `_check_geo_id` rejected every id `<= -3`, so no constraint could reference geometry `sketch_add_external_geometry` had just projected — the tool's output was unusable by its siblings. External ids are now accepted, bounded by `len(ExternalGeometry)`.
  - `[medium]` `[patch]` `_sketch_state` returned `None` when a rollback destroyed the sketch, violating the `fcb.sketch-state/1` schema it claims to emit and breaking any consumer that dereferences it — it now returns a block carrying `readable: False`.
  - `[medium]` `[patch]` a rolled-back `sketch_add_geometry` reported the `geo_ids` it held mid-transaction, naming geometry the rollback had removed — both id lists are now empty on the rollback path.
  - `[medium]` `[patch]` `Symmetric` silently defaulted `first_pos`/`second_pos` to `start` while every sibling constraint requires them explicitly, producing a wrong sketch rather than an error — both are now required, and the optional `third_pos` (point symmetry) is wired instead of being dead wire surface.
  - `[medium]` `[patch]` no finiteness guard existed, so NaN defeated both the zero-length and zero-radius checks (NaN comparisons are always false) and reached the solver — quantities and coordinates now reject non-finite values pre-bracket.
  - `[medium]` `[patch]` a duplicate `geo_id` in `sketch_toggle_construction` toggled twice and silently no-opped while reporting success — duplicates are now rejected.
  - `[low]` `[patch]` `_ANGLE_UNITS` accepted an undocumented `rad`, so a caller sending `{"value":45,"unit":"rad"}` meaning degrees got a silent 2578° error — only `deg` is accepted, matching the wire contract.
  - `[low]` `[patch]` `sketch_add_external_geometry` accepted a selector resolving to a Face or Vertex and let `addExternal` fail opaquely inside the bracket — a non-Edge is now named and rejected pre-bracket.
  - Test corrections carried by the same pass: the 13 tests that asserted the pre-bracket rejections as rolled-back `SPEC_FAILED` envelopes now assert `ValidationError`, unchanged document state, **and** that `temp_snapshot_path` was never called (state comparison alone cannot discriminate, because a rollback restores state); six tautological assertions that derived their expected constraint ids from the code under test were replaced with hand-derived literals. Both classes were proven to bite by mutation testing — disabling `precheck` fails 42 tests, returning 0-based ids fails 9, removing the `finally` fails 1.

### 2026-07-31 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 10: (high 2, medium 5, low 3)
- defer: 3: (medium 2, low 1)
- reject: 24: (medium 4, low 20)
- addressed_findings:
  - `[high]` `[patch]` `sketch_state` emitted a `readable` field that existed in neither `SketchState` nor `sketch-state.schema.json`, and the `readable: False` block omitted `dof`/`fully_constrained`/`geometry_count`/`constraint_count` — the four fields the schema required — so the block the tools claim to emit failed its own generated schema. `readable` is now a declared, required contract field and the grading fields are conditional on it; the readable path also carries `sketch` explicitly rather than relying on the verify subject.
  - `[high]` `[patch]` `Tangent`/`Perpendicular` silently dropped `first_pos` whenever `second_pos` was absent, converting a requested endpoint tangency into an edge-to-edge one — a different constraint with different DoF, applied with no error. The half-specified form is now rejected, matching the guard the same module already applied to the dimensional types.
  - `[medium]` `[patch]` `Radius`/`Diameter` accepted a negative or zero datum, which `setDatum` refuses (`SketchObjectPyImp.cpp:927,930`), so a sign error cost a snapshot, a transaction and a rollback instead of `INVALID_INPUT`. A shared `_positive_datum` now rejects it pre-bracket for every dimensional type, exempting the signed `DistanceX`/`DistanceY`.
  - `[medium]` `[patch]` `_check_geo_id` accepted the `-1`/`-2` axes for every constraint type before per-type dispatch, so `Radius` on an infinite axis line reached the solver. `Radius`/`Diameter` now require a real curve.
  - `[medium]` `[patch]` the external geo-id bound used `len(ExternalGeometry)`, the link-entry count, while the negative id space counts projected curves — `SketchObject.h:1222` names them as distinct index spaces. One link projecting a face's four edges legally exposes `-3..-6`, and the check rejected `-4` and below. Now bounded by `getExternalGeometryCount()`, discounting the two axes `ExternalGeo` always carries.
  - `[medium]` `[patch]` `sketch_add_constraint` reported `constraint_ids` unconditionally, naming solver ids a rollback had already removed — the exact defect a prior pass fixed for `sketch_add_geometry` and left unfixed in its sibling. Both id lists are now empty on the rollback path.
  - `[medium]` `[patch]` the redundancy deferral added to `_invalid_objects` was unconditional, but step 1 sweeps the whole document while step 3 grades only `touched` — so an untouched redundant sketch, which is shapeless, was exempted from the only check that would have seen it and no longer blocked any commit anywhere in the system. The deferral is now scoped to touched objects.
  - `[low]` `[patch]` `_resolve_constraint_index` matched an empty-string reference against the first unnamed constraint (`Name == ""`) instead of naming nothing, silently targeting the wrong constraint for removal or a datum change.
  - `[low]` `[patch]` an arc whose angles differ by exactly a full turn passed the `start_angle == end_angle` guard while being just as degenerate; the span is now taken modulo 2π.
  - `[low]` `[patch]` `_sketch_method`'s docstring claimed the handler "threads the audit sink" while `make` passes none — the Spec Change Log already records the sink as deliberately not threaded, so the docstring was the defect, not the wiring.
  - Tests carried by the same pass: eight new `ReviewPatchTest` cases pin every behavioural fix above, plus an external case validating the unreadable `sketch_state` block against its own schema — a gap that let findings 1 and 2 ship, because the schema was only ever tested against hand-authored fixtures and never against the producer. All eight were proven to bite by mutation testing: reverting the ten fixes fails them and passes nothing. One first draft passed tautologically (its circle fixture rolled back, so the later rejection fired on a missing geo id rather than the datum sign) and was corrected to a genuinely constrained fixture.

### 2026-07-31 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 5: (high 2, medium 3, low 0)
- defer: 3: (medium 1, low 2)
- reject: 12: (medium 3, low 9)
- addressed_findings:
  - `[high]` `[patch]` `_positive_datum` rejected values FreeCAD accepts, citing a source location that does not state the rule. The predicate is `SketchObjectConstraints.cpp:200-204`: non-positive is refused for `Radius`/`Diameter`/`Weight` only, and zero for `Distance` only — `Angle` carries no sign rule at all. The tool refused a negative `Angle` (the reversed measurement of the same angle) and a negative `Distance`, both legal, at `sketch_add_constraint` and `sketch_set_datum` alike. Replaced the `_SIGNED_TYPES` exemption list with `_POSITIVE_DATUM_TYPES`/`_NONZERO_DATUM_TYPES` mirroring the source, and corrected the miscitation carried by the existing test.
  - `[high]` `[patch]` `_external_curve_count` probed `getExternalGeometryCount`, which is a C++ inline (`SketchObject.h:305`) that the Python binding never exposes — absent from all 92 `def`s in `SketchObject.pyi`, while `addExternal`/`delExternal` are present. The `callable()` branch was therefore dead and the `ExternalGeometry` link-count fallback always ran, so a single link projecting a face's several edges legally exposed `-3..-6` while the check rejected `-4` and below. Now reads the `ExternalGeo` geometry list, which `SketchObject.h:307` shows is exactly what the C++ counter returns.
  - `[medium]` `[patch]` the `Angle` two-geometry branch silently dropped `first_pos`/`second_pos`, building the edge-to-edge constraint when the caller described the 5-arg endpoint form (`ConstraintPyImp.cpp:685-693`) — a different constraint with different DoF, applied without an error. This is the identical defect a prior pass fixed for `Tangent`/`Perpendicular` and left in their sibling; `Angle` now rejects the half-given form and routes the fully-given one.
  - `[medium]` `[patch]` both id-blanking gates read `mutation.rolled_back`, but the unproven-rollback path (`transaction.py:501-517`) reports `rolled_back: False` with the snapshot kept on disk precisely because restoration could not be claimed. `sketch_add_geometry` and `sketch_add_constraint` therefore reported mid-transaction ids as live for a document whose state is unknown. Replaced with a shared `_ids_survived` gating on a committed (`OK`) envelope, so both the proven and unproven paths suppress the ids.
  - `[medium]` `[patch]` `_sketch_state` caught only `ValidationError`, so a non-OK or malformed verify envelope yielded an empty `subject` and a block claiming `readable: True` while carrying none of the grading fields — a consumer that checked `readable` before reading `dof` got a `KeyError` from a block that passed its own schema (the schema cannot express the conditional, since it marks every grading field optional). `readable` now tracks whether the fields are actually present.
  - Tests carried by the same pass: two in-FreeCAD classes (`DatumSignRuleTest`, `AngleEndpointFormTest`) pinning the negative-`Angle`, negative/zero-`Distance` and half-given-`Angle` behaviours against the live solver, and two external cases pinning `_ids_survived` across all four envelope outcomes and the unreadable-subject path at the producer rather than against a hand-authored fixture. All four behavioural fixes were proven to bite by mutation testing: restoring the old datum predicate errors 2 tests, the old `Angle` branch fails 1, and reverting the two envelope fixes fails 2.

## Design Notes

**One bracket helper, eight thin tools.** Each tool differs only in its validated input and the closure it hands to `run_mutation`. The shared helper is the only place that knows the call contract:

```python
def _sketch_mutation(registry, doc, sketch_name, label, tool, params, op):
    def call(handle, document):
        return transaction.run_mutation(document, handle, label, op, ...)
    document, envelope = registry.with_document(doc, call)
    registry.rebind(doc, document)          # DW-71 — the snapshot path reopened it
    _attach_sketch_state(registry, envelope, doc, sketch_name)
    return envelope
```

`rebind` must happen for **every** exit path, not only the rollback one — the tool cannot tell from the envelope alone whether the document object changed.

**The 1-based boundary.** The wire uses 1-based constraint ids (`Constraints[id-1]`, `verification-design.md:205`); FreeCAD's `addConstraint`/`delConstraint`/`setDatum` are 0-based. Convert in one named helper in each direction and test the off-by-one explicitly — an id that silently drifts by one names the wrong constraint in a diagnostic, which is worse than an error.

**Angle units are the sharpest trap.** `setDatum(int, float)` treats an angular value as **radians** (`SketchObjectPyImp.cpp:884`), and `Constraint("Angle", geo, value)` likewise. The wire unit is `deg`. Convert explicitly; passing a `Base.Quantity` with an angle unit also works and is the safer form since the C++ does the conversion (`:829`).

**An empty sketch is fully constrained.** `sketch_create` commits a sketch with `DoF == 0`, so it passes `post_verify` step 3 trivially. The first `sketch_add_geometry` then *breaks* that — which is why a bare add-geometry call rolls back. Callers reach a constrained state by sending geometry and constraints in one `sketch_add_geometry` + `sketch_add_constraint` pair per shape, or the tests will spend their time watching correct rollbacks. Note this in the tool descriptions so an agent does not read the rollback as a bug.

## Verification

**Commands:**
- `python scripts/check_imports.py` -- expected: `check_imports OK`
- `uv run python scripts/gen_schemas.py --check` -- expected: `gen_schemas --check OK` (byte-identical)
- `uv run pytest tests/external` -- expected: all pass, no regression against the 650-passing baseline
- `FreeCADCmd tests/run_tests.py` -- expected: the new `test_sketch_tools` cases pass; no regression against the 165-test baseline
- `uv run python scripts/check_provenance.py` -- expected: `check_provenance OK`
- `uv run ruff check` -- expected: `All checks passed!`

**Manual checks (if no CLI):**
- Drive `g2-dev-001-sketch` (8×16 mm rectangle) through the tools under `FreeCADCmd` and read `verify_sketch` directly: `fully_constrained` must be `True` with four line segments, and the audit log must carry one mutation record per tool call with both fingerprint digests.



## Auto Run Result

**Change:** A follow-up review pass over the eight `sketch_*` mutation tools. No implementation loopback — no intent gap and no bad spec — five patches applied directly to the diff, three findings deferred.

**Files changed:**
- `src/freecad_buddy/usecases/sketches.py` — datum sign predicate rebuilt against `SketchObjectConstraints.cpp:200-204`; `_external_curve_count` reads `ExternalGeo` instead of probing a C++-only method; the `Angle` endpoint form is routed rather than silently dropped; a shared `_ids_survived` replaces the two `rolled_back` gates; `_sketch_state` reports `readable` from the fields actually present.
- `tests/infc/test_sketch_tools.py` — added `DatumSignRuleTest` and `AngleEndpointFormTest`; corrected the miscited source reference on the existing non-positive-datum test.
- `tests/external/test_sketch_contract.py` — added a producer-level unreadable-subject case and an `_ids_survived` case covering all four envelope outcomes.
- `_bmad-output/implementation-artifacts/deferred-work.md` — appended DW-86, DW-87, DW-88.

**Review findings:** 5 patched (2 high, 3 medium), 3 deferred (1 medium, 2 low), 12 rejected. Several reviewer findings were already tracked (DW-80 probe caching, DW-81 source-grep tests, DW-83 two-window state read, DW-84 status-string matching) and were not re-ledgered. Rejections were mostly claims that did not survive source verification, restatements of the specified confirm-gate deferral, or style preferences.

**Verification:**
- `python scripts/check_imports.py` — `check_imports OK`
- `uv run python scripts/gen_schemas.py --check` — `gen_schemas --check OK`
- `uv run python scripts/check_provenance.py` — `check_provenance OK`
- `uv run pytest tests/external` — 682 passed
- `FreeCADCmd tests/run_tests.py` — 242 tests, `OK (skipped=1)`
- `uv run ruff check` — 10 pre-existing E501s in `scripts/automation/` and `tests/external/test_check_imports.py`, none in the changed files; confirmed identical on a stashed tree.
- Mutation testing: each of the four behavioural fixes was reverted in turn and the pinning tests fail (datum predicate 2 errors, `Angle` branch 1 failure, the two envelope fixes 2 failures).

**Residual risks:**
- The `_external_curve_count` fix is verified against the FreeCAD source and the existing single-edge test, but no test projects a face contributing several curves, so the multi-curve bound is reasoned rather than measured. A fixture that projects a face would close it.
- `Angle`'s edge-to-edge path stays untested against the solver for the negative-datum case beyond the wedge fixture added here.
- DW-88 leaves `renameConstraint`/`setDriving` validated inside the bracket, so a name collision still costs a snapshot and a proven rollback rather than returning `INVALID_INPUT`.
