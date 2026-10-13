# TC-03: Sketch Authoring

Exercises all eight `sketch_*` mutation tools against a live FreeCAD document, plus the two
read tools that grade their result: `query_sketch_info` and `verify_sketch`. The load-bearing rule
is AD-8: a sketch passes only when it is `FullyConstrained` with `dof == 0`, so geometry sent
without the constraints that pin it is rolled back — geometry included. Redundancy follows FreeCAD
(Story 10.2 D1/D2): a fully redundant sketch is a hard fail (`RECOMPUTE_ERROR`, rolled back), and
partial redundancy only warns. Every scenario also proves the schema boundary: `{value, unit}`
quantities, the 16 constraint types, 1-based solver ids, and `additionalProperties: false`.

We are building the MCP bridge, so the bridge's own output is never the test result. Every
`status`, envelope field, `sketch_state` block, fingerprint and `query_screenshot` render below is a
**claim under test**. The test result is the `cua-driver` pixel capture of the real FreeCAD window,
read and judged by the agent. A `sketch_*` tool reporting `dof=0` is a claim; a closed green
profile in the human's window is the evidence.

**Host**: GUI through the H2 proxy for every scenario. Each scenario authors sketches in a live
document, so the closing visual reads the human's own 3D view.

## Preconditions

- [ ] FreeCAD 1.1.x installed (verify: `ls "$FREECAD_EXE"`); the build under test is the live version: `query_capabilities.freecad_version`, read once at the start of the run and written `<live version>` below
- [ ] FreeCAD GUI is open and the addon spawned the proxy (verify: `netstat -ano | grep :8765` shows LISTENING)
- [ ] The MCP tool surface is complete (verify: `tools/list` returns the live count: 45 typed tools, plus `script_exec` when it is on, so 46 by default)
- [ ] The host runs the operator auto-approve posture, so a mutation needs no `preview_id` (verify: the addon log carries `SECURITY: mutation auto-approve ENABLED (to require preview_id, clear Auto-approve mutations in the FreeCAD GUI: Edit > Preferences > FreeCAD Buddy, or set FREECAD_BUDDY_AUTO_APPROVE=0)`)
- [ ] Auto-approve is on for this launch: the **Auto-approve mutations** preference is on (the default) and `FREECAD_BUDDY_AUTO_APPROVE` is unset, or the variable is `1` in the environment that launched FreeCAD. The preference off or the variable `0` turns the confirm gate on (verify: the banner line above is present in `%APPDATA%/FreeCAD/v1-1/freecad-buddy/addon.log` for this launch)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` returns a `QOpenGLWidget`)
- [ ] `cua-driver` can reach the View menu, so framing never depends on the code under test (verify: the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view) moves the camera)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)
- [ ] `script_exec` is on (the default; verify: `tools/list` includes `script_exec`). Scenarios use it as an outside oracle and to build fixtures the typed tools refuse. It opens no transaction, so `document_undo` does not revert it.
- [ ] **Sketch edit mode.** FreeCAD draws the sketch axis cross, the constraint colours (green fully constrained, white under-constrained, orange redundant, red conflicting), the constraint glyphs and the dimension labels only in Sketcher edit mode. Outside edit mode a sketch is a plain black wire. Before a visual Then that judges any of these, open the sketch in edit mode: `mcp script_exec { doc: <handle>, code: "import FreeCADGui; FreeCADGui.getDocument(doc.Name).setEdit(doc.getObject('<sketch>'))" }`, or double-click its tree item (`double_click` by `element_token` goes through `global_input`, so it needs foreground input). Close edit mode before the next MCP call: `mcp script_exec { doc: <handle>, code: "import FreeCADGui; FreeCADGui.getDocument(doc.Name).resetEdit()" }`.
- [ ] **Topology oracle.** `query_object` returns type, label and properties only, not face or edge names. Take sub-element names from an outside oracle: `mcp script_exec { doc: <handle>, code: "o = doc.getObject('<name>'); result = [(i + 1, round(e.Length, 3), [round(v, 3) for v in (e.BoundBox.XMin, e.BoundBox.YMin, e.BoundBox.ZMin, e.BoundBox.XMax, e.BoundBox.YMax, e.BoundBox.ZMax)]) for i, e in enumerate(o.Shape.Edges)]" }` (use `o.Shape.Faces` and `f.Surface` for faces), or the `fcb` env.
- [ ] **Session temp path.** The bridge writes its snapshots under `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/` (GUI workdir `%APPDATA%\FreeCAD\v1-1\freecad-buddy\workdir`), never under `$TEMP`. Written `<session tmp>` below. The agent shell may get "Access is denied" on it: list it in-process with `mcp script_exec { doc: <handle>, code: "import os; result = os.listdir(r'<session tmp>')" }`, or take the folder from a `mutation.snapshot_path`.

**Confirm convention for this file**: every `sketch_*` call below is a geometry-intent mutation and
is gated by AD-10. This file runs under the operator auto-approve posture, so no scenario passes a
`confirm` object. The confirm gate's own negative cases — missing, expired, spent, wrong tool,
wrong document, wrong arguments — belong to TC-08 and are not repeated here.

---

### TC-03-01: sketch_create on each base plane

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.6 (sketch tools), `verification-design.md` §4 (AD-8)

**Given** a scratch document exists — verify: `mcp document_create { label: "BracketPlate" }` returns a handle  

**When** one sketch is created on each member of the `plane` enum  
```
mcp sketch_create { doc: <handle>, name: "PlateProfileXY", plane: "XY" }
mcp sketch_create { doc: <handle>, name: "RibProfileXZ",   plane: "XZ" }
mcp sketch_create { doc: <handle>, name: "EndProfileYZ",   plane: "YZ" }
```
**And** each new sketch is graded  
```
mcp verify_sketch { doc: <handle>, sketch: "PlateProfileXY" }
```

**Then** all three commit — verify: each envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** an empty sketch is fully constrained — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfileXY" }` returns `status=OK` with `subject.dof=0` and `subject.fully_constrained=true`  
**And** the post-verify gate agrees — verify: each create envelope carries `mutation.post_verify.fully_constrained=true` and `mutation.post_verify.passed=true`  
**And** the sketch is empty — verify: `mcp query_sketch_info { doc: <handle>, sketch: "RibProfileXZ" }` returns `geometry=[]` and `constraints=[]`  
**And** each lands on its own plane — verify: `mcp query_placement { doc: <handle>, object: "EndProfileYZ" }` reports a rotation distinct from `PlateProfileXY`  
**And** a fourth plane value is a schema reject — verify: `mcp sketch_create { doc: <handle>, name: "BadPlane", plane: "ZX" }` is refused against the enum `["XY","XZ","YZ"]`, and `mcp query_tree_summary { doc: <handle> }` names no `BadPlane`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* three empty sketches stand at mutually perpendicular orientations — verify: outside edit mode the 3D view draws nothing for an empty sketch, so open each sketch in edit mode in turn (Preconditions, **Sketch edit mode**) and capture each one with `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-01-after-<sketch>.png"}' | & cua-driver call get_window_state`, closing edit mode after each capture. `Read` the three PNGs and describe what is on screen: each edit view looks straight at its own sketch plane (top for `PlateProfileXY`, front for `RibProfileXZ`, right for `EndProfileYZ`), so the three orientations differ; each shows the axis cross only, with no closed profile and no drawn edge; no fourth sketch exists in the tree; no error dialog. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# close the scratch document; no file was written
mcp document_close { doc: <handle> }
```

---

### TC-03-02: sketch_create inside a Body

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.6 (sketch tools), `mcp-tools-design.md` §3.7 (Body as container)

**Given** a scratch document exists — verify: `mcp document_create { label: "BracketPlate" }` returns a handle  
**And** a Body exists to adopt the sketch — verify: `mcp feature_body_create { doc: <handle>, name: "PlateBody" }` returns `status=OK`  

**When** the sketch is created into the Body  
```
mcp sketch_create { doc: <handle>, name: "PlateProfile", plane: "XY", body: "PlateBody" }
```
**And** the tree is read to see where the sketch landed  
```
mcp query_tree_summary { doc: <handle>, depth: 3 }
```

**Then** the create commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** the sketch is inside the Body — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` shows `PlateProfile` as a child of `PlateBody`, not at document root  
**And** the Body still carries no solid — verify: `mcp query_object { doc: <handle>, object: "PlateBody" }` reports no Tip feature, because a sketch is not a solid  
**And** the sketch grades clean — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `status=OK` with `subject.dof=0`  
**And** an unknown Body is rejected before the transaction — verify: `mcp sketch_create { doc: <handle>, name: "Orphan", plane: "XY", body: "NoSuchBody" }` returns `status=INVALID_INPUT` and the envelope carries no `mutation.snapshot_path`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* one empty sketch is on screen and no solid — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-02-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and describe what is on screen: a single sketch axis cross seen from the top (the XY plane), with no shaded or coloured solid surface anywhere in the viewport, no second sketch, and no error dialog. The model tree panel, if visible, shows `PlateProfile` indented under `PlateBody`. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-03: sketch_create on a planar face

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.2 (sub-element selectors, AD-7), `mcp-tools-design.md` §3.6

