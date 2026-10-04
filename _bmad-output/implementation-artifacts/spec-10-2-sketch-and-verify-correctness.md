---
title: 'Story 10.2: Sketch and Verify Correctness'
type: 'bugfix'
created: '2026-10-04'
status: 'done'
route: 'dispatch'
baseline_commit: '2e03c1bec05b52cbc793f2d8a3048c09b55c5d1f'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-10-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Sketch tools refuse inputs FreeCAD accepts, and `verify_*` verdicts disagree with what FreeCAD measures (UAT run `2026-10-03-04`, findings F-04, F-05, F-06, F-17, F-19, F-22, F-23). A point cannot be added with `start`. A single-point `DistanceX`/`DistanceY` is refused. The same constraint set passes or fails `verify_sketch` depending on insertion order. A sketch opened from a file reports `dof=0` when it is under-constrained. `verify_recompute` and mutation post-verify disagree on a redundant sketch. `verify_shape` crashes on a nested `fn` and grades the first object for `object: ""`.

**Approach:** Fix each at its root cause in `usecases/sketches.py`, `usecases/verify.py` and `usecases/transaction.py`, each with a regression test that fails on HEAD.

**Decisions (2026-10-04, user):**
- **D1 — F-06 (amended in review 1).** FreeCAD 1.1 treats full redundancy as an execution error: `SketchObject::execute` returns "Sketch with redundant constraints" and skips `buildShape()` (`SketchObject.cpp:301-304`), and `solve()` writes the solved geometry and `FullyConstrained` only when it returns 0 (`:611-623`). So a sketch passes only when `solve()` returns 0, `FullyConstrained` is true, `dof == 0`, and no conflicting, malformed, redundant or degenerate condition holds. Full redundancy is a HARD FAIL in both insertion orders. Partial redundancy stays a WARN, because FreeCAD only logs it (`:602-606`). The reported `fully_constrained` field is the flag only when `solve()` returned 0, else `false`. AD-8, `verification-design.md` §4.1-§4.2 and Story 10.2 AC3 are corrected to say this.
- **D2 — F-19 (amended in review 1).** A sketch FreeCAD marks in error, redundancy included, is a recompute error everywhere: `verify_recompute` reports it, and post-verify step 1 no longer defers a redundant-only sketch, so a mutation that makes a sketch redundant returns `RECOMPUTE_ERROR` with `recompute_clean: false` and rolls back. Story 10.2 AC5 keeps its original wording.
- **D3 — F-04.** A point takes its position from `start` or `center`; both present is `INVALID_INPUT`.
- **D4 — F-17.** `read_sketch` calls the sketch's `solve()` after `recompute()` and before reading `DoF` and the diagnostics, as FreeCAD does when no recompute runs.

## Boundaries & Constraints

**Always:**
- Input faults return `INVALID_INPUT` with the closed-vocabulary message (AD-17).
- Full redundancy fails like FreeCAD's own execute; partial redundancy only warns (D1).
- Every fix has a regression test that fails on the current code.

**Never:**
- No `autoRemoveRedundants()` inside any verify or mutation path.
- No change to UAT test-case files (Story 10.7).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Point by `start` | `{kind:"point", start:[10,30]}` | `OK`; a `Part::GeomPoint` at (10,30) | — |
| Single-point DistanceX/Y | `{type:"DistanceX", first:1, first_pos:3, value:20 mm}` | `OK`; constraint `('DistanceX', 1, 3, 20)` | `first_pos` without `second` on any other type stays `INVALID_INPUT` |
| Order-independent verdict | same 15-constraint set incl. one redundant, two insertion orders | `SPEC_FAILED` in both orders, the redundant constraint named in the failure detail | — |
| Opened under-constrained sketch | file sketch, true DoF 4 | `SPEC_FAILED`, message and subject show `dof=4` | — |
| Both point fields | `{kind:"point", start:[1,1], center:[1,1]}` | `INVALID_INPUT` naming both fields | — |
| Redundant sketch in `verify_recompute` | duplicate Horizontal | `RECOMPUTE_ERROR` naming the sketch | — |
| Mutation making a sketch redundant | `sketch_add_constraint` duplicate Horizontal | `RECOMPUTE_ERROR`, `recompute_clean:false`, rolled back | — |
| Nested `fn` | `checks:[{fn:{a:{…}}}]` | `INVALID_INPUT` "unknown assertion fn: …" | — |
| Empty object | `verify_shape {object:""}` | `INVALID_INPUT` "missing required 'object' name" | — |

</frozen-after-approval>

## Code Map

