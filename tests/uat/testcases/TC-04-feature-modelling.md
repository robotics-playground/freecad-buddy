# TC-04: Feature Modelling

Exercises all eleven `feature_*` mutation tools against a live FreeCAD document, plus the four
read tools that grade their result: `query_mass_properties`, `query_object`, `query_placement` and
`verify_shape`. Every solid-producing scenario checks an analytic volume, not only a status code,
because a feature that commits with the wrong dimension still reports `OK`. The mutation protocol
is also under test: a failed feature must roll back with a proven fingerprint and leave no partial
solid, and a recompute that leaves the document invalid must class as `RECOMPUTE_ERROR`, never
`SPEC_FAILED`.

The MCP bridge is the system being built, so its own output is never the test result. Every
`status`, envelope field, `feature_state` summary, fingerprint and `query_screenshot` render below
is a **claim under test**. The test result is the `cua-driver` pixel capture of the real FreeCAD
window, `Read` and judged by the agent. Filesystem entries, exit codes and audit lines corroborate.
A `feature_*` call that returns `OK` with a plausible volume while the window shows no solid passes
every numeric assertion and fails the user completely.

**Host**: GUI through the H2 proxy for every scenario. Every `feature_*` call is a live-document
mutation and every scenario closes on a capture of the human's own FreeCAD window.

## Preconditions

- [ ] FreeCAD GUI is open and the addon spawned the proxy (verify: `netstat -ano | grep :8765` shows LISTENING)
- [ ] The MCP tool surface is complete (verify: `mcp query_capabilities {}` lists 44 tools)
- [ ] PartDesign is available on this build (verify: `mcp feature_body_create { doc: <handle>, name: "ProbeBody" }` returns `status=OK`, not `PartDesign is unavailable on this FreeCAD build`)
- [ ] The host runs the operator auto-approve posture, so a mutation needs no `preview_id` (verify: the addon log carries `SECURITY: mutation auto-approve ENABLED (to require preview_id, clear Auto-approve mutations in the FreeCAD GUI: Edit > Preferences > FreeCAD Buddy, or set FREECAD_BUDDY_AUTO_APPROVE=0)`)
- [ ] Auto-approve is on for this launch: the **Auto-approve mutations** preference is on (the default) and `FREECAD_BUDDY_AUTO_APPROVE` is unset, or the variable is `1` in the environment that launched FreeCAD. The preference off or the variable `0` turns the confirm gate on (verify: the banner line above is present in `%APPDATA%/FreeCAD/v1-1/freecad-buddy/addon.log` for this launch)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` returns a `QOpenGLWidget`)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)

**Confirm convention for this file**: every `feature_*` call below is a geometry-intent mutation and
is gated by AD-10. This file runs under the operator auto-approve posture, so no scenario passes a
`confirm` object. The confirm gate's own negative cases belong to TC-08 and are not repeated here.

**Reference part**: the scenarios build one bracket — a 60 x 40 x 5 mm plate, M5 clearance holes on
40 mm spacing, a 2 mm fillet on the corners. Volumes below are the analytic values for that part.

---

### TC-04-01: feature_body_create empty and adopting a base

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (feature tools), `verification-design.md` §5 (verify_shape)

**Given** a scratch document exists — verify: `mcp document_create { label: "Bracket" }` returns a handle  
**And** a loose solid exists for the adoption case — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns a handle and `mcp query_mass_properties` reports `volume=6000.0`  

**When** an empty Body is created  
```
mcp feature_body_create { doc: <handle>, name: "PlateBody" }
```
**And** a second Body is created that adopts the golden box as its base feature  
```
mcp feature_body_create { doc: <boxhandle>, name: "AdoptBody", base_feature: "Box" }
```

**Then** The empty Body commits — verify: step 1 returns `status=OK` with `mutation.rolled_back=false`  
**And** An empty Body carries no solid — verify: `mcp query_object { doc: <handle>, object: "PlateBody" }` reports no Tip, because a new Body's `Shape` is null until a feature is added  
**And** The Body brings its origin — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` shows an `App::Origin` child under `PlateBody` with its plane, line and point children  
**And** The adoption commits — verify: step 2 returns `status=OK` with `mutation.rolled_back=false`  
**And** The adopted Body reports the base volume — verify: `mcp query_mass_properties { doc: <boxhandle>, object: "AdoptBody" }` returns `volume=6000.0` within 0.1 %  
**And** The adopted Body is a valid solid — verify: `mcp verify_shape { doc: <boxhandle>, object: "AdoptBody" }` returns `status=OK`  
**And** A double adoption is refused — verify: a second `feature_body_create { base_feature: "Box" }` returns `status=INVALID_INPUT` naming `is already adopted by a Body`  
**And** A shapeless base is refused — verify: `base_feature` naming a sketch returns `status=INVALID_INPUT` naming `carries no shape to adopt`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <boxhandle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the adopted 10 x 20 x 30 box standing alone as the adopting Body's solid — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-01-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm one rectangular solid of 10 x 20 x 30 proportions is wholly inside the viewport, and that the empty `PlateBody` contributes no visible geometry. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
mcp document_close { doc: <boxhandle> }
```

---

### TC-04-02: feature_pad Length with analytic volume

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pad`), `verification-design.md` §5

**Given** a Body named `BlockBody` exists — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` names it  
**And** a fully constrained 20 x 30 mm rectangle sketch named `BlockProfile` sits inside it — verify: `mcp verify_sketch { doc: <handle>, sketch: "BlockProfile" }` returns `status=OK` with `subject.dof=0`  

**When** the profile is padded 10 mm  
```
mcp feature_pad { doc: <handle>, body: "BlockBody", profile: "BlockProfile",
                  name: "BlockPad", length: { value: 10, unit: "mm" } }
```
**And** the result is measured  
```
mcp query_mass_properties { doc: <handle>, object: "BlockPad" }
```

**Then** The pad commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** The volume is analytic — verify: `mcp query_mass_properties { doc: <handle>, object: "BlockPad" }` returns `volume` equal to `6000.0` mm³ (20 x 30 x 10) within 0.1 %  
**And** The solid is valid and single — verify: `mcp verify_shape { doc: <handle>, object: "BlockPad" }` returns `status=OK`, and the mutation envelope's `feature_state.shape_summary` reports `solid_count=1` and `is_valid=true`  
**And** The bounding box matches — verify: the same `shape_summary` reports `bbox=[20, 30, 10]` within 0.1 %  
**And** The face count matches a box — verify: the same `shape_summary` reports `face_count=6`, `edge_count=12`, `vertex_count=8`  
**And** The pad became the Body Tip — verify: the same envelope's `feature_state` reports `body="BlockBody"` and `is_tip=true`  
**And** `up_to` defaults to Length — verify: `mcp query_object { doc: <handle>, object: "BlockPad" }` reports the extrude `Type` as `Length`, because `up_to` was omitted  
**And** The post-verify gate passed every step — verify: the envelope carries `mutation.post_verify.passed=true`, `recompute_clean=true`, `is_valid=true` and `tnp_audit.status=CLEAN`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows one padded rectangular solid of 20 x 30 x 10 proportions — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-02-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm a single box-shaped solid whose 20 x 30 footprint is visibly wider than its 10 mm height, wholly inside the viewport, with no second solid and no leftover sketch outline standing proud of it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-03: feature_pad midplane straddles the sketch plane

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pad`, midplane)

**Given** a Body holds a fully constrained 20 x 30 mm rectangle sketch on XY — verify: `mcp verify_sketch { doc: <handle>, sketch: "BlockProfile" }` returns `subject.dof=0`  
**And** a non-midplane 10 mm pad of the same profile was measured for comparison — verify: TC-04-02 CP2 recorded `volume=6000.0` with the solid sitting from z=0 to z=10  

