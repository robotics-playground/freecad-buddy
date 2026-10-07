# TC-11: Security Posture & Artifact Hygiene

Validates the shipped security controls and the temporary-artifact lifecycle. AD-4 says typed
tools are the only mutation path and `debug_exec` is off unless an operator turns it on. AD-20
says a reserved-prefix temporary document must never outlive the call that made it. This file
also asserts that the bridge writes nothing into the user's document folder on its own, and that
the audit log is append-only.

**Not covered here.** Bearer-token authentication and `Origin` validation on the HTTP endpoint
are AD-3 requirements the code does not implement. They are asserted as expected failures in
`TC-99-ad-conformance-gaps.md` (TC-99-01 and TC-99-02). The only transport control that ships is
the loopback bind, tested in TC-11-05 and TC-11-06.

**Evidence hierarchy.** We are building the MCP bridge, so the bridge's own output can never be
the test result. A `cua-driver` pixel capture of the real FreeCAD window, `Read` and judged by the
agent, is the test result. Filesystem permissions, exit codes, audit lines and logs read directly
are corroborating, and they carry most of the weight in this security file — keep every one of
those assertions. MCP envelope fields, statuses and `query_screenshot` renders are claims under
test, never evidence. A bridge that reports a refusal while having already executed the thing it
claims to have refused passes every string assertion and fails the user completely; commit
`636fb8a` fixed exactly that class of defect, a correct-looking report over a wrong reality.

**Host**: H1 inline for TC-11-02, TC-11-03, TC-11-04, TC-11-08, TC-11-11, TC-11-12, TC-11-13 and
TC-11-15; H1 inline and the H2 proxy for TC-11-01, TC-11-10 and TC-11-14; the H2 GUI proxy for
TC-11-06; the in-FreeCAD RPC listener for TC-11-05, TC-11-07 and TC-11-09; the listener plus the
H2 proxy for TC-11-16. Most scenarios here are filesystem, process-environment or static-source
assertions with no visible model effect: each one opens a golden model in the GUI as an untouched
baseline, and its closing visual asserts the security check never reached the live application.

## Preconditions

- [ ] micromamba `fcb` env is H1-capable (verify: `"$FCB_PYTHON" -c "import FreeCAD, mcp"`)
- [ ] `FREECAD_BUDDY_ALLOW_EXEC` is unset in the shell used for the default-posture scenarios (verify: `env | grep FREECAD_BUDDY_ALLOW_EXEC` returns nothing)
- [ ] The host machine has a non-loopback IPv4 address for the bind scenarios (verify: `ipconfig | grep IPv4`)
- [ ] FreeCAD GUI is running with a 3D view open, so each scenario's closing visual has a baseline (verify: the FreeCAD window shows a 3D view; confirm by looking at a `cua-driver` capture, not by an MCP field)
- [ ] Golden models are present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` returns a `QOpenGLWidget`)
- [ ] The GUI's own **Fit All** toolbar button is reachable, as the non-MCP framing path (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` lists a `Fit All` toolbar element with an `element_token`; clicking it returns `route: "accessibility"` and reframes the view. Note `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable` at segment 1 — only `["View","Zoom"]` resolves.)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)

**Framing rule for every scenario below.** The `before.png` is captured AFTER the same fit as the
`after.png`, so the two images share a camera and a difference between them means a real change,
not a camera move.

---

### TC-11-01: debug_exec is unregistered by default

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (exec gating), `mcp-tools-design.md` §5 (tool surface)

**Host**: H1 inline and the H2 proxy. `registered_tools` skips `debug_exec` when
`exec_registered(caps)` is false (`adapters/mcp_server.py:70-75`); the proxy's
`build_proxy_registry` appends `DEBUG_EXEC_SPEC` only under the same condition
(`hosts/gui_external/entry.py:105-107`).

**Given** `FREECAD_BUDDY_ALLOW_EXEC` is unset — verify: `env | grep FREECAD_BUDDY_ALLOW_EXEC` returns nothing  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-01-before.png"}' | & cua-driver call get_window_state`  

**When** the H1 host is started with a clean environment and the tools are listed  
```bash
uv run python scripts/automation/run_mcp_e2e.py
```
**And** `debug_exec` is called directly by name anyway, bypassing `tools/list`  

