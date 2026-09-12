# TC-12: GUI Workflows Observed Through the Bridge

Drives real user workflows through the FreeCAD 1.1.1 GUI with `cua-driver`, then asserts over MCP
that the bridge observes the same state the user sees. This is the maximal-GUI file: the GUI is the
actor and MCP is the observer, which is the opposite direction from every other TC file. It proves
the addon's in-process listener reads the live application rather than a private copy of it, and
that handles, visibility, undo labels, and teardown all survive being driven from the GUI side.

## Prerequisites
- [ ] FreeCAD 1.1.1 GUI is open (verify: `Get-Process -Name freecad | Select-Object Id,MainWindowTitle` lists one process with title `FreeCAD 1.1.1`). Find the process by NAME; a `*FreeCAD*` title regex also matches VS Code.
- [ ] The MCP proxy serves `:8765` — the addon auto-spawns it on FreeCAD start (verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row)
- [ ] `cua-driver` runs in the interactive user session (verify: `cua-driver status` reports the daemon and NOT Session 0; Session 0 has no desktop, so UIA enumeration and `PrintWindow` fail there)
- [ ] The FreeCAD `(pid, window_id)` pair is known (verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns the window whose `title` is `FreeCAD 1.1.1`)
- [ ] The menu bar is exposed (verify: `'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state` lists MenuBar children `File Edit View Tools Macro Sketch "Part Design" Windows Help`)

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

**Preconditions**:
- [ ] No document is open (verify: `mcp document_list {}` returns an empty list)
- [ ] The Part Design and Sketch menus are present (verify: `get_window_state` lists `Sketch` and `Part Design` at menu depth 2)

**Steps**:
1. Create the document and a body through the GUI. Re-snapshot before each menu hop.
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["File","New"]}' | & cua-driver call invoke_menu
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["Part Design"]}' | & cua-driver call invoke_menu
   ```
   The body-creation leaf under `Part Design` is resolved at runtime by `invoke_menu`.
2. Start a new sketch on the XY plane through the `Sketch` menu, draw a closed 60 x 40 mm profile,
   and constrain it fully. Re-snapshot before every action and act through `element_token`.
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1201_sketch.png"}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["Sketch"]}' | & cua-driver call invoke_menu
   ```
3. Close the sketch, then pad it 5 mm through the `Part Design` menu. Enter `5` in the Length field
   with `type_text` bound to the field's `element_token`, then commit.
4. Add a pocket for an M5 clearance hole pair 40 mm apart, then fillet the outer corners at 3 mm,
   each through the `Part Design` menu with the same snapshot-act-verify loop.
5. Assert the result over MCP:
   ```bash
   mcp document_list {}
   mcp query_tree_summary {doc:<handle>, depth:3}
   mcp query_mass_properties {doc:<handle>}
   mcp verify_shape {doc:<handle>}
   ```

**Checkpoints**:
- [ ] CP1: The GUI actions landed — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"Pad"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`; `unknown` is inconclusive, not a pass
- [ ] CP2: The bridge sees the document — verify: `mcp document_list {}` returns exactly one handle
- [ ] CP3: The bridge sees the same feature chain — verify: `mcp query_tree_summary {doc:<handle>, depth:3}` lists the Body, the sketch, the pad, the pocket, and the fillet in that dependency order
- [ ] CP4: The geometry agrees with the design intent — verify: `mcp query_mass_properties {doc:<handle>}` returns a `bbox` of 60 x 40 x 5 mm within the fillet's corner allowance
- [ ] CP5: The solid is valid — verify: `mcp verify_shape {doc:<handle>}` reports a valid, closed, single solid
- [ ] CP6: The hole spacing is real — verify: the two pocket cylinders are 40 mm apart, read from `mcp query_placement {doc:<handle>}` or from the sketch datum in `mcp query_sketch_info {doc:<handle>, sketch:"<Sketch>"}`
- [ ] CP7: The recompute is clean after GUI editing — verify: `mcp verify_recompute {doc:<handle>}` reports no touched, invalid, or error object
- [ ] CP8: The MCP render matches the viewport — verify: `mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}` produces an image whose silhouette matches a `PrintWindow` viewport grab of the same isometric view

**Cleanup**:
```bash
rm -f _automation/tc1201_*.png
```
Close the document in the GUI with `invoke_menu ["File","Close"]` and discard changes.

---

### TC-12-02: A GUI-created document is visible to document_list

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Preconditions**:
- [ ] No document is open (verify: `mcp document_list {}` returns an empty list)

**Steps**:
1. Record the empty state:
   ```bash
   mcp document_list {}
   ```
2. Create a document through the GUI:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["File","New"]}' | & cua-driver call invoke_menu
   ```
