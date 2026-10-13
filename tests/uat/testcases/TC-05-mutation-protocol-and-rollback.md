# TC-05: Mutation Protocol, Rollback Proof & TNP Guard

Validates the uniform mutation bracket in `usecases/transaction.py`: every mutation fingerprints
the document, snapshots it, opens exactly one transaction, runs the four `post_verify` checks, and
then either commits or proves its rollback by re-hashing. The thing under test is not "the mutation
worked" but the honesty of the report: a rollback is claimed only when a re-hash proves it, an
unproven rollback keeps its snapshot and says so, and a TNP audit never reports `CLEAN` for a check
it did not run. Driven over MCP against the live bridge; no automation script covers this surface.

Every envelope field this file asserts on — `status`, `mutation.*`, every fingerprint digest — is
produced by the code under test. Those assertions are claims, not evidence. The result of each
scenario is the closing `cua-driver` pixel capture, `Read` and judged by the agent. This matters
most for the rollback scenarios: an envelope reporting `rolled_back: true` with a restored
fingerprint, over a window still showing the half-applied feature, passes every numeric assertion
in this file and fails the user completely.

**Host**: GUI through the H2 proxy for every scenario. TC-05-02, TC-05-03, TC-05-07, TC-05-08,
TC-05-10, TC-05-11, TC-05-12 and TC-05-18 use `script_exec` to build a fixture the typed tools
refuse, or to patch a bridge function for one call so a fault path becomes reachable. `script_exec`
is on by default. It is off when `FREECAD_BUDDY_SCRIPT_EXEC=0` is set or the **Allow script_exec**
preference (`ScriptExec`) is cleared, and when `FREECAD_BUDDY_UNATTENDED=1` is set without
`FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`. When it is off, those scenarios are not-exercised.
`script_exec` opens no transaction, so `document_undo` never reverts what it did: each patch restores
itself after one call, and each Cleanup restores what the scenario changed.

## Preconditions

- [ ] FreeCAD 1.1.x installed (verify: `ls "$FREECAD_EXE"`); the build under test is the live version: `query_capabilities.freecad_version`, read once at the start of the run and written `<live version>` below
- [ ] FreeCAD GUI open and the addon bridge serving `:8765` (verify: `netstat -ano | grep :8765` shows LISTENING)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)
- [ ] Golden and fault `.FCStd` files have no `GuiDocument.xml` and open with every object hidden. After each `document_open` of such a file, and before any fit or render of it, run **Show All**: `cua-driver call invoke_menu { pid, window_id, path: ["View","Visibility","Show All Objects"] }`. A fit before it returns `SPEC_FAILED view_fit.nothing_to_frame`.
- [ ] `script_exec` is on, as it is by default (verify: `tools/list` includes `script_exec`; the new `addon.log` `operator settings:` line shows `FREECAD_BUDDY_SCRIPT_EXEC='1'`)
- [ ] Host is NOT in auto-approve posture, so every mutation below carries a real `confirm`: FreeCAD was started with `FREECAD_BUDDY_AUTO_APPROVE=0`, or with the **Auto-approve mutations** preference off and the variable unset, because auto-approve is on by default (verify: the new `addon.log` lines from that launch do not contain `SECURITY: mutation auto-approve ENABLED`)
- [ ] The session temp folder holds no stale snapshot. Every bridge temp file lives in `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/` (GUI workdir `%APPDATA%\FreeCAD\v1-1\freecad-buddy\workdir`), never in `$TEMP`. The agent shell can get "Access is denied" there, so list it in-process. This is the **snapshot check** used below: `mcp script_exec { doc: <handle>, code: "import os\nfrom freecad_buddy.usecases.documents import temp_dir\nroot = temp_dir()\nresult = sorted(n for n in os.listdir(root) if n.startswith('FCB_TMP_snap_'))" }` returns `value_repr` `[]` (verify: run it once on any open document)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` returns a `QOpenGLWidget`)
- [ ] `cua-driver` can reach the **View → Fit All** menu item, the non-MCP framing path (verify: the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view) succeeds)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)

---

### TC-05-01: Successful mutation reports the full bracket

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (mutation transaction protocol), `mcp-tools-design.md` §1.4 (mutation block)

**Given** a document with a body and a fully-constrained 20x20 mm rectangular sketch on XY — verify: `mcp verify_sketch { doc: <handle>, sketch: "Sketch" }` returns `OK` with `subject.fully_constrained: true` and `subject.dof: 0`  

**When** the pre-mutation state is recorded  
```
mcp query_mass_properties { doc: <handle>, object: "Body" }
```
**And** a 30 mm pad is previewed then applied  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>" } }
```

**Then** envelope is `OK` — verify: `feature_pad` returns `status: "OK"` and `detail: null`  
**And** both fingerprints present and different — verify: `structured_content.mutation.fingerprint_before.digest` and `fingerprint_after.digest` are both 64-hex strings and are not equal  
**And** post_verify passed with no explanation — verify: `mutation.post_verify.passed` is `true` and `mutation.post_verify.explanation` is `null`  
**And** not rolled back, no proof path taken — verify: `mutation.rolled_back` is `false` and `mutation.rollback_proven` is `null`  
**And** the wire block is the compact one — verify: `mutation.schema` equals `"fcb.mutation/2"` and the block has no `transaction_id` key  
**And** summary names the commit — verify: envelope `text` starts with `Mutation committed; fingerprint ` and carries the first 12 chars of `fingerprint_after.digest`  
**And** geometry matches the request — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0` (20 x 20 x 30 mm)  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window shows a solid box that was not there before — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-01-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a shaded three-dimensional solid, about one and a half times as tall as it is wide (30 mm on 20 mm), whole and with no edge cut off by the viewport border, and no error dialog or warning popup raised over it. If you see only a flat sketch outline, or an empty viewport, that is the finding. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
# close without saving
mcp document_close { doc: <handle> }
```

---

### TC-05-02: Snapshot created during the bracket, deleted on commit

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (snapshot lifecycle), `mcp-tools-design.md` §1.4 (`snapshot_path`)

**Given** no stale reserved-prefix snapshot directories — verify: the **snapshot check** (Preconditions) returns `[]`  
**And** the same body + sketch document as TC-05-01 is open — verify: `mcp verify_sketch { doc: <handle>, sketch: "Sketch" }` returns `OK` with `subject.fully_constrained: true` and `subject.dof: 0`  

**When** the `feature_pad` from TC-05-01 is previewed, so the preview's own bracket runs before the spy is armed  
**And** a one-shot spy is armed in-process on the function that deletes the snapshot. The bracket runs on the GUI thread and a shell watcher cannot list the session folder reliably, so the spy records the snapshot folder and its files at the moment of deletion, then restores the original function  
```
mcp script_exec { doc: <handle>, code: "import os\nfrom freecad_buddy.usecases import transaction as _t\n_orig = _t._delete_snapshot\n_t._fcb_seen = []\ndef _spy(path):\n    _t._delete_snapshot = _orig\n    _t._fcb_seen.append((path, sorted(os.listdir(os.path.dirname(path)))))\n    return _orig(path)\n_t._delete_snapshot = _spy\nresult = 'armed'" }
```
**And** the previewed `feature_pad` is applied with its `confirm`  
**And** the spy's record is read  
```
mcp script_exec { doc: <handle>, code: "import os\nfrom freecad_buddy.usecases import transaction as _t\nresult = [(p, files, os.path.exists(os.path.dirname(p))) for p, files in _t._fcb_seen]" }
```

