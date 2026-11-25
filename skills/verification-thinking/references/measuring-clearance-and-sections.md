# Measuring clearance and sections

Read this when `query_interference` or `query_section` refuses a call or returns a value you
cannot read as a number. Both tools return numbers only and give no verdict: you compare the
numbers with the spec.

## `query_interference`

Give exactly one of `objects` (2 to 20 names, every pair) or `pairs` (1 to 100 `[a, b]` pairs).
Each object is measured on its own shape in its container's frame, so name a Body, not a feature
inside it. Bodies in different containers (for example two `App::Part`) are measured in different
frames: name the `App::Part` of each, or keep the objects in one container.

Result `{pairs: [{a, b, common_volume, min_distance, boolean_failed}]}`.

| Field | Reading |
| --- | --- |
| `common_volume` | overlap as `{value, unit: "mm^3"}`; a value of 0 with `boolean_failed` false is a measured zero overlap, which includes valid solids that only touch (the tool fuses them and compares volumes). An overlap of less than 1.5e-12 of the summed volume can read as touching |
| `min_distance` | gap as `{value, unit: "mm"}`; 0 for solids that touch or overlap |
| `boolean_failed` true | the overlap is **unmeasured**, `common_volume` is null, and a script that reads the same empty boolean as zero is wrong too. `min_distance` null: a shape is not a valid solid with positive volume. `min_distance` 0 (at most 1e-7 mm, the contact tolerance): the boolean returned nothing at contact and the fuse could not prove plain contact (for example a pair with BSpline faces, or a very small overlap in the contact band) |

| Refusal | Cause | Fix |
| --- | --- | --- |
| `INVALID_INPUT` `interference.too_complex` | a pair whose faces multiplied exceed 150000, or the call ran past 40 s | a pair over the face limit: measure objects with fewer faces. A call over 40 s: send fewer pairs |

When `boolean_failed` is true and `min_distance` is null, run `verify_shape` on each shape
(`is_valid_solid`, `expect_solid_count`) to find the broken shape. When it is true and
`min_distance` is 0 (at most 1e-7 mm), check both shapes the same way; if both are valid the parts are in contact and the
tool could not prove they only touch: report "contact, overlap unmeasured". For a number, use the fuse-volume gap row of
`freecad-scripting-idioms`: `a.Volume + b.Volume - a.fuse(b).Volume` is the overlap volume, 0
for parts that only touch; a failed fuse (`isValid()` false) leaves the overlap unmeasured.

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
| `section.too_complex` | more than 3,000 faces, or BSpline or Bezier faces with about 800 poles or more in one face (a coil spring) | cut a simpler part, or report the section as unmeasured |
| `section.plane_on_face` | the plane lies on a planar face | move `offset` into the part by 1e-6 mm or more, and by more than the face tolerance of a shape that has a larger one (a plane moved outward misses the part: `wires` 0, `area` 0) |

Solids that overlap or touch inside one compound are not detected: `area` counts each solid.
