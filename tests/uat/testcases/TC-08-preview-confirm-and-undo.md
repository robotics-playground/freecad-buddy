# TC-08: Preview, the Confirm-Token Gate & Verified Undo

Validates AD-10: no geometry mutation runs without a `preview_id` this process minted for exactly
this tool, these arguments, this document and this document state. The gate in
`usecases/confirm.py` is the only thing standing between a model and an unreviewed change, so each
refusal path is tested for its own distinct message — a gate that refuses everything with one
generic error cannot tell a caller what to fix. Also covers `preview_dry_run` leaving the live
document untouched, and `document_undo` reporting restoration as a measurement rather than an
assumption. Driven over MCP against the live bridge; no automation script covers this surface.

We are building the MCP bridge, so the bridge's own output can never be the test result. Every
status, envelope field, fingerprint and `query_screenshot` render in this file is a **claim under
test**. The test result is the `cua-driver` pixel capture of the real FreeCAD window, `Read` and
judged by the agent. A bridge that reports a clean undo while the window still shows the mutation
passes every numeric assertion here and fails the user completely; commit `636fb8a` fixed exactly
that class of defect. Where a numeric assertion and the pixels disagree, the pixels win and the
disagreement is recorded in `$RUN_DIR/bugs.md`.

**Host**: GUI through the H2 proxy for every scenario except TC-08-18, which runs on the H1
headless host to prove the auto-approve operator posture, and TC-08-05, which uses the GUI host for
the available-render contrast and an H1 headless host for the no-render-port contrast.

## Preconditions
- [ ] FreeCAD GUI open and the addon bridge serving `:8765` (verify: `netstat -ano | grep :8765` shows LISTENING)
- [ ] Host is NOT in auto-approve posture: FreeCAD was started with `FREECAD_BUDDY_AUTO_APPROVE=0`, or with the **Auto-approve mutations** preference off and the variable unset, because auto-approve is on by default (verify: the new `addon.log` lines from that launch do not contain `SECURITY: mutation auto-approve ENABLED`)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)
- [ ] No stale preview TempDocs (verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` returns a `QOpenGLWidget`)
- [ ] The GUI's own **Fit All** toolbar button is reachable, as the non-MCP framing path (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` lists a `Fit All` toolbar element with an `element_token`; clicking it returns `route: "accessibility"` and reframes the view. Note `invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable` at segment 1 — only `["View","Zoom"]` resolves.)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)

---

### TC-08-01: preview_dry_run returns the structured diff

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.8 (preview_dry_run), `data-contracts-design.md` §8

**Given** a body with a fully-constrained 20x20 mm rectangular sketch on XY — verify: `mcp query_sketch_info { doc: <handle>, sketch: "Sketch" }` returns `fully_constrained: true`  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-preview window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-01-before.png"}' | & cua-driver call get_window_state`  

**When** a 30 mm pad is previewed  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
```

**Then** the envelope succeeded — verify: `status` is `OK`, `detail` is `null`, and `structured_content.diff.schema` equals `"fcb.geometry-diff/1"`  
**And** the volume delta is measured with units — verify: `diff.deltas.volume` reports `before: 0.0`, `after: 12000.0`, `delta: 12000.0`, `units: "mm^3"`  
**And** area and bbox carry their own units — verify: `diff.deltas.area.units` equals `"mm^2"` and `diff.deltas.bbox.units` equals `"mm"`, and `diff.deltas.com.units` equals `"mm"`  
**And** topology counts are deltas, not totals — verify: `diff.counts.solids` reports `before: 0`, `after: 1`, `delta: 1`, and `diff.counts.faces.delta` equals `6`  
**And** the three name sets are reported — verify: `diff.touched` contains `"Pad"`, `diff.new` contains `"Pad"`, and `diff.deleted` is `[]`  
**And** validity carries the op's own verdict — verify: `diff.validity.is_valid` is `true`, `diff.validity.recompute_clean` is `true`, `diff.validity.status` is `"OK"`, `diff.validity.explanation` is `null`  
**And** the TNP pre-check is present — verify: `diff.tnp_precheck.status` is one of `CLEAN`, `FLAGGED`, `UNSUPPORTED` and `diff.tnp_precheck.element_map_version` is present  
**And** a token and its deadline were issued — verify: `structured_content.preview_id` starts with `fcb-preview:` and `structured_content.expires_at` is an ISO-8601 UTC timestamp  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window shows the sketch only, with no pad — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-01-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen in each. **This is a PREVIEW: the two images must be visually IDENTICAL by eye** — a flat 20x20 mm rectangle and no extruded solid in either. A preview that reports "no changes applied" while the viewport shows the new 30 mm pad is the exact defect this catches. The identity is judged by looking at both images, not by comparing fingerprints. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-02: A preview leaves the live document unchanged

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.8 (throwaway copy), `verification-design.md` §1

**Given** a body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad` — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`  
**And** no stale preview TempDocs — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-preview window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-02-before.png"}' | & cua-driver call get_window_state`  

