# G2 — Phase 2 Copilot benchmark (entry gate G2.E)

Landed by Story 3.1 **before any mutation tool exists** (AD-19): the machinery is born graded,
so Phase-2 code is measured by assertions authored independently of it.

```
g2/
  gate.yaml            declarative mirror of the phase-gates.md G2 criteria table
  dev/                 40 commands x 8 op types, 5 per type, with geometry assertions
  heldout/             8 held-out commands, one per op type — SEALED at G2 exit (Story 3.8)
  fault-injection/     validates the validators; never counts toward the G2.1 pass rate
    tnp/                 the 5 TNP-provoking scenarios + 3 clean controls
    dressup-drop/        the FeatureDressUp silent edge-drop trap + 2 controls
    coincidental-hash/   the Layer-1 witness-match false negative + 1 control
    rollback-boundary/   the #6031 patterns + 2 controls
    wrong-parameter/     8 wrong-parameter runs + 3 controls
```

## Op types

The eight are enumerated in [decision 013](../../docs/decisions/013-g2-eight-op-types.md):
`sketch`, `pad`, `pocket`, `revolve`, `hole`, `dressup`, `pattern`, `mirror`. Every dev and
held-out case declares one in `op_type`; the loader validates against that closed set.
"40 commands × 8 op types" is asserted by phase-gates.md, epics.md, intent.md and SPEC.md but
enumerated by none of them — decision 013 is the enumeration they refer to.

## Assertions are hand-derived, never captured

Every `expect` value is computed analytically from the target golden model's known geometry, and
each case carries its derivation as a comment (e.g. `pi*3^2*30 = 848.230 mm^3 removed through
the 30 mm Z extent`). Nothing here was read off a verify tool: an assertion captured from the
implementation cannot falsify that implementation (AD-13/AD-19).

The reference models are the G0 golden models, whose volumes are themselves hand-computed in
`benchmarks/g0/golden-models/expected.yaml`. Commands are dimensioned to fit their target model —
a 6 mm hole through the 10 mm width of `box-10-20-30`, not a 12 mm one.

## Assertion vocabulary

Five of the `fn` names come from the closed Phase-3 vocabulary in `verification-design.md` §7.2:
`is_valid_solid`, `count_cylindrical_holes`, `hole_spacing`, `hole_through`, `expect_volume`.

Three do **not** exist in that vocabulary and are a declared G2 extension, not a silent fork:

| `fn` | Why G2 needs it |
| --- | --- |
| `expect_solid_count` | A mutation can sever a body or leave a stray lump; §7.2 has no primitive that counts solids, and volume alone cannot distinguish one solid from two. |
| `expect_sketch_fully_constrained` | G2.5 grades `FullyConstrained` (AD-8), which no §7.2 primitive reads. |
| `expect_sketch_geometry_count` | A sketch command's result is geometry, not a solid, so no shape-measuring primitive applies. |

The reconcile kept all eight names: `benchmarks/harness/assertions.py` implements the five §7.2
primitives plus these three extensions, so no case was renamed and the vocabulary grew by exactly
the three documented above. `test_assertion_fns_are_declared` pins the split, so a fourth name
cannot appear unnoticed, and `test_assertions_grade_every_declared_g2_fn` pins that the grader
covers every one of them.

## Fault suites

Each suite mixes planted defects with clean controls: sensitivity = detected/planted (bar
**≥95 %**), false_alarm = flagged/controls (bar **≤5 %**). 17 planted defects and 11 controls
across the five suites.

The controls are chosen to be *discriminating*, not decorative. `tnp-control-intended-target`
and `dressup-intended-edge-removal` carry the same observable delta as their paired defect and
differ only in whether the change was the mutation's intended target — a guard that flags them
has an unusable false-alarm rate, and one that flags neither them nor the defect scores zero
sensitivity.

Two cases exist specifically to defeat a shallow guard, and say so in `must_not_be_caught_by`:

- `tnp-a-fillet-edge-renumber` and `dressup-silent-edge-drop` keep recompute **clean**, so a
  Layer-0 error sweep sees nothing; only an entry-count comparison detects them.
- `tnp-e-boolean-reorder-repoint` and `coincidental-witness-match` resolve with a **matching
  witness**, so Layer 1 sees nothing; only `getElementHistory` divergence detects them.

## Running it

```sh
uv run python -m benchmarks.runner run G2 --run <run-id>
```

Until Stories 3.3–3.7 land, every criterion fails honestly with `INVALID_INPUT` — there is no
mutation *tool* for an actor to drive, even though the mutation runtime and the grader now exist.
That failure is the entry-gate acceptance signal, not a defect.

The `rollback-boundary/` fixtures are materialized (Story 3.2): each is the pre-mutation input
document, rebuilt by `rollback-boundary/build_rollback_fixtures.py`, and each `case.yaml` names the
op that plants its fault in `planted_op`. The other four suites' fixtures remain `pending` until
the tools that can plant them land.
