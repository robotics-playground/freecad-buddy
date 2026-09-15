# G4 Threat List

The threats Phase 4 introduces, the counter for each, and the criterion or fault leg that measures
the counter. A threat with no measuring leg is an unmeasured claim, so every row names one.

Phase 4 changes the trust model. Earlier phases relied on an operator confirming each mutation;
a headless job API removes that control and accepts fully untrusted input from another agent.
Everything below follows from that.

## Threats and counters

| Threat | Counter | Measured by |
| --- | --- | --- |
| HTTP 200 for a bad part: the worker returns a wrong part with a report claiming every check passed | The supervisor re-executes every check against the artifacts on disk. Worker claims are hints, never results | G4.3; `wrong-part/` leg, validator `supervisor_recheck` |
| A revision silently breaks a feature nobody asked about | The revision-diff checker compares the geometry diff against the request scope and flags out-of-scope change | G4.2; `revision-diff/` leg, validator `revision_diff` |
| A memory leak hidden by restart luck | RSS sampled at job boundaries from the health endpoint, never from a post-hoc log parse | G4.5; `soak_status` |
| A runaway job wedges the pool forever | Wall-clock deadline plus whole-tree kill; the job resolves `TIMEOUT` | `timeout/` leg, validator `soak_status` |
| Unbounded allocation takes down the host rather than the job | The sandbox caps worker memory; the job resolves `OOM_KILLED` | `oom/` leg, validator `soak_status` |
| A native OCCT fault kills the worker and the job hangs with nothing reported | Abnormal exit maps to `WORKER_CRASHED` and the pool refills | `crash/` leg, validator `soak_status` |
| A job fails and says nothing a machine can read | Every terminal failure carries a structured detail; a detail-less failure is refused | `lifecycle/` leg, validator `job_lifecycle` |
| A job spec exfiltrates data from the host | Egress deny-by-default; the worker has an empty network namespace and needs no network | Story 5.3 — NOT measured by this suite |
| Free-form Python execution reaches the host through the service | Service mode unregisters the operator exec tool unconditionally; typed tools are the only mutation path | Story 5.2 — NOT measured by this suite |

## What this suite does NOT measure

Recorded so nobody reads a green G4.E as more than it is.

- **The kill's origin.** The `oom/` leg asserts the STATUS MAPPING only. Proving `OOM_KILLED` came
  from the sandbox rather than the host OOM killer needs the real jail of story 5.3. Until then
  nothing here distinguishes them.
- **Any real service behaviour.** Every case is resolved by `stub_service.py` from the case's own
  declaration. No job is run, no process is spawned, nothing is allocated. What the suite proves
  is that it can separate a planted fault from a clean control against a mapping authored before
  any service existed — the entry-gate property (AD-19), and nothing beyond it.
- **The two threats marked NOT measured above.** Both are sandbox and supervisor properties with
  no case in this suite. They are listed anyway: a threat list that dropped them would imply
  Phase 4's threat surface is smaller than it is.

## No grading rubric, and that is a decision

The entry-gate deliverable list requires "a grading rubric where judgment is needed". G4.E needs
none: every case is decided by comparing a terminal status against a closed set, which is
mechanical. The two rubrics in the repo (`benchmarks/g1/rubric.md`,
`benchmarks/g3/fault-injection/visual-judge/RUBRIC.md`) both exist because a model judges prose or
an image. Recorded here so the absence reads as a judged decision rather than an omission.
