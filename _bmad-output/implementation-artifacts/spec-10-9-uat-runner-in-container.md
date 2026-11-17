---
title: 'Story 10.9: UAT and E2E harness in the fcb-desktop container'
type: 'feature'
created: '2026-11-17'
status: 'in-review'
baseline_commit: '9c214a97525117c44f14db1c10f5fbff175c64de'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/tests/close-loop/README.md'
  - '{project-root}/tests/uat/runner/README.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/uat-run-practices.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/freecad-native-validation.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** CLAUDE.md section 9 says every UAT and GUI smoke test runs on FreeCAD 1.1.4 in the `fcb-desktop` container, but four harness parts still need the Windows host:
(1) `cua-driver` element actions (`get_window_state` element tree, `element_index`, `invoke_menu`) see only one element in container FreeCAD, so 16 test-case files cannot run as written;
(2) the scripted runner `tests/uat/runner/` launches the host `freecad.exe` (`launch.py:27`), uses `tasklist`, `%APPDATA%` and the host `cua-driver` daemon, so its 72 scenarios are `NOT RUN`;
(3) the watchdog `scripts/automation/uat_watchdog.py` checks host temp folders and the host `:8765`;
(4) the headless sweeps `run_mcp_e2e.py` and `run_mcp_edge_cases.py` need the conda env `fcb` (`FCB_ENV`), which does not exist on the machine.
Story 10.8 (the Gate 1 re-run) cannot start before they run in the container.

