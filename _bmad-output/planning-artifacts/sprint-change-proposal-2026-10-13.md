---
title: 'Sprint Change Proposal: two-process headless host'
date: '2026-10-13'
author: TanNT
scope: Moderate
status: approved
---

# Sprint Change Proposal: two-process headless host

## 1. Issue Summary

Story 10.6 AC1 (TC-10-11) requires that any headless tool returns `TIMEOUT` when its body runs past
its registry `timeout_s`. Planning of `spec-10-6-headless-bounded-execution.md` found that a
single-process host cannot meet this for every body.

**Evidence:**

- FreeCAD App code never releases the Python GIL (global interpreter lock: only one thread runs
  Python at a time). `PyGILStateRelease` occurs only in `src/Base/Interpreter.h`,
  `src/Mod/MeshPart/App/AppMeshPartPy.cpp` and `src/Mod/Sandbox`, and never in `src/App` or
  `src/Mod/Part/App` (`docs/references/FreeCAD/`).
- So a long pure-C++ body (an OCC boolean, a C++ recompute) holds the GIL for its full run. Every
  other thread in that process stops: the thread that waits on the budget, the thread that must
  refuse new calls, and any watchdog.
- The UAT fixture for TC-10-11 sleeps in a `FeaturePython` `execute()`
  (`tests/uat/run/2026-10-03-04/evidence/tc10_slowfeat.py:15`). `time.sleep` releases the GIL, so
  that fixture does not show the limit. A real model would.
- GUI mode does not have this problem: the MCP proxy is a separate process, and its
  `RpcClient` socket read timeout (`rpc_client.py:26`, `_DEFAULT_READ_TIMEOUT_S = 130.0`) runs
  outside FreeCAD.

**Issue type:** technical limit found during planning.

### Decisions (human, 2026-10-13)

Recorded in the Story 10.6 spec frozen block:

- **D3** — The bound must hold for any body. H1 splits into two processes: a front MCP stdio
  process and a FreeCAD worker process, connected by the existing RPC wire.
- **D4** — The change goes through this proposal first. Story 10.6 is re-planned after it.
- **D5** — Past 2× budget the front returns `WORKER_CRASHED` and tells the operator to restart the
  host. The front never kills the worker on escalation, so no open document is lost.
- **D6** — The worker runs in the same interpreter as the front (`sys.executable`) and imports
  FreeCAD as a module. Offscreen render keeps working. It is not `FreeCADCmd`.
- **D7** — The change may edit the shared RPC code (`rpc_listener.py`, `rpc_client.py`,
  `gui_external/entry.py`) if GUI behaviour stays the same and the existing GUI tests prove it.

## 2. Impact Analysis

### Checklist

| Item | Status | Finding |
|------|--------|---------|
| 1.1 Trigger story | [x] | Story 10.6 goal A (AC1, AC2) |
| 1.2 Problem | [x] | Technical limit: a GIL-holding body defeats any in-process bound |
| 1.3 Evidence | [x] | Section 1 |
| 2.1 Current epic | [!] | Epic 10 can finish; Story 10.6 needs a topology story first |
| 2.2 Epic changes | [!] | Add Story 10.6a; amend Story 10.6 AC1 and the sequencing line |
| 2.3 Future epics | [x] | Epic 4 (paused) and Phase 3+ use H1 over stdio only; the CLI does not change |
| 2.4 Obsolete or new epics | [N/A] | None |
| 2.5 Order | [!] | 10.6a before 10.6 |
| 3.1 PRD (`SPEC.md`) | [x] | No conflict. CAP-1 says "identically in-GUI and headless" (`SPEC.md:21`); the agent still reaches tools only through MCP (`SPEC.md:121`) |
| 3.2 Architecture | [!] | AD-2, AD-27; design §1, §2.4, §3.2, §4.1, §4.2, §7; component-design, sequence-diagrams, project-structure |
| 3.3 UX | [N/A] | No UX documents |
| 3.4 Other | [!] | `AGENTS.md:439` and `CLAUDE.md:439` say "single-process H1"; `epics.md:38` FR6 |
| 4.1 Direct adjustment | Viable | Effort Medium-High, risk Medium |
| 4.2 Rollback | Not viable | No completed story needs a revert |
| 4.3 MVP review | Not needed | Scope and gates do not change |

### Epics and stories

- **Story 10.6** keeps goal A (AC1, AC2: bounded execution and AD-27 quarantine), now implemented in
  the front process. Goals B, C and D stay in `deferred-work.md` as before.
- **New Story 10.6a** builds the two-process topology with no behaviour change. It is a separate
  story because it is independently shippable and testable: every existing H1 test must pass on
  it before the bound is added. One spec for both would exceed the spec size limit.
- **Story 1.4** (done) uses `serve --transport stdio --mode inline`. The command does not change.

### Architecture

