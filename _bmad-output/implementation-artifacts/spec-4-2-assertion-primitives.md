---
title: 'Story 4.2a: Assertion Primitives'
type: 'feature'
created: '2026-10-03'
status: 'done'
baseline_commit: '806955a163d47afba479acbf9f9a0495aa071477'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
  - '{project-root}/benchmarks/g3/README.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The agent cannot measure a part against a G3 spec. Six of the 11 §7.2 primitives do not exist, nothing resolves an anchor frame, and no selector is honoured.

**Approach:** Implement the closed §7.2 vocabulary, its selectors and one shared anchor-frame resolver in `usecases/`, with names in `contracts/`, and reach them through MCP `verify_shape`. The benchmark harness delegates to the same code.

**Decisions (2026-10-03):**
- **D1 — Split.** This spec covers epic ACs 1-3. Replay scoring (G3.E.4) and the cross-leg frame check (G3.E.3) move to Story 4.2b (`deferred-work.md`).
- **D2 — Placement (1A).** Measurements in `usecases/assertions.py`; `verify_shape` gains `anchor_frame` and the §7.2 vocabulary; `benchmarks/harness/assertions.py` delegates §7.2 fns to it. The changed sources stale the G0 `verify_shape` and G2 `assertions`/`verify_sketch` scores, so this story re-runs those scorers and refreshes `validators.yaml`.
- **D3 — `expect_bbox` (2A).** Compares sorted extents measured in the frame; `expect_extent` stays directional.

## Boundaries & Constraints

**Always:**
- Selector, `hole_diameter` and empty-match semantics are exactly `benchmarks/g3/README.md:62-85`.
- `largest_planar_face`: largest area, then lowest centroid Z, then lowest sorted mapped name; origin at the face centroid, +Z from the face into the part. The resolved entity goes in the report banner.
- Tolerance never tighter than `Shape.getTolerance`; defaults linear ±0.05 mm, angle ±0.1°, volume ±1 %.
- Every validator score in `validators.yaml` is current and meets its bar when the story ends.

**Never:**
- No done-predicate, aggregate verdict beyond the existing `derive_verdict`, iteration count or repair logic.
- No sub-element index selector; feature metadata only as `detail.hint`.
- No plan replayer, sensitivity score, cross-leg check, render or TechDraw work.
- No edit to G3 spec or fault-case data; no unseal.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Hole match | `hole_position select {diameter: 12}` on a part with that bore at frame (0,0) | `passed: true`, measured `[0,0]` | — |
| Empty match | selector matches nothing | check fails, `detail.code = invalid_input.unsupported_assertion` | never a pass |
| Missing frame ref | `named_datum` ref absent | frame-dependent checks fail with that code; volume/validity still measured | — |
| Symmetric part | two equal largest faces | tie-break picks one; banner names it | unresolvable tie raises → frame checks fail with that code |
| Malformed check | unknown `fn`, index selector `Face6`, wrong `expect` arity | `verify_shape` raises `ValidationError` (status `INVALID_INPUT`); harness `evaluate` turns it into a failing check | — |
| No frame given | `verify_shape` without `anchor_frame` | global frame; banner says `global` | — |

</frozen-after-approval>

## Code Map