**When** the same profile is padded 10 mm, straddling the sketch plane  
```
mcp feature_pad { doc: <handle>, body: "MidBody", profile: "MidProfile",
                  name: "MidPad", length: { value: 10, unit: "mm" }, midplane: true }
```
**And** the placement and the bounding box are read  
```
mcp query_mass_properties { doc: <handle>, object: "MidPad" }
mcp query_placement { doc: <handle>, object: "MidPad" }
```

**Then** The midplane pad commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** The volume is unchanged — verify: `mcp query_mass_properties { doc: <handle>, object: "MidPad" }` returns `volume=6000.0` within 0.1 %; midplane splits the extent, it does not double it  
**And** The extent is still 10 mm — verify: the mutation envelope's `feature_state.shape_summary` reports `bbox=[20, 30, 10]`  
**And** The solid is symmetric about the sketch plane — verify: `mcp query_mass_properties { doc: <handle>, object: "MidPad" }` reports a bounding box running from z = -5 mm to z = +5 mm, not 0 to 10  
**And** The centre of mass sits on the plane — verify: the same read reports `com.z` equal to `{value: 0, unit: "mm"}` within 0.1 %  
**And** The solid is valid — verify: `mcp verify_shape { doc: <handle>, object: "MidPad" }` returns `status=OK`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows one 20 x 30 x 10 solid straddling the XY plane, half above and half below — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-03-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm the solid sits centred on the origin planes rather than resting entirely on top of the XY plane. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-04: feature_pad reversed, second_length and taper_angle

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pad` optional fields)

**Given** three Bodies each hold an identical fully constrained 20 x 30 mm rectangle sketch on XY — verify: `mcp verify_sketch` returns `subject.dof=0` for each of `RevProfile`, `TwoProfile`, `TaperProfile`  

**When** the profile is padded reversed — the solid grows the other way along the plane normal  
```
mcp feature_pad { doc: <handle>, body: "RevBody", profile: "RevProfile",
                  name: "RevPad", length: { value: 10, unit: "mm" }, reversed: true }
```
**And** a pad is made with a second length — material on both sides, independently sized  
```
mcp feature_pad { doc: <handle>, body: "TwoBody", profile: "TwoProfile",
                  name: "TwoPad", length: { value: 10, unit: "mm" },
                  second_length: { value: 4, unit: "mm" } }
```
**And** a pad is made with a draft angle  
```
mcp feature_pad { doc: <handle>, body: "TaperBody", profile: "TaperProfile",
                  name: "TaperPad", length: { value: 10, unit: "mm" },
                  taper_angle: { value: 5, unit: "deg" } }
```

**Then** All three commit — verify: each envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** `reversed` flips the direction, not the size — verify: `mcp query_mass_properties { doc: <handle>, object: "RevPad" }` returns `volume=6000.0` within 0.1 %, with the bounding box running z = -10 to z = 0  
**And** The property was written — verify: `mcp query_object { doc: <handle>, object: "RevPad" }` reports `Reversed=true`  
**And** `second_length` adds its own material — verify: `mcp query_mass_properties { doc: <handle>, object: "TwoPad" }` returns a volume larger than `6000.0`, and `mcp query_object { doc: <handle>, object: "TwoPad" }` reports `Length2` as `4 mm`  
**And** `taper_angle` changes the side faces — verify: `mcp query_mass_properties { doc: <handle>, object: "TaperPad" }` returns a volume different from `6000.0`, and `mcp query_object { doc: <handle>, object: "TaperPad" }` reports `TaperAngle` as `5 deg`  
**And** All three solids are valid — verify: `mcp verify_shape` returns `status=OK` for each of `RevPad`, `TwoPad`, `TaperPad`  
**And** A taper outside -90..90 degrees is rejected — verify: `taper_angle: { value: 120, unit: "deg" }` returns `status=INVALID_INPUT` naming `taper_angle must be in` its bound, with no `mutation.snapshot_path`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows three distinct padded solids — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-04-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm `RevPad` grows downward from its sketch plane, `TwoPad` is visibly taller than `RevPad` because it carries material on both sides, and `TaperPad` has sloped side faces rather than vertical ones. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-05: feature_pocket Length and ThroughAll

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pocket`), `verification-design.md` §5

**Given** a Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` — verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %  
**And** two fully constrained 10 x 10 mm square sketches sit on the plate's top face, named `SlotProfile` and `ThroughProfile` — verify: `mcp verify_sketch` returns `subject.dof=0` for both  

**When** a 2 mm deep pocket is cut  
```
mcp feature_pocket { doc: <handle>, body: "PlateBody", profile: "SlotProfile",
                     name: "SlotPocket", length: { value: 2, unit: "mm" } }
```
**And** a second pocket is cut right through the plate  
```
mcp feature_pocket { doc: <handle>, body: "PlateBody", profile: "ThroughProfile",
                     name: "ThroughPocket", up_to: "ThroughAll" }
```

**Then** The length-driven pocket commits — verify: step 1 returns `status=OK` with `mutation.rolled_back=false`  
**And** The volume falls by the analytic amount — verify: `mcp query_mass_properties { doc: <handle>, object: "SlotPocket" }` returns `volume=11800.0` (12000 - 10 x 10 x 2) within 0.1 %  
**And** The ThroughAll pocket commits — verify: step 2 returns `status=OK` with `mutation.rolled_back=false`  
**And** ThroughAll cuts the full thickness — verify: `mcp query_mass_properties { doc: <handle>, object: "ThroughPocket" }` returns `volume=11300.0` (11800 - 10 x 10 x 5) within 0.1 %  
**And** The through cut made a hole, not a dent — verify: the mutation envelope's `feature_state.shape_summary` reports a `face_count` higher than the plate's 6 and `solid_count=1`  
**And** Both solids are valid — verify: `mcp verify_shape { doc: <handle>, object: "ThroughPocket" }` returns `status=OK`  
**And** `ThroughAll` is checked against the live Pocket enum — verify: `mcp query_object { doc: <handle>, object: "ThroughPocket" }` reports `Type=ThroughAll`; the same value on a `feature_pad` is refused, because Pad carries a different member at that position  
**And** A ThroughAll pocket needs no length — verify: step 2 supplied no `length` and was not refused; only a length-driven type requires one  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows a 60 x 40 x 5 mm plate carrying one shallow square recess and one square hole cut clean through — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-05-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm the `SlotPocket` recess still has a visible floor while the `ThroughPocket` opening shows the background or the far side through it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-06: feature_revolve about the sketch V_Axis

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_revolve`), `verification-design.md` §5

**Given** a Body holds a fully constrained rectangle sketch named `ShaftProfile` on XZ, running x = 0..5 mm and z = 0..20 mm — verify: `mcp verify_sketch { doc: <handle>, sketch: "ShaftProfile" }` returns `subject.dof=0`  

**When** the profile is revolved a full turn about the sketch's own vertical axis  
```
mcp feature_revolve { doc: <handle>, body: "ShaftBody", profile: "ShaftProfile",
                      name: "ShaftRev",
                      axis: { kind: "mapped_name", object: "ShaftProfile",
                              mapped_name: "V_Axis" },
                      angle: { value: 360, unit: "deg" } }
```
**And** the cylinder is measured  
```
mcp query_mass_properties { doc: <handle>, object: "ShaftRev" }
```

