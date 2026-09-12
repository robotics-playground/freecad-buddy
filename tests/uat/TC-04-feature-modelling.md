# TC-04: Feature Modelling

Exercises all eleven `feature_*` mutation tools against a live FreeCAD document, plus the four
read tools that grade their result: `query_mass_properties`, `query_object`, `query_placement` and
`verify_shape`. Every solid-producing scenario checks an analytic volume, not only a status code,
because a feature that commits with the wrong dimension still reports `OK`. The mutation protocol
is also under test: a failed feature must roll back with a proven fingerprint and leave no partial
solid, and a recompute that leaves the document invalid must class as `RECOMPUTE_ERROR`, never
`SPEC_FAILED`.

## Prerequisites

- [ ] FreeCAD GUI is open and the addon spawned the proxy (verify: `netstat -ano | grep :8765` shows LISTENING)
- [ ] The MCP tool surface is complete (verify: `mcp query_capabilities {}` lists 44 tools)
- [ ] PartDesign is available on this build (verify: `mcp feature_body_create { doc: <handle>, name: "ProbeBody" }` returns `status=OK`, not `PartDesign is unavailable on this FreeCAD build`)
- [ ] The host runs the operator auto-approve posture, so a mutation needs no `preview_id` (verify: the addon log carries `SECURITY: mutation auto-approve ENABLED by operator flag`)
- [ ] `FREECAD_BUDDY_AUTO_APPROVE=1` was set in the environment that launched FreeCAD (verify: the banner line above is present in `%APPDATA%/FreeCAD/v1-1/freecad-buddy/addon.log`)

**Confirm convention for this file**: every `feature_*` call below is a geometry-intent mutation and
is gated by AD-10. This file runs under the operator auto-approve posture, so no scenario passes a
`confirm` object. The confirm gate's own negative cases belong to TC-08 and are not repeated here.

**Reference part**: the scenarios build one bracket — a 60 x 40 x 5 mm plate, M5 clearance holes on
40 mm spacing, a 2 mm fillet on the corners. Volumes below are the analytic values for that part.

---

### TC-04-01: feature_body_create empty and adopting a base

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (feature tools), `verification-design.md` §5 (verify_shape)

**Preconditions**:
- [ ] A scratch document exists (verify: `mcp document_create { label: "Bracket" }` returns a handle)
- [ ] A loose solid exists for the adoption case (verify: `mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns a handle and `mcp query_mass_properties` reports `volume=6000.0`)

**Steps**:
1. Create an empty Body:
   ```
   mcp feature_body_create { doc: <handle>, name: "PlateBody" }
   ```
2. Create a second Body that adopts the golden box as its base feature:
   ```
   mcp feature_body_create { doc: <boxhandle>, name: "AdoptBody", base_feature: "Box" }
   ```

**Checkpoints**:
- [ ] CP1: The empty Body commits — verify: step 1 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: An empty Body carries no solid — verify: `mcp query_object { doc: <handle>, object: "PlateBody" }` reports no Tip, because a new Body's `Shape` is null until a feature is added
- [ ] CP3: The Body brings its origin — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` shows an `App::Origin` child under `PlateBody` with its plane, line and point children
- [ ] CP4: The adoption commits — verify: step 2 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP5: The adopted Body reports the base volume — verify: `mcp query_mass_properties { doc: <boxhandle>, object: "AdoptBody" }` returns `volume=6000.0` within 0.1 %
- [ ] CP6: The adopted Body is a valid solid — verify: `mcp verify_shape { doc: <boxhandle>, object: "AdoptBody" }` returns `status=OK`
- [ ] CP7: A double adoption is refused — verify: a second `feature_body_create { base_feature: "Box" }` returns `status=INVALID_INPUT` naming `is already adopted by a Body`
- [ ] CP8: A shapeless base is refused — verify: `base_feature` naming a sketch returns `status=INVALID_INPUT` naming `carries no shape to adopt`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
mcp document_close { doc: <boxhandle> }
```

---

### TC-04-02: feature_pad Length with analytic volume

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pad`), `verification-design.md` §5

**Preconditions**:
- [ ] A Body named `BlockBody` exists (verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` names it)
- [ ] A fully constrained 20 x 30 mm rectangle sketch named `BlockProfile` sits inside it (verify: `mcp verify_sketch { doc: <handle>, sketch: "BlockProfile" }` returns `status=OK` with `subject.dof=0`)

**Steps**:
1. Pad the profile 10 mm:
   ```
   mcp feature_pad { doc: <handle>, body: "BlockBody", profile: "BlockProfile",
                     name: "BlockPad", length: { value: 10, unit: "mm" } }
   ```
2. Measure the result.
   ```
   mcp query_mass_properties { doc: <handle>, object: "BlockPad" }
   ```

**Checkpoints**:
- [ ] CP1: The pad commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The volume is analytic — verify: `mcp query_mass_properties { doc: <handle>, object: "BlockPad" }` returns `volume` equal to `6000.0` mm³ (20 x 30 x 10) within 0.1 %
- [ ] CP3: The solid is valid and single — verify: `mcp verify_shape { doc: <handle>, object: "BlockPad" }` returns `status=OK`, and the mutation envelope's `feature_state.shape_summary` reports `solid_count=1` and `is_valid=true`
- [ ] CP4: The bounding box matches — verify: the same `shape_summary` reports `bbox=[20, 30, 10]` within 0.1 %
- [ ] CP5: The face count matches a box — verify: the same `shape_summary` reports `face_count=6`, `edge_count=12`, `vertex_count=8`
- [ ] CP6: The pad became the Body Tip — verify: the same envelope's `feature_state` reports `body="BlockBody"` and `is_tip=true`
- [ ] CP7: `up_to` defaults to Length — verify: `mcp query_object { doc: <handle>, object: "BlockPad" }` reports the extrude `Type` as `Length`, because `up_to` was omitted
- [ ] CP8: The post-verify gate passed every step — verify: the envelope carries `mutation.post_verify.passed=true`, `recompute_clean=true`, `is_valid=true` and `tnp_audit.status=CLEAN`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-03: feature_pad midplane straddles the sketch plane

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pad`, midplane)

**Preconditions**:
- [ ] A Body holds a fully constrained 20 x 30 mm rectangle sketch on XY (verify: `mcp verify_sketch { doc: <handle>, sketch: "BlockProfile" }` returns `subject.dof=0`)
- [ ] A non-midplane 10 mm pad of the same profile was measured for comparison (verify: TC-04-02 CP2 recorded `volume=6000.0` with the solid sitting from z=0 to z=10)

**Steps**:
1. Pad the same profile 10 mm, straddling the sketch plane:
   ```
   mcp feature_pad { doc: <handle>, body: "MidBody", profile: "MidProfile",
                     name: "MidPad", length: { value: 10, unit: "mm" }, midplane: true }
   ```
2. Read the placement and the bounding box.
   ```
   mcp query_mass_properties { doc: <handle>, object: "MidPad" }
   mcp query_placement { doc: <handle>, object: "MidPad" }
   ```

