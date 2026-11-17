# Lead log: UAT run 2026-10-23-02, fix work and display freeze

Owner request (2026-10-24): record the plan, what was done, what was found, what was decided, and the result. The lead updates this file as work progresses.

Branch: `fix/uat-gate-1-failures` (created from `main` at `3025e7c`). No commit was made. A commit needs the owner's approval.

Decision rule from the owner: decide from `docs/intent.md` and `_bmad-output/specs/spec-freecad-buddy/SPEC.md` (with `phase-gates.md` and `ARCHITECTURE-SPINE.md`), and cite the deciding line.

## 1. State of the UAT run 2026-10-23-02

| Item | State |
| --- | --- |
| Phases done | P0 (runner + §9 review), P1–P10 (TC-01..TC-12 agent-driven), P13 headless G3 |
| Phases not done | P11 (TC-13), P12 (TC-14, TC-99), G3 GUI replay: blocked by the display freeze |
| Verdicts (260 scenarios) | Critical 179: PASS 126, FAIL 26, BLOCKED 27. High 67: PASS 54, FAIL 3, BLOCKED 10. Medium 14: PASS 9, FAIL 4, BLOCKED 1 |
| Gate 1 | Red (Critical below 100 %) |
| G3 headless | Unchanged against `g3r-2026-10-08-1.1.3`: 10/10 planted detected, 10/10 reverted clean, 4/4 controls clean, frames-check OK |
| Report files | `report.md` and `bugs.md` not written yet. Verdict notes are in the lead scratchpad (`scratchpad/gate/`, tables in `tables.md`) |

Report written 2026-10-24 13:40: `tests/uat/run/2026-10-23-02/report.md`, `bugs.md` (51 entries), and 18 new `deferred-work.md` entries plus a status line under the goal 3 entry.

Lead check: 255 TC-01..TC-14 rows, each once. Gate counts recomputed from the tables: Critical 126/174 = 72.4 %, High 54/67 = 80.6 %. Gate 1 RED.

addon.log merge, done 2026-10-24 at about 14:20 with no FreeCAD running (owner choice "Merge at run end"):
- **Order joined:** dev backup (1626 lines, 2026-10-04 16:09:12 .. 2026-10-23 19:04:28), then `p1-addon-L1-L2.log` (16), then `p1-addon-L4-L5.log` (21), then the current file (430 lines, 2026-10-23 19:25:13 .. 2026-10-24 14:04:39).
- **Result:** 2093 lines, 523,962 bytes, time order checked with 0 lines out of order. SHA-256 `2a67ec86…2842`.
- **Copy kept:** the pre-merge current file is at `scratchpad/addon.log.current-before-merge`.

## 2. Display freeze

### Symptom

- After some minutes with no physical mouse or keyboard input, GPU-drawn windows (WezTerm terminal, FreeCAD) stop updating on the physical monitor and in screen captures. The taskbar clock keeps updating.
- A physical mouse move ends it. Confirmed by the owner on 2026-10-24 ("it was stuck, moving mouse fixed it").
- Seen 2026-10-24 about 08:15–09:18 and 10:04–about 12:20. It blocked P10's visual checks and stopped P11, P12 and the G3 GUI replay.

### What was checked

| Check | Result |
| --- | --- |
| Power plan | High performance. "Turn off display" AC = 0 (never). No screen saver executable set |
| Event logs (System, Application, DWM, Kernel-Power, display) around each onset and end | Nothing display or power related. Only `backgroundTaskHost.exe` crashes (about every 15 min) |
| GPU | RTX 4070 Ti, driver 32.0.16.1088, status OK, P8 at idle. One monitor ASUS VG27AQ1A, 2560×1440 at 119 Hz, 125 % scale |
| Other display device | `Virtual Desktop Monitor` (`ROOT\DISPLAY\0000`), status Error |
| DWM registry | No `OverlayTestMode` (multi-plane overlay at its default) |
| Software input during a freeze | cua-driver `move_cursor` with scope desktop did not end it |
| Idle test without cua-driver activity, 12:30–12:33 (3.8 min idle) | No freeze. A GDI probe window and a WezTerm probe window kept repainting |
| cua-driver windows | Two full-screen `Cua.AgentCursorOverlay` windows (pids 5516 `serve` and 11840 `mcp`), ex-style `0x080800A0` (no-activate, layered, transparent, tool window), rect 0,0–2048,1152. Their z-order position changes (cua-driver places the overlay above the window it acts on) |

### Current hypothesis (not proven)

The freeze needs both conditions: cua-driver activity and no physical input. The full-screen cua-driver overlay windows are the main suspect.

### Experiment running now

`scratchpad/freeze/sampler2.ps1`, log `scratchpad/freeze/freeze2.log`. Two topmost probe windows sit at the bottom-left of the screen: a GDI clock and a WezTerm clock. A freeze is when one probe stops changing for 8 s. At each freeze the probe:
- records the idle time, the z-order and a screenshot;
- then tries these in turn: hide the overlay windows, move the cursor through `SetCursorPos`, move it through `SendInput`.

