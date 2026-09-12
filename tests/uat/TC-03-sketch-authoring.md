# TC-03: Sketch Authoring

Exercises all eight `sketch_*` mutation tools against a live FreeCAD document, plus the two
read tools that grade their result: `query_sketch_info` and `verify_sketch`. The load-bearing rule
is AD-8: a sketch passes only when it is `FullyConstrained` with `dof == 0`, so geometry sent
without the constraints that pin it is rolled back — geometry included. Redundant constraints are
a warning and must never fail. Every scenario also proves the schema boundary: `{value, unit}`
quantities, the 16 constraint types, 1-based solver ids, and `additionalProperties: false`.

## Prerequisites

- [ ] FreeCAD GUI is open and the addon spawned the proxy (verify: `netstat -ano | grep :8765` shows LISTENING)
- [ ] The MCP tool surface is complete (verify: `mcp query_capabilities {}` lists 44 tools)
- [ ] The host runs the operator auto-approve posture, so a mutation needs no `preview_id` (verify: `mcp query_capabilities {}` reports the auto-approve posture, and the addon log carries `SECURITY: mutation auto-approve ENABLED by operator flag`)
- [ ] `FREECAD_BUDDY_AUTO_APPROVE=1` was set in the environment that launched FreeCAD (verify: the banner line above is present in `%APPDATA%/FreeCAD/v1-1/freecad-buddy/addon.log`)

**Confirm convention for this file**: every `sketch_*` call below is a geometry-intent mutation and
is gated by AD-10. This file runs under the operator auto-approve posture, so no scenario passes a
`confirm` object. The confirm gate's own negative cases — missing, expired, spent, wrong tool,
wrong document, wrong arguments — belong to TC-08 and are not repeated here.

---

### TC-03-01: sketch_create on each base plane

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.6 (sketch tools), `verification-design.md` §4 (AD-8)

**Preconditions**:
- [ ] A scratch document exists (verify: `mcp document_create { label: "BracketPlate" }` returns a handle)

**Steps**:
1. Create one sketch on each member of the `plane` enum:
   ```
   mcp sketch_create { doc: <handle>, name: "PlateProfileXY", plane: "XY" }
   mcp sketch_create { doc: <handle>, name: "RibProfileXZ",   plane: "XZ" }
   mcp sketch_create { doc: <handle>, name: "EndProfileYZ",   plane: "YZ" }
   ```
2. Grade each new sketch.
   ```
   mcp verify_sketch { doc: <handle>, sketch: "PlateProfileXY" }
   ```

**Checkpoints**:
- [ ] CP1: All three commit — verify: each envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: An empty sketch is fully constrained — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfileXY" }` returns `status=OK` with `subject.dof=0` and `subject.fully_constrained=true`
- [ ] CP3: The post-verify gate agrees — verify: each create envelope carries `mutation.post_verify.fully_constrained=true` and `mutation.post_verify.passed=true`
- [ ] CP4: The sketch is empty — verify: `mcp query_sketch_info { doc: <handle>, sketch: "RibProfileXZ" }` returns `geometry=[]` and `constraints=[]`
- [ ] CP5: Each lands on its own plane — verify: `mcp query_placement { doc: <handle>, object: "EndProfileYZ" }` reports a rotation distinct from `PlateProfileXY`
- [ ] CP6: A fourth plane value is a schema reject — verify: `mcp sketch_create { doc: <handle>, name: "BadPlane", plane: "ZX" }` is refused against the enum `["XY","XZ","YZ"]`, and `mcp query_tree_summary { doc: <handle> }` names no `BadPlane`

**Cleanup**:
```bash
# close the scratch document; no file was written
mcp document_close { doc: <handle> }
```

---

### TC-03-02: sketch_create inside a Body

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.6 (sketch tools), `mcp-tools-design.md` §3.7 (Body as container)

**Preconditions**:
- [ ] A scratch document exists (verify: `mcp document_create { label: "BracketPlate" }` returns a handle)
- [ ] A Body exists to adopt the sketch (verify: `mcp feature_body_create { doc: <handle>, name: "PlateBody" }` returns `status=OK`)

**Steps**:
1. Create the sketch into the Body:
   ```
   mcp sketch_create { doc: <handle>, name: "PlateProfile", plane: "XY", body: "PlateBody" }
   ```
2. Read the tree to see where the sketch landed.
   ```
   mcp query_tree_summary { doc: <handle>, depth: 3 }
   ```

**Checkpoints**:
- [ ] CP1: The create commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The sketch is inside the Body — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` shows `PlateProfile` as a child of `PlateBody`, not at document root
- [ ] CP3: The Body still carries no solid — verify: `mcp query_object { doc: <handle>, object: "PlateBody" }` reports no Tip feature, because a sketch is not a solid
- [ ] CP4: The sketch grades clean — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `status=OK` with `subject.dof=0`
- [ ] CP5: An unknown Body is rejected before the transaction — verify: `mcp sketch_create { doc: <handle>, name: "Orphan", plane: "XY", body: "NoSuchBody" }` returns `status=INVALID_INPUT` and the envelope carries no `mutation.snapshot_path`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-03: sketch_create on a planar face

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.2 (sub-element selectors, AD-7), `mcp-tools-design.md` §3.6

**Preconditions**:
- [ ] A Body carrying a 60 x 40 x 5 mm plate solid exists (verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume` near `12000.0`)
- [ ] The plate's top face name is known (verify: `mcp query_object { doc: <handle>, object: "PlatePad" }` lists the face names)