**Checkpoints**:
- [ ] CP1: The midplane pad commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The volume is unchanged — verify: `mcp query_mass_properties { doc: <handle>, object: "MidPad" }` returns `volume=6000.0` within 0.1 %; midplane splits the extent, it does not double it
- [ ] CP3: The extent is still 10 mm — verify: the mutation envelope's `feature_state.shape_summary` reports `bbox=[20, 30, 10]`
- [ ] CP4: The solid is symmetric about the sketch plane — verify: `mcp query_mass_properties { doc: <handle>, object: "MidPad" }` reports a bounding box running from z = -5 mm to z = +5 mm, not 0 to 10
- [ ] CP5: The centre of mass sits on the plane — verify: the same read reports `com.z` equal to `{value: 0, unit: "mm"}` within 0.1 %
- [ ] CP6: The solid is valid — verify: `mcp verify_shape { doc: <handle>, object: "MidPad" }` returns `status=OK`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-04: feature_pad reversed, second_length and taper_angle

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pad` optional fields)

**Preconditions**:
- [ ] Three Bodies each hold an identical fully constrained 20 x 30 mm rectangle sketch on XY (verify: `mcp verify_sketch` returns `subject.dof=0` for each of `RevProfile`, `TwoProfile`, `TaperProfile`)

**Steps**:
1. Pad reversed — the solid grows the other way along the plane normal:
   ```
   mcp feature_pad { doc: <handle>, body: "RevBody", profile: "RevProfile",
                     name: "RevPad", length: { value: 10, unit: "mm" }, reversed: true }
   ```
2. Pad with a second length — material on both sides, independently sized:
   ```
   mcp feature_pad { doc: <handle>, body: "TwoBody", profile: "TwoProfile",
                     name: "TwoPad", length: { value: 10, unit: "mm" },
                     second_length: { value: 4, unit: "mm" } }
   ```
3. Pad with a draft angle:
   ```
   mcp feature_pad { doc: <handle>, body: "TaperBody", profile: "TaperProfile",
                     name: "TaperPad", length: { value: 10, unit: "mm" },
                     taper_angle: { value: 5, unit: "deg" } }
   ```

**Checkpoints**:
- [ ] CP1: All three commit — verify: each envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: `reversed` flips the direction, not the size — verify: `mcp query_mass_properties { doc: <handle>, object: "RevPad" }` returns `volume=6000.0` within 0.1 %, with the bounding box running z = -10 to z = 0
- [ ] CP3: The property was written — verify: `mcp query_object { doc: <handle>, object: "RevPad" }` reports `Reversed=true`
- [ ] CP4: `second_length` adds its own material — verify: `mcp query_mass_properties { doc: <handle>, object: "TwoPad" }` returns a volume larger than `6000.0`, and `mcp query_object { doc: <handle>, object: "TwoPad" }` reports `Length2` as `4 mm`
- [ ] CP5: `taper_angle` changes the side faces — verify: `mcp query_mass_properties { doc: <handle>, object: "TaperPad" }` returns a volume different from `6000.0`, and `mcp query_object { doc: <handle>, object: "TaperPad" }` reports `TaperAngle` as `5 deg`
- [ ] CP6: All three solids are valid — verify: `mcp verify_shape` returns `status=OK` for each of `RevPad`, `TwoPad`, `TaperPad`
- [ ] CP7: A taper outside -90..90 degrees is rejected — verify: `taper_angle: { value: 120, unit: "deg" }` returns `status=INVALID_INPUT` naming `taper_angle must be in` its bound, with no `mutation.snapshot_path`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-05: feature_pocket Length and ThroughAll

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pocket`), `verification-design.md` §5

**Preconditions**:
- [ ] A Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` (verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %)
- [ ] Two fully constrained 10 x 10 mm square sketches sit on the plate's top face, named `SlotProfile` and `ThroughProfile` (verify: `mcp verify_sketch` returns `subject.dof=0` for both)

**Steps**:
1. Cut a 2 mm deep pocket:
   ```
   mcp feature_pocket { doc: <handle>, body: "PlateBody", profile: "SlotProfile",
                        name: "SlotPocket", length: { value: 2, unit: "mm" } }
   ```
2. Cut a second pocket right through the plate:
   ```
   mcp feature_pocket { doc: <handle>, body: "PlateBody", profile: "ThroughProfile",
                        name: "ThroughPocket", up_to: "ThroughAll" }
   ```

**Checkpoints**:
- [ ] CP1: The length-driven pocket commits — verify: step 1 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The volume falls by the analytic amount — verify: `mcp query_mass_properties { doc: <handle>, object: "SlotPocket" }` returns `volume=11800.0` (12000 - 10 x 10 x 2) within 0.1 %
- [ ] CP3: The ThroughAll pocket commits — verify: step 2 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP4: ThroughAll cuts the full thickness — verify: `mcp query_mass_properties { doc: <handle>, object: "ThroughPocket" }` returns `volume=11300.0` (11800 - 10 x 10 x 5) within 0.1 %
- [ ] CP5: The through cut made a hole, not a dent — verify: the mutation envelope's `feature_state.shape_summary` reports a `face_count` higher than the plate's 6 and `solid_count=1`
- [ ] CP6: Both solids are valid — verify: `mcp verify_shape { doc: <handle>, object: "ThroughPocket" }` returns `status=OK`
- [ ] CP7: `ThroughAll` is checked against the live Pocket enum — verify: `mcp query_object { doc: <handle>, object: "ThroughPocket" }` reports `Type=ThroughAll`; the same value on a `feature_pad` is refused, because Pad carries a different member at that position
- [ ] CP8: A ThroughAll pocket needs no length — verify: step 2 supplied no `length` and was not refused; only a length-driven type requires one

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-06: feature_revolve about the sketch V_Axis

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_revolve`), `verification-design.md` §5

**Preconditions**:
- [ ] A Body holds a fully constrained rectangle sketch named `ShaftProfile` on XZ, running x = 0..5 mm and z = 0..20 mm (verify: `mcp verify_sketch { doc: <handle>, sketch: "ShaftProfile" }` returns `subject.dof=0`)

**Steps**:
1. Revolve the profile a full turn about the sketch's own vertical axis:
   ```
   mcp feature_revolve { doc: <handle>, body: "ShaftBody", profile: "ShaftProfile",
                         name: "ShaftRev",
                         axis: { kind: "mapped_name", object: "ShaftProfile",
                                 mapped_name: "V_Axis" },
                         angle: { value: 360, unit: "deg" } }
   ```
2. Measure the cylinder.
   ```
   mcp query_mass_properties { doc: <handle>, object: "ShaftRev" }
   ```

