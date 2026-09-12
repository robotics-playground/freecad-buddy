# TC-09: Error Contract & Fault Injection

Validates AD-17: every terminal status the client sees comes from the closed set, and the audit log
is append-only. The signature assertion of this file is WHICH rejection path fires — an MCP protocol
rejection at the input-schema gate (`isError` set, no envelope, so no status to read) versus a
semantic refusal that returns a real `INVALID_INPUT` envelope. Those are two different layers and
each edge scenario names the one it expects. Nothing here may crash the server.

## Prerequisites
- [ ] micromamba `fcb` env is H1-capable (verify: `"$USERPROFILE/micromamba/envs/fcb/python.exe" -c "import FreeCAD, mcp"`)
- [ ] Fault fixtures present (verify: `ls benchmarks/g0/fault-injection/wrong-volume/fixture.FCStd`)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/*.FCStd` lists 5 files)
- [ ] No stale H1 server holding the fixtures (verify: `netstat -ano | grep :8765` shows at most the GUI proxy)
- [ ] `_automation/` exists and is writable (verify: `mkdir -p _automation && touch _automation/.tc09 && rm _automation/.tc09`)

---

### TC-09-01: The legacy edge sweep is still green

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (status), `verification-design.md` §6.3 (fault detection)

**Preconditions**:
- [ ] No stale H1 server holding the fixtures (verify: no `freecad_buddy.hosts.main` process is running)

**Steps**:
1. Run the automated edge sweep. It spawns its own headless H1 server and drives the failure and
   boundary contract over real MCP stdio:
   ```bash
   uv run python scripts/automation/run_mcp_edge_cases.py
   ```

**Checkpoints**:
- [ ] CP1: the sweep gate is green — verify: `python3 -c "import json;print(json.load(open('_automation/edge_report.json'))['all_passed'])"` returns `True`
- [ ] CP2: the sweep records 14 checks, not 15 — verify: `python3 -c "import json;print(json.load(open('_automation/edge_report.json'))['total'])"` returns `14`. The former `docs/tests/TC-09` file claimed 15; it was removed in commit `4cc4ee5` and its count was already stale.
- [ ] CP3: every recorded check passed — verify: `python3 -c "import json;r=json.load(open('_automation/edge_report.json'));print(r['passed']==r['total'], r['failed'])"` returns `True 0`
- [ ] CP4: the retired-parameter check is present and asserts a SCHEMA rejection — verify: `python3 -c "import json;print([c for c in json.load(open('_automation/edge_report.json'))['checks'] if c['tool']=='retired_max_nodes_rejected'])"` shows one entry with `status` equal to `SCHEMA_ERROR`, not `OK`
- [ ] CP5: both planted-fault checks are present — verify: the `checks[*].tool` values include `fault_shape:wrong-volume` and `fault_shape:non-watertight-open-shell`, both with `ok` true
- [ ] CP6: the process exit code is 0 — verify: `echo $?` immediately after step 1 prints `0`
- [ ] CP7: no genuine crash in the sweep's server — verify: `grep -iE "access violation|swig|segfault|fatal" _automation/edge.stderr.log` returns nothing. Deliberate `ValidationError` tracebacks are expected, one per case.

**Cleanup**:
```bash
rm -f _automation/edge.stl _automation/edge_multi.step
```

---

### TC-09-02: Every observed terminal status is inside the closed set

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (closed terminal status set)

**Preconditions**:
- [ ] The edge sweep report exists from TC-09-01 (verify: `ls _automation/edge_report.json`)

**Steps**:
1. Read the shipped status vocabulary:
   ```bash
   python3 -c "import re;print(re.findall(r'\"(\w+)\"', open('src/freecad_buddy/contracts/status.py').read()))"
   ```
2. Collect every `status` value the sweeps recorded and compare it against that set:
   ```bash
   python3 -c "import json;r=json.load(open('_automation/edge_report.json'));print(sorted({c.get('status') for c in r['checks']}))"
   ```
3. Run the repo's own vocabulary gate:
   ```bash
   uv run python scripts/check_status_vocab.py
   ```

**Checkpoints**:
- [ ] CP1: the closed set is exactly seven members — verify: `TerminalStatus` in `src/freecad_buddy/contracts/status.py:11` declares `OK`, `SPEC_FAILED`, `RECOMPUTE_ERROR`, `TIMEOUT`, `OOM_KILLED`, `WORKER_CRASHED`, `INVALID_INPUT` and nothing else
- [ ] CP2: every status observed in the sweep is a member of that set, spelled exactly — verify: the step 2 output contains no value outside the seven, allowing for the harness's own non-status marker `SCHEMA_ERROR` used where there is no envelope
- [ ] CP3: no near-miss spelling reaches the client — verify: `grep -rnE "INVALID_ARGUMENT|VALIDATION_ERROR|BAD_INPUT|RECOMPUTE_FAILED|SPEC_FAIL\b" src/freecad_buddy/` returns nothing
- [ ] CP4: the vocabulary gate passes — verify: step 3 exits 0
- [ ] CP5: the set is closed, not fully reachable — verify: `OOM_KILLED` is NOT produced anywhere on the GUI or H1 path. The assertion is that the declared set admits no eighth member, NOT that every member can be triggered here. `WORKER_CRASHED` is likewise unreachable on the in-process hosts.
- [ ] CP6: no dispatch path can emit a status outside the boundary — verify: `MethodRegistry.dispatch` at `src/freecad_buddy/adapters/rpc_dispatch.py:108` maps every exception class to one of `INVALID_INPUT`, `TIMEOUT`, `RECOMPUTE_ERROR`, and its final `except Exception` clause guarantees nothing raises past it

**Cleanup**: none — read-only.

---

### TC-09-03: A missing schema-required field is a protocol rejection, not an envelope

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (schema gate vs. semantic refusal), `mcp-tools-design.md` §3.5

**Preconditions**:
- [ ] `box-10-20-30.FCStd` open as `<H>` with sole object `<OBJ>` (verify: `query_tree_summary` names it)

**Steps**:
1. Omit `path`, which `export_step` declares required:
   ```
   mcp export_step { doc: <H>, objects: [<OBJ>] }
   ```
2. Omit `doc`, required by `verify_shape`:
   ```
   mcp verify_shape { object: <OBJ> }
   ```
3. Omit `export_id`, required by `verify_export_stl`:
   ```
   mcp verify_export_stl { doc: <H> }
   ```
4. Omit `object`, required by `query_object`:
   ```
   mcp query_object { doc: <H> }
   ```

**Checkpoints**:
- [ ] CP1: missing `path` → MCP protocol rejection (`isError` set, `structuredContent` is `null`), NOT an `INVALID_INPUT` envelope
- [ ] CP2: missing `doc` → protocol rejection
- [ ] CP3: missing `export_id` → protocol rejection
- [ ] CP4: missing `object` → protocol rejection
- [ ] CP5: no envelope means no status field — verify: none of the four results has a `structuredContent.status`, so nothing may be read as `INVALID_INPUT`
- [ ] CP6: the two layers are distinguishable — verify: by contrast, `mcp verify_export_stl { doc: <H>, export_id: "fcb-export:bogus" }` satisfies the schema and DOES return an envelope with `status` equal to `INVALID_INPUT`

**Cleanup**: none — nothing was mutated.

---

### TC-09-04: A wrong JSON type for a declared field is a protocol rejection

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (typed schema gate)

**Preconditions**:
- [ ] `<H>` and `<OBJ>` resolved as in TC-09-03

**Steps**:
1. Pass a string where an integer is declared:
   ```
   mcp query_tree_summary { doc: <H>, depth: "1" }
   ```
2. Pass a number where a string is declared:
   ```
   mcp export_step { doc: <H>, path: 42, objects: [<OBJ>] }
   ```
3. Pass an object where an array is declared:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc09_t.step", objects: { "0": <OBJ> } }
   ```
4. Pass a string where a number is declared:
   ```
   mcp export_stl { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc09_t.stl", linear: "0.1" }
   ```

**Checkpoints**:
- [ ] CP1: `depth` as a string → protocol rejection (`isError`, no envelope)
- [ ] CP2: `path` as a number → protocol rejection
- [ ] CP3: `objects` as an object → protocol rejection
- [ ] CP4: `linear` as a string → protocol rejection
- [ ] CP5: no coercion happens — verify: none of the four produced a successful call; a JSON Schema `type` is a gate, never a cast
- [ ] CP6: nothing was written — verify: `ls _automation/tc09_t.*` reports no such files

**Cleanup**: none — no file was created.

---

### TC-09-05: An unknown key is a protocol rejection on every tool

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (`additionalProperties: false` everywhere)

**Preconditions**:
- [ ] `<H>` and `<OBJ>` resolved as in TC-09-03

**Steps**:
1. Confirm the schema fact across the whole surface:
   ```bash
   python3 -c "import json;d=json.load(open('_automation/tool_surface.json'));print(sorted(k for k,v in d.items() if v['addProps'] is not False))"
   ```
   Regenerate that file from `tools/list` first if it is absent.
2. Add one unknown key to several tools:
   ```
   mcp verify_shape       { doc: <H>, object: <OBJ>, strict: true }
   mcp query_tree_summary { doc: <H>, max_nodes: 50 }
   mcp export_step        { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc09_u.step", overwrite: true }
   mcp document_close     { doc: <H>, force: true }
   mcp query_capabilities { verbose: true }
   ```

**Checkpoints**:
- [ ] CP1: no tool permits extra properties — verify: step 1 prints an empty list; every input schema sets `additionalProperties: false`
- [ ] CP2: `verify_shape` with an unknown key → protocol rejection
- [ ] CP3: `query_tree_summary` with an unknown key → protocol rejection
- [ ] CP4: `export_step` with an unknown key → protocol rejection
- [ ] CP5: `document_close` with an unknown key → protocol rejection, and the document stays OPEN — verify: `document_list` still names `<H>`
- [ ] CP6: an empty-object schema still rejects extras — verify: `query_capabilities { verbose: true }` is a protocol rejection even though the tool declares no properties at all
- [ ] CP7: an unknown key is never silently dropped — verify: none of the five calls returned `OK`; a schema reject and a silent ignore are different outcomes and only the reject is correct

**Cleanup**: none — nothing was mutated.

---

### TC-09-06: Empty arrays are rejected where `minItems` applies

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (array bounds), `mcp-tools-design.md` §3.4

**Preconditions**:
- [ ] A scratch document `<H>` with a sketch `<SK>` exists (verify: `query_sketch_info` returns `OK` for `<SK>`)

**Steps**:
1. Pass an empty geometry list:
   ```
   mcp sketch_add_geometry { doc: <H>, sketch: <SK>, geometry: [], confirm: { preview_id: <P> } }
   ```
2. Pass a coordinate array below `minItems: 2`:
   ```
   mcp sketch_add_geometry { doc: <H>, sketch: <SK>, geometry: [
     { kind: "line_segment", start: [0], end: [10, 0] }
   ], confirm: { preview_id: <P> } }
   ```
3. Pass a coordinate array above `maxItems: 3`:
   ```
   mcp sketch_add_geometry { doc: <H>, sketch: <SK>, geometry: [
     { kind: "line_segment", start: [0, 0, 0, 0], end: [10, 0] }
   ], confirm: { preview_id: <P> } }
   ```
4. Pass an empty `objects` array to an export, which declares NO `minItems`:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc09_e.step", objects: [] }
   ```

**Checkpoints**:
- [ ] CP1: an empty `geometry` array → protocol rejection where the schema sets `minItems: 1`
- [ ] CP2: a 1-element coordinate array → protocol rejection (`minItems: 2`)
- [ ] CP3: a 4-element coordinate array → protocol rejection (`maxItems: 3`)
- [ ] CP4: the two bounds are distinct failures, not one generic one — verify: both CP2 and CP3 are rejections and neither produced an envelope
- [ ] CP5: an empty `objects` array is NOT a schema error — verify: step 4 returns a real envelope, because `export_step` declares no `minItems` on `objects`; the empty list falls through to the runtime default-selection path
- [ ] CP6: the sketch is unchanged — verify: `query_sketch_info { doc: <H>, sketch: <SK> }` reports the same `geometry_count` as before step 1

**Cleanup**:
```bash
rm -f _automation/tc09_e.step
```

---

### TC-09-07: Integer boundaries on `depth`, `max_edges`, and `occurrences`

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (numeric bounds), `mcp-tools-design.md` §3.2

**Preconditions**:
- [ ] `box40-hole-r5.FCStd` open as `<H>` (verify: `query_tree_summary` returns `OK`)

**Steps**:
1. Drive `depth`, declared `minimum: 1`:
   ```
   mcp query_tree_summary { doc: <H>, depth: 0 }
   mcp query_tree_summary { doc: <H>, depth: -1 }
   mcp query_tree_summary { doc: <H>, depth: 2147483647 }
   mcp query_tree_summary { doc: <H>, depth: 1 }
   ```
2. Drive `max_edges`, declared `minimum: 1`, default 2000:
   ```
   mcp query_dependencies { doc: <H>, max_edges: 0 }
   mcp query_dependencies { doc: <H>, max_edges: -1 }
   mcp query_dependencies { doc: <H>, max_edges: 1 }
   ```
3. Drive `occurrences` on `feature_pattern`, declared `minimum: 2`:
   ```
   mcp feature_pattern { doc: <H>, ..., kind: "linear", occurrences: 0, ... }
   mcp feature_pattern { doc: <H>, ..., kind: "linear", occurrences: 1, ... }
   ```

**Checkpoints**:
- [ ] CP1: `depth: 0` → protocol rejection (below `minimum: 1`)
- [ ] CP2: `depth: -1` → protocol rejection
- [ ] CP3: `depth: 2147483647` is inside the declared range, so it is accepted and bounded by the real tree — verify: an `OK` envelope whose `returned_nodes` equals the document's actual node count, with no hang
- [ ] CP4: `depth: 1` is the documented default and returns roots only — verify: `OK` with `returned_nodes` equal to `len(tree)`
- [ ] CP5: `max_edges: 0` and `max_edges: -1` → protocol rejection (below `minimum: 1`)
- [ ] CP6: `max_edges: 1` is legal and truncates — verify: `OK` with at most one edge reported
- [ ] CP7: `occurrences: 0` and `occurrences: 1` → protocol rejection (below `minimum: 2`); a one-occurrence pattern is not expressible on the wire
- [ ] CP8: a boundary rejection never reaches the handler — verify: `_automation/edge.stderr.log` or the addon log shows no `ValidationError` traceback for the rejected boundary calls, because the schema gate refused them first

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-09-08: null and absent behave distinguishably for optional fields

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (optional fields), `mcp-tools-design.md` §3.3

**Preconditions**:
- [ ] `box-10-20-30.FCStd` open as `<H>` with sole object `<OBJ>`

**Steps**:
1. Call `verify_shape` three ways:
   ```
   mcp verify_shape { doc: <H>, object: <OBJ> }
   mcp verify_shape { doc: <H>, object: <OBJ>, checks: null }
   mcp verify_shape { doc: <H>, object: <OBJ>, checks: [] }
   ```
2. Call `query_tree_summary` with `depth` absent versus `depth: null`:
   ```
   mcp query_tree_summary { doc: <H> }
   mcp query_tree_summary { doc: <H>, depth: null }
   ```
3. Call `export_step` with `ap` absent versus `ap: null`:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc09_n.step" }
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc09_n2.step", ap: null }
   ```

**Checkpoints**:
- [ ] CP1: `checks` absent returns measurement-only facts — verify: `OK` with five checks carrying no `expected` key
- [ ] CP2: `checks: null` is a protocol rejection — verify: `isError` set, because the schema declares `checks` as `array`, and `null` is not an array
- [ ] CP3: `checks: []` is accepted and takes the same measurement-only path — verify: `OK` with the same five fact ids as CP1; an empty list is falsy at `verify.py:332`
- [ ] CP4: `depth` absent applies the declared default of 1 — verify: `OK` with `returned_nodes` equal to the root count
- [ ] CP5: `depth: null` is a protocol rejection — verify: `isError` set; `null` is not an integer, so the default never applies
- [ ] CP6: `ap` absent applies the default `AP242` — verify: `grep -c AP242` on the written file is non-zero
- [ ] CP7: `ap: null` is a protocol rejection — verify: `isError` set; `null` is outside the enum `["AP214","AP242"]`, so it is not treated as "use the default"
- [ ] CP8: the distinction is consistent — verify: in every pair above, absent means "apply the declared default" and explicit `null` means "protocol rejection". They are never interchangeable.

**Cleanup**:
```bash
rm -f _automation/tc09_n.step _automation/tc09_n2.step
```

---

### TC-09-09: Very long strings are handled without truncation or crash

**Priority**: Medium
**Design Ref**: `data-contracts-design.md` §3 (string fields), `mcp-tools-design.md` §3.1

**Preconditions**:
- [ ] A scratch document is available (verify: `document_create` returns `OK`)

**Steps**:
1. Create a document whose label is 4096 characters (`document_create` declares `label`, not
   `name` — confirm with `python3 -c "import json;print(json.load(open('_automation/tool_surface.json'))['document_create'])"`):
   ```
   mcp document_create { label: "<4096 'a' characters>" }
   ```
2. Open a nonexistent path 8192 characters long:
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/_automation/<8192 'b' characters>.FCStd" }
   ```
3. Query an object name 65536 characters long:
   ```
   mcp query_object { doc: <H>, object: "<65536 'c' characters>" }
   ```

**Checkpoints**:
- [ ] CP1: the long document label returns a real envelope, not a crash — verify: `status` is `OK` or `INVALID_INPUT`, never absent
- [ ] CP2: if the label is accepted, it is not truncated — verify: `document_list` echoes back the same character count the call sent
- [ ] CP3: the long nonexistent path is refused cleanly — verify: `status` equals `INVALID_INPUT` with a message naming the path
- [ ] CP4: the long object name is refused cleanly — verify: `status` equals `INVALID_INPUT` with message `unknown object: ccc...`
- [ ] CP5: the traceback in `detail.data.traceback` is capped — verify: its length is at most 4000 characters, matching `_TRACEBACK_LIMIT` at `src/freecad_buddy/adapters/rpc_dispatch.py:24`
- [ ] CP6: the server survives — verify: `mcp query_capabilities {}` returns `OK` after step 3
- [ ] CP7: the 16 MiB frame cap is not reached by any of these — verify: no `handshake required` or frame-size error appears in the addon log

**Cleanup**:
```
mcp document_close { doc: <the long-named document, if created> }
```

---

### TC-09-10: Deeply nested objects in an untyped field

**Priority**: Medium
**Design Ref**: `data-contracts-design.md` §3 (untyped `checks` items), `verification-design.md` §5

**Preconditions**:
- [ ] `box-10-20-30.FCStd` open as `<H>` with sole object `<OBJ>`

**Steps**:
1. Confirm `checks` items are untyped objects: `verify_shape` declares `checks` as an array of
   objects with no per-item property schema, so nesting is not caught at the schema gate and MUST
   be caught at the handler.
2. Send a check nested 100 levels deep:
   ```
   mcp verify_shape { doc: <H>, object: <OBJ>, checks: [ { fn: { a: { a: { ... 100 deep ... } } } } ] }
   ```
3. Send a check that is not an object at all:
   ```
   mcp verify_shape { doc: <H>, object: <OBJ>, checks: ["expect_volume"] }
   ```
4. Send a well-formed check carrying a deeply nested `tol`:
   ```
   mcp verify_shape { doc: <H>, object: <OBJ>, checks: [{ fn: "expect_volume", expect: 6000, tol: { rel: { deep: { deeper: 0.001 } } } }] }
   ```

**Checkpoints**:
- [ ] CP1: the deeply nested `fn` is refused by the handler, not the schema — verify: a real envelope with `status` equal to `INVALID_INPUT` and a message starting `unknown assertion fn:`
- [ ] CP2: a non-object check is refused — verify: `status` equals `INVALID_INPUT` with message `check must be an object, got 'expect_volume'`
- [ ] CP3: a nested `tol` does not crash the tolerance resolver — verify: step 4 returns a real envelope; a `rel` that is not a number becomes a `TypeError`/`ValueError` mapped to `INVALID_INPUT` at `rpc_dispatch.py:124`, never an unhandled fault
- [ ] CP4: no rejection here is a protocol rejection — verify: all three calls carry `structuredContent` with a `status`, because the untyped item schema admitted them
- [ ] CP5: the server survives the nesting — verify: `mcp verify_shape { doc: <H>, object: <OBJ> }` still returns `OK` afterwards
- [ ] CP6: no recursion error escapes — verify: `grep -i "RecursionError" _automation/edge.stderr.log` and the addon log return nothing

**Cleanup**: none — read-only.

---

### TC-09-11: The retired `max_nodes` parameter is a schema rejection

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (`additionalProperties: false`), `mcp-tools-design.md` §3.2

**Preconditions**:
- [ ] `box-10-20-30.FCStd` open as `<H>`

**Steps**:
1. Pass the retired parameter:
   ```
   mcp query_tree_summary { doc: <H>, max_nodes: 0 }
   mcp query_tree_summary { doc: <H>, max_nodes: 50 }
   ```
2. Confirm the shipped property list:
   ```bash
   python3 -c "import json;print(json.load(open('_automation/tool_surface.json'))['query_tree_summary']['props'])"
   ```

**Checkpoints**:
- [ ] CP1: `max_nodes: 0` → protocol rejection (`isError`, no envelope)
- [ ] CP2: `max_nodes: 50` → protocol rejection; the value is irrelevant, the key itself is unknown
- [ ] CP3: the OLD documented behaviour is GONE — verify: neither call returns `OK`, neither returns empty `nodes`, and neither returns `truncated: true`. The former `docs/tests/TC-09` CP6 asserted `OK` + truncated; that expectation is stale and must not be revived from git history.
- [ ] CP4: the shipped property list confirms the retirement — verify: step 2 prints `['doc', 'depth', 'root', 'filters']` with no `max_nodes`
- [ ] CP5: `truncated` is no longer a response field — verify: a successful `query_tree_summary { doc: <H> }` returns `structured_content` with no `truncated` key
- [ ] CP6: bounding now happens through `depth` — verify: `depth: 1` returns roots only and `returned_nodes` equals `len(tree)`
- [ ] CP7: the automated sweep asserts the same thing — verify: `_automation/edge_report.json` names `retired_max_nodes_rejected` as a passed check

**Cleanup**: none — read-only.

---

### TC-09-12: An unknown doc handle returns INVALID_INPUT

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (handle resolution), `verification-design.md` §6.3

**Preconditions**:
- [ ] The handle `fcb-doc:does-not-exist` was never issued by this session (verify: `mcp document_list {}` does not list it)

**Steps**:
1. Call several tools with a handle that was never issued:
   ```
   mcp query_tree_summary { doc: "fcb-doc:does-not-exist" }
   mcp verify_recompute   { doc: "fcb-doc:does-not-exist" }
   mcp query_object       { doc: "fcb-doc:does-not-exist", object: "Box" }
   mcp document_close     { doc: "fcb-doc:does-not-exist" }
   ```
2. Open a document, close it, then reuse the now-stale handle.

**Checkpoints**:
- [ ] CP1: unknown doc handle → `INVALID_INPUT` (a real envelope, not a protocol rejection)
- [ ] CP2: the same refusal on a read-only tool and a mutating one — verify: all four calls in step 1 return `status` equal to `INVALID_INPUT`
- [ ] CP3: the message names the handle — verify: each `detail.message` contains `fcb-doc:does-not-exist`
- [ ] CP4: `detail.code` mirrors the status — verify: `detail.code` equals `INVALID_INPUT`
- [ ] CP5: a stale handle after close behaves identically — verify: step 2 returns `INVALID_INPUT`, and a second `document_close` on the same handle also returns `INVALID_INPUT` with no crash
- [ ] CP6: the handle format is not what is checked — verify: a well-formed but unissued handle and a malformed string both return `INVALID_INPUT`; the refusal comes from registry lookup, not from a format test

**Cleanup**: none — nothing was mutated.

---

### TC-09-13: An unknown object name returns INVALID_INPUT

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3, `verification-design.md` §5

**Preconditions**:
- [ ] `box-10-20-30.FCStd` open as `<H>`

**Steps**:
1. Name an object that does not exist, across the read surface:
   ```
   mcp query_object          { doc: <H>, object: "NoSuchObject" }
   mcp query_mass_properties { doc: <H>, object: "NoSuchObject" }
   mcp query_placement       { doc: <H>, object: "NoSuchObject" }
   mcp verify_shape          { doc: <H>, object: "NoSuchObject" }
   ```
2. Name it in an export selection:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc09_o.step", objects: ["NoSuchObject"] }
   ```

**Checkpoints**:
- [ ] CP1: every read tool returns `INVALID_INPUT` — verify: all four step 1 envelopes carry `status` equal to `INVALID_INPUT`
- [ ] CP2: `verify_shape` names the object in its message — verify: `detail.message` equals `unknown object: NoSuchObject`
- [ ] CP3: the export path names it identically — verify: step 2's `detail.message` equals `unknown object: NoSuchObject`
- [ ] CP4: the failed export wrote nothing — verify: `ls _automation/tc09_o.step` reports no such file
- [ ] CP5: a name that differs only by case is also unknown — verify: `object: "box"` when the real name is `Box` returns `INVALID_INPUT`; object names are matched exactly
- [ ] CP6: an empty object name is refused distinctly — verify: `mcp verify_shape { doc: <H>, object: "" }` returns `INVALID_INPUT` with message `missing required 'object' name`

**Cleanup**: none — no file was created.

---

### TC-09-14: An unknown sketch or feature name returns INVALID_INPUT

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3, `mcp-tools-design.md` §3.4

**Preconditions**:
- [ ] A scratch document `<H>` with one real sketch `<SK>` exists (verify: `verify_sketch { doc: <H>, sketch: <SK> }` returns an envelope)

**Steps**:
1. Name a sketch that does not exist:
   ```
   mcp verify_sketch     { doc: <H>, sketch: "NoSuchSketch" }
   mcp query_sketch_info { doc: <H>, sketch: "NoSuchSketch" }
   ```
2. Name a real object that is NOT a sketch:
   ```
   mcp verify_sketch { doc: <H>, sketch: "<a real non-sketch object name>" }
   ```
3. Name a feature that does not exist:
   ```
   mcp feature_set_parameters { doc: <H>, feature: "NoSuchFeature", ..., confirm: { preview_id: <P> } }
   ```

**Checkpoints**:
- [ ] CP1: unknown sketch → `INVALID_INPUT` with message `unknown object: NoSuchSketch`
- [ ] CP2: `query_sketch_info` refuses the same name the same way — verify: `status` equals `INVALID_INPUT`
- [ ] CP3: a real object that is not a sketch is a DIFFERENT refusal — verify: `detail.message` equals `object is not a sketch: <name>`, distinguishing "absent" from "wrong type"
- [ ] CP4: unknown feature → `INVALID_INPUT` — verify: `status` equals `INVALID_INPUT`, never `RECOMPUTE_ERROR`
- [ ] CP5: no mutation occurred — verify: `verify_recompute { doc: <H> }` returns `OK` and `query_tree_summary` reports the same node count as before step 3
- [ ] CP6: the refusal is logged as a client error, not a fault — verify: the addon log carries one `INFO` line for each refusal and no traceback

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-09-15: A non-string `doc` is rejected before dispatch

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (pre-dispatch guard), `mcp-tools-design.md` §3.1

**Preconditions**:
- [ ] The inline H1 host is reachable (verify: `uv run python scripts/automation/run_mcp_edge_cases.py` has completed at least once)

**Steps**:
1. Against the INLINE host (`freecad_buddy.hosts.main serve --mode inline --transport stdio`), send a
   `doc` that satisfies the schema's union type but is not a string:
   ```
   mcp verify_recompute { doc: { "handle": "fcb-doc:x" } }
   ```
2. Repeat the same call against the H2 proxy on `:8765`.

**Checkpoints**:
- [ ] CP1: the inline host refuses pre-dispatch — verify: the envelope `status` equals `INVALID_INPUT` with `detail.message` equal to `doc handle must be a string`
- [ ] CP2: the message comes from the host, not a use case — verify: `grep -n "doc handle must be a string" src/freecad_buddy/adapters/mcp_server.py` locates the guard, and no use-case module emits that string
- [ ] CP3: no document registry lookup ran — verify: the message names the type problem, not a missing handle
- [ ] CP4: the H2 proxy DIVERGES — verify: `src/freecad_buddy/hosts/gui_external/entry.py` has its own `_call_tool` with no non-string-`doc` guard, so the same call surfaces differently there. Record the actual H2 status and message as evidence; do not fail the case on the divergence, it is a known and documented gap.
- [ ] CP5: the divergence is limited to this guard, the suspect-document logic, and audit writes — verify: `grep -n "_call_tool" src/freecad_buddy/hosts/gui_external/entry.py src/freecad_buddy/adapters/mcp_server.py` shows two distinct implementations
- [ ] CP6: neither host crashes — verify: both still answer `tools/list` after the call

**Divergence handling**:
- CP4 is a **recorded divergence**, not a regression. Write down the exact H2 status string. A
  change in H2 behaviour toward the inline host's message is a promotion signal.

**Cleanup**: none — read-only.

---

### TC-09-16: Opening a nonexistent path returns INVALID_INPUT

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3, `mcp-tools-design.md` §3.1

**Preconditions**:
- [ ] The target paths do not exist (verify: `ls _automation/nope-missing.FCStd _automation/no_such_dir/x.FCStd 2>&1` reports no such file)

**Steps**:
1. Open paths that do not exist:
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/_automation/nope-missing.FCStd" }
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/_automation/no_such_dir/x.FCStd" }
   mcp document_open { path: "" }
   ```
2. Open a path that exists but is not a FreeCAD document:
   ```
   mcp document_open { path: "README.md" }
   ```

**Checkpoints**:
- [ ] CP1: a missing file → `INVALID_INPUT` (a real envelope)
- [ ] CP2: a missing directory → `INVALID_INPUT`
- [ ] CP3: an empty path → `INVALID_INPUT`, never a silently created document
- [ ] CP4: the message names the path — verify: each `detail.message` contains the path string that was sent
- [ ] CP5: a non-FreeCAD file is refused, not half-opened — verify: step 2 returns a non-`OK` status and `document_list` names no new handle
- [ ] CP6: no handle is issued for any refused open — verify: none of the four envelopes carries a `structured_content.doc`
- [ ] CP7: the automated sweep asserts the same — verify: `_automation/edge_report.json` names `open_bad_path` as a passed check

**Cleanup**: none — nothing was opened.

---

### TC-09-17: A broken recompute returns RECOMPUTE_ERROR, not a false OK

**Priority**: Critical
**Design Ref**: `verification-design.md` §6.3 (recompute grading), `data-contracts-design.md` §3

**Preconditions**:
- [ ] A document with at least one object that fails to recompute (verify: build one by setting a pad length that cannot resolve, or use a fixture whose object reports an error state)

**Steps**:
1. Produce a document `<H>` holding a failing object. A pad whose sketch has been emptied, or a
   feature whose profile was removed, leaves the object in an `Invalid`/`Error`/`Touched` state.
2. Grade it:
   ```
   mcp verify_recompute { doc: <H> }
   ```
3. Grade the same document a second time to confirm the result is stable, not a first-call artifact.

**Checkpoints**:
- [ ] CP1: the status is `RECOMPUTE_ERROR`, never `OK` — verify: the envelope `status` equals `RECOMPUTE_ERROR`
- [ ] CP2: the verdict is derived, not asserted — verify: `structured_content.verdict` equals `RECOMPUTE_ERROR` and equals the envelope `status`
- [ ] CP3: the failing check is tagged so the verdict classes correctly — verify: at least one check has id `recompute.object` with `passed: false` and `detail.code` equal to `recompute.error`
- [ ] CP4: the summary names the count — verify: the envelope `text` matches `Recompute: <n> error(s): <names>.`
- [ ] CP5: an object still `Touched` after a full recompute counts as an error — verify: `_RECOMPUTE_ERROR_STATES` at `src/freecad_buddy/usecases/verify.py:24` includes `Touched`, catching a silently skipped recompute that would otherwise read as clean
- [ ] CP6: the result is stable across calls — verify: step 3 returns the same status and the same `subject.failing_objects` list
- [ ] CP7: a clean document in the same session still grades `OK` — verify: `verify_recompute` on `box-10-20-30.FCStd` returns `OK`, proving the `RECOMPUTE_ERROR` is document-specific and not a stuck server state

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-09-18: A broken reference surfaces the failing object and its status string

**Priority**: Critical
**Design Ref**: `verification-design.md` §6.3 (failing-object reporting)

**Preconditions**:
- [ ] A document `<H>` where one object references a deleted or unresolvable dependency

**Steps**:
1. Break a reference: delete the sketch a pad depends on, or remove an external geometry link.
2. Grade the document:
   ```
   mcp verify_recompute { doc: <H> }
   ```
3. Read the dependency graph to confirm the broken edge:
   ```
   mcp query_dependencies { doc: <H> }
   ```

**Checkpoints**:
- [ ] CP1: the failing object is named — verify: `structured_content.subject.failing_objects` contains the broken object's `Name`
- [ ] CP2: the object's own status string is carried through — verify: the `recompute.object` check `measured` equals the value FreeCAD's `getStatusString()` returns for that object, not a rewritten message
- [ ] CP3: the check detail pairs name and status — verify: `detail.message` equals `<Name>: <status string>`
- [ ] CP4: the detail lists the object for the client — verify: the `recompute.object` check `detail.objects` equals `["<Name>"]`
- [ ] CP5: one check per failing object — verify: `len(structured_content.checks)` equals `len(subject.failing_objects)`
- [ ] CP6: the status string is non-empty — verify: `measured` is not the empty string; an empty value means `getStatusString` was unavailable and the diagnostic is lost
- [ ] CP7: the dependency query still answers — verify: step 3 returns `OK` and the graph shows the missing target, so a broken reference does not break the read surface

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-09-19: An unwritable audit-log path degrades without losing the status

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (AD-17 audit), `verification-design.md` §6.3

**Preconditions**:
- [ ] A path that cannot be written (verify: a directory used as the log file path, or a read-only location)

**Steps**:
1. Start a headless H1 server with the audit log pointed at an unwritable target:
   ```bash
   FREECAD_BUDDY_AUDIT_LOG=_automation/tc09_unwritable_dir \
     mkdir -p _automation/tc09_unwritable_dir
   ```
   The env var names a path that is a DIRECTORY, so every append attempt fails.
2. Drive one mutating call (a `document_create`, then a `document_close`) and one read-only call
   through that server.
3. Read the resulting envelopes and the server stderr.

**Checkpoints**:
- [ ] CP1: the mutating call still returns a real envelope with a status from the closed set — verify: `status` is `OK` or a named failure, never absent
- [ ] CP2: the operation's OWN status is not replaced by the audit failure — verify: a successful `document_create` still reports `OK`; the audit sink is not allowed to turn a good mutation into an error
- [ ] CP3: the read-only call is unaffected — verify: `query_capabilities {}` returns `OK`
- [ ] CP4: the failure is visible, not silent — verify: the server stderr or addon log records the audit write failure; a lost audit line that leaves no trace is the defect this checkpoint guards against
- [ ] CP5: the server survives — verify: `tools/list` still answers after step 2
- [ ] CP6: restoring a writable path restores auditing — verify: pointing `FREECAD_BUDDY_AUDIT_LOG` at `_automation/tc09_audit.jsonl` and repeating step 2 produces `before` and `after` records in that file

**Cleanup**:
```bash
rmdir _automation/tc09_unwritable_dir
rm -f _automation/tc09_audit.jsonl
```

---

### TC-09-20: The audit log is append-only

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (AD-17 append-only audit)

**Preconditions**:
- [ ] A writable audit target (verify: `rm -f _automation/tc09_append.jsonl`)

**Steps**:
1. Point the audit log at a fresh file and run three mutating calls through a server started with
   `FREECAD_BUDDY_AUDIT_LOG=_automation/tc09_append.jsonl`.
2. Snapshot the file after each call:
   ```bash
   cp _automation/tc09_append.jsonl _automation/tc09_snap_1.jsonl   # after call 1
   cp _automation/tc09_append.jsonl _automation/tc09_snap_2.jsonl   # after call 2
   cp _automation/tc09_append.jsonl _automation/tc09_snap_3.jsonl   # after call 3
   ```
3. Compare each snapshot against the prefix of the next:
   ```bash
   python3 -c "
   a=open('_automation/tc09_snap_1.jsonl').read()
   b=open('_automation/tc09_snap_2.jsonl').read()
   c=open('_automation/tc09_snap_3.jsonl').read()
   print(b.startswith(a), c.startswith(b), len(a)<len(b)<len(c))"
   ```

**Checkpoints**:
- [ ] CP1: each snapshot is a strict prefix of the next — verify: step 3 prints `True True True`
- [ ] CP2: no earlier line is ever rewritten — verify: `diff <(head -n $(wc -l < _automation/tc09_snap_1.jsonl) _automation/tc09_snap_3.jsonl) _automation/tc09_snap_1.jsonl` returns nothing
- [ ] CP3: the file only grows — verify: the three byte counts are strictly increasing
- [ ] CP4: every line is a complete JSON object — verify: `python3 -c "import json;[json.loads(l) for l in open('_automation/tc09_append.jsonl')]"` raises nothing
- [ ] CP5: every record declares the schema — verify: every line's `schema` field equals `fcb.audit-record/1`
- [ ] CP6: each mutation wrote a before and an after record — verify: the line count is at least twice the mutation count, and the `after` lines carry a `verify_verdict` while the `before` lines do not
- [ ] CP7: the sink never truncates or rotates — verify: `grep -nE "\"w\"|truncate|rotate|os.remove" src/freecad_buddy/adapters/audit_log.py` returns nothing; the only open mode in the file is `"a"` at `audit_log.py:46`

**Cleanup**:
```bash
rm -f _automation/tc09_append.jsonl _automation/tc09_snap_*.jsonl
```

---

### TC-09-21: Client errors log one INFO line while keeping the traceback in the envelope

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (error detail), `verification-design.md` §6.3

**Preconditions**:
- [ ] A server whose stderr is captured to a file (verify: `ls _automation/edge.stderr.log`)

**Steps**:
1. Drive a run of client errors through the H1 server and capture stderr:
   ```bash
   uv run python scripts/automation/run_mcp_edge_cases.py
   ```
2. Inspect one `INVALID_INPUT` envelope's `detail.data`.
3. Count how the error channel recorded the same calls:
   ```bash
   grep -c "INVALID_INPUT" _automation/edge.stderr.log
   grep -cE "^Traceback" _automation/edge.stderr.log
   ```

**Checkpoints**:
- [ ] CP1: the envelope retains the traceback — verify: `detail.data.traceback` is a non-empty string for an `INVALID_INPUT` result
- [ ] CP2: the traceback is truncated at the declared limit — verify: `len(detail.data.traceback)` is at most 4000, matching `_TRACEBACK_LIMIT` at `rpc_dispatch.py:24`
- [ ] CP3: the exception class is recorded — verify: `detail.data.exception` equals `ValidationError` for a handle or object refusal
- [ ] CP4: a client error logs one line, not a stack — verify: `INVALID_INPUT` and `TIMEOUT` take the `logger.info` branch at `rpc_dispatch.py:71`, which is reached because both are members of `_EXPECTED_CLIENT_STATUSES` at `rpc_dispatch.py:28`
- [ ] CP5: only the unexpected class spills a stack to stderr — verify: `rpc_dispatch.py:69` writes the traceback to stderr only when the status is outside `_EXPECTED_CLIENT_STATUSES` or `unexpected` is set
- [ ] CP6: an unexpected fault is flagged as such — verify: a `RECOMPUTE_ERROR` produced by the final `except Exception` clause carries `detail.data.unexpected` equal to `true`, while an `INVALID_INPUT` does not carry that key at all
- [ ] CP7: the error channel stays readable — verify: the stderr traceback count is far below the total call count; a traceback per client error would make the log unusable

**Cleanup**: none — read-only.

---

### TC-09-22: No unhandled traceback appears in stderr across the whole sweep

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (nothing raises past the dispatch boundary)

**Preconditions**:
- [ ] Both sweeps have run in this session (verify: `ls _automation/e2e_report.json _automation/edge_report.json`)

**Steps**:
1. Run both sweeps so their stderr logs are current:
   ```bash
   uv run python scripts/automation/run_mcp_e2e.py
   uv run python scripts/automation/run_mcp_edge_cases.py
   ```
2. Scan both logs for genuine crash signatures:
   ```bash
   grep -iE "access violation|swig|segfault|fatal" _automation/server.stderr.log _automation/edge.stderr.log
   ```
3. Confirm that the tracebacks present are the deliberate ones:
   ```bash
   grep -cE "^Traceback" _automation/edge.stderr.log
   grep -c "ValidationError" _automation/edge.stderr.log
   ```

**Checkpoints**:
- [ ] CP1: no crash signature in either log — verify: step 2 returns nothing
- [ ] CP2: `access violation` absent — verify: the grep produces no match in `server.stderr.log`
- [ ] CP3: `swig` absent — verify: no SWIG-level error surfaces; a SWIG director error means a FreeCAD binding fault reached the process
- [ ] CP4: `segfault` and `fatal` absent — verify: no match in either log
- [ ] CP5: the remaining tracebacks are the deliberate ones — verify: every `Traceback` in `edge.stderr.log` is followed by a `ValidationError` line, one per deliberately invalid case
- [ ] CP6: no traceback names a module outside the dispatch boundary — verify: no traceback terminates in `mcp_server.py` or `rpc_listener.py` without a mapped status; `rpc_dispatch.py:127` is the single boundary and nothing raises past it
- [ ] CP7: both sweep gates are still green — verify: both report files have `all_passed` equal to `True`

**Cleanup**:
```bash
rm -f _automation/edge.stl _automation/edge_multi.step _automation/*.step _automation/*.stl _automation/scratch.FCStd
```

---

### TC-09-23: The server survives the entire abnormal sweep and still answers

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (no crash on any invalid input)

**Preconditions**:
- [ ] TC-09-03 through TC-09-22 have all run against the same server process (verify: the process id has not changed since the case series began)

**Steps**:
1. Record the server process id before the abnormal series begins.
2. After the last abnormal scenario, list the tools:
   ```
   mcp tools/list {}
   ```
3. Drive one full healthy round trip: open a golden model, verify its shape, export STEP, verify the
   export, close the document.

**Checkpoints**:
- [ ] CP1: the server still answers `tools/list` — verify: the call returns without error
- [ ] CP2: the full tool surface is still present — verify: the listing holds 44 tools, plus `debug_exec` only when `FREECAD_BUDDY_ALLOW_EXEC=1` is set; a short count means the server degraded
- [ ] CP3: the process id is unchanged — verify: the recorded id from step 1 still names a live process; a new id means it crashed and restarted
- [ ] CP4: the healthy round trip completes — verify: every call in step 3 returns `OK`
- [ ] CP5: the exported geometry is still correct after all the abuse — verify: `verify_export_step` reports `export_step.volume` within 0.1 % of the golden model's analytic volume
- [ ] CP6: no document was left open by the abnormal cases — verify: `mcp document_list {}` names no handle from TC-09-03 onward, and no `FCB_TMP_` document remains
- [ ] CP7: no orphaned temp artifact remains — verify: `ls -d ${TMPDIR:-/tmp}/FCB_TMP_snap_* ${TMPDIR:-/tmp}/FCB_TMP_prev_* 2>/dev/null` reports nothing left by this case series

**Cleanup**:
```bash
rm -f _automation/tc09_*.step _automation/tc09_*.stl _automation/tc09_*.3mf
```
```
mcp document_close { doc: <any handle document_list still names> }
```
