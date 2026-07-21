# 003 — Render Ladder: SoQtOffscreenRenderer under xvfb + software Mesa

## Decision

Screenshots use `FreeCADGui.SoQtOffscreenRenderer` after calling
`FreeCADGui.setupWithoutGUI()` (which MUST run before any `*Gui` import). The scene graph is
obtained via `subgraphFromObject`. Raw `pivy.coin.SoOffscreenRenderer` is NEVER used — it
lacks the Qt/GL context wiring that FreeCAD's offscreen renderer sets up. Headless rendering
runs under `xvfb-run` with `LIBGL_ALWAYS_SOFTWARE=1` (llvmpipe software GL). The whole
capability is guarded behind `usecases/shim.render_available()`; screenshot features stay
disabled until a usable GL context is confirmed.

## Drives

- Story 1.9 screenshots.
- CI `render` leg in `ci.yml` (1.1.0 only, `continue-on-error: true`, xvfb + `LIBGL_ALWAYS_SOFTWARE=1`).

## Runtime-confirm

- Is a usable GL context obtainable under `xvfb` + llvmpipe on the **1.1.0** leg?
- Does `FreeCADGui.setupWithoutGUI()` + `SoQtOffscreenRenderer` produce a non-empty image headlessly?
- To be confirmed on the CI render leg; `shim.render_available()` will return True only after this passes.
