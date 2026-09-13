# TC-06: Render and GUI Visual Fidelity

Confirms `query_screenshot` depicts the object as FreeCAD itself draws it, not merely that it wrote
a non-empty PNG with plausible numbers. The MCP render builds its own Coin scene — its own camera,
its own lighting, its own white background — and is NOT a capture of the live viewport, so
comparing a render only against another render proves nothing. Every rendering scenario in this
file grabs the real FreeCAD viewport through `cua-driver` and compares the two images.
Scenarios 06 and 02 also drive the GUI with `cua-driver` so the live viewport state and the render
are set from opposite sides.

**The window is the referent; the render is the thing on trial.** We are building this bridge, so
`query_screenshot` is a claim produced by the code under test, never the test result. Per
test-plan §3 the only rank-1 artifact is a `cua-driver` pixel capture of the real FreeCAD window,
`Read` and judged by the agent. Where a render and the window disagree, **the window wins** and the
disagreement is recorded in `$RUN_DIR/bugs.md` as a finding against the render. Commit `636fb8a`
fixed exactly this class of defect: the fit reported success while the part occupied about 5 % of
the viewport.

**Ordering rule for this file.** A fit moves the camera, and a moved camera changes what a later
`query_screenshot` renders. Every scenario that compares a render against the window therefore
**fits first, then takes both captures**, so the two images share one camera. A render taken before
the fit and a window captured after it cannot be compared.

**Host**: GUI through the H2 proxy for every scenario except TC-06-11, which runs on the H1
headless host with no GL context to prove the honest-degradation path.

## Preconditions

- [ ] FreeCAD 1.1.1 GUI is open (verify: `Get-Process -Name freecad | Select-Object Id,MainWindowTitle` lists one process with title `FreeCAD 1.1.1`)
- [ ] The MCP proxy serves `:8765` — the addon auto-spawns it on FreeCAD start (verify: `netstat -ano | Select-String ":8765" | Select-String "LISTENING"` returns a row). No manual `serve` command. If absent, restart FreeCAD or read `%APPDATA%/FreeCAD/v1-1/freecad-buddy/addon.log`.
- [ ] `cua-driver` is reachable and in the interactive session (verify: `cua-driver status` reports the daemon and NOT Session 0)
- [ ] The render ladder reports a usable mode (verify: `mcp query_capabilities {}` returns `render` = `gui_constructed`)
- [ ] The FreeCAD `(pid, window_id)` pair is known (verify: `'{"pid":<PID>}' | & cua-driver call list_windows` returns the window whose `title` is `FreeCAD 1.1.1`)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)

### Shared viewport-capture recipe

Every scenario that compares against the live viewport uses this exact capture, through
`cua-driver`. It does not raise, restack, or focus the FreeCAD window, so the user's active window
stays where it is.

```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-NN-<name>.png"}' | & cua-driver call get_window_state
```

Forbidden in every scenario below: `Start-Process`, `SetForegroundWindow`, `taskkill /F`.

### Shared GUI-fit fallback

`mcp view_fit_viewport` is MCP code under test, so it can never be the only way to frame a shot.
Where a visual line offers the GUI fallback, use the `Fit All` **toolbar** button, which touches
none of the code under test:

```bash
'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state
# from THAT snapshot take the element_token whose label is exactly "Fit All"
'{"pid":<PID>,"element_token":"<Fit All token>"}' | & cua-driver call click
```

the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view) is the standard fallback elsewhere in the
suite, but on FreeCAD 1.1.1 it is **refused** with `menu_path_unavailable` at segment 1 (verified
2026-09-12, see TC-06-01 and `APPENDIX-B`). On this build use the toolbar click. The button exists
in the UIA tree **only while a document is open**.

---

### TC-06-01: MCP render matches the live viewport

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Given** a document with one shape-bearing object is open — verify: `mcp document_list {}` returns a handle; `mcp query_tree_summary {doc:<handle>}` names the object  
**And** the object's geometry is known — verify: `mcp query_mass_properties {doc:<handle>}` returns `volume` and `bbox`  

**When** the GUI camera is set through the **toolbar buttons**, not the View menu and not keystrokes. Snapshot first, then act on a token from that same snapshot.  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-01-pre.png"}' | & cua-driver call get_window_state
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

**And** the MCP render is captured. The toolbar `Fit All` above already framed the window, so the render and the window below share one camera; taking the render before the fit would compare two different cameras.  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso", include:["<Object>"]}}
```
Copy the returned `render.resource_link` PNG to `$RUN_DIR/evidence/tc-06-01-mcp.png`.

**And** the live viewport is captured with the shared recipe to `$RUN_DIR/evidence/tc-06-01-viewport.png`  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-01-viewport.png"}' | & cua-driver call get_window_state
```

**And** both PNGs are opened side by side and compared  

