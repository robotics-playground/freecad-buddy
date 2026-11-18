# Story 10-9: verification report

Verifier: verifier-10-9 (claude-opus-5-5, medium). Independent of the builder.
SHA tested: `9019b76c5d03e2f7c2a7569c65265618184b2e67` (base `97fac62`). The main tree equals the commit. The only other files are untracked leader files.
Date: 2026-11-18 (container clock 2026-11-17 UTC).

## Verdict

**FAIL.** Two medium findings are open. Every other check passed.

- **V-1 (AC10, Q10): the edge sweep exits 0 when the golden path is wrong.** It skips 10 of its 14 checks and reports `4/4 edge checks passed`. AC10 says that a planted wrong golden path makes the sweep exit non-zero. `run_mcp_e2e.py` meets this. `run_mcp_edge_cases.py` does not.
- **V-2 (AC1, Q1): check `mcp-session-env` read red on the committed code in 3 of 6 full `check_harness.py` runs.** The same function passed in 22 of 22 direct calls. The cause is not found. Thus the check is either flaky or it found a real race in `fcb-cua-mcp`. In both cases it does not prove AC1 reliably.

AC4 stays PARTIAL. This is the accepted deferral R1-24: `invoke_menu` refuses the FreeCAD menu bar, and I measured this again.

## 1. Gates (host)

| Command | Result |
| --- | --- |
| `uv run ruff check .` | `All checks passed!`, exit 0 |
| `uv run python scripts/check_imports.py` | `check_imports OK`, exit 0 |
| `uv run ruff format --check` on the 13 `.py` files changed in `97fac62..9019b76` | `13 files already formatted`, exit 0 |
| `uv run pytest tests/external -q` | `1752 passed, 4 skipped, 6 warnings in 99.21s`, exit 0. The known unstable test passed in this run |
| `freecadcmd.exe -u <scratch>\fccfg\user.cfg -s <scratch>\fccfg\system.cfg tests/run_tests.py` | `Ran 866 tests in 23.991s`, `OK (skipped=1)` |
| Story test files only, in the worktree (baseline for the mutants) | `208 passed in 4.69s` |

## 2. Container

The image was rebuilt from the committed tree: `build_addon.py --release`, then `compose up -d --build`. Every layer came from the cache, so the inputs are equal to those of image `sha256:ccccd43b5b3d…`. Then I ran `--force-recreate` twice to get a fresh container. FreeCAD started with `fcb-freecad start`. `/healthz` showed `freecad_pid`.

### check_harness.py

Final run, on a recreated container with FreeCAD started:

```
PASS mcp-session-env: cua-driver mcp address='unix:path=/tmp/dbus-r9vrX5BLnM,...' session address='unix:path=/tmp/dbus-r9vrX5BLnM,...'
PASS registry-childcount: Registry ChildCount=11
PASS gtk-elements-serve: Xfce4-panel element_count=4 error=None
PASS gtk-elements-mcp: Xfce4-panel element_count=4 error=None
PASS freecad-logging-rule: FreeCAD QT_LOGGING_RULES='qt.accessibility.atspi.warning=false'
PASS freecad-elements: FreeCAD element_count=346 missing menu items=[] error=None
exit 0
```

The first run after the first recreate gave `FAIL mcp-session-env: cua-driver mcp address='' session address='unix:path=/tmp/dbus-vXbQM3X2E9,...'`. The other 5 checks passed. See V-2.

### journey_box.py

`GUI: window '* CloseLoopJourney - FreeCAD 1.1.4'; solid share of the 3D view 49.7%`, `PASS`, exit 0. I read `tests/close-loop/evidence/journey-box.png`. It shows a shaded, fitted box and `CloseLoopBox` under `CloseLoopJourney` in the model tree.

### Sweeps (from the host `uv` env, H1 in the container)

