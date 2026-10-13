# TC-01: Session Lifecycle & Transport

Validates the shipped bridge topology: the GUI addon starts the in-FreeCAD RPC listener and
auto-spawns the external MCP HTTP proxy on `127.0.0.1:8765`, so opening FreeCAD is the only setup
step. Also validates the transport contract — the `rpc_hello` handshake, the session token, the
`contract_version` check, the discovery file, and the tool surface the proxy exposes. Executed by
the agent against the live application; the two legacy sweep scripts are wrapped as evidence, not
re-derived.

**Host**: GUI through the H2 proxy for every scenario that drives `mcp__freecad-buddy__*`
(`gui_external/entry.py`). That path has its own `_call_tool` and does not carry the
suspect-document logic, the non-string `doc` guard, or the audit writes that the inline host in
`adapters/mcp_server.py` has. Each assertion below names its host where the two diverge. TC-01-02
runs its sweep on the H1 headless host from the `fcb` env, alongside the live GUI. TC-01-05 reads
the shipped catalog from the repo venv and needs no host.

## Preconditions

- [ ] FreeCAD 1.1.1 installed (verify: `ls "$FREECAD_EXE"`)
- [ ] Addon linked into the FreeCAD Mod dir (verify: `ls "$APPDATA/FreeCAD/v1-1/Mod/FreeCADBuddy/freecad_buddy/hosts/gui_addon/InitGui.py"`)
- [ ] Repo venv exists so the addon can discover the proxy interpreter (verify: `ls .venv/Scripts/pythonw.exe`)
- [ ] cua-driver daemon runs in an interactive session (verify: `cua-driver status` shows `SessionId` ≥ 1)
- [ ] micromamba `fcb` env is H1-capable (verify: `"$FCB_PYTHON" -c "import FreeCAD, mcp"`)
- [ ] No FreeCAD process and nothing on `:8765` before TC-01-01 (verify: `netstat -ano | grep :8765` returns nothing)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)

---

### TC-01-01: Addon auto-spawns the MCP proxy

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §1 (bridge topology), `integration-mcp-clients.md` §2 (HTTP endpoint)

**Given** no FreeCAD process is running — verify: `tasklist | grep -i freecad` returns nothing  
**And** `:8765` is free — verify: `netstat -ano | grep :8765` returns nothing  
**And** the addon log is rotated aside so the new run's lines are unambiguous — verify: `mv "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log.prev"`  

**When** FreeCAD is launched through cua-driver. Do **not** run any `serve` command by hand — starting `serve --mode rpc` manually invalidates this scenario.  
```
cua-driver call launch_app { path: "$FREECAD_EXE" }
```
**And** the main window is waited for, then the pid and window id are recorded  
```
cua-driver call list_windows {}
```
**And** the addon log written by the freshly started bridge is read  
```bash
cat "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"
```
**And** a golden model is opened so the closing visual has a subject  
```
mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }
```

**Then** the RPC listener bound a port — verify: `grep "freecad-buddy RPC listener started on" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns one line naming `127.0.0.1:<port>`  
**And** the proxy was spawned by the addon, not by an operator — verify: `grep "spawned MCP proxy" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line with `(pid <n>) -> http://127.0.0.1:8765/mcp`  
**And** `:8765` is LISTENING — verify: `netstat -ano | grep :8765` shows `LISTENING` and the owning pid equals the pid in the spawn line  
**And** the proxy runs in the external venv interpreter, not FreeCAD's bundled Python — verify: `powershell -c "(Get-CimInstance Win32_Process -Filter 'ProcessId=<proxy pid>').CommandLine"` contains `.venv\Scripts\python` and `-m freecad_buddy.hosts.main serve --mode rpc --transport http`  
**And** no manual `serve` process exists — verify: that command line is the only `freecad_buddy.hosts.main serve` process in `powershell -c "Get-CimInstance Win32_Process | ? {$_.CommandLine -like '*hosts.main*serve*'} | select ProcessId"`  
**And** the bridge answers over MCP — verify: `mcp query_capabilities {}` returns `status: "OK"`  
**And** the proxy log records no spawn failure — verify: `grep -i "failed to spawn" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns nothing  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the auto-spawned bridge really drives the human's window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-01-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a FreeCAD main window with a 3D view area, one box-shaped solid inside it, all eight corners inside the view rectangle, no edge cut off, and no dialog or error popup. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. A LISTENING port over a window with no visible part is the failure this catches.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```
```bash
rm -f "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log.prev"
```

---

### TC-01-02: Legacy G0 sweep still green

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1 (tool surface), `verification-design.md` §6 (export pairing)

