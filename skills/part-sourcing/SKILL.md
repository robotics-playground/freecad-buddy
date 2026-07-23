---
name: part-sourcing
track: R
description: >-
  Use when finding and bringing in an off-the-shelf part: searching a catalog for a
  named screw, bearing, motor, connector, or standoff, importing its STEP file
  through the bridge, and placing it with measured mating frames. Trigger phrases:
  "find an M3 screw", "add an SG90 servo", "source a bearing", "import this
  off-the-shelf part", "off-the-shelf STEP", "catalog part", "purchasable
  component". Do NOT use for modeling a custom part (see design-decomposition) or
  exporting a robot description (see urdf-export).
version: 0.1.0
freecad-versions: ['1.0', '1.1']
---

## Scope

Bring a purchasable off-the-shelf part into a design correctly. This skill owns the
sourcing flow: searching an external catalog for a named component, importing its
STEP through the bridge, and placing it with frames measured from its real geometry.
It does not own modeling a custom part (design-decomposition) or exporting a robot
description (urdf-export). The catalog *search* is an external concern; this skill's
discipline is that *import and placement* go through the bridge and never trust an
imported part's assumed origin.

This skill drives FreeCAD through the **freecad-buddy MCP server** (the document
import path plus `query_mass_properties`, `query_object`, and `query_placement`).
These are Phase-5 capabilities — if they aren't available in your session, the
sourcing/import tools aren't installed yet; install and connect the freecad-buddy
MCP (open FreeCAD with the add-on, which auto-starts the server, then point your MCP
client at it) and confirm the Phase-5 tool set is present.

## Decision Rules

- Search the catalog with **specific-but-not-overconstrained** terms first (the
  standard designation, size, and family), then narrow, because a query that's too
  broad returns noise and one that's too narrow misses the near-match — for a model
  number, retry likely aliases and vendor names before declaring a miss.
- Prefer the **real off-the-shelf STEP** over a simplified placeholder when an
  exact or near-exact match exists, because a real part carries correct mating
  geometry a stand-in doesn't — drop to a documented simplified envelope only when
  no match exists and an assembly-time reason justifies it, and record the miss.
- Import a sourced part **only through the bridge's document/import path**, never a
  raw open alongside it, because the bridge tracks the document handle,
  single-writer serialization, and cleanup — a side import desynchronizes that
  bookkeeping.
- **Measure an imported part before trusting its frames.** Its origin and
  orientation were authored elsewhere and are not assumed — run
  `query_mass_properties` and `query_placement` on it, then derive its mating frames
  (mounting face, bolt-pattern center, shaft axis) from the measured geometry, not
  from a guessed origin.
- Place the part by a **datum or a geometric-query selector**, not a bare face
  index, because an imported part's topology gives you no persistent intent labels
  and an index reshuffles on recompute (TNP) — anchor to what you measured.
- Verify the placed part **matches its interface**: after placing, check the mating
  face is flush or the screw axis is coaxial with `query_placement` deltas, because
  a placement that looks right can be off by a frame the part carried.
- Record **provenance and license** for any part you ship as a fixture — the catalog
  id, source URL, and license — because off-the-shelf geometry carries terms, and a
  shipped benchmark or golden model must be commercial-clean.
- Treat a catalog's data as **evidence, not a stable contract**: if a returned
  record is missing a field or conflicts, report the gap rather than turning it into
  a silent pass — an unmeasured attribute is unverified.

## Worked Examples

Input: "Add an M3×12 socket-head cap screw to this bracket's corner holes."

Reasoning → sourcing:
1. Search: `M3 SHCS 12` (specific, not overconstrained). If empty, retry the
   standard designation (ISO 4762) and common aliases before treating it as a miss.
2. Import the matched STEP through the bridge's document/import path (not a raw
   open), returning a handle.
3. Measure: `query_mass_properties` + `query_placement` on the imported screw →
   locate its shaft axis and head-seat face from geometry, not its assumed origin.
4. Place: align the screw's shaft axis coaxial with each corner hole via a
   geometric-query selector, not a face index.
5. Verify: `query_placement` delta confirms the head seats flush and the axis is
   coaxial. Record the catalog id + license if the assembly is a shipped fixture.

Input: "Source an SG90 servo but the exact model isn't in the catalog."

Reasoning: retry aliases (`SG-90`, `9g servo`, the vendor name) and the servo family
facet before giving up. If still no match, record the miss and use a documented
simplified envelope with its stated dimensions — never a guessed one presented as
the real part.

## Anti-Patterns

- **Placeholder when a real part exists.** Symptom: an assembly with wrong mating
  geometry. Why: a stand-in was used instead of the catalog STEP. Fix: prefer the
  real off-the-shelf STEP; envelope only on a recorded miss.
- **Raw import beside the bridge.** Symptom: desynchronized document state. Why: the
  part bypassed the tracked import path. Fix: import through the document/import path.
- **Trusting the imported origin.** Symptom: the part lands in the wrong place or
  orientation. Why: its authored origin was assumed. Fix: measure geometry and derive
  mating frames.
- **Placing by face index.** Symptom: the placement breaks after a recompute. Why:
  an imported face index reshuffled (TNP). Fix: anchor to a datum or geometric-query
  selector.
- **Shipping without provenance.** Symptom: a fixture with unclear license. Why: the
  catalog source wasn't recorded. Fix: record id, source, and license for shipped
  parts.
- **Silently passing missing catalog data.** Symptom: an unverified attribute
  reported as fact. Why: a gap in the record was ignored. Fix: report the gap; an
  unmeasured attribute is unverified.
