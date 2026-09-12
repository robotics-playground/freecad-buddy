# TC-13: GUI and MCP Parity

Proves that MCP and the FreeCAD GUI are two views of the SAME document, not two systems that
happen to agree. Three directions are graded. Direction A: what MCP reports equals what FreeCAD
shows — tree, identity, visibility, geometry, placement, render, error state. Direction B: a
mutation issued through MCP appears in the FreeCAD tree, viewport, and property panel. Direction C:
a change made by hand in the GUI is observed by MCP. A number that matches a number proves nothing
on its own, so every geometry or render scenario here also reads the pixels.

TC-12 grades GUI workflows end to end. This file grades the AGREEMENT between the two surfaces, so
some subjects overlap (visibility, recompute, close) and the assertions do not: TC-12 asks "did the
GUI action work", TC-13 asks "do both sides report the same state".

## Prerequisites
- [ ] FreeCAD 1.1.1 GUI is open (verify: `Get-Process -Name freecad | Select-Object Id,MainWindowTitle` lists one process with title `FreeCAD 1.1.1`)
- [ ] The MCP proxy serves `:8765` — the addon auto-spawns it on FreeCAD start (verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row). No manual `serve` command.
- [ ] `cua-driver` is reachable and in the interactive session (verify: `cua-driver status` reports the daemon and NOT Session 0)
- [ ] The FreeCAD `(pid, window_id)` pair is RE-RESOLVED for this run (verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns the window whose `title` is `FreeCAD 1.1.1`). Both values change between FreeCAD restarts. Never carry a `pid` or `window_id` from a previous run or a previous test file.
- [ ] The render ladder is usable (verify: `mcp query_capabilities {}` returns `render` = `gui_constructed`)

### Rule 1 — every MCP `path` argument is ABSOLUTE

A relative `path` resolves against FreeCAD's own working directory, which is
`C:\Program Files\FreeCAD 1.1\bin`, and the open fails. Write
`D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd`, never
`benchmarks/g0/golden-models/box-10-20-30.FCStd`. Shell `rm` and `ls` stay repository-relative;
only the MCP argument must be absolute.

### Rule 2 — element tokens shift between snapshots, and an adjacent token may be the RENAME EDITOR

Observed on 2026-09-12: in one snapshot token `:160` was the `BoxHole` TreeItem. After a
re-snapshot, token `:161` was the model tree's inline rename editor. A `space` keystroke sent to it
typed a space into the object's Label, and `query_tree_summary` immediately reported
`label: " "`. `Ctrl+Z` delivered with `delivery_mode:"foreground"` restored the original label.

So, in every scenario below:
- Take a fresh `get_window_state` immediately before each action.
- Select the target by BOTH `role == "TreeItem"` AND its `label`. A row index alone is not a match.
- Never reuse a token across a re-snapshot, even within one step.

### Rule 3 — `effect: "unverifiable"` is not a verdict

Both directions of the asymmetry are confirmed on this build. A tree-targeted `press_key` with
`space` returned `effect:"unverifiable"` with `escalation:{reason:"delivery_failed",
target:"foreground"}` and DID land — `query_tree_summary` flipped to `"visibility": true`. A
viewport-targeted `press_key` (camera key `0`) returned `effect:"unverifiable"` and did NOT land —
the camera was unchanged in a fresh screenshot. Never record a pass from a delivered action and
never record a failure from an `unverifiable` result. Verify the postcondition through MCP state or
a fresh screenshot, in every case.

### Rule 4 — the reliable GUI route is a toolbar button by `element_token`

Confirmed present in the UIA tree with `route: accessibility`: `Fit All` (label exactly `Fit All`),
`Fit Selection`, `Standard Views`, `Align to Selection`, `Draw Style`, `Selection Filter`,
`Tree View Actions`, `Measure`, `New Document`, `Open…`, `Save`.

**These buttons exist only while a document is open.** With no document open they are absent from
the tree. That is a precondition of the scenarios that use them, not a defect.

Confirmed UNRELIABLE or refused on this build, recorded so no scenario wastes a run on them:
- `invoke_menu(["View","Fit all"])`, `["View","Fit All"]`, and `["View","Standard views"]` are all
  REFUSED with `menu_path_unavailable` naming segment 1. Only `["View","Zoom"]` resolves.
- Qt renders an open menu as a popup that is NOT a separate top-level window. `list_windows` still
  reports only the main window and the popup's items never enter the main window's UIA tree, so
  submenu children cannot be enumerated from a snapshot.
- `press_key` with `space` on a tree row lands sometimes and not others, even with
  `delivery_mode:"foreground"`. Always confirm with `query_tree_summary`.
- `press_key` to the 3D viewport does not land, even foreground.

### Rule 5 — golden models ship hidden, and mutated fixtures close WITHOUT saving

Every golden model ships with `Visibility=false`. A default `query_screenshot` therefore returns
`{"render":{"available":true,"empty_scene":true},"scene":{"rendered_objects":[]}}` with no
`resource_link`, which is correct behavior. Every render scenario in this file passes
`view.include`. Every scenario that mutates a golden model closes it with `document_close` and
never calls `document_save`, so the committed fixture keeps its on-disk state.

### Shared viewport-capture recipe

Every scenario that compares against the live viewport uses this exact capture. It does not raise,
restack, or focus the FreeCAD window, so the user's active window stays where it is.

```powershell
# Find the process by NAME. A *FreeCAD* title regex also matches VS Code windows.
$p = Get-Process -Name freecad | Select-Object -First 1
$h = $p.MainWindowHandle
# SetThreadDpiAwarenessContext(-4) = PER_MONITOR_AWARE_V2 -> GetWindowRect returns physical pixels.
# If IsIconic($h) then ShowWindow($h, 4) = SW_SHOWNOACTIVATE. NEVER SetForegroundWindow.
# GetWindowRect -> new Bitmap(w,h) -> Graphics.GetHdc -> PrintWindow($h, $hdc, 2) -> Save($out)
# Flag 2 = PW_RENDERFULLCONTENT. Without it the OpenGL viewport saves as a black rectangle.
```

Forbidden in every scenario below: `Start-Process`, `SetForegroundWindow`, `taskkill /F`.

---

### TC-13-01: Tree parity — the MCP node set equals the GUI Model tree

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.2 (query_tree_summary), `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Preconditions**:
- [ ] `box40-hole-r5` is open (verify: `mcp document_open {path:"D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box40-hole-r5.FCStd"}` returns a handle)
- [ ] The FreeCAD Model tree is exposed in the accessibility tree (verify: `'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state` lists a `Tree` role element)

**Steps**:
1. Read the MCP node set:
   ```bash
   mcp query_tree_summary {doc:<handle>, depth:2}
   ```
   Record every node `name` and `label`.
