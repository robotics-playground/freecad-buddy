# Measuring clearance and sections

Read this when `query_interference` or `query_section` refuses a call or returns a value you
cannot read as a number. Both tools return numbers only and give no verdict: you compare the
numbers with the spec.

## `query_interference`

Give exactly one of `objects` (2 to 20 names, every pair) or `pairs` (1 to 100 `[a, b]` pairs).
Each object is measured on its own shape in its container's frame, so name a Body, not a feature
inside it.

Result `{pairs: [{a, b, common_volume, min_distance, boolean_failed}]}`.

| Field | Reading |
| --- | --- |
| `common_volume` | overlap as `{value, unit: "mm^3"}`; a value of 0 with `boolean_failed` false is a measured zero overlap |
| `min_distance` | gap as `{value, unit: "mm"}`; 0 for solids that touch or overlap |
| `boolean_failed` true | the overlap is **unmeasured**, `common_volume` is null. A shape is not a valid solid with positive volume (`min_distance` is null too), or the boolean returned nothing at distance 0 or at an unknown distance. Solids that only touch can give this |

| Refusal | Cause | Fix |
| --- | --- | --- |
| `INVALID_INPUT` `interference.too_complex` | a pair whose faces multiplied exceed 150000, or the call ran past 40 s | send fewer, larger pairs per call; cost grows with face count |

When `boolean_failed` is true, run `verify_shape` on each shape (`is_valid_solid`,
`expect_solid_count`) to find which shape is broken before you report a clearance.

## `query_section`

Input: `object`, `plane {normal, offset}` and optional `points {deflection, max_points}`. The
plane is `normal . p = offset` in the frame of the object's container; the object's own
Placement is applied and the container's is not. `normal` is `"x"`, `"y"`, `"z"` or a non-zero
`[nx, ny, nz]`; `offset` and `deflection` are `{"value": 12.5, "unit": "mm"}`.

Result `{wires, closed_wires, length, area, bbox}`. A plane that misses the part gives
`wires` 0, `area` 0 and `bbox` null.

| Field | Reading |
| --- | --- |
| `area` null | **unmeasured**, never zero: a shell or face, an open wire, more than 300 wires, a failed boolean, or two area methods that disagree |
| `truncated` true (with `points`) | `max_points` cut the polylines; raise `max_points` or the `deflection` |

| Refusal | Cause | Fix |
| --- | --- | --- |
| `section.untrusted_shape` | an invalid or reversed shape, or one with no face | repair the part; check it with `verify_shape` |
| `section.too_complex` | more than 3,000 faces, or BSpline or Bezier faces with about 800 poles or more in one face (a coil spring) | cut a simpler part, or measure by `query_mass_properties` |
| `section.plane_on_face` | the plane lies on a planar face | change `offset` by 1e-6 mm or more |

Solids that overlap or touch inside one compound are not detected: `area` counts each solid.