3. Read the bridge's view:
   ```bash
   mcp document_list {}
   ```
4. Use the returned handle for a read:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   ```

**Checkpoints**:
- [ ] CP1: The GUI created the document — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"Unnamed"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`
- [ ] CP2: The bridge sees exactly one document — verify: step 3 `mcp document_list {}` returns one entry where step 1 returned none
- [ ] CP3: A handle was minted — verify: the entry carries a non-empty `handle` string
- [ ] CP4: The handle works for reads — verify: step 4 returns `OK` with an empty object list for the new document
- [ ] CP5: The label matches the GUI — verify: the entry's `label` equals the document name shown in the FreeCAD title bar and model tree
- [ ] CP6: The transient flag is honest — verify: the entry's `transient` flag reflects that the document has never been saved

**Cleanup**:
```bash
mcp document_close {doc:<handle>}
```

---

### TC-12-03: A GUI-opened golden model is seen with correct geometry

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Preconditions**:
- [ ] No document is open (verify: `mcp document_list {}` returns an empty list)
- [ ] The golden model exists (verify: `Test-Path benchmarks/g0/golden-models/box-10-20-30.FCStd` returns `True`)

**Steps**:
1. Open the golden model through the GUI file dialog:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["File","Open"]}' | & cua-driver call invoke_menu
   ```
   The dialog is a separate window. Enumerate it with `list_windows`, snapshot it with
   `get_window_state`, type the absolute path into the file-name field through its
   `element_token`, and commit with `press_key` bound to that same element.
2. Read the bridge's view:
   ```bash
   mcp document_list {}
   mcp query_tree_summary {doc:<handle>}
   mcp query_mass_properties {doc:<handle>}
   mcp verify_shape {doc:<handle>}
   ```

**Checkpoints**:
- [ ] CP1: The GUI opened it — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"box-10-20-30"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`
- [ ] CP2: The bridge sees it — verify: `mcp document_list {}` returns one entry whose `label` contains `box-10-20-30`
- [ ] CP3: The object is present — verify: `mcp query_tree_summary {doc:<handle>}` names the `Box` object
- [ ] CP4: The geometry is exact — verify: `mcp query_mass_properties {doc:<handle>}` returns `volume` equal to `6000.0` mm3
- [ ] CP5: The shape is valid — verify: `mcp verify_shape {doc:<handle>}` reports a valid single closed solid
- [ ] CP6: The file path is reported — verify: the `document_list` entry names the file it was opened from and its `transient` flag is false

**Cleanup**:
```bash
mcp document_close {doc:<handle>}
```

---

### TC-12-04: GUI tree selection does not change what a doc handle targets

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Preconditions**:
- [ ] Two documents are open (verify: `mcp document_open {path:"D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"}` and `mcp document_open {path:"D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/sphere-r10.FCStd"}` each return a handle; `mcp document_list {}` returns two entries)

**Steps**:
1. Record both handles and their volumes:
   ```bash
   mcp query_mass_properties {doc:<handleBox>}
   mcp query_mass_properties {doc:<handleSphere>}
   ```