**Then** a snapshot directory existed mid-operation — verify: the record holds exactly one entry, and its folder is an `FCB_TMP_snap_*` folder inside the session temp folder `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/`, not in `$TEMP`  
**And** the snapshot file was the document itself — verify: the entry's file list is exactly `['<DocumentName>.FCStd']`  
**And** snapshot gone after commit — verify: the entry's third value is `False`, and the **snapshot check** (Preconditions) returns `[]`  
**And** envelope names no snapshot — verify: the `OK` envelope's mutation block has no `snapshot_path` key  
**And** no orphan `.FCBak` sibling left behind — verify: `mcp script_exec { doc: <handle>, code: "import os\nfrom freecad_buddy.usecases.documents import temp_dir\nresult = [f for _, _, fs in os.walk(temp_dir()) for f in fs if f.endswith('.FCBak')]" }` returns `value_repr` `[]`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window shows a solid box, so the deleted snapshot accompanied a real commit — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-02-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a shaded solid prism, whole, not clipped at any viewport edge, with no error dialog. An empty viewport here means the snapshot was deleted after a mutation that never reached the user, which the filesystem checks above cannot detect. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp script_exec { doc: <handle>, code: "from freecad_buddy.usecases import transaction as _t\nresult = _t._delete_snapshot.__name__" }
```
`value_repr` is `'_delete_snapshot'`, so the spy is gone.
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-03: post_verify runs its four checks in order

**Priority**: Critical
**Design Ref**: `verification-design.md` §2 (post-verify checklist)

**Given** a body holding an UNDER-constrained sketch (one rectangle, no dimensional constraints). The typed sketch tools roll back any sketch they leave under-constrained (AD-8), so the fixture is built with `script_exec` on a scratch document from `mcp document_create { label: "tc-05-03" }` — verify: the call below returns `OK`, and `mcp verify_sketch { doc: <handle>, sketch: "Sketch" }` returns `subject.fully_constrained: false` and `subject.dof: 4`  
```
mcp script_exec { doc: <handle>, code: "import Part, Sketcher\nfrom FreeCAD import Vector as V\nbody = doc.addObject('PartDesign::Body', 'Body')\nxy = [f for f in body.Origin.OriginFeatures if f.Role == 'XY_Plane'][0]\nsk = body.newObject('Sketcher::SketchObject', 'Sketch')\nsk.AttachmentSupport = [(xy, '')]\nsk.MapMode = 'FlatFace'\npts = [V(0, 0, 0), V(20, 0, 0), V(20, 20, 0), V(0, 20, 0)]\nfor i in range(4):\n    sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))\nfor i in range(4):\n    sk.addConstraint(Sketcher.Constraint('Coincident', i, 2, (i + 1) % 4, 1))\nfor i, kind in enumerate(['Horizontal', 'Vertical', 'Horizontal', 'Vertical']):\n    sk.addConstraint(Sketcher.Constraint(kind, i))\ndoc.recompute()\nresult = sk.solve()" }
```
**And** the pre-mutation window is framed and captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view); then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-03-before.png"}' | & cua-driver call get_window_state`  

**When** a pad is previewed and applied on the under-constrained sketch  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 10, unit: "mm" } } } }
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 10, unit: "mm" }, confirm: { preview_id: "<token>" } }
```
**And** the check that reported the failure is recorded  

**Then** check 1 (recompute) passed first — verify: `mutation.post_verify.recompute_clean` is `true`, proving the sketch check was reached rather than short-circuited at step 1  
**And** check 2 (shape validity) passed — verify: `mutation.post_verify.is_valid` is `true`  
**And** check 3 (sketch constraint) is the one that failed — verify: `mutation.post_verify.fully_constrained` is `false` and `explanation` starts with `verify_sketch failed on Sketch (dof=4)`. The pad touches only `Pad` and `Body`; post-verify also grades every sketch a touched feature consumes  
**And** check 4 (TNP) still ran on the short-circuit — verify: `mutation.post_verify.tnp_audit.status` is not `"UNSUPPORTED"` and `tnp_audit.counts` is present. The audit runs on every path where the operation returned; only a path where it never ran reports `UNSUPPORTED`  
**And** status maps to the failing check, not to recompute — verify: envelope `status` is `SPEC_FAILED` (a `RECOMPUTE_ERROR` would mean check 1 failed)  
**And** the mutation did not land — verify: `mutation.rolled_back` is `true` and `mcp query_tree_summary { doc: <handle>, depth: 2 }` does not list `Pad`  
**And** ordering is observable as a chain — verify: a repeat run with an INVALID object present instead reports `recompute_clean: false`, `is_valid: false` and an `explanation` starting `recompute left `, proving check 1 short-circuits before check 3 is graded  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window looks exactly as it did before the failed mutation — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-03-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what each one shows. The after image must show the same flat sketch outline as the before image, with no shaded solid anywhere in the viewport, no partially extruded body, no error marker on a tree item, and no dialog. Any pixel difference beyond cursor position is the finding. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; do not reason from `Pad` being absent in the tree to what the picture must contain.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-04: `touched` names exactly the changed objects

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §1.4 (`touched`), `verification-design.md` §1

**Given** a body with a fully-constrained 20x20 mm sketch and an existing 30 mm `Pad` — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists `Body`, `Sketch`, `Pad`  

**When** the object list before is captured  
```
mcp query_tree_summary { doc: <handle>, depth: 3 }
```
**And** a 2 mm fillet on one edge of the pad is previewed and applied  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 2, unit: "mm" } } } }
mcp feature_fillet { doc: <handle>, body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 2, unit: "mm" }, confirm: { preview_id: "<token>" } }
```
**And** the object list after is captured  

**Then** `touched` is non-empty — verify: `mutation.touched` contains `"Fillet"`  
**And** `touched` holds no object the operation did not change — verify: `"Sketch"` is absent from `mutation.touched`  
**And** `touched` matches the tree diff — verify: the set difference between the after and before `query_tree_summary` node names equals the new names in `mutation.touched`  
**And** the preview predicted the same set — verify: the `preview_dry_run` `diff.touched` for the same operation equals `mutation.touched` from the apply  
**And** post_verify graded the touched object — verify: `mutation.post_verify.is_valid` is `true`, which is `verify_shape` run over the shape-bearing members of `touched`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window shows one rounded edge on the solid — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-04-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a shaded solid prism, whole and unclipped, with exactly one of its visible edges curved into a narrow rounded strip while the other visible edges stay sharp corners, and no error dialog. If every edge is still sharp, or more than one is rounded, that is the finding. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-05: Failed mutation proves its rollback by re-hashing

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (rollback proof), `mcp-tools-design.md` §1.4 (`rollback_proven`)

