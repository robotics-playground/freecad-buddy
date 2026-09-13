# UAT Run 2026-09-13-04 — Story 9.2 Regression (TC-15-04)

Targeted run. Validates the story 9.2 fix against the R2-02 reproducer recorded in run
`2026-09-13-02`. Scope is the wrong-document guard in `view_fit_viewport`.

## Build banner

| Field | Value |
| --- | --- |
| FreeCAD | 1.1.1 |
| Host | GUI addon + auto-spawned H2 proxy on `:8765` |
| FreeCAD pid / window | 29440 / 1447652 |
| FreeCAD start time | 2026-09-13 20:04:13 |
| Addon matches source | yes — `md5sum` equal for `view_fit.py`, `viewport.py`, `render.py` |
| `element_map_available` | `true` (version `15.70200.5`) |

**Staleness precondition satisfied:** FreeCAD was restarted after the story 9.2 files were written,
so the process imported the patched modules.

## Summary

| Scenario | Verdict | Notes |
| --- | --- | --- |
| TC-15-04 | **PASS** | Off-screen fit refused naming both documents; on-screen camera unmoved |
| TC-15-04 control | **PASS** | Same handle, now on screen, accepted with `OK` |

R2-02 is **fixed**. No new findings.

## The reproducer

`boxA` was created, given a 40 mm cube and fitted (`OK`, `ratio 0.949200376293509`). `otherB` was
then created and became the focused tab. Independent evidence that B was on screen, not the
bridge's own claim: `cua-driver list_windows` reported the window title as
`" otherB - FreeCAD 1.1.1"`.

A fit targeting `boxA` — the document **not** on screen — returned:

```
status: INVALID_INPUT
message: the live viewport is showing 'otherB', not the targeted 'boxA';
         call view_fit_viewport with the handle for 'otherB', or open a 3D view for 'boxA'
```

Both documents named, as AD-31 requires. Run `2026-09-13-02` recorded
`{"fitted": true, "document": "tc14bar", "camera_recorded": true}` for the same situation.

## The camera did not move

`evidence/tc-15-04-after.png` read and judged:

- Active tab is **`otherB : 1`** (bold); `boxA : 1*` sits inactive beside it. Model tree shows
  `otherB` bold. Title bar reads `otherB`.
- The viewport is **empty** and the navigation cube reads **TOP** — `otherB`'s untouched default
  camera.
- The status bar reads **`8.68 mm x 4.14 mm`**.

That last value is the decisive one. R2-02 recorded the defect rescaling the on-screen view "from
`8.68 × 4.14 mm` to `79.39 × 59.55 mm`". The viewport still reads the pre-fit `8.68 × 4.14 mm`, so
the camera the human was watching was not touched.

## The control

After closing `otherB`, `boxA` became the on-screen document again. A fit on the **same handle**
that was just refused returned `OK` with `framing.fits: true` and `ratio 0.949200376293509`. The
guard discriminates on what is actually on screen rather than refusing every call.

## Method note

The MCP bridge is the code under test, so its envelope fields are claims, never evidence. The
verdict rests on the `cua-driver` window capture and on `list_windows`' title, both produced
outside the bridge's reporting path.

## Evidence

| File | What it shows |
| --- | --- |
| `evidence/tc-15-04-before.png` | `boxA` fitted and on screen, before `otherB` was opened |
| `evidence/tc-15-04-after.png` | `otherB` on screen after the refusal; viewport unchanged at 8.68 x 4.14 mm |

## Cleanup

`boxA` and `otherB` closed without saving. No documents left open. FreeCAD left running.

## Out of scope for this run

Stories 9.3 and 9.4 are unvalidated here. R2-03 (white axis-aligned renders) and R2-04 (temp-file
hygiene) remain open.
