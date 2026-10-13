# TC-11: Security Posture & Artifact Hygiene

Validates the shipped security controls and the temporary-artifact lifecycle. AD-4 says typed
tools come first and `script_exec` covers the operations no typed tool covers. `script_exec` is on
by default, the operator can turn it off, it is unregistered when it is off, and every call is
audit-logged with its source. AD-20 says a reserved-prefix temporary document must never outlive
the call that made it. AD-25 says every temp file a host writes lives in that host's own session
folder under the workdir, and a sweep at bridge start removes only the leftovers of hosts that are
gone. This file also asserts that the bridge writes nothing into the user's document folder on its
own, and that the audit log is append-only.

**Not covered here.** Bearer-token authentication and `Origin` validation on the HTTP endpoint
are AD-3 requirements the code does not implement. They are asserted as expected failures in
`TC-99-ad-conformance-gaps.md` (TC-99-01 and TC-99-02). The only transport control that ships is
the loopback bind, tested in TC-11-05 and TC-11-06. The AD-25 parts the code does not implement
(the `snap/ exports/ audit.log` layout, a session-named workdir, the headless default location and
the audit log location) are TC-99-04, TC-99-05 and TC-99-06.

**Evidence hierarchy.** We are building the MCP bridge, so the bridge's own output can never be
the test result. A `cua-driver` pixel capture of the real FreeCAD window, `Read` and judged by the
agent, is the test result. Filesystem permissions, exit codes, audit lines and logs read directly
are corroborating, and they carry most of the weight in this security file — keep every one of
those assertions. MCP envelope fields, statuses and `query_screenshot` renders are claims under
test, never evidence. A bridge that reports a refusal while having already executed the thing it
claims to have refused passes every string assertion and fails the user completely; commit
`636fb8a` fixed exactly that class of defect, a correct-looking report over a wrong reality.

**Host**: H1 headless for TC-11-02, TC-11-03, TC-11-04, TC-11-08, TC-11-11, TC-11-12, TC-11-13
and TC-11-15; H1 headless and the H2 proxy for TC-11-01, TC-11-10, TC-11-14 and TC-11-17; the H2
GUI proxy for TC-11-06; the in-FreeCAD RPC listener for TC-11-05, TC-11-07 and TC-11-09; the
listener plus the H2 proxy for TC-11-16; the GUI addon plus H1 headless for TC-11-18 and TC-11-19.
Most scenarios here are filesystem, process-environment or static-source assertions with no
visible model effect: each one opens a golden model in the GUI as an untouched baseline, and its
closing visual asserts the security check never reached the live application.

H1 is two processes. The front (`hosts/headless/entry.py`) speaks MCP over stdio, writes the
adapter audit lines and never imports FreeCAD. It starts the worker (`hosts/headless/worker.py`)
with its own interpreter (`sys.executable`), and the worker imports FreeCAD. Start H1 with the
`fcb` env interpreter so the worker can import FreeCAD, and set each environment variable on that
command; the worker inherits it:

```bash
"$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline
```

## Preconditions

- [ ] FreeCAD 1.1.x installed (verify: `ls "$FREECAD_EXE"`); the build under test is the live version: `query_capabilities.freecad_version`, read once at the start of the run and written `<live version>` below
- [ ] Golden and fault `.FCStd` files have no `GuiDocument.xml` and open with every object hidden. After each `document_open` of such a file, and before any fit or render of it, run **Show All**: `cua-driver call invoke_menu { pid, window_id, path: ["View","Visibility","Show All Objects"] }`. A fit before it returns `SPEC_FAILED view_fit.nothing_to_frame`.
- [ ] micromamba `fcb` env is H1-capable (verify: `"$FCB_PYTHON" -c "import FreeCAD, mcp"`)
- [ ] The `script_exec` posture is the default in the shell used for the default-posture scenarios and in the GUI: none of `FREECAD_BUDDY_SCRIPT_EXEC`, `FREECAD_BUDDY_UNATTENDED` and `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED` is set, and the GUI's **Allow script_exec** preference (Edit > Preferences > FreeCAD Buddy, key `ScriptExec`) is at its default, on (verify: `env | grep -E 'FREECAD_BUDDY_(SCRIPT_EXEC|UNATTENDED)'` returns nothing, and the `operator settings:` line in `addon.log` contains `FREECAD_BUDDY_SCRIPT_EXEC='1' (preference)`, `FREECAD_BUDDY_UNATTENDED='' (unset)` and `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED='' (unset)`)
- [ ] The host machine has a non-loopback IPv4 address for the bind scenarios (verify: `ipconfig | grep IPv4`)
- [ ] FreeCAD GUI is running with a 3D view open, so each scenario's closing visual has a baseline (verify: the FreeCAD window shows a 3D view; confirm by looking at a `cua-driver` capture, not by an MCP field)
- [ ] Golden models are present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` returns a `QOpenGLWidget`)
- [ ] The GUI's own **Fit All** toolbar button is reachable, as the non-MCP framing path (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` lists a `Fit All` toolbar element with an `element_token`; clicking it returns `route: "accessibility"` and reframes the view. `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`.)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)

**Framing rule for every scenario below.** The `before.png` is captured AFTER the same fit as the
`after.png`, so the two images share a camera and a difference between them means a real change,
not a camera move.

---

### TC-11-01: script_exec is registered by default

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (exec gating), `mcp-tools-design.md` §5 (tool surface), spine AD-4

**Host**: H1 headless and the H2 proxy. `Capabilities.from_env` reads `FREECAD_BUDDY_SCRIPT_EXEC`
as on when it is unset (`usecases/capabilities.py:37-52`). `registered_tools` lists `script_exec`
only when `exec_registered(caps)` is true (`adapters/mcp_server.py:78-86`), and the proxy's
`build_proxy_registry` appends `SCRIPT_EXEC_SPEC` under the same condition
(`hosts/rpc_proxy.py:101-102`).

**Given** none of the three exec variables is set — verify: `env | grep -E 'FREECAD_BUDDY_(SCRIPT_EXEC|UNATTENDED)'` returns nothing  
**And** the GUI started at the default posture — verify: the `operator settings:` line in `addon.log` contains `FREECAD_BUDDY_SCRIPT_EXEC='1' (preference)`  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-01-before.png"}' | & cua-driver call get_window_state`  

**When** the H1 host is started with that environment and a scratch audit log, and its tools are listed through an MCP stdio client  
```bash
FREECAD_BUDDY_AUDIT_LOG=$RUN_DIR/evidence/tc-11-01-audit.jsonl \
  "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline 2> "$RUN_DIR/evidence/tc-11-01-h1.stderr.log"
```
**And** on H1, `document_create { label: "tc11-01" }` is called, then `script_exec { doc: "<h1 handle>", code: "result = len(doc.Objects)" }`  
**And** the proxy's tools are listed at `http://127.0.0.1:8765/mcp`  
**And** `query_capabilities {}` is called on both hosts  

