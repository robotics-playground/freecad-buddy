---
title: 'Story 4.5 — Designer Loop'
type: 'feature'
epic: 4
story: '4-5-designer-loop'
created: '2026-09-14'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/validation-harness-design.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The 20 G3 specs have no driver. There is no code that takes a written spec, plans, runs
the Phase 2 mutation tools, measures the result, and repairs it — so G3.1, G3.4 and G3.5 have nothing
to measure, and all 29 G3 fault cases sit at `fixture: pending` because planting a fault requires
driving a plan through a loop that does not exist.

**Approach:** Land `usecases/designer_loop.py`: plan → execute over the existing Phase 2 tools →
measure with the assertion vocabulary → read the discrepancy vector plus judge findings → repair,
capped at 3 self-repairs. Convergence is declared **only** by geometry ∧ visual passing, never by
reaching the cap. One human plan approval at the start; nothing after it is supervised.

## Boundaries & Constraints

**Always:**
- Convergence is `geometry_pass AND visual_pass`. Hitting the repair cap is a **failure**, reported
  as such. A loop that returns "done" because it ran out of iterations is the exact defect G3.4
  exists to catch.
- Every mutation goes through the existing Phase 2 tool surface and `run_mutation()`. The loop opens
  no transaction itself and writes no geometry directly.
- `run_mutation` returns `(document, envelope)` and the returned document **must** be rebound into
  the registry — the snapshot-restore path closes and reopens the document (DW-71). Every call site,
  without exception.
- Repair input is the **discrepancy vector** (measured vs expected per failing assertion) plus the
  judge's findings. Not a raw error string, and never the plan text alone.
- Assertions measure the produced artifact, never the plan. A loop that detects a corrupted plan by
  reading the plan would pass the fault suite while catching no real deviant part.
- Every run carries a `run_id` threaded through every envelope, audit record and report, and writes
  the plan, each iteration's discrepancy vector, the judge verdicts and the repair decisions to the
  session workdir. A failed run must be reconstructable from its workdir alone.
- Wall-clock is measured on the AD-24 basis: tool-call entry to envelope return, model time included,
  spanning all repair iterations including judge and drawing generation.
- The 29 pending fault fixtures become drivable when this lands. Each `planted_op` must resolve to a
  real callable — the G2 history (DW-73) is that unresolved `planted_op` names left a whole suite
  unscoreable for months.

**Block If:**
- Stories 4.2 (assertion primitives) and 4.4 (visual judge) are not both landed. The loop's
  convergence test is `geometry ∧ visual`; without either half it cannot declare convergence honestly
  and must not be given a weakened test to compensate.

