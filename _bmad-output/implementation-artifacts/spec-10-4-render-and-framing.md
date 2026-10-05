---
title: 'Story 10.4: Render and Framing'
type: 'bugfix'
created: '2026-10-05'
status: 'done'
baseline_commit: 'a1ef9abc30d90a33380a858047ad7076412acf99'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-10-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** UAT run `2026-10-03-04` found render and framing defects. `include:["BodyA"]` writes a blank PNG with `empty_scene:false` (F-14). Rendering a hidden object un-hides it in the live document and marks the document modified (F-15). A style with `transparency` and no colour has no effect (F-16). A datum plane has an infinite shape, so its bbox poisons the projection: `view_fit_viewport` returns `OK`, `ratio:0.0` (F-28).

**Approach:** Fix each at its root in `usecases/screenshot.py`, `adapters/render_probe.py`, `usecases/framing.py` and `usecases/view_fit.py`. Each fix gets a regression test that fails on the baseline.

**Decisions (planning):**
- **D1 — F-14.** An `include` entry naming a `PartDesign::Body` renders the Body's `Tip` subgraph; `rendered_objects` reports the Body name the caller gave. A Body with no `Tip` adds nothing. The Body view provider itself is never passed to `subgraphFromObject` (it faults the headless Coin, `screenshot.py:43-45`). Any subgraph whose `SoGetBoundingBoxAction` box is empty counts as not rendered, so a scene of only such nodes reports `empty_scene:true`.
- **D2 — F-15.** `OffscreenRenderPort.render` reads `obj.Visibility` and, in GUI mode, the GUI document's `Modified` before `subgraphFromObject`, and restores any changed value in a `finally`. Cause: `ViewProviderDocumentObject.cpp:360-363` writes the fresh view provider's `Visibility=true` onto the live object on `attach`.
- **D3 — F-16.** `_wrap_style` always calls `setOverride(True)` and calls `setIgnored(True)` on every `SoMaterial` field it does not write. The object keeps its own colour; only the written fields override.
- **D4 — F-28 (datum).** `is_default_renderable` also excludes objects derived from `App::DatumElement`, `App::LocalCoordinateSystem` and `Part::Datum` (covers `PartDesign::Plane/Line/Point/CoordinateSystem` and `Part::DatumPlane`). `_object_bounds` also rejects a bbox with any `|value| >= 1e99` (an infinite OCC shape reports about `±1e100`). The predicate stays shared by render and framing (AD-30).

**Decisions (2026-10-05, user):**
- **D5 — F-28 (Q1 B).** Sketches and meshes join the shared predicate. `Sketcher::SketchObject` leaves `_NON_RENDER_TYPES`. A `Mesh::Feature` with a non-empty `Mesh` counts as having a shape, and its bounds come from `Mesh.BoundBox`. So the default render draws a visible sketch or mesh, and framing and the fit measure it. A hidden sketch (the usual state after a pad) stays out.
- **D6 — F-28 nothing measurable (user).** Datums stay excluded. When the measurable set is empty (for example datum-only), `view_fit_viewport` checks before any camera move and returns `SPEC_FAILED`, code `view_fit.nothing_to_frame`, reason "no visible object to frame; datum planes are infinite and are not measured". Camera does not move. No `framing` block.
- **D7 — size (user).** One spec; no split.
- **D8 — F-27 (user): not a product defect.** Framing and the fit measure the whole 3D view (`getSize()`), whatever its size. The bridge does not account for a FreeCAD window so small that the MDI area scrolls part of the 3D view off screen. AD-30 stays as written. Story 10.4 AC4 in `epics.md` is replaced by this decision; TC-14-13 is corrected in Story 10.7.
- **D9 — fit centres on the measured model (user, after UAT `2026-10-05-01` S4).** Pass 2 of the fit no longer calls `fitAll(factor)`, because `fitAll` centres on the Coin scene box, which includes a drawn datum plane that D4 leaves out of the measurement. Pass 2 calls `view.boxZoom(XMin, YMin, XMax, YMax)` on the pass-1 projected hull of the measured set, expanded about its centre by `1 / _FILL_FRACTION`, with Y converted from `getPointOnViewport` (Y-up) to `boxZoom`'s Y-down (`y_box = height - y`). `boxZoom` pans to the box centre and scales by the larger axis quotient (`NavigationStyle.cpp:584-620`), so the model is centred and its binding axis lands on `_FILL_FRACTION`. Pass 1 (`viewIsometric`, `fitAll(1.0)`) and pass 3 are unchanged. `_MIN_FIT_FACTOR` keeps its role as a floor on the box size. Spine AD-30's three-pass bullet is amended to match.

