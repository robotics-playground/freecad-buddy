# TC-06: Render and GUI Visual Fidelity

Confirms `query_screenshot` depicts the object as FreeCAD itself draws it, not merely that it wrote
a non-empty PNG with plausible numbers. The MCP render builds its own Coin scene — its own camera,
its own lighting, its own white background — and is NOT a capture of the live viewport, so
comparing a render only against another render proves nothing. Every rendering scenario in this
file grabs the real FreeCAD viewport through Win32 `PrintWindow` and compares the two images.
Scenarios 06 and 02 also drive the GUI with `cua-driver` so the live viewport state and the render
are set from opposite sides.

## Prerequisites
- [ ] FreeCAD 1.1.1 GUI is open (verify: `Get-Process -Name freecad | Select-Object Id,MainWindowTitle` lists one process with title `FreeCAD 1.1.1`)
- [ ] The MCP proxy serves `:8765` — the addon auto-spawns it on FreeCAD start (verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row). No manual `serve` command. If absent, restart FreeCAD or read `%APPDATA%/FreeCAD/v1-1/freecad-buddy/addon.log`.
- [ ] `cua-driver` is reachable and in the interactive session (verify: `cua-driver status` reports the daemon and NOT Session 0)
- [ ] The render ladder reports a usable mode (verify: `mcp query_capabilities {}` returns `render` = `gui_constructed`)
- [ ] The FreeCAD `(pid, window_id)` pair is known (verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns the window whose `title` is `FreeCAD 1.1.1`)

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

### TC-06-01: MCP render matches the live viewport

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Preconditions**:
- [ ] A document with one shape-bearing object is open (verify: `mcp document_list {}` returns a handle; `mcp query_tree_summary {doc:<handle>}` names the object)
- [ ] The object's geometry is known (verify: `mcp query_mass_properties {doc:<handle>}` returns `volume` and `bbox`)

**Steps**:
1. Set the GUI camera through the **toolbar buttons**, not the View menu and not keystrokes.
   Snapshot first, then act on a token from that same snapshot.
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc0601_pre.png"}' | & cua-driver call get_window_state
   # from that response take the element_token whose label is exactly "Standard Views",
   # then the token whose label is exactly "Fit All"
   '{"pid":<PID>,"element_token":"<Standard Views token>"}' | & cua-driver call click
   '{"pid":<PID>,"element_token":"<Fit All token>"}'        | & cua-driver call click
   ```
   **Verified 2026-09-12 — use the toolbar route.** `invoke_menu` with
   `["View","Standard views","Isometric"]`, `["View","Fit all"]` and `["View","Fit All"]` are all
   **refused** with `menu_path_unavailable` at segment 1 on FreeCAD 1.1.1; only `["View","Zoom"]`
   resolves, and Qt renders the open popup as a window that is not enumerable from a snapshot, so
   the leaf labels cannot be discovered that way. Viewport keystrokes (`press_key` "0") did **not**
   land even at `delivery_mode:"foreground"`. A `Fit All` toolbar click returns
   `route: "accessibility"` and demonstrably reframes the view.
   These buttons exist in the UIA tree **only while a document is open**.
2. Capture the MCP render:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso", include:["<Object>"]}}
   ```
   Copy the returned `render.resource_link` PNG to `_automation/tc0601_mcp.png`.
3. Capture the live viewport with the shared recipe to `_automation/tc0601_viewport.png`.
4. Open both PNGs side by side and compare.

**Checkpoints**:
- [ ] CP1: Same object present — verify: both images show the same silhouette, and `mcp query_screenshot` returned `scene.rendered_objects` containing `<Object>`
- [ ] CP2: Proportions match the geometry — verify: the rendered extents agree with the `bbox` from `mcp query_mass_properties {doc:<handle>}` (a 60x40x5 mm bracket reads flat and wide, not cubic)
- [ ] CP3: Camera and framing consistent — verify: the iso orientation in `tc0601_mcp.png` matches `tc0601_viewport.png`; any axis flip or off-centre framing is recorded
- [ ] CP4: No missing or extra geometry — verify: no object visible in the viewport is absent from the MCP render, and no `PartDesign::Body`, `Sketcher::SketchObject`, or `App::Origin` child leaked into it
- [ ] CP5: Anti-aliasing honored — verify: edges are smooth when AA is configured; read the configured value with `Select-String AntiAliasing "$env:APPDATA/FreeCAD/v1-1/user.cfg"`
- [ ] CP6: Shading not black-sided — verify: faces angled away from the camera render as shaded grey, not pure black. A black side face means the camera-aligned headlight was lost; compare tone against the lit sides in `tc0601_viewport.png`

