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

**Host divergence (applies to the whole file).** The inline H1 host
(`adapters/mcp_server.py:174-220`) carries the document-suspect set, the non-string-`doc` guard,
and audit writes. The H2 GUI proxy (`hosts/gui_external/entry.py:136-140`) has its own
`_call_tool` that does none of those things — it only dispatches and wraps. A suspect-document
scenario run against `http://127.0.0.1:8765/mcp` will NOT reproduce. The in-FreeCAD listener
(`adapters/rpc_listener.py:304-343`) carries its own suspect set with DIFFERENT wording.

**Host**: H1 inline (stdio) for the serialization, budget, timeout and quarantine scenarios
(TC-10-01, TC-10-02, TC-10-05, TC-10-07..TC-10-11); the in-FreeCAD RPC listener for the
client-session and framing scenarios (TC-10-01, TC-10-03, TC-10-04, TC-10-06, TC-10-13,
TC-10-14); the H2 GUI proxy plus the listener for TC-10-12. Every scenario's closing visual is
captured from the live FreeCAD GUI window with `cua-driver`.

## Preconditions

- [ ] micromamba `fcb` env is H1-capable (verify: `"$FCB_PYTHON" -c "import FreeCAD, mcp"`)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)
- [ ] For the H2 scenarios only: FreeCAD GUI running with the addon loaded (verify: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/mcp` returns a non-`000` code)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)
- [ ] `cua-driver` can drive the FreeCAD window and invoke its menus (verify: `cua-driver call list_windows` reports the `pid` and `window_id`, and click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`) returns without error)

---

### TC-10-01: One client's calls are strictly serialized

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §2.4 (single marshal), `component-design.md` §RPC listener

**Host**: H1 inline (stdio) and the in-FreeCAD listener.

**Given** no stale H1 server holds the golden files — verify: `ls "$RUN_DIR/evidence"/*.lock 2>/dev/null` returns nothing  
**And** a golden model is open in the GUI so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-01-before.png"}' | & cua-driver call get_window_state`  

**When** one document is opened and six reads are issued back to back on a single connection, recording entry and exit timestamps per call  
```bash
uv run python scripts/automation/run_mcp_e2e.py
```
**And** the per-call ordering is read out of the report  
```bash
python3 -c "import json;r=json.load(open('$RUN_DIR/evidence/tc-10-01-e2e_report.json'));print([c['tool'] for c in r['checks']])"
```

**Then** every call returned before the next one started — verify: the recorded `[start, end]` spans in `$RUN_DIR/evidence/tc-10-01-e2e_report.json` do not overlap  
**And** results arrive in request order — verify: the `tool` sequence printed by the second command matches the request sequence in `scripts/automation/run_mcp_e2e.py`  
**And** exactly one marshal call per request — verify: `grep -c "marshal" "$RUN_DIR/evidence/tc-10-01-server.stderr.log"` shows no nested-call warnings  
**And** the sweep gate is green — verify: `python3 -c "import json;print(json.load(open('$RUN_DIR/evidence/tc-10-01-e2e_report.json'))['all_passed'])"` returns `True`  
**And** no interleaving traceback — verify: `grep -iE "reentrant|deadlock|already in marshal" "$RUN_DIR/evidence/tc-10-01-server.stderr.log"` returns nothing  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — record it as the finding.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after the serialized sweep settled — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-01-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and one whole box is drawn and framed in the viewport — not blank, not half-painted, and with no duplicated or half-applied geometry from the six back-to-back reads. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence"/*.step "$RUN_DIR/evidence"/*.stl "$RUN_DIR/evidence"/tc-10-01-scratch.FCStd
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-10-02: Read-only latency budget (AD-24)

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §7 (latency budget), `mcp-tools-design.md` §timeouts

**Host**: H1 inline.