**Given** a Body carrying a 60 x 40 x 5 mm plate solid exists — verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume` near `12000.0`  
**And** the plate's top face name is known — verify: the topology oracle (Preconditions) lists `PlatePad` faces; the top face is the plane face at `z = 5` (`Face6` on 1.1.4). `query_object` returns properties only and names no face  

**When** a new sketch is attached to the plate's top face by selector  
```
mcp sketch_create { doc: <handle>, name: "BossProfile",
                    face: { kind: "mapped_name", object: "PlatePad", mapped_name: "Face6" },
                    body: "PlateBody" }
```

**Then** the create commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** the sketch sits on the face plane — verify: `mcp query_placement { doc: <handle>, object: "BossProfile" }` reports `position.z` equal to the plate thickness `{value: 5, unit: "mm"}`  
**And** the sketch grades clean — verify: `mcp verify_sketch { doc: <handle>, sketch: "BossProfile" }` returns `status=OK` with `subject.fully_constrained=true`  
**And** `plane` and `face` together are rejected — verify: `mcp sketch_create { doc: <handle>, name: "Both", plane: "XY", face: { kind: "mapped_name", object: "PlatePad", mapped_name: "Face6" } }` returns `status=INVALID_INPUT` naming `sketch_create requires exactly one of 'plane' and 'face'`  
**And** a non-planar face is rejected — verify: a selector naming a cylindrical face returns `status=INVALID_INPUT` naming `is not a planar face`  
**And** a `geometric` selector kind is rejected — verify: `face: { kind: "geometric", object: "PlatePad" }` returns `status=INVALID_INPUT` naming `selector kind must be 'mapped_name'`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the new sketch rests on the plate's upper face, not at the document origin — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-03-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and describe what is on screen: a shaded rectangular plate, wide and thin, with the sketch axis cross drawn on its top surface and visibly raised above the plate's bottom by the plate's own thickness. The sketch must not be sunk inside the solid or floating below it. No second sketch, no error dialog. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-04: Rectangle reaches FullyConstrained in one flow

**Priority**: Critical
**Design Ref**: `verification-design.md` §4 (AD-8), `mcp-tools-design.md` §3.6

**Given** an empty sketch exists on XY — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` returns `geometry=[]`  

**When** the four edges of a 60 x 40 mm plate outline are added with their constraints in one call. Sketch geo_ids are 0-based, so the four lines are 0..3.  
```
mcp sketch_add_geometry { doc: <handle>, sketch: "PlateProfile",
  geometry: [
    { kind: "line_segment", start: [0, 0],   end: [60, 0] },
    { kind: "line_segment", start: [60, 0],  end: [60, 40] },
    { kind: "line_segment", start: [60, 40], end: [0, 40] },
    { kind: "line_segment", start: [0, 40],  end: [0, 0] }
  ],
  constraints: [
    { type: "Coincident", first: 0, first_pos: 2, second: 1, second_pos: 1 },
    { type: "Coincident", first: 1, first_pos: 2, second: 2, second_pos: 1 },
    { type: "Coincident", first: 2, first_pos: 2, second: 3, second_pos: 1 },
    { type: "Coincident", first: 3, first_pos: 2, second: 0, second_pos: 1 },
    { type: "Horizontal", first: 0 },
    { type: "Horizontal", first: 2 },
    { type: "Vertical",   first: 1 },
    { type: "Vertical",   first: 3 },
    { type: "Coincident", first: 0, first_pos: 1, second: -1, second_pos: 1 },
    { type: "DistanceX",  first: 0, first_pos: 1, second: 0, second_pos: 2,
      value: { value: 60, unit: "mm" }, name: "PlateWidth" },
    { type: "DistanceY",  first: 1, first_pos: 1, second: 1, second_pos: 2,
      value: { value: 40, unit: "mm" }, name: "PlateDepth" }
  ] }
```
**And** the sketch is graded  
```
mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }
```

**Then** the call commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** AD-8 PASS — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `status=OK` with `subject.dof=0` and `subject.fully_constrained=true`  
**And** the check id is the AD-8 one — verify: the same envelope carries a passed check with `id=sketch.fully_constrained` and `expected=true`  
**And** the post-verify gate agrees — verify: the mutation envelope carries `mutation.post_verify.fully_constrained=true` and `mutation.post_verify.passed=true`  
**And** counts match the request — verify: the same verify envelope reports `subject.geometry_count=4` and `subject.constraint_count=11`  
**And** no conflicting or malformed constraints — verify: `subject.conflicting=[]` and `subject.malformed=[]`  
**And** the datum names survived — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` lists constraints named `PlateWidth` and `PlateDepth`, each with `driving=true`  
**And** the envelope reports the state it produced — verify: the mutation envelope's `sketch_state` block has `readable=true`, `dof=0` and `fully_constrained=true`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* a closed rectangle stands on the XY plane in the fully-constrained colour — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-04-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and describe what is on screen: four straight edges meeting at four corners with no visible gap at any corner, forming one closed rectangle roughly half again as wide as it is deep, lying flat on the horizontal plane with one corner on the sketch origin. The edges are drawn in the fully-constrained colour (green), not the white or amber of unconstrained geometry. Two dimension labels reading 60 and 40 are drawn beside the edges. No edge is clipped by a viewport border. No error dialog. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; a `dof=0` claim over a window showing an open or white profile is the exact defect this scenario catches.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-05: All four geometry kinds

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.6 (geometry kind enum)

**Given** an empty sketch exists on XY — verify: `mcp query_sketch_info { doc: <handle>, sketch: "MixedProfile" }` returns `geometry=[]`  

**When** one instance of every member of the `kind` enum is added, each pinned exactly: one constraint per degree of freedom and no more (line 4, circle 3, arc 5, point 2). An extra pin is full redundancy, which is a hard fail (Story 10.2 D1). Circle and arc radii are `{value, unit}` length quantities; arc angles are `{value, unit}` angle quantities. A single-point `DistanceX`/`DistanceY` pins one coordinate of one point.  
```
mcp sketch_add_geometry { doc: <handle>, sketch: "MixedProfile",
  geometry: [
    { kind: "line_segment", start: [0, 0], end: [40, 0] },
    { kind: "circle", center: [20, 20], radius: { value: 2.5, unit: "mm" } },
    { kind: "arc_of_circle", center: [50, 20], radius: { value: 8, unit: "mm" },
      start_angle: { value: 0, unit: "deg" }, end_angle: { value: 90, unit: "deg" } },
    { kind: "point", start: [10, 30] }
  ],
  constraints: [
    { type: "Coincident", first: 0, first_pos: 1, second: -1, second_pos: 1 },
    { type: "Horizontal", first: 0 },
    { type: "DistanceX", first: 0, first_pos: 1, second: 0, second_pos: 2,
      value: { value: 40, unit: "mm" } },
    { type: "DistanceX", first: 1, first_pos: 3, value: { value: 20, unit: "mm" } },
    { type: "DistanceY", first: 1, first_pos: 3, value: { value: 20, unit: "mm" } },
    { type: "Radius", first: 1, value: { value: 2.5, unit: "mm" } },
    { type: "DistanceX", first: 2, first_pos: 3, value: { value: 50, unit: "mm" } },
    { type: "DistanceY", first: 2, first_pos: 3, value: { value: 20, unit: "mm" } },
    { type: "Radius", first: 2, value: { value: 8, unit: "mm" } },
    { type: "DistanceY", first: 2, first_pos: 1, value: { value: 20, unit: "mm" } },
    { type: "DistanceX", first: 2, first_pos: 2, value: { value: 50, unit: "mm" } },
    { type: "DistanceX", first: 3, first_pos: 1, value: { value: 10, unit: "mm" } },
    { type: "DistanceY", first: 3, first_pos: 1, value: { value: 30, unit: "mm" } }
  ] }
