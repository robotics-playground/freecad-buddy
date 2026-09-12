# TC-05: Mutation Protocol, Rollback Proof & TNP Guard

Validates the uniform mutation bracket in `usecases/transaction.py`: every mutation fingerprints
the document, snapshots it, opens exactly one transaction, runs the four `post_verify` checks, and
then either commits or proves its rollback by re-hashing. The thing under test is not "the mutation
worked" but the honesty of the report: a rollback is claimed only when a re-hash proves it, an
unproven rollback keeps its snapshot and says so, and a TNP audit never reports `CLEAN` for a check
it did not run. Driven over MCP against the live bridge; no automation script covers this surface.

## Prerequisites
- [ ] FreeCAD GUI open and the addon bridge serving `:8765` (verify: `netstat -ano | grep :8765` shows LISTENING)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)
- [ ] Host is NOT in auto-approve posture, so every mutation below carries a real `confirm` (verify: `mcp query_capabilities {}` reports `auto_approve: false`)
- [ ] Temp directory writable and free of stale snapshots (verify: `ls "$TEMP" | grep FCB_TMP_snap_` returns nothing)

---

### TC-05-01: Successful mutation reports the full bracket

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (mutation transaction protocol), `mcp-tools-design.md` §1.4 (mutation block)

**Preconditions**:
- [ ] A document with a body and a fully-constrained 20x20 mm rectangular sketch on XY (verify: `mcp query_sketch_info { doc: <handle>, sketch: "Sketch" }` returns `fully_constrained: true`, `dof: 0`)

**Steps**:
1. Record the pre-mutation state:
   ```
   mcp query_mass_properties { doc: <handle>, object: "Body" }
   ```
2. Preview then apply a 30 mm pad:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>" } }
   ```

**Checkpoints**:
- [ ] CP1: Envelope is `OK` — verify: `feature_pad` returns `status: "OK"` and `detail: null`
- [ ] CP2: Both fingerprints present and different — verify: `structured_content.mutation.fingerprint_before.digest` and `fingerprint_after.digest` are both 64-hex strings and are not equal
- [ ] CP3: post_verify passed with no explanation — verify: `mutation.post_verify.passed` is `true` and `mutation.post_verify.explanation` is `null`
- [ ] CP4: Not rolled back, no proof path taken — verify: `mutation.rolled_back` is `false` and `mutation.rollback_proven` is `null`
- [ ] CP5: Transaction id reported — verify: `mutation.transaction_id` equals `"0"` and `mutation.schema` equals `"fcb.mutation/1"`
- [ ] CP6: Summary names the commit — verify: envelope `text` starts with `Mutation committed; fingerprint ` and carries the first 12 chars of `fingerprint_after.digest`
- [ ] CP7: Geometry matches the request — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0` (20 x 20 x 30 mm)

**Cleanup**:
```bash
# close without saving
mcp document_close { doc: <handle> }
```

---

### TC-05-02: Snapshot created during the bracket, deleted on commit

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (snapshot lifecycle), `mcp-tools-design.md` §1.4 (`snapshot_path`)

**Preconditions**:
- [ ] No stale reserved-prefix snapshot directories (verify: `ls -d "$TEMP"/FCB_TMP_snap_* 2>/dev/null` returns nothing)
- [ ] Same body + sketch document as TC-05-01

**Steps**:
1. Start a watcher that samples the temp directory while a mutation runs:
   ```bash
   while true; do ls -d "$TEMP"/FCB_TMP_snap_* 2>/dev/null >> /tmp/snapwatch.log; sleep 0.2; done &
   ```
2. Run the previewed `feature_pad` from TC-05-01.
3. Stop the watcher:
   ```bash
   kill %1
   ```

**Checkpoints**:
- [ ] CP1: A snapshot directory existed mid-operation — verify: `grep -c FCB_TMP_snap_ /tmp/snapwatch.log` returns a count of at least 1
- [ ] CP2: The snapshot file was the document itself — verify: the logged directory contained `<DocumentName>.FCStd` while the bracket was open
- [ ] CP3: Snapshot gone after commit — verify: `ls -d "$TEMP"/FCB_TMP_snap_* 2>/dev/null` returns nothing
- [ ] CP4: Envelope names no snapshot — verify: `mutation.snapshot_path` is `null` on the `OK` envelope
- [ ] CP5: No orphan `.FCBak` sibling left behind — verify: `ls "$TEMP"/*.FCBak 2>/dev/null` returns nothing

**Cleanup**:
```bash
rm -f /tmp/snapwatch.log
rm -rf "$TEMP"/FCB_TMP_snap_*
```

