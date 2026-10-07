---
title: 'Mass properties that tell shapes apart'
type: 'bugfix'
created: '2026-10-06'
status: 'done'
baseline_commit: '1b71e76cb8906c29f6cf4f68780f1cca64934a93'
route: 'dispatch'
review_loop_iteration: 2
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/data-contracts-design.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `massprops_equal` is the identity check in 4 of 5 comparison sites, but it is blind in two ways. A `Compound` shape has no `PrincipalProperties` and no `CenterOfMass`, so 74 of 144 objects on `kiwibox-drawer.FCStd` record `principal_moments: [0, 0, 0]` and a tessellation-derived bbox centre as `com`. Principal moments are eigenvalues, so they do not change under a rotation or mirror about the centre of mass.

**Approach:** For a shape with solids, compute volume, centre of mass, inertia tensor and principal moments from its solids: rebuild each solid's tensor from its `PrincipalProperties`, combine the solids with the parallel-axis rule, and take the eigenvalues of the combined tensor. Add `inertia` (6 tensor components about the COM, document axes) to `MassProps` as an optional field of `fcb.fingerprint/1` (AD-28), and add it to the `massprops_equal` invariants. Calibrate its step on a copy of the drawer.

**Decisions (human, 2026-10-07):**
- D1 — Cost: 2 integrations per solid, `CenterOfMass` and `PrincipalProperties`. The solid's tensor about its COM is `Σk λk·ak·akᵀ` (`Moments` λ, unit `First/Second/ThirdAxisOfInertia` a). Its volume is `λk / rk²` (`RadiusOfGyration` r) on the axis with the largest `rk`; 0 when every `rk` is 0. `MatrixOfInertia` and `Solid.Volume` are not read. Measured result (exact method): 4.18 s before, 7.32 s with 3 integrations; record the new median.
- D2 — Step: `principal_moments` and `inertia` round to a per-object step `10^(floor(log10(s) + 1e-9) − 9)`, `s` = largest absolute diagonal component of that object's tensor; when `s` is 0 or not finite, the step is `Q`. `volume`, `area`, `com`, `bbox` keep `Q`; the record's `quantum` stays `Q`. A fixed absolute step is rejected: it hides a rotation of a small part. The `+ 1e-9` (2026-10-07) moves the step boundary off exact powers of ten, which round dimensions produce (a 6 x 10 x 10 mm box has `s = 10000.0`), to `s = 10^k·(1 − 2.3e-9)`; without it, last-bit jitter flips the step 10x.
- D4 (2026-10-07) — `usecases/transaction.py` `_prove_rollback` docstring and `tests/infc/test_document_undo.py:433` wording may change to list `inertia`; no code change in either. `_check_expectation` in `documents.py` stays as is.
- D3 — Documents: correct spine AD-6, `verification-design.md` (§2.2 sketch, §8 step rule) and `data-contracts-design.md` §9 to state D2; update the `_matches_pre_op` docstring in `usecases/documents.py` to list `inertia` (docstring only).

## Boundaries & Constraints

**Always:**
- One code path for every shape that has solids, a single `Solid` included. `area` stays `shape.Area`; `bbox` stays `shape.BoundBox`.
- A shape with no solids (sketch, wire, face, shell) keeps today's `principal_moments` and `com` rules; its `inertia` is the shape's own `MatrixOfInertia` when exposed, else six zeros.
- Null-shape entries get `inertia: [0.0] * 6`.
- 2 integrations per solid plus `shape.Area` (D1); Story 11.4 depends on fingerprint cost.
- Rings: `contracts/` stays stdlib-only; FreeCAD stays lazily imported in `usecases/fingerprint.py`.