| Sweep | Result |
| --- | --- |
| `run_mcp_e2e.py` | `29/29 checks passed`, exit 0, `_automation/e2e_report.json` |
| `run_mcp_edge_cases.py` | `14/14 edge checks passed`, exit 0, `_automation/edge_report.json` |
| `run_mcp_e2e.py` with `GOLDEN_DIR` planted wrong (worktree) | `4/9 checks passed`, 5 lines `[FAIL] open:<model> MISSING fixture missing`, exit 1. Red, correct |
| `run_mcp_edge_cases.py` with the same planted path | `4/4 edge checks passed`, **exit 0**. See V-1 |
| `grep -rn -E "FCB_ENV|micromamba" scripts/automation` | no hit in a source file. One hit in a `__pycache__` `.pyc`, which git ignores |

R1-9 import origin: `docker exec -u cua -e PYTHONPATH=/home/cua/.local/share/FreeCAD/v1-1/Mod/FreeCADBuddy fcb-desktop fcb-py -c "import FreeCAD, freecad_buddy; print(freecad_buddy.__file__)"` printed `/home/cua/.local/share/FreeCAD/v1-1/Mod/FreeCADBuddy/./freecad_buddy/__init__.py`. No `/repo` path is on `sys.path`. The sweeps test the installed addon.

### Watchdog (AC9), inside the container

Command: `fcb-py /repo/scripts/automation/uat_watchdog.py --pid <pid> [--since <container time>]`.

| Case | Output | Exit |
| --- | --- | --- |
| Clean (the workdir does not exist yet) | `ok temp-hygiene: temp /home/cua/.local/share/FreeCAD/v1-1/freecad-buddy/workdir/tmp: 0 snapshot dir(s) total, 0 render file(s)` | 0 |
| Folder planted in the old `/tmp` (`/tmp/FCB_TMP_snap_verify_old`) | the same `0 snapshot dir(s)` line | 0 |
| Folder planted in the bridge's real temp folder (`<workdir>/tmp/FCB_TMP_session_1_verify/FCB_TMP_snap_verify_x`) | `FAIL temp-hygiene: 1 snapshot dir(s) leaked since cutoff: FCB_TMP_snap_verify_x` | 1 |
| FreeCAD stopped | `FAIL freecad-window: FreeCAD pid 2626 has no enumerable window (process gone?)` | 1 |

I removed the planted folders and the workdir that I created. Every run prints `cua session 'uat' REVIVED (was dead)` (see the low observations).

### Runner smoke run (AC8): `tests/uat/run/2026-11-18-10-9-verify/runner/`

Command: `docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/runner/run.py <tc-02-02, tc-02-04, tc-11-17, tc-05-03>.json --out /repo/tests/uat/run/2026-11-18-10-9-verify/runner`. Before the run, FreeCAD was stopped. Duration 1 min 45 s. Exit 0. Result: `4 scenarios: 0 PASS, 0 FAIL, 4 ESCALATE.`, `run errors: 0`.

`results.json` `run`: `freecad_version` `1.1.4`, `freecad_apprun` `/opt/freecad/AppRun`, addon `/home/cua/.local/share/FreeCAD/v1-1/Mod/FreeCADBuddy` (`linked: false`). There were 3 groups (default, `SCRIPT_EXEC=0`, `AUTO_APPROVE=0`), with FreeCAD pids 4623, 4764 and 5242 and `error: null`. `git_dirty: true` comes from the untracked leader files.

| Scenario | Verdict | Reason read | Scripted checks | Capture read |
| --- | --- | --- | --- | --- |
| TC-02-02 | ESCALATE | `agent_check` only (JSON-safe property values) | no finding, no disagreement. Menu Show All: `attempts 1`. Pixel: sample on geometry, extent fraction 0.944 | `box-10-20-30` open, `Box` visible, a fitted tall shaded box |
| TC-02-04 | ESCALATE | `agent_check` only (handles A and B, a tree click) | no finding. Menu `attempts 1`. Pixel extent 0.586 | `sphere-r10` open, a shaded sphere with its seam edge |
| TC-11-17 | ESCALATE | `agent_check` only (H1 and audit Thens) | no finding. Menu `attempts 2`, `attempt_log ['delivered, no effect']`. Pixel extent 0.944 | `box-10-20-30`, the same view as TC-02-02 |
| TC-05-03 | ESCALATE | `agent_check` only (a framed capture before the mutation) | no finding. No pixel block in the scenario | `tc-05-03` with `Body`. Only the square sketch outline shows, in isometric view. This agrees with the probe expectation (`Sketch` visible) and with `AUTO_APPROVE=0` |