```

**Then** all four kinds are created — verify: `mcp query_sketch_info { doc: <handle>, sketch: "MixedProfile" }` lists 4 geometry entries at `index` 0..3  
**And** each kind maps to the FreeCAD type — verify: the same read reports `type` values `LineSegment`, `Circle`, `ArcOfCircle`, `Point` in index order (the Python class name, `queries.py:701`)  
**And** geo_ids returned are 0-based — verify: the mutation envelope names the created geometry starting at `0`, matching the `index` values in the first assertion  
**And** AD-8 PASS — verify: `mcp verify_sketch { doc: <handle>, sketch: "MixedProfile" }` returns `status=OK` with `subject.dof=0`, `subject.constraint_count=13` and `subject.redundant=[]`  
**And** a fifth kind is a schema reject — verify: `geometry: [ { kind: "ellipse", center: [0,0] } ]` is refused against the enum `["line_segment","circle","arc_of_circle","point"]`  
**And** a coordinate array outside 2..3 entries is a schema reject — verify: `start: [0, 0, 0, 0]` is refused (`maxItems: 3`), and `start: [0]` is refused (`minItems: 2`)  
**And** a bare number radius is a schema reject — verify: `radius: 2.5` is refused; the schema requires `{value, unit}` with both fields  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* four distinct shapes are on screen, one per geometry kind — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-05-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and describe what is on screen: a straight horizontal line running right from the sketch origin; a small closed circle above and left of centre; a quarter-arc — an open curve, not a closed circle — to the right; and one isolated dot with no curve attached, upper left. All four are drawn in the fully-constrained colour (green). No ellipse, no fifth shape, no clipped shape at a viewport edge, no error dialog. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image. The judgement must be made by looking, not by reasoning from the four `type` strings the envelope reported.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-06: All 16 constraint types

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.6 (`sketch_add_constraint`, constraint type enum), `verification-design.md` §4 (AD-8)

AD-8 rolls back every mutation that leaves the sketch under-constrained, and a constraint added on top of geometry that is already pinned is full redundancy, which is a hard fail (Story 10.2 D1). So no sketch can first hold free geometry and then take its constraints one call later. Each type is therefore sent in a `sketch_add_geometry` call together with the geometry it constrains and exactly enough other pins to leave that geometry fully constrained. The `constraints` field of `sketch_add_geometry` uses the same constraint schema as `sketch_add_constraint`. Ids are checked relative to the constraint count before each call.

**Given** an empty sketch exists — verify: `mcp query_sketch_info { doc: <handle>, sketch: "ConstraintBed" }` returns `geometry=[]` and `constraints=[]`  

**When** eight groups are added in eight calls, in this order. Each group pins its own new geometry exactly (line 4, circle 3, point 2 degrees of freedom). The new type each group proves is named in its comment.  
```
# 1: Coincident, Horizontal, Distance — geo 0, line (0,0)-(60,0)
mcp sketch_add_geometry { doc: <handle>, sketch: "ConstraintBed",
  geometry: [ { kind: "line_segment", start: [0, 0], end: [60, 0] } ],
  constraints: [
    { type: "Coincident", first: 0, first_pos: 1, second: -1, second_pos: 1 },
    { type: "Horizontal", first: 0 },
    { type: "Distance", first: 0, first_pos: 1, second: 0, second_pos: 2, value: { value: 60, unit: "mm" } } ] }
# 2: Vertical, DistanceX, DistanceY — geo 1, line (70,5)-(70,45)
mcp sketch_add_geometry { doc: <handle>, sketch: "ConstraintBed",
  geometry: [ { kind: "line_segment", start: [70, 5], end: [70, 45] } ],
  constraints: [
    { type: "Vertical", first: 1 },
    { type: "DistanceX", first: 1, first_pos: 1, value: { value: 70, unit: "mm" } },
    { type: "DistanceY", first: 1, first_pos: 1, value: { value: 5, unit: "mm" } },
    { type: "DistanceY", first: 1, first_pos: 1, second: 1, second_pos: 2, value: { value: 40, unit: "mm" } } ] }
# 3: Parallel, Equal — geo 2, line (10,20)-(70,20)
mcp sketch_add_geometry { doc: <handle>, sketch: "ConstraintBed",
  geometry: [ { kind: "line_segment", start: [10, 20], end: [70, 20] } ],
  constraints: [
    { type: "Parallel", first: 2, second: 0 },
    { type: "Equal", first: 2, second: 0 },
    { type: "DistanceX", first: 2, first_pos: 1, value: { value: 10, unit: "mm" } },
    { type: "DistanceY", first: 2, first_pos: 1, value: { value: 20, unit: "mm" } } ] }
# 4: Perpendicular, PointOnObject — geo 3, line (30,0)-(30,15)
mcp sketch_add_geometry { doc: <handle>, sketch: "ConstraintBed",
  geometry: [ { kind: "line_segment", start: [30, 0], end: [30, 15] } ],
  constraints: [
    { type: "Perpendicular", first: 3, second: 0 },
    { type: "PointOnObject", first: 3, first_pos: 1, second: 0 },
    { type: "DistanceX", first: 3, first_pos: 1, value: { value: 30, unit: "mm" } },
    { type: "DistanceY", first: 3, first_pos: 1, second: 3, second_pos: 2, value: { value: 15, unit: "mm" } } ] }
# 5: Radius, Diameter, Tangent — geo 4 and 5, two circles r 2.5 touching at (22.5,40)
mcp sketch_add_geometry { doc: <handle>, sketch: "ConstraintBed",
  geometry: [ { kind: "circle", center: [20, 40], radius: { value: 2.5, unit: "mm" } },
              { kind: "circle", center: [25, 40], radius: { value: 2.5, unit: "mm" } } ],
  constraints: [
    { type: "DistanceX", first: 4, first_pos: 3, value: { value: 20, unit: "mm" } },
    { type: "DistanceY", first: 4, first_pos: 3, value: { value: 40, unit: "mm" } },
    { type: "Radius", first: 4, value: { value: 2.5, unit: "mm" } },
    { type: "Tangent", first: 4, second: 5 },
    { type: "Diameter", first: 5, value: { value: 5, unit: "mm" } },
    { type: "DistanceY", first: 5, first_pos: 3, value: { value: 40, unit: "mm" } } ] }
# 6: Angle — geo 6, line from (5,50) at 45 deg to geo 0, as long as geo 0
mcp sketch_add_geometry { doc: <handle>, sketch: "ConstraintBed",
  geometry: [ { kind: "line_segment", start: [5, 50], end: [47.43, 92.43] } ],
  constraints: [
    { type: "Angle", first: 0, second: 6, value: { value: 45, unit: "deg" } },
    { type: "Equal", first: 6, second: 0 },
    { type: "DistanceX", first: 6, first_pos: 1, value: { value: 5, unit: "mm" } },
    { type: "DistanceY", first: 6, first_pos: 1, value: { value: 50, unit: "mm" } } ] }
# 7: Symmetric — geo 7 and 8, two points mirrored about the V axis (-2)
mcp sketch_add_geometry { doc: <handle>, sketch: "ConstraintBed",
  geometry: [ { kind: "point", start: [-10, 60] }, { kind: "point", start: [10, 60] } ],
  constraints: [
    { type: "Symmetric", first: 7, first_pos: 1, second: 8, second_pos: 1, third: -2 },
    { type: "DistanceX", first: 7, first_pos: 1, second: 8, second_pos: 1, value: { value: 20, unit: "mm" } },
    { type: "DistanceY", first: 7, first_pos: 1, value: { value: 60, unit: "mm" } } ] }
# 8: Block — geo 9, circle pinned whole by one Block
mcp sketch_add_geometry { doc: <handle>, sketch: "ConstraintBed",
  geometry: [ { kind: "circle", center: [80, 60], radius: { value: 3, unit: "mm" } } ],
  constraints: [ { type: "Block", first: 9 } ] }
