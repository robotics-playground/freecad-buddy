---
title: 'Story 4.2 — Assertion Primitives'
type: 'feature'
epic: 4
story: '4-2-assertion-primitives'
created: '2026-09-13'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '273413a46692d95c17c1e2f613ec3b3f57bbbd16'
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Only 5 of the 11 AD-13 assertion primitives exist, and the anchor frame is not
implemented at all. Measured directly: `benchmarks/harness/assertions.py` implements
`is_valid_solid`, `count_cylindrical_holes`, `hole_spacing`, `hole_through`, `expect_volume` (plus
three declared G2 extensions), while `hole_diameter`, `hole_position`, `distance_between`,
`angle_between`, `expect_bbox` and `expect_extent` are absent. Separately (DW-115), 40 benchmark
cases declare `assertions.anchor_frame` and **no code reads it** — every measurement runs in global
coordinates. Story 4.1's G3 cases cite the missing names, so they grade `INVALID_INPUT` today.

**Approach:** Complete the closed §7.2 vocabulary in `benchmarks/harness/assertions.py` and
implement the anchor-frame resolver that every measurement transforms into before comparing. The
frame work is the load-bearing half: without it `expect_bbox` and `hole_position` measure the wrong
thing on any part that is not axis-aligned, which is exactly what Phase 3's real specs produce.

## Boundaries & Constraints

**Always:**
- Extend `benchmarks/harness/assertions.py`; do not fork it. The module is FreeCAD-import-free and
  reads only attributes off the objects it is handed — keep that property, it is what lets the
  in-FreeCAD scorer and the external harness share one implementation.
- Every new primitive returns through the existing `_check(...)` helper so the result shape stays
  `(passed, measured, expected, tolerance, detail)` inside a `ValidationReport`.
- The frame resolver implements the closed derivation set: `named_datum`, `base_sketch_plane`,
  `largest_planar_face`. Each member must be **total and deterministic** — it returns exactly one
  frame on every supported leg or it raises; it never guesses.
- `largest_planar_face` carries the mandatory tie-break: largest area, then lowest centroid along
  global Z, then lowest sorted mapped name. Without it a symmetric part resolves a different origin
  on different legs and the frame silently flips.
- `expect_bbox` and `expect_extent` measure **in the resolved frame**, never the naive global
  bounding box (`verification-design.md:299`). `hole_position` projects the cylinder axis onto the
  anchor plane in frame coordinates (§7.2).
- Tolerance defaults come from `verification-design.md` §8: linear ±0.05 mm, angle ±0.1°, volume
  ±1 % relative, coaxial grouping ≤0.1° axis angle and ≤0.01 mm centre offset. No assertion may be
  tighter than the measured shape's own `Shape.getTolerance`.
- Disambiguation rules stay normative, and the existing implementations already encode several
  (`_is_hole_wall` probes material outside the cylinder, `_is_full_circle_wall` filters fillet arcs,
  `_logical_holes` groups coaxial faces). Reuse those helpers rather than re-deriving them.
- Feature metadata (for example `PartDesign::Hole.Diameter`) is a diagnostic hint in `detail` only,
  never the verdict.
- Adding a primitive changes the `assertions` validator source hash, which stales its registry
  score. Re-run `faults G2` and record the new `validator_sha`, or the gate reads stale.

**Never:**
- Never add an `fn` name outside the §7.2 vocabulary plus the three already-declared G2 extensions.
  A new name is a documented extension in the gate README with its reason, never a silent addition.
- Never accept a sub-element index selector (`Face3`, `Edge7`) as a spec-level selector — selectors
  are geometric queries (AD-13). Mapped names may appear only inside a resolved witness.
- Never capture an expected value from a verify tool or from this module's own output. Golden values
  are analytic.
- Never weaken or delete an existing G2 measurement to make a new primitive fit.
- Do not implement `techdraw_for_judge`, `verify_visual`, or any designer-loop code.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Frame on rotated part | part rotated 30° about Z, `base_sketch_plane` declared | `expect_bbox` measures the in-frame extents, matching the unrotated values | Unresolvable frame → failing `INVALID_INPUT` check |
| Symmetric largest-face tie | two planar faces of equal area | Tie-break selects deterministically; same face on repeat runs | Never an arbitrary pick |
| `hole_diameter` | shape with one 6 mm hole | `2 * Cylinder.Radius` = 6.0 within ±0.05 mm | No cylindrical face → failing check naming the miss |
| `hole_position` | hole at frame (20, 15) | Axis projected onto anchor plane in frame coords | Out-of-tolerance → fail with measured vs expected |
| `angle_between` | two perpendicular faces | 90° within ±0.1° | Non-planar selector → failing check |
| `distance_between` | two parallel faces 40 mm apart | `distToShape` min distance = 40.0 | Empty selector match → failing check |
| `expect_extent` | oriented extent along frame X | Length along the frame direction, not global X | Degenerate direction → failing check |
| Tolerance below kernel floor | assertion tighter than `Shape.getTolerance` | Refused as invalid, never silently passed | `INVALID_INPUT` naming the floor |

</frozen-after-approval>

## Code Map

- `benchmarks/harness/assertions.py` -- the module to extend. `_MEASUREMENTS` dict at :564-573 maps
  `fn` name to measurer; `SUPPORTED_FNS` at :576 derives from it; `evaluate()` at :579 dispatches and
  already reports an unknown `fn` as failing `INVALID_INPUT`. Add new measurers and register them in
  that one dict — no dispatch change needed.
