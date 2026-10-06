---
title: 'Headless host: bounded execution and AD-27 quarantine'
type: 'bugfix'
created: '2026-10-05'
status: 'draft'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The headless H1 host bounds only `debug_exec`. Every other tool runs inline on the asyncio thread through `Marshal(InlineExecutor())`, so its registry `timeout_s` is never enforced: a 130 s `verify_recompute` returned `OK` (TC-10-11). After a `debug_exec` `TIMEOUT`, the abandoned body still holds the `DocumentRegistry` lock, so the next call blocked 11.3 s (F-33). This is Story 10.6 goal A (AC1, AC2).

**Approach:** H1 adopts the GUI thread model. FreeCAD runs on the process main thread, which pumps a job queue. The MCP stdio server runs on a background thread and submits each call through `Marshal.call(fn, spec.timeout_s)`, so every tool's budget is real. While a timed-out body still runs, the session is quarantined: each new call returns `TIMEOUT` at once, without dispatch, and without waiting on any lock. The quarantine lifts by itself when the body returns.

**Decisions (human, 2026-10-06):**
- D1 — Quarantine is session-wide (AD-27): every call is refused while an abandoned body runs, on any handle. No wait may be unbounded:
  - each refusal returns at once;
  - when the abandoned body has run its own `timeout_s` again past its timeout (2× budget in total), refusals change from `TIMEOUT` to `WORKER_CRASHED` with a message that tells the operator to restart the headless host (AD-27 escalation); if the body returns later, the quarantine still lifts;
  - when the stdio server ends while a body still runs, the host waits at most 5 s for the pump, then logs once and exits with code 1, so the process never hangs after its client is gone.
- D2 — A timed-out mutation that completes later keeps its commit, as today (TC-10-10). The document stays suspect until a read confirms it. The AD-27 "aborted with rollback proved" clause is deferred work, for both hosts.

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

## Code Map

- `src/freecad_buddy/adapters/marshal.py:26-87` -- `InlineExecutor`, `ThreadExecutor`, `MarshalTimeout`, `Marshal.call`. Add the main-thread queue executor here (stdlib only) and the in-flight tracking of abandoned bodies.
- `src/freecad_buddy/hosts/headless/entry.py:74-108` -- `run()`: today `Marshal(InlineExecutor())` and `asyncio.run(serve_stdio(server))` on the main thread. Restructure: run the warm-up on the main thread, start the server thread, then pump on the main thread.
- `src/freecad_buddy/hosts/tool_catalog.py:1441-1512` -- `build_inline_handlers`: `wrap` (outer marshal) and `bound_off_main_thread` (inner `ThreadExecutor` for `debug_exec` only). The inner bound becomes redundant.
- `src/freecad_buddy/adapters/rpc_dispatch.py:122-140` -- `dispatch` maps `MarshalTimeout` to `TIMEOUT` with `marshal_timeout`/`maybe_still_running`. Add the quarantine mapping (`quarantined:true`, no `marshal_timeout`).
- `src/freecad_buddy/adapters/rpc_listener.py:336-343` -- GUI listener's own `marshal.call` and `except MarshalTimeout` suspect marking. Do not change; the reason the refusal lives in `wrap`.
- `src/freecad_buddy/adapters/mcp_server.py:123-148,174-228` -- `_is_marshal_timeout`, `_with_suspect_message`, the suspect set. Reuse as is: a refusal without `marshal_timeout` must pass through untouched.
- `src/freecad_buddy/usecases/documents.py:331-380` -- `DocumentRegistry._lock` (the F-33 lock). Do not change.
- `src/freecad_buddy/adapters/render_probe.py:181-188,191-215` -- `OffscreenRenderPort` creates a `QGuiApplication` on first use. It must stay on the main thread, which is why the pump stays on the main thread.
- Callers of `Marshal(InlineExecutor())`: `tests/external/test_mcp_surface.py:109,430,435,844`, `test_confirm_contract.py:37,243-272`, `test_assistant_readonly_profile.py:132`. Keep `InlineExecutor` for these unit tests.
- `tests/external/test_mcp_surface.py:509-541` -- `ThreadExecutor` tests. Remove them with `ThreadExecutor` if it becomes unused.
- Design: `integration-mcp-freecad.md` §2.4, §3.3, §4.1, §7 (marshal-timeout and busy rows).

## Tasks & Acceptance