**Given** a body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad` — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`  
**And** the pre-mutation window is framed and captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view); then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-05-before.png"}' | & cua-driver call get_window_state`  

**When** the pre-mutation digest is recorded by previewing any operation  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 500, unit: "mm" } } } }
```
Record `diff.fingerprint_before`.
**And** the impossible fillet is applied — a 500 mm radius cannot fit a 20 mm edge, so OCCT fails the feature  
```
mcp feature_fillet { doc: <handle>, body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 500, unit: "mm" }, confirm: { preview_id: "<token>" } }
```

**Then** the call returned an envelope, not a transport error — verify: the MCP result carries the `ResultEnvelope` in `structuredContent` and has `isError: true`, as every non-`OK` result has  
**And** rollback is claimed and proven — verify: `mutation.rolled_back` is `true` and `mutation.rollback_proven` equals `"rolled_back_verified"`  
**And** the abort path, not the snapshot path — verify: the mutation block has no `snapshot_path` key (it is present only for `rolled_back_via_snapshot`)  
**And** the geometry returned to the pre-mutation value — verify: `mutation.changed` is `[]`; `mutation.fingerprint_after.digest` equals the preview's `diff.fingerprint_before`, or differs only because the abort re-wrote B-rep bytes with equal mass properties (the proof accepts `massprops_equal`, AD-5)  
**And** status is the failing check's status — verify: envelope `status` is `SPEC_FAILED` or `RECOMPUTE_ERROR`, and `detail.code` equals `mutation.` plus that status lowercased  
**And** summary names the proof path — verify: envelope `text` starts with `Mutation rolled back (rolled_back_verified): `  
**And** the document really is unchanged — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` still returns `volume` = `12000.0` and `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Fillet`  
**And** snapshot cleaned up after the proven rollback — verify: the **snapshot check** (Preconditions) returns `[]`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window looks exactly as it did before the failed mutation — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-05-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what each one shows. The after image must show the same solid prism with the same sharp edges as the before image: no rounded or bulged edge, no gouged or deformed face, no fragment of a half-applied fillet, no error marker on a tree item, no dialog. This image pair is the result of this scenario. A restored fingerprint reported over a window still showing a half-applied feature is the exact defect the numbers cannot catch, so judge the pixels alone — no MCP status, digest, or render may stand in for looking at the two images.  

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

**Given** a body with a `Pad`, a `Fillet` on that pad, a `Sketch001` mapped to a fillet-created face, and a 900 mm `Pocket` from `Sketch001` — a topology chain where undo has historically failed to restore the boundary. The 900 mm pocket cuts through the whole solid and commits `OK`, so it is part of the chain, not a reproducer — verify: `mcp query_dependencies { doc: <handle> }` shows `Sketch001` depending on `Fillet` and `Pocket` on `Sketch001`  
**And** the pre-mutation window is framed and captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view); then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-06-before.png"}' | & cua-driver call get_window_state`  

**When** the reproducer search runs — each of the following failing mutations is previewed, then attempted in turn, recording `mutation.rollback_proven` for each  
```
mcp feature_pattern { doc: <handle>, body: "Body", name: "Pattern", kind: "linear", originals: ["Pocket"], direction: { kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }, occurrences: 200, confirm: { preview_id: "<token>" } }
mcp feature_set_parameters { doc: <handle>, feature: "Fillet", parameters: { Radius: { value: 400, unit: "mm" } }, confirm: { preview_id: "<token>" } }
```
**And** which, if any, reported `rolled_back_via_snapshot` is recorded  

**Then** if any reproducer hit the escalation — verify: `mutation.rollback_proven` equals `"rolled_back_via_snapshot"`  
**And** the snapshot path is named on the escalated block — verify: `mutation.snapshot_path` is a non-null path under a `FCB_TMP_snap_` directory inside the session temp folder  
**And** rollback is still claimed as proven — verify: `mutation.rolled_back` is `true`, because the re-hash after the restore matched  
**And** the geometry returned to the pre-mutation value — verify: `mutation.changed` is `[]`. On this path the proof compares mass properties, not digests: reopening a file re-serializes every shape, so `fingerprint_after.digest` never equals the pre-mutation digest after a snapshot restore (Story 10.3 D4)  
**And** the reopened document is usable — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` returns `OK` on the same handle, because the restore rebinds the handle to the reopened document  
**And** label and save target survived the restore — verify: `mcp document_list {}` shows the same `label` as before the mutation  
**And** the snapshot was deleted after the proven restore — verify: the **snapshot check** (Preconditions) returns `[]`  
**And** CONDITIONAL — if every reproducer returned `rolled_back_verified`, record the scenario as not-exercised. Verify: no run produced `rolled_back: true` with `rollback_proven: null`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window shows the pre-mutation document, not an empty or replaced one — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-06-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what each one shows. The after image must show the same solid with the same fillet at the same size as the before image: the same 900 mm pocket, no 200-instance pattern array, no oversized fillet, no empty viewport, no error marker, no dialog. A snapshot restore reopens the document behind the human's back, so an empty viewport or a stale window here is a real defect that the rebound handle and matching digest both hide. The judgement is on the pixels alone — no MCP status, digest, or render may stand in for looking at the two images.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-07: An unproven rollback keeps its snapshot and never claims restoration

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (R6: snapshot deleted only after commit or proven rollback)

**CONDITIONAL**: reaching `RollbackNotProven` needs both the abort and the snapshot restore to
miss the pre-mutation fingerprint. Force both in-process with `script_exec`: turn undo off so the
abort restores nothing (the **UndoMode 0 recipe** of TC-05-08), and wrap the restore function so it
copies a DIFFERENT document over the snapshot file just before it reopens it. A shell watcher on
the session temp folder is not used: the shell can be denied access there, and the timing window is
not reliable. If `script_exec` is off, mark not-exercised — but the never-claims-restoration `Then`
below must be checked in every run of the whole suite, because it is a claim-honesty property.

**Given** a body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad` is open — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`  
**And** `benchmarks/g0/golden-models/sphere-r10.FCStd` present as the swap payload — verify: `ls benchmarks/g0/golden-models/sphere-r10.FCStd`  
**And** the pre-mutation window is framed and captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view); then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-07-before.png"}' | & cua-driver call get_window_state`  

**When** the impossible fillet of TC-05-05 (radius 500 mm on `Edge1`) is previewed  
**And** undo is turned off and the restore is wrapped, in one call. `shim.enable_undo` is patched to report `False` so the bracket cannot turn undo back on; the wrapper restores itself after one call  
```
mcp script_exec { doc: <handle>, code: "import shutil\nfrom freecad_buddy.usecases import shim, transaction as _t\nshim._fcb_enable_undo = shim.enable_undo\nshim.enable_undo = lambda d: False\ndoc.UndoMode = 0\n_orig = _t._restore_from_snapshot\ndef _swap(document, snapshot_path):\n    _t._restore_from_snapshot = _orig\n    shutil.copyfile('<PROJECT_ROOT>/benchmarks/g0/golden-models/sphere-r10.FCStd', snapshot_path)\n    return _orig(document, snapshot_path)\n_t._restore_from_snapshot = _swap\nresult = doc.UndoMode" }
```
**And** the previewed fillet is applied with its `confirm`, and the envelope is inspected  

