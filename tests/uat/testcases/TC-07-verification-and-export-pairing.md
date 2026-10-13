# TC-07: Verification & Export Pairing

Validates AD-9: an export is complete ONLY when its paired `verify_export_*` passes, and a failed
export leaves no file at the target path. Also covers the whole `verify_*` read-only surface —
`verify_shape`, `verify_sketch`, `verify_recompute` — against the real golden models and the
planted-fault fixtures. STEP, STL, and 3MF are all exercised; 3MF closes a gap the automated
sweeps do not reach. Run the scenarios in order against the live GUI bridge on `:8765`.

Every `verify_*` verdict in this file is produced by the code under test. A verdict of `OK` is a
claim, not evidence. The evidence is rank 1, a `cua-driver` pixel capture of the real FreeCAD
window that the agent reads and judges, corroborated at rank 2 by the exported file read back by an
outside tool — `trimesh`, `lib3mf`, or a re-import the agent looks at. Where a scenario has an
exported artifact, the outside-tool read is the strong corroboration and is named as such.

**Host**: GUI through the H2 proxy for every scenario. Every scenario's closing visual is a capture
of the human's FreeCAD window, so no scenario runs on the H1 headless host.

**Re-import.** `document_open` opens `.FCStd` files only: a STEP, STL or 3MF path is refused
(`documents.py:485-499`). Every "re-import as `<H_RT>`" below therefore uses this recipe. It runs
FreeCAD's own readers, not bridge code:

1. `mcp document_create { label: "<scenario>_rt" }` → record the handle as `<H_RT>`.
2. STEP: `mcp script_exec { doc: <H_RT>, code: "o = doc.addObject('Part::Feature', 'Reimport'); o.Shape = Part.read(r'<path>'); doc.recompute()" }`.
3. STL or 3MF: `mcp script_exec { doc: <H_RT>, code: "import Mesh; o = doc.addObject('Mesh::Feature', 'Reimport'); o.Mesh = Mesh.Mesh(r'<path>'); doc.recompute()" }`.

The re-imported object is `Reimport`. Read its volume with
`mcp query_mass_properties { doc: <H_RT>, object: "Reimport" }`. The object is visible, so it
needs no Show All. The `fcb` env (`Part.read`, `Mesh.Mesh`) is an equal alternative.