After the run: `fcb-freecad status` showed `freecad pids:` (empty) and `healthz: unreachable`. Teardown freed `:8765`.

Live preflight refusal (Q6): with FreeCAD started by `fcb-freecad start`, the runner printed `preflight refused: another FreeCAD is running (pid 5598)` with exit 2. It wrote no run folder.

AC4 and AC14 checks:
- `invoke_menu {"path":["View","Status Bar"]}` gave `{"refusal":{"code":"menu_path_unavailable","message":"invoke_menu: menu path segment 0 has no safe activation action"},"status":"refused"}`. The deferral is confirmed.
- `/usr/share/applications/fcb-freecad.desktop` and `~/Desktop/fcb-freecad.desktop` contain `Name=FreeCAD 1.1.4`, `Exec=fcb-freecad start`, `Icon=/opt/freecad/org.freecad.FreeCAD.svg` and `Categories=Graphics;Engineering;`. I did not click the menu entry. The builder's screenshots are the evidence for the click.

## 3. My own element-action check (cua-driver CLI in the container)

- `list_windows`: FreeCAD pid 2626, window 35651682, title `FreeCAD 1.1.4`, 1600 x 949.
- `get_window_state`: `element_count 349`, not degraded, snapshot `s0000000b`. The top-level menu items are `File, Edit, View, Tools, Macro, Sketch, Part Design, Windows, Help`. `View` has 16 children, among them `Status Bar` (`enabled: True`, `selected: True`, `actions ['Press']`).
- I clicked `element_token s0000000b:186` (`View > Status Bar`). The reply was `effect "unverifiable"`, `route "accessibility"`.
- Screenshot `tests/uat/run/2026-11-18-10-9-verify/evidence/elem-1-after-status-bar.png`, which I read: the status bar at the bottom is gone (no `CAD` navigation item and no colour chooser), and the tab bar and the Welcome panel moved down by about 16 px. The before image is `elem-0-before.png`. The new tree shows `Status Bar` with `selected: False`.
- I clicked the new token `s0000000c:186`. In `elem-2-restored.png` the status bar is back and the layout equals the before image.
- Result: the element tree and a token click on a menu leaf work. The driver says `unverifiable`, and the screenshot confirms the effect.

## 4. Falsification

Each mutant ran in the worktree `<scratchpad>/verify-10-9` at `9019b76` (removed at the end) or in the running container. Each was restored and checked again.

