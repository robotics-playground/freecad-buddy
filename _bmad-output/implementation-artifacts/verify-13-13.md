# Verify 13-13: `script_exec` observe-only bracket

Verifier: verifier-13-13. Date: 2026-11-25. Commit under test: `fba56e57` on `story/13-13-script-exec-bracket` (worktree `D:/Work/Personal/Sources/freecad-buddy-wt-13-13`).

**Verdict: PASS.** Gates green, 6 of 6 mutants killed, Q1-Q15 met. Container UAT: 8 PASS, 0 FAIL. Some runner sub-checks are NOT RUN (runner limit, listed below). No product defect.

Scope note: after my container run (container build 22:34), another agent changed `src/freecad_buddy/usecases/script_exec.py`, `hosts/tool_catalog.py`, `tests/infc/test_script_exec_bracket.py` and `mcp-tools-design.md` in wt-13-13 (uncommitted, dated 22:58). This report covers `fba56e57` only. The image ran the committed file: installed `script_exec.py` SHA-256 `a4cc782c...` = `git show fba56e57:src/freecad_buddy/usecases/script_exec.py`.

## 1. Gates at fba56e57

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `check_imports.py` | OK |
| `check_status_vocab.py` | OK |
| `gen_schemas.py --check` | OK |
| `check_skill_shape.py` | exit 0 |
| `check_provenance.py` | OK |
| `uv run --extra dev pytest tests/external -q` (Git Bash) | **2117 passed, 6 skipped, 0 failed** (189.9 s). The two known intermittent tests passed in the full run, so no re-run was needed. |
| `freecadcmd -u <tmp>/user.cfg -s <tmp>/system.cfg tests/run_tests.py`, private `FREECAD_USER_HOME` | **Ran 1311 tests, OK (skipped=1)** (128.8 s) |

AC5 timing in that run: `script_exec on 30 objects x 406 faces took 3.81 s` (budget 30 s). Mutant runs printed 8.5 s.

## 2. Mutants

Copy: `git archive fba56e57` into `scratchpad/verifier-13-13/mut-13-13` (removed after). Runner: only `tests/infc/test_script_exec_bracket.py` under `freecadcmd` with private cfg and `FREECAD_USER_HOME`; it printed the imported `script_exec.py` path from the copy. Baseline 57/57 OK.

| Mutant | Change | Result |
| --- | --- | --- |
| M1 commit step skipped | `document.commitTransaction()` -> `pass` (`script_exec.py:214`) | KILLED, 2 failures (`..._When_the_document_commit_raises`, `..._When_the_recompute_and_the_commit_raise`) |
| M2 app-level close skipped | `shim.commit_active_transaction` body -> `return None` (`shim.py:440-443`) | KILLED, 5 failures + 1 error (read-only no transaction, other-document undo x2, closed document, commit-raises x2) |
| M3 repr guard removed | `_value_repr` returns `repr(value)` with no `try` (`script_exec.py:102-106`) | KILLED, 2 errors (deleted object as `result`, closed document as `result`) |
| M4a alignment head only | drop `or remaining == before[size - len(remaining):]` (`script_exec.py:82`) | KILLED, 3 failures (`UndoStackTest`) |
| M4b alignment tail only | drop `remaining == before[: len(remaining)] or` | KILLED, 2 failures (full-stack cases) |
| M5 SystemExit not caught | `except BaseException` -> `except Exception` (`script_exec.py:251`) | KILLED: the `SystemExit` escaped and ended the test process (`Exception while processing file: tests/run_bracket.py`) |

## 3. Quality bar Q1-Q15