2. Select the SPHERE document in the GUI model tree. Re-snapshot, then click its tree row through
   the token from that snapshot:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1204_tree.png"}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<sphere row token from this snapshot>"}' | & cua-driver call click
   ```
3. Query the BOX handle while the sphere is the GUI's active document:
   ```bash
   mcp query_mass_properties {doc:<handleBox>}
   mcp query_tree_summary {doc:<handleBox>}
   mcp query_screenshot {doc:<handleBox>, view:{camera:"iso"}}
   ```
4. Select the BOX document in the GUI, then query the SPHERE handle the same way.

**Checkpoints**:
- [ ] CP1: The GUI selection changed — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"sphere-r10"},"selected":true}}]}' | & cua-driver call verify_state` returns `satisfied`
- [ ] CP2: The box handle still returns box geometry — verify: step 3 `volume` equals `6000.0` mm3, NOT `4188.7902`
- [ ] CP3: The box handle's tree is the box's — verify: step 3 `query_tree_summary` names `Box` and not the sphere object
- [ ] CP4: The render follows the handle, not the selection — verify: step 3 `query_screenshot` returns `scene.rendered_objects` containing the box object only
- [ ] CP5: The reverse direction holds — verify: after step 4, `mcp query_mass_properties {doc:<handleSphere>}` returns `4188.7902` mm3
- [ ] CP6: No tool silently used the active document — verify: no response in steps 3 or 4 names an object belonging to the other document

**Cleanup**:
```bash
rm -f _automation/tc1204_*.png
```
```bash
mcp document_close {doc:<handleBox>}
mcp document_close {doc:<handleSphere>}
```

---

### TC-12-05: A GUI Visibility toggle is observed by query_tree_summary

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Preconditions**:
- [ ] A document with two visible shape-bearing objects is open (verify: `mcp query_tree_summary {doc:<handle>}` reports `visibility` true for both)

**Steps**:
1. Record the visible set:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   mcp query_tree_summary {doc:<handle>, filters:{visible_only:true}}
   ```
2. Hide `<ObjectB>` in the GUI. Re-snapshot, select its tree row by `element_token`, then toggle
   visibility through the `View` menu; the leaf label is resolved at runtime by `invoke_menu`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1205_tree.png"}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<ObjectB row token from this snapshot>"}' | & cua-driver call click
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["View","Visibility"]}' | & cua-driver call invoke_menu
   ```
3. Re-read the bridge:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   mcp query_tree_summary {doc:<handle>, filters:{visible_only:true}}
   ```
4. Restore visibility by repeating step 2 and re-read.

**Checkpoints**:
- [ ] CP1: The object vanished from the viewport — verify: a `PrintWindow` viewport grab after step 2 no longer shows `<ObjectB>`
- [ ] CP2: The bridge reports the new flag — verify: step 3 first call returns `visibility` false for `<ObjectB>` and true for `<ObjectA>`
- [ ] CP3: The `visible_only` filter drops it — verify: step 3 second call returns `<ObjectA>` only, where step 1 second call returned both
- [ ] CP4: No geometry changed — verify: `mcp query_mass_properties {doc:<handle>}` returns the same volume before and after the toggle; visibility is a view flag, not geometry
- [ ] CP5: Restoring works both ways — verify: after step 4, `visibility` is true again for `<ObjectB>` and `visible_only` returns both objects
- [ ] CP6: The bridge read the live flag, not a cache — verify: the step-3 result differs from the step-1 result without any MCP mutation call in between

**Cleanup**:
```bash
rm -f _automation/tc1205_*.png
```
Restore `<ObjectB>` visibility before leaving the scenario.

---

### TC-12-06: GUI Undo shows the bridge's transaction label

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Preconditions**:
- [ ] A document with a padded body is open (verify: `mcp query_tree_summary {doc:<handle>}` names a pad feature)
- [ ] The undo stack state is recorded before the mutation (verify: `get_window_state` after opening the `Edit` menu shows the current Undo entry label)

**Steps**:
1. Run one mutation over MCP so the bridge opens its own transaction:
   ```bash
   mcp preview_dry_run {doc:<handle>, tool:"feature_fillet", args:{doc:<handle>, base:"<Pad>", edges:[{kind:"geometric", object:"<Pad>", element_type:"edge", query:{}}], radius:{value:3, unit:"mm"}}}
   mcp feature_fillet {doc:<handle>, base:"<Pad>", edges:[...], radius:{value:3, unit:"mm"}, confirm:{preview_id:"<token>"}}
   ```
2. Open the `Edit` menu in the GUI and read the Undo entry's label:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["Edit"]}' | & cua-driver call invoke_menu
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1206_edit.png"}' | & cua-driver call get_window_state
   ```
3. Invoke Undo from the GUI:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["Edit","Undo"]}' | & cua-driver call invoke_menu
   ```
4. Read the result over MCP:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   mcp query_mass_properties {doc:<handle>}
   ```