2. Snapshot the GUI and extract the tree rows:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1301_tree.png"}' | & cua-driver call get_window_state
   ```
   From the returned elements, keep only those whose `role` is `TreeItem` and record each `label`.
3. Read the PNG from step 2 and read the model tree panel directly.

**Checkpoints**:
- [ ] CP1: The object node is present on both sides — verify: step 1 names `BoxHole` and the step-2 `TreeItem` set contains a row labelled `BoxHole`. The object in `box40-hole-r5` is named `BoxHole`, NOT `Cut`
- [ ] CP2: The document root agrees — verify: the `TreeItem` set contains a row for the document, and `mcp document_list {}` reports one entry whose label matches that row
- [ ] CP3: Node counts agree — verify: the count of shape-bearing nodes in step 1 equals the count of object rows in step 2, after excluding the document root row
- [ ] CP4: No MCP-only node — verify: every `name` reported by step 1 has a `TreeItem` row with a matching `label` in step 2
- [ ] CP5: No GUI-only node — verify: every object `TreeItem` row in step 2 appears in the step-1 output; a row with no MCP node is a parity defect, not a filter
- [ ] CP6: Visual confirmation — verify: `_automation/tc1301_tree.png` shows the same rows in the Model panel that step 2's `TreeItem` list named. Read the PNG; do not pass on the element list alone

**Cleanup**:
```bash
rm -f _automation/tc1301_*.png
```
```bash
mcp document_close {doc:<handle>}
```
Do not save. The fixture must keep its shipped state.

---

### TC-13-02: Object identity parity — name and type agree with the status bar and the property panel

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.2 (query_object), `data-contracts-design.md` §9 (error field)

**Preconditions**:
- [ ] `box40-hole-r5` is open (verify: `mcp query_tree_summary {doc:<handle>}` names `BoxHole`)
- [ ] The GUI status bar is present in the accessibility tree (verify: `'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state` lists a `StatusBar` or a bottom `Text` element)

**Steps**:
1. Read the MCP identity:
   ```bash
   mcp query_object {doc:<handle>, object:"BoxHole"}
   ```
   Record `name`, `type`, `label`, and `error`.
2. Re-snapshot, then select the `BoxHole` row by its token from THAT snapshot, matched on
   `role == "TreeItem"` and `label == "BoxHole"`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<BoxHole TreeItem token from this snapshot>"}' | & cua-driver call click
   ```
3. Re-snapshot and read the status bar text and the property panel:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1302_selected.png"}' | & cua-driver call get_window_state
   ```
   The property panel is bottom-left, Data tab, with a `Base` group holding `Placement` and `Label`
   rows.

**Checkpoints**:
- [ ] CP1: Internal name agrees — verify: step 1 `name` is `BoxHole` and the step-3 status bar reads `Valid, Internal name: BoxHole`
- [ ] CP2: The status bar also confirms validity — verify: the status bar text begins `Valid,`, and step 1 `error` is null or absent. A `Valid` status bar with a non-null MCP `error` is a parity defect
- [ ] CP3: Label agrees — verify: step 1 `label` equals the value in the property panel `Label` row and equals the `TreeItem` label used in step 2
- [ ] CP4: The type is reported — verify: step 1 `type` is a non-empty FreeCAD type string, and the object it names is the one the tree row selects
- [ ] CP5: Selection did not mutate anything — verify: `mcp query_mass_properties {doc:<handle>, object:"BoxHole"}` returns `volume` `15214.601836602547` both before and after step 2
- [ ] CP6: Visual confirmation — verify: read `_automation/tc1302_selected.png` and confirm the `BoxHole` row is highlighted, the status bar shows the internal name, and the property panel shows the same `Label`
- [ ] CP7: Face naming agrees on hover — verify: hovering a face makes the status bar read `Preselected: <doc>.BoxHole.<FaceN>`, and the object segment of that string equals step 1 `name`

**Cleanup**:
```bash
rm -f _automation/tc1302_*.png
```
```bash
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-03: Visibility parity in BOTH states

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles), `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Preconditions**:
- [ ] `box-10-20-30` is open and still hidden as shipped (verify: `mcp query_tree_summary {doc:<handle>}` reports `"visibility": false` for `Box`)

**Steps**:
1. Record the hidden state on both sides:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   mcp query_screenshot {doc:<handle>}
   ```
   Then grab the live viewport with the shared recipe to `_automation/tc1303_hidden.png`.
2. Toggle visibility in the GUI. Re-snapshot, select the `Box` row by token matched on
   `role == "TreeItem"` and `label == "Box"`, then send `space`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Box TreeItem token from this snapshot>"}' | & cua-driver call click
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Box TreeItem token from THIS snapshot>","key":"space"}' | & cua-driver call press_key
   ```
   The result is expected to report `effect:"unverifiable"`. That is not the verdict. Confirm with
   step 3. If `visibility` did not change, repeat this step once with
   `"delivery_mode":"foreground"` and confirm again.
3. Re-read both sides:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   mcp query_screenshot {doc:<handle>}
   ```
   Then grab the live viewport to `_automation/tc1303_visible.png`.

**Checkpoints**:
- [ ] CP1: Hidden agrees on both sides — verify: step 1 `query_tree_summary` reports `"visibility": false` for `Box`, AND `_automation/tc1303_hidden.png` shows an empty viewport with the tree eye icon struck through
- [ ] CP2: The hidden default render is honest — verify: step 1 `query_screenshot` returns `render.empty_scene` true, `scene.rendered_objects` `[]`, and NO `resource_link`. This is correct behavior, not a render failure
- [ ] CP3: Visible agrees on both sides — verify: step 3 `query_tree_summary` reports `"visibility": true` for `Box`, AND `_automation/tc1303_visible.png` shows the box drawn in the viewport
- [ ] CP4: The default render follows the live flag — verify: step 3 `query_screenshot` returns `scene.rendered_objects` equal to `["Box"]` with a non-null `resource_link`
- [ ] CP5: An explicit include overrides the flag in EITHER state — verify: `mcp query_screenshot {doc:<handle>, view:{include:["Box"]}}` returns `rendered_objects: ["Box"]` and a PNG while `visibility` is false
- [ ] CP6: Visual confirmation — verify: read both PNGs. `tc1303_hidden.png` shows no solid, `tc1303_visible.png` shows one box. A numeric flag flip with no pixel change is a parity defect
- [ ] CP7: The toggle changed no geometry — verify: `mcp query_mass_properties {doc:<handle>, object:"Box"}` returns `volume` `6000.0` in both states

**Cleanup**:
```bash
rm -f _automation/tc1303_*.png
```
Restore `Box` to hidden with the same toggle route, confirm with `query_tree_summary`, then:
```bash
mcp document_close {doc:<handle>}
```
Do not save. The fixture ships with `Visibility=false` and must keep it.

---

### TC-13-04: Geometry parity — mass properties agree with the drawn shape

**Priority**: Critical
**Design Ref**: `verification-design.md` §5 (measured facts), `mcp-tools-design.md` §3.3

**Preconditions**:
- [ ] `box40-hole-r5` is open (verify: `mcp query_tree_summary {doc:<handle>}` names `BoxHole`)
- [ ] The render ladder is usable (verify: `mcp query_capabilities {}` returns `render` = `gui_constructed`)

**Steps**:
1. Read the measured facts:
   ```bash
   mcp query_mass_properties {doc:<handle>, object:"BoxHole"}
   mcp verify_shape {doc:<handle>, object:"BoxHole"}
   ```
2. Render the object and copy `render.resource_link` to `_automation/tc1304_mcp.png`:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso", include:["BoxHole"]}}
   ```
