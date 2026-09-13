# Fix Plan — UAT Run 2026-09-13-02

Three product defects: two in Epic 8's `view_fit_viewport` (`usecases/view_fit.py`), one in Epic 1's
render lighting (`adapters/render_probe.py`).

R2-01 and R2-02 are **high**: each makes the bridge report success over a window that does not show
what was claimed, which `docs/intent.md` §Validation-First Discipline names as the project's primary
failure mode. R2-03 is **medium** — the render is wrong but says so consistently, and a workaround
(use `iso`) exists. None is a data-loss or safety risk; geometry is never harmed.

## Order of work

1. **R2-02** — small, well-bounded correctness fix with an obvious shape.
2. **R2-03** — independent file, independent reviewer; can run in parallel with R2-02.
3. **R2-01** — needs a geometry decision and new fixtures, and touches the same file as R2-02, so
   land R2-02 first to keep the diffs separable.

---

## R2-02 — The wrong-document guard can never fire

**Defect.** `_require_same_document` (`usecases/view_fit.py:234-250`) compares the target document
against the document the *view it was handed* belongs to. But `GuiViewportPort.view()`
(`hosts/gui_addon/viewport.py:54`) resolves that view with `gui.getDocument(name).ActiveView` —
keyed on the **target's own name**. The two names are therefore always equal and the guard returns
early every time. The condition TC-14-06 describes — the live viewport showing a *different*
document — is never checked.

**The obvious fix is banned — read this before starting.**

Reading `FreeCADGui.ActiveDocument` is **not** available, in any ring. Verified 2026-09-13 by
planting the form in a throwaway tree: `check_imports.py`'s `_check_active_document` runs with **no
layer filter**, so `hosts/` is flagged exactly like `usecases/`:

```
hosts/probe.py:2 -- 'FreeCADGui.ActiveDocument' is banned; operate on the explicit doc handle,
                    never the process-global active document
```

`FREECAD_MODULE_ALIASES` (`check_imports.py:52`) covers `FreeCAD`, `App` and `FreeCADGui`, and
`ACTIVE_DOCUMENT_ATTRS` covers both `ActiveDocument` and `setActiveDocument`. This is story 8.5's
closed gap working as designed.

The two `FreeCADGui.ActiveDocument` strings already in `hosts/gui_addon/viewport.py` (lines 15 and
75) are **docstrings**, not code — the AST check only matches real attribute access. Both say the
port deliberately never falls back to the active document.

**So the fix must identify the on-screen document without naming the banned attribute.** Options,
cheapest first:

1. **Ask the view, not the module.** The viewport port already holds a `View3DInventor` for the
   target. Qt/Gui exposes the *focused* MDI sub-window independently of
   `FreeCADGui.ActiveDocument` — e.g. via the main window's active sub-window and the view it
   hosts. Compare the document that view reports against the target. Stays inside
   `hosts/gui_addon/`, where Qt knowledge is already legal, and names no banned attribute.
2. **Compare view identity rather than names.** Resolve the target's `ActiveView` as today, and
   separately obtain whichever view is frontmost; a mismatch of the two view objects is the
   refusal condition. Avoids document names entirely.

Whichever route: add one `ViewportPort` method (e.g. `showing_document_name() -> str | None`),
implement it in `hosts/gui_addon/viewport.py`, and return `None` when unreadable — an unreadable
answer is not evidence of a mismatch.

Then change `_require_same_document` to compare the target against that value instead of against a
view resolved from the target's own name. Keep the existing message; it already names both
documents and tells the caller what to do. Keep the early return when either name is `None`.

**Do not** relax `check_imports.py` to let the attribute through. The ban is AD-20, and the defect
TC-14-06 catches is the same class of implicit-target bug the ban exists to prevent.

**Verification.**
- Unit: a fake port reporting a different active document makes `view_fit_viewport` raise
  `ValidationError` naming both; a matching one lets the fit through; `None` does not refuse.
- Manual (TC-14-06): open A, then open B so B is active, call `view_fit_viewport` with **A's**
  handle, and confirm the refusal names both. Capture the window and confirm **no camera moved**.

**Watch for.** The guard must not activate or raise the named document to fix the mismatch — AD-31
says the fit is never redirected. Refuse and return; let the caller decide.

---

## R2-01 — The fit leaves compact models clipped

**Defect.** `_fill_factor` (`usecases/view_fit.py:168-191`) estimates the on-screen silhouette as
the largest **face** diagonal over the space diagonal. That estimate is too small for compact
models, so the computed factor zooms in past the point where the model still fits.

Measured overflow after one fit, live:

| Model | ratio | fits |
| --- | --- | --- |
| 40x40x800 bar (the tuning case) | 0.8137 | `true` |
| 20x20x30 box | 1.0768 | `false` |
| 40x40x40 cube | 1.0978 | `false` |