**Cleanup**:
```bash
rm -f _automation/tc0601_*.png
```

---

### TC-06-02: Each named camera orients correctly

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Preconditions**:
- [ ] A document with one asymmetric object is open, so front and back are distinguishable (verify: `mcp query_mass_properties {doc:<handle>}` returns a `bbox` with three different extents)

**Steps**:
1. Render each of the seven named cameras to its own file:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
   mcp query_screenshot {doc:<handle>, view:{camera:"front"}}
   mcp query_screenshot {doc:<handle>, view:{camera:"top"}}
   mcp query_screenshot {doc:<handle>, view:{camera:"right"}}
   mcp query_screenshot {doc:<handle>, view:{camera:"left"}}
   mcp query_screenshot {doc:<handle>, view:{camera:"back"}}
   mcp query_screenshot {doc:<handle>, view:{camera:"bottom"}}
   ```
   Copy each `render.resource_link` to `_automation/tc0602_<camera>.png`.
2. For each camera, set the matching GUI standard view through the **`Standard Views` toolbar
   button**, then grab the viewport:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc0602_tree.png"}' | & cua-driver call get_window_state
   # act on the token from THAT snapshot whose label is exactly "Standard Views"
   '{"pid":<PID>,"element_token":"<Standard Views token>"}' | & cua-driver call click
   ```
   Then run the shared viewport recipe to `_automation/tc0602_front_viewport.png`. Repeat for Top,
   Right, Left, Rear, Bottom, Isometric.

   Do **not** use `invoke_menu(["View","Standard views",…])` — that path is refused at segment 1 on
   this build (see TC-13-01 and `APPENDIX-B`). Re-snapshot before every click: element tokens are
   per-snapshot, and an adjacent token can be the tree's inline rename editor rather than the
   control you intended.

**Checkpoints**:
- [ ] CP1: All seven cameras accepted — verify: each `mcp query_screenshot` call returns `status` `OK` with a non-null `render.resource_link`
- [ ] CP2: Each render matches its GUI counterpart — verify: `tc0602_front.png` and `tc0602_front_viewport.png` show the same face; repeat for all seven pairs
- [ ] CP3: Opposite pairs are mirrored, not identical — verify: `tc0602_front.png` differs from `tc0602_back.png`, `tc0602_top.png` from `tc0602_bottom.png`, `tc0602_left.png` from `tc0602_right.png`
- [ ] CP4: `iso` is a three-quarter view — verify: `tc0602_iso.png` shows three faces, matching the GUI Isometric viewport
- [ ] CP5: No axis flip — verify: for every pair, the up direction in the render agrees with the up direction in the viewport grab
- [ ] CP6: An unknown camera is rejected — verify: `mcp query_screenshot {doc:<handle>, view:{camera:"oblique"}}` returns `INVALID_INPUT` (the `camera` enum admits only the seven names plus `custom`)

**Cleanup**:
```bash
rm -f _automation/tc0602_*.png
```

---

### TC-06-03: include and exclude select the right objects

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.9 (view-controlled render)

**Preconditions**:
- [ ] A document with at least two shape-bearing objects and one `PartDesign::Body` is open (verify: `mcp query_tree_summary {doc:<handle>, depth:2}` lists both leaf features and the Body)

**Steps**:
1. Render the default scene with no `include`:
   ```bash
   mcp query_screenshot {doc:<handle>}
   ```
2. Render only the first object:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{include:["<ObjectA>"]}}
   ```
3. Render everything except the first object:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{exclude:["<ObjectA>"]}}
   ```
