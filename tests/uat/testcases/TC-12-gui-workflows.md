# TC-12: GUI Workflows Observed Through the Bridge

Drives real user workflows through the FreeCAD 1.1.1 GUI with `cua-driver`, then asserts over MCP
that the bridge observes the same state the user sees. This is the maximal-GUI file: the GUI is the
actor and MCP is the observer, which is the opposite direction from every other TC file. It proves
the addon's in-process listener reads the live application rather than a private copy of it, and
that handles, visibility, undo labels, and teardown all survive being driven from the GUI side.

**Host**: GUI through the H2 proxy for every scenario. The GUI is the actor in this file, so no
scenario runs on the H1 headless host. TC-12-14 and TC-12-15 end with the GUI process gone by
design, and each restores it in Cleanup.

**Evidence rank**: we are building the MCP bridge, so the bridge's own output can never be the test
result. A `cua-driver` pixel capture of the real FreeCAD window, `Read` and judged by the agent, is
the test result (rank 1). `cua-driver` accessibility-tree reads, exit codes, the filesystem, and
logs corroborate it (rank 2). MCP envelope fields, statuses, and `query_screenshot` renders are
claims under test, never evidence (rank 3). Commit `636fb8a` is why: the bridge reported a
successful fit while the part occupied about 5 % of the viewport — a correct-looking report over a
wrong reality. In this file specifically, an accessibility-tree read is good corroboration but is
not the visual: a control can be present in the UIA tree and not painted on screen. The PNG decides.

## Preconditions

- [ ] FreeCAD 1.1.1 GUI is open (verify: `Get-Process -Name freecad | Select-Object Id,MainWindowTitle` lists one process with title `FreeCAD 1.1.1`). Find the process by NAME; a `*FreeCAD*` title regex also matches VS Code.
- [ ] The MCP proxy serves `:8765` — the addon auto-spawns it on FreeCAD start (verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row)
- [ ] `cua-driver` runs in the interactive user session (verify: `cua-driver status` reports the daemon and NOT Session 0; Session 0 has no desktop, so UIA enumeration and `PrintWindow` fail there)
- [ ] The FreeCAD `(pid, window_id)` pair is known (verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns the window whose `title` is `FreeCAD 1.1.1`)
- [ ] The menu bar is exposed (verify: `'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state` lists MenuBar children `File Edit View Tools Macro Sketch "Part Design" Windows Help`)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)

### Rules that govern every scenario in this file

- Re-snapshot with `get_window_state` immediately before any element action. Act through
  `element_token`, never a bare `element_index`; indices are per-snapshot and keyed on
  `(pid, window_id)`.
- Prefer `invoke_menu({pid, window_id, path:[...]})` over pixel coordinates. It resolves each hop
  against live UIA and refuses a missing, ambiguous, or disabled segment. Only the verified
  top-level labels above are named here; a deeper submenu leaf is resolved at runtime by
  `invoke_menu`.
- **Submenu paths under `View` do not resolve on this build** (verified 2026-09-12):
  `["View","Standard views",…]`, `["View","Fit all"]` and `["View","Fit All"]` are each refused
  with `menu_path_unavailable` at segment 1; only `["View","Zoom"]` resolves. Qt renders an open
  menu as a popup that is **not** a separate top-level window and whose items do not appear in the
  main window's UIA tree, so submenu leaves cannot be discovered from a snapshot. For any view or
  camera change, use the **toolbar buttons** instead — `Fit All`, `Fit Selection`,
  `Standard Views`, `Align to Selection`, `Draw Style`, `Selection Filter`, `Measure`,
  `New Document`, `Open…`, `Save` are all AX-invokable by `element_token` and return
  `route: "accessibility"`. They are present in the UIA tree **only while a document is open**.
- **The GUI fit is the non-MCP framing route.** Every visual assertion needs the model framed, and
  `mcp view_fit_viewport` is code under test, so it can never be the only way to frame the shot.
  The GUI fallback on this build is the **`Fit All` toolbar button**, invoked by `element_token`
  from a fresh `get_window_state`; it touches none of the code under test. The `View → Fit All`
  menu path is the equivalent route on a build where it resolves, but on this build it is refused
  per the note above — try it only if the toolbar button is absent, and record the refusal.
- **Viewport keystrokes are unreliable.** `press_key` into the 3D view (for example `"0"`) did not
  land even at `delivery_mode:"foreground"`. A `space` on a tree item to toggle visibility landed
  on one attempt and silently did nothing on another — both reporting `effect: "unverifiable"`.
  Always verify the postcondition through MCP state or a fresh screenshot, and retry if needed.
- **Match a tree element by `role == "TreeItem"` and its exact `label`, never by token position.**
  In a live run an adjacent token was the tree's inline **rename editor**: a `space` sent to it
  typed a space into the object's `Label` and `query_tree_summary` reported `label: " "`.
  Recover with a foreground `Ctrl+Z`, then re-verify the label.
- `verify_state` returning `unknown` is NOT success. Record the scenario as inconclusive. The same
  applies to an action result of `effect: "unverifiable"` — it describes the actuator, never the
  task outcome.
- Write snapshot PNGs with `screenshot_out_file` rather than inlining them.
- **A `before.png` used for an identity comparison must be captured after the same fit as its
  `after.png`**, so the two share a camera. A framing difference between two images that were
  framed differently proves nothing.
