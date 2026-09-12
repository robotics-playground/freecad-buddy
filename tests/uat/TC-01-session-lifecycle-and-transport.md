# TC-01: Session Lifecycle & Transport

Validates the shipped bridge topology: the GUI addon starts the in-FreeCAD RPC listener and
auto-spawns the external MCP HTTP proxy on `127.0.0.1:8765`, so opening FreeCAD is the only setup
step. Also validates the transport contract — the `rpc_hello` handshake, the session token, the
`contract_version` check, the discovery file, and the tool surface the proxy exposes. Executed by
the agent against the live application; the two legacy sweep scripts are wrapped as evidence, not
re-derived.

**Host note**: scenarios that drive `mcp__freecad-buddy__*` run under the **H2 proxy** host
(`gui_external/entry.py`). That path has its own `_call_tool` and does not carry the
suspect-document logic, the non-string `doc` guard, or the audit writes that the inline host in
`adapters/mcp_server.py` has. Each checkpoint below names its host where the two diverge.

## Prerequisites

- [ ] FreeCAD 1.1.1 installed (verify: `ls "/c/Program Files/FreeCAD 1.1/bin/freecad.exe"`)
- [ ] Addon linked into the FreeCAD Mod dir (verify: `ls "$APPDATA/FreeCAD/v1-1/Mod/FreeCADBuddy/freecad_buddy/hosts/gui_addon/InitGui.py"`)
- [ ] Repo venv exists so the addon can discover the proxy interpreter (verify: `ls .venv/Scripts/pythonw.exe`)
- [ ] cua-driver daemon runs in an interactive session (verify: `cua-driver status` shows `SessionId` ≥ 1)
- [ ] micromamba `fcb` env is H1-capable (verify: `"$USERPROFILE/micromamba/envs/fcb/python.exe" -c "import FreeCAD, mcp"`)
- [ ] No FreeCAD process and nothing on `:8765` before TC-01-01 (verify: `netstat -ano | grep :8765` returns nothing)

---

### TC-01-01: Addon auto-spawns the MCP proxy

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §1 (bridge topology), `integration-mcp-clients.md` §2 (HTTP endpoint)

**Preconditions**:
- [ ] No FreeCAD process is running (verify: `tasklist | grep -i freecad` returns nothing)
- [ ] `:8765` is free (verify: `netstat -ano | grep :8765` returns nothing)
- [ ] Addon log is rotated aside so the new run's lines are unambiguous (verify: `mv "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log.prev"`)

**Steps**:
1. Launch FreeCAD through cua-driver. Do **not** run any `serve` command by hand — starting
   `serve --mode rpc` manually invalidates this scenario.
   ```
   cua launch_app { path: "C:\\Program Files\\FreeCAD 1.1\\bin\\freecad.exe" }
   ```
2. Wait for the main window to exist, then record the pid and window id.
   ```
   cua list_windows {}
   ```
3. Read the addon log written by the freshly started bridge.
   ```bash
   cat "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"
   ```

**Checkpoints**:
- [ ] CP1: The RPC listener bound a port — verify: `grep "freecad-buddy RPC listener started on" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns one line naming `127.0.0.1:<port>`
- [ ] CP2: The proxy was spawned by the addon, not by an operator — verify: `grep "spawned MCP proxy" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line with `(pid <n>) -> http://127.0.0.1:8765/mcp`
- [ ] CP3: `:8765` is LISTENING — verify: `netstat -ano | grep :8765` shows `LISTENING` and the owning pid equals the pid in CP2
- [ ] CP4: The proxy runs in the external venv interpreter, not FreeCAD's bundled Python — verify: `powershell -c "(Get-CimInstance Win32_Process -Filter 'ProcessId=<CP2 pid>').CommandLine"` contains `.venv\Scripts\python` and `-m freecad_buddy.hosts.main serve --mode rpc --transport http`
- [ ] CP5: No manual `serve` process exists — verify: the CP4 command line is the only `freecad_buddy.hosts.main serve` process in `powershell -c "Get-CimInstance Win32_Process | ? {$_.CommandLine -like '*hosts.main*serve*'} | select ProcessId"`
- [ ] CP6: The bridge answers over MCP — verify: `mcp query_capabilities {}` returns `status: "OK"`
- [ ] CP7: The proxy log records no spawn failure — verify: `grep -i "failed to spawn" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns nothing

**Cleanup**:
```bash
rm -f "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log.prev"
```

---

### TC-01-02: Legacy G0 sweep still green

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1 (tool surface), `verification-design.md` §6 (export pairing)

**Preconditions**:
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/*.FCStd` lists 5 files)
- [ ] No stale H1 server holds the golden files (verify: `tasklist | grep -i "python.exe"` shows no `micromamba/envs/fcb` process)