4. Ask for an object that does not exist:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{include:["NoSuchObject"]}}
   ```

**Checkpoints**:
- [ ] CP1: Default scene skips containers — verify: step 1 `scene.rendered_objects` contains no `PartDesign::Body` name, no `Sketcher::SketchObject` name, and no `App::Origin`/`App::Line`/`App::Plane`/`App::Point` name
- [ ] CP2: `include` is the exact set — verify: step 2 `scene.rendered_objects` equals `["<ObjectA>"]`
- [ ] CP3: `exclude` removes exactly one — verify: step 3 `scene.rendered_objects` equals the step-1 list minus `<ObjectA>`
- [ ] CP4: The images agree with the lists — verify: the step-2 PNG shows one solid and the step-3 PNG shows the rest; neither shows a datum plane
- [ ] CP5: An unknown name fails closed — verify: step 4 returns `INVALID_INPUT` with detail `unknown object: NoSuchObject`
- [ ] CP6: An explicit `include` of the Body still renders it — verify: `mcp query_screenshot {doc:<handle>, view:{include:["<Body>"]}}` returns `scene.rendered_objects` containing `<Body>`, proving the skip shapes only the automatic set

**Cleanup**:
```bash
rm -f _automation/tc0603_*.png
```

---

### TC-06-04: styles transparency and color are honored

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.9 (view-controlled render)

**Preconditions**:
- [ ] A document with two overlapping or adjacent solids is open (verify: `mcp query_tree_summary {doc:<handle>}` names both)

**Steps**:
1. Render with an opaque red front object:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"front", styles:[{object:"<ObjectA>", color:[1.0,0.0,0.0]}]}}
   ```
2. Render the same view with the front object at 80 percent transparency:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"front", styles:[{object:"<ObjectA>", color:[1.0,0.0,0.0], transparency:80}]}}
   ```
3. Send a transparency outside the range:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{styles:[{object:"<ObjectA>", transparency:150}]}}
   ```
4. Send a two-element color:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{styles:[{object:"<ObjectA>", color:[1.0,0.0]}]}}
   ```

**Checkpoints**:
- [ ] CP1: Color applied — verify: `<ObjectA>` renders red in the step-1 PNG while the other object keeps its own color
- [ ] CP2: Transparency applied — verify: the object behind `<ObjectA>` is visible through it in the step-2 PNG and not in the step-1 PNG
- [ ] CP3: Transparency 0 and 100 both accepted — verify: `mcp query_screenshot {doc:<handle>, view:{styles:[{object:"<ObjectA>", transparency:0}]}}` and the same call with `transparency:100` both return `OK`
- [ ] CP4: Out-of-range transparency rejected — verify: step 3 returns `INVALID_INPUT` (schema `maximum: 100`)
- [ ] CP5: Wrong-length color rejected — verify: step 4 returns `INVALID_INPUT` (schema `minItems: 3, maxItems: 3`)
- [ ] CP6: Styling a nonexistent object fails closed — verify: `mcp query_screenshot {doc:<handle>, view:{styles:[{object:"NoSuchObject", color:[0,0,1]}]}}` returns `INVALID_INPUT` with detail `unknown object: NoSuchObject`
- [ ] CP7: Styles do not touch the live viewport — verify: a viewport grab taken after step 2 with the shared recipe shows `<ObjectA>` in its ORIGINAL color, not red; the render must never mutate the user's view

**Cleanup**:
```bash
rm -f _automation/tc0604_*.png
```

---

### TC-06-05: focus and highlight frame and accent the target

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.9 (view-controlled render)

**Preconditions**:
- [ ] A document with a solid whose face count is known is open (verify: `mcp verify_shape {doc:<handle>}` reports the face count)

**Steps**:
1. Render the whole scene, then focus one face:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
   mcp query_screenshot {doc:<handle>, view:{camera:"iso", focus:{object:"<ObjectA>", element_type:"face", index:0}}}
   ```
2. Highlight the object:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso", highlight:{object:"<ObjectA>"}}}
   ```
3. Focus an out-of-range face index:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{focus:{object:"<ObjectA>", element_type:"face", index:9999}}}
   ```
