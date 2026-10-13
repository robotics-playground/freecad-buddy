# Epic 10 Context: UAT Gate 1 Green

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Make the bridge do what the design says when a real agent drives it through the real FreeCAD 1.1.4 window: queries return what matches, mutations that should fail do fail, rollback is proven, every call is bounded, and every report states what actually happened. The UAT suite and its harness must describe the product as it is, and a full UAT run must become cheap enough to repeat (scripted runner plus an independent FreeCAD probe). Trigger: UAT run `2026-10-03-04` (HEAD `bece7ac`) was the first to run all of TC-01..TC-14 and left Gate 1 red: 34 of 251 scenarios FAIL, 29 on product defects F-01..F-33 (Critical 74.7 %, needs 100 %; High 79.1 %, needs >= 95 %). Most defects are code that does not match an AD that is already correct. Planning of Story 10.6 then found that a single-process headless host cannot bound a C++ body that holds the GIL, so the headless host is split into a front process and a FreeCAD worker (new Story 10.6a). The epic corrects shipped behaviour of Epics 1-3, 8 and 9; it opens no gate and reopens no epic. Epic 4 is paused: Story 4.3 starts only when Epic 10 is done.

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

- **Each finding is a hypothesis.** Reproduce it first from `tests/uat/run/2026-10-03-04/report.md` ("Findings" gives request, output and `file:line` at `bece7ac`; re-locate lines before editing). Fix with a regression test. A finding that does not reproduce is closed with evidence, not fixed.
- **Re-run every validator score whose sources change.** Never open `benchmarks/*/heldout`. CI stays green throughout.
- **10.1-10.5 (done):** tree filters, save/label/path, bad save targets, undo fingerprint input, stale handle, `FCB_TMP_` sweep; sketch point/DistanceX/redundancy/DoF/error state, `verify_shape` input refusals; pad `TwoLengths`, pre-transaction refusals, post-verify of consumed sketch, rollback proof, null shapes in fingerprint, audit never `CLEAN` when not run, shared `params_digest`; render of a Body, render never changes `Visibility`/modified flag, transparency-only style, fit of sketch/mesh, refusal on datum-only; STEP AP242 `FILE_SCHEMA`. 10.7 and 10.8 test these behaviours as shipped.
- **10.6a:** `freecad-buddy serve --transport stdio --mode inline` keeps its CLI. It spawns one worker with the same interpreter. The front never imports `FreeCAD`; the worker never imports `mcp`. Envelopes and audit records equal the single-process host on `initialize`, `tools/list`, `tests/external` and `scripts/automation/run_mcp_e2e.py`. On stdin EOF: idle worker -> both exit 0; worker still busy after 5 s -> front ends it, logs once at ERROR, exits 1. Worker exits -> next call `WORKER_CRASHED` with "restart the host"; no auto-restart. Worker writes no discovery file; RPC hop requires the session token. `headless` and `render` CI legs pass; GUI tests pass unchanged.
- **10.6:** every headless tool, including a C++ body that holds the GIL, returns `TIMEOUT` within `timeout_s` + 1 s (measure with a C++ body, not only a sleep) and quarantines the session (TC-10-11). F-33: after a timed-out `script_exec`, the next call is refused or served without waiting on the abandoned registry lock. TC-99-07: second RPC client gets the busy error, never a hang. F-26: addon verifies `/healthz` session identity before adopting `:8765`; never adopts an orphan or foreign server. F-24/F-31: malformed first frame, clean exit and dropped in-flight call each logged once at the right level, no traceback on clean exit. F-32: Windows discovery-file comment states the ACL protection actually applied.
- **10.7:** test cases read build version and tool count from the live bridge, use current field names and the Epic 11 result envelope, accept MCP schema-layer refusals, show golden models before fitting, use 1.1.4 edge numbering and menu labels, build only fixtures the bridge allows. Disputed TC-02-17, TC-08-14, TC-10-06, TC-06-01/TC-13-06 assert shipped behaviour (cite sprint-change-proposal-2026-10-04). TC-14-13: bound is the whole 3D view. TC-99-03/04/05: promote implemented AD-25 parts. TC-06-10/TC-13-17: build Touched state through a bridge route, or retire with reason. `script_exec` replaces `debug_exec` in TC-01/05/08/09/11, coverage matrix, Appendix B and test plan: on by default, off with `FREECAD_BUDDY_SCRIPT_EXEC=0`, off with `FREECAD_BUDDY_UNATTENDED=1`, on again with `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`; past run reports keep their text. Harness standard forbids modal dialogs via `invoke_menu`, requires FreeCAD at the agent shell's integrity level, documents 1.1.4 background-input routes. Fix `uat_watchdog.py --since` crash on offset-aware timestamps.
- **10.7b:** test-only probe reads, read-only from FreeCAD kernel and GUI state: object type, visibility, `Shape` validity, volume, bbox, modified flag, active document, camera, visible view size. Shares no code with `src/freecad_buddy`, not shipped, loads only under the UAT launch profile. A FreeCADCmd reader checks a saved `.FCStd` offline. Probe catches every planted fault in its own set. Scenarios are executable files, no LLM call; TC markdown stays the human source. Pixel check grades fixed-size, fixed-DPI captures. Runner groups by launch configuration, launches non-elevated with a dedicated `-u` profile. A failed check or probe/MCP disagreement is a finding, never a retry; it goes to the `cua-driver` escalation ladder. Test plan §9: agent reads the capture for every FAIL, every disagreement, the first scenario per TC, and a random 20 % of the rest. Runner reproduces the 2026-10-03-04 verdicts it covers.
- **10.8 (epic acceptance):** full TC-01..TC-14, TC-99 and G3 live replay on FreeCAD 1.1.4 through the 10.7b runner. Gate 1 green (Critical 100 %, High >= 95 %); Gate 2 matches documented deviations; G3 replay unchanged. Report committed under `tests/uat/run/`.