**Checkpoints**:
- [ ] CP1: The revolution commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The volume matches the golden cylinder — verify: `mcp query_mass_properties { doc: <handle>, object: "ShaftRev" }` returns `volume=1570.7963` mm³ (r=5, h=20) within 0.1 %, the same value as `benchmarks/g0/golden-models/cylinder-r5-h20.FCStd`
- [ ] CP3: The solid is a closed cylinder — verify: the mutation envelope's `feature_state.shape_summary` reports `solid_count=1`, `face_count=3` and `is_valid=true`
- [ ] CP4: `ReferenceAxis` was written — verify: `mcp query_object { doc: <handle>, object: "ShaftRev" }` names `ShaftProfile` and `V_Axis` as the reference axis
- [ ] CP5: The solid verifies — verify: `mcp verify_shape { doc: <handle>, object: "ShaftRev" }` returns `status=OK`
- [ ] CP6: A non-axis subelement on the profile is rejected — verify: `mapped_name: "Edge1"` on the profile sketch returns `status=INVALID_INPUT` naming `axis on the profile sketch must be one of ['H_Axis', 'N_Axis', 'V_Axis']`
- [ ] CP7: An angle above 360 degrees is rejected — verify: `angle: { value: 400, unit: "deg" }` returns `status=INVALID_INPUT` with no `mutation.snapshot_path`
- [ ] CP8: `second_angle` without the two-angle type is rejected — verify: supplying `second_angle` while `up_to` is omitted returns `status=INVALID_INPUT` naming `second_angle is only read when up_to='TwoAngles'`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-07: feature_hole subtracts the correct volume

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_hole`), `verification-design.md` §5

**Preconditions**:
- [ ] A Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` (verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %)
- [ ] A fully constrained sketch named `HoleProfile` holds one point on the plate's top face at the M5 hole position (verify: `mcp verify_sketch { doc: <handle>, sketch: "HoleProfile" }` returns `subject.dof=0`)

**Steps**:
1. Drill an M5 clearance hole, 5.5 mm diameter, 3 mm deep:
   ```
   mcp feature_hole { doc: <handle>, body: "PlateBody", profile: "HoleProfile",
                      name: "ClearanceHole",
                      diameter: { value: 5.5, unit: "mm" },
                      depth: { value: 3, unit: "mm" } }
   ```
2. Measure the result.
   ```
   mcp query_mass_properties { doc: <handle>, object: "ClearanceHole" }
   ```

**Checkpoints**:
- [ ] CP1: The hole commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The volume falls by the bore — verify: `mcp query_mass_properties { doc: <handle>, object: "ClearanceHole" }` returns `volume=11928.7` mm³ (12000 - pi x 2.75² x 3) within 0.1 %
- [ ] CP3: `depth_type` defaults to Dimension — verify: `mcp query_object { doc: <handle>, object: "ClearanceHole" }` reports `DepthType=Dimension`, because `depth_type` was omitted
- [ ] CP4: The hole is a blind bore, not a through cut — verify: the mutation envelope's `feature_state.shape_summary` reports `solid_count=1` and a `face_count` higher than the plate's 6
- [ ] CP5: The solid verifies — verify: `mcp verify_shape { doc: <handle>, object: "ClearanceHole" }` returns `status=OK`
- [ ] CP6: A Dimension hole without a depth is rejected — verify: omitting `depth` returns `status=INVALID_INPUT` naming `depth_type='Dimension' is depth-driven; 'depth' is required`
- [ ] CP7: ThroughAll cuts the full thickness — verify: `depth_type: "ThroughAll"` with no `depth` returns `status=OK` and a volume of `11881.2` mm³ (12000 - pi x 2.75² x 5) within 0.1 %
- [ ] CP8: A zero diameter is rejected — verify: `diameter: { value: 0, unit: "mm" }` returns `status=INVALID_INPUT` naming `diameter must be positive`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-08: feature_hole thread_type before cut_type

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_hole` ordering)

**Preconditions**:
- [ ] A Body holds a 60 x 40 x 5 mm plate pad and a point sketch for the hole (verify: `mcp verify_sketch { doc: <handle>, sketch: "ThreadProfile" }` returns `subject.dof=0`)
- [ ] The build's `ThreadType` and `HoleCutType` enumerations are known (verify: `mcp query_object { doc: <handle>, object: <an existing Hole> }` lists their legal members, or create one plain hole first and read them)

**Steps**:
1. Drill a threaded hole with a counterbore, naming both enumerations in one call. `thread_type` is
   applied first because FreeCAD re-populates the legal `cut_type` set from it:
   ```
   mcp feature_hole { doc: <handle>, body: "PlateBody", profile: "ThreadProfile",
                      name: "ThreadedHole",
                      thread_type: "ISOMetricProfile", cut_type: "Counterbore",
                      depth: { value: 4, unit: "mm" } }
   ```
2. Read back both properties.
   ```
   mcp query_object { doc: <handle>, object: "ThreadedHole" }
   ```

**Checkpoints**:
- [ ] CP1: The threaded hole commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: Both enumerated values survived the write order — verify: `mcp query_object { doc: <handle>, object: "ThreadedHole" }` reports the requested `ThreadType` and the requested `HoleCutType`, so the thread write did not clear the cut type
- [ ] CP3: A threading type sets `Threaded` — verify: the same read reports `Threaded=true`
- [ ] CP4: `diameter` with a threading type is rejected — verify: adding `diameter: { value: 5, unit: "mm" }` returns `status=INVALID_INPUT` naming `'diameter' cannot be combined with thread_type=`, because FreeCAD sizes a threaded hole from its ThreadSize table
- [ ] CP5: A cut type illegal for that thread is rejected — verify: a `cut_type` outside the set the chosen `thread_type` re-populates returns `status=INVALID_INPUT` naming `is not one of`
- [ ] CP6: An unknown thread type is rejected pre-transaction — verify: `thread_type: "ISOMetricFake"` returns `status=INVALID_INPUT` with no `mutation.snapshot_path`
- [ ] CP7: The solid verifies — verify: `mcp verify_shape { doc: <handle>, object: "ThreadedHole" }` returns `status=OK`

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

**Preconditions**:
- [ ] A Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` (verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %)
- [ ] The four vertical corner edge names are known (verify: `mcp query_object { doc: <handle>, object: "PlatePad" }` lists the edge names)

**Steps**:
1. Fillet the four corners with a 2 mm radius:
   ```
   mcp feature_fillet { doc: <handle>, body: "PlateBody", base: "PlatePad",
                        name: "CornerFillet",
                        edges: [ { kind: "mapped_name", object: "PlatePad", mapped_name: "Edge1" },
                                 { kind: "mapped_name", object: "PlatePad", mapped_name: "Edge3" },
                                 { kind: "mapped_name", object: "PlatePad", mapped_name: "Edge5" },
                                 { kind: "mapped_name", object: "PlatePad", mapped_name: "Edge7" } ],
                        radius: { value: 2, unit: "mm" } }
   ```

**Checkpoints**:
- [ ] CP1: The fillet commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The volume falls by the corner material — verify: `mcp query_mass_properties { doc: <handle>, object: "CornerFillet" }` returns `volume=11982.8` mm³ — 12000 minus 4 x (4 - pi) x 5 for the removed corner prisms — within 0.1 %
- [ ] CP3: Every requested edge was dressed — verify: the mutation envelope's `feature_state.shape_summary` reports `face_count=10`, which is the plate's 6 plus one new face per filleted edge
- [ ] CP4: The solid is valid and single — verify: the same `shape_summary` reports `solid_count=1` and `is_valid=true`, and `mcp verify_shape { doc: <handle>, object: "CornerFillet" }` returns `status=OK`
- [ ] CP5: The surface area rises — verify: `mcp query_mass_properties { doc: <handle>, object: "CornerFillet" }` reports an `area` consistent with four 2 mm quarter-cylinder faces replacing four sharp corners
- [ ] CP6: A base outside the Body is rejected — verify: `base` naming a feature in a different Body returns `status=INVALID_INPUT` naming `is not in Body`
- [ ] CP7: An edge naming a different object than the base is rejected — verify: an `edges` entry whose `object` is not the base returns `status=INVALID_INPUT` naming `not the dress-up base`
- [ ] CP8: A repeated edge is rejected — verify: listing `Edge1` twice returns `status=INVALID_INPUT` naming `repeats Edge1`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-10: feature_chamfer sizes, angle and chamfer_type

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_chamfer`)

**Preconditions**:
- [ ] A Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` (verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %)
- [ ] The build's `ChamferType` enumeration is known (verify: read it from a chamfer created with defaults, or from `mcp query_object` on an existing chamfer)

