---
title: 'Tighten focus framing and signal the empty scene in the offscreen render port (DW-45, DW-48)'
type: 'bugfix'
created: '2026-07-29'
status: 'done'
baseline_revision: '9b6856d'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
---

<intent-contract>

## Intent

**Problem:** Two scene-construction edges on the shared `_aim_camera` path in
`src/freecad_buddy/adapters/render_probe.py`.

**DW-45 — focus framing is systematically loose.** `_frame_bbox` (l289-301) builds a `SoCube`
sized to the grown bbox and calls `camera.viewAll(proxy, viewport)`. Coin's `viewAll`
**circumscribes a sphere** around whatever it is given — FreeCAD's own source says so at
`docs/references/FreeCAD/src/Gui/View3DInventorViewer.cpp` l4570-4572: *"SoCamera::viewBoundingBox()
is not accurate as well. It uses a sphere to surround the bounding box for easy calculation."* So the
effective camera height is the bbox **space diagonal**, not the requested 20% margin, and the error
grows with bbox anisotropy. Measured in-FreeCAD (1.1.1) on a 10x20x30 bbox: `viewAll` yields camera
height `37.417` for *every* orientation (= `sqrt(10^2+20^2+30^2)` = 37.4166, orientation-invariant,
which is itself proof it is a sphere), while the tight top-view framing is `20.0`. The bbox occupies
53% of the frame instead of the intended 83%: a **1.56x overshoot** on that view.

**DW-48 — an all-skipped render returns a blank PNG as OK.** `render` (l161-174) appends nothing to
`root` when every requested object is missing or has no subgraph; `_aim_camera` then falls through to
`camera.viewAll(root, viewport)` over a graph holding only a camera and a light. The renderer writes a
uniformly white PNG, the non-empty-file check passes, and the caller receives `status: OK` with a
`resource_link` to a blank image and `rendered_objects: []`. Nothing in the response says the scene was
empty. Reachable today with a genuinely empty document (an all-nonexistent `include` is already rejected
upstream by `_require_object`).

**Approach:** (1) Replace the proxy-cube framing with a direct computation: rotate the eight bbox corners
into the camera frame (`orientation.inverse()`), take the extents there, and set `height` /`position`
/near/far from those spans, honoring the viewport aspect. (2) Give the render port an explicit empty-scene
signal: when no geometry was added, skip the render entirely, write no PNG, and return that fact on the
wire as `render.empty_scene: true` with `resource_link: null`, keeping `status: OK` (an empty document is
valid input, not an error — the same posture the existing `render.available: false` path already takes).

## Boundaries & Constraints

**Always:**
- Keep the degenerate-axis clamp semantics from DW-50: a projected span of zero must not produce a zero or
  NaN camera height. The clamp moves to the projected extent (`max(span, 1e-3)`), which is where the
  degeneracy actually lands once framing is computed in the camera frame rather than from raw
  `bbox.XLength`/`YLength`/`ZLength`.
- `grow = 1.2` stays the margin factor, and it must now mean what it says: the framed bbox spans
  `1/1.2 = 0.8333` of the frame along its binding axis.
- Aspect handling follows Coin's actual semantics, verified in-process: `cam.height` **is** the world
  height and world width is `height * aspect`. The width constraint therefore binds only when
  `aspect < 1`; `height = max(span_y, span_x / aspect)` covers both.
- The empty-scene path stays `status: OK`. `contracts/status.py` owns a closed 7-member terminal set and
  none of them means "nothing to draw"; inventing one is an AD-17 violation.
- `render_probe.py` keeps every `FreeCADGui`/`pivy`/Qt import function-local (AD-1 carve-out).
- New tests live in `tests/infc/` under stdlib `unittest` (AD-12). Framing assertions are pure Coin math
  and must run **unguarded** by `_render_available()`; only assertions that actually rasterize keep the skip.

**Block If:**
- `SbRotation.inverse()` or `SoOrthographicCamera.height`/`position`/`nearDistance`/`farDistance` is absent
  from the bundled pivy — the computation has no API to stand on. (Verified present on FreeCAD 1.1.1 during
  planning; re-probe rather than assume on another leg.)

