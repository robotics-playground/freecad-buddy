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
| A job spec exfiltrates data from the host | Egress deny-by-default; the worker runs in an empty network namespace and needs no network | Story 5.3, Linux backend; `tests/external/test_phase4_sandbox.py` measures it against an unsandboxed baseline |
| A job writes outside its own directory | Mount namespace: everything read-only except `jobs/<id>/` | Story 5.3, Linux backend; same test file |
| Free-form Python execution reaches the host through the service | Service mode unregisters the operator exec tool unconditionally; typed tools are the only mutation path | Story 5.2; `test_phase4_supervisor.py` asserts `debug_exec` is unreachable with the flag set |

## What story 5.4 measured, and what it did not

The design payload, deliverable re-check and revision scope-checker landed with story 5.4, and the
committed plans were driven through the job service. Recorded in `parity-results.json`:

```
planned 20  geometry_pass 20  visual_pass 0  converged 0
```

- **This is not G4.1.** G4.1 requires the 20-SPEC benchmark. No spec-to-plan translator exists
  (`benchmarks/runner.py`), so the run carried the 20 COMMITTED plans instead. It measures the
  designer loop end to end through the job service — document creation, per-step preview-token
  approval, mutation, grading — and says nothing about the actor half, which is absent.
- **Geometry is 20/20, matching the G3 dev split.** The job service did not degrade the loop, which
  is the useful fact this run does establish.
- **Convergence is 0 by construction, not by failure.** The visual leg is unavailable: no vision
  backend, no GUI under `FreeCADCmd`, and on this branch no part exposes driving parameters so the
  judge drawing refuses. G4.3's visual-verdict requirement is therefore unmet and unmeasured.
- **G4.2 is unmeasured.** The revision mechanism and its `diff_scope` checker exist and are tested
  against synthetic diffs, but the 15-revision benchmark needs converged parts to revise, and
  nothing converges.

## What story 5.5 measured

Both criteria that do not depend on the visual leg were measured and PASS.

**G4.5, the 50-job soak** (`soak-results.json`):

```
jobs 50  statuses {'OK': 43, 'TIMEOUT': 2, 'WORKER_CRASHED': 5}
supervisor growth 2.00% (bar 20%)  hangs 0  silent 0
```

The mix deliberately includes crashes and timeouts. A soak of 50 clean jobs measures the happy
path 50 times and would miss the leak that only a killed worker leaves behind — and killing
workers is the normal condition of a service running untrusted specs. "No crash or hang" is read
as the SERVICE never crashing or hanging; a job resolving to a structured failure status is the
service working.

RSS is sampled at each job boundary from the health surface through stdlib `ctypes`, not parsed
from logs afterwards and not via `psutil`, which is not a dependency of this project.

**G4.4, the agent-to-agent cycle** (`agent-cycle-results.json`):

```
submit -> OK   inspect -> OK   revise -> QUEUED   accept -> OK
completed=True  auto_approve_off=True  human_inputs=0
```

`auto_approve_off` is asserted, not assumed. A cycle completed while the process-global
auto-approve flag was set would prove the flag works, not that the service can be driven without
a human — the flag IS a human's approval left permanently on. The confirm gate is satisfied per
step by a real preview token instead.

**The `spot_audit` token is deliberately unminted.** Leg-d requires a human attestation over at
least 20% of passing results. `attest_command` stamps `signed_by` from the environment and
verifies nothing about who ran it, so an agent minting one would fabricate the human audit the leg
exists to require. The gate therefore reports `leg-d: spot_audit token absent`, which is correct.

## What this suite does NOT measure

Recorded so nobody reads a green G4.E as more than it is.

- **The kill's origin, still only partly.** The `oom/` leg asserts the STATUS MAPPING only. Story
  5.3 landed the jail, so a memory ceiling is now enforced from outside the payload — but on a
  host that does not delegate cgroup2 it is enforced by `RLIMIT_AS`, which the process can lower
  itself. The sandbox report marks that case `weakened` rather than `applied`, so a run's own
  status says which it got. A cgroup-enforced kill is contained; an rlimit-enforced one stops an
  honest runaway and not a determined one.
- **Seccomp is not applied.** The Linux backend uses user, mount and network namespaces plus
  resource ceilings. There is no syscall filter, so a worker may make any syscall its unprivileged
  uid allows. `nsjail`/`bubblewrap` would add one; neither is a dependency, for the reason
  recorded in `REUSE-SURVEY.md`.
- **The Windows backend contains less.** A Job Object gives real memory and CPU ceilings and an
  atomic tree kill, but no network or filesystem isolation. It reports `egress_denied` and
  `filesystem_readonly` as UNAVAILABLE rather than claiming them. Running the service under WSL2
  gets the Linux backend and its containment.
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
