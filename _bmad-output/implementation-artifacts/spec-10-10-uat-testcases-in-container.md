---
title: 'Story 10.10: UAT test cases run in the fcb-desktop container'
type: 'chore'
created: '2026-11-18'
status: 'in-review'
baseline_commit: '031d8e868cad07e3a98c424480b29c1a381bbcb8'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-10-9-uat-runner-in-container.md'
  - '{project-root}/_bmad-output/implementation-artifacts/review-ledger-10-9.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-10-decisions.md'
  - '{project-root}/tests/close-loop/README.md'
  - '{project-root}/tests/uat/runner/README.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/uat-run-practices.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `tests/uat/testcases/TC-01..TC-99` still hold Windows-host commands in Given, When, Then and Preconditions text.
A tester who follows them in the `fcb-desktop` container hits commands that do not exist there (`tasklist`, `netstat -ano`, PowerShell `& cua-driver call`), paths that do not exist there (`$APPDATA/FreeCAD/v1-1/...`, `.venv/Scripts/python.exe`, `$TEMP`), and a host URL the container does not serve (`127.0.0.1:8765` is container-internal; the host reaches the proxy on `:18765`).
Story 10-9 replaced only `$FREECAD_EXE`, `$FCB_ENV` and `$FCB_PYTHON`.
Story 10-8 (new UAT Gate 1 run in the container) cannot start before the rest is done (user decision 17, 2026-11-18).
Ledger entries: R1-26, R2-14 (all commands), R1-24 (`invoke_menu` on the Qt menu bar).

**Approach:** One rewrite rule per command kind (section "Rewrite rules"), applied to the test cases, `test-plan.md` and `APPENDIX-B`.
Each rewritten kind is run once in the container and the output is saved.
Expected behaviour does not change: a `Then` or `And` observable keeps its words.

## Decisions

- **D1 — Replace, do not duplicate.** A host command is replaced. No test case keeps a "Windows:" and a "container:" variant.
- **D2 — Observable is frozen.** For every `Then` and `And` line under a `Then` block, the text before the first ` — verify:` is equal before and after, except the one listed line (section "Then lines that change"). The text after ` — verify:` (the check) may change, because the check is where the host command lives.
- **D3 — Notation, not new behaviour.** `cua-driver` stays the tool. The test cases name it through one variable, `$FCB_CUA`, as 10-9 did for `$FCB_PYTHON`.
- **D4 — Paths.** Host-side commands keep host paths for the repo and the run folder (the container mounts the same files). Commands about FreeCAD's own state (addon log, discovery file, user data, `/tmp`) run in the container and use container paths through variables.
- **D5 — Menu route.** `invoke_menu` on a Qt menu bar item is refused by `cua-driver` 0.28.1 (R1-24). A step that needs a menu command presses the leaf item by `element_token`, as `tests/uat/runner/capture.py:121` does, or sends the menu's shortcut key. No test case relies on `invoke_menu` for a FreeCAD menu.

## Boundaries & Constraints

**Always:**
- Test-case format stays Given/When/Then. Every `**Given**`, `**When**`, `**Then**`, `**And**` line keeps its two trailing spaces (`grep -n '^\*\*\(Given\|When\|Then\|And\)\*\*' TC-*.md | grep -v '  $'` prints nothing).
- Rule 14 of the `manual-testing` skill holds: no machine path. `grep -rn "D:/\|C:\\\\\|/Users/" tests/uat/testcases/` prints nothing.
- New variables are defined in `test-plan.md` §6 "Environment Variables" and in `APPENDIX-B`.
- Every rewritten command was executed once in the container (proof folder).

**Never:**
- Change a `Then` observable (D2) other than the listed line.
- Edit `src/`, the runner, the watchdog, `uat/scenarios/` (they encode Thens; they stay valid because no observable changes), the probe README (D-2), `run_faults.py` (D-1), or the canary (Story 10-8, decision 19).
- Start the host FreeCAD, write `%APPDATA%\FreeCAD\v1-1\user.cfg`, or write the container `user.cfg` (TC-06 reads it only).
- Edit an existing folder under `tests/uat/run/`, or the leader files `epic-10-*.md`, `sprint-status.yaml`.
- Commit, push or merge.

