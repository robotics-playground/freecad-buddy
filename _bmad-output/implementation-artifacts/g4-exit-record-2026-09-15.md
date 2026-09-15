# G4 Exit Record (2026-09-15)

The Phase 4 exit ceremony was run. **The gate is RED**, and this records exactly which criteria
were measured, what they measured, and which remain blocked.

## Verdict

```
G4.1: FAIL   G4.2: FAIL   G4.3: FAIL   G4.4: PASS   G4.5: PASS
FAILURE leg-a: G4.1 verdict INVALID_INPUT (not OK)
FAILURE leg-a: G4.2 verdict INVALID_INPUT (not OK)
FAILURE leg-a: G4.3 verdict INVALID_INPUT (not OK)
FAILURE leg-d: spot_audit token absent
gate G4: FAIL
```

Leg-b does not appear: all four G4 validators are current at sensitivity 1.000 / false-alarm
0.000. Leg-c is inert — G4 declares `verdict.heldout: inert` because it has no sealed held-out
split, and nothing about this run burned one.

## What passed, on real measurement

**G4.5, robustness soak.** 50 jobs, 43 OK, 5 `WORKER_CRASHED`, 2 `TIMEOUT`. Supervisor RSS growth
2.00% against a 20% bar. Zero hangs, zero silent failures; every failing job carried a closed-set
status with structured detail. Recorded in `benchmarks/g4/soak-results.json`.

**G4.4, agent-to-agent proof.** submit → inspect → revise → accept completed with
`human_inputs: 0` and `auto_approve_off: true`. Recorded in
`benchmarks/g4/agent-cycle-results.json`.

## What is blocked, and by what

All three failing criteria reduce to one root cause, and none of them is a defect in the Phase 4
service.

**G4.1, headless parity.** The criterion requires the 20-SPEC benchmark through the job API. No
spec-to-plan translator exists — `benchmarks/runner.py` names this as what blocks G3.1 too. The
parity run therefore carried the 20 COMMITTED plans instead and measured 20/20 geometry pass,
matching the G3 dev split exactly. That number establishes the job service did not degrade the
loop; it is not the G4.1 criterion, and the collector says so rather than reporting the rate.

**G4.2, revisions.** The revision mechanism and its `diff_scope` checker are implemented and
tested against synthetic diffs. The 15-revision benchmark needs converged parts to revise, and
convergence is 0.

**G4.3, deliverables complete.** Requires the AD-21 visual judge verdict on every job. The judge
drawing refuses to be dimensioned because no part exposes driving parameters on this branch.

The common cause is the G3 visual-leg blocker recorded in
`g3-visual-leg-blocker-2026-09-15.md`. Its step 1 — expose parameter declaration as an
actor-callable tool — is resolved by commit `a1b7e8b` on `feat/epic-4-gate-g3-exit` and is NOT on
this branch. Steps 2 to 4 of that document remain open.

**leg-d, spot_audit.** Deliberately unminted. The token attests a human audited at least 20% of
passing results; `attest_command` stamps `signed_by` from the environment and verifies nothing
about who ran it. An agent minting one would fabricate the audit the leg exists to require.

## What would make G4 green

In order, and none of it is Phase 4 work:

1. Land `parameter_declare` on this branch (cherry-pick `a1b7e8b`).
2. Re-author the 20 dev plans to declare their driving dimensions.
3. Re-measure G3.1 and G3.2; confirm the visual leg passes.
4. Write the spec-to-plan translator, without which G4.1 can never be more than a loop
   measurement.
5. Re-run parity and the 15-revision benchmark.
6. Have an operator run the spot audit and mint the token.

Steps 1 to 3 are Epic 4's. Step 4 is an actor the G3 gate is meant to grade, so authoring it
inside Epic 5 would be grading our own work.

## Held-out set

`benchmarks/g3/heldout/SEAL.json` still reads `unseal_events: []`, `case_count: 7`. Unburned. G4
has no held-out split of its own, and this ceremony created none.
