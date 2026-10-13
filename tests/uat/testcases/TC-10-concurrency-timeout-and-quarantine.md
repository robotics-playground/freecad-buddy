# TC-10: Concurrency, Timeout Budget & Document Quarantine

Validates what the bridge does when a call runs longer than its budget, when a second client
arrives, and when the transport dies mid-call. The rule under test is AD-27: a marshal timeout
returns `TIMEOUT`, the operation body may still be running, and the bridge NEVER re-issues the
mutation. AD-24's latency budget is measured here too. Two hosts exist and they do NOT behave
alike — every scenario names which one it targets.

We are BUILDING the MCP bridge, so the bridge's own output can never be the test result. Every
`status`, envelope field and `query_screenshot` render in this file is a claim under test. The
result is the `cua-driver` pixel capture of the real FreeCAD window, `Read` and judged by the
agent. This matters more here than anywhere else in the suite: a bridge that returns a clean
`TIMEOUT` envelope while the human's FreeCAD sits frozen mid-operation passes every numeric
assertion below and fails the user completely. Commit `636fb8a` fixed that exact class of defect.

**Host divergence (applies to the whole file).** The H1 host is two processes. Its front
(`hosts/headless/entry.py`) serves MCP over stdio through `build_server`
(`adapters/mcp_server.py:239-292`), which carries the document-suspect set, the non-string-`doc`
guard and the audit writes. The front's `WorkerClient` (`entry.py:86-127`) bounds every call with
the method `timeout_s` and holds the session quarantine (AD-27). Its worker
(`hosts/headless/worker.py`) runs FreeCAD and an RPC listener on its main thread. The H2 GUI proxy
(`hosts/gui_external/entry.py:62-66`) has its own `_call_tool` that only dispatches and wraps.
Behind it, the in-FreeCAD listener (`adapters/rpc_listener.py:410-424`) carries its own
non-string-`doc` guard and suspect set, with DIFFERENT wording, and has no session quarantine.

**Host**: H1 (stdio, front plus worker) for the serialization, budget, timeout and quarantine
scenarios (TC-10-01, TC-10-02, TC-10-05, TC-10-07..TC-10-11); the in-FreeCAD RPC listener for the
client-session and framing scenarios (TC-10-01, TC-10-03, TC-10-04, TC-10-06, TC-10-13,
TC-10-14); the H2 GUI proxy plus the listener for TC-10-12. Every scenario's closing visual is
captured from the live FreeCAD GUI window with `cua-driver`. The H1 documents live in another
process and never appear in the GUI window, so an H1 scenario's GUI capture shows a golden model
`<G>` opened in the GUI as an untouched subject.

## Preconditions

- [ ] FreeCAD 1.1.x installed (verify: `ls "$FREECAD_EXE"`); the build under test is the live version: `query_capabilities.freecad_version`, read once at the start of the run and written `<live version>` below
- [ ] Golden and fault `.FCStd` files have no `GuiDocument.xml` and open with every object hidden. After each `document_open` of such a file, and before any fit or render of it, run **Show All**: `cua-driver call invoke_menu { pid, window_id, path: ["View","Visibility","Show All Objects"] }`. A fit before it returns `SPEC_FAILED view_fit.nothing_to_frame`.
- [ ] The H1 host starts as `"$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline`; its front spawns the worker with the same interpreter (`sys.executable`). The worker pid is the child of the front whose command line ends `-m freecad_buddy.hosts.headless.worker`
- [ ] micromamba `fcb` env is H1-capable (verify: `"$FCB_PYTHON" -c "import FreeCAD, mcp"`)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)
- [ ] For the H2 scenarios only: FreeCAD GUI running with the addon loaded (verify: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/mcp` returns a non-`000` code)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)
- [ ] `cua-driver` can drive the FreeCAD window and invoke its menus (verify: `cua-driver call list_windows` reports the `pid` and `window_id`, and click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`) returns without error)

---

### TC-10-01: One client's calls are strictly serialized

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §2.4 (single marshal), `component-design.md` §RPC listener

**Host**: H1 (stdio, front plus worker) and the in-FreeCAD listener.

**Given** no stale H1 server holds the golden files — verify: `ls "$RUN_DIR/evidence"/*.lock 2>/dev/null` returns nothing  
**And** a golden model is open in the GUI so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-01-before.png"}' | & cua-driver call get_window_state`  

**When** the happy-path sweep is run on its own H1 host, and its report and server stderr are copied from `_automation/`, where the sweep writes them  
```bash
uv run python scripts/automation/run_mcp_e2e.py
cp _automation/e2e_report.json "$RUN_DIR/evidence/tc-10-01-e2e_report.json"
cp _automation/server.stderr.log "$RUN_DIR/evidence/tc-10-01-server.stderr.log"
```
**And** on one H1 connection, one golden model is opened and six reads are issued back to back by a client script that records each call's entry and exit time in `$RUN_DIR/evidence/tc-10-01-six-spans.json` as `[{"tool", "start", "end", "status"}]`. The sweep report carries no per-call times, so the script times the calls itself  
**And** the per-call ordering is read out of the sweep report  
```bash
python3 -c "import json;r=json.load(open('$RUN_DIR/evidence/tc-10-01-e2e_report.json'));print([c['tool'] for c in r['checks']])"
```