**Steps**:
1. Run the happy-path sweep. It spawns its own H1 stdio host from the `fcb` env and does not touch
   the GUI bridge.
   ```bash
   uv run python scripts/automation/run_mcp_e2e.py
   ```

**Checkpoints**:
- [ ] CP1: The sweep exits 0 — verify: `echo $?` immediately after the run returns `0`
- [ ] CP2: Every check passed — verify: `python -c "import json;print(json.load(open('_automation/e2e_report.json'))['all_passed'])"` returns `True`
- [ ] CP3: The box volume is analytic — verify: the report entry `query_mass_properties:box-10-20-30` shows `volume=6000.0`
- [ ] CP4: Export round-trips verified — verify: every `verify_export_step:*` and `verify_export_stl:*` entry in `_automation/e2e_report.json` has `status=OK`
- [ ] CP5: No unhandled server fault — verify: `grep -iE "access violation|segfault|swig director" _automation/server.stderr.log` returns nothing
- [ ] CP6: The GUI bridge is unaffected by the sweep — verify: `mcp query_capabilities {}` still returns `status: "OK"` after the sweep

**Cleanup**:
```bash
rm -f _automation/*.step _automation/*.stl _automation/scratch.FCStd
```

---

### TC-01-03: tools/list is exactly the 44 shipped names

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1 (tool surface), `integration-mcp-clients.md` §2 (discovery)

**Preconditions**:
- [ ] The bridge answers over MCP (verify: `mcp query_capabilities {}` returns `status: "OK"`)

**Steps**:
1. List the tools the proxy advertises and save the names.
   ```bash
   uv run python -c "
   import asyncio, json
   from mcp.client.streamable_http import streamablehttp_client
   from mcp import ClientSession
   async def main():
       async with streamablehttp_client('http://127.0.0.1:8765/mcp') as (r, w, _):
           async with ClientSession(r, w) as s:
               await s.initialize()
               names = sorted(t.name for t in (await s.list_tools()).tools)
               json.dump(names, open('_automation/tools_list.json','w'), indent=1)
               print(len(names))
   asyncio.run(main())
   "
   ```

**Checkpoints**:
- [ ] CP1: Exactly 44 tools — verify: the command above prints `44`
- [ ] CP2: The internal RPC-only writers are filtered out — verify: `grep -E "export_self_read_(stl|3mf)" _automation/tools_list.json` returns nothing
- [ ] CP3: `debug_exec` is absent while its flag is unset — verify: `grep debug_exec _automation/tools_list.json` returns nothing
- [ ] CP4: Family counts match the catalog — verify: `python -c "import json,collections;n=json.load(open('_automation/tools_list.json'));print({p:sum(1 for x in n if x.startswith(p)) for p in ('document_','query_','verify_','export_','sketch_','feature_','preview_')})"` returns `document_: 7, query_: 8, verify_: 6, export_: 3, sketch_: 8, feature_: 11, preview_: 1`
- [ ] CP5: The 13 read-only-profile names are all present — verify: `python -c "import json;n=set(json.load(open('_automation/tools_list.json')));ro={'query_capabilities','query_tree_summary','query_object','query_mass_properties','query_dependencies','query_sketch_info','query_placement','verify_shape','verify_sketch','verify_recompute','document_open','document_close','document_list'};print(ro<=n)"` returns `True`
- [ ] CP6: Every input schema is closed — verify: the same client run with `t.inputSchema.get('additionalProperties')` shows `False` for all 44 tools

**Cleanup**:
```bash
rm -f _automation/tools_list.json
```

---

### TC-01-04: query_capabilities reports the live build honestly

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §2 (capability probes), `data-contracts-design.md` §9 (banner)

**Preconditions**:
- [ ] FreeCAD GUI is the process serving the bridge (verify: the CP2 proxy pid from TC-01-01 is still alive)
- [ ] `FREECAD_BUDDY_ALLOW_EXEC` is unset (verify: `echo "${FREECAD_BUDDY_ALLOW_EXEC:-unset}"` returns `unset`)