4. Send a partial sub-element selector:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{focus:{object:"<ObjectA>", element_type:"face"}}}
   ```

**Checkpoints**:
- [ ] CP1: Focus frames tighter — verify: the focused PNG fills more of the frame with `<ObjectA>` than the unfocused PNG
- [ ] CP2: Focus echo carries the sub-element — verify: step 1 second call returns `scene.focused_on` equal to `{object:"<ObjectA>", element_type:"face", index:0}`
- [ ] CP3: Highlight accents the object — verify: `<ObjectA>` renders in the accent orange in the step-2 PNG while other objects keep their color
- [ ] CP4: An unresolvable index falls back honestly — verify: step 3 returns `OK` with `scene.focused_on` equal to `{object:"<ObjectA>"}` only, with no `element_type` or `index` key; the response never claims a framing that did not happen
- [ ] CP5: A partial selector is rejected — verify: step 4 returns `INVALID_INPUT` with detail `sub-element selector requires both element_type and index`
- [ ] CP6: Mixed selector forms are rejected — verify: `mcp query_screenshot {doc:<handle>, view:{focus:{object:"<ObjectA>", mapped_name:"Face1", element_type:"face", index:0}}}` returns `INVALID_INPUT` with detail `selector cannot carry both mapped_name and element_type/index`

**Cleanup**:
```bash
rm -f _automation/tc0605_*.png
```

---

### TC-06-06: The default scene honors live GUI Visibility

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Preconditions**:
- [ ] A document with two visible shape-bearing objects is open (verify: `mcp query_tree_summary {doc:<handle>}` reports `visibility` true for both)
- [ ] The FreeCAD model tree is exposed in the accessibility tree (verify: `'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state` lists a `Tree` role element)

**Steps**:
1. Render the default scene and record `scene.rendered_objects`:
   ```bash
   mcp query_screenshot {doc:<handle>}
   ```
2. Re-snapshot the window, then select `<ObjectB>` in the model tree by its `element_token` from that snapshot:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"_automation/tc0606_tree.png"}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<token from this snapshot>"}' | & cua-driver call click
   ```
   Use `element_token`, never a bare `element_index`; indices are per-snapshot and keyed on `(pid, window_id)`.
3. Hide the selected object through the GUI. Re-snapshot, match the tree item by `role == "TreeItem"`
   **and** its exact `label`, then send `space` to that token:
   ```bash
   '{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
   '{"pid":<PID>,"element_token":"<TreeItem token for ObjectB>","key":"space","delivery_mode":"foreground"}' | & cua-driver call press_key
   ```
   **This route is unreliable and MUST be verified, then retried if it did not land** (observed
   2026-09-12: the same call landed on one attempt and silently did nothing on another, in both
   cases reporting `effect: "unverifiable"`). Confirm with
   `mcp query_tree_summary {doc:<handle>}` and repeat until `visibility` actually flips.

   **Hazard — match the token by role and label, never by position.** Tokens are per-snapshot. In a
   live run an adjacent token was the tree's inline **rename editor**, and the `space` keystroke
   typed a space into the object's `Label`; `query_tree_summary` then reported `label: " "`.
   Recover with a foreground `Ctrl+Z` and re-verify the label before continuing.
4. Render the default scene again, then render `<ObjectB>` explicitly:
   ```bash
   mcp query_screenshot {doc:<handle>}
   mcp query_screenshot {doc:<handle>, view:{include:["<ObjectB>"]}}
   ```
5. Restore visibility by repeating step 3, and confirm with the bridge.

**Checkpoints**:
- [ ] CP1: The hide landed in the GUI — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"<ObjectB>"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`. A result of `unknown` is NOT success — record the scenario as inconclusive and stop.
- [ ] CP2: The bridge sees the new visibility — verify: `mcp query_tree_summary {doc:<handle>}` reports `visibility` false for `<ObjectB>`
- [ ] CP3: The hidden object drops out of the default render — verify: step 4 first call returns `scene.rendered_objects` WITHOUT `<ObjectB>`
- [ ] CP4: An explicit include still renders it — verify: step 4 second call returns `scene.rendered_objects` equal to `["<ObjectB>"]` with a non-null `render.resource_link`
- [ ] CP5: The default render matches the viewport — verify: a viewport grab taken after step 3 shows the same object set as the step-4 default render
- [ ] CP6: Visibility restored — verify: after step 5, `mcp query_tree_summary {doc:<handle>}` reports `visibility` true for `<ObjectB>` and the default render lists it again

**Cleanup**:
```bash
rm -f _automation/tc0606_*.png
```
Restore `<ObjectB>` visibility in the GUI before leaving the scenario.

---

### TC-06-07: camera custom requires exactly four numbers

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.9 (view-controlled render)

**Preconditions**:
- [ ] A document with one shape-bearing object is open (verify: `mcp document_list {}` returns a handle)