**Checkpoints**:
- [ ] CP1: The Undo entry names the bridge's transaction — verify: the step-2 snapshot tree contains a MenuItem whose label begins with `buddy: `. A generic label such as `Undo` alone means the mutation did not run inside a named transaction, which is a defect.
- [ ] CP2: The label names the tool — verify: that label identifies the fillet operation, so a human reading the GUI can tell which bridge call produced it
- [ ] CP3: The undo is enabled — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"buddy:"},"enabled":true}}]}' | & cua-driver call verify_state` returns `satisfied`
- [ ] CP4: GUI Undo removes the feature — verify: step 4 `query_tree_summary` no longer names the fillet
- [ ] CP5: The geometry reverted — verify: step 4 `query_mass_properties` returns the pre-fillet volume
- [ ] CP6: The bridge and the GUI share one undo history — verify: after the GUI Undo, `mcp document_undo {doc:<handle>}` either undoes the NEXT older transaction or refuses with an empty stack; it must not undo the same fillet twice

**Cleanup**:
```bash
rm -f _automation/tc1206_*.png
```
Close the document in the GUI and discard changes.

---

### TC-12-07: A GUI-side recompute agrees with the bridge

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Preconditions**:
- [ ] A document with a feature chain is open (verify: `mcp query_tree_summary {doc:<handle>, depth:3}` lists at least a sketch and a pad)
- [ ] The document is clean (verify: `mcp verify_recompute {doc:<handle>}` reports no touched object)

**Steps**:
1. Make the document dirty from the GUI by editing a driving parameter in the property editor.
   Re-snapshot, select the feature row, then write the new value through `set_value` bound to the
   property field's `element_token`.
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1207_props.png"}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Length field token from this snapshot>","value":"8 mm"}' | & cua-driver call set_value
   ```
2. Confirm the bridge sees the pending recompute:
   ```bash
   mcp verify_recompute {doc:<handle>}
   ```
3. Recompute from the GUI. The refresh command lives under a top-level menu resolved at runtime:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["Edit","Refresh"]}' | & cua-driver call invoke_menu
   ```
4. Compare against the bridge:
   ```bash
   mcp verify_recompute {doc:<handle>}
   mcp document_recompute {doc:<handle>}
   mcp query_mass_properties {doc:<handle>}
   ```

**Checkpoints**:
- [ ] CP1: The GUI edit landed — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"8 mm"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`; `unknown` is inconclusive
- [ ] CP2: The bridge sees the dirty state — verify: step 2 `verify_recompute` reports at least one Touched object
- [ ] CP3: The GUI recompute cleaned it — verify: step 4 first call reports no touched, invalid, or error object
- [ ] CP4: A following bridge recompute is a no-op — verify: step 4 `document_recompute` reports zero recomputed objects, or reports the same clean state, and does not change the geometry
- [ ] CP5: The geometry reflects the GUI edit — verify: step 4 `query_mass_properties` returns the volume implied by the new 8 mm value
- [ ] CP6: Both sides agree on the final state — verify: `mcp verify_recompute` and a `PrintWindow` viewport grab both show a fully rebuilt, error-free model

**Cleanup**:
```bash
rm -f _automation/tc1207_*.png
```
Close the document in the GUI and discard changes.

---

### TC-12-08: GUI Save writes the document and the bridge sees the path

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Preconditions**:
- [ ] A modified document is open (verify: `mcp document_list {}` returns a handle; its `transient` flag is true for a never-saved document)
- [ ] The target directory is writable (verify: `Test-Path _automation` returns `True`)

**Steps**:
1. Record the pre-save state:
   ```bash
   mcp document_list {}
   mcp query_mass_properties {doc:<handle>}
   ```
2. Save from the GUI:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["File","Save"]}' | & cua-driver call invoke_menu
   ```
   The Save dialog is a separate window. Enumerate it with `list_windows`, snapshot it, type
   `_automation/tc1208_bracket.FCStd` into the file-name field through its `element_token`, and
   commit with `press_key` bound to the same element.
3. Read the bridge:
   ```bash
   mcp document_list {}
   ```
4. Close and reopen from the saved file over MCP:
   ```bash
   mcp document_close {doc:<handle>}
   mcp document_open {path:"D:/Work/Personal/Sources/freecad-buddy/_automation/tc1208_bracket.FCStd"}
   mcp query_mass_properties {doc:<handleReopened>}
   ```

