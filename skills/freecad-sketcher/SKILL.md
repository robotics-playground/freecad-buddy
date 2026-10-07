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
version: 0.2.0
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

- Treat a sketch as done only when the last `sketch_*` result reports
  `structured_content.sketch_state.fully_constrained` true and `dof` 0, with
  `mutation.post_verify.passed` true. That is the AD-8 sketch signal: the same
  grade `verify_sketch` computes (a clean solve, no conflicting, malformed or
  redundant constraint), so do not call `verify_sketch` after a typed sketch
  tool. `sketch_state.readable` false (no grade) or a `"not_measured"`
  `fully_constrained` is not a pass: call `verify_sketch`. Call `verify_sketch`
  also for a sketch changed outside the typed tools (a GUI edit, a script),
  because no mutation result covers that change. FreeCAD's
  `FullyConstrained` property alone is not enough, because FreeCAD does not update
  it after a failed solve, so a redundant sketch can keep a stale true.
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
- Treat **conflicting**, **malformed** and **redundant** constraints as a hard
  failure, because FreeCAD marks a redundant sketch in error and builds no shape for
  it. Only **partially redundant** constraints are a warning. Remove the redundant
  constraint the diagnostic names; never add a constraint "to be safe".
- Map a solver constraint id back to its constraint by name when reporting a
  conflict — the solver reports 1-based ids, and naming the actual constraint is
  what makes the diagnosis actionable.
- Use **external geometry with caution**: projecting a model edge or face into a
  sketch creates a reference that a later recompute can re-point or drop (the
  topological-naming risk), so prefer attaching to a datum plane over projecting a
  face, and after any change read the reference audit in
  `mutation.post_verify.tnp_audit` — an `UNSUPPORTED` status or finding is not
  clean.
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
4. Send the lines and all these constraints in one `sketch_add_geometry` call —
   geometry sent alone leaves `dof` > 0, which fails and rolls back. Its result →
   `sketch_state.fully_constrained` true, `dof` 0, `post_verify.passed` true, no
   conflicting or redundant constraints. Done — no separate `verify_sketch` call.
If instead you'd dimensioned all four corners from the origin, the sketch would be
over-defined the moment you added the width, and the solver would report a conflict.

Input: "I added two holes to the sketch in the GUI; is it still fine?"

Reasoning: the edit was made outside the typed tools, so no mutation result covers
it — call `verify_sketch`. It reports `dof` 2: the two hole centers are unlocated.
Add the missing position constraints in one `sketch_add_constraint` call — distances
from a construction centerline, or a symmetry constraint if the holes are mirrored.
Its `sketch_state` reports `fully_constrained` true and `dof` 0. Never pad the
feature before that.

## Anti-Patterns

- **Reading DoF from the solver code.** Symptom: an under-constrained sketch
  treated as done. Why: `solve() == 0` means "solved", not "fully constrained". Fix:
  gate on `sketch_state.fully_constrained` and `dof`.
- **Duplicated dimensions instead of symmetry.** Symptom: an edit makes a
  once-symmetric feature lopsided. Why: two equal numbers drift when one changes.
  Fix: use a symmetric or equal constraint.
- **Dimensioning before locating.** Symptom: the solver reports conflicts as you
  add sizes. Why: shape and size were fought at once. Fix: geometric constraints
  first, dimensions second.
- **Keeping a redundant constraint.** Symptom: the mutation rolls back with
  `RECOMPUTE_ERROR` "Sketch with redundant constraints". Why: FreeCAD fails a
  redundant sketch. Fix: remove the constraint the diagnostic names.
- **Projecting a face for an external reference.** Symptom: the sketch breaks after
  an unrelated recompute. Why: the projected edge was re-pointed or dropped (TNP).
  Fix: attach to a datum plane where possible; read `post_verify.tnp_audit` after
  each change.