| Q | Evidence | Result |
| --- | --- | --- |
| Q1 | `tests/infc/test_script_exec_bracket.py:62` (one step, object listed), `:81` (`matches_pre_op` after `document_undo`); container: `write` returned `OK`, `changed` [Box], `undo_steps` 1; `document_undo` with `expect_fingerprint` `07a23484...` returned `matches_pre_op: true`, Length back to 10 mm | PASS |
| Q2 | `:94`, `:111`, `:123`, `:137`, `:149`, `:166`, `:273`; M2 killed; container `readonly` `undo_steps` 0 with the "earlier step" note | PASS |
| Q3 | `script_exec.py:251` (`except BaseException`); `:304` (SystemExit, KeyboardInterrupt, GeneratorExit), `:969` (through `MethodRegistry.dispatch`, next call `OK`); M5 killed; container `SystemExit(3)` and `SystemExit(5)` -> `INVALID_INPUT` `exec.python_error`, next call served, same FreeCAD pid 882. No external pytest raises `SystemExit` through the listener: the dispatch-level infc test and the live run cover it | PASS |
| Q4 | `:384`, `:401` (pad), `:423`; container `Width = 0` -> `RECOMPUTE_ERROR` `recompute.failed_objects`, `new_errors` [Box]; runner TC-09-17 / TC-09-18 `build` -> `RECOMPUTE_ERROR`, `new_errors` [Pad], change kept | PASS |
| Q5 | `:934`, 3.81 s | PASS |
| Q6 | `:447`, `:461`, `:485`, `:497`, `:531`, `:567`, `:580`, `:605`, `:619`, `:773`; `_setup_failed` `script_exec.py:185-194`; `_envelope` `:322-327` | PASS |
| Q7 | `:273`, `:290`; `shim.commit_active_transaction` commits (`closeActiveTransaction(False)`, `shim.py:443`) | PASS |
| Q8 | `tool_catalog.py:1423` `params.get("recompute") is not False`, schema `:1431`; `:181`, `:434`, `:1004`; `gen_schemas --check` OK; runner TC-12-07 `touch` with `recompute:false` -> `value_repr` `['Touched']` | PASS |
| Q9 | `framing.py` `fresh` parameter; `tests/external/test_framing_envelope.py:617`, `:638`, `:658` | PASS |
| Q10 | `:898`; spine AD-27 line 249: "for `script_exec` the late return commits and nothing aborts it" | PASS |
| Q11 | `rpc_dispatch.exec_digests`; `tests/external/test_rpc_listener.py:562` (both digests), `:588` (TIMEOUT, no digest); same call in `mcp_server.py` | PASS |
| Q12 | `grep -rniE "runs? raw|raw python|raw exec" skills/ <architecture>/` -> no hit; `exec.bracket_failed` in `data-contracts-design.md:64`, `mcp-tools-design.md:845`, `sequence-diagrams.md:477`, `verification-design.md:39`; `undo_steps` in `skills/freecad-scripting-idioms/SKILL.md:60-63`; AD-5 other-document sentence present (spine line 77) | PASS |
| Q13 | `git diff 7549c1d4..fba56e57 -- src/freecad_buddy/contracts` is empty; version tests pass in the external run | PASS |
| Q14 | Section 1 | PASS |
| Q15 | Section 4: write then `document_undo` restores; failing script `INVALID_INPUT`, bridge up; GUI undo list shows one named entry per call | PASS |

## 4. Container UAT (run `tests/uat/run/13-13-r1/`)

Setup: `build_addon.py --release` and `compose up -d --build` from wt-13-13; `docker inspect` shows `D:\...\freecad-buddy-wt-13-13 -> /repo`; installed `script_exec.py` hash = fba56e57; `fcb-freecad start` first try; `/healthz` `freecad_pid` 882. MCP client: `evidence/mcpcall.py`; call lists `evidence/calls-*.json`; results `evidence/out-*.json`.

