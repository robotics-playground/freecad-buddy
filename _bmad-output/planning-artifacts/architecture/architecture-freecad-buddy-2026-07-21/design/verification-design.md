---
title: 'Verification Subsystem Design — FreeCAD Buddy'
status: draft
date: '2026-07-21'
ad-refs:
  primary: [AD-5, AD-6, AD-7, AD-8, AD-9, AD-13]
  secondary: [AD-1, AD-11, AD-12, AD-17, AD-19, AD-20]
sources:
  - _bmad-output/planning-artifacts/research/technical-undo-transaction-geometry-hashing-research-2026-07-20.md
  - _bmad-output/planning-artifacts/research/technical-tnp-post-mutation-reference-audit-research-2026-07-20.md
  - _bmad-output/planning-artifacts/research/technical-sketch-dof-programmatic-query-research-2026-07-20.md
  - _bmad-output/planning-artifacts/research/technical-geometry-to-spec-assertions-research-2026-07-20.md
  - _bmad-output/planning-artifacts/research/technical-freecad-3mf-export-fidelity-research-2026-07-20.md
---

# Verification Subsystem Design

Design for the verify-first core: the mutation protocol wrapper, `fingerprint()`, the TNP guard, `verify_sketch` / `verify_shape` / `verify_export_*`, and the Phase 3 assertion vocabulary. All implementations live in `usecases/` (AD-1); all report/verdict types live in `contracts/` and reuse `ResultEnvelope` / `ValidationReport` (AD-17). Code that runs inside the FreeCAD process is stdlib + FreeCAD API only (AD-12). Every tool call takes an explicit document handle — never `ActiveDocument` (AD-20).

---

## 1. Mutation Protocol (AD-5)

One wrapper — `run_mutation()` — is the only path any `sketch_*` / `feature_*` / `document_*` mutation tool executes through. No mutation happens outside a bridge transaction; undo history is bridge-owned (AD-5, AD-20).

### 1.1 Design rules

| # | Rule | Rationale (research evidence) |
| --- | --- | --- |
| R1 | The bridge opens/commits transactions itself, always — including headless. | Headless `FreeCADCmd` opens no transactions on its own; without `openTransaction` undo is silently a no-op (`Document.cpp` `_checkTransaction`; UndoMode is a dead shim). |
| R2 | `doc.recompute()` after every `abortTransaction`/undo, before any verification. | Recompute is skipped during undo/rollback (`Document.cpp:2840`); undo pastes properties only. |
| R3 | `openTransaction` uses transaction id 0 (fresh id, single-document). Cross-document grouping is not used unless a future assembly feature deliberately requires it. | Non-zero ids group transactions across documents (undo together) — an unwanted side channel. |
| R4 | Rollback success is measured by re-hash, never assumed. | Bug #6031: undo can fail to restore the pre-`openTransaction` boundary; property restore is best-effort and swallows exceptions. |
| R5 | Never nest or leave transactions open. One transaction per tool call, opened and closed inside `run_mutation()`. | Opening a new transaction silently auto-commits a stray open one and wipes the redo stack; nesting is a #6031 trigger. |
| R6 | A `saveCopy` snapshot is taken before every mutation and deleted only after commit or verified rollback. | Undo history is in-memory only, capped at 20 steps, and not trustworthy alone — the snapshot is the guaranteed restore path. |

### 1.2 Wrapper pseudocode

```python
def run_mutation(doc, op) -> ResultEnvelope:
    # --- pre-state capture (outside the transaction) ---
    fp_before   = fingerprint(doc)                    # AD-6, §2
    refs_before = snapshot_references(doc)            # AD-7, §3
    snap_path   = temp_snapshot_path(doc)             # reserved-prefix temp file
    doc.saveCopy(snap_path)                           # R6: guaranteed fallback

    doc.openTransaction(f"buddy: {op.label}")         # R1, R3 (id 0 implicit), R5
    try:
        apply_typed_op(doc, op)                       # AD-4: typed ops only
        doc.recompute()
        report = post_verify(doc, op, refs_before)    # §1.3
        ok = report.passed
    except Exception as e:
        ok, report = False, error_report(e)

    if ok:
        doc.commitTransaction()
        delete(snap_path)
        return ok_envelope(report, fp_after=fingerprint(doc))

    # --- rollback with proof (R4) ---
    doc.abortTransaction()
    doc.recompute()                                   # R2
    if fingerprint(doc) == fp_before:
        rollback = "rolled_back_verified"
    else:
        restore_from_snapshot(doc, snap_path)         # close + reopen from saveCopy
        doc.recompute()
        assert fingerprint(doc) == fp_before, "ROLLBACK FAILED — hash mismatch"
        rollback = "rolled_back_via_snapshot"
    delete(snap_path)
    return failed_envelope(report, rollback=rollback) # status per AD-17 closed set
```

