# TC-08: Preview, the Confirm-Token Gate & Verified Undo

Validates AD-10: no geometry mutation runs without a `preview_id` this process minted for exactly
this tool, these arguments, this document and this document state. The gate in
`usecases/confirm.py` is the only thing standing between a model and an unreviewed change, so each
refusal path is tested for its own distinct message — a gate that refuses everything with one
generic error cannot tell a caller what to fix. Also covers `preview_dry_run` leaving the live
document untouched, and `document_undo` reporting restoration as a measurement rather than an
assumption. Driven over MCP against the live bridge; no automation script covers this surface.

## Prerequisites
- [ ] FreeCAD GUI open and the addon bridge serving `:8765` (verify: `netstat -ano | grep :8765` shows LISTENING)
- [ ] Host is NOT in auto-approve posture (verify: `mcp query_capabilities {}` reports `auto_approve: false`)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)
- [ ] No stale preview TempDocs (verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing)

---

### TC-08-01: preview_dry_run returns the structured diff

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.8 (preview_dry_run), `data-contracts-design.md` §8 (GeometryDiff)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm rectangular sketch on XY (verify: `mcp query_sketch_info { doc: <handle>, sketch: "Sketch" }` returns `fully_constrained: true`)

**Steps**:
1. Preview a 30 mm pad:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
   ```

**Checkpoints**:
- [ ] CP1: The envelope succeeded — verify: `status` is `OK`, `detail` is `null`, and `structured_content.diff.schema` equals `"fcb.geometry-diff/1"`
- [ ] CP2: The volume delta is measured with units — verify: `diff.deltas.volume` reports `before: 0.0`, `after: 12000.0`, `delta: 12000.0`, `units: "mm^3"`
- [ ] CP3: Area and bbox carry their own units — verify: `diff.deltas.area.units` equals `"mm^2"` and `diff.deltas.bbox.units` equals `"mm"`, and `diff.deltas.com.units` equals `"mm"`
- [ ] CP4: Topology counts are deltas, not totals — verify: `diff.counts.solids` reports `before: 0`, `after: 1`, `delta: 1`, and `diff.counts.faces.delta` equals `6`
- [ ] CP5: The three name sets are reported — verify: `diff.touched` contains `"Pad"`, `diff.new` contains `"Pad"`, and `diff.deleted` is `[]`
- [ ] CP6: Validity carries the op's own verdict — verify: `diff.validity.is_valid` is `true`, `diff.validity.recompute_clean` is `true`, `diff.validity.status` is `"OK"`, `diff.validity.explanation` is `null`
- [ ] CP7: The TNP pre-check is present — verify: `diff.tnp_precheck.status` is one of `CLEAN`, `FLAGGED`, `UNSUPPORTED` and `diff.tnp_precheck.element_map_version` is present
- [ ] CP8: A token and its deadline were issued — verify: `structured_content.preview_id` starts with `fcb-preview:` and `structured_content.expires_at` is an ISO-8601 UTC timestamp

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-02: A preview leaves the live document unchanged

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §3.8 (throwaway copy), `verification-design.md` §1

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad` (verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`)
- [ ] No stale preview TempDocs (verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing)

**Steps**:
1. Record the live mass properties and the open document list:
   ```
   mcp query_mass_properties { doc: <handle>, object: "Pad" }
   mcp document_list {}
   ```
2. Preview a change that WOULD alter the geometry:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_set_parameters", args: { feature: "Pad", parameters: { Length: { value: 80, unit: "mm" } } } } }
   ```
3. Re-read the live mass properties and document list.

**Checkpoints**:
- [ ] CP1: The preview reported the change — verify: `diff.deltas.volume.after` equals `32000.0` (20 x 20 x 80 mm)
- [ ] CP2: The live volume is unchanged — verify: the step-3 `query_mass_properties` returns `volume` = `12000.0`, byte-identical to step 1
- [ ] CP3: The live bbox and centre of mass are unchanged — verify: step-3 `bbox` and `com` equal step 1
- [ ] CP4: No TempDoc was adopted into the document list — verify: step-3 `document_list` holds the same handles as step 1, with no name starting `FCB_TMP_prev_`
- [ ] CP5: The TempDoc directory is gone — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing
- [ ] CP6: The preview did not report a live-document change — verify: the envelope is `OK`, not a `SPEC_FAILED` carrying `preview changed the live document`
- [ ] CP7: Cleanup happens on the failing path too — verify: after previewing an operation that FAILS on the copy, `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` still returns nothing

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
rm -rf "$TEMP"/FCB_TMP_prev_*
```

---

### TC-08-03: A preview_id authorizes exactly that apply

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (confirm gate), `data-contracts-design.md` §8

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch (verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists `Body` and `Sketch`, not `Pad`)

**Steps**:
1. Preview the pad and keep the token:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
   ```
2. Apply the identical operation with that token:
   ```
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The apply was authorized — verify: `status` is `OK` and `detail` is `null`
- [ ] CP2: The mutation committed — verify: `mutation.rolled_back` is `false` and `mutation.fingerprint_after` is a full record
- [ ] CP3: The token's signed fingerprint matched the live one — verify: `mutation.fingerprint_before.digest` equals the preview's `diff.fingerprint_before`
- [ ] CP4: The geometry matches what the preview predicted — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`, equal to `diff.deltas.volume.after`
- [ ] CP5: The token form is as documented — verify: the `preview_id` matches `^fcb-preview:[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$`
- [ ] CP6: An explicit accept is also honored — verify: the same flow with `confirm: { preview_id: "<fresh token>", elicitation_action: "accept" }` also returns `status: "OK"`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-04: A preview of a failing operation is still a successful preview

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.8 (a failing op is a successful preview reporting a failing diff)

**Preconditions**:
- [ ] A body with a 30 mm `Pad` (verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`)

**Steps**:
1. Preview a fillet whose radius cannot fit the edge:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "geometric", object: "Pad", subelement: "Edge1" }], radius: { value: 500, unit: "mm" } } } }
   ```

**Checkpoints**:
- [ ] CP1: The envelope is a success — verify: `status` is `OK` and `detail` is `null`
- [ ] CP2: The failure travels in `validity`, not in the envelope — verify: `diff.validity.is_valid` is `false` and `diff.validity.status` is `SPEC_FAILED` or `RECOMPUTE_ERROR`
- [ ] CP3: The failure has a stated reason — verify: `diff.validity.explanation` is a non-null, non-empty string naming the failing check
- [ ] CP4: The diff still reports measurements — verify: `diff.deltas.volume` is present with `before`, `after`, `delta` and `units`
- [ ] CP5: Nothing is reported as touched or new, because the op rolled back on the copy — verify: `diff.new` is `[]`
- [ ] CP6: A token was still issued — verify: `structured_content.preview_id` is non-null, because the op reached the gate on the copy
- [ ] CP7: The live document is unchanged — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-05: `render:"off"` and an unavailable render are reported distinctly

**Priority**: Medium
**Design Ref**: `mcp-tools-design.md` §3.8 (render block; unavailability is not an error)

**Preconditions**:
- [ ] A body with a 30 mm `Pad`
- [ ] A GUI host with a render port available (verify: `mcp query_screenshot { doc: <handle>, view: { camera: "iso" } }` returns `status: "OK"` with a `resource_link`)

**Steps**:
1. Preview with the render explicitly off:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_set_parameters", args: { feature: "Pad", parameters: { Length: { value: 40, unit: "mm" } } } }, render: "off" }
   ```
2. Preview with the render left on the default:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_set_parameters", args: { feature: "Pad", parameters: { Length: { value: 40, unit: "mm" } } } }, render: "auto" }
   ```
3. Repeat step 2 against a headless host, which has no render port.

**Checkpoints**:
- [ ] CP1: An explicit opt-out is recorded as such — verify: step 1 returns `diff.render` equal to `{ "available": false, "reason": "off" }`
- [ ] CP2: A missing port is a different reason — verify: step 3 returns `diff.render.reason` equal to `"no render port"`, not `"off"`
- [ ] CP3: The two are never collapsed — verify: `"off"` never appears as the reason on a call that did not pass `render: "off"`
- [ ] CP4: Neither case is an error — verify: both step 1 and step 3 return envelope `status: "OK"`
- [ ] CP5: An available render says so — verify: step 2 on the GUI host returns `diff.render.available` equal to `true`
- [ ] CP6: The enum is closed — verify: `mcp preview_dry_run { doc: <handle>, operation: {...}, render: "sometimes" }` is rejected by the schema, because `render` enumerates only `["auto", "off"]`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-06: document_undo reports a measured match against expect_fingerprint

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (restoration is reported, never assumed), `data-contracts-design.md` §8

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch, undo available (verify: `mcp document_undo { doc: <handle> }` is not refused with `undo is unavailable`)

**Steps**:
1. Apply a pad and keep BOTH forms of its before-fingerprint:
   ```
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>" } }
   ```
   Keep `mutation.fingerprint_before.digest` (the string form) and the whole
   `mutation.fingerprint_before` object (the record form).
2. Undo with the string form:
   ```
   mcp document_undo { doc: <handle>, expect_fingerprint: "<digest string>" }
   ```
3. Re-apply the pad, then undo with the record form:
   ```
   mcp document_undo { doc: <handle>, expect_fingerprint: { schema: "...", serializer: "...", objects: [...], digest: "..." } }
   ```

**Checkpoints**:
- [ ] CP1: The string form reports a match — verify: step 2 returns `matches_pre_op: true`
- [ ] CP2: The record form reports a match — verify: step 3 returns `matches_pre_op: true`
- [ ] CP3: Both fingerprints are reported, before and after the undo — verify: `fingerprint_before` and `fingerprint_after` are both 64-hex digests and differ from each other
- [ ] CP4: The undone transaction is named — verify: `undone` equals `buddy: <the pad's transaction label>`
- [ ] CP5: The text states the measurement, not an assumption — verify: envelope `text` contains `restored the pre-op state`
- [ ] CP6: No expectation gives no verdict — verify: `mcp document_undo { doc: <handle> }` with no `expect_fingerprint` returns `matches_pre_op: null` and `text` containing `no pre-op digest supplied to compare against`
- [ ] CP7: The object set is reported — verify: `restored_objects` lists `Body`, `Sketch` and their Origin members, and does NOT list `Pad`
- [ ] CP8: A wrong type is refused, not reported as a non-match — verify: `mcp document_undo { doc: <handle>, expect_fingerprint: 42 }` is refused with `expect_fingerprint must be a fingerprint digest string or a FingerprintRecord, got int`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-07: A token is single-use

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (a token authorizes one mutation)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch
- [ ] A previewed, unspent token for `feature_body_create`, which can run twice under different names without changing the fingerprint in a way that blocks the replay

**Steps**:
1. Preview and apply an operation that commits without moving the document digest — creating an
   empty body adds no shape, so the fingerprint is unchanged:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_body_create", args: { name: "Probe" } } }
   mcp feature_body_create { doc: <handle>, name: "Probe", confirm: { preview_id: "<token>" } }
   ```
2. Replay the SAME token on the identical call:
   ```
   mcp feature_body_create { doc: <handle>, name: "Probe", confirm: { preview_id: "<same token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The first apply was authorized — verify: step 1's mutation returns `status: "OK"`
- [ ] CP2: The fingerprint did not move — verify: step 1's `mutation.fingerprint_before.digest` equals `mutation.fingerprint_after.digest`, which is what makes the spent-check the only thing refusing the replay
- [ ] CP3: The replay is refused — verify: step 2 returns the refusal `confirm.preview_id has already authorized a mutation; re-run preview_dry_run`
- [ ] CP4: The refusal is not a fingerprint complaint — verify: the message does NOT contain `the document has changed since the preview was taken`
- [ ] CP5: The replay mutated nothing — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` lists exactly one `Probe` body, not two
- [ ] CP6: A fresh preview restores the ability to apply — verify: a new `preview_dry_run` for the same operation yields a token whose apply returns `status: "OK"`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-08: A token is bound to the tool that minted it

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (the gate re-derives the tool from the call)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch (verify: `mcp query_sketch_info { doc: <handle>, sketch: "Sketch" }` returns `fully_constrained: true`)

**Steps**:
1. Preview a PAD, keeping its token:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
   ```
2. Present that token to a POCKET with otherwise identical arguments:
   ```
   mcp feature_pocket { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<pad token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The call is refused — verify: it returns the refusal `confirm.preview_id was issued for 'feature_pad', not 'feature_pocket'`
- [ ] CP2: Both tool names appear in the message — verify: the message names the minting tool first and the called tool second, in that order
- [ ] CP3: Nothing was mutated — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists neither `Pad` nor a pocket
- [ ] CP4: The refusal is not an argument complaint — verify: the message does NOT contain `was issued for different arguments`
- [ ] CP5: The token is still usable on its own tool — verify: presenting the same token to `feature_pad` with the same arguments returns `status: "OK"`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-09: A token is bound to the arguments it was minted for

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (args_digest comparison)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch

**Steps**:
1. Preview a 30 mm pad:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
   ```
2. Present the token to the same tool with a DIFFERENT length:
   ```
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 60, unit: "mm" }, confirm: { preview_id: "<30 mm token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The call is refused — verify: it returns the refusal `confirm.preview_id was issued for different arguments`
- [ ] CP2: Nothing was mutated — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Pad`
- [ ] CP3: A one-character difference is enough — verify: presenting the token with `name: "Pad1"` and every other argument identical is refused with the same message
- [ ] CP4: `doc` is excluded from the digest, so it is not what refused this — verify: the refusal message is NOT `confirm.preview_id was issued for a different document`
- [ ] CP5: `confirm` itself is excluded from the digest — verify: presenting the same token as `confirm: { preview_id: "<token>", elicitation_action: "accept" }` with the original 30 mm arguments returns `status: "OK"`, proving adding the `elicitation_action` field did not change the digest
- [ ] CP6: The identical call is still authorized — verify: re-presenting a FRESH 30 mm token with the 30 mm arguments returns `status: "OK"`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-10: A token is bound to the document it was minted on

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (doc handle comparison)

**Preconditions**:
- [ ] TWO documents open, each with a body and an identical fully-constrained 20x20 mm sketch (verify: `mcp document_list {}` returns two handles, `<handle-a>` and `<handle-b>`)

**Steps**:
1. Preview the pad on document A:
   ```
   mcp preview_dry_run { doc: <handle-a>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
   ```
2. Present A's token to the identical call on document B:
   ```
   mcp feature_pad { doc: <handle-b>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<A's token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The call is refused — verify: it returns the refusal `confirm.preview_id was issued for a different document`
- [ ] CP2: Document B was not mutated — verify: `mcp query_tree_summary { doc: <handle-b>, depth: 3 }` does not list `Pad`
- [ ] CP3: Document A was not mutated either — verify: `mcp query_tree_summary { doc: <handle-a>, depth: 3 }` does not list `Pad`
- [ ] CP4: Identical geometry does not defeat the binding — verify: the refusal holds even though the two documents are byte-identical copies, because the comparison is on the handle, not the content
- [ ] CP5: The refusal is not an argument complaint — verify: the message does NOT contain `was issued for different arguments`
- [ ] CP6: A's token still works on A — verify: presenting the same token to the same call on `<handle-a>` returns `status: "OK"`

**Cleanup**:
```bash
mcp document_close { doc: <handle-a> }
mcp document_close { doc: <handle-b> }
```

---

### TC-08-11: A token is bound to the document state it measured

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (fingerprint_before comparison)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch

**Steps**:
1. Preview the pad and keep its token:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
   ```
2. Change the document between the preview and the apply — widen the sketch:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "sketch_set_datum", args: { sketch: "Sketch", constraint: "Width", value: { value: 40, unit: "mm" } } } }
   mcp sketch_set_datum { doc: <handle>, sketch: "Sketch", constraint: "Width", value: { value: 40, unit: "mm" }, confirm: { preview_id: "<datum token>" } }
   ```
3. Present the STALE step-1 token:
   ```
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<step-1 token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The stale token is refused — verify: step 3 returns the refusal `the document has changed since the preview was taken; re-run preview_dry_run`
- [ ] CP2: The intervening mutation did commit — verify: step 2 returns `status: "OK"` and `mcp query_sketch_info { doc: <handle>, sketch: "Sketch" }` reports the 40 mm width
- [ ] CP3: Nothing was padded — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Pad`
- [ ] CP4: The refusal is not a spent-token complaint — verify: the message does NOT contain `has already authorized a mutation`
- [ ] CP5: Re-previewing recovers — verify: a fresh `preview_dry_run` for the same pad, followed by its apply, returns `status: "OK"`
- [ ] CP6: An unreadable live state is also a refusal, not a crash — verify: a document whose shape cannot be serialized produces a refusal starting `cannot read the state of ` and naming the handle

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-12: An expired token is refused as expired, before the spent check

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §4 (TTL 900 s; expiry checked before the spent set)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch
- [ ] Ability to wait past the 900 s TTL, or a host clock the test may advance

**Steps**:
1. Preview an operation whose apply will not move the document digest, so its token stays
   otherwise valid, and record `expires_at`:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_body_create", args: { name: "Probe" } } }
   ```
2. SPEND that token by applying it once:
   ```
   mcp feature_body_create { doc: <handle>, name: "Probe", confirm: { preview_id: "<token>" } }
   ```
3. Wait past the deadline (901 s from mint), then present the SAME spent-and-expired token:
   ```
   mcp feature_body_create { doc: <handle>, name: "Probe", confirm: { preview_id: "<token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The advertised TTL is 900 s — verify: `expires_at` minus the call time is 900 seconds, to within clock skew
- [ ] CP2: The expired token is refused as expired — verify: step 3 returns `confirm.preview_id has expired; re-run preview_dry_run`
- [ ] CP3: Expiry wins over spent — verify: step 3's message is the expiry message, NOT `confirm.preview_id has already authorized a mutation; re-run preview_dry_run`, even though the token was spent in step 2
- [ ] CP4: The ordering is only observable on a spent-AND-expired token — verify: the same token presented at step 2+1 s (spent, not expired) DOES return the already-authorized message, proving both checks are live
- [ ] CP5: An unexpired unspent token still works — verify: a fresh preview's token applied within the TTL returns `status: "OK"`
- [ ] CP6: The expired call mutated nothing — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` lists exactly one `Probe` body

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-13: A refused call does not spend its token

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (spend once the mutation is going ahead, after any precheck)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch

**Steps**:
1. Preview a 30 mm pad:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
   ```
2. Make a call the gate REFUSES — wrong arguments for this token:
   ```
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 60, unit: "mm" }, confirm: { preview_id: "<token>" } }
   ```
3. Correct the call and re-send the SAME token:
   ```
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<same token>" } }
   ```

**Checkpoints**:
- [ ] CP1: Step 2 was refused — verify: it returns `confirm.preview_id was issued for different arguments`
- [ ] CP2: The corrected call is authorized — verify: step 3 returns `status: "OK"`
- [ ] CP3: The corrected call was NOT refused as spent — verify: step 3's response contains no `has already authorized a mutation` message
- [ ] CP4: The geometry landed — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`
- [ ] CP5: The token is spent only after the successful apply — verify: re-sending the same token a fourth time now returns `confirm.preview_id has already authorized a mutation; re-run preview_dry_run`
- [ ] CP6: Other refusal paths also leave the token usable — verify: repeating the flow where step 2 is refused with `confirm.elicitation_action must be 'accept', got 'decline'` still lets step 3 succeed

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-14: Tampered, malformed and foreign tokens produce distinct messages

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (token codec), `data-contracts-design.md` §8

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch
- [ ] One valid `feature_pad` token in hand, from `preview_dry_run`

