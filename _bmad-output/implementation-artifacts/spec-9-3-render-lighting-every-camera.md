---
title: 'Story 9.3: Every Camera Renders a Visible Part'
type: 'bugfix'
created: '2026-09-13'
status: 'done'
baseline_revision: '306aa7bd569a3faacbe2ece8585730a6959bcf4f'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-9-context.md'
warnings: [ac-deviation-iso-tone]
deferred:
  - summary: >-
      The iso render is darker than the live viewport: measured (141,144,148) against the spec's
      stated target of rgb(158,165,169).
    evidence: |-
      AC "iso must still read near rgb(158,165,169)" is not met. The implementer established by
      measurement that it cannot be met alongside the band: ambient and the headlight offset trade
      against each other, and raising ambient to restore iso pushes the axis-aligned views up
      nearly one-for-one -- at 0.95, `right` measured 241.6 on blue, over the 235 ceiling. Light
      intensity is already 1.0 and does not separate them. The band is AD-34's invariant and the
      iso value was a fidelity nicety, so the ceiling was chosen and the reasoning recorded in
      adapters/render_probe.py. Settled by either accepting the darker iso or finding a rig with a
      third degree of freedom (per-light intensity, or a second light with its own colour).
    location: >-
      src/freecad_buddy/adapters/render_probe.py
    severity: low
---

<intent-contract>

## Intent

**Problem:** `_add_lighting` aims a single `SoDirectionalLight` **along** the view direction. For
an axis-aligned camera the visible face's normal is exactly anti-parallel to that light, so the
diffuse term degenerates and only `ambientIntensity` 0.7 remains, which saturates the near-white
default material to pure white. R2-03 measured `front`, `top`, `right` and `back` rendering the
face at `rgb(255,255,255)` — identical to the background, so the PNG carries no shape information
beyond its outline. `iso` renders correctly at `rgb(159,164,169)`.

**Approach:** Offset the headlight off the pure view axis (or add a second fill light at an angle)
so a face whose normal is anti-parallel to the camera still receives a diffuse term, and replace
the one-sided acceptance test with a two-sided tone band plus a sample-count floor.

## Boundaries & Constraints

**Always:**
- Every named camera **plus `custom`** must render a face tone separable from the background.
- The acceptance test is **two-sided**: mean interior tone differs from the background by
  **>= 24/255 on at least one channel** *and* lies within **`[20, 235]` on every channel**.
- Interior sampling excludes the outer **10 %** of the span on each axis and requires
  **>= 500 interior samples**. The `front` defect yielded only ~138 samples, all anti-aliased edge
  pixels, so the floor is part of the assertion, not a harness detail.
- `iso` must still read near `rgb(158,165,169)`. The fix must not brighten the case that already
  matches the live viewport.
- The render is a validator under AD-13: a planted all-white render must be caught by the fault
  suite, not only by a human spot-check.
- `design/integration-mcp-freecad.md:306` is updated in the same change. It still specifies a bare
  `coin.SoDirectionalLight()` with no aiming and no ambient — the shipped divergence was never
  recorded, which is why it was never reviewed.

**Never:**
- Do not assert only "not black". That one-sidedness is exactly how this shipped: the existing
  docstring states the purpose as "so no face renders black", it closed the black end and opened
  the white end, and a "not black" test passes the current defect.
- Do not assert only "not white" either — that would re-admit the original black-face defect.
- Do not change the camera orientations, the framing, or `_FRAME_GROW`. This story changes
  lighting and its test only.
- Do not widen the Qt/pivy import carve-out: `adapters/render_probe.py` is already the one ring
  outside `hosts/` allowed those imports, and every import stays function-local.
- Do not tune `ambientIntensity` alone to escape the white end. Ambient without a diffuse term is
  the flat-tone failure; the light geometry is the fix.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Axis-aligned cameras | Golden box rendered from `front`, `top`, `right`, `back`, `left`, `bottom` | Mean interior tone passes the two-sided band | No error expected |
| Isometric | Same box from `iso` | Passes the band **and** stays near `rgb(158,165,169)` | No error expected |
| Custom orientation | `custom` with an explicit quaternion | Passes the band | No error expected |
| Sample floor | Interior region yields < 500 samples | Test **fails** rather than passing on edge pixels | Assertion failure names the count |
| Planted all-white render | Fault-injection case | Caught mechanically by the suite | Detected, not silently passed |
| No GUI stack | Headless interpreter | Unchanged capability answer | Existing reason preserved |

</intent-contract>

## Code Map

- `src/freecad_buddy/adapters/render_probe.py:81` -- `_add_lighting(coin, root, orientation)`, the
  defect. `:91` computes `view_dir` as the orientation quaternion applied to the camera's default
  `-Z` look axis; `:92-93` creates one `SoDirectionalLight` and aims it **along** that vector;
  `:94-98` adds `SoEnvironment` with `ambientIntensity` 0.7. The docstring at `:82` states the
  one-sided goal ("so no face renders black") and must be rewritten with the new invariant.