**Steps**:
1. Render with a valid custom quaternion:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"custom", custom_orientation:[0.424708,0.17592,0.339851,0.820473]}}
   ```
2. Render `custom` with no orientation at all:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"custom"}}
   ```
3. Send a three-element orientation:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"custom", custom_orientation:[0.0,0.0,1.0]}}
   ```
4. Send a five-element orientation, then a zero quaternion:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"custom", custom_orientation:[0,0,0,1,0]}}
   mcp query_screenshot {doc:<handle>, view:{camera:"custom", custom_orientation:[0,0,0,0]}}
   ```

**Checkpoints**:
- [ ] CP1: A valid quaternion renders — verify: step 1 returns `OK` with a non-null `render.resource_link`
- [ ] CP2: That quaternion equals the iso preset — verify: the step-1 PNG is visually the same view as `mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}`
- [ ] CP3: A missing orientation is rejected — verify: step 2 returns `INVALID_INPUT` with detail `camera 'custom' requires custom_orientation (a 4-float quaternion)`
- [ ] CP4: Too few numbers rejected — verify: step 3 returns `INVALID_INPUT` (schema `minItems: 4`)
- [ ] CP5: Too many numbers rejected — verify: step 4 first call returns `INVALID_INPUT` (schema `maxItems: 4`)
- [ ] CP6: A zero-norm quaternion is rejected — verify: step 4 second call returns `INVALID_INPUT` with detail matching `custom_orientation is degenerate (zero norm)`

**Cleanup**:
```bash
rm -f _automation/tc0607_*.png
```

---

### TC-06-08: Resolution default and cap

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.9 (view-controlled render)

**Preconditions**:
- [ ] A document with one shape-bearing object is open (verify: `mcp document_list {}` returns a handle)
- [ ] A tool that reads PNG dimensions is available (verify: `python -c "from PIL import Image; print(Image.open('<png>').size)"` runs)

**Steps**:
1. Render with no width or height, and copy the PNG to `_automation/tc0608_default.png`:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
   ```
2. Render at an explicit smaller size:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso", width:640, height:480}}
   ```
3. Request a size above the cap:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso", width:4096, height:4096}}
   ```
4. Request a non-positive size:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso", width:0}}
   ```

**Checkpoints**:
- [ ] CP1: Default is 1920x1920 — verify: `python -c "from PIL import Image; print(Image.open('_automation/tc0608_default.png').size)"` prints `(1920, 1920)`
- [ ] CP2: An explicit size is honored — verify: the step-2 PNG measures `(640, 480)`
- [ ] CP3: Above the cap is REFUSED, not clamped — verify: step 3 returns `INVALID_INPUT` from the schema `maximum: 1920`; it must NOT return `OK` with a 1920x1920 image. A silent clamp is a defect: the client asked for a resolution it did not get and was not told.
- [ ] CP4: Exactly 1920 is accepted — verify: `mcp query_screenshot {doc:<handle>, view:{width:1920, height:1920}}` returns `OK` and the PNG measures `(1920, 1920)`
- [ ] CP5: Zero is rejected — verify: step 4 returns `INVALID_INPUT`
- [ ] CP6: Only width given still renders — verify: `mcp query_screenshot {doc:<handle>, view:{width:800}}` returns `OK` and the PNG measures `(800, 1920)`

**Cleanup**:
```bash
rm -f _automation/tc0608_*.png
```

---

### TC-06-09: query_screenshot is read-only on a clean document

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.9 (view-controlled render)

**Preconditions**:
- [ ] A golden model is open and clean (verify: `mcp document_open {path:"D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"}` returns a handle; `mcp verify_recompute {doc:<handle>}` reports no touched or error object)

**Steps**:
1. Record the geometry before:
   ```bash
   mcp query_mass_properties {doc:<handle>}
   mcp query_tree_summary {doc:<handle>, depth:2}
   ```