</frozen-after-approval>

## Census (measured 2026-11-18 at `031d8e8`)

Script: `tests/uat/run/2026-11-18-10-10-proof/census.sh [testcases-dir]` (counts lines, not matches;
needs `LC_ALL=C.UTF-8` for `grep -P`). Output before: `census-before.txt` (the baseline folder from
`git archive 031d8e8`). Output after: `census-after.txt`, which also lists each remaining hit.

| Kind | Pattern (host command) | Before | After |
|---|---|---|---|
| K1 | `cua-driver call`, `& cua-driver` | 635 | 0 |
| K1b | `cua-driver status\|doctor\|kill_app\|launch_app\|list-tools\|serve\|stop` | 9 | 0 |
| K2 | `invoke_menu` (not `invoke_menu(["View","Fit All"])`: 345 lines state that it is refused, true in the container) | 64 | 0 |
| K3 | `netstat` | 51 | 0 |
| K4 | `tasklist`, `taskkill` | 19 | 0 |
| K5 | `Get-Process`, `Stop-Process`, `Start-Process`, `powershell`, `Get-CimInstance`, `Win32_Process`, `cmd.exe` | 45 | 0 |
| K6 | PowerShell file cmdlets | 36 | 0 |
| K7 | `APPDATA`, `%VAR%`, `$env:` | 78 | 0 |
| K8 | `$TEMP`, `.exe`, `C:\`, `Scripts/`, `.cmd`, junction | 34 | 0 |
| K9 | host-run `curl ...:8765`, `ipconfig`, `http.server 8765`, `Invoke-RestMethod` (a line with `docker exec` is container-side) | 11 | 0 |
| K10 | `launch_env`, `launch_app`, `uv run python -c "` snippets that read container files or ports | 17 | 0 |
| any | union of the lines above | 905 | 0 |

Other host files: `tests/uat/test-plan.md` 5 lines and `tests/uat/APPENDIX-B-environment-setup.md` 17 lines
(rewritten by the same rules); `README.md` 2 lines and `coverage-matrix.md` 1 line.

K1b, K8 and K9 were narrowed during the build (a first version matched the word "cua-driver tool", the
python text `d:\n`, and the in-container address in a log line). K10 was added after the build found
host scripts that need the container (`_automation/uat/launch_env.sh`, `close_all.py`, `uv run python`
snippets that open the RPC discovery file or the listener socket).

## Container facts (measured in `fcb-desktop`, FreeCAD running, 2026-11-18)

| Need | Container fact |
|---|---|
| Process list | `pgrep`, `ps`, `kill`, `ss`, `netstat`, `lsof`, `curl`, `nc` exist. `tasklist`, `powershell`, `jq` do not. |
| Port owner | `ss -ltnp` prints `LISTEN 0 2048 127.0.0.1:8765 ... users:(("python",pid=728,fd=6))`. `netstat -tlnp` prints `127.0.0.1:8765 ... LISTEN 728/python`. |
| FreeCAD process | `pgrep -af '^/opt/freecad/usr/bin/freecad'` (the pattern `fcb-freecad` uses). `AppRun` is a separate bash parent. |
| Proxy command line | `/home/cua/.local/share/FreeCAD/v1-1/FreeCADBuddy/venv/bin/python -m freecad_buddy.hosts.main serve --mode rpc --transport http` (from `pgrep -af`). |
| User data dir | `/home/cua/.local/share/FreeCAD/v1-1/` holds `Mod`, `FreeCADBuddy`, `freecad-buddy/` (`addon.log`, `mcp-proxy.log`, `rpc-<pid>.json`). |
| Config dir | `/home/cua/.config/FreeCAD/v1-1/` holds `user.cfg`, `system.cfg`. |
| Temp dir | `/tmp` (the FreeCAD log is `/tmp/freecad.log`). |
| Proxy reach | Inside: `127.0.0.1:8765`. Host: `127.0.0.1:18765` (socat relay, listens on `0.0.0.0` in the container). |
| CLI | `echo '{"pid":555}' \| docker exec -i -u cua fcb-desktop bash -c 'eval "$(fcb-session-env)"; /usr/local/bin/cua-driver call list_windows'` returns the window list (pid 555, `window_id` 37748829, title `FreeCAD 1.1.4`). |
| Addon in FreeCAD | A copy installed from `dist/addon/`, not a junction to `src/`. |