**Then** every call returned before the next one started — verify: the `[start, end]` spans in `$RUN_DIR/evidence/tc-10-01-six-spans.json` do not overlap, and each of the six has `status` `OK`  
**And** results arrive in request order — verify: the `tool` sequence in `tc-10-01-six-spans.json` equals the order the script sent them, and the sequence printed from the sweep report matches the request sequence in `scripts/automation/run_mcp_e2e.py`  
**And** exactly one marshal call per request — verify: `grep -c "marshal" "$RUN_DIR/evidence/tc-10-01-server.stderr.log"` shows no nested-call warnings  
**And** the sweep gate is green — verify: `python3 -c "import json;print(json.load(open('$RUN_DIR/evidence/tc-10-01-e2e_report.json'))['all_passed'])"` returns `True`  
**And** no interleaving traceback — verify: `grep -iE "reentrant|deadlock|already in marshal" "$RUN_DIR/evidence/tc-10-01-server.stderr.log"` returns nothing  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — record it as the finding.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after the serialized sweep settled — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-01-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and one whole box is drawn and framed in the viewport — not blank, not half-painted, and with no duplicated or half-applied geometry from the six back-to-back reads. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# The sweep writes its exports under _automation/; delete nothing in $RUN_DIR/evidence; other scenarios keep their files there.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-10-02: Read-only latency budget (AD-24)

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §7 (latency budget), `mcp-tools-design.md` §timeouts

**Host**: H1 (stdio, front plus worker).

The measurement point is tool-call entry to envelope return, not wall time of the whole sweep.
The budget is median <= 15 s over the read-only profile. The per-tool marshal timeouts are
larger (30 s for most `query_*`, 60 s for `query_screenshot` / `verify_shape` / `verify_sketch`,
120 s for `verify_recompute`) — the budget is a performance assertion, the timeout is a contract.

**Given** golden models are present — verify: `ls benchmarks/g0/golden-models/*.FCStd | wc -l` is >= 5  
**And** a golden model is open in the GUI so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-02-before.png"}' | & cua-driver call get_window_state`  

**When** the happy-path sweep is run, and its report is copied from `_automation/`  
```bash
uv run python scripts/automation/run_mcp_e2e.py
cp _automation/e2e_report.json "$RUN_DIR/evidence/tc-10-02-e2e_report.json"
```
**And** a client script times every read-only call, from tool-call entry to envelope return, on one H1 connection over the 5 golden models, and writes `[{"tool", "duration_s", "status"}]` to `$RUN_DIR/evidence/tc-10-02-latency.json`. The sweep report carries no per-call durations, so the script times the calls itself  
**And** the median duration over the read-only tools is computed  
```bash
python3 -c "import json,statistics;d=[c['duration_s'] for c in json.load(open('$RUN_DIR/evidence/tc-10-02-latency.json')) if c['tool'].startswith(('query_','verify_','document_list'))];print(len(d), statistics.median(d))"
```

**Then** the median read-only call is at or under 15 s — verify: the second number printed by the median command is `<= 15.0`  
**And** at least 8 read-only calls were sampled — verify: the first number printed by the median command is `>= 8`  
**And** no read-only call returned `TIMEOUT` — verify: `grep -c '"status": "TIMEOUT"' "$RUN_DIR/evidence/tc-10-02-latency.json" "$RUN_DIR/evidence/tc-10-02-e2e_report.json"` returns `0` for both files  
**And** `query_screenshot` stayed inside its own 60 s budget — verify: the `query_screenshot` entries in the latency file show `status` `OK` and `duration_s` below `60`  
**And** no call exceeded its declared `timeout_s` — verify: each check's `duration_s` is below the tool's timeout in `src/freecad_buddy/hosts/tool_catalog.py`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — record it as the finding.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after the budget sweep settled — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-02-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and one whole box is drawn and framed — not blank, not half-painted, and not frozen mid-render by the sweep. A median under 15 s reported by the bridge while the window is dead is the defect this catches. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Keep tc-10-02-*.png: they are this scenario's visual evidence.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-10-03: A second client while a session is active is refused busy

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3.2 (accept thread, busy refusal), §7 (FreeCAD busy), spine AD-26

**Host**: the in-FreeCAD RPC listener, with the addon's MCP proxy as the active session.

AD-26: the bridge serves one client session at a time. The listener's accept thread runs every
handshake, so a second client that authenticates while a session is active gets JSON-RPC `-32000`
with the message `bridge busy: another client session is active`, and its connection is closed.
Authentication runs first: a wrong token gets `auth failed`, never the busy message.

**Given** the FreeCAD GUI is running with the addon loaded  
**And** the discovery file is readable — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-"*.json`  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle. This call also makes the proxy connect, and it keeps that connection as the active session  
**And** the proxy holds the session — verify: `netstat -ano | findstr <listener-port>` shows one `ESTABLISHED` pair owned by the proxy pid  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-03-before.png"}' | & cua-driver call get_window_state`  

**When** the host, port and token are read from the discovery file  
```bash
python3 -c "import glob,json,os;p=glob.glob(os.path.expandvars(r'%APPDATA%/FreeCAD/v1-1/freecad-buddy/rpc-*.json'))[0];r=json.load(open(p));print(r['host'],r['port'],r['token'])"
```
**And** client B opens a TCP connection to that port, sends a valid `rpc_hello`, and records the time until the first reply frame arrives  
**And** client C opens a TCP connection to that port and sends `rpc_hello` with a wrong token  
**And** a `document_list` is issued through the proxy — `mcp document_list {}`  

**Then** B's TCP connect succeeds immediately — verify: `socket.create_connection((host, port), timeout=5)` returns without raising  
**And** B is refused busy within 1 s — verify: B's first frame carries `"error": {"code": -32000, "message": "bridge busy: another client session is active"}` and arrived less than 1 s after B sent its hello  
**And** B's connection is closed by the listener — verify: B's next `recv` returns zero bytes  
**And** C is refused for its token, not for the session — verify: C's first frame carries `"error": {"code": -32000, "message": "auth failed"}`  
**And** the session was undisturbed — verify: `mcp document_list {}` returns `OK` and lists the handle  
**And** the listener logged the refusal and no crash — verify: `grep -c "refused a second client: a session is active" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` is at least 1, and `grep -i "connection handler crashed\|handshake crashed" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns nothing  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — record it as the finding.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after the refusals — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-03-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and one whole box is drawn and framed at the same size and position as in the before image — not blank and not half-painted. A refused second client must never freeze the human's window. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Close the test sockets; no files are written.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-10-04: A second client after the first disconnects must handshake afresh

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §2.4 (handshake), `security-and-service-design.md` §2 (session token)

**Host**: the in-FreeCAD RPC listener.

**Given** the MCP proxy is stopped so the raw client is the only session — a raw `rpc_hello` while the proxy holds the session gets `-32000 bridge busy: another client session is active` (AD-26). Verify: `netstat -ano | grep ":<port>" | grep ESTABLISHED` returns nothing  
**And** before the proxy is stopped, a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-04-before.png"}' | & cua-driver call get_window_state`  

