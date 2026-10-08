# Phase B results: TC-16-07, TC-05-01, -02, -05, -06, -13

Run `2026-10-08-02`. FreeCAD 1.1.4 GUI, pid 10600, window 595056. Launch at `addon.log` 11:50:50. No
`SECURITY: mutation auto-approve ENABLED` line after that launch (last one is line 346, 11:40:41,
the earlier launch). So the confirm gate is ON. Corroboration: the first un-confirmed
`feature_body_create` was refused with `this mutation requires a confirm` (`phaseB-calls.jsonl`
label `16-07-body-noconfirm`), and `audit-B.jsonl` has 0 `"mode": "auto_approve"` lines.

Evidence:
- `phaseB-calls.jsonl`: every MCP call, raw blocks, char counts, seconds, `isError`.
- `audit-B.jsonl`: audit log of this launch (line numbers cited below).
- PNGs: `tc-16-07-*.png`, `tc-05-*.png`.

Terms used below:
- **gate ON**: every mutation needs `preview_dry_run` first, then `confirm.preview_id` (a one-use token).
- **rollback proof**: after a failed mutation, the bridge re-hashes the document and compares to the before hash. `rolled_back_verified` = undo restored it; `rolled_back_via_snapshot` = file restore was needed.
- **snapshot**: `saveCopy` of the document taken before each mutation, in a `FCB_TMP_snap_*` folder.

## Verdicts

| Scenario | Verdict | Reason |
| --- | --- | --- |
| TC-16-07 | **PASS** | All 5 lines pass. Document closed. |
| TC-05-01 | **PASS** (2 test-case defects) | Product correct. Given check tool returns no `dof`; visual text says "3x as tall", geometry is 1.5x. Document closed. |
| TC-05-02 | **PARTIAL** | Snapshot seen and deleted. Snapshot contents not readable from outside FreeCAD (folder ACL). Test-case paths point at `$TEMP`, which is wrong. `tc05_02` left open. |
| TC-05-05 | **PASS** (1 test-case defect) | Proven rollback, document unchanged on screen. "not an MCP isError" line is stale vs code. Document closed. |
| TC-05-06 | **FAIL** | Escalation not exercised (CONDITIONAL). Reproducer 1 (900 mm pocket) **committed and destroyed the solid**; product defect. Documents `tc05_06`, `tc05_06b` left open. |
| TC-05-13 | **PASS** (2 deviations) | Equal digests, serializer tag, real change moves digest, box on screen. Documents closed. |

---

## TC-16-07: visibility-only edit needs no token; any other edit does

Fixture: `tc16_vis`, handle `fcb-doc:5AFznEyGN_Rnt3oP64QYGg`. Body, sketch, geometry and 30 mm pad, each built with a preview token. `query_mass_properties Pad` before: volume `12000.0`.

| Assertion | Result |
| --- | --- |
| Given: no SECURITY auto-approve line in new addon.log lines | PASS (see header) |
| Visibility-only call applies | PASS. `16-07-hide`: `status` `OK`, 1100 chars, 0.06 s. Digest before = after = `a1f853c7bf2e…`, `changed: []` |
| Audited as display state | PASS. `audit-B.jsonl:28`: `"mode": "display_state"`, `tool` `feature_set_parameters` |
| Mixed call refused | PASS. `16-07-mixed`: `status` `INVALID_INPUT`, message `this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id`. 2786 chars, 0.02 s |
| Mixed call changed nothing | PASS. `query_mass_properties Pad` → volume `12000.0` |
| (visual) solid hidden | PASS. Read both. Before (`tc-16-07-before.png`, after `view_fit_viewport` OK, Body expanded in Model panel): tall shaded grey square prism, isometric; `Pad` row in black text with an open eye. After (`tc-16-07-after.png`, same camera, status bar `52.21 mm x 42.95 mm` in both): no shaded prism; only a thin black square outline (the sketch) where the prism base stood; `Pad` row greyed with a crossed eye. No taller prism. No dialog. |

Deviation: no fit before the after capture. The camera stays the same as the before image, so the two images compare directly (test plan §3 rule 5, "unchanged" sub-rule). A fit on a hidden solid would reframe to the sketch.

