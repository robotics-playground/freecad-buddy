# Appendix B — Environment Setup Runbook

Work through every step in order before any test case runs. Each step has a verify command. A step
that does not verify is a blocker: fix it, do not proceed.

Commands are written for bash on the host. A command that runs inside the container starts with
`docker exec -u cua fcb-desktop`. `$FCB_CUA`, `$FCB_USER_DIR`, `$FCB_CONFIG_DIR` and `$RUN_DIR_C` come
from the environment block of `test-plan.md` §6.

**UAT runs FreeCAD in the `fcb-desktop` container, never on the host.** Do Steps C1–C4 below; Steps
1, 2, 4 and 5 hold the container form of the old host steps, in their original positions, so that references to them hold.
Step 3 (H1 legs) runs in the container too. Steps 6, 6a and 7 apply through MCP server
`freecad-buddy-docker`. Container reference: `tests/close-loop/README.md`.

---

## Step C1 — Container image with the code under test

- [ ] Release addon tree built (verify: `uv run python scripts/build_addon.py --release` prints
      `addon zip written to`, and `dist/addon/wheels/` holds one `.whl`)
- [ ] Container up (verify: `docker compose -f tests/close-loop/docker/compose.yaml up -d --build`,
      then `docker ps --filter name=fcb-desktop` lists it)
- [ ] Repo and run folder mounted (verify: `docker exec -u cua fcb-desktop ls /repo/benchmarks/g0/golden-models`
      lists the golden models)

## Step C2 — cua-driver in the container

- [ ] Every doctor line is `[ok  ]` (verify:
      `docker exec -u cua fcb-desktop bash -c 'eval "$(fcb-session-env)"; /usr/local/bin/cua-driver doctor'`)
- [ ] Daemon running (verify: `docker exec fcb-desktop supervisorctl status fcb-cua-serve` shows
      `RUNNING`)

## Step C3 — Launch FreeCAD

- [ ] No FreeCAD before the launch (verify: `docker exec -u cua fcb-desktop fcb-freecad status`
      shows an empty pid list)
- [ ] Launched by the helper (verify: `docker exec -u cua fcb-desktop fcb-freecad start`)

## Step C4 — Confirm proxy auto-spawn

- [ ] Proxy pinned to that FreeCAD (verify: `curl -fsS http://127.0.0.1:18765/healthz` shows a
      number in `freecad_pid` equal to the pid from `fcb-freecad status`)
- [ ] `addon.log` has `spawned MCP proxy` (verify:
      `docker exec -u cua fcb-desktop grep "spawned MCP proxy" /home/cua/.local/share/FreeCAD/v1-1/freecad-buddy/addon.log`)

---

## Step 1 — cua-driver daemon

Replaced by Step C2. The daemon drives the FreeCAD GUI inside the container desktop session.

- [ ] Daemon is up (verify: `"$FCB_CUA" status` shows `Cua Driver daemon is running`)
- [ ] Control socket answers (verify: `echo '{}' | "$FCB_CUA" list_windows` returns a `windows` array)

---

## Step 2 — Addon install

The container's FreeCAD runs the addon **copy** that the image installs from `dist/addon/`. After a
change under `src/`, run the build and compose commands of Step C1 again; the installed copy does
not follow the source tree.

- [ ] The addon is installed (verify:
      `docker exec -u cua fcb-desktop ls $FCB_USER_DIR/Mod/FreeCADBuddy/freecad_buddy/hosts/gui_addon/InitGui.py`)
- [ ] Addon metadata present (verify: `docker exec -u cua fcb-desktop ls $FCB_USER_DIR/Mod/FreeCADBuddy/package.xml`)
- [ ] The copy is the build under test (verify: `docker exec -u cua fcb-desktop sha256sum $FCB_USER_DIR/Mod/FreeCADBuddy/freecad_buddy/__init__.py`
      equals `sha256sum dist/addon/freecad_buddy/__init__.py` on the host)

The proxy runs from the managed venv `$FCB_USER_DIR/FreeCADBuddy/venv`, which `uv` provisions on the
first FreeCAD start in a new container (about 25 s).

---

## Step 3 — H1 legs

The headless host runs inside the `fcb-desktop` container, in the interpreter that holds FreeCAD
and `mcp` together: `fcb-py` (the AppImage's Python 3.11 with the pinned `mcp`, `trimesh` and
`lib3mf`, and the addon installed in the image; rebuild the image after a change under `src/`). No micromamba env and no host FreeCAD is involved.

- [ ] The container interpreter is H1-capable (verify, **bash**):
      ```bash
      docker exec -u cua fcb-desktop fcb-py -c "import FreeCAD, mcp; print('H1 ok', '.'.join(FreeCAD.Version()[:3]))"
      ```
      Expect `H1 ok 1.1.4`. Record that version as the H1 version. The H1 leg and the GUI run the
      same FreeCAD build.
