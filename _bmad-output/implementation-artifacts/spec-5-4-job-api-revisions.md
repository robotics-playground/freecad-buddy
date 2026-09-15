---
title: 'Story 5.4: Job API & Revisions'
type: 'feature'
created: '2026-09-15'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '_bmad-output/implementation-artifacts/epic-5-context.md'
  - '_bmad-output/implementation-artifacts/g3-visual-leg-blocker-2026-09-15.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/security-and-service-design.md'
warnings: ['multiple-goals']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Stories 5.2 and 5.3 built a job runner that can spawn, contain, deadline and resolve
a worker — but the only payloads it runs sleep, crash or echo. Nothing submits a design request,
nothing produces a deliverable, and nothing revises a prior result. Three G4 exit criteria measure
exactly those things.

**Approach:** Add a designer payload the worker can run, a deliverable set the supervisor
re-verifies rather than trusts, and a revision request carrying a declared scope that a
geometry-diff checker grades against. Then run the measurements and report what they produce.

## Boundaries & Constraints

**Always:**
- The supervisor re-derives every verdict it reports. `derive_verdict` is documented as "derived,
  never asserted", and a worker-supplied verdict is precisely the wrong-part-with-clean-report
  fault the G4 suite plants.
- Geometry and visual convergence are reported as two separate facts, never collapsed into one
  boolean. The visual leg is unavailable on this branch, so a collapsed number would read as a
  geometry failure that did not happen.
- `CAP_EXHAUSTED` is a failure. Mapping it to anything else reintroduces the G3.4 defect the
  designer loop was built to avoid.
- A payload raises; it never names its own terminal status. The supervisor owns status.
- The worker is the only place FreeCAD loads. The supervisor's flat RSS is what makes the soak
  leak measurement interpretable.
- Every measurement this story reports states what it measured. A number whose provenance is
  unstated will be read as the criterion it resembles.

**Never:**
- Do not write a spec-to-plan translator. None exists, the 20 committed plans come from an offline
  generator, and inventing one here would be authoring the actor the G3 gate is supposed to grade.
- Do not import `benchmarks/` from `usecases/`. The grader lives in the outermost ring and the
  import checker enforces the direction.
- Do not set a process-global auto-approve posture in the service. Every existing caller does this
  in a benchmark; a service running untrusted payloads must not.
- Do not claim G4.1 parity from a plan-driven run. Carrying committed plans measures the loop, not
  the actor, and the two are different criteria.
- Do not build the agent-to-agent proof or the exit ceremony. Story 5.5 owns both.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Design job submitted | Spec with a committed plan and compiled checks | `JobStatus` OK carrying the run record and deliverables | No error expected |
| Plan refused | Unapproved plan, or a step outside the surface | `INVALID_INPUT` | `PlanRefused` caught in the payload, never a crash |
| Geometry fails | Part misses its assertions | `SPEC_FAILED`, geometry and visual reported separately | Never `OK` |
| Visual unavailable | No judge backend on this host | Job reports geometry pass with `visual.unavailable` | Never counted as converged |
| Cap exhausted | Repairs run out before convergence | `SPEC_FAILED` with the cap named | Never `OK` |
| Deliverables written | Converged or geometry-passing part | STEP/STL/3MF under `jobs/<id>/exports/`, re-import verified | Missing export is a check failure |
| Worker lies in a report | Worker claims every check passed | Supervisor re-derives the verdict from the checks | Claim never echoed |
| Revision in scope | Request names one dimension; only it changes | Revision accepted, diff confined | No error expected |
| Revision out of scope | An unrequested feature also changes | `SPEC_FAILED` flagged by `diff_scope` | The G4.2 threat, caught |
| Revision of an unknown job | Request names a job with no prior result | `INVALID_INPUT` | Refused before a worker binds |

</intent-contract>

## Code Map

Anchors verified on this branch at `2b78ffb`.

**The seam stories 5.2/5.3 left for this one:**
- `src/freecad_buddy/hosts/phase4/worker.py:26` `Payload`, `:32` `PAYLOADS`, `:39` `register` —
  a job kind resolves to a callable registered inside the WORKER process. `:50` `load_payloads`
  imports `spec["payload_module"]`, because a callable cannot cross a fresh interpreter.
- `src/freecad_buddy/hosts/phase4/lifecycle_payloads.py` — the working example to imitate.
- `src/freecad_buddy/contracts/job.py:26` `JobSpec.payload` is an open mapping, deliberately: the
  designer job's own shape is this story's.
- `src/freecad_buddy/hosts/phase4/job_dir.py` — `exports/`, `renders/`, `validation.json` already
  exist as the one writable mount.