**Then** The revolution commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** The volume matches the golden cylinder — verify: `mcp query_mass_properties { doc: <handle>, object: "ShaftRev" }` returns `volume=1570.7963` mm³ (r=5, h=20) within 0.1 %, the same value as `benchmarks/g0/golden-models/cylinder-r5-h20.FCStd`  
**And** The solid is a closed cylinder — verify: the mutation envelope's `feature_state.shape_summary` reports `solid_count=1`, `face_count=3` and `is_valid=true`  
**And** `ReferenceAxis` was written — verify: `mcp query_object { doc: <handle>, object: "ShaftRev" }` names `ShaftProfile` and `V_Axis` as the reference axis  
**And** The solid verifies — verify: `mcp verify_shape { doc: <handle>, object: "ShaftRev" }` returns `status=OK`  
**And** A non-axis subelement on the profile is rejected — verify: `mapped_name: "Edge1"` on the profile sketch returns `status=INVALID_INPUT` naming `axis on the profile sketch must be one of ['H_Axis', 'N_Axis', 'V_Axis']`  
**And** An angle above 360 degrees is rejected — verify: `angle: { value: 400, unit: "deg" }` returns `status=INVALID_INPUT` with no `mutation.snapshot_path`  
**And** `second_angle` without the two-angle type is rejected — verify: supplying `second_angle` while `up_to` is omitted returns `status=INVALID_INPUT` naming `second_angle is only read when up_to='TwoAngles'`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows one closed cylinder about 10 mm across and 20 mm tall — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-06-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm a full round solid of revolution, not a partial wedge and not an open surface, with its height visibly about twice its diameter. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-07: feature_hole subtracts the correct volume

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_hole`), `verification-design.md` §5

**Given** a Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` — verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %  
**And** a fully constrained sketch named `HoleProfile` holds one point on the plate's top face at the M5 hole position — verify: `mcp verify_sketch { doc: <handle>, sketch: "HoleProfile" }` returns `subject.dof=0`  

**When** an M5 clearance hole is drilled, 5.5 mm diameter, 3 mm deep  
```
mcp feature_hole { doc: <handle>, body: "PlateBody", profile: "HoleProfile",
                   name: "ClearanceHole",
                   diameter: { value: 5.5, unit: "mm" },
                   depth: { value: 3, unit: "mm" } }
```
**And** the result is measured  
```
mcp query_mass_properties { doc: <handle>, object: "ClearanceHole" }
```

**Then** The hole commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** The volume falls by the bore — verify: `mcp query_mass_properties { doc: <handle>, object: "ClearanceHole" }` returns `volume=11928.7` mm³ (12000 - pi x 2.75² x 3) within 0.1 %  
**And** `depth_type` defaults to Dimension — verify: `mcp query_object { doc: <handle>, object: "ClearanceHole" }` reports `DepthType=Dimension`, because `depth_type` was omitted  
**And** The hole is a blind bore, not a through cut — verify: the mutation envelope's `feature_state.shape_summary` reports `solid_count=1` and a `face_count` higher than the plate's 6  
**And** The solid verifies — verify: `mcp verify_shape { doc: <handle>, object: "ClearanceHole" }` returns `status=OK`  
**And** A Dimension hole without a depth is rejected — verify: omitting `depth` returns `status=INVALID_INPUT` naming `depth_type='Dimension' is depth-driven; 'depth' is required`  
**And** ThroughAll cuts the full thickness — verify: `depth_type: "ThroughAll"` with no `depth` returns `status=OK` and a volume of `11881.2` mm³ (12000 - pi x 2.75² x 5) within 0.1 %  
**And** A zero diameter is rejected — verify: `diameter: { value: 0, unit: "mm" }` returns `status=INVALID_INPUT` naming `diameter must be positive`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows a 60 x 40 x 5 mm plate with one round bore in its top face — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-07-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm the bore is circular, sits at the M5 hole position, and is a blind pocket with a visible floor rather than an opening through the plate. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-08: feature_hole thread_type before cut_type

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_hole` ordering)

**Given** a Body holds a 60 x 40 x 5 mm plate pad and a point sketch for the hole — verify: `mcp verify_sketch { doc: <handle>, sketch: "ThreadProfile" }` returns `subject.dof=0`  
**And** the build's `ThreadType` and `HoleCutType` enumerations are known — verify: `mcp query_object { doc: <handle>, object: <an existing Hole> }` lists their legal members, or create one plain hole first and read them  

**When** a threaded hole with a counterbore is drilled, naming both enumerations in one call. `thread_type` is applied first because FreeCAD re-populates the legal `cut_type` set from it  
```
mcp feature_hole { doc: <handle>, body: "PlateBody", profile: "ThreadProfile",
                   name: "ThreadedHole",
                   thread_type: "ISOMetricProfile", cut_type: "Counterbore",
                   depth: { value: 4, unit: "mm" } }
```
**And** both properties are read back  
```
mcp query_object { doc: <handle>, object: "ThreadedHole" }
```

**Then** The threaded hole commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** Both enumerated values survived the write order — verify: `mcp query_object { doc: <handle>, object: "ThreadedHole" }` reports the requested `ThreadType` and the requested `HoleCutType`, so the thread write did not clear the cut type  
**And** A threading type sets `Threaded` — verify: the same read reports `Threaded=true`  
**And** `diameter` with a threading type is rejected — verify: adding `diameter: { value: 5, unit: "mm" }` returns `status=INVALID_INPUT` naming `'diameter' cannot be combined with thread_type=`, because FreeCAD sizes a threaded hole from its ThreadSize table  
**And** A cut type illegal for that thread is rejected — verify: a `cut_type` outside the set the chosen `thread_type` re-populates returns `status=INVALID_INPUT` naming `is not one of`  
**And** An unknown thread type is rejected pre-transaction — verify: `thread_type: "ISOMetricFake"` returns `status=INVALID_INPUT` with no `mutation.snapshot_path`  
**And** The solid verifies — verify: `mcp verify_shape { doc: <handle>, object: "ThreadedHole" }` returns `status=OK`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows a plate with one counterbored hole — a wide shallow step at the top face narrowing to the threaded bore below — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-08-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm two concentric circular diameters at the hole, not a single plain bore. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Conditional skip**: the exact member spellings of `ThreadType` and `HoleCutType` differ between
builds. Read the live enumeration first and substitute the members this build advertises. If the
build advertises no threading member at all, record CP2 to CP5 as skipped with that reason.

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-09: feature_fillet on named edges

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_fillet`), `mcp-tools-design.md` §1.2 (selectors)

**Given** a Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` — verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %  
**And** the four vertical corner edge names are known — verify: `mcp query_object { doc: <handle>, object: "PlatePad" }` lists the edge names  

**When** the four corners are filleted with a 2 mm radius  
```
mcp feature_fillet { doc: <handle>, body: "PlateBody", base: "PlatePad",
                     name: "CornerFillet",
                     edges: [ { kind: "mapped_name", object: "PlatePad", mapped_name: "Edge1" },
                              { kind: "mapped_name", object: "PlatePad", mapped_name: "Edge3" },
                              { kind: "mapped_name", object: "PlatePad", mapped_name: "Edge5" },
                              { kind: "mapped_name", object: "PlatePad", mapped_name: "Edge7" } ],
                     radius: { value: 2, unit: "mm" } }
```

**Then** The fillet commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** The volume falls by the corner material — verify: `mcp query_mass_properties { doc: <handle>, object: "CornerFillet" }` returns `volume=11982.8` mm³ — 12000 minus 4 x (4 - pi) x 5 for the removed corner prisms — within 0.1 %  
**And** Every requested edge was dressed — verify: the mutation envelope's `feature_state.shape_summary` reports `face_count=10`, which is the plate's 6 plus one new face per filleted edge  
**And** The solid is valid and single — verify: the same `shape_summary` reports `solid_count=1` and `is_valid=true`, and `mcp verify_shape { doc: <handle>, object: "CornerFillet" }` returns `status=OK`  
**And** The surface area rises — verify: `mcp query_mass_properties { doc: <handle>, object: "CornerFillet" }` reports an `area` consistent with four 2 mm quarter-cylinder faces replacing four sharp corners  
**And** A base outside the Body is rejected — verify: `base` naming a feature in a different Body returns `status=INVALID_INPUT` naming `is not in Body`  
**And** An edge naming a different object than the base is rejected — verify: an `edges` entry whose `object` is not the base returns `status=INVALID_INPUT` naming `not the dress-up base`  
**And** A repeated edge is rejected — verify: listing `Edge1` twice returns `status=INVALID_INPUT` naming `repeats Edge1`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows a 60 x 40 x 5 mm plate whose four vertical corners are rounded — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-09-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm all four corners carry a visible 2 mm round, with none left sharp. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-10: feature_chamfer sizes, angle and chamfer_type

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_chamfer`)

