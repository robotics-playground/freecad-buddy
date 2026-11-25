# TC-21: Part primitives and Part booleans

Proves Story 13-17 in the live GUI: `feature_part_primitive` makes each of the five kinds
at the requested place, `feature_part_boolean` cuts, fuses and intersects them, an empty result is
refused and rolled back, an untrusted input is refused with its reason, and `document_undo` brings
the inputs back. The envelope is a claim of the code under test. The volumes are read back with
`script_exec` (FreeCAD's own `Shape.Volume`) and compared with hand-computed values. The result is
the FreeCAD window captured with `cua-driver` and read by the agent.

**Host**: GUI through the H2 proxy in `fcb-desktop`. `script_exec` is on (the default).

## Preconditions

- [ ] The installed addon is the image's copy of the code under test (verify: `docker exec -u cua fcb-desktop sha256sum $FCB_USER_DIR/Mod/FreeCADBuddy/freecad_buddy/usecases/features.py` equals the `sha256sum` of `dist/addon/freecad_buddy/usecases/features.py` on the host after `scripts/build_addon.py --release`)
- [ ] No document is open in the GUI (verify: `mcp document_list` returns no document)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `echo '{"pid":<pid>,"window_id":<wid>}' | "$FCB_CUA" get_window_state` returns an element tree)

---

### TC-21-01: Two overlapping boxes are cut, fused and intersected, and the inputs are hidden

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7.5; `tool-contracts.md` T-9

**Given** a new document `tc21_ops` holding two 10 mm cubes, `A` at the origin and `B` shifted 5 mm along x, made by the primitive tool — verify: both calls return `OK`; `structured_content.feature_state.shape_summary.volume` is `1000` for each; `script_exec` `result = [doc.A.TypeId, doc.A.getParentGeoFeatureGroup() is None]` returns `["Part::Box", true]`  
```
mcp feature_part_primitive { doc: <handle>, kind: "box", name: "A", length: {value: 10, unit: "mm"}, width: {value: 10, unit: "mm"}, height: {value: 10, unit: "mm"} }
mcp feature_part_primitive { doc: <handle>, kind: "box", name: "B", length: {value: 10, unit: "mm"}, width: {value: 10, unit: "mm"}, height: {value: 10, unit: "mm"}, placement: { base: { x: {value: 5, unit: "mm"} } } }
```

**When** the three operations run, in this order  
```
mcp feature_part_boolean { doc: <handle>, operation: "cut", base: "A", tools: ["B"], name: "CutAB" }
mcp feature_part_boolean { doc: <handle>, operation: "common", base: "A", tools: ["B"], name: "CommonAB" }
mcp feature_part_boolean { doc: <handle>, operation: "fuse", base: "A", tools: ["B"], name: "FuseAB" }
```

**Then** each call succeeds with the analytic volume — verify: every call returns `OK`; `structured_content.feature_state.shape_summary.volume` is `500`, `500` and `1500`; `script_exec` `result = [round(doc.CutAB.Shape.Volume, 6), round(doc.CommonAB.Shape.Volume, 6), round(doc.FuseAB.Shape.Volume, 6)]` returns `[500.0, 500.0, 1500.0]`  
**And** the objects are the two-input types — verify: `script_exec` `result = [doc.CutAB.TypeId, doc.CommonAB.TypeId, doc.FuseAB.TypeId]` returns `["Part::Cut", "Part::Common", "Part::Fuse"]`  
**And** the inputs are hidden in the GUI as headless — verify: `script_exec` `result = [doc.A.Visibility, doc.B.Visibility]` returns `[false, false]`  
**And** *(visual)* each result has the expected length along x — verify: for each of `CutAB`, `CommonAB`, `FuseAB` in turn, `script_exec` `result = [doc.CutAB.Visibility, doc.CommonAB.Visibility, doc.FuseAB.Visibility]` after setting `Visibility` true on that result only and false on the other two (`doc.<name>.Visibility = ...`); `mcp view_fit_viewport { doc: <handle> }`; `echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-21-01-<name>.png"}' | "$FCB_CUA" get_window_state`; then `Read` the three PNGs and state for each whether one solid is drawn and whether its length along x is 5, 5 and 15 mm, that is the fused solid is three times as long as the cut and the common solid (read the picture, not the numbers); the model tree shows the inputs nested under the result  
**And** undo removes the results one by one and shows the inputs again — verify: `mcp document_undo { doc: <handle> }` three times returns `OK` each time; `script_exec` `result = [doc.getObject("FuseAB"), doc.getObject("CommonAB"), doc.getObject("CutAB"), doc.A.Visibility, doc.B.Visibility]` returns `[null, null, null, true, true]`  

