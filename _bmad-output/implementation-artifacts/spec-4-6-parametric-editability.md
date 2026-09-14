---
title: 'Story 4.6 — Parametric Editability'
type: 'feature'
epic: 4
story: '4-6-parametric-editability'
created: '2026-09-14'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** G3.2 requires driving dimensions exposed as named parameters and G3.3 requires ≥90 % of
passing parts to survive a parameter change, but no parameter façade exists and **no document
specifies how the editability test selects, applies, or judges a change**. Without it a generated
part is a frozen blob that happens to have the right shape.

**Approach:** Land the driving-parameter façade — a VarSet with a Spreadsheet fallback, selected by
capability probe — so driving dimensions live as named, intent-bearing parameters that sketches and
features reference. Then define and implement the editability test the gate criterion needs: pick one
driving parameter, change it, recompute, and verify the part rebuilds clean.

## Boundaries & Constraints

**Always:**
- The façade is selected by **capability probe**, never by version string (AD-11). VarSet preferred,
  Spreadsheet fallback; the probe result is recorded in the report banner.
- The façade is the single home for the parameter surface. Downstream code reads and writes driving
  dimensions only through it — story 4.3's dimension generator sources its callouts from here, so the
  two must agree on naming before both are relied on.
- Parameter names are **intent-bearing**: `plate_thickness`, not `d1` or `Param003`. A name that
  describes the value's role is the difference between a parametric model and a blob with variables.
- Every sketch in a passing part reaches `FullyConstrained` (AD-8). This is the existing pass signal;
  do not introduce a second one.
- The editability test must be **defined** as well as implemented: which parameter is selected, by
  what rule, what magnitude of change, and what "recomputes clean" means. Record the definition where
  the gate reader will find it, because no planning document states it.
- A parameter change that produces a valid but wrong part is a failure, not a pass. "Recompute
  without errors" means the resulting shape is still a valid solid and the changed dimension actually
  changed — verify both, since a parameter silently ignored also recomputes cleanly.
- Every mutation goes through `run_mutation()`; the returned document is rebound (DW-71).

**Block If:**
- The capability probe cannot distinguish VarSet availability on both CI legs. A façade that silently
  differs between FreeCAD 1.1.0 (H1) and 1.1.1 (GUI) would make the editability rate
  environment-dependent, which no gate number could be read from.

**Never:**
- Never expose a driving dimension as a raw feature property while also exposing it through the
  façade — one owner, or the two drift.
- Never count a part as editable because the recompute returned without raising. Prove the dimension
  moved.
- Never rename or restructure existing Phase 2 feature parameters to fit the façade.
- Do not implement the gate exit run (4.7).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| VarSet available | FreeCAD exposing VarSet | Façade uses VarSet; probe result recorded | N/A |
| VarSet absent | older leg | Falls back to Spreadsheet with identical surface | Fallback recorded, never silent |
| Parameter change | thickness 6 mm → 8 mm | Recomputes clean; measured thickness is 8 mm | Both checks required |
| Ignored parameter | change applied but geometry unchanged | FAILURE — the parameter is not driving anything | Reported as non-editable |
| Change breaks the part | new value makes the solid invalid | FAILURE, recorded with the failing value | Not counted as editable |
| Unconstrained sketch | a sketch is not `FullyConstrained` | Part fails artifact hygiene (G3.2) | Existing signal, unchanged |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/shim.py` -- where the VarSet/Spreadsheet capability probe belongs
  (AD-11 probe pattern; never version sniffing). **A probe already ships and works**: the live
  `query_capabilities` tool reports `varset_backend: "varset"` on the GUI leg (FreeCAD 1.1.1), and
  `doc.addObject("App::VarSet", ...)` succeeds on the H1 leg (FreeCAD 1.1.0) — both measured
  2026-09-14. So VarSet is the path on **both** legs and the Spreadsheet fallback is currently
  unexercised; write it anyway, but know that no available environment tests it, and say so rather
  than implying it was verified.
- `src/freecad_buddy/usecases/transaction.py` -- `run_mutation()`; the parameter write path goes
  through it like every other mutation.
- `src/freecad_buddy/usecases/verify.py:485` -- `verify_recompute`, the validator G3.2/G3.3 cite.
  Story 4.1 left it cited in `benchmarks/g3/gate.yaml` — confirm it has a registry row by the time
  this story claims the criteria.
- `benchmarks/harness/assertions.py` -- `expect_sketch_fully_constrained` already exists as a
  declared G2 extension; reuse it for the hygiene leg rather than writing a second check.
- `benchmarks/g3/gate.yaml:61-68` -- G3.2 and G3.3, the criteria this story serves, with their
  pass rules.
- `src/freecad_buddy/usecases/techdraw.py` (story 4.3) -- sources dimension callouts from the
  parameter names this story defines. Agree on naming before both land.
- `docs/decisions/` -- where the editability-test definition belongs, in the format of
  `013-g2-eight-op-types.md` (a decision note that supplies an enumeration the specs refer to but
  never state).

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/shim.py` -- VarSet capability probe with Spreadsheet fallback
      detection, result exposed for the report banner.