If hiding the overlays ends the freeze, the probe shows them again. It then checks that the freeze comes back. It changes no system setting.

### Probe result so far

- **Window:** the probe ran from 12:56 to at least 14:17. The time since the last physical input reached 2294 s (38 min, owner away).
- **Activity:** six cua-driver GUI sessions ran by agents: W6, W5, W2b, W1b, W7, plus probes.
- **Freezes:** zero. Both probe windows repainted on every sample.
- **Open question:** the freeze did not come back, so the cause is still unproven. Either the trigger was absent, or the probe changed the conditions: two topmost windows that repaint every 0.25–0.5 s keep the desktop updating. The second reading is an observer effect, and it is untested.
- **Earlier freezes:** both started while the screen showed mostly static content.

### Owner decision

"Try some for verify. If still problem, debugging the root cause before fixing." No fix is applied until a cause is proven.

## 3. Fix plan for the 33 FAILs

Plan file: `scratchpad/fix/PLAN.md`. Six workstreams run as subagents. Each one edits only its own files. A GUI lock (`scratchpad/fix/gui.lock`) lets one agent at a time use the FreeCAD GUI.

| WS | Scenarios | Cause class | State |
| --- | --- | --- | --- |
| W1 | TC-02-08 | Product: `view_fit` and framing ignore the container placement (AD-30; SPEC CAP-9: `fitted: true` must be true) | First agent stopped by the owner before any edit. Restarted as `fix-w1b` |
| W2 | TC-08-02, TC-12-14 | Product: a failing preview posts a GUI notification (AD-31/AD-33). A clean quit writes no teardown line to `addon.log` | First agent stopped by the owner before any edit. Restarted as `fix-w2b` |
| W3 | TC-01-02, TC-09-01, TC-09-02, TC-09-22 (sweep), TC-10-01, TC-10-07 | Harness: the sweeps read only `structuredContent` and need a missing `fcb` env; `query_tree_summary` returns text only | Running |
| W4 | TC-01-13/15, TC-04-16/21/23, TC-05-06/17, TC-06-01/09, TC-08-01/13 | Test-case defects. TC-05-17 and TC-06-09 get a cause check | Running |
| W5 | TC-09-09, TC-09-22 (Given), TC-10-03, TC-11-11/14/15 | Test-case defects | Text fixes done; live checks of TC-09-09 and TC-10-03 wait for the GUI lock |
| W6 | TC-12-04/05/06/08/10/11 | Test-case defects plus GUI steps that cua-driver cannot drive | Running, holds the GUI lock |

Re-run only, no fix: TC-08-12 (agent execution fault), TC-09-15 (physical mouse).

## 3b. Re-run 2026-10-24-01 (started)

Spec D2: after the fixes, re-run into a new run folder.
- **Folder:** `tests/uat/run/2026-10-24-01/`, with `RUN-CONTEXT.md` listing the phases.
- **Baseline:** commit `3025e7c` plus the uncommitted fix diff. Tracked diff SHA-256 `9b30351f…00e9c`. The diff and the untracked file hashes are in `evidence/`.
- **Scope:** every FAIL and BLOCKED scenario of 2026-10-23-02 (84 agent-driven, plus TC-08-13 in the runner), plus a regression set of all agent-driven TC-02 and TC-08 scenarios. The runner runs all 72 files. The G3 GUI replay and the headless scorer also run.
- **Phases:** R0 (env + runner + §9), R1 (TC-01/02/04/05/06), R2 (TC-08/09/10/11), R3 (TC-12), R4 (TC-13), R5 (TC-14, TC-99), R6 (G3).
- **Phase rules:** `scratchpad/rerun/RULES.md`.
- **H1 env:** an fcb-shaped venv on FreeCAD 1.1.4 Python, built from the current working tree. It has no pip numpy, because of the deadlock W3 found.
- **Commit:** no commit before the re-run. The owner approves commits, so the run reports a commit plus a diff hash.

### R0 (done)

- **H1 env:** `scratchpad/rerun/fcbenv/fcb`. Its source equals the working-tree `src`, and pivy imports. The APPENDIX-B Step 3 check prints "H1 ok 1.1.4". The e2e sweep gives 29/29 and the edge sweep 14/14.
- **Runner:** seed 3815675731, 14:29–14:37. Results: 5 PASS, 1 FAIL (TC-08-04), 66 ESCALATE, 0 run errors. FreeCAD launched with `-u` and `-s`. `user.cfg` and `system.cfg` were unchanged.
- **§9 review:** all 72 runner scenarios PASS, which includes TC-08-04 graded PASS over the runner FAIL (D-lead-2). The lead checked the capture `TC-14-06` and its verdict row.
- **R0 stop:** R0 stopped 15:46–18:00 at the agent session limit and resumed after the reset.