**Steps**:
1. Read the capability banner over MCP.
   ```
   mcp query_capabilities {}
   ```
2. Read the same facts from the running FreeCAD process, to cross-check rather than trust the
   banner.
   ```
   cua invoke_menu { pid: <freecad pid>, window_id: <window id>, path: ["Help", "About FreeCAD"] }
   ```

**Checkpoints**:
- [ ] CP1: Version matches the running build — verify: `structured_content.freecad_version` equals the version in the About dialog (`1.1.1`) and equals `grep "freecad_version" "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"`
- [ ] CP2: Every banner key is present — verify: the response keys are exactly `freecad_version`, `element_map_available`, `serializer`, `varset_backend`, `render`, `sketcher_available`, `partdesign_available`, `enums`, `exec_enabled`
- [ ] CP3: `element_map_available` is a live boolean probe, not a constant — verify: the value is `true` or `false`, never null or a string
- [ ] CP4: The serializer tag names the real serializer — verify: `structured_content.serializer` is a non-empty string
- [ ] CP5: The render ladder reports a GUI mode under the GUI host — verify: `structured_content.render` is `"gui_constructed"` (a value of `"none"` means every screenshot checkpoint in TC-06 must be skipped, not failed)
- [ ] CP6: exec is disabled by default — verify: `structured_content.exec_enabled` is `false`, and the same value appears in the handshake capabilities of `rpc-<freecad pid>.json`'s session
- [ ] CP7: Sketcher and PartDesign report available in the GUI build — verify: `sketcher_available` and `partdesign_available` are both `true`

**Cleanup**: none. This scenario mutates nothing.

---

### TC-01-05: Per-tool timeout budgets match the catalog

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1 (per-tool budgets), `integration-mcp-freecad.md` §3 (marshal timeout)

**Preconditions**:
- [ ] Repo checkout matches the installed addon (verify: `ls -l "$APPDATA/FreeCAD/v1-1/Mod/FreeCADBuddy/freecad_buddy"` shows the symlink target under `src/`)

**Steps**:
1. Dump every tool's declared timeout from the shipped catalog.
   ```bash
   uv run python -c "
   from freecad_buddy.hosts.tool_catalog import tool_specs
   for s in sorted(tool_specs(), key=lambda s: s.name):
       print(f'{s.name}\t{s.timeout_s}\t{s.mutating}')
   "
   ```

**Checkpoints**:
- [ ] CP1: Only four distinct budgets exist — verify: the dump's timeout column has exactly the values `30.0`, `60.0`, `120.0`, `180.0`
- [ ] CP2: `preview_dry_run` is the only 180 s tool — verify: `... | awk -F'\t' '$2==180.0'` returns exactly one row, `preview_dry_run`
- [ ] CP3: The 30 s set is correct — verify: with `debug_exec` ungated the rows with `30.0` are exactly `document_create`, `document_close`, `document_list`, `query_capabilities`, `query_tree_summary`, `query_object`, `query_mass_properties`, `query_dependencies`, `query_sketch_info`, `query_placement`
- [ ] CP4: The 60 s set is correct — verify: the rows with `60.0` are exactly `document_open`, `query_screenshot`, `verify_shape`, `verify_sketch`
- [ ] CP5: Every `sketch_*`, `feature_*`, and `export_*` tool is 120 s — verify: `... | awk -F'\t' '$1 ~ /^(sketch_|feature_|export_)/ && $2!=120.0'` returns nothing
- [ ] CP6: The mutating flag agrees with the family — verify: every `query_*` and `verify_*` row has `mutating` `False`, and every `sketch_*`, `feature_*`, `export_*` row has `True`
- [ ] CP7: Document lifecycle tools are marked mutating even when they change no geometry — verify: `document_open` and `document_close` both report `mutating` `True`, because they open and close documents; this is why neither appears in a mutating-means-geometry reading of the catalog

**Cleanup**: none. This scenario reads the catalog only.

---

### TC-01-06: Wrong contract_version is refused

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (handshake), `integration-mcp-clients.md` §2 (contract negotiation)

