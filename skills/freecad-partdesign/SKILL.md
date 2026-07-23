---
name: freecad-partdesign
track: A
description: >-
  Use when adding or editing a PartDesign solid feature: pad, pocket, revolution,
  hole, fillet, chamfer, loft, sweep, linear/polar pattern, or mirror. Covers each
  feature's prerequisites, key properties, and failure modes, plus overshooting
  cuts and patterning in one operation. Trigger phrases: "pad the sketch", "pocket
  a slot", "add a fillet", "put a hole", "revolve", "loft", "pattern these", "why
  did the fillet fail". Do NOT use for planning the whole feature sequence (see
  design-decomposition) or sketch constraints (see freecad-sketcher).
version: 0.1.0
freecad-versions: ['1.0', '1.1']
---

## Scope

Drive individual PartDesign features correctly and know how each one fails. This
skill owns per-feature knowledge: what a pad/pocket/revolution/hole/fillet/chamfer/
loft/sweep/pattern/mirror needs before it will run, the properties that control it,
and the trap each one falls into. It does not own the *order* features run in
(design-decomposition) or the sketches they consume (freecad-sketcher) — it owns
the operation once its input exists. The full per-feature prerequisite and
failure-mode tables live in `references/feature-failure-tables.md`; load that when
a specific feature misbehaves.

This skill drives FreeCAD through the **freecad-buddy MCP server** (the `feature_*`,
`query_*`, and `verify_*` tools named below). If those tools aren't available in your
session, install and connect the freecad-buddy MCP first — open FreeCAD with the
freecad-buddy add-on, which auto-starts the server, then point your MCP client at
it — otherwise none of these steps can run.

## Decision Rules

- Give a solid-adding or -removing feature a valid **closed profile** before
  running it, because pad and pocket are profile-based — an open wire produces no
  face and the feature fails or yields a null shape.
- Set a pad/pocket's length mode deliberately: `Type = "Length"` for a fixed
  extent, or an up-to mode (`"UpToFace"`, `"UpToShape"`, and for pad `"UpToLast"`/
  `"UpToFirst"`, for pocket `"ThroughAll"`) when the extent should follow existing
  geometry — the enum members differ between pad and pocket, so confirm the exact
  value with `query_object` rather than assuming. Use `Midplane` to grow symmetric
  about the sketch and
  `Reversed` to flip direction rather than negating the length.
- **Overshoot a through-cut**: extend the cutting profile roughly 1 mm past the
  faces it enters and exits (or use a through-all/up-to mode), because a tool face
  coincident or coplanar with a target face is a classic OCCT boolean failure.
- **Cut a repeated feature once, then pattern it** — model one hole/pocket and
  apply a linear or polar pattern (`Occurrences` controls the count) rather than
  placing N separate features, because one patterned feature is one named step that
  edits and verifies as a unit.
- Apply **fillets and chamfers last**, because every boolean before them re-labels
  the edges they select; a fillet added early loses its edge references when a
  later feature recomputes. Fillet's control is `Radius`; chamfer's is `Size` (with
  `ChamferType` and `Angle` for the equal/two-distance/distance-angle variants).
- Keep a fillet `Radius` (or chamfer `Size`) **smaller than the local geometry** it
  rounds, because a radius larger than the adjacent face or edge length has no valid
  solution and the dress-up fails.
- Select the edges/faces a feature references by **datum, axis, position, or a
  geometric-query/mapped-name selector**, never a bare `Face6`/`Edge3`, because
  indices reshuffle on recompute (TNP) and a fillet's edge list silently drops
  members that lose their two adjacent faces.
- Give a loft/sweep ordered, compatible profiles: a loft needs its `Sections` in
  sequence (set `Closed` to loop the last back to the first, `Ruled` for straight
  transitions); a sweep needs a `Spine` path plus its section(s), and a self-
  intersecting or sharply-kinked spine is the usual sweep failure.
- Give a hole feature a sketch of its center points, then set `Diameter`,
  `DepthType`, and (if tapped) `Threaded` — the thread and counterbore/countersink
  metadata (`HoleCutType`, `ThreadDiameter`) is descriptive, so verify the actual
  cut geometry, not the property values.
- After any feature, treat a clean recompute as necessary but not sufficient:
  measure the result against intent and audit references — recompute success only
  proves the script ran (verification is owned by verification-thinking).

## Worked Examples

Input: "Pad this rectangular sketch 5 mm, then put four Ø5.5 holes and round the
top edges 2 mm."

Reasoning → operations:
1. Pad the closed rectangle: `Type = "Length"`, `Length = 5`. Verify one valid
   solid, bbox thickness 5 mm.
2. Holes: one hole-point sketch with the four centers, one Hole feature
   `Diameter = 5.5` `DepthType` through — patterned from the sketch, not four
   features. Overshoot is automatic for a through hole.
3. Fillet **last**: select the four top edges by "top face + its bounding edges"
   (position/axis), not by index; `Radius = 2`. Because the holes were cut before
   the fillet, the fillet's edge references are stable.
If the fillet had been added before the holes, the holes' recompute would have
re-labelled the top edges and the fillet would report dropped edges.

Input: "The 4 mm fillet on this 3 mm-thick web fails."

Reasoning: `Radius = 4` exceeds the local 3 mm geometry — no valid rounding fits.
Fix per `references/feature-failure-tables.md`: reduce the radius below the local
thickness, or narrow the edge selection, or split the edge group by intent.

## Anti-Patterns

- **Fillet-before-boolean.** Symptom: dropped-edge or recompute error after a later
  feature. Why: the boolean re-labelled the filleted edges. Fix: fillets/chamfers
  are the last features.
- **Coincident cut faces.** Symptom: a through-pocket leaves a thin skin or the
  boolean errors. Why: the tool face sits exactly on the target face. Fix: overshoot
  ~1 mm or use a through-all/up-to mode.
- **N separate features for a pattern.** Symptom: an edit means changing N features
  and they drift. Why: the repetition wasn't captured as one feature. Fix: model one
  and pattern it with `Occurrences`.
- **Index-based edge selection.** Symptom: a fillet or chamfer references the wrong
  edge after recompute, or silently drops one. Why: `Edge3` moved (TNP), and dress-up
  drops edges that lose adjacency. Fix: select by datum/axis/position or a
  geometric-query selector.
- **Radius larger than local geometry.** Symptom: fillet/chamfer fails with no
  clear message. Why: no valid solution fits the adjacent faces. Fix: shrink the
  radius/size below the local dimension.
- **Open profile into a pad/pocket.** Symptom: null shape or feature error. Why:
  a profile-based feature needs a closed face. Fix: close the sketch profile first
  (freecad-sketcher).