**When** the live mass properties and the open document list are recorded  
```
mcp query_mass_properties { doc: <handle>, object: "Pad" }
mcp document_list {}
```
**And** a change that WOULD alter the geometry is previewed  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_set_parameters", args: { feature: "Pad", parameters: { Length: { value: 80, unit: "mm" } } } } }
```
**And** the live mass properties and document list are re-read  

**Then** the preview reported the change — verify: `diff.deltas.volume.after` equals `32000.0` (20 x 20 x 80 mm)  
**And** the live volume is unchanged — verify: the re-read `query_mass_properties` returns `volume` = `12000.0`, byte-identical to the first read  
**And** the live bbox and centre of mass are unchanged — verify: the re-read `bbox` and `com` equal the first read  
**And** no TempDoc was adopted into the document list — verify: the re-read `document_list` holds the same handles as the first read, with no name starting `FCB_TMP_prev_`  
**And** the TempDoc directory is gone — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing  
**And** the preview did not report a live-document change — verify: the envelope is `OK`, not a `SPEC_FAILED` carrying `preview changed the live document`  
**And** cleanup happens on the failing path too — verify: after previewing an operation that FAILS on the copy, `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` still returns nothing  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window still shows the 30 mm pad, not an 80 mm one — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-02-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state the pad's proportions in each. **This is a PREVIEW: the two images must be visually IDENTICAL by eye** — the pad's height is unchanged and no taller solid appeared. A preview that reports the live document untouched while the viewport shows a visibly lengthened pad is the exact defect this catches. The identity is judged by looking at both images, not by comparing volumes or fingerprints. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
rm -rf "$TEMP"/FCB_TMP_prev_*
```

---

### TC-08-03: A preview_id authorizes exactly that apply

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (confirm gate), `data-contracts-design.md` §8

**Given** a body with a fully-constrained 20x20 mm sketch — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists `Body` and `Sketch`, not `Pad`  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-mutation window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-03-before.png"}' | & cua-driver call get_window_state`  

**When** the pad is previewed and the token kept  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
```
**And** the identical operation is applied with that token  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>" } }
```

**Then** the apply was authorized — verify: `status` is `OK` and `detail` is `null`  
**And** the mutation committed — verify: `mutation.rolled_back` is `false` and `mutation.fingerprint_after` is a full record  
**And** the token's signed fingerprint matched the live one — verify: `mutation.fingerprint_before.digest` equals the preview's `diff.fingerprint_before`  
**And** the geometry matches what the preview predicted — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`, equal to `diff.deltas.volume.after`  
**And** the token form is as documented — verify: the `preview_id` matches `^fcb-preview:[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$`  
**And** an explicit accept is also honored — verify: the same flow with `confirm: { preview_id: "<fresh token>", elicitation_action: "accept" }` also returns `status: "OK"`  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window shows the new extruded solid — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-03-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen in each. **This is a CONFIRMED mutation: the new geometry must be visibly present** — the before image shows a flat sketch, the after image shows a 20x20x30 mm solid box. An `OK` envelope over a window that still shows only the sketch is the defect. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-04: A preview of a failing operation is still a successful preview

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.8 (a failing op is a successful preview reporting a failing diff)

**Given** a body with a 30 mm `Pad` — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-preview window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-04-before.png"}' | & cua-driver call get_window_state`  

**When** a fillet whose radius cannot fit the edge is previewed  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 500, unit: "mm" } } } }
```

**Then** the envelope is a success — verify: `status` is `OK` and `detail` is `null`  
**And** the failure travels in `validity`, not in the envelope — verify: `diff.validity.is_valid` is `false` and `diff.validity.status` is `SPEC_FAILED` or `RECOMPUTE_ERROR`  
**And** the failure has a stated reason — verify: `diff.validity.explanation` is a non-null, non-empty string naming the failing check  
**And** the diff still reports measurements — verify: `diff.deltas.volume` is present with `before`, `after`, `delta` and `units`  
**And** nothing is reported as touched or new, because the op rolled back on the copy — verify: `diff.new` is `[]`  
**And** a token was still issued — verify: `structured_content.preview_id` is non-null, because the op reached the gate on the copy  
**And** the live document is unchanged — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window shows the unfilleted pad — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-04-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state the edges you see in each. **This is a PREVIEW: the two images must be visually IDENTICAL by eye** — sharp edges, no rounded edge, and no error-state colouring on the solid. A failing preview that left a broken or rounded feature on the human's screen is the exact defect this catches. The identity is judged by looking at both images, not by comparing `validity` fields. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-05: `render:"off"` and an unavailable render are reported distinctly

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §3.8 (render block; unavailability is not an error)

**Given** a body with a 30 mm `Pad`  
**And** a GUI host with a render port available — verify: `mcp query_screenshot { doc: <handle>, view: { camera: "iso" } }` returns `status: "OK"` with a `resource_link`  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-preview window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-05-before.png"}' | & cua-driver call get_window_state`  

**When** a preview is taken with the render explicitly off  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_set_parameters", args: { feature: "Pad", parameters: { Length: { value: 40, unit: "mm" } } } }, render: "off" }
```
**And** a preview is taken with the render left on the default  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_set_parameters", args: { feature: "Pad", parameters: { Length: { value: 40, unit: "mm" } } } }, render: "auto" }
```
**And** the default-render preview is repeated against a headless host, which has no render port  

**Then** an explicit opt-out is recorded as such — verify: the `render: "off"` call returns `diff.render` equal to `{ "available": false, "reason": "off" }`  
**And** a missing port is a different reason — verify: the headless call returns `diff.render.reason` equal to `"no render port"`, not `"off"`  
**And** the two are never collapsed — verify: `"off"` never appears as the reason on a call that did not pass `render: "off"`  
**And** neither case is an error — verify: both the `render: "off"` call and the headless call return envelope `status: "OK"`  
**And** an available render says so — verify: the `render: "auto"` call on the GUI host returns `diff.render.available` equal to `true`  
**And** the enum is closed — verify: `mcp preview_dry_run { doc: <handle>, operation: {...}, render: "sometimes" }` is rejected by the schema, because `render` enumerates only `["auto", "off"]`  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the GUI window still shows the 30 mm pad — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-05-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state the pad's proportions in each. **These are PREVIEWS: the two images must be visually IDENTICAL by eye** — the pad's height is unchanged by any of the three previews, whichever render setting they carried. The `diff.render` block is a claim under test and cannot stand as evidence for what the human saw; the identity is judged by looking at both images. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-06: document_undo reports a measured match against expect_fingerprint

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (restoration is reported, never assumed), `data-contracts-design.md` §8