**Preconditions**:
- [ ] The discovery file for the live FreeCAD exists (verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"`)

**Steps**:
1. Connect directly to the RPC listener with a valid token but an unsupported contract version.
   ```bash
   uv run python -c "
   import json, socket, os, glob
   rec = json.load(open(sorted(glob.glob(os.path.expandvars(r'%APPDATA%/FreeCAD/v1-1/freecad-buddy/rpc-*.json')))[-1]))
   s = socket.create_connection((rec['host'], rec['port']), timeout=5)
   s.sendall((json.dumps({'jsonrpc':'2.0','id':1,'method':'rpc_hello',
       'params':{'token':rec['token'],'contract_version':'99'}})+'\n').encode())
   print(s.makefile('r', encoding='utf-8').readline().strip())
   "
   ```

**Checkpoints**:
- [ ] CP1: The reply is a JSON-RPC error, not a result — verify: the printed frame has an `error` key and no `result` key
- [ ] CP2: The error code is the version-mismatch code — verify: `error.code` is `-32004`
- [ ] CP3: The message is verbatim — verify: `error.message` is exactly `contract version unsupported`
- [ ] CP4: The supported list is disclosed to an authenticated caller — verify: `error.data` is `{"supported": ["1"]}`
- [ ] CP5: No capabilities leak in the refusal — verify: the printed frame contains no `capabilities` and no `freecad_version` key
- [ ] CP6: The connection is closed after the refusal — verify: a second `readline()` on the same socket returns an empty string
- [ ] CP7: The listener survives the refusal — verify: `mcp query_capabilities {}` still returns `status: "OK"`

**Cleanup**: none. The socket closes with the script.

---

### TC-01-07: Bad session token is refused before any disclosure

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (token authentication), `integration-mcp-clients.md` §2 (session token)

**Preconditions**:
- [ ] The discovery file for the live FreeCAD exists (verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"`)

**Steps**:
1. Connect with a wrong token **and** an unsupported contract version at the same time. The listener
   authenticates before checking the version, so the reply must be the auth failure.
   ```bash
   uv run python -c "
   import json, socket, os, glob
   rec = json.load(open(sorted(glob.glob(os.path.expandvars(r'%APPDATA%/FreeCAD/v1-1/freecad-buddy/rpc-*.json')))[-1]))
   s = socket.create_connection((rec['host'], rec['port']), timeout=5)
   s.sendall((json.dumps({'jsonrpc':'2.0','id':7,'method':'rpc_hello',
       'params':{'token':'not-the-token','contract_version':'99'}})+'\n').encode())
   print(s.makefile('r', encoding='utf-8').readline().strip())
   "
   ```
2. Repeat with the token field omitted entirely.

**Checkpoints**:
- [ ] CP1: The error code is the auth-failure code — verify: `error.code` is `-32000`
- [ ] CP2: The message is verbatim — verify: `error.message` is exactly `auth failed`
- [ ] CP3: Auth is checked **before** the version — verify: the reply is `-32000` / `auth failed`, **not** `-32004` / `contract version unsupported`, even though the version was also invalid
- [ ] CP4: No capability disclosure to an unauthenticated caller — verify: the frame contains no `capabilities`, no `freecad_version`, and no `supported` list
- [ ] CP5: The omitted-token case behaves identically — verify: step 2 also returns `-32000` / `auth failed`
- [ ] CP6: The refusal is logged — verify: `grep "token mismatch; closing" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns two lines (one per attempt)
- [ ] CP7: The listener survives both refusals — verify: `mcp query_capabilities {}` still returns `status: "OK"`

**Cleanup**: none.

---

### TC-01-08: First frame that is not rpc_hello is refused

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (handshake required)

**Preconditions**:
- [ ] The discovery file for the live FreeCAD exists (verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"`)

**Steps**:
1. Send a valid tool call as the first frame, skipping the handshake.
   ```bash
   uv run python -c "
   import json, socket, os, glob
   rec = json.load(open(sorted(glob.glob(os.path.expandvars(r'%APPDATA%/FreeCAD/v1-1/freecad-buddy/rpc-*.json')))[-1]))
   s = socket.create_connection((rec['host'], rec['port']), timeout=5)
   s.sendall((json.dumps({'jsonrpc':'2.0','id':3,'method':'query_capabilities','params':{}})+'\n').encode())
   f = s.makefile('r', encoding='utf-8')
   print('frame1:', f.readline().strip())
   print('frame2:', repr(f.readline()))
   "
   ```
2. Repeat with a first frame that is not valid JSON at all, for example the bytes `not json\n`.

**Checkpoints**:
- [ ] CP1: The error code is the no-handshake code — verify: `error.code` is `-32002`
- [ ] CP2: The message is verbatim — verify: `error.message` is exactly `handshake required`
- [ ] CP3: The request id is echoed — verify: the frame's `id` is `3`
- [ ] CP4: The socket is closed immediately after the refusal — verify: `frame2` prints `''`
- [ ] CP5: The tool never ran — verify: the frame carries no `result` and no `structured_content`
- [ ] CP6: The refusal is logged — verify: `grep "first frame was not rpc_hello; closing" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line
- [ ] CP7: The malformed-JSON case also refuses — verify: step 2 returns `-32002` / `handshake required` with `id` `null`
- [ ] CP8: The listener survives both — verify: `mcp query_capabilities {}` still returns `status: "OK"`

**Cleanup**: none.

---

### TC-01-09: Discovery file is live and correct

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §1 (discovery), `integration-mcp-clients.md` §2 (attach)

**Preconditions**:
- [ ] FreeCAD is running with a known pid (verify: `cua list_windows {}` names the pid)

**Steps**:
1. Read the discovery record for the live FreeCAD pid.
   ```bash
   cat "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"
   ```
2. Check its file mode.
   ```bash
   ls -l "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"
   ```

**Checkpoints**:
- [ ] CP1: The file sits under the FreeCAD user appdata dir — verify: the path is `$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<pid>.json`; `$APPDATA/FreeCAD/Mod/` is legacy and empty
- [ ] CP2: Every field is present — verify: the record keys are exactly `schema`, `pid`, `host`, `port`, `token`, `contract_version`, `freecad_version`, `started`
- [ ] CP3: `pid` names the live FreeCAD process — verify: the `pid` value equals the pid from `cua list_windows`, and `tasklist | grep <pid>` shows `freecad.exe`
- [ ] CP4: `host` and `port` match a bound loopback socket — verify: `host` is `127.0.0.1` and `netstat -ano | grep "127.0.0.1:<port>"` shows `LISTENING` owned by that pid
- [ ] CP5: `contract_version` is the supported version — verify: the value is `"1"`
- [ ] CP6: `freecad_version` matches the live build — verify: the value equals `query_capabilities` `freecad_version` (`1.1.1`)
- [ ] CP7: The token authenticates — verify: an `rpc_hello` using this `token` and `contract_version` returns a `result` carrying `capabilities`
- [ ] CP8: Mode is restricted, best-effort on Windows — verify: `ls -l` shows `-rw-------` on POSIX. On Windows `chmod` only toggles the read-only bit, so record the observed mode and treat the loopback bind plus the per-session token as the enforced control; do not fail CP8 on Windows

**Cleanup**: none.

---

### TC-01-10: Discovery file is deleted on clean shutdown

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §1 (teardown)

**Preconditions**:
- [ ] The discovery file for the live pid exists (verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"`)
- [ ] No unsaved document is open, so the quit does not raise a save dialog (verify: `mcp document_list {}` shows no document with `transient: true`)
- [ ] Record the proxy pid before the quit (verify: `grep "spawned MCP proxy" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"`)

