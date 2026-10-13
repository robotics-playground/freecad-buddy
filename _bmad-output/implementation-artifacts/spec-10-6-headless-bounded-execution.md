---
title: 'Headless host: bounded execution and AD-27 quarantine'
type: 'bugfix'
created: '2026-10-13'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'f040f5e79335cb5a45ecf186b90fd388ced62a2d'
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md'
  - '{project-root}/_bmad-output/planning-artifacts/sprint-change-proposal-2026-10-13.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The headless H1 host bounds only `script_exec`. Every other tool runs inline on the asyncio thread through `Marshal(InlineExecutor())`, so its registry `timeout_s` is never enforced: a 130 s `verify_recompute` returned `OK` (TC-10-11). After a `script_exec` `TIMEOUT`, the abandoned body still holds the `DocumentRegistry` lock, so the next call blocked 11.3 s (F-33). This is Story 10.6 goal A (AC1, AC2).

**Approach:** The headless front (Story 10.6a) bounds every call: it waits for the worker's reply for at most the method `timeout_s`. On a timeout it returns `TIMEOUT` and quarantines the session: each new call returns at once, without dispatch, and without waiting on any lock. The front probes the worker; the quarantine lifts when the worker answers, which proves the body returned. The worker runs every body, `script_exec` included, on its main thread.

**Decisions (human, 2026-10-06):**
- D1 — Quarantine is session-wide (AD-27): every call is refused while an abandoned body runs, on any handle. No wait may be unbounded:
  - each refusal returns at once;
  - when the abandoned body has run its own `timeout_s` again past its timeout (2× budget in total), refusals change from `TIMEOUT` to `WORKER_CRASHED` with a message that tells the operator to restart the headless host (AD-27 escalation); if the body returns later, the quarantine still lifts;
  - The `stdin EOF` behaviour is Story 10.6a AC3.