Findings:
- R0-F1: `tc-08-04.json:487` `"\bFillet\b"` is a JSON backspace, so TC-08-04 fails on every runner run. The fix is `"\\bFillet\\b"`, to be made after the re-run.
- R0-F2: the runner cannot press GUI Fit All (TC-02-12/15/16/17).
- R0-F3: cua-driver `invoke_menu` stops resolving and leaves orphan popups late in a long session. A relaunch clears it.
- R0-F4: a refused redundant-constraint call (TC-03-12) still posts FreeCAD's "redundant constraints" message to the notification counter. This is the same family as TC-08-02.
- R0-F5: TC-11-17 names the default audit file, while runner launches set `FREECAD_BUDDY_AUDIT_LOG`.
- Lead note: runner capture `TC-14-06` shows a notification badge "8" from earlier scenarios in the same FreeCAD group. The source is not checked.

### R1 (done)

R1 graded 18/18 PASS. After the lead's own grading, the result is 15 PASS and 3 FAIL (`scratchpad/rerun/lead-grades.txt`).

| Scenario | Result |
| --- | --- |
| TC-02-08 | **FAIL (product defect, new cause).** The view-border clipping of 2026-10-23-02 is fixed: the plate is no longer cut by a view edge. But in `tc-02-08-after.png` (read by the lead) the plate's back-right corner and part of its top edge sit under the floating Tasks panel, while the fit reported `fitted: true`. This breaks SPEC CAP-9. FreeCAD's own Fit All does the same. Owner decision needed: does the area under an overlay panel count as visible? The notification badge stayed blank after `feature_datum` (W7 fix confirmed) |
| TC-02-05, TC-02-14 | **FAIL (test-case defect).** The Thens read `structured_content.shown` / `.matches` of the text-only `query_tree_summary`. This is the same rule as TC-10-07. These scenarios PASSed in 2026-10-23-02 on the same text reading, which was not consistent with D-lead-1 |
| TC-01-02, 13, 15; TC-02-07, 09, 10, 11, 18; TC-04-16, 21, 23; TC-05-06, 17; TC-06-01, 09 | PASS |

Findings:
- TC-05-06: the new reproducer reaches the bracket (`Pocket: Wire is not closed.`, `rolled_back_verified`). The snapshot restore was not reached, so that branch is recorded as not exercised.
- TC-06-01: the AntiAliasing seed works (edges blended, 16 colours versus 3 before). The written Cleanup calls `RemoveInt`, which FreeCAD does not have (`RemInt` is the real method). This is a test-case defect in the Cleanup.
- A failed `script_exec` posts its traceback to the GUI notification area. This is the same family as TC-08-02.
- The TC-02-05 Space toggle needs foreground delivery.
- R1-F1: agent launch-script fault. TC-01-13 was re-run, and both runs are kept.

### R2 (done)

R2 (agent `rerun-r2`, 19:00–20:04) graded 21 PASS and 1 FAIL. The lead confirmed the grades.

| Scenario | Result |
| --- | --- |
| TC-08-01, 02, 05, 06, 12, 17, 18, 19, 20, 21; TC-09-01, 02, 09, 15, 22; TC-10-01, 03, 07; TC-11-11, 14, 15 | PASS |
| TC-11-18 | **FAIL (test-case defect).** All path Thens pass. The visual Then (TC-11:887, "identical to before") cannot hold: the When (:867) creates `tc11-18` in the GUI, its view comes to the front, and the Then has no step to activate the golden again. The lead read `tc-11-18-after.png` (tc11-18 in front) and `tc-11-18-info-box-activated.png` (golden box whole and unchanged) |

Lead checks:
- `tc-08-02-statusbar-after.png`: no notification badge after the failing preview. The W2b fix holds.
- `tc-09-15-after.png`: box whole, no preselection highlight. The pointer-off-window rule works.
- Sweeps: e2e 29/29, edge 14/14, no `NO_STATUS`. `user.cfg` unchanged through 2 GUI launches and 19 H1 starts.

Findings:
- R2-F1: TC-11-18 needs a Windows-menu step to activate the golden before the closing fit.
- R2-F2: TC-08:680 restores `Visibility: true`, but Pad was hidden before. The step must restore the value read before. No verdict effect.
- R2-F3: TC-09:46 Given "no `hosts.main` process" conflicts with the GUI proxy, which is a `hosts.main` process. The agent read it as "no H1 server".
- R2-F4: a failed `script_exec` posts its traceback to the GUI notification area (`tc-08-21-notifications.png`). Same as R1-F5; owner decision pending.
- R2-F5: three agent execution faults (TC-08-19, TC-08-21, TC-11-18). Each scenario was re-run once from its Given; both runs are kept.

Not done: TC-11-14 H2 leg (H1 only, as in 2026-10-23-02).

### R3 (done)

R3 (agent `rerun-r3`, Sonnet, 20:06–21:37) finished all 12 scenarios. The agent reports that the pause request reached it only after the phase was complete. Result: 11 PASS and 1 FAIL. The lead confirmed the grades.

| Scenario | Result |
| --- | --- |
| TC-12-01, 03, 04, 06, 08, 10, 11, 12, 13, 14, 15 | PASS |
| TC-12-05 | **FAIL (test-case defect).** Thens TC-12:328 and :330 compare the whole `query_tree_summary` text. The header lines (framing ratio, Warning) change by design with the visible set and the fit (`mcp-tools-design.md:282`). The object lines match. The lead read `tc-12-05-after-unselected.png`: one cube, ObjectB row greyed, no dialog |

