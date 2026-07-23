# Sprint Change Proposal — 2026-07-23

## Section 1: Issue Summary

Full-automation testing of the FreeCAD MCP bridge (H1 headless harness) surfaced four
verification bugs during Epic-1 hardening. All were fixed and verified in code (223 external +
73 in-FreeCAD tests + 29/29 harness checks, stderr clean). This proposal aligns the design
artifacts that still described the **superseded** behavior, so the docs match shipped, verified
code.

Discovered while building `scripts/automation/run_mcp_e2e.py` and re-running the golden-model
sweep with real geometry.

## Section 2: Impact Analysis

- **Epic impact:** none — no scope/plan change. Epic 1 stories unchanged.
- **Story impact:** none — the affected code is already implemented and passing.
- **Artifact conflicts:** 3 design docs described behavior the fixes replaced (hard drift), plus
  one imprecise band formula (soft).
- **Technical impact:** documentation-only. Code, tests, and CI are already green.

## Section 3: Recommended Approach

**Direct Adjustment** (Minor scope). Edit the four drifted design statements to match code. No
rollback, no MVP change. Effort: minutes; risk: none (docs follow verified code); timeline: nil.

## Section 4: Detailed Change Proposals

### D1 — Euler check — `design/verification-design.md` §6.3

OLD: `mesh.volume` within the deflection-derived band (§8 — never ±0.1 %), sane `euler_number`
/ **expected genus**.

NEW: … and an **even** `euler_number`. A closed orientable surface has even Euler
characteristic (Σ 2−2g over its bodies); an odd value signals non-closed/non-manifold. A
*specific* genus is NOT required — a through-hole part (χ=0) and a multi-body compound (χ=4) are
valid exports; flipped-normals detection comes from `is_volume`, not Euler.

Rationale: requiring `euler==2`/expected-genus falsely rejected valid genus-1 and multi-body
meshes. `export_oracle._trimesh_checks` now checks `euler % 2 == 0`.

### D2 — Read-only-after-render invariant — `design/data-contracts-design.md` §10

OLD (implied): read-only verdict = `digest` equality; `massprops` only a human-diffable
cross-oracle on mismatch.

NEW: added a normative paragraph — a read-only-after-render check compares
`massprops_equal(before, after)` (volume/area/COM/principal-moments), NOT the digest. OCCT
re-serializes a loaded shape's BRep bytes on first render touch, so the digest shifts while
geometry is unchanged; `bbox` is excluded as tessellation-derived.

Rationale: `screenshot._render_with_lifecycle` uses `massprops_equal`; a digest compare gives a
false "changed" verdict (`contracts/fingerprint.py::massprops_equal`,
`_INVARIANT_MASSPROP_KEYS`).

### D3 — Screenshot render object set — `design/integration-mcp-freecad.md` §6

OLD: default renders "all-visible-minus-excluded" via `subgraphFromObject(obj)` — silent on
containers/datum.

NEW: default set additionally excludes container/datum types (`PartDesign::Body`,
`App::Origin`/`Line`/`Plane`/`Point`) whose headless subgraph faults (Access violation that
corrupts Coin for later objects, so it can't be caught+recovered); leaf shape features render
instead; explicit `include` overrides. Added an inline comment at the `visible_objects` loop.

Rationale: `subgraphFromObject(PartDesign::Body)` crashes headless; `screenshot._object_list`
now filters via `_is_default_renderable`.

### D4 — Mesh volume band formula — `design/verification-design.md` §8 (soft)

OLD: band "derived from tessellation deflection (linear + angular)".

NEW: `(2/3) · linear_deflection · surface_area` (chordal-sag bound), never bbox-relative,
never ±0.1 %. Note explains a bbox-relative band under-bounds doubly-curved surfaces ~3×.

Rationale: `exports.mesh_volume_band(linear, area)`; the prior bbox-relative band was too tight
for spheres/cylinders.

## Section 5: Implementation Handoff

- **Scope:** Minor.
- **Recipient:** Developer (self) — edits applied directly in this run.
- **Success criteria:** the four design statements match shipped code; no other artifact
  references the superseded euler/digest/render-set claims (verified by grep — none remain).

## Not drifted (verified consistent)

Compound `CenterOfMass` null-guard (envelope already lists COM optional); `ActiveDocument` ban
(matches AD-20 in `contracts/document.py`); AD-9 oracle split; band "never ±0.1 %" rule.