**When** client A connects, sends `rpc_hello` with the discovery token, runs `document_list`, disconnects  
**And** client B connects and sends `document_list` as its FIRST frame, with no `rpc_hello`  
**And** client C connects, sends a correct `rpc_hello`, then `document_list`  

**Then** A's handshake is accepted — verify: A reads a result carrying `contract_version`, `freecad_version` and `capabilities`  
**And** B is refused for skipping the handshake — verify: B reads an error frame with `message` exactly `handshake required`  
**And** B's connection is closed by the listener — verify: B's next `recv` returns zero bytes  
**And** C's fresh handshake succeeds — verify: C reads a result carrying `contract_version` equal to `"1"`  
**And** C's `document_list` returns `OK` — verify: the envelope `status` field is `OK`  
**And** refusing B did not stop the accept loop — verify: C connected AFTER B was refused and was served  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — record it as the finding.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after the three sessions settled — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-04-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal or error popup is stuck on screen from the refused handshake, and one whole box is drawn and framed — not blank and not half-painted. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Restart the proxy by hand with the addon's command line (from Win32_Process.CommandLine of the spawned proxy), setting on that command each FREECAD_BUDDY_* value from the last operator settings: line of addon.log. A hand-started proxy reads only the shell's environment (gui_external/entry.py:142), not the addon's preference overlay, so without those values its exec_enabled and tool count can differ from FreeCAD's posture. When the run uses a non-default posture, restart FreeCAD instead, then: mcp query_capabilities {} returns OK
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-10-05: A long-running operation does not starve the listener

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §7 (budget), `mcp-tools-design.md` §5 (preview)

**Host**: H1 (stdio, front plus worker). `preview_dry_run` carries the largest budget in the surface: 180 s, and the front waits that long for the worker's reply.

**Given** a document with a body that takes a measurable time to recompute is open on the H1 host — record the handle  
**And** a golden model is open in the GUI as `<G>`, framed, and captured, so the GUI capture has an untouched subject; the H1 document lives in another process and never appears in the GUI — verify: run Show All, then `mcp view_fit_viewport { doc: "<G>" }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test, then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-05-before.png"}' | & cua-driver call get_window_state`  

**When** a `preview_dry_run` whose operation takes roughly 100 s to recompute is issued, and the connection is held open for its whole duration  
**And** nothing else is issued on the same connection while it runs  
**And** when it returns, a `document_list` is issued on the same connection  