Confirmed by R3:
- The foreground rules work for tree-row select, combo ListItem and scroll. The pointer was moved outside the window rectangle before every capture.
- TC-12-06 with a real fillet: the Undo popup reads `buddy: feature_fillet Fillet` first.
- TC-12-14: `addon.log` holds `freecad-buddy bridge stopped` 0.22 s after File > Exit.
- `user.cfg` was unchanged through 14 launches.

Findings:
- R3-F1: TC-12-05 must compare object lines only.
- R3-F2 (harness limit): `invoke_menu` File > Save, File > Exit and a Windows entry were refused at times with `menu_path_unavailable`; the agent used the toolbar or a pixel click on the popup instead.
- R3-F3: the TC-12-01 menu leaf names differ from the live menu (`Part Design > New Body`, `Sketch > New Sketch`). The Then at TC-12:151 (40 mm pocket spacing) has no single tool value; it was derived from `query_sketch_info`.
- R3-F4: TC-12-12 `view_fit_viewport` returns `SPEC_FAILED view_fit.unverified` while a TechDraw page is the active view, until the 3D tab is activated.
- R3-F5: TC-12-14 with a fresh temporary profile shows the Welcome panel over the Start page.
- R3-F6: stale `rpc-<pid>.json` files remain after killed launches (same family as the AD-25 open finding).
- R3-F7: FreeCAD's own sketch and preview messages raise the notification badge in TC-12-01. These are not bridge messages.
- R3-F8 (agent execution fault): TC-12-01 run 1 clicked the main-window Close button. It was re-run from its Given, and both runs are kept.

### Paused by the owner (2026-10-24 about 20:30)

The owner said "stop here. Save the progress". State at the pause:
- **Phases done:** R0, R1, R2 (lead-graded). **R3** finished all 12 scenarios at 21:37 (see R3 above); the pause request reached the agent only after that.
- **Not started (resume here):** R4 (TC-13), R5 (TC-14, TC-99), R6 (G3), R7 (regression of 104 scenarios).
- **Freeze probe stopped** at 20:30: sampler, monitor and both probe windows ended. Zero freezes from 12:56 to 20:26. The log is `lead-notes/freeze2.log`. The cause is still not proven.
- **Lead notes copied** from the session scratchpad to `tests/uat/run/2026-10-24-01/lead-notes/`: `LEAD-CONTEXT.md` (resume file), `RULES.md` (phase rules), `h1-env.txt`, `lead-grades.txt`, `r0.txt`..`r3.txt`, `regression-list.txt`. One file with a live session token was not copied.
- **H1 env** (`FCB_ENV`) lives in the session scratchpad and may be gone in a new session. Rebuild it as `lead-notes/h1-env.txt` and `uat-run-practices.md` §2 say, then prove it with both sweeps.

To resume:
1. Check `git status` and the branch `fix/uat-gate-1-failures`. Confirm the tracked diff SHA-256 still equals `9b30351f…00e9c`; if the code changed, the re-run needs a new baseline.
2. Hash the developer `user.cfg` (baseline `4c415695…6b75`).
3. Rebuild the H1 env if it is gone.
4. Start R4 (TC-13) on Sonnet with the R3 prompt pattern: rules file, RUN-CONTEXT, h1-env, lead-grades, watch items.
5. Then R5, R6, R7, the report, the test-case fixes, the end checks, and the commit request.

## 4. Decisions

| When | Decision | Reason |
| --- | --- | --- |
| 2026-10-24 | Fix work goes on the branch `fix/uat-gate-1-failures`, not on `main` | Git safety rule; the owner approves every commit |
| 2026-10-24 | The run folder 2026-10-23-02 stays the record of that run. Fixed scenarios and the BLOCKED ones are re-run into a new run folder | Spec D2: fixes are separate changes, and the re-run counts for the gate |
| 2026-10-24 | A Then may be rewritten only when the design or SPEC proves the product behaviour is the designed one; otherwise it is a product defect | Owner rule: decide from intent and SPEC |
| 2026-10-24 12:46 | The lead closed the owner's FreeCAD (pid 21664, graceful close) because it held `:8765` and blocked GUI checks | Owner: "You can close freecad don't ask me to do that" |
| 2026-10-24 12:46 | New `user.cfg` baseline SHA-256 `39d770956016d8d51e7c931c183add34499cc597704cb270c1ff5fbec553fa73` (old `ccf87cfe…`) | The owner's own FreeCAD wrote it at 12:46:33 when it closed. No run or fix FreeCAD wrote it |
| 2026-10-24 12:52 | Incident: W1b ran `freecadcmd.exe` with no `-u` at 12:52:29. FreeCADCmd saves its parameters on exit, so it rewrote the developer `user.cfg`: 67547 → 67483 bytes, SHA-256 `4c415695ea8006ae1515001702c2bdf31674508d9a7705c7c73c9ce987d56b75`. `system.cfg` was also rewritten at 12:52:29 and 12:56:02. No copy of the previous file exists, so the diff cannot be shown and the file was not restored. New rule for all agents: every FreeCADCmd call uses `-u <temp>\user.cfg -s <temp>\system.cfg`, and any in-process `import FreeCAD` runs with `FREECAD_USER_HOME` set to a temp dir. New baseline `4c415695…` | Found by W2b; writer identified from the agent transcripts (12:52:29 `freecadcmd.exe` call by W1b, file mtime 12:52:29.98) |
| 2026-10-24 | W1 and W2 restarted after the stop | The stop came in a bulk stop of finished agents with no reason given, and the owner's goal is to fix every FAIL |