The measurement point is tool-call entry to envelope return, not wall time of the whole sweep.
The budget is median <= 15 s over the read-only profile. The per-tool marshal timeouts are
larger (30 s for most `query_*`, 60 s for `query_screenshot` / `verify_shape` / `verify_sketch`,
120 s for `verify_recompute`) — the budget is a performance assertion, the timeout is a contract.

**Given** golden models are present — verify: `ls benchmarks/g0/golden-models/*.FCStd | wc -l` is >= 5  
**And** a golden model is open in the GUI so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-02-before.png"}' | & cua-driver call get_window_state`  

**When** the happy-path sweep is run, which records a duration per check  
```bash
uv run python scripts/automation/run_mcp_e2e.py
```
**And** the median duration over the read-only tools is computed  
```bash
python3 -c "import json,statistics;r=json.load(open('$RUN_DIR/evidence/tc-10-02-e2e_report.json'));d=[c['duration_s'] for c in r['checks'] if c['tool'].startswith(('query_','verify_','document_list'))];print(len(d), statistics.median(d))"
```

**Then** the median read-only call is at or under 15 s — verify: the second number printed by the median command is `<= 15.0`  
**And** at least 8 read-only calls were sampled — verify: the first number printed by the median command is `>= 8`  
**And** no read-only call returned `TIMEOUT` — verify: `grep -c '"status": "TIMEOUT"' "$RUN_DIR/evidence/tc-10-02-e2e_report.json"` returns `0`  
**And** `query_screenshot` stayed inside its own 60 s marshal budget — verify: the `query_screenshot:*` entries in the report show `status=OK`  
**And** no call exceeded its declared `timeout_s` — verify: each check's `duration_s` is below the tool's timeout in `src/freecad_buddy/hosts/tool_catalog.py`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — record it as the finding.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after the budget sweep settled — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-02-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and one whole box is drawn and framed — not blank, not half-painted, and not frozen mid-render by the sweep. A median under 15 s reported by the bridge while the window is dead is the defect this catches. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence"/tc-10-02-*.png
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
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-03-before.png"}' | & cua-driver call get_window_state`  

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
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — record it as the finding.  
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

**Given** no client is currently connected — verify: `netstat -ano | grep ":<port>" | grep ESTABLISHED` returns nothing  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-04-before.png"}' | & cua-driver call get_window_state`  

**When** client A connects, sends `rpc_hello` with the discovery token, runs `document_list`, disconnects  
**And** client B connects and sends `document_list` as its FIRST frame, with no `rpc_hello`  
**And** client C connects, sends a correct `rpc_hello`, then `document_list`  

**Then** A's handshake is accepted — verify: A reads a result carrying `contract_version`, `freecad_version` and `capabilities`  
**And** B is refused for skipping the handshake — verify: B reads an error frame with `message` exactly `handshake required`  
**And** B's connection is closed by the listener — verify: B's next `recv` returns zero bytes  
**And** C's fresh handshake succeeds — verify: C reads a result carrying `contract_version` equal to `"1"`  
**And** C's `document_list` returns `OK` — verify: the envelope `status` field is `OK`  
**And** refusing B did not stop the accept loop — verify: C connected AFTER B was refused and was served  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — record it as the finding.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after the three sessions settled — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-04-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal or error popup is stuck on screen from the refused handshake, and one whole box is drawn and framed — not blank and not half-painted. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-10-05: A long-running operation does not starve the listener

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §7 (budget), `mcp-tools-design.md` §5 (preview)

**Host**: H1 inline. `preview_dry_run` carries the largest budget in the surface: 180 s.

**Given** a document with a body that takes a measurable time to recompute is open — record the handle  
**And** the model is framed and the pre-call state is captured through that same framing, so before and after share a camera — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-05-before.png"}' | & cua-driver call get_window_state`  

**When** a `preview_dry_run` whose operation takes roughly 100 s to recompute is issued, and the connection is held open for its whole duration  
**And** nothing else is issued on the same connection while it runs  
**And** when it returns, a `document_list` is issued on the same connection  