**Then** rollback is NOT claimed — verify: `mutation.rolled_back` is `false`  
**And** no proof path is claimed — verify: `mutation.rollback_proven` is `null`  
**And** status is `SPEC_FAILED` — verify: envelope `status` equals `SPEC_FAILED`  
**And** the snapshot is named on the envelope — verify: `mutation.snapshot_path` is a non-null path  
**And** the snapshot file is still on disk — verify: `mcp script_exec { doc: <handle>, code: "import os\nresult = os.path.exists(r'<snapshot_path>')" }` returns `value_repr` `True` (the agent shell can be denied access to the session temp folder)  
**And** the text never claims restoration — verify: envelope `text` is exactly `Mutation failed and its rollback could not be proven: {snapshot_path}.` with the real path substituted, and contains neither `rolled back` nor `restored`  
**And** the explanation carries the reason — verify: `mutation.post_verify.explanation` ends with `rollback could not be proven: the snapshot-restored document does not match the pre-mutation fingerprint ` plus the before-digest  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; the swapped sphere file has no `GuiDocument.xml`, so if the fit returns `view_fit.nothing_to_frame`, run Show All first and record that you did; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* what the human is left looking at is recorded, and it is not a restored document — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-07-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and write down what each one actually shows — a prism, a sphere, an empty viewport, a dialog. Either a changed or an unchanged after image is acceptable in this scenario, because the swap makes the outcome indeterminate; what must hold is that the envelope claimed no restoration. A window plainly showing the swapped sphere alongside a `rolled_back: true` claim is the defect. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the two images, and the recorded description must be of the picture, not of what the envelope says the document is.  

**Cleanup**:
Restore undo, remove the kept snapshot folder, then close without saving:
```
mcp script_exec { doc: <handle>, code: "import os, shutil\nfrom freecad_buddy.usecases import shim\nshim.enable_undo = shim._fcb_enable_undo\ndoc.UndoMode = 1\nshutil.rmtree(os.path.dirname(r'<snapshot_path>'))\nresult = shim.enable_undo(doc)" }
mcp document_close { doc: <handle> }
```
`value_repr` is `True`. Then the **snapshot check** (Preconditions) returns `[]`.

---

### TC-05-08: Undo unavailable is recorded, not misread as the #6031 defect

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (undo stack enablement)

**Given** a body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad` is open — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`  
**And** the document's undo stack is turned off with the **UndoMode 0 recipe**. A GUI document always has undo, and the bracket turns undo on itself (`shim.enable_undo`), so the recipe sets `UndoMode` to 0 and patches `shim.enable_undo` to report `False` until Cleanup restores it  
```
mcp script_exec { doc: <handle>, code: "from freecad_buddy.usecases import shim\nshim._fcb_enable_undo = shim.enable_undo\nshim.enable_undo = lambda d: False\ndoc.UndoMode = 0\nresult = doc.UndoMode" }
```
— verify: `value_repr` is `0`, and `mcp document_undo { doc: <handle> }` is refused with `undo is unavailable on <Name>: the document reports UndoMode 0`
**And** the pre-mutation window is framed and captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view); then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-08-before.png"}' | & cua-driver call get_window_state`  

**When** a mutation that will fail post_verify is run on that document  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 500, unit: "mm" } } } }
mcp feature_fillet { doc: <handle>, body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 500, unit: "mm" }, confirm: { preview_id: "<token>" } }
```

**Then** the unavailability is recorded in the explanation — verify: `mutation.post_verify.explanation` ends with `; undo unavailable on this document`  
**And** the restore still happened, via the snapshot — verify: `mutation.rollback_proven` equals `"rolled_back_via_snapshot"`, because `abortTransaction` restores nothing without an undo stack  
**And** rollback is still proven, not assumed — verify: `mutation.rolled_back` is `true` and `mutation.changed` is `[]`. Digests are not compared: a reopened file never reproduces the pre-mutation digest, so the snapshot path proves the rollback on mass properties (Story 10.3 D4)  
**And** the failed feature is gone — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` does not list `Fillet`  
**And** the document is genuinely unchanged — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns the pre-mutation volume  
**And** the note is absent on a document WITH undo — verify: after the Cleanup recipe below restores undo, repeating the same failing mutation (fresh preview, then apply) produces an `explanation` that does NOT contain `undo unavailable`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window looks exactly as it did before the failed mutation — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-08-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what each one shows. The after image must show the same solid with the same sharp edges as the before image: no rounded or deformed edge, no missing face, no empty viewport where the reopened document should be, no error marker, no dialog. The snapshot restore path reopens the document, so this pair is the only evidence that the human was left with a working window rather than a blank one. The judgement is on the pixels alone — no MCP status, digest, or render may stand in for looking at the two images.  

**Cleanup**: restore undo before the WITH-undo repeat above, then close without saving
```
mcp script_exec { doc: <handle>, code: "from freecad_buddy.usecases import shim\nshim.enable_undo = shim._fcb_enable_undo\ndoc.UndoMode = 1\nresult = shim.enable_undo(doc)" }
mcp document_close { doc: <handle> }
```
`value_repr` is `True`.

---

### TC-05-09: A transaction is never left open after any failure path

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (R5: never leave a transaction open)

**Given** a body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad` — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`  

**When** for each failure path in turn — under-constrained sketch (TC-05-03), impossible fillet (TC-05-05), and an operation naming a missing base — the failing mutation is run, then a mutation that MUST succeed  
```
mcp feature_fillet { doc: <handle>, body: "Body", base: "Pad", name: "BadFillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 500, unit: "mm" }, confirm: { preview_id: "<token-a>" } }
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "Pad", name: "GoodFillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 2, unit: "mm" } } } }
mcp feature_fillet { doc: <handle>, body: "Body", base: "Pad", name: "GoodFillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 2, unit: "mm" }, confirm: { preview_id: "<token-b>" } }
```

**Then** the follow-up mutation succeeded after every failure path — verify: each `GoodFillet` call returns `status: "OK"`  
**And** no transaction is pending after the failure — verify: `mcp document_undo { doc: <handle> }` is NOT refused with `has an open transaction; undo would commit it`  
**And** `document_undo` reverts the follow-up, not a leaked bracket — verify: `document_undo` returns `undone` equal to `buddy: <the follow-up label>`  
**And** no snapshot leaked across the failure paths — verify: after the successful follow-up, the **snapshot check** (Preconditions) returns `[]`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window shows one small rounded edge and no wreckage from the three failed attempts — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-09-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a shaded solid prism, whole and unclipped, with exactly one edge curved into a narrow rounded strip, every other visible edge sharp, no bulged or gouged face left by the 500 mm attempt, no error marker on a tree item, and no dialog. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-10: Commit failure aborts the bracket and deletes the snapshot

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (commit-failure path)