## 5. Results so far

### W5 (done, live checks pending)

All six are test-case defects. The edits touch only the test-case markdown; no scenario JSON exists for them. The lead checked the cited design lines and ran both new TC-11-15 `grep` commands.

| Scenario | Fix |
| --- | --- |
| TC-09-09 | The visual Then brings the golden model back to the front through the GUI Windows menu (AD-31: the bridge must not activate another document) |
| TC-09-22 | The Given checks that the sweep scripts exist, not their reports |
| TC-10-03 | Reads `rpc-<pid>.json` of the live FreeCAD, not the first file found |
| TC-11-11 | Reads each cause where the product reports it (`detail` is null on `OK`, `data-contracts-design.md:88`) |
| TC-11-14 | Allows the one `.FCBak` that FreeCAD's own save writes (`Document.cpp:1866-1895`) |
| TC-11-15 | `grep` excludes `.pyc` files and matches calls, not words in a docstring |

W5 findings:
- Stale `rpc-*.json` files: W5 first called them designed (`security-and-service-design.md:65`). Re-checked against the spine, they are a product/design gap. AD-25 binds "every component that writes a file", and its Prevents line names "unbounded artifact growth". The discovery file lives outside the session workdir, and nothing deletes a dead pid's file. There are 62 now, the oldest from 2026-08-01. Proposed fix: the bridge-start sweep also deletes `rpc-<pid>.json` files whose pid is dead. This fix is not made in this round; it is recorded for the owner.
- TC-11-14 reading (lead decision): the `.FCBak` comes from FreeCAD's own `Document.save()` inside an explicit `document_save` on the operator's file. It is not a bridge orphan file in the sense of AD-25. The edit stands.
- The TC-10-03 When prints the live token. This was already so before W5's edit.

Runner tests: 144 passed.

W5 live checks, 13:04–13:16, own FreeCAD pid 5256 with temporary `-u` and `-s` profiles:

| Scenario | Result |
| --- | --- |
| TC-09-09 | PASS. A fit on the golden model while the long document is in front is refused with "the live viewport is showing 'aaa…'" (AD-31). The Windows menu entry is `3 box-10-20-30 : 1*`, not `: 1`, because Show All marks the document modified. TC-09:403 is corrected to read the exact entry from a fresh snapshot. W5 read the after capture: whole box, same size and place, no extra document |
| TC-10-03 | PASS with the new When. Second client: `-32000 "bridge busy: another client session is active"`, then 0 bytes. Wrong token: `auth failed`. Refusal line once in `addon.log`. The capture is byte-identical to the before capture. The token was masked in every saved file |

Extra W5 edits after W3:
- TC-10-07 (and the TC-10-08 Given) now read the quarantine through `query_object` on `Cylinder`. Run evidence `tc-10-07-h1-checks.txt` shows that call returning `detail.data.quarantined: true`.
- The `FCB_ENV` note is added to TC-09-01, TC-09-22, TC-10-01 and TC-10-02.
- The H1 precondition is now the APPENDIX-B Step 3 command (`tests/uat/APPENDIX-B-environment-setup.md:59-63`).

Open: the `fcb` env does not exist on this machine (`%USERPROFILE%\micromamba\envs\fcb`). The H1 preconditions cannot pass here until the env is created per APPENDIX-B. The run used a scratchpad stand-in. This is a setup step for the re-run.

### W1b (done)

TC-02-08 is a product defect, now fixed.
- **Cause:** `framing.py:99-102` read each object's bounding box in its container's coordinates. A Pad in a moved Body was framed as if it sat at the origin. FreeCADCmd repro: `model_bounds` gave (0,0,0,60,40,10); the true global box is (10,20,10,81.96,84.64,20). `view_fit.py` has no defect.
- **Fix:** `_object_bounds` reads the box after the existing `assertions.document_shape` places the shape by its global placement.
- **Decision basis:** SPEC CAP-9 "`fitted: true` requires the post-fit verdict to agree", and AD-30 (it projects world points).
- **Tests:** `tests/infc/test_framing.py`, 2 tests (moved and rotated Body; Mesh in a moved App::Part), which fail without the fix. infc full suite: 858 OK. External: 1697 passed.
- **Live check:** `tc0208-after.png`, read by the lead, shows the whole rotated plate in view with no edge cut.

New finding from that check (handled by W7): the status-bar badge showed 141 notifications. They are errors from the MapMode probe (`shim.py` `implemented_map_modes`, scratch document `fcb_mapmode_probe`) that `feature_datum` runs. This is the same class as TC-08-02 (AD-33). A re-run of TC-02-08 would see it.

