---
title: 'Make the declared marshal timeout real on the headless host (DW-22)'
type: 'bugfix'
created: '2026-07-30'
status: 'done'
baseline_revision: '1658cb2905fd731189869dbc142437486261eedd'
review_loop_iteration: 1
followup_review_recommended: true
context: []
warnings: []
---

<intent-contract>

## Intent

**Problem:** `hosts/headless/entry.py:73` builds `Marshal(InlineExecutor())`, and `InlineExecutor.submit` (`adapters/marshal.py:28-29`) calls `fn()` synchronously. By the time `Marshal.call` reaches `done.wait(timeout_s)` (`marshal.py:64`) the event is already set, so the timeout branch is dead code on H1. A `debug_exec` body that sleeps or loops forever therefore hangs the whole stdio server: no `TIMEOUT` envelope, no interrupt, no further tool calls served. It is worse than one lost call — `debug_exec` runs its `exec` inside `DocumentRegistry.with_document`, which holds a non-reentrant `threading.Lock` (`usecases/documents.py:100,121-125`) shared by all 16 `with_document` call sites, so the abandoned body also wedges every subsequent document tool.

**Approach:** Give the headless host a bounded executor that runs the submitted callable on a worker thread, so the existing `done.wait(timeout_s)` actually blocks and a budget overrun raises `MarshalTimeout` — which `MethodRegistry.dispatch` (`adapters/rpc_dispatch.py:99-105`) already maps to a `TIMEOUT` envelope carrying `marshal_timeout`/`maybe_still_running`. Because a Python thread cannot be forcibly killed, the abandoned body may still be mutating the document, so the host must also mark the session document-suspect on timeout and refuse further mutations on that document until a read confirms state, exactly as `MarshalTimeout`'s docstring and the `RpcListener` gate (`adapters/rpc_listener.py:314-364`) already specify.

## Boundaries & Constraints

**Always:**
- The new executor lives in `adapters/marshal.py` beside `InlineExecutor` and is stdlib-only (no Qt, no third-party) — that module is imported by the headless host and must stay Qt-free at import time.
- Worker threads are daemon threads, so an abandoned body never blocks interpreter exit.
- `Marshal.call` semantics are unchanged: it still returns the callable's value, still re-raises the callable's exception on the caller thread, and still raises `MarshalTimeout` when the budget elapses. Only the executor changes.
- The `TIMEOUT` envelope reaching the client says the session is document-suspect: `detail.data` carries `marshal_timeout: true` and `maybe_still_running: true`, and the message states that the body may still be running and must not be blind-retried.
- After a timeout on a mutating tool the headless host refuses further **mutating** calls on that same `doc` handle with `INVALID_INPUT` until a non-mutating call on that handle returns `OK`. Reads are always allowed — a read is the sanctioned way to clear the flag. This mirrors `RpcListener._is_suspect`/`_mark_suspect`/`_update_suspect` semantics, including a `doc`-less call tracked as its own suspect slot.
- Audit before/after records are still written for mutating and `exec` calls, including on the timeout path and on a suspect-refusal.
- Ring discipline (AD-1) holds: `check_imports.py` stays green; nothing new is imported into `contracts/` or `usecases/`.
- Statuses stay inside the closed contract set — `TIMEOUT` and `INVALID_INPUT` are both already members; no new status, no new envelope shape.

**Block If:**
- Making the gate work requires changing `contracts/` (the envelope, the status set, or `detail.data`) — HALT `blocked`; the recorded DW-22 decision scopes this to host/adapter wiring.
- The only way to bound the exec body proves to require killing the thread, a subprocess, an interpreter-level interrupt, or `signal`-based preemption — HALT `blocked`; the decision explicitly accepts a still-running abandoned body plus the document-suspect marking, and rejects forcible termination.