**Cleanup**: `mcp document_close { doc: <handle> }`

---

### TC-21-02: An empty result is refused and the document is unchanged

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7.5; `tool-contracts.md` T-9; AD-5

**Given** a new document `tc21_empty` holding `A`, a 10 mm cube at the origin, and `Far`, a 10 mm cube shifted 100 mm along x, made by the primitive tool, and a screenshot of the window — verify: both calls return `OK`; `echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-21-02-before.png"}' | "$FCB_CUA" get_window_state` writes the PNG  
```
mcp feature_part_primitive { doc: <handle>, kind: "box", name: "A", length: {value: 10, unit: "mm"}, width: {value: 10, unit: "mm"}, height: {value: 10, unit: "mm"} }
mcp feature_part_primitive { doc: <handle>, kind: "box", name: "Far", length: {value: 10, unit: "mm"}, width: {value: 10, unit: "mm"}, height: {value: 10, unit: "mm"}, placement: { base: { x: {value: 100, unit: "mm"} } } }
```

**When** the common of two solids that do not meet is asked for  
```
mcp feature_part_boolean { doc: <handle>, operation: "common", base: "A", tools: ["Far"], name: "Nothing" }
```

**Then** the call is refused — verify: `status` is `RECOMPUTE_ERROR`, `detail.code` is `part_boolean.empty_result`, `structured_content.mutation.rolled_back` is `true` and `rollback_proven` is not `null`  
**And** nothing is left — verify: `mcp query_tree_summary { doc: <handle> }` lists `A` and `Far` and no `Nothing`; `script_exec` `result = [doc.getObject("Nothing"), doc.A.Visibility, doc.Far.Visibility]` returns `[null, true, true]`  
**And** *(visual)* the viewport shows the two cubes apart and is the same as before — verify: `echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-21-02-after.png"}' | "$FCB_CUA" get_window_state`, then `Read` both PNGs and state whether both cubes are still drawn in the same places and the tree holds the same two objects  
**And** the next typed call works and undo reverts only it — verify: `mcp feature_part_primitive { doc: <handle>, kind: "sphere", name: "Ball", radius: {value: 4, unit: "mm"} }` returns `OK`; `mcp document_undo { doc: <handle> }` returns `OK`; `script_exec` `result = [doc.getObject("Ball"), doc.getObject("A") is not None]` returns `[null, true]`  

**Cleanup**: `mcp document_close { doc: <handle> }`

---

### TC-21-03: An untrusted input and a Body feature are refused with a reason

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.7.5; epic decisions 24, 44

**Given** a new document `tc21_trust` holding `A`, a 10 mm cube made by the primitive tool, a solid `Rev` with reversed orientation, and a Body `Body` with a padded sketch, built by one call — verify: `mcp script_exec` returns `OK`; `script_exec` `result = [doc.Rev.Shape.Volume < 0, doc.Pad.getParentGeoFeatureGroup().Name]` returns `[true, "Body"]`  
```
mcp feature_part_primitive { doc: <handle>, kind: "box", name: "A", length: {value: 10, unit: "mm"}, width: {value: 10, unit: "mm"}, height: {value: 10, unit: "mm"} }
mcp script_exec { doc: <handle>, code: "import Part, Sketcher, FreeCAD as App\nV = App.Vector\nrev = doc.addObject('Part::Feature', 'Rev')\nbox = Part.makeBox(10, 10, 10, V(5, 0, 0))\nbox.reverse()\nrev.Shape = box\nbody = doc.addObject('PartDesign::Body', 'Body')\nsk = body.newObject('Sketcher::SketchObject', 'Profile')\nsk.AttachmentSupport = [(body.Origin.OriginFeatures[3], '')]\nsk.MapMode = 'FlatFace'\nfor i, (a, b) in enumerate([((0,0),(8,0)), ((8,0),(8,16)), ((8,16),(0,16)), ((0,16),(0,0))]):\n    sk.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(b[0], b[1], 0)))\nfor i in range(4):\n    sk.addConstraint(Sketcher.Constraint('Coincident', i, 2, (i + 1) % 4, 1))\ndoc.recompute()\npad = body.newObject('PartDesign::Pad', 'Pad')\npad.Profile = sk\npad.Length = 5\ndoc.recompute()\nresult = 'built'" }
```