**Steps**:
1. Close FreeCAD cleanly through its own menu, not by killing the process.
   ```
   cua invoke_menu { pid: <freecad pid>, window_id: <window id>, path: ["File", "Exit"] }
   ```
2. Wait until the process is gone.
   ```bash
   tasklist | grep -i freecad.exe
   ```

**Checkpoints**:
- [ ] CP1: FreeCAD exited — verify: `tasklist | grep -i freecad.exe` returns nothing
- [ ] CP2: The discovery file is gone — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"` reports no such file
- [ ] CP3: The proxy child was terminated with the parent — verify: `tasklist | grep <proxy pid>` returns nothing
- [ ] CP4: `:8765` is free — verify: `netstat -ano | grep :8765` returns nothing
- [ ] CP5: No other pid's discovery file was deleted — verify: files named for other pids under `$APPDATA/FreeCAD/v1-1/freecad-buddy/` are unchanged in count

**Cleanup**: relaunch FreeCAD for the following scenarios.
```
cua launch_app { path: "C:\\Program Files\\FreeCAD 1.1\\bin\\freecad.exe" }
```

---

### TC-01-11: Stale discovery record from a dead pid fails fast

**Priority**: High
**Design Ref**: `integration-mcp-clients.md` §2 (attach and fail fast), `integration-mcp-freecad.md` §1 (discovery)