**Then** the surface lists 44 tools — verify: the `tools/list` result length is `44`  
**And** `debug_exec` is absent from the listing — verify: no listed tool has `name` equal to `debug_exec`  
**And** a direct call is refused — verify: the returned envelope `status` is `INVALID_INPUT`  
**And** the refusal names the flag — verify: `detail.message` is exactly `debug_exec is disabled (set FREECAD_BUDDY_ALLOW_EXEC=1 to enable)`  
**And** the denied attempt is still audited — verify: `grep '"event": "exec"' "$RUN_DIR/evidence/tc-11-01-audit.jsonl"` returns a before/after pair for the refused call  
**And** no code was executed — verify: the document fingerprint is unchanged across the refused call  
**And** the proxy surface matches — verify: a `tools/list` against `http://127.0.0.1:8765/mcp` also returns 44 tools with no `debug_exec`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-01-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-01-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. A refusal that returned the right message while the payload nevertheless ran is exactly what the string assertions above cannot catch, so this image is the test result. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-11-01-scratch.FCStd"
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-02: debug_exec appears only with the exact flag value

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (operator flag), `mcp-tools-design.md` §5

**Host**: H1 inline. `Capabilities.from_env` (`usecases/capabilities.py:27-31`) compares the
environment value to the string `"1"` with `==`, so any other value disables the flag.

**Given** the operator accepts enabling arbitrary code execution for the duration of this scenario — verify: the operator's acceptance is recorded in the run report  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-02-before.png"}' | & cua-driver call get_window_state`  

**When** the host is started once for each value and the tools are listed  
```bash
FREECAD_BUDDY_ALLOW_EXEC=1    uv run python -m freecad_buddy.hosts.main serve --transport stdio --mode inline
FREECAD_BUDDY_ALLOW_EXEC=true uv run python -m freecad_buddy.hosts.main serve --transport stdio --mode inline
FREECAD_BUDDY_ALLOW_EXEC=yes  uv run python -m freecad_buddy.hosts.main serve --transport stdio --mode inline
FREECAD_BUDDY_ALLOW_EXEC=0    uv run python -m freecad_buddy.hosts.main serve --transport stdio --mode inline
```
**And** for the `=1` run, `query_capabilities` is called and the startup log is read  

**Then** with `=1` the surface lists 45 tools — verify: the `tools/list` result length is `45`  
**And** with `=1` `debug_exec` is present — verify: a listed tool has `name` equal to `debug_exec`  
**And** with `true` the tool is absent — verify: that run's `tools/list` length is `44`  
**And** with `yes` the tool is absent — verify: that run's `tools/list` length is `44`  
**And** with `0` the tool is absent — verify: that run's `tools/list` length is `44`  
**And** capabilities report the enabled state — verify: the `query_capabilities` envelope's `structured_content` reports `exec_enabled` as `true` on the `=1` run only  
**And** the operator is warned at startup — verify: the `=1` run's stderr contains `SECURITY: debug_exec ENABLED by operator flag`  
**And** the warning is absent otherwise — verify: the `true`, `yes` and `0` runs' stderr do not contain that string  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-02-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-02-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. Three of the four runs registered the exec tool or refused it; a run that reported the tool absent while still executing on the live application is what the count assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
unset FREECAD_BUDDY_ALLOW_EXEC
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-03: Every debug_exec call is audit-logged with a params digest

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (audit of exec), `data-contracts-design.md` §audit-record

**Host**: H1 inline. `AuditSink._record` (`adapters/audit_log.py:49-66`) writes
`event:"exec"` and additionally persists the executed `code` string, not only its digest.

**Given** `FREECAD_BUDDY_ALLOW_EXEC=1` for this scenario only — verify: `env | grep FREECAD_BUDDY_ALLOW_EXEC` returns `1`  
**And** a known audit-log path is set — verify: `echo $FREECAD_BUDDY_AUDIT_LOG`  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-03-before.png"}' | & cua-driver call get_window_state`  

**When** the audit log is pointed at a scratch file and one `debug_exec` is run  
```bash
FREECAD_BUDDY_AUDIT_LOG=$RUN_DIR/evidence/tc-11-03-audit.jsonl FREECAD_BUDDY_ALLOW_EXEC=1 \
  uv run python -m freecad_buddy.hosts.main serve --transport stdio --mode inline
```
**And** the resulting audit lines are read  
```bash
python3 -c "import json;[print(json.loads(l)['event'], json.loads(l)['tool'], json.loads(l).get('params_digest')) for l in open('$RUN_DIR/evidence/tc-11-03-audit.jsonl')]"
```

**Then** two lines were written for the one call — verify: `grep -c '"tool": "debug_exec"' "$RUN_DIR/evidence/tc-11-03-audit.jsonl"` returns `2`  
**And** both carry the exec event — verify: both lines have `"event": "exec"`  
**And** both carry a params digest — verify: each line's `params_digest` is a 64-character hexadecimal string  
**And** the digests match each other — verify: the `before` and `after` lines carry the same `params_digest`  
**And** the executed source is persisted — verify: the lines carry a `code` field equal to the submitted code string  
**And** the after line carries the verdict — verify: the second line has a non-null `verify_verdict`  
**And** each line is a valid audit record — verify: each line's `schema` is `fcb.audit-record/1`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-03-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-03-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. The exec ran on the separate H1 host; an exec that reached across into the human's application is what the audit-file assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-11-03-audit.jsonl"
unset FREECAD_BUDDY_ALLOW_EXEC
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-04: Typed tools are the only mutation path

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (AD-4), `mcp-tools-design.md` §5 (previewable operations)