**CONDITIONAL**: `commitTransaction` raising is not reachable from the wire on a healthy build.
Force it in-process with `script_exec`. The FreeCAD `Document` type is immutable, so its method
cannot be patched. Instead, `transaction.run_mutation` is wrapped for one call: the wrapper passes
the bracket a proxy of the document whose `commitTransaction` raises, and hands the real document
back to the caller. If `script_exec` is off, mark not-exercised.

**Given** `script_exec` is on — verify: `mcp script_exec { doc: <handle>, code: "result = 1" }` returns `OK` with `value_repr` `1`  
**And** a body with a fully-constrained 20x20 mm sketch is open — verify: `mcp verify_sketch { doc: <handle>, sketch: "Sketch" }` returns `OK` with `subject.fully_constrained: true` and `subject.dof: 0`  
**And** the pre-mutation window is framed and captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view); then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-10-before.png"}' | & cua-driver call get_window_state`  

**When** a mutation whose post_verify will PASS is previewed. The preview runs its own bracket, so it comes before the patch  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
```
**And** the commit is patched to raise once  
```
mcp script_exec { doc: <handle>, code: "from freecad_buddy.usecases import transaction as _t\n_orig = _t.run_mutation\nclass _Proxy:\n    def __init__(self, d):\n        object.__setattr__(self, '_d', d)\n    def __getattr__(self, name):\n        return getattr(self._d, name)\n    def __setattr__(self, name, value):\n        setattr(self._d, name, value)\n    def commitTransaction(self):\n        raise RuntimeError('injected commit failure')\ndef _wrap(document, *args, **kwargs):\n    _t.run_mutation = _orig\n    out, envelope = _orig(_Proxy(document), *args, **kwargs)\n    return (document if isinstance(out, _Proxy) else out), envelope\n_t.run_mutation = _wrap\nresult = 'armed'" }
```
**And** the previewed pad is applied, so the commit is reached  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>" } }
```

**Then** the failure is reported, not raised — verify: a `ResultEnvelope` is returned with `status: "SPEC_FAILED"`  
**And** the injected cause is named — verify: `mutation.post_verify.explanation` equals `RuntimeError: injected commit failure`  
**And** rollback is claimed — verify: `mutation.rolled_back` is `true`  
**And** the snapshot was deleted — verify: the mutation block has no `snapshot_path` key and the **snapshot check** (Preconditions) returns `[]`  
**And** no after-fingerprint was taken — verify: `mutation.fingerprint_after` is `null`, while `fingerprint_before` carries a 64-hex `digest` and a `serializer`  
**And** the bracket is closed — verify: a subsequent well-formed `feature_pad` returns `status: "OK"` on the same handle  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window looks exactly as it did before the injected commit failure — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-10-after.png"}' | & cua-driver call get_window_state` — taken immediately after the injected failure and BEFORE the closing well-formed `feature_pad` that the bracket-is-closed assertion above needs — then `Read` both PNGs and say what each one shows. The after image must show the same flat sketch outline as the before image: no shaded solid, no partially extruded body, no error marker, no dialog. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the two images; a `rolled_back: true` claim is precisely what is being checked here, so do not read it back as the answer.  

**Cleanup**:
```
mcp script_exec { doc: <handle>, code: "from freecad_buddy.usecases import transaction as _t\nresult = _t.run_mutation.__name__" }
mcp document_close { doc: <handle> }
```
`value_repr` is `'run_mutation'`, so the wrapper is gone.

---

### TC-05-11: A committed-but-unhashable mutation keeps its snapshot

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (the commit landed; the snapshot is an operator decision)

**CONDITIONAL**: requires `fingerprint()` to raise AFTER a successful commit. Forced with a
`script_exec` patch of the bracket's `fingerprint` for one call. The mutation gate takes the
pre-mutation fingerprint before the bracket and passes it in (`features.py:372-386`), so the first
`fingerprint` call inside the bracket is the post-commit one. If `script_exec` is off, mark
not-exercised.

**Given** `script_exec` is on — verify: `mcp script_exec { doc: <handle>, code: "result = 1" }` returns `OK` with `value_repr` `1`  
**And** a body with a fully-constrained 20x20 mm sketch is open — verify: `mcp verify_sketch { doc: <handle>, sketch: "Sketch" }` returns `OK` with `subject.fully_constrained: true` and `subject.dof: 0`  

**When** the 30 mm pad is previewed. The preview runs its own bracket, so it comes before the patch  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_pad", args: { body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" } } } }
```
**And** the post-commit fingerprint is patched to raise once  
```
mcp script_exec { doc: <handle>, code: "from freecad_buddy.usecases import transaction as _t\n_orig = _t.fingerprint\n_state = {'n': 0}\ndef _fp(d, *args, **kwargs):\n    _state['n'] += 1\n    if _state['n'] == 1:\n        _t.fingerprint = _orig\n        raise RuntimeError('injected serializer failure')\n    return _orig(d, *args, **kwargs)\n_t.fingerprint = _fp\nresult = 'armed'" }
```
**And** the previewed pad, whose post_verify passes, is applied  
```
mcp feature_pad { doc: <handle>, body: "Body", profile: "Sketch", name: "Pad", length: { value: 30, unit: "mm" }, confirm: { preview_id: "<token>" } }
```

**Then** rollback is NOT claimed — verify: `mutation.rolled_back` is `false`, because the commit landed and the document is permanently changed  
**And** status is `SPEC_FAILED` — verify: envelope `status` equals `SPEC_FAILED`  
**And** the snapshot is KEPT and named — verify: `mutation.snapshot_path` is non-null, and `mcp script_exec { doc: <handle>, code: "import os\nresult = os.path.exists(r'<snapshot_path>')" }` returns `value_repr` `True`  
**And** no after-fingerprint is reported — verify: `mutation.fingerprint_after` is `null`  
**And** the mutation really committed — verify: `mcp query_tree_summary { doc: <handle>, depth: 3 }` lists `Pad` and `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`  
**And** the text does not claim a rollback — verify: envelope `text` is the unproven-rollback form `Mutation failed and its rollback could not be proven: {snapshot_path}.`, never `Mutation rolled back`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window shows the committed solid, even though the envelope reports a failure — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-11-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a shaded three-dimensional solid, about one and a half times as tall as it is wide (30 mm on 20 mm), whole and unclipped, with no error dialog. A flat sketch or an empty viewport here means the geometry the envelope says is permanent never reached the human. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image; the `SPEC_FAILED` status must not lead you to expect an empty window.  

**Cleanup**:
Remove the kept snapshot folder, then close without saving:
```
mcp script_exec { doc: <handle>, code: "import os, shutil\nshutil.rmtree(os.path.dirname(r'<snapshot_path>'))\nresult = 'removed'" }
mcp document_close { doc: <handle> }
```
Then the **snapshot check** (Preconditions) returns `[]`.

---

### TC-05-12: A setup failure mutates nothing and opens no transaction

**Priority**: Critical
**Design Ref**: `verification-design.md` §1 (pre-bracket setup)

**CONDITIONAL**: requires a setup step to raise BEFORE the transaction opens. The mutation gate
takes the pre-mutation fingerprint before the bracket (`features.py:372-386`), so a `fingerprint`
patch no longer reaches the setup path. The setup steps inside the bracket are
`tnp_guard.snapshot_references` and the `saveCopy` snapshot (`transaction.py:636-643`); a
`script_exec` patch makes the first one raise for one call. If `script_exec` is off, mark
not-exercised.

**Given** `script_exec` is on — verify: `mcp script_exec { doc: <handle>, code: "result = 1" }` returns `OK` with `value_repr` `1`  
**And** a body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad` is open — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`  
**And** the pre-mutation window is framed and captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view); then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-12-before.png"}' | & cua-driver call get_window_state`  