## Technical Decisions

- **AD-2 headless topology:** two processes, one interpreter (conda env, `sys.executable`, `import FreeCAD` as a module; not `FreeCADCmd`, offscreen render keeps working).
  - **Front** (`hosts/headless/entry.py`): MCP over stdio, never imports FreeCAD. Spawns the worker, generates the session token and hands it over directly (not through the discovery file, which belongs to GUI mode). Only RPC client of the worker (AD-26). Forwards each call with the method `timeout_s` as the per-call read timeout. Holds quarantine and document-suspect state. Runs mesh-verify oracle legs (AD-9).
  - **Worker** (new `hosts/headless/worker.py`, stdlib + FreeCAD only, AD-12, although `mcp` is installed): builds the registry, `Marshal(InlineExecutor())`, `RpcListener(...).serve_forever_inline()` on its main thread. Writes the audit log, as the listener does in GUI mode. Writes no discovery file. Capabilities `gui:false, qt_loop:false`.
  - Why: FreeCAD never releases the GIL during a C++ operation, so no thread inside the FreeCAD process can time it out. The process boundary makes the budget real.
  - Shared RPC code (`rpc_listener.py`, `rpc_client.py`, `gui_external/entry.py`) may change only if GUI behaviour stays the same. `RpcClient` gets a per-call read timeout; the GUI proxy keeps its fixed 130 s. In-process registry unit tests (`test_confirm_contract.py`, `test_mcp_surface.py`) do not change. Stdout stays clean on stdio; all logs to stderr (AD-3).
  - H2 (`FreeCADCmd` worker) is not built.
- **AD-27 quarantine:** `TIMEOUT` is terminal for the caller, not the operation. The process that observes it quarantines the session: the listener in GUI mode, the front in headless mode. Headless: every call during quarantine is refused at once, without dispatch, `TIMEOUT` with `detail.data.quarantined:true`. Past 2x budget, refusals become `WORKER_CRASHED` with a message to restart the host; the front never kills the worker, so no open document is lost. Quarantine lifts when the worker answers again (single-threaded serve loop, so an answer proves the body returned). No mutation is ever retried automatically. The method registry is the single source of `timeout_s` (default 30 s; mutation/recompute 120 s; render 60 s).
- **AD-26:** one client session; a second gets JSON-RPC `-32000` busy, never a hang.
- **AD-2 port ownership:** the addon's already-served check on `:8765` probes `/healthz` for its own session id; a foreign or stale listener is an operator-visible error, never a silent reuse. Connection file records token and addon PID.
- **AD-4 `script_exec`:** official tool, on by default, unregistered when off, audit-logged with its source, writes its `before` line ahead of execution. Runs outside the AD-5 bracket: no transaction, fingerprint or rollback.
- **AD-17:** closed status set `OK | SPEC_FAILED | RECOMPUTE_ERROR | TIMEOUT | OOM_KILLED | WORKER_CRASHED | INVALID_INPUT`. Input faults are `INVALID_INPUT`.
- **AD-25:** temp files under `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/`; sweep touches only `FCB_TMP_` entries of dead hosts.
- **AD-13 / AD-20:** pass/fail by deterministic code or an independent grader; the 10.7b probe has its own sensitivity set.
- **Render and framing (for 10.7/10.8 expectations):** render is a constructed Coin scene per call and need not match live viewport shading (AD-34). Framing bound is the whole 3D view, `getSize()` (AD-30). The bridge never fits spontaneously; it moves the camera only on `view_fit_viewport` (AD-33). A quarantined document is never projected or fitted.
- **AD-1 rings:** imports point inward only, `contracts/` <- `usecases/` <- `adapters/` <- `hosts/`. The probe lives outside `src/freecad_buddy`. AD-35: no AI workflow in shipped code.

## Cross-Story Dependencies

- 10.1-10.5 are done.
- 10.6a before 10.6: 10.6 bounds calls in the front that 10.6a builds. Epic 12 Story 12.1 (done) before 10.6: both edit exec wiring in `hosts/tool_catalog.py`. The Story 10.6 spec is re-planned after 10.6a; its single-process approach and stdin-EOF rows are superseded (EOF behaviour moved to 10.6a).
- Epic 11 Stories 11.1-11.4 (done) before 10.7: test cases are written against the new envelope.
- 10.7 before 10.7b: the runner encodes the corrected test cases. 10.7b and 10.8 sit behind 10.6a.
- 10.8 is last: needs 10.1-10.7b done and CI green. It closes the epic and unblocks Epic 4 Story 4.3.
- CI `headless` and `render` legs and `scripts/automation/run_mcp_*.py` launch H1 through the unchanged CLI; they are the regression check for 10.6a.
