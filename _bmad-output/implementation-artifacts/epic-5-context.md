# Epic 5 Context: Autonomous Design Service (Phase 4 · gate G4)

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Turn the Phase 3 designer loop into a headless, single-tenant service. Any agent or human submits a part spec to a job API and gets back a validated model, exports, a validation report, rendered views, and revisions — no GUI, no human in the loop, every worker sandboxed. This matters because agent-to-agent job specs are fully untrusted input: the earlier phases relied on an operator confirming each mutation, and that control disappears here. The epic replaces it with OS-level isolation, a supervisor that re-runs every check instead of trusting worker claims, and a closed status set so no job ever fails silently.

## Stories

- Story 5.1: Entry Gate G4.E — Soak & Fault Harness
- Story 5.2: Supervisor & Worker Pool
- Story 5.3: Per-Job Sandbox
- Story 5.4: Job API & Revisions
- Story 5.5: Agent-to-Agent Proof & Gate G4 Exit

## Requirements & Constraints

**Capability.** A headless job API accepts spec submissions and delivers: the model, a supervisor-re-executed validation report, STEP/STL/3MF exports, and rendered views. It accepts revision requests against prior results and preserves unrelated geometry. It completes a full agent-to-agent submit → inspect → revise → accept cycle.

**Gate exit criteria (all must pass).**
- Headless parity: the 20-spec Phase 3 benchmark runs through the job API on CI with zero GUI, holding the Phase 3 rate (≥70 %).
- Revisions: 15 modification requests against prior results succeed ≥70 % with the geometry diff confined to the requested change.
- Deliverables complete: every job's report is schema-valid, carries supervisor-re-executed check fields including the independent visual-judge verdict, and ships STEP + STL that re-import clean.
- Agent-to-agent proof: an external MCP-client agent drives the whole cycle with zero human input.
- Robustness soak: a 50-job soak with no crash or hang, memory growth under 20 %, and every failure carrying a structured closed-set status — none silent.

**Entry gate before any implementation.** The soak and fault harness lands first and must fail honestly against a stub service. Four canonical faults must be caught ≥95 %: planted infinite loop → `TIMEOUT` with whole-tree kill; unbounded allocation → `OOM_KILLED` by the sandbox, not the host OOM killer; OCCT segfault → `WORKER_CRASHED` with pool refill; wrong-part-with-clean-report → supervisor re-check flags `SPEC_FAILED`. The revision-diff checker is fault-tested too (plant an unrelated-feature change, assert it is flagged). Both OS legs run the same suite with the identical error taxonomy. A leak-baseline experiment (single long-lived interpreter, M iterations) records the evidence for the worker-recycle default.

**Measurement discipline.** Rates carry Wilson 95 % CI and use majority-of-R scoring (R≥10 on exit). Held-out sets stay sealed until the exit run; a dev-vs-held-out gap over 15pp blocks exit. Validator sensitivity ≥95 % / false-alarm ≤5 % must be current before any score is citable. Exit also requires a human spot-audit token over ≥20 % of passing results; any audit-found false pass invalidates the run. Budgets are pass/fail at the gate, not advisory — meeting every assertion while blowing the soak budget fails.

## Technical Decisions

**Supervisor.** One long-lived process that never imports FreeCAD, so its own memory is flat by construction. It owns a spawn-context process pool (never fork — Qt/OCCT thread hazard plus no Windows support) with one task per worker child as the shipping default; the pool keeps K workers warm via background refill. The job queue is bounded with backpressure: submission past the bound returns a queue-full status rather than exhausting host memory. A dead worker resolves its job to `WORKER_CRASHED`; nothing hangs. Job lifecycle: schema-validate the spec (fail fast on invalid input) → enqueue → bind to a warm sandboxed worker with a wall-clock deadline and an iteration cap → collect the result envelope → re-execute verification → stamp the terminal status → clean the job directory per retention policy. K and any recycle count above one are set empirically by the soak test, not guessed.

**Sandbox.** One internal wrapper API keeps the supervisor OS-agnostic, with two backends. Linux is primary: an unprivileged jail (nsjail or bubblewrap, or a hardened network-free OCI container for CI reproducibility) with user/net/mount/pid/ipc/uts/cgroup namespaces, a read-only bind of the FreeCAD and Python install, cgroups v2 memory and CPU and pid caps, `setrlimit` as a per-process backstop, a seccomp allowlist, all capabilities dropped, unprivileged UID. Windows prefers running the identical Linux stack inside WSL2 with outbound deny, so one hardening profile serves both; the native alternative is a zero-capability AppContainer plus a Job Object for kill-on-close, process limits, memory limits, and CPU time. Restricted-token-only is a documented non-production fallback. Whole-tree kill on deadline or cap breach is mandatory on both OSes — never kill only the top PID, since orphaned OCCT helpers wedge the pool — and every kill maps to a status, never to silence.

