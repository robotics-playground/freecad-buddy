---
title: 'Story 10.7: UAT Suite and Harness Maintenance'
type: 'chore'
created: '2026-10-13'
status: 'done'
baseline_commit: 'b792cad387b0eb30d1622cf1d8f5b2fd17b0e665'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-10-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-10-7-edit-inventory.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** UAT run `2026-10-03-04` recorded test-case defects (stale version literal, tool count, field names, menu labels, edge numbers, fixtures the bridge refuses), disputed FAILs, AD-25 scenarios that are now partly implemented, two BLOCKED Touched-document scenarios and harness failures (modal dialogs through `invoke_menu`, FreeCAD at a higher integrity level than the agent shell, a `uat_watchdog.py --since` crash). Stories 10.1–10.6, 11.x and 12.1 then changed shipped behaviour the test cases still contradict (`script_exec` replaced `debug_exec`, full sketch redundancy fails, temp files moved to the session workdir, session quarantine, busy refusal, plain-text tree).

**Approach:** Edit the UAT test cases, suite docs and the GUI harness standard so each scenario describes the shipped product at HEAD, working from the edit inventory, and fix the watchdog timestamp comparison with a regression test.

## Boundaries & Constraints

**Always:**
- Every expectation follows the code at HEAD. Re-read the cited source before each edit; the inventory is a hypothesis list.
- Version and tool count are read live (`query_capabilities.freecad_version`, `tools/list`); no literal remains.
- Disputed TC-02-17, TC-08-14, TC-10-06 cite sprint-change-proposal-2026-10-04 decision 2; TC-06-01, TC-13-06, TC-14-05 cite decision 4 (render tone band, AD-34).
- `script_exec` scenarios cover: on by default, off with `FREECAD_BUDDY_SCRIPT_EXEC=0`, off with `FREECAD_BUDDY_UNATTENDED=1`, on with `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`.
- Docs follow CLAUDE.md §5 (ASD-STE100, caveman limits for documents); scenarios keep Given/When/Then.

**Never:**
- Edit anything under `tests/uat/run/` (past reports keep their text).
- Change product code under `src/` (a product gap found here goes to `deferred-work.md`).
- Weaken a Then that a product fix in 10.1–10.6 now satisfies.
- Open a modal dialog through `invoke_menu` in any test case.

## Decisions

- **D1 — Watchdog scope.** Fix only the `--since` crash (AC5). `check_temp` keeps scanning `tempfile.gettempdir()`; the stale scan location is not changed here.
- **D2 — `query_object` link targets.** TC-04-06, TC-04-13 and TC-04-15 accept the shipped type string (`"<PartDesign::Pad>"`, `queries.py:407`) and read the link target through `query_dependencies` or a FreeCAD oracle (`script_exec` or the fcb env).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Watchdog naive cutoff | `--since 2026-10-03T23:17:00` | runs; compares against local naive creation time | N/A |
| Watchdog aware cutoff | `--since 2026-10-03T23:17:00+07:00` | runs, no `TypeError`; same verdict as the equivalent naive local time | N/A |
| Watchdog bad cutoff | `--since yesterday` | argparse error naming `--since`, exit 2 | no traceback |

</frozen-after-approval>

## Code Map

- `_bmad-output/implementation-artifacts/spec-10-7-edit-inventory.md` -- per-file edit list with line, current text, change and evidence; shared terms (live version, Show All, session temp path, schema refusal, busy Given, Touched route, UndoMode 0 recipe, redundancy rule, rollback proof)
- `tests/uat/testcases/TC-01..TC-14, TC-99` -- scenario files to edit; TC-15, TC-16 untouched
- `tests/uat/{coverage-matrix,test-plan,APPENDIX-A-deferred-coverage,APPENDIX-B-environment-setup,README}.md` -- counts, env table, Gate 2 text, `script_exec` rows
- `tests/uat/run/2026-10-03-04/report.md:472-541` and `evidence/tc-NN-results.json` -- findings and full per-scenario notes (read-only)
- `_bmad-output/implementation-artifacts/spec-10-{1,2,3,4,5,6,6a,6b,6c,6d}-*.md`, `spec-12-1-*.md` -- decisions the test cases must follow
- `.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md` -- §3 Drive the GUI table (FreeCAD 1.1.1 rows), §2 Launch, §7 Shut down
- `scripts/automation/uat_watchdog.py:193` -- `datetime.fromisoformat(args.since)`; `:161-172` `_created_after` compares with naive `datetime.fromtimestamp`
- `tests/external/test_session_metrics.py:9-12` -- pattern for importing a `scripts/automation` module in pytest

## Tasks & Acceptance

