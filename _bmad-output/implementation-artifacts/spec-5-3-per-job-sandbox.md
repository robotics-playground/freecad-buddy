---
title: 'Story 5.3: Per-Job Sandbox'
type: 'feature'
created: '2026-09-15'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '_bmad-output/implementation-artifacts/epic-5-context.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/security-and-service-design.md'
  - 'benchmarks/g4/THREATS.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Story 5.2 made a job killable, but not contained. A Phase 4 job spec is fully
untrusted input with no human in the loop, and today a worker can open a socket, read any file
the operator can read, and write anywhere. `OOM_KILLED` currently names a status with nothing
enforcing it from outside the process.

**Approach:** Add `run_job_in_sandbox`, one internal API over two backends, and run the worker
inside it. The Linux backend builds the jail from namespaces and resource limits the kernel
already offers unprivileged — an empty network namespace, a mount namespace whose only writable
path is the job directory, a user namespace with an unprivileged uid, and `setrlimit` caps. The
Windows backend uses the Job Object story 5.2 already owns, extended with memory and CPU limits.

## Boundaries & Constraints

**Always:**
- Egress is denied by default. The worker needs no network at all — spec intake and result
  delivery both live in the supervisor — so an empty network namespace costs zero functionality
  and removes the exfiltration threat class outright.
- `jobs/<id>/` is the only writable path. Everything else the worker can see is read-only.
- The worker runs GPU-none, through the offscreen software path.
- A control that cannot be applied on this host is REPORTED, never silently skipped. A sandbox
  that quietly degraded to nothing would let an uncontained run be reported as contained.
- Every containment claim this story makes is backed by a test that would fail if the control
  were removed. A jail asserted only by inspection is a jail nobody has checked.
- The status vocabulary stays the closed set from `contracts/status.py`. This story adds no
  status and edits no contract.

**Never:**
- Do not require `bwrap`, `nsjail`, or Docker. Measured on this host: neither `bwrap` nor
  `nsjail` is installed, and cgroup2 creation under `/sys/fs/cgroup/unified` is permission-denied
  unprivileged. A sandbox that depends on them is untestable here and in any CI without them.
- Do not claim seccomp or cgroup containment that is not applied. Both are hardening layers this
  story detects and uses WHEN available, and honestly reports as absent otherwise.
- Do not change the pool's kill path, the status map, or the supervisor's validation. Those are
  story 5.2's and they pass.
- Do not build the job API or the designer payload. Story 5.4 owns both.
- Do not treat in-process Python restriction as a boundary. The only boundaries are the typed-tool
  architecture and the OS jail.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Egress attempt | Worker opens a socket to any host | Connection fails; job resolves on its own terms | Denied by empty netns, not by policy check |
| Write outside job dir | Worker writes to a path outside `jobs/<id>/` | Write fails, read-only filesystem | Refused by the mount namespace |
| Write inside job dir | Worker writes `jobs/<id>/exports/part.step` | Write succeeds | No error expected |
| Memory cap breach | Worker allocates past its cap | Allocation refused or process killed; `OOM_KILLED` | Cap enforced from outside the payload |
| CPU cap breach | Worker burns past its CPU budget | Process killed; resolves to a closed-set status | Never a silent overrun |
| Sandbox unavailable | Host cannot apply a requested control | Job refused, or run with the gap REPORTED | Never silently uncontained |
| Windows host | Job submitted on Windows | Runs under the Job Object backend with its limits | Same status vocabulary both OSes |
| Nested control absent | cgroup2 not delegated | Falls back to rlimit backstop, records which applied | Degradation is visible, not silent |

</intent-contract>

## Code Map

Anchors verified on this branch at `71074ba`.

**Story 5.2's machinery this story extends — do not rewrite it:**
- `src/freecad_buddy/hosts/phase4/pool.py` — `WorkerPool._spawn` builds the command and takes
  ownership of the tree. The sandbox wraps the COMMAND here; the kill path stays untouched.
- `src/freecad_buddy/hosts/phase4/tree_kill.py:41` `spawn_kwargs`, `:160` `JobHandle` — the
  Windows Job Object already exists and already kills a tree. Its `_ExtendedLimits` structure
  already carries `ProcessMemoryLimit` and `JobMemoryLimit` fields that are declared and unused;
  the Windows backend sets them rather than building a second primitive.
