---
title: 'Story 5.2: Supervisor & Worker Pool'
type: 'feature'
created: '2026-09-15'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '_bmad-output/implementation-artifacts/epic-5-context.md'
  - '_bmad-output/implementation-artifacts/ad-19-override-epic-5-2026-09-15.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/security-and-service-design.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Phase 4 needs a process that accepts a job, runs it in a worker that CAN be killed,
and resolves every outcome — including a crash, a hang, or a kill — to a machine-readable terminal
status. Nothing of this exists: there is no pool code anywhere in `src/`, and the one subprocess
precedent kills a single PID, which the design forbids because orphaned OCCT helpers wedge the
pool.

**Approach:** Add `hosts/phase4/` carrying a supervisor that never imports FreeCAD, a
spawn-context process pool at one task per child with warm refill and a bounded queue, and a
whole-tree kill that maps every abnormal exit to the closed status set. The worker runs the
existing use cases; the supervisor owns lifecycle, deadlines, and status.

## Boundaries & Constraints

**Always:**
- The supervisor never imports FreeCAD, directly or transitively. Its RSS is flat by
  construction, which is what makes the soak leak measurement meaningful at all.
- The pool uses `mp_context="spawn"` on both operating systems. Never `fork`: it is a Qt/OCCT
  thread hazard and has no Windows support.
- `max_tasks_per_child=1` ships as the default. The process is the unit of memory reclamation —
  closing a document only invalidates the Python wrapper while the OCCT allocator keeps the
  freed blocks.
- Kill the whole process tree, never the top PID alone. POSIX kills the process group; Windows
  closes a Job Object handle.
- Every abnormal exit maps to a member of the existing closed set. A worker that crashed, timed
  out, or was killed can never surface as `OK`.
- The supervisor host constructs its capability record with `service_mode=True` unconditionally,
  so `debug_exec` is unreachable regardless of the environment flag.
- Terminal failures carry structured detail. A failure with no detail is the silent failure AD-17
  forbids.

**Never:**
- Do not build the jail: no namespaces, cgroups, seccomp, nsjail, bwrap, WSL2 or AppContainer.
  Story 5.3 owns `run_job_in_sandbox` and everything inside it.
- Do not build the job API, the HTTP surface, or revisions. Story 5.4 owns those.
- Do not claim `OOM_KILLED` comes from a sandbox. Without 5.3's jail a memory cap is a
  `setrlimit`-class backstop at best; the status maps, the containment does not yet exist.
- Do not add a Phase-4-only validator variant. Re-checks reuse the existing verify and oracle
  code paths.
- Do not edit `usecases/capabilities.py`. `service_mode` and `exec_registered` already ship and
  are already tested; this story only calls them.
- Do not widen the audit `event` vocabulary or add `job_id` to `AuditRecord` unless a task below
  says so.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Job completes | Valid spec, worker returns an envelope | `JobStatus.state == "OK"` carrying the envelope | No error expected |
| Spec invalid | Spec failing contract validation | `INVALID_INPUT` before anything is enqueued | Fail fast, no worker bound |
| Worker exceeds deadline | Job runs past its wall clock | Whole tree killed; `TIMEOUT` with detail | Never a hang |
| Worker dies | Worker process exits abnormally | `WORKER_CRASHED` with detail; pool refills | Future never left pending |
| Worker exceeds memory cap | Allocation past the cap | `OOM_KILLED` with detail | Status maps; containment is 5.3's |
| Queue full | Submission past the bound | Queue-full status, host memory intact | Backpressure, never unbounded growth |
| Worker returns a malformed result | Worker output missing `state` or outside the closed set | Refused, resolved to a failure status | Untrusted output validated at the boundary |
| Exec flag set in service mode | `FREECAD_BUDDY_ALLOW_EXEC=1` on the supervisor host | `debug_exec` absent from the tool surface | Permanently off, not runtime-rejected |

</intent-contract>

## Code Map

Anchors verified on this branch at `e4738ec`.

