# UAT Bug Ledger — Run 2026-09-13-02

Fresh run. Findings are numbered from `R2-01` and are independent of any earlier run's ledger.

**Status vocabulary:** `open` = found, unfixed. `invalid` = not a product defect (test or
environment fault).

**Severity:** `blocker` = stops the suite. `high` = a shipped contract is wrong.
`medium` = wrong behaviour with a workaround. `low` = cosmetic or documentation.

## Build banner

| Field | Value |
| --- | --- |
| FreeCAD | 1.1.1 |
| `element_map_available` | `true` (version `15.70200.5`) |
| `serializer` | `exportBinary` |
| `render` | `gui_constructed` |
| `exec_enabled` | `false` |
| Host | GUI addon + auto-spawned H2 proxy on `:8765` |
| FreeCAD pid / window | 26912 / 398030 |

---

## Summary

| ID | Severity | Area | Title | Status |
| --- | --- | --- | --- | --- |
| R2-01 | **high** | product | `view_fit_viewport` reports `fitted: true` while leaving the model clipped; repeated calls never converge | open |
| R2-02 | **high** | product | The wrong-document guard in `view_fit_viewport` can never fire, so a fit moves the camera of a document the human is not looking at | open |
| R2-03 | medium | product | Every axis-aligned camera renders the model as an unshaded white silhouette, indistinguishable from an empty scene | open |
| R2-04 | low | product | `query_screenshot` leaves its `FCB_TMP_shot_*.png` behind; the temp directory accumulates one file per render | open |
| R2-05 | low | product | `export_*` creates missing parent directories instead of refusing an unwritable path | open |

---

## Findings

### R2-01 — `view_fit_viewport` returns `fitted: true` but the model stays clipped

- **Severity:** high
- **Area:** product
- **Found in:** TC-05-01 closing visual `Then`
- **Status:** open
- **Epic:** 8 (story 8-3, `view_fit_viewport`); regression against commit `636fb8a`
  "fix(tools): make view_fit_viewport fill the viewport in one call"

**What happened.** After a 30 mm `feature_pad` on a 20x20 mm sketch, `view_fit_viewport` was
called on the owning handle. It returned success while its own framing block simultaneously
reported that the model does not fit:

```
{"fitted": true, "document": "uat_tc05", "camera_recorded": true}
framing: {"fits": false, "ratio": 1.0768211920529802, "checked": "computed"}
```

A second identical call did not converge — it returned `fits: false` with `ratio:
1.0752587017873942`. Two consecutive fits both leave the model about 7.5 % larger than the
viewport.

**The pixels.** `tests/uat/run/2026-09-13-02/evidence/tc-05-01-after.png` (captured immediately
after the MCP fit) shows the shaded box with its **bottom face cut off by the viewport border**
and the top face nearly touching the top border.

**The control.** The GUI's own **Fit All** toolbar button (element token `s00000005:96`,
`route: "accessibility"`) was then clicked on the same document, in the same window, seconds
later. `tests/uat/run/2026-09-13-02/evidence/tc-05-01-gui-fitall.png` shows the same box
**whole**, with clear margin on every side.

The only variable between the two captures is which code performed the fit. FreeCAD can frame
this model correctly; `view_fit_viewport` does not.

**Why it matters.** This is the failure mode `test-plan.md` §3 is built around: a tool reporting
success over a window that does not show the user what was claimed. An agent trusting
`fitted: true` will believe the human can see the change when part of it is off-screen. The
`ratio` field proves the code already measured the overflow and returned success anyway.

**Reproduce.**
1. Create a document, a `Body`, and a fully-constrained 20x20 mm sketch on XY.
2. `feature_pad` it 30 mm.
3. Call `view_fit_viewport` on the handle. Observe `fitted: true` with `framing.fits: false`.
4. Capture the window and look at it: the solid is clipped.
5. Click the GUI **Fit All** and capture again: the solid is whole.

**Against the suite's own threshold.** TC-14-03 requires `framing.ratio` to be between `0.85` and
`1.0`. The measured 1.0768 and 1.0753 are outside that band on the overflow side.

**Root cause.** Two functions measure the silhouette differently, and they disagree.