- `benchmarks/harness/assertions.py:26-27` `_band`, `:106` `_graded_shape`, `:284-430` five fns (§7.3 rules 1-3), `:564-578` `_MEASUREMENTS`/`SUPPORTED_FNS`/`evaluate` -- move §7.2 logic out; keep G2 extras (`expect_solid_count`, sketch checks) here. `tests/external/test_mutation_contract.py:289` pins `SUPPORTED_FNS`.
- `src/freecad_buddy/usecases/verify.py:195` `_check_expect_bbox` (ordered global extents), `:256-262` `_ASSERTIONS`, `:291` `verify_shape`, `:310` `read_shape` -- dispatch to the new module; keep `expect_solid_count`/`expect_valid`/`expect_watertight`.
- `src/freecad_buddy/contracts/assertions.py` -- holds `AnchorFrame{origin, axes, units}`; add vocabulary names and declared frame `{kind, ref}`.
- `src/freecad_buddy/hosts/tool_catalog.py:1225-1239` -- `verify_shape` schema and description.
- Source-hash lists, all four must match: `benchmarks/runner.py:97-119`, `benchmarks/g2/fault-injection/score_g2_infc.py:82-87`, `score_g2_validators.py` `VALIDATOR_SOURCES`, `benchmarks/g0/fault-injection/score_verify_shape.py:49-51`.
- `benchmarks/g0/fault-injection/*/case.yaml` -- three `expect_bbox [10,20,30]` cases; sorted semantics keep `wrong-bbox` (Z=60) detected.
- `tests/infc/test_harness_assertions.py:27-50` `_ShapeFixture` -- fixture pattern; `tests/infc/test_verify_tools.py:144,207,216-227` -- existing bbox and `ValidationError` tests.
- `benchmarks/g3/dev/*/case.yaml` -- selector shapes in use: `select {diameter}`, `{axis}`, `{diameter, axis}`; `select_a/select_b` with `{hole: {diameter}}`, `{face: {normal}}`, `{face: {diameter}}`; same selector on both sides means distinct matches (015, 020).
- `docs/references/FreeCAD/` -- confirm `optimalBoundingBox`, element-map API (mapped names) on 1.0 and 1.1 before use.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/contracts/assertions.py` -- add `ASSERTION_FNS` (11 names), `AnchorFrameKind`, `DeclaredAnchorFrame{kind, ref}` -- closed vocabulary in contracts (§7).
- [x] `src/freecad_buddy/usecases/assertions.py` -- new: frame resolver (three kinds), selector resolution to logical holes and faces (§7.3 rules 1-4), the 11 primitives, `evaluate_checks(document, shape, anchor_frame, checks)`.
- [x] `src/freecad_buddy/usecases/verify.py` -- `verify_shape`/`read_shape` accept `anchor_frame`; route §7.2 fns to `usecases/assertions.py`; banner records the resolved frame.
- [x] `src/freecad_buddy/hosts/tool_catalog.py` + `contracts/jsonschema/` -- add `anchor_frame` to `verify_shape`; regenerate schemas.
- [x] `benchmarks/harness/assertions.py` -- delegate §7.2 fns; optional `anchor_frame` argument; keep G2 extras and the failing-check wrapper.
- [x] four source-hash lists -- add `usecases/assertions.py` to `verify_shape` and `assertions`.
- [x] `tests/infc/test_assertion_primitives.py` -- one test per primitive pass and fail, per frame kind, tie-break, and every I/O matrix row.
- [x] `tests/infc/test_verify_tools.py`, `tests/external/test_mutation_contract.py` -- update for sorted bbox and the larger vocabulary.
- [x] `benchmarks/_registry/validators.yaml` -- re-run `score_verify_shape.py` and `score_g2_infc.py` under FreeCADCmd; write the new shas and rates.
- [x] `benchmarks/g3/gate.yaml`, `benchmarks/g3/README.md` -- state that the primitives landed and G3.E.3/G3.E.4 wait for 4.2b.
- [x] `_bmad-output/planning-artifacts/architecture/.../design/mcp-tools-design.md` §3.3 -- document `anchor_frame` and the vocabulary.

**Acceptance Criteria:**
- Given each of the 11 §7.2 fns, when `verify_shape` runs it on a matching and a violating FreeCAD part, then it passes and fails respectively, with `(passed, measured, expected, tolerance, detail)`.
- Given the three G3 frame kinds, when resolved on the same part translated and rotated, then frame-relative measurements are unchanged.
- Given the live GUI bridge, when the 4 control plans are replayed with `replay_g3.py` and each spec's checks sent to `verify_shape`, then every check passes; and `g3-fault-plan-wrong-hole-diameter` fails `hole_diameter`.
- Given `runner faults` and `validators.yaml`, when checked, then every score is current and meets its bar.

## Design Notes

- `largest_planar_face` in-plane X: global X projected onto the face; global Y when that projection is degenerate. Without mapped names, the last tie-break uses centroid (X, Y); a remaining tie raises.
- `base_sketch_plane`/`named_datum`: the object matched by `Name`, then by unique `Label`; frame = its global placement. Ambiguous or absent → unresolvable.
- `hole_position`/`hole_diameter`/`hole_through` with several matches: every match must equal `expect`.

## Implementation Notes

- New `usecases/assertions.py` holds validation, the frame resolver, selectors and the 11 primitives; `evaluate_checks` returns `(checks, frame_banner)`. `verify.py` keeps `expect_solid_count`/`expect_valid`/`expect_watertight`; `harness/assertions.py` keeps the three G2 extensions. `SUPPORTED_FNS` has 14 names.
- When `verify_shape` receives checks, a §7.2 check id is `assert.<fn>`, so `shape.volume` and `shape.bbox` become `assert.expect_volume` and `assert.expect_bbox`. A checkless call keeps the `shape.*` measured facts. `tests/uat/testcases/TC-07-verification-and-export-pairing.md` is updated to match.
- The measured shape is placed in document coordinates (`document_shape`), so a feature inside a moved Body is measured where the frame is.
- Re-scored under FreeCADCmd after the last `verify.py` edit: G0 `verify_shape` 11/11 detected, 0/1 false alarm; G2 `assertions` 8/8 detected, 0/3 false alarm. `score_g2_infc.py` exits 1 with "BARS NOT MET" because `fingerprint`, `run_mutation` and `verify_sketch` have no scorable fault case. They were unscored at the baseline too.
- `uv run pytest tests/external`: 5 failures, all G1 grader-hash tests that fail at the baseline. The baseline had 6; the G2 currency test now passes after the re-score.
- `ruff format --check` fails on `benchmarks/runner.py` at the baseline too; no other file this story touched is unformatted.
- Live GUI run (FreeCAD 1.1.1, `:8765`): the 4 control plans pass every spec check; `wrong-hole-diameter` fails `hole_diameter` (measured 8.0 against 5.5). Its four `distance_between` checks fail `INVALID_INPUT` through the empty-match rule, so the part verdict is `INVALID_INPUT`; Story 4.2b must count detections per check. No 011 control exists, so the 011 check replayed `mirrored-hole-pattern` with its planted step replaced by the spec placement (in `replay_verify.py` only; no case data edited): OK 8/8, `hole_position` [0, 0] for the 12 mm bore and [60, 0] for the 8 mm hole, and the top-view screenshot agrees. The planted plan fails both `hole_position` checks with the holes swapped. Evidence: `tests/uat/run/2026-10-03-03/evidence/` (no `report.md`).
- The `largest_planar_face` mapped name carries a hasher tag that differed between two runs of the same plan (`#78:1;:H453,F` headless, `#78:1;:He0a,F` GUI). The tie-break only reads it when area and centroid Z tie; Story 4.2b's cross-leg check must not compare the banner `entity` text for this kind.
- `view_fit_viewport` again framed a 1.81 mm region on the named-datum document while reporting OK; this is the bug already logged in `deferred-work.md`.
- Review pass 1 patches applied: a measurement exception is now an `INVALID_INPUT`-coded check; the harness measures all §7.2 checks of one call in a single `evaluate_checks` call; `verification-design.md` §7.1/§7.2, `data-contracts-design.md` §5.1 and the G0 fault README document the frame rules, contract types and sorted bbox; new tests pin the MCP `anchor_frame` schema, harness frame forwarding, face-frame axes and an off-centre face-frame position, Label lookup and ambiguous labels, the tolerance floor on a real shape, all 20 G3 dev specs through `validate_check`, and the G0 `verify_shape` sha (runner == scorer == registry).
- Final state after the patches and the G0/G2 re-score: `FreeCADCmd tests/run_tests.py` 667 run, OK (1 skipped); `pytest tests/external` 1157 passed, 5 failed (the baseline G1 grader-hash failures); `check_imports`, `gen_schemas --check` and `ruff check src benchmarks` OK. `tests/external/test_harness_g0.py` fails `ruff format --check` at the baseline too. Live-run report: `tests/uat/run/2026-10-03-03/report.md`.

