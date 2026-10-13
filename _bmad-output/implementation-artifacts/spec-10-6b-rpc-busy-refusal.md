---
title: 'Story 10.6 goal B: a second RPC client gets the AD-26 busy refusal'
type: 'bugfix'
created: '2026-10-13'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'efadc0125ad2ec37632b8e12bc9b321a153bbd77'
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** AD-26 says the bridge serves one client session at a time and refuses a second client that presents the token with `-32000` and a busy detail. The listener has no busy path: `_accept_loop` accepts, then serves that connection on the same thread until it closes, with `listen(1)`. A second client queues in the backlog and gets no frame, or on Windows its connect is refused with `WinError 10061`, which looks the same as "bridge not running" (TC-99-03, TC-10-03, Story 10.6 AC3). A connection that never sends its hello also holds the only slot for as long as it stays open.

**Approach:** The listener accepts on its own thread at all times and runs the handshake there, with a deadline. A connection that authenticates while no session is active becomes the session and is served as today, on the serving thread (the Qt-marshaling listener thread in GUI mode, the worker main thread in headless mode). A connection that authenticates while a session is active gets `-32000` with the message `bridge busy: another client session is active` and is closed. The session ends when its connection closes.

## Boundaries & Constraints

**Always:**
- Authentication and the version check run before the busy check, so an unauthenticated caller learns nothing about the session (`auth failed` stays first).
- Calls still run one at a time, through the same `marshal.call`, on the same thread as today.
- The headless front's quarantine probe keeps working: a busy reply means the abandoned body has not returned yet.