3. Make the object visible in the GUI using the TC-13-03 toggle route, press the `Fit All` toolbar
   button, then grab the live viewport:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Fit All Button token from this snapshot>"}' | & cua-driver call click
   ```
   Then run the shared viewport recipe to `_automation/tc1304_viewport.png`.
4. Read both PNGs side by side.

**Checkpoints**:
- [ ] CP1: Volume matches the verified reference — verify: step 1 returns `volume` `15214.601836602547` mm3, within `rel: 0.001` of the `expected.yaml` analytic value
- [ ] CP2: Surface area matches — verify: step 1 returns `area` `4957.079632679489` mm2
- [ ] CP3: Bounding box matches — verify: step 1 returns `bbox` spanning 0 to 40 mm in x, 0 to 40 mm in y, and 0 to 10 mm in z
- [ ] CP4: Topology counts are exact — verify: step 1 returns faces `7`, edges `15`, vertices `10`, solids `1`. These carry no tolerance
- [ ] CP5: `com` is `null` and stays `null` — verify: step 1 returns `com` null for `BoxHole`; a scenario asserting a number here is wrong
- [ ] CP6: Visual confirmation of proportion — verify: read both PNGs. The object reads as a flat square plate, 40 by 40 by 10 mm, that is four times wider than it is tall. A cubic silhouette contradicts CP3 and is a defect
- [ ] CP7: The through hole is visible — verify: both PNGs show one circular hole passing through the plate, consistent with the genus-1 topology CP4 asserts. A solid plate with no hole means the numbers and the pixels disagree
- [ ] CP8: The two images depict the same solid — verify: the silhouette, hole position, and camera in `tc1304_mcp.png` match `tc1304_viewport.png`; any extra or missing body is a defect, not a tolerance

**Cleanup**:
```bash
rm -f _automation/tc1304_*.png
```
Restore `BoxHole` to hidden, confirm with `query_tree_summary`, then:
```bash
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-05: Placement parity — query_placement agrees with the property panel

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2 (query_placement), `data-contracts-design.md` §9 (Quantity)

**Preconditions**:
- [ ] `box40-hole-r5` is open (verify: `mcp query_tree_summary {doc:<handle>}` names `BoxHole`)
- [ ] The property panel is visible in the GUI (verify: a snapshot lists a `Placement` row and a `Label` row in the bottom-left Data tab)

**Steps**:
1. Read the MCP placement:
   ```bash
   mcp query_placement {doc:<handle>, object:"BoxHole"}
   ```
   Record position, axis, and angle, each with its `unit`.
2. Select the object in the GUI so the property panel populates. Re-snapshot first and match the
   row on `role == "TreeItem"` and `label == "BoxHole"`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<BoxHole TreeItem token from this snapshot>"}' | & cua-driver call click
   ```
3. Re-snapshot and read the `Base` group in the property panel:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1305_props.png"}' | & cua-driver call get_window_state
   ```
   The `Placement` row renders as `[(<axis x> <axis y> <axis z>); <angle>°; (<position>...`, for
   example `[(0.00 0.00 1.00); 0.00°; (0.0...`.

**Checkpoints**:
- [ ] CP1: The rotation axis agrees — verify: the axis vector from step 1 equals the first bracketed triple in the step-3 `Placement` row
- [ ] CP2: The angle agrees — verify: step 1 reports the angle with `unit` `deg`, and its value equals the degrees shown in the `Placement` row
- [ ] CP3: The position agrees — verify: step 1 position equals the position triple in the `Placement` row; the GUI row truncates, so read the full value by expanding the `Placement` row in the panel
- [ ] CP4: Units are typed on the wire — verify: every length in step 1 is a `{value, unit}` object with `unit` `mm`, and every angle uses `deg`. A bare number is a contract defect
- [ ] CP5: Visual confirmation — verify: read `_automation/tc1305_props.png` and confirm the `Placement` and `Label` rows are the ones the assertions above used
- [ ] CP6: Placement is consistent with the bounding box — verify: the origin reported by step 1 agrees with the `bbox` from `mcp query_mass_properties {doc:<handle>, object:"BoxHole"}`, which spans 0 to 40 mm in x and y

**Cleanup**:
```bash
rm -f _automation/tc1305_*.png
```
```bash
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-06: Render parity — the MCP render matches the live viewport

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Preconditions**:
- [ ] `box40-hole-r5` is open and `BoxHole` has been made visible (verify: `mcp query_tree_summary {doc:<handle>}` reports `"visibility": true` for `BoxHole`)
- [ ] The geometry is known (verify: `mcp query_mass_properties {doc:<handle>, object:"BoxHole"}` returns `volume` `15214.601836602547` and the 40 x 40 x 10 mm `bbox`)

**Steps**:
1. Set a shared camera through the toolbar, not a keystroke. Re-snapshot, press `Standard Views`,
   re-snapshot, then select the isometric entry by its token from the NEW snapshot:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Standard Views Button token from this snapshot>"}' | & cua-driver call click
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1306_menu.png"}' | & cua-driver call get_window_state
   ```
   `invoke_menu(["View","Standard views"])` is REFUSED on this build with `menu_path_unavailable`
   at segment 1, and a viewport `press_key` does not land. If the isometric entry does not appear
   in the snapshot, the Qt popup is not a top-level window and cannot be enumerated; in that case
   record the camera FreeCAD is actually showing and compare against the matching MCP camera
   instead of forcing iso.
2. Frame the object with the `Fit All` toolbar button:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Fit All Button token from this snapshot>"}' | & cua-driver call click
   ```
3. Capture the MCP render and copy `render.resource_link` to `_automation/tc1306_mcp.png`:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso", include:["BoxHole"]}}
   ```
4. Capture the live viewport with the shared recipe to `_automation/tc1306_viewport.png`, then read
   both PNGs side by side.

**Checkpoints**:
- [ ] CP1: The MCP render names the object — verify: step 3 returns `scene.rendered_objects` containing `BoxHole` and a non-null `render.resource_link`
- [ ] CP2: Same silhouette — verify: read both PNGs. The plate outline and the through hole appear in the same relative position in each
- [ ] CP3: Same camera — verify: the number of visible faces and the up direction agree between the two images. An axis flip is a defect, recorded exactly
- [ ] CP4: Proportions match the geometry — verify: both images read as a flat 40 x 40 x 10 mm plate, consistent with the `bbox` in the preconditions, not as a cube
- [ ] CP5: No extra or missing geometry — verify: nothing visible in `tc1306_viewport.png` is absent from `tc1306_mcp.png`, and no `PartDesign::Body`, `Sketcher::SketchObject`, or `App::Origin` child leaked into the render
- [ ] CP6: Shading is not black-sided — verify: faces angled away from the camera render as shaded grey in `tc1306_mcp.png`, matching the tone of the same faces in `tc1306_viewport.png`. Pure black means the camera-aligned headlight was lost
- [ ] CP7: The render did not touch the document — verify: `mcp query_mass_properties {doc:<handle>, object:"BoxHole"}` returns the same volume after step 3 as before it, and `mcp verify_recompute {doc:<handle>}` reports no touched object