**Then** the same object is present — verify: both images show the same silhouette, and `mcp query_screenshot` returned `scene.rendered_objects` containing `<Object>`  
**And** the proportions match the geometry — verify: the rendered extents agree with the `bbox` from `mcp query_mass_properties {doc:<handle>}` (a 60x40x5 mm bracket reads flat and wide, not cubic)  
**And** the camera and framing are consistent — verify: the iso orientation in `$RUN_DIR/evidence/tc-06-01-mcp.png` matches `$RUN_DIR/evidence/tc-06-01-viewport.png`; any axis flip or off-centre framing is recorded  
**And** there is no missing or extra geometry — verify: no object visible in the viewport is absent from the MCP render, and no `PartDesign::Body`, `Sketcher::SketchObject`, or `App::Origin` child leaked into it  
**And** anti-aliasing is honored — verify: edges are smooth when AA is configured; read the configured value with `Select-String AntiAliasing "$env:APPDATA/FreeCAD/v1-1/user.cfg"`  
**And** the shading is not black-sided — verify: faces angled away from the camera render as shaded grey, not pure black. A black side face means the camera-aligned headlight was lost; compare tone against the lit sides in `$RUN_DIR/evidence/tc-06-01-viewport.png`  
**And** *(visual)* the model is framed, before either capture is taken — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the shared GUI-fit fallback, which touches none of the code under test. Fit FIRST, then capture, so the render and the window share one camera.  
**And** *(visual)* the window shows one whole object, drawn as FreeCAD draws it, and the render depicts that same object — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-01-after.png"}' | & cua-driver call get_window_state`, then `Read` the after PNG and say what is on screen as the user would see it: how many solids, what shape and proportion, which faces are lit and which are shaded. Then `Read` `$RUN_DIR/evidence/tc-06-01-mcp.png` and judge the render against that description. The window is the referent; the render is the thing being judged against it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. Where the two disagree, the window wins: record the disagreement in `$RUN_DIR/bugs.md` as a finding against the render.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-06-01-"*.png
```

---

### TC-06-02: Each named camera orients correctly

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Given** a document with one asymmetric object is open, so front and back are distinguishable — verify: `mcp query_mass_properties {doc:<handle>}` returns a `bbox` with three different extents  

**When** each of the seven named cameras is rendered to its own file  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
mcp query_screenshot {doc:<handle>, view:{camera:"front"}}
mcp query_screenshot {doc:<handle>, view:{camera:"top"}}
mcp query_screenshot {doc:<handle>, view:{camera:"right"}}
mcp query_screenshot {doc:<handle>, view:{camera:"left"}}
mcp query_screenshot {doc:<handle>, view:{camera:"back"}}
mcp query_screenshot {doc:<handle>, view:{camera:"bottom"}}
```
Copy each `render.resource_link` to `$RUN_DIR/evidence/tc-06-02-<camera>.png`.

