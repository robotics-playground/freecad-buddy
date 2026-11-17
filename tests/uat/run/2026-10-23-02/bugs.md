# Bugs and findings — UAT run 2026-10-23-02

Source: `report.md` of this run (verdict tables and Findings). One entry per FAIL cause (`B-nn`) and per finding that changed no verdict (`N-nn`). An entry lists every scenario it covers; every FAIL of `report.md` appears in exactly one `B-nn` entry, except TC-09-22, which has two causes (B-01 and B-17).

Cause classes:

- **product defect**: the product does not do what the design or SPEC says.
- **test-case defect**: the scenario text asks for something the designed product does not do (rule D-lead-1: still a FAIL).
- **harness defect / harness limit**: a test tool is wrong, or cannot drive the GUI step as written.
- **environment**: the machine, not the product or the test.
- **agent execution fault**: the agent ran the scenario wrongly; re-run needed, no fix.
- **human intervention**: a person's input changed the result; re-run needed, no fix.

States:

- **fix on branch, re-run pending**: the lead log (`_bmad-output/implementation-artifacts/lead-log-2026-10-24-uat-fixes.md`) records a fix on the branch `fix/uat-gate-1-failures` (uncommitted at report time). The scenario counts only after a re-run into a new run folder (spec D2).
- **fix on branch, lead check pending**: a change is on the branch, but the lead log has no checked result yet.
- **open**: no fix on the branch. Recorded in `_bmad-output/implementation-artifacts/deferred-work.md`.

Line numbers are at commit `3025e7c`. `TC-xx:n` means `tests/uat/testcases/TC-xx-*.md` line n.

## FAIL causes