**Cleanup**:
```bash
rm -f _automation/tc1306_*.png
```
Restore `BoxHole` to hidden, confirm with `query_tree_summary`, then:
```bash
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-07: Error-state parity — a broken object is reported by both sides

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2 (query_object), `verification-design.md` §6.3 (failing-object reporting)

**Preconditions**:
- [ ] A fixture whose object carries an error or a failing recompute is open. Use a case from `benchmarks/g0/fault-injection/`, for example `non-watertight-open-shell` (verify: `mcp document_open {path:"D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/fault-injection/non-watertight-open-shell/fixture.FCStd"}` returns a handle)
- [ ] The reference checks from the case are to hand (verify: the `assertions.checks` block in that case's `case.yaml` is read and will be passed to `verify_shape`)

**Steps**:
1. Read the MCP error surface:
   ```bash
   mcp query_object {doc:<handle>, object:"<Object>"}
   mcp verify_recompute {doc:<handle>}
   mcp verify_shape {doc:<handle>, object:"<Object>", checks:<checks from case.yaml>}
   ```
2. Snapshot the GUI Model tree and look for the tree error marker on the object row:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1307_tree.png"}' | & cua-driver call get_window_state
   ```
3. Select the object row and re-snapshot to read the status bar:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Object TreeItem token from this snapshot>"}' | & cua-driver call click
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1307_status.png"}' | & cua-driver call get_window_state
   ```

**Checkpoints**:
- [ ] CP1: MCP reports the fault — verify: step 1 `query_object` returns a non-null `error` for the object, OR `verify_recompute` names it among the failing objects
- [ ] CP2: The graded verdict uses the reference checks — verify: step 1 `verify_shape` was called WITH the `assertions.checks` from `case.yaml` and returns `SPEC_FAILED`. Called without them a wrong-but-valid shape returns `OK` and the scenario would detect nothing
- [ ] CP3: The GUI marks the same object — verify: read `_automation/tc1307_tree.png` and confirm the object row carries the FreeCAD error or touched marker
- [ ] CP4: The status bar does not claim validity — verify: `_automation/tc1307_status.png` does NOT read `Valid, Internal name: <Object>` for the broken object. A `Valid` status bar alongside a non-null MCP `error` is a parity defect and is recorded as such
- [ ] CP5: Both sides name the SAME object — verify: the object named by step 1 is the object whose row carries the marker in step 2; a mismatch is the finding
- [ ] CP6: The clean control separates detection from rejection — verify: repeat steps 1 and 2 against `benchmarks/g0/fault-injection/clean-control/fixture.FCStd`; MCP returns no error and the GUI tree shows no marker. Without this, a verifier that fails everything scores the same as a correct one

**Cleanup**:
```bash
rm -f _automation/tc1307_*.png
```
```bash
mcp document_close {doc:<handle>}
```
Do not save.

**Conditional skip**: skip when no broken fixture can be opened in the live GUI. Record the skip
with the `document_open` result that failed and the `benchmarks/g0/fault-injection/` case that was
attempted. Do not substitute a healthy document and report a pass.

---

### TC-13-08: document_create via MCP appears as a new GUI tab and tree root

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles), `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Preconditions**:
- [ ] The GUI document set is recorded before the call (verify: `mcp document_list {}` returns the current entries, and a snapshot records the current tab and tree rows)

**Steps**:
1. Snapshot the GUI first, so the before state is evidence and not memory:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1308_before.png"}' | & cua-driver call get_window_state
   ```
2. Create the document through MCP:
   ```bash
   mcp document_create {label:"TC13Parity"}
   ```
3. Re-snapshot the GUI:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1308_after.png"}' | & cua-driver call get_window_state
   ```
4. Read both sides:
   ```bash
   mcp document_list {}
   mcp query_tree_summary {doc:<newHandle>}
   ```

**Checkpoints**:
- [ ] CP1: MCP returns a handle — verify: step 2 returns `OK` with a document handle
- [ ] CP2: The GUI gained a tree root — verify: the step-3 `TreeItem` set contains a row labelled `TC13Parity` that is absent from the step-1 set
- [ ] CP3: The GUI gained a tab — verify: the step-3 snapshot lists a document tab for `TC13Parity` that step 1 did not have
- [ ] CP4: Visual confirmation — verify: read `_automation/tc1308_after.png`. The new document is visible in the Model panel and the tab bar. Compare against `tc1308_before.png`
- [ ] CP5: `document_list` includes it — verify: step 4 `document_list` returns an entry whose handle equals the step-2 handle and whose label is `TC13Parity`
- [ ] CP6: The new document is empty on both sides — verify: step 4 `query_tree_summary` returns no shape-bearing node, and the new GUI tree root has no child object rows
- [ ] CP7: No other document was disturbed — verify: every handle recorded in the preconditions still returns `OK` from `mcp query_tree_summary`

**Cleanup**:
```bash
rm -f _automation/tc1308_*.png
```
```bash
mcp document_close {doc:<newHandle>}
```
Do not save. `TC13Parity` is a scratch document and no `.FCStd` for it is committed.

---

### TC-13-09: document_open via MCP appears in the GUI tree and tab bar

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_open), §3.2 (query_tree_summary)

**Preconditions**:
- [ ] `box-10-20-30` is NOT already open (verify: `mcp document_list {}` returns no entry for it)

**Steps**:
1. Snapshot the GUI before:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1309_before.png"}' | & cua-driver call get_window_state
   ```
2. Open the golden model through MCP with an ABSOLUTE path:
   ```bash
   mcp document_open {path:"D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"}
   ```
3. Re-snapshot the GUI:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1309_after.png"}' | & cua-driver call get_window_state
   ```
4. Read the MCP side:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   mcp query_mass_properties {doc:<handle>, object:"Box"}
   ```

**Checkpoints**:
- [ ] CP1: The open succeeded — verify: step 2 returns `OK` with a handle
- [ ] CP2: A relative path would have failed — verify: `mcp document_open {path:"D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"}` returns `INVALID_INPUT`, because a relative path resolves against `C:\Program Files\FreeCAD 1.1\bin`
- [ ] CP3: The GUI gained the tree root — verify: the step-3 `TreeItem` set contains a row for the `box-10-20-30` document that step 1 did not have
- [ ] CP4: The GUI gained the object row — verify: the step-3 `TreeItem` set contains a row labelled `Box`, matching the node in step 4 `query_tree_summary`
- [ ] CP5: Visual confirmation — verify: read `_automation/tc1309_after.png`. The tab bar and Model panel show the opened document. The viewport is EXPECTED to be empty, because the fixture ships hidden
- [ ] CP6: The geometry agrees immediately — verify: step 4 `query_mass_properties` returns `volume` `6000.0`, `bbox` 0 to 10 by 0 to 20 by 0 to 30 mm, `com` `(5, 10, 15)`, faces `6`, edges `12`, vertices `8`, solids `1`
- [ ] CP7: The shipped visibility flag survived the open — verify: step 4 `query_tree_summary` reports `"visibility": false` for `Box`, and the GUI tree eye icon is struck through in `tc1309_after.png`

**Cleanup**:
```bash
rm -f _automation/tc1309_*.png
```
```bash
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-10: A feature_pad via MCP appears in the GUI tree and viewport

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pad`), `verification-design.md` §1 (mutation protocol, AD-5)

**Preconditions**:
- [ ] A scratch document with a Body and a padded-ready profile is open (verify: `mcp document_create {label:"TC13Pad"}` returns a handle; `mcp feature_body_create {doc:<handle>, name:"Body", confirm:{preview_id:"<token>"}}` returns `OK`; a sketch exists on the XY plane with a closed profile)
- [ ] The tree row set before the pad is recorded (verify: a snapshot's `TreeItem` labels are written down)

**Steps**:
1. Snapshot the GUI before the mutation:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1310_before.png"}' | & cua-driver call get_window_state
   ```