**Then** the preview returns a terminal envelope, not a dropped connection — verify: one envelope frame is read with `status` in the closed set  
**And** the call was not cut at a shorter budget — verify: the measured duration is above 60 s and the status is not `TIMEOUT`  
**And** the connection survived — verify: the following `document_list` returns `status=OK` on the SAME socket  
**And** no keepalive or idle-timeout close was logged — verify: `grep -iE "timed out|connection reset" "$RUN_DIR/evidence/tc-10-05-server.stderr.log"` returns nothing  
**And** the preview TempDoc was cleaned up — verify: `document_list` on the H1 connection shows no handle whose name starts with `FCB_TMP_prev_`, and the H1 session temp folder `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/` (H1 workdir: `FREECAD_BUDDY_WORKDIR`, else `./freecad-buddy-workdir` under the host's working folder; `<pid>` is the worker pid) holds no `FCB_TMP_prev_*` entry  
**And** *(visual)* the GUI subject is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<G>" }` over the GUI proxy returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — after a 100 s call held the connection open, that is exactly the outcome this scenario must not silently pass.  
**And** *(visual)* the FreeCAD window is alive and unchanged after the 100 s H1 call — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-05-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no progress modal is stuck on screen, and `<G>` is drawn whole and framed — not blank, not half-painted, and unchanged: the H1 worker is a separate process, so the long preview must not reach the GUI window. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Nothing to delete: the preview removes its own TempDoc folder on every path (preview.py:336).
```
```
mcp document_close { doc: "<handle>" }
mcp document_close { doc: "<G>" }
```

---

### TC-10-06: Handles survive a session change on the same FreeCAD

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (handles), `security-and-service-design.md` §2 (session scope), sprint-change-proposal-2026-10-04 decision 2

**Host**: the in-FreeCAD RPC listener.

The bridge keeps one process-wide document registry (`usecases/documents.py`, `DocumentRegistry`),
so a handle names a document in that FreeCAD, not in one client session. TC-01-12 depends on this:
a handle must survive a proxy reconnect. Sprint-change-proposal-2026-10-04 decision 2 keeps this
product behaviour, so this scenario asserts it.

**Given** the GUI has at least one document open  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test, then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-06-before.png"}' | & cua-driver call get_window_state`  
**And** the MCP proxy is stopped so the raw client is the only session — a raw `rpc_hello` while the proxy holds the session gets `-32000 bridge busy: another client session is active` (AD-26). Verify: `netstat -ano | grep ":<port>" | grep ESTABLISHED` returns nothing  

**When** session A connects with `rpc_hello`, opens `cylinder-r5-h20.FCStd`, and the handle it returns is recorded  
**And** A disconnects, and session B connects with a fresh `rpc_hello`  
**And** session B calls `query_object` using session A's handle verbatim  
**And** session B calls `document_list` and the handles it reports are compared  
**And** session B closes the cylinder with A's handle  

**Then** session A's open returned a handle — verify: the `document_open` envelope carries a non-empty handle string  
**And** session B reads A's handle — verify: the `query_object` envelope `status` is `OK` and names the cylinder object  
**And** the result is a closed-set envelope — verify: the envelope has `schema` equal to `fcb.result-envelope/1`  
**And** session B's own `document_list` contains A's handle — verify: the returned handle list includes the recorded string  
**And** session B can close it — verify: `document_close` with A's handle returns `OK`, and a following `document_list` on B returns `status=OK` without it  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — record it as the finding.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after both sessions settled — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-06-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and the golden box is drawn whole and framed — not blank and not half-painted. The session change must have closed no document but the cylinder and disturbed no view. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Restart the proxy by hand with the addon's command line (from Win32_Process.CommandLine of the spawned proxy), setting on that command each FREECAD_BUDDY_* value from the last operator settings: line of addon.log. A hand-started proxy reads only the shell's environment (gui_external/entry.py:142), not the addon's preference overlay, so without those values its exec_enabled and tool count can differ from FreeCAD's posture. When the run uses a non-default posture, restart FreeCAD instead, then: mcp query_capabilities {} returns OK
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-10-07: A budget overrun returns TIMEOUT and quarantines the session

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §2.4 (H1 bound and quarantine), §7 (timeout), spine AD-27

**Host**: H1 (stdio, front plus worker). The front waits for the worker's reply for at most the
method `timeout_s` (`hosts/headless/entry.py:115-127`). There is NO preemption: on a timeout the
front returns `TIMEOUT` and the body runs on in the worker. Until that body returns, the front
refuses every call on any handle without dispatch (`entry.py:111-113`). Past twice the budget the
refusal becomes `WORKER_CRASHED` (`_AbandonedCall.refusal`, `entry.py:67-83`); the front never
ends the worker, and the session is served again once the body returns.

**Given** an H1 host is started with its audit log and stderr captured, and one MCP stdio client keeps the session open through TC-10-11  
```bash
FREECAD_BUDDY_AUDIT_LOG="$RUN_DIR/evidence/tc-10-07-audit.jsonl" \
  "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline \
  2> "$RUN_DIR/evidence/tc-10-07-server.stderr.log"
```
**And** `script_exec` is on, the default posture — verify: `tools/list` on that session includes `script_exec`  
**And** the golden box is open on H1 as `D` and `cylinder-r5-h20.FCStd` as `E` — verify: both `document_open` calls return `OK`; record both handles  
**And** the worker pid is recorded — verify: the child of the H1 front whose command line ends `-m freecad_buddy.hosts.headless.worker`  
**And** a golden model is open in the GUI as `<G>`, framed, and captured, so the GUI capture has an untouched subject — verify: run Show All, then `mcp view_fit_viewport { doc: "<G>" }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test, then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-07-before.png"}' | & cua-driver call get_window_state`  

**When** a mutating `script_exec` on `D` whose body spends about 75 s in FreeCAD C++ calls is issued; its budget is 30 s  
```
mcp script_exec { doc: <D>, code: "import time, Part\nend = time.monotonic() + 75\nwhile time.monotonic() < end:\n    Part.makeBox(10, 10, 10).fuse(Part.makeSphere(6))\nresult = 'done'" }
```
**And** the returned envelope is read in full and its elapsed time recorded  
**And** the worker's CPU time is read twice, 3 s apart, right after the envelope arrives: `powershell -NoProfile -Command "(Get-Process -Id <worker pid>).CPU"`  
**And** within 5 s of that envelope, `mcp query_tree_summary { doc: <E> }` is issued and its elapsed time recorded  
**And** about 65 s after the first call started, `mcp query_tree_summary { doc: <E> }` is issued again  
**And** about 85 s after the first call started, when the body has returned, `mcp query_tree_summary { doc: <E> }` is issued once more  

**Then** the envelope status is `TIMEOUT` within the budget plus 1 s — verify: the returned `status` field is exactly `TIMEOUT` and the elapsed time is between 30 s and 31 s  
**And** the timeout is flagged as a marshal timeout — verify: `detail.data.marshal_timeout` is `true`  
**And** the envelope says the body may still be running — verify: `detail.data.maybe_still_running` is `true`  
**And** the message names the budget and the consequence — verify: `detail.message` contains `did not answer script_exec within its 30 s budget` and `the document is now suspect: do not blind-retry, run a query_* read first to confirm `  
**And** the call was NOT preempted — verify: the worker's CPU time grew between the two reads  
**And** the next call is refused without dispatch, at once — verify: the first `query_tree_summary` on `E` returns in under 1 s with `status` `TIMEOUT`, `detail.data.quarantined` `true`, no `marshal_timeout` key, and a message starting `not dispatched: the session is quarantined while a timed-out script_exec call still runs in the headless worker`  
**And** past twice the budget the refusal escalates — verify: the second `query_tree_summary` returns `status` `WORKER_CRASHED`, `detail.data.quarantined` `true`, and a message containing `has run past twice its 30 s budget` and `restart the headless host`  
**And** the front did not end the worker — verify: `Get-Process -Id <worker pid>` still finds the worker after the escalation  
**And** the session is served again once the body returns — verify: the third `query_tree_summary` returns `status` `OK`  
**And** the timeout was audit-logged — verify: `grep '"verify_verdict": "TIMEOUT"' "$RUN_DIR/evidence/tc-10-07-audit.jsonl"` returns at least one line whose `tool` is `script_exec`  
**And** *(visual)* no fit is performed on `D` here, by either route: `D` is now suspect, and a fit is a mutating call the suspect rule must refuse. The `before.png` was framed in the `Given` so the two images already share a camera.  
**And** *(visual)* the FreeCAD window is alive and unchanged by the H1 timeout — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-07-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and `<G>` is drawn whole — not blank, not half-painted, and not frozen. The H1 worker is a separate process, so the GUI window must not change. A correct `TIMEOUT` envelope over a frozen FreeCAD window is the exact defect class commit `636fb8a` fixed, and every numeric `Then` above would still pass. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Keep the H1 session open: TC-10-08 to TC-10-11 use it. D stays suspect for TC-10-08.
```

---

### TC-10-08: A timed-out mutation leaves its document suspect

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §7 (document-suspect), `data-contracts-design.md` §3 (INVALID_INPUT), spine AD-27

**Host**: H1 front ONLY (`adapters/mcp_server.py:264-271`). Two rules apply after a timeout. While
the abandoned body runs, the session quarantine refuses every call on every handle (TC-10-07).
After the body returns, the document-suspect rule refuses only mutations on the document whose
mutation timed out. The in-FreeCAD listener behind H2 enforces the suspect rule with different
wording (`adapters/rpc_listener.py:420-424`): `document-suspect: a prior call timed out on this
document; run a query_* read to confirm state before mutating`. The H2 proxy adds no rule of its
own.

**Given** TC-10-07 has just run on the same H1 session, and its abandoned body has returned — verify: the last `query_tree_summary` of TC-10-07 returned `OK`  
**And** document `D` is marked suspect by the timed-out `script_exec` of TC-10-07  
**And** the GUI window's current state is captured before the attempt, with no fit of any kind — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-08-before.png"}' | & cua-driver call get_window_state`  

**When** a second MUTATING call is issued on the same document handle `D`; its body would write a marker file  
```
mcp script_exec { doc: <D>, code: "open(r'$RUN_DIR/evidence/tc-10-08-D.marker', 'w').write('x'); result = 'ran'" }
```
**And** the returned envelope is read  
**And** the same mutating call is issued on the DIFFERENT document handle `E`, writing `tc-10-08-E.marker`  

**Then** the second mutation on `D` is refused — verify: the returned `status` is `INVALID_INPUT`  
**And** the refusal names the suspect rule — verify: `detail.message` starts with `document-suspect: a prior call timed out on this document and its body may `  
**And** the message tells the operator what to do — verify: `detail.message` contains `run a query_* read to confirm the document still responds `  
**And** the refusal happened WITHOUT dispatching — verify: `ls "$RUN_DIR/evidence/tc-10-08-D.marker"` reports no such file, and `tc-10-07-server.stderr.log` gained no worker line for the refused call  
**And** the refusal is still audit-logged — verify: `grep '"verify_verdict": "INVALID_INPUT"' "$RUN_DIR/evidence/tc-10-07-audit.jsonl"` returns a line whose `tool` is `script_exec`  
**And** the suspect rule is per document — verify: the call on `E` returns `OK` and `tc-10-08-E.marker` exists. While the TC-10-07 body ran, a call on `E` was refused too, but by the session quarantine (`TIMEOUT` with `quarantined:true`), not by `document-suspect`  
**And** the H2 proxy adds no rule of its own — verify: `grep -c "document-suspect" src/freecad_buddy/hosts/gui_external/entry.py` returns `0`, and `grep -n "document-suspect" src/freecad_buddy/adapters/rpc_listener.py` shows the listener's own wording  
**And** *(visual)* no fit is performed first here, by either route: the GUI window must stay exactly as it was, so the before and after images can be compared without a camera move  
**And** *(visual)* the FreeCAD window is alive and visually unchanged by the refused mutation — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-08-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and the viewport is the same scene as the before image. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-10-08-E.marker"
# Leave D suspect; TC-10-09 clears it.
```

---

### TC-10-09: The document-suspect flag clears only via a non-mutating OK

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §7 (document-suspect clearing), `mcp-tools-design.md` §read-only profile

**Host**: H1 front (`adapters/mcp_server.py:286-287`: clear only when the method is known, not
mutating, and the envelope status is `OK`).

**Given** document `D` is still suspect from TC-10-08, on the same H1 session  
**And** the abandoned body of TC-10-07 has returned, so the session quarantine is lifted and only the document-suspect rule applies — verify: a `query_tree_summary` on `E` returns `OK`  
**And** the window's current state is captured before the attempts, with no fit of any kind, since `D` is still suspect — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-09-before.png"}' | & cua-driver call get_window_state`  

**When** a read-only call on `D` that FAILS is issued, for example `query_object` naming an object that does not exist  
**And** a mutating call is issued on `D` again: `mcp script_exec { doc: <D>, code: "open(r'$RUN_DIR/evidence/tc-10-09-D.marker', 'w').write('x'); result = 'ran'" }`  
**And** a read-only call on `D` that SUCCEEDS is issued, for example `query_tree_summary`  
**And** a mutating call is issued on `D` once more; it also adds a 5 mm cube, so the GUI check has a visible effect: `mcp script_exec { doc: <D>, code: "b = doc.addObject('Part::Box', 'QuarantineCleared'); b.Length = b.Width = b.Height = 5; b.Placement.Base.x = 15; doc.recompute(); result = 'ran'" }`  

**Then** the failing read returns `INVALID_INPUT` — verify: the first call's envelope `status` is `INVALID_INPUT`  
**And** a failing read does NOT clear the suspect flag — verify: the second call's mutation is still refused with `document-suspect: a prior call timed out on this document and its body may `  
**And** the passing read returns `OK` — verify: the third call's envelope `status` is `OK`  
**And** the passing read clears the suspect flag — verify: the fourth call's mutation is no longer refused with `document-suspect`  
**And** a mutation can never clear it — verify: the second call's refusal did not remove `D` from the suspect set, proven by the failing-read assertion still holding before the passing read  
**And** the clearing read was a member of the read-only profile — verify: `grep -A16 "READ_ONLY_PROFILE = frozenset" src/freecad_buddy/hosts/tool_catalog.py` lists `query_tree_summary`  
**And** *(visual)* `D` is shown in the GUI, because H1 has no viewport — verify: `mcp document_save { doc: <D>, path: "$RUN_DIR/evidence/tc-10-09-D.FCStd" }` on H1 returns `OK`; then over the GUI proxy `mcp document_open { path: "$RUN_DIR/evidence/tc-10-09-D.FCStd" }` returns `OK`, run Show All (H1 writes no `GuiDocument.xml`), then `mcp view_fit_viewport { doc: "<GUI handle>" }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state once the suspect flag is cleared — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-09-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and `D`'s box is drawn whole and framed with exactly one small `QuarantineCleared` cube beside it — nothing half-applied, no blank or half-painted viewport. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-10-09-D.marker"
```
```
mcp document_close { doc: "<GUI handle>" }
```

---

### TC-10-10: NO automatic mutation retry

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §7 (AD-27 no blind retry), `verification-design.md` §fingerprint

**Host**: H1 (stdio, front plus worker), the same session as TC-10-07. The contract is that the
BRIDGE never re-issues a timed-out mutation: not the front, not the RPC client, not the listener.
The client is told to read and compare fingerprints itself.

**Given** the golden box is open on the TC-10-07 H1 session as `F`, and no abandoned body is running — verify: `document_open` returns `OK` and `query_tree_summary { doc: <F> }` returns `OK`  
**And** the overrunning mutation is a `script_exec` on `F` whose body spends about 40 s in FreeCAD C++ calls, then adds a 5 mm cube `LateBox`; its budget is 30 s  
**And** a golden model is open in the GUI as `<G>`, framed, and captured, so the GUI capture has an untouched subject — verify: run Show All, then `mcp view_fit_viewport { doc: "<G>" }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test, then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-10-before.png"}' | & cua-driver call get_window_state`  

**When** the document fingerprint is recorded before the mutation. No `query_*` tool returns a fingerprint digest, so read it from a preview  
```
mcp preview_dry_run { doc: <F>, operation: { tool: "feature_body_create", args: { name: "FpProbe" } } }
```
record its `fingerprint_before` digest
**And** the overrunning mutation is issued and the `TIMEOUT` envelope is read  
```
mcp script_exec { doc: <F>, code: "import time, Part\nend = time.monotonic() + 40\nwhile time.monotonic() < end:\n    Part.makeBox(10, 10, 10).fuse(Part.makeSphere(6))\nb = doc.addObject('Part::Box', 'LateBox'); b.Length = b.Width = b.Height = 5; b.Placement.Base.y = 25; doc.recompute()\nresult = 'done'" }
```
**And** the worker process is waited on until it is idle again  
**And** a `query_tree_summary { doc: <F> }` read is run, and the fingerprint digest is captured again with the same `preview_dry_run`  

**Then** the envelope tells the client not to blind-retry — verify: `detail.message` contains `the document is now suspect: do not blind-retry, run a query_* read first to confirm `  
**And** exactly ONE dispatch of the mutation occurred — verify: in `$RUN_DIR/evidence/tc-10-07-audit.jsonl`, the `script_exec` call on `F` has one `before` and one `after` line  
**And** the bridge issued no second attempt — verify: no second `before` line for the same `params_digest` appears in `$RUN_DIR/evidence/tc-10-07-audit.jsonl`, and `LateBox` appears once in the `query_tree_summary` result  
**And** the client can decide from the fingerprints — verify: the final digest differs from the pre-mutation digest if and only if the body landed  
**And** a manual retry is the operator's call — verify: re-issuing the mutation after the clearing read returns a normal terminal envelope, proving retry is a client action  
**And** no retry loop exists in source — verify: `grep -rniE "retry|re-?issue" src/freecad_buddy/adapters/mcp_server.py src/freecad_buddy/adapters/rpc_listener.py src/freecad_buddy/adapters/rpc_client.py src/freecad_buddy/hosts/headless/entry.py` returns nothing that re-dispatches a call; the one expected hit is the `do not blind-retry` message text at `mcp_server.py:199`  
**And** *(visual)* `F` is shown in the GUI, because H1 has no viewport — verify: before any manual retry, `mcp document_save { doc: <F>, path: "$RUN_DIR/evidence/tc-10-10-F.FCStd" }` on H1 returns `OK`; then over the GUI proxy `mcp document_open { path: "$RUN_DIR/evidence/tc-10-10-F.FCStd" }` returns `OK`, run Show All, then `mcp view_fit_viewport { doc: "<GUI handle>" }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window is alive and shows the mutation applied at most once — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-10-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and the model carries the mutation's effect exactly once or not at all — never twice. A doubled feature in the pixels is the visible form of a blind retry, and it is the only artifact that can show it: the audit log records what the bridge believes it dispatched, not what landed in the model. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<GUI handle>" }
```

---

### TC-10-11: A read that times out quarantines the session but marks no document suspect

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §7 (suspect scope), §2.4 (H1 bound and quarantine), spine AD-27

**Host**: H1 (stdio, front plus worker), the same session as TC-10-07 (`adapters/mcp_server.py:189-210`,
the `marked_suspect=False` wording branch; `hosts/headless/entry.py:111-127`, the quarantine).
A read overrun quarantines the whole session like any other timeout. It marks no document
suspect, so once the body returns, a mutation on the same document is served.

**Given** a new document `H` is created on the H1 session with `document_create`, and an object whose recompute takes about 130 s is added to it with `script_exec`. That is longer than the 120 s budget of `verify_recompute`. The new object is touched, and `verify_recompute` recomputes the document before it reads it (`usecases/verify.py:436-437`)  
```
mcp script_exec { doc: <H>, code: "import time, Part\nclass Slow:\n    def __init__(self, obj):\n        obj.Proxy = self\n    def execute(self, obj):\n        time.sleep(130)\n        obj.Shape = Part.makeBox(10, 10, 10)\nSlow(doc.addObject('Part::FeaturePython', 'Slow'))\nresult = 'built'" }
```
**And** no abandoned body is running — verify: `query_tree_summary { doc: <H> }` returns `OK`  
**And** a golden model is open in the GUI as `<G>`, framed, and captured, so the GUI capture has an untouched subject — verify: run Show All, then `mcp view_fit_viewport { doc: "<G>" }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test, then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-11-before.png"}' | & cua-driver call get_window_state`  

**When** the overrunning READ-ONLY call is issued and the envelope is read  
```
mcp verify_recompute { doc: <H> }
```
**And** a MUTATING call is issued on the same handle at once, while the body still runs  
```
mcp script_exec { doc: <H>, code: "b = doc.addObject('Part::Box', 'AcceptedAfterRead'); b.Placement.Base.x = 15; result = 'ran'" }
```
**And** the client waits until the body has returned, about 140 s after the first call started, and issues the same mutating call again  

**Then** the read-only call returns `TIMEOUT` — verify: the first call's envelope `status` is `TIMEOUT`, after 120 s and before 121 s  
**And** the message states no mutation was attempted — verify: `detail.message` contains `no mutation was attempted, so the document is not marked suspect`  
**And** the message still warns the body may run — verify: `detail.message` contains `the body may still be running and `  
**And** the two wordings are mutually exclusive — verify: the first call's message does NOT contain `the document is now suspect`  
**And** `marshal_timeout` is still set on the read-only timeout — verify: `detail.data.marshal_timeout` is `true`  
**And** the mutation sent while the body runs is refused by the quarantine, not by the suspect rule — verify: the second call's envelope `status` is `TIMEOUT` with `detail.data.quarantined` `true` and a message starting `not dispatched:`; it does NOT carry `document-suspect`  
**And** after the body returns, the mutation applies — verify: the third call's envelope `status` is `OK`, and `query_tree_summary { doc: <H> }` lists `AcceptedAfterRead` once  
**And** *(visual)* the GUI subject is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<G>" }` over the GUI proxy returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — record it as the finding.  
**And** *(visual)* the FreeCAD window is alive and unchanged by the H1 read timeout — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-11-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and `<G>` is drawn whole and framed — not blank, not half-painted, not frozen. The H1 worker is a separate process, so the GUI window must not change. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
mcp document_close { doc: "<G>" }
```
End the H1 session: close the client's stdin. The front stops the worker.

---

### TC-10-12: FreeCAD killed mid-call surfaces WORKER_CRASHED

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (status closed set), `integration-mcp-freecad.md` §2.4 (transport failure)

**Host**: the H2 GUI proxy plus the in-FreeCAD listener. The proxy's `RpcClient.call` never
raises: a dead peer must become an envelope.

**Given** FreeCAD GUI is running with the addon loaded, and the operator accepts that this scenario terminates that process  
**And** no unsaved user work is open — verify: every open document reports no unsaved changes  
**And** a golden model is open so the post-restart visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed and the live state is captured through that same framing before the kill, so before and after share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-12-before.png"}' | & cua-driver call get_window_state`  

**When** a long-running call is issued through the proxy at `http://127.0.0.1:8765/mcp`  
**And** while the call is in flight, the FreeCAD process is ended through the operating system, from the agent shell at the same integrity level as FreeCAD (`cua-driver kill_app` and `Stop-Process` from another integrity level are refused)  
**And** what the in-flight call returns is read, with a hard client-side deadline of 180 s  

**Then** the in-flight call returns rather than hanging — verify: a response arrives inside the 180 s deadline  
**And** the status is `WORKER_CRASHED` — verify: the returned envelope `status` is exactly `WORKER_CRASHED`  
**And** the client is not left blocked on a socket — verify: the client process exits cleanly after reading the envelope  
**And** the proxy exits on its own once FreeCAD is gone, after the in-flight call has returned — verify: within 5 s of that envelope, `netstat -ano | grep :8765` shows no `LISTENING` row, and a following `tools/list` against `:8765` returns a connection error, never a partial/corrupt body  
**And** the crash and the exit are visible in the proxy log — verify: before the restart (the new proxy rewrites the log), `grep -i "crash\|connection" "$APPDATA/FreeCAD/v1-1/freecad-buddy/mcp-proxy.log"` shows the failure, and `grep -c "the MCP proxy exits and frees port 8765"` on the same file prints `1`  
**And** the discovery file for the dead pid is stale, not corrupt — verify: the remaining `rpc-<pid>.json` still parses as JSON  
**And** restarting FreeCAD restores service — verify: after restart, `tools/list` against `:8765` returns the live count (45 typed tools, plus `script_exec` when it is on: 46 by default)  
**And** the service comes from a new proxy bound to the new FreeCAD — verify: `curl -s http://127.0.0.1:8765/healthz` returns `"freecad_pid"` equal to the restarted FreeCAD pid  
**And** *(visual)* after the restart the golden model is reopened and framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<new handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — on a freshly restarted FreeCAD that is a restart-recovery failure, not a framing problem.  
**And** *(visual)* the restarted FreeCAD window is alive and shows a single coherent model state — verify: `'{"pid":<new pid>,"window_id":<new wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-12-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no crash-recovery or document-restore modal is left stuck on screen, and the same golden model is drawn whole and framed — not blank and not half-painted. A full `tools/list` proves the proxy came back, not that the human's application did. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Delete only the killed FreeCAD's discovery file; the live listener's file must stay.
rm -f "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<killed pid>.json"
```
```
mcp document_close { doc: "<new handle>" }
```

---

### TC-10-13: A socket dropped mid-frame closes only that connection and the listener survives

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §2.4 (framing), `data-contracts-design.md` §3

**Host**: the in-FreeCAD RPC listener. `_FrameReader.read_line`
(`adapters/rpc_listener.py:85-110`) raises `ValueError("connection closed mid-frame")` when the
peer closes with a partial buffer; `_read_line` (`:330-348`) catches it, logs one WARNING line with
no traceback, and closes only that connection. The proxy side of a dropped listener connection
is covered by TC-10-12: an in-flight proxy call returns `WORKER_CRASHED` with `listener connection
dropped`, never a raised exception.

**Given** the listener is accepting — verify: the discovery file exists and the port accepts a connect  
**And** before the proxy is stopped, a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-13-before.png"}' | & cua-driver call get_window_state`  
**And** the MCP proxy is stopped so the raw client is the only session — a raw `rpc_hello` while the proxy holds the session gets `-32000 bridge busy: another client session is active` (AD-26). Verify: `netstat -ano | grep ":<port>" | grep ESTABLISHED` returns nothing  

**When** a client connects, completes `rpc_hello`, then writes a request with NO trailing newline and closes the socket immediately  
**And** the listener log is read  
**And** a fresh client connects, completes `rpc_hello`, and issues `document_list`  

**Then** the truncated frame closed only that connection — verify: `grep "WARNING.*frame read failed; closing connection: connection closed mid-frame" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns one line, and no `Traceback` follows it  
**And** the accept loop kept running — verify: the fresh client's connect succeeds  
**And** the fresh client's handshake is answered — verify: it reads a result carrying `contract_version` equal to `"1"`  
**And** the fresh client's call returns `OK` — verify: the `document_list` envelope `status` is `OK`  
**And** the drop was not reported as a document fault — verify: no `document-suspect` string appears in the log for this scenario  
**And** FreeCAD is still responsive — verify: the GUI window still answers a menu query via `cua-driver`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — after a mid-frame drop that is a listener-survival failure and must be recorded.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after the framing fault — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-13-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal or error popup is stuck on screen from the truncated frame, and the model is drawn whole and framed — not blank and not half-painted. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Restart the proxy by hand with the addon's command line (from Win32_Process.CommandLine of the spawned proxy), setting on that command each FREECAD_BUDDY_* value from the last operator settings: line of addon.log. A hand-started proxy reads only the shell's environment (gui_external/entry.py:142), not the addon's preference overlay, so without those values its exec_enabled and tool count can differ from FreeCAD's posture. When the run uses a non-default posture, restart FreeCAD instead, then: mcp query_capabilities {} returns OK
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-10-14: An over-cap or non-UTF-8 frame closes only that connection

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §2.4 (16 MiB frame cap), `data-contracts-design.md` §3

**Host**: the in-FreeCAD RPC listener. The cap is `_MAX_FRAME_BYTES = 16 * 1024 * 1024`
(`adapters/rpc_listener.py:43`), enforced in `read_line` at line 96.

**Given** the listener is accepting  
**And** before the proxy is stopped, a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the FreeCAD process working set is recorded before the over-cap stream — verify: `powershell -NoProfile -Command "(Get-Process -Id <pid>).WorkingSet64"` prints a byte count; record it as `ws_before`  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-14-before.png"}' | & cua-driver call get_window_state`  
**And** the MCP proxy is stopped so the raw client is the only session — a raw `rpc_hello` while the proxy holds the session gets `-32000 bridge busy: another client session is active` (AD-26). Verify: `netstat -ano | grep ":<port>" | grep ESTABLISHED` returns nothing  

**When** a client connects, completes `rpc_hello`, then streams more than 16 MiB with no newline  
```bash
python3 -c "import socket,sys;s=socket.create_connection((HOST,PORT));s.sendall(HELLO);s.recv(65536);s.sendall(b'{\"x\":\"'+b'A'*(17*1024*1024))"
```
**And** the FreeCAD process working set is read again  
```bash
powershell -NoProfile -Command "(Get-Process -Id <pid>).WorkingSet64"
```
**And** a second client connects and sends a frame containing raw bytes that are not valid UTF-8, terminated by a newline  
**And** a third client connects normally and issues `document_list`  

**Then** the over-cap connection is closed — verify: the first client's next `recv` returns zero bytes or raises `ConnectionResetError`. On Windows the listener closes while unread client data is still queued, so the peer sees a reset instead of an orderly close; both mean the connection is closed  
**And** the cap breach is logged once at WARNING with no traceback — verify: `grep "WARNING.*frame read failed; closing connection: frame exceeds 16 MiB cap" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns one line  
**And** the non-UTF-8 connection is also closed — verify: the second client's next `recv` returns zero bytes  
**And** the accept loop survived both — verify: the third client's connect and handshake succeed  
**And** the third client's call returns `OK` — verify: the `document_list` envelope `status` is `OK`  
**And** FreeCAD's memory did not grow unboundedly — verify: the FreeCAD process working set after the over-cap stream is within 100 MB of its value before the stream, that is `ws_after - ws_before` is below `104857600` bytes  
**And** no document was marked suspect by a framing fault — verify: a mutating call on any open document is not refused with `document-suspect`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — after a 17 MiB stream that points at memory pressure and must be recorded, not retried away.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after both malformed frames — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-14-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and the model is drawn whole and framed — not blank, not half-painted, and with no stall or partial repaint left by the 17 MiB stream. A working-set number inside 100 MB proves nothing about whether the human's window still draws. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Restart the proxy by hand with the addon's command line (from Win32_Process.CommandLine of the spawned proxy), setting on that command each FREECAD_BUDDY_* value from the last operator settings: line of addon.log. A hand-started proxy reads only the shell's environment (gui_external/entry.py:142), not the addon's preference overlay, so without those values its exec_enabled and tool count can differ from FreeCAD's posture. When the run uses a non-default posture, restart FreeCAD instead, then: mcp query_capabilities {} returns OK
```
```
mcp document_close { doc: "<handle>" }
```
