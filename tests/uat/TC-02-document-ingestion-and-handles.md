# TC-02: Document Ingestion & Handles

Validates AD-20: every document operation targets an explicit opaque `fcb-doc:<token>` handle and
the bridge never reads `ActiveDocument`. Covers the full lifecycle (create, open, save, save-as,
close, list) and the read-only query surface that reads through a handle (`query_tree_summary`,
`query_object`, `query_dependencies`, `query_placement`). Also covers handle staleness, GUI-opened
document adoption, and the `FCB_TMP_` prefix rule for bridge-owned temporary artifacts. Executed by
the agent against the live GUI bridge.

**Host note**: unless a scenario says otherwise, MCP calls run under the **H2 proxy** host
(`gui_external/entry.py`). That path has its own `_call_tool` and does **not** carry the
non-string-`doc` guard, the suspect-document logic, or the audit writes that the inline host in
`adapters/mcp_server.py` has. TC-02-15 CP7 names the one checkpoint that must run under the inline
host instead.

## Prerequisites

- [ ] FreeCAD GUI is running and the bridge answers (verify: `mcp query_capabilities {}` returns `status: "OK"`)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/*.FCStd` lists 5 files)
- [ ] A writable scratch directory exists (verify: `mkdir -p _automation && ls -d _automation`)
- [ ] No document is open at the start (verify: `mcp document_list {}` returns `0 open document(s).`)

---

### TC-02-01: Create, list, save, close round trip

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document lifecycle), `data-contracts-design.md` §9 (handle contract)

**Preconditions**:
- [ ] No document is open (verify: `mcp document_list {}` returns `0 open document(s).`)

**Steps**:
1. Create a document with an explicit label.
   ```
   mcp document_create { label: "uat-roundtrip" }
   ```
2. List the open documents.
   ```
   mcp document_list {}
   ```
3. Save it to an explicit path. A document created without a `path` is transient and has no save
   target, so a bare save must be refused first.
   ```
   mcp document_save { doc: <handle> }
   mcp document_save { doc: <handle>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/uat-roundtrip.FCStd" }
   ```
4. Close it and list again.
   ```
   mcp document_close { doc: <handle> }
   mcp document_list {}
   ```

**Checkpoints**:
- [ ] CP1: The handle is opaque and session-minted — verify: `structured_content.doc` matches `^fcb-doc:` and is not the FreeCAD `Name`
- [ ] CP2: The create response names the document — verify: `structured_content` carries `doc`, `name`, and `label`, with `label` equal to `uat-roundtrip`
- [ ] CP3: The list reports the document as transient before any save — verify: `mcp document_list {}` shows one entry whose `doc` equals the handle and whose `transient` is `true`
- [ ] CP4: A bare save on a transient document is refused — verify: the first `document_save` returns `INVALID_INPUT` with message `document has no save target; call document_save with a 'path' first`
- [ ] CP5: Save-as writes the file — verify: `ls -l _automation/uat-roundtrip.FCStd` lists a non-empty file and the response `structured_content.saved` is `true`
- [ ] CP6: The document is no longer transient after the save-as — verify: `mcp document_list {}` now shows `transient: false` for that handle
- [ ] CP7: Close releases the handle — verify: `document_close` returns `status: "OK"` with `closed: true`, and the following `mcp document_list {}` returns `0 open document(s).`
- [ ] CP8: The saved file survives the close — verify: `ls -l _automation/uat-roundtrip.FCStd` still lists the file

**Cleanup**:
```bash
rm -f _automation/uat-roundtrip.FCStd
```

---

### TC-02-02: Open a golden model and read its tree

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_open), §3.2 (query_tree_summary)

**Preconditions**:
- [ ] `box-10-20-30.FCStd` exists (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)
- [ ] No document is open (verify: `mcp document_list {}` returns `0 open document(s).`)

**Steps**:
1. Open the golden model.
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd" }
   ```
2. Read the tree through the returned handle.
   ```
   mcp query_tree_summary { doc: <handle> }
   ```
3. Read the one object it contains.
   ```
   mcp query_object { doc: <handle>, object: "Box" }
   ```

**Checkpoints**:
- [ ] CP1: Open returns a handle and the source path — verify: `structured_content` carries `doc`, `name`, `label`, and `path` equal to the path passed in
- [ ] CP2: The summary text is the shipped form — verify: the envelope `text` is `Opened box-10-20-30 -> fcb-doc:<token>.`
- [ ] CP3: The tree reports one object — verify: `structured_content.total_objects` is `1` and `returned_nodes` is `1`
- [ ] CP4: The node is the golden `Box` — verify: `structured_content.tree[0].name` is `Box` and `type` is `Part::Feature`
- [ ] CP5: The node is clean, so no error field appears — verify: `structured_content.tree[0]` has no `error` key, because `getStatusString()` returned `Valid`
- [ ] CP6: `query_object` reads the same object through the same handle — verify: `structured_content.name` is `Box`, `type` is `Part::Feature`, and `error` is `null`
- [ ] CP7: The properties dict is JSON-safe — verify: `structured_content.properties` is an object whose values are all JSON scalars, arrays, objects, or strings, with no Python `repr` of a live FreeCAD pointer beyond a stringified value
- [ ] CP8: The volume is analytic — verify: `mcp query_mass_properties { doc: <handle>, object: "Box" }` returns `volume` `6000.0` within 0.1 %

**Cleanup**:
```
mcp document_close { doc: <handle> }
```

---

### TC-02-03: Save-as writes a new path and rebinds the handle

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_save), `data-contracts-design.md` §9 (handle stability)

**Preconditions**:
- [ ] `cylinder-r5-h20.FCStd` exists (verify: `ls benchmarks/g0/golden-models/cylinder-r5-h20.FCStd`)
- [ ] `_automation/uat-saveas.FCStd` does not exist (verify: `ls _automation/uat-saveas.FCStd` reports no such file)

**Steps**:
1. Open the golden model and record its handle.
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/cylinder-r5-h20.FCStd" }
   ```
2. Save it to a new path.
   ```
   mcp document_save { doc: <handle>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/uat-saveas.FCStd" }
   ```
3. Query through the same handle afterwards.
   ```
   mcp query_tree_summary { doc: <handle> }
   ```

**Checkpoints**:
- [ ] CP1: The new file is written — verify: `ls -l _automation/uat-saveas.FCStd` lists a non-empty file
- [ ] CP2: The original golden file is untouched — verify: the mtime and size of `benchmarks/g0/golden-models/cylinder-r5-h20.FCStd` are unchanged from before step 2
- [ ] CP3: The handle string is unchanged by the save-as — verify: the `structured_content.doc` in the save response equals the handle from step 1, character for character
- [ ] CP4: The handle still resolves after the rebind — verify: step 3 returns `status: "OK"` with `total_objects` `1`
- [ ] CP5: The object survives the save-as — verify: `structured_content.tree[0].name` is `Cylinder`
- [ ] CP6: The new file reopens independently — verify: closing the handle and running `mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/_automation/uat-saveas.FCStd" }` yields a fresh handle whose `query_mass_properties` on `Cylinder` returns `volume` `1570.7963` within 0.1 %

**Cleanup**:
```
mcp document_close { doc: <handle> }
```
```bash
rm -f _automation/uat-saveas.FCStd
```

---

### TC-02-04: Two open documents stay isolated

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (explicit handle, never ActiveDocument), `data-contracts-design.md` §9 (AD-20)

**Preconditions**:
- [ ] `box-10-20-30.FCStd` and `sphere-r10.FCStd` both exist (verify: `ls benchmarks/g0/golden-models/{box-10-20-30,sphere-r10}.FCStd`)
- [ ] No document is open (verify: `mcp document_list {}` returns `0 open document(s).`)

**Steps**:
1. Open both golden models, recording handle A (box) and handle B (sphere).
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd" }
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/sphere-r10.FCStd" }
   ```
2. Select the **sphere** document in the FreeCAD tree, so FreeCAD's `ActiveDocument` is B while the
   queries below target A.
   ```
   cua get_window_state { pid: <freecad pid>, window_id: <window id> }
   cua click { pid: <freecad pid>, window_id: <window id>, element_token: <sphere-r10 tree item token> }
   ```
3. Query A and B separately, without changing the GUI selection between calls.
   ```
   mcp query_tree_summary { doc: <handle A> }
   mcp query_tree_summary { doc: <handle B> }
   mcp query_object { doc: <handle A>, object: "Box" }
   mcp query_object { doc: <handle B>, object: "Sphere" }
   ```

**Checkpoints**:
- [ ] CP1: Two distinct handles were minted — verify: handle A and handle B are different strings, both matching `^fcb-doc:`
- [ ] CP2: `document_list` shows both — verify: `mcp document_list {}` reports `2 open document(s): box-10-20-30, sphere-r10.`
- [ ] CP3: A query on A returns A's object while B is the GUI's active document — verify: `query_tree_summary { doc: <handle A> }` returns `tree[0].name` `Box`, never `Sphere`
- [ ] CP4: A query on B returns B's object — verify: `query_tree_summary { doc: <handle B> }` returns `tree[0].name` `Sphere`
- [ ] CP5: An object name that exists only in B is unknown in A — verify: `mcp query_object { doc: <handle A>, object: "Sphere" }` returns `INVALID_INPUT` with message `unknown object: Sphere`
- [ ] CP6: The reverse holds — verify: `mcp query_object { doc: <handle B>, object: "Box" }` returns `INVALID_INPUT` with message `unknown object: Box`
- [ ] CP7: Mass properties do not cross documents — verify: `query_mass_properties` on A's `Box` returns `6000.0` and on B's `Sphere` returns `4188.7902`, each within 0.1 %
- [ ] CP8: Closing A leaves B usable — verify: after `document_close { doc: <handle A> }`, `query_tree_summary { doc: <handle B> }` still returns `status: "OK"`

**Cleanup**:
```
mcp document_close { doc: <handle B> }
```

---

### TC-02-05: query_tree_summary depth, root, and every filter

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.2 (tree summary filters)

**Preconditions**:
- [ ] A document with a nested PartDesign Body is open. Build one, or reuse the TC-04 body (verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` shows a `PartDesign::Body` node with `children`)

**Steps**:
1. Read at the default depth, then deeper.
   ```
   mcp query_tree_summary { doc: <handle>, depth: 1 }
   mcp query_tree_summary { doc: <handle>, depth: 3 }
   ```
2. Re-root the walk at a named object.
   ```
   mcp query_tree_summary { doc: <handle>, depth: 2, root: "Body" }
   ```
3. Exercise each filter in turn.
   ```
   mcp query_tree_summary { doc: <handle>, depth: 3, filters: { types: ["PartDesign::Pad"] } }
   mcp query_tree_summary { doc: <handle>, depth: 3, filters: { exclude_types: ["Sketcher::SketchObject"] } }
   mcp query_tree_summary { doc: <handle>, depth: 3, filters: { renderable_only: true } }
   mcp query_tree_summary { doc: <handle>, depth: 3, filters: { visible_only: true } }
   mcp query_tree_summary { doc: <handle>, depth: 3, filters: { name_pattern: "^Pad" } }
   ```

**Checkpoints**:
- [ ] CP1: Depth 1 does not expand children — verify: at `depth: 1` the root node carries `children_count` but no `children` array, and `returned_nodes` equals the number of roots
- [ ] CP2: Depth 3 expands and counts more — verify: `returned_nodes` at `depth: 3` is strictly greater than at `depth: 1`, and the root node now carries a `children` array
- [ ] CP3: `root` re-roots the walk — verify: with `root: "Body"` the single entry in `tree` has `name` `Body`, and `returned_nodes` counts only that subtree
- [ ] CP4: An unknown root is refused — verify: `mcp query_tree_summary { doc: <handle>, root: "NoSuchObject" }` returns `INVALID_INPUT` with message `unknown object: NoSuchObject`
- [ ] CP5: `types` is an allow-list — verify: every node in the `types: ["PartDesign::Pad"]` result has `type` `PartDesign::Pad`
- [ ] CP6: `exclude_types` replaces the datum default, it does not add to it — verify: `filters_applied.exclude_types` in the `exclude_types: ["Sketcher::SketchObject"]` result is exactly `["Sketcher::SketchObject"]`, and the `App::Origin`/`App::Plane`/`App::Line`/`App::Point` nodes that the default suppressed now appear
- [ ] CP7: The default excludes the datum clutter set — verify: with no `filters` at all, `filters_applied.exclude_types` is `["App::Plane", "App::Line", "App::Point", "App::Origin"]`
- [ ] CP8: `renderable_only` drops containers and datums — verify: no `PartDesign::Body`, `Sketcher::SketchObject`, or `App::Origin*` node appears in the `renderable_only: true` result
- [ ] CP9: `visible_only` honours the Visibility flag — verify: hide one object in the GUI, re-run, and that object's node is absent while it is present without the filter
- [ ] CP10: `name_pattern` is a regular expression over name and label — verify: the `^Pad` result contains only nodes whose `name` or `label` starts with `Pad`
- [ ] CP11: Filters AND-stack — verify: `filters: { renderable_only: true, name_pattern: "^Pad" }` returns a subset of each single-filter result
- [ ] CP12: An unknown filter key is a schema reject — verify: `mcp query_tree_summary { doc: <handle>, filters: { unknown_filter: true } }` is rejected by the MCP layer as a protocol error (`isError`, no envelope), because the filter object is closed with `additionalProperties: false`

**Cleanup**: none. Every call in this scenario is read-only.

---

### TC-02-06: query_object returns properties and error state for a Pad

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.2 (query_object), `data-contracts-design.md` §9 (error field)

**Preconditions**:
- [ ] A document with a recomputed `PartDesign::Pad` is open (verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` names a `PartDesign::Pad` node)

**Steps**:
1. Read the healthy Pad.
   ```
   mcp query_object { doc: <handle>, object: "Pad" }
   ```
2. Break the Pad so FreeCAD marks it invalid — for example set its `Length` to `0` — then
   recompute and read it again.
   ```
   mcp feature_set_parameters { doc: <handle>, feature: "Pad", parameters: { Length: { value: 0, unit: "mm" } }, confirm: { preview_id: <token> } }
   mcp document_recompute { doc: <handle> }
   mcp query_object { doc: <handle>, object: "Pad" }
   ```

**Checkpoints**:
- [ ] CP1: The identity triple is present — verify: `structured_content` carries `name` `Pad`, a `label`, and `type` `PartDesign::Pad`
- [ ] CP2: Properties come from `PropertiesList` — verify: `structured_content.properties` contains the Pad's own properties including `Length`, `Type`, `Profile`, and `Reversed`
- [ ] CP3: A quantity property reports a readable value — verify: `properties.Length` is a number or a stringified quantity, never `null`, for the healthy Pad
- [ ] CP4: A healthy object reports no error — verify: `structured_content.error` is `null`, because `getStatusString()` returned `Valid` or `Touched`, both of which are surfaced as `null`
- [ ] CP5: The broken Pad reports a genuine error string — verify: after step 2 `structured_content.error` is a non-empty string, the verbatim `getStatusString()` text, not a boolean and not a code
- [ ] CP6: The recompute also flags it — verify: `document_recompute` returned status `RECOMPUTE_ERROR` naming `Pad` in `structured_content.errors`
- [ ] CP7: An unreadable property degrades to null, not a crash — verify: the response is valid JSON and the tool returns `status: "OK"` even for the broken object
- [ ] CP8: An unknown object name is refused — verify: `mcp query_object { doc: <handle>, object: "NoSuchPad" }` returns `INVALID_INPUT` with message `unknown object: NoSuchPad`

**Cleanup**: undo the parameter change so later scenarios see a healthy document.
```
mcp document_undo { doc: <handle> }
mcp document_recompute { doc: <handle> }
```

---

### TC-02-07: query_dependencies per-object and whole-document

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2 (query_dependencies)

**Preconditions**:
- [ ] A document with a Body, a Sketch, and a Pad is open (verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` names all three)

**Steps**:
1. Read the per-object view for the Pad.
   ```
   mcp query_dependencies { doc: <handle>, object: "Pad" }
   ```
2. Read the whole-document edge list.
   ```
   mcp query_dependencies { doc: <handle> }
   ```

**Checkpoints**:
- [ ] CP1: The per-object shape is the three-key form — verify: `structured_content` keys are exactly `object`, `in_list`, `out_list`
- [ ] CP2: Names are immutable `Name` values, never labels — verify: every entry in `in_list` and `out_list` matches the `name` field of a node in `query_tree_summary`, not its `label`
- [ ] CP3: The Pad's profile appears downstream — verify: the Pad's `out_list` contains the `Sketcher::SketchObject` name it pads
- [ ] CP4: The Pad's Body appears upstream — verify: the Pad's `in_list` contains the `PartDesign::Body` name
- [ ] CP5: No entry is repeated — verify: `in_list` and `out_list` each contain no duplicate name, because `getOutList` returns an object reachable through two link properties twice and the tool de-duplicates
- [ ] CP6: The whole-document shape is the four-key form — verify: with no `object`, `structured_content` keys are exactly `edges`, `total_edges`, `returned_edges`, `truncated`
- [ ] CP7: Edges are directed pairs — verify: every entry in `edges` is an object with exactly `from` and `to`
- [ ] CP8: Nothing is truncated at the default cap — verify: `total_edges` equals `returned_edges` and `truncated` is `false`, because the default `max_edges` is 2000
- [ ] CP9: The two views agree — verify: for every name `n` in the Pad's `out_list`, `edges` contains `{from: "Pad", to: n}`

**Cleanup**: none. Both calls are read-only.

---

### TC-02-08: query_placement local vs global on a datum-attached feature

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2 (query_placement), `data-contracts-design.md` §9 (Quantity)

**Preconditions**:
- [ ] A document with a `PartDesign::Body` whose `Placement` is non-identity, containing a feature attached to a datum plane, is open (verify: `mcp query_object { doc: <handle>, object: "Body" }` shows a non-zero `Placement`)

**Steps**:
1. Read the container's placement.
   ```
   mcp query_placement { doc: <handle>, object: "Body" }
   ```
2. Read the contained feature's placement.
   ```
   mcp query_placement { doc: <handle>, object: "Pad" }
   ```

**Checkpoints**:
- [ ] CP1: The response shape is fixed — verify: `structured_content` keys are exactly `object`, `local`, `global`
- [ ] CP2: Positions carry explicit units — verify: `local.position.x` is a `{value, unit}` object with `unit` `mm`, and the same for `y` and `z`
- [ ] CP3: The rotation axis is a bare float triple — verify: `local.axis` is `{x, y, z}` with plain numbers and no `unit` key, because an axis is dimensionless
- [ ] CP4: The angle is reported in degrees — verify: `local.angle` is a `{value, unit}` object with `unit` `deg`, never radians
- [ ] CP5: The global placement differs from the local one for a contained feature — verify: for `Pad` inside the moved `Body`, `global.position` differs from `local.position` in at least one axis
- [ ] CP6: Global equals local at the top level — verify: for `Body` itself, `global` equals `local` field for field
- [ ] CP7: The global value composes the container transform — verify: `global.position` for `Pad` equals the `Body` placement applied to the `Pad` local position, within floating-point tolerance
- [ ] CP8: An object with no placement is refused cleanly — verify: querying an object that carries no `Placement` returns `INVALID_INPUT` with message `object has no placement: <name>`, not a crash

**Cleanup**: none. Both calls are read-only.

---

### TC-02-09: document_list adopts a GUI-opened document

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_list adoption), `data-contracts-design.md` §9 (AD-20)

**Preconditions**:
- [ ] No document is open (verify: `mcp document_list {}` returns `0 open document(s).`)
- [ ] `box40-hole-r5.FCStd` exists (verify: `ls benchmarks/g0/golden-models/box40-hole-r5.FCStd`)

**Steps**:
1. Open the file through the FreeCAD GUI, not through MCP.
   ```
   cua invoke_menu { pid: <freecad pid>, window_id: <window id>, path: ["File", "Open..."] }
   cua type_text { pid: <freecad pid>, text: "D:\\Work\\Personal\\Sources\\freecad-buddy\\benchmarks\\g0\\golden-models\\box40-hole-r5.FCStd" }
   cua press_key { pid: <freecad pid>, key: "Enter" }
   ```
2. Confirm the document is loaded in the GUI.
   ```
   cua verify_state { pid: <freecad pid>, window_id: <window id>, expect: { title_contains: "box40-hole-r5" } }
   ```
3. List documents over MCP.
   ```
   mcp document_list {}
   ```

**Checkpoints**:
- [ ] CP1: The GUI opened it — verify: step 2 returns a match, not `unknown`; `unknown` is not success and requires re-snapshotting the window
- [ ] CP2: MCP sees the GUI-opened document — verify: `mcp document_list {}` reports `1 open document(s): box40-hole-r5.`
- [ ] CP3: A handle was minted on first sight — verify: the listed entry carries a `doc` matching `^fcb-doc:`
- [ ] CP4: An adopted document is not marked transient — verify: the entry's `transient` is `false`
- [ ] CP5: The adopted handle is usable — verify: `mcp query_tree_summary { doc: <adopted handle> }` returns `tree[0].name` `BoxHole`
- [ ] CP6: The geometry is the real file, not a stub — verify: `mcp query_mass_properties { doc: <adopted handle>, object: "BoxHole" }` returns `volume` `15214.6018` within 0.1 %
- [ ] CP7: A second `document_list` does not mint a second handle — verify: calling `mcp document_list {}` again returns the same `doc` string and still one entry

**Cleanup**:
```
mcp document_close { doc: <adopted handle> }
```

---

### TC-02-10: Handle survives a GUI selection change

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.1 (never ActiveDocument), `data-contracts-design.md` §9 (AD-20)

**Preconditions**:
- [ ] Two documents are open with handles A (`box-10-20-30`) and B (`two-box-compound`) (verify: `mcp document_list {}` lists both labels)

**Steps**:
1. Read A's tree and record the result.
   ```
   mcp query_tree_summary { doc: <handle A> }
   ```
2. Change the GUI selection and the active MDI window several times, ending on B.
   ```
   cua get_window_state { pid: <freecad pid>, window_id: <window id> }
   cua click { pid: <freecad pid>, window_id: <window id>, element_token: <two-box-compound tree item token> }
   cua invoke_menu { pid: <freecad pid>, window_id: <window id>, path: ["Windows", "two-box-compound"] }
   ```
3. Re-read A's tree with the same handle, without touching the GUI again.
   ```
   mcp query_tree_summary { doc: <handle A> }
   ```

**Checkpoints**:
- [ ] CP1: The GUI selection really moved to B — verify: `cua get_window_state` shows the `two-box-compound` window as active, not `unknown`
- [ ] CP2: The handle string is unchanged — verify: handle A from step 1 is still the exact string used in step 3
- [ ] CP3: The re-read returns A's content — verify: step 3's `tree[0].name` is `Box`, identical to step 1
- [ ] CP4: The re-read is byte-identical apart from nothing — verify: step 1 and step 3 `structured_content` are equal field for field, since no mutation happened between them
- [ ] CP5: B remains separately addressable — verify: `mcp query_tree_summary { doc: <handle B> }` returns `tree[0].name` `TwoBoxCompound`
- [ ] CP6: The compound's centre of mass is null, matching the shipped behaviour — verify: `mcp query_mass_properties { doc: <handle B>, object: "TwoBoxCompound" }` returns `volume` `2000.0` within 0.1 %, `counts.solids` `2`, and `com` `null`

**Cleanup**:
```
mcp document_close { doc: <handle A> }
mcp document_close { doc: <handle B> }
```

---

### TC-02-11: Tree depth boundary and the retired max_nodes parameter

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2 (depth bound), `data-contracts-design.md` §9 (closed schemas)

**Preconditions**:
- [ ] A document with at least two tree levels is open (verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` shows a `children` array)

**Steps**:
1. Probe the depth boundary.
   ```
   mcp query_tree_summary { doc: <handle>, depth: 1 }
   mcp query_tree_summary { doc: <handle>, depth: 0 }
   mcp query_tree_summary { doc: <handle>, depth: -1 }
   ```
2. Pass the retired `max_nodes` parameter.
   ```
   mcp query_tree_summary { doc: <handle>, max_nodes: 0 }
   mcp query_tree_summary { doc: <handle>, depth: 2, max_nodes: 5 }
   ```

**Checkpoints**:
- [ ] CP1: `depth: 1` is the minimum accepted value — verify: it returns `status: "OK"` with `structured_content.depth` `1`
- [ ] CP2: `depth` defaults to 1 when omitted — verify: `mcp query_tree_summary { doc: <handle> }` returns `structured_content.depth` `1`
- [ ] CP3: `depth: 0` is a schema reject — verify: the call is rejected by the MCP layer as a protocol error (`isError`, no envelope), because the schema declares `minimum: 1`
- [ ] CP4: `depth: -1` is a schema reject — verify: same protocol rejection as CP3
- [ ] CP5: **`max_nodes` is retired; passing it is a schema reject** — verify: `mcp query_tree_summary { doc: <handle>, max_nodes: 0 }` is rejected by the MCP layer as a protocol error, **not** an `OK` envelope with empty nodes. The former `docs/tests/TC-09` CP6 expected `OK` with `truncated: true`; that expectation is stale. Assert the rejection.
- [ ] CP6: The rejection is caused by the closed schema — verify: the tool's input schema has `additionalProperties: false` and its `properties` are exactly `doc`, `depth`, `root`, `filters`, with no `max_nodes`
- [ ] CP7: A valid call still works after the rejections — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` returns `status: "OK"`, so a schema reject never poisons the handle

**Cleanup**: none. Every call is read-only or rejected before dispatch.

---

### TC-02-12: query_dependencies max_edges truncation and rejection

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2 (max_edges), `data-contracts-design.md` §9 (truncation is flagged)

**Preconditions**:
- [ ] A document with at least two dependency edges is open (verify: `mcp query_dependencies { doc: <handle> }` returns `total_edges` ≥ 2)

**Steps**:
1. Read the full edge list and record `total_edges`.
   ```
   mcp query_dependencies { doc: <handle> }
   ```
2. Cap the result at one edge.
   ```
   mcp query_dependencies { doc: <handle>, max_edges: 1 }
   ```
3. Pass values below the minimum and a non-integer.
   ```
   mcp query_dependencies { doc: <handle>, max_edges: 0 }
   mcp query_dependencies { doc: <handle>, max_edges: -5 }
   mcp query_dependencies { doc: <handle>, max_edges: 1.5 }
   ```

**Checkpoints**:
- [ ] CP1: The default cap truncates nothing here — verify: step 1 returns `truncated` `false` and `returned_edges` equal to `total_edges`
- [ ] CP2: `max_edges: 1` keeps exactly one edge — verify: `edges` has length `1` and `returned_edges` is `1`
- [ ] CP3: Truncation is flagged, not silent — verify: `truncated` is `true` in the capped result
- [ ] CP4: The full count is still reported when truncated — verify: `total_edges` in the capped result equals `total_edges` from step 1, so a caller can tell how much was withheld
- [ ] CP5: The kept edge is the first in document order — verify: the single entry equals `edges[0]` from step 1
- [ ] CP6: `max_edges: 0` is refused — verify: the call returns `INVALID_INPUT` with message `max_edges must be >= 1: 0`, or is rejected by the MCP layer as a protocol error because the schema declares `minimum: 1`. Record which layer refused it.
- [ ] CP7: `max_edges: -5` is refused the same way — verify: the same refusal shape as CP6, with the value `-5` where the message names it
- [ ] CP8: A non-integer is refused — verify: `max_edges: 1.5` is refused, either as `INVALID_INPUT` with message `max_edges must be an integer: 1.5` or as a schema protocol rejection

**Cleanup**: none. Every call is read-only or refused.

---

### TC-02-13: Unicode, spaces, and a long label round-trip

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §1.1 (label handling), `data-contracts-design.md` §9 (UTF-8 on the wire)

**Preconditions**:
- [ ] No document is open (verify: `mcp document_list {}` returns `0 open document(s).`)
- [ ] `_automation/uat-unicode.FCStd` does not exist (verify: `ls _automation/uat-unicode.FCStd` reports no such file)

**Steps**:
1. Create a document whose label mixes CJK, an emoji, spaces, and length.
   ```
   mcp document_create { label: "測試 ドキュメント 🔧 with spaces and a deliberately long label for width" }
   ```
2. List, save to a plain ASCII path, and close.
   ```
   mcp document_list {}
   mcp document_save { doc: <handle>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/uat-unicode.FCStd" }
   mcp document_close { doc: <handle> }
   ```
3. Reopen the saved file and read the label back.
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/_automation/uat-unicode.FCStd" }
   mcp document_list {}
   ```

**Checkpoints**:
- [ ] CP1: The create succeeds — verify: the call returns `status: "OK"` with a handle
- [ ] CP2: The label survives the create — verify: `structured_content.label` equals the input string exactly, including the emoji and both CJK runs
- [ ] CP3: The internal `Name` is sanitized while the `Label` is not — verify: `structured_content.name` is a FreeCAD-legal identifier and `label` still carries the full Unicode text; the two must not be assumed equal
- [ ] CP4: The listing carries the label unmangled — verify: `document_list` shows the same label, not a `?` or `\u` escape sequence in the rendered `text`
- [ ] CP5: The label survives save and reopen — verify: after step 3, `document_list` reports the same label string as CP2
- [ ] CP6: No mojibake on the wire — verify: the reopened label compares equal byte for byte to the input string in Python, not merely equal when printed to a cp1252 console
- [ ] CP7: The file reads back cleanly — verify: `mcp query_tree_summary { doc: <reopened handle> }` returns `status: "OK"` with `total_objects` `0`

**Cleanup**:
```
mcp document_close { doc: <reopened handle> }
```
```bash
rm -f _automation/uat-unicode.FCStd
```

---

### TC-02-14: Deeply nested App::Part and App::Link tree

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §3.2 (children vs links partition)

**Preconditions**:
- [ ] A document with nested `App::Part` containers and at least one `App::Link` is open. Build one with the GUI (Std Part, then Make Link) or over MCP, then verify: `mcp query_tree_summary { doc: <handle>, depth: 5 }` names both an `App::Part` and an `App::Link` node

**Steps**:
1. Walk the tree at increasing depth.
   ```
   mcp query_tree_summary { doc: <handle>, depth: 1 }
   mcp query_tree_summary { doc: <handle>, depth: 5 }
   ```
2. Re-root at the inner container.
   ```
   mcp query_tree_summary { doc: <handle>, depth: 3, root: "<inner App::Part name>" }
   ```

**Checkpoints**:
- [ ] CP1: Structural children and links are separate arrays — verify: a node with both carries `children` and `links` as two distinct keys, never one merged array
- [ ] CP2: Only `App::Link*` types land in `links` — verify: every node in any `links` array has a `type` starting with `App::Link`
- [ ] CP3: Counts appear at the depth boundary — verify: at `depth: 1` the root reports `children_count` and, if it has links, `links_count`, with no expanded arrays
- [ ] CP4: Counts are omitted when zero — verify: a leaf node carries neither `children_count` nor `links_count`, because sparse nodes omit zero-valued fields
- [ ] CP5: Nesting is preserved to the requested depth — verify: at `depth: 5` the outer `App::Part` node's `children` contains the inner `App::Part` node, which in turn carries its own `children`
- [ ] CP6: Re-rooting yields the subtree only — verify: the `root: "<inner App::Part name>"` result has exactly one entry in `tree`, and `returned_nodes` is smaller than the whole-document walk at the same depth
- [ ] CP7: A link does not create a cycle in the walk — verify: the call returns within its 30 s budget and `returned_nodes` is finite and stable across two identical calls
- [ ] CP8: A link target is still reachable as a root — verify: `root: "<link target name>"` returns `status: "OK"` naming that object

**Cleanup**:
```
mcp document_close { doc: <handle> }
```

---

### TC-02-15: Unknown or stale handle is refused by every document-taking tool

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (handle resolution), `data-contracts-design.md` §9 (closed status set)

**Preconditions**:
- [ ] One document is open, so the registry is non-empty and the refusal is not a trivially empty lookup (verify: `mcp document_list {}` reports one entry)
- [ ] A fabricated handle string is prepared, for example `fcb-doc:not-a-real-handle`

**Steps**:
1. Call each read-only document-taking tool with the fabricated handle.
   ```
   mcp query_tree_summary { doc: "fcb-doc:not-a-real-handle" }
   mcp query_object { doc: "fcb-doc:not-a-real-handle", object: "Box" }
   mcp query_mass_properties { doc: "fcb-doc:not-a-real-handle", object: "Box" }
   mcp query_dependencies { doc: "fcb-doc:not-a-real-handle" }
   mcp query_placement { doc: "fcb-doc:not-a-real-handle", object: "Box" }
   mcp query_sketch_info { doc: "fcb-doc:not-a-real-handle", sketch: "Sketch" }
   ```
2. Call the lifecycle and verification tools with the same handle.
   ```
   mcp document_save { doc: "fcb-doc:not-a-real-handle" }
   mcp document_close { doc: "fcb-doc:not-a-real-handle" }
   mcp document_recompute { doc: "fcb-doc:not-a-real-handle" }
   mcp document_undo { doc: "fcb-doc:not-a-real-handle" }
   mcp verify_shape { doc: "fcb-doc:not-a-real-handle" }
   mcp query_screenshot { doc: "fcb-doc:not-a-real-handle" }
   ```
3. Under the **inline host** only, call one tool with a non-string `doc`.
   ```bash
   "$USERPROFILE/micromamba/envs/fcb/python.exe" -m freecad_buddy.hosts.main serve --transport stdio --mode inline
   # then over stdio: query_tree_summary { doc: 12345 }
   ```

**Checkpoints**:
- [ ] CP1: Every read-only tool refuses — verify: each call in step 1 returns `status: "INVALID_INPUT"` with message `unknown or stale document handle: fcb-doc:not-a-real-handle`
- [ ] CP2: Every lifecycle tool refuses — verify: each call in step 2 returns the same `INVALID_INPUT` message
- [ ] CP3: The refusal is an envelope, not a protocol error — verify: each response carries `schema` `fcb.result-envelope/1` and `detail.code` `INVALID_INPUT`, because a well-typed but unknown handle passes the JSON Schema and fails at resolution
- [ ] CP4: Nothing crashes — verify: after all twelve calls, `mcp query_capabilities {}` still returns `status: "OK"` and `grep -iE "access violation|segfault|swig" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns nothing
- [ ] CP5: The live handle is unaffected — verify: the still-open document's handle returns `status: "OK"` from `query_tree_summary` after all the refusals
- [ ] CP6: An omitted `doc` is a schema reject, not a resolution failure — verify: `mcp query_tree_summary {}` is rejected by the MCP layer as a protocol error, because `doc` is in the tool's `required` list
- [ ] CP7 (**inline host only**): A non-string `doc` is rejected before dispatch — verify: step 3 returns `INVALID_INPUT` with message `doc handle must be a string`. This guard lives in `adapters/mcp_server.py` and the H2 proxy path does **not** have it, so running this checkpoint against `:8765` proves nothing. Record the host.

**Cleanup**: none. No call mutated anything.

---

### TC-02-16: Double document_close is refused, not crashed

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (handle release), `data-contracts-design.md` §9 (closed status set)

**Preconditions**:
- [ ] No document is open (verify: `mcp document_list {}` returns `0 open document(s).`)

**Steps**:
1. Open a golden model and record the handle.
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/sphere-r10.FCStd" }
   ```
2. Close it, then close it again with the same handle.
   ```
   mcp document_close { doc: <handle> }
   mcp document_close { doc: <handle> }
   ```
3. Query through the released handle.
   ```
   mcp query_tree_summary { doc: <handle> }
   ```

**Checkpoints**:
- [ ] CP1: The first close succeeds — verify: `status: "OK"` with `closed: true` and `name` `sphere-r10`
- [ ] CP2: The second close is refused — verify: `status: "INVALID_INPUT"` with message `unknown or stale document handle: <handle>`
- [ ] CP3: The refusal names the handle that failed — verify: the message contains the exact handle string passed in, so a caller can identify which of several handles is stale
- [ ] CP4: A query through the released handle is refused the same way — verify: step 3 returns the same `INVALID_INPUT` message
- [ ] CP5: No document was closed twice in FreeCAD — verify: `mcp document_list {}` returns `0 open document(s).` and the FreeCAD window shows no orphan MDI child
- [ ] CP6: Nothing crashed — verify: `mcp query_capabilities {}` still returns `status: "OK"` and the addon log records no traceback for the second close
- [ ] CP7: The file is intact — verify: `ls -l benchmarks/g0/golden-models/sphere-r10.FCStd` shows the same size as before, and reopening it returns a fresh handle with `volume` `4188.7902` within 0.1 %

**Cleanup**:
```
mcp document_close { doc: <reopened handle from CP7> }
```

---

### TC-02-17: Bad open paths are each distinguishable

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_open), `data-contracts-design.md` §9 (INVALID_INPUT detail)

**Preconditions**:
- [ ] Three bad inputs are prepared (verify with the commands in step 1)

**Steps**:
1. Prepare a non-FCStd file and a corrupt zip.
   ```bash
   printf 'this is not a FreeCAD document\n' > _automation/uat-not-fcstd.txt
   printf 'PK\x03\x04garbage-not-a-real-zip' > _automation/uat-corrupt.FCStd
   ```
2. Try to open each bad path.
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/_automation/does-not-exist.FCStd" }
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/_automation/uat-not-fcstd.txt" }
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/_automation/uat-corrupt.FCStd" }
   mcp document_open { path: "" }
   mcp document_open { path: "_automation" }
   ```

**Checkpoints**:
- [ ] CP1: A nonexistent path is refused — verify: `status: "INVALID_INPUT"` with a message starting `document_open failed for '_automation/does-not-exist.FCStd':`
- [ ] CP2: A non-FCStd file is refused — verify: `status: "INVALID_INPUT"` with a message starting `document_open failed for '_automation/uat-not-fcstd.txt':`
- [ ] CP3: A corrupt zip is refused — verify: `status: "INVALID_INPUT"` with a message starting `document_open failed for '_automation/uat-corrupt.FCStd':`
- [ ] CP4: The three refusals are distinguishable — verify: the FreeCAD exception text appended after the colon differs between CP1, CP2, and CP3, so a caller can tell a missing file from an unreadable one from a corrupt archive
- [ ] CP5: An empty path is refused before FreeCAD is called — verify: `status: "INVALID_INPUT"` with message `document_open requires a 'path'`
- [ ] CP6: A directory path is refused — verify: `status: "INVALID_INPUT"` with a message starting `document_open failed for '_automation':`
- [ ] CP7: No handle leaks from a failed open — verify: `mcp document_list {}` after all five attempts shows no new entry
- [ ] CP8: Nothing crashed — verify: `mcp query_capabilities {}` still returns `status: "OK"` and the addon log records no unhandled traceback

**Cleanup**:
```bash
rm -f _automation/uat-not-fcstd.txt _automation/uat-corrupt.FCStd
```

---

### TC-02-18: Save to an unwritable path leaves the original intact

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_save), `data-contracts-design.md` §9 (closed status set)

**Preconditions**:
- [ ] A read-only target file exists (verify: `cp benchmarks/g0/golden-models/box-10-20-30.FCStd _automation/uat-readonly.FCStd && chmod 444 _automation/uat-readonly.FCStd && ls -l _automation/uat-readonly.FCStd`)
- [ ] Record the original file's size and a hash (verify: `sha256sum _automation/uat-readonly.FCStd`)

**Steps**:
1. Open a golden model in a separate handle.
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/cylinder-r5-h20.FCStd" }
   ```
2. Try to save it over the read-only file, and into a directory that does not exist.
   ```
   mcp document_save { doc: <handle>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/uat-readonly.FCStd" }
   mcp document_save { doc: <handle>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/no-such-dir/out.FCStd" }
   ```
3. Try to save onto a path that names an existing directory.
   ```
   mcp document_save { doc: <handle>, path: "_automation" }
   ```

**Checkpoints**:
- [ ] CP1: The read-only save is refused with a closed-set status — verify: the response `status` is one of the closed set (`INVALID_INPUT` or `WORKER_CRASHED`), never an ad-hoc code, and never `OK`
- [ ] CP2: The read-only file is byte-identical afterwards — verify: `sha256sum _automation/uat-readonly.FCStd` matches the hash recorded in the preconditions
- [ ] CP3: The missing-directory save is refused — verify: the response `status` is a closed-set non-`OK` value and no directory was created (`ls _automation/no-such-dir` reports no such file)
- [ ] CP4: The directory-as-path save is refused — verify: the response `status` is a closed-set non-`OK` value and `_automation` is still a directory
- [ ] CP5: The source golden file is untouched — verify: `sha256sum benchmarks/g0/golden-models/cylinder-r5-h20.FCStd` matches its value before the run
- [ ] CP6: The handle is still usable after all three failures — verify: `mcp query_tree_summary { doc: <handle> }` returns `status: "OK"` with `tree[0].name` `Cylinder`
- [ ] CP7: A later save to a writable path succeeds — verify: `mcp document_save { doc: <handle>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/uat-writable.FCStd" }` returns `status: "OK"` with `saved: true`, proving no failed save poisoned the document
- [ ] CP8: Nothing crashed — verify: `mcp query_capabilities {}` still returns `status: "OK"` and the addon log records no unhandled traceback

**Cleanup**:
```
mcp document_close { doc: <handle> }
```
```bash
chmod 644 _automation/uat-readonly.FCStd
rm -f _automation/uat-readonly.FCStd _automation/uat-writable.FCStd
```