**Given** a Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` — verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %  
**And** the build's `ChamferType` enumeration is known — verify: read it from a chamfer created with defaults, or from `mcp query_object` on an existing chamfer  

**When** one edge is chamfered with an equal-distance chamfer  
```
mcp feature_chamfer { doc: <handle>, body: "PlateBody", base: "PlatePad",
                      name: "EqualChamfer",
                      edges: [ { kind: "mapped_name", object: "PlatePad",
                                 mapped_name: "Edge1" } ],
                      size: { value: 1.5, unit: "mm" } }
```
**And** a second edge is chamfered with two distances, naming the build's two-distance type  
```
mcp feature_chamfer { doc: <handle>, body: "PlateBody", base: "EqualChamfer",
                      name: "TwoSizeChamfer",
                      edges: [ { kind: "mapped_name", object: "EqualChamfer",
                                 mapped_name: "Edge3" } ],
                      chamfer_type: "Two distances",
                      size: { value: 2, unit: "mm" },
                      second_size: { value: 1, unit: "mm" } }
```
**And** a third edge is chamfered with a distance and an angle  
```
mcp feature_chamfer { doc: <handle>, body: "PlateBody", base: "TwoSizeChamfer",
                      name: "AngleChamfer",
                      edges: [ { kind: "mapped_name", object: "TwoSizeChamfer",
                                 mapped_name: "Edge5" } ],
                      chamfer_type: "Distance and angle",
                      size: { value: 2, unit: "mm" },
                      angle: { value: 30, unit: "deg" } }
```

**Then** All three chamfers commit — verify: each envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** The equal chamfer removes the analytic wedge — verify: `mcp query_mass_properties { doc: <handle>, object: "EqualChamfer" }` returns `volume=11994.4` mm³ (12000 - 0.5 x 1.5² x 5) within 0.1 %  
**And** Each chamfer adds exactly one face — verify: each mutation envelope's `feature_state.shape_summary` reports `face_count` one higher than its base feature's  
**And** `chamfer_type` is checked against the live enum — verify: `chamfer_type: "Bevel"` returns `status=INVALID_INPUT` naming `chamfer_type 'Bevel' is not one of` followed by the build's members  
**And** The angle bound is enforced — verify: `angle: { value: 200, unit: "deg" }` returns `status=INVALID_INPUT` naming `angle must be in` its bound  
**And** A zero size is rejected — verify: `size: { value: 0, unit: "mm" }` returns `status=INVALID_INPUT` naming `size must be positive`  
**And** Every solid is valid — verify: `mcp verify_shape { doc: <handle>, object: "AngleChamfer" }` returns `status=OK` with `solid_count=1`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows a 60 x 40 x 5 mm plate with three chamfered edges — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-10-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm three flat bevel faces cut back three different edges, not rounds, and that the three bevels differ in width because they were sized differently. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Conditional skip**: the `ChamferType` member spellings differ between builds. Read the live
enumeration and substitute this build's members in steps 2 and 3. If the build advertises only the
equal-distance member, record CP3 partially and note the skipped variants.

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-11: feature_pattern linear and polar

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pattern`, conditional requirements)

**Given** a Body holds a 60 x 40 x 5 mm plate pad and one M5 clearance hole named `ClearanceHole` — verify: `mcp query_mass_properties { doc: <handle>, object: "ClearanceHole" }` returns `volume=11881.2` for a through hole within 0.1 %  
**And** a second Body holds a disc pad and one hole for the polar case — verify: `mcp verify_shape { doc: <handle>, object: "DiscHole" }` returns `status=OK`  

**When** the hole is repeated twice along the plate's X axis on 40 mm spacing. `occurrences` counts the original, so 2 is the original plus one copy  
```
mcp feature_pattern { doc: <handle>, body: "PlateBody", name: "HoleRow", kind: "linear",
                      originals: ["ClearanceHole"],
                      direction: { kind: "mapped_name", object: "PlateProfile",
                                   mapped_name: "H_Axis" },
                      length: { value: 40, unit: "mm" }, occurrences: 2 }
```
**And** a hole is repeated six times around the disc's normal axis  
```
mcp feature_pattern { doc: <handle>, body: "DiscBody", name: "HoleRing", kind: "polar",
                      originals: ["DiscHole"],
                      axis: { kind: "mapped_name", object: "DiscProfile",
                              mapped_name: "N_Axis" },
                      angle: { value: 360, unit: "deg" }, occurrences: 6 }
```

**Then** The linear pattern commits — verify: step 1 returns `status=OK` with `mutation.rolled_back=false`  
**And** `occurrences` counts the original — verify: `mcp query_mass_properties { doc: <handle>, object: "HoleRow" }` returns `volume=11762.4` mm³ — the plate minus exactly two bores of pi x 2.75² x 5 — within 0.1 %, proving 2 holes total, not 3  
**And** The spacing is the requested length — verify: the mutation envelope's `feature_state.shape_summary` bbox is unchanged from the plate's `[60, 40, 5]`, so both holes fall inside the plate at 40 mm apart  
**And** The polar pattern commits — verify: step 2 returns `status=OK` with `mutation.rolled_back=false`  
**And** A full turn steps by angle/occurrences — verify: `mcp query_mass_properties { doc: <handle>, object: "HoleRing" }` shows exactly 6 bores removed, so the copies land 60 degrees apart, not 72  
**And** Both solids are valid — verify: `mcp verify_shape` returns `status=OK` for `HoleRow` and `HoleRing`  
**And** `originals` defaults to the Body Tip — verify: omitting `originals` on an equivalent call returns `status=OK` and patterns the Tip feature  
**And** A kind outside the enum is a schema reject — verify: `kind: "mirror"` is refused against the enum `["linear","polar"]`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows a plate carrying exactly two holes 40 mm apart along its long axis, and a disc carrying exactly six holes evenly spaced around its centre — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-11-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and count the holes in each body; three on the plate or five or seven on the disc is a defect. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-12: feature_mirror across datum, base plane and face

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_mirror`), `verification-design.md` §5

**Given** a Body holds a 20 x 30 x 10 mm pad named `HalfPad` sitting entirely on one side of the YZ plane, so its mirror does not overlap it — verify: `mcp query_mass_properties { doc: <handle>, object: "HalfPad" }` returns `volume=6000.0` and a bounding box with `x` running 5..25 mm  
**And** a datum plane named `MirrorPlane` exists in the same Body — verify: `mcp query_placement { doc: <handle>, object: "MirrorPlane" }` returns `status=OK`  

**When** the pad is mirrored across the Body origin's YZ base plane  
```
mcp feature_mirror { doc: <handle>, body: "HalfBody", name: "PlaneMirror",
                     mirror_plane: { kind: "mapped_name", object: "YZ_Plane" },
                     originals: ["HalfPad"] }
```
**And** a pad is mirrored across the datum plane  
```
mcp feature_mirror { doc: <handle>, body: "DatumBody", name: "DatumMirror",
                     mirror_plane: { kind: "mapped_name", object: "MirrorPlane" },
                     originals: ["DatumPad"] }
