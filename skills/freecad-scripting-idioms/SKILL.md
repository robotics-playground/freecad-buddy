---
name: freecad-scripting-idioms
track: A
description: >-
  Use when reasoning about FreeCAD's API behavior while driving it through tools:
  object naming and identity, recompute timing, when properties are fresh to read,
  property value types and units, and headless vs GUI differences. Trigger phrases:
  "why is the property stale", "Name vs Label in code", "when do I recompute",
  "does this work headless", "the value didn't update", "object identity". Do NOT
  use for the document/recompute mental model at a conceptual level (see
  freecad-fundamentals) or diagnosing a specific error (see freecad-troubleshooting).
version: 0.1.0
freecad-versions: ['1.0', '1.1']
---

## Scope

Avoid the API-level gotchas that bite when you drive FreeCAD programmatically. This
skill owns the idioms and timing traps: object identity and naming, when a property
is safe to read, value types and units on the wire, and where headless behavior
differs from the GUI. It sits below freecad-fundamentals (the conceptual document
model) and beside freecad-troubleshooting (fixing failures) — this one is about
*driving the API correctly the first time* so fewer failures happen.

This skill drives FreeCAD through the **freecad-buddy MCP server** (the `query_*`,
`verify_*`, `document_*`, and mutation tools named below). If those tools aren't
available in your session, install and connect the freecad-buddy MCP first — open
FreeCAD with the freecad-buddy add-on, which auto-starts the server, then point your
MCP client at it — otherwise none of these steps can run.

## Decision Rules

- Identify an object by its **immutable Name**, show its **Label**, because Name is
  the unique in-document identifier that never changes, while Label is user-editable
  display text; any lookup keyed on Label breaks the instant a user renames the
  object.
- **Recompute before you read a computed property**, because a mutation marks
  objects touched but does not re-evaluate them until a recompute — reading a shape,
  volume, or bounding box before `document_recompute` gives you the stale
  pre-mutation value. Prefer the mutation tools' built-in recompute over reading
  raw.
- After an **undo or an abort, recompute again before reading**, because undo/abort
  restore properties but skip recompute, so the computed geometry lags the restored
  state until you force it.
- Read a property's value **with its explicit unit** — internal lengths are
  millimetres and angles are degrees, and every tool result carries units — so never
  compare a raw number against a value in unknown units; that is the classic scale
  bug.
- Know a property's **type before you set it**: a length is a quantity with a unit,
  an enum is one of a fixed set of members (which do not always match the GUI
  dropdown order), and a reference is a link, not a string. Confirm an enum member
  with `query_object` rather than guessing it.
- Drive every mutation through the **typed tools** (`sketch_*`, `feature_*`,
  `document_*`), never through free-form code, because the typed path runs the
  transaction, verification, and reference audit around the change — raw execution
  bypasses all of it and leaves an unverified, possibly corrupt document.
- Take an **explicit document handle** on every call; never rely on the active
  document, because "the active document" is whichever the user last focused and an
  implicit target silently drives the wrong file.
- Assume **headless and GUI must behave identically** for anything that isn't a
  render: the same tools run in both, and a check that only passes with the GUI open
  isn't a real pass. Renders are the one capability that may be unavailable headless
  — treat an absent render as "unavailable", never as a failure of the geometry.
- Address sub-elements by **geometric query or mapped name**, resolving any bare
  index at call time, because indexed names (`Face6`) are valid only until the next
  recompute reshuffles them; never store an index for later reuse.

## Worked Examples

Input: "I set the pad length but `query_mass_properties` shows the old volume."

Reasoning: the length property is set and the object is touched, but the shape
hasn't re-evaluated. Run `document_recompute` (or use the mutation tool that
recomputes as part of its transaction), then re-query. The pre-recompute read was of
the stale shape — expected, not a bug.

Input: "My lookup by name stopped finding the object."

Reasoning: the code keyed on the Label, and the user renamed it. Switch the lookup
to the immutable Name; treat the Label as display-only. If you need a durable
human-facing handle, give the feature an intent-bearing Name when you create it.

## Anti-Patterns

- **Reading a computed property before recompute.** Symptom: a stale volume or
  bbox. Why: the mutation touched but did not re-evaluate. Fix: `document_recompute`
  first (or let the mutation tool do it).
- **Keying lookups on Label.** Symptom: a lookup fails after a rename. Why: Label is
  mutable. Fix: identify by immutable Name.
- **Free-form execution for a mutation.** Symptom: an unverified or corrupt document
  that recompiled fine. Why: raw code bypassed the transaction/verify/audit wrapper.
  Fix: use the typed `sketch_*`/`feature_*`/`document_*` tools.
- **Guessing an enum member.** Symptom: a feature does the wrong thing silently.
  Why: FreeCAD enum members don't always follow the GUI order. Fix: confirm with
  `query_object`.
- **Assuming headless mirrors GUI for renders.** Symptom: a render check "passes"
  only with the GUI open. Why: render capability can differ headless. Fix: treat an
  unavailable render as unavailable, and gate real correctness on geometry, not the
  picture.
