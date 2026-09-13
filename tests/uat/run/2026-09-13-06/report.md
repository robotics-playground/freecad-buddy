# UAT Run 2026-09-13-06 — Epic 9 Acceptance (TC-15, all scenarios)

Epic 9's stated acceptance is "the four reproducers in `tests/uat/run/2026-09-13-02/bugs.md` re-run
clean, each against the regression fixture its story adds". This run executes every TC-15 scenario
against the shipped code at commit `5b824bc` and settles that claim.

## Build banner

| Field | Value |
| --- | --- |
| FreeCAD | 1.1.1 |
| Host | GUI addon + auto-spawned H2 proxy on `:8765` |
| Commit under test | `5b824bc` |
| FreeCAD pid (main run / post-sweep) | 24584 / 1456 |
| FreeCAD start time | 2026-09-13 20:58:59 |
| Newest addon file | 2026-09-13 20:46:21 |
| Installed addon == source | yes — `md5sum` equal across all 10 epic-9 files |
| External suite | 1094 passed |

**Staleness precondition satisfied:** the process started after every addon file was written.

## Summary

| Scenario | Reproducer | Verdict |
| --- | --- | --- |
| TC-15-01 | R2-01 — fit reports success only when measurably framed | **PASS** |
| TC-15-02 | R2-01 — grown model reframed, not falsely reported | **PASS** (one branch untested, below) |
| TC-15-03 | R2-01 — repeated fits converge | **PASS** |
| TC-15-04 | R2-02 — off-screen fit refused, no camera moved | **PASS** |
| TC-15-05 | R2-02 — guard fires on mismatch only (control) | **PASS** |
| TC-15-06 | R2-03 — every camera renders a visible face | **PASS** |
| TC-15-07 | R2-04 — temp files inside the workdir, sweep scoped | **PASS** |

**7 passed, 0 failed, 0 skipped.** All four reproducers re-run clean. Epic 9 acceptance is met.

## Suite change made by this run

TC-15 covered R2-01 and R2-02 only. R2-03 and R2-04 had no executable scenario anywhere in the
suite — TC-06-02 asserts camera *orientation* and never tone, so it passes against a pure-white
render, and TC-11-13 covers cleanup prefix scope but not the workdir location or the session-start
sweep. **TC-15-06 and TC-15-07 were written in this run** to close that gap, then executed.

## Per-scenario detail

### TC-15-01 — PASS
One fit on a 40 mm cube: `OK`, `fitted: true`, `framing.fits: true`,
`ratio 0.949200376293509`, no warning sentence in `text`. R2-01 recorded `fits: false` with
`ratio 1.0978363123236123` for the same shape.

**Visual:** cube whole, all corners inside the window, margin on every side, no face cut by a
border. R2-01's clipped bottom face does not occur.

### TC-15-02 — PASS, with one branch untested
The pad was grown 40 mm -> 900 mm (22.5x the framed height). The mutation's own envelope carried
`framing {"fits": false, "ratio": null, "checked": "computed"}` and the warning sentence — the
bridge detected the overflow with no fit call involved. One fit then returned `OK` with
`fits: true`.

**Visual:** before the fit, the bar's top was sheared flat by the viewport edge with no cap drawn,
status bar `144.16 mm x 68.81 mm`. After, both square caps are fully drawn with background above
and below, status bar `1693.08 mm x 808.15 mm` — an 11.7x zoom out, whole model framed.

**Untested branch, recorded not waived:** the scenario permits either `OK`-with-`fits:true` or
`SPEC_FAILED`. The fit succeeded, so the `SPEC_FAILED` path never executed and its two assertions
(`detail.code` is `view_fit.not_framed`; the AD-32 carve-out carries a `computed` `framing` block;
the ratio stays out of the prose) are **NOT RUN**. This PASS is not coverage of the carve-out. The
external suite covers it at unit level.

### TC-15-03 — PASS
Two consecutive fits on the unchanged cube: `0.949200376293509` then `0.949200376293509`,
difference exactly `0.0`. R2-01 drifted `1.0768211920529802` -> `1.0752587017873942` and never
converged.

**Camera-movement proof:** the two window captures are **byte-identical**
(`md5 7f03b0e60a12a793e806917314c2e15f`). The second fit moved the camera by zero pixels. This
assertion rests on pixels, not on the reported number.

**Note on the second verdict:** it came back `checked: "cached"` with
`stale_reason "served from cache; unverified key component(s): geometry"`, so the equal ratios are
not two independent measurements. That is correct behaviour and in fact corroborates convergence —
AD-32's cache key includes the camera string, so serving from cache proves the fit wrote an
identical camera. The fit's own pass-3 measurement is always fresh; only the advisory envelope block
is cached.

