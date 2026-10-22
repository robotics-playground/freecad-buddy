---
name: tool-selection
track: B
description: >-
  Use when choosing which modeling operation fits: pad vs revolve vs loft vs sweep,
  fillet vs chamfer, pattern vs mirror vs individual features, and PartDesign
  features vs Part booleans. Trigger phrases: "pad or revolve", "which operation",
  "fillet or chamfer", "pattern or mirror", "loft or sweep", "how should I make
  this shape". Do NOT use for the parameters and failure modes of a chosen feature
  (see freecad-partdesign), the whole build sequence (see design-decomposition), or
  converting an existing build123d / CadQuery model (see code-cad-conversion).
version: 0.2.0
freecad-versions: ['1.1']
---

## Scope

Pick the right operation for a shape and know why. This skill owns the choice
between operations — pad/revolve/loft/sweep, fillet/chamfer, pattern/mirror,
PartDesign vs Part booleans — with the reasoning behind each rule. It does not own
how to drive the chosen feature or its failure modes (freecad-partdesign) or the
order features run in (design-decomposition). Choose here; execute there.

This skill guides operations you carry out through the **freecad-buddy MCP server**
(the `feature_*`, `sketch_*`, and `verify_*` tools). If those tools aren't available
in your session, install and connect the freecad-buddy MCP first — open FreeCAD with
the freecad-buddy add-on, which auto-starts the server, then point your MCP client
at it — otherwise the chosen operation can't be built.

## Decision Rules

- Choose the operation whose natural parameter is the spec's **controlling
  dimension**, because the point of picking well is that the stated number becomes a
  direct feature parameter rather than a derived value.
- **Pad** a constant cross-section along a straight axis; **revolve** a profile with
  rotational symmetry about an axis, because a revolve captures "this is round about
  an axis" in one profile plus one angle, where a pad would need an impossible
  circular sweep of the section. Reach for a round part → revolve first.
- **Loft** between two or more *different* profiles along their sequence;
  **sweep** one constant profile along a path, because loft is for a changing
  cross-section (a transition, a blend) and sweep is for a constant one following a
  curve (a pipe, a trim). If the section changes, loft; if only the path bends,
  sweep.
- Prefer a **pad/pocket/revolve** over a loft or sweep whenever the shape allows,
  because lofts and sweeps are more failure-prone (twist, self-intersection) and
  harder to constrain — spend that complexity only when a simpler operation genuinely
  can't make the shape.
- **Fillet** to round an edge (stress relief, a soft look, a cast/molded look);
  **chamfer** to bevel an edge (a lead-in for assembly, a deburr, a machined look),
  because they express different intents — a fillet says "smooth transition", a
  chamfer says "flat cut" — and manufacturing and function usually dictate which.
- **Pattern** a feature that repeats on a regular grid or around an axis (`linear`
  for a row/grid, `polar` for a circle); **mirror** a feature that is symmetric
  across a plane. Prefer pattern or mirror over placing N individual features,
  because one patterned/mirrored feature is one named step that edits and verifies as
  a unit and stays regular under a count or spacing change.
- Use **mirror** (not a 2-count pattern) when the intent is symmetry across a datum,
  because a mirror ties the copy to the original through a symmetry plane, so moving
  the original keeps the pair symmetric — a pattern would just place a fixed offset.
- Prefer **PartDesign features on a Body** over raw Part booleans for a parametric
  part, because PartDesign keeps a single ordered feature tree that edits cleanly and
  carries the reference/TNP machinery; reach for Part booleans only when combining
  independent solids that aren't a single body's feature history.
- When the task **converts an existing CSG code-CAD model** (build123d, CadQuery:
  primitives plus `+=` / `-=`), build with Part primitives and booleans whose sizes
  and placements are VarSet expressions (see code-cad-conversion), because that maps
  the source one-to-one and each part can be proven equal to the source STEP.
- When two operations both work, pick the one that leaves the **simpler, more
  editable tree**, because the tree is read and edited later — favor the choice a
  human can follow over the one that's momentarily convenient.

## Worked Examples

Input: "Make a cylindrical spacer, 20 mm diameter, 8 mm tall, with a 6 mm bore."

Reasoning: rotational symmetry → **revolve** the half-section (outer radius, height,
bore) about the axis, so `diameter`, `height`, and `bore` are direct profile
dimensions. A pad of a circle plus a pocket of a smaller circle also works, but the
revolve captures the round intent in one feature. Chamfer (not fillet) the bore
mouths if the spec wants an assembly lead-in.

Input: "Four mounting tabs, one at each corner."

Reasoning: the tabs repeat on a rectangular grid → model **one tab and linear-pattern
it** (or mirror across both center planes if the intent is symmetry). Placing four
separate tabs would drift on an edit and clutter the tree.

## Anti-Patterns

- **Loft/sweep where a pad/revolve would do.** Symptom: a twisted or failed surface
  on a shape a simpler feature makes cleanly. Why: complexity was spent
  unnecessarily. Fix: use the simplest operation the shape allows.
- **Fillet where the intent was a bevel** (or vice versa). Symptom: the wrong edge
  treatment for the function. Why: round and cut were conflated. Fix: fillet =
  smooth, chamfer = flat lead-in/deburr.
- **N individual features instead of a pattern/mirror.** Symptom: an edit means
  touching N features and they drift. Why: the repetition wasn't captured. Fix:
  pattern (regular) or mirror (symmetric).
- **A 2-count pattern where mirror was meant.** Symptom: a "symmetric" pair drifts
  when the original moves. Why: a pattern places a fixed offset, not a symmetry
  relation. Fix: mirror across the symmetry plane.
- **Part booleans for a parametric body.** Symptom: a tree that's hard to edit and
  loses reference tracking. Why: raw booleans bypass the PartDesign feature history.
  Fix: use PartDesign features on a Body; reserve booleans for combining independent
  solids and for converting a CSG code-CAD source (see code-cad-conversion).