**Already ships — call it, do not rebuild it:**
- `src/freecad_buddy/usecases/capabilities.py:12` `Capabilities(allow_exec, service_mode,
  auto_approve)`; `:21` `from_env(environ, *, service_mode=False)`; `:34` `exec_registered(caps)`
  returns `caps.allow_exec and not caps.service_mode`. The AD-4 gate the design sketches is
  already the shipped body. The supervisor calls
  `Capabilities.from_env(dict(os.environ), service_mode=True)` and changes nothing here.
- `src/freecad_buddy/contracts/status.py:11` `TerminalStatus` — all seven values including
  `TIMEOUT`, `OOM_KILLED`, `WORKER_CRASHED`; `:21` `JobState` adds `QUEUED`/`RUNNING`.
- `src/freecad_buddy/contracts/job.py:14` `JobStatus` TypedDict; required keys `schema` and
  `state`.
- `src/freecad_buddy/contracts/envelope.py:49` `ResultEnvelope` — what a worker returns.
- `src/freecad_buddy/adapters/audit_log.py:34` `AuditSink` — thread-safe, append-only, write-only.
  It has no reader; the design's "supervisor-aggregated" stream is new code if a task needs it.
- `benchmarks/g4/stub_service.py:90` `validate_job_status` — already-written validation for
  untrusted job output, landed by story 5.1. Reuse its rules rather than re-deriving them.

**The sibling to model, and the one to diverge from:**
- `src/freecad_buddy/hosts/headless/entry.py:74` `run()` — the startup sequence to mirror:
  stderr logging, capability record, registry, tool handlers, audit sink, serve. **Diverge at
  `:41` `verify_freecad_importable()` — the supervisor must NOT do this.**
- `src/freecad_buddy/hosts/gui_external/entry.py` — the working proof that a `hosts/` module can
  be FreeCAD-free. The supervisor is the second such module.

**The subprocess precedent, and exactly where it falls short:**
- `src/freecad_buddy/hosts/gui_addon/bootstrap.py:263` `subprocess.Popen(command,
  **_no_window_kwargs(logfile))`; `:278` `_no_window_kwargs` already carries the process-group
  primitives — POSIX `start_new_session=True`, Windows `CREATE_NO_WINDOW | DETACHED_PROCESS`.
- `bootstrap.py:295` teardown is `terminate()` then `kill()` **on a single PID**, which
  `security-and-service-design.md:139` forbids. Note `DETACHED_PROCESS` works AGAINST tree-kill.
  Read it for the spawn flags, not for the teardown.
- `src/freecad_buddy/adapters/marshal.py:37` states the constraint that motivates this whole
  story: "Threads cannot be killed, so a callable that overruns its budget keeps running after
  `Marshal.call` has already raised." A process can be killed; that is the point of the pool.

**Import rules — `scripts/check_imports.py`:**
- `hosts/` is the outermost ring and may import anything inward plus any third-party.
  `concurrent.futures` and `multiprocessing` are stdlib, so the pool needs no rule change.
- **The checker does NOT enforce "never imports FreeCAD" anywhere.** AD-18's central supervisor
  invariant is undefended today. A task below adds that guard.

**Read-only evidence:**
- `grep` for `ProcessPoolExecutor|multiprocessing|max_tasks_per_child|mp_context` over `src/` and
  `tests/` returns **nothing**. There is no pool to extend.
- `JobSpec` appears only in planning documents — zero hits in `src/`, `tests/`, `benchmarks/`.
  Adding it is a contracts change that drags `contracts/__init__.py`, `scripts/gen_schemas.py`,
  a generated `jsonschema/job-spec.schema.json`, and `tests/external/test_contracts.py`.
- `benchmarks/g4/stub_service.py:174` `submit(_spec)` raises `ServiceUnavailable`, and
  `tests/external/test_gate_g4_exit.py:158` asserts that it does. **That assertion STAYS.** The
  supervisor this story lands runs a lifecycle payload, not a design job, so the service still
  cannot produce a deliverable. Only its docstring changes, to name what is now missing.

## Tasks & Acceptance