**Then** the H1 surface is the live count — verify: the `tools/list` length is the typed tool count plus one (46 with the shipped catalog)  
**And** `script_exec` is listed on H1 — verify: a listed tool has `name` equal to `script_exec`  
**And** the proxy surface matches — verify: the proxy's `tools/list` has the same length and also lists `script_exec`  
**And** the operator is warned at startup — verify: `tc-11-01-h1.stderr.log` contains `SECURITY: script_exec ENABLED: any MCP client of this bridge can run Python with your user rights`, and the GUI's `addon.log` has the same line from its start  
**And** capabilities report it — verify: `structured_content.exec_enabled` is `true` in `query_capabilities` on both hosts  
**And** the call runs — verify: the `script_exec` envelope `status` is `OK` and `structured_content.value_repr` is `'0'`  
**And** the call is audited — verify: `grep '"tool": "script_exec"' "$RUN_DIR/evidence/tc-11-01-audit.jsonl"` returns two `"event": "exec"` lines; the second carries `verify_verdict` `OK`  
**And** no retired exec switch remains — verify: `grep -rn --include=*.py "ALLOW_EXEC\|AllowExec\|debug_exec" src/` returns nothing  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-01-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-01-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. The `script_exec` call ran on the separate H1 host; a call that reached across into the human's application is what the envelope and audit assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-11-01-audit.jsonl"
# Stop the H1 host (close its stdin); its worker exits with it.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-02: The script_exec posture follows the operator switches

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (operator flag), `mcp-tools-design.md` §5, spine AD-4

**Host**: H1 headless. `Capabilities.from_env` (`usecases/capabilities.py:37-52`) reads
`FREECAD_BUDDY_SCRIPT_EXEC` as on only when it is unset or exactly `"1"`, and reads
`FREECAD_BUDDY_UNATTENDED` and `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED` as on only when they are
exactly `"1"`. `exec_registered` (`usecases/capabilities.py:54-60`) then needs the switch on, and
an unattended run also needs the unattended opt-in. No tool, RPC call or wire field can change the
switches after start.

**Given** the operator accepts enabling arbitrary code execution for the runs that turn it on — verify: the operator's acceptance is recorded in the run report  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-02-before.png"}' | & cua-driver call get_window_state`  

**When** the H1 host is started once for each environment below, and on each start the tools are listed, `query_capabilities` is called, and stderr is kept  
```bash
FREECAD_BUDDY_SCRIPT_EXEC=0                                                 "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline 2> "$RUN_DIR/evidence/tc-11-02-a.stderr.log"
FREECAD_BUDDY_SCRIPT_EXEC=true                                              "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline 2> "$RUN_DIR/evidence/tc-11-02-b.stderr.log"
FREECAD_BUDDY_UNATTENDED=1                                                  "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline 2> "$RUN_DIR/evidence/tc-11-02-c.stderr.log"
FREECAD_BUDDY_UNATTENDED=1 FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1           "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline 2> "$RUN_DIR/evidence/tc-11-02-d.stderr.log"
FREECAD_BUDDY_UNATTENDED=1 FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=true        "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline 2> "$RUN_DIR/evidence/tc-11-02-e.stderr.log"
FREECAD_BUDDY_UNATTENDED=yes                                                "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline 2> "$RUN_DIR/evidence/tc-11-02-f.stderr.log"
```

**Then** `FREECAD_BUDDY_SCRIPT_EXEC=0` turns it off — verify: run `a` lists the typed tool count (45 with the shipped catalog), no tool named `script_exec`, and `exec_enabled` `false`  
**And** any value other than exactly `1` turns it off — verify: run `b` gives the same result as run `a`  
**And** an unattended run turns it off — verify: run `c` gives the same result as run `a`  
**And** the unattended opt-in turns it on again — verify: run `d` lists the typed count plus one, including `script_exec`, and `exec_enabled` is `true`  
**And** the opt-in needs exactly `1` — verify: run `e` gives the same result as run `a`  
**And** the unattended mark needs exactly `1` — verify: run `f` gives the same result as run `d`: `FREECAD_BUDDY_UNATTENDED=yes` does not mark the run unattended  
**And** the operator is warned only when it is on — verify: the stderr logs of runs `d` and `f` contain `SECURITY: script_exec ENABLED`; the logs of runs `a`, `b`, `c` and `e` do not  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-02-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-02-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. Two of the six runs registered the exec tool; a run that reported the tool absent while still executing on the live application is what the count assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
unset FREECAD_BUDDY_SCRIPT_EXEC FREECAD_BUDDY_UNATTENDED FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-03: Every script_exec call is audit-logged with its source

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (audit of exec), `data-contracts-design.md` §audit-record, spine AD-4

**Host**: H1 headless. The H1 front writes the `before` line of an exec call ahead of execution
and the `after` line when it returns (`adapters/mcp_server.py:276-291`). `AuditSink._record`
(`adapters/audit_log.py:51-69`) writes `event:"exec"` and also persists the executed `code`
string, not only its digest. `script_exec` runs outside the AD-5 bracket, so neither line carries
a fingerprint.

**Given** the default posture: none of the three exec variables is set — verify: `env | grep -E 'FREECAD_BUDDY_(SCRIPT_EXEC|UNATTENDED)'` returns nothing  
**And** a known audit-log path is set — verify: `echo $FREECAD_BUDDY_AUDIT_LOG` prints `$RUN_DIR/evidence/tc-11-03-audit.jsonl`  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-03-before.png"}' | & cua-driver call get_window_state`  

**When** the H1 host is started with the audit log pointed at the scratch file  
```bash
FREECAD_BUDDY_AUDIT_LOG=$RUN_DIR/evidence/tc-11-03-audit.jsonl "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline
```
**And** `document_create { label: "tc11-03" }` is called, then one `script_exec { doc: "<h1 handle>", code: "result = doc.Name" }`  
**And** the resulting audit lines are read  
```bash
python3 -c "import json;[print(json.loads(l)['event'], json.loads(l)['tool'], json.loads(l).get('params_digest')) for l in open('$RUN_DIR/evidence/tc-11-03-audit.jsonl')]"
```

**Then** two lines were written for the one call — verify: `grep -c '"tool": "script_exec"' "$RUN_DIR/evidence/tc-11-03-audit.jsonl"` returns `2`  
**And** both carry the exec event — verify: both lines have `"event": "exec"`  
**And** both carry a params digest — verify: each line's `params_digest` is a 64-character hexadecimal string  
**And** the digests match each other — verify: the `before` and `after` lines carry the same `params_digest`  
**And** the executed source is persisted — verify: both lines carry a `code` field equal to the submitted code string  
**And** the `before` line was written ahead of execution — verify: the first line has no `verify_verdict` key  
**And** the after line carries the verdict — verify: the second line has `verify_verdict` `OK`  
**And** no fingerprint is claimed — verify: `fingerprint_before` is `null` on both lines  
**And** each line is a valid audit record — verify: each line's `schema` is `fcb.audit-record/1`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-03-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-03-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. The exec ran on the separate H1 host; an exec that reached across into the human's application is what the audit-file assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-11-03-audit.jsonl"
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-04: Typed tools come first and script_exec is never previewable

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (AD-4), `mcp-tools-design.md` §5 (previewable operations)

