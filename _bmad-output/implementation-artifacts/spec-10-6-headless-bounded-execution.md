---
title: 'Headless host: bounded execution and AD-27 quarantine'
type: 'bugfix'
created: '2026-10-13'
status: 'draft'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The headless H1 host bounds only `script_exec`. Every other tool runs inline on the asyncio thread through `Marshal(InlineExecutor())`, so its registry `timeout_s` is never enforced: a 130 s `verify_recompute` returned `OK` (TC-10-11). After a `script_exec` `TIMEOUT`, the abandoned body still holds the `DocumentRegistry` lock, so the next call blocked 11.3 s (F-33). This is Story 10.6 goal A (AC1, AC2).

**Approach:** H1 adopts the GUI thread model. FreeCAD runs on the process main thread, which pumps a job queue. The MCP stdio server runs on a background thread and submits each call through `Marshal.call(fn, spec.timeout_s)`, so every tool's budget is real. While a timed-out body still runs, the session is quarantined: each new call returns `TIMEOUT` at once, without dispatch, and without waiting on any lock. The quarantine lifts by itself when the body returns.

**Decisions (human, 2026-10-06):**
- D1 — Quarantine is session-wide (AD-27): every call is refused while an abandoned body runs, on any handle. No wait may be unbounded:
  - each refusal returns at once;
  - when the abandoned body has run its own `timeout_s` again past its timeout (2× budget in total), refusals change from `TIMEOUT` to `WORKER_CRASHED` with a message that tells the operator to restart the headless host (AD-27 escalation); if the body returns later, the quarantine still lifts;
  - when the stdio server ends while a body still runs, the host waits at most 5 s for the pump, then logs once and exits with code 1, so the process never hangs after its client is gone.
- D2 — A timed-out mutation that completes later keeps its commit, as today (TC-10-10). The document stays suspect until a read confirms it. The AD-27 "aborted with rollback proved" clause is deferred work, for both hosts.
- D3 (human, 2026-10-13) — The bound must hold for any body, including a pure-C++ body that holds the Python GIL. FreeCAD App code never releases the GIL, so a thread in the FreeCAD process cannot enforce it. H1 therefore splits into two processes: a front MCP stdio process and a FreeCAD worker process over the RPC wire. This supersedes the single-process thread model in **Approach** and reverses AD-2 "headless = single process".
- D4 (human, 2026-10-13) — D3 goes through `bmad-correct-course` first: a sprint change proposal amends AD-2 and integration design §1, §4.1 and §4.2. This spec is re-planned against the amended design.
- D5 (human, 2026-10-13) — Escalation stays as D1 states: past 2× budget the front returns `WORKER_CRASHED` and tells the operator to restart the host. The front never kills the worker, so no open document is lost.
- D6 (human, 2026-10-13) — The worker runs in the same interpreter as the front (`sys.executable`) and imports FreeCAD as a module, so offscreen render keeps working. It is not `FreeCADCmd`.
- D7 (human, 2026-10-13) — D3 may change the shared RPC code (`rpc_listener.py`, `rpc_client.py`, `gui_external/entry.py`) to reuse it for H1, if GUI behaviour stays the same and the existing GUI tests prove it. This replaces the first **Never** rule below for those modules only.

## Boundaries & Constraints

**Always:**
- FreeCAD and Qt are touched only on the process main thread. No two FreeCAD calls ever run at once.
- A quarantine refusal dispatches nothing, marks no document suspect, and returns in well under 1 s.
- The existing document-suspect rule (a mutating `TIMEOUT` marks its `doc`; a non-mutating `OK` on that `doc` clears it) stays unchanged after the body returns.
- No call is ever retried automatically (AD-27).

**Never:**
- No change to the GUI host, `rpc_listener.py` or `gui_external/entry.py` (goals B, C, D are deferred).
- No thread pool and no killing of threads.
- No new environment variable or flag.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Under budget | any tool, body ends before `timeout_s` | envelope as today | N/A |
| Read overrun | `verify_recompute`, body 130 s, budget 120 s | `TIMEOUT`, `marshal_timeout:true`, `maybe_still_running:true`, wording `no mutation was attempted…` | doc not suspect |
| Mutation overrun | mutating tool overruns | `TIMEOUT`, wording `the document is now suspect…` | doc suspect |
| Call during abandoned body | any tool, any `doc` | `TIMEOUT`, `detail.data.quarantined:true`, no `marshal_timeout`, message says not dispatched | handler never runs |
| Body runs past 2× budget | any call, body still running | `WORKER_CRASHED`, `quarantined:true`, message says restart the host | handler never runs |
| Body returns | next call after abandoned body ends (also after escalation) | served normally | suspect rule applies |
| stdin EOF, pump idle | server thread ends | process exits 0 | log once at INFO |
| stdin EOF, body running | server thread ends, pump busy > 5 s | process exits 1 | log once at ERROR |

</frozen-after-approval>

## Implementation Notes

## Spec Change Log

## Review Triage Log