**Host**: H1 inline. `preview_op_table` (`hosts/tool_catalog.py:909-927`) is built from the
`sketch_*` and `feature_*` spec lists only, so `debug_exec` is excluded structurally rather than
by a name list.

**Given** `FREECAD_BUDDY_ALLOW_EXEC` is unset — verify: `env | grep FREECAD_BUDDY_ALLOW_EXEC` returns nothing  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-04-before.png"}' | & cua-driver call get_window_state`  

**When** the tool surface is listed and every name is inspected  
**And** `preview_dry_run` is asked to preview `debug_exec` and the refusal is read  
**And** `preview_dry_run` is asked to preview a name that is not a tool at all  

**Then** no generic script or eval tool exists — verify: `grep -riE '"(exec|eval|script|run_python|run_code)"' src/freecad_buddy/hosts/tool_catalog.py` matches only the gated `debug_exec` spec  
**And** every mutating tool is a typed `document_*`, `sketch_*`, `feature_*` or `export_*` — verify: the 44 listed names contain no other mutating prefix  
**And** `debug_exec` is not previewable — verify: previewing it returns `status=INVALID_INPUT` with `detail.message` starting `not a previewable mutation tool:`  
**And** the refusal lists what IS previewable — verify: `detail.message` contains `(previewable: ` followed by `sketch_`/`feature_` names only  
**And** an unknown name is refused the same way — verify: the third call returns `status=INVALID_INPUT` with the same `not a previewable mutation tool:` prefix  
**And** every input schema is closed — verify: `python3 -c "import json;s=json.load(open('.../tool_surface.json'));print(all(t['input_schema'].get('additionalProperties') is False for t in s))"` returns `True`  
**And** an untyped extra argument is rejected — verify: any tool called with an undeclared key returns an MCP protocol rejection, not an envelope  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-04-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-04-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. Both previews were refused; a refusal that returned `INVALID_INPUT` while the operation nevertheless ran is exactly what the message assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-05: The RPC listener binds loopback only

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §2 (loopback bind), `integration-mcp-freecad.md` §2.4

**Host**: the in-FreeCAD RPC listener. `RpcListener.__init__` defaults `host="127.0.0.1"`
(`adapters/rpc_listener.py:109`) and `_bind` binds exactly that
(`adapters/rpc_listener.py:141-150`).

**Given** FreeCAD GUI is running with the addon loaded — verify: `netstat -ano | grep ":<port>" | grep LISTENING` shows the listener  
**And** the machine's LAN IPv4 address is known — verify: `ipconfig | grep IPv4`  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-05-before.png"}' | & cua-driver call get_window_state`  

**When** the listener port is read from the discovery file  
**And** the bound address is confirmed  
```bash
netstat -ano | grep ":<port>" | grep LISTENING
```
**And** a TCP connect to `<LAN-IP>:<port>` is attempted  

**Then** the listener is bound to `127.0.0.1`, not `0.0.0.0` — verify: the `netstat` line shows the local address as `127.0.0.1:<port>`  
**And** the discovery record agrees — verify: the `host` field in `rpc-<pid>.json` is `127.0.0.1`  
**And** a LAN-IP connect is refused — verify: the connect raises `ConnectionRefusedError` or times out with no handshake  
**And** a loopback connect still succeeds — verify: a connect to `127.0.0.1:<port>` completes `rpc_hello` and returns `contract_version` `"1"`  
**And** no other interface is listening on that port — verify: the `netstat` output shows exactly one LISTENING line for that port  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-05-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-05-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised by the refused LAN connect. A connect the listener reported as refused while still serving it is what the socket assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-06: The MCP HTTP endpoint binds loopback only

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §2 (loopback bind), `integration-mcp-clients.md` §transport

**Host**: the H2 GUI proxy. `_HOST = "127.0.0.1"` and `_PORT = 8765` are module constants
(`hosts/gui_external/entry.py:38-39`) and `run()` passes them straight into the uvicorn config
(`hosts/gui_external/entry.py:182`). There is no `--host` or `--port` CLI flag to change them.

**Given** the proxy is serving — verify: `netstat -ano | grep ":8765" | grep LISTENING`  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. This scenario probes the proxy's own bind and the proxy may be unreachable during the probe, so prefer the GUI menu path here.  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-06-before.png"}' | & cua-driver call get_window_state`  

