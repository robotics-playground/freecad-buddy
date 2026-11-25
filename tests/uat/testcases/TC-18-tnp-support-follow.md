# TC-18: TNP audit accepts a reference that rides its moved support

Proves epic decision 40 (decision note 017) in the live GUI. A datum attached to a Pad face keeps
its reference when a driving value moves that face: the typed edit commits, and the TNP audit
(the reference check that runs after every typed mutation) stays `CLEAN`. A real re-point, and a
move the support box does not explain, still grade `REPOINTED`. The envelope is a claim of the code
under test. The datum position is read back with `script_exec` (FreeCAD's own `Placement`), and the
FreeCAD window is captured with `cua-driver` and read by the agent.

**Host**: GUI through the H2 proxy in `fcb-desktop`. `script_exec` is on (the default).

Each scenario builds its own document with the same base part, called **the block** below:

```
mcp document_create { label: <scenario label> }
mcp feature_body_create { doc: <handle>, name: "Body" }
mcp sketch_create { doc: <handle>, name: "Profile", plane: "XY", body: "Body" }
mcp sketch_add_geometry { doc: <handle>, sketch: "Profile",
  geometry: 4 line_segment (0,0)-(20,0), (20,0)-(20,10), (20,10)-(0,10), (0,10)-(0,0),
  constraints: 4 Coincident corners, Horizontal 0 and 2, Vertical 1 and 3,
               Coincident (0,start) with root (-1,start),
               DistanceX 0/start-0/end 20 mm name "Width", DistanceY 1/start-1/end 10 mm name "Depth" }
mcp feature_pad { doc: <handle>, body: "Body", profile: "Profile", name: "Block", length: 10 mm }
```

A face is named by reading it back, not by a fixed index — verify: `mcp script_exec` with
`faces = doc.getObject('Block').Shape.Faces` and a filter on `f.BoundBox` returns one name. The
exact call list is `tests/uat/run/13-15-r1/evidence/tc18.py` (scenario functions `s01` .. `s04b`).

## Preconditions

- [ ] The installed addon is the image's copy of the code under test (verify: `docker exec -u cua fcb-desktop sha256sum /home/cua/.local/share/FreeCAD/v1-1/Mod/FreeCADBuddy/freecad_buddy/usecases/tnp_guard.py` equals `sha256sum $PROJECT_ROOT/src/freecad_buddy/usecases/tnp_guard.py` after `scripts/build_addon.py --release` and `docker compose ... up -d --build`)
- [ ] No document is open in the GUI (verify: `mcp document_list` returns no document)
- [ ] `cua-driver` sees the FreeCAD window (verify: `echo '{"pid":<pid>,"window_id":<wid>,"include_screenshot":false}' | "$FCB_CUA" get_window_state` shows `element_count` above 1)

---

### TC-18-01: A Pad Length edit moves the face; the attached datum follows and the edit commits

**Priority**: Critical
**Design Ref**: `verification-design.md` §3.2 Layer 1; decision 017; epic decision 40; quality bar Q1, Q11

**Given** the block in a new document `tc18_01_pad_length`  
**And** a datum plane on the top face — verify: the face read back at `ZMin = ZMax = 10` is one name (`Face6` on FreeCAD 1.1.4), and `mcp feature_datum { doc: <handle>, body: "Body", name: "TopDatum", kind: "plane", map_mode: "FlatFace", attachment: { kind: "mapped_name", object: "Block", mapped_name: "<top face>" } }` returns `OK` with `tnp_audit.status` `CLEAN`  
**And** the datum sits on the face — verify: `mcp script_exec { code: "result = doc.getObject('TopDatum').Placement.Base.z" }` returns `10.0`  

**When** the Pad grows  
```
mcp feature_set_parameters { doc: <handle>, feature: "Block", parameters: { Length: { value: 15, unit: "mm" } } }
```

**Then** the edit commits — verify: `status` is `OK`, `mutation.rolled_back` is `false`  
**And** the TNP audit is clean — verify: `mutation.post_verify.tnp_audit.status` is `CLEAN`, `counts` holds no `REPOINTED`, `BROKEN` or `DROPPED`, and `findings` is empty  
**And** the datum followed the face — verify: `mcp script_exec { code: "d = doc.getObject('TopDatum')\nresult = (round(d.Placement.Base.z, 6), d.AttachmentSupport[0][1], [o.Name for o in doc.Objects if not o.isValid()])" }` returns `(15.0, ('<top face>',), [])`  
**And** the audit log agrees — verify: the last `feature_set_parameters` line for this handle in `/home/cua/.local/share/FreeCAD/v1-1/freecad-buddy/audit.jsonl` (read with `docker exec -u cua fcb-desktop cat ...`) has `verify_verdict` `OK` and `rollback.rolled_back` `false`  
**And** *(visual)* the datum lies on the top of the taller block — verify: `mcp view_fit_viewport { doc: <handle> }`, then `echo '{"pid":<pid>,"window_id":<wid>,"x":900,"y":500,"key":"1"}' | "$FCB_CUA" press_key` (front view), then `echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-18-01-after-front.png"}' | "$FCB_CUA" get_window_state`, and `Read` the PNG. The block outline is 20 wide by 15 tall (ratio about 1.33) and the datum line runs along its top edge. A datum line inside the block or above it is a finding  

**Cleanup**: `mcp document_close { doc: <handle> }`

---

### TC-18-02: A sketch width edit moves a side face; datums on the side and top faces follow

**Priority**: Critical
**Design Ref**: `verification-design.md` §3.2 Layer 1; decision 017; quality bar Q2

**Given** the block in a new document `tc18_02_sketch_width`  
**And** `TopDatum` on the face at `Z = 10` and `SideDatum` on the face at `XMin = XMax = 20` (both `kind: "plane"`, `map_mode: "FlatFace"`) — verify: each `feature_datum` returns `OK` with `tnp_audit.status` `CLEAN`  

**When** the sketch width changes  
```
mcp sketch_set_datum { doc: <handle>, sketch: "Profile", constraint: "Width", value: { value: 30, unit: "mm" } }
```

**Then** the edit commits — verify: `status` is `OK`, `mutation.rolled_back` is `false`, `tnp_audit.status` is `CLEAN` with no `REPOINTED` in `counts`  
**And** both datums sit where their faces are — verify: `mcp script_exec { code: "t, s = doc.getObject('TopDatum'), doc.getObject('SideDatum')\nresult = (round(t.Placement.Base.z, 6), round(s.Placement.Base.x, 6), round(doc.getObject('Block').Shape.BoundBox.XMax, 6), [o.Name for o in doc.Objects if not o.isValid()])" }` returns `(10.0, 30.0, 30.0, [])`  

**Cleanup**: `mcp document_close { doc: <handle> }`

---

### TC-18-03: A real re-point, a witness tamper and a move the support does not explain still grade REPOINTED

**Priority**: Critical
**Design Ref**: `verification-design.md` §3.2 Layer 1; decision 017 "Accepted residual"; quality bar Q4, Q5, Q6

Four independent sub-scenarios, each in its own document with the block and `TopDatum` on the top face
(03c uses an axis on an edge instead).

**03a — planted re-point.** **Given** `tc18_03a_planted_repoint` with `TopDatum` on the top face  
**When** the guard runs in FreeCAD around a re-attach that no op wrote  
```
mcp script_exec { code: "from freecad_buddy.usecases import tnp_guard\nd = doc.getObject('TopDatum')\nsnap = tnp_guard.snapshot_references(doc)\nd.AttachmentSupport = [(doc.getObject('Block'), ('<bottom face>',))]\ndoc.recompute()\naudit = tnp_guard.audit_references(doc, snap)\nresult = (audit['status'], [(f['owner'], f['verdict'], f['layer']) for f in audit['findings'] if f['owner'] == 'TopDatum'])" }
```
**Then** verify: `result` is `('FLAGGED', [('TopDatum', 'REPOINTED', 1)])` and the detail says the entry "now maps to a different element"  
**And** the guard that ran is the installed copy — verify: `mcp script_exec { code: "from freecad_buddy.usecases import tnp_guard\nresult = tnp_guard.__file__" }` names `.../Mod/FreeCADBuddy/.../tnp_guard.py`  

**03b — witness tamper, support unchanged.** **Given** `tc18_03a2_planted_witness`  
**When** the same script runs, but in place of the re-attach it lowers the snapshot witness of the `TopDatum` entry by 5 mm in z (`w[3] - 5`, `w[6] - 5`)  
**Then** verify: `result` is `('FLAGGED', [('TopDatum', 'REPOINTED', 1)])` and the detail says "whose witness moved"  

**03c — the face moves against the support.** **Given** `tc18_03b_reversed`  
**When** `mcp feature_set_parameters { doc: <handle>, feature: "Block", parameters: { Reversed: true } }`  
**Then** the edit is refused and undone — verify: `status` `SPEC_FAILED`, `mutation.rolled_back` `true`, `tnp_audit.status` `FLAGGED`, one finding `TopDatum.AttachmentSupport` `REPOINTED` at layer 1 with witness z 10 -> -10  
**And** the document is as before — verify: `script_exec` reads `Block.Reversed` `False` and `TopDatum` z `10.0`  

**03d — a mapped name that changes is never excused.** **Given** `tc18_03c_vertical_edge` with a datum axis `EdgeAxis` (`kind: "axis"`, `map_mode: "TwoPointLine"`) on the vertical edge at `x = 20, y = 0`  
**When** `mcp feature_set_parameters { doc: <handle>, feature: "Block", parameters: { Length: { value: 15, unit: "mm" } } }`  
**Then** verify: `status` `SPEC_FAILED`, `rolled_back` `true`, finding `EdgeAxis.AttachmentSupport` `REPOINTED` layer 1 "now maps to a different element". This is the safe-side false positive decision 017 records ("A vertical edge also grades `REPOINTED`, from the mapped-name check"); a `CLEAN` result here means that rule changed and the case needs review  

**Cleanup**: `mcp document_close { doc: <handle> }` for each sub-scenario

---

### TC-18-04: A datum on a curved face under GUI mesh deflection

**Priority**: High
**Design Ref**: `verification-design.md` §3.2 Layer 1; review ledger 13-15 R1-D1

The witness is the face's `BoundBox`. In the GUI, the view tessellates each shape, and FreeCAD then
computes `BoundBox` from that mesh, so a curved face's box depends on the mesh deflection, which
grows with the part size. The expected outcome is `CLEAN`, or a `REPOINTED` on the safe side that
the run records with the witness values.

**04a — the curved face is on the support's box.** **Given** a new document `tc18_04_curved_face`: Body, sketch `Profile` with one circle at the origin, radius 5 mm (`Coincident` centre-root, `Radius` 5 mm), Pad `Block` 10 mm  
**And** a datum point `CurvedPoint` (`kind: "point"`, `map_mode: "CenterOfMass"`) on the cylindrical face (`f.Surface.TypeId == 'Part::GeomCylinder'`), and `mcp view_fit_viewport` so the GUI meshes the part  
**When** `mcp feature_set_parameters { ..., feature: "Block", parameters: { Length: { value: 15, unit: "mm" } } }`  
**Then** record `status`, `rolled_back` and `tnp_audit`; with `CLEAN`, verify `CurvedPoint` z `7.5`  

**04b — the curved face is inside the support's box.** **Given** `tc18_04b_inner_curved_face`: the block, then a sketch `BossProfile` on XY in the Body with one circle centre (10, 5) radius 3 mm (`DistanceX`/`DistanceY` from the root, `Radius`), Pad `Boss` 15 mm, a datum point `BossPoint` (`CenterOfMass`) on the Boss cylindrical face, `view_fit_viewport`  
**When** `mcp feature_set_parameters { ..., feature: "Boss", parameters: { Length: { value: 20, unit: "mm" } } }`  
**Then** record `status`, `rolled_back`, the finding and both witnesses  
**And** the witness is exact on both sides — verify: the y bounds in the finding (or in a `PASS`) are `2.0` and `8.0` before and after. A y bound off the true value (for example `2.0164`) is the mesh-deflection defect D-1 of run 13-15-r1  
**And** a `REPOINTED` names its reason — verify with `evidence/probe04b_reason.py` (run 13-15-r2): the installed guard grades the same edit `REPOINTED` as shipped and `PASS` with `_has_positional_counter` and `_lineage_has_counter` switched off. The Boss side face has a name of the form `#<id>:1;:M;FUS;...` (`#23:1;:M;FUS;:H-85b:7,F` in run 13-15-r2): the fuse with the block gives it the piece counter `;:M`, and decision 017 never excuses a name that carries one. That is the expected safe-side result; a `REPOINTED` with the detector off is a finding  

**Cleanup**: `mcp document_close { doc: <handle> }`