- Background delivery must never raise or restack the window. Forbidden: `Start-Process`,
  `SetForegroundWindow`, `taskkill /F` — except in TC-12-15, which IS the unclean-kill case and
  says so.
- `modifier` is not honored on a background click on Windows. Escalate that single action to
  `delivery_mode:"foreground"` when a Ctrl-click is genuinely required. `right_click` and `count > 1`
  skip the UIA Invoke step.
- `replay_trajectory` cannot re-resolve element tokens across sessions. Record a trajectory as
  regression evidence only; never use it as the executor for these scenarios.

---

### TC-12-01: Model a bracket end to end through the GUI

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Given** no document is open — verify: `mcp document_list {}` returns an empty list  
**And** the Part Design and Sketch menus are present — verify: `get_window_state` lists `Sketch` and `Part Design` at menu depth 2  

**When** the document and a body are created through the GUI, re-snapshotting before each menu hop  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["File","New"]}' | & cua-driver call invoke_menu
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["Part Design"]}' | & cua-driver call invoke_menu
```
The body-creation leaf under `Part Design` is resolved at runtime by `invoke_menu`.
**And** a new sketch is started on the XY plane through the `Sketch` menu, a closed 60 x 40 mm profile is drawn, and it is constrained fully. Re-snapshot before every action and act through `element_token`.  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-01-sketch.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["Sketch"]}' | & cua-driver call invoke_menu
```
**And** the sketch is closed, then padded 5 mm through the `Part Design` menu. Enter `5` in the Length field with `type_text` bound to the field's `element_token`, then commit.  
**And** a pocket is added for an M5 clearance hole pair 40 mm apart, then the outer corners are filleted at 3 mm, each through the `Part Design` menu with the same snapshot-act-verify loop.  
**And** the result is read over MCP  
```bash
mcp document_list {}
mcp query_tree_summary {doc:<handle>, depth:3}
mcp query_mass_properties {doc:<handle>}
mcp verify_shape {doc:<handle>}
```

**Then** the GUI actions landed — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"Pad"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`; `unknown` is inconclusive, not a pass  
**And** the bridge sees the document — verify: `mcp document_list {}` returns exactly one handle  
**And** the bridge sees the same feature chain — verify: `mcp query_tree_summary {doc:<handle>, depth:3}` lists the Body, the sketch, the pad, the pocket, and the fillet in that dependency order  
**And** the geometry agrees with the design intent — verify: `mcp query_mass_properties {doc:<handle>}` returns a `bbox` of 60 x 40 x 5 mm within the fillet's corner allowance  
**And** the solid is valid — verify: `mcp verify_shape {doc:<handle>}` reports a valid, closed, single solid  
**And** the hole spacing is real — verify: the two pocket cylinders are 40 mm apart, read from `mcp query_placement {doc:<handle>}` or from the sketch datum in `mcp query_sketch_info {doc:<handle>, sketch:"<Sketch>"}`  
**And** the recompute is clean after GUI editing — verify: `mcp verify_recompute {doc:<handle>}` reports no touched, invalid, or error object  
**And** the MCP render matches the viewport — verify: `mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}` produces an image whose silhouette matches a `cua-driver` viewport grab of the same isometric view. The render is the claim and the `cua-driver` grab is the evidence: on a disagreement the grab wins and the render is recorded as the defect.  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on this build), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the finished bracket — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-01-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: the 3D view shows one 60 x 40 x 5 mm plate with two round through-holes and rounded outer corners, and the model tree panel lists the Body with its sketch, pad, pocket, and fillet rows. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-01-sketch.png
```
Close the document in the GUI with `invoke_menu ["File","Close"]` and discard changes.

---

### TC-12-02: A GUI-created document is visible to document_list

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Given** no document is open — verify: `mcp document_list {}` returns an empty list  

**When** the empty state is recorded  
```bash
mcp document_list {}
```
**And** a document is created through the GUI  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["File","New"]}' | & cua-driver call invoke_menu
```
**And** the bridge's view is read  
```bash
mcp document_list {}
```
**And** the returned handle is used for a read  
```bash
mcp query_tree_summary {doc:<handle>}
```

**Then** the GUI created the document — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"Unnamed"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`  
**And** the bridge sees exactly one document — verify: the third `mcp document_list {}` returns one entry where the first returned none  
**And** a handle was minted — verify: the entry carries a non-empty `handle` string  
**And** the handle works for reads — verify: the `query_tree_summary` call returns `OK` with an empty object list for the new document  
**And** the label matches the GUI — verify: the entry's `label` equals the document name shown in the FreeCAD title bar and model tree  
**And** the transient flag is honest — verify: the entry's `transient` flag reflects that the document has never been saved  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on this build), which touches none of the code under test  
**And** *(visual)* the GUI shows a new empty document — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-02-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: the title bar names the new `Unnamed` document, the model tree shows one document root with no child object, and the 3D view is an empty scene. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<handle>}
```

---

### TC-12-03: A GUI-opened golden model is seen with correct geometry

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Given** no document is open — verify: `mcp document_list {}` returns an empty list  
**And** the golden model exists — verify: `Test-Path benchmarks/g0/golden-models/box-10-20-30.FCStd` returns `True`  

**When** the golden model is opened through the GUI file dialog  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["File","Open"]}' | & cua-driver call invoke_menu
```
The dialog is a separate window. Enumerate it with `list_windows`, snapshot it with
`get_window_state`, type the absolute path into the file-name field through its
`element_token`, and commit with `press_key` bound to that same element.
**And** the bridge's view is read  
```bash
mcp document_list {}
mcp query_tree_summary {doc:<handle>}
mcp query_mass_properties {doc:<handle>}
mcp verify_shape {doc:<handle>}
```

