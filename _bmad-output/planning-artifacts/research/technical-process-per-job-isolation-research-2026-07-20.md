---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: ['docs/intent.md', 'docs/references/FreeCAD/src/App/Application.cpp', 'docs/references/FreeCAD/src/App/Document.cpp']
workflowType: 'research'
lastStep: 5
research_type: 'technical'
research_topic: 'Process-per-job isolation for a headless FreeCAD design service'
research_goals: 'Recommend a concrete worker architecture that lets a headless FreeCAD design service survive a 50-job soak run with <20% memory growth, no crash/hang, and structured errors (Phase 4 robustness exit criterion).'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Process-per-job Isolation for a Headless FreeCAD Design Service

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** technical (deep dive)

---

## Research Overview

Phase 4 of FreeCAD Buddy packages the Phase 3 design loop as a long-running headless
service (`docs/intent.md`, "Phase 4 — Autonomous Agent"). Its hardest exit criterion is
robustness:

> *Service survives a 50-job soak run without crash, hang, or resource leak (memory growth
> < 20% over the run); every failed job fails with a structured error, never silently.*
> — `docs/intent.md`, Phase 4 Measurable exit criteria

This is a real risk, not a theoretical one, because of two properties of the underlying
engine that the intent already flags: **FreeCAD is not thread-safe, and it leaks memory
across document open/close cycles.** A naive "one long-lived FreeCAD interpreter that opens
and closes a document per job" design will fail the soak criterion.

This research answers, with evidence: how bad the leak behavior is and why, what the
architectural options are (process-per-job vs process-pool-with-recycling), what
`FreeCADCmd` startup actually costs and how to hide it, how to contain crashes and enforce
timeouts/kills, how to cap resources on Windows *and* Linux (the CI matrix targets both),
and how the service front-end should talk to workers. It ends with a concrete, buildable
worker architecture and a validation plan tied directly to the Phase 4 exit criteria.

### Methodology and sources

Two evidence streams, in priority order:

1. **Web research** — FreeCAD issue tracker and forum, OpenCASCADE (OCCT) memory-manager
   docs, Python `multiprocessing` / gunicorn pre-fork practice, Windows Job Objects vs
   Linux cgroups/rlimit.
2. **Local FreeCAD source** — `docs/references/FreeCAD/src/App/Application.cpp` and
   `Document.cpp`, to read the actual `closeDocument`/`~Document` cleanup path and judge
   what is and is not released on close. File paths and line numbers are cited inline.

All web claims carry source links (see **Sources** at the end). All source-code claims cite
the local file and line.

---

## 1. The problem: why a single long-lived FreeCAD process leaks

### 1.1 What the FreeCAD source actually does on close

`App::Application::closeDocument` (local: `docs/references/FreeCAD/src/App/Application.cpp:687`)
removes the document from the internal `DocMap` and deletes the C++ `Document` via a
`std::unique_ptr`:

```cpp
// Application.cpp:707-711
const std::unique_ptr<Document> delDoc (pos->second);
DocMap.erase( pos );
DocFileMap.erase(Base::FileInfo(delDoc->FileName.getValue()).filePath());
_objCount = -1;
```

The `Document` destructor (`docs/references/FreeCAD/src/App/Document.cpp:1037`) does clear
the obvious owned state: it calls `clearUndos()`, `d->clearDocument()` (deletes the object
array), and deletes the transient directory on disk. **However**, note the deliberate
comment about the Python wrapper (`Document.cpp:1055-1063`):

```cpp
// ...we must still invalidate the Python object because it doesn't need to be
// destructed right now because the interpreter can own several references to it.
Base::PyGILStateLocker lock;
auto* doc = static_cast<Base::PyObjectBase*>(d->DocumentPythonObject.ptr());
doc->setInvalid();
```

The C++ side is freed, but the **Python-visible wrapper is only marked invalid**, and its
actual release depends on the CPython interpreter dropping every reference it holds. In a
scripted headless driver this is exactly where references leak: a stray reference to the
old `App.ActiveDocument`, a `Part.Shape` pulled out for verification, an object in a
closure, or a value cached in a module-level dict keeps the wrapper — and through it
potentially large OCCT shapes — alive across jobs. The C++ `closeDocument` cannot reclaim
what Python still references.

