# TC-12: GUI Workflows Observed Through the Bridge

Drives real user workflows through the FreeCAD 1.1.x GUI with `cua-driver`, then asserts over MCP
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

- [ ] FreeCAD 1.1.x installed (verify: `ls "$FREECAD_EXE"`); the build under test is the live version: `query_capabilities.freecad_version`, read once at the start of the run and written `<live version>` below
- [ ] FreeCAD GUI is open (verify: `Get-Process -Name freecad | Select-Object Id,MainWindowTitle` lists one process whose title ends `FreeCAD <live version>`). Find the process by NAME; a `*FreeCAD*` title regex also matches VS Code.
- [ ] FreeCAD runs at the agent shell's integrity level, so the agent shell can stop it (verify: the `cua-driver` daemon was started from the agent shell, per `freecad-gui-e2e-harness.md` §2)
- [ ] The MCP proxy serves `:8765` — the addon auto-spawns it on FreeCAD start (verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row)
- [ ] `cua-driver` runs in the interactive user session (verify: `cua-driver status` reports the daemon and NOT Session 0; Session 0 has no desktop, so UIA enumeration and `PrintWindow` fail there)
- [ ] The FreeCAD `(pid, window_id)` pair is known (verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns the window whose `title` ends `FreeCAD <live version>`)
- [ ] The menu bar is exposed (verify: `'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state` lists MenuBar children `File Edit View Tools Macro Sketch "Part Design" Windows Help`)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)
- [ ] Golden and fault `.FCStd` files have no `GuiDocument.xml` and open with every object hidden. After each `document_open` of such a file, and before any fit or render of it, run **Show All**: `cua-driver call invoke_menu { pid, window_id, path: ["View","Visibility","Show All Objects"] }`. A fit before it returns `SPEC_FAILED view_fit.nothing_to_frame`.

### Rules that govern every scenario in this file

- Re-snapshot with `get_window_state` immediately before any element action. Act through
  `element_token`, never a bare `element_index`; indices are per-snapshot and keyed on
  `(pid, window_id)`.
- Prefer `invoke_menu({pid, window_id, path:[...]})` over pixel coordinates. It resolves each hop
  against live UIA and refuses a missing, ambiguous, or disabled segment. Only the verified
  top-level labels above are named here; a deeper submenu leaf is resolved at runtime by
  `invoke_menu`.
- **Some `View` submenu paths resolve on FreeCAD 1.1.x and some do not.**
  `["View","Visibility","Show All Objects"]` and `["View","Zoom",…]` resolve.
  `["View","Standard views",…]` and `["View","Fit All"]` are refused with `menu_path_unavailable`.
  A leaf that resolves can still be refused while another popup is open: re-snapshot and try once
  more, then use the toolbar route. Qt renders an open menu as a popup that is **not** a separate
  top-level window and whose items do not appear in the main window's UIA tree, so submenu leaves
  cannot be discovered from a snapshot. For any camera change, use the **toolbar buttons** instead — `Fit All`, `Fit Selection`,
  `Standard Views`, `Align to Selection`, `Draw Style`, `Selection Filter`, `Measure`,
  `New Document`, `Save` are all AX-invokable by `element_token` and return
  `route: "accessibility"`. They are present in the UIA tree **only while a document is open**.
- **Never open a modal dialog through `invoke_menu` or a toolbar button by `element_token`.**
  The UIA call blocks until the dialog closes, and the UIA provider stays busy, so every later
  background action returns `background_unavailable`. File > Open, File > Save As, the `Open…`
  toolbar button and Edit > Preferences are modal. To open a file in the GUI, quit FreeCAD with
  `invoke_menu ["File","Exit"]` and launch it again with the file path as its argument
  (`launch_app` with `additional_arguments`), or double-click its Start page **Recent Files**
  entry. To change a preference, write it with `script_exec`
  (`FreeCAD.ParamGet(...)`) and restore it in Cleanup.
- **The GUI fit is the non-MCP framing route.** Every visual assertion needs the model framed, and
  `mcp view_fit_viewport` is code under test, so it can never be the only way to frame the shot.
  The GUI fallback on FreeCAD 1.1.x is the **`Fit All` toolbar button**, invoked by `element_token`
  from a fresh `get_window_state`; it touches none of the code under test. The `View → Fit All`
  menu path is the equivalent route on a build where it resolves, but on FreeCAD 1.1.x it is refused
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
  says so. `kill_app` and a `Stop-Process` from a shell at a lower integrity level than FreeCAD
  are refused; TC-12-15 stops FreeCAD from the agent shell, at the same integrity level.
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
'{"pid":<PID>,"window_id":<WID>,"path":["File","New Document"]}' | & cua-driver call invoke_menu
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["Part Design"]}' | & cua-driver call invoke_menu
```
If `["File","New Document"]` is refused, click the `New Document` toolbar button by `element_token`.
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
mcp query_mass_properties {doc:<handle>, object:"<Fillet>"}
mcp verify_shape {doc:<handle>}
```