**Then** the preview returns a terminal envelope, not a dropped connection — verify: one envelope frame is read with `status` in the closed set  
**And** the call was not cut at a shorter budget — verify: the measured duration is above 60 s and the status is not `TIMEOUT`  
**And** the connection survived — verify: the following `document_list` returns `status=OK` on the SAME socket  
**And** no keepalive or idle-timeout close was logged — verify: `grep -iE "timed out|connection reset" "$RUN_DIR/evidence/tc-10-05-server.stderr.log"` returns nothing  
**And** the preview TempDoc was cleaned up — verify: `mcp__freecad-buddy__document_list` shows no handle whose name starts with `FCB_TMP_prev_`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — after a 100 s call held the connection open, that is exactly the outcome this scenario must not silently pass.  
**And** *(visual)* the FreeCAD window is alive and shows the document in a coherent state after the 100 s call — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-05-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no progress modal is stuck on screen, and the same document is drawn whole and framed — not blank, not half-painted, and with no mid-recompute artifact left by the long preview. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -rf "$TEMP"/FCB_TMP_prev_*
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-10-06: Handles are not shared across sessions

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (handles), `security-and-service-design.md` §2 (session scope)

**Host**: the in-FreeCAD RPC listener.

**Given** the GUI has at least one document open  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-06-before.png"}' | & cua-driver call get_window_state`  

**When** session A opens a document and the handle it returns is recorded  
**And** A disconnects, and a reconnect is made as session B with a fresh `rpc_hello`  
**And** session B calls `query_object` using session A's handle verbatim  
**And** session B calls `document_list` and the handles it reports are compared  

**Then** session A's open returned a handle — verify: the `document_create`/`document_open` envelope carries a non-empty handle string  
**And** session B rejects A's handle — verify: the `query_object` envelope `status` is `INVALID_INPUT`  
**And** the rejection is a closed-set status, not a raised exception — verify: the envelope has `schema` equal to `fcb.result-envelope/1`  
**And** session B's own `document_list` does not contain A's handle — verify: the returned handle list excludes the recorded string  
**And** the listener survived the bad handle — verify: a following `document_list` on B returns `status=OK`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — record it as the finding.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after both sessions settled — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-06-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and the model is drawn whole and framed — not blank and not half-painted. The cross-session handle rejection must have closed no document and disturbed no view. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-10-07: A budget overrun returns TIMEOUT and the body may still run

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §7 (timeout), `data-contracts-design.md` §3 (status closed set)

**Host**: H1 inline. There is NO preemption: `Marshal.call` raises `MarshalTimeout` at the caller
and the queued body keeps running on the Qt main thread.

**Given** a document whose recompute exceeds the tool's `timeout_s` is available — record the handle  
**And** the model is framed through the GUI menu, not through MCP, and the pre-timeout state is captured through that same framing, so before and after share a camera — verify: click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-07-before.png"}' | & cua-driver call get_window_state`  

**When** a mutating call whose body is known to exceed its 120 s budget is issued  
**And** the returned envelope is read in full  
**And** whether the FreeCAD process stays busy after the envelope was returned is recorded  