**Given** a body with a fully-constrained 20x20 mm sketch, undo available — verify: `mcp document_undo { doc: <handle> }` is not refused with `undo is unavailable`  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-mutation window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-06-before.png"}' | & cua-driver call get_window_state`  

**When** a pad is applied and BOTH forms of its before-fingerprint are kept  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>" } }
```
Keep `mutation.fingerprint_before.digest` (the string form) and the whole
`mutation.fingerprint_before` object (the record form).
**And** the undo is called with the string form  
```
mcp document_undo { doc: <handle>, expect_fingerprint: "<digest string>" }
```
**And** the pad is re-applied, then undone with the record form  
```
mcp document_undo { doc: <handle>, expect_fingerprint: { schema: "...", serializer: "...", objects: [...], digest: "..." } }
```

**Then** the string form reports a match — verify: the string-form undo returns `matches_pre_op: true`  
**And** the record form reports a match — verify: the record-form undo returns `matches_pre_op: true`  
**And** both fingerprints are reported, before and after the undo — verify: `fingerprint_before` and `fingerprint_after` are both 64-hex digests and differ from each other  
**And** the undone transaction is named — verify: `undone` equals `buddy: <the pad's transaction label>`  
**And** the text states the measurement, not an assumption — verify: envelope `text` contains `restored the pre-op state`  
**And** no expectation gives no verdict — verify: `mcp document_undo { doc: <handle> }` with no `expect_fingerprint` returns `matches_pre_op: null` and `text` containing `no pre-op digest supplied to compare against`  
**And** the object set is reported — verify: `restored_objects` lists `Body`, `Sketch` and their Origin members, and does NOT list `Pad`  
**And** a wrong type is refused, not reported as a non-match — verify: `mcp document_undo { doc: <handle>, expect_fingerprint: 42 }` is refused with `expect_fingerprint must be a fingerprint digest string or a FingerprintRecord, got int`  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is restored to its pre-mutation appearance — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-06-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen in each. **This is an UNDO: the post-undo image must match the pre-mutation image by eye** — the flat sketch is shown and the extruded solid is gone. `matches_pre_op: true` over a window that still shows the pad is a finding; so is a fingerprint mismatch over a window that is visually restored. Record which of the two is wrong in `$RUN_DIR/bugs.md`. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-07: A token is single-use

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (a token authorizes one mutation)

**Given** a body with a fully-constrained 20x20 mm sketch  
**And** a previewed, unspent token for `feature_body_create`, which can run twice under different names without changing the fingerprint in a way that blocks the replay  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-replay window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-07-before.png"}' | & cua-driver call get_window_state`  

**When** an operation that commits without moving the document digest is previewed and applied — creating an empty body adds no shape, so the fingerprint is unchanged  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_body_create", args: { name: "Probe" } } }
mcp feature_body_create { doc: <handle>, name: "Probe", confirm: { preview_id: "<token>" } }
```
**And** the SAME token is replayed on the identical call  
```
mcp feature_body_create { doc: <handle>, name: "Probe", confirm: { preview_id: "<same token>" } }
```

**Then** the first apply was authorized — verify: the apply's mutation returns `status: "OK"`  
**And** the fingerprint did not move — verify: the apply's `mutation.fingerprint_before.digest` equals `mutation.fingerprint_after.digest`, which is what makes the spent-check the only thing refusing the replay  
**And** the replay is refused — verify: the replay returns the refusal `confirm.preview_id has already authorized a mutation; re-run preview_dry_run`  
**And** the refusal is not a fingerprint complaint — verify: the message does NOT contain `the document has changed since the preview was taken`  
**And** the replay mutated nothing — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` lists exactly one `Probe` body, not two  
**And** a fresh preview restores the ability to apply — verify: a new `preview_dry_run` for the same operation yields a token whose apply returns `status: "OK"`  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the refused replay added no geometry to the window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-07-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen and in the model tree in each. **The refused replay must leave the window IDENTICAL by eye** — the same geometry, no duplicated body, and no error dialog raised by the replay. A refusal envelope over a window that gained a second body is the defect. The judgement is on the pixels alone — no MCP status, tree summary or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-08: A token is bound to the tool that minted it

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (the gate re-derives the tool from the call)

**Given** a body with a fully-constrained 20x20 mm sketch — verify: `mcp query_sketch_info { doc: <handle>, sketch: "Sketch" }` returns `fully_constrained: true`  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-attempt window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-08-before.png"}' | & cua-driver call get_window_state`  