**Never:**
- Do not change `InlineExecutor` itself or the GUI/RPC host's marshal semantics. `RpcListener` keeps its own `MarshalTimeout` handling and its own suspect set; `gui_addon`/`gui_external` wiring is untouched.
- Do not attempt to kill, interrupt, or `ctypes`-inject an exception into the worker thread, and do not add a thread pool that reuses a wedged worker for a later call.
- Do not change `usecases/debug_exec.py`'s exec semantics, its namespace, or its `with_document` lock usage; do not swap `DocumentRegistry._lock` for an `RLock` or add lock timeouts.
- Do not change any tool's declared `timeout_s`, nor add a new tool, wire field, or env flag.
- Do not edit `_bmad-output/implementation-artifacts/deferred-work.md`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Fast call under budget | callable returns in ≪ `timeout_s` | `Marshal.call` returns the value; no thread leak beyond the finished worker | No error expected |
| Callable raises | callable raises `ValidationError` | the same exception instance re-raised on the caller thread | Propagates as today (`dispatch` maps it to `INVALID_INPUT`) |
| Body exceeds budget | callable sleeps past `timeout_s` | `MarshalTimeout` raised at the budget; caller thread is released while the worker keeps running | `dispatch` → `TIMEOUT` envelope, `marshal_timeout` + `maybe_still_running` set |
| Timed-out `debug_exec` (mutating) | `debug_exec` body loops forever on `doc=D` | `TIMEOUT` envelope; `D` marked document-suspect | Envelope message names the suspect condition and the no-blind-retry rule |
| Mutating call on a suspect doc | `document_save` on `doc=D` after the above | `INVALID_INPUT` envelope naming the suspect state and telling the caller to run a read first | No dispatch, no marshal submit, no new worker thread |
| Read on a suspect doc | `query_tree_summary` on `doc=D` | dispatched normally; on `OK` the suspect flag on `D` is cleared | Ordinary dispatch error handling |
| Read on a suspect doc returns non-OK | read on `D` fails | flag stays set; the next mutation is still refused | Ordinary dispatch error handling |
| Timeout with no `doc` param | a `doc`-less mutating call times out | the `doc`-less suspect slot is set; per-handle flags are unaffected | Same as the doc case |
| Non-mutating call times out | a read exceeds its budget | `TIMEOUT` envelope; no suspect flag is set | A read cannot have corrupted the document |

</intent-contract>

## Code Map

