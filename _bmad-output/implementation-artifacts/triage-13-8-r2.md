# Story 13-8 triage: round 2 (red team; verifier PASS)

Base: d4a258e4 on `story/13-8-query-section`. Sources (this folder): `redteam-13-8.md` (RT-1 .. RT-5), `verify-13-8.md` (mutant f note). Use the red team's shapes as failing tests first. Leader decision 31.

| Id | Source | Required fix |
| --- | --- | --- |
| RT-1 (high) | red team | The face guard does not bound cost: a valid 3-face coil spring took 111.8 s (30 turns) / 209.9 s (60 turns); a 9,992-face prism 95.7 s; a 1,400 hex-hole plate 42.6 s. Replace the single face-count guard with measured guards that bound one call well inside the 60 s budget on these shapes: (a) a lower face limit, set from the prism and hole-plate timings; (b) a BSpline/Bezier complexity limit (for example the sum of control points, `NbUPoles*NbVPoles`, over BSpline/Bezier faces), set from the spring timings. Refuse above either with `INVALID_INPUT` `section.too_complex`. Document every measurement beside its constant; test both sides on real shapes (spring, prism, hole plate). If no cheap pre-check can bound the spring, refuse swept BSpline faces above the measured complexity and say so in the tool description. |
| RT-2 (medium) | red team | The face-limit budget test uses separate boxes (cheapest layout, `common` never runs) — a false pass. Replace with a worst-case layout (one solid with many faces that `common` must process). |
| RT-3 (medium) | red team | On a valid 30-turn spring, `section` drops 10 of 60 crossings and the tool returns OK with area 157 vs ~188 and no flag. Add a self-check: compute the area bounded by the closed section wires (face built from the wires, holes respected) and compare with the `common` area; on a mismatch beyond a stated tolerance, `area` is null. If the shape is refused by RT-1 first, keep the self-check anyway (it covers shapes under the limits). Test. |
| RT-4 (medium) | red team | `bbox` too loose for BSpline section edges (-12.08 vs -10 on a NURBS circle). Use `optimalBoundingBox()` (verify the API in FreeCAD source) for the section bbox. Test with a NURBS circle. |
| RT-5 (medium) | red team | Plane coplanar with a planar face gives wrong numbers (mesh box: length 82.4 vs 60 with 0 closed wires; void floor: area 400 vs closed wires 300). Detect a plane that coincides (within `Precision::Confusion`-level tolerance, verify in source) with any planar face of the shape and refuse with `INVALID_INPUT` `section.plane_on_face`, message "the plane lies on a face of <object>; offset it by a small amount". A plane 1e-6 mm inside a face must still be cut (keep those tests). The RT-3 self-check is the second line of defence. |
| f (low) | verifier | Design §3.2.4 states the copy as the reason the fingerprint is unchanged; the probe shows `section`/`common` leave it unchanged anyway. Reword to "runs on a copy so the document's shapes are never modified" without the false cause. |

## Not fixed, with the reason

- Bridge recovery after a long single OCC call (GIL held, bridge busy for minutes after `TIMEOUT`, seen in 13-7 F2) is a bridge-level problem under AD-27, not this tool's. Leader records it in `deferred-work.md` for an architecture decision.

## After the fixes

1. Commit on your branch yourself (no trailer).
2. Core rule changed: run `bmad-build`'s three lenses again as fresh subagents (round 2) on d4a258e4..HEAD with `quality-bar-13-8.md`. Patch high/medium; commit.
3. External tests from Git Bash (not PowerShell) and the infc suite; reply with SHA, lens ids, counts and the new limits with their measurements in at most 10 lines. Scratch only under scratchpad subfolder `builder-13-8\`.