| ID | Title | Priority | Scenario(s) | Evidence | Cause class | State |
| --- | --- | --- | --- | --- | --- | --- |
| B-01 | Sweep scripts read the status only from `structuredContent` and hard-code the `fcb` env path | Critical | TC-01-02, TC-09-01, TC-09-02, TC-09-22 (sweep part), TC-10-01 | `scripts/automation/run_mcp_e2e.py:44` (hard-coded env, exit 2), `:57-58` (`_status`), `:64-74` (`_tree_names` reads `content[1]`); `mcp_server.py:111-115` (text-only tool, by design `mcp-tools-design.md:60`); `evidence/tc-01-02-sweep-stdout.txt`, `tc-09-01-edge_report.json` | harness defect | fix on branch (W3: e2e 29/29, edge 14/14), re-run pending |
| B-02 | `view_fit_viewport` and the framing verdict ignore the container placement: `OK fitted`, `fits 0.95`, part cut by the view border | High | TC-02-08 | `usecases/framing.py:91` `model_bounds`, `:95-102` `_object_bounds`; `view_fit.py:162-168`; `evidence/tc-02-08-after.png` | product defect (AD-30) | fix on branch (W1b, `usecases/framing.py`), lead check pending; re-run pending |
| B-03 | A failing `preview_dry_run` posts a notification into the human's GUI (badge blank → 1, "Fillet: BRep_API: command not done (2 times)") | Critical | TC-08-02 | `evidence/tc-08-02-notification-popup.png`, `tc-08-02-statusbar-*.png`, `tc-08-02-checks.txt` | product defect (AD-31) | fix on branch (W2b, `usecases/preview.py`), lead check pending; re-run pending |
| B-04 | Clean quit writes no teardown line to `addon.log` | Critical | TC-12-14 | `hosts/gui_addon/bootstrap.py:510-531` `stop_bridge` logs nothing; `evidence/tc-12-c-addon.log`, `tc-12-14-checks.txt` | product gap (verdict: "test-case defect or product gap") | fix on branch (W2b, `bootstrap.py`), lead check pending; re-run pending |
| B-05 | Visual Then asks for a 3D view and Fit All, but the scenario opens no document | Critical | TC-01-13 (Medium), TC-01-15 | `TC-01:520-521`, `:630`; `evidence/tc-01-13-startpage.png` | test-case defect | fix on branch (W4), re-run pending |
| B-06 | Rollback Then accepts only equal digests or `rolled_back_via_snapshot`; product proves `rolled_back_verified` by mass properties (AD-5) | Critical | TC-04-16, TC-04-23 | `TC-04:686`, `:1000`; `usecases/transaction.py:345-370`; `evidence/tc-04-16-checks.txt` | test-case defect | fix on branch (W4), re-run pending |
| B-07 | Then quotes a refusal message no longer in source | Critical | TC-04-21 | `TC-04:910`; `usecases/features.py:1782-1789`; observed `BlockPad.Length is a App::PropertyLength and takes a {value, unit} quantity or a number, got [25]` | test-case defect | fix on branch (W4), re-run pending |
| B-08 | Reproducer 1 has no `length`, so it is refused at input and the conditional Then never holds | Critical | TC-05-06 | `TC-05:234`, `:246`; `usecases/features.py:1396` → `:121`; `evidence/tc-05-06-mcp.jsonl` | test-case defect | fix on branch (W4, new reproducer not yet run live), re-run pending |
| B-09 | Then expects the BROKEN owner `Fillet`; on 1.1.4 only `Pad` is invalid | Critical | TC-05-17 | `TC-05:677`; `usecases/tnp_guard.py:380-406`; `evidence/tc-05-17-mcp.jsonl` | test-case defect | fix on branch (W4), re-run pending |
| B-10 | Anti-aliasing Then reads the developer `user.cfg`; the temporary `-u` profile has no `AntiAliasing` key | Critical | TC-06-01 | `TC-06:119`; `evidence/tc-06-01-checks.txt` | harness limit | fix on branch (W4: Given seeds `AntiAliasing=4`, not yet run live), re-run pending |
| B-11 | Then allows "at most" the 3 linked render files; the session folder keeps all same-session renders by design (AD-25) | Critical | TC-06-09 | `TC-06:474`; `evidence/tc-06-09-checks.txt` | test-case defect | fix on branch (W4), re-run pending |
| B-12 | Then wants schema `fcb.geometry-diff/1`; the contract is `/2` | Critical | TC-08-01 | `TC-08:63`; `contracts/diff.py:77` | test-case defect | fix on branch (W4), re-run pending |
| B-13 | Then quotes the listener message for `decline`; over MCP the input schema refuses first: `Input validation error: 'decline' is not one of ['accept']` | Critical | TC-08-13 | `mcp-tools-design.md:554`; `tests/uat/scenarios/tc-08-13.json`; `ev/tc-08-13-at8` | test-case defect | fix on branch (W4, test case and `tc-08-13.json`), re-run pending |
| B-14 | Agent ran TC-08-21 in the same GUI during the 900 s TTL wait; badge 0 → 2 and an extra Tasks button in the capture | High | TC-08-12 | `evidence/tc-08-12-checks.txt`, `tc-08-12-notifications.png` | agent execution fault | open: re-run only, no fix |
| B-15 | Visual Then "golden model still shown" contradicts the When's `document_create` | Medium | TC-09-09 | `TC-09:385`, `:404`; `evidence/tc-09-09-checks.txt` | test-case defect | fix on branch (W5, live check PASS 13:04-13:16), re-run pending |
| B-16 | Physical mouse over the 3D view left a preselection highlight (118848 px) | Critical | TC-09-15 | `evidence/tc-09-15-after.png`, `tc-09-15-checks.txt` | human intervention | open: re-run only, no fix |
| B-17 | Given lists `tc-09-22-e2e_report.json` before the When creates it | Critical | TC-09-22 (Given part; sweep part is B-01) | `TC-09:861` | test-case defect | fix on branch (W5), re-run pending |
| B-18 | When takes the first `rpc-*.json` found, a stale file (1 live of 60) | Critical | TC-10-03 | `TC-10:153`; `evidence/tc-10-03-when-discovery.txt` | test-case defect | fix on branch (W5, live check PASS), re-run pending |
| B-19 | Two Thens read `detail.data.quarantined` from `query_tree_summary`, a text-only tool | Critical | TC-10-07 | `TC-10:324-325`; `mcp_server.py:111-115`, `_plain_text` `:127-138`; `evidence/tc-10-07-checks.txt` | test-case defect | fix on branch (W5: reads `query_object`), re-run pending |
| B-20 | Then reads `detail.message` on an `OK` preview; `detail` is null on `OK` | Critical | TC-11-11 | `TC-11:527`; `contracts/envelope.py:52`; `evidence/tc-11-11-checks.txt` | test-case defect | fix on branch (W5), re-run pending |
| B-21 | Third listing must add only the export; FreeCAD's own save adds a `.FCBak` | Critical | TC-11-14 | `TC-11:695-696`; `evidence/tc-11-14-listing3.txt` | test-case defect | fix on branch (W5), re-run pending |
| B-22 | `grep` also matches `__pycache__/*.pyc` and the docstring `audit_log.py:9` | Critical | TC-11-15 | `TC-11:734`, `:735`; `evidence/tc-11-15-checks.txt` | test-case defect | fix on branch (W5), re-run pending |
| B-23 | Background token click does not select a tree row; value `4188.7902` vs rule 9 rounding | Critical | TC-12-04 | `TC-12:237`, `:250`, `:254`, `:691`; `evidence/tc-12-04-checks.txt` | test-case defect | fix on branch (W6: foreground `select`), re-run pending |
| B-24 | `View > Visibility > Toggle Visibility` refused (`menu_path_unavailable`); the command is disabled with nothing selected | Critical | TC-12-05 | `CommandView.cpp:927-930`; `evidence/tc-12-05-checks.txt` | harness limit | fix on branch (W6), re-run pending |
| B-25 | `verify_state` selector `"buddy:"` matches 5 entries; undo popup not in the main-window capture; undo runs before the closing capture | Critical | TC-12-06 | `TC-12:350`, `:353`; `evidence/tc-12-06-popup.png` | test-case defect + harness limit | fix on branch (W6, not re-run with a real fillet), re-run pending |
| B-26 | Query by `Cube001`, a Label; queries resolve by Name (`Box001`) | High | TC-12-08 | `TC-12:467`; `usecases/queries.py:188-198`; spine `:377` | test-case defect | fix on branch (W6), re-run pending |
| B-27 | Background click on the workbench combo list item does not switch the workbench | Medium | TC-12-10 | `TC-12:569`; `evidence/tc-12-10-verify-sketcher.txt` | harness limit | fix on branch (W6: foreground click), re-run pending |
| B-28 | Token scroll falls back to `global_input` and does not scroll the tree | Medium | TC-12-11 | `TC-12:613`; `evidence/tc-12-11-frozen-checks.txt` | harness limit | fix on branch (W6: foreground pixel scroll), re-run pending |