**Then** the envelope status is `TIMEOUT` — verify: the returned `status` field is exactly `TIMEOUT`  
**And** the timeout is flagged as a marshal timeout — verify: `detail.data.marshal_timeout` is `true`  
**And** the envelope says the body may still be running — verify: `detail.data.maybe_still_running` is `true`  
**And** the message names the consequence — verify: `detail.message` contains `the document is now suspect: do not blind-retry, run a query_* read first to confirm `  
**And** the call was NOT preempted — verify: the FreeCAD process still shows CPU activity after the envelope arrived  
**And** the connection is still usable — verify: a following read-only call on the same connection returns a terminal envelope  
**And** the timeout was audit-logged — verify: `grep '"verify_verdict": "TIMEOUT"' "$RUN_DIR/evidence/tc-10-07-audit.jsonl"` returns at least one line  
**And** *(visual)* no fit is performed here, by either route: the handle is now suspect, and a fit is a mutating call the quarantine must refuse, so performing it would corrupt TC-10-08. The `before.png` was framed in the `Given` so the two images already share a camera.  
**And** *(visual)* the FreeCAD window is alive and shows the document in a coherent state after the timed-out call — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-07-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and the document is drawn whole — not blank, not half-painted, and not frozen mid-operation. **This is the assertion the whole scenario earns.** A correct `TIMEOUT` envelope over a frozen FreeCAD window is the exact defect class commit `636fb8a` fixed, and every numeric `Then` above would still pass. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Wait for the running body to finish before the next scenario; do not kill FreeCAD.
```

---

### TC-10-08: A timeout quarantines the document

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §7 (quarantine), `data-contracts-design.md` §3 (INVALID_INPUT)

**Host**: H1 inline ONLY (`adapters/mcp_server.py:199-207`). The in-FreeCAD listener enforces the
same rule with different wording (`adapters/rpc_listener.py:319-323`): `document-suspect: a prior
call timed out on this document; run a query_* read to confirm state before mutating`. The H2
proxy does NOT enforce it at all.

**Given** TC-10-07 has just run and left document `D` marked suspect  
**And** the window's current state is captured before the attempt, with no fit of any kind, so the camera is whatever TC-10-07 left — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-08-before.png"}' | & cua-driver call get_window_state`  

**When** a second MUTATING call is issued on the same document handle `D`  
**And** the returned envelope is read  
**And** a mutating call is issued on a DIFFERENT document handle `E`  

**Then** the second mutation on `D` is refused — verify: the returned `status` is `INVALID_INPUT`  
**And** the refusal names the quarantine — verify: `detail.message` starts with `document-suspect: a prior call timed out on this document and its body may `  
**And** the message tells the operator what to do — verify: `detail.message` contains `run a query_* read to confirm the document still responds `  
**And** the refusal happened WITHOUT dispatching — verify: no new `before`/`after` pair for the operation body appears in the FreeCAD log between the request and the reply  
**And** the refusal is still audit-logged — verify: `grep '"verify_verdict": "INVALID_INPUT"' "$RUN_DIR/evidence/tc-10-08-audit.jsonl"` returns a line whose `tool` is the refused tool  
**And** quarantine is per document — verify: the mutating call on handle `E` is NOT refused with `document-suspect`  
**And** the H2 proxy does not carry this rule — verify: `grep -c "document-suspect" src/freecad_buddy/hosts/gui_external/entry.py` returns `0`  
**And** *(visual)* no fit is performed first here, by either route: a fit is a mutating call the quarantine must refuse, so performing it — through MCP or through **View → Fit All** — would move the camera and destroy the unchanged-window comparison this scenario rests on  
**And** *(visual)* the FreeCAD window is alive and visually unchanged by the refused mutation — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-08-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and the viewport is pixel-for-pixel the same scene as the before image. A quarantined mutation that reached the window would prove the refusal happened after dispatch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Leave D quarantined; TC-10-09 clears it.
```

---

### TC-10-09: Quarantine clears only via a non-mutating OK

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §7 (quarantine clearing), `mcp-tools-design.md` §read-only profile

**Host**: H1 inline (`adapters/mcp_server.py:216-217`: clear only when the method is known, not
mutating, and the envelope status is `OK`).

**Given** document `D` is still quarantined from TC-10-08  
**And** the window's current state is captured before the attempts, with no fit of any kind, since `D` is still quarantined — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-09-before.png"}' | & cua-driver call get_window_state`  

**When** a read-only call on `D` that FAILS is issued, for example `query_object` naming an object that does not exist  
**And** a mutating call is issued on `D` again  
**And** a read-only call on `D` that SUCCEEDS is issued, for example `query_tree_summary`  
**And** the mutating call is issued on `D` once more  

