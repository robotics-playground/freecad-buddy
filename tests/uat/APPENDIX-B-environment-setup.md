# Appendix B — Environment Setup Runbook

Work through every step in order before any test case runs. Each step has a verify command. A step
that does not verify is a blocker: fix it, do not proceed.

Commands are written for PowerShell 7 on Windows unless marked otherwise.

---

## Step 1 — cua-driver daemon

The daemon drives the FreeCAD GUI. It must run in an **interactive** Windows session. A daemon in
Session 0 cannot see or drive a desktop window.

- [ ] Daemon is up (verify: `cua-driver status`)
- [ ] Daemon session is interactive (verify: `Get-Process cua-driver | Select-Object Id, SessionId`
      — `SessionId` must be **≥ 1**, never `0`)
- [ ] Control socket answers (verify: `cua-driver call list_apps '{}'` returns an `apps` array)

      Do **not** use `Test-Path \\.\pipe\cua-driver`. PowerShell's provider cannot stat a named
      pipe and returns `False` even when the daemon is healthy. A real call is the only sound
      liveness check.

If `SessionId` is `0`, stop. Restart the daemon from an interactive desktop session. Every GUI step
in TC-06 and TC-12 will silently produce empty windows otherwise.

---

## Step 2 — Addon install

The addon is expected to be a **symlink** from the FreeCAD Mod directory to the repo source, so
edits in the repo take effect after a FreeCAD restart with no rebuild.