**Steps**:
1. Present each malformed token in turn to the same `feature_pad` call, changing only
   `confirm.preview_id`:
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

**Checkpoints**:
- [ ] CP1: No prefix — verify: `"not-a-token"` returns `confirm.preview_id is not a preview token`
- [ ] CP2: No separator, or an empty half — verify: `"fcb-preview:onlybody"`, `"fcb-preview:.sig"` and `"fcb-preview:body."` each return `confirm.preview_id is malformed`
- [ ] CP3: Undecodable base64 — verify: `"fcb-preview:!!!!.!!!!"` returns `confirm.preview_id is not decodable`
- [ ] CP4: A tampered signature — verify: the signature-altered token returns `confirm.preview_id carries an invalid signature`
- [ ] CP5: Each message is distinct — verify: the four messages above are four different strings; a single generic refusal for all of them is a defect
- [ ] CP6: A payload missing a required field is named — verify: a token whose body decodes to an object lacking a payload field returns `confirm.preview_id payload is missing ` followed by the list of missing keys
- [ ] CP7: A non-string `preview_id` is refused — verify: `confirm: { preview_id: 12345 }` returns `confirm.preview_id is not a preview token`
- [ ] CP8: None of the variants mutated anything — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Pad` after all variants have been tried

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-15: An undeclared confirm field is refused, never silently dropped

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (`_CONFIRM_SCHEMA`; `autoApprove` is absent from the wire by design)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch
- [ ] One valid `feature_pad` token in hand

**Steps**:
1. Present the valid token alongside an undeclared field:
   ```
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>", autoApprove: true } }
   ```
2. Repeat with two undeclared fields:
   ```
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>", autoApprove: true, force: 1 } }
   ```
3. Present a `confirm` that is not an object:
   ```
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: "yes" }
   ```

**Checkpoints**:
- [ ] CP1: The undeclared field is refused — verify: step 1 returns `confirm carries field(s) the schema does not declare: ['autoApprove']`
- [ ] CP2: The unknown keys are listed, sorted — verify: step 2 returns `confirm carries field(s) the schema does not declare: ['autoApprove', 'force']`
- [ ] CP3: It was not silently dropped — verify: step 1 did NOT return `status: "OK"`, and `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Pad`
- [ ] CP4: A non-object confirm is refused with its own message — verify: step 3 returns either the schema rejection for a non-object `confirm`, or `confirm must be an object`
- [ ] CP5: The token survives the refusal — verify: re-presenting the same token with `confirm: { preview_id: "<token>" }` alone returns `status: "OK"`
- [ ] CP6: Only the two declared fields are accepted — verify: `confirm: { preview_id: "<fresh token>", elicitation_action: "accept" }` is authorized, and no third key is

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-16: An elicitation_action other than accept is refused

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (`elicitation_action` enum is `["accept"]`)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch
- [ ] One valid `feature_pad` token in hand

**Steps**:
1. Present the valid token with a declining action:
   ```
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>", elicitation_action: "decline" } }
   ```
2. Repeat with `"cancel"` and with `null`.

**Checkpoints**:
- [ ] CP1: A declining action is refused — verify: the call returns `confirm.elicitation_action must be 'accept', got 'decline'`
- [ ] CP2: The rejected value is quoted back — verify: the message ends with the Python repr of the supplied value, so `"cancel"` yields `got 'cancel'` and `null` yields `got None`
- [ ] CP3: The schema also closes the enum — verify: the same call may instead be rejected at the JSON Schema layer, because `elicitation_action` enumerates only `["accept"]`; either refusal is a pass, a silent acceptance is not
- [ ] CP4: Nothing was mutated — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Pad`
- [ ] CP5: The token survives — verify: re-presenting the same token with `elicitation_action: "accept"` returns `status: "OK"`
- [ ] CP6: Omitting the field defaults to accept — verify: `confirm: { preview_id: "<fresh token>" }` alone returns `status: "OK"`

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