**Execution:**
- [x] `scripts/automation/uat_watchdog.py` -- parse `--since` with an argparse `type` that converts an aware timestamp to local naive time (`astimezone().replace(tzinfo=None)`), and rejects an unparsable value -- AC5
- [x] `tests/external/test_uat_watchdog.py` -- cases from the I/O matrix: naive, aware (+07:00 and Z), unparsable; `_created_after` true/false around the cutoff on a `tmp_path` folder -- regression for AC5
- [x] `.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md` -- add rules: never open a modal dialog through `invoke_menu` (UIA stays busy until it closes); start the `cua-driver` daemon from the agent shell so FreeCAD runs at its integrity level, checked by `whoami /groups` (Medium) and `[System.Diagnostics.Process]::GetProcessById(P).Handle` succeeding; replace the 1.1.1 table with the 1.1.4 background-input routes (toolbar button by `element_token` works; `invoke_menu ["View","Fit All"]` refused; `right_click`/`double_click` by token go through `global_input`; `press_key`/`hotkey` to the viewport dropped; `invoke_menu ["File","Exit"]` works) -- AC4
- [x] `tests/uat/testcases/TC-01..TC-14` -- apply the inventory rows per file: AC1 shared edits, AC2 disputed and render-tone rewrites, AC6 Touched route in TC-06-10, TC-12-07, TC-13-17, AC7 `script_exec` posture (TC-11 plan in the inventory) -- AC1, AC2, AC6, AC7
- [x] `tests/uat/testcases/TC-99-ad-conformance-gaps.md` + `TC-11` -- move the implemented AD-25 parts (current TC-99-04/05/07, workdir and sweep) into new TC-11 Gate 1 scenarios; TC-99 keeps only the gap (snap/exports layout, session-named workdir, headless cwd default, audit log location — TC-99-06) -- AC3
- [x] `tests/uat/{coverage-matrix,test-plan,APPENDIX-A,APPENDIX-B,README}.md` -- inventory "Suite docs" rows; recompute Gate 1 / Gate 2 scenario counts after the TC-99 move -- AC1, AC3, AC7

**Acceptance Criteria:**
- Given the edited suite, when `rg -n "1\.1\.1|debug_exec|ALLOW_EXEC|AllowExec|\\$TEMP\"?/FCB_TMP|44 tools|exactly 45" tests/uat --glob '!run/**'` runs, then it returns no line that states current behaviour.
- Given each inventory row, when implementation ends, then it is applied or recorded in Implementation Notes as refuted with the source line that refutes it.
- Given the new 1.1.4 routes the edits introduce (Show All Objects menu, Touched route through `script_exec`, `File > Close` on a selected root, non-modal open), when each is run once on the live FreeCAD 1.1.4 GUI, then it behaves as the test case states, with a capture read by the agent.
- Given `coverage-matrix.md`, when its scenario totals are recounted from the TC files, then they match.

## Implementation Notes

Inventory rows: every row is applied. Rows corrected by the source while applied:

- TC-12-07, TC-12-12, TC-13-17 "Edit > Refresh": the command text is `Recompute`
  (`CommandDoc.cpp:1608` `sMenuText = QT_TR_NOOP("Recompute");`), enabled only when the document
  `mustExecute()` (`:1659-1662`). The test cases use `["Edit","Recompute"]`, with the `Recompute`
  toolbar button as fallback.
- TC-13-06 menu label: Fit All sits under `View > Standard Views` (`Workbench.cpp:707-709`); this is
  why `["View","Fit All"]` is refused.
- TC-12-02/03/08 `transient`: `false` for a GUI-adopted document (`documents.py:708`), `true` only for
  an unsaved `document_create` document (`:471`). The transient Thens in GUI flows are removed.
- TC-08-14: the shipped decoder gives a fourth distinct message for `fcb-preview:a.a`
  (`is not decodable`, `confirm.py:177-181`), so the Then keeps four distinct messages with that
  input; `!!!!.!!!!` and the truncated token give `carries an invalid signature`, and
  `payload is missing` is unreachable over the wire.

Scenario moves (AC3): TC-99-07 → TC-11-19 (start sweep); implemented parts of TC-99-04 and TC-99-05
→ TC-11-18 (session temp folder); the inventory's "TC-11-02b" (direct call while off) → TC-11-17.
TC-99 keeps 01, 02, 04, 05, 06 (gap only). Totals: 260 scenarios, Gate 1 255, Gate 2 5.

TC-15: one edit only, the precondition at `:22` reads `FreeCAD 1.1.x is running (record
query_capabilities.freecad_version)` instead of the `1.1.1` literal. The rest of TC-15 is untouched.