**Given** golden models are present — verify: `ls benchmarks/g0/golden-models/*.FCStd` lists 5 files  
**And** no stale H1 server holds the golden files — verify: `tasklist | grep -i "python.exe"` shows no `micromamba/envs/fcb` process  
**And** a golden model is open on the GUI host so the closing visual has a subject — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the GUI's pre-sweep state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-02-before.png"}' | & cua-driver call get_window_state`  

**When** the happy-path sweep is run. It spawns its own H1 stdio host from the `fcb` env and does not touch the GUI bridge.  
```bash
uv run python scripts/automation/run_mcp_e2e.py
```

**Then** the sweep exits 0 — verify: `echo $?` immediately after the run returns `0`  
**And** every check passed — verify: `python -c "import json;print(json.load(open('$RUN_DIR/evidence/tc-01-02-e2e_report.json'))['all_passed'])"` returns `True`  
**And** the box volume is analytic — verify: the report entry `query_mass_properties:box-10-20-30` shows `volume=6000.0`  
**And** export round-trips verified — verify: every `verify_export_step:*` and `verify_export_stl:*` entry in `$RUN_DIR/evidence/tc-01-02-e2e_report.json` has `status=OK`  
**And** no unhandled server fault — verify: `grep -iE "access violation|segfault|swig director" "$RUN_DIR/evidence/tc-01-02-server.stderr.log"` returns nothing  
**And** the GUI bridge is unaffected by the sweep — verify: `mcp query_capabilities {}` still returns `status: "OK"` after the sweep  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the headless sweep never reached into the human's window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-02-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen in each: one box-shaped solid, whole, no edge clipped, the same document label in the tree, and no extra document, no new window, and no dialog that the sweep might have raised. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```
```bash
rm -f "$RUN_DIR/evidence/tc-01-02-"*.step "$RUN_DIR/evidence/tc-01-02-"*.stl "$RUN_DIR/evidence/tc-01-02-scratch.FCStd"
```

---

### TC-01-03: tools/list is exactly the 45 shipped names

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1 (tool surface), `integration-mcp-clients.md` §2 (discovery)

**Given** the bridge answers over MCP — verify: `mcp query_capabilities {}` returns `status: "OK"`  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  

**When** the tools the proxy advertises are listed and the names saved  
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
            json.dump(names, open('$RUN_DIR/evidence/tc-01-03-tools_list.json','w'), indent=1)
            print(len(names))
asyncio.run(main())
"
```

**Then** there are exactly 45 tools — verify: the command above prints `45`  
**And** the internal RPC-only writers are filtered out — verify: `grep -E "export_self_read_(stl|3mf)" "$RUN_DIR/evidence/tc-01-03-tools_list.json"` returns nothing  
**And** `debug_exec` is absent while its flag is unset — verify: `grep debug_exec "$RUN_DIR/evidence/tc-01-03-tools_list.json"` returns nothing  
**And** family counts match the catalog — verify: `python -c "import json,collections;n=json.load(open('$RUN_DIR/evidence/tc-01-03-tools_list.json'));print({p:sum(1 for x in n if x.startswith(p)) for p in ('document_','query_','verify_','export_','sketch_','feature_','preview_','view_')})"` returns `document_: 7, query_: 8, verify_: 6, export_: 3, sketch_: 8, feature_: 11, preview_: 1, view_: 1`  
**And** the 13 read-only-profile names are all present — verify: `python -c "import json;n=set(json.load(open('$RUN_DIR/evidence/tc-01-03-tools_list.json')));ro={'query_capabilities','query_tree_summary','query_object','query_mass_properties','query_dependencies','query_sketch_info','query_placement','verify_shape','verify_sketch','verify_recompute','document_open','document_close','document_list'};print(ro<=n)"` returns `True`  
**And** every input schema is closed — verify: the same client run with `t.inputSchema.get('additionalProperties')` shows `False` for all 45 tools  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the advertised surface belongs to the window in front of the human — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-03-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one box-shaped solid inside the 3D view, whole, no edge cut off, and no dialog. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. A tool list is only worth something if the endpoint that produced it is driving this window.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```
```bash
rm -f "$RUN_DIR/evidence/tc-01-03-tools_list.json"
```

---

### TC-01-04: query_capabilities reports the live build honestly

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §2 (capability probes), `data-contracts-design.md` §9 (banner)

