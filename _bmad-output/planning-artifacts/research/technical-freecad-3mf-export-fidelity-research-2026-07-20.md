---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: ['docs/intent.md', 'docs/references/FreeCAD (src/Mod/Mesh, src/Mod/Part)']
workflowType: 'research'
lastStep: 5
research_type: 'technical'
research_topic: '3MF export fidelity in FreeCAD (and STEP/STL round-trip validation)'
research_goals: 'Assess FreeCAD 3MF import/export maturity, headless export paths, lib3mf fallback, and validation approaches for STEP/STL/3MF; recommend export toolchain + validation checks for the export.* and verify.* tool taxonomy.'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: 3MF Export Fidelity in FreeCAD (and STEP/STL Round-Trip Validation)

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** technical

---

## Research Overview

This report investigates the maturity and failure modes of FreeCAD's mesh/BREP export
subsystem and recommends a concrete export toolchain plus validation checks for the
`export.*` and `verify.*` tool taxonomy defined in `docs/intent.md`. It blocks the
**Phase 0** export criterion ("export STEP, STL … round-trip test passes") and the
**Phase 4** deliverable ("at least STEP + STL exports that re-import cleanly", plus 3MF).

Evidence is drawn, in priority order, from:

1. **Local FreeCAD source** at `docs/references/FreeCAD` — version **26.3.0-dev** (the
   post-1.0 continuous-versioning line; the successor to the 1.x releases). File paths are
   cited inline.
2. **Web research** — FreeCAD/PrusaSlicer/BambuStudio/OpenSCAD issue trackers, lib3mf docs,
   trimesh and ADMesh documentation.

**Bottom line up front:** FreeCAD *has* native 3MF read/write, but it is a **minimal,
single-precision, millimetre-hardcoded core-spec mesh writer** with a documented history of
downstream-slicer incompatibility and a tessellation path that only controls *linear*
deflection. For the verify-first taxonomy this project needs, treat FreeCAD's export as
**one producer among several**, always **re-import and independently validate** every export
(never trust the writer), and keep **`lib3mf` as a validation/repair oracle and optional
fallback writer**. STEP round-trips are the reliable, high-fidelity path (OCCT); mesh
formats are lossy by nature and must be validated on geometry, not on "the file was written".

---

## 1. FreeCAD 3MF Implementation Maturity

### 1.1 Which module owns it

3MF lives entirely in the **Mesh module** (not Part / not a dedicated importer):

- Writer: `src/Mod/Mesh/App/Core/IO/Writer3MF.cpp` / `.h`
- Reader: `src/Mod/Mesh/App/Core/IO/Reader3MF.cpp` / `.h`
- Wired into mesh I/O at `src/Mod/Mesh/App/Core/MeshIO.cpp` (`MeshInput::Load3MF` ~L911,
  `MeshOutput::Save3MF` ~L2193)
- High-level export orchestration: `src/Mod/Mesh/App/Exporter.cpp` (`Exporter3MF`, ~L273–314)
- Python entry point: `Mesh.export(objects, filename, [tolerance=0.1, exportAmfCompressed=True])`
  in `src/Mod/Mesh/App/AppMeshPy.cpp` (~L77, L209)

Copyright header dates the implementation to **2022** (Werner Mayer). It is
**hand-rolled XML over a zip container** — it does **not** use the 3MF Consortium's `lib3mf`.

### 1.2 What the writer actually emits (verified from source)

From `Writer3MF::Initialize` and `SaveObject` (`Writer3MF.cpp` L58–154):

- **Namespace / spec level:** core spec only —
  `http://schemas.microsoft.com/3dmanufacturing/core/2015/02`. No production, materials,
  colors, beam-lattice, or slice extensions.
- **Units: hardcoded `unit="millimeter"`** (L61). There is **no** unit negotiation — if the
  FreeCAD document is authored in inches, the numeric vertex values are written verbatim
  under a `millimeter` declaration (silent unit corruption risk).