2. Take a preview token, then pad through MCP:
   ```bash
   mcp preview_dry_run {doc:<handle>, operation:{tool:"feature_pad", args:{doc:<handle>, body:"Body", profile:"<Sketch>", name:"Pad", length:{value:5, unit:"mm"}}}}
   mcp feature_pad {doc:<handle>, body:"Body", profile:"<Sketch>", name:"Pad", length:{value:5, unit:"mm"}, confirm:{preview_id:"<token>"}}
   ```
3. Re-snapshot, then press the `Fit All` toolbar button so the viewport frames the new solid:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Fit All Button token from this snapshot>"}' | & cua-driver call click
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1310_after.png"}' | & cua-driver call get_window_state
   ```
4. Grab the live viewport with the shared recipe to `_automation/tc1310_viewport.png`, and read the
   MCP side:
   ```bash
   mcp query_tree_summary {doc:<handle>, depth:2}
   mcp query_mass_properties {doc:<handle>, object:"Pad"}
   ```

**Checkpoints**:
- [ ] CP1: The mutation succeeded — verify: step 2 `feature_pad` returns `OK` with a mutation block whose `rolled_back` is false
- [ ] CP2: MCP shows the new node — verify: step 4 `query_tree_summary` names `Pad`
- [ ] CP3: The GUI tree shows the SAME new node — verify: the step-3 `TreeItem` set contains a row labelled `Pad` that the step-1 set did not have.

  > **Expand `Body` first — a collapsed parent hides its children from the UIA tree.** Verified
  > 2026-09-12: immediately after the pad the flat `TreeItem` set was still
  > `['TC13Pad', 'Body']`, because `Pad` is nested under `Body` and that node was collapsed. The
  > row only appeared — `['TC13Pad', 'Body', 'Origin', 'Pad']` — after expanding. **Absence from
  > the flat list is NOT a parity defect until the parent has been expanded.** The
  > `click({action:"expand"})` on the `Body` token did not land; a foreground pixel click on the
  > row's disclosure arrow (roughly `x = 21` at the row's `y`) did.
- [ ] CP4: Visual confirmation in the viewport — verify: read `_automation/tc1310_viewport.png`. A solid is drawn where the step-1 capture showed only the sketch. Do not pass on the tree row alone
- [ ] CP5: The solid matches the pad length — verify: step 4 `query_mass_properties` returns a `bbox` whose z extent is 5 mm, matching the `length` in step 2, and the viewport solid reads as that thickness
- [ ] CP6: The `Fit All` button exists because a document is open — verify: the button was found in the step-3 snapshot with label exactly `Fit All`. If it is absent, the document is not open and that is the precondition failing, not a defect
- [ ] CP7: Units were typed — verify: `length` was sent as `{value:5, unit:"mm"}`; a bare number is a schema reject, since the length unit enum admits only `mm`

**Cleanup**:
```bash
rm -f _automation/tc1310_*.png
```
```bash
mcp document_close {doc:<handle>}
```
Do not save. `TC13Pad` is a scratch document built by the test.

---

### TC-13-11: feature_set_parameters via MCP changes the value shown in the GUI property panel

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_set_parameters`), `verification-design.md` §1 (mutation protocol)

**Preconditions**:
- [ ] `box-10-20-30` is open (verify: `mcp query_mass_properties {doc:<handle>, object:"Box"}` returns `volume` `6000.0`)
- [ ] `Box` is selected in the GUI so the property panel shows its `Base` group (verify: a snapshot lists a `Placement` row and a `Label` row)

**Steps**:
1. Snapshot the property panel before the change:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1311_before.png"}' | & cua-driver call get_window_state
   ```
2. Change the driving parameter through MCP:
   ```bash
   mcp preview_dry_run {doc:<handle>, operation:{tool:"feature_set_parameters", args:{doc:<handle>, feature:"Box", parameters:{Length:{value:25, unit:"mm"}}}}}
   mcp feature_set_parameters {doc:<handle>, feature:"Box", parameters:{Length:{value:25, unit:"mm"}}, confirm:{preview_id:"<token>"}}
   ```
3. Re-snapshot the property panel:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1311_after.png"}' | & cua-driver call get_window_state
   ```
4. Read the MCP side:
   ```bash
   mcp query_mass_properties {doc:<handle>, object:"Box"}
   mcp verify_recompute {doc:<handle>}
   ```

**Checkpoints**:
- [ ] CP1: The mutation succeeded — verify: step 2 `feature_set_parameters` returns `OK` with `rolled_back` false
- [ ] CP2: The GUI property panel shows the new value — verify: the `Length` row in the step-3 snapshot reads `25`, where the step-1 snapshot read `10`
- [ ] CP3: Visual confirmation — verify: read `_automation/tc1311_before.png` and `_automation/tc1311_after.png` and confirm the property row value changed. An unchanged panel with a successful MCP call is a parity defect
- [ ] CP4: MCP geometry follows the change — verify: step 4 `query_mass_properties` returns `volume` `15000.0` (25 x 20 x 30), not `6000.0`, and a `bbox` x extent of 25 mm
- [ ] CP5: The two sides agree on the driving value — verify: the number in the GUI `Length` row equals the value in the MCP `parameters` argument that was accepted
- [ ] CP6: The confirm gate was honored — verify: repeating step 2's `feature_set_parameters` WITHOUT `confirm` returns the refusal `this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id`
- [ ] CP7: The recompute state agrees — verify: step 4 `verify_recompute` reports the same object set as touched or clean as the GUI tree markers show in `tc1311_after.png`

**Cleanup**:
```bash
rm -f _automation/tc1311_*.png
```
```bash
mcp document_close {doc:<handle>}
```
Do not save. `box-10-20-30` is a committed golden model and its `Length` must stay 10 mm on disk.

---

### TC-13-12: document_undo via MCP reverts the GUI tree and viewport

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (undo is refused, never silently no-op), `mcp-tools-design.md` §1.1 (document handles)

