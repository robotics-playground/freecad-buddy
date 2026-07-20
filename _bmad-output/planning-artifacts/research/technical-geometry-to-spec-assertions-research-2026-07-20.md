---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - docs/intent.md
  - docs/references/FreeCAD/src/Mod/Part/App
  - docs/references/FreeCAD/src/Mod/Measure/App
  - docs/references/FreeCAD/src/Mod/PartDesign/App
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'Geometry-to-spec assertion strategy: verifying hole positions, diameters, and dimensions from FreeCAD B-rep'
research_goals: "docs/intent.md Phase 3 needs machine-checkable spec assertions verified on the final artifact (not the process): e.g. 'two M5 through-holes 40 mm apart'. Research measurement strategies from the resulting shape (cylindrical-face detection + axis extraction from B-rep via FreeCAD Python, Hole feature metadata, datum-anchored measurement, bbox/volume/section checks), robustness across modeling approaches, and prior art in geometric assertion/metrology; recommend an assertion-primitive vocabulary for the benchmark harness."
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Geometry-to-Spec Assertions from FreeCAD B-Rep: Comprehensive Technical Research

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** technical

---

## Research Overview

FreeCAD Buddy's Phase 3 ("Designer") is judged by a rule the whole project is built on: *success is measured on the final artifact, not the process.* A part is correct not because "the plan executed" but because the resulting solid actually satisfies the spec — "two M5 through-holes 40 mm apart", "a 60x40x5 mm base plate", "a 30 mm flange". This research answers how to *measure* those properties from the B-rep FreeCAD produces, robustly across the different ways an agent might model the same feature (Hole feature vs. pocket vs. boolean cut), and how to turn those measurements into a small, machine-checkable **assertion-primitive vocabulary** for the benchmark harness.

The central finding is that FreeCAD already exposes everything needed through its Python API, and the exact code path is proven by the shipped `Measure` workbench: every cylindrical hole wall becomes a `Part.Cylinder` surface via OpenCASCADE's `BRepAdaptor_Surface`, carrying `.Radius`, `.Center`, and `.Axis` directly. Diameters, axes, and hole positions are therefore first-class, artifact-level measurements — no golden mesh, no feature-tree trust required. This is the decisive difference from mainstream text-to-CAD benchmarks (Text2CAD-Bench, CadBench), which score whole-shape similarity (Chamfer distance, volumetric IoU) against a reference model and cannot express "an M5 hole here". The recommended strategy — a **geometry-first, feature-tree-as-hint, datum-anchored** assertion layer built on `BRepAdaptor`-backed surface typing plus bounding-box/volume/section sanity checks — is independently validated by the newest prior art (CADSmith's OCCT-kernel Validator, MUSE's geometric-check stage). See the Executive Summary and Section 8 for the full recommendation and the proposed assertion vocabulary.

Full methodology, primary-source citations into the local FreeCAD tree, and prior-art comparison follow in the Research Synthesis below.

---

## Technical Research Scope Confirmation

**Research Topic:** Geometry-to-spec assertion strategy: verifying hole positions, diameters, and dimensions from FreeCAD B-rep
**Research Goals:** Machine-checkable spec assertions for Phase 3, measured on the artifact; strategies to extract properties from the resulting shape; robustness across modeling approaches; prior art; a recommended assertion-primitive vocabulary.

**Technical Research Scope:**

- Architecture Analysis — how B-rep property extraction is layered in FreeCAD/OCCT and how an assertion harness sits on top
- Implementation Approaches — the concrete Python API surface (Part, Measure, PartDesign) for detecting cylindrical faces, extracting axes/radii, measuring distances, and reading feature metadata
- Technology Stack — FreeCAD Python API, OpenCASCADE (OCCT) geometry adaptors, the Measure module, PartDesign Hole feature
- Integration Patterns — how `verify.*` tools in the bridge consume these primitives; datum-anchored measurement; TNP-robust sub-shape resolution
- Performance Considerations — robustness across modeling approaches, tolerance handling, false-alarm control

**Scope Confirmed:** 2026-07-20

---

# Verifying Design Intent in the Solid: A Geometry-to-Spec Assertion Strategy for FreeCAD Buddy

## Executive Summary

Phase 3 of FreeCAD Buddy asks an agent to turn a written spec into a parametric part and then *prove* the part meets the spec — with pass/fail decided by deterministic code, never by the agent's own opinion (Validation-First Discipline, `docs/intent.md` §"Principles", items 1 and 6). The hard question this research resolves is: **given only the final solid, how do you machine-check statements like "two M5 through-holes 40 mm apart"?**

The answer is that FreeCAD's Python API, sitting on the OpenCASCADE (OCCT) kernel, already exposes hole geometry as directly-measurable primitives, and the shipped `Measure` workbench is a working reference implementation of exactly the extraction logic the harness needs. A cylindrical hole wall, however it was modeled, is a `TopoShapeFace` whose `.Surface` is a `Part.Cylinder` object carrying `.Radius`, `.Center`, and `.Axis` (verified in `src/Mod/Part/App/Cylinder.pyi` and in the OCCT extraction path `MeasureClient.cpp:335-339`). Diameter = `2 x Radius`; hole axis = the cylinder `.Axis`; hole position = a point on the axis (`.Center`) projected to the datum face; hole-to-hole spacing = distance between the two axes. All of these are **artifact-level** measurements independent of *how* the hole was created — the decisive robustness property, because an agent may legitimately produce a hole via the PartDesign `Hole` feature, a `Pocket` from a circular sketch, or a boolean `cut` with a cylinder, and the assertion layer must not care which.

This geometry-first approach is strongly corroborated by the current external prior art. Mainstream text-to-CAD benchmarks (Text2CAD-Bench, CadBench, BenchCAD) score *whole-shape similarity* — Chamfer distance and volumetric IoU against a ground-truth mesh — which is the wrong tool for FreeCAD Buddy: it needs a reference solid the project does not have, and it cannot express a per-feature requirement like "M5 hole, here, this deep". The 2026 systems that do match the need — **CADSmith** (OCCT-kernel Validator: exact bounding box, volume, solid validity + an independent VLM judge) and **MUSE** (three-stage code-check / geometric-check / design-intent protocol) — independently arrive at the same architecture this research recommends: a deterministic OCCT-measurement layer as the source of truth, kept strictly separate from the acting agent.

