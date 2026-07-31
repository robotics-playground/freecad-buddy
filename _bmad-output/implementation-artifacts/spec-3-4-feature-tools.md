---
title: 'Story 3.4: Feature Tools'
type: 'feature'
epic: 3
story: '3-4-feature-tools'
created: '2026-07-31'
status: 'done'
baseline_revision: 'b8fe6f5'
final_revision: 'ca87352'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-3-3-sketch-tools.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** Story 3.3 landed the eight `sketch_*` tools, but a sketch is not a solid. `grep -rn "feature_" src/` returns exactly one hit — a comment in `tool_catalog.py:542` naming `feature_*` as tools that must be absent from `READ_ONLY_PROFILE`. Nothing in `src/` creates a `PartDesign::Body`, and no `PartDesign` type id is constructed anywhere. So 35 of the 40 G2.1 dev commands (every pad, pocket, revolve, hole, dressup, pattern and mirror case) have no tool that can execute them, and G2.1's ≥85 % pass rate has nothing to measure.

**Approach:** Land `usecases/features.py` with the ten `feature_*` tools from `mcp-tools-design.md` §2, each executing its typed op through `run_mutation()` via the same bracket pattern `sketches.py` established, returning a `feature_state` block (created feature Name + shape summary) beside the common `mutation` block. Add contracts-owned feature wire types, a PartDesign capability probe, and shim accessors for the two properties that genuinely differ across the two blocking CI legs.

## Boundaries & Constraints

**Always:**
- Every `feature_*` tool executes through `transaction.run_mutation()` — no `openTransaction`, `recompute`, or geometry write outside it (AD-5). The op callable returns the touched object Names; the created feature **and** its Body must be in that list so `post_verify` grades the resulting solid.
- Reuse `sketches.py`'s bracket contract exactly: resolve the document, run a `precheck` closure inside `with_document` **before** `run_mutation` so malformed input raises `ValidationError` without writing a snapshot, and `registry.rebind(doc, document)` in a `finally` on every exit path including the raising one (DW-71's closure; `sketches.py:516-560` is the template).
- **Cross-leg property divergence goes through `shim.py`, never a version comparison.** Verified against both legs: FreeCAD 1.0.0 `FeatureExtrude.h` declares no `SideType`, no `Type2`, no `Offset2`, and spells the Pad/Pocket `Type` index-4 tombstone `"TwoLengths"`; FreeCAD 1.1.1 (probed live) declares `SideType` `['One side','Two sides','Symmetric']`, `Type2`, and spells index 4 `"?TwoLengths"`. `SideType` was introduced by upstream PR #21794 (`a346c266e7`), after tag `1.0.2`. Symmetric extrude therefore routes through `Midplane` (an `App::PropertyBool` present and functional on **both** legs, inherited from `ProfileBased`), never `SideType`. Never index a `Type` enum numerically — always assign the string, and never assume index 4 is reachable.
- Every enum value assigned to a PartDesign property is validated against `obj.getEnumerationsOfProperty(name)` at call time, not against a hardcoded list. This is mandatory for `Hole.HoleCutType`, `ThreadSize`, `ThreadClass` and `ThreadFit`, which `FeatureHole.cpp:1283-1320` re-populates on every `ThreadType` change — so `ThreadType` is assigned first, then the dependent enum is read back before assignment. `Hole.ThreadType` itself is 6 values on 1.0.0 and 11 on 1.1.1, so it is probed too.
- **Dressup edge references are validated before submission.** `FeatureDressUp.cpp:141-145` silently `erase`s any requested edge whose `mapEdgeFace` entry has `los.Extent() != 2`, and `:147-154` silently erases any edge whose `BRep_Tool::Continuity` is not `GeomAbs_C0`. There is no return value or error. A fillet/chamfer tool must therefore compare the requested edge count against the surviving count and fail rather than commit a feature that silently ignored the user's selection — this is the exact trap `project-context.md` names ("`FeatureDressUp` silently DROPS edges … reference count comparison is mandatory; error state alone misses it").
- Sub-elements are addressed only by the contracts `Selector` (`contracts/document.py`, `kind` discriminator — the reconcile Story 3.3 already recorded). Every dimension is an explicit-unit `Quantity`; angles arrive as `deg` on the wire. The mandatory intent-bearing `name` field is applied to the created feature's `Label`, while all logic keys on the immutable `Name`.
- A created feature is added to its Body via `Body.addObject(feature)` — `Body.cpp:230-262`, which validates via `isAllowed`, calls `insertObject`, and moves `Tip` only for solid features. Never write `Body.Group` directly (`Body.cpp:313` owns it).
- Ring purity: `usecases/` is stdlib + FreeCAD App only, version-sensitive calls through `shim.py`, every new wire type in `contracts/` with a regenerated schema (AD-1/AD-12/AD-17). `check_imports.py` stays green.
- Status values come from the existing closed set. No new status strings, no envelope variant.

