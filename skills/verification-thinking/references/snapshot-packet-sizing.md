# Snapshot packet sizing

Read this when deciding how many `query_screenshot` views a part needs and which
camera angles and display modes to request. The screenshot is a constructed-scene
render: it never mutates the document or the user's live viewport, so composing a
focused view is free — you reduce noise by choosing what to render, not by hiding
model geometry.

## How many views

**One view** (a single iso) is enough for a simple static part — a plate, a block,
a bracket with holes on one face.

**A small multi-view packet** is warranted when a semantic error is plausible from
the part's complexity or the prompt's intent:

- more than one body, or an assembly
- holes on multiple faces or multiple axes
- shells, internal cavities, bores, passages, open enclosures, section-critical
  features
- ribs, gussets, bosses, standoffs, slots, cutouts, lightening holes, fins,
  blades, or repeated patterns
- a re-render after a geometry/boolean/selector/feature repair
- prompts where "looks like the requested object" is part of the task
- deterministic checks passed but the visible semantics are still uncertain

## The standard packet

Request four views:

- **iso** — gestalt, feature presence, orientation
- **opposite iso** (camera direction roughly mirrored) — the two opposed
  isometrics guarantee every face appears in at least one image, so rear, left, and
  bottom features are covered by default rather than by suspicion
- **top ortho** — the primary pattern/symmetry check
- **front ortho** — the profile check

Use `query_screenshot`'s view control (include/exclude objects, per-object
transparency, focus-on-element, camera preset) to keep the subject readable — e.g.
ghost context parts at high transparency while inspecting a flange, or focus the
camera on one hole's bounding box. All view control is scene composition; it does
not touch `Visibility` or the document.

## Size

Request `view.width` and `view.height` of **800** by default. The tool default is
1920 (also the maximum), and every image travels through the agent's context; 800 px
shows feature presence, orientation, and placement at a fraction of that cost.

Go above 800 only for a **review-directed image**, and never request more than 1920
from `query_screenshot` — that is its cap. The AD-21 ≥ 2048 px legibility floor
applies to the review-directed visual set (the images a reviewer reads dimensions
from), which `query_screenshot` does not produce; the 800 px default never lowers
that floor.

## Targeted additions

Add a view only when the brief or a failure mode calls for it:

- **section** — for a shell, bore, internal cavity, passage, blind hole,
  enclosure, or a wall/floor relationship
- **transparent** display — overlap, collision, enclosure readability, or hidden
  contact checks
- **wireframe / hidden-edge** display — internal overlap, hidden interference, or
  assembly collision suspicion
- **reference-image reproduction** — one view from the reference image's
  viewpoint for side-by-side comparison

## Don't loop

Re-render only when a source repair changed visible geometry or a specific visual
finding needs confirmation. Repeated snapshots of an unchanged part add no
information.

## Every visual finding becomes a measurement

A packet is diagnostic. Before any observation counts as a validation claim,
convert it into a deterministic check:

- hole pattern looks asymmetric → measure hole centers, compare offsets
  (`query_placement`)
- lid / child / occurrence looks offset → check the frame delta (`query_placement`)
- gusset / boss / standoff / rib looks floating → check solid count, labels, and
  contact distance (`query_mass_properties`, `query_dependencies`)
- cavity / bore / blind hole looks wrong → section view, then measure wall
  thickness, depth, or through-condition
- repeated pattern looks uneven → measure pattern centers or angular spacing

The measurement is the result; the render only told you where to point it.