**Then** the GUI actions landed — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"Pad"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`; `unknown` is inconclusive, not a pass  
**And** the bridge sees the document — verify: `mcp document_list {}` returns exactly one handle  
**And** the bridge sees the same feature chain — verify: `mcp query_tree_summary {doc:<handle>, depth:3}` lists the Body, the sketch, the pad, the pocket, and the fillet in that dependency order  
**And** the geometry agrees with the design intent — verify: `mcp query_mass_properties {doc:<handle>, object:"<Fillet>"}` returns a `bbox` of 60 x 40 x 5 mm within the fillet's corner allowance  
**And** the solid is valid — verify: `mcp verify_shape {doc:<handle>}` reports a valid, closed, single solid  
**And** the hole spacing is real — verify: the two pocket cylinders are 40 mm apart, read from `mcp query_placement {doc:<handle>}` or from the sketch datum in `mcp query_sketch_info {doc:<handle>, sketch:"<Sketch>"}`  
**And** the recompute is clean after GUI editing — verify: `mcp verify_recompute {doc:<handle>}` returns `OK` with `subject.failing_objects` empty  
**And** the MCP render matches the viewport — verify: `mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}` produces an image whose silhouette matches a `cua-driver` viewport grab of the same isometric view. The render is the claim and the `cua-driver` grab is the evidence: on a disagreement the grab wins and the render is recorded as the defect.  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on FreeCAD 1.1.x), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the finished bracket — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-01-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: the 3D view shows one 60 x 40 x 5 mm plate with two round through-holes and rounded outer corners, and the model tree panel lists the Body with its sketch, pad, pocket, and fillet rows. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-01-sketch.png
```
Close the document with `mcp document_close {doc:<handle>}`. It closes without a save prompt; `File > Close` on a modified document opens a modal save prompt, which a test case never opens through `invoke_menu`.

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
'{"pid":<PID>,"window_id":<WID>,"path":["File","New Document"]}' | & cua-driver call invoke_menu
```
If the leaf is refused, click the `New Document` toolbar button by `element_token` instead.
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
**And** a handle was minted — verify: the entry carries a non-empty `doc` string that matches `^fcb-doc:`  
**And** the handle works for reads — verify: the `query_tree_summary` call returns `OK` with an empty object list for the new document  
**And** the label matches the GUI — verify: the entry's `label` equals the document name shown in the FreeCAD title bar and model tree  
**And** an adopted document is not transient — verify: the entry's `transient` is `false`. `transient` marks a document the bridge created and has not saved (`documents.py:471`); a document the GUI created is adopted with `transient: false` (`documents.py:708`)  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on FreeCAD 1.1.x), which touches none of the code under test  
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

**When** the golden model is opened by the FreeCAD GUI through a non-modal route. File > Open is modal, so it is not used: quit FreeCAD through its own menu, launch it again with the file path as its argument, wait for `:8765`, and record the new pid and window id from `list_windows`. The Start page **Recent Files** entry for `box-10-20-30` is a second non-modal route when it is listed: double-click it.  
```bash
'{"pid":<PID>,"window_id":<WID>,"path":["File","Exit"]}' | & cua-driver call invoke_menu
'{"path":"$FREECAD_EXE","additional_arguments":["$PROJECT_ROOT\\benchmarks\\g0\\golden-models\\box-10-20-30.FCStd"]}' | & cua-driver call launch_app
```
**And** the bridge's view is read  
```bash
mcp document_list {}
mcp query_tree_summary {doc:<handle>}
mcp query_mass_properties {doc:<handle>, object:"Box"}
mcp verify_shape {doc:<handle>}
```

**Then** the GUI opened it — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"role":"TreeItem","label_contains":"box-10-20-30"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`  
**And** the bridge sees it — verify: `mcp document_list {}` returns one entry whose `label` contains `box-10-20-30`  
**And** the object is present — verify: `mcp query_tree_summary {doc:<handle>}` names the `Box` object  
**And** the geometry is exact — verify: `mcp query_mass_properties {doc:<handle>, object:"Box"}` returns `volume` equal to `6000.0` mm3  
**And** the shape is valid — verify: `mcp verify_shape {doc:<handle>}` reports a valid single closed solid  
**And** the file is identified — verify: the `document_list` entry's `label` is the file stem `box-10-20-30` (`document_list` carries `doc`, `name`, `label` and `transient`, and no path) and its `transient` flag is false  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on FreeCAD 1.1.x), which touches none of the code under test  
**And** *(visual)* the GUI shows the opened golden box — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-03-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: no dialog is open, the model tree lists a `Box` row under a document named `box-10-20-30`, and the 3D view shows one whole rectangular block with no edge clipped. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

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
mcp query_mass_properties {doc:<handleBox>, object:"Box"}
mcp query_mass_properties {doc:<handleSphere>, object:"Sphere"}
```
**And** Show All is run in each document while its tab is active, so the renders below have a visible subject  
**And** the SPHERE document is selected in the GUI model tree. Re-snapshot, then click its tree row through the token from that snapshot, matched on `role == "TreeItem"` and its label.  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-04-tree.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<sphere row token from this snapshot>"}' | & cua-driver call click
```
**And** the BOX handle is queried while the sphere is the GUI's active document  
```bash
mcp query_mass_properties {doc:<handleBox>, object:"Box"}
mcp query_tree_summary {doc:<handleBox>}
mcp query_screenshot {doc:<handleBox>, view:{camera:"iso"}}
```
**And** the BOX document is selected in the GUI, then the SPHERE handle is queried the same way  