```
**And** the schema boundary of `sketch_add_constraint` is probed with three malformed constraints, each in its own call  
```
mcp sketch_add_constraint { doc: <handle>, sketch: "ConstraintBed", constraints: [ { type: "Symmetry", first: 0 } ] }
mcp sketch_add_constraint { doc: <handle>, sketch: "ConstraintBed", constraints: [ { type: "Horizontal" } ] }
mcp sketch_add_constraint { doc: <handle>, sketch: "ConstraintBed", constraints: [ { type: "Horizontal", first: 0, first_pos: 4 } ] }
```

**Then** every type in the enum is accepted — verify: all eight calls return `status=OK` with `mutation.rolled_back=false`, and together they cover all 16 members `Coincident Horizontal Vertical Parallel Perpendicular Tangent Equal Symmetric PointOnObject Block Distance DistanceX DistanceY Radius Diameter Angle`  
**And** returned solver ids are 1-based — verify: call 1 returns `constraint_ids` `[1, 2, 3]`, never `0`  
**And** each call's ids continue the sketch's count — verify: each call returns `constraint_ids` that start at the constraint count before the call plus 1 and run without a gap (call 2 `[4..7]`, call 3 `[8..11]`, call 4 `[12..15]`, call 5 `[16..21]`, call 6 `[22..25]`, call 7 `[26..28]`, call 8 `[29]`)  
**And** ids match the read back — verify: `mcp query_sketch_info { doc: <handle>, sketch: "ConstraintBed" }` lists constraints with `id` running `1..29` and no `id=0`, and each `type` matches the call that sent it  
**And** dimensional constraints carry their unit — verify: the same read reports `value` as `{value: 2.5, unit: "mm"}` for the Radius and `{value: 45, unit: "deg"}` for the Angle  
**And** the sketch is fully constrained and not redundant — verify: `mcp verify_sketch { doc: <handle>, sketch: "ConstraintBed" }` returns `status=OK` with `subject.dof=0`, `subject.constraint_count=29`, `subject.redundant=[]` and `subject.conflicting=[]`  
**And** a 17th type is a schema reject — verify: the `Symmetry` call is refused against the 16-member enum  
**And** `first` is required — verify: the `{ type: "Horizontal" }` call is refused; `required` is `["type","first"]`  
**And** a `*_pos` outside 0..3 is a schema reject — verify: the `first_pos: 4` call is refused against the enum `[0,1,2,3]`  
**And** the three rejects changed nothing — verify: `mcp verify_sketch { doc: <handle>, sketch: "ConstraintBed" }` still reports `subject.constraint_count=29`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the geometry carries visible constraint markers and dimension labels — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-06-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and describe what is on screen: five lines, three circles and two points, all in the fully-constrained colour (green), with small constraint glyphs drawn against them. One line lies horizontal along the H axis from the origin and one stands vertical; a third line runs parallel to the first; a short line stands perpendicular on the first; one line rises at 45 degrees. Two equal small circles touch at one point rather than overlap or stand apart. Two points sit mirror-wise either side of the V axis. Numeric dimension labels including 60, 2.5, 5 and 45 are drawn beside their geometry. Count the distinct glyph and label marks visible and say how many you see. No geometry is clipped at a viewport edge, no orange (redundant) or red (conflicting) geometry, no error dialog. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; do not infer the glyphs from the list of 16 accepted types.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-07: sketch_set_datum drives a downstream Pad

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.6 (`sketch_set_datum`), `verification-design.md` §5 (verify_shape)

**Given** a fully constrained 10 x 40 mm rectangle sketch named `TabProfile` exists, with a driving `DistanceX` constraint named `TabWidth` set to 10 mm — verify: `mcp query_sketch_info { doc: <handle>, sketch: "TabProfile" }` shows `TabWidth` with `value={value:10,unit:"mm"}` and `driving=true`  
**And** a 5 mm Pad named `TabPad` consumes that sketch — verify: `mcp query_mass_properties { doc: <handle>, object: "TabPad" }` returns `volume` near `2000.0`  
**And** the narrow starting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-07-before.png"}' | & cua-driver call get_window_state`  

**When** the driving dimension is changed from 10 mm to 25 mm  
```
mcp sketch_set_datum { doc: <handle>, sketch: "TabProfile",
                       constraint: "TabWidth", value: { value: 25, unit: "mm" } }
```
**And** the downstream solid is recomputed and re-measured  
```
mcp document_recompute { doc: <handle> }
mcp query_mass_properties { doc: <handle>, object: "TabPad" }
```

**Then** the datum edit commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** the new datum is stored — verify: `mcp query_sketch_info { doc: <handle>, sketch: "TabProfile" }` reports `TabWidth` with `value={value:25,unit:"mm"}`  
**And** the sketch stays fully constrained — verify: `mcp verify_sketch { doc: <handle>, sketch: "TabProfile" }` returns `status=OK` with `subject.dof=0`  
**And** the Pad volume tracks the change — verify: `mcp query_mass_properties { doc: <handle>, object: "TabPad" }` returns `volume` near `5000.0` (25 x 40 x 5), within 0.1 %  
**And** the solid stays valid — verify: `mcp verify_shape { doc: <handle>, object: "TabPad" }` returns `status=OK`  
**And** `value` and `sense` together are rejected — verify: `mcp sketch_set_datum { doc: <handle>, sketch: "TabProfile", constraint: "TabWidth", value: { value: 25, unit: "mm" }, sense: "internal" }` returns `status=INVALID_INPUT` naming `sketch_set_datum requires exactly one of 'value' and 'sense'`  
**And** a non-driving constraint is rejected — verify: setting a datum on a reference (non-driving) constraint returns `status=INVALID_INPUT` naming `is not driving; its datum is read-only`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the solid on screen grew wider and the profile under it followed — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-07-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and describe what changed on screen: in the before image the shaded solid is a narrow tab, clearly much longer in one direction than the other; in the after image it is visibly wider, closer to two-thirds as wide as it is long. The sketch profile beneath it is still one closed rectangle, and its width tracked the solid rather than staying behind. With the sketch open in edit mode (Preconditions, **Sketch edit mode**) the profile is in the fully-constrained colour and the `TabWidth` label reads 25. No hole, gap, or broken face appeared in the solid; no error dialog. The judgement is on the pixels alone — no MCP status or volume number may stand in for looking at the image; a volume of 5000 reported over a window showing an unchanged narrow tab is the defect this scenario catches.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-08: sketch_toggle_construction on and back

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.6 (`sketch_toggle_construction`)

**Given** a fully constrained sketch named `PlateProfile` holds 4 line segments plus one extra diagonal line at geo_id 4 — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports 5 geometry entries, all with `construction=false`  
**And** the all-normal starting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-08-before.png"}' | & cua-driver call get_window_state`  

**When** the diagonal is turned into construction geometry  
```
mcp sketch_toggle_construction { doc: <handle>, sketch: "PlateProfile", geo_ids: [4] }
```
**And** the state is read, then the flag is toggled back  
```
mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }
mcp sketch_toggle_construction { doc: <handle>, sketch: "PlateProfile", geo_ids: [4] }
```

**Then** the first toggle commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** the flag is on — verify: after the first toggle, `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports the entry at `index=4` with `construction=true`  
**And** nothing else changed — verify: the same read reports `construction=false` for `index` 0..3  
**And** the flag is off again — verify: after the second toggle, the entry at `index=4` reports `construction=false`  
**And** the sketch stays fully constrained across both toggles — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `subject.dof=0` after each  
**And** a repeated geo_id in one call is rejected — verify: `geo_ids: [4, 4]` returns `status=INVALID_INPUT` naming `is listed twice; a double toggle is a no-op`  
**And** an out-of-range geo_id is rejected — verify: `geo_ids: [99]` returns `status=INVALID_INPUT` naming `is outside the sketch (0..4)`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the diagonal is drawn like the four rectangle edges again — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-08-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and describe what is on screen: five lines — a closed four-edge rectangle plus one diagonal crossing it. In the after image the diagonal is drawn with the same solid line style and colour as the four rectangle edges, matching the before image; it is not a thin dashed blue construction line. All five lines are present, none was deleted by the two toggles. No error dialog. The judgement is on the pixels alone — no MCP status or `construction` field may stand in for looking at the image. If the intermediate construction state was also captured, say whether the diagonal looked visibly different there; a toggle whose only effect was a field value and never reached the screen is a defect.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-09: Unconstrained geometry is rolled back with the geometry

**Priority**: Critical
**Design Ref**: `verification-design.md` §4 (AD-8 pass/fail policy), `verification-design.md` §1 (mutation protocol, AD-5)

**Given** an empty, fully constrained sketch exists — verify: `mcp verify_sketch { doc: <handle>, sketch: "LooseProfile" }` returns `subject.dof=0` and `subject.geometry_count=0`  
**And** the document fingerprint before the call is recorded — verify: `mcp query_tree_summary { doc: <handle> }` and note the object list  
**And** the empty starting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-09-before.png"}' | & cua-driver call get_window_state`  

**When** geometry is sent with no constraints at all  
```
mcp sketch_add_geometry { doc: <handle>, sketch: "LooseProfile",
  geometry: [ { kind: "line_segment", start: [0, 0], end: [60, 0] } ] }
```

**Then** the call does not commit — verify: the envelope returns `status=SPEC_FAILED`, not `OK`  
**And** the rollback is proven — verify: the envelope carries `mutation.rolled_back=true` and `mutation.post_verify.passed=false`  
**And** the cause names the sketch and its dof — verify: `mutation.post_verify.explanation` starts `verify_sketch failed on LooseProfile (dof=` with a non-zero dof  
**And** the geometry is gone too — verify: `mcp query_sketch_info { doc: <handle>, sketch: "LooseProfile" }` returns `geometry=[]`, so the rollback removed the line, not only the failure  
**And** the document is back to its prior state — verify: `mutation.fingerprint_before.digest` equals `mutation.fingerprint_after.digest`, or the rollback state is `rolled_back_via_snapshot`  
**And** no snapshot is left behind — verify: `<session tmp>` (Preconditions) holds no `FCB_TMP_snap_*` folder created by this call, because a proven rollback deletes its snapshot  
**And** the sketch is still gradeable — verify: `mcp verify_sketch { doc: <handle>, sketch: "LooseProfile" }` returns `status=OK` with `subject.dof=0`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* no line was left on screen by the rolled-back call — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-09-after.png"}' | & cua-driver call get_window_state` (take the before capture the same way), then `Read` both PNGs and describe what is on screen: in both images an empty sketch — the axis cross only, with no straight segment running out from the origin and no white or amber unconstrained line anywhere in the viewport. The two images are indistinguishable apart from framing. No error dialog. The judgement is on the pixels alone — no MCP status, `geometry=[]` read, or fingerprint match may stand in for looking at the image. A `rolled_back=true` claim over a window still showing the loose line is the exact defect this scenario catches.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-10: sketch_remove_geometry cascades its constraints

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.6 (`sketch_remove_geometry`)