- D2 — A timed-out mutation that completes later keeps its commit, as today (TC-10-10). The document stays suspect until a read confirms it. The AD-27 "aborted with rollback proved" clause is deferred work, for both hosts.
- D3 (human, 2026-10-13) — The bound must hold for any body, including a pure-C++ body that holds the Python GIL. FreeCAD App code never releases the GIL, so a thread in the FreeCAD process cannot enforce it. H1 therefore splits into two processes: a front MCP stdio process and a FreeCAD worker process over the RPC wire. This supersedes the single-process thread model in **Approach** and reverses AD-2 "headless = single process".
- D4 (human, 2026-10-13) — D3 goes through `bmad-correct-course` first: a sprint change proposal amends AD-2 and integration design §1, §4.1 and §4.2. This spec is re-planned against the amended design.
- D5 (human, 2026-10-13) — Escalation stays as D1 states: past 2× budget the front returns `WORKER_CRASHED` and tells the operator to restart the host. The front never kills the worker, so no open document is lost.
- D6 (human, 2026-10-13) — The worker runs in the same interpreter as the front (`sys.executable`) and imports FreeCAD as a module, so offscreen render keeps working. It is not `FreeCADCmd`.
- D7 (human, 2026-10-13) — D3 may change the shared RPC code (`rpc_listener.py`, `rpc_client.py`, `gui_external/entry.py`) to reuse it for H1, if GUI behaviour stays the same and the existing GUI tests prove it. This replaces the first **Never** rule below for those modules only.
- D8 (human, 2026-10-13) — At the re-plan after Story 10.6a, the **Approach**, D1's third bullet and the `stdin EOF` rows were rewritten for the two-process host (sprint-change-proposal-2026-10-13 §4.7).

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

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/hosts/headless/entry.py` -- `WorkerClient.call` (dead worker: `WORKER_CRASHED` "restart the headless host"), `shut_down_worker`, `run()` builds `RpcClient(endpoint=…, read_timeout_s=None)`. The bound and quarantine go into `WorkerClient`.
- `src/freecad_buddy/adapters/rpc_client.py:24-26,160-235` -- `_HELLO_TIMEOUT_S = 5.0`; `_ensure_connected` connects lazily and handshakes; `call` turns `socket.timeout` into `_timeout_envelope("listener read timed out")` with `marshal_timeout: False` and closes the socket. The socket read timeout is fixed at connect time.
- `src/freecad_buddy/adapters/rpc_listener.py:232-260,273-315` -- `_accept_loop` serves one connection at a time on the worker main thread, so a hello reply on a new connection proves the previous body returned.
- `src/freecad_buddy/adapters/mcp_server.py:181-211,262-286` -- `_is_marshal_timeout` needs `detail.data.marshal_timeout: true`; then `build_server` marks a mutating call's `doc` suspect and `_with_suspect_message` writes the `no mutation was attempted…` / `the document is now suspect…` wording. Reuse; do not change.
- `src/freecad_buddy/hosts/rpc_proxy.py` -- `build_proxy_registry` calls `client.call(name, params)`; mesh verifiers call `export_self_read_stl|3mf`. `RpcMethod.timeout_s` holds each tool's budget.
- `src/freecad_buddy/hosts/tool_catalog.py:1487-1583` -- `build_inline_handlers(…, marshal, …)`: with a `marshal`, `script_exec` runs on a `Marshal(ThreadExecutor())` thread (`:1521`, `:1533-1541`, `:1547`), so after its `TIMEOUT` the worker serves the next call while the abandoned body holds the `DocumentRegistry` lock (F-33). With `None` (the GUI, `gui_addon/bootstrap.py:144`) every body runs inside the listener's single `marshal.call`. Self-read legs have `timeout_s=120.0` (`:1578`). Do not change.
- `src/freecad_buddy/hosts/headless/worker.py:52-65,112` -- `run()` calls `build_registry(DocumentRegistry(), caps, marshal)`. Keep the `build_registry` signature: `test_confirm_contract.py` and `test_mcp_surface.py` call it and must not change (proposal §2 Code).
- Tests: `test_headless_two_process.py` has the subprocess, stub-worker and stdio patterns.
- Design: `integration-mcp-freecad.md` §2.4 "H1 bound and quarantine" paragraph (`:84`) and §7 rows state the target; the §2.4 table has no H1 front row yet (proposal §4.3).

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/adapters/rpc_client.py` -- let a caller give a per-call read timeout and probe a reconnect without blocking on the hello; GUI callers and defaults unchanged (D7).
- [x] `src/freecad_buddy/hosts/headless/entry.py` -- `WorkerClient` bounds each call to the method budget (proxy registry `timeout_s`; a self-read leg uses its verify tool's budget). On timeout: return `TIMEOUT` with `marshal_timeout: true`, `maybe_still_running: true`, and quarantine. While quarantined: dead worker first (existing message); past 2× budget `WORKER_CRASHED`, `quarantined: true`, message says restart the headless host; else `TIMEOUT`, `quarantined: true`, no `marshal_timeout`, message says not dispatched. Probe with at most one pending hello connection; lift on its answer, also after escalation. Never kill the worker on escalation (D5).
- [x] `src/freecad_buddy/hosts/headless/worker.py` -- `run()` passes `None` to `build_registry`, so the listener's inline marshal is the only one and `script_exec` runs on the main thread, as in GUI mode. Signature unchanged.
- [x] `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md` §2.4 table -- add row `Call (read) timeout, H1 front | method timeout_s | the bound; the worker's inline marshal never times out`.
- [x] `tests/external/` -- no change to `test_confirm_contract.py` or `test_mcp_surface.py`. New tests per matrix row, against a real `RpcListener` in a child process whose stub method holds the GIL in C (for example a catastrophic `re` backtrack), with sub-second budgets. Under FreeCAD (`needs_freecad`), over stdio: a `script_exec` body that spends its time in FreeCAD C++ calls (for example repeated `Part` booleans until a deadline past 30 s) returns `TIMEOUT` within 31 s, the next call is refused in under 1 s, and a call after the body returns is served (F-33).

**Acceptance Criteria:**
- Given a body that holds the GIL in C++ on the headless host, when it overruns its budget, then `TIMEOUT` arrives within `timeout_s` + 1 s (proposal §5).
- Given a quarantine, when the body returns, then the next call reaches the worker and the document-suspect rule applies as before.
- Given the GUI tests and the in-process registry tests (`test_confirm_contract.py`, `test_mcp_surface.py`), when they run, then they pass unchanged.

## Implementation Notes

- `RpcClient.reconnect_answered()` holds one non-blocking probe connection; its answered connection becomes the client socket. `call(..., read_timeout_s=)` overrides the read timeout for one call. `rpc_proxy.call_budgets()` maps each method to its `timeout_s`; self-read legs take their verify tool's budget.
- A mutating call on a document already suspect gets `build_server`'s `INVALID_INPUT` document-suspect refusal, even during a quarantine, because `build_server` checks suspect before dispatch. Both refuse without dispatch.
- After an abandoned body returns, the worker listener logs `frame read failed` / `failed to write frame` because the front closed that connection. Harmless; Story 10.6 AC5 (log levels) owns it.

## Spec Change Log

## Review Triage Log

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | `call_budgets()` untested; a missing key makes `WorkerClient.call` raise `KeyError` (blind, edge-case, verification-gap) | medium | No test calls `call_budgets()`; the stub tests pass a hand-written `BUDGETS`. Deleting the self-read loop breaks headless `verify_export_stl|3mf` (`_invoke` maps `KeyError` to `INVALID_INPUT`) and CI stays green. | patch |
| 2 | Tests wait a fixed 0.3 s for the probe answer; a call made just after the body returns can still be refused once (blind, edge-case) | medium | `_wait_until_returned` sleeps 0.3 s after the `returned` marker; on a slow runner the hello reply can arrive later and three tests fail. | patch |
| 3 | FreeCAD stdio test hardcodes the 30 s budget and never checks that the created document survived (D5) | low | `budget_s = 30.0` duplicates `SCRIPT_EXEC_SPEC.timeout_s`; `served` checks only `status`. Direct fix. | patch |
| 4 | Escalation message says only "restart the headless host" | low | A restart ends the worker and loses unsaved documents; the quarantine still lifts if the body returns (test at `test_headless_two_process.py:642-661`). Wording fix. | patch |
| 5 | `worker.build_registry` docstring first line says each handler is marshaled; production now passes `None` | low | Direct docstring correction. | patch |
| 6 | `script_exec` `ThreadExecutor` path and the `build_inline_handlers` docstring ("headless inline host") now describe a configuration no host runs; `test_mcp_surface.py` "real catalog" test pins it | low | Accepted by Design Notes (proposal keeps those tests unchanged); Code Map says `tool_catalog.py` does not change. | defer |
| 7 | Audit pair for a quarantine refusal records `TIMEOUT` with no `quarantined` marker | low | `build_server` writes status only, as for every refusal; recovery after a refused mutation is the same query plus fingerprint as after a real timeout, so the record errs toward caution. Fix needs an audit field and a `build_server` change. | reject |
| 8 | Rejected probe hello is read as "body still running" | false | The probe uses the same token and `contract_version` that the first connection already passed; a rejection cannot happen while the worker is the same process. | reject |
| 9 | Probe `create_connection` can block 2 s | low | The worker listens with `listen(1)` and one probe at most is pending, so connect completes from the backlog; a refused connect means a dead worker, which `process.poll()` catches first. | reject |
| 10 | `read_timeout_s=None` means "no timeout" in the constructor and "client default" in `call` | low | Docstring states the per-call meaning; no caller needs an unbounded per-call read. | reject |
| 11 | Third hand-built envelope (`entry._envelope`); escalated `WORKER_CRASHED` lacks `data.rpc` | low | Shape matches the contract; no reader keys on `data.rpc` for escalation. | reject |
| 12 | First connect plus hello (up to 7 s) sits outside the budget | low | The front opens a fresh connection only when the worker is idle (start, or after the probe answered), so the hello returns at once. | reject |
| 13 | A worker-side `TIMEOUT` would be rewritten as a read timeout | false | With `marshal=None` and an inline listener marshal, no worker path raises `MarshalTimeout` (`rpc_dispatch.py:146-152` is the only `TIMEOUT` producer). | reject |

## Design Notes

The worker's serve loop is single-threaded, so the probe needs no new RPC method: the front connects and sends `rpc_hello`; the kernel queues the connection, and the reply arrives only after the abandoned body returns and the loop accepts again. Keep that one connection pending and check it without blocking on each refused call. A fresh probe per call would queue stale connections in the listen backlog.

With `None` from the worker, the `script_exec` `ThreadExecutor` path in `build_inline_handlers` has no production host; only the in-process tests reach it. It stays, because the proposal keeps those tests unchanged.

`build_server` keeps its suspect rule because the front's own `TIMEOUT` carries `marshal_timeout: true`; a refusal carries none, so it marks nothing suspect.

## Verification

**Commands:**
- `uv run pytest tests/external -q` -- expected: all pass.
- `fcb` env (`PYTHONPATH=<env>\Library\bin`): `python -m pytest tests/external/test_headless_two_process.py tests/external/test_rpc_listener.py tests/external/test_rpc_client.py tests/external/test_gui_external_proxy.py -q -rA` -- expected: pass, FreeCAD tests not skipped.
- `fcb` env: `freecadcmd tests/run_tests.py` and `score_g3_replay.py --leg 1.1.x --run local --check --frames-check benchmarks/g3/fault-injection/frames-reference.json` -- expected: pass.
- `uv run ruff check . && uv run python scripts/check_imports.py` -- expected: clean.