**Host**: H1 headless. AD-4 makes the typed `sketch_*`/`feature_*`/`document_*` tools the verified
mutation path and `script_exec` the path for the rest. `preview_op_table`
(`hosts/tool_catalog.py:986-1004`) is built from the `sketch_*` and `feature_*` spec lists only, so
`script_exec` is excluded structurally rather than by a name list.

**Given** the default posture: none of the three exec variables is set — verify: `env | grep -E 'FREECAD_BUDDY_(SCRIPT_EXEC|UNATTENDED)'` returns nothing  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-04-before.png"}' | & cua-driver call get_window_state`  

**When** the H1 host is started, the tool surface is listed, and every name is inspected  
**And** `preview_dry_run { doc: "<h1 handle>", operation: { tool: "script_exec", args: { code: "result = 1" } } }` is called on a document made with `document_create`, and the refusal is read  
**And** `preview_dry_run` is called the same way with `tool: "no_such_tool"`, a name that is not a tool at all  

**Then** `script_exec` is the only generic code tool — verify: `grep -riE '"(exec|eval|script|run_python|run_code)"' src/freecad_buddy/hosts/tool_catalog.py` matches only `audit_event="exec"` in `SCRIPT_EXEC_SPEC` (`hosts/tool_catalog.py:1051-1071`)  
**And** every other mutating tool is typed — verify: among the live count of listed names (46 by default), no mutating name falls outside the `document_*`, `sketch_*`, `feature_*` and `export_*` families, `view_fit_viewport` and `script_exec`  
**And** `script_exec` is not previewable — verify: previewing it returns `status=INVALID_INPUT` with `detail.message` starting `not a previewable mutation tool: 'script_exec'`  
**And** the refusal lists what IS previewable — verify: `detail.message` contains `(previewable: ` followed by `sketch_`/`feature_` names only  
**And** an unknown name is refused the same way — verify: the third call returns `status=INVALID_INPUT` with the same `not a previewable mutation tool:` prefix  
**And** every input schema is closed — verify: `python3 -c "import json;s=json.load(open('.../tool_surface.json'));print(all(t['input_schema'].get('additionalProperties') is False for t in s))"` returns `True`  
**And** an untyped extra argument is rejected — verify: any tool called with an undeclared key returns the schema refusal `Input validation error: …`, not an envelope  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
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
(`adapters/rpc_listener.py:133`) and `bind` binds exactly that
(`adapters/rpc_listener.py:176-187`).

**Given** FreeCAD GUI is running with the addon loaded — verify: `netstat -ano | grep ":<port>" | grep LISTENING` shows the listener  
**And** the machine's LAN IPv4 address is known — verify: `ipconfig | grep IPv4`  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-05-before.png"}' | & cua-driver call get_window_state`  

**When** the listener port is read from the discovery file  
**And** the bound address is confirmed  
```bash
netstat -ano | grep ":<port>" | grep LISTENING
```
**And** a TCP connect to `<LAN-IP>:<port>` is attempted  
**And** the proxy is stopped, and a loopback `rpc_hello` is sent with the discovery token  

**Then** the listener is bound to `127.0.0.1`, not `0.0.0.0` — verify: the `netstat` line shows the local address as `127.0.0.1:<port>`  
**And** the discovery record agrees — verify: the `host` field in `rpc-<pid>.json` is `127.0.0.1`  
**And** a LAN-IP connect is refused — verify: the connect raises `ConnectionRefusedError` or times out with no handshake  
**And** a loopback connect still succeeds — verify: with the proxy stopped, a connect to `127.0.0.1:<port>` completes `rpc_hello` and returns `contract_version` `"1"`. While the proxy holds the session, a raw `rpc_hello` while the proxy holds the session gets `-32000 bridge busy: another client session is active` (AD-26), which also proves the listener answered  
**And** no other interface is listening on that port — verify: the `netstat` output shows exactly one LISTENING line for that port  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-05-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-05-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised by the refused LAN connect. A connect the listener reported as refused while still serving it is what the socket assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```
Restart the proxy by hand with the addon's command line (from `Win32_Process.CommandLine` of the spawned proxy), setting on that command each `FREECAD_BUDDY_*` value from the last `operator settings:` line of `addon.log`. A hand-started proxy reads only the shell's environment (`gui_external/entry.py:142`), not the addon's preference overlay, so without those values its `exec_enabled` and tool count can differ from FreeCAD's posture. When the run uses a non-default posture, restart FreeCAD instead, then `mcp query_capabilities {}` returns `OK`.
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-06: The MCP HTTP endpoint binds loopback only

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §2 (loopback bind), `integration-mcp-clients.md` §transport

**Host**: the H2 GUI proxy. `_HOST = "127.0.0.1"` and `_PORT = 8765` are module constants
(`hosts/gui_external/entry.py:44-45`) and `run()` passes them straight into the uvicorn config
(`hosts/gui_external/entry.py:160`). There is no `--host` or `--port` CLI flag to change them.

**Given** the proxy is serving — verify: `netstat -ano | grep ":8765" | grep LISTENING`  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. This scenario probes the proxy's own bind and the proxy may be unreachable during the probe, so prefer the GUI menu path here.  
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
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Use the GUI menu path if the rebind attempt left the proxy down.  
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

**Host**: the in-FreeCAD RPC listener. `_write_discovery` (`adapters/rpc_listener.py:233-253`)
writes the record then calls `os.chmod(path, 0o600)`. **On Windows `chmod` only sets the read-only
bit, and `0o600` leaves it clear**, so the file keeps the ACL it inherits from its folder. The
default FreeCAD user appdata folder grants owner, SYSTEM and Administrators only. On both
platforms the enforced controls are the loopback bind and the per-session token.

**Credential hygiene**: the discovery file holds a live session token. Do not copy the file, its
contents, or the token into `$RUN_DIR/evidence/`. Record the token only as a masked value, for
example the first four characters followed by its length.

**Given** FreeCAD GUI is running with the addon loaded — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-"*.json` lists a discovery file for the running pid  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-07-before.png"}' | & cua-driver call get_window_state`  

**When** the discovery file is located  
```bash
ls -l "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-"*.json
```
**And** its contents are read, in place, without copying them into the run folder  
**And** a handshake with a wrong token is attempted  

**Then** exactly one discovery file exists per live listener pid — verify: the filename is `rpc-<pid>.json` where `<pid>` is the running FreeCAD pid  
**And** the file is not world-readable — verify: on POSIX `stat -c %a` returns `600`; on Windows `attrib` shows the read-only bit clear, and `icacls "<discovery file>"` lists only the owner, `NT AUTHORITY\SYSTEM` and `BUILTIN\Administrators`  
**And** the record carries a token — verify: the parsed JSON has a non-empty `token` string; assert on the masked value only, and keep the token itself out of `$RUN_DIR/evidence/`  
**And** the record carries the contract version — verify: `contract_version` is `"1"`  
**And** a wrong token is refused — verify: the handshake reply is an error frame with `message` exactly `auth failed`  
**And** the refusal discloses nothing — verify: that error frame carries no `data.supported` and no capabilities  
**And** the file is removed when the listener stops — verify: after FreeCAD quits, `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<pid>.json"` returns not-found  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
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