**Key Technical Findings:**

- **Hole geometry is directly measurable from the B-rep.** `Face.Surface` returns a typed `Part.Cylinder`/`Cone`/`Plane`/`Sphere`/`Torus` (via OCCT `BRepAdaptor_Surface::GetType()`), exposing radius, axis, and center as attributes. This is the load-bearing primitive for hole diameter, axis, and position. (`Cylinder.pyi:44-51`, `GeometrySurface.pyi`, `MeasureClient.cpp:335-339`, `Geometry.cpp:7040-7056`.)
- **The `Measure` workbench is a shipped reference implementation.** `Measurement` (`Measurement.pyi`) offers `radius()`, `angle()`, `length()`, `delta()`, `com()` over selected sub-elements; `MeasureDiameter` literally computes `radius x 2.0` (`MeasureDiameter.cpp:115`). The harness can reuse this logic rather than reinventing it.
- **Modeling-approach robustness comes from measuring geometry, not reading the tree.** A hole made by `Hole`, `Pocket`, or boolean all yield a cylindrical face with the same measurable radius/axis. Feature-tree metadata (`PartDesign::Hole` properties: `Diameter`, `Depth`, `DepthType`, `ThreadSize`, etc. in `FeatureHole.h:53-80`) is a *hint / cross-check*, never the primary check — reading it would validate intent, not the artifact.
- **Datum-anchored measurement defeats the Topological Naming Problem for assertions.** Sub-element indices (`Face7`, `Edge3`) are unstable across recompute; but assertions expressed against *datums and geometric queries* ("count cylindrical faces of radius 2.5 mm whose axis is perpendicular to the base datum") are stable. `Shape.getElement()` also accepts TNP-mitigation mapped names (`TopoShape.pyi:1035-1043`).
- **Bounding box, volume, and section are the cheap sanity layer.** `Shape.BoundBox` (X/Y/Z lengths, center — `BoundBox.pyi`), `Shape.Volume`, and `Shape.section()`/`common()`/`cut()` (`TopoShape.pyi`) give order-of-magnitude and overall-dimension checks that catch gross failures before the precise feature checks run.

**Technical Recommendations:**

1. **Adopt a geometry-first assertion layer.** Extract features by typing faces through `Face.Surface` (OCCT `BRepAdaptor`), not by parsing the feature tree. Make the assertion vocabulary operate on measured geometry.
2. **Wrap, don't fork, the `Measure` logic.** Build the harness's radius/axis/distance/angle primitives on the same `BRepAdaptor_Surface` + `gp_Circ`/`gp_Cylinder` path the `Measure` module already uses (Reuse Map: "Geometry validity checks — never reinvent").
3. **Ship a fixed assertion-primitive vocabulary** (Section 8): `expect_bbox`, `expect_volume`, `count_cylindrical_holes`, `hole_diameter`, `hole_axis`, `hole_through`, `hole_spacing`, `distance_between`, `angle_between`, `is_valid_solid`, plus a datum/frame anchor. Every Phase 3 spec compiles to a set of these.
4. **Keep the actor out of grading.** The assertion layer runs as an independent `verify.*` tool; the designing agent never computes its own pass/fail — matching `docs/intent.md` Principle 1 and CADSmith's Validator/Refiner separation.
5. **Validate the validator by fault injection.** Feed planted-wrong parts (missing hole, wrong diameter, mirrored hole pattern, slightly-off spacing) through the assertion layer; require >= 95% sensitivity and <= 5% false-alarm, per intent.md §"Principles" item 3 — the tolerance defaults chosen in Section 6 exist to hit exactly this.

## Table of Contents

1. Technical Research Introduction and Methodology
2. B-Rep Property Extraction — Technical Landscape and Architecture Analysis
3. Implementation Approaches: Measuring Holes and Dimensions from FreeCAD Python
4. Technology Stack: FreeCAD Part / Measure / PartDesign APIs and OCCT Adaptors
5. Integration and Interoperability: Datum-Anchored, TNP-Robust Assertions
6. Robustness, Tolerance, and Performance Analysis
7. Prior Art: CAD Metrology and Text-to-CAD Benchmark Evaluation
8. Strategic Recommendation: The Assertion-Primitive Vocabulary
9. Implementation Roadmap and Risk Assessment
10. Future Technical Outlook
11. Research Methodology and Source Verification
12. Appendices and Reference Materials

---

## 1. Technical Research Introduction and Methodology

### Technical Research Significance

Every phase of FreeCAD Buddy stands on one belief: an LLM agent will systematically over-grade its own work, so the artifact must be measured, not trusted (`docs/intent.md` §"Validation-First Discipline"). For Phases 0-2 the measurements are relatively coarse — is the shape a valid watertight solid, did it recompute, is the sketch fully constrained. Phase 3 is where the measurement problem gets *semantic*: the spec talks about **features and their relationships** ("two M5 through-holes 40 mm apart"), and the harness must decide whether the produced solid actually contains those features, at those sizes, in those places. If that assertion layer is weak, Phase 3's headline metric (">= 70% of 20 specs produce a passing part") is meaningless — the agent will pass by producing plausible-looking wrong parts, exactly the Phase 3 self-deception mode intent.md already names ("measures what it built instead of what was asked").

_Technical Importance: The assertion layer is the objective definition of "done" for the first true design capability; it is explicitly listed as a genuine invention in the Reuse Map ("machine-checkable spec-assertion benchmarks")._
_Business Impact: Without it, Phase 3 cannot exit its Validation Design Gate, and validation-first discipline collapses for every phase above it (Phase 4 reuses these exact checks headlessly)._

### Technical Research Methodology

