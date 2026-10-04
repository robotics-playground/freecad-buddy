# TC-12-13 — Closing a document in the GUI invalidates its handle cleanly

Verdict: **PASS** on product behaviour (F-25 fixed). Three Thens carry a test-case defect.

## Setup

- Start: `document_list` returned 0 documents. FreeCAD pid `13352`, window_id `4135230`.
- B = `cylinder-r5-h20` golden, handle `fcb-doc:niG1MyZiOaIypbyxEU0vJA`, opened first.
- B ships with `Cylinder` hidden. GUI step: select `Cylinder`, then click the property-view `Visibility` checkbox (foreground pixel click). Two earlier attempts with `space` on the TreeItem did nothing (`effect: unverifiable`). After the click, `query_tree_summary` B reported `visibility: true`. B is now modified (`*`).
- A = `box-10-20-30` golden, handle `fcb-doc:EeVzBbYtBtIBh3fkspkBoA`, opened last (active document).
- Given: `document_list` 2 entries; `query_tree_summary` A and B both `OK`; B `Cylinder` volume 1570.7963267948965 mm^3.
- When: `document_list` recorded both handles. This is the last MCP call before the GUI close.

## GUI close

- `tc-12-13-tree.png` (deleted by the scenario cleanup) showed both document rows; A was active.
- Background click on A row token `s00000873:197`: `effect: unverifiable`, row not selected. A was already active.
- `invoke_menu ["File","Close"]` at 18:18:13: route `accessibility`, foreground. No save prompt: `list_windows` showed only the main window, title `* cylinder-r5-h20 - FreeCAD 1.1.4`.
- First MCP call on handle A came at 18:18:30, with no `document_list` before it.

## Per-Then results

| Then | Result | Actual |
| --- | --- | --- |
| GUI closed it (`verify_state` exists:false) | TEST-CASE DEFECT | `verify_state` returned `predicate 0 element.exists=false is unsupported because element snapshots are not exhaustive`. This is not `satisfied`. The outcome is confirmed by other evidence: UIA TreeItems after the close are `['cylinder-r5-h20','Cylinder']` and no element label contains `box-10-20-30`. The console shows `Gui.runCommand('Std_CloseActiveWindow',0)` and `App.closeDocument("box_10_20_30")`. |
| Every stale read returns INVALID_INPUT | PASS (product) / TEST-CASE DEFECT | `query_tree_summary`: `INVALID_INPUT "unknown or stale document handle: fcb-doc:EeVzBbYtBtIBh3fkspkBoA"`. `query_screenshot`: same. `query_mass_properties {doc}` as written: MCP schema refusal `Input validation error: 'object' is a required property`. The TC omits the required `object` argument. With `object:"Box"`: `INVALID_INPUT` with the same message. No `RECOMPUTE_ERROR`, no `WORKER_CRASHED`. |
| Stale close is a clean refusal | PASS | `document_close`: `INVALID_INPUT "unknown or stale document handle: ..."` |
| No crash, no hang | PASS | `Get-Process freecad` returns pid 13352. Each stale call took 0.006–0.017 s. |
| List no longer names A | PASS | `document_list`: 1 entry, `fcb-doc:niG1MyZiOaIypbyxEU0vJA` `cylinder-r5-h20` |
| B still works, original volume | PASS (product) / TEST-CASE DEFECT | `{doc}` as written: same schema refusal (`object` is required). With `object:"Cylinder"`: `OK`, volume 1570.7963267948965 mm^3, the same as the Given value. |
| Listener intact | PASS | `query_capabilities` returned `OK`, freecad_version 1.1.4 |
| (visual) model is framed | PASS | `view_fit_viewport` B: `OK fitted:true`, framing ratio 0.9506 |
| (visual) GUI shows B alone | PASS | `tc-12-13-after.png`: the tree shows only `cylinder-r5-h20` > `Cylinder` with the eye icon on. There is no `box-10-20-30` row, and the only tabs are `Start` and `cylinder-r5-h20 : 1*`. There is no save prompt or error popup. The 3D view shows the whole grey cylinder in isometric view, centred and framed with margin. |

## Against RUN-CONTEXT (F-25)

The fix is confirmed. The first use of the stale handle after a GUI close returns `INVALID_INPUT "unknown or stale document handle"`, with no `document_list` before it. The previous run (`2026-10-03-04`) returned `RECOMPUTE_ERROR "Cannot access attribute 'Objects' of deleted object"` here.

## Test-case defects

1. `query_mass_properties {doc}` omits the required `object` argument, in both the stale read and the B check.
2. `verify_state` with `exists:false` is unsupported by `cua-driver`, so it can never return `satisfied`. Use the UIA tree read and the screenshot instead.
3. The TC does not say how to open the two documents. The golden models ship with their objects hidden, so the visual Then needs a visibility toggle in setup.

## Cleanup

The scenario cleanup ran. `tc-12-13-tree.png` was removed as the TC says. `document_close` B returned `OK` and `document_list` returned 0 documents. `tc-12-13-cleanup.png` shows the Start page, an empty Model tree, and the title `FreeCAD 1.1.4`. `git status benchmarks/` is clean.

## Evidence

`tc-12-13-mcp.jsonl` (raw envelopes with elapsed times), `tc-12-13-gui.txt`, `tc-12-13-after.png`, `tc-12-13-cleanup.png`, `tc-12-13-handles.json`, `tc-12-13-run.py`
