# TC-06: Render Visual Fidelity vs. Real FreeCAD Viewport

Confirms the MCP `query_screenshot` render actually depicts the object as it appears in FreeCAD —
not merely that it produced a non-empty PNG with plausible geometry numbers. The MCP render builds
its own constructed Coin scene (own camera, lighting, background) and is NOT a capture of the live
viewport, so visual fidelity must be checked by direct image comparison, every time.

## Prerequisites

- [ ] A FreeCAD instance (GUI) is open with the target document, reachable via the bridge
- [ ] The MCP proxy is serving `:8765` — the addon **auto-spawns it on FreeCAD start**, so simply opening FreeCAD is enough (verify: `netstat -ano | grep :8765` shows LISTENING). No manual `serve` command; if it is absent, restart FreeCAD or check the addon log. Starting `serve --mode rpc` by hand is a debug fallback only.

---

### TC-06-01: MCP render matches the live viewport

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §6 (constructed-scene offscreen render, AA)

**Preconditions**:
- [ ] Target object identified (verify: `document_list` then `query_tree_summary` name the object)
- [ ] Object's geometry known (verify: `query_mass_properties` returns volume/bbox/counts)

**Steps**:
1. Capture the MCP render at a named camera:
   ```
   mcp query_screenshot { doc: <handle>, view: { camera: "iso", include: [<object>] } }
   ```
   `Read` the returned `resource_link` PNG.
2. Capture the **real FreeCAD viewport** directly via the OS — no need to ask the user. Find the
   FreeCAD window and grab its live GL content with Win32 `PrintWindow` (flag `2` =
   `PW_RENDERFULLCONTENT`, which captures the OpenGL viewport, not a black rectangle):
   ```powershell
   # Get-Process -Name freecad (NOT a *FreeCAD* title regex — that matches VS Code);
   # SetThreadDpiAwarenessContext(-4) for physical px; if IsIconic ShowWindow(h,4)=SW_SHOWNOACTIVATE;
   # NO SetForegroundWindow (do not steal focus); GetWindowRect -> Bitmap -> PrintWindow(h,hdc,2) -> Save
   ```
   Set the same isometric view in FreeCAD first (View → Standard views → Isometric / press `0`).
   The capture does not raise or focus the FreeCAD window — the user's active window is undisturbed.
3. `Read` the captured viewport PNG.

**Checkpoints**:
- [ ] CP1: Same object present — verify: both images show the same shape silhouette (compare by eye; the MCP `scene.rendered_objects` must list the object)
- [ ] CP2: Proportions match the geometry — verify: the rendered slab/solid proportions agree with `query_mass_properties` bbox extents (e.g. a 10 mm-thick, ~80×62 mm slab reads flat and wide)
- [ ] CP3: Camera/framing consistent — verify: the iso orientation and framing of the MCP render match the viewport's isometric view (flag any axis flip or off-centre framing)
- [ ] CP4: No missing/extra geometry — verify: no object visible in the viewport is absent from the MCP render, and no datum/container leaked into the MCP render (Body/origin planes must be skipped)
- [ ] CP5: Anti-aliasing honored — verify: edges are smooth when the user's `Preferences/View/AntiAliasing` is MSAA (no stair-stepping); confirm the config value with `grep AntiAliasing "$APPDATA/FreeCAD/v1-1/user.cfg"`
- [ ] CP6: Shading not black-sided — verify: faces angled away from the camera render as shaded grey (headlight + ambient), NOT pure black. A black side face means the render lost its camera-aligned headlight; compare tone against the viewport's lit sides.

**Divergence handling**:
- Any CP1–CP4 mismatch is a **defect**, not a tolerance — record the exact difference (missing object, wrong camera, geometry mismatch) and stop; do not pass the render on numbers alone.
- CP5 (AA) differences are quality-level, not blocking, unless AA is entirely absent while configured on.

**Cleanup**:
```bash
rm -f _automation/pad_*.png  # or the copied render artifacts under _automation/
```