**Given** the FreeCAD GUI is the process serving the bridge — verify: the proxy pid from TC-01-01 is still alive  
**And** `FREECAD_BUDDY_ALLOW_EXEC` is unset and the **Allow debug_exec** preference is off — verify: `echo "${FREECAD_BUDDY_ALLOW_EXEC:-unset}"` returns `unset`, and the `operator settings:` line of this launch in `addon.log` contains `FREECAD_BUDDY_ALLOW_EXEC='0' (preference)`  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  

**When** the capability banner is read over MCP  
```
mcp query_capabilities {}
```
**And** the same facts are read from the running FreeCAD process, to cross-check rather than trust the banner  
```
cua-driver call invoke_menu { pid: <freecad pid>, window_id: <window id>, path: ["Help", "About FreeCAD"] }
```

**Then** the version matches the running build — verify: `structured_content.freecad_version` equals the version in the About dialog (`1.1.1`) and equals `grep "freecad_version" "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"`  
**And** every banner key is present — verify: the response keys are exactly `freecad_version`, `element_map_available`, `serializer`, `varset_backend`, `render`, `sketcher_available`, `partdesign_available`, `enums`, `exec_enabled`  
**And** `element_map_available` is a live boolean probe, not a constant — verify: the value is `true` or `false`, never null or a string  
**And** the serializer tag names the real serializer — verify: `structured_content.serializer` is a non-empty string  
**And** the render ladder reports a GUI mode under the GUI host — verify: `structured_content.render` is `"gui_constructed"` (a value of `"none"` means every screenshot checkpoint in TC-06 must be skipped, not failed)  
**And** exec is disabled by default — verify: `structured_content.exec_enabled` is `false`, and the same value appears in the handshake capabilities of `rpc-<freecad pid>.json`'s session  
**And** Sketcher and PartDesign report available in the GUI build — verify: `sketcher_available` and `partdesign_available` are both `true`  
**And** *(visual)* the About dialog is dismissed and the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window the banner claims to describe is a real GUI FreeCAD showing real geometry — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-04-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a FreeCAD main window with a 3D view area, one box-shaped solid inside it, whole and no edge cut off, and the About dialog gone. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-01-05: Per-tool timeout budgets match the catalog

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1 (per-tool budgets), `integration-mcp-freecad.md` §3 (marshal timeout)

**Given** the repo checkout matches the installed addon — verify: `ls -l "$APPDATA/FreeCAD/v1-1/Mod/FreeCADBuddy/freecad_buddy"` shows the symlink target under `src/`  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  

**When** every tool's declared timeout is dumped from the shipped catalog  
```bash
uv run python -c "
from freecad_buddy.hosts.tool_catalog import tool_specs
for s in sorted(tool_specs(), key=lambda s: s.name):
    print(f'{s.name}\t{s.timeout_s}\t{s.mutating}')
" | tee "$RUN_DIR/evidence/tc-01-05-budgets.txt"
```

**Then** only four distinct budgets exist — verify: the dump's timeout column has exactly the values `30.0`, `60.0`, `120.0`, `180.0`  
**And** `preview_dry_run` is the only 180 s tool — verify: `... | awk -F'\t' '$2==180.0'` returns exactly one row, `preview_dry_run`  
**And** the 30 s set is correct — verify: with `debug_exec` ungated the rows with `30.0` are exactly `document_create`, `document_close`, `document_list`, `query_capabilities`, `query_tree_summary`, `query_object`, `query_mass_properties`, `query_dependencies`, `query_sketch_info`, `query_placement`  
**And** the 60 s set is correct — verify: the rows with `60.0` are exactly `document_open`, `query_screenshot`, `verify_shape`, `verify_sketch`  
**And** every `sketch_*`, `feature_*`, and `export_*` tool is 120 s — verify: `... | awk -F'\t' '$1 ~ /^(sketch_|feature_|export_)/ && $2!=120.0'` returns nothing  
**And** the mutating flag agrees with the family — verify: every `query_*` and `verify_*` row has `mutating` `False`, and every `sketch_*`, `feature_*`, `export_*` row has `True`  
**And** document lifecycle tools are marked mutating even when they change no geometry — verify: `document_open` and `document_close` both report `mutating` `True`, because they open and close documents; this is why neither appears in a mutating-means-geometry reading of the catalog  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* reading the catalog disturbed nothing in the running application — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-05-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one box-shaped solid inside the 3D view, whole, no edge cut off, and no dialog or error popup raised by the catalog dump. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-01-06: Wrong contract_version is refused

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (handshake), `integration-mcp-clients.md` §2 (contract negotiation)