**Then** the GUI selection changed — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"role":"TreeItem","label_contains":"sphere-r10"},"selected":true}}]}' | & cua-driver call verify_state` returns `satisfied`  
**And** the box handle still returns box geometry — verify: the box-handle `volume` equals `6000.0` mm3, NOT `4188.7902`  
**And** the box handle's tree is the box's — verify: the box-handle `query_tree_summary` names `Box` and not the sphere object  
**And** the render follows the handle, not the selection — verify: the box-handle `query_screenshot` returns `scene.rendered_objects` containing the box object only  
**And** the reverse direction holds — verify: after the box document is selected, `mcp query_mass_properties {doc:<handleSphere>, object:"Sphere"}` returns `4188.7902` mm3  
**And** no tool silently used the active document — verify: no response in either handle-query block names an object belonging to the other document  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handleBox>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on FreeCAD 1.1.x), which touches none of the code under test  
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
**And** no geometry changed — verify: `mcp query_mass_properties {doc:<handle>, object:"<ObjectA>"}` and the same call for `<ObjectB>` return the same volumes before and after the toggle; visibility is a view flag, not geometry  
**And** restoring works both ways — verify: after the restore, the `<ObjectB>` line starts `v ` again and the tree text equals the pre-toggle one  
**And** the bridge read the live flag, not a cache — verify: the post-toggle result differs from the pre-toggle result without any MCP mutation call in between  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on FreeCAD 1.1.x), which touches none of the code under test. Use the same fit that produced `tc-12-05-before.png`, so the two images share a camera.  
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
**And** the undo stack state is recorded before the mutation — verify: a snapshot shows the toolbar `Undo` button and whether it is enabled  
**And** the fillet edge is named — verify: an outside topology oracle (`script_exec` reading `doc.getObject('<Pad>').Shape.Edges`, or the `fcb` env) gives one vertical edge of the pad; record its name as `<edge>`  

**When** one mutation runs over MCP so the bridge opens its own transaction  
```bash
mcp preview_dry_run {doc:<handle>, operation:{tool:"feature_fillet", args:{body:"<Body>", base:"<Pad>", name:"Fillet", edges:[{kind:"mapped_name", object:"<Pad>", mapped_name:"<edge>"}], radius:{value:3, unit:"mm"}}}}
mcp feature_fillet {doc:<handle>, body:"<Body>", base:"<Pad>", name:"Fillet", edges:[{kind:"mapped_name", object:"<Pad>", mapped_name:"<edge>"}], radius:{value:3, unit:"mm"}, confirm:{preview_id:"<token>"}}
```
**And** the toolbar `Undo` dropdown is opened in the GUI and its first entry is read. FreeCAD 1.1.x does not rename the Edit > Undo menu item: the transaction name is shown in the dropdown list of the toolbar `Undo` button. Open the dropdown by its arrow, by `element_token` from a fresh snapshot. The list is a popup: find it with `list_windows` and snapshot it, or read the painted pixels.  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Undo dropdown arrow token from this snapshot>"}' | & cua-driver call click
'{"pid":<PID>}' | & cua-driver call list_windows
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-06-edit.png"}' | & cua-driver call get_window_state
```
Close the dropdown without choosing an entry before the next step.
**And** Undo is invoked from the GUI  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["Edit","Undo"]}' | & cua-driver call invoke_menu
```
**And** the result is read over MCP  
```bash
mcp query_tree_summary {doc:<handle>}
mcp query_mass_properties {doc:<handle>, object:"<Pad>"}
```