---

### TC-05-03: post_verify runs its four checks in order

**Priority**: Critical
**Design Ref**: `verification-design.md` §2 (post-verify checklist)

**Preconditions**:
- [ ] A body holding an UNDER-constrained sketch (one rectangle, no dimensional constraints) (verify: `mcp query_sketch_info { doc: <handle>, sketch: "Sketch" }` returns `dof` greater than 0)

**Steps**:
1. Preview and apply a pad on the under-constrained sketch:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 10, unit: "mm" } } } }
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 10, unit: "mm" }, confirm: { preview_id: "<token>" } }
   ```
2. Record which check reported the failure.

**Checkpoints**:
- [ ] CP1: Check 1 (recompute) passed first — verify: `mutation.post_verify.recompute_clean` is `true`, proving the sketch check was reached rather than short-circuited at step 1
- [ ] CP2: Check 2 (shape validity) passed — verify: `mutation.post_verify.is_valid` is `true`
- [ ] CP3: Check 3 (sketch constraint) is the one that failed — verify: `mutation.post_verify.fully_constrained` is `false` and `explanation` starts with `verify_sketch failed on Sketch (dof=`
- [ ] CP4: Check 4 (TNP) did not run — verify: `mutation.post_verify.tnp_audit.findings` is `[]`, which is the short-circuit block, not a graded audit
- [ ] CP5: Status maps to the failing check, not to recompute — verify: envelope `status` is `SPEC_FAILED` (a `RECOMPUTE_ERROR` would mean check 1 failed)
- [ ] CP6: The mutation did not land — verify: `mcp query_tree_summary { doc: <handle>, depth: 2 }` does not list `Pad`
- [ ] CP7: Ordering is observable as a chain — verify: a repeat run with an INVALID object present instead reports `recompute_clean: false`, `is_valid: false` and an `explanation` starting `recompute left `, proving check 1 short-circuits before check 3 is graded

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-04: `touched` names exactly the changed objects

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.4 (`touched`), `verification-design.md` §1

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch and an existing 30 mm `Pad` (verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists `Body`, `Sketch`, `Pad`)

**Steps**:
1. Capture the object list before:
   ```
   mcp query_tree_summary { doc: <handle>, depth: 3 }
   ```
2. Preview and apply a 2 mm fillet on one edge of the pad:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "geometric", object: "Pad", subelement: "Edge1" }], radius: { value: 2, unit: "mm" } } } }
   mcp feature_fillet { doc: <handle>, body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "geometric", object: "Pad", subelement: "Edge1" }], radius: { value: 2, unit: "mm" }, confirm: { preview_id: "<token>" } }
   ```
3. Capture the object list after.

**Checkpoints**:
- [ ] CP1: `touched` is non-empty — verify: `mutation.touched` contains `"Fillet"`
- [ ] CP2: `touched` holds no object the operation did not change — verify: `"Sketch"` is absent from `mutation.touched`
- [ ] CP3: `touched` matches the tree diff — verify: the set difference between the step-3 and step-1 `query_tree_summary` node names equals the new names in `mutation.touched`
- [ ] CP4: The preview predicted the same set — verify: the `preview_dry_run` `diff.touched` for the same operation equals `mutation.touched` from the apply
- [ ] CP5: post_verify graded the touched object — verify: `mutation.post_verify.is_valid` is `true`, which is `verify_shape` run over the shape-bearing members of `touched`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-05: Failed mutation proves its rollback by re-hashing

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (rollback proof), `mcp-tools-design.md` §1.4 (`rollback_proven`)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad` (verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`)