| Area | Change |
|------|--------|
| AD-2 | Headless = front MCP process + FreeCAD worker child process over RPC, not a single process |
| AD-27 | On H1 the front, not the listener, quarantines the session, because only the front sees the timeout |
| AD-3 | No change. The worker RPC hop uses a per-session token, as GUI mode does |
| AD-12 | No change. The worker imports stdlib + FreeCAD only, although `mcp` is installed in the same interpreter |
| AD-26 | No change. The front is the only RPC client of its worker |
| AD-29 | No change. H1 still has no live viewport (`ARCHITECTURE-SPINE.md:266`) |

### Code (Story 10.6a and Story 10.6)

- `hosts/headless/entry.py` becomes the front. It spawns the worker and serves MCP over stdio.
- New `hosts/headless/worker.py` builds the registry and runs `RpcListener.serve_forever_inline()`
  on its main thread with `Marshal(InlineExecutor())`.
- `RpcClient` gets a read timeout per call (D7). The GUI proxy keeps its fixed 130 s.
- The worker must not write the GUI discovery file. Otherwise a GUI proxy could connect to the
  headless worker.
- Unit tests that build the registry in-process (`test_confirm_contract.py`, `test_mcp_surface.py`)
  do not change.

### CI and harness

The `headless` and `render` CI legs and `scripts/automation/run_mcp_*.py` launch H1 through the CLI.
The CLI does not change, so they need no edit. They are the regression check for Story 10.6a.

## 3. Recommended Approach

**Direct adjustment.** Add Story 10.6a for the topology and re-plan Story 10.6 on top of it.

- **Effort:** Medium-High. Most parts exist: `RpcListener.serve_forever_inline`
  (`rpc_listener.py:160`), `RpcClient`, and the proxy registry (`gui_external/entry.py:95`).
  New work: worker spawn and token handoff, front lifecycle, per-call timeout, and the quarantine.
- **Risk:** Medium. A child process on Windows and Linux CI; stdout must stay clean on the stdio
  path (AD-3); every H1 user (CI, UAT, harness) depends on it.
- **Timeline:** one more story in Epic 10 before 10.6. 10.7b and 10.8 move behind it.

## 4. Detailed Change Proposals

### 4.1 `ARCHITECTURE-SPINE.md` — AD-2 (line 53)

OLD (excerpt):

> Headless mode = single process, tool core called inline (no Qt loop exists); where the external
> interpreter cannot `import FreeCAD`, the documented fallback is the GUI topology minus Qt —
> `FreeCADCmd`-hosted RPC listener with inline dispatch.

NEW:

> Headless mode = two processes: a front MCP process (stdio, no `import FreeCAD`) and a FreeCAD
> worker child process that it spawns with its own interpreter. The worker runs the RPC listener
> with inline dispatch on its main thread (no Qt loop exists). The front is the worker's only
> client, authenticates with a per-session token it generates, and ends the worker when it exits.
> The process boundary is what makes a call budget real: FreeCAD never releases the GIL during a
> C++ operation, so no thread inside the FreeCAD process can time it out. Where the interpreter
> cannot `import FreeCAD`, the worker may run under `FreeCADCmd` instead; that variant is not
> built.

Add to **Prevents:** "a C++ body that holds the GIL making a call budget unenforceable".

### 4.2 `ARCHITECTURE-SPINE.md` — AD-27 (line 249)

OLD: "On timeout the listener marks the session **quarantined**:"

NEW: "On timeout the process that observed it marks the session **quarantined** — the listener in
GUI mode, the front process in headless mode:"

### 4.3 `design/integration-mcp-freecad.md`