**Then** the Undo entry names the bridge's transaction — verify: the first entry of the toolbar `Undo` dropdown begins with `buddy: `. An entry without that prefix means the mutation did not run inside a named transaction, which is a defect.  
**And** the label names the tool — verify: that entry reads `buddy: feature_fillet Fillet`, so a human reading the GUI can tell which bridge call produced it  
**And** the undo is enabled — verify: `'{"pid":<PID>,"window_id":<POPUP_WID>,"expect":[{"element":{"selector":{"label_contains":"buddy:"},"enabled":true}}]}' | & cua-driver call verify_state` on the dropdown popup window returns `satisfied`; `unknown` is inconclusive  
**And** GUI Undo removes the feature — verify: the post-undo `query_tree_summary` no longer names the fillet  
**And** the geometry reverted — verify: the post-undo `query_mass_properties` returns the pre-fillet volume  
**And** the bridge and the GUI share one undo history — verify: after the GUI Undo, `mcp document_undo {doc:<handle>}` either undoes the NEXT older transaction or refuses with an empty stack; it must not undo the same fillet twice  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on FreeCAD 1.1.x), which touches none of the code under test  
**And** *(visual)* the window shows the `buddy:` Undo entry and then the un-filleted body — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-06-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: `tc-12-06-edit.png` shows the toolbar `Undo` dropdown open with a first entry whose visible text begins `buddy: `, and the after PNG shows no menu or dropdown open, the model tree without a fillet row, and the pad's corners sharp again. Read the entry label off the painted dropdown in the image, not off the accessibility tree. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-06-edit.png
```
Close the document in the GUI and discard changes.

---

### TC-12-07: A GUI-side recompute agrees with the bridge

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

A GUI property-editor edit recomputes at once on FreeCAD 1.1.x, and `verify_recompute` recomputes
before it reads (`verify.py:435-437`), so neither can leave or observe a pending recompute. The
**Touched route** does: `script_exec` sets a property and does not recompute
(`script_exec.py:19-67`). `script_exec` opens no transaction, so `document_undo` does not revert it;
the document is closed without saving.

**Given** a scratch document with a padded body is open, built over MCP — verify: `mcp document_create {label:"TC1207"}`, `feature_body_create`, `sketch_create` on XY, `sketch_add_geometry` with a fully constrained 20 x 10 mm rectangle, and `feature_pad` with `length:{value:5, unit:"mm"}` each return `OK`; `mcp query_mass_properties {doc:<handle>, object:"Pad"}` returns `volume` `1000.0`  
**And** the document is clean — verify: `mcp verify_recompute {doc:<handle>}` returns `OK` with `subject.failing_objects` empty, and a snapshot shows the toolbar `Recompute` button disabled  

**When** the document is made dirty without a recompute through the Touched route  
```bash
mcp script_exec {doc:<handle>, code:"doc.getObject('Pad').Length = 8\nresult = doc.getObject('Pad').State"}
```
**And** the dirty state is captured  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-07-props.png"}' | & cua-driver call get_window_state
mcp query_screenshot {doc:<handle>}
```
**And** the recompute is run from the GUI: Edit > Recompute (`Std_Refresh`, menu text `Recompute`, `CommandDoc.cpp:1608`). The command is enabled only while the active document must recompute (`CommandDoc.cpp:1659-1662`). If the menu leaf is refused, click the `Recompute` toolbar button by `element_token` from a fresh snapshot.  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["Edit","Recompute"]}' | & cua-driver call invoke_menu
```
**And** the result is compared against the bridge  
```bash
mcp verify_recompute {doc:<handle>}
mcp document_recompute {doc:<handle>}
mcp query_mass_properties {doc:<handle>, object:"Pad"}
```

**Then** the property was set without a recompute — verify: the `script_exec` result `value_repr` is `['Touched']`  
**And** the bridge sees the dirty state without recomputing it — verify: the `query_screenshot` result has `render.dirty_document: true` and its text contains `Document dirty (pending/broken recompute)`  
**And** the GUI shows the same dirty state — verify: `tc-12-07-props.png` shows the 3D view still drawing the old pad, and the snapshot taken with it lists `Button "Recompute"` with `enabled: true`. Where the `Body` row is already expanded, the `Pad` row also carries the touched marker; a UIA click on a tree row does not expand it on FreeCAD 1.1.4  
**And** the GUI recompute cleaned it — verify: the post-refresh `verify_recompute` returns `OK` with `subject.failing_objects` empty  
**And** a following bridge recompute is a no-op — verify: `document_recompute` returns `OK` with `touched: 0` and `errors: []`, and does not change the geometry  
**And** the geometry reflects the new value — verify: the post-refresh `query_mass_properties` returns `volume` `1600.0` (20 x 10 x 8)  
**And** both sides agree on the final state — verify: `mcp verify_recompute` and a `cua-driver` viewport grab both show a fully rebuilt, error-free model. The grab is the evidence; the `verify_recompute` answer is the claim being checked against it.  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on FreeCAD 1.1.x), which touches none of the code under test  
**And** *(visual)* the window shows the rebuilt model at the new 8 mm value — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-07-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: `tc-12-07-props.png` shows the touched marker on the `Pad` row, and the after PNG shows no tree row with the touched or error marker, the `Recompute` toolbar button disabled again, and a solid visibly taller than the 5 mm plate. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-07-props.png
mcp document_close {doc:<handle>}
```
Do not save. `document_undo` does not revert a `script_exec` change.

---

### TC-12-08: GUI Save writes the document and the bridge sees it

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

File > Save on a document that was never saved opens the modal Save As dialog, and a modal dialog
is never opened through `invoke_menu`. So the document is saved once over MCP first: it then has a
file name, and the GUI Save writes to it with no dialog.

**Given** a document created in the GUI holds one Part cube — verify: `invoke_menu ["File","New Document"]` (or the `New Document` toolbar button), then the Part workbench and `invoke_menu ["Part","Primitives","Cube"]`; `mcp document_list {}` returns its handle and `mcp query_tree_summary {doc:<handle>}` names `Cube`  
**And** the document was saved once over MCP, so it has a file name — verify: `mcp document_save {doc:<handle>, path:"$RUN_DIR/evidence/tc-12-08-bracket.FCStd"}` returns `OK` and `Test-Path $RUN_DIR/evidence/tc-12-08-bracket.FCStd` returns `True`  
**And** the target directory is writable — verify: `Test-Path $RUN_DIR/evidence` returns `True`  

