---
title: 'Mesh-independent centre for shapes without a centre of mass'
type: 'bugfix'
created: '2026-10-08'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** In the GUI, a failed mutation on the kiwibox drawer is never proven by the abort. It falls back to the snapshot restore (close and reopen, 32 to 38 s; UAT run 2026-10-08-02, B1). The fingerprint takes the centre of a shape that has no `CenterOfMass` (a sketch compound) from `shape.BoundBox`. `BoundBox` reads the display mesh when one is attached (`BRepBndLib::Add`, `useTriangulation=true`). The GUI view providers clear and rebuild that mesh on recompute, also on sketch edges shared with downstream solids. So `com` of an unchanged sketch moves (`sma_boss_sketch`: `88.009728` to `88.0`), and `massprops_equal` fails.

**Approach:** Take the fallback centre from `shape.optimalBoundingBox(False, False)`: exact geometry, no triangulation, no tolerance gap. On the drawer copy it did not change under meshing on all 14 fallback sketches, and it equals `BoundBox` on shapes with no mesh, so headless records keep their values.

</frozen-after-approval>

## Implementation Notes

- `src/freecad_buddy/usecases/fingerprint.py` `_center_of_mass`: fallback box changed. Same idiom as `usecases/assertions.py` `_optimal_extents`.
- Test: `tests/infc/test_mutation_protocol.py`, a sketch of two disconnected arcs (a `Compound`, no `CenterOfMass`), coarse `tessellate`, fresh fingerprint `com` must not change. Fails before the fix.
- Not changed: the `bbox` field still uses `BoundBox`. It is in the digest, not in `massprops_equal`, so it does not block the proof.
- Test run: failed before the fix (`com` y `5.496673` became `5.495592` after `tessellate(1.0)`), passes after. `tests/run_tests.py` 810 OK (1 skipped); `pytest tests/external` 1,330 passed; ruff, `gen_schemas --check`, `check_imports` clean.
- GUI check at the failure layer: `run_mutation` with `duct_pilot.Length = 0` on a drawer copy in FreeCAD 1.1.4 GUI gave `RECOMPUTE_ERROR`, `rolled_back_verified`, same document object, no `closeDocument` call, `Length` 6.0, 29.8 s (was `rolled_back_via_snapshot`, 32 to 38 s). Window capture: model intact, tab `drawer-v : 1` (no reopen), no error markers.
- Scope of the "headless records keep their values" claim: measured on the 14 drawer sketches (lines and arcs). On B-spline or Bezier edges, `BoundBox` without a mesh bounds by control points, so the centre of such a sketch can change once. Records are compared within one process, so no stored record is affected.
- Cost: `optimalBoundingBox` 0.116 ms against `BoundBox` 0.122 ms over the 14 sketches; drawer fresh fingerprint 6.0 s headless.
- `benchmarks/_registry/validators.yaml` re-scored (`fingerprint.py` is in their sources): `verify_shape` 11/11 detected, 0/1 false alarm; G2 `assertions` 8/8 and 0/3, `audit_references` 3/3 and 0/6; `fingerprint` and `run_mutation` not scored, as before.
- `design/verification-design.md` §6 pseudo-code comment updated for the fallback box.

## Review Triage Log

- Empty compound now raises in `_center_of_mass` — low: `fingerprint` already raised on that shape (`_quantize` overflow on the void `BoundBox`); deferred with B2.
- Spline claim in Intent — low: true; claim scope recorded above; no stored record affected.
- Digest `bbox` and TNP witness still mesh-dependent — maybe-false (TNP witness, medium if true); deferred.
- GUI fix not verified in GUI — false: verified, see GUI check above.
- Audit record does not name mismatched objects — medium, pre-existing; deferred.
- Assertion in Arrange, test checks `com` only — low: the assertion guards the precondition (the shape takes the fallback); `com` is the only field that moved. Rejected.
- `run_mutation` validator hash misses `usecases/fingerprint.py` — medium, pre-existing; deferred.
- Design docs do not describe `com` for shapes with no solids — low: `verification-design.md` updated; `data-contracts-design.md` did not describe the fallback before either. Rejected.
- Spec state incomplete — fixed by this finalization.
- Docstring sentence reads as history — medium (commenting standard): patched to state the mechanism only.
- Cost not measured — fixed: measured, no cost.