`_fill_factor` (`usecases/view_fit.py:168-191`) estimates the on-screen silhouette as the largest
*face* diagonal and divides it by the space diagonal:

```python
silhouette = max(
    math.sqrt(dx * dx + dy * dy),
    math.sqrt(dy * dy + dz * dz),
    math.sqrt(dx * dx + dz * dz),
)
return max(silhouette / diagonal / _FILL_FRACTION, _MIN_FIT_FACTOR)
```

`hull_ratio` (`usecases/framing.py:137-153`) instead projects the eight bbox corners and measures
their real 2D screen hull.

For this 20x20x30 box:

| Quantity | Value |
| --- | --- |
| space diagonal | 41.2311 |
| largest face diagonal — `_fill_factor`'s estimate | 36.0555 |
| resulting fit factor | 0.9205 (zooms **in**) |
| true projected extent — what `hull_ratio` measures | 40.8248 |
| underestimate | **1.13x** |

The comment at `view_fit.py:182-185` asserts "the widest thing on screen is a face diagonal, never
the space diagonal the sphere framing reserves room for", justifying it by "looking down a cube
corner". The measurements below show the opposite: the estimate is worst for a cube and best for an
elongated bar. The fit therefore zooms in past the point where the model still fits, and the model
overflows by roughly the ratio of the underestimate.

The tuning note at `view_fit.py:30-34` records measurement on "a 40x40x800 bar and a 40x25x15
plate". Both are elongated or flat, where the approximation happens to hold. The error grows as the
box approaches a **cube** — precisely the shape the comment cites as its justification.

**Measured on the live bridge, same session, one fit call each:**

| Model | `framing.ratio` after the fit | `fits` | Pixels |
| --- | --- | --- | --- |
| 40x40x800 bar (the tuning case) | 0.8137 | `true` | whole, ~78 % of viewport height |
| 20x20x30 box | 1.0768, then 1.0753 | `false` | bottom face clipped |
| **40x40x40 cube** | **1.0978** | `false` | **clipped top vertex and bottom face** |

Evidence: `evidence/tc-14-04-after.png` (bar, correct), `evidence/tc-05-01-after.png` (box,
clipped), `evidence/r2-01-cube-worst-case.png` (cube, worst).

The analytic sweep agrees on the ordering — ratio of true projected extent to `_fill_factor`'s
estimate: cube 1.155, 20x20x30 1.132, 40x40x80 1.095, 40x25x15 0.974, 40x40x800 0.856. Anything
above 1.0 overflows. **Compact, near-cubic models overflow; elongated and flat ones do not**, which
is why the tuning cases pass and the regression guard TC-14-04 passes while ordinary parts fail.

**This is not a full regression of `636fb8a`.** That fix works for the extreme aspect ratio it was
measured against; TC-14-04 passes. The gap is in the middle and compact end of the range, which the
tuning never sampled.

**Suggested fix direction.** Compute the silhouette from the actual projected corner hull rather
than from an analytic face-diagonal estimate — the projection `hull_ratio` already performs is the
correct measurement, so the two should share one routine. Failing that, the fit must not report
`fitted: true` when its own post-fit measurement returns `fits: false`; reporting success alongside
a contradicting measurement in the same envelope is the part that must not ship.

---

### R2-02 — The wrong-document guard can never fire; a fit moves a camera the human is not looking at

- **Severity:** high
- **Area:** product
- **Found in:** TC-14-06
- **Status:** open
- **Epic:** 8 (story 8-3); violates spine §AD-31 and the AD-20 implicit-target ban

**What TC-14-06 requires.** A handle naming a document the live viewport is not showing must be
refused, naming both documents. `view_fit_viewport`'s own tool description states it: "Refused when
the live viewport is showing a different document."

**What happened.** Two documents were open: `tc14bar` (a 40x40x40 cube) and `box_10_20_30`, with
**`box_10_20_30` active in the GUI**. `view_fit_viewport` was then called with the `tc14bar` handle:

```
{"fitted": true, "document": "tc14bar", "camera_recorded": true}
```

It did not refuse. It reported success and moved the camera.

**The pixels.** `evidence/tc-14-06-after.png`, captured immediately after, shows the GUI state at
that moment:

- the active tab is **`box-10-20-30 : 1`** (bold, white); `tc14bar : 1*` sits inactive beside it
- the Model tree shows **`box-10-20-30`** bold as the active document
- the viewport is **empty** and the navigation cube reads **TOP**

`cua-driver list_windows` agrees: the window title is `" box-10-20-30 - FreeCAD 1.1.1"`.

So the human was looking at `box_10_20_30`, and the call — targeting `tc14bar` — reoriented and
refit the live view anyway, leaving the camera of the document they *were* looking at moved to a
TOP orientation they never asked for.

**Root cause.** The guard compares the wrong pair of names.

`_require_same_document` (`usecases/view_fit.py:234-250`) compares the **view's own** document
against the target:

```python
target = _name_of(document)
showing = _name_of(_view_document(view))
if showing is None or target is None or showing == target:
    return
```

But the view it is handed comes from `GuiViewportPort.view()` (`hosts/gui_addon/viewport.py:54`):

```python
return gui.getDocument(name).ActiveView
```

The view is resolved **by the target document's own name**, so the view handed back always belongs
to the target. `showing == target` is therefore always true and the guard returns early every time.

The docstring at `view_fit.py:237-240` says so outright: "The port resolves a view through
`getDocument(<Name>)`, so a view handed back for document A belongs to A. The failure this guards is
the other direction." The guard checks a condition that cannot arise, while the condition TC-14-06
actually describes — the *live viewport* showing a different document — is never checked at all.

**Reproduce.**
1. Create document A with any solid; leave it active.
2. `document_open` document B. B becomes the active tab.
3. Call `view_fit_viewport` with **A's** handle.
4. Observe `fitted: true` instead of a refusal, and the GUI camera moving while B is on screen.

**Suggested fix direction.** Compare the target against the **GUI's active document**
(`FreeCADGui.ActiveDocument`, read inside the `hosts/` layer where Gui knowledge is legal — note
story 8.5's alias rule, so route it through the port rather than importing `FreeCADGui` in
`usecases/`). The port should report which document the live viewport is actually showing, and
`_require_same_document` should compare against that, not against a view it resolved from the target
name.

---

### R2-03 — Axis-aligned cameras render an unshaded white silhouette

- **Severity:** medium
- **Area:** product
- **Found in:** TC-06-02
- **Status:** open
- **Epic:** 1 (story 1-9, view-controlled screenshots)

**What happened.** `query_screenshot` with `camera: "iso"` renders the golden box correctly: three
faces, each a distinct grey, matching the live viewport. The same document rendered with any of the
four axis-aligned cameras comes back as a **white rectangle with a thin outline** — the face is the
same RGB as the background.

**Measured.** Sampling every 5th pixel and counting mid-grey fill (`120 < R < 230`, near-neutral),
excluding near-white background and near-black edges:

| `view.camera` | shaded samples |
| --- | --- |
| `iso` | **66789** |
| `front` | 307 |
| `top` | 308 |
| `right` | 309 |
| `back` | 307 |

The ~307 in each orthogonal view are anti-aliased edge pixels, not a face. The dominant interior
colour in `front`/`top` is `rgb(255,255,255)` — identical to the background — whereas `iso` fills
with `rgb(159,164,169)`.

Evidence: `evidence/tc-06-01-mcp.png` (iso, correct), `evidence/tc-06-02-front.png`,
`tc-06-02-top.png`, `tc-06-02-right.png`, `tc-06-02-back.png`.

**Orientation itself is correct.** The `front` render is 1:3 (10x30) and `top` is 1:2 (10x20),
matching the `bbox` from `query_mass_properties`. Only the shading is lost, so TC-06-02's
orientation assertions pass — this defect is confined to the lighting.

**Root cause.** `_add_lighting` (`adapters/render_probe.py:81-100`) aims a single
`SoDirectionalLight` along the camera's view direction:

```python
view_dir = coin.SbRotation(*orientation).multVec(coin.SbVec3f(0.0, 0.0, -1.0))
headlight = coin.SoDirectionalLight()
headlight.direction.setValue(view_dir)
```

For an axis-aligned camera the visible face's normal is exactly anti-parallel to that view
direction, so the diffuse term is degenerate and only the `ambientIntensity` 0.7 term remains
(`render_probe.py:98`). Against the near-white default material that saturates to pure white.