**Then** the GUI opened it — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"box-10-20-30"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`  
**And** the bridge sees it — verify: `mcp document_list {}` returns one entry whose `label` contains `box-10-20-30`  
**And** the object is present — verify: `mcp query_tree_summary {doc:<handle>}` names the `Box` object  
**And** the geometry is exact — verify: `mcp query_mass_properties {doc:<handle>}` returns `volume` equal to `6000.0` mm3  
**And** the shape is valid — verify: `mcp verify_shape {doc:<handle>}` reports a valid single closed solid  
**And** the file path is reported — verify: the `document_list` entry names the file it was opened from and its `transient` flag is false  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on this build), which touches none of the code under test  
**And** *(visual)* the GUI shows the opened golden box — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-03-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: the file dialog is gone, the model tree lists a `Box` row under a document named `box-10-20-30`, and the 3D view shows one whole rectangular block with no edge clipped. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<handle>}
```

---

### TC-12-04: GUI tree selection does not change what a doc handle targets

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Given** two documents are open — verify: `mcp document_open {path:"$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd"}` and `mcp document_open {path:"$PROJECT_ROOT/benchmarks/g0/golden-models/sphere-r10.FCStd"}` each return a handle; `mcp document_list {}` returns two entries  

**When** both handles and their volumes are recorded  
```bash
mcp query_mass_properties {doc:<handleBox>}
mcp query_mass_properties {doc:<handleSphere>}
```
**And** the SPHERE document is selected in the GUI model tree. Re-snapshot, then click its tree row through the token from that snapshot.  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-04-tree.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<sphere row token from this snapshot>"}' | & cua-driver call click
```
**And** the BOX handle is queried while the sphere is the GUI's active document  
```bash
mcp query_mass_properties {doc:<handleBox>}
mcp query_tree_summary {doc:<handleBox>}
mcp query_screenshot {doc:<handleBox>, view:{camera:"iso"}}
```
**And** the BOX document is selected in the GUI, then the SPHERE handle is queried the same way  

**Then** the GUI selection changed — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"sphere-r10"},"selected":true}}]}' | & cua-driver call verify_state` returns `satisfied`  
**And** the box handle still returns box geometry — verify: the box-handle `volume` equals `6000.0` mm3, NOT `4188.7902`  
**And** the box handle's tree is the box's — verify: the box-handle `query_tree_summary` names `Box` and not the sphere object  
**And** the render follows the handle, not the selection — verify: the box-handle `query_screenshot` returns `scene.rendered_objects` containing the box object only  
**And** the reverse direction holds — verify: after the box document is selected, `mcp query_mass_properties {doc:<handleSphere>}` returns `4188.7902` mm3  
**And** no tool silently used the active document — verify: no response in either handle-query block names an object belonging to the other document  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handleBox>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on this build), which touches none of the code under test  
**And** *(visual)* the GUI tree shows the selection the scenario made — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-04-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: the model tree lists both documents, the `box-10-20-30` row is the highlighted selection, and the 3D view shows the box document's model rather than the sphere. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-04-tree.png
```
```bash
mcp document_close {doc:<handleBox>}
mcp document_close {doc:<handleSphere>}
```

---

### TC-12-05: A GUI Visibility toggle is observed by query_tree_summary

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Given** a document with two visible top-level shape-bearing objects is open — verify: in the tree lines of `mcp query_tree_summary {doc:<handle>}` both lines start `v `  

**When** the visible set is recorded  
```bash
mcp query_tree_summary {doc:<handle>}
```
**And** the model is framed, then the starting state is captured under that same camera so the later comparison is like-for-like  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-05-before.png"}' | & cua-driver call get_window_state
```
**And** `<ObjectB>` is hidden in the GUI. Re-snapshot, select its tree row by `element_token`, then toggle visibility through the `View` menu; the leaf label is resolved at runtime by `invoke_menu`.  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-05-tree.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<ObjectB row token from this snapshot>"}' | & cua-driver call click
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["View","Visibility"]}' | & cua-driver call invoke_menu
```
**And** the bridge is re-read  
```bash
mcp query_tree_summary {doc:<handle>}
```
**And** visibility is restored by repeating the toggle, then the bridge is re-read again  

**Then** the object vanished from the viewport — verify: a `cua-driver` viewport grab after the toggle no longer shows `<ObjectB>`  
**And** the bridge reports the new flag — verify: in the post-toggle tree text the `<ObjectB>` line starts `- ` and the `<ObjectA>` line starts `v `  
**And** the hidden object is still listed — verify: the post-toggle tree text has the same lines as the pre-toggle one apart from the first character of the `<ObjectB>` line; visibility marks a line, it does not drop it  
**And** no geometry changed — verify: `mcp query_mass_properties {doc:<handle>}` returns the same volume before and after the toggle; visibility is a view flag, not geometry  
**And** restoring works both ways — verify: after the restore, the `<ObjectB>` line starts `v ` again and the tree text equals the pre-toggle one  
**And** the bridge read the live flag, not a cache — verify: the post-toggle result differs from the pre-toggle result without any MCP mutation call in between  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on this build), which touches none of the code under test. Use the same fit that produced `tc-12-05-before.png`, so the two images share a camera.  
**And** *(visual)* the hidden object is gone from the window and the tree marks it hidden — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-05-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the before PNG shows both `<ObjectA>` and `<ObjectB>` drawn in the 3D view, the after PNG shows `<ObjectA>` only, and the `<ObjectB>` tree row is drawn in the greyed style FreeCAD uses for a hidden object. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-05-tree.png $RUN_DIR/evidence/tc-12-05-before.png
```
Restore `<ObjectB>` visibility before leaving the scenario.