**Never:**
- No change to `preview.py`, `screenshot.py`, the code of `transaction.py` and `documents.py` (D3 and D4 allow docstrings), the digest rule, or the wire projection (Stories 11.2 and 11.4).
- No numpy or other third-party import.
- Never edit the original `kiwibox-drawer.FCStd`; probe a copy in the scratchpad.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Compound of solids | 2 cubes 10 mm at (0,0,0) and (20,20,0) | `com` (15,15,5); `inertia` Ixx = Iyy = 2·(1000·200/12 + 1000·100), Izz = 2·(1000·200/12 + 1000·200), Ixy = −200000, Ixz = Iyz = 0; moments non-zero | N/A |
| Rotation | asymmetric solid rotated 90° about its COM | `principal_moments` equal, `inertia` differs, `massprops_equal` False | N/A |
| Mirror | L-shaped solid (non-zero product of inertia) mirrored through a plane through its COM | volume, area, com equal; `inertia` differs; `massprops_equal` False | N/A |
| Symmetric inertia | cube rotated 90° about its COM | `massprops_equal` True: documented limit | N/A |
| Old record | one side has no `inertia` | `massprops_equal` False (never equal by omission) | N/A |
| Zero-volume solids | solids with total volume 0 | `com` falls back to today's rule; no division by zero | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/fingerprint.py:44-62` `_principal_moments` -- replace with solid-based path; keep it for the no-solids case. `:94-108` `_center_of_mass` -- keep as the no-solids / zero-volume fallback. `:111-127` `_massprops` -- add `inertia`, call the solid path. `:136-145` `_null_massprops` -- add zeros. `Q = 1e-6` and `_quantize` reused.
- `src/freecad_buddy/contracts/fingerprint.py:13-19` `MassProps` -- `inertia: NotRequired[list[float]]`. `:61-65` `_INVARIANT_MASSPROP_KEYS` and its comment, `:68-87` docstring -- add `inertia`.
- `scripts/gen_schemas.py:108` -- required list unchanged (inertia optional). Regenerate `src/freecad_buddy/contracts/jsonschema/fingerprint.schema.json` (and any schema embedding `MassProps`).
- FreeCAD API (`docs/references/FreeCAD/src/Mod/Part/App/TopoShapeSolidPyImp.cpp:104-132`): `Solid.MatrixOfInertia` is the OCC `GProp_GProps` matrix about the solid's own COM in absolute axes, as `Base.Matrix` (`A11..A33`); off-diagonals are the negated products of inertia. `Compound` exposes no `CenterOfMass`/`MatrixOfInertia`/`PrincipalProperties` (`TopoShape*.pyi`).
- `tests/infc/test_verify_tools.py:51` `FingerprintTest` -- add AC tests here (fixture `_DocFixture`, `Part::Feature` with assigned `Shape`).
- `tests/external/test_fingerprint_contract.py:38-60` -- null entry gains `inertia`. `tests/external/test_contracts.py:526-560` -- add pure `massprops_equal` tests.
- Validators whose `validator_sha` covers changed files (`benchmarks/runner.py:96-125`): `verify_shape` (`benchmarks/g0/fault-injection/score_verify_shape.py`), `fingerprint` and `run_mutation` (`benchmarks/g2/fault-injection/score_g2_infc.py`). Registry: `benchmarks/_registry/validators.yaml`.
- Drawer: `D:/Work/3D Printers/Ender 3V2 - Klipper/cad/kiwibox-drawer.FCStd` (read-only; copy it). FreeCADCmd: `C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe`.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/contracts/fingerprint.py` -- add `inertia` field and invariant key; update comment and docstring -- AC2.
- [x] `src/freecad_buddy/usecases/fingerprint.py` -- D1 per-solid tensor from `PrincipalProperties`, D2 per-object step; solid-based volume/com/tensor/moments, eigenvalues of a symmetric 3x3 by cyclic Jacobi rotations, sorted descending (Design Notes), `inertia` order `[Ixx, Iyy, Izz, Ixy, Ixz, Iyz]` as OCC matrix elements, quantized; module and function docstrings state the symmetric-inertia limit -- AC1, AC2, AC3.
- [x] `tests/infc/test_verify_tools.py` -- tests for the I/O matrix rows (compound analytic values, rotation, mirror, symmetric limit, zero moments fail) -- AC1, AC3.
- [x] `tests/external/test_contracts.py`, `tests/external/test_fingerprint_contract.py` -- inertia mismatch and missing-inertia cases; null entry -- AC2.
- [x] `src/freecad_buddy/contracts/jsonschema/` -- regenerate with `scripts/gen_schemas.py`; drift check green.
- [x] Scratchpad probe (not committed), re-run after D1/D2 -- on a copy of the drawer: fingerprint, open transaction, change `duct_pilot.Length`, recompute, abort, recompute, fingerprint; report per-object jitter of every invariant and fingerprint time before/after this change -- AC4.
- [x] Calibrate -- apply D2; the tuned exponent 9 gets a comment with the mechanism and the measured jitter; confirm AC4 on the drawer copy and record the D1 fingerprint median -- AC4.
- [x] `benchmarks/_registry/validators.yaml` -- re-score again after D1/D2; `verify_shape`, `fingerprint`, `run_mutation`; each still meets sensitivity ≥ 95 %, false alarm ≤ 5 %, and every G2 case fails or flags as before.

- [x] Design documents and `usecases/documents.py` docstring -- D3. `verification-design.md` step pseudo-code checks every diagonal component for finiteness (as the code does), shows the no-solids branch and the Jacobi eigenvalues, and states that the exponent is recalibrated after a FreeCAD or OCCT version change and that every stored digest changes with this story.
- [x] `tests/external/test_fingerprint_contract.py` -- pure specs for `_eigenvalues` against analytic values: a rotated tensor with all three off-diagonals non-zero, a degenerate pair (cylinder-like, `(a, a, b)` rotated), a triple (`(a, a, a)` rotated); each perturbed by ±2e-16 relative over many draws stays within 1e-5 of the step; and `_principal_tensor` with fake props.
- [x] `tests/infc/test_verify_tools.py` -- add: the compound test asserts each recorded `inertia` and `principal_moments` value is already a multiple of `_tensor_step` (re-quantizing returns it unchanged); the small-part rotation uses a box of about 0.1 x 0.05 x 0.025 mm, whose Ixx/Iyy difference a fixed `Q` or 0.1 step rounds to zero, with a correct comment; a solid tilted out of the z axis whose `principal_moments` match `sorted(PrincipalProperties["Moments"], reverse=True)` within the step; a tilted cylinder whose `principal_moments` match OCC's within the step; a face (`Part.makePlane(20, 10)`) rotated 90 deg about its centre is not `massprops_equal` and has non-zero `inertia`.
- [x] Loop-2 fixes -- `_tensor_step` per D2 with a comment on the boundary shift; a test that a solid with `s` exactly a power of ten (6 x 10 x 10 mm box) and the same tensor with `s` one ulp below give the same step. `_eigenvalues` convergence check multiplies (`x * x`), never `** 2`, which raises `OverflowError` above 1.34e154. `_principal_tensor` comment says why it reads `PrincipalProperties` and not `MatrixOfInertia`/`Volume` (one integration fewer per solid, 7.32 s to 5.81 s on the drawer). Contract comment and `data-contracts-design.md` state that off-diagonals are the negated products of inertia (`Ixy = −∫xy dm`). Docstrings, spine AD-6 Obligation and `verification-design.md` state the full limit: a mirror through a plane through the COM normal to a principal axis, any rotation of a solid with three equal moments, and a rotation of an axisymmetric part about its axis leave the tensor unchanged. `verification-design.md` says a sketch is covered only when its shape is a single wire (a multi-wire or point-bearing sketch is a compound and records zeros), and puts the `# 6 values about the COM` comment on the tensor line. D4 docstrings. Every new test carries `# Arrange` / `# Act` / `# Assert` phases and a `test_should_<outcome>_when_<condition>` name.

