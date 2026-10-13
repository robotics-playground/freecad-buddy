# Epic 10 Context: UAT Gate 1 Green

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Make the bridge do what the design says when a real agent drives it through the real FreeCAD 1.1.4 window: queries return what matches, mutations that should fail do fail, rollback is proven, every headless call is bounded, the RPC hop owns its session and logs what happens, and every report states what actually happened. The UAT suite and its harness must describe the shipped product, and a full UAT run must become cheap enough to repeat (scripted runner plus an independent FreeCAD probe). Trigger: UAT run `2026-10-03-04` (HEAD `bece7ac`) was the first to run all of TC-01..TC-14 and left Gate 1 red: 34 of 251 scenarios FAIL, 29 on product defects F-01..F-33. Most defects are code that does not match an architecture decision that is already correct. The epic corrects shipped behaviour of Epics 1-3, 8 and 9; it opens no gate and reopens no epic. Epic 4 Story 4.3 waits until Epic 10 is done.

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

- **Each finding is a hypothesis.** Reproduce it first from `tests/uat/run/2026-10-03-04/report.md` (Findings give request, output and `file:line` at `bece7ac`; re-locate lines before editing). Fix with a regression test. A finding that does not reproduce is closed with evidence, not fixed.
- Re-run every validator score whose sources change. Never open `benchmarks/*/heldout`. CI stays green.
- **Headless bound (10.6a, 10.6 goal A):** `freecad-buddy serve --transport stdio --mode inline` keeps its CLI. Envelopes and audit records stay identical to the single-process host on `tests/external` and `scripts/automation/run_mcp_e2e.py`. Every headless tool, including a pure-C++ body that holds the GIL, returns `TIMEOUT` within `timeout_s` + 1 s; measure with a C++ body, not only a `sleep`. After a timed-out `script_exec`, the next call never waits on the abandoned body's registry lock (F-33). GUI tests pass unchanged. A timed-out mutation that completes later keeps its commit (TC-10-10); the AD-27 "rollback proved" clause is deferred for both hosts.
- **Story 10.6 is split into goals.** A (AC1, AC2: bounded execution), B (AC3: second RPC client gets busy refusal) and D (AC5, AC6: log levels, Windows discovery-file ACL comment; F-24, F-31, F-32) are built. **Goal C is open:** after an unclean FreeCAD kill the relaunched addon must verify `/healthz` session identity before it adopts a server on `:8765` (AC4, F-26; TC-01-14, TC-10-12, TC-12-15, TC-99-08). It touches the GUI bootstrap spawn guard and the proxy health endpoint, and needs a `cua-driver` GUI check.
- **Busy refusal (AD-26):** auth and version check run before the busy check. A second authenticated client gets `-32000` `bridge busy: another client session is active` in under 1 s and is closed. Calls still run one at a time on the same serving thread. No multi-client mode, no new flag. The headless front's quarantine probe reads a busy reply as "abandoned body not returned yet".
- **RPC logging:** each connection event logs once, no traceback. Client close or reset: INFO. Bad frame, non-JSON first frame, reply to a gone client: WARNING. Dropped in-flight call: WARNING in `rpc_client`, naming the method.
- **UAT suite (10.7):** test cases read build version and tool count from the live bridge, use the Epic 11 result envelope and current field names, accept MCP schema-layer refusals, use 1.1.4 edge numbering and menu labels, and build only fixtures the bridge allows. Disputed cases assert shipped behaviour and cite the sprint change proposal of 2026-10-04. `script_exec` replaces `debug_exec` everywhere: on by default, off with `FREECAD_BUDDY_SCRIPT_EXEC=0`, off with `FREECAD_BUDDY_UNATTENDED=1`, on again with `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`. Past run reports keep their text. TC-10 must drop the old `frame read failed` ERROR greps, check the new log levels and the busy refusal, and stop citing moved `rpc_listener.py` line numbers. The GUI harness standard forbids opening modal dialogs through `invoke_menu` and requires FreeCAD at the agent shell's integrity level.
- **Runner and probe (10.7b):** the probe reads FreeCAD kernel and GUI state read-only, shares no code with `src/freecad_buddy`, is not shipped, and loads only under the UAT launch profile. It must detect every planted fault in its own fault set. Scenarios run with no LLM call; the TC markdown stays the human source. A failed scripted check or a probe/MCP disagreement is a finding, never a retry, and goes to the `cua-driver` escalation ladder. FreeCAD launches non-elevated with a dedicated `-u` profile. The runner must reproduce the 2026-10-03-04 verdicts it covers.
- **Epic acceptance (10.8):** full TC-01..TC-14, TC-99 and the G3 live replay on FreeCAD 1.1.4 through the 10.7b runner. Gate 1 green (Critical 100 %, High >= 95 %); Gate 2 matches its documented deviations; G3 replay unchanged. Report committed under `tests/uat/run/`.