**Checkpoints**:
- [ ] CP1: The file exists on disk — verify: `Test-Path _automation/tc1208_bracket.FCStd` returns `True`
- [ ] CP2: The title bar dropped the modified marker — verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns a window title with no trailing modification indicator
- [ ] CP3: The bridge reports the saved path — verify: step 3 `document_list` entry names `tc1208_bracket.FCStd`
- [ ] CP4: The transient flag cleared — verify: step 3 entry `transient` is false where step 1 had it true
- [ ] CP5: The saved file round-trips — verify: step 4 `query_mass_properties` returns the same `volume` as step 1
- [ ] CP6: The handle stayed valid across the save — verify: a read on `<handle>` between steps 2 and 4 returns `OK`, so a GUI Save does not invalidate an existing bridge handle

**Cleanup**:
```bash
mcp document_close {doc:<handleReopened>}
```
```bash
rm -f _automation/tc1208_bracket.FCStd
```

---

### TC-12-09: A GUI modal dialog blocking the main thread

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Preconditions**:
- [ ] A document is open (verify: `mcp document_list {}` returns a handle)
- [ ] No modal dialog is currently up (verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns only the main `FreeCAD 1.1.1` window)

**Steps**:
1. Open a modal dialog from the GUI. The preferences dialog under `Edit` is modal and blocks the
   Qt main thread; the leaf label is resolved at runtime by `invoke_menu`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["Edit","Preferences"]}' | & cua-driver call invoke_menu
   '{"pid":<PID>}' | & cua-driver call list_windows
   ```
2. While the dialog is up, issue a read over MCP and time it:
   ```bash
   Measure-Command { mcp query_tree_summary {doc:<handle>} }
   ```
   `query_tree_summary` carries a 30 s budget.
3. Dismiss the dialog. Re-snapshot the dialog window, then invoke its Cancel button through the
   `element_token` from that snapshot:
   ```bash
   '{"pid":<PID>,"window_id":<DIALOG_WID>,"screenshot_out_file":"_automation/tc1209_dialog.png"}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Cancel button token from this snapshot>"}' | & cua-driver call click
   ```
4. Re-read over MCP after the dialog is gone:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   mcp query_capabilities {}
   ```

**Checkpoints**:
- [ ] CP1: The dialog is up and modal — verify: `list_windows` in step 1 returns a second window for the same pid
- [ ] CP2: The concurrent call either waits or times out within its budget — verify: step 2 either returns `OK` or returns a timeout status; it must resolve within about 30 s and must not hang unbounded
- [ ] CP3: The client is told which happened — verify: on timeout the response carries a status the client can branch on, not a dropped connection
- [ ] CP4: The dialog dismissal landed — verify: `'{"pid":<PID>}' | & cua-driver call list_windows` after step 3 returns only the main window
- [ ] CP5: The listener survived — verify: step 4 `query_capabilities` returns `OK`, so the blocked call did not tear down the in-process listener
- [ ] CP6: The document is intact — verify: step 4 `query_tree_summary` returns the same object list as before the dialog, with no object lost or duplicated
- [ ] CP7: The proxy is still listening — verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` still returns a row

**Cleanup**:
```bash
rm -f _automation/tc1209_*.png
```
Dismiss the dialog with Cancel so no preference is changed.

---

### TC-12-10: Switching workbench does not disturb bridge handles

**Priority**: Medium
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Preconditions**:
- [ ] Two documents are open (verify: `mcp document_list {}` returns two entries)
- [ ] Both the `Sketch` and `Part Design` menus are present (verify: `get_window_state` lists both at menu depth 2)

**Steps**:
1. Record both handles and read each one:
   ```bash
   mcp document_list {}
   mcp query_mass_properties {doc:<handleA>}
   mcp query_mass_properties {doc:<handleB>}
   ```
2. Switch workbench in the GUI through the workbench selector. Re-snapshot, then set its value
   through the combo box's `element_token`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1210_wb.png"}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<workbench selector token from this snapshot>","value":"Sketcher"}' | & cua-driver call set_value
   ```
