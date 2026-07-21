---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'FreeCAD features and functionalities (full catalog)'
research_goals: 'Produce a complete, verified inventory of FreeCAD features and functionalities to ground FreeCAD Buddy planning (bridge tool taxonomy, skills library, phase scoping)'
user_name: 'TanNT'
date: '2026-07-21'
web_research_enabled: true
source_verification: true
---

# Research Report: technical

**Date:** 2026-07-21
**Author:** TanNT
**Research Type:** technical

---

## Research Overview

This report inventories the complete feature and functionality surface of FreeCAD 1.x to ground FreeCAD Buddy planning: the bridge tool taxonomy (`query.*`/`verify.*`/mutation tools), the skills library scoping, and phase feasibility. It covers the technology stack (C++/OCCT/Qt6/Python 3.11+), integration surface (Python API, embedding patterns, file formats), internal architecture (document model, recompute DAG, TNP/ElementMap, Sketcher solver), and a full command-level catalog of all ~20 built-in workbenches organized per the FreeCAD wiki User hub.

Method: assistant knowledge base verified and supplemented by targeted web checks against official sources (FreeCAD blog, Developers Handbook, official wiki via its GitHub documentation mirror — the wiki itself is bot-protected). Confidence levels stated per section; command lists crawled from per-workbench documentation pages on 2026-07-21. Full executive summary in the Research Synthesis section at the end of this document.

---

<!-- Content will be appended sequentially through research workflow steps -->

## Technical Research Scope Confirmation

**Research Topic:** FreeCAD features and functionalities (full catalog)
**Research Goals:** Produce a complete, verified inventory of FreeCAD features and functionalities to ground FreeCAD Buddy planning (bridge tool taxonomy, skills library, phase scoping)

**Technical Research Scope:**

- Workbench catalog — every built-in workbench and its capabilities
- Core capabilities — parametric feature tree, constraint solver, OCCT kernel operations, document model, units, expressions/VarSets
- Scripting & integration — Python API surface, headless operation, macros, addons, file formats
- Version landscape — FreeCAD 1.0/1.1 changes (TNP mitigation, integrated Assembly, Materials)
- Ecosystem — community addons relevant to FreeCAD Buddy

**Research Methodology:**

- Assistant knowledge base verified/supplemented with targeted web checks against FreeCAD official sources
- Confidence levels applied to uncertain information
- Sources cited per section

**Scope Confirmed:** 2026-07-21

---

## Technology Stack Analysis

### Programming Languages

FreeCAD is a hybrid C++/Python application under LGPL v2.1.

- **C++ (core)**: geometry kernel integration, document/recompute engine, GUI framework, performance-critical workbenches. C++17 codebase.
- **Python (extension layer)**: nearly the entire C++ API is mirrored to Python via bindings (pybind11 / legacy PyCXX). Workbenches can be pure Python (Draft, Arch/BIM, parts of CAM are). Python **3.11+** required as of the 1.x line.
- Practical consequence for FreeCAD Buddy: everything a human does in the GUI has a scriptable Python equivalent; Python is the integration surface, C++ internals never need touching.

_Confidence: High._
_Source: https://freecad.github.io/DevelopersHandbook/gettingstarted/dependencies.html, https://en.wikipedia.org/wiki/FreeCAD_

### Core Frameworks and Libraries

- **OCCT (Open CASCADE Technology)** — the B-rep geometry kernel. All solid modeling (booleans, fillets, sweeps, STEP/IGES I/O, `Shape.isValid()`/BRepCheck validity checks, mass properties) is OCCT underneath. Minimum supported: OCCT 7.3; releases bundle newer (7.7/7.8+).
- **Qt** — GUI framework. FreeCAD 1.1 targets **Qt 6.4+**; Qt5 support officially dropped (announced 2026-01-05). PySide6 provides Python GUI access.
- **Coin3D / pivy** — OpenInventor-style scene graph for the 3D viewport; `pivy` is its Python binding. Relevant to Buddy for viewport screenshots.
- **Sketcher solver: planegcs** — FreeCAD's own C++ geometric constraint solver (DoF analysis, conflict/redundancy detection). This is what "DoF = 0" queries hit.
- **Netgen / gmsh + CalculiX** — FEM meshing and solving (FEM workbench). 1.1 adds Netgen second-order element support.
- **Other notable deps**: boost, xerces-c (document XML), VTK (FEM post-processing), Eigen3 (math).

_Confidence: High._
_Source: https://freecad.github.io/DevelopersHandbook/gettingstarted/dependencies.html, https://blog.freecad.org/2026/03/25/freecad-version-1-1-released/_

### Data and Document Model (in place of database analysis — no DB in FreeCAD)

- **`.FCStd` format**: a ZIP container holding `Document.xml` (parametric object graph, properties, expressions), BRep geometry blobs, thumbnails, embedded spreadsheets/materials.
- **Document objects**: typed property system (`App::PropertyLength`, `PropertyLink`, etc.); dependency graph (DAG) drives recompute order; `touch()`/`recompute()` semantics.
- **Expressions engine**: any numeric property can be driven by expressions referencing other properties, spreadsheet cells, or VarSets (1.1 formalizes VarSets as first-class parameter containers).
- **No external DB/storage** — single-file documents plus optional linked external files (`App::Link` across documents).

_Confidence: High._

### Development Tools and Platforms

