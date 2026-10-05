# UAT run 2026-10-05-01 — Story 10.4 targeted GUI acceptance

- **Code under test:** uncommitted working tree on `feat/epic-4-spec-to-part` (baseline `a1ef9ab`): `adapters/render_probe.py`, `usecases/framing.py`, `usecases/screenshot.py`, `usecases/view_fit.py`. Addon junction to repo `src`.
- **FreeCAD:** 1.1.4 GUI, pid `6760`, window_id `2885910`; bridge proxy pid `31740` on `:8765`.
- **Proof the new code ran:** S7 returned `SPEC_FAILED` with `detail.code` `view_fit.nothing_to_frame`. `git show a1ef9ab:src/freecad_buddy/usecases/view_fit.py | grep -c nothing_to_frame` returns `0`; the working tree has 4 matches. Error tracebacks name `...\Mod\FreeCADBuddy\.\freecad_buddy\...`, which is the junction (`evidence/mcp-s4-setup.jsonl`).
- **Environment, call method, rules:** [RUN-CONTEXT.md](RUN-CONTEXT.md).

## Results

| Scenario | Finding | Verdict | Notes |
| --- | --- | --- | --- |
| S1 (TC-06-03) Body include | F-14 | PASS | `include:["Body"]` → `OK`, `rendered_objects:["Body"]`, `empty_scene:false`. The PNG shows one slab with the 20 x 30 x 10 pad proportions. The 10 x 20 x 30 `Box` is not drawn. Box stays greyed in the tree. `s1-render-include-body.png`, `s1-render-mcp.json`, `s1-window.png`. |
| S2 (TC-06-04) transparency only | F-16 | PASS | Plain render vs `{object:"Box", transparency:85}`: 1,679,729 of 3,686,400 pixels changed. The transparent PNG shows a see-through box with its hidden edges. Mean non-white colour: plain hue 0.585 sat 0.045; transparent hue 0.615 sat 0.008. That is the stock blue-grey blended with white, with no foreign tint. Limit: O-1. `s2-render-plain.png`, `s2-render-transparency85.png`, `s2-pixdiff.txt`. |
| S3 (TC-13-03) hidden include | F-15 | PASS | Box hidden in the GUI (tree row + `space`) and saved with the toolbar Save. Title: `s3-box - FreeCAD 1.1.4`, no `*`. `include:["Box"]` → `OK`, and the PNG shows the box. After: the title still has no `*`, the tree row is greyed, and the viewport is empty. The before and after window PNGs differ in 0 pixels. Console: `Gui Modified False`, `App Visibility False`, `ViewObject Visibility False`. `s3-before.png`, `s3-after.png`, `s3-window-pixdiff.txt`, `s3-console-after-render.png`, `s3-render-include-box.png`. |
| S4 (TC-02-08 / TC-04-13) pad + datum | F-28 | **FAIL** | Framing ratio is not `0.0`: after the fit, `ratio 0.950`, `checked: computed`. But `view_fit_viewport` → `SPEC_FAILED view_fit.not_framed`, `fits:false`, on both runs. In the window the pad runs off the right edge, and its far corner is not visible. Console measurements: the Coin scene box is `(-30.2,-30.2,0)-(30.2,35.2,10)` because it includes the drawn datum plane; the pad is `(0,0,0)-(20,30,10)`. `fitAll` centres on the scene box, but the measurement grades only the pad, so the pad sits off-centre at 95 % fill and overflows. The spec I/O row ("verdict measures the pad only; ratio > 0") holds. The fit expectation (`OK`, pad framed) does not. `s4-fit-mcp.json`, `s4-fit2-mcp.json`, `s4-after-fit.png`, `s4-after-fit2.png`, `s4-console-scenebbox.png`. |
| S5 sketch only | F-28 (D5) | PASS | Fit → `OK`, `fitted:true`, `fits:true`, `ratio 0.949`. The window shows the whole 20 x 30 rectangle in iso. Default render → `rendered_objects:["Sketch"]`, and the PNG draws the outline. `s5-fit-mcp.json`, `s5-after-fit.png`, `s5-render-default.png`. |
| S6 mesh only | F-28 (D5) | PASS | Mesh imported in the GUI Python console with `Mesh.insert` of `s6-input.stl` (a copy of `_automation/uat/tc-07-10-default.stl`). Result: one `Mesh::Feature`, 124 facets, bbox `(-10,-10,0)-(10,10,20)`. Fit → `OK`, `fits:true`, `ratio 0.951`. The window shows the whole cylinder. Default render → `["s6_input"]`, and the PNG draws the cylinder. `s6-console-import.png`, `s6-fit-mcp.json`, `s6-after-fit.png`, `s6-render-default.png`. |
| S7 datum only | F-28 (D6) | PASS | Fit → `SPEC_FAILED view_fit.nothing_to_frame`, with the D6 reason and no `framing` key. `ActiveView.getCamera()` is identical before and after (`diff` and console `True`). The window PNGs differ in 0 pixels. `s7-fit-mcp.json`, `s7-camera-before.txt`, `s7-camera-after.txt`, `s7-before.png`, `s7-after.png`, `s7-window-pixdiff.txt`. |

