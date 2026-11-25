# Story 13-15: second red team report (r2)

Scope: fix batch `5115b2ac...e7f9d717` on `story/13-15-tnp-expected-reattachment`; whole Story diff `538db0be...e7f9d717` as context. Code read at `e7f9d717` from a detached copy. Base comparison from a detached copy of `538db0be`. Host `freecadcmd.exe` (FreeCAD 1.1.4) with private `-u`/`-s` cfg files and a private `FREECAD_USER_HOME`. Container not used.

Probe folder: `C:/Users/thuan/AppData/Local/Temp/claude/3d3814eab912640f/17c8e5ee-89aa-4e27-ba05-1fe1774e804a/scratchpad/redteam-13-15b/probes/` (below: `<probes>`). Runner: `sh <probes>/../run.sh <probe>` (a second runner `run2.sh` uses a second cfg folder for parallel runs). `boot.py` imports `tnp_guard` from the `e7f9d717` copy, or from `RT_SRC` (the base copy), and asserts which copy it imported. The copies are removed after this report; to re-run, re-create them with `git worktree add --detach <scratch>/copy e7f9d717` and `<scratch>/base 538db0be`.

## Verdict

**FAIL.** One reproduced high: a FreeCAD pattern-instance index is a positional counter that the detector does not know. A real re-point through `sketch_set_datum` grades `CLEAN` and commits. Before the Story the same edit was `REPOINTED` and rolled back.

## Reproduced

### RT2-1 — high — pattern instance index `;_<n>` (and the unsuffixed instance 2) is positional; a real re-point is excused

- Q row: Q5/Q6 and the Story contract (decision 40 (2), AC2: a real re-point must stay `REPOINTED`).
- Code: `src/freecad_buddy/usecases/tnp_guard.py:65` (`_POSITIONAL_COUNTER` lists `;:M`, `;:MG`, `;:G<n>`/`;:U<n>`, `;:G0#`, `;K<n>`, `;:I<n>`, `;D<hex>`, but not the pattern index), `:249` `_has_positional_counter`, `:281` `_lineage_has_counter`, `:331` `same_element`, applied at `:907`.
- Mechanism (FreeCAD source): `FeatureTransformed.cpp:359-368` names each pattern instance with `Data::indexSuffix(idx++)` as the transform op code. `ElementNamingUtils.cpp:116-123`: index 1 gives `""`, index n >= 2 gives `"_" + n` (`ELEMENT_MAP_INDEX = "_"`, `ElementNamingUtils.h:72`). So instance 2 is named `...;:H,F...` and instance n+1 is named `...;_<n>;:H:3,F...`. The number is the position in the transformation list, not a role. `FeatureLinearPattern.cpp:251-255` builds the list row-major over the two directions (`k = i*N2 + j`), and `FeatureMultiTransform.cpp:175-181` builds it new-outer, old-inner. A change of one count renumbers every instance after the first row, so one name moves to another instance while the old instance still exists. The name has no `;:M`/`;:G<n>`/`;:I<n>` marker, and its lineage (`getElementHistory(recursive=True)`) carries none: `lineage_counter False`.
- Fixture (realistic parametric design): plate Pad from a sketch with `L = 60`, `W = 0.4 * L` (expression); a 4 x 4 x 3 boss; one `LinearPattern` grid of the boss (FreeCAD 1.1 two-direction pattern): Direction = `V_Axis` reversed, Spacing 10, 2 rows; Direction2 = `H_Axis`, Spacing 13, `Occurrences2 = floor(L / 20 mm)` (3 columns). A datum plane (`FlatFace`) and a datum point (`CenterOfMass`) are attached to the top face of boss `_3` (row 2, column 1, at x 3, y 7). One op: `sketch_set_datum` sets `L = 100` through the real bracket (auto-approve on). The column count becomes 5.
- Probe: `<probes>/p13_grid_index.py`. Commands:
  - story: `sh <probes>/../run.sh <probes>/p13_grid_index.py`
  - excuse off (pre-Story rule, `_follows_support` patched to `False`): `EXCUSE_OFF=1 sh <probes>/../run.sh <probes>/p13_grid_index.py`
  - base: `RT_SRC=<scratch>/base/src sh <probes>/../run.sh <probes>/p13_grid_index.py`