- `usecases/sketches.py:203-204` -- point reads `center` only (F-04, D3).
- `usecases/sketches.py:441-445` -- `first_pos` without `second` refused for every type (F-05). FreeCAD `ConstraintPyImp.cpp:346-356` reads `(type, geo, pos, value)` as single-point for `DistanceX`/`DistanceY` only.
- `usecases/verify.py:331-354` (`read_sketch`) -- `DoF` read after `recompute()` only. FreeCAD `DoF` returns `lastDoF` (`SketchObjectPyImp.cpp:2644`), 0 until a solve; an untouched sketch from a file is not re-executed by `recompute()`. Call `obj.solve()` before reading, as FreeCAD itself does when no recompute runs (F-17). Pass rule per D1 (F-06), solve per D4 (F-17).
- `usecases/verify.py:401-420` (`verify_recompute`) and `transaction.py:155-172` (`_invalid_objects`) -- per D2 (F-19). Reuse `shim.redundant_only_sketch` (`shim.py:256`).
- `usecases/verify.py:238` -- `if object:` treats `""` as omitted (F-23); test `is not None` so `_resolve_object` (`:100-103`) refuses it.
- `usecases/verify.py:248-252` -- `fn not in ASSERTION_FNS` on a dict raises `TypeError` (F-22); refuse a non-string `fn` with the same message first.
- `verification-design.md` §4.2 and `epics.md` Story 10.2 AC5 -- corrected per D1, D2.
- Tests: `tests/infc/test_sketch_tools.py`, `tests/infc/test_verify_tools.py`.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/sketches.py` -- point field, single-point DistanceX/Y -- F-04, F-05.
- [x] `src/freecad_buddy/usecases/verify.py` -- solve before DoF, pass rule, `object`/`fn` guards, recompute deferral -- F-06, F-17, F-19, F-22, F-23.
- [x] `src/freecad_buddy/usecases/transaction.py` -- only if D2 needs it.
- [x] `tests/infc/test_sketch_tools.py`, `tests/infc/test_verify_tools.py` -- one test per I/O row.
- [x] `verification-design.md` §4.2, `epics.md` Story 10.2 AC5 -- per D1, D2.
- [x] Re-score every validator whose sources change (`benchmarks/runner.py:96-128`): `verify.py` feeds `verify_shape` (G0), `verify_sketch` (G2) and `spec_assertions` (G3); `transaction.py` feeds `run_mutation` (G2). Use the in-FreeCAD scorers the registry names.

**Acceptance Criteria:**
- Given each I/O row, when its regression test runs on FreeCAD 1.1.3, then it passes, and it fails on the baseline commit.
- Given the full suites, when run, then in-FreeCAD and external tests pass, ruff, `check_imports`, `gen_schemas --check` and `check_provenance` pass, and every validator score is current.

## Implementation Notes

## Spec Change Log

- **Review 1 (intent gap, resolved by user: follow FreeCAD).** Trigger: review found that FreeCAD 1.1 treats full redundancy as an execution error (`SketchObject.cpp:301-304`, `:611-623`), so D1/D2's "redundancy only warns" passed and hid sketches with no rebuilt shape and unsolved geometry; the raw `fully_constrained` field stayed order-dependent in every report and grader. Amended: D1, D2, the redundancy boundary, two matrix rows, one new row. Known-bad state avoided: a committed redundant sketch with a stale shape; `verify_recompute` reporting `OK` for a sketch FreeCAD marks in error. KEEP: F-04 point field, F-05 single-point DistanceX/Y, F-17 `solve()` before reading `DoF`, F-22 non-string `fn`, F-23 `object: ""`, and their tests.

## Review Triage Log

| # | Source | Finding | Verdict | Route / evidence |
|---|--------|---------|---------|------------------|
| 1 | blind, edge, gap, impl | Redundancy policy: FreeCAD fails execute on full redundancy; D1/D2 waived it, stale `fully_constrained` in post_verify, sketch_state, G2.5, harness assertion | high | intent_gap; resolved by user into D1/D2 (follow FreeCAD). |
| 2 | blind, edge, gap | `solve()` return discarded; a non-converged solve (-1) can pass | high | patch under D1: pass requires `solve() == 0`. |
| 3 | blind, edge | Partial redundancy waived the flag though FreeCAD updates it | medium | patch under D1: partial redundancy is WARN, flag still required. |
| 4 | blind, impl | AD-8 in `ARCHITECTURE-SPINE.md:101`, `mcp-tools-design.md:351`, `transaction.py:215-216` docstring, `skills/freecad-sketcher/SKILL.md` state the old rule | medium | patch (docs) per D1. |
| 5 | impl | `document_recompute`/`document_undo` report a redundant sketch as error while `verify_recompute` did not | medium | resolved by D2: all report it. |
| 6 | impl | A redundant untouched sketch blocks later mutations | false | Intended under D2: FreeCAD marks it in error. |
| 7 | edge | `DistanceX` with `second_pos` and no `second` silently builds the single-point form | medium | patch: refuse naming `second`. |
| 8 | blind | Single-point DistanceX/Y and point `start` not in `tool_catalog.py` / `mcp-tools-design.md` §3.6 | low | patch: one line each. |
| 9 | blind | §4.2 HARD FAIL row restates `evaluateConstraints()` inverted (it returns true when valid) | low | patch: drop the clause from the row the diff edited; code untouched. |
| 10 | blind, edge, gap | `solve()` can write geometry; §4 says read-only, no test | medium | patch: §4 states the write (only when `solve()` returns 0 and geometry differs, no transaction); test that a solved sketch keeps `UndoCount` and geometry. |
| 11 | blind | Order test does not assert its stale-flag premise | low | moot under D1: test now asserts `SPEC_FAILED` both orders. |
| 12 | blind | No G2 fault case targets `verify_sketch` | low | defer: pre-existing gap. |
| 13 | blind | Spec and context files missing from the review diff | false | Spec is the claims file, given to the edge-case layer by design. |
| 14 | edge | Stale `RedundantConstraints` could hide a non-solver error in `verify_recompute` | false | D2 removes the deferral; every error state is reported. |
| 15 | impl | GUI 1.1.4 modified flag after `solve()` not checked | maybe-false | defer to UAT: run `verify_sketch` in the GUI and check the title `*`. |
| 16 | r2 blind, edge | Live text still says redundancy only warns: `sketches.py:921`, `tool_catalog.py:454`, `shim.py:259`, `test_verify_tools.py:6`, `data-contracts-design.md:131`, `epics.md:392` (Story 1.6 AC), `benchmarks/g2/gate.yaml:68` + `phase-gates.md` G2.5 | medium | patch (text) per D1. |
| 17 | r2 blind, edge, gap | `tnp_guard.py:383` still exempts redundant-only sketches; `shim.redundant_only_sketch` then unused | medium | patch per D2: remove the exemption, delete the helper and its tests, re-score `audit_references`. |
| 18 | r2 blind, edge, gap | `solver_status_code` in §4.1 and `mcp-tools-design.md` §3.4 but not emitted | low | patch: emit it in the `read_sketch` subject. |
| 19 | r2 blind, edge | `mcp-tools-design.md` §3.6 says conflicting/malformed give `SPEC_FAILED`; post-verify step 1 returns `RECOMPUTE_ERROR` | low | patch (doc). |
| 20 | r2 blind | §4.2 dropped `evaluateConstraints()`; code still reports `evaluate_bad` | low | patch (doc): state it is a reported diagnostic, true only with malformed present. |
| 21 | r2 blind, edge | Harness `expect_sketch_fully_constrained` uses `FullyConstrained and isValid()`, not the §4.2 rule | medium | patch: grade with `read_sketch` so grader and verifier share one rule (AD-8). |
| 22 | r2 gap | No test for the `sketch.partially_redundant` warning path (id, `measured` list, verdict OK) | medium | patch: stub-sketch test. |
| 23 | r2 gap | `; solve() returned N` detail not asserted | low | patch: one assertion. |
| 24 | r2 blind, edge | Point with neither field names only `center` | low | patch: message names both. |
| 25 | r2 blind, edge | Single-point DistanceX/Y accepts `first_pos: 0` | low | patch: require 1-3. |
| 26 | r2 blind, edge | Undo test cannot fail; no check that `verify_sketch` leaves a file-opened sketch untouched | low | patch: assert `Geometry` unchanged and no `Touched` state on the reopened sketch. |
| 27 | r2 blind | `second_pos`/`center` schema descriptions missing in `tool_catalog.py` | low | patch. |
| 28 | r2 blind | History-style comments (`transaction.py` `_invalid_objects` docstring, a test comment) | low | patch: describe current behaviour. |
| 29 | r2 blind | "FreeCAD itself solves when no recompute runs" uncited | low | patch: cite `SketchObject.cpp:922`. |
| 30 | r2 blind | Citations carry no FreeCAD version | false | `docs/references/FreeCAD` is pinned to tag 1.1.4; repo convention. |
| 31 | r2 blind | No G2 fault case for `verify_sketch` | low | carried from #12: deferred. |
| 32 | r2 blind | TC-03-12 and TC-07 (`:120`) still expect redundancy to warn | low | defer to Story 10.7. |
| 33 | r2 blind | `third`/`third_pos` without `second` not checked | low | rejected: pre-existing, no reported failure. |
| 34 | r2 blind | Spec Code Map still names `redundant_only_sketch` reuse | false | fix would edit this build's spec. |
| 35 | r2 blind | `spec-1-6` example shows old warning shape | false | historical record. |

## Verification

**Commands:**
- `micromamba run -n fcb freecadcmd tests/run_tests.py` (FreeCAD 1.1.3) -- expected: OK.
- `uv run pytest tests/external` -- expected: all pass.
- `uv run ruff check .`, `uv run python scripts/check_imports.py`, `uv run python scripts/gen_schemas.py --check`, `uv run python scripts/check_provenance.py` -- expected: pass.