**Steps**:
1. Attach a new sketch to the plate's top face by selector:
   ```
   mcp sketch_create { doc: <handle>, name: "BossProfile",
                       face: { kind: "mapped_name", object: "PlatePad", mapped_name: "Face6" },
                       body: "PlateBody" }
   ```

**Checkpoints**:
- [ ] CP1: The create commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The sketch sits on the face plane — verify: `mcp query_placement { doc: <handle>, object: "BossProfile" }` reports `position.z` equal to the plate thickness `{value: 5, unit: "mm"}`
- [ ] CP3: The sketch grades clean — verify: `mcp verify_sketch { doc: <handle>, sketch: "BossProfile" }` returns `status=OK` with `subject.fully_constrained=true`
- [ ] CP4: `plane` and `face` together are rejected — verify: `mcp sketch_create { doc: <handle>, name: "Both", plane: "XY", face: { kind: "mapped_name", object: "PlatePad", mapped_name: "Face6" } }` returns `status=INVALID_INPUT` naming `sketch_create requires exactly one of 'plane' and 'face'`
- [ ] CP5: A non-planar face is rejected — verify: a selector naming a cylindrical face returns `status=INVALID_INPUT` naming `is not a planar face`
- [ ] CP6: A `geometric` selector kind is rejected — verify: `face: { kind: "geometric", object: "PlatePad" }` returns `status=INVALID_INPUT` naming `selector kind must be 'mapped_name'`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-04: Rectangle reaches FullyConstrained in one flow

**Priority**: Critical
**Design Ref**: `verification-design.md` §4 (AD-8), `mcp-tools-design.md` §3.6

**Preconditions**:
- [ ] An empty sketch exists on XY (verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` returns `geometry=[]`)

**Steps**:
1. Add the four edges of a 60 x 40 mm plate outline with their constraints in one call. Sketch
   geo_ids are 0-based, so the four lines are 0..3.
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
2. Grade the sketch.
   ```
   mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }
   ```

**Checkpoints**:
- [ ] CP1: The call commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: AD-8 PASS — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `status=OK` with `subject.dof=0` and `subject.fully_constrained=true`
- [ ] CP3: The check id is the AD-8 one — verify: the same envelope carries a passed check with `id=sketch.fully_constrained` and `expected=true`
- [ ] CP4: The post-verify gate agrees — verify: the mutation envelope carries `mutation.post_verify.fully_constrained=true` and `mutation.post_verify.passed=true`
- [ ] CP5: Counts match the request — verify: the same verify envelope reports `subject.geometry_count=4` and `subject.constraint_count=11`
- [ ] CP6: No conflicting or malformed constraints — verify: `subject.conflicting=[]` and `subject.malformed=[]`
- [ ] CP7: The datum names survived — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` lists constraints named `PlateWidth` and `PlateDepth`, each with `driving=true`
- [ ] CP8: The envelope reports the state it produced — verify: the mutation envelope's `sketch_state` block has `readable=true`, `dof=0` and `fully_constrained=true`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-05: All four geometry kinds

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.6 (geometry kind enum)

**Preconditions**:
- [ ] An empty sketch exists on XY (verify: `mcp query_sketch_info { doc: <handle>, sketch: "MixedProfile" }` returns `geometry=[]`)