**When** the document is modified in the GUI: a second cube is added through the same menu, so the title bar gains the modified marker  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["Part","Primitives","Cube"]}' | & cua-driver call invoke_menu
'{"pid":<PID>}' | & cua-driver call list_windows
```
**And** the pre-save state is recorded  
```bash
mcp document_list {}
(Get-Item $RUN_DIR/evidence/tc-12-08-bracket.FCStd).LastWriteTime
```
**And** the document is saved from the GUI. It already has a file name, so no dialog opens. If the menu leaf is refused, click the `Save` toolbar button by `element_token`.  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["File","Save"]}' | & cua-driver call invoke_menu
'{"pid":<PID>}' | & cua-driver call list_windows
```
**And** the bridge is read  
```bash
mcp document_list {}
mcp query_tree_summary {doc:<handle>}
```
**And** the document is closed and reopened from the saved file over MCP  
```bash
mcp document_close {doc:<handle>}
mcp document_open {path:"$RUN_DIR/evidence/tc-12-08-bracket.FCStd"}
mcp query_tree_summary {doc:<handleReopened>}
mcp query_mass_properties {doc:<handleReopened>, object:"Cube001"}
```

**Then** the GUI Save wrote the file — verify: `(Get-Item $RUN_DIR/evidence/tc-12-08-bracket.FCStd).LastWriteTime` after the save is later than the pre-save value  
**And** no dialog opened — verify: the `list_windows` after the save returns only the main window  
**And** the title bar dropped the modified marker — verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns a window title that names `tc-12-08-bracket` with no `*` marker, where the pre-save title had one  
**And** the bridge identifies the saved document — verify: the post-save `document_list` entry has the same `doc` handle and the `label` `tc-12-08-bracket` (the file stem; `document_list` carries no path)  
**And** the handle stayed valid across the save — verify: the post-save `query_tree_summary` on `<handle>` returns `OK` and names `Cube` and `Cube001`, so a GUI Save does not invalidate an existing bridge handle  
**And** the saved file holds the GUI change — verify: the reopened `query_tree_summary` names `Cube` and `Cube001`, and `query_mass_properties` on `Cube001` returns `volume` `1000.0`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handleReopened>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on FreeCAD 1.1.x), which touches none of the code under test  
**And** *(visual)* the window shows the reopened saved document — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-08-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state what is on screen: no dialog is open, the title bar reads `tc-12-08-bracket` with no modification marker, and the model tree lists `Cube` and `Cube001`. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

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

This scenario raises a modal dialog on purpose, which runs a nested Qt event loop on the main
thread. That is the behaviour under test. The dialog is never opened through `invoke_menu` or a
UIA click: those calls block until the dialog closes and leave the UIA provider busy
(`freecad-gui-e2e-harness.md` §3). Instead `script_exec` schedules the command on a zero-delay Qt
timer, so the call returns before the dialog opens. Keep the dialog up only as long as the timed
read needs, and dismiss it with Cancel so no preference is changed. Do not open any further
dialog inside this scenario.

**Given** a document is open — verify: `mcp document_list {}` returns a handle  
**And** no modal dialog is currently up — verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns only the main window, whose title ends `FreeCAD <live version>`  

**When** the modal Preferences dialog is opened from inside FreeCAD on a zero-delay timer  
```bash
mcp script_exec {doc:<handle>, code:"from PySide import QtCore\nimport FreeCADGui\nQtCore.QTimer.singleShot(0, lambda: FreeCADGui.runCommand('Std_DlgPreferences'))\nresult = 'scheduled'"}
'{"pid":<PID>}' | & cua-driver call list_windows
```
**And** a read is issued over MCP while the dialog is up, and timed  
```bash
Measure-Command { mcp query_tree_summary {doc:<handle>} }
```
`query_tree_summary` carries a 30 s budget.
**And** the dialog window is captured while it is still up. If `get_window_state` on the dialog reports the UIA provider unresponsive, capture it with `get_desktop_state` instead.  
```bash
'{"pid":<PID>,"window_id":<DIALOG_WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-09-dialog.png"}' | & cua-driver call get_window_state
```
**And** the dialog is dismissed through its Cancel button, using the `element_token` from that snapshot. If the dialog's UIA tree cannot be read, dismiss it from inside FreeCAD instead: `reject()` is the Cancel action.  
```bash
'{"pid":<PID>,"element_token":"<Cancel button token from this snapshot>"}' | & cua-driver call click
```
```bash
mcp script_exec {doc:<handle>, code:"from PySide import QtWidgets\nw = QtWidgets.QApplication.activeModalWidget()\nresult = w.windowTitle() if w else None\nif w: w.reject()"}
```
**And** MCP is re-read after the dialog is gone  
```bash
mcp query_tree_summary {doc:<handle>}
mcp query_capabilities {}
```