- Output at `e7f9d717` (story):
  ```
  boss top faces (xmin,ymin) before [(3.0, 7.0), (3.0, 17.0), (16.0, 7.0), (16.0, 17.0), (29.0, 7.0), (29.0, 17.0)]
    Face31 (3.0, 7.0) #24:1;:G0;XTR;:Hac3:8,F;_3;:H:3,F;:Hac4,F
    Face35 (16.0, 17.0) #24:1;:G0;XTR;:Hac3:8,F;:H,F;:Hac4,F
    Face36 (29.0, 17.0) #24:1;:G0;XTR;:Hac3:8,F;_2;:H:3,F;:Hac4,F
  datum face Face31 #24:1;:G0;XTR;:Hac3:8,F;_3;:H:3,F;:Hac4,F at (3.0, 7.0) lineage_counter False
  point before Vector (5.0, 9.0, 8.0)
  EXCUSE_OFF False status OK tnp_audit CLEAN N2 5 L 100.0 mm
  datum now on Face55 #24:1;:G0;XTR;:Hac3:8,F;_3;:H:3,F;:Hac4,F at (42.0, 17.0)
  boss top faces (xmin,ymin) after [(3.0, 7.0), (3.0, 17.0), (16.0, 7.0), (16.0, 17.0), (29.0, 7.0), (29.0, 17.0), (42.0, 7.0), (42.0, 17.0), (55.0, 7.0), (55.0, 17.0)]
  datum after Vector (0.0, 0.0, 8.0) point after Vector (44.0, 19.0, 8.0)
  ```
  The boss at (3, 7) still exists after the edit. The reference now resolves to a new boss at (42, 17), in the other row. The datum point moved from (5, 9) to (44, 19). Reply `OK`, audit `CLEAN`, the op commits.
- Output with the excuse off (same code, `_follows_support = False`):
  ```
  EXCUSE_OFF True status SPEC_FAILED tnp_audit FLAGGED N2 3 L 60.0 mm
   finding AttachmentSupport REPOINTED 1 BossPlane.AttachmentSupport entry Face31 resolves to a sub-shape whose witness moved: ('Face', 3.0, 7.0, 8.0, 7.0, 11.0, 8.0) -> ('Face', 42.0, 17.0, ...
  ```
- Output at `538db0be` (base):
  ```
  EXCUSE_OFF False status SPEC_FAILED tnp_audit FLAGGED N2 3 L 60.0 mm
   finding BossPlane AttachmentSupport REPOINTED 1 ... ('Face', 3.0, 7.0, 8.0, 7.0, 11.0, 8.0) -> ('Face', 42.0, 17.0, ...
   finding BossPoint AttachmentSupport REPOINTED 1 ... ('Face', 3.0, 7.0, 8.0, 7.0, 11.0, 8.0) -> ('Face', 42.0, 17.0, ...
  ```
  The Story turns a caught re-point into a silent pass.
- Why the bound does not stop it: element shift x +39, y +10; support shift `((0.0, 40.0), (0.0, 16.0), (0.0, 0.0))`. Both inside the support travel.
- Same class, other feature: `<probes>/p14_multitransform.py` (MultiTransform of LinearPattern x then LinearPattern y reversed, x count `floor(L / 20 mm)`; element sweep with `_follows_support`, no bracket): `EXCUSED Face31 -> Face55 (3.0, 7.0, 8.0, 7.0, 11.0, 8.0) -> (42.0, 17.0, 8.0, 46.0, 21.0, 8.0) ... ;_3;:H:3,F` and `EXCUSED Face32 -> Face56 (16.0, 7.0, ...) -> (55.0, 17.0, ...) ... ;_4;:H:3,F`. Command: `sh <probes>/../run.sh <probes>/p14_multitransform.py`.
- Same class, 1D patterns (supporting evidence, weaker because the old instance position no longer exists after the edit): `<probes>/p10_patterns.py`. A `PolarPattern` notch ring with `Occurrences = floor(R / 4 mm)`, R 20 -> 26 (5 -> 6 notches): `EXCUSED Edge60 -> Edge75 (2.733, 13.648, 3.0, 6.537, 14.884, 3.0) -> (5.768, 11.99, 3.0, 9.232, 13.99, 3.0) ... ;:H,E` (instance 2 moves from 72 deg to 60 deg). A linear boss pattern with `Length`/`Occurrences` bound to L: `EXCUSED Face21 -> Face25 (34.0, ...) -> (36.667, ...) ... ;_2;:H:3,F` (the end boss name moves to the third of four).
- Possible direction for the builder (not tested): treat `;_<n>;` (index suffix) and the empty-op instance marker `;:H,` after a transform as positional, the same as `;:I<n>`; or never excuse an element of a `PartDesign::Transformed` target (or one whose lineage passes one) when its count or list changed.