**Never:**
- Do not use `SoCamera.viewBoundingBox()` as the fix. It is bound in pivy, but FreeCAD's own source
  documents it as carrying the *same* sphere-circumscription looseness this spec exists to remove.
- Do not change `_focus_bbox`, `_sub_shape`, `_indexed_sub_shape`, `_mapped_sub_shape`, or the
  `RenderResult.focused` semantics — sub-element *resolution* is correct; only the framing math is wrong.
- Do not change the whole-scene (`focus is None`) path to the new math. `viewAll` over the real scene graph
  is correct there: it frames actual geometry, and a scene-wide sphere margin is not what DW-45 reports.
- Do not touch the DW-44 camera preset table, the lighting, or the MSAA preference mapping.
- Do not emit a blank PNG "as well as" the empty-scene flag, and do not leave a temp file behind on that path.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| focus on a face, square viewport | 10x20x30 box, `top`, 1920x1920 | camera height `24.0` (= 20.0 * 1.2), bbox spans 0.8333 of frame | no error |
| focus, wide viewport | same, 1920x1080 | height still `24.0` — width does not bind when `aspect > 1` | no error |
| focus, tall viewport | same, 1080x1920 | height grows to `span_x / aspect` when that exceeds `span_y` | no error |
| focus on a flat face | zero-thickness bbox | frames the two non-zero axes; zero depth clamped, no NaN | no error |
| focus on an edge seen end-on | all projected spans ~0 | height clamps to `1e-3`, render still produces a PNG | no error (DW-50 preserved) |
| focus bbox off-origin | bbox centered at (105,-40,20) | framing identical to the origin-centered case (translation-invariant) | no error |
| empty document, no include | `document.Objects == []` | `OK`, `render.empty_scene: true`, `resource_link: null`, `rendered_objects: []`, no PNG written | no error |
| every requested object skipped | include names resolve to no subgraph | same as above | no error |
| normal render | >=1 object added | `empty_scene: false`, `resource_link` set — unchanged today's behavior | no error |
| render unavailable | ladder reports `none` | `available: false` + reason — unchanged | no error |

</intent-contract>

## Code Map

- `src/freecad_buddy/adapters/render_probe.py`
  - `_frame_bbox` (l289-301) -- **replace** the proxy-cube body with corner projection.
  - `_aim_camera` (l212-225) -- unchanged control flow; only the `_frame_bbox` call site benefits.
  - `render` (l137-187) -- add the empty-scene early return before the renderer runs.
- `src/freecad_buddy/contracts/render.py` -- `RenderResult` (l63-73) gains an `empty_scene` flag; default
  `False` keeps it additive (AD-17: additive-only within a major).
- `src/freecad_buddy/usecases/screenshot.py`
  - `_render_with_lifecycle` (l150-175) -- must not demand a non-empty PNG when the port reports an empty scene.
  - `query_screenshot.read` (l96-130) -- carries `empty_scene` into `structured.render`, drops `resource_link`
    and the `images` key on that path.
  - `summarize_screenshot` (l390-398) -- says so in the one-line text mirror.
- `docs/references/FreeCAD/src/Gui/View3DInventorViewer.cpp` -- authority for the sphere-circumscription
  claim (l4570-4572) and for FreeCAD's own bbox framing entry point `viewBoundBox` (l4819-4840).
