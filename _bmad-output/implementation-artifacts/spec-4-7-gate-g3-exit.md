---
title: 'Story 4.7 — Gate G3 Exit'
type: 'feature'
epic: 4
story: '4-7-gate-g3-exit'
created: '2026-09-14'
status: 'in-progress'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/validation-harness-design.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Phase 3 cannot be claimed complete until the sealed held-out split has been run once,
every cited validator has a current fault score, the human spot-audit token is bound to the run, and
the five-leg verdict protocol passes. None of that has happened; `benchmarks/g3/heldout/` has never
been unsealed (`unseal_events: []`).

**Approach:** Run the G3 exit: unseal the held-out split exactly once with the operator key, drive
the full benchmark at R≥10, compute the verdict over stored reports, bind the `spot_audit` token,
and report the outcome honestly — including a failing outcome, which is a legitimate result.

## Boundaries & Constraints

**Always:**
- The exit run is **operator-driven**. It needs the unseal key, a live actor, and a human spot-audit.
  An unattended agent cannot produce a citable G3 verdict and must not claim one.
- The held-out set unseals **exactly once**. The run appends its unseal event to `SEAL.json`. If the
  gate then fails, the set is **burned**: a re-run requires newly authored held-out cases, recorded
  in the manifest. This is the rule that makes "sealed until exit" auditable.
- The verdict is a pure function over stored `ValidationReport`s plus token artifacts. `gate verdict`
  must be re-runnable by anyone, including an auditor, without re-executing cases.
- All five legs must hold: (a) every criterion passes its stated rule evaluated **on report fields**,
  never on exit code or log absence; (b) every cited validator has a current fault run at
  sensitivity ≥95 % and false-alarm ≤5 %; (c) exit legs ran on the sealed set at R≥10 with
  dev/held-out gap ≤15pp; (d) the required human token is present and bound to this run; (e) the
  AD-24 budget is met — median ≤10 min per part.
- The `spot_audit` token covers ≥20 % of passing results, hashes the run's report set, and cannot be
  recycled across runs. Any audit-found false pass invalidates the whole run.
- A failing gate is reported as failing, with the measured numbers. Wilson CI accompanies every rate,
  and a point estimate that clears the bar while its lower CI bound does not is flagged
  low-confidence rather than quietly cited.

**Block If:**
- Stories 4.2–4.6 are not all landed and their validators not all scoring. Running the exit against
  an incomplete implementation burns the held-out set for nothing — that is the single most
  expensive irreversible action in this epic.
- Any cited validator is `not_scored`. Leg (b) fails by definition, so the run cannot produce a
  citable verdict and would waste the unseal.

**Never:**
- Never unseal the held-out set to "check" something, to debug, or to preview. The only legitimate
  unseal is the real exit run.
- Never quote a G3 pass rate computed over the dev split and present it as the gate result.
- Never mark the gate green with a validator at `sensitivity: 0.0` or `not_scored`.
- Never generate the human token programmatically. The runner checks for its presence and binding; it
  never performs the audit.
- Never edit a held-out case after unsealing to make a failing run pass.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| No key | `run G3 --exit`, env unset | Refuses, exits 2, no unseal | Already verified in 4.1 |
| Validator not scored | any cited validator `not_scored` | Leg (b) fails; no citable verdict | Reported, run not green |
| Token absent | no `spot_audit` for this run | Leg (d) fails | Verdict withheld |
| Token recycled | token bound to a different report set | Leg (d) fails on the hash | Rejected, not warned |
| Gap > 15pp | dev 85 %, held-out 65 % | Overfitting; no exit | Reported with both numbers |
| Budget blown | every assertion passes, median 14 min | Gate FAILS on leg (e) | Budget is pass/fail, not advisory |
| Audit finds a false pass | human rejects a passing result | Run invalidated; held-out burned | Recorded in the manifest |

</frozen-after-approval>

## Code Map

- `benchmarks/runner.py:68` -- `_UNSEAL_KEY_ENV`; the only key source, no offline fallback.
- `benchmarks/runner.py:72` -- `_EXIT_REPEATS = 10`, the R≥10 the exit forces.
- `benchmarks/harness/seal.py` -- `unseal_heldout(heldout_dir, *, key, run_id, timestamp, git_sha)`;
  appends the unseal event. Verified working in story 4.1 (7 cases round-trip).
- `benchmarks/harness/seal.py` -- `burn_seal`, the path taken when an exit run fails after unsealing.
- `benchmarks/harness/verdict.py:115-145` -- `check_validator_currency`; leg (b). Note it checks the
  hash and the bars but **not** that the suite contributed cases — a known gap, so confirm each G3
  suite actually scored over real cases rather than trusting a green leg.
- `benchmarks/g3/gate.yaml` -- the seven criteria and their pass rules; `required_tokens:
  [spot_audit]`; `verdict.heldout: sealed`.
- `benchmarks/g3/heldout/SEAL.json` -- `case_count: 7`, `unseal_events: []` as of story 4.1.
- `benchmarks/_registry/validators.yaml` -- `g3_assertions`, `visual_judge`, `corrupted_plan`,
  `verify_recompute` must all carry current measured scores before this story runs.
