# TC-07: Verification & Export Pairing

Validates AD-9: an export is complete ONLY when its paired `verify_export_*` passes, and a failed
export leaves no file at the target path. Also covers the whole `verify_*` read-only surface —
`verify_shape`, `verify_sketch`, `verify_recompute` — against the real golden models and the
planted-fault fixtures. STEP, STL, and 3MF are all exercised; 3MF closes a gap the automated
sweeps do not reach. Run the scenarios in order against the live GUI bridge on `:8765`.

## Prerequisites
- [ ] FreeCAD GUI open, addon loaded, proxy serving `:8765` (verify: `netstat -ano | grep :8765` shows LISTENING)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/*.FCStd` lists 5 files)
- [ ] Fault fixtures present (verify: `ls benchmarks/g0/fault-injection/wrong-volume/case.yaml benchmarks/g0/fault-injection/non-watertight-open-shell/case.yaml`)
- [ ] `_automation/` exists and is writable (verify: `mkdir -p _automation && touch _automation/.tc07 && rm _automation/.tc07`)
- [ ] Oracle libraries importable in the external proxy env (verify: `uv run python -c "import trimesh, lib3mf"`)
- [ ] The export tools declare NO `confirm` property; only `sketch_*` and `feature_*` do. Because every schema sets `additionalProperties: false`, passing `confirm` to an export is a schema rejection (verify: `python3 -c "import json;d=json.load(open('_automation/tool_surface.json'));print([k for k,v in d.items() if v['mut'] and 'confirm' in v['props']])"` lists no `export_*` tool)

---

### TC-07-01: verify_shape covers the whole closed assertion vocabulary

**Priority**: Critical
**Design Ref**: `verification-design.md` §5 (shape assertions), `mcp-tools-design.md` §3.3 (verify surface)

**Preconditions**:
- [ ] `box-10-20-30.FCStd` closed from any prior case (verify: `document_list` does not name it)

**Steps**:
1. Open the golden box:
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd" }
   ```
   Record the returned `doc` handle as `<H>`; name its sole object `<OBJ>` via
   `mcp query_tree_summary { doc: <H> }` (read `tree[0].name`).
2. Run all five assertion kinds in one call:
   ```
   mcp verify_shape { doc: <H>, object: <OBJ>, checks: [
     { fn: "expect_volume", expect: 6000.0, tol: { rel: 0.001 } },
     { fn: "expect_bbox", expect: [10.0, 20.0, 30.0], tol: { abs: 0.05 } },
     { fn: "expect_solid_count", expect: 1 },
     { fn: "expect_valid", expect: true },
     { fn: "expect_watertight", expect: true }
   ] }
   ```

**Checkpoints**:
- [ ] CP1: envelope status is `OK` — verify: `status` equals `OK` and `detail` is `null`
- [ ] CP2: five checks returned, one per `fn` — verify: `structured_content.checks` has ids `shape.volume`, `shape.bbox`, `shape.solid_count`, `shape.valid`, `shape.watertight`
- [ ] CP3: every check passed — verify: no element of `structured_content.checks` has `passed: false`
- [ ] CP4: measured volume is the analytic 6000.0 — verify: the `shape.volume` check `measured` equals `6000.0`
- [ ] CP5: verdict is derived, not asserted — verify: `structured_content.verdict` equals `OK` and equals the envelope `status`
- [ ] CP6: an unknown assertion `fn` is refused — verify: `mcp verify_shape { doc: <H>, object: <OBJ>, checks: [{ fn: "expect_genus", expect: 0 }] }` returns `INVALID_INPUT` with message `unknown assertion fn: 'expect_genus'`

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-07-02: verify_shape with no checks is measurement-only

**Priority**: High
**Design Ref**: `verification-design.md` §5 (measured facts), `mcp-tools-design.md` §3.3

**Preconditions**:
- [ ] `cylinder-r5-h20.FCStd` not already open (verify: `document_list` does not name it)

**Steps**:
1. Open the cylinder and resolve its sole object as `<OBJ>`:
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/cylinder-r5-h20.FCStd" }
   mcp query_tree_summary { doc: <H> }
   ```
2. Call with `checks` omitted entirely:
   ```
   mcp verify_shape { doc: <H>, object: <OBJ> }
   ```

**Checkpoints**:
- [ ] CP1: status is `OK` — verify: `status` equals `OK`
- [ ] CP2: the five measured facts are reported — verify: `structured_content.checks` has exactly the ids `shape.volume`, `shape.bbox`, `shape.solid_count`, `shape.valid`, `shape.watertight`
- [ ] CP3: no check carries an `expected` — verify: no element of `structured_content.checks` has an `expected` key
- [ ] CP4: every fact is marked `passed: true` (nothing was asserted, so nothing can fail) — verify: all `checks[*].passed` are `true`
- [ ] CP5: the measured volume matches the analytic cylinder — verify: the `shape.volume` `measured` is within 0.001 of `1570.7963`
- [ ] CP6: measurement-only mode never grades — verify: repeating the call with `expect_volume` of `1.0` returns `SPEC_FAILED`, proving CP4's `OK` came from the absent `checks`, not from a lenient grader

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-07-03: verify_sketch PASS is equivalent to FullyConstrained, both directions

**Priority**: Critical
**Design Ref**: `verification-design.md` §5 (AD-8 sketch grading), `mcp-tools-design.md` §3.3

**Preconditions**:
- [ ] A scratch document exists for sketch work (verify: `mcp document_create { label: "tc07_sketch" }` returns `OK`; `document_create` declares `label`, not `name`, and takes no `confirm`)

**Steps**:
1. Create a sketch on the XY plane and add one line segment:
   ```
   mcp sketch_create { doc: <H>, plane: "XY", confirm: { preview_id: <P> } }
   mcp sketch_add_geometry { doc: <H>, sketch: <SK>, geometry: [
     { kind: "line_segment", start: [0, 0], end: [10, 0] }
   ], confirm: { preview_id: <P> } }
   ```
   Each mutation needs its own `preview_dry_run` token; see TC-08 for the confirm protocol.
2. Grade the under-constrained sketch:
   ```
   mcp verify_sketch { doc: <H>, sketch: <SK> }
   ```
3. Add constraints until `FullyConstrained` holds (Coincident to origin, Horizontal, DistanceX),
   then grade again with the same call.

**Checkpoints**:
- [ ] CP1: the under-constrained sketch fails — verify: step 2 returns status `SPEC_FAILED` with the failed check id `sketch.fully_constrained`
- [ ] CP2: the reported `dof` is greater than 0 for the failing sketch — verify: `structured_content.subject.dof` is a positive integer
- [ ] CP3: the failure detail names the measured state — verify: the `sketch.fully_constrained` check `detail.message` matches `dof=<n>, conflicting=0, malformed=0, evaluate_bad=False, degenerate=0`
- [ ] CP4: the fully-constrained sketch passes — verify: step 3 returns status `OK`
- [ ] CP5: `dof` is 0 exactly when the verdict is `OK` — verify: step 3's `structured_content.subject.dof` equals `0` and `subject.fully_constrained` is `true`
- [ ] CP6: redundant constraints warn, never fail — verify: adding a duplicate Horizontal constraint keeps status `OK` and places a `sketch.redundant` entry in `structured_content.warnings`, not in `checks`
- [ ] CP7: a non-sketch object is refused — verify: `mcp verify_sketch { doc: <H>, sketch: <a non-sketch object name> }` returns `INVALID_INPUT` with message `object is not a sketch: <name>`

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-07-04: verify_recompute on a clean document reports no failing objects

**Priority**: Critical
**Design Ref**: `verification-design.md` §5 (recompute grading), `mcp-tools-design.md` §3.3

**Preconditions**:
- [ ] `box40-hole-r5.FCStd` present (verify: `ls benchmarks/g0/golden-models/box40-hole-r5.FCStd`)

**Steps**:
1. Open the genus-1 golden model:
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box40-hole-r5.FCStd" }
   ```
2. Recompute-grade it:
   ```
   mcp verify_recompute { doc: <H> }
   ```

**Checkpoints**:
- [ ] CP1: status is `OK` — verify: `status` equals `OK` and `detail` is `null`
- [ ] CP2: the clean path emits exactly one passed check — verify: `structured_content.checks` is a single entry with id `recompute.clean` and `passed: true`
- [ ] CP3: no failing objects are listed — verify: `structured_content.subject.failing_objects` is an empty array
- [ ] CP4: the summary text states the clean result — verify: the envelope `text` equals `Recompute clean: no errors.`
- [ ] CP5: the call is read-only — verify: `mcp query_mass_properties { doc: <H>, object: <OBJ> }` returns the same `volume.value` before and after step 2
- [ ] CP6: the banner records the build — verify: `structured_content.banner.freecad_version` is non-empty and `banner.element_map_version` is an integer or `null`

**Cleanup**:
```
mcp document_close { doc: <H> }
```

---

### TC-07-05: export_step writes both AP schemas and never self-reports verified

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (export pairing, AD-9), `mcp-tools-design.md` §3.5 (export surface)

**Preconditions**:
- [ ] `_automation/` writable (verify: `ls -d _automation`)
- [ ] No stale target files (verify: `rm -f _automation/tc07_ap242.step _automation/tc07_ap214.step`)

**Steps**:
1. Open `box-10-20-30.FCStd` as `<H>`, resolve `<OBJ>`.
2. Export with the default schema:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_ap242.step", objects: [<OBJ>], ap: "AP242" }
   ```
3. Export with the other enum value:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_ap214.step", objects: [<OBJ>], ap: "AP214" }
   ```

**Checkpoints**:
- [ ] CP1: both exports return `OK` — verify: both envelopes carry `status` equal to `OK`
- [ ] CP2: both results carry `verified: false` — verify: `structured_content.verified` is `false` in both, never `true`
- [ ] CP3: both mint a distinct `export_id` — verify: both `structured_content.export_id` values start with `fcb-export:` and differ from each other
- [ ] CP4: the reported `bytes` matches the file on disk — verify: `stat -c %s _automation/tc07_ap242.step` equals the result's `structured_content.bytes`
- [ ] CP5: the AP schema is pinned per call — verify: `grep -c "AP242" _automation/tc07_ap242.step` is non-zero and `grep -c "AP214" _automation/tc07_ap214.step` is non-zero
- [ ] CP6: a value outside the enum is refused at the schema gate — verify: `ap: "AP203"` returns an MCP protocol rejection (`isError` set, no envelope)
- [ ] CP7: the summary text names the written path — verify: the envelope `text` equals `STEP export written -> _automation/tc07_ap242.step.`

**Cleanup**:
```bash
rm -f _automation/tc07_ap242.step _automation/tc07_ap214.step
```
```
mcp document_close { doc: <H> }
```

---

### TC-07-06: export_stl and export_3mf come from one tessellation source

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (single tessellation, #25311), `mcp-tools-design.md` §3.5

**Preconditions**:
- [ ] No stale mesh targets (verify: `rm -f _automation/tc07_same.stl _automation/tc07_same.3mf`)

**Steps**:
1. Open `sphere-r10.FCStd` as `<H>` (a curved surface makes the deflection observable), resolve `<OBJ>`.
2. Write both formats with the SAME deflection pair:
   ```
   mcp export_stl { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_same.stl", objects: [<OBJ>], linear: 0.1, angular: 0.5 }
   mcp export_3mf { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_same.3mf", objects: [<OBJ>], linear: 0.1, angular: 0.5 }
   ```

**Checkpoints**:
- [ ] CP1: both exports return `OK` — verify: both envelopes carry `status` equal to `OK`
- [ ] CP2: the two formats report the identical facet count — verify: the STL result `structured_content.facets` equals the 3MF result `structured_content.facets`
- [ ] CP3: both carry `verified: false` — verify: `structured_content.verified` is `false` in both
- [ ] CP4: both files exist and are non-empty — verify: `stat -c %s _automation/tc07_same.stl _automation/tc07_same.3mf` prints two values greater than 0
- [ ] CP5: the paired verifiers both pass — verify: `verify_export_stl` and `verify_export_3mf` on the two `export_id`s both return `OK`
- [ ] CP6: the self-read facet count matches the written count in both — verify: in both verify reports, the `self_read.facet_count` check has `measured` equal to `expected` and `passed: true`
- [ ] CP7: a zero-facet tessellation is refused, not written — verify: an angular deflection of `0` returns `INVALID_INPUT` with a message starting `deflection out of range:`

**Cleanup**:
```bash
rm -f _automation/tc07_same.stl _automation/tc07_same.3mf
```
```
mcp document_close { doc: <H> }
```

---

### TC-07-07: verify_export_step re-imports and grades against the recorded source

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (STEP round-trip), `mcp-tools-design.md` §3.3

**Preconditions**:
- [ ] No stale target (verify: `rm -f _automation/tc07_rt.step`)

**Steps**:
1. Open `box40-hole-r5.FCStd` as `<H>`, resolve `<OBJ>`.
2. Export STEP and keep the returned `export_id` as `<EID>`:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_rt.step", objects: [<OBJ>] }
   ```
3. Run the paired verifier:
   ```
   mcp verify_export_step { doc: <H>, export_id: <EID> }
   ```

**Checkpoints**:
- [ ] CP1: status is `OK` — verify: `status` equals `OK` and `structured_content.verdict` equals `OK`
- [ ] CP2: exactly three round-trip checks run — verify: `structured_content.checks` has the ids `export_step.volume`, `export_step.valid`, `export_step.topology_counts`
- [ ] CP3: the volume band is the STEP relative tolerance — verify: the `export_step.volume` check `tolerance` equals `{ "rel": 0.001 }`
- [ ] CP4: the re-imported volume matches the genus-1 analytic value — verify: the `export_step.volume` `measured` is within 0.1 % of `15214.6018`
- [ ] CP5: the re-imported shape is valid — verify: the `export_step.valid` check has `measured: true` and `passed: true`
- [ ] CP6: topology counts are EQUAL, not banded — verify: the `export_step.topology_counts` check `measured` object equals its `expected` object for `faces`, `edges`, and `solids`
- [ ] CP7: the subject names the verified artifact — verify: `structured_content.subject.export_id` equals `<EID>` and `subject.path` equals `_automation/tc07_rt.step`
- [ ] CP8: the temp re-import document is closed — verify: `mcp document_list {}` lists no handle whose name starts with `FCB_TMP_`

**Cleanup**:
```bash
rm -f _automation/tc07_rt.step
```
```
mcp document_close { doc: <H> }
```

---

### TC-07-08: verify_export_stl merges its two oracle legs plus the self-read, and they agree

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (independent oracles, disagreement is FAIL), `mcp-tools-design.md` §3.3

**Preconditions**:
- [ ] trimesh importable in the proxy env (verify: `uv run python -c "import trimesh"`)
- [ ] No stale target (verify: `rm -f _automation/tc07_legs.stl`)

**Steps**:
1. Open `box-10-20-30.FCStd` as `<H>`, resolve `<OBJ>`.
2. Export STL, keep `<EID>`:
   ```
   mcp export_stl { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_legs.stl", objects: [<OBJ>] }
   ```
3. Verify:
   ```
   mcp verify_export_stl { doc: <H>, export_id: <EID> }
   ```

**Checkpoints**:
- [ ] CP1: status is `OK` — verify: `status` equals `OK`
- [ ] CP2: the trimesh leg reported all five of its checks — verify: `structured_content.checks` holds the ids `trimesh_stl.watertight`, `trimesh_stl.winding_consistent`, `trimesh_stl.is_volume`, `trimesh_stl.volume_band`, `trimesh_stl.euler`
- [ ] CP3: the stdlib leg reported all four of its checks — verify: `structured_content.checks` holds the ids `stl2.facets`, `stl2.manifold_edge_pairing`, `stl2.local_winding`, `stl2.non_degenerate`
- [ ] CP4: the FreeCAD self-read leg is merged in — verify: `structured_content.checks` holds `self_read.facet_count` and `self_read.vertex_count`, both `passed: true`
- [ ] CP5: the two oracles agree — verify: the `oracle.agreement` check has `passed: true` and its `measured` object reads `{"trimesh_stl": true, "stdlib_stl": true}`
- [ ] CP6: the volume band is deflection-derived, never ±0.1 % — verify: `structured_content.volume_band` equals `(2/3) * linear * area` for the recorded tessellation, and the `trimesh_stl.volume_band` check `tolerance` carries an `abs` key, not a `rel` key
- [ ] CP7: the recorded tessellation is echoed — verify: `structured_content.tess` equals `{ "linear": 0.1, "angular": 0.5 }` for a default-deflection export
- [ ] CP8: a corrupted file fails closed rather than raising — verify: truncating the STL to 100 bytes and re-running `verify_export_stl` returns `SPEC_FAILED`, not `INVALID_INPUT` and not a crash

**Cleanup**:
```bash
rm -f _automation/tc07_legs.stl
```
```
mcp document_close { doc: <H> }
```

---

### TC-07-09: verify_export_3mf merges the lib3mf container and geometry layers with the self-read

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (3MF oracle layers, unit-lie guard), `mcp-tools-design.md` §3.3

**Preconditions**:
- [ ] lib3mf importable in the proxy env (verify: `uv run python -c "import lib3mf"`)
- [ ] No stale target (verify: `rm -f _automation/tc07_legs.3mf`)

**Steps**:
1. Open `cylinder-r5-h20.FCStd` as `<H>`, resolve `<OBJ>`.
2. Export 3MF, keep `<EID>`:
   ```
   mcp export_3mf { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_legs.3mf", objects: [<OBJ>] }
   ```
3. Verify:
   ```
   mcp verify_export_3mf { doc: <H>, export_id: <EID> }
   ```

**Checkpoints**:
- [ ] CP1: status is `OK` — verify: `status` equals `OK`
- [ ] CP2: the lib3mf container layer reported its four checks — verify: `structured_content.checks` holds `lib3mf.parses`, `lib3mf.unit_millimeter`, `lib3mf.manifold_and_oriented`, `lib3mf.metadata_present`
- [ ] CP3: the trimesh geometry layer is built from the lib3mf arrays, not a second file read — verify: `structured_content.checks` holds `trimesh_3mf.watertight`, `trimesh_3mf.winding_consistent`, `trimesh_3mf.is_volume`, `trimesh_3mf.volume_band`, `trimesh_3mf.euler`
- [ ] CP4: the unit-lie guard passed on both sides — verify: the `lib3mf.unit_millimeter` check `measured` reads `{"unit": 1, "source_is_mm": true}` (confirm the enum with `uv run python -c "import lib3mf; print(int(lib3mf.ModelUnit.MilliMeter))"`) and `passed: true`
- [ ] CP5: every mesh object in the container is manifold — verify: the `lib3mf.manifold_and_oriented` check `measured` reads `{"meshes": 1, "non_manifold": 0}` and `passed: true`
- [ ] CP6: missing metadata never drives a FAIL — verify: the `lib3mf.metadata_present` check is `passed: true` regardless of its `measured` count
- [ ] CP7: the self-read leg is merged in and agrees — verify: `self_read.facet_count` and `self_read.vertex_count` are both `passed: true`, and `oracle.agreement` reads `{"lib3mf": true}` with `passed: true`
- [ ] CP8: the mesh volume is inside the deflection band, not the STEP band — verify: the `trimesh_3mf.volume_band` `measured` is within `structured_content.volume_band` of `1570.7963`, and that band is smaller than 0.1 % of the volume

**Cleanup**:
```bash
rm -f _automation/tc07_legs.3mf
```
```
mcp document_close { doc: <H> }
```

---

### TC-07-10: custom deflection changes the facet count and the derived volume band

**Priority**: High
**Design Ref**: `verification-design.md` §6 (deflection-derived band), `mcp-tools-design.md` §3.5

**Preconditions**:
- [ ] No stale targets (verify: `rm -f _automation/tc07_coarse.stl _automation/tc07_fine.stl`)

**Steps**:
1. Open `sphere-r10.FCStd` as `<H>`, resolve `<OBJ>`. A doubly-curved surface is the case a
   bbox-relative band underestimates, so the sphere is the required fixture here.
2. Export coarse and fine:
   ```
   mcp export_stl { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_coarse.stl", objects: [<OBJ>], linear: 0.5, angular: 1.0 }
   mcp export_stl { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_fine.stl", objects: [<OBJ>], linear: 0.01, angular: 0.1 }
   ```
3. Verify each with its own `export_id`.

**Checkpoints**:
- [ ] CP1: the finer deflection produces strictly more facets — verify: the fine export's `structured_content.facets` is greater than the coarse export's
- [ ] CP2: both verifies return `OK` — verify: both `verify_export_stl` calls return `status` equal to `OK`
- [ ] CP3: the band tracks the deflection — verify: the coarse verify's `structured_content.volume_band` is 50 times the fine verify's, matching `(2/3) * linear * area` at `linear` 0.5 versus 0.01
- [ ] CP4: the band is never the STEP ±0.1 % — verify: the fine verify's `volume_band` is far below `0.001 * 4188.7902`, and the `trimesh_stl.volume_band` check `tolerance` has an `abs` key with no `rel` key
- [ ] CP5: the coarse mesh volume falls short of the solid but stays inside its own band — verify: the coarse `trimesh_stl.volume_band` `measured` is less than `4188.7902` and its check is `passed: true`
- [ ] CP6: a deflection below the floor is refused before any file is written — verify: `linear: 0.00001` returns `INVALID_INPUT` with a message starting `deflection out of range:` and `ls _automation/tc07_floor.stl` reports no such file

**Cleanup**:
```bash
rm -f _automation/tc07_coarse.stl _automation/tc07_fine.stl
```
```
mcp document_close { doc: <H> }
```

---

### TC-07-11: multi-object selection is refused by the single-shape writers

**Priority**: High
**Design Ref**: `verification-design.md` §6 (fail-closed selection), `mcp-tools-design.md` §3.5

**Preconditions**:
- [ ] No stale targets (verify: `rm -f _automation/tc07_multi.step _automation/tc07_multi.stl _automation/tc07_multi.3mf`)

**Steps**:
1. Open `box-10-20-30.FCStd` as `<H>`, resolve `<OBJ>`.
2. Pass a two-element selection to each writer:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_multi.step", objects: [<OBJ>, <OBJ>] }
   mcp export_stl  { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_multi.stl",  objects: [<OBJ>, <OBJ>] }
   mcp export_3mf  { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_multi.3mf",  objects: [<OBJ>, <OBJ>] }
   ```

**Checkpoints**:
- [ ] CP1: all three writers return `INVALID_INPUT` — verify: each envelope `status` equals `INVALID_INPUT`
- [ ] CP2: the message names the single-shape constraint — verify: each `detail.message` equals `export supports a single object; got multiple`
- [ ] CP3: no partial file is left behind — verify: `ls _automation/tc07_multi.*` reports no such files
- [ ] CP4: an unknown object name inside a one-element selection is a separate refusal — verify: `objects: ["NoSuchObject"]` returns `INVALID_INPUT` with message `unknown object: NoSuchObject`
- [ ] CP5: an empty document is refused distinctly — verify: exporting from a freshly created empty document returns `INVALID_INPUT` with message `document has no objects to export`

**Cleanup**:
```bash
rm -f _automation/tc07_multi.step _automation/tc07_multi.stl _automation/tc07_multi.3mf
```
```
mcp document_close { doc: <H> }
```

---

### TC-07-12: an omitted `objects` exports the document's sole object

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §3.5 (default selection), `verification-design.md` §6

**Preconditions**:
- [ ] No stale target (verify: `rm -f _automation/tc07_default.step`)

**Steps**:
1. Open `box-10-20-30.FCStd` as `<H>` (a single-object document).
2. Export with `objects` absent from the arguments entirely:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_default.step" }
   ```
3. Open `two-box-compound.FCStd` as `<H2>` and repeat the omitted-`objects` export.

**Checkpoints**:
- [ ] CP1: the single-object document exports without a selection — verify: step 2 returns `status` equal to `OK`
- [ ] CP2: the exported shape is the document's sole object — verify: `verify_export_step` on the returned `export_id` returns `OK` with `export_step.volume` `measured` within 0.1 % of `6000.0`
- [ ] CP3: a multi-object document refuses the ambiguous default — verify: step 3 returns `INVALID_INPUT` with message `document has multiple objects; specify 'objects' with the one to export`
- [ ] CP4: the ambiguous case wrote nothing — verify: `ls _automation/tc07_default_compound.step` reports no such file
- [ ] CP5: an empty `objects` array behaves as omitted, not as a selection of none — verify: `objects: []` on the single-object document returns the same `OK` result as CP1

**Cleanup**:
```bash
rm -f _automation/tc07_default.step
```
```
mcp document_close { doc: <H> }
mcp document_close { doc: <H2> }
```

---

### TC-07-13: genus-1 and compound geometry verify correctly

**Priority**: High
**Design Ref**: `verification-design.md` §5 (topology-independent checks), §6 (Euler parity)

**Preconditions**:
- [ ] Both fixtures present (verify: `ls benchmarks/g0/golden-models/box40-hole-r5.FCStd benchmarks/g0/golden-models/two-box-compound.FCStd`)

**Steps**:
1. Open `box40-hole-r5.FCStd` as `<H1>`, resolve `<OBJ1>`. Grade it:
   ```
   mcp verify_shape { doc: <H1>, object: <OBJ1>, checks: [
     { fn: "expect_volume", expect: 15214.6018, tol: { rel: 0.001 } },
     { fn: "expect_solid_count", expect: 1 },
     { fn: "expect_watertight", expect: true }
   ] }
   ```
2. Export it to STL and verify the paired result (the through-hole makes it genus 1, Euler
   characteristic 0).
3. Open `two-box-compound.FCStd` as `<H2>`, resolve `<OBJ2>`. Grade it:
   ```
   mcp verify_shape { doc: <H2>, object: <OBJ2>, checks: [
     { fn: "expect_volume", expect: 2000.0, tol: { rel: 0.001 } },
     { fn: "expect_solid_count", expect: 2 }
   ] }
   ```
4. Read its mass properties:
   ```
   mcp query_mass_properties { doc: <H2>, object: <OBJ2> }
   ```

**Checkpoints**:
- [ ] CP1: the genus-1 solid passes all three checks — verify: step 1 returns `status` equal to `OK` with `shape.volume` `measured` within 0.1 % of `15214.6018`
- [ ] CP2: the through-hole export verifies — verify: step 2's `verify_export_stl` returns `OK`
- [ ] CP3: the Euler check accepts genus 1 — verify: the `trimesh_stl.euler` check has `measured` equal to `0` and `passed: true`, proving the check tests parity and not a fixed value
- [ ] CP4: the compound passes with 2 solids — verify: step 3 returns `status` equal to `OK` with the `shape.solid_count` check `measured` equal to `2`
- [ ] CP5: the compound volume is the analytic 2000.0 — verify: step 3's `shape.volume` `measured` is within 0.001 of `2000.0`
- [ ] CP6: the compound reports a null centre of mass — verify: step 4 returns `status` equal to `OK` with `structured_content.com` equal to `null`
- [ ] CP7: a compound is not watertight under the single-solid rule — verify: `expect_watertight: true` on `<OBJ2>` returns `SPEC_FAILED`, because `_is_watertight` requires exactly one solid

**Cleanup**:
```bash
rm -f _automation/tc07_genus.stl
```
```
mcp document_close { doc: <H1> }
mcp document_close { doc: <H2> }
```

---

### TC-07-14: Unicode, spaces, and a long path are written and re-read correctly

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §3.5 (path handling), `verification-design.md` §6

**Preconditions**:
- [ ] The target directory exists (verify: `mkdir -p "_automation/tc07 exports"`)

**Steps**:
1. Open `box-10-20-30.FCStd` as `<H>`, resolve `<OBJ>`.
2. Export to a path with a space and non-ASCII characters:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07 exports/boîte-立方体.step", objects: [<OBJ>] }
   ```
3. Export to a deliberately long file name (200 characters of `a` before the extension) under the
   same directory.
4. Verify each export through its own `export_id`.

**Checkpoints**:
- [ ] CP1: the Unicode path export returns `OK` — verify: step 2 `status` equals `OK`
- [ ] CP2: the file exists at the exact path given — verify: `ls "_automation/tc07 exports/boîte-立方体.step"` lists the file
- [ ] CP3: the returned `path` is echoed back unmodified — verify: `structured_content.path` equals the string passed in, with no escaping or normalisation
- [ ] CP4: the paired verify re-reads the same file — verify: `verify_export_step` returns `OK` with `subject.path` equal to the Unicode path
- [ ] CP5: the long file name is written or refused cleanly, never half-written — verify: step 3 returns either `OK` with an existing file, or `INVALID_INPUT`/`RECOMPUTE_ERROR` with no file at that path
- [ ] CP6: `bytes` is correct for the Unicode path — verify: `stat -c %s "_automation/tc07 exports/boîte-立方体.step"` equals the result's `structured_content.bytes`

**Cleanup**:
```bash
rm -rf "_automation/tc07 exports"
```
```
mcp document_close { doc: <H> }
```

---

### TC-07-15: overwriting an existing file replaces it deterministically

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §3.5 (write semantics), `verification-design.md` §6

**Preconditions**:
- [ ] No stale target (verify: `rm -f _automation/tc07_over.stl`)

**Steps**:
1. Open `box-10-20-30.FCStd` as `<H>`, resolve `<OBJ>`.
2. Export coarse to the target, record `bytes` as `B1`:
   ```
   mcp export_stl { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_over.stl", objects: [<OBJ>], linear: 0.5 }
   ```
3. Export fine to the SAME path, record `bytes` as `B2`:
   ```
   mcp export_stl { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_over.stl", objects: [<OBJ>], linear: 0.01 }
   ```
4. Export the coarse settings a third time to the same path.

**Checkpoints**:
- [ ] CP1: all three writes return `OK` — verify: each `status` equals `OK`
- [ ] CP2: the overwrite replaces, it does not append — verify: `stat -c %s _automation/tc07_over.stl` after step 3 equals `B2`, not `B1 + B2`
- [ ] CP3: the reported `bytes` matches the file on disk after each write — verify: `stat -c %s _automation/tc07_over.stl` equals that call's `structured_content.bytes`
- [ ] CP4: repeating identical settings is deterministic — verify: the step 4 result's `bytes` equals `B1` and its `facets` equals the step 2 `facets`
- [ ] CP5: each write mints a new `export_id` — verify: the three `structured_content.export_id` values are all distinct
- [ ] CP6: the stale `export_id` from step 2 now verifies against the OVERWRITTEN file, so it fails — verify: `verify_export_stl` with the step 2 `export_id` after step 3 returns `SPEC_FAILED` on `self_read.facet_count`, which is the intended pairing signal: an `export_id` is only meaningful while its file is unchanged

**Cleanup**:
```bash
rm -f _automation/tc07_over.stl
```
```
mcp document_close { doc: <H> }
```

---

### TC-07-16: a FAILED export leaves NO file at the target path

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (AD-9 no partial artifact), `mcp-tools-design.md` §3.5

**Preconditions**:
- [ ] No files at any of the failure targets (verify: `rm -f _automation/tc07_fail_*.step _automation/tc07_fail_*.stl _automation/tc07_fail_*.3mf`)

**Steps**:
1. Open `box-10-20-30.FCStd` as `<H>`, resolve `<OBJ>`.
2. Drive each failure mode at a distinct target path:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_fail_multi.step", objects: [<OBJ>, <OBJ>] }
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_fail_unknown.step", objects: ["NoSuchObject"] }
   mcp export_stl  { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_fail_defl.stl", objects: [<OBJ>], linear: 0.00001 }
   mcp export_3mf  { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_fail_defl.3mf", objects: [<OBJ>], angular: 0.0 }
   ```
3. Attempt a write into a directory that does not exist:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_no_such_dir/x.step", objects: [<OBJ>] }
   ```

**Checkpoints**:
- [ ] CP1: every failure returns a non-`OK` status — verify: each envelope `status` is `INVALID_INPUT` or `RECOMPUTE_ERROR`, never `OK`
- [ ] CP2: no file exists at any failure target — verify: `ls _automation/tc07_fail_*` reports no such files
- [ ] CP3: no zero-byte stub is left — verify: `find _automation -name "tc07_fail_*" -size 0` returns nothing
- [ ] CP4: the missing-directory write created no directory — verify: `ls -d _automation/tc07_no_such_dir` reports no such directory
- [ ] CP5: no `export_id` was minted for a failed write — verify: none of the failure envelopes carries a `structured_content.export_id`
- [ ] CP6: a later successful export to the same path still works — verify: re-running the multi-object target with a single-element `objects` returns `OK` and the file now exists

**Cleanup**:
```bash
rm -f _automation/tc07_fail_multi.step
```
```
mcp document_close { doc: <H> }
```

---

### TC-07-17: an unknown or stale export_id is refused

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (export registry), `mcp-tools-design.md` §3.3

**Preconditions**:
- [ ] A document is open to carry the call (verify: `document_list` names the handle)

**Steps**:
1. Open `box-10-20-30.FCStd` as `<H>`.
2. Verify against an id that was never minted:
   ```
   mcp verify_export_step { doc: <H>, export_id: "fcb-export:bogus" }
   mcp verify_export_stl  { doc: <H>, export_id: "fcb-export:bogus" }
   mcp verify_export_3mf  { doc: <H>, export_id: "fcb-export:bogus" }
   ```
3. Export STL, close the document, reopen it as `<H2>`, then verify the OLD `export_id` against
   `<H2>` — the registry entry still names the closed handle.

**Checkpoints**:
- [ ] CP1: all three unknown-id calls return `INVALID_INPUT` — verify: each envelope `status` equals `INVALID_INPUT`
- [ ] CP2: the message names the id — verify: each `detail.message` equals `unknown or stale export_id: fcb-export:bogus`
- [ ] CP3: the exception class is recorded — verify: each `detail.data.exception` equals `ValidationError`
- [ ] CP4: an empty `export_id` string is refused distinctly — verify: `export_id: ""` returns `INVALID_INPUT` with message `missing required 'export_id'`
- [ ] CP5: the reopened-document case is refused — verify: step 3 returns `INVALID_INPUT` with a message starting `export_id ` and containing `does not belong to document`
- [ ] CP6: no crash — verify: `mcp query_capabilities {}` immediately after still returns `OK`

**Cleanup**:
```bash
rm -f _automation/tc07_stale.stl
```
```
mcp document_close { doc: <H2> }
```

---

### TC-07-18: a format-crossed export_id is refused by every verifier

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (format binding), `mcp-tools-design.md` §3.3

**Preconditions**:
- [ ] No stale targets (verify: `rm -f _automation/tc07_x.step _automation/tc07_x.stl _automation/tc07_x.3mf`)

**Steps**:
1. Open `box-10-20-30.FCStd` as `<H>`, resolve `<OBJ>`.
2. Export all three formats and keep `<EID_STEP>`, `<EID_STL>`, `<EID_3MF>`.
3. Cross every verifier against a foreign format id:
   ```
   mcp verify_export_step { doc: <H>, export_id: <EID_STL> }
   mcp verify_export_step { doc: <H>, export_id: <EID_3MF> }
   mcp verify_export_stl  { doc: <H>, export_id: <EID_STEP> }
   mcp verify_export_stl  { doc: <H>, export_id: <EID_3MF> }
   mcp verify_export_3mf  { doc: <H>, export_id: <EID_STEP> }
   mcp verify_export_3mf  { doc: <H>, export_id: <EID_STL> }
   ```

**Checkpoints**:
- [ ] CP1: all six crossed calls return `INVALID_INPUT` — verify: every envelope `status` equals `INVALID_INPUT`
- [ ] CP2: the STEP verifier names the format mismatch — verify: `verify_export_step` on `<EID_STL>` has `detail.message` equal to `export_id <EID_STL> is not a step export`
- [ ] CP3: the STL verifier names its format — verify: `verify_export_stl` on `<EID_STEP>` has `detail.message` equal to `export_id <EID_STEP> is not a stl export`
- [ ] CP4: the 3MF verifier names its format — verify: `verify_export_3mf` on `<EID_STL>` has `detail.message` equal to `export_id <EID_STL> is not a 3mf export`
- [ ] CP5: a crossed call never reads the file — verify: the envelopes carry no `structured_content.checks`; refusal happens before any oracle leg runs
- [ ] CP6: the matched pairings still pass — verify: each verifier against its OWN id returns `OK`, proving the refusals are format-specific and not blanket failures

**Cleanup**:
```bash
rm -f _automation/tc07_x.step _automation/tc07_x.stl _automation/tc07_x.3mf
```
```
mcp document_close { doc: <H> }
```

---

### TC-07-19: an export_id from another document fails the ownership check

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (registry ownership), `mcp-tools-design.md` §3.3

**Preconditions**:
- [ ] Two distinct golden models present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd benchmarks/g0/golden-models/sphere-r10.FCStd`)

**Steps**:
1. Open `box-10-20-30.FCStd` as `<HA>` and `sphere-r10.FCStd` as `<HB>`; both stay open.
2. Export from `<HA>` and keep `<EID_A>`:
   ```
   mcp export_step { doc: <HA>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_own.step", objects: [<OBJ_A>] }
   ```
3. Verify that id against the OTHER document:
   ```
   mcp verify_export_step { doc: <HB>, export_id: <EID_A> }
   ```

**Checkpoints**:
- [ ] CP1: the cross-document verify is refused — verify: step 3 returns `status` equal to `INVALID_INPUT`
- [ ] CP2: the message names both the id and the wrong document — verify: `detail.message` equals `export_id <EID_A> does not belong to document <HB>`
- [ ] CP3: refusal precedes any file read — verify: the envelope carries no `structured_content.checks` and no `subject`
- [ ] CP4: the correct pairing still passes — verify: `verify_export_step { doc: <HA>, export_id: <EID_A> }` returns `OK`
- [ ] CP5: the ownership check is not order-dependent — verify: exporting from `<HB>` and verifying that id against `<HA>` is refused with the symmetric message
- [ ] CP6: neither document was disturbed — verify: `verify_recompute` on `<HA>` and `<HB>` both return `OK` after the refusals

**Cleanup**:
```bash
rm -f _automation/tc07_own.step _automation/tc07_own_b.step
```
```
mcp document_close { doc: <HA> }
mcp document_close { doc: <HB> }
```

---

### TC-07-20: planted-fault fixtures are caught, given their reference checks

**Priority**: Critical
**Design Ref**: `verification-design.md` §6.3 (fault detection), §5 (assertion vocabulary)

**Preconditions**:
- [ ] Both fixtures and their `case.yaml` files present (verify: `ls benchmarks/g0/fault-injection/wrong-volume/fixture.FCStd benchmarks/g0/fault-injection/non-watertight-open-shell/case.yaml`)

**Steps**:
1. Read the reference checks out of each fixture's `case.yaml` — they are the CORRECT-shape values
   that the fixture deviates from. Passing bare checks would let a wrong-but-valid shape through,
   so the reference checks are required, never optional:
   ```bash
   python3 -c "import yaml,sys;print(yaml.safe_load(open(sys.argv[1]))['assertions']['checks'])" \
     benchmarks/g0/fault-injection/wrong-volume/case.yaml
   ```
   For `wrong-volume` this is `[{fn: expect_volume, expect: 6000, tol: {rel: 0.001}}]`; for
   `non-watertight-open-shell` it is
   `[{fn: expect_watertight, expect: true}, {fn: expect_solid_count, expect: 1}]`.
2. Open each fixture, resolve its sole object, and grade it with those exact checks:
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/fault-injection/wrong-volume/fixture.FCStd" }
   mcp verify_shape { doc: <H>, object: <OBJ>, checks: [{ fn: "expect_volume", expect: 6000, tol: { rel: 0.001 } }] }
   ```
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/fault-injection/non-watertight-open-shell/fixture.FCStd" }
   mcp verify_shape { doc: <H2>, object: <OBJ2>, checks: [
     { fn: "expect_watertight", expect: true },
     { fn: "expect_solid_count", expect: 1 }
   ] }
   ```

**Checkpoints**:
- [ ] CP1: `wrong-volume` is caught — verify: its `verify_shape` returns `status` equal to `SPEC_FAILED`, never `OK`
- [ ] CP2: the failing check names the planted defect — verify: the `shape.volume` check has `passed: false` with `measured` near `7200.0` against `expected` `6000.0` (a 12x20x30 box where the reference is 10x20x30)
- [ ] CP3: `non-watertight-open-shell` is caught — verify: its `verify_shape` returns `status` equal to `SPEC_FAILED`
- [ ] CP4: the watertight check is the primary signal — verify: the `shape.watertight` check has `passed: false` with `measured: false` against `expected: true`
- [ ] CP5: the solid-count diagnostic confirms it — verify: the `shape.solid_count` check has `measured` equal to `0`, an open shell carrying no solid
- [ ] CP6: bare checks would NOT catch the volume fault — verify: `verify_shape` on the same fixture with `checks` omitted returns `OK`, which is exactly why the reference checks must be passed in
- [ ] CP7: the failure detail names each failed check id — verify: `detail.message` lists the failed ids, and `detail.code` equals `SPEC_FAILED`
- [ ] CP8: the clean control is not flagged — verify: `benchmarks/g0/fault-injection/clean-control/fixture.FCStd` graded with its own `case.yaml` checks returns `OK`

**Cleanup**:
```
mcp document_close { doc: <H> }
mcp document_close { doc: <H2> }
```

---

### TC-07-21: an export never self-reports verified; only the paired verify completes it

**Priority**: Critical
**Design Ref**: `verification-design.md` §6 (AD-9 pairing rule), `mcp-tools-design.md` §3.5

**Preconditions**:
- [ ] No stale targets (verify: `rm -f _automation/tc07_pair.step _automation/tc07_pair.stl _automation/tc07_pair.3mf`)

**Steps**:
1. Open `box-10-20-30.FCStd` as `<H>`, resolve `<OBJ>`.
2. Write all three formats and read each write result:
   ```
   mcp export_step { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_pair.step", objects: [<OBJ>] }
   mcp export_stl  { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_pair.stl",  objects: [<OBJ>] }
   mcp export_3mf  { doc: <H>, path: "D:/Work/Personal/Sources/freecad-buddy/_automation/tc07_pair.3mf",  objects: [<OBJ>] }
   ```
3. Run each paired verifier against its own `export_id`.

**Checkpoints**:
- [ ] CP1: every write reports `verified: false` — verify: all three `structured_content.verified` values are `false`; no write result anywhere carries `verified: true`
- [ ] CP2: the write verdict is `written`, not `verified` — verify: each envelope `text` ends `export written -> <path>.`
- [ ] CP3: the write result carries no checks — verify: none of the three write envelopes has a `structured_content.checks` array; grading only exists in the verify result
- [ ] CP4: the verify result is a validation report, not an export result — verify: each verify envelope's `structured_content.schema` equals `fcb.validation-report/1`, while the write envelope's `schema` is `fcb.result-envelope/1` with a plain payload
- [ ] CP5: the verify verdict is derived from its checks — verify: each verify `structured_content.verdict` equals `OK` and every entry of `structured_content.checks` has `passed: true`
- [ ] CP6: a write to an unverifiable file is still `OK` at write time — verify: after truncating `_automation/tc07_pair.stl` to 0 bytes, the ALREADY-RETURNED write result is unchanged while `verify_export_stl` now returns a non-`OK` status, which is the whole point of the pairing
- [ ] CP7: the status set stays closed across all six calls — verify: every observed `status` is one of `OK`, `SPEC_FAILED`, `RECOMPUTE_ERROR`, `TIMEOUT`, `OOM_KILLED`, `WORKER_CRASHED`, `INVALID_INPUT`

**Cleanup**:
```bash
rm -f _automation/tc07_pair.step _automation/tc07_pair.stl _automation/tc07_pair.3mf
```
```
mcp document_close { doc: <H> }
```
