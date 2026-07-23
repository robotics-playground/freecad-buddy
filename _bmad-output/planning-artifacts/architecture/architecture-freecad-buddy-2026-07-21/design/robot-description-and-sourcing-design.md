---
title: 'Robot-Description Export & Part Sourcing Design — Phase 5'
status: draft
date: '2026-07-23'
ad-refs: [AD-22, AD-23, AD-9, AD-11, AD-12, AD-17, AD-20, AD-16, AD-1, AD-2]
binds: ['../ARCHITECTURE-SPINE.md']
sources:
  - ../ARCHITECTURE-SPINE.md
  - ../../../../../sprint-change-proposal-robot-description-2026-07-23.md
  - docs/references/FreeCAD/src/Mod/Assembly/App
  - docs/references/FreeCAD/src/Mod/Part/App/TopoShapeSolidPyImp.cpp
  - docs/references/FreeCAD/src/Mod/Import/App
---

# Robot-Description Export & Part Sourcing Design — Phase 5

Implementation-ready design for the Phase-5 capability governed by **AD-22** (URDF/SDF export)
and **AD-23** (off-the-shelf part sourcing). It extends the existing rings and conventions — the
new tools follow the `export_`/`verify_` pairing (AD-9 pattern), the contracts-owned envelopes
(AD-17), the document lifecycle (AD-20), the version shim (AD-11), and the stdlib-only in-FreeCAD
posture (AD-12). Nothing here weakens an existing AD; it is additive and gated at the G5-robot
entry gate (AD-19). Detail that depends on empirical Phase-5 spikes is marked **[GATE-DECIDED]**.

## 0. Prerequisite & build-path

Robot-description export consumes a **kinematic tree**, which comes from a Phase-5 **Assemblies**
capability (native FreeCAD Assembly workbench — `AssemblyObject`, `JointGroup`, joints created via
`CommandCreateJoint`: Fixed/Revolute/Cylindrical/Ball/Distance/…; `AssemblyObject.solve()` returns
int, >0 solved / 0 redundant / -1 error). That capability is a separate epic and a hard
prerequisite: Epic 7 cannot complete before an assembly with a resolvable joint tree exists.

**Build-path decision [GATE-DECIDED]** — two options for emitting the XML, chosen at the G5-robot
gate after a spike:
- **Wrap the CROSS addon** (Common Robotic-Oriented Sensor System — authors URDF/SDF from FreeCAD
  assemblies). Reuse-first per the spine convention: adopt and wrap if it fits, never fork. CROSS
  runs in-FreeCAD, so it can't import our external deps — it would be invoked on the FreeCAD side.
- **Emit XML ourselves** from the assembly tree + native inertials + mesh export, if CROSS doesn't
  fit (version, API, dependency, or licensing).
Either way the **verify leg is ours** and identical — the design below is build-path-agnostic on
the export side and fully specified on the verify side.

## 1. Ring placement (AD-1, AD-12)

| Component | Ring | Runs in | Notes |
| --- | --- | --- | --- |
| `usecases/robot_export.py` | usecases | FreeCAD process | reads the Assembly tree + inertials via shim; emits URDF/SDF XML (or drives CROSS); stdlib + FreeCAD only (AD-12) |
| `usecases/part_import.py` | usecases | FreeCAD process | STEP import via the document lifecycle; measured-frame derivation |
| `adapters/robot_oracles.py` | adapters | external process | the `verify_export_urdf`/`verify_export_sdf` orchestration: re-parse + schema-validate + kinematic-tree/inertial/mesh checks, using a third-party URDF/SDF parse lib (external-only, AD-12) |
| `usecases/shim.py` (extend) | usecases | FreeCAD process | new capability probes: `assembly_available()`, `assembly_joint_tree(doc)`, `solid_inertials(obj)` |
| `contracts/` (extend) | contracts | both | `RobotExportResult`, `RobotVerifyReport` shapes reusing `ResultEnvelope`/`ValidationReport` (AD-17) — no new envelope variant |

Orchestration split mirrors AD-9: the third-party parse/schema oracle lives external
(`robot_oracles.py`); the in-FreeCAD legs (read the assembly tree, compute inertials, write meshes)
run in the FreeCAD process, reached over RPC in GUI mode.

## 2. Unit & frame boundary (AD-22, normative)

The single most error-prone seam. Fixed here, pinned per call, never ambient:

| Quantity | FreeCAD internal | URDF/SDF target | Conversion |
| --- | --- | --- | --- |
| Length | millimetre | metre | ÷ 1000 |
| Angle | degree | radian | × π/180 |
| Mass | gram-equivalent from `Mass` (density-scaled) | kilogram | per the density basis; **[GATE-DECIDED]** density source (unit-density vs material) |
| Inertia | mm²·mass | kg·m² | length² and mass conversions composed |

**Frame rules (URDF):** a joint `<origin xyz rpy>` is expressed in the **parent-link frame** and
maps parent→joint; the child link frame **coincides** with the joint frame; `<axis>` is in the
**joint frame**. `<visual>/<collision>/<inertial><origin>` are in the **link frame**.
**Frame rules (SDF):** every `<pose>` carries an explicit `relative_to`; axis vectors are in the
joint frame unless `expressed_in` says otherwise.

Every emitted origin records, in the export result's structured content, the frame it was expressed
in — so the verify leg and a human reviewer can check it. Right-handed frames throughout.

## 3. Assembly → link/joint mapping

| Assembly element | URDF | SDF |
| --- | --- | --- |
| A solved part (body) | `<link>` | `<link>` |
| A joint in the `JointGroup` | `<joint type=…>` between parent/child links | `<joint type=…>` |
| Fixed joint | `type="fixed"` | `type="fixed"` |
| Revolute joint | `type="revolute"` (+ limits) or `continuous` (no limits) | `type="revolute"` |
| Cylindrical / prismatic | `type="prismatic"` (axial) | `type="prismatic"` |
| Ball | (URDF has no ball; emit `floating` or decompose — **[GATE-DECIDED]**) | `type="ball"` |

The solved assembly placements (`AssemblyObject.solve()` then read each part's `Placement`) give the
link poses; the joint definitions give the tree edges. The tree's **root** is the grounded/fixed
part. A continuous joint must **not** carry fake finite limits (a common URDF error) — no limits
means `continuous`, not `revolute` with wide bounds.

## 4. Inertials from native API (AD-22)

Read per link from the solid, via shim `solid_inertials(obj)` wrapping the source-verified surface:
- `Mass` → link mass (→ kg)
- `CenterOfMass` (Vector3d) → `<inertial><origin>` in the link frame (→ m)
- `MatrixOfInertia` / `PrincipalProperties` → the inertia tensor (→ kg·m²)

The inertial origin is the **center of mass**, not the visual origin — never copy one to the other.
If a value is approximated (e.g. a link with no solid, or a placeholder density), the result records
the method; the verify leg flags a missing or implausible inertial as at least a warning, a
non-positive-definite tensor as a failure.

## 5. Tool schemas (AD-9 pairing, AD-17 envelopes)

Wire names follow the underscore convention. Each `export_*` carries `verified: false` until its
pair passes. Fragments show `structured_content`; each wraps the contracts `ResultEnvelope`.

### 5.1 `export_urdf`

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" },
    "assembly": { "type": "string", "description": "assembly object Name (must be solved)" },
    "path": { "type": "string", "description": ".urdf output target" },
    "mesh_format": { "enum": ["stl", "dae"], "default": "stl" },
    "mesh_dir": { "type": "string", "description": "relative mesh output dir beside the .urdf" },
    "collision": { "enum": ["primitive", "mesh"], "default": "primitive",
                   "description": "simplified primitives (stable) or full mesh" }
  }, "required": ["doc", "assembly", "path"] },
  "outputSchema-result": { "type": "object", "properties": {
    "export_id": { "type": "string" }, "path": { "type": "string" },
    "links": { "type": "array", "items": { "type": "object", "properties": {
      "name": { "type": "string" }, "frame": { "type": "string" },
      "mass_kg": { "type": "number" }, "mesh": { "type": "string" } } } },
    "joints": { "type": "array", "items": { "type": "object", "properties": {
      "name": { "type": "string" }, "type": { "type": "string" },
      "parent": { "type": "string" }, "child": { "type": "string" },
      "axis_frame": { "type": "string" } } } },
    "units": { "const": "m_kg_rad", "description": "pinned conversion applied (AD-22)" },
    "verified": { "const": false, "description": "completes ONLY via verify_export_urdf (AD-9)" }
  }, "required": ["export_id", "path", "verified"] } }