**Acceptance Criteria:**
- Given a non-empty compound of solids, when `fingerprint()` runs, then `principal_moments` are non-zero and a `tests/infc/` test fails if they are zero.
- Given any shape, then `MassProps.inertia` holds the 6 tensor components about the COM from its solids, and `massprops_equal` compares it.
- Given an asymmetric solid rotated 90° about its COM, and an L-shaped solid mirrored through a plane through its COM, then `massprops_equal(before, after)` is False for both.
- Given a copy of `kiwibox-drawer.FCStd`, when one feature is changed in a transaction, aborted and recomputed, then `massprops_equal(before, after)` is True on every object, and Implementation Notes record the step and the measured jitter.

## Implementation Notes

- **Step (D2):** `principal_moments` and `inertia` round to `_tensor_step(tensor)` = `10^(floor(log10(s) + 1e-9) − INERTIA_DIGITS)`, `INERTIA_DIGITS = 9`, `s` the largest absolute diagonal component; `Q` when any diagonal component is not finite or `s` is 0. `volume`, `area`, `com`, `bbox` keep `Q = 1e-6`; `quantum` stays `Q`. Example: `riser_zone` (`s` about 1.7e8) gets step 0.1; a 2 x 1 x 0.5 mm box gets 1e-10. Boundary shift: `log10` of one ulp below 10000.0 still rounds to 4.0, but 1e-15 relative below (5e-16 is enough) rounds below 4.0, so without the `+ 1e-9` the step of a 6 x 10 x 10 mm box drops from 1e-5 to 1e-6 under last-bit jitter. On the drawer copy no object changes step under the shift; the closest `s` to a power of ten is `front_plate_sketch` (`s` = 1.027e6, 0.012 from an integer in log10).
- **Per-solid path (D1):** `CenterOfMass` + `PrincipalProperties` per solid. The rebuilt tensor matches `Solid.MatrixOfInertia` within 2.2e-16 of `s`, and `λk / rk²` matches `Solid.Volume` within 2e-16 relative (box, tilted box, L, cube, cylinder, tilted cylinder, sphere, 0.5 mm box). An open solid gives `rk` = 0, so volume 0.
- **Measured jitter** (copy of `kiwibox-drawer.FCStd`, FreeCAD 1.1.4, `UndoMode` 1, change `duct_pilot.Length` 6 -> 7 mm, recompute, abort, recompute; 144 objects, 34 with new B-rep bytes). Raw (unquantized) maximum difference per invariant:

  | Invariant | Max jitter | Relative | Objects | Worst |
  |---|---|---|---|---|
  | volume | 7.3e-12 | 1.4e-16 | 1 | riser_zone |
  | area | 1.8e-12 | 1.4e-16 | 1 | riser_tongue |
  | com | 1.4e-14 | 2.1e-16 | 1 | riser_zone |
  | principal_moments | 1.8e-7 | 1.1e-15 | 2 | riser_zone |
  | inertia | 1.8e-7 | 1.1e-15 | 4 | riser_zone |

  Re-run with the loop-2 code gives the same values. Same maxima over 12 cycles (3 each on `duct_pilot`, `locating_lip`, `riser_zone`, `tray_rib_seam_chamfer`). Largest jitter / per-object step: 1.8e-6 (moments, Jacobi) and 1.8e-6 (inertia), both `riser_zone` at step 0.1; area at `Q` has 1.8e-6. `massprops_equal` is True on every object after each of the 12 cycles. With a fixed 1e-6 step the `riser_zone` moments crossed a rounding boundary.
