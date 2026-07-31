---
title: 'Story 3.5: TNP Guard Layers 1–2'
type: 'feature'
epic: 3
story: '3-5-tnp-guard-layers-1-2'
created: '2026-07-31'
status: 'in-review'
baseline_revision: '36bd870'
review_loop_iteration: 1
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-3-2-mutation-protocol-runtime.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** `audit_references` runs only Layer 0. On the supported path it compares nothing against its `snapshot` argument, so `REPOINTED`, `DROPPED`, `PASS` and `RE_BASELINED` are unreachable verdicts (DW-70) — a mutation that silently re-points `Pad.Profile` to a different element, or a fillet that silently loses an edge, leaves every object `isValid()`, the audit returns `CLEAN`, and `post_verify` commits it. 13 of the 29 G2 fault cases target this validator and 8 declare verdicts it structurally cannot emit, so G2.4 (5/5 scenarios flagged) has nothing to measure and DW-93 keeps the whole G2 scorer blocked.

**Approach:** Implement Layer 1 (per-entry mapped-name/witness/entry-count diff against the snapshot) and Layer 2 (`getElementHistory` ancestry cross-check, run only where Layer 1 is ambiguous) inside `tnp_guard.py`, extend the snapshot record with the resolution witness the diff needs, and thread the mutation's intended-target names from `run_mutation` into the audit so a designed change is `PASS`, not `REPOINTED`.

## Boundaries & Constraints

**Always:**
- **Verified against both blocking legs; measured live on 1.1.1.** `getElement`'s `silent` argument is **positional-only** (`PyArg_ParseTuple(args, "s|O")`, `TopoShapePyImp.cpp:2124-2139`) — `getElement(name, silent=True)` raises `TypeError: getElement() takes no keyword arguments`. Call `getElement(name, True)`; an unresolvable name returns a **null `Shape`** (`isNull() == True`), never `None` and never a raise. `verification-design.md §3.2` writes the keyword form; it is wrong and this spec supersedes it (record in the Spec Change Log).
- **`hasMissingElement` has no Python binding on either leg** (`App/ElementNamingUtils.h:97` and `App/GeoFeature.h:202` are C++-only). The existing `_split_subname` already reimplements it; keep that, and keep the constants `ELEMENT_MAP_PREFIX = ";"` / `MISSING_PREFIX = "?"` (`ElementNamingUtils.h:52,57`; identical at `1.0.0:...:44,48`).
- **A reference with no mapped name is not a broken reference.** Measured: `Part.makeBox(1,1,1).ElementMapSize == 0` and `ElementMap == []`, while a `PartDesign::Pad` shape carries 30 entries. So a link to a `Part::Box` `Face1` legitimately has `mapped is None`. Layer 1 grades such an entry by witness and resolution only — never `BROKEN` for a missing mapped half.
- **Layer 2 runs only where Layer 1 is ambiguous** (resolves, entry count intact, mapped name and witness both unchanged) — it is the expensive path and the design pins it to that case. `Shape.getElementHistory(mapped)` returns `(sourceTag:int, sourceName:str, [intermediates])` or `None` for an unmapped/indexed name (`TopoShapePyImp.cpp:2915-2943`; measured: `(2355, 'g1v22;SKT', ['#4:2;:H933,V'])`). Prefer the object-level `PartFeature.getElementHistory` only if the shape-level tuple proves insufficient; both exist on 1.0.0 unchanged.
- **The intended target exempts, it does not whitelist.** A reference whose owner is in the op's `touched` list, or whose entry the op deliberately rewrote, is `PASS` when it still resolves — that is the `g2-fault-tnp-control-intended-target` and `g2-fault-dressup-intended-edge-removal` controls. It is never exempted from the resolution check itself.
- **`ElementMapVersion` drift re-baselines, never fails** (AD-7). When an owner's live value differs from its snapshot value, its entries are `RE_BASELINED`, still reported, and `post_verify`'s existing filter (`transaction.py:254`) already excludes that verdict from failing.
- **`UNSUPPORTED` never coexists with `PASS`.** When `shim.element_map_available()` is false the whole audit is `UNSUPPORTED` and no reference reports `PASS` — the existing early return keeps that shape.
- Ring purity: `tnp_guard.py` is `usecases/` — stdlib + FreeCAD App only, FreeCAD never imported at module level (the document is passed in), version-sensitive calls through `shim.py`. Any new wire field is contracts-owned with a regenerated schema (AD-1/AD-12/AD-17).
- Status values and the `RefVerdict` set are already closed and complete — this story makes existing members reachable, it does not add one.

**Block If:**
- A fault-suite case's declared `expected_verdict`/`expected_layer` cannot be produced by the design's layer rules without special-casing that fixture. Report the case id and the measured verdict; do not edit the case to match the implementation (AD-13 — the suite is independent).
- Distinguishing `g2-fault-tnp-e-boolean-reorder-repoint` or `g2-fault-coincidental-witness-match` (both `expected_layer: 2`, both `must_not_be_caught_by: layer_1_witness_comparison`) requires ancestry data `getElementHistory` does not expose on the 1.0.x leg.