- [ ] Both sweeps pass against the container (verify: `uv run python scripts/automation/run_mcp_e2e.py`
      and `uv run python scripts/automation/run_mcp_edge_cases.py` exit 0). Each prints
      `N/N checks passed` and writes its report under `_automation/`.
- [ ] Repo `uv` env is present (verify: `uv run python -c "import sys; print(sys.version)"` reports
      Python 3.12.12)

---

## Step 4 — Launch FreeCAD

Replaced by Step C3. Launch with the helper, never with a direct `AppRun` call. Take the
`window_id` from `list_windows` — do not guess it.

```bash
docker exec -u cua fcb-desktop fcb-freecad start
echo '{"pid":<pid>}' | "$FCB_CUA" list_windows
```

- [ ] Process is up (verify: `docker exec -u cua fcb-desktop pgrep -af '^/opt/freecad/usr/bin/freecad'` lists one process)
- [ ] A window id was returned (verify: `list_windows` returns the window whose `title` ends
      `FreeCAD <live version>`; record `pid` and `window_id`)
- [ ] The window is drivable (verify:
      `echo '{"pid":<pid>,"window_id":<window_id>}' | "$FCB_CUA" get_window_state` returns an
      element tree with the menu items `File`, `Edit` and `View`)

Record `pid` and `window_id` into the run evidence. Every later cua call needs both.

---

## Step 5 — Confirm proxy auto-spawn

Replaced by Step C4. The addon starts the in-FreeCAD RPC listener **and** auto-spawns the external
MCP HTTP proxy; both must appear without any manual command.

- [ ] `:8765` is listening in the container (verify: `docker exec -u cua fcb-desktop ss -ltnp | grep :8765` shows a `LISTEN` line;
      record the owning pid)
- [ ] **No manual `serve` command was run.** Running `freecad-buddy serve --mode rpc` by hand
      invalidates TC-01-01, because that case proves the addon spawns the proxy itself.
- [ ] Addon log shows the bridge start (verify:
      `docker exec -u cua fcb-desktop tail -n 40 "$FCB_USER_DIR/freecad-buddy/addon.log"`)
- [ ] Proxy log shows the HTTP host bound (verify:
      `docker exec -u cua fcb-desktop tail -n 40 "$FCB_USER_DIR/freecad-buddy/mcp-proxy.log"`)

The host and port are hard-coded: `_HOST="127.0.0.1"`, `_PORT=8765` in `gui_external/entry.py`.
There are no `--host` or `--port` flags. The host reaches the proxy through the relay on
`127.0.0.1:18765`.

If `:8765` was already served before FreeCAD started, the addon never reuses it. It probes
`http://127.0.0.1:8765/healthz` (in the container) and spawns no proxy of its own while the port stays
held. It waits up to 10 s for an orphan proxy (one whose FreeCAD has exited) or a holder without
`/healthz` to free the port, then spawns. In every other case `addon.log` gets one ERROR line that
starts `MCP proxy not started:` and names the holder. Stop the holder and restart FreeCAD. Before you
test, confirm that `/healthz` reports `"freecad_pid"` equal to the FreeCAD pid under test.

---

## Step 6 — Confirm the tool surface

- [ ] `tools/list` returns the live count: 46 names on the default posture, 45 typed tools plus
      `script_exec` (verify: call `tools/list` through the connected MCP client and count; record
      the count for the run)
- [ ] `export_self_read_stl` and `export_self_read_3mf` are **ABSENT**. They are internal RPC-only
      and are filtered out of `tools/list`.
- [ ] `script_exec` is **PRESENT** on the default surface. It is absent when
      `FREECAD_BUDDY_SCRIPT_EXEC=0` is set or the **Allow script_exec** preference is cleared (the
      variable wins over the preference), and when `FREECAD_BUDDY_UNATTENDED=1` is set without
      `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`. Under an off posture the count is 45, a call through
      the proxy returns `unknown method: script_exec`, and a direct call on the inline host returns
      `script_exec is off: FREECAD_BUDDY_SCRIPT_EXEC or the ScriptExec preference turned it off, or FREECAD_BUDDY_UNATTENDED=1 is set without FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`.

Expected counts by family: `document_` 7, `query_` 8, `verify_` 6, `export_` 3, `sketch_` 8,
`feature_` 11, `preview_dry_run` 1, `view_fit_viewport` 1, `script_exec` 1. Total 46 (45 under an
off posture).

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
| default | `$FCB_USER_DIR/freecad-buddy/audit.jsonl` |

The default does not depend on the working directory. The `operator settings:` line in `addon.log`
names the effective path and its source. Only the headless host still falls back to the cwd-relative
`freecad-buddy-audit.jsonl`.

- [ ] The effective path is writable (verify: the `operator settings:` line in the new `addon.log`
      lines gives `FREECAD_BUDDY_AUDIT_LOG=` with a path in a writable folder)