3. Re-read both handles, then switch to Part Design and re-read again:
   ```bash
   mcp query_mass_properties {doc:<handleA>}
   mcp query_mass_properties {doc:<handleB>}
   ```

**Checkpoints**:
- [ ] CP1: The workbench changed — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"Sketcher"},"selected":true}}]}' | & cua-driver call verify_state` returns `satisfied`; `unknown` is inconclusive
- [ ] CP2: Both handles still resolve — verify: both step-3 calls return `OK`, not `INVALID_INPUT`
- [ ] CP3: The geometry is unchanged — verify: both step-3 volumes equal their step-1 values exactly
- [ ] CP4: No handle was remapped — verify: `mcp document_list {}` after the switch returns the same two handle strings as step 1
- [ ] CP5: The switch back is equally harmless — verify: after switching to Part Design, both handles still read the same values
- [ ] CP6: The listener is unaffected — verify: `mcp query_capabilities {}` returns `OK` with the same `render` mode after both switches

**Cleanup**:
```bash
rm -f _automation/tc1210_*.png
```
```bash
mcp document_close {doc:<handleA>}
mcp document_close {doc:<handleB>}
```

---

### TC-12-11: A large tree stays navigable while the summary stays bounded

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Preconditions**:
- [ ] A document with at least 50 features is open (verify: `mcp query_tree_summary {doc:<handle>, depth:3}` reports 50 or more objects). Build it by patterning a padded profile, or open an existing large model.

**Steps**:
1. Read the full tree at depth 1 and depth 3:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   mcp query_tree_summary {doc:<handle>, depth:3}
   ```
2. Read a filtered slice:
   ```bash
   mcp query_tree_summary {doc:<handle>, filters:{renderable_only:true}}
   mcp query_tree_summary {doc:<handle>, filters:{name_pattern:"Pad*"}}
   ```
3. Scroll and inspect the GUI tree. Re-snapshot before the scroll and act by `element_token`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1211_tree.png"}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Tree token from this snapshot>","direction":"down","amount":10}' | & cua-driver call scroll
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1211_tree2.png"}' | & cua-driver call get_window_state
   ```

**Checkpoints**:
- [ ] CP1: The GUI tree scrolls — verify: the two snapshot trees in step 3 expose different visible rows, so the list is navigable at this size
- [ ] CP2: The default depth stays shallow — verify: step 1 first call returns only depth-1 nodes, not all 50 features; `depth` defaults to 1
- [ ] CP3: Deeper depth returns more — verify: step 1 second call returns strictly more nodes than the first
- [ ] CP4: Filters shrink the result — verify: both step-2 calls return fewer nodes than the unfiltered depth-3 call
- [ ] CP5: `max_nodes` is not a parameter — verify: `mcp query_tree_summary {doc:<handle>, max_nodes:10}` returns `INVALID_INPUT`; the schema sets `additionalProperties: false` and `max_nodes` is retired
- [ ] CP6: Each call stays within its budget — verify: every `query_tree_summary` call in this scenario returns within its 30 s timeout
- [ ] CP7: The GUI stays responsive — verify: a `get_window_state` taken after the queries still returns a populated tree, not `degraded`

**Cleanup**:
```bash
rm -f _automation/tc1211_*.png
```
Close the document in the GUI and discard changes.

---

### TC-12-12: A long GUI operation freezes the viewport but not the bridge

**Priority**: Medium
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Preconditions**:
- [ ] A document whose recompute takes several seconds is open (verify: a prior `mcp document_recompute {doc:<handle>}` took more than 3 s)
- [ ] The proxy is listening (verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row)

**Steps**:
1. Start a long operation from the GUI:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["Edit","Refresh"]}' | & cua-driver call invoke_menu
   ```
2. While it runs, take a viewport grab and issue an MCP read:
   ```bash
   Measure-Command { mcp query_capabilities {} }
   ```
   Grab the viewport with the `PrintWindow` recipe to `_automation/tc1212_busy.png`.
3. After the operation finishes, read again:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   mcp verify_recompute {doc:<handle>}
   ```