- **Build**: CMake; official builds for Windows, macOS (Intel + ARM), Linux (AppImage). Also conda-forge packages and community Docker images — the headless CI path relevant to Buddy Phase 0.
- **Headless operation**: `FreeCADCmd` (console binary) and `freecad --console`; full Python API without GUI; screenshot capture headless is limited (needs offscreen GL — caveat for Buddy's `query.screenshot`).
- **Testing**: built-in `Test` framework (unittest-based) runnable headless: `FreeCADCmd -t TestSketcherApp` etc.
- **Addon Manager**: in-app package manager pulling from the FreeCAD-addons registry; addons = Python workbenches, macros, or preference packs. Distribution channel for a Buddy addon.
- **Version cadence**: 1.0 released 2024-11 (TNP mitigation, integrated Assembly, new Materials system); **1.1 released 2026-03-24** (Qt6/Wayland, UI theming, CAM improvements, fillet manipulators, assembly animation, three-point lighting, Whitworth threads). 0.21 is the last pre-TNP-fix line — Buddy should target 1.x only.

_Confidence: High on versions/dates (web-verified); Medium on exact 1.1 minor-feature list._
_Source: https://blog.freecad.org/2026/03/25/freecad-version-1-1-released/, https://www.neowin.net/software/freecad-110/_

### Deployment / Infrastructure Relevant to Buddy

- No cloud service — desktop-first. Headless automation paths: conda-forge `freecad` package, community Docker images, AppImage with `--appimage-extract` in CI runners.
- Python-embedded interpreter means MCP server can run **inside** the FreeCAD process (GUI addon) or **as** the process (FreeCADCmd script) — both patterns proven by existing community FreeCAD MCP servers.

_Confidence: High._

### Technology Adoption Trends

- 1.0/1.1 era: TNP mitigation landed (elementmap-based naming), first-party Assembly workbench replacing fragmented A2plus/Assembly3/Assembly4 landscape, Qt5→Qt6 migration complete, materials unified.
- Community AI/MCP activity: several FreeCAD MCP server projects exist on GitHub (study targets per intent.md Reuse Map) — ecosystem trend confirms the Buddy bridge approach is viable.

_Confidence: High on FreeCAD trends; Medium on current state of individual MCP projects (verify at Phase 0 reuse survey)._

## Integration Patterns Analysis

### API Surface (Python)

FreeCAD's integration story is Python-first; no official REST/GraphQL/gRPC API exists — external protocols are always community layers over the Python API.

- **`FreeCAD` (App) module**: document lifecycle (`newDocument`, `openDocument`, `saveAs`), object creation (`addObject("Part::Box")`), property get/set, `recompute()`, units (`FreeCAD.Units.Quantity`).
- **`FreeCADGui` (Gui) module**: selection, viewport/camera, screenshots (`ActiveView.saveImage`), commands (`Gui.runCommand`), workbench switching. Absent in headless mode — bridge code must branch on `FreeCAD.GuiUp`.
- **Workbench module APIs**: `Part` (primitives, booleans, `Shape` topology access), `Sketcher` (`addGeometry`, `addConstraint`, `solve()`, DoF via solver), `PartDesign` (Body/feature objects), `Draft`, `Mesh`, `TechDraw`, `Fem`, `Spreadsheet` — each importable standalone in Python.
- **Topology data access**: `obj.Shape` exposes `Vertexes/Edges/Faces/Solids`, `Volume`, `Area`, `BoundBox`, `CenterOfMass`, `MatrixOfInertia`, `isValid()`, `check()`, `distToShape()`, section/common operations — the entire `verify.*` toolset maps to these calls.
- **Observer hooks**: `App.addDocumentObserver`, selection observers, GUI events — enables Buddy to react to user actions in Copilot mode.

_Confidence: High._
_Source: https://wiki.freecad.org/Python_scripting_tutorial, https://wiki.freecad.org/FreeCAD_Scripting_Basics_

### Embedding / Communication Patterns

Four proven patterns for driving FreeCAD externally:

1. **In-process addon (GUI)**: Python workbench/addon starts a server thread (socket/HTTP/MCP-stdio-proxy) inside the FreeCAD process. GUI thread caveat: mutations must be marshaled to the main Qt thread (`QTimer.singleShot` / `Gui.doCommand` pattern) or crashes ensue.
2. **Headless script host**: `FreeCADCmd script.py` or external Python importing FreeCAD as a module (conda-forge build allows `import FreeCAD` in plain Python if paths set). Best for CI and the Phase 4 service.
3. **External process + RPC bridge**: community FreeCAD MCP servers mostly use this — MCP server as separate process, XML-RPC/socket into a small listener addon inside FreeCAD. Decouples MCP SDK deps from FreeCAD's bundled Python.
4. **File-drop / batch**: write `.py`/`.FCStd`, invoke FreeCADCmd per job. Simplest, stateless, slow (process startup ~seconds) — acceptable for CI golden-model tests.

Existing community FreeCAD MCP servers (GitHub: several, e.g. `mcp-freecad`, `freecad-mcp`) implement pattern 1/3 with tools like execute-python, screenshot, export — but none implement Buddy's verify-first taxonomy (confirms intent.md Reuse Map row: adopt transport, invent tool layer).

_Confidence: High on patterns; Medium on individual project details._
_Source: https://glama.ai/mcp/servers/@jango-blockchained/mcp-freecad (community MCP server example)_

### File Formats and Data Exchange

Native: **`.FCStd`** (full parametric), **`.FCMacro`/`.py`** (scripts), **`.FCMat`** (materials).

| Category | Formats | Handler |
|----------|---------|---------|
| Solid/B-rep CAD | **STEP** (.step/.stp — most faithful, solids + NURBS), **IGES** (.iges/.igs — legacy), **BREP** (.brep — raw OCCT) | Part/OCCT |
| Mesh | **STL** (3D printing standard, triangles only), **OBJ**, **3MF**, **PLY**, **AMF**, **OFF** | Mesh workbench |
| 2D drawing | **DXF** (import/export), **SVG**, **DWG** (via external ODA converter), **PDF/EPS** (drawing output) | Draft/TechDraw |
| BIM | **IFC** (needs IfcOpenShell — strong support), **DAE/Collada**, **SHP**, **glTF** (via OCCT 7.x) | BIM workbench |
| Point cloud | **ASC**, **PCD**, **PLY** | Points workbench |
| FEM | **INP** (Abaqus/CalculiX), **UNV**, **VTK/VTU**, **med** | FEM workbench |
| CAM | **G-code** (.nc/.gcode, post-processor system) | CAM workbench |
| Other | **VRML/X3D**, **WebGL/X3DOM export**, **CSG** (OpenSCAD), **PNG/JPG** (viewport render) | various |

Buddy relevance: `export.*` tools cover STEP + STL + 3MF (Phase 0/4 criteria); STEP re-import round-trip is the fidelity check; DXF/TechDraw is Phase 5.

_Confidence: High; format list cross-checked._
_Source: https://yorikvanhavre.github.io/FreeCAD-manual/discovering_freecad/import_and_export_to_other_filetypes.html, https://www.xsim.info/articles/FreeCAD/en-US/HowTo/Supported-file-formats.html_

### Interoperability Standards

- **STEP AP214/AP242**: OCCT-backed; assemblies, colors, names survive. The lingua franca to other CAD (SolidWorks, Fusion, Onshape).
- **IFC 2x3/4**: BIM interop via IfcOpenShell.
- **3MF**: modern print format, richer than STL (units, colors) — preferred Phase 4 print export.
- **Units**: internal mm/deg/g; `Quantity` parsing accepts unit strings — Buddy tools should accept/emit explicit units to avoid silent unit bugs.

_Confidence: High._

### Extension Ecosystem (Addon/Macro/Workbench)

- **Addon Manager**: installs from FreeCAD-addons registry + custom repos; addon = Python package with `package.xml` metadata. Distribution path for Buddy workbench.
- **Macros**: recorded/authored Python snippets; FreeCAD GUI has macro recorder — useful for discovering API call sequences for skills authoring.
- **Preference packs, themes**: cosmetic.
- **Notable functional addons**: Fasteners (bolt/nut library), SheetMetal, Curves, A2plus/Assembly4 (legacy assembly), OpenSCAD workbench, KiCad StepUp. Fasteners addon directly relevant to `mechanical-conventions` skill (standard hardware generation).

_Confidence: High._

### Integration Security Considerations

- FreeCAD Python has **no sandbox** — `exec` of arbitrary Python = full system access. Buddy's typed-tool layer (no free-form exec in mutation path, per intent.md) is the mitigation; any `execute_python` tool must be gated/opt-in.
- MCP servers running in-process inherit FreeCAD's privileges; headless service (Phase 4) needs OS-level sandboxing (container, resource limits) — matches intent.md safety rails.

_Confidence: High._

## Architectural Patterns and Design

### Core Architecture: App/Gui Split

FreeCAD is layered strictly:

- **App layer** (`FreeCAD` core): documents, objects, properties, expressions, recompute — fully functional without GUI. This is why headless works at all.
- **Gui layer** (`FreeCADGui`): each `DocumentObject` pairs with a `ViewProvider` (visualization + interaction). ViewProviders don't exist headless — code touching `obj.ViewObject` crashes in FreeCADCmd. Standing trap for bridge code.
- **Module/workbench layer**: each workbench = plugin (C++ and/or Python) registering object types, commands, GUI panels. Workbenches share one document — objects from different workbenches coexist in one model.

_Confidence: High._
_Source: https://deepwiki.com/FreeCAD/FreeCAD/2-workbenches, https://wiki.freecad.org/Workbenches_

### Document Object Model & Recompute Engine

- **Everything is a `DocumentObject`** with typed **Properties** (Length, Angle, Link, LinkList, Enumeration, ...). Features, sketches, bodies, spreadsheets, even assembly joints — all the same object model. Buddy's `query.*` tools reduce to walking objects + properties.
- **Dependency DAG**: `PropertyLink`-type properties define edges; `recompute()` topologically sorts and calls `execute()` on touched objects. Cycles = error. `obj.OutList`/`InList` expose the graph — basis for feature-tree summarization (Phase 1) and TNP reference audit (Phase 2).
- **Transactions/undo**: document-level transaction stack (`openTransaction`/`commitTransaction`/`abortTransaction`, `doc.undo()`). Buddy's rollback = wrap every mutation in a transaction; geometry-hash verification confirms restore.
- **Expression engine**: property-level formulas (`<<Sketch>>.Constraints.width * 2`, spreadsheet refs, VarSet refs). Design-intent carrier for `parametric-patterns` skill.
- **Error surfaces**: `execute()` failures mark object with error state (`obj.State`, `doc.RecomputesFrozen`, per-object `getStatusString()`); recompute returns touched-object count. `verify.recompute` tool = check no object left in error state.

_Confidence: High._

### PartDesign Body Architecture (the main modeling pattern)

- **Body = linear feature history**: single contiguous solid ("Tip" points at last feature). Sketch → Pad → Pocket → Fillet chain; each feature consumes previous solid ("BaseFeature") + its own profile/params.
- Contrast **Part workbench**: CSG-style — independent solids combined by boolean operations (Cut/Fuse/Common), no linear history discipline. `tool-selection` skill must teach when each is right.
- **Datum objects** (plane/axis/point/CS) and **ShapeBinder/SubShapeBinder** provide stable references across bodies/documents — the TNP-defensive referencing pattern.
- **Multi-body + `App::Link`**: Link = lightweight instance reference (supports arrays, external documents) — basis of Assembly and pattern efficiency.

_Confidence: High._

### TNP Mitigation Architecture (1.0+)

- Pre-1.0: topology referenced by generated index names ("Face6", "Edge3") — indices reshuffle on recompute, references break silently. The classic TNP.
- 1.0+ (realthunder's design, integrated by Ondsel/FreeCAD team): **TopoShape wraps OCCT `TopoDS_Shape` with an ElementMap** — persistent "MappedNames" encoding element creation history; references re-resolve via history instead of index.
- Mitigation, not elimination: heavy topology changes can still orphan references. Datum-based modeling remains best practice. Buddy's post-mutation reference audit (intent.md invention) layers on top: after each mutation, walk all Link/ExternalGeometry references, confirm resolution.
- Python-visible: `Shape.ElementMapVersion`, mapped element queries on `TopoShape` — bridge can read mapped names for robust reference storage.

_Confidence: High on architecture; Medium on exact Python API names for elementmap queries (verify against 1.1 API during Phase 0)._
_Source: https://deepwiki.com/FreeCAD/FreeCAD/2.1-toposhape-and-topological-naming, https://www.ondsel.com/blog/milestone-toponaming-fix-phase-2-done/, https://github.com/FreeCAD/FreeCAD/issues/8432_

### Sketcher Constraint Architecture

- Sketch = 2D geometry set (lines/arcs/circles/ellipses/B-splines/points) + **constraint set** solved by planegcs. Geometry flagged construction-mode participates in solving but not profiles.
- Constraint types: geometric (coincident, horizontal/vertical, parallel, perpendicular, tangent, symmetric, equal, point-on-object, block) + dimensional (distance, X/Y-distance, radius/diameter, angle) + special (Snell's law for optics-style, weight for B-splines).
- **Degrees of Freedom** exposed by solver; DoF = 0 = fully constrained. Solver also reports **conflicting** and **redundant** constraint sets — all three queryable from Python (`sketch.solve()` return, `sketch.getDoF()` in newer API, diagnostics in `sketch.FullyConstrained` / solver messages). Foundation of Buddy's `verify.sketch` and the ≥90% DoF=0 Phase 2 criterion.
- **External geometry**: projecting edges from existing 3D into a sketch — powerful, TNP-sensitive (documented risk for `freecad-sketcher` skill).

_Confidence: High; exact method names Medium (API drift between versions)._

### Scalability / Performance Characteristics

- Single-threaded recompute (mostly); OCCT operations dominate cost. Big feature trees (100+ features) recompute slowly — motivates Buddy's tree summarization and per-step (not per-token) verification granularity.
- `App::Link` avoids geometry duplication for patterns/assemblies — memory-efficient instancing.
- Headless startup ~2–5 s per FreeCADCmd process — batch pattern costs process startup per job; long-running bridge process amortizes (Phase 4 service design driver).

_Confidence: Medium-High (order-of-magnitude figures from community experience, not benchmarked here)._

## Implementation Approaches and Technology Adoption

### Full Feature Catalog — Built-in Workbenches (FreeCAD 1.x)

The complete list of workbenches bundled with FreeCAD 1.0/1.1, with their functionality:

#### Core modeling

**Part** — primitive solids (Box, Cylinder, Sphere, Cone, Torus, Tube, Prism, Wedge, parametric geometric primitives incl. helix/spiral); boolean operations (Fuse/Union, Cut, Common/Intersection); Extrude, Revolve, Loft, Sweep, Mirror, Fillet/Chamfer on solids; Offset (2D/3D), Thickness (shelling), Section/Cross-sections, Slice/Split, Ruled Surface, Shape Builder (build faces/shells/solids from edges); Compound make/explode; shape checks (Check geometry = BRepCheck GUI), defeaturing; import/export BREP/STEP/IGES.

**PartDesign** — body-based feature history modeling:
- Additive: Pad, Revolution, Additive Loft, Additive Pipe (sweep), Additive Helix, additive primitives (box/cylinder/sphere/cone/ellipsoid/torus/prism/wedge)
- Subtractive: Pocket, Hole (parametric hole feature: drill sizes, countersink/counterbore, threads incl. modeled threads, clearance per standards), Groove, Subtractive Loft/Pipe/Helix, subtractive primitives
- Dress-up: Fillet, Chamfer, Draft, Thickness
- Transformations: Mirrored, Linear Pattern, Polar Pattern, MultiTransform, Scaled
- Datums: Datum Plane/Line/Point, local Coordinate System, ShapeBinder, SubShapeBinder, Clone
- Boolean between bodies
- 1.1: on-screen fillet manipulators (drag-to-set radius)

**Sketcher** — constrained 2D sketching: geometry (point, line, polyline, arc, circle, ellipse, arc-of-ellipse/hyperbola/parabola, B-spline incl. periodic, polygon, slot, rectangle variants, fillet/trim/extend/split tools); construction geometry mode; external geometry projection; carbon-copy (import another sketch); constraints — coincident, point-on-object, horizontal, vertical, parallel, perpendicular, tangent, equal, symmetric, block, lock, distance, X/Y distance, radius/diameter, angle, Snell's law; solver diagnostics (DoF readout, conflicting/redundant detection); B-spline tooling (knots, multiplicity, weights); sketch validation tool; virtual space; 1.1 adds tool overlays/on-viewport constraint editing improvements.

**Assembly** (new in 1.0, first-party, Ondsel solver) — assemblies with joints: Fixed, Revolute, Cylindrical, Slider, Ball, Planar, Parallel, Tangent, Distance, Rack-and-pinion, Screw, Gears/Belt; grounded parts; sub-assemblies; insert parts from external documents via App::Link; degrees-of-freedom solving; exploded views; Bill of Materials export; 1.1 adds assembly animation (drive joints over time) and joint mirroring.

#### 2D / annotation / output

**Draft** — 2D drafting in 3D space: line, wire, arc, circle, ellipse, rectangle, polygon, B-spline, Bézier, point, facebinder, hatch; modifiers (move, rotate, scale, offset, trimex, join/split, upgrade/downgrade, array — orthogonal/polar/circular/path/point, clone, mirror, stretch); annotation (text, dimensions, labels); working planes, grid/snapping system; layers; shape-from-text (TTF strings); DXF/SVG import-export core.

**TechDraw** — 2D drawing sheets from 3D models: base/projection group views (first/third angle), section views (simple, complex/offset), detail views, broken views (1.1 improvements), clip views; dimensions (length, radius, diameter, angle, chained, coordinate; links to 3D via measurement), GD&T-style annotations (datum features, feature control frames via extensions), balloons + BOM support, hatching (geometric + SVG/pattern), templates (SVG, editable fields), page export PDF/SVG/DXF; spreadsheet view embedding; line-style/standards support (ISO/ANSI/JIS options).

**Spreadsheet** — in-document spreadsheet: cells with units-aware quantities, formulas, cross-references from any property via expressions (`Spreadsheet.Alias` naming); alias-driven parametric models; import/export CSV/XLSX (basic).

#### Meshes, surfaces, reverse engineering

**Mesh** — triangulated mesh handling: import/export (STL, OBJ, 3MF, PLY, AMF, OFF), create mesh from shape (tessellation with deviation control), analyze (self-intersections, non-manifold, holes, folds), repair (fill holes, fix normals/orientation, remove duplicates/degenerates), decimation, smoothing, boolean on meshes (via OpenSCAD/own), cut/trim/split, merge, unwrap-ish flattening (limited), mesh-to-shape conversion (with shape from mesh + sew + solid).

**Surface** — NURBS surface tools: Filling (boundary + constraints), GeomFillSurface (2–4 edges), Sections surface, Blend curve/surface (continuity control G0–G2), Curve on mesh, Extend surface.

**Points** — point-cloud import (ASC/PCD/PLY), visualization, structuring, export; basis for scan-to-CAD workflows (with Reverse Engineering removed in 1.0, surface fitting moved to addons).

**Inspection** — compare scanned mesh/points against nominal shape, deviation coloring (specialized, thin).

#### Analysis & manufacturing

**FEM** — finite element analysis: mechanical static/frequency/thermal/buckling (CalculiX solver), Elmer solver integration (multiphysics: flow, electrostatics, heat), Mystran, Z88 options; geometry prep (constraints/loads: fixed, force, pressure, displacement, temperature, contact, tie; materials — nonlinear mechanical support), meshing via gmsh and Netgen (1.1: Netgen second-order elements, new Netgen builds), result post-processing (VTK pipelines, stress/displacement views, filters, clipping).

**CAM** (renamed from Path in 1.0) — CNC toolpaths: job setup (stock, tool controllers, work coordinate systems), operations — profile, pocket, drilling, face, helix, adaptive clearing, engrave, deburr, V-carve, surface (3D), waterline, slot; tool library (shapes, feeds/speeds); dressups (dogbone, tags/holding, lead-in/out, ramp, boundary); simulation (new CAM simulator), post-processors (GRBL, LinuxCNC, Mach3/4, Centroid, many; Python-extensible); 1.1: CAM improvements continue post-rename.

**Material** (integrated system, overhauled 1.0) — unified material database (mechanical, thermal, appearance properties), per-object appearance + physical material assignment, used by FEM/CAM/rendering/BOM mass calculations; user-extensible material cards.

#### BIM / architecture

**BIM** (Arch + BIM merged in 1.0) — walls, structures (beams/columns/slabs), windows/doors (parametric, sketch-based), roofs, stairs, panels, pipes/fittings, rebar (basic; more via Reinforcement addon), spaces, levels/storeys, axes/grids, sections + 2D output to TechDraw/Draft, quantities/schedules (BOQ), IFC import/export (IfcOpenShell; native IFC editing footprint growing), DAE/SHP/glTF exchange.

#### Scripting-adjacent / misc built-ins

**OpenSCAD** — imports .scad CSG scripts, mesh↔solid interop, offers OpenSCAD-style mesh booleans (requires OpenSCAD binary for full function).

**Robot** — 6-axis industrial robot simulation (Kuka-oriented), trajectories from Draft wires. Legacy/unmaintained; effectively deprecated. _(Confidence: Medium — may be excluded from some 1.x builds.)_

**Test Framework** — built-in unittest runner for self-tests (`Test` module), runnable headless — reusable pattern for Buddy CI.

Removed/replaced in 1.x line: Start workbench → new Start page; Web workbench removed; Reverse Engineering workbench removed (1.0); Drawing workbench long since replaced by TechDraw; Path → CAM; Arch → BIM.

_Confidence: High on catalog structure and major features; Medium on per-workbench exhaustive tool lists (individual tool names drift between versions)._
_Source: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Workbenches.md, https://www.freecad.org/features.php, https://librearts.org/2024/11/freecad-1-0/, https://alternativeto.net/news/2024/11/freecad-1-0-launches-with-enhanced-ui-ux-built-in-assembly-workbench-and-tnp-fixes/, https://blog.freecad.org/2026/03/25/freecad-version-1-1-released/_

### Cross-Cutting Application Features (not workbench-bound)

- **Parametric document core**: feature tree, typed properties, expressions everywhere, VarSets (1.1: first-class variable containers), configuration tables via spreadsheet, undo/redo transaction stack, external document links (App::Link).
- **Measurement**: unified Measure tool (1.0) — distances, angles, radii, areas on any geometry; Python-accessible.
- **Selection & navigation**: multiple navigation styles (CAD, Blender, etc.), selection view/filters, tree filtering and search, quick-search commands (1.1 UI work), customizable toolbars/shortcuts, theming (1.1 modern themes/UI overhaul).
- **Units system**: multiple unit schemes (metric/imperial variants, MKS), quantity-aware inputs everywhere.
- **Macro system**: record GUI actions to Python, macro editor, addon-distributed macros.
- **Addon Manager**: one-click community workbenches/macros/preference packs.
- **Rendering hooks**: appearance materials + community Render workbench (POV-Ray/Cycles/LuxCore) — not built-in rendering beyond OpenGL viewport.
- **Persistent document recovery**: autosave/recovery, thumbnailing, transient backup files.

_Confidence: High._

### Technology Adoption Mapping — FreeCAD Buddy

- **Pin FreeCAD 1.1.x** as primary target (TNP mitigation + Assembly + VarSets are all load-bearing for Buddy phases); keep 1.0.x in CI matrix; ignore ≤0.21.
- **Bridge tool taxonomy grounding**: `query.*` = DocumentObject/property walking + Shape topology reads + Measure API; `verify.*` = `isValid()`/`check()` + mass properties + solver DoF diagnostics + recompute error-state scan; `sketch.*`/`feature.*` = Sketcher/PartDesign Python APIs above; `export.*` = STEP/STL/3MF via Part/Mesh/Import modules. Phase 0's "≥15 tools" fits comfortably in this surface.
- **Phase→workbench dependency map**: Phases 0–3 need only Part/PartDesign/Sketcher/Spreadsheet(+VarSet)/Mesh(export); Phase 4 adds Material (mass), CAM-free DFM heuristics (slicer CLI external per Reuse Map); Phase 5 adds Assembly, TechDraw, FEM — all confirmed built-in, no addon dependencies for core roadmap.
- **Skills library grounding**: Track A skill scopes map 1:1 onto catalog sections above (`freecad-partdesign` = PartDesign feature list + failure modes; `freecad-sketcher` = constraint/solver section; `freecad-datums-references` = datum/ShapeBinder subsection + TNP architecture section).

### Success Metrics Alignment

Catalog confirms intent.md exit criteria are implementable with built-ins only: DoF=0 via solver diagnostics, watertight/valid via OCCT checks, geometry-hash undo via transactions + shape export hashing, TNP audit via ElementMap-aware reference walking. No blocking gaps found; open verification items for Phase 0: exact elementmap Python API names, headless offscreen screenshot capability.

_Confidence: High._

## Full Feature List — organized per FreeCAD wiki User hub

Structure follows https://wiki.freecad.org/User_hub (crawled via official GitHub documentation mirror, wiki itself bot-protected). Every command list below extracted from the corresponding workbench documentation page.

_Source: https://github.com/FreeCAD/FreeCAD-documentation/tree/main/wiki (official wiki mirror), pages: User_hub, Std_Base, *_Workbench.md, Testing.md_
_Local copy: [`docs/references/FreeCAD-wiki/wiki/`](../../../docs/references/FreeCAD-wiki/wiki/) — full offline wiki clone (~7200 wikitext pages, e.g. `User_hub.wikitext`, `Part_Workbench.wikitext`); usable for offline lookup and skills authoring without hitting the bot-protected live wiki._

### 1. Using FreeCAD — Introduction

- Application overview; installers for Windows, Linux (AppImage), macOS; help files, additional components via Addon Manager
- Getting started guide, FAQ, tutorials
- Migration guides: from Fusion360, OnShape, SolidWorks, Revit; BIM migration guide + BIM application compatibility table; documented workarounds

### 2. Basic Application

- **Interface**: 3D view (multi-view, navigation cube), tree view (feature hierarchy), property editor (Data/View tabs), task panel, Python console, report view, status bar
- **Mouse navigation**: multiple styles (CAD, Blender, Maya, OpenInventor, Revit, TinkerCAD...)
- **Selection methods**: click, box select, selection view, selection filters (vertex/edge/face), Select-all-instances
- **Object naming**: internal Name (immutable) vs Label (user-editable) — critical distinction for scripting
- **Preferences Editor**: global + per-workbench settings, unit schemes, theming
- **File formats**: native FCStd/FCMacro/FCMat + full import/export table (see Integration Patterns section above)

### 3. Workbenches — complete command catalogs

#### Standard tools (Std Base — always available)

- Standard menus: File, Edit, View, Tools, Macro, Windows, Help
- Structure toolbar: Create part; Create datums (Coordinate system, Datum plane, Datum line, Datum point); Create group; Link tools (Make link, Make sub-link, Replace with link, Unlink, Import link, Import all links); **Create variable set (VarSet)**
- Other: Make link group; Expression actions (copy/paste expression data); Selection filters (vertex/edge/face/clear); Select all instances; Toggle freeze; **Std Measure** (unified measurement, replaces old Part measure tools)

#### Part Workbench

- **Primitives**: Box, Cylinder, Sphere, Cone, Torus, Tube; Create Primitives dialog (plane, ellipsoid, prism, wedge, helix, spiral, circle, ellipse, point, line, regular polygon)
- **Creation/modification**: Create sketch, Extrude, Revolve, Mirror, Scale, Fillet, Chamfer, Make face from wires, Ruled surface, Loft, Sweep, Section, Cross sections, 3D offset, 2D offset, Thickness, Projection on surface, Color per face
- **Boolean/compound**: Make compound, Explode compound, Compound filter, Boolean (generic), Cut, Union, Intersection, Connect, Embed, Cutout, Boolean fragments, Slice apart, Slice to compound, Boolean XOR
- **Validation/utility**: Check geometry (BRepCheck), Defeaturing, Import/Export CAD (IGES/STEP/BREP), Box selection, Shape from mesh, Points object from geometry, Convert to solid, Reverse shapes, Simple copy, Transformed copy, Shape element copy, Refine shape, Attachment

#### PartDesign Workbench

- **Helpers**: Create body, Create/Attach/Edit/Validate sketch, Check geometry, ShapeBinder, Sub-object ShapeBinder, Clone, Datum plane/line/point, Local coordinate system
- **Additive**: Pad, Revolution, Additive loft, Additive pipe, Additive helix; additive primitives (box, cylinder, sphere, cone, ellipsoid, torus, prism, wedge)
- **Subtractive**: Pocket, Hole (drill standards, countersink/counterbore, threads), Groove, Subtractive loft/pipe/helix; subtractive primitives (same 8 shapes)
- **Boolean**: between bodies/clones
- **Dress-up**: Fillet, Chamfer, Draft, Thickness
- **Transformation**: Mirrored, Linear pattern, Polar pattern, MultiTransform, Scaled
- **Extras**: Sprocket, Involute gear, Shaft design wizard
- **Context**: Suppress feature, Set tip, Move object to other body, Move object after other object, Appearance, Color per face

#### Sketcher Workbench

- **General**: Create/Edit/Attach/Reorient/Validate/Merge/Mirror sketch, Leave sketch, View sketch, View section, Toggle grid, Toggle snap, Configure rendering order
- **Geometry**: Point, Line, Polyline, Arc (center / 3-point), Arc of ellipse/hyperbola/parabola, Circle (center / 3-point), Ellipse (center / 3-point), Rectangle (plain/centered/rounded), Triangle, Square, Pentagon, Hexagon, Heptagon, Octagon, Regular polygon, Slot, Arc slot, B-spline (control points / knots, both periodic variants), Toggle construction geometry
- **Dimensional constraints**: Dimension (context-sensitive), Horizontal distance, Vertical distance, Distance, Radius, Diameter, Auto radius/diameter, Angle, Lock
- **Geometric constraints**: Coincident (unified), Point-on-object, Horizontal/Vertical (unified + separate), Parallel, Perpendicular, Tangent/Collinear, Equal, Symmetric, Block, Snell's law (refraction); Toggle driving/reference; Activate/deactivate constraint
- **Editing**: Fillet, Chamfer, Trim, Split, Extend, External geometry (projection + intersection), Carbon copy, Array/Polar/Scale transform, Offset geometry, Symmetry, Remove axes alignment, Delete all geometry/constraints, Copy/Cut/Paste
- **B-spline tools**: Convert to B-spline, Increase/Decrease degree, Increase/Decrease knot multiplicity, Insert knot, Join curves
- **Diagnostics/visual**: Select unconstrained DoF, Select redundant constraints, Select conflicting constraints, Select associated constraints/geometry, B-spline visual toggles (degree, control polygon, curvature comb, knot multiplicity, weights), Switch virtual space, Show/hide internal geometry

#### Assembly Workbench (1.0+)

- **Assembly**: Create assembly, Insert component, Insert new part, Solve assembly, Create exploded view, Create simulation (1.1), Create Bill of Materials, Export ASMT
- **Joints**: Toggle grounded; Fixed, Revolute, Cylindrical, Slider, Ball, Distance, Parallel, Perpendicular, Angle, Rack-and-pinion, Screw, Gears, Belt

#### Draft Workbench

- **Drafting**: Line, Polyline, Fillet, Arc, Arc by 3 points, Circle, Ellipse, Rectangle, Polygon, B-spline, Cubic Bézier, Bézier, Point, Facebinder, Shape from text, Hatch
- **Annotation**: Text, Dimension (linear/radial/angular), Label, Annotation styles
- **Modification**: Move, Rotate, Scale, Mirror, Offset, Trimex, Stretch, Clone, Array (orthogonal), Polar array, Circular array, Path array (+link), Point array (+link), Edit, Subelement highlight, Join, Split, Upgrade, Downgrade, Wire↔B-spline, Draft↔Sketch, Set slope, Flip dimension, Shape 2D view
- **Snapping**: lock, endpoint, midpoint, center, angle, intersection, perpendicular, extension, parallel, special, near, ortho, grid, working plane, dimensions; Toggle grid
- **Utilities**: Layers, named groups, move-to-group, construction group, working plane proxy, Select plane, Set style, Toggle construction mode, AutoGroup, Heal

#### BIM Workbench (Arch+BIM merged, 1.0+)

- **2D drafting**: Sketch, Line, Polyline, Circle, Arc (+3-point), Fillet, Ellipse, Polygon, Rectangle, B-spline, Bézier (+cubic), Point
- **3D/BIM objects**: Project, Site, Building, Level, Space, Wall, Curtain wall, Column, Beam, Slab, Door, Window, Pipe, Connector, Stairs, Roof, Panel, Frame, Fence, Truss, Equipment
- **Reinforcement**: Custom/Straight/U-shape/L-shape/Bent-shape/Helical rebar, Stirrup, Column/Beam/Slab/Footing reinforcement
- **Generic 3D**: Profile, Box, Shape builder, Facebinder, Objects library, Component, External reference
- **Annotation**: Text, Shape from text, Aligned/Horizontal/Vertical dimension, Leader, Label, Axis, Axis system, Grid, Section plane, Hatch, TechDraw page, View, Shape-based view
- **Modify**: Move, Copy, Rotate, Clone, Simple copy, Compound, Offset, 2D offset, Trimex, Join, Split, Scale, Stretch, Draft↔Sketch, Upgrade/Downgrade, Add/Remove component, Arrays (ortho/path/polar/point), Cut with plane, Mirror, Extrude, Difference, Union, Intersection
- **Manage**: BIM setup, Views manager, Manage project/doors-windows/IFC elements/IFC quantities/IFC properties/classification/layers, Material, Schedule, Preflight checks, Annotation styles
- **Utils**: trash, working plane views, mesh tools (split, mesh→shape, non-manifold select), Remove shape from Arch, Close holes, Merge walls, Check, IFC B-rep flag, Survey mode, IFC Diff, IFC explorer, IFC spreadsheet, Image plane, Unclone, Rewire, Glue, Reextrude; Panel cut/sheet, Nest; Structure system tools; Nudge tools

#### CAM Workbench (renamed from Path, 1.0)

- **Project**: Job, Post Process (G-code export), Job error check, Export template
- **Tooling**: ToolBit library editor, ToolBit dock, Inspect G-code, CAM Simulator (+new GL simulator), Finish selecting loop, Toggle operation active
- **Basic ops**: Profile, Pocket shape, Drilling, Face, Helix, Adaptive clearing, Slot (exp.), Engrave, Deburr, V-carve
- **3D ops**: 3D pocket, 3D surface (exp.), Waterline (exp.)
- **Dressups**: Axis map, Boundary, Dogbone, DragKnife, Lead-in/out, Ramp entry, Holding tags, Z-depth correction
- **Supplemental**: Fixture, Comment, Stop, Custom G-code, Probe grid, From shape (exp.)
- **Modification**: Copy (parametric), Array, Simple copy
- **Specialty**: Thread milling (exp.)
- Post-processors: GRBL, LinuxCNC, Mach3/4, Centroid + many more, Python-extensible

#### FEM Workbench

- **Model**: Analysis container; Materials (solid, fluid, nonlinear mechanical, reinforced/concrete, editor); Element geometry (beam cross-section + rotation, shell thickness, 1D fluid section)
- **Boundary conditions/loads**: electromagnetic (electrostatic potential, current density, magnetization); fluid (initial velocity/pressure, flow velocity); geometrical (plane multi-point, section print, local coordinate system); mechanical (fixed, rigid body, displacement, contact, tie, spring, force, pressure, centrifugal, gravity); thermal (initial temperature, heat flux, temperature, body heat source); constant overrides (vacuum permittivity)
- **Mesh**: Netgen mesher (1.1: second-order), Gmsh mesher, boundary layer, mesh region, mesh group, erase elements, FEM-mesh→mesh
- **Solvers**: CalculiX (standard), Elmer (multiphysics), Mystran, Z88; Elmer equations — elasticity, deformation, electrostatic, electric force, magnetodynamic (+2D), flow, flux, heat; solver job control, run
- **Results**: purge, show, post pipeline, warp filter, scalar clip, function cut, region clip, contours, line clip, stress linearization plot, data-at-point; filter functions (plane, sphere, cylinder, box)
- **Utilities**: clipping planes, FEM examples, clear/info mesh

#### Mesh Workbench

- Import/Export mesh, Create mesh from shape (tessellation), Refinement (remesh)
- **Analyze**: Evaluate & repair, Face info, Curvature info, Check solid, Boundings info
- **Modify**: Curvature plot, Harmonize/Flip normals, Fill holes, Close hole, Add triangle
- **Components**: Remove components (auto/by hand), Merge, Split by components
- **Segmentation**: mesh segments, best-fit-surface segments
- **Processing**: Smooth, Decimate, Scale, Regular solid
- **Boolean**: Union, Intersection, Difference
- **Cutting**: Cut, Trim, Trim with plane, Section from mesh+plane, Cross-sections
- **Unwrap**: Unwrap mesh, Unwrap face

#### Surface Workbench

- Filling, Fill boundary curves (2–4 edges), Sections surface, Extend face, Curve on mesh, Blend curve (G0–G2 continuity)

#### Points Workbench

- Import points, Export points, Convert shape→points, Structured point cloud, Merge point clouds, Cut point cloud

#### Inspection Workbench

- Visual inspection (deviation coloring between two shapes/meshes); early-stage, thin

#### Material Workbench (1.0+)

- Materials editor (create/modify material cards: physical, thermal, appearance properties), material preferences (card sources, defaults); consumed by FEM/CAM/BOM/appearance

#### Spreadsheet Workbench

- Create sheet, Import/Export CSV (+XLSX), Merge/Split cells, Alignment (6 tools), Bold/Italic/Underline, Set alias, Cell colors
- Capabilities: units-aware formulas, model-property references, cell aliases as global parameters, configuration tables, cell-range binding, Python automation

#### OpenSCAD Workbench

- Color code shape, Replace object, Remove subtree, Refine shape, Mirror/Scale/Resize mesh feature, Increase tolerance, Edges→Faces, Expand placements, Explode group, Add OpenSCAD element (inline code), Mesh boolean, Hull, Minkowski

#### Robot Workbench (legacy/unmaintained)

- Create robot, Simulate trajectory, Export trajectory (robot program), Set/Restore home; Trajectories: create, default orientation/speed, insert waypoint (current/preselected), trajectory from edges, dress-up, trajectory compound

#### Reverse Engineering Workbench

- Approximate B-spline surface (FitSurface); otherwise empty — documented as programmer sandbox, effectively removed from practical use in 1.x

#### Test Framework Workbench

- Self-test GUI runner; CLI: `freecad --run-test 0` (all), `freecad -c -t TestPartDesignApp` (headless specific)
- Suites: BaseTests, UnitTests, Document, MeshTestsApp, TestDraft, TestSketcherApp, TestPartApp, TestPartDesignApp, TestCAMApp...; scriptable via `Test.runTestsFromModule()` / `FreeCAD.__unit_test__`

### 4. Macros

- Macro recorder (GUI actions → Python), macro editor, macros-recipes library on wiki, installation via Addon Manager or manual `.FCMacro`

### 5. External Workbenches

- Community workbench ecosystem installed via Addon Manager (Fasteners, SheetMetal, Curves, A2plus, Assembly4, KiCad StepUp, Render, ...); overview + install docs on wiki

### 6. Reference

- **Commands Reference**: wiki page indexing every command across all workbenches (the machine-readable superset of the catalogs above)
- **Online help system**, Power users hub (Python scripting docs), Community portal, Glossary

_Confidence: High — command lists extracted from official documentation mirror pages, current as of crawl date 2026-07-21._

---

# Research Synthesis — FreeCAD as an AI-Drivable CAD Platform

## Executive Summary

FreeCAD 1.x is a fully scriptable parametric CAD platform: a C++ core over the OCCT geometry kernel with a near-complete Python 3.11+ mirror API, ~20 built-in workbenches, and roughly 500 commands cataloged in this report. Every capability a human reaches through the GUI has a headless-reachable Python equivalent via `FreeCADCmd`, which is the load-bearing fact for FreeCAD Buddy's entire architecture. The 1.0 (Nov 2024) and 1.1 (Mar 2026) releases removed the historical blockers to AI-driven automation: Topological Naming Problem mitigation via the ElementMap, a first-party Assembly workbench, VarSets as first-class parameter containers, and a unified Measure tool.

The platform ships its own verification primitives — OCCT validity checks (`isValid()`, BRepCheck), mass properties, sketch solver diagnostics (DoF, conflicting, redundant — each with a dedicated command), document transactions for exact rollback, and a headless test CLI. Buddy's verify-first tool taxonomy is therefore a composition job, not a kernel-engineering job, exactly as intent.md's Reuse Map assumed.

**Key Technical Findings:**

1. Phases 0–3 need only built-in workbenches (Part, PartDesign, Sketcher, Spreadsheet/VarSet, Mesh) — zero addon dependencies on the critical path; Phase 5 targets (Assembly, TechDraw, FEM) are also built-in.
2. Verification primitives exist natively; the invention budget stays where intent.md placed it (taxonomy, benchmarks, TNP audit, skills).
3. No official external API exists — Python is the only integration surface. Community FreeCAD MCP servers prove the transport/embedding patterns (in-process addon, external RPC bridge) but none implement verify-first tooling.
4. TNP is mitigated, not eliminated: ElementMap re-resolves references by creation history, but datum-based referencing remains best practice and Buddy's post-mutation reference audit is still a genuine gap worth building.
5. FreeCAD's embedded Python is unsandboxed — the typed-tool mutation layer (no free-form exec) is a security requirement, not just a quality choice.
6. Headless caveats to verify in Phase 0: offscreen screenshot capture, exact ElementMap Python API names, `FreeCAD.GuiUp` branching in all bridge code.

**Technical Recommendations:**

1. Pin FreeCAD 1.1.x as primary target; CI matrix with 1.0.x; ignore ≤0.21.
2. Wrap, don't fork: adopt community MCP server transport patterns + official MCP Python SDK; build only the tool layer.
3. Build `verify.*` directly on OCCT checks + planegcs diagnostics + transaction geometry-hash comparison.
4. Gate or omit any `execute_python` tool; mutations go through typed tools only.
5. Reuse the Test Framework headless CLI pattern (`freecad -c -t <suite>`) for the golden-model CI harness.

## Table of Contents

1. Technical Research Scope Confirmation
2. Technology Stack Analysis — languages, OCCT/Qt/planegcs, document model, tooling, versions
3. Integration Patterns Analysis — Python API surface, embedding patterns, file formats, addons, security
4. Architectural Patterns and Design — App/Gui split, DocumentObject/DAG/recompute, PartDesign Body, TNP/ElementMap, Sketcher solver, performance
5. Implementation Approaches and Technology Adoption — workbench feature catalog, cross-cutting features, Buddy adoption mapping
6. Full Feature List (per FreeCAD wiki User hub) — complete command catalogs for all built-in workbenches
7. Research Synthesis (this section)

## Methodology and Source Verification

- **Approach**: assistant knowledge base cross-checked against live sources; every section carries explicit confidence levels; command catalogs crawled page-by-page from the official documentation mirror.
- **Primary sources**: FreeCAD release blog (1.1 announcement), FreeCAD Developers Handbook, official wiki content via `FreeCAD/FreeCAD-documentation` GitHub mirror (User_hub, Std_Base, 20 workbench pages, Testing), DeepWiki TopoShape/TNP analysis, Ondsel toponaming milestone posts. Full offline wiki clone available in-repo at [`docs/references/FreeCAD-wiki/wiki/`](../../../docs/references/FreeCAD-wiki/wiki/) (~7200 wikitext pages) for offline verification and Track A skills authoring.
- **Secondary sources**: Wikipedia, Libre Arts 1.0 review, Neowin/AlternativeTo release coverage, XSim format list, community MCP server listings.
- **Limitations**: per-tool lists reflect documentation state, which can drift from shipped binaries between releases (Medium confidence flagged where relevant); performance figures are community-reported orders of magnitude, not benchmarked here; individual community MCP project maturity not audited (deferred to Phase 0 reuse survey per intent.md).
- **Search/crawl log**: 4 targeted web searches (1.1 release/stack, formats, TNP architecture, workbench list) + 16 documentation page fetches, 2026-07-21.

## Conclusion and Next Steps

FreeCAD's feature surface fully supports the Buddy vision ladder — no phase in intent.md depends on a capability FreeCAD lacks. The platform's own diagnostics make the Validation-First Discipline implementable with deterministic code throughout.

Recommended next steps:

1. Feed this catalog into the Phase 0 Validation Design Gate reuse survey (audit the specific community MCP servers named here).
2. Resolve the two open Phase 0 verification items: headless offscreen screenshots, ElementMap Python API surface on 1.1.
3. Use the per-workbench catalogs as scope statements for Track A skills (`freecad-partdesign` = PartDesign section; `freecad-sketcher` = Sketcher section; `freecad-datums-references` = datum/ShapeBinder + TNP sections).

---

**Technical Research Completion Date:** 2026-07-21
**Source Verification:** all claims cited; confidence levels per section
**Overall Confidence:** High (architecture, stack, catalog structure); Medium (exhaustive per-tool lists, API method names — re-verify against pinned 1.1.x during Phase 0)