| Mutant | Check | Result before → with mutant → restored |
| --- | --- | --- |
| (a) `fcb-cua-mcp`: remove the `until … fcb-session-env` wait, use `eval "$(fcb-session-env)"` (container) | `check_harness` `mcp-session-env` | PASS → `FAIL … address=''`. The other 5 checks PASS → PASS. Restored file SHA-256 `9fb1b334…` equals the repo |
| (b) `fcb-freecad`: remove the `QT_LOGGING_RULES` export (container), FreeCAD restarted | `check_harness` | `FAIL freecad-logging-rule: QT_LOGGING_RULES=''`, `FAIL freecad-elements: element_count=1`, `FAIL gtk-elements-mcp: element_count=1`. FreeCAD hangs: `journey_box` gave `document_create … status TIMEOUT, marshal_timeout`, then `FAIL: solid missing`. `/tmp/freecad.log` has 51 lines `Received text event for invalid interface`. Restored SHA-256 `80c46ef5…` equals the repo, and journey PASS 49.7 % |
| (c1) `launch.started_pids` without the process group (R2-5) | pytest | 208 passed → 2 failed (`…delete_the_discovery_files_of_every_started_pid…`, `…see_the_process_table_before_the_kill…`) |
| (c2) `launch_environment`: silencing rule first (R1-2) | pytest | → 2 failed (`…silence_the_atspi_warning_and_keep_other_rules…`, `…silence_the_atspi_warning_last_When_the_launch_map…`) |
| (c3) `stop` deletes only the ready pid's file: old code (R1-1) | pytest | → 2 failed (`…every_started_pid_When_readiness_failed`, `…see_the_process_table…`) |
| (c4) `check_tools` without the `DISPLAY` check (R3-6) | pytest | → 1 failed (`…refuse_naming_display…`) |
| (c5) `wait_until_ready` needs `/healthz` pid == AppRun pid (R1-11) | pytest | → 1 failed (`…return_the_record_of_the_freecad_below_apprun…`, after the 120 s readiness timeout) |
| (d) watchdog reads `tempfile.gettempdir()`: the old `/tmp` path | pytest `test_uat_watchdog.py` | 18 passed → 5 failed (`…folder_appears_after_the_cutoff`, `…no_snapshot_folder_is_newer…`, `…not_count_a_snapshot_folder_in_the_os_temp_folder…`, `…count_the_render_files…`, `…check_the_workdir_it_was_given…`) |
| `capture.invoke_menu` raises at once, no wait (R2-1, R1-3) | pytest | → 2 failed (`…press_the_leaf_once_it_is_enabled…`, `…wait_for_the_item_When_it_is_missing…`). This equals the builder's claim "fails 2 tests" |
| `invoke_menu` ignores `enabled` (R1-3), and every click error wrapped as a refusal (R3-3) | pytest | → 3 failed (`…stays_disabled`, `…starts_disabled`, `…not_wrap_a_driver_fault…`) |
| `run.MENU_ATTEMPTS = 1` (R1-5, R2-2, R3-2) | pytest | → 6 failed (`…2_attempts_When_show_all_is_refused_once`, `…refused_3_times`, `…deliver_again…`, `…probe_never_confirms…`, `…unconfirmed_then_refused`, `…deliveries_are_mixed`) |
| watchdog accepts a missing `--workdir` (R2-6) | pytest | → 1 failed (`…given_workdir_does_not_exist`) |
| watchdog raises when `<workdir>/tmp` is missing (R3-1) | pytest | → 1 failed (`…no_tmp_folder_yet`) |
| `fcb_py.sh` rewrites the prefix with no boundary (R3-4, R2-9) | pytest | → 1 failed (`…leave_a_sibling_folder_alone…`) |
| `GOLDEN_DIR` planted wrong | e2e sweep / edge sweep | e2e exit 1 (red). **Edge exit 0** (V-1) |

After all mutants, `git status --short` in the worktree was empty.

## 5. Ledger proof table