**Preconditions**:
- [ ] A document holding a body, a fully-constrained sketch, a `Pad` and a `Fillet`, so every one of the 19 tools has a valid target (verify: `mcp query_tree_summary { doc: <handle>, depth: 4 }` lists all four)
- [ ] Host is NOT in auto-approve posture

**Steps**:
1. For each of the 19 tools, issue an otherwise-valid call with the `confirm` key OMITTED entirely:
   ```
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad2", length: { value: 30, unit: "mm" } }
   mcp sketch_create { doc: <handle>, name: "Sketch2", plane: "XZ" }
   ...
   ```
2. Record the refusal message from each.

**Checkpoints**:
- [ ] CP1: All 19 are refused — verify: every one of the 19 calls returns a refusal, none returns `status: "OK"`
- [ ] CP2: The message is identical on all 19 — verify: each returns `this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id`
- [ ] CP3: A null confirm is the same as an absent one — verify: `confirm: null` on any of the 19 returns the same message
- [ ] CP4: Nothing was mutated by any of them — verify: `mcp query_tree_summary { doc: <handle>, depth: 4 }` after all 19 calls lists the same nodes as the precondition
- [ ] CP5: The set boundary is correct — verify: `mcp document_save { doc: <handle>, path: "/tmp/fcb-uat.FCStd" }` and `mcp export_stl { doc: <handle>, objects: ["Pad"], path: "/tmp/fcb-uat.stl" }` succeed WITHOUT a confirm, because they carry no `confirm` property
- [ ] CP6: The count is exactly 19 — verify: `mcp query_capabilities {}` or the `tools/list` response shows `confirm` in the input schema of exactly 19 tools
- [ ] CP7: Each refused tool works once previewed — verify: for a sample of at least 3 of the 19, a `preview_dry_run` plus its token returns `status: "OK"`