**And** for each camera the matching GUI standard view is set through the **`Standard Views` toolbar button**, then the viewport is grabbed  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-02-tree.png"}' | & cua-driver call get_window_state
# act on the token from THAT snapshot whose label is exactly "Standard Views"
'{"pid":<PID>,"element_token":"<Standard Views token>"}' | & cua-driver call click
```
Then run the shared viewport recipe to `$RUN_DIR/evidence/tc-06-02-front-viewport.png`. Repeat for Top,
Right, Left, Rear, Bottom, Isometric.

Do **not** use `invoke_menu(["View","Standard views",…])` — that path is refused at segment 1 on
this build (see TC-13-01 and `APPENDIX-B`). Re-snapshot before every click: element tokens are
per-snapshot, and an adjacent token can be the tree's inline rename editor rather than the
control you intended.

**Then** all seven cameras are accepted — verify: each `mcp query_screenshot` call returns `status` `OK` with a non-null `render.resource_link`  
**And** each render matches its GUI counterpart — verify: `$RUN_DIR/evidence/tc-06-02-front.png` and `$RUN_DIR/evidence/tc-06-02-front-viewport.png` show the same face; repeat for all seven pairs  
**And** opposite pairs are mirrored, not identical — verify: `$RUN_DIR/evidence/tc-06-02-front.png` differs from `$RUN_DIR/evidence/tc-06-02-back.png`, `$RUN_DIR/evidence/tc-06-02-top.png` from `$RUN_DIR/evidence/tc-06-02-bottom.png`, `$RUN_DIR/evidence/tc-06-02-left.png` from `$RUN_DIR/evidence/tc-06-02-right.png`  
**And** `iso` is a three-quarter view — verify: `$RUN_DIR/evidence/tc-06-02-iso.png` shows three faces, matching the GUI Isometric viewport  
**And** there is no axis flip — verify: for every pair, the up direction in the render agrees with the up direction in the viewport grab  
**And** an unknown camera is rejected — verify: `mcp query_screenshot {doc:<handle>, view:{camera:"oblique"}}` returns `INVALID_INPUT` (the `camera` enum admits only the seven names plus `custom`)  
**And** *(visual)* the model is framed in the Isometric view, before either capture is taken — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the shared GUI-fit fallback, which touches none of the code under test. Fit FIRST, then capture, so the render and the window share one camera.  
**And** *(visual)* the window shows a three-quarter view of the object, and the `iso` render depicts that same view — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-02-after.png"}' | & cua-driver call get_window_state`, then `Read` the after PNG and say what is on screen as the user would see it: how many faces are visible, which way is up, which corner of the object faces the viewer. Then `Read` `$RUN_DIR/evidence/tc-06-02-iso.png` and judge the render against that description. The window is the referent; the render is the thing being judged against it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. Where the two disagree, the window wins: record the disagreement in `$RUN_DIR/bugs.md` as a finding against the render.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-06-02-"*.png
```

---

### TC-06-03: include and exclude select the right objects

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.9 (view-controlled render)

**Given** a document with at least two shape-bearing objects and one `PartDesign::Body` is open — verify: `mcp query_tree_summary {doc:<handle>, depth:2}` lists both leaf features and the Body  

**When** the default scene is rendered with no `include`  
```bash
mcp query_screenshot {doc:<handle>}
```
**And** only the first object is rendered  
```bash
mcp query_screenshot {doc:<handle>, view:{include:["<ObjectA>"]}}
```
**And** everything except the first object is rendered  
```bash
mcp query_screenshot {doc:<handle>, view:{exclude:["<ObjectA>"]}}
```
**And** an object that does not exist is asked for  
```bash
mcp query_screenshot {doc:<handle>, view:{include:["NoSuchObject"]}}
```

**Then** the default scene skips containers — verify: the first call's `scene.rendered_objects` contains no `PartDesign::Body` name, no `Sketcher::SketchObject` name, and no `App::Origin`/`App::Line`/`App::Plane`/`App::Point` name  
**And** `include` is the exact set — verify: the second call's `scene.rendered_objects` equals `["<ObjectA>"]`  
**And** `exclude` removes exactly one — verify: the third call's `scene.rendered_objects` equals the first call's list minus `<ObjectA>`  
**And** the images agree with the lists — verify: the second call's PNG shows one solid and the third call's PNG shows the rest; neither shows a datum plane  
**And** an unknown name fails closed — verify: the fourth call returns `INVALID_INPUT` with detail `unknown object: NoSuchObject`  
**And** an explicit `include` of the Body still renders it — verify: `mcp query_screenshot {doc:<handle>, view:{include:["<Body>"]}}` returns `scene.rendered_objects` containing `<Body>`, proving the skip shapes only the automatic set  
**And** *(visual)* the model is framed, before either capture is taken — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the shared GUI-fit fallback, which touches none of the code under test. Fit FIRST, then capture, so the render and the window share one camera.  
**And** *(visual)* the window shows the document's visible solids and no datum plane, and the default render depicts that same set — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-03-after.png"}' | & cua-driver call get_window_state`, then `Read` the after PNG and say what is on screen as the user would see it: count the solids, and name any datum plane, origin marker, or sketch line that is drawn. Then `Read` the default render and judge it against that description. The window is the referent; the render is the thing being judged against it. The judgement is on the pixels alone — no MCP status, `scene.rendered_objects` list, or render may stand in for looking at the image. Where the two disagree, the window wins: record the disagreement in `$RUN_DIR/bugs.md` as a finding against the render.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-06-03-"*.png
```

---

### TC-06-04: styles transparency and color are honored

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.9 (view-controlled render)

**Given** a document with two overlapping or adjacent solids is open — verify: `mcp query_tree_summary {doc:<handle>}` names both  
**And** the untouched live viewport is captured — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-04-before.png"}' | & cua-driver call get_window_state`  

**When** the scene is rendered with an opaque red front object  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"front", styles:[{object:"<ObjectA>", color:[1.0,0.0,0.0]}]}}
```
**And** the same view is rendered with the front object at 80 percent transparency  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"front", styles:[{object:"<ObjectA>", color:[1.0,0.0,0.0], transparency:80}]}}
```
**And** a transparency outside the range is sent  
```bash
mcp query_screenshot {doc:<handle>, view:{styles:[{object:"<ObjectA>", transparency:150}]}}
```
**And** a two-element color is sent  
```bash
mcp query_screenshot {doc:<handle>, view:{styles:[{object:"<ObjectA>", color:[1.0,0.0]}]}}
```