- `src/freecad_buddy/adapters/render_probe.py:95-97` -- the tuning comment recording the measured
  `rgb(158,165,169)` viewport tone and the `~159,164,169` the current ambient reproduces. This is a
  measured constant with its justification; keep the measurement, update it if the value moves.
- `src/freecad_buddy/adapters/render_probe.py:20` -- `_ACCENT_COLOR`; `:24-27` `_FRAME_GROW` and
  `_MIN_FRAME_EXTENT`; `:31-36` the MSAA preference mapping. All read-only here.
- `_bmad-output/planning-artifacts/architecture/.../design/integration-mcp-freecad.md:306` -- the
  `render_offscreen` sketch. Its line `root.addChild(camera); root.addChild(coin.SoDirectionalLight())`
  specifies a bare unaimed light with no ambient. Update it to the rig this story lands.
- `tests/infc/test_screenshot.py` -- the in-FreeCAD suite (runs under `FreeCADCmd` with stdlib
  `unittest` via `run_tests.py`, never pytest). A render test needs a real GUI stack, so the
  camera sweep belongs here rather than in `tests/external/`. Check what it already asserts about
  rendered output before adding, and reuse its golden-box fixture if one exists.
- `benchmarks/g0/fault-injection/` -- the planted-defect suite. The all-white render case joins it;
  read a neighbouring case for the manifest shape and the validator registry entry it needs.
- `benchmarks/_registry/validators.yaml` -- validator provenance. A render validator whose
  sensitivity changes may need its recorded bar refreshed; read before editing.

## Tasks & Acceptance

**Execution:**

- `src/freecad_buddy/adapters/render_probe.py` -- change `_add_lighting` so the diffuse term
  survives an axis-aligned camera: offset the headlight off the pure view axis, or add a second
  fill light at an angle. Rewrite the docstring to state the two-sided invariant rather than "so no
  face renders black" -- a rig documented one-sidedly is how the white end opened unnoticed.
- `src/freecad_buddy/adapters/render_probe.py` -- if the ambient value changes, update the tuning
  comment with the newly measured tone and how it was measured; a tuned constant without its
  measurement gets retuned blind by the next reader.
- `tests/infc/test_screenshot.py` -- add the camera sweep: render the golden box from every named
  camera plus `custom`, sample the interior excluding the outer 10 % per axis, require >= 500
  samples, and assert the two-sided band (>= 24/255 difference from background on at least one
  channel, and within `[20, 235]` on every channel). Assert separately that `iso` stays near
  `rgb(158,165,169)` -- the sweep proves separability, this pins the one case already correct.
- `benchmarks/g0/fault-injection/` -- add the planted all-white render case so AD-13 catches this
  class mechanically; register it wherever its neighbours are registered.
- `_bmad-output/planning-artifacts/architecture/.../design/integration-mcp-freecad.md` -- update the
  `render_offscreen` sketch's lighting line to the shipped rig -- the divergence was never recorded,
  which is why it was never reviewed.

**Acceptance Criteria:**

- Given the golden box rendered from each named camera and `custom`, when the interior is sampled,
  then every render passes the two-sided band with at least 500 interior samples.
- Given the `front` camera specifically, when its interior is sampled, then the mean tone is no
  longer `rgb(255,255,255)` and differs from the background by at least 24/255 on some channel.
- Given the `iso` camera, when its interior is sampled, then the tone is still near
  `rgb(158,165,169)` -- the fix brightened nothing that was already right.
- Given a test that asserts only "not black", when run against the fixed rig, then it still passes
  -- proving the fix did not close the white end by opening the black one.
- Given `grep -n "so no face renders black" src/freecad_buddy/adapters/render_probe.py`, when the
  change is done, then it returns nothing.
- Given the design doc, when read at the `render_offscreen` sketch, then its lighting line matches
  the shipped rig.

## Verification

**Commands:**
- `uv run ruff check src/freecad_buddy/adapters/render_probe.py` -- expected: clean.
- `uv run pytest -q` -- expected: no new failures; the external suite does not cover the GUI render.
- In-FreeCAD suite: run `tests/infc/` the way `run_tests.py` drives it under `FreeCADCmd` --
  expected: the new camera sweep passes. Read `scripts/` or the test plan for the exact invocation
  before running; do not invent one.
- `uv run python scripts/check_imports.py` -- expected: clean; no new top-level Qt/pivy import.

**Manual checks (if no CLI):**
- The live-GUI reproducer (R2-03) is a UAT step: `query_screenshot` from `front` on a golden box
  must produce a PNG whose face is visibly distinguishable from the background. The agent reads the
  PNG and judges the pixels; an MCP render is the actor grading itself and is corroborating
  evidence only.