**Given** the discovery file for the live FreeCAD exists — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"`  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the undisturbed window is captured before the refusal — verify: the model is framed (`mcp view_fit_viewport { doc: "<handle>" }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-06-before.png"}' | & cua-driver call get_window_state`  

**When** a direct connection is made to the RPC listener with a valid token but an unsupported contract version  
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

**Then** the reply is a JSON-RPC error, not a result — verify: the printed frame has an `error` key and no `result` key  
**And** the error code is the version-mismatch code — verify: `error.code` is `-32004`  
**And** the message is verbatim — verify: `error.message` is exactly `contract version unsupported`  
**And** the supported list is disclosed to an authenticated caller — verify: `error.data` is `{"supported": ["1"]}`  
**And** no capabilities leak in the refusal — verify: the printed frame contains no `capabilities` and no `freecad_version` key  
**And** the connection is closed after the refusal — verify: a second `readline()` on the same socket returns an empty string  
**And** the listener survives the refusal — verify: `mcp query_capabilities {}` still returns `status: "OK"`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the refusal disturbed nothing in the window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-06-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen in each: the same one box-shaped solid, whole, no edge cut off, at the same size and position, and no dialog or error popup raised by the rejected handshake. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-01-07: Bad session token is refused before any disclosure

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (token authentication), `integration-mcp-clients.md` §2 (session token)

**Given** the discovery file for the live FreeCAD exists — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"`  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the undisturbed window is captured before the refusals — verify: the model is framed (`mcp view_fit_viewport { doc: "<handle>" }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-07-before.png"}' | & cua-driver call get_window_state`  

**When** a connection is made with a wrong token **and** an unsupported contract version at the same time. The listener authenticates before checking the version, so the reply must be the auth failure.  
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
**And** the same is repeated with the token field omitted entirely  

**Then** the error code is the auth-failure code — verify: `error.code` is `-32000`  
**And** the message is verbatim — verify: `error.message` is exactly `auth failed`  
**And** auth is checked **before** the version — verify: the reply is `-32000` / `auth failed`, **not** `-32004` / `contract version unsupported`, even though the version was also invalid  
**And** there is no capability disclosure to an unauthenticated caller — verify: the frame contains no `capabilities`, no `freecad_version`, and no `supported` list  
**And** the omitted-token case behaves identically — verify: the second attempt also returns `-32000` / `auth failed`  
**And** the refusal is logged — verify: `grep "token mismatch; closing" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns two lines (one per attempt)  
**And** the listener survives both refusals — verify: `mcp query_capabilities {}` still returns `status: "OK"`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* neither unauthenticated attempt disturbed the window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-07-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen in each: the same one box-shaped solid, whole, no edge cut off, at the same size and position, and no dialog or error popup raised by the two rejected handshakes. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-01-08: First frame that is not rpc_hello is refused

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (handshake required)

**Given** the discovery file for the live FreeCAD exists — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"`  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the undisturbed window is captured before the refusals — verify: the model is framed (`mcp view_fit_viewport { doc: "<handle>" }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-08-before.png"}' | & cua-driver call get_window_state`  

**When** a valid tool call is sent as the first frame, skipping the handshake  
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
**And** the same is repeated with a first frame that is not valid JSON at all, for example the bytes `not json\n`  

**Then** the error code is the no-handshake code — verify: `error.code` is `-32002`  
**And** the message is verbatim — verify: `error.message` is exactly `handshake required`  
**And** the request id is echoed — verify: the frame's `id` is `3`  
**And** the socket is closed immediately after the refusal — verify: `frame2` prints `''`  
**And** the tool never ran — verify: the frame carries no `result` and no `structured_content`  
**And** the refusal is logged — verify: `grep "first frame was not rpc_hello; closing" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line  
**And** the malformed-JSON case also refuses — verify: the second attempt returns `-32002` / `handshake required` with `id` `null`  
**And** the listener survives both — verify: `mcp query_capabilities {}` still returns `status: "OK"`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the skipped handshake never reached the application — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-08-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen in each: the same one box-shaped solid, whole, no edge cut off, at the same size and position, and no dialog or error popup raised by the two rejected frames. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-01-09: Discovery file is live and correct

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §1 (discovery), `integration-mcp-clients.md` §2 (attach)

**Given** FreeCAD is running with a known pid — verify: `cua-driver call list_windows {}` names the pid  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  

**When** the discovery record for the live FreeCAD pid is read  
```bash
cat "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json" | tee "$RUN_DIR/evidence/tc-01-09-discovery.json"
```
**And** its file mode is checked  
```bash
ls -l "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"
```

**Then** the file sits under the FreeCAD user appdata dir — verify: the path is `$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<pid>.json`; `$APPDATA/FreeCAD/Mod/` is legacy and empty  
**And** every field is present — verify: the record keys are exactly `schema`, `pid`, `host`, `port`, `token`, `contract_version`, `freecad_version`, `started`  
**And** `pid` names the live FreeCAD process — verify: the `pid` value equals the pid from `cua-driver call list_windows`, and `tasklist | grep <pid>` shows `freecad.exe`  
**And** `host` and `port` match a bound loopback socket — verify: `host` is `127.0.0.1` and `netstat -ano | grep "127.0.0.1:<port>"` shows `LISTENING` owned by that pid  
**And** `contract_version` is the supported version — verify: the value is `"1"`  
**And** `freecad_version` matches the live build — verify: the value equals `query_capabilities` `freecad_version` (`1.1.1`)  
**And** the token authenticates — verify: an `rpc_hello` using this `token` and `contract_version` returns a `result` carrying `capabilities`  
**And** the mode is restricted, best-effort on Windows — verify: `ls -l` shows `-rw-------` on POSIX. On Windows `chmod` only toggles the read-only bit, so record the observed mode and treat the loopback bind plus the per-session token as the enforced control; do not fail this assertion on Windows  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the pid in the record is the window in front of the human — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-09-after.png"}' | & cua-driver call get_window_state` using the pid read from the discovery file, then `Read` the PNG and say what is on screen: a FreeCAD main window with a 3D view area, one box-shaped solid inside it, whole and no edge cut off, and no dialog. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. A record naming a pid that cannot be captured, or that captures some other application's window, would mean the discovery file points at the wrong process.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-01-10: Discovery file is deleted on clean shutdown

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §1 (teardown)

**Given** the discovery file for the live pid exists — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"`  
**And** no unsaved document is open, so the quit does not raise a save dialog — verify: `mcp document_list {}` shows no document with `transient: true`  
**And** the proxy pid is recorded before the quit — verify: `grep "spawned MCP proxy" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"`  
**And** the live window is framed and captured before the quit — verify: fit through the GUI with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), which touches none of the code under test, then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-10-before.png"}' | & cua-driver call get_window_state`  