## Spec Change Log

## Review Triage Log

Pass 1 (2026-10-03). Layers: blind-hunter (BH), edge-case-hunter (EC), verification-gap (VG).

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| BH1 | `largest_planar_face` mapped-name tie-break is not stable across sessions | medium | Same plan gave `#78:1;:H453,F` (headless) and `#78:1;:H1306,F` (GUI); the `H` part is an object tag. The rule is AD-13's, reached only after area and centroid Z tie; no current spec reaches it | defer (design correction for AD-13, 4.2b) |
| BH2 / EC-del | Sorted `expect_bbox` loses orientation; G0 README row and verification-design §7.2 still say per-axis | low | Sorting is human decision D3; only the two docs are stale | patch (docs only) |
| BH3 / VG-o1 / EC 775, 958 | Empty selector match makes a defective part read `INVALID_INPUT` | false | Frozen Always and `benchmarks/g3/README.md:82` define exactly this; the measured `hole_diameter` failure stays visible per check; noted for 4.2b in Implementation Notes | reject |
| BH4 / EC 943 | `count_cylindrical_holes` with `select` and `expect: 0` can never pass | low | Follows the empty-match rule; no spec uses it; fix adds a branch | reject |
| BH5 | Harness resolves the frame and classifies walls once per check | low | `_measure_primitive` calls `evaluate_checks(..., [check])` per check; correct but repeats `isInside` probes; batching is a direct simplification | patch |
| BH6 / VG-o2 | G2 callers never pass the declared frame | low | Every G2 primitive is frame-independent; behaviour unchanged | reject |
| BH7 | Harness and `verify_shape` choose different default objects | false | `verify_shape` took the first object at the baseline too; the design-doc edit aligns the doc to the code | reject |
| BH8 | `assert.<fn>` vs `shape.*` ids for one quantity | low | Checkless facts keep `shape.*`; checks carry `assert.<fn>` as in the harness; consumers updated (TC-07) | reject |
| BH9 / EC 220, 252, 218, 254, 263 | Unhashable `fn`/`kind`, unvalidated extension checks, `pattern` key | low | `pattern` is used by G2 cases; extension checks were unvalidated at the baseline; unhashable values are never shown reachable from a real spec | reject |
| BH10 | `shape_floor` failure aborts the call | false | Same behaviour as the baseline `_shape_floor`; loud failure | reject |
| BH11 | Frame rules and new contract types absent from the binding design docs | medium | verification-design §7.1 has no tie-break, origin or axis rule; data-contracts-design has no `AnchorFrame`/`ASSERTION_FNS` | patch |
| BH12 / VG1-7 | Test gaps: MCP schema `anchor_frame`; harness frame forwarding; face-frame in-plane axes; Label lookup and ambiguous label; shape-tolerance floor on a real shape; G3 dev specs through `validate_check`; G0 sha mirror; malformed frame declarations | medium | Each gap filed with a demonstration that a regression passes every test | patch |
| BH13 | UAT run has no report; script hard-codes paths | low | No `report.md` in `tests/uat/run/2026-10-03-03`; hard-coded paths match the 4.1 replay script | patch (report only) |
| EC 1199 | A measurement that raises becomes an uncoded failing check, read as `SPEC_FAILED` | medium | `evaluate_checks` generic `except` builds `_check(...)` without a code; Story 4.2b would count a crash as a detection, and the frozen intent says an unevaluable check is `INVALID_INPUT` | patch |
| EC 471 | OCC error in frame resolution escapes | low | Never shown reachable; loud failure | reject |
| EC 372 | Several Bodies: `XY_Plane` resolves to the first Body | low | Name-then-Label is the approved rule; G3 specs are single-body | reject |
| EC 389 | `ref` naming a non-datum object resolves silently | low | Ref is spec-declared; fix adds type guards | reject |
| EC 512 | `rel`-only tol with `expect: 0` gives a 0 band | low | Every G3 angle and position check declares `abs`; fix adds a branch | reject |
| EC 117 | Infinite `tol` passes everything | low | Only a hostile spec; fix adds guards | reject |
| EC 453 | In-plane X unstable when the face normal is near document X | low | Rule approved in Design Notes; no G3 face-frame spec has such a face | reject |
| EC claim | AC2 "translated and rotated" does not hold for a rotation about the face normal | low | In-plane X follows document X by the approved rule; all three face-frame specs assert positions at `[0, 0]`, which no such rotation changes; documented in the BH11 doc patch | reject |
| EC replay | `replay_verify.py` grades the first object when a plan has no feature | low | Evidence script, not shipped; every replayed plan has features | reject |

## Verification

**Commands:**
- `micromamba run -n fcb FreeCADCmd tests/run_tests.py` -- expected: all pass.
- `uv run pytest tests/external` -- expected: no new failures (6 pre-existing failures are listed in 4.1).
- `uv run ruff check . && uv run ruff format --check .` -- expected: clean.
- `python scripts/check_imports.py`, `uv run python scripts/gen_schemas.py --check` -- expected: OK.
- `uv run python -m benchmarks.runner faults G2` -- expected: exit 0, validators current.
- `git diff benchmarks/_registry/validators.yaml` after the FreeCADCmd re-runs -- expected: only `verify_shape`, `assertions`, `verify_sketch` blocks change; each keeps sensitivity ≥0.95 and false-alarm ≤0.05.

**Manual checks:**
- Live GUI: open the replayed control part of `g3-dev-011` with Fit all; confirm the 12 mm bore sits at the origin and the 8 mm at +60 X, matching `verify_shape` measurements.