```
**And** a pad is mirrored across a planar face of the solid  
```
mcp feature_mirror { doc: <handle>, body: "FaceBody", name: "FaceMirror",
                     mirror_plane: { kind: "mapped_name", object: "FacePad",
                                     mapped_name: "Face1" },
                     originals: ["FacePad"] }
```

**Then** All three mirrors commit — verify: each envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** The volume doubles for a non-overlapping original — verify: `mcp query_mass_properties { doc: <handle>, object: "PlaneMirror" }` returns `volume=12000.0` mm³ within 0.1 %  
**And** The bounding box spans both halves — verify: the mutation envelope's `feature_state.shape_summary` reports `bbox=[50, 30, 10]`, the original x-extent reflected about x=0  
**And** A whole-object selector needs no `mapped_name` — verify: step 1 and step 2 omit `mapped_name` and are accepted, because a datum or base plane is referenced as a whole object  
**And** A face selector carries its `mapped_name` — verify: step 3 is accepted with `mapped_name: "Face1"`  
**And** Every mirrored solid is valid — verify: `mcp verify_shape` returns `status=OK` with `solid_count=1` for each of `PlaneMirror`, `DatumMirror`, `FaceMirror`  
**And** An unknown mirror plane is rejected pre-transaction — verify: `object: "NoSuchPlane"` returns `status=INVALID_INPUT` naming `unknown object in mirror_plane` with no `mutation.snapshot_path`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows each mirrored Body as two matching halves reflected about their plane — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-12-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm `PlaneMirror` shows two separated 20 x 30 x 10 blocks, one on each side of the YZ plane, rather than a single block. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-13: feature_datum plane, axis, point and cs

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_datum`), `verification-design.md` §3 (attachment references, AD-7)

**Given** a Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` — verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %  
**And** the plate's top face name is known — verify: `mcp query_object { doc: <handle>, object: "PlatePad" }` lists the face names  

**When** a datum plane is created on the top face, offset 10 mm along its local Z. `map_mode` defaults to `"FlatFace"`  
```
mcp feature_datum { doc: <handle>, body: "PlateBody", name: "RaisedPlane", kind: "plane",
                    attachment: { kind: "mapped_name", object: "PlatePad",
                                  mapped_name: "Face6" },
                    offset: { value: 10, unit: "mm" } }
```
**And** the other three kinds are created against their own attachments  
```
mcp feature_datum { doc: <handle>, body: "PlateBody", name: "EdgeAxis", kind: "axis",
                    attachment: { kind: "mapped_name", object: "PlatePad",
                                  mapped_name: "Edge1" },
                    map_mode: "ObjectXY" }
mcp feature_datum { doc: <handle>, body: "PlateBody", name: "CornerPoint", kind: "point",
                    attachment: { kind: "mapped_name", object: "PlatePad",
                                  mapped_name: "Vertex1" },
                    map_mode: "ObjectOrigin" }
mcp feature_datum { doc: <handle>, body: "PlateBody", name: "FaceCS", kind: "cs",
                    attachment: { kind: "mapped_name", object: "PlatePad",
                                  mapped_name: "Face6" } }
```

**Then** All four kinds commit — verify: each envelope returns `status=OK` with `mutation.rolled_back=false`, covering the enum `["plane","axis","point","cs"]`  
**And** The offset moved the plane — verify: `mcp query_placement { doc: <handle>, object: "RaisedPlane" }` reports `position.z` equal to `{value: 15, unit: "mm"}` — the 5 mm face plus the 10 mm offset  
**And** `map_mode` defaults to FlatFace — verify: `mcp query_object { doc: <handle>, object: "RaisedPlane" }` reports `MapMode=FlatFace`, because `map_mode` was omitted  
**And** `AttachmentSupport` names the target — verify: the same read names `PlatePad` and `Face6` as the attachment support  
**And** A datum is not a solid — verify: `mcp query_mass_properties { doc: <handle>, object: "RaisedPlane" }` returns no solid volume; a datum carries no material  
**And** The tree carries all four — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists `RaisedPlane`, `EdgeAxis`, `CornerPoint` and `FaceCS` under `PlateBody`  
**And** A fifth kind is a schema reject — verify: `kind: "curve"` is refused against the enum `["plane","axis","point","cs"]`  
**And** A map_mode the kind cannot use is rejected pre-transaction — verify: a mode the datum kind's attach engine does not implement returns `status=INVALID_INPUT` naming `is not implemented for kind` with no `mutation.snapshot_path`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the 60 x 40 x 5 mm plate with a datum plane floating 10 mm above its top face, plus the datum axis, point and coordinate system — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-13-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm the datums are drawn as reference geometry above and on the plate and that the plate's own solid is unchanged — a datum adds no material. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-14: feature_set_parameters edits a Pad length

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_set_parameters`), `verification-design.md` §1 (mutation protocol)

**Given** a Body holds a 20 x 30 mm profile padded 10 mm, named `BlockPad` — verify: `mcp query_mass_properties { doc: <handle>, object: "BlockPad" }` returns `volume=6000.0` within 0.1 %  
**And** the 10 mm starting state is captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK` (if it does not, fit through the GUI with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-14-before.png"}' | & cua-driver call get_window_state`  

**When** the pad length is changed from 10 mm to 25 mm in one transaction  
```
mcp feature_set_parameters { doc: <handle>, feature: "BlockPad",
                             parameters: { Length: { value: 25, unit: "mm" } } }
```
**And** the solid is re-measured  
```
mcp query_mass_properties { doc: <handle>, object: "BlockPad" }
```

**Then** The edit commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`  
**And** The volume tracks the new length — verify: `mcp query_mass_properties { doc: <handle>, object: "BlockPad" }` returns `volume=15000.0` mm³ (20 x 30 x 25) within 0.1 %  
**And** The property holds the new value — verify: `mcp query_object { doc: <handle>, object: "BlockPad" }` reports `Length` as `25 mm`  
**And** The re-verify ran inside the same transaction — verify: the envelope carries `mutation.post_verify.passed=true` with `is_valid=true` and `recompute_clean=true`  
**And** The solid is valid — verify: `mcp verify_shape { doc: <handle>, object: "BlockPad" }` returns `status=OK` with a `bbox` of `[20, 30, 25]`  
**And** Several properties change together — verify: `parameters: { Length: { value: 12, unit: "mm" }, Reversed: true }` returns `status=OK` and both properties read back changed  
**And** A boolean and an enum are accepted — verify: `parameters: { Midplane: true }` and `parameters: { Type: "Length" }` each return `status=OK`  
**And** An empty parameters object is rejected — verify: `parameters: {}` returns `status=INVALID_INPUT` naming `feature_set_parameters requires a non-empty 'parameters' object`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the same 20 x 30 footprint grown visibly taller — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-14-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and confirm the solid's height relative to its 20 x 30 footprint is greater in the after image, the footprint itself is unchanged, and no second solid appeared. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-15: feature_pad up_to and up_to_face enums

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pad`, live enum validation)

**Given** a Body holds a base solid and a fully constrained profile sketch below it, so an up-to extrude has a target — verify: `mcp verify_shape { doc: <handle>, object: "BasePad" }` returns `status=OK` and `mcp verify_sketch { doc: <handle>, sketch: "RiserProfile" }` returns `subject.dof=0`  
**And** the target face name on the base solid is known — verify: `mcp query_object { doc: <handle>, object: "BasePad" }` lists the face names  

**When** the profile is padded up to a named face  
```
mcp feature_pad { doc: <handle>, body: "PlateBody", profile: "RiserProfile",
                  name: "RiserPad", up_to: "UpToFace",
                  up_to_face: { kind: "mapped_name", object: "BasePad",
                                mapped_name: "Face5" } }
```
**And** a value outside the live enumeration is tried  
```
mcp feature_pad { doc: <handle>, body: "PlateBody", profile: "RiserProfile",
                  name: "BadTypePad", up_to: "UpToInfinity" }
```