**Execution:**
- `src/freecad_buddy/contracts/job.py` -- add a `JobSpec` TypedDict alongside `JobStatus`: the
  input half of the job contract, carrying the spec payload, an optional deadline and resource
  caps -- the supervisor validates against it and fails `INVALID_INPUT` before enqueueing, so the
  shape must exist before anything can be rejected against it.
- `src/freecad_buddy/contracts/__init__.py` -- re-export `JobSpec` -- every other contract type is
  reachable from the package root and a reader should not learn this one is different.
- `scripts/gen_schemas.py` -- register `("job-spec", JobSpec)` and regenerate -- schemas are
  drift-checked, so an unregistered contract type fails the check rather than silently skipping.
- `src/freecad_buddy/hosts/phase4/__init__.py` -- create the package, byte-empty or module-only --
  `tests/external/test_scaffold.py:44` constrains the shape of ring `__init__.py` files.
- `src/freecad_buddy/hosts/phase4/status_map.py` -- map an exit condition (timeout, abnormal exit
  code, signal, memory cap, clean return) onto `TerminalStatus` with structured detail -- one
  place decides status so no caller can invent a member outside the closed set, and a silent
  failure has nowhere to hide.
- `src/freecad_buddy/hosts/phase4/tree_kill.py` -- whole-tree kill with a POSIX process-group
  branch and a Windows Job Object branch, graceful signal then force after a grace period --
  killing the top PID alone leaves orphaned OCCT helpers that wedge the pool, which is the
  failure the design calls out by name.
- `src/freecad_buddy/hosts/phase4/pool.py` -- the worker pool: `spawn` context,
  `max_tasks_per_child=1`, K warm workers with background refill, a bounded queue returning a
  queue-full status under backpressure, and a per-job wall-clock deadline that triggers the tree
  kill -- the pool is what makes a job killable at all, and one task per child is what reclaims
  OCCT memory the allocator will not return.
- `src/freecad_buddy/hosts/phase4/worker.py` -- the worker entry the pool spawns: import FreeCAD
  HERE (never in the supervisor), dispatch the job to a payload callable, write artifacts to the
  job directory, and return a `ResultEnvelope` -- the process boundary is where FreeCAD becomes
  legal, and keeping the import on this side is what the supervisor's flat-RSS claim rests on.
  **Scope the payload to a single injected callable, not to the designer loop.** The eventual
  payload is `usecases/designer_loop.py:84` `run_designer_loop`, whose signature takes a
  `DesignPlan`, a `GeometryGrader`, a `VisualLeg` and a `Repairer`; wiring those is story 5.4's
  job-API work, and the visual leg in particular is the G3 blocker recorded in
  `g3-visual-leg-blocker-2026-09-15.md`. This story proves the LIFECYCLE — spawn, deadline, kill,
  status — which is measurable with a payload that sleeps, allocates, crashes or returns. A
  lifecycle that only works for one payload would have to be rebuilt when the payload changes.
- `src/freecad_buddy/hosts/phase4/supervisor.py` -- the long-lived supervisor: validate, enqueue,
  bind to a warm worker with a deadline, collect the envelope, validate untrusted worker output,
  stamp a `JobStatus`, and never import FreeCAD -- this is the AD-18 process whose invariant the
  whole phase depends on.
- `scripts/check_imports.py` -- add a rule that named FreeCAD-free modules import no FreeCAD
  module, directly or transitively through a first-party import, and register the supervisor
  under it -- AD-18's central invariant is undefended today, so a later edit adding
  `import FreeCAD` to the supervisor would pass every existing check.
- `benchmarks/g4/stub_service.py` -- leave `submit` raising `ServiceUnavailable` and say why in its
  docstring: a supervisor that runs a lifecycle payload cannot yet run a DESIGN job, because the
  designer payload is 5.4's wiring -- the seam's contract is "can this service produce a
  deliverable", and the honest answer stays no until 5.4. Flipping it here would make the gate
  report a capability the service does not have, which is the exact self-deception the entry gate
  exists to prevent.
