# G0 fault-injection suite

Planted-defect + clean-control fixtures that validate `verify_shape` **before** it exists
(AD-19 entry gate). This story lands and binds the suite; the sensitivity/false-alarm run is
Story 1.6 (recorded as `last_run: null` in `_registry/validators.yaml`).

## Assertion vocabulary — Phase-0 forward-declared reserved set (CLOSED)

`contracts/assertions.py` defers the full assertion vocabulary to Phase 3. This suite
therefore uses a small **closed, forward-declared** set of `fn` names that the Story-1.6
`verify_shape` validator will bind. The Story-0 gate runner does **not** resolve or execute
these `fn`s (there is no bridge yet); they are the contract 1.6 binds:

| `fn`                | measures                     |
| ------------------- | ---------------------------- |
| `expect_volume`     | solid volume (mm³)           |
| `expect_bbox`       | axis-aligned bbox `[X,Y,Z]`  |
| `expect_solid_count`| number of `Solids`           |
| `expect_valid`      | OCCT `Shape.isValid()`       |
| `expect_watertight` | closed/manifold solid shell  |

## Detection rule — assertions encode the REFERENCE, not the defect

Each planted-defect `case.yaml` asserts the value a **correct** shape yields for the targeted
property. The fixture carries a real geometric defect that violates that property, so a
validator measuring the property and comparing to the assertion **detects the deviation**.
An assertion is never hand-set to the defective value (that would make the case pass on the
defect). Fixtures are built by `build_fault_fixtures.py` under FreeCADCmd.

## Cases

| id                              | defect                                            | primary assertion (reference) |
| ------------------------------- | ------------------------------------------------- | ----------------------------- |
| wrong-volume                    | box 12×20×30 (vol 7200)                            | `expect_volume: 6000`         |
| wrong-bbox                      | box Z=60                                           | `expect_bbox: [10,20,30]`     |
| non-watertight-open-shell       | single-face open shell (0 solids)                 | `expect_watertight: true`     |
| degenerate-face                 | collinear polygon → zero-area, `isValid()==False` | `expect_valid: true`          |
| zero-volume-lamina              | planar 10×10 face (vol 0)                          | `expect_volume: 100`          |
| dropped-solid                   | one box where reference compound has 2            | `expect_solid_count: 2`       |
| wrong-solid-count               | three boxes where reference compound has 2        | `expect_solid_count: 2`       |
| unit-lie                        | 1/10-scale box (1×2×3, vol 6) sold as mm          | `expect_volume: 6000`         |
| invalid-self-intersecting-solid | bowtie profile extruded → `isValid()==False`      | `expect_valid: true`          |
| self-intersecting-compound      | 2 overlapping boxes left as a 2-solid compound    | `expect_solid_count: 1`       |
| non-manifold                    | 3 faces sharing one edge (adjacency 3), open      | `expect_watertight: true`     |
| clean-control                   | exact box-10-20-30 rebuild                        | PASS_CLEAN (all reference)    |

`invalid-self-intersecting-solid` replaces a signed-volume "negative-volume" case: OCCT
signed volume is version-fragile across the CI legs, so detection is re-targeted to the
robust `isValid()==False` signal (verified under FreeCAD 1.1: the bowtie extrusion is a
single solid that fails `isValid()`).