- **Technical Scope:** B-rep geometry extraction (faces, surfaces, edges, adaptors), the FreeCAD Measure module, PartDesign Hole metadata, bounding-box/volume/section queries, datum-anchored measurement, and prior-art benchmark evaluation methods.
- **Data Sources (priority order):** (1) The local FreeCAD source tree at `docs/references/FreeCAD` — cited by exact file and line/class. (2) Web search for OCCT adaptor semantics and 2024-2026 text-to-CAD benchmark evaluation prior art.
- **Analysis Framework:** For each spec property class (diameter, axis, position, spacing, overall dimension, count), trace the exact Python/OCCT path that measures it, confirm it is artifact-level (modeling-approach independent), and fold it into a primitive.
- **Time Period:** Current — FreeCAD 1.x source tree (the `getElement` TNP-mapped-name support and the standalone `Measure` module confirm a 1.x-era tree); prior art from 2024-2026.
- **Technical Depth:** Implementation-level — down to specific `.pyi` attributes and OCCT `BRepAdaptor` calls the harness will invoke.

### Technical Research Goals and Objectives

**Original Technical Goals:** (see frontmatter `research_goals`)

**Achieved Technical Objectives:**

- Confirmed, from primary FreeCAD source, that hole diameter/axis/position are directly extractable from the B-rep via `Face.Surface` -> `Part.Cylinder` (`.Radius`/`.Center`/`.Axis`), with the shipped `Measure` module as reference implementation.
- Established modeling-approach robustness: the measurement is identical whether the hole came from `Hole`, `Pocket`, or boolean `cut`.
- Mapped the full supporting query surface (BoundBox, Volume, Area, section/common/cut, distToShape, countElement) for dimension and count assertions.
- Surveyed prior art and found FreeCAD Buddy's need aligns with property-level validators (CADSmith, MUSE), not whole-shape-similarity benchmarks (Text2CAD-Bench, CadBench) — with a concrete recommendation to not adopt Chamfer/IoU as the primary Phase 3 metric.
- Produced a concrete, fixed assertion-primitive vocabulary (Section 8).

## 2. B-Rep Property Extraction — Technical Landscape and Architecture Analysis

### The layered architecture

FreeCAD's geometry stack has three layers relevant here, and the assertion harness sits above all of them:

```
Spec assertion harness (verify.* tools)   <-- FreeCAD Buddy invents this
        |  calls
FreeCAD Python API (Part, Measure, PartDesign)
   TopoShape / TopoShapeFace / Part.Cylinder / Measurement
        |  wraps
OpenCASCADE (OCCT) kernel
   TopoDS_Shape, BRepAdaptor_Surface/Curve, gp_Cylinder/gp_Circ, GProp
```

The critical architectural fact: **the topology (which faces/edges exist) and the geometry (what surface underlies each face) are separable, and the geometry is typed.** OCCT's `BRepAdaptor_Surface::GetType()` returns an enum (`GeomAbs_Plane`, `GeomAbs_Cylinder`, `GeomAbs_Cone`, `GeomAbs_Sphere`, `GeomAbs_Torus`, `GeomAbs_BSplineSurface`, ...). FreeCAD surfaces this both as the concrete Python class of `Face.Surface` and inside the Measure module's element classifier (`MeasureClient.cpp:190-229`, which switches on exactly these enum values to classify a face as CYLINDER / TORUS / SPHERE / PLANE / DISC).

This is what makes "detect the holes" a solved kernel problem rather than a mesh-analysis heuristic: a through-hole's wall is a cylindrical face; you find holes by finding cylindrical faces and filtering by radius/axis.

_Dominant Pattern: adaptor-based surface typing — iterate faces, adapt each to its geometric surface, switch on surface type, read the geometric parameters._
_Architectural Trade-off: surface typing sees only the local face geometry, so a "hole" and a "boss" (external cylinder) are both cylindrical faces; disambiguation needs orientation/normal or a solid-inside test (Section 6)._
_Source: `docs/references/FreeCAD/src/Mod/Part/App/MeasureClient.cpp` (140-229, 288-390); OCCT `BRepAdaptor_Surface`._

### System design principles

- **Measure geometry, treat topology indices as volatile.** Face/edge *indices* are TNP-unstable; the *geometry* (a cylinder of radius r with axis a) is stable. Assertions phrased over geometry survive recompute.
- **Reuse the kernel's own measurement path.** The Measure module already implements radius/diameter/distance/angle over sub-elements; the harness composes these rather than re-deriving OCCT math (Reuse Map: geometry checks are "never" reinvented).

## 3. Implementation Approaches: Measuring Holes and Dimensions from FreeCAD Python

This section gives the concrete Python-level recipes, each grounded in a cited API.

### 3.1 Detect cylindrical holes and extract diameter + axis

Every solid exposes `.Faces`; each face exposes `.Surface`. When the surface is cylindrical it is a `Part.Cylinder` with `.Radius`, `.Center`, `.Axis` (`Cylinder.pyi:44-51`). The OCCT path that populates these is `MeasureClient.cpp:335-339`:

```
BRepAdaptor_Surface surf(face);
if (surf.GetType() == GeomAbs_Cylinder) {
    pointOnCurve = surf.Cylinder().Location();   // -> Part.Cylinder.Center
    radius       = surf.Cylinder().Radius();     // -> Part.Cylinder.Radius
}
```

Harness recipe (conceptual):

```python
def cylindrical_faces(shape):
    for f in shape.Faces:
        s = f.Surface
        if s.TypeId == 'Part::GeomCylinder':      # or: isinstance-style check
            yield f, s.Radius, s.Center, s.Axis
```

Diameter is `2 * Radius` — this is exactly what the shipped `MeasureDiameter` does: `Diameter.setValue(info->radius * 2.0);` (`MeasureDiameter.cpp:115`). So "the M5 tap-drill hole is 4.2 mm" becomes `abs(2*Radius - 4.2) <= tol`.

The hole **axis** is `Part.Cylinder.Axis` (a direction `Vector`); the axis **line** passes through `.Center`. For a circular hole, the bounding circular edges are also available: a planar face bounded by a single circular edge is classified DISC and its `BRepAdaptor_Curve.Circle()` yields center + radius (`MeasureClient.cpp:355-373`), a useful cross-check for the hole opening.

### 3.2 Hole position and hole-to-hole spacing

Hole *position* is the axis line intersected with (or projected onto) the reference datum face. Two robust options:

- **Project the cylinder `.Center` onto the base datum plane** using `GeometrySurface.projectPoint(...)` (`GeometrySurface.pyi:87-118`) or simple vector projection against the datum's normal/origin. This gives the (x, y) hole location in the datum frame.
- **Section the solid with the datum plane** (`Shape.section(...)`, `TopoShape.pyi:314`) and read the resulting circle centers.

Hole *spacing* ("40 mm apart") is the distance between the two hole axes. For parallel axes this is the distance between axis lines; practically, project both centers to the common datum and take the 2D distance, or use `Shape.distToShape` (`TopoShape.pyi:1005-1032`, returns min distance + witness points + element info) between the two cylindrical faces / their axis edges. The Measure module exposes `Measurement.delta()` and `lineLineDistance()` for the same purpose (`Measurement.pyi:35,51`).

### 3.3 Through vs. blind

"Through-hole" is checkable geometrically: the hole axis segment enters and exits the solid — i.e. the cylindrical face's axial extent spans the material thickness, or a ray along `.Axis` from the datum face intersects both the entry face and the opposite face. Cheap proxy: the cylinder face's parametric V-range (axial length) equals the local wall thickness (from BoundBox or opposing-datum distance). The `Face.ParameterRange` (`TopoShapeFace.pyi:37`) and `Surface.bounds()` (`GeometrySurface.pyi:149-154`) give the parametric extent; `section()` at both faces confirms the hole is open on both sides.

### 3.4 Overall dimensions (base plate 60x40x5)

`Shape.BoundBox` returns a `BoundBox` with `XLength`/`YLength`/`ZLength`, `Center`, and min/max per axis (`BoundBox.pyi:40-95`). For an axis-aligned plate this directly checks "60 x 40 x 5" within tolerance. For non-axis-aligned parts, align to the part's datum frame first (measure in the local coordinate system), or use oriented measurements via section/edge lengths. `Shape.Volume` and `Shape.Area` (`TopoShape.pyi:60-66`) give order-of-magnitude sanity ("volume within a factor of the expected 60*40*5 minus holes").

### 3.5 Angle / perpendicularity of a flange

"One perpendicular flange 30 mm tall" -> the flange's principal face normal is perpendicular to the base datum normal. `Measurement.angle()` (`Measurement.pyi:59`) measures angle between two edges/faces; or take the two face normals (`TopoShapeFace.normalAt`, `TopoShapeFace.pyi:162`) and assert their dot product ~ 0. Flange height is a BoundBox extent in the flange's local up-direction.

### 3.6 Counting features

`Shape.countElement("Face")` (`TopoShape.pyi:1045`) plus the cylindrical-face filter gives "number of holes of radius r". This is how "two M5 holes" is asserted: `count of cylindrical faces with Radius ~ 2.5 and axis perpendicular to base == 2`.

## 4. Technology Stack: FreeCAD Part / Measure / PartDesign APIs and OCCT Adaptors

### 4.1 Part module — the geometric substrate (primary)

| API surface | What it provides for assertions | Cited source |
|---|---|---|
| `TopoShape.Faces / .Edges / .Vertexes` | iterate B-rep sub-shapes | `TopoShape.pyi` |
| `TopoShapeFace.Surface` | typed geometric surface of a face | `TopoShapeFace.pyi:40` |
| `Part.Cylinder.Radius / .Center / .Axis` | hole radius, a point on axis, axis direction | `Cylinder.pyi:44-51` |
| `Part.Cone / .Sphere / .Plane / .Toroid` | countersink/fillet/ball/flat/torus faces | `Geometry.cpp:7040-7078` |
| `GeometrySurface.projectPoint / .normal / .bounds / .isPlanar` | project hole center to datum, face extent, planarity | `GeometrySurface.pyi:87-162` |
| `TopoShapeFace.normalAt / .valueAt / .ParameterRange` | face normal (perpendicularity), axial extent | `TopoShapeFace.pyi:37,155,162` |
| `TopoShape.BoundBox` | overall dimensions, center | `TopoShape.pyi:1188`, `BoundBox.pyi` |
| `TopoShape.Volume / .Area / .Length` | magnitude sanity checks | `TopoShape.pyi:60-66` |
| `TopoShape.section / .common / .cut` | slice with datum plane, boolean probes | `TopoShape.pyi:297,314,351` |
| `TopoShape.distToShape` | min distance + witness elements (spacing, edge distance) | `TopoShape.pyi:1005` |
| `TopoShape.isValid / .check` | valid watertight solid gate | `TopoShape.pyi:235,779` |
| `TopoShape.getElement(name, silent)` | resolve sub-element, accepts TNP-mapped names | `TopoShape.pyi:1035` |
| `TopoShape.countElement(type)` | feature counts | `TopoShape.pyi:1045` |

### 4.2 Measure module — a shipped reference implementation (reuse target)

The standalone `Measure` module (`src/Mod/Measure/App`) is the exact prior art *inside FreeCAD itself* for this problem, and should be wrapped rather than reinvented:

- `Measurement` Python class (`Measurement.pyi`): `addReference3D`, `radius()`, `angle()`, `length()`, `area()`, `volume()`, `delta()`, `lineLineDistance()`, `planePlaneDistance()`, `com()` (center of mass).
- `MeasureRadius` / `MeasureDiameter` (`MeasureRadius.cpp`, `MeasureDiameter.cpp:115` — literally `radius * 2.0`) — the diameter primitive.
- `MeasureClient.cpp` (`MeasureRadiusHandler`, 288-390; element classifier 140-229) — the OCCT `BRepAdaptor_Surface` + `gp_Cylinder`/`gp_Circ`/`gp_Torus`/`gp_Sphere` extraction that turns a selected face into (radius, point-on-axis, center-of-mass). This is the canonical code the harness mirrors.
- `MassPropertiesObject` / `MassPropertiesResult` — volume/COM/inertia as document objects.

### 4.3 PartDesign Hole feature — metadata as a *hint*, not a check

The `PartDesign::Hole` feature carries rich parametric metadata (`FeatureHole.h:53-80`): `Diameter`, `Depth`, `DepthType` (enum `{"Dimension","ThroughAll"}`, `FeatureHole.cpp:76`), `Threaded`, `ThreadType`, `ThreadSize`, `HoleCutType`, `HoleCutDiameter`, `HoleCutDepth`, `HoleCutCountersinkAngle`, `DrillPoint` (`{"Flat","Angled"}`), `Tapered`, `TaperedAngle`. `BaseProfileType` defaults to `OnCirclesArcs` (`FeatureHole.cpp:650`), i.e. the feature drills at each circle/arc in a sketch.