**When** a PAD is previewed and its token kept  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
```
**And** that token is presented to a POCKET with otherwise identical arguments  
```
mcp feature_pocket { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<pad token>" } }
```

**Then** the call is refused — verify: it returns the refusal `confirm.preview_id was issued for 'feature_pad', not 'feature_pocket'`  
**And** both tool names appear in the message — verify: the message names the minting tool first and the called tool second, in that order  
**And** nothing was mutated — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists neither `Pad` nor a pocket  
**And** the refusal is not an argument complaint — verify: the message does NOT contain `was issued for different arguments`  
**And** the token is still usable on its own tool — verify: presenting the same token to `feature_pad` with the same arguments returns `status: "OK"`  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the refused pocket left the window unchanged, and the later authorized pad reached it — verify: capture immediately after the refused pocket to `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-08-refused.png"}' | & cua-driver call get_window_state`, and again after the authorized `feature_pad` to `"$RUN_DIR/evidence/tc-08-08-after.png"`, then `Read` all three PNGs and state what is on screen in each. The refused image must be IDENTICAL to the before image by eye — no pocket, no hole, no removed material. The after image must show the extruded 30 mm solid, because a CONFIRMED mutation must be visibly present. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the images.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-09: A token is bound to the arguments it was minted for

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (args_digest comparison)

**Given** a body with a fully-constrained 20x20 mm sketch  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-attempt window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-09-before.png"}' | & cua-driver call get_window_state`  

**When** a 30 mm pad is previewed  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
```
**And** the token is presented to the same tool with a DIFFERENT length  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 60, unit: "mm" }, confirm: { preview_id: "<30 mm token>" } }
```

**Then** the call is refused — verify: it returns the refusal `confirm.preview_id was issued for different arguments`  
**And** nothing was mutated — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Pad`  
**And** a one-character difference is enough — verify: presenting the token with `name: "Pad1"` and every other argument identical is refused with the same message  
**And** `doc` is excluded from the digest, so it is not what refused this — verify: the refusal message is NOT `confirm.preview_id was issued for a different document`  
**And** `confirm` itself is excluded from the digest — verify: presenting the same token as `confirm: { preview_id: "<token>", elicitation_action: "accept" }` with the original 30 mm arguments returns `status: "OK"`, proving adding the `elicitation_action` field did not change the digest  
**And** the identical call is still authorized — verify: re-presenting a FRESH 30 mm token with the 30 mm arguments returns `status: "OK"`  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the 60 mm pad never reached the window — verify: capture immediately after the refused 60 mm call to `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-09-refused.png"}' | & cua-driver call get_window_state`, and again after the authorized 30 mm apply to `"$RUN_DIR/evidence/tc-08-09-after.png"`, then `Read` all three PNGs and state the solid's height in each. The refused image must be IDENTICAL to the before image by eye — a flat sketch and no solid at all. The after image must show a solid whose height reads as 30 mm against the 20 mm base, not double it. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the images.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-10: A token is bound to the document it was minted on

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (doc handle comparison)

**Given** TWO documents open, each with a body and an identical fully-constrained 20x20 mm sketch — verify: `mcp document_list {}` returns two handles, `<handle-a>` and `<handle-b>`  
**And** document B is in the live viewport and framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle-b> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-attempt window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-10-before.png"}' | & cua-driver call get_window_state`  

**When** the pad is previewed on document A  
```
mcp preview_dry_run { doc: <handle-a>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
```
**And** A's token is presented to the identical call on document B  
```
mcp feature_pad { doc: <handle-b>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<A's token>" } }
```

**Then** the call is refused — verify: it returns the refusal `confirm.preview_id was issued for a different document`  
**And** document B was not mutated — verify: `mcp query_tree_summary { doc: <handle-b>, depth: 3 }` does not list `Pad`  
**And** document A was not mutated either — verify: `mcp query_tree_summary { doc: <handle-a>, depth: 3 }` does not list `Pad`  
**And** identical geometry does not defeat the binding — verify: the refusal holds even though the two documents are byte-identical copies, because the comparison is on the handle, not the content  
**And** the refusal is not an argument complaint — verify: the message does NOT contain `was issued for different arguments`  
**And** A's token still works on A — verify: presenting the same token to the same call on `<handle-a>` returns `status: "OK"`  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle-b> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* document B's viewport is unchanged by the refused apply — verify: capture immediately after the refused call to `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-10-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen and which document's title the window carries in each. The two images must be visually IDENTICAL by eye — B still shows a flat sketch with no pad, and document A was not silently activated into the viewport. The judgement is on the pixels alone — no MCP status, tree summary or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle-a> }
mcp document_close { doc: <handle-b> }
```

---

### TC-08-11: A token is bound to the document state it measured

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (fingerprint_before comparison)

**Given** a body with a fully-constrained 20x20 mm sketch  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-attempt window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-11-before.png"}' | & cua-driver call get_window_state`  

**When** the pad is previewed and its token kept  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
```
**And** the document is changed between the preview and the apply — the sketch is widened  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "sketch_set_datum", args: { sketch: "Sketch", constraint: "Width", value: { value: 40, unit: "mm" } } } }
mcp sketch_set_datum { doc: <handle>, sketch: "Sketch", constraint: "Width", value: { value: 40, unit: "mm" }, confirm: { preview_id: "<datum token>" } }
```
**And** the STALE first token is presented  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<step-1 token>" } }
```

**Then** the stale token is refused — verify: the stale-token call returns the refusal `the document has changed since the preview was taken; re-run preview_dry_run`  
**And** the intervening mutation did commit — verify: the `sketch_set_datum` apply returns `status: "OK"` and `mcp query_sketch_info { doc: <handle>, sketch: "Sketch" }` reports the 40 mm width  
**And** nothing was padded — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Pad`  
**And** the refusal is not a spent-token complaint — verify: the message does NOT contain `has already authorized a mutation`  
**And** re-previewing recovers — verify: a fresh `preview_dry_run` for the same pad, followed by its apply, returns `status: "OK"`  
**And** an unreadable live state is also a refusal, not a crash — verify: a document whose shape cannot be serialized produces a refusal starting `cannot read the state of ` and naming the handle  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window shows the widened sketch and no stale pad — verify: capture immediately after the refused stale-token call to `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-11-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state the sketch's proportions and whether a solid is present in each. The after image must show the rectangle visibly wider than in the before image, because that CONFIRMED datum change must be visible; and it must show no extruded solid, because the refused stale token must produce nothing. The judgement is on the pixels alone — no MCP status, `query_sketch_info` width or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-12: An expired token is refused as expired, before the spent check

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §4 (TTL 900 s; expiry checked before the spent set)

**Given** a body with a fully-constrained 20x20 mm sketch  
**And** ability to wait past the 900 s TTL, or a host clock the test may advance  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-attempt window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-12-before.png"}' | & cua-driver call get_window_state`  

**When** an operation whose apply will not move the document digest is previewed, so its token stays otherwise valid, and `expires_at` is recorded  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_body_create", args: { name: "Probe" } } }
```
**And** that token is SPENT by applying it once  
```
mcp feature_body_create { doc: <handle>, name: "Probe", confirm: { preview_id: "<token>" } }
```
**And** after waiting past the deadline (901 s from mint), the SAME spent-and-expired token is presented  
```
mcp feature_body_create { doc: <handle>, name: "Probe", confirm: { preview_id: "<token>" } }
```

**Then** the advertised TTL is 900 s — verify: `expires_at` minus the call time is 900 seconds, to within clock skew  
**And** the expired token is refused as expired — verify: the post-deadline call returns `confirm.preview_id has expired; re-run preview_dry_run`  
**And** expiry wins over spent — verify: the post-deadline message is the expiry message, NOT `confirm.preview_id has already authorized a mutation; re-run preview_dry_run`, even though the token was spent by the first apply  
**And** the ordering is only observable on a spent-AND-expired token — verify: the same token presented one second after the apply (spent, not expired) DOES return the already-authorized message, proving both checks are live  
**And** an unexpired unspent token still works — verify: a fresh preview's token applied within the TTL returns `status: "OK"`  
**And** the expired call mutated nothing — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` lists exactly one `Probe` body  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the expired refusal added nothing to the window — verify: capture immediately after the post-deadline call to `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-12-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen and in the model tree in each. Apart from the one `Probe` body the first apply legitimately created, the images must be IDENTICAL by eye — no duplicated body and no error dialog left open by the expired call. The judgement is on the pixels alone — no MCP status, tree summary or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-13: A refused call does not spend its token

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (spend once the mutation is going ahead, after any precheck)

**Given** a body with a fully-constrained 20x20 mm sketch  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-attempt window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-13-before.png"}' | & cua-driver call get_window_state`  

**When** a 30 mm pad is previewed  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
```
**And** a call the gate REFUSES is made — wrong arguments for this token  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 60, unit: "mm" }, confirm: { preview_id: "<token>" } }
```
**And** the call is corrected and the SAME token re-sent  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<same token>" } }
```

**Then** the wrong-argument call was refused — verify: it returns `confirm.preview_id was issued for different arguments`  
**And** the corrected call is authorized — verify: the corrected call returns `status: "OK"`  
**And** the corrected call was NOT refused as spent — verify: the corrected call's response contains no `has already authorized a mutation` message  
**And** the geometry landed — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`  
**And** the token is spent only after the successful apply — verify: re-sending the same token a fourth time now returns `confirm.preview_id has already authorized a mutation; re-run preview_dry_run`  
**And** other refusal paths also leave the token usable — verify: repeating the flow where the middle call is refused with `confirm.elicitation_action must be 'accept', got 'decline'` still lets the corrected call succeed  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window shows exactly one 30 mm pad — verify: capture immediately after the refused 60 mm call to `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-13-refused.png"}' | & cua-driver call get_window_state`, and again after the corrected apply to `"$RUN_DIR/evidence/tc-08-13-after.png"`, then `Read` all three PNGs and state what is on screen in each. The refused image must be IDENTICAL to the before image by eye — a flat sketch and no solid. The after image must show a single extruded solid whose height reads as 30 mm, not the 60 mm of the refused call. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the images.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-14: Tampered, malformed and foreign tokens produce distinct messages

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (token codec), `data-contracts-design.md` §8

**Given** a body with a fully-constrained 20x20 mm sketch  
**And** one valid `feature_pad` token in hand, from `preview_dry_run`  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-attempt window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-14-before.png"}' | & cua-driver call get_window_state`  

**When** each malformed token is presented in turn to the same `feature_pad` call, changing only `confirm.preview_id`  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<variant>" } }
```
Variants, in order:
- `"not-a-token"` (no prefix)
- `"fcb-preview:onlybody"` (prefix, no `.` separator)
- `"fcb-preview:.sig"` (empty body) and `"fcb-preview:body."` (empty signature)
- `"fcb-preview:!!!!.!!!!"` (prefix and separator, undecodable base64)
- the valid token with one character of its signature segment changed
- a token whose body is a valid base64 JSON object missing `jti`, re-signed is impossible, so
  instead: the valid token truncated mid-body

**Then** no prefix is named as such — verify: `"not-a-token"` returns `confirm.preview_id is not a preview token`  
**And** no separator, or an empty half, is malformed — verify: `"fcb-preview:onlybody"`, `"fcb-preview:.sig"` and `"fcb-preview:body."` each return `confirm.preview_id is malformed`  
**And** undecodable base64 is its own message — verify: `"fcb-preview:!!!!.!!!!"` returns `confirm.preview_id is not decodable`  
**And** a tampered signature is named — verify: the signature-altered token returns `confirm.preview_id carries an invalid signature`  
**And** each message is distinct — verify: the four messages above are four different strings; a single generic refusal for all of them is a defect  
**And** a payload missing a required field is named — verify: a token whose body decodes to an object lacking a payload field returns `confirm.preview_id payload is missing ` followed by the list of missing keys  
**And** a non-string `preview_id` is refused — verify: `confirm: { preview_id: 12345 }` returns `confirm.preview_id is not a preview token`  
**And** none of the variants mutated anything — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Pad` after all variants have been tried  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* no variant reached the window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-14-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen in each. After every variant has been tried the two images must be visually IDENTICAL by eye — a flat sketch, no extruded solid, and no error dialog left open by any variant. The judgement is on the pixels alone — no MCP status, refusal message or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-15: An undeclared confirm field is refused, never silently dropped

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (`_CONFIRM_SCHEMA`; `autoApprove` is absent from the wire by design)

**Given** a body with a fully-constrained 20x20 mm sketch  
**And** one valid `feature_pad` token in hand  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-attempt window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-15-before.png"}' | & cua-driver call get_window_state`  

**When** the valid token is presented alongside an undeclared field  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>", autoApprove: true } }
```
**And** it is repeated with two undeclared fields  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>", autoApprove: true, force: 1 } }
```
**And** a `confirm` that is not an object is presented  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: "yes" }
```

**Then** the undeclared field is refused — verify: the single-field call returns `confirm carries field(s) the schema does not declare: ['autoApprove']`  
**And** the unknown keys are listed, sorted — verify: the two-field call returns `confirm carries field(s) the schema does not declare: ['autoApprove', 'force']`  
**And** it was not silently dropped — verify: the single-field call did NOT return `status: "OK"`, and `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Pad`  
**And** a non-object confirm is refused with its own message — verify: the `confirm: "yes"` call returns either the schema rejection for a non-object `confirm`, or `confirm must be an object`  
**And** the token survives the refusal — verify: re-presenting the same token with `confirm: { preview_id: "<token>" }` alone returns `status: "OK"`  
**And** only the two declared fields are accepted — verify: `confirm: { preview_id: "<fresh token>", elicitation_action: "accept" }` is authorized, and no third key is  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the three refusals produced no geometry — verify: capture immediately after the three refused calls to `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-15-refused.png"}' | & cua-driver call get_window_state`, and again after the authorized apply to `"$RUN_DIR/evidence/tc-08-15-after.png"`, then `Read` all three PNGs and state what is on screen in each. The refused image must be IDENTICAL to the before image by eye — a flat sketch and no solid, proving `autoApprove` was not silently honoured. The after image must show the extruded solid from the legitimate apply. The judgement is on the pixels alone — no MCP status, refusal message or render may stand in for looking at the images.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-16: An elicitation_action other than accept is refused

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (`elicitation_action` enum is `["accept"]`)