**Steps**:
1. Add one instance of every member of the `kind` enum, each fully pinned. Circle and arc radii are
   `{value, unit}` length quantities; arc angles are `{value, unit}` angle quantities.
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
       { type: "DistanceX", first: 2, first_pos: 1, value: { value: 58, unit: "mm" } },
       { type: "DistanceY", first: 2, first_pos: 1, value: { value: 20, unit: "mm" } },
       { type: "DistanceX", first: 2, first_pos: 2, value: { value: 50, unit: "mm" } },
       { type: "DistanceY", first: 2, first_pos: 2, value: { value: 28, unit: "mm" } },
       { type: "DistanceX", first: 3, first_pos: 1, value: { value: 10, unit: "mm" } },
       { type: "DistanceY", first: 3, first_pos: 1, value: { value: 30, unit: "mm" } }
     ] }
   ```

**Checkpoints**:
- [ ] CP1: All four kinds are created — verify: `mcp query_sketch_info { doc: <handle>, sketch: "MixedProfile" }` lists 4 geometry entries at `index` 0..3
- [ ] CP2: Each kind maps to the FreeCAD type — verify: the same read reports `type` values `Part::GeomLineSegment`, `Part::GeomCircle`, `Part::GeomArcOfCircle`, `Part::GeomPoint` in index order
- [ ] CP3: geo_ids returned are 0-based — verify: the mutation envelope names the created geometry starting at `0`, matching the `index` values in CP1
- [ ] CP4: AD-8 PASS — verify: `mcp verify_sketch { doc: <handle>, sketch: "MixedProfile" }` returns `status=OK` with `subject.dof=0`
- [ ] CP5: A fifth kind is a schema reject — verify: `geometry: [ { kind: "ellipse", center: [0,0] } ]` is refused against the enum `["line_segment","circle","arc_of_circle","point"]`
- [ ] CP6: A coordinate array outside 2..3 entries is a schema reject — verify: `start: [0, 0, 0, 0]` is refused (`maxItems: 3`), and `start: [0]` is refused (`minItems: 2`)
- [ ] CP7: A bare number radius is a schema reject — verify: `radius: 2.5` is refused; the schema requires `{value, unit}` with both fields

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-06: All 16 constraint types

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.6 (`sketch_add_constraint`, constraint type enum)

**Preconditions**:
- [ ] A sketch carrying enough geometry to host each family exists: two lines, two circles, and a point (verify: `mcp query_sketch_info { doc: <handle>, sketch: "ConstraintBed" }` reports 5 geometry entries)

**Steps**:
1. Add the geometric family, one constraint per type:
   ```
   mcp sketch_add_constraint { doc: <handle>, sketch: "ConstraintBed",
     constraints: [
       { type: "Coincident",    first: 0, first_pos: 2, second: 1, second_pos: 1 },
       { type: "Horizontal",    first: 0 },
       { type: "Vertical",      first: 1 },
       { type: "Parallel",      first: 0, second: 4 },
       { type: "Perpendicular", first: 1, second: 4 },
       { type: "Tangent",       first: 2, second: 3 },
       { type: "Equal",         first: 2, second: 3 },
       { type: "Symmetric",     first: 0, first_pos: 1, second: 0, second_pos: 2, third: -2 },
       { type: "PointOnObject", first: 5, first_pos: 1, second: 0 },
       { type: "Block",         first: 4 }
     ] }
   ```
2. Add the dimensional family, one constraint per type:
   ```
   mcp sketch_add_constraint { doc: <handle>, sketch: "ConstraintBed",
     constraints: [
       { type: "Distance",  first: 0, first_pos: 1, second: 0, second_pos: 2,
         value: { value: 60, unit: "mm" } },
       { type: "DistanceX", first: 1, first_pos: 1, value: { value: 60, unit: "mm" } },
       { type: "DistanceY", first: 1, first_pos: 1, value: { value: 0, unit: "mm" } },
       { type: "Radius",    first: 2, value: { value: 2.5, unit: "mm" } },
       { type: "Diameter",  first: 3, value: { value: 5, unit: "mm" } },
       { type: "Angle",     first: 0, second: 4, value: { value: 45, unit: "deg" } }
     ] }
   ```

**Checkpoints**:
- [ ] CP1: Every type in the enum is accepted — verify: both calls return `status=OK`, covering all 16 members `Coincident Horizontal Vertical Parallel Perpendicular Tangent Equal Symmetric PointOnObject Block Distance DistanceX DistanceY Radius Diameter Angle`
- [ ] CP2: Returned solver ids are 1-based — verify: the first call's lowest returned constraint id is `1`, never `0`
- [ ] CP3: Ids match the read back — verify: `mcp query_sketch_info { doc: <handle>, sketch: "ConstraintBed" }` lists constraints with `id` running `1..16` and no `id=0`
- [ ] CP4: Dimensional constraints carry their unit — verify: the same read reports `value` as `{value: 2.5, unit: "mm"}` for the Radius and `{value: 45, unit: "deg"}` for the Angle
- [ ] CP5: A 17th type is a schema reject — verify: `{ type: "Symmetry", first: 0 }` is refused against the 16-member enum
- [ ] CP6: `first` is required — verify: `{ type: "Horizontal" }` is refused; `required` is `["type","first"]`
- [ ] CP7: A `*_pos` outside 0..3 is a schema reject — verify: `first_pos: 4` is refused against the enum `[0,1,2,3]`
- [ ] CP8: The sketch grades — verify: `mcp verify_sketch { doc: <handle>, sketch: "ConstraintBed" }` returns a graded envelope with `subject.constraint_count=16`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-07: sketch_set_datum drives a downstream Pad

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.6 (`sketch_set_datum`), `verification-design.md` §5 (verify_shape)

**Preconditions**:
- [ ] A fully constrained 10 x 40 mm rectangle sketch named `TabProfile` exists, with a driving `DistanceX` constraint named `TabWidth` set to 10 mm (verify: `mcp query_sketch_info { doc: <handle>, sketch: "TabProfile" }` shows `TabWidth` with `value={value:10,unit:"mm"}` and `driving=true`)
- [ ] A 5 mm Pad named `TabPad` consumes that sketch (verify: `mcp query_mass_properties { doc: <handle>, object: "TabPad" }` returns `volume` near `2000.0`)

**Steps**:
1. Change the driving dimension from 10 mm to 25 mm:
   ```
   mcp sketch_set_datum { doc: <handle>, sketch: "TabProfile",
                          constraint: "TabWidth", value: { value: 25, unit: "mm" } }
   ```
2. Recompute and re-measure the downstream solid.
   ```
   mcp document_recompute { doc: <handle> }
   mcp query_mass_properties { doc: <handle>, object: "TabPad" }
   ```

**Checkpoints**:
- [ ] CP1: The datum edit commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The new datum is stored — verify: `mcp query_sketch_info { doc: <handle>, sketch: "TabProfile" }` reports `TabWidth` with `value={value:25,unit:"mm"}`
- [ ] CP3: The sketch stays fully constrained — verify: `mcp verify_sketch { doc: <handle>, sketch: "TabProfile" }` returns `status=OK` with `subject.dof=0`
- [ ] CP4: The Pad volume tracks the change — verify: `mcp query_mass_properties { doc: <handle>, object: "TabPad" }` returns `volume` near `5000.0` (25 x 40 x 5), within 0.1 %
- [ ] CP5: The solid stays valid — verify: `mcp verify_shape { doc: <handle>, object: "TabPad" }` returns `status=OK`
- [ ] CP6: `value` and `sense` together are rejected — verify: `mcp sketch_set_datum { doc: <handle>, sketch: "TabProfile", constraint: "TabWidth", value: { value: 25, unit: "mm" }, sense: "internal" }` returns `status=INVALID_INPUT` naming `sketch_set_datum requires exactly one of 'value' and 'sense'`
- [ ] CP7: A non-driving constraint is rejected — verify: setting a datum on a reference (non-driving) constraint returns `status=INVALID_INPUT` naming `is not driving; its datum is read-only`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-08: sketch_toggle_construction on and back

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.6 (`sketch_toggle_construction`)

**Preconditions**:
- [ ] A fully constrained sketch named `PlateProfile` holds 4 line segments plus one extra diagonal line at geo_id 4 (verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports 5 geometry entries, all with `construction=false`)

**Steps**:
1. Turn the diagonal into construction geometry:
   ```
   mcp sketch_toggle_construction { doc: <handle>, sketch: "PlateProfile", geo_ids: [4] }
   ```
2. Read the state, then toggle it back:
   ```
   mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }
   mcp sketch_toggle_construction { doc: <handle>, sketch: "PlateProfile", geo_ids: [4] }
   ```

**Checkpoints**:
- [ ] CP1: The first toggle commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The flag is on — verify: after step 1, `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports the entry at `index=4` with `construction=true`
- [ ] CP3: Nothing else changed — verify: the same read reports `construction=false` for `index` 0..3
- [ ] CP4: The flag is off again — verify: after step 2, the entry at `index=4` reports `construction=false`
- [ ] CP5: The sketch stays fully constrained across both toggles — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `subject.dof=0` after each
- [ ] CP6: A repeated geo_id in one call is rejected — verify: `geo_ids: [4, 4]` returns `status=INVALID_INPUT` naming `is listed twice; a double toggle is a no-op`
- [ ] CP7: An out-of-range geo_id is rejected — verify: `geo_ids: [99]` returns `status=INVALID_INPUT` naming `is outside the sketch (0..4)`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-09: Unconstrained geometry is rolled back with the geometry