## Preconditions
- [ ] FreeCAD 1.1.x installed (verify: `ls "$FREECAD_EXE"`); the build under test is the live version: `query_capabilities.freecad_version`, read once at the start of the run and written `<live version>` below
- [ ] Golden and fault `.FCStd` files have no `GuiDocument.xml` and open with every object hidden. After each `document_open` of such a file, and before any fit or render of it, run **Show All**: `cua-driver call invoke_menu { pid, window_id, path: ["View","Visibility","Show All Objects"] }`. A fit before it returns `SPEC_FAILED view_fit.nothing_to_frame`. If `invoke_menu` refuses the path, show the objects with `mcp script_exec { doc: <H>, code: "for o in doc.Objects: o.Visibility = True" }`.
- [ ] `script_exec` is on (the default: `tools/list` names it). The re-import recipe and the TC-07-03 and TC-07-12 fixtures need it.
- [ ] FreeCAD GUI open, addon loaded, proxy serving `:8765` (verify: `netstat -ano | grep :8765` shows LISTENING)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/*.FCStd` lists 5 files)
- [ ] Fault fixtures present (verify: `ls benchmarks/g0/fault-injection/wrong-volume/case.yaml benchmarks/g0/fault-injection/non-watertight-open-shell/case.yaml`)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)
- [ ] Oracle libraries importable in the external proxy env, with the extras the outside reads need: `trimesh` loads a 3MF only with `lxml` and returns a mesh only with `force='mesh'`, and `split()` needs `networkx` (verify: `uv run --with networkx --with lxml python -c "import trimesh, lib3mf, networkx, lxml"`)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` returns a `QOpenGLWidget`)
- [ ] `cua-driver` can reach the **View → Fit All** menu path, the non-MCP framing fallback (verify: the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view) succeeds with a document open)
- [ ] The export tools declare NO `confirm` property; only `sketch_*` and `feature_*` do. Because every schema sets `additionalProperties: false`, passing `confirm` to an export is a schema rejection (verify: `python3 -c "import json;d=json.load(open('$RUN_DIR/evidence/tool_surface.json'));print([k for k,v in d.items() if v['mut'] and 'confirm' in v['props']])"` lists no `export_*` tool)

---

### TC-07-01: verify_shape covers the whole closed assertion vocabulary

**Priority**: Critical
**Design Ref**: `verification-design.md` §5 (shape assertions), `mcp-tools-design.md` §3.3 (verify surface)

**Given** `box-10-20-30.FCStd` closed from any prior case — verify: `document_list` does not name it  
**And** the golden box is open — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the returned `doc` handle as `<H>`; name its sole object `<OBJ>` via `mcp query_tree_summary { doc: <H> }` (read the Name on the first tree line)  

**When** all five assertion kinds are run in one call  
```
mcp verify_shape { doc: <H>, object: <OBJ>, checks: [
  { fn: "expect_volume", expect: 6000.0, tol: { rel: 0.001 } },
  { fn: "expect_bbox", expect: [10.0, 20.0, 30.0], tol: { abs: 0.05 } },
  { fn: "expect_solid_count", expect: 1 },
  { fn: "expect_valid", expect: true },
  { fn: "expect_watertight", expect: true }
] }
```

**Then** envelope status is `OK` — verify: `status` equals `OK` and `detail` is `null`  
**And** five checks returned, one per `fn` — verify: `structured_content.checks` has ids `assert.expect_volume`, `assert.expect_bbox`, `shape.solid_count`, `shape.valid`, `shape.watertight`  
**And** every check passed — verify: no element of `structured_content.checks` has `passed: false`  
**And** measured volume is the analytic 6000.0 — verify: the `assert.expect_volume` check `measured` equals `6000.0`  
**And** verdict is derived, not asserted — verify: `structured_content.verdict` equals `OK` and equals the envelope `status`  
**And** an unknown assertion `fn` is refused — verify: `mcp verify_shape { doc: <H>, object: <OBJ>, checks: [{ fn: "expect_genus", expect: 0 }] }` returns `INVALID_INPUT` with message `unknown assertion fn: 'expect_genus'`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window shows one whole box with the proportions the scenario asked for — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-01-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one solid body, closed on every side, whose three edge lengths read as roughly 1 : 2 : 3. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-07-02: verify_shape with no checks is measurement-only

**Priority**: High
**Design Ref**: `verification-design.md` §5 (measured facts), `mcp-tools-design.md` §3.3

**Given** `cylinder-r5-h20.FCStd` not already open — verify: `document_list` does not name it  
**And** the cylinder is open and its sole object resolved as `<OBJ>` — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/cylinder-r5-h20.FCStd" }` returns `OK`, then `mcp query_tree_summary { doc: <H> }` names the object  

**When** the call is made with `checks` omitted entirely  
```
mcp verify_shape { doc: <H>, object: <OBJ> }
```

**Then** status is `OK` — verify: `status` equals `OK`  
**And** the five measured facts are reported — verify: `structured_content.checks` has exactly the ids `shape.volume`, `shape.bbox`, `shape.solid_count`, `shape.valid`, `shape.watertight`  
**And** no check carries an `expected` — verify: no element of `structured_content.checks` has an `expected` key  
**And** every fact is marked `passed: true` (nothing was asserted, so nothing can fail) — verify: all `checks[*].passed` are `true`  
**And** the measured volume matches the analytic cylinder — verify: the `shape.volume` `measured` is within 0.01 of `1570.7963` (results carry 2 decimals)  
**And** measurement-only mode never grades — verify: repeating the call with `expect_volume` of `1.0` returns `SPEC_FAILED`, proving the `passed: true` facts came from the absent `checks`, not from a lenient grader  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window shows a cylinder, not some other solid — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-02-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one body with a round cross-section and two flat circular ends, standing roughly twice as tall as it is wide. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-07-03: verify_sketch PASS is equivalent to FullyConstrained, both directions

**Priority**: Critical
**Design Ref**: `verification-design.md` §5 (AD-8 sketch grading), `mcp-tools-design.md` §3.3

**Given** a scratch document exists for sketch work — verify: `mcp document_create { label: "tc07_sketch" }` returns `OK`; record the handle as `<H>`. `document_create` declares `label`, not `name`, and takes no `confirm`  
**And** the document holds an under-constrained sketch `Sketch` with one line segment, and one non-sketch object `Group`. The typed sketch tools cannot build it: the bridge rolls back any mutation that leaves a sketch under-constrained (AD-8). So `script_exec` builds it — verify: the call returns `OK`  
```
mcp script_exec { doc: <H>, code: "sk = doc.addObject('Sketcher::SketchObject', 'Sketch'); sk.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0))); doc.addObject('App::DocumentObjectGroup', 'Group'); doc.recompute()" }
```

**When** the under-constrained sketch is graded  
```
mcp verify_sketch { doc: <H>, sketch: "Sketch" }
```
**And** the three constraints that fully constrain it are added in one call. Auto-approve is on by default, so no `confirm` is sent  
```
mcp sketch_add_constraint { doc: <H>, sketch: "Sketch", constraints: [
  { type: "Coincident", first: 0, first_pos: 1, second: -1, second_pos: 1 },
  { type: "Horizontal", first: 0 },
  { type: "DistanceX", first: 0, value: { value: 10, unit: "mm" } }
] }
```
**And** the same `verify_sketch` call grades it again  
**And** a duplicate Horizontal constraint is added  
```
mcp sketch_add_constraint { doc: <H>, sketch: "Sketch", constraints: [ { type: "Horizontal", first: 0 } ] }
```

**Then** the under-constrained sketch fails — verify: the first grade returns status `SPEC_FAILED` with the failed check id `sketch.fully_constrained`  
**And** the reported `dof` is the solver's value, greater than 0 — verify: `structured_content.subject.dof` is a positive integer (4 for one free line). `verify_sketch` solves before it reads the DoF, so a sketch FreeCAD has not solved yet does not report 0  
**And** the failure detail names the measured state — verify: the `sketch.fully_constrained` check `detail.message` matches `dof=<n>, conflicting=0, malformed=0, evaluate_bad=False, degenerate=0`  
**And** the constraint call commits — verify: it returns status `OK`  
**And** the fully-constrained sketch passes — verify: the second grade returns status `OK`  
**And** `dof` is 0 exactly when the verdict is `OK` — verify: the second grade's `structured_content.subject.dof` equals `0` and `subject.fully_constrained` is `true`  
**And** a fully redundant constraint fails and rolls back (redundancy rule: full redundancy is a hard fail, partial redundancy only warns) — verify: the duplicate Horizontal call returns `RECOMPUTE_ERROR`, `structured_content.mutation.post_verify.recompute_clean` is `false` and `mutation.rolled_back` is `true`; a third `verify_sketch` returns `OK` with `dof` `0`, so the rollback left the three constraints and nothing more  
**And** a non-sketch object is refused — verify: `mcp verify_sketch { doc: <H>, sketch: "Group" }` returns `INVALID_INPUT` with message `object is not a sketch: Group`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window shows the sketch the grading describes — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-03-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one straight horizontal segment beginning at the origin marker, with constraint glyphs drawn on it, and drawn in FreeCAD's fully-constrained colour rather than the under-constrained white. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-07-04: verify_recompute on a clean document reports no failing objects

**Priority**: Critical
**Design Ref**: `verification-design.md` §5 (recompute grading), `mcp-tools-design.md` §3.3

**Given** `box40-hole-r5.FCStd` present — verify: `ls benchmarks/g0/golden-models/box40-hole-r5.FCStd`  
**And** the genus-1 golden model is open — verify: `mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box40-hole-r5.FCStd" }` returns `OK`; record the handle as `<H>`  

**When** it is recompute-graded  
```
mcp verify_recompute { doc: <H> }
```

**Then** status is `OK` — verify: `status` equals `OK` and `detail` is `null`  
**And** the clean path emits exactly one passed check — verify: `structured_content.checks` is a single entry with id `recompute.clean` and `passed: true`  
**And** no failing objects are listed — verify: `structured_content.subject.failing_objects` is an empty array  
**And** the summary text states the clean result — verify: the envelope `text` equals `Recompute clean: no errors.`  
**And** the call is read-only — verify: `mcp query_mass_properties { doc: <H>, object: <OBJ> }` returns the same `volume.value` before and after the grade  
**And** the banner records the build — verify: `structured_content.banner.freecad_version` is non-empty and `banner.element_map_version` is an integer or `null`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window shows a built solid, not an empty view — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-04-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one box with a round hole passing through it, and no red or yellow error marker on any tree item. A "clean recompute" over an empty viewport is the defect this looks for. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-07-05: export_step writes both AP schemas and never self-reports verified

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (export pairing, AD-9), `mcp-tools-design.md` §3.5 (export surface)

**Given** `$RUN_DIR/evidence/` writable — verify: `ls -d "$RUN_DIR/evidence"`  
**And** no stale target files — verify: `rm -f "$RUN_DIR/evidence/tc-07-05-ap242.step" "$RUN_DIR/evidence/tc-07-05-ap214.step"`  
**And** `box-10-20-30.FCStd` is open as `<H>` with `<OBJ>` resolved — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H> }` names the object  

**When** the default schema is exported  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-07-05-ap242.step", objects: [<OBJ>], ap: "AP242" }
```
**And** the other enum value is exported  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-07-05-ap214.step", objects: [<OBJ>], ap: "AP214" }
```

**Then** both exports return `OK` — verify: both envelopes carry `status` equal to `OK`  
**And** both results carry `verified: false` — verify: `structured_content.verified` is `false` in both, never `true`  
**And** both mint a distinct `export_id` — verify: both `structured_content.export_id` values start with `fcb-export:` and differ from each other  
**And** the reported `bytes` matches the file on disk — verify: `stat -c %s "$RUN_DIR/evidence/tc-07-05-ap242.step"` equals the result's `structured_content.bytes`  
**And** the AP schema is pinned per call — verify: the file header `FILE_SCHEMA` names the schema of each `ap`. `grep -c "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING" "$RUN_DIR/evidence/tc-07-05-ap242.step"` is non-zero and `grep -c "AUTOMOTIVE_DESIGN" "$RUN_DIR/evidence/tc-07-05-ap242.step"` is `0`; `grep -c "AUTOMOTIVE_DESIGN" "$RUN_DIR/evidence/tc-07-05-ap214.step"` is non-zero (AP214 is written as `AUTOMOTIVE_DESIGN`, never as the literal `AP214`)  
**And** the paired verifier reads the same schema from each file — verify: `mcp verify_export_step { doc: <H>, export_id: <each export_id> }` returns `OK` for both, and its `export_step.schema` check has `passed: true` with `measured` `AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF` for the AP242 file and `AUTOMOTIVE_DESIGN` for the AP214 file  
**And** a value outside the enum is refused at the schema gate — verify: `ap: "AP203"` returns an MCP protocol rejection (`isError` set, no envelope)  
**And** the summary text names the written path — verify: the envelope `text` equals `STEP export written -> $RUN_DIR/evidence/tc-07-05-ap242.step.`  
**And** the file is a real solid to an outside reader — verify: re-import the AP242 file as `<H_RT>` with the re-import recipe (STEP) and read its volume with `mcp query_mass_properties { doc: <H_RT>, object: "Reimport" }`; it is within 0.1 % of `6000.0`. The exporter's own `bytes` count is a claim; a shape re-read from the file is an outside witness.  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the re-imported solid looks like the original box — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-05-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one closed box whose edge lengths read as roughly 1 : 2 : 3, with no missing face and no split into fragments. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-05-ap242.step" "$RUN_DIR/evidence/tc-07-05-ap214.step"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <H> }
```

---

### TC-07-06: export_stl and export_3mf come from one tessellation source

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (single tessellation, #25311), `mcp-tools-design.md` §3.5

**Given** no stale mesh targets — verify: `rm -f "$RUN_DIR/evidence/tc-07-06-same.stl" "$RUN_DIR/evidence/tc-07-06-same.3mf"`  
**And** `sphere-r10.FCStd` is open as `<H>` with `<OBJ>` resolved (a curved surface makes the deflection observable) — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H> }` names the object  

**When** both formats are written with the SAME deflection pair  
```
mcp export_stl { doc: <H>, path: "$RUN_DIR/evidence/tc-07-06-same.stl", objects: [<OBJ>], linear: 0.1, angular: 0.5 }
mcp export_3mf { doc: <H>, path: "$RUN_DIR/evidence/tc-07-06-same.3mf", objects: [<OBJ>], linear: 0.1, angular: 0.5 }
```

**Then** both exports return `OK` — verify: both envelopes carry `status` equal to `OK`  
**And** the two formats report the identical facet count — verify: the STL result `structured_content.facets` equals the 3MF result `structured_content.facets`  
**And** both carry `verified: false` — verify: `structured_content.verified` is `false` in both  
**And** both files exist and are non-empty — verify: `stat -c %s "$RUN_DIR/evidence/tc-07-06-same.stl" "$RUN_DIR/evidence/tc-07-06-same.3mf"` prints two values greater than 0  
**And** the paired verifiers both pass — verify: `verify_export_stl` and `verify_export_3mf` on the two `export_id`s both return `OK`  
**And** the self-read facet count matches the written count in both — verify: in both verify reports, the `self_read.facet_count` check has `measured` equal to `expected` and `passed: true`  
**And** a zero-facet tessellation is refused, not written — verify: an angular deflection of `0` returns `INVALID_INPUT` with a message starting `deflection out of range:`  
**And** an outside tool confirms the identical facet count from the two files themselves — verify: `uv run --with networkx --with lxml python -c "import trimesh;print(len(trimesh.load('$RUN_DIR/evidence/tc-07-06-same.stl').faces), len(trimesh.load('$RUN_DIR/evidence/tc-07-06-same.3mf', force='mesh').faces))"` prints two equal numbers. The bridge reporting equal `facets` is a claim by the code under test; `trimesh` counting them off disk is an outside witness.  
**And** *(visual)* the model is framed — verify: re-import the STL as `<H_RT>` with the re-import recipe (STL), then `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the re-imported mesh looks like the original sphere — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-06-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one closed round body with a faceted surface, no hole, no missing cap, no flattened side. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-06-same.stl" "$RUN_DIR/evidence/tc-07-06-same.3mf"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <H> }
```

---

### TC-07-07: verify_export_step re-imports and grades against the recorded source

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (STEP round-trip), `mcp-tools-design.md` §3.3

**Given** no stale target — verify: `rm -f "$RUN_DIR/evidence/tc-07-07-rt.step"`  
**And** `box40-hole-r5.FCStd` is open as `<H>` with `<OBJ>` resolved — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H> }` names the object  

**When** STEP is exported and the returned `export_id` kept as `<EID>`  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-07-07-rt.step", objects: [<OBJ>] }
```
**And** the paired verifier is run  
```
mcp verify_export_step { doc: <H>, export_id: <EID> }
```

**Then** status is `OK` — verify: `status` equals `OK` and `structured_content.verdict` equals `OK`  
**And** exactly four round-trip checks run — verify: `structured_content.checks` has the ids `export_step.volume`, `export_step.valid`, `export_step.topology_counts`, `export_step.schema`  
**And** the file schema matches the default `ap` — verify: the `export_step.schema` check has `passed: true` and `measured` `AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF` (the default `ap` is `AP242`)  
**And** the volume band is the STEP relative tolerance — verify: the `export_step.volume` check `tolerance` equals `{ "rel": 0.001 }`  
**And** the re-imported volume matches the genus-1 analytic value — verify: the `export_step.volume` `measured` is within 0.1 % of `15214.6018`  
**And** the re-imported shape is valid — verify: the `export_step.valid` check has `measured: true` and `passed: true`  
**And** topology counts are EQUAL, not banded — verify: the `export_step.topology_counts` check `measured` object equals its `expected` object for `faces`, `edges`, and `solids`  
**And** the subject names the verified artifact — verify: `structured_content.subject.export_id` equals `<EID>` and `subject.path` equals `$RUN_DIR/evidence/tc-07-07-rt.step`  
**And** the temp re-import document is closed — verify: `mcp document_list {}` lists no handle whose name starts with `FCB_TMP_`  
**And** an independent re-import reproduces the same volume the verifier claimed — verify: re-import the file yourself as `<H_RT>` with the re-import recipe (STEP) and read `mcp query_mass_properties { doc: <H_RT>, object: "Reimport" }`; it is within 0.1 % of `15214.6018`. `verify_export_step` grading its own re-import is the actor grading itself; a separate re-import measured by the agent is the outside witness.  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the re-imported solid carries the through-hole — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-07-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one box with a single round opening you can see through, not a plain solid block. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-07-rt.step"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <H> }
```

---

### TC-07-08: verify_export_stl merges its two oracle legs plus the self-read, and they agree

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (independent oracles, disagreement is FAIL), `mcp-tools-design.md` §3.3

**Given** trimesh importable in the proxy env — verify: `uv run python -c "import trimesh"`  
**And** no stale target — verify: `rm -f "$RUN_DIR/evidence/tc-07-08-legs.stl"`  
**And** `box-10-20-30.FCStd` is open as `<H>` with `<OBJ>` resolved — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H> }` names the object  

**When** STL is exported and `<EID>` kept  
```
mcp export_stl { doc: <H>, path: "$RUN_DIR/evidence/tc-07-08-legs.stl", objects: [<OBJ>] }
```
**And** it is verified  
```
mcp verify_export_stl { doc: <H>, export_id: <EID> }
```

**Then** status is `OK` — verify: `status` equals `OK`  
**And** the trimesh leg reported all five of its checks — verify: `structured_content.checks` holds the ids `trimesh_stl.watertight`, `trimesh_stl.winding_consistent`, `trimesh_stl.is_volume`, `trimesh_stl.volume_band`, `trimesh_stl.euler`  
**And** the stdlib leg reported all four of its checks — verify: `structured_content.checks` holds the ids `stl2.facets`, `stl2.manifold_edge_pairing`, `stl2.local_winding`, `stl2.non_degenerate`  
**And** the FreeCAD self-read leg is merged in — verify: `structured_content.checks` holds `self_read.facet_count` and `self_read.vertex_count`, both `passed: true`  
**And** the two oracles agree — verify: the `oracle.agreement` check has `passed: true` and its `measured` object reads `{"trimesh_stl": true, "stdlib_stl": true}`  
**And** the volume band is deflection-derived, never ±0.1 % — verify: `structured_content.volume_band` equals `(2/3) * linear * area` for the recorded tessellation, and the `trimesh_stl.volume_band` check `tolerance` carries an `abs` key, not a `rel` key  
**And** the recorded tessellation is echoed — verify: `structured_content.tess` equals `{ "linear": 0.1, "angular": 0.5 }` for a default-deflection export  
**And** a corrupted file fails closed rather than raising — verify: truncating the STL to 100 bytes and re-running `verify_export_stl` returns `SPEC_FAILED`, not `INVALID_INPUT` and not a crash  
**And** `trimesh` run outside the bridge reaches the same watertight verdict — verify: re-export the intact STL, then `uv run --with networkx --with lxml python -c "import trimesh;m=trimesh.load('$RUN_DIR/evidence/tc-07-08-legs.stl');print(m.is_watertight, m.is_winding_consistent, m.volume)"` prints `True True` and a volume within the deflection band of `6000.0`. The bridge's `oracle.agreement` is a claim by the code under test; `trimesh` invoked directly on the file is the outside witness.  
**And** *(visual)* the model is framed — verify: re-import the intact STL as `<H_RT>` with the re-import recipe (STL), then `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the re-imported mesh is a closed box — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-08-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one box with all six sides present, no gap you can see through, no dark inverted patch where a facet faces the wrong way. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-08-legs.stl"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <H> }
```

---

### TC-07-09: verify_export_3mf merges the lib3mf container and geometry layers with the self-read

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (3MF oracle layers, unit-lie guard), `mcp-tools-design.md` §3.3

**Given** lib3mf importable in the proxy env — verify: `uv run python -c "import lib3mf"`  
**And** no stale target — verify: `rm -f "$RUN_DIR/evidence/tc-07-09-legs.3mf"`  
**And** `cylinder-r5-h20.FCStd` is open as `<H>` with `<OBJ>` resolved — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H> }` names the object  

**When** 3MF is exported and `<EID>` kept  
```
mcp export_3mf { doc: <H>, path: "$RUN_DIR/evidence/tc-07-09-legs.3mf", objects: [<OBJ>] }
```
**And** it is verified  
```
mcp verify_export_3mf { doc: <H>, export_id: <EID> }
```

**Then** status is `OK` — verify: `status` equals `OK`  
**And** the lib3mf container layer reported its four checks — verify: `structured_content.checks` holds `lib3mf.parses`, `lib3mf.unit_millimeter`, `lib3mf.manifold_and_oriented`, `lib3mf.metadata_present`  
**And** the trimesh geometry layer is built from the lib3mf arrays, not a second file read — verify: `structured_content.checks` holds `trimesh_3mf.watertight`, `trimesh_3mf.winding_consistent`, `trimesh_3mf.is_volume`, `trimesh_3mf.volume_band`, `trimesh_3mf.euler`  
**And** the unit-lie guard passed on both sides — verify: the `lib3mf.unit_millimeter` check `measured` reads `{"unit": 1, "source_is_mm": true}` (confirm the enum with `uv run python -c "import lib3mf; print(int(lib3mf.ModelUnit.MilliMeter))"`) and `passed: true`  
**And** every mesh object in the container is manifold — verify: the `lib3mf.manifold_and_oriented` check `measured` reads `{"meshes": 1, "non_manifold": 0}` and `passed: true`  
**And** missing metadata never drives a FAIL — verify: the `lib3mf.metadata_present` check is `passed: true` regardless of its `measured` count  
**And** the self-read leg is merged in and agrees — verify: `self_read.facet_count` and `self_read.vertex_count` are both `passed: true`, and `oracle.agreement` reads `{"lib3mf": true}` with `passed: true`  
**And** the mesh volume is inside the deflection band, not the STEP band — verify: `structured_content.volume_band` equals `(2/3) * linear * area` of the source, about `52.36` for the default `linear` 0.1 and the cylinder area 785.40 (`verification-design.md` §8, `exports.py` `mesh_volume_band`); the `trimesh_3mf.volume_band` `measured` is within that band of `1570.7963`, and the check `tolerance` has an `abs` key, not a `rel` key  
**And** `lib3mf` run outside the bridge reads the same unit and the same mesh count from the file — verify: `uv run --with networkx --with lxml python -c "import lib3mf,trimesh;w=lib3mf.Wrapper();m=w.CreateModel();m.QueryReader('3mf').ReadFromFile('$RUN_DIR/evidence/tc-07-09-legs.3mf');print(int(m.GetUnit()))"` prints `1`, and `uv run --with networkx --with lxml python -c "import trimesh;print(trimesh.load('$RUN_DIR/evidence/tc-07-09-legs.3mf', force='mesh').is_watertight)"` prints `True`. The bridge's own `lib3mf.*` checks are claims by the code under test; the library invoked directly on the file is the outside witness.  
**And** *(visual)* the model is framed — verify: re-import the 3MF as `<H_RT>` with the re-import recipe (3MF), then `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the re-imported mesh is a closed cylinder at the size the source document shows — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-09-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one round body roughly twice as tall as it is wide, both flat ends closed, and its size against the on-screen axis cross the same as the source cylinder's. A unit lie shows here as a body a thousand times too large or too small next to the same axis cross. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-09-legs.3mf"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <H> }
```

---

### TC-07-10: custom deflection changes the facet count and the derived volume band

**Priority**: High
**Design Ref**: `verification-design.md` §6 (deflection-derived band), `mcp-tools-design.md` §3.5

**Given** no stale targets — verify: `rm -f "$RUN_DIR/evidence/tc-07-10-coarse.stl" "$RUN_DIR/evidence/tc-07-10-fine.stl"`  
**And** `sphere-r10.FCStd` is open as `<H>` with `<OBJ>` resolved — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H> }` names the object. A doubly-curved surface is the case a bbox-relative band underestimates, so the sphere is the required fixture here.  

**When** coarse and fine are exported  
```
mcp export_stl { doc: <H>, path: "$RUN_DIR/evidence/tc-07-10-coarse.stl", objects: [<OBJ>], linear: 0.5, angular: 1.0 }
mcp export_stl { doc: <H>, path: "$RUN_DIR/evidence/tc-07-10-fine.stl", objects: [<OBJ>], linear: 0.01, angular: 0.1 }
```
**And** each is verified with its own `export_id`  

**Then** the finer deflection produces strictly more facets — verify: the fine export's `structured_content.facets` is greater than the coarse export's  
**And** both verifies return `OK` — verify: both `verify_export_stl` calls return `status` equal to `OK`  
**And** the band tracks the deflection — verify: the coarse verify's `structured_content.volume_band` is 50 times the fine verify's, matching `(2/3) * linear * area` at `linear` 0.5 versus 0.01: about `418.88` and `8.378` for the sphere area 1256.64 (`verification-design.md` §8)  
**And** the band is never the STEP ±0.1 % — verify: the fine verify's `volume_band` is about `8.378`, not `0.001 * 4188.7902` (`4.19`), and the `trimesh_stl.volume_band` check `tolerance` has an `abs` key with no `rel` key  
**And** the coarse mesh volume falls short of the solid but stays inside its own band — verify: the coarse `trimesh_stl.volume_band` `measured` is less than `4188.7902` and its check is `passed: true`  
**And** a deflection below the floor is refused before any file is written — verify: `linear: 0.00001` returns `INVALID_INPUT` with a message starting `deflection out of range:` and `ls "$RUN_DIR/evidence/tc-07-10-floor.stl"` reports no such file  
**And** an outside tool confirms the facet counts differ in the direction claimed — verify: `uv run --with networkx --with lxml python -c "import trimesh;print(len(trimesh.load('$RUN_DIR/evidence/tc-07-10-coarse.stl').faces), len(trimesh.load('$RUN_DIR/evidence/tc-07-10-fine.stl').faces))"` prints a smaller number then a larger one. The bridge's `facets` field is a claim by the code under test; `trimesh` counting them off disk is an outside witness.  
**And** *(visual)* the coarse mesh is framed — verify: re-import the coarse STL as `<H_COARSE>` with the re-import recipe (STL), then `mcp view_fit_viewport { doc: <H_COARSE> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test; capture `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-10-coarse.png"}' | & cua-driver call get_window_state`  
**And** *(visual)* the fine mesh is framed and the two images differ as the deflection says — verify: re-import the fine STL as `<H_FINE>` with the re-import recipe (STL), fit it the same way, then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-10-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen in each: the coarse sphere shows large flat plates and a visibly angular outline, the fine sphere reads as a smooth round body. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-10-coarse.stl" "$RUN_DIR/evidence/tc-07-10-fine.stl"
```
```
mcp document_close { doc: <H_COARSE> }
mcp document_close { doc: <H_FINE> }
mcp document_close { doc: <H> }
```

---

### TC-07-11: multi-object selection is refused by the single-shape writers

**Priority**: High
**Design Ref**: `verification-design.md` §6 (fail-closed selection), `mcp-tools-design.md` §3.5

**Given** no stale targets — verify: `rm -f "$RUN_DIR/evidence/tc-07-11-multi.step" "$RUN_DIR/evidence/tc-07-11-multi.stl" "$RUN_DIR/evidence/tc-07-11-multi.3mf"`  
**And** `box-10-20-30.FCStd` is open as `<H>` with `<OBJ>` resolved — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H> }` names the object  
**And** the framed starting state is captured — verify: run Show All and fit the model, then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-11-before.png"}' | & cua-driver call get_window_state`  

**When** a two-element selection is passed to each writer  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-07-11-multi.step", objects: [<OBJ>, <OBJ>] }
mcp export_stl  { doc: <H>, path: "$RUN_DIR/evidence/tc-07-11-multi.stl",  objects: [<OBJ>, <OBJ>] }
mcp export_3mf  { doc: <H>, path: "$RUN_DIR/evidence/tc-07-11-multi.3mf",  objects: [<OBJ>, <OBJ>] }
```

**Then** all three writers return `INVALID_INPUT` — verify: each envelope `status` equals `INVALID_INPUT`  
**And** the message names the single-shape constraint — verify: each `detail.message` equals `export supports a single object; got multiple`  
**And** no partial file is left behind — verify: `ls "$RUN_DIR/evidence/tc-07-11-multi."*` reports no such files  
**And** an unknown object name inside a one-element selection is a separate refusal — verify: `objects: ["NoSuchObject"]` returns `INVALID_INPUT` with message `unknown object: NoSuchObject`  
**And** an empty document is refused distinctly — verify: exporting from a freshly created empty document returns `INVALID_INPUT` with message `document has no objects to export`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is unchanged by the five refusals — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-11-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: the same single whole box in both, no error dialog raised, no object added to or removed from the tree. No file was written, so there is no exported artifact for an outside tool to read; the visual carries the whole result here. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-11-multi.step" "$RUN_DIR/evidence/tc-07-11-multi.stl" "$RUN_DIR/evidence/tc-07-11-multi.3mf"
```
```
mcp document_close { doc: <H> }
```

---

### TC-07-12: an omitted `objects` exports the document's sole object

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §3.5 (default selection), `verification-design.md` §6

**Given** no stale target — verify: `rm -f "$RUN_DIR/evidence/tc-07-12-default.step"`  
**And** `box-10-20-30.FCStd` is open as `<H>` (a single-object document) — verify: `mcp document_open` returns `OK`  

**When** the export is made with `objects` absent from the arguments entirely  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-07-12-default.step" }
```
**And** a document that holds two shape objects is built as `<H2>`, and the omitted-`objects` export is repeated on it to `$RUN_DIR/evidence/tc-07-12-default-compound.step`. `two-box-compound.FCStd` cannot serve here: it holds one object (`TwoBoxCompound`, a compound of two solids), so its default export is not ambiguous  
```
mcp document_create { label: "tc07_two_objects" }
mcp script_exec { doc: <H2>, code: "doc.addObject('Part::Box', 'BoxA'); b = doc.addObject('Part::Box', 'BoxB'); b.Placement.Base = App.Vector(20, 0, 0); doc.recompute()" }
mcp export_step { doc: <H2>, path: "$RUN_DIR/evidence/tc-07-12-default-compound.step" }
```

**Then** the single-object document exports without a selection — verify: the first export returns `status` equal to `OK`  
**And** the exported shape is the document's sole object — verify: `verify_export_step` on the returned `export_id` returns `OK` with `export_step.volume` `measured` within 0.1 % of `6000.0`  
**And** a multi-object document refuses the ambiguous default — verify: the repeat on `<H2>` returns `INVALID_INPUT` with message `document has multiple objects; specify 'objects' with the one to export`  
**And** the ambiguous case wrote nothing — verify: `ls "$RUN_DIR/evidence/tc-07-12-default-compound.step"` reports no such file  
**And** an empty `objects` array behaves as omitted, not as a selection of none — verify: `objects: []` on the single-object document returns the same `OK` result as the first export  
**And** an independent re-import measures the box, not the compound — verify: re-import the file as `<H_RT>` with the re-import recipe (STEP, path `$RUN_DIR/evidence/tc-07-12-default.step`) and read `mcp query_mass_properties { doc: <H_RT>, object: "Reimport" }`; it is within 0.1 % of `6000.0`, not `2000.0` (two 10 mm boxes). The verifier's own volume check is a claim by the code under test; a separate re-import measured by the agent is the outside witness.  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the re-imported file holds exactly one box — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-12-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one solid box of roughly 1 : 2 : 3 proportions — not two separate bodies, and not an empty view. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-12-default.step" "$RUN_DIR/evidence/tc-07-12-default-compound.step"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <H> }
mcp document_close { doc: <H2> }
```

---

### TC-07-13: genus-1 and compound geometry verify correctly

**Priority**: High
**Design Ref**: `verification-design.md` §5 (topology-independent checks), §6 (Euler parity)

**Given** both fixtures present — verify: `ls benchmarks/g0/golden-models/box40-hole-r5.FCStd benchmarks/g0/golden-models/two-box-compound.FCStd`  
**And** `box40-hole-r5.FCStd` is open as `<H1>` with `<OBJ1>` resolved — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H1> }` names the object  
**And** `two-box-compound.FCStd` is open as `<H2>` with `<OBJ2>` resolved — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H2> }` names the object  

**When** the genus-1 solid is graded  
```
mcp verify_shape { doc: <H1>, object: <OBJ1>, checks: [
  { fn: "expect_volume", expect: 15214.6018, tol: { rel: 0.001 } },
  { fn: "expect_solid_count", expect: 1 },
  { fn: "expect_watertight", expect: true }
] }
```
**And** it is exported to STL at `$RUN_DIR/evidence/tc-07-13-genus.stl` and the paired result verified (the through-hole makes it genus 1, Euler characteristic 0)  
**And** the compound is graded  
```
mcp verify_shape { doc: <H2>, object: <OBJ2>, checks: [
  { fn: "expect_volume", expect: 2000.0, tol: { rel: 0.001 } },
  { fn: "expect_solid_count", expect: 2 }
] }
```
**And** its mass properties are read  
```
mcp query_mass_properties { doc: <H2>, object: <OBJ2> }
```

**Then** the genus-1 solid passes all three checks — verify: the first grade returns `status` equal to `OK` with `assert.expect_volume` `measured` within 0.1 % of `15214.6018`  
**And** the through-hole export verifies — verify: the `verify_export_stl` returns `OK`  
**And** the Euler check accepts genus 1 — verify: the `trimesh_stl.euler` check has `measured` equal to `0` and `passed: true`, proving the check tests parity and not a fixed value  
**And** the compound passes with 2 solids — verify: the compound grade returns `status` equal to `OK` with the `shape.solid_count` check `measured` equal to `2`  
**And** the compound volume is the analytic 2000.0 — verify: the compound grade's `assert.expect_volume` `measured` is within 0.001 of `2000.0`  
**And** the compound reports a null centre of mass — verify: the mass-properties read returns `status` equal to `OK` with `structured_content.com` equal to `null`  
**And** a compound is not watertight under the single-solid rule — verify: `expect_watertight: true` on `<OBJ2>` returns `SPEC_FAILED`, because `_is_watertight` requires exactly one solid  
**And** an outside tool reaches Euler characteristic 0 from the file itself — verify: `uv run --with networkx --with lxml python -c "import trimesh;m=trimesh.load('$RUN_DIR/evidence/tc-07-13-genus.stl');print(m.euler_number, m.is_watertight)"` prints `0 True`. The bridge's `trimesh_stl.euler` check is a claim by the code under test; `trimesh` invoked directly on the file is the outside witness.  
**And** *(visual)* the model is framed — verify: re-import the STL as `<H_RT>` with the re-import recipe (STL, path `$RUN_DIR/evidence/tc-07-13-genus.stl`), then `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the re-imported mesh has a hole you can see through — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-13-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one box with a single round opening passing all the way through it. A plain block with no opening is the failure this looks for. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-13-genus.stl"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <H1> }
mcp document_close { doc: <H2> }
```

---

### TC-07-14: Unicode, spaces, and a long path are written and re-read correctly

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §3.5 (path handling), `verification-design.md` §6

**Given** the target directory exists — verify: `mkdir -p "$RUN_DIR/evidence/tc-07-14 exports"`  
**And** `box-10-20-30.FCStd` is open as `<H>` with `<OBJ>` resolved — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H> }` names the object  

**When** the export targets a path with a space and non-ASCII characters  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-07-14 exports/boîte-立方体.step", objects: [<OBJ>] }
```
**And** a deliberately long file name (200 characters of `a` before the extension) is exported under the same directory  
**And** each export is verified through its own `export_id`  

**Then** the Unicode path export returns `OK` — verify: the first export's `status` equals `OK`  
**And** the file exists at the exact path given — verify: `ls "$RUN_DIR/evidence/tc-07-14 exports/boîte-立方体.step"` lists the file  
**And** the returned `path` is echoed back unmodified — verify: `structured_content.path` equals the string passed in, with no escaping or normalisation  
**And** the paired verify re-reads the same file — verify: `verify_export_step` returns `OK` with `subject.path` equal to the Unicode path  
**And** the long file name is written or refused cleanly, never half-written — verify: the long-name export returns either `OK` with an existing file, or `INVALID_INPUT`/`RECOMPUTE_ERROR` with no file at that path  
**And** `bytes` is correct for the Unicode path — verify: `stat -c %s "$RUN_DIR/evidence/tc-07-14 exports/boîte-立方体.step"` equals the result's `structured_content.bytes`  
**And** an independent re-import of the Unicode path yields the right solid — verify: re-import it as `<H_RT>` with the re-import recipe (STEP, path `$RUN_DIR/evidence/tc-07-14 exports/boîte-立方体.step`) and read `mcp query_mass_properties { doc: <H_RT>, object: "Reimport" }`; it is within 0.1 % of `6000.0`. The echoed `path` and `bytes` are claims by the code under test; a shape re-read from the named file is the outside witness that the bytes landed where the name says.  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the solid survived the Unicode round trip intact — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-14-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one closed box of roughly 1 : 2 : 3 proportions, whole, with no missing or corrupted face. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -rf "$RUN_DIR/evidence/tc-07-14 exports"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <H> }
```

---

### TC-07-15: overwriting an existing file replaces it deterministically

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §3.5 (write semantics), `verification-design.md` §6

**Given** no stale target — verify: `rm -f "$RUN_DIR/evidence/tc-07-15-over.stl"`  
**And** `sphere-r10.FCStd` is open as `<H>` with `<OBJ>` resolved. A curved surface is required: on the planar box, `linear` 0.5 and 0.01 give the same 12-facet mesh, so the two writes would be identical — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H> }` names the object  

**When** coarse is exported to the target and `bytes` recorded as `B1`  
```
mcp export_stl { doc: <H>, path: "$RUN_DIR/evidence/tc-07-15-over.stl", objects: [<OBJ>], linear: 0.5 }
```
**And** fine is exported to the SAME path and `bytes` recorded as `B2`  
```
mcp export_stl { doc: <H>, path: "$RUN_DIR/evidence/tc-07-15-over.stl", objects: [<OBJ>], linear: 0.01 }
```
**And** the coarse settings are exported a third time to the same path  

**Then** all three writes return `OK` — verify: each `status` equals `OK`  
**And** the overwrite replaces, it does not append — verify: `stat -c %s "$RUN_DIR/evidence/tc-07-15-over.stl"` after the fine write equals `B2`, not `B1 + B2`  
**And** the reported `bytes` matches the file on disk after each write — verify: `stat -c %s "$RUN_DIR/evidence/tc-07-15-over.stl"` equals that call's `structured_content.bytes`  
**And** repeating identical settings is deterministic — verify: the third write's `bytes` equals `B1` and its `facets` equals the coarse write's `facets`  
**And** each write mints a new `export_id` — verify: the three `structured_content.export_id` values are all distinct  
**And** the stale `export_id` from the coarse write now verifies against the OVERWRITTEN file, so it fails — verify: `verify_export_stl` with the coarse `export_id` after the fine write returns `SPEC_FAILED` on `self_read.facet_count`, which is the intended pairing signal: an `export_id` is only meaningful while its file is unchanged  
**And** an outside tool reads exactly one closed body from the final file — verify: `uv run --with networkx --with lxml python -c "import trimesh;m=trimesh.load('$RUN_DIR/evidence/tc-07-15-over.stl');print(m.is_watertight, len(m.split()), m.volume)"` prints `True`, `1`, and a volume below `4188.79` but within the coarse band of it (`(2/3) * 0.5 * 1256.64`, about `418.88`). An appended file would read back as two bodies or fail to load; the bridge's `bytes` field cannot show that, so `trimesh` on the file is the outside witness.  
**And** *(visual)* the model is framed — verify: re-import the final file as `<H_RT>` with the re-import recipe (STL, path `$RUN_DIR/evidence/tc-07-15-over.stl`), then `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the re-imported mesh is one coarse sphere — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-15-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a single closed round body with visibly coarse flat facets, not two overlapping bodies and not a torn surface. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-15-over.stl"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <H> }
```

---

### TC-07-16: a FAILED export leaves NO file at the target path

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (AD-9 no partial artifact), `mcp-tools-design.md` §3.5

**Given** no files at any of the failure targets — verify: `rm -f "$RUN_DIR/evidence/tc-07-16-fail-"*.step "$RUN_DIR/evidence/tc-07-16-fail-"*.stl "$RUN_DIR/evidence/tc-07-16-fail-"*.3mf`  
**And** `box-10-20-30.FCStd` is open as `<H>` with `<OBJ>` resolved — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H> }` names the object  

**When** each failure mode is driven at a distinct target path  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-07-16-fail-multi.step", objects: [<OBJ>, <OBJ>] }
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-07-16-fail-unknown.step", objects: ["NoSuchObject"] }
mcp export_stl  { doc: <H>, path: "$RUN_DIR/evidence/tc-07-16-fail-defl.stl", objects: [<OBJ>], linear: 0.00001 }
mcp export_3mf  { doc: <H>, path: "$RUN_DIR/evidence/tc-07-16-fail-defl.3mf", objects: [<OBJ>], angular: 0.0 }
```
**And** a write into a directory that does not exist is attempted  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-07-16-no-such-dir/x.step", objects: [<OBJ>] }
```

**Then** every failure returns a non-`OK` status — verify: each envelope `status` is `INVALID_INPUT` or `RECOMPUTE_ERROR`, never `OK`  
**And** no file exists at any failure target — verify: `ls "$RUN_DIR/evidence/tc-07-16-fail-"*` reports no such files  
**And** no zero-byte stub is left — verify: `find "$RUN_DIR/evidence" -name "tc-07-16-fail-*" -size 0` returns nothing  
**And** the missing-directory write created no directory — verify: `ls -d "$RUN_DIR/evidence/tc-07-16-no-such-dir"` reports no such directory  
**And** no `export_id` was minted for a failed write — verify: none of the failure envelopes carries a `structured_content.export_id`  
**And** a later successful export to the same path still works — verify: re-running the multi-object target with a single-element `objects` returns `OK` and the file now exists  
**And** an independent re-import of that recovered file yields the whole box — verify: re-import it as `<H_RT>` with the re-import recipe (STEP, path `$RUN_DIR/evidence/tc-07-16-fail-multi.step`) and read `mcp query_mass_properties { doc: <H_RT>, object: "Reimport" }`; it is within 0.1 % of `6000.0`. The filesystem absence of the failure targets is rank-2 evidence on its own; this re-import shows the successful write was not polluted by the refused ones.  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the recovered export is a complete box — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-16-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one closed box of roughly 1 : 2 : 3 proportions, with no stray fragment or partial surface left over from an earlier refused write. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-16-fail-multi.step"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <H> }
```

---

### TC-07-17: an unknown or stale export_id is refused

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (export registry), `mcp-tools-design.md` §3.3

**Given** a document is open to carry the call — verify: `document_list` names the handle  
**And** `box-10-20-30.FCStd` is open as `<H>` — verify: `mcp document_open` returns `OK`  
**And** the framed starting state is captured — verify: run Show All and fit the model, then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-17-before.png"}' | & cua-driver call get_window_state`  

**When** a verify is made against an id that was never minted  
```
mcp verify_export_step { doc: <H>, export_id: "fcb-export:bogus" }
mcp verify_export_stl  { doc: <H>, export_id: "fcb-export:bogus" }
mcp verify_export_3mf  { doc: <H>, export_id: "fcb-export:bogus" }
```
**And** STL is exported to `$RUN_DIR/evidence/tc-07-17-stale.stl`, the document closed, reopened as `<H2>`, then the OLD `export_id` verified against `<H2>` — the registry entry still names the closed handle  

**Then** all three unknown-id calls return `INVALID_INPUT` — verify: each envelope `status` equals `INVALID_INPUT`  
**And** the message names the id — verify: each `detail.message` equals `unknown or stale export_id: fcb-export:bogus`  
**And** the exception class is recorded — verify: each `detail.data.exception` equals `ValidationError`  
**And** an empty `export_id` string is refused distinctly — verify: `export_id: ""` returns `INVALID_INPUT` with message `missing required 'export_id'`  
**And** the reopened-document case is refused — verify: the reopened-handle verify returns `INVALID_INPUT` with a message starting `export_id ` and containing `does not belong to document`  
**And** no crash — verify: `mcp query_capabilities {}` immediately after still returns `OK`  
**And** the exported file on disk was not touched by any refusal — verify: `uv run --with networkx --with lxml python -c "import trimesh;m=trimesh.load('$RUN_DIR/evidence/tc-07-17-stale.stl');print(m.is_watertight, m.volume)"` prints `True` and a volume near `6000.0`. A refusal is meant to read no file at all; `trimesh` reading it back intact is the outside witness that none did.  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H2> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the reopened document is intact after the four refusals — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-17-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: the same single whole box in both, with no error dialog and no emptied viewport. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-17-stale.stl"
```
```
mcp document_close { doc: <H2> }
```

---

### TC-07-18: a format-crossed export_id is refused by every verifier

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (format binding), `mcp-tools-design.md` §3.3

**Given** no stale targets — verify: `rm -f "$RUN_DIR/evidence/tc-07-18-x.step" "$RUN_DIR/evidence/tc-07-18-x.stl" "$RUN_DIR/evidence/tc-07-18-x.3mf"`  
**And** `box-10-20-30.FCStd` is open as `<H>` with `<OBJ>` resolved — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H> }` names the object  
**And** all three formats are exported to `$RUN_DIR/evidence/tc-07-18-x.step`, `$RUN_DIR/evidence/tc-07-18-x.stl`, `$RUN_DIR/evidence/tc-07-18-x.3mf` — verify: each returns `OK`; keep `<EID_STEP>`, `<EID_STL>`, `<EID_3MF>`; record each file's size with `stat -c %s`  

**When** every verifier is crossed against a foreign format id  
```
mcp verify_export_step { doc: <H>, export_id: <EID_STL> }
mcp verify_export_step { doc: <H>, export_id: <EID_3MF> }
mcp verify_export_stl  { doc: <H>, export_id: <EID_STEP> }
mcp verify_export_stl  { doc: <H>, export_id: <EID_3MF> }
mcp verify_export_3mf  { doc: <H>, export_id: <EID_STEP> }
mcp verify_export_3mf  { doc: <H>, export_id: <EID_STL> }
```

**Then** all six crossed calls return `INVALID_INPUT` — verify: every envelope `status` equals `INVALID_INPUT`  
**And** the STEP verifier names the format mismatch — verify: `verify_export_step` on `<EID_STL>` has `detail.message` equal to `export_id <EID_STL> is not a step export`  
**And** the STL verifier names its format — verify: `verify_export_stl` on `<EID_STEP>` has `detail.message` equal to `export_id <EID_STEP> is not a stl export`  
**And** the 3MF verifier names its format — verify: `verify_export_3mf` on `<EID_STL>` has `detail.message` equal to `export_id <EID_STL> is not a 3mf export`  
**And** a crossed call never reads the file — verify: the envelopes carry no `structured_content.checks`; refusal happens before any oracle leg runs  
**And** the matched pairings still pass — verify: each verifier against its OWN id returns `OK`, proving the refusals are format-specific and not blanket failures  
**And** all three files are byte-identical to before the crossing — verify: `stat -c %s` on each of the three paths returns the sizes recorded in the `Given`, and `uv run --with networkx --with lxml python -c "import trimesh;m=trimesh.load('$RUN_DIR/evidence/tc-07-18-x.stl');print(m.is_watertight, m.volume)"` prints `True` and a volume near `6000.0`. The "never reads the file" claim is made by the code under test; unchanged bytes and a clean outside read are the witness.  
**And** *(visual)* the model is framed — verify: re-import the STEP file as `<H_RT>` with the re-import recipe (STEP, path `$RUN_DIR/evidence/tc-07-18-x.step`), then `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the written artifact survived the crossed refusals — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-18-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one whole box of roughly 1 : 2 : 3 proportions, with no damaged or missing face. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-18-x.step" "$RUN_DIR/evidence/tc-07-18-x.stl" "$RUN_DIR/evidence/tc-07-18-x.3mf"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <H> }
```

---

### TC-07-19: an export_id from another document fails the ownership check

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (registry ownership), `mcp-tools-design.md` §3.3

**Given** two distinct golden models present — verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd benchmarks/g0/golden-models/sphere-r10.FCStd`  
**And** `box-10-20-30.FCStd` is open as `<HA>` and `sphere-r10.FCStd` as `<HB>`; both stay open — verify: `mcp document_list {}` lists both handles  

**When** an export is made from `<HA>` and `<EID_A>` kept  
```
mcp export_step { doc: <HA>, path: "$RUN_DIR/evidence/tc-07-19-own.step", objects: [<OBJ_A>] }
```
**And** that id is verified against the OTHER document  
```
mcp verify_export_step { doc: <HB>, export_id: <EID_A> }
```

**Then** the cross-document verify is refused — verify: the crossed call returns `status` equal to `INVALID_INPUT`  
**And** the message names both the id and the wrong document — verify: `detail.message` equals `export_id <EID_A> does not belong to document <HB>`  
**And** refusal precedes any file read — verify: the envelope carries no `structured_content.checks` and no `subject`  
**And** the correct pairing still passes — verify: `verify_export_step { doc: <HA>, export_id: <EID_A> }` returns `OK`  
**And** the ownership check is not order-dependent — verify: exporting from `<HB>` to `$RUN_DIR/evidence/tc-07-19-own-b.step` and verifying that id against `<HA>` is refused with the symmetric message  
**And** neither document was disturbed — verify: `verify_recompute` on `<HA>` and `<HB>` both return `OK` after the refusals  
**And** an independent re-import shows each file holds its own document's shape — verify: re-import `$RUN_DIR/evidence/tc-07-19-own.step` as `<H_RT>` with the re-import recipe (STEP) and read `mcp query_mass_properties { doc: <H_RT>, object: "Reimport" }`; it is within 0.1 % of `6000.0`, the box, not `4188.7902`, the sphere. The registry's ownership message is a claim by the code under test; the shape re-measured from each file is the outside witness that no crossover happened on disk.  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the re-imported solid is the box from `<HA>`, not the sphere from `<HB>` — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-19-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one rectangular body with flat faces and sharp straight edges. A round body here means the registry resolved the wrong document's shape, which is the exact confusion the ownership check exists to prevent. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-19-own.step" "$RUN_DIR/evidence/tc-07-19-own-b.step"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <HA> }
mcp document_close { doc: <HB> }
```

---

### TC-07-20: planted-fault fixtures are caught, given their reference checks

**Priority**: Critical
**Design Ref**: `verification-design.md` §6.3 (fault detection), §5 (assertion vocabulary)

**Given** both fixtures and their `case.yaml` files present — verify: `ls benchmarks/g0/fault-injection/wrong-volume/fixture.FCStd benchmarks/g0/fault-injection/non-watertight-open-shell/case.yaml`  
**And** the reference checks are read out of each fixture's `case.yaml` — they are the CORRECT-shape values that the fixture deviates from. Passing bare checks would let a wrong-but-valid shape through, so the reference checks are required, never optional — verify:  
```bash
python3 -c "import yaml,sys;print(yaml.safe_load(open(sys.argv[1]))['assertions']['checks'])" \
  benchmarks/g0/fault-injection/wrong-volume/case.yaml
```
For `wrong-volume` this is `[{fn: expect_volume, expect: 6000, tol: {rel: 0.001}}]`; for
`non-watertight-open-shell` it is
`[{fn: expect_watertight, expect: true}, {fn: expect_solid_count, expect: 1}]`.

**When** each fixture is opened, its sole object resolved, and graded with those exact checks  
```
mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/fault-injection/wrong-volume/fixture.FCStd" }
mcp verify_shape { doc: <H>, object: <OBJ>, checks: [{ fn: "expect_volume", expect: 6000, tol: { rel: 0.001 } }] }
```
```
mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/fault-injection/non-watertight-open-shell/fixture.FCStd" }
mcp verify_shape { doc: <H2>, object: <OBJ2>, checks: [
  { fn: "expect_watertight", expect: true },
  { fn: "expect_solid_count", expect: 1 }
] }
```

**Then** `wrong-volume` is caught — verify: its `verify_shape` returns `status` equal to `SPEC_FAILED`, never `OK`  
**And** the failing check names the planted defect — verify: the `assert.expect_volume` check has `passed: false` with `measured` near `7200.0` against `expected` `6000.0` (a 12x20x30 box where the reference is 10x20x30)  
**And** `non-watertight-open-shell` is caught — verify: its `verify_shape` returns `status` equal to `SPEC_FAILED`  
**And** the watertight check is the primary signal — verify: the `shape.watertight` check has `passed: false` with `measured: false` against `expected: true`  
**And** the solid-count diagnostic confirms it — verify: the `shape.solid_count` check has `measured` equal to `0`, an open shell carrying no solid  
**And** bare checks would NOT catch the volume fault — verify: `verify_shape` on the same fixture with `checks` omitted returns `OK`, which is exactly why the reference checks must be passed in  
**And** the failure detail names each failed check id — verify: `detail.message` lists the failed ids, and `detail.code` equals `SPEC_FAILED`  
**And** the clean control is not flagged — verify: `benchmarks/g0/fault-injection/clean-control/fixture.FCStd` graded with its own `case.yaml` checks returns `OK`  
**And** an outside tool confirms both planted faults from exported files — verify: export each fixture to STL under `$RUN_DIR/evidence/tc-07-20-<fault>.stl`, then `uv run --with networkx --with lxml python -c "import trimesh;m=trimesh.load('$RUN_DIR/evidence/tc-07-20-wrong-volume.stl');print(m.volume)"` prints a value near `7200.0`, and the same on the open-shell file prints `is_watertight` `False`. **This is the evidence for the `wrong-volume` fault.** `verify_shape` reporting `7200.0` is a claim by the code under test; `trimesh` measuring the exported mesh is the outside witness.  
**And** *(visual)* the open-shell fixture is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <H2> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the open-shell defect is plainly visible — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-20-open-shell.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one thin flat open sheet and no enclosed body. The fixture is a single planar face (a shell with one face and no solid, `shape.solid_count` `0`), so the open surface itself is the visible defect. The `wrong-volume` fixture is a dimension error (12x20x30 in place of 10x20x30) that nothing on screen distinguishes from the correct box in isolation — it gets no visual claim, and the `trimesh` read above carries its evidence instead. The judgement here is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-20-wrong-volume.stl" "$RUN_DIR/evidence/tc-07-20-open-shell.stl"
```
```
mcp document_close { doc: <H> }
mcp document_close { doc: <H2> }
```

---

### TC-07-21: an export never self-reports verified; only the paired verify completes it

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (AD-9 pairing rule), `mcp-tools-design.md` §3.5

**Given** no stale targets — verify: `rm -f "$RUN_DIR/evidence/tc-07-21-pair.step" "$RUN_DIR/evidence/tc-07-21-pair.stl" "$RUN_DIR/evidence/tc-07-21-pair.3mf"`  
**And** `box-10-20-30.FCStd` is open as `<H>` with `<OBJ>` resolved — verify: `mcp document_open` returns `OK` and `mcp query_tree_summary { doc: <H> }` names the object  

**When** all three formats are written and each write result read  
```
mcp export_step { doc: <H>, path: "$RUN_DIR/evidence/tc-07-21-pair.step", objects: [<OBJ>] }
mcp export_stl  { doc: <H>, path: "$RUN_DIR/evidence/tc-07-21-pair.stl",  objects: [<OBJ>] }
mcp export_3mf  { doc: <H>, path: "$RUN_DIR/evidence/tc-07-21-pair.3mf",  objects: [<OBJ>] }
```
**And** each paired verifier is run against its own `export_id`  

**Then** every write reports `verified: false` — verify: all three `structured_content.verified` values are `false`; no write result anywhere carries `verified: true`  
**And** the write verdict is `written`, not `verified` — verify: each envelope `text` ends `export written -> <path>.`  
**And** the write result carries no checks — verify: none of the three write envelopes has a `structured_content.checks` array; grading only exists in the verify result  
**And** the verify result is a validation report, not an export result — verify: each verify envelope's `structured_content.schema` equals `fcb.validation-report/1`, while the write envelope's `schema` is `fcb.result-envelope/1` with a plain payload  
**And** the verify verdict is derived from its checks — verify: each verify `structured_content.verdict` equals `OK` and every entry of `structured_content.checks` has `passed: true`  
**And** a write to an unverifiable file is still `OK` at write time — verify: after truncating `$RUN_DIR/evidence/tc-07-21-pair.stl` to 0 bytes, the ALREADY-RETURNED write result is unchanged while `verify_export_stl` now returns a non-`OK` status, which is the whole point of the pairing  
**And** the status set stays closed across all six calls — verify: every observed `status` is one of `OK`, `SPEC_FAILED`, `RECOMPUTE_ERROR`, `TIMEOUT`, `OOM_KILLED`, `WORKER_CRASHED`, `INVALID_INPUT`  
**And** an outside tool confirms the STEP file the verifier passed really holds the box — verify: re-import `$RUN_DIR/evidence/tc-07-21-pair.step` as `<H_RT>` with the re-import recipe (STEP) and read `mcp query_mass_properties { doc: <H_RT>, object: "Reimport" }`; it is within 0.1 % of `6000.0`. A `verdict: OK` over a file that re-reads as nothing is the defect the pairing rule exists to catch, and only a read outside the verifier can show it.  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <H_RT> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the verified artifact is a real box on screen — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-07-21-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one closed box of roughly 1 : 2 : 3 proportions. An empty viewport, or a body of the wrong shape, means the `OK` verdict was a false claim. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-07-21-pair.step" "$RUN_DIR/evidence/tc-07-21-pair.stl" "$RUN_DIR/evidence/tc-07-21-pair.3mf"
```
```
mcp document_close { doc: <H_RT> }
mcp document_close { doc: <H> }
```