## Not reproduced / low

- RT2-L1 — low — Q7 cost. The lineage walk scales with feature count x reference count. `<probes>/p15_cost.py` (plate + NF pocket features, 200 datum points on elements of the last feature), `NF=80 ND=200`: `snapshot_references` median 0.641 s at `e7f9d717` vs 0.081 s at `538db0be` (x 7.9); `audit_references` 0.692 s vs 0.142 s. `NF=10`: 0.055 s snapshot (story). A mutation runs both, so about +1.1 s per op on this model. No written budget exists, so not a defect; the Q7 row "infc timing unchanged" holds only for shallow models. Commands: `NF=80 ND=200 sh <probes>/../run.sh <probes>/p15_cost.py` and with `RT_SRC=<scratch>/base/src`.
- Lineage check across pass-through features: holds. `<probes>/p11_lineage.py` (RT-1 slotted plate, then N = 1, 2, 4 pass-through Pocket, Pad, Fillet, Chamfer features): `lineage_counter True` on the strip edge in every case, and no strip piece is excused; only end faces and long edges that grow with the plate are excused. `PT_KIND=pocket PT_N=4 sh <probes>/../run.sh <probes>/p11_lineage.py`.
- Lineage truncation: `ElementMap.cpp:1364` logs `invalid name length` and returns tag 0, and `PartFeature.cpp` (recursive loop) then breaks and drops the last `original`. A search of every element of the boss-pattern fixture for a counter in that dropped tail found none (`<probes>/p12_gaps.py`: `B gaps 0`). Not reproduced; a chain that ends at a deleted or other-document object would drop the same tail (not probed).
- `optimalBoundingBox(False, False)`: `<probes>/p16_obb.py`. Vertex, straight edge, planar face, solid, ellipse, sphere face, degenerate cone edge and infinite plane: equal to `BoundBox`. B-spline face, sphere seam and a rotated solid: box grows by 1e-7 on some sides (uniform on both sides of an audit, so the delta cancels). Empty compound and null shape: `RuntimeError('Bnd_Box is void')` -> witness `None`; `BoundBox` gave an equal void box on both sides before, so `_witness_moved` gives the same "not moved" result. Cost per call equal (2000 calls: 0.009 s vs 0.010 s). No excused re-point and no faked test found.
- Story positives at `e7f9d717`: `infc.test_tnp_guard` + `infc.test_feature_tools` (includes `SupportFollowTest` datum on Pad top face for Length and sketch width, external geometry, `Pad.Profile`, `Fillet.Base` Edge4, the written-baseline and `feature_set_parameters` e2e cases): `Ran 286 tests ... OK`. Command: `sh <probes>/../run.sh <probes>/run_subset.py` from the copy.
- Other feature types swept for excused moves after one L or Length edit (`<probes>/p17_misc.py`, `p10_patterns.py`): Thickness, Part::Cut (box minus two cylinders), multi-edge Fillet (probe reference broke on a Pad rename, no data), boss LinearPattern, PolarPattern. Apart from the pattern-index cases under RT2-1, every excused element is an end face or a long edge or face that grows with the support. Hole with several positions, Pocket through all, and multi-wire sketches: not probed.
- RT-1 regression check: `<probes>/p6c_datum_point.py` at `e7f9d717` -> `status SPEC_FAILED tnp_audit FLAGGED`, finding `REPOINTED`. The RT-1 fix holds.

## Not run

- Container, E2E over MCP HTTP: not used (verifier owns them). RT2-1 runs through the real `sketch_set_datum` bracket on host freecadcmd.
- Cross-document links and `App::Link` targets in the lineage walk.