**Then** the failing read returns `INVALID_INPUT` — verify: the first call's envelope `status` is `INVALID_INPUT`  
**And** a failing read does NOT clear the quarantine — verify: the second call's mutation is still refused with `document-suspect: a prior call timed out on this document and its body may `  
**And** the passing read returns `OK` — verify: the third call's envelope `status` is `OK`  
**And** the passing read clears the quarantine — verify: the fourth call's mutation is no longer refused with `document-suspect`  
**And** a mutation can never clear it — verify: the second call's refusal did not remove `D` from the suspect set, proven by the failing-read assertion still holding before the passing read  
**And** the clearing read was a member of the read-only profile — verify: `grep -A16 "READ_ONLY_PROFILE = frozenset" src/freecad_buddy/hosts/tool_catalog.py` lists `query_tree_summary`  
**And** *(visual)* the model is framed, and only now — the quarantine is lifted, so a fit is legal at this point and would have been the refused mutation at any earlier one — verify: `mcp view_fit_viewport { doc: "<D handle>" }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — after the timeout body of TC-10-07, that is a real possibility and must be recorded, not worked around.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state once the quarantine is cleared — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-09-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and `D`'s model is drawn whole and framed carrying the effect of the final accepted mutation — nothing half-applied, no blank or half-painted viewport. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# D is now clear.
```

---

### TC-10-10: NO automatic mutation retry

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §7 (AD-27 no blind retry), `verification-design.md` §fingerprint

**Host**: H1 inline. The contract is that the BRIDGE never re-issues a timed-out mutation. The
client is told to read and compare fingerprints itself.

**Given** a mutating call that reliably overruns its budget is available — record the handle  
**And** the model is framed through the GUI menu, not through MCP, and the pre-mutation state is captured through that same framing, so before and after share a camera — verify: click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-10-before.png"}' | & cua-driver call get_window_state`  

**When** the document fingerprint is recorded before the mutation  
```bash
# via query_object / verify_recompute, capture the fingerprint digest
```
**And** the overrunning mutation is issued and the `TIMEOUT` envelope is read  
**And** the FreeCAD process is waited on until it is idle again  
**And** a `query_*` read is run and the fingerprint digest is captured again  

**Then** the envelope tells the client not to blind-retry — verify: `detail.message` contains `the document is now suspect: do not blind-retry, run a query_* read first to confirm `  
**And** exactly ONE dispatch of the mutation occurred — verify: `grep -c '"tool": "<the tool>"' "$RUN_DIR/evidence/tc-10-10-audit.jsonl"` shows one `before` and one `after` line for the call  
**And** the bridge issued no second attempt — verify: no second `before` line for the same `params_digest` appears in `$RUN_DIR/evidence/tc-10-10-audit.jsonl`  
**And** the client can decide from the fingerprints — verify: the final digest differs from the pre-mutation digest if and only if the body landed  
**And** a manual retry is the operator's call — verify: re-issuing the mutation after the clearing read returns a normal terminal envelope, proving retry is a client action  
**And** no retry loop exists in source — verify: `grep -rniE "retry|re-?issue" src/freecad_buddy/adapters/mcp_server.py src/freecad_buddy/adapters/rpc_listener.py` returns nothing that re-dispatches a call  
**And** *(visual)* the model is framed, and only after the clearing read above has lifted the quarantine — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked by the still-running timeout body — record it as the finding.  
**And** *(visual)* the FreeCAD window is alive and shows the mutation applied at most once — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-10-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and the model carries the mutation's effect exactly once or not at all — never twice. A doubled feature in the pixels is the visible form of a blind retry, and it is the only artifact that can show it: the audit log records what the bridge believes it dispatched, not what landed in the model. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```

---

### TC-10-11: A call that attempted no mutation does not mark the document suspect

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §7 (suspect scope), `mcp-tools-design.md` §read-only profile

**Host**: H1 inline (`adapters/mcp_server.py:126-148`, the `marked_suspect=False` wording branch).