**Totals (first pass):** 7 scenarios: 6 PASS, 1 FAIL (S4, product), 0 NOT RUN.

## Re-run after spec decision D9 (fit pass 2 uses `boxZoom` on the measured hull)

FreeCAD 1.1.4 pid `3448`, window_id `1058650`; proxy pid `32300`, parent `3448`. The working tree holds the `boxZoom` pass 2 in `view_fit._fit_all`.

| Scenario | Finding | Verdict | Notes |
| --- | --- | --- | --- |
| S4b pad + datum, fit 1 | F-28 (D9) | PASS | `OK`, `fitted:true`, `fits:true`, `ratio 0.949`, `checked:computed`. The whole pad is centred: pad x 272-1318 in view x 245-1346 (centre 795 vs 795), pad y 355-1200 in view y 248-1302 (centre 777 vs 775). The datum plane is drawn behind it. `s4b-fit-mcp.json`, `s4b-after.png`. |
| S4b pad + datum, fit 2 | F-28 (D9) | PASS | `OK`, `fits:true`, `ratio 0.949`. Window pixel-identical to fit 1. `s4b-2-fit-mcp.json`, `s4b-2-after.png`. |
| S5b sketch only | F-28 (D5) | PASS | `OK`, `fits:true`, `ratio 0.949`. Whole rectangle visible and centred. `s5b-fit-mcp.json`, `s5b-after.png`. |
| S6b mesh only | F-28 (D5) | PASS | Mesh loaded in the GUI console (`Mesh.insert`, 124 facets). `OK`, `fits:true`, `ratio 0.951`. Whole cylinder visible and centred. `s6b-console-import.png`, `s6b-fit-mcp.json`, `s6b-after.png`. |
| S8 cube 40x40x40 | F-28 (D9) | PASS | `Part::Box` made in the GUI console. `OK`, `fits:true`, `ratio 0.951`. Whole cube visible and centred, about 95 % vertical fill. `s8b-cube-console.png`, `s8b-cube-fit-mcp.json`, `s8b-cube-after.png`. |
| S8 bar 40x40x800 | F-28 (D9) | PASS | `OK`, `fits:true`, `ratio 0.948`. Whole bar visible, centred, fills the height. `s8b-bar-console.png`, `s8b-bar-fit-mcp.json`, `s8b-bar-after.png`. |

**Totals (final):** S1-S3, S5-S7 from the first pass and S4b, S5b, S6b, S8 (two models) from the re-run all PASS. 0 product FAIL, 0 NOT RUN.

## Product defect (first pass)