**Takeaway:** correct close semantics in FreeCAD are *cooperative*. Freeing the document
requires both `App.closeDocument(name)` **and** the Python driver dropping every reference
(then `gc.collect()`). Any single missed reference in the verify-first tool layer — which,
by design, pulls shapes, bounding boxes, and mass properties out of the model on every job —
becomes a per-job leak. Under a 50-job soak this compounds.

### 1.2 The OCCT allocator hides freed memory from the OS

Even with perfectly disciplined references, the process RSS can grow. FreeCAD's geometry
kernel is OpenCASCADE (OCCT). When OCCT is built with its optimized memory manager
(`MMGT_OPT=1`, historically common), freeing a block does **not** return it to the OS:

> *"Recycled medium blocks contained in the free lists (released by the program but held by
> the memory manager) can be returned to the heap by method `Standard::Purge()`. This may
> lead to considerable memory consumption and even be misinterpreted as a memory leak."*
> — OCCT Foundation Classes docs

> *"Space allocated for small blocks cannot be (currently) released to the system, while
> space for medium size blocks can be released by method `Purge()`."*

So OCCT intentionally caches freed blocks in free-lists for reuse; medium blocks only go
back to the OS on an explicit `Standard::Purge()`, and small blocks essentially never do.
A per-job design that builds and tears down geometry will show a rising RSS that looks like
a leak but is partly allocator caching — and partly genuinely unreclaimable small-block
fragmentation. This directly threatens the "< 20% memory growth" number regardless of how
clean the Python side is.

### 1.3 Confirmed leak reports in FreeCAD

The FreeCAD issue tracker corroborates that leaks are a live, recurring problem across
subsystems (not a one-off):