**When** the bound address for port 8765 is confirmed  
**And** an HTTP POST to `http://<LAN-IP>:8765/mcp` is attempted  
**And** it is confirmed that no CLI flag can rebind  
```bash
uv run python -m freecad_buddy.hosts.main serve --transport http --mode rpc --host 0.0.0.0
```

**Then** the endpoint is bound to `127.0.0.1:8765` — verify: the `netstat` line shows the local address as `127.0.0.1:8765`  
**And** a LAN-IP POST fails at the transport — verify: `curl` to `http://<LAN-IP>:8765/mcp` reports connection refused  
**And** a loopback POST is served — verify: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/mcp` returns a real HTTP status code  
**And** there is no host override flag — verify: the `--host 0.0.0.0` command exits non-zero with an unrecognized-argument error  
**And** the bind is hard-coded, not read from the environment — verify: `grep -n "_HOST\|_PORT" src/freecad_buddy/hosts/gui_external/entry.py` shows literal values with no `os.environ` lookup  
**And** loopback bind is the ONLY control on this endpoint — verify: `grep -riE "Bearer|Authorization|Origin|CORS" src/freecad_buddy/hosts/gui_external/entry.py` returns nothing (this gap is TC-99-01 and TC-99-02)  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Use the GUI menu path if the rebind attempt left the proxy down.  
**And** *(visual)* the window is identical to `tc-11-06-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-06-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised by the refused LAN POST or the rejected rebind. A POST the transport reported as refused while the proxy still served it is what the `curl` assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-07: The discovery file is 0600 and carries the session token

**Priority**: High
**Design Ref**: `security-and-service-design.md` §2 (discovery file), `integration-mcp-freecad.md` §2.4 (handshake)

**Host**: the in-FreeCAD RPC listener. `_write_discovery` (`adapters/rpc_listener.py:182-203`)
writes the record then calls `os.chmod(path, 0o600)`. **On Windows `chmod` only toggles the
read-only bit**, which the source states at lines 197-198: the real controls are the loopback
bind plus the per-session token. Grade the world-readable assertion accordingly on this platform.

**Credential hygiene**: the discovery file holds a live session token. Do not copy the file, its
contents, or the token into `$RUN_DIR/evidence/`. Record the token only as a masked value, for
example the first four characters followed by its length.

**Given** FreeCAD GUI is running with the addon loaded — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-"*.json` lists a discovery file for the running pid  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-07-before.png"}' | & cua-driver call get_window_state`  

**When** the discovery file is located  
```bash
ls -l "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-"*.json
```
**And** its contents are read, in place, without copying them into the run folder  
**And** a handshake with a wrong token is attempted  

**Then** exactly one discovery file exists per live listener pid — verify: the filename is `rpc-<pid>.json` where `<pid>` is the running FreeCAD pid  
**And** the file is not world-readable — verify: on POSIX `stat -c %a` returns `600`; on Windows record that `chmod` only set the read-only bit and the enforced control is the token  
**And** the record carries a token — verify: the parsed JSON has a non-empty `token` string; assert on the masked value only, and keep the token itself out of `$RUN_DIR/evidence/`  
**And** the record carries the contract version — verify: `contract_version` is `"1"`  
**And** a wrong token is refused — verify: the handshake reply is an error frame with `message` exactly `auth failed`  
**And** the refusal discloses nothing — verify: that error frame carries no `data.supported` and no capabilities  
**And** the file is removed when the listener stops — verify: after FreeCAD quits, `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<pid>.json"` returns not-found  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-07-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-07-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised by the refused handshake. Capture this pair before the quit that closes the listener. A handshake the listener reported as `auth failed` while still admitting the caller is what the error-frame assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# The addon removes the file on quit.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-08: Auto-approve warns at startup and audits every auto-approved mutation

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (auto-approve), `mcp-tools-design.md` §5 (confirm gate)

**Host**: H1 inline. `build_server` logs the warning when `auto_approve_enabled(caps)` is true
(`adapters/mcp_server.py:161-162`). `AuditSink.approval` (`adapters/audit_log.py:86-101`) writes
one `event:"approval"` line naming what the approval covered.

**Given** the operator accepts running mutations without a confirm token for this scenario — verify: the operator's acceptance is recorded in the run report  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-08-before.png"}' | & cua-driver call get_window_state`  

**When** the host is started with `FREECAD_BUDDY_AUTO_APPROVE` unset (auto-approve is on by default) and a scratch audit log  
```bash
env -u FREECAD_BUDDY_AUTO_APPROVE FREECAD_BUDDY_AUDIT_LOG=$RUN_DIR/evidence/tc-11-08-approve.jsonl \
  uv run python -m freecad_buddy.hosts.main serve --transport stdio --mode inline
