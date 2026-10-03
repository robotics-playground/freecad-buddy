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
| Smoke script | `tests/uat/run/2026-10-03-01/evidence/e2e.py` | 13-check mutation, measure, export, screenshot run over `:8765` |
| One tool call | `_automation/uat/fcb.py <tool> '<json>'` or `--batch file.json` | ad hoc MCP call over HTTP |
| Close all docs | `_automation/uat/close_all.py` | close every open document in one session |
| Logs | `%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log`, `mcp-proxy.log` | bridge start, proxy spawn, errors |

`_automation/` is gitignored: the `_automation/uat/` files exist only in a working checkout, not
in a fresh clone. The two `tests/uat/run/2026-10-03-01/evidence/` scripts are committed.

Call tools through `fcb.py` or the smoke script. The session `mcp__freecad-buddy__*` tools connect
only at session start, and a reconnect needs `/mcp`, which is a human step.

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

**Done when:** 0 FreeCAD processes, no `:8765` listener, daemon running, and the install mode is
known (see [Install modes](#install-modes)). Record `git status` to compare at the end.

### 2. Launch

Pass JSON to `cua-driver` on stdin. The positional form fails to parse Windows backslashes.

```bash
cat _automation/uat/launch.json | cua-driver launch_app
```

Wait until `:8765` is listening, then read the new `addon.log` lines. The launch helper does both.

**Done when:** `addon.log` shows `freecad-buddy RPC listener started` and
`spawned MCP proxy (pid N)`, `:8765` is `LISTENING`, and pid and `window_id` are recorded. Take
`window_id` from `cua-driver list_windows` after the bridge is up: the id that `launch_app`
returns can belong to the splash screen.

### 3. Drive the GUI

Use UIA element tokens from a fresh snapshot:

```bash
echo '{"pid":P,"window_id":W,"include_screenshot":false}' | cua-driver get_window_state > state.json
# find the element, then:
echo '{"pid":P,"element_token":"s00000003:78"}' | cua-driver click
```

Confirmed on FreeCAD 1.1.1:

| Action | Result |
|--------|--------|
| UIA click on toolbar `Button "New Document"` | works |
| `invoke_menu ["File","Exit"]` | works; clean shutdown |
| `invoke_menu ["File","New"]` | refused at segment 1 (label differs on this build) |
| `hotkey ["ctrl","n"]`, background delivery | dropped |

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

- Every `sketch_*`/`feature_*` mutation needs `preview_dry_run` first. Pass the returned
  `preview_id` back as `"confirm": {"preview_id": ..., "elicitation_action": "accept"}`.
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

**Done when:** 0 FreeCAD processes, no `:8765` `LISTENING` line (`TIME_WAIT` client lines are
normal), and `git status` matches preflight. A proxy you started by hand outlives FreeCAD; stop it
with `Stop-Process -Id <pid>`.

## Install modes

| Mode | Layout | When | Proxy discovery |
|------|--------|------|-----------------|
| Junction (dev) | `Mod\FreeCADBuddy\freecad_buddy` → `<repo>\src\freecad_buddy` | every source edit | walk from `bootstrap.py` to the repo `.venv` |
| Built copy | real copy of `dist/addon` | testing the packaged addon | `repo-root.txt` marker written by `scripts/build_addon.py` |

Switch to a built copy:

```powershell
uv run python scripts/build_addon.py
Move-Item "$env:APPDATA\FreeCAD\v1-1\Mod\FreeCADBuddy" "$env:APPDATA\FreeCAD\v1-1\FreeCADBuddy.harness-backup"
Copy-Item dist\addon "$env:APPDATA\FreeCAD\v1-1\Mod\FreeCADBuddy" -Recurse
```

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

`freecadcmd.exe <script>.py` prints nothing and writes no output file from a script. Use the
`fcb` env interpreter for scripted in-FreeCAD checks.

The in-FreeCAD suite writes `FCB_TMP_shot_*.png` to `./freecad-buddy-workdir/`. Delete that
folder after the run.

## Pitfalls

- **pid reuse.** A listener pid can repeat an earlier run's pid. Confirm with the parent chain:
  `Get-CimInstance Win32_Process -Filter "ProcessId=N"` → `ParentProcessId` leads to `freecad.exe`.
- **Long paths.** `git worktree add` under the scratchpad fails with `Filename too long`. Use a
  short path such as `D:/fcbwt`, and remove the worktree after use.
- **`_automation/` is gitignored.** A fix to a script there is not committed unless force-added.