Live-check instance: FreeCAD 1.1.4 pid 33392, not started by this story (started 2026-10-13
19:50:34 by the `cua-driver` daemon pid 22944; `/healthz` `freecad_pid` 33392). It started before
commit `b792cad` (19:52:21); the routes checked here (menus, `script_exec`, File > Close, non-modal
open) do not depend on that change. Integrity: the agent shell is Medium (`whoami /groups`), and
`[System.Diagnostics.Process]::GetProcessById(33392).get_Handle()` fails with "Access is denied", so
this FreeCAD runs above the shell's level: the AC4 rule is not met on this instance, and the
`.Handle` property form silently returns `$null` (the harness standard now names `get_Handle()`).
The window was minimized; `bring_to_front` restored it once so captures had pixels.

Live route results (each capture read by the agent):

- Show All Objects: on `box-10-20-30`, `view_fit_viewport` gave `SPEC_FAILED
  view_fit.nothing_to_frame`; `invoke_menu ["View","Visibility","Show All Objects"]` then the fit gave
  `OK` (ratio 0.95). Capture: whole isometric box. Show All also marks the document modified (`*`).
- Touched route: on a 20×10×10 `BoxPad`, `script_exec` `Length = 25` returned `['Touched']`;
  `query_screenshot` gave `dirty_document: true` and `Document dirty (pending/broken recompute)`; the
  `Recompute` toolbar button was `enabled: true`. `invoke_menu ["Edit","Recompute"]` left `State`
  `['Up-to-date']`, `document_recompute` `touched: 0`, `dirty_document: false`, volume 5000. A second
  touch (`Length = 12`) followed by `document_recompute` gave `touched: 2`, then `0`, volume 2400.
  Capture: old pad drawn while touched, taller pad after. The tree touched marker was not readable
  (the `Body` row stayed collapsed).
- File > Close on a selected root: a UIA click and a background pixel click on the
  `cylinder-r5-h20` root row did not select it or change the active document (captures). The
  `Windows` menu entry `3 cylinder-r5-h20 : 1` activated it; `invoke_menu ["File","Close"]` closed it
  with no prompt; the stale handle then gave `INVALID_INPUT unknown or stale document handle`.
  TC-12-13 and TC-13-18 now activate through the `Windows` menu, and TC-12-01 Cleanup uses
  `document_close` (File > Close on a modified document opens a modal prompt).
- Non-modal open: after `document_close` of `box-10-20-30`, a background pixel double-click on its
  Start page Recent Files entry opened it (`route: synthetic_events`), no dialog window, and
  `document_list` adopted it with a new handle. The `launch_app` `additional_arguments` route was
  not run: it needs a FreeCAD restart, which was out of bounds for this instance.

End state: 0 documents open, pid 33392 still running.

Open risks for 10.7b/10.8: new `script_exec` recipes and fixtures were checked against the source,
not run: TC-03-06/11/14 fixtures (DoF counted by hand), TC-05-02/03/07/08/10/11/12/18 patches,
TC-07 re-import of 3MF through `Mesh`, TC-10-07/11 slow bodies, TC-11-12 patches. TC-10-05 still
needs a 100 s recompute fixture that typed tools cannot build. TC-12-09 opens Preferences through a
`script_exec` `QTimer` and closes it with `activeModalWidget().reject()`.

Review patches (pass 1): findings 1, 5, 7, 9, 12, 13, 18 and 20 applied. Finding 16 is refuted by
source and not applied: every audit write is wrapped and never fails the mutation
(`mcp_server.py:297-306` `_audit_safe`; `transaction.py:529`, `:551`), so an H1 in a non-writable
working directory loses its audit lines but its mutations still run.

## Spec Change Log

## Review Triage Log

