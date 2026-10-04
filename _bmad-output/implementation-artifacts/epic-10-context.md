# Epic 10 Context: UAT Gate 1 Green

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Make the bridge do what the design says when a real agent drives it through the real FreeCAD 1.1.4 window: queries return what matches, mutations that should fail do fail, rollback is proven, and every report states what actually happened. The UAT suite and its harness must describe the product as it is, and a full UAT run must become cheap enough to repeat (scripted runner plus an independent FreeCAD probe). Trigger: UAT run `2026-10-03-04` (HEAD `bece7ac`) was the first to run all of TC-01..TC-14 and left Gate 1 red: 34 of 251 scenarios FAIL, 29 on product defects F-01..F-33 (Critical 74.7 %, needs 100 %; High 79.1 %, needs ≥ 95 %). Most defects are code that does not match an AD that is already correct. Epic 4 is paused: Story 4.3 starts only when Epic 10 is done.

## Stories

- Story 10.1: Documents and Queries
- Story 10.2: Sketch and Verify Correctness
- Story 10.3: Feature Tools and the Mutation Protocol
- Story 10.4: Render and Framing
- Story 10.5: STEP Export Schema
- Story 10.6: Session, Transport and Bounded Execution
- Story 10.7: UAT Suite and Harness Maintenance
- Story 10.7b: Scripted UAT Runner and FreeCAD Probe
- Story 10.8: UAT Gate 1 Re-run

## Requirements & Constraints

- **Each finding is a hypothesis.** Reproduce it first from `tests/uat/run/2026-10-03-04/report.md` ("Findings" gives request, output and `file:line` at `bece7ac`; re-locate lines before editing). Fix with a regression test. A finding that does not reproduce is closed with evidence, not fixed.
- **Re-run every validator score whose sources change:** G0 `verify_shape`; G2 `assertions`, `verify_sketch`, `audit_references`, `run_mutation`; G3 `spec_assertions`. Never open `benchmarks/*/heldout`. CI stays green throughout.
- **Findings by story:**
  - 10.1: F-01 tree filters drop matching children of a non-matching container; F-02 save/create to a new path must set label to the file stem (GUI Save As parity) and report `label` and `path`; F-03 bad save targets (missing folder, directory, read-only file) must be `INVALID_INPUT` naming the path, no silent folder creation; F-12/F-20 `document_undo` fingerprint handling; F-25 stale handle after GUI close is `INVALID_INPUT`; F-30 temp sweep scope.
  - 10.2: F-04 point geometry reads `start`; F-05 single-point `DistanceX`/`DistanceY`; F-06 verdict independent of constraint order; F-17 DoF read after solving; F-19 sketch in error makes `recompute_clean` false; F-22/F-23 `verify_shape` input refusal.
  - 10.3: F-07 `second_length`/`TwoLengths`; F-08 type check before transaction; F-09 post-verify covers consumed sketch; F-10 rollback proof survives reopen; F-11 null shapes in fingerprint; F-13 audit never `CLEAN` when not run or broken; F-21 joinable auto-approve audit lines.
  - 10.4: F-14 Body `include` renders or reports `empty_scene: true`; F-15 render never changes live visibility or modified flag; F-16 transparency without colour; F-27 framing uses visible area; F-28 fit on datum/sketch/mesh-only document.
  - 10.5: F-18 `ap:"AP242"` and default write AP242 `FILE_SCHEMA`; paired verify checks it.
  - 10.6: TC-10-11 every headless tool bounded by registry `timeout_s`; F-33 no wait on abandoned `debug_exec` lock; TC-99-07 second client gets busy error; F-26 verify `/healthz` session identity before adopting `:8765`; F-24/F-31 logging levels, no traceback on clean exit; F-32 truthful Windows ACL comment.
