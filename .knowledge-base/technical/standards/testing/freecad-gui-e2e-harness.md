# FreeCAD GUI — Agent-Driven End-to-End Harness

How an agent proves a code change works in the real FreeCAD GUI, from source edit to a visible
part, with no human step. The **harness** has four parts: `cua-driver` launches, drives, and
captures the window; the addon starts the bridge itself; MCP calls over HTTP change and measure
the model; the agent reads every screenshot itself.

The headless H1 sweep, the `fcb` env, verification bars, and the render-against-viewport rules are
in [FreeCAD automation & verification](freecad-automation-verification.md). This guide covers only
the GUI path.

Reference run with every artifact: `tests/uat/run/2026-10-03-01/` (report, evidence, scripts).

## Tools

| Tool | Path | Role |
|------|------|------|
| `cua-driver` CLI | on `PATH` | launch, UIA click, menu, window screenshot |
| `launch.json` | `_automation/uat/launch.json` | `{"path": "C:\\Program Files\\FreeCAD 1.1\\bin\\freecad.exe"}` |
| Launch helper | `tests/uat/run/2026-10-03-01/evidence/launch.sh` | launch, wait for `:8765`, print pid, window id, new `addon.log` lines |
| Launch with environment | `_automation/uat/launch_env.sh <tag> "<set statements>"` | same as the launch helper, but `cua-driver` starts `cmd.exe`, which sets the variables and starts FreeCAD |
| Smoke script | `tests/uat/run/2026-10-03-01/evidence/e2e.py` | 13-check mutation, measure, export, screenshot run over `:8765` |
| One tool call | `_automation/uat/fcb.py <tool> '<json>'` or `--batch file.json` | ad hoc MCP call over HTTP |
| Close all docs | `_automation/uat/close_all.py` | close every open document in one session |
| Logs | `%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log`, `mcp-proxy.log`, `provision.log` | bridge start, operator settings, venv provisioning, proxy spawn, errors |

`_automation/` is gitignored: the `_automation/uat/` files exist only in a working checkout, not
in a fresh clone. The two `tests/uat/run/2026-10-03-01/evidence/` scripts are committed.

Call tools through `fcb.py` or the smoke script. The session `mcp__freecad-buddy__*` tools connect
only at session start, and a reconnect needs `/mcp`, which is a human step.

The session tools show only `structuredContent` when a result has it; `fcb.py` prints the
content blocks. To judge what the agent reads, call the tool through the session tools.

## Steps

### 1. Preflight

```bash
powershell -NoProfile -c "Get-Process freecad* -EA SilentlyContinue | Measure-Object | % Count"   # 0
netstat -ano | grep "127.0.0.1:8765 .*LISTENING" || echo free                                    # free
cua-driver status                                                                                 # daemon is running
```

```powershell
Get-Item "$env:APPDATA\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy" | Select-Object LinkType, Target
```

Start the `cua-driver` daemon from the agent shell, not from an elevated shell or a scheduled
task. FreeCAD inherits the daemon's integrity level. When FreeCAD runs at a higher level than the
agent shell, the shell cannot read its command line, stop it, or open its process handle, and
`Stop-Process` and `kill_app` are refused. Check both sides:

```powershell
whoami /groups | Select-String "Mandatory Label"                     # Medium Mandatory Level
[System.Diagnostics.Process]::GetProcessById(P).get_Handle()         # after launch: returns a number, no "Access is denied"
```

Call `get_Handle()`, not the `.Handle` property: PowerShell turns an exception in a property
getter into `$null`, so the property form prints nothing instead of "Access is denied".

When `get_Handle()` fails, FreeCAD runs above the shell's level. Recover:

1. Exit FreeCAD: `invoke_menu ["File","Exit"]`.
2. Stop the daemon: `cua-driver stop`.
3. Start it from the agent shell as a background process: `cua-driver serve`. Do not use the
   `cua-driver autostart` scheduled task; it can start the daemon at a higher level.