**Host**: H1 headless. `build_server` logs the warning when `auto_approve_enabled(caps)` is
true (`adapters/mcp_server.py:224-225`). `AuditSink.approval` (`adapters/audit_log.py:88-103`)
writes one `event:"approval"` line naming what the approval covered.

**Given** the operator accepts running mutations without a confirm token for this scenario — verify: the operator's acceptance is recorded in the run report  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-08-before.png"}' | & cua-driver call get_window_state`  

**When** the host is started with `FREECAD_BUDDY_AUTO_APPROVE` unset (auto-approve is on by default) and a scratch audit log  
```bash
env -u FREECAD_BUDDY_AUTO_APPROVE FREECAD_BUDDY_AUDIT_LOG=$RUN_DIR/evidence/tc-11-08-approve.jsonl \
  "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline
```
**And** one geometry mutation is run with NO `confirm` argument  
**And** the same is repeated with `FREECAD_BUDDY_AUTO_APPROVE=0`, and again with `FREECAD_BUDDY_AUTO_APPROVE=true`  

**Then** the operator is warned at startup — verify: stderr contains `SECURITY: mutation auto-approve ENABLED (to require preview_id, clear Auto-approve mutations in the FreeCAD GUI: Edit > Preferences > FreeCAD Buddy, or set FREECAD_BUDDY_AUTO_APPROVE=0)`  
**And** the mutation runs without a confirm token — verify: the envelope `status` is `OK` and no `this mutation requires a confirm` message appears  
**And** one approval record was written — verify: `grep -c '"event": "approval"' "$RUN_DIR/evidence/tc-11-08-approve.jsonl"` returns `1`  
**And** the approval names the tool and the switch — verify: that line's `tool` is the mutating tool name, and its `approval` has `"mode": "auto_approve"` and `"source": "FREECAD_BUDDY_AUTO_APPROVE"`  
**And** the approval carries the pre-mutation fingerprint — verify: that line's `fingerprint_before` matches the mutation's own `before` line  
**And** the approval digest matches the mutation's digest — verify: the approval line's `params_digest` equals the `before`/`after` lines' digest  
**And** `0` turns the confirm gate on — verify: the `FREECAD_BUDDY_AUTO_APPROVE=0` run's stderr lacks the warning and the same unconfirmed mutation is refused with `this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id`  
**And** any value other than `1` turns it on too — verify: the `FREECAD_BUDDY_AUTO_APPROVE=true` run gives the same result as the `=0` run  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
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
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-09-before.png"}' | & cua-driver call get_window_state`  

**When** the token is recorded from the discovery file, masked  
**And** FreeCAD is quit and restarted  
**And** the new token is recorded, masked  
**And** a handshake against the new listener is attempted using the OLD token  

**Then** the second token differs from the first — verify: the two recorded `token` values are not equal; compare them in memory and report only the masked values  
**And** the old token is refused — verify: the OLD-token handshake reply is an error frame with `message` exactly `auth failed`  
**And** the connection is closed after refusal — verify: the next `recv` on that socket returns zero bytes  
**And** the new token is accepted — verify: with the restarted proxy stopped, a handshake with the post-restart token returns `contract_version` `"1"`. While the proxy holds the session, the same hello gets `-32000 bridge busy: another client session is active` (AD-26): the token and version checks run before the busy check, so the `auth failed` assertions above hold with the proxy running  
**And** auth is checked before version — verify: a handshake carrying the OLD token AND an unsupported `contract_version` still returns `auth failed`, not `contract version unsupported`  
**And** the stale discovery file did not survive — verify: the pre-restart `rpc-<old pid>.json` no longer exists  
**And** *(visual)* the model is framed — verify: reopen the golden model after the restart and run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. The restart may leave the bridge unready, so prefer the GUI menu path here.  
**And** *(visual)* the restarted window matches `tc-11-09-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-09-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised by the refused OLD-token handshakes. A handshake the listener reported as `auth failed` while still admitting the caller is what the error-frame assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```
Restart the proxy by hand with the addon's command line (from `Win32_Process.CommandLine` of the spawned proxy), setting on that command each `FREECAD_BUDDY_*` value from the last `operator settings:` line of `addon.log`. A hand-started proxy reads only the shell's environment (`gui_external/entry.py:142`), not the addon's preference overlay, so without those values its `exec_enabled` and tool count can differ from FreeCAD's posture. When the run uses a non-default posture, restart FreeCAD instead, then `mcp query_capabilities {}` returns `OK`.
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-10: Reserved-prefix temporary documents never leak into document_list

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-20 TempDoc lifecycle), `mcp-tools-design.md` §5 (preview)

**Host**: H1 headless and the H2 proxy. `_discard_tempdoc` (`usecases/preview.py:346-358`) closes
the copy and removes its directory on the success, failure and exception paths alike. The
docstring states why: a leaked TempDoc is adopted by `document_list` and surfaced to the caller
mislabeled.

**Given** a document with at least one body is open — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** `document_list` currently reports no `FCB_TMP_` handles — verify: `mcp document_list {}` returns no name starting with `FCB_TMP_`  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured, including the model tree — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-10-before.png"}' | & cua-driver call get_window_state`  

**When** the `document_list` result is recorded  
**And** one `preview_dry_run` that succeeds is run  
**And** one `export_step` to an absolute path under `$RUN_DIR/evidence/` is run, then `verify_export_step` with the `export_id` it returned (which re-imports into a fresh `FCB_TMP_` document)  
**And** `document_list` is recorded again  

**Then** the baseline list has no temp handles — verify: no returned name starts with `FCB_TMP_`  
**And** the preview returned a terminal envelope — verify: the `status` is in the closed set  
**And** no preview TempDoc remains — verify: no returned name starts with `FCB_TMP_prev_`  
**And** no export re-import document remains — verify: no returned name starts with `FCB_TMP_`  
**And** the list is identical to the baseline — verify: the final handle set equals the recorded baseline handle set  
**And** the user's own documents were untouched — verify: each pre-existing document's fingerprint digest is unchanged  
**And** no temp directory remains on disk — verify: the host's session temp folder `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/` holds no `FCB_TMP_prev_` entry. On the GUI the agent shell may get "Access is denied" for that folder: list it in-process with `script_exec { doc: "<handle>", code: "import os; from freecad_buddy.usecases.documents import temp_dir; result = sorted(os.listdir(temp_dir()))" }`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-10-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-10-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, the model tree listing only the user's own document with no `FCB_TMP_` item, no new object in the viewport, no dialog raised. `document_list` is bridge output, so a leaked temporary document it omits from its own answer is exactly what the handle-set assertions cannot catch — the tree in the image is the independent check. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-11-10-"*.step
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-11: A preview TempDoc is removed on every exit path

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-20), `mcp-tools-design.md` §5 (preview)