**Never:**
- Do not implement the confirm gate, `preview_dry_run`, or elicitation (Stories 3.6/3.7).
- Do not wire the `G2` fault scorer or `validators.yaml` rows, and do not quote a G2.4 or any G2 pass rate — DW-93 gates that on this guard **plus** DW-73's `planted_op` callables and DW-89. Reassess DW-70/DW-72/DW-93 explicitly and record the measured result; never skip silently.
- Do not materialize the 13 `fixture: pending` fault fixtures. This story proves the layers by in-FreeCAD unit tests over documents it builds itself; fixture materialization belongs with the scorer.
- Do not open, read, or reference `benchmarks/g2/heldout/`.
- Do not use `Shape.hashCode()` as the resolution witness. Verified: it hashes the `TShape` pointer identity plus Location (`ShapeMapHasher.h:37-49`), so a recompute changes it for a geometrically identical element — it would flag every reference on every mutation.
- Do not change `RefVerdict`, `TnpAuditBlock` or `RefFinding` field names; the audit vocabulary is shared with the preview diff (Story 3.6).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Unchanged reference | Mutation touches no reference-holding property | Every snapshotted entry `PASS`, `status: CLEAN`, layer 1 | No error expected |
| Silent re-point | Reference resolves, but its mapped name differs from the snapshot and its owner is not in `touched` | `REPOINTED`, `layer: 1`, `mapped_before` and `state_after` naming both mapped names | Reported, mutation rolls back |
| Witness moved, name intact | Mapped name unchanged but the resolved sub-shape's witness differs beyond tolerance, owner not in `touched` | `REPOINTED`, `layer: 1`, detail naming the witness delta | Reported |
| Dressup silent drop | A `LinkSubList` holds fewer entries than the snapshot; owner not in `touched` | `DROPPED`, `layer: 1`, detail carrying entries-before/after counts | Reported; this is the `FeatureDressUp` trap an error sweep misses |
| Intended edge removal | Same count drop, but the owner **is** in `touched` | `PASS` — the drop is the mutation's declared intent | No error expected |
| Reference stops resolving | `getElement(mapped, True)` returns a null shape, or the subname now carries `?` | `BROKEN`, `layer: 1` | Reported |
| Ambiguous entry, divergent ancestry | Mapped name and witness both unchanged, but `getElementHistory` returns a different `(sourceTag, sourceName)` than the snapshot | `REPOINTED`, `layer: 2` | Reported — the coincidental-witness case |
| Ambiguous entry, same ancestry | Name, witness and history all unchanged | `PASS`, `layer: 2` | No error expected |
| `ElementMapVersion` bump | Owner's live version differs from its snapshot value | Every entry under that owner `RE_BASELINED`, `layer: 1`, audit does **not** fail, findings still reported | `post_verify` already excludes `RE_BASELINED` |
| Entry with no mapped half | Link to a `Part::Box` `Face1` (`ElementMapSize == 0`) | Graded on resolution + witness only; `PASS` when both hold — never `BROKEN` for the absent mapped name | No error expected |
| History unavailable for an entry | `getElementHistory` returns `None` (unmapped/indexed name) | Layer 2 abstains; the Layer-1 verdict stands | Never `BROKEN` from an abstention |
| Element map unavailable | `shim.element_map_available()` false | `status: UNSUPPORTED`, one `UNSUPPORTED` finding per snapshotted reference, no `PASS` anywhere | Existing behavior preserved |
| Snapshot owner deleted | An owner in the snapshot is absent from the live document | `BROKEN`, `layer: 1`, detail naming the missing owner — unless it is in `touched`, where a deliberate delete is `PASS` | Reported |
| Witness read raises | `getElement` or a shape property raises on a live entry | Entry graded `BROKEN` with the exception text in `detail`; the audit never propagates the exception | Caught per entry |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/tnp_guard.py` -- the whole story. `snapshot_references` (`:122`) gains the per-entry resolution witness; `audit_references` (`:229`) gains `touched` and the Layer 1/2 passes. `_split_subname` (`:56`), `_link_sub_entries` (`:76`), `_element_map_version` (`:46`), `_unsupported_findings` (`:164`), `_invalid_object_findings` (`:180`) and `_missing_element_findings` (`:257`) are reusable as-is.
- `src/freecad_buddy/usecases/transaction.py:467` -- `refs_before = tnp_guard.snapshot_references(document)`; `:475` -- `post_verify(document, handle, touched, refs_before)`; `:253` -- the `audit_references(document, refs_before)` call that must now pass `touched`. `:254` already filters `RE_BASELINED`.
- `src/freecad_buddy/usecases/transaction.py:192-262` -- `post_verify` signature and step order; the TNP step is step 4 and stays there.
- `src/freecad_buddy/contracts/mutation.py:14-41` -- `RefVerdict` (all six members already declared), `RefFinding`, `TnpAuditBlock`. No new member; check whether `layer` needs no change (it is `int`).
- `src/freecad_buddy/usecases/shim.py:79-117` -- `element_map_available()` (probes `getElementHistory`/`ElementMapSize`/`ElementMap` on a box) and `element_map_version()`. **`element_map_version` is defective:** it returns `int(raw)` on a value measured as `'15.70200.5'`, so `int()` raises and it returns `None` unconditionally on 1.1.1. Assess and fix or record; `contracts/document.py:30` and `contracts/report.py:26` type it `int`, while `contracts/mutation.py:40` types the audit banner `str | None`.
- `src/freecad_buddy/usecases/exports.py:441` -- the other `shim.element_map_version()` consumer; a signature change touches it.
- `benchmarks/g2/fault-injection/tnp/*/case.yaml` -- the 5 scenarios + 3 controls, with `expected_verdict`/`expected_layer`/`must_not_be_caught_by` per case. The acceptance surface; all `fixture: pending`.
- `benchmarks/g2/fault-injection/dressup-drop/*/case.yaml` -- the count-drop defect and its two controls (`entries_before: 4`, `entries_after: 3`).
- `benchmarks/g2/fault-injection/coincidental-hash/*/case.yaml` -- the two Layer-2 cases.
- `tests/infc/test_mutation_protocol.py:240-290` -- `TnpGuardTest`: the fixture idiom, the `element_map_available` monkeypatch pattern, and the existing Layer-0 assertions that must keep passing.
- `tests/external/test_mutation_contract.py:43-128` -- the `RefVerdict` closed-set assertion and the callable checks.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- DW-70 (this story's charter), DW-72/DW-93 (the scorer, still gated), DW-89 (fingerprint over origin planes).
- `docs/references/FreeCAD/src/Mod/Part/App/TopoShapePyImp.cpp:2124-2139,2915-2943` -- `getElement` and `getElementHistory` bindings; `src/App/ElementNamingUtils.h:52,57` -- the prefix constants; `src/App/ComplexGeoData.pyi:152-158` -- `ElementMap`/`ElementReverseMap`/`ElementMapSize`.

**As landed:**

- `src/freecad_buddy/usecases/tnp_guard.py` -- `RefEntry` gains `witness` and `history`; module gains the `Witness`
  and `RecordKey` type aliases and `_WITNESS_EPSILON = 1e-7`. New capture helpers `_shape_of` / `_resolve_element` /
  `_mapped_name` / `_witness` / `_element_tolerance` / `_witness_moved` / `_history` / `_capture_entry`; new grading
  helpers `_keyed` / `_position` / `_pair_records` / `_entry_name` / `_entry_values` / `_finding` / `_grade_ancestry`
  (Layer 2) / `_live_element` / `_grade_resolution` / `_grade_entry` (Layer 1) / `_grade_entries` / `_grade_record` /
  `_reference_findings`. Record identity is `(owner, prop, target, occurrence)`; `_pair_records` matches a snapshot
  record to its live counterpart by exact key, falling back to the ordinal position within the `(owner, prop)` group
  so a link re-pointed to another object pairs with its replacement rather than reading as a vanished owner.
  `_grade_record`'s order is: owner absent -> `BROKEN` (returns alone); target changed -> `REPOINTED` (returns alone);
  `ElementMapVersion` drift -> a `RE_BASELINED` **annotation** that does not return; then the written-value exemption,
  which suppresses the entry-count comparison and nothing else; then the count comparison; then `_grade_entries`.
  Both the exempt and unexempt paths call `_grade_entries`, so an exempt record runs the identical per-entry diff
  against the value the op wrote. `snapshot_references` wraps `_capture_entry` inside the per-property `try`, so one
  unreadable shape skips that property rather than aborting the walk. `audit_references(doc, snapshot, written=None)`
  computes the live snapshot **once** and threads it to both `_missing_element_findings` and `_reference_findings`.
  `FLAGGED` counts only verdicts outside `PASS`/`RE_BASELINED`. `_element_map_version_banner` reads the verbatim
  string probe.
- `src/freecad_buddy/usecases/shim.py` -- `element_map_version_string()` added (verbatim `str | None`, feeds the TNP
  audit banner); `element_map_version()` keeps its `int | None` contract by narrowing to the leading dotted component.
  Both warmed in `warm_capability_probes`.
- `src/freecad_buddy/usecases/transaction.py` -- `run_mutation` captures `refs_written = snapshot_references(document)`
  between `op(document)` returning and `document.recompute()`; `post_verify` gains `refs_written` and passes it to
  `audit_references`. `_unrun_tnp_audit` reads the string probe. The `RE_BASELINED` filter and the step-4 position are
  unchanged. `touched` keeps its shape and its reporting role and is **not** consulted for the exemption.
- `tests/infc/test_tnp_guard.py` -- new, 44 cases: `SnapshotWitnessTest`, `LayerOneTest`, `WrittenValueExemptionTest`,
  `LayerTwoTest`, `NoMappedHalfTest`, `TargetIdentityTest`, `WholeObjectLinkTest`, `CapabilityGateTest`,
  `WitnessReadFailureTest`, `MutationRollbackTest`, plus the `_DroppingDocument` proxy that plants a silent edge drop
  in the post-capture window. `TargetIdentityTest` covers a genuine multi-target `PropertyLinkSubList` in three
  directions (unchanged -> CLEAN, one target swapped -> one PASS + one REPOINTED, targets reordered -> CLEAN);
  `WrittenValueExemptionTest` covers the exemption failing to cover a moved witness, a changed mapped name and a
  divergent Layer-2 ancestry; `LayerOneTest` covers a re-baseline concurrent with an entry drop.
- `tests/external/test_mutation_contract.py` -- `_split_subname` dict assertions extended for the two new fields, plus
  16 new contract tests: the `written` signature, the `post_verify` threading, the capture-point ordering inside
  `run_mutation`, the **absence** of any `in touched` exemption, the `hashCode` ban, the positional `getElement` form,
  the bounding-box witness excluding `CenterOfMass`, the tolerant witness comparison, Layer 2 dropping the
  intermediates, the record key carrying the target, the key disambiguating a repeated target, the re-baseline branch
  not short-circuiting, the exemption reaching the same per-entry grader, the two-probe typing, both probes being
  warmed, and the verbatim banner.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- DW-70 closed with a resolution describing the landed
  written-value design; DW-72 and DW-93 reassessed with measured counts (28 cases, 24 pending); DW-94 added recording
  the re-triage of the six previously-deferred review findings (four fixed, one fixed after measurement, one open).

## Tasks & Acceptance

**Execution:**
- [ ] **Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)** -- Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md`; read `_bmad-output/project-context.md`; read `verification-design.md §3` (the TNP guard contract) and §1.3 (`post_verify`). Confirm every element-map API name, argument form and return shape against `docs/references/FreeCAD/` **and** by live probe under `FreeCADCmd` before writing code — the design doc's `getElement(mapped, silent=True)` is already known wrong.
- [x] `src/freecad_buddy/usecases/shim.py` -- Assess and resolve `element_map_version()`: the probed value is the dotted string `'15.70200.5'`, so the `int()` cast can never succeed and the function is a constant `None`. Fix it to return the build's real version (and reconcile the `int` typing at `contracts/document.py:30` / `contracts/report.py:26` with the `str | None` audit banner), or record precisely why it must stay -- the re-baseline rule and the audit banner both read this value, so a permanently-`None` version silently disables drift detection.
- [x] `src/freecad_buddy/usecases/tnp_guard.py` (snapshot) -- Extend `RefEntry` with the resolution witness the diff needs (a cheap deterministic geometric descriptor — sub-shape type plus bbox/centre-of-mass, never `hashCode()`), captured per entry at snapshot time and tolerant of an entry that does not resolve -- Layer 1 cannot detect a same-name re-point without a witness, and `verification-design §3.1` names the witness a mandatory captured field.
- [x] `src/freecad_buddy/usecases/tnp_guard.py` (Layer 1) -- Implement the per-entry diff: resolution check, mapped-name comparison, witness comparison with an explicit tolerance, `LinkSubList` entry-count comparison, the `touched` intended-target exemption, and the `ElementMapVersion` re-baseline branch; emit `PASS`/`BROKEN`/`REPOINTED`/`DROPPED`/`RE_BASELINED` with `layer: 1` -- this is the guard proper and the reason DW-70 is `high`.
- [x] `src/freecad_buddy/usecases/tnp_guard.py` (Layer 2) -- Implement the ancestry cross-check over entries Layer 1 left ambiguous only, comparing `getElementHistory`'s `(sourceTag, sourceName)` against the snapshot's; divergence is `REPOINTED` with `layer: 2`, an abstention (`None` history) leaves the Layer-1 verdict standing -- the two `must_not_be_caught_by: layer_1_witness_comparison` cases are unreachable otherwise.
- [x] `src/freecad_buddy/usecases/transaction.py` -- Thread `touched` into `audit_references` from `post_verify`, keeping the `RE_BASELINED` filter and the step-4 position -- without the op's intended targets every deliberate re-point and every intended edge removal reads as a silent one, failing both clean controls.
- [x] `benchmarks/` + `deferred-work.md` -- Reassess DW-70 (close it or state exactly what remains), DW-72 and DW-93 against the working tree now that the guard can emit every verdict, and record the measured case counts -- Story 3.4 established the reassess-don't-skip precedent, and DW-93 names this story as one of its two gating conditions.
- [x] `tests/infc/test_tnp_guard.py` -- stdlib `unittest` covering every I/O-matrix row on documents the test builds: a PartDesign body whose pad carries a real element map (measured: 30 entries) for the resolving cases, a `Part::Box` link for the no-mapped-name case, a forced `LinkSubList` truncation for `DROPPED` and its `touched` control, a monkeypatched `ElementMapVersion` for `RE_BASELINED`, and a monkeypatched history for the Layer-2 divergence -- the verdicts are unreachable today, so nothing but an executable test can prove they became reachable.
- [x] `tests/external/test_mutation_contract.py` -- Extend with the ring-import and contract assertions for any changed signature or wire field, and assert `audit_references` accepts the `touched` argument -- contracts and import discipline are testable outside FreeCAD.
- [x] **Final Task: Quality Checks** -- Run `python scripts/check_imports.py`, `uv run python scripts/gen_schemas.py --check`, `uv run pytest tests/external`, `uv run python scripts/check_provenance.py`, `uv run ruff check`, and the in-FreeCAD suite via `FreeCADCmd tests/run_tests.py`.

**Acceptance Criteria:**
- Given each of the 5 TNP fault scenarios reproduced as an in-FreeCAD test, when the guard audits after mutate → recompute, then 5/5 are flagged with the case's declared `expected_verdict` at its declared `expected_layer`, and each case marked `must_not_be_caught_by: layer_0_error_sweep` is proven to survive a Layer-0-only audit unflagged.
- Given the three TNP clean controls and the two dressup controls, when the guard audits, then every one reports `CLEAN` with no non-`PASS`, non-`RE_BASELINED` finding — the guard's false-alarm surface is what makes the sensitivity figure meaningful.
- Given a mutation whose `post_verify` receives a `REPOINTED` or `DROPPED` finding, when `run_mutation` completes, then the envelope carries a non-`OK` status, `rolled_back` true with a proven rollback, and an explanation naming the owner, property and verdict.
- Given an audit on a build where `shim.element_map_available()` is false, when it returns, then `status` is `UNSUPPORTED` and no finding carries `PASS` — the pre-existing guarantee survives both new layers.
- Given the full in-FreeCAD suite, when it runs, then the existing `TnpGuardTest` Layer-0 cases still pass unchanged — the new layers extend the audit, they do not replace it.

## Spec Change Log

**1. `verification-design.md §3.2` writes `getElement(mapped, silent=True)`; the keyword form does not exist.** Re-confirmed live on 1.1.1: `getElement() takes no keyword arguments` (`PyArg_ParseTuple(args, "s|O")`, `TopoShapePyImp.cpp:2124-2139`). The implementation calls `getElement(name, True)` positionally. An unresolvable name returns a Shape with `isNull() == True`, never `None` and never a raise. The design doc is wrong on this point and this spec supersedes it; the design doc is left unedited because the correction is an API-call form, not a contract change.

**2. Link properties store the INDEXED subname, so the mapped half must be resolved at capture time.** The spec's Layer-1 rule "mapped name differs from the snapshot" is unimplementable as written against what `snapshot_references` originally captured: measured, `PartDesign::Fillet.Base` holds `['Edge2', 'Edge5', ...]` and `SketchObject.ExternalGeometry` / `AttachmentSupport` hold `[(obj, ('Face6',))]` — all indexed, so `_split_subname` sets `mapped = None` for every real reference and a mapped-name comparison would never fire. `_capture_entry` now resolves the shadow through `Shape.getElementMappedName(indexed)` (measured: `'Face6'` -> `'#14:1;:G0;XTR;:Hb30:8,F'`) and records it. Caught by `test_a_reference_whose_mapped_name_changed_is_repointed_at_layer_one`, which failed `CLEAN != FLAGGED` before the fix.

**3. A whole-object link stores the subname `""`, which names no element and is not a broken reference.** The I/O matrix has no row for it. Measured: `PartDesign::Plane.AttachmentSupport` = `[(YZ_Plane, ('',))]` on a datum attached to an origin plane. Grading it by resolution reported `BROKEN` and regressed `test_feature_tools.MirrorTest.test_a_mirror_across_a_bisecting_plane_doubles_the_hole` (`TNP audit flagged 1 reference(s): MidPlane.AttachmentSupport BROKEN`). Layer 1 now returns `PASS` for an empty entry name before the resolution check, covered by `WholeObjectLinkTest`. Added as an I/O-matrix row in effect; the read-only `<intent-contract>` was not edited.

**4. `element_map_version()` resolved by splitting the probe in two rather than by changing its type.** The spec asks for a fix or a recorded reason. The value is the dotted string `'15.70200.5'`, but `contracts/report.py:26` (`ReportBanner`) and `contracts/document.py:30` (`MappedNameSelector`) type it `int` and the emitted JSON Schema says `{"type": "integer"}` — while `contracts/mutation.py:40` (`TnpAuditBlock`) types it `str | None`. Naively returning the string would have made `usecases/verify.py:_banner()` and `usecases/exports.py:_banner()` emit a string into an integer-typed wire field on every verify and export report, converting a dormant defect into a live schema violation (no test would have caught it: the in-FreeCAD banner tests assert key presence only). Widening `ReportBanner` to `str` instead is an enum/type change, which the project's wire rules make a major bump. Resolution: `shim.element_map_version_string()` returns the build value verbatim and feeds the `str`-typed TNP audit banner; `shim.element_map_version()` narrows to the leading integral component (`'15.70200.5'` -> `15`) for the `int`-typed `ReportBanner`/`MappedNameSelector` consumers. Both wire contracts keep their declared types, `gen_schemas --check` stays byte-identical, and drift detection is live because the guard's re-baseline branch compares the per-owner `GeoFeature.ElementMapVersion` string, not this build-level probe.

**5. The witness is the sub-shape type plus bounding-box corners, and deliberately excludes `CenterOfMass`.** Measured: `Part.Vertex` raises `AttributeError: 'Part.Vertex' object has no attribute 'CenterOfMass'`, so a CoM-bearing witness would fail on vertex references. `BoundBox` reads on every shape type. Comparison is per-component with an epsilon floored at the element's own `Shape.getTolerance(1)` (measured `1.0000000000000002e-07`), never `==`, per the tolerance policy.

**6. Layer 2 compares only `(sourceTag, sourceName)`, not the intermediate list.** `getElementHistory` returns `(sourceTag, sourceName, [intermediates])`; the third member is rebuild-order sensitive, so including it would flag legitimate recomputes. Measured stable across no-op recompute, unrelated object add, forced `touch()` rebuild and a genuine length change within one process: `(565, 'g1;SKT', [...])` unchanged throughout.

**7. The third acceptance criterion had no executable coverage until the orchestrator's verification pass.** The guard's 30 unit tests grade `audit_references` directly and stop there; `test_mutation_protocol.py`'s rollback cases are driven by other failure modes. So "a `REPOINTED`/`DROPPED` finding yields a non-`OK` envelope with proven rollback and an explanation naming owner, prop and verdict" was observed manually but asserted nowhere. Added `MutationRollbackTest` to `tests/infc/test_tnp_guard.py`: an op that silently truncates the fillet's `Base` `LinkSubList` is driven through `run_mutation`, and the test asserts `SPEC_FAILED`, `rolled_back`, a non-null `rollback_proven`, a fingerprint equal to the pre-op hash, and an explanation containing `Fillet`, `Base` and `DROPPED`. The handle is minted by `registry.document_create` and rebound onto the fixture document — `DocumentRegistry` exposes `rebind`, not a `bind`.

**8. The exemption is keyed to the written value, so `audit_references` takes `written`, not `touched` (decision 014).** Supersedes the `<intent-contract>`'s owner-level wording wherever the two conflict, per the human resolution recorded in `docs/decisions/014-tnp-intended-target-is-what-the-op-wrote.md` and now inline in `verification-design.md §3.2`. `run_mutation` captures `refs_written = tnp_guard.snapshot_references(document)` between the op returning and `document.recompute()` — measured readable at that point: a `Fillet.Base` written to three entries reads back as three before any recompute. The `op` callable signature is unchanged, so Stories 3.3 and 3.4 stay closed and no `feature_*` or `sketch_*` tool was touched. `touched` keeps its meaning for reporting in `post_verify` and is not passed to the guard; a contract test pins that neither the `touched` parameter nor an `in touched` test survives anywhere in `tnp_guard.py`.

**9. The written-value exemption must be bounded to the count check, or it re-introduces the blindness it was meant to remove.** Caught by test, not by review: a first cut returned one record-level `PASS` as soon as `live == written`, which skipped the per-entry loop entirely — so an intended-target reference that had stopped resolving graded `PASS`, failing `test_the_exemption_never_covers_an_unwritten_reference_on_a_written_owner` with `'BROKEN' not found in ['PASS']`. `_grade_resolution` now runs per entry even on an exempt record, and only the entry-count comparison is excused. The Design Notes' "the exemption is bounded" rule is therefore load-bearing at record level too, not only at entry level.

**10. FreeCAD 1.1.1 marks an unresolvable dressup entry `?missing` rather than removing it, so a genuine count drop cannot be provoked from the Python API.** Measured across four attempts: shrinking the pad under a chamfer yields `Base == ['?Edge1', '?Edge2', 'Edge3', 'Edge4']` with `isValid() == False` (a Layer-0 `BROKEN`, not a `DROPPED`); deleting a sketch line under a fillet leaves `Base` at four entries and the fillet `Valid`; a forced `touch()` + recompute re-maps names but keeps the count. The entry count only ever falls when something writes the property. `MutationRollbackTest` therefore plants the drop with a `_DroppingDocument` proxy that rewrites `Fillet.Base` on the first `recompute` — inside the window `run_mutation` opens between its post-op capture and `post_verify`, which is exactly where a drop the op did not write would land. The planted-drop framing is what the acceptance check requires; it is not a workaround for a guard limitation.

**11. A forced `pad.touch()` + recompute is a real mapped-name re-point, not a Layer-2 fixture.** A test asserting that `touch()` exercises the ancestry path measured `FLAGGED != CLEAN`: `Fillet.Base` entry `Edge1` moved from `#f:1;:G;XTR;:H48c:7,E` to `#35:2;:G;XTR;:H48c:7,E` and entry `Edge2` likewise, so Layer 1 correctly reported `REPOINTED` and the entries never reached Layer 2. The Design Notes' claim that a mapped name is "unchanged across a forced `pad.touch()` rebuild" holds for `getElementMappedName("Face6")` read directly off the pad, but not for a dressup's stored `Base` entries, whose shadows are re-resolved against the rebuilt map. Layer 2's intermediates rule is pinned by a direct `getElementHistory` comparison instead.

**12. `PartDesign::Body.Origin.OriginFeatures` is ordered axes-then-planes, so index 1 is `Y_Axis`, not a plane.** Measured: `[X_Axis, Y_Axis, Z_Axis, XY_Plane, XZ_Plane, YZ_Plane, Origin001]`. A `FlatFace` attachment to `OriginFeatures[1]` fails with "No planar face in AttachEngine3D::calculateAttachedPlacement()", leaving the datum invalid and producing a legitimate Layer-0 `BROKEN` that masks the whole-object-link row under test. The fixture selects the plane by `TypeId == "App::Plane"` rather than by index.

**13. A `Fillet.Base` is a `PropertyLinkSub`, not a `PropertyLinkSubList`.** Measured: `fillet.getTypeIdOfProperty("Base")` returns `App::PropertyLinkSub` and the value reads `(<PartDesign::Pad>, ['Edge1', ...])`. The design doc and the `dressup-drop` fault cases describe the dressup edge list as a LinkSubList; `_link_sub_entries` already normalizes both shapes to `[(target, subs)]`, so the count comparison works either way, but a reader looking for a `PropertyLinkSubList` on a fillet will not find one.

**14. Five of the six previously-deferred review findings were resolved during re-derivation rather than re-deferred.** Fixed with tests: the unchecked entry *gain* (now `REPOINTED`, `test_a_gained_entry_is_flagged_rather_than_passing_silently`), the NaN witness grading `PASS` (comparison written `not (delta <= tol)`), the one-sided witness skipping the check (a missing side now counts as moved), and `snapshot_references` running three times per audit (the live snapshot is computed once in `audit_references` and threaded to both consumers, so one document walk replaces three). The target-identity gap was **measured before fixing**: two `Part::Box` objects with identical geometry both report `mapped: None` and `history: None`, so re-pointing a `Sketcher` `AttachmentSupport` from one to the other graded `PASS layer 2 | Face1 has no comparable element history`; `_grade_record` now compares `record["target"]` against `live["target"]` and grades a change `REPOINTED` at layer 1, ordered *before* the `ElementMapVersion` branch so a re-point onto a differently-versioned object cannot report `RE_BASELINED` instead. Only the per-record (rather than per-entry) `?`-dedup remains open, recorded as DW-94 — a record holding one `?` entry alongside a genuinely re-pointed entry would have the re-point suppressed with it. That case was not reproduced on a live document, so it is recorded as a code-reading observation rather than a measured defect.


**15. The exemption's falsifiability was proven by mutation testing, not asserted.** The reverted run shipped a fully green suite around a blind exemption, so "the tests cover it" is not evidence here. Three mutations were injected into `_grade_record` and the suite re-run under `FreeCADCmd` each time. (a) `intended = True` — the reverted owner-blind behaviour, where every record is exempt: **12 failures**, including `test_a_drop_the_op_did_not_write_is_dropped_even_when_the_op_wrote_the_property` and the end-to-end `MutationRollbackTest.test_a_drop_the_op_never_wrote_rolls_the_mutation_back_with_a_proven_restore`. This is the check the previous implementation structurally could not fail. (b) Dropping `_grade_resolution` from the exempt path — the unbounded exemption of change-log entry 9: **1 failure**, `test_the_exemption_never_covers_a_reference_that_stopped_resolving`. (c) The same mutation against that test's *first* form, which asserted only `assertIn("BROKEN", verdicts)`: **0 failures** — the test was insensitive, because an op-written unresolvable entry also invalidates its owner and Layer 0 emits a `BROKEN` for the same property regardless. The test now asserts a Layer-**1** `BROKEN` specifically and names the offending element; that is what makes it bite. Any future change to the exemption should be re-checked with mutation (a), since it is the one the story exists to prevent.

**16. The new mutation tests made a pre-existing racy snapshot cleanup in three other fixtures fail intermittently, and the fix belongs in this suite.** Observed as 344-test runs alternating between `OK (skipped=1)` and `FAILED (failures=12, errors=4)` with the failures landing in `test_sketch_tools`, not in the guard's own cases. Root cause: `_SketchFixture.setUp` (and the equivalents in `test_mutation_protocol.py` and `test_feature_tools.py`) glob `FCB_TMP_snap_*` and then `os.listdir` each hit, which raises `FileNotFoundError: [WinError 3]` when the directory is removed between the two calls. That cleanup is pre-existing and untouched by this story, but it never fired before because no earlier suite left a snapshot behind: `MutationRollbackTest` is the first fixture outside those three to call `run_mutation`, and `_BodyFixture` had no snapshot sweep, so its leftovers raced the alphabetically-later `test_sketch_tools`. **Verified pre-existing-but-not-triggered rather than assumed:** the baseline at `36bd870` ran green 6/6 while the working tree alternated. Fixed inside this story's own file — `_BodyFixture` now clears the reserved prefix with `shutil.rmtree(..., ignore_errors=True)` in both `setUp` and `tearDown`, which is also race-tolerant. Confirmed stable 8/8 consecutive runs afterwards. The three pre-existing fixtures still carry the racy `os.listdir` form; that is left alone per the surgical-changes rule and is worth hardening the next time one of them is edited.

**17. Record identity is `(owner, prop, target)`, never `(owner, prop)` — a link property may hold several targets.** Triggering finding: `_record_key` returned `(owner, prop)` while `snapshot_references` emits one record per `(target, subs)` pair (`:317-326`), so `_reference_findings`' `live_by_key` / `written_by_key` dicts silently overwrote all but the last target and graded every snapshot record against it. Reproduced on an *unchanged* document: two `AttachmentSupport` targets (`BoxA/Face1`, `BoxB/Face2`) produced `REPOINTED | now links a different object: BoxA -> BoxB`, which fails `post_verify` and rolls back a valid mutation; the other N-1 references are never graded at all. Reachable through the shipped `sketch_add_external_geometry` (`sketches.py:1067` calls `addExternal`, appending a pair), and both `SketchObject.h:103` (`ExternalGeometry`) and `AttachExtension.h:92` (`AttachmentSupport`) are `App::PropertyLinkSubList`. Known-bad state to avoid: any record-identity tuple that omits the target. The re-derivation must also cover a multi-target link in the tests — the previous `TargetIdentityTest` used a single-target list and so could not fail.

**18. The written-value exemption excuses the entry-count comparison and nothing else.** Triggering finding: the exempt branch returned after `_grade_resolution` only, so the mapped-name check, the witness check and the Layer-2 ancestry check were all skipped for the property the op wrote — while the function's own docstring asserted "Every entry still runs the per-entry diff". Reproduced: an op writes `["Edge1","Edge2","Edge3"]`, the geometry those names bind to then moves 99 mm, and all three entries grade `PASS`. Change-log entry 9 records an earlier cut of this same branch being caught skipping the per-entry loop and repaired by adding `_grade_resolution` — resolution is a liveness check (`getElement` returns non-null), not the diff, so the repair was incomplete and the docstring was updated to claim more than the code did. Known-bad state to avoid: an exempt path that returns without running the same per-entry grading an unexempt record runs. The correct shape is to compute the per-entry verdicts exactly as normal and suppress only the record-level count verdict; `test_the_exemption_never_covers_a_reference_that_stopped_resolving` is necessary but not sufficient, because resolution is the one check the broken version did run.

**19. An `ElementMapVersion` re-baseline annotates the record; it must not short-circuit the other record-level checks.** Triggering finding: the version branch `return`ed a lone `RE_BASELINED`, and since `post_verify` filters that verdict as non-failing (`transaction.py:256`), drift concurrent with an entry drop reported `CLEAN` and committed. Reproduced: version `15.70200.5 -> 16.70200.5` with `Base` falling from four entries to one yields exactly one `RE_BASELINED` finding and zero failing findings. This is reachable rather than theoretical — `GeoFeature.cpp:261-262` populates `_ElementMapVersion` from an empty default on first geometry computation, so any object whose geometry first computes *during* the audited mutation transitions `"" -> "15.70200.5"` and takes the branch. (This does not contradict the KEEP note that a freshly created Pad reports a version immediately: the snapshot is taken *before* the op runs, so the record's snapshot value is the pre-creation one.) AD-7's rule is that a version bump never *fails* the audit, not that it suppresses grading; the entry-count and target checks must still run and still report, with the re-baseline recorded alongside them. Known-bad state to avoid: an early `return` from the version branch.

**20. Making the target part of the record key makes the `target != live["target"]` branch unreachable by exact lookup, so pairing needs a positional fallback.** Change-log entry 17 requires the target in the record identity; doing only that regressed two tests to `['BROKEN'] != ['REPOINTED']` and `['PASS', 'BROKEN'] != ['PASS', 'REPOINTED']`. Mechanism: a re-point *changes the key*, so the snapshot key `(Attached, AttachmentSupport, BoxA, 0)` has no live counterpart, `_grade_record` takes its `live is None` branch and reports "no longer present in the document" instead of "now links a different object". Resolution: `_pair_records` matches by exact key first, then pairs each leftover snapshot record with the live record holding the same ordinal position within its `(owner, prop)` group. Exact-match-first is what keeps the fallback safe — see entry 21.

**21. Target-keyed pairing and positional pairing disagree on a reordered multi-target link, and the target must win.** Measured: `AttachmentSupport = [(BoxA, ('Face1',)), (BoxB, ('Face1',))]` rewritten as `[(BoxB, ('Face1',)), (BoxA, ('Face1',))]` reads back in the written order, so both references still exist and the correct verdict is `CLEAN`. Pairing by position alone yields `REPOINTED | BoxA -> BoxB` and `REPOINTED | BoxB -> BoxA` — two false failures on a document whose reference set did not change. This is the case that makes the target component of the key falsifiable: dropping the target while keeping the occurrence counter (entry 17's weaker form) passes every other test, because snapshot and live iterate in the same order and occurrence 0 accidentally pairs with occurrence 0. `test_a_reordered_multi_target_link_pairs_each_target_with_itself` is the test that fails under that mutation and only that test.

**22. The exempt path is graded against the written entries, not the snapshot entries.** `_grade_record`'s exempt branch calls `_grade_entries(doc, record, written["entries"], live["entries"])` while the unexempt branch calls it with `record["entries"]`. The two lists are the same length by construction (the exemption's own condition is `_entry_values(live) == _entry_values(written)`), and the written reading is the correct baseline: it is the value the op assigned, which is what the live state must still hold. Grading an exempt record against the *snapshot* would re-introduce the count mismatch the exemption exists to excuse. `_grade_entries` also handles the empty-entry record with a single `PASS`, which is what `Pad.Profile` (measured: zero entries) produces.

**23. The `?`-missing dedup now keys off the paired live record rather than a separate key set.** `_reference_findings` previously built a `reported` set of live keys and skipped any snapshot record whose key was in it. With `_pair_records` in place the paired record is already in hand, so the skip reads `paired is not None and any(entry["missing"] ...)`. Same behaviour, one less lookup, and it stays correct when the pairing came from the positional fallback rather than an exact key match. DW-94's open per-record-versus-per-entry dedup observation is unchanged by this.

**24. Four mutations were injected and every one was caught; one first attempt was insensitive and the test was strengthened rather than the result accepted.** Run under `FreeCADCmd` against the full suite each time. (a) *Record key omits the target, occurrence counter kept* — first attempt: **0 failures**, because snapshot and live iterate in the same order so occurrence 0 pairs with occurrence 0. The test was insensitive, not the mutation harmless; `test_a_reordered_multi_target_link_pairs_each_target_with_itself` was added from the measurement in entry 21 and the same mutation then produced **1 failure**, that test alone. (b) *Record key is run 2's exact `(owner, prop)` plain-dict overwrite* — **2 failures**: `test_a_multi_target_link_property_audits_clean_when_nothing_changed` and `test_a_multi_target_link_grades_each_target_against_its_own_snapshot`. (c) *Exempt branch returns after `_grade_resolution` only* (run 2's defect 2 verbatim) — **3 failures**, one per skipped check: `..._a_witness_that_moved_under_an_op_written_name`, `..._a_mapped_name_that_changed`, `..._a_divergent_ancestry_at_layer_two`. (d) *Version branch returns a lone `RE_BASELINED`* — **1 failure**: `test_a_re_baseline_annotates_the_record_without_hiding_a_concurrent_drop`. (e) The run-2 regression mutation `intended = True` (the owner-blind exemption) — **11 failures**, including the end-to-end `MutationRollbackTest.test_a_drop_the_op_never_wrote_rolls_the_mutation_back_with_a_proven_restore`.

**25. `_history`'s conversions moved inside its `try`, and `_capture_entry` moved inside `snapshot_references`' per-property `try`.** Two of the findings the deferred ledger recorded against the reverted code were cheap to close while writing the same lines and are closed here rather than re-deferred. `_history` previously ran `int(record[0])`/`str(record[1])` outside the `try` guarding `getter(mapped)`, so a build returning an unexpected history shape would raise out of `snapshot_references` and be rendered to the operator as a failed mutation; the conversions are now inside it, matching every sibling probe helper. `snapshot_references` previously closed its per-property `try` before the `_link_sub_entries` loop, so a raise inside `_capture_entry` (which touches `getElementMappedName`, `getElement`, `BoundBox` and `getElementHistory`) escaped the whole walk instead of skipping the one unreadable property; the loop is now inside the same `try`, preserving the documented "a property that cannot be read is skipped, never raised" contract.

## Review Triage Log

### 2026-07-31 — Review pass
- intent_gap: 1: (high 1, medium 0, low 0)
- bad_spec: 0
- patch: 0
- defer: 6: (high 0, medium 4, low 2)
- reject: 13: (high 1, medium 7, low 5)
- addressed_findings:
  - none

### 2026-07-31 — Review pass (re-derivation)
- intent_gap: 0
- bad_spec: 3: (high 2, medium 1, low 0)
- patch: 0
- defer: 3: (high 0, medium 2, low 1)
- reject: 22: (high 0, medium 9, low 13)
- addressed_findings:
  - `[high]` `[bad_spec]` `_record_key` is `(owner, prop)` while `snapshot_references` emits one record per `(target, subs)` pair, so a multi-target `PropertyLinkSubList` collapses to one key. Reproduced on unchanged input: two `AttachmentSupport` targets yield a false `REPOINTED BoxA -> BoxB`, which fails `post_verify` and rolls back a valid mutation, and leaves N-1 references ungraded. Reachable through the shipped `sketch_add_external_geometry` (`sketches.py:1067` `addExternal`); both `SketchObject.h:103` and `AttachExtension.h:92` are `PropertyLinkSubList`. Spec amended to make record identity include the target.
  - `[high]` `[bad_spec]` The written-value exemption returns after `_grade_resolution` only (`tnp_guard.py:651-668`), so the mapped-name, witness and Layer-2 ancestry checks are all skipped on the exempt record — while the same function's docstring claims "Every entry still runs the per-entry diff". Change-log entry 9 shows an earlier cut was caught skipping the loop and was repaired with resolution alone, which is a liveness check, not the diff. Spec amended to define the exemption as excusing the entry-count comparison and nothing else.
  - `[medium]` `[bad_spec]` The `ElementMapVersion` branch returns a lone `RE_BASELINED` (`tnp_guard.py:634-648`), which `post_verify` filters as non-failing, so drift concurrent with an entry drop reports `CLEAN` and commits. Reproduced: version bump plus 3-of-4 edges dropped yields 0 failing findings. `GeoFeature.cpp:261-262` populates `_ElementMapVersion` from empty on first geometry computation, so an object first computed during the audited mutation takes this path. Spec amended so a re-baseline annotates rather than short-circuits the record-level checks.

## Design Notes

**Measured on FreeCAD 1.1.1, not assumed.** A `Part.makeBox` has `ElementMapSize == 0` and an empty `ElementMap`, while a `PartDesign::Pad` built from a sketch carries 30 entries:

```
pad.Shape.ElementMap  -> {'#10:2;:G;XTR;:H933:7,E': 'Edge2', '#14:1;:G0;XTR;:H933:8,F': 'Face6', ...}
pad.Shape.getElementHistory('#10:2;:G;XTR;:H933:7,E')
    -> (2355, 'g1v22;SKT', ['#4:2;:H933,V'])
pad.resolveSubElement('Face1', False, 0)
    -> (<PartDesign::Pad>, ';#d:1;:G;XTR;:H933:7,F.Face1', 'Face1')
```

Two consequences the implementation must not get wrong: the guard's own test fixtures need a PartDesign body to exercise Layer 1/2 at all (a `Part::Box` document silently tests nothing), and a reference with no mapped half is normal rather than broken.

**`element_map_available()` probes attribute presence, not map population.** It calls `Part.makeBox` and checks `getElementHistory`/`ElementMapSize`/`ElementMap` exist — which is the right availability question, but it returns `True` on a build whose probe box has an empty map. Do not tighten the probe into a population check; grade absence per entry instead.

**Witness tolerance.** Compare geometric witnesses with an epsilon, never `==` — and per the tolerance policy no comparison may be tighter than the measured shape's own `Shape.getTolerance`. A witness that reads as "moved" on floating-point noise turns every mutation into a false `REPOINTED`, which is the failure mode the three clean controls exist to catch.

**Mapped names are stable within a process and unstable across processes.** Measured on 1.1.1: `getElementMappedName("Face6")` on a pad returned `'#14:1;:G0;XTR;:H235:8,F'` unchanged across a no-op recompute, an unrelated object add, a forced `pad.touch()` rebuild and a real length change — but the `H…` component differed between separate `freecadcmd` runs of the same script (`Hab5`, `Hdfe`, `H1357`). This is what makes Layer 1's mapped-name comparison sound: the guard only ever compares a snapshot to a live read inside one process and one mutation bracket. It also means a mapped name must never be persisted across sessions as a stable identity, and `ElementMap` **keys** are not durable reference identities either — after `pad.touch()` + recompute the key `#10:2;…` was absent from the rebuilt map while the link's own `Edge2` still resolved. The guard therefore snapshots link-property subnames and resolves the shadow, rather than harvesting `ElementMap` keys.

**Layer ordering inside Layer 1, and what makes an entry "ambiguous".** The per-entry order is: empty subname (whole-object link) -> `PASS`; missing marker or null `getElement` -> `BROKEN`; mapped name differs -> `REPOINTED`; witness moved beyond tolerance -> `REPOINTED`. Only an entry that survives all four reaches Layer 2, which is exactly the design's "resolves, entry count intact, mapped name and witness both unchanged" definition of ambiguous. Entry-count and `ElementMapVersion` are record-level checks and run before the per-entry loop, because a re-baseline supersedes every entry verdict under that owner and a count drop is a property-level fact rather than an entry-level one.

**The written value exempts, and the exemption is bounded.** Superseded from the reverted run: the exemption is keyed to the value the op wrote, never to `touched` (decision 014). `run_mutation` reads every reference after the op returns and before `recompute()`; a record whose live entry names equal that reading is graded against the written value rather than against the snapshot, so the entry count the op itself chose is not a drop. The exemption excuses the count comparison only — every entry still runs `_grade_resolution`, so an intended-target reference that stops resolving is still `BROKEN`. This is what separates `g2-fault-dressup-intended-edge-removal` (the op wrote the shorter list -> `PASS`) from `g2-fault-dressup-silent-edge-drop` (the op wrote four, three came back -> `DROPPED`), and unlike an owner test it is falsifiable: `MutationRollbackTest` plants a drop the op never wrote and the guard must fail it.

**`Pad.Profile` snapshots zero entries.** Measured: `Profile` is a `PropertyLinkSub` holding a whole-object link to the sketch with an empty subname list, so it contributes a record with `entries == []`. That is correct and not a capture failure — there is no sub-element to grade. The spec's problem statement describes a re-point of `Pad.Profile` to "a different element"; on the measured build a profile link carries no element, so that particular scenario is graded by the record-level target/deletion checks rather than by the per-entry diff.

**The exemption's granularity is the record, its scope is per entry.** `_grade_record` decides *whether* a record is
exempt by comparing the whole live entry-name list against the whole written one — a record is exempt or it is not,
there is no partially-exempt record. But an exempt record is still graded *per entry* for resolution, so the exemption
suppresses the count, mapped-name, witness and ancestry comparisons without suppressing `BROKEN`. Getting this
backwards (a single aggregate `PASS` for the record) is what Spec Change Log entry 9 records.

**Record-level checks and their order.** They run before the per-entry loop because each supersedes every entry
verdict under that owner: owner absent -> `BROKEN`; target object changed -> `REPOINTED`; `ElementMapVersion` drift ->
`RE_BASELINED`; then the written-value exemption; then the entry-count comparison. Target identity must be checked
before the element-map version, or a re-point onto an object with a different map version would report
`RE_BASELINED` and never fail.

**Why the capture point cannot move.** `refs_written` must be read after `op(document)` returns and before
`document.recompute()`. Reading it earlier misses what the op wrote; reading it after recompute reads FreeCAD's edit as
if the op had made it, which restores exactly the blindness decision 014 removed.
`test_run_mutation_captures_the_written_references_before_recompute` asserts the three source positions in order, so a
later refactor that moves the call cannot pass silently.

**`written=None` means "no exemption", not "exempt everything".** `audit_references` defaults `written` to `None` so a
direct audit outside a mutation bracket grades every reference. The guard against `_entry_values(None) == []`
accidentally exempting an empty record is the explicit `written is not None` test ordered first in the conjunction.

**Test fixtures need a PartDesign body.** A `Part::Box` has `ElementMapSize == 0`, so a document built from boxes has
`mapped is None` and `history is None` on every entry and exercises neither layer. `_BodyFixture` builds
sketch -> pad -> fillet; the pad carries 30 element-map entries. The `Part::Box` path is still covered deliberately, by
`NoMappedHalfTest` (a reference with no mapped half is graded, never `BROKEN`) and by `TargetIdentityTest` (two boxes
are the case where only target identity can tell a re-point apart).

**`OriginFeatures` ordering.** A `PartDesign::Body` origin exposes `X_Axis`, `Y_Axis`, `Z_Axis` at indices 0-2 and
`XY_Plane`, `XZ_Plane`, `YZ_Plane` at 3-5, with `Origin001` (an `App::Point`) at 6. Indexing `[1]` for a plane yields
`Y_Axis`, and attaching a datum plane to it with `MapMode = "FlatFace"` fails at recompute with "No planar face in
AttachEngine3D::calculateAttachedPlacement()" — which the guard then correctly reports as a Layer-0 `BROKEN`. The
fixture filters by `TypeId == "App::Plane"` rather than indexing.

## Verification

**Commands:**
- `python scripts/check_imports.py` -- expected: `check_imports OK`
- `uv run python scripts/gen_schemas.py --check` -- expected: `gen_schemas --check OK` (byte-identical)
- `uv run pytest tests/external` -- expected: all pass, no regression against the 715-passing baseline
- `FreeCADCmd tests/run_tests.py` -- expected: the new `test_tnp_guard` cases pass; no regression against the 307-test baseline (`OK (skipped=1)`)
- `uv run python scripts/check_provenance.py` -- expected: `check_provenance OK`
- `uv run ruff check` -- expected: no new findings (10 pre-existing E501s in `scripts/automation/` and `tests/external/test_check_imports.py`)

**Manual checks (if no CLI):**
- Under `FreeCADCmd`, build a body → sketch → pad → fillet, snapshot, then truncate the fillet's `Base` `LinkSubList` by one entry and recompute: the audit must report `DROPPED` at layer 1 with the entries-before/after counts in `detail`, while the same document with the fillet's owner in `touched` must report `PASS`.

## Auto Run Result

Status: blocked
Blocking condition: intent gap in intent contract

The implementation landed complete and green, then adversarial review found that the
`<intent-contract>`'s own definition of the intended-target exemption makes the guard blind on
the ops it most needs to grade. Because the root cause is inside the read-only contract, the code
was reverted per the intent_gap branch and the run halts for a human decision.

### The gap

The contract specifies the exemption at **owner** granularity, in five places:

- Boundaries: "A reference whose **owner** is in the op's `touched` list … is `PASS` when it still resolves."
- I/O matrix: three rows qualify the failure verdicts with "owner **is not** in `touched`", and the
  intended-edge-removal row grants `PASS` when "the owner **is** in `touched`".

The implementation matched that verbatim (`tnp_guard.py` `_grade_record`: `intended = record["owner"] in touched`).
It did not deviate from the spec — the spec is what is wrong.

Measured consequence: every mutation tool returns `touched = [feature.Name, body.Name]`
(`features.py:486,718,860,1027,1358,1422,1490` and `feature_set_parameters` at `:1571`). So:

- `feature_fillet` always places `Fillet` in `touched`, which exempts `Fillet.Base` from the
  entry-count check — **the FreeCAD dressup silent-edge-drop trap, the guard's headline purpose,
  is switched off for the exact op that triggers it** (`FeatureDressUp.cpp:141-154` erases edges
  with no error and no return value).
- `feature_set_parameters` on a Pad exempts every reference the Pad owns, so a `Profile` or
  `UpToFace` that silently re-points during the forced re-solve grades `PASS`.

Both reviewers reached this independently and ranked it their most severe finding.

### The decision a human must make

The exemption needs entry- or property-level granularity, and there is no single reading of the
contract that supplies it. The two candidate resolutions differ in cost and blast radius:

1. **Ops declare `(owner, prop)` pairs** instead of bare Names. Precise, but changes the `op`
   callable contract in `run_mutation` and touches all ten `feature_*` and eight `sketch_*` tools —
   i.e. it reopens Stories 3.3 and 3.4.
2. **The guard diffs against the value the op actually assigned**, exempting only entries the op
   wrote. No signature change, but the guard must observe the write, which it currently cannot.

Choosing is a design decision with real cost either way, so it is escalated rather than guessed.

## RESOLVED 2026-07-31 — option 2 (guard diffs against the value the op assigned)

Human decision, recorded in `docs/decisions/014-tnp-intended-target-is-what-the-op-wrote.md` and
written into `verification-design.md` §3.2 so the contract no longer admits the object-level
reading.

**The exemption is keyed to the value the op wrote, never to reference ownership.**
`run_mutation` captures each snapshotted reference's value immediately after the op callable
returns and *before* `recompute()`. A reference is exempt only when its post-op value equals the
one the op assigned. `touched` keeps its current shape and meaning for reporting; it is no longer
consulted for the exemption, so `_grade_record`'s `record["owner"] in touched` test is removed.

Consequences for the re-derivation:

- No `op` callable signature change. Stories 3.3 and 3.4 stay closed; the ten `feature_*` and
  eight `sketch_*` tools are not touched.
- All new work is inside the mutation runtime: one capture point in `run_mutation` plus the
  grading change in `tnp_guard`.
- The DROPPED entry-count comparison must run on `feature_fillet`. A test writing a known
  four-entry `Fillet.Base`, dropping one entry behind the guard, and asserting the verdict is
  DROPPED rather than PASS is the acceptance check — the previous implementation could not fail
  this test, which is why a fully green suite still shipped the defect.
- The `dressup-intended-edge-removal` control must still grade PASS: the op wrote the shorter
  list, so its post-op value matches and the exemption legitimately applies.
`/bmad-loop-resolve 3-5-tnp-guard-layers-1-2` is the intended next step.

### What was verified before the revert

The implementation was fully green — these were observed, not claimed, and are recorded so the
re-derivation has a baseline to beat:

- `FreeCADCmd tests/run_tests.py` — `Ran 339 tests` / `OK (skipped=1)` (307 baseline + 30 guard
  cases + 2 end-to-end rollback cases)
- `uv run pytest tests/external` — `722 passed` (715 baseline + 7)
- `python scripts/check_imports.py` — `check_imports OK`
- `uv run python scripts/gen_schemas.py --check` — `gen_schemas --check OK`
- `uv run python scripts/check_provenance.py` — `check_provenance OK`
- `uv run ruff check` — `Found 10 errors` (exactly the 10 pre-existing E501s, zero new)

All six `RefVerdict` members were reachable with executable coverage, closing DW-70's charter.
After the revert the tree is back to `Ran 307 tests ... OK (skipped=1)`.

### KEEP for re-derivation

Six Spec Change Log entries above record measured FreeCAD facts that cost real probe time and must
survive: the positional-only `getElement(name, True)`, link properties storing *indexed* names
(so the mapped shadow must be resolved at capture via `getElementMappedName`), whole-object links
storing subname `""`, the `element_map_version` two-probe split that keeps both wire contracts
typed as declared, the bounding-box witness that excludes `CenterOfMass` (`Part.Vertex` has none),
and Layer 2 comparing only `(sourceTag, sourceName)`.

One measured correction to a review claim, recorded so it is not re-litigated: the Edge Case
Hunter reported that `_ElementMapVersion` starts empty and would fire a spurious `RE_BASELINED`
on every first mutation. Probed on FreeCAD 1.1.1 — a freshly created Pad, Sketch and Body all
report `'15.70200.5'` immediately, unchanged across a parameter edit. The claim is false on this
build; the re-baseline branch is correct as written.

### Review findings breakdown

- intent_gap 1 (high) — the owner-scoped exemption above; halted on it.
- defer 6 — appended to `deferred-work.md`: unchecked entry *gain*, NaN witness grading PASS,
  one-sided witness skipping the check, target identity never compared, `snapshot_references`
  running three times per audit, and double-reported `?`-missing references.
- reject 13 — including the disproven `ElementMapVersion` claim above, and findings that restated
  behavior the contract explicitly specifies.
- patch 0, bad_spec 0 — no code survives the revert, so nothing was patched.

### Residual risk

- The six deferred findings were reviewed against code that no longer exists. They are defects of
  the *design as specified* and will recur in any re-derivation that follows the current contract,
  so they should be read alongside the intent gap rather than treated as a separate backlog.
- DW-70 remains **open**. It was closed in the reverted work and the ledger's DW-72/DW-93
  reassessment (which survives the revert, in `deferred-work.md`) describes a guard that is not
  currently in the tree — re-read it as a record of what the implementation achieved, not of the
  present state.
