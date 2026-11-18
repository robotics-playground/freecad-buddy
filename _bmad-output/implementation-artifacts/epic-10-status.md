# Epic 10 status

Goal: correct the behaviour found by the first full UAT run and prove Gate 1 green (Story 10.8) before Epic 4 resumes.
Done: 10-1, 10-2, 10-3, 10-4, 10-5, 10-6a, 10-6, 10-7, 10-7b, 10-9, 10-10. Gate 1 fixes from run 2026-10-23-02 — `84c8e07`..`fab7ba6`.
In progress: none. The leader stopped at the decision-22 stop point (10-10 merged).
Remaining: 10-8 — new UAT Gate 1 run in the container, includes the weekly `canary` fix on `main` (decision 19). Needs planning.
Branch / head: integration `fix/uat-gate-1-failures` = merge of `story/10-10-uat-testcases-in-container` (Story head `498b53d` plus the leader-record commit). `origin` is at `031d8e8`: the 10-10 merge is not pushed (decision 21).
Blockers: none for 10-8.
Open decisions: push of the 10-10 merge; 10-8 plan (canary cause not yet read).
Confirmed by the user: preset `anthropic-balanced`, integration branch `fix/uat-gate-1-failures` (decision 20).
Agents alive: none (builder-10-10, verifier-10-10 shut down; redteam-10-10 shut down earlier). Container `fcb-desktop` stopped. Computer stays on (decision 22).
Updated: 2026-11-18 at `498b53d`

## Final report, Story 10-10 (2026-11-18)

Result: done and merged into `fix/uat-gate-1-failures`. No push, no change to `main`.

What changed:
- `tests/uat/testcases/` (17 files), `test-plan.md`, `APPENDIX-B`, `README.md`, `coverage-matrix.md`: every Windows-host command has a container form. Census of host-command lines: 905 before, 0 after.
- New `scripts/automation/fcb_cua.sh` (`$FCB_CUA`, the container `cua-driver` CLI from a host shell); path mapping shared with `fcb_py.sh` in `fcb_paths.sh`; 32 wrapper tests, exit code passes through.
- `test-plan.md` §6 "GUI routes in the container": measured routes for 48 `cua-driver` tools, actions and tree fields. Tree rows and combo items take a foreground pixel click in screenshot pixels; keys go to the window; the rename editor takes window-level typing; selection is read with `script_exec` (no `selected` field in the container tree); Recompute is `F5`; `cua-driver` exits 0 on a tool error, so a step is judged by its text.
- Then observables unchanged except two listed lines (TC-01:368 Windows chmod exception removed; TC-09:403 route to the document view). One recorded weakening: TC-12-06 reads the undo list from `doc.UndoNames` (the Undo dropdown does not open in the container).

Verification: verifier-10-10 PASS at `498b53d` after 3 fix rounds (`verify-10-10.md`); red team at `5ee4824` found 5 medium, all fixed and proven by running the test-case text as written. Gates: ruff clean, check_imports OK, pytest tests/external 1784 passed 4 skipped, `then-check.py` 2340 lines 0 failures. Developer `user.cfg` unchanged. Ledger: `review-ledger-10-10.md`.

Limits that stay (`deferred-work.md`):
- Whole scenarios were not run end to end: only each command kind and each GUI route. Story 10-8 runs them; a route found broken there is a test-case defect fixed in the run.
- Low: "Pixel points" should say scroll the row into view first; proof-tool blind spots; `cua-driver` exits 0 on tool errors.
- `invoke_menu` on the Qt menu bar is still refused by cua-driver 0.28.1 (test cases no longer use it).

Next steps for the user:
1. Push `fix/uat-gate-1-failures` (the 10-10 merge), if wanted.
2. Plan Story 10-8: read the `canary` failure cause on `main`, then the Gate 1 run in the container.
3. Optional: Epic 10 retrospective after 10-8.

## Final report, Story 10-9 (2026-11-18)

Result: done and merged into `fix/uat-gate-1-failures`. No push, no change to `main`.

What works now in the container (FreeCAD 1.1.4):
- `cua-driver` sees FreeCAD widgets (346-349 elements) through rebuilt `libQt6Gui` and `libQt6XcbQpa` (qtbase 6.8.3 with the AT-SPI bridge). Element-token clicks change FreeCAD (screenshots `tests/uat/run/2026-11-17-10-9-smoke/evidence/demo-*.png`).
- The FreeCAD hang under the bridge is a FreeCAD deadlock in `NotificationArea` (`NotificationArea.cpp:1143`); `QT_LOGGING_RULES=qt.accessibility.atspi.warning=false` in `fcb-freecad start` and the runner removes it.
- The scripted runner, the probe fault set (`run_faults.py`: detected 5/5, false alarms 0/2) and the watchdog run in the container through `fcb-py`.
- Headless sweeps: `run_mcp_e2e.py` 29/29, `run_mcp_edge_cases.py` 14/14, over the installed addon in the image.
- `tests/close-loop/check_harness.py` 6/6 PASS. XFCE Applications menu entry and desktop shortcut start FreeCAD.