**Checkpoints**:
- [ ] CP1: The viewport freezes for the operation's duration — verify: `_automation/tc1212_busy.png` shows a stale or unpainted viewport. This is documented and accepted behavior: FreeCAD's recompute runs on the Qt main thread.
- [ ] CP2: The bridge does not drop the connection — verify: step 2 `query_capabilities` returns `OK` or a timeout status, never a transport-level disconnect
- [ ] CP3: The proxy stays listening throughout — verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row during and after the operation
- [ ] CP4: Post-operation reads succeed — verify: both step-3 calls return `OK`
- [ ] CP5: The model is complete — verify: step 3 `verify_recompute` reports no touched, invalid, or error object
- [ ] CP6: The GUI recovers — verify: a `get_window_state` after the operation returns a populated tree and a freshly painted viewport, not `degraded`

**Cleanup**:
```bash
rm -f _automation/tc1212_*.png
```

---

### TC-12-13: Closing a document in the GUI invalidates its handle cleanly

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles)

**Preconditions**:
- [ ] Two documents are open (verify: `mcp document_list {}` returns two entries)
- [ ] Both handles read successfully (verify: `mcp query_tree_summary {doc:<handleA>}` and the same for `<handleB>` both return `OK`)

**Steps**:
1. Record both handles:
   ```bash
   mcp document_list {}
   ```
2. Close document A in the GUI. Re-snapshot, select its tree row by `element_token`, then invoke
   the close command:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1213_tree.png"}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<document A row token from this snapshot>"}' | & cua-driver call click
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["File","Close"]}' | & cua-driver call invoke_menu
   ```
   If a save prompt appears, enumerate it with `list_windows`, snapshot it, and click its discard
   button by `element_token`.
3. Use the stale handle:
   ```bash
   mcp query_tree_summary {doc:<handleA>}
   mcp query_mass_properties {doc:<handleA>}
   mcp query_screenshot {doc:<handleA>}
   mcp document_close {doc:<handleA>}
   ```
4. Confirm document B is unharmed:
   ```bash
   mcp document_list {}
   mcp query_mass_properties {doc:<handleB>}
   ```

**Checkpoints**:
- [ ] CP1: The GUI closed it — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"<document A label>"},"exists":false}}]}' | & cua-driver call verify_state` returns `satisfied`; `unknown` is inconclusive, not a pass
- [ ] CP2: Every stale read returns INVALID_INPUT — verify: all three read calls in step 3 return `INVALID_INPUT`, not `WORKER_CRASHED` and not `OK` with empty data
- [ ] CP3: The stale close is also a clean refusal — verify: `document_close` on the stale handle returns `INVALID_INPUT`, not a crash
- [ ] CP4: No crash and no hang — verify: FreeCAD is still running (`Get-Process -Name freecad` returns the same pid) and each step-3 call returned within its own timeout
- [ ] CP5: The list no longer names document A — verify: step 4 `document_list` returns one entry, and its handle is `<handleB>`
- [ ] CP6: Document B still works — verify: step 4 `query_mass_properties` on `<handleB>` returns `OK` with its original volume
- [ ] CP7: The listener is intact — verify: `mcp query_capabilities {}` returns `OK`

**Cleanup**:
```bash
rm -f _automation/tc1213_*.png
```
```bash
mcp document_close {doc:<handleB>}
```

---

