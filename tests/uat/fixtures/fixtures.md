# UAT Fixture Reference

What test data the manual UAT suite uses, where it lives, and how to grade against it. This file
holds no scenarios. **The suite adds NO new fixture binaries** — every model named here is
already committed under `benchmarks/g0/`, or is built by the tests at run time and thrown away.

---

## Golden models

Path: `benchmarks/g0/golden-models/`

| Model | File | Volume (mm³) | Bounding box (mm) | Solids | Note |
|-------|------|--------------|-------------------|--------|------|
| box-10-20-30 | `box-10-20-30.FCStd` | 6000.0 | 10 x 20 x 30 | 1 | The default subject for read and export scenarios. **Ships with `Visibility=false`** — see the note below |
| cylinder-r5-h20 | `cylinder-r5-h20.FCStd` | 1570.7963 | 10 x 10 x 20 | 1 | Curved surface; exercises mesh deflection |
| sphere-r10 | `sphere-r10.FCStd` | 4188.7902 | 20 x 20 x 20 | 1 | Fully curved; the hardest mesh case |
| box40-hole-r5 | `box40-hole-r5.FCStd` | 15214.6018 | 40 x 40 x 10 | 1 | **Genus-1** — has a through hole; use it whenever a topology assertion matters |
| two-box-compound | `two-box-compound.FCStd` | 2000.0 | — | **2** | Two disjoint 10 mm cubes. **`com` is null** — a compound has no single center of mass, so `query_mass_properties` returns `null` there and a scenario asserting a number is wrong |

The reference numbers live in `benchmarks/g0/golden-models/expected.yaml` with their analytic
derivations. They are **hand-computed, never captured from a verify tool** (AD-13): a value read
back from the tool under test cannot grade that tool. `expected.yaml` carries `tolerance.rel:
0.001`.

No `golden_fingerprint.sha256` is committed. A `.FCStd` is a non-byte-reproducible zip, so a
committed hash would be unverifiable. Do not write a scenario that asserts a fixed file hash for
a golden model.

### Golden models ship hidden — every render scenario must pass `include`

Verified 2026-09-12 by opening `box-10-20-30.FCStd` in the live GUI and reading both the MCP tree
and the FreeCAD viewport:

- `query_tree_summary` reports `"visibility": false` for `Box`.
- The FreeCAD viewport renders **nothing**, and the model-tree eye icon is struck through.
- A default `query_screenshot` (no `include`) returns
  `{"render": {"available": true, "empty_scene": true}, "scene": {"rendered_objects": []}}`
  with **no `resource_link`** — the default scene honours the live `Visibility` flag, so a hidden
  object is correctly omitted. This is the shipped behaviour, not a defect.
- `query_screenshot` **with** `view.include: ["Box"]` renders it —
  `rendered_objects: ["Box"]` plus a PNG — because an explicit `include` overrides the flag.

Consequences for scenario authors:

1. **A render scenario against a golden model must pass `view.include`.** Omit it and the
   assertion "a PNG was produced" fails for a fixture reason, not a product reason.
2. **`empty_scene: true` with no `resource_link` is a valid, correct result.** Do not write a
   checkpoint that treats a missing PNG as a render failure without first proving the subject is
   visible.
3. **To test the default-visibility path deliberately** (TC-06-06), toggle `Visibility` in the GUI
   and re-read `query_tree_summary`; do not assume the fixture starts visible.
4. If a scenario toggles visibility, **close the document without saving** so the fixture's
   on-disk flag is preserved for the next run.

---

## Fault-injection fixtures (shape)

Path: `benchmarks/g0/fault-injection/`

Each case directory holds a `case.yaml` and a `fixture.FCStd`. The suite uses two of them
directly:

- `wrong-volume/` — a 12 x 20 x 30 box (volume 7200) standing in for the 10 x 20 x 30 reference
  (volume 6000). The shape is perfectly valid geometry; only the size is wrong.
- `non-watertight-open-shell/` — an open shell, which fails a watertightness check.

**The reference `assertions.checks` in `case.yaml` MUST be passed into `verify_shape`.** This is
the whole point of the fixture, and skipping it silently voids the test. For `wrong-volume`,
`case.yaml` carries:

```yaml
assertions:                       # reference (correct-shape) values; fixture deviates
  checks:
    - {fn: expect_volume, expect: 6000, tol: {rel: 0.001}}
```

Called with those checks, `verify_shape` returns `SPEC_FAILED` — the measured 7200 misses the
expected 6000. Called **without** them, `verify_shape` grades only intrinsic validity, and the
12 x 20 x 30 box is a perfectly valid solid, so it returns `OK`. A bare check would let a
wrong-but-valid shape through and the scenario would report a pass while detecting nothing.
`verify_shape`'s schema requires only `doc`; `checks` is optional, so nothing stops the mistake
except this rule.