**Then** the dialog is up and modal — verify: the `list_windows` call taken after the `script_exec` returns a second window for the same pid, titled `Preferences`  
**And** the opening call did not wait on the dialog — verify: the scheduling `script_exec` returned `OK` with `value_repr` `'scheduled'` before the dialog opened  
**And** the concurrent call either waits or times out within its budget — verify: the timed `query_tree_summary` either returns `OK` or returns a timeout status; it must resolve within about 30 s and must not hang unbounded  
**And** the client is told which happened — verify: on timeout the response carries a status the client can branch on, not a dropped connection  
**And** the dialog dismissal landed — verify: `'{"pid":<PID>}' | & cua-driver call list_windows` after the Cancel returns only the main window, and the route used (Cancel button or `reject()`) is recorded  
**And** the listener survived — verify: the post-dialog `query_capabilities` returns `OK`, so the blocked call did not tear down the in-process listener  
**And** the document is intact — verify: the post-dialog `query_tree_summary` returns the same object list as before the dialog, with no object lost or duplicated  
**And** the proxy is still listening — verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` still returns a row  
**And** *(visual)* the dialog really was up, modal, and then gone — verify: `Read "$RUN_DIR/evidence/tc-12-09-dialog.png"` and state what is on screen: a FreeCAD Preferences dialog painted as a separate window, its title readable, with its Cancel button visible. Then `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-09-after.png"}' | & cua-driver call get_window_state` and `Read` that PNG to confirm no dialog is painted over the main window and the main window is interactive again. A dialog present in the accessibility tree is not enough; it must be painted in the image. No auto-fit is issued before the dialog capture: the GUI `Fit All` button is unreachable behind a modal dialog, and a fit is not the subject here. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-09-dialog.png
```
Confirm the dialog was dismissed with Cancel (or `reject()`), so no preference changed.

---

### TC-12-10: Switching workbench does not disturb bridge handles

**Priority**: Medium
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Given** two golden documents are open, A = `box-10-20-30` and B = `sphere-r10` — verify: `mcp document_open` on each returns a handle; `mcp document_list {}` returns two entries  
**And** both the `Sketch` and `Part Design` menus are present — verify: `get_window_state` lists both at menu depth 2  

**When** both handles are recorded and each one is read  
```bash
mcp document_list {}
mcp query_mass_properties {doc:<handleA>, object:"Box"}
mcp query_mass_properties {doc:<handleB>, object:"Sphere"}
```
**And** the workbench is switched in the GUI through the workbench selector. `set_value` on the combo box does not change it on FreeCAD 1.1.x: click the combo box, re-snapshot, then click the `Sketcher` list item, each by `element_token`.  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-10-wb.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<workbench ComboBox token from this snapshot>"}' | & cua-driver call click
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Sketcher list item token from THIS snapshot>"}' | & cua-driver call click
```
**And** both handles are re-read, then the workbench is switched to Part Design the same way and both are read again  
```bash
mcp query_mass_properties {doc:<handleA>, object:"Box"}
mcp query_mass_properties {doc:<handleB>, object:"Sphere"}
```

**Then** the workbench changed — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"role":"ComboBox","label_contains":"Sketcher"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`; `unknown` is inconclusive  
**And** both handles still resolve — verify: both post-switch calls return `OK`, not `INVALID_INPUT`  
**And** the geometry is unchanged — verify: both post-switch volumes equal their pre-switch values exactly  
**And** no handle was remapped — verify: `mcp document_list {}` after the switch returns the same two handle strings as the pre-switch list  
**And** the switch back is equally harmless — verify: after switching to Part Design, both handles still read the same values  
**And** the listener is unaffected — verify: `mcp query_capabilities {}` returns `OK` with the same `render` mode after both switches  
**And** *(visual)* the model is framed — verify: with document A's tab active, run Show All, then `mcp view_fit_viewport { doc: "<handleA>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on FreeCAD 1.1.x), which touches none of the code under test  
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
**And** `max_nodes` is not a parameter — verify: `mcp query_tree_summary {doc:<handle>, max_nodes:10}` is refused: `Input validation error: Additional properties are not allowed ('max_nodes' was unexpected)` (schema refusal) or `INVALID_INPUT`; the input is refused either way. The schema sets `additionalProperties: false` and `max_nodes` is retired  
**And** each call stays within its budget — verify: every `query_tree_summary` call in this scenario returns within its 30 s timeout  
**And** the GUI stays responsive — verify: a `get_window_state` taken after the queries still returns a populated tree, not `degraded`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on FreeCAD 1.1.x), which touches none of the code under test  
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

No MCP-only route makes a document whose recompute takes several seconds: `document_recompute`
recomputes only touched objects. The long GUI operation is therefore the open of a heavy model:
FreeCAD's bundled `ArchDetail.FCStd` example (435 objects; its open kept the main thread busy for
about 6 s in run `2026-10-03-04`). The open uses the non-modal Start page route.

**Given** the heavy model is listed on the FreeCAD Start page — verify: a snapshot of the Start page lists a card or Recent Files entry for `ArchDetail.FCStd`; record its `element_token` and its pixel position  
**And** the proxy is listening — verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row  
**And** a timed MCP poller is ready to run beside the GUI action — verify: a loop that calls `mcp query_capabilities {}` every 0.5 s and records each call's duration and status runs in its own shell  

