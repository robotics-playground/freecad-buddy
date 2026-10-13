# TC-09: Error Contract & Fault Injection

Validates AD-17: every terminal status the client sees comes from the closed set, and the audit log
is append-only. The signature assertion of this file is WHICH rejection path fires — an MCP protocol
rejection at the input-schema gate (`isError` set, no envelope, so no status to read) versus a
semantic refusal that returns a real `INVALID_INPUT` envelope. Those are two different layers and
each edge scenario names the one it expects. Nothing here may crash the server.

Every status, envelope field, and error string this file asserts on comes from the code under test.
They are **claims**, not evidence. A bridge that returns a correct-looking `INVALID_INPUT` while
having already half-applied the mutation passes every string assertion here and fails the user
completely; commit `636fb8a` fixed exactly that class of defect. The exact-string assertions stay —
they are the point of this file — but each scenario's closing visual is what decides whether the
claim was true, and it is judged on pixels alone.

Most scenarios here assert a **refusal**. Their closing visual is therefore a no-change assertion:
the human's window after the refused call must look identical to the window before it, with no
dialog and no modal raised. That is the failure the string assertion cannot catch.

**Host**: GUI through the H2 proxy for every scenario, except TC-09-01, TC-09-02, TC-09-19,
TC-09-20, TC-09-21 and TC-09-22, which drive the headless H1 host through the automation sweeps, and
TC-09-15, which runs on the H1 host AND the H2 proxy to show they refuse the same way. H1 is two
processes: the front (`hosts/headless/entry.py`) serves MCP over stdio, bounds every call and
holds the quarantine; the worker (`hosts/headless/worker.py`) runs FreeCAD. Behind H2, the RPC
listener carries the non-string-`doc` guard and the suspect-document logic
(`rpc_listener.py:417-424`), so the two hosts refuse the same inputs.