**Recommended posture:** read this metadata only as a *cross-check / diagnostic*, never as the pass/fail source. Reasons: (1) it exists only when the hole was made by the `Hole` feature — a `Pocket` or boolean hole has none, so relying on it breaks modeling-approach robustness; (2) reading declared parameters validates *intent*, not the *artifact* — it is exactly the "measure what it built" trap intent.md warns against for Phase 3. Metadata is useful to *explain* a failure ("declared M5 but the wall measures 4.9 mm -> feature vs. geometry mismatch") and to map thread designations (M5 -> nominal 5 mm) to expected measured geometry.

### 4.4 The OCCT layer

Underneath, all of the above is OCCT: `BRepAdaptor_Surface`/`BRepAdaptor_Curve` for typed geometry, `gp_Cylinder`/`gp_Circ`/`gp_Cone`/`gp_Sphere`/`gp_Torus` for parameters, `GProp_GProps` + `BRepGProp` for mass/length/area properties, `Bnd_Box`/`BRepBndLib` for bounding boxes. The harness never calls OCCT directly — it goes through the Python API — but knowing the mapping (Section 12 appendix) makes the tolerance and robustness behavior predictable.

## 5. Integration and Interoperability: Datum-Anchored, TNP-Robust Assertions

### 5.1 The datum-frame problem

"40 mm apart" and "hole at (10, 10)" are only meaningful in a reference frame. Two frames are candidates:

- **The part's local datum frame** (its base sketch plane / origin datum). Preferred: robust to the whole part being placed anywhere in the document, and it matches how the spec is authored ("relative to the base plate").
- **The document global frame.** Simpler but fragile — a placement change moves every absolute coordinate.

**Recommendation:** every assertion is evaluated in an explicit **anchor frame**, established from the part's base datum plane/axis (or, if absent, from the largest planar face taken as the reference datum). All hole centers, spacings, and bbox extents are transformed into that frame before comparison. This also makes assertions invariant to the agent's freedom in placing the body.

### 5.2 TNP robustness

The Topological Naming Problem means `Face7` may become `Face9` after a recompute. The assertion layer sidesteps this by **never naming sub-elements by index in specs**. Instead:

- Specs describe features by *geometry and relationship* ("a cylindrical hole of radius 2.5 perpendicular to base"), resolved by a live query at assert-time.
- Where a stable handle is genuinely needed, `Shape.getElement(name, silent=True)` accepts FreeCAD 1.x TNP-mitigation mapped names (`TopoShape.pyi:1035-1043`) and `getElementHistory` (`:1087`) traces provenance.
- This aligns with the project's TNP guard (intent.md Phase 2) and the `freecad-datums-references` skill.

### 5.3 verify.* tool integration

Each primitive becomes a deterministic `verify.*` tool in the bridge (intent.md Architecture: `verify.*` = "recompute checks, geometry assertions"). The Phase-3 self-repair loop calls these after each build; convergence is defined as *all assertions pass*, never "loop finished" (intent.md Phase 3 threat row). The acting agent receives the discrepancy vector (which assertion failed, measured vs. expected) as diagnostic input, exactly the CADSmith Refiner pattern (Section 7) — but the pass/fail verdict is the tool's, not the agent's.

## 6. Robustness, Tolerance, and Performance Analysis

### 6.1 Modeling-approach robustness (the core requirement)

| Property | Hole feature | Pocket from circular sketch | Boolean cut with cylinder | Measurable identically? |
|---|---|---|---|---|
| Cylindrical wall face exists | yes | yes | yes | **yes** — `Face.Surface` is `Part.Cylinder` in all three |
| Radius / diameter | yes | yes | yes | **yes** (`.Radius`) |
| Axis direction & point | yes | yes | yes | **yes** (`.Axis`, `.Center`) |
| Feature metadata (`Diameter`, `DepthType`) | yes | no | no | no — metadata is approach-specific (hence hint-only) |

Conclusion: an assertion layer built on `Face.Surface` geometry is invariant to modeling approach; one built on feature-tree reading is not. This is the single most important design decision.

### 6.2 Disambiguation hazards and their mitigations

