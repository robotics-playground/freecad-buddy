---
name: freecad-sketcher
track: A
description: >-
  Use when creating or editing a sketch, adding or fixing constraints, driving a
  sketch to fully constrained (DoF = 0), choosing geometry vs construction
  geometry, or attaching external references. Covers the constraint system,
  redundant vs conflicting constraints, and the risks of external-geometry
  references. Trigger phrases: "add a constraint", "constrain this sketch", "DoF >
  0", "fully constrained", "construction line", "external reference", "the sketch
  won't solve". Do NOT use for the solid feature built from a sketch (see
  freecad-partdesign) or planning how many sketches a part needs (see
  sketch-strategy).
version: 0.1.0
freecad-versions: ['1.1']
---

## Scope

Drive a single sketch to a clean, fully constrained state and know how its
constraint solver behaves. This skill owns the sketch interior: geometry vs
construction geometry, the constraint types and what each removes, reaching
DoF = 0, and the special risk of external-geometry references. It does not own the
feature a sketch feeds (freecad-partdesign) or the decision of how many sketches a
part needs (sketch-strategy) — it owns one sketch once you're in it.

This skill drives FreeCAD through the **freecad-buddy MCP server** (the `query_*`,
`verify_*`, and `sketch_*` tools named below). If those tools aren't available in
your session, install and connect the freecad-buddy MCP first — open FreeCAD with
the freecad-buddy add-on, which auto-starts the server, then point your MCP client
at it — otherwise none of these steps can run.

## Decision Rules

- Treat a sketch as done only when `FullyConstrained` reads true after a recompute,
  because that is the one signal that both DoF = 0 and the solve is clean — an
  under-constrained sketch still "solves" and still returns a zero solver code, so
  the solver return value is never the pass signal. Read it with `verify_sketch`.
- Never infer degrees of freedom from a successful solve: `solve()` returning 0
  means "solved", not "fully constrained", because the solver happily converges on
  an under-constrained sketch by holding the free parameters where they sit.
- Constrain **construction geometry first**, then hang real geometry off it,
  because construction lines and points carry the design skeleton (centerlines,
  bolt-circle radii) and constraining them first makes the rest fall into place
  with fewer, clearer constraints.
- Prefer **symmetric and equal constraints over duplicated dimensions**, because
  one symmetry constraint captures the intent ("these are mirrored") in a way a
  later edit preserves, whereas two equal numbers silently drift apart when one is
  changed.
- Add constraints in the order geometric → dimensional: lock the shape
  (coincident, horizontal, vertical, parallel, perpendicular, tangent, equal,
  symmetric) before the sizes (distance, radius, angle), because dimensioning
  un-located geometry produces a solver fighting to place and size at once, which is
  where conflicts appear.
- Treat **conflicting** or **malformed** constraints as a hard failure and
  **redundant** constraints as a warning only, because a conflict means the sketch
  is over-defined and won't solve correctly, while a redundant constraint is merely
  untidy — remove redundancy deliberately, never let a repair loop fail on it.
- Map a solver constraint id back to its constraint by name when reporting a
  conflict — the solver reports 1-based ids, and naming the actual constraint is
  what makes the diagnosis actionable.
- Use **external geometry with caution**: projecting a model edge or face into a
  sketch creates a reference that a later recompute can re-point or drop (the
  topological-naming risk), so prefer attaching to a datum plane over projecting a
  face, and after any change re-audit references with `verify_references` — an
  `UNSUPPORTED` result is not clean.
- Keep degenerate geometry out: a zero-length edge or a coincident-endpoints line
  passes a casual glance but fails the solve or the downstream feature. Fix it in
  the sketch, not by working around it downstream.

## Worked Examples

Input: "Constrain this rectangle sketch to 60×40 centered on the origin."

Reasoning → constraints:
1. Geometry constraints first: the four lines get horizontal/vertical, endpoints
   coincident to close the loop.
2. Symmetry: constrain the rectangle symmetric about the origin in X and in Y —
   one symmetric constraint per axis, not four corner dimensions — so a later width
   edit stays centered.
3. Dimensions: one horizontal distance = 60, one vertical distance = 40.
4. `verify_sketch` → `FullyConstrained` true, DoF = 0, no conflicts. Done.
If instead you'd dimensioned all four corners from the origin, the sketch would be
over-defined the moment you added the width, and the solver would report a conflict.

Input: "The sketch shows DoF = 2 after I added the holes."

Reasoning: two hole centers are unlocated. Add the missing position constraints —
distances from a construction centerline, or a symmetry constraint if the holes are
mirrored — then re-read `verify_sketch`. Never pad the feature until
`FullyConstrained` is true.

## Anti-Patterns

- **Reading DoF from the solver code.** Symptom: an under-constrained sketch
  treated as done. Why: `solve() == 0` means "solved", not "fully constrained". Fix:
  gate on `FullyConstrained` after recompute.
- **Duplicated dimensions instead of symmetry.** Symptom: an edit makes a
  once-symmetric feature lopsided. Why: two equal numbers drift when one changes.
  Fix: use a symmetric or equal constraint.
- **Dimensioning before locating.** Symptom: the solver reports conflicts as you
  add sizes. Why: shape and size were fought at once. Fix: geometric constraints
  first, dimensions second.
- **Failing on a redundant constraint.** Symptom: a repair loop aborts on a
  harmless redundancy. Why: redundant was treated as conflicting. Fix: redundant is
  a warning; only conflicting/malformed is a hard fail.
- **Projecting a face for an external reference.** Symptom: the sketch breaks after
  an unrelated recompute. Why: the projected edge was re-pointed or dropped (TNP).
  Fix: attach to a datum plane where possible; re-audit with `verify_references`.