4. Confirm it runs: `cua-driver status` reports the daemon and its pid.
5. Relaunch FreeCAD (see [Launch](#2-launch)), then run `get_Handle()` again. It must return a
   number.

**Done when:** 0 FreeCAD processes, no `:8765` listener, daemon running from the agent shell, the
shell is at Medium integrity, and the install mode is known (see [Install modes](#install-modes)).
Record `git status` to compare at the end.

### 2. Launch

Choose the mutation approval posture first. Two controls set it. The bridge reads both once, at
start, so a change has no effect until FreeCAD restarts:

- the **Auto-approve mutations** box on Edit > Preferences > **FreeCAD Buddy** (default on);
- the `FREECAD_BUDDY_AUTO_APPROVE` variable. FreeCAD gets it only from the process that starts
  it. When it is set, it wins over the preference.

| Effective value | Posture |
|-----------------|---------|
| `1` (preference on, variable unset — the default) | A mutation without `confirm` applies in one call; its audit `approval` line has `mode: "auto_approve"` and `source: "FREECAD_BUDDY_AUTO_APPROVE"` |
| `0` (preference off, or variable `0`) | A mutation without a valid `preview_id` is refused (`INVALID_INPUT`), except a `feature_set_parameters` that writes only `Visibility` |

`preview_dry_run` stays available in both postures. A call that sends `confirm` is checked
against its token in both postures: a stale, expired or forged `preview_id` is refused.

- Persistent (Windows, current user): `setx FREECAD_BUDDY_AUTO_APPROVE 0`. It reaches only
  processes started after it. Remove it with
  `[Environment]::SetEnvironmentVariable("FREECAD_BUDDY_AUTO_APPROVE", $null, "User")`.
  To turn the confirm gate on, use `0`. An empty value usually reaches a new process as unset,
  so auto-approve stays on.
- Per shell: `$env:FREECAD_BUDDY_AUTO_APPROVE = "0"` (PowerShell) or
  `set FREECAD_BUDDY_AUTO_APPROVE=0` (`cmd.exe`), then start FreeCAD from that shell.
- `cua-driver launch_app` takes no environment: FreeCAD gets the environment of the
  `cua-driver` daemon, not of your shell. To set a variable for one launch, let `cua-driver`
  start `cmd.exe`, which sets it and starts FreeCAD. The helper
  `_automation/uat/launch_env.sh <tag> "<set statements>"` does this. Write the statements as
  `set VAR=value&& set VAR2=value2`, with no space before `&&`: `cmd` keeps that space as part
  of the value.
- The audit log goes to the **Audit log file** preference, else to
  `%APPDATA%\FreeCAD\v1-1\freecad-buddy\audit.jsonl`. `FREECAD_BUDDY_AUDIT_LOG`, set the same
  way as above, wins over both.

**Check:** the new `addon.log` lines include one `operator settings:` line. It gives each
`FREECAD_BUDDY_*` value and its source (`env`, `preference`, `default` or `unset`). With auto-approve on,
they also include
`SECURITY: mutation auto-approve ENABLED (to require preview_id, clear Auto-approve mutations in the FreeCAD GUI: Edit > Preferences > FreeCAD Buddy, or set FREECAD_BUDDY_AUTO_APPROVE=0)`.
With the effective value `0` the line is absent. In the audit log, an `approval` line with `mode: "auto_approve"`
proves the posture is on; `preview_token` and `display_state` lines occur in both postures.

Pass JSON to `cua-driver` on stdin. The positional form fails to parse Windows backslashes.

```bash
cat _automation/uat/launch.json | cua-driver launch_app
```

Wait until `:8765` is listening, then read the new `addon.log` lines. The launch helper does both.

**Done when:** `addon.log` shows `freecad-buddy RPC listener started` and
`spawned MCP proxy (pid N)`, `:8765` is `LISTENING`, pid and `window_id` are recorded, and
`[System.Diagnostics.Process]::GetProcessById(P).get_Handle()` succeeds from the agent shell (FreeCAD
runs at the shell's integrity level). Take
`window_id` from `cua-driver list_windows` after the bridge is up: the id that `launch_app`
returns can belong to the splash screen.

### 3. Drive the GUI

Use UIA element tokens from a fresh snapshot:

```bash
echo '{"pid":P,"window_id":W,"include_screenshot":false}' | cua-driver get_window_state > state.json
# find the element, then:
echo '{"pid":P,"element_token":"s00000003:78"}' | cua-driver click
```

Confirmed on FreeCAD 1.1.4, background delivery:

| Action | Result |
|--------|--------|
| UIA click on a toolbar button by `element_token` (`New Document`, `Fit All`) | works; returns `route: "accessibility"` |
| `invoke_menu ["View","Fit All"]` | refused with `menu_path_unavailable`: Fit All is under `View > Standard Views`; use the toolbar button |
| `invoke_menu ["View","Visibility","Show All Objects"]` | works; shows every object of the active document and marks it modified (`*`) |
| `right_click` / `double_click` by `element_token` | delivered through `global_input`, not background delivery: they move the real pointer |
| `press_key` / `hotkey` to the 3D view | dropped |
| `invoke_menu ["Edit","Recompute"]` | works while the active document must recompute |
| `invoke_menu ["Windows","<n> <label> : 1"]` | works; makes that document active. `1 Start` is the first entry |
| UIA or pixel click on a document root row in the tree | does not select the row or change the active document; use the `Windows` menu entry |
| `invoke_menu ["File","Close"]` | works; closes the active document. On a modified document (`*` in the title) it opens a modal save prompt: close that document with `document_close` instead |
| Pixel `click` with `count: 2` on a Start page Recent Files entry | works (`route: "synthetic_events"`); opens the file with no dialog |
| `invoke_menu ["File","Exit"]` | works; clean shutdown |

Never open a modal dialog through `invoke_menu` (Open, Save As, Preferences, Help > About). The
call blocks until the dialog closes, and the UIA provider stays busy: later background clicks
return `background_unavailable` (`uia_status: busy`); only `zoom` still captures pixels. Use a
non-modal route instead:

- Open a file: double-click its Start page Recent Files entry (confirmed on 1.1.4). Starting
  FreeCAD with the path as an argument (`launch_app` `additional_arguments`) is not yet confirmed
  on 1.1.4.
- Read the version: the main window title from `list_windows`, compared with
  `query_capabilities.freecad_version`.
- Change a preference: `script_exec` with `FreeCAD.ParamGet(...)`, then restore the value.

`invoke_menu` fires the command as soon as it resolves the path. Send only a path whose effect you
want.

**Done when:** each action is confirmed in a second domain: window title from `list_windows`, MCP
`document_list`, or pixels.

### 4. Change and measure the model over MCP

Run the smoke script, or build calls the same way it does:

```bash
uv run python tests/uat/run/2026-10-03-01/evidence/e2e.py <tag> <absolute out dir>
```

Rules the script follows:

- Every `sketch_*`/`feature_*` mutation runs `preview_dry_run` first and passes the returned
  `preview_id` back as `"confirm": {"preview_id": ..., "elicitation_action": "accept"}`. With
  auto-approve off (preference or `FREECAD_BUDDY_AUTO_APPROVE=0`) this is required. A call that sends `confirm` is checked
  against its token in every posture, so the token must be fresh even with auto-approve on.
- `sketch_add_geometry` must leave the sketch fully constrained, or the mutation is rolled back
  with `SPEC_FAILED` (`dof=N`). Send the constraints in the same call
  (`"constraints": [...]`).
- Use absolute paths for every export.

**Done when:** the script prints `13/13 passed`. The plate volume is `1000 mm³` within `1e-3`.

### 5. Visual check

```bash
printf '{"pid":%s,"window_id":%s,"screenshot_out_file":"%s"}' P W "<abs path>.png" | cua-driver get_window_state
```

`Read` the PNG yourself. Compare document name in the tree, part shape, proportions, and camera
with what the run built.

**Done when:** the real window shows the expected part, and no modal dialog is open.

To prove measured values without trusting MCP output, follow
[FreeCAD native validation](freecad-native-validation.md).

### 6. Prove the code under test is the code that ran

A passing smoke does not prove the edited source ran. Use a **canary**: a temporary marker log
line in the code path under test.

1. Add the line (for bootstrap, after the session-start sweep log in `start_bridge`).
2. Relaunch. The marker must be in the new `addon.log` lines.
3. Revert. Confirm `git diff` on that file is empty.
4. Relaunch. The marker must be absent.

For an error path, read the traceback file paths in the tool's error envelope: they show which
copy of `freecad_buddy` FreeCAD loaded.

**Done when:** the marker is present with the edit and absent after the revert.

### 7. Shut down

```bash
uv run python _automation/uat/close_all.py
echo '{"pid":P,"window_id":W,"path":["File","Exit"]}' | cua-driver invoke_menu
```

When a test case needs an unclean kill, stop FreeCAD from the agent shell with
`Stop-Process -Id P -Force`. It works only when FreeCAD runs at the shell's integrity level (see
[Preflight](#1-preflight)).

**Done when:** 0 FreeCAD processes, no `:8765` `LISTENING` line (`TIME_WAIT` client lines are
normal), and `git status` matches preflight. A proxy you started by hand exits about 2 s after the
FreeCAD it pinned is gone; if it is still listed, stop it with `Stop-Process -Id <pid>`.

## Install modes

| Mode | Layout | When | Proxy discovery |
|------|--------|------|-----------------|
| Junction (dev) | `Mod\FreeCADBuddy\freecad_buddy` → `<repo>\src\freecad_buddy` | every source edit | walk from `bootstrap.py` to the repo `.venv` |
| Built copy | real copy of `dist/addon` | testing the packaged addon | `repo-root.txt` marker written by `scripts/build_addon.py` |
| Release zip | `FreeCADBuddy-<ver>.zip` extracted into `Mod\` (no marker, wheel in `wheels\`) | testing a release install | managed venv `%APPDATA%\FreeCAD\v1-1\FreeCADBuddy\venv`; on first start `uv` provisions it on a background thread (`provision.log`), then the proxy spawns |

Switch to a built copy:

```powershell
uv run python scripts/build_addon.py
Move-Item "$env:APPDATA\FreeCAD\v1-1\Mod\FreeCADBuddy" "$env:APPDATA\FreeCAD\v1-1\FreeCADBuddy.harness-backup"
Copy-Item dist\addon "$env:APPDATA\FreeCAD\v1-1\Mod\FreeCADBuddy" -Recurse
```

Switch to a release install the same way: build it with
`uv run python scripts/build_addon.py --release`, then extract `dist\FreeCADBuddy-<ver>.zip` into
`Mod\` in place of the copy. `uv` must be on `PATH` or named in the **uv path** preference. The
first start provisions the venv; read `addon.log` for `MCP proxy venv ready` before you wait on
`:8765`.

Keep the backup **outside** `Mod\`. FreeCAD loads every folder under `Mod\` as an addon, and a
backup there wins the `freecad_buddy` import.

Restore the junction:

1. Confirm the copy holds no reparse point:
   `Get-ChildItem "$env:APPDATA\FreeCAD\v1-1\Mod\FreeCADBuddy" -Recurse -Force -Attributes ReparsePoint`
   returns nothing.
2. Delete the copy, then move the backup back.
3. Confirm `freecad_buddy` is a `Junction` to `src\freecad_buddy`.

Never run a recursive delete on a folder that holds the junction. Some tools follow it into `src`.

## Test commands

| World | Command |
|-------|---------|
| External (pytest) | `uv run pytest tests/external` |
| In-FreeCAD | `<fcb-env>\python.exe tests/run_tests.py`, with `PYTHONPATH` and `PATH` set as in [the `fcb` env](freecad-automation-verification.md#the-fcb-conda-env-h1-capable-interpreter) |

`freecadcmd.exe <script>.py` imports the script as a module: `__name__` is the file stem, so an
`if __name__ == "__main__":` block never runs. It also hides stdout. Module-level code does run
and can write files, and arguments after `--pass` reach `sys.argv`. Example:
`tests/uat/probe/read_fcstd.py` writes its result to a JSON file. Use the `fcb` env interpreter
for scripted in-FreeCAD checks that need stdout or a `__main__` block.

The in-FreeCAD suite writes `FCB_TMP_shot_*.png` to `./freecad-buddy-workdir/`. Delete that
folder after the run.

## Pitfalls

- **pid reuse.** A listener pid can repeat an earlier run's pid. Confirm with the parent chain:
  `Get-CimInstance Win32_Process -Filter "ProcessId=N"` → `ParentProcessId` leads to `freecad.exe`.
- **Long paths.** `git worktree add` under the scratchpad fails with `Filename too long`. Use a
  short path such as `D:/fcbwt`, and remove the worktree after use.
- **`_automation/` is gitignored.** A fix to a script there is not committed unless force-added.