**Steps**:
1. Chamfer one edge with an equal-distance chamfer:
   ```
   mcp feature_chamfer { doc: <handle>, body: "PlateBody", base: "PlatePad",
                         name: "EqualChamfer",
                         edges: [ { kind: "mapped_name", object: "PlatePad",
                                    mapped_name: "Edge1" } ],
                         size: { value: 1.5, unit: "mm" } }
   ```
2. Chamfer a second edge with two distances, naming the build's two-distance type:
   ```
   mcp feature_chamfer { doc: <handle>, body: "PlateBody", base: "EqualChamfer",
                         name: "TwoSizeChamfer",
                         edges: [ { kind: "mapped_name", object: "EqualChamfer",
                                    mapped_name: "Edge3" } ],
                         chamfer_type: "Two distances",
                         size: { value: 2, unit: "mm" },
                         second_size: { value: 1, unit: "mm" } }
   ```
3. Chamfer a third edge with a distance and an angle:
   ```
   mcp feature_chamfer { doc: <handle>, body: "PlateBody", base: "TwoSizeChamfer",
                         name: "AngleChamfer",
                         edges: [ { kind: "mapped_name", object: "TwoSizeChamfer",
                                    mapped_name: "Edge5" } ],
                         chamfer_type: "Distance and angle",
                         size: { value: 2, unit: "mm" },
                         angle: { value: 30, unit: "deg" } }
   ```

**Checkpoints**:
- [ ] CP1: All three chamfers commit — verify: each envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The equal chamfer removes the analytic wedge — verify: `mcp query_mass_properties { doc: <handle>, object: "EqualChamfer" }` returns `volume=11994.4` mm³ (12000 - 0.5 x 1.5² x 5) within 0.1 %
- [ ] CP3: Each chamfer adds exactly one face — verify: each mutation envelope's `feature_state.shape_summary` reports `face_count` one higher than its base feature's
- [ ] CP4: `chamfer_type` is checked against the live enum — verify: `chamfer_type: "Bevel"` returns `status=INVALID_INPUT` naming `chamfer_type 'Bevel' is not one of` followed by the build's members
- [ ] CP5: The angle bound is enforced — verify: `angle: { value: 200, unit: "deg" }` returns `status=INVALID_INPUT` naming `angle must be in` its bound
- [ ] CP6: A zero size is rejected — verify: `size: { value: 0, unit: "mm" }` returns `status=INVALID_INPUT` naming `size must be positive`
- [ ] CP7: Every solid is valid — verify: `mcp verify_shape { doc: <handle>, object: "AngleChamfer" }` returns `status=OK` with `solid_count=1`

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

**Preconditions**:
- [ ] A Body holds a 60 x 40 x 5 mm plate pad and one M5 clearance hole named `ClearanceHole` (verify: `mcp query_mass_properties { doc: <handle>, object: "ClearanceHole" }` returns `volume=11881.2` for a through hole within 0.1 %)
- [ ] A second Body holds a disc pad and one hole for the polar case (verify: `mcp verify_shape { doc: <handle>, object: "DiscHole" }` returns `status=OK`)

**Steps**:
1. Repeat the hole twice along the plate's X axis on 40 mm spacing. `occurrences` counts the
   original, so 2 is the original plus one copy:
   ```
   mcp feature_pattern { doc: <handle>, body: "PlateBody", name: "HoleRow", kind: "linear",
                         originals: ["ClearanceHole"],
                         direction: { kind: "mapped_name", object: "PlateProfile",
                                      mapped_name: "H_Axis" },
                         length: { value: 40, unit: "mm" }, occurrences: 2 }
   ```
2. Repeat a hole six times around the disc's normal axis:
   ```
   mcp feature_pattern { doc: <handle>, body: "DiscBody", name: "HoleRing", kind: "polar",
                         originals: ["DiscHole"],
                         axis: { kind: "mapped_name", object: "DiscProfile",
                                 mapped_name: "N_Axis" },
                         angle: { value: 360, unit: "deg" }, occurrences: 6 }
   ```

**Checkpoints**:
- [ ] CP1: The linear pattern commits — verify: step 1 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: `occurrences` counts the original — verify: `mcp query_mass_properties { doc: <handle>, object: "HoleRow" }` returns `volume=11762.4` mm³ — the plate minus exactly two bores of pi x 2.75² x 5 — within 0.1 %, proving 2 holes total, not 3
- [ ] CP3: The spacing is the requested length — verify: the mutation envelope's `feature_state.shape_summary` bbox is unchanged from the plate's `[60, 40, 5]`, so both holes fall inside the plate at 40 mm apart
- [ ] CP4: The polar pattern commits — verify: step 2 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP5: A full turn steps by angle/occurrences — verify: `mcp query_mass_properties { doc: <handle>, object: "HoleRing" }` shows exactly 6 bores removed, so the copies land 60 degrees apart, not 72
- [ ] CP6: Both solids are valid — verify: `mcp verify_shape` returns `status=OK` for `HoleRow` and `HoleRing`
- [ ] CP7: `originals` defaults to the Body Tip — verify: omitting `originals` on an equivalent call returns `status=OK` and patterns the Tip feature
- [ ] CP8: A kind outside the enum is a schema reject — verify: `kind: "mirror"` is refused against the enum `["linear","polar"]`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-12: feature_mirror across datum, base plane and face

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_mirror`), `verification-design.md` §5

**Preconditions**:
- [ ] A Body holds a 20 x 30 x 10 mm pad named `HalfPad` sitting entirely on one side of the YZ plane, so its mirror does not overlap it (verify: `mcp query_mass_properties { doc: <handle>, object: "HalfPad" }` returns `volume=6000.0` and a bounding box with `x` running 5..25 mm)
- [ ] A datum plane named `MirrorPlane` exists in the same Body (verify: `mcp query_placement { doc: <handle>, object: "MirrorPlane" }` returns `status=OK`)

**Steps**:
1. Mirror across the Body origin's YZ base plane:
   ```
   mcp feature_mirror { doc: <handle>, body: "HalfBody", name: "PlaneMirror",
                        mirror_plane: { kind: "mapped_name", object: "YZ_Plane" },
                        originals: ["HalfPad"] }
   ```
2. Mirror across the datum plane:
   ```
   mcp feature_mirror { doc: <handle>, body: "DatumBody", name: "DatumMirror",
                        mirror_plane: { kind: "mapped_name", object: "MirrorPlane" },
                        originals: ["DatumPad"] }
   ```
3. Mirror across a planar face of the solid:
   ```
   mcp feature_mirror { doc: <handle>, body: "FaceBody", name: "FaceMirror",
                        mirror_plane: { kind: "mapped_name", object: "FacePad",
                                        mapped_name: "Face1" },
                        originals: ["FacePad"] }
   ```

**Checkpoints**:
- [ ] CP1: All three mirrors commit — verify: each envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The volume doubles for a non-overlapping original — verify: `mcp query_mass_properties { doc: <handle>, object: "PlaneMirror" }` returns `volume=12000.0` mm³ within 0.1 %
- [ ] CP3: The bounding box spans both halves — verify: the mutation envelope's `feature_state.shape_summary` reports `bbox=[50, 30, 10]`, the original x-extent reflected about x=0
- [ ] CP4: A whole-object selector needs no `mapped_name` — verify: step 1 and step 2 omit `mapped_name` and are accepted, because a datum or base plane is referenced as a whole object
- [ ] CP5: A face selector carries its `mapped_name` — verify: step 3 is accepted with `mapped_name: "Face1"`
- [ ] CP6: Every mirrored solid is valid — verify: `mcp verify_shape` returns `status=OK` with `solid_count=1` for each of `PlaneMirror`, `DatumMirror`, `FaceMirror`
- [ ] CP7: An unknown mirror plane is rejected pre-transaction — verify: `object: "NoSuchPlane"` returns `status=INVALID_INPUT` naming `unknown object in mirror_plane` with no `mutation.snapshot_path`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-13: feature_datum plane, axis, point and cs

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_datum`), `verification-design.md` §3 (attachment references, AD-7)