**Given** a body with a fully-constrained 20x20 mm sketch  
**And** one valid `feature_pad` token in hand  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-attempt window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-16-before.png"}' | & cua-driver call get_window_state`  

**When** the valid token is presented with a declining action  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>", elicitation_action: "decline" } }
```
**And** it is repeated with `"cancel"` and with `null`  

**Then** a declining action is refused — verify: the call returns `confirm.elicitation_action must be 'accept', got 'decline'`  
**And** the rejected value is quoted back — verify: the message ends with the Python repr of the supplied value, so `"cancel"` yields `got 'cancel'` and `null` yields `got None`  
**And** the schema also closes the enum — verify: the same call may instead be rejected at the JSON Schema layer, because `elicitation_action` enumerates only `["accept"]`; either refusal is a pass, a silent acceptance is not  
**And** nothing was mutated — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Pad`  
**And** the token survives — verify: re-presenting the same token with `elicitation_action: "accept"` returns `status: "OK"`  
**And** omitting the field defaults to accept — verify: `confirm: { preview_id: "<fresh token>" }` alone returns `status: "OK"`  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the declined calls produced no geometry — verify: capture immediately after the three declining calls to `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-16-refused.png"}' | & cua-driver call get_window_state`, and again after the accepted apply to `"$RUN_DIR/evidence/tc-08-16-after.png"`, then `Read` all three PNGs and state what is on screen in each. The refused image must be IDENTICAL to the before image by eye — a flat sketch and no solid, because a declined mutation must never reach the human's window. The after image must show the extruded solid from the accepted apply. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the images.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-17: Every gated mutation tool fails closed without a confirm

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (the gate applies to every geometry-intent tool)

