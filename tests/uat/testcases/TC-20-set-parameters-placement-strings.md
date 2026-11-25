# TC-20: feature_set_parameters writes placements and strings

Proves Story 13-16 in the live GUI: a Body moves by a `Placement` write that names one component, a
feature is renamed by a `Label` write, an attached sketch refuses a `Placement` write, and
`document_undo` restores both. The envelope is a claim of the code under test. The result is the
FreeCAD window captured with `cua-driver` and read by the agent, and the placements read back with
`script_exec` (FreeCAD's own `Placement`).

**Host**: GUI through the H2 proxy. `script_exec` is on (the default).

## Preconditions

- [ ] The installed addon is the image's copy of the code under test (verify: `docker exec -u cua fcb-desktop sha256sum $FCB_USER_DIR/Mod/FreeCADBuddy/freecad_buddy/usecases/features.py` equals the `sha256sum` of `dist/addon/freecad_buddy/usecases/features.py` on the host after `scripts/build_addon.py --release`)
- [ ] No document is open in the GUI (verify: `mcp document_list` returns no document)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `echo '{"pid":<pid>,"window_id":<wid>}' | "$FCB_CUA" get_window_state` returns an element tree)

---

### TC-20-01: A Body moves by a one-component placement write and undo restores it

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §2 `feature_set_parameters`; `tool-contracts.md` T-4

**Given** a new document `tc20_place` (`mcp document_create { label: "tc20_place" }`) holding a Body `Body` with a fully constrained sketch `Profile` (8 x 16 mm rectangle, attached to `XY_Plane` with `MapMode` `FlatFace`) and a 5 mm pad `Block`, built by one call — verify: `mcp script_exec` returns `OK` with `value_repr` `('built', True)` (the sketch is fully constrained: every mutation that touches the pad or the sketch verifies the sketch, and an under-constrained one fails the call as `SPEC_FAILED`) and `mcp query_tree_summary { doc: <handle> }` lists `Body`, `Profile`, `Block` with no `!` marker  
```
mcp script_exec { doc: <handle>, code: "import Part, Sketcher, FreeCAD as App\nV = App.Vector\nbody = doc.addObject('PartDesign::Body', 'Body')\nsk = body.newObject('Sketcher::SketchObject', 'Profile')\nsk.AttachmentSupport = [(body.Origin.OriginFeatures[3], '')]\nsk.MapMode = 'FlatFace'\nfor i, (a, b) in enumerate([((0,0),(8,0)), ((8,0),(8,16)), ((8,16),(0,16)), ((0,16),(0,0))]):\n    sk.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(b[0], b[1], 0)))\nfor i in range(4):\n    sk.addConstraint(Sketcher.Constraint('Coincident', i, 2, (i + 1) % 4, 1))\nfor i in (0, 2):\n    sk.addConstraint(Sketcher.Constraint('Horizontal', i))\nfor i in (1, 3):\n    sk.addConstraint(Sketcher.Constraint('Vertical', i))\nsk.addConstraint(Sketcher.Constraint('DistanceX', -1, 1, 0, 1, 0))\nsk.addConstraint(Sketcher.Constraint('DistanceY', -1, 1, 0, 1, 0))\nsk.addConstraint(Sketcher.Constraint('DistanceX', 0, 1, 0, 2, 8))\nsk.addConstraint(Sketcher.Constraint('DistanceY', 1, 1, 1, 2, 16))\ndoc.recompute()\npad = body.newObject('PartDesign::Pad', 'Block')\npad.Profile = sk\npad.Length = 5\ndoc.recompute()\nresult = ('built', sk.FullyConstrained)" }
```
**And** `Body` sits at (1, 2, 3) rotated 90 deg about Z — verify: `mcp script_exec { doc: <handle>, code: "import FreeCAD as App\ndoc.Body.Placement = App.Placement(App.Vector(1, 2, 3), App.Rotation(App.Vector(0, 0, 1), 90))\ndoc.recompute()\nresult = [tuple(doc.Body.Placement.Base), round(doc.Body.Placement.Rotation.Angle * 57.29577951308232, 6)]" }` returns `[(1.0, 2.0, 3.0), 90.0]`  
**And** the before image is captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, then `echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-20-01-before.png"}' | "$FCB_CUA" get_window_state`  

**When** only `base.x` is written  
```
mcp feature_set_parameters { doc: <handle>, feature: "Body", parameters: { Placement: { base: { x: {value: 10, unit: "mm"} } } } }
```