- `benchmarks/harness/assertions.py:46` -- `_check(...)`, the required result shape.
- `benchmarks/harness/assertions.py:75` -- `_band(...)`, tolerance resolution with abs/rel defaults.
- `benchmarks/harness/assertions.py:132-282` -- existing geometry helpers to reuse:
  `_cylindrical_faces`, `_is_full_circle_wall`, `_axis_of`, `_parallel`, `_axis_offset`, `_distance`,
  `_probe_is_inside`, `_is_hole_wall`, `_logical_holes`, `_hole_axis_points`.
- `benchmarks/harness/assertions.py:491` -- `_extent_along(points, axis)`, the nearest thing to an
  oriented extent today; `expect_extent` should build on it rather than duplicate it.
- `benchmarks/harness/assertions.py:34-44` -- existing tolerance constants
  (`_DEFAULT_LINEAR_ABS = 0.05`, `_DEFAULT_VOLUME_REL = 0.01`, `_COAXIAL_ANGLE_TOL`,
  `_COAXIAL_OFFSET_TOL`). Add the angle default beside them.
- `_bmad-output/.../design/verification-design.md:280-311` -- §7.2 primitive table (signatures and
  measurement definitions) and §7.3 normative disambiguation rules.
- `_bmad-output/.../design/verification-design.md:332-350` -- §8 tolerance policy table.
- `benchmarks/g2/README.md` -- the precedent for documenting a declared vocabulary extension.
- `benchmarks/_registry/validators.yaml` -- the `assertions` row whose `validator_sha` this story
  stales.
- `benchmarks/runner.py:113` -- `_VALIDATOR_SOURCES["assertions"]` hashes
  `benchmarks/harness/assertions.py`; editing it is what stales the score.
- `tests/infc/` -- where a real-geometry test belongs (it needs FreeCAD shapes). `tests/external/`
  cannot import FreeCAD.

## Tasks & Acceptance

**Execution:**
- [ ] `benchmarks/harness/assertions.py` -- add the anchor-frame resolver: the three derivation
      members, the largest-planar-face tie-break, and a transform helper every measurement applies
      before comparing. This is the story's load-bearing change (DW-115).
- [ ] `benchmarks/harness/assertions.py` -- add `hole_diameter`, `hole_position`, `distance_between`,
      `angle_between`, `expect_bbox`, `expect_extent`; register each in `_MEASUREMENTS`.
- [ ] `benchmarks/harness/assertions.py` -- make the existing frame-sensitive measurements honour the
      resolved frame, and refuse any tolerance tighter than `Shape.getTolerance`.
- [ ] `tests/infc/test_assertion_primitives.py` -- per-primitive tests over documents the test builds,
      with analytic expected values. Must include a **rotated-part fixture**: an axis-aligned fixture
      cannot falsify a missing frame transform, which is how DW-115 stayed invisible.
- [ ] `tests/infc/test_assertion_primitives.py` -- a tie-break test with two equal-area faces,
      asserting the same face resolves on repeated runs.
- [ ] `benchmarks/_registry/validators.yaml` -- refresh the `assertions` `validator_sha` and its
      `last_run` after re-running the fault suite, so the score is current rather than stale.
- [ ] `_bmad-output/implementation-artifacts/deferred-work.md` -- close DW-115 with the measured
      resolution, or record precisely what remains.

**Acceptance Criteria:**
- Given a part rotated about Z with a declared `base_sketch_plane` frame, when `expect_bbox` runs,
  then it reports the in-frame extents and not the global bounding box.
- Given two planar faces of equal area, when `largest_planar_face` resolves, then the same face is
  chosen on every run and the choice is recorded in the result detail.
- Given the 11 §7.2 names, when `SUPPORTED_FNS` is read, then all 11 are present alongside the three
  declared G2 extensions, and no fourth undeclared name exists.
- Given an assertion tolerance tighter than the shape's own `getTolerance`, when evaluated, then it
  is refused as invalid rather than passed.
- Given `faults G2`, when re-run after this change, then the `assertions` validator reports a current
  score and `test_leg_b_is_current_for_the_committed_g2_scores` passes.
- Given the full suites, when run, then in-FreeCAD and external baselines do not regress
  (614 infc OK, 1094 external passed at commit 273413a).

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

**Why the frame is the real work.** The six missing primitives are mostly thin wrappers over
geometry the module already computes. The anchor frame is not: it is absent, 40 cases declare it, and
its absence is undetectable with the axis-aligned fixtures the suite currently uses. A rotated
fixture is therefore mandatory — it is the only thing that can fail if the transform is skipped.

**Why `hole_position` needs the frame most.** `verification-design.md` §7.2 defines it as the
cylinder axis projected onto the anchor plane *in frame coordinates*. Implemented globally it would
return plausible-looking numbers that are wrong by exactly the part's placement, which is the failure
mode hardest to notice in a passing-looking report.

## Verification

**Commands:**
- `python tests/run_tests.py` (H1 `fcb` env, with the documented `PYTHONPATH` patch)
  -- expected: new primitive tests pass; no regression below 614 OK
- `uv run pytest tests/external -q` -- expected: no regression below 1094 passed
- `uv run python -m benchmarks.runner faults G2` -- expected: `assertions` scores current
- `uv run pytest tests/external/test_gate_g2_exit.py -q` -- expected: leg-b currency passes
- `uv run ruff check benchmarks/ tests/` -- expected: clean
- `python scripts/check_imports.py` -- expected: exit 0