**Then** The up-to pad commits — verify: step 1 returns `status=OK` with `mutation.rolled_back=false`  
**And** The extrude stopped at the face — verify: the mutation envelope's `feature_state.shape_summary` reports a `bbox` whose z-extent ends at the target face's z, not at an arbitrary length  
**And** `UpToFace` needs no length — verify: step 1 supplied no `length` and was not refused; only a length-driven type requires one  
**And** `UpToFace` was written — verify: `mcp query_object { doc: <handle>, object: "RiserPad" }` reports `Type=UpToFace` and names `BasePad` with `Face5` as the up-to face  
**And** A bad enum value is rejected — verify: step 2 returns `status=INVALID_INPUT` naming `up_to 'UpToInfinity' is not one of` followed by this build's members  
**And** The rejection is pre-transaction — verify: the step 2 envelope carries no `mutation.snapshot_path`, and `mcp query_tree_summary { doc: <handle>, depth: 3 }` names no `BadTypePad`  
**And** The solid verifies — verify: `mcp verify_shape { doc: <handle>, object: "RiserPad" }` returns `status=OK`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the riser solid reaching the base solid's target face and stopping there — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-15-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm the riser meets the base face flush, with no gap below it and no material passing through it, and that no second `BadTypePad` solid exists. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Conditional skip**: the `Type` member spellings differ between builds and one position carries a
deprecation tombstone on the newer one. Read the live enumeration before step 1 and substitute this
build's up-to-face member. Step 2 needs only a value the live enumeration does not contain.

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-16: Fillet radius too large rolls back

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (mutation protocol, AD-5), `mcp-tools-design.md` §3.7

**Given** a Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` — verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %  
**And** the temp directory holds no snapshot from a prior run — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing  
**And** the untouched plate is captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK` (if it does not, fit through the GUI with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-16-before.png"}' | & cua-driver call get_window_state`  

**When** a fillet radius larger than the plate can carry is asked for — 20 mm on a 5 mm thick plate  
```
mcp feature_fillet { doc: <handle>, body: "PlateBody", base: "PlatePad",
                     name: "TooBigFillet",
                     edges: [ { kind: "mapped_name", object: "PlatePad",
                                mapped_name: "Edge1" } ],
                     radius: { value: 20, unit: "mm" } }
```

**Then** The call does not commit — verify: the envelope returns a non-`OK` status: `RECOMPUTE_ERROR` when OCCT reports the failure through the recompute, or `SPEC_FAILED` when the shape grade rejects it  
**And** The rollback is proven — verify: the envelope carries `mutation.rolled_back=true`  
**And** The failure is explained — verify: `mutation.post_verify.explanation` is non-empty and names the feature and the engine's own status string  
**And** No partial solid survives — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` names no `TooBigFillet`  
**And** The plate is unchanged — verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` again returns `volume=12000.0` within 0.1 %  
**And** The fingerprint proves it — verify: `mutation.fingerprint_before.digest` equals `mutation.fingerprint_after.digest`, or the rollback state is `rolled_back_via_snapshot`  
**And** The snapshot was deleted — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing, because a proven rollback removes its snapshot  
**And** The document still recomputes clean — verify: `mcp verify_recompute { doc: <handle> }` returns `status=OK`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the plate exactly as the `Given` left it — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-16-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and confirm the plate still has four sharp corners, no rounded edge, and no half-built fillet face; the rolled-back feature must leave no visible trace. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-17: Fillet on a silently-droppable edge is rejected up front

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_fillet` edge check)

**Given** a Body holds a solid with at least one edge whose faces meet tangentially — a cylinder's seam edge or the join between a fillet and its flat face — verify: `mcp query_object { doc: <handle>, object: "ShaftRev" }` lists the edge names, and the seam edge is identified  
**And** the temp directory holds no snapshot from a prior run — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing  
**And** the untouched solid is captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK` (if it does not, fit through the GUI with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-17-before.png"}' | & cua-driver call get_window_state`  

**When** a fillet is asked for on the tangential edge  
```
mcp feature_fillet { doc: <handle>, body: "ShaftBody", base: "ShaftRev",
                     name: "DropFillet",
                     edges: [ { kind: "mapped_name", object: "ShaftRev",
                                mapped_name: "Edge2" } ],
                     radius: { value: 1, unit: "mm" } }
```
**And** one good edge and one droppable edge are mixed in the same call  
```
mcp feature_fillet { doc: <handle>, body: "ShaftBody", base: "ShaftRev",
                     name: "MixedFillet",
                     edges: [ { kind: "mapped_name", object: "ShaftRev",
                                mapped_name: "Edge1" },
                              { kind: "mapped_name", object: "ShaftRev",
                                mapped_name: "Edge2" } ],
                     radius: { value: 1, unit: "mm" } }
```

**Then** The droppable edge is refused — verify: step 1 returns `status=INVALID_INPUT` naming `cannot be shown to survive the dress-up` and listing the edge  
**And** The reason is stated — verify: the same detail names `each needs exactly two adjacent faces meeting at a measurable crease, and FreeCAD drops the rest without reporting it`  
**And** The refusal is pre-transaction — verify: the step 1 envelope carries no `mutation.snapshot_path`, and `ls "$TEMP"/FCB_TMP_snap_*` lists nothing  
**And** A mixed request is refused whole — verify: step 2 returns `status=INVALID_INPUT`; the good edge is not filleted on its own  
**And** Nothing was created — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` names neither `DropFillet` nor `MixedFillet`  
**And** The base solid is untouched — verify: `mcp query_mass_properties { doc: <handle>, object: "ShaftRev" }` returns the same volume as before both steps  
**And** A committed dress-up that dressed fewer edges than asked is caught inside the transaction — verify: any such case returns `status=SPEC_FAILED` with `mutation.rolled_back=true` and an explanation naming `dressed N of the M requested edge(s)`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the cylinder exactly as the `Given` left it — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-17-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and confirm no edge of the solid carries a round, including the good `Edge1` from the mixed call; a partially dressed solid is the exact defect this scenario catches. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-18: feature_pattern occurrences and conditional requirements

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pattern`, `allOf`/`if`/`then`)

**Given** a Body holds a plate pad and one hole feature to pattern — verify: `mcp verify_shape { doc: <handle>, object: "ClearanceHole" }` returns `status=OK`  
**And** the document object list before the calls is recorded — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }`  
**And** the starting state of the plate is captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK` (if it does not, fit through the GUI with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-18-before.png"}' | & cua-driver call get_window_state`  

**When** one occurrence is asked for  
```
mcp feature_pattern { doc: <handle>, body: "PlateBody", name: "OnePattern", kind: "linear",
                      direction: { kind: "mapped_name", object: "PlateProfile",
                                   mapped_name: "H_Axis" },
                      length: { value: 40, unit: "mm" }, occurrences: 1 }
```
**And** zero occurrences are asked for, then a linear pattern with no `direction`  
```
mcp feature_pattern { doc: <handle>, body: "PlateBody", name: "ZeroPattern", kind: "linear",
                      direction: { kind: "mapped_name", object: "PlateProfile",
                                   mapped_name: "H_Axis" },
                      length: { value: 40, unit: "mm" }, occurrences: 0 }
mcp feature_pattern { doc: <handle>, body: "PlateBody", name: "NoDirection", kind: "linear",
                      length: { value: 40, unit: "mm" }, occurrences: 3 }
```
**And** a polar pattern with no `axis` is asked for  
```
mcp feature_pattern { doc: <handle>, body: "PlateBody", name: "NoAxis", kind: "polar",
                      angle: { value: 360, unit: "deg" }, occurrences: 4 }
```

**Then** `occurrences: 1` is a schema reject — verify: step 1 is refused; the schema sets `minimum: 2`  
**And** `occurrences: 0` is a schema reject — verify: the first call of step 2 is refused against the same `minimum: 2`  
**And** A linear pattern without `direction` is refused — verify: the second call of step 2 is refused by the `if kind == "linear" then required: ["direction"]` branch  
**And** A polar pattern without `axis` is refused — verify: step 3 is refused by the `if kind == "polar" then required: ["axis"]` branch  
**And** The complementary field is not required — verify: a valid linear call carrying `direction` and no `axis` returns `status=OK`, so the conditional does not demand both  
**And** A very large count is refused rather than handed to OCCT — verify: `occurrences: 5000` returns `status=INVALID_INPUT` naming `occurrences must be an integer between 2 and 1000`  
**And** Nothing was created — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists the same objects as the precondition, naming no `OnePattern`, `ZeroPattern`, `NoDirection` or `NoAxis`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the plate still carrying its single original hole — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-18-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and confirm the hole count is unchanged between them; any extra bore means one of the refused patterns partly ran. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-19: Zero and negative pad length

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pad`), `mcp-tools-design.md` §1.4 (quantity fields)

**Given** a Body holds a fully constrained 20 x 30 mm profile sketch — verify: `mcp verify_sketch { doc: <handle>, sketch: "BlockProfile" }` returns `subject.dof=0`  
**And** the temp directory holds no snapshot from a prior run — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing  
**And** the solid-free starting state is captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK` (if it does not, fit through the GUI with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-19-before.png"}' | & cua-driver call get_window_state`  

**When** a pad with zero length is asked for  
```
mcp feature_pad { doc: <handle>, body: "BlockBody", profile: "BlockProfile",
                  name: "ZeroPad", length: { value: 0, unit: "mm" } }
```
**And** a pad with a negative length is asked for  
```
mcp feature_pad { doc: <handle>, body: "BlockBody", profile: "BlockProfile",
                  name: "NegPad", length: { value: -10, unit: "mm" } }
```
**And** a pad with a length-driven type and no length at all is asked for  
```
mcp feature_pad { doc: <handle>, body: "BlockBody", profile: "BlockProfile",
                  name: "NoLenPad" }
```

**Then** Zero is refused — verify: step 1 returns `status=INVALID_INPUT` naming `length must be positive, got 0`  
**And** Negative is refused — verify: step 2 returns `status=INVALID_INPUT` naming `length must be positive, got -10`  
**And** A missing length on a length-driven type is refused — verify: step 3 returns `status=INVALID_INPUT` naming `up_to='Length' is length-driven; 'length' is required`  
**And** Every refusal is pre-transaction — verify: none of the three envelopes carries `mutation.snapshot_path`  
**And** No snapshot was written — verify: `ls "$TEMP"/FCB_TMP_snap_*` still lists nothing after all three steps  
**And** Nothing was created — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` names no `ZeroPad`, `NegPad` or `NoLenPad`  
**And** A non-finite length is refused — verify: a length encoding as infinity returns `status=INVALID_INPUT` naming `must be finite`  
**And** The Body still carries no solid — verify: `mcp query_object { doc: <handle>, object: "BlockBody" }` reports no Tip, because no pad was ever created  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows only the flat rectangle sketch and no padded solid — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-19-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and confirm the view is unchanged and carries no extruded material, not even a zero-height sliver. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-20: Omitted radius and size take FreeCAD's 1 mm default

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_fillet`, `feature_chamfer` defaults)

**Given** a Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` — verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %  
**And** two corner edge names are known — verify: `mcp query_object { doc: <handle>, object: "PlatePad" }` lists the edge names  

**When** one edge is filleted with no radius at all  
```
mcp feature_fillet { doc: <handle>, body: "PlateBody", base: "PlatePad",
                     name: "DefaultFillet",
                     edges: [ { kind: "mapped_name", object: "PlatePad",
                                mapped_name: "Edge1" } ] }
```
**And** another edge is chamfered with no size at all  
```
mcp feature_chamfer { doc: <handle>, body: "PlateBody", base: "DefaultFillet",
                      name: "DefaultChamfer",
                      edges: [ { kind: "mapped_name", object: "DefaultFillet",
                                 mapped_name: "Edge3" } ] }
```

**Then** The fillet commits without a radius — verify: step 1 returns `status=OK` with `mutation.rolled_back=false`  
**And** The radius is FreeCAD's own 1 mm — verify: `mcp query_object { doc: <handle>, object: "DefaultFillet" }` reports `Radius` as `1 mm`  
**And** The volume matches a 1 mm fillet — verify: `mcp query_mass_properties { doc: <handle>, object: "DefaultFillet" }` returns `volume=11998.9` mm³ — 12000 minus (1 - pi/4) x 1² x 5 — within 0.1 %  
**And** The chamfer commits without a size — verify: step 2 returns `status=OK` with `mutation.rolled_back=false`  
**And** The chamfer size is FreeCAD's own 1 mm — verify: `mcp query_object { doc: <handle>, object: "DefaultChamfer" }` reports `Size` as `1 mm`  
**And** Both solids are valid — verify: `mcp verify_shape { doc: <handle>, object: "DefaultChamfer" }` returns `status=OK` with `solid_count=1`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the plate with one small rounded corner and one small flat bevel, both about 1 mm — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-20-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and confirm both dress-ups are visible but small against the 60 x 40 plate, and that the round and the bevel sit on different edges. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Conditional skip**: the 1 mm default is FreeCAD's property default, not a value this package sets.
If this build ships a different default, record the observed value and treat CP2 and CP5 as a build
divergence rather than a defect.

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-21: feature_set_parameters on a read-only or unknown property

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_set_parameters` pre-transaction validation)

