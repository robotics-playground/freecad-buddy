# Story 10-10: verifier report

Commit `b5064f1` (base `031d8e8`). Verifier: independent of the builder. Evidence folder:
`tests/uat/run/2026-11-18-10-10-verify/` (each `.txt` has the command line first; `evidence/` holds
the captures). FreeCAD 1.1.4 in `fcb-desktop`, started by `fcb-freecad start`, stopped at the end;
container left up.

## Verdict

**FAIL** — two commands written in the test plan and test cases do not work in the container
(Q4/AC2), and one verify clause became always-true (Q2). All other rows hold.

## Defects

| # | Severity | Where | Finding | Evidence |
| --- | --- | --- | --- | --- |
| D1 | medium | `TC-13-gui-mcp-parity.md:221-223` (TC-13-03), `TC-13:744`, `TC-06-render-and-gui-visual-fidelity.md:330`, `TC-02-document-ingestion-and-handles.md:240`, `test-plan.md:333`, `APPENDIX-B-environment-setup.md:262`, `TC-12-gui-workflows.md:46` | Toggle Visibility route fails as written. `click` by `element_token` on the `Box` tree item does not select it: `Gui.Selection.getSelection()` stays `[]` (background and foreground). `press_key` `space` with the tree item `element_token` prints `AT-SPI Component.GrabFocus returned false for element 530` (exit 0) and the tree stays `- [FEATURE] Box`; the case's own foreground retry fails the same way. A route that worked: foreground pixel `click` on the row (window coordinates from the screenshot), then window-level `press_key` `space` foreground: selection `['Box']`, tree `v [FEATURE] Box`. | `K2-toggle-visibility.txt`, `evidence/tc-13-03-hidden.png`, `evidence/v-after-toggle-undo-recompute.png` |
| D2 | medium | `test-plan.md:333`, `TC-12-gui-workflows.md:46`, `APPENDIX-B-environment-setup.md:262` | Recompute key is wrong. The container's `Std_Refresh` shortcut is `F5` (`FreeCADGui.Command.get('Std_Refresh').getShortcut()` returns `'F5'`). `hotkey` `["ctrl","r"]`, background and foreground, left `Box.State` `['Touched']`; `press_key` `f5` foreground gave `['Up-to-date']`. The statement "`Recompute` is not listed" is also wrong while the document must recompute: the snapshot lists `menu item 'Recompute'` (enabled) and `push button 'Recompute'`, and pressing the leaf recomputed (`['Up-to-date']`). The case steps `TC-12:429` and `TC-13:913` (leaf press, toolbar fallback) work. | `K2-recompute.txt` |
| D3 | medium | `TC-01-session-lifecycle-and-transport.md:639` (base `:638`) | The verify clause still has the bare host command `` `grep "spawned MCP proxy" addon.log` returns nothing ``. The host has no `addon.log`, so the check passes with no evidence (always-true). Lines `:638` and `:640` of the same Then block were changed to `docker exec ... "$FCB_USER_DIR/freecad-buddy/addon.log"`; this one was missed. | `then-verify-diff.txt` row `TC-01...:638 hand [K3]` |
| D4 | low | `TC-01-session-lifecycle-and-transport.md:361` | Sub-check dropped with no reason: before `` `$APPDATA/FreeCAD/Mod/` is legacy and empty ``, after only the discovery path. The `hand` reason names only the APPDATA rewrite. | `hand.txt` pair (`q2-hand-pairs.txt`) |
| D5 | low | `TC-01-session-lifecycle-and-transport.md:578` | Verify clause still says "the `LISTENING` pid on `:8765`"; `ss` prints `LISTEN`. Wording only. | — |
| D6 | low | `quality-bar-10-10.md` Q1 vs spec "Then lines that change" | Q1 allows only `TC-01:368`; the spec also lists `TC-09:403`. `then-check.py` without `--allow ...TC-09...:403` exits 1. Meaning of TC-09:403 holds (see Q1). Leader aligns the bar. | — |
| D7 | low | `TC-11-security-posture-and-artifact-hygiene.md:312` | "reports connection refused": container `curl -sS` prints `Couldn't connect to server` (exit 7). Same words as the base check; `nc -zv` prints `Connection refused`. | `K9.txt` |