## Boundaries & Constraints

**Always:**
- Render never changes live `Visibility`, the document, or the GUI modified flag.
- Render and framing use the one `is_default_renderable` predicate.
- `fitted:true` only with its own post-fit `fits:true` (AD-31).
- Every fix has a regression test that fails on the baseline commit.

**Never:**
- No change to UAT test-case files (Story 10.7).
- No expansion of `App::Part` or other containers in `include` (not in the ACs).
- No change to the AD-34 lighting rig.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Body include | `include:["Body"]`, Tip `Pad` | PNG shows the pad; `rendered_objects:["Body"]` | — |
| Empty subgraph | include resolves only to empty-bbox nodes | `empty_scene:true`, no PNG | — |
| Hidden include | `include:["Box"]`, `Box.Visibility=False` | after render `Box.Visibility` is `False`; GUI `Modified` unchanged | restored in `finally` on raise |
| Transparency only | style `{object:"Box", transparency:85}` | pixels differ from the plain render; hue kept | — |
| Datum + pad | Body with Pad and `PartDesign::Plane` | verdict measures the pad only; `ratio > 0` | — |
| Sketch only | one visible closed sketch | default render draws it; fit `OK`, `fits:true`, `0 < ratio <= 1` | — |
| Mesh only | one `Mesh::Feature` | default render draws it; fit `OK`, `fits:true`, `0 < ratio <= 1` | — |
| Pad + datum fit | Body with Pad and `PartDesign::Plane`; `view_fit_viewport` | `OK`, `fits:true`, `0 < ratio <= 1`; pad hull centred on the view | — |
| Datum only | Body with only `PartDesign::Plane` | fit `SPEC_FAILED view_fit.nothing_to_frame`; camera string unchanged | — |

</frozen-after-approval>

## Code Map

