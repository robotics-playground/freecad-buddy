# TC-16 batch A results (TC-16-01, -02, -03, -04, -06)

Run: `2026-10-08-02`. FreeCAD 1.1.4 GUI pid 26356, window 463900, auto-approve ON (addon.log line 346,
`2026-10-08 11:40:41,250 ... SECURITY: mutation auto-approve ENABLED ...`). Every MCP call is in
`tc16-calls.jsonl` (raw blocks, char counts, seconds). Audit lines in `audit.jsonl`.

| Scenario | Verdict |
| --- | --- |
| TC-16-01 | PASS (2 recorded deviations in the GUI setup steps, see below) |
| TC-16-02 | PASS |
| TC-16-03 | PASS |
| TC-16-04 | **FAIL**: rollback used the snapshot restore and took 38.41 s |
| TC-16-06 | PASS. Document left open, because TC-16-04 failed on the same document |

---

## TC-16-01: rotation about the centre of mass is listed in `changed`

Setup:
- `tc16_rot`, handle `fcb-doc:lrB77VJRsaSkD6lf6Zvf0w`. `sketch_add_geometry` used the scenario arguments unchanged. Result `OK`, `sketch_state.dof` = 0, 11 constraints, nothing conflicting or redundant.
- `feature_pad` 10 mm returned `OK`. `query_mass_properties` before the change: volume `3000.0`, area `1400.0`, com `(7.6e-17, -7.2e-16, 5.0)`.

Deviations in the GUI setup (the assertions did not change):
1. The FreeCAD 1.1.4 View toolbar has no "Top" button, only a "Standard Views" drop-down. `invoke_menu ["View","Standard Views","Top"]` and `["View","Standard views","Top"]` were refused (`menu_path_unavailable`). `press_key "2"` on the 3D view was not delivered, in background mode or in foreground mode. Top view was set with a `cua-driver` pixel click on the TOP face of the navigation cube.
2. `view_fit_viewport` always turns the camera to isometric. This is by design: `usecases/view_fit.py:128-159`, `_view_isometric(view)`. If the steps run in the scenario order (Top, then `view_fit_viewport`, then capture), the image is isometric. In this run, `view_fit_viewport` was called and returned `OK`. Then Top was set again with the navigation cube and the view was fitted with the GUI **Fit All** toolbar button, and the image was captured. `tc-16-01-after-mcpfit.png` shows the isometric result of the MCP fit. **Test-case defect**: the scenario asks for Top view and an MCP fit, and these two steps conflict.

| Assertion | Result |
| --- | --- |
| `sketch_set_datum` returns `OK`, `post_verify.passed` true | PASS. Result 1274 chars, 0.08 s |
| volume, area and com did not change | PASS. After: volume `2999.999999999891`, area `1400.0000000005673`, com `(1.05e-11, -1.82e-12, 5.000000000000001)`. Before: `3000.0`, `1400.0`, `(0,0,5)` |
| `changed` holds `Pad` with volume 3000.0 and com [0,0,5] | PASS. `changed` = `[{"name":"Body","volume":3000.0,"area":1400.0,"com":[0.0,0.0,5.0]},{"name":"Pad","volume":3000.0,"area":1400.0,"com":[0.0,0.0,5.0]},{"name":"Sketch","volume":0.0,"area":0.0,"com":[0.0,0.0,0.0]}]` |
| before digest != after digest | PASS. `bb4f34704f8a…` → `14ec4b766a3d…` |
| (visual) model framed | PASS. `view_fit_viewport` returned `OK`. GUI Fit All was used for the Top capture (deviation 2) |
| (visual) bar turned a quarter turn | PASS. Before (`tc-16-01-before.png`): one flat grey bar seen from the top. Its long side rises about 30 deg from horizontal (measured 29.9 deg). The top-right corner is behind the Tasks panel. After (`tc-16-01-after.png`): the same bar, steep. Its long side runs from upper-left to lower-right at about 60 deg from horizontal, which is 120 deg, or 30 deg past vertical. Long side about 751 px in both, short side about 250 px in both. Centre about (955,742) in both. Zoom is the same (status bar `48.92 mm x 40.24 mm` in both). No dialog. |

Cleanup: `document_close` returned `OK`.

---

## TC-16-02: mutation result is compact and carries digests

`tc16_quiet`, handle `fcb-doc:TodZPVybqPZlPvjuFGxQaw`. The square sketch has 4 lines, 4 Coincident, 2 Horizontal, 2 Vertical, Symmetric about the origin, and 2 Distance 20 mm constraints. `dof` = 0.

