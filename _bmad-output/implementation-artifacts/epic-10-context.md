# Epic 10 Context: UAT Gate 1 Green

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Make the bridge do what the design says when a real agent drives it through the real FreeCAD 1.1.4 window. Queries return what matches. Mutations that should fail do fail. Rollback is proven. Every headless call is bounded. The RPC hop serves one session, the GUI proxy is bound to its own FreeCAD, and every log and report states what actually happened. The UAT suite and its harness must describe the shipped product, and a full UAT run must become cheap enough to repeat (scripted runner plus an independent FreeCAD probe). Trigger: UAT run `2026-10-03-04` (HEAD `bece7ac`) was the first to run all of TC-01..TC-14. It left Gate 1 red: 34 of 251 scenarios FAIL, 29 of them on product defects F-01..F-33. Most defects are code that does not match an architecture decision that is already correct. The epic corrects shipped behaviour of Epics 1-3, 8 and 9. It opens no gate and reopens no epic. Epic 4 Story 4.3 waits until Epic 10 is done.

## Stories

- Story 10.1: Documents and Queries
- Story 10.2: Sketch and Verify Correctness
- Story 10.3: Feature Tools and the Mutation Protocol
- Story 10.4: Render and Framing
- Story 10.5: STEP Export Schema
- Story 10.6a: Two-Process Headless Host
- Story 10.6: Session, Transport and Bounded Execution
- Story 10.7: UAT Suite and Harness Maintenance
- Story 10.7b: Scripted UAT Runner and FreeCAD Probe
- Story 10.8: UAT Gate 1 Re-run

## Requirements & Constraints

- **Each finding is a hypothesis.** Reproduce it first from `tests/uat/run/2026-10-03-04/report.md` (Findings give request, output and `file:line` at `bece7ac`; re-locate lines before you edit). Fix with a regression test. A finding that does not reproduce is closed with evidence, not fixed. Re-run every validator score whose sources change. Never open `benchmarks/*/heldout`. CI stays green.
- **Headless bound (10.6a, 10.6):** `freecad-buddy serve --transport stdio --mode inline` keeps its CLI. Envelopes and audit records stay the same as on the single-process host for `tests/external` and `scripts/automation/run_mcp_e2e.py`. A body that holds the GIL in C++ and overruns its budget returns `TIMEOUT` within `timeout_s` + 1 s; measure with a C++ body, not only a `sleep`. After a timed-out `script_exec`, the next call never waits on the abandoned body's registry lock (F-33). GUI tests pass with no change to their expectations.
- **Busy refusal (AD-26):** token and version checks run before the busy check, so an unauthenticated caller learns nothing about the session. A second authenticated client waits up to 0.2 s for the session to end, then gets `-32000` `bridge busy: another client session is active` in under 1 s and is closed; the active session is undisturbed. `rpc_client` reports it as `WORKER_CRASHED` with that message and does not retry. No multi-client mode.
- **Proxy identity (GUI, F-26):** after an unclean FreeCAD kill the relaunched addon never adopts what holds `:8765`. Details under Technical Decisions.
- **Logging (F-24, F-31, F-32):** each connection event logs once, no traceback on a clean exit. A connection with no `rpc_hello` in 5 s is closed and logged once at WARNING. The Windows discovery-file comment states the ACL protection actually applied.
- **UAT suite (10.7):** test cases read build version and tool count from the live bridge, use current field names and the Epic 11 result envelope, accept MCP schema-layer refusals where the input is still refused, use FreeCAD 1.1.4 edge numbering and menu labels, and build only fixtures the bridge allows. Disputed TC-02-17, TC-08-14, TC-10-06 and render shading (TC-06-01, TC-13-06) assert shipped behaviour and cite the 2026-10-04 proposal. TC-14-13 is corrected: framing bound is the whole 3D view, and a window so small that the MDI area scrolls the view is out of scope (F-27 is not a defect). `script_exec` replaces `debug_exec` everywhere: on by default, off with `FREECAD_BUDDY_SCRIPT_EXEC=0`, off with `FREECAD_BUDDY_UNATTENDED=1`, on again with `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`. Past run reports keep their text. The GUI harness standard forbids opening modal dialogs through `invoke_menu` and requires FreeCAD at the agent shell's integrity level.
- **Runner and probe (10.7b):** the probe reads FreeCAD kernel and GUI state read-only, shares no code with `src/freecad_buddy`, is not shipped, and loads only under the UAT launch profile. It must detect every planted fault in its own fault set. Scenarios run with no LLM call; the TC markdown stays the human source. A failed scripted check or a probe/MCP disagreement is a finding, never a retry, and goes to the `cua-driver` escalation ladder. A scripted pass never stands without its capture. FreeCAD launches non-elevated with a dedicated `-u` profile. The runner must reproduce the 2026-10-03-04 verdicts it covers.
- **Epic acceptance (10.8):** full TC-01..TC-14, TC-99 and the G3 live replay on FreeCAD 1.1.4 through the 10.7b runner. Gate 1 green (Critical 100 %, High >= 95 %); Gate 2 matches its documented deviations; G3 replay unchanged. Report committed under `tests/uat/run/`.

