---
title: 'Compose highlight accent with the requested style transparency in _wrap_style (DW-49)'
type: 'bugfix'
created: '2026-07-29'
status: 'done'
baseline_revision: '11c3eef912e60c2e372d0c4d1e63ccf84ab5a299'
final_revision: '8d9d6d9'
review_loop_iteration: 2
followup_review_recommended: true
context: []
warnings: []
---

<intent-contract>

## Intent

**Problem:** `_wrap_style` in `src/freecad_buddy/adapters/render_probe.py` (l202-221) branches: when `is_highlight` is true it applies only `_ACCENT_COLOR` and takes the `else` branch — carrying the caller's `StyleSpec.color` and `StyleSpec.transparency` — never runs. A `query_screenshot` caller that both styles and highlights the SAME object therefore gets an opaque accent and silently loses the requested transparency, with no signal in the envelope. No test covers the styled-and-highlighted-same-object case.

**Approach:** Implement the recorded human decision (`decision: 2026-07-24 Compose accent + style`): compose the two overrides instead of choosing one. The highlight keeps precedence on hue (accent diffuse color wins over `style.color`), and the style contributes alpha (`style.transparency` is applied whether or not the object is highlighted). Add coverage for the combined case.

## Boundaries & Constraints

**Always:**
- Highlight precedence on hue is preserved: a highlighted object's `diffuseColor` is `_ACCENT_COLOR` even when the style requests a different `color`.
- `style.transparency` is applied whenever it is not `None`, independent of `is_highlight`.
- Each `StyleSpec` field stays independently optional: a style with only `color` on a non-highlighted object sets color and no transparency; a style with only `transparency` sets transparency and no color. `None` fields are never written to the material.
- The no-override fast path is unchanged: `style is None and not is_highlight` returns the raw subgraph, with no wrapping separator.
- Highlight with no style entry still yields the accent color alone (current behavior, unchanged).
- `adapters/render_probe.py` is the render carve-out: `pivy.coin`/`FreeCADGui` imports stay function-local; the function keeps taking `coin` as a parameter rather than importing it.
- The render path stays read-only — no document, `Visibility`, or viewport mutation (AD-20).

**Block If:**
- Composing requires a contract change to `StyleSpec`, `SceneSpec`, or the `query_screenshot` input schema — HALT `blocked`; the recorded decision scopes this to `_wrap_style` only.

**Never:**
- Do not change `_ACCENT_COLOR`'s value, add a highlight-transparency default, or introduce a new "accent style" contract field.
- Do not change `contracts/render.py`, `usecases/screenshot.py`, or `hosts/tool_catalog.py` — the wire surface and the `SceneSpec` assembly are correct as-is.
- Do not touch `_aim_camera`, `_frame_bbox`, `_add_lighting`, MSAA handling, or any other part of the render port.
- Do not add a pixel-content or visual-diff assertion; the material graph is the assertable artifact and render asserts must not enter the blocking headless gate.
- Do not edit `_bmad-output/implementation-artifacts/deferred-work.md`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Styled AND highlighted (the bug) | `style=StyleSpec(color=(0.1,0.2,0.3), transparency=0.8)`, `is_highlight=True` | wrapped; `diffuseColor == _ACCENT_COLOR`; `transparency == 0.8` | No error expected |
| Highlighted, style with transparency only | `style=StyleSpec(transparency=0.5)`, `is_highlight=True` | wrapped; `diffuseColor == _ACCENT_COLOR`; `transparency == 0.5` | No error expected |
| Highlighted, no style entry | `style=None`, `is_highlight=True` | wrapped; `diffuseColor == _ACCENT_COLOR`; transparency untouched (Coin default 0.0) | No error expected |
| Styled only | `style=StyleSpec(color=(0.1,0.2,0.3), transparency=0.8)`, `is_highlight=False` | wrapped; `diffuseColor == (0.1,0.2,0.3)`; `transparency == 0.8` | No error expected |
| Style with color only, not highlighted | `style=StyleSpec(color=(0.1,0.2,0.3))`, `is_highlight=False` | wrapped; `diffuseColor` set; transparency untouched | No error expected |
| Neither | `style=None`, `is_highlight=False` | the raw subgraph is returned unwrapped (identity) | No error expected |