## Rewrite rules

Variables added to `test-plan.md` §6 (exported with `PROJECT_ROOT`, `RUN_DIR`, `FCB_PYTHON`):

```bash
export FCB_CUA="$PROJECT_ROOT/scripts/automation/fcb_cua.sh"      # cua-driver CLI in the container (see Q1)
export FCB_USER_DIR=/home/cua/.local/share/FreeCAD/v1-1           # container path
export FCB_CONFIG_DIR=/home/cua/.config/FreeCAD/v1-1              # container path
```

`$FCB_EXEC` is not a variable. A command that runs in the container is written in full: `docker exec -u cua fcb-desktop <command>`.

| Kind | Host form (before) | Container form (after) | Example |
|---|---|---|---|
| **K1** `cua-driver call` | `'<json>' \| & cua-driver call <tool>` | `echo '<json>' \| "$FCB_CUA" <tool>`. The wrapper runs `/usr/local/bin/cua-driver call <tool>` in the container with the session environment, and maps a literal `$PROJECT_ROOT` or `$RUN_DIR` in the JSON to its `/repo/...` path. A prose form `cua-driver call T { ... }` becomes `"$FCB_CUA" T { ... }`. | `'{"pid":<pid>,"window_id":<wid>}' \| & cua-driver call get_window_state` -> `echo '{"pid":<pid>,"window_id":<wid>}' \| "$FCB_CUA" get_window_state` |
| **K1b** other `cua-driver` subcommands | `cua-driver status`, `cua-driver kill_app { pid }`, `cua-driver launch_app` | `"$FCB_CUA" status` (the wrapper passes `status`, `doctor`, `list-tools`, `describe` through and uses `call` for every other word). `launch_app` of FreeCAD is replaced by `docker exec -u cua fcb-desktop fcb-freecad start` (the harness rule). | `cua-driver status` -> `"$FCB_CUA" status` shows `Cua Driver daemon is running` |
| **K2** `invoke_menu` | `invoke_menu {path:["View","Visibility","Show All Objects"]}` | Press the leaf by token: `get_window_state` with `include_screenshot:false`, take the `element_token` of the element whose label is the leaf (`Show All Objects`), then `click` it. Fallback: the shortcut key with `hotkey`. | Exit: leaf `Exit`, or `hotkey ["ctrl","q"]`. New Document: leaf `New`, or `hotkey ["ctrl","n"]`. `Windows` menu entries are not named (`Activates this window`): press `Next` or `Previous` and read the `list_windows` title. |
| **K3** `netstat` | `netstat -ano \| grep :8765` shows `LISTENING` | `docker exec -u cua fcb-desktop ss -ltnp \| grep :8765` shows `LISTEN` and `users:(("python",pid=<n>`. The word `LISTENING` in the check becomes `LISTEN`. A "no row" check keeps its meaning. | `netstat -ano \| Select-String ":8765" \| Select-String "LISTENING"` -> `docker exec -u cua fcb-desktop ss -ltnp \| grep ':8765'` |
| **K4** `tasklist`, `taskkill` | `tasklist \| grep -i freecad.exe`; `taskkill //PID <pid> //F` | `docker exec -u cua fcb-desktop pgrep -af '^/opt/freecad/usr/bin/freecad'` (`freecad.exe` -> `freecad`); one pid: `docker exec -u cua fcb-desktop ps -p <pid> -o pid=,comm=` (exit 1 and no row when the pid is gone); force kill: `docker exec -u cua fcb-desktop kill -KILL <pid>`. | `tasklist \| grep <pid>` returns nothing -> `docker exec -u cua fcb-desktop ps -p <pid> -o pid=` returns nothing, exit 1 |
| **K5** PowerShell process tools | `Get-Process -Name freecad`; `(Get-Process -Id <pid>).CPU`; `(Get-Process -Id <pid>).WorkingSet64`; `Stop-Process -Id <pid> -Force`; `Get-CimInstance Win32_Process ... CommandLine`; `cmd.exe` + `start` | `pgrep` as in K4; CPU seconds: `ps -o cputimes= -p <pid>`; resident bytes: `ps -o rss= -p <pid>` (KiB; the check multiplies by 1024 and says so); `kill -KILL <pid>` as in K4; command line: `docker exec -u cua fcb-desktop sh -c "tr '\0' ' ' < /proc/<pid>/cmdline"`; FreeCAD start with a macro or environment: `docker exec -u cua -e NAME=value fcb-desktop fcb-freecad start /repo/<macro path>`. | `powershell -NoProfile -Command "(Get-Process -Id <worker pid>).CPU"` -> `docker exec -u cua fcb-desktop ps -o cputimes= -p <worker pid>` |
| **K6** PowerShell file cmdlets | `Test-Path`, `Get-ChildItem`, `Get-Content -Tail`, `Select-String` | Repo or run-folder file: `test -e <path> && echo True`, `ls`, `tail -n`, `grep` on the host. FreeCAD-state file: the same command after `docker exec -u cua fcb-desktop`. | `Select-String AntiAliasing "$env:APPDATA/FreeCAD/v1-1/user.cfg"` -> `docker exec -u cua fcb-desktop grep AntiAliasing "$FCB_CONFIG_DIR/user.cfg"` |
| **K7** `%APPDATA%`, `$APPDATA`, `$env:APPDATA` | `$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log` | `$FCB_USER_DIR/freecad-buddy/addon.log`, read with `docker exec -u cua fcb-desktop cat\|grep\|ls\|mv`. `user.cfg` is `$FCB_CONFIG_DIR/user.cfg`, read only. In prose, `%APPDATA%\FreeCAD\v1-1\freecad-buddy\workdir` -> `$FCB_USER_DIR/freecad-buddy/workdir`. | `grep "spawned MCP proxy" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` -> `docker exec -u cua fcb-desktop grep "spawned MCP proxy" "$FCB_USER_DIR/freecad-buddy/addon.log"` |
| **K8** host interpreter, temp, link | `.venv/Scripts/python.exe -m freecad_buddy.hosts.main serve ...`; `"$TEMP"/x`; `Junction` check on the addon | `"$FCB_PYTHON" -m freecad_buddy.hosts.main serve ...` (the wrapper already runs it in the container); `/tmp/x` created and counted with `docker exec -u cua fcb-desktop`; the installed addon is the image copy: `docker exec -u cua fcb-desktop sha256sum $FCB_USER_DIR/Mod/FreeCADBuddy/freecad_buddy/__init__.py` equals `sha256sum dist/addon/FreeCADBuddy/freecad_buddy/__init__.py` on the host (the builder confirms the exact `dist/addon` path in build). A `.cmd` wrapper or `pythonw.exe` launcher sentence is removed (no such file in the container). | `find "$TEMP" -maxdepth 1 -name 'FCB_TMP_*' \| wc -l` -> `docker exec -u cua fcb-desktop sh -c "find /tmp -maxdepth 1 -name 'FCB_TMP_*' \| wc -l"` |
| **K9** host client to the proxy | `curl -s http://127.0.0.1:8765/healthz`; `ipconfig \| grep IPv4`; `uv run python -m http.server 8765` | A check that only needs the proxy to answer uses the relay: `curl -s http://127.0.0.1:18765/healthz`. A check about the bind (loopback only, LAN refused, port held) runs in the container, because the relay hides the bind: `docker exec -u cua fcb-desktop curl -s http://127.0.0.1:8765/healthz`. LAN address: `docker exec -u cua fcb-desktop hostname -I`. Foreign holder: `docker exec -d -u cua fcb-desktop fcb-py -m http.server 8765 --bind 127.0.0.1`, removed with `docker exec -u cua fcb-desktop pkill -f 'http.server 8765'`. | `ipconfig \| grep IPv4` -> `docker exec -u cua fcb-desktop hostname -I` |
| **Proxy restart by hand** (10 Cleanup and When lines) | "restart the proxy with the addon's command line (from `Win32_Process.CommandLine`)" | Read the command line from `/proc/<proxy pid>/cmdline` (K5) before the kill, then `docker exec -d -u cua -e FREECAD_BUDDY_<NAME>=<value> fcb-desktop <that command line>`. | Same sentence, container form. The builder runs it once and records whether the new proxy serves `/healthz` (see Q3). |
| **Forbidden-command lines** (TC-06:57, TC-12:83-85, TC-13:124) | "Forbidden: `Start-Process`, `SetForegroundWindow`, `taskkill /F`" | "Forbidden: `wmctrl -a`, `xdotool windowactivate`, `kill -KILL`" (the container's way to raise a window or end a process). The integrity-level sentences (TC-10:518, TC-12:26, :84-85, :856) are removed: the container shell and FreeCAD run as the same user `cua`. | |

The wrapper is code, so it needs a test (Q1): `tests/external/test_fcb_cua_wrapper.py` in the style of `tests/external/test_fcb_py_wrapper.py`.

## Then lines that change

Observable (text before ` — verify:`), listed one by one. `then-check.py` fails on any other head change.

| Scenario | Line (at `031d8e8`) | Change | Reason |
|---|---|---|---|
| TC-01-09 | TC-01:368 | `the mode is restricted, best-effort on Windows` -> `the mode is restricted` | The container is POSIX: `chmod 600` is enforced, so the "best-effort on Windows" exception has no case. The verify text keeps `-rw-------`. |
| TC-09-09 | TC-09:403 | `Activate <H> through its numbered Windows menu entry: the entry reads <n> box-10-20-30 : 1* ...` -> `Activate <H> through the Next leaf of the Windows menu ... pressed until the list_windows title names box-10-20-30` | The head holds the instruction. In the container the numbered `Windows` entries expose only `Activates this window` (measured, `K2-menu-more.txt`), so an entry cannot be chosen by name; the expected result (`<H>` active, title names it) is the same. |

## Acceptance Criteria

Proof folder: `tests/uat/run/2026-11-18-10-10-proof/` (`PF`).

- **AC1 (census).** `census-after.txt`: K1..K10 and `any` are 0. The only stated exception is the 345
  `invoke_menu(["View","Fit All"])` refusal statements, which K2 does not count. MET.
- **AC2 (each kind runs).** `PF/K1.txt` .. `K10.txt` (`proof.sh` runs them in one pass),
  `K2-menu-exit.txt`, `K2-menu-leaves.txt`, `K2-menu-more.txt` (menu leaves), `K-proxy-restart.txt`
  (proxy by hand), `K-freecad-cwd.txt`. Every output has its command line first. MET.
- **AC3 (Thens frozen).** `then-check.txt`: 2340 Then/And lines, 0 head failures with the two listed
  lines allowed; `then-check-planted.txt`: a planted head edit exits 1. `then-verify-diff.txt` tags the
  370 changed verify clauses (`rule:K<n>` or `hand` with a reason). MET.
- **AC4 (format).** Hard-break count per file equals the baseline (37 lines in TC-15 lack the two
  spaces at `031d8e8` and still do); no machine path except the user project source in TC-16 (a host
  `cp` source); 17 files, scenario headings unchanged. MET, with that TC-16 exception.
- **AC5 (runner scenarios).** `git diff --stat 031d8e8 -- tests/uat/scenarios tests/uat/runner` is empty;
  `uv run pytest tests/external -q -k uat_runner` is green. MET.
- **AC6 (documents).** `test-plan.md` §6 defines `FCB_CUA`, `FCB_USER_DIR`, `FCB_CONFIG_DIR`, `RUN_DIR_C`
  and holds the "Menu route" and "Process commands" sections; `APPENDIX-B` steps 1, 2, 4, 5 and the
  usage rules are container text. MET.
- **AC7 (wrapper).** `tests/external/test_fcb_cua_wrapper.py` 19 tests green (30 with `test_fcb_py_wrapper.py`); mutations: without
  the boundary in `fcb_paths.sh` 3 sibling and flag tests go red (2 more with the backslash boundary
  removed, `fcb_py` tests included); without the `$RUN_DIR` expansion, the `$RUN_DIR_C`-first rule, the
  closing-quote rule or `patsub_replacement` off, 1 test each goes red. MET.
- **AC8 (deferred entries).** Pointer text for the leader: R1-26, R2-14 and R1-24 resolved by
  `spec-10-10-uat-testcases-in-container.md` and `tests/uat/run/2026-11-18-10-10-proof/`. Leader edits
  the ledger.
- **AC9 (gates).** See Build Notes.

## Approval conditions (leader, 2026-11-18; supersede the same-numbered text above)

- **Q1.** Option A. `fcb_cua.sh` and `fcb_py.sh` share one path-mapping file (`scripts/automation/fcb_paths.sh`); no copy. The wrapper test covers `<root>-other`, `<root>2`, a backslash root, and a root inside a `--flag=` value and inside JSON; each case goes red on a mapping without the boundary.
- **Q2.** Test Exit, New and the `Windows` entries once each; record "leaf found" or "shortcut used" in the proof folder; each test case names the route it uses.
- **Q3.** Measure once. If a hand-started proxy does not serve `/healthz` (relay and in-container), Cleanup and When text use `fcb-freecad stop` then `start`.
- **Q4.** Delete only the Windows sentence when a POSIX branch exists in the same check. A scenario with no check left that the container can run is marked `NOT APPLICABLE (container: <reason>)` in its header line and listed in the build notes; no invented check.
- **D2 extra.** The changed verify clauses check the same thing. `then-verify-diff.txt` tags each changed line `rule:K<n>` or `hand`; each `hand` line has a one-line reason.
- **AC5.** `git diff --stat 031d8e8 -- tests/uat/scenarios tests/uat/runner` is empty and `uv run pytest tests/external -q -k uat_runner` is green. No validate-step run.
- **AC9.** Gates: `uv run ruff check .`, `uv run python scripts/check_imports.py`, `uv run ruff format --check` on changed `.py` files, `uv run pytest tests/external -q`.
- **Proof folder.** Also holds `census-before.txt` and `census-after.txt`.

## Out of scope

`src/`; the runner and watchdog code; `tests/uat/scenarios/`; `tests/uat/probe/README.md` (deferred D-2); `run_faults.py` preflight (D-1); the canary fix (Story 10-8, decision 19); any Then observable except the listed one; running Gate 1.

## Open questions

- **Q1 — New helper `scripts/automation/fcb_cua.sh`?** Options: (A) a 10-line wrapper plus one test, `$FCB_CUA`, as `fcb_py.sh` did for `$FCB_PYTHON`; one short line per call, 635 mechanical edits; (B) the full `docker exec ... bash -c 'eval "$(fcb-session-env)"; /usr/local/bin/cua-driver call ...'` in every line (635 lines of 120+ characters, easy to mistype); (C) write the calls as MCP tool names `mcp__cua-driver-docker__<tool>` (no new code, but a test case then cannot be pasted into a shell, and `screenshot_out_file` captures lose the stdout evidence form). **Recommend A.** It adds the only code of this Story, in `scripts/`, not `src/`; if you refuse new code, take C.
- **Q2 — Menu leaf route versus shortcut keys.** The leaf-by-token route works only when the element tree shows the leaf without opening the menu (the runner relies on it for `Show All Objects`, `Fit All` and the allow-list). I did not test `Exit`, `New` and the `Windows` entries. The build tests each once; a leaf that is absent falls back to the shortcut key and the test case says so. I recommend recording the result in the proof folder, not deciding now.
- **Q3 — Proxy restart by hand in the container.** The proxy pins the FreeCAD it serves and exits about 2 s after that FreeCAD is gone (CLAUDE.md section 16). A proxy started by hand with `docker exec -d` may not pin the same way. If the manual restart does not serve `/healthz`, the Cleanup text changes to "restart FreeCAD with `fcb-freecad stop` then `fcb-freecad start`" (the addon spawns its own proxy). The change touches Cleanup and When text only, no Then. The build decides from the measured result.
- **Q4 — Cases that test Windows-only behaviour** (TC-10-14 "On Windows the listener closes while unread client data is queued", TC-11-07 `attrib`/`icacls`, TC-12 `modifier` not honoured on a background click on Windows). In the container the Windows branch is not testable. I propose to delete the Windows sentence in the check text and keep the POSIX branch (D1: no duplicate). That removes coverage of a Windows host that UAT no longer runs on (decision 17). Confirm.

## Estimate

About 950 changed lines in `tests/uat/testcases/` (901 matching lines plus fenced lines that follow them), about 40 in `test-plan.md` and `APPENDIX-B`, one new script (about 25 lines), one new test (about 60 lines), and the proof folder. Build order: wrapper and test; mechanical K1 and K2 edits; hand edits per file in the order TC-01, TC-10, TC-11, TC-12, TC-06, then the rest; proof runs per kind; AC3 and AC4 scripts; documents.

## Build Notes (2026-11-18)

- **Code.** `scripts/automation/fcb_paths.sh` (path mapping shared by `fcb_py.sh` and the new
  `fcb_cua.sh`), `fcb_cua.sh` (tool call or management word in the container; expands literal
  `$RUN_DIR` and `$PROJECT_ROOT`; reads no stdin for `status`), `tests/external/test_fcb_cua_wrapper.py`.
  `fcb_py.sh` now sources `fcb_paths.sh`; its existing tests stay green.
- **Q2 measured.** `Exit`, `New Document`, `Show All Objects`, `Close`, `Save`, `Zoom In`, `Next`,
  `Previous` and `Part > Primitives > Cube` (after the Part workbench leaf) are leaves in the
  snapshot and pressing them works (`effect: unverifiable`; the window title or tree shows the
  result). `Undo`, `Recompute`, `Toggle Visibility` are not listed: keys `ctrl+z`, `ctrl+r`,
  `space` are written in the cases, not measured for effect. The numbered `Windows` entries expose only
  `Activates this window`: `Next` and `Previous` switch the document (title read back).
- **Q3 measured.** A proxy started by hand with `docker exec -d -u cua <command line>` pins to the
  running FreeCAD and serves `/healthz` in the container and on the host relay (`K-proxy-restart.txt`).
- **Q4.** NOT APPLICABLE scenarios: 0. TC-10-14 and TC-11-07 keep their POSIX check; the TC-12
  `modifier` note keeps its rule for the container.
- **Hand edits.** 63 `hand` verify clauses of 370 (`then-verify-diff.txt`); 307 are `rule:K<n>`. `then-check.py` joins continuation lines and fails on a changed clause with no reason.
- **Stays as written (not host commands).** Statements that a case reads a file "in-process with
  `script_exec`" because the agent shell gets "Access is denied" (a Windows remark; the in-process
  route still works); the word UIA for the accessibility tree; TC-16's source path of the user project
  drawer (a host `cp`); `curl -o /dev/null` on Git Bash exits 23 but prints the code.