**When** a 2 mm fillet on `Edge1` of the pad is previewed. The preview runs its own bracket, so it comes before the patch  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 2, unit: "mm" } } } }
```
**And** the reference snapshot, the first setup step, is patched to raise once  
```
mcp script_exec { doc: <handle>, code: "from freecad_buddy.usecases import tnp_guard as _g\n_orig = _g.snapshot_references\ndef _boom(document):\n    _g.snapshot_references = _orig\n    raise RuntimeError('injected setup failure')\n_g.snapshot_references = _boom\nresult = 'armed'" }
```
**And** the previewed fillet is applied with its `confirm`  

**Then** the failure is reported as a setup failure — verify: envelope `status` is `SPEC_FAILED` and `mutation.post_verify.explanation` equals `RuntimeError: injected setup failure`  
**And** the pre-mutation fingerprint is the one the gate took — verify: `mutation.fingerprint_before` carries a 64-hex `digest` and a `serializer`  
**And** the audit did not run, and says so — verify: `mutation.post_verify.tnp_audit.status` is `"UNSUPPORTED"`  
**And** no after-fingerprint either — verify: `mutation.fingerprint_after` is `null`  
**And** rollback is not claimed — verify: `mutation.rolled_back` is `false` and `mutation.rollback_proven` is `null`  
**And** `touched` is empty — verify: `mutation.touched` equals `[]`  
**And** no snapshot survives — verify: the mutation block has no `snapshot_path` key and the **snapshot check** (Preconditions) returns `[]`  
**And** no transaction was opened — verify: `mcp document_undo { doc: <handle> }` reports `undone` equal to the label of the LAST successful mutation, not `buddy: <the failed label>`  
**And** the document is untouched — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` still returns `volume` = `12000.0`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window looks exactly as it did before the injected setup failure — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-12-after.png"}' | & cua-driver call get_window_state` — taken BEFORE the `document_undo` that the no-transaction assertion above needs — then `Read` both PNGs and say what each one shows. The after image must show the same solid prism as the before image: nothing added, nothing removed, no deformed face, no error marker, no dialog. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the two images.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-13: The fingerprint carries a serializer tag and is deterministic

**Priority**: High
**Design Ref**: `verification-design.md` §3 (AD-6 fingerprint), `data-contracts-design.md` §8

**Given** `benchmarks/g0/golden-models/box-10-20-30.FCStd` present — verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`  

**When** the golden box is opened, and a byte-identical copy of it is opened from a second path, as two independent handles. Opening the same path twice returns the same handle (`documents.py:500-502`), so the second handle needs a second file  
```bash
cp benchmarks/g0/golden-models/box-10-20-30.FCStd "$RUN_DIR/evidence/tc-05-13-box-copy.FCStd"
```
```
mcp document_open { path: "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd" }
mcp document_open { path: "$RUN_DIR/evidence/tc-05-13-box-copy.FCStd" }
```
Run Show All on each.
**And** a fingerprint is taken from each by previewing a no-effect operation  
```
mcp preview_dry_run { doc: <handle-a>, operation: { tool: "feature_body_create", args: { name: "Probe" } } }
mcp preview_dry_run { doc: <handle-b>, operation: { tool: "feature_body_create", args: { name: "Probe" } } }
```

**Then** the serializer tag is present on a mutation record — verify: a successful mutation's `mutation.fingerprint_before.serializer` is a non-null, non-empty string  
**And** the tag is the same on both sides of one bracket — verify: `mutation.fingerprint_before.serializer` equals `mutation.fingerprint_after.serializer`  
**And** the two opens are independent — verify: `<handle-a>` and `<handle-b>` differ  
**And** identical documents give identical digests — verify: the two `diff.fingerprint_before` values from the two previews are equal  
**And** the digest is a SHA-256 — verify: it matches `^[0-9a-f]{64}$`  
**And** the wire carries the digest, not the record — verify: `mutation.fingerprint_before` has exactly the keys `digest` and `serializer` (the per-object record stays in the server's digest-keyed cache)  
**And** a real geometry change moves the digest — verify: after a successful `feature_pad`, `fingerprint_after.digest` differs from `fingerprint_before.digest`  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: <handle-a> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window shows a real box, so the two equal digests describe a visible document — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-13-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one shaded rectangular solid with three visibly different edge lengths, whole and unclipped, and no error dialog. Two identical digests taken over an empty document would also be equal, so an empty viewport here voids the determinism claim. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```bash
mcp document_close { doc: <handle-a> }
mcp document_close { doc: <handle-b> }
```
```bash
rm -f "$RUN_DIR/evidence/tc-05-13-box-copy.FCStd"
```

---

### TC-05-14: A cross-tag fingerprint comparison raises, never returns "not equal"

**Priority**: High
**Design Ref**: `verification-design.md` §3 (AD-6: comparing across serializer tags is banned)

**CONDITIONAL-SKIP on a single FreeCAD build.** Producing two records with DIFFERENT serializer
tags needs two builds — one exposing `Shape.exportBinary`, one exposing only `exportBrep`. Only
one FreeCAD build is installed. Run the degraded form below: assert the tag exists, is carried on
both records, and that a record with a MISSING tag is refused rather than compared. Record the full
two-build comparison as not-exercised.

**Given** a body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad` is open — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`  
**And** a second FreeCAD build with a different serializer, if available — verify: the build exposes the other of `exportBinary` / `exportBrep`  
**And** the pre-attempt window is framed and captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view); then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-14-before.png"}' | & cua-driver call get_window_state`  

**When** the degraded form runs — a tagless record is passed to the one wire comparison that accepts a whole record  
```
mcp document_undo { doc: <handle>, expect_fingerprint: { objects: [], digest: "0000000000000000000000000000000000000000000000000000000000000000" } }
```
**And** the two-build form runs, if a second build is present — a fingerprint is taken on build A, then fed to build B as `expect_fingerprint`  