- **Metadata:** exactly one entry — `<metadata name="Application">FreeCAD</metadata>`. No
  Title, Designer, CreationDate, or custom metadata. (The intent's Phase-4 "validation
  report" cannot be round-tripped *inside* the 3MF; it must be a sidecar.)
- **Geometry precision:** vertices are streamed straight from the mesh kernel
  (`it->x`, `it->y`, `it->z`, L136). The mesh kernel stores points as **32-bit float**
  (`MeshPoint`), so 3MF vertices carry **single-precision** coordinates regardless of the
  solid's double-precision BREP origin.
- **Object type heuristic:** `GetType()` (L156) writes `type="model"` if the mesh passes
  `MeshEvalSolid` (a closed-manifold check) or if `forceModel` is set, else `type="surface"`.
  `Mesh.export` sets `forceModel` from the `Export3mfModel` preference (default **true**), so
  a **non-watertight mesh can be labelled `model`** — the 3MF file *claims* to be a solid the
  geometry cannot back up. This is a self-deception vector the `verify.*` layer must catch.
- **Build transform:** each object gets a `<build><item>` with a transposed 3×4 matrix
  (`DumpMatrix`, L169). Correct per spec §3.3, but note the transpose convention.
- **Container:** writes `[Content_Types].xml`, `_rels/.rels`, `3D/3dmodel.model` — the
  minimal valid OPC package.

### 1.3 What the reader does (and drops)

From `Reader3MF.cpp`:

- DOM-based (Xerces), **namespace-processing disabled** (`setDoNamespaces(false)`, L119) and
  **no schema validation** — it is lenient but also blind to spec violations.
- Vertices are parsed with **`std::stof` → single-precision float** (L435–437). Triangles via
  `std::stoul`. So even a double-precision third-party 3MF is **truncated to float on import**.
- Reads core mesh + `<components>` (multi-object refs with `p:path`), applies build/component
  transforms, runs `MeshCleanup::RemoveInvalids` and rebuilds adjacency (L391–393).
- **Ignores** materials, colors, textures, metadata, and every 3MF extension. Round-tripping
  a 3MF through FreeCAD is a **geometry-only, single-precision** operation.

### 1.4 Known issues (web-corroborated)

| Issue | Source | Relevance |
|-------|--------|-----------|
| FreeCAD 3MF imports "silently" (renders nothing / "size of object is zero") in PrusaSlicer & BambuStudio; regressed between 0.20 and 0.21 | PrusaSlicer #8401, FreeCAD #10075, BambuStudio #3012, OpenSCAD #4723 | The hand-rolled writer produces files that strict slicers reject. PR #10446 targeted it; treat slicer-acceptance as an *external* validation gate, not assumed. |
| "3mf export exports only part of the model" | FreeCAD #22483 | Visibility/sub-object expansion (`expandSubObjectNames`, `Exporter.cpp` L40–90) silently skips invisible sub-objects — a partial-export self-deception mode. |
| "Mesh export produces very inaccurate results" — >0.75 mm inward deviation at 0.1 mm setting; **Confirmed / Known issue** | FreeCAD #25311 | The `Mesh.export` path exposes **only linear deflection** (`getFaces(aPoints, aTopo, tol)`, `Exporter.cpp` L119). Curved faces under-tessellate because **angular deflection is not applied** on this path. |

**Maturity verdict:** *Functional but immature.* Good enough to write a geometrically-valid
core-spec file for a clean watertight solid at a fine tolerance; **not** robust for
units ≠ mm, curved-surface fidelity, downstream-slicer strictness, or metadata round-trip.

---

## 2. The Export Paths and Their Fidelity

### 2.1 STEP (BREP, lossless) — the reliable path

- Import: `src/Mod/Part/App/ImportStep.cpp` (OCCT `STEPControl_Reader`).
- Export config: `src/Mod/Part/App/Interface.cpp` — OCCT `Interface_Static` knobs:
  `write.step.schema` (AP203 / AP214 / **AP242**), `write.step.unit` (**default `MM`**),
  `write.precision.mode`/`val`, `write.step.assembly`, `write.surfacecurve.mode`,
  `write.step.product.name`.
- Python: `Part.export([...], "f.step")` / `Shape.exportStep(...)`.
- **Fidelity:** double-precision B-rep; no tessellation loss. This is the **canonical
  round-trip** for the Phase 0 criterion "export STEP → re-import → volume ±0.1%". Set an
  explicit schema (**AP214 or AP242**) and `write.step.unit = MM` in the bridge to avoid
  environment-dependent defaults.

### 2.2 STL — lossy, single-precision, deflection-controlled

- Path: mesh kernel → `MeshOutput::SaveBinarySTL` / `SaveAsciiSTL` (`MeshIO.cpp` L1598/L1647).
- Binary STL is single-precision **by spec**; ASCII writer uses `precision(6)` (L1608).
- Same tessellation source as 3MF: for a solid, `Exporter::addObject` tessellates via
  `getFaces(tol)` with **linear deflection only**. Inherits the #25311 accuracy caveat.
- No units, no metadata, no watertight guarantee — STL is a triangle soup.

### 2.3 3MF — lossy, single-precision, but a real container

- Covered in §1. Advantage over STL: zip container, a units *field* (albeit hardcoded), a
  solid/surface *type* field, build transforms, and multi-object support.

### 2.4 Higher-quality mesh path (recommended for `export.mesh`)

`MeshPart.meshFromShape` (`src/Mod/MeshPart/App/AppMeshPartPy.cpp` L94–133, L456–487) exposes
what `Mesh.export` hides:

```
meshFromShape(Shape, LinearDeflection, AngularDeflection=0.5, Relative=False, Segments=False)
```

It sets **both** `setDeflection` (linear) **and** `setAngularDeflection` (angular) plus
`setRelative`. **This is the fix for the #25311 under-tessellation of curved faces.**
Recommended bridge pattern: tessellate the solid explicitly with
`MeshPart.meshFromShape(shape, LinearDeflection=<tol>, AngularDeflection=<rad>)`, then write
that `Mesh` object to STL/3MF — rather than letting `Mesh.export` choose linear-only defaults.

### 2.5 Headless viability

All of the above are pure `App`-layer / Python-API calls — **no GUI dependency**. They run
under `FreeCADCmd` / `freecad --console` and in the CI Docker/conda-forge/AppImage images the
intent's Reuse Map already lists. (`Exporter::addObject` takes a `PyGILStateLocker` and calls
`getSubObject`, which is available headless.) 3MF's zip container relies on `zipios`, bundled
with FreeCAD — no extra runtime dep. Confirmed viable for the Phase 4 headless service.