**Given** a fully constrained 60 x 40 mm rectangle sketch exists with 4 lines and 11 constraints — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` reports `subject.geometry_count=4` and `subject.constraint_count=11`  
**And** the constraint list is recorded — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` lists ids 1..11 with their types  
**And** the intact rectangle is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-10-before.png"}' | & cua-driver call get_window_state`  

**When** one edge of the rectangle is removed  
```
mcp sketch_remove_geometry { doc: <handle>, sketch: "PlateProfile", geo_ids: [3] }
```
**And** what survived is read  
```
mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }
```

**Then** removing the edge leaves the rest under-constrained, so the call is rolled back — verify: the envelope returns `status=SPEC_FAILED` with `mutation.rolled_back=true`  
**And** the cause is the dof, not a crash — verify: `mutation.post_verify.explanation` names `verify_sketch failed on PlateProfile (dof=`  
**And** the rollback restored the edge — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` again reports 4 geometry entries  
**And** the dependent constraints came back too — verify: the same read again reports 11 constraints, proving the cascade was undone as a unit  
**And** the cascade is observable when the result stays constrained — verify: on a sketch where the removed geometry carries only its own constraints, the call returns `status=OK` and `subject.constraint_count` drops by exactly the number of constraints referencing that geo_id  
**And** an out-of-range geo_id is rejected before the transaction — verify: `geo_ids: [7]` returns `status=INVALID_INPUT` naming `is outside the sketch (0..3)` with no `mutation.snapshot_path`  
**And** an empty list is a schema reject — verify: `geo_ids: []` is refused against `minItems: 1`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the rectangle is closed again with no missing side — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-10-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and describe what is on screen: four edges meeting at four corners, one closed rectangle with no open side and no gap where the fourth edge was removed, drawn in the fully-constrained colour (green) rather than the white or amber of under-constrained geometry. The after image matches the before image edge for edge, and its dimension labels are still present. No error dialog. The judgement is on the pixels alone — no MCP status or restored count may stand in for looking at the image; a `rolled_back=true` claim over a window showing a three-sided open profile is the defect this scenario catches.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-11: sketch_remove_constraint by id and by name

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.6 (`sketch_remove_constraint`, constraint reference `anyOf`)

**Given** a fully constrained rectangle sketch exists (the TC-03-04 build, ids 1..11) carrying two reference constraints at the end, so removing either one leaves the grade unchanged. A redundant driving constraint cannot be the removable one: full redundancy is a hard fail, so that sketch cannot be built (Story 10.2 D1). Reference constraints (`driving: false`) remove no freedom and are never redundant. Built with  
```
mcp sketch_add_constraint { doc: <handle>, sketch: "PlateProfile",
  constraints: [
    { type: "DistanceY", first: 1, first_pos: 1, second: 1, second_pos: 2,
      value: { value: 40, unit: "mm" }, driving: false },
    { type: "DistanceX", first: 0, first_pos: 1, second: 0, second_pos: 2,
      value: { value: 60, unit: "mm" }, name: "SpareWidth", driving: false } ] }
```
— verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` lists 13 constraints: id 12 a `DistanceY` with `driving=false` and id 13 named `SpareWidth` with `driving=false`; `mcp verify_sketch` returns `status=OK` with `subject.dof=0`  
**And** the starting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-11-before.png"}' | & cua-driver call get_window_state`  

**When** a constraint is removed by 1-based solver id — the integer branch of the `anyOf`  
```
mcp sketch_remove_constraint { doc: <handle>, sketch: "PlateProfile", constraints: [12] }
```
**And** a constraint is removed by name — the string branch of the same `anyOf`  
```
mcp sketch_remove_constraint { doc: <handle>, sketch: "PlateProfile", constraints: ["SpareWidth"] }
```

**Then** the id branch works — verify: the first call returns `status=OK` with `mutation.rolled_back=false`  
**And** the name branch works — verify: the second call returns `status=OK` with `mutation.rolled_back=false`; `SpareWidth` moved from id 13 to id 12 after the first removal, and the name still finds it  
**And** the count drops by one each time — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports 12 constraints after the first call and 11 after the second  
**And** the grade never changed — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `status=OK` with `subject.dof=0` after each call  
**And** the named constraint is gone — verify: the same read lists no constraint named `SpareWidth`  
**And** id `0` is a schema reject — verify: `constraints: [0]` is refused; the integer branch has `minimum: 1`, because solver ids are 1-based  
**And** an unknown name is rejected — verify: `constraints: ["NoSuchConstraint"]` returns `status=INVALID_INPUT` naming `no constraint named 'NoSuchConstraint' in the sketch`  
**And** a wrong-typed reference is a schema reject — verify: `constraints: [ { id: 3 } ]` is refused; the `anyOf` accepts only an integer or a string  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the profile is still closed and the `SpareWidth` label is gone from the screen — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-11-after.png"}' | & cua-driver call get_window_state` (take the before capture the same way), then `Read` both PNGs and describe what changed on screen: the four rectangle edges are still joined at four corners with no gap and stay in the fully-constrained colour, the geometry did not shift or collapse, and the two reference dimension labels visible in the before image (drawn in FreeCAD's reference-dimension colour, not the driving one) — including `SpareWidth` — are no longer drawn in the after image. The driving labels 60 and 40 are still drawn. No edge was deleted along with the constraints. No error dialog. The judgement is on the pixels alone — no MCP status or constraint count may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-12: A fully redundant constraint is a hard fail and rolls back

**Priority**: Critical
**Design Ref**: `verification-design.md` §4.2 (pass/warn/fail policy, AD-8), Story 10.2 D1/D2

FreeCAD 1.1 treats full redundancy as an execution error: `SketchObject::execute` reports "Sketch with redundant constraints" and skips rebuilding the shape. The bridge follows FreeCAD (Story 10.2 D1/D2): a mutation that makes a sketch fully redundant fails post-verify step 1 (recompute clean), returns `RECOMPUTE_ERROR` and rolls back. Partial redundancy only warns (`sketch.partially_redundant`).

**Given** a fully constrained 60 x 40 mm rectangle sketch exists — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `status=OK` with `subject.dof=0`, `subject.redundant=[]` and `subject.constraint_count=11`  
**And** the healthy starting state is captured — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-12-before.png"}' | & cua-driver call get_window_state`, then close edit mode  

**When** a constraint that repeats information the sketch already carries is added — a second `Horizontal` on a line the solver already holds horizontal  
```
mcp sketch_add_constraint { doc: <handle>, sketch: "PlateProfile",
  constraints: [ { type: "Horizontal", first: 0 } ] }
```
**And** the sketch is graded  
```
mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }
```

**Then** the redundant constraint does not commit — verify: the mutation envelope returns `status=RECOMPUTE_ERROR`, never `OK`  
**And** the recompute gate fired — verify: the envelope carries `mutation.post_verify.recompute_clean=false` and `mutation.post_verify.passed=false`  
**And** the cause names the sketch — verify: `mutation.post_verify.explanation` starts `recompute left 1 object(s) invalid: PlateProfile:`  
**And** the rollback is proven — verify: the envelope carries `mutation.rolled_back=true`  
**And** the redundant constraint is gone — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports 11 constraints, the same as the `Given`  
**And** the sketch is healthy again — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `status=OK` with `subject.dof=0`, `subject.redundant=[]` and no `sketch.partially_redundant` warning  
**And** the document recomputes clean — verify: `mcp verify_recompute { doc: <handle> }` returns `status=OK`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the profile is unchanged and still coloured as a healthy sketch — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-12-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and describe what is on screen: the same closed rectangle at the same size and position as the before image, its edges drawn in the fully-constrained colour (green), not the orange FreeCAD uses for a redundant sketch. No extra horizontal glyph is drawn on the bottom edge, and the edit view shows no "Redundant constraints" notice. No modal error dialog blocks the window. The judgement is on the pixels alone — no MCP status or rollback field may stand in for looking at the image; an orange profile after a `rolled_back=true` claim is the defect this scenario catches.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-13: sketch_add_external_geometry projects a model edge

**Priority**: Critical
**Design Ref**: `verification-design.md` §3 (TNP guard, AD-7), `mcp-tools-design.md` §1.2 (selectors)