- **Core memory leak, v1.0 regression** (FreeCAD/FreeCAD #19274): a confirmed regression —
  v0.21 does not leak on the same hardware, v1.0 leaks at **6–15 MB/s** during basic UI
  interaction, "Priority: High", still open. *This particular one is GUI-side* (menus /
  Preferences), so it is largely irrelevant to a `FreeCADCmd` headless service — a useful
  point in favor of headless — but it shows the project ships memory regressions between
  minor versions, so the service must not assume any given FreeCAD build is leak-free.
- Multiple workbench-level leaks: Draft (#5761), TechDraw (#9265), CAM/PathSimulator
  (#9403, #6092), `Part.Face.Surface` (tracker #3771). The recurring community observation
  is blunt: *closing the document does not release the memory — you have to close FreeCAD
  entirely.*

That last sentence is the whole argument for process isolation: the community's own
empirical workaround for FreeCAD leaks is **restart the process**. A service should
automate exactly that.

**Conclusion for Phase 4:** treat "one FreeCAD interpreter, many jobs" as unable to meet the
soak criterion on its own. The reliable way to hit "< 20% growth over 50 jobs" is to make
the *unit of memory reclamation a process*, and recycle processes.

---

## 2. Architectural options

### 2.1 Option A — Process-per-job (spawn, run one job, exit)

Front-end receives a job, spawns a fresh `FreeCADCmd` (or `python` importing `FreeCAD`)
process, hands it the spec, collects the result + exports + validation report, then lets the
process exit. The OS reclaims **all** memory — OCCT free-lists, leaked Python wrappers,
fragmentation, everything — on exit.

- **Pros:** strongest possible isolation. Memory growth over the run is structurally ~0 (each
  job starts from a clean process; the service parent stays tiny). A crash or hang in one job
  cannot corrupt another. Simplest correctness story — trivially satisfies the leak
  criterion. A segfault in OCCT is contained to one job.
- **Cons:** pays full FreeCAD startup cost on **every** job (see §3). For a design loop where
  a single job is minutes long (Phase 3 target is ≤ 10 min/part; Phase 4 keeps that), a
  ~1–5 s startup is negligible overhead (< a few %). For short jobs it would dominate.

### 2.2 Option B — Process pool with recycling (warm workers, recycle after N jobs)

A small pool of pre-started worker processes, each already having imported FreeCAD, pull jobs
from a queue. After a worker finishes **N** jobs (or exceeds a memory watermark) it is retired
and replaced. This is the classic gunicorn `--max-requests` / `multiprocessing`
`maxtasksperchild` pattern:

> *"`maxtasksperchild` limits the number of tasks a worker can execute before being terminated
> and replaced with a new process, which resets memory."* — Python multiprocessing practice
> *"Set `--max-requests` with jitter to recycle workers."* — gunicorn design notes

- **Pros:** amortizes startup across N jobs (startup cost ≈ startup/N per job). Bounds memory
  because recycling caps how much any worker can accumulate. Keeps crash isolation at the
  worker granularity.
- **Cons:** within a worker's N-job window, the §1 leaks still accumulate, so N must be chosen
  so that N jobs' growth stays under budget. More moving parts (pool manager, health checks,
  recycle logic). If N is set too high the soak criterion fails; if N=1 it degenerates into
  Option A.

### 2.3 Option C — Fork a warm template (Linux) / spawn (Windows)

Pre-initialize one "warm" FreeCAD process, then `fork()` a child per job. Copy-on-write means
the child inherits the loaded interpreter + FreeCAD modules at near-zero cost:

> *"Fork-based approaches achieve near-zero startup latency by cloning a warm process,
> leveraging the kernel's fork() mechanism ... with copy-on-write to defer actual page
> copies."* — cold-start / pre-fork literature

- **Pros:** combines Option A's per-job clean-slate reclamation (child exits → all its memory
  freed) with near-zero startup. Best of both on Linux.
- **Cons:** `fork()` after Qt/OCCT/Python have initialized is **risky**: forking a
  multi-threaded process only clones the calling thread, so any OCCT/Qt background thread or
  held lock in the parent leaves the child in an undefined state (the classic fork-without-exec
  hazard). And Windows has **no `fork()`** — `multiprocessing` there uses `spawn`, which
  re-imports everything, so the CoW win evaporates. Given the CI matrix is Windows + Linux
  (`docs/intent.md` risk row "Headless vs GUI behavior differences" and cross-platform CI),
  a fork-only design is not portable.

### 2.4 Recommendation: **hybrid — warm pool of single-job workers (recycle N=1 by default)**

The right answer for this project is Option B *structured to behave like Option A per job*:

- **A small warm pool** of worker processes that have already imported FreeCAD, so startup
  cost is paid once at pool fill, not per job (defeats §3 latency).
- **`maxtasksperchild = 1` by default** — i.e. each worker executes exactly **one** design
  job, returns the result, and is then torn down and replaced by a fresh warm worker. This
  gives Option A's guarantee ("all memory reclaimed by the OS between jobs, growth ≈ 0")
  while a background refill hides startup. Because Phase 4 jobs are minute-scale, the pool
  only needs to be a few workers deep to keep latency invisible.
- **N is a tunable, not a constant.** If profiling shows a single FreeCAD import + a few
  jobs stays comfortably under 20% growth, N can be raised (e.g. 5–10) to cut process churn.
  The soak test (§7) sets the ceiling empirically. Ship with the safe default (N=1) and raise
  only with soak evidence.
- **Cross-platform:** use `multiprocessing`'s **`spawn`** start method (the default and only
  option on Windows) everywhere, so behavior is identical on the Windows and Linux CI legs.
  Do **not** rely on `fork()` — the Qt/OCCT/thread hazards and Windows unavailability make it
  a portability and correctness trap here.

This is a small amount of machinery (a supervisor + a recyclable worker) that turns the
FreeCAD leak from a service-killing property into a non-issue, and it is directly aligned with
the intent's "Reuse before invention" principle — the recycle pattern is standard gunicorn/
multiprocessing practice, not a novel invention.

---

## 3. FreeCADCmd startup cost and how to hide it

**What startup costs.** `FreeCADCmd` (a.k.a. `freecadcmd`, the console executable) is the
headless twin of the GUI binary. A caveat from the field: *"FreeCADCmd actually requires all
or at least most of the UI libraries"* and *"it is not always clear whether commands work in
the headless environment or not."* In practice startup is dominated by loading the FreeCAD
core + OCCT shared libraries and importing the workbench Python modules the job needs
(`Part`, `Sketcher`, `PartDesign`). Order-of-magnitude, cold startup is typically **~1–5 s**
depending on disk, platform, and which modules import; a related MCP project raised its FreeCAD
startup timeout to **60 s** to tolerate slow machines, which sets the pessimistic tail.