- `src/freecad_buddy/hosts/phase4/resource_limits.py:31` `apply(limits)` — already applies
  `RLIMIT_AS` and `RLIMIT_CPU` inside the worker, already no-ops on Windows. The Linux backend
  keeps it as the per-process backstop and adds the namespace layer around it.
- `src/freecad_buddy/hosts/phase4/status_map.py:63` `resolve` — `Outcome.memory_exceeded` already
  maps to `OOM_KILLED`. The sandbox is what finally SETS that flag from an observed cap breach.
- `src/freecad_buddy/contracts/job.py` `JobLimits` — `wall_deadline_s`, `memory_bytes`,
  `cpu_time_s` already exist. No contract change needed.

**Measured facts about this host and CI — the constraints the design must fit:**
- CI is `ubuntu-latest` in all three workflows (`.github/workflows/{ci,canary,gate-exit}.yml`), so
  the Linux backend is the one CI exercises.
- WSL2 Ubuntu, kernel `5.15.167.4-microsoft-standard-WSL2`, Python 3.12.3.
- `unshare -Ur` succeeds: **user namespaces work unprivileged.**
- `unshare -Urn` then a DNS lookup reports `blocked`: **an empty network namespace denies egress**,
  measured rather than assumed.
- `setrlimit(RLIMIT_AS)` then a 512 MB allocation raises `MemoryError`: **memory caps are
  enforced.**
- `mkdir /sys/fs/cgroup/unified/<name>` is **permission denied** unprivileged, so cgroup limits
  are a detect-and-use layer, not a dependency.
- `bwrap` and `nsjail` are **absent**; only `unshare` is present.

**Read-only evidence:**
- `grep` for `run_job_in_sandbox` returns hits only in planning documents — zero in `src/`,
  `tests/`, `benchmarks/`. This story creates it.
- `benchmarks/g4/THREATS.md` records that the `oom/` leg asserts the status mapping only, and
  that proving the kill came from a sandbox rather than the host OOM killer needs this story.
  That limit is discharged here, and the file must be updated to say so.

## Tasks & Acceptance

**Execution:**
- `src/freecad_buddy/hosts/phase4/sandbox.py` -- create `run_job_in_sandbox(command, job_dir,
  limits)` plus a `SandboxReport` naming which controls were APPLIED and which were UNAVAILABLE --
  one API keeps the supervisor OS-agnostic, and reporting the gap is what stops an uncontained run
  from being read as a contained one.
- `src/freecad_buddy/hosts/phase4/sandbox_linux.py` -- the Linux backend: wrap the worker command
  so it runs with an empty network namespace, a mount namespace whose only writable path is the
  job directory, an unprivileged user namespace, and the existing rlimit caps; detect cgroup2
  delegation and use it for the memory cap when available, falling back to `RLIMIT_AS` otherwise
  -- the namespace layer is the containment the rlimits alone cannot provide, and detection is
  what keeps it honest on a host that denies cgroup creation.
- `src/freecad_buddy/hosts/phase4/sandbox_windows.py` -- the Windows backend: set
  `ProcessMemoryLimit` and per-job CPU time on the Job Object story 5.2 already creates, and
  record that network isolation is NOT applied on this backend -- the Job Object gives real memory
  and CPU containment; claiming egress denial it does not enforce would be the silent gap this
  story exists to prevent.
- `src/freecad_buddy/hosts/phase4/job_dir.py` -- create and own the `jobs/<id>/` layout (`spec.json`,
  `exports/`, `renders/`, `validation.json`, `audit.log`, `worker.stderr.log`) with the supervisor
  creating and cleaning it -- the job directory is the sandbox's only writable mount, so its shape
  is part of the containment rather than a convention.
- `src/freecad_buddy/hosts/phase4/pool.py` -- route `_spawn` through `run_job_in_sandbox` and carry
  the `SandboxReport` onto the run -- the pool is where a worker becomes a process, so it is the
  one place the jail can be applied without duplicating spawn logic.