---

### TC-12-06: GUI Undo shows the bridge's transaction label

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Given** a document with a padded body is open — verify: `mcp query_tree_summary {doc:<handle>}` names a pad feature  
**And** the undo stack state is recorded before the mutation — verify: `get_window_state` after opening the `Edit` menu shows the current Undo entry label  

**When** one mutation runs over MCP so the bridge opens its own transaction  
```bash
mcp preview_dry_run {doc:<handle>, tool:"feature_fillet", args:{doc:<handle>, base:"<Pad>", edges:[{kind:"geometric", object:"<Pad>", element_type:"edge", query:{}}], radius:{value:3, unit:"mm"}}}
mcp feature_fillet {doc:<handle>, base:"<Pad>", edges:[...], radius:{value:3, unit:"mm"}, confirm:{preview_id:"<token>"}}
```
**And** the `Edit` menu is opened in the GUI and the Undo entry's label is read  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["Edit"]}' | & cua-driver call invoke_menu
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-06-edit.png"}' | & cua-driver call get_window_state
```
**And** Undo is invoked from the GUI  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["Edit","Undo"]}' | & cua-driver call invoke_menu
```
**And** the result is read over MCP  
```bash
mcp query_tree_summary {doc:<handle>}
mcp query_mass_properties {doc:<handle>}
```

**Then** the Undo entry names the bridge's transaction — verify: the `Edit`-menu snapshot tree contains a MenuItem whose label begins with `buddy: `. A generic label such as `Undo` alone means the mutation did not run inside a named transaction, which is a defect.  
**And** the label names the tool — verify: that label identifies the fillet operation, so a human reading the GUI can tell which bridge call produced it  
**And** the undo is enabled — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"buddy:"},"enabled":true}}]}' | & cua-driver call verify_state` returns `satisfied`  
**And** GUI Undo removes the feature — verify: the post-undo `query_tree_summary` no longer names the fillet  
**And** the geometry reverted — verify: the post-undo `query_mass_properties` returns the pre-fillet volume  
**And** the bridge and the GUI share one undo history — verify: after the GUI Undo, `mcp document_undo {doc:<handle>}` either undoes the NEXT older transaction or refuses with an empty stack; it must not undo the same fillet twice  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on this build), which touches none of the code under test  
**And** *(visual)* the window shows the `buddy:` Undo entry and then the un-filleted body — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-06-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: `tc-12-06-edit.png` shows the `Edit` menu open with an Undo entry whose visible text begins `buddy: `, and the after PNG shows the `Edit` menu closed, the model tree without a fillet row, and the pad's corners sharp again. Read the menu label off the painted menu in the image, not off the accessibility tree. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-06-edit.png
```
Close the document in the GUI and discard changes.

---

### TC-12-07: A GUI-side recompute agrees with the bridge

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Given** a document with a feature chain is open — verify: `mcp query_tree_summary {doc:<handle>, depth:3}` lists at least a sketch and a pad  
**And** the document is clean — verify: `mcp verify_recompute {doc:<handle>}` reports no touched object  

**When** the document is made dirty from the GUI by editing a driving parameter in the property editor. Re-snapshot, select the feature row, then write the new value through `set_value` bound to the property field's `element_token`.  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-07-props.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Length field token from this snapshot>","value":"8 mm"}' | & cua-driver call set_value
```
**And** the bridge is asked whether it sees the pending recompute  
```bash
mcp verify_recompute {doc:<handle>}
```
**And** the recompute is run from the GUI. The refresh command lives under a top-level menu resolved at runtime.  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["Edit","Refresh"]}' | & cua-driver call invoke_menu
```
**And** the result is compared against the bridge  
```bash
mcp verify_recompute {doc:<handle>}
mcp document_recompute {doc:<handle>}
mcp query_mass_properties {doc:<handle>}
```

**Then** the GUI edit landed — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"8 mm"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`; `unknown` is inconclusive  
**And** the bridge sees the dirty state — verify: the pre-refresh `verify_recompute` reports at least one Touched object  
**And** the GUI recompute cleaned it — verify: the post-refresh `verify_recompute` reports no touched, invalid, or error object  
**And** a following bridge recompute is a no-op — verify: `document_recompute` reports zero recomputed objects, or reports the same clean state, and does not change the geometry  
**And** the geometry reflects the GUI edit — verify: the post-refresh `query_mass_properties` returns the volume implied by the new 8 mm value  
**And** both sides agree on the final state — verify: `mcp verify_recompute` and a `cua-driver` viewport grab both show a fully rebuilt, error-free model. The grab is the evidence; the `verify_recompute` answer is the claim being checked against it.  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on this build), which touches none of the code under test  
**And** *(visual)* the window shows the rebuilt model at the new 8 mm value — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-07-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: the property editor row reads `8 mm`, no tree row carries the touched or error marker, and the 3D view shows the rebuilt solid rather than a stale or missing shape. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-07-props.png
```
Close the document in the GUI and discard changes.

---

### TC-12-08: GUI Save writes the document and the bridge sees the path

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Given** a modified document is open — verify: `mcp document_list {}` returns a handle; its `transient` flag is true for a never-saved document  
**And** the target directory is writable — verify: `Test-Path $RUN_DIR/evidence` returns `True`  

**When** the pre-save state is recorded  
```bash
mcp document_list {}
mcp query_mass_properties {doc:<handle>}
```
**And** the document is saved from the GUI  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["File","Save"]}' | & cua-driver call invoke_menu
```
The Save dialog is a separate window. Enumerate it with `list_windows`, snapshot it, type
`$RUN_DIR/evidence/tc-12-08-bracket.FCStd` into the file-name field through its `element_token`, and
commit with `press_key` bound to the same element.
**And** the bridge is read  
```bash
mcp document_list {}
```
**And** the document is closed and reopened from the saved file over MCP  
```bash
mcp document_close {doc:<handle>}
mcp document_open {path:"$RUN_DIR/evidence/tc-12-08-bracket.FCStd"}
mcp query_mass_properties {doc:<handleReopened>}
```

