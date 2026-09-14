# G3 Exit Preflight — 2026-09-14

Story 4.7's first task is a preflight audit that decides whether the exit run may proceed. It ran.
**The exit is REFUSED and the held-out split was not unsealed.**

`benchmarks/g3/heldout/SEAL.json` still reads `unseal_events: []` with `case_count: 7`.

## Why refused

Story 4.7's Block If: *"Any cited validator is `not_scored`. Leg (b) fails by definition, so the run
cannot produce a citable verdict and would waste the unseal."*

Measured with `uv run python -m benchmarks.runner faults G3`:

| Validator | Sensitivity | False alarm | Status |
| --- | --- | --- | --- |
| `corrupted_plan` | **1.000** | **0.000** | scored, 8 planted + 4 controls driven |
| `g3_assertions` | **1.000** | **0.000** | scored, 4 planted + 3 controls driven |
| `verify_recompute` | — | — | **NOT SCORED** — no fault case targets it |
| `visual_judge` | — | — | **NOT SCORED** — pending fixtures, and no credential |

Two of four cited validators are unmeasured, so leg (b) of the five-leg protocol fails by
definition. Unsealing now would spend a resource that can only be replaced by authoring new held-out
cases — and the replacement is strictly weaker, because whoever authors it has by then seen the dev
set's failures.

## Gate state

`run G3` exits 1 with all seven criteria failing. Six report `INVALID_INPUT` (no actor drives them
in an unattended run); **G3.4 now reports `SPEC_FAILED`**, which is progress rather than regression —
it has real corrupted-plan results and fails on the measurement rather than on a missing input.

## What blocks each remaining validator

**`visual_judge`** — two independent blockers, both recorded:
1. No vision-model credential exists on this machine (decision 017). The client reads its key from
   the environment only, by design, so a sensitivity number is an operator run and never a green CI
   job.
2. Its 8 fault cases still declare `fixture: pending`; planting a visual fault needs a part the
   judge can actually be shown.

**`verify_recompute`** — cited by G3.2 and G3.3 but no fault suite exists to measure it over. It has
a registry row with an honest `not_scored` reason rather than a fabricated score. Authoring that
suite is the smallest remaining piece of work before an exit is possible.

## What an operator must do to run the real exit

1. Author a fault suite targeting `verify_recompute`, and score it.
2. Supply a vision credential, drive the `visual_judge` fault suite, and record its measured
   sensitivity — or consciously decide G3.7 cannot be claimed and record that instead.
3. Re-run `faults G3` and confirm no validator reports `not_scored`.
4. Only then `run G3 --exit`, which prompts for `FREECAD_BUDDY_UNSEAL_KEY` and unseals once.
5. `gate attest g3 --run <id> --type spot_audit` — the human audits ≥20 % of passing results.
6. `gate verdict g3 --run <id>` to recompute the verdict from stored reports.

The unseal key for the current seal is at `~/.freecad-buddy-g3-unseal.key` — machine-generated, not
operator-held (recorded in `benchmarks/g3/README.md` as a deliberate downgrade made because the
operator was asleep when the seal was created). An operator who wants the stronger property should
re-seal with their own key before the exit run, which is cheap while `unseal_events` is still empty.

## Verification that the refusal is real, not assumed

```
$ python -c "import json; print(json.load(open('benchmarks/g3/heldout/SEAL.json'))['unseal_events'])"
[]
$ uv run python -m benchmarks.runner run G3 ; echo $?
... 7 criteria FAIL ...
1
```

---

## Update — leg (b) now PASSES

The preflight above refused the exit because two validators were unmeasured. Both are now measured,
and `check_validator_currency` reports **ALL CITED VALIDATORS CURRENT AND AT BAR**.

| Validator | Sensitivity | False alarm | How measured |
| --- | --- | --- | --- |
| `corrupted_plan` | 1.000 | 0.000 | 8 driveable planted + 4 controls, designer loop |
| `g3_assertions` | 1.000 | 0.000 | 4 planted + 3 controls, designer loop |
| `verify_recompute` | 1.000 | 0.000 | 10 driveable planted + 8 controls |
| `verify_shape` | 1.000 | 0.000 | G0 suite, re-scored |
| `verify_sketch` | — | — | G2 `sketch/` suite (authored during this pass) |
| `visual_judge` | 1.000 | 0.000 | **agent grading rendered images**, CI [0.566, 1.000] at n=5 |

### What changed the visual-judge answer

The operator corrected a conflation this preflight had inherited: **grading the 8-case fault suite
never needed a credential.** A vision-capable agent reads the rendered PNGs directly. Decision 017
governs the *in-loop* judge — `usecases/verify_visual.py`, driven headless by the harness with no
agent attached — which genuinely does need a programmatic client. It never governed a one-off
offline grading, and reading it as a blanket ban is what kept the row unscored.

Decision 017 now carries that correction, and `score_g3_validators.py` accepts a graded results
file (`visual_judge.json`) as a first-class outcome source alongside the in-FreeCAD drivers.

### Caveats that travel with the visual-judge number

Both are written onto the registry row itself, not only into the grading record, because a bare
`sensitivity: 1.0` reads as stronger than it is:

- **Low confidence.** Wilson CI [0.566, 1.000] at n=5. At this n one miss gives 0.800 and one
  flagged control 0.333, so the suite falsifies an obviously broken judge but cannot *demonstrate*
  the AD-13 bars. Compare the G1 grader at n=16: CI [0.806, 1.000].
- **Not independent.** The grading agent also drove the designer loop. Bounded — parts authored
  before any judge existed, rubric written before any image was seen — but a clean AD-13
  measurement needs a separate model or a separate context.

### Four defects found by grading, all since fixed

DW-127 (the mirrored-part fixture planted nothing detectable — an L-bracket is achiral and its spec
fixed no hand, making the suite unpassable by construction), DW-128 (the cosmetic control rendered
illegibly), plus two real bugs in shipped `usecases/` code: `techdraw.py` accepted a view only if
its SVG carried `<path>`, rejecting any fully-circular outline; and a render shifted a hollow
sleeve's centre of mass by 0.02 mm, which `query_screenshot`'s read-only guard misread as a mutation.

## The exit is STILL not runnable, for a different reason

Leg (b) is satisfied. **Leg (a) is not**, and this is by design rather than by defect:

```
run G3 -> exit 1; all seven criteria FAIL
  G3.1/2/3/5/6/7: INVALID_INPUT   (no actor drives the loop in an unattended run)
  G3.4:           SPEC_FAILED     (real corrupted-plan results; fails on the measurement)
```

The criteria need a live actor driving the designer loop against the specs, one human plan approval,
and a `spot_audit` token over ≥20 % of passing results. None can be produced unattended.

`benchmarks/g3/heldout/SEAL.json` still reads `unseal_events: []` with `case_count: 7`. The
irreversible action remains unspent.

### Remaining operator steps, unchanged except for step 1

1. ~~Author a `verify_recompute` suite~~ — done. ~~Measure `visual_judge`~~ — done, with caveats above.
2. Consider re-sealing the held-out split under a human-held key (DW-116) while `unseal_events` is
   still empty. Cheap now; impossible to improve after an exit run.
3. Decide DW-122: two dev specs cannot decide a wrong-face or mirrored part. DW-129 records that a
   third spec *was* amended for exactly this reason, so the inconsistency is a live reviewer call.
4. Run the exit with a live actor, then `gate attest` and `gate verdict`.
