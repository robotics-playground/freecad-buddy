# FreeCAD Bridge — Automation & Verification Guide

How to test the FreeCAD MCP bridge end-to-end with **real geometry**, fully automated, with no
manual FreeCAD launches or restarts, and how to capture errors from code running inside FreeCAD.

## Two run modes

| Mode | Process shape | Transport | Use |
| --- | --- | --- | --- |
| **H1 headless** | one interpreter: FreeCAD + MCP + usecases | stdio only | automation workhorse — spawn/kill, control stdin/stdout, capture stderr |
| **Head / GUI** | in-FreeCAD RPC listener ← external MCP proxy | HTTP | interactive use inside the FreeCAD GUI |

H1 is the single-command test target. It needs **one Python interpreter that can `import FreeCAD`
AND `import mcp`**. FreeCAD's bundled Python has FreeCAD but not `mcp`; the `uv` venv has `mcp`
but not FreeCAD. The bridge is resolved by a dedicated conda env.

## The `fcb` conda env (H1-capable interpreter)

Built with micromamba (user-space, no admin), mirroring `.github/workflows/ci.yml`:

```
micromamba create -n fcb python=3.11 freecad=1.1 -c conda-forge
# then, into that env:
pip install "mcp>=1.28,<2" jsonschema pyyaml
pip install -e .            # the bridge
```

Conda-forge FreeCAD (feedstock #21) needs its native libs on the path. Invoke the env's Python
directly with these child-env vars rather than `micromamba run`:

- `PYTHONPATH = <env>\Library\bin`
- `PATH = <env>\Library\bin;<env>\Library\lib;<PATH>`

`scripts/automation/run_mcp_e2e.py::_fcb_env()` encodes this exactly.

Sanity check: `<env>\python.exe -c "import FreeCAD, mcp; print('H1 ok')"`.

## Automated E2E harness

`scripts/automation/run_mcp_e2e.py` — run from the `uv` env (which has the `mcp` **client**):

```
uv run python scripts/automation/run_mcp_e2e.py
```

It spawns the H1 server under the `fcb` env, drives it over the MCP **stdio** protocol, sweeps
the whole tool surface against the golden models (`benchmarks/g0/golden-models/*.FCStd`), and
writes to `_automation/`:

- `e2e_report.json` — per-tool pass/fail with real measured values
- `server.stderr.log` — the H1 server's captured stderr (read this for plugin/listener errors)
- `sample_render.png` — a rendered golden model to eyeball

The harness owns the subprocess lifecycle: **no manual FreeCAD launch, no restart between runs.**

## Verification bar (falsify the completion claim)

Assert real results, not proxies:

- **Geometry:** `query_mass_properties` volume within 0.1 % of the analytic expectation
  (box-10-20-30 = 6000 mm³, sphere-r10 = 4188.79 mm³, …).
- **Exports:** every `export_*` is unverified until its paired `verify_export_*` passes. STEP is
  a pure FreeCAD round-trip (±0.1 % volume, isValid, exact topology counts). STL/3MF run
  independent oracles (trimesh, lib3mf, a from-scratch STL checker) plus a FreeCAD self-read;
  any oracle disagreement forces FAIL.
- **Render:** `query_screenshot` writes a non-empty PNG; the document fingerprint must be
  geometry-unchanged afterward (see the read-only rule below).
- **Errors:** `_automation/server.stderr.log` must be free of unhandled tracebacks.

The harness reports the actual failed **check IDs** — never mask a failure with a blanket
"expected" leniency. A leniency comment that hides a real failure is a defect.

## In-FreeCAD test suite

`tests/infc/` runs inside FreeCAD via `FreeCADCmd` (or the `fcb` env Python):

```
<fcb-env>\python.exe tests/run_tests.py
```

`tests/external/` (FreeCAD-free, oracle + static-analysis legs) runs under `uv`:

```
uv run pytest tests/external
```

## Verification legs & invariants (learned the hard way)

- **Mesh volume band** is `(2/3) · linear_deflection · surface_area` (chordal-sag bound), NOT a
  bbox-relative fraction and NEVER the STEP ±0.1 %. A bbox-relative band under-bounds the volume
  deficit of doubly-curved surfaces (spheres) by ~3×.
- **Euler check is "even", not "== 2".** A closed orientable mesh has even Euler characteristic
  (Σ 2−2g over its bodies). A through-hole part (χ=0) and a multi-body compound (χ=4) are valid
  exports; requiring χ=2 falsely rejects them. Soundness for flipped normals comes from
  `is_volume`, not Euler.
- **Read-only-after-render compares geometry, not raw bytes.** OCCT re-serializes a freshly
  loaded shape's BRep bytes the first time a render touches it, so the SHA digest shifts while
  the geometry is identical. Use `massprops_equal` (volume/area/COM/principal-moments), never the
  byte digest, to assert a render did not mutate the document. `Shape.BoundBox` is also
  tessellation-derived and is excluded from the geometric invariants.
- **PartDesign render targets leaf features, not the Body.** `subgraphFromObject` on a
  `PartDesign::Body` (a container) raises an Access violation in a headless renderer AND corrupts
  the Coin library for every later object, so a `try/except` cannot recover. The default render
  set skips container/datum types (`PartDesign::Body`, `App::Origin/Line/Plane/Point`) and
  renders the shape-bearing leaf features (e.g. the Pad).

## Capturing errors from inside FreeCAD

- **H1:** all `freecad_buddy` logging goes to **stderr** (stdout carries the stdio MCP protocol).
  The harness captures it to `_automation/server.stderr.log`.
- **GUI mode:** addon logging also goes to a **file** so it can be read without the Report View:
  `%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log` (override with `FREECAD_BUDDY_LOG_FILE`).
  Tail this file to diagnose a GUI-mode failure without a screenshot.

## Environment trap: installed addon shadows the source tree

`import FreeCAD` adds FreeCAD's `Mod` dirs to `sys.path`. If the addon at
`%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy` is a **copied snapshot**, it shadows the
editable `src\freecad_buddy` and tests silently run stale code (symptom: behavior contradicting
the current source; `exports.__file__` resolving under the `Mod` dir). Install the addon package
as a **directory junction** to `src\freecad_buddy` so head-mode FreeCAD and the in-FreeCAD tests
always run current source:

```
mklink /J "%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy" "<repo>\src\freecad_buddy"
```

## Visual check is mandatory (render ≠ viewport)

Any manual test touching rendering or geometry MUST include a **visual check**, and that check
compares the MCP render against a **real FreeCAD viewport screenshot** — never numbers or a
self-generated render alone.

The MCP `query_screenshot` builds its own **constructed Coin scene** (own camera, lighting,
background per AD-1, read-only) — it is **not** a capture of the user's live viewport. So a passing
render with correct volume/bbox numbers does **not** prove the output looks like what the user
sees: camera, framing, and materials can diverge, and a mis-constructed scene can still yield
plausible numbers. Treat "matches the actual FreeCAD screen" as a **separately-verified**
checkpoint:

1. Capture the MCP render (`query_screenshot`) and `Read` the PNG.
2. Capture the real FreeCAD viewport **directly — you do not need to ask the user.** The FreeCAD
   window's live GL content is grabbable with Win32 `PrintWindow` using flag `2`
   (`PW_RENDERFULLCONTENT`) — the default flag returns a black rectangle for a GL surface, so the
   `PW_RENDERFULLCONTENT` flag is required. Set the same isometric view in FreeCAD first, then:
   - **Target the process, not a window-title regex.** Use `Get-Process -Name freecad`, not a
     `*FreeCAD*` title match — the latter also matches "freecad-buddy - Visual Studio Code" and
     captures the wrong window.
   - **Be DPI-aware, or the capture is clipped.** On a scaled display (e.g. 125 %),
     `GetWindowRect` returns *logical* pixels while `PrintWindow` renders the *physical*
     framebuffer, so a bitmap sized to the logical rect loses the right/bottom ~scale-1 fraction.
     Call `SetThreadDpiAwarenessContext(-4)` (`PER_MONITOR_AWARE_V2`) before measuring so the rect
     comes back in physical pixels.
   - **Do not steal focus.** `PrintWindow(h, hdc, 2)` re-renders the window's content (incl. the
     GL viewport) into the DC regardless of z-order or occlusion, so the window need NOT be
     foreground — omit `SetForegroundWindow` entirely and the user's active window is never raised
     or interrupted. Confirmed: `GetForegroundWindow()` is identical before and after the capture.
   - **Restore a minimized window WITHOUT activating.** `GetWindowRect` on a minimized window
     returns a taskbar-button-sized rect (e.g. 159×27), and a minimized window has no surface to
     render. If `IsIconic`, call `ShowWindow(SW_SHOWNOACTIVATE=4)` (un-minimizes without focusing/
     raising), wait ~400 ms, then `GetWindowRect` + `PrintWindow(h, hdc, 2)` into a
     `System.Drawing.Bitmap`. If the window is already visible (even behind others), skip even
     that — capture it in place.