**Preconditions**:
- [ ] A document carrying one MCP mutation is open — reuse the TC-13-11 state (verify: `mcp query_mass_properties {doc:<handle>, object:"Box"}` returns `volume` `15000.0` after the `Length` change)
- [ ] The GUI shows that mutated state (verify: a snapshot's `Length` property row reads `25`)

**Steps**:
1. Snapshot the GUI in its mutated state and grab the viewport to
   `_automation/tc1312_mutated.png`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1312_before_undo.png"}' | & cua-driver call get_window_state
   ```
2. Undo through MCP:
   ```bash
   mcp document_undo {doc:<handle>}
   ```
3. Re-snapshot and grab the viewport to `_automation/tc1312_reverted.png`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1312_after_undo.png"}' | & cua-driver call get_window_state
   ```
4. Read the MCP side:
   ```bash
   mcp query_mass_properties {doc:<handle>, object:"Box"}
   mcp query_tree_summary {doc:<handle>}
   ```

**Checkpoints**:
- [ ] CP1: The undo succeeded — verify: step 2 returns `OK`, not a silent no-op
- [ ] CP2: MCP geometry reverted — verify: step 4 returns `volume` `6000.0` and the original `bbox` 0 to 10 by 0 to 20 by 0 to 30 mm
- [ ] CP3: The GUI property panel reverted — verify: the `Length` row in the step-3 snapshot reads `10` again, where the step-1 snapshot read `25`
- [ ] CP4: Visual confirmation — verify: read `tc1312_mutated.png` and `tc1312_reverted.png`. The solid is visibly narrower after the undo. A reverted number with an unchanged viewport is a parity defect
- [ ] CP5: The tree survived — verify: step 4 `query_tree_summary` names `Box` with the same node set as before the mutation, and the GUI `TreeItem` set matches it
- [ ] CP6: Both sides agree the document is clean — verify: `mcp verify_recompute {doc:<handle>}` reports no touched object, and the GUI tree in `tc1312_after_undo.png` shows no touched marker

**Cleanup**:
```bash
rm -f _automation/tc1312_*.png
```
```bash
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-13: document_close via MCP removes the GUI tab and tree root

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.1 (handle release), `data-contracts-design.md` §9 (closed status set)

**Preconditions**:
- [ ] Two documents are open (verify: `mcp document_list {}` returns two entries and both handles read `OK` from `mcp query_tree_summary`)

**Steps**:
1. Snapshot the GUI with both documents present:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1313_before.png"}' | & cua-driver call get_window_state
   ```
2. Close document A through MCP:
   ```bash
   mcp document_close {doc:<handleA>}
   ```
3. Re-snapshot the GUI:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1313_after.png"}' | & cua-driver call get_window_state
   ```
4. Read both sides:
   ```bash
   mcp document_list {}
   mcp query_tree_summary {doc:<handleA>}
   mcp query_tree_summary {doc:<handleB>}
   ```

**Checkpoints**:
- [ ] CP1: The close succeeded — verify: step 2 returns `OK`
- [ ] CP2: The GUI tree root is gone — verify: the document A row is present in the step-1 `TreeItem` set and ABSENT from the step-3 set
- [ ] CP3: The GUI tab is gone — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"<document A label>"},"exists":false}}]}' | & cua-driver call verify_state` returns `satisfied`. A result of `unknown` is inconclusive, never a pass; re-snapshot and judge `tc1313_after.png` directly instead
- [ ] CP4: Visual confirmation — verify: read both PNGs. Document A is in the tab bar and Model panel in `tc1313_before.png` and absent in `tc1313_after.png`
- [ ] CP5: `document_list` agrees with the GUI — verify: step 4 `document_list` returns one entry, and its handle is `<handleB>`
- [ ] CP6: The stale handle refuses cleanly — verify: step 4 `query_tree_summary {doc:<handleA>}` returns `INVALID_INPUT`, not `WORKER_CRASHED` and not `OK` with empty data
- [ ] CP7: Document B is untouched on both sides — verify: step 4 `query_tree_summary {doc:<handleB>}` returns `OK`, and its tree root is still present in `tc1313_after.png`

**Cleanup**:
```bash
rm -f _automation/tc1313_*.png
```
```bash
mcp document_close {doc:<handleB>}
```
Do not save either document.

---

### TC-13-14: A GUI visibility toggle is observed by MCP

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.2 (tree summary filters), `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Preconditions**:
- [ ] `box-10-20-30` is open and hidden as shipped (verify: `mcp query_tree_summary {doc:<handle>}` reports `"visibility": false` for `Box`)
- [ ] The FreeCAD Model tree is exposed in the accessibility tree (verify: a snapshot lists a `Tree` role element)

**Steps**:
1. Record the MCP state before any GUI action:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   mcp query_tree_summary {doc:<handle>, filters:{visible_only:true}}
   ```
2. Select the `Box` row. Re-snapshot first and match on `role == "TreeItem"` AND `label == "Box"`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Box TreeItem token from this snapshot>"}' | & cua-driver call click
   ```
3. Re-snapshot AGAIN, re-match the row on role and label, then send `space`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Box TreeItem token from THIS snapshot>","key":"space"}' | & cua-driver call press_key
   ```
   Do NOT reuse the step-2 token. A token that shifted by one may be the inline rename editor, and
   a `space` sent there edits the Label instead of the visibility flag — see TC-13-15.
4. Verify through MCP, which is the only verdict:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   mcp query_tree_summary {doc:<handle>, filters:{visible_only:true}}
   ```
   If `visibility` did not change, repeat step 3 once with `"delivery_mode":"foreground"` and read
   step 4 again. Record every attempt.

**Checkpoints**:
- [ ] CP1: MCP sees the flip — verify: step 4 reports `"visibility": true` for `Box`, where step 1 reported false
- [ ] CP2: The `visible_only` filter follows — verify: step 1's filtered call returned no node and step 4's returns `Box`
- [ ] CP3: `unverifiable` was not treated as a verdict — verify: the step-3 result is recorded verbatim, including `effect` and any `escalation`, and the pass or fail came from step 4 only. This route is confirmed to report `effect:"unverifiable"` with `escalation:{reason:"delivery_failed", target:"foreground"}` and still land
- [ ] CP4: The viewport agrees — verify: a viewport grab taken after step 3 with the shared recipe shows the box drawn, matching the `true` flag. Read the PNG
- [ ] CP5: No geometry changed — verify: `mcp query_mass_properties {doc:<handle>, object:"Box"}` returns `volume` `6000.0` before and after; visibility is a view flag
- [ ] CP6: The label was NOT edited — verify: step 4 reports `label` `Box`, not a string containing a space. If the label changed, the keystroke hit the rename editor and the toggle did not happen; undo with `Ctrl+Z` and re-run step 3 from a fresh snapshot
- [ ] CP7: MCP read the live flag, not a cache — verify: the step-4 result differs from step 1 with no MCP mutation call between them

**Cleanup**:
```bash
rm -f _automation/tc1314_*.png
```
Restore `Box` to hidden through the same route, confirm with `query_tree_summary`, then:
```bash
mcp document_close {doc:<handle>}
```
Do not save. The fixture ships with `Visibility=false`.

---

### TC-13-15: A GUI label rename is observed by MCP

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (label handling), `data-contracts-design.md` §9 (UTF-8 on the wire)

**Preconditions**:
- [ ] `box40-hole-r5` is open (verify: `mcp query_tree_summary {doc:<handle>}` reports `label` `BoxHole`)
- [ ] The token-shift hazard in Prerequisites Rule 2 has been read

**Steps**:
1. Record the label on both sides:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   mcp query_object {doc:<handle>, object:"BoxHole"}
   ```
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1315_before.png"}' | & cua-driver call get_window_state
   ```
2. Open the inline rename editor on the `BoxHole` row. Re-snapshot, match on
   `role == "TreeItem"` AND `label == "BoxHole"`, select it, re-snapshot, then press `F2`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<BoxHole TreeItem token from this snapshot>"}' | & cua-driver call click
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<BoxHole TreeItem token from THIS snapshot>","key":"f2"}' | & cua-driver call press_key
   ```
3. Re-snapshot to find the rename editor element, set its whole value, then commit with `enter`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1315_editing.png"}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<rename editor token from this snapshot>","value":"BoxHoleRenamed"}' | & cua-driver call set_value
   '{"pid":<PID>,"element_token":"<rename editor token from this snapshot>","key":"enter"}' | & cua-driver call press_key
   ```
   `set_value` replaces a control's whole value; `type_text` would insert at the cursor and could
   append to the existing label.
4. Read the MCP side, then revert with `Ctrl+Z` and read again:
   ```bash
   mcp query_tree_summary {doc:<handle>}
   ```
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"keys":["ctrl","z"],"delivery_mode":"foreground"}' | & cua-driver call hotkey
   ```
   ```bash
   mcp query_tree_summary {doc:<handle>}
   ```