**Preconditions**:
- [ ] A Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` (verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %)
- [ ] The plate's top face name is known (verify: `mcp query_object { doc: <handle>, object: "PlatePad" }` lists the face names)

**Steps**:
1. Create a datum plane on the top face, offset 10 mm along its local Z. `map_mode` defaults to
   `"FlatFace"`:
   ```
   mcp feature_datum { doc: <handle>, body: "PlateBody", name: "RaisedPlane", kind: "plane",
                       attachment: { kind: "mapped_name", object: "PlatePad",
                                     mapped_name: "Face6" },
                       offset: { value: 10, unit: "mm" } }
   ```
2. Create the other three kinds against their own attachments:
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

**Checkpoints**:
- [ ] CP1: All four kinds commit — verify: each envelope returns `status=OK` with `mutation.rolled_back=false`, covering the enum `["plane","axis","point","cs"]`
- [ ] CP2: The offset moved the plane — verify: `mcp query_placement { doc: <handle>, object: "RaisedPlane" }` reports `position.z` equal to `{value: 15, unit: "mm"}` — the 5 mm face plus the 10 mm offset
- [ ] CP3: `map_mode` defaults to FlatFace — verify: `mcp query_object { doc: <handle>, object: "RaisedPlane" }` reports `MapMode=FlatFace`, because `map_mode` was omitted
- [ ] CP4: `AttachmentSupport` names the target — verify: the same read names `PlatePad` and `Face6` as the attachment support
- [ ] CP5: A datum is not a solid — verify: `mcp query_mass_properties { doc: <handle>, object: "RaisedPlane" }` returns no solid volume; a datum carries no material
- [ ] CP6: The tree carries all four — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists `RaisedPlane`, `EdgeAxis`, `CornerPoint` and `FaceCS` under `PlateBody`
- [ ] CP7: A fifth kind is a schema reject — verify: `kind: "curve"` is refused against the enum `["plane","axis","point","cs"]`
- [ ] CP8: A map_mode the kind cannot use is rejected pre-transaction — verify: a mode the datum kind's attach engine does not implement returns `status=INVALID_INPUT` naming `is not implemented for kind` with no `mutation.snapshot_path`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-14: feature_set_parameters edits a Pad length

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_set_parameters`), `verification-design.md` §1 (mutation protocol)

**Preconditions**:
- [ ] A Body holds a 20 x 30 mm profile padded 10 mm, named `BlockPad` (verify: `mcp query_mass_properties { doc: <handle>, object: "BlockPad" }` returns `volume=6000.0` within 0.1 %)

**Steps**:
1. Change the pad length from 10 mm to 25 mm in one transaction:
   ```
   mcp feature_set_parameters { doc: <handle>, feature: "BlockPad",
                                parameters: { Length: { value: 25, unit: "mm" } } }
   ```
2. Re-measure the solid.
   ```
   mcp query_mass_properties { doc: <handle>, object: "BlockPad" }
   ```

**Checkpoints**:
- [ ] CP1: The edit commits — verify: the envelope returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The volume tracks the new length — verify: `mcp query_mass_properties { doc: <handle>, object: "BlockPad" }` returns `volume=15000.0` mm³ (20 x 30 x 25) within 0.1 %
- [ ] CP3: The property holds the new value — verify: `mcp query_object { doc: <handle>, object: "BlockPad" }` reports `Length` as `25 mm`
- [ ] CP4: The re-verify ran inside the same transaction — verify: the envelope carries `mutation.post_verify.passed=true` with `is_valid=true` and `recompute_clean=true`
- [ ] CP5: The solid is valid — verify: `mcp verify_shape { doc: <handle>, object: "BlockPad" }` returns `status=OK` with a `bbox` of `[20, 30, 25]`
- [ ] CP6: Several properties change together — verify: `parameters: { Length: { value: 12, unit: "mm" }, Reversed: true }` returns `status=OK` and both properties read back changed
- [ ] CP7: A boolean and an enum are accepted — verify: `parameters: { Midplane: true }` and `parameters: { Type: "Length" }` each return `status=OK`
- [ ] CP8: An empty parameters object is rejected — verify: `parameters: {}` returns `status=INVALID_INPUT` naming `feature_set_parameters requires a non-empty 'parameters' object`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-15: feature_pad up_to and up_to_face enums

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pad`, live enum validation)

**Preconditions**:
- [ ] A Body holds a base solid and a fully constrained profile sketch below it, so an up-to extrude has a target (verify: `mcp verify_shape { doc: <handle>, object: "BasePad" }` returns `status=OK` and `mcp verify_sketch { doc: <handle>, sketch: "RiserProfile" }` returns `subject.dof=0`)
- [ ] The target face name on the base solid is known (verify: `mcp query_object { doc: <handle>, object: "BasePad" }` lists the face names)

**Steps**:
1. Pad up to a named face:
   ```
   mcp feature_pad { doc: <handle>, body: "PlateBody", profile: "RiserProfile",
                     name: "RiserPad", up_to: "UpToFace",
                     up_to_face: { kind: "mapped_name", object: "BasePad",
                                   mapped_name: "Face5" } }
   ```
2. Try a value outside the live enumeration:
   ```
   mcp feature_pad { doc: <handle>, body: "PlateBody", profile: "RiserProfile",
                     name: "BadTypePad", up_to: "UpToInfinity" }
   ```

**Checkpoints**:
- [ ] CP1: The up-to pad commits — verify: step 1 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The extrude stopped at the face — verify: the mutation envelope's `feature_state.shape_summary` reports a `bbox` whose z-extent ends at the target face's z, not at an arbitrary length
- [ ] CP3: `UpToFace` needs no length — verify: step 1 supplied no `length` and was not refused; only a length-driven type requires one
- [ ] CP4: `UpToFace` was written — verify: `mcp query_object { doc: <handle>, object: "RiserPad" }` reports `Type=UpToFace` and names `BasePad` with `Face5` as the up-to face
- [ ] CP5: A bad enum value is rejected — verify: step 2 returns `status=INVALID_INPUT` naming `up_to 'UpToInfinity' is not one of` followed by this build's members
- [ ] CP6: The rejection is pre-transaction — verify: the step 2 envelope carries no `mutation.snapshot_path`, and `mcp query_tree_summary { doc: <handle>, depth: 3 }` names no `BadTypePad`
- [ ] CP7: The solid verifies — verify: `mcp verify_shape { doc: <handle>, object: "RiserPad" }` returns `status=OK`

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

**Preconditions**:
- [ ] A Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` (verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %)
- [ ] The temp directory holds no snapshot from a prior run (verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing)