**Then** the color is applied — verify: `<ObjectA>` renders red in the first call's PNG while the other object keeps its own color  
**And** the transparency is applied — verify: the object behind `<ObjectA>` is visible through it in the second call's PNG and not in the first call's PNG  
**And** transparency 0 and 100 are both accepted — verify: `mcp query_screenshot {doc:<handle>, view:{styles:[{object:"<ObjectA>", transparency:0}]}}` and the same call with `transparency:100` both return `OK`  
**And** out-of-range transparency is rejected — verify: the third call returns `INVALID_INPUT` (schema `maximum: 100`)  
**And** a wrong-length color is rejected — verify: the fourth call returns `INVALID_INPUT` (schema `minItems: 3, maxItems: 3`)  
**And** styling a nonexistent object fails closed — verify: `mcp query_screenshot {doc:<handle>, view:{styles:[{object:"NoSuchObject", color:[0,0,1]}]}}` returns `INVALID_INPUT` with detail `unknown object: NoSuchObject`  
**And** styles do not touch the live viewport — verify: a viewport grab taken after the second call with the shared recipe to `$RUN_DIR/evidence/tc-06-04-styled.png` shows `<ObjectA>` in its ORIGINAL color, not red; the render must never mutate the user's view  
**And** *(visual)* the model is framed, before the capture is taken — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the shared GUI-fit fallback, which touches none of the code under test  
**And** *(visual)* the window is unchanged by the styled renders — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-04-after.png"}' | & cua-driver call get_window_state`, then `Read` both `$RUN_DIR/evidence/tc-06-04-before.png` and the after PNG and say what colour `<ObjectA>` is in each, as the user would see it; it must still carry its original colour in both. Then `Read` the red render and compare: the two must **disagree** on colour, because the style lived only in the constructed scene. This is the one place in the file where agreement is the defect. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. A window that turned red is a finding: record it in `$RUN_DIR/bugs.md`.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-06-04-"*.png
```

---

### TC-06-05: focus and highlight frame and accent the target

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.9 (view-controlled render)

**Given** a document with a solid whose face count is known is open — verify: `mcp verify_shape {doc:<handle>}` reports the face count  

**When** the whole scene is rendered, then one face is focused  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
mcp query_screenshot {doc:<handle>, view:{camera:"iso", focus:{object:"<ObjectA>", element_type:"face", index:0}}}
```
**And** the object is highlighted  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso", highlight:{object:"<ObjectA>"}}}
```
**And** an out-of-range face index is focused  
```bash
mcp query_screenshot {doc:<handle>, view:{focus:{object:"<ObjectA>", element_type:"face", index:9999}}}
```
**And** a partial sub-element selector is sent  
```bash
mcp query_screenshot {doc:<handle>, view:{focus:{object:"<ObjectA>", element_type:"face"}}}
```

**Then** focus frames tighter — verify: the focused PNG fills more of the frame with `<ObjectA>` than the unfocused PNG  
**And** the focus echo carries the sub-element — verify: the second call of the first step returns `scene.focused_on` equal to `{object:"<ObjectA>", element_type:"face", index:0}`  
**And** highlight accents the object — verify: `<ObjectA>` renders in the accent orange in the highlight PNG while other objects keep their color  
**And** an unresolvable index falls back honestly — verify: the out-of-range call returns `OK` with `scene.focused_on` equal to `{object:"<ObjectA>"}` only, with no `element_type` or `index` key; the response never claims a framing that did not happen  
**And** a partial selector is rejected — verify: the partial-selector call returns `INVALID_INPUT` with detail `sub-element selector requires both element_type and index`  
**And** mixed selector forms are rejected — verify: `mcp query_screenshot {doc:<handle>, view:{focus:{object:"<ObjectA>", mapped_name:"Face1", element_type:"face", index:0}}}` returns `INVALID_INPUT` with detail `selector cannot carry both mapped_name and element_type/index`  
**And** *(visual)* the model is framed, before either capture is taken — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the shared GUI-fit fallback, which touches none of the code under test. Fit FIRST, then capture, so the render and the window share one camera.  
**And** *(visual)* the window shows the object with no orange accent, and the unfocused render depicts that same object — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-05-after.png"}' | & cua-driver call get_window_state`, then `Read` the after PNG and say what is on screen as the user would see it: the object's shape and framing, and the colour of every face — no face is accent orange, because highlight lives only in the constructed scene. Then `Read` the unfocused iso render and judge it against that description. The window is the referent; the render is the thing being judged against it. The judgement is on the pixels alone — no MCP status, `scene.focused_on` echo, or render may stand in for looking at the image. Where the two disagree, the window wins: record the disagreement in `$RUN_DIR/bugs.md` as a finding against the render.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-06-05-"*.png
```

---

### TC-06-06: The default scene honors live GUI Visibility

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Given** a document with two visible shape-bearing objects is open — verify: `mcp query_tree_summary {doc:<handle>}` reports `visibility` true for both  
**And** the FreeCAD model tree is exposed in the accessibility tree — verify: `'{"pid":<PID>,"window_id":<WID>,"include_screenshot":false}' | & cua-driver call get_window_state` lists a `Tree` role element  

**When** the default scene is rendered and `scene.rendered_objects` is recorded  
```bash
mcp query_screenshot {doc:<handle>}
```
**And** the window is re-snapshotted, then `<ObjectB>` is selected in the model tree by its `element_token` from that snapshot  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-06-tree.png"}' | & cua-driver call get_window_state
'{"pid":<PID>,"element_token":"<token from this snapshot>"}' | & cua-driver call click
```
Use `element_token`, never a bare `element_index`; indices are per-snapshot and keyed on `(pid, window_id)`.

**And** the selected object is hidden through the GUI. Re-snapshot, match the tree item by `role == "TreeItem"` **and** its exact `label`, then send `space` to that token  
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

**And** the default scene is rendered again, then `<ObjectB>` is rendered explicitly  
```bash
mcp query_screenshot {doc:<handle>}
mcp query_screenshot {doc:<handle>, view:{include:["<ObjectB>"]}}
```
**And** visibility is restored by repeating the hide step, and confirmed with the bridge  