### 1.3 `post_verify` composition

`post_verify` is the AD-5 checklist, in order (cheap → expensive), short-circuiting on first hard failure:

1. **Recompute clean** — no object with `not obj.isValid()`; collect `getStatusString()` per failed object.
2. **Shape validity** — `verify_shape` (§5) on every shape-bearing object the op touched.
3. **Sketch signal** — `verify_sketch` (§4) on every sketch involved; PASS requires `FullyConstrained == True` (AD-8).
4. **TNP audit** — `audit_references(doc, refs_before)` (§3); any BROKEN/REPOINTED/DROPPED verdict fails.

---

## 2. `fingerprint()` (AD-6)

Exactly one implementation, in `usecases/fingerprint.py`. Document fingerprint = SHA-256 over per-object shape bytes (objects sorted by immutable `Name`) plus a quantized mass-property tuple as independent cross-oracle.

### 2.1 Serializer probe and tag

The serializer is shim-probed once per process (AD-11 capability probe, never version sniffing):

- `exportBinary(stream)` exposed to Python → serializer tag `exportBinary` (OCCT BinTools VERSION_3; byte-deterministic for an unchanged in-memory shape — positional ids, no pointer hash in the stream).
- else `exportBrep(stream)` (ASCII `BRepTools_ShapeSet`, same determinism argument) → serializer tag `exportBrep`. (Tag literals match `contracts/fingerprint.py` — data-contracts-design.md §10.)

Every `Fingerprint` value carries its serializer tag. **Comparing fingerprints across different tags is banned** — the comparison helper raises. Document-XML/FCStd hashing (random UUIDs, zip mtimes, build strings) and tessellation hashing (parallel, non-deterministic meshing) are banned as identity oracles.

### 2.2 Python sketch

```python
Q = 1e-6  # quantization step (spine convention)

def _massprops(shape):
    bb = shape.BoundBox
    t = (shape.Volume, shape.Area,
         bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax,
         *shape.CenterOfMass, *principal_moments(shape))
    return tuple(round(v / Q) * Q for v in t)

def fingerprint(doc) -> Fingerprint:
    entries = []
    for obj in sorted(doc.Objects, key=lambda o: o.Name):   # immutable Name order
        shape = getattr(obj, "Shape", None)
        if shape is None or shape.isNull():
            continue
        buf = io.BytesIO()
        serialize(shape, buf)                                # probed: exportBinary | exportBrep
        entries.append((obj.Name,
                        hashlib.sha256(buf.getvalue()).hexdigest(),
                        _massprops(shape)))
    digest = hashlib.sha256(repr(entries).encode()).hexdigest()
    return Fingerprint(digest=digest, serializer=SERIALIZER_ID,
                       per_object=entries)                   # per-object detail = diff aid
```

Equality semantics: primary = digest equality (same serializer tag). The mass-property tuple is a cross-oracle: BRep-hash equality with mass-prop inequality (or vice versa) on a benchmark run is a validator bug and is investigated, not averaged away. The scope is *representation identity* (undo/rollback proof) — two independently rebuilt but geometrically equal shapes may hash differently, which is correct for this use.

---

## 3. TNP Guard (AD-7)

Bridge-side pair `snapshot_references(doc)` / `audit_references(doc, snapshot)` composing existing FreeCAD 1.x element-map signals. No C++ changes. Capability-gated: if the shim's `element_map_available()` probe fails, every reference verdict is `UNSUPPORTED` — never clean (AD-7).