Other case directories exist (`clean-control`, `degenerate-face`, `dropped-solid`,
`invalid-self-intersecting-solid`, `non-manifold`, `self-intersecting-compound`, `unit-lie`,
`wrong-bbox`, `wrong-solid-count`, `zero-volume-lamina`) and follow the same `case.yaml`
contract. The UAT suite does not drive them; `benchmarks/g0/fault-injection/score_verify_shape.py`
does.

---

## Fault-injection fixtures (export)

Path: `benchmarks/g0/export-fault-injection/`

Three families, one directory per planted fault, each with the same `case.yaml` contract:

- `step-*` — STEP faults: `step-clean-control`, `step-compsolid`, `step-cut-notch`,
  `step-dropped-solid`, `step-fused-overlap`, `step-loose-face`, `step-open-shell`,
  `step-scaled-half-box`, `step-shell-no-solid`, `step-unit-lie`, `step-unrefined-fuse`.
- `stl-*` — STL faults: `stl-appended-degenerate`, `stl-clean-control`, `stl-collapsed-facet`,
  `stl-duplicated-shell`, `stl-flipped-normals`, `stl-hole`, `stl-missing-face`,
  `stl-non-manifold`, `stl-scaled-mesh`, `stl-shifted-vertex`, `stl-truncated-coordinates`.
- `3mf-*` — 3MF faults: `3mf-clean-control`, `3mf-corrupt-container`, `3mf-corrupt-vertex`,
  `3mf-duplicated-triangle`, `3mf-malformed-transform`, `3mf-missing-model-part`,
  `3mf-missing-triangle`, `3mf-second-non-manifold-object`, `3mf-type-model-lie`,
  `3mf-unit-lie`, `3mf-vertex-index-out-of-range`.

Every family carries a `*-clean-control` case. **Run the clean control alongside any fault
case.** A verifier that fails everything scores the same as a correct one on fault cases alone;
only the control separates detection from indiscriminate rejection.

The reference `assertions.checks` rule above applies identically here. Scoring lives in
`benchmarks/g0/export-fault-injection/score_export_verify.py`.

---

## The bracket working fixture

The mutation scenarios build a working part rather than loading one:

- A plate 60 x 40 x 5 mm.
- Two M5 through-holes, centers 40 mm apart.
- A flange 30 mm tall.

**It is built by the tests, not stored.** There is no `bracket.FCStd` in the repository and none
should be added. It is produced by the typed tool sequence (`sketch_create`,
`sketch_add_geometry`, `sketch_add_constraint`, `sketch_set_datum`, `feature_pad`,
`feature_hole`), which is exactly what those scenarios are grading: building it is the test. A
committed binary would make the build step optional and hide a regression in the tool sequence.

Because it is built, its expected values come from the dimensions above, not from a reference
file. Compute them in the scenario and state the arithmetic there.

---

## Tolerances

**Solid (B-Rep) volumes — golden models and STEP round-trips: within 0.1 % relative.** This is
`tolerance.rel: 0.001` from `expected.yaml`, and the same `tol: {rel: 0.001}` the fault fixtures
carry. Use it for anything measured from an exact solid.

**Mesh volumes — STL and 3MF: a deflection-derived band, NEVER ±0.1 %.** A mesh is a faceted
approximation of a curved surface, so its volume is systematically below the solid's by an amount
set by the tessellation deflection. The band is computed from the deflection actually used for
that export and is carried on the wire as `volume_band` in the self-read facts (see
`_mesh_verify_proxy_handler` in `src/freecad_buddy/hosts/gui_external/entry.py:50-84`). **Pass the
band through; do not substitute a percentage.** Applying ±0.1 % to `sphere-r10` or
`cylinder-r5-h20` fails a correct export, and applying it to `box-10-20-30` passes trivially
because a box meshes exactly — so the tolerance would be graded by which model was picked rather
than by the export.

**Counts and topology are exact.** Solid counts (2 for `two-box-compound`), genus (1 for
`box40-hole-r5`), and watertightness carry no tolerance.

**`com` on a compound is `null`, not a number.** Assert `null` for `two-box-compound`.

---

## What this suite does not add

No new `.FCStd`, `.step`, `.stl` or `.3mf` binary is committed for the UAT suite. Every scenario
either uses a committed `benchmarks/g0/` fixture, builds its subject from typed tools at run
time, or writes an export into `_automation/` and deletes it in its own `Cleanup` block.