**When** FreeCAD is closed cleanly through its own menu, not by killing the process  
```
cua-driver call invoke_menu { pid: <freecad pid>, window_id: <window id>, path: ["File", "Exit"] }
```
**And** the process is waited for until it is gone  
```bash
tasklist | grep -i freecad.exe
```

**Then** FreeCAD exited — verify: `tasklist | grep -i freecad.exe` returns nothing  
**And** the discovery file is gone — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<freecad pid>.json"` reports no such file  
**And** the proxy child was terminated with the parent — verify: `tasklist | grep <proxy pid>` returns nothing  
**And** `:8765` is free — verify: `netstat -ano | grep :8765` returns nothing  
**And** no other pid's discovery file was deleted — verify: files named for other pids under `$APPDATA/FreeCAD/v1-1/freecad-buddy/` are unchanged in count  
**And** *(visual)* the window really closed — verify: `cua-driver call list_windows {}` lists no FreeCAD window, and `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-10-after.png"}' | & cua-driver call get_window_state` fails to capture the dead pid. No MCP fit is possible here and none is attempted: the quit removed the document, the camera, and the bridge, which is what the scenario asserts. The framing in the `Given` was done through **View → Fit All** for that reason. `Read` the before PNG and say what was on screen — a FreeCAD main window with a 3D view and a box-shaped solid inside it — then confirm that exact window is absent from the desktop now. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**: relaunch FreeCAD for the following scenarios.
```
cua-driver call launch_app { path: "$FREECAD_EXE" }
```

---

### TC-01-11: Stale discovery record from a dead pid fails fast

**Priority**: High
**Design Ref**: `integration-mcp-clients.md` §2 (attach and fail fast), `integration-mcp-freecad.md` §1 (discovery)