### 3.1 Data model — what is captured per reference

`snapshot_references` walks every object and records one `RefRecord` per subelement link in each of the four reference-holding subsystems (all funnel through `PropertyLinkSub`/`PropertyLinkSubList` + shadow pairs, so one strategy covers all):

| Subsystem | Property | Captured per entry |
| --- | --- | --- |
| Sketcher external geometry | `SketchObject.ExternalGeometry` (LinkSubList) | owner `Name`, prop name, target object `Name`, `(mappedName, indexedName)` shadow pair, entry count |
| Attachment / datums | `AttachmentSupport` (LinkSubList) | same, plus resolved attachment placement |
| PartDesign profile / dressup | `Profile`, `Base` (LinkSub / LinkSubList) | same, plus entry count (dressup edge lists) |
| Expression engine | `ExpressionEngine` dependencies (`ObjectIdentifier`) | owner, expression path, referenced object/property names |

Per entry additionally: **resolution witness** — the resolved sub-shape's placement or element hash via `getSubObject` / `getElement(mapped, silent=True)`; and per owning `GeoFeature`: its **`ElementMapVersion`**.

```python
RefRecord = {
  "owner": str, "prop": str, "target": str,
  "entries": [ {"mapped": str, "indexed": str, "witness": WitnessHash} ],
  "element_map_version": str,
}
```

### 3.2 Audit layers

Run after mutate → recompute, in order:

- **Layer 0 — error sweep (cheap, hard-fail class).** `[(o.Name, o.getStatusString()) for o in doc.Objects if not o.isValid()]`. Catches missing external geometry (Sketcher `Missing` flag → recompute error), unresolvable attachments (`AttachEngineException`), broken expressions.
- **Layer 1 — mapped-name diff (the guard proper).** For each snapshotted entry:
  - subname now begins with `?` (`hasMissingElement`) or `getElement(mapped, silent=True)` returns null → **BROKEN**;
  - reference resolves but mapped name changed, or witness differs, while the reference was not the mutation's intended target → **REPOINTED** (silent re-point);
  - a LinkSubList lost entries vs snapshot → **DROPPED** (the `FeatureDressUp.getContinuousEdges` silent-drop trap — count comparison is mandatory, `Error` status alone misses it);
  - otherwise **PASS**.
- **Layer 2 — history cross-check (only where Layer 1 is ambiguous).** `TopoShape.getElementHistory(mapped)` — the current element must descend from the same source tag/element as pre-mutation. Divergent history on an unchanged reference = REPOINTED even when witnesses coincide.

### 3.3 Verdict shape

Per reference: `{owner, prop, mapped_before, state_after, verdict: PASS|BROKEN|REPOINTED|DROPPED|UNSUPPORTED, layer: 0|1|2, detail}`. Aggregate verdict feeds `post_verify` (§1.3): any non-PASS (other than re-baselined, below) → mutation fails and rolls back. Every audit report records the `ElementMapVersion` banner (spine conventions).

### 3.4 `ElementMapVersion` re-baseline rule

If an owner's `ElementMapVersion` differs from its snapshot value, all mapped names under it may legitimately re-hash (shape-build logic changed, e.g. FreeCAD upgrade). Verdict for those entries is **RE-BASELINED**, the snapshot is re-taken, and the audit does **not** fail — a version bump re-baselines, it never fails (AD-7). RE-BASELINED entries are still reported so drift is visible.

---

## 4. `verify_sketch` (AD-8)

Read-only tool. Contract: `doc.recompute()` first (properties are only guaranteed fresh post-recompute; `SketchObject.execute()` runs `solve(true)` on every recompute), then read properties. `solve()` return codes are never used as the DoF signal — logging only (a `0` return means "solved", not "fully constrained").

### 4.1 Report fields