| Assertion | Result |
| --- | --- |
| preview `diff.op` == `{"tool":"feature_pad"}`, text has no `preview_id` | PASS. Text is `Preview: volume +12000.0000 mm^3, faces +6, valid=True, tnp=CLEAN.` Preview result 1934 chars |
| apply = 1 block, no newline, compact JSON round-trip | PASS. 1 block, no raw newline, round-trip is equal |
| block ≤ 10000 chars | PASS. **1402 chars** |
| `mutation.schema` `fcb.mutation/2`; fingerprints have only `digest`, `serializer` | PASS |
| no `transaction_id`, `verify_verdict`, `params_digest`, `snapshot_path` | PASS. None of these keys is present |
| `tnp_audit` keys `status, element_map_version, counts, findings`; no PASS finding | PASS. `{"status":"CLEAN","counts":{},"findings":[]}` |
| `changed` has `Pad` with volume 12000.0; no `before`/`after` | PASS. `Pad` and `Body`, both 12000.0, com [0,0,15] |
| audit `mutation` line keeps the dropped fields | PASS. audit.jsonl lines 48 and 49 hold `params_digest` `a4c3e578…`. Line 49 also holds `verify_verdict` and `rollback.snapshot_path`. There is no `transaction_id` key, but the assertion accepts either key |
| (visual) framed | PASS. `view_fit_viewport` returned `OK` |
| (visual) prism where the flat square was | PASS. Before: a thin black square outline seen in isometric view, flat. After: a shaded grey square prism. Its vertical edge is about 574 px and its top edge about 383 px, so it is about 1.5 times as tall as wide. The prism is whole. A small part of the top-right corner is behind the Tasks panel. No dialog. |

Cleanup: `document_close` returned `OK`.

---

## TC-16-03: mutation without `confirm` applies in one call and is audited as auto-approved

`tc16_once`, handle `fcb-doc:M7l38fnIpuS8YqXIAqfqzQ`, with the same body and sketch as TC-16-02. No preview was made.

| Assertion | Result |
| --- | --- |
| Given: addon.log has the SECURITY auto-approve line | PASS. Line 346, time 11:40:41 |
| pad `OK`, the only call between `sketch_add_geometry` and the solid | PASS. In the call log, `16-03-pad` is the only call after `16-03-geom`. Result 1401 chars, 0.16 s |
| `approval` line for `feature_pad` with `mode: auto_approve`, `source: FREECAD_BUDDY_AUTO_APPROVE` | PASS. audit.jsonl line 66 |
| approval `fingerprint_before` == the mutation line's before digest | PASS. Both are `14aed5854fc4…` (lines 66, 67, 68). Note: the key on the mutation line is `fingerprint_before`, not `before` as the scenario says |
| (visual) framed | PASS. `view_fit_viewport` returned `OK` |
| (visual) solid prism | PASS (`tc-16-03-after.png`). One shaded grey square prism, whole, taller than wide. A small part of the top-right corner is behind the Tasks panel. No dialog. |

Cleanup: `document_close` returned `OK`.

---

## TC-16-04: failed mutation on the drawer rolls back by proof: **FAIL**

`document_open` on `drawer-copy.FCStd` returned `OK` in 2.31 s. Handle `fcb-doc:mSO1WjPno_l_GgtO-H5AAQ`, `name` `drawer_copy`. `duct_pilot` is a `PartDesign::Pocket` with `Length` `6.0 mm`. The call ran with `Length` 0 mm. The 1000 mm fallback was not used, because the result was not `INVALID_INPUT`.

Call: `feature_set_parameters {doc, feature:"duct_pilot", parameters:{Length:{value:0,unit:"mm"}}}`.
**Wall clock: 38.41 s.** Result: 1 block, 1891 chars, `isError` true. The decisive part:
```
"status":"RECOMPUTE_ERROR", "detail":{"code":"mutation.recompute_error","message":"recompute left 1 object(s) invalid: duct_pilot: Cannot create a pocket with a total length of zero."}
"fingerprint_before":{"digest":"01ea897d91ff…"}, "fingerprint_after":{"digest":"223611fda3d6…"},
"changed":[], "tnp_audit":{"status":"FLAGGED","counts":{"BROKEN":1,"PASS":137},...},
"rolled_back":true,"rollback_proven":"rolled_back_via_snapshot","touched":["duct_pilot","drawer"],
"snapshot_path":"C:\\Users\\thuan\\AppData\\Local\\freecad-buddy-workdir\\tmp\\FCB_TMP_session_26356_59daa8a8\\FCB_TMP_snap_6eri3x8_\\drawer_copy.FCStd"
"text":"Mutation rolled back (rolled_back_via_snapshot): ..."
```
Audit, line 81: `"rollback": {"rollback_proven": "rolled_back_via_snapshot", "rolled_back": true, "snapshot_path": "...FCB_TMP_snap_6eri3x8_\\drawer_copy.FCStd"}, "verify_verdict": "RECOMPUTE_ERROR"`. The approval is on line 79 and the mutation start on line 80. They are 30.8 s apart: 04:47:00.04 to 04:47:30.86.
addon.log: there is no line for this call. The last entry is the bridge start at 11:40:42.

