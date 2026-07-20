---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments:
  - docs/intent.md
  - docs/references/FreeCAD/src (local FreeCAD source)
workflowType: 'research'
lastStep: 5
research_type: 'technical'
research_topic: 'Offscreen screenshot rendering of FreeCAD models without a GUI (FreeCADCmd)'
research_goals: 'Determine whether and how model screenshots/rendered views can be produced headless; conclude feasible-native / feasible-fallback / cut.'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** Technical (deep dive)
**Topic:** Offscreen screenshot rendering of FreeCAD models without a GUI (`FreeCADCmd`)

---

## Research Overview

### Question

Can FreeCAD Buddy produce a rendered screenshot / view of a model **headless** (no display server, no interactive GUI), so that:

- **Phase 0** can ship the `query.*` "screenshot capture" tool that its exit criteria imply (bridge "works both inside the FreeCAD GUI and headless via `FreeCADCmd`", tool taxonomy explicitly lists "screenshots"), and
- **Phase 4** can deliver the "rendered views" artifact ("submit spec → receive model + validation report + STEP/STL/3MF exports + **rendered views**") on a fully headless CI/service, "zero GUI"?

The three candidate outcomes framed by the goal: **(A) feasible natively**, **(B) feasible via fallback**, **(C) cut the screenshot tool for headless mode**.

### Method

1. **Primary evidence — local FreeCAD source** at `docs/references/FreeCAD/src/`. Traced exactly what `FreeCADCmd` initializes vs. skips, how the offscreen renderer is exposed to Python, how a Coin scenegraph is built without view providers, and how FreeCAD's own tools/tests/CI render offscreen. This is version-current source, so it is authoritative over forum lore.
2. **Web corroboration** — FreeCAD wiki (Headless_FreeCAD), FreeCAD GitHub issues #13356 and #16407, forum threads on offscreen Coin rendering, and the offscreen PR #6808. Used to confirm the historical pain points and the officially blessed pattern.

### Bottom line (stated up front)

**Outcome A — feasible natively — with one hard dependency.** Headless model screenshots are a **supported, first-party FreeCAD capability**, not a hack. FreeCAD itself ships the exact tool we need (`src/Tools/make_snapshot.py`) that runs under `FreeCADCmd`, plus Python bindings (`FreeCADGui.setupWithoutGUI()`, `FreeCADGui.subgraphFromObject()`, `Gui.SoQtOffscreenRenderer`) and CI that renders Coin scenes offscreen on Linux runners. **Do not cut the tool.** The single non-negotiable requirement is an **OpenGL context**, which on a headless Linux CI box is satisfied by `xvfb-run` (+ software Mesa/llvmpipe for determinism) — exactly what FreeCAD's own CI does. There is no pure-CPU path through Coin; the fallback (mesh export + external rasterizer) is the plan-B only if GL-in-CI proves troublesome.

---

## Finding 1 — `FreeCADCmd` alone does NOT link the rendering stack, but `import FreeCADGui` does

`FreeCADCmd`'s `main()` (`docs/references/FreeCAD/src/Main/MainCmd.cpp`) initializes **only** `App::Application::init(argc, argv)` — the geometry/document kernel. It never touches `Gui::`, Coin, or Qt. So the offscreen renderer classes that live under `src/Gui/` (`SoFCOffscreenRenderer`, `SoQtOffscreenRenderer`, `View3DPy::saveImage`) are **not present in the base `FreeCADCmd` process image** until the `FreeCADGui` Python extension module is imported.

The bridge to rendering is therefore the line `import FreeCADGui` (optionally `from pivy import coin`). That import runs `PyMOD_INIT_FUNC(FreeCADGui)` in `src/Main/FreeCADGuiPy.cpp`, which links in Qt + Coin and registers the headless helpers. This is why the historical error "**Cannot load Gui module in console application**" (seen in forum threads) appears: older/partial builds shipped `FreeCADCmd` without the loadable `FreeCADGui` module, or `import FreeCADGui` was attempted without the required Qt/Coin libraries and OpenGL. On a normal, complete FreeCAD install (AppImage, conda-forge, official Ubuntu/Windows packages) the `FreeCADGui` module **is** importable from `FreeCADCmd`.