| Field | Source | Notes |
| --- | --- | --- |
| `dof` | `sk.DoF` | QR-decomposition DoF count |
| `fully_constrained` | `sk.FullyConstrained` | **the PASS signal** — implies DoF==0 *and* clean solve |
| `geometry_count` / `constraint_count` | `sk.GeometryCount` / `sk.ConstraintCount` | |
| `conflicting` | `sk.ConflictingConstraints` | 1-based ids → mapped to `Constraints[id-1]` name/type |
| `redundant` / `partially_redundant` | `sk.RedundantConstraints` / `sk.PartiallyRedundantConstraints` | defensive `getattr` behind shim (1.0+ availability) |
| `malformed` | `sk.MalformedConstraints` + `sk.evaluateConstraints()` | invalid-index / un-addable constraints |
| `degenerate_geometry_count` | `sk.detectDegeneratedGeometries(tol)` | zero-length/degenerate elements |
| `open_vertices` | `len(sk.OpenVertices)` | open wire endpoints |
| `under_constrained_elements` | `sk.getGeometryWithDependentParameters()` | `(geoId, posId)` list — repair-loop diagnostic |
| `solver_status_code` | optional `sk.solve()` | logging only |

### 4.2 Pass/warn/fail policy (AD-8)

| Verdict | Condition |
| --- | --- |
| **PASS** | `FullyConstrained == True`, read after `doc.recompute()` — and only this |
| **HARD FAIL** | non-empty `conflicting` or `malformed`; `evaluateConstraints() == True`; `dof < 0` (over-constrained); `dof > 0` (under-constrained); `degenerate_geometry_count > 0` |
| **WARN (never fail)** | non-empty `redundant` / `partially_redundant` — quality warning; optional cleanup via `autoRemoveRedundants()` is a separate explicit repair action, never applied silently inside verify |

Constraint diagnostics in the report map 1-based solver ids to `Constraints[id-1]` names (spine error convention).

---

## 5. `verify_shape`

Deterministic read-only contract on a shape-bearing object; also the reusable gate inside `post_verify` and `is_valid_solid` (§7).

| Field | Source | Pass condition |
| --- | --- | --- |
| `is_valid` | `Shape.isValid()` | must be True |
| `check_report` | `Shape.check()` (BRepCheck) | no errors reported |
| `is_solid` / `is_watertight` | shape type is `Solid`, `Shape.isClosed()` on shells | must hold when the op claims a solid |
| `volume` / `area` | `Shape.Volume` / `Shape.Area` | volume > 0 for solids; compared to expectations where the caller supplies them |
| `bbox` | `Shape.BoundBox` (min/max, extents, center) | reported; compared when expected |
| `counts` | faces / edges / vertices / solids / shells via `countElement` | reported; compared when expected |
| `shape_tolerance` | `Shape.getTolerance(...)` | reported — downstream assertions must never be tighter (§8) |

Result is a `ValidationReport` (AD-17): every field is a re-executed deterministic check; agent claims are never echoed.

---

## 6. `verify_export_*` (AD-9)

