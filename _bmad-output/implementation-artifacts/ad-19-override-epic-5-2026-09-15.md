# AD-19 Override: Epic 5 started while G3 is red (2026-09-15)

Epic 5 (Phase 4, gate G4) implementation was started while gate G3 is not green.
This breaks the ordering rule in `_bmad-output/specs/spec-freecad-buddy/SPEC.md:46`:

> A phase may not start until the previous phase's gate is fully green; phase
> implementation may not start until its entry gate lands (AD-19).

The override was requested explicitly by the operator after the rule and the
measured G3 state were presented. It is recorded here so a later reader sees a
deliberate waiver rather than a missed rule.

## State of G3 at the time of the override

`4-7-gate-g3-exit` is `in-progress`. The dev split measures:

```
planted 20  geometry_pass 20  visual_pass 0  converged 0
```

against a G3.1 bar of >=70%. Root cause and the four-step path to a real
measurement are recorded in `g3-visual-leg-blocker-2026-09-15.md`. Step 1 of
that list (expose parameter declaration as an actor-callable tool) is resolved
by commit `a1b7e8b` on `feat/epic-4-gate-g3-exit`. Steps 2 to 4 are open.

`benchmarks/g3/heldout/SEAL.json` reads `unseal_events: []`, `case_count: 7`.
The G3 held-out set is unburned and this override does not touch it.

## Scope of the waiver

The waiver covers the ordering rule only. It does not waive:

- **The G4 entry gate itself.** AD-19's second clause still binds: Phase 4
  implementation may not start until G4.E lands. Story 5.1 IS that entry gate,
  so building 5.1 first is what AD-19 requires, override or not. Stories 5.2
  to 5.5 stay blocked behind a landed 5.1.
- **Measurement discipline.** Wilson 95% CI, majority-of-R, sealed held-out
  sets, validator sensitivity bars, and pass/fail budgets all still apply.
- **The G4 exit criteria.** In particular G4.1 (headless parity, the 20-spec
  Phase 3 benchmark at >=70% through the job API) cannot pass while G3.1
  measures 0/20, because it re-runs the same benchmark. The override lets
  Phase 4 implementation begin; it cannot make G4 exitable.

## Consequence to plan around

Story 5.1 builds a soak and fault harness that must fail honestly against a
**stub** service. A stub is the measurement subject, so 5.1 is meaningful with
G3 red. The dependency on a green G3 bites later, at G4.1, not here.