**Preconditions**:
- [ ] At least one discovery file names a pid that no longer exists (verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/"rpc-*.json` lists more pids than `tasklist | grep -c freecad.exe`). An unclean kill leaves these behind, so the directory normally already holds several.

**Steps**:
1. Pick a discovery file whose pid is dead and try to attach to it with a bounded timeout.
   ```bash
   uv run python -c "
   import json, socket, sys, time
   rec = json.load(open(sys.argv[1]))
   t0 = time.monotonic()
   try:
       s = socket.create_connection((rec['host'], rec['port']), timeout=5)
       s.sendall((json.dumps({'jsonrpc':'2.0','id':1,'method':'rpc_hello',
           'params':{'token':rec['token'],'contract_version':rec['contract_version']}})+'\n').encode())
       print('reply:', s.makefile('r', encoding='utf-8').readline().strip())
   except OSError as exc:
       print('refused:', type(exc).__name__, exc)
   print('elapsed', round(time.monotonic()-t0, 2))
   " "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<dead pid>.json"
   ```

**Checkpoints**:
- [ ] CP1: The named pid really is dead — verify: `tasklist | grep <dead pid>` returns nothing
- [ ] CP2: The connect fails rather than hanging — verify: the script prints `refused:` with `ConnectionRefusedError` or `TimeoutError`, never a `reply:` line
- [ ] CP3: It fails fast — verify: the printed `elapsed` is under the 5 s connect timeout
- [ ] CP4: The stale file is not self-healing — verify: the file still exists after the failed attach; the listener only deletes its own record on clean shutdown
- [ ] CP5: The live bridge is unaffected — verify: `mcp query_capabilities {}` still returns `status: "OK"`
- [ ] CP6: A port reused by an unrelated process cannot be mistaken for the bridge — verify: if the connect **succeeds**, the reply must be an error rather than a `capabilities` result, because the stale token cannot authenticate against any other listener

**Cleanup**: leave the stale files. They are the input for a re-run of this scenario.

---

### TC-01-12: Proxy restart re-attaches to the same FreeCAD

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §1 (proxy is stateless over RPC), `integration-mcp-clients.md` §2 (HTTP endpoint)

**Preconditions**:
- [ ] FreeCAD is running and the bridge answers (verify: `mcp query_capabilities {}` returns `status: "OK"`)
- [ ] A document is open, so re-attachment can be proven against live state (verify: `mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns a handle)
- [ ] Record the proxy pid (verify: `netstat -ano | grep :8765`)

**Steps**:
1. Terminate **only** the proxy child. Do not touch the FreeCAD process.
   ```bash
   powershell -c "Stop-Process -Id <proxy pid>"
   ```
2. Confirm `:8765` is free, then start the proxy again with the same command the addon used.
   ```bash
   ".venv/Scripts/python.exe" -m freecad_buddy.hosts.main serve --mode rpc --transport http
   ```
3. Re-issue a query against the handle minted before the restart.

**Checkpoints**:
- [ ] CP1: FreeCAD survived the proxy kill — verify: `tasklist | grep <freecad pid>` still shows `freecad.exe`
- [ ] CP2: The RPC listener stayed bound — verify: the discovery file `rpc-<freecad pid>.json` is unchanged, same `port` and same `token`
- [ ] CP3: `:8765` is served again — verify: `netstat -ano | grep :8765` shows `LISTENING` on the new proxy pid
- [ ] CP4: The restarted proxy reaches the same FreeCAD — verify: `mcp query_capabilities {}` returns the same `freecad_version` as before the restart
- [ ] CP5: Document handles survive — verify: `mcp query_tree_summary { doc: <handle minted before the restart> }` returns `status: "OK"`, because the handle registry lives in FreeCAD, not in the proxy
- [ ] CP6: `document_list` still reports the open document — verify: `mcp document_list {}` lists the `box-10-20-30` label

**Cleanup**:
```
mcp document_close { doc: <handle> }
```

---

### TC-01-13: FREECAD_BUDDY_NO_AUTO_MCP suppresses the spawn, and the CLI contract holds

**Priority**: Medium
**Design Ref**: `integration-mcp-freecad.md` §1 (opt-out), `integration-mcp-clients.md` §2 (CLI surface)

**Preconditions**:
- [ ] FreeCAD is not running (verify: `tasklist | grep -i freecad.exe` returns nothing)
- [ ] `:8765` is free (verify: `netstat -ano | grep :8765` returns nothing)
- [ ] Addon log rotated aside (verify: `mv "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log.prev"`)

**Steps**:
1. Launch FreeCAD with the opt-out set to a value that is **not** `"1"`, to prove the check is
   truthiness and not an equality test against `"1"`.
   ```
   cua launch_app { path: "C:\\Program Files\\FreeCAD 1.1\\bin\\freecad.exe", env: { FREECAD_BUDDY_NO_AUTO_MCP: "no" } }
   ```
2. Read the addon log.
3. Exercise the two refused CLI combinations from the repo venv.
   ```bash
   ".venv/Scripts/python.exe" -m freecad_buddy.hosts.main serve --mode rpc; echo "exit=$?"
   ".venv/Scripts/python.exe" -m freecad_buddy.hosts.main serve --transport http --mode inline; echo "exit=$?"
   ```

**Checkpoints**:
- [ ] CP1: The listener still started — verify: `grep "freecad-buddy RPC listener started on" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line, and `rpc-<pid>.json` exists
- [ ] CP2: The proxy was not spawned — verify: `netstat -ano | grep :8765` returns nothing
- [ ] CP3: The log states why, verbatim — verify: `grep "FREECAD_BUDDY_NO_AUTO_MCP set; not auto-starting the MCP proxy" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line
- [ ] CP4: The check is truthiness, not `"1"` — verify: CP2 and CP3 hold even though the value was `no`, a non-empty string that is not `1`
- [ ] CP5: `--mode rpc` without `--transport http` exits 2 — verify: the first CLI command writes exactly `--mode rpc requires --transport http.` to stderr and `exit=2`
- [ ] CP6: `--transport http --mode inline` is refused — verify: the second CLI command writes exactly `transport 'http' is not available yet; use --transport stdio.` to stderr and `exit=2`
- [ ] CP7: Neither refused command bound a port — verify: `netstat -ano | grep :8765` still returns nothing

**Cleanup**: restart FreeCAD without the variable so later scenarios get the auto-spawned proxy.
```
cua kill_app { pid: <freecad pid> }
cua launch_app { path: "C:\\Program Files\\FreeCAD 1.1\\bin\\freecad.exe" }
```
```bash
rm -f "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log.prev"
```

---

### TC-01-14: Unclean FreeCAD kill leaves no half-open bridge

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §1 (teardown), `integration-mcp-clients.md` §2 (attach failure)

**Preconditions**:
- [ ] FreeCAD is running and the bridge answers (verify: `mcp query_capabilities {}` returns `status: "OK"`)
- [ ] Record the FreeCAD pid, the RPC port from the discovery file, and the proxy pid

**Steps**:
1. Kill the FreeCAD process without letting it run its shutdown handlers. Use the cua tool, not
   `taskkill /F` from a shell.
   ```
   cua kill_app { pid: <freecad pid> }
   ```
2. Try to connect to the RPC port recorded before the kill.
   ```bash
   uv run python -c "
   import socket, time
   t0 = time.monotonic()
   try:
       socket.create_connection(('127.0.0.1', <rpc port>), timeout=5)
       print('connected')
   except OSError as exc:
       print('refused:', type(exc).__name__)
   print('elapsed', round(time.monotonic()-t0, 2))
   "
   ```
3. Try one MCP call through the endpoint.

**Checkpoints**:
- [ ] CP1: FreeCAD is gone — verify: `tasklist | grep <freecad pid>` returns nothing
- [ ] CP2: The RPC port no longer accepts — verify: step 2 prints `refused:` and never `connected`
- [ ] CP3: The failure is fast, not a hang — verify: the printed `elapsed` is under the 5 s connect timeout
- [ ] CP4: The proxy child does not outlive its parent as a serving endpoint — verify: either `tasklist | grep <proxy pid>` returns nothing, or the proxy is alive but `mcp query_capabilities {}` returns a transport-level failure rather than a fabricated `OK`
- [ ] CP5: The kill leaves a stale discovery file, matching the shipped behaviour — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<killed pid>.json"` still lists the file. A clean exit deletes it (TC-01-10 CP2); an unclean kill does not. Record this as observed state, not a defect.
- [ ] CP6: A fresh launch is not blocked by the stale state — verify: relaunching FreeCAD writes a new `rpc-<new pid>.json` and `:8765` returns to `LISTENING`
- [ ] CP7: The new session mints a different token — verify: the `token` in the new discovery file differs from the killed session's token, and the old token no longer authenticates

**Cleanup**:
```bash
rm -f "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<killed pid>.json"
```
