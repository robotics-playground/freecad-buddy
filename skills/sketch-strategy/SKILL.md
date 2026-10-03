---
name: sketch-strategy
track: B
description: >-
  Use when deciding what belongs in one sketch versus several, how to split a
  profile, and which profile captures the design intent before you start drawing.
  Trigger phrases: "one sketch or two", "how should I split this profile", "what
  goes in this sketch", "simplify this sketch", "which profile", planning a
  multi-feature part's sketches. Do NOT use for constraining a sketch you're already
  in (see freecad-sketcher) or ordering the whole feature plan (see
  design-decomposition).
version: 0.1.0
freecad-versions: ['1.1']
---

## Scope

Decide how to divide a part's shape into sketches before drawing them. This skill
owns the *strategy*: what belongs in one sketch versus several, when to split a
complex profile, and choosing the profile that expresses design intent. It does not
own constraining a sketch (freecad-sketcher, which takes over once you're inside a
sketch) or the overall feature sequence (design-decomposition, which decides the
order of the features these sketches feed). It sits between them: given the plan,
shape the sketches.

This skill guides work you carry out through the **freecad-buddy MCP server** (the
`sketch_*`, `verify_sketch`, and `query_sketch_info` tools). If those tools aren't
available in your session, install and connect the freecad-buddy MCP first — open
FreeCAD with the freecad-buddy add-on, which auto-starts the server, then point your
MCP client at it — otherwise the sketches you plan can't be built.

## Decision Rules

- Prefer **two simple sketches over one clever one**, because a simple profile
  reaches fully constrained with fewer constraints, is easier to verify, and fails
  in an obvious place — a single elaborate profile that does three jobs is where
  conflicts and un-constrainable geometry hide.
- Put in one sketch the geometry that shares a **plane and a feature**: one profile
  that becomes one pad or pocket. Split into separate sketches when the geometry
  belongs to different features, different planes, or different design decisions,
  because a sketch that mixes a pad profile with a hole pattern couples two edits
  that should move independently.
- Choose the profile that makes the spec's **controlling dimension a direct sketch
  dimension**, because the whole point of a parametric sketch is that the number the
  user stated is the number you dimension — a profile that forces the key dimension
  to be derived buries the intent.
- Keep **construction geometry** carrying the skeleton (centerlines, bolt-circle
  radii, symmetry axes) in the sketch that uses it, because construction geometry is
  how a sketch stays symmetric and driven by intent rather than by duplicated
  numbers.
- Sketch the **profile, not the finished shape**: a revolve profile is the
  half-section, a pad profile is the flat outline — draw the minimal generating
  curve and let the feature make the solid, because sketching the whole 3D shape in
  2D is both harder to constrain and wrong for the operation.
- Split a profile when part of it is **fragile or likely to change**: isolate the
  feature the user is most likely to edit into its own sketch so an edit touches one
  sketch, not a shared monolith.
- Plan every sketch to reach **fully constrained** (DoF = 0). If a profile can't be
  cleanly constrained, that's a signal it's trying to do too much — split it. Verify
  the intent with `verify_sketch` after building, not by eye.
- Prefer a profile that references a **datum or the origin** over one that projects
  a model face, because a projected external reference re-points or drops on
  recompute (TNP); a sketch anchored to a datum is durable.

## Worked Examples

Input: "Model a bracket: an L-shaped base with a bolt pattern and a rounded flange."

Reasoning → sketch split:
1. Base sketch: the L outline only, on XY — one pad. Controlling dims (`arm_a`,
   `arm_b`, `thickness`) are direct sketch dimensions.
2. Bolt-pattern sketch: the hole centers only, as a separate sketch (its own
   feature), so editing the pattern doesn't disturb the base profile. Use a
   construction bolt-circle or centerlines for symmetry.
3. Flange sketch: on a datum plane at the base end, not projected off the base face.
One sketch per feature, each reaching `verify_sketch` fully-constrained. Trying to
draw the L, the holes, and the flange in one profile would be near-impossible to
constrain and couple three independent edits.

Input: "Make a turned knob with a knurled rim."

Reasoning: sketch the **half-section profile** for the revolve, not the round 3D
shape — one closed profile from the axis out. The knurl is a separate feature
(pattern), not part of the revolve profile.

## Anti-Patterns

- **One clever mega-sketch.** Symptom: the sketch won't fully constrain, or an edit
  moves the wrong thing. Why: one profile is doing several features' jobs. Fix:
  split by plane and by feature.
- **Sketching the finished 3D shape in 2D.** Symptom: a profile that's hard to
  constrain and wrong for the feature. Why: the generating curve was confused with
  the solid. Fix: sketch the minimal profile the feature needs.
- **Deriving the controlling dimension.** Symptom: the user's stated number isn't a
  sketch dimension. Why: the profile choice buried it. Fix: pick the profile that
  makes the stated dimension direct.
- **Coupling independent features in one sketch.** Symptom: editing the hole pattern
  disturbs the base outline. Why: two features share one sketch. Fix: one sketch per
  feature.
- **Projecting a face instead of anchoring to a datum.** Symptom: the sketch breaks
  after an unrelated recompute. Why: the external reference was re-pointed (TNP).
  Fix: anchor the profile to a datum or the origin.