**VERIFIED SET: 19 tools carry a `confirm` property** — 8 `sketch_*` (`sketch_create`,
`sketch_add_geometry`, `sketch_remove_geometry`, `sketch_add_constraint`,
`sketch_remove_constraint`, `sketch_set_datum`, `sketch_toggle_construction`,
`sketch_add_external_geometry`) and 11 `feature_*` (`feature_pad`, `feature_pocket`,
`feature_revolve`, `feature_hole`, `feature_fillet`, `feature_chamfer`, `feature_pattern`,
`feature_mirror`, `feature_datum`, `feature_body_create`, `feature_set_parameters`). The other
mutating tools (`document_*`, `export_*`, `debug_exec`) carry no `confirm` and are out of scope
here. This is the same 19 that `preview_dry_run` will accept.

**Given** a document holding a body, a fully-constrained sketch, a `Pad` and a `Fillet`, so every one of the 19 tools has a valid target — verify: `mcp query_tree_summary { doc: <handle>, depth: 4 }` lists all four  
**And** the GUI host runs the confirm gate: FreeCAD was started with `FREECAD_BUDDY_AUTO_APPROVE=0`, or with the **Auto-approve mutations** preference off and the variable unset (the default is auto-approve on) — verify: the new `addon.log` lines from that launch do NOT contain `SECURITY: mutation auto-approve ENABLED`  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-attempt window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-17-before.png"}' | & cua-driver call get_window_state`  

