# TC-02: Document Ingestion & Handles

Validates AD-20: every document operation targets an explicit opaque `fcb-doc:<token>` handle and
the bridge never reads `ActiveDocument`. Covers the full lifecycle (create, open, save, save-as,
close, list) and the read-only query surface that reads through a handle (`query_tree_summary`,
`query_object`, `query_dependencies`, `query_placement`). Also covers handle staleness, GUI-opened
document adoption, and the `FCB_TMP_` prefix rule for bridge-owned temporary artifacts. Executed by
the agent against the live GUI bridge.

We are building this bridge, so its own output can never be the test result. Every envelope field,
status, handle string, and `query_screenshot` render in this file is a **claim under test**. The
result is the `cua-driver` pixel capture of the real FreeCAD window, `Read` and judged by the agent.
"The document is open" is proven by seeing the model and its tree entry in the window, never by
`document_open` returning `OK`.

**Host**: GUI through the H2 proxy (`gui_external/entry.py`) for every scenario. The proxy
forwards each call to the in-FreeCAD RPC listener, which applies the non-string-`doc` guard and the
suspect-document logic (`adapters/rpc_listener.py:417-424`) and writes the audit pairs. The MCP
input schema declares `doc` as `{type: string}` on every host, so a non-string `doc` sent over MCP
is refused by the schema before either guard runs.

## Preconditions

