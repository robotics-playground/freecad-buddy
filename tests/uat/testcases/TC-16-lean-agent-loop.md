# TC-16: Lean Agent Loop (Epic 11)

Proves the Epic 11 claims in the live GUI: mass properties see a rotation about the centre of mass
(Story 11.1), a mutation result is compact and carries digests instead of records (Story 11.2), a
mutation applies in one call by default and a display-only edit needs no token (Story 11.3), a
failed mutation on a large document proves its rollback without a document reopen and the bridge
adds at most 10 s per change (Story 11.4), and the document tree fits one result (`ba1ead6`).

Every envelope field asserted here is a claim of the code under test. The closing `cua-driver`
capture of the real FreeCAD window is the result of each scenario (test plan §3). Sizes are counted
on the raw MCP content blocks, not on a re-serialized envelope, because the raw text is what the
agent's context pays for.

**Host**: GUI through the H2 proxy for every scenario. TC-16-01 .. TC-16-04 and TC-16-06 run under
the default posture (auto-approve on). TC-16-07 needs a FreeCAD started with
`FREECAD_BUDDY_AUTO_APPROVE=0`, or with the **Auto-approve mutations** preference off. TC-16-05 runs `scripts/automation/time_mutation_overhead.py` as a
GUI macro in its own FreeCAD launch.

## Preconditions

- [ ] No FreeCAD process before the first launch (verify: `powershell -NoProfile -c "Get-Process freecad* -EA SilentlyContinue | Measure-Object | % Count"` prints `0`)
- [ ] The installed addon is the junction to `src/freecad_buddy` (verify: `Get-Item "$env:APPDATA\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy" | Select-Object LinkType, Target` shows `Junction` to `<repo>\src\freecad_buddy`)
- [ ] A copy of the 178-object rebuilt drawer exists outside the user project, and the original is never opened (verify: `ls "$RUN_DIR/evidence/drawer-copy.FCStd"`, copied from `D:/Work/3D Printers/Ender 3V2 - Klipper/cad/kiwibox-drawer-rebuild.FCStd`)
- [ ] The audit log path is set for the launch (verify: FreeCAD was started through `_automation/uat/launch_env.sh` with `set FREECAD_BUDDY_AUDIT_LOG=<RUN_DIR>\evidence\audit.jsonl`)
- [ ] Raw MCP results are recorded per call with the character count of each content block (verify: `$RUN_DIR/evidence/tc16_calls.py` writes `{"blocks": [...], "chars": [...]}` per call)
- [ ] `cua-driver` daemon is running in an interactive session (verify: `cua-driver status`)

---

### TC-16-01: A rotation about the centre of mass is listed in `changed`

**Priority**: Critical
**Design Ref**: spine AD-6; `verification-design.md` §8 (mass-property step rule); `contracts/fingerprint.py` `massprops_changed`

**Given** a new document `tc16_rot` with body `Body` and sketch `Sketch` on XY in `Body`  
**And** a 30 x 10 mm rectangle centred on the origin, tilted 30 deg, fully constrained in one call — verify: `sketch_add_geometry` returns `OK` and `sketch_state.dof` is `0`  
```
mcp sketch_add_geometry { doc: <handle>, sketch: "Sketch",
  geometry: [
    { kind: "line_segment", start: [-10.490, -11.830], end: [15.490, 3.170] },
    { kind: "line_segment", start: [15.490, 3.170], end: [10.490, 11.830] },
    { kind: "line_segment", start: [10.490, 11.830], end: [-15.490, -3.170] },
    { kind: "line_segment", start: [-15.490, -3.170], end: [-10.490, -11.830] } ],
  constraints: [
    { type: "Coincident", first: 0, first_pos: 2, second: 1, second_pos: 1 },
    { type: "Coincident", first: 1, first_pos: 2, second: 2, second_pos: 1 },
    { type: "Coincident", first: 2, first_pos: 2, second: 3, second_pos: 1 },
    { type: "Coincident", first: 3, first_pos: 2, second: 0, second_pos: 1 },
    { type: "Perpendicular", first: 0, second: 1 },
    { type: "Perpendicular", first: 1, second: 2 },
    { type: "Perpendicular", first: 2, second: 3 },
    { type: "Symmetric", first: 0, first_pos: 1, second: 2, second_pos: 1, third: -1, third_pos: 1 },
    { type: "Distance", first: 0, value: { value: 30, unit: "mm" } },
    { type: "Distance", first: 1, value: { value: 10, unit: "mm" } },
    { type: "Angle", first: -1, second: 0, value: { value: 30, unit: "deg" }, name: "tilt" } ] }
```
**And** a 10 mm pad `Pad` of `Sketch` — verify: `feature_pad` returns `OK`; `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` `3000.0` and `com` `(0, 0, 5)`  
**And** the view is set to Top and fitted, and the before image is captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK` (it always leaves an isometric camera), then Top view through the GUI by a click on the TOP face of the navigation cube (FreeCAD 1.1.4 has no Top toolbar button), then the **Fit All** toolbar button, then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-16-01-before.png"}' | & cua-driver call get_window_state`  