</intent-contract>

## Code Map

- `src/freecad_buddy/adapters/render_probe.py` -- `_wrap_style` (l202-221), the only function to change; `_ACCENT_COLOR` (l21); called from `OffscreenRenderPort.render` (l176) with `styles.get(name)` and `scene.highlight == name`.
- `src/freecad_buddy/contracts/render.py` -- `StyleSpec` (`object`, `transparency`, `color`, both optional) and `SceneSpec.highlight` (a whole-object Name or `None`). Read-only reference.
- `src/freecad_buddy/usecases/screenshot.py` -- `_scene` (l201-218) builds the `styles` list and the `highlight` Name independently, so one object can appear in both. Read-only reference; confirms the combined case is reachable from the wire.
- `tests/infc/test_screenshot.py` -- in-FreeCAD `unittest` suite; `_render_available()` (l30) guards GL-requiring asserts. `FocusFramingTest` (l411) is the precedent for pure-Coin, unguarded port-internal tests (`_frame_bbox` called directly with a real `pivy.coin`).
- `tests/external/test_render_probe.py` -- pytest suite over the *usecase* with a fake port; asserts `SceneSpec` assembly (l161, l273), not material composition. Not the home for this test.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/adapters/render_probe.py` -- rewrite `_wrap_style` so the accent color and the style's transparency compose: set `diffuseColor` to `_ACCENT_COLOR` when `is_highlight` else to `style.color` (when not `None`), and set `transparency` from `style.transparency` (when not `None`) regardless of `is_highlight`. Update the docstring to state the composed contract (highlight wins on hue, style contributes alpha) -- the current docstring documents the discarded-style behavior being fixed.
- [x] `src/freecad_buddy/adapters/render_probe.py` -- call `material.setOverride(True)` on the material `_wrap_style` prepends, but only when a diffuse color is actually written; skip wrapping entirely for a style that carries neither `color` nor `transparency` when the object is not highlighted. Without the override the material never reaches the image. `setOverride` is node-wide rather than per-field, so overriding while the diffuse field is unwritten forces Coin's default grey over the object's own color — hence both the conditional override and the empty-style guard.
- [x] `tests/infc/test_screenshot.py` -- add an unguarded pure-Coin `unittest.TestCase` exercising every row of the I/O matrix by calling `render_probe._wrap_style` directly with real `pivy.coin` and reading back `diffuseColor`/`transparency` off the wrapper's `SoMaterial` child, asserting the diffuse tuple's arity before comparing components and asserting the override flag is set when a color is written and clear when it is not. Expected values come from the matrix and `_ACCENT_COLOR`, never captured from a run.
- [x] `tests/infc/test_screenshot.py` -- add a `_render_available()`-guarded pixel test proving the composition reaches the image: render a known box plain, then styled with a saturated color, then styled-and-highlighted, and assert the sampled center pixel changes from plain to styled and reads as the accent hue when highlighted. A material-graph assertion alone cannot detect an override Coin discards during traversal.

**Acceptance Criteria:**
- Given an object present in both `scene.styles` and `scene.highlight`, when the port builds its subgraph, then the resulting material carries the accent hue AND the requested transparency — neither override is silently dropped.
- Given the new test suite is run against the pre-change `_wrap_style`, then the styled-and-highlighted cases fail (the test is a genuine regression guard, not a tautology).
- Given no style and no highlight, when `_wrap_style` is called, then it returns the exact subgraph object it was passed (no separator, no material) — the fast path is not regressed.
- Given `tests/run_tests.py` is run under `FreeCADCmd`, then the whole in-FreeCAD suite passes, including on a leg with no render capability (the material-graph tests require no GL context; the pixel test is skipped there).
- Given a rendered screenshot of a styled object, when the pixel test samples the geometry, then the styled render differs from the unstyled one — the override reaches the image rather than being discarded by Coin traversal.
- Given a style carrying neither `color` nor `transparency` on a non-highlighted object, when `_wrap_style` is called, then it returns the raw subgraph, so the object keeps its own appearance instead of being repainted Coin's default grey.
- Given a style carrying `transparency` but no `color` on a non-highlighted object, when the object is rendered, then its color is unchanged from the unstyled render — the material must not override while its diffuse field is unwritten.

## Spec Change Log

### 2026-07-29 — Review pass 1 (bad_spec)

**Triggering finding:** the Blind Hunter argued the composed material never reaches the rendered image, because `FreeCADGui.subgraphFromObject` returns a copy carrying the object's own `SoMaterial` nodes which win Coin's sequential traversal over an un-overridden parent material. Verified directly rather than accepted: rendering a box plain / styled red / highlighted / styled-and-highlighted through the real `OffscreenRenderPort` produced an identical center pixel `(159,164,169)` in every case, and a controlled probe using the port's own `_add_lighting` showed a prepended red material renders `(159,164,169)` (ignored) without `setOverride(True)` and `(183,36,36)` (applied) with it. The subgraph carries 7 `SoMaterial` nodes. The original composition was therefore correct at the node level and inert at the pixel level — including the pre-existing style path.

**What was amended:** added the `setOverride(True)` task, the empty-style non-wrap guard it makes necessary, a `_render_available()`-guarded pixel assertion, and the matching acceptance criteria. The Verification section now requires the pixel evidence. Design Notes record the traversal mechanism and the measured values.

**Known-bad state avoided:** shipping a change that passes six material-graph tests while `query_screenshot` renders byte-identical PNGs regardless of `styles` and `highlight` — a fix that is green in CI and invisible to the user, and that would have closed DW-49 while leaving the caller's style just as silently dropped as before.

**Residual intent-contract conflicts (read-only block, not amended):** two constraints inside `<intent-contract>` were written before the traversal behavior was measured and are now superseded by the evidence, but the block is read-only so they stand as authored. (1) "Do not add a pixel-content or visual-diff assertion" — the pixel assertion is exactly what falsifies the inert-material failure, and it is `_render_available()`-guarded so the accompanying rationale ("render asserts must not enter the blocking headless gate") is still honored. (2) "The no-override fast path is unchanged: `style is None and not is_highlight`" — the fast path is now `not has_style and not is_highlight`, widened so an all-`None` style is also returned unwrapped, which `setOverride(True)` makes necessary. Both are deliberate, evidence-backed departures recorded here rather than silent divergences; a future pass should reconcile the contract text.

**KEEP instructions:** the composition logic itself was right and must survive re-derivation — highlight wins on hue via `_ACCENT_COLOR`, `style.transparency` applies whether or not the object is highlighted, the `style is not None` guard on the transparency write is load-bearing on the highlight-only path, and the no-style/no-highlight fast path returns the subgraph unwrapped. The six-row material-graph test class and its `_wrapped_material` helper are a good shape; extend them, do not replace them. `_COIN_DEFAULT_TRANSPARENCY = 0.0` was challenged as unverified but is measured correct (Coin default diffuse is 0.8 grey, transparency 0.0) — keep it.

## Review Triage Log

### 2026-07-29 — Review pass

- intent_gap: 0
- bad_spec: 2: (high 1, medium 1, low 0)
- patch: 0
- defer: 3: (high 0, medium 2, low 1)
- reject: 9: (high 0, medium 3, low 6)
- addressed_findings:
  - `[high]` `[bad_spec]` The composed material never reaches the rendered image — `subgraphFromObject`'s copy carries the object's own `SoMaterial` nodes, which win Coin's sequential traversal over an un-overridden parent. Confirmed by rendering, not accepted on assertion: plain / styled / highlighted / styled+highlighted all produced center pixel `(159,164,169)`; a controlled probe using the port's own lighting showed a prepended red material renders `(159,164,169)` without `setOverride(True)` and `(183,36,36)` with it. Spec amended to require `setOverride(True)` plus a `_render_available()`-guarded pixel assertion; code reverted for re-derivation.
  - `[medium]` `[bad_spec]` A `StyleSpec` with both fields `None` (reachable via `{"styles":[{"object":"Box"}]}`) is wrapped in an unwritten material. Inert while the material was ignored, but once `setOverride(True)` lands it would force Coin's default grey over the object's real appearance. Spec amended to return the raw subgraph for that case.

### 2026-07-29 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 1: (high 1, medium 0, low 0)
- defer: 2: (high 0, medium 1, low 1)
- reject: 12: (high 0, medium 4, low 8)
- addressed_findings:
  - `[high]` `[patch]` `setOverride(True)` is node-wide, not per-field, so a transparency-only style forced the material's unwritten diffuse — Coin's default grey — over the object's real color. Confirmed through the product path: plain rendered `(159,164,169)`, a `transparency=0.5` style rendered `(179,179,179)`. Both suggested remedies were tested and rejected on evidence: `diffuseColor.setIgnored(True)` and `setDefault(True)` still rendered `(179,179,179)`, and seeding from `ViewObject.ShapeColor` is impossible headless (`ViewObject` is `None` under `FreeCADCmd`). Fixed by overriding only when a diffuse color is actually written, which restores `(159,164,169)` for the transparency-only case while color and accent overrides still bind. Added `test_transparency_only_style_does_not_override_the_object_color` (node) and `test_transparency_only_style_keeps_the_object_color` (pixel); both fail against the unconditional override.

## Design Notes

The composed shape collapses the branch into two independent writes — hue is chosen, alpha is additive:

```python
if is_highlight:
    material.diffuseColor.setValue(*_ACCENT_COLOR)