W1b open items, no fix this round:
- The fit measures the whole 3D view, including the area under a floating Tasks panel. A part can end up just beside or under that panel.
- `document_shape` copies the shape of each object whose container moved, on each framing measure that is not served from cache. A fit measures up to 3 times.

### W8 (done)

All six review items applied:
- **Framing:** `_document_box` transforms the existing box, with no copy. A new test with a rotated cylinder fails under the old copy method. The rotated-Body box is unchanged, because a box's 8 corners rotate exactly.
- **Preview:** the mute starts after `live.saveCopy`.
- **Restore tests:** they compare against the values saved at the start. A new test covers a mute inside a mute.
- **TC-05-17:** names Layer 0.
- **Profile rule:** added to the harness standard (§2 Launch, Profile), and cited from TC-06:82.
- **`run_tests.py`:** finds its own path anywhere in `argv`. README:306-311 shows the temp-profile command.

Verify:
- infc 866 OK, both through the wrapper and through the fixed `run_tests.py`.
- External 1698 passed. Runner 144 passed. `check_imports` OK. ruff clean.
- `user.cfg` unchanged.

Lead follow-up:
- `tests/uat/runner/launch.py` now also passes `-s <temp>/system.cfg`. Before, it passed `-u` only, so a runner launch wrote the developer `system.cfg`. Runner tests: 144 passed.
- Open, no fix this round: `_automation/uat/launch.json` (the documented `cua-driver launch_app` step) starts FreeCAD with no profile.
- Open, no fix this round: CI and the `<fcb-env>\python.exe tests/run_tests.py` lines in the knowledge base are unchanged. CI runners have no developer profile.

### Review (done)

An independent review of the whole diff, read-only, found:
- **A, product:** no correctness defect.
- **B, harness:** nothing.
- **C, test cases:** no rewrite hides a product defect. Every cited line was checked.

Findings, all given to W8:
1. Medium: framing copies each moved shape on every measure. This is slow for large imports, and without triangulation the box can come out looser. Fix: transform the existing box, no copy.
2. Low: the `preview.py` comment is wrong, because the mute also covers `live.saveCopy`. Fix: start the mute after the save.
3. Low: the restore tests cannot catch a forced `True`, and no test covers a mute inside a mute. Fix: start one level False, and add a nested test.
4. Low: the TC-05-17 title and Design Ref still name Layer 1. Fix: name Layer 0.
5. Low: TC-06:82 claims a temporary-profile launch that no harness document states. Fix: add the `-u`/`-s`/`FREECAD_USER_HOME` rule to `freecad-gui-e2e-harness.md` and cite it.
6. Low, lead addition from W7: make `tests/run_tests.py` find its own path anywhere in `sys.argv`, so the infc suite runs with a temporary profile.

### W7 (done)

Probe notifications are a product defect (AD-33), now fixed.
- **Source, proved headless:** the live document's own datum recompute posts 0 messages. `implemented_map_modes("PartDesign::Plane")` posts 51 `Probe:` lines (the recompute of the throwaway datum, `shim.py:328`) and 102 `PositionBySupport:` lines (from `obj.MapMode = mode`, `AttachExtension.cpp:451`).
- **Fix:** the mute helper moves to `shim.py` as `notifications_muted()`. `_scratch_document` runs inside it, so every scratch probe (mapmode, enum, partdesign, varset, type) posts nothing to the notification area. `preview.py` uses the same helper, so the code is not duplicated. The probe still reads `getStatusString()`, so its result does not change.
- **Tests:** new `tests/infc/test_shim.py` (3 tests; the mute test fails without the fix) and a shared stand-in `tests/infc/notification_console.py`. infc 864 OK (through a wrapper, see below). External: 1698 passed. `check_imports` OK. ruff clean.
- **Live timing check, read by the lead:** after `feature_datum`, the badge was blank at +6.9 s, +32.7 s and +56 s. Control: after a failing fillet on the live document, badge `1` appeared within 1.8 s.

Harness finding:
- `tests/run_tests.py` checks `sys.argv[1]` for the script path. With `-u`/`-s` in front, it runs no test.
- So the standard infc command cannot run with a temporary profile, and run as written it rewrites the developer `user.cfg`.
- W7 used a wrapper script. No fix this round.

### W2b (done)

TC-08-02 is a product defect, now fixed.
- **Cause:** the preview's throwaway-copy recompute fails, and FreeCAD reports it through `Base::Console().error` (`App/Document.cpp:2798`). The GUI notification area (`NotificationAreaObserver`, `Gui/NotificationArea.cpp:268-317`) turns that into a badge. FreeCAD's own suppression flag `IgnoreErrorOnRecompute` has no Python binding.
- **Fix:** `preview.py` `_notifications_muted()` switches that one observer off only while the TempDoc exists, and restores it on every path. Headless, the observer does not exist and nothing changes.
- **Decision basis:** intent "Verify, don't trust" (the result still says `RECOMPUTE_ERROR`), and AD-33 (no GUI change the human did not ask for).
- **Tests:** `tests/infc/test_preview.py` `NotificationAreaTest`, 3 tests, which fail without the fix.
- **Live check:** after a failing preview, the badge stays blank and the window is pixel-identical after the fit. After a failing apply on the live document, the badge shows `1`, so the notification area still works. The lead read `a-statusbar-after.png` and `a-statusbar-after-live-apply.png`.