**Implication for the bridge:** the screenshot tool must live behind a lazy `import FreeCADGui` and degrade gracefully (feature-detect) if that import fails, rather than assuming the base `FreeCADCmd` can render.

*Evidence:* `src/Main/MainCmd.cpp` (init only calls `App::Application::init`); `src/Main/FreeCADGuiPy.cpp:336` (`PyMOD_INIT_FUNC(FreeCADGui)`).

---

## Finding 2 — `setupWithoutGUI()` is the official headless entry point; it initializes Coin without a MainWindow or event loop

`FreeCADGui.setupWithoutGUI()` (`src/Main/FreeCADGuiPy.cpp:194`) does exactly and only what headless rendering needs:

```cpp
static PyObject* FreeCADGui_setupWithoutGUI(...) {
    if (!Gui::Application::Instance) {
        static Gui::Application* app = new Gui::Application(false);  // no main window
        _isSetupWithoutGui = true;
    }
    if (!SoDB::isInitialized()) {          // init the Coin/Inventor subsystem
        SoDB::init();
        SoNodeKit::init();
        SoInteraction::init();
    }
    if (!Gui::SoFCDB::isInitialized()) {   // FreeCAD's Coin node registry
        Gui::SoFCDB::init();
    }
    ...
}
```

It constructs a `Gui::Application(false)` (the `false` = "no GUI"), initializes the Coin scene-graph database and FreeCAD's custom Coin nodes, and **does not** create a `MainWindow`, start an event loop, or need a display connection. After this call, all Coin node types and FreeCAD view-provider classes are registered and instantiable.

*Evidence:* `src/Main/FreeCADGuiPy.cpp:194-217`.

---

## Finding 3 — `subgraphFromObject()` builds a renderable scenegraph WITHOUT a GUI document / view provider instance

The documented headless limitation ("no GUI document, so no view providers") is real but **does not block rendering**, because FreeCAD provides a dedicated path that constructs a view provider *transiently* just to emit its Coin subgraph.

`FreeCADGui.subgraphFromObject(obj)` (`src/Gui/Application.cpp:272`) does:

1. Looks up the object's view-provider class name (`obj->getViewProviderName()`).
2. **Instantiates that view provider directly** via `Base::Type::createInstanceByName(vp, true)` — no GUI document required.
3. `vp->attach(obj)`, replays the property map through `vp->updateData(...)`, sets a display mode.
4. Returns `vp->getRoot()->copy()` wrapped as a `pivy.coin` `SoNode *`.

So the "there are no view providers headless" statement in the wiki means only that there is no *persistent GUI document tree*; you still get a fully-materialized, correctly-colored Coin subgraph per object on demand. That subgraph is a normal `pivy` node you compose into a scene.

*Evidence:* `src/Gui/Application.cpp:272-334` (`FreeCADGui_subgraphFromObject`), method registered at `Application.cpp:387`.

---

## Finding 4 — FreeCAD ships the exact headless-screenshot tool we need: `make_snapshot.py`

This is the strongest single piece of evidence. `src/Tools/make_snapshot.py` is a first-party FreeCAD utility whose docstring explicitly says it is meant to run under `FreeCADCmd`:

```
FreeCAD -c make_snapshot_from_file.py
    or
FreeCADCmd make_snapshot_from_file.py
```

Its body is a complete, minimal recipe for exactly our Phase 0 / Phase 4 need — load a model file, render it offscreen, write a PNG — and it maps 1:1 onto the pieces found above:

```python
import FreeCAD, FreeCADGui, os, importlib, sys
from PySide2 import QtGui

def make_snapshot(input_file, output_file, size=48):
    from pivy import coin
    # ... open the file into an ActiveDocument ...
    FreeCADGui.setupWithoutGUI()                                   # Finding 2
    nodes = [FreeCADGui.subgraphFromObject(o) for o in doc.Objects]  # Finding 3

    root  = coin.SoSeparator()
    light = coin.SoDirectionalLight()
    cam   = coin.SoOrthographicCamera()
    root.addChild(cam); root.addChild(light)
    for node in nodes: root.addChild(node)

    axo = coin.SbRotation(-0.353553, -0.146447, -0.353553, -0.853553)  # iso view
    viewport = coin.SbViewportRegion(size, size)
    cam.orientation.setValue(axo)
    cam.viewAll(root, viewport)                                    # auto-frame

    off = FreeCADGui.SoQtOffscreenRenderer(size, size)            # Finding 5
    off.setBackgroundColor(1, 1, 1)
    root.ref()

    # A QGuiApplication is needed to create an OpenGL context
    if QtGui.QGuiApplication.instance() is None:
        app = QtGui.QGuiApplication(sys.argv)                     # Finding 6

    off.render(root)
    off.writeToImage(output_file)                                 # PNG/JPG out
    root.unref()
```

For FreeCAD Buddy we adapt this trivially: instead of `module.open(input_file)`, render the **already-open** `FreeCAD.ActiveDocument` (the model the agent just built), pick a nicer camera/size, and write to a temp PNG that the `query.screenshot` tool returns. The pattern is production-blessed, not experimental.

*Evidence:* `src/Tools/make_snapshot.py` (full file, 83 lines).

---

## Finding 5 — `Gui.SoQtOffscreenRenderer` is a real Python-exposed offscreen renderer with `render()` + `writeToImage()`

`src/Gui/SoQtOffscreenRendererPy.cpp` exposes a Python class `Gui.SoQtOffscreenRenderer` with the methods:

- `setViewportRegion(w, h)`, `setBackgroundColor(r,g,b[,a])`, `setNumPasses(n)` (anti-aliasing), `setInternalTextureFormat(...)`
- `render(node)` — renders a `pivy.coin` node graph into the offscreen buffer; returns bool success.
- `writeToImage(filename)` — pulls the buffer into a `QImage` and `img.save(...)`, so **any Qt-supported format (PNG, JPG, BMP, …)** works, not just Coin's native `.ps`/`.rgb`.
- `getWriteImageFiletypeInfo()` — enumerate supported formats.

This is the key upgrade over the old, broken forum approach in issue #13356. That issue (open, "help wanted") failed because it used the **bare Coin `SoOffscreenRenderer`** directly: `render()` "always returns 0", PNG unsupported, and `writeToPostScript()` segfaulted in `libCoin`. FreeCAD's own `SoQtOffscreenRenderer` wrapper is precisely the sanctioned replacement — it uses a Qt/GL framebuffer and the QImage saver, sidestepping every failure mode in #13356. Use the FreeCAD `Gui.SoQtOffscreenRenderer`, **never** raw `pivy.coin.SoOffscreenRenderer`.

*Evidence:* `src/Gui/SoQtOffscreenRendererPy.cpp` (methods `render`, `writeToImage`, `init_type`); contrast with GitHub issue #13356 (raw `SoOffscreenRenderer` crashes/PNG-unsupported).

---

## Finding 6 — The one hard requirement: an OpenGL context (⇒ Xvfb + software GL on headless Linux CI)

Coin renders through OpenGL. The offscreen renderer still needs a valid GL context, and Qt needs a platform plugin to hand one out. This is the **only** real gating constraint, and it has a standard, FreeCAD-endorsed solution:

- `make_snapshot.py` itself creates `QtGui.QGuiApplication(sys.argv)` before rendering, with the comment *"A QGuiApplication is needed to create an OpenGL context."* So a Qt application object must exist in the process (it does not need to show any window).
- On a headless **Linux** CI runner there is no display, so the GL context must come from a virtual display or an offscreen GL platform. FreeCAD's own CI does exactly this:
  - `.github/workflows/sub_buildUbuntu.yml` wraps GUI/Coin tests in **`xvfb-run -a -s "-screen 0 1024x768x24"`**, and `package/ubuntu/install-apt-packages.sh` installs **`xvfb`**.
  - The C++ Qt-test action sets **`QT_QPA_PLATFORM: offscreen`** (`.github/workflows/actions/.../runSingleQtTest/action.yml`).
  - FreeCAD's Coin snapshot test `src/Mod/Test/TestCoinNodeSnapshots.py` sets, for determinism, **`LIBGL_ALWAYS_SOFTWARE=1`** and **`MESA_LOADER_DRIVER_OVERRIDE=llvmpipe`**, and accepts a headless Qt platform (`QT_QPA_PLATFORM ∈ {offscreen, minimal, eglfs, linuxfb, vnc}`) or a real `DISPLAY`. It skips gracefully if neither is available.

**Concretely for Phase 4 CI:** run the render job as `xvfb-run -a freecadcmd render_snapshot.py` (or set `QT_QPA_PLATFORM=offscreen`), with `mesa`/`libgl1` + `xvfb` in the image and `LIBGL_ALWAYS_SOFTWARE=1` for reproducible pixels. This is a documented, low-risk pattern already exercised on every FreeCAD push.

> Caveat worth flagging: `QT_QPA_PLATFORM=offscreen` gives a Qt platform but historically does **not** always provide a usable GL context on its own; the robust, FreeCAD-proven choice is **`xvfb-run` + software Mesa**. Prefer Xvfb; treat pure `offscreen` as a secondary option validated per-image.

*Evidence:* `src/Tools/make_snapshot.py` (QGuiApplication comment); `.github/workflows/sub_buildUbuntu.yml:184,196` (`xvfb-run`); `.github/workflows/actions/runCPPTests/runSingleQtTest/action.yml:28` (`QT_QPA_PLATFORM: offscreen`); `package/ubuntu/install-apt-packages.sh:87` (`xvfb`); `src/Mod/Test/TestCoinNodeSnapshots.py:328-367` (software-GL + headless-QPA logic).

---

## Finding 7 — Related headless GUI-module pitfalls (import ordering) are known and fixed

Issue **#16407** ("Crash when `import PartDesignGui` in headless python script") confirms a real gotcha: importing a `*Gui` workbench module (e.g. `PartDesignGui`) headless can crash **unless `FreeCADGui.setupWithoutGUI()` is called first**. It is now **closed / fixed** (PR #21659). For the bridge this reinforces a rule: **always call `setupWithoutGUI()` immediately after `import FreeCADGui`, before importing any `*Gui` module or touching view providers.** `make_snapshot.py` already follows this ordering.

*Evidence:* GitHub issue #16407 (closed, PR #21659).

---

## Finding 8 — What the resulting screenshot does and does not show (quality expectations)

`subgraphFromObject` uses the object's real view provider, so the render carries **shape shading, per-face/edge coloring, and display mode** (Findings 3 + the FreeCAD Coin nodes `SoBrepFaceSet`, `SoBrepEdgeSet`, etc., exercised in `TestCoinNodeSnapshots.py`). It is a solid-shaded CAD view — sufficient for:

- **Phase 4 "rendered views"** deliverable (an orientation/preview image of the part), and
- **Phase 5 "vision feedback"** exploratory idea (does it *look* like the reference).

It is **not** photorealistic and does not need to be — the intent doc explicitly lists "Photorealistic rendering pipelines" as **out of scope**, and the separate FreeCAD **Render workbench** (path-tracers) is a different, heavier tool we do not need here. What headless Coin gives is exactly the lightweight, deterministic "screenshot" the tool taxonomy asks for.

*Evidence:* `docs/intent.md` Out-of-Scope ("Photorealistic rendering pipelines"); `src/Mod/Test/TestCoinNodeSnapshots.py` (renders real `SoBrep*` FreeCAD nodes offscreen with color/material).