- **S4 — a fit with a datum plane in the scene does not frame the model.** `view_fit._fit_all` calls `fitAll`, and `fitAll` frames the Coin scene bbox, which includes the drawn datum plane. `measure_framing` excludes datums (D4), so pass 3 grades a model that `fitAll` did not centre. Every Body with a datum plane gets `SPEC_FAILED view_fit.not_framed` and an off-centre view. TC-04-13 will hit this. To fix it, the fit must centre on the measured box, not on the scene box. **Fixed by spec decision D9** (pass 2 uses `boxZoom` on the measured hull); the re-run row S4b confirms it.

## Test-case defects for Story 10.7

- TC-06-03: The Then "rendered_objects contains no `Sketcher::SketchObject`" contradicts D5. A visible sketch is now in the default set: the S4 default render lists `["Sketch","Pad"]`, because the MCP pad leaves the sketch visible.
- TC-06-04: It always sends `color` with `transparency`, so it does not cover F-16. Add a transparency-only step that expects changed pixels and the object's own hue.
- TC-13-03: It has no Then for F-15. Add: after the hidden-state `include:["Box"]` render, the box is still hidden in the tree and the viewport, and the title has no `*`. To reach "no `*`", save through the GUI, not with `document_save` (O-2).
- Mesh only (S6): no test case covers it, and no bridge route loads a mesh. It needs the GUI Python console.

## Observations

- **O-1:** The render ignores the live view colour. With `Box.ViewObject.ShapeColor=(0.9,0.1,0.1)`, the plain and transparent renders are byte-identical to the grey renders (`s2-red-*.png`, same SHA-256). The constructed scene uses fresh view providers with the stock material, so "keeps its own colour" (D3) in practice means the stock material.
- **O-2:** `document_save` over MCP leaves the GUI document modified. The title kept `*`, the console shows `Gui.getDocument("s3_box").Modified` → `True`, and no object is `Touched` (`s3-console-after-mcp-save.png`). The toolbar Save cleared the flag. Run 2026-10-04-01 saw the same symptom and blamed `view_fit_viewport`; in this run no fit ran.
- **O-3:** Before any fit, framing in S1 and S4 was `fits:false`, `ratio:null`. The camera was at about 4 mm, so the projected corners were implausible and were discarded. This is by design; the ratio is not `0.0`.
- **O-4:** The 1.1.4 overlay Tasks panel covers the top right of the 3D view, and in S5 and S6 it covers part of models that report `fits:true`. Under D8 this is not a product defect.
- **O-5:** `addon.log` has `ERROR rpc_listener: frame read failed` (`ConnectionResetError`) at 16:49:20, during exit. This is teardown, not a scenario result (`addon-log.txt`).
- **O-6:** `feature_datum` refuses attachment kind `geometric` (`must be 'mapped_name'`). `{kind:"mapped_name", object:"XY_Plane"}` works.
- **O-7:** The second S4b fit returned its `framing` block as `checked:"cached"`, `stale_reason:"served from cache; unverified key component(s): geometry"`, although the fit had just measured; the first fit said `computed`. Values are equal. An `OK` fit appears to report the framing cache rather than its own pass-3 verdict.
- **O-8:** Creating a datum plane floods the GUI notification area with `AttachEngine3D::calculateAttachedPlacement` errors from objects `Probe` and `PositionBySupport` (seen by the user). Source: the `feature_datum` map-mode probe `usecases/shim.py:273-310`, pre-existing since `2cf5a14`.

## Evidence

`evidence/` holds:
- Scripts: `run.py` (driver), `console.sh` (GUI console helper), `pixdiff.py`, `schemas.py`.
- MCP logs: `mcp-*.jsonl`.
- Scenario files: the `sN-*` PNGs and JSON named in the table.
- Documents and input: `s1-box.FCStd`, `s2-box.FCStd`, `s3-box.FCStd`, `s6-input.stl`.
- Repo state: `git-status-*.txt` and `git-diff-stat-*.txt`; preflight equals after.