## Preconditions
- [ ] FreeCAD 1.1.x installed (verify: `ls "$FREECAD_EXE"`); the build under test is the live version: `query_capabilities.freecad_version`, read once at the start of the run and written `<live version>` below
- [ ] Golden and fault `.FCStd` files have no `GuiDocument.xml` and open with every object hidden. After each `document_open` of such a file, and before any fit or render of it, run **Show All**: `cua-driver call invoke_menu { pid, window_id, path: ["View","Visibility","Show All Objects"] }`. A fit before it returns `SPEC_FAILED view_fit.nothing_to_frame`.
- [ ] micromamba `fcb` env is H1-capable (verify: `"$FCB_PYTHON" -c "import FreeCAD, mcp"`)
- [ ] Fault fixtures present (verify: `ls benchmarks/g0/fault-injection/wrong-volume/fixture.FCStd`)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/*.FCStd` lists 5 files)
- [ ] No stale H1 server holding the fixtures (verify: `netstat -ano | grep :8765` shows at most the GUI proxy)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` returns a `QOpenGLWidget`)
- [ ] The GUI's own **Fit All** toolbar button is reachable, as the non-MCP framing path (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` lists a `Fit All` toolbar element with an `element_token`; clicking it returns `route: "accessibility"` and reframes the view. Note `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; `["View","Visibility","Show All Objects"]` resolves.)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)

---

### TC-09-01: The legacy edge sweep is still green

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (status), `verification-design.md` §6.3 (fault detection)

**Given** no stale H1 server holds the fixtures — verify: no `freecad_buddy.hosts.main` process is running  
**And** a golden model is open in the GUI so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched GUI window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-01-before.png"}' | & cua-driver call get_window_state`  

**When** the automated edge sweep is run. It spawns its own headless H1 server and drives the failure and boundary contract over real MCP stdio  
```bash
uv run python scripts/automation/run_mcp_edge_cases.py
```
**And** the sweep's report and server stderr are copied into the run folder. The sweep writes them under `_automation/`  
```bash
cp _automation/edge_report.json "$RUN_DIR/evidence/tc-09-01-edge_report.json"
cp _automation/edge.stderr.log "$RUN_DIR/evidence/tc-09-01-edge.stderr.log"
```

**Then** the sweep gate is green — verify: `python3 -c "import json;print(json.load(open('$RUN_DIR/evidence/tc-09-01-edge_report.json'))['all_passed'])"` returns `True`  
**And** the sweep records 14 checks, not 15 — verify: `python3 -c "import json;print(json.load(open('$RUN_DIR/evidence/tc-09-01-edge_report.json'))['total'])"` returns `14`. The former `docs/tests/TC-09` file claimed 15; it was removed in commit `4cc4ee5` and its count was already stale.  
**And** every recorded check passed — verify: `python3 -c "import json;r=json.load(open('$RUN_DIR/evidence/tc-09-01-edge_report.json'));print(r['passed']==r['total'], r['failed'])"` returns `True 0`  
**And** the retired-parameter check is present and asserts a SCHEMA rejection — verify: `python3 -c "import json;print([c for c in json.load(open('$RUN_DIR/evidence/tc-09-01-edge_report.json'))['checks'] if c['tool']=='retired_max_nodes_rejected'])"` shows one entry with `status` equal to `SCHEMA_ERROR`, not `OK`  
**And** both planted-fault checks are present — verify: the `checks[*].tool` values include `fault_shape:wrong-volume` and `fault_shape:non-watertight-open-shell`, both with `ok` true  
**And** the process exit code is 0 — verify: `echo $?` immediately after the sweep prints `0`  
**And** no genuine crash in the sweep's server — verify: `grep -iE "access violation|swig|segfault|fatal" "$RUN_DIR/evidence/tc-09-01-edge.stderr.log"` returns nothing  
**And** each client error logs one line, not a traceback — verify: `grep -c "INFO.*INVALID_INPUT" "$RUN_DIR/evidence/tc-09-01-edge.stderr.log"` is at least 1 and `grep -c "^Traceback" "$RUN_DIR/evidence/tc-09-01-edge.stderr.log"` returns `0`; an `INVALID_INPUT` takes the `logger.info` branch at `rpc_dispatch.py:88-91`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the headless sweep never reached the human's window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-01-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the box is still shown whole and framed, the two images look identical, and no error dialog or modal was raised by the sweep's deliberate failures. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f _automation/edge.stl _automation/edge_multi.step
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-09-02: Every observed terminal status is inside the closed set

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (closed terminal status set)

**Given** the edge sweep report exists from TC-09-01 — verify: `ls "$RUN_DIR/evidence/tc-09-01-edge_report.json"`  
**And** a golden model is open in the GUI so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched GUI window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-02-before.png"}' | & cua-driver call get_window_state`  

**When** the shipped status vocabulary is read  
```bash
python3 -c "import re;print(re.findall(r'\"(\w+)\"', open('src/freecad_buddy/contracts/status.py').read()))"
```
**And** every `status` value the sweeps recorded is collected and compared against that set  
```bash
python3 -c "import json;r=json.load(open('$RUN_DIR/evidence/tc-09-01-edge_report.json'));print(sorted({c.get('status') for c in r['checks']}))"
```
**And** the repo's own vocabulary gate is run  
```bash
uv run python scripts/check_status_vocab.py
```

**Then** the closed set is exactly seven members — verify: `TerminalStatus` in `src/freecad_buddy/contracts/status.py:11` declares `OK`, `SPEC_FAILED`, `RECOMPUTE_ERROR`, `TIMEOUT`, `OOM_KILLED`, `WORKER_CRASHED`, `INVALID_INPUT` and nothing else  
**And** every status observed in the sweep is a member of that set, spelled exactly — verify: the collection output contains no value outside the seven, allowing for the harness's own non-status marker `SCHEMA_ERROR` used where there is no envelope  
**And** no near-miss spelling reaches the client — verify: `grep -rnE "INVALID_ARGUMENT|VALIDATION_ERROR|BAD_INPUT|RECOMPUTE_FAILED|SPEC_FAIL\b" src/freecad_buddy/` returns nothing  
**And** the vocabulary gate passes — verify: the gate run exits 0  
**And** the set is closed, not fully reachable — verify: `OOM_KILLED` is NOT produced anywhere on the GUI or H1 path. The assertion is that the declared set admits no eighth member, NOT that every member can be triggered here.  
**And** `WORKER_CRASHED` comes only from a client of an RPC listener, never from the in-FreeCAD dispatch — verify: the H1 front emits it when the worker has exited (`hosts/headless/entry.py:105-110`) and when a quarantined call has run past twice its budget (`entry.py:69-77`); the H2 proxy emits it through `rpc_client` when the listener is unreachable. `grep -n "WORKER_CRASHED" src/freecad_buddy/adapters/rpc_dispatch.py` names it only in a comment  
**And** no dispatch path can emit a status outside the boundary — verify: `MethodRegistry._invoke` at `src/freecad_buddy/adapters/rpc_dispatch.py:138-157` maps every exception class to one of `INVALID_INPUT`, `TIMEOUT`, `RECOMPUTE_ERROR`, and its final `except Exception` clause at `:156` guarantees nothing raises past it  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the read-only inspection left the window untouched — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-02-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the box is still shown whole and framed, the two images look identical, and no dialog or modal was raised. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-09-03: A missing schema-required field is a protocol rejection, not an envelope

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (schema gate vs. semantic refusal), `mcp-tools-design.md` §3.5

**Given** `box-10-20-30.FCStd` is open as `<H>` with sole object `<OBJ>` — verify: `query_tree_summary` names it  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit, before the four refusals — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-03-before.png"}' | & cua-driver call get_window_state`  

**When** `path` is omitted, which `export_step` declares required  
```
mcp export_step { doc: <H>, objects: [<OBJ>] }
```
**And** `doc` is omitted, required by `verify_shape`  
```
mcp verify_shape { object: <OBJ> }
```
**And** `export_id` is omitted, required by `verify_export_stl`  
```
mcp verify_export_stl { doc: <H> }
```
**And** `object` is omitted, required by `query_object`  
```
mcp query_object { doc: <H> }
```

**Then** missing `path` → MCP protocol rejection (`isError` set, `structuredContent` is `null`), NOT an `INVALID_INPUT` envelope  
**And** missing `doc` → protocol rejection  
**And** missing `export_id` → protocol rejection  
**And** missing `object` → protocol rejection  
**And** no envelope means no status field — verify: none of the four results has a `structuredContent.status`, so nothing may be read as `INVALID_INPUT`  
**And** the two layers are distinguishable — verify: by contrast, `mcp verify_export_stl { doc: <H>, export_id: "fcb-export:bogus" }` satisfies the schema and DOES return an envelope with `status` equal to `INVALID_INPUT`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* none of the four refusals disturbed the window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-03-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, the two images visually identical, no error dialog or modal raised. A refusal that returned the right protocol rejection while leaving a partial mutation on screen is precisely the failure the string assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**: none — nothing was mutated.

---

### TC-09-04: A wrong JSON type for a declared field is a protocol rejection

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (typed schema gate)

**Given** `<H>` and `<OBJ>` are resolved as in TC-09-03  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit, before the four refusals — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-04-before.png"}' | & cua-driver call get_window_state`  

**When** a string is passed where an integer is declared  
```
mcp query_tree_summary { doc: <H>, depth: "1" }
```
**And** a number is passed where a string is declared  
```
mcp export_step { doc: <H>, path: 42, objects: [<OBJ>] }
```
**And** an object is passed where an array is declared  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-09-04-t.step", objects: { "0": <OBJ> } }
```
**And** a string is passed where a number is declared  
```
mcp export_stl { doc: <H>, path: "$RUN_DIR/evidence/tc-09-04-t.stl", linear: "0.1" }
```

**Then** `depth` as a string → protocol rejection (`isError`, no envelope)  
**And** `path` as a number → protocol rejection  
**And** `objects` as an object → protocol rejection  
**And** `linear` as a string → protocol rejection  
**And** no coercion happens — verify: none of the four produced a successful call; a JSON Schema `type` is a gate, never a cast  
**And** nothing was written — verify: `ls "$RUN_DIR/evidence/tc-09-04-t."*` reports no such files  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* none of the four type rejects disturbed the window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-04-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, the two images visually identical, no error dialog or modal raised. A reject that returned the right protocol rejection while leaving a partial mutation on screen is precisely the failure the string assertions cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**: none — no file was created.

---

### TC-09-05: An unknown key is a protocol rejection on every tool

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (`additionalProperties: false` everywhere)

**Given** `<H>` and `<OBJ>` are resolved as in TC-09-03  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit, before the five refusals — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-05-before.png"}' | & cua-driver call get_window_state`  

**When** the schema fact is confirmed across the whole surface. Regenerate that file from `tools/list` first if it is absent  
```bash
python3 -c "import json;d=json.load(open('$RUN_DIR/evidence/tc-09-05-tool_surface.json'));print(sorted(k for k,v in d.items() if v['addProps'] is not False))"
```
**And** one unknown key is added to several tools  
```
mcp verify_shape       { doc: <H>, object: <OBJ>, strict: true }
mcp query_tree_summary { doc: <H>, max_nodes: 50 }
mcp export_step        { doc: <H>, path: "$RUN_DIR/evidence/tc-09-05-u.step", overwrite: true }
mcp document_close     { doc: <H>, force: true }
mcp query_capabilities { verbose: true }
```

**Then** no tool permits extra properties — verify: the surface command prints an empty list; every input schema sets `additionalProperties: false`  
**And** `verify_shape` with an unknown key → protocol rejection  
**And** `query_tree_summary` with an unknown key → protocol rejection  
**And** `export_step` with an unknown key → protocol rejection  
**And** `document_close` with an unknown key → protocol rejection, and the document stays OPEN — verify: `document_list` still names `<H>`  
**And** an empty-object schema still rejects extras — verify: `query_capabilities { verbose: true }` is a protocol rejection even though the tool declares no properties at all  
**And** an unknown key is never silently dropped — verify: none of the five calls returned `OK`; a schema reject and a silent ignore are different outcomes and only the reject is correct  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the rejected `document_close` really left the window showing the document — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-05-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same model still displayed, the two images visually identical, no error dialog or modal raised. A window that went empty or grey means the rejected close half-applied while reporting a clean protocol rejection — `document_list` naming the handle does not prove the human still sees it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**: none — nothing was mutated.

---

### TC-09-06: Empty arrays are rejected where `minItems` applies

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (array bounds), `mcp-tools-design.md` §3.4

**Given** a scratch document `<H>` with a sketch `<SK>` exists — verify: `query_sketch_info` returns `OK` for `<SK>`  
**And** the sketch's geometry count is recorded before the refusals — verify: `len(geometry)` from `query_sketch_info { doc: <H>, sketch: <SK> }`  
**And** the sketch is framed, so the before and after images share a camera — verify: `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-06-before.png"}' | & cua-driver call get_window_state`  

**When** an empty geometry list is passed  
```
mcp sketch_add_geometry { doc: <H>, sketch: <SK>, geometry: [] }
```
**And** a coordinate array below `minItems: 2` is passed  
```
mcp sketch_add_geometry { doc: <H>, sketch: <SK>, geometry: [
  { kind: "line_segment", start: [0], end: [10, 0] }
] }
```
**And** a coordinate array above `maxItems: 3` is passed  
```
mcp sketch_add_geometry { doc: <H>, sketch: <SK>, geometry: [
  { kind: "line_segment", start: [0, 0, 0, 0], end: [10, 0] }
] }
```
**And** an empty `objects` array is passed to an export, which declares NO `minItems`  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-09-06-e.step", objects: [] }
```

**Then** an empty `geometry` array → protocol rejection where the schema sets `minItems: 1`  
**And** a 1-element coordinate array → protocol rejection (`minItems: 2`)  
**And** a 4-element coordinate array → protocol rejection (`maxItems: 3`)  
**And** the two bounds are distinct failures, not one generic one — verify: both the 1-element and the 4-element calls are rejections and neither produced an envelope  
**And** an empty `objects` array is NOT a schema error — verify: the export returns a real envelope, because `export_step` declares no `minItems` on `objects`; the empty list falls through to the runtime default-selection path  
**And** the sketch is unchanged — verify: `len(geometry)` from `query_sketch_info { doc: <H>, sketch: <SK> }` is the same as before the first call  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* no geometry was half-added to the sketch on screen — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-06-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same sketch, no new line segment drawn, the two images visually identical, no error dialog or modal raised. A matching geometry count is a claim from the bridge; a stray line visible in the viewport is the defect it would hide. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-09-06-e.step"
```

---

### TC-09-07: Integer boundaries on `depth`, `max_edges`, and `occurrences`

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (numeric bounds), `mcp-tools-design.md` §3.2

**Given** `box40-hole-r5.FCStd` is open as `<H>` — verify: `query_tree_summary` returns `OK`  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit, before the boundary calls — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-07-before.png"}' | & cua-driver call get_window_state`  

**When** `depth` is driven, declared `minimum: 1`  
```
mcp query_tree_summary { doc: <H>, depth: 0 }
mcp query_tree_summary { doc: <H>, depth: -1 }
mcp query_tree_summary { doc: <H>, depth: 2147483647 }
mcp query_tree_summary { doc: <H>, depth: 1 }
```
**And** `max_edges` is driven, declared `minimum: 1`, default 2000  
```
mcp query_dependencies { doc: <H>, max_edges: 0 }
mcp query_dependencies { doc: <H>, max_edges: -1 }
mcp query_dependencies { doc: <H>, max_edges: 1 }
```
**And** `occurrences` is driven on `feature_pattern`, declared `minimum: 2`  
```
mcp feature_pattern { doc: <H>, ..., kind: "linear", occurrences: 0, ... }
mcp feature_pattern { doc: <H>, ..., kind: "linear", occurrences: 1, ... }
```

**Then** `depth: 0` → protocol rejection (below `minimum: 1`)  
**And** `depth: -1` → protocol rejection  
**And** `depth: 2147483647` is inside the declared range, so it is accepted and bounded by the real tree — verify: an `OK` envelope whose `shown` equals the document's actual object count (or `200` with `truncated: true` when the document has more lines), with no hang  
**And** `depth: 1` is the documented default and returns the top level only — verify: a first line starting `OK:` whose `<M> shown` equals the number of tree lines, and no line starts with a connector (`|-- ` or `` `-- ``)  
**And** `max_edges: 0` and `max_edges: -1` → protocol rejection (below `minimum: 1`)  
**And** `max_edges: 1` is legal and truncates — verify: `OK` with at most one edge reported  
**And** `occurrences: 0` and `occurrences: 1` → protocol rejection (below `minimum: 2`); a one-occurrence pattern is not expressible on the wire  
**And** a boundary rejection never reaches the handler — verify: `$RUN_DIR/evidence/tc-09-01-edge.stderr.log` or the addon log shows no `ValidationError` traceback for the rejected boundary calls, because the schema gate refused them first  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the rejected `feature_pattern` calls added no pattern to the model — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-07-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: one single part with its hole, no repeated copies, the two images visually identical, no error dialog or modal raised. A schema rejection that still spawned pattern instances would be visible here and nowhere in the envelope. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-09-08: null and absent behave distinguishably for optional fields

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (optional fields), `mcp-tools-design.md` §3.3

**Given** `box-10-20-30.FCStd` is open as `<H>` with sole object `<OBJ>`  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-08-before.png"}' | & cua-driver call get_window_state`  

**When** `verify_shape` is called three ways  
```
mcp verify_shape { doc: <H>, object: <OBJ> }
mcp verify_shape { doc: <H>, object: <OBJ>, checks: null }
mcp verify_shape { doc: <H>, object: <OBJ>, checks: [] }
```
**And** `query_tree_summary` is called with `depth` absent versus `depth: null`  
```
mcp query_tree_summary { doc: <H> }
mcp query_tree_summary { doc: <H>, depth: null }
```
**And** `export_step` is called with `ap` absent versus `ap: null`  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-09-08-n.step" }
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-09-08-n2.step", ap: null }
```

**Then** `checks` absent returns measurement-only facts — verify: `OK` with five checks carrying no `expected` key  
**And** `checks: null` is a protocol rejection — verify: `isError` set, because the schema declares `checks` as `array`, and `null` is not an array  
**And** `checks: []` is accepted and takes the same measurement-only path — verify: `OK` with the same five fact ids as the absent-`checks` call; an empty list is falsy at `checks = checks or []` (`verify.py:248`)  
**And** `depth` absent applies the declared default of 1 — verify: a first line starting `OK:` whose `<M> shown` equals the number of top-level tree lines  
**And** `depth: null` is a protocol rejection — verify: `isError` set; `null` is not an integer, so the default never applies  
**And** `ap` absent applies the default `AP242` — verify: `grep -c AP242` on the written file is non-zero  
**And** `ap: null` is a protocol rejection — verify: `isError` set; `null` is outside the enum `["AP214","AP242"]`, so it is not treated as "use the default"  
**And** the distinction is consistent — verify: in every pair above, absent means "apply the declared default" and explicit `null` means "protocol rejection". They are never interchangeable.  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* neither the accepted reads nor the `null` rejects changed the model on screen — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-08-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, the two images visually identical, no error dialog or modal raised. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-09-08-n.step" "$RUN_DIR/evidence/tc-09-08-n2.step"
```

---

### TC-09-09: Very long strings are handled without truncation or crash

**Priority**: Medium
**Design Ref**: `data-contracts-design.md` §3 (string fields), `mcp-tools-design.md` §3.1

**Given** a scratch document is available — verify: `document_create` returns `OK`  
**And** a golden model is open as `<H>` so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-09-before.png"}' | & cua-driver call get_window_state`  

**When** a document is created whose label is 4096 characters (`document_create` declares `label`, not `name` — confirm with `python3 -c "import json;print(json.load(open('$RUN_DIR/evidence/tc-09-05-tool_surface.json'))['document_create'])"`)  
```
mcp document_create { label: "<4096 'a' characters>" }
```
**And** a nonexistent path 8192 characters long is opened  
```
mcp document_open { path: "$RUN_DIR/evidence/tc-09-09-<8192 'b' characters>.FCStd" }
```
**And** an object name 65536 characters long is queried  
```
mcp query_object { doc: <H>, object: "<65536 'c' characters>" }
```

**Then** the long document label returns a real envelope, not a crash — verify: `status` is `OK` or `INVALID_INPUT`, never absent  
**And** if the label is accepted, it is not truncated — verify: `document_list` echoes back the same character count the call sent  
**And** the long nonexistent path is refused cleanly — verify: `status` equals `INVALID_INPUT` with a message naming the path  
**And** the long object name is refused cleanly — verify: `status` equals `INVALID_INPUT` with message `unknown object: ccc...`  
**And** the traceback in `detail.data.traceback` is capped — verify: its length is at most 4000 characters, matching `_TRACEBACK_LIMIT` at `src/freecad_buddy/adapters/rpc_dispatch.py:25`  
**And** the server survives — verify: `mcp query_capabilities {}` returns `OK` after the long-name query  
**And** the 16 MiB frame cap is not reached by any of these — verify: no `handshake required` or frame-size error appears in the addon log  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the refused long-path open left no half-opened document on screen — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-09-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the golden model still shown whole and framed, no extra empty document tab or blank 3D view, the two images visually identical apart from any legitimately created long-labelled document, and no error dialog or modal raised by the oversized strings. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <the long-named document, if created> }
mcp document_close { doc: <H> }
```

---

### TC-09-10: Deeply nested objects inside a `checks` item

**Priority**: Medium
**Design Ref**: `data-contracts-design.md` §3 (`checks` items typed `object`), `verification-design.md` §5

**Given** `box-10-20-30.FCStd` is open as `<H>` with sole object `<OBJ>`  
**And** `checks` items are typed `object` with no per-item property schema: `verify_shape` declares `checks: {type: array, items: {type: object}}` (`hosts/tool_catalog.py:1313`). So a non-object item is a schema refusal, while nesting inside an object item is not checked by the schema and MUST be caught at the handler  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-10-before.png"}' | & cua-driver call get_window_state`  

**When** a check whose `fn` is an object nested about 10 levels deep is sent. Deeper nesting is refused by the MCP client or the MCP SDK layer before it reaches the bridge, so it tests the transport, not the handler  
```
mcp verify_shape { doc: <H>, object: <OBJ>, checks: [ { fn: { a: { a: { ... 10 deep ... } } } } ] }
```
**And** a check that is not an object at all is sent  
```
mcp verify_shape { doc: <H>, object: <OBJ>, checks: ["expect_volume"] }
```
**And** a well-formed check carrying a deeply nested `tol` is sent  
```
mcp verify_shape { doc: <H>, object: <OBJ>, checks: [{ fn: "expect_volume", expect: 6000, tol: { rel: { deep: { deeper: 0.001 } } } }] }
```

**Then** the deeply nested `fn` is refused by the handler, not the schema — verify: a real envelope with `status` equal to `INVALID_INPUT` and a message starting `unknown assertion fn:` (`usecases/verify.py:253-255`)  
**And** a non-object check is refused at the schema gate — verify: the call is a protocol rejection (`isError` set, `structuredContent` is `null`) whose text names `'expect_volume' is not of type 'object'` (schema refusal); the input is refused either way  
**And** a nested `tol` does not crash the tolerance resolver — verify: the nested-`tol` call returns a real envelope with `status` equal to `INVALID_INPUT` and message `expect_volume.tol.rel must be a non-negative number` (`usecases/assertions.py:191`), never an unhandled fault  
**And** the two object items reach the handler — verify: the nested-`fn` call and the nested-`tol` call each carry `structuredContent` with a `status`, because the item schema admitted them  
**And** the server survives the nesting — verify: `mcp verify_shape { doc: <H>, object: <OBJ> }` still returns `OK` afterwards  
**And** no recursion error escapes — verify: `grep -i "RecursionError" "$RUN_DIR/evidence/tc-09-01-edge.stderr.log"` and the addon log return nothing  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the three refusals left the window untouched — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-10-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, the two images visually identical, no error dialog or modal raised, and no frozen or half-painted viewport left by the nesting. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**: none — read-only.

---

### TC-09-11: The retired `max_nodes` parameter is a schema rejection

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (`additionalProperties: false`), `mcp-tools-design.md` §3.2

**Given** `box-10-20-30.FCStd` is open as `<H>`  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-11-before.png"}' | & cua-driver call get_window_state`  

**When** the retired parameter is passed  
```
mcp query_tree_summary { doc: <H>, max_nodes: 0 }
mcp query_tree_summary { doc: <H>, max_nodes: 50 }
```
**And** the shipped property list is confirmed  
```bash
python3 -c "import json;print(json.load(open('$RUN_DIR/evidence/tc-09-05-tool_surface.json'))['query_tree_summary']['props'])"
```

**Then** `max_nodes: 0` → protocol rejection (`isError`, no envelope)  
**And** `max_nodes: 50` → protocol rejection; the value is irrelevant, the key itself is unknown  
**And** the OLD documented behaviour is GONE — verify: neither call returns `OK`, neither returns an empty tree, and neither returns `truncated: true`. The former `docs/tests/TC-09` CP6 asserted `OK` + truncated; that expectation is stale and must not be revived from git history.  
**And** the shipped property list confirms the retirement — verify: the property-list command prints `['doc', 'focus', 'expand', 'depth', 'filters']` with no `max_nodes`  
**And** `truncated` now reports the 200-line cap, not `max_nodes` — verify: a successful `query_tree_summary { doc: <H> }` returns a first line with no `truncated` for the one-object box  
**And** bounding now happens through `focus`, `depth`, and the 200-line cap — verify: `depth: 1` returns the top level only and the `<M> shown` count equals the number of tree lines  
**And** the automated sweep asserts the same thing — verify: `$RUN_DIR/evidence/tc-09-01-edge_report.json` names `retired_max_nodes_rejected` as a passed check  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the two retired-parameter rejects left the window untouched — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-11-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, the two images visually identical, no error dialog or modal raised, and no tree-panel change. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**: none — read-only.

---

### TC-09-12: An unknown doc handle returns INVALID_INPUT

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (handle resolution), `verification-design.md` §6.3

**Given** the handle `fcb-doc:does-not-exist` was never issued by this session — verify: `mcp document_list {}` does not list it  
**And** a golden model is open as `<H>` so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-12-before.png"}' | & cua-driver call get_window_state`  

**When** several tools are called with a handle that was never issued  
```
mcp query_tree_summary { doc: "fcb-doc:does-not-exist" }
mcp verify_recompute   { doc: "fcb-doc:does-not-exist" }
mcp query_object       { doc: "fcb-doc:does-not-exist", object: "Box" }
mcp document_close     { doc: "fcb-doc:does-not-exist" }
```
**And** a document is opened, closed, then the now-stale handle is reused  

**Then** unknown doc handle → `INVALID_INPUT` (a real envelope, not a protocol rejection)  
**And** the same refusal on a read-only tool and a mutating one — verify: all four calls with the never-issued handle return `status` equal to `INVALID_INPUT`  
**And** the message names the handle — verify: each `detail.message` contains `fcb-doc:does-not-exist`  
**And** `detail.code` mirrors the status — verify: `detail.code` equals `INVALID_INPUT`  
**And** a stale handle after close behaves identically — verify: the stale-handle call returns `INVALID_INPUT`, and a second `document_close` on the same handle also returns `INVALID_INPUT` with no crash  
**And** the handle format is not what is checked — verify: a well-formed but unissued handle and a malformed string both return `INVALID_INPUT`; the refusal comes from registry lookup, not from a format test  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the refused `document_close` calls closed nothing on screen — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-12-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the golden model still displayed, the two images visually identical, no error dialog or modal raised. A correct `INVALID_INPUT` string over a window whose document vanished is exactly the defect the string cannot catch. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-09-13: An unknown object name returns INVALID_INPUT

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3, `verification-design.md` §5

**Given** `box-10-20-30.FCStd` is open as `<H>`  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-13-before.png"}' | & cua-driver call get_window_state`  

**When** an object that does not exist is named, across the read surface  
```
mcp query_object          { doc: <H>, object: "NoSuchObject" }
mcp query_mass_properties { doc: <H>, object: "NoSuchObject" }
mcp query_placement       { doc: <H>, object: "NoSuchObject" }
mcp verify_shape          { doc: <H>, object: "NoSuchObject" }
```
**And** it is named in an export selection  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-09-13-o.step", objects: ["NoSuchObject"] }
```

**Then** every read tool returns `INVALID_INPUT` — verify: all four read envelopes carry `status` equal to `INVALID_INPUT`  
**And** `verify_shape` names the object in its message — verify: `detail.message` equals `unknown object: NoSuchObject`  
**And** the export path names it identically — verify: the export's `detail.message` equals `unknown object: NoSuchObject`  
**And** the failed export wrote nothing — verify: `ls "$RUN_DIR/evidence/tc-09-13-o.step"` reports no such file  
**And** a name that differs only by case is also unknown — verify: `object: "box"` when the real name is `Box` returns `INVALID_INPUT`; object names are matched exactly  
**And** an empty object name is refused distinctly — verify: `mcp verify_shape { doc: <H>, object: "" }` returns `INVALID_INPUT` with message `missing required 'object' name`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* no object was added, removed, or selected by the refusals — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-13-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same single box, no new or missing object, nothing highlighted as selected, the two images visually identical, no error dialog or modal raised. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**: none — no file was created.

---

### TC-09-14: An unknown sketch or feature name returns INVALID_INPUT

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3, `mcp-tools-design.md` §3.4

**Given** a scratch document `<H>` with one real sketch `<SK>` exists — verify: `verify_sketch { doc: <H>, sketch: <SK> }` returns an envelope  
**And** the node count is recorded before the feature call — verify: `query_tree_summary { doc: <H> }` reports it  
**And** the model is framed, so the before and after images share a camera — verify: `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-14-before.png"}' | & cua-driver call get_window_state`  

**When** a sketch that does not exist is named  
```
mcp verify_sketch     { doc: <H>, sketch: "NoSuchSketch" }
mcp query_sketch_info { doc: <H>, sketch: "NoSuchSketch" }
```
**And** a real object that is NOT a sketch is named  
```
mcp verify_sketch { doc: <H>, sketch: "<a real non-sketch object name>" }
```
**And** a feature that does not exist is named  
```
mcp feature_set_parameters { doc: <H>, feature: "NoSuchFeature", parameters: { Length: { value: 12, unit: "mm" } } }
```

**Then** unknown sketch → `INVALID_INPUT` with message `unknown object: NoSuchSketch`  
**And** `query_sketch_info` refuses the same name the same way — verify: `status` equals `INVALID_INPUT`  
**And** a real object that is not a sketch is a DIFFERENT refusal — verify: `detail.message` equals `object is not a sketch: <name>`, distinguishing "absent" from "wrong type"  
**And** unknown feature → `INVALID_INPUT` — verify: `status` equals `INVALID_INPUT`, never `RECOMPUTE_ERROR`. The call sends no `confirm`: auto-approve is on by default, so the feature lookup is what refuses it, not the confirm gate  
**And** no mutation occurred — verify: `verify_recompute { doc: <H> }` returns `OK` and `query_tree_summary` reports the same node count as before the feature call  
**And** the refusal is logged as a client error, not a fault — verify: the addon log carries one `INFO` line for each refusal and no traceback  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the refused `feature_set_parameters` changed no geometry on screen — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-14-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the same model at the same size and shape, the two images visually identical, no error dialog or modal raised. An unchanged node count is a claim from the bridge; a resized or re-padded solid is the defect it would hide. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-09-15: A non-string `doc` is refused before dispatch on both hosts

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (pre-dispatch guard), `mcp-tools-design.md` §3.1

**Host**: the H1 headless host (`freecad_buddy.hosts.main serve --mode inline --transport stdio`) AND
the H2 proxy on `:8765`. Every tool declares `doc` as `{type: string}` (`_DOC_SCHEMA`,
`hosts/tool_catalog.py:48`) on both hosts, so the MCP input schema refuses a non-string `doc` first.
Behind the schema, a second guard returns `doc handle must be a string` on the H1 front
(`adapters/mcp_server.py:258-263`) and in the RPC listener behind H2 (`rpc_listener.py:417-418`).

**Given** the H1 host is reachable — verify: `uv run python scripts/automation/run_mcp_edge_cases.py` has completed at least once  
**And** a golden model is open in the GUI as `<H>` so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched GUI window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-15-before.png"}' | & cua-driver call get_window_state`  

**When** a `doc` that is an object, not a string, is sent to the H1 host  
```
mcp verify_recompute { doc: { "handle": "fcb-doc:x" } }
```
**And** the same call is repeated against the H2 proxy on `:8765`  

**Then** the H1 host refuses it before dispatch — verify: the call is a protocol rejection (`isError` set, `structuredContent` is `null`) whose text names `is not of type 'string'` (schema refusal); the input is refused either way  
**And** the H2 proxy refuses it the same way — verify: the same protocol rejection and the same text; the two hosts do not diverge  
**And** no document registry lookup ran — verify: neither message names a missing handle (`unknown or stale document handle`)  
**And** the second guard exists behind the schema on both hosts — verify: `grep -n "doc handle must be a string" src/freecad_buddy/adapters/mcp_server.py src/freecad_buddy/adapters/rpc_listener.py` returns one line in each file, and no use-case module emits that string  
**And** neither host crashes — verify: both still answer `tools/list` after the call  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* neither host's refusal disturbed the human's window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-15-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the golden model still whole and framed, the two images visually identical, no error dialog or modal raised by either refusal. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-09-16: Opening a nonexistent path returns INVALID_INPUT

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3, `mcp-tools-design.md` §3.1

**Given** the target paths do not exist — verify: `ls "$RUN_DIR/evidence/tc-09-16-nope-missing.FCStd" "$RUN_DIR/evidence/tc-09-16-no_such_dir/x.FCStd" 2>&1` reports no such file  
**And** a golden model is open as `<H>` so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-16-before.png"}' | & cua-driver call get_window_state`  

**When** paths that do not exist are opened  
```
mcp document_open { path: "$RUN_DIR/evidence/tc-09-16-nope-missing.FCStd" }
mcp document_open { path: "$RUN_DIR/evidence/tc-09-16-no_such_dir/x.FCStd" }
mcp document_open { path: "" }
```
**And** a path that exists but is not a FreeCAD document is opened. Use an absolute path: a relative path resolves against FreeCAD's working folder, not the repository  
```
mcp document_open { path: "$PROJECT_ROOT/AGENTS.md" }
```

**Then** a missing file → `INVALID_INPUT` (a real envelope)  
**And** a missing directory → `INVALID_INPUT`  
**And** an empty path → `INVALID_INPUT`, never a silently created document  
**And** the message names the path — verify: each `detail.message` contains the path string that was sent  
**And** a non-FreeCAD file is refused, not half-opened — verify: the `AGENTS.md` open returns `INVALID_INPUT` with `Invalid project file <path>` in its message, and `document_list` names no new handle  
**And** no handle is issued for any refused open — verify: none of the four envelopes carries a `structured_content.doc`  
**And** the automated sweep asserts the same — verify: `$RUN_DIR/evidence/tc-09-01-edge_report.json` names `open_bad_path` as a passed check  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* no refused open produced a new or empty document window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-16-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the golden model is the only document shown, no extra tab and no blank 3D view appeared, the two images visually identical, no error dialog or modal raised. `document_list` naming no new handle is a claim from the bridge; a half-opened window is the defect it would hide. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-09-17: A broken recompute returns RECOMPUTE_ERROR, not a false OK

**Priority**: Critical
**Design Ref**: `verification-design.md` §6.3 (recompute grading), `data-contracts-design.md` §3

**Given** a document with at least one object that fails to recompute — verify: build one by setting a pad length that cannot resolve, or use a fixture whose object reports an error state  
**And** the document `<H>` holds a failing object. A pad whose sketch has been emptied, or a feature whose profile was removed, leaves the object in an `Invalid`/`Error`/`Touched` state  

**When** the document is graded  
```
mcp verify_recompute { doc: <H> }
```
**And** the same document is graded a second time to confirm the result is stable, not a first-call artifact  

**Then** the status is `RECOMPUTE_ERROR`, never `OK` — verify: the envelope `status` equals `RECOMPUTE_ERROR`  
**And** the verdict is derived, not asserted — verify: `structured_content.verdict` equals `RECOMPUTE_ERROR` and equals the envelope `status`  
**And** the failing check is tagged so the verdict classes correctly — verify: at least one check has id `recompute.object` with `passed: false` and `detail.code` equal to `recompute.error`  
**And** the summary names the count — verify: the envelope `text` matches `Recompute: <n> error(s): <names>.`  
**And** an object still `Touched` after a full recompute counts as an error — verify: `_RECOMPUTE_ERROR_STATES` at `src/freecad_buddy/usecases/verify.py:22` includes `Touched`, catching a silently skipped recompute that would otherwise read as clean  
**And** the result is stable across calls — verify: the second grading returns the same status and the same `subject.failing_objects` list  
**And** a clean document in the same session still grades `OK` — verify: `verify_recompute` on `box-10-20-30.FCStd` returns `OK`, proving the `RECOMPUTE_ERROR` is document-specific and not a stuck server state  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not — the document is in a faulted state and the MCP fit may refuse it — fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the planted fault is visible in the tree — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-17-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: the FreeCAD tree marks the failing object with an error icon. The 3D view still shows the last valid shape of the failed feature: FreeCAD keeps that shape on a failed recompute, so an intact solid in the view is expected. A tree with no error marker on the object the envelope names is a finding, and only looking at the image can find it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-09-18: A broken reference surfaces the failing object and its status string

**Priority**: Critical
**Design Ref**: `verification-design.md` §6.3 (failing-object reporting)

**Given** a document `<H>` where one object references a deleted or unresolvable dependency  
**And** the reference is broken: the sketch a pad depends on is deleted, or an external geometry link is removed  

**When** the document is graded  
```
mcp verify_recompute { doc: <H> }
```
**And** the dependency graph is read to confirm the broken edge  
```
mcp query_dependencies { doc: <H> }
```

**Then** the failing object is named — verify: `structured_content.subject.failing_objects` contains the broken object's `Name`  
**And** the object's own status string is carried through — verify: the `recompute.object` check `measured` equals the value FreeCAD's `getStatusString()` returns for that object, not a rewritten message  
**And** the check detail pairs name and status — verify: `detail.message` equals `<Name>: <status string>`  
**And** the detail lists the object for the client — verify: the `recompute.object` check `detail.objects` equals `["<Name>"]`  
**And** one check per failing object — verify: `len(structured_content.checks)` equals `len(subject.failing_objects)`  
**And** the status string is non-empty — verify: `measured` is not the empty string; an empty value means `getStatusString` was unavailable and the diagnostic is lost  
**And** the dependency query still answers — verify: the dependency read returns `OK` and shows no edge from the failing object to the deleted target. FreeCAD clears the link when the target is deleted, so a broken reference does not break the read surface  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not — the broken reference leaves the document faulted and the MCP fit may refuse it — fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the broken reference is visible in the tree — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-18-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: the object named in `subject.failing_objects` has an error icon in the tree and its dependency is gone from the tree. The 3D view still shows the last valid shape: FreeCAD keeps it on a failed recompute. A tree with no error marker on the named object would mean the envelope's failing-object report does not describe what the human sees. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-09-19: An unwritable audit-log path degrades without losing the status

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (AD-17 audit), `verification-design.md` §6.3

**Given** a path that cannot be written — verify: a directory used as the log file path, or a read-only location  
**And** a golden model is open in the GUI as `<H>` so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched GUI window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-19-before.png"}' | & cua-driver call get_window_state`  

**When** a headless H1 server is started with the audit log pointed at an unwritable target. The variable names a path that is a DIRECTORY, so every append attempt fails. Set the variable on the server command, not on `mkdir`; an MCP stdio client drives this server  
```bash
mkdir -p "$RUN_DIR/evidence/tc-09-19-unwritable_dir"
FREECAD_BUDDY_AUDIT_LOG="$RUN_DIR/evidence/tc-09-19-unwritable_dir" \
  "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline \
  2> "$RUN_DIR/evidence/tc-09-19-server.stderr.log"
```
**And** one mutating call (a `document_create`, then a `document_close`) and one read-only call are driven through that server  
**And** the resulting envelopes and the server stderr are read  

**Then** the mutating call still returns a real envelope with a status from the closed set — verify: `status` is `OK` or a named failure, never absent  
**And** the operation's OWN status is not replaced by the audit failure — verify: a successful `document_create` still reports `OK`; the audit sink is not allowed to turn a good mutation into an error  
**And** the read-only call is unaffected — verify: `query_capabilities {}` returns `OK`  
**And** the failure is visible, not silent — verify: `grep "audit write failed" "$RUN_DIR/evidence/tc-09-19-server.stderr.log"` returns at least one line (`adapters/mcp_server.py:306`); a lost audit line that leaves no trace is the defect this assertion guards against  
**And** the server survives — verify: `tools/list` still answers after the driven calls  
**And** restoring a writable path restores auditing — verify: pointing `FREECAD_BUDDY_AUDIT_LOG` at `$RUN_DIR/evidence/tc-09-19-audit.jsonl` and repeating the driven calls produces `before` and `after` records in that file  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not — the bridge has been driven with a broken audit sink and may not answer — fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the headless audit failure never reached the human's window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-19-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the golden model still whole and framed, the two images visually identical, no error dialog or modal raised by the unwritable sink. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rmdir "$RUN_DIR/evidence/tc-09-19-unwritable_dir"
rm -f "$RUN_DIR/evidence/tc-09-19-audit.jsonl"
```
```
mcp document_close { doc: <H> }
```

---

### TC-09-20: The audit log is append-only

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (AD-17 append-only audit)

**Given** a writable audit target — verify: `rm -f "$RUN_DIR/evidence/tc-09-20-append.jsonl"`  
**And** a golden model is open in the GUI as `<H>` so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched GUI window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-20-before.png"}' | & cua-driver call get_window_state`  

**When** the audit log is pointed at a fresh file and three mutating calls are run through a server started with `FREECAD_BUDDY_AUDIT_LOG="$RUN_DIR/evidence/tc-09-20-append.jsonl"`  
**And** the file is snapshotted after each call  
```bash
cp "$RUN_DIR/evidence/tc-09-20-append.jsonl" "$RUN_DIR/evidence/tc-09-20-snap_1.jsonl"   # after call 1
cp "$RUN_DIR/evidence/tc-09-20-append.jsonl" "$RUN_DIR/evidence/tc-09-20-snap_2.jsonl"   # after call 2
cp "$RUN_DIR/evidence/tc-09-20-append.jsonl" "$RUN_DIR/evidence/tc-09-20-snap_3.jsonl"   # after call 3
```
**And** each snapshot is compared against the prefix of the next  
```bash
python3 -c "
a=open('$RUN_DIR/evidence/tc-09-20-snap_1.jsonl').read()
b=open('$RUN_DIR/evidence/tc-09-20-snap_2.jsonl').read()
c=open('$RUN_DIR/evidence/tc-09-20-snap_3.jsonl').read()
print(b.startswith(a), c.startswith(b), len(a)<len(b)<len(c))"
```

**Then** each snapshot is a strict prefix of the next — verify: the comparison prints `True True True`  
**And** no earlier line is ever rewritten — verify: `diff <(head -n $(wc -l < "$RUN_DIR/evidence/tc-09-20-snap_1.jsonl") "$RUN_DIR/evidence/tc-09-20-snap_3.jsonl") "$RUN_DIR/evidence/tc-09-20-snap_1.jsonl"` returns nothing  
**And** the file only grows — verify: the three byte counts are strictly increasing  
**And** every line is a complete JSON object — verify: `python3 -c "import json;[json.loads(l) for l in open('$RUN_DIR/evidence/tc-09-20-append.jsonl')]"` raises nothing  
**And** every record declares the schema — verify: every line's `schema` field equals `fcb.audit-record/1`  
**And** each mutation wrote a before and an after record — verify: the line count is at least twice the mutation count, and the `after` lines carry a `verify_verdict` while the `before` lines do not  
**And** the sink never truncates or rotates — verify: `grep -nE "open\(|\.truncate\(|os\.remove|\.unlink\(|rename\(" src/freecad_buddy/adapters/audit_log.py` returns one line only, the `open(self._path, "a", …)` at `audit_log.py:48`. The pattern matches code only: the module docstring says "never truncates, rotates", so a bare `truncate|rotate` grep matches the docstring  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the audited mutations never reached the human's window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-20-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the golden model still whole and framed, the two images visually identical, no error dialog or modal raised. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-09-20-append.jsonl" "$RUN_DIR/evidence/tc-09-20-snap_"*.jsonl
```
```
mcp document_close { doc: <H> }
```

---

### TC-09-21: Client errors log one INFO line while keeping the traceback in the envelope

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (error detail), `verification-design.md` §6.3

**Given** a server whose stderr is captured to a file — verify: `ls "$RUN_DIR/evidence/tc-09-01-edge.stderr.log"`  
**And** a golden model is open in the GUI as `<H>` so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched GUI window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-21-before.png"}' | & cua-driver call get_window_state`  

**When** a run of client errors is driven through the H1 server and stderr is captured  
```bash
uv run python scripts/automation/run_mcp_edge_cases.py
```
**And** one `INVALID_INPUT` envelope's `detail.data` is inspected  
**And** the error channel's record of the same calls is counted  
```bash
grep -c "INVALID_INPUT" "$RUN_DIR/evidence/tc-09-01-edge.stderr.log"
grep -cE "^Traceback" "$RUN_DIR/evidence/tc-09-01-edge.stderr.log"
```

**Then** the envelope retains the traceback — verify: `detail.data.traceback` is a non-empty string for an `INVALID_INPUT` result  
**And** the traceback is truncated at the declared limit — verify: `len(detail.data.traceback)` is at most 4000, matching `_TRACEBACK_LIMIT` at `rpc_dispatch.py:25`  
**And** the exception class is recorded — verify: `detail.data.exception` equals `ValidationError` for a handle or object refusal  
**And** a client error logs one line, not a stack — verify: `INVALID_INPUT` and `TIMEOUT` take the `logger.info` branch at `rpc_dispatch.py:90-91`, which is reached because both are members of `_EXPECTED_CLIENT_STATUSES` at `rpc_dispatch.py:29`  
**And** only the unexpected class spills a stack to stderr — verify: `rpc_dispatch.py:88-89` writes the traceback to stderr only when the status is outside `_EXPECTED_CLIENT_STATUSES` or `unexpected` is set  
**And** an unexpected fault is flagged as such — verify: a `RECOMPUTE_ERROR` produced by the final `except Exception` clause carries `detail.data.unexpected` equal to `true`, while an `INVALID_INPUT` does not carry that key at all  
**And** the error channel stays readable — verify: the stderr traceback count is far below the total call count; a traceback per client error would make the log unusable  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the headless client-error run never reached the human's window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-21-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the golden model still whole and framed, the two images visually identical, no error dialog or modal raised. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-09-22: No unhandled traceback appears in stderr across the whole sweep

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (nothing raises past the dispatch boundary)

**Given** both sweeps have run in this session — verify: `ls "$RUN_DIR/evidence/tc-09-22-e2e_report.json" "$RUN_DIR/evidence/tc-09-01-edge_report.json"`  
**And** a golden model is open in the GUI as `<H>` so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`  
**And** the model is framed, so the before and after images share a camera — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the untouched GUI window is captured after that fit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-22-before.png"}' | & cua-driver call get_window_state`  

**When** both sweeps are run so their stderr logs are current, and their outputs are copied from `_automation/` into the run folder  
```bash
uv run python scripts/automation/run_mcp_e2e.py
cp _automation/e2e_report.json "$RUN_DIR/evidence/tc-09-22-e2e_report.json"
cp _automation/server.stderr.log "$RUN_DIR/evidence/tc-09-22-server.stderr.log"
uv run python scripts/automation/run_mcp_edge_cases.py
cp _automation/edge_report.json "$RUN_DIR/evidence/tc-09-01-edge_report.json"
cp _automation/edge.stderr.log "$RUN_DIR/evidence/tc-09-01-edge.stderr.log"
```
**And** both logs are scanned for genuine crash signatures  
```bash
grep -iE "access violation|swig|segfault|fatal" "$RUN_DIR/evidence/tc-09-22-server.stderr.log" "$RUN_DIR/evidence/tc-09-01-edge.stderr.log"
```
**And** the tracebacks in both logs are counted  
```bash
grep -cE "^Traceback" "$RUN_DIR/evidence/tc-09-22-server.stderr.log" "$RUN_DIR/evidence/tc-09-01-edge.stderr.log"
```

**Then** no crash signature in either log — verify: the crash-signature scan returns nothing  
**And** `access violation` absent — verify: the grep produces no match in `tc-09-22-server.stderr.log`  
**And** `swig` absent — verify: no SWIG-level error surfaces; a SWIG director error means a FreeCAD binding fault reached the process  
**And** `segfault` and `fatal` absent — verify: no match in either log  
**And** no client error leaves a traceback — verify: the traceback count is `0` in both logs. Every deliberately invalid case is an `INVALID_INPUT`, which logs one `INFO` line and no stack (`rpc_dispatch.py:88-91`)  
**And** nothing raises past the dispatch boundary — verify: the final `except Exception` clause at `rpc_dispatch.py:156` is the single boundary; if a traceback does appear, it ends in `rpc_dispatch.py` with a mapped `RECOMPUTE_ERROR`, never in `mcp_server.py` or `rpc_listener.py`  
**And** both sweep gates are still green — verify: both report files have `all_passed` equal to `True`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not — the sweeps put the bridge through every failure path and it may not answer — fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* neither sweep reached the human's window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-22-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the golden model still whole and framed, the two images visually identical, and no crash dialog, error modal, or Windows fault popup raised. A clean stderr log is corroborating evidence; an intact window is the result. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-09-22-edge.stl" "$RUN_DIR/evidence/tc-09-22-edge_multi.step" "$RUN_DIR/evidence/tc-09-22-"*.step "$RUN_DIR/evidence/tc-09-22-"*.stl "$RUN_DIR/evidence/tc-09-22-scratch.FCStd"
```
```
mcp document_close { doc: <H> }
```

---

### TC-09-23: The server survives the entire abnormal sweep and still answers

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (no crash on any invalid input)

**Given** TC-09-03 through TC-09-22 have all run against the same server process — verify: the process id has not changed since the case series began  
**And** the server process id is recorded before the abnormal series begins  
**And** the window state after the abnormal series is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-23-before.png"}' | & cua-driver call get_window_state`. No fit precedes this capture: the point of the image is the state the abnormal series actually left behind, and framing it first would hide a viewport the abuse had already damaged.  

**When** the tools are listed after the last abnormal scenario  
```
mcp tools/list {}
```
**And** one full healthy round trip is driven: open a golden model as `<H>`, verify its shape, export STEP, verify the export, close the document  

**Then** the server still answers `tools/list` — verify: the call returns without error  
**And** the full tool surface is still present — verify: the listing holds the live count (45 typed tools, plus `script_exec` when it is on: 46 by default), the same count `tools/list` returned at the start of the run; a short count means the server degraded  
**And** the process id is unchanged — verify: the recorded id still names a live process; a new id means it crashed and restarted  
**And** the healthy round trip completes — verify: every call in the round trip returns `OK`  
**And** the exported geometry is still correct after all the abuse — verify: `verify_export_step` reports `export_step.volume` within 0.1 % of the golden model's analytic volume  
**And** no document was left open by the abnormal cases — verify: `mcp document_list {}` names no handle from TC-09-03 onward, and no `FCB_TMP_` document remains  
**And** no orphaned temp artifact remains — verify: the session temp folder `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/` (GUI workdir `%APPDATA%\FreeCAD\v1-1\freecad-buddy\workdir`) holds no `FCB_TMP_snap_*` or `FCB_TMP_prev_*` entry left by this case series. The agent shell may get "Access is denied" there: list it in-process with `mcp script_exec { doc: <any open handle>, code: "import os; result = os.listdir(r'<folder>')" }`  
**And** *(visual)* the model is framed, while `<H>` is still open and before the round trip's closing `document_close` — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not — this is the scenario that asks whether the abuse left the bridge able to work at all — fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test, and record that the MCP fit failed while the menu fit worked  
**And** *(visual)* the healthy round trip renders a correct model in the human's window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-09-23-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: the golden model shown whole and framed, the 3D view painting normally, and no dialog, modal, or crash popup left behind by the abnormal series. A live process id and a full tool listing are claims from the bridge; a blank, frozen, or half-painted viewport after all the abuse is the defect only the image can find. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-09-23-"*.step "$RUN_DIR/evidence/tc-09-23-"*.stl "$RUN_DIR/evidence/tc-09-23-"*.3mf
```
```
mcp document_close { doc: <any handle document_list still names> }
```