- [x] `src/freecad_buddy/usecases/parameters.py` -- the façade: create, read, write and list driving
      parameters with intent-bearing names, backed by VarSet or Spreadsheet behind one surface.
- [x] `docs/decisions/018-editability-test-definition.md` -- define the G3.3 test: selection rule,
      change magnitude, and the two-part pass condition (recomputes clean AND the dimension moved).
      No planning document states this; the note is the enumeration the gate refers to.
- [x] `benchmarks/harness/editability.py` -- the editability runner implementing that definition
      over passing parts, wired into `runner.py` as the G3.3 collector.
- [x] `tests/infc/test_parameters.py` -- façade round-trip on both backends, an ignored-parameter
      case that must FAIL, and a change-breaks-the-part case that must FAIL.
- [x] `tests/infc/test_parameters.py` -- a test that the probe result is recorded, so a silent
      backend switch between legs is visible rather than invisible.
- [x] `benchmarks/_registry/validators.yaml` -- `verify_recompute` carries a row with an honest
      `not_scored` reason; the hash was re-measured after this story touched `verify.py`.

**Acceptance Criteria:**
- Given a passing part, when inspected, then every driving dimension is reachable through the façade
  under an intent-bearing name, and every sketch reports `FullyConstrained`.
- Given a driving parameter changed by the defined magnitude, when the document recomputes, then the
  part is a valid solid **and** the measured dimension reflects the new value.
- Given a parameter the model ignores, when changed, then the part is reported non-editable rather
  than passing on a clean recompute.
- Given both CI legs, when the probe runs, then the selected backend is recorded in the report, and
  the same part yields the same editability verdict on both.
- Given the full suites, when run, then the in-FreeCAD and external baselines do not regress.

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

**The ignored-parameter case is the one that matters.** A parameter written into a VarSet that no
sketch references will recompute perfectly cleanly forever, and a test that only checks "no errors"
would score it as editable. Proving the dimension actually moved is the only way the ≥90 % number
means what the gate says it means.

**Why the test needs a decision note.** G3.3 states a threshold and names the façade as its enabler,
but no document says how the parameter is chosen or what counts as clean. Left undefined, the number
would be whatever the implementation happened to measure — so the definition is written down first
and cited by the gate.

## Verification

**Commands:**
- `python tests/run_tests.py` (H1 `fcb` env) -- expected: façade and editability tests pass
- `uv run pytest tests/external -q` -- expected: no regression
- `uv run python -m benchmarks.runner run G3` -- expected: G3.2/G3.3 collect real results
- `python scripts/check_imports.py` -- expected: exit 0
- `uv run ruff check src/ tests/ benchmarks/` -- expected: clean for touched files