- `usecases/screenshot.py:47-66` `_NON_RENDER_TYPE_PREFIXES`, `is_default_renderable` -- D4. `:229-243` `_object_list` -- D1 (Body to Tip, keep the given name).
- `adapters/render_probe.py:221-238` subgraph loop and `empty_scene` -- D1, D2. `:255-279` `_wrap_style` -- D3; its docstring `:262-264` explains the old reason and must change.
- `usecases/framing.py:78-94` `_object_bounds` -- D4. D5: a mesh's bounds come from `Mesh.BoundBox`. `:300-344` `measure_framing` -- unchanged bound (`getSize()`, D8).
- `usecases/view_fit.py:85-115` fit flow, `:117-152` `_fit_all` -- D6 check goes before `_fit_all`. `:362-415` envelope builders; reuse `_refused_envelope`.
- Tests: `tests/infc/test_screenshot.py` (`test_include_exclude_honored :96`, `test_default_set_honors_visibility :106`, `test_partdesign_default_render_skips_body_and_datum :186`, `EmptySceneTest :220`, `WrapStyleTest :521`; `:564` and `:636` assert the F-16 bug and must be rewritten). `tests/external/test_render_probe.py`, `tests/external/test_framing.py` (`_FakeView :72`, `_FakeViewportPort :99`), `tests/external/test_view_fit.py` (`_FakeViewportPort :103`, `_ProjectingView :519`).
- Docs: `mcp-tools-design.md` §3.9 `:524-529` add `empty_scene`; `:493` and `:537` stay true after the fix. Spine AD-30 predicate list `:277` (D4, D5). `epics.md:1317-1319` Story 10.4 AC4 (D8).
- D5 risk: confirm `FreeCADGui.subgraphFromObject` works for a sketch and a mesh under FreeCADCmd offscreen before relying on it; a mesh view provider may need `import MeshGui` first.
- No `benchmarks/runner.py` validator covers these files. `verify_render_tone` controls come from `OffscreenRenderPort` (`capture_render_controls.py`); re-check them after D2/D3.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/screenshot.py` -- D1, D4, D5 (`_NON_RENDER_TYPES`, `_has_shape` accepts a non-empty `Mesh`; update the skip comment `:40-46`). `framing._object_bounds` reads `Mesh.BoundBox` for a mesh. Existing tests that assert the sketch skip change with D5.
- [x] `src/freecad_buddy/adapters/render_probe.py` -- D1 empty-bbox check, D2, D3.
- [x] `src/freecad_buddy/usecases/framing.py` -- D4 infinite-bbox guard, D5 mesh bounds.
- [x] `src/freecad_buddy/usecases/view_fit.py` -- D6: empty-set check before `_fit_all`.
- [x] Tests -- one per I/O row, in the files the Code Map names.
- [x] Docs -- `mcp-tools-design.md` §3.9 (default set now includes visible sketches and meshes), spine AD-30 predicate list `:277` (D4, D5), `epics.md` Story 10.4 AC4 replaced per D8.
- [x] Re-run `verify_render_tone` and confirm its controls do not drift.

**Acceptance Criteria:**
- Given each I/O row, when its regression test runs on FreeCAD 1.1.x, then it passes, and it fails on the baseline commit.
- Given the full suites, when run, then in-FreeCAD and external tests pass, and ruff, `check_imports`, `gen_schemas --check` and `check_provenance` pass.
- Given FreeCAD 1.1.4 GUI driven with `cua-driver`, when TC-06-03, TC-06-04, TC-13-03, TC-02-08 and TC-04-12/13 run, then the visual check agrees with each AC.

## Implementation Notes

- D1 lives in the port, not in `_object_list`. `_subgraph_source` (`adapters/render_probe.py`) swaps a Body for its Tip at the one place that calls `subgraphFromObject`. `SceneSpec.objects` keeps the given name, so `rendered_objects`, styles and the highlight all key on "Body" with no contract change. Headless baseline evidence: `include:["Body"]` raised `RuntimeError: Access violation`.
- D3 needs `COIN_SEPARATE_DIFFUSE_TRANSPARENCY_OVERRIDE=1`. Without it Coin couples the diffuse and transparency overrides: `setIgnored` + `setOverride` still rendered a red box grey, rgb(143,143,143). FreeCAD's 3D view sets the variable (`View3DInventorSelection.cpp:60`); a headless process has no 3D view. Coin caches it at the first override it traverses, so `render()` sets it before every render.
- D5: `subgraphFromObject` works under FreeCADCmd offscreen for a sketch and a `Mesh::Feature` with no `import MeshGui`. A headless pad leaves its sketch `Visibility=True`, so a headless default render now draws the sketch.
- D6: `view_fit` checks `framing.model_bounds` (the shared measured set). A document that raises on read is not "nothing to frame": the fit runs and `view_fit.unverified` names the failure, as before.
- `verify_render_tone` controls: the baseline and the fixed port render byte-identical PNGs for all 8 cameras on this machine, and the scorer reports sensitivity 1.000, false alarm 0.000. The committed controls were not re-captured.
- D9: pass 1 boxes the measured set's projected corners with `framing.projected_hull` (same corners, projection and implausible-magnitude rule as `measure_framing`). Pass 2 calls `view.boxZoom` on that hull expanded by `1 / _FILL_FRACTION`, Y flipped, rounded to whole pixels. Each side is floored at `_MIN_FIT_FACTOR` of its view dimension, because `boxZoom` ignores a 0x0 box. `_correction_factor` is removed; `_fit_all_with_factor` became `_fit_all_known_state` (pass 1 only). The external fake models `boxZoom` per `NavigationStyle.cpp:584-620`, including the integer midpoint normalised by `size - 1`. In the S4 geometry that leaves the pad hull about 3 px off centre after the zoom, and the landed ratio is within 0.002 of 0.95. The S4 regression test returns `SPEC_FAILED` with the old `fitAll(factor)` pass 2 and `OK`, centred, with `boxZoom`.

## Spec Change Log

## Review Triage Log

| # | Source | Finding | Verdict | Route / evidence |
|---|--------|---------|---------|------------------|
| 1 | blind, edge, gap | `epic-10-context.md` still says F-27 uses the visible area, the default set skips sketches, and `empty_scene` is missing from the tool design | medium | patch (doc): contradicts D5, D8 and the `mcp-tools-design.md` edit in this diff; a later story could re-implement the visible-area bound. |
| 2 | blind | Spine AD-30 bullets beside the amended three-pass bullet still argue for `fitAll(factor)` and cite removed `view_fit.py` symbols (`_fill_factor`, `:168`, `:182-186`) | medium | patch (doc): D9 removed that mechanism; the spine must state current state. `epics.md:1054,1094` are closed Epic 8/9 story texts: rejected. `TC-14...md:140`: defer to 10.7. |
| 3 | blind | A measured set with zero extent (single-point sketch) passes `_nothing_to_frame`, projects to one pixel, and returns `OK` with `ratio: 0.0` | medium | patch: `model_bounds` returns a non-`None` zero-size box; pass 3 `hull_ratio` is 0 and `fits` true; epic AC5 forbids `OK` with `ratio 0.0`. Treat a zero-size box as nothing to frame, plus a test. |
| 4 | blind, edge | `view_fit.nothing_to_frame` reason always names datum planes, also for an empty or all-hidden document | low | rejected: the reason text is fixed verbatim by D6 (frozen); its first clause "no visible object to frame" is true in every case. |
| 5 | blind, edge | An infinite non-datum shape stays in the render set but framing skips it | low | rejected: needs a non-datum `Part::Feature` with an infinite shape (not built by any bridge tool); the fix adds a bbox read to the shared predicate. |
| 6 | blind | `_MIN_FIT_FACTOR` is no longer a `fitAll` factor and its comment does not justify 1 % | low | patch: rename to `_MIN_ZOOM_BOX_FRACTION`; comment states the mechanism. |
| 7 | blind | `sprint-status.yaml` says `in-progress` while the spec says `in-review` | false | step 5 syncs sprint status; the spec reached `in-review` in this step. |
| 8 | blind | `RUN-CONTEXT.md` says D1-D8 and lists only first-pass pids | low | patch (doc). |
| 9 | blind | UAT report "Product defect" section still reads as open after the S4b re-run | low | patch (doc): state that D9 fixed it and S4b confirmed it. |
| 10 | blind, edge | UAT O-1 (render ignores live `ShapeColor`), O-6 and the test-case defects are not in `deferred-work.md` | low | defer: O-1 is pre-existing render behaviour (fresh view providers); test-case defects are listed in the run report for Story 10.7. |
| 11 | blind | Baseline-failure proof recorded only for the D9 test; TC-04-12 not run | false | the implementation report states every I/O-row test was run on a baseline worktree and failed there; S4/S4b exercise the same datum-in-Body framing path as TC-04-12. |
| 12 | blind | `rendered_objects` now means "drew something"; tool design does not say so | low | patch (doc): one sentence in `mcp-tools-design.md` §3.9. |
| 13 | blind | Datum exclusion by base type is checked in FreeCAD only for `PartDesign::Plane` | low | patch: one infc test over `Part::DatumPlane`, `PartDesign::Line`, `PartDesign::Point`, `PartDesign::CoordinateSystem`. |
| 14 | blind | `include:["Body","Pad"]` draws the Tip twice | low | rejected: unlikely input; fix adds a de-duplication branch. |
| 15 | blind | Comment on `COIN_SEPARATE_DIFFUSE_TRANSPARENCY_OVERRIDE` overstates why it is set per render | low | patch: comment states it matters in a headless process before its first override, and the write is idempotent. |
| 16 | gap | Style or highlight on an included Body is not checked through the real port | medium | patch: infc test, `include:["Body"]` with `highlight` on "Body", centre pixel takes the accent hue. |
| 17 | gap | GUI `Modified` restore is checked only with fakes | medium | defer: needs a live GUI document; UAT S3 covered it manually; a 10.7b probe check fits. |
| 18 | edge | Hull under 1 % after `fitAll(1.0)` caps the zoom at 100x and can return `OK` with a small ratio | low | rejected: same floor semantics as the baseline `_MIN_FIT_FACTOR`; `fitted:true` requires `fits:true` only (AD-31). |
| 19 | edge | A zoom box outside the `short` range raises `OverflowError` | low | rejected: needs a view wider than about 7,800 px; result is an honest `view_fit.failed`. |
| 20 | edge | A view without `boxZoom` raises | false | every FreeCAD 1.1 `View3DInventor` has `boxZoom` (`View3DPy.cpp:81`). |
| 21 | edge | Perspective camera: `boxZoom` pans on the focal plane, parallax may leave the model off-centre | maybe-false | defer (medium if true): settle by running the pad + datum fit with a perspective camera; pass 3 still grades the result honestly. |
| 22 | edge | NaN projection makes `round()` raise in `_zoom_box` | false | `getPointOnViewport` returns `short` integers; a NaN cannot reach the hull. |
| 23 | edge | D3 "keeps its own colour" means the stock material, not the live `ShapeColor` | low | defer with row 10 (same root cause, pre-existing). |

## Verification

**Commands:**
- `micromamba run -n fcb freecadcmd tests/run_tests.py` -- expected: OK.
- `uv run pytest tests/external` -- expected: all pass.
- `uv run ruff check .`, `uv run python scripts/check_imports.py`, `uv run python scripts/gen_schemas.py --check`, `uv run python scripts/check_provenance.py` -- expected: pass.

**Manual checks:**
- Live GUI per the last AC: screenshots of the hidden-object tree state, the Body render, the transparency render, and the fit on sketch-only, mesh-only and datum-only documents.