**Given** a Body holds a 60 x 40 x 5 mm plate solid named `PlatePad` — verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume` near `12000.0`  
**And** a sketch named `BossProfile` sits on the plate's top face — verify: `mcp verify_sketch { doc: <handle>, sketch: "BossProfile" }` returns `status=OK`  
**And** the target edge name is known — verify: the topology oracle (Preconditions) lists `PlatePad` edges; pick a 60 mm edge (`Edge3` on 1.1.4), written `<edge>` below. A 5 mm vertical edge (`Edge1`, `Edge2`) projects onto the sketch plane as a single point, not a curve. `query_object` returns properties only and names no edge  
**And** the pre-projection state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-13-before.png"}' | & cua-driver call get_window_state`  

**When** one edge of the plate is projected into the sketch  
```
mcp sketch_add_external_geometry { doc: <handle>, sketch: "BossProfile",
  edge: { kind: "mapped_name", object: "PlatePad", mapped_name: "<edge>" } }
```

**Then** the projection commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** the sketch stays fully constrained — verify: `mcp verify_sketch { doc: <handle>, sketch: "BossProfile" }` returns `status=OK` with `subject.dof=0`; external geometry adds no freedom  
**And** the TNP audit ran and is clean — verify: the mutation envelope carries `mutation.post_verify.tnp_audit.status=CLEAN` with `findings=[]` and `counts.PASS` of 1 or more. The result lists only non-PASS findings and counts every verdict, so the references the audit checked appear in `counts`, and none is `REPOINTED`, `BROKEN` or `UNSUPPORTED`  
**And** the audit recorded the element map version — verify: the same block carries a non-empty `tnp_audit.element_map_version`  
**And** the reference is held by the sketch — verify: `mcp query_dependencies { doc: <handle> }` shows an edge from `BossProfile` to `PlatePad`  
**And** an unknown source object is rejected before the transaction — verify: `edge: { kind: "mapped_name", object: "NoSuchPad", mapped_name: "Edge1" }` returns `status=INVALID_INPUT` naming `unknown object in edge selector: NoSuchPad`  
**And** a face selector is rejected — verify: a selector whose `mapped_name` resolves to a face returns `status=INVALID_INPUT` naming `resolves to a Face, not an Edge`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* a projected curve now lies along one edge of the plate — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-13-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and describe what changed on screen: the after image shows one new sketch curve that was not in the before image, running along a boundary of the shaded plate and matching that boundary's length and direction. It is drawn in the distinct external-geometry colour, unlike the sketch's own geometry. It lies on the plate, not offset in space beside or above it. The solid itself is unchanged in shape. No error dialog. The judgement is on the pixels alone — no MCP status, TNP verdict, or dependency read may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-14: Axis references -1 and -2 resolve as operands

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.6 (constraint `first`: -1 HAxis, -2 VAxis), `verification-design.md` §4 (AD-8)

An unpinned rectangle cannot exist as a starting state: AD-8 rolls back any mutation that leaves a sketch under-constrained. So the axis constraints are sent in the same call that builds the rectangle, and they are the only constraints that fix its position.

**Given** two empty sketches exist on XY, `AxisProfile` and `AxisFirst` — verify: `mcp query_sketch_info { doc: <handle>, sketch: "AxisProfile" }` returns `geometry=[]`  

**When** a 60 x 40 mm rectangle is added whose shape is fully constrained and whose position is fixed only by a corner on the H axis (`-1`) and a corner on the V axis (`-2`)  
```
mcp sketch_add_geometry { doc: <handle>, sketch: "AxisProfile",
  geometry: [
    { kind: "line_segment", start: [0, 0],   end: [60, 0] },
    { kind: "line_segment", start: [60, 0],  end: [60, 40] },
    { kind: "line_segment", start: [60, 40], end: [0, 40] },
    { kind: "line_segment", start: [0, 40],  end: [0, 0] }
  ],
  constraints: [
    { type: "Coincident", first: 0, first_pos: 2, second: 1, second_pos: 1 },
    { type: "Coincident", first: 1, first_pos: 2, second: 2, second_pos: 1 },
    { type: "Coincident", first: 2, first_pos: 2, second: 3, second_pos: 1 },
    { type: "Coincident", first: 3, first_pos: 2, second: 0, second_pos: 1 },
    { type: "Horizontal", first: 0 },
    { type: "Horizontal", first: 2 },
    { type: "Vertical",   first: 1 },
    { type: "Vertical",   first: 3 },
    { type: "DistanceX",  first: 0, first_pos: 1, second: 0, second_pos: 2, value: { value: 60, unit: "mm" } },
    { type: "DistanceY",  first: 1, first_pos: 1, second: 1, second_pos: 2, value: { value: 40, unit: "mm" } },
    { type: "PointOnObject", first: 0, first_pos: 1, second: -1 },
    { type: "PointOnObject", first: 3, first_pos: 1, second: -2 }
  ] }
```
**And** a line is added to the second sketch with an axis as `first`  
```
mcp sketch_add_geometry { doc: <handle>, sketch: "AxisFirst",
  geometry: [ { kind: "line_segment", start: [0, 0], end: [20, 0] } ],
  constraints: [
    { type: "Coincident", first: -1, first_pos: 1, second: 0, second_pos: 1 },
    { type: "Horizontal", first: 0 },
    { type: "Distance", first: 0, first_pos: 1, second: 0, second_pos: 2, value: { value: 20, unit: "mm" } } ] }
```
**And** an undefined negative index is sent  
```
mcp sketch_add_constraint { doc: <handle>, sketch: "AxisProfile",
  constraints: [ { type: "PointOnObject", first: 1, first_pos: 2, second: -9 } ] }
```

**Then** `-1` and `-2` resolve as HAxis and VAxis — verify: the first call returns `status=OK` with `mutation.rolled_back=false`  
**And** the axis pins are what fixes the position — verify: `mcp verify_sketch { doc: <handle>, sketch: "AxisProfile" }` returns `status=OK` with `subject.dof=0` and `subject.redundant=[]`; the 10 shape constraints alone leave 2 degrees of freedom  
**And** the axis constraints are readable — verify: `mcp query_sketch_info { doc: <handle>, sketch: "AxisProfile" }` lists both `PointOnObject` constraints at 1-based ids `11` and `12`  
**And** an axis works as `first` too — verify: the second call returns `status=OK`, because `first` is a plain integer and negative values address the axes; `mcp verify_sketch { doc: <handle>, sketch: "AxisFirst" }` returns `subject.dof=0`  
**And** an undefined negative index is rejected — verify: the third call returns `status=INVALID_INPUT` naming the geo id; only `-1` and `-2` name axes, and lower values name external geometry the sketch has not projected  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the profile sits on the sketch axes — verify: open `AxisProfile` in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-14-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and describe what is on screen: a closed green rectangle whose bottom edge lies on the horizontal axis line and whose left edge lies on the vertical axis line, with point-on-object markers at the two pinned corners. The rectangle is four joined edges and did not collapse or invert. No orange or red geometry, no error dialog. The judgement is on the pixels alone — no MCP status or `dof` number may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-15: Zero, negative and very large datum values

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.6 (`sketch_set_datum`), `verification-design.md` §4

**Given** a fully constrained sketch carries a driving `Radius` named `BossRadius` at 2.5 mm and a driving `Distance` named `HoleSpacing` at 40 mm — verify: `mcp query_sketch_info { doc: <handle>, sketch: "BossProfile" }` shows both with `driving=true`  
**And** the healthy starting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-15-before.png"}' | & cua-driver call get_window_state`  

**When** a zero radius is tried  
```
mcp sketch_set_datum { doc: <handle>, sketch: "BossProfile",
                       constraint: "BossRadius", value: { value: 0, unit: "mm" } }
```
**And** a negative distance is tried  
```
mcp sketch_set_datum { doc: <handle>, sketch: "BossProfile",
                       constraint: "HoleSpacing", value: { value: -5, unit: "mm" } }
```
**And** the window is captured before the large value, for the closing visual — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-15-after.png"}' | & cua-driver call get_window_state`, then close edit mode  
**And** a distance far outside any real part is tried  
```
mcp sketch_set_datum { doc: <handle>, sketch: "BossProfile",
                       constraint: "HoleSpacing", value: { value: 1e9, unit: "mm" } }
```

