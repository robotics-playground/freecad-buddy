---
title: 'Story 8.2: Framing Read — Exact Projection Test'
type: 'feature'
created: '2026-09-12'
status: 'done'
baseline_revision: 'ac0ed6b5398561b58d6518f63ec2746c8c29d63e'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-8-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-8-1-viewportport-contract-gui-host-impl.md'
warnings: [oversized]
deferred:
  - summary: >-
      viewport_port still carries `# noqa: ARG001` in build_inline_handlers; the port is not
      threaded to read_framing because story 8.2 has no tool that consumes a framing verdict.
    evidence: |-
      The spec's Execution task says to thread the port "to the handler factory for the tool(s)
      that read framing", but its own Never list defers the `framing` envelope key to story 8.4
      and the I/O matrix calls read_framing's caller "the 8.4 caller". No tool in this story
      reads framing, so there is no factory to thread it to. The three candidate seams were each
      rejected on inspection: widening HandlerFactory to a 5th positional port is what story 8.1
      explicitly forbade ("~40 unused closures now is speculative; the first consumer threads
      it"); `tool_specs()` takes no arguments and is called from gui_external/entry.py:105 plus
      six test modules, so changing its signature ripples outside this story; and registering
      read_framing as an internal RPC method in the `export_self_read_*` style
      (tool_catalog.py:1350-1365) does not fit, because dispatch requires a ResultEnvelope while
      read_framing returns `FramingVerdict | None`. `usecases/framing.py:read_framing` already
      accepts `viewport_port` as its second positional parameter, so story 8.4 threads the port
      into its envelope-assembly call site with no change to this module.
    location: >-
      src/freecad_buddy/hosts/tool_catalog.py:1279
    severity: medium
---

<intent-contract>

## Intent

**Problem:** `ViewportPort` (story 8.1) can hand back a live 3D view, but nothing answers "is the targeted document's model fully visible in it". Without an exact answer, two implementations would invent different framing tests (bbox-diagonal-vs-camera-height in one, pixel margin in another) and disagree about the same document.

**Approach:** A new `usecases/framing.py` that projects the 8 corners of the union bounding box of visible shape-bearing objects through the view's `getPointOnViewport` and tests containment against `getSize()`. It reuses the render's visibility predicate rather than re-deriving one, and returns the `FramingVerdict` already declared in `contracts/render.py`.

## Boundaries & Constraints

**Always:**
- `fits` is false **iff any** of the 8 corners falls outside the viewport rectangle. Exact, never heuristic.
- The measured object set comes from **the render's own predicate**, promoted to `is_default_renderable` in `usecases/screenshot.py` and imported. Re-deriving a second "visible shape-bearing" filter is a defect (AD-30): it is exactly how the render and the warning end up describing different scenes.
- A coordinate whose magnitude exceeds **4×** the corresponding viewport dimension is treated as **outside** and the coordinate **discarded**. `getPointOnViewport` casts through an unchecked `short()` (`View3DInventorViewer.cpp:3821-3822`), so a distant corner wraps sign and a wrapped value must never read as inside.
- `ratio` is the larger of the two `extent / viewport_extent` quotients over the 2D axis-aligned hull of the 8 projected corners, and is `None` (with `fits: false`) whenever **any** coordinate was discarded.
- Every `fits: None` pairs with `checked: "unavailable"` and a named `stale_reason`. `fits` is never a guess.
- **No `devicePixelRatio` correction.** `getSize()` and the projection share one render-manager pixel space; the DPI divide lives only in `toQPoint`, which this path never calls.
- `usecases/` stays Gui-free: the view arrives as an opaque object from the injected port and is only duck-typed (`getPointOnViewport`, `getSize`). No `FreeCADGui` import.
- Story 8.2 is the first consumer of the `viewport_port` seam, so it threads the port from `build_inline_handlers` to this usecase and removes the `# noqa: ARG001` at `tool_catalog.py:1279`.

**Never:**
- Do **not** build the `framing` envelope key, the shared warning-sentence helper, or the cache — story 8.4. This story computes a verdict on demand; `checked` is `"computed"` or `"unavailable"` only, never `"cached"`.
- Do **not** add `view_fit_viewport` — story 8.3.
- Do **not** "fix" the unclamped projection. Returning coordinates outside `[0,w]×[0,h]` is what makes the containment test possible.
- Do **not** apply a Y-flip. Containment is symmetric in Y; a flip would only matter for a reported pixel coordinate, and none is reported.
- Do **not** widen or alter the `PartDesign::Body` / datum exclusions in the predicate. AD-30 binds the framing read to the render's definition of on-screen, including its known container-visibility limitation.
- Do **not** hold a FreeCAD `BoundBox` for the union. Fold min/max over raw floats so the union step is stdlib-pure and unit-testable with no FreeCAD.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Model fully inside | 8 corners project within `getSize()` | `fits: True`, `checked: "computed"`, `ratio < 1.0`, `stale_reason: None` | No error expected |
| Model overflows | One corner outside the rectangle | `fits: False`, `checked: "computed"`, `ratio > 1.0` | No error expected |
| Corner exactly on the boundary | A coordinate equals `0` or equals `width`/`height` | Treated as **inside** (containment is inclusive) | No error expected |
| Wrapped `short` coordinate | A coordinate magnitude exceeds `4 ×` the viewport dimension | `fits: False`, `ratio: None`, `checked: "computed"` — the coordinate is discarded, not trusted | No error expected |
| No viewport for the document | `viewport_port` is `None`, or `available()` is `(False, reason)` | Returns `None` (no verdict object at all — the block is omitted by the 8.4 caller) | Not an error |
| Projection raises | `getPointOnViewport` or `getSize` throws | `fits: None`, `checked: "unavailable"`, `stale_reason` names the failure | Exception caught |
| Every corner discarded | All 8 corners implausible | `fits: None`, `checked: "unavailable"`, reason names it | Not an error |
| No visible shape-bearing objects | Document empty, or all objects hidden/datum-only | `fits: None`, `checked: "unavailable"`, `stale_reason` names the empty set — never `fits: True` on no geometry | Not an error |
| Zero-extent viewport | `getSize()` returns a `0` dimension | `fits: None`, `checked: "unavailable"` — no division by zero | Guarded before the ratio |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/screenshot.py:51-62` -- `_is_default_renderable`, the predicate AD-30 mandates reusing. Constants at `:47-48`; `_has_shape` at `:242-245`; `__all__` at `:444` is `["query_screenshot"]`. **Promote to `is_default_renderable` and add to `__all__`** — there is no precedent in `src/` for importing a leading-underscore symbol across modules, and establishing one here would be the first. The `PartDesign::Body` exclusion (`:40-46`) is a Coin-fault workaround that narrows the set to shape-bearing leaf features, so the Body's tip is still measured; do not touch it.
- `src/freecad_buddy/usecases/screenshot.py:80-85` -- `query_screenshot(registry, render_port, doc, view)`: the port-as-positional-parameter shape the new usecase copies.
- `src/freecad_buddy/contracts/render.py:79-111` -- `FramingVerdict`; its docstring already pins the three no-verdict states, the `ratio` discard rule and the 4× constant. This story fills it; do not redefine it.
- `src/freecad_buddy/contracts/render.py:130-148` -- `ViewportPort.available(document)` / `.view(document)`, both per document.
- `src/freecad_buddy/hosts/gui_addon/viewport.py:12-56` -- `GuiViewportPort`; `view()` returns `ActiveView` or `None` and never raises.
- `src/freecad_buddy/hosts/tool_catalog.py:1279` -- `viewport_port: ViewportPort | None = None,  # noqa: ARG001 - held for its first consumer`. **This story is that consumer:** thread it and drop the `noqa`. Docstring at `:1288-1291` states the contract.
- `src/freecad_buddy/adapters/render_probe.py:318-323` -- the 8-corner triple-comprehension idiom over `bbox.XMin/XMax`, `YMin/YMax`, `ZMin/ZMax`. Copy the shape, drop the Coin rotation: `getPointOnViewport` takes world coordinates.
- `docs/references/FreeCAD/src/Gui/View3DInventorViewer.cpp:3814-3822` -- `vv.projectToScreen(pt, pt)` then `short(std::roundf(pt[0] * sp[0]))`, unguarded and unclamped. Source proof of the wrap hazard.
- `docs/references/FreeCAD/src/Gui/FreeCADGui._View3DInventor.pyi:283-285, 325-330` -- `getSize() -> tuple[int, int]`, `getPointOnViewport(point) -> _Point2` (a plain 2-tuple of ints via `View3DPy.cpp:1677-1700`).
- `docs/references/FreeCAD/src/Base/BoundBox.pyi:77` -- `XMin`/`XMax`/… are plain float attributes. `united()` exists at `:225` but is unused in this repo; fold raw floats instead.
- `tests/external/test_viewport_port.py:24-67` -- the fake-and-monkeypatch style for this leg, including the adversarial trick of making a forbidden attribute a property that raises.
- `tests/external/test_render_probe.py:27-94` -- `_FakeShape`/`_FakeObject`/`_FakeDocument`/`_FakeRegistry`; `_FakeRegistry.with_document` at `:65` is the registry stand-in.

## Tasks & Acceptance

**Execution:**
- `src/freecad_buddy/usecases/screenshot.py` -- rename `_is_default_renderable` to `is_default_renderable`, update its internal call site, add it to `__all__` -- single-sources the visibility rule without establishing a cross-module private import.
- `src/freecad_buddy/usecases/framing.py` -- new module. A pure `union_bbox(objects)` folding min/max over raw floats; a pure `containment(corners, size)` applying the 4× discard rule and inclusive bounds; a pure `hull_ratio(corners, size)` returning `None` when anything was discarded; and `read_framing(registry, viewport_port, doc)` orchestrating them into a `FramingVerdict` or `None`. Separate module because framing is a distinct concern with a distinct port; folding it into `screenshot.py` would give that module two unrelated reasons to change.
- `src/freecad_buddy/hosts/tool_catalog.py` -- thread `viewport_port` from `build_inline_handlers` to the handler factory for the tool(s) that read framing, and remove the `# noqa: ARG001` -- the seam's first consumer.
- `tests/external/test_framing.py` -- new pytest module covering every I/O matrix row with fakes: a `_FakeView` whose `getPointOnViewport` returns scripted coordinates and whose `getSize` returns a scripted pair, plus fakes for objects/shapes/bbox. Include a fake view that raises, one that returns wrapped coordinates, and one with a zero dimension.

**Acceptance Criteria:**
- Given a document whose visible objects' union bbox projects entirely inside the viewport, when the framing read runs, then `fits` is `True` and `checked` is `"computed"`.
- Given the render's predicate excludes an object, when the framing read measures, then that object is absent from the union bbox — proven by a test that changes only `Visibility` and observes the verdict change, so render and warning describe one scene.
- Given any coordinate beyond 4× its viewport dimension, when the verdict is built, then `fits` is `False` and `ratio` is `None` — a wrapped value never reads as inside and no ratio is fabricated.
- Given a HiDPI-style viewport, when the test runs, then no `devicePixelRatio` factor appears anywhere in the diff.
- Given the whole diff, when reviewed, then `usecases/framing.py` imports no `FreeCADGui`/Qt/pivy, `check_imports.py` passes, and `QT_EXEMPT_ADAPTERS` still holds exactly one entry.

## Spec Change Log

### 2026-09-12 — Port threading moved to story 8.3
- Triggering finding: the spec's Execution list required story 8.2 to thread `viewport_port`
  through `tool_catalog.py` and drop the `# noqa: ARG001`, on the premise that 8.2 is the seam's
  first consumer.
- Amended: that task is not done here. `read_framing` is called by story 8.4's envelope assembly,
  not by a handler factory, so threading the port through the ~11 `make_handler` signatures now
  would leave it unused a second time. Story 8.3's `view_fit_viewport` is an actual tool whose
  handler needs the port, so it threads it.
- Known-bad state avoided: churning 11 factory signatures twice, and a second round of
  `# noqa: ARG001` suppressions on a still-unused argument.
- KEEP: the pure/impure split in `usecases/framing.py` (`union_bbox`, `corners`, `containment`,
  `hull_ratio` are all FreeCAD-free and directly unit-testable) must survive re-derivation.

## Review Triage Log

## Design Notes

**Why a `None` return rather than a verdict for "no viewport".** AD-32 state 1 says the block is *omitted entirely*, not reported as `unavailable`. Returning `None` lets story 8.4's envelope assembly omit the key without inspecting field values, and keeps `checked: "unavailable"` meaning exactly one thing: a viewport existed and the projection failed.

**Why the empty set is `unavailable`, not `fits: True`.** Vacuously "everything fits" when there is nothing to fit would tell an agent its work is visible when the viewport may be showing nothing at all. AD-32 forbids a guess; an empty measurement set is a reason the verdict could not be computed.

**Containment is inclusive.** A corner at exactly `x == width` is the last visible pixel column, not the first invisible one. Exclusive bounds would report `fits: false` for a model framed perfectly to the edge.

## Verification

**Commands:**
- `uv run python scripts/check_imports.py` -- expected: `check_imports OK`. Proves `usecases/framing.py` stayed Gui-free.
- `uv run python scripts/gen_schemas.py --check` -- expected: `gen_schemas --check OK`. `FramingVerdict` is still not embedded in a schema in this story; drift here means the envelope key was added early (story 8.4's work).
- `uv run pytest tests/external/test_framing.py tests/external/test_viewport_port.py -q` -- expected: all pass.
- `grep -rn "_is_default_renderable" src/ tests/` -- expected: no hits. The predicate has exactly one internal call site (`screenshot.py:238`); a leftover underscore reference means the rename was partial. `dist/addon/` is build output and is not renamed.
- `uv run pytest tests/external -q` -- expected: no regressions.
- `uv run ruff check .` -- expected: 9 pre-existing errors, none in a file this diff touches.
