# TC-08-06 results — run 2026-10-04-01

Verdict: **PASS** (product). No product defect. Three Thens/Givens are test-case defects: the scenario text predates F-20 (Story 10.1) and the MCP input schema.

Doc handle: `fcb-doc:zH9I9sszJQ3xgYqPkGA-vw` (label `TC0806`). Start: `document_list` → 0 documents. FreeCAD pid `13352`, window_id `4135230`. Every mutation used a real `preview_dry_run` token.

## Preconditions

| Check | Result |
| --- | --- |
| `:8765` LISTENING | yes, pid 39356 |
| `auto_approve: false` | field absent from 1.1.4 `query_capabilities`; real tokens used |
| Golden model present | `box-10-20-30.FCStd` present |
| No stale preview TempDocs | DEVIATION: `%TEMP%\FCB_TMP_prev_rtoduji3` exists, created 2026-09-13, access denied. Pre-existing leftover, not from this host (AD-25 uses `<workdir>/tmp`). Left in place. No effect on this scenario |
| `cua-driver` sees `QOpenGLWidget` and `Fit All` | yes |

## Per-step table

| Step | Result | Actual | Evidence |
| --- | --- | --- | --- |
| Given: sketch fully constrained via `query_sketch_info` | TEST-CASE DEFECT | `query_sketch_info` has no `fully_constrained` field (returns only `sketch`, `geometry`, `constraints`). Fact confirmed by `verify_sketch` → `dof: 0`, `fully_constrained: true`, and `query_object` → `FullyConstrained: true` | `tc-08-06-setup.txt`, `tc-08-06-given-constrained.txt` |
| Given: undo available | PASS | `document_undo {doc}` → OK, undid `buddy: add geometry to Sketch`. Geometry re-applied with a new token; `verify_sketch` above ran after the re-apply | `tc-08-06-setup.txt` |
| Given: framed before capture | PASS (fallback) | `view_fit_viewport` → `SPEC_FAILED` `view_fit.unverified` "no visible shape-bearing objects to measure". GUI Fit All by `element_token` → `route: "accessibility"`; console shows `Std_ViewFitAll` | `tc-08-06-fitall-before.txt`, `tc-08-06-before.png` |
| Given: before capture | PASS | Flat 20x20 square sketch outline, isometric, centred. Tree: `TC0806` > `Body` | `tc-08-06-before.png` |
| When: pad, keep both forms | done | `fingerprint_before.digest` = `80cc3021...b670da` (pad 1); pad 2 record digest `646a68eb...df63f5` | `tc-08-06-when.txt` |
| Then: string form `matches_pre_op: true` | TEST-CASE DEFECT | `matches_pre_op: false`. Text: "Undid 'buddy: feature_pad Pad' on TC0806: the digest differs from the expected one on byte comparison; pass the whole FingerprintRecord as expect_fingerprint to also compare the geometry (6c69192e6d47 -> 646a68eb84ba)." Product matches RUN-CONTEXT F-20: false kept, byte comparison stated, record form recommended, no "did NOT restore". Cause: Sketch `brep_sha256` changes after Pad consumes it (`4463fd9b...` → `731300a9...`), same massprops | `tc-08-06-when.txt` |
| And: record form `matches_pre_op: true` | PASS | `true`. Text: "Undid 'buddy: feature_pad Pad' on TC0806: restored the pre-op state (6c69192e6d47 -> 646a68eb84ba)." | `tc-08-06-when.txt` |
| And: both fingerprints 64-hex and differ | PASS | before `6c69192e6d47200e550fdbf60ae3172ed820e834cb172ed94fe43e309273faa8`, after `646a68eb84ba29b0d4696e0c23a6465d98837c8156e5f5223a27972919df63f5` (both undos) | `tc-08-06-when.txt` |
| And: `undone` = `buddy: <pad label>` | PASS | `buddy: feature_pad Pad` (all three pad undos) | `tc-08-06-when.txt` |
| And: text contains `restored the pre-op state` | PASS (record) / TEST-CASE DEFECT (string) | Record form: yes. String form: no, by design of F-20 | `tc-08-06-when.txt` |
| And: no expectation → `null` | PASS | `matches_pre_op: null`. Text: "Undid 'buddy: feature_pad Pad' on TC0806: no pre-op digest supplied to compare against (6c69192e6d47 -> 646a68eb84ba)." Run on a third pad | `tc-08-06-when.txt` |
| And: `restored_objects` | PASS | `["Body","Origin","X_Axis","Y_Axis","Z_Axis","XY_Plane","XZ_Plane","YZ_Plane","Origin001","Sketch"]`; no `Pad` | `tc-08-06-when.txt` |
| And: `expect_fingerprint: 42` refused | TEST-CASE DEFECT | Refused, not a non-match: `isError` "Input validation error: 42 is not of type 'string', 'object'" (MCP input schema). Expected product text "expect_fingerprint must be a fingerprint digest string or a FingerprintRecord, got int" is not reachable. Undo did not run: tree still has `Pad` | `tc-08-06-mcp.jsonl`, `tc-08-06-when.txt` |
| And (visual): framed | PASS (fallback) | `view_fit_viewport` → `SPEC_FAILED` same reason; GUI Fit All → `route: "accessibility"`, console `Std_ViewFitAll` | `tc-08-06-fitall-after.txt` |
| And (visual): restored | PASS | After image shows the same flat square outline, same camera, no solid. Viewport crop pixel-identical (diff bbox `None`); only whole-window diff is the Redo toolbar icon, now enabled | `tc-08-06-before.png`, `tc-08-06-after.png`, `tc-08-06-pixeldiff.txt` |

## Notes

- Sequence after the record-form undo: pad 3 applied, then `expect_fingerprint: 42`, then undo with no expectation. This keeps the final state at sketch only for the visual check.
- `view_fit_viewport` returns `SPEC_FAILED` on a sketch-only document. The scenario allows the GUI fallback. Not counted as a failure.
- Cleanup done: `document_close` → OK; `document_list` → 0 documents; `tc-08-06-cleanup.png` shows the Start page only.
