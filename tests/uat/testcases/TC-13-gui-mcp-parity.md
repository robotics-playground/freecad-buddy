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

**Host**: GUI through the H2 proxy for every scenario. Every scenario needs the live FreeCAD window,
because the parity claim is graded against a `cua-driver` capture of that window.

### Rule 0 — the MCP bridge is the code under test, so its output is never the test result

We are BUILDING the MCP bridge. Parity is the claim that the MCP view and the GUI view agree. If
that claim is checked using MCP output, the bridge has been asked to confirm itself. Commit
`636fb8a` fixed exactly that class of defect: the bridge reported a successful fit while the part
occupied roughly 5 % of the viewport.

| Rank | Artifact | Trust |
| --- | --- | --- |
| 1 | A `cua-driver` pixel capture of the real FreeCAD window, `Read` and judged by the agent | The test result |
| 2 | `cua-driver` accessibility-tree reads, filesystem, exit codes, logs | Corroborating |
| 3 | MCP envelope fields, statuses, `query_screenshot` renders | **Claims under test, never evidence** |

The asymmetry is deliberate. In every scenario below the GUI is the referent and the MCP report is
the thing judged against it. Never the reverse. Where the two disagree, the window wins, and the
disagreement is written to `$RUN_DIR/bugs.md` as a finding against the bridge.

## Preconditions
- [ ] FreeCAD 1.1.1 GUI is open (verify: `Get-Process -Name freecad | Select-Object Id,MainWindowTitle` lists one process with title `FreeCAD 1.1.1`)
- [ ] The MCP proxy serves `:8765` — the addon auto-spawns it on FreeCAD start (verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row). No manual `serve` command.
- [ ] `cua-driver` is reachable and in the interactive session (verify: `cua-driver status` reports the daemon and NOT Session 0)
- [ ] The FreeCAD `(pid, window_id)` pair is RE-RESOLVED for this run (verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns the window whose `title` is `FreeCAD 1.1.1`). Both values change between FreeCAD restarts. Never carry a `pid` or `window_id` from a previous run or a previous test file.
- [ ] The render ladder is usable (verify: `mcp query_capabilities {}` returns `render` = `gui_constructed`)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)

### Rule 1 — every MCP `path` argument is ABSOLUTE

A relative `path` resolves against FreeCAD's own working directory, which is
`C:\Program Files\FreeCAD 1.1\bin`, and the open fails. Write
`$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd`, never
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
target:"foreground"}` and DID land — `query_tree_summary` flipped the `Box` line to start `v `. A
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

Every scenario that compares against the live viewport captures it with `cua-driver`, which does not
raise, restack, or focus the FreeCAD window, so the user's active window stays where it is.

```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-NN-<name>.png"}' | & cua-driver call get_window_state
```

Forbidden in every scenario below: `Start-Process`, `SetForegroundWindow`, `taskkill /F`.

---

### TC-13-01: Tree parity — the MCP node set equals the GUI Model tree

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.2 (query_tree_summary), `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Given** `box40-hole-r5` is open — verify: `mcp document_open {path:"$PROJECT_ROOT/benchmarks/g0/golden-models/box40-hole-r5.FCStd"}` returns a handle  
**And** the FreeCAD Model tree is exposed in the accessibility tree — verify: `'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state` lists a `Tree` role element  

**When** the MCP node set is read  
```bash
mcp query_tree_summary {doc:<handle>, depth:2}
```
Record every node `name` and `label`.
**And** the GUI is snapshotted and its tree rows extracted  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-01-tree.png"}' | & cua-driver call get_window_state
```
From the returned elements, keep only those whose `role` is `TreeItem` and record each `label`.
**And** the PNG from the snapshot is read and the model tree panel read directly  

**Then** the object node is present on both sides — verify: the MCP read names `BoxHole` and the `TreeItem` set contains a row labelled `BoxHole`. The object in `box40-hole-r5` is named `BoxHole`, NOT `Cut`  
**And** the document root agrees — verify: the `TreeItem` set contains a row for the document, and `mcp document_list {}` reports one entry whose label matches that row  
**And** node counts agree — verify: the count of shape-bearing nodes in the MCP read equals the count of object rows in the snapshot, after excluding the document root row  
**And** no MCP-only node — verify: every `name` reported by the MCP read has a `TreeItem` row with a matching `label` in the snapshot  
**And** no GUI-only node — verify: every object `TreeItem` row in the snapshot appears in the MCP output; a row with no MCP node is a parity defect, not a filter  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the GUI Model panel is the referent for the node set — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-01-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and write down the rows you can see in the Model panel. Confirm the `TreeItem` labels match those rows one for one, and that the MCP node set matches the rows you read. Do not pass on the element list alone. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<handle>}
```
Do not save. The fixture must keep its shipped state.

---

### TC-13-02: Object identity parity — name and type agree with the status bar and the property panel

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.2 (query_object), `data-contracts-design.md` §9 (error field)

**Given** `box40-hole-r5` is open — verify: `mcp query_tree_summary {doc:<handle>}` names `BoxHole`  
**And** the GUI status bar is present in the accessibility tree — verify: `'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state` lists a `StatusBar` or a bottom `Text` element  

**When** the MCP identity is read  
```bash
mcp query_object {doc:<handle>, object:"BoxHole"}
```
Record `name`, `type`, `label`, and `error`.
**And** the tree is re-snapshotted and the `BoxHole` row selected by its token from THAT snapshot, matched on `role == "TreeItem"` and `label == "BoxHole"`  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<BoxHole TreeItem token from this snapshot>"}' | & cua-driver call click
```
**And** the window is re-snapshotted and the status bar text and property panel read  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-02-selected.png"}' | & cua-driver call get_window_state
```
The property panel is bottom-left, Data tab, with a `Base` group holding `Placement` and `Label`
rows.