- `src/freecad_buddy/hosts/phase4/supervisor.py` -- attach the sandbox report to the resolved
  `JobStatus` and set `Outcome.memory_exceeded` when the backend observed a cap breach -- the
  status map already turns that flag into `OOM_KILLED`; until something sets it, the mapping is
  unreachable.
- `benchmarks/g4/THREATS.md` -- update the "what this suite does NOT measure" section: the
  sandbox now exists, so state precisely which controls are enforced on which backend and what
  remains unproven -- the file's current text says proving sandbox-sourced `OOM_KILLED` needs this
  story, and leaving that standing after the story lands would misreport the gate.
- `tests/external/test_phase4_sandbox.py` -- test every I/O matrix row against the REAL sandbox:
  egress denied, writes outside the job directory refused, writes inside allowed, memory cap
  enforced, an unavailable control reported rather than skipped -- test naming is
  `Should <outcome> When <condition>` with `// Arrange`/`// Act`/`// Assert` phases, and each
  containment test must fail if its control is removed.

**Acceptance Criteria:**
- Given a job running under the Linux backend, when its payload attempts any outbound connection,
  then the connection fails and the sandbox report records egress as denied.
- Given a job running under the Linux backend, when its payload writes to a path outside
  `jobs/<id>/`, then the write fails, and a write inside `jobs/<id>/` succeeds.
- Given a memory cap, when a payload allocates past it, then the job resolves `OOM_KILLED` and the
  report attributes the cap to the control that enforced it.
- Given a host that cannot apply a requested control, when a job runs, then the sandbox report
  names that control UNAVAILABLE and the job is never reported as fully contained.
- Given a Windows host, when a job runs, then it is contained by the Job Object's memory and CPU
  limits, and the report states that network isolation is not applied on this backend.
- Given story 5.2's tests, when this story's changes land, then all of them still pass unchanged:
  the kill path, the status map, and the queue bound are not this story's to alter.

## Design Notes

**Why namespaces and rlimits rather than bwrap or nsjail.** The design names nsjail or bubblewrap
for the Linux jail, with a hardened OCI container as the CI-reproducibility alternative. Measured
on this host, neither binary is installed and cgroup2 creation is permission-denied unprivileged.
A sandbox built on them would be untestable here and in any CI that lacks them, which would make
every containment claim an assertion rather than a measurement. The kernel features they wrap —
user, mount and network namespaces — are reachable unprivileged and verified working, so the
backend uses those directly and treats the external tools as an optional hardening layer. The
posture the design fixes is unchanged; only the mechanism is narrower and provable.

**What is contained, and what is not.** Egress denial and the read-only filesystem are real
kernel-enforced boundaries. Memory and CPU caps are enforced, but through `setrlimit` when cgroup
delegation is unavailable, which stops an honest runaway rather than a determined one — a process
can lower its own soft limits. Seccomp is not applied. These are exactly the distinctions that
must reach `THREATS.md` rather than living in a commit message, because the gate cites that file.

**The Windows backend contains less, and says so.** A Job Object gives real memory and CPU limits
and an atomic tree kill, but no network isolation. The design's answer is WSL2 running the Linux
stack; that is a deployment decision, not something this story can assert on an arbitrary Windows
host. So the Windows backend reports egress as UNAVAILABLE rather than claiming a control it does
not apply.

## Verification

**Commands:**
- `uv run pytest tests/external/test_phase4_sandbox.py -q` -- expected: all pass.
- `uv run pytest tests/external/test_phase4_supervisor.py -q` -- expected: story 5.2's 32 tests
  still pass unchanged.
- `uv run pytest tests/external -q` -- expected: 1514 pre-existing tests still pass, plus the new
  ones.
- `uv run python scripts/check_imports.py` -- expected: `check_imports OK`, with the sandbox
  modules added to the FreeCAD-free set.
- `uv run python benchmarks/runner.py faults G4` -- expected: the G4 bars still met.
- `uv run ruff check src/freecad_buddy/hosts/phase4 tests/external/test_phase4_sandbox.py` --
  expected: clean.

**Manual checks (if no CLI):**
- Under WSL, run a payload that attempts a DNS lookup and confirm it fails inside the sandbox
  while succeeding outside it. A containment test that passes because the network was down
  anyway proves nothing.