| Id | Proven? | Test or command |
| --- | --- | --- |
| R1-1 | proven | mutant c3 (old cleanup): `…delete_the_discovery_files_of_every_started_pid_When_readiness_failed` (`test_uat_runner_container.py:422`) goes red |
| R1-2 | proven | mutant c2 → 2 red tests (`:245`, `:325`). Live mutant b → `freecad-logging-rule` red and FreeCAD hangs |
| R1-3 | proven | the enabled-ignored mutant → `:337`, `:351` red |
| R1-5 | proven | `MENU_ATTEMPTS=1` → 6 red. Live: TC-11-17 `attempts 2`, `attempt_log ['delivered, no effect']` |
| R1-9 | proven | the import origin is `Mod/FreeCADBuddy/./freecad_buddy/__init__.py`, with no `/repo` on `sys.path` |
| R1-10 | proven | `tests/uat/testcases`: 15 files, 70 changed lines. The Then and And lines under a Then block are equal in each file (for example TC-01 132 = 132, TC-02 178 = 178), 0 differ. Script: `<scratchpad>/tools/then_check.py`. The TC-01 lines in Then-block scope are fenced command lines in `**Cleanup**` and Given sections. None starts with Then or And |
| R1-11 | proven | mutant c5 → `:372` red. The `freecad()` test is at `:392` (I did not mutate it) |
| R1-23 | proven | 4 live cases (0, 0, 1, 1), and mutant d → 5 red |
| R1-25 | proven | `fcb-freecad start /repo/benchmarks/g0/golden-models/box40-hole-r5.FCStd` gave cmdline `/opt/freecad/usr/bin/freecad /repo/.../box40-hole-r5.FCStd`, `freecad-logging-rule` PASS, `freecad-elements` 591. The capture `evidence/file-start-box40.png` shows `box40-hole-r5` with `BoxHole` in the tree, and FreeCAD responds |
| R1-4, 6, 12, 14, 15, 17 | not re-proven | low. I did not check them one by one |
| R2-1 | proven | the no-wait mutant → 2 red |
| R2-2 | proven | `MENU_ATTEMPTS=1` → `…unconfirmed_then_refused` red |
| R2-3 | proven | live `attempt_log` in `results.json` (TC-11-17) |
| R2-5 | proven | mutant c1 → 2 red |
| R2-6 | proven (unit) | the missing-workdir mutant → 1 red. I did not run the live `--workdir /tmp/nope` case |
| R2-8 | proven | mutant d → `…not_count_a_snapshot_folder_in_the_os_temp_folder…` red |
| R2-9 | proven | the boundary mutant → 1 red |
| R2-10 | proven | live mutant b: `freecad-logging-rule` red |
| R2-4, R2-7, R2-11, R2-12, R2-13 | not re-proven | docs and docstrings (R2-4, R2-7), glob tests not mutated (R2-11). R2-12: TC-01 still has `invoke_menu … ["File", "Exit"]` at `TC-01-…md:391`, `:530`, `:615`, `:650` (see the low observations) |
| R3-1 | proven | the missing-tmp mutant → 1 red. Live clean case: workdir absent, exit 0 |
| R3-2 | proven (partly) | `…deliveries_are_mixed` red under `MENU_ATTEMPTS=1`. I did not mutate the message text itself |
| R3-3 | proven | the wrap-all mutant → `…not_wrap_a_driver_fault…` red |
| R3-4 | proven | the boundary mutant → `…sibling_folder_alone…` red |
| R3-6 | proven | mutant c4 → 1 red |
| R3-8 | proven (partly) | `…see_the_process_table_before_the_kill…` red under c1 and c3 |
| R3-5 | not proven | `swap-qt-gui.sh` needs an image rebuild with a bad pattern. Not run |
| R3-7 | not re-proven | docs and pattern. `pgrep -f '^/opt/freecad/usr/bin/freecad( \|$)'` worked live in `freecad-logging-rule` |

## 6. Q16

`sha256sum %APPDATA%\FreeCAD\v1-1\user.cfg` = `b89a97711941619bb0ba74ae04fb888025e82f49ff48174fbebb42aed28d85a0`, at the start and at the end. This equals decision 8.

## 7. AC map