**Given** a read-only call that overruns its budget is available, for example `verify_recompute` on a very heavy document — record the handle  
**And** the model is framed and the pre-timeout state is captured through that same framing, so before and after share a camera — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-11-before.png"}' | & cua-driver call get_window_state`  

**When** the overrunning READ-ONLY call is issued and the envelope is read  
**And** a MUTATING call is issued immediately on the same document handle  

**Then** the read-only call returns `TIMEOUT` — verify: the first call's envelope `status` is `TIMEOUT`  
**And** the message states no mutation was attempted — verify: `detail.message` contains `no mutation was attempted, so the document is not marked suspect`  
**And** the message still warns the body may run — verify: `detail.message` contains `the body may still be running and `  
**And** the following mutation is NOT refused — verify: the second call's envelope `status` is not `INVALID_INPUT` carrying `document-suspect`  
**And** the two wordings are mutually exclusive — verify: the first call's message does NOT contain `the document is now suspect`  
**And** `marshal_timeout` is still set on the read-only timeout — verify: `detail.data.marshal_timeout` is `true`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; the fit is legitimate here because the document was never marked suspect, which is the assertion under test. If it does not return `OK`, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked by the still-running read body — record it as the finding.  
**And** *(visual)* the FreeCAD window is alive and shows the document in a coherent state after the timed-out read — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-11-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and the model is drawn whole and framed carrying the effect of the accepted mutation — not blank, not half-painted, not frozen mid-operation. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```

---

### TC-10-12: FreeCAD killed mid-call surfaces WORKER_CRASHED

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (status closed set), `integration-mcp-freecad.md` §2.4 (transport failure)

**Host**: the H2 GUI proxy plus the in-FreeCAD listener. The proxy's `RpcClient.call` never
raises: a dead peer must become an envelope.

**Given** FreeCAD GUI is running with the addon loaded, and the operator accepts that this scenario terminates that process  
**And** no unsaved user work is open — verify: every open document reports no unsaved changes  
**And** a golden model is open so the post-restart visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed and the live state is captured through that same framing before the kill, so before and after share a camera — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-12-before.png"}' | & cua-driver call get_window_state`  

**When** a long-running call is issued through the proxy at `http://127.0.0.1:8765/mcp`  
**And** while the call is in flight, the FreeCAD process is ended through the operating system  
**And** what the in-flight call returns is read, with a hard client-side deadline of 180 s  

**Then** the in-flight call returns rather than hanging — verify: a response arrives inside the 180 s deadline  
**And** the status is `WORKER_CRASHED` — verify: the returned envelope `status` is exactly `WORKER_CRASHED`  
**And** the client is not left blocked on a socket — verify: the client process exits cleanly after reading the envelope  
**And** the proxy did not itself crash — verify: a following `tools/list` against `:8765` either answers or returns a connection error, never a partial/corrupt body  
**And** the crash is visible in the proxy log — verify: `grep -i "crash\|connection" "$APPDATA/FreeCAD/v1-1/freecad-buddy/mcp-proxy.log"` shows the failure  
**And** the discovery file for the dead pid is stale, not corrupt — verify: the remaining `rpc-<pid>.json` still parses as JSON  
**And** restarting FreeCAD restores service — verify: after restart, `tools/list` against `:8765` returns 44 tools  
**And** *(visual)* after the restart the golden model is reopened and framed — verify: `mcp view_fit_viewport { doc: "<new handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — on a freshly restarted FreeCAD that is a restart-recovery failure, not a framing problem.  
**And** *(visual)* the restarted FreeCAD window is alive and shows a single coherent model state — verify: `'{"pid":<new pid>,"window_id":<new wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-12-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no crash-recovery or document-restore modal is left stuck on screen, and the same golden model is drawn whole and framed — not blank and not half-painted. A `tools/list` answering 44 tools proves the proxy came back, not that the human's application did. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-"*.json
```
```
mcp document_close { doc: "<new handle>" }
```

---

### TC-10-13: A socket dropped mid-frame yields WORKER_CRASHED and the listener survives

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §2.4 (framing), `data-contracts-design.md` §3

**Host**: the in-FreeCAD RPC listener. `_FrameReader.read_line`
(`adapters/rpc_listener.py:64-83`) raises `ValueError("connection closed mid-frame")` when the
peer closes with a partial buffer; `_serve_conn` catches it and closes only that connection
(lines 242-247).

**Given** the listener is accepting — verify: the discovery file exists and the port accepts a connect  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-13-before.png"}' | & cua-driver call get_window_state`  