- **§1 Topology table, H1 row** (line 22). OLD: "Single process: MCP server + usecases + `import
  FreeCAD` as module (conda env) | Direct in-proc call, inline". NEW: "Front MCP process (stdio) +
  worker child process (same interpreter, `import FreeCAD` as module) | RPC → worker listener,
  inline dispatch on the worker main thread".
- **§1 H2 row and paragraph** (lines 23, 25). NEW: H2 is the H1 topology with `FreeCADCmd` as the
  worker interpreter, for an interpreter that cannot `import FreeCAD`. Not built.
- **§2.4 Timeouts.** Add row: "Call timeout, H1 front: method `timeout_s` (the bound; the worker's
  inline marshal never times out)". Add the quarantine paragraph: refusal `TIMEOUT` with
  `quarantined:true`; `WORKER_CRASHED` past 2× budget; lifts when the worker answers again.
- **§3.2 `serve_forever_inline` docstring** (line 171). OLD: "Headless H2". NEW: "Headless worker".
- **§4.1** rewritten: front and worker roles, spawn, token handoff (not through the discovery file,
  which belongs to GUI mode), worker exit when the front exits (grace 5 s, then the front ends it),
  audit written by the worker listener as in GUI mode, quarantine and document-suspect state held
  by the front, mesh-verify oracle legs run in the front (AD-9).
- **§4.2** reduced to the `FreeCADCmd` worker variant.
- **§7 Failure modes.** Add rows: "Worker process exits" → `WORKER_CRASHED`, no restart, operator
  restarts the host; "Call while a timed-out body runs (H1)" → refusal per AD-27; "Body past 2×
  budget (H1)" → `WORKER_CRASHED` escalation.

### 4.4 Other design documents

- `design/component-design.md:95` — OLD: "Headless entry: single process where FreeCAD is
  importable (conda env); runs `mcp_server` on stdio, use-cases called inline through the marshal's
  degrade path (AD-2)." NEW: "Headless front: runs `mcp_server` on stdio and spawns the FreeCAD
  worker (`worker.py`: RPC listener, inline dispatch) (AD-2)."
- `design/sequence-diagrams.md:38` — OLD: "one in-process hop when headless". NEW: "Front →
  Listener when headless".
- `design/sequence-diagrams.md:126-127` — OLD: "Headless (`FreeCADCmd`) is the same diagram with
  Proxy, Listener and Marshal collapsed: one process, `InlineExecutor`, use cases called inline."
  NEW: "Headless is the same diagram: the front is the Proxy, the worker hosts the Listener, and the
  Marshal is inline on the worker main thread."
- `design/project-structure.md:90-91` — add `worker.py  # headless FreeCAD worker: RPC listener,
  stdlib + FreeCAD only` under `headless/`; `entry.py` comment becomes "headless front: MCP stdio,
  spawns the worker".

### 4.5 `epics.md`

- **FR6** (line 38). OLD: "single-process headless, and FreeCADCmd-hosted RPC fallback". NEW:
  "headless (front MCP process + FreeCAD worker process), with a `FreeCADCmd` worker as the
  fallback".
- **Epic 10 sequencing** (line 1218). Add: "10.6a -> 10.6 (10.6 bounds calls in the front that
  10.6a builds)".
- **Story 10.6 AC1** (line 1340). OLD: "**Given** any tool in the headless host". NEW: "**Given**
  any tool in the headless host, including a body that holds the GIL in C++".
- **New Story 10.6a: Two-Process Headless Host**, before Story 10.6:

  > **As** an operator, **I want** the headless host to run FreeCAD in a worker process, so that
  > the host can bound any call (AD-2, AD-27).
  >
  > 1. **Given** `freecad-buddy serve --transport stdio --mode inline` **When** it starts **Then**
  >    it spawns one worker with the same interpreter; the front has not imported `FreeCAD` and the
  >    worker has not imported `mcp` (AD-12).
  > 2. **Given** an MCP client **When** it runs `initialize`, `tools/list` and the existing H1
  >    suites (`tests/external`, `scripts/automation/run_mcp_e2e.py`) **Then** the envelopes and the
  >    audit records are the same as on the single-process host.
  > 3. **Given** the front ends (stdin EOF) **When** the worker is idle **Then** both exit with code
  >    0; **When** the worker is still busy after 5 s **Then** the front ends it, logs once at
  >    ERROR and exits with code 1.
  > 4. **Given** the worker exits **When** the next call arrives **Then** it returns
  >    `WORKER_CRASHED` with a message to restart the host; the front does not restart it.
  > 5. **Given** a FreeCAD GUI bridge on the same machine **When** the headless host runs **Then**
  >    the worker writes no discovery file and the RPC hop requires the session token (AD-3).
  > 6. The `headless` and `render` CI legs pass, and the GUI tests pass unchanged (D7).

### 4.6 `AGENTS.md:439` and `CLAUDE.md:439`

OLD: "it uses the single-process H1 stdio host, not this proxy." NEW: "it uses the H1 stdio host (a
front process that spawns its own FreeCAD worker), not this proxy."

### 4.7 Story 10.6 spec — `spec-10-6-headless-bounded-execution.md`

Re-plan with `bmad-build` after Story 10.6a is done. The frozen **Approach** paragraph and the
"stdin EOF" rows of the I/O matrix describe the single-process thread model; D3 supersedes them.
The human rewrites them at the re-plan checkpoint. The EOF behaviour moves to Story 10.6a AC3.

### 4.8 `sprint-status.yaml`

- Add `10-6a-two-process-headless-host: backlog` above `10-6-session-transport-and-bounded-execution`.
- Epic 10 ordering comment: add "10-6a -> 10-6 (sprint-change-proposal-2026-10-13: 10-6 bounds
  calls in the front that 10-6a builds)".

## 5. Implementation Handoff

**Scope: Moderate.** It changes an architecture decision and adds one story, but it changes no
gate, no PRD requirement and no MVP scope. TanNT approves as architect and product owner.

| Step | Owner | Deliverable |
|------|-------|-------------|
| 1 | Developer (this workflow) | Apply 4.1–4.6 and 4.8 after approval |
| 2 | Developer, `bmad-build` | Story 10.6a: spec, implementation, review |
| 3 | Developer, `bmad-build` | Re-plan and build Story 10.6 (4.7) |

**Success criteria:**

- On H1, a body that holds the GIL in C++ and overruns its budget returns `TIMEOUT` within
  `timeout_s` + 1 s (Story 10.6 AC1, measured with a C++ body, not only a sleep).
- Every existing H1 suite and both CI legs pass on the two-process host.
- GUI tests pass with no change to their expectations.