**Then** a zero radius is refused — verify: the first call returns a non-`OK` status; a `Radius` datum must be non-zero  
**And** the refusal is pre-transaction — verify: the first envelope carries no `mutation.snapshot_path`, so no snapshot was written  
**And** a negative distance is refused or rolled back — verify: the second call returns `status=INVALID_INPUT`, or `status=SPEC_FAILED` with `mutation.rolled_back=true`  
**And** a 1e9 mm distance does not commit a broken sketch — verify: the third call returns either `INVALID_INPUT`, or `OK` with `mcp verify_sketch { doc: <handle>, sketch: "BossProfile" }` still reporting `subject.dof=0` and `subject.malformed=[]`  
**And** the original datum survives every refusal — verify: after all three calls, `mcp query_sketch_info { doc: <handle>, sketch: "BossProfile" }` reports `BossRadius` at `{value: 2.5, unit: "mm"}`. A non-finite value is not tested: JSON cannot carry Infinity, so no MCP client can send it  
**And** no snapshot is orphaned — verify: `<session tmp>` (Preconditions) holds no `FCB_TMP_snap_*` folder created by these three calls  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the sketch on screen is untouched by the zero and negative refusals — verify: `Read` the before PNG and the `tc-03-15-after.png` taken before the large-value call (a committed 1e9 mm datum moves geometry 1000 km away, so a capture after it cannot show the profile) and describe what is on screen: the boss circle is still a visible round circle of the same size as in the before image — not collapsed to a dot and not enlarged past the viewport border. The profile is at the same place and the same proportions as before, not mirrored or flipped by a negative value. The `BossRadius` label reads 2.5. No error dialog was left open by any of the three refusals. The judgement is on the pixels alone — no MCP status or datum read-back may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-16: Conflicting constraints name the offending ids

**Priority**: Critical
**Design Ref**: `verification-design.md` §4.2 (hard fail on conflicting/malformed), `mcp-tools-design.md` §3.6

**Given** a fully constrained 60 x 40 mm rectangle sketch exists with a driving `DistanceX` named `PlateWidth` at 60 mm — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `subject.dof=0` and `subject.conflicting=[]`  
**And** the constraint count before the call is recorded — verify: the same read reports `subject.constraint_count`  
**And** the healthy starting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-16-before.png"}' | & cua-driver call get_window_state`  

**When** a second, contradictory length is added on the same edge — 45 mm where the sketch already says 60 mm  
```
mcp sketch_add_constraint { doc: <handle>, sketch: "PlateProfile",
  constraints: [ { type: "DistanceX", first: 0, first_pos: 1, second: 0, second_pos: 2,
                   value: { value: 45, unit: "mm" }, name: "ConflictWidth" } ] }
```