**When** the poller is started, then the long operation is started from the GUI: double-click the `ArchDetail.FCStd` card. A UIA click on the card token may not open it; a background window-targeted double-click at its pixel position does.  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"x":<card x>,"y":<card y>,"count":2}' | & cua-driver call click
```
**And** a viewport grab is taken while the open runs  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-12-busy.png"}' | & cua-driver call get_window_state
```
**And** the poller is stopped and the bridge is read again after the operation finishes  
```bash
mcp document_list {}
mcp query_tree_summary {doc:<handle>}
mcp verify_recompute {doc:<handle>}
```

**Then** the main thread was busy for the operation's duration — verify: the poller calls that overlapped the open each took longer than the idle calls (about 0.01 s), and `$RUN_DIR/evidence/tc-12-12-busy.png` shows a stale or unpainted viewport. This is documented and accepted behavior: FreeCAD loads and recomputes on the Qt main thread. A `cua-driver` call to the window waits for the busy main thread, so the busy grab can return only after the open ends; then record that, and judge the freeze from the poller durations alone  
**And** the bridge does not drop the connection — verify: every poller `query_capabilities` call returns `OK` or a timeout status, never a transport-level disconnect  
**And** the proxy stays listening throughout — verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row during and after the operation  
**And** post-operation reads succeed — verify: `document_list` names `ArchDetail`, and the `query_tree_summary` and `verify_recompute` calls on its handle return `OK`  
**And** the model is complete — verify: the post-operation `verify_recompute` returns `OK` with `subject.failing_objects` empty  
**And** the GUI recovers — verify: a `get_window_state` after the operation returns a populated tree and a freshly painted viewport, not `degraded`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on FreeCAD 1.1.x), which touches none of the code under test. `ArchDetail.FCStd` opens a TechDraw page as the active view: activate the document's 3D view tab first, because a fit needs a 3D view. Issue this fit only after the long operation has finished; a fit during the freeze cannot land.  
**And** *(visual)* the frozen viewport recovered into a painted one — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-12-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen: the busy PNG shows a stale, blank, or white-washed 3D view during the open (or, when the grab waited, the loaded page; record which), and the after PNG shows the model freshly painted and framed in a responsive, non-greyed main window. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-12-busy.png
mcp document_close {doc:<handle>}
```
Do not save the example file.

---

### TC-12-13: Closing a document in the GUI invalidates its handle cleanly

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Given** two golden documents are open, A = `box-10-20-30` and B = `cylinder-r5-h20` — verify: `mcp document_open` on each returns a handle; `mcp document_list {}` returns two entries  
**And** both handles read successfully — verify: `mcp query_tree_summary {doc:<handleA>}` and the same for `<handleB>` both return `OK`  

**When** both handles are recorded  
```bash
mcp document_list {}
```
**And** document A is closed in the GUI. To make document A the active document, activate it through its numbered `Windows` menu entry. The entries read `<n> <label> : 1`, with `1 Start` first; take `<n>` from the order of the document tabs. A UIA or pixel click on the root tree row does not change the active document on FreeCAD 1.1.4. Confirm from the `list_windows` title that document A is active, then invoke `File > Close`, which closes the active document.  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-13-tree.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"path":["Windows","<n> box-10-20-30 : 1"]}' | & cua-driver call invoke_menu
'{"pid":<PID>}' | & cua-driver call list_windows
'{"pid":<PID>,"window_id":<WID>,"path":["File","Close"]}' | & cua-driver call invoke_menu
```
Document A must have no `*` modified marker before the close: `File > Close` on a modified
document opens a modal save prompt, and the `invoke_menu` call then blocks until it closes. Do not
run Show All on document A before the close.
**And** the stale handle is used  
```bash
mcp query_tree_summary {doc:<handleA>}
mcp query_mass_properties {doc:<handleA>, object:"Box"}
mcp query_screenshot {doc:<handleA>}
mcp document_close {doc:<handleA>}
```
Issue these stale calls before any `document_list`: they must refuse on their own, not because a
list call pruned the handle first.
**And** document B is confirmed unharmed  
```bash
mcp document_list {}
mcp query_mass_properties {doc:<handleB>, object:"Cylinder"}
```