**Then** the internal name agrees — verify: the MCP `name` is `BoxHole` and the status bar reads `Valid, Internal name: BoxHole`  
**And** the status bar also confirms validity — verify: the status bar text begins `Valid,`, and the MCP `error` is null or absent. A `Valid` status bar with a non-null MCP `error` is a parity defect  
**And** the label agrees — verify: the MCP `label` equals the value in the property panel `Label` row and equals the `TreeItem` label used for the selection  
**And** the type is reported — verify: the MCP `type` is a non-empty FreeCAD type string, and the object it names is the one the tree row selects  
**And** selection did not mutate anything — verify: `mcp query_mass_properties {doc:<handle>, object:"BoxHole"}` returns `volume` `15214.601836602547` both before and after the selection  
**And** face naming agrees on hover — verify: hovering a face makes the status bar read `Preselected: <doc>.BoxHole.<FaceN>`, and the object segment of that string equals the MCP `name`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the window states the identity, and the MCP report is judged against it — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-02-after.png"}' | & cua-driver call get_window_state`, then `Read` `$RUN_DIR/evidence/tc-13-02-selected.png` and `$RUN_DIR/evidence/tc-13-02-after.png`. Read off the images which row is highlighted, what the status bar says, and what the property panel `Label` row reads. Confirm the highlighted row is `BoxHole`, the status bar shows the internal name, and the `Label` row shows the same label — then check the MCP `name` and `label` against what you read. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-03: Visibility parity in BOTH states

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document handles), `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Given** `box-10-20-30` is open and still hidden as shipped — verify: the tree text (`content[1]`) of `mcp query_tree_summary {doc:<handle>}` is `- [FEATURE] Box`  

**When** the hidden state is recorded on both sides  
```bash
mcp query_tree_summary {doc:<handle>}
mcp query_screenshot {doc:<handle>}
```
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-03-hidden.png"}' | & cua-driver call get_window_state
```
**And** visibility is toggled in the GUI: re-snapshot, select the `Box` row by token matched on `role == "TreeItem"` and `label == "Box"`, then send `space`  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Box TreeItem token from this snapshot>"}' | & cua-driver call click
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Box TreeItem token from THIS snapshot>","key":"space"}' | & cua-driver call press_key
```
The result is expected to report `effect:"unverifiable"`. That is not the verdict. Confirm with the
re-read below. If the `Box` line still starts `-`, repeat this action once with
`"delivery_mode":"foreground"` and confirm again.
**And** both sides are re-read  
```bash
mcp query_tree_summary {doc:<handle>}
mcp query_screenshot {doc:<handle>}
```
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-03-visible.png"}' | & cua-driver call get_window_state
```

**Then** hidden agrees on both sides — verify: the first `query_tree_summary` tree text is `- [FEATURE] Box`, AND `$RUN_DIR/evidence/tc-13-03-hidden.png` shows an empty viewport with the tree eye icon struck through  
**And** the hidden default render is honest — verify: the first `query_screenshot` returns `render.empty_scene` true, `scene.rendered_objects` `[]`, and NO `resource_link`. This is correct behavior, not a render failure  
**And** visible agrees on both sides — verify: the second `query_tree_summary` tree text is `v [FEATURE] Box`, AND `$RUN_DIR/evidence/tc-13-03-visible.png` shows the box drawn in the viewport  
**And** the default render follows the live flag — verify: the second `query_screenshot` returns `scene.rendered_objects` equal to `["Box"]` with a non-null `resource_link`  
**And** an explicit include overrides the flag in EITHER state — verify: `mcp query_screenshot {doc:<handle>, view:{include:["Box"]}}` returns `rendered_objects: ["Box"]` and a PNG while the `Box` line starts `-`  
**And** the toggle changed no geometry — verify: `mcp query_mass_properties {doc:<handle>, object:"Box"}` returns `volume` `6000.0` in both states  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the pixels followed the flag in both directions — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-03-after.png"}' | & cua-driver call get_window_state`, then `Read` `$RUN_DIR/evidence/tc-13-03-hidden.png` and `$RUN_DIR/evidence/tc-13-03-after.png` and say what each viewport contains. The hidden capture shows no solid, the after capture shows one box. A numeric flag flip with no pixel change is a parity defect. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
Restore `Box` to hidden with the same toggle route, confirm with `query_tree_summary`, then:
```bash
mcp document_close {doc:<handle>}
```
Do not save. The fixture ships with `Visibility=false` and must keep it.

---

### TC-13-04: Geometry parity — mass properties agree with the drawn shape

**Priority**: Critical
**Design Ref**: `verification-design.md` §5 (measured facts), `mcp-tools-design.md` §3.3

**Given** `box40-hole-r5` is open — verify: `mcp query_tree_summary {doc:<handle>}` names `BoxHole`  
**And** the render ladder is usable — verify: `mcp query_capabilities {}` returns `render` = `gui_constructed`  

**When** the measured facts are read  
```bash
mcp query_mass_properties {doc:<handle>, object:"BoxHole"}
mcp verify_shape {doc:<handle>, object:"BoxHole"}
```
**And** the object is rendered and `render.resource_link` copied to `$RUN_DIR/evidence/tc-13-04-mcp.png`  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso", include:["BoxHole"]}}
```
**And** the object is made visible in the GUI using the TC-13-03 toggle route, the `Fit All` toolbar button is pressed, and the live viewport captured  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Fit All Button token from this snapshot>"}' | & cua-driver call click
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-04-viewport.png"}' | & cua-driver call get_window_state
```
**And** both PNGs are read side by side  