The error is worst for a **cube** — the very shape the comment at `view_fit.py:182-185` cites to
justify the approximation. The tuning cases recorded at `view_fit.py:30-34` (a 40x40x800 bar, a
40x25x15 plate) are both elongated or flat, where the approximation happens to hold, which is why
TC-14-04 passes while ordinary parts fail.

**Fix — preferred.** Measure the silhouette from the **actual projected corner hull** instead of an
analytic estimate. `framing.hull_ratio` (`usecases/framing.py:137-153`) already projects the eight
bbox corners and measures their 2D screen extent; that is the correct quantity, and the fit and the
verdict should share one routine rather than disagreeing.

Sketch: project the corners through the post-orientation camera, take the binding-axis extent, and
choose the factor that lands it at `_FILL_FRACTION` of the viewport. Because `_fit_all` already
orients isometrically before framing (`view_fit.py:128`), the projection is well defined at that
point.

**Fix — fallback.** If sharing the projection proves impractical inside the marshal, then at minimum
`view_fit_viewport` must **stop reporting `fitted: true` when its own post-fit measurement returns
`fits: false`**. Returning success alongside a contradicting measurement in the same envelope is the
part that must not ship. Prefer the real fix; this is a floor, not a target.

**Verification.**
- Add fixtures across the aspect-ratio range, not just the extremes. The analytic underestimate
  ratio (true projected extent / `_fill_factor` estimate) predicts the failures: cube 1.155,
  20x20x30 1.132, 40x40x80 1.095, 40x25x15 0.974, 40x40x800 0.856. **A cube and a 20x20x30 box are
  the cases the current tuning misses — both must be in the suite.**
- Assert TC-14-03's stated band: `0.85 <= framing.ratio <= 1.0` after a single fit.
- Assert idempotence: a second fit does not change the ratio materially. Today two consecutive fits
  on the 20x20x30 box give 1.0768 then 1.0753 — it never converges.
- Manual: fit each fixture, capture the window, and confirm no edge crosses a viewport border.

**Watch for.**
- Do not simply raise `_FILL_FRACTION`; that trades one wrong constant for another and would shrink
  the bar case further (already at 0.8137, below TC-14-03's floor).
- The `40x40x800` bar must stay inside the band after the change — it is the `636fb8a` regression
  guard and currently sits at 0.8137, which is itself **below** TC-14-03's 0.85 floor. A correct
  projection-based fit should bring the bar *up* into the band as well as bringing the cube down.

---

---

## R2-03 — Axis-aligned cameras render an unshaded white silhouette

**Defect.** `_add_lighting` (`adapters/render_probe.py:81-100`) aims a single `SoDirectionalLight`
along the camera's view direction. For an axis-aligned camera the visible face's normal is exactly
anti-parallel to that direction, so the diffuse term is degenerate; only `ambientIntensity` 0.7
remains, which saturates the near-white default material to pure white.

Measured shaded-pixel counts (every 5th pixel, mid-grey fill, excluding background and edges):

| camera | shaded samples |
| --- | --- |
| `iso` | 66789 |
| `front` / `top` / `right` / `back` | ~307 each (edges only) |

**Fix.** Give a camera-facing surface a non-degenerate diffuse term. Either:

- offset the headlight a few degrees off the pure view axis (FreeCAD's own viewport headlight is not
  exactly camera-parallel, which is why the live viewport shades these views correctly); or
- add a second fill light at an angle to the primary.

Keep the measured tone the tuning comment records: a lit face should still read near
`rgb(158,165,169)` (`render_probe.py:95-97`), so the `iso` case must not get brighter.

**Verification.**
- Re-run the pixel count for all seven named cameras plus `custom`. **Every** one must produce a
  shaded interior, not only `iso`.
- Compare a `front` render against a `front` live-viewport capture: FreeCAD shades that view, so the
  render should too.
- Guard against the opposite regression: no face may go black. Assert a tone band rather than
  "not white".

**Watch for.** The docstring at `render_probe.py:82` states the function's purpose as "so no face
renders black". The fix must satisfy both ends — no black face *and* no white-on-white face. A test
asserting only one direction is how this shipped.

---

## Test-suite work (no product change)

Not defects in the product, but the suite cannot run clean until they are fixed.

1. **TC-05 fillet scenarios use a rejected selector.** TC-05-04/05/06/08/09 write
   `edges: [{kind: "geometric", object: "Pad", subelement: "Edge1"}]`. Shipped tools reject it:
   `edges[0] kind must be 'mapped_name'; 'geometric' is not resolvable by a feature tool`
   (`usecases/features.py:141-169` — `geometric` is rejected until a query resolver lands). Rewrite
   as `{kind: "mapped_name", object: "Pad", mapped_name: "Edge1"}`.
2. **TC-14-03's ratio band contradicts the shipped tuning case.** The band is `0.85..1.0`; the
   40x40x800 bar fits correctly at 0.8137. Once R2-01 is fixed, re-derive the band from the fixed
   implementation and check every fixture against it.
