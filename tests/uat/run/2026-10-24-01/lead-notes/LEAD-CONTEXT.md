# Lead resume context (saved 2026-10-24 ~19:20, before compaction)

Read this first after compaction. Then read `_bmad-output/implementation-artifacts/lead-log-2026-10-24-uat-fixes.md` (the full record) and `tests/uat/run/2026-10-24-01/RUN-CONTEXT.md`.

## Where things stand

- Repo `D:\Work\Personal\Sources\freecad-buddy`, branch `fix/uat-gate-1-failures` (from main `3025e7c`). NOTHING COMMITTED. 24 tracked files changed plus untracked: lead log, spec-10-8-d, tests/external/test_run_mcp_e2e.py, tests/infc/{notification_console,test_framing,test_shim}.py, run folders 2026-10-23-02 and 2026-10-24-01.
- Run 2026-10-23-02: closed. report.md, bugs.md (51), 18 deferred-work entries written. Gate 1 RED (Critical 126/174, High 54/67). Do not change its verdicts.
- Fix workstreams W1b, W2b, W3–W8 all done and shut down; review done. All checks green at last run: infc 866 OK, external 1698, runner 144, check_imports OK, ruff clean.
- Re-run 2026-10-24-01 in progress. Phases: R0 done (72/72 PASS), R1 done (15 PASS, 3 FAIL after lead grades), R2 done (21 PASS, 1 FAIL TC-11-18 test-case defect; lead-graded, agent shut down), R3 RUNNING (agent `rerun-r3`, sonnet, spawned ~20:10), then R3 TC-12 (12), R4 TC-13 (16), R5 TC-14 (11) + TC-99 (5), R6 G3 GUI replay + headless scorer, R7 regression of 104 agent-driven PASS scenarios (list: `scratchpad/rerun/regression-list.txt`).
- Owner said: run phase agents on model "sonnet" from R3 on (memory `sonnet-for-run-agents`). Lead assumed option 2 (full re-run incl. R7); owner did not answer explicitly; drop R7 if owner says option 1.
- Phase rules for agents: `scratchpad/rerun/RULES.md`. Phase verdict rows: `scratchpad/rerun/rN.txt`. Lead grade overrides: `scratchpad/rerun/lead-grades.txt` (TC-02-05, TC-02-14 FAIL test-case defect; TC-02-08 FAIL product defect overlay panel).
- H1 env for re-run: `FCB_ENV=...\scratchpad\rerun\fcbenv\fcb` (details `scratchpad/rerun/h1-env.txt`).
- Prompt template for phase agents: see the R1/R2 prompts in this conversation (read RULES.md, RUN-CONTEXT.md, h1-env.txt, lead-grades.txt; scenario list; watch items; output rN.txt + short report). Spawn one phase at a time (one desktop). Shut down each agent after checking its report (memory `shutdown-finished-subagents`).

## Machine state / invariants

- Developer `%APPDATA%\FreeCAD\v1-1\user.cfg` SHA-256 baseline `4c415695ea8006ae1515001702c2bdf31674508d9a7705c7c73c9ce987d56b75` (stable since 12:52:29). Every FreeCAD/FreeCADCmd uses temp `-u` and `-s`; in-process import FreeCAD uses FREECAD_USER_HOME temp.
- addon.log merge DONE (2093 lines). Pre-merge copy `scratchpad/addon.log.current-before-merge`.
- Freeze probe running: background task `sampler2.ps1` (pid via `Get-CimInstance ... sampler2`), log `scratchpad/freeze/freeze2.log`, probe windows GDI pid 11280, WezTerm pid 35760 (bottom-left, topmost). Zero freezes since 12:56 (idle up to 99 min). Re-arm the Monitor on `freeze2.log` (filter FREEZE|RESUME|REFREEZE|ACTION|NO-|END) after each 30-min expiry. Cause of freeze unproven; possible observer effect.
- Old run user.cfg baseline history: ccf87cfe… -> 39d77095… (owner FreeCAD close 12:46:33) -> 4c415695… (W1b FreeCADCmd without -u 12:52:29).

## Open decisions for the owner (asked 2026-10-24 ~19:10, not answered)

1. TC-02-08: does the area under a floating (overlay) Tasks panel count as visible? If not, the fit must exclude it (product + design note). SPEC CAP-9.
2. More GUI notification noise (same family as TC-08-02): refused redundant-constraint call (R0-F4, TC-03-12), failed script_exec traceback (R1-F5). Fix now or defer?
3. Commit approval: fixes + both run folders on `fix/uat-gate-1-failures` (main merge needs separate approval naming main). No Co-Authored-By trailer.

## After the re-run (to do)

- Write `tests/uat/run/2026-10-24-01/report.md` (2026-10-03-04 layout) + bugs.md from r0..r7 + lead-grades; Gate 1 / Gate 2 / G3.
- Small test-case fixes found in re-run: `tc-08-04.json:487` `"\bFillet\b"` -> `"\\bFillet\\b"`; TC-06-01 Cleanup `RemoveInt` -> `RemInt`; TC-02-05/14 `structured_content.shown/.matches` -> text header; TC-11-17 default audit file vs FREECAD_BUDDY_AUDIT_LOG (R0-F5). Then those scenarios need one more re-run.
- Open findings with no fix (in lead log / deferred-work): stale rpc-*.json (AD-25), H1 numpy deadlock, 200-occurrence pattern hang, `_automation/uat/launch.json` no profile, Report View still prints preview copy error, status-bar size label vanishes after preview without fit, cost note on framing.
- End checks, review step, then ask owner for commit approval.
- Test-case fixes after re-run also: TC-11-18 add Windows-menu activation of golden before closing fit; TC-08:680 restore Visibility value read before; TC-09:46 Given wording (no H1 server).