**Then** the hide landed in the GUI — verify: `'{"pid":<PID>,"window_id":<WID>,"expect":[{"element":{"selector":{"label_contains":"<ObjectB>"},"exists":true}}]}' | & cua-driver call verify_state` returns `satisfied`. A result of `unknown` is NOT success — record the scenario as inconclusive and stop.  
**And** the bridge sees the new visibility — verify: `mcp query_tree_summary {doc:<handle>}` reports `visibility` false for `<ObjectB>`  
**And** the hidden object drops out of the default render — verify: the post-hide default render returns `scene.rendered_objects` WITHOUT `<ObjectB>`  
**And** an explicit include still renders it — verify: the explicit-include call returns `scene.rendered_objects` equal to `["<ObjectB>"]` with a non-null `render.resource_link`  
**And** the default render matches the viewport — verify: a viewport grab taken after the hide, to `$RUN_DIR/evidence/tc-06-06-hidden.png`, shows the same object set as the post-hide default render  
**And** visibility is restored — verify: after the restore step, `mcp query_tree_summary {doc:<handle>}` reports `visibility` true for `<ObjectB>` and the default render lists it again  
**And** *(visual)* the model is framed, before either capture is taken — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the shared GUI-fit fallback, which touches none of the code under test. Fit FIRST, then capture, so the render and the window share one camera.  
**And** *(visual)* the window shows both objects again, and the restored default render depicts that same pair — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-06-after.png"}' | & cua-driver call get_window_state`, then `Read` the after PNG and say how many solids are on screen and which they are, as the user would see it. `Read` `$RUN_DIR/evidence/tc-06-06-hidden.png` and say the same for the hidden state — one solid, `<ObjectB>` absent. Then `Read` the final default render and judge it against the after description. The window is the referent; the render is the thing being judged against it. The judgement is on the pixels alone — no MCP status, `visibility` flag, or render may stand in for looking at the image. Where the two disagree on which objects are on screen, the window wins: record the disagreement in `$RUN_DIR/bugs.md` as a finding against the render.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-06-06-"*.png
```
Restore `<ObjectB>` visibility in the GUI before leaving the scenario.

---

### TC-06-07: camera custom requires exactly four numbers

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.9 (view-controlled render)

**Given** a document with one shape-bearing object is open — verify: `mcp document_list {}` returns a handle  

**When** the scene is rendered with a valid custom quaternion  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"custom", custom_orientation:[0.424708,0.17592,0.339851,0.820473]}}
```
**And** `custom` is rendered with no orientation at all  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"custom"}}
```
**And** a three-element orientation is sent  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"custom", custom_orientation:[0.0,0.0,1.0]}}
```
**And** a five-element orientation is sent, then a zero quaternion  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"custom", custom_orientation:[0,0,0,1,0]}}
mcp query_screenshot {doc:<handle>, view:{camera:"custom", custom_orientation:[0,0,0,0]}}
```

**Then** a valid quaternion renders — verify: the first call returns `OK` with a non-null `render.resource_link`  
**And** that quaternion equals the iso preset — verify: the first call's PNG is visually the same view as `mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}`  
**And** a missing orientation is rejected — verify: the second call returns `INVALID_INPUT` with detail `camera 'custom' requires custom_orientation (a 4-float quaternion)`  
**And** too few numbers are rejected — verify: the three-element call returns `INVALID_INPUT` (schema `minItems: 4`)  
**And** too many numbers are rejected — verify: the five-element call returns `INVALID_INPUT` (schema `maxItems: 4`)  
**And** a zero-norm quaternion is rejected — verify: the zero-quaternion call returns `INVALID_INPUT` with detail matching `custom_orientation is degenerate (zero norm)`  
**And** *(visual)* the model is framed in the Isometric view, before either capture is taken — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the shared GUI-fit fallback, which touches none of the code under test. Fit FIRST, then capture, so the render and the window share one camera.  
**And** *(visual)* the window shows a three-quarter view of the object, and the custom-quaternion render depicts that same view — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-07-after.png"}' | & cua-driver call get_window_state`, then `Read` the after PNG and say what is on screen as the user would see it: how many faces are visible, which way is up, which corner faces the viewer. Then `Read` the valid-quaternion render and judge it against that description. The window is the referent; the render is the thing being judged against it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. Where the two disagree, the window wins: record the disagreement in `$RUN_DIR/bugs.md` as a finding against the render.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-06-07-"*.png
```

---

### TC-06-08: Resolution default and cap

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.9 (view-controlled render)

**Given** a document with one shape-bearing object is open — verify: `mcp document_list {}` returns a handle  
**And** a tool that reads PNG dimensions is available — verify: `python -c "from PIL import Image; print(Image.open('<png>').size)"` runs  

**When** the scene is rendered with no width or height, and the PNG is copied to `$RUN_DIR/evidence/tc-06-08-default.png`  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
```
**And** the scene is rendered at an explicit smaller size  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso", width:640, height:480}}
```
**And** a size above the cap is requested  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso", width:4096, height:4096}}
```
**And** a non-positive size is requested  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso", width:0}}
```

**Then** the default is 1920x1920 — verify: `python -c "from PIL import Image; print(Image.open('$RUN_DIR/evidence/tc-06-08-default.png').size)"` prints `(1920, 1920)`  
**And** an explicit size is honored — verify: the 640x480 PNG measures `(640, 480)`  
**And** above the cap is REFUSED, not clamped — verify: the 4096x4096 call returns `INVALID_INPUT` from the schema `maximum: 1920`; it must NOT return `OK` with a 1920x1920 image. A silent clamp is a defect: the client asked for a resolution it did not get and was not told.  
**And** exactly 1920 is accepted — verify: `mcp query_screenshot {doc:<handle>, view:{width:1920, height:1920}}` returns `OK` and the PNG measures `(1920, 1920)`  
**And** zero is rejected — verify: the `width:0` call returns `INVALID_INPUT`  
**And** only width given still renders — verify: `mcp query_screenshot {doc:<handle>, view:{width:800}}` returns `OK` and the PNG measures `(800, 1920)`  
**And** *(visual)* the model is framed, before either capture is taken — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the shared GUI-fit fallback, which touches none of the code under test. Fit FIRST, then capture, so the render and the window share one camera.  
**And** *(visual)* the window shows the object, and the default-resolution render depicts that same object — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-08-after.png"}' | & cua-driver call get_window_state`, then `Read` the after PNG and say what is on screen as the user would see it: the object's shape, proportion, and orientation. Then `Read` `$RUN_DIR/evidence/tc-06-08-default.png` and judge it against that description; the two images differ in resolution, and must not differ in content. The window is the referent; the render is the thing being judged against it. The judgement is on the pixels alone — no MCP status or reported pixel size may stand in for looking at the image. Where the two disagree, the window wins: record the disagreement in `$RUN_DIR/bugs.md` as a finding against the render.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-06-08-"*.png
```

---

### TC-06-09: query_screenshot is read-only on a clean document

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.9 (view-controlled render)

**Given** a golden model is open and clean — verify: `mcp document_open {path:"$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd"}` returns a handle; `mcp verify_recompute {doc:<handle>}` reports no touched or error object  

**When** the geometry is recorded before  
```bash
mcp query_mass_properties {doc:<handle>}
mcp query_tree_summary {doc:<handle>, depth:2}
```
**And** several renders with different view options are run  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
mcp query_screenshot {doc:<handle>, view:{camera:"top", styles:[{object:"Box", color:[0,1,0], transparency:50}]}}
mcp query_screenshot {doc:<handle>, view:{camera:"front", focus:{object:"Box", element_type:"face", index:2}}}
```
**And** the geometry is recorded after  
```bash
mcp query_mass_properties {doc:<handle>}
mcp query_tree_summary {doc:<handle>, depth:2}
```