**When** a client connects, completes `rpc_hello`, then writes a request with NO trailing newline and closes the socket immediately  
**And** the listener log is read  
**And** a fresh client connects, completes `rpc_hello`, and issues `document_list`  

**Then** the truncated frame closed only that connection — verify: `grep "frame read failed; closing connection" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line  
**And** the accept loop kept running — verify: the fresh client's connect succeeds  
**And** the fresh client's handshake is answered — verify: it reads a result carrying `contract_version` equal to `"1"`  
**And** the fresh client's call returns `OK` — verify: the `document_list` envelope `status` is `OK`  
**And** the drop was not reported as a document fault — verify: no `document-suspect` string appears in the log for this scenario  
**And** through the H2 proxy the same drop surfaces as an envelope — verify: the proxy's corresponding call returns `status=WORKER_CRASHED`, never a raised exception  
**And** FreeCAD is still responsive — verify: the GUI window still answers a menu query via `cua-driver`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — after a mid-frame drop that is a listener-survival failure and must be recorded.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after the framing fault — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-13-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal or error popup is stuck on screen from the truncated frame, and the model is drawn whole and framed — not blank and not half-painted. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-10-14: An over-cap or non-UTF-8 frame closes only that connection

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §2.4 (16 MiB frame cap), `data-contracts-design.md` §3

**Host**: the in-FreeCAD RPC listener. The cap is `_MAX_FRAME_BYTES = 16 * 1024 * 1024`
(`adapters/rpc_listener.py:36`), enforced in `read_line` at line 76.

**Given** the listener is accepting  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the FreeCAD process working set is recorded before the over-cap stream — verify: `powershell -NoProfile -Command "(Get-Process -Id <pid>).WorkingSet64"` prints a byte count; record it as `ws_before`  
**And** the model is framed and the starting state is captured through that same framing, so before and after share a camera — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-14-before.png"}' | & cua-driver call get_window_state`  

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

**Then** the over-cap connection is closed — verify: the first client's next `recv` returns zero bytes  
**And** the cap breach is logged — verify: `grep "frame exceeds 16 MiB cap" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line  
**And** the non-UTF-8 connection is also closed — verify: the second client's next `recv` returns zero bytes  
**And** the accept loop survived both — verify: the third client's connect and handshake succeed  
**And** the third client's call returns `OK` — verify: the `document_list` envelope `status` is `OK`  
**And** FreeCAD's memory did not grow unboundedly — verify: the FreeCAD process working set after the over-cap stream is within 100 MB of its value before the stream, that is `ws_after - ws_before` is below `104857600` bytes  
**And** no document was marked suspect by a framing fault — verify: a mutating call on any open document is not refused with `document-suspect`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. A **View → Fit All** that itself hangs is diagnostic evidence that the GUI is blocked — after a 17 MiB stream that points at memory pressure and must be recorded, not retried away.  
**And** *(visual)* the FreeCAD window is alive and shows a single coherent model state after both malformed frames — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-10-14-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the window paints, the title bar carries no `Not Responding`, no modal is stuck on screen, and the model is drawn whole and framed — not blank, not half-painted, and with no stall or partial repaint left by the 17 MiB stream. A working-set number inside 100 MB proves nothing about whether the human's window still draws. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```
```
mcp document_close { doc: "<handle>" }
```
