---
title: 'query_section tool'
type: 'feature'
created: '2026-11-24'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '90303e36100208aee86ccb67214115d0c6c5a4e2'
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/.knowledge-base/technical/standards/freecad/source-verify.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** An agent that needs the cross-section of a part at a plane runs `Shape.slice` or `Shape.section` in `script_exec` (CAP-1). `Shape.slice` returns no wires for a plane within 1e-5 mm of a face and for a plane on the bottom face, and an empty list reads as "plane misses" (a measured false pass).

**Approach:** New read-only tool `query_section` cuts one solid object with a plane and returns wire counts, area, length, bounding box and optional capped polylines. Numbers only (AD-35). Schema is new, so additive (AD-28).

## Boundaries & Constraints

**Always:** Input `doc`, `object`, `plane {normal, offset}`, optional `points {deflection, max_points}`. `normal` is `"x"`, `"y"`, `"z"` or `[nx,ny,nz]` (finite, non-zero, normalised by the tool); the plane is `normal . p = offset` (offset a mm Quantity) in the object's own shape frame (container-local, like `query_interference`). `points.deflection` is a mm Quantity, required, at least 1e-6 of the shape bounding-box diagonal (a deflection of 0 hangs `discretize`); `max_points` is an integer 1 to 5000, default 1000. Cut with `Shape.section` against a plane face on a copy of the shape (copies keep the document fingerprint unchanged); `slice` is never used. Output `wires`, `closed_wires` (`isClosed()`), `length` (sum of wire lengths, mm), `bbox` (same record as `query_mass_properties`), `area` (mm^2, from `Shape.common` of the plane face, so holes and islands are right). `area` is null when closed wires exist and `common` raises or returns nothing, and always null for a shape that is not solids only (shell, face): unmeasured, never 0. A plane that misses gives `OK` with `wires` 0, `closed_wires` 0, `area` 0, `length` 0, `bbox` null. With `points`: `polylines` (each wire discretised, `[[x,y,z],...]` in mm, wire order) and `truncated`; polylines stop once `max_points` points are returned and `truncated` is true when any point or wire is left out. A valid shell or face is cut too (decision 29). An invalid shape, a solid with non-positive volume (reversed), or a shape with no face (wire, edge) returns `INVALID_INPUT` with `detail.code` `section.untrusted_shape`. A shape above 10,000 faces returns `INVALID_INPUT` with `detail.code` `section.too_complex` before any cut (the limit is the measured cost beside the constant). Unknown object, no or empty shape, bad plane or points → `INVALID_INPUT`. Tool is added to `READ_ONLY_PROFILE`; design document gets the §2 row, §3 schema, counts.

