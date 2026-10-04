# TC-02 results — run 2026-10-04-01

Host: GUI through H2 proxy `:8765` (FreeCAD 1.1.4, pid 13352, window 4135230), except the TC-02-15 non-string `doc` leg (inline host, `FCB_PYTHON`, FreeCAD 1.1.3, repo `src` on `PYTHONPATH`).
Calls: scratch batch client (same as `fcb.py`, plus records `isError`). Raw envelopes in `tc-02-MM-mcp*.json`.

| Scenario | Verdict |
| --- | --- |
| TC-02-01 | PASS (1 test-case defect, F-02) |
| TC-02-05 | PASS |
| TC-02-13 | PASS against AC2 (3 test-case defects, F-02) |
| TC-02-15 | PARTIAL (inline-host message differs) |
| TC-02-18 | PASS |

## TC-02-01 — create, list, save, close round trip

| Then | Result | Actual |
| --- | --- | --- |
| Handle opaque | PASS | `fcb-doc:cUZdBT9RsRkG82VTwoZJ6g`, Name `uat_roundtrip` |
| Create names doc | PASS | `doc`, `name`, `label` = `uat-roundtrip` |
| List transient before save | PASS | one entry, same handle, `transient: true` |
| Bare save refused | PASS | `INVALID_INPUT` "document has no save target; call document_save with a 'path' first" |
| Save-as writes file | PASS | 1727-byte file, `saved: true`; label now `tc-02-01-uat-roundtrip` (AC2) |
| Not transient after save | PASS | `transient: false` |
| Close releases handle | PASS | `closed: true`, then `0 open document(s).` |
| File survives close | PASS | file present |
| (visual) framed | PASS (GUI path) | `view_fit_viewport` → `SPEC_FAILED` "no visible shape-bearing objects to measure" (empty doc). Fit All toolbar by token, `route: accessibility` |
| (visual) window | TEST-CASE DEFECT | `tc-02-01-after.png`: one 3D view `tc-02-01-uat-roundtrip : 1`, empty viewport, one tree entry, no leftover view, no dialog. Title reads `tc-02-01-uat-roundtrip`, not `uat-roundtrip`. Product matches AC2 (save-as sets label to file stem). |

Cleanup done.

## TC-02-05 — query_tree_summary

Doc built over MCP (Body > Sketch > Pad 20x10x5), `tc-02-05-setup.txt`.

| Then | Result | Actual |
| --- | --- | --- |
| Given Body with children | PASS | depth 3 Body `children` [Pad, Sketch] |
| depth 1 no children | PASS | Body `children_count: 3`, no `children`, `returned_nodes 1` = 1 root |
| depth 3 expands | PASS | `returned_nodes 4` > 1, `children` present |
| root re-roots | PASS | single `Body`, `returned_nodes 3` |
| unknown root | PASS | `INVALID_INPUT` "unknown object: NoSuchObject" |
| `types` allow-list | PASS | only `Pad` (Pad nested in Body returned, F-01) |
| `exclude_types` replaces default | PASS | `filters_applied.exclude_types` = `["Sketcher::SketchObject"]`; Origin, 3 axes, 3 planes, `App::Point` shown |
| default excludes datums | PASS | `["App::Plane","App::Line","App::Point","App::Origin"]` |
| `renderable_only` | PASS | only `Pad` |
| `visible_only` | PASS | Pad hidden by tree click + Space (foreground; background Space dropped). With filter: Body > Sketch, Pad absent (subtree dropped, F-01). Without: Pad `visibility false` present. `tc-02-05-pad-hidden.png` |
| `name_pattern` | PASS | only `Pad` |
| AND-stack | PASS | `[Pad]`, subset of both |
| unknown filter key | PASS | `isError`, no envelope: "Additional properties are not allowed ('unknown_filter' was unexpected)" |
| (visual) restore + fit | PASS | Space restores Pad; `view_fit_viewport` OK |
| (visual) before vs after | PASS | both show the same whole grey slab, same camera, no clip. Only difference: tree row expanded in after. |

Cleanup: none in TC; closed the built doc.

## TC-02-13 — Unicode label round trip