**Then** volume matches the verified reference — verify: the mass-properties read returns `volume` `15214.601836602547` mm3, within `rel: 0.001` of the `expected.yaml` analytic value  
**And** surface area matches — verify: the same read returns `area` `4957.079632679489` mm2  
**And** the bounding box matches — verify: the same read returns `bbox` spanning 0 to 40 mm in x, 0 to 40 mm in y, and 0 to 10 mm in z  
**And** topology counts are exact — verify: the same read returns faces `7`, edges `15`, vertices `10`, solids `1`. These carry no tolerance  
**And** `com` is `null` and stays `null` — verify: the same read returns `com` null for `BoxHole`; a scenario asserting a number here is wrong  
**And** *(visual)* the proportion is confirmed — verify: read both PNGs. The object reads as a flat square plate, 40 by 40 by 10 mm, that is four times wider than it is tall. A cubic silhouette contradicts the `bbox` assertion and is a defect  
**And** *(visual)* the through hole is visible — verify: both PNGs show one circular hole passing through the plate, consistent with the genus-1 topology the counts assert. A solid plate with no hole means the numbers and the pixels disagree  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the window is the referent and the MCP render is judged against it — verify: fit FIRST, then take both captures so they share a camera: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-04-after.png"}' | & cua-driver call get_window_state`, and the `query_screenshot` render already written to `$RUN_DIR/evidence/tc-13-04-mcp.png`. `Read` `$RUN_DIR/evidence/tc-13-04-after.png` first and describe the solid you see; then `Read` `$RUN_DIR/evidence/tc-13-04-mcp.png` and confirm the silhouette, hole position, and camera match; any extra or missing body is a defect, not a tolerance. Where they disagree the window wins, and the disagreement is recorded as a finding against the bridge in `$RUN_DIR/bugs.md`. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
Restore `BoxHole` to hidden, confirm with `query_tree_summary`, then:
```bash
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-05: Placement parity — query_placement agrees with the property panel

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2 (query_placement), `data-contracts-design.md` §9 (Quantity)

**Given** `box40-hole-r5` is open — verify: `mcp query_tree_summary {doc:<handle>}` names `BoxHole`  
**And** the property panel is visible in the GUI — verify: a snapshot lists a `Placement` row and a `Label` row in the bottom-left Data tab  

**When** the MCP placement is read  
```bash
mcp query_placement {doc:<handle>, object:"BoxHole"}
```
Record position, axis, and angle, each with its `unit`.
**And** the object is selected in the GUI so the property panel populates: re-snapshot first and match the row on `role == "TreeItem"` and `label == "BoxHole"`  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<BoxHole TreeItem token from this snapshot>"}' | & cua-driver call click
```
**And** the window is re-snapshotted and the `Base` group in the property panel read  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-05-props.png"}' | & cua-driver call get_window_state
```
The `Placement` row renders as `[(<axis x> <axis y> <axis z>); <angle>°; (<position>...`, for
example `[(0.00 0.00 1.00); 0.00°; (0.0...`.

**Then** the rotation axis agrees — verify: the axis vector from the MCP read equals the first bracketed triple in the `Placement` row  
**And** the angle agrees — verify: the MCP read reports the angle with `unit` `deg`, and its value equals the degrees shown in the `Placement` row  
**And** the position agrees — verify: the MCP position equals the position triple in the `Placement` row; the GUI row truncates, so read the full value by expanding the `Placement` row in the panel  
**And** units are typed on the wire — verify: every length in the MCP read is a `{value, unit}` object with `unit` `mm`, and every angle uses `deg`. A bare number is a contract defect  
**And** placement is consistent with the bounding box — verify: the origin reported by the MCP read agrees with the `bbox` from `mcp query_mass_properties {doc:<handle>, object:"BoxHole"}`, which spans 0 to 40 mm in x and y  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the property panel is the referent for the placement — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-05-after.png"}' | & cua-driver call get_window_state`, then `Read` `$RUN_DIR/evidence/tc-13-05-props.png` and `$RUN_DIR/evidence/tc-13-05-after.png` and read the `Placement` and `Label` row values straight off the images. Confirm those are the rows the assertions above used, then check the MCP numbers against the values you read. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-06: Render parity — the MCP render matches the live viewport

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Given** `box40-hole-r5` is open and `BoxHole` has been made visible — verify: the tree text (`content[1]`) of `mcp query_tree_summary {doc:<handle>}` has a `BoxHole` line starting `v `  
**And** the geometry is known — verify: `mcp query_mass_properties {doc:<handle>, object:"BoxHole"}` returns `volume` `15214.601836602547` and the 40 x 40 x 10 mm `bbox`  

**When** a shared camera is set through the toolbar, not a keystroke: re-snapshot, press `Standard Views`, re-snapshot, then select the isometric entry by its token from the NEW snapshot  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Standard Views Button token from this snapshot>"}' | & cua-driver call click
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-06-menu.png"}' | & cua-driver call get_window_state
```
`invoke_menu(["View","Standard views"])` is REFUSED on this build with `menu_path_unavailable`
at segment 1, and a viewport `press_key` does not land. If the isometric entry does not appear
in the snapshot, the Qt popup is not a top-level window and cannot be enumerated; in that case
record the camera FreeCAD is actually showing and compare against the matching MCP camera
instead of forcing iso.
**And** the object is framed with the `Fit All` toolbar button  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Fit All Button token from this snapshot>"}' | & cua-driver call click
```
**And** the MCP render is captured and `render.resource_link` copied to `$RUN_DIR/evidence/tc-13-06-mcp.png`  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso", include:["BoxHole"]}}
```
**And** the live viewport is captured and both PNGs read side by side  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-06-viewport.png"}' | & cua-driver call get_window_state
```

**Then** the MCP render names the object — verify: the render returns `scene.rendered_objects` containing `BoxHole` and a non-null `render.resource_link`  
**And** the render did not touch the document — verify: `mcp query_mass_properties {doc:<handle>, object:"BoxHole"}` returns the same volume after the render as before it, and `mcp verify_recompute {doc:<handle>}` reports no touched object  
**And** *(visual)* the silhouette is the same — verify: read both PNGs. The plate outline and the through hole appear in the same relative position in each  
**And** *(visual)* the camera is the same — verify: the number of visible faces and the up direction agree between the two images. An axis flip is a defect, recorded exactly  
**And** *(visual)* the proportions match the geometry — verify: both images read as a flat 40 x 40 x 10 mm plate, consistent with the `bbox` in the Given, not as a cube  
**And** *(visual)* there is no extra or missing geometry — verify: nothing visible in `$RUN_DIR/evidence/tc-13-06-viewport.png` is absent from `$RUN_DIR/evidence/tc-13-06-mcp.png`, and no `PartDesign::Body`, `Sketcher::SketchObject`, or `App::Origin` child leaked into the render  
**And** *(visual)* shading is not black-sided — verify: faces angled away from the camera render as shaded grey in `$RUN_DIR/evidence/tc-13-06-mcp.png`, matching the tone of the same faces in `$RUN_DIR/evidence/tc-13-06-viewport.png`. Pure black means the camera-aligned headlight was lost  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the fitted window is the referent and the render is judged against it — verify: fit FIRST, then take both captures so they share a camera: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-06-after.png"}' | & cua-driver call get_window_state`, and the `query_screenshot` render at `$RUN_DIR/evidence/tc-13-06-mcp.png`. `Read` `$RUN_DIR/evidence/tc-13-06-after.png` first and describe what is on screen; then `Read` `$RUN_DIR/evidence/tc-13-06-mcp.png` and confirm the same plate with the same hole at a comparable framing and orientation. Where they disagree the window wins, and the disagreement is recorded as a finding against the bridge in `$RUN_DIR/bugs.md`. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
Restore `BoxHole` to hidden, confirm with `query_tree_summary`, then:
```bash
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-07: Error-state parity — a broken object is reported by both sides

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2 (query_object), `verification-design.md` §6.3 (failing-object reporting)

**Given** a fixture whose object carries an error or a failing recompute is open. Use a case from `benchmarks/g0/fault-injection/`, for example `non-watertight-open-shell` — verify: `mcp document_open {path:"$PROJECT_ROOT/benchmarks/g0/fault-injection/non-watertight-open-shell/fixture.FCStd"}` returns a handle  
**And** the reference checks from the case are to hand — verify: the `assertions.checks` block in that case's `case.yaml` is read and will be passed to `verify_shape`  

**When** the MCP error surface is read  
```bash
mcp query_object {doc:<handle>, object:"<Object>"}
mcp verify_recompute {doc:<handle>}
mcp verify_shape {doc:<handle>, object:"<Object>", checks:<checks from case.yaml>}
```
**And** the GUI Model tree is snapshotted and the tree error marker on the object row looked for  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-07-tree.png"}' | & cua-driver call get_window_state
```
**And** the object row is selected and the window re-snapshotted to read the status bar  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Object TreeItem token from this snapshot>"}' | & cua-driver call click
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-07-status.png"}' | & cua-driver call get_window_state
```

**Then** MCP reports the fault — verify: `query_object` returns a non-null `error` for the object, OR `verify_recompute` names it among the failing objects  
**And** the graded verdict uses the reference checks — verify: `verify_shape` was called WITH the `assertions.checks` from `case.yaml` and returns `SPEC_FAILED`. Called without them a wrong-but-valid shape returns `OK` and the scenario would detect nothing  
**And** the GUI marks the same object — verify: read `$RUN_DIR/evidence/tc-13-07-tree.png` and confirm the object row carries the FreeCAD error or touched marker  
**And** the status bar does not claim validity — verify: `$RUN_DIR/evidence/tc-13-07-status.png` does NOT read `Valid, Internal name: <Object>` for the broken object. A `Valid` status bar alongside a non-null MCP `error` is a parity defect and is recorded as such  
**And** both sides name the SAME object — verify: the object named by the MCP reads is the object whose row carries the marker in the tree snapshot; a mismatch is the finding  
**And** the clean control separates detection from rejection — verify: repeat the MCP reads and the tree snapshot against `benchmarks/g0/fault-injection/clean-control/fixture.FCStd`; MCP returns no error and the GUI tree shows no marker. Without this, a verifier that fails everything scores the same as a correct one  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the window is the referent for the fault — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-07-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and name, from the image alone, which row carries the FreeCAD error or touched marker and what the status bar for that row reads. Confirm the marked row is the object MCP named and that the status bar does not read `Valid,`. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
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

**Given** the GUI document set is recorded before the call — verify: `mcp document_list {}` returns the current entries, and a snapshot records the current tab and tree rows  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open {path:"$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd"}` returns `OK`; record the handle as `<goldenHandle>`  

**When** the GUI is snapshotted first, so the before state is evidence and not memory  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-08-before.png"}' | & cua-driver call get_window_state
```
**And** the document is created through MCP  
```bash
mcp document_create {label:"TC13Parity"}
```
**And** the GUI is re-snapshotted  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-08-after-create.png"}' | & cua-driver call get_window_state
```
**And** both sides are read  
```bash
mcp document_list {}
mcp query_tree_summary {doc:<newHandle>}
```

**Then** MCP returns a handle — verify: `document_create` returns `OK` with a document handle  
**And** the GUI gained a tree root — verify: the post-create `TreeItem` set contains a row labelled `TC13Parity` that is absent from the before set  
**And** the GUI gained a tab — verify: the post-create snapshot lists a document tab for `TC13Parity` that the before snapshot did not have  
**And** `document_list` includes it — verify: `document_list` returns an entry whose handle equals the created handle and whose label is `TC13Parity`  
**And** the new document is empty on both sides — verify: `query_tree_summary` returns no shape-bearing node, and the new GUI tree root has no child object rows  
**And** no other document was disturbed — verify: every handle recorded in the Given still returns `OK` from `mcp query_tree_summary`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<goldenHandle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the MCP-created document reached the human's screen — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-08-after.png"}' | & cua-driver call get_window_state`, then `Read` `$RUN_DIR/evidence/tc-13-08-before.png` and `$RUN_DIR/evidence/tc-13-08-after.png` and confirm `TC13Parity` is visible in the Model panel and the tab bar in the after image and absent in the before image. `document_create` returning `OK` is the claim; the new tab and tree root in the picture are the evidence. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<newHandle>}
mcp document_close {doc:<goldenHandle>}
```
Do not save. `TC13Parity` is a scratch document and no `.FCStd` for it is committed.

---

### TC-13-09: document_open via MCP appears in the GUI tree and tab bar

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_open), §3.2 (query_tree_summary)

**Given** `box-10-20-30` is NOT already open — verify: `mcp document_list {}` returns no entry for it  

**When** the GUI is snapshotted before  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-09-before.png"}' | & cua-driver call get_window_state
```
**And** the golden model is opened through MCP with an ABSOLUTE path  
```bash
mcp document_open {path:"$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd"}
```
**And** the GUI is re-snapshotted  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-09-after-open.png"}' | & cua-driver call get_window_state
```
**And** the MCP side is read  
```bash
mcp query_tree_summary {doc:<handle>}
mcp query_mass_properties {doc:<handle>, object:"Box"}
```

**Then** the open succeeded — verify: `document_open` returns `OK` with a handle  
**And** a relative path would have failed — verify: `mcp document_open {path:"benchmarks/g0/golden-models/box-10-20-30.FCStd"}` — the bare relative form, with no `$PROJECT_ROOT` prefix — returns `INVALID_INPUT`, because a relative path resolves against `C:\Program Files\FreeCAD 1.1\bin`  
**And** the GUI gained the tree root — verify: the post-open `TreeItem` set contains a row for the `box-10-20-30` document that the before set did not have  
**And** the GUI gained the object row — verify: the post-open `TreeItem` set contains a row labelled `Box`, matching the node in `query_tree_summary`  
**And** the geometry agrees immediately — verify: `query_mass_properties` returns `volume` `6000.0`, `bbox` 0 to 10 by 0 to 20 by 0 to 30 mm, `com` `(5, 10, 15)`, faces `6`, edges `12`, vertices `8`, solids `1`  
**And** the shipped visibility flag survived the open — verify: the `query_tree_summary` `Box` line starts `- `, and the GUI tree eye icon is struck through in `$RUN_DIR/evidence/tc-13-09-after-open.png`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the MCP-opened document reached the human's screen — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-09-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm the tab bar and Model panel show the opened document. The viewport is EXPECTED to be empty, because the fixture ships hidden. `document_open` returning a handle is the claim; the document visible in the tab bar is the evidence. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-10: A feature_pad via MCP appears in the GUI tree and viewport

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pad`), `verification-design.md` §1 (mutation protocol, AD-5)

**Given** a scratch document with a Body and a padded-ready profile is open — verify: `mcp document_create {label:"TC13Pad"}` returns a handle; `mcp feature_body_create {doc:<handle>, name:"Body", confirm:{preview_id:"<token>"}}` returns `OK`; a sketch exists on the XY plane with a closed profile  
**And** the tree row set before the pad is recorded — verify: a snapshot's `TreeItem` labels are written down  

**When** the GUI is snapshotted before the mutation  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-10-before.png"}' | & cua-driver call get_window_state
```
**And** a preview token is taken, then the pad is issued through MCP  
```bash
mcp preview_dry_run {doc:<handle>, operation:{tool:"feature_pad", args:{doc:<handle>, body:"Body", profile:"<Sketch>", name:"Pad", length:{value:5, unit:"mm"}}}}
mcp feature_pad {doc:<handle>, body:"Body", profile:"<Sketch>", name:"Pad", length:{value:5, unit:"mm"}, confirm:{preview_id:"<token>"}}
```
**And** the window is re-snapshotted, then the `Fit All` toolbar button pressed so the viewport frames the new solid  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Fit All Button token from this snapshot>"}' | & cua-driver call click
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-10-after-pad.png"}' | & cua-driver call get_window_state
```
**And** the live viewport is captured and the MCP side read  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-10-viewport.png"}' | & cua-driver call get_window_state
```
```bash
mcp query_tree_summary {doc:<handle>, depth:2}
mcp query_mass_properties {doc:<handle>, object:"Pad"}
```

**Then** the mutation succeeded — verify: `feature_pad` returns `OK` with a mutation block whose `rolled_back` is false  
**And** MCP shows the new node — verify: `query_tree_summary` names `Pad`  
**And** the GUI tree shows the SAME new node — verify: the post-pad `TreeItem` set contains a row labelled `Pad` that the before set did not have.  

  > **Expand `Body` first — a collapsed parent hides its children from the UIA tree.** Verified
  > 2026-09-12: immediately after the pad the flat `TreeItem` set was still
  > `['TC13Pad', 'Body']`, because `Pad` is nested under `Body` and that node was collapsed. The
  > row only appeared — `['TC13Pad', 'Body', 'Origin', 'Pad']` — after expanding. **Absence from
  > the flat list is NOT a parity defect until the parent has been expanded.** The
  > `click({action:"expand"})` on the `Body` token did not land; a foreground pixel click on the
  > row's disclosure arrow (roughly `x = 21` at the row's `y`) did.
**And** the solid matches the pad length — verify: `query_mass_properties` returns a `bbox` whose z extent is 5 mm, matching the `length` sent, and the viewport solid reads as that thickness  
**And** the `Fit All` button exists because a document is open — verify: the button was found in the post-pad snapshot with label exactly `Fit All`. If it is absent, the document is not open and that is the precondition failing, not a defect  
**And** units were typed — verify: `length` was sent as `{value:5, unit:"mm"}`; a bare number is a schema reject, since the length unit enum admits only `mm`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the MCP mutation reached the human's viewport — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-10-after.png"}' | & cua-driver call get_window_state`, then `Read` `$RUN_DIR/evidence/tc-13-10-before.png` and `$RUN_DIR/evidence/tc-13-10-after.png` and say what each viewport contains. A solid is drawn where the before capture showed only the sketch. `feature_pad` returning `OK` is the claim; the pad visible in the viewport is the evidence. Do not pass on the tree row alone. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<handle>}
```
Do not save. `TC13Pad` is a scratch document built by the test.

---

### TC-13-11: feature_set_parameters via MCP changes the value shown in the GUI property panel

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_set_parameters`), `verification-design.md` §1 (mutation protocol)

**Given** `box-10-20-30` is open — verify: `mcp query_mass_properties {doc:<handle>, object:"Box"}` returns `volume` `6000.0`  
**And** `Box` is selected in the GUI so the property panel shows its `Base` group — verify: a snapshot lists a `Placement` row and a `Label` row  

**When** the property panel is snapshotted before the change  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-11-before.png"}' | & cua-driver call get_window_state
```
**And** the driving parameter is changed through MCP  
```bash
mcp preview_dry_run {doc:<handle>, operation:{tool:"feature_set_parameters", args:{doc:<handle>, feature:"Box", parameters:{Length:{value:25, unit:"mm"}}}}}
mcp feature_set_parameters {doc:<handle>, feature:"Box", parameters:{Length:{value:25, unit:"mm"}}, confirm:{preview_id:"<token>"}}
```
**And** the property panel is re-snapshotted  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-11-after-change.png"}' | & cua-driver call get_window_state
```
**And** the MCP side is read  
```bash
mcp query_mass_properties {doc:<handle>, object:"Box"}
mcp verify_recompute {doc:<handle>}
```

**Then** the mutation succeeded — verify: `feature_set_parameters` returns `OK` with `rolled_back` false  
**And** the GUI property panel shows the new value — verify: the `Length` row in the post-change snapshot reads `25`, where the before snapshot read `10`  
**And** MCP geometry follows the change — verify: `query_mass_properties` returns `volume` `15000.0` (25 x 20 x 30), not `6000.0`, and a `bbox` x extent of 25 mm  
**And** the two sides agree on the driving value — verify: the number in the GUI `Length` row equals the value in the MCP `parameters` argument that was accepted  
**And** the confirm gate was honored — verify: repeating `feature_set_parameters` WITHOUT `confirm` returns the refusal `this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id`  
**And** the recompute state agrees — verify: `verify_recompute` reports the same object set as touched or clean as the GUI tree markers show in `$RUN_DIR/evidence/tc-13-11-after-change.png`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the MCP parameter change reached the human's screen — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-11-after.png"}' | & cua-driver call get_window_state`, then `Read` `$RUN_DIR/evidence/tc-13-11-before.png` and `$RUN_DIR/evidence/tc-13-11-after.png` and read the `Length` row value off each image. Confirm it changed from `10` to `25`. `feature_set_parameters` returning `OK` is the claim; the changed row in the picture is the evidence. An unchanged panel with a successful MCP call is a parity defect. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<handle>}
```
Do not save. `box-10-20-30` is a committed golden model and its `Length` must stay 10 mm on disk.

---

### TC-13-12: document_undo via MCP reverts the GUI tree and viewport

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (undo is refused, never silently no-op), `mcp-tools-design.md` §1.1 (document handles)

**Given** a document carrying one MCP mutation is open — reuse the TC-13-11 state — verify: `mcp query_mass_properties {doc:<handle>, object:"Box"}` returns `volume` `15000.0` after the `Length` change  
**And** the GUI shows that mutated state — verify: a snapshot's `Length` property row reads `25`  

**When** the GUI is snapshotted in its mutated state and the viewport captured  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-12-before-undo.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-12-mutated.png"}' | & cua-driver call get_window_state
```
**And** the undo is issued through MCP  
```bash
mcp document_undo {doc:<handle>}
```
**And** the window is re-snapshotted and the viewport captured again  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-12-after-undo.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-12-reverted.png"}' | & cua-driver call get_window_state
```
**And** the MCP side is read  
```bash
mcp query_mass_properties {doc:<handle>, object:"Box"}
mcp query_tree_summary {doc:<handle>}
```

**Then** the undo succeeded — verify: `document_undo` returns `OK`, not a silent no-op  
**And** MCP geometry reverted — verify: `query_mass_properties` returns `volume` `6000.0` and the original `bbox` 0 to 10 by 0 to 20 by 0 to 30 mm  
**And** the GUI property panel reverted — verify: the `Length` row in the post-undo snapshot reads `10` again, where the pre-undo snapshot read `25`  
**And** the tree survived — verify: `query_tree_summary` names `Box` with the same node set as before the mutation, and the GUI `TreeItem` set matches it  
**And** both sides agree the document is clean — verify: `mcp verify_recompute {doc:<handle>}` reports no touched object, and the GUI tree in `$RUN_DIR/evidence/tc-13-12-after-undo.png` shows no touched marker  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the undo reached the human's viewport — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-12-after.png"}' | & cua-driver call get_window_state`, then `Read` `$RUN_DIR/evidence/tc-13-12-mutated.png` and `$RUN_DIR/evidence/tc-13-12-after.png` and compare the width of the solid in each. The solid is visibly narrower after the undo. `document_undo` returning `OK` is the claim; the narrower solid in the picture is the evidence. A reverted number with an unchanged viewport is a parity defect. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-13: document_close via MCP removes the GUI tab and tree root

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.1 (handle release), `data-contracts-design.md` §9 (closed status set)

**Given** two documents are open — verify: `mcp document_list {}` returns two entries and both handles read `OK` from `mcp query_tree_summary`  

**When** the GUI is snapshotted with both documents present  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-13-before.png"}' | & cua-driver call get_window_state
```
**And** document A is closed through MCP  
```bash
mcp document_close {doc:<handleA>}
```
**And** the GUI is re-snapshotted  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-13-after-close.png"}' | & cua-driver call get_window_state
```
**And** both sides are read  
```bash
mcp document_list {}
mcp query_tree_summary {doc:<handleA>}
mcp query_tree_summary {doc:<handleB>}
```

**Then** the close succeeded — verify: `document_close` returns `OK`  
**And** the GUI tree root is gone — verify: the document A row is present in the before `TreeItem` set and ABSENT from the post-close set  
**And** the GUI tab is gone — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"<document A label>"},"exists":false}}]}' | & cua-driver call verify_state` returns `satisfied`. A result of `unknown` is inconclusive, never a pass; re-snapshot and judge `$RUN_DIR/evidence/tc-13-13-after-close.png` directly instead  
**And** `document_list` agrees with the GUI — verify: `document_list` returns one entry, and its handle is `<handleB>`  
**And** the stale handle refuses cleanly — verify: `query_tree_summary {doc:<handleA>}` returns `INVALID_INPUT`, not `WORKER_CRASHED` and not `OK` with empty data  
**And** document B is untouched on both sides — verify: `query_tree_summary {doc:<handleB>}` returns `OK`, and its tree root is still present in `$RUN_DIR/evidence/tc-13-13-after-close.png`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handleB>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the MCP close reached the human's screen — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-13-after.png"}' | & cua-driver call get_window_state`, then `Read` `$RUN_DIR/evidence/tc-13-13-before.png` and `$RUN_DIR/evidence/tc-13-13-after.png` and list the tabs and tree roots you can see in each. Document A is in the tab bar and Model panel in the before image and absent in the after image, and document B's tree root is still shown. `document_close` returning `OK` is the claim; the missing tab in the picture is the evidence. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<handleB>}
```
Do not save either document.