**Priority**: Critical
**Design Ref**: `verification-design.md` §4 (AD-8 pass/fail policy), `verification-design.md` §1 (mutation protocol, AD-5)

**Preconditions**:
- [ ] An empty, fully constrained sketch exists (verify: `mcp verify_sketch { doc: <handle>, sketch: "LooseProfile" }` returns `subject.dof=0` and `subject.geometry_count=0`)
- [ ] The document fingerprint before the call is recorded (verify: `mcp query_tree_summary { doc: <handle> }` and note the object list)

**Steps**:
1. Send geometry with no constraints at all:
   ```
   mcp sketch_add_geometry { doc: <handle>, sketch: "LooseProfile",
     geometry: [ { kind: "line_segment", start: [0, 0], end: [60, 0] } ] }
   ```

**Checkpoints**:
- [ ] CP1: The call does not commit — verify: the envelope returns `status=SPEC_FAILED`, not `OK`
- [ ] CP2: The rollback is proven — verify: the envelope carries `mutation.rolled_back=true` and `mutation.post_verify.passed=false`
- [ ] CP3: The cause names the sketch and its dof — verify: `mutation.post_verify.explanation` starts `verify_sketch failed on LooseProfile (dof=` with a non-zero dof
- [ ] CP4: The geometry is gone too — verify: `mcp query_sketch_info { doc: <handle>, sketch: "LooseProfile" }` returns `geometry=[]`, so the rollback removed the line, not only the failure
- [ ] CP5: The document is back to its prior state — verify: `mutation.fingerprint_before.digest` equals `mutation.fingerprint_after.digest`, or the rollback state is `rolled_back_via_snapshot`
- [ ] CP6: No snapshot is left behind — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing for this run, because a proven rollback deletes its snapshot
- [ ] CP7: The sketch is still gradeable — verify: `mcp verify_sketch { doc: <handle>, sketch: "LooseProfile" }` returns `status=OK` with `subject.dof=0`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-10: sketch_remove_geometry cascades its constraints

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.6 (`sketch_remove_geometry`)

**Preconditions**:
- [ ] A fully constrained 60 x 40 mm rectangle sketch exists with 4 lines and 11 constraints (verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` reports `subject.geometry_count=4` and `subject.constraint_count=11`)
- [ ] The constraint list is recorded (verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` lists ids 1..11 with their types)

**Steps**:
1. Remove one edge of the rectangle:
   ```
   mcp sketch_remove_geometry { doc: <handle>, sketch: "PlateProfile", geo_ids: [3] }
   ```
2. Read what survived.
   ```
   mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }
   ```

**Checkpoints**:
- [ ] CP1: Removing the edge leaves the rest under-constrained, so the call is rolled back — verify: the envelope returns `status=SPEC_FAILED` with `mutation.rolled_back=true`
- [ ] CP2: The cause is the dof, not a crash — verify: `mutation.post_verify.explanation` names `verify_sketch failed on PlateProfile (dof=`
- [ ] CP3: The rollback restored the edge — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` again reports 4 geometry entries
- [ ] CP4: The dependent constraints came back too — verify: the same read again reports 11 constraints, proving the cascade was undone as a unit
- [ ] CP5: The cascade is observable when the result stays constrained — verify: on a sketch where the removed geometry carries only its own constraints, the call returns `status=OK` and `subject.constraint_count` drops by exactly the number of constraints referencing that geo_id
- [ ] CP6: An out-of-range geo_id is rejected before the transaction — verify: `geo_ids: [7]` returns `status=INVALID_INPUT` naming `is outside the sketch (0..3)` with no `mutation.snapshot_path`
- [ ] CP7: An empty list is a schema reject — verify: `geo_ids: []` is refused against `minItems: 1`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-11: sketch_remove_constraint by id and by name

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.6 (`sketch_remove_constraint`, constraint reference `anyOf`)

**Preconditions**:
- [ ] A fully constrained rectangle sketch exists carrying a redundant extra constraint at the end, so removing one still grades (verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` lists a named constraint `SpareWidth` and a `Horizontal` at a known id)