**Egress deny-by-default and GPU-none.** The worker needs no network at all: spec intake, transport, and result delivery all live in the supervisor, and the worker only reads a spec file and writes artifacts to its scratch directory. An empty network namespace therefore costs zero functionality while removing the exfiltration threat class. Renders go through the offscreen software path.

**Data plane.** The control plane carries only small JSON — a spec descriptor in, a result envelope out, paths rather than blobs. No FreeCAD or OCCT object ever crosses the process boundary. The per-job directory is the sole writable mount and holds the input spec, exports, renders, the validation report, a per-job append-only audit stream, and captured worker stderr. The supervisor owns creation and cleanup.

**Supervisor re-executed checks.** This closes the "HTTP 200 for a bad part" hole. Every field the job API reports is backed by a check the supervisor re-runs against the artifacts on disk — export re-import oracles and the deterministic spec verifiers. Worker claims are hints, never results. The re-check machinery is the same verify code path the harness already uses; there is no Phase-4-only validator variant. A worker that crashed, timed out, or was OOM-killed can never surface as success.

**Closed status set and shared schemas.** Terminal outcomes come only from `OK | SPEC_FAILED | RECOMPUTE_ERROR | TIMEOUT | OOM_KILLED | WORKER_CRASHED | INVALID_INPUT`, each with machine-readable detail. The result envelope, validation report, job status, and audit-record types are contracts-owned and already exist from Phase 0 — this epic reuses them unchanged and defines no new variants. Every run carries a run id threaded through every envelope, audit record, and report, and writes its plan, per-iteration discrepancy vectors, judge verdicts with their images, and repair decisions into the session workdir under that id, so a failed production run is reconstructable from its workdir alone.

**Visual leg carries into delivery.** A part is done only when geometry assertions and an independent visual judge both pass. The judge is conjunctive and can never pass a part that geometry failed. The rendered views ship with the job, and the judge verdict is part of the delivered report.

**Free-form exec is permanently off.** The supervisor host sets service mode unconditionally, which unregisters the operator exec tool regardless of any environment flag. Typed tools stay the only mutation path. In-process Python restriction — audit hooks, RestrictedPython, import or builtin blacklists, namespace-restricted exec, AST filtering — is never described or relied on as a security boundary here; the only boundaries are the typed-tool architecture and the OS jail.

**Rejected alternative, do not revisit.** A long-lived shared FreeCAD worker cleaned between jobs does not work: closing a document only invalidates the Python wrapper while the OCCT allocator retains freed blocks. The process is the unit of memory reclamation.

**Health surface.** The service exposes a health endpoint reporting worker-pool occupancy, per-worker RSS, jobs completed, and the session id. Soak numbers are computed from samples of that endpoint at job boundaries, never from a post-hoc log parse.

**Document lifecycle.** The supervisor and worker open and close documents only through the document use cases — never raw FreeCAD document calls alongside the bridge. Every call carries an explicit document handle; the active document is never an implicit target. One job equals one worker equals one writer, which satisfies mutation serialization structurally.

**Runs on both OS legs.** The FreeCAD version matrix and the headless-CI requirement apply here as everywhere; version-sensitive calls stay behind the single shim.

## Cross-Story Dependencies

- Story 5.1 gates the whole epic: no Phase 4 implementation may begin until the soak and fault harness lands and demonstrably fails against a stub. Its budget is roughly 20 % of the phase.
- Story 5.2 (supervisor, pool, status mapping) is the base for 5.3, 5.4, and 5.5.
- Story 5.3 (sandbox) must land before the fault harness can prove `OOM_KILLED` comes from the sandbox rather than the host, and before soak numbers count.
- Story 5.4 depends on 5.2 and 5.3, and on the revision-diff checker fault-tested in 5.1.
- Story 5.5 is the exit and depends on all of the above plus a human spot-audit token.
- Epic 5 depends on Epic 4 (Phase 3 designer loop, its 20-spec benchmark, the visual judge) being green, and on Epic 1 for the gate runner, fault-injection framework, contracts-owned schemas, audit log, and export oracles. The preceding gate must be fully green before this phase starts.
- The concrete sandbox profiles, pool tuning, and slicer/DFM oracle choice are explicitly deferred to this gate — they are decisions to make here, not decisions already made elsewhere.