| AC | Status | Evidence |
| --- | --- | --- |
| AC1 | met, but the proof is unstable (V-2) | `tests/close-loop/check_harness.py:146` `check_mcp_session_env`, script `:44-71`. PASS on most runs, red under mutant a. 3 of 6 full runs red on the committed code |
| AC2 | met | `check_harness.py` `registry-childcount` `ChildCount=11` (13 with more apps). `gtk-elements-serve` and `gtk-elements-mcp` show `Xfce4-panel element_count=4` (2 to 6 between runs) with `error=None` |
| AC3 | met | `freecad-elements` 346 (349, and 591 with a document), with File, Edit and View. My own tree read in §3 |
| AC4 | PARTIAL (deferral R1-24) | token click: §3 `evidence/elem-*.png`. `invoke_menu` refusal measured again |
| AC5 | met | `test_uat_runner_container.py:86` (command), `:108` (environment), `:67` (child), `:372` (readiness). Smoke `results.json` `run`: `freecad_version 1.1.4`, addon path |
| AC6 | met | `test_uat_runner.py:394` (exit 2 names the pid), `:415` (port), `:1436-1441` (exit 3). `test_uat_runner_container.py:159`, `:186`, `:422`. Live refusal `pid 5598`, exit 2. After the smoke run, `:8765` was free |
| AC7 | met | `test_uat_runner_container.py:201` (pinned binary), `:291` (token press). Smoke captures read. Show All retry seen live (TC-11-17) |
| AC8 | met | `tests/uat/run/2026-11-18-10-9-verify/runner/summary.md`, `results.json`, 4 captures read. Exit 0, 0 run errors |
| AC9 | met | 4 live cases in §2. `test_uat_watchdog.py:114`, `:138`, `:156`, `:166` |
| AC10 | **not met** (V-1) | the sweeps pass (29/29, 14/14) and the e2e planted path gives exit 1. The edge planted path gives exit 0. Test of the sweep command: `test_uat_runner_container.py:229` |
| AC11 | met | 1752 passed. Every mutant in §4 read red. ruff, `check_imports` and format are clean |
| AC12 | met | `diff --strip-trailing-cr CLAUDE.md AGENTS.md` shows no difference (index EOL `lf` for both). A grep for `Not usable for UAT yet`, `FCB_ENV`, `FREECAD_EXE` and `micromamba` in the named docs finds only `APPENDIX-B…md:96` "No micromamba env … is involved". I did not read the full documents again |
| AC13 | met | `deferred-work.md` diff: the 10-9 port entry and the `fcb` env entry resolved with pointers. A new resolved entry for element actions. New deferred entries for `invoke_menu` and for the Windows commands in the test cases |
| AC14 | met (file check) | `.desktop` fields in §2. The menu click is the builder's evidence |

## 8. Findings returned to the leader

### V-1 (medium): edge sweep passes with a missing golden directory

Reproduction (worktree): set `GOLDEN_DIR = REPO / "benchmarks" / "g0" / "golden-models-planted-wrong"` in `scripts/automation/run_mcp_e2e.py:37`, then run `python scripts/automation/run_mcp_edge_cases.py`. The output is `4/4 edge checks passed`, exit 0. Cause: `run_mcp_edge_cases.py:45` `_open_golden` returns `None` when the fixture is missing, and the callers skip their checks (`if handle:` at `:66`, and `:166`). The skip logic exists at `97fac62` too. AC10 and Q10 still ask for a non-zero exit, and the builder's evidence does not separate the two sweeps. This silently drops 10 of 14 checks (Q14 class: a masked failure).

### V-2 (medium): `mcp-session-env` reads red on correct code

Observed: `FAIL mcp-session-env: cua-driver mcp address='' session address='unix:path=…'` in 3 of 6 full runs of `uv run python tests/close-loop/check_harness.py` on the committed `fcb-cua-mcp` (SHA-256 `9fb1b334…`, equal to the repo). The runs were: the first run after a `--force-recreate` and FreeCAD start; the first run after a FreeCAD restart; the first run after a FreeCAD start with a file. The function `check_mcp_session_env` passed in 22 of 22 direct calls, among them a debug copy that also printed the process state (`alive=yes elapsed=6`, cmdline `/usr/local/bin/cua-driver mcp`). An empty address comes either from a `cua-driver mcp` with no address or from a process that is gone when the script reads `/proc/<pid>/environ` (`check_harness.py:63-66`: `sleep 1`, then read). Thus I cannot say whether the check is flaky or whether `fcb-cua-mcp` has a race. Next step: make the script record whether `/proc/$mcp_pid` exists and the exit status of the process, then repeat full runs right after a FreeCAD start.