**When** the cut by the reversed solid and the cut by the Body's pad are asked for  
```
mcp feature_part_boolean { doc: <handle>, operation: "cut", base: "A", tools: ["Rev"], name: "BadCut" }
mcp feature_part_boolean { doc: <handle>, operation: "cut", base: "A", tools: ["Pad"], name: "PadCut" }
```

**Then** the reversed solid is refused with its name and reason — verify: the first call returns `INVALID_INPUT` with `detail.code` `part_boolean.untrusted_shape`; `detail.message` contains `Rev` and `reversed`  
**And** the Body feature is refused — verify: the second call returns `INVALID_INPUT` with `detail.code` `part_boolean.not_top_level`; `detail.message` contains `Pad` and `Body`  
**And** the Body itself is accepted — verify: `mcp feature_part_boolean { doc: <handle>, operation: "cut", base: "Body", tools: ["A"], name: "BodyCut" }` returns `OK`  
**And** nothing was written by the two refusals — verify: `script_exec` `result = [doc.getObject("BadCut"), doc.getObject("PadCut")]` returns `[null, null]`  
**And** *(visual)* the tree shows `BodyCut` and no `BadCut` or `PadCut` — verify: `echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-21-03-after.png"}' | "$FCB_CUA" get_window_state`, then `Read` the PNG and list the object names in the model tree  

**Cleanup**: `mcp document_close { doc: <handle> }`

---

### TC-21-04: Each primitive kind and a several-tool cut

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.7.5; `tool-contracts.md` T-9

**Given** a new document `tc21_kinds` — verify: `mcp document_create` returns `OK`  

**When** a cylinder, a cone, a torus and a plate are made, and the plate is cut by the cylinder and the cone together, without refinement  
```
mcp feature_part_primitive { doc: <handle>, kind: "cylinder", name: "Pin", radius: {value: 2, unit: "mm"}, height: {value: 30, unit: "mm"}, placement: { base: { x: {value: 5, unit: "mm"}, y: {value: 5, unit: "mm"}, z: {value: -5, unit: "mm"} } } }
mcp feature_part_primitive { doc: <handle>, kind: "cone", name: "Horn", radius1: {value: 3, unit: "mm"}, radius2: {value: 0, unit: "mm"}, height: {value: 20, unit: "mm"}, placement: { base: { x: {value: 25, unit: "mm"}, y: {value: 5, unit: "mm"}, z: {value: -5, unit: "mm"} } } }
mcp feature_part_primitive { doc: <handle>, kind: "torus", name: "Ring", radius1: {value: 10, unit: "mm"}, radius2: {value: 2, unit: "mm"}, placement: { base: { x: {value: 60, unit: "mm"} } } }
mcp feature_part_primitive { doc: <handle>, kind: "box", name: "Plate", length: {value: 40, unit: "mm"}, width: {value: 10, unit: "mm"}, height: {value: 10, unit: "mm"} }
mcp feature_part_boolean { doc: <handle>, operation: "cut", base: "Plate", tools: ["Pin", "Horn"], name: "Drilled", refine: false }
```

**Then** every call succeeds — verify: all five return `OK`  
**And** the volumes are analytic — verify: `script_exec` `result = [round(doc.Pin.Shape.Volume, 3), round(doc.Horn.Shape.Volume, 3), round(doc.Ring.Shape.Volume, 3)]` returns `[376.991, 188.496, 789.568]` (pi r^2 h, pi r^2 h / 3, 2 pi^2 R r^2)  
**And** the cut is a cut of the fuse of the tools — verify: `script_exec` `result = [doc.Drilled.TypeId, doc.Drilled_tools.TypeId, doc.Drilled.Refine, doc.Drilled_tools.Refine]` returns `["Part::Cut", "Part::MultiFuse", false, false]`  
**And** a refused size changes nothing — verify: `mcp feature_part_primitive { doc: <handle>, kind: "torus", name: "Bad", radius1: {value: 2, unit: "mm"}, radius2: {value: 2, unit: "mm"} }` returns `INVALID_INPUT` with `detail.code` `part_primitive.dimension`; `script_exec` `result = doc.getObject("Bad")` returns `null`  
**And** *(visual)* the viewport shows a plate with a round hole and a conical hole, and a ring — verify: `mcp view_fit_viewport { doc: <handle> }`, then `echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-21-04-after.png"}' | "$FCB_CUA" get_window_state`, then `Read` the PNG and state which shapes are drawn and whether the plate shows two holes (the pin hole is round and straight, the cone hole narrows)  

**Cleanup**: `mcp document_close { doc: <handle> }`