**Host**: H1 headless. The prefix is `FCB_TMP_prev_` (`usecases/preview.py:33`) and it is carried
by the directory AND the filename, because the reopened document takes its `Name` from the file
stem (`usecases/preview.py:316-326`). The directory is minted inside the host's session temp
folder. Start H1 with `FREECAD_BUDDY_WORKDIR=$RUN_DIR/evidence/tc-11-11-workdir`, so the agent
shell can list that folder as `$RUN_DIR/evidence/tc-11-11-workdir/tmp/FCB_TMP_session_*/`.

**Given** H1 runs with the scratch workdir and its session temp folder's `FCB_TMP_prev_*` count is recorded — verify: `ls -d "$RUN_DIR"/evidence/tc-11-11-workdir/tmp/FCB_TMP_session_*/FCB_TMP_prev_* 2>/dev/null | wc -l` returns the baseline count  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured, including the model tree — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-11-before.png"}' | & cua-driver call get_window_state`  

**When** a preview whose operation SUCCEEDS is run  
**And** a preview whose operation FAILS its post-verify is run: a `feature_fillet` whose radius is larger than the edge allows, on a padded box  
**And** a preview whose operation RAISES is run, for example a feature naming an object that does not exist  
**And** the remaining temp directories are counted after each  

**Then** the success path leaves nothing — verify: `ls -d "$RUN_DIR"/evidence/tc-11-11-workdir/tmp/FCB_TMP_session_*/FCB_TMP_prev_* 2>/dev/null | wc -l` is unchanged from the baseline after the succeeding preview  
**And** the failure path leaves nothing — verify: the same count is unchanged after the failing preview  
**And** the exception path leaves nothing — verify: the same count is unchanged after the raising preview  
**And** the failure is reported as a successful preview of a failing diff — verify: the failing preview's `status` is `OK` and `structured_content.diff.validity.status` is `RECOMPUTE_ERROR` (`usecases/preview.py:439-440`)  
**And** the exception still returned an envelope — verify: the raising preview's `status` is a closed-set value with a `detail.message`  
**And** cleanup never masked the outcome — verify: each preview's `detail.message` names the real cause, not a cleanup failure  
**And** no TempDoc is left open in FreeCAD — verify: `document_list` reports no `FCB_TMP_prev_` handle after any of the three  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-11-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-11-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, the model tree carrying no `FCB_TMP_prev_` item, no new object in the viewport, no dialog raised. `document_list` is bridge output, so a preview copy it omits from its own answer is exactly what that assertion cannot catch — the tree in the image is the independent check. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Stop the H1 host first, so its session folder belongs to a dead pid.
rm -rf "$RUN_DIR/evidence/tc-11-11-workdir"
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-12: The snapshot directory is removed on commit, abort and error

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (snapshot lifecycle), `verification-design.md` §rollback

**Host**: H1 headless. `temp_snapshot_path` mints
`tempfile.mkdtemp(prefix="FCB_TMP_snap_", dir=temp_dir())` inside the host's session temp folder
(`usecases/transaction.py:97-108`), and `_delete_snapshot` (`usecases/transaction.py:111-135`)
empties and removes it. Start H1 with `FREECAD_BUDDY_WORKDIR=$RUN_DIR/evidence/tc-11-12-workdir`,
so the agent shell can list the session folder as
`$RUN_DIR/evidence/tc-11-12-workdir/tmp/FCB_TMP_session_*/`.

**Two keep-cases are deliberate, not leaks.** (a) Unproven rollback: `RollbackNotProven` keeps
the snapshot and names it in `mutation.snapshot_path`, because it is the only pre-mutation copy
and restoring is an operator decision (`usecases/transaction.py:697-713`). (b) Committed but
unhashable: the commit landed and cannot be fingerprinted, so `rolled_back` is `False`, the
status is `SPEC_FAILED`, and the snapshot is kept and named
(`usecases/transaction.py:446-464`). Both MUST retain the directory.

**Fault reproducers.** No typed tool can make a commit raise, a rollback unprovable or a commit
unhashable, so each case is driven by a `script_exec` patch of the bridge's own module in the H1
worker, applied before the mutation and removed after it. Each patch replaces a module attribute
that `_bracket` looks up at call time:

- commit raises: wrap `transaction.run_mutation` so it passes a proxy of the document whose
  `commitTransaction` raises (FreeCAD's document type is immutable, so the method cannot be
  replaced on it):
  ```python
  import freecad_buddy.usecases.transaction as t
  class _CommitRaises:
      def __init__(self, d): object.__setattr__(self, "_d", d)
      def __getattr__(self, n): return getattr(self._d, n)
      def __setattr__(self, n, v): setattr(self._d, n, v)
      def commitTransaction(self): raise RuntimeError("tc-11-12 forced commit failure")
  t._fcb_saved = t.run_mutation
  def _wrapped(document, *a, **k):
      out, env = t._fcb_saved(_CommitRaises(document), *a, **k)
      return getattr(out, "_d", out), env
  t.run_mutation = _wrapped
  ```
- unproven rollback: `t._fcb_saved = t._prove_rollback`, then replace `t._prove_rollback` with a
  function that raises `t.RollbackNotProven("tc-11-12 forced", document, fp_before)`;
- committed but unhashable: `t._fcb_saved = t.fingerprint`, then replace `t.fingerprint` with a
  function that raises. The confirm gate takes the pre-mutation fingerprint itself and passes it in
  (`usecases/features.py:372-386`), so on a passing mutation the bracket's only call of
  `t.fingerprint` is the after-fingerprint, taken after the commit (`usecases/transaction.py:673-674`).

Restore after each case with `t.<name> = t._fcb_saved`. If a patch cannot be applied on the build
under test, record the case as not run with the reason; never pass it.

**Given** H1 runs with the scratch workdir and its session folder's `FCB_TMP_snap_*` count is recorded as the baseline — verify: `ls -d "$RUN_DIR"/evidence/tc-11-12-workdir/tmp/FCB_TMP_session_*/FCB_TMP_snap_* 2>/dev/null | wc -l` returns the baseline count  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-12-before.png"}' | & cua-driver call get_window_state`  

**When** a mutation that COMMITS is run  
**And** a mutation that FAILS post-verify and rolls back provably is run  
**And** a mutation whose commit raises is run, under the commit-raises patch  
**And** a mutation that fails post-verify is run under the unproven-rollback patch, and one that passes is run under the unhashable patch  
**And** `FCB_TMP_snap_*` directories in the session folder are counted after each  