**Then** the volume is unchanged — verify: the after `volume` equals the before `volume` exactly, and equals `6000.0` mm3 for `box-10-20-30`  
**And** the centre of mass is unchanged — verify: the after `com` equals the before `com` exactly  
**And** the tree is unchanged — verify: the after `query_tree_summary` output equals the before output, including every `visibility` flag  
**And** the strict guard is active — verify: every render response has `render.dirty_document` false, which is the state in which the before-equals-after mutation assertion runs  
**And** no document dirty flag is set — verify: `mcp verify_recompute {doc:<handle>}` after the renders still reports no touched object; a render must not touch the document  
**And** styles did not persist — verify: a render with no `styles` after the styled render shows `Box` in its original color, so the style override lived only in the constructed scene  
**And** no temp PNG is orphaned in the system temp dir beyond the returned link — verify: `Get-ChildItem $env:TEMP -Filter "FCB_TMP_shot_*.png"` lists at most the files still referenced by the three `render.resource_link` values  
**And** *(visual)* the model is framed, before either capture is taken — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the shared GUI-fit fallback, which touches none of the code under test. Fit FIRST, then capture, so the render and the window share one camera.  
**And** *(visual)* the window shows one box in its original colour, not green, and the iso render depicts that same box — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-09-after.png"}' | & cua-driver call get_window_state`, then `Read` the after PNG and say what is on screen as the user would see it: one box, its proportions, and its colour — which is its original colour, not the green the styled render used. Then `Read` the iso render and judge it against that description. The window is the referent; the render is the thing being judged against it. The judgement is on the pixels alone — no MCP status, `dirty_document` flag, or render may stand in for looking at the image. Where the two disagree, the window wins: record the disagreement in `$RUN_DIR/bugs.md` as a finding against the render.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-06-09-"*.png
```
```bash
mcp document_close {doc:<handle>}
```

---

### TC-06-10: A dirty document renders with dirty_document true

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Given** a document that can be made dirty is open — verify: `mcp document_open {path:"$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd"}` returns a handle  
**And** the document is clean to start — verify: `mcp query_screenshot {doc:<handle>}` returns `render.dirty_document` false  

**When** the document is made dirty by changing a driving parameter without recomputing, using `preview_dry_run` for the token, then `feature_set_parameters`  
```bash
mcp preview_dry_run {doc:<handle>, tool:"feature_set_parameters", args:{doc:<handle>, feature:"Box", parameters:{Length:{value:25, unit:"mm"}}}}
mcp feature_set_parameters {doc:<handle>, feature:"Box", parameters:{Length:{value:25, unit:"mm"}}, confirm:{preview_id:"<token>"}}
```
If the tool recomputes on commit, instead leave a dependent object Touched and confirm with the next step before proceeding.

**And** the document is confirmed actually dirty  
```bash
mcp verify_recompute {doc:<handle>}
```
**And** it is rendered  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
```
**And** it is recomputed and rendered again  
```bash
mcp document_recompute {doc:<handle>}
mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
```