- **Snapshot path:** `saveCopy` + reopen of the drawer copy gives `massprops_equal` True on every object.
- **Fingerprint time** (median of 5, headless, drawer copy): 4.16 s before this story, 7.32 s with 3 integrations per solid, 5.81 s with D1 and Jacobi eigenvalues. Re-measured with the loop-2 code in a slower machine state, alternating runs: before this story 6.99 s and 6.57 s; this story 9.94 s and 9.97 s (ratio 1.45, against 1.40 above); the loop-2 code without its two code fixes 9.55 s against 10.13 s in the same pair, inside the 9.0 to 10.5 s run-to-run spread. The loop-2 fixes add no measurable cost. All 76 compounds on the drawer hold one solid: before, a compound cost `Volume` + `Area`; now `CenterOfMass` + `PrincipalProperties` + `Area`. A `Solid` cost `Volume` + `CenterOfMass` + `PrincipalProperties` + `Area` before and costs one integration less now. Zero-moment objects with volume > 0: 61 before, 0 after.
- **Eigenvalues (loop 1):** cyclic Jacobi, at most 6 sweeps for distinct or paired moments over 20,000 random draws; with three equal moments (sphere, tilted cube) the off-diagonals stop shrinking below one ulp and the 50-sweep bound ends the loop, with the diagonal already within 6e-7 of the step. Under ±2e-16 relative noise the error stays within 1e-5 of the step; the old closed form gave 0.858 against a 1e-6 bound.
- **Validators** (re-scored on the loop-2 code): `verify_shape` 11/11 detected, 0/1 false alarm (as before). G2: `assertions` 8/8 and 0/3, `audit_references` 3/3 and 0/6, per-case outcomes identical to before. `fingerprint` and `run_mutation` stay not scored (no fault case targets `fingerprint`; both `run_mutation` planted cases are not driveable on 1.1), as before.