**Given** a Body holds a 20 x 30 x 10 mm pad named `BlockPad` — verify: `mcp query_mass_properties { doc: <handle>, object: "BlockPad" }` returns `volume=6000.0` within 0.1 %  
**And** the temp directory holds no snapshot from a prior run — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing  
**And** the 10 mm pad is captured before the four refusals — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK` (if it does not, fit through the GUI with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-21-before.png"}' | & cua-driver call get_window_state`  

**When** a property the feature does not carry is named  
```
mcp feature_set_parameters { doc: <handle>, feature: "BlockPad",
                             parameters: { Thickness: { value: 3, unit: "mm" } } }
```
**And** a property FreeCAD marks read-only is named — a revolution's computed `Base` or a pad's `Shape`  
```
mcp feature_set_parameters { doc: <handle>, feature: "BlockPad",
                             parameters: { Shape: 1 } }
```
**And** the wrong unit for a length property is sent  
```
mcp feature_set_parameters { doc: <handle>, feature: "BlockPad",
                             parameters: { Length: { value: 25, unit: "deg" } } }
```
**And** a value of an unsupported type is sent  
```
mcp feature_set_parameters { doc: <handle>, feature: "BlockPad",
                             parameters: { Length: [25] } }
```

**Then** An unknown property is refused — verify: step 1 returns `status=INVALID_INPUT` naming `BlockPad has no property named 'Thickness'`  
**And** A read-only property is refused — verify: step 2 returns `status=INVALID_INPUT` naming `BlockPad.Shape is read-only`  
**And** A wrong unit is refused — verify: step 3 returns `status=INVALID_INPUT` naming `Length value unit must be one of ['mm'], got 'deg'`  
**And** An unsupported value type is refused — verify: step 4 returns `status=INVALID_INPUT` naming `Length value must be a quantity, number, boolean or enum string`  
**And** Every refusal is pre-transaction — verify: none of the four envelopes carries `mutation.snapshot_path`  
**And** No snapshot was written — verify: `ls "$TEMP"/FCB_TMP_snap_*` still lists nothing after all four steps  
**And** The feature is unchanged — verify: `mcp query_mass_properties { doc: <handle>, object: "BlockPad" }` again returns `volume=6000.0` within 0.1 %  
**And** A whole batch is refused when one entry is bad — verify: `parameters: { Length: { value: 12, unit: "mm" }, Thickness: 3 }` returns `status=INVALID_INPUT` and `Length` reads back unchanged at `10 mm`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the pad at its original 10 mm height — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-21-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and confirm the solid's proportions are identical; a taller or differently shaped pad means one refused write partly landed. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-22: Feature on a nonexistent Body, profile or base

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.3 (error surface, AD-17), `mcp-tools-design.md` §3.7