**Checkpoints**:
- [ ] CP1: MCP sees the new label — verify: the first step-4 `query_tree_summary` reports `label` `BoxHoleRenamed`
- [ ] CP2: The internal name did NOT change — verify: `mcp query_object {doc:<handle>, object:"BoxHole"}` still resolves and returns `name` `BoxHole`. A rename changes the Label, never the internal name, and the GUI status bar still reads `Valid, Internal name: BoxHole`
- [ ] CP3: The GUI shows the new label — verify: a fresh snapshot's `TreeItem` set contains a row labelled `BoxHoleRenamed` and no row labelled `BoxHole`
- [ ] CP4: `Ctrl+Z` reverts on both sides — verify: the second step-4 `query_tree_summary` reports `label` `BoxHole` again, and a fresh snapshot's `TreeItem` row reads `BoxHole`
- [ ] CP5: MCP catches an ACCIDENTAL rename too — verify: this is the real incident this scenario is built from. On 2026-09-12 a `space` keystroke aimed at a tree row landed in the inline rename editor at the adjacent token, and `query_tree_summary` immediately reported `label: " "`. Reproduce it deliberately: send `space` to the rename editor token, read `query_tree_summary`, confirm `label` is `" "`, then `Ctrl+Z` with `delivery_mode:"foreground"` and confirm the label is restored
- [ ] CP6: Visual confirmation — verify: read `_automation/tc1315_before.png` and `_automation/tc1315_editing.png`. The second shows the inline editor open on the row. A rename claimed without the editor ever opening is not proven
- [ ] CP7: A value readback from the editor is NOT proof — verify: the pass comes from `query_tree_summary` after the `enter` commit, not from the editor echoing its own value. An editor that shows the new text while MCP still reports the old label is the parity defect this checkpoint exists to catch
- [ ] CP8: No geometry changed — verify: `mcp query_mass_properties {doc:<handle>, object:"BoxHole"}` returns `volume` `15214.601836602547` throughout

**Cleanup**:
```bash
rm -f _automation/tc1315_*.png
```
Confirm the label is `BoxHole` again with `mcp query_tree_summary {doc:<handle>}`, then:
```bash
mcp document_close {doc:<handle>}
```
Do not save. A saved rename would corrupt the committed golden model.

---

### TC-13-16: A GUI-opened document is seen by MCP and gets a handle

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_list adoption), `data-contracts-design.md` §9 (AD-20)

**Preconditions**:
- [ ] `cylinder-r5-h20` is NOT open (verify: `mcp document_list {}` returns no entry for it)
- [ ] At least one document is already open, so the `Open…` toolbar button exists in the UIA tree (verify: a snapshot lists a Button labelled `Open…`). With no document open the toolbar buttons are absent, which is a precondition, not a defect

**Steps**:
1. Record the MCP document set before:
   ```bash
   mcp document_list {}
   ```
2. Press the `Open…` toolbar button. Re-snapshot first and match on `role == "Button"` AND
   `label == "Open…"`:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Open… Button token from this snapshot>"}' | & cua-driver call click
   ```
3. Drive the file dialog. Enumerate it with `list_windows`, snapshot it, set the filename field to
   the ABSOLUTE path, then press its Open button by `element_token`:
   ```bash
   '{"pid":<PID>}' | & cua-driver call list_windows
   '{"pid":<PID>,"window_id":<dialogWID>,"screenshot_out_file":"_automation/tc1316_dialog.png"}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<filename Edit token from this snapshot>","value":"D:\\Work\\Personal\\Sources\\freecad-buddy\\benchmarks\\g0\\golden-models\\cylinder-r5-h20.FCStd"}' | & cua-driver call set_value
   '{"pid":<PID>,"window_id":<dialogWID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Open Button token from THIS snapshot>"}' | & cua-driver call click
   ```
4. Read the MCP side:
   ```bash
   mcp document_list {}
   mcp query_tree_summary {doc:<newHandle>}
   mcp query_mass_properties {doc:<newHandle>, object:"<Object>"}
   ```

**Checkpoints**:
- [ ] CP1: The GUI opened it — verify: a fresh snapshot's `TreeItem` set contains a row for the `cylinder-r5-h20` document that the step-1 state did not have. Read `_automation/tc1316_dialog.png` to confirm the dialog was the one driven
- [ ] CP2: MCP adopted it — verify: step 4 `document_list` returns one more entry than step 1, naming `cylinder-r5-h20`
- [ ] CP3: The new entry carries a usable handle — verify: step 4 `query_tree_summary` on that handle returns `OK` and names the object
- [ ] CP4: The geometry agrees with the reference — verify: step 4 `query_mass_properties` returns `volume` `1570.7963` within `rel: 0.001`, and a `bbox` of 10 x 10 x 20 mm
- [ ] CP5: The adopted handle behaves like an MCP-opened one — verify: `mcp query_screenshot {doc:<newHandle>, view:{include:["<Object>"]}}` returns a PNG with `rendered_objects` naming the object; read the PNG and confirm a cylinder, not a box
- [ ] CP6: No existing handle broke — verify: every handle from step 1 still returns `OK` from `mcp query_tree_summary`
- [ ] CP7: The toolbar route was used, not a menu — verify: the run evidence records the `Open…` Button `element_token` and `route: accessibility`. `invoke_menu` menu paths for this build are refused beyond the confirmed labels

**Cleanup**:
```bash
rm -f _automation/tc1316_*.png
```
```bash
mcp document_close {doc:<newHandle>}
```
Do not save.

---

### TC-13-17: A GUI-side recompute agrees with verify_recompute

**Priority**: High
**Design Ref**: `verification-design.md` §6.3 (recompute grading), `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Preconditions**:
- [ ] A document with at least one object that can be left touched is open (verify: `mcp document_list {}` returns a handle and `mcp verify_recompute {doc:<handle>}` returns `OK`)
- [ ] The document has a pending recompute. Use the TC-13-11 route to change a driving parameter without recomputing (verify: `mcp verify_recompute {doc:<handle>}` names at least one touched object)