```

### 5.2 `verify_export_urdf`

```json
{ "inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" }, "export_id": { "type": "string", "description": "binds the pair" }
  }, "required": ["doc", "export_id"] },
  "outputSchema-result": { "type": "object", "properties": {
    "reparse": { "type": "object", "properties": {
      "parses": { "type": "boolean" }, "schema_valid": { "type": "boolean" },
      "single_root": { "type": "boolean" }, "acyclic": { "type": "boolean" },
      "one_parent_per_child": { "type": "boolean" } } },
    "joints": { "type": "object", "properties": {
      "axes_normalized": { "type": "boolean" }, "continuous_no_fake_limits": { "type": "boolean" } } },
    "inertials": { "type": "object", "properties": {
      "all_mass_positive": { "type": "boolean" }, "tensors_positive_semidefinite": { "type": "boolean" } } },
    "meshes": { "type": "object", "properties": {
      "all_resolve": { "type": "boolean" }, "scale_matches_metre": { "type": "boolean" } } },
    "verdict": { "enum": ["PASS", "FAIL"] },
    "banner": { "type": "object", "description": "ValidationReport banner (AD-17)" }
  }, "required": ["reparse", "verdict"] } }
```

`export_sdf`/`verify_export_sdf` share this shape; the SDF verify adds `scope` (model vs world),
`poses_relative_to_resolves`, and `frame_attachment_acyclic`. Any failed check → envelope
`status: "SPEC_FAILED"`; a parse failure → `RECOMPUTE_ERROR`-class detail. Independent of the
export build-path (CROSS or our XML), the verify leg re-parses the written file from scratch —
"bytes were written" is never success.

### 5.3 Part sourcing / import (AD-23)

```json
{ "part_import.inputSchema": { "type": "object", "properties": {
    "doc": { "type": "string" }, "step_path": { "type": "string", "description": "local .step/.stp" },
    "label": { "type": "string", "description": "intent-bearing occurrence label" }
  }, "required": ["doc", "step_path"] },
  "part_import.outputSchema-result": { "type": "object", "properties": {
    "object": { "type": "string", "description": "imported object Name" },
    "measured": { "type": "object", "description": "bbox/com/axis from query_mass_properties — the basis for mating frames (never the assumed origin)" },
    "provenance": { "type": "object", "properties": {
      "catalog_id": { "type": ["string", "null"] }, "source_url": { "type": ["string", "null"] },
      "license": { "type": ["string", "null"] } }, "description": "recorded for shipped fixtures (AD-16)" }
  }, "required": ["object", "measured"] } }
```

Catalog **search** is an external adapter (swappable, `[GATE-DECIDED]` which catalog); it returns
a downloadable STEP path that `part_import` then brings in through the document lifecycle (AD-20).
Placement is standard bridge flow (feature/datum/selector), addressed by geometric query or mapped
name — never a bare imported face index.

## 6. Verify orchestration (AD-9 split)

| Leg | Runs in | Checks |
| --- | --- | --- |
| Assembly-tree read, inertial compute, mesh write | FreeCAD process (RPC in GUI) | link/joint extraction, `solid_inertials`, mesh export |
| URDF/SDF re-parse + schema-validate | external process | `robot_oracles.py` with a third-party parse lib; structural tree checks |
| Verdict assembly | external process | merges legs into one contracts `ValidationReport`; any failed check → FAIL |

## 7. Fault suite (G5-robot entry gate, AD-13/AD-19)

Before any export tool ships, the verify leg proves sensitivity ≥95 % / FA ≤5 % on planted faults:
wrong-frame axis, second root, cyclic tree, child with two parents, negative/implausible inertia,
non-normalized axis, continuous-with-fake-limits, unresolved mesh, mm-as-m unit lie, SDF pose with
unresolvable `relative_to`. Plus clean controls (the golden 2–3-link arm). Bound in
`_registry/validators.yaml` like every other validator.

## 8. Conflicts

No AD conflicts. Two recorded interpretations:
1. **Ball-joint in URDF** — URDF has no native ball joint; emit `floating` or decompose into three
   revolutes. **[GATE-DECIDED]** at G5-robot; noted so it isn't silently mishandled.
2. **Mass/density basis** — FreeCAD volume × density gives mass; the density source (unit density
   vs per-material) is **[GATE-DECIDED]**. The inertial verdict checks *plausibility and
   positive-definiteness*, not an absolute mass, until a density basis is fixed.