**Then** the file exists on disk — verify: `Test-Path $RUN_DIR/evidence/tc-12-08-bracket.FCStd` returns `True`  
**And** the title bar dropped the modified marker — verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns a window title with no trailing modification indicator  
**And** the bridge reports the saved path — verify: the post-save `document_list` entry names `tc-12-08-bracket.FCStd`  
**And** the transient flag cleared — verify: the post-save entry `transient` is false where the pre-save entry had it true  
**And** the saved file round-trips — verify: the reopened `query_mass_properties` returns the same `volume` as the pre-save read  
**And** the handle stayed valid across the save — verify: a read on `<handle>` between the GUI Save and the close returns `OK`, so a GUI Save does not invalidate an existing bridge handle  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handleReopened>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on this build), which touches none of the code under test  
**And** *(visual)* the window shows the reopened saved document — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-08-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: the Save dialog is gone, the title bar reads `tc-12-08-bracket` with no modification marker, and the 3D view shows the same model the pre-save volume described. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<handleReopened>}
```
```bash
rm -f $RUN_DIR/evidence/tc-12-08-bracket.FCStd
```

---

### TC-12-09: A GUI modal dialog blocking the main thread

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

This scenario deliberately raises a modal dialog, which blocks the Qt main thread and can stall any
MCP call issued while it is up. That is the behaviour under test, but it is also a risk to the
automation channel: keep the dialog up only as long as the timed read needs, and dismiss it with
Cancel so no preference is changed. Do not open any further blocking dialog inside this scenario.

**Given** a document is open — verify: `mcp document_list {}` returns a handle  
**And** no modal dialog is currently up — verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns only the main `FreeCAD 1.1.1` window  

**When** a modal dialog is opened from the GUI. The preferences dialog under `Edit` is modal and blocks the Qt main thread; the leaf label is resolved at runtime by `invoke_menu`.  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["Edit","Preferences"]}' | & cua-driver call invoke_menu
'{"pid":<PID>}' | & cua-driver call list_windows
```
**And** a read is issued over MCP while the dialog is up, and timed  
```bash
Measure-Command { mcp query_tree_summary {doc:<handle>} }
```
`query_tree_summary` carries a 30 s budget.
**And** the dialog window is captured while it is still up  
```bash
'{"pid":<PID>,"window_id":<DIALOG_WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-09-dialog.png"}' | & cua-driver call get_window_state
```
**And** the dialog is dismissed through its Cancel button, using the `element_token` from that snapshot  
```bash
'{"pid":<PID>,"element_token":"<Cancel button token from this snapshot>"}' | & cua-driver call click
```
**And** MCP is re-read after the dialog is gone  
```bash
mcp query_tree_summary {doc:<handle>}
mcp query_capabilities {}
```

**Then** the dialog is up and modal — verify: the `list_windows` call taken while the dialog is up returns a second window for the same pid  
**And** the concurrent call either waits or times out within its budget — verify: the timed `query_tree_summary` either returns `OK` or returns a timeout status; it must resolve within about 30 s and must not hang unbounded  
**And** the client is told which happened — verify: on timeout the response carries a status the client can branch on, not a dropped connection  
**And** the dialog dismissal landed — verify: `'{"pid":<PID>}' | & cua-driver call list_windows` after the Cancel click returns only the main window  
**And** the listener survived — verify: the post-dialog `query_capabilities` returns `OK`, so the blocked call did not tear down the in-process listener  
**And** the document is intact — verify: the post-dialog `query_tree_summary` returns the same object list as before the dialog, with no object lost or duplicated  
**And** the proxy is still listening — verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` still returns a row  
**And** *(visual)* the dialog really was up, modal, and then gone — verify: `Read "$RUN_DIR/evidence/tc-12-09-dialog.png"` and state what is on screen: a FreeCAD Preferences dialog painted as a separate window, its title readable, with its Cancel button visible. Then `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-09-after.png"}' | & cua-driver call get_window_state` and `Read` that PNG to confirm no dialog is painted over the main window and the main window is interactive again. A dialog present in the accessibility tree is not enough; it must be painted in the image. No auto-fit is issued before the dialog capture: a `view_fit_viewport` while a modal dialog blocks the Qt main thread would itself stall on the blocked thread and could take down the timed read this scenario depends on, and the GUI `Fit All` button is unreachable behind a modal dialog. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-09-dialog.png
```
Dismiss the dialog with Cancel so no preference is changed.

---

### TC-12-10: Switching workbench does not disturb bridge handles

**Priority**: Medium
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Given** two documents are open — verify: `mcp document_list {}` returns two entries  
**And** both the `Sketch` and `Part Design` menus are present — verify: `get_window_state` lists both at menu depth 2  

**When** both handles are recorded and each one is read  
```bash
mcp document_list {}
mcp query_mass_properties {doc:<handleA>}
mcp query_mass_properties {doc:<handleB>}
```
**And** the workbench is switched in the GUI through the workbench selector. Re-snapshot, then set its value through the combo box's `element_token`.  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-10-wb.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<workbench selector token from this snapshot>","value":"Sketcher"}' | & cua-driver call set_value
```
**And** both handles are re-read, then the workbench is switched to Part Design and both are read again  
```bash
mcp query_mass_properties {doc:<handleA>}
mcp query_mass_properties {doc:<handleB>}
```