**Approach:** Four goals, each with a measured before and after.
G1 fixes or disproves three measured AT-SPI causes (C1 `fcb-cua-mcp` reads the D-Bus address once and may start before the desktop session; C2 the AT-SPI registry gives `NoReply` for every app; C3 the AppImage's conda-forge `libQt6Gui.so.6.8.3` has no AT-SPI bridge).
G2 ports the runner, its probe use and the watchdog to the container.
G3 runs both sweeps against the container.
G4 corrects the documents that state the old limits.

## Decisions

- **D1 — Version fixed.** FreeCAD stays 1.1.4 (epic-10 decisions D4). For C3 the builder looks for a 1.1.4 build whose Qt has an AT-SPI bridge (official build or package with a distro Qt, a matching Qt 6.8.3 accessibility plugin, another base image). If none works, the builder stops at the plan gate with the evidence and the options. The builder does not change the version.
- **D2 — Replace, do not duplicate.** The runner's host path (`tasklist`, `%APPDATA%`, `FREECAD_EXE`) is replaced by the container path, not kept beside it. Host `freecad.exe` is never started by the runner.
- **D3 — Product code stays.** No change under `src/freecad_buddy/` except what the container harness needs. No change to a test case's Thens.
- **D5 — Runner placement (leader decision 7).** The runner and the watchdog run inside the container through `docker exec`. The image installs `mcp==1.28.1` (the `uv.lock` pin), pinned like every other image download. They do not use the addon's managed venv, which exists only after a first FreeCAD start.
- **D4 — Falsifiable proofs.** Each G1 fix is shown with a check that reads red before the fix and green after, with counts. At least one fix is reverted once to show the check go red, then restored.

## Boundaries & Constraints

**Always:**
- The runner keeps the temporary-profile rule (`-u` and `-s` temp files), the one-FreeCAD check and the `:8765` free check, with the container as the place they check. The container profile `user.cfg` SHA-256 is unchanged by a run.
- Every pinned download in the image keeps its SHA-256 check.
- A host tool call that reaches the container uses container paths (`/repo/...`); the run folder is written under `/repo/tests/uat/run/`.
- Tests: names `Should <outcome> When <condition>`, `# Arrange` / `# Act` / `# Assert`; pure logic in `tests/external/`; in-FreeCAD tests in `tests/infc/`.
- The runner imports the standard library, `mcp` and the probe module `expect` only; never `freecad_buddy`.

**Never:**
- Start the host FreeCAD, write the developer `%APPDATA%\FreeCAD\v1-1\user.cfg`, or use the conda env `fcb`.
- Mask a failure: no `|| true`, no retry to get a pass, no `continue-on-error`.
- Edit an existing folder under `tests/uat/run/`, or edit intent, PRD, architecture spine or design documents.
- Change the FreeCAD version, or run the Gate 1 run itself (Story 10.8).

</frozen-after-approval>

## Code Map

- `tests/close-loop/docker/` -- `Dockerfile`, `compose.yaml`, `bin/fcb-cua-mcp` (reads the D-Bus address once, at start), `bin/fcb-session-env`, `bin/fcb-cua-serve`, `bin/fcb-freecad`, `supervisor/*.conf`
- `tests/close-loop/journey_box.py` -- working host client of the container (MCP on `:18765`, `docker exec` for `cua-driver`)
- `tests/uat/runner/launch.py`, `capture.py`, `mcp_client.py`, `run.py` -- host-only today: `tasklist`, `%APPDATA%`, `FREECAD_EXE`, `cua-driver` on the host `PATH`, `http://127.0.0.1:8765/mcp`
- `tests/uat/probe/` -- probe loaded with `freecad -M`; its HTTP port and token live inside FreeCAD's process
- `scripts/automation/uat_watchdog.py` -- host `cua-driver`, `http://127.0.0.1:8765/mcp/`, `tempfile.gettempdir()`
- `scripts/automation/run_mcp_e2e.py:_fcb_env`, `run_mcp_edge_cases.py:_run` -- spawn the H1 front with the conda `fcb` python; `GOLDEN_DIR` is a host path
- `src/freecad_buddy/hosts/headless/entry.py`, `worker.py` -- H1 front (MCP, no FreeCAD) and FreeCAD worker child
- `tests/external/test_uat_runner.py` -- existing pure runner tests
- `_bmad-output/implementation-artifacts/deferred-work.md` -- entries this Story closes (see AC13)

## Tasks & Acceptance

**Execution:**
- [x] `tests/close-loop/docker/Dockerfile`: Qt build stage and library swap (C3); `/opt/fcb-site` pinned install; `bin/fcb-py` -- AC3, D5
- [x] `tests/close-loop/docker/bin/fcb-cua-mcp` (C1), `bin/fcb-cua-serve` if C2 reproduces; `tests/close-loop/check_harness.py` -- AC1, AC2, AC3, AC4
- [x] `tests/close-loop/docker/applications/fcb-freecad.desktop`, `Dockerfile`, `tests/close-loop/README.md` -- AC14
- [x] `tests/uat/runner/launch.py`, `capture.py`, `run.py`, `tests/external/test_uat_runner.py` -- AC5..AC8, AC11
- [x] `scripts/automation/uat_watchdog.py` and its tests -- AC9, AC11
- [x] `scripts/automation/run_mcp_e2e.py`, `run_mcp_edge_cases.py` -- AC10
- [x] G4 correct the documents -- AC11, AC12
- [x] close or keep the deferred entries -- AC13

**Acceptance Criteria:**

G1 — element actions in the container.
- AC1 (C1). Given the container is restarted, when `fcb-cua-mcp` runs, then the `cua-driver mcp` process environment (`/proc/<pid>/environ`) holds a `DBUS_SESSION_BUS_ADDRESS` equal to the desktop session's, whatever the start order. The before value (no address) and the after value are recorded. A test or script check fails when the address is absent.
- AC2 (C2). Given the fix, when `get_window_state` runs on a GTK control app beside FreeCAD (for example `xfce4-panel` or another GTK window), then it returns more than 1 element and no `atspi_walk_failed`, through both `cua-driver serve` and the MCP server; the registry answers `ChildCount` with no `NoReply`. The cause is proven or disproved with evidence; `at-spi2-registryd --use-gnome-session` is named as a cause only if a change to it flips the result.
- AC3 (C3). Given the container FreeCAD 1.1.4, when `get_window_state` runs on its main window, then the element tree has more than 1 element, and the menu bar items (File, Edit, View) are in it. The before count (1) and the after count are recorded. If no 1.1.4 build can show this, the Story stops at the plan gate with the evidence (D1); AC3 to AC5 then stay open.
- AC4 (demo), **PARTIAL**. Blocker: cua-driver 0.28.1 `invoke_menu` refuses FreeCAD's Qt top-level menu items (`menu path segment 0 has no safe activation action`). Unblock: a cua-driver release that activates `ShowMenu` items, or a rewrite of the test-case steps to the token route. Met: an `element_token` click on the menu item `Show All Objects` and on a tree item changes FreeCAD (screenshots read); test-case steps written as `invoke_menu` do not run. Given FreeCAD with a box document, when `invoke_menu ["View","Visibility","Show All Objects"]` and one `element_index` click run in the container, then the FreeCAD screenshot of each shows the effect (the object shown or hidden; a menu or panel state), and the builder has read each screenshot. A scenario step written as `invoke_menu` or `element_index` needs no pixel rewrite.

G2 — runner and watchdog in the container.
- AC5. Given the container, when the runner starts a group, then FreeCAD 1.1.4 starts inside the container with `-M /repo/tests/uat/probe` and a temporary `-u`/`-s` profile; readiness uses `/healthz` naming its pid and the probe discovery file; no host process, `tasklist`, `%APPDATA%` or `FREECAD_EXE` is used. `results.json` `run` records the container FreeCAD version and the addon path.
- AC6. Given the preflight, when a FreeCAD already runs in the container or `:8765` is held there, then the run stops with exit 2 and names the pid or port; when a launch finds the same, it is exit 3. Teardown ends the FreeCAD the runner started, removes its discovery file, and waits until `:8765` is free in the container.
- AC7. Given the capture and menu steps, when a scenario runs, then the window frame, the capture PNG (readable on the host under the run folder) and the allow-listed menu steps use the container `cua-driver`; the Show All retry rule and the probe confirmation stay.
- AC8 (smoke). Given a run of the named scenarios `TC-02-02`, `TC-11-17` and two more that cover a pixel check and a menu step, when run into `tests/uat/run/2026-11-17-10-9-smoke/`, then exit is 0 or 1 with each non-PASS reason read; no group error; the builder reads each capture; `summary.md` and `results.json` exist.
- AC9 (watchdog). Given the container, when `uat_watchdog.py` runs, then it checks the cua session, the FreeCAD window by pid, the proxy handshake and the `FCB_TMP_snap_*` temp folders inside the container. With FreeCAD stopped it exits 1 naming the missing window; with a planted `FCB_TMP_snap_x` folder created after `--since` it exits 1 naming the folder; with neither it exits 0.

G3 — headless sweeps.
- AC10. Given the container, when `run_mcp_e2e.py` and `run_mcp_edge_cases.py` run from the host `uv` env, then each spawns the H1 front and its FreeCAD worker inside the container, reads golden models by container path, writes its report under `_automation/` on the host, and exits 0 with all checks passed (the 2026-10-23-02 baseline of the edge sweep is 13 of 13). A failed check is a reported finding. No file under `scripts/automation/` reads `FCB_ENV` or a `micromamba` path. A planted wrong golden path makes the sweep exit non-zero.

Unit and documents.
- AC11. Given the pure logic of the port (container command building, path translation, process and port parsing, the watchdog checks against faked command output), when `uv run pytest tests/external -q` runs, then the new tests pass, and each reads red against a deliberately broken input. `uv run ruff check .`, `uv run python scripts/check_imports.py` and `ruff format --check` on the changed files report 0 issues.
- AC12 (G4). Given the finished work, when the documents are read, then each states the new truth and none keeps a fixed limit: `tests/close-loop/README.md` ("Not proven" element actions), `tests/uat/runner/README.md` ("Not usable for UAT yet", Windows-only text), the UAT lines of CLAUDE.md and AGENTS.md section 9 (the two files stay identical), `uat-run-practices.md`, `freecad-gui-e2e-harness.md`, `tests/uat/test-plan.md` (NOT RUN lines, `FCB_ENV`, `FREECAD_EXE`) and `tests/uat/APPENDIX-B-environment-setup.md` step 3 (the `fcb` env). Where a limit stays (container render differs from Windows), the text says so.
- AC13. Given `deferred-work.md`, when the Story ends, then every entry it unblocks is resolved with a pointer to the evidence: the 10-9 port entry, the `fcb` env entry (APPENDIX-B step 3), and any entry on `element_index`, `invoke_menu` or the H1 sweeps found by the builder's search. Each other entry stays deferred with a one-line reason.

- AC14 (decision 11, launcher). Given the rebuilt image, when the XFCE Applications menu is opened, then it holds an entry "FreeCAD 1.1.4" (Categories Graphics;Engineering, the FreeCAD icon of the AppImage) that runs `fcb-freecad start`, and one launcher of the same name is on the desktop. Clicking the menu entry starts FreeCAD: `fcb-freecad status` shows a pid and the screenshot, read by the builder, shows the FreeCAD window. `tests/close-loop/README.md` documents it under Start.

## Design (plan, 2026-11-17)

Measured in `fcb-desktop` before planning:

- **C1 confirmed.** The long-lived `cua-driver mcp` (pid 7, started by the host `docker exec` at 05:51:46) began before `xfce4-session` (05:52:13). `bin/fcb-cua-mcp` runs `eval "$(fcb-session-env)"` once. `fcb-session-env` exits 1 with no session, but `eval` of an empty substitution succeeds under `set -e`, so `exec cua-driver mcp` runs with no `DBUS_SESSION_BUS_ADDRESS`. Fix: wait for the session like `bin/fcb-cua-serve` does (`until env_lines=...`), bounded at 120 s, then exit 1 with a message.
- **C2 not reproduced.** With the session up, `busctl` on the a11y bus (`unix:path=/home/cua/.cache/at-spi/bus_1`) answers `Registry ChildCount` = 11 and `GetChildren` lists 11 apps; `org.a11y.Status IsEnabled` is `true`. `cua-driver call get_window_state` on `xfce4-panel` (pid 476, window 16777236) returns `element_count` 10 with labelled buttons. The `NoReply` and 1-element reading is a transient or a wrong-window reading (the panel has a 3 px window). The plan re-measures on a fresh container start. If it reproduces, the fix is a registry readiness wait in `fcb-cua-serve`. If not, C2 is closed as disproved with these counts.
- **C3 confirmed, with a cause.** `libQt6Gui.so.6.8.3` has 0 matches for `a11y`, `atspi`, `ScreenReaderEnabled`, `QSpi`, and FreeCAD (pid 776) is absent from the a11y bus while `IsEnabled` is true. Qt `src/gui/configure.cmake:665` (tag v6.8.3) sets `accessibility-atspi-bridge` only when `ATSPI2_FOUND`. All 13 conda-forge `qt6-main` 6.8.x builds list `dbus` and no `at-spi2-core` in `depends`, so none has the bridge. The AppImage (`packages.txt`: `qt6-main 6.8.3 h75f3359_4`) holds no Qt headers or mkspecs.
- **G3 feasible.** `/opt/freecad/AppRun python` imports FreeCAD 1.1.4 (python 3.11.14) with `/opt/freecad/usr/lib` on `sys.path`, and has `pip`. The H1 front spawns its worker with `sys.executable` (`entry.py:179`), so one interpreter needs FreeCAD, `mcp`, `trimesh`, `lib3mf` and `freecad_buddy`.

Approach, in dependency order:

1. **C3 spike first (G1).** In a Docker build stage, build `libQt6Gui` of qtbase 6.8.3 with `libatspi2.0-dev` present (so `ATSPI2_FOUND`), using the `qt-main-feedstock` CMake arguments (`recipe/build.sh`) for the other features, and swap it into `/opt/freecad/usr/lib`. Gate: FreeCAD shows on the a11y bus and `get_window_state` returns File, Edit, View. If FreeCAD fails or crashes on the swapped library, stop and report. Fallbacks not chosen: B, build FreeCAD 1.1.4 from source on Debian trixie Qt 6.8.2 (OCCT 7.8.1 is there; an hour-scale build); C, Flatpak FreeCAD (KDE runtime has the bridge; needs bubblewrap privileges in the container and changes profile paths).
2. **C1 and C2 fixes** in `bin/fcb-cua-mcp` and, if C2 reproduces, `bin/fcb-cua-serve`. A host script `tests/close-loop/check_harness.py` (needs the container, so outside pytest and CI like `journey_box.py`) has named checks: the MCP environment holds the address when the session starts late (a shim `fcb-session-env` that fails for 5 s, read `/proc/<pid>/environ`); element counts of a GTK window and of FreeCAD. Red run: revert the `fcb-cua-mcp` wait and show the first check fail.
3. **Image:** a pinned site dir `/opt/fcb-site` from `/opt/freecad/AppRun python -m pip install --target`, with `mcp==1.28.1`, `trimesh` and `lib3mf` at the `uv.lock` versions and hashes. Helper `bin/fcb-py` evaluates `fcb-session-env`, sets `PYTHONPATH=/opt/fcb-site:/opt/freecad/usr/lib`, and runs `/opt/freecad/AppRun python "$@"`. The runner, the watchdog and the H1 host start through it.
4. **Runner port (G2).** `launch.py`: process list from `/proc` (match `/opt/freecad/usr/bin/freecad`); command `/opt/freecad/AppRun -M /repo/tests/uat/probe -u <tmp>/user.cfg -s <tmp>/system.cfg`; discovery glob under `~/.local/share` (`FreeCAD/*/fcb-uat-probe/probe-<pid>.json`); `check_tools` tests the AppRun path and the daemon; `stop` ends the process group. `capture.py`: `CUA_DRIVER = /usr/local/bin/cua-driver`. `run.py`: `REPO_ROOT` is `/repo`; `_git` records `null` when `git` or `.git` is unreadable on the read-only mount. `AppRun` ends with `"${MAIN}" "$@"` (a child, not `exec`), so its pid may differ from `/healthz` `freecad_pid`; readiness then matches the process tree. I verify this first.
5. **Watchdog port (G2).** Checks stay; `_cua` uses `/usr/local/bin/cua-driver`; the proxy URL stays `:8765` (container); temp hygiene reads container `/tmp`; Linux has no creation time, so `_created_after` uses `st_ctime`.
6. **Sweeps (G3).** `_fcb_env` is replaced by a `docker exec -i -u cua -e PYTHONPATH=... fcb-desktop fcb-py -m freecad_buddy.hosts.main serve --mode inline --transport stdio` command. `PYTHONPATH` adds `/repo/src`, so the working tree is tested. `GOLDEN_DIR` and every path sent to the server become `/repo/...`; the report stays in host `_automation/`.
7. **Smoke and demo (UAT).** Smoke scenarios: `TC-02-02` (menu step and pixel check), `TC-02-04` (menu step with a retry history), `TC-11-17` (pixel check, past false alarm), `TC-05-03` (a `launch` map, so a second FreeCAD group tests teardown and relaunch). Element demo: `invoke_menu` plus `element_index`, screenshots read.
8. **Docs and deferred entries** (AC12, AC13) last, once measured values exist.

## Leader Conditions (approved plan, route A for C3)

C3 route A is approved (epic-10 decision 9). Conditions:
- Pin the qtbase 6.8.3 source tarball by SHA-256. Build in a separate cached stage; the runtime image receives only the rebuilt library.
- Match the conda-forge `qt6-main` 6.8.3 configure features (`qt-main-feedstock` `recipe/build.sh`; measure what you can from the AppImage libraries) so only the AT-SPI bridge differs. Before use, compare the swapped library's exported symbol versions (`Qt_6`, `Qt_6_PRIVATE_API`) with the original's.
- At most 2 build attempts. If FreeCAD 1.1.4 does not start and pass `journey_box.py` on the swapped library after 2, stop and report the evidence; do not start route B (a user question).
- Guard: the FreeCAD binary is unchanged, so prove the swap changes nothing else: capture one scene with the original library and the same scene with the swapped one (same image build otherwise, same window size), compare, read both. Re-run `journey_box.py`.
- C2: re-measure on a fresh container start. If it does not reproduce, record it as disproved with that evidence (epic-10 decision 10).
- C1: the wait is bounded at 120 s; a timeout fails loudly and never starts `cua-driver mcp` without the bus.
- Smoke scenarios `TC-02-02`, `TC-02-04`, `TC-11-17`, `TC-05-03` into `tests/uat/run/2026-11-17-10-9-smoke/`.

Environment and boundaries:
- Work in `D:\Work\Personal\Sources\freecad-buddy` on branch `story/10-9-uat-runner-in-container`. No commit, no merge, no push. Never stage or edit `.leader.json`, `epic-10-status.md`, `epic-10-decisions.md`, `quality-bar-10-9.md`, `review-ledger-10-9.md`. Read `quality-bar-10-9.md` (Q1-Q16) and meet each row.
- Shell: Git Bash (POSIX) and PowerShell 7; `uv`, `docker`, `docker compose` present. Host FreeCAD `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe` only with `-u <tmp>\user.cfg -s <tmp>\system.cfg`; never the GUI, never the developer `%APPDATA%\FreeCAD\v1-1\user.cfg` (SHA-256 baseline `b89a97711941619bb0ba74ae04fb888025e82f49ff48174fbebb42aed28d85a`; report it at the end).
- The container `fcb-desktop`, image `fcb-desktop:local`, ports 6901 and 18765 are yours to stop, rebuild and restart. Leave it running with FreeCAD started when done. Leave no other process or temp file.
- Gates: `uv run ruff check .`, `uv run python scripts/check_imports.py`, `uv run pytest tests/external -q`, `freecadcmd.exe -u/-s tests/run_tests.py`, `uv run ruff format --check <changed files>` (29 older files already fail; leave them). Quality checks of CLAUDE.md `npm run` do not apply. After any change under `src/` or the image: `uv run python scripts/build_addon.py --release`, `docker compose -f tests/close-loop/docker/compose.yaml up -d --build`, `docker exec -u cua fcb-desktop fcb-freecad start`, wait for `freecad_pid` in `http://127.0.0.1:18765/healthz`.
- Known unstable test: `tests/external/test_managed_venv.py::test_Should_start_an_external_interpreter_When_freecad_set_pythonhome` fails in the full run and passes alone.
- Edit files with the edit tools. Cut long output with a tail or a log file. Comments only for a non-obvious why; tests named `Should <outcome> When <condition>` with `# Arrange` / `# Act` / `# Assert`.
- Prove at least one fix falsifiable: revert it, show the check go red, restore it. Paste counts.
- Write the full report to `_bmad-output/implementation-artifacts/report-10-9-builder.md`.

## Implementation Notes

- C3 (route A, decisions 9, 12, 14): three Qt builds. Attempt 1 (xcb and wayland off) lacked 83 exported symbols. Attempt 2 (xcb, xcb_xlib, wayland on) differed in 4 names, all measured as unimported by any of 1980 ELF files. Attempt 3 added `libQt6XcbQpa`, where `QXcbIntegration::accessibility()` creates the bridge. The first image then hung: gdb showed the main thread in `pthread_mutex_lock` under `NotificationArea::pushNotification` under `showInNotificationArea` (`NotificationArea.cpp:1143`), re-entered by the bridge's `Received text event for invalid interface` warning. `QT_LOGGING_RULES=qt.accessibility.atspi.warning=false` removes it.
- C2 not reproduced; the earlier `NoReply` reading came from `dbus-send --address=<a11y bus>`, which does not register first (`busctl` does).

## Spec Change Log

## Review Triage Log

Round 1, lenses: Blind Hunter (opus, high, agent a877e24789249d4fa), Edge Case Hunter (opus, high, agent a1339bc70a7f1b862), Verification Gap (sonnet, medium, agent a774d1e6d3d58efee). Verdict, route and evidence per finding.

| # | Finding (lens) | Verdict | Route | Evidence |
| --- | --- | --- | --- | --- |
| 1 | Probe discovery file stays when readiness fails (Blind, Edge x2, Gap) | medium | patch | `launch.stop` read only the ready pid; it now deletes the file of every pid below the started process; test `Should_delete_the_discovery_files_of_every_started_pid_When_readiness_failed` |
| 2 | A later `QT_LOGGING_RULES` rule re-enables the atspi warning (Edge x2) | medium | patch | Qt applies the last matching rule; the silencing rule now goes last in `launch_environment` and `fcb-freecad`; tests for env and launch-map rules |
| 3 | Menu press does not check the item is enabled (Blind) | medium | patch | `capture.invoke_menu` waits up to 5 s for the enabled flag, then raises; two tests |
| 4 | Stale foreground wording in `run.py` (Blind) | low | patch | comments, docstring and error text rewritten |
| 5 | Known menu defect not in the runner docs (Blind) | medium | patch | the defect was a first-press no-op, found in this round and fixed in `run.menu` (redelivery up to `MENU_ATTEMPTS`, 2 tests); README section "Menu step in the container" |
| 6 | Swap script header describes one library (Blind) | low | patch | header and usage line name both libraries |
| 7 | Qt version written in two places (Blind) | low | reject | the library file names must equal the AppImage's; a second ARG adds a path to keep equal for no gain |
| 8 | `libatspi2.0-0` not in the runtime apt list; no import check (Blind) | false | reject | `ldd -r` of both rebuilt libraries in the final image reports no unresolved symbol or missing library; `at-spi2-core` depends on `libatspi2.0-0` |
| 9 | H1 proof of running `/repo/src` removed (Blind) | high | patch | measured: `import FreeCAD` puts `Mod/FreeCADBuddy` ahead of `/repo/src`, so the sweeps test the installed addon. `PYTHONPATH` now names that folder; docs and docstrings say "installed addon" |
| 10 | `test-plan.md` drops variables the test cases use (Blind) | medium | patch (leader R1-10) | `$FREECAD_EXE`, `$FCB_ENV` replaced in step and Given text (32 lines in 15 files, no Then); `$FCB_PYTHON` defined as `scripts/automation/fcb_py.sh`; one line per variable run in the container |
| 11 | No positive tests for `wait_until_ready` and `freecad()` (Blind, Gap x2) | medium | patch | 2 tests added (readiness returns the child's record; `Popen` kwargs and `stop` pid) |
| 12 | `NOT RUN` wording in the harness standard (Blind) | low | patch | reworded |
| 13 | Shared sweep scratch folder; exports not copied out (Blind, Edge) | low | reject | sweeps run one after another; the docstring now says only the render and the reports reach the host |
| 14 | Stray spaces in the runner README command (Blind) | low | patch | fixed |
| 15 | Profile-hash step lost its reason (Blind) | low | patch | the step says it guards host-side FreeCADCmd calls |
| 16 | Watchdog `ctime` tests run on Windows (Blind) | low | reject | the Linux behaviour is exercised live (planted folder, exit 1); a unit test of inode time adds nothing |
| 17 | `check_harness.py` trap uses an unset variable (Blind, Edge) | low | patch | `mcp_pid=""` before the trap |
| 18 | FreeCAD detection by exact `argv[0]`; `FREECAD_BINARY` independent of `FREECAD_APPRUN` (Blind, Edge) | low | reject | the override is for tests; widening adds a branch for a case the image never has |
| 19 | No `DISPLAY` check; SIGKILL leaves the a11y registration; stale file after pid reuse (Edge) | maybe-false | reject | `fcb-py` exports the session; a stale registration did not stop the next group (4 consecutive launches); pid reuse is covered by finding 1 |
| 20 | Watchdog `--since` timezone and `ctime` edge cases (Edge) | low | reject | the live planted-folder run passed with a UTC cutoff; no failure shown |
| 21 | Sweep: checkout mismatch, `docker cp` exception, audit log lost (Edge, Gap) | low | reject | thin wrappers, exercised live (29/29, 14/14); the audit log is not a deliverable |
| 22 | Desktop launcher may need a trusted checksum (Edge) | maybe-false | reject | the menu entry was clicked and started FreeCAD (evidence); the desktop launcher exists; a double-click was not tested |
| 23 | Watchdog counts `/tmp` snapshots, the bridge writes `<workdir>/tmp` (Edge, claim) | medium | patch (leader R1-23) | `check_temp` reads `<workdir>/tmp/FCB_TMP_session_*/`; `--workdir`; 4 live cases (clean 0, planted in old `/tmp` 0, planted in real dir 1, FreeCAD stopped 1) |
| 24 | AC4: test-case `invoke_menu` steps still fail (Edge, claim) | medium | defer | driver limit, deferred entry exists; the runner and the demo use the token route |

Round 2, lenses: Blind Hunter (opus, high, agent a55189f6b4591cf43), Edge Case Hunter (opus, high, agent a940d1f7bcc1ffe03), Verification Gap (sonnet, medium, agent a749ce62c03bc176e), on the whole Story diff against 97fac62.

| # | Finding (lens) | Verdict | Route | Evidence |
| --- | --- | --- | --- | --- |
| R2-1 | `invoke_menu` fails at once on an item missing from a partial tree; click refusal has no refusal prefix; no `elements` key (Blind, Edge x3) | medium | patch | loop waits for missing or disabled items up to `MENU_ENABLE_S`; refused click re-raised with `menu_path_unavailable`; 3 tests; mutation (no wait) fails 2 tests |
| R2-2 | Redelivery after an unconfirmed press raises a raw `CuaError` (Blind, Edge, Gap) | medium | patch | `run.menu` is one loop with one refusal rule; tests for refused-after-unconfirmed and last-refused |
| R2-3 | Repeated press hides why it repeated (Blind, Edge claim) | medium | patch | step record has `attempt_log`; runner3 TC-11-17 shows `delivered, no effect` once; README says to read it |
| R2-4 | Runner docs contradict code (Blind) | low | patch | `run.py` docstring, `menu` docstring, README rewritten |
| R2-5 | `stop` cleans discovery files for a different pid set than it kills (Blind, Edge) | medium | patch | `started_pids` adds the process group; test with an orphaned FreeCAD (parent init, group 10); mutation fails it |
| R2-6 | Watchdog passes when the checked folder does not exist (Blind, Edge, Gap) | medium | patch | `CheckFailed` when `<workdir>/tmp` is absent; live: `--workdir /tmp/nope` exit 1; 2 tests |
| R2-7 | `_created_after` docstring false; naive `--since` timezone (Blind, Edge) | low | patch | docstring and `--since` help corrected |
| R2-8 | New watchdog test cannot fail (Blind) | medium | patch | test sets `tempfile.tempdir` to the planted folder, so it reads red on the old code |
| R2-9 | `fcb_py.sh` untested, silent without `PROJECT_ROOT`, one path spelling, host values leak (Blind, Edge x3, Gap) | medium | patch | exit 2 without `PROJECT_ROOT`; backslash spelling; warning for host-looking values; 4 tests with a fake `docker`; mutation fails one. Forwarding of `FREECAD_BUDDY_*` stays (the cases pass settings that way) |
| R2-10 | `fcb-freecad start` file arguments and logging rule untested (Gap) | medium | patch | `check_harness.py` check `freecad-logging-rule` (PASS); argument forwarding shown live by the TC-02 launch line opening `box40-hole-r5` |
| R2-11 | `default_workdir` glob and fallback untested (Gap) | medium | patch | 2 tests |
| R2-12 | Reopen-with-file steps close FreeCAD with `invoke_menu File>Exit` (Blind) | medium | patch | TC-02, TC-12 lines use `fcb-freecad stop`; TC-01 wording |
| R2-13 | New tests combine Act and Assert (Blind) | low | patch | 7 tests split |
| R2-14 | TC steps with host tools after `$FCB_PYTHON` moved (Get-Process, TC-11-19 sleeper, mixed preconditions) (Blind x2) | medium | defer | R1-26: deferred entry names TC-10 worker-pid steps and TC-11-19 |
| R2-15 | `v1-1` written in three places (Blind) | low | reject | one version folder per image; the glob in the watchdog covers a change |
| R2-16 | Stale probe file with a reused pid (Edge) | low | reject | `stop` deletes the file of every started pid |

Round 3 (last), lenses: Blind Hunter (opus, high, agent a2c265bf9c9c321a7), Edge Case Hunter (opus, high, agent a2c8f2089769c1af2), Verification Gap (sonnet, medium, agent a0226a6bd4a5811a6), on the whole Story diff against 97fac62; fixed point `97fac62` plus the tree at 37 files +856/-395.

| # | Finding (lens) | Verdict | Route | Evidence |
| --- | --- | --- | --- | --- |
| R3-1 | Watchdog fails on a clean, freshly started FreeCAD: `<workdir>/tmp` does not exist before first use (Blind, Edge) | high (breaks AC9 "clean exits 0") | patch | reproduced: `mv workdir/tmp workdir/tmp.bak` then the watchdog exit 1; now a missing `tmp` is zero, a missing workdir the operator named is an error; live on a recreated container (tmp absent) exit 0; tests |
| R3-2 | `run.menu` error text says "refused on 3 of 3" for mixed outcomes; log lost on the failure path (Blind, Edge) | medium | patch | message counts each outcome and carries `last_menu_log`; mixed and pure cases tested; record test for `attempt_log` |
| R3-3 | `invoke_menu` treats a click timeout or non-JSON reply as a refusal and repeats it (Blind) | medium | patch | only an answer the driver refused is wrapped; test with `click exited 1` |
| R3-4 | `fcb_py.sh` drops a trailing `=`; rewrites sibling folders (`<root>2`); trailing-slash root; backslash arguments (Blind, Edge x3, Gap) | medium | patch | `read -r line`, boundary rewrite, `%/`, slashes for backslash arguments; reproduced then 5 new tests |
| R3-5 | `swap-qt-gui.sh` `|| true` hides a grep failure (Blind, Q14) | medium | patch | `|| [ $? -eq 1 ]`; bad pattern now stops (exit 1), image rebuilt, swap passes |
| R3-6 | Runner launch error does not name a missing desktop session (Blind) | medium | patch | preflight `DISPLAY` check; test |
| R3-7 | README says `check_harness.py` checks the press; `summary.md` paths are container paths; `pgrep` pattern too broad (Blind) | low | patch | README sentences, pattern with `( \|$)` |
| R3-8 | Test gaps: pre-kill snapshot order, docker command line, `--workdir` wiring, render count, `attempt_log` in the record (Gap) | medium | patch | 5 tests; the pre-kill test removes the fake process at `killpg` |
| R3-9 | Delivered press with no effect is repeated until it passes (Blind) | medium | reject | accepted by the leader as R2-3; every repeat is in `attempt_log` and the probe confirms the effect |
| R3-10 | `wait_until_ready` and `started_pids` disagree when AppRun exits (Blind) | low | reject | AppRun runs FreeCAD as a child and waits for it, so an AppRun exit is a FreeCAD exit; the group case only widens cleanup |
| R3-11 | `fcb-freecad start` file argument forwarding has no automated check (Gap) | low | defer | shown live (TC-02 launch line); add a `cmdline` check when `check_harness.py` is next extended |
| R3-12 | Hard-coded addon path in three places; invented menu fixture; Q10 says 13 of 13 (Blind) | low | reject | suggestions without a failing input; Q10 is a leader-owned file |
| R3-13 | `Edit > Recompute` press has no probe effect; `get_window_state` failure in the poll loop (Edge) | low | reject | conditional on a drop never measured for Recompute; a failed state read is a real fault |
| R3-14 | Stale probe file with a reused pid (Edge, suggestion) | low | reject | `stop` deletes the files of every started pid |

## Verification

**Manual checks:**
- Every screenshot named in AC4 and AC8 is read, and the effect is described in the report.
- Counts (elements before and after, sweep pass counts, pytest counts) are pasted, not exit codes.