- `tests/external/test_scaffold.py` -- add the new `hosts/phase4` files to the expected-file list
  -- the scaffold test is the repo's structural inventory.
- `tests/external/test_phase4_supervisor.py` -- unit-test the I/O matrix rows: each exit condition
  mapping to its status, the deadline killing a tree, a dead worker resolving rather than hanging,
  the bounded queue refusing under backpressure, malformed worker output being refused, and the
  supervisor importing no FreeCAD -- test naming is `Should <outcome> When <condition>` with
  `// Arrange`/`// Act`/`// Assert` phases.

**Acceptance Criteria:**
- Given the supervisor module, when its imports are resolved transitively, then no FreeCAD module
  is among them, and a test fails if one is later added.
- Given a job whose worker exceeds its wall-clock deadline, when the deadline fires, then the
  whole process tree is killed and the job resolves `TIMEOUT` with structured detail, leaving no
  orphaned child.
- Given a worker that exits abnormally, when the supervisor collects its result, then the job
  resolves `WORKER_CRASHED`, the future never stays pending, and the pool returns to K warm
  workers.
- Given a submission arriving when the queue is at its bound, when it is submitted, then it is
  refused with a queue-full status rather than growing the queue.
- Given `FREECAD_BUDDY_ALLOW_EXEC=1` in the supervisor host's environment, when its tool surface
  is listed, then `debug_exec` is absent.
- Given worker output missing `state` or naming a value outside the closed set, when the
  supervisor validates it, then the result is refused rather than reported as success.
- Given the pool is configured, when a worker finishes one job, then that worker process exits and
  is replaced rather than reused.

## Design Notes

**Why `spawn` and one task per child, restated so nobody re-tunes it blind.** `fork` is rejected
for two independent reasons: it is a Qt/OCCT thread hazard, and Windows does not have it.
`max_tasks_per_child=1` is rejected-alternative territory in the other direction: a long-lived
worker "cleaned between jobs" does not reclaim memory, because `closeDocument` only invalidates
the Python wrapper while the OCCT allocator retains the freed blocks. The process is the
reclamation unit. K and any recycle count above one are set empirically by the G4 soak, not
guessed here.

**Where this story's kill stops.** Whole-tree kill at the OS process level is 5.2's: a process
group on POSIX, a Job Object on Windows. The jail around that tree — namespaces, cgroups,
seccomp, egress deny — is 5.3's `run_job_in_sandbox`. The two are separable because a tree can be
killed without a jail. What cannot be claimed until 5.3 lands is that `OOM_KILLED` came from a
sandbox rather than the host OOM killer; `benchmarks/g4/THREATS.md` already records that limit and
this story does not discharge it.

**The supervisor's invariant needs a guard, not a comment.** `check_imports.py` bounds what each
ring MAY import but never requires a module to avoid something. "The supervisor never imports
FreeCAD" is the claim that makes its flat RSS meaningful and the soak measurement interpretable,
and today nothing would catch a later edit breaking it. The guard is cheap and belongs with the
module it protects.

## Verification

**Commands:**
- `uv run pytest tests/external/test_phase4_supervisor.py -q` -- expected: all pass.
- `uv run pytest tests/external -q` -- expected: 1482 pre-existing tests still pass, plus the new
  ones. `test_gate_g4_exit.py` is unchanged: the G4 gate must stay red.
- `uv run python scripts/check_imports.py` -- expected: `check_imports OK`, including the new
  FreeCAD-free rule over the supervisor.
- `uv run python scripts/gen_schemas.py --check` -- expected: no drift after `JobSpec` is
  registered and regenerated.
- `uv run python benchmarks/runner.py faults G4` -- expected: the G4 bars still met; the stub
  seam change must not silently unmeasure a validator.
- `uv run ruff check src/freecad_buddy/hosts/phase4 tests/external/test_phase4_supervisor.py` --
  expected: clean. Nine pre-existing E501 findings elsewhere are not this story's.

**Manual checks (if no CLI):**
- After a deadline-killed job, no worker process remains: inspect the process list for children of
  the supervisor PID and confirm the tree is gone, not just the parent.