- `usecases/stats.py` -- Wilson CI and majority-of-R; every rate cited must carry its CI.
- `benchmarks/gate-artifacts/g3/<run-id>/` -- where reports and the human token live.
- `~/.freecad-buddy-g3-unseal.key` -- the key location story 4.1 used (machine-generated; see the
  seal caveat in `benchmarks/g3/README.md`).

## Tasks & Acceptance

**Execution:**
- [ ] Preflight audit -- confirm every cited validator carries a current, measured score and no
      `not_scored` remains. If any does, STOP and report; do not unseal.
- [ ] `benchmarks/runner.py` -- wire the G3 exit path if anything is missing: R≥10 forcing, held-out
      unseal, dev/held-out gap computation, budget leg.
- [ ] `benchmarks/harness/verdict.py` -- ensure the G3 verdict evaluates all five legs and reports
      which leg failed, rather than a bare pass/fail.
- [ ] Exit run -- unseal once, drive the 20 dev + 7 held-out cases at R≥10, write reports under
      `gate-artifacts/g3/<run-id>/`.
- [ ] `gate attest g3 --run <id> --type spot_audit` -- the operator ceremony: the runner pre-selects
      ≥20 % of passing results, the human audits them, the token binds to the report-set hash.
- [ ] `gate verdict g3 --run <id>` -- recompute the verdict from stored reports only, proving it is
      re-runnable by an auditor.
- [ ] `_bmad-output/implementation-artifacts/` -- record the outcome: the measured numbers, every
      Wilson CI, the gap, the budget median, and the verdict per leg. A failing gate is recorded as
      failing.
- [ ] `_bmad-output/implementation-artifacts/sprint-status.yaml` -- set `epic-4` to `done` only if
      the gate actually passed.

**Acceptance Criteria:**
- Given any cited validator at `not_scored`, when preflight runs, then the exit is refused and the
  held-out set is not unsealed.
- Given a completed exit run, when `gate verdict g3 --run <id>` is re-run by a different caller, then
  it produces the identical verdict from stored reports without re-executing any case.
- Given the exit run, when it completes, then `SEAL.json` carries exactly one unseal event naming the
  run id, timestamp and git sha.
- Given a rate cited in the report, when read, then it carries its Wilson CI and the n it was
  computed at, and a point estimate clearing the bar with a lower bound below it is flagged
  low-confidence.
- Given the `spot_audit` token, when the verdict is computed, then the token's
  `binds_reports_sha256` matches this run's report set, and a token from another run is rejected.
- Given a gate failure after unsealing, when recorded, then the held-out set is marked burned and the
  re-run requirement (newly authored cases) is stated.

## Implementation Notes

**Preflight ran and REFUSED the exit. The held-out split was not unsealed** — `SEAL.json` still reads
`unseal_events: []`. Full record: `g3-exit-preflight-2026-09-14.md`.

Three of four cited validators now score **1.000 sensitivity / 0.000 false alarm**: `corrupted_plan`
(8 driveable planted + 4 controls), `g3_assertions` (4 + 3), and `verify_recompute` (10 driveable
planted + 8 controls, authored during this story). Two `verify_recompute` cases were EXCLUDED with
their measurements attached rather than scored as misses — a circular dependency is refused by
FreeCAD before it exists, and removing a bound property plants no fault at all, which surfaced a real
defect in the parameter façade (DW-126).

`visual_judge` remains UNMEASURED and blocks leg (b), for two independent reasons: its 8 fault cases
declare `fixture: pending`, and no vision credential exists on this machine (decision 017). An
unattended agent cannot clear either, so the exit stops here by design rather than by failure.

**What an operator must do** is listed in the preflight record. In short: measure the judge (or
record that G3.7 cannot be claimed), consider re-sealing under a human-held key while
`unseal_events` is still empty, then run the exit ceremony with the spot-audit token.

## Spec Change Log

## Review Triage Log

## Design Notes

**The unseal is the irreversible act of this epic.** Everything else can be re-run freely. Unsealing
against an incomplete implementation spends a resource that can only be replaced by authoring new
held-out cases, and the replacement is strictly weaker because the author has by then seen the dev
set's failures. Hence the preflight audit is a task in its own right and a hard block.

**A failing exit is a real outcome.** The gate exists to be falsifiable. Reporting "G3 failed at leg
(b), two validators unscored" is a successful execution of this story; reporting green over an
unmeasured population is the failure mode every part of this harness was built to prevent.

## Verification

**Commands:**
- `uv run python -m benchmarks.runner faults G3` -- expected: every cited validator measured, no
  `not_scored`, before any unseal
- `uv run python -m benchmarks.runner run G3 --exit --run <id>` -- expected: unseals once, R≥10
- `uv run python -m benchmarks.runner verdict g3 --run <id>` -- expected: same verdict, recomputed
  from stored reports
- `python -c "import json;print(json.load(open('benchmarks/g3/heldout/SEAL.json'))['unseal_events'])"`
  -- expected: exactly one event for this run
- `uv run pytest tests/external -q` -- expected: no regression