---

## Fallback path (Outcome B) — only if GL-in-CI is rejected

If a target environment forbids any OpenGL (e.g. an extremely locked-down container with no GPU, no Mesa, no Xvfb), the Coin path is unavailable and the fallback is **geometry → mesh → CPU rasterizer**, which the Reuse Map already anticipates:

1. Tessellate the shape (`Shape.tessellate()` / Mesh workbench) — pure kernel, no GL, works in bare `FreeCADCmd`.
2. Export the mesh (already a Phase 0/4 deliverable: STL/3MF).
3. Render with a **CPU** rasterizer: `trimesh` (`trimesh.Scene.save_image` via pyglet needs GL, so prefer its `pyrender`/`matplotlib` backends), **`matplotlib` `mplot3d`** (pure CPU, trivially headless), or **`vtk`**'s offscreen software rendering. `trimesh` + `matplotlib` are already in the project's candidate stack for mesh validation.

**Trade-off:** the fallback loses FreeCAD's native materials/edge styling and design-tree fidelity (it renders a dumb mesh), and adds a dependency. It is strictly a plan-B; the native Coin path is higher-fidelity and is what FreeCAD's own tooling uses.

*Evidence:* `docs/intent.md` Reuse Map (row: "Mesh/export validation (STL/3MF) — trimesh, Open3D …"); standard headless-rendering knowledge for matplotlib/vtk software rasterization.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| `import FreeCADGui` fails in the target `FreeCADCmd` build (Gui module absent) | Low on official packages; higher on minimal/custom images | Screenshot tool unavailable | Feature-detect: `try: import FreeCADGui` and expose `query.screenshot` only when it (and a GL context) succeed; document required package (`freecad` full, not a stripped kernel-only build) |
| No OpenGL context on headless CI (no display / no Mesa) | Medium (depends on runner) | Render fails/segfaults | Use `xvfb-run` + `libgl1`/`mesa` + `LIBGL_ALWAYS_SOFTWARE=1` (FreeCAD's own CI recipe); verify in the Phase 0 CI matrix, not at Phase 4 |
| Using raw `pivy.coin.SoOffscreenRenderer` (the #13356 trap) | Low if we follow this doc | Segfault / PNG unsupported | Mandate `Gui.SoQtOffscreenRenderer` wrapper (Finding 5); never call `writeToPostScript` |
| `*Gui` module import crash headless (#16407 class) | Low (fixed upstream) | Process crash | Always `setupWithoutGUI()` first; pin FreeCAD ≥ version containing PR #21659; keep import ordering in a single helper |
| Non-deterministic pixels across runners (GPU driver diff) | Medium | Flaky visual asserts (Phase 5) | Force software GL (`llvmpipe`) + pinned fonts, as `TestCoinNodeSnapshots.py` does; assert with pixel tolerance, not exact match |
| GL context leaks / renderer singleton memory leak | Low-medium | Long-running Phase 4 service memory growth | Note: `SoFCOffscreenRenderer` is a deliberate leaking singleton (documented in its header); reuse one `SoQtOffscreenRenderer`, one `QGuiApplication`, per process; watch it in the Phase 4 50-job soak test |

---

## Recommendation

**Adopt Outcome A (native, feasible). Keep the `query.screenshot` / Phase 4 "rendered views" tool.** Do not cut it.

Concrete plan:

1. **Bridge implementation.** Implement `query.screenshot` as a thin adaptation of `src/Tools/make_snapshot.py`: lazy `import FreeCADGui` → `setupWithoutGUI()` → ensure a `QGuiApplication` exists → build a `coin.SoSeparator` root with camera + light + `subgraphFromObject(o)` for each visible object → `Gui.SoQtOffscreenRenderer(w,h)` → `render()` → `writeToImage(tmp.png)` → return the PNG bytes/path. Guard the whole thing behind capability detection so headless builds without GUI/GL degrade to "screenshot unavailable" rather than crashing.

2. **Phase 0 CI (make it real early).** Bake the GL prerequisites into the CI image now, not at Phase 4: install `xvfb`, `libgl1`/`mesa`; run the render test under `xvfb-run -a -s "-screen 0 1024x768x24"` with `LIBGL_ALWAYS_SOFTWARE=1`. Add one Phase 0 test that renders a known box headless and asserts a non-empty, correctly-sized PNG. This retires the biggest risk (GL-in-CI) during the foundation phase, satisfying the intent's "every phase's suite runs headless in CI from Phase 0."

3. **Version pin.** Require a FreeCAD version that includes the #16407 fix (PR #21659) and ships a `FreeCADCmd`-importable `FreeCADGui`; encode this in the CI version matrix (the intent already calls for a version matrix to guard API drift).

4. **Fallback (documented, not built yet).** Note the mesh-export + `matplotlib`/`vtk` CPU-raster path as the contingency if a deployment truly cannot have OpenGL. Build it only if a concrete GL-less target appears.

**Phase-0 exit-criteria verdict:** the "screenshot capture" tool is achievable headless and should remain in the Phase 0 tool set. **Phase-4 "rendered views" verdict:** deliverable is feasible on zero-GUI CI/service via `xvfb` + software GL; no scope cut required.

---

## Sources

**Primary — local FreeCAD source (`docs/references/FreeCAD/`):**

- `src/Main/MainCmd.cpp` — `FreeCADCmd` inits only `App::Application` (no Gui/Coin/Qt).
- `src/Main/FreeCADGuiPy.cpp` — `setupWithoutGUI()` (line 194), `FreeCADGui` module init (line 336), QApplication/GL requirements.
- `src/Gui/Application.cpp` — `subgraphFromObject()` (line 272) builds Coin subgraph from a transient view provider.
- `src/Gui/SoQtOffscreenRendererPy.cpp` — Python `Gui.SoQtOffscreenRenderer` with `render()` / `writeToImage()`.
- `src/Gui/SoFCOffscreenRenderer.h/.cpp`, `src/Gui/View3DPy.cpp` (`saveImage`, line 1006) — GUI-side offscreen renderer (leaking singleton note in header).
- `src/Tools/make_snapshot.py` — first-party headless snapshot tool designed for `FreeCADCmd`.
- `src/Mod/Test/TestCoinNodeSnapshots.py` — official offscreen Coin render test; software-GL / headless-QPA setup.
- `.github/workflows/sub_buildUbuntu.yml`, `.github/workflows/actions/runCPPTests/runSingleQtTest/action.yml`, `package/ubuntu/install-apt-packages.sh` — CI uses `xvfb-run`, `QT_QPA_PLATFORM=offscreen`, `xvfb` package.

**Web corroboration:**

- [Headless FreeCAD — FreeCAD wiki/documentation](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Headless_FreeCAD.md) — `setupWithoutGUI()` + `subgraphFromObject()`; "no GUI document / view providers" limitation.
- [Issue #13356 — CLI: User can't generate an image without using GUI](https://github.com/FreeCAD/FreeCAD/issues/13356) — the raw `SoOffscreenRenderer` failure mode (PNG unsupported, `writeToPostScript` SIGSEGV); still open.
- [Issue #16407 — Crash when `import PartDesignGui` in headless script](https://github.com/FreeCAD/FreeCAD/issues/16407) — fixed (PR #21659); reinforces `setupWithoutGUI()`-first ordering.
- [PR #6808 — Offscreen rendering (wwmayer)](https://github.com/FreeCAD/FreeCAD/pull/6808) — true-headless offscreen rendering groundwork.
- [Forum: Offscreen Scenegraph pivy/coin (t=83427)](https://forum.freecad.org/viewtopic.php?t=83427) and [Offscreen rendering thumbnails of .stp (t=33389)](https://forum.freecadweb.org/viewtopic.php?f=22&t=33389) — community offscreen patterns and the "Cannot load Gui module" pitfall.