**Then** the render does NOT hard-fail — verify: the dirty render returns `status` `OK`, not `SPEC_FAILED` or `INVALID_INPUT`  
**And** the dirty flag is reported — verify: the dirty render returns `render.dirty_document` true  
**And** an image was still produced — verify: the dirty render's `render.resource_link` is non-null and the PNG on disk is larger than zero bytes  
**And** the flag reaches the human-readable text — verify: the dirty render's `text` contains `Document dirty (pending/broken recompute)`  
**And** the before-equals-after guard was skipped and flagged, not silently dropped — verify: `render.dirty_document` true is the ONLY signal a client gets that the read-only assertion did not run; it is present in `structured_content.render`, so a client can branch on it  
**And** a clean document returns to the strict guard — verify: the post-recompute render returns `render.dirty_document` false  
**And** the dirty render still lists the right objects — verify: the dirty render's `scene.rendered_objects` equals the post-recompute list  
**And** *(visual)* the model is framed, before either capture is taken — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the shared GUI-fit fallback, which touches none of the code under test. Fit FIRST, then capture, so the render and the window share one camera.  
**And** *(visual)* the window shows the recomputed box, and the post-recompute render depicts that same box — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-10-after.png"}' | & cua-driver call get_window_state`, then `Read` the after PNG and say what is on screen as the user would see it: one box, and the ratio of its three edge lengths, which now reflect `Length: 25 mm`. Then `Read` the post-recompute render and judge it against that description. The window is the referent; the render is the thing being judged against it. The judgement is on the pixels alone — no MCP status, `dirty_document` flag, or render may stand in for looking at the image. Where the two disagree, the window wins: record the disagreement in `$RUN_DIR/bugs.md` as a finding against the render.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-06-10-"*.png
```
```bash
mcp document_close {doc:<handle>}
```
Do not save the modified golden model.

---

### TC-06-11: No render capability degrades honestly

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Host**: H1 headless with no GL context. The closing visual asserts the separate GUI window was
**not** touched by an H1 call.

**Given** a host with no usable render context is available. Run this scenario against the headless H1 stdio host in an environment with no GL context, NOT against the live GUI — verify: `mcp query_capabilities {}` on that host returns `render` = `none` with a reason  
**And** the GUI still has its own document open — verify: `mcp document_open {path:"$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd"}` returns a handle; record it as `<gui handle>`  
**And** the GUI's state is captured before the headless calls — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-11-before.png"}' | & cua-driver call get_window_state`  

**When** the capability ladder result is read  
```bash
mcp query_capabilities {}
```
**And** a render is taken on that host  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
```
**And** any PNG the call might have written is listed  
```bash
Get-ChildItem $env:TEMP -Filter "FCB_TMP_shot_*.png"
```

**Then** the ladder reports none — verify: `query_capabilities` returns `render` equal to `none`  
**And** the render call still returns OK — verify: the render returns `status` `OK`; unavailability is reported, not raised as an error  
**And** availability is false — verify: the render returns `render.available` false  
**And** a reason is carried — verify: the render's `render.reason` is a non-null string naming the failure (for example `FreeCADGui not importable` or `offscreen probe render failed`)  
**And** NO fake PNG is produced — verify: the render's `render.resource_link` is absent from the unavailable envelope and the response carries no `images` array  
**And** no temp file is left behind — verify: the `Get-ChildItem` listing shows no new `FCB_TMP_shot_*.png` created by the render call  
**And** the scene block is empty and honest — verify: the render returns `scene.rendered_objects` equal to `[]` and `scene.focused_on` null  
**And** *(visual)* the GUI model was framed in the `Given`, before `tc-06-11-before.png` was taken; **no fit is run now** — verify: nothing is called between the two captures. A fit here would move the very camera this scenario asserts was left alone. If the `Given` fit was needed, `mcp view_fit_viewport { doc: "<gui handle>" }` returning `OK` is enough; if it did not, the shared GUI-fit fallback frames it without touching the code under test.  
**And** *(visual)* the GUI window is pixel-for-pixel the same scene as before the headless calls — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-11-after.png"}' | & cua-driver call get_window_state`, then `Read` both `$RUN_DIR/evidence/tc-06-11-before.png` and the after PNG and say what is on screen in each, as the user would see it: the same model, at the same size, at the same orientation, with no dialog or error popup raised. The judgement is on the pixels alone — no MCP status may stand in for looking at the image; the H1 envelope said nothing about the GUI and cannot be evidence about it. A headless refusal that changed the human's viewport would be a serious defect: record it in `$RUN_DIR/bugs.md`.  