**Given** a document holds exactly one Body named `PlateBody`, one sketch named `PlateProfile` and one pad named `PlatePad` — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists them  
**And** the temp directory holds no snapshot from a prior run — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing  
**And** the single-pad starting state is captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK` (if it does not, fit through the GUI with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-22-before.png"}' | & cua-driver call get_window_state`  

**When** a Body that does not exist is named  
```
mcp feature_pad { doc: <handle>, body: "NoSuchBody", profile: "PlateProfile",
                  name: "OrphanPad", length: { value: 5, unit: "mm" } }
```
**And** a profile that does not exist is named  
```
mcp feature_pad { doc: <handle>, body: "PlateBody", profile: "NoSuchSketch",
                  name: "OrphanPad", length: { value: 5, unit: "mm" } }
```
**And** a dress-up base that does not exist is named  
```
mcp feature_fillet { doc: <handle>, body: "PlateBody", base: "NoSuchPad",
                     name: "OrphanFillet",
                     edges: [ { kind: "mapped_name", object: "NoSuchPad",
                                mapped_name: "Edge1" } ] }
```
**And** an object that exists but is the wrong type is named  
```
mcp feature_pad { doc: <handle>, body: "PlateProfile", profile: "PlateProfile",
                  name: "WrongTypePad", length: { value: 5, unit: "mm" } }
```

**Then** An unknown Body is `INVALID_INPUT` — verify: step 1 returns `status=INVALID_INPUT` naming `unknown object in body: NoSuchBody`  
**And** An unknown profile is `INVALID_INPUT` — verify: step 2 returns `status=INVALID_INPUT` naming `unknown object in profile: NoSuchSketch`  
**And** An unknown dress-up base is `INVALID_INPUT` — verify: step 3 returns `status=INVALID_INPUT` naming `unknown object in base: NoSuchPad`  
**And** A wrong-typed Body is `INVALID_INPUT` — verify: step 4 returns `status=INVALID_INPUT` naming `object is not a PartDesign Body: PlateProfile`  
**And** Nothing was created — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists the same objects as the precondition, naming no `OrphanPad`, `OrphanFillet` or `WrongTypePad`  
**And** No transaction opened — verify: none of the four envelopes carries `mutation.snapshot_path`  
**And** No snapshot was written — verify: `ls "$TEMP"/FCB_TMP_snap_*` still lists nothing after all four steps  
**And** A taken name is also refused — verify: `name: "PlatePad"` on a fresh pad returns `status=INVALID_INPUT` naming `an object named PlatePad already exists`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the one original `PlatePad` solid and nothing else — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-22-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and confirm the two images are the same model: one solid, no orphan pad, no fillet on any edge. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-23: Padding an under-constrained sketch rolls back

**Priority**: Critical
**Design Ref**: `verification-design.md` §4 (AD-8), `verification-design.md` §1.3 (`post_verify` composition)

**Given** a Body holds a sketch that is deliberately under-constrained: a rectangle whose position is not pinned to the origin — verify: `mcp verify_sketch { doc: <handle>, sketch: "LooseProfile" }` returns a non-`OK` status with `subject.dof` greater than 0  
**And** the temp directory holds no snapshot from a prior run — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing  
**And** the solid-free starting state is captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK` (if it does not, fit through the GUI with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-23-before.png"}' | & cua-driver call get_window_state`  

**When** the under-constrained sketch is padded  
```
mcp feature_pad { doc: <handle>, body: "LooseBody", profile: "LooseProfile",
                  name: "LoosePad", length: { value: 10, unit: "mm" } }
```

**Then** The pad does not commit — verify: the envelope returns `status=SPEC_FAILED`, not `OK`  
**And** The rollback is proven — verify: the envelope carries `mutation.rolled_back=true` and `mutation.post_verify.passed=false`  
**And** The cause names the sketch and its dof — verify: `mutation.post_verify.explanation` starts `verify_sketch failed on LooseProfile (dof=` with a non-zero dof  
**And** The shape check passed before the sketch check failed — verify: the same block carries `recompute_clean=true`, `is_valid=true` and `fully_constrained=false`, so the failure is the AD-8 step, not the solid  
**And** No partial solid survives — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` names no `LoosePad`  
**And** The Body carries no Tip — verify: `mcp query_object { doc: <handle>, object: "LooseBody" }` reports no Tip feature  
**And** The fingerprint proves the rollback — verify: `mutation.fingerprint_before.digest` equals `mutation.fingerprint_after.digest`, or the rollback state is `rolled_back_via_snapshot`  
**And** The snapshot was deleted — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows only the loose rectangle sketch and no padded solid — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-23-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and confirm no extruded material appeared; a visible 10 mm block would mean the rollback restored the tree but not the view. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-24: A failed recompute is RECOMPUTE_ERROR, not SPEC_FAILED

**Priority**: Critical
**Design Ref**: `verification-design.md` §1.3 (`post_verify` composition, status mapping), `mcp-tools-design.md` §1.3 (closed status set)

**Given** a Body holds a chain of features where one can be driven into an engine failure — a pocket deeper than the material, or a fillet whose radius consumes its face — verify: `mcp verify_recompute { doc: <handle> }` returns `status=OK` before the call  
**And** the temp directory holds no snapshot from a prior run — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing  
**And** the healthy starting model is captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK` (if it does not, fit through the GUI with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view)), then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-24-before.png"}' | & cua-driver call get_window_state`  

**When** an existing feature is driven into a state the engine cannot build. A pocket length is set far beyond the solid, so the recompute leaves the feature in an error state  
```
mcp feature_set_parameters { doc: <handle>, feature: "SlotPocket",
                             parameters: { Length: { value: 500, unit: "mm" } } }
```
**And** the document's recompute health is read afterwards  
```
mcp verify_recompute { doc: <handle> }
```

**Then** The status is `RECOMPUTE_ERROR` — verify: the envelope returns `status=RECOMPUTE_ERROR`, never `SPEC_FAILED`; only a recompute that left an object invalid maps to that value  
**And** The recompute flag is false — verify: the envelope carries `mutation.post_verify.recompute_clean=false`  
**And** The later checks were not measured — verify: the same block carries `is_valid` and `fully_constrained` as not-measured, because the checklist short-circuits at the first hard failure  
**And** The engine's own message is quoted — verify: `mutation.post_verify.explanation` starts `recompute left` and names the object with its `getStatusString()` text  
**And** The rollback is proven — verify: the envelope carries `mutation.rolled_back=true`  
**And** The old value is restored — verify: `mcp query_object { doc: <handle>, object: "SlotPocket" }` reports the original `Length`, not `500 mm`  
**And** The document recomputes clean again — verify: `mcp verify_recompute { doc: <handle> }` returns `status=OK` with no failing checks  
**And** The snapshot was deleted — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing, because a proven rollback removes its snapshot  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the FreeCAD window shows the model restored to its healthy shape — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-04-24-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and confirm the solid matches the before image, with the original shallow pocket and no 500 mm cut through or past the material, and no error marker drawn on the tree. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```
