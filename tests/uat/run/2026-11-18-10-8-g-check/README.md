# Story 10-8-g check run (not a gate run)

This folder records the check of the Story 10-8-g test-case fixes. It is not a UAT gate run and grades no scenario for Gate 1. Container `fcb-desktop`, FreeCAD 1.1.4, MCP only on `:18765`.

## Runner

`runner/`: `tc-02-15`, `tc-02-17`, `tc-03-03`, `tc-03-20`, `tc-07-03`, `tc-09-12`, `tc-13-04` in one run. Result: 7 ESCALATE (agent checks only), 0 FAIL, 0 run errors. Every scripted `expect` of the seven scenarios passed, including the `query_tree_summary` text reads of TC-02-15 and TC-09-12 and the `Invalid project file` prefix of TC-02-17. The runner cannot open Sketcher edit mode or press GUI buttons, so its captures show the object view. Agent reads of `runner/captures/`:

- TC-02-15, TC-02-17: unframed top view of `box-10-20-30` (the runner cannot press Fit All; these scenarios frame by GUI in the test case). One document, one tab, no dialog.
- TC-09-12: whole box, iso view, no dialog.
- TC-03-03, TC-03-20: whole thin plate in iso view; TC-03-20 shows the circle on the top face as a black wire.
- TC-07-03: one black line in the object view (edit mode is not entered by the runner).
- TC-13-04: whole 40 x 40 x 10 plate with one through hole, iso view, same silhouette as the MCP render.

## Agent-driven steps (MCP `freecad-buddy-docker`, `cua-driver` through `fcb_cua.sh`)

Camera quaternion read with `script_exec ... getCameraOrientation().Q`.

| Case | Step | Measured result | Capture read |
| --- | --- | --- | --- |
| TC-03-03 | `setEdit(BossProfile)` | camera `[0.0, 0.0, 0.0, 1.0]` (top view) | |
| TC-03-03 | press `Isometric` push button by token, press `Fit All`, wait 8 s (an 8 s wait is the measured upper bound: the capture was stable at 6 s and at 8 s) | camera `[0.425, 0.176, 0.34, 0.82]`, still in edit mode | `evidence/tc-03-03-after.png`: thick grey plate, red and green axes along the top face edges, origin on the top face corner, raised above the plate bottom; the Tasks panel hides the right end of the plate |
| TC-03-20 | Given: `setEdit`, `Isometric`, `Fit All`, 8 s, capture | camera iso; `resetEdit` then restores `[0.0, 0.0, 0.0, 1.0]` | `evidence/tc-03-20-before.png`: whole thin plate, green circle R5 with labels, magenta external line along the bottom edge, `Fully constrained` |
| TC-03-20 | `feature_set_parameters Length 30` | `SPEC_FAILED`, `BossProfile.AttachmentSupport REPOINTED`, `rolled_back` true, volume `12000.0` | |
| TC-03-20 | `sketch_set_datum BossRadius 4`, `setEdit` (camera `[0,0,0,1]` again), `Isometric`, `Fit All`, 8 s | OK | `evidence/tc-03-20-after.png`: same plate and camera, circle smaller (`BossRadius = R4 mm`), magenta line on the plate edge, no dialog |
| TC-07-03 | after the duplicate Horizontal (`RECOMPUTE_ERROR`, rolled back): `setEdit(Sketch)`, `Fit All`, 8 s | `Fully constrained` | `evidence/tc-07-03-after.png`: green segment from the origin along the lower edge, `10 mm` label, horizontal glyph, three constraints listed; the segment has no height, so Fit All puts it on the lower edge |
| TC-07-05 | `Show All`, no fit: `export_step` AP242 | `text` = `STEP export written -> <path>.` + blank line + `Warning: the model does not fully fit the live viewport ...`; `framing.fits` false | |
| TC-07-05 | `view_fit_viewport` first, then `export_step` AP242 and AP214 | `text` equals `STEP export written -> <path>.` exactly; `framing.fits` true, ratio 0.95 | |
| TC-07-05 | before `Show All` (object hidden), `export_step` | `text` equals the line (`framing` unavailable, no visible object) | |
| TC-13-04 | `query_screenshot` iso, `Show All`, press `Isometric`, `Fit All` | window camera iso | `evidence/tc-13-04-after.png` and `evidence/tc-13-04-mcp.png`: same flat square plate with one hole, same silhouette, same camera; face tone differs by design (AD-34) |
| TC-13-10 | press `Isometric`, `Fit All`, capture sketch; `feature_pad` 5 mm; `Fit All`, capture | pad OK, `bbox` z 5 | `evidence/tc-13-10-before.png`: sketch outline in iso view; `evidence/tc-13-10-after.png`: solid 30 x 20 x 5 slab, thickness visible |
| TC-02-15, TC-09-12 | `query_tree_summary { doc: "fcb-doc:not-a-real-handle" }`, `"fcb-doc:does-not-exist"` | tool error text `INVALID_INPUT: unknown or stale document handle: <handle>`, no envelope | |
| TC-02-17 | `document_open` on a missing path, a text file, a corrupt zip | all `status INVALID_INPUT`, `detail.code INVALID_INPUT`; missing: `File '<path>' does not exist!`; text file and corrupt zip: `Invalid project file <path>: basic_ios::clear: iostream error`, equal after the path is replaced | |

Capture names: the case names for TC-13-04 (`-viewport.png`, `-after.png`) and TC-13-10 (`-after-pad.png`, `-viewport.png`, `-after.png`) show one camera state with no step between them, so this run holds one image for each state: `tc-13-04-after.png` and `tc-13-10-after.png`. TC-07-05 and TC-13-10 have no runner scenario file; only the agent-driven rows above cover them.

Test files made for TC-02-17 and the STEP files of TC-07-05 were removed after the read.