**Cleanup**: stop the H1 host.
```bash
rm -f "$RUN_DIR/evidence/tc-06-11-"*.png
```
```bash
mcp document_close {doc:<gui handle>}
```

**Conditional skip**: skip when no host with `render` = `none` is available. Record the skip with
the `query_capabilities` output that shows `render` was `gui_constructed` or `offscreen` instead.

---

### TC-06-12: Anti-aliasing tracks the user's own preference

**Priority**: Medium
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Given** the FreeCAD GUI is open and rendering through `gui_constructed` — verify: `mcp query_capabilities {}` returns `render` = `gui_constructed`  
**And** the AA preference value is readable — verify: `Select-String AntiAliasing "$env:APPDATA/FreeCAD/v1-1/user.cfg"` returns the `AntiAliasing` entry, or returns nothing when the key is unset  

**When** the configured value is read  
```bash
Select-String AntiAliasing "$env:APPDATA/FreeCAD/v1-1/user.cfg"
```
The stored enum is NOT sequential. The mapping is `0 -> 0 samples`, `1 -> 1`, `2 -> 2`,
`3 -> 4`, `4 -> 8`, `5 -> 6`. An absent key means 0.

**And** a shape with long straight silhouette edges is rendered at the default resolution  
```bash
mcp query_screenshot {doc:<handle>, view:{camera:"iso"}}
```
Copy the PNG to `$RUN_DIR/evidence/tc-06-12-mcp.png`.

**And** the live viewport is grabbed with the shared recipe to `$RUN_DIR/evidence/tc-06-12-viewport.png`  
```bash
'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-12-viewport.png"}' | & cua-driver call get_window_state
```

**And** both images are zoomed on the same silhouette edge and the edge pixels are compared  

**Then** the configured value is recorded — verify: the `Select-String` output names the `AntiAliasing` enum value, and it is mapped to a sample count with the table above  
**And** AA is present when configured on — verify: when the mapped sample count is above 1, `$RUN_DIR/evidence/tc-06-12-mcp.png` shows blended intermediate pixels along a diagonal silhouette edge, not a pure two-colour stair  
**And** AA is absent when configured off — verify: when the mapped sample count is 0 or 1, hard stair-stepping in `$RUN_DIR/evidence/tc-06-12-mcp.png` is expected and is NOT a defect  
**And** render and viewport agree on edge quality — verify: the same edge in `$RUN_DIR/evidence/tc-06-12-viewport.png` and `$RUN_DIR/evidence/tc-06-12-mcp.png` shows the same class of smoothing  
**And** the preference is read at render time, not baked — verify: change the GUI preference, re-render, and confirm the edge quality follows the new value; restore the original value afterwards  
**And** *(visual)* the model is framed, before either capture is taken — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, fit through the GUI instead with the shared GUI-fit fallback, which touches none of the code under test. Fit FIRST, then capture, so the render and the window share one camera.  
**And** *(visual)* a diagonal silhouette edge in the window carries a given class of smoothing, and the render carries that same class — verify: `'{"pid":<PID>,"window_id":<WID>,"screenshot_out_file":"$RUN_DIR/evidence/tc-06-12-after.png"}' | & cua-driver call get_window_state`, then `Read` the after PNG, zoom one diagonal silhouette edge, and say what the user would see there: blended intermediate pixels, or a hard two-colour stair. Then `Read` `$RUN_DIR/evidence/tc-06-12-mcp.png`, zoom the same edge, and judge it against that description. The window is the referent; the render is the thing being judged against it. The judgement is on the pixels alone — no MCP status and no `AntiAliasing` config value may stand in for looking at the image. Where the two disagree, the window wins: record the disagreement in `$RUN_DIR/bugs.md` as a finding against the render.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-06-12-"*.png
```
Restore the original `AntiAliasing` preference value if the preference assertion changed it.

---

## Divergence handling

- Any mismatch on the first four `Then` lines of TC-06-01 is a **defect**, not a tolerance. Record
  the exact difference (missing object, wrong camera, geometry mismatch, black-sided face) and stop.
  Do not pass the render on numbers alone.
- Anti-aliasing differences (the AA line in TC-06-01, and TC-06-12) are quality-level and not
  blocking, UNLESS AA is entirely absent while `Preferences/View/AntiAliasing` maps to more than 1
  sample. That case is a defect: the render ignored the user's configured preference.
- A `verify_state` result of `unknown` in any GUI step is inconclusive, never a pass. Re-snapshot
  and re-read; if it stays `unknown`, record the scenario as inconclusive with the observed tree and
  screenshot, and do not claim a checkpoint.
- A silent clamp where the schema should refuse (the above-cap line in TC-06-08) is a defect, not a
  convenience. The client must be told it did not get what it asked for.
- Where a render and the window disagree, the **window wins** and the render is the defect. Do not
  resolve the disagreement in favour of the numbers, and do not re-read the envelope to decide which
  image is right — the envelope is produced by the same code that produced the render. Record the
  finding in `$RUN_DIR/bugs.md` against the render.