**Block If:**
- The G2 assertion grader cannot grade a feature the tools produce because `_graded_shape` (`benchmarks/harness/assertions.py:99`) picks the *last* shape-bearing object in `document.Objects` order while a PartDesign build leaves the Body, its Origin and the sketch in that list. If the produced document orders such that the graded shape is not the finished solid, HALT rather than reordering objects to satisfy the grader or editing the grader to match the implementation (AD-13: the grader is independent).
- A benchmark-representative command cannot be expressed without inventing a PartDesign property or enum value absent from **both** verified legs.

**Never:**
- Do not implement or enforce the confirm gate, `preview_dry_run`, or elicitation (Stories 3.6/3.7). Accept `confirm` as an optional, unvalidated passthrough exactly as the sketch tools do (DW-85 tracks the gap).
- Do not implement TNP Layer 1/2 (Story 3.5, DW-70) or modify `tnp_guard.py`.
- Do not add any `feature_*` name to `READ_ONLY_PROFILE` — that profile's G1.6 guarantee is zero mutation tools, and `tool_catalog.py:542` already reserves the namespace by construction.
- Do not open, read, or reference `benchmarks/g2/heldout/`.
- Do not use `ActiveDocument`; every call takes an explicit handle.
- Do not capture expected test values from a `verify_*` tool or from the implementation — golden values are hand-derived analytically (AD-13).
- Do not use `SideType`, `Type2`, `Offset2`, `TaperAngle2`, `UpToFace2` or `UpToShape2` — all are 1.1-only and would break the 1.0.x blocking leg.
- Do not quote a G2.1 pass rate. Wiring the scorer is in scope; running the gate for a score is Story 3.8.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Pad a profile | `feature_pad(doc, body, profile, name, length={value:5,unit:"mm"})` | `PartDesign::Pad` created, added to Body, `Tip` advanced; committed; `feature_state.feature` names it; `shape_summary` carries volume/bbox/counts | No error expected |
| Pad symmetric | `feature_pad(..., midplane=true)` | `Midplane=True` (both legs); solid straddles the sketch plane | No error expected |
| Pocket through all | `feature_pocket(..., up_to="ThroughAll")` | `Type="ThroughAll"` assigned as a **string** validated against `getEnumerationsOfProperty("Type")`. `ThroughAll` is a Pocket-only value — the Pad enum has `UpToLast` at that position instead | Value absent from the live enum for *that* feature type → `INVALID_INPUT` naming the value and the legal set |
| Length-driven with no length | `feature_pad(..., up_to="Length")` and `length` omitted | `INVALID_INPUT` pre-bracket — the design schema leaves `length` optional while defaulting `up_to` to `Length`, so the conditional requirement is enforced in the use case | Validated pre-bracket |
| Revolve about a sketch axis | `feature_revolve(..., axis={selector on sketch V_Axis}, angle={value:360,unit:"deg"})` | `ReferenceAxis` set to `(sketch,['V_Axis'])`; `Angle` set in **degrees** (`App::PropertyAngle` takes deg, unlike Sketcher's radians) | Axis subelement outside `V_Axis`/`H_Axis`/`N_Axis`/an edge → `INVALID_INPUT` |
| Hole, threaded | `feature_hole(..., thread_type="ISOMetricProfile", cut_type=...)` | `ThreadType` assigned first, then `HoleCutType` validated against the **re-populated** enum and assigned | Cut type not in the post-`ThreadType` enum → `INVALID_INPUT` naming the legal set for that thread type |
| Hole, through | `feature_hole(..., depth_type="ThroughAll")` | `DepthType="ThroughAll"`; `Diameter` from a `Quantity` | `depth_type="UpToFirst"` → `INVALID_INPUT`; it is commented out in the source on both legs (`FeatureHole.cpp` `DepthTypeEnums`) |
| Fillet named edges | `feature_fillet(doc, body, base, name, edges=[Selector...], radius={value:2,unit:"mm"})` | `Base` set as LinkSub `(baseFeature, ['Edge3','Edge5'])`; `Radius` set; solid re-verified | An edge that FreeCAD silently drops (not exactly 2 adjacent faces, or not C0) → `INVALID_INPUT` **pre-bracket**, naming the dropped edges — never a silently smaller fillet |
| Fillet drops every edge | All requested edges fail the adjacency/continuity test | `INVALID_INPUT` pre-bracket; document untouched, no snapshot written | Validated pre-bracket |
| Chamfer equal distance | `feature_chamfer(..., size={value:1,unit:"mm"})` | `ChamferType="Equal distance"` (verbatim, spaces and capital A preserved); `Size` set | An unknown chamfer type → `INVALID_INPUT` against the live enum |
| Linear pattern | `feature_pattern(..., kind="linear", direction=Selector, length={value:10,unit:"mm"}, occurrences=3)` | `PartDesign::LinearPattern` with `Originals=[feature]`, `Mode="Extent"`, `Length`, `Occurrences=3` | `occurrences < 2` → `INVALID_INPUT` (`App::PropertyIntegerConstraint`) |
| Polar pattern | `feature_pattern(..., kind="polar", axis=Selector, angle={value:360,unit:"deg"}, occurrences=6)` | `PartDesign::PolarPattern`; at `Angle=360` the step is `Angle/Occurrences`, not `Angle/(Occurrences-1)` — documented in the tool description so an agent does not off-by-one it | No error expected |
| Mirror across a plane | `feature_mirror(..., mirror_plane=Selector, originals=[feature])` | `PartDesign::Mirrored` with `MirrorPlane` LinkSub and `Originals` | Unresolvable plane selector → `INVALID_INPUT` |
| Datum creation | `feature_datum(..., kind="plane"\|"axis"\|"point"\|"cs", attachment=Selector, offset=Quantity)` | Datum object created in the Body, attached via `AttachmentSupport`+`MapMode` through the existing `shim.set_attachment` | Unresolvable attachment → `INVALID_INPUT` |
| Edit a driving parameter | `feature_set_parameters(doc, feature, parameters={"Length":{value:8,unit:"mm"}})` | Named properties written, document recomputed, solid re-verified inside the bracket | Unknown property, read-only property, or a `Quantity` whose unit does not match the property's unit → `INVALID_INPUT` pre-bracket |
| Op leaves an invalid solid | Any feature op producing a shape failing `isValid()` | `post_verify` step 1/2 hard-fails → abort → recompute → re-hash proof; envelope `RECOMPUTE_ERROR` or `SPEC_FAILED`, `rolled_back=true`, explanation naming the feature | Reported, not raised |
| Snapshot-restore path ran | A failing op whose abort does not restore the hash | `run_mutation` returns the reopened document; the tool **rebinds** it in a `finally`; the next call on that handle operates on the live document | Registry holding a closed document is the DW-71 defect — asserted by test |
| Body not found | `body` names a non-existent or non-`PartDesign::Body` object | `INVALID_INPUT` naming the object | Pre-bracket |
| PartDesign unavailable | The capability probe fails on the running build | `INVALID_INPUT` naming the unavailable workbench; `query_capabilities` reports `partdesign_available: false` | Probed, never version-compared |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/features.py` -- NEW. The ten `feature_*` use cases + a shared `_feature_mutation` bracket helper. Placement fixed by `component-design.md` (P2, use-case ring).
- `src/freecad_buddy/contracts/feature.py` -- NEW. `FeatureState`, `ShapeSummary`, `PatternKind`/`DatumKind`/`ExtrudeType` literals. Nothing feature-shaped exists in `contracts/` today.
- `src/freecad_buddy/contracts/__init__.py` -- import block + `__all__` (alphabetical); every new contract symbol lands in both.
- `src/freecad_buddy/contracts/document.py` -- the authoritative `Selector` union (`kind` discriminator). Reuse; do not re-declare the mcp-tools `by` variant (Story 3.3 Spec Change Log records this reconcile).
- `scripts/gen_schemas.py:48-107` -- import, `WIRE_ROOTS` tuple, and `REQUIRED_FIELDS` entry (required for the root **and** every embedded `$def`); the generator fails on orphan files, so regeneration is mandatory.
- `src/freecad_buddy/usecases/sketches.py:516-560` -- `_sketch_mutation`: the exact bracket contract (precheck-inside-`with_document`, `rebound` list, `finally` rebind, state attach). The feature helper mirrors it.
- `src/freecad_buddy/usecases/sketches.py:101-156,481-513` -- `_quantity_value`/`_length_mm`/`_datum_value`/`_positive_datum`/`_point`, `_ids_survived`, `_selector_subelement`. Reuse rather than re-deriving; extract to a shared module only if duplication is otherwise unavoidable.
- `src/freecad_buddy/usecases/transaction.py:426-434` -- `run_mutation(document, handle, label, op, audit_sink=None, tool="", params=None) -> (document, envelope)`; `op` returns `list[str]` of touched Names.
- `src/freecad_buddy/usecases/transaction.py:192-262` -- `post_verify` steps 1-4 and the `fully_constrained` conjunction; feature tools inherit the rollback, they do not re-implement it. `_rollback_status` at `:265-271`.
- `src/freecad_buddy/usecases/documents.py:121-141` -- `with_document` (non-reentrant lock) and `rebind`.
- `src/freecad_buddy/usecases/verify.py` -- `verify_shape` is the source of the `shape_summary` fields; reuse, never re-read shape properties directly.
- `src/freecad_buddy/usecases/shim.py:117-131,154,192-207,234-249` -- `sketcher_available` (the probe template), `set_attachment`, `warm_capability_probes`, `capability_banner`. Add `partdesign_available` and the two cross-leg accessors here.
- `src/freecad_buddy/contracts/capabilities.py` + `scripts/gen_schemas.py:73-81` -- `CapabilityBanner` gains `partdesign_available`; both the TypedDict and `REQUIRED_FIELDS` must be updated (Story 3.3 did exactly this for `sketcher_available`).
- `src/freecad_buddy/hosts/tool_catalog.py:283-441,834` -- `_sketch_schema`/`_sketch_method` factories, `_sketch_specs()`, and the splice point in `tool_specs()`. Feature specs follow the same shape with `mutating=True`.
- `src/freecad_buddy/hosts/tool_catalog.py:32,205-220,542-564` -- `_DOC_SCHEMA`, `_QUANTITY_SCHEMA`, `_SUBELEMENT_SELECTOR_SCHEMA`, `_CONFIRM_SCHEMA`, and `READ_ONLY_PROFILE` (leave unchanged; its comment already reserves `feature_*`).
- `docs/references/FreeCAD/src/Mod/PartDesign/App/FeatureExtrude.h:47-60` + `git show 1.0.0:src/Mod/PartDesign/App/FeatureExtrude.h` -- the two legs' property sets; the diff that forces `Midplane` over `SideType`.
- `docs/references/FreeCAD/src/Mod/PartDesign/App/FeaturePad.cpp:41-46`, `FeaturePocket.cpp:42-47` -- `Type` enums and the `?TwoLengths` tombstone comment (issues #21794/#23612).
- `docs/references/FreeCAD/src/Mod/PartDesign/App/FeatureHole.cpp:76-103,1283-1320` -- static vs dynamically-repopulated enums.
- `docs/references/FreeCAD/src/Mod/PartDesign/App/FeatureDressUp.cpp:122-185` -- the silent edge-drop (`los.Extent() != 2` at `:141-145`, `Continuity != GeomAbs_C0` at `:147-154`, face expansion at `:158-181`).
- `docs/references/FreeCAD/src/Mod/PartDesign/App/FeatureRevolved.cpp:303-310` + `FeatureSketchBased.cpp:1322-1332` -- `ReferenceAxis` drives read-only `Base`/`Axis`; the `V_Axis`/`H_Axis`/`N_Axis` names.
- `docs/references/FreeCAD/src/Mod/PartDesign/App/Body.cpp:230-262,313` -- `addObject` semantics and `Group` ownership.
- `benchmarks/g2/dev/g2-dev-0{06..40}-*/case.yaml` -- the 35 feature commands these tools must satisfy. Three golden models only: `box-10-20-30`, `box40-hole-r5`, `cylinder-r5-h20`.
- `benchmarks/harness/assertions.py:99,496` -- `_graded_shape` (last shape-bearing object) and the `_MEASUREMENTS` table; all six feature-case `fn`s are already implemented.
- `benchmarks/_registry/validators.yaml` + `benchmarks/runner.py:75-77,318` -- no G2 entry exists; `_FAULT_SCORERS` has no `G2` key (DW-72).
- `tests/infc/test_sketch_tools.py`, `tests/infc/test_mutation_protocol.py:37-62` -- the in-FreeCAD fixture idiom and the snapshot-leftover assertion helper.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- DW-72/DW-73 (G2 scorer + `planted_op` callables; this story must assess, not silently skip), DW-70 (TNP Layer 1/2 gap the feature tools inherit), DW-82/DW-85 (unit enum, confirm gate — inherited, not this story's).

## Tasks & Acceptance

**Execution:**
- [ ] **Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)** -- Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md`; read `_bmad-output/project-context.md`; read `mcp-tools-design.md` §1.2/§2/§3.7 and `verification-design.md` §4. Confirm every PartDesign property, enum value and enum **ordering** against `docs/references/FreeCAD/src/Mod/PartDesign/App/` **on both legs** (`git show 1.0.0:<path>` for the floor leg) before writing code — never from memory, never from the 1.2-dev checkout alone.
- [x] `src/freecad_buddy/contracts/feature.py` + `contracts/__init__.py` -- Add `FeatureState`, `ShapeSummary` and the kind literals as TypedDict/Literal, stdlib only; export them -- the wire vocabulary must be contracts-owned before a producer exists (AD-17), and `shape_summary` is an untyped `{"type":"object"}` in the design catalog.
- [x] `scripts/gen_schemas.py` + `src/freecad_buddy/contracts/jsonschema/` -- Register the new wire root with its `REQUIRED_FIELDS` entry and regenerate -- the drift check fails CI otherwise.
- [x] `src/freecad_buddy/usecases/shim.py` + `contracts/capabilities.py` -- Add `partdesign_available()`, an `extrude_symmetric(obj, on)` accessor that writes `Midplane` (present on both legs), and an `enum_values(obj, prop)` helper wrapping `getEnumerationsOfProperty`; wire the probe into `warm_capability_probes` + `capability_banner` + `CapabilityBanner` + `REQUIRED_FIELDS` -- version-sensitive availability is probed, never version-compared (AD-11), and the 1.0/1.1 property divergence must not leak into the use case ring.
- [x] `src/freecad_buddy/usecases/features.py` -- Implement the ten tools (`feature_pad`, `feature_pocket`, `feature_revolve`, `feature_hole`, `feature_fillet`, `feature_chamfer`, `feature_pattern`, `feature_mirror`, `feature_datum`, `feature_set_parameters`) over one shared bracket helper that validates input in a `precheck`, calls `run_mutation`, rebinds in a `finally`, and attaches `feature_state` -- the story's substance; each is a `run_mutation` caller, never a transaction author.
- [x] `src/freecad_buddy/usecases/features.py` (dressup guard) -- Implement the pre-submission edge-survival check for `feature_fillet`/`feature_chamfer`: map each requested edge to its adjacent faces and its continuity, and reject any edge FreeCAD would silently erase -- `FeatureDressUp.cpp:141-154` drops them with no error and no return value, so a committed feature would silently ignore the user's selection.
- [x] `src/freecad_buddy/hosts/tool_catalog.py` -- Register the ten specs with hand-authored input schemas (`Selector`/`Quantity` refs, optional `confirm` passthrough), `mutating=True`, spliced into `tool_specs()`; leave `READ_ONLY_PROFILE` untouched -- registration is how the tools become reachable, and the profile guarantee must survive.
- [x] `benchmarks/_registry/validators.yaml` + `benchmarks/runner.py` -- Resolve DW-72/DW-73 now that a driveable mutation tool exists: wire the `G2` fault scorer and the `assertions` validator row, or record precisely what still blocks -- `gate.yaml` cites a validator named `assertions` that the registry does not define, and no G2 pass rate may be quoted while nothing scores it. Assess explicitly; never skip silently.
- [x] `tests/infc/test_feature_tools.py` -- stdlib `unittest` covering every I/O-matrix row: a pad/pocket/revolve/hole/fillet/pattern/mirror each reaching a valid solid, the `Midplane` symmetric path, the dynamically-repopulated `HoleCutType` rejection, the dressup silent-drop rejection, each pre-bracket validation, and a forced snapshot-restore asserting the registry was rebound -- the rollback, rebind and edge-drop paths cannot be proven by inspection.
- [x] `tests/external/test_feature_contract.py` -- pytest over the new contract types, schema drift, ring-import discipline, and that no `feature_*` name entered `READ_ONLY_PROFILE` -- contracts and the profile are stdlib-only and testable outside FreeCAD.
- [x] **Final Task: Quality Checks** -- Run `python scripts/check_imports.py`, `uv run python scripts/gen_schemas.py --check`, `uv run pytest tests/external`, `uv run python scripts/check_provenance.py`, `uv run ruff check`, and the in-FreeCAD suite via `FreeCADCmd tests/run_tests.py`.

**Acceptance Criteria:**
- Given each of the 35 `benchmarks/g2/dev/*-{pad,pocket,revolve,hole,dressup,pattern,mirror}` commands driven through the typed tools, when the sequence completes, then the produced solid satisfies that case's declared assertions, with every step committed through `run_mutation`.
- Given a fillet or chamfer request naming an edge FreeCAD would silently drop, when the tool is called, then it returns `INVALID_INPUT` naming that edge and no transaction is opened — a feature that ignored part of the selection never commits.
- Given the registered tool set, when the catalog is introspected, then all ten `feature_*` tools are present with `mutating=True` and none appears in `READ_ONLY_PROFILE`.
- Given any `feature_*` call, when it succeeds, then the envelope carries both a `mutation` block and a `feature_state` block whose `feature` names an object that exists in the document and is the Body's `Tip` for solid features.
- Given a tool whose op forces the snapshot-restore rollback path, when the tool returns, then the registry resolves the handle to the reopened live document and the next tool call on that handle succeeds.

## Spec Change Log

- **Pattern `Mode` and `TransformMode` have no cross-leg-portable literal value.** The spec's Design Notes asserted `Mode` is `['Extent','Spacing']` on both legs, derived from the 1.2-dev checkout. Re-verified against `git show 1.0.0:`: on FreeCAD 1.0.0 the linear values are `{"length","offset"}` and the polar values `{"angle","offset"}` — `Extent`/`Spacing` only arrived when the properties moved into `Part/App/*PatternExtension.cpp`. `TransformMode` diverges the same way. The tools therefore validate against the live enum and omit the property to take the build's default rather than assigning any literal. No new tool, no new status. Tracked as DW-92.

- **`Midplane=False` is a redundant write, not a neutral one.** The spec routes symmetric extrude through `Midplane` (correct — it is the only form present on both legs). Measured on 1.1.1: writing `Midplane=False` emits the deprecation warning even though it is the default, so `shim.extrude_symmetric` writes the property only when symmetry is actually requested.

## Review Triage Log

## Design Notes

**The 1.0/1.1 divergence is the sharpest trap in this story.** The vendored `docs/references/FreeCAD/` checkout is `weekly-2026.07.15` (1.2-dev), *not* either blocking CI leg. Reading it alone yields `SideType`/`Type2`/`Offset2` — none of which exist on the 1.0.0 floor leg. Verified both ways:

```
1.0.0  FeatureExtrude.h:  Type, Length, Length2, TaperAngle, TaperAngle2, Offset, ...   # no SideType
1.1.1  (live probe):      SideType ['One side','Two sides','Symmetric'], Type2, Offset2
1.0.0  Pad::TypeEnums:    {"Length","UpToLast","UpToFirst","UpToFace","TwoLengths","UpToShape"}
1.1.1  Pad Type:          ['Length','UpToLast','UpToFirst','UpToFace','?TwoLengths','UpToShape']
```

`Midplane` is an `App::PropertyBool` on `ProfileBased` and works on both legs — it is deprecated *on 1.2-dev only*, where it emits a warning and auto-translates. Use it. Everything else probed identical across legs: Chamfer's `ChamferType`, Fillet's `Radius`/`UseAllEdges`, `LinearPattern`/`PolarPattern` `Mode` `['Extent','Spacing']`, `Mirrored.MirrorPlane`, `Revolution.Type`, and Hole's `DepthType`/`DrillPoint`. Only `Hole.ThreadType` differs in length (6 on 1.0, 11 on 1.1) — which is why it is probed rather than hardcoded.

**Angles are degrees here, unlike the sketch layer.** `App::PropertyAngle` (Revolution `Angle`, Chamfer `Angle`, PolarPattern `Angle`) takes degrees, while Sketcher's `setDatum`/`Constraint` take radians. The wire unit is `deg` in both cases, so the feature tools pass the value through where the sketch tools converted it. Do not copy `_angle_radians` into this module by reflex — assert the unit and assign directly.

**Read-only outputs are not inputs.** `Revolution.Base` and `Revolution.Axis` are `Prop_ReadOnly | Prop_Hidden` and are computed from `ReferenceAxis` during execute (`FeatureRevolved.cpp:303-310`). Set `ReferenceAxis` only.

**Body/Tip ordering feeds the grader.** `Body.addObject` moves `Tip` only for solid features (`Body.cpp:246-249`), and the independent grader takes the *last* shape-bearing object in `document.Objects`. If those two disagree for a produced document, that is the Block-If — surface it, do not reorder objects to please the grader.

## Verification

**Commands:**
- `python scripts/check_imports.py` -- expected: `check_imports OK`
- `uv run python scripts/gen_schemas.py --check` -- expected: `gen_schemas --check OK` (byte-identical)
- `uv run pytest tests/external` -- expected: all pass, no regression against the 682-passing baseline
- `FreeCADCmd tests/run_tests.py` -- expected: the new `test_feature_tools` cases pass; no regression against the 242-test baseline
- `uv run python scripts/check_provenance.py` -- expected: `check_provenance OK`
- `uv run ruff check` -- expected: no new findings (10 pre-existing E501s in `scripts/automation/` and `tests/external/test_check_imports.py`)

**Manual checks (if no CLI):**
- Drive `g2-dev-006-pad` (5 mm pad on `box-10-20-30`) through the tools under `FreeCADCmd` and read `verify_shape` directly: the solid must be valid with the case's expected volume, and the audit log must carry one mutation record per tool call with both fingerprint digests.

## Auto Run Result

Status: done

The dev session timed out (`"status": "timeout"`, `expired_clock: "both"`) after 90 minutes
and 2.44M weighted tokens, pausing for manual rollback with nothing committed. The tree it left
held 3,556 coherent lines across `contracts/feature.py`, `usecases/features.py`, the
feature-state schema and both test legs, with one failing test, so the work was verified and
finished by hand rather than discarded.

### The one failure, and how it was decided

`test_the_same_cut_type_becomes_legal_once_its_thread_type_is_set` passed `diameter` together
with `thread_type`, which `feature_hole`'s precheck rejects — a contradiction inside the
timed-out session's own output.

Measured on FreeCAD 1.1.1 rather than argued: `Diameter` is **not** made read-only
(`FeatureHole.cpp` carries no `Diameter.setReadOnly` call), and assigning it alongside
`ThreadType=ISOMetricProfile` succeeds with the value persisting as `6.0 mm`. But the geometry
ignores it — the same hole bores `ThreadSize M1x0.25`. The guard's conclusion is therefore
correct and its stated reason was wrong; the message was corrected to say the diameter is
stored but never reaches the geometry, and the test now asserts the rejection.

### Verification

- `FreeCADCmd tests/run_tests.py` — `Ran 307 tests ... OK (skipped=1)` (143 before this epic)
- `uv run pytest tests/external` — `715 passed`
- `python scripts/check_imports.py` — `check_imports OK`
- `uv run python scripts/check_provenance.py` — `check_provenance OK`
- `ruff check` / `ruff format --check` — clean

### Residual risk

- `followup_review_recommended: true` — the story timed out before its review pass, so the ten
  feature tools have had **no independent adversarial review**. They pass every executable gate;
  nothing has read the diff for defects the tests do not cover.
- The hole-diameter guard is now the only place encoding the thread-sizing rule. If a future
  FreeCAD build lets `Diameter` drive a threaded bore, the guard becomes wrong in the opposite
  direction and the measurement above should be re-run.