**Never:** Return a pass or verdict (AD-35). Mutate the document or touch the viewport. Import FreeCAD outside the AD-1 whitelist. Add a status value. Change other tools' behaviour.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Box mid | 10x20x30 box, z, offset 15 | wires 1, closed 1, area 200, length 60, bbox z 15..15 | N/A |
| Near face | offset 1e-7 or 0 or 30 | same counts as mid (section, not slice) | N/A |
| Hole | plate with one hole | wires 2, area = plate minus hole | N/A |
| Miss | offset 40 | wires 0, area 0, bbox null | N/A |
| Oblique | normal [1,1,1] | wires 1, area equals analytic value | N/A |
| Polylines | `points` on sphere section | polylines present, point count <= max_points | N/A |
| Cap | `max_points` 5 on a circle | 5 points, `truncated` true | N/A |
| Bad plane | normal [0,0,0], bad string, non-finite offset | none | `INVALID_INPUT` |
| Bad points | deflection 0, below floor, max_points 0 or over 5000 | none | `INVALID_INPUT` |
| Shell | valid closed shell | wires and length measured, `area` null | N/A |
| Untrusted shape | wire, invalid or reversed solid | none | `INVALID_INPUT` `section.untrusted_shape` |
| Too complex | over 10,000 faces | none | `INVALID_INPUT` `section.too_complex` |
| Unknown / no shape | missing name, empty compound | none | `INVALID_INPUT` naming it |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/queries.py:748` -- `_interference_shape` (resolve, null/empty check, `.copy()`): rename to a generic name and reuse. `_is_measurable_solid` (`:777`), `_too_complex_envelope` (`:833`; extract `_refusal_envelope(code, message)` and delegate), `_quantity` (`:120`), `_ok_envelope` (`:31`), mass bbox record (`:603`), `shim.displayed` for text.
- `src/freecad_buddy/hosts/tool_catalog.py:1038` (`READ_ONLY_PROFILE`), `:1273` spec pattern after `query_interference`; `_LENGTH_QUANTITY_SCHEMA` (`:234`). `timeout_s` 60.
- `mcp-tools-design.md` §2 row after `query_interference` (`:132`), new §3.2.4 after §3.2.3, counts table.
- Tests: `tests/infc/test_query_tools.py` (new `QuerySectionTest`), `tests/external/test_mcp_surface.py:61`, `tests/external/test_assistant_readonly_profile.py:47` add the name.
- FreeCAD source: `TopoShapePyImp.cpp:755` (`slice` via `CrossSection`, `CrossSection.cpp:131` cut by half-space), `Part.Plane.toShape`, `Shape.section`, `Shape.common`.
- Do not change: other tool specs, `shape_metrics`.

## Tasks & Acceptance

**Execution:**
- [x] `queries.py` -- `query_section`, plane/points validation, shape trust and face-limit guards, polyline cap, summary; rename shared helper; `_refusal_envelope`
- [x] `tool_catalog.py` -- spec, schema, description, `READ_ONLY_PROFILE`
- [x] `mcp-tools-design.md` -- §2 row, §3.2.4 schema, counts
- [x] `tests/infc/test_query_tools.py`, two `tests/external` lists -- one test per matrix row, fingerprint unchanged, dispatch test

**Acceptance Criteria:**
- Given a box and offsets 0, 1e-7, 15, 30, when sectioned, then each reads wires 1 and area 200 (analytic).
- Given an invalid or reversed solid, when sectioned, then `section.untrusted_shape`, never `wires: 0`.
- Given a catalog, when `gen_schemas --check`, `check_imports`, `ruff` and `pytest tests/external` run, then all pass.

## Implementation Notes

Probe (FreeCAD 1.1.4 freecadcmd): box 10x20x30, `slice(z, d)`: d 1e-7, 1e-6, 1e-5 and 30-d return 0 wires, d 1e-4 and above return 1, d 0 returns 0 and d 30 returns 1; `section` with a plane face returns 1 closed wire at every offset. `discretize(Deflection=0)` never returns. Section + `common`, plates and compounds: 1,600 separate boxes (9,600 faces) 1.7 s + 4.7 s; 3,200 boxes (19,200 faces) 7.4 s + 16 s; 6,400 boxes 25 s + 51 s; 784-hole plate (790 faces) 0.1 s + 0.8 s; 3,000 cylinders (9,000 faces) 1.1 s + 4.6 s. Overlapping or touching solids inside one compound pass `isValid()` and give a wrong `common` area (not detected, as in `query_interference`). Added after review: `common` with 3,000 holes 21 s and 9,000 holes 103 s (9,006 faces), so the area is skipped above 1,500 wires.

## Spec Change Log

Review round 1 (deviations from the frozen text, approved scope unchanged): (a) `max_points` minimum is 2, not 1, because a one-point polyline is not a line and the cap logic never returns one; (b) `area` is also null above 1,500 wires (`_MAX_AREA_WIRES`) because `Shape.common` took 103 s on a plate with 9,000 holes under the 10,000-face limit; (c) `area` is 0 only when `wires` is 0 (a face or open shell with open wires gives null); (d) the frame reads "the object's container: own `Placement` applied, container's not"; (e) the face limit is checked on the object's own shape before the copy and `isValid`; (f) plane normals are scaled by the largest component before normalising, because a normal near the float limit reached `Part.Plane` as a zero vector and aborts the process, and JSON integers beyond float range give `INVALID_INPUT`.

## Review Triage Log

Lenses: Blind Hunter ac765520a554447e9 (opus, high), Edge Case Hunter a38cb940b3153dc6b (opus, high), Verification Gap acab03bbc43f14a88 (sonnet, medium).

| # | Lens | Finding | Verdict | Route and evidence |
|---|------|---------|---------|--------------------|
| 1 | BH, EC | Face or open shell reads `area` 0, not null; closed==0 branch before solids check | high | patch: 0 only when no wires; test with a face and an open shell |
| 2 | BH, EC, VG | Cost guard runs after copy and `isValid` | medium | patch: face count on the object's own shape first |
| 3 | BH | Worst layout (many holes) unmeasured | high | patch: measured plate 9,000 holes `common` 103 s; wire limit 1,500, area null above |
| 4 | BH, EC | Measurement comment not beside `_MAX_SECTION_FACES` | low | patch: constants moved under their comments |
| 5 | BH | Skill gap list still advises `slice` | medium | defer: Story 13-12 owns skills |
| 6 | BH | `_mm_quantity` third copy of parser | low | defer: shared helper edits two other modules |
| 7 | BH | Frame wording and no test with a placement | medium | patch: wording and placement test |
| 8 | BH | Near-face tests only inside; design probe list differs | low | patch: design lists probed offsets; outside side is undefined by the contract, no test |
| 9 | BH | Second Act inside Assert | low | patch: single Act |
| 10 | BH, VG | `max_points` 1 returns no point; `remaining < 2` branch untested | medium | patch: minimum 2; test at N and N+1 |
| 11 | BH, EC | Touching solids in a compound | medium | defer: documented, same class as overlapping (probe in deferred-work) |
| 12 | BH | Solid with only open wires gets area 0 | medium | patch: area from `common` whenever wires exist on a solids-only shape, null when empty |
| 13 | BH | Deflection floor not in description | low | patch: in catalog schema description |
| 14 | EC | Normal near float limits aborts the process or cuts a wrong plane | high | patch: scale by largest component; tests |
| 15 | EC | JSON integer beyond float range gives wrong status | medium | patch: `_is_finite_number`; test |
| 16 | EC | Dispatch zero-normal test passes a non-Quantity offset | low | patch: test uses a Quantity |

Review round 2 (red team, decision 31), deviations from the frozen text: face limit 3,000 (was 10,000); new `section.too_complex` rule for BSpline and Bezier pole load (spring); new code `section.plane_on_face` (a plane within 1e-7 mm of a planar face is refused, so offsets 0, 1e-9, 1e-7 and the top face are no longer cut); area limit 300 wires (was 1,500) because the area is cross-checked against the face built from the wires; `area` null for an open wire or when the two areas disagree; `bbox` from `optimalBoundingBox()`. The section loss on a 30-turn spring is not caught by the cross-check (both calls lose it); the pole limit refuses that spring.

| # | Source | Finding | Verdict | Route and evidence |
|---|--------|---------|---------|--------------------|
| R2-1 | red team RT-1 | Face guard does not bound cost (spring 112 s, prism 95.7 s, hole plate 42.6 s) | high | patch: faces 3,000 and pole load limit, measured |
| R2-2 | RT-2 | Budget test uses separate boxes | medium | patch: prism and hole plate at the limit |
| R2-3 | RT-3 | Section drops spring crossings, area short | medium | patch: pole limit refuses it; wires-vs-common cross-check added (does not see a loss in both) |
| R2-4 | RT-4 | Loose BSpline bbox | medium | patch: `optimalBoundingBox` |
| R2-5 | RT-5 | Plane on a face gives wrong numbers | medium | patch: `section.plane_on_face` |
| R2-6 | verifier f | Design names the copy as the fingerprint reason | low | patch: reworded |

Review round 2 lenses: Blind Hunter abfb81d141a72bd07 (opus, high), Edge Case Hunter a5dbd96c7419d33d7 (opus, high), Verification Gap abd3c64bf528ae7ff (sonnet, medium) on d4a258e4..b29c92b4.

| # | Lens | Finding | Verdict | Route and evidence |
|---|------|---------|---------|--------------------|
| R2-7 | BH, VG | Six round-1 tests deleted by a bad splice in the round-2 test patch | high | patch: restored; 99 tests in the three query classes pass |
| R2-8 | BH, VG | Pole refusal message states a per-face rule and no measured load | medium | patch: message names the load and limit; boundary and sum tests |
| R2-9 | BH, EC | Face tolerance above 1e-7 not used; box with tolerance 1e-5 gave an open wire | medium | patch: `max(1e-7, face.Tolerance)`; test with `fixTolerance(1e-5)` |
| R2-10 | BH, EC | Planar BSpline face (`toNurbs()` box) not detected | medium | patch: `findPlane()` for BSpline and Bezier faces; test |
| R2-11 | EC | `face.Surface` can raise; guards ran outside the trust handling | medium | patch: guards wrapped, refusal `section.untrusted_shape`; test |
| R2-12 | BH, EC | Plane-on-face check ran before the trust check | medium | patch: reordered; test with an invalid solid |
| R2-13 | BH, EC | Area tolerance 1e-6 nulls NURBS sections (7e-4 gap) | medium | patch: 5e-3 with the measurement beside the constant; test |
| R2-14 | BH | Message gives no minimum offset | low | patch: message names 1e-6 mm |
| R2-15 | BH, VG | Budget bound 60 s hides regressions; area path unmeasured at limits | medium | patch: 30 s bound, plate with area, combined shape measured |
| R2-16 | BH | Tilted-plane test asserts only status | low | patch: asserts wires and area; refused tilt 1e-10 added |
| R2-17 | BH, VG | No placement or 1e-6 void floor test | medium | patch: placed top face refused; void floor at 1e-6 measured |
| R2-18 | EC | Offset surface over a BSpline surface bypasses the pole load | low | defer: not measured; documented in design and constant comment |
| R2-19 | BH, EC, VG | Spec acceptance criterion, quality bar Q6 and T-2 still list the old offsets and 10,000 faces | medium | leader-owned documents; reported to the leader; spec change log above names the new rules |