- [ ] FreeCAD GUI is running and the bridge answers (verify: `mcp query_capabilities {}` returns `status: "OK"`)
- [ ] Golden and fault `.FCStd` files have no `GuiDocument.xml` and open with every object hidden. After each `document_open` of such a file, and before any fit or render of it, run **Show All**: `cua-driver call invoke_menu { pid, window_id, path: ["View","Visibility","Show All Objects"] }`. A fit before it returns `SPEC_FAILED view_fit.nothing_to_frame`.
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/*.FCStd` lists 5 files)
- [ ] A writable scratch directory exists (verify: `mkdir -p _automation && ls -d _automation`)
- [ ] No document is open at the start (verify: `mcp document_list {}` returns `0 open document(s).`)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` returns a `QOpenGLWidget`)
- [ ] The GUI's own **Fit All** toolbar button is reachable, as the non-MCP framing path (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` lists a `Fit All` toolbar element with an `element_token`; clicking it returns `route: "accessibility"` and reframes the view. Note `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable` at segment 1. `["View","Visibility","Show All Objects"]` resolves.)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)

---

### TC-02-01: Create, list, save, close round trip

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document lifecycle), `data-contracts-design.md` §9 (handle contract)

**Given** no document is open — verify: `mcp document_list {}` returns `0 open document(s).`  

**When** a document is created with an explicit label  
```
mcp document_create { label: "uat-roundtrip" }
```
**And** the open documents are listed  
```
mcp document_list {}
```
**And** it is saved to an explicit path. A document created without a `path` is transient and has no save target, so a bare save must be refused first.  
```
mcp document_save { doc: <handle> }
mcp document_save { doc: <handle>, path: "$RUN_DIR/evidence/tc-02-01-uat-roundtrip.FCStd" }
```
**And** it is closed and the documents are listed again  
```
mcp document_close { doc: <handle> }
mcp document_list {}
```

**Then** the handle is opaque and session-minted — verify: `structured_content.doc` matches `^fcb-doc:` and is not the FreeCAD `Name`  
**And** the create response names the document — verify: `structured_content` carries `doc`, `name`, and `label`, with `label` equal to `uat-roundtrip`  
**And** the list reports the document as transient before any save — verify: `mcp document_list {}` shows one entry whose `doc` equals the handle and whose `transient` is `true`  
**And** a bare save on a transient document is refused — verify: the first `document_save` returns `INVALID_INPUT` with message `document has no save target; call document_save with a 'path' first`  
**And** save-as writes the file — verify: `ls -l "$RUN_DIR/evidence/tc-02-01-uat-roundtrip.FCStd"` lists a non-empty file and the response `structured_content.saved` is `true`  
**And** save-as sets the label to the file stem, as GUI Save As does — verify: the save response `structured_content.label` is `tc-02-01-uat-roundtrip`  
**And** the document is no longer transient after the save-as — verify: `mcp document_list {}` now shows `transient: false` for that handle  
**And** close releases the handle — verify: `document_close` returns `status: "OK"` with `closed: true`, and the following `mcp document_list {}` returns `0 open document(s).`  
**And** the saved file survives the close — verify: `ls -l "$RUN_DIR/evidence/tc-02-01-uat-roundtrip.FCStd"` still lists the file  
**And** *(visual)* the reopened document is framed — verify: reopen with `mcp document_open { path: "$RUN_DIR/evidence/tc-02-01-uat-roundtrip.FCStd" }`, then `mcp view_fit_viewport { doc: "<reopened handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the window and say what is on screen: exactly one 3D view, its title bar reading `tc-02-01-uat-roundtrip` (the label is the file stem after a save-as), an empty viewport with no model in it, one matching entry in the model tree, no second `uat-roundtrip` view left behind by the close, and no dialog — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-01-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and judge it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <reopened handle> }
```
```bash
rm -f "$RUN_DIR/evidence/tc-02-01-uat-roundtrip.FCStd"
```

---

### TC-02-02: Open a golden model and read its tree

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_open), §3.2 (query_tree_summary)

**Given** `box-10-20-30.FCStd` exists — verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`  
**And** no document is open — verify: `mcp document_list {}` returns `0 open document(s).`  

**When** the golden model is opened  
```
mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }
```
**And** the tree is read through the returned handle  
```
mcp query_tree_summary { doc: <handle> }
```
**And** the one object it contains is read  
```
mcp query_object { doc: <handle>, object: "Box" }
```

**Then** open returns a handle and the source path — verify: `structured_content` carries `doc`, `name`, `label`, and `path` equal to the path passed in  
**And** the summary text is the shipped form — verify: the envelope `text` is `Opened box-10-20-30 -> fcb-doc:<token>.`  
**And** the tree reports one object — verify: `structured_content.total_objects` is `1` and `shown` is `1`  
**And** the line is the golden `Box` — verify: the tree lines is the one line `<v|-> [FEATURE] Box`; `FEATURE` is the code of `Part::Feature`  
**And** the object is clean, so no error marker appears — verify: the `Box` line has no `!` suffix and the envelope `text` has no `Errors:` part, because `getStatusString()` returned `Valid`  
**And** `query_object` reads the same object through the same handle — verify: `structured_content.name` is `Box`, `type` is `Part::Feature`, and `error` is `null`  
**And** the properties dict is JSON-safe — verify: `structured_content.properties` is an object whose values are all JSON scalars, arrays, objects, or strings, with no Python `repr` of a live FreeCAD pointer beyond a stringified value  
**And** the volume is analytic — verify: `mcp query_mass_properties { doc: <handle>, object: "Box" }` returns `volume` `6000.0` within 0.1 %  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the window and say what is on screen: one box-shaped solid, present and whole, with no edge clipped by the viewport border, one `Box` entry in the model tree, and no dialog — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-02-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and judge it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. An empty viewport here is a failure however clean the envelope was.  

**Cleanup**:
```
mcp document_close { doc: <handle> }
```

---

### TC-02-03: Save-as writes a new path and rebinds the handle

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_save), `data-contracts-design.md` §9 (handle stability)

**Given** `cylinder-r5-h20.FCStd` exists — verify: `ls benchmarks/g0/golden-models/cylinder-r5-h20.FCStd`  
**And** `$RUN_DIR/evidence/tc-02-03-uat-saveas.FCStd` does not exist — verify: `ls "$RUN_DIR/evidence/tc-02-03-uat-saveas.FCStd"` reports no such file  

**When** the golden model is opened and its handle recorded  
```
mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/cylinder-r5-h20.FCStd" }
```
**And** it is saved to a new path  
```
mcp document_save { doc: <handle>, path: "$RUN_DIR/evidence/tc-02-03-uat-saveas.FCStd" }
```
**And** the same handle is queried afterwards  
```
mcp query_tree_summary { doc: <handle> }
```

**Then** the new file is written — verify: `ls -l "$RUN_DIR/evidence/tc-02-03-uat-saveas.FCStd"` lists a non-empty file  
**And** the original golden file is untouched — verify: the mtime and size of `benchmarks/g0/golden-models/cylinder-r5-h20.FCStd` are unchanged from before the save  
**And** the handle string is unchanged by the save-as — verify: the `structured_content.doc` in the save response equals the handle from the open, character for character  
**And** the handle still resolves after the rebind — verify: the `query_tree_summary` first line starts `OK: 1 objects`  
**And** the object survives the save-as — verify: the first tree line names `Cylinder`  
**And** the new file reopens independently — verify: closing the handle and running `mcp document_open { path: "$RUN_DIR/evidence/tc-02-03-uat-saveas.FCStd" }` yields a fresh handle whose `query_mass_properties` on `Cylinder` returns `volume` `1570.7963` within 0.1 %  
**And** *(visual)* the reopened file is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<reopened handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the window and say what is on screen: one cylinder, present and whole, no edge clipped, a `Cylinder` entry in the model tree, and a title bar reading `tc-02-03-uat-saveas` rather than `cylinder-r5-h20` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-03-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and judge it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <handle> }
```
```bash
rm -f "$RUN_DIR/evidence/tc-02-03-uat-saveas.FCStd"
```

---

### TC-02-04: Two open documents stay isolated

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (explicit handle, never ActiveDocument), `data-contracts-design.md` §9 (AD-20)

**Given** `box-10-20-30.FCStd` and `sphere-r10.FCStd` both exist — verify: `ls benchmarks/g0/golden-models/{box-10-20-30,sphere-r10}.FCStd`  
**And** no document is open — verify: `mcp document_list {}` returns `0 open document(s).`  

**When** both golden models are opened, recording handle A (box) and handle B (sphere)  
```
mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }
mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/sphere-r10.FCStd" }
```
**And** the **sphere** document is selected in the FreeCAD tree, so FreeCAD's `ActiveDocument` is B while the queries below target A  
```bash
'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state
'{"pid":<pid>,"window_id":<wid>,"element_token":"<sphere-r10 tree item token>"}' | & cua-driver call click
```
**And** A and B are queried separately, without changing the GUI selection between calls  
```
mcp query_tree_summary { doc: <handle A> }
mcp query_tree_summary { doc: <handle B> }
mcp query_object { doc: <handle A>, object: "Box" }
mcp query_object { doc: <handle B>, object: "Sphere" }
```

**Then** two distinct handles were minted — verify: handle A and handle B are different strings, both matching `^fcb-doc:`  
**And** `document_list` shows both — verify: `mcp document_list {}` reports `2 open document(s): box-10-20-30, sphere-r10.`  
**And** a query on A returns A's object while B is the GUI's active document — verify: `query_tree_summary { doc: <handle A> }` returns the tree lines whose first line names `Box`, never `Sphere`  
**And** a query on B returns B's object — verify: `query_tree_summary { doc: <handle B> }` returns the tree lines whose first line names `Sphere`  
**And** an object name that exists only in B is unknown in A — verify: `mcp query_object { doc: <handle A>, object: "Sphere" }` returns `INVALID_INPUT` with message `unknown object: Sphere`  
**And** the reverse holds — verify: `mcp query_object { doc: <handle B>, object: "Box" }` returns `INVALID_INPUT` with message `unknown object: Box`  
**And** mass properties do not cross documents — verify: `query_mass_properties` on A's `Box` returns `6000.0` and on B's `Sphere` returns `4188.7902`, each within 0.1 %  
**And** closing A leaves B usable — verify: after `document_close { doc: <handle A> }`, `query_tree_summary { doc: <handle B> }` still returns a first line starting `OK:`  
**And** *(visual)* B is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle B>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the window and say what is on screen: a sphere, present and whole, not a box; one 3D view remaining after A was closed, with no orphan box view; one `sphere-r10` entry in the model tree and no `box-10-20-30` entry — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-04-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and judge it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; a round shape on screen is what separates B from A here, not the handle strings.  

**Cleanup**:
```
mcp document_close { doc: <handle B> }
```

---

### TC-02-05: query_tree_summary depth, focus, expand, and the reveal filters

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.2 (tree text, views, reveal filters)

**Given** a document with a PartDesign Body named `Body` holding a sketch and a Pad named `Pad` is open. Build one, or reuse the TC-04 body — verify: `mcp query_tree_summary { doc: <handle>, focus: "Body" }` shows a `[BODY] Body` line with child lines under it  
**And** the starting window state is captured, before any object is hidden — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-05-before.png"}' | & cua-driver call get_window_state`  

**When** the tree is read at the default depth, then deeper  
```
mcp query_tree_summary { doc: <handle>, depth: 1 }
mcp query_tree_summary { doc: <handle>, depth: 3 }
```
**And** the view is focused on the Body, and the Pad is expanded from the top level  
```
mcp query_tree_summary { doc: <handle>, focus: "Body", depth: 2 }
mcp query_tree_summary { doc: <handle>, expand: ["Pad"] }
```
**And** each reveal filter is exercised in turn  
```
mcp query_tree_summary { doc: <handle>, filters: { types: ["PAD"] } }
mcp query_tree_summary { doc: <handle>, filters: { types: ["PartDesign::Pad"] } }
mcp query_tree_summary { doc: <handle>, filters: { name_pattern: "^Pad" } }
mcp query_tree_summary { doc: <handle>, filters: { types: ["PAD"], name_pattern: "zzz" } }
```

**Then** depth 1 lists the top level collapsed — verify: at `depth: 1` the tree text has one line per top-level object, the `Body` line ends `(+N)`, no line starts with a connector (`|-- ` or `` `-- ``), and `structured_content.shown` equals the number of lines  
**And** depth 3 opens more — verify: `shown` at `depth: 3` is strictly greater than at `depth: 1`, and child lines with `|-- `/`` `-- `` connectors appear under the `Body` line  
**And** `focus` scopes the view — verify: with `focus: "Body"` the first line is `path: Body`, the second line is the `[BODY] Body` line, and no line names an object outside the Body  
**And** an unknown focus is refused — verify: `mcp query_tree_summary { doc: <handle>, focus: "NoSuchObject" }` returns `INVALID_INPUT` with message `unknown object: NoSuchObject`  
**And** `expand` opens only the path — verify: with `expand: ["Pad"]` the `Body` line ends `(+N more)`, the one child line under it is the `[PAD] Pad` line, and the Pad's `[SKETCH]` line is shown under the Pad  
**And** `types` reveals by code or by TypeId — verify: the `types: ["PAD"]` and `types: ["PartDesign::Pad"]` results are the same text, each Pad line sits under its opened ancestors, `structured_content.matches` equals the number of Pads, and every other top-level line stays collapsed  
**And** `name_pattern` is a regular expression over name and label — verify: every revealed line in the `^Pad` result names an object whose `Name` or `Label` starts with `Pad`  
**And** filters AND-stack — verify: `types: ["PAD"], name_pattern: "zzz"` returns `matches` `0` and the same tree text as `depth: 1`  
**And** the `v`/`-` marker follows the Visibility flag — verify: hide the Pad through `cua-driver` (`'{"pid":<pid>,"window_id":<wid>,"element_token":"<Pad tree item token>"}' | & cua-driver call click`, then `'{"pid":<pid>,"key":"Space"}' | & cua-driver call press_key`), re-run `{ focus: "Body" }`, and the `Pad` line starts `- ` where it started `v ` before  
**And** a retired filter is a schema reject — verify: `mcp query_tree_summary { doc: <handle>, filters: { visible_only: true } }` is rejected by the MCP layer as a protocol error (`isError`, no envelope)  
**And** an unknown filter key is a schema reject — verify: `mcp query_tree_summary { doc: <handle>, filters: { unknown_filter: true } }` is rejected by the MCP layer as a protocol error (`isError`, no envelope), because the filter object is closed with `additionalProperties: false`  
**And** *(visual)* the hidden object is restored through `cua-driver` (re-select the tree item and press `Space`) and the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the window and say what is on screen: a padded solid, present and whole with no edge clipped, and the Pad that was hidden for the visibility probe now shown again, so the two images look the same — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-05-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and judge them. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; the read-only claim is proven by the two pictures matching, not by the envelopes.  

**Cleanup**: none. Every call in this scenario is read-only.

---

### TC-02-06: query_object returns properties and error state for a Pad

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.2 (query_object), `data-contracts-design.md` §9 (error field)

**Given** a document with a recomputed `PartDesign::Pad` is open — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` shows a `[PAD]` line  
**And** the healthy state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-06-before.png"}' | & cua-driver call get_window_state`  

**When** the healthy Pad is read, and its `Length` recorded  
```
mcp query_object { doc: <handle>, object: "Pad" }
```
**And** the typed tool is asked to break the Pad. The mutation bracket verifies the result and rolls it back, so the Pad stays healthy  
```
mcp feature_set_parameters { doc: <handle>, feature: "Pad", parameters: { Length: { value: 0, unit: "mm" } } }
mcp query_object { doc: <handle>, object: "Pad" }
```
**And** the Pad is broken outside the bracket with `script_exec`, so FreeCAD marks it invalid, then recomputed and read again. `script_exec` opens no transaction, so `document_undo` cannot revert it (see Cleanup)  
```
mcp script_exec { doc: <handle>, code: "doc.getObject('Pad').Length = 0" }
mcp document_recompute { doc: <handle> }
mcp query_object { doc: <handle>, object: "Pad" }
```

**Then** the identity triple is present — verify: `structured_content` carries `name` `Pad`, a `label`, and `type` `PartDesign::Pad`  
**And** properties come from `PropertiesList` — verify: `structured_content.properties` contains the Pad's own properties including `Length`, `Type`, `Profile`, and `Reversed`  
**And** a quantity property reports a readable value — verify: `properties.Length` is a number or a stringified quantity, never `null`, for the healthy Pad  
**And** a healthy object reports no error — verify: `structured_content.error` is `null`, because `getStatusString()` returned `Valid` or `Touched`, both of which are surfaced as `null`  
**And** the typed break is refused and rolled back — verify: `feature_set_parameters` returns a non-`OK` status, and the `query_object` after it still reports `error` `null` and the recorded `Length`  
**And** the broken Pad reports a genuine error string — verify: after the `script_exec` break `structured_content.error` is a non-empty string, the verbatim `getStatusString()` text, not a boolean and not a code  
**And** the recompute also flags it — verify: `document_recompute` returned status `RECOMPUTE_ERROR` naming `Pad` in `structured_content.errors`  
**And** an unreadable property degrades to null, not a crash — verify: the response is valid JSON and the tool returns `status: "OK"` even for the broken object  
**And** an unknown object name is refused — verify: `mcp query_object { doc: <handle>, object: "NoSuchPad" }` returns `INVALID_INPUT` with message `unknown object: NoSuchPad`  
**And** *(visual)* after the restore in Cleanup, the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the window and say what is on screen: a padded solid restored to the same extent it had in the before image, not a collapsed zero-length one; no error marker or exclamation icon on the `Pad` tree item; no error dialog — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-06-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and judge them. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; a clean restore envelope over a collapsed solid on screen is the defect this closer catches.  

**Cleanup**: restore the recorded `Length` so later scenarios see a healthy document. `document_undo` does not revert a `script_exec` change, so restore it the same way.
```
mcp script_exec { doc: <handle>, code: "doc.getObject('Pad').Length = <recorded Length>" }
mcp document_recompute { doc: <handle> }
```

---

### TC-02-07: query_dependencies per-object and whole-document

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2 (query_dependencies)

**Given** a document with a Body, a Sketch, and a Pad is open — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` names all three  

**When** the per-object view for the Pad is read  
```
mcp query_dependencies { doc: <handle>, object: "Pad" }
```
**And** the whole-document edge list is read  
```
mcp query_dependencies { doc: <handle> }
```

**Then** the per-object shape is the three-key form — verify: `structured_content` keys are exactly `object`, `in_list`, `out_list`  
**And** names are immutable `Name` values, never labels — verify: every entry in `in_list` and `out_list` matches the `Name` on a line of the `query_tree_summary` tree text, not its quoted `"Label"`  
**And** the Pad's profile appears downstream — verify: the Pad's `out_list` contains the `Sketcher::SketchObject` name it pads  
**And** the Pad's Body appears upstream — verify: the Pad's `in_list` contains the `PartDesign::Body` name  
**And** no entry is repeated — verify: `in_list` and `out_list` each contain no duplicate name, because `getOutList` returns an object reachable through two link properties twice and the tool de-duplicates  
**And** the whole-document shape is the four-key form — verify: with no `object`, `structured_content` keys are exactly `edges`, `total_edges`, `returned_edges`, `truncated`  
**And** edges are directed pairs — verify: every entry in `edges` is an object with exactly `from` and `to`  
**And** nothing is truncated at the default cap — verify: `total_edges` equals `returned_edges` and `truncated` is `false`, because the default `max_edges` is 2000  
**And** the two views agree — verify: for every name `n` in the Pad's `out_list`, `edges` contains `{from: "Pad", to: n}`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the window and say what is on screen: a padded solid, present and whole with no edge clipped, and a model tree showing a `Body` item containing a sketch item and a `Pad` item — the three objects the edge list claims exist — with no dialog — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-07-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and judge it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; read the tree items off the screenshot, not off the envelope.  

**Cleanup**: none. Both calls are read-only.

---

### TC-02-08: query_placement local vs global on a datum-attached feature

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2 (query_placement), `data-contracts-design.md` §9 (Quantity)

**Given** a document with a `PartDesign::Body` named `Body` that holds a sketch and a Pad named `Pad` is open  
**And** the Body `Placement` is non-identity. No typed tool writes a Body placement, so set it with `script_exec` (or in the GUI through the Edit > Placement task panel) — verify: `mcp script_exec { doc: <handle>, code: "doc.getObject('Body').Placement = App.Placement(App.Vector(30, 20, 10), App.Rotation(App.Vector(0, 0, 1), 30)); doc.recompute()" }` returns `OK`, and `mcp query_placement { doc: <handle>, object: "Body" }` shows that position  
**And** the Body holds a datum plane made with `feature_datum` (`sketch_create` takes only a base plane or a planar face, so a datum plane is its own object) — verify: `mcp feature_datum { doc: <handle>, body: "Body", name: "DatumPlane", kind: "plane", attachment: <a planar face of Pad>, offset: { value: 5, unit: "mm" } }` returns `OK`  

**When** the container's placement is read  
```
mcp query_placement { doc: <handle>, object: "Body" }
```
**And** the contained features' placements are read  
```
mcp query_placement { doc: <handle>, object: "Pad" }
mcp query_placement { doc: <handle>, object: "DatumPlane" }
```

**Then** the response shape is fixed — verify: `structured_content` keys are exactly `object`, `local`, `global`  
**And** positions carry explicit units — verify: `local.position.x` is a `{value, unit}` object with `unit` `mm`, and the same for `y` and `z`  
**And** the rotation axis is a bare float triple — verify: `local.axis` is `{x, y, z}` with plain numbers and no `unit` key, because an axis is dimensionless  
**And** the angle is reported in degrees — verify: `local.angle` is a `{value, unit}` object with `unit` `deg`, never radians  
**And** the global placement differs from the local one for a contained feature — verify: for `Pad` and for `DatumPlane` inside the moved `Body`, `global.position` differs from `local.position` in at least one axis  
**And** global equals local at the top level — verify: for `Body` itself, `global` equals `local` field for field  
**And** the global value composes the container transform — verify: `global.position` for `Pad` equals the `Body` placement applied to the `Pad` local position, within floating-point tolerance  
**And** an object with no placement is refused cleanly — verify: querying an object that carries no `Placement` returns `INVALID_INPUT` with message `object has no placement: <name>`, not a crash  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the window and say what is on screen: a solid sitting away from the origin axes cross rather than on it, present and whole with no edge clipped, and no dialog — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-08-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and judge it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; do not reason from the reported `Placement` numbers to where the part must be, look at where it is.  

**Cleanup**: none for the reads. The Given changed the document; close it without saving if no later scenario reuses it.

---

### TC-02-09: document_list adopts a GUI-opened document

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_list adoption), `data-contracts-design.md` §9 (AD-20)

**Given** no document is open — verify: `mcp document_list {}` returns `0 open document(s).`  
**And** `box40-hole-r5.FCStd` exists — verify: `ls benchmarks/g0/golden-models/box40-hole-r5.FCStd`  

**When** the file is opened by the FreeCAD GUI, not through MCP. Do not use File > Open: its file dialog is modal, and a modal dialog opened through `invoke_menu` keeps the UIA provider busy until it closes. Use a non-modal route: close FreeCAD through its own menu, then launch it with the file path as its argument and wait for `:8765`. (The Start page **Recent Files** entry for `box40-hole-r5` is a second non-modal route when it is listed.)  
```bash
'{"pid":<pid>,"window_id":<wid>,"path":["File","Exit"]}' | & cua-driver call invoke_menu
'{"path":"$FREECAD_EXE","additional_arguments":["$PROJECT_ROOT\\benchmarks\\g0\\golden-models\\box40-hole-r5.FCStd"]}' | & cua-driver call launch_app
```
**And** the document is confirmed loaded in the GUI, with the new pid and window id from `list_windows`  
```bash
'{"pid":<pid>,"window_id":<wid>,"expect":[{"element":{"selector":{"role":"TreeItem","label_contains":"box40-hole-r5"},"exists":true}}]}' | & cua-driver call verify_state
```
**And** documents are listed over MCP  
```
mcp document_list {}
```

**Then** the GUI opened it — verify: the `verify_state` predicate is `satisfied`, not `unknown`; `unknown` is not success and requires re-snapshotting the window. The main window title from `list_windows` names `box40-hole-r5`  
**And** MCP sees the GUI-opened document — verify: `mcp document_list {}` reports `1 open document(s): box40-hole-r5.`  
**And** a handle was minted on first sight — verify: the listed entry carries a `doc` matching `^fcb-doc:`  
**And** an adopted document is not marked transient — verify: the entry's `transient` is `false`  
**And** the adopted handle is usable — verify: `mcp query_tree_summary { doc: <adopted handle> }` returns the tree lines whose first line names `BoxHole`  
**And** the geometry is the real file, not a stub — verify: `mcp query_mass_properties { doc: <adopted handle>, object: "BoxHole" }` returns `volume` `15214.6018` within 0.1 %  
**And** a second `document_list` does not mint a second handle — verify: calling `mcp document_list {}` again returns the same `doc` string and still one entry  
**And** *(visual)* the adopted document is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<adopted handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the window and say what is on screen: a block with a round hole passing through it, present and whole with no edge clipped, a `BoxHole` entry in the model tree, a title bar reading `box40-hole-r5`, and no dialog left open — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-09-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and judge it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. Adoption means the handle reached the human's own window: the hole must be visible on screen, not merely implied by the volume number.  

**Cleanup**:
```
mcp document_close { doc: <adopted handle> }
```

---

### TC-02-10: Handle survives a GUI selection change

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.1 (never ActiveDocument), `data-contracts-design.md` §9 (AD-20)

**Given** two documents are open with handles A (`box-10-20-30`) and B (`two-box-compound`) — verify: `mcp document_list {}` lists both labels  

**When** A's tree is read and the result recorded  
```
mcp query_tree_summary { doc: <handle A> }
```
**And** the GUI selection and the active MDI window are changed several times, ending on B. The Windows menu numbers its entries: the entry for B reads `<n> two-box-compound : 1` (for example `3 two-box-compound : 1`); take `<n>` from the menu snapshot  
```bash
'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state
'{"pid":<pid>,"window_id":<wid>,"element_token":"<two-box-compound tree item token>"}' | & cua-driver call click
'{"pid":<pid>,"window_id":<wid>,"path":["Windows","<n> two-box-compound : 1"]}' | & cua-driver call invoke_menu
```
**And** A's tree is re-read with the same handle, without touching the GUI again  
```
mcp query_tree_summary { doc: <handle A> }
```

**Then** the GUI selection really moved to B — verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` shows the `two-box-compound` window as active, not `unknown`  
**And** the handle string is unchanged — verify: handle A from the first read is still the exact string used in the re-read  
**And** the re-read returns A's content — verify: the re-read's tree text is identical to the first read and its first line names `Box`  
**And** the re-read is byte-identical apart from nothing — verify: the first and second `structured_content` are equal field for field, since no mutation happened between them  
**And** B remains separately addressable — verify: `mcp query_tree_summary { doc: <handle B> }` returns the tree lines whose first line names `TwoBoxCompound`  
**And** the compound's centre of mass is null, matching the shipped behaviour — verify: `mcp query_mass_properties { doc: <handle B>, object: "TwoBoxCompound" }` returns `volume` `2000.0` within 0.1 %, `counts.solids` `2`, and `com` `null`  
**And** *(visual)* B is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle B>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the window and say what is on screen: two separate box solids, both present and whole with no edge clipped, a title bar reading `two-box-compound` and not `box-10-20-30`, and both documents still listed in the model tree — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-10-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and judge it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. Count the boxes in the picture; do not take `counts.solids` as the answer.  

**Cleanup**:
```
mcp document_close { doc: <handle A> }
mcp document_close { doc: <handle B> }
```

---

### TC-02-11: Tree depth boundary and the retired max_nodes parameter

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2 (depth bound), `data-contracts-design.md` §9 (closed schemas)

**Given** a document with at least two tree levels is open — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` shows child lines with `|-- `/`` `-- `` connectors  
**And** the model is framed and the undisturbed window state captured — verify: fit through the GUI with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-11-before.png"}' | & cua-driver call get_window_state`  

**When** the depth boundary is probed  
```
mcp query_tree_summary { doc: <handle>, depth: 1 }
mcp query_tree_summary { doc: <handle>, depth: 0 }
mcp query_tree_summary { doc: <handle>, depth: -1 }
```
**And** the retired `max_nodes` parameter is passed  
```
mcp query_tree_summary { doc: <handle>, max_nodes: 0 }
mcp query_tree_summary { doc: <handle>, depth: 2, max_nodes: 5 }
```

**Then** `depth: 1` is the minimum accepted value — verify: it returns `status: "OK"` with top-level lines only  
**And** `depth` defaults to 1 when omitted — verify: `mcp query_tree_summary { doc: <handle> }` returns the same tree text as `depth: 1`  
**And** `depth: 0` is a schema reject — verify: the call is rejected by the MCP layer as a protocol error (`isError`, no envelope), because the schema declares `minimum: 1`  
**And** `depth: -1` is a schema reject — verify: same protocol rejection as `depth: 0`  
**And** **`max_nodes` is retired; passing it is a schema reject** — verify: `mcp query_tree_summary { doc: <handle>, max_nodes: 0 }` is rejected by the MCP layer as a protocol error, **not** an `OK` envelope with empty nodes. The former `docs/tests/TC-09` CP6 expected `OK` with `truncated: true`; that expectation is stale. Assert the rejection.  
**And** the rejection is caused by the closed schema — verify: the tool's input schema has `additionalProperties: false` and its `properties` are exactly `doc`, `focus`, `expand`, `depth`, `filters`, with no `max_nodes`  
**And** a valid call still works after the rejections — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` returns a first line starting `OK:`, so a schema reject never poisons the handle  
**And** *(visual)* the model is framed with the **GUI's own Fit All toolbar button** only — verify: click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`). This scenario asserts the MCP surface disturbed nothing, so the framing must not go through MCP either; the before image was framed the same way, which is what makes the two comparable.  
**And** *(visual)* look at both windows and say whether they are the same picture: the same model, at the same size and position, no dialog or error popup raised by the five rejected calls, no document closed or added — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-11-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and judge them. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; a schema rejection that also blanked the viewport would pass every `Then` above and fail here.  

**Cleanup**: none. Every call is read-only or rejected before dispatch.

---

### TC-02-12: query_dependencies max_edges truncation and rejection

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2 (max_edges), `data-contracts-design.md` §9 (truncation is flagged)

**Given** a document with at least two dependency edges is open — verify: `mcp query_dependencies { doc: <handle> }` returns `total_edges` ≥ 2  
**And** the model is framed and the undisturbed window state captured — verify: fit through the GUI with click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-12-before.png"}' | & cua-driver call get_window_state`  

**When** the full edge list is read and `total_edges` recorded  
```
mcp query_dependencies { doc: <handle> }
```
**And** the result is capped at one edge  
```
mcp query_dependencies { doc: <handle>, max_edges: 1 }
```
**And** values below the minimum and a non-integer are passed  
```
mcp query_dependencies { doc: <handle>, max_edges: 0 }
mcp query_dependencies { doc: <handle>, max_edges: -5 }
mcp query_dependencies { doc: <handle>, max_edges: 1.5 }
```

**Then** the default cap truncates nothing here — verify: the uncapped read returns `truncated` `false` and `returned_edges` equal to `total_edges`  
**And** `max_edges: 1` keeps exactly one edge — verify: `edges` has length `1` and `returned_edges` is `1`  
**And** truncation is flagged, not silent — verify: `truncated` is `true` in the capped result  
**And** the full count is still reported when truncated — verify: `total_edges` in the capped result equals `total_edges` from the uncapped read, so a caller can tell how much was withheld  
**And** the kept edge is the first in document order — verify: the single entry equals `edges[0]` from the uncapped read  
**And** `max_edges: 0` is refused — verify: the call returns `INVALID_INPUT` with message `max_edges must be >= 1: 0`, or is rejected by the MCP layer as a protocol error because the schema declares `minimum: 1`. Record which layer refused it.  
**And** `max_edges: -5` is refused the same way — verify: the same refusal shape as `max_edges: 0`, with the value `-5` where the message names it  
**And** a non-integer is refused — verify: `max_edges: 1.5` is refused, either as `INVALID_INPUT` with message `max_edges must be an integer: 1.5` or as a schema protocol rejection  
**And** *(visual)* the model is framed with the **GUI's own Fit All toolbar button** only — verify: click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`). This scenario asserts three refused MCP calls disturbed nothing, so the framing must not go through MCP either; the before image was framed the same way.  
**And** *(visual)* look at both windows and say whether they are the same picture: the same model, at the same size and position, no dialog or error popup raised by the three refused calls, no document closed or added — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-12-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and judge them. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**: none. Every call is read-only or refused.

---

### TC-02-13: Unicode, spaces, and a long label round-trip

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §1.1 (label handling), `data-contracts-design.md` §9 (UTF-8 on the wire)

**Given** no document is open — verify: `mcp document_list {}` returns `0 open document(s).`  
**And** `$RUN_DIR/evidence/tc-02-13-uat-unicode.FCStd` does not exist — verify: `ls "$RUN_DIR/evidence/tc-02-13-uat-unicode.FCStd"` reports no such file  

**When** a document is created whose label mixes CJK, an emoji, spaces, and length  
```
mcp document_create { label: "測試 ドキュメント 🔧 with spaces and a deliberately long label for width" }
```
**And** it is listed, and the window is captured while the Unicode label is still the label  
```
mcp document_list {}
```
```bash
'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-13-unicode.png"}' | & cua-driver call get_window_state
```
**And** it is saved to a plain ASCII path, and closed  
```
mcp document_save { doc: <handle>, path: "$RUN_DIR/evidence/tc-02-13-uat-unicode.FCStd" }
mcp document_close { doc: <handle> }
```
**And** the saved file is reopened and the label read back  
```
mcp document_open { path: "$RUN_DIR/evidence/tc-02-13-uat-unicode.FCStd" }
mcp document_list {}
```

**Then** the create succeeds — verify: the call returns `status: "OK"` with a handle  
**And** the label survives the create — verify: `structured_content.label` equals the input string exactly, including the emoji and both CJK runs  
**And** the internal `Name` is sanitized while the `Label` is not — verify: `structured_content.name` is a FreeCAD-legal identifier and `label` still carries the full Unicode text; the two must not be assumed equal  
**And** the listing carries the label unmangled — verify: `document_list` shows the same label, not a `?` or `\u` escape sequence in the rendered `text`  
**And** no mojibake on the wire — verify: the `document_list` label compares equal byte for byte to the input string in Python, not merely equal when printed to a cp1252 console  
**And** save-as sets the label to the file stem, as GUI Save As does — verify: the save response `structured_content.label` is `tc-02-13-uat-unicode`, and after the reopen `document_list` reports `tc-02-13-uat-unicode`  
**And** the file reads back cleanly — verify: `mcp query_tree_summary { doc: <reopened handle> }` returns a first line starting `OK: 0 objects`  
**And** *(visual)* the reopened document is framed — verify: `mcp view_fit_viewport { doc: "<reopened handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the capture taken before the save and read the label off the screen character by character: both CJK runs and the 🔧 emoji drawn as real glyphs in the model tree entry, not `?` marks, empty boxes, or a `\u` escape; the spaces preserved; the long label either shown in full or visibly elided by the widget rather than truncated to mojibake — verify: `Read` `$RUN_DIR/evidence/tc-02-13-unicode.png` and judge it. Then capture the reopened document with `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-13-after.png"}' | & cua-driver call get_window_state`, `Read` it, and say that the tree entry reads `tc-02-13-uat-unicode` and no dialog is open. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. A label that is byte-correct on the wire and broken on screen is still a defect, and only the picture can show it.  

**Cleanup**:
```
mcp document_close { doc: <reopened handle> }
```
```bash
rm -f "$RUN_DIR/evidence/tc-02-13-uat-unicode.FCStd"
```
Keep `tc-02-13-unicode.png` and `tc-02-13-after.png` as evidence.

---

### TC-02-14: Deeply nested App::Part and App::Link tree

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §3.2 (containment children, `App::Link` lines)

**Given** a document with nested `App::Part` containers and at least one `App::Link` is open. No typed MCP tool creates `App::Part` or `App::Link`: build it with the GUI (Std Part, then Make Link) or with `script_exec` (`outer = doc.addObject('App::Part','OuterPart'); inner = doc.addObject('App::Part','InnerPart'); outer.addObject(inner); box = doc.addObject('Part::Box','LinkTarget'); inner.addObject(box); link = doc.addObject('App::Link','BoxLink'); link.LinkedObject = box; link.Placement.Base.x = 20; outer.addObject(link); doc.recompute()`) — verify: `mcp query_tree_summary { doc: <handle>, depth: 5 }` shows both a `[PART]` line and a `[LINK]` line  

**When** the tree is walked at increasing depth  
```
mcp query_tree_summary { doc: <handle>, depth: 1 }
mcp query_tree_summary { doc: <handle>, depth: 5 }
```
**And** the view is focused on the inner container  
```
mcp query_tree_summary { doc: <handle>, focus: "<inner App::Part name>", depth: 3 }
```

**Then** a link is a leaf line — verify: each `App::Link` line ends `-> <target Name>` and has no child line under it at any depth  
**And** only `App::Link` lines carry an arrow — verify: no line other than a `[LINK]` line contains ` -> `  
**And** counts appear at the depth boundary — verify: at `depth: 1` the outer `App::Part` line ends `(+N)` and no child line is shown  
**And** a leaf carries no count — verify: the `[LINK]` line and every shape line with no children end without `(+N)`  
**And** nesting is preserved to the requested depth — verify: at `depth: 5` the inner `[PART]` line sits under the outer `[PART]` line, each `App::Part` lists its `[ORIGIN]` line first, and the inner Part's own child lines sit under it  
**And** focusing yields the subtree only — verify: the `focus: "<inner App::Part name>"` result starts `path: <outer Part Name> > <inner Part Name>`, and its `shown` is smaller than the whole-document walk at `depth: 5`  
**And** a link does not create a cycle in the walk — verify: the call returns within its 30 s budget and the tree text is identical across two identical calls  
**And** a link target is still reachable — verify: `focus: "<link target name>"` returns `status: "OK"` and its second line names that object  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the window and say what is on screen: two instances of the same shape — the link target and the linked copy — both present and whole with no edge clipped, and a model tree showing one `App::Part` item nested inside another with a link item among them; no dialog — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-14-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and judge it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; a `[LINK]` line with nothing drawn on screen is the failure this closer catches.  

**Cleanup**:
```
mcp document_close { doc: <handle> }
```

---

### TC-02-15: Unknown or stale handle is refused by every document-taking tool

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (handle resolution), `data-contracts-design.md` §9 (closed status set)

**Given** one document is open, so the registry is non-empty and the refusal is not a trivially empty lookup — verify: `mcp document_list {}` reports one entry  
**And** a fabricated handle string is prepared, for example `fcb-doc:not-a-real-handle`  
**And** the live document is framed through the GUI and its window state captured as the untouched baseline — verify: click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-15-before.png"}' | & cua-driver call get_window_state`  

**When** each read-only document-taking tool is called with the fabricated handle  
```
mcp query_tree_summary { doc: "fcb-doc:not-a-real-handle" }
mcp query_object { doc: "fcb-doc:not-a-real-handle", object: "Box" }
mcp query_mass_properties { doc: "fcb-doc:not-a-real-handle", object: "Box" }
mcp query_dependencies { doc: "fcb-doc:not-a-real-handle" }
mcp query_placement { doc: "fcb-doc:not-a-real-handle", object: "Box" }
mcp query_sketch_info { doc: "fcb-doc:not-a-real-handle", sketch: "Sketch" }
```
**And** the lifecycle and verification tools are called with the same handle  
```
mcp document_save { doc: "fcb-doc:not-a-real-handle" }
mcp document_close { doc: "fcb-doc:not-a-real-handle" }
mcp document_recompute { doc: "fcb-doc:not-a-real-handle" }
mcp document_undo { doc: "fcb-doc:not-a-real-handle" }
mcp verify_shape { doc: "fcb-doc:not-a-real-handle" }
mcp query_screenshot { doc: "fcb-doc:not-a-real-handle" }
```
**And** one tool is called with a non-string `doc`  
```
mcp query_tree_summary { doc: 12345 }
```

**Then** every read-only tool refuses — verify: each of the six read-only calls returns `status: "INVALID_INPUT"` with message `unknown or stale document handle: fcb-doc:not-a-real-handle`  
**And** every lifecycle tool refuses — verify: each of the six lifecycle calls returns the same `INVALID_INPUT` message  
**And** the refusal is an envelope, not a protocol error — verify: each response carries `schema` `fcb.result-envelope/1` and `detail.code` `INVALID_INPUT`, because a well-typed but unknown handle passes the JSON Schema and fails at resolution  
**And** nothing crashes — verify: after all twelve calls, `mcp query_capabilities {}` still returns `status: "OK"` and `grep -iE "access violation|segfault|swig" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns nothing  
**And** the live handle is unaffected — verify: the still-open document's handle returns a first line starting `OK:` from `query_tree_summary` after all the refusals  
**And** an omitted `doc` is a schema reject, not a resolution failure — verify: `mcp query_tree_summary {}` is rejected by the MCP layer as a protocol error, because `doc` is in the tool's `required` list  
**And** a non-string `doc` is rejected before dispatch — verify: the call returns `Input validation error: 12345 is not of type 'string'` (schema refusal) or the product message `doc handle must be a string`; the input is refused either way. The MCP input schema declares `doc` as `{type: string}` on every host, so the schema refuses it first; the product guard (`adapters/rpc_listener.py:417-418`, `adapters/mcp_server.py:256-259`) answers only a raw RPC client. Record which message came back.  
**And** *(visual)* the model is framed with the **GUI's own Fit All toolbar button** only — verify: click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`). Every handle in this scenario is deliberately unknown or stale, so no MCP fit can be issued against one; the baseline was framed the same way, which is what makes the two images comparable.  
**And** *(visual)* look at both windows and say whether they are the same picture: the live document still shown, its model present and whole with no edge clipped, the same one entry in the model tree, no view closed by the `document_close` refusal, and no dialog or error popup from any of the refusals — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-15-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and judge them. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. A `document_close` that refused in the envelope but still closed the window would pass every `Then` above and fail here.  

**Cleanup**: none. No call mutated anything.

---

### TC-02-16: Double document_close is refused, not crashed

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (handle release), `data-contracts-design.md` §9 (closed status set)

**Given** no document is open — verify: `mcp document_list {}` returns `0 open document(s).`  

**When** a golden model is opened and the handle recorded  
```
mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/sphere-r10.FCStd" }
```
**And** it is closed, then closed again with the same handle  
```
mcp document_close { doc: <handle> }
mcp document_close { doc: <handle> }
```
**And** the released handle is queried  
```
mcp query_tree_summary { doc: <handle> }
```

**Then** the first close succeeds — verify: `status: "OK"` with `closed: true` and `name` `sphere_r10` (FreeCAD's internal `Name` replaces the `-` of the file stem with `_`)  
**And** the second close is refused — verify: `status: "INVALID_INPUT"` with message `unknown or stale document handle: <handle>`  
**And** the refusal names the handle that failed — verify: the message contains the exact handle string passed in, so a caller can identify which of several handles is stale  
**And** a query through the released handle is refused the same way — verify: the `query_tree_summary` returns the same `INVALID_INPUT` message  
**And** no document was closed twice in FreeCAD — verify: `mcp document_list {}` returns `0 open document(s).` and the FreeCAD window shows no orphan MDI child  
**And** nothing crashed — verify: `mcp query_capabilities {}` still returns `status: "OK"` and the addon log records no traceback for the second close  
**And** the file is intact — verify: `ls -l benchmarks/g0/golden-models/sphere-r10.FCStd` shows the same size as before, and reopening it returns a fresh handle with `volume` `4188.7902` within 0.1 %  
**And** *(visual)* the reopened document is shown and framed with the **GUI's own Fit All toolbar button** only — verify: run Show All, then click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`). The handle this scenario tests is deliberately released, so the framing must come from the GUI rather than from an MCP call on a stale handle.  
**And** *(visual)* look at the window and say what is on screen: exactly one 3D view holding one sphere, present and whole with no edge clipped; one `sphere-r10` entry in the model tree and no second, orphan `sphere-r10` view left behind by the double close; no error dialog — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-16-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and judge it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; count the views and the tree entries in the picture, do not take `0 open document(s).` as the answer.  

**Cleanup**:
```
mcp document_close { doc: <reopened handle> }
```

---

### TC-02-17: Bad open paths are refused, and a missing file is distinguishable

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_open), `data-contracts-design.md` §9 (INVALID_INPUT detail)

**Given** three bad inputs are prepared — verify: the `printf` commands in the first `When` block complete and `ls -l "$RUN_DIR/evidence/tc-02-17-not-fcstd.txt" "$RUN_DIR/evidence/tc-02-17-corrupt.FCStd"` lists both  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** that baseline is shown and framed through the GUI and captured — verify: run Show All, then click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-17-before.png"}' | & cua-driver call get_window_state`  

**When** a non-FCStd file and a corrupt zip are prepared  
```bash
printf 'this is not a FreeCAD document\n' > "$RUN_DIR/evidence/tc-02-17-not-fcstd.txt"
printf 'PK\x03\x04garbage-not-a-real-zip' > "$RUN_DIR/evidence/tc-02-17-corrupt.FCStd"
```
**And** each bad path is opened  
```
mcp document_open { path: "$RUN_DIR/evidence/tc-02-17-does-not-exist.FCStd" }
mcp document_open { path: "$RUN_DIR/evidence/tc-02-17-not-fcstd.txt" }
mcp document_open { path: "$RUN_DIR/evidence/tc-02-17-corrupt.FCStd" }
mcp document_open { path: "" }
mcp document_open { path: "$RUN_DIR/evidence" }
```

**Then** a nonexistent path is refused — verify: `status: "INVALID_INPUT"` with a message starting `document_open failed for '$RUN_DIR/evidence/tc-02-17-does-not-exist.FCStd':`  
**And** a non-FCStd file is refused — verify: `status: "INVALID_INPUT"` with a message starting `document_open failed for '$RUN_DIR/evidence/tc-02-17-not-fcstd.txt':`  
**And** a corrupt zip is refused — verify: `status: "INVALID_INPUT"` with a message starting `document_open failed for '$RUN_DIR/evidence/tc-02-17-corrupt.FCStd':`  
**And** a missing file is distinguishable from an unreadable one — verify: the FreeCAD exception text appended after the colon for the nonexistent path says the file does not exist, and differs from the text for the non-FCStd file and the corrupt zip  
**And** the non-FCStd file and the corrupt zip share one refusal text — verify: both tails read `Invalid project file <path>: ios_base::failbit set: iostream stream error` and differ only in the path. This is the shipped behaviour: the bridge passes FreeCAD's own text through (`usecases/documents.py:496-499`), and the 2026-10-04 sprint change proposal, decision 2 (`_bmad-output/planning-artifacts/sprint-change-proposal-2026-10-04.md`), keeps it and updates this test case  
**And** an empty path is refused before FreeCAD is called — verify: `status: "INVALID_INPUT"` with message `document_open requires a 'path'`  
**And** a directory path is refused — verify: `status: "INVALID_INPUT"` with a message starting `document_open failed for '$RUN_DIR/evidence':`  
**And** no handle leaks from a failed open — verify: `mcp document_list {}` after all five attempts shows only the baseline entry and no new entry  
**And** nothing crashed — verify: `mcp query_capabilities {}` still returns `status: "OK"` and the addon log records no unhandled traceback  
**And** *(visual)* the baseline is framed with the **GUI's own Fit All toolbar button** only — verify: run Show All, then click the **Fit All** toolbar button by its `element_token` from a fresh `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` (the response carries `route: "accessibility"`; `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`). This scenario asserts five failed opens reached nothing, so the framing must not go through MCP either; the before image was framed the same way.  
**And** *(visual)* look at both windows and say whether they are the same picture: the baseline box still the only model on screen, present and whole with no edge clipped; exactly one 3D view and one model-tree entry, with no extra, empty, or half-loaded document added by the five refusals; no error dialog or file dialog left on screen — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-17-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and judge them. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; a refusal in the envelope that still left a blank document in the window would pass every `Then` above and fail here.  

**Cleanup**:
```
mcp document_close { doc: <handle> }
```
```bash
rm -f "$RUN_DIR/evidence/tc-02-17-not-fcstd.txt" "$RUN_DIR/evidence/tc-02-17-corrupt.FCStd"
```

---

### TC-02-18: Save to an unwritable path leaves the original intact

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_save), `data-contracts-design.md` §9 (closed status set)

**Given** a read-only target file exists — verify: `cp benchmarks/g0/golden-models/box-10-20-30.FCStd "$RUN_DIR/evidence/tc-02-18-readonly.FCStd" && chmod 444 "$RUN_DIR/evidence/tc-02-18-readonly.FCStd" && ls -l "$RUN_DIR/evidence/tc-02-18-readonly.FCStd"`  
**And** the original file's size and a hash are recorded — verify: `sha256sum "$RUN_DIR/evidence/tc-02-18-readonly.FCStd"`  

**When** a golden model is opened in a separate handle  
```
mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/cylinder-r5-h20.FCStd" }
```
**And** it is saved over the read-only file, and into a directory that does not exist  
```
mcp document_save { doc: <handle>, path: "$RUN_DIR/evidence/tc-02-18-readonly.FCStd" }
mcp document_save { doc: <handle>, path: "$RUN_DIR/evidence/tc-02-18-no-such-dir/out.FCStd" }
```
**And** it is saved onto a path that names an existing directory  
```
mcp document_save { doc: <handle>, path: "$RUN_DIR/evidence" }
```

**Then** the read-only save is refused with a closed-set status — verify: the response `status` is one of the closed set (`INVALID_INPUT` or `WORKER_CRASHED`), never an ad-hoc code, and never `OK`  
**And** the read-only file is byte-identical afterwards — verify: `sha256sum "$RUN_DIR/evidence/tc-02-18-readonly.FCStd"` matches the hash recorded in the `Given`  
**And** the missing-directory save is refused — verify: the response `status` is a closed-set non-`OK` value and no directory was created (`ls "$RUN_DIR/evidence/tc-02-18-no-such-dir"` reports no such file)  
**And** the directory-as-path save is refused — verify: the response `status` is a closed-set non-`OK` value and `$RUN_DIR/evidence` is still a directory  
**And** the source golden file is untouched — verify: `sha256sum benchmarks/g0/golden-models/cylinder-r5-h20.FCStd` matches its value before the run  
**And** the handle is still usable after all three failures — verify: `mcp query_tree_summary { doc: <handle> }` returns a first line starting `OK:` and tree lines whose first line names `Cylinder`  
**And** a later save to a writable path succeeds — verify: `mcp document_save { doc: <handle>, path: "$RUN_DIR/evidence/tc-02-18-writable.FCStd" }` returns `status: "OK"` with `saved: true`, proving no failed save poisoned the document  
**And** nothing crashed — verify: `mcp query_capabilities {}` still returns `status: "OK"` and the addon log records no unhandled traceback  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* look at the window and say what is on screen: one cylinder, present and whole with no edge clipped; a `Cylinder` entry in the model tree; a title bar reading `tc-02-18-writable` from the one save that succeeded; and no error dialog left on screen by the three refused saves — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-02-18-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and judge it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; a document emptied or corrupted by a failed save would still report `status: "OK"` on the later write and only show up in the picture.  

**Cleanup**:
```
mcp document_close { doc: <handle> }
```
```bash
chmod 644 "$RUN_DIR/evidence/tc-02-18-readonly.FCStd"
rm -f "$RUN_DIR/evidence/tc-02-18-readonly.FCStd" "$RUN_DIR/evidence/tc-02-18-writable.FCStd"
```