- [ ] Symlink exists and points at the repo (verify:
      `Get-Item "$env:APPDATA\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy" | Select-Object LinkType, Target`
      — `Target` must be `$PROJECT_ROOT\src\freecad_buddy`, this checkout's source directory)
- [ ] Addon metadata present (verify:
      `Test-Path "$env:APPDATA\FreeCAD\v1-1\Mod\FreeCADBuddy\package.xml"`)

Rebuild **only** if the link is absent:
```bash
uv run python scripts/build_addon.py
```

A release install is a different layout: `FreeCADBuddy-<ver>.zip` (from
`uv run python scripts/build_addon.py --release`) extracted into `Mod\`. It has no repo link and
no `repo-root.txt`; it carries the wheel in `wheels\` and runs the proxy from the managed venv
`%APPDATA%\FreeCAD\v1-1\FreeCADBuddy\venv`, which `uv` provisions on the first start. Test it
only in a scenario that asks for it, then restore the link.

**Warning:** `%APPDATA%\FreeCAD\Mod\` is the legacy directory and is empty on this machine. The
real one is `%APPDATA%\FreeCAD\v1-1\Mod\`. Checking the legacy path gives a false negative.

---

## Step 3 — H1 legs

The headless host needs FreeCAD and `mcp` importable from the **same** interpreter.

- [ ] `fcb` env is H1-capable (verify, **bash** — the PYTHONPATH patch is required):
      ```bash
      FCB="$USERPROFILE/micromamba/envs/fcb"
      PYTHONPATH="$FCB/Library/bin;$FCB/Library/lib" PATH="$FCB/Library/bin:$PATH" \
        "$FCB/python.exe" -c "import FreeCAD, mcp; print('H1 ok', '.'.join(FreeCAD.Version()[:3]))"
      ```
      Expect `H1 ok 1.1.0`.

      **A bare `"$FCB/python.exe" -c "import FreeCAD"` always fails with `ModuleNotFoundError`.**
      `FreeCAD.pyd` lives in `Library/bin`, not on the default `sys.path`. This is not a broken
      env — `scripts/automation/run_mcp_e2e.py` applies the same patch in `_fcb_env` before it
      spawns the H1 server. Do not "fix" the env in response to the bare-import failure.

      Note the H1 leg is FreeCAD **1.1.0**, while the GUI is **1.1.1**. Record which host produced
      a result whenever a version-sensitive value (fingerprint, element map) is compared.
- [ ] Repo `uv` env is present (verify: `uv run python -c "import sys; print(sys.version)"` reports
      Python 3.12.12)

---

## Step 4 — Launch FreeCAD

Launch through `cua-driver`, never with `Start-Process`. Take the `window_id` from the `windows`
array in the launch result — do not guess it.

```bash
'{"path":"C:\\Program Files\\FreeCAD 1.1\\bin\\freecad.exe"}' | & cua-driver call launch_app
```

- [ ] Process is up and interactive (verify:
      `Get-Process freecad | Select-Object Id, SessionId` — `SessionId` ≥ 1)
- [ ] A window id was returned (verify: the launch result `windows` array is non-empty; record
      `pid` and `window_id`)
- [ ] The window is drivable (verify:
      `'{"pid":<pid>,"window_id":<window_id>}' | & cua-driver call get_window_state` returns an
      element tree with a `MenuBar` and a `QOpenGLWidget` viewport)

Record `pid` and `window_id` into the run evidence. Every later cua call needs both.

---

## Step 5 — Confirm proxy auto-spawn

The addon starts the in-FreeCAD RPC listener **and** auto-spawns the external MCP HTTP proxy. Both
must appear without any manual command.

- [ ] `:8765` is LISTENING (verify: `netstat -ano | findstr :8765` shows a `LISTENING` line;
      record the owning pid)
- [ ] **No manual `serve` command was run.** Running
      `freecad-buddy serve --mode rpc` by hand invalidates TC-01-01, because that case proves the
      addon spawns the proxy itself.
- [ ] Addon log shows the bridge start (verify:
      `Get-Content "$env:APPDATA\FreeCAD\v1-1\freecad-buddy\addon.log" -Tail 40`)
- [ ] Proxy log shows the HTTP host bound (verify:
      `Get-Content "$env:APPDATA\FreeCAD\v1-1\freecad-buddy\mcp-proxy.log" -Tail 40`)

The host and port are hard-coded: `_HOST="127.0.0.1"`, `_PORT=8765` in `gui_external/entry.py`.
There are no `--host` or `--port` flags.

If `:8765` was already served before FreeCAD started, the addon does not double-spawn. In that case
the listener you are testing is not the one the addon owns — kill it and relaunch FreeCAD.

---

## Step 6 — Confirm the tool surface

- [ ] `tools/list` returns **exactly 45** names (verify: call `tools/list` through the connected
      MCP client and count)
- [ ] `export_self_read_stl` and `export_self_read_3mf` are **ABSENT**. They are internal RPC-only
      and are filtered out of `tools/list`.
- [ ] `debug_exec` is **ABSENT** from the default surface. It appears only when
      the **Allow debug_exec** preference is on or `FREECAD_BUDDY_ALLOW_EXEC=1` is set (the
      variable wins over the preference). With both off, calling it returns
      `debug_exec is disabled (set FREECAD_BUDDY_ALLOW_EXEC=1 to enable)`.

Expected counts by family: `document_` 7, `query_` 8, `verify_` 6, `export_` 3, `sketch_` 8,
`feature_` 11, `preview_dry_run` 1, `view_fit_viewport` 1. Total 45.

**A short count is stop-the-line.** Do not begin testing against a partial surface — the failures
it produces are setup artifacts, not findings.

---

## Step 6a — Confirm the audit log is writable — MUTATIONS FAIL WITHOUT IT

Every mutation appends to the audit log. If the append fails, **every mutation tool fails** with

```
SPEC_FAILED  mutation.spec_failed
OSError: Failed to write all data to file Permission denied
```

and the addon log records the real cause (`ERROR freecad_buddy.rpc_listener: audit write
failed`, `PermissionError`). The envelope message names the *write*, not the audit log, so this
reads as a snapshot or `saveAs` problem. It is neither.

The GUI host takes the audit path in this order, once, at bridge start:

| Source | Path |
| --- | --- |
| `FREECAD_BUDDY_AUDIT_LOG` set in the environment FreeCAD inherits | that path |
| **Audit log file** on Edit > Preferences > FreeCAD Buddy | that path |
| default | `%APPDATA%\FreeCAD\v1-1\freecad-buddy\audit.jsonl` |

The default does not depend on the working directory, so a Start-menu launch and a `cua-driver`
launch write to the same file. The `operator settings:` line in `addon.log` names the effective
path and its source. Only the headless host still falls back to the cwd-relative
`freecad-buddy-audit.jsonl`.

- [ ] The effective path is writable (verify: the `operator settings:` line in the new `addon.log`
      lines gives `FREECAD_BUDDY_AUDIT_LOG=` with a path in a writable folder)
- [ ] A mutation actually commits (verify: `preview_dry_run` then `feature_body_create` on a
      scratch document returns `status: "OK"` with `post_verify.passed: true`). **This is the real
      check.** Run it before any mutation scenario; do not infer it from the environment.

A variable must be set **in the environment the FreeCAD process inherits**, before that process
starts. A `User`-scope variable set after the `cua-driver` daemon started does **not** reach a
FreeCAD the daemon launches — the daemon passes on its own environment. Restart the daemon, or
relaunch FreeCAD from a shell that already carries the variable. A preference change needs a
FreeCAD restart.

Every scenario in TC-03, TC-04, TC-05, TC-08 and TC-13 group B depends on this step. TC-99-06
records the remaining AD-25 gap: the log is one file, not a dated file per session.

---

## Step 7 — Record the build banner

A fingerprint or a TNP result is only interpretable against the build that produced it. Call
`query_capabilities` (empty-object schema, no properties) and record all of these into the run
evidence:

- [ ] FreeCAD version (expect `1.1.1`)
- [ ] `element_map` — the topological naming scheme in use
- [ ] serializer tag
- [ ] render ladder — which render backend was selected; `none` means every visual checkpoint skips
- [ ] `exec_enabled` — must be `false` for the green gate unless a case explicitly sets the flag
- [ ] package version
- [ ] contract version (the RPC listener supports exactly `["1"]`)

Store this banner at the top of the run report. If FreeCAD is restarted mid-run, capture it again.

---

## cua-driver usage rules

These apply to every GUI step in TC-06 and TC-12.

### CLI stdin form

Windows quoting breaks inline JSON arguments. Pipe the payload on stdin instead:
```bash
'{"pid":29764,"window_id":393368}' | & cua-driver call get_window_state
```

### `element_token`, never `element_index`

Use `element_token` (for example `s00000004:71`). Indices are per-snapshot and keyed on
`(pid, window_id)`; a stale index silently clicks the wrong control. Refresh the snapshot with
`get_window_state` before acting, and act on the token from that snapshot.

### `verify_state` — unknown is not success

`verify_state({pid, window_id, expect})` returns one of pass, fail, or `unknown`. Treat `unknown`
as **not verified**. Either find a bounded postcondition that resolves, or add
`include_screenshot: true` and judge the visual evidence directly.

### `invoke_menu` for menu paths

```bash
'{"pid":29764,"window_id":393368,"path":["File","New"]}' | & cua-driver call invoke_menu
```
It re-resolves the live UIA tree at each hop and refuses a path that is missing, ambiguous, or
disabled. Prefer it over clicking menu coordinates.

Menu bar layout on this build: MenuBar at index 70; menus at depth 2 are File(71), Edit(72),
View(73), Tools(74), Macro(75), Sketch(76), "Part Design"(77), Windows(78), Help(79).

**Submenu labels must be discovered, never guessed** (learned 2026-09-12). `invoke_menu` refuses
a wrong label with `menu_path_unavailable` naming the failing segment index, which is the correct
behaviour but makes guessing expensive. Confirmed on this build:

- `["View","Zoom"]` resolves. `["View","Fit all"]`, `["View","Fit All"]` and
  `["View","Standard views"]` are all **refused at segment 1** — those labels do not exist as
  direct children of `View` here.
- Qt renders an open menu as a **popup that is not a separate top-level window**: `list_windows`
  still reports only the main window, and the popup's items do not appear in the main window's
  UIA tree. So you cannot enumerate submenu children from a snapshot while the menu is open.

Practical rule: drive state through MCP where an MCP tool exists, and reserve `invoke_menu` for
paths whose exact labels you have already confirmed. Record any label you confirm in the scenario
that uses it.

### FreeCAD viewport keystrokes are frequently dropped

`press_key` to the 3D viewport — including the px form that clicks to focus first, and including
`delivery_mode:"foreground"` — returned `effect:"unverifiable"` and, on verification, **had not
landed**: the camera was unchanged in a fresh screenshot. A tree-targeted `press_key` with `space`
(visibility toggle) reported `effect:"unverifiable"` with
`escalation:{reason:"delivery_failed", target:"foreground"}` yet **did** land, confirmed by
`query_tree_summary` flipping to `"visibility": true`.

Both directions of that asymmetry are why the skill's rule is absolute: **`unverifiable` is not a
verdict.** Always verify the postcondition — via MCP state or a fresh screenshot — before
recording a checkpoint either way. Never record a pass from a delivered action, and never record a
failure from an `unverifiable` result.

### `screenshot_out_file` for context protection

Always write screenshots to a file rather than returning bytes:
```bash
'{"pid":29764,"window_id":393368,"screenshot_out_file":"_automation/uat/tc06-iso.png"}' | & cua-driver call get_window_state
```
Then `Read` the file only when a visual comparison actually needs it.

### Forbidden commands on Windows

Do not use: `Start-Process`, `SetForegroundWindow`, `taskkill /F`. They break the daemon's window
tracking and leave FreeCAD in a state the driver cannot recover.

Two further limits: `modifier` is not honoured on a background click, and right-click or
`count > 1` skip the UIA Invoke path.

### `replay_trajectory` is regression evidence only

It cannot re-resolve element tokens across sessions. A recorded trajectory documents what happened;
it is not a re-runnable test step. Never write a checkpoint that depends on replaying one.