2. Run several renders with different view options:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
   mcp query_screenshot {doc:<handle>, view:{camera:"top", styles:[{object:"Box", color:[0,1,0], transparency:50}]}}
   mcp query_screenshot {doc:<handle>, view:{camera:"front", focus:{object:"Box", element_type:"face", index:2}}}
   ```
3. Record the geometry after:
   ```bash
   mcp query_mass_properties {doc:<handle>}
   mcp query_tree_summary {doc:<handle>, depth:2}
   ```

**Checkpoints**:
- [ ] CP1: Volume unchanged — verify: step 3 `volume` equals step 1 `volume` exactly, and equals `6000.0` mm3 for `box-10-20-30`
- [ ] CP2: Centre of mass unchanged — verify: step 3 `com` equals step 1 `com` exactly
- [ ] CP3: Tree unchanged — verify: step 3 `query_tree_summary` output equals step 1 output, including every `visibility` flag
- [ ] CP4: The strict guard is active — verify: every step-2 response has `render.dirty_document` false, which is the state in which the before-equals-after mutation assertion runs
- [ ] CP5: No document dirty flag set — verify: `mcp verify_recompute {doc:<handle>}` after step 2 still reports no touched object; a render must not touch the document
- [ ] CP6: Styles did not persist — verify: a render with no `styles` after step 2 shows `Box` in its original color, so the style override lived only in the constructed scene
- [ ] CP7: No temp PNG orphaned in the system temp dir beyond the returned link — verify: `Get-ChildItem $env:TEMP -Filter "FCB_TMP_shot_*.png"` lists at most the files still referenced by the three `render.resource_link` values

**Cleanup**:
```bash
rm -f _automation/tc0609_*.png
```
```bash
mcp document_close {doc:<handle>}
```

---

### TC-06-10: A dirty document renders with dirty_document true

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Preconditions**:
- [ ] A document that can be made dirty is open (verify: `mcp document_open {path:"D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"}` returns a handle)
- [ ] The document is clean to start (verify: `mcp query_screenshot {doc:<handle>}` returns `render.dirty_document` false)

**Steps**:
1. Make the document dirty by changing a driving parameter without recomputing. Use `preview_dry_run` for the token, then `feature_set_parameters`:
   ```bash
   mcp preview_dry_run {doc:<handle>, tool:"feature_set_parameters", args:{doc:<handle>, feature:"Box", parameters:{Length:{value:25, unit:"mm"}}}}
   mcp feature_set_parameters {doc:<handle>, feature:"Box", parameters:{Length:{value:25, unit:"mm"}}, confirm:{preview_id:"<token>"}}
   ```
   If the tool recomputes on commit, instead leave a dependent object Touched and confirm with step 2 before proceeding.
2. Confirm the document is actually dirty:
   ```bash
   mcp verify_recompute {doc:<handle>}
   ```
3. Render it:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
   ```
4. Recompute and render again:
   ```bash
   mcp document_recompute {doc:<handle>}
   mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
   ```

**Checkpoints**:
- [ ] CP1: The render does NOT hard-fail — verify: step 3 returns `status` `OK`, not `SPEC_FAILED` or `INVALID_INPUT`
- [ ] CP2: The dirty flag is reported — verify: step 3 returns `render.dirty_document` true
- [ ] CP3: An image was still produced — verify: step 3 `render.resource_link` is non-null and the PNG on disk is larger than zero bytes
- [ ] CP4: The flag reaches the human-readable text — verify: step 3 `text` contains `Document dirty (pending/broken recompute)`
- [ ] CP5: The before-equals-after guard was skipped and flagged, not silently dropped — verify: `render.dirty_document` true is the ONLY signal a client gets that the read-only assertion did not run; it is present in `structured_content.render`, so a client can branch on it
- [ ] CP6: A clean document returns to the strict guard — verify: step 4 second call returns `render.dirty_document` false
- [ ] CP7: The dirty render still lists the right objects — verify: step 3 `scene.rendered_objects` equals the step-4 list

**Cleanup**:
```bash
rm -f _automation/tc0610_*.png
```
```bash
mcp document_close {doc:<handle>}
```
Do not save the modified golden model.

---

### TC-06-11: No render capability degrades honestly

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Preconditions**:
- [ ] A host with no usable render context is available. Run this scenario against the headless H1 stdio host in an environment with no GL context, NOT against the live GUI (verify: `mcp query_capabilities {}` on that host returns `render` = `none` with a reason)

**Steps**:
1. Read the capability ladder result:
   ```bash
   mcp query_capabilities {}
   ```
