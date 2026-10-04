# TC-05-14 results — run 2026-10-04-01

Verdict: **PASS** (degraded single-build form). Two-build comparison NOT RUN: only FreeCAD 1.1.4 (`serializer: exportBinary`) is installed.

Doc handle: `fcb-doc:6QAFmRx0Rc7ei4fgnJD64w` (label `TC0514`). Start: `document_list` → 0 documents.

| Step | Result | Actual | Evidence |
| --- | --- | --- | --- |
| Given: Pad volume 12000.0 | PASS | `query_mass_properties Pad` → volume 12000.0 mm^3, bbox 20x20x30 | `tc-05-14-setup.txt`, `tc-05-14-given.txt` |
| Given: second build with other serializer | NOT RUN | Only 1.1.4 with `exportBinary` installed | — |
| Given: framed and captured before | PASS | `view_fit_viewport` → OK; screenshot shows one grey prism in iso view, about 1.5x taller than wide | `tc-05-14-before.png` |
| When (degraded): `document_undo {expect_fingerprint:{objects:[], digest:"0"*64}}` | refused | `INVALID_INPUT` "expect_fingerprint record: cannot compare fingerprints: serializer tag missing/mismatch (None vs 'exportBinary')"; `structured_content: {}` | `tc-05-14-when.txt`, `tc-05-14-mcp.jsonl` |
| Then: tag on every record | PASS | `feature_pad` `fingerprint_before.serializer` = `"exportBinary"` | `tc-05-14-setup.txt` |
| And: same tag in one bracket | PASS | before = after = `"exportBinary"` | `tc-05-14-setup.txt` |
| And: missing `objects` refused | PASS | `document_undo {expect_fingerprint:{digest:"abc"}}` → `INVALID_INPUT` "expect_fingerprint record must carry an 'objects' list; got keys ['digest']" (exact) | `tc-05-14-when.txt` |
| And: CONDITIONAL two-build raises | NOT RUN | No second build. Single-build equivalent (tagless record) raised the same `cannot compare fingerprints: serializer tag missing/mismatch` error | `tc-05-14-when.txt` |
| And: no quiet "not equal" | PASS | Both refusals have empty `structured_content`: no `matches_pre_op`, no `rolled_back` | `tc-05-14-when.txt` |
| Extra: undo did not run | PASS | GUI Python console: `UndoCount` 4 before and after, `UndoNames[0]` = `buddy: feature_pad Pad` both times, same 11 objects; MCP tree and Pad volume unchanged | `tc-05-14-undoprobe.txt`, `tc-05-14-when.txt` |
| And (visual): framed | PASS | `view_fit_viewport` → OK | `tc-05-14-when.txt` |
| And (visual): window unchanged | PASS | Before and after both show the same grey prism, whole, no dialog, no removed feature. Viewport crop is pixel-identical (diff bbox `None`) | `tc-05-14-before.png`, `tc-05-14-after.png`, `tc-05-14-pixeldiff.txt` |

Product result against RUN-CONTEXT F-12: matches. Malformed `expect_fingerprint` → `INVALID_INPUT`, undo not run.

## Notes

- Test-case text is out of date: it says "Only FreeCAD 1.1.1 is installed"; the installed build is 1.1.4. No effect on the result.
- Precondition `query_capabilities` reports `auto_approve: false`: the field is not in the 1.1.4 envelope. Real `confirm` tokens from `preview_dry_run` were used for every mutation.
- Operator incident: the first attempt to type the `UndoCount` probe into the Python console went to the 3D view (keys `0 5 1 4` ran Isometric/Bottom/Front/Rear views, and a click selected `Pad.Face3`). No document change (UndoCount 4, same objects). View restored to isometric, selection cleared, refit, and `tc-05-14-before.png` recaptured before the When step. Earlier captures: `tc-05-14-before-initial.png`, `tc-05-14-misstep-view.png`.
- Cleanup done: `document_close` → OK; `document_list` → 0 documents.