Observation: the `INVALID_INPUT` refusal block carries a full Python traceback in `detail.data.traceback` (2786 chars for a refusal). Same on every `INVALID_INPUT` in this run.

Cleanup: `document_close` OK.

---

## TC-05-01: successful mutation reports the full bracket

Fixture: `tc05_01`, handle `fcb-doc:J3CbgYcDk3eh7UEh6Q4s2g`.

| Assertion | Result |
| --- | --- |
| Given: `query_sketch_info` returns `fully_constrained: true`, `dof: 0` | **Test-case defect.** `query_sketch_info` returns only `sketch`, `geometry`, `constraints` (`src/freecad_buddy/usecases/queries.py:706` `structured = {"sketch": obj.Name, "geometry": geometry, "constraints": constraints}`). Substitute evidence: `sketch_add_geometry` result `sketch_state.dof` `0`, `fully_constrained` `true`. Fixture state is correct. |
| When: record `query_mass_properties Body` | Returned `INVALID_INPUT` `object has no queryable shape: Body` (empty body). Recording step only; no assertion depends on it. |
| `feature_pad` `OK`, `detail` null | PASS. 1401 chars, 0.13 s |
| Both digests 64-hex and different | PASS. `14aed5854fc4…` → `a1f853c7bf2e…` |
| `post_verify.passed` true, `explanation` null | PASS |
| `rolled_back` false, `rollback_proven` null | PASS |
| `schema` `fcb.mutation/2`, no `transaction_id` | PASS. Keys: `changed, fingerprint_after, fingerprint_before, post_verify, rollback_proven, rolled_back, schema, touched` |
| Text starts `Mutation committed; fingerprint ` + first 12 of after digest | PASS. `Mutation committed; fingerprint a1f853c7bf2e.` |
| `Pad` volume `12000.0` | PASS |
| (visual) framed | PASS. `view_fit_viewport` OK |
| (visual) solid box, "roughly three times as tall as wide" | Pixels: one shaded grey square prism, isometric, whole, no dialog. Vertical edge about 575 px, top edge about 383 px: about **1.5 times** as tall as wide. A small part near the top-right corner is behind the docked Tasks panel. **Test-case defect**: 20 x 20 x 30 mm is 1.5:1, not 3:1. The picture matches the requested geometry. |