**Given** at least one discovery file names a pid that no longer exists — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/"rpc-*.json` lists more pids than `tasklist | grep -c freecad.exe`. An unclean kill leaves these behind, so the directory normally already holds several.  
**And** a golden model is open on the live FreeCAD so the closing visual has a subject — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the live window is framed and captured before the attach attempt — verify: the model is framed (`mcp view_fit_viewport { doc: "<handle>" }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-11-before.png"}' | & cua-driver call get_window_state`  

**When** a discovery file whose pid is dead is picked and an attach is attempted with a bounded timeout  
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

**Then** the named pid really is dead — verify: `tasklist | grep <dead pid>` returns nothing  
**And** the connect fails rather than hanging — verify: the script prints `refused:` with `ConnectionRefusedError` or `TimeoutError`, never a `reply:` line  
**And** it fails fast — verify: the printed `elapsed` is under the 5 s connect timeout  
**And** the stale file is not self-healing — verify: the file still exists after the failed attach; the listener only deletes its own record on clean shutdown  
**And** the live bridge is unaffected — verify: `mcp query_capabilities {}` still returns `status: "OK"`  
**And** a port reused by an unrelated process cannot be mistaken for the bridge — verify: if the connect **succeeds**, the reply must be an error rather than a `capabilities` result, because the stale token cannot authenticate against any other listener  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the failed attach on a dead pid left the live window untouched — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-11-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen in each: the same one box-shaped solid, whole, no edge cut off, at the same size and position, and no dialog or error popup raised by the refused connection. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**: leave the stale files. They are the input for a re-run of this scenario.
```
mcp document_close { doc: "<handle>" }
```

---

### TC-01-12: Proxy restart re-attaches to the same FreeCAD

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §1 (proxy is stateless over RPC), `integration-mcp-clients.md` §2 (HTTP endpoint)

**Given** FreeCAD is running and the bridge answers — verify: `mcp query_capabilities {}` returns `status: "OK"`  
**And** a document is open, so re-attachment can be proven against live state — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns a handle  
**And** the pre-restart window is framed and captured — verify: the model is framed (`mcp view_fit_viewport { doc: "<handle>" }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-12-before.png"}' | & cua-driver call get_window_state`  
**And** the proxy pid is recorded — verify: `netstat -ano | grep :8765`  

**When** **only** the proxy child is terminated. Do not touch the FreeCAD process.  
```bash
powershell -c "Stop-Process -Id <proxy pid>"
```
**And** `:8765` is confirmed free, then the proxy is started again with the same command the addon used  
```bash
".venv/Scripts/python.exe" -m freecad_buddy.hosts.main serve --mode rpc --transport http
```
**And** a query is re-issued against the handle minted before the restart  

**Then** FreeCAD survived the proxy kill — verify: `tasklist | grep <freecad pid>` still shows `freecad.exe`  
**And** the RPC listener stayed bound — verify: the discovery file `rpc-<freecad pid>.json` is unchanged, same `port` and same `token`  
**And** `:8765` is served again — verify: `netstat -ano | grep :8765` shows `LISTENING` on the new proxy pid  
**And** the restarted proxy reaches the same FreeCAD — verify: `mcp query_capabilities {}` returns the same `freecad_version` as before the restart  
**And** document handles survive — verify: `mcp query_tree_summary { doc: <handle minted before the restart> }` returns a first line starting `OK:`, because the handle registry lives in FreeCAD, not in the proxy  
**And** `document_list` still reports the open document — verify: `mcp document_list {}` lists the `box-10-20-30` label  
**And** *(visual)* the model is framed through the **restarted** proxy — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test, and record that the restarted proxy could not frame the shot  
**And** *(visual)* the restarted proxy drives the same window with the same document — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-12-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen in each: the same FreeCAD window, one box-shaped solid, whole, no edge cut off, and the same document label in the tree. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. A proxy that re-attached to a different FreeCAD, or to none, could not put this picture on this screen.  

**Cleanup**:
```
mcp document_close { doc: <handle> }
```

---

### TC-01-13: FREECAD_BUDDY_NO_AUTO_MCP suppresses the spawn, and the CLI contract holds

**Priority**: Medium
**Design Ref**: `integration-mcp-freecad.md` §1 (opt-out), `integration-mcp-clients.md` §2 (CLI surface)

**Given** FreeCAD is not running — verify: `tasklist | grep -i freecad.exe` returns nothing  
**And** `:8765` is free — verify: `netstat -ano | grep :8765` returns nothing  
**And** the addon log is rotated aside — verify: `mv "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log.prev"`  

**When** FreeCAD is launched with the opt-out set to a value that is **not** `"1"`, to prove the check is truthiness and not an equality test against `"1"`  
```
cua-driver call launch_app { path: "$FREECAD_EXE", env: { FREECAD_BUDDY_NO_AUTO_MCP: "no" } }
```
**And** the addon log is read  
```bash
cat "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"
```
**And** the two refused CLI combinations are exercised from the repo venv  
```bash
".venv/Scripts/python.exe" -m freecad_buddy.hosts.main serve --mode rpc; echo "exit=$?"
".venv/Scripts/python.exe" -m freecad_buddy.hosts.main serve --transport http --mode inline; echo "exit=$?"
```

**Then** the listener still started — verify: `grep "freecad-buddy RPC listener started on" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line, and `rpc-<pid>.json` exists  
**And** the proxy was not spawned — verify: `netstat -ano | grep :8765` returns nothing  
**And** the log states why, verbatim — verify: `grep "FREECAD_BUDDY_NO_AUTO_MCP set; not auto-starting the MCP proxy" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line  
**And** the check is truthiness, not `"1"` — verify: the two assertions above hold even though the value was `no`, a non-empty string that is not `1`  
**And** `--mode rpc` without `--transport http` exits 2 — verify: the first CLI command writes exactly `--mode rpc requires --transport http.` to stderr and `exit=2`  
**And** `--transport http --mode inline` is refused — verify: the second CLI command writes exactly `transport 'http' is not available yet; use --transport stdio.` to stderr and `exit=2`  
**And** neither refused command bound a port — verify: `netstat -ano | grep :8765` still returns nothing  
**And** *(visual)* the view is framed through the GUI only — verify: take a fresh `'{"pid":<freecad pid>,"window_id":<window id>}' | & cua-driver call get_window_state`, resolve the **Fit All** toolbar element's `element_token`, and click it; the response carries `route: "accessibility"` and the view reframes. The MCP fit is not available and must not be attempted: the suppressed proxy is the state under test, so the toolbar button is the only framing path, and it touches none of the code under test. Do **not** use `invoke_menu(["View","Fit All"])` — it is refused on FreeCAD 1.1.1 with `menu_path_unavailable` at segment 1.  
**And** *(visual)* the GUI came up normally despite the suppressed proxy — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-13-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a FreeCAD main window with its menu bar, tree panel, and a 3D view area, no error dialog, and no crash or splash screen left up. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image, and here no MCP endpoint exists to ask.  

**Cleanup**: restart FreeCAD without the variable so later scenarios get the auto-spawned proxy.
```
cua-driver call kill_app { pid: <freecad pid> }
cua-driver call launch_app { path: "$FREECAD_EXE" }
```
```bash
rm -f "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log.prev"
```

---

### TC-01-14: Unclean FreeCAD kill leaves no half-open bridge

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §1 (teardown), `integration-mcp-clients.md` §2 (attach failure)

**Given** FreeCAD is running and the bridge answers — verify: `mcp query_capabilities {}` returns `status: "OK"`  
**And** the FreeCAD pid, the RPC port from the discovery file, and the proxy pid are recorded  
**And** the live window is framed and captured before the kill — verify: fit through the GUI with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), which touches none of the code under test, then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-14-before.png"}' | & cua-driver call get_window_state`  

**When** the FreeCAD process is killed without letting it run its shutdown handlers. Use the cua-driver tool, not `taskkill /F` from a shell.  
```
cua-driver call kill_app { pid: <freecad pid> }
```
**And** a connection to the RPC port recorded before the kill is attempted  
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
**And** one MCP call is attempted through the endpoint  

**Then** FreeCAD is gone — verify: `tasklist | grep <freecad pid>` returns nothing  
**And** the RPC port no longer accepts — verify: the connect attempt prints `refused:` and never `connected`  
**And** the failure is fast, not a hang — verify: the printed `elapsed` is under the 5 s connect timeout  
**And** the proxy exits once its FreeCAD is gone — verify: within 5 s of the kill, `tasklist | grep <proxy pid>` returns nothing and `netstat -ano | grep :8765` shows no `LISTENING` row. The proxy pid is the `LISTENING` pid on `:8765` recorded in the `Given`.  
**And** the proxy logs its exit once — verify: `grep -c "FreeCAD pid <freecad pid> has exited; the MCP proxy exits and frees port 8765" "$APPDATA/FreeCAD/v1-1/freecad-buddy/mcp-proxy.log"` prints `1`. Read the log before the relaunch: the new proxy rewrites it.  
**And** the kill leaves a stale discovery file, matching the shipped behaviour — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<killed pid>.json"` still lists the file. A clean exit deletes it (TC-01-10); an unclean kill does not. Record this as observed state, not a defect.  
**And** a fresh launch is not blocked by the stale state — verify: relaunching FreeCAD writes a new `rpc-<new pid>.json` and `:8765` returns to `LISTENING`  
**And** the relaunched FreeCAD is served by its own new proxy, not by an adopted one — verify: `curl -s http://127.0.0.1:8765/healthz` returns `200` with `"service": "freecad-buddy-mcp-proxy"` and `"freecad_pid"` equal to the new FreeCAD pid, the `LISTENING` pid on `:8765` differs from the killed session's proxy pid, and the new session's `addon.log` lines hold no `MCP proxy not started` ERROR  
**And** the new session mints a different token — verify: the `token` in the new discovery file differs from the killed session's token, and the old token no longer authenticates  
**And** *(visual)* a golden model is opened in the **relaunched** FreeCAD and framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. The killed session has no MCP surface left, so the pre-kill framing in the `Given` was done through the GUI menu for that reason.  
**And** *(visual)* the killed window is gone and the relaunched one is healthy — verify: `'{"pid":<new pid>,"window_id":<new wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-14-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen in each: the before PNG shows the killed session's FreeCAD window with its 3D view; the after PNG shows a FreeCAD window on the new pid with one box-shaped solid inside the view, whole, no edge cut off, and no crash dialog or recovery prompt left up. The killed pid must not capture at all. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```
```bash
rm -f "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<killed pid>.json"
```

---

### TC-01-15: The proxy serves /healthz, and the addon never adopts a foreign server on :8765

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3.1 (proxy identity and the already-served check), AD-2, AD-24

**Given** FreeCAD is running with its auto-spawned proxy — verify: `netstat -ano | grep :8765` shows `LISTENING`, and the FreeCAD pid and the `token` from `rpc-<freecad pid>.json` are recorded  
**And** a golden model is open as an untouched baseline — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-15-before.png"}' | & cua-driver call get_window_state`  

**When** the health route is probed  
```bash
curl -s -i http://127.0.0.1:8765/healthz
```

**Then** `/healthz` answers — verify: the status line is `HTTP/1.1 200 OK` and the body is JSON  
**And** the body names the proxy and its FreeCAD — verify: `"service"` is `"freecad-buddy-mcp-proxy"` and `"freecad_pid"` equals the recorded FreeCAD pid  
**And** the body carries a session id and no secret — verify: `"session_id"` is a non-empty string, the recorded `token` does not occur anywhere in the response, and the body holds no path and no environment value  
**And** *(visual)* the probe left the baseline unchanged — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-15-probed.png"}' | & cua-driver call get_window_state`, then `Read` it beside the before PNG and say what is on screen: the same box, whole, at the same size and position, with no dialog raised. The judgement is on the pixels alone.  

**When** the document is closed and FreeCAD is closed cleanly  
```
mcp document_close { doc: "<handle>" }
cua-driver call invoke_menu { pid: <freecad pid>, window_id: <window id>, path: ["File", "Exit"] }
```
**And** `:8765` is held by an unrelated HTTP server, and the addon log is moved aside  
```bash
netstat -ano | grep :8765        # must return nothing first
uv run python -m http.server 8765 --bind 127.0.0.1 &
netstat -ano | grep ":8765.*LISTENING"   # record the last column: the Windows pid that holds the port
mv "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log.prev"
```
**And** FreeCAD is launched and the addon log is read after 15 s, past the addon's 10 s wait for the port to free  
```
cua-driver call launch_app { path: "$FREECAD_EXE" }
```
```bash
cat "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"
```

**Then** the addon reports the foreign holder once — verify: `grep -c "ERROR" addon.log` prints `1`, and that line contains `MCP proxy not started: port 8765 is still held by another program`  
**And** no proxy was spawned — verify: `grep "spawned MCP proxy" addon.log` returns nothing, and `netstat -ano | grep :8765` shows `LISTENING` only on the holder pid recorded from `netstat`  
**And** the RPC listener is up — verify: `grep "freecad-buddy RPC listener started on" addon.log` returns a line, and `rpc-<new freecad pid>.json` exists  
**And** *(visual)* the GUI came up normally despite the foreign holder — verify: `'{"pid":<new pid>,"window_id":<new wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-01-15-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a FreeCAD main window with its menu bar, tree panel and 3D view, no port-conflict dialog, no addon-failure popup, and no `Not Responding` in the title bar. The judgement is on the pixels alone; no MCP endpoint of this FreeCAD exists to ask.  

**Cleanup**: stop the process that holds `:8765`, then restart FreeCAD so later scenarios get the auto-spawned proxy. Use the Windows pid from `netstat`; the shell's `$!` names the `uv` wrapper, not the python child that holds the port.
```bash
powershell -c "Stop-Process -Id <holder pid> -Force"
netstat -ano | grep ":8765.*LISTENING"   # must return nothing
rm -f "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log.prev"
```
```
cua-driver call kill_app { pid: <new freecad pid> }
cua-driver call launch_app { path: "$FREECAD_EXE" }
```