TC-12-14 is a product gap, now fixed.
- **Fix:** `stop_bridge` logs `freecad-buddy bridge stopped` at INFO.
- **Decision basis:** the logging standard lists "Service startup/shutdown" under what to log, and SPEC J2 says the log makes failures legible. The design was silent.
- **Live check:** the lead saw the line in `addon.log` at 13:54:03.

Lead follow-up:
- TC-12-14 Then (`TC-12-gui-workflows.md:826`) now names the exact line `freecad-buddy bridge stopped`. The lead edited it because W6 had shut down.
- The new test `test_should_log_one_teardown_line_when_the_bridge_stops` passes; the lead ran it.

W2b open items:
- After a preview with no fit, the status-bar view-size label disappeared until the next fit. The cause is not proven.
- The Report View still prints the copy's error. With the non-default "show Report View on error" setting on, the Report View would open.
- Possible one-line additions to the design docs (mcp-tools-design §3.8, integration-mcp-freecad §3.1).

Note: GUI FreeCADs started with a temporary `-u` profile still write to the developer `addon.log`, because its path comes from the user app data folder, not the profile. Add this to the addon.log merge task.

### W6 (done)

The only file changed is `tests/uat/testcases/TC-12-gui-workflows.md`. None of the six failures is a product defect. Live session: own FreeCAD pid 27344 with a temporary `-u` profile, 12:47–13:04. The display painted the whole time.

One cause sits behind four of the failures. On FreeCAD 1.1.4 these three actions do nothing in the background and work only with `delivery_mode:"foreground"`:
- selecting a tree row;
- clicking a list item in a combo-box popup;
- scrolling.

W6 added file-level rules for this.

| Scenario | Cause | Fix | Live proof |
| --- | --- | --- | --- |
| TC-12-04 | Test case named `4188.7902` (rule 9 rounds to 2 decimals). A background click does not select a tree row | `4188.79`. Foreground `select`. Check `selected` in a fresh snapshot plus the window title | `t04-after.png`: box row highlighted and bold, whole box drawn |
| TC-12-05 | "Toggle Visibility" is disabled with nothing selected (`CommandView.cpp:927-930`) | Foreground select of ObjectB, then the menu, then `escape`. The capture moves before the restore | `t05-after.png` (read by the lead): only ObjectA drawn, ObjectB row greyed |
| TC-12-06 | Selector `"buddy:"` matched 5 entries. The popup is not in the main-window capture. The undo ran before the closing capture | Full label selector. Capture the popup window. Fit, capture and undo become When steps | `t06-popup.png`. Not re-run with a real fillet |
| TC-12-08 | Query tools resolve by `Name` (spine :377 "Script against immutable `Name`, display `Label`") | `object:"Box001"` | Run evidence: volume 1000.0 |
| TC-12-10 | Background click on the combo list item does nothing. `View > Workbench` refuses after one use | Foreground list-item click | `t10-sk2`: selector reads Sketcher, and the switch back works |
| TC-12-11 | Token scroll falls back to `global_input` and has no effect | Foreground pixel scroll. Then: the topmost visible tree row changes | `t11-c.png` (read by the lead): rows Extra11–Extra25 after the scroll |

Lead decision: foreground delivery is accepted for TC-12-04/05/10/11 on one condition. After a foreground action, the real pointer moves outside the FreeCAD window before any visual capture, so no hover or preselection highlight shows (the cause of the TC-09-15 FAIL). W6 adds this rule.

W6 notes:
- W6's FreeCAD wrote the developer `system.cfg` at 13:03:58, because its launch used `-u` only. `user.cfg` was not written.
- Not re-run end to end: TC-12-06 with a real fillet, and TC-12-11 with the expanded Body.

Runner tests: 144 passed.

### W3 (done)

The sweep harness was the defect, not the product.

Design decision, checked by the lead:
- `query_tree_summary` returns text only, by design (`mcp-tools-design.md:60`: "Such a tool declares no `outputSchema` ... There is no JSON block and no `structuredContent`"; also `data-contracts-design.md:97`).
- Commit `57d3adb` made that change, and the sweeps were not updated with it.

| Scenario | Root cause | Fix |
| --- | --- | --- |
| TC-01-02, TC-10-01, TC-09-22 (sweep part) | `run_mcp_e2e.py:57` read the status only from `structuredContent`, so every tree check gave `NO_STATUS`. `_tree_names` read a second content block that no longer exists | `_status` reads `structuredContent` when present, else the `<STATUS>: ` text prefix. `_tree_names` parses `content[0]` |
| TC-09-01 (13 checks, 6 passed) | The same reader defect cascaded: no handle, then `obj` None, then a skipped check | Same fix. The edge sweep reads `shown` from the documented text. The `max_nodes` check now asserts a schema rejection |
| TC-09-02 | `NO_STATUS` was the sweep's own marker | Same fix |
| Exit 2 "fcb env python not found" | `run_mcp_e2e.py:44` hard-coded a path and ignored `FCB_ENV` (test-plan.md:261) | Uses `$FCB_ENV` and falls back to the old default. The `fcb` conda env stays a setup prerequisite (project-structure.md §2.3) |
| TC-10-07 | Not a product defect: a text-only tool cannot carry `detail.data.quarantined` | The test case must read the quarantine through a structured tool (owned by W5) |