Stale parenthetical: "(the audit log `mutation` line keeps it)" is false. `audit-B.jsonl:56` (this call's mutation line) has no `transaction_id`. `src/freecad_buddy/adapters/audit_log.py` never writes it, although `usecases/result_projection.py:101` docstring says "the audit log records them from the full block". Doc/test-case drift; not asserted.

Cleanup: `document_close` OK. Closed although two lines are test-case defects, because the product result was correct and no state is needed to fix a wording error.

---

## TC-05-02: snapshot created during the bracket, deleted on commit

Fixture: `tc05_02`, handle `fcb-doc:-dX1MMmRjvaLiN2GfaSfWw`. Sketch `dof` 0 (from `sketch_add_geometry`; `query_sketch_info` has no `dof`, same defect as TC-05-01).

**Path drift (test-case finding).** Snapshots are not under `$TEMP`. Code: `usecases/transaction.py:107` `tempfile.mkdtemp(prefix=_SNAPSHOT_PREFIX, dir=temp_dir())`, and `usecases/documents.py:72` `workdir_root() / "tmp" / f"{_TEMP_PREFIX}session_{os.getpid()}_{_SESSION_TOKEN}"`. Live path: `%LOCALAPPDATA%\freecad-buddy-workdir\tmp\FCB_TMP_session_10600_a34422c0\FCB_TMP_snap_*`.

**Environment.** `$TEMP` holds 10 stale `FCB_TMP_snap_*` folders dated 2026-09-22 15:57. Each is `Permission denied` to list, and `icacls` returns `Access is denied`. They cannot be removed without elevation, and removing them is outside this agent's write scope. So the file precondition "Temp directory free of stale snapshots" is NOT met, and every literal `ls -d "$TEMP"/FCB_TMP_snap_*` check is void. I ran three watchers: the literal one on `$TEMP`, the same loop on the session folder, and a tight loop.

| Assertion | Result |
| --- | --- |
| Snapshot folder existed mid-operation | PASS on the real path. `tc-05-02-snapwatch-session.log`: 1 line, `…\FCB_TMP_session_10600_a34422c0/FCB_TMP_snap_ao8oebxj/`. Literal `$TEMP` log: `grep -c` = 120, but all 120 lines are the 10 stale 2026-09-22 folders (12 samples each), so the literal count proves nothing. |
| Logged folder held `<DocumentName>.FCStd` | **NOT RUN (cannot be observed).** Two extra runs (`tc05_02b`, `tc05_02c`) with a Python watcher (`os.listdir` tight loop). The folder existed about 108 ms; listing it raised `PermissionError 13`, then `FileNotFoundError` (`tc-05-02-snapwatch-contents.log`). `mkdtemp` makes an owner-only folder that this agent's process cannot read. Code says the file is `f"{doc.Name}.FCStd"` (`transaction.py:108`), and TC-05-06 below shows a kept snapshot named `…\FCB_TMP_snap_fi4o7967\tc05_06.FCStd`, which is indirect support. |
| Snapshot gone after commit | PASS on the real path: session folder empty after the call. Literal `$TEMP`: 10 stale folders remain (pre-existing, not from this run). |
| No `snapshot_path` on the `OK` block | PASS. `05-02-pad` `OK`, 1401 chars, 0.16 s; key absent. `audit-B.jsonl:83` `"snapshot_path": null` |
| No `.FCBak` left | PASS. None in `$TEMP`, none under `freecad-buddy-workdir` |
| (visual) framed | PASS. `view_fit_viewport` OK |
| (visual) solid prism | PASS. `tc-05-02-after.png`: one shaded grey square prism, isometric, whole, not cut by the viewport edge (small part near top-right behind the Tasks panel), no dialog. |

Deviations: snapwatch logs kept as evidence, not deleted (Cleanup step); `rm -rf "$TEMP"/FCB_TMP_snap_*` not run (outside write scope, and permission denied). Extra documents `tc05_02b`, `tc05_02c` closed. `tc05_02` left open (its Cleanup has no close, and one line is not verified).

---

## TC-05-05: failed mutation proves its rollback by re-hashing

Fixture: `tc05_05`, handle `fcb-doc:pZdA0dPsHtJl0uKlmn6BfQ`. `Pad` volume `12000.0`.

Preview `diff.fingerprint_before` = `a1f853c7bf2e6ae6d549db4a3cadbd3d31b0f93effc40153cbe5f11152d32d22`.

| Assertion | Result |
| --- | --- |
| Call did not raise: a ResultEnvelope, "not an MCP `isError` response" | Envelope returned in full (1338 chars, 0.12 s). But `isError` is **true**. **Test-case defect**: `src/freecad_buddy/adapters/mcp_server.py:100` `isError=envelope.get("status") != "OK"` sets it on every non-OK envelope, by design since Story 1.4. Intent (no exception, full envelope) holds. |
| `rolled_back` true, `rollback_proven` `rolled_back_verified` | PASS |
| No `snapshot_path` key | PASS. `audit-B.jsonl:164` `"snapshot_path": null` |
| `changed` `[]`; after digest = preview before, or equal mass properties | PASS. `changed: []`. After digest `5ddf1f1ce76a…` differs from `a1f853c7bf2e…`; mass properties equal (volume 12000.0, area 3199.9999999999995, com (5.55e-18, 1.45e-16, 15.0) before and after) |
| Status is failing check's; `detail.code` = `mutation.` + lowercase | PASS. `RECOMPUTE_ERROR`, `mutation.recompute_error`. Message `recompute left 1 object(s) invalid: Fillet: BRep_API: command not done` |
| Text starts `Mutation rolled back (rolled_back_verified): ` | PASS |
| `Pad` 12000.0; tree has no `Fillet` | PASS. Tree: Body, Origin (7 children), `Pad *tip`, `Sketch` |
| Snapshot cleaned up | PASS on the real path (session folder empty). Literal `$TEMP`: 10 stale folders, void (see TC-05-02) |
| (visual) framed | PASS. `view_fit_viewport` OK |
| (visual) window as before | PASS. Read both. Before (`tc-05-05-before.png`) and after (`tc-05-05-after.png`): same tall shaded square prism, same sharp edges, same size and place. Model panel the same: `Body` > `Origin`, `Pad`; no `Fillet` row; no error marker; no dialog. One difference: the status bar now shows a notification counter `1` next to the blue square at the bottom right. That is FreeCAD's own notification of the failed recompute inside the bracket. It is not in the model. |

Cleanup: `document_close` OK.

---

## TC-05-06: escalation to snapshot restore (CONDITIONAL)

Fixture `tc05_06`, handle `fcb-doc:XsfcDNMGci7owgor_WTmWg`: Body, 20x20 sketch, 30 mm Pad, 2 mm Fillet on `Edge1`, `Sketch001` on Fillet `Face7`, a 100 x 100 mm fully constrained square in `Sketch001` (`dof` 0). Deviation: the fillet-created face (`Face3`) is cylindrical, so `sketch_create` refused it (`Face3 on Fillet is not a planar face`). `Face7` is a planar face of the Fillet result (plane y = 10). `query_dependencies` shows `{"from":"Sketch001","to":"Fillet"}`: Given met.

Before image: I captured `tc05_06` and described it (shaded prism with one narrow rounded vertical edge at the left, a large square outline behind it, Model panel `Body` > `Origin`, `Pad` grey, `Fillet`, `Sketch001`). That file was then overwritten by my mistake with the identical `tc05_06b` fixture capture, now saved as `tc-05-06b-before.png`; the pixels are the same scene.

Reproducer search (each with a preview token):

| # | Call | Result |
| --- | --- | --- |
| 1 | `feature_pocket` `Sketch001`, 900 mm (doc `tc05_06`) | **`SPEC_FAILED`, the pocket COMMITTED.** `rolled_back` false, `rollback_proven` null, `fingerprint_after` null, `snapshot_path` `…\FCB_TMP_snap_fi4o7967\tc05_06.FCStd` (kept), `post_verify.recompute_clean` true, `is_valid` true, `explanation` `OverflowError: cannot convert float infinity to integer`. Text `Mutation failed and its rollback could not be proven: …tc05_06.FCStd.` 1327 chars, 0.08 s. `audit-B.jsonl:228` `verify_verdict` `SPEC_FAILED`. |
| 2 | `feature_pattern` linear, 200 occurrences (doc `tc05_06b`) | Literal TC args refused: `feature_pattern() got an unexpected keyword argument 'base'` (**test-case defect**: the tool takes `originals` and a `direction` selector, `usecases/features.py:1342-1356`). Adapted: `originals: ["Fillet"]`, `direction: {kind: mapped_name, object: X_Axis}`, `length` 4000 mm. Result `OK`, committed; Pattern volume 11974.25 (= Fillet volume, so no copies), `is_tip` false. Not a failure path. |
| 3 | `feature_set_parameters` Fillet `Radius` 400 mm (doc `tc05_06b`) | `RECOMPUTE_ERROR`, `rolled_back` true, `rollback_proven` `rolled_back_verified`. After digest `6affe5b0…` vs preview before `ca50893b…`, `changed: []`. Fillet `Radius` still `2.0 mm`, volume 11974.25. 1564 chars, 0.22 s. |

Fresh doc `tc05_06b` (`fcb-doc:ZvKaqeX7d5eWP-8vZRDmjg`, same fixture) was built for #2 and #3, because #1 changed `tc05_06`.

| Assertion | Result |
| --- | --- |
| Any reproducer hit `rolled_back_via_snapshot` | No. Escalation NOT EXERCISED |
| `snapshot_path` on escalated block; `rolled_back` true; digest restored; handle usable; label kept | NOT RUN (escalation not reached) |
| CONDITIONAL: no `rolled_back: true` with `rollback_proven: null` | PASS. #1 claims no rollback (`rolled_back` false); #3 is proven |
| (visual) framed | PASS. `view_fit_viewport` OK on both docs |
| (visual) same solid, no 900 mm pocket, no 200-instance array, no oversized fillet | **FAIL for `tc05_06`.** `tc-05-06-after-pocket.png`: the shaded prism is gone. Only two thin outlines remain: the large square of `Sketch001` and a small diamond (the base sketch) where the prism stood. Model panel: `Fillet` greyed, new `Pocket` row visible. No dialog, no error marker. **PASS for `tc05_06b`** (`tc-05-06b-after.png`): same prism with the same narrow rounded left edge and same size as before, no array, no big fillet; Model panel now shows `Pattern` visible and `Fillet` greyed (the committed #2). |

### Product defect P1: a pocket that removes the whole solid commits, then the after-hash crashes

Decisive evidence: `05-06-r1-pocket` result above; after it, `query_mass_properties Pocket` → `"solid":false,"volume":null`, bbox `xmin 1.7976931348623157e+308`; tree `Pocket *tip`; Body has no solid.

Cause, two parts:
1. `post_verify` does not grade a null result shape. `src/freecad_buddy/usecases/transaction.py:143-152` `_shape_bearing` keeps a name only `if shape is not None and not (is_null is not None and is_null())`. The empty `Pocket` shape is skipped, so `verify_shape` never runs on it and `passed` is true. The commit runs (`transaction.py:661`).
2. The after-fingerprint overflows. An empty shape's `BoundBox` is ±DBL_MAX, which is finite. `src/freecad_buddy/usecases/fingerprint.py:65-68`:
   ```
   number = float(value)
   if not math.isfinite(number):
       return 0.0
   return round(number / step) * step
   ```
   `1.7976931348623157e+308 / 1e-6` is `inf`, so `round(inf)` raises `OverflowError: cannot convert float infinity to integer` (reproduced in plain Python). The unhashable-commit branch (`transaction.py:674-679`) then reports `SPEC_FAILED` with the snapshot kept.

The report is honest (no rollback claimed, snapshot named), but the user's solid is destroyed by a call that a correct `post_verify` would have rejected and rolled back. The wording `Mutation failed and its rollback could not be proven` also never says the change was committed.

Related, same root: the preview of #1 already reported `diff.validity.status` `SPEC_FAILED` with the same `OverflowError`, but the preview envelope was `OK`, its text said `valid=True`, and it minted a token. The preview's run on its throw-away copy also kept a snapshot that nothing deletes: `FCB_TMP_snap_0_k8j4t4` (12:01:03) is still in the session folder next to the kept `fi4o7967`. No `addon.log` line records the OverflowError.

Observation (not verified further): #2 committed a `Pattern` that is not the Body `Tip` (`Tip` stays `<PartDesign::Fillet>`), although `features.py:250` says `Body.addObject` advances `Tip`.

Cleanup NOT run: `tc05_06` and `tc05_06b` left open; both snapshot folders left on disk.

---

## TC-05-13: fingerprint carries a serializer tag and is deterministic

| Assertion | Result |
| --- | --- |
| Given: golden box present | PASS. 2215 bytes |
| Two independent handles | Deviation. A second `document_open` of the same path returns the same handle `fcb-doc:M-MCvV6R2MR3N9FuDz_GrA`. Handle-b is a byte copy at `evidence/tc05-13-b/box-10-20-30.FCStd` → `fcb-doc:GKFN0DXGNZRonVT_jjkFdQ`, name `box_10_20_31` |
| Serializer tag non-empty on a successful mutation | PASS. `05-13-apply-a` (`feature_body_create Probe`, confirmed): `serializer` `exportBinary` |
| Same tag on both sides | PASS. `exportBinary` / `exportBinary` |
| Identical documents give identical digests | PASS. Preview a `554070c862f8…`, preview b `554070c862f8…`, repeat on a `554070c862f8…`. Also, `feature_pad` on two separate new docs (`tc05_01`, `tc05_02`) gave the same before/after pair `14aed5854fc4…` → `a1f853c7bf2e…` |
| SHA-256 form | PASS. Matches `^[0-9a-f]{64}$` |
| Wire carries digest only | PASS. Keys exactly `digest`, `serializer` |
| Real change moves the digest | PASS. `feature_pad` (TC-05-01): `14aed5854fc4…` → `a1f853c7bf2e…`. Body create on box: `554070c862f8…` → `21297bb40fec…` |
| (visual) framed | `view_fit_viewport` on handle-a first returned `INVALID_INPUT` `the live viewport is showing 'box_10_20_31', not the targeted 'box_10_20_30'`. I clicked the handle-a tab with `cua-driver`, then the fit returned `OK` |
| (visual) real box, three different edge lengths | PASS after one fix. First capture (`tc-05-13-after-hidden-b.png`): **empty viewport**; `Box` row greyed with a crossed eye. **Fixture defect**: the golden `box-10-20-30.FCStd` is saved with `Box` hidden. I set `Visibility: true` on handle-a (display-state call; digest `21297bb40fec…` before and after). `tc-05-13-after.png`: one shaded rectangular solid, isometric, three clearly different edge lengths (about 212, 425 and 640 px), whole; the docked Tasks panel covers a small strip near the right face; no dialog. |

Cleanup: both `document_close` OK.

---

## Product defects

| ID | Defect | Where |
| --- | --- | --- |
| P1 | A feature with an empty result shape passes `post_verify` and commits; the solid is destroyed | `usecases/transaction.py:143-152` |
| P2 | `fingerprint` crashes on an empty shape (DBL_MAX bbox / 1e-6 overflows) | `usecases/fingerprint.py:65-68` |
| P3 | Preview reports `OK`, `valid=True` and mints a token when its own `diff.validity.status` is `SPEC_FAILED` | `usecases/preview.py` (`05-06-r1-pocket-preview`) |
| P4 | A preview whose copy-run hits the unhashable path leaves its snapshot folder behind | `FCB_TMP_snap_0_k8j4t4` in the session folder |
| P5 (minor) | `INVALID_INPUT` refusals carry a full traceback (about 1.5 to 2.8 k chars) | every refusal in `phaseB-calls.jsonl` |
| P6 (minor) | No `addon.log` line for the post-commit `OverflowError` | `addon.log` 11:50:50 onward |

## Test-case defects

| Case | Line | Fix |
| --- | --- | --- |
| TC-05-01, -02 | `query_sketch_info` → `fully_constrained`, `dof` | Tool does not return them (`queries.py:706`). Use the `sketch_add_geometry` `sketch_state` |
| TC-05-01 | "roughly three times as tall as it is wide" | 20 x 20 x 30 is 1.5:1 |
| TC-05-01 | "(the audit log `mutation` line keeps it)" for `transaction_id` | Audit line has no `transaction_id` |
| TC-05-02, -05, -06 | `$TEMP/FCB_TMP_snap_*` | Real path is `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/FCB_TMP_snap_*` |
| TC-05-02 | Check snapshot contents from outside | Folder is owner-only; listing is denied. Needs an in-process check or a different proof |
| TC-05-05 | "not an MCP `isError` response" | Every non-OK envelope sets `isError` (`mcp_server.py:100`) |
| TC-05-06 | `feature_pattern` `base`, `direction: "X"` | Use `originals`, a `direction` selector, and `length` |
| TC-05-06 | Sketch on a "fillet-created face" | That face is cylindrical; use a planar face of the Fillet result |
| TC-05-13 | Two handles from one path | Second open returns the same handle; use a copy |
| TC-05-13 | Golden box visible | `Box` is saved hidden in `box-10-20-30.FCStd` |

## Not verified

- TC-05-02 snapshot file name while the bracket is open (ACL).
- TC-05-06 snapshot-restore escalation (no reproducer reached it).

## State left behind

- Open documents: `tc05_02` (TC-05-02), `tc05_06` and `tc05_06b` (TC-05-06 FAIL).
- Snapshot folders in `%LOCALAPPDATA%\freecad-buddy-workdir\tmp\FCB_TMP_session_10600_a34422c0\`: `FCB_TMP_snap_fi4o7967` (kept by P1, holds `tc05_06.FCStd`), `FCB_TMP_snap_0_k8j4t4` (P4 leak).
- 10 stale `$TEMP\FCB_TMP_snap_*` folders from 2026-09-22, access denied, not touched.
- FreeCAD pid 10600 still running.