**The designer loop, and exactly how it is driven today:**
- `src/freecad_buddy/usecases/designer_loop.py:84` `run_designer_loop(registry, plan, checks,
  grader, visual_leg, repairer, authorizer, doc, run_id, anchor_frame, ...)`.
- `benchmarks/g3/actor_run.py:326-354` — the reference construction. Grader is
  `benchmarks/harness/assertions.evaluate`; visual leg is `make_visual_leg`; the confirm gate is
  satisfied by `confirm.set_auto_approve(True)` in a try/finally.
- `src/freecad_buddy/contracts/designer.py:150` `GeometryGrader` takes a live `document`; `:164`
  `VisualLeg` takes a `doc` STRING. The asymmetry matters when wiring.
- `:140` `converged(geometry_pass, visual_pass)` is the conjunction; `:115` `RunRecord.converged`
  is computed from the LAST iteration's two legs.
- `designer_loop.py:76` `PlanRefused` is a `ValueError`. Uncaught, the worker boundary turns it
  into `WORKER_CRASHED` rather than `INVALID_INPUT`.

**What the supervisor can re-run versus what needs a live document:**
- FreeCAD-FREE, so supervisor-repeatable: `adapters/export_oracle.py:173` `stl_oracle`, `:93`
  `StdlibStlOracle`, `:239` `mesh3mf_oracle`; `adapters/export_verdict.py:70`
  `assemble_export_verdict`; `contracts/report.py:79` `derive_verdict`.
- Needs a LIVE document, so worker-side only: `usecases/exports.py:128` `export_step`, `:240`
  `export_stl`, `:257` `export_3mf`, `:366` `_self_read`, `:287` `verify_export_step`, and
  `assertions.evaluate`.
- The trust boundary is the `facts` dict a worker returns. `assemble_export_verdict` grades the
  written file AGAINST those facts, so a worker that lies in `facts["source"]` earns a green
  verdict. Cross-checking it is this story's job, not an assumption to inherit.

**Measured blockers — verified on this branch, not inferred:**
- `parameter_declare` is **absent** here (it is on `feat/epic-4-gate-g3-exit`), so no part exposes
  driving parameters and the judge drawing refuses. The visual leg fails `visual.unavailable` on
  every part.
- `benchmarks/g3/actor-plans/*.json` holds **20 committed plans** from an offline generator.
  `grep` for a spec-to-plan translator returns **nothing**. `benchmarks/runner.py:575` names this
  as what blocks G3.1: "no designer actor ... nothing translates a spec into a plan."
- `grep "authorizer="` across `src/`, `benchmarks/`, `tests/` returns **nothing**. The
  `StepAuthorizer` protocol exists and is wired by no one.
- Revisions are **entirely absent**: `contracts/diff.py` `GeometryDiff` has one producer,
  `usecases/preview.py:559 _diff()`, which compares a scratch document before and after ONE
  operation. Nothing compares two persisted part states, and `diff_scope` does not exist in `src/`.
- The export-verdict composition is copy-pasted at `hosts/tool_catalog.py:70-111` and
  `hosts/gui_external/entry.py:67-82`. A third copy is a smell; factor it.

## Tasks & Acceptance

**Execution:**
- `src/freecad_buddy/hosts/phase4/designer_payload.py` -- the design job kind: load a case's
  checks and plan, run `run_designer_loop` with an injected grader and visual leg, catch
  `PlanRefused` and re-raise as an invalid-input signal, and return a `ResultEnvelope` reporting
  geometry and visual as separate facts -- the payload is the seam 5.2 left, and catching
  `PlanRefused` is what keeps a bad plan an `INVALID_INPUT` rather than a `WORKER_CRASHED`.
- `src/freecad_buddy/hosts/phase4/deliverables.py` -- write STEP/STL/3MF plus renders into the job
  directory and return the `facts` each export verified against -- the deliverable set is what
  G4.3 grades, and the facts are what the supervisor re-grades the files against.
- `src/freecad_buddy/adapters/export_verdict.py` -- factor the oracle-composition currently
  duplicated in `tool_catalog.py` and `gui_external/entry.py` into one helper both call --
  a third copy-paste for the supervisor would make the shared rule three places to change.
- `src/freecad_buddy/hosts/phase4/recheck.py` -- the supervisor's re-execution: re-run the
  FreeCAD-free oracles over the written files, re-derive the verdict with `derive_verdict`, and
  cross-check the worker's claimed facts against what the oracles measured -- worker claims are
  hints, and the wrong-part-with-clean-report fault is caught here or nowhere.
- `src/freecad_buddy/contracts/job.py` -- add a `RevisionRequest` shape carrying the prior job id,
  the requested change, and the declared SCOPE the diff is graded against -- a revision without a
  declared scope cannot be judged out-of-scope, which is the whole of G4.2.