Every `export_*` completes only through its paired `verify_export_*` re-import check — "bytes were written" is never success. One tessellation source feeds both mesh formats: `MeshPart.meshFromShape(shape, LinearDeflection=lin, AngularDeflection=ang, Relative=False)` — linear **and** angular deflection (fixes the linear-only under-tessellation defect, FreeCAD #25311) — so STL and 3MF cannot silently diverge.

### 6.1 Orchestration split

Third-party oracles (trimesh, admesh, lib3mf) live only in the external MCP/harness process (AD-12). Therefore `verify_export_*` is **orchestrated on the external-process side**; the FreeCAD self-read leg runs in-FreeCAD via RPC (AD-9).

| Leg | Runs in | Checks |
| --- | --- | --- |
| STEP re-import, 3MF/STL FreeCAD self-read | FreeCAD process (via RPC, or inline headless) | fresh-document re-import; `verify_shape` on result; count/bbox comparisons |
| trimesh / admesh / lib3mf oracles | external process | file-level and mesh-level independent validation |
| Verdict assembly | external process | merges legs into one `ValidationReport`; independent-oracle disagreement = **FAIL** (disagreement is signal, never averaged) |

### 6.2 `verify_export_step` — the canonical round-trip

Export pins config **per call**: `write.step.schema = AP214` (or AP242) and `write.step.unit = MM` — never ambient defaults. Verify:

1. Re-import the written file into a fresh document (fresh `STEPControl_Reader` state).
2. `Shape.isValid()` + `Shape.check()` pass on the re-imported shape.
3. `Volume` within **±0.1 %** of source; `BoundBox` diagonal and `CenterOfMass` within tolerance.
4. Face / edge / solid counts match the source (no dropped subshapes).

### 6.3 `verify_export_stl` — dual independent mesh oracles

- **trimesh (primary):** `is_watertight`, `is_winding_consistent`, `is_volume`, `mesh.volume` within the deflection-derived band (§8 — never ±0.1 %), sane `euler_number` / expected genus.
- **Second oracle:** admesh where available (check-only mode: unconnected facets, bad normals, degenerate facets, holes; auto-repair is a separate remediation tool, never silently applied inside a pass). admesh is dormant upstream and Linux-leaning; the fallback second oracle is chosen at the Phase 0 gate (AD-9). The verifier interface takes an abstract `SecondStlOracle` so the pin is a config swap.
- trimesh/second-oracle disagreement → FAIL.

### 6.4 `verify_export_3mf` — layered oracle stack

1. **lib3mf (container/spec layer):** parses clean; declared `unit == "millimeter"` and the source document was mm (guard against the writer's hardcoded-mm unit lie); object `type` consistent with actual manifoldness (catches non-watertight mesh labelled `type="model"`); required metadata present.
2. **trimesh (geometry layer):** same assertions as STL.
3. **FreeCAD self-read (in-FreeCAD via RPC):** re-import; facet/vertex counts and bbox match — necessary but not sufficient (FreeCAD's lenient reader accepts its own writer's defects).
4. Exported object/facet count matches the intended object set (guards visibility-filtered partial export, FreeCAD #22483).
5. Slicer-acceptance smoke test and lib3mf-as-fallback-writer: deferred to the Phase 4 realism gate (spine Deferred table).

Any layer failing, or any cross-oracle disagreement → FAIL.

---

## 7. Assertion Primitive Vocabulary (Phase 3, AD-13)

Fixed, closed vocabulary in `contracts/` (names + signatures); measurement implementations in `usecases/`, wrapping the `Face.Surface` typed-geometry path (`Part.Cylinder.Radius/.Center/.Axis`) that the shipped Measure module already uses — wrapped, not forked. Assertions measure **geometry in an explicit anchor frame**; feature metadata (e.g. `PartDesign::Hole.Diameter`) is diagnostic hint only; sub-element index selectors are banned in specs (AD-13). Each primitive returns `(passed, measured, expected, tolerance, detail)` inside a `ValidationReport`.

### 7.1 Frame and selectors

- `anchor_frame(spec) -> Frame` — declared per spec from the closed derivation set: **named datum | base sketch plane | largest planar face fallback**, resolved by one shared implementation. All subsequent measurements are transformed into this frame before comparison.
- `HoleSelector` — a geometric query (radius band, axis direction relative to frame, position region), never an index. Resolution at assert-time yields logical holes after disambiguation (§7.3).

### 7.2 Primitive set

| Primitive | Signature | Measurement |
| --- | --- | --- |
| `is_valid_solid` | `(shape)` | `verify_shape` gate (§5) |
| `count_cylindrical_holes` | `(shape, frame, radius, axis_dir, tol) -> int` | filter cylindrical `Face.Surface`, disambiguate (§7.3), group coaxial, count logical holes |
| `hole_diameter` | `(shape, selector, expected, tol)` | `2 * Part.Cylinder.Radius` |
| `hole_position` | `(shape, selector, expected_xy, tol)` | cylinder axis intersected with / `.Center` projected onto the anchor plane, in frame coords |
| `hole_spacing` | `(shape, sel_a, sel_b, expected, tol)` | axis-to-axis distance (projected centers in frame; `distToShape` witness as cross-check) |
| `hole_through` | `(shape, selector)` | axis exits both sides: `section()` at entry and exit faces both open, or axial extent (`Face.ParameterRange`) spans local thickness |
| `distance_between` | `(shape, sel_a, sel_b, expected, tol)` | `Shape.distToShape` min distance |
| `angle_between` | `(shape, sel_a, sel_b, expected, tol)` | face normals (`normalAt`) / edge directions; includes perpendicular/parallel as expected = 90°/0° |
| `expect_bbox` | `(shape, frame, x, y, z, tol)` | `Shape.BoundBox` extents measured in the anchor frame (never the naive global bbox on non-axis-aligned parts) |
| `expect_extent` | `(shape, frame, direction, length, tol)` | oriented extent along a frame direction |
| `expect_volume` | `(shape, expected, rel_tol)` | `Shape.Volume` |

Every Phase 3 spec compiles to a set of these; whole-shape similarity (Chamfer/IoU) is never a primary metric (AD-13).

### 7.3 Disambiguation rules (normative for `count_cylindrical_holes` and selectors)

1. **Hole vs boss:** a cylindrical face is a hole wall iff material lies *outside* the cylinder — test the face orientation/normal (hole wall normal points toward the axis) or an inside-solid membership test on a point offset from the wall toward the axis.
2. **Coaxial grouping:** cylindrical faces sharing an axis direction and collinear centers (within angular/positional tolerance) merge into **one logical hole** before counting (stepped walls / split faces).
3. **Fillet filtering:** exclude cylindrical faces that are partial arcs — count only faces whose bounding edges include full circles; additionally filter by the spec's radius band (fillets are typically small-radius partial cylinders).
4. **Countersink/counterbore:** a cone (or larger coaxial cylinder) sharing the hole axis is recognized as part of the same logical hole; its diameter/angle is checked only when the spec asserts it.
5. **Metadata cross-check (diagnostic only):** when a `PartDesign::Hole` feature exists, declared-vs-measured mismatch is reported as an explanatory detail, never as the verdict.

---

## 7a. Visual Verification Leg — `verify_visual` (AD-21, Phase 3)

Dual-channel done: a generated part is done ⇔ geometry assertions (§7) PASS **∧** `verify_visual` PASS. Conjunctive only — the judge can never pass a part geometry failed, and per-operation verification (§1) stays geometry-only.

- **Independence:** the judge is a vision-capable model that is never the acting agent — separate model id or separate context, enforced at preflight exactly like the Phase 1 grader (validation-harness-design §8). The actor inspecting its own render is banned as a verdict source.
- **Inputs (standard visual set, one judge call at part-done):**
  1. **3D iso render** (constructed-scene renderer) — gestalt, feature presence, orientation.
  2. **Focus views** — one per spec-named feature (`view.focus` selectors).
  3. **Dimensioned TechDraw projections, front/top/right** — auto-generated per-axis 2D engineering drawings [user decision, full-dims-at-Phase-3]. Line art gives the judge perspective-free proportions/symmetry/layout; the dimension callouts give an independent cross-check of stated dimensions against the spec text — the only check that can catch spec→assertion mistranslation.
  4. The spec text + a structured checklist derived from it ("flange present and perpendicular", "two holes 40 mm apart per drawing callout", "proportions consistent with 60×40×5").
- **Drawing generation (`techdraw_for_judge`, Phase 3 usecase):** runs on a **TempDoc copy** (AD-20 reserved prefix — TechDraw page objects never pollute the part document): `TechDraw::DrawPage` + three `DrawViewPart` projections + dimensions generated **from the part's named driving parameters and the spec's assertion set** (dimension what the spec states — design-intent principle; parameter-sourced, not view-geometry-picked, so TNP-immune). Export page to PNG/SVG, discard TempDoc. Drawing images ship to the judge at legible resolution (≥2048 px page width — judge-directed input travels directly to the judge API, not through client context, so the AD-10 ≤1024 px *user-facing* budget does not apply).
- **Judge precedence on dimensions:** a drawing-callout-vs-spec mismatch flagged by the judge is a **finding that blocks done** and triggers investigation of both the part and the assertion compilation; geometry assertions (§7) remain the authoritative measurement — the judge never overrides a passing geometric measurement with a misread callout (findings are re-checked against `verify_*` measurements before rework).
- **Phase 3 entry-gate additions:** headless TechDraw page-export spike (TechDrawGui module dependency risk — verify SVG/PNG export under the render-leg environment); drawing-generator fault cases (planted wrong-callout drawing must be flagged by the judge; sensitivity counted in the judge's suite).
- **Output:** structured verdict `{pass: bool, findings: [{view, observation, severity}]}`, temperature 0, schema-validated; wrapped in the standard `ValidationReport` (check id `visual.judge`). Findings feed the repair loop as diagnostics alongside the geometry discrepancy vector.
- **Degradation (fail-closed):** render capability `none` or judge unreachable → check reports `visual.unavailable`, part is **not done**; the only bypass is an explicit operator waiver flag, audit-logged with the reason (AD-21).
- **Judge as validator (AD-13/AD-19):** fault-suite of planted visually-wrong parts — mirrored part, missing flange, feature on wrong face, grossly wrong proportions — plus clean controls; sensitivity ≥95 % / FA ≤5 % before verdicts are citable; rubric/checklist edits invalidate prior sensitivity runs (hash-staleness rule).

## 8. Tolerance Policy

Defaults below are starting points; **exact values are calibrated by each phase's ≥10-case fault-injection suite** (AD-19, spine Deferred) until every validator reports sensitivity ≥ 95 % and false-alarm ≤ 5 % (AD-13) — tolerances are tuned against planted faults, not guessed. No assertion may be tighter than the shape's own `Shape.getTolerance` (spine convention).

| Quantity | Default tolerance | Notes |
| --- | --- | --- |
| Fingerprint mass-prop quantization | 1e-6 (absolute, per component) | AD-6 fixed; not calibratable |
| Fingerprint digest | exact equality | same serializer tag only |
| Linear dimension (diameter, spacing, position, extent) | ±0.05 mm absolute, plus relative band for large dims | per-assertion override allowed in spec |
| Angle (perpendicularity, `angle_between`) | ±0.1° | via normal dot-product |
| STEP round-trip volume | ±0.1 % | AD-9 fixed |
| STEP bbox diagonal / CoM | ±0.1 % / ±0.05 mm | calibrate |
| Mesh (STL/3MF) volume band | derived from tessellation deflection (linear + angular), **never ±0.1 %** | AD-9 fixed rule; band computed per export call from the deflection actually used |
| Mesh counts (self-read leg) | exact match on facet/vertex counts vs written mesh | same tessellation source |
| Coaxial grouping | axis angle ≤ 0.1°, center-line offset ≤ 0.01 mm | calibrate |
| Degenerate sketch geometry | `detectDegeneratedGeometries` default tol | kernel default; calibrate |
| Volume assertion (`expect_volume`) | ±1 % relative | magnitude sanity, not precision |
| Floor for all of the above | `Shape.getTolerance` of the measured shape | never assert tighter than the B-rep's own tolerance |

---

## 9. Verification Obligations on This Subsystem (AD-13 / AD-19)

The validators themselves are validated before their scores are citable:

- **Fingerprint:** planted 1 µm dimension change / hole add-delete / mirror must change the digest; N repeated hashes of an unchanged document in one process must be identical; BRep-hash and mass-prop oracles must agree on the benchmark.
- **Rollback:** deliberately reproduce the #6031 pattern (sketch-on-plane) and confirm the hash-mismatch path fires and the snapshot restore re-verifies.
- **TNP guard:** the two known false-negative traps — dressup silent edge drop, coincidental witness match — are planted cases; the 5 TNP-provoking benchmark scenarios must all be flagged.
- **Sketch:** planted unconstrained line, duplicate dimension, over-definition, bad-index constraint, zero-length edge — each maps to a distinct property signal.
- **Export:** planted dropped solid, unit lie, hole in mesh, flipped normals, non-manifold edge, `type="model"` on open surface, corrupt container.
- **Assertions:** planted missing hole, wrong diameter, mirrored pattern, 0.5 mm spacing error.

Each suite must show sensitivity ≥ 95 % / false-alarm ≤ 5 % before phase implementation begins (AD-19); reports carry the spine banner (FreeCAD version, `ElementMapVersion`, validator sensitivity).
