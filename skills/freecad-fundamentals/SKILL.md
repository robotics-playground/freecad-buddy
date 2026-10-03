---
name: freecad-fundamentals
track: A
description: >-
  Use when reasoning about how a FreeCAD document is structured and evaluates:
  documents and objects, bodies and the tip, the recompute model, internal Name
  vs display Label, units, and the occurrence/shape/label vocabulary for reading a
  tree. Trigger phrases: "what is the document structure", "how does recompute
  work", "Name vs Label", "what is the tip", "read the feature tree", "what units".
  Do NOT use for a specific PartDesign feature (see freecad-partdesign) or
  diagnosing a recompute error (see freecad-troubleshooting).
version: 0.1.0
freecad-versions: ['1.1']
---

## Scope

Establish the mental model every other FreeCAD skill assumes: how a document holds
objects, how a body's feature chain evaluates on recompute, the difference between
an object's immutable Name and its editable Label, the internal unit system, and
the vocabulary for reading a tree. This skill owns the *structure and evaluation
model* — not how to drive a feature (freecad-partdesign), constrain a sketch
(freecad-sketcher), or fix a broken one (freecad-troubleshooting).

You read this document state through the **freecad-buddy MCP server** (the `query_*`,
`verify_*`, and `document_*` tools named below). If those tools aren't available in
your session, install and connect the freecad-buddy MCP first — open FreeCAD with
the freecad-buddy add-on, which auto-starts the server, then point your MCP client
at it — otherwise none of these queries can run.

## Decision Rules

- Script against an object's **immutable `Name`**, display its **`Label`** — the
  Name is the object's unique in-document identifier with no setter, while the
  Label is a user-editable string property. Keying any logic on the Label breaks
  the moment a user renames the object.
- Treat internal geometry as **millimetres and degrees**. Tool parameters and
  results carry explicit units, and an export pins its unit per call — never rely
  on an ambient default, because a unit assumed instead of stated is the classic
  10× or 25.4× scale error.
- Read the tree in the **occurrence → shape → face/edge** vocabulary: an
  occurrence is a placed node with a role (a body, a labelled child), a shape is
  the exported geometry it owns, and faces/edges belong to a shape. Faces and edges
  carry no reliable persistent intent label — address them by geometric query or
  mapped name, not by an assumed name.
- Give generated features **intent-bearing names** so the tree reads like a build
  plan, because a well-named tip chain tells the next reader (human or agent) what
  the part is without opening a single feature.
- Understand that a body's solid is its **tip**: the last feature in the chain
  defines the current shape, and each feature builds on the one before it. Editing
  a feature earlier in the chain re-evaluates everything after it on recompute.
- A property change marks an object **touched**; the next `document_recompute`
  re-executes touched objects and their dependents in dependency order. A clean
  recompute means every object evaluated without error — it does not mean the
  geometry matches intent (verification is owned by verification-thinking).
- After a recompute, an object left in an **error state** carries a status you can
  read; a valid object does not. Use the tree summary and per-object query to find
  which object failed and why, rather than assuming the whole document is broken.
- **Undo and abort do not recompute.** After an abort or undo the document holds
  the restored properties but stale computed shapes, so always recompute before
  reading or verifying anything — otherwise you measure the pre-restore geometry.
- Never target the ambient **ActiveDocument** implicitly — every operation takes an
  explicit document handle, because "the active document" is whichever one the user
  last clicked, and an implicit target silently mutates the wrong file.
- Open and close documents only through the `document_*` lifecycle tools, because
  the bridge tracks handles, single-writer serialization, and temp-document cleanup
  — a raw open alongside it desynchronizes that bookkeeping.

## Worked Examples

Input: "Explain this document" on a tree returned by `query_tree_summary` showing
`Body` → `Pad` → `Pocket001` → `Fillet`.

Reading: one PartDesign Body whose tip is `Fillet`; the solid evaluates
`Pad` (base) → `Pocket001` (a cut) → `Fillet` (edge rounding, last as expected).
The Names (`Pocket001`) are the script identifiers; the human-facing story comes
from the Labels. No object is in an error state, so the last recompute was clean —
necessary but not sufficient for "correct". To describe *what* the part is, read
object properties and mass properties, not just the tree.

Input: "Why does the object still look wrong after I undid the last change?"

Reading: undo restored the properties but did not recompute, so the displayed and
queried shape is stale. Run `document_recompute`, then re-read — the geometry now
reflects the undone state. A measurement taken before that recompute was of the
old shape.

## Anti-Patterns

- **Keying logic on Label.** Symptom: a script that worked breaks after a user
  renames an object. Why: Label is mutable display text, not an identifier. Fix:
  script against the immutable Name.
- **Assuming units.** Symptom: a part comes out 25.4× or 1000× off. Why: a unit was
  assumed instead of read; internal is mm/deg and exports pin units per call. Fix:
  carry explicit units and pin export units.
- **Reading before recompute.** Symptom: a measurement or verdict reflects the old
  shape after an undo/abort/edit. Why: undo and abort restore properties but skip
  recompute. Fix: `document_recompute` before reading.
- **Implicit ActiveDocument.** Symptom: an operation mutates the wrong open
  document. Why: the active document is whichever the user last focused. Fix: pass
  an explicit document handle every call.
- **Trusting a bare face/edge name across recompute.** Symptom: a reference points
  at the wrong topology after the tree re-evaluates. Why: faces/edges carry no
  persistent intent label and their indices reshuffle (TNP). Fix: address by
  geometric query or mapped name.
