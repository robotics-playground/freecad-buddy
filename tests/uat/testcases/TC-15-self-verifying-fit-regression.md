# TC-15: Self-Verifying Fit — R2-01 Regression

Proves that `view_fit_viewport` can no longer report `fitted: true` over a viewport its own
measurement says the model overflows. R2-01 (run `2026-09-13-02`) recorded a 40 mm cube returning
`fitted: true` beside `framing: {"fits": false, "ratio": 1.0978}`, with the top vertex and bottom
face visibly clipped. Story 9.1 replaced the analytic silhouette estimate with the shared corner
projection and gated the success envelope on a post-fit re-measurement.

The compact and near-cubic aspects are the point: the shipped estimate underestimated the projected
extent by 1.155x on a cube and 1.132x on a 20x20x30 box, while the elongated bar it was tuned
against passed. A suite that only re-runs the bar would pass against the defect.

**Host**: GUI via H2 proxy. Every scenario needs the live viewport, so none run under H1 headless.

## Preconditions
- [ ] FreeCAD 1.1.1 is running and its process started **after** the addon files were last written
      (verify: compare `Get-Process -Id <pid>` `StartTime` against the `LastWriteTime` of
      `$env:APPDATA\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy\usecases\view_fit.py`)
- [ ] The installed addon matches the source under test
      (verify: `md5sum` of `src/freecad_buddy/usecases/{view_fit,framing}.py` equals the installed copies)
- [ ] No documents are open (verify: `mcp document_list` reports `0 open document(s).`)
- [ ] `cua-driver` daemon is running in an interactive session (verify: `cua-driver status`)
- [ ] `$RUN_DIR` is set to this run's folder under `tests/uat/run/`

---

### TC-15-01: A cube fit reports success only when it is measurably framed

**Priority**: Critical
**Design Ref**: AD-30, AD-31, AD-32; epics.md §Story 9.1 AC1-AC3; source `usecases/view_fit.py:108`

**Given** a new document holding a PartDesign Body  
**And** a fully constrained 40 x 40 mm sketch on XY padded 40 mm, so the solid is a 40 mm cube  
**And** the cube is the aspect R2-01 measured worst, where the retired estimate erred by 1.155x  

**When** `view_fit_viewport { doc: "<handle>" }` is called exactly once  

**Then** the envelope `status` is `OK` — verify: read `status` from the response  
**And** `structured_content.fitted` is `true` — verify: read the field  
**And** the `framing` block reports `fits: true` — verify: read `framing.fits`; this is the
assertion R2-01 failed, where `fits` was `false` beside `fitted: true`  
**And** `framing.ratio` is at or below `1.0` — verify: read `framing.ratio`; R2-01 recorded
`1.0978363123236123`, an overflow of roughly 9.8%  
**And** the response `text` carries no framing warning sentence — verify: the text does not contain
`does not fully fit`  
**And** *(visual)* the viewport captured with `cua-driver` shows the **whole** cube, all eight
corners inside the window, with visible margin on every side and no face cut by a window border
  — verify: `cua-driver call get_window_state` with
  `screenshot_out_file: "$RUN_DIR/evidence/tc-15-01-after.png"`, then `Read` it and judge

**Cleanup**:
```
mcp document_close { doc: "<handle>", save: false }
```

---

### TC-15-02: A fit that cannot frame the model refuses instead of claiming success

**Priority**: Critical
**Design Ref**: AD-31, AD-32 carve-out; epics.md §Story 9.1 AC3-AC4; source `usecases/view_fit.py:372`

**Given** the document and cube of TC-15-01, already fitted and reporting `fits: true`  

**When** the model is grown far past the framed camera by padding a second solid well outside the
current view, without calling the fit again  
**And** `view_fit_viewport { doc: "<handle>" }` is then called once  

**Then** the call either returns `OK` with `framing.fits: true` — the fit reframed both solids —
or returns `SPEC_FAILED` — verify: read `status`; both are correct outcomes, and the forbidden
third is `OK` beside `framing.fits: false`  
**And** if `status` is `SPEC_FAILED`, `detail.code` is `view_fit.not_framed` and the envelope
carries a top-level `framing` block whose `checked` is `computed` — verify: read `detail.code` and
`framing.checked`; AD-32 omits the block on every other non-`OK` status, and this is its single
carve-out  
**And** if `status` is `SPEC_FAILED`, the measured ratio appears nowhere in `text` or
`detail.message` — verify: `str(framing.ratio)` is absent from both strings  
**And** *(visual)* the captured viewport agrees with whichever verdict was returned: whole model in
frame for `OK`, or a model genuinely overflowing the window for `SPEC_FAILED`
  — verify: `cua-driver call get_window_state` with
  `screenshot_out_file: "$RUN_DIR/evidence/tc-15-02-after.png"`, then `Read` it and judge

**Cleanup**:
```
mcp document_close { doc: "<handle>", save: false }
```

---

### TC-15-03: Repeated fits converge instead of restating the same miss

**Priority**: High
**Design Ref**: epics.md §Story 9.1 AC9; source `usecases/view_fit.py:141`

**Given** the document and cube of TC-15-01  
**And** R2-01 recorded two consecutive fits returning `1.0768` then `1.0753`, a model that never
converged because a factor derived from geometry cannot improve by repetition  

**When** `view_fit_viewport { doc: "<handle>" }` is called a second time on the same unchanged model  

**Then** the second call returns `OK` with `framing.fits: true` — verify: read `status` and
`framing.fits`  
**And** the second `framing.ratio` is within `0.01` of the first — verify: compare the two recorded
ratios; a drifting ratio on unchanged geometry means the fit is not converging  
**And** *(visual)* the viewport is framed substantially as it was after the first fit, with the
cube whole — verify: `cua-driver call get_window_state` with
  `screenshot_out_file: "$RUN_DIR/evidence/tc-15-03-after.png"`, then `Read` it and compare
  against `tc-15-01-after.png`

**Cleanup**:
```
mcp document_close { doc: "<handle>", save: false }
```