**Then** the GUI closed it — verify: a fresh snapshot's `TreeItem` set has no row labelled `box-10-20-30`, and `tc-12-13-after.png` (below) shows no such row. `verify_state` with `exists:false` is refused by the driver (snapshots are not exhaustive), so the PNG is the judgement  
**And** every stale read returns INVALID_INPUT — verify: all three stale read calls return `INVALID_INPUT`, not `WORKER_CRASHED` and not `OK` with empty data  
**And** the stale close is also a clean refusal — verify: `document_close` on the stale handle returns `INVALID_INPUT`, not a crash  
**And** no crash and no hang — verify: FreeCAD is still running (`Get-Process -Name freecad` returns the same pid) and each stale call returned within its own timeout  
**And** the list no longer names document A — verify: the final `document_list` returns one entry, and its handle is `<handleB>`  
**And** document B still works — verify: the final `query_mass_properties` on `<handleB>` returns `OK` with its original volume  
**And** the listener is intact — verify: `mcp query_capabilities {}` returns `OK`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handleB>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead by invoking the **`Fit All` toolbar button** through its `element_token` from a fresh `get_window_state` (`View → Fit All` is the menu equivalent but is refused on FreeCAD 1.1.x), which touches none of the code under test  
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
**And** *(visual)* the window that existed is gone, and the restarted one is back — verify: `'{"pid":<PID>}' | & cua-driver call list_windows` after the quit returns no FreeCAD window, then after the restart `'{"pid":<NEW_PID>,"window_id":<NEW_WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-14-after.png"}' | & cua-driver call get_window_state`; `Read` both PNGs and state what is on screen: the before PNG shows a live FreeCAD main window titled with the live version, with its menu bar and painted workspace, and the after PNG shows a freshly started FreeCAD window titled with the live version, with its start page and no crash or recovery dialog. No auto-fit is issued by either route: the target process does not exist between the quit and the restart, and the restarted instance holds no document, so the `Fit All` toolbar button is absent from the UIA tree. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

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
**And** a long MCP call is started, then FreeCAD is killed mid-call. **This scenario is the explicit unclean-kill case, so a forced termination is intentional here and ONLY here.** The kill runs from the agent shell, which is at FreeCAD's integrity level (the `cua-driver` daemon was started from it, `freecad-gui-e2e-harness.md` §2). `cua-driver kill_app` is refused for FreeCAD, and a `Stop-Process` from a shell at a lower integrity level returns `Access is denied`. A scratch document recomputes too fast to be in flight at the kill, so the long call is an MCP open of a heavy model (FreeCAD's bundled `ArchDetail.FCStd`, about 5 s).  
```bash
mcp document_open {path:"<FreeCAD install>/data/examples/ArchDetail.FCStd"}   # issue this, then about 1.5 s later run the kill below
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

**Then** the in-flight call surfaces a crash to the client — verify: the `document_open` issued before the kill returns `WORKER_CRASHED`, or fails at the transport with a connection error. It must NOT return `OK`.  
**And** the client does not hang — verify: that same call resolves within its 60 s budget; an unbounded wait is a defect  
**And** FreeCAD is gone — verify: the post-kill `Get-Process -Name freecad` returns nothing  
**And** no half-open bridge remains — verify: the post-kill `netstat` returns no LISTENING row for `:8765` that still accepts connections; a socket that accepts but never answers is a defect  
**And** a following call fails fast — verify: the post-kill `query_capabilities` fails at the transport and returns promptly  
**And** no orphan proxy — verify: within 5 s of the kill, the proxy pid recorded before the kill (the `LISTENING` pid on `:8765`) is no longer in `Get-Process`, and `Select-String "has exited; the MCP proxy exits" "$env:APPDATA\FreeCAD\v1-1\freecad-buddy\mcp-proxy.log"` returns one line. Read the log before the restart: the new proxy rewrites it. If the proxy survives, record the orphan pid as a defect and stop it manually before continuing.  
**And** restart recovers fully — verify: reopening FreeCAD re-serves `:8765`, recreates the discovery file, and `mcp query_capabilities {}` returns `OK`  
**And** the restarted FreeCAD has its own proxy — verify: `Invoke-RestMethod http://127.0.0.1:8765/healthz` returns `freecad_pid` equal to the new FreeCAD pid, and the `LISTENING` pid on `:8765` differs from the pre-kill proxy pid  
**And** no stale snapshot or temp file blocks restart — verify: the restarted addon's `addon.log` has one `session-start sweep removed N leftover temp artifact(s)` line, and `<workdir>/tmp` (`%APPDATA%\FreeCAD\v1-1\freecad-buddy\workdir\tmp`) holds no `FCB_TMP_session_<killed pid>_*` folder: the sweep removes a session folder whose pid is dead. List it in-process with `script_exec` if the shell gets "Access is denied". The restarted host must still serve normally  
**And** *(visual)* the killed window is gone and the restarted one comes back clean — verify: `'{"pid":<PID>}' | & cua-driver call list_windows` after the kill returns no FreeCAD window, then after the restart `'{"pid":<NEW_PID>,"window_id":<NEW_WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-12-15-after.png"}' | & cua-driver call get_window_state`; `Read` both PNGs and state what is on screen: the before PNG shows a live main window with the scratch document painted in its 3D view, and the after PNG shows a freshly started FreeCAD window titled with the live version. Record whether a document-recovery prompt is painted in the after PNG: it is expected after an unclean kill, and it must be dismissed rather than left blocking the channel. No auto-fit is issued by either route: the target process was killed and the restarted instance holds no document, so the `Fit All` toolbar button is absent from the UIA tree. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f $RUN_DIR/evidence/tc-12-15-before.png
```
Reopen FreeCAD. Its session-start sweep removes the killed session's temp folder; no manual
removal is needed. Delete the killed pid's stale `rpc-<pid>.json` discovery file if it is still
present.
