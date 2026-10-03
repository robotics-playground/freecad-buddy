---
name: parametric-patterns
track: B
description: >-
  Use when building a part to stay editable: a master/skeleton sketch, driving
  dimensions in a spreadsheet or variable set, and feature ordering that survives
  parameter edits (references early, fillets last). Trigger phrases: "make it
  editable", "master sketch", "skeleton sketch", "driving dimensions", "spreadsheet
  parameters", "VarSet", "parameter table", "so a user can change it". Do NOT use
  for deciding which values are parameters (see design-intent) or splitting sketches
  (see sketch-strategy).
version: 0.1.0
freecad-versions: ['1.1']
---

## Scope

Build a part whose parameters actually drive robust edits. This skill owns the
parametric *mechanism*: the master/skeleton sketch pattern, storing driving
dimensions in a spreadsheet or variable set, and ordering features so a parameter
change recomputes cleanly. It does not own *which* values should be parameters or
how to name them (design-intent) or how sketches are divided (sketch-strategy) — it
takes those decisions and makes them robust under editing.

This skill guides work you carry out through the **freecad-buddy MCP server** (the
`sketch_*`, `feature_*`, `query_*`, and `verify_*` tools). If those tools aren't
available in your session, install and connect the freecad-buddy MCP first — open
FreeCAD with the freecad-buddy add-on, which auto-starts the server, then point your
MCP client at it — otherwise the parametric model can't be built or verified.

## Decision Rules

- Store driving dimensions in **one place** — a variable set (preferred) or a
  spreadsheet fallback — and reference them by expression from features and
  constraints, because a single source of truth means an edit happens once and
  propagates, instead of the same number living in five features that drift apart.
- Use a **master (skeleton) sketch** for the part's controlling geometry — key
  planes, axes, hole-circle radii, overall envelope — and attach features to it,
  because the skeleton carries the design intent and a change to it moves everything
  downstream together, the way the designer means.
- Order features so **references come early and fragile steps come late**: create
  datums and the skeleton first, add the solid features, and apply fillets and
  chamfers last, because every boolean re-labels edges and a fillet placed early
  loses its references on the next recompute.
- Make dependent values **expressions on the drivers**, never re-typed literals —
  a hole offset is `spacing/2`, a flange datum is `base_len - inset` — because an
  expression re-evaluates on an edit while a duplicated number silently goes stale.
- Anchor parametric features to **datums, not model faces**, because an edit that
  resizes the part re-labels faces (TNP); a feature referencing a datum survives the
  resize where one referencing `Face6` breaks.
- Give each driving parameter a **valid default and a sane range**, and check the
  extremes: a parameter that produces a self-intersecting or impossible model at its
  min or max isn't a usable degree of freedom. Verify a representative edit with
  `verify_shape` and `verify_references`, not by eye.
- After changing a driving parameter, **recompute and re-verify** the whole part —
  a clean recompute plus the reference audit proves the edit propagated without
  breaking a reference. An edit that "worked" but broke an unrelated feature is a
  regression; catch it with `verify_fingerprint` or a re-measure.
- Keep the parameter set **minimal**: expose the real design degrees of freedom, not
  every constant. Too many parameters make the model as hard to reason about as too
  few — one control per genuine design choice.
- Encode units in a parameter name only when **ambiguous** (`_deg`, `_mm`); a length
  in a mm-internal model needs no suffix, but an angle or a time does.

## Worked Examples

Input: "Make this bolt-pattern plate editable so a user can change size and hole
count."

Reasoning → parametric build:
1. Driving dimensions in one variable set: `plate_len`, `plate_wid`, `hole_dia`,
   `hole_count`, `edge_margin`.
2. Master sketch: the plate envelope and a construction bolt-circle/grid driven by
   those variables; hole positions are expressions (`edge_margin` in from each
   corner), not literals.
3. Features in order: base pad → hole pattern (count driven by `hole_count`) →
   fillets last. Holes anchored to the skeleton, not the pad's faces.
4. Test the edit: change `plate_len`, recompute, then `verify_shape` +
   `verify_references` → the holes stay margin-in and symmetric, references clean.
If the holes had been dimensioned from a face instead of the skeleton, resizing the
plate would have broken them.

Input: "The fillet errors whenever I make the part taller."

Reasoning: the fillet was applied before a feature whose recompute re-labels its
edges. Move the fillet to the end of the feature order so its edges are stable at the
time it computes, and re-select them by intent, not index.

## Anti-Patterns

- **Same number in many features.** Symptom: an edit updates some features and not
  others; the part goes inconsistent. Why: no single source of truth. Fix: one
  variable set/spreadsheet, referenced by expression.
- **Fillets early in the order.** Symptom: a fillet breaks whenever an upstream
  parameter changes. Why: a later boolean re-labelled its edges. Fix: fillets and
  chamfers last; references early.
- **Re-typed literals for dependent values.** Symptom: a derived dimension goes
  stale after an edit. Why: it was a copied number, not an expression. Fix: express
  dependents on the drivers.
- **Parametric features on model faces.** Symptom: features break when the part
  resizes. Why: face indices re-label on recompute (TNP). Fix: anchor to datums/the
  skeleton.
- **Too many parameters.** Symptom: nobody can tell which control matters. Why:
  every constant was exposed. Fix: expose only real design degrees of freedom.
- **Not testing the extremes.** Symptom: a parameter produces a broken model at its
  range ends. Why: only the default was checked. Fix: verify min/max edits with
  `verify_shape`.