- `src/freecad_buddy/adapters/marshal.py` -- `Executor` Protocol (l19-22), `InlineExecutor` (l25-29), `MarshalTimeout` (l32-37) whose docstring already states the document-suspect contract, `Marshal.call` (l50-68) with the dead `done.wait(timeout_s)` at l64. Home of the new executor.
- `src/freecad_buddy/hosts/headless/entry.py` -- l73 `marshal = Marshal(InlineExecutor())`, the host-wide marshal. This must STAY `InlineExecutor` (see Design Notes: AD-2 forbids off-main-thread FreeCAD calls). Also l75 `marshal.call(shim.warm_capability_probes, 30.0)`, which must stay on the main thread.
- `src/freecad_buddy/hosts/tool_catalog.py` -- `DEBUG_EXEC_SPEC` (l318-336) and `build_inline_handlers` (l588-651), whose `wrap` (l605-612) marshals every handler through the one host marshal. The bounded executor must reach `debug_exec` **only**, so the per-tool wrapping is where the second marshal goes. Its docstring (l7-11, l596-600) describes the inline no-op and needs updating for the exception.
- `src/freecad_buddy/adapters/mcp_server.py` -- `build_server._call_tool` (l97-118): the headless tool-call boundary. Resolves the method, audits before/after, calls `registry.dispatch`. Has no suspect gate today — this is where it must go for H1.
- `src/freecad_buddy/adapters/rpc_dispatch.py` -- `MethodRegistry.dispatch` (l90-110) already catches `MarshalTimeout` and returns the `TIMEOUT` envelope with `marshal_timeout`/`maybe_still_running` (l99-105). No change needed; confirms the timeout path is complete once the executor is threaded.
- `src/freecad_buddy/adapters/rpc_listener.py` -- `_handle_request` (l299-338), `_timeout_envelope` (l340-344), `_update_suspect`/`_is_suspect`/`_mark_suspect` (l346-364). The reference semantics to mirror; must stay untouched.
- `src/freecad_buddy/hosts/tool_catalog.py` -- `build_inline_handlers.wrap` (l605-612) wraps each handler in `marshal.call(..., spec.timeout_s)`, so `MarshalTimeout` surfaces *inside* `dispatch`. `DEBUG_EXEC_SPEC` (l318-336): `timeout_s=30.0`, `mutating=True`, `audit_event="exec"`.
- `src/freecad_buddy/usecases/documents.py` -- `DocumentRegistry._lock` (l100, non-reentrant) and `with_document` (l121-125). Explains the cascade: a wedged exec body holds this lock against all 16 `with_document` call sites. Read-only reference; do not change.
- `tests/external/test_mcp_surface.py` -- the H1 surface suite. `_registry()` (l71) builds via `build_registry(..., Marshal(InlineExecutor()))`; existing marshal tests at l320-331; `_call_tool_via_server` (l340-349) drives a built server through the real `tools/call` handler. Home for the new tests.
- `tests/external/test_rpc_client.py` -- l22-24 `ThreadedExecutor`, a test-local threaded executor. Precedent for the shape; the production one replaces it conceptually but this file stays as-is.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/adapters/marshal.py` -- add a `ThreadExecutor` (stdlib `threading` only) whose `submit(fn)` starts a daemon `threading.Thread` per submission and returns immediately, so `Marshal.call`'s `done.wait(timeout_s)` is the thing that blocks. Give it a docstring stating that an abandoned body keeps running (threads cannot be killed), that the caller must treat a timeout as document-suspect, and that it is for the operator exec path only because FreeCAD state must otherwise be touched on the main thread. Update the `Marshal` class docstring, which currently asserts "the wait never blocks" as if inline were the only executor.
- [x] `src/freecad_buddy/hosts/tool_catalog.py` -- wrap the `debug_exec` handler, and only that handler, in a second `Marshal(ThreadExecutor())` created inside `build_inline_handlers`, so the exec body is the one thing that runs off the main thread. Every other tool keeps going through the host's `InlineExecutor` marshal untouched. Wrap it beneath the existing `wrap(...)` so the outer inline `marshal.call` still runs (its wait is a no-op) and the inner bounded call is what enforces the 30 s budget and raises `MarshalTimeout`. When `marshal is None` (the listener path) leave `debug_exec` entirely alone — the GUI/RPC host bounds it through the Qt pump and must not gain a worker thread. Update the module and `build_inline_handlers` docstrings, which say every handler is a same-thread no-op.
- [x] `src/freecad_buddy/adapters/mcp_server.py` -- add the document-suspect gate to the `tools/call` boundary, mirroring `RpcListener` semantics: refuse a mutating call on a suspect `doc` with an `INVALID_INPUT` envelope before dispatching (still audited before/after); after dispatch, mark the `doc` suspect when a mutating call returned `TIMEOUT` with `marshal_timeout` set, and clear it when a non-mutating call on that `doc` returned `OK`. Track a `doc`-less slot separately. Reject a non-string `doc` as `INVALID_INPUT` rather than letting it key the suspect set. Keep the state per-server (created in `build_server`), not module-global, so tests and any second server do not share it. Record in a comment that the boundary is single-in-flight (AD-20 transport-level serialization), which is why the state needs no lock.
- [x] `src/freecad_buddy/adapters/mcp_server.py` -- ensure the `TIMEOUT` envelope's message tells the operator the body may still be running and must not be blind-retried. `dispatch` currently uses the raw `MarshalTimeout` text ("marshaled call exceeded 30.0s"), which carries the budget but not the suspect consequence; the flags are in `detail.data` but the human-readable line is what an operator reads first. Build the amended envelope defensively — do not subscript `detail` unguarded, since the sibling `_is_marshal_timeout` check already tolerates a missing/non-dict `detail` and an exception here would escape the `tools/call` boundary.
- [x] `src/freecad_buddy/adapters/mcp_server.py` -- state in the suspect-clearing path that a `query_*` read clears the flag, and reconcile `MarshalTimeout`'s docstring, which says "until a fingerprint check confirms state". A tree-summary read proves liveness, not geometry. Either weaken the docstring to match what is enforced or say plainly in the refusal message that the read is a liveness check; do not ship two adjacent strings promising different guarantees.
- [x] `tests/external/test_mcp_surface.py` -- add executor-level tests covering the marshal rows of the I/O matrix: a fast call returns its value, a raising callable re-raises the same exception on the caller thread, and a callable that blocks past a short budget raises `MarshalTimeout` promptly. Assert the elapsed wall time is close to the budget — a generous multiple of it, not a fixed several-second ceiling that a 20x regression would still satisfy — and assert the body had not finished, so a body that merely returns late cannot satisfy the test. Release any blocked body at test teardown so the suite leaks no live worker.
- [x] `tests/external/test_mcp_surface.py` -- add server-level tests covering the suspect rows: drive a built server via `_call_tool_via_server` with a stub registry whose mutating tool blocks past its budget, and assert (1) the call returns a `TIMEOUT` envelope rather than blocking, (2) a following mutating call on the same `doc` is refused `INVALID_INPUT` without reaching the handler, (3) a read on that `doc` returning `OK` clears the flag and the next mutation is dispatched again, (4) a read on a *different* `doc` does not clear it, (5) a timed-out non-mutating call sets no flag, and (6) a read that returns non-`OK` leaves the flag set — the I/O matrix row no test covered. Assert audit records are still written for the timeout and refusal paths.
- [x] `tests/external/test_mcp_surface.py` -- add a test that pins the scoping decision, since the previous attempt tested only hand-rolled stubs and left the actual wiring uncovered: build the real catalog via `build_inline_handlers` with exec enabled and an `InlineExecutor` marshal, and assert that a `debug_exec` body which overruns its budget returns/raises a timeout while a non-exec tool's handler is NOT wrapped in a threaded marshal. The point is to fail if someone later re-broadens `ThreadExecutor` to every tool.

**Acceptance Criteria:**
- Given the headless host and a `debug_exec` body that sleeps past its 30 s budget, when the tool is called, then the call returns a `TIMEOUT` envelope at the budget and the server continues serving subsequent tool calls — it does not hang.
- Given the new executor is reverted to `InlineExecutor` at the point the implementation actually wires it, when the new tests run, then the timeout tests fail — the tests are a genuine regression guard, not a tautology satisfied by a body that happens to return, and not sealed off from the production wiring by constructing their own threaded marshal.
- Given any tool other than `debug_exec`, when it is dispatched on the headless host, then its use case runs on the main thread through `InlineExecutor` — no FreeCAD or Coin call is moved onto a worker thread.
- Given a mutating tool timed out on document `D`, when any mutating tool is called on `D`, then it is refused with `INVALID_INPUT` naming the document-suspect state, and the underlying use case is never invoked.
- Given that refusal state, when a read on `D` returns `OK`, then the next mutating call on `D` is dispatched normally.
- Given the GUI/RPC host, when its tests run, then `RpcListener` behavior and `tests/external/test_rpc_listener.py` are unchanged — the fix is scoped to H1.
- Given `scripts/check_imports.py` runs, then it exits 0: the new executor adds no import that crosses a ring boundary.
- Given a callable that raises, when it is marshaled through the threaded executor, then the original exception instance surfaces on the caller thread with its traceback intact — error mapping in `dispatch` is unaffected.

## Spec Change Log

### 2026-07-30 — Review pass 1 (bad_spec)

**Triggering finding:** both reviewers independently argued that swapping the host-wide marshal to `ThreadExecutor` moves *every* tool off the main thread, not just `debug_exec`. Verified against the authoritative design rather than accepted on assertion. `ARCHITECTURE-SPINE.md` AD-2 (ADOPTED) states its purpose as "**Prevents:** background-thread FreeCAD/Qt calls (the documented crash mode)". `design/integration-mcp-freecad.md` adds the governing rule at l15 ("every call that reads or mutates FreeCAD state executes on the Qt main thread under the GIL"), specifies H1's topology at l25 as preventing "off-thread FreeCAD calls", documents `InlineExecutor` for H1 at l166/l225 ("headless: no Qt loop, already on main thread"; "`Marshal` is constructed with `InlineExecutor`"), and calls Coin GUI-thread-affine at l297. `build_inline_handlers` wraps all ~22 tools in the one host marshal, so the change put `OffscreenRenderPort` and every geometry mutation on per-call daemon threads. The failure mode traded for the hang is a segfault that kills the stdio server.

**What was amended:** the executor is now scoped to the `debug_exec` handler alone, wrapped in `hosts/tool_catalog.py` rather than swapped in `hosts/headless/entry.py`; the host marshal stays `InlineExecutor`. Added an acceptance criterion and a test task pinning the scope so a future change cannot silently re-broaden it, a defensive-construction requirement for the timeout envelope, a test for the uncovered "read returns non-OK" matrix row, a tightened wall-clock assertion, the docstring reconciliation for `MarshalTimeout`'s "fingerprint check" claim, and an explicit statement of the gate's limit (a true wedge is unclearable in-process because the recovery read blocks on the same lock).

**Known-bad state avoided:** shipping a green test suite whose 35 passing tests never touch the production wiring, while the real headless host runs Coin3D offscreen rendering and every FreeCAD mutation on arbitrary per-call threads in violation of an ADOPTED spine AD — turning an operator-only hang into an intermittent process-killing crash affecting all tools.

**Residual note (not amended):** the `<intent-contract>` says "the headless host refuses further mutating calls" and describes the executor at host level in its Approach paragraph. The block is read-only, so it stands as authored; the scoping to `debug_exec` is a strict narrowing that still satisfies the contract's stated intent (the declared `debug_exec` timeout becomes real, the session is marked document-suspect), and the DW-22 ledger decision names `debug_exec` as the subject throughout.

**KEEP instructions:** the following were correct and must survive re-derivation. `ThreadExecutor` itself — a per-call daemon thread, no pool — is the right primitive and its docstring shape is good. The `_SuspectDocuments` helper (per-server, created in `build_server`, separate `doc`-less slot, `is_suspect`/`mark`/`clear`) faithfully mirrors `RpcListener` and should be reused as-is. Marking only on a *mutating* `TIMEOUT` carrying `detail.data.marshal_timeout`, and clearing only on a *non-mutating* `OK` from a registered method, is the correct state machine. Extracting `_invalid_input_envelope` and having `_denied_exec_envelope` delegate to it removed real duplication — keep it. The `release` fixture (an event set at teardown so no worker leaks) and the `assert not release.is_set()` anti-tautology guard are both load-bearing; keep them. The audit-record assertions on the timeout and refusal paths are good and should be extended, not replaced.

## Review Triage Log

### 2026-07-30 — Review pass

- intent_gap: 0
- bad_spec: 1: (high 1, medium 0, low 0)
- patch: 0
- defer: 3: (high 0, medium 2, low 1)
- reject: 14: (high 0, medium 5, low 9)
- addressed_findings:
  - `[high]` `[bad_spec]` Swapping the host-wide marshal to `ThreadExecutor` moved all ~22 tools — including `OffscreenRenderPort` and every geometry mutation — onto per-call daemon threads, violating AD-2 (ADOPTED), whose stated purpose is preventing "background-thread FreeCAD/Qt calls (the documented crash mode)". Confirmed against the spine and `integration-mcp-freecad.md` (l15, l25, l166, l225, l297), not accepted on assertion. Spec amended to scope the bounded executor to the `debug_exec` handler in `hosts/tool_catalog.py`, leaving the host marshal inline; code reverted for re-derivation.

### 2026-07-30 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 2: (high 1, medium 0, low 1)
- defer: 3: (high 0, medium 2, low 1)
- reject: 12: (high 0, medium 3, low 9)
- addressed_findings:
  - `[high]` `[patch]` The non-string-`doc` rejection audited the raw value, writing schema-violating records into the append-only audit log. Reproduced against the real `build_server`/`AuditSink` and validated with `jsonschema`: a call with `doc: 7` produced two lines each failing `audit-record.schema.json` with `7 is not of type 'string' at ['doc','handle']`. `AuditSink._record` is typed `doc: str | None` and writes `{"handle": doc}` uncoerced; `rpc_listener.py:322` already does the `isinstance` coercion this path omitted. Fixed by auditing `None` for a rejected handle, and pinned by `test_rejected_doc_never_reaches_the_audit_log`, which validates every emitted record against the schema over four bad-handle shapes and fails against the unpatched code.
  - `[low]` `[patch]` `_with_suspect_message` told the operator "the document is now suspect: do not blind-retry, run a query_* read" on *every* marshal timeout, including non-mutating ones where no flag was set — contradicting the state machine and advising a read right after a read had timed out. Now takes `marked_suspect` and words the consequence to match, with the read case asserted by `test_timed_out_non_mutating_call_sets_no_suspect_flag`.

## Design Notes

The timeout path downstream of the executor is already complete — `dispatch` maps `MarshalTimeout` to `TIMEOUT` with both flags. The bug is one seam: `InlineExecutor.submit` runs `fn()` before `done.wait` is ever reached. A per-submission daemon thread is the minimum change that makes the existing wait real:

```python
class ThreadExecutor:
    def submit(self, fn: Callable[[], None]) -> None:
        threading.Thread(target=fn, daemon=True).start()