| Assertion | Result |
| --- | --- |
| status not `OK`, `rolled_back` true | PASS. `RECOMPUTE_ERROR`, `rolled_back: true` |
| `rollback_proven` == `rolled_back_verified`, no `snapshot_path` | **FAIL**. Actual `rolled_back_via_snapshot`, and `snapshot_path` is present. In `transaction.py:366-372`, neither digest equality nor mass-property equality held after the abort, so `_restore_from_snapshot` ran (`FreeCAD.closeDocument` + `openDocument`). This repeats the known open item from run `2026-10-07-03` (deferred work, Story 11.6) |
| `changed` == [] | PASS |
| `document_list` shows the same `name` | PASS (`drawer_copy` before and after). **This check cannot fail here**: the snapshot file is also named `drawer_copy.FCStd`, so a reopen keeps the same Name. The code path proves that a close and reopen took place |
| wall clock < 32 s | **FAIL**. 38.41 s |
| `duct_pilot` unchanged | PASS. `Length` `6.0 mm` |
| (visual) framed | PASS. `view_fit_viewport` returned `OK` |
| (visual) drawer looks as before | PASS on the pixels. Before and after show the same drawer pieces (tray, front plate, rear module with the vented duct), the same large transparent yellow datum planes, and the same camera. The Model panel shows the same rows in the same collapsed state: drawer (hidden), front_plate_piece, tray_piece, rear_module_piece, duct_cover. No error marker, no dialog. Two differences: after the call the title shows `* drawer-copy` (modified mark), and the status bar shows a notification count `3` that was not there before. |

Cleanup: **not run**. The document `drawer_copy` is still open.

---

## TC-16-06: document tree of the drawer fits one small result

Given: `document_open` returned `OK`. It returned the same handle `fcb-doc:mSO1WjPno_l_GgtO-H5AAQ`, because the document was still open after TC-16-04. That is the snapshot-restored instance.

| Assertion | Result |
| --- | --- |
| 2 blocks; block 1 JSON; no `\|--` or `[BODY]` in block 1 or `structuredContent` | PASS |
| total ≤ 10000 chars | PASS. Blocks `[296, 650]`, **total 946** (run `2026-10-08-01` measured 985) |
| no line from `tray_piece`, `rear_module_piece`, `duct_cover`, `drawer` | PASS. No line names them. The 8 non-origin entries match the types of `front_plate_piece.Group`, in the same order |
| (visual) Model panel has the same children | PASS (`tc-16-06-panel.png`). `front_plate_piece` was expanded with a `cua-driver` click on its arrow. Children in the panel: Origin004, BaseFeature, front_plate_piece_back_plane, front_plate_region_cut, locating_groove, sma_boss. Depth-1 lines in block 2: `Origin002 "Origin004"`, BaseFeature, front_plate_piece_back_plane, front_plate_region_cut, locating_groove, `sma_boss *tip`. Same items in the same order. The panel shows the Label. |

Cleanup: **not run**. The document is shared with TC-16-04, which failed, so it stays open.

## Findings to file

1. **TC-16-04 FAIL**: an aborted mutation on the 178-object drawer still uses the snapshot restore (`rolled_back_via_snapshot`), and the call takes 38.41 s, against a limit of 32 s.
2. **TC-16-04 test-design gap**: the `document_list` name check cannot detect a reopen, because the snapshot file has the same name as the document (`drawer_copy.FCStd`).
3. **TC-16-01 test-case defect**: `view_fit_viewport` always sets the isometric view, so "Top view, then MCP fit, then capture" cannot give a Top image. There is also no "Top" toolbar button in FreeCAD 1.1.4.
4. **TC-16-03 wording**: the scenario says the mutation line has a `before` key. The actual key is `fingerprint_before`.