## Spec Change Log

- **Loop 2 (review, 2026-10-07).** Trigger: pass-2 review found the D2 step flips at exact powers of ten (intent_gap, human decided D2 boundary shift and D4 docstring scope). Amended: frozen D2 and D4 (human), Never bullet, the `Loop-2 fixes` task. Known-bad state avoided: a no-op recompute on a round-dimension part changing its recorded moments and digest. KEEP: the whole loop-2 diff (`C:/Users/thuan/AppData/Local/Temp/claude/D--Work-Personal-Sources-freecad-buddy/07a79862-9e59-45ab-90f1-be3118a5141b/scratchpad/keep-11-1-loop2.patch`), including Jacobi eigenvalues, the loop-1 tests, D3 document edits and Implementation Notes. Re-apply it, then change only what the `Loop-2 fixes` task names; re-run AC4 and the validator re-score because `fingerprint.py` changes.

- **Loop 1 (review, 2026-10-07).** Trigger: edge-case review found the trigonometric closed-form eigenvalue routine unstable for a repeated moment pair; probe confirmed 0.86 error against a 0.1 step, so a cylinder or revolved part would fail the rollback proof and `massprops_equal` after a no-op recompute. Amended: Design Notes (Jacobi eigenvalues), the `usecases/fingerprint.py` task, new test tasks (eigenvalue specs, step assertion, tiny-part rotation, tilted and axisymmetric moments, face rotation), and the D3 documents task. Known-bad state avoided: a closed form that is exact on distinct moments and wrong on axisymmetric parts, with tests that cannot see it. KEEP: everything else in the loop-1 diff (`C:/Users/thuan/AppData/Local/Temp/claude/D--Work-Personal-Sources-freecad-buddy/07a79862-9e59-45ab-90f1-be3118a5141b/scratchpad/keep-11-1-loop1.patch`): the `MassProps.inertia` contract and `massprops_equal` rule (missing `inertia` never equal), `_principal_tensor` (D1), `_tensor_step` with the all-components finiteness check (D2), `_solid_mass_properties` parallel-axis combination, the no-solids and null-shape branches, regenerated schemas, the existing `MassPropsTest` and external tests, the D3 document edits, and the Implementation Notes measurements. Re-apply that patch, then change only what this entry names.

## Review Triage Log

- Pass 3: a 180 deg rotation about a principal axis through the COM and a point reflection through the COM leave the tensor unchanged on any solid; limit texts omit them (blind) -- low, patch: `R = diag(1, -1, -1)` and `R = -E` give `R·T·Rᵀ = T`; add to the limit texts and a known-limit test.
- Pass 3: the no-solids compound limit (multi-wire sketch records zeros) is stated only in `verification-design.md` (blind) -- low, patch: add to the `massprops_equal` Limit and the spine AD-6 Obligation.
- Pass 3: overflow test asserts only `len == 3` (blind) -- low, patch: assert the values.
- Pass 3: no test pins where the shifted step boundary sits (blind) -- low, patch: `s = 10000·(1 − 1e-8)` must give `1e-6`.
- Pass 3: `_quantize` docstring still says "fixed" step (blind) -- low, patch.
- Pass 3: small-part rotation test does not assert its step or which field changed (blind) -- low, patch.
- Pass 3: no-solids branch keeps OCC's unsorted `Moments` order at the finer per-object step (blind) -- low, rejected: an order swap needs near-equal but unequal moments on a non-solid shape, and the fix changes the frozen no-solids rule.
- Pass 3: missing `inertia` returns False instead of raising like a serializer-tag mismatch (blind) -- false: frozen I/O matrix row "Old record" requires `massprops_equal` False.
- Pass 3: fingerprint cost not recorded against AD-24 (blind) -- low, rejected: measured in Implementation Notes; Story 11.4 owns per-mutation timing.
- Pass 3: recalibration trigger and exponent not recorded in the record (blind) -- carried low, rejected (pass 2); regression test carried deferred.
- Pass 3: zero total volume falls back to the bbox centre, which shifts after a render (edge-case) -- low, rejected: before this story every compound used the bbox centre; the fallback now covers only zero-volume solids.
- Pass 3: `PrincipalProperties` missing or not a dict aborts `fingerprint()` (edge-case) -- false: `TopoShapeSolidPy::getPrincipalProperties` (`TopoShapeSolidPyImp.cpp:147-184`) always returns the dict on FreeCAD 1.1, the only supported build.
- Pass 3: carried -- `_check_expectation` guard (D4, rejected), calibration regression test (deferred), subnormal `s` (false), mixed compounds (rejected), opposite-sign volumes (rejected), no-solid compounds record zeros (deferred), AC2 claim (rejected).