**When** for each of the 19 tools an otherwise-valid call is issued with the `confirm` key OMITTED entirely; the `feature_set_parameters` call writes `Length`, not `Visibility` alone (a `Visibility`-only write is display state and needs no confirm)  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad2", length: { value: 30, unit: "mm" } }
mcp sketch_create { doc: <handle>, name: "Sketch2", plane: "XZ" }
...
```
**And** the refusal message from each is recorded  

**Then** all 19 are refused — verify: every one of the 19 calls returns a refusal, none returns `status: "OK"`  
**And** the message is identical on all 19 — verify: each returns `this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id`  
**And** a null confirm is the same as an absent one — verify: `confirm: null` on any of the 19 returns the same message  
**And** nothing was mutated by any of them — verify: `mcp query_tree_summary { doc: <handle>, depth: 4 }` after all 19 calls lists the same nodes as the `Given`  
**And** the set boundary is correct — verify: `mcp document_save { doc: <handle>, path: "$RUN_DIR/evidence/tc-08-17-save.FCStd" }` and `mcp export_stl { doc: <handle>, objects: ["Pad"], path: "$RUN_DIR/evidence/tc-08-17-export.stl" }` succeed WITHOUT a confirm, because they carry no `confirm` property  
**And** the count is exactly 19 — verify: `mcp query_capabilities {}` or the `tools/list` response shows `confirm` in the input schema of exactly 19 tools  
**And** each refused tool works once previewed — verify: for a sample of at least 3 of the 19, a `preview_dry_run` plus its token returns `status: "OK"`  
**And** the display-state carve-out holds — verify: `mcp feature_set_parameters { doc: <handle>, feature: "Pad", parameters: { Visibility: false } }` with no `confirm` returns `status: "OK"` with `mutation.changed: []`, and its audit `approval` line has `mode: "display_state"`; restore with `{ Visibility: true }` before the after-capture  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* none of the 19 refusals changed the model on screen — verify: capture immediately after the 19 refused calls and BEFORE the previewed sample, to `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-17-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what features you see in each. The two images must be visually IDENTICAL by eye — the same body, sketch, pad and fillet, with no added, removed or altered feature, and no error dialog left open. A fail-closed gate that nonetheless let one of the 19 reach the window is the exact defect this catches. The judgement is on the pixels alone — no MCP status, refusal message, tree summary or render may stand in for looking at the image.  

**Cleanup**:
```bash
rm -f "$RUN_DIR/evidence/tc-08-17-save.FCStd" "$RUN_DIR/evidence/tc-08-17-export.stl"
mcp document_close { doc: <handle> }
```

---

### TC-08-18: Headless auto-approves by default; any value other than "1" turns the gate on

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (auto-approve is an operator posture, never a wire field; on by default; a sent token is checked in every posture)

**Host**: H1 headless for the four flag postures. The closing visual asserts the separate GUI
window was never touched by a headless call.

**Given** the H1 headless host can be started with a controlled environment — verify: `"$FCB_PYTHON" -c "import FreeCAD, mcp"` succeeds  
**And** a saved document with a body and a fully-constrained 20x20 mm sketch  
**And** a golden model is open in the GUI so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <gui handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the GUI's framed state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-18-before.png"}' | & cua-driver call get_window_state`  

**When** H1 is started with the flag UNSET, with the audit log redirected, and a gated tool is called without a confirm  
```bash
env -u FREECAD_BUDDY_AUTO_APPROVE FREECAD_BUDDY_AUDIT_LOG="$RUN_DIR/evidence/tc-08-18-approve.jsonl" \
  "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline
```
**And** on the same flag-unset host the call is repeated with a forged token, `confirm: { preview_id: "fcb-preview:forged.AAAA" }`  
**And** H1 is started with `FREECAD_BUDDY_AUTO_APPROVE=1` and the call without a confirm repeated  
**And** H1 is started with `FREECAD_BUDDY_AUTO_APPROVE=0` and the call repeated  
**And** H1 is started with `FREECAD_BUDDY_AUTO_APPROVE=true` (a value that is not `"1"`) and the call repeated  

**Then** unset approves — verify: the flag-unset run returns `status: "OK"` with no `confirm` in the call  
**And** a sent token is checked under auto-approve — verify: the forged-token call on the flag-unset host returns `INVALID_INPUT` with `confirm.preview_id carries an invalid signature`  
**And** the exact flag approves — verify: the `=1` run returns `status: "OK"` with no `confirm` in the call  
**And** `0` turns the gate on — verify: the `=0` run returns `this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id`  
**And** any other value turns the gate on — verify: the `=true` run returns the same refusal, because the flag is compared against the exact string `"1"`  
**And** the operator posture is announced at startup — verify: the stderr of the flag-unset run and of the `=1` run each contain `SECURITY: mutation auto-approve ENABLED (to require preview_id, clear Auto-approve mutations in the FreeCAD GUI: Edit > Preferences > FreeCAD Buddy, or set FREECAD_BUDDY_AUTO_APPROVE=0)`, and the stderr of the `=0` and `=true` runs do not  
**And** the approval is audited — verify: `grep '"mode": *"auto_approve"' "$RUN_DIR/evidence/tc-08-18-approve.jsonl"` returns a line naming the tool and the document handle, with `"source": "FREECAD_BUDDY_AUTO_APPROVE"`  
**And** the audited approval carries no token — verify: that line's `args_digest` is present while no `preview_id` appears, because an auto-approved call presented none  
**And** the refused forged-token call wrote no approval line — verify: the file holds exactly one `approval` line  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <gui handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the separate GUI window was not touched by any of the headless runs — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-18-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen in each. The two images must be visually IDENTICAL by eye — the same golden box, unchanged. A headless auto-approved mutation that reached across into the human's document would be a serious defect, and the audit line proving it "ran headless" is a claim under test, not evidence that the window was spared. The judgement is on the pixels alone — no MCP status, audit line or render may stand in for looking at the image.  

**Cleanup**: stop the H1 host.
```bash
rm -f "$RUN_DIR/evidence/tc-08-18-approve.jsonl"
```
```
mcp document_close { doc: <gui handle> }
```

---

### TC-08-19: Previewing a non-previewable tool lists the previewable set

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.8 (the op table is injected; an absent tool is rejected before any file is written)

**Given** a body with a fully-constrained 20x20 mm sketch  
**And** no stale preview TempDocs — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-attempt window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-19-before.png"}' | & cua-driver call get_window_state`  