### TC-12-14: Quitting FreeCAD tears down the listener and the proxy child

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Preconditions**:
- [ ] FreeCAD is running and the proxy is serving (verify: `Get-Process -Name freecad` returns a pid and `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row)
- [ ] No unsaved document is open, so the quit needs no save decision (verify: `mcp document_list {}` returns an empty list)
- [ ] The discovery file location is known (verify: `Get-ChildItem "$env:APPDATA/FreeCAD/v1-1/freecad-buddy"` lists the RPC discovery file)

**Steps**:
1. Record the live state:
   ```bash
   Get-Process -Name freecad | Select-Object Id
   netstat -ano | Select-String ":8765"
   Get-ChildItem "$env:APPDATA/FreeCAD/v1-1/freecad-buddy"
   ```
   Note the proxy pid from the `:8765` row; it is a child process, not FreeCAD's own pid.
2. Quit FreeCAD cleanly. Do NOT use `taskkill /F` here — this scenario is the clean-teardown case.
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"window_id":<WID>,"path":["File","Exit"]}' | & cua-driver call invoke_menu
   ```
   If the menu leaf does not resolve, use `'{"pid":<PID>,"keys":["alt","f4"]}' | & cua-driver call hotkey`.
3. After the process is gone, re-read the same three facts:
   ```bash
   Get-Process -Name freecad
   netstat -ano | Select-String ":8765"
   Get-ChildItem "$env:APPDATA/FreeCAD/v1-1/freecad-buddy"
   ```

**Checkpoints**:
- [ ] CP1: FreeCAD exited — verify: step 3 `Get-Process -Name freecad` returns nothing
- [ ] CP2: `:8765` stops listening — verify: step 3 `netstat` returns no LISTENING row for `:8765`
- [ ] CP3: The proxy child is gone — verify: the proxy pid recorded in step 1 is no longer in `Get-Process`; it was torn down with its parent, not orphaned
- [ ] CP4: The discovery file is deleted — verify: step 3 `Get-ChildItem` no longer lists the RPC discovery file
- [ ] CP5: A client call now fails at the transport — verify: `mcp query_capabilities {}` fails to connect to `http://127.0.0.1:8765/mcp`; it must not hang indefinitely
- [ ] CP6: The addon log records a clean shutdown — verify: `Get-Content "$env:APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log" -Tail 20` shows the teardown and no unhandled exception
- [ ] CP7: Restart is clean — verify: reopening FreeCAD recreates the discovery file, re-serves `:8765`, and `mcp query_capabilities {}` returns `OK` again

**Cleanup**:
Reopen FreeCAD so later scenarios have a live GUI. No files to remove.

---

### TC-12-15: An unclean kill surfaces WORKER_CRASHED and leaves no half-open bridge

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Preconditions**:
- [ ] FreeCAD is running with a document open (verify: `mcp document_list {}` returns a handle)
- [ ] The proxy is serving (verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row)
- [ ] Nothing unsaved is at risk. Use a scratch document only. An unclean kill loses unsaved work.

**Steps**:
1. Record the live pids:
   ```bash
   Get-Process -Name freecad | Select-Object Id
   netstat -ano | Select-String ":8765"
   ```
2. Start a long MCP call, then kill FreeCAD mid-call. **This scenario is the explicit unclean-kill
   case, so a forced termination is intentional here and ONLY here.**
   ```bash
   mcp document_recompute {doc:<handle>}   # issue this, then immediately run the kill below
   ```
   ```bash
   Stop-Process -Id <FREECAD_PID> -Force
   ```
3. Read the client's result and the surviving state:
   ```bash
   Get-Process -Name freecad
   netstat -ano | Select-String ":8765"
   mcp query_capabilities {}
   ```

**Checkpoints**:
- [ ] CP1: The in-flight call surfaces a crash to the client — verify: the step-2 `document_recompute` returns `WORKER_CRASHED`, or fails at the transport with a connection error. It must NOT return `OK`.
- [ ] CP2: The client does not hang — verify: the step-2 call resolves within its 120 s budget; an unbounded wait is a defect
- [ ] CP3: FreeCAD is gone — verify: step 3 `Get-Process -Name freecad` returns nothing
- [ ] CP4: No half-open bridge remains — verify: step 3 `netstat` returns no LISTENING row for `:8765` that still accepts connections; a socket that accepts but never answers is a defect
- [ ] CP5: A following call fails fast — verify: step 3 `query_capabilities` fails at the transport and returns promptly
- [ ] CP6: No orphan proxy — verify: the proxy pid from step 1 is no longer in `Get-Process`. If it survives, record the orphan pid as a defect and stop it manually before continuing.
- [ ] CP7: Restart recovers fully — verify: reopening FreeCAD re-serves `:8765`, recreates the discovery file, and `mcp query_capabilities {}` returns `OK`
- [ ] CP8: No stale snapshot or temp file blocks restart — verify: `Get-ChildItem $env:TEMP -Filter "FCB_TMP_*"` names only files whose transaction is known to have been in flight; the restarted host must still serve normally

**Cleanup**:
Reopen FreeCAD. Remove any `FCB_TMP_snap_*` or `FCB_TMP_shot_*` leftovers the kill orphaned:
```bash
rm -rf $env:TEMP/FCB_TMP_snap_* $env:TEMP/FCB_TMP_shot_*
```