2. Render on that host:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
   ```
3. List any PNG the call might have written:
   ```bash
   Get-ChildItem $env:TEMP -Filter "FCB_TMP_shot_*.png"
   ```

**Checkpoints**:
- [ ] CP1: The ladder reports none — verify: step 1 returns `render` equal to `none`
- [ ] CP2: The render call still returns OK — verify: step 2 returns `status` `OK`; unavailability is reported, not raised as an error
- [ ] CP3: Availability is false — verify: step 2 returns `render.available` false
- [ ] CP4: A reason is carried — verify: step 2 `render.reason` is a non-null string naming the failure (for example `FreeCADGui not importable` or `offscreen probe render failed`)
- [ ] CP5: NO fake PNG is produced — verify: step 2 `render.resource_link` is absent from the unavailable envelope and the response carries no `images` array
- [ ] CP6: No temp file left behind — verify: step 3 lists no new `FCB_TMP_shot_*.png` created by step 2
- [ ] CP7: The scene block is empty and honest — verify: step 2 returns `scene.rendered_objects` equal to `[]` and `scene.focused_on` null

**Cleanup**:
```bash
rm -f _automation/tc0611_*.png
```

**Conditional skip**: skip when no host with `render` = `none` is available. Record the skip with
the `query_capabilities` output that shows `render` was `gui_constructed` or `offscreen` instead.

---

### TC-06-12: Anti-aliasing tracks the user's own preference

**Priority**: Medium
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Preconditions**:
- [ ] The FreeCAD GUI is open and rendering through `gui_constructed` (verify: `mcp query_capabilities {}` returns `render` = `gui_constructed`)
- [ ] The AA preference value is readable (verify: `Select-String AntiAliasing "$env:APPDATA/FreeCAD/v1-1/user.cfg"` returns the `AntiAliasing` entry, or returns nothing when the key is unset)

**Steps**:
1. Read the configured value:
   ```bash
   Select-String AntiAliasing "$env:APPDATA/FreeCAD/v1-1/user.cfg"
   ```
   The stored enum is NOT sequential. The mapping is `0 -> 0 samples`, `1 -> 1`, `2 -> 2`,
   `3 -> 4`, `4 -> 8`, `5 -> 6`. An absent key means 0.
2. Render a shape with long straight silhouette edges at the default resolution:
   ```bash
   mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
   ```
   Copy the PNG to `_automation/tc0612_mcp.png`.
3. Grab the live viewport with the shared recipe to `_automation/tc0612_viewport.png`.
4. Zoom both images on the same silhouette edge and compare the edge pixels.

**Checkpoints**:
- [ ] CP1: The configured value is recorded — verify: step 1 output names the `AntiAliasing` enum value, and it is mapped to a sample count with the table above
- [ ] CP2: AA present when configured on — verify: when the mapped sample count is above 1, the step-2 PNG shows blended intermediate pixels along a diagonal silhouette edge, not a pure two-colour stair
- [ ] CP3: AA absent when configured off — verify: when the mapped sample count is 0 or 1, hard stair-stepping in the step-2 PNG is expected and is NOT a defect
- [ ] CP4: Render and viewport agree on edge quality — verify: the same edge in `tc0612_viewport.png` and `tc0612_mcp.png` shows the same class of smoothing
- [ ] CP5: The preference is read at render time, not baked — verify: change the GUI preference, re-render, and confirm the edge quality follows the new value; restore the original value afterwards

**Cleanup**:
```bash
rm -f _automation/tc0612_*.png
```
Restore the original `AntiAliasing` preference value if CP5 changed it.

---

## Divergence handling

- Any CP1 to CP4 mismatch in TC-06-01 is a **defect**, not a tolerance. Record the exact difference
  (missing object, wrong camera, geometry mismatch, black-sided face) and stop. Do not pass the
  render on numbers alone.
- Anti-aliasing differences (TC-06-01 CP5, TC-06-12) are quality-level and not blocking, UNLESS
  AA is entirely absent while `Preferences/View/AntiAliasing` maps to more than 1 sample. That case
  is a defect: the render ignored the user's configured preference.
- A `verify_state` result of `unknown` in any GUI step is inconclusive, never a pass. Re-snapshot
  and re-read; if it stays `unknown`, record the scenario as inconclusive with the observed tree and
  screenshot, and do not claim a checkpoint.
- A silent clamp where the schema should refuse (TC-06-08 CP3) is a defect, not a convenience. The
  client must be told it did not get what it asked for.