| # | Layer | Finding | Verdict | Evidence | Route |
|---|-------|---------|---------|----------|-------|
| 1 | verification-gap | `test_uat_watchdog.py:55` asserts `"--since" in error`; usage line always contains it | low | argparse prints `[--since SINCE]` in usage on every error; direct correction | patch |
| 2 | blind, edge | `check_temp` scans `tempfile.gettempdir()`, snapshots live in the session workdir; README rule 9 promises a stop that cannot fire | medium | `uat_watchdog.py:149-150` vs `transaction.py:107`; spec D1 keeps the scan location | defer |
| 3 | blind | no test runs `main()`/`check_temp` with an aware `--since` | low | crash site is the comparison in `_created_after`, tested with a `parse_since` aware value; fix adds a test | reject |
| 4 | blind | test helper repeats the creation-time expression; equal cutoff untested | low | helper computes a fixture; `>` at equality never meets a real run; fix adds tests | reject |
| 5 | blind | status differs across spec, sprint-status, `epic-10-context.md` | low | spec/sprint gap is the workflow's own sequence (step 5 syncs); the `epic-10-context.md` status bullet is not from planning artifacts and is stale | patch (delete bullet) |
| 6 | blind, edge | spec Code Map says TC-15 untouched; spec task names `.Handle` | low | true, but the fix edits this build's spec | reject |
| 7 | blind | AC route changed to Windows menu; `additional_arguments` open route recommended but not run | low | route change is recorded in Implementation Notes (spec edit otherwise); harness lists the unrun route as working | patch (mark unconfirmed) |
| 8 | blind | live checks ran on FreeCAD above the shell's integrity; `Stop-Process` route unchecked | medium | `get_Handle()` "Access is denied" on pid 33392 (Implementation Notes) | defer |
| 9 | blind | harness requires the daemon from the agent shell but gives no command or recovery | medium | `freecad-gui-e2e-harness.md` Preflight; `cua-driver stop`/`serve`/`autostart` exist (`cua-driver --help`) | patch |
| 10 | blind | TC-12-09 Preferences modal via `QTimer`; dismissal through the same marshal may stall | maybe-false | settle by running TC-12-09 once: does `script_exec` run while the modal loop is up? | defer (medium, unverified) |
| 11 | blind | TC-11-17 and harness depend on gitignored `_automation/uat/` scripts | medium | `.gitignore:32`; pattern predates this story (harness Tools table) | defer |
| 12 | blind | TC-11-19 cleanup `kill %1` needs job control; pid from `tasklist` ambiguous | medium | agent shell keeps no state between calls; `TC-11:917,953` | patch |
| 13 | blind | TC-99-04/06 `cd A && … serve` then `ls -R A` cannot run in order | low | `serve` blocks; new lines at `TC-99:216,324`; direct correction | patch |
| 14 | blind | coverage matrix changed checkpoint rule without saying; TC-15/16 missing | false | rule stated at `coverage-matrix.md:33`; TC-15/16 omission predates this story | reject |
| 15 | blind | `epic-10-context.md` rewrite out of scope, drops requirements | false | recompile is mandated by the build workflow (stale cache); dropped TC-10 items already hold in TC-10 (`:564`, `:609` WARNING greps; `:525` matches `rpc_client.py:385` warning) | reject |
| 16 | blind | TC-99-06 dropped the "non-writable cwd fails every mutation" consequence, still true for H1 | low | `audit_log.py:24-26` bare relative default; baseline `TC-99:303-308`; one sentence | patch |
| 17 | edge | DST fall-back hour makes naive comparison off by up to 1 h | low | rare; fix adds aware comparison logic | reject |
| 18 | edge | proxy restarted by hand from `CommandLine` lacks the addon's settings overlay | medium | `entry.py:143` `Capabilities.from_env(os.environ)`; overlay lives only in the addon-spawned env; new in TC-01/10/11 cleanups | patch |
| 19 | edge | MCP client keeps the old session id after a proxy restart | low | `fcb.py:43` opens a new session per call; harness already says session tools need `/mcp` | reject |
| 20 | edge | `D=999999` not a multiple of 4; Windows ignores the low pid bits | low | Windows pids are multiples of 4; direct correction to `999996` | patch |
| 21 | edge | spec task text names `.Handle` | low | fix edits this build's spec | reject |

## Design Notes

AC3 numbering: the story says TC-99-03/04/05, written before commit `feabd50` moved AD-26 to TC-10-03. The AD-25 scenarios are now TC-99-04..07; the split applies to them. The move to TC-11 follows the precedent of TC-99-03 → TC-10-03 and TC-99-08 → TC-01-15.

TC-10-11: under Story 10.6 quarantine, a mutation sent while the 130 s read runs gets `TIMEOUT quarantined:true`. The scenario asserts that refusal, then waits for the body to return and asserts the mutation applies.

Reproducers that need a fault the typed tools cannot make (TC-05-07/08/10/11/12, TC-08-11/21, TC-11-12) use `script_exec` patches of bridge internals, as the `debug_exec` versions did. A case with no reproducer is retired with its reason.

## Verification

**Commands:**
- `uv run pytest tests/external/test_uat_watchdog.py` -- expected: all pass
- `uv run pytest tests/external` -- expected: no new failure
- `uv run python scripts/automation/uat_watchdog.py --pid 1 --since 2026-10-03T23:17:00+07:00` -- expected: no `TypeError` (other checks may fail without FreeCAD)
- `uv run ruff check .` and `uv run ruff format --check scripts/automation/uat_watchdog.py tests/external/test_uat_watchdog.py` -- expected: clean (no `package.json`; CI lints with ruff)

**Manual checks:**
- Live FreeCAD 1.1.4 GUI via `cua-driver`, per `freecad-gui-e2e-harness.md`: run each new route once, read each capture.