- **Hole wall vs. external boss.** Both are cylindrical faces. Mitigate by testing face orientation / inward normal (a hole's wall normal points toward the axis, i.e. into void; a boss points outward), or by an inside-solid test on a point offset from the wall toward the axis. `Face.normalAt` + solid membership.
- **Fillets and rounds are cylindrical too.** A rounded edge is a cylindrical (or toroidal) face of small radius. Filter by expected radius band and by whether the face is bounded by full 360-deg (through-hole) vs. partial arcs (fillet). Count only faces whose bounding edges include full circles.
- **Split faces.** A hole through a stepped wall may be two coaxial cylindrical faces. Group cylindrical faces by shared axis (same `.Axis` direction and collinear `.Center`) before counting/measuring — merge coaxial faces into one logical hole.
- **Countersinks / counterbores** appear as a cylinder + cone (or cylinder + larger cylinder) sharing an axis (`Part.Cone` from `Geometry.cpp:7058`). Recognize the compound and check the cut diameter/angle against `HoleCut*` expectations.

### 6.3 Tolerance strategy (drives sensitivity vs. false-alarm)

- **Dimensional tolerance:** default absolute band (e.g. +/-0.05 mm) plus a relative band for large dimensions; expose per-assertion override. OCCT modeling introduces sub-micron noise, so exact equality is never used.
- **Angular tolerance:** e.g. +/-0.1 deg for perpendicularity via normal dot-product.
- **Shape tolerance awareness:** `Shape.getTolerance(mode, ShapeType)` (`TopoShape.pyi:1099`) reports the actual B-rep tolerance; assertions should not be tighter than the geometry's own tolerance.
- **Fault-injection calibration:** intent.md mandates >= 95% sensitivity / <= 5% false-alarm. The default bands are chosen so a planted 0.5 mm spacing error or a wrong tap-drill diameter is caught, while legitimate kernel noise is not flagged. These numbers are *tuned against the fault suite*, not guessed.

### 6.4 Performance

Face iteration + surface adaptor typing is O(number of faces) and microseconds-per-face; a Phase-3 part (tens to low-hundreds of faces) is measured in milliseconds. `section`/`distToShape`/BOP-based probes are heavier (tens of ms) but used sparingly (through-hole confirmation, spacing witness). Well within intent.md's <= 10 min/part Phase-3 budget; the assertion pass is negligible next to the LLM planning/execution time.

## 7. Prior Art: CAD Metrology and Text-to-CAD Benchmark Evaluation

### 7.1 The whole-shape-similarity mainstream (and why it is the wrong primary tool here)

The dominant 2024-2026 text-to-CAD benchmarks evaluate generation by comparing the produced solid to a **ground-truth mesh/solid**:

- **Text2CAD-Bench** uses Chamfer Distance (bidirectional point-cloud NN distance), Invalidity Rate (fraction of code that fails to produce valid geometry), and volumetric IoU (voxelized at 256^3). Target representation is CadQuery.
- **CadBench** defines a suite of volumetric IoU, surface IoU, Chamfer distance, valid-shape rate, token count, operation count; evaluated across ~1.4M generations, finding accuracy degrades with geometric complexity.
- **BenchCAD** frames tasks (Vision2Code, Edit Code, Code QA, Vision QA) but still leans on program-vs-reference comparison.

**Assessment for FreeCAD Buddy:** these metrics require a golden solid the project deliberately does not commit to (specs, not reference models, are the source of truth — Reuse Map: "the specs with machine-checkable acceptance criteria mostly don't exist and are our invention"). Worse, Chamfer/IoU are *holistic*: they cannot express "the M5 hole is 2 mm off" — a small but functionally fatal error barely moves a whole-shape metric. **Recommendation: do not adopt Chamfer/IoU as the Phase-3 pass/fail metric.** They are usable only as an *optional secondary* signal if a reference model happens to exist, and as regression telemetry.

### 7.2 The property-level / programmatic-validation prior art (the right match)

- **CADSmith (2026)** is the closest architectural precedent: a multi-agent pipeline whose **Validator combines exact OpenCASCADE-kernel measurements (bounding-box dimensions, volume, solid validity) with an independent vision-language-model judge**, and a Refiner that receives the exact geometric discrepancies. This is precisely the recommended FreeCAD Buddy architecture — deterministic OCCT measurement as truth, actor kept out of grading, discrepancy fed back for repair. It validates both the *geometry-first* choice and the *actor-never-grades-itself* discipline.
- **MUSE (2026)** evaluates via a three-stage protocol — **code check -> geometric check -> design-intent alignment** (with design-specific rubrics for functionality/manufacturability/assemblability). The middle "geometric check" stage is the analog of this research's assertion layer; the staged structure mirrors intent.md's "valid solid -> assertions pass -> (human audit)".
- **CADReview (2025)** automatically reviews CAD programs with error detection and correction — supporting the general viability of programmatic CAD verification.
- **CadBench's** "attribute accuracy / spatial-relation accuracy / instruction-following accuracy" decomposition is a useful *vocabulary influence*: FreeCAD Buddy's assertions are essentially attribute checks (diameter) + spatial-relation checks (spacing, perpendicularity) + presence/count checks.

### 7.3 Classical metrology framing

The classical CAD/GD&T world names exactly these operations: **datum reference frame** establishment (US Patent 6,922,690 "creating a datum reference frame"), feature-of-size measurement, and position tolerancing. FreeCAD Buddy's assertion layer is, in effect, a lightweight programmatic **GD&T-style metrology harness**: features (holes) as features-of-size (diameter), located relative to a datum reference frame (spacing/position). Framing the vocabulary in these terms keeps it principled and extensible toward true position tolerance later.

_Source: see Section 11 for URLs._

## 8. Strategic Recommendation: The Assertion-Primitive Vocabulary

Every Phase-3 spec compiles into a set of primitives from this fixed vocabulary. Each primitive is a deterministic `verify.*` call returning `(pass: bool, measured, expected, tolerance, detail)`. The vocabulary is deliberately small, geometry-first, and datum-anchored.

### 8.1 Frame / anchor

- `anchor_frame(datum)` — establish the reference frame from a named datum plane/axis, or auto-derive from the base/largest planar face. All subsequent primitives evaluate in this frame.

### 8.2 Presence & count

- `is_valid_solid()` -> `Shape.isValid()` + watertight/solid check (gate; reuses Phase-0 `verify.shape`).
- `count_cylindrical_holes(radius, axis_dir=perp_to(base), tol)` -> filter `Face.Surface` cylinders, group coaxial, disambiguate hole-vs-boss, count.
- `count_faces(type)` / `count_edges()` -> `countElement`.

### 8.3 Feature-of-size (attribute) assertions

- `hole_diameter(selector, expected, tol)` -> `2 * Part.Cylinder.Radius` (mirrors `MeasureDiameter`).
- `hole_thread(selector, designation)` -> map M5 -> nominal geometry; measured wall vs. tap-drill / nominal; metadata cross-check optional.
- `edge_radius(selector, expected, tol)` -> circular-edge / cylindrical-fillet radius.

### 8.4 Location & relation (spatial) assertions

- `hole_position(selector, expected_xy, tol)` -> project cylinder `.Center` axis into anchor frame.
- `hole_spacing(sel_a, sel_b, expected, tol)` -> axis-to-axis distance (`distToShape` / `Measurement.delta`).
- `distance_between(sel_a, sel_b, expected, tol)` -> general min-distance.
- `angle_between(sel_a, sel_b, expected, tol)` -> face-normal / edge angle (`Measurement.angle`).
- `is_perpendicular(sel, datum, tol)` / `is_parallel(...)` -> normal dot-product.
- `hole_through(selector)` -> axis exits both sides (section at entry+exit or axial-extent == thickness).

### 8.5 Overall-dimension & magnitude assertions

- `expect_bbox(x, y, z, tol, frame=anchor)` -> `Shape.BoundBox` extents in anchor frame.
- `expect_extent(direction, length, tol)` -> oriented dimension.
- `expect_volume(value, rel_tol)` / `expect_area(...)` -> magnitude sanity.

### 8.6 Example — the intent.md Phase-3 bracket spec compiles to:

```
"60x40x5 mm base plate, two M5 through-holes 40 mm apart,
 one perpendicular flange 30 mm tall with a 10 mm lightening slot"

is_valid_solid()
anchor_frame(base_datum)
expect_bbox(>=60, >=40, ...)                      # overall envelope incl. flange
count_cylindrical_holes(radius~2.5, axis=perp_to(base)) == 2
hole_diameter(each, expected=nominal_M5_or_tapdrill, tol)
hole_through(each)
hole_spacing(hole_a, hole_b, expected=40, tol=0.1)
is_perpendicular(flange_face, base_datum, tol=0.1deg)
expect_extent(flange_up, 30, tol)                 # flange height
count_slots / expect_volume(slot removed ~ 10mm feature)   # lightening slot
```

### 8.7 Why this vocabulary and not Chamfer/IoU

It is (a) reference-model-free (works from the spec alone), (b) modeling-approach-invariant (geometry, not tree), (c) per-feature-sensitive (catches a 2 mm hole shift that IoU misses), (d) reuses FreeCAD's own `Measure`/OCCT path (Reuse Map compliant), and (e) fault-injection-tunable to the mandated sensitivity/false-alarm targets. Chamfer/IoU remain available only as optional secondary regression signals when a golden model exists.

## 9. Implementation Roadmap and Risk Assessment

### Implementation phases (fits the Phase-3 Validation Design Gate, ~20% timebox)

1. **Wrap the geometry primitives** — thin Python over `Face.Surface` typing + `Measure`-equivalent radius/axis/distance/angle. Ship `is_valid_solid`, `count_cylindrical_holes`, `hole_diameter`, `hole_axis`, `hole_spacing`, `expect_bbox`, `expect_volume`. (Reuse `Measure` logic.)
2. **Anchor frame + datum resolution** — derive/accept the reference frame; transform all measurements into it.
3. **Disambiguation layer** — hole-vs-boss, coaxial grouping, fillet filtering, countersink recognition.
4. **Spec compiler** — map a structured spec (or an LLM-extracted structured form) to a primitive set; author the 20 Phase-3 specs with these assertions (dev + held-out split).
5. **Fault-injection suite** — >= 10 planted-failure parts per validator; measure sensitivity/false-alarm; tune tolerances until >= 95% / <= 5%.

### Risk assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Cylindrical-face ambiguity (hole vs boss vs fillet) | false pass/fail on hole count | orientation/inside-solid test, radius band, full-circle bounding-edge filter, coaxial grouping (Section 6.2) |
| Tolerance too tight/loose | false alarms or missed faults | fault-injection-calibrated bands; respect `getTolerance`; per-assertion override |
| TNP renames sub-elements between build and assert | selector resolves to wrong face | geometry-query selectors, not indices; `getElement` mapped names; anchor frame |
| Over-reliance on Hole metadata | breaks on pocket/boolean holes; validates intent not artifact | metadata is hint-only; primary check is measured geometry (Section 4.3) |
| Non-axis-aligned parts break naive BoundBox | wrong overall-dimension verdict | measure in anchor frame / oriented extents |
| Assertion layer authored by/with the agent | flattering metrics | independent `verify.*` tool; actor never grades (intent.md P1; CADSmith pattern) |

## 10. Future Technical Outlook

- **Near-term:** extend the vocabulary to true GD&T-style *position tolerance* (a hole's axis within a cylindrical tolerance zone relative to the datum frame) — the classical metrology framing (Section 7.3) makes this a natural extension.
- **Medium-term:** a VLM "judge" as an *independent secondary* channel (CADSmith-style) for spec aspects hard to reduce to geometry (e.g. "looks like a bracket") — kept advisory, never overriding deterministic assertions; matches intent.md Phase-5 "vision feedback".
- **Long-term:** reuse the same primitives for Phase-4 DFM checks (hole-edge distance, min wall thickness via `distToShape` / section) and for revision diffs (assert the geometry delta is confined to the requested change).

## 11. Research Methodology and Source Verification

### Primary sources (local FreeCAD tree, `docs/references/FreeCAD`)

- `src/Mod/Part/App/Cylinder.pyi` (44-51) — `Part.Cylinder.Radius/.Center/.Axis`.
- `src/Mod/Part/App/GeometrySurface.pyi` (36-162) — `toShape`, `projectPoint`, `normal`, `bounds`, `isPlanar`, `curvature`.
- `src/Mod/Part/App/TopoShapeFace.pyi` (37,40,49,155,162) — `Surface`, `ParameterRange`, `OuterWire`, `valueAt`, `normalAt`, `CenterOfMass`.
- `src/Mod/Part/App/TopoShape.pyi` (60-66,235,297,314,351,779,1005,1035,1045,1188) — `Volume/Area/Length`, `check`, `common/section/cut`, `isValid`, `distToShape`, `getElement`, `countElement`, `BoundBox`.
- `src/Mod/Part/App/MeasureClient.cpp` (140-229 element classifier; 288-390 `MeasureRadiusHandler` OCCT extraction) — the `BRepAdaptor_Surface`/`gp_Cylinder`/`gp_Circ` path.
- `src/Mod/Part/App/Geometry.cpp` (7040-7118 `makeFromSurfaceAdaptor`) — adaptor-type -> `Geom*` surface mapping.
- `src/Mod/Measure/App/Measurement.pyi` — `radius/angle/length/delta/com/...` measurement API.
- `src/Mod/Measure/App/MeasureDiameter.cpp` (115 `radius*2.0`), `MeasureRadius.cpp` — diameter/radius primitives.
- `src/Mod/PartDesign/App/FeatureHole.h` (53-80) & `FeatureHole.cpp` (76,97,650) — Hole feature properties & enums (`DepthType`, `DrillPoint`, `BaseProfileType`).
- `src/Base/BoundBox.pyi` (40-95) — bbox members (`XLength`, `Center`, min/max).
- `docs/intent.md` — Phase 3, Validation-First Discipline, Reuse Map.

### Web sources (2024-2026 prior art)

- Text2CAD-Bench (Chamfer/IoU/Invalidity, CadQuery target) — https://arxiv.org/html/2605.18430
- CadBench (multi-metric suite, ~1.4M generations) — https://arxiv.org/html/2605.10873v1
- BenchCAD (Vision2Code/Edit/QA tasks) — https://arxiv.org/html/2605.10865v1
- MUSE (code-check/geometric-check/design-intent three-stage protocol) — https://arxiv.org/abs/2605.28579
- **CADSmith (OCCT-kernel Validator + independent VLM judge + Refiner)** — https://arxiv.org/abs/2603.26512
- CADReview (program error detection/correction) — https://arxiv.org/pdf/2505.22304
- Datum reference frame (classical GD&T framing), US Patent 6,922,690 — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6922690

### Quality assurance

- **Verification:** every FreeCAD API claim is cited to an exact file (and line/class) in the local source; the diameter-as-`radius*2` and cylinder-axis-extraction claims are triangulated across `.pyi` (public API), `MeasureClient.cpp` (implementation), and `Geometry.cpp` (adaptor mapping).
- **Confidence:** High for the FreeCAD/OCCT extraction path (primary source). High for the prior-art positioning (multiple 2026 benchmark papers converge). Medium for exact tolerance defaults — these are stated as *to be tuned by fault injection*, not asserted as final.
- **Limitations:** The local tree was read via `.pyi` stubs and C++ implementation, not executed; the recommended primitives should be smoke-tested against 3-5 hand-made reference parts (as intent.md Phase-0 already prescribes) before the Phase-3 gate. Thread-designation -> measured-geometry mapping (M5 nominal vs. tap-drill vs. clearance) needs a small lookup table authored against the same ISO tables FreeCAD's Hole feature uses.

## 12. Appendices and Reference Materials

### Appendix A — OCCT-to-FreeCAD-to-assertion mapping

| Spec property | OCCT | FreeCAD Python | Assertion primitive |
|---|---|---|---|
| Hole diameter | `BRepAdaptor_Surface.Cylinder().Radius()` | `Face.Surface.Radius` (`Part.Cylinder`) | `hole_diameter` |
| Hole axis | `gp_Cylinder.Axis()` | `Part.Cylinder.Axis` / `.Center` | `hole_axis`, `hole_position` |
| Hole spacing | min-distance / axis lines | `distToShape`, `Measurement.delta` | `hole_spacing` |
| Through vs blind | axial extent / ray-exit | `section`, `Face.ParameterRange` | `hole_through` |
| Overall dims | `Bnd_Box` | `Shape.BoundBox` (`XLength`...) | `expect_bbox` |
| Volume/area | `GProp_GProps` | `Shape.Volume/.Area` | `expect_volume` |
| Perpendicularity | face normals dot | `Face.normalAt`, `Measurement.angle` | `is_perpendicular` |
| Feature count | face iteration + type | `Face.Surface` type filter, `countElement` | `count_cylindrical_holes` |
| Valid solid | `BRepCheck` | `Shape.isValid/.check` | `is_valid_solid` |

### Appendix B — Surface-type enum -> feature meaning

`GeomAbs_Cylinder` -> hole wall / boss / fillet (radius-band + orientation disambiguates); `GeomAbs_Cone` -> countersink / chamfer / drill point; `GeomAbs_Plane` -> flat face / datum; `GeomAbs_Sphere` -> ball end; `GeomAbs_Torus` -> filleted edge / O-ring groove; DISC (planar face bounded by one circle) -> hole opening. (`MeasureClient.cpp:190-229`.)

### Appendix C — PartDesign Hole metadata (hint-only cross-check)

`Diameter`, `Depth`, `DepthType {Dimension, ThroughAll}`, `Threaded`, `ThreadType`, `ThreadSize`, `ThreadClass`, `ThreadFit`, `HoleCutType`, `HoleCutDiameter`, `HoleCutDepth`, `HoleCutCountersinkAngle`, `DrillPoint {Flat, Angled}`, `DrillPointAngle`, `Tapered`, `TaperedAngle`, `BaseProfileType (OnCirclesArcs)`. (`FeatureHole.h:53-80`, `FeatureHole.cpp:76,97,650`.)

---

## Technical Research Conclusion

### Summary of Key Technical Findings

FreeCAD's B-rep, through its Python API over OCCT, makes hole diameter, axis, position, spacing, and overall dimensions **directly and artifact-level measurable** — with the shipped `Measure` workbench as a ready reference implementation. Building Phase-3's spec assertions on measured geometry (not the feature tree) delivers the essential robustness across modeling approaches and sidesteps the Topological Naming Problem. Prior art confirms the choice: property-level programmatic validators (CADSmith, MUSE) are the right lineage; whole-shape-similarity benchmarks (Chamfer/IoU) are not the primary tool for a per-feature spec.

### Strategic Technical Impact Assessment

This unblocks the Phase-3 Validation Design Gate: the recommended assertion-primitive vocabulary gives "done" an objective, deterministic definition that the acting agent cannot grade, satisfying Validation-First Discipline. The same primitives carry forward into Phase-4 DFM and revision-diff checks, so the investment compounds.

### Next Steps Technical Recommendations

1. Implement the geometry primitives (Section 8) as `verify.*` bridge tools, wrapping `Measure`/OCCT logic.
2. Author the 20 Phase-3 specs as primitive sets (dev + held-out).
3. Build the fault-injection suite and tune tolerance bands to >= 95% sensitivity / <= 5% false-alarm before any Phase-3 implementation code exists.
4. Smoke-test primitives against 3-5 hand-made reference parts (reuse Phase-0 golden models).

---

**Technical Research Completion Date:** 2026-07-20
**Research Period:** current comprehensive technical analysis (FreeCAD 1.x source + 2024-2026 prior art)
**Source Verification:** all FreeCAD API claims cited to exact local source files/classes; prior art cited with URLs
**Technical Confidence Level:** High — grounded in primary FreeCAD/OCCT source and convergent recent benchmark literature

_This document is an authoritative technical reference for FreeCAD Buddy's Phase-3 geometry-to-spec assertion strategy and the harness's assertion-primitive vocabulary._