```
**And** one geometry mutation is run with NO `confirm` argument  
**And** the same is repeated with `FREECAD_BUDDY_AUTO_APPROVE=0`, and again with `FREECAD_BUDDY_AUTO_APPROVE=true`  

**Then** the operator is warned at startup — verify: stderr contains `SECURITY: mutation auto-approve ENABLED (FREECAD_BUDDY_AUTO_APPROVE unset or 1; set it to 0 to require preview_id)`  
**And** the mutation runs without a confirm token — verify: the envelope `status` is `OK` and no `this mutation requires a confirm` message appears  
**And** one approval record was written — verify: `grep -c '"event": "approval"' "$RUN_DIR/evidence/tc-11-08-approve.jsonl"` returns `1`  
**And** the approval names the tool and the switch — verify: that line's `tool` is the mutating tool name, and its `approval` has `"mode": "auto_approve"` and `"source": "FREECAD_BUDDY_AUTO_APPROVE"`  
**And** the approval carries the pre-mutation fingerprint — verify: that line's `fingerprint_before` matches the mutation's own `before` line  
**And** the approval digest matches the mutation's digest — verify: the approval line's `params_digest` equals the `before`/`after` lines' digest  
**And** `0` turns the confirm gate on — verify: the `FREECAD_BUDDY_AUTO_APPROVE=0` run's stderr lacks the warning and the same unconfirmed mutation is refused with `this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id`  
**And** any value other than `1` turns it on too — verify: the `FREECAD_BUDDY_AUTO_APPROVE=true` run gives the same result as the `=0` run  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-08-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-08-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. The `=0` and `true` runs refused their mutation; a refusal that returned the confirm-required message while the mutation nevertheless landed on the human's model is exactly what the message assertion cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-11-08-approve.jsonl"
unset FREECAD_BUDDY_AUTO_APPROVE
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-09: The session token is regenerated per listener start

**Priority**: High
**Design Ref**: `security-and-service-design.md` §2 (per-session token), `integration-mcp-freecad.md` §2.4

**Host**: the in-FreeCAD RPC listener.

**Credential hygiene**: both tokens are live secrets. Record them only as masked values and keep
them out of `$RUN_DIR/evidence/` entirely; compare the two in memory.

**Given** the operator can restart FreeCAD — verify: the operator's acceptance is recorded in the run report  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-09-before.png"}' | & cua-driver call get_window_state`  

**When** the token is recorded from the discovery file, masked  
**And** FreeCAD is quit and restarted  
**And** the new token is recorded, masked  
**And** a handshake against the new listener is attempted using the OLD token  

**Then** the second token differs from the first — verify: the two recorded `token` values are not equal; compare them in memory and report only the masked values  
**And** the old token is refused — verify: the OLD-token handshake reply is an error frame with `message` exactly `auth failed`  
**And** the connection is closed after refusal — verify: the next `recv` on that socket returns zero bytes  
**And** the new token is accepted — verify: a handshake with the post-restart token returns `contract_version` `"1"`  
**And** auth is checked before version — verify: a handshake carrying the OLD token AND an unsupported `contract_version` still returns `auth failed`, not `contract version unsupported`  
**And** the stale discovery file did not survive — verify: the pre-restart `rpc-<old pid>.json` no longer exists  
**And** *(visual)* the model is framed — verify: reopen the golden model after the restart, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. The restart may leave the bridge unready, so prefer the GUI menu path here.  
**And** *(visual)* the restarted window matches `tc-11-09-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-09-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised by the refused OLD-token handshakes. A handshake the listener reported as `auth failed` while still admitting the caller is what the error-frame assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-10: Reserved-prefix temporary documents never leak into document_list

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-20 TempDoc lifecycle), `mcp-tools-design.md` §5 (preview)

**Host**: H1 inline and the H2 proxy. `_discard_tempdoc` (`usecases/preview.py:338-351`) closes
the copy and removes its directory on the success, failure and exception paths alike. The
docstring states why: a leaked TempDoc is adopted by `document_list` and surfaced to the caller
mislabeled.

**Given** a document with at least one body is open — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** `document_list` currently reports no `FCB_TMP_` handles — verify: `mcp document_list {}` returns no name starting with `FCB_TMP_`  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured, including the model tree — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-10-before.png"}' | & cua-driver call get_window_state`  

**When** the `document_list` result is recorded  
**And** one `preview_dry_run` that succeeds is run  
**And** one `verify_export_step` is run (which re-imports into a fresh `FCB_TMP_` document)  
**And** `document_list` is recorded again  

