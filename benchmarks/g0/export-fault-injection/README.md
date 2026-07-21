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

| id                     | verifier            | defect                                              | expectation |
| ---------------------- | ------------------- | --------------------------------------------------- | ----------- |
| step-dropped-solid     | verify_export_step  | single box where the reference is a 2-solid compound | DETECT      |
| step-unit-lie          | verify_export_step  | 1/10-scale box (vol 6) sold as the mm reference      | DETECT      |
| step-clean-control     | verify_export_step  | exact box-10-20-30 round-trip                        | PASS_CLEAN  |
| stl-hole               | verify_export_stl   | clean STL with one facet removed (open surface)      | DETECT      |
| stl-flipped-normals    | verify_export_stl   | every facet's winding reversed                       | DETECT      |
| stl-non-manifold       | verify_export_stl   | duplicated facet -> edge shared by three facets      | DETECT      |
| stl-clean-control      | verify_export_stl   | sound tessellated box                                | PASS_CLEAN  |
| 3mf-type-model-lie     | verify_export_3mf   | open surface written as a solid model object         | DETECT      |
| 3mf-unit-lie           | verify_export_3mf   | container re-tagged millimetre -> metre              | DETECT      |
| 3mf-corrupt-container  | verify_export_3mf   | truncated zip container (lib3mf cannot parse)        | DETECT      |
| 3mf-clean-control      | verify_export_3mf   | sound tessellated box                                | PASS_CLEAN  |

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