**When** the tilt changes from 30 to 120 deg, a 90 deg turn about the centre of mass  
```
mcp sketch_set_datum { doc: <handle>, sketch: "Sketch", constraint: "tilt", value: { value: 120, unit: "deg" } }
```

**Then** the mutation commits — verify: `status` is `OK` and `mutation.post_verify.passed` is `true`  
**And** volume, area and centre of mass did not change — verify: `query_mass_properties` on `Pad` returns `volume` `3000.0` and `com` `(0, 0, 5)` again, and `area` equal to the value before  
**And** the rotated solid is listed as changed although those values are equal — verify: `mutation.changed` holds an entry with `name: "Pad"`, `volume` `3000.0` and `com` `[0, 0, 5]` (within `1e-6`). Before Story 11.1 the principal moments, which are eigenvalues, could not see this turn.  
**And** the digests differ — verify: `mutation.fingerprint_before.digest` != `mutation.fingerprint_after.digest`  
**And** *(visual)* the model is framed in Top view — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, then the TOP face of the navigation cube and the **Fit All** toolbar button, as for the before image  
**And** *(visual)* the bar turned by a quarter turn — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-16-01-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs. Before: one long flat bar whose long side rises about 30 deg from horizontal. After: the same bar, same size, with its long side about 30 deg past vertical (120 deg from horizontal). Both bars centred at the same place, no dialog. Judge the pixels only.  

**Cleanup**:
```
mcp document_close { doc: <handle> }
```

---

### TC-16-02: A mutation result is compact and carries digests, not records

**Priority**: Critical
**Design Ref**: spine AD-7, AD-17; `data-contracts-design.md` (ResultEnvelope, `fcb.mutation/2`); `usecases/result_projection.py` `project_mutation`; `adapters/mcp_server.py` `_to_call_result`

**Given** a new document `tc16_quiet` with body `Body` and a fully constrained 20 x 20 mm square sketch `Sketch` on XY, centred on the origin  
**And** the before image is captured after a fit — verify: `view_fit_viewport` returns `OK`, then `cua-driver` capture to `$RUN_DIR/evidence/tc-16-02-before.png`  

**When** the pad is previewed, recording the raw result  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
```
**And** the pad is applied without `confirm`, recording the raw result  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } }
```

**Then** the preview names only the tool — verify: `structured_content.diff.op` equals `{"tool": "feature_pad"}` and the preview `text` does not contain `preview_id`  
**And** the apply result is one compact JSON block — verify: the result has 1 content block, it holds no newline, and `json.dumps(json.loads(t), separators=(",", ":"), ensure_ascii=False) == t`  
**And** the block is small — verify: its character count is at most `10000`; record the count  
**And** the mutation block is `fcb.mutation/2` — verify: `mutation.schema` is `"fcb.mutation/2"`; `fingerprint_before` and `fingerprint_after` each have exactly the keys `digest` and `serializer`  
**And** dropped fields are absent — verify: the mutation block has no key `transaction_id`, `verify_verdict`, `params_digest` or `snapshot_path`  
**And** the TNP audit holds counts and non-PASS findings only — verify: `mutation.post_verify.tnp_audit` has the keys `status`, `element_map_version`, `counts`, `findings`, and no member of `findings` has `verdict: "PASS"`  
**And** `changed` names the new solid with its after values — verify: an entry `name: "Pad"` with `volume` `12000.0`; no entry carries `before` or `after` (those appear only on a failed mutation)  
**And** the audit log still keeps the dropped fields — verify: the `mutation` line for this call in `$RUN_DIR/evidence/audit.jsonl` holds `transaction_id` or `params_digest`  
**And** *(visual)* the model is framed — verify: `view_fit_viewport` returns `OK`, else the **Fit All** toolbar button  
**And** *(visual)* a square prism stands where the flat square was — verify: capture to `$RUN_DIR/evidence/tc-16-02-after.png`, `Read` both. Before: flat square outline. After: shaded solid, about 1.5 times as tall as wide, whole, no dialog.  

**Cleanup**:
```
mcp document_close { doc: <handle> }
```

---

### TC-16-03: A mutation without `confirm` applies in one call and is audited as auto-approved

**Priority**: Critical
**Design Ref**: spine AD-10; `mcp-tools-design.md` §4; `usecases/confirm.py` (auto-approve); `freecad-gui-e2e-harness.md` §2