**Then** the conflicting set does not commit — verify: the envelope returns `status=RECOMPUTE_ERROR`, not `OK`: FreeCAD marks a conflicting sketch in error, so post-verify step 1 (recompute clean) fails first  
**And** the rollback is proven — verify: the envelope carries `mutation.rolled_back=true` and `mutation.post_verify.recompute_clean=false`  
**And** the cause names the sketch — verify: `mutation.post_verify.explanation` starts `recompute left 1 object(s) invalid: PlateProfile:`  
**And** the offending ids are reported — verify: the same explanation names the conflicting solver ids (FreeCAD's `conflicting constraints:` list), not a bare message  
**And** the conflicting constraint is gone — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` lists no constraint named `ConflictWidth`  
**And** the count is back to its prior value — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` reports the same `subject.constraint_count` as the `Given`  
**And** the sketch is healthy again — verify: the same envelope returns `status=OK` with `subject.dof=0` and `subject.conflicting=[]`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the rectangle is at its original width and shows no conflict colouring — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-16-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and describe what is on screen: one closed rectangle at the same width and depth as the before image, not shrunk toward the shorter contradictory length. Its edges are drawn in the fully-constrained colour (green), not the red FreeCAD uses for conflicting constraints. Exactly one width dimension label is drawn, reading 60; there is no second overlapping width label. No error dialog was left open. The judgement is on the pixels alone — no MCP status or constraint count may stand in for looking at the image; a `rolled_back=true` claim over a window showing a red or 45-wide profile is the defect this scenario catches.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-17: Unknown sketch name and unknown geo_id

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.3 (result envelope and error surface, AD-17)

**Given** a document holds exactly one sketch, `PlateProfile`, with 4 geometry entries — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports 4 entries  
**And** the snapshot folders already in the session temp folder are recorded — verify: list the `FCB_TMP_snap_*` entries of `<session tmp>` (Preconditions)  
**And** the untouched starting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-17-before.png"}' | & cua-driver call get_window_state`  

**When** a sketch that does not exist is named  
```
mcp sketch_add_geometry { doc: <handle>, sketch: "NoSuchSketch",
  geometry: [ { kind: "point", start: [0, 0] } ] }
```
**And** a geo_id past the end of a real sketch is named  
```
mcp sketch_remove_geometry { doc: <handle>, sketch: "PlateProfile", geo_ids: [99] }
```
**And** an object that exists but is not a sketch is named  
```
mcp sketch_add_constraint { doc: <handle>, sketch: "PlatePad",
  constraints: [ { type: "Horizontal", first: 0 } ] }
```

**Then** an unknown sketch is `INVALID_INPUT` — verify: the first call returns `status=INVALID_INPUT` naming `unknown object: NoSuchSketch`  
**And** an out-of-range geo_id is `INVALID_INPUT` — verify: the second call returns `status=INVALID_INPUT` naming `is outside the sketch (0..3)`  
**And** a non-sketch object is `INVALID_INPUT` — verify: the third call returns `status=INVALID_INPUT` naming `object is not a sketch: PlatePad`  
**And** no transaction opened — verify: none of the three envelopes carries `mutation.snapshot_path`  
**And** no snapshot was written — verify: after all three calls `<session tmp>` lists the same `FCB_TMP_snap_*` entries as the `Given`  
**And** the document is untouched — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` lists the same objects as the `Given`  
**And** the status is the closed-set value — verify: each `status` is exactly `INVALID_INPUT`, never a free-text error or `SPEC_FAILED`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is undisturbed by the three refusals — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-17-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and describe what is on screen: the same `PlateProfile` rectangle with its four edges still joined, no stray dot drawn at the sketch origin, no missing edge, and nothing added or removed anywhere in the viewport. The two images are indistinguishable apart from framing. No error dialog, crash banner, or greyed-out window. The judgement is on the pixels alone — no MCP status or tree read may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-18: Wrong unit on a datum is a schema reject

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.4 (quantity fields), `mcp-tools-design.md` §3.6

**Given** a fully constrained sketch carries a driving `Distance` named `HoleSpacing` at 40 mm and a driving `Angle` named `RibAngle` at 45 deg — verify: `mcp query_sketch_info { doc: <handle>, sketch: "BracketProfile" }` shows `HoleSpacing` with `unit: "mm"` and `RibAngle` with `unit: "deg"`  
**And** the starting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-18-before.png"}' | & cua-driver call get_window_state`  

**When** degrees are sent where the schema allows only millimetres  
```
mcp sketch_set_datum { doc: <handle>, sketch: "BracketProfile",
                       constraint: "HoleSpacing", value: { value: 10, unit: "deg" } }
```
**And** a bare number with no unit at all is sent  
```
mcp sketch_add_geometry { doc: <handle>, sketch: "BracketProfile",
  geometry: [ { kind: "circle", center: [20, 20], radius: 2.5 } ] }
```
**And** a quantity missing its `value` is sent  
```
mcp sketch_set_datum { doc: <handle>, sketch: "BracketProfile",
                       constraint: "HoleSpacing", value: { unit: "mm" } }
```

**Then** a `deg` datum on a length constraint does not commit — verify: the first call returns a non-`OK` status; `sketch_set_datum.value` accepts `["mm","deg"]` at the schema, and the use case then refuses the wrong dimension for a `Distance`  
**And** the refusal names the unit — verify: the first call's detail names the allowed unit for that constraint type  
**And** a geometry `radius` in `deg` is a hard schema reject — verify: `radius: { value: 2.5, unit: "deg" }` is refused; `_LENGTH_QUANTITY_SCHEMA` allows the enum `["mm"]` only  
**And** a bare number is a schema reject — verify: the second call is refused; the quantity schema requires an object with both `value` and `unit`  
**And** a missing `value` is a schema reject — verify: the third call is refused against `required: ["value","unit"]`  
**And** an extra key inside a quantity is a schema reject — verify: `value: { value: 10, unit: "mm", tolerance: 0.1 }` is refused; the quantity schema sets `additionalProperties: false`  
**And** the sketch is unchanged — verify: `mcp query_sketch_info { doc: <handle>, sketch: "BracketProfile" }` still reports `HoleSpacing` at `{value: 40, unit: "mm"}`  
**And** an angle constraint still accepts `deg` — verify: `mcp sketch_set_datum { doc: <handle>, sketch: "BracketProfile", constraint: "RibAngle", value: { value: 30, unit: "deg" } }` returns `status=OK`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* no stray circle appeared and the only change is the accepted angle edit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-18-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and describe what is on screen: there is no new circle drawn in the middle of the profile that was absent from the before image. The `HoleSpacing` dimension label still reads 40 and the distance it marks is unchanged on screen. The `RibAngle` label reads 30 and the angled geometry it drives has visibly swung closer, which is the one difference between the two images. Nothing collapsed or exploded from a unit read as the wrong dimension. No error dialog. The judgement is on the pixels alone — no MCP status or datum read-back may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-19: Constraint referencing a removed geo_id

**Priority**: Critical
**Design Ref**: `verification-design.md` §4.2 (malformed constraints are a hard fail), `verification-design.md` §1

**Given** a fully constrained sketch holds 4 lines at geo_ids 0..3 — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` reports `subject.geometry_count=4` and `subject.malformed=[]`  
**And** a spare sketch exists whose geometry can be removed without breaking its grade — verify: `mcp query_sketch_info { doc: <handle>, sketch: "ScrapProfile" }` reports its entries  
**And** the starting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-19-before.png"}' | & cua-driver call get_window_state`  

**When** a geometry is removed from the spare sketch so a later reference to it is stale  
```
mcp sketch_remove_geometry { doc: <handle>, sketch: "ScrapProfile", geo_ids: [1] }
```
**And** the geo_id that no longer exists is referenced  
```
mcp sketch_add_constraint { doc: <handle>, sketch: "ScrapProfile",
  constraints: [ { type: "Horizontal", first: 1 } ] }
```
**And** a geo_id far past the end is referenced in one batch alongside a valid constraint  
```
mcp sketch_add_constraint { doc: <handle>, sketch: "PlateProfile",
  constraints: [ { type: "Horizontal", first: 0 },
                 { type: "Horizontal", first: 88 } ] }
```

**Then** a stale geo_id is refused — verify: the second call returns `status=INVALID_INPUT` naming the geo_id as outside the sketch  
**And** the refusal is pre-transaction — verify: the second call's envelope carries no `mutation.snapshot_path`  
**And** a mixed batch is refused as a whole — verify: the third call returns a non-`OK` status; the valid `Horizontal` at index 0 is not applied on its own  
**And** the valid constraint did not land — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports the same `constraints` list as before the third call  
**And** no malformed constraint was committed — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `subject.malformed=[]`  
**And** the sketch still grades PASS — verify: the same envelope returns `status=OK` with `subject.dof=0`  
**And** no snapshot is left behind — verify: `<session tmp>` (Preconditions) holds no `FCB_TMP_snap_*` folder created by these calls  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* `PlateProfile` on screen is exactly as it was, with no half-applied constraint — verify: open the sketch in edit mode first (Preconditions, **Sketch edit mode**), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-19-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and describe what is on screen: `PlateProfile` is four joined edges forming a closed rectangle in the fully-constrained colour (green), identical to the before image, with no new horizontal glyph added to its bottom edge. In `ScrapProfile` exactly one segment fewer is drawn than in the before image, and nothing else there changed. No dangling line fragment, no error dialog. The judgement is on the pixels alone — no MCP status or constraint list read may stand in for looking at the image; a partially applied batch that landed one of its two constraints would show that extra glyph here.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-20: A moved external-geometry source is flagged and rolled back

**Priority**: Critical
**Design Ref**: `verification-design.md` §3.2 (TNP audit layers, AD-7), `verification-design.md` §3.3 (verdict shape)

Changing the Pad length moves the top face that `BossProfile` is attached to and the edge it projects. The TNP audit grades that reference `REPOINTED`, which fails the mutation. A deleted source (`BROKEN`) has no MCP route: no typed tool deletes an object. The layer-0 `BROKEN` finding is covered by TC-05-17.

**Given** a Body holds the 60 x 40 x 5 mm plate `PlatePad` (volume `12000.0`) and a sketch `BossProfile` attached to its top face, as in TC-03-13  
**And** `BossProfile` holds its own geometry: a circle at `[30, 20]` pinned by a centre `DistanceX` 30 mm, a centre `DistanceY` 20 mm and a driving `Radius` named `BossRadius` at 5 mm — verify: `mcp verify_sketch { doc: <handle>, sketch: "BossProfile" }` returns `status=OK` with `subject.dof=0`  
**And** `BossProfile` holds external geometry projected from a 60 mm edge of `PlatePad` (TC-03-13) — verify: `mcp query_dependencies { doc: <handle> }` shows an edge from `BossProfile` to `PlatePad`  
**And** the last mutation's TNP audit was clean — verify: the `sketch_add_external_geometry` envelope carried `mutation.post_verify.tnp_audit.status=CLEAN`  
**And** the intact state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-20-before.png"}' | & cua-driver call get_window_state`  

**When** the source is moved by changing the Pad that owns the face and the projected edge  
```
mcp feature_set_parameters { doc: <handle>, feature: "PlatePad",
                             parameters: { Length: { value: 30, unit: "mm" } } }
```
**And** a harmless mutation is then run on the sketch, and the audit it carries is read  
```
mcp sketch_set_datum { doc: <handle>, sketch: "BossProfile",
                       constraint: "BossRadius", value: { value: 4, unit: "mm" } }
```

**Then** the TNP audit runs on every mutation — verify: each mutation envelope carries a `mutation.post_verify.tnp_audit` block with a `status` and a `findings` list  
**And** the moved reference is graded `REPOINTED` — verify: the `feature_set_parameters` audit has `status=FLAGGED` and a finding with `verdict=REPOINTED`, `owner=BossProfile` and `prop=AttachmentSupport`  
**And** a `REPOINTED` finding fails the mutation — verify: that call returns `status=SPEC_FAILED` with `mutation.rolled_back=true`, because only `PASS` and `RE_BASELINED` are allowed to pass  
**And** the explanation names the reference — verify: `mutation.post_verify.explanation` starts `TNP audit flagged` and names `BossProfile.AttachmentSupport REPOINTED`  
**And** the rollback restored the plate — verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume` near `12000.0`  
**And** the harmless mutation passes a clean audit — verify: the `sketch_set_datum` call returns `status=OK`, its `tnp_audit.status` is `CLEAN` with `findings=[]` (the result lists only non-PASS findings)  
**And** the audit reports the build's element map version — verify: `tnp_audit.element_map_version` is non-empty on both the clean and the flagged reading  
**And** the document survives the rollback — verify: `mcp verify_recompute { doc: <handle> }` returns `status=OK` after the failed mutation  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the plate kept its thickness and the sketch still sits on it — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-20-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and describe what is on screen: the shaded solid is still one whole thin plate, as thin as in the before image (the rejected 30 mm length did not land), with no torn, missing, or black-shaded face. `BossProfile` is still drawn on its top face; its circle is a little smaller than before (radius 4, not 5). The projected external curve runs along a real edge of the plate and is not left hanging in space. No error dialog or red error marker blocking the view. The judgement is on the pixels alone — no MCP status, TNP verdict, or recompute result may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-21: Unknown key anywhere is a hard reject

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.3 (error surface, AD-17), `mcp-tools-design.md` §3.6

**Given** a fully constrained sketch exists — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `status=OK`  
**And** the document object list before the call is recorded — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }`  
**And** the starting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-21-before.png"}' | & cua-driver call get_window_state`  

**When** an unknown key is added at the top level of a sketch tool  
```
mcp sketch_create { doc: <handle>, name: "ExtraKey", plane: "XY", visible: true }
```
**And** an unknown key is added inside a nested geometry spec  
```
mcp sketch_add_geometry { doc: <handle>, sketch: "PlateProfile",
  geometry: [ { kind: "point", start: [5, 5], color: "red" } ] }
```
**And** an unknown key is added inside a nested constraint spec  
```
mcp sketch_add_constraint { doc: <handle>, sketch: "PlateProfile",
  constraints: [ { type: "Horizontal", first: 0, weight: 2 } ] }
```
**And** an unknown key is added inside a selector  
```
mcp sketch_add_external_geometry { doc: <handle>, sketch: "PlateProfile",
  edge: { kind: "mapped_name", object: "PlatePad", mapped_name: "Edge1", hint: "top" } }
```

**Then** a top-level unknown key is refused — verify: the first call is rejected; every sketch input schema sets `additionalProperties: false`  
**And** a nested geometry key is refused — verify: the second call is rejected against `_GEOMETRY_SPEC_SCHEMA`, which also sets `additionalProperties: false`  
**And** a nested constraint key is refused — verify: the third call is rejected against `_CONSTRAINT_SPEC_SCHEMA`  
**And** a selector key is refused — verify: the fourth call is rejected against `_SUBELEMENT_SELECTOR_SCHEMA`  
**And** the rejection is a protocol error, not an envelope — verify: each is refused at the schema boundary, so no `status` field and no `mutation` block are returned  
**And** nothing was created — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` lists the same objects as the `Given`, and names no `ExtraKey`  
**And** the sketch is unchanged — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports the same geometry and constraint lists as before  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is undisturbed by all four rejects — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-03-21-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and describe what is on screen: the same `PlateProfile` geometry as the before image and nothing else — no second sketch plane or axis cross from an `ExtraKey` sketch, no isolated dot drawn inside the profile, no extra horizontal glyph on its bottom edge, and no projected external curve along any solid edge. The two images are indistinguishable apart from framing. No error dialog, crash banner, or disconnected-server notice. The judgement is on the pixels alone — no MCP status or tree read may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```