- **Story 10.7:** test cases read build version and tool count from the live bridge, use current field names, accept MCP schema-layer refusals, show golden models before fitting, use 1.1.4 edge numbering and menu labels, build only fixtures the bridge allows. Disputed TC-02-17, TC-08-14, TC-10-06, TC-06-01/TC-13-06 (F-29): keep product behaviour, test cases assert it and cite the 2026-10-04 sprint change proposal. TC-99-03/04/05: promote implemented AD-25 parts to Gate 1, only the gap stays expected-fail. TC-06-10/TC-13-17: build Touched state through a bridge route, or retire with reason. Harness standard forbids modal dialogs via `invoke_menu`, requires FreeCAD at the agent shell's integrity level, documents background-input routes that work on 1.1.4. Fix `uat_watchdog.py --since` crash on offset-aware timestamps.
- **Story 10.7b:** test-only probe reads (read-only, from FreeCAD kernel and GUI state) object type, visibility, `Shape` validity, volume, bbox, modified flag, active document, camera, visible view size. It shares no code with `src/freecad_buddy`, is not shipped, loads only under the UAT launch profile. A FreeCADCmd reader checks saved `.FCStd` offline. Probe must catch every planted fault in its own fault set. Scenarios are executable files run with no LLM call; TC markdown stays the human source. Runner groups by launch configuration, launches non-elevated with a dedicated `-u` profile. A failed check or probe/MCP disagreement is a finding, never a retry, and goes to the `cua-driver` escalation ladder; a scripted pass never stands without its capture. Test plan §9: agent reads capture for every FAIL, every disagreement, first scenario per TC, and a random 20 % of the rest. Runner must reproduce the 2026-10-03-04 verdicts for every deterministic Then it covers.
- **Story 10.8 (epic acceptance):** full TC-01..TC-14, TC-99 and G3 live replay on FreeCAD 1.1.4 through the 10.7b runner, desktop free or GUI lane in an isolated Windows session. Gate 1 green (Critical 100 %, High ≥ 95 %); Gate 2 matches documented deviations; G3 replay unchanged. Report committed under `tests/uat/run/`.

## Technical Decisions

- **AD-5 mutation protocol:** snapshot → `openTransaction` → op → `recompute()` → post-verify (recompute clean, `Shape.isValid()`, `FullyConstrained` where sketches are involved, TNP audit) → commit. On failure: abort, recompute, re-hash to prove rollback; on mismatch restore the `saveCopy` snapshot and re-verify. Rollback is measured, never assumed.
- **AD-6 fingerprint:** one `fingerprint()` in usecases; SHA-256 over per-object shape bytes sorted by `Name`, plus quantized mass-property tuple; hashes tagged by serializer id and never compared across tags. FCStd/document-XML hashing is banned as identity oracle.
- **AD-7:** no element map means `UNSUPPORTED`, never clean.
- **AD-8:** sketch PASS iff `solve()` returns 0 after recompute, `FullyConstrained` is true, `dof == 0`, and no conflicting, malformed, redundant or degenerate condition holds; full redundancy fails as in FreeCAD's own execute, partial redundancy only warns.
- **AD-13:** pass/fail decided by deterministic code or an independent grader. The 10.7b probe is such an oracle and must pass its own sensitivity set.
- **AD-17:** closed status set `OK | SPEC_FAILED | RECOMPUTE_ERROR | TIMEOUT | OOM_KILLED | WORKER_CRASHED | INVALID_INPUT`. Input faults are `INVALID_INPUT`, never catch-all `RECOMPUTE_ERROR`. Audit records are append-only and joinable.
- **AD-19:** Epic 10 corrects shipped behaviour in Epics 1-3, 8, 9; it opens no gate and reopens no epic.
- **AD-20:** every call carries an explicit document handle; a handle to a document closed in the GUI is invalid input.
- **AD-25:** every bridge file lives in a session-scoped workdir (`snap/`, `exports/`, `audit.log`, `tmp/`). Each host owns `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/`. Sweep touches only `FCB_TMP_` entries: removes session folders whose pid is dead and prefixed entries at the top of `tmp/`; never a non-prefixed entry or a live host's folder. `FCB_TMP_` names of in-memory probe documents are never unlinked. Sweep runs at session start.
- **AD-26:** one client session at a time; a second client gets `-32000` busy, never a hang.
- **AD-27:** `TIMEOUT` quarantines the session until the in-flight op returns and its transaction is aborted with rollback proved. No automatic retry of mutations. The method registry is the single source of per-method `timeout_s`, so the headless host bounds every tool.
- **AD-30:** framing `fits` is false iff any of the 8 union-bbox corners projected through `getPointOnViewport` falls outside the viewport (visible area, per F-27).
- **AD-31:** `view_fit_viewport` is view-only: no geometry or fingerprint change.
- **AD-34:** render rig is one off-axis `SoDirectionalLight` plus ambient; ambient and headlight intensity (0.80) are set by the tone-band ceiling, not by viewport match. The MCP render need not match live viewport shading. A render must be distinguishable from an empty scene.
- **AD-1 rings:** imports point inward only, `contracts/` ← `usecases/` ← `adapters/` ← `hosts/`. The 10.7b probe lives outside `src/freecad_buddy`.

## Cross-Story Dependencies

- 10.1 to 10.6 are parallel-eligible, except 10.2 before 10.3: both edit post-verify (`usecases/transaction.py`, `usecases/verify.py`).
- 10.7 runs alongside the product stories; 10.7 before 10.7b, because the runner encodes the corrected test cases.
- 10.8 is last: needs 10.1 to 10.7b done and CI green. It closes the epic.
- Epic 4: Story 4.3 is blocked until Epic 10 is done.