- `tests/infc/test_screenshot.py` -- in-FreeCAD suite; `_render_available()` (l28) is the GL skip guard.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/contracts/render.py` -- add `empty_scene: bool = False` to `RenderResult` with a
  docstring line -- the port needs a way to say "nothing drawable" that is not an exception.
- [x] `src/freecad_buddy/adapters/render_probe.py` -- rewrite `_frame_bbox` to project the eight bbox corners
  through `camera.orientation.getValue().inverse()`, derive `height` from the in-frame spans and the viewport
  aspect, and set `position`/`nearDistance`/`farDistance`/`focalDistance` from the depth span -- removes the
  sphere-circumscription looseness that is DW-45.
- [x] `src/freecad_buddy/adapters/render_probe.py` -- in `render`, return
  `RenderResult(rendered_objects=[], focused=False, empty_scene=True)` before constructing the renderer when
  `rendered` is empty -- no blank PNG is written at all.
- [x] `src/freecad_buddy/usecases/screenshot.py` -- skip the non-empty-PNG assertion and remove the unused temp
  file when the port reports `empty_scene`; emit `empty_scene` in `structured.render`, leave `resource_link`
  `None`, omit `images`, and give `summarize_screenshot` an empty-scene sentence.
- [x] `tests/infc/test_screenshot.py` -- add `FocusFramingTest` covering every framing row of the I/O matrix by
  calling `_frame_bbox` directly against a real Coin camera and asserting the projected screen occupancy is
  `1/1.2` within tolerance -- an occupancy assertion is falsifiable by the old proxy code, a height assertion
  alone is not.
- [x] `tests/infc/test_screenshot.py` -- add an empty-document render test asserting `OK`, `empty_scene: true`,
  null `resource_link`, no `images` key, and that no temp PNG survives.
- [x] `src/freecad_buddy/adapters/render_probe.py` -- floor the *depth* span as well as the height -- a bbox flat
  along the view axis collapsed `nearDistance` onto `farDistance`, giving a zero-thickness view volume. Caught by
  `test_degenerate_bbox_keeps_a_positive_finite_height` during the first suite run.

**Acceptance Criteria:**
- Given a 10x20x30 box focused whole-object at `top` on a 1920x1920 viewport, when `_frame_bbox` runs, then the
  camera height is `24.0 +/- 1e-3` and the bbox occupies `0.8333 +/- 1e-3` of the frame's binding axis.
- Given the pre-fix proxy-cube implementation is restored, when `FocusFramingTest` runs, then it fails (the
  suite is falsifiable against the exact defect, not merely green).
- Given a bbox degenerate on one axis viewed end-on, when `_frame_bbox` runs, then the camera height is finite,
  positive, and >= `1e-3`, and the render still writes a PNG.
- Given an empty document, when `query_screenshot` runs with a render context present, then the envelope is
  `OK` with `render.empty_scene: true`, `render.resource_link: null`, no `images` key, and no temp file left on disk.
- Given a document with at least one shape-bearing object, when `query_screenshot` runs, then `empty_scene` is
  `false` and a non-empty PNG is linked — today's behavior is unchanged.

## Spec Change Log

- Added a depth floor to `_frame_bbox` (task 7). Not in the original task list: the spec's clamp reasoning
  covered the projected *height* only, and a bbox flat along the view axis was left with `near == far`. The
  degenerate-bbox acceptance criterion already required a valid camera, so this closes the spec as written
  rather than widening it.

## Review Triage Log

### 2026-07-29 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 1 (high 1, medium 0, low 0)
- defer: 2 (high 0, medium 1, low 1)
- reject: 0
- addressed_findings:
  - `[high]` `[patch]` Zero-depth view volume on a bbox flat along the view axis (`near == far == 1e-3`),
    which renders nothing. Found by the new degenerate-bbox test on the first run, before any review pass.
    Fixed by flooring the depth span, not by loosening the assertion.
- deferred (reported to the orchestrator, ledger not edited per invocation constraint):
  - `[medium]` A `focus` resolving to a single **vertex** still frames a singularity: the point bbox drives
    the camera height to the `1e-3` floor, so the surrounding box projects ~21,000x the frame. Measured
    in-FreeCAD. This is **DW-50**, which is still `status: open` in the ledger — the clamp it asks for exists
    and prevents a crash/NaN, but its "frames a sensible neighborhood" requirement is unmet. Out of scope for
    this bundle (DW-45/DW-48), and the bundle intent explicitly directed preserving the clamp as-is.
  - `[low]` `subgraphs` in `OffscreenRenderPort.render` is populated and never read — a pre-existing dead
    local, present at `HEAD`, untouched by this change and left alone per the surgical-changes rule.

## Design Notes

### Why not `SoCamera.viewBoundingBox()`

FreeCAD's `View3DInventorViewer::viewBoundBox` (l4819-4840) ends in `cam->viewBoundingBox(box, aspectratio, 1.0)`,
so it looks like the sanctioned fix. It is not: l4570-4572 of the same file states `viewBoundingBox()` "is not
accurate as well. It uses a sphere to surround the bounding box for easy calculation." Adopting it would swap one
sphere-circumscribed framing for another and leave DW-45 open. The corner projection is the only approach that
makes `grow` mean the requested margin.

### Measured framing (FreeCAD 1.1.1, headless `freecadcmd`)

Camera height from `viewAll` on the proxy cube vs. the corner-projection formula, `grow = 1.2`:

| bbox | view | proxy `viewAll` | corner projection | proxy overshoot |
|---|---|---|---|---|
| 10x20x30 | `top` | 37.417 | 24.000 | 1.56x |
| 10x20x30 | `front` | 37.417 | 36.000 | 1.04x |
| 10x20x30 | `iso` | 37.417 | 44.091 | 0.85x (proxy *under*-frames) |
| flat 10x20 face | `front` | 22.361 | 12.000 | 1.86x |

The proxy height is identical across all three orientations of the same bbox — the signature of a sphere. Note the
`iso` row: the proxy does not merely over-zoom, it *clips* on some views (0.85x means the geometry is larger than
the frame), so this is a correctness fix, not only a tightness one.

### The formula

With `inv = camera.orientation.getValue().inverse()`, project all eight corners, then:

```
span_x = (max(xs) - min(xs)) * grow
span_y = (max(ys) - min(ys)) * grow
span_z =  max(zs) - min(zs)
height = max(span_y, span_x / aspect, 1e-3)      # aspect = width / height
```

`cam.height` is the world height and world width is `height * aspect` (verified: at `height=20`, a 1920x1080
viewport yields a view volume of 35.556 x 20.000, a 1080x1920 one 11.250 x 20.000). Hence `span_x / aspect` only
binds on tall viewports, matching Coin's own `viewAll`, which raised height from 37.417 to 66.518 for 1080x1920
and left it unchanged for 1920x1080.

The camera sits at `center - view_dir * (span_z / 2 + height)`, clear of the geometry for any orientation; near/far
bracket the depth span. Validated against `SbViewVolume.projectToScreen` over 3 orientations x 3 viewports x 4 bbox
shapes: the binding-axis screen span is `0.8333` in every non-degenerate case (the flat-face-end-on cases correctly
hit the clamp).

### Empty scene as OK, not a terminal status

`contracts/status.py` owns a closed set (`OK|SPEC_FAILED|RECOMPUTE_ERROR|TIMEOUT|OOM_KILLED|WORKER_CRASHED|
INVALID_INPUT`) and `scripts/check_status_vocab.py` fails the build on any `Literal` redefining it. None means
"nothing drawable", and an empty document is valid input — `SPEC_FAILED`/`INVALID_INPUT` would both be wrong. The
existing `render.available: false` branch already sets the precedent: `OK` plus a structured flag plus no image.
`empty_scene` follows it exactly, and being an additive optional field it is a legal within-major schema evolution.

## Verification

**Commands:**
- `freecadcmd tests/run_tests.py` -- expected: whole `tests/infc/` suite green; `FocusFramingTest` reported run,
  not skipped.
- Falsifiability: restore the proxy-cube `_frame_bbox`, re-run, confirm `FocusFramingTest` fails; then restore.
- `python scripts/check_imports.py` -- expected `check_imports OK`.
- `python scripts/check_status_vocab.py` -- expected exit 0 (no new status literal).
- `python scripts/gen_schemas.py` (or the documented drift check) -- expected: byte-identical, since `RenderResult`
  is not a generated wire schema.
- `uv run pytest tests/external/test_render_probe.py tests/external/test_mcp_surface.py tests/external/test_contracts.py`
  -- expected green.
- `uv run ruff check src tests` / `ruff format --check` -- expected: no new findings on the touched files.

**Manual checks (if no CLI):**
- If `freecadcmd` is unavailable, state the in-FreeCAD leg was not executed; do not claim it passed.

## Auto Run Result

Status: done

**Implemented change.** Replaced the `SoCube`-proxy framing in `_frame_bbox` with a direct corner projection
into the camera frame, and gave the render port an explicit empty-scene signal so an all-skipped render no
longer returns a blank PNG as `OK`.

The root cause of DW-45 is confirmed from FreeCAD's own source, not inferred: `View3DInventorViewer.cpp`
l4570-4572 states `SoCamera::viewBoundingBox()` "is not accurate as well. It uses a sphere to surround the
bounding box." `viewAll` over the proxy cube has the same behavior, which is why the measured camera height was
`37.417` for a 10x20x30 bbox on *every* orientation — exactly its space diagonal. That orientation-invariance is
the fingerprint of a sphere. This also means the old code did not merely over-zoom: on `iso` it produced 0.85x,
i.e. it **clipped** the geometry. So DW-45 was a correctness bug, not only a tightness one.

**Files changed.**
- `src/freecad_buddy/contracts/render.py` — `RenderResult.empty_scene` (additive, defaults `False`).
- `src/freecad_buddy/adapters/render_probe.py` — `_frame_bbox` rewritten; empty-scene early return in `render`;
  `_FRAME_GROW`/`_MIN_FRAME_EXTENT` module constants.
- `src/freecad_buddy/usecases/screenshot.py` — empty-scene lifecycle (temp file removed, `out_path` `None`),
  `empty_scene` on the wire, `images` key omitted when there is no image, summary sentence.
- `tests/infc/test_screenshot.py` — `FocusFramingTest` (7 tests) + `EmptySceneTest` (2 tests).

**Verification.** All run in this environment against `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`
(FreeCAD 1.1.1, render capability `offscreen`):
- `freecadcmd tests/run_tests.py` — `Ran 124 tests ... OK (skipped=1)`. The single skip is the pre-existing
  render-unavailable case (this machine has a render context).
- **Falsifiability proven for both defects.** Restoring the proxy-cube `_frame_bbox` behind a temporary env
  flag → 4 failures (`test_bbox_fills_the_requested_fraction_of_the_frame`, `test_flat_bbox_frames_its_two_real_axes`,
  `test_framing_varies_with_orientation`, `test_top_view_height_is_the_grown_in_plane_extent`). Disabling the
  empty-scene return → 1 failure (`test_empty_document_reports_empty_scene_without_an_image`). The hooks were
  removed and the file byte-compared against the verified version afterward.
- **End-to-end pixel check** (beyond the Coin-math assertions): rendered real PNGs and measured the non-white
  ink extent. `focus whole object` occupies **0.8333** of the frame vertically — the requested margin, measured
  in actual pixels. Every focus mode produced a non-blank image with nothing clipped.
- Sub-element framing verified against the *target*: `edge 0` and `face 0` each span 0.8333 of the frame. (A
  raw full-image ink reading of ~1.0 for edge focus is the rest of the box extending past the frame, which is
  correct behavior when zooming into a sub-element.)
- `python scripts/check_imports.py` — `check_imports OK`.
- `uv run python scripts/check_status_vocab.py` — `check_status_vocab OK` (no new status literal).
- `uv run python scripts/gen_schemas.py --check` — `gen_schemas --check OK` (no wire-schema drift).
- `uv run pytest tests/external/test_render_probe.py test_mcp_surface.py test_contracts.py test_tool_summaries.py`
  — `131 passed`.
- `uv run ruff check` on the four changed files — `All checks passed!`. Full-tree `ruff check src tests` reports
  1 error, `tests/external/test_check_imports.py:302` E501, in an untouched file. `ruff format --check`: the
  remaining hunks on `screenshot.py` and `test_screenshot.py` reproduce identically on the unmodified `HEAD`
  copies (verified by extracting both from git and re-running), so they are pre-existing and were left alone.

**Residual risks.** The framing is verified against Coin's own view volume and against rendered pixels, but no
golden-image baseline exists, so a future change to lighting/MSAA would not be caught by these tests. Vertex
focus remains degenerate (DW-50, still open — see the Review Triage Log). Pyright reports pre-existing
diagnostics in all touched files (unresolvable `FreeCAD`/`pivy` imports outside the FreeCAD interpreter,
untyped document handles); none originate from this change.