**Steps**:
1. Record the pre-mutation digest by previewing any operation:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "geometric", object: "Pad", subelement: "Edge1" }], radius: { value: 500, unit: "mm" } } } }
   ```
   Record `diff.fingerprint_before`.
2. Apply the impossible fillet — a 500 mm radius cannot fit a 20 mm edge, so OCCT fails the feature:
   ```
   mcp feature_fillet { doc: <handle>, body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "geometric", object: "Pad", subelement: "Edge1" }], radius: { value: 500, unit: "mm" }, confirm: { preview_id: "<token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The call did not raise — verify: a `ResultEnvelope` was returned, not an MCP `isError` response
- [ ] CP2: Rollback is claimed and proven — verify: `mutation.rolled_back` is `true` and `mutation.rollback_proven` equals `"rolled_back_verified"`
- [ ] CP3: The abort path, not the snapshot path — verify: `mutation.snapshot_path` is `null` (it is populated only for `rolled_back_via_snapshot`)
- [ ] CP4: The fingerprint returned to the pre-mutation value — verify: `mutation.fingerprint_after.digest` equals the `diff.fingerprint_before` recorded in step 1
- [ ] CP5: Status is the failing check's status — verify: envelope `status` is `SPEC_FAILED` or `RECOMPUTE_ERROR`, and `detail.code` equals `mutation.` plus that status lowercased
- [ ] CP6: Summary names the proof path — verify: envelope `text` starts with `Mutation rolled back (rolled_back_verified): `
- [ ] CP7: The document really is unchanged — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` still returns `volume` = `12000.0` and `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Fillet`
- [ ] CP8: Snapshot cleaned up after the proven rollback — verify: `ls -d "$TEMP"/FCB_TMP_snap_* 2>/dev/null` returns nothing

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-06: Escalation to snapshot restore reports `rolled_back_via_snapshot`

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (snapshot escalation, FreeCAD #6031)

**CONDITIONAL**: this path runs only when `abortTransaction` fails to restore the pre-transaction
boundary (FreeCAD issue #6031 class). It cannot be forced from the wire. Run the reproducer search
below; if no reproducer is found on this build, a result of `rolled_back_verified` is a
CONDITIONAL PASS and the scenario is recorded as not-exercised, not as a failure. What must never
be accepted is `rolled_back: true` with `rollback_proven: null`.

**Preconditions**:
- [ ] A body with a `Pad`, a `Fillet` on that pad, and a `Sketch` mapped to a fillet-created face — a topology chain where undo has historically failed to restore the boundary (verify: `mcp query_dependencies { doc: <handle> }` shows the sketch depending on the fillet)

**Steps**:
1. Reproducer search — attempt each of the following failing mutations in turn, recording
   `mutation.rollback_proven` for each:
   ```
   mcp feature_pocket { doc: <handle>, body: "Body", profile: "Sketch001", name: "Pocket", length: { value: 900, unit: "mm" }, confirm: { preview_id: "<token>" } }
   mcp feature_pattern { doc: <handle>, body: "Body", base: "Fillet", name: "Pattern", kind: "linear", occurrences: 200, direction: "X", confirm: { preview_id: "<token>" } }
   mcp feature_set_parameters { doc: <handle>, feature: "Fillet", parameters: { Radius: { value: 400, unit: "mm" } }, confirm: { preview_id: "<token>" } }
   ```
2. Record which, if any, reported `rolled_back_via_snapshot`.

**Checkpoints**:
- [ ] CP1: If any reproducer hit the escalation — verify: `mutation.rollback_proven` equals `"rolled_back_via_snapshot"`
- [ ] CP2: The snapshot path is named on the escalated block — verify: `mutation.snapshot_path` is a non-null path under a `FCB_TMP_snap_` directory
- [ ] CP3: Rollback is still claimed as proven — verify: `mutation.rolled_back` is `true`, because the re-hash after the restore matched
- [ ] CP4: The fingerprint returned to the pre-mutation value — verify: `mutation.fingerprint_after.digest` equals the preview's `diff.fingerprint_before`
- [ ] CP5: The reopened document is usable — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` returns `OK` on the same handle, because the restore rebinds the handle to the reopened document
- [ ] CP6: Label and save target survived the restore — verify: `mcp document_list {}` shows the same `label` as before the mutation
- [ ] CP7: CONDITIONAL — if every reproducer returned `rolled_back_verified`, record the scenario as not-exercised. Verify: no run produced `rolled_back: true` with `rollback_proven: null`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
rm -rf "$TEMP"/FCB_TMP_snap_*
```

---

### TC-05-07: An unproven rollback keeps its snapshot and never claims restoration

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (R6: snapshot deleted only after commit or proven rollback)

**CONDITIONAL**: reaching `RollbackNotProven` needs both the abort and the snapshot restore to
miss the pre-mutation fingerprint. Force it by making the snapshot restore land on different bytes:
run the failing mutation while the snapshot file on disk is replaced with a copy of a DIFFERENT
document mid-bracket. If the timing window cannot be hit, mark not-exercised — but CP6 below must
be checked in every run of the whole suite, because it is a claim-honesty property.

**Preconditions**:
- [ ] A document known to take the snapshot-restore path, or the file-swap harness below is in place
- [ ] `benchmarks/g0/golden-models/sphere-r10.FCStd` present as the swap payload (verify: `ls benchmarks/g0/golden-models/sphere-r10.FCStd`)

**Steps**:
1. Arm a watcher that overwrites the snapshot the moment it appears:
   ```bash
   while true; do
     f=$(ls "$TEMP"/FCB_TMP_snap_*/*.FCStd 2>/dev/null | head -1)
     if [ -n "$f" ]; then cp benchmarks/g0/golden-models/sphere-r10.FCStd "$f"; break; fi
   done &
   ```
2. Run a mutation that fails post_verify AND misses the abort re-hash (the TC-05-06 reproducer set).
3. Stop the watcher and inspect the envelope.

**Checkpoints**:
- [ ] CP1: Rollback is NOT claimed — verify: `mutation.rolled_back` is `false`
- [ ] CP2: No proof path is claimed — verify: `mutation.rollback_proven` is `null`
- [ ] CP3: Status is `SPEC_FAILED` — verify: envelope `status` equals `SPEC_FAILED`
- [ ] CP4: The snapshot is named on the envelope — verify: `mutation.snapshot_path` is a non-null path
- [ ] CP5: The snapshot file is still on disk — verify: `ls "$(mutation.snapshot_path)"` succeeds
- [ ] CP6: The text never claims restoration — verify: envelope `text` is exactly `Mutation failed and its rollback could not be proven: {snapshot_path}.` with the real path substituted, and contains neither `rolled back` nor `restored`
- [ ] CP7: The explanation carries the reason — verify: `mutation.post_verify.explanation` ends with `rollback could not be proven: the snapshot-restored document does not match the pre-mutation fingerprint ` plus the before-digest

**Cleanup**:
```bash
kill %1 2>/dev/null
mcp document_close { doc: <handle> }
rm -rf "$TEMP"/FCB_TMP_snap_*
```

---

### TC-05-08: Undo unavailable is recorded, not misread as the #6031 defect

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (undo stack enablement)

**Preconditions**:
- [ ] A document whose undo stack cannot be enabled — a headless-created document, or one whose `UndoMode` is 0 (verify: `mcp document_undo { doc: <handle> }` is refused with `undo is unavailable on <Name>: the document reports UndoMode 0`)

**Steps**:
1. Run a mutation that will fail post_verify on that document:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "geometric", object: "Pad", subelement: "Edge1" }], radius: { value: 500, unit: "mm" } } } }
   mcp feature_fillet { doc: <handle>, body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "geometric", object: "Pad", subelement: "Edge1" }], radius: { value: 500, unit: "mm" }, confirm: { preview_id: "<token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The unavailability is recorded in the explanation — verify: `mutation.post_verify.explanation` ends with `; undo unavailable on this document`
- [ ] CP2: The restore still happened, via the snapshot — verify: `mutation.rollback_proven` equals `"rolled_back_via_snapshot"`, because `abortTransaction` restores nothing without an undo stack
- [ ] CP3: Rollback is still proven, not assumed — verify: `mutation.rolled_back` is `true` and `mutation.fingerprint_after.digest` equals the preview's `diff.fingerprint_before`
- [ ] CP4: The document is genuinely unchanged — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns the pre-mutation volume
- [ ] CP5: The note is absent on a document WITH undo — verify: repeating the same failing mutation on a GUI-created document produces an `explanation` that does NOT contain `undo unavailable`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-09: A transaction is never left open after any failure path

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (R5: never leave a transaction open)

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad` (verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`)

**Steps**:
1. For each failure path in turn — under-constrained sketch (TC-05-03), impossible fillet
   (TC-05-05), and an operation naming a missing base — run the failing mutation, then run a
   mutation that MUST succeed:
   ```
   mcp feature_fillet { doc: <handle>, body: "Body", base: "Pad", name: "BadFillet", edges: [{ kind: "geometric", object: "Pad", subelement: "Edge1" }], radius: { value: 500, unit: "mm" }, confirm: { preview_id: "<token-a>" } }
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "Pad", name: "GoodFillet", edges: [{ kind: "geometric", object: "Pad", subelement: "Edge1" }], radius: { value: 2, unit: "mm" } } } }
   mcp feature_fillet { doc: <handle>, body: "Body", base: "Pad", name: "GoodFillet", edges: [{ kind: "geometric", object: "Pad", subelement: "Edge1" }], radius: { value: 2, unit: "mm" }, confirm: { preview_id: "<token-b>" } }
   ```

**Checkpoints**:
- [ ] CP1: The follow-up mutation succeeded after every failure path — verify: each `GoodFillet` call returns `status: "OK"`
- [ ] CP2: The follow-up opened its own transaction, not a nested one — verify: its `mutation.transaction_id` equals `"0"`
- [ ] CP3: No transaction is pending after the failure — verify: `mcp document_undo { doc: <handle> }` is NOT refused with `has an open transaction; undo would commit it`
- [ ] CP4: `document_undo` reverts the follow-up, not a leaked bracket — verify: `document_undo` returns `undone` equal to `buddy: <the follow-up label>`
- [ ] CP5: No snapshot leaked across the failure paths — verify: `ls -d "$TEMP"/FCB_TMP_snap_* 2>/dev/null` returns nothing after the successful follow-up

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-10: Commit failure aborts the bracket and deletes the snapshot

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (commit-failure path)

**CONDITIONAL**: `commitTransaction` raising is not reachable from the wire on a healthy build.
Force it in-process with `debug_exec` monkeypatching `Document.commitTransaction` for one call, on
a host started with `FREECAD_BUDDY_ALLOW_EXEC=1`. If `debug_exec` is disabled, mark not-exercised.

**Preconditions**:
- [ ] Host started with `FREECAD_BUDDY_ALLOW_EXEC=1` (verify: `mcp debug_exec { doc: <handle>, code: "1" }` is NOT refused with `debug_exec is disabled (set FREECAD_BUDDY_ALLOW_EXEC=1 to enable)`)
- [ ] A body with a fully-constrained 20x20 mm sketch

**Steps**:
1. Patch the commit to raise once:
   ```
   mcp debug_exec { doc: <handle>, code: "import FreeCAD\n_d = FreeCAD.getDocument('<Name>')\n_orig = type(_d).commitTransaction\ndef _boom(self):\n    type(_d).commitTransaction = _orig\n    raise RuntimeError('injected commit failure')\ntype(_d).commitTransaction = _boom" }
   ```
2. Run a mutation whose post_verify will PASS, so the commit is reached:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The failure is reported, not raised — verify: a `ResultEnvelope` is returned with `status: "SPEC_FAILED"`
- [ ] CP2: The injected cause is named — verify: `mutation.post_verify.explanation` equals `RuntimeError: injected commit failure`
- [ ] CP3: Rollback is claimed — verify: `mutation.rolled_back` is `true`
- [ ] CP4: The snapshot was deleted — verify: `mutation.snapshot_path` is `null` and `ls -d "$TEMP"/FCB_TMP_snap_* 2>/dev/null` returns nothing
- [ ] CP5: No after-fingerprint was taken — verify: `mutation.fingerprint_after` is `null`, while `fingerprint_before` is a full record
- [ ] CP6: The bracket is closed — verify: a subsequent well-formed `feature_pad` returns `status: "OK"` on the same handle

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-11: A committed-but-unhashable mutation keeps its snapshot

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (the commit landed; the snapshot is an operator decision)

**CONDITIONAL**: requires `fingerprint()` to raise AFTER a successful commit. Forced with
`debug_exec` making the shape serializer unavailable for one call. If `debug_exec` is disabled,
mark not-exercised.

**Preconditions**:
- [ ] Host started with `FREECAD_BUDDY_ALLOW_EXEC=1`
- [ ] A body with a fully-constrained 20x20 mm sketch

**Steps**:
1. Patch the post-commit fingerprint to raise once:
   ```
   mcp debug_exec { doc: <handle>, code: "from freecad_buddy.usecases import transaction as _t\n_orig = _t.fingerprint\n_state = {'n': 0}\ndef _fp(d):\n    _state['n'] += 1\n    if _state['n'] == 2:\n        _t.fingerprint = _orig\n        raise RuntimeError('injected serializer failure')\n    return _orig(d)\n_t.fingerprint = _fp" }
   ```
2. Run a mutation whose post_verify passes:
   ```
   mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>" } }
   ```

**Checkpoints**:
- [ ] CP1: Rollback is NOT claimed — verify: `mutation.rolled_back` is `false`, because the commit landed and the document is permanently changed
- [ ] CP2: Status is `SPEC_FAILED` — verify: envelope `status` equals `SPEC_FAILED`
- [ ] CP3: The snapshot is KEPT and named — verify: `mutation.snapshot_path` is non-null and `ls "$(mutation.snapshot_path)"` succeeds
- [ ] CP4: No after-fingerprint is reported — verify: `mutation.fingerprint_after` is `null`
- [ ] CP5: The mutation really committed — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists `Pad` and `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`
- [ ] CP6: The text does not claim a rollback — verify: envelope `text` is the unproven-rollback form `Mutation failed and its rollback could not be proven: {snapshot_path}.`, never `Mutation rolled back`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
rm -rf "$TEMP"/FCB_TMP_snap_*
```

---

### TC-05-12: A setup failure mutates nothing and opens no transaction

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (pre-bracket setup)

**CONDITIONAL**: requires `fingerprint()` or `saveCopy` to raise BEFORE the transaction opens.
Forced with `debug_exec`, or by making the system temp directory unwritable. If neither is
available, mark not-exercised.

**Preconditions**:
- [ ] Host started with `FREECAD_BUDDY_ALLOW_EXEC=1`
- [ ] A body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad` (verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`)

**Steps**:
1. Patch the FIRST fingerprint call to raise:
   ```
   mcp debug_exec { doc: <handle>, code: "from freecad_buddy.usecases import transaction as _t\n_orig = _t.fingerprint\ndef _fp(d):\n    _t.fingerprint = _orig\n    raise RuntimeError('injected setup failure')\n_t.fingerprint = _fp" }
   ```
2. Run any mutation on that document.

**Checkpoints**:
- [ ] CP1: No pre-mutation fingerprint is reported — verify: `mutation.fingerprint_before` is `null`
- [ ] CP2: No after-fingerprint either — verify: `mutation.fingerprint_after` is `null`
- [ ] CP3: Rollback is not claimed — verify: `mutation.rolled_back` is `false` and `mutation.rollback_proven` is `null`
- [ ] CP4: `touched` is empty — verify: `mutation.touched` equals `[]`
- [ ] CP5: No snapshot survives — verify: `mutation.snapshot_path` is `null` and `ls -d "$TEMP"/FCB_TMP_snap_* 2>/dev/null` returns nothing
- [ ] CP6: No transaction was opened — verify: `mcp document_undo { doc: <handle> }` reports `undone` equal to the label of the LAST successful mutation, not `buddy: <the failed label>`
- [ ] CP7: The document is untouched — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` still returns `volume` = `12000.0`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-13: The fingerprint carries a serializer tag and is deterministic

**Priority**: High
**Design Ref**: `verification-design.md` §3 (AD-6 fingerprint), `data-contracts-design.md` §8

**Preconditions**:
- [ ] `benchmarks/g0/golden-models/box-10-20-30.FCStd` present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)

**Steps**:
1. Open the golden box twice, as two independent handles:
   ```
   mcp document_open { path: "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd" }
   ```
   Take a fingerprint from each by previewing a no-effect operation:
   ```
   mcp preview_dry_run { doc: <handle-a>, operation: { tool: "feature_body_create", args: { name: "Probe" } } }
   mcp preview_dry_run { doc: <handle-b>, operation: { tool: "feature_body_create", args: { name: "Probe" } } }
   ```

**Checkpoints**:
- [ ] CP1: The serializer tag is present on a mutation record — verify: a successful mutation's `mutation.fingerprint_before.serializer` is a non-null, non-empty string
- [ ] CP2: The tag is the same on both sides of one bracket — verify: `mutation.fingerprint_before.serializer` equals `mutation.fingerprint_after.serializer`
- [ ] CP3: Identical documents give identical digests — verify: the two `diff.fingerprint_before` values from step 1 are equal
- [ ] CP4: The digest is a SHA-256 — verify: it matches `^[0-9a-f]{64}$`
- [ ] CP5: The record carries per-object entries — verify: `mutation.fingerprint_before.objects` is a list whose members each hold `name`, `brep_sha256` and `massprops`
- [ ] CP6: A real geometry change moves the digest — verify: after a successful `feature_pad`, `fingerprint_after.digest` differs from `fingerprint_before.digest`

**Cleanup**:
```bash
mcp document_close { doc: <handle-a> }
mcp document_close { doc: <handle-b> }
```

---

### TC-05-14: A cross-tag fingerprint comparison raises, never returns "not equal"

**Priority**: High
**Design Ref**: `verification-design.md` §3 (AD-6: comparing across serializer tags is banned)

**CONDITIONAL-SKIP on a single FreeCAD build.** Producing two records with DIFFERENT serializer
tags needs two builds — one exposing `Shape.exportBinary`, one exposing only `exportBrep`. Only
FreeCAD 1.1.1 is installed. Run the degraded form below: assert the tag exists, is carried on both
records, and that a record with a MISSING tag is refused rather than compared. Record the full
two-build comparison as not-exercised.

**Preconditions**:
- [ ] A body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad`
- [ ] A second FreeCAD build with a different serializer, if available (verify: the build exposes the other of `exportBinary` / `exportBrep`)

**Steps**:
1. Degraded form — pass a tagless record to the one wire comparison that accepts a whole record:
   ```
   mcp document_undo { doc: <handle>, expect_fingerprint: { objects: [], digest: "0000000000000000000000000000000000000000000000000000000000000000" } }
   ```
2. Two-build form, if a second build is present — take a fingerprint on build A, then feed it to
   build B as `expect_fingerprint`.

**Checkpoints**:
- [ ] CP1: The tag is carried on every record the wire returns — verify: `mutation.fingerprint_before.serializer` is non-null on a successful mutation
- [ ] CP2: Both records in one bracket carry the same tag — verify: `fingerprint_before.serializer` equals `fingerprint_after.serializer`
- [ ] CP3: A record missing its `objects` list is refused at the boundary — verify: `mcp document_undo { doc: <handle>, expect_fingerprint: { digest: "abc" } }` is refused with `expect_fingerprint record must carry an 'objects' list; got keys ['digest']`
- [ ] CP4: CONDITIONAL two-build — verify: the cross-build comparison RAISES `cannot compare fingerprints: serializer tag missing/mismatch` and never returns a quiet `false`
- [ ] CP5: A quiet "not equal" is never produced for a tag mismatch — verify: in no run does a tag mismatch surface as `matches_pre_op: false` or `rolled_back: false` without an accompanying comparison error

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-15: TNP reports CLEAN on a healthy mutation

**Priority**: Critical
**Design Ref**: `verification-design.md` §3 (AD-7 TNP guard), `mcp-tools-design.md` §1.4 (`tnp_audit`)

**Preconditions**:
- [ ] A body with a 30 mm `Pad` and a 2 mm `Fillet` referencing one pad edge (verify: `mcp query_dependencies { doc: <handle> }` shows `Fillet` depending on `Pad`)
- [ ] This build exposes an element map (verify: `mcp query_capabilities {}` reports the element-map version as non-null)

**Steps**:
1. Preview and apply a harmless parameter change on the pad:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_set_parameters", args: { feature: "Pad", parameters: { Length: { value: 32, unit: "mm" } } } } }
   mcp feature_set_parameters { doc: <handle>, feature: "Pad", parameters: { Length: { value: 32, unit: "mm" } }, confirm: { preview_id: "<token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The mutation committed — verify: envelope `status` is `OK`
- [ ] CP2: The audit ran and is CLEAN — verify: `mutation.post_verify.tnp_audit.status` equals `"CLEAN"`
- [ ] CP3: Every finding is a passing verdict — verify: every member of `tnp_audit.findings` has `verdict` in `["PASS", "RE_BASELINED"]`
- [ ] CP4: The element map version is reported — verify: `tnp_audit.element_map_version` is a non-null string
- [ ] CP5: The audit is not the short-circuit block — verify: `tnp_audit.findings` is NOT empty, proving check 4 actually graded the fillet's reference
- [ ] CP6: The reference survived — verify: `mcp query_mass_properties { doc: <handle>, object: "Fillet" }` returns `OK` and the fillet is still present in `query_tree_summary`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-16: TNP flags REPOINTED when an edge reference re-indexes

**Priority**: Critical
**Design Ref**: `verification-design.md` §3 (AD-7, Layer 1 mapped-name grading)

**Preconditions**:
- [ ] A body with a 30 mm `Pad` and a 2 mm `Fillet` on `Edge1` of that pad (verify: `mcp query_object { doc: <handle>, object: "Fillet" }` shows `Base` naming `Pad` and `Edge1`)
- [ ] This build exposes an element map

**Steps**:
1. Insert geometry that re-indexes the filleted edge — add a chamfer on an adjacent edge of the
   same pad, so the edge numbering downstream of it shifts:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_chamfer", args: { body: "Body", base: "Pad", name: "Chamfer", edges: [{ kind: "geometric", object: "Pad", subelement: "Edge2" }], size: { value: 3, unit: "mm" } } } }
   mcp feature_chamfer { doc: <handle>, body: "Body", base: "Pad", name: "Chamfer", edges: [{ kind: "geometric", object: "Pad", subelement: "Edge2" }], size: { value: 3, unit: "mm" }, confirm: { preview_id: "<token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The audit flagged the reference — verify: `mutation.post_verify.tnp_audit.status` equals `"FLAGGED"`
- [ ] CP2: A REPOINTED finding names the fillet's reference — verify: `tnp_audit.findings` contains an entry with `verdict: "REPOINTED"` and `owner` equal to `"Fillet"`
- [ ] CP3: The finding names its layer — verify: that entry's `layer` is `1` or `2`
- [ ] CP4: post_verify failed on the audit, not earlier — verify: `recompute_clean` is `true`, `is_valid` is `true`, and `explanation` starts with `TNP audit flagged `
- [ ] CP5: The mutation was rolled back — verify: `mutation.rolled_back` is `true` and `mutation.rollback_proven` is `"rolled_back_verified"` or `"rolled_back_via_snapshot"`
- [ ] CP6: The chamfer did not land — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Chamfer`
- [ ] CP7: The preview predicted it — verify: the matching `preview_dry_run` reports `diff.tnp_precheck.status` equal to `"FLAGGED"`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-17: TNP flags BROKEN when a referent vanishes

**Priority**: Critical
**Design Ref**: `verification-design.md` §3 (AD-7, Layer 0 validity sweep and Layer 1 unresolvable element)

**Preconditions**:
- [ ] A body with a 30 mm `Pad` and a 2 mm `Fillet` on `Edge1` of that pad
- [ ] This build exposes an element map

**Steps**:
1. Remove the geometry the fillet's base depends on — shrink the pad's profile sketch so the
   filleted edge no longer exists:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "sketch_remove_geometry", args: { sketch: "Sketch", geometry: [0] } } }
   mcp sketch_remove_geometry { doc: <handle>, sketch: "Sketch", geometry: [0], confirm: { preview_id: "<token>" } }
   ```

**Checkpoints**:
- [ ] CP1: The audit flagged it — verify: `mutation.post_verify.tnp_audit.status` equals `"FLAGGED"`
- [ ] CP2: A BROKEN finding is present — verify: `tnp_audit.findings` contains an entry with `verdict: "BROKEN"`
- [ ] CP3: The finding sits at Layer 0 or Layer 1 — verify: that entry's `layer` is `0` or `1`
- [ ] CP4: The break is attributed to the fillet — verify: the BROKEN entry's `owner` is `"Fillet"`
- [ ] CP5: The mutation was rolled back — verify: `mutation.rolled_back` is `true`
- [ ] CP6: The fillet is intact after the rollback — verify: `mcp query_mass_properties { doc: <handle>, object: "Fillet" }` returns `status: "OK"`
- [ ] CP7: A Layer-0 break is reported even when the failure also fails recompute — verify: if `recompute_clean` is `false`, `tnp_audit.status` is still not `"CLEAN"`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-18: TNP UNSUPPORTED is never reported as CLEAN or PASS

**Priority**: Critical
**Design Ref**: `verification-design.md` §3 (AD-7, capability gate)

**CONDITIONAL-SKIP on FreeCAD 1.1.** The `UNSUPPORTED` path needs
`shim.element_map_available()` to return false, which FreeCAD 1.1.1 does not do — its toponaming
element map is always present. Run the degraded form: assert that `preview_dry_run`'s own
`UNSUPPORTED` block (produced when an op yields no `post_verify`) is never dressed as `CLEAN`, and
that no finding ever carries `PASS` alongside an `UNSUPPORTED` status. Record the build-gated form
as not-exercised.

**Preconditions**:
- [ ] A build reporting no element map, if one is available (verify: `mcp query_capabilities {}` reports the element-map version as `null`)
- [ ] Degraded form: a document where an operation fails before producing a `post_verify` block

**Steps**:
1. Degraded form — preview an operation that is refused by its own use case before the bracket
   runs, so no `post_verify` block exists:
   ```
   mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "NoSuchFeature", name: "Fillet", edges: [{ kind: "geometric", object: "NoSuchFeature", subelement: "Edge1" }], radius: { value: 2, unit: "mm" } } } }
   ```
2. Build-gated form, if a no-element-map build exists — run any successful mutation on it.

**Checkpoints**:
- [ ] CP1: An un-run audit is UNSUPPORTED, not CLEAN — verify: the preview's `diff.tnp_precheck.status` equals `"UNSUPPORTED"`
- [ ] CP2: UNSUPPORTED carries no passing findings — verify: `diff.tnp_precheck.findings` is `[]`, never a list holding `PASS`
- [ ] CP3: The element map version is still reported — verify: `diff.tnp_precheck.element_map_version` is present
- [ ] CP4: CONDITIONAL build-gated — verify: on a no-element-map build, `mutation.post_verify.tnp_audit.status` equals `"UNSUPPORTED"` and every finding carries `verdict: "UNSUPPORTED"` with `layer: 0`
- [ ] CP5: CONDITIONAL build-gated — verify: on that build no finding carries `verdict: "PASS"`, because an ungraded reference is not a passing one
- [ ] CP6: The distinction is never collapsed — verify: across every scenario in this file, no envelope reports `tnp_audit.status: "CLEAN"` together with an `element_map_version` of `null`

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```