**Steps**:
1. Ask for a fillet radius larger than the plate can carry — 20 mm on a 5 mm thick plate:
   ```
   mcp feature_fillet { doc: <handle>, body: "PlateBody", base: "PlatePad",
                        name: "TooBigFillet",
                        edges: [ { kind: "mapped_name", object: "PlatePad",
                                   mapped_name: "Edge1" } ],
                        radius: { value: 20, unit: "mm" } }
   ```

**Checkpoints**:
- [ ] CP1: The call does not commit — verify: the envelope returns a non-`OK` status: `RECOMPUTE_ERROR` when OCCT reports the failure through the recompute, or `SPEC_FAILED` when the shape grade rejects it
- [ ] CP2: The rollback is proven — verify: the envelope carries `mutation.rolled_back=true`
- [ ] CP3: The failure is explained — verify: `mutation.post_verify.explanation` is non-empty and names the feature and the engine's own status string
- [ ] CP4: No partial solid survives — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` names no `TooBigFillet`
- [ ] CP5: The plate is unchanged — verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` again returns `volume=12000.0` within 0.1 %
- [ ] CP6: The fingerprint proves it — verify: `mutation.fingerprint_before.digest` equals `mutation.fingerprint_after.digest`, or the rollback state is `rolled_back_via_snapshot`
- [ ] CP7: The snapshot was deleted — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing, because a proven rollback removes its snapshot
- [ ] CP8: The document still recomputes clean — verify: `mcp verify_recompute { doc: <handle> }` returns `status=OK`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-17: Fillet on a silently-droppable edge is rejected up front

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_fillet` edge check)

**Preconditions**:
- [ ] A Body holds a solid with at least one edge whose faces meet tangentially — a cylinder's seam edge or the join between a fillet and its flat face (verify: `mcp query_object { doc: <handle>, object: "ShaftRev" }` lists the edge names, and the seam edge is identified)
- [ ] The temp directory holds no snapshot from a prior run (verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing)

**Steps**:
1. Ask for a fillet on the tangential edge:
   ```
   mcp feature_fillet { doc: <handle>, body: "ShaftBody", base: "ShaftRev",
                        name: "DropFillet",
                        edges: [ { kind: "mapped_name", object: "ShaftRev",
                                   mapped_name: "Edge2" } ],
                        radius: { value: 1, unit: "mm" } }
   ```
2. Mix one good edge and one droppable edge in the same call:
   ```
   mcp feature_fillet { doc: <handle>, body: "ShaftBody", base: "ShaftRev",
                        name: "MixedFillet",
                        edges: [ { kind: "mapped_name", object: "ShaftRev",
                                   mapped_name: "Edge1" },
                                 { kind: "mapped_name", object: "ShaftRev",
                                   mapped_name: "Edge2" } ],
                        radius: { value: 1, unit: "mm" } }
   ```

**Checkpoints**:
- [ ] CP1: The droppable edge is refused — verify: step 1 returns `status=INVALID_INPUT` naming `cannot be shown to survive the dress-up` and listing the edge
- [ ] CP2: The reason is stated — verify: the same detail names `each needs exactly two adjacent faces meeting at a measurable crease, and FreeCAD drops the rest without reporting it`
- [ ] CP3: The refusal is pre-transaction — verify: the step 1 envelope carries no `mutation.snapshot_path`, and `ls "$TEMP"/FCB_TMP_snap_*` lists nothing
- [ ] CP4: A mixed request is refused whole — verify: step 2 returns `status=INVALID_INPUT`; the good edge is not filleted on its own
- [ ] CP5: Nothing was created — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` names neither `DropFillet` nor `MixedFillet`
- [ ] CP6: The base solid is untouched — verify: `mcp query_mass_properties { doc: <handle>, object: "ShaftRev" }` returns the same volume as before both steps
- [ ] CP7: A committed dress-up that dressed fewer edges than asked is caught inside the transaction — verify: any such case returns `status=SPEC_FAILED` with `mutation.rolled_back=true` and an explanation naming `dressed N of the M requested edge(s)`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-18: feature_pattern occurrences and conditional requirements

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pattern`, `allOf`/`if`/`then`)

**Preconditions**:
- [ ] A Body holds a plate pad and one hole feature to pattern (verify: `mcp verify_shape { doc: <handle>, object: "ClearanceHole" }` returns `status=OK`)
- [ ] The document object list before the calls is recorded (verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }`)

**Steps**:
1. Ask for one occurrence:
   ```
   mcp feature_pattern { doc: <handle>, body: "PlateBody", name: "OnePattern", kind: "linear",
                         direction: { kind: "mapped_name", object: "PlateProfile",
                                      mapped_name: "H_Axis" },
                         length: { value: 40, unit: "mm" }, occurrences: 1 }
   ```
2. Ask for zero occurrences, then for a linear pattern with no `direction`:
   ```
   mcp feature_pattern { doc: <handle>, body: "PlateBody", name: "ZeroPattern", kind: "linear",
                         direction: { kind: "mapped_name", object: "PlateProfile",
                                      mapped_name: "H_Axis" },
                         length: { value: 40, unit: "mm" }, occurrences: 0 }
   mcp feature_pattern { doc: <handle>, body: "PlateBody", name: "NoDirection", kind: "linear",
                         length: { value: 40, unit: "mm" }, occurrences: 3 }
   ```
3. Ask for a polar pattern with no `axis`:
   ```
   mcp feature_pattern { doc: <handle>, body: "PlateBody", name: "NoAxis", kind: "polar",
                         angle: { value: 360, unit: "deg" }, occurrences: 4 }
   ```

