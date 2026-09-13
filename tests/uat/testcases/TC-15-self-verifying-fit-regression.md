# TC-15: Self-Verifying Fit — R2-01 and R2-02 Regressions

Proves that `view_fit_viewport` can no longer report `fitted: true` over a viewport its own
measurement says the model overflows, and can no longer move the camera of a document the human is
not looking at. R2-01 (run `2026-09-13-02`) recorded a 40 mm cube returning `fitted: true` beside
`framing: {"fits": false, "ratio": 1.0978}`, with the top vertex and bottom face visibly clipped.
Story 9.1 replaced the analytic silhouette estimate with the shared corner projection and gated the
success envelope on a post-fit re-measurement. R2-02 recorded a fit targeting `tc14bar` returning
`fitted: true` while `box_10_20_30` was on screen, rewriting the camera the human was watching.
Story 9.2 gave `ViewportPort` a session-wide `showing_document_name()` and compared against that.

The compact and near-cubic aspects are the point for R2-01: the shipped estimate underestimated the
projected extent by 1.155x on a cube and 1.132x on a 20x20x30 box, while the elongated bar it was
tuned against passed. A suite that only re-runs the bar would pass against the defect.

The two open documents are the point for R2-02. With one document open the shipped guard and the
fixed guard behave identically, so a single-document scenario passes against the defect.

**Host**: GUI via H2 proxy. Every scenario needs the live viewport, so none run under H1 headless.

## Preconditions
- [ ] FreeCAD 1.1.1 is running and its process started **after** the addon files were last written
      (verify: compare `Get-Process -Id <pid>` `StartTime` against the `LastWriteTime` of
      `$env:APPDATA\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy\usecases\view_fit.py`)
- [ ] The installed addon matches the source under test
      (verify: `md5sum` of `src/freecad_buddy/usecases/{view_fit,framing}.py`,
      `src/freecad_buddy/hosts/gui_addon/viewport.py` and `src/freecad_buddy/contracts/render.py`
      equals the installed copies)
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

---

### TC-15-04: A fit aimed off-screen is refused and moves no camera

**Priority**: Critical
**Design Ref**: AD-29, AD-31; epics.md §Story 9.2; source `usecases/view_fit.py:291`,
`hosts/gui_addon/viewport.py:59`

This is R2-02's exact reproduction. The shipped guard compared the target against a view the port
resolved from that same target's `Name`, so the comparison tested a name against itself and
returned early every time.

**Given** `box-10-20-30.FCStd` is open and fitted, so its camera is a recorded baseline — verify:
`view_fit_viewport` returns `OK`; record its `framing.ratio` as `ratio_before`  
**And** a second document `tc14bar` is then opened and becomes the focused tab — verify:
`mcp document_list {}` lists both, and `cua-driver call list_windows` reports the active window
title naming `tc14bar`  
**And** `box_10_20_30` still has its own open 3D view, so any refusal cannot be a no-viewport
answer — verify: its earlier `OK` fit proves the view exists  

**When** the fit targets the document that is **not** on screen  
```
mcp view_fit_viewport { doc: "<box_10_20_30 handle>" }
```

**Then** the call is refused — verify: `status` is `INVALID_INPUT`  
**And** the message names **both** documents — verify: `detail.message` contains
`box_10_20_30` and `tc14bar`. A message naming only the target means the guard is comparing a name
against itself again, which is the defect.  
**And** no camera moved — verify: `mcp query_tree_summary { doc: "<tc14bar handle>" }` reports the
same `framing.ratio` as immediately before the call, and
`mcp query_tree_summary { doc: "<box_10_20_30 handle>" }` still reports `ratio_before`  
**And** `box_10_20_30` was not brought forward — verify: `cua-driver call list_windows` still
reports `tc14bar` as the active window. AD-31 refuses; it never redirects and never activates.  
**And** *(visual)* the window is untouched — verify: `cua-driver call get_window_state` with
  `screenshot_out_file: "$RUN_DIR/evidence/tc-15-04-after.png"`, then `Read` it and say what is on
  screen: `tc14bar`'s model at the same size and position as before the call, its tab still
  active. The judgement is on the pixels alone — no MCP status or `ratio` may stand in for looking
  at the image.

**Cleanup**:
```
mcp document_close { doc: "<box_10_20_30 handle>", save: false }
mcp document_close { doc: "<tc14bar handle>", save: false }
```

---

### TC-15-05: The refusal fires on the mismatch only, never on every fit

**Priority**: Critical
**Design Ref**: AD-29; epics.md §Story 9.2; source `usecases/view_fit.py:291`

A guard that refuses everything would pass TC-15-04 while making the tool unusable. This is the
control that separates a working guard from a broken one.

**Given** the two documents of TC-15-04 are open with `tc14bar` focused  

**When** the fit targets the document that **is** on screen  
```
mcp view_fit_viewport { doc: "<tc14bar handle>" }
```
**And** the focus is then moved to `box_10_20_30` by clicking its tab with `cua-driver`, and the
fit targets `box_10_20_30`  