- Pass 2: tensor step flips 10x when `s` is exactly a power of ten, which round dimensions produce (blind; edge-case same claim) -- medium, intent_gap: verified `s = 10000.0` for a 6 x 10 x 10 mm box, step `1e-5` vs `1e-6` one ulp below; supersedes the pass-1 rejection, which assumed such `s` values are rare. Human decided D2 boundary shift.
- Pass 2: `_check_expectation` accepts a record without `inertia` (verification-gap, edge-case, blind) -- carried low, rejected; human confirmed in D4 that the guard stays.
- Pass 2: `_prove_rollback` docstring (`transaction.py:348`) and `test_document_undo.py:433` omit `inertia` (verification-gap) -- low, D4 allows the docstring fix; loop-2 task.
- Pass 2: `** 2` in the Jacobi convergence check raises `OverflowError` for an off-diagonal above 1.34e154 (edge-case) -- low, loop-2 task: Python float `**` raises where `*` returns inf; one-token fix.
- Pass 2: mirror and rotation limits understated as "a cube turned 90 degrees" (blind) -- low, loop-2 task: a mirror through a principal plane leaves `T = M·T·Mᵀ` unchanged.
- Pass 2: contract does not state the off-diagonal sign (blind) -- low, loop-2 task: compound test expects `-200000.0` for Ixy.
- Pass 2: no comment on why D1 reads `PrincipalProperties` (blind) -- low, loop-2 task.
- Pass 2: design implies sketches are covered by the no-solids tensor, but a multi-wire sketch is a compound (blind) -- low, loop-2 task: `SketchObject.cpp:412,428` builds a compound when vertices exist.
- Pass 2: pseudo-code comment on the wrong line (blind) -- low, loop-2 task.
- Pass 2: new tests lack Arrange/Act/Assert phases and `should..when` names (blind) -- low, loop-2 task: CLAUDE.md §9; `test_verify_tools.py` already has `test_should_` tests.
- Pass 2: schema id stays `fcb.fingerprint/1` though every digest changes (blind) -- low, rejected: frozen intent makes `inertia` additive under `/1`; digests are compared within a session, and `verification-design.md` states the change.
- Pass 2: `query_mass_properties` volume (`shape.Volume`) and the fingerprint volume (`λ/r²`) can differ in the last bits (blind) -- low, rejected: nothing compares the two.
- Pass 2: `volume`/`area` at absolute `Q` cross rounding boundaries above about 1e9 mm³ (blind) -- low, defer: pre-existing rule; no part that size in scope today.
- Pass 2: exponent 9 written in five places; no test catches kernel jitter growth (blind) -- low, defer for the regression test (needs a jittering large part fixture); rejected for the five places: code holds one constant, the documents state the decision.
- Pass 2: carried -- subnormal `s` (false), opposite-sign volumes (rejected), compound of faces or wire sketches records zeros (deferred), mixed compounds (rejected), validators sensitivity claim (rejected), `fingerprint` unscored (deferred).