**Checkpoints**:
- [ ] CP1: `occurrences: 1` is a schema reject — verify: step 1 is refused; the schema sets `minimum: 2`
- [ ] CP2: `occurrences: 0` is a schema reject — verify: the first call of step 2 is refused against the same `minimum: 2`
- [ ] CP3: A linear pattern without `direction` is refused — verify: the second call of step 2 is refused by the `if kind == "linear" then required: ["direction"]` branch
- [ ] CP4: A polar pattern without `axis` is refused — verify: step 3 is refused by the `if kind == "polar" then required: ["axis"]` branch
- [ ] CP5: The complementary field is not required — verify: a valid linear call carrying `direction` and no `axis` returns `status=OK`, so the conditional does not demand both
- [ ] CP6: A very large count is refused rather than handed to OCCT — verify: `occurrences: 5000` returns `status=INVALID_INPUT` naming `occurrences must be an integer between 2 and 1000`
- [ ] CP7: Nothing was created — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists the same objects as the precondition, naming no `OnePattern`, `ZeroPattern`, `NoDirection` or `NoAxis`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-19: Zero and negative pad length

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_pad`), `mcp-tools-design.md` §1.4 (quantity fields)

**Preconditions**:
- [ ] A Body holds a fully constrained 20 x 30 mm profile sketch (verify: `mcp verify_sketch { doc: <handle>, sketch: "BlockProfile" }` returns `subject.dof=0`)
- [ ] The temp directory holds no snapshot from a prior run (verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing)

**Steps**:
1. Pad with zero length:
   ```
   mcp feature_pad { doc: <handle>, body: "BlockBody", profile: "BlockProfile",
                     name: "ZeroPad", length: { value: 0, unit: "mm" } }
   ```
2. Pad with a negative length:
   ```
   mcp feature_pad { doc: <handle>, body: "BlockBody", profile: "BlockProfile",
                     name: "NegPad", length: { value: -10, unit: "mm" } }
   ```
3. Pad with a length-driven type and no length at all:
   ```
   mcp feature_pad { doc: <handle>, body: "BlockBody", profile: "BlockProfile",
                     name: "NoLenPad" }
   ```

**Checkpoints**:
- [ ] CP1: Zero is refused — verify: step 1 returns `status=INVALID_INPUT` naming `length must be positive, got 0`
- [ ] CP2: Negative is refused — verify: step 2 returns `status=INVALID_INPUT` naming `length must be positive, got -10`
- [ ] CP3: A missing length on a length-driven type is refused — verify: step 3 returns `status=INVALID_INPUT` naming `up_to='Length' is length-driven; 'length' is required`
- [ ] CP4: Every refusal is pre-transaction — verify: none of the three envelopes carries `mutation.snapshot_path`
- [ ] CP5: No snapshot was written — verify: `ls "$TEMP"/FCB_TMP_snap_*` still lists nothing after all three steps
- [ ] CP6: Nothing was created — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` names no `ZeroPad`, `NegPad` or `NoLenPad`
- [ ] CP7: A non-finite length is refused — verify: a length encoding as infinity returns `status=INVALID_INPUT` naming `must be finite`
- [ ] CP8: The Body still carries no solid — verify: `mcp query_object { doc: <handle>, object: "BlockBody" }` reports no Tip, because no pad was ever created

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-20: Omitted radius and size take FreeCAD's 1 mm default

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §3.7 (`feature_fillet`, `feature_chamfer` defaults)

**Preconditions**:
- [ ] A Body holds a 60 x 40 x 5 mm plate pad named `PlatePad` (verify: `mcp query_mass_properties { doc: <handle>, object: "PlatePad" }` returns `volume=12000.0` within 0.1 %)
- [ ] Two corner edge names are known (verify: `mcp query_object { doc: <handle>, object: "PlatePad" }` lists the edge names)

**Steps**:
1. Fillet one edge with no radius at all:
   ```
   mcp feature_fillet { doc: <handle>, body: "PlateBody", base: "PlatePad",
                        name: "DefaultFillet",
                        edges: [ { kind: "mapped_name", object: "PlatePad",
                                   mapped_name: "Edge1" } ] }
   ```
2. Chamfer another edge with no size at all:
   ```
   mcp feature_chamfer { doc: <handle>, body: "PlateBody", base: "DefaultFillet",
                         name: "DefaultChamfer",
                         edges: [ { kind: "mapped_name", object: "DefaultFillet",
                                    mapped_name: "Edge3" } ] }
   ```

**Checkpoints**:
- [ ] CP1: The fillet commits without a radius — verify: step 1 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP2: The radius is FreeCAD's own 1 mm — verify: `mcp query_object { doc: <handle>, object: "DefaultFillet" }` reports `Radius` as `1 mm`
- [ ] CP3: The volume matches a 1 mm fillet — verify: `mcp query_mass_properties { doc: <handle>, object: "DefaultFillet" }` returns `volume=11998.9` mm³ — 12000 minus (1 - pi/4) x 1² x 5 — within 0.1 %
- [ ] CP4: The chamfer commits without a size — verify: step 2 returns `status=OK` with `mutation.rolled_back=false`
- [ ] CP5: The chamfer size is FreeCAD's own 1 mm — verify: `mcp query_object { doc: <handle>, object: "DefaultChamfer" }` reports `Size` as `1 mm`
- [ ] CP6: Both solids are valid — verify: `mcp verify_shape { doc: <handle>, object: "DefaultChamfer" }` returns `status=OK` with `solid_count=1`

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

**Preconditions**:
- [ ] A Body holds a 20 x 30 x 10 mm pad named `BlockPad` (verify: `mcp query_mass_properties { doc: <handle>, object: "BlockPad" }` returns `volume=6000.0` within 0.1 %)
- [ ] The temp directory holds no snapshot from a prior run (verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing)

**Steps**:
1. Name a property the feature does not carry:
   ```
   mcp feature_set_parameters { doc: <handle>, feature: "BlockPad",
                                parameters: { Thickness: { value: 3, unit: "mm" } } }
   ```
2. Name a property FreeCAD marks read-only — a revolution's computed `Base` or a pad's `Shape`:
   ```
   mcp feature_set_parameters { doc: <handle>, feature: "BlockPad",
                                parameters: { Shape: 1 } }
   ```
3. Send the wrong unit for a length property:
   ```
   mcp feature_set_parameters { doc: <handle>, feature: "BlockPad",
                                parameters: { Length: { value: 25, unit: "deg" } } }
   ```
4. Send a value of an unsupported type:
   ```
   mcp feature_set_parameters { doc: <handle>, feature: "BlockPad",
                                parameters: { Length: [25] } }
   ```

**Checkpoints**:
- [ ] CP1: An unknown property is refused — verify: step 1 returns `status=INVALID_INPUT` naming `BlockPad has no property named 'Thickness'`
- [ ] CP2: A read-only property is refused — verify: step 2 returns `status=INVALID_INPUT` naming `BlockPad.Shape is read-only`
- [ ] CP3: A wrong unit is refused — verify: step 3 returns `status=INVALID_INPUT` naming `Length value unit must be one of ['mm'], got 'deg'`
- [ ] CP4: An unsupported value type is refused — verify: step 4 returns `status=INVALID_INPUT` naming `Length value must be a quantity, number, boolean or enum string`
- [ ] CP5: Every refusal is pre-transaction — verify: none of the four envelopes carries `mutation.snapshot_path`
- [ ] CP6: No snapshot was written — verify: `ls "$TEMP"/FCB_TMP_snap_*` still lists nothing after all four steps
- [ ] CP7: The feature is unchanged — verify: `mcp query_mass_properties { doc: <handle>, object: "BlockPad" }` again returns `volume=6000.0` within 0.1 %
- [ ] CP8: A whole batch is refused when one entry is bad — verify: `parameters: { Length: { value: 12, unit: "mm" }, Thickness: 3 }` returns `status=INVALID_INPUT` and `Length` reads back unchanged at `10 mm`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-22: Feature on a nonexistent Body, profile or base

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §1.3 (error surface, AD-17), `mcp-tools-design.md` §3.7

