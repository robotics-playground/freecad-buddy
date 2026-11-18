# Epic 10 status

Goal: correct the behaviour found by the first full UAT run and prove Gate 1 green (Story 10.8) before Epic 4 resumes.
Done: 10-1, 10-2, 10-3, 10-4, 10-5, 10-6a, 10-6, 10-7, 10-9. Gate 1 fixes from run 2026-10-23-02 — `84c8e07`..`fab7ba6`.
In progress: none. The leader stopped at the decision-16 stop point (10-9 merged).
Remaining: 10-7b (status `review`: close after its sub-spec review evidence is confirmed), a new Story for the container rewrite of `tests/uat/testcases/` (R1-26, to plan), then 10-8 (new Gate 1 run in the container).
Branch / head: integration `fix/uat-gate-1-failures` = merge of `story/10-9-uat-runner-in-container` (Story head `f23d58d` plus the leader-record commit). Nothing pushed.
Blockers: Story 10-8 is blocked by R1-26 — 737 lines of Windows-only commands in `tests/uat/testcases/` must be rewritten for the container first.
Open decisions: weekly `canary` workflow fails on `main` (2026-11-02, 11-09, 11-16); 10.8 AC needs "CI green" — user to say whether 10-8 includes the canary fix.
Open for the user to confirm: preset `anthropic-balanced` (`.leader.json`, left untracked); integration branch `fix/uat-gate-1-failures`; the decision-16 autonomy contract ends at this stop point.
Agents alive: none (builder-10-9-b and verifier-10-9 shut down at the end of the run). Container `fcb-desktop` stopped (`docker compose ... down`).
Updated: 2026-11-18 at `f23d58d`

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