**Then** the baseline list has no temp handles — verify: no returned name starts with `FCB_TMP_`  
**And** the preview returned a terminal envelope — verify: the `status` is in the closed set  
**And** no preview TempDoc remains — verify: no returned name starts with `FCB_TMP_prev_`  
**And** no export re-import document remains — verify: no returned name starts with `FCB_TMP_`  
**And** the list is identical to the baseline — verify: the final handle set equals the recorded baseline handle set  
**And** the user's own documents were untouched — verify: each pre-existing document's fingerprint digest is unchanged  
**And** no temp directory remains on disk — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-10-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-10-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, the model tree listing only the user's own document with no `FCB_TMP_` item, no new object in the viewport, no dialog raised. `document_list` is bridge output, so a leaked temporary document it omits from its own answer is exactly what the handle-set assertions cannot catch — the tree in the image is the independent check. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -rf "$TEMP"/FCB_TMP_prev_*
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-11: A preview TempDoc is removed on every exit path

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-20), `mcp-tools-design.md` §5 (preview)

**Host**: H1 inline. The prefix is `FCB_TMP_prev_` (`usecases/preview.py:33`) and it is carried by
the directory AND the filename, because the reopened document takes its `Name` from the file stem
(`usecases/preview.py:312-320`).

**Given** the temp directory is writable and its current `FCB_TMP_prev_*` count is recorded — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null | wc -l` returns the baseline count  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured, including the model tree — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-11-before.png"}' | & cua-driver call get_window_state`  

**When** a preview whose operation SUCCEEDS is run  
**And** a preview whose operation FAILS its post-verify is run, for example a pad on an unconstrained sketch that leaves an invalid object  
**And** a preview whose operation RAISES is run, for example a feature naming an object that does not exist  
**And** the remaining temp directories are counted after each  

**Then** the success path leaves nothing — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null | wc -l` is unchanged from the baseline after the succeeding preview  
**And** the failure path leaves nothing — verify: the same count is unchanged after the failing preview  
**And** the exception path leaves nothing — verify: the same count is unchanged after the raising preview  
**And** the failure still returned an envelope — verify: the failing preview's `status` is `SPEC_FAILED` or `RECOMPUTE_ERROR`, not a raised exception  
**And** the exception still returned an envelope — verify: the raising preview's `status` is a closed-set value with a `detail.message`  
**And** cleanup never masked the outcome — verify: each preview's `detail.message` names the real cause, not a cleanup failure  
**And** no TempDoc is left open in FreeCAD — verify: `document_list` reports no `FCB_TMP_prev_` handle after any of the three  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-11-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-11-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, the model tree carrying no `FCB_TMP_prev_` item, no new object in the viewport, no dialog raised. `document_list` is bridge output, so a preview copy it omits from its own answer is exactly what that assertion cannot catch — the tree in the image is the independent check. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -rf "$TEMP"/FCB_TMP_prev_*
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-12: The snapshot directory is removed on commit, abort and error

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (snapshot lifecycle), `verification-design.md` §rollback

**Host**: H1 inline. `temp_snapshot_path` mints `tempfile.mkdtemp(prefix="FCB_TMP_snap_")`
(`usecases/transaction.py:94`) and `_delete_snapshot` (`usecases/transaction.py:98-117`) empties
and removes it.

**Two keep-cases are deliberate, not leaks.** (a) Unproven rollback: `RollbackNotProven` keeps
the snapshot and names it in `mutation.snapshot_path`, because it is the only pre-mutation copy
and restoring is an operator decision (`usecases/transaction.py:584-601`). (b) Committed but
unhashable: the commit landed and cannot be fingerprinted, so `rolled_back` is `False`, the
status is `SPEC_FAILED`, and the snapshot is kept and named
(`usecases/transaction.py:375-391`). Both MUST retain the directory.

**Given** the temp directory `FCB_TMP_snap_*` count is recorded as the baseline — verify: `ls -d "$TEMP"/FCB_TMP_snap_* 2>/dev/null | wc -l` returns the baseline count  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-12-before.png"}' | & cua-driver call get_window_state`  

**When** a mutation that COMMITS is run  
**And** a mutation that FAILS post-verify and rolls back provably is run  
**And** a mutation whose commit raises is run  
**And** `FCB_TMP_snap_*` directories are counted after each  

