# G0 export-fault-injection suite

Planted export-defect + clean-control fixtures that validate `verify_export_step`,
`verify_export_stl`, and `verify_export_3mf` at sensitivity >=95% / false-alarm <=5% (AD-9,
AD-19, NFR2). Each case commits a real exported file carrying a file-level defect (or a clean
control) next to a `case.yaml` recording the targeted verifier, the format, the DETECT /
PASS_CLEAN expectation, and the reference source facts the verifier compares against.

## Detection rule — the fixture deviates from the reference

Each `case.yaml` records the source facts a **correct** export of the intended part yields
(volume, face/edge/solid counts, bbox, unit). The committed file carries a real defect that
violates one of those facts, so a verifier re-reading the file and comparing to the reference
detects the deviation. A control's file matches its reference and must pass.

## Cases

Each verifier carries 10 planted cases plus a clean control, so its Wilson lower bound is
computed over n=10 rather than the vacuous n=2/n=3 the suite originally shipped.

| id                             | verifier           | defect                                                        | expectation |
| ------------------------------ | ------------------ | ------------------------------------------------------------- | ----------- |
| step-dropped-solid             | verify_export_step | single box where the reference is a 2-solid compound           | DETECT      |
| step-unit-lie                  | verify_export_step | 1/10-scale box (vol 6) sold as the mm reference                | DETECT      |
| step-shell-no-solid            | verify_export_step | closed shell with no solid — solids 0 vs 1, volume exact       | DETECT      |
| step-unrefined-fuse            | verify_export_step | stacked halves fused unrefined — faces 10/edges 20, vol exact  | DETECT      |
| step-cut-notch                 | verify_export_step | 2x2x2 corner notch cut out — vol 5992, faces 9, edges 21       | DETECT      |
| step-fused-overlap             | verify_export_step | 5x5x5 block fused on +X — vol 6125, faces 11, edges 24         | DETECT      |
| step-compsolid                 | verify_export_step | stacked halves as a CompSolid — solids 2, volume exact         | DETECT      |
| step-loose-face                | verify_export_step | box compounded with a stray far-off plane — vol 6607, faces 7  | DETECT      |
| step-open-shell                | verify_export_step | shell with the top face dropped — vol 4800, faces 5, solids 0  | DETECT      |
| step-scaled-half-box           | verify_export_step | half-size box (vol 750) sold as the full-scale reference       | DETECT      |
| step-clean-control             | verify_export_step | exact box-10-20-30 round-trip                                  | PASS_CLEAN  |
| stl-hole                       | verify_export_stl  | clean STL with one facet removed (open surface)                | DETECT      |
| stl-flipped-normals            | verify_export_stl  | every facet's winding reversed                                 | DETECT      |
| stl-non-manifold               | verify_export_stl  | duplicated facet -> edge shared by three facets                | DETECT      |
| stl-duplicated-shell           | verify_export_stl  | every facet emitted twice — doubled shell, vol 12000           | DETECT      |
| stl-scaled-mesh                | verify_export_stl  | every coordinate scaled 0.9 — vol 4374 outside the band        | DETECT      |
| stl-missing-face               | verify_export_stl  | the whole top face removed — box open across one side          | DETECT      |
| stl-shifted-vertex             | verify_export_stl  | one facet's first vertex displaced 1 mm — torn corner          | DETECT      |
| stl-appended-degenerate        | verify_export_stl  | zero-area facet appended (three identical vertices)            | DETECT      |
| stl-collapsed-facet            | verify_export_stl  | one facet collapsed in place onto a single vertex              | DETECT      |
| stl-truncated-coordinates      | verify_export_stl  | cylinder mesh rounded to whole mm — 10 collapsed facets        | DETECT      |
| stl-clean-control              | verify_export_stl  | sound tessellated box                                          | PASS_CLEAN  |
| 3mf-type-model-lie             | verify_export_3mf  | open surface written as a solid model object                   | DETECT      |
| 3mf-unit-lie                   | verify_export_3mf  | container re-tagged millimetre -> metre                        | DETECT      |
| 3mf-corrupt-container          | verify_export_3mf  | truncated zip container (lib3mf cannot parse)                  | DETECT      |
| 3mf-missing-model-part         | verify_export_3mf  | container rebuilt without `3D/3dmodel.model`                   | DETECT      |
| 3mf-malformed-transform        | verify_export_3mf  | build-item transform with a non-numeric token                  | DETECT      |
| 3mf-missing-triangle           | verify_export_3mf  | one `<triangle>` element deleted — open, non-manifold          | DETECT      |
| 3mf-corrupt-vertex             | verify_export_3mf  | one vertex pulled x=10 -> x=5 — vol 5000 outside the band      | DETECT      |
| 3mf-duplicated-triangle        | verify_export_3mf  | one `<triangle>` repeated — edges shared by three triangles    | DETECT      |
| 3mf-vertex-index-out-of-range  | verify_export_3mf  | a triangle referencing a vertex index past the array end       | DETECT      |
| 3mf-second-non-manifold-object | verify_export_3mf  | a second mesh object that is a single loose triangle           | DETECT      |
| 3mf-clean-control              | verify_export_3mf  | sound tessellated box                                          | PASS_CLEAN  |

`stl-truncated-coordinates` is built from a cylinder, not the box: the box mesh's vertices are
all integer-valued, so rounding it is a bitwise no-op. Its `case.yaml` therefore records the
cylinder's own source facts, and the mesh volume band derives from the cylinder's area.

## Degenerate-suite guard

`score_export_verify.py` raises `SuiteError` and exits non-zero when any validator has fewer
than `MIN_PLANTED` (10) planted cases or fewer than `MIN_CONTROLS` (1) control, so a thin suite
cannot ship a green-but-vacuous sensitivity again.

## Independent oracles — disagreement is signal

The mesh verifiers run independent oracles per format: `verify_export_stl` runs trimesh
(watertight / winding / volume band / Euler) AND a from-scratch `StdlibStlOracle` (manifold
edge-pairing / winding / non-degeneracy). `verify_export_3mf` runs lib3mf (container / unit /
`IsManifoldAndOriented` / metadata) plus a trimesh geometry layer built from the lib3mf mesh
arrays. Any oracle failing OR any cross-oracle disagreement forces the verdict to FAIL — the
`stl-flipped-normals` case is caught by trimesh flagging a non-`is_volume` mesh where the
stdlib edge-pairing check still passes, so the disagreement itself is the detection. The mesh
volume band derives from the tessellation deflection (never STEP's +-0.1%).

## Building fixtures and scoring

`build_export_fault_fixtures.py` runs under FreeCADCmd and writes each `export.<fmt>` +
`case.yaml`. `score_export_verify.py` scores whichever verifiers the current environment can
run: the mesh verifiers read the committed `.stl`/`.3mf` directly (trimesh + lib3mf, no
FreeCAD), and `verify_export_step` re-imports the committed `.step` (FreeCAD, no oracles). No
single CI leg has both FreeCAD and the oracles, so a run scores its subset and load-merges only
those blocks into `_registry/validators.yaml`, preserving `verify_shape` and any verifier block
it did not touch.
