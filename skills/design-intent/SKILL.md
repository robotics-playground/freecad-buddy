---
name: design-intent
track: B
description: >-
  Use when deciding which values become parameters and which are derived, how to
  encode intent in constraints and names, and how to treat a source's authority
  (drawing vs image vs prose). Trigger phrases: "what should be a parameter",
  "dimension what the spec says", "derive the rest", "name these features", "the
  drawing says X but the image looks Y", "keep it editable", "don't hardcode". Do
  NOT use for the parametric mechanism itself (see parametric-patterns) or splitting
  sketches (see sketch-strategy).
version: 0.1.0
freecad-versions: ['1.0', '1.1']
---

## Scope

Encode what the spec *means* into the model so it stays right under edits. This
skill owns design intent: which values are driving parameters versus derived,
expressing relationships as constraints rather than duplicated numbers, naming so the
tree reads like a build plan, and how much to trust each input source. It does not
own the parametric mechanism — spreadsheets, master sketches, VarSet (see
parametric-patterns) — or how sketches are split (sketch-strategy). It owns the
judgment; those own the execution.

This skill guides work you carry out through the **freecad-buddy MCP server** (the
`sketch_*`, `feature_*`, `query_*`, and `verify_*` tools). If those tools aren't
available in your session, install and connect the freecad-buddy MCP first — open
FreeCAD with the freecad-buddy add-on, which auto-starts the server, then point your
MCP client at it — otherwise the model can't be built or checked.

## Decision Rules

- **Dimension what the spec states; derive the rest.** A number the user gave is a
  driving parameter; a number implied by the geometry is computed from those drivers
  — because the stated values are the contract, and deriving them instead means an
  edit to the real intent doesn't propagate.
- Express a relationship as a **constraint, not a repeated number**: symmetry as a
  symmetric constraint, equality as an equal constraint, a derived length as an
  expression on a driver. Two identical literals silently drift apart when one is
  edited; a constraint keeps them tied.
- Record **no hidden numbers**: every meaningful value is a named parameter with a
  clear source (stated, derived, or an explicit assumption), because a literal buried
  in a placement or a feature tells the next reader nothing and can't be traced when
  the part comes out wrong.
- Name every parameter for its **intent in snake_case** — `wall_thickness`,
  `bolt_spacing`, `flange_height` — not `offset2` or `magic_scale`, and encode a unit
  in the name only when ambiguous (`_deg`, `_mm`). A good name lets a reader predict
  what changing it does.
- Give every feature an **intent-bearing name** so the feature tree reads like the
  build plan, because a tree of `Pad`/`Pad001`/`Pocket002` hides the design while
  `base_plate`/`mount_holes`/`lightening_slot` explains it.
- Treat a **dimensioned source as authority over an image proportion**: when prose
  or a drawing gives a number, use it; when only an image is given, its proportions
  are design intent, not a spec — establish scale from one stated dimension and
  record the rest as assumptions.
- **Flag a conflict; don't silently choose.** When two dimensioned sources disagree
  (prose says one value, a drawing callout says another), surface the conflict rather
  than picking one, because a silent choice hides an error the user could have caught.
- Convert every **drawing callout into a parameter and a validation target**:
  `4X Ø12` becomes a hole count, a diameter, and the checks `count == 4`,
  `diameter == 12`. A callout that isn't turned into a check is an unverified claim.
- **Fix the source and regenerate; never patch the output.** The model is the source
  of truth — when a value is wrong, change the parameter or feature and recompute,
  because editing an exported artifact desynchronizes it from the parametric model
  that will overwrite it next time.
- Prefer a parameter that **stays inside a valid range**: a driving dimension should
  have a sensible default and not produce a self-intersecting or impossible model at
  its extremes, because a parameter is only useful if edits to it stay valid.

## Worked Examples

Input: "Bracket, 60×40 base, two M5 holes 40 mm apart, flange 30 mm tall."

Reasoning → intent:
- Drivers (stated): `base_len=60`, `base_wid=40`, `hole_spacing=40`,
  `hole_dia=5.5` (M5 clearance — an assumption, recorded), `flange_ht=30`.
- Derived: hole positions = ±`hole_spacing`/2 about the center (not two literals);
  flange datum offset = a function of `base_len`.
- Relationships as constraints: the two holes symmetric about the origin, so a
  `base_len` edit keeps them centered.
- Names: features `base_plate`, `mount_holes`, `end_flange`. An editor reading the
  tree sees the design.
Verify each stated dimension with `query_mass_properties`/`verify_shape`; nothing is
a hidden literal.

Input: a drawing says "wall 2.0 mm", the reference photo looks thicker.

Reasoning: the drawing is dimensioned, the photo is proportion. Use 2.0 mm as the
driver; treat the photo as intent only. If prose also stated a *different* wall,
flag the conflict rather than averaging.

## Anti-Patterns

- **Deriving a stated dimension.** Symptom: editing the real intent doesn't
  propagate. Why: the stated value became a computed one. Fix: stated values are
  drivers; derive the rest.
- **Duplicated numbers instead of constraints.** Symptom: a once-symmetric part
  goes lopsided on an edit. Why: two literals drifted. Fix: symmetry/equality as a
  constraint or an expression.
- **Hidden literals.** Symptom: a wrong part with no traceable source for the bad
  value. Why: a number was buried in a placement. Fix: every meaningful value is a
  named parameter with a recorded source.
- **Anonymous feature names.** Symptom: a tree nobody can read. Why: default names
  were kept. Fix: name features for intent.
- **Silently resolving a source conflict.** Symptom: the model matches neither
  source and the user never learns why. Why: a conflict was hidden. Fix: flag it.
- **Patching the export.** Symptom: the model and the delivered file disagree. Why:
  the output was edited, not the source. Fix: fix the parameter and regenerate.