**Given** FreeCAD was started with `FREECAD_BUDDY_AUTO_APPROVE` unset and the **Auto-approve mutations** preference on — verify: the new `addon.log` lines contain `SECURITY: mutation auto-approve ENABLED (to require preview_id, clear Auto-approve mutations in the FreeCAD GUI: Edit > Preferences > FreeCAD Buddy, or set FREECAD_BUDDY_AUTO_APPROVE=0)`  
**And** the `feature_pad` of TC-16-02 is the call under test, made with no `preview_dry_run` before it on a fresh document `tc16_once` (same body and sketch as TC-16-02)  

**When** the count of tool calls from the sketch to the solid is recorded  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } }
```

**Then** the pad applies in one call — verify: `status` is `OK`, and it is the only tool call between `sketch_add_geometry` and the solid  
**And** the approval is audited — verify: `grep '"event": *"approval"' "$RUN_DIR/evidence/audit.jsonl"` has a line for `feature_pad` on this document with `"mode": "auto_approve"` and `"source": "FREECAD_BUDDY_AUTO_APPROVE"`  
**And** the approval and the mutation agree on the start state — verify: that line's `fingerprint_before` equals the `fingerprint_before` on the `mutation` line of the same call (Story 11.4: the gate fingerprint is reused)  
**And** *(visual)* the model is framed — verify: `view_fit_viewport` returns `OK`, else the **Fit All** toolbar button  
**And** *(visual)* a solid prism is on screen — verify: capture to `$RUN_DIR/evidence/tc-16-03-after.png`, `Read` it: one shaded square prism, whole, no dialog.  

**Cleanup**:
```
mcp document_close { doc: <handle> }
```

---

### TC-16-04: A failed mutation on the drawer rolls back by proof, without a reopen

**Priority**: Critical
**Design Ref**: spine AD-5; `verification-design.md` §1 (rollback proof); `usecases/transaction.py` `_prove_rollback`, `_restore_from_snapshot`

**Given** `$RUN_DIR/evidence/drawer-copy.FCStd` is open — verify: `mcp document_open` returns `OK`; record the handle and `document_list` `name`  
**And** `duct_pilot` is a Pocket with `Length` 6 mm — verify: `mcp query_object { doc: <handle>, object: "duct_pilot" }`  
**And** the before image is captured after a fit — verify: `view_fit_viewport` returns `OK`, then capture to `$RUN_DIR/evidence/tc-16-04-before.png`  

**When** the pocket depth is set to a value FreeCAD cannot build, and the wall-clock time of the call is recorded  
```
mcp feature_set_parameters { doc: <handle>, feature: "duct_pilot", parameters: { Length: { value: 0, unit: "mm" } } }
```
If this returns `INVALID_INPUT` with no `mutation` block (refused before the bracket), repeat with `Length` `1000` mm and record which value ran.

**Then** the mutation failed and rolled back — verify: `status` is not `OK`, `mutation.rolled_back` is `true`  
**And** the abort was proven, not restored from the snapshot — verify: `mutation.rollback_proven` is `"rolled_back_verified"` and the block has no `snapshot_path`  
**And** nothing differs after the rollback — verify: `mutation.changed` is `[]`  
**And** the document was not closed and reopened — verify: the audit `rollback` line of this call names `rolled_back_verified` and no `snapshot_path`. A `document_list` name check cannot see a reopen, because the snapshot file carries the document's own name  
**And** the call took less than a snapshot restore — verify: recorded wall-clock time; under 32 s (the measured restore time in run `2026-10-07-03`)  
**And** `duct_pilot` is unchanged — verify: `query_object` shows `Length` 6 mm  
**And** *(visual)* the model is framed — verify: `view_fit_viewport` returns `OK`, else the **Fit All** toolbar button  
**And** *(visual)* the drawer looks as before — verify: capture to `$RUN_DIR/evidence/tc-16-04-after.png`, `Read` both. Same pieces, same shapes, same camera after the fit, the Model panel still shows the same document and expanded state, no error marker on a tree item, no dialog.  

**Cleanup**:
```
mcp document_close { doc: <handle> }
```

---

### TC-16-05: The bridge adds at most 10 s per change on the drawer in the GUI

**Priority**: High
**Design Ref**: Story 11.4 AC5, Story 11.6 AC3 (human decision 2026-10-07: ≤ 10 s GUI); `scripts/automation/time_mutation_overhead.py`

**Given** no FreeCAD process is running — verify: process count `0`  
**And** a fresh copy `$RUN_DIR/evidence/drawer-timing.FCStd` of the rebuilt drawer  

**When** FreeCAD is started with the timing macro as its argument, through `cmd.exe`  
```
set FCB_DRAWER_COPY=<RUN_DIR>\evidence\drawer-timing.FCStd&& set FCB_TIMING_OUT=<RUN_DIR>\evidence\gui-timing.json&& set FCB_TIMING_FEATURE=duct_pilot&& start "" "C:\Program Files\FreeCAD 1.1\bin\freecad.exe" "<PROJECT_ROOT>\scripts\automation\time_mutation_overhead.py"
```
**And** the run is repeated once into `gui-timing-repeat.json`  

**Then** each run's median overhead is at most 10 s — verify: the median `T - R` in `gui-timing.json` and in `gui-timing-repeat.json`; record both  
**And** the abort proof in the macro holds on the same document — verify: the report's abort check is `rolled_back_verified` and records no `closeDocument` call. Known open item: run `2026-10-07-03` saw `rolled_back_via_snapshot` here (deferred-work, Story 11.6); a repeat of that is a FAIL of this line, not of the timing line  
**And** *(visual)* the drawer is on screen after the macro — verify: Fit All toolbar button, capture to `$RUN_DIR/evidence/tc-16-05-after.png`, `Read` it: the drawer pieces, whole, no dialog  

**Cleanup**:
```bash
uv run python _automation/uat/close_all.py
```
Quit FreeCAD with `invoke_menu ["File","Exit"]`; discard the copy.

---

### TC-16-06: The document tree of the drawer fits one small result

**Priority**: High
**Design Ref**: `mcp-tools-design.md` (`query_tree_summary`); `adapters/mcp_server.py` `_to_call_result` (`text_blocks`); UAT run `2026-10-07-03` AC2 FAIL row

**Given** `$RUN_DIR/evidence/drawer-copy.FCStd` is open — verify: `document_open` returns `OK`  

**When** the call that returned 11,612 chars in run `2026-10-07-03` is repeated in its current form  
```
mcp query_tree_summary { doc: <handle>, focus: "front_plate_piece", depth: 3 }
```

**Then** the result is one text block — verify: line 1 starts `OK:` and ends `shown.`, a `framing:` line follows, then the tree lines; the block holds no `{` and there is no `structuredContent`  
**And** the total is at most 10,000 chars — verify: the block character count; record it (run `2026-10-08-01` measured 985)  
**And** no line comes from another body — verify: the tree lines name no feature of `tray_piece`, `rear_module_piece`, `duct_cover` or `drawer`  
**And** *(visual)* the Model panel has the same children — verify: expand `front_plate_piece` in the Model panel with `cua-driver`, capture to `$RUN_DIR/evidence/tc-16-06-panel.png`, `Read` it: the children and their order equal the tree lines at depth 1 under `front_plate_piece`  

**Cleanup**:
```
mcp document_close { doc: <handle> }
```

---

### TC-16-07: With the gate on, a visibility-only edit needs no token, and any other edit does

**Priority**: High
**Design Ref**: Story 11.3 AC3, AC4; spine AD-10; `usecases/confirm.py` (display state)

**Given** FreeCAD was started with `FREECAD_BUDDY_AUTO_APPROVE=0`, or with the **Auto-approve mutations** preference off and the variable unset — verify: the new `addon.log` lines do not contain `SECURITY: mutation auto-approve ENABLED`  
**And** a document `tc16_vis` with body `Body`, a 20 x 20 mm sketch and a 30 mm `Pad` built with preview tokens  
**And** the before image is captured after a fit — verify: capture to `$RUN_DIR/evidence/tc-16-07-before.png`  

**When** `Pad` is hidden without `confirm`  
```
mcp feature_set_parameters { doc: <handle>, feature: "Pad", parameters: { Visibility: false } }
```
**And** a call that writes `Visibility` and `Length` without `confirm` is made  
```
mcp feature_set_parameters { doc: <handle>, feature: "Pad", parameters: { Visibility: true, Length: { value: 40, unit: "mm" } } }
```

**Then** the visibility-only call applies — verify: `status` is `OK`  
**And** it is audited as display state — verify: the audit log has an `approval` line for it with `"mode": "display_state"`  
**And** the mixed call is refused — verify: `status` is `INVALID_INPUT` and the message contains `requires a confirm`  
**And** the mixed call changed nothing — verify: `query_mass_properties` on `Pad` returns `volume` `12000.0`  
**And** *(visual)* the solid is hidden — verify: capture to `$RUN_DIR/evidence/tc-16-07-after.png`, `Read` both. Before: shaded prism. After: no shaded prism in the viewport (only the sketch outline or empty origin), and the `Pad` row in the Model panel is greyed. A visible prism, or a taller one, is the finding.  

**Cleanup**:
```
mcp document_close { doc: <handle> }
```