| Then | Result | Actual |
| --- | --- | --- |
| Create OK | PASS | handle `fcb-doc:5z_ti-o66n03P3nhWz9-FA` |
| Label survives create | PASS | equal to input |
| Name sanitized, label not | PASS | Name `測試_ドキュメント___with_spaces_and_a_deliberately_long_label_for_width` (emoji and spaces → `_`) |
| Listing unmangled | PASS | label equal; `text` has no `?` or `\u` |
| Label survives save + reopen | TEST-CASE DEFECT | reopened label `tc-02-13-uat-unicode`. Save result reported `label` + `path` (AC2). |
| No mojibake byte-for-byte | TEST-CASE DEFECT | compare false for same reason (label replaced, not corrupted) |
| File reads back | PASS | `total_objects 0` |
| (visual) framed | PASS (GUI path) | MCP fit `SPEC_FAILED` (empty doc); Fit All toolbar `route: accessibility` |
| (visual) glyphs on screen | TEST-CASE DEFECT | `tc-02-13-after.png`: tree and tab show ASCII `tc-02-13-uat-unicode`. CJK/emoji rendering in the tree was not observable, so it is not verified. |

Cleanup done.

## TC-02-15 — unknown handle refused

Live doc: `box-10-20-30` opened first, but it ships hidden (`tc-02-15-before-box-hidden.png`). Replaced by `cylinder-r5-h20` + View > Visibility > Show All Objects (also ships hidden). Note: this invoke_menu left the View menu popups open until the end of TC-02-18 (separate windows, not in window captures); closed with Escape before final capture.

| Then | Result | Actual |
| --- | --- | --- |
| 6 read-only refuse | PASS | each `INVALID_INPUT` "unknown or stale document handle: fcb-doc:not-a-real-handle" |
| 6 lifecycle refuse | PASS | same |
| Envelope, not protocol | PASS | `schema fcb.result-envelope/1`, `detail.code INVALID_INPUT` on all 12 |
| No crash | PASS | caps OK; grep access violation/segfault/swig = 0 |
| Live handle OK | PASS | `query_tree_summary` OK, `Cylinder` |
| Omitted `doc` schema reject | PASS | `isError`, "'doc' is a required property" |
| Inline non-string `doc` | FAIL | expected envelope `INVALID_INPUT` "doc handle must be a string"; actual `isError` protocol reject "Input validation error: 12345 is not of type 'string'" (`tc-02-15-inline.txt`). Rejected before dispatch, but the guard in `mcp_server.py:195` is not reached. Same as run 2026-10-03-04. Probably a stale expectation. |
| (visual) Fit All toolbar | PASS | `route: accessibility` |
| (visual) before = after | PASS | `tc-02-15-before.png` and `-after.png` byte-identical: one grey disc (cylinder, top view), whole, one tree entry, view still open, no dialog |

Side note (F-30): the inline host start sweep removed 1 entry, `FCB_TMP_session_38120_eb745ce0/` in repo `freecad-buddy-workdir/tmp`; pid 38120 is not running. Matches AD-25.

## TC-02-18 — save to unwritable path

`document_open` of the cylinder returned the same handle as TC-02-15 (`fcb-doc:5Y5mp3h-D_To0fYnBHhQHA`); FreeCAD reuses the open doc.

| Then | Result | Actual |
| --- | --- | --- |
| Read-only save refused | PASS | `INVALID_INPUT` "save target is not writable: …/tc-02-18-readonly.FCStd" |
| Read-only file identical | PASS | sha256 `94969ac4…3136` before and after |
| Missing dir refused | PASS | `INVALID_INPUT` "save folder does not exist: …\tc-02-18-no-such-dir"; no dir created |
| Directory path refused | PASS | `INVALID_INPUT` "save path is a directory, not a file: …/evidence"; still a dir |
| Golden untouched | PASS | `0ce46355…8617` = `git show HEAD:` hash |
| Handle usable | PASS | `tree[0].name` `Cylinder`; label stayed `cylinder-r5-h20` after the 3 refusals (F-03) |
| Writable save OK | PASS | `saved: true`, 5325-byte file, label `tc-02-18-writable` |
| Nothing crashed | PASS | caps OK; no traceback after bridge start 18:01:23 (3 older ones are from 16:13–18:01:03) |
| (visual) fit | PASS | `view_fit_viewport` OK `fitted: true` |
| (visual) window | PASS | `tc-02-18-after.png`: one whole grey cylinder, iso, `Cylinder` tree row, title `* tc-02-18-writable`, no dialog. Title has `*` after the save. |

Cleanup done. Final state: 0 documents, main window only (`tc-02-final-state.png`).