Verification: verifier PASS at `f23d58d` (`verify-10-9.md`, "Re-run at f23d58d"; evidence `tests/uat/run/2026-11-18-10-9-verify/`). Gates: ruff clean, check_imports OK, pytest tests/external 1763 passed 4 skipped, infc 866 OK. Developer `user.cfg` hash unchanged (decision 8). Review: 3 lens rounds (trend 9, 11, 7 new high + harness medium), verifier rounds at `9019b76` and `73c84d4`, red team at `73c84d4` (5 medium, 1 low-medium, all fixed and proven). Ledger: `review-ledger-10-9.md`.

Limits that stay (in `deferred-work.md`):
- AC4 PARTIAL: `cua-driver` 0.28.1 `invoke_menu` refuses the Qt menu bar; press the leaf item by token (R1-24; TC-01 lines 391, 530, 615, 650).
- R1-26 / R2-14: Windows-only commands in the test cases. Blocks 10-8.
- Low: D-1 (`run_faults.py` no preflight for a running FreeCAD), D-2 (`tests/uat/probe/README.md:28,41`), V-4 (unit test checks script text only).
- The 4th review round was not run (user decision); the red-team fix batch `f23d58d` (+250/-73) had one verifier defect read instead of lens review.

Next steps for the user:
1. Plan the test-case container rewrite Story (R1-26), before 10-8.
2. Close 10-7b after its review evidence check.
3. Decide whether 10-8 includes the `canary` fix on `main`.
4. Confirm or change the preset and the integration branch; decide whether to push `fix/uat-gate-1-failures`.
5. Optional: Epic 10 retrospective after 10-8.

## Story 10-9 scope (user, 2026-11-17)

1. Fix AT-SPI in the `fcb-desktop` container so `cua-driver` element actions (`element_index`, `invoke_menu`) work on FreeCAD 1.1.4.
2. Port the scripted UAT runner (`tests/uat/runner/`), its FreeCAD probe and the UAT watchdog from the Windows host to the container.
3. Run the headless E2E sweeps (`scripts/automation/run_mcp_e2e.py`, `run_mcp_edge_cases.py`) in the container.

Leader measurements, 2026-11-17, container up since 05:51:46, FreeCAD pid 776:
- Cause 1: the stdio `cua-driver mcp` (pid 7, from `fcb-cua-mcp`) started at 05:51:46, before the desktop D-Bus session socket `/tmp/dbus-3CF95yaPhf` (05:52). Its environment has `DISPLAY=:1` and no `DBUS_SESSION_BUS_ADDRESS`. MCP `get_window_state` returned `atspi_walk_failed: AT-SPI connect failed: ZBus Error: InputOutput(... NotFound ...)`.
- Cause 2: through `cua-driver serve` (pid 57, correct bus address) the walk still fails for every app: FreeCAD and the GTK control `xfce4-panel` both return 1 element, `x11_property_fallback_partial: AT-SPI was unavailable`. `org.a11y.Bus.GetAddress` answers `unix:path=/home/cua/.cache/at-spi/bus_1`, but `org.a11y.atspi.Registry` `ChildCount` returns `org.freedesktop.DBus.Error.NoReply`. Registry runs as `at-spi2-registryd --use-gnome-session` under XFCE (suspected, not proven).
- Cause 3: `/opt/freecad/usr/lib/libQt6Gui.so.6.8.3` (AppImage, conda-forge Qt) has 0 matches for `org.a11y`, `QSpiAccessibleBridge`, `AtSpiAdaptor`. Strong evidence of no AT-SPI bridge; not compared against a Qt build known to have one.

## Environment
Skill version: bmad-leader SKILL.md sha256 `936e3e227d5e`.
Host: Windows 11 Pro, power plan High performance; user timezone SE Asia Standard Time (UTC+7).
Shell and tools: Git Bash (POSIX) and PowerShell 7. `uv` for Python. `docker` and `docker compose` present. No `package.json`: CLAUDE.md `npm run` gates do not apply; the gates are below. Host FreeCAD 1.1 at `C:\Program Files\FreeCAD 1.1\bin\` — never for UAT; `freecadcmd.exe` only with `-u <tmp>\user.cfg -s <tmp>\system.cfg`.
Gates: `uv run ruff check .` · `uv run python scripts/check_imports.py` · `uv run pytest tests/external -q` · `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py`. `uv run ruff format --check .` fails on 29 pre-existing files: check only the files you change.
Known unstable test: `tests/external/test_managed_venv.py::test_Should_start_an_external_interpreter_When_freecad_set_pythonhome` fails in the full run and passes alone (not caused by this epic's diffs).
Credentials: none needed. GitHub `gh` is logged in; do not push.
In use: container `fcb-desktop` publishes `127.0.0.1:6901` (noVNC) and `127.0.0.1:18765` (MCP proxy relay). Host `:8765` is the host FreeCAD bridge port; leave it free.
Missing tools: conda env `fcb` (`%USERPROFILE%\micromamba\envs\fcb`, `FCB_ENV`) is gone — the host headless H1 sweeps cannot run; Story 10-9 moves them into the container.
Shared resources: container `fcb-desktop`, image `fcb-desktop:local`, ports 6901/18765 — owner builder-10-9 during Story 10-9; `tests/uat/run/` — new run folders only, never edit an existing run folder; developer `%APPDATA%\FreeCAD\v1-1\user.cfg` — nobody writes it.
