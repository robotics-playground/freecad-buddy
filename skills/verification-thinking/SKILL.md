---
name: verification-thinking
track: B
description: >-
  Use when deciding what to measure after a modeling step and whether a part is
  actually done: which geometry to check against the spec, when a screenshot is
  required, and how to turn a visual doubt into a measurement. Trigger phrases:
  "verify", "does it match the spec", "is this done", "check the result", "measure
  it", after a mutation or a full part build. Do NOT use for planning the build
  order (see design-decomposition) or diagnosing a recompute error (see
  freecad-troubleshooting).
version: 0.1.0
freecad-versions: ['1.1']
---

## Scope

Decide what "done" means for a modeled part and prove it. This skill owns the
verification mindset: which deterministic checks a spec demands, why a clean
recompute is necessary but never sufficient, when a render is mandatory, and how
to convert a visual concern into a measurement before it counts as a result. It
covers per-part done-ness, not per-operation transaction safety (the mutation
protocol handles rollback automatically) and not error diagnosis
(freecad-troubleshooting). Snapshot packet sizing lives in
`references/snapshot-packet-sizing.md`, loaded when a review needs more than one
view.

Every check here runs through the **freecad-buddy MCP server** (the `query_*` and
`verify_*` tools named below). If those tools aren't available in your session,
install and connect the freecad-buddy MCP first — open FreeCAD with the
freecad-buddy add-on, which auto-starts the server, then point your MCP client at
it — otherwise none of these checks can run.

## Decision Rules

- Treat the producing agent's own judgement as **input, never a verdict** — pass
  or fail comes from deterministic checks (`verify_shape`, `verify_sketch`,
  `verify_export_step`) or an independent judge, because an agent that grades its
  own work systematically over-scores it.
- A clean recompute is **necessary but not sufficient**: `verify_recompute`
  passing means the script ran, not that the geometry is right. Always follow it
  with spec-driven measurement, because "a pocket exists" is not "the right pocket,
  right place, right depth".
- Measure **every** dimension, offset, and clearance the spec (or a drawing
  callout) states — with `query_mass_properties` for bbox/volume and
  `query_placement` for distances and offsets — because an unchecked dimension is
  an unverified claim, and the point of verifying is to falsify a wrong part.
- Run a baseline inspection on every result before spec checks:
  `query_tree_summary` + `query_object` for labels and error states,
  `query_mass_properties` for a scale sanity check. An order-of-magnitude or
  centering error passes narrow checks but shows up in the baseline.
- Check an interface that should be flush or centered with `query_placement`
  deltas between the two references; if it's off, fix the source feature or datum
  and recompute — never nudge exported geometry, because the model is the source
  of truth and the export is derived.
- On a **modification**, compare geometry before and after with
  `verify_fingerprint`, because a change that "worked" may have silently altered an
  unrelated feature, and the fingerprint diff catches what a spot check misses.
  Never use file size or a diff of the saved document as a geometry comparison —
  those change for reasons unrelated to shape.
- An export counts as done **only** when its paired `verify_export_step` (or
  `_stl`/`_3mf`) re-imports and matches, because "the file was written" is not
  proof the geometry survived the round-trip. Independent-oracle disagreement is a
  fail, never an average.
- After any mutation, run `verify_references` (the post-recompute reference audit)
  and treat an `UNSUPPORTED` result as *not clean*, never as a pass — a silently
  re-pointed or dropped reference is a corrupted model that still recomputes.
- Take a screenshot with `query_screenshot` for every part whose geometry
  changed, **even when every deterministic check passed**, because deterministic
  checks only catch what the spec encoded; a mirrored part or a feature on the
  wrong face passes the numbers and fails the eye. Size the packet per
  `references/snapshot-packet-sizing.md`; don't re-render in a loop.
- **Convert every visual concern into a geometry check before it becomes a
  result** — a screenshot is diagnostic, not authoritative. "Holes look
  asymmetric" → measure the hole centers; "the lid looks offset" → check the frame
  delta; "a boss looks floating" → check the solid count and contact. The
  measurement is the claim; the render only pointed at it.
- A generated *part* is done only when **both** channels pass: all geometry
  assertions AND an independent visual judge (a vision model that is never the
  acting agent). The judge is conjunctive — it can flag a wrong-looking part that
  geometry missed, but it can never rescue a part geometry already failed.
- When a mating part is **inserted, slid, or tilted into place**, check clearance
  along that path, not only at the final position: sweep the mating part through
  the travel in steps and measure overlap and minimum gap at each step, because a
  wall that clears the installed part can still block it on the way in.
- Re-check an earlier clearance after **every edit near it**: widening a gap on one
  side moves material toward something else, so rerun the clearance and path checks
  for the neighbours, not only for the feature you changed.
- Report only checks that actually ran. Never claim structural safety, tolerance
  compliance, or manufacturability unless that analysis was explicitly performed —
  geometric plausibility is the ceiling of what these checks prove.

## Worked Examples

Input: a copilot just padded a sketch to make a 60×40×5 plate; spec says two Ø5.5
holes 40 mm apart.

Verification read:
1. Baseline: `query_tree_summary` (one solid, named, no error state);
   `query_mass_properties` → bbox ≈ 60×40×5, volume plausible.
2. Spec checks: `verify_shape` for validity + counts;
   `count_cylindrical_holes == 2`; `hole_diameter == 5.5`; hole-center distance via
   `query_placement` == 40 mm.
3. `verify_references` clean after recompute.
4. `query_screenshot` (single iso — simple static part per the packet guide). The
   holes look centered; nothing to escalate. Done: geometry ∧ visual both pass.

Input: a modification — "make the flange 5 mm taller" on an existing bracket.

Verification read: `verify_fingerprint` before vs after → confirm only the flange
volume changed and the base plate + holes are byte-identical; if the hole pattern
also shifted, that's a silent regression to investigate, not a success. Then
`query_screenshot` and re-measure the flange height. A clean recompute alone would
have hidden the regression.

## Anti-Patterns

- **Recompute = done.** Symptom: a wrong part reported as passing. Why: the script
  ran, so it was assumed correct. Fix: follow every recompute with spec-driven
  measurement.
- **Skipping the render because the numbers passed.** Symptom: a mirrored or
  wrong-face part ships. Why: deterministic checks only encode what the spec
  listed; orientation and gestalt aren't in the numbers. Fix: screenshot every
  changed part; done is geometry ∧ visual.
- **Claiming a visual finding as a result.** Symptom: "looks asymmetric" reported
  as a defect with no measurement. Why: a render is diagnostic, not authoritative.
  Fix: convert the concern into a `query_placement`/`query_mass_properties` check
  first.
- **File diff as geometry comparison.** Symptom: "the file changed, so the
  geometry changed" (or the reverse). Why: saved-document bytes shift for reasons
  unrelated to shape. Fix: use `verify_fingerprint`.
- **Export written = export done.** Symptom: a STEP/STL delivered without a
  re-import check. Why: writing bytes isn't verifying geometry survived. Fix:
  require the paired `verify_export_*` before calling it done.
- **Treating `UNSUPPORTED` reference audit as clean.** Symptom: a silently
  corrupted model passes. Why: no-element-map was read as no-problem. Fix:
  `UNSUPPORTED` is not a pass.
- **Checking only the installed position.** Symptom: a part that "fits" cannot be
  assembled. Why: the interference check ran at the end pose only. Fix: sweep the
  assembly path and report overlap and minimum gap per step.