## Per quality-bar row

| Q | Result | Decisive evidence |
| --- | --- | --- |
| Q1 | proven (with the spec's two listed lines) | My run: `then-check.py --allow TC-01...:368 TC-09...:403` → 2340 lines, 370 changed clauses, 0 failures, exit 0. Without `--allow`: exactly those 2 fail. Mutant A (worktree copy, `TC-11:187` head `**Then** NOT ...`) → exit 1. Mutant B (delete an `And` under a Then in `TC-13`) → `Then/And count 146 -> 145`, exit 1. A deleted `And` under a When is not covered (D2 freezes Then only). TC-01:368: Windows exception removed; `ls -l` measured `-rw-------` and `stat -c %a` = `600`, so the observable "restricted" holds. TC-09:403: same result (`<H>` active, `list_windows` title names the document); my run of `Next` leaf presses reached `* box-10-20-30 - FreeCAD 1.1.4` (`K2-menu-new-next.txt`). |
| Q2 | not proven | Read all 63 `hand` pairs and 58 `rule` pairs (every 9th K1 line, all 5 K3, all 21 K7, 16 files). Rule lines: same check, container form. `ss -ltnp \| grep ":8765"` replacing `netstat ... \| Select-String "LISTENING"` is equal (`-l` lists only listening sockets; `:18765` does not match `:8765`). Hand lines: same check except D3 (always-true) and D4 (dropped sub-check). TC-01:59 dropped launcher-child check is justified: measured spawn line `pid 5005` = `ss` owner `pid=5005`. |
| Q3 | proven | `census.sh` at `b5064f1`: K1..K10 and ANY = 0. At `031d8e8` (worktree): 635/9/64/51/19/45/36/78/34/11/17, ANY 905 — equal to `census-before.txt`. Extra greps: `.ps1`, `Start-Sleep`, `$env`, `cmd`, `pythonw`, `.venv`, `APPDATA`, `SetForegroundWindow` = 0. Remaining hits are not host commands: `Windows` (FreeCAD menu name), `C:` (prose "Direction C:", `${...:-unset}`), `%` (`%{http_code}`, Python `% 4`), `\` (line continuations), "Access is denied" (kept remark), `127.0.0.1:8765` (inside `docker exec` or `"$FCB_PYTHON"`, which runs in the container). |
| Q4 | not proven | One step per kind, my choice, as written: K1 `TC-13-03` screenshot to `$RUN_DIR` (file on host); K1b `TC-06:39` `status`; K2 `New Document` and `Next` leaves; K3 `TC-01:59`, `TC-01:364`; K4 `TC-01:363` (`4911 freecad`), dead-pid `ps -p` exit 1; K5 `TC-01:60` `/proc` cmdline, `TC-01:61`, `TC-12:764`; K6 `TC-06:596` (key unset, allowed); K7 `TC-01:58`, `TC-01-09` cat and `ls -l`; K8 `TC-01:197` hashes equal (`ca78f505...`), `TC-11:859` count 0; K9 `TC-11:258` `172.20.0.2`, `TC-11:312` refused, `TC-11:313` `307`, `TC-10:528` relay `freecad_pid` 4911, `TC-01:605` `HTTP/1.1 200 OK`; K10 `TC-07:365` prints `1`, `TC-01-03` When prints `46`, `TC-10:159` connect exit 0. The three unmeasured menu commands: Undo `ctrl+z` (`TC-13:810`) works (`BoxRenamed` → `Box`, undo stack empty); Recompute key fails (D2); Toggle Visibility fails (D1). |
| Q5 | proven | `test_fcb_cua_wrapper.py` + `test_fcb_py_wrapper.py`: 30 passed. Mutant in a worktree copy of `fcb_paths.sh` (plain `${value//"$root"//repo}`, boundary removed): 3 red (cua sibling, cua flag-in-JSON, py sibling). Mutant `"$root_backslash"*` (backslash boundary removed): 2 red (cua and py backslash sibling). `fcb_py.sh` sources `fcb_paths.sh` and its tests pass. |
| Q6 | proven | `NOT APPLICABLE` appears in no test case; build notes say 0. TC-10:608 and TC-11:355 keep a container check (measured `stat` = `600`). |
| Q7 | proven | Missing hard breaks: only TC-15, 37 = base 37. Machine path: only `TC-16:23`, byte-equal to base. 17 files; 274 `### TC-` headings, identical list. |
| Q8 | proven | `git diff --stat 031d8e8 b5064f1 -- src tests/uat/scenarios tests/uat/runner scripts/automation/uat_watchdog.py` empty; no existing run folder changed (only `2026-11-18-10-10-proof/` added). |
| Q9 | proven | `ruff check .` all passed; `check_imports` OK; `ruff format --check` on the 2 changed `.py`: already formatted; `pytest tests/external -q`: 1782 passed, 4 skipped, exit 0. |
| Q10 | proven | `sha256sum "$APPDATA/FreeCAD/v1-1/user.cfg"` = `b89a97711941619bb0ba74ae04fb888025e82f49ff48174fbebb42aed28d85a0`. Container `user.cfg` read only (`grep`, `ls -l`). |

## Notes (no action needed)

- `press_key` that fails `GrabFocus` still exits 0 through `fcb_cua.sh`; the driver prints the error
  as text. A tester must read the output, not the exit code.
- `fcb_py.sh` warned `FREECAD_BUDDY_WORKDIR=C:\Users\...` — that variable came from the verifier's own
  host environment; the warning is the designed behavior.
- `TC-11:308` runs `uv run python -m freecad_buddy.hosts.main serve ... --host 0.0.0.0` on the host:
  it tests the CLI parser of `src/`, not the image copy. Not a host-only command.
- `TC-01:58`: `addon.log` in the container holds one `spawned MCP proxy` line per launch (8 lines);
  the check reads the last one.

## Re-run at 355690e

Commit `355690e` (fix round 1 on `b5064f1`). Evidence: `tests/uat/run/2026-11-18-10-10-verify/rerun-355690e/`.
FreeCAD started with `fcb-freecad start` (pid 8790), stopped at the end; container left up.

### Verdict

**FAIL**. D1 to D5 and D7 are fixed and proven. The re-run found two new medium defects at
tree-row sites in rewritten scenarios: the TC-13-15 rename editor, and the `selected: true`
check in TC-12. Both fail as written in the container.

### Rows

| Row | Result | Evidence |
| --- | --- | --- |
| D1 | proven | Site 1, TC-13-03 as written: the rows PNG gives the `Box` row at (80,175). Before: selection `[]`, `- [FEATURE] Box`. After the foreground pixel `click`: selection `['Box']`. After the window-level `space`: `v [FEATURE] Box` (`D1-site1-TC-13-03.txt`). Site 2, TC-02:240 as written, Pad row at (91,228): selection `['Pad']`, `v [PAD] Pad` became `- [PAD] Pad`. The TC-02:243 restore gave `v` again (`D1-site2-TC-02-05.txt`). The `Body` row had to be expanded first; the case does not say to do that (low, below). I read every changed tree-row site. TC-13-03 and TC-13-14 name the selection read and the marker as the verdict. The select-only sites (TC-13-02, -05, -07, TC-12-04) are followed by a status-bar, property-panel or title check. Measured: after the select, the status bar reads `Valid, Internal name: Pad`. |
| D2 | proven | `D2-recompute.txt`. Box `['Touched'], True` became `['Up-to-date'], False` three times: with the `Recompute` menu leaf (TC-12:429), with `press_key f5`, and with `hotkey ["f5"]`. |
| D3 | proven | TC-01:639 as written prints this launch's `spawned MCP proxy` lines, so "returns nothing" fails. The old host form gives `grep: addon.log: No such file`, exit 2 (`D3-tc01-639.txt`). `sweep-state-files.py`: 0 hits at `355690e`, and 1 hit at `b5064f1` (that same line) (`D3-sweep.txt`). The sweep does not cover prose. My prose grep found no command without its location. It did find expected values in Windows path form (new defect N3). |
| D4 | proven | `ls "$FCB_USER_DIR/../Mod"` gives `No such file or directory`, exit 2. `/home/cua/.local/share/FreeCAD` holds only `v1-1`. The `then-verify-diff.txt` row is tagged `hand` with a reason. |
| D5 | proven | `LISTENING` remains only in the TC-01:59 head (frozen) and in TC-01:65 prose. |
| D7 | proven | `curl: (7) Failed to connect to 172.20.0.2 port 8765 after 0 ms: Couldn't connect to server`, exit 7. This matches the new TC-11:312 text. |
| then-check | proven | 2340 lines, 371 changed, 0 failures, exit 0. The planted head edit in a worktree copy at `355690e` (TC-11:187) gives exit 1. The diff changes only the reason table and the reason order. |
| census | proven | K1..K10 and ANY are 0. |
| gates | green | `ruff check` passed. `check_imports` OK. `ruff format --check` on the 4 changed `.py` files: already formatted. `pytest tests/external`: 1782 passed, 4 skipped. |
| Q10 | proven | `user.cfg` SHA-256 still starts with `b89a97711941619bb0b`. |

### New defects

| # | Severity | Where | Finding | Evidence |
| --- | --- | --- | --- | --- |
| N1 | medium | `TC-13-gui-mcp-parity.md:797-802` (TC-13-15) | The new route works up to the editor: the pixel select and the window-level `F2` open the inline rename editor (seen in `evidence/tc-13-15-editing.png`). The next step then fails as written. The snapshot has no element for the editor (roles: menu item, push button, list item, tree item, check box, button menu, page tab list, scroll bar, combo box, 4 `text`, none of them the editor). So `set_value` and `press_key enter` on `<rename editor token>` have no target. What worked: window-level `type_text "PadRenamed"` (foreground), then window-level `enter`. Result: `Pad "PadRenamed"`, and `ctrl+z` restored `Pad`. Line 802 also says `type_text` must not be used. | `D1-TC-13-15-rename.txt` |
| N2 | medium | `TC-12-gui-workflows.md:272` (Then verify), `:307` (When "confirm the row reads `selected: true`"), `:89` (rule text "`selected: false`") | In the container a tree item has no `selected` field. While `FreeCADGui.Selection` names `Box`, every `Box` tree item in the snapshot has `selected=None`. A check on `selected: true` cannot pass. Read the selection with `script_exec` instead, as test-plan §6 says. The text existed at the base; line 307 was rewritten in this round. | `D1-selected-state.txt` |
| N3 | low | `TC-99-ad-conformance-gaps.md:205`, `:318` (Given verify), `:223`, `:333` (Then verify text) | The expected values use the Windows path form `<FreeCAD user app data>\freecad-buddy\workdir` and `...\audit.jsonl`. The container log prints `FREECAD_BUDDY_WORKDIR='/home/cua/.local/share/FreeCAD/v1-1/freecad-buddy/workdir' (default)`. TC-11:875-880 got this fix; TC-99 did not. The census does not count it, and my round-1 grep missed it. | `docker exec ... grep` of the live `addon.log` |
| N4 | low | `test-plan.md:332-333`, `APPENDIX-B-environment-setup.md:261-262`, `TC-12-gui-workflows.md:47-48` | Two wrong claims. "`Recompute` is listed while a document is open": it is not listed while the open document is clean, only while it must recompute. "`Toggle Visibility` is not listed": it is listed while an object is selected (`menu item 'Toggle Visibility'` in the snapshot). TC-12:307 says this correctly. | `D2-recompute.txt` ("clean: NONE"), `D1-selected-state.txt` |
| N5 | low | `TC-02-document-ingestion-and-handles.md:240` | The `Pad` row is visible only when `Body` is expanded. A new Body opens collapsed, and the step does not say to expand it. I clicked the expander at (17,193), foreground. | `D1-site2-TC-02-05.txt` |

## Re-run at 5ee4824

Commit `5ee4824` (fix round 2 on `355690e`). Evidence: `tests/uat/run/2026-11-18-10-10-verify/rerun-5ee4824/`.
FreeCAD was started with `fcb-freecad start` (pid 16744). I killed it once on purpose, the restart ran as pid
17961, and FreeCAD is stopped at the end. The container is left up.

### Verdict

**PASS with low findings.** N1 to N5 are fixed and proven. The 5 C1 rows that I ran work as
written. This run found no new medium defect of the GUI-route class, so the stop rule of triage v2
does not trigger. Two low findings remain: one weakening of a GUI check (accepted, recorded) and one
claim that is not always true.

### Rows

| Row | Result | Evidence |
| --- | --- | --- |
| N1 | proven | TC-13-15 as written on `box40-hole-r5`: pixel click on the `BoxHole` row, window-level `f2`, `ctrl+a`, `type_text` (reports `delivery_failed`, as the case says), `Return`. Tree: `BoxHole` became `BoxHole "BoxHoleRenamed"`; after `ctrl+z` it was `BoxHole` again (`N1-TC-13-15.txt`). |
| N2 | proven | TC-12-04 route: a foreground pixel click on the `box40-hole-r5` row set the title to `* box40-hole-r5 - FreeCAD 1.1.4` and `G.ActiveDocument.Document.Label` to `'box40-hole-r5'`. A click on the `sphere-r10` row set both back to `sphere-r10`. The tree re-lays out after each click, so take a new screenshot before the next click (`N2-TC-12-04.txt`). TC-12:308: `Gui.Selection` read `['Sphere']` after the row click (`N4-menu-listed.txt`). |
| N3 | proven | The live `operator settings:` line prints `FREECAD_BUDDY_WORKDIR='/home/cua/.local/share/FreeCAD/v1-1/freecad-buddy/workdir' (default)`, and the same form for `AUDIT_LOG`. TC-99 now expects `<FreeCAD user app data>/freecad-buddy/...` (`N3-tc99-paths.txt`). |
| N4 | proven | `N4-menu-listed.txt`. With no selection, a clean document and no undo entries, the listed leaves were Undo/Redo/Recompute/Toggle Visibility = False/False/False/False. With an object selected and the document touched: Toggle Visibility True, Recompute True. After a transaction and F5: Undo True, Recompute False. After `ctrl+z`: Undo False, Redo True. |
| N5 | proven | TC-02:240: before the expand, `Pad` is not in the tree items. A foreground click on the `Body` arrow (17,211) lists `Pad`. The pixel click on the row plus a window-level `space` changed the marker from `v [PAD] Pad` to `- [PAD] Pad` (`N5-TC-02-240.txt`). |
| C1 row 15 | proven | TC-12-10 as written: combo box token click, then a foreground pixel click at the `Sketcher` item centre (screen frame minus the window origin). Workbench `PartDesignWorkbench` became `SketcherWorkbench`, and the Then `verify_state` returned `satisfied` (`C1-workbench-combo.txt`). |
| C1 row 19 | proven | Window-level `press_key` in the foreground (`f2`, `Return`, `space`) gave the effects in N1 and N5. |
| C1 row 31 | proven | TC-14:474-493 as written, hex wid `0x02400062`: the `wmctrl` un-maximize, then `set_window_frame` width 960, gave `list_windows` `(5, 56, 960, 949)`. The restore and re-maximize gave `(0, 51, 1600, 949)` (`C1-set-window-frame.txt`). |
| C1 row 29/48 | proven | TC-12:362 `script_exec {code:"result = list(doc.UndoNames)"}` returns `['buddy: verify pad length']`. My own extra check: a foreground pixel click on the Undo arrow (158,37) opens no popup (`list_windows` lists only the main window; `evidence/undo-arrow.png`). The route limitation is real. |
| C1 row 8 | proven | `Isometric` push button by token: camera Q changed from `[0,0,0,1]` to `[0.4247,0.1759,0.3399,0.8205]`. `1 Front`: `[0.7071,0,0,0.7071]` (`C1-standard-view-buttons.txt`). |
| then-check | proven | 2340 lines, 379 changed, 0 failures, exit 0. My planted head edit (TC-11:187, in a worktree copy at `5ee4824`) gave exit 1. The diff adds only reason entries. |
| census, sweep | proven | Census ANY 0. `sweep-state-files.py`: 0 hits. |
| gates | green | `ruff check`: all checks passed. `check_imports` OK. `ruff format --check` on the 4 changed `.py` files: already formatted. `pytest tests/external`: 1782 passed, 4 skipped. |
| Q10 | proven | `user.cfg` SHA-256 still starts with `b89a97711941619bb0ba`. |

### Q2 judgement on the changed checks of this round

- **TC-12:388-395 (TC-12-06), low, accepted weakening.** The Then "the Undo entry names the bridge's
  transaction" was a check of a visible GUI element (the dropdown entry and its painted label). It is now
  a document read, `doc.UndoNames`. GUI evidence that remains: the `Undo` leaf or button is enabled, and
  the after-capture is still checked. The dropdown cannot be opened in the container (measured by the
  builder and by me), so no visual route exists. The leader records this as a route limitation of the
  container. The GUI rendering of the transaction name is no longer checked.
- TC-12:272: `selected: true` is replaced by the window title (visible) plus the active-document read.
  The visible part remains. Not a weakening.
- TC-12:442, TC-99 lines, TC-02:240: same check, container form.

### New findings

| # | Severity | Where | Finding | Evidence |
| --- | --- | --- | --- | --- |
| R1 | low | `test-plan.md:365` | Not always true. I killed FreeCAD with `kill -KILL` while 3 modified documents were open, all opened less than 15 minutes earlier. The next start showed no `Document Recovery` window: only `FreeCAD 1.1.4` was listed for 60 s, and the Start page was in front (`GUI-document-recovery.txt`, `evidence/after-kill-start.png`). Recovery needs recovery files, and the autosave timer writes them. Write "can show". The builder's own record also shows `Cleanup`, then a `Delete` window with `Yes`, not "`Yes`, then `OK`". | — |
| R2 | low | prose verify clauses `TC-01:363`, `TC-10:43`, `:146`, `TC-14:191`, `:229`, `:466`, `:484`, `TC-15:137`, `:154` | `"$FCB_CUA" list_windows` with no JSON on standard input: in an interactive terminal the wrapper waits on `cat` until end of input. With `</dev/null` it works and lists the windows (`prose-list-windows.txt`). An `echo '{}' \|` prefix makes the call a copy-paste command. | — |

Not run: the first-run Welcome panel claim. A new container profile is needed to see the panel, and
this profile is not new.

## Re-run at 498b53d

Commit `498b53d` (red-team fix round on `5ee4824`). Evidence: `tests/uat/run/2026-11-18-10-10-verify/rerun-498b53d/`.
FreeCAD was started with `fcb-freecad start` (pid 22338) and stopped at the end; no proxy is left
running and the container is up. Rule for this run: every test-case line was copied as written. In the
round at 5ee4824, my N2 run used my own `script_exec` call form instead of the text, so RT-2 was not
caught.

### Verdict

**PASS.** RT-1 to RT-5, R1 and R2 are fixed and proven. One low finding (V1).

### Rows

| Row | Result | Evidence |
| --- | --- | --- |
| RT-1 | proven | Ran TC-10:185 as written (the same text as :260, :558, :595) on port 41781. With the proxy up, `ss -tnp \| grep ":41781" \| grep ESTAB` printed 2 `ESTAB` rows (python pid 22429 and freecad pid 22338). The old `ss -ltnp ... \| grep ESTABLISHED` printed nothing. After the proxy was stopped, the new check printed nothing, exit 1. The proxy was restarted by hand (test-plan §6) and `/healthz` then served `freecad_pid` 22338 (`RT1-established.txt`). |
| RT-2 | proven | TC-12:273 and test-plan.md:347, copied as written with a doc handle, returned `OK` `'rt3-verify'` and `OK` `['B17']`. The form without `doc` returned `Input validation error: 'doc' is a required property`. The builder's `run-script-exec-sites.py` (run in the container) gave 7 sites, all `status=OK`. My own sweep over the test cases, test-plan and APPENDIX-B found 84 `script_exec {` calls, 0 without `doc` (`RT2-script-exec.txt`, `RT2-my-sweep.txt`). |
| RT-3 | proven | Ran the "Pixel points" rule on a 40-box document, with a new screenshot snapshot before each click. The reply has `screenshot_width` and `screenshot_height` 1568 x 930. B16: frame y=491, converted point (132,440), selection `['B16']`. B17: window y 467, selection `['B17']`. B18: window y 485, point (132,475), selection `['B18']`. B12: selection `['B12']` (`RT3-pixel-points.txt`). See V1 for a row outside the visible tree. |
| RT-4 | proven | Wrapper tests: 32 passed. Mutant in a worktree copy, `... cua-driver call "$@"' _ "$@" \|\| true`: `test_Should_return_the_exit_code_of_docker_When_it_fails[arguments0]` went red (`RT4-exit-code.txt`). |
| RT-5 | proven | TC-01:83 as written, with the GUI proxy up (`serve --mode rpc --transport http`, pid 22429): no output, exit 1. With a stray headless host (`"$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline`): 3 lines (the `AppRun` wrapper, `hosts.main serve --transport stdio` and `hosts.headless.worker`), exit 0, so the check fails as it must (`RT5-tc01-83.txt`). |
| R1 | builder text is right | test-plan.md now says: `Cleanup` opens a `Cleanup` window (`Yes`, `No`), `Yes` opens a `Delete` window (`OK`), and `OK` closes it. This matches the builder record `C1-document-recovery.txt` (window list `Document Recovery`, `Cleanup`, then `Delete`, then only the main window). It also matches the FreeCAD source: `DocumentRecovery::onButtonCleanupClicked` (`DocumentRecovery.cpp:681-705`) shows `QMessageBox` "Cleanup" with `Yes \| No`, then `DlgCheckableMessageBox::showMessage(tr("Delete"), ...)`, which has an OK button. My round-2 note "Cleanup -> Delete / Yes" was imprecise. "can show" also matches my round-2 kill run, where no Recovery window appeared. |
| R2 | proven | `sweep-cua-stdin.py`: `calls without stdin: 0`. My own grep over the test cases, test-plan and APPENDIX-B: 0. TC-14:191 `echo '{}' \| "$FCB_CUA" list_windows`, pasted with a standard input that stays open (as a terminal does), printed the window list at once. The old prose form with the same open input timed out: `timeout` exit 124 (`R2-cua-stdin.txt`). |
| exit-code sentence | present | test-plan.md §6 "Pixel points": "`cua-driver` exits 0 on a tool error ... judge a step by the text it prints". This matches round 1 (`GrabFocus returned false`, exit 0). |
| then-check | proven | 2340 lines, 379 changed, 0 failures, exit 0. The planted head edit in a worktree copy at `498b53d` (TC-11:187) gave exit 1 (`then-check-planted.txt`). |
| census, sweeps | proven | Census ANY 0; `sweep-state-files.py` 0 hits. |
| gates | green | `ruff check`: all checks passed. `check_imports` OK. `ruff format --check` on the 6 changed `.py` files: already formatted. `pytest tests/external`: 1784 passed, 4 skipped. |
| Q10 | proven | `user.cfg` SHA-256 = `b89a97711941619bb0ba74ae04fb888025e82f49ff48174fbebb42aed28d85a0`. |

### New finding

| # | Severity | Where | Finding |
| --- | --- | --- | --- |
| V1 | low | `test-plan.md` §6 "Pixel points" (the frame conversion) | A row outside the visible part of the tree still has an element with a `frame`. On the 40-box document, `B30` has frame y=743 (converted point y=687), and the tree panel shows rows only up to `B19` (`evidence/rt3-before-B30.png`). The converted point lands in the property panel, and the selection stays `['B16']`. The rule should say that the row must be visible: scroll the tree first (C1 row 27, a foreground pixel `scroll` inside the tree rows). The selection read catches the miss, so no wrong verdict follows. |

### Incident during this run (fixed)

A `git worktree add` into the scratchpad failed without a message, and my script then ran the planted
TC-11:187 head edit (`**Then** NOT ...`) in the main working tree. I found it with `git diff`, restored
the file with `git checkout -- tests/uat/testcases/TC-11-security-posture-and-artifact-hygiene.md`, and
confirmed that `git diff --quiet 498b53d -- tests/uat/testcases` passes. I then re-ran `then-check.py` (0
failures) and ran the planted edit again in a worktree whose top level I checked first. No other file
was touched.