| Case | Result | Evidence |
| --- | --- | --- |
| Q1/Q15 live write + `document_undo` with `expect_fingerprint` | PASS. `write` `OK`, `changed` [Box], `undo_steps` 1. `document_undo` text: `Undid "script_exec doc.getObject('Box').Length = 25" on V1313Core: restored the pre-op state (273eefd0a4f2 -> 07a23484713e).`, `matches_pre_op: true` | `out-a1.json`, `out-a2.json` |
| Q15 GUI undo stack | PASS. The Undo toolbar drop-down lists exactly two entries, one per call: `script_exec doc.getObject('Box').Length = 25` and `script_exec b = doc.addObject('Part::Box', 'Box')` | `q15-undo-list-desktop.png` |
| Q15 failing script, bridge stays up | PASS. `SystemExit(3)`, `ValueError` after a write (change kept, Height 30 mm, `undo_steps` 1, text `...; the changes it made so far are kept`), `SyntaxError`, `RuntimeError`, `SystemExit(5)`: each `INVALID_INPUT` `exec.python_error` with the traceback cut at the script frame. `/healthz` pid unchanged; next calls served | `out-a2.json`, `out-a3.json`, `out-a4.json` |
| GUI no notification for a failing script (deferred-work entry) | PASS. No dialog. The status-bar notification count stayed 1 across four failing scripts. The one notification is `Box: Width of box too small`, which FreeCAD writes for the `Width = 0` recompute error (a normal recompute error, not a script exception) | `q15-after-failing-script-desktop.png`, `q15-after-failing-script-2-desktop.png` |
| TC-08 fixtures starting with `FreeCAD.closeActiveTransaction()` | PASS. `fx1` and `fx2` `undo_steps` 0; `document_undo` -> `RECOMPUTE_ERROR`, `undone` `buddy: create body Probe`, `errors` [Box]; the next undo -> `nothing to undo on UndoOff: the undo stack is empty` | `out-b-tc08.json` |
| TC-03 edit-mode probe, `recompute: false` | PASS. With the sketch in edit mode, a read-only `script_exec` with `recompute:false` returned `OK`, `undo_steps` 0, and edit mode stayed open (Sketch Edit task panel and axis cross on screen). The default `recompute` call did the same. Observation: `setEdit` and `resetEdit` each record one undo entry (`undo_steps` 1). TC-03 never undoes after them; I added one sentence to the TC-03 precondition so a later case does not | `out-c-editmode.json`, `tc03-editmode-open.png`; `tests/uat/testcases/TC-03-sketch-authoring.md:31` |
| R2-D probe: close ignored under a GUI command guard | MEASURED (deferred item, no defect in this Story). A Python command run through `FreeCADGui.runCommand` (`Command::_invoke` holds `App::AutoTransaction committer(nullptr, true)`, `Gui/Command.cpp:452`) called `_run_bracket`. Result `OK`, `undo_steps` 1 (no wrong "earlier step" note). After the bracket, inside the command, `App.getActiveTransaction()` was `("script_exec doc.getObject('Box').Width = 17", 28)`: the close was ignored. A second write in the same command added no undo entry, so it joined the script's entry. After the command returned, the guard closed it (`active_after_command` None). Effect is limited to the rest of the same command; the bridge runs from the pump, outside a command | `out-d-guard.json` |
| Runner `tc-02-06` | PASS on scripted checks and on the closing capture: restored pad, no error marker on `Pad`, Recompute disabled; `exec_break` with `recompute:false` -> `OK`, then `document_recompute` -> `RECOMPUTE_ERROR` naming Pad. NOT RUN: the Given "before" capture (the runner takes no mid-run capture) | `runner/results.json`, `runner/captures/TC-02-06.png` |
| Runner `tc-09-17` | PASS. `build` -> `RECOMPUTE_ERROR`; capture: `Pad` carries the error icon, last valid 20 x 20 x 10 block drawn | `runner/captures/TC-09-17.png` |
| Runner `tc-09-18` | PASS. `build` -> `RECOMPUTE_ERROR`; capture: `Pad` error icon, no Sketch child, block drawn | `runner/captures/TC-09-18.png` |
| Runner `tc-12-07` | PASS on scripted checks and on the closing capture (taller 20 x 10 x 8 solid, no marker, Recompute disabled); `touch` with `recompute:false` -> `['Touched']`. NOT RUN: the clean-state and dirty-state GUI reads between steps (the runner takes no mid-run capture) | `runner/captures/TC-12-07.png` |

Runner summary: `4 scenarios: 0 PASS, 0 FAIL, 4 ESCALATE`, `run errors: 0`, findings and disagreements empty; ESCALATE means only the agent's visual checks were left, graded above.

Driving notes: a background pixel click on the Undo drop-down arrow went through AT-SPI to the Undo button and undid the write in the GUI (also evidence that one GUI undo reverts the whole script). I restored it with the Redo button (by `element_token`), checked Length 25 mm and the same `fingerprint_after` `273eef...`, then opened the drop-down with `delivery_mode: "foreground"`. The popup is its own X window, so `get_window_state` does not show it; `get_desktop_state` does.

Teardown: `fcb-freecad stop`; `docker compose -f tests/close-loop/docker/compose.yaml down` from wt-13-13; `docker ps` shows no `fcb-desktop`.

## 5. Defects

None in product code.

Case fix (by verifier): `tests/uat/testcases/TC-03-sketch-authoring.md:31` now says that `setEdit` and `resetEdit` each record one undo entry, so `document_undo` must not follow them to revert an earlier mutation.

Deferred item update for the leader: the R2-D entry in `deferred-work.md` ("unverified, would be medium") is now measured in FreeCAD 1.1.4 (row above). The predicted wrong "earlier step" note does not occur (`undo_steps` 1); the open transaction lasts only until the command ends.

UAT files are left uncommitted in wt-13-13: `tests/uat/run/13-13-r1/` and the TC-03 edit.