**Then** the tagless record is refused before the undo runs — verify: the degraded-form call returns `INVALID_INPUT` with the message `expect_fingerprint record: cannot compare fingerprints: serializer tag missing/mismatch (None vs '<serializer>')`, where `<serializer>` is `query_capabilities.serializer`; it returns no `matches_pre_op`, and `mcp query_mass_properties { doc: <handle>, object: "Pad" }` still returns `volume` = `12000.0`  
**And** the tag is carried on every record the wire returns — verify: `mutation.fingerprint_before.serializer` is non-null on a successful mutation  
**And** both records in one bracket carry the same tag — verify: `fingerprint_before.serializer` equals `fingerprint_after.serializer`  
**And** a `{digest, serializer}` object without a serializer is refused at the boundary — verify: `mcp document_undo { doc: <handle>, expect_fingerprint: { digest: "abc" } }` returns `INVALID_INPUT` with `expect_fingerprint serializer None does not match this build's '<serializer>'; fingerprints with different serializers cannot be compared`, and the undo does not run  
**And** CONDITIONAL two-build — verify: the cross-build comparison RAISES `cannot compare fingerprints: serializer tag missing/mismatch` and never returns a quiet `false`  
**And** a quiet "not equal" is never produced for a tag mismatch — verify: in no run does a tag mismatch surface as `matches_pre_op: false` or `rolled_back: false` without an accompanying comparison error  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window looks exactly as it did before the refused comparison — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-14-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what each one shows. The after image must show the same solid prism as the before image, so the refused `expect_fingerprint` stopped the undo rather than letting it run: no removed feature, no reverted geometry, no error marker, no dialog. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the two images.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-15: TNP reports CLEAN on a healthy mutation

**Priority**: Critical
**Design Ref**: `verification-design.md` §3 (AD-7 TNP guard), `mcp-tools-design.md` §1.4 (`tnp_audit`)

**Given** a body with a 30 mm `Pad` and a 2 mm `Fillet` referencing one pad edge — verify: `mcp query_dependencies { doc: <handle> }` shows `Fillet` depending on `Pad`  
**And** this build exposes an element map — verify: `mcp query_capabilities {}` returns `element_map_available: true`  
**And** the pre-mutation window is framed and captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view); then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-15-before.png"}' | & cua-driver call get_window_state`  

**When** a harmless parameter change on the fillet is previewed and applied. A `Pad` `Length` change is not harmless on the build under test: it breaks the fillet's edge link (`Invalid edge link`), so the radius is changed instead  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_set_parameters", args: { feature: "Fillet", parameters: { Radius: { value: 3, unit: "mm" } } } } }
mcp feature_set_parameters { doc: <handle>, feature: "Fillet", parameters: { Radius: { value: 3, unit: "mm" } }, confirm: { preview_id: "<token>" } }
```

**Then** the mutation committed — verify: envelope `status` is `OK`  
**And** the audit ran and is CLEAN — verify: `mutation.post_verify.tnp_audit.status` equals `"CLEAN"`  
**And** every listed finding is a passing verdict — verify: every member of `tnp_audit.findings` has `verdict` `"RE_BASELINED"`. The wire block lists only non-`PASS` findings and counts the rest in `tnp_audit.counts`  
**And** the element map version is reported — verify: `tnp_audit.element_map_version` is a non-null string  
**And** the audit is not the short-circuit block — verify: `tnp_audit.counts.PASS` is at least `1`, proving check 4 actually graded the fillet's reference  
**And** the reference survived — verify: `mcp query_mass_properties { doc: <handle>, object: "Fillet" }` returns `OK` and the fillet is still present in `query_tree_summary`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window shows the same solid whose rounded edge is still on the same corner — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-15-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what each one shows. The after image must show the same solid at the same size as the before image, still with exactly one edge curved into a rounded strip, slightly wider than before (3 mm, was 2 mm), and that strip on the same corner of the shape as before: not migrated to another edge, not gone, not spread to several edges. A fillet that silently re-attached to a different edge is the toponaming defect this scenario exists for, and it is visible in the pixels before it is visible in any envelope. The judgement is on the pixels alone — a `CLEAN` audit status may not stand in for looking at the two images.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-16: TNP flags REPOINTED when a referenced face moves; a dress-up off the Tip is refused

**Priority**: Critical
**Design Ref**: `verification-design.md` §3 (AD-7, Layer 1 mapped-name grading)

A chamfer on `Pad` while the Tip is `Fillet` no longer reaches the audit: a dress-up whose `base` is
not the Body's `Tip` is refused before the bracket, because it would silently drop every feature
after the base (Story 10.3 D9). The REPOINTED path is reached instead by moving the face an
attachment references, as TC-03-20 does.

**Given** document A: a body with a 30 mm `Pad` and a 2 mm `Fillet` on `Edge1` of that pad, so the Body's `Tip` is `Fillet` — verify: `mcp query_dependencies { doc: <handle-a> }` shows `Fillet` depending on `Pad`  
**And** document B, built as in the TC-03-20 Given: a Body with the 60 x 40 x 5 mm `PlatePad` and a sketch `BossProfile` attached to the plate's top face, holding one external edge projected from `PlatePad` — verify: `mcp query_dependencies { doc: <handle-b> }` shows an edge from `BossProfile` to `PlatePad`, and `mcp query_mass_properties { doc: <handle-b>, object: "PlatePad" }` returns `volume` = `12000.0`  
**And** this build exposes an element map — verify: `mcp query_capabilities {}` returns `element_map_available: true`  
**And** the pre-mutation window of document B is framed and captured — verify: `mcp view_fit_viewport { doc: <handle-b> }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view); then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-16-before.png"}' | & cua-driver call get_window_state`  

**When** a chamfer on an edge of `Pad` is asked for on document A, naming `Pad` as its base while the Tip is `Fillet`  
```
mcp preview_dry_run { doc: <handle-a>, operation: { tool: "feature_chamfer", args: { body: "Body", base: "Pad", name: "Chamfer", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge2" }], size: { value: 3, unit: "mm" } } } }
```
**And** on document B the plate is thickened, which moves the face `BossProfile` is attached to  
```
mcp preview_dry_run { doc: <handle-b>, operation: { tool: "feature_set_parameters", args: { feature: "PlatePad", parameters: { Length: { value: 30, unit: "mm" } } } } }
mcp feature_set_parameters { doc: <handle-b>, feature: "PlatePad", parameters: { Length: { value: 30, unit: "mm" } }, confirm: { preview_id: "<token>" } }
```