---

### TC-13-14: A GUI visibility toggle is observed by MCP

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.2 (tree text `v`/`-` marker), `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Given** `box-10-20-30` is open and hidden as shipped — verify: the tree text (`content[1]`) of `mcp query_tree_summary {doc:<handle>}` is `- [FEATURE] Box`  
**And** the FreeCAD Model tree is exposed in the accessibility tree — verify: a snapshot lists a `Tree` role element  

**When** the MCP state is recorded before any GUI action  
```bash
mcp query_tree_summary {doc:<handle>}
```
**And** the `Box` row is selected: re-snapshot first and match on `role == "TreeItem"` AND `label == "Box"`  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Box TreeItem token from this snapshot>"}' | & cua-driver call click
```
**And** the window is re-snapshotted AGAIN, the row re-matched on role and label, then `space` sent  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Box TreeItem token from THIS snapshot>","key":"space"}' | & cua-driver call press_key
```
Do NOT reuse the earlier token. A token that shifted by one may be the inline rename editor, and
a `space` sent there edits the Label instead of the visibility flag — see TC-13-15.
**And** MCP is read, which is the only verdict  
```bash
mcp query_tree_summary {doc:<handle>}
```
If the `Box` line still starts `-`, repeat the `space` action once with `"delivery_mode":"foreground"`
and read MCP again. Record every attempt.

**Then** MCP sees the flip — verify: the post-toggle tree text is `v [FEATURE] Box`, where the pre-toggle read was `- [FEATURE] Box`  
**And** only the marker changed — verify: apart from the first character, the post-toggle line equals the pre-toggle line  
**And** `unverifiable` was not treated as a verdict — verify: the `press_key` result is recorded verbatim, including `effect` and any `escalation`, and the pass or fail came from the MCP re-read only. This route is confirmed to report `effect:"unverifiable"` with `escalation:{reason:"delivery_failed", target:"foreground"}` and still land  
**And** no geometry changed — verify: `mcp query_mass_properties {doc:<handle>, object:"Box"}` returns `volume` `6000.0` before and after; visibility is a view flag  
**And** the label was NOT edited — verify: the post-toggle `Box` line carries no quoted `"<Label>"`, so the Label still equals the Name `Box` and holds no space. If the label changed, the keystroke hit the rename editor and the toggle did not happen; undo with `Ctrl+Z` and re-run the `space` action from a fresh snapshot  
**And** MCP read the live flag, not a cache — verify: the post-toggle result differs from the pre-toggle result with no MCP mutation call between them  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the GUI toggle is the ground truth and the MCP flag is judged against it — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-14-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and state, from the image alone, whether the box is drawn in the viewport. The GUI action and this window are the ground truth; only after reading the image, check that the `v`/`-` marker on the MCP `Box` line agrees with what you saw. A window showing the box while the MCP line still starts `-` is a finding against the bridge, recorded in `$RUN_DIR/bugs.md`. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
Restore `Box` to hidden through the same route, confirm with `query_tree_summary`, then:
```bash
mcp document_close {doc:<handle>}
```
Do not save. The fixture ships with `Visibility=false`.

---

### TC-13-15: A GUI label rename is observed by MCP

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (label handling), `data-contracts-design.md` §9 (UTF-8 on the wire)

**Given** `box40-hole-r5` is open — verify: `mcp query_tree_summary {doc:<handle>}` reports `label` `BoxHole`  
**And** the token-shift hazard in Prerequisites Rule 2 has been read  

**When** the label is recorded on both sides  
```bash
mcp query_tree_summary {doc:<handle>}
mcp query_object {doc:<handle>, object:"BoxHole"}
```
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-15-before.png"}' | & cua-driver call get_window_state
```
**And** the inline rename editor is opened on the `BoxHole` row: re-snapshot, match on `role == "TreeItem"` AND `label == "BoxHole"`, select it, re-snapshot, then press `F2`  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<BoxHole TreeItem token from this snapshot>"}' | & cua-driver call click
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<BoxHole TreeItem token from THIS snapshot>","key":"f2"}' | & cua-driver call press_key
```
**And** the window is re-snapshotted to find the rename editor element, its whole value set, then committed with `enter`  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-15-editing.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<rename editor token from this snapshot>","value":"BoxHoleRenamed"}' | & cua-driver call set_value
'{"pid":<PID>,"element_token":"<rename editor token from this snapshot>","key":"enter"}' | & cua-driver call press_key
```
`set_value` replaces a control's whole value; `type_text` would insert at the cursor and could
append to the existing label.
**And** the MCP side is read, then reverted with `Ctrl+Z` and read again  
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