**Then** the workbench changed — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"Sketcher"},"selected":true}}]}' | & cua-driver call verify_state` returns `satisfied`; `unknown` is inconclusive  
**And** both handles still resolve — verify: both post-switch calls return `OK`, not `INVALID_INPUT`  
**And** the geometry is unchanged — verify: both post-switch volumes equal their pre-switch values exactly  
**And** no handle was remapped — verify: `mcp document_list {}` after the switch returns the same two handle strings as the pre-switch list  
**And** the switch back is equally harmless — verify: after switching to Part Design, both handles still read the same values  
**And** the listener is unaffected — verify: `mcp query_capabilities {}` returns `OK` with the same `render` mode after both switches  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handleA>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on this build), which touches none of the code under test  
**And** *(visual)* the window shows the switched workbench with both documents intact — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-10-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: the workbench selector reads `Part Design`, its toolbars replaced the Sketcher ones, the model tree still lists both documents, and the 3D view still shows document A's model. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-10-wb.png
```
```bash
mcp document_close {doc:<handleA>}
mcp document_close {doc:<handleB>}
```

---

### TC-12-11: A large tree stays navigable while the summary stays bounded

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Given** a document with at least 50 features is open — verify: `mcp query_tree_summary {doc:<handle>, depth:3}` reports 50 or more objects. Build it by patterning a padded profile, or open an existing large model.  

**When** the full tree is read at depth 1 and depth 3  
```bash
mcp query_tree_summary {doc:<handle>}
mcp query_tree_summary {doc:<handle>, depth:3}
```
**And** a filtered slice is read  
```bash
mcp query_tree_summary {doc:<handle>, filters:{types:["PAD"]}}
mcp query_tree_summary {doc:<handle>, filters:{name_pattern:"Pad*"}}
```
**And** the GUI tree is scrolled and inspected. Re-snapshot before the scroll and act by `element_token`.  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-11-tree.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Tree token from this snapshot>","direction":"down","amount":10}' | & cua-driver call scroll
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-11-tree2.png"}' | & cua-driver call get_window_state
```

**Then** the GUI tree scrolls — verify: the two snapshot trees taken around the scroll expose different visible rows, so the list is navigable at this size  
**And** the default depth stays shallow — verify: the first read returns top-level lines only, not all 50 features; `depth` defaults to 1  
**And** deeper depth returns more — verify: the depth-3 read has a strictly greater `shown` than the depth-1 read, and at most 200 tree lines; when the cap cuts it, `truncated` is true and the last line is `... <K> more lines; narrow with focus or a smaller depth`  
**And** filters reveal a slice — verify: both filtered calls report `matches`, show each match on its opened path, and have a smaller `shown` than the depth-3 call  
**And** `max_nodes` is not a parameter — verify: `mcp query_tree_summary {doc:<handle>, max_nodes:10}` returns `INVALID_INPUT`; the schema sets `additionalProperties: false` and `max_nodes` is retired  
**And** each call stays within its budget — verify: every `query_tree_summary` call in this scenario returns within its 30 s timeout  
**And** the GUI stays responsive — verify: a `get_window_state` taken after the queries still returns a populated tree, not `degraded`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on this build), which touches none of the code under test  
**And** *(visual)* the GUI tree really scrolled and the model is still drawn — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-11-after.png"}' | & cua-driver call get_window_state`, then `Read` `tc-12-11-tree.png` and `tc-12-11-tree2.png` and state what is on screen: the model tree panel paints a different set of feature rows in the second image, with row labels readable in each. Then `Read` the after PNG and confirm the 3D view still shows the 50-feature model whole and framed. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-11-tree.png $RUN_DIR/evidence/tc-12-11-tree2.png
```
Close the document in the GUI and discard changes.

---

### TC-12-12: A long GUI operation freezes the viewport but not the bridge

**Priority**: Medium
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Given** a document whose recompute takes several seconds is open — verify: a prior `mcp document_recompute {doc:<handle>}` took more than 3 s  
**And** the proxy is listening — verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row  

**When** a long operation is started from the GUI  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["Edit","Refresh"]}' | & cua-driver call invoke_menu
```
**And** a viewport grab is taken and an MCP read issued while it runs  
```bash
Measure-Command { mcp query_capabilities {} }
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-12-busy.png"}' | & cua-driver call get_window_state
```
**And** the bridge is read again after the operation finishes  
```bash
mcp query_tree_summary {doc:<handle>}
mcp verify_recompute {doc:<handle>}
```