**Execution:**
- [ ] `src/freecad_buddy/adapters/marshal.py` -- add `MainThreadQueueExecutor` (`submit` enqueues; `pump(stop)` runs jobs on the calling thread until `stop` is set). `Marshal` records, for a call it abandoned, the completion event, the budget and the time of the timeout, and exposes `abandoned_body()` returning `None` once the body has returned, else whether it has run past 2× its budget; `Marshal.call` itself does not refuse. Add `SessionQuarantined(escalated: bool)` (not a `MarshalTimeout` subclass). Remove `ThreadExecutor` if it has no caller left. -- one source of bounded execution.
- [ ] `src/freecad_buddy/adapters/rpc_dispatch.py` -- map `SessionQuarantined` to `TIMEOUT` (or `WORKER_CRASHED` when `escalated`) with `quarantined:true`, `maybe_still_running:true` and a message saying the call was not dispatched (escalated: restart the headless host). -- the suspect set must not fire on a refusal.
- [ ] `src/freecad_buddy/hosts/tool_catalog.py` -- drop `bound_off_main_thread`. Every handler goes through the one `wrap`, which raises `SessionQuarantined` before `marshal.call` while `marshal.abandoned_body()` is not `None`. -- `debug_exec` is now bounded like every tool; only H1 passes a `marshal`, so the GUI path is untouched.
- [ ] `src/freecad_buddy/hosts/headless/entry.py` -- warm-up on the main thread, then start `serve_stdio` on a daemon thread that sets `stop` when it ends, then `executor.pump(stop)`. When `stop` is set while a job runs, a watchdog waits 5 s for the pump, then logs once at ERROR and calls `os._exit(1)` (D1). -- FreeCAD and Qt stay on the main thread; the process never outlives its client.
- [ ] `tests/external/test_marshal_quarantine.py` (new) -- with the queue executor and a pumping thread: under budget returns; overrun raises `MarshalTimeout`; next call raises `SessionQuarantined(escalated=False)` in < 1 s without running; past 2× budget it is `escalated=True`; after the body ends, calls run again. A pump test: `stop` set while a job blocks makes the watchdog call an injected exit hook. `tests/external/test_mcp_surface.py` -- a dispatch-level test that a refusal envelope carries `quarantined:true`, and through `build_server` a refusal on a mutating tool marks no suspect.
- [ ] `tests/infc/` -- an H1 stack test under FreeCAD: a `verify_recompute` whose recompute overruns a reduced budget returns `TIMEOUT`, the next call is refused, and calls serve again after the body ends. A real FreeCAD body on the pumped main thread.
- [ ] `integration-mcp-freecad.md` -- §4.1 thread model; §2.4/§7 quarantine semantics; §3.3 executor list. -- design must match code.

**Acceptance Criteria:**
- Given the H1 host and any tool, when the body overruns the registry `timeout_s`, then the envelope is `TIMEOUT` within `timeout_s` + 1 s (TC-10-11).
- Given a `debug_exec` that timed out, when the next call arrives while the body runs, then it is refused in under 1 s and never waits on the registry lock (F-33).
- Given an abandoned body that never returns, when calls keep arriving, then each returns at once, and after 2× its budget they return `WORKER_CRASHED` (D1).
- Given the H1 host started over stdio, when a client sends `initialize`, `tools/list` and `query_capabilities`, then each returns as before (thread change is invisible).

## Design Notes

Thread layout, mirroring GUI mode (`integration-mcp-freecad.md` §3.3):

```
main thread:   warm-up -> executor.pump(stop)        # all FreeCAD + Qt work
server thread: asyncio.run(serve_stdio(server))      # MCP stdio; Marshal.call waits bounded
               finally: stop.set()
```

`Marshal` is the only object that knows a body was abandoned, so it tracks the state; the refusal is raised by the H1 `wrap` (`build_inline_handlers` with a `marshal`). The refusal is not raised inside `Marshal.call`: the GUI listener (`rpc_listener.py:338-343`) also calls `Marshal.call` and catches `MarshalTimeout` to mark the document suspect, so a refusal there would mark a document for a call that never ran. `SessionQuarantined` is not a `MarshalTimeout` subclass for the same reason. The GUI host keeps its queued-behind behaviour.

## Verification

**Commands:**
- `uv run pytest tests/external -q` -- expected: all pass.
- fcb env `python tests/infc/run_tests.py` -- expected: all pass, including the H1 overrun test.
- `uv run ruff check src tests && uv run python scripts/check_imports.py` -- expected: clean.

**Manual checks:**
- Run H1 over stdio with a 130 s recompute document: `TIMEOUT` at ~120 s, the next call is refused at once, and a call after the body returns gets `OK`.