The function's own docstring states its purpose as "so no face renders black". It solved the
black-face case and introduced the white-face case at the opposite extreme: in both, the face
carries no tone that separates it from the background.

**Why it matters.** The docstring at `render_probe.py:183` notes the concern about "rendering that
writes a blank PNG the caller cannot distinguish from a real [empty scene]". That is exactly what
these four cameras produce. An agent rendering a `front` view to check a part sees a white rectangle
and cannot tell a successful render from an empty one — the envelope says `empty_scene: false` and
`rendered_objects: ["Box"]`, but the image carries no usable shape information beyond its outline.

**Reproduce.**
1. Open `benchmarks/g0/golden-models/box-10-20-30.FCStd`.
2. `query_screenshot { doc, view: { camera: "iso", include: ["Box"] } }` — faces are shaded grey.
3. Repeat with `camera: "front"` (or `top`, `right`, `back`) — the face is pure white.

**Suggested fix direction.** Offset the headlight slightly from the pure view axis (FreeCAD's own
viewport headlight is not exactly camera-parallel), or add a second fill light at an angle, so a
face perpendicular to the camera still receives a diffuse term. Verify by re-running the pixel count
above: every named camera should produce a shaded interior, not only `iso`.

---

### R2-04 — `query_screenshot` leaves its temp PNG behind

- **Severity:** low
- **Area:** product
- **Found in:** TC-06-01 / TC-06-02 teardown
- **Status:** open
- **Epic:** 1 (story 1-9)

**What happened.** Each `query_screenshot` call returns a `render.resource_link` pointing at
`%TEMP%\FCB_TMP_shot_<random>.png`. Nothing removes them.

Measured after the run, with every document closed and the bridge idle: **390 files, 0.7 MB**,
oldest 2026-09-12 16:12, newest 2026-09-13 10:50 — two days of accumulation across several
sessions, including runs that had already exited.

The reserved `FCB_TMP_` prefix is the same one TC-11-12/13 covers for snapshot directories, and
those *are* cleaned up (zero `FCB_TMP_snap_*` leaked this run). Render outputs are not.

**Why it is low.** The files are small, live in the system temp directory, carry no secret, and the
OS reclaims them eventually. It is an accumulation issue, not a correctness or safety one. It is
recorded because the neighbouring cleanup contract is explicit and this path is the exception.

**Reproduce.** Note the `%TEMP%\FCB_TMP_shot_*` count, call `query_screenshot` N times, close every
document, and count again — it grew by N.

**Suggested fix direction.** Either sweep `FCB_TMP_shot_*` at session start alongside the snapshot
sweep AD-25 calls for, or give the render output a session working directory that is removed on
exit. A caller may still be reading the link when the call returns, so deleting it immediately is
not safe.

---

### R2-05 — `export_*` creates missing parent directories

- **Severity:** low
- **Area:** product
- **Found in:** TC-09-06 probe (incidental)
- **Status:** open
- **Epic:** 1 (story 1-7)

**What happened.** `export_step` was called with `path: "D:/tmp/x.step"` where `D:\tmp` did not
exist. The call returned `OK` and **created the directory**, writing a 6854-byte STEP into it.

Contrast with the deeper nesting tested in TC-07-16: `.../uat/no_such_dir_xyz/box.step` returned
`RECOMPUTE_ERROR` ("Writing of STEP failed") and created nothing. So the behaviour differs by depth
— one missing level is created, a missing level under it is not.

**Why it is low.** No data is lost or corrupted, and the written file verified correctly. But an
export that silently creates directories can scatter files where the caller did not intend,
and the inconsistency between the two depths makes the contract hard to state.

**Reproduce.**
1. `export_step { doc, path: "<drive>/<nonexistent-dir>/x.step" }` — returns `OK`, directory created.
2. `export_step { doc, path: "<existing>/<nonexistent>/<nonexistent>/x.step" }` — returns
   `RECOMPUTE_ERROR`, nothing created.

**Suggested fix direction.** Decide one rule and state it in the tool description: either require an
existing parent directory and refuse otherwise with `INVALID_INPUT`, or create the full path
consistently. Refusing is the safer default for a tool that writes to a user-supplied path.