**Steps**:
1. Remove by 1-based solver id — the integer branch of the `anyOf`:
   ```
   mcp sketch_remove_constraint { doc: <handle>, sketch: "PlateProfile", constraints: [12] }
   ```
2. Remove by name — the string branch of the same `anyOf`:
   ```
   mcp sketch_remove_constraint { doc: <handle>, sketch: "PlateProfile", constraints: ["SpareWidth"] }
   ```

**Checkpoints**:
- [ ] CP1: The id branch works — verify: step 1 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The name branch works — verify: step 2 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP3: The count drops by one each time — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports `constraints` one shorter after each call
- [ ] CP4: The named constraint is gone — verify: the same read lists no constraint named `SpareWidth`
- [ ] CP5: Id `0` is a schema reject — verify: `constraints: [0]` is refused; the integer branch has `minimum: 1`, because solver ids are 1-based
- [ ] CP6: An unknown name is rejected — verify: `constraints: ["NoSuchConstraint"]` returns `status=INVALID_INPUT` naming `no constraint named 'NoSuchConstraint' in the sketch`
- [ ] CP7: A wrong-typed reference is a schema reject — verify: `constraints: [ { id: 3 } ]` is refused; the `anyOf` accepts only an integer or a string

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-12: Redundant constraints warn and commit

**Priority**: Critical
**Design Ref**: `verification-design.md` §4.2 (pass/warn/fail policy, AD-8)

**Preconditions**:
- [ ] A fully constrained 60 x 40 mm rectangle sketch exists (verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `status=OK` with `subject.dof=0` and `subject.redundant=[]`)

**Steps**:
1. Add a constraint that repeats information the sketch already carries — a second `Horizontal`
   on a line the solver already holds horizontal:
   ```
   mcp sketch_add_constraint { doc: <handle>, sketch: "PlateProfile",
     constraints: [ { type: "Horizontal", first: 0 } ] }
   ```
2. Grade the sketch.
   ```
   mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }
   ```

**Checkpoints**:
- [ ] CP1: A redundant constraint commits — verify: the mutation envelope returns `status=OK` with `mutation.rolled_back=false`, never `SPEC_FAILED`
- [ ] CP2: AD-8 still grades PASS — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `status=OK`, because a redundancy is never a failed check
- [ ] CP3: The redundancy is reported as a warning — verify: the same envelope carries a `warnings` entry with `id=sketch.redundant` and `detail.message` equal to `redundant constraints present (warning only)`
- [ ] CP4: The offending constraint is named — verify: the same envelope's `subject.redundant` is a non-empty list of constraint references
- [ ] CP5: The failing check did not fire — verify: the `sketch.fully_constrained` check still reports `passed=true` with `measured=true`
- [ ] CP6: The redundant constraint is not auto-removed — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports `constraint_count` one higher than before, so nothing was silently deleted
- [ ] CP7: `dof` is unchanged — verify: `subject.dof=0`, because a redundant constraint removes no freedom

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-13: sketch_add_external_geometry projects a model edge

**Priority**: Critical
**Design Ref**: `verification-design.md` §3 (TNP guard, AD-7), `mcp-tools-design.md` §1.2 (selectors)