**Cleanup**:
```bash
rm -f /tmp/fcb-uat.FCStd /tmp/fcb-uat.stl
mcp document_close { doc: <handle> }
```

---

### TC-08-18: Headless fails closed unless FREECAD_BUDDY_AUTO_APPROVE is exactly "1"

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` §4 (auto-approve is an operator posture, never a wire field)

**Preconditions**:
- [ ] The H1 headless host can be started with a controlled environment (verify: `"$USERPROFILE/micromamba/envs/fcb/python.exe" -c "import FreeCAD, mcp"` succeeds)
- [ ] A saved document with a body and a fully-constrained 20x20 mm sketch

**Steps**:
1. Start H1 with the flag UNSET and call a gated tool without a confirm.
2. Start H1 with `FREECAD_BUDDY_AUTO_APPROVE=true` (a truthy value that is not `"1"`) and repeat.
3. Start H1 with `FREECAD_BUDDY_AUTO_APPROVE=1` and repeat, with the audit log redirected:
   ```bash
   FREECAD_BUDDY_AUTO_APPROVE=1 FREECAD_BUDDY_AUDIT_LOG=/tmp/fcb-approve.jsonl \
     "$USERPROFILE/micromamba/envs/fcb/python.exe" -m freecad_buddy.hosts.main serve --transport stdio --mode inline
   ```

**Checkpoints**:
- [ ] CP1: Unset fails closed — verify: step 1 returns `this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id`
- [ ] CP2: A non-`"1"` truthy value fails closed — verify: step 2 returns the same refusal, because the flag is compared against the exact string `"1"`
- [ ] CP3: The exact flag approves — verify: step 3 returns `status: "OK"` with no `confirm` in the call
- [ ] CP4: The operator posture is announced at startup — verify: `grep "SECURITY: mutation auto-approve ENABLED by operator flag" <the step-3 stderr log>` returns a match
- [ ] CP5: The approval is audited — verify: `grep '"mode": *"auto_approve"' /tmp/fcb-approve.jsonl` returns a line naming the tool and the document handle
- [ ] CP6: The audited approval carries no token — verify: that line's `args_digest` is present while no `preview_id` appears, because an auto-approved call presented none
- [ ] CP7: The posture is reported on the capability record — verify: `mcp query_capabilities {}` on the step-3 host reports auto-approve enabled, and on the step-1 host reports it disabled

**Cleanup**:
```bash
rm -f /tmp/fcb-approve.jsonl
```

---

### TC-08-19: Previewing a non-previewable tool lists the previewable set

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.8 (the op table is injected; an absent tool is rejected before any file is written)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch
- [ ] No stale preview TempDocs (verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing)

**Steps**:
1. Preview a mutating tool that is not in the op table:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "document_save", args: { path: "/tmp/fcb-uat.FCStd" } } }
   mcp preview_dry_run { doc: <handle>, operation: { tool: "debug_exec", args: { code: "1" } } }
   mcp preview_dry_run { doc: <handle>, operation: { tool: "no_such_tool", args: {} } }
   ```