**Why it's tolerable here.** Phase 4 inherits Phase 3's "median wall-clock ≤ 10 minutes per
part" budget. Even a 5 s cold start is < 1% of a 10-minute job, so **process-per-job startup
is not the bottleneck** — the design loop is. The reason to still hide startup is *latency to
first byte* for the agent-to-agent cycle and interactive revision requests, not throughput.

**Mitigations, in order of preference:**

1. **Warm pool (primary).** Keep K workers pre-imported and idle-ready. A submitted job binds
   to an already-warm worker → ~0 startup latency observed by the caller. Background refill
   replaces a retired worker while other workers serve.
2. **Import only what's needed.** Import `Part`/`Sketcher`/`PartDesign` explicitly in the
   worker bootstrap; avoid pulling GUI/`FreeCADGui`, TechDraw, CAM, Draft etc. unless a job
   needs them (several of those are exactly the leaky workbenches from §1.3).
3. **Pin the FreeCAD build & reuse the CI image.** The intent already mandates version pinning
   and a CI matrix (risk row "FreeCAD version drift"); a prebuilt conda/AppImage/Docker image
   with FreeCAD resident avoids per-run install cost. (Reuse Map: "Headless FreeCAD in CI —
   Community Docker images / conda-forge / AppImage.")
4. **Avoid fork-based warm cloning** for the reasons in §2.3 (Qt/thread + Windows).

---

## 4. Crash containment, timeouts, and kill mechanics

The soak criterion forbids "crash" and "hang." Both are worker-process concerns, and both are
solved by making the **supervisor** own worker lifecycle:

### 4.1 Crash containment

- Each job runs in a child process. An OCCT segfault, a Python `SIGABRT` from a bad shape, or
  a C++ assertion kills **only that child**. The supervisor (the service front-end) survives.
  This is the same isolation gunicorn relies on: *"Each worker is a separate, isolated OS
  process ... ensuring isolation and resilience,"* and the arbiter *"restarts crashed
  workers"* on `SIGCHLD`.
- The supervisor must distinguish **clean exit with result** vs **abnormal exit (non-zero /
  signal)**. Abnormal exit → emit a **structured error** for that job (satisfying "every
  failed job fails with a structured error, never silently") and refill the pool. Never let a
  dead worker be silently reused.

### 4.2 Timeout / hang detection and kill

- Every job gets a **wall-clock deadline** (bounded above by the Phase 3 ≤ 10 min budget plus
  headroom; the intent's Phase 4 "iteration caps" also cap self-repair loops). On deadline
  breach the supervisor **kills the worker process tree** — not just the top process, because
  FreeCAD/OCCT may have spawned helper threads/processes, and orphaned children keep memory
  and can wedge the pool.
- **Kill mechanics must terminate the whole tree:**
  - **Windows:** assign the worker to a **Job Object**. *"When a job is closed, all associated
    processes can be terminated automatically"* — closing the job handle atomically kills the
    entire tree with no orphan risk. This is the correct Windows primitive; do not rely on
    `Process.kill()` of the top PID alone.
  - **Linux:** put the worker in its own **process group / session** (`start_new_session`) and
    signal the group (`SIGTERM` → grace → `SIGKILL`), or use a cgroup (§5) and freeze/kill the
    cgroup. This reaps children the same way the Windows Job Object does.
- A hard `SIGKILL`/Job-close is safe here precisely because of process isolation: there is no
  shared in-process state to corrupt, and the killed job's memory is fully reclaimed by the OS.

### 4.3 Structured errors

Give every terminal job outcome one of a small closed set of structured statuses, e.g.
`OK | SPEC_FAILED | RECOMPUTE_ERROR | TIMEOUT | OOM_KILLED | WORKER_CRASHED | INVALID_INPUT`,
plus a machine-readable detail payload. Crucially — and this maps to the Phase 4
self-deception threat in `docs/intent.md` ("Service returns HTTP 200 + well-formatted report
for a bad part") — the validation report fields must be **re-executed geometry checks run by
the supervisor/an independent check, not the worker agent's echoed claims.** A worker that
crashed or timed out can never be reported as `OK`.

---

## 5. Resource caps — Windows and Linux

The service must cap memory (to catch a runaway job before it OOMs the host) and CPU/time. The
mechanisms differ by OS; the abstraction should be a single "resource-limited sandbox" wrapper
with two backends.

### 5.1 Windows — **Job Objects**

Windows Job Objects are the direct analog of Linux cgroups (they *"group processes and enforce
`JobObjectExtendedLimitInformation.ProcessMemoryLimit`"*; a process exceeding it is terminated
with `STATUS_COMMITMENT_LIMIT`). One Job Object per worker gives:

- **`ProcessMemoryLimit` / `JobMemoryLimit`** → hard memory cap (runaway job is killed, host
  protected — feeds the `OOM_KILLED` structured error).
- **`ActiveProcessLimit`** → cap number of processes (defense against a job fork-bomb).
- **`BasicLimitInformation.PerJobUserTimeLimit`** → CPU-time cap.
- **`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`** → whole-tree teardown on handle close (the §4.2
  kill primitive).

Access from Python via `pywin32` (`win32job`) or a small `ctypes` shim.

### 5.2 Linux — **cgroups v2** (primary) + **rlimit** (per-process backstop)

- **cgroups v2** is the group-level control matching Job Objects: *"limits, accounts for and
  isolates the resource usage (CPU, memory ...) of a collection of processes"* with rich
  memory (`memory.max`, `memory.high`) and CPU controllers, and can kill the whole group when
  the memory limit is hit (`memory.oom.group`). This is the preferred Linux backend — it caps
  the entire worker tree, and pairs naturally with running workers in containers where the CI
  already provides cgroup limits.
- **`setrlimit`** (`RLIMIT_AS`/`RLIMIT_DATA` for address space, `RLIMIT_CPU` for CPU time,
  `RLIMIT_NPROC`) applied in the child before `exec` is a simple **per-process** backstop.
  Note the documented limitation: *"rlimit does not allow specifying limits for a set of
  processes or ... an action when a limit is reached"* — so rlimit alone is insufficient if a
  job spawns helpers; use it *in addition to* cgroups/process-group kill, not instead.
- The **Linux OOM killer** is the last-resort host protector; the service should set explicit
  cgroup memory limits so a job is killed cleanly (attributable → `OOM_KILLED`) rather than
  letting the kernel OOM-killer pick a victim unpredictably.

### 5.3 Portability wrapper

Expose one internal API — `run_job_in_sandbox(spec, mem_limit, cpu_time_limit, wall_deadline)`
— with a Windows (Job Object) and a Linux (cgroup + process-group + rlimit) implementation.
This keeps the supervisor OS-agnostic and keeps the CI matrix honest (same abstraction, tested
on both legs, per the intent's headless-parity discipline).

---

## 6. IPC between service front-end and worker processes

Requirements: pass a job spec + skills context in; get a result + validation report + export
file paths + structured status out; survive worker death without deadlocking; work on Windows
and Linux; keep the *large* artifacts (STEP/STL/3MF, renders) off the wire.

**Recommended pattern:**

1. **Control plane — a queue, not shared memory.** A `multiprocessing.Queue` (or a real broker
   like Redis/RabbitMQ if the service later scales to multiple hosts) carries small JSON job
   descriptors and small JSON result envelopes. JSON (not pickle) as the wire format keeps the
   boundary language-agnostic — the same MCP-style contract the bridge already uses — and
   avoids pickling FreeCAD/OCCT objects, which is fragile and a leak vector.
2. **Data plane — the filesystem.** Workers write exports and the validation report to a
   per-job working directory (e.g. `jobs/<job_id>/`); the result envelope carries **paths**,
   not blobs. This matches how FreeCAD already exports (STEP/STL to disk) and keeps IPC
   messages tiny. The supervisor owns cleanup of the job dir after collecting results.
3. **Never share FreeCAD state across the boundary.** Because FreeCAD is not thread-safe and
   its Python wrappers can't be safely serialized, the only things that cross the process
   boundary are plain data (spec in, JSON report + file paths out). This is what makes the
   isolation real rather than nominal.
4. **Liveness & backpressure.** The supervisor tracks each worker with a timeout and a
   heartbeat/`sentinel` (process handle). If a worker dies mid-job, the pending job's `Future`
   is resolved with `WORKER_CRASHED` (never left hanging → satisfies "no hang"). A bounded
   queue applies backpressure so a flood of submissions can't exhaust host memory.
5. **Audit log.** The intent requires "full audit log of every operation." Have workers stream
   structured operation records (tool call → params → verify result) to a per-job log file in
   the data plane; the supervisor aggregates. Logs are for explaining failures; per intent
   principle #6, they never *define* success.

**Concrete stack:** Python `concurrent.futures.ProcessPoolExecutor` (with `max_workers = K`,
`max_tasks_per_child = N`, `mp_context = spawn`) is the smallest thing that implements the
warm-pool + recycling + Future-based result/crash handling above, on both OSes, from the
standard library. Wrap each submitted task in the §5 sandbox and the §4 timeout. Graduate to
an external broker only if/when Phase 5 needs multi-host scale (the intent scopes Phase 4 as
single-tenant/local-first, so stdlib is enough now — "Reuse before invention").

---

## 7. Recommended architecture (concrete) and how it meets the exit criteria

```
                 ┌───────────────────────────────────────────────┐
   job spec  ──► │  Service front-end (Supervisor, 1 process)     │
   (MCP/HTTP)    │  - job queue (bounded, JSON descriptors)       │
                 │  - warm worker pool manager (K warm workers)   │
   report +  ◄── │  - per-job: deadline + sandbox + result future │
   exports       │  - structured-status assembler (re-checks!)    │
                 │  - audit-log aggregator                        │
                 └───────┬───────────────┬───────────────┬────────┘
                         │ spawn (mp)     │               │  (recycle after N jobs)
                 ┌───────▼──────┐  ┌──────▼───────┐  ┌────▼─────────┐
                 │ Worker 1     │  │ Worker 2     │  │ Worker K     │
                 │ FreeCAD      │  │ FreeCAD      │  │ FreeCAD      │
                 │ imported;    │  │ imported;    │  │ imported;    │
                 │ Part/Sketch/ │  │ runs 1 job,  │  │ ...          │
                 │ PartDesign   │  │ exits, freed │  │              │
                 │ + sandbox    │  │ by OS        │  │              │
                 └──────┬───────┘  └──────────────┘  └──────────────┘
                        │ writes exports + validation.json + audit.log
                 ┌──────▼───────────────────────────────────────────┐
                 │  Data plane: jobs/<job_id>/ (STEP, STL, 3MF,      │
                 │  renders, validation.json, audit.log)             │
                 └───────────────────────────────────────────────────┘
```

**Design summary:**

- **Supervisor** is a single small, long-lived process. It never imports FreeCAD, so *it*
  cannot leak FreeCAD/OCCT memory — the service's own footprint is flat by construction.
- **Warm worker pool** of `K` processes (small, e.g. 2–4 for local-first) that have imported
  only the needed FreeCAD modules. **`max_tasks_per_child = N` (default 1)**: a worker runs one
  design job then is torn down and replaced by a background-warmed successor. All FreeCAD/OCCT
  memory (leaked wrappers, OCCT free-lists, fragmentation) is reclaimed by the OS on worker
  exit — this is what holds memory growth near zero across the run.
- **Per job:** wrapped in the §5 OS sandbox (Windows Job Object / Linux cgroup+pgroup+rlimit)
  and a wall-clock deadline; kill-the-tree on breach.
- **Result path:** worker writes artifacts to `jobs/<job_id>/`; returns a small JSON envelope;
  supervisor **re-runs the geometry/shape validity checks itself** (or via an independent
  checker) before stamping the report status — closing the Phase 4 self-deception hole.
- **`spawn`** start method on both OSes for identical Windows/Linux behavior.

**Mapping to Phase 4 exit criteria:**

| Phase 4 criterion | How this architecture satisfies it |
|---|---|
| Memory growth < 20% over 50-job soak | Worker recycling (N=1 default) makes the OS reclaim all per-job memory; supervisor never touches FreeCAD, so its RSS is flat. Growth is bounded by pool size × per-worker window, not by cumulative jobs. |
| No crash | Job crash is contained to one child; supervisor survives and refills. |
| No hang | Wall-clock deadline + tree-kill (Job Object / process group); dead-worker `Future` resolves to `WORKER_CRASHED`. Nothing blocks forever. |
| Every failed job → structured error, never silent | Closed status set (`TIMEOUT`/`OOM_KILLED`/`WORKER_CRASHED`/`RECOMPUTE_ERROR`/…); abnormal exit is always mapped to a structured failure; report fields are re-executed checks, not echoed worker claims. |
| Audit log of every operation | Per-job `audit.log` in the data plane, aggregated by supervisor. |
| Resource limits / sandbox (Phase 4 "safety rails") | Per-job OS sandbox with memory/CPU/process caps on both platforms. |

---

## 8. Validation plan (validate this before Phase 4 build, per the intent's gate)

The intent mandates a Validation Design Gate before implementation. For this architecture:

1. **Leak-baseline experiment (build-vs-reuse evidence).** Before choosing N, run the *same*
   FreeCAD design job in a single long-lived interpreter for M iterations (open doc → build →
   verify → `closeDocument` → `gc.collect()`), sampling RSS. This quantifies the real per-job
   growth and whether `Standard::Purge()` + disciplined `gc` alone can hold < 20% (it likely
   cannot for large M — which is the justification for process recycling, recorded per the
   "record why you invented/adopted" rule).
2. **Soak harness = the exit test.** A 50-job soak run driven through the job API, sampling
   supervisor RSS + aggregate worker RSS at job boundaries; assert peak growth < 20% and zero
   unhandled exits. This *is* the Phase 4 robustness criterion; build it against a stub first
   (fail honestly), then against the real service.
3. **Fault injection (per intent principle #2, "validate the validator"):** plant a job that
   (a) infinite-loops → must hit `TIMEOUT` + tree-kill; (b) allocates unbounded memory → must
   hit `OOM_KILLED` via the sandbox, not the host OOM killer; (c) segfaults OCCT → must yield
   `WORKER_CRASHED` and pool refill; (d) returns a *wrong* part with an HTTP-200-shaped report
   → the supervisor's independent re-check must flag `SPEC_FAILED`. All four must be caught
   with the intent's ≥ 95% sensitivity target.
4. **Cross-platform:** run the soak + fault suite on **both** Windows and Linux CI legs; assert
   identical structured-error taxonomy on both (guards the "works in dev, fails in service"
   headless-parity risk).

---

## Key Findings & Recommendation (summary)

1. **A single long-lived FreeCAD process will fail the soak criterion.** Local source shows
   `closeDocument` only *invalidates* the Python document wrapper (`Document.cpp:1055-1063`) —
   reclamation depends on the Python driver dropping every reference — and OCCT's `MMGT_OPT`
   allocator caches freed blocks (only `Standard::Purge()` returns medium blocks; small blocks
   never return to the OS). The FreeCAD tracker confirms recurring leaks and the community's own
   workaround: *restart the process.*
2. **Make the process the unit of memory reclamation.** Recommended architecture: a **warm pool
   of worker processes recycled after N jobs (default N=1)** using Python `multiprocessing`/
   `ProcessPoolExecutor` with the **`spawn`** start method (identical on Windows + Linux; avoid
   `fork()` — Qt/OCCT/thread hazards and no Windows support). This gives process-per-job memory
   guarantees while the warm pool hides FreeCAD's ~1–5 s startup (negligible vs the ≤ 10 min
   job budget anyway).
3. **Crash/hang containment via the supervisor:** per-job wall-clock deadline + **whole-tree
   kill** (Windows **Job Object** / Linux **process group or cgroup**); a dead worker resolves
   its job `Future` to a structured error and the pool refills — nothing hangs, nothing is
   silent.
4. **Resource caps, cross-platform:** **Windows Job Objects** (memory/CPU/process limits,
   kill-on-close) and **Linux cgroups v2** (primary) with **`setrlimit`** as a per-process
   backstop, behind one `run_job_in_sandbox()` wrapper.
5. **IPC:** JSON control plane over a bounded queue (`ProcessPoolExecutor` Futures);
   filesystem data plane (`jobs/<job_id>/` holds exports + `validation.json` + `audit.log`,
   envelopes carry paths not blobs); **no FreeCAD state ever crosses the process boundary**;
   the supervisor **re-executes** validation checks rather than trusting the worker's report —
   closing the Phase 4 "HTTP 200 for a bad part" self-deception hole. Ship stdlib now
   (single-tenant/local-first); graduate to a broker only if Phase 5 needs multi-host scale.

---

## Sources

- FreeCAD source (local): `docs/references/FreeCAD/src/App/Application.cpp` (`closeDocument` @687, `closeAllDocuments` @719); `docs/references/FreeCAD/src/App/Document.cpp` (`~Document` @1037, Python-wrapper invalidate @1055-1063, `_clearRedos` @541, `clearDocument` @716).
- [Core: Memory leak in v1.0 (Regression) · Issue #19274 · FreeCAD/FreeCAD](https://github.com/FreeCAD/FreeCAD/issues/19274)
- [Massive memory leak in Draft · Issue #5761 · FreeCAD/FreeCAD](https://github.com/FreeCAD/FreeCAD/issues/5761)
- [Memory leak in TechDraw · Issue #9265 · FreeCAD/FreeCAD](https://github.com/FreeCAD/FreeCAD/issues/9265)
- [CAM: Memory leak in PathSimPy.cpp · Issue #9403 · FreeCAD/FreeCAD](https://github.com/FreeCAD/FreeCAD/issues/9403)
- [CAM: Increasing memory usage with Adaptive Processing · Issue #6092 · FreeCAD/FreeCAD](https://github.com/FreeCAD/FreeCAD/issues/6092)
- [0003771: Memory leak in Part.Face.Surface — FreeCAD Tracker](https://tracker.freecad.org/view.php?id=3771)
- [FreeCAD: Memory debugging (SrcDocu)](https://free-cad.sourceforge.net/SrcDocu/d4/d30/group__MemDebug.html)
- [OCCT Foundation Classes — memory manager / Standard::Purge](https://dev.opencascade.org/doc/occt-6.7.0/overview/html/user_guides__foundation_classes.html)
- [Standard_MMgrOpt Class Reference — OCCT](https://dev.opencascade.org/doc/occt-7.0.0/refman/html/class_standard___m_mgr_opt.html)
- [FreeCAD documentation — Start up and Configuration (FreeCADCmd / --console)](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Start_up_and_Configuration.md)
- [spkane/freecad-addon-robust-mcp-server — releases (60s FreeCAD startup timeout)](https://github.com/spkane/freecad-addon-robust-mcp-server/releases)
- [Python docs — multiprocessing (maxtasksperchild, spawn/fork)](https://docs.python.org/3/library/multiprocessing.html)
- [Python's Multiprocess Pool Memory Leak (maxtasksperchild)](https://blog.konpat.me/dev/2016/11/08/pythons-multiprocess-pool-memory-leak.html)
- [multiprocessing.pool memory growing: causes and fixes](https://www.pythontutorials.net/blog/memory-usage-keep-growing-with-python-s-multiprocessing-pool/)
- [Gunicorn — Design (pre-fork, arbiter, worker recycling, SIGCHLD)](https://gunicorn.org/design/)
- [Rippling's Gunicorn pre-fork journey (warm workers, memory)](https://www.rippling.com/blog/rippling-gunicorn-pre-fork-journey-memory-savings-and-cost-reduction)
- [Overcoming the cold-start challenge with Gunicorn workers (warm pools)](https://www.scoutapm.com/blog/overcoming-the-cold-start-challenge-with-gunicorn-workers-in-python-in-django)
- [Windows Job Objects process management (memory limit, kill-on-close)](https://langgrant.com/blog/docker-windows/)
- [Limit process memory on Linux with cgroups and earlyoom — Raymii.org](https://raymii.org/s/articles/Limit_specific_process_memory_on_desktop_linux_with_cgroups.html)
- [Fix: Linux OOM Killer killing processes — FixDevs](https://fixdevs.com/blog/linux-oom-killer/)
- [CadQuery via FreeCAD cmd — Google Groups (subprocess isolation, OCCT)](https://groups.google.com/g/cadquery/c/DBpfRCfn1Bg)