## Findings with no verdict change

| ID | Title | Priority | Scenario(s) | Evidence | Cause class | State |
| --- | --- | --- | --- | --- | --- | --- |
| N-01 | Display freeze: GPU-drawn windows stop repainting until a physical mouse move; stopped P11, P12 and the G3 GUI replay (32 BLOCKED in Gate 1, 5 in TC-99) | Critical | TC-12-01/03/12/13/15, TC-13 (16), TC-14 (11), TC-99 (5), G3 GUI | `evidence/lead-desktop-0910.png`, `p10-recovery-watch.txt`, `p10-freeze2-diag.txt`; lead log §2 | environment (cause unproven; suspect `cua-driver` overlay windows) | open |
| N-02 | Stale `rpc-*.json` discovery files of dead FreeCADs are never removed (61 at report time, oldest 2026-08-01), each with a dead token | Medium | TC-10-03, TC-11 | P9 B8; lead log §5 W5 (AD-25 "unbounded artifact growth") | product/design gap (AD-25) | open |
| N-03 | H1 stdio front deadlocks with pip numpy 2.4.6 (`import trimesh` while a thread blocks on stdin) | High | H1 `verify_export_stl` | `adapters/export_oracle.py:187` via `rpc_proxy.py:49`; repro `scratchpad/fix/w3/repro_numpy_stdin.py`; lead log §5 W3 | product defect (owner decision needed) | open |
| N-04 | `feature_pattern` with 200 occurrences recomputes without limit (more than 10 min, 5 GB) | Medium | TC-05-06 (fix-work probe) | lead log §5 W4 | product robustness (not tested through the bridge) | open |
| N-05 | FreeCADCmd started without `-u` (for example `freecadcmd tests/run_tests.py`) rewrites the developer `user.cfg` and `system.cfg` on exit | High | teardown | lead log §4 incident 12:52:29 (67547 → 67483 B, `4c415695…`) | environment / harness | open |
| N-06 | `fcb` micromamba env (and micromamba) missing on this machine; H1 ran on a scratchpad stand-in | High | all H1 legs | `evidence/h1-setup.txt`; `tests/uat/APPENDIX-B-environment-setup.md` step 3 | environment | open |
| N-07 | H1 stand-in venv has no `pivy`, so the H1 render Then cannot be met | Critical | TC-11-18 (BLOCKED) | `TC-11:883`; `evidence/tc-11-18-checks.txt` | harness limit | open |
| N-08 | `document_save` leaves `*` in the window title; GUI Save clears it | Medium | TC-01-10 | P1 F4; `usecases/documents.py:341`, `:533` (not verified) | product defect (suspected) | open |
| N-09 | Consumed profile sketch stays visible after pad/pocket/revolve; FreeCAD's Pad hides it | Low | TC-04-06/10/15/17, TC-05-15 | `usecases/features.py:516-532`; `evidence/tc-04-10-top.png` | product defect (visual) | open |
| N-10 | `feature_datum` result: `feature_state.body ""`, `is_tip false`, volume 4e+101, area 8e+100 | Low | TC-04-13 | `usecases/features.py:329-335`, `:296` | product defect | open |
| N-11 | Mutation summary text prints `None` and says "could not be proven" for a committed but unhashable mutation | Low | TC-05-10/12/18, TC-11-12 | `usecases/transaction.py:491-497` | product defect | open |
| N-12 | Failed-check messages print a fixed `<=` (`1200.0 <= 6 mm^3`) | Low | TC-07-20 | `usecases/assertions.py:861`, `:892`, `:917`, `:954`; `usecases/exports.py:360` | product defect | open |
| N-13 | A failing `script_exec` posts its full traceback as a GUI notification | Low | TC-08-12, TC-08-21 | P5 observation (a); `evidence/tc-08-12-notifications.png` | product defect | open |
| N-14 | `query_tree_summary` says "2 objects, 2 shown" while one object is hidden | Low | TC-06-06 | P5 observation (b) | product defect | open |
| N-15 | GUI session render folder survives quit; H1 leaves an empty `FCB_TMP_session_*` after a clean stdin close (next start sweeps both) | Low | TC-06, TC-10, TC-11 | P5 observations (c)(d), F-P8-6, P9 B9 | product (temp hygiene, AD-25) | open |
| N-16 | MCP-created document is active (title `* tc11-18`) with no MDI tab and no tree entry | Low | TC-11-18 | `evidence/tc-11-18-after.png`; P9 B10 | product defect | open |
| N-17 | Negative radius explanation `ValueError: Invalid constraint index: 4` does not name the value | Low | TC-03-15 | F-P2-5 (also in 2026-10-03-04) | product defect | open |
| N-18 | `query_mass_properties` `com` null for Compound-shaped PartDesign results | Low | TC-04 | `usecases/queries.py:591-596` | observation | open |
| N-19 | `query_mass_properties` bbox `xmax` 10.0 before Show All, 9.98 after | Low | TC-12 | F-P10-3 | observation | open |
| N-20 | MCP render face tones inverted against the window; no Then compares tone | Low | TC-06-03 | P0 F6; `runner/tc-06-03-default.png` | observation | open |
| N-21 | Scenario file regex `"\bFillet\b"` is a JSON backspace (U+0008), so the runner FAILs TC-08-04 | High | TC-08-04 (graded PASS, D-lead-2) | `tests/uat/scenarios/tc-08-04.json:487` | test asset defect | open |
| N-22 | Test-case text with no verdict effect: `query_mass_properties Body` refused (`TC-05:50`); re-import recipe fails for `Mesh::Feature` (`TC-07:26-27`); "first tree line" (`TC-07:51`); `tool_surface.json` has no producer (`TC-11:233`); `launch_app` cannot set profile or env (`TC-02:368-371`); hide step should name the context-menu route (`TC-02:240`) | Low | TC-05-01, TC-07, TC-11-04, TC-02-09, TC-02-05 | as cited | test-case defect | open |
| N-23 | P0 evidence `tc-05-03-mcp.jsonl` holds full (expired) `fcb-preview` tokens | Low | TC-05-03 | F-P4-7 | evidence hygiene | open |