2. Preview a malformed operation object:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { args: { name: "Pad" } } }
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: "not an object" } }
   ```

**Checkpoints**:
- [ ] CP1: A non-previewable tool is named and the alternatives listed — verify: `document_save` returns `not a previewable mutation tool: 'document_save' (previewable: ` followed by the comma-separated sorted tool list
- [ ] CP2: The listed set is the 19 gated tools — verify: the `previewable:` list holds exactly the 8 `sketch_*` and 11 `feature_*` names, and no `document_*`, `export_*` or `debug_exec`
- [ ] CP3: An unknown tool gets the same treatment — verify: `no_such_tool` returns the same message form with its own name quoted
- [ ] CP4: A missing `tool` is refused — verify: the first step-2 call returns `preview_dry_run requires operation.tool`
- [ ] CP5: A non-object `args` is refused — verify: the second step-2 call returns `operation.args must be an object`
- [ ] CP6: The refusal happened before any file was written — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing after all five calls
- [ ] CP7: A missing `operation` is refused — verify: `mcp preview_dry_run { doc: <handle> }` is rejected by the schema, because `operation` is in `required`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-08-20: operation.args carrying `doc` is refused

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.8 (the preview supplies the document handle)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch
- [ ] A second open document, so the redundant handle could name a different one (verify: `mcp document_list {}` returns two handles)

**Steps**:
1. Preview with the document handle repeated inside `args`:
   ```
   mcp preview_dry_run { doc: <handle-a>, operation: { tool: "feature_pad", args: { doc: "<handle-a>", body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
   ```
2. Repeat with `args.doc` naming the OTHER document:
   ```
   mcp preview_dry_run { doc: <handle-a>, operation: { tool: "feature_pad", args: { doc: "<handle-b>", body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
   ```

**Checkpoints**:
- [ ] CP1: The redundant handle is refused — verify: step 1 returns `operation.args must not carry 'doc'; the preview supplies it`
- [ ] CP2: A conflicting handle is refused identically — verify: step 2 returns the same message, not a message about the mismatch
- [ ] CP3: No TempDoc was created — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing after both calls
- [ ] CP4: Neither document was mutated — verify: `mcp query_tree_summary` on both handles lists no `Pad`
- [ ] CP5: Omitting `args.doc` succeeds — verify: the same preview without the `doc` key inside `args` returns `status: "OK"`
- [ ] CP6: The token the successful preview mints names the outer handle — verify: applying it against `<handle-b>` returns `confirm.preview_id was issued for a different document`

**Cleanup**:
```bash
mcp document_close { doc: <handle-a> }
mcp document_close { doc: <handle-b> }
```

---

### TC-08-21: document_undo never reports an undo that did not happen

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (undo is refused, never silently no-op)

**Preconditions**:
- [ ] A freshly created document with nothing undone yet (verify: `mcp document_create { label: "UndoProbe" }` returns a handle)
- [ ] A second document whose undo stack cannot be enabled, if one is available

**Steps**:
1. Call undo on the empty stack:
   ```
   mcp document_undo { doc: <handle> }
   ```
2. Apply one mutation, undo it, then undo again past the bottom of the stack:
   ```
   mcp feature_body_create { doc: <handle>, name: "Body", confirm: { preview_id: "<token>" } }
   mcp document_undo { doc: <handle> }
   mcp document_undo { doc: <handle> }
   ```
3. On a document reporting `UndoMode 0`, call undo.

**Checkpoints**:
- [ ] CP1: An empty stack is refused, not reported as done — verify: step 1 returns `nothing to undo on <Name>: the undo stack is empty`
- [ ] CP2: The first real undo succeeds — verify: the step-2 first `document_undo` returns `status: "OK"` with `undone` equal to `buddy: <the body-create label>`
- [ ] CP3: Exhausting the stack is refused — verify: the step-2 second `document_undo` returns the same empty-stack refusal
- [ ] CP4: The refusal never carries a fabricated result — verify: neither refusal returns a `matches_pre_op`, `fingerprint_after` or `undone` field
- [ ] CP5: Unavailable undo is its own refusal — verify: step 3 returns `undo is unavailable on <Name>: the document reports UndoMode 0`, distinct from the empty-stack message
- [ ] CP6: An open transaction is refused rather than guessed at — verify: on a document with a transaction left open by the GUI, `document_undo` returns `<Name> has an open transaction; undo would commit it and revert the transaction beneath it. Commit or abort it first.`
- [ ] CP7: An undo that leaves the document broken is not `OK` — verify: an undo whose recompute leaves an object in an error state returns `status: "RECOMPUTE_ERROR"`, with the offending object named in `errors`
- [ ] CP8: The undo count is reported — verify: after the successful step-2 undo, `undo_count` is `0`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```