**Preconditions**:
- [ ] A Body holds a 60 x 40 x 5 mm plate solid named `PlatePad` (verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume` near `12000.0`)
- [ ] A sketch named `BossProfile` sits on the plate's top face (verify: `mcp verify_sketch { doc: <handle>, sketch: "BossProfile" }` returns `status=OK`)
- [ ] The target edge name is known (verify: `mcp query_object { doc: <handle>, object: "PlatePad" }` lists the edge names)

**Steps**:
1. Project one edge of the plate into the sketch:
   ```
   mcp sketch_add_external_geometry { doc: <handle>, sketch: "BossProfile",
     edge: { kind: "mapped_name", object: "PlatePad", mapped_name: "Edge1" } }
   ```

**Checkpoints**:
- [ ] CP1: The projection commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The sketch stays fully constrained — verify: `mcp verify_sketch { doc: <handle>, sketch: "BossProfile" }` returns `status=OK` with `subject.dof=0`; external geometry adds no freedom
- [ ] CP3: The TNP audit ran and is clean — verify: the mutation envelope carries `mutation.post_verify.tnp_audit.status=CLEAN` with `findings=[]`
- [ ] CP4: The audit recorded the element map version — verify: the same block carries a non-empty `tnp_audit.element_map_version`
- [ ] CP5: The reference is held by the sketch — verify: `mcp query_dependencies { doc: <handle> }` shows an edge from `BossProfile` to `PlatePad`
- [ ] CP6: An unknown source object is rejected before the transaction — verify: `edge: { kind: "mapped_name", object: "NoSuchPad", mapped_name: "Edge1" }` returns `status=INVALID_INPUT` naming `unknown object in edge selector: NoSuchPad`
- [ ] CP7: A face selector is rejected — verify: a selector whose `mapped_name` resolves to a face returns `status=INVALID_INPUT` naming `resolves to a Face, not an Edge`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-14: Axis references -1 and -2 resolve as operands

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.6 (constraint `first`: -1 HAxis, -2 VAxis)

**Preconditions**:
- [ ] A sketch holds an unpinned rectangle whose corner is not yet tied to the origin (verify: `mcp verify_sketch { doc: <handle>, sketch: "AxisProfile" }` reports `subject.dof` greater than 0)

**Steps**:
1. Constrain a line against the sketch H axis, addressed as `-1`:
   ```
   mcp sketch_add_constraint { doc: <handle>, sketch: "AxisProfile",
     constraints: [ { type: "PointOnObject", first: 0, first_pos: 1, second: -1 } ] }
   ```
2. Constrain another line against the V axis, addressed as `-2`:
   ```
   mcp sketch_add_constraint { doc: <handle>, sketch: "AxisProfile",
     constraints: [ { type: "PointOnObject", first: 3, first_pos: 1, second: -2 } ] }
   ```

**Checkpoints**:
- [ ] CP1: `-1` resolves as HAxis — verify: step 1 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: `-2` resolves as VAxis — verify: step 2 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP3: The dof falls — verify: `mcp verify_sketch { doc: <handle>, sketch: "AxisProfile" }` reports a lower `subject.dof` after each call than before it
- [ ] CP4: The axis constraints are readable — verify: `mcp query_sketch_info { doc: <handle>, sketch: "AxisProfile" }` lists both `PointOnObject` constraints with 1-based ids
- [ ] CP5: An axis works as `first` too — verify: `{ type: "Coincident", first: -1, first_pos: 1, second: 0, second_pos: 1 }` is accepted, because `first` is a plain integer and negative values address the axes
- [ ] CP6: An undefined negative index is rejected — verify: `second: -9` returns `status=INVALID_INPUT`; only `-1` and `-2` name axes

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-15: Zero, negative and very large datum values

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.6 (`sketch_set_datum`), `verification-design.md` §4

**Preconditions**:
- [ ] A fully constrained sketch carries a driving `Radius` named `BossRadius` at 2.5 mm and a driving `Distance` named `HoleSpacing` at 40 mm (verify: `mcp query_sketch_info { doc: <handle>, sketch: "BossProfile" }` shows both with `driving=true`)

**Steps**:
1. Try a zero radius:
   ```
   mcp sketch_set_datum { doc: <handle>, sketch: "BossProfile",
                          constraint: "BossRadius", value: { value: 0, unit: "mm" } }
   ```
2. Try a negative distance:
   ```
   mcp sketch_set_datum { doc: <handle>, sketch: "BossProfile",
                          constraint: "HoleSpacing", value: { value: -5, unit: "mm" } }
   ```
3. Try a distance far outside any real part:
   ```
   mcp sketch_set_datum { doc: <handle>, sketch: "BossProfile",
                          constraint: "HoleSpacing", value: { value: 1e9, unit: "mm" } }
   ```

**Checkpoints**:
- [ ] CP1: A zero radius is refused — verify: step 1 returns a non-`OK` status; a `Radius` datum must be non-zero
- [ ] CP2: The refusal is pre-transaction — verify: the step 1 envelope carries no `mutation.snapshot_path`, so no snapshot was written
- [ ] CP3: A negative distance is refused or rolled back — verify: step 2 returns `status=INVALID_INPUT`, or `status=SPEC_FAILED` with `mutation.rolled_back=true`
- [ ] CP4: A 1e9 mm distance does not commit a broken sketch — verify: step 3 returns either `INVALID_INPUT`, or `OK` with `mcp verify_sketch { doc: <handle>, sketch: "BossProfile" }` still reporting `subject.dof=0` and `subject.malformed=[]`
- [ ] CP5: The original datum survives every refusal — verify: after all three steps, `mcp query_sketch_info { doc: <handle>, sketch: "BossProfile" }` reports `BossRadius` at `{value: 2.5, unit: "mm"}`
- [ ] CP6: A non-finite value is refused — verify: `value: { value: 1e999, unit: "mm" }` (which encodes as infinity) returns `status=INVALID_INPUT` naming `must be finite`
- [ ] CP7: No snapshot is orphaned — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing for this run

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-16: Conflicting constraints name the offending ids

**Priority**: Critical
**Design Ref**: `verification-design.md` §4.2 (hard fail on conflicting/malformed), `mcp-tools-design.md` §3.6

**Preconditions**:
- [ ] A fully constrained 60 x 40 mm rectangle sketch exists with a driving `DistanceX` named `PlateWidth` at 60 mm (verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `subject.dof=0` and `subject.conflicting=[]`)
- [ ] The constraint count before the call is recorded (verify: the same read reports `subject.constraint_count`)

**Steps**:
1. Add a second, contradictory length on the same edge — 45 mm where the sketch already says 60 mm:
   ```
   mcp sketch_add_constraint { doc: <handle>, sketch: "PlateProfile",
     constraints: [ { type: "DistanceX", first: 0, first_pos: 1, second: 0, second_pos: 2,
                      value: { value: 45, unit: "mm" }, name: "ConflictWidth" } ] }
   ```

**Checkpoints**:
- [ ] CP1: The conflicting set does not commit — verify: the envelope returns `status=SPEC_FAILED`, not `OK`
- [ ] CP2: The rollback is proven — verify: the envelope carries `mutation.rolled_back=true`
- [ ] CP3: The cause names the sketch — verify: `mutation.post_verify.explanation` starts `verify_sketch failed on PlateProfile (dof=`
- [ ] CP4: The offending ids are reported — verify: the failure detail or `sketch_state` names the conflicting solver ids, not a bare message
- [ ] CP5: The conflicting constraint is gone — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` lists no constraint named `ConflictWidth`
- [ ] CP6: The count is back to its prior value — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` reports the same `subject.constraint_count` as the precondition
- [ ] CP7: The sketch is healthy again — verify: the same envelope returns `status=OK` with `subject.dof=0` and `subject.conflicting=[]`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-17: Unknown sketch name and unknown geo_id

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.3 (result envelope and error surface, AD-17)

**Preconditions**:
- [ ] A document holds exactly one sketch, `PlateProfile`, with 4 geometry entries (verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports 4 entries)
- [ ] The temp directory holds no snapshot from a prior run (verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing)

**Steps**:
1. Name a sketch that does not exist:
   ```
   mcp sketch_add_geometry { doc: <handle>, sketch: "NoSuchSketch",
     geometry: [ { kind: "point", start: [0, 0] } ] }
   ```
2. Name a geo_id past the end of a real sketch:
   ```
   mcp sketch_remove_geometry { doc: <handle>, sketch: "PlateProfile", geo_ids: [99] }
   ```
3. Name an object that exists but is not a sketch:
   ```
   mcp sketch_add_constraint { doc: <handle>, sketch: "PlatePad",
     constraints: [ { type: "Horizontal", first: 0 } ] }
   ```

**Checkpoints**:
- [ ] CP1: An unknown sketch is `INVALID_INPUT` — verify: step 1 returns `status=INVALID_INPUT` naming `unknown object: NoSuchSketch`
- [ ] CP2: An out-of-range geo_id is `INVALID_INPUT` — verify: step 2 returns `status=INVALID_INPUT` naming `is outside the sketch (0..3)`
- [ ] CP3: A non-sketch object is `INVALID_INPUT` — verify: step 3 returns `status=INVALID_INPUT` naming `object is not a sketch: PlatePad`
- [ ] CP4: No transaction opened — verify: none of the three envelopes carries `mutation.snapshot_path`
- [ ] CP5: No snapshot was written — verify: `ls "$TEMP"/FCB_TMP_snap_*` still lists nothing after all three steps
- [ ] CP6: The document is untouched — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` lists the same objects as the precondition
- [ ] CP7: The status is the closed-set value — verify: each `status` is exactly `INVALID_INPUT`, never a free-text error or `SPEC_FAILED`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-18: Wrong unit on a datum is a schema reject

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.4 (quantity fields), `mcp-tools-design.md` §3.6

**Preconditions**:
- [ ] A fully constrained sketch carries a driving `Distance` named `HoleSpacing` at 40 mm and a driving `Angle` named `RibAngle` at 45 deg (verify: `mcp query_sketch_info { doc: <handle>, sketch: "BracketProfile" }` shows `HoleSpacing` with `unit: "mm"` and `RibAngle` with `unit: "deg"`)

**Steps**:
1. Send degrees where the schema allows only millimetres:
   ```
   mcp sketch_set_datum { doc: <handle>, sketch: "BracketProfile",
                          constraint: "HoleSpacing", value: { value: 10, unit: "deg" } }
   ```
2. Send a bare number with no unit at all:
   ```
   mcp sketch_add_geometry { doc: <handle>, sketch: "BracketProfile",
     geometry: [ { kind: "circle", center: [20, 20], radius: 2.5 } ] }
   ```
3. Send a quantity missing its `value`:
   ```
   mcp sketch_set_datum { doc: <handle>, sketch: "BracketProfile",
                          constraint: "HoleSpacing", value: { unit: "mm" } }
   ```

**Checkpoints**:
- [ ] CP1: A `deg` datum on a length constraint does not commit — verify: step 1 returns a non-`OK` status; `sketch_set_datum.value` accepts `["mm","deg"]` at the schema, and the use case then refuses the wrong dimension for a `Distance`
- [ ] CP2: The refusal names the unit — verify: the step 1 detail names the allowed unit for that constraint type
- [ ] CP3: A geometry `radius` in `deg` is a hard schema reject — verify: `radius: { value: 2.5, unit: "deg" }` is refused; `_LENGTH_QUANTITY_SCHEMA` allows the enum `["mm"]` only
- [ ] CP4: A bare number is a schema reject — verify: step 2 is refused; the quantity schema requires an object with both `value` and `unit`
- [ ] CP5: A missing `value` is a schema reject — verify: step 3 is refused against `required: ["value","unit"]`
- [ ] CP6: An extra key inside a quantity is a schema reject — verify: `value: { value: 10, unit: "mm", tolerance: 0.1 }` is refused; the quantity schema sets `additionalProperties: false`
- [ ] CP7: The sketch is unchanged — verify: `mcp query_sketch_info { doc: <handle>, sketch: "BracketProfile" }` still reports `HoleSpacing` at `{value: 40, unit: "mm"}`
- [ ] CP8: An angle constraint still accepts `deg` — verify: `mcp sketch_set_datum { doc: <handle>, sketch: "BracketProfile", constraint: "RibAngle", value: { value: 30, unit: "deg" } }` returns `status=OK`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-19: Constraint referencing a removed geo_id

**Priority**: Critical
**Design Ref**: `verification-design.md` §4.2 (malformed constraints are a hard fail), `verification-design.md` §1

**Preconditions**:
- [ ] A fully constrained sketch holds 4 lines at geo_ids 0..3 (verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` reports `subject.geometry_count=4` and `subject.malformed=[]`)
- [ ] A spare sketch exists whose geometry can be removed without breaking its grade (verify: `mcp query_sketch_info { doc: <handle>, sketch: "ScrapProfile" }` reports its entries)

**Steps**:
1. Remove a geometry from the spare sketch so a later reference to it is stale:
   ```
   mcp sketch_remove_geometry { doc: <handle>, sketch: "ScrapProfile", geo_ids: [1] }
   ```
2. Reference the geo_id that no longer exists:
   ```
   mcp sketch_add_constraint { doc: <handle>, sketch: "ScrapProfile",
     constraints: [ { type: "Horizontal", first: 1 } ] }
   ```
3. Reference a geo_id far past the end in one batch alongside a valid constraint:
   ```
   mcp sketch_add_constraint { doc: <handle>, sketch: "PlateProfile",
     constraints: [ { type: "Horizontal", first: 0 },
                    { type: "Horizontal", first: 88 } ] }
   ```

**Checkpoints**:
- [ ] CP1: A stale geo_id is refused — verify: step 2 returns `status=INVALID_INPUT` naming the geo_id as outside the sketch
- [ ] CP2: The refusal is pre-transaction — verify: the step 2 envelope carries no `mutation.snapshot_path`
- [ ] CP3: A mixed batch is refused as a whole — verify: step 3 returns a non-`OK` status; the valid `Horizontal` at index 0 is not applied on its own
- [ ] CP4: The valid constraint did not land — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports the same `constraints` list as before step 3
- [ ] CP5: No malformed constraint was committed — verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `subject.malformed=[]`
- [ ] CP6: The sketch still grades PASS — verify: the same envelope returns `status=OK` with `subject.dof=0`
- [ ] CP7: No snapshot is left behind — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing for this run

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-20: Deleted external-geometry source is reported BROKEN

**Priority**: Critical
**Design Ref**: `verification-design.md` §3.2 (TNP audit layers, AD-7), `verification-design.md` §3.3 (verdict shape)

**Preconditions**:
- [ ] A sketch named `BossProfile` holds external geometry projected from `PlatePad` (verify: `mcp query_dependencies { doc: <handle> }` shows an edge from `BossProfile` to `PlatePad`)
- [ ] The last mutation's TNP audit was clean (verify: the `sketch_add_external_geometry` envelope carried `mutation.post_verify.tnp_audit.status=CLEAN`)

**Steps**:
1. Break the source by moving the face the external edge came from. Change the Pad that owns it:
   ```
   mcp feature_set_parameters { doc: <handle>, feature: "PlatePad",
                                parameters: { Length: { value: 30, unit: "mm" } } }
   ```
2. Run the next mutation on the sketch and read the audit it carries:
   ```
   mcp sketch_add_constraint { doc: <handle>, sketch: "BossProfile",
     constraints: [ { type: "Horizontal", first: 0 } ] }
   ```
3. If the source is deleted outright instead, the reference vanishes. Delete the base and repeat
   the read.

**Checkpoints**:
- [ ] CP1: The TNP audit runs on every mutation — verify: each mutation envelope carries a `mutation.post_verify.tnp_audit` block with a `status` and a `findings` list
- [ ] CP2: A broken external reference is graded `BROKEN` — verify: once the source edge no longer resolves, the audit carries a finding with `verdict=BROKEN` naming `BossProfile` as the `owner`
- [ ] CP3: A `BROKEN` finding fails the mutation — verify: that mutation returns `status=SPEC_FAILED` with `mutation.rolled_back=true`, because only `PASS` and `RE_BASELINED` are allowed to pass
- [ ] CP4: The explanation names the reference — verify: `mutation.post_verify.explanation` starts `TNP audit flagged` and names the owner and property
- [ ] CP5: A rebased element map is not a failure — verify: a finding with `verdict=RE_BASELINED` leaves the mutation at `status=OK`, per the re-baseline rule
- [ ] CP6: The audit reports the build's element map version — verify: `tnp_audit.element_map_version` is non-empty on both the clean and the flagged reading
- [ ] CP7: The document survives the rollback — verify: `mcp verify_recompute { doc: <handle> }` returns `status=OK` after the failed mutation

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-03-21: Unknown key anywhere is a hard reject

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.3 (error surface, AD-17), `mcp-tools-design.md` §3.6

**Preconditions**:
- [ ] A fully constrained sketch exists (verify: `mcp verify_sketch { doc: <handle>, sketch: "PlateProfile" }` returns `status=OK`)
- [ ] The document object list before the call is recorded (verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }`)

**Steps**:
1. Add an unknown key at the top level of a sketch tool:
   ```
   mcp sketch_create { doc: <handle>, name: "ExtraKey", plane: "XY", visible: true }
   ```
2. Add an unknown key inside a nested geometry spec:
   ```
   mcp sketch_add_geometry { doc: <handle>, sketch: "PlateProfile",
     geometry: [ { kind: "point", start: [5, 5], color: "red" } ] }
   ```
3. Add an unknown key inside a nested constraint spec:
   ```
   mcp sketch_add_constraint { doc: <handle>, sketch: "PlateProfile",
     constraints: [ { type: "Horizontal", first: 0, weight: 2 } ] }
   ```
4. Add an unknown key inside a selector:
   ```
   mcp sketch_add_external_geometry { doc: <handle>, sketch: "PlateProfile",
     edge: { kind: "mapped_name", object: "PlatePad", mapped_name: "Edge1", hint: "top" } }
   ```

**Checkpoints**:
- [ ] CP1: A top-level unknown key is refused — verify: step 1 is rejected; every sketch input schema sets `additionalProperties: false`
- [ ] CP2: A nested geometry key is refused — verify: step 2 is rejected against `_GEOMETRY_SPEC_SCHEMA`, which also sets `additionalProperties: false`
- [ ] CP3: A nested constraint key is refused — verify: step 3 is rejected against `_CONSTRAINT_SPEC_SCHEMA`
- [ ] CP4: A selector key is refused — verify: step 4 is rejected against `_SUBELEMENT_SELECTOR_SCHEMA`
- [ ] CP5: The rejection is a protocol error, not an envelope — verify: each is refused at the schema boundary, so no `status` field and no `mutation` block are returned
- [ ] CP6: Nothing was created — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` lists the same objects as the precondition, and names no `ExtraKey`
- [ ] CP7: The sketch is unchanged — verify: `mcp query_sketch_info { doc: <handle>, sketch: "PlateProfile" }` reports the same geometry and constraint lists as before

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```