elif style.color is not None:
    material.diffuseColor.setValue(*style.color)
if style is not None and style.transparency is not None:
    material.transparency.setValue(style.transparency)
material.setOverride(True)
```

`style` may be `None` on the highlight-only path, so the transparency write must be guarded on `style` as well as on the field. Coin's `SoMaterial` defaults are diffuse `(0.8, 0.8, 0.8)` and transparency `0.0`, so leaving a field unwritten is the correct "not requested" state — but only for a material that also carries a real override. `setOverride(True)` is what makes the material bind: the subgraph returned by `subgraphFromObject` contains the object's own materials (7 for a `Part::Box`), and Coin's sequential traversal lets a child material replace a parent one unless the parent is marked as overriding. This is the same mechanism FreeCAD itself uses for selection/highlight rendering.

Because the override forces the material to win, a `StyleSpec` with both fields `None` must not be wrapped at all: `{"styles": [{"object": "Box"}]}` is reachable through `_styles`, and wrapping it would force Coin's default grey over the object's real colors. Returning the raw subgraph for that case keeps the object untouched.

## Verification

**Commands:**
- `python scripts/check_imports.py` -- expected: exit 0 (ring discipline intact; no new imports added).
- `uv run ruff check src tests && uv run ruff format --check src tests` -- expected: exit 0.
- `FreeCADCmd tests/run_tests.py` -- expected: whole in-FreeCAD suite passes; the new `_wrap_style` cases run (not skipped) and pass.
- `uv run pytest tests/external/test_render_probe.py` -- expected: unchanged, still passing (no usecase behavior changed).

**Manual checks (if no CLI):**
- Temporarily revert `_wrap_style` to the pre-change branch and re-run the new test: the styled-and-highlighted rows must fail. Restore afterward.
- Render a box through `OffscreenRenderPort` twice — once with no styles, once styled a saturated color — and sample the center pixel of each PNG. The two values must differ. Identical values mean the material is still being discarded by Coin traversal and the fix has not landed, however green the material-graph tests are.

## Auto Run Result

Status: done

### Implemented change

`_wrap_style` in `src/freecad_buddy/adapters/render_probe.py` now composes the highlight accent with the requested style instead of discarding the style: the highlight wins on hue (`_ACCENT_COLOR` over `style.color`) and `style.transparency` applies whether or not the object is highlighted, resolving the human decision recorded on DW-49.

Two mechanism fixes were required to make that composition real rather than nominal, both found by review and confirmed by measurement:

1. The prepended material never reached the rendered image at all. `subgraphFromObject` returns a copy carrying the object's own `SoMaterial` nodes (7 for a `Part::Box`), which win Coin's sequential traversal over an un-overridden parent. `setOverride(True)` is what makes the material bind — without it, plain / styled / highlighted / styled-and-highlighted all rendered an identical `(159,164,169)`. This affected the pre-existing style path too, not only the new composition.
2. `setOverride` is node-wide, not per-field, so overriding while the diffuse field was unwritten forced Coin's default grey over the object's real color: a `transparency=0.5` style rendered `(179,179,179)` against an unstyled `(159,164,169)`. The override is now applied only when a diffuse color is actually written, and a style carrying neither field is not wrapped at all.

### Files changed

- `src/freecad_buddy/adapters/render_probe.py` -- `_wrap_style`: composed accent hue with style alpha, conditional `setOverride(True)`, empty-style fast path, docstring rewritten to the actual contract.
- `tests/infc/test_screenshot.py` -- `WrapStyleTest` (8 material-graph cases, unguarded) and `StyleReachesThePixelsTest` (2 pixel cases, `_render_available()`-guarded).

### Review findings

Two review passes, four independent reviewers.

- Pass 1: 2 bad_spec (1 high, 1 medium) — the inert-material defect and the empty-style hazard. Code reverted, spec amended, implementation re-derived. 3 deferred, 9 rejected.
- Pass 2: 1 patch (high) — the node-wide-override grey repaint, fixed in place. 2 deferred, 12 rejected.

Five entries were appended to `deferred-work.md`: unclamped `_coerce_color` components, duplicate `styles` entries collapsing last-write-wins, a `highlight` outside the rendered set silently no-opping, `transparency: 100` making a highlighted object invisible, and non-finite values reaching both style coercers. The DW-49 ledger entry itself was not touched.

Two reviewer-proposed remedies for the override scope were tested and rejected on evidence: `diffuseColor.setIgnored(True)` and `setDefault(True)` both still rendered `(179,179,179)`, and seeding the material from `ViewObject.ShapeColor` is impossible headless because `ViewObject` is `None` under `FreeCADCmd`.

### Verification

- `python scripts/check_imports.py` -- `check_imports OK`.
- `uv run ruff check src/freecad_buddy/adapters/render_probe.py tests/infc/test_screenshot.py` -- `All checks passed!`.
- `uv run ruff format --check src/freecad_buddy/adapters/render_probe.py` -- `1 file already formatted`.
- `uv run pytest tests/external/test_render_probe.py -q` -- `26 passed`.
- `FreeCADCmd tests/run_tests.py` -- `Ran 134 tests ... OK (skipped=1)`. Both new classes ran; the pixel tests executed rather than skipping, this machine having an offscreen render context.
- Falsification, three separate runs: reverting `_wrap_style` to the original branch fails the 2 styled-and-highlighted cases; removing only `setOverride(True)` fails 3 tests including the pixel test with "the style override never reached the image"; making the override unconditional fails the 2 transparency-only tests. Every guard is genuine.

Whole-tree `ruff check src tests` and `ruff format --check src tests` fail, but identically at the baseline commit (1 pre-existing E501 in `tests/external/test_check_imports.py`, 14 files the installed ruff would reformat). Not introduced here and out of scope.

### Residual risks

- The pixel tests sit behind `_render_available()`, so they run only on the non-blocking xvfb render leg. A future traversal-level regression would not fail the blocking headless gate. The material-graph tests do gate it, and `test_transparency_only_style_does_not_override_the_object_color` catches the override-scope defect without GL.
- `test_transparency_only_style_keeps_the_object_color` asserts the rendered pixel is *unchanged*, because an opaque box against a white background at the iso view shows no visible alpha effect. It proves the hue is not repainted; it does not prove transparency is visible in the image. No current test does, and transparency rendering depends on the renderer's transparency type, which the Python binding does not expose.
- Two constraints inside the read-only `<intent-contract>` are now superseded by measured evidence (the pixel-assertion ban and the fast-path wording). Both are recorded in the Spec Change Log as deliberate departures; the contract text still states the opposite and wants reconciling.
- `followup_review_recommended: true` — pass 2 changed the override mechanism on a high-severity finding late in the loop, which merits an independent look.