```

A per-call thread rather than a pool is deliberate: a pooled worker wedged by an abandoned body would silently starve later calls, reintroducing the hang this fixes.

**The executor must reach `debug_exec` and nothing else.** Swapping the host-wide marshal to `ThreadExecutor` moves all ~22 tools off the main thread, which AD-2 (ADOPTED) exists to prevent — it names "background-thread FreeCAD/Qt calls" as *the documented crash mode*. The integration design states the rule directly: "every call that reads or mutates FreeCAD state executes on the Qt main thread under the GIL"; H1's single-process topology is specified to prevent "off-thread FreeCAD calls"; `InlineExecutor` is documented for H1 as "no Qt loop, already on main thread"; and Coin is called out as GUI-thread-affine, so `OffscreenRenderPort` on a per-call worker risks a segfault that kills the stdio server — strictly worse than the hang being fixed. `debug_exec` is the operator-only bring-up path DW-22 names, and putting only it on a worker confines the accepted risk to the tool whose whole premise is already "trusted operator, off the typed path".

The gate has a real limit worth stating plainly: a wedged `debug_exec` body holds `DocumentRegistry._lock` forever, and the sanctioned recovery read goes through `with_document` too, so that read will itself block and time out rather than return `OK`. In the true wedge case the flag is therefore unclearable in-process and the operator must restart. The gate still earns its place — it converts an unbounded hang into a prompt, explicit refusal that names the cause — but it is a diagnosis, not a recovery. Do not describe it as one.

No lock is needed on the suspect state: the transport processes requests strictly sequentially, single in-flight call globally (AD-20 serialization at the transport layer). Note the assumption in a comment rather than adding synchronization that would imply concurrency the design forbids.

The suspect gate is required, not optional polish. `debug_exec` holds `DocumentRegistry._lock` for the whole `exec`, so an abandoned body keeps that non-reentrant lock forever. Without the gate, every later document call would submit a worker that blocks on the lock, time out, and leak another permanently-blocked thread — the client would see a stream of `TIMEOUT`s and the process would accumulate threads. With the gate, mutations are refused cheaply and the operator is told why.

Note the asymmetry with `RpcListener`: there the listener owns the single `marshal.call` and catches `MarshalTimeout` itself. On H1 the marshal is wrapped per-handler inside `build_inline_handlers`, so `MarshalTimeout` never escapes `dispatch` — the MCP boundary must detect the timeout from the returned envelope (`status == "TIMEOUT"` with `detail.data.marshal_timeout`) rather than from a raised exception.

## Verification

**Commands:**
- `python scripts/check_imports.py` -- expected: `check_imports OK`.
- `uv run ruff check src/freecad_buddy/adapters/marshal.py src/freecad_buddy/adapters/mcp_server.py src/freecad_buddy/hosts/tool_catalog.py tests/external/test_mcp_surface.py` -- expected: `All checks passed!`.
- `uv run ruff format --check src/freecad_buddy/adapters/marshal.py src/freecad_buddy/adapters/mcp_server.py src/freecad_buddy/hosts/tool_catalog.py` -- expected: already formatted.
- `uv run pytest tests/external/test_mcp_surface.py -q` -- expected: all pass, including the new timeout and suspect tests.
- `uv run pytest tests/external/test_rpc_listener.py tests/external/test_rpc_client.py tests/external/test_assistant_readonly_profile.py -q` -- expected: unchanged, still passing (GUI/RPC semantics untouched).
- `uv run pytest tests/external -q` -- expected: no new failures against the baseline; the suite must not hang (a hang means a worker thread is not a daemon or a test leaks a blocked body).

**Manual checks (if no CLI):**
- Temporarily remove the bounded wrapping from the `debug_exec` handler in `hosts/tool_catalog.py` and re-run the new tests: the timeout and suspect tests must fail. Restore afterward.
- Confirm the suite process exits promptly after `pytest` completes. A hang at exit means a worker thread was created non-daemon.
- Grep the diff for `ThreadExecutor`: it must appear in `adapters/marshal.py` (definition), `hosts/tool_catalog.py` (the `debug_exec` wrap), and tests — never in `hosts/headless/entry.py`, `hosts/gui_addon/`, or `hosts/gui_external/`.

## Auto Run Result

Status: done

### Implemented change

The declared `debug_exec` timeout is now real on the headless host. `InlineExecutor.submit` runs `fn()` synchronously, so `Marshal.call` reached `done.wait(timeout_s)` with the event already set and the timeout branch was dead code — an exec body that slept or looped hung the stdio server with no `TIMEOUT` and no interrupt. A new `ThreadExecutor` runs its callable on a per-submission daemon thread, so the existing wait is what decides the budget and `MethodRegistry.dispatch` maps the resulting `MarshalTimeout` onto the `TIMEOUT` envelope it already knew how to build.

The bounded executor is wired to the `debug_exec` handler alone, inside `build_inline_handlers`. The first implementation swapped the host-wide marshal in `hosts/headless/entry.py` instead, which moved all ~22 tools — Coin3D offscreen rendering included — onto worker threads in violation of AD-2 ("Prevents: background-thread FreeCAD/Qt calls (the documented crash mode)"). Review caught it, the code was reverted, and the spec was amended before re-derivation. `entry.py` is unchanged and still builds `Marshal(InlineExecutor())`.

Because a Python thread cannot be killed, an abandoned body may still be mutating, so the MCP `tools/call` boundary now keeps a per-server document-suspect set mirroring `RpcListener`: a mutating call that returns a marshal `TIMEOUT` marks its handle, further mutations on that handle are refused `INVALID_INPUT` naming the cause, and a non-mutating `OK` on the same handle clears it. The `TIMEOUT` message states the consequence rather than only the budget.

### Files changed

- `src/freecad_buddy/adapters/marshal.py` -- added `ThreadExecutor`; corrected the `Marshal` and `MarshalTimeout` docstrings, which claimed the wait never blocks and promised a fingerprint check the gate does not perform.
- `src/freecad_buddy/hosts/tool_catalog.py` -- `build_inline_handlers` builds one `Marshal(ThreadExecutor())` and applies it to the `debug_exec` spec only, beneath the existing inline `wrap`; untouched on the `marshal is None` listener path.
- `src/freecad_buddy/adapters/mcp_server.py` -- `_SuspectDocuments`, `_is_marshal_timeout`, `_with_suspect_message`, and the gate in `_call_tool`; extracted `_invalid_input_envelope` with `_denied_exec_envelope` delegating to it.
- `tests/external/test_mcp_surface.py` -- 15 tests: 3 executor-level, 10 gate-level, and 2 driving the real catalog through `build_inline_handlers` (one asserting the budget fires, one asserting via thread identity that `debug_exec` runs on a worker while a non-exec tool does not).

### Review findings

Two passes, four independent reviewers.

- Pass 1: 1 bad_spec (high) — the AD-2 thread-affinity violation. Code reverted, spec amended, implementation re-derived. 3 deferred, 14 rejected.
- Pass 2: 2 patches (1 high, 1 low) — schema-violating audit records for a rejected `doc` handle, and a timeout message that declared a document suspect when no flag had been set. Both fixed in place. 3 deferred, 12 rejected.

Six entries were appended to `deferred-work.md`; the DW-22 ledger entry itself was not touched.

### Verification

- `python scripts/check_imports.py` -- `check_imports OK`.
- `uv run ruff check` (4 changed files) -- `All checks passed!`.
- `uv run ruff format --check` (4 changed files) -- `4 files already formatted`.
- `uv run pytest tests/external/test_mcp_surface.py -q` -- `42 passed`.
- `uv run pytest tests/external -q` -- `388 passed, 4 warnings in 13.33s` (373 at baseline; +15, no regressions). Suite exits promptly, so no worker thread is non-daemon.
- Falsification, run directly rather than taken on report: replacing `if spec.name == "debug_exec":` with `if False:` fails `test_debug_exec_overrunning_its_budget_times_out_through_the_real_catalog` and `test_only_debug_exec_runs_off_the_main_thread`, and the run stretches from 0.9 s to 32.4 s — the hang itself. Restoring the raw `doc` in the audit calls fails `test_rejected_doc_never_reaches_the_audit_log` on a `jsonschema` `ValidationError`. Both guards are genuine.
- The pass-1 audit defect was reproduced independently against the real `build_server`/`AuditSink` before being accepted: `line 0: VIOLATION -> 7 is not of type 'string' at ['doc','handle']`, twice per rejected call.

Whole-tree `ruff check src tests` fails on 1 pre-existing E501 in `tests/external/test_check_imports.py`, identical at baseline. Not introduced here.

### Residual risks

- The gate is a diagnosis, not a recovery. A genuinely wedged `debug_exec` body holds `DocumentRegistry._lock` forever, so the sanctioned clearing read blocks on that same lock and times out instead of returning `OK` — in the true wedge case the operator must restart the process. Ledgered.
- `debug_exec` remains unbounded at the body level on the GUI/RPC host: the listener returns `TIMEOUT` to the client while the exec body keeps the Qt main thread. Unchanged from baseline and out of scope per the intent contract; ledgered with measurements.
- Each timed-out exec leaks one parked daemon thread, with no cap and no counter. Acceptable for an operator-only bring-up tool, but it degrades silently.
- The suspect gate is now duplicated between `mcp_server.py` and `rpc_listener.py`, and their operator-facing messages already differ. Ledgered as a consolidation task.
- The doc-less suspect slot is cleared by any successful doc-less read, including `query_capabilities`, which confirms nothing. Mirrors existing `RpcListener` behavior; ledgered so both hosts can be fixed together.