### TC-15-04 — PASS
Two documents, `docB_bar` focused, fit aimed at `docA_cube`:

```
status: INVALID_INPUT
message: the live viewport is showing 'docB_bar', not the targeted 'docA_cube';
         call view_fit_viewport with the handle for 'docB_bar', or open a 3D view for 'docA_cube'
```

Both documents named. R2-02 returned `fitted: true` here.

**No camera moved:** status bar read `8.68 mm x 4.14 mm` before the call and `8.68 mm x 4.14 mm`
after. R2-02 recorded the defect rescaling that same viewport to `79.39 x 59.55 mm`. Independent
evidence that B was on screen came from `cua-driver list_windows` reporting the title
`"* docB_bar - FreeCAD 1.1.1"`, not from the bridge.

### TC-15-05 — PASS (the control)
A guard that refused everything would pass TC-15-04 while making the tool useless. Fitting the
document that **is** on screen returned `OK` with `fits: true`, both before and after switching
focus to the other document. The guard fires on the mismatch only.

### TC-15-06 — PASS
`front` — the camera R2-03 measured at `rgb(255,255,255)` — rendered and measured with the shipped
`usecases/render_tone.verify_render_tone` oracle, the same one the in-FreeCAD sweep and the fault
suite use:

| Camera | Tone | Difference from background | Coverage | Samples | Verdict |
| --- | --- | --- | --- | --- | --- |
| `front` | `(200.4, 207.2, 213.0)` | 54.6 | 39.9 % | 122,500 | pass |
| `iso` | `(140.7, 144.3, 147.9)` | 114.3 | 66.2 % | 203,244 | pass |

Both clear the two-sided band (>= 24/255 difference on some channel, within `[20, 235]` on every
channel) with empty `reasons`.

**Visual:** the `front` PNG shows a filled grey-blue square clearly separable from the white
background — a shaded face, not an outline around empty space.

`iso`'s absolute tone is deliberately not asserted: the rig trades ambient against the headlight
offset, and the deviation from the live viewport's `rgb(158,165,169)` is recorded in the story 9.3
spec's `deferred` list.

### TC-15-07 — PASS
| Assertion | Expected | Actual |
| --- | --- | --- |
| Render paths inside the workdir | under `<workdir>/tmp` | both, e.g. `C:\Users\thuan\freecad-buddy-workdir\tmp\FCB_TMP_shot_0rkgv7h3.png` |
| OS temp count unchanged | 743 | 743 |
| Workdir holds the renders | 2 | 2 |
| Files survive session exit | 2 | 2 |
| Next session start sweeps them | 0 | 0 |
| Sweep stays out of OS temp | 743 | 743 |

R2-04 counted 392 orphans accumulating one per render; the OS temp directory held 743 at the start
of this run and holds 743 now. The 743 pre-existing strays are operator cleanup and the bridge
correctly leaves them alone.

## Method note

The MCP bridge is the code under test, so its statuses, `framing` blocks and `resource_link` values
are claims under test, never evidence. Every verdict above rests on artifacts produced outside the
bridge's reporting path: `cua-driver` window pixels read and judged directly, `list_windows` titles,
filesystem counts, and a stdlib tone oracle run outside the render path.

Every visual `Then` was executed — each PNG was read, not inferred from MCP fields.

## Deviations

1. **TC-15-04/05 document substitution.** The golden model `box-10-20-30.FCStd` cannot serve as
   document A: its `Box` ships `Visibility=false`, so a fit on it returns `SPEC_FAILED` /
   `view_fit.unverified` with "no visible shape-bearing objects to measure". Both documents were
   built through the tool surface instead. The guard compares document names, not geometry, so the
   substitution does not weaken either scenario.
2. **TC-15-02 model growth.** The scenario text says "padding a second solid"; the existing pad was
   grown to 900 mm instead. Same effect on framing, one solid rather than two.
3. **Extra before-fit captures.** Added in TC-15-02 and TC-15-04. Without them "the fit reframed the
   model" cannot be distinguished from "the model was already framed", so the verdict would be
   unfalsifiable.

## Harness notes for the next runner

- The document tab strip is **not** in the UIA tree — only the property panel's View/Data tabs are.
  Switching documents needs a pixel click, and the coordinates are **screenshot-space** (1568-wide
  PNG), not real window pixels (2560-wide). `invoke_menu ["Windows", ...]` is refused
  `menu_path_unavailable`, and `Ctrl+Tab` has no effect.
- `preview_dry_run`'s schema is `{doc, operation: {tool, args}}`.

## Cleanup

All documents closed; `document_list` reports 0 open. FreeCAD left running (pid 1456). Nothing
removed from the OS temp directory — those 743 files are the control for TC-15-07.