**Then** a committed mutation leaves no snapshot — verify: the directory count equals the baseline after the committing mutation  
**And** the committed envelope reports no snapshot path — verify: `structured_content.mutation` has no `snapshot_path` key (the wire block carries it only when a snapshot is kept, `usecases/result_projection.py:119-120`)  
**And** a proven rollback leaves no snapshot — verify: the count equals the baseline after the rolled-back mutation  
**And** the rolled-back envelope names its proof — verify: `mutation.rollback_proven` is `rolled_back_verified` or `rolled_back_via_snapshot`  
**And** a failed commit leaves no snapshot — verify: the count equals the baseline after the raising commit, whose envelope `status` is `SPEC_FAILED` with `RuntimeError: tc-11-12 forced commit failure` in its explanation  
**And** an UNPROVEN rollback deliberately KEEPS its snapshot — verify: the envelope `text` starts `Mutation failed and its rollback could not be proven: ` and the named `mutation.snapshot_path` directory still exists on disk  
**And** a committed-but-unhashable result deliberately KEEPS its snapshot — verify: the envelope has `mutation.rolled_back` `false`, `status` `SPEC_FAILED`, and a non-null `mutation.snapshot_path` that exists on disk  
**And** both keep-cases are named to the operator — verify: `mutation.snapshot_path` is an absolute path under `$RUN_DIR/evidence/tc-11-12-workdir/tmp/FCB_TMP_session_<pid>_<token>/FCB_TMP_snap_<random>/`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-12-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-12-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. Two of the three mutations claim a rollback; a rollback the envelope reported as proven while the geometry stayed changed is exactly what the `rollback_proven` assertion cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# Restore every patched attribute (or stop the H1 host: the patches die with its worker).
# Remove the keep-case directories only after the operator has decided whether to restore
# from them; stop the H1 host first.
rm -rf "$RUN_DIR/evidence/tc-11-12-workdir"
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-13: Cleanup only touches reserved-prefix paths

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (cleanup scope), `verification-design.md` §rollback

**Host**: H1 headless. Both cleanup helpers gate on the directory's basename prefix before
emptying it: `_delete_snapshot` (`usecases/transaction.py:123-128`) and `_remove_tempdir`
(`usecases/preview.py:329-344`). The start sweep has the same prefix rule; TC-11-19 tests it. A non-prefixed path has only the single file removed
(snapshot case) or is left entirely alone (preview case).

**Given** a scratch directory with a non-reserved name containing two files is prepared — verify: `ls "$TEMP"/not-reserved` lists `keep-a.txt` and `keep-b.txt`  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
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
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
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

**Host**: H1 headless and the H2 proxy.

**Given** a user document folder is chosen and its full file listing plus modification times are recorded — verify: `ls -l "<user document folder>"` is captured as the first listing  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
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
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
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

**Host**: H1 headless. `AuditSink._write` (`adapters/audit_log.py:45-49`) opens the file in `"a"`
mode under a lock and writes one line. The module docstring states the sink never truncates,
rotates, or reads it.

**Given** a scratch audit-log path is set — verify: `echo $FREECAD_BUDDY_AUDIT_LOG` prints `$RUN_DIR/evidence/tc-11-15-append.jsonl`  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-15-before.png"}' | & cua-driver call get_window_state`  

**When** a batch of mutations is run against the scratch audit log and the line count plus a digest of the whole file are recorded  
**And** a second batch is run against the same file  
**And** the file is compared to the recorded state  
**And** the source is searched for any read, truncate or rotate of the audit path  

**Then** the second batch only appended — verify: the first N lines of the file are byte-identical to the first-batch content  
**And** the line count grew — verify: the post-comparison line count is greater than the first-batch count  
**And** no line was rewritten — verify: the digest of the first N lines equals the first-batch digest  
**And** the file is opened append-only — verify: `grep -n 'open(self._path, "a"' src/freecad_buddy/adapters/audit_log.py` returns line 48  
**And** no bridge tool reads the audit log — verify: `grep -rn "FREECAD_BUDDY_AUDIT_LOG\|audit.jsonl" src/freecad_buddy/usecases/ src/freecad_buddy/contracts/ | grep -v operator_settings.py` returns only the `usecases/documents.py` docstring line that names the variable as a precedent for the workdir variable. `usecases/operator_settings.py` only names the default path for the GUI host's environment and never opens it  
**And** no rotation or truncation exists — verify: `grep -rniE "rotate|truncate|\"w\"|'w'" src/freecad_buddy/adapters/audit_log.py` returns nothing  
**And** writes are serialized — verify: the file after a concurrent two-writer run contains no interleaved partial line; every line parses as JSON  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
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
the discovery file (`adapters/rpc_listener.py:233-253`); the handshake result carries
`contract_version`, `freecad_version` and `capabilities` only (`adapters/rpc_listener.py:393-397`).

**Credential hygiene**: the token is a live secret. Hold it in a shell variable for the `grep -F`
calls and never write it, or any file containing it, into `$RUN_DIR/evidence/`. Report only the
masked value and the grep verdicts.

**Given** the current session token is recorded from the discovery file, into a shell variable and not into the run folder — verify: `<token>` is set and its masked form is recorded in the run report  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-16-before.png"}' | & cua-driver call get_window_state`  

**When** a representative set of tools is run covering `query_*`, `verify_*`, `export_*`, one mutation, and `query_screenshot`  
**And** every produced envelope, every render artifact, the audit log, and both log files are searched for the token string  

**Then** no envelope carries the token — verify: `grep -F "<token>" "$RUN_DIR/evidence/tc-11-16-e2e-report.json"` returns nothing; report only the verdict, never the matched text  
**And** no render artifact carries it — verify: `grep -aF "<token>" "$RUN_DIR/evidence/tc-11-16-"*.png` returns nothing  
**And** the audit log does not carry it — verify: `grep -F "<token>" "$RUN_DIR/evidence/tc-11-16-audit.jsonl"` returns nothing  
**And** the addon log does not carry it — verify: `grep -F "<token>" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns nothing  
**And** the proxy log does not carry it — verify: `grep -F "<token>" "$APPDATA/FreeCAD/v1-1/freecad-buddy/mcp-proxy.log"` returns nothing  
**And** the handshake reply does not echo it — verify: with the MCP proxy stopped (a raw `rpc_hello` while the proxy holds the session gets `-32000 bridge busy: another client session is active`, AD-26), the `rpc_hello` result object has exactly the keys `contract_version`, `freecad_version`, `capabilities`  
**And** `query_capabilities` does not expose it — verify: the envelope's `structured_content` contains no field whose value equals the token  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-16-before.png` and shows no token text — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-16-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised, and no token text legible in any panel, title bar or status line. The sweep included one mutation and `query_screenshot`; a mutation that reported `OK` while altering the human's model, or a token rendered into a visible panel, is exactly what the `grep -F` verdicts cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# No files written.
```
Restart the proxy by hand with the addon's command line (from `Win32_Process.CommandLine` of the spawned proxy), setting on that command each `FREECAD_BUDDY_*` value from the last `operator settings:` line of `addon.log`. A hand-started proxy reads only the shell's environment (`gui_external/entry.py:142`), not the addon's preference overlay, so without those values its `exec_enabled` and tool count can differ from FreeCAD's posture. When the run uses a non-default posture, restart FreeCAD instead, then `mcp query_capabilities {}` returns `OK`.
```
mcp document_close { doc: "<handle>" }
```

---

### TC-11-17: A script_exec call while it is off is refused, audited and never runs

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (exec gating), `mcp-tools-design.md` §5, spine AD-4

**Host**: H1 headless and the H2 proxy. A client can call `script_exec` by name without reading
`tools/list`. The H1 front refuses an unregistered `script_exec` before any dispatch and still
writes the `exec` audit pair (`adapters/mcp_server.py:243-247`); the refusal text is built at
`adapters/mcp_server.py:322-326`. The proxy has no such branch: its registry holds no
`script_exec` entry when exec is off (`hosts/rpc_proxy.py:101-102`), so the call reaches the
registry's unknown-method refusal (`adapters/rpc_dispatch.py:141`) and never reaches FreeCAD.

**Given** the operator accepts a FreeCAD restart with `script_exec` off — verify: the operator's acceptance is recorded in the run report  
**And** FreeCAD runs with `script_exec` off: started through `_automation/uat/launch_env.sh tc-11-17 "set FREECAD_BUDDY_SCRIPT_EXEC=0"` (`launch_app` has no environment field) — verify: the new `operator settings:` line in `addon.log` contains `FREECAD_BUDDY_SCRIPT_EXEC='0' (env)`, and the new `addon.log` lines contain no `SECURITY: script_exec ENABLED` line  
**And** the GUI audit log line count is recorded — verify: `wc -l "$APPDATA/FreeCAD/v1-1/freecad-buddy/audit.jsonl"`  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-17-before.png"}' | & cua-driver call get_window_state`  