### Low observations (no verdict impact)

- `TC-01-session-lifecycle-and-transport.md:391`, `:530`, `:615`, `:650` still close FreeCAD with `cua-driver call invoke_menu … ["File", "Exit"]`. The container driver refuses this path. Then `fcb-freecad start` at `:531` refuses because FreeCAD still runs. These lines are in the deferred R1-26 scope, but R2-12 says the TC-01 wording is fixed.
- `fcb-freecad stop` printed `window close timed out; killing <pid>` 2 times: when the Welcome panel was open with a document loaded, and when the mutant FreeCAD hung.
- The watchdog prints `cua session 'uat' REVIVED (was dead)` on every run, because each `cua-driver call` session ends with its call. So the revive line gives no warning when a real session is lost.
- The `qt-build` stage installs apt packages with no version pins. The base image is pinned by digest, and the qtbase tarball and the pip wheels have SHA-256 checks. Q15 says "any new package is pinned".

## End state

- The container `fcb-desktop` runs. FreeCAD pid 7026 was started clean by `fcb-freecad start`, with no document, and `/healthz` shows `freecad_pid` 7026.
- The container scripts `fcb-cua-mcp` and `fcb-freecad` were restored, and their SHA-256 values equal the repo files.
- The worktree was removed (`git worktree list` shows the main tree only).
- I wrote only `tests/uat/run/2026-11-18-10-9-verify/` and this report in the repository. The sweeps rewrote `_automation/*.json` and the journey rewrote `tests/close-loop/evidence/journey-box.png`, by design. Git ignores both.

## Re-run at f23d58d (2026-11-18)

Scope: the rows of `triage-10-9-rt.md` (RT-1 to RT-6, V-3), the gates, one full `check_harness` pass, both sweeps, and one reading of the `73c84d4..f23d58d` diff. Mutants ran in a worktree at `f23d58d` or in a `/tmp` copy in the container. Both were removed. New evidence is in `tests/uat/run/2026-11-18-10-9-verify/rerun-f23d58d/`.

**Verdict: PASS.** Every row is proven. I found 2 low defects and no medium or high defect.

### Gates

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | `All checks passed!` |
| `uv run python scripts/check_imports.py` | `check_imports OK` |
| `ruff format --check` on the 7 `.py` files changed in `73c84d4..f23d58d` | `7 files already formatted` |
| `uv run pytest tests/external -q` | `1763 passed, 4 skipped` |
| `freecadcmd -u/-s <temp cfg> tests/run_tests.py` | `Ran 866 tests`, `OK (skipped=1)` |
| `check_harness.py`, one full run | 6/6 PASS, exit 0. `freecad-elements: element_count=349 missing menu items=[]` |
| Sweeps from the host | e2e `29/29 checks passed`, edge `14/14 edge checks passed`, both exit 0 |
| Q16 | `b89a97711941619bb0ba74ae04fb888025e82f49ff48174fbebb42aed28d85a0`, unchanged |

No file under `src/` or `tests/close-loop/docker/` changed, so the image was not rebuilt.

### Rows