**Never:**
- Never declare convergence on the iteration cap, on a clean recompute alone, or on tool success.
- Never grade the loop with assertions the loop itself produced.
- Never exceed 3 self-repairs; the cap is a gate criterion, not a tuning knob.
- Never call the judge on an iteration whose geometry assertions failed.
- Never use `ActiveDocument`; every call takes an explicit handle.
- Do not implement the parameter façade (4.6) or the gate exit run (4.7).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Converges first try | spec whose plan is correct | geometry ∧ visual pass; 0 repairs; run artifacts written | N/A |
| Converges after repair | first attempt misses one dimension | discrepancy vector drives repair; converges within ≤3 | N/A |
| Hits the cap | part never satisfies the spec | reported as FAILURE, never done | Explicit non-convergence status |
| Corrupted plan | plan contradicts the spec | detected by measuring the artifact | Reported as a spec violation |
| Judge unavailable | no vision backend | not done, regardless of geometry | `visual.unavailable` |
| Mutation rolls back | a tool fails post-verify | document rebound; loop sees the failure | No stale handle |
| Budget exceeded | run passes 10 min median | recorded; the gate judges it, the loop does not hide it | Timing always reported |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/transaction.py` -- `run_mutation()`, the only mutation path. Returns
  `(document, envelope)`; rebinding the returned document is mandatory (DW-71).
- `src/freecad_buddy/usecases/sketches.py`, `features.py` -- the Phase 2 tool surface the loop drives.
- `benchmarks/harness/assertions.py` -- `evaluate(document, checks)` returns one `Check` per entry;
  this is the discrepancy vector's source. Story 4.2 completes the vocabulary it supports.
- `benchmarks/g3/dev/*/case.yaml` -- the 20 specs, each with `spec` text plus compiled `assertions`.
  The loop consumes the spec text; the harness grades with the assertions.
- `benchmarks/g3/fault-injection/corrupted-plan/` -- 14 cases, all `fixture: pending`, each naming a
  `corruption_class`, a `spec_ref` and the `detected_by` assertion. These become drivable here.
- `benchmarks/g3/judge.py` + `usecases/verify_visual.py` (4.4) -- the visual half of convergence.
- `benchmarks/g2/case_run.py` -- the existing per-case driver (preview → confirm → apply → undo →
  grade) proven under FreeCAD 1.1.1. The closest working precedent; read it before designing.
- `src/freecad_buddy/usecases/documents.py:36-56` -- `workdir_root()`/`temp_dir()`; run artifacts go
  under the session workdir.
- `src/freecad_buddy/adapters/audit_log.py` -- where run records land.
- `benchmarks/runner.py:134` -- `_VALIDATOR_SOURCES["corrupted_plan"]` already points at
  `usecases/designer_loop.py`, the module this story creates. Its registry row currently carries an
  empty `validator_sha` because the file does not exist.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/designer_loop.py` -- the loop: plan, execute, measure, repair,
      capped at 3, with convergence defined as geometry ∧ visual.
- [x] `src/freecad_buddy/usecases/designer_loop.py` -- discrepancy-vector assembly from the
      assertion results, shaped as repair input rather than as a report.
- [x] `src/freecad_buddy/usecases/designer_loop.py` -- run artifact writing: plan, per-iteration
      vectors, judge verdicts, repair decisions, timing, all under the session workdir keyed by
      `run_id`.
- [x] `benchmarks/g3/fault-injection/**` -- resolve every `planted_op` to a real callable and
      replace `fixture: pending` where the loop can now plant the fault. Report honestly on any that
      remain and why.
- [x] `benchmarks/g3/fault-injection/score_g3_validators.py` -- score `corrupted_plan` over the now
      drivable cases; keep the `not_scored` path for anything still unreachable.
- [x] `benchmarks/_registry/validators.yaml` -- record the measured `corrupted_plan` sensitivity and
      its real `validator_sha`.
- [x] `tests/infc/test_designer_loop.py` -- convergence-by-verdict test, cap-is-failure test,
      document-rebind test, and a corrupted-plan detection test that proves detection came from
      measuring the artifact.
- [x] `tests/external/` -- deterministic tests for the loop's control flow against a scripted
      backend, so the logic is provable without a live model.

**Acceptance Criteria:**
- Given a spec whose part cannot satisfy the assertions, when the loop exhausts 3 repairs, then it
  reports failure and never reports done.
- Given a converging spec, when the loop finishes, then convergence was declared by geometry ∧ visual
  both passing, provable from the run artifacts.
- Given a corrupted-plan case, when driven, then the violation is detected by an assertion over the
  produced artifact, and the run records which assertion caught it.
- Given any run, when it fails, then the workdir alone is sufficient to reconstruct what happened —
  plan, every discrepancy vector, every judge verdict, every repair decision.
- Given a mutation that takes the snapshot-restore path, when the loop continues, then it holds the
  rebound document and not a closed handle.
- Given `faults G3`, when run after this story, then `corrupted_plan` reports a measured sensitivity
  or an honest `not_scored` reason naming exactly what is still unreachable.

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

**Convergence is the verdict, never the count.** This is the single most important property in the
story. A loop that returns success because it ran out of repairs produces a silently bad part, which
is precisely the failure G3.4's ≥9/10 catch rate and "zero silent bad parts" rule exist to prevent.

**Why the fault fixtures are pending until now.** A planted fault must be produced by the real
mutation path — a defect hand-carved into a shape validates nothing, because no production code path
created it. That is why all 29 G3 fault cases declare `fixture: pending` and why resolving the
`planted_op` callables belongs to this story and not to 4.1.

## Verification

**Commands:**
- `python tests/run_tests.py` (H1 `fcb` env) -- expected: new loop tests pass, no regression
- `uv run pytest tests/external -q` -- expected: no regression
- `uv run python -m benchmarks.runner faults G3` -- expected: `corrupted_plan` measured or honestly
  `not_scored`
- `uv run python -m benchmarks.runner run G3` -- expected: criteria that depend on the loop now
  collect real results instead of reporting a missing actor
- `python scripts/check_imports.py` -- expected: exit 0