**Never:**
- No multi-client mode, and no new environment variable, flag or CLI option.
- No change to the `-32000` code, the RPC `contract_version`, or the status vocabulary.
- No idle timeout for an authenticated session.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First client | valid hello, no session | hello `result`; calls served as today | N/A |
| Second client | valid hello while a session is active | `-32000`, `bridge busy: another client session is active`, connection closed, in under 1 s | session undisturbed |
| Second client, bad token | wrong token while a session is active | `-32000` `auth failed` | as today |
| Session ends | first client closes | next client's hello succeeds | N/A |
| Silent connection | connects, sends nothing | closed after the hello deadline; logged once at WARNING | other clients not blocked |
| Busy proxy | `RpcClient` hello gets the busy error | `WORKER_CRASHED`, message names the busy condition | no retry |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/adapters/rpc_listener.py:145-190` -- `bind` (`listen(1)`), `start_threaded` (one daemon thread runs `_accept_loop`), `serve_forever_inline` (accept loop on the caller thread), `stop`. `:232-268` `_accept_loop` / `_serve_conn`: accept, handshake, serve until close, then accept again. `:286-322` `_handshake`: reads the hello with no deadline, checks token then version, writes the result through `_write_frame`. Calls, suspect state and audit (`:324+`) do not change.
- `src/freecad_buddy/contracts/rpc.py:17` -- `RPC_ERROR_WORKER_CRASHED = -32000`; reuse it for busy.
- `src/freecad_buddy/adapters/rpc_client.py` -- `_ensure_connected` sets `_connect_error = "handshake rejected"` for any hello error; `reconnect_answered` treats any non-`result` reply as "not yet" and closes the probe (the headless quarantine path, `hosts/headless/entry.py` `WorkerClient`).
- `src/freecad_buddy/hosts/headless/worker.py` -- calls `listener.bind()` then `serve_forever_inline()` on the main thread; a stdin-EOF thread calls `stop()`.
- `src/freecad_buddy/hosts/gui_addon/bootstrap.py:175` -- `listener.start_threaded()`; no change.
- Tests: `tests/external/test_rpc_listener.py` (`Conn`, `_start_listener`, `ThreadedExecutor`, the connection-end logging tests and `_after_handler_returned`, which relies on one connection at a time); `tests/external/test_headless_two_process.py` (quarantine tests on a stub worker).
- UAT: `tests/uat/testcases/TC-10-concurrency-timeout-and-quarantine.md` TC-10-03 pins the old "B waits" behaviour; `tests/uat/testcases/TC-99-ad-conformance-gaps.md` TC-99-03 lists the busy refusal as a gap.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/adapters/rpc_listener.py` -- an accept thread that always accepts, runs the handshake with a 5 s hello deadline (the client's `_HELLO_TIMEOUT_S`), and either hands the connection to the serving loop or writes the busy error and closes it. The serving loop runs on the daemon thread in `start_threaded` and on the caller in `serve_forever_inline`, and serves one session at a time. `stop()` ends both. A session is active from its hello reply until its serving loop returns.
- [x] `src/freecad_buddy/adapters/rpc_client.py` -- when the hello reply is the busy error, set the connect error to the busy message so the envelope names it.
- [x] `tests/external/test_rpc_listener.py` -- a test per matrix row; adjust `_after_handler_returned` if the one-connection assumption no longer holds.
- [x] `tests/external/test_headless_two_process.py` -- the quarantine tests still pass; add one where the probe gets a busy reply while the abandoned body runs, and the quarantine lifts after it returns.
- [x] `tests/uat/testcases/TC-10-concurrency-timeout-and-quarantine.md` (TC-10-03), `tests/uat/testcases/TC-99-ad-conformance-gaps.md` (TC-99-03) -- expect the busy refusal.
- [x] `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md` §3.2 and the §7 "FreeCAD busy" row -- the accept thread, the hello deadline and the busy refusal.

**Acceptance Criteria:**
- Given the GUI addon with its proxy connected, when a second client sends a valid hello, then it gets the busy refusal in under 1 s and the FreeCAD window stays responsive (cua-driver screenshot).
- Given the headless host, when the G3 replay and the two-process tests run, then they pass.

## Implementation Notes

- Probe: the Design Note assumed no answer while an abandoned body runs. A body that loops in Python around C++ calls lets the accept thread answer `busy` between calls, and that answer is stale by the next call. When a probe is refused, `RpcClient.reconnect_answered` opens a new probe and waits `_PROBE_REASK_WAIT_S = 0.1` for its answer. The fcb FreeCAD bound test failed without it.
- `_BUSY_GRACE_S = 0.2`: the accept thread waits this long for the old session to end before it refuses; without it a client that reconnects right after closing its own session was refused about 1 run in 25.
- The client recognises busy by `RPC_BUSY_MESSAGE` (new in `contracts/rpc.py`), because `-32000` is shared with `auth failed`.
- UAT: TC-10-03 expects the busy refusal; TC-99-03 is removed under the TC-99 promotion rule, with references updated in `coverage-matrix.md`, `test-plan.md`, `APPENDIX-A-deferred-coverage.md`. Design §1, §2.3, §2.4, §3.2, §3.4, §7 updated; AD-26 added to its `ad-refs`.
- A silent connection delays other handshakes by up to 5 s, because the handshake runs on the accept thread.
- AC1 verified on FreeCAD 1.1.4 (junction install, relaunched on the new code, pid 31496) with the proxy holding the session: a valid second hello got `-32000` `bridge busy: another client session is active` in 0.203 s and the connection closed; a wrong token got `auth failed`; the proxy's `document_list` still returned `OK`; `addon.log` has one INFO and one WARNING line, no traceback; the window screenshot shows the Start page fully painted, no `Not Responding`, no modal.

## Spec Change Log

## Review Triage Log

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | `_idle.clear()` before the hello reply is built; an exception there refuses every later client as busy (blind, edge-case) | low | `_handshake` clears `_idle` then calls `_write_frame`; only a False return restores it. Trigger is unlikely; the fix moves one line. | patch |
| 2 | A client admitted while `stop()` runs is queued after the sentinel and never served or closed (blind, edge-case) | low | `_accept_loop` never checks `_stop` after an admitted handshake. Two-line guard. | patch |
| 3 | `listen(1)` with a serial accept thread lets a third connect be refused on Windows (blind, edge-case) | medium | The accept thread can spend up to 5 s in one handshake; Windows refuses connects past the backlog (`WinError 10061`, TC-99-03). | patch |
| 4 | Busy envelope carries `data.rpc = "unreachable"`, as for a dead bridge (blind, edge-case) | medium | `call` returns `_worker_crashed(..., unreachable=True)` for every connect error. | patch |
| 5 | Docs and comments say a quarantined call is refused "at once"; it now waits up to 0.1 s | low | `_PROBE_REASK_WAIT_S = 0.1` runs out during a body, because busy arrives only after `_BUSY_GRACE_S`. Wording fix. | patch |
| 6 | Module and `read_line` docstrings and the §3.2 sketch still describe one accept loop; sketch returns `-> None` | low | Direct correction. | patch |
| 7 | No test keeps an admitted session idle past the hello deadline (verification-gap) | medium | Deleting `conn.settimeout(None)` would close every GUI proxy session after 5 s idle; no test fails. | patch |
| 8 | Busy grace checked only by a test that fails about 1 run in 25 without it (verification-gap) | medium | `test_should_accept_the_next_client_when_the_session_has_ended` is probabilistic by the code's own comment. | patch |
| 9 | No test for version mismatch during a session, or for `stop()` ending an idle serving thread (blind) | medium | Frozen rule "auth and version before busy" has a test only for auth; `stop()` now ends the loop through the sentinel. | patch |
| 10 | New headless busy test does not assert the refusal's status (blind, edge-case) | low | Asserts `data` and message only. | patch |
| 11 | A looping silent local client can keep new handshakes waiting up to 5 s each; a queued valid client can hit its own 5 s hello timeout (blind, edge-case) | medium | The spec puts the handshake on the accept thread. The old listener let a silent connection hold the slot for good, so this narrows the 10.6a finding; per-connection handshake threads would close it. | defer |
| 12 | `stop()` does not end a serving loop blocked on an active session (edge-case) | false | Same as before the change, and the `stop()` docstring states it; the headless front closes its connection before the worker's stdin, and GUI quit ends the process. | reject |
| 13 | A probe rejected for a non-busy reason re-probes forever | false | The probe uses the token and version the first connection already passed. | reject |
| 14 | Busy is detected by message text, not a structured `data` field | low | The text is the shared `RPC_BUSY_MESSAGE` constant in `contracts/rpc.py`. | reject |
| 15 | Busy message says "another client" when the same client reconnects during its own in-flight call | low | The message text is fixed by the frozen matrix. | reject |
| 16 | `_HELLO_TIMEOUT_S` is defined in both client and listener | low | Linked by comments; moving it adds a contracts constant. | reject |
| 17 | TC-10 line references to `rpc_listener.py` are stale; no UAT step for the hello deadline or the H1 probe lift; multi-client mode not recorded as unbuilt | low | UAT maintenance (Story 10.7). | defer |
| 18 | TC-99-03 deleted instead of rewritten | low | TC-99's own rule moves a passing gap into the green gate; TC-10-03 now carries it. Recorded in Implementation Notes. | reject |

## Design Notes

The busy check needs the accept thread to run while a call executes. In GUI mode calls run on the Qt main thread, so the listener threads are free. In headless mode a body runs on the worker main thread. A body that holds the GIL in C++ for its whole run stops the accept thread too, so the front's probe gets no answer until it returns. A body that loops in Python around C++ calls lets the accept thread answer `busy` between calls; that answer is stale by the next call, so the front re-asks with a new probe and waits up to 0.1 s for it (Implementation Notes). A refused call therefore returns within about 0.1 s.

## Verification

**Commands:**
- `uv run pytest tests/external -q` -- expected: all pass.
- `fcb` env: `python -m pytest tests/external/test_headless_two_process.py tests/external/test_rpc_listener.py tests/external/test_rpc_client.py tests/external/test_gui_external_proxy.py -q` and `score_g3_replay.py --leg 1.1.x --run local --check --frames-check benchmarks/g3/fault-injection/frames-reference.json` -- expected: pass.
- `uv run ruff check . && uv run python scripts/check_imports.py` -- expected: clean.

**Manual checks:**
- GUI (cua-driver, per `freecad-gui-e2e-harness.md`): open FreeCAD with the addon; with the proxy connected, send a valid hello from a second client using the discovery file; expect `-32000` busy in under 1 s, the proxy's tools still answer, and a screenshot shows the window painted and responsive.