**Then** MCP sees the new label — verify: the first post-rename `query_tree_summary` reports `label` `BoxHoleRenamed`  
**And** the internal name did NOT change — verify: `mcp query_object {doc:<handle>, object:"BoxHole"}` still resolves and returns `name` `BoxHole`. A rename changes the Label, never the internal name, and the GUI status bar still reads `Valid, Internal name: BoxHole`  
**And** the GUI shows the new label — verify: a fresh snapshot's `TreeItem` set contains a row labelled `BoxHoleRenamed` and no row labelled `BoxHole`  
**And** `Ctrl+Z` reverts on both sides — verify: the second post-rename `query_tree_summary` reports `label` `BoxHole` again, and a fresh snapshot's `TreeItem` row reads `BoxHole`  
**And** MCP catches an ACCIDENTAL rename too — verify: this is the real incident this scenario is built from. On 2026-09-12 a `space` keystroke aimed at a tree row landed in the inline rename editor at the adjacent token, and `query_tree_summary` immediately reported `label: " "`. Reproduce it deliberately: send `space` to the rename editor token, read `query_tree_summary`, confirm `label` is `" "`, then `Ctrl+Z` with `delivery_mode:"foreground"` and confirm the label is restored  
**And** a value readback from the editor is NOT proof — verify: the pass comes from `query_tree_summary` after the `enter` commit, not from the editor echoing its own value. An editor that shows the new text while MCP still reports the old label is the parity defect this assertion exists to catch  
**And** no geometry changed — verify: `mcp query_mass_properties {doc:<handle>, object:"BoxHole"}` returns `volume` `15214.601836602547` throughout  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the GUI rename is the ground truth and the MCP read is judged against it — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-15-after.png"}' | & cua-driver call get_window_state`, then `Read` `$RUN_DIR/evidence/tc-13-15-before.png`, `$RUN_DIR/evidence/tc-13-15-editing.png`, and `$RUN_DIR/evidence/tc-13-15-after.png`. The editing image shows the inline editor open on the row. Read the tree row label off the after image; only then check that `query_tree_summary` reports that same label. A rename claimed without the editor ever opening is not proven, and a window label that MCP does not match is a finding against the bridge, recorded in `$RUN_DIR/bugs.md`. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
Confirm the label is `BoxHole` again with `mcp query_tree_summary {doc:<handle>}`, then:
```bash
mcp document_close {doc:<handle>}
```
Do not save. A saved rename would corrupt the committed golden model.

