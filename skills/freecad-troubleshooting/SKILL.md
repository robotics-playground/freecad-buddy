---
name: freecad-troubleshooting
track: A
description: >-
  Use when a document, feature, sketch, or export fails and you need to diagnose
  it: reading a recompute error, finding the failing object, running the repair
  loop, and fixing broken references, self-intersecting sketches, failed fillets,
  or wrong-scale geometry. Trigger phrases: "recompute error", "it failed", "broken
  reference", "the object is in error", "why won't this recompute", "dangling
  sketch", "fix this". Do NOT use for planning a build (see design-decomposition)
  or the normal use of a specific feature (see freecad-partdesign).
version: 0.1.0
freecad-versions: ['1.1']
---

## Scope

Diagnose and repair a FreeCAD document that failed, and do it in a disciplined loop
rather than by guessing. This skill owns failure triage: reading the error,
locating the one failing object, classifying the cause, and applying the smallest
fix — plus the recurring failure families (broken reference, invalid sketch,
failed dress-up, wrong scale, missing feature). It does not own the correct normal
use of a feature (freecad-partdesign) or the verification of a *working* part
(verification-thinking). The full symptom → cause → fix catalog lives in
`references/symptom-cause-fix.md`; load it when a failure doesn't match an obvious
class.

You diagnose and repair through the **freecad-buddy MCP server** (the `query_*`,
`verify_*`, `document_*`, and mutation tools named below). If those tools aren't
available in your session, install and connect the freecad-buddy MCP first — open
FreeCAD with the freecad-buddy add-on, which auto-starts the server, then point your
MCP client at it — otherwise none of these repair steps can run.

## Decision Rules

- Run the loop, don't guess: **read the failing output → classify the failure →
  make the smallest responsible change → rerun the failed operation → rerun any
  dependent checks → report remaining risk.** Guessing a fix without classifying
  the cause usually breaks something else and hides the real problem.
- Find the **one failing object** before touching anything, using
  `query_tree_summary` for the tree-wide error states and `query_object` for the
  failing object's status string, because a document reports the specific object
  and reason that failed — fixing the wrong object leaves the real fault in place.
- **Recompute after any abort or undo before you diagnose**, because undo and abort
  restore properties but do not recompute; reading the error state before
  recomputing shows you a stale result, not the current one.
- Make the change at the **source of the fault**, not at the symptom — fix the
  feature, sketch, or datum and recompute; never patch exported geometry, because
  the model is the source of truth and an edited export desynchronizes from it.
- On a **broken reference** (a feature pointing at a face/edge that a recompute
  re-labelled or dropped), re-resolve it against a stable target — a datum plane or
  a geometric-query/mapped-name selector — rather than re-picking another bare
  index that will break again. `verify_references` reporting `UNSUPPORTED` means the
  audit could not run, not that the reference is fine.
- On an **invalid or self-intersecting sketch**, the fault is upstream of every
  feature that consumes it — repair the sketch to fully-constrained and non-
  degenerate first, because a pad or pocket on a broken profile can only fail.
- On a **failed fillet/chamfer**, apply the narrow fixes in order: reduce the
  radius/size below the local geometry, narrow the edge selection, move the dress-up
  later in the chain, or split the edge group by intent — because the cause is
  almost always an oversized radius or edges re-labelled by a prior boolean.
- On **wrong scale or bounding box**, check the parameter values and the units
  first, then measure the critical extents — because the usual cause is a
  units mismatch or a diameter entered as a radius, not a modelling error.
- After a repair that *could* have touched unrelated geometry, compare before and
  after with `verify_fingerprint` and re-run the dependent checks, because a fix
  that "worked" may have silently changed a neighbouring feature.
- When a failure can't be repaired in the current environment, **report it
  honestly**: what failed, what was tried, which artifact is still usable, which
  validation claims can't be made, and the next source-level correction to try.
  A silently-abandoned failure is worse than a reported one.

## Worked Examples

Input: a document with a deliberately broken recompute — a pad whose sketch lost
its external reference.

Diagnosis loop:
1. `query_tree_summary` → the pad and its sketch show an error state; everything
   downstream is also flagged.
2. `query_object` on the sketch → status names the missing external geometry (the
   `?`-marked reference). The *root* is the sketch's dropped reference, not the pad.
3. Smallest fix: re-attach the sketch's external reference to a stable datum or a
   geometric-query selector, not the original bare edge that moved.
4. `document_recompute`, then re-check the sketch is fully constrained and the pad
   is valid.
5. Report: root cause (dropped external reference after a prior recompute), fix
   applied, and that the downstream features now re-resolve.

Input: "The fillet errors after I added a pocket."

Diagnosis: classify as dress-up-after-boolean. The pocket re-labelled the edges the
fillet selected, so the fillet lost (or mis-targeted) its edge list. Fix: move the
fillet after the pocket in the chain and re-select its edges by position/intent,
then recompute and confirm the edge count matches intent.

## Anti-Patterns

- **Guessing a fix without classifying.** Symptom: the change breaks something else
  and the original fault persists. Why: no root cause was found. Fix: read →
  classify → smallest change → rerun.
- **Fixing the wrong object.** Symptom: the error moves but doesn't clear. Why: the
  symptom object was patched, not the upstream fault. Fix: trace to the first object
  in error via the tree and status strings.
- **Diagnosing before recompute.** Symptom: the error state read after an undo/abort
  is stale. Why: undo/abort don't recompute. Fix: recompute first.
- **Re-picking another bare index for a broken reference.** Symptom: the reference
  breaks again on the next recompute. Why: indices reshuffle (TNP). Fix: re-resolve
  to a datum or geometric-query selector.
- **Patching the export.** Symptom: the model and the delivered file disagree. Why:
  the symptom was fixed in the output, not the source. Fix: fix the feature/sketch
  and regenerate.
- **Silently abandoning a failure.** Symptom: a broken result reported as done, or
  as nothing. Why: the failure wasn't surfaced. Fix: report what failed, what was
  tried, and the next correction.