**Then** the viewport freezes for the operation's duration — verify: `$RUN_DIR/evidence/tc-12-12-busy.png` shows a stale or unpainted viewport. This is documented and accepted behavior: FreeCAD's recompute runs on the Qt main thread.  
**And** the bridge does not drop the connection — verify: the concurrent `query_capabilities` returns `OK` or a timeout status, never a transport-level disconnect  
**And** the proxy stays listening throughout — verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row during and after the operation  
**And** post-operation reads succeed — verify: both post-operation calls return `OK`  
**And** the model is complete — verify: the post-operation `verify_recompute` reports no touched, invalid, or error object  
**And** the GUI recovers — verify: a `get_window_state` after the operation returns a populated tree and a freshly painted viewport, not `degraded`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on this build), which touches none of the code under test. Issue this fit only after the long operation has finished; a fit during the freeze cannot land.  
**And** *(visual)* the frozen viewport recovered into a painted one — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-12-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the busy PNG shows a stale, blank, or white-washed 3D view during the recompute, and the after PNG shows the model freshly painted and framed in a responsive, non-greyed main window. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-12-busy.png
```

---

### TC-12-13: Closing a document in the GUI invalidates its handle cleanly

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Given** two documents are open — verify: `mcp document_list {}` returns two entries  
**And** both handles read successfully — verify: `mcp query_tree_summary {doc:<handleA>}` and the same for `<handleB>` both return `OK`  

**When** both handles are recorded  
```bash
mcp document_list {}
```
**And** document A is closed in the GUI. Re-snapshot, select its tree row by `element_token`, then invoke the close command.  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-13-tree.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<document A row token from this snapshot>"}' | & cua-driver call click
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["File","Close"]}' | & cua-driver call invoke_menu
```
If a save prompt appears, enumerate it with `list_windows`, snapshot it, and click its discard
button by `element_token`.
**And** the stale handle is used  
```bash
mcp query_tree_summary {doc:<handleA>}
mcp query_mass_properties {doc:<handleA>}
mcp query_screenshot {doc:<handleA>}
mcp document_close {doc:<handleA>}
```
**And** document B is confirmed unharmed  
```bash
mcp document_list {}
mcp query_mass_properties {doc:<handleB>}
```

**Then** the GUI closed it — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"<document A label>"},"exists":false}}]}' | & cua-driver call verify_state` returns `satisfied`; `unknown` is inconclusive, not a pass  
**And** every stale read returns INVALID_INPUT — verify: all three stale read calls return `INVALID_INPUT`, not `WORKER_CRASHED` and not `OK` with empty data  
**And** the stale close is also a clean refusal — verify: `document_close` on the stale handle returns `INVALID_INPUT`, not a crash  
**And** no crash and no hang — verify: FreeCAD is still running (`Get-Process -Name freecad` returns the same pid) and each stale call returned within its own timeout  
**And** the list no longer names document A — verify: the final `document_list` returns one entry, and its handle is `<handleB>`  
**And** document B still works — verify: the final `query_mass_properties` on `<handleB>` returns `OK` with its original volume  
**And** the listener is intact — verify: `mcp query_capabilities {}` returns `OK`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handleB>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on this build), which touches none of the code under test  
**And** *(visual)* the GUI shows document B alone — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-13-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: the model tree paints only document B, no row named `<document A label>` remains, no save prompt or error popup is up, and the 3D view shows document B's model whole and framed. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-13-tree.png
```
```bash
mcp document_close {doc:<handleB>}
```

---

### TC-12-14: Quitting FreeCAD tears down the listener and the proxy child

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

The quit path can raise a save-decision dialog, which would block the automation channel. The
`Given` below requires no unsaved document precisely so that no blocking prompt appears. If one
appears anyway, dismiss it through `list_windows` plus an `element_token` click on its discard
button, and record the unexpected prompt as a finding.

**Given** FreeCAD is running and the proxy is serving — verify: `Get-Process -Name freecad` returns a pid and `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row  
**And** no unsaved document is open, so the quit needs no save decision — verify: `mcp document_list {}` returns an empty list  
**And** the discovery file location is known — verify: `Get-ChildItem "$env:APPDATA/FreeCAD/v1-1/freecad-buddy"` lists the RPC discovery file  

**When** the live state is recorded  
```bash
Get-Process -Name freecad | Select-Object Id
netstat -ano | Select-String ":8765"
Get-ChildItem "$env:APPDATA/FreeCAD/v1-1/freecad-buddy"
```
Note the proxy pid from the `:8765` row; it is a child process, not FreeCAD's own pid.
**And** the running window is captured before the quit  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-14-before.png"}' | & cua-driver call get_window_state
```
**And** FreeCAD is quit cleanly. Do NOT use `taskkill /F` here — this scenario is the clean-teardown case.  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["File","Exit"]}' | & cua-driver call invoke_menu
```
If the menu leaf does not resolve, use `'{"pid":<PID>,"keys":["alt","f4"]}' | & cua-driver call hotkey`.
**And** the same three facts are re-read after the process is gone  
```bash
Get-Process -Name freecad
netstat -ano | Select-String ":8765"
Get-ChildItem "$env:APPDATA/FreeCAD/v1-1/freecad-buddy"
```