---

### TC-13-16: A GUI-opened document is seen by MCP and gets a handle

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.1 (document_list adoption), `data-contracts-design.md` §9 (AD-20)

**Given** `cylinder-r5-h20` is NOT open — verify: `mcp document_list {}` returns no entry for it  
**And** at least one document is already open, so the `Open…` toolbar button exists in the UIA tree — verify: a snapshot lists a Button labelled `Open…`. With no document open the toolbar buttons are absent, which is a precondition, not a defect  

**When** the MCP document set is recorded before  
```bash
mcp document_list {}
```
**And** the `Open…` toolbar button is pressed: re-snapshot first and match on `role == "Button"` AND `label == "Open…"`  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Open… Button token from this snapshot>"}' | & cua-driver call click
```
**And** the file dialog is driven: enumerate it with `list_windows`, snapshot it, set the filename field to the ABSOLUTE path, then press its Open button by `element_token`  
```bash
'{"pid":<PID>}' | & cua-driver call list_windows
'{"pid":<PID>,"window_id":<dialogWID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-16-dialog.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<filename Edit token from this snapshot>","value":"$PROJECT_ROOT\\benchmarks\\g0\\golden-models\\cylinder-r5-h20.FCStd"}' | & cua-driver call set_value
'{"pid":<PID>,"window_id":<dialogWID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Open Button token from THIS snapshot>"}' | & cua-driver call click
```
**And** the MCP side is read  
```bash
mcp document_list {}
mcp query_tree_summary {doc:<newHandle>}
mcp query_mass_properties {doc:<newHandle>, object:"<Object>"}
```

**Then** the GUI opened it — verify: a fresh snapshot's `TreeItem` set contains a row for the `cylinder-r5-h20` document that the before state did not have. Read `$RUN_DIR/evidence/tc-13-16-dialog.png` to confirm the dialog was the one driven  
**And** MCP adopted it — verify: the post-open `document_list` returns one more entry than the before read, naming `cylinder-r5-h20`  
**And** the new entry carries a usable handle — verify: `query_tree_summary` on that handle returns `OK` and names the object  
**And** the geometry agrees with the reference — verify: `query_mass_properties` returns `volume` `1570.7963` within `rel: 0.001`, and a `bbox` of 10 x 10 x 20 mm  
**And** the adopted handle behaves like an MCP-opened one — verify: `mcp query_screenshot {doc:<newHandle>, view:{include:["<Object>"]}}` returns a PNG with `rendered_objects` naming the object; read the PNG and confirm a cylinder, not a box  
**And** no existing handle broke — verify: every handle from the before read still returns `OK` from `mcp query_tree_summary`  
**And** the toolbar route was used, not a menu — verify: the run evidence records the `Open…` Button `element_token` and `route: accessibility`. `invoke_menu` menu paths for this build are refused beyond the confirmed labels  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<newHandle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the GUI-opened document is the ground truth and the MCP adoption is judged against it — verify: fit FIRST, then capture, so the window and the render share a camera: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-16-after.png"}' | & cua-driver call get_window_state`. `Read` the PNG and name, from the image alone, which document the tab bar and Model panel show. Confirm it is `cylinder-r5-h20`; only then check that `document_list` adopted that same document, and compare the window against the `query_screenshot` render of the same handle. Where they disagree the window wins, and the disagreement is recorded as a finding against the bridge in `$RUN_DIR/bugs.md`. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<newHandle>}
```
Do not save.

---

### TC-13-17: A GUI-side recompute agrees with verify_recompute

**Priority**: High
**Design Ref**: `verification-design.md` §6.3 (recompute grading), `integration-mcp-freecad.md` §3 (GUI mode, addon lifecycle)

**Given** a document with at least one object that can be left touched is open — verify: `mcp document_list {}` returns a handle and `mcp verify_recompute {doc:<handle>}` returns `OK`  
**And** the document has a pending recompute. Use the TC-13-11 route to change a driving parameter without recomputing — verify: `mcp verify_recompute {doc:<handle>}` names at least one touched object  

**When** the touched set is recorded from MCP and the tree markers from the GUI  
```bash
mcp verify_recompute {doc:<handle>}
```
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-17-touched.png"}' | & cua-driver call get_window_state
```
**And** the recompute is triggered from the GUI: re-snapshot, select the document root row on `role == "TreeItem"`, then use the `Tree View Actions` toolbar button to reach the refresh command  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<document root TreeItem token from this snapshot>"}' | & cua-driver call click
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<Tree View Actions Button token from THIS snapshot>"}' | & cua-driver call click
```
If the popup entry cannot be enumerated — Qt popups are not top-level windows — fall back to
`mcp document_recompute {doc:<handle>}` and record that the GUI route was unavailable. That is a
route limitation, recorded, not a product defect.
**And** both sides are re-read  
```bash
mcp verify_recompute {doc:<handle>}
```
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-17-clean.png"}' | & cua-driver call get_window_state
```

