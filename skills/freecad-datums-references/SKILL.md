---
name: freecad-datums-references
track: A
description: >-
  Use when choosing what a feature references: creating datum planes/axes/points or
  a local coordinate system, deciding a part's origin and orientation, or defending
  against broken references by attaching to datums instead of faces/edges (TNP
  defense). Trigger phrases: "datum plane", "reference axis", "local coordinate
  system", "what origin", "attach to", "broken reference after recompute", "TNP".
  Do NOT use for constraining a sketch (see freecad-sketcher) or the mutation
  transaction/audit itself (see verification-thinking).
version: 0.2.0
freecad-versions: ['1.1']
---

## Scope

Choose durable references and a sound part frame. This skill owns datum features
(planes, axes, points, local coordinate systems), the choice of a part's origin and
orientation, and the discipline of referencing datums instead of raw faces/edges to
survive recompute (the topological-naming problem). It does not own sketch
constraints (freecad-sketcher) or the verification of references after a mutation
(verification-thinking) — it owns *what to attach to* so those audits stay clean.
Part-type origin defaults live in `references/part-local-origin-defaults.md`.

This skill drives FreeCAD through the **freecad-buddy MCP server** (the `query_*`,
`verify_*`, and `feature_*` tools named below). If those tools aren't available in
your session, install and connect the freecad-buddy MCP first — open FreeCAD with
the freecad-buddy add-on, which auto-starts the server, then point your MCP client
at it — otherwise none of these steps can run.

## Decision Rules

- Pick a part's **origin and orientation from its functional datum** — the mounting
  face, mating interface, or symmetry axis — before modeling, because the frame you
  model in is the frame every later measurement, alignment check, and reference
  lives in; an arbitrary origin makes every downstream check ambiguous.
- Reference a **datum plane or axis over a model face or edge** whenever a later
  feature needs an attachment, because face/edge indices reshuffle when the tree
  recomputes (TNP) while a datum is a stable, named object that does not move. A
  datum created early is cheaper than a reference repaired later.
- When you must reference model topology, address it by **geometric query or mapped
  name**, never a bare `Face6`/`Edge3`, because a stored index silently points at
  different geometry after a recompute. Resolve a bare index at call time; never
  persist it.
- Create the datum **early**, before the features that will attach to it, because a
  datum built on top of geometry a later boolean invalidates is itself fragile —
  anchor datums to the base solid or the origin, not to a face a downstream cut will
  re-label.
- Keep visual, collision, and reference frames **distinct in your head**: the frame
  a feature is measured in, the frame it attaches at, and the part's own origin are
  not automatically the same. Name which frame a value is expressed in, because a
  number without its frame is the classic silent placement error.
- After any mutation that could touch a reference, read the reference audit in
  `mutation.post_verify.tnp_audit` and treat a re-pointed, dropped, or `?`-marked reference as a failure, and an `UNSUPPORTED`
  result as *not clean* — a silently re-pointed reference recomputes fine and is
  still a corrupted model.
- Use a **local coordinate system** when a sub-assembly or a repeated feature group
  needs its own frame, so its internal placements are expressed relative to one
  named origin rather than scattered global offsets that break when the group moves.
- Put every meaningful offset in a **named parameter**, not a literal buried in a
  placement, because a datum at `Location(30, 17.5, 0)` tells the next reader
  nothing, while `bolt_offset_x`/`bolt_offset_y` say what it is and edit in one place.

## Worked Examples

Input: "Add a flange on the end of this plate that references the plate end."

Reasoning: don't attach the flange sketch to the plate's end *face* — a later hole
or fillet recompute can re-label it. Instead: create a datum plane at the plate end,
offset from the origin by a `plate_len` parameter, and sketch the flange on the
datum. Now the flange survives edits to the holes, and `post_verify.tnp_audit`
stays `CLEAN` because the reference is a stable datum, not a moving face index.

Input: "The bracket's holes broke after I added a pocket."

Reasoning: the holes referenced a face the pocket re-labelled (TNP). Fix by
re-resolving the hole positions against a datum or a geometric-query selector rather
than re-picking another bare index — see `references/part-local-origin-defaults.md`
for choosing the anchoring frame per part type.

## Anti-Patterns

- **Modeling before choosing the origin.** Symptom: alignment and symmetry checks
  are ambiguous. Why: an arbitrary origin gives every relative measurement an
  arbitrary reference. Fix: fix the functional datum first.
- **Attaching to a face a later step invalidates.** Symptom: `post_verify.tnp_audit`
  reports `BROKEN`/`REPOINTED` findings after recompute. Why: the face index moved (TNP). Fix:
  attach to a datum plane created early.
- **Storing a bare `Face6`.** Symptom: a reference points at the wrong topology
  after a recompute. Why: indices reshuffle. Fix: address by geometric query or
  mapped name; resolve indices only at call time.
- **A number without its frame.** Symptom: a feature lands in the wrong place
  despite "correct" coordinates. Why: the value was expressed in a different frame
  than assumed. Fix: state which frame every placement value is in.
- **Treating `UNSUPPORTED` reference audit as clean.** Symptom: a silently
  corrupted model passes. Why: no-element-map read as no-problem. Fix: `UNSUPPORTED`
  is not a pass.