**When** the H1 host is started with `script_exec` off and a scratch audit log  
```bash
FREECAD_BUDDY_SCRIPT_EXEC=0 FREECAD_BUDDY_AUDIT_LOG=$RUN_DIR/evidence/tc-11-17-audit.jsonl "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline
```
**And** on H1, `document_create { label: "tc11-17" }` is called, then `script_exec` is called by name, bypassing `tools/list`: `script_exec { doc: "<h1 handle>", code: "doc.addObject('Part::Box', 'Leak'); doc.recompute()" }`  
**And** on H1, `query_tree_summary { doc: "<h1 handle>" }` is called  
**And** through the proxy at `http://127.0.0.1:8765/mcp`, `query_capabilities {}` is called, then the same `script_exec` call is sent with `doc: "<handle>"`  
**And** through the proxy, `query_tree_summary { doc: "<handle>" }` is called, and the GUI audit log line count is read again  

**Then** H1 refuses the call — verify: the envelope `status` is `INVALID_INPUT` and `detail.message` is exactly `script_exec is off: FREECAD_BUDDY_SCRIPT_EXEC or the ScriptExec preference turned it off, or FREECAD_BUDDY_UNATTENDED=1 is set without FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`  
**And** the denied attempt is still audited — verify: `grep '"tool": "script_exec"' "$RUN_DIR/evidence/tc-11-17-audit.jsonl"` returns two `"event": "exec"` lines that carry the submitted `code`; the second has `verify_verdict` `INVALID_INPUT`  
**And** no code ran on H1 — verify: the H1 `query_tree_summary` text has no `Leak` line  
**And** the GUI reports `script_exec` off — verify: the proxy's `query_capabilities` has `structured_content.exec_enabled` `false`  
**And** the proxy refuses the call — verify: the envelope `status` is `INVALID_INPUT` and `detail.message` is `unknown method: script_exec`  
**And** no code ran in the GUI — verify: the GUI `query_tree_summary` text lists `Box` and no `Leak`  
**And** the call never reached FreeCAD — verify: the GUI audit log line count is unchanged  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-17-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-17-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. The tree in the after image lists no `Leak` object. A refusal that returned the right message while the payload nevertheless ran is exactly what the string assertions above cannot catch, so this image is the test result. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-11-17-audit.jsonl"
# Stop the H1 host (close its stdin).
```
```
mcp document_close { doc: "<handle>" }
```
Quit FreeCAD with `invoke_menu ["File","Exit"]`, then start it again at the default posture with `launch_app`, and confirm the new `operator settings:` line contains `FREECAD_BUDDY_SCRIPT_EXEC='1' (preference)`.

---

### TC-11-18: Every bridge temp file lives in the host's session folder under the workdir

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (temp files), spine AD-25

**Host**: the GUI addon behind the H2 proxy, and H1 headless. When `FREECAD_BUDDY_WORKDIR` is unset
the addon sets it to `<FreeCAD user app data>/freecad-buddy/workdir`
(`usecases/operator_settings.py:89`). `temp_dir` (`usecases/documents.py:61-73`) makes one
`<workdir>/tmp/FCB_TMP_session_<pid>_<token>/` folder per host process, where `<pid>` is the
process that runs the use cases (FreeCAD in the GUI, the worker on H1) and `<token>` is 8 hex
characters. Every bridge temp file is minted inside that folder: the snapshot
(`usecases/transaction.py:107`), the preview copy (`usecases/preview.py:325`), the fingerprint
scratch file (`usecases/fingerprint.py:120`) and the render (`usecases/screenshot.py:187`). None
falls back to the OS temp directory.

The agent shell may get "Access is denied" for the GUI's session folder. List it in-process
instead: `script_exec { doc: "<handle>", code: "import os; from freecad_buddy.usecases.documents import temp_dir; result = (temp_dir(), sorted(os.listdir(temp_dir())))" }`.

**Given** the GUI started with `FREECAD_BUDDY_WORKDIR` unset — verify: the `operator settings:` line in `addon.log` contains `FREECAD_BUDDY_WORKDIR='<FreeCAD user app data>\freecad-buddy\workdir' (default)`  
**And** the reserved-prefix entries directly in the OS temp directory are counted — verify: `find "$TEMP" -maxdepth 1 -name 'FCB_TMP_*' | wc -l` returns the baseline count  
**And** a golden model is open in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed before the baseline capture — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** that framed baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-18-before.png"}' | & cua-driver call get_window_state`  

**When** on the GUI, a document is made with `document_create { label: "tc11-18" }` and given a body, one `feature_*` mutation that commits, and one `preview_dry_run` of a second feature  
**And** `query_screenshot { doc: "<tc11-18 handle>" }` is called and the PNG path in its `resource_link` is recorded  
**And** the session folder is listed in-process with the `script_exec` call above  
**And** the folder names the two minting functions would use are read in-process, without running a mutation: `script_exec { doc: "<tc11-18 handle>", code: "from freecad_buddy.usecases import transaction, preview; result = (transaction.temp_snapshot_path(doc), preview._tempdoc_path())" }`  
**And** the H1 host is started with an explicit workdir, and one mutation and one `query_screenshot` are run on it  
```bash
FREECAD_BUDDY_WORKDIR=$RUN_DIR/evidence/tc-11-18-workdir "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline
ls -R "$RUN_DIR/evidence/tc-11-18-workdir"
```
**And** the reserved-prefix entries directly in the OS temp directory are counted again  