**Then** FreeCAD exited — verify: the post-quit `Get-Process -Name freecad` returns nothing  
**And** `:8765` stops listening — verify: the post-quit `netstat` returns no LISTENING row for `:8765`  
**And** the proxy child is gone — verify: the proxy pid recorded before the quit is no longer in `Get-Process`; it was torn down with its parent, not orphaned  
**And** the discovery file is deleted — verify: the post-quit `Get-ChildItem` no longer lists the RPC discovery file  
**And** a client call now fails at the transport — verify: `mcp query_capabilities {}` fails to connect to `http://127.0.0.1:8765/mcp`; it must not hang indefinitely  
**And** the addon log records a clean shutdown — verify: `Get-Content "$env:APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log" -Tail 20` shows the teardown and no unhandled exception  
**And** restart is clean — verify: reopening FreeCAD recreates the discovery file, re-serves `:8765`, and `mcp query_capabilities {}` returns `OK` again  
**And** *(visual)* the window that existed is gone, and the restarted one is back — verify: `'{"pid":<PID>}' | & cua-driver call list_windows` after the quit returns no FreeCAD window, then after the restart `'{"pid":<NEW_PID>,"window_id":<NEW_WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-14-after.png"}' | & cua-driver call get_window_state`; `Read` both PNGs and state what is on screen: the before PNG shows a live FreeCAD 1.1.1 main window with its menu bar and painted workspace, and the after PNG shows a freshly started FreeCAD 1.1.1 window with its start page and no crash or recovery dialog. No auto-fit is issued by either route: the target process does not exist between the quit and the restart, and the restarted instance holds no document, so the `Fit All` toolbar button is absent from the UIA tree. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-14-before.png
```
Reopen FreeCAD so later scenarios have a live GUI. No other files to remove.

---

### TC-12-15: An unclean kill surfaces WORKER_CRASHED and leaves no half-open bridge

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Given** FreeCAD is running with a document open — verify: `mcp document_list {}` returns a handle  
**And** the proxy is serving — verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row  
**And** nothing unsaved is at risk. Use a scratch document only. An unclean kill loses unsaved work.  

**When** the live pids are recorded  
```bash
Get-Process -Name freecad | Select-Object Id
netstat -ano | Select-String ":8765"
```
**And** the running window is captured before the kill  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-15-before.png"}' | & cua-driver call get_window_state
```
**And** a long MCP call is started, then FreeCAD is killed mid-call. **This scenario is the explicit unclean-kill case, so a forced termination is intentional here and ONLY here.**  
```bash
mcp document_recompute {doc:<handle>}   # issue this, then immediately run the kill below
```
```bash
Stop-Process -Id <FREECAD_PID> -Force
```
**And** the client's result and the surviving state are read  
```bash
Get-Process -Name freecad
netstat -ano | Select-String ":8765"
mcp query_capabilities {}
```

**Then** the in-flight call surfaces a crash to the client — verify: the `document_recompute` issued before the kill returns `WORKER_CRASHED`, or fails at the transport with a connection error. It must NOT return `OK`.  
**And** the client does not hang — verify: that same call resolves within its 120 s budget; an unbounded wait is a defect  
**And** FreeCAD is gone — verify: the post-kill `Get-Process -Name freecad` returns nothing  
**And** no half-open bridge remains — verify: the post-kill `netstat` returns no LISTENING row for `:8765` that still accepts connections; a socket that accepts but never answers is a defect  
**And** a following call fails fast — verify: the post-kill `query_capabilities` fails at the transport and returns promptly  
**And** no orphan proxy — verify: the proxy pid recorded before the kill is no longer in `Get-Process`. If it survives, record the orphan pid as a defect and stop it manually before continuing.  
**And** restart recovers fully — verify: reopening FreeCAD re-serves `:8765`, recreates the discovery file, and `mcp query_capabilities {}` returns `OK`  
**And** no stale snapshot or temp file blocks restart — verify: `Get-ChildItem $env:TEMP -Filter "FCB_TMP_*"` names only files whose transaction is known to have been in flight; the restarted host must still serve normally  
**And** *(visual)* the killed window is gone and the restarted one comes back clean — verify: `'{"pid":<PID>}' | & cua-driver call list_windows` after the kill returns no FreeCAD window, then after the restart `'{"pid":<NEW_PID>,"window_id":<NEW_WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-15-after.png"}' | & cua-driver call get_window_state`; `Read` both PNGs and state what is on screen: the before PNG shows a live main window with the scratch document painted in its 3D view, and the after PNG shows a freshly started FreeCAD 1.1.1 window. Record whether a document-recovery prompt is painted in the after PNG: it is expected after an unclean kill, and it must be dismissed rather than left blocking the channel. No auto-fit is issued by either route: the target process was killed and the restarted instance holds no document, so the `Fit All` toolbar button is absent from the UIA tree. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-15-before.png
```
Reopen FreeCAD. Remove any `FCB_TMP_snap_*` or `FCB_TMP_shot_*` leftovers the kill orphaned:
```bash
rm -rf $env:TEMP/FCB_TMP_snap_* $env:TEMP/FCB_TMP_shot_*
```