**Preconditions**:
- [ ] A document holds exactly one Body named `PlateBody`, one sketch named `PlateProfile` and one pad named `PlatePad` (verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists them)
- [ ] The temp directory holds no snapshot from a prior run (verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing)

**Steps**:
1. Name a Body that does not exist:
   ```
   mcp feature_pad { doc: <handle>, body: "NoSuchBody", profile: "PlateProfile",
                     name: "OrphanPad", length: { value: 5, unit: "mm" } }
   ```
2. Name a profile that does not exist:
   ```
   mcp feature_pad { doc: <handle>, body: "PlateBody", profile: "NoSuchSketch",
                     name: "OrphanPad", length: { value: 5, unit: "mm" } }
   ```
3. Name a dress-up base that does not exist:
   ```
   mcp feature_fillet { doc: <handle>, body: "PlateBody", base: "NoSuchPad",
                        name: "OrphanFillet",
                        edges: [ { kind: "mapped_name", object: "NoSuchPad",
                                   mapped_name: "Edge1" } ] }
   ```
4. Name an object that exists but is the wrong type:
   ```
   mcp feature_pad { doc: <handle>, body: "PlateProfile", profile: "PlateProfile",
                     name: "WrongTypePad", length: { value: 5, unit: "mm" } }
   ```

**Checkpoints**:
- [ ] CP1: An unknown Body is `INVALID_INPUT` — verify: step 1 returns `status=INVALID_INPUT` naming `unknown object in body: NoSuchBody`
- [ ] CP2: An unknown profile is `INVALID_INPUT` — verify: step 2 returns `status=INVALID_INPUT` naming `unknown object in profile: NoSuchSketch`
- [ ] CP3: An unknown dress-up base is `INVALID_INPUT` — verify: step 3 returns `status=INVALID_INPUT` naming `unknown object in base: NoSuchPad`
- [ ] CP4: A wrong-typed Body is `INVALID_INPUT` — verify: step 4 returns `status=INVALID_INPUT` naming `object is not a PartDesign Body: PlateProfile`
- [ ] CP5: Nothing was created — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists the same objects as the precondition, naming no `OrphanPad`, `OrphanFillet` or `WrongTypePad`
- [ ] CP6: No transaction opened — verify: none of the four envelopes carries `mutation.snapshot_path`
- [ ] CP7: No snapshot was written — verify: `ls "$TEMP"/FCB_TMP_snap_*` still lists nothing after all four steps
- [ ] CP8: A taken name is also refused — verify: `name: "PlatePad"` on a fresh pad returns `status=INVALID_INPUT` naming `an object named PlatePad already exists`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-23: Padding an under-constrained sketch rolls back

**Priority**: Critical
**Design Ref**: `verification-design.md` §4 (AD-8), `verification-design.md` §1.3 (`post_verify` composition)

**Preconditions**:
- [ ] A Body holds a sketch that is deliberately under-constrained: a rectangle whose position is not pinned to the origin (verify: `mcp verify_sketch { doc: <handle>, sketch: "LooseProfile" }` returns a non-`OK` status with `subject.dof` greater than 0)
- [ ] The temp directory holds no snapshot from a prior run (verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing)

**Steps**:
1. Pad the under-constrained sketch:
   ```
   mcp feature_pad { doc: <handle>, body: "LooseBody", profile: "LooseProfile",
                     name: "LoosePad", length: { value: 10, unit: "mm" } }
   ```

**Checkpoints**:
- [ ] CP1: The pad does not commit — verify: the envelope returns `status=SPEC_FAILED`, not `OK`
- [ ] CP2: The rollback is proven — verify: the envelope carries `mutation.rolled_back=true` and `mutation.post_verify.passed=false`
- [ ] CP3: The cause names the sketch and its dof — verify: `mutation.post_verify.explanation` starts `verify_sketch failed on LooseProfile (dof=` with a non-zero dof
- [ ] CP4: The shape check passed before the sketch check failed — verify: the same block carries `recompute_clean=true`, `is_valid=true` and `fully_constrained=false`, so the failure is the AD-8 step, not the solid
- [ ] CP5: No partial solid survives — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` names no `LoosePad`
- [ ] CP6: The Body carries no Tip — verify: `mcp query_object { doc: <handle>, object: "LooseBody" }` reports no Tip feature
- [ ] CP7: The fingerprint proves the rollback — verify: `mutation.fingerprint_before.digest` equals `mutation.fingerprint_after.digest`, or the rollback state is `rolled_back_via_snapshot`
- [ ] CP8: The snapshot was deleted — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-04-24: A failed recompute is RECOMPUTE_ERROR, not SPEC_FAILED

**Priority**: Critical
**Design Ref**: `verification-design.md` §1.3 (`post_verify` composition, status mapping), `mcp-tools-design.md` §1.3 (closed status set)

**Preconditions**:
- [ ] A Body holds a chain of features where one can be driven into an engine failure — a pocket deeper than the material, or a fillet whose radius consumes its face (verify: `mcp verify_recompute { doc: <handle> }` returns `status=OK` before the call)
- [ ] The temp directory holds no snapshot from a prior run (verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing)

**Steps**:
1. Drive an existing feature into a state the engine cannot build. Set a pocket length far beyond
   the solid, so the recompute leaves the feature in an error state:
   ```
   mcp feature_set_parameters { doc: <handle>, feature: "SlotPocket",
                                parameters: { Length: { value: 500, unit: "mm" } } }
   ```
2. Read the document's recompute health afterwards.
   ```
   mcp verify_recompute { doc: <handle> }
   ```

**Checkpoints**:
- [ ] CP1: The status is `RECOMPUTE_ERROR` — verify: the envelope returns `status=RECOMPUTE_ERROR`, never `SPEC_FAILED`; only a recompute that left an object invalid maps to that value
- [ ] CP2: The recompute flag is false — verify: the envelope carries `mutation.post_verify.recompute_clean=false`
- [ ] CP3: The later checks were not measured — verify: the same block carries `is_valid` and `fully_constrained` as not-measured, because the checklist short-circuits at the first hard failure
- [ ] CP4: The engine's own message is quoted — verify: `mutation.post_verify.explanation` starts `recompute left` and names the object with its `getStatusString()` text
- [ ] CP5: The rollback is proven — verify: the envelope carries `mutation.rolled_back=true`
- [ ] CP6: The old value is restored — verify: `mcp query_object { doc: <handle>, object: "SlotPocket" }` reports the original `Length`, not `500 mm`
- [ ] CP7: The document recomputes clean again — verify: `mcp verify_recompute { doc: <handle> }` returns `status=OK` with no failing checks
- [ ] CP8: The snapshot was deleted — verify: `ls "$TEMP"/FCB_TMP_snap_*` lists nothing, because a proven rollback removes its snapshot

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```