**Then** the GUI workdir is the per-user default — verify: the folder `temp_dir()` returned starts with `<FreeCAD user app data>\freecad-buddy\workdir\tmp\`  
**And** the GUI session folder belongs to this FreeCAD — verify: its name is `FCB_TMP_session_<FreeCAD pid>_<8 hex characters>`, with the pid from `list_windows`  
**And** the render is inside it — verify: the `resource_link` path is `<session folder>\FCB_TMP_shot_<random>.png` and the file exists (read it in-process if the shell is refused)  
**And** a committed mutation and a preview leave no snapshot or preview copy behind — verify: the in-process listing has no `FCB_TMP_snap_` and no `FCB_TMP_prev_` entry  
**And** the snapshot path is minted inside it — verify: the first path is `<session folder>\FCB_TMP_snap_<random>\<document Name>.FCStd`  
**And** the preview path is minted inside it — verify: the second path is `<session folder>\FCB_TMP_prev_<random>\FCB_TMP_prev_<16 hex characters>.FCStd`  
**And** H1 uses the workdir it was given — verify: the `ls -R` listing shows `tmp/FCB_TMP_session_<worker pid>_<8 hex characters>/` holding the H1 render, and nothing else at the top of `tmp/`  
**And** nothing lands in the OS temp directory — verify: the second `find "$TEMP" -maxdepth 1 -name 'FCB_TMP_*'` count equals the baseline  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is identical to `tc-11-18-before.png` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-18-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, whole and framed, no new object in the viewport, no dialog raised. The mutation, preview and render ran on a separate document; a temp file written into the user's own document is what the folder listings cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
script_exec { doc: "<tc11-18 handle>", code: "import os, shutil; [shutil.rmtree(os.path.dirname(p)) for p in (<snapshot path>, <preview path>)]" }
mcp document_close { doc: "<tc11-18 handle>" }
mcp document_close { doc: "<handle>" }
```
```bash
# Stop the H1 host first, so its session folder belongs to a dead pid.
rm -rf "$RUN_DIR/evidence/tc-11-18-workdir"
```

---

### TC-11-19: The start sweep removes only a dead host's leftovers

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (temp files), spine AD-25 (start-of-session sweep)

**Host**: the GUI addon, and H1 headless. Both hosts call `sweep_temp_dir`
(`usecases/documents.py:76-115`) once at start and log
`session-start sweep removed N leftover temp artifact(s)`: the addon at
`hosts/gui_addon/bootstrap.py:139`, the H1 worker at `hosts/headless/worker.py:107`. The sweep
reads only `<workdir>/tmp`. It touches only `FCB_TMP_` entries. It removes a
`FCB_TMP_session_<pid>_<token>` folder only when that pid is dead, and removes any other
`FCB_TMP_` entry at the top of `tmp/`, because no live host writes there. It never scans the OS
temp directory.

**Given** FreeCAD is stopped — verify: `tasklist | grep -i freecad` returns nothing  
**And** the GUI workdir `tmp/` folder holds no `FCB_TMP_` entry from an earlier run — verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/workdir/tmp/"`; with FreeCAD stopped, delete any `FCB_TMP_session_*` folder whose pid is not running  
**And** a live pid the agent owns is started, and it writes its own Windows pid to a file — verify: after the command below, `cat "$RUN_DIR/evidence/tc-11-19-sleeper.pid"` prints one number; record it as `<live pid>`, and `tasklist //FI "PID eq <live pid>"` lists one process  
```bash
"$FCB_PYTHON" -c "import os, time; open(r'$RUN_DIR/evidence/tc-11-19-sleeper.pid', 'w').write(str(os.getpid())); time.sleep(900)" &
```
**And** five entries are planted in `$APPDATA/FreeCAD/v1-1/freecad-buddy/workdir/tmp/`, and one in the OS temp directory — verify: `ls -R` lists each of them  
```bash
T="$APPDATA/FreeCAD/v1-1/freecad-buddy/workdir/tmp"
D=999996   # a multiple of 4 (Windows ignores the low two pid bits); confirm with tasklist that no process has this pid
mkdir -p "$T/FCB_TMP_session_${D}_deadbeef/FCB_TMP_snap_x" && echo x > "$T/FCB_TMP_session_${D}_deadbeef/FCB_TMP_snap_x/Doc.FCStd"
mkdir -p "$T/FCB_TMP_snap_orphan" && echo x > "$T/FCB_TMP_snap_orphan/Doc.FCStd"
mkdir -p "$T/FCB_TMP_session_<live pid>_cafebabe" && echo x > "$T/FCB_TMP_session_<live pid>_cafebabe/keep.txt"
mkdir -p "$T/not-reserved" && echo x > "$T/not-reserved/keep.txt"
echo x > "$T/keep-me.txt"
mkdir -p "$TEMP/FCB_TMP_snap_tc1119"
```

**When** FreeCAD is started with `launch_app`, and the bridge is allowed to come up  
**And** the new `addon.log` lines are read, and `tmp/` is listed again  
**And** a golden model is opened in the GUI as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the framed window is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-19-before.png"}' | & cua-driver call get_window_state`  
**And** H1 is started with a scratch workdir that holds one dead session folder  
```bash
mkdir -p "$RUN_DIR/evidence/tc-11-19-workdir/tmp/FCB_TMP_session_${D}_deadbeef"
FREECAD_BUDDY_WORKDIR=$RUN_DIR/evidence/tc-11-19-workdir "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline 2> "$RUN_DIR/evidence/tc-11-19-h1.stderr.log"
```

**Then** the sweep ran at start and is logged — verify: the new `addon.log` lines contain `session-start sweep removed 2 leftover temp artifact(s)`  
**And** a dead host's session folder is removed — verify: `FCB_TMP_session_999996_deadbeef` is gone, with the snapshot copy inside it  
**And** a reserved-prefix entry outside every session folder is removed — verify: `FCB_TMP_snap_orphan` is gone, with its `.FCStd`  
**And** a live host's session folder is kept — verify: `FCB_TMP_session_<live pid>_cafebabe/keep.txt` still exists  
**And** non-prefixed entries are never removed — verify: `not-reserved/keep.txt` and `keep-me.txt` still exist  
**And** the OS temp directory is never scanned — verify: `ls -d "$TEMP/FCB_TMP_snap_tc1119"` still lists the folder  
**And** H1 sweeps the same way — verify: `tc-11-19-h1.stderr.log` contains `session-start sweep removed 1 leftover temp artifact(s)`, and the planted folder is gone from `$RUN_DIR/evidence/tc-11-19-workdir/tmp/`  
**And** both hosts call the sweep — verify: `grep -n "session-start sweep" src/freecad_buddy/hosts/gui_addon/bootstrap.py src/freecad_buddy/hosts/headless/worker.py` returns one line in each file  
**And** *(visual)* the restarted bridge came up coherent with the baseline shown — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-11-19-after.png"}' | & cua-driver call get_window_state` after a second fit, then `Read` both PNGs and state what is on screen: the baseline box drawn whole inside the frame, no startup error dialog or addon-failure popup, no "Not Responding" in the title bar, and the after image showing the same box at the same size and position as `tc-11-19-before.png`. A sweep that logged the right count while deleting a file the user owns is what the log assertion cannot catch, so the listings above and this image are the test result. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
taskkill //PID <live pid> //F   # the sleeper; <live pid> is the number in tc-11-19-sleeper.pid
rm -rf "$T/FCB_TMP_session_<live pid>_cafebabe" "$T/not-reserved" "$T/keep-me.txt" "$TEMP/FCB_TMP_snap_tc1119"
rm -rf "$RUN_DIR/evidence/tc-11-19-workdir" "$RUN_DIR/evidence/tc-11-19-sleeper.pid"   # after the H1 host is stopped
```
```
mcp document_close { doc: "<handle>" }
```