- **Not measured.** The keys for `Undo`, `Recompute` and `Toggle Visibility`; whole scenarios (the
  build checks each rewritten command kind, not each scenario).
- **Review lenses (3, blind, edge case, verification gap).** Fixed: unquoted globs in `docker exec`
  lines, bare `addon.log` greps, `tools/list` against the container-internal `:8765`, `$RUN_DIR_C`
  matched by the `$RUN_DIR` rule, a dropped closing quote, `&` in a root under bash 5.2, untested
  `doctor`/`list-tools`/`describe`, `QOpenGLWidget` precondition (the container tree has none), the
  symlink check of TC-01, `kill -KILL` where a plain `kill` fits, `curl --version` on the host, the
  missing stop before the TC-16 repeat run, a `FREECAD_BUDDY_SRC` host example, continuation lines in
  `then-check.py`, guards in `proof.sh`. Accepted without change: the installed-addon check hashes
  `__init__.py` only; `ps -o lstart=` versus the file time in TC-15 is true by construction in a fresh
  image; the numbered-`Windows` replacement has no iteration limit; the census and `then-check.py`
  pattern tables differ on purpose (counting versus tagging); the relay's own loopback binding and the
  compose port mapping are not tested (not a host command, outside this Story); a JSON string with an
  escaped quote next to a path is not handled (no payload has one).