**Then** a committed mutation leaves no snapshot — verify: the directory count equals the baseline after the committing mutation  
**And** the committed envelope reports no snapshot path — verify: `structured_content.mutation.snapshot_path` is `null`  
**And** a proven rollback leaves no snapshot — verify: the count equals the baseline after the rolled-back mutation  
**And** the rolled-back envelope names its proof — verify: `mutation.rollback_proven` is `rolled_back_verified` or `rolled_back_via_snapshot`  
**And** a failed commit leaves no snapshot — verify: the count equals the baseline after the raising commit  
**And** an UNPROVEN rollback deliberately KEEPS its snapshot — verify: the envelope `text` starts `Mutation failed and its rollback could not be proven: ` and the named `mutation.snapshot_path` directory still exists on disk  
**And** a committed-but-unhashable result deliberately KEEPS its snapshot — verify: the envelope has `mutation.rolled_back` `false`, `status` `SPEC_FAILED`, and a non-null `mutation.snapshot_path` that exists on disk  
**And** both keep-cases are named to the operator — verify: `mutation.snapshot_path` is an absolute path the operator can act on  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-12-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-12-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. Two of the three mutations claim a rollback; a rollback the envelope reported as proven while the geometry stayed changed is exactly what the `rollback_proven` assertion cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Remove ONLY the directories the deliberate keep-cases created, after the operator
# has decided whether to restore from them.
rm -rf "$TEMP"/FCB_TMP_snap_*
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-13: Cleanup only touches reserved-prefix paths

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (cleanup scope), `verification-design.md` §rollback

**Host**: H1 inline. Both cleanup helpers gate on the directory's basename prefix before emptying
it: `_delete_snapshot` (`usecases/transaction.py:105-111`) and `_remove_tempdir`
(`usecases/preview.py:327-336`). A non-prefixed path has only the single file removed
(snapshot case) or is left entirely alone (preview case).

**Given** a scratch directory with a non-reserved name containing two files is prepared — verify: `ls "$TEMP"/not-reserved` lists `keep-a.txt` and `keep-b.txt`  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-13-before.png"}' | & cua-driver call get_window_state`  

**When** `"$TEMP"/not-reserved/` is created holding `keep-a.txt` and `keep-b.txt`  
**And** the snapshot cleanup helper is driven against `"$TEMP"/not-reserved/keep-a.txt`  
```bash
uv run python -c "from freecad_buddy.usecases.transaction import _delete_snapshot; _delete_snapshot(r'<TEMP>/not-reserved/keep-a.txt')"
```
**And** the preview cleanup helper is driven against a file inside the same directory  
```bash
uv run python -c "from freecad_buddy.usecases.preview import _remove_tempdir; _remove_tempdir(r'<TEMP>/not-reserved/keep-b.txt')"
```
**And** the directory is listed  

**Then** the named snapshot file was removed — verify: `keep-a.txt` no longer exists  
**And** the sibling file survived — verify: `keep-b.txt` still exists after the snapshot-helper call  
**And** the non-reserved directory survived — verify: `"$TEMP"/not-reserved/` still exists  
**And** the preview helper removed nothing — verify: `keep-b.txt` still exists after the preview-helper call  
**And** neither helper raised — verify: both commands exit `0`  
**And** a reserved-prefix directory IS emptied — verify: repeating the snapshot call against a real `FCB_TMP_snap_*` directory removes the directory and all its contents  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-13-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-13-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised, and the open document still present. The helpers ran in a separate interpreter; a helper that reached into the live application's files while exiting `0` is what the exit-code assertion cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -rf "$TEMP"/not-reserved
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-14: The bridge writes into the user's document folder only via an explicit path

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (write scope), `mcp-tools-design.md` §5 (exports)

**Host**: H1 inline and the H2 proxy.

**Given** a user document folder is chosen and its full file listing plus modification times are recorded — verify: `ls -l "<user document folder>"` is captured as the first listing  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-14-before.png"}' | & cua-driver call get_window_state`  

**When** the folder listing with modification times is recorded as the **first listing**  
**And** the full read-only sweep is run: `document_open`, every `query_*`, every `verify_*`, `preview_dry_run`, `document_close`  
**And** the folder listing is recorded again as the **post-sweep listing**  
**And** one `export_stl` with an explicit `path` INSIDE that folder is run, and one `document_save`  
**And** the folder listing is recorded as the **third listing**  

**Then** reads created no file — verify: the post-sweep listing has the same file names as the first listing  
**And** reads modified no file — verify: every modification time in the post-sweep listing equals its first-listing value  
**And** `preview_dry_run` wrote nothing there — verify: no `FCB_TMP_prev_` file appears in the post-sweep listing  
**And** no snapshot was written there — verify: no `FCB_TMP_snap_` entry appears in the post-sweep listing  
**And** the explicit export wrote exactly one new file — verify: the third listing adds only the requested `path`  
**And** `document_save` touched only the document — verify: only the `.FCStd` file's modification time changed, plus its `.FCBak` if FreeCAD writes one  
**And** no audit log was written there — verify: no `freecad-buddy-audit.jsonl` appears in the folder unless `FREECAD_BUDDY_AUDIT_LOG` explicitly named it (see TC-99-06)  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-14-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-14-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised by the sweep or the export. The sweep was declared read-only; a `query_*` or `preview_dry_run` that reported success while altering the human's model is exactly what a directory listing cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "<user document folder>/tc11-export.stl"
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-15: The audit log is append-only

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (audit), `data-contracts-design.md` §audit-record