**Then** both calls return `OK` — verify: read `status` from each. The guard fires on the mismatch
only.  
**And** each fit framed its own document — verify: each envelope's `framing.fits` is `true`  
**And** *(visual)* each fit reframed the document it named and left the other alone — verify:
`cua-driver call get_window_state` with
  `screenshot_out_file: "$RUN_DIR/evidence/tc-15-05-after.png"` after the second call, then `Read`
  it and say what is on screen: `box_10_20_30` whole and framed, with `tc14bar` unchanged behind
  its own tab

**Cleanup**:
```
mcp document_close { doc: "<box_10_20_30 handle>", save: false }
mcp document_close { doc: "<tc14bar handle>", save: false }
```

---

### TC-15-06: Every named camera renders a face the human can see

**Priority**: Critical
**Design Ref**: AD-34; epics.md §Story 9.3; source `adapters/render_probe.py:_add_lighting`,
`usecases/render_tone.py`

This is R2-03's reproduction. The shipped rig aimed one `SoDirectionalLight` **along** the view
axis, so an axis-aligned face normal was exactly anti-parallel, the diffuse term degenerated, and
ambient alone saturated the near-white material to pure white. `front`, `top`, `right` and `back`
all rendered `rgb(255,255,255)` — identical to the background, so the PNG carried no shape
information beyond its outline. Orientation was correct throughout, which is why TC-06-02 passes
against the defect: it asserts orientation and never tone.

**Given** a document holding a 40 mm cube built through the tool surface — verify: the pad's
`feature_state.shape_summary.bbox` is `[40, 40, 40]` and `is_valid` is `true`  

**When** the cube is rendered from `front`, the camera R2-03 measured at `rgb(255,255,255)`  
```
mcp query_screenshot { doc: "<handle>", view: { camera: "front", width: 800, height: 600 } }
```

**Then** the call returns `OK` with a real image — verify: `render.available` is `true` and
`render.empty_scene` is `false`  
**And** the rendered PNG passes the two-sided tone band — verify: run the shipped oracle on the
returned path, `verify_render_tone(<path>)`, and read `passed`; it must be `true` with empty
`reasons`. The oracle is the same one the in-FreeCAD sweep and the fault suite use, so a pass here
cannot drift from them  
**And** the face differs from the background by at least 24/255 on some channel — verify: read
`difference` from that verdict; R2-03 measured 0 for this camera  
**And** the mean tone sits within `[20, 235]` on every channel — verify: read `tone`; a one-sided
"not black" check would pass the defect, so both ends are asserted  
**And** `iso` also passes the band — verify: render `iso` and run the oracle; `passed` is `true`.
Its absolute tone is **not** asserted: the rig trades ambient against the headlight offset, and the
`iso` tone deviation is recorded in the story 9.3 spec's `deferred` list  
**And** *(visual)* the `front` PNG shows a shaded face clearly separable from the background, not an
outline around empty space — verify: `Read` the returned PNG and judge the pixels  

**Cleanup**:
```
mcp document_close { doc: "<handle>", save: false }
```

---

### TC-15-07: Temp files land where the sweep can see them, and the sweep stays in its lane

**Priority**: High
**Design Ref**: AD-25; epics.md §Story 9.4; source `usecases/documents.py` (workdir + sweep),
`usecases/screenshot.py`, `usecases/fingerprint.py`

This is R2-04's reproduction. Both `mkstemp` sites passed no `dir=`, so every render and
fingerprint temporary landed in the OS temp directory — outside the tree AD-25 scopes the sweep to.
R2-04 counted 392 orphaned `FCB_TMP_shot_*` files across already-exited sessions.

The scope half matters as much as the location half: a sweep that "fixed" the leak by deleting from
the OS temp directory would break the guarantee that a caller may still be reading a returned link,
and on a shared host would delete another session's files.

**Given** the count of `FCB_TMP_*` entries in the OS temp directory is recorded as `before` —
verify: `(Get-ChildItem $env:TEMP -Filter 'FCB_TMP_*' | Measure-Object).Count`  
**And** a document holding a renderable solid is open  

**When** two renders are taken through the bridge  

**Then** each returned path is **inside** the session workdir — verify: read `render.resource_link`
from each envelope; both are under `<workdir>/tmp`, and neither is under the OS temp directory  
**And** the OS temp count is unchanged — verify: re-count `FCB_TMP_*` in `$env:TEMP`; it equals
`before`. Under the shipped code each render added one  
**And** the workdir's own `tmp/` holds the two renders — verify: count entries under
`<workdir>/tmp`  
**And** those files survive the session exit — verify: close FreeCAD, then re-count
`<workdir>/tmp`; the files are still present, because a caller may still be reading a returned link
and the sweep is a session-start action, never an immediate unlink  
**And** the next session start sweeps them — verify: relaunch FreeCAD via `cua-driver launch_app`,
wait for the proxy on `:8765`, then re-count `<workdir>/tmp`; it is `0`  
**And** the sweep did not reach outside the workdir — verify: re-count `FCB_TMP_*` in `$env:TEMP`;
it still equals `before`. Pre-existing strays there are a one-time operator cleanup and the bridge
must not delete them  

**Cleanup**:
```
mcp document_close { doc: "<handle>", save: false }
```
Do not delete anything from the OS temp directory: those files are the control for this scenario.