**Then** the off-Tip dress-up is refused before the bracket — verify: the document A preview returns `INVALID_INPUT` with a message starting `dress-up base Pad is not the Tip of Body Body; the Tip is Fillet`, it carries no `mutation` block and no `snapshot_path`, and `mcp query_tree_summary { doc: <handle-a>, depth: 3 }` does not list `Chamfer`  
**And** the audit flagged the moved reference — verify: on document B `mutation.post_verify.tnp_audit.status` equals `"FLAGGED"` and the envelope `status` is `SPEC_FAILED`  
**And** a REPOINTED finding names the sketch's reference — verify: `tnp_audit.findings` contains an entry with `verdict: "REPOINTED"` and `owner` equal to `"BossProfile"`  
**And** the finding names its layer — verify: that entry's `layer` is `1` or `2`  
**And** post_verify failed on the audit, not earlier — verify: `recompute_clean` is `true`, `is_valid` is `true`, and `explanation` starts with `TNP audit flagged `  
**And** the mutation was rolled back — verify: `mutation.rolled_back` is `true` and `mutation.rollback_proven` is `"rolled_back_verified"` or `"rolled_back_via_snapshot"`  
**And** the plate did not change — verify: `mcp query_mass_properties { doc: <handle-b>, object: "PlatePad" }` still returns `volume` = `12000.0`  
**And** the preview predicted it — verify: the document B `preview_dry_run` reports `diff.tnp_precheck.status` equal to `"FLAGGED"`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle-b> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window looks exactly as it did before the flagged mutation — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-16-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what each one shows. The after image must show the same thin plate as the before image, not a plate six times thicker, with `BossProfile` still drawn on its top face and the projected external edge still along a real edge of the plate. If the plate is thicker, or the sketch hangs in space away from the plate, the rollback restored the numbers but not the model, and that is the finding. The judgement is on the pixels alone — no MCP status, digest, or render may stand in for looking at the two images.  

**Cleanup**:
```bash
mcp document_close { doc: <handle-a> }
mcp document_close { doc: <handle-b> }
```

---

### TC-05-17: TNP flags BROKEN when a referent vanishes

**Priority**: Critical
**Design Ref**: `verification-design.md` §3 (AD-7, Layer 0 validity sweep and Layer 1 unresolvable element)

**Given** a body with a 30 mm `Pad` and a 2 mm `Fillet` on `Edge1` of that pad is open  
**And** this build exposes an element map  
**And** the pre-mutation window is framed and captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view); then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-17-before.png"}' | & cua-driver call get_window_state`  

**When** the geometry the fillet's base depends on is removed — the pad's profile sketch is shrunk so the filleted edge no longer exists  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "sketch_remove_geometry", args: { sketch: "Sketch", geo_ids: [0] } } }
mcp sketch_remove_geometry { doc: <handle>, sketch: "Sketch", geo_ids: [0], confirm: { preview_id: "<token>" } }
```

**Then** the recompute failure sets the status — verify: envelope `status` is `RECOMPUTE_ERROR` and `mutation.post_verify.recompute_clean` is `false`  
**And** the audit still ran and flagged it — verify: `mutation.post_verify.tnp_audit.status` equals `"FLAGGED"`, not `"CLEAN"` and not `"UNSUPPORTED"`  
**And** a BROKEN finding is present — verify: `tnp_audit.findings` contains an entry with `verdict: "BROKEN"`  
**And** the finding comes from the Layer-0 validity sweep — verify: that entry's `layer` is `0`  
**And** the break is attributed to the fillet — verify: a BROKEN entry's `owner` is `"Fillet"`  
**And** the mutation was rolled back — verify: `mutation.rolled_back` is `true`  
**And** the fillet is intact after the rollback — verify: `mcp query_mass_properties { doc: <handle>, object: "Fillet" }` returns `status: "OK"`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window looks exactly as it did before the removed geometry — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-17-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what each one shows. The after image must show the whole solid with its rounded edge, exactly as in the before image: no missing or open face, no collapsed or shrunken body, no red or marked error icon in the model tree, no dialog. A body left visibly broken after a `rolled_back: true` claim is the defect. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the two images; an `OK` from `query_mass_properties` on `Fillet` is not proof the human sees an intact model.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```

---

### TC-05-18: TNP UNSUPPORTED is never reported as CLEAN or PASS

**Priority**: Critical
**Design Ref**: `verification-design.md` §3 (AD-7, capability gate)

**CONDITIONAL-SKIP on FreeCAD 1.1.** The build-gated `UNSUPPORTED` path needs
`shim.element_map_available()` to return false, which FreeCAD 1.1.x does not do — its toponaming
element map is always present. Run the degraded form: a path where the audit never ran (a setup
failure, forced with the TC-05-12 `script_exec` patch) must report `UNSUPPORTED`, never `CLEAN`,
and no finding may carry `PASS` alongside an `UNSUPPORTED` status. Record the build-gated form as
not-exercised.

**Given** a build reporting no element map, if one is available — verify: `mcp query_capabilities {}` returns `element_map_available: false`  
**And** degraded form: a body with a fully-constrained 20x20 mm sketch and a 30 mm `Pad` is open, so the Tip is `Pad` — verify: `mcp query_mass_properties { doc: <handle>, object: "Pad" }` returns `volume` = `12000.0`  
**And** the pre-attempt window is framed and captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, or failing that the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view); then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-18-before.png"}' | & cua-driver call get_window_state`  

**When** the degraded form runs — a 2 mm fillet on `Edge1` is previewed, the reference snapshot is patched to raise once with the TC-05-12 `script_exec` call, and the previewed fillet is applied, so the bracket fails in setup and the audit never runs  
```
mcp preview_dry_run { doc: <handle>, operation: { tool: "feature_fillet", args: { body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 2, unit: "mm" } } } }
mcp script_exec { doc: <handle>, code: "from freecad_buddy.usecases import tnp_guard as _g\n_orig = _g.snapshot_references\ndef _boom(document):\n    _g.snapshot_references = _orig\n    raise RuntimeError('injected setup failure')\n_g.snapshot_references = _boom\nresult = 'armed'" }
mcp feature_fillet { doc: <handle>, body: "Body", base: "Pad", name: "Fillet", edges: [{ kind: "mapped_name", object: "Pad", mapped_name: "Edge1" }], radius: { value: 2, unit: "mm" }, confirm: { preview_id: "<token>" } }
```
**And** the build-gated form runs, if a no-element-map build exists — any successful mutation is run on it  

**Then** an un-run audit is UNSUPPORTED, not CLEAN — verify: the apply returns `SPEC_FAILED` and `mutation.post_verify.tnp_audit.status` equals `"UNSUPPORTED"`  
**And** UNSUPPORTED carries no passing findings — verify: `tnp_audit.findings` is `[]` and `tnp_audit.counts` holds no `PASS` key  
**And** the element map version is still reported — verify: the `tnp_audit.element_map_version` key is present  
**And** CONDITIONAL build-gated — verify: on a no-element-map build, `mutation.post_verify.tnp_audit.status` equals `"UNSUPPORTED"` and every finding carries `verdict: "UNSUPPORTED"` with `layer: 0`  
**And** CONDITIONAL build-gated — verify: on that build no finding carries `verdict: "PASS"`, because an ungraded reference is not a passing one  
**And** the distinction is never collapsed — verify: across every scenario in this file, no envelope reports `tnp_audit.status: "CLEAN"` together with an `element_map_version` of `null`  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the human's window looks exactly as it did before the failed mutation — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-05-18-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what each one shows. The after image must be the same scene as the before image: no added feature, no rounded edge, no removed geometry, no error marker, no dialog. A setup failure mutates nothing, so an `UNSUPPORTED` verdict must be accompanied by a window that did not change at all. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the two images.  

**Cleanup**:
```bash
mcp document_close { doc: <handle> }
```