- [ ] A mutation actually commits (verify: `preview_dry_run` then `feature_body_create` on a
      scratch document returns `status: "OK"` with `post_verify.passed: true`). **This is the real
      check.** Run it before any mutation scenario; do not infer it from the environment.

A variable must be set **in the environment the FreeCAD process inherits**, before that process
starts: pass it with `docker exec -u cua -e NAME=value fcb-desktop fcb-freecad start`. A preference
change needs a FreeCAD restart.

Every scenario in TC-03, TC-04, TC-05, TC-08 and TC-13 group B depends on this step. TC-99-06
records the remaining AD-25 gap: the log is one file, not a dated file per session.

---

## Step 7 — Record the build banner

A fingerprint or a TNP result is only interpretable against the build that produced it. Call
`query_capabilities` (empty-object schema, no properties) and record all of these into the run
evidence:

- [ ] FreeCAD version: `freecad_version`, the live version every test case compares with
- [ ] `element_map` — the topological naming scheme in use
- [ ] serializer tag
- [ ] render ladder — which render backend was selected; `none` means every visual checkpoint skips
- [ ] `exec_enabled` — `true` on the default posture; `false` only when a case sets an off posture
- [ ] package version
- [ ] contract version (the RPC listener supports exactly `["1"]`)

Store this banner at the top of the run report. If FreeCAD is restarted mid-run, capture it again.

---

## cua-driver usage rules

These apply to every GUI step in TC-06 and TC-12. `cua-driver` runs in the container: call it
through `$FCB_CUA` (`scripts/automation/fcb_cua.sh`), which runs
`/usr/local/bin/cua-driver call <tool>` in the desktop session and maps the host `$PROJECT_ROOT` and
`$RUN_DIR` in the JSON to `/repo/...`.

### CLI stdin form

Pipe the JSON payload on stdin:
```bash
echo '{"pid":<pid>,"window_id":<wid>}' | "$FCB_CUA" get_window_state
```

### `element_token`, never `element_index`

Use `element_token` (for example `s00000004:71`). Indices are per-snapshot and keyed on
`(pid, window_id)`; a stale index silently clicks the wrong control. Refresh the snapshot with
`get_window_state` before acting, and act on the token from that snapshot.

### `verify_state` — unknown is not success

`verify_state({pid, window_id, expect})` returns one of pass, fail, or `unknown`. Treat `unknown`
as **not verified**. Either find a bounded postcondition that resolves, or add
`include_screenshot: true` and judge the visual evidence directly.

### Menu route: press the leaf item by `element_token`

`cua-driver` 0.28.1 refuses a Qt top-level menu item (`menu path segment 0 has no safe activation
action`), so a menu command is a leaf press: take a fresh `get_window_state` snapshot, take the
`element_token` of the `menu item` whose label is the leaf, and `click` it. The menu does not need to
be open. A snapshot invalidates every earlier token, so snapshot again before each press.
```bash
echo '{"pid":<pid>,"window_id":<wid>,"include_screenshot":false}' | "$FCB_CUA" get_window_state
echo '{"pid":<pid>,"element_token":"<Exit token from this snapshot>"}' | "$FCB_CUA" click
```
Measured in the container (FreeCAD 1.1.4): `Exit`, `New Document`, `Close`, `Save` and `Zoom In` are
listed; `Show All Objects` and `Standard Views` are listed while a document is open; the `Part`
workbench's `Primitives > Cube` is listed after the `Part` workbench leaf is pressed. Some
leaves are listed only while their command is available: `Recompute` while the document needs a
recompute (`F5` recomputes too, `ctrl+r` does nothing), `Toggle Visibility` while an object is selected,
`Undo` after a transaction. Without the leaf use `ctrl+z` with `hotkey`, `F5`, and the tree row toggle of
`test-plan.md` §6 (a foreground pixel click on the row, then a window-level `press_key` `space`). The numbered `Windows` entries expose only `Activates this window`: press the `Next` or
`Previous` leaf of the `Windows` menu until the `list_windows` title names the document. The result of
a leaf press is `effect:"unverifiable"`; the verdict comes from the window title or a fresh screenshot.
The proof records are in `tests/uat/run/2026-11-18-10-10-proof/K2-*.txt`.

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
echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc06-iso.png"}' | "$FCB_CUA" get_window_state
```
`$FCB_CUA` maps `$RUN_DIR` to its `/repo/tests/uat/run/...` path, and the file appears in the run folder
on the host.
Then `Read` the file only when a visual comparison actually needs it.

### Forbidden commands in the container

Do not use: `wmctrl -a`, `xdotool windowactivate`, `kill -KILL` (except in a scenario that is the
unclean-kill case). They raise or end a window outside the driver's tracking.

Two further limits: `modifier` is not honoured on a background click, and right-click or
`count > 1` skip the accessibility invoke path.

### `replay_trajectory` is regression evidence only

It cannot re-resolve element tokens across sessions. A recorded trajectory documents what happened;
it is not a re-runnable test step. Never write a checkpoint that depends on replaying one.