- Eigenvalue closed form unstable for a repeated moment pair (edge-case; also compound-test pair flakiness, calibration claim not covering axisymmetric parts, blind `p == 0` division guard) -- high, bad_spec: probe on `(1.7e8, 1.7e8, 0.9e8)` rotated, ±2e-16 noise, error 0.86 vs step 0.1; Jacobi 1.5e-6.
- Compound test `delta=step` cannot see a dropped step argument (verification-gap) -- medium, folded into the loop-1 test tasks.
- Small-part rotation test passes under a fixed 0.1 step; comment wrong (verification-gap, blind) -- medium, folded into the loop-1 test tasks: values 0.1042/0.3542 round to (0.1, 0.4) and still differ.
- `_eigenvalues` never checked with non-zero Ixz/Iyz; no pure spec (verification-gap, blind) -- medium, folded into the loop-1 test tasks.
- No-solids `inertia` branch untested (verification-gap, blind) -- medium, folded into the loop-1 test tasks.
- Design pseudo-code uses `max` before the finiteness check and omits the no-solids branch (blind) -- low, folded into the D3 task.
- Documents do not say every stored digest changes, nor when to recalibrate (blind) -- low, folded into the D3 task.
- `document_undo` with a pre-upgrade record lacking `inertia` reports `matches_pre_op: false` (blind) -- low, rejected: needs a client holding a full record across a bridge upgrade; the fix adds a guard in `documents.py` code.
- NaN `RadiusOfGyration` position changes the volume (blind) -- maybe-false, rejected: no shape shown to produce NaN radii (the open solid gives 0); at most low.
- Mixed compound (solids + loose faces): moving a loose face is no longer seen by `massprops_equal` (blind) -- low, rejected: rare in PartDesign output, the digest still changes on the abort path, and the fix adds a second combination path.
- Record's `quantum` does not state the tensor step; step jumps 10x when `s` crosses a power of ten (blind, edge-case) -- low, rejected: needs `s` within about 1e-15 relative of a power of ten; the step is derivable from the recorded tensor; the fix adds hysteresis.
- Subnormal `s` makes the step underflow to 0 (edge-case) -- false: needs `s` below about 1e-306 mm^5, a part near 1e-61 mm, below FreeCAD's 1e-7 mm tolerance.
- Opposite-sign solid volumes cancel to a tiny total (edge-case) -- maybe-false, rejected: no FreeCAD route to a compound of a solid and its reversed copy shown; at most low.
- Compound of faces or shells with no solids keeps zero inertia, rotation invisible (edge-case) -- medium, defer: pre-existing (moments were zero before), spec keeps today's no-solids rule.
- No G2 fault case plants a rotation or mirror about the COM (blind) -- low, defer: coverage is by infc tests; a fault case is new suite work.
- Spec task says `fingerprint` and `run_mutation` meet sensitivity >= 95 % while both stay not scored (edge-case) -- rejected: fix edits this spec; reported to the human.

## Design Notes

Per solid (D1): `M = Σk λk·ak·akᵀ` about its own COM, `v = λk / rk²`. Combination for solids `i` with volume `v`, centre `c`, matrix `M` (density 1, so mass = volume): `V = Σv`, `C = Σ v·c / V`, `d = c − C`, `T = Σ [M + v·(|d|²·E − d·dᵀ)]`. `Σk λk·ak·akᵀ` is the tensor `∫(|r|²·E − r·rᵀ)`, the same matrix OCC's `MatrixOfInertia` returns (off-diagonals are the negated products of inertia), so no sign change; the `−d·dᵀ` term follows the same convention. Test: rebuilt `M` equals `Solid.MatrixOfInertia` within float noise. Principal moments = eigenvalues of `T` by cyclic Jacobi rotations (rotate out `T[p][q]` for `(0,1), (0,2), (1,2)` until the off-diagonal sum of squares is 0, at most 50 sweeps), sorted descending. Not the trigonometric closed form: with two equal moments (cylinder, revolved part) its `acos` near ±1 turns 2e-16 relative noise into an error of up to 0.86 on moments of 1.7e8 (step 0.1); Jacobi stays within 1.5e-6 on the same probe (repeated pair, triple, distinct).

## Verification

**Commands:**
- `"C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/run_tests.py` -- expected: all infc tests pass, new fingerprint tests included.
- `uv run pytest tests/external` -- expected: green.
- `uv run python scripts/gen_schemas.py --check` -- expected: no drift.
- `uv run python scripts/check_imports.py` -- expected: ring rules hold.
- `uv run ruff check .` -- expected: clean.