3. `Read` both and diff by eye: same object silhouette, proportions consistent with the geometry
   bbox, matching camera/framing (no axis flip), no missing/extra geometry (datum/container must
   be skipped), AA honored when configured, and shading not black-sided.

Any object/camera/geometry mismatch is a **defect**, not a tolerance — record the exact difference
and stop; do not pass the render on numbers alone. See test case
`docs/tests/TC-06-render-visual-fidelity.md`.

**Render lighting must match the viewport (no black faces).** FreeCAD's live viewport lights the
scene with a **headlight that follows the camera**, so every visible face is lit. A constructed
render that adds a single fixed `SoDirectionalLight` (default world-space direction) leaves faces
angled away from that direction near-black — a divergence the viewport comparison exposes but the
geometry numbers never would. The render port therefore aims a headlight along the camera's view
direction (the orientation quaternion applied to the camera's -Z look axis, `SbRotation.multVec`)
and adds a modest `SoEnvironment.ambientIntensity`, matching the viewport's softer shading. This
was confirmed against `docs/references/FreeCAD/src/Gui/View3DInventorViewer.cpp` (the viewer's
headlight/backlight/fillLight setup), per the source-verify standard.

## Render anti-aliasing comes from FreeCAD's own preference

The offscreen render's multisample count is read from FreeCAD's 3D-view preference
(`User parameter:BaseApp/Preferences/View` → `AntiAliasing`) and applied via
`SoQtOffscreenRenderer.setNumPasses` — not hard-coded. The stored value is the `Gui::AntiAliasing`
**enum value, which is non-sequential** (`MSAA8x=4`, `MSAA6x=5`); it maps to samples
`{0:0, 1:1, 2:2, 3:4, 4:8, 5:6}`. A running FreeCAD caches the imported render module, so a code
change to the render path needs a FreeCAD restart (or module reload) to take effect in GUI mode.

Whenever a FreeCAD enum/preference/API drives behavior, confirm it against the source under
`docs/references/FreeCAD/` before coding — see the [FreeCAD source-verify
standard](../freecad/source-verify.md). The AA enum above is the worked example of why: the
obvious index assumption is wrong.

## Static gate

`uv run python scripts/check_imports.py` enforces the ring/import rules and bans
`FreeCAD.ActiveDocument` / `setActiveDocument` (every tool operates on an explicit doc handle).
Run it before any commit — it catches the addon-import-leak and active-document-target bug
classes mechanically.