Results:
- e2e sweep 29/29, exit 0. Edge sweep 14/14, exit 0.
- TC-09-02 statuses: `INVALID_INPUT`, `OK`, `SCHEMA_ERROR`, `SPEC_FAILED`.
- `pytest tests/external`: 1698 passed. The lead re-ran the new `tests/external/test_run_mcp_e2e.py`: 6 passed.
- The run used an `fcb`-shaped stand-in env on FreeCAD 1.1.4 Python, built from `HEAD` `3025e7c`.

Product finding (owner decision needed): the H1 stdio front can deadlock on a pip-installed numpy.
- With pip numpy 2.4.6, `verify_export_stl` hung in `import trimesh` (`export_oracle.py:187`, reached from `rpc_proxy.py:49`).
- Mechanism: a thread blocked on `sys.stdin.buffer.readline()`, then `import numpy`. Minimal repro: `scratchpad/fix/w3/repro_numpy_stdin.py`.
- FreeCAD's conda numpy 1.26.4 does not hang.
- Possible fix: import the oracle modules at front start, before the stdio reader starts.

Test-case text still to apply:
- W5: TC-10-07, plus the `FCB_ENV` note in TC-09 and TC-10.
- W4: the `FCB_ENV` note in TC-01.
- The precondition `"$FCB_PYTHON" -c "import FreeCAD, mcp"` fails without the APPENDIX-B PYTHONPATH step. It must use the APPENDIX-B Step 3 command.

### W4 (done, two small edits pending)

All 11 are test-case defects. No product defect found. Runner tests: 144 passed. All 72 scenario files load.

| Scenario | Cause | Fix |
| --- | --- | --- |
| TC-01-13, TC-01-15 | Start page, so no 3D view | When adds File > New Document. The visual expects `Unnamed` and an empty 3D view |
| TC-04-16, TC-04-23 | Then accepted only digest equality or snapshot | Accepts `rolled_back_verified` or `rolled_back_via_snapshot` with `changed` empty. Lead check: spine AD-5 (:77) "digest equality, else equal mass-property invariants over the same object names"; verification-design.md:70. SPEC "hash-proven rollback (AD-5/6)" refers to this AD |
| TC-04-21 | Quoted message no longer in source | Current text from `features.py:1789` |
| TC-05-06 | A pattern without `length` is refused at input. A probe showed no pattern count is a reproducer: 20 commits, 200 never finishes (more than 10 min, 5 GB) | Reproducer 1 is now `sketch_remove_geometry` (open wire, "Wire is not closed."). New Then: an `INVALID_INPUT` means the search is incomplete |
| TC-05-17 | Layer-0 sweep reports objects that fail `isValid()`. Only Pad fails; FreeCAD does not recompute Fillet | Then expects owner `Pad`, prop `Profile` (verification-design.md:94, :232) |
| TC-06-01 | The temporary profile has no AntiAliasing key, and FreeCAD reads it only when a view is built | The Given seeds `AntiAliasing=4` before the document opens. Cleanup restores the old value |
| TC-06-09 | Renders stay until the session-start sweep (AD-25: a link may still be read) | Then: the files added are exactly this scenario's links, and none sits in the system temp folder |
| TC-08-01 | Schema `/1` vs `/2` | `fcb.geometry-diff/2` (`contracts/diff.py:77`) |
| TC-08-13 | The MCP input schema refuses `decline` first (mcp-tools-design.md:554) | Quotes `Input validation error: 'decline' is not one of ['accept']`. `tc-08-13.json` updated |

W4 notes:
- The new TC-05-06 reproducer, the TC-06-01 AntiAliasing seed and the TC-01 New Document step are not yet run in the live GUI. The re-run must confirm them.
- A 200-occurrence pattern recompute can run without limit. This is a possible robustness finding (intent Phase 4: "survives a long unattended run without crash, hang"). It was not tested through the bridge.

Done later, checked by the lead:
- TC-01:25 has the APPENDIX-B Step 3 precondition.
- TC-01:87 has the `FCB_ENV` note.
- TC-03:438 has the same rollback wording as TC-04-16.
- Correction by W4: the two exit-127 results were the lead's kills, not FreeCAD crashes. The TC-05-06 text now rests only on the run that passed 10 min and 5 GB.

W4 ran five FreeCADCmd probes without `-u`, two of them before the rule existed. The developer `user.cfg` hash is still the 12:52 baseline `4c415695…`.

W4 shut down.

### Other workstreams

Pending. The lead adds each report here after checking it.