**Host**: H1 inline. `AuditSink._write` (`adapters/audit_log.py:43-47`) opens the file in `"a"`
mode under a lock and writes one line. The module docstring states the sink never truncates,
rotates, or reads it.

**Given** a scratch audit-log path is set — verify: `echo $FREECAD_BUDDY_AUDIT_LOG` prints `$RUN_DIR/evidence/tc-11-15-append.jsonl`  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-15-before.png"}' | & cua-driver call get_window_state`  

**When** a batch of mutations is run against the scratch audit log and the line count plus a digest of the whole file are recorded  
**And** a second batch is run against the same file  
**And** the file is compared to the recorded state  
**And** the source is searched for any read, truncate or rotate of the audit path  

**Then** the second batch only appended — verify: the first N lines of the file are byte-identical to the first-batch content  
**And** the line count grew — verify: the post-comparison line count is greater than the first-batch count  
**And** no line was rewritten — verify: the digest of the first N lines equals the first-batch digest  
**And** the file is opened append-only — verify: `grep -n 'open(self._path, "a"' src/freecad_buddy/adapters/audit_log.py` returns line 46  
**And** no bridge tool reads the audit log — verify: `grep -rn "FREECAD_BUDDY_AUDIT_LOG\|audit.jsonl" src/freecad_buddy/usecases/ src/freecad_buddy/contracts/` returns nothing  
**And** no rotation or truncation exists — verify: `grep -rniE "rotate|truncate|\"w\"|'w'" src/freecad_buddy/adapters/audit_log.py` returns nothing  
**And** writes are serialized — verify: the file after a concurrent two-writer run contains no interleaved partial line; every line parses as JSON  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-15-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-15-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. Two batches of mutations ran on the separate H1 host; a batch that reached across into the human's model is what the audit-file assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-11-15-append.jsonl"
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-16: The session token never appears in results, artifacts or reports

**Priority**: High
**Design Ref**: `security-and-service-design.md` §2 (token handling), `data-contracts-design.md` §envelope

**Host**: the in-FreeCAD RPC listener plus the H2 proxy. The token leaves the listener only via
the discovery file (`adapters/rpc_listener.py:182-203`); the handshake result carries
`contract_version`, `freecad_version` and `capabilities` only (`adapters/rpc_listener.py:294-298`).

**Credential hygiene**: the token is a live secret. Hold it in a shell variable for the `grep -F`
calls and never write it, or any file containing it, into `$RUN_DIR/evidence/`. Report only the
masked value and the grep verdicts.

**Given** the current session token is recorded from the discovery file, into a shell variable and not into the run folder — verify: `<token>` is set and its masked form is recorded in the run report  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-16-before.png"}' | & cua-driver call get_window_state`  

**When** a representative set of tools is run covering `query_*`, `verify_*`, `export_*`, one mutation, and `query_screenshot`  
**And** every produced envelope, every render artifact, the audit log, and both log files are searched for the token string  

**Then** no envelope carries the token — verify: `grep -F "<token>" "$RUN_DIR/evidence/tc-11-16-e2e-report.json"` returns nothing; report only the verdict, never the matched text  
**And** no render artifact carries it — verify: `grep -aF "<token>" "$RUN_DIR/evidence/tc-11-16-"*.png` returns nothing  
**And** the audit log does not carry it — verify: `grep -F "<token>" "$RUN_DIR/evidence/tc-11-16-audit.jsonl"` returns nothing  
**And** the addon log does not carry it — verify: `grep -F "<token>" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns nothing  
**And** the proxy log does not carry it — verify: `grep -F "<token>" "$APPDATA/FreeCAD/v1-1/freecad-buddy/mcp-proxy.log"` returns nothing  
**And** the handshake reply does not echo it — verify: the `rpc_hello` result object has exactly the keys `contract_version`, `freecad_version`, `capabilities`  
**And** `query_capabilities` does not expose it — verify: the envelope's `structured_content` contains no field whose value equals the token  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-16-before.png` and shows no token text — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-16-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised, and no token text legible in any panel, title bar or status line. The sweep included one mutation and `query_screenshot`; a mutation that reported `OK` while altering the human's model, or a token rendered into a visible panel, is exactly what the `grep -F` verdicts cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```
```
mcp document_close { doc: "<handle>" }
```