**Steps**:
1. Record the touched set from MCP and the tree markers from the GUI:
   ```bash
   mcp verify_recompute {doc:<handle>}
   ```
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1317_touched.png"}' | & cua-driver call get_window_state
   ```
2. Trigger the recompute from the GUI. Re-snapshot, select the document root row on
   `role == "TreeItem"`, then use the `Tree View Actions` toolbar button to reach the refresh
   command:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<document root TreeItem token from this snapshot>"}' | & cua-driver call click
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<Tree View Actions Button token from THIS snapshot>"}' | & cua-driver call click
   ```
   If the popup entry cannot be enumerated — Qt popups are not top-level windows — fall back to
   `mcp document_recompute {doc:<handle>}` and record that the GUI route was unavailable. That is a
   route limitation, recorded, not a product defect.
3. Re-read both sides:
   ```bash
   mcp verify_recompute {doc:<handle>}
   ```
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1317_clean.png"}' | & cua-driver call get_window_state
   ```

**Checkpoints**:
- [ ] CP1: Both sides agree the document was dirty — verify: step 1 `verify_recompute` names touched objects, AND `_automation/tc1317_touched.png` shows the touched marker on the same rows
- [ ] CP2: Both sides agree it is clean after — verify: step 3 `verify_recompute` reports no touched object, AND `_automation/tc1317_clean.png` shows no touched marker
- [ ] CP3: The failing set is identical — verify: any object MCP names as failing is an object the GUI tree marks with an error, and no object is marked on one side only
- [ ] CP4: Visual confirmation — verify: read both PNGs. The marker state visibly changed. A cleared MCP touched set with unchanged tree markers is a parity defect
- [ ] CP5: The geometry settled — verify: `mcp query_mass_properties {doc:<handle>, object:"<Object>"}` returns the value implied by the changed parameter, not the pre-change value
- [ ] CP6: The route actually used is recorded — verify: the run evidence states whether the GUI button route or the `document_recompute` fallback produced the recompute

**Cleanup**:
```bash
rm -f _automation/tc1317_*.png
```
```bash
mcp document_undo {doc:<handle>}
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-18: A GUI-side close removes the document from MCP and invalidates the handle

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.1 (handle resolution), `data-contracts-design.md` §9 (closed status set)

**Preconditions**:
- [ ] Two documents are open (verify: `mcp document_list {}` returns two entries; both handles return `OK` from `mcp query_tree_summary`)
- [ ] Neither document has unsaved changes, so no save prompt appears (verify: `mcp verify_recompute {doc:<handleA>}` reports no touched object)

**Steps**:
1. Record both handles and the GUI state:
   ```bash
   mcp document_list {}
   ```
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1318_before.png"}' | & cua-driver call get_window_state
   ```
2. Close document A from the GUI. Re-snapshot, select its root row matched on
   `role == "TreeItem"` and its label, then use `Ctrl+W` delivered to that row:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<document A root TreeItem token from this snapshot>"}' | & cua-driver call click
   '{"pid":<PID>,"keys":["ctrl","w"],"delivery_mode":"foreground"}' | & cua-driver call hotkey
   ```
   If a save prompt appears, enumerate it with `list_windows`, snapshot it, and click its discard
   button by `element_token`. Never accept a save on a golden model.
3. Confirm the GUI state and read the MCP side:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc1318_after.png"}' | & cua-driver call get_window_state
   ```
   ```bash
   mcp document_list {}
   mcp query_tree_summary {doc:<handleA>}
   mcp query_mass_properties {doc:<handleA>, object:"<Object>"}
   mcp document_close {doc:<handleA>}
   ```

**Checkpoints**:
- [ ] CP1: The GUI closed it — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"<document A label>"},"exists":false}}]}' | & cua-driver call verify_state` returns `satisfied`. `unknown` is inconclusive, not a pass — judge `tc1318_after.png` directly instead
- [ ] CP2: Visual confirmation — verify: read both PNGs. Document A's tab and tree root are present before and absent after
- [ ] CP3: `document_list` dropped it — verify: step 3 `document_list` returns one entry, and its handle is `<handleB>`
- [ ] CP4: Every stale read refuses with INVALID_INPUT — verify: `query_tree_summary` and `query_mass_properties` on `<handleA>` both return `INVALID_INPUT`, not `WORKER_CRASHED` and not `OK` with empty data
- [ ] CP5: The stale close is also a clean refusal — verify: `document_close {doc:<handleA>}` returns `INVALID_INPUT`, not a crash
- [ ] CP6: FreeCAD and the bridge survived — verify: `Get-Process -Name freecad` reports the same pid, and `mcp query_capabilities {}` returns `OK`
- [ ] CP7: Document B is unharmed on both sides — verify: `mcp query_tree_summary {doc:<handleB>}` returns `OK`, and its tree root is still visible in `tc1318_after.png`

**Cleanup**:
```bash
rm -f _automation/tc1318_*.png
```
```bash
mcp document_close {doc:<handleB>}
```
Do not save either document.

---

## Divergence handling

- A number that matches while the pixels disagree is a **defect**, not a tolerance. Every geometry
  and render scenario here carries a visual checkpoint for that reason. Record the exact difference
  and stop; do not pass on numbers alone.
- A `verify_state` result of `unknown` is inconclusive, never a pass. Re-snapshot and read the
  screenshot directly. If it stays unresolvable, record the scenario as inconclusive with the
  observed tree and PNG.
- An `effect: "unverifiable"` result is neither a pass nor a fail. The verdict comes from the MCP
  state read or the fresh screenshot that follows it.
- A GUI action that cannot be reached — a refused `invoke_menu` path, a Qt popup that cannot be
  enumerated — is a **route limitation**. Record the exact refusal, name the fallback used, and
  grade the parity assertion through the fallback. Do not report the product as broken for a
  driving limitation, and do not report a pass without saying which route produced it.
- A label that changes without the operator intending it means a keystroke reached the inline
  rename editor. Undo with `Ctrl+Z` at `delivery_mode:"foreground"`, confirm the label through
  `query_tree_summary`, and re-run the step from a fresh snapshot. TC-13-15 CP5 grades this on
  purpose; anywhere else it invalidates the step.
- A mutated golden model that reaches `document_save` invalidates every later run in the suite.
  Every scenario that mutates a fixture closes without saving, and the Cleanup block says so.