**Then** the call succeeds — verify: `status` is `OK`, `structured_content.undo_steps` is `1`  
**And** y, z and the rotation are kept — verify: `mcp query_placement { doc: <handle>, object: "Body" }` reads local base (10, 2, 3) and rotation 90 deg about Z; `script_exec` `result = [tuple(doc.Body.Placement.Base), round(doc.Body.Placement.Rotation.Angle * 57.29577951308232, 6)]` returns `[(10.0, 2.0, 3.0), 90.0]`  
**And** an identical second call changes nothing — verify: the same call again returns `OK` with `structured_content.unchanged` equal to `["Placement"]`, `undo_steps` `0` and no `mutation` block  
**And** *(visual)* the solid moved — verify: `echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-20-01-after.png"}' | "$FCB_CUA" get_window_state`, then `Read` both PNGs and state whether the block sits at a different place in the viewport than before (the first write moved it by 9 mm along X; read the position, not the numbers). The judgement is on the pixels alone  
**And** undo restores the placement — verify: `mcp document_undo { doc: <handle> }` returns `OK`, then `mcp query_placement` reads local base (1, 2, 3); the second (no-op) call recorded no step, so a single undo reverts the first write  

**Cleanup**: `mcp document_close { doc: <handle> }`

---

### TC-20-02: A Label write reports the unique label; an attached sketch refuses a Placement write

**Priority**: High
**Design Ref**: `tool-contracts.md` T-4; decisions 34, 38

**Given** a new document `tc20_label` (`mcp document_create { label: "tc20_label" }`) built by the same `script_exec` call as TC-20-01 (`Profile` is fully constrained and attached with `MapMode` `FlatFace`; `Body` stays at the origin) — verify: the call returns `value_repr` `('built', True)` and `mcp query_tree_summary { doc: <handle> }` lists `Body`, `Profile`, `Block` with no `!` marker  

**And** the before image is captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, then `echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-20-02-before.png"}' | "$FCB_CUA" get_window_state`  

**When** `Block` is renamed to a label that another object holds, and the attached sketch is moved  
```
mcp feature_set_parameters { doc: <handle>, feature: "Block", parameters: { Label: "Profile" } }
mcp feature_set_parameters { doc: <handle>, feature: "Profile", parameters: { Placement: { base: { z: {value: 5, unit: "mm"} } } } }
mcp feature_set_parameters { doc: <handle>, feature: "Profile", parameters: { AttachmentOffset: { base: { z: {value: 5, unit: "mm"} } } } }
```

**Then** the rename succeeds with a unique label — verify: the first call returns `OK` with `structured_content.label` equal to `{requested: "Profile", stored: "Profile001"}`; `script_exec` `result = doc.Block.Label` returns `Profile001`  
**And** the placement write is refused before any change — verify: the second call returns `INVALID_INPUT`, `detail.message` contains `Profile.Placement is read-only` and `AttachmentOffset`; `script_exec` `result = doc.Profile.Placement.Base.z` returns `0.0`  
**And** the offset write moves the attached sketch — verify: the third call returns `OK`; `script_exec` `result = doc.Profile.Placement.Base.z` returns `5.0`  
**And** *(visual)* the sketch moved 5 mm and the model tree shows the new label — verify: with no new fit (a fit centres the moved model again and hides a uniform move), `echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-20-02-after.png"}' | "$FCB_CUA" get_window_state`; then expand `Body` in the model tree with a foreground pixel click on its expand arrow (`echo '{"pid":<pid>,"window_id":<wid>,"x":17,"y":175,"delivery_mode":"foreground"}' | "$FCB_CUA" click`; the tree item's AT-SPI `Toggle` selects the row and does not expand it), move the pointer off the window, wait 1 s and capture `$RUN_DIR/evidence/tc-20-02-tree.png`. `Read` the PNGs and state whether the solid (the pad follows its profile) sits higher in the viewport than before, and read the tree label of the pad under `Body` (`Profile001`). The judgement is on the pixels alone  
**And** undo restores both writes — verify: `mcp document_undo { doc: <handle> }` twice (the refused placement write recorded no step) returns `OK` each time; `script_exec` `result = [doc.Block.Label, doc.Profile.Placement.Base.z]` returns `["Block", 0.0]`  

**Cleanup**: `mcp document_close { doc: <handle> }`
