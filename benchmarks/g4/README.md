# G4 — Autonomous Design Service (Phase 4)

The entry gate for Phase 4, landed by story 5.1 before any service exists.

## Every criterion fails today, on purpose

There is no job service: no supervisor, no worker pool, no sandbox, no job API (stories 5.2-5.4).
So `runner.py run G4` reports `INVALID_INPUT` for all five criteria and the verdict is red.

That failure IS the acceptance signal (AD-19). An entry gate exists so the measuring machinery is
born before the thing it measures and cannot be tuned to it. A green G4 today would mean the
criteria are measuring nothing.

## Layout

```
benchmarks/g4/
  gate.yaml                 declarative mirror of the G4 exit table (phase-gates.md:99-105)
  stub_service.py           the job-service seam: status vocabulary + JobStatus shape rules
  THREATS.md                threat list, counters, and what this suite does NOT measure
  REUSE-SURVEY.md           what is reused from the existing harness and what is new
  fault-injection/
    drive_g4_faults.py      resolves every case against the stub, writes <validator>.json
    score_g4_validators.py  computes the bars, merge-writes the G4 registry rows
    timeout/                planted infinite loop      -> TIMEOUT          + control
    oom/                    unbounded allocation       -> OOM_KILLED       + control
    crash/                  OCCT segfault              -> WORKER_CRASHED   + control
    wrong-part/             wrong part, clean report   -> SPEC_FAILED      + control
    revision-diff/          unrelated feature changed  -> flagged          + control
    lifecycle/              terminal failure, no detail-> refused          + control
```

Fault suites live BESIDE the dev/held-out split, never inside it
(validation-harness-design.md §1): they validate validators and never count toward the G4.1 pass
rate.

## Validators

| Name | Grades | Cited by |
| --- | --- | --- |
| `soak_status` | Runtime faults map to the right terminal status | G4.5 |
| `supervisor_recheck` | A wrong part with a clean report is caught by re-execution | G4.3 |
| `revision_diff` | An out-of-scope geometry change is flagged | G4.2 |
| `job_lifecycle` | A terminal result carries a well-formed, non-silent status | G4.1, G4.4, G4.5 |

All four hash `stub_service.py` today. When the real modules land they join each source set, the
digests change, and these rows stale — which is correct: a bar measured over a stub must not
survive the service that replaces it.

## Running it

```bash
uv run python benchmarks/g4/fault-injection/drive_g4_faults.py   # drive cases -> results files
uv run python benchmarks/runner.py faults G4                     # score + write registry rows
uv run python benchmarks/runner.py run G4 --run <id>             # every criterion fails honestly
uv run python benchmarks/runner.py verdict G4 --run <id>         # red, as it should be
```

Add `--check` to either script to verify structure without writing.

## What a green G4.E means, and what it does not

The suite catches every planted fault and flags no control, so it can separate a defect from a
clean run against a mapping authored before any service existed. That is the entry-gate property.

It is not a service measurement. `THREATS.md` records the limits in full; the load-bearing one is
that the `oom/` leg asserts the status mapping only — proving the kill came from the sandbox rather
than the host OOM killer needs story 5.3's real jail.