**When** a mutating tool that is not in the op table is previewed  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "document_save", args: { path: "$RUN_DIR/evidence/tc-08-19-save.FCStd" } } }
mcp preview_dry_run { doc: <handle>, operation: { tool: "debug_exec", args: { code: "1" } } }
mcp preview_dry_run { doc: <handle>, operation: { tool: "no_such_tool", args: {} } }
```
**And** a malformed operation object is previewed  
```
mcp preview_dry_run { doc: <handle>, operation: { args: { name: "Pad" } } }
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: "not an object" } }
```

**Then** a non-previewable tool is named and the alternatives listed — verify: `document_save` returns `not a previewable mutation tool: 'document_save' (previewable: ` followed by the comma-separated sorted tool list  
**And** the listed set is the 19 gated tools — verify: the `previewable:` list holds exactly the 8 `sketch_*` and 11 `feature_*` names, and no `document_*`, `export_*` or `debug_exec`  
**And** an unknown tool gets the same treatment — verify: `no_such_tool` returns the same message form with its own name quoted  
**And** a missing `tool` is refused — verify: the first malformed call returns `preview_dry_run requires operation.tool`  
**And** a non-object `args` is refused — verify: the second malformed call returns `operation.args must be an object`  
**And** the refusal happened before any file was written — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing after all five calls  
**And** a missing `operation` is refused — verify: `mcp preview_dry_run { doc: <handle> }` is rejected by the schema, because `operation` is in `required`  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* none of the five refused previews altered the window — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-19-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen, in the tree and in the title bar of each. The two images must be visually IDENTICAL by eye — the same body and sketch, no new feature, and no save marker or exec side effect visible in the title bar or the tree. The judgement is on the pixels alone — no MCP status, refusal message or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-20: operation.args carrying `doc` is refused

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.8 (the preview supplies the document handle)

**Given** a body with a fully-constrained 20x20 mm sketch  
**And** a second open document, so the redundant handle could name a different one — verify: `mcp document_list {}` returns two handles  
**And** document A is in the live viewport and framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle-a> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-attempt window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-20-before.png"}' | & cua-driver call get_window_state`  

**When** a preview is taken with the document handle repeated inside `args`  
```
mcp preview_dry_run { doc: <handle-a>, operation: { tool: "feature_pad", args: { doc: "<handle-a>", body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
```
**And** it is repeated with `args.doc` naming the OTHER document  
```
mcp preview_dry_run { doc: <handle-a>, operation: { tool: "feature_pad", args: { doc: "<handle-b>", body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
```

**Then** the redundant handle is refused — verify: the first call returns `operation.args must not carry 'doc'; the preview supplies it`  
**And** a conflicting handle is refused identically — verify: the second call returns the same message, not a message about the mismatch  
**And** no TempDoc was created — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing after both calls  
**And** neither document was mutated — verify: `mcp query_tree_summary` on both handles lists no `Pad`  
**And** omitting `args.doc` succeeds — verify: the same preview without the `doc` key inside `args` returns `status: "OK"`  
**And** the token the successful preview mints names the outer handle — verify: applying it against `<handle-b>` returns `confirm.preview_id was issued for a different document`  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle-a> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* document A's viewport is unchanged by both refused previews — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-20-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen and which document's title the window carries in each. The two images must be visually IDENTICAL by eye — a flat sketch with no pad, and document B was not silently activated into the viewport. The judgement is on the pixels alone — no MCP status, tree summary or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle-a> }
mcp document_close { doc: <handle-b> }
```

---

### TC-08-21: document_undo never reports an undo that did not happen

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (undo is refused, never silently no-op)

**Given** a freshly created document with nothing undone yet — verify: `mcp document_create { label: "UndoProbe" }` returns a handle  
**And** a second document whose undo stack cannot be enabled, if one is available  
**And** the model is framed BEFORE the before-capture, so both images share one camera — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the pre-mutation window state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-21-before.png"}' | & cua-driver call get_window_state`  

**When** undo is called on the empty stack  
```
mcp document_undo { doc: <handle> }
```
**And** one mutation is applied, undone, then undo is called again past the bottom of the stack  
```
mcp feature_body_create { doc: <handle>, name: "Body", confirm: { preview_id: "<token>" } }
mcp document_undo { doc: <handle> }
mcp document_undo { doc: <handle> }
```
**And** undo is called on a document reporting `UndoMode 0`  

**Then** an empty stack is refused, not reported as done — verify: the first call returns `nothing to undo on <Name>: the undo stack is empty`  
**And** the first real undo succeeds — verify: the first `document_undo` after the mutation returns `status: "OK"` with `undone` equal to `buddy: <the body-create label>`  
**And** exhausting the stack is refused — verify: the second `document_undo` after the mutation returns the same empty-stack refusal  
**And** the refusal never carries a fabricated result — verify: neither refusal returns a `matches_pre_op`, `fingerprint_after` or `undone` field  
**And** unavailable undo is its own refusal — verify: the `UndoMode 0` document returns `undo is unavailable on <Name>: the document reports UndoMode 0`, distinct from the empty-stack message  
**And** an open transaction is refused rather than guessed at — verify: on a document with a transaction left open by the GUI, `document_undo` returns `<Name> has an open transaction; undo would commit it and revert the transaction beneath it. Commit or abort it first.`  
**And** an undo that leaves the document broken is not `OK` — verify: an undo whose recompute leaves an object in an error state returns `status: "RECOMPUTE_ERROR"`, with the offending object named in `errors`  
**And** the undo count is reported — verify: after the successful undo, `undo_count` is `0`  
**And** *(visual)* the model is framed with the same camera as the before-capture — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the window is restored to its pre-mutation appearance — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-08-21-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and state what is on screen and in the model tree in each. **This is an UNDO: the post-undo image must match the pre-mutation image by eye** — the `Body` created by the mutation is gone from both the tree and the viewport, and no refusal left an error dialog open. A `status: "OK"` with `undo_count: 0` over a window that still shows the `Body` is a finding; so is a window that is visually restored while the envelope refused. Record which of the two is wrong in `$RUN_DIR/bugs.md`. The judgement is on the pixels alone — no MCP status, `undone` label or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```
