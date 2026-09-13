# UAT Run 2026-09-13-03 — Story 9.1 Regression (TC-15)

Targeted run. Validates the story 9.1 fix against the R2-01 reproducer recorded in run
`2026-09-13-02`. Not a full-suite run: scope is `view_fit_viewport` and the framing verdict.

## Build banner

| Field | Value |
| --- | --- |
| FreeCAD | 1.1.1 |
| Host | GUI addon + auto-spawned H2 proxy on `:8765` |
| FreeCAD pid / window | 27360 / 1641198 |
| FreeCAD start time | 2026-09-13 19:28:54 |
| Addon `view_fit.py` written | 2026-09-13 19:03:51 |
| Addon matches source | yes — `md5sum` equal for `view_fit.py` and `framing.py` |
| `element_map_available` | `true` (version `15.70200.5`) |
| `render` | `gui_constructed` |
| `exec_enabled` | `false` |

**Staleness precondition satisfied:** the process started 25 minutes after the addon files were
written, so it imported the patched modules.

## Summary

| Scenario | Verdict | Notes |
| --- | --- | --- |
| TC-15-01 | **PASS** | 40 mm cube fits in one call; pixels show the whole cube |
| TC-15-02 | **PASS** | 900 mm bar reframed in one call; pixels show the whole bar |
| TC-15-03 | **PASS** | Second fit byte-identical; converged |

R2-01 is **fixed**. No new findings; `bugs.md` is not written for this run.

## The numbers, before and after

Measured on the same 40 mm cube, same host, same tool call.

| Quantity | Run 2026-09-13-02 (defect) | This run |
| --- | --- | --- |
| `status` | `OK` | `OK` |
| `structured_content.fitted` | `true` | `true` |
| `framing.fits` | **`false`** | **`true`** |
| `framing.ratio` | **`1.0978363123236123`** | **`0.949200376293509`** |
| framing warning in `text` | present | absent |
| second consecutive fit | `1.0752587017873942` (drifting) | `0.949200376293509` (identical) |

`0.9492` sits on `_FILL_FRACTION` (0.95). The overflow of roughly 9.8 % is gone.

## Aspect convergence

The retired analytic estimate erred by 1.155x on a cube and 0.856x on a long bar, which is why the
tuning cases passed while ordinary parts clipped. Both aspects now land on one value:

| Model | `framing.ratio` after one fit | `fits` |
| --- | --- | --- |
| 40 x 40 x 40 cube | `0.949200376293509` | `true` |
| 40 x 40 x 900 bar | `0.949200376293509` | `true` |

## Scenario detail

### TC-15-01 — cube fit reports success only when measurably framed

Built a PartDesign Body, a fully constrained 40 x 40 mm sketch on XY (`dof: 0`), padded 40 mm.
Solid verified at `volume 63999.999999999985 mm^3`, `bbox [40,40,40]`, `is_valid: true`,
`tnp: CLEAN`.

One `view_fit_viewport` call returned `OK` / `fitted: true` with `framing: {"fits": true,
"ratio": 0.949200376293509, "checked": "computed"}` and no warning sentence in `text`.

**Visual:** `evidence/tc-15-01-after.png` read and judged. The cube is whole — top vertex near
y=163 with white space above, bottom vertex near y=780 with space below, left edge x=617, right
edge x=1154. Three faces distinguishable (light top, mid-grey left, dark right). No face is cut by
a window border. R2-01's recorded symptom — bottom face cut off, top face nearly touching the
border — does not occur.

### TC-15-02 — a model grown past the frame is reframed, not falsely reported

With the cube framed, `feature_set_parameters` changed `CubePad.Length` to 900 mm, making the model
22x taller than the framed height. That mutation's own envelope carried the warning correctly:
`framing: {"fits": false, "ratio": null, "checked": "computed"}` — `ratio` is `null` because
corners were discarded as implausible, which is AD-32's rule that no ratio beats a fabricated one.

One `view_fit_viewport` call then returned `OK` with `framing.fits: true` and
`ratio 0.949200376293509`. The scenario permits this branch; the forbidden outcome is `OK` beside
`fits: false`, which did not occur.

**Visual:** `evidence/tc-15-02-after.png` read and judged. The bar is whole — top cap near y=163,
bottom near y=780, both inside the viewport with margin, faces shaded, nothing clipped.

### TC-15-03 — repeated fits converge

A second `view_fit_viewport` on the unchanged cube returned `ratio 0.949200376293509`, identical to
the first to 15 decimal places, `fits: true`. The verdict was served `checked: "cached"` naming
geometry as the unverified key component, which is correct AD-32 behaviour for an unchanged camera
and viewport.

**Visual:** `evidence/tc-15-03-after.png` is **byte-identical** to `tc-15-01-after.png`
(`md5 e29f2800b4dd0ca481e81120a188efda`). The camera did not move. R2-01's non-convergence
(`1.0768` then `1.0753`) does not occur.

## Method note

The MCP bridge is the code under test, so its envelope fields are claims, never evidence. Every
scenario's verdict rests on a `cua-driver` capture of the real FreeCAD window, read and judged as a
human would. `query_screenshot` was not used for any assertion — it renders a constructed scene
produced by the actor under test.

## Evidence

| File | What it shows |
| --- | --- |
| `evidence/tc-15-01-after.png` | 40 mm cube, whole, after one fit |
| `evidence/tc-15-02-after.png` | 900 mm bar, whole, after one fit |
| `evidence/tc-15-03-after.png` | Second fit on the cube; identical to the first capture |

## Cleanup

`r3cube` closed without saving. No documents left open. FreeCAD left running.

## Out of scope for this run

- Stories 9.2, 9.3 and 9.4 are unvalidated here. R2-02 (wrong-document guard), R2-03 (white
  axis-aligned renders) and R2-04 (temp-file hygiene) remain open.
- `iso` shading was observed correct in both captures, consistent with R2-03 affecting the
  axis-aligned cameras rather than `iso`. Not asserted — no scenario in TC-15 covers it.