## Technical Decisions

- **Headless topology (AD-2):** two processes, one interpreter (`sys.executable`, `import FreeCAD` as a module, not `FreeCADCmd`, so offscreen render keeps working). Reason: FreeCAD never releases the GIL during a C++ operation, so only a process boundary can enforce a budget.
  - Front (`hosts/headless/entry.py`): MCP over stdio, never imports FreeCAD. Spawns the worker, hands it the session token directly (never through the discovery file), and is its only RPC client. Forwards each call with the method `timeout_s` as read timeout. Holds quarantine and document-suspect state, runs mesh-verify oracle legs (AD-9), and writes the adapter audit pairs (including the `script_exec`-off denial and the document-suspect refusal).
  - Worker (`hosts/headless/worker.py`): stdlib + FreeCAD only (AD-12). Runs the listener inline on its main thread. Its listener has no audit sink; it writes only the records the mutation bracket and the camera fit write themselves. Both processes append to the same audit file, one call at a time. Writes no discovery file.
  - Lifecycle: on stdin EOF the front waits at most 5 s, then ends the worker, logs once at ERROR, exits 1. Worker exit → every next call `WORKER_CRASHED`, no restart.
  - Shared RPC code may change only if GUI behaviour stays the same. GUI proxy keeps its fixed 130 s read timeout. Stdout stays clean on stdio (AD-3).
- **Post-timeout state (AD-27):** `TIMEOUT` is terminal for the caller, not the operation. Headless front quarantines: every call refused without dispatch within 0.1 s, `TIMEOUT` with `detail.data.quarantined:true`. Past 2x budget, refusals become `WORKER_CRASHED` asking the operator to restart; the front never kills the worker. Quarantine lifts when the worker accepts a hello from the front's probe connection; a busy reply means "not yet". No mutation is retried automatically. The method registry is the single source of `timeout_s`.
- **Listener threads (AD-26):** an accept thread runs every handshake (5 s hello deadline, auth, version, then busy check); one serving loop serves the single active session (Qt-marshal thread in GUI, worker main thread headless). No idle timeout for an authenticated session.
- **GUI proxy identity (AD-2, AD-24):** the addon writes its discovery record before it spawns the proxy. The proxy pins that record (pid + token), reconnects only to it, and never moves to a newer FreeCAD. A watchdog exits the proxy about 2 s after the pinned pid dies. `GET /healthz` returns `service`, `freecad_pid`, `session_id` (first 16 hex of SHA-256 of the token), never the token. At start, if `:8765` is served, the addon probes `/healthz` on a daemon thread and never reuses the port: live FreeCAD's proxy or unpinned proxy → one ERROR, no spawn; orphan proxy or non-`/healthz` holder → wait up to 10 s, then spawn or ERROR. The addon never ends a process it did not spawn. The RPC listener starts in every case.
- **Status set (AD-17):** `OK | SPEC_FAILED | RECOMPUTE_ERROR | TIMEOUT | OOM_KILLED | WORKER_CRASHED | INVALID_INPUT`. Input faults (bad path, stale handle, malformed fingerprint, bad `verify_shape` input) are `INVALID_INPUT`, never a catch-all `RECOMPUTE_ERROR`.
- **Mutation protocol (AD-5, AD-6, AD-7, AD-8):** rollback is measured, never assumed; digest equality, else equal mass-property invariants, else snapshot restore and re-verify. Sketch PASS needs `solve()==0`, `FullyConstrained`, `DoF==0` read after solve; full redundancy fails, partial redundancy warns. A TNP audit that did not run is never `CLEAN`.
- **`script_exec` (AD-4):** on by default, unregistered when off, audit-logged with its source, outside the AD-5 bracket.
- **Temp files (AD-25):** each host owns `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/`; the sweep touches only `FCB_TMP_` entries and removes a session folder only when its pid is dead.
- **Render and framing:** a render is a constructed scene and need not match live viewport shading (AD-34). The framing bound is the whole 3D view, `getSize()` (AD-30). The bridge moves the camera only on `view_fit_viewport` (AD-33).
- **Grading independence (AD-13):** a gate verdict comes from deterministic code or an independent grader, never from the producing agent. Every validator, the 10.7b probe included, proves its sensitivity on a planted fault set.
- **Rings (AD-1, AD-35):** imports point inward only. The probe lives outside `src/freecad_buddy`. No AI workflow in shipped code. FreeCAD 1.1.x only.

## Cross-Story Dependencies

- 10.2 -> 10.3: both edit post-verify.
- 10.6a -> 10.6: 10.6 bounds calls in the front that 10.6a builds. Epic 12 Story 12.1 precedes 10.6: both edit exec wiring in `hosts/tool_catalog.py`.
- Epic 11 Stories 11.1-11.4 -> 10.7: test cases are written once, against the new envelope.
- 10.7 -> 10.7b: the runner encodes the corrected test cases.
- 10.8 is last: needs 10.1-10.7b done and CI green. It closes the epic and unblocks Epic 4 Story 4.3.
- The CI `headless` and `render` legs and `scripts/automation/run_mcp_*.py` launch the headless host through the unchanged CLI; they are the regression check for 10.6a.
