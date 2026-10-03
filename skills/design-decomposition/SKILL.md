---
name: design-decomposition
track: B
description: >-
  Use when turning a part spec, sketch, reference image, or 2D drawing into an
  ordered feature plan before any modeling: deciding the base solid, the primary
  sketch plane, additive vs subtractive sequencing, single body vs multiple
  bodies, and what one clarification (if any) to ask. Trigger phrases: "design
  a...", "plan this part", "how should I model", full-part spec text, "break this
  down", ambiguous or under-dimensioned request. Do NOT use for constraining an
  individual sketch (see sketch-strategy) or choosing one feature operation
  (see tool-selection).
version: 0.1.0
freecad-versions: ['1.1']
---

## Scope

Turn a request into an ordered build plan a copilot can execute one feature at a
time. This skill owns the *plan*: what the base solid is, which plane it sketches
on, the order features attach in, and whether the result is one body or several.
It does not own sketch constraint strategy (sketch-strategy) or picking a single
operation like pad-vs-revolve (tool-selection) — it decides the sequence those
operations run in. It also owns the one-question clarification gate and the
extraction of a drawing or image into a modeling brief. Assembly *strategy*
(mating surfaces, degrees of freedom) is out of scope for now; here you only
decide part-vs-assembly and hand a body list downstream.

The plan you produce is executed through the **freecad-buddy MCP server** (the
`query_*`, `verify_*`, and `sketch_*`/`feature_*` tools the plan hands to). If those
tools aren't available in your session, install and connect the freecad-buddy MCP
first — open FreeCAD with the freecad-buddy add-on, which auto-starts the server,
then point your MCP client at it — otherwise the plan can't be built.

## Decision Rules

- Pick the construction that makes the spec's controlling dimensions **direct
  parameters**, because a dimension the user stated should be a driving value, not
  something derived. Profile-driven shapes → one closed sketch plus a single
  pad/revolve/sweep/loft; block-and-feature parts → a base solid plus subtractive
  features.
- Choose the base solid and its sketch plane from the **functional datum** —
  the mounting face, mating interface, or symmetry axis — before planning
  features, because the frame you model in is the frame every later reference and
  measurement lives in.
- Order features so fragile steps land last and a failure points at one feature:
  **base solid → major additions → subtractive features → shell → through-wall
  holes → fillets and chamfers last.** Fillets are the most failure-prone step and
  every prior boolean re-labels the edges a fillet selects, so postponing them
  keeps selectors valid and localizes blame (fillet failure modes: see
  freecad-partdesign).
- Make each planned feature a **named step** with an intent-bearing name, because
  the feature tree should read like the build plan and a parameter edit should
  touch one obvious place.
- Decide single body vs multiple bodies before modeling: parts that are
  separately manufactured, purchased, or movable are separate bodies; one
  monolithic manufacturing intent is one fused solid. Never emit an unlabeled
  multi-body result — traceability in `query_tree_summary` depends on names.
- Plan references defensively: a later feature that attaches to a face or edge
  should target a **datum plane or a geometric-query/mapped-name selector**, not a
  bare `Face6`, because indices reshuffle on recompute (TNP). Prefer creating a
  datum early over referencing a face that a later boolean will invalidate.
- When a technical drawing drives the model, read the title block (units,
  projection) and map each view to a model axis **before** extracting numbers, then
  convert every callout into a named parameter and a validation target — because a
  drawing is a dimensioned contract, and every callout must end up checkable by
  `verify_shape`/`query_mass_properties` or explicitly reported as unverified.
- A reference image without stated dimensions is **design intent, not a spec**:
  establish scale from one stated dimension or a known object, estimate the rest,
  and record every estimate as an assumption.
- When sources conflict, dimensioned beats proportion, and two conflicting
  dimensioned sources get **flagged, not silently resolved** — a silent choice
  hides an error the user could have caught.
- Ask exactly **one** clarification only when the answer changes the geometry and
  can't be assumed: no dimensions and no scale reference, a mating interface named
  but unspecified, a safety/load/pressure/compliance-critical part, or a missing
  source file. Otherwise proceed with stated assumptions — asking for a defaultable
  clearance hole, a cosmetic fillet radius, or a choosable origin wastes a turn.

## Worked Examples

Input: "Design a mounting bracket: 60×40×5 mm base plate, two M5 through-holes
40 mm apart, one perpendicular flange 30 mm tall with a 10 mm lightening slot."

Reasoning → plan:
1. Base solid = the 60×40×5 plate; sketch on XY, functional datum = the mounting
   face (plate underside), origin at plate center so the hole pattern is symmetric.
   Controlling params: `plate_len=60`, `plate_wid=40`, `plate_thk=5`,
   `hole_spacing=40`, `hole_dia=5.5` (M5 clearance).
2. Two through-holes next (subtractive), positioned from `hole_spacing` about the
   center — not from a plate edge, so they stay symmetric under a length edit.
3. Flange = a second pad on a datum plane at the plate end (create the datum
   early; don't reference the plate's end face, which the holes' recompute could
   re-label). `flange_ht=30`.
4. Lightening slot = subtractive pocket on the flange. `slot_len=10`.
5. No fillets requested → none planned. One body (monolithic bracket).
No clarification needed: M5 clearance is defaultable, origin is choosable-and-
reported. Verification targets handed down: bbox ≈ 60×40×35, 2 holes Ø5.5 at 40 mm
spacing, flange perpendicular, one valid solid.

Input: a 2D drawing, front view labelled "Ø12 THRU, 4X", title block "mm, third-
angle".

Reasoning: units = mm (from title block, not assumed); "4X Ø12 THRU" → one pocket
feature patterned 4× → parameters `hole_dia=12`, `hole_count=4` → validation
targets `count_cylindrical_holes == 4`, `hole_diameter == 12`. Map the front view
to the XY face before reading positions. Any position dimension missing from the
drawing is reported as unverified, never scaled off the image.

## Anti-Patterns

- **Planning fillets early.** Symptom: a later boolean fails or its edge selector
  breaks. Why: booleans re-label edges, invalidating the fillet's selection. Fix:
  fillets/chamfers are the last planned step.
- **Modeling before choosing the origin.** Symptom: alignment and hole-symmetry
  checks are ambiguous downstream. Why: an arbitrary origin means every relative
  measurement has an arbitrary reference. Fix: fix the functional datum first.
- **Deriving a stated dimension.** Symptom: the user edits "plate length" and the
  hole spacing doesn't follow, or vice versa. Why: the controlling dimension became
  a computed value instead of a parameter. Fix: choose the construction that makes
  stated dimensions direct parameters.
- **Referencing a face a later step invalidates.** Symptom: `verify_references`
  reports BROKEN/REPOINTED after recompute. Why: a bare face index moved when the
  tree recomputed (TNP). Fix: attach to a datum plane or a geometric-query selector.
- **Unlabeled multi-body output.** Symptom: `query_tree_summary` shows anonymous
  solids; inspection can't tell which is which. Why: bodies with no intent names
  lose traceability. Fix: name every body from its role.
- **Asking a question you could assume.** Symptom: a turn spent asking for a
  clearance-hole size or a cosmetic fillet. Why: the answer was defaultable and
  reportable. Fix: proceed with a stated assumption; reserve the one question for
  fit/safety/missing-source cases.
