# 015 — G2.6 Fails Honestly at the G2 Exit: The Ablation Harness Is Epic-6 Infrastructure

## Decision

Criterion **G2.6** ("Skills + ablation harness: shape-check 6 newly drafted skills; run ablation
with declared subsets", pass rule "Harness reports per-skill paired deltas in AD-14 format")
**fails at the Gate G2 exit** with an explicit `not_collected` report naming its missing
dependency. It is not synthesized, not approximated, and not dropped from `gate.yaml`.

The report reads:

> no ablation harness: the ablation runner and paired-delta reporting are Epic-6 shared
> infrastructure (Epic 6 is backlog)

G2.6 stays in `benchmarks/g2/gate.yaml` as a declared criterion, so the gate verdict counts it as
a failure rather than silently exiting on five of six criteria.

## Rationale

Three independent facts make G2.6 unbuildable inside Epic 3:

1. **The ablation harness is assigned elsewhere.** `epic-3-context.md` states it directly under
   Cross-Story Dependencies: "the ablation harness itself is shared infrastructure, **not Epic 3
   code**." Building it here would take on another epic's deliverable.

2. **That epic has not started.** Every Epic-6 story is `backlog`. No ablation runner exists, and
   neither does the McNemar paired-significance test the AD-14 format requires — `usecases/stats.py`
   holds `wilson_ci`, `sensitivity` and `false_alarm`, and nothing else.

3. **The population is undefined.** The criterion grades "the 6 **newly drafted** skills", but
   nothing in `skills/` marks which of its directories are newly drafted for this phase. There is
   no marker, no manifest, and no field to read. Even with a harness, the subset to ablate could
   not be resolved without a human declaring it.

## Why an honest failure and not a removal

A criterion that cannot be met has two dishonest resolutions and one honest one.

Removing G2.6 from `gate.yaml` would make the gate report PASS over a criterion nobody measured —
the exact vacuous-green the verdict discipline exists to prevent (AD-13: a criterion that cannot
be evaluated fails; it never disappears). Synthesizing a paired-delta number without an ablation
run would be worse: it would put a fabricated measurement into the evidence record.

Reporting `not_collected` with the blocking dependency named keeps the failure visible, keeps its
reason on record, and makes the criterion re-runnable the moment the harness lands. The gate
exits red on G2.6 until Epic 6 delivers, which is the accurate state.

## Consequences

- `run G2` writes a failing G2.6 report on every run; the G2 gate verdict cannot be green while
  that is true.
- No ablation code, no McNemar implementation, and no `skills/` marker are added by Story 3.8.
- When Epic 6 lands the shared ablation harness, G2.6 needs a collector and a declaration of which
  six skills are in the ablated subset. Nothing else about the gate changes.

## Related

- Decision 010 / 011 — the same posture for the live pass-rate numbers: ship the machinery, let
  the unattended run fail honestly, and leave the measured number to the operator ceremony.