## Technical Decisions

- **Headless topology (AD-2):** two processes, one interpreter (`sys.executable`, `import FreeCAD` as a module, not `FreeCADCmd`, so offscreen render keeps working).
  - Front (`hosts/headless/entry.py`): MCP over stdio, never imports FreeCAD. Spawns the worker, hands it the session token directly (never through the discovery file), and is its only RPC client. Forwards each call with the method `timeout_s` as read timeout, holds quarantine and document-suspect state, runs mesh-verify oracle legs (AD-9).
  - Worker (`hosts/headless/worker.py`): stdlib + FreeCAD only (AD-12). Runs the RPC listener inline on its main thread, writes the audit log, writes no discovery file.
  - Why: FreeCAD never releases the GIL during a C++ operation, so no thread inside the FreeCAD process can enforce a budget. The process boundary makes it real.
  - Shared RPC code (`rpc_listener.py`, `rpc_client.py`, `gui_external/entry.py`) may change only if GUI behaviour stays the same. The GUI proxy keeps its fixed 130 s read timeout. Stdout stays clean on stdio; logs go to stderr (AD-3).
- **Post-timeout state (AD-27):** `TIMEOUT` is terminal for the caller, not the operation. Headless front quarantines the session: every call refused at once, without dispatch, with `TIMEOUT` and `detail.data.quarantined:true`. Past 2x budget, refusals become `WORKER_CRASHED` telling the operator to restart; the front never kills the worker. Quarantine lifts when the worker answers again. Worker exit: next call returns `WORKER_CRASHED`, no auto-restart. No mutation is retried automatically. The method registry is the single source of `timeout_s`.
- **Status set (AD-17):** closed set `OK | SPEC_FAILED | RECOMPUTE_ERROR | TIMEOUT | OOM_KILLED | WORKER_CRASHED | INVALID_INPUT`. Input faults (bad path, stale handle, malformed fingerprint) are `INVALID_INPUT`, never a catch-all `RECOMPUTE_ERROR`.
- **`script_exec` (AD-4):** official tool, on by default, unregistered when off, audit-logged with its source, outside the AD-5 transaction bracket.
- **Temp files (AD-25):** each host owns `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/`; the sweep touches only `FCB_TMP_` entries and removes a session folder only when its pid is dead.
- **Grading independence (AD-13):** a gate verdict comes from deterministic code or an independent grader, never from the producing agent. Every validator, the 10.7b probe included, proves its sensitivity on a planted fault set.
- **Render and framing:** a render is a constructed scene per call and need not match live viewport shading (AD-34). The framing bound is the whole 3D view, `getSize()` (AD-30). The bridge moves the camera only on `view_fit_viewport` (AD-33).
- **Rings (AD-1):** imports point inward only, `contracts/` <- `usecases/` <- `adapters/` <- `hosts/`. The probe lives outside `src/freecad_buddy`. No AI workflow in shipped code (AD-35).

## Cross-Story Dependencies

- 10.1-10.5 are done. 10.6a and 10.6 goals A, B, D are built and in review; goal C is open.
- 10.2 -> 10.3: both edit post-verify.
- 10.6a -> 10.6: 10.6 bounds calls in the front that 10.6a builds. Epic 12 Story 12.1 (done) precedes 10.6: both edit exec wiring in `hosts/tool_catalog.py`.
- Epic 11 Stories 11.1-11.4 (done) -> 10.7: test cases are written against the new envelope.
- 10.7 -> 10.7b: the runner encodes the corrected test cases. 10.7b and 10.8 also sit behind 10.6a.
- 10.8 is last: needs 10.1-10.7b done and CI green. Goal C covers Gate 1 scenarios, so it must be resolved or explicitly accepted before 10.8. 10.8 closes the epic and unblocks Epic 4 Story 4.3.
- The CI `headless` and `render` legs and `scripts/automation/run_mcp_*.py` launch the headless host through the unchanged CLI; they are the regression check for 10.6a.