---

## 3. lib3mf as Fallback / Oracle

`lib3mf` (3MF Consortium, BSD, `pip install lib3mf`, current line **v2.x**) is the reference
implementation of the full 3MF spec (core + materials + production + beam-lattice + slice),
with reader, writer, and a **built-in validation/consistency layer**.

**Recommended role — dual use:**

1. **Independent validation oracle (primary use).** Read FreeCAD's exported `.3mf` back with
   `lib3mf` and assert: it parses without warnings, declares the expected unit, and its mesh
   `IsManifoldAndOriented()` / has a valid volume. This directly attacks the Phase-4
   self-deception mode "service returns 200 for a bad part" — a *different* implementation
   validating the file catches FreeCAD-writer-specific defects (e.g. the #10075 slicer-reject
   family) that FreeCAD's own reader would happily accept.
2. **Fallback writer (secondary, if FreeCAD's writer proves too incompatible).** Take the
   tessellated triangle+vertex arrays from `MeshPart.meshFromShape` and write the 3MF via
   `lib3mf` instead — gaining correct unit handling, richer metadata (title/designer/spec
   assertions), and spec-conformant output that strict slicers accept.

`lib3mf` is also **double-precision-capable on the write side**, sidestepping FreeCAD's float
truncation — though STL/3MF vertices are ultimately float-limited by the formats themselves,
so this matters mainly for very large-coordinate parts.

**Reuse-map alignment:** the intent lists 3MF/STL validation under "`trimesh`, `admesh`,
Open3D … Never [invent] for the checks themselves". `lib3mf` extends that list as the
*format-aware* validator (units/spec-conformance), complementing the *geometry-aware* checks
of trimesh/admesh.

---

## 4. Validation Approaches per Format

Design principle from `docs/intent.md` §Validation-First: **the actor never grades itself**,
and **success is measured on the artifact via re-import round-trips, not on "export returned
ok"**. Every export tool must have a paired verify tool that re-reads the file.

### 4.1 STEP round-trip (`verify.export.step`)

1. `export.step` writes with explicit schema=AP214/AP242, unit=MM.
2. Re-import the written file with a **fresh** `STEPControl_Reader` (new document).
3. Assert on the re-imported shape (OCCT / FreeCAD built-ins — the intent's "Never invent" row):
   - `Shape.isValid()` and `Shape.check()` (BRepCheck) pass.
   - `Volume` within **±0.1%** of source (Phase 0 criterion).
   - `BoundBox` diagonal within tolerance; `CenterOfMass` within tolerance.
   - Face/edge/solid **counts** match (topology preserved, no dropped subshapes).
4. This is the strongest, lowest-noise round-trip — make it the Phase-0 gold check.

### 4.2 STL round-trip (`verify.export.stl`)

STL has no solid guarantee, so validate the *mesh* it produced:

- **trimesh** (`pip install trimesh`) — load the written STL and assert:
  - `mesh.is_watertight` (every edge in exactly two faces),
  - `mesh.is_winding_consistent`,
  - `mesh.is_volume` (watertight + consistent winding + finite centroid + positive volume),
  - `mesh.volume` within a mesh-tolerance band of the source solid's `Volume` (band must
    account for tessellation deflection — e.g. ±(deflection-driven) %, not ±0.1%),
  - `abs(mesh.euler_number)` sane / genus as expected (catches holes and extra shells).
- **admesh** (`pip install admesh`, or CLI) — as a *second, independent* checker for
  STL-specific defects: unconnected facets, bad normals, degenerate facets, holes. Run in
  **check-only** mode for validation; its auto-repair is a *separate* remediation tool, never
  silently applied inside a "pass" (silent repair = a self-deception mode).
- Cross-check the two: if trimesh says watertight but admesh reports unconnected facets (or
  vice-versa), fail and investigate — disagreement between independent validators is signal.

### 4.3 3MF round-trip (`verify.export.3mf`)

Layered, because 3MF is both a container and a mesh:

1. **Container/spec layer — `lib3mf`:** file parses clean; declared `unit` == expected;
   object `type`/manifold flag consistent with geometry (catches the "surface labelled model"
   bug from §1.2); metadata present if the job requires it.
2. **Geometry layer — trimesh:** trimesh reads 3MF directly; apply the same
   watertight / winding / volume assertions as §4.2.
3. **FreeCAD self-round-trip:** re-import via `Mesh.insert`/`Reader3MF` and compare
   facet/vertex counts and bounding box — confirms FreeCAD can read what FreeCAD wrote
   (necessary but, per §1, **not sufficient** — hence the independent lib3mf/trimesh layers).
4. **(Optional, high-value) external-slicer acceptance smoke test:** given the documented
   PrusaSlicer/BambuStudio rejections (#10075), a CI job that runs `prusa-slicer --export-gcode`
   (or `--info`) headless on the exported 3MF and asserts a non-empty, non-error result is the
   *realism* check the intent demands ("realism over convenience"). Gate Phase-4 3MF delivery
   on it.

### 4.4 Validator sensitivity (fault injection — required by the gate)

Per intent §Validation Design Gate, each verifier needs ≥10 planted-fault cases with
**sensitivity ≥ 95%, false-alarm ≤ 5%**. Concrete planted faults for these validators:

- STEP: dropped solid, unit mismatch (write INCH, expect MM), degenerate face, scaled shape.
- STL/3MF: deleted triangle (hole), flipped normals, duplicated shell, coordinate truncated,
  non-manifold edge, `type="model"` on an open surface (the §1.2 bug), inches-as-mm unit lie.
- Container: corrupt zip, missing `3dmodel.model`, malformed transform matrix.

A validator that passes any of these is measured as broken (intent Principle 2).

---

## 5. Recommended Export Toolchain & Tool Taxonomy Mapping

| Tool | Implementation | Notes |
|------|----------------|-------|
| `export.step` | `Part.export` / `Shape.exportStep`; set `write.step.schema=AP214` (or AP242), `write.step.unit=MM`, `write.precision.mode` explicit | Lossless BREP; the canonical round-trip. Pin config each call — don't rely on defaults. |
| `export.mesh` (internal) | `MeshPart.meshFromShape(shape, LinearDeflection=tol, AngularDeflection=0.5, Relative=False)` | **Single tessellation source** for STL & 3MF, with angular deflection — fixes #25311 curved-face under-tessellation. |
| `export.stl` | Write the `export.mesh` result via `Mesh.write` (binary) | Single-precision by format; pair with `verify.export.stl`. |
| `export.3mf` | **Phase 0/1:** FreeCAD `Exporter3MF` from the `export.mesh` result. **If slicer-incompat proves blocking:** switch producer to `lib3mf`. | Always set units explicitly / verify them; force `Export3mfModel` only when the mesh is actually watertight (else the `type` field lies). |
| `verify.export.step` | Re-import + OCCT `isValid`/`check` + Volume/BBox/CoM/count asserts | Phase 0 gold check (±0.1%). |
| `verify.export.stl` | trimesh (`is_volume`/watertight/volume) **+** admesh (facet/normal defects) | Two independent checkers; disagreement = fail. |
| `verify.export.3mf` | lib3mf (spec/units/manifold-flag) + trimesh (geometry) + FreeCAD self-read + optional slicer smoke | Layered; slicer-acceptance is the Phase-4 realism gate. |

**Guiding decisions:**

1. **Never trust the writer.** Every `export.*` is only "done" when its paired `verify.*`
   re-reads the file and asserts geometry. "The bytes were written" is a process check, which
   the intent explicitly rejects (Principle 6).
2. **STEP is the trustworthy round-trip; mesh formats are validated, not trusted.** Report a
   mesh volume tolerance band derived from the tessellation deflection — do not hold STL/3MF
   to the ±0.1% STEP tolerance.
3. **One tessellation source (`MeshPart.meshFromShape` with angular deflection)** feeds both
   STL and 3MF, so the two formats can't silently disagree and the #25311 accuracy bug is
   avoided at the source.
4. **`lib3mf` is the independent oracle** (and optional fallback writer) that catches the
   FreeCAD-writer-specific incompatibilities its own lenient reader would miss.
5. **Wrap, don't fork** (intent Reuse Map): adopt trimesh + admesh + lib3mf as-is behind the
   `verify.*` layer; the *only* invention is the CAD-agent assertion glue (volume-band logic,
   fault-injection suite, slicer-acceptance CI job).

### 5.1 Residual risks / open items

- **Units audit:** because FreeCAD's 3MF writer hardcodes `millimeter`, the bridge must assert
  the source document is in mm (or convert) *before* export. Add a `verify` guard.
- **`type="model"` mislabelling** of non-watertight meshes — explicit check required (§4.3.1).
- **Partial export via visibility filtering** (`Exporter.cpp` `expandSubObjectNames`) — assert
  exported object/facet count matches the intended object set (guards #22483).
- **Slicer strictness drift** — pin the slicer version used in the acceptance CI job; treat a
  new slicer rejection as a regression signal, and consider the `lib3mf` writer fallback.
- **Version pin:** local source is 26.3.0-dev; the CI matrix (intent risk row "FreeCAD version
  drift") should pin the exact tessellation/writer behavior tested here.

---

## Sources

- Local source (`docs/references/FreeCAD`, v26.3.0-dev):
  `src/Mod/Mesh/App/Core/IO/Writer3MF.cpp`, `.../Reader3MF.cpp`,
  `src/Mod/Mesh/App/Core/MeshIO.cpp`, `src/Mod/Mesh/App/Exporter.cpp`,
  `src/Mod/Mesh/App/AppMeshPy.cpp`, `src/Mod/MeshPart/App/AppMeshPartPy.cpp`,
  `src/Mod/Part/App/Interface.cpp`, `src/Mod/Part/App/ImportStep.cpp`.
- [FreeCAD #10075 — 3MF files exported from FreeCAD don't work in PrusaSlicer](https://github.com/FreeCAD/FreeCAD/issues/10075)
- [FreeCAD #25311 — Mesh export produces very inaccurate results (Confirmed/Known issue)](https://github.com/FreeCAD/FreeCAD/issues/25311)
- [FreeCAD #22483 — 3mf export exports only part of the model](https://github.com/FreeCAD/FreeCAD/issues/22483)
- [PrusaSlicer #8401 — 3MF import from FreeCAD fails](https://github.com/prusa3d/PrusaSlicer/issues/8401)
- [BambuStudio #3012 — Load of 3mf from FreeCAD 0.21 fails "no geometry"](https://github.com/bambulab/BambuStudio/issues/3012)
- [OpenSCAD #4723 — Import of FreeCAD 3mf fails silently](https://github.com/openscad/openscad/issues/4723)
- [lib3mf (3MF Consortium)](https://github.com/3MFConsortium/lib3mf/) · [lib3mf docs](https://lib3mf.readthedocs.io/) · [lib3mf on PyPI](https://pypi.org/project/lib3mf/)
- [trimesh docs — base (is_watertight/is_winding_consistent/is_volume)](https://trimesh.org/trimesh.base.html) · [trimesh.repair](https://trimesh.org/trimesh.repair.html)
- [ADMesh docs](https://admesh.readthedocs.io/) · [admesh on PyPI](https://pypi.org/project/admesh/)