**Then** both sides agree the document was dirty — verify: the first `verify_recompute` names touched objects, AND `$RUN_DIR/evidence/tc-13-17-touched.png` shows the touched marker on the same rows  
**And** both sides agree it is clean after — verify: the second `verify_recompute` reports no touched object, AND `$RUN_DIR/evidence/tc-13-17-clean.png` shows no touched marker  
**And** the failing set is identical — verify: any object MCP names as failing is an object the GUI tree marks with an error, and no object is marked on one side only  
**And** the geometry settled — verify: `mcp query_mass_properties {doc:<handle>, object:"<Object>"}` returns the value implied by the changed parameter, not the pre-change value  
**And** the route actually used is recorded — verify: the run evidence states whether the GUI button route or the `document_recompute` fallback produced the recompute  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the tree markers are the ground truth and the MCP verdict is judged against them — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-17-after.png"}' | & cua-driver call get_window_state`, then `Read` `$RUN_DIR/evidence/tc-13-17-touched.png` and `$RUN_DIR/evidence/tc-13-17-after.png` and say which rows carry the touched marker in each. The touched marker is present before and absent after; only then check that `verify_recompute` agrees with what you saw. A cleared MCP touched set with unchanged tree markers is a parity defect. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_undo {doc:<handle>}
mcp document_close {doc:<handle>}
```
Do not save.

---

### TC-13-18: A GUI-side close removes the document from MCP and invalidates the handle

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.1 (handle resolution), `data-contracts-design.md` §9 (closed status set)

**Given** two documents are open — verify: `mcp document_list {}` returns two entries; both handles return `OK` from `mcp query_tree_summary`  
**And** neither document has unsaved changes, so no save prompt appears — verify: `mcp verify_recompute {doc:<handleA>}` reports no touched object  

**When** both handles and the GUI state are recorded  
```bash
mcp document_list {}
```
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-18-before.png"}' | & cua-driver call get_window_state
```
**And** document A is closed from the GUI: re-snapshot, select its root row matched on `role == "TreeItem"` and its label, then use `Ctrl+W` delivered to that row  
```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<document A root TreeItem token from this snapshot>"}' | & cua-driver call click
'{"pid":<PID>,"keys":["ctrl","w"],"delivery_mode":"foreground"}' | & cua-driver call hotkey
```
If a save prompt appears, enumerate it with `list_windows`, snapshot it, and click its discard
button by `element_token`. Never accept a save on a golden model.
**And** the GUI state is confirmed and the MCP side read  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-18-after-close.png"}' | & cua-driver call get_window_state
```
```bash
mcp document_list {}
mcp query_tree_summary {doc:<handleA>}
mcp query_mass_properties {doc:<handleA>, object:"<Object>"}
mcp document_close {doc:<handleA>}
```

**Then** the GUI closed it — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"<document A label>"},"exists":false}}]}' | & cua-driver call verify_state` returns `satisfied`. `unknown` is inconclusive, not a pass — judge `$RUN_DIR/evidence/tc-13-18-after-close.png` directly instead  
**And** `document_list` dropped it — verify: the post-close `document_list` returns one entry, and its handle is `<handleB>`  
**And** every stale read refuses with INVALID_INPUT — verify: `query_tree_summary` and `query_mass_properties` on `<handleA>` both return `INVALID_INPUT`, not `WORKER_CRASHED` and not `OK` with empty data  
**And** the stale close is also a clean refusal — verify: `document_close {doc:<handleA>}` returns `INVALID_INPUT`, not a crash  
**And** FreeCAD and the bridge survived — verify: `Get-Process -Name freecad` reports the same pid, and `mcp query_capabilities {}` returns `OK`  
**And** document B is unharmed on both sides — verify: `mcp query_tree_summary {doc:<handleB>}` returns `OK`, and its tree root is still visible in `$RUN_DIR/evidence/tc-13-18-after-close.png`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handleB>" }` returns `OK`; if it does not, or if the scenario is grading GUI-side ground truth, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. Rule 4 records `invoke_menu(["View","Fit All"])` as REFUSED on this build with `menu_path_unavailable` at segment 1; when it is refused, fall back to the `Fit All` toolbar button by `element_token`, which is also GUI-side and touches none of the code under test  
**And** *(visual)* the GUI close is the ground truth and the MCP document set is judged against it — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-13-18-after.png"}' | & cua-driver call get_window_state`, then `Read` `$RUN_DIR/evidence/tc-13-18-before.png` and `$RUN_DIR/evidence/tc-13-18-after.png` and list the tabs and tree roots you can see in each. Document A's tab and tree root are present before and absent after, and document B is still shown; only then check that the `document_list` entry for document A disappeared to match. A window without document A while MCP still lists it is a finding against the bridge, recorded in `$RUN_DIR/bugs.md`. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close {doc:<handleB>}
```
Do not save either document.

---

## Divergence handling

- A number that matches while the pixels disagree is a **defect**, not a tolerance. Every geometry
  and render scenario here carries a visual assertion for that reason. Record the exact difference
  and stop; do not pass on numbers alone.
- Where the window and the MCP report disagree, **the window wins**. Per Rule 0 the bridge is the
  code under test, so an MCP envelope field, status, or `query_screenshot` render is a claim, never
  the test result. Record the disagreement in `$RUN_DIR/bugs.md` as a finding against the bridge.
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
  `query_tree_summary`, and re-run the step from a fresh snapshot. TC-13-15 grades this on
  purpose; anywhere else it invalidates the step.
- A mutated golden model that reaches `document_save` invalidates every later run in the suite.
  Every scenario that mutates a fixture closes without saving, and the Cleanup block says so.