| Row | Proven | Decisive evidence |
| --- | --- | --- |
| RT-1 | yes | The real `get_session` reply is `{"session": "uat", "state": "active", ...}`, with no `active` key. The old `uat_watchdog.py` against the new tests: `test_should_report_active_When_get_session_answers_with_the_state_active` red. Live, `--no-revive`: with a session that `start_session` started, `ok cua-session: cua session 'uat' active` and exit 0. After `end_session`: `FAIL cua-session: cua session 'uat' is not active: session 'uat' has ended; ...` and exit 1 |
| RT-2 | yes | The old code against the new tests: `test_should_refuse_the_cutoff_naming_the_offset_when_the_cutoff_has_no_utc_offset` red. Live: a naive host time gives `argument --since: '2026-11-18T08:08:59' has no UTC offset; add one, ...` and exit 2. A folder planted after a `2026-11-18T08:09:00+07:00` cutoff gives `FAIL temp-hygiene: 1 snapshot dir(s) leaked since cutoff: FCB_TMP_snap_verify_rt2` and exit 1. After I removed the folder, the same cutoff gave exit 0. The `%z` form (`+0700`) that `tests/uat/README.md:115` gives parses in the container Python 3.11.14 |
| RT-3 | yes | A grep in `tests/uat/README.md` for `shows no widgets`, `until story 10-9`, `Windows host session` and `freecad.exe` finds nothing. The only `NOT RUN` hit, `README.md:75`, states the container truth (a step with no token, pixel or key route) |
| RT-4 | yes | `fcb_py.sh` from `73c84d4` against the new tests: 2 red (`…backslash_sibling_folder_alone…`, `…backslash_root_When_it_follows_a_flag_prefix`) and 9 passed |
| RT-5 | yes | Live in the container, with FreeCAD stopped: `detected 5/5`, `false alarms 0/2`, exit 0, in 31 s (`rerun-f23d58d/faults.log`). Planted break in a `/tmp` copy (`judge` ignores the `view.clipped` field): `MISSED clipped-view`, `detected 4/5`, exit 1 (`faults-mut.log`) |
| RT-6 | yes | Live tree: `missing_menu_items` gives `[]`. The same captured tree with the line `    - [165] menu item "View" [actions=[ShowMenu]]` removed gives `['View']`, while another element labelled `"View"` (the page tab) stays in the tree. The old substring rule passes that tree. As a behavioural mutant: `test_Should_report_view_missing_When_only_a_page_tab_and_a_submenu_carry_that_label` red |
| V-3 | yes | With the non-OK branch of `_open_golden` removed: `test_Should_record_a_failed_check_When_the_edge_sweep_golden_file_does_not_open` red (1 failed, 36 passed). After restore it is green |

### Diff reading (`73c84d4..f23d58d`)

I checked for a wrong process, a hidden failure, a retry that turns a fail into a pass, and a Windows path left behind.

- `run_faults.py` finds the discovery file through `launch.started_pids(process.pid)`, so it reads the FreeCAD below `AppRun`, not another FreeCAD. It ends the run with `launch.stop`.
- `wait_until_laid_out` is a readiness wait before the snapshots, not a retry of a verdict. If the view never lays out, it raises `LaunchError`, and the case reads as `MISSED` or `FALSE ALARM` (exit 1).
- `check_harness.py` `_MENU_BAR_ITEM` needs exactly 4 spaces of depth. A format change would read red, not green.
- `fcb_py.sh` `--*=*` passes the value after `=` back through `rewrite`. Forward-slash and backslash forms are both covered by tests.

Defects:

- **D-1 (low): `run_faults.py` has no preflight for a running FreeCAD.** Reproduction: `fcb-freecad start`, then `docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/probe/run_faults.py`. The run takes 2 min 7 s, prints `MISSED … no verdict: LaunchError: :8765 still held 15 s after exit` for each fault and `FALSE ALARM` for each control, then `detected 0/5`, `false alarms 2/2`, exit 1 (`rerun-f23d58d/faults-running.log`). The failure is visible, but the report blames the probe and not the running FreeCAD. `tests/uat/probe/README.md:154-155` tells the operator to stop FreeCAD first. The runner's `launch.check_free()` would name the pid before any launch.
- **D-2 (low): `tests/uat/probe/README.md:28` still gives the Windows host launch** (`& "C:\Program Files\FreeCAD 1.1\bin\freecad.exe" -M D:\path\to\repo\tests\uat\probe ...`), and `:41` gives the `%APPDATA%` discovery path. RT-5 updated `:139` and `:166` only.

### End state

- The container is up. FreeCAD pid 42365 was started with `fcb-freecad start`, and `/healthz` names it. FreeCAD has no document open.
- The worktree and the `/tmp` copies in the container are removed.
- The workdir that I created for the planted folder is removed. It did not exist before.