- `src/freecad_buddy/hosts/phase4/revision.py` -- apply a revision to a prior result and produce a
  `GeometryDiff` between the two states, plus a `diff_scope` check that fails when anything
  outside the declared scope changed -- `GeometryDiff` already has the right shape (`touched`,
  `new`, `deleted`); nothing produces it from two part states, and the G4 fault suite already
  plants the out-of-scope case.
- `src/freecad_buddy/hosts/phase4/supervisor.py` -- accept a design job and a revision request,
  create the job directory, attach the re-executed `ValidationReport` to the `JobStatus`, and
  refuse a revision naming an unknown prior job -- the supervisor is where a submission becomes a
  job and where a report becomes trustworthy.
- `benchmarks/g4/run_parity.py` -- drive the 20 committed plans through the job API and record the
  rate, stating in the artifact that it measures the LOOP through the service and not the actor,
  because no spec-to-plan translator exists -- an unlabelled number will be read as G4.1 parity,
  which it is not.
- `benchmarks/g4/THREATS.md` -- record what the parity and revision runs actually measured and
  what they did not -- the gate cites this file, and a measurement whose limits live only in a
  commit message is a measurement that will be misread.
- `tests/external/test_phase4_job_api.py` -- test every I/O matrix row: plan refused, geometry
  failure, visual unavailable, cap exhausted, a lying worker's verdict re-derived, an in-scope
  revision accepted, an out-of-scope revision flagged, an unknown prior job refused -- naming is
  `Should <outcome> When <condition>` with `// Arrange`/`// Act`/`// Assert`.

**Acceptance Criteria:**
- Given a design job naming a committed plan, when it is submitted, then it runs to a `JobStatus`
  carrying a run record, and geometry and visual convergence are reported as separate fields.
- Given a worker that returns a report claiming every check passed, when the supervisor resolves
  the job, then the reported verdict is re-derived from the checks and the worker's claim is not
  echoed.
- Given a converged or geometry-passing part, when the job finishes, then STEP, STL and 3MF exist
  under `jobs/<id>/exports/` and each re-imports clean under an oracle the supervisor re-ran.
- Given a revision request whose result changes only what the scope declared, when it is graded,
  then it is accepted; and given one that changes anything else, then `diff_scope` fails it with
  `SPEC_FAILED`.
- Given a revision naming a prior job that does not exist, when it is submitted, then it is
  refused `INVALID_INPUT` before a worker is bound.
- Given the 20 committed plans, when they are driven through the job API, then a rate is recorded
  together with an explicit statement of what it measured and what it did not.
- Given stories 5.2 and 5.3, when this story lands, then their tests pass unchanged.

## Design Notes

**What the parity number can and cannot be.** G4.1 reads "run the 20-spec Phase 3 benchmark via
job API". The benchmark has two halves: an actor that turns spec text into a plan, and a loop that
executes the plan and grades the result. Only the second exists in code — `runner.py:575` says so
directly, and the 20 plans are committed output from an offline generator. A job API can therefore
carry plans, not specs. Driving the committed plans measures the loop end to end through the
service, which is worth having and is not G4.1. The artifact must say which it is, because a bare
rate will be read as the criterion it resembles.

**Why the visual leg still fails here.** `parameter_declare` is not on this branch, so no part
exposes driving parameters and the judge drawing refuses to be dimensioned from produced geometry.
Every job will report `visual.unavailable`, and `converged` will be false by construction. That is
why geometry and visual stay two fields: collapsing them would turn a measurable geometry result
into an unmeasurable zero, which is what `actor_run.py:404-410` already avoids.

**Auto-approve is a benchmark posture, not a service one.** Every existing caller satisfies the
confirm gate with a process-global `confirm.set_auto_approve(True)`. A service running untrusted
job specs must not hold that posture process-wide, and the `StepAuthorizer` protocol exists for
exactly this and is wired by nobody. The payload supplies an authorizer scoped to its own run
rather than flipping a global.

## Verification

**Commands:**
- `uv run pytest tests/external/test_phase4_job_api.py -q` -- expected: all pass.
- `uv run pytest tests/external/test_phase4_supervisor.py tests/external/test_phase4_sandbox.py -q`
  -- expected: stories 5.2 and 5.3 unchanged, 57 pass.
- `uv run pytest tests/external -q` -- expected: 1539 pre-existing plus the new ones.
- `uv run python scripts/check_imports.py` -- expected: `check_imports OK`.
- `uv run python scripts/gen_schemas.py --check` -- expected: no drift after `RevisionRequest`.
- `uv run python benchmarks/g4/run_parity.py` -- expected: a recorded rate with its scope stated.
- `uv run python benchmarks/runner.py faults G4` -- expected: the G4 bars still met.
- `uv run ruff check src/freecad_buddy/hosts/phase4 tests/external/test_phase4_job_api.py` --
  expected: clean.
