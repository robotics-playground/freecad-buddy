# Story 13-8: red team report

Head: d4a258e4 (branch story/13-8-query-section), diff 90303e36...d4a258e4. Own worktree, host
FreeCAD 1.1.4 `freecadcmd.exe` with private cfg files. No container, no ports used.

Probe scripts: `C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\50958ed8-8fcb-4d26-a32d-c7025b2780ae\scratchpad\redteam-13-8\`
(`common.py` puts the worktree `src` first on `sys.path` and asserts that `queries.__file__` is
the worktree copy; `sec()` calls `queries.query_section` on a real `DocumentRegistry`; `t` is the
wall time of one tool call).

Run command for every probe below:

```
CASE=<case> "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" -u <scratch>\user.cfg -s <scratch>\system.cfg <scratch>\<probe>.py <scratch>\<out>.txt
```

## Reproduced

| Id | Severity | Q | file:line | Finding |
| --- | --- | --- | --- | --- |
| RT-1 | high | Q6 | `src/freecad_buddy/usecases/queries.py:1126-1154`, `:940` | One call runs far past the 60 s budget on shapes under the 10,000-face guard |
| RT-2 | medium | Q6 | `tests/infc/test_query_tools.py:1532-1548` | Budget test uses the cheapest layout, so it passes while RT-1 fails |
| RT-3 | medium | Q2 | `src/freecad_buddy/usecases/queries.py:1147-1154` | Valid solid: section kernel drops wires; tool reports a short area as measured |
| RT-4 | medium | Q2 | `src/freecad_buddy/usecases/queries.py:1165` | `bbox` is loose for BSpline section edges |
| RT-5 | medium | Q2, Q3 | `src/freecad_buddy/usecases/queries.py:1147-1154` | Plane on a face: open wires, inflated length, area that disagrees with the closed wires |

### RT-1 (high, Q6): the face guard does not bound the cost

`_MAX_SECTION_FACES = 10_000` (`queries.py:940`) is the only guard before `isValid`,
`Shape.section` and `Shape.common`. These calls hold the interpreter lock (the code comment says
so). The cost depends on the layout, not on the face count. The design text ("one call stays near
8 s (section 3 s at most plus `common` near 5 s)") and Q6 ("one call stays well inside the 60 s
budget") do not hold.

Reproduction: `p9.py` and `p10.py` (one tool call each, process alone on the host).

| Shape (all `isValid()` True, OK status) | Faces | Wires | Tool call |
| --- | --- | --- | --- |
| Coil spring, 10 turns (`Part.Wire(helix).makePipeShell([circle], True, True)`) | 3 | 20 | 15.5 s (`section` 12.9 s) |
| Coil spring, 30 turns | 3 | 50 | **111.8 s** (`section` 122.5 s in the phase run) |
| Coil spring, 60 turns | 3 | 68 | **209.9 s** |
| Coil spring, 100 turns (`MakePipeShell`, Frenet) | 3 | 70 | **214.6 s** |
| Regular 9,990-gon prism, one solid | 9,992 | 1 | **95.7 s** (106.6 s in a second run) |
| Plate with 1,400 hex holes | 8,406 | 1,401 | 42.6 s (phases: `isValid` 35.7 s, `section` 4.1 s, `common` 38.1 s) |
| Plate with 1,500 hex holes (area skipped) | 9,006 | 1,501 | 51.1 s |

Output lines (`out10.txt`, `out9.txt`, `out.txt`):

```
spring030 faces 3 Solid valid True vol 11843.52 expected vol ~ 11846.9
spring030 tool {'wires': 50, 'closed_wires': 50, 'area': 157.08031856088883, ...} t 111.8
spring060 tool {'wires': 68, 'closed_wires': 68, 'area': 229.63894087833322, ...} t 209.9
prism9990 faces 9992 Solid vol 314159.24
prism9990 tool {'wires': 1, 'closed_wires': 1, 'area': 31415.92446467254, ...} t 95.7
prism5000 phases ({'copy': 0.3, 'isValid': 10.8, 'section': 1.7, 'sort+wire': 0.2, 'common': 14.8}, 5000, 1, ...)
```

Two separate causes: (a) `Shape.section` on a swept BSpline face grows with the turn count, with
3 faces; (b) on one solid with many faces, `isValid` and `common` grow with the square of the face
count (prism 2,500 → 5,000 faces: `isValid` 2.0 → 10.8 s, `common` 4.3 → 14.8 s). Springs and
STL-derived solids with thousands of planar faces are ordinary inputs.

### RT-2 (medium, Q6): false-pass budget test

`test_Should_finish_inside_the_query_budget_When_a_shape_is_at_the_face_limit`
(`test_query_tools.py:1532`) cuts 1,666 separate 2 mm boxes. That is 1,666 wires, above
`_MAX_AREA_WIRES`, so `common` never runs, and separate boxes are the cheapest `section` layout.
The test passes (89/89 in `infc.test_query_tools`) while RT-1 shows the same face count taking
95.7 s in one solid.

### RT-3 (medium, Q2): dropped section wires on a valid solid, area reported as measured

`p11.py`: 30-turn spring, `isValid()` True, volume 11,843.5 (analytic 11,846.9). All 60 crossing
centres `(0, ±20, 3·(k+0.25|0.75))` are inside the solid (`isInside`). `Shape.section` returns 50
wires: 10 crossings have no wire. The tool returns `OK`, `wires 50`, `closed_wires 50`,
`area 157.08` (expected about 188.5, −17 %), with no flag. A slab `common` reference gives the
same 157.08, so `common` misses the same regions.

```
crossing centers inside solid: 60 of 60
tool wires 50 t 121.3 inside-solid crossings with no section wire: 10 [(20, 9.75), (-20, 20.25), (-20, 29.25), (20, 30.75), ...]
```

The tool matches a script's `Shape.section` (Q2 literal), so this is a kernel failure the trust
check does not catch. Severity is medium, not high, for that reason.

### RT-4 (medium, Q2): loose `bbox` on BSpline section edges

`hull = Part.Compound(edges).BoundBox` (`queries.py:1165`) bounds BSpline edges by their poles.
`p7.py`:

```
NC z 0.0 tool bbox x -12.080126 10.0 y -12.072727 12.072727 | polyline x -9.9996 10.0 y -9.9997 9.9999
   optimalBoundingBox BoundBox (-10, -10, -1e-07, 10, 10, 1e-07)
EX profile true x -9.6288 10.1286 y -6.0216 6.0216
EX z 0.0 tool bbox x -9.863658 10.437936 y -6.341855 6.341855
EX z 2.5 tool bbox x -9.628808 10.12859 y -6.021628 6.021628
```

`NC` is `Part.makeCylinder(10, 30).toNurbs()` cut on its cap: bbox 2.08 mm too wide on a 20 mm
circle. `EX` is one BSpline profile extruded 5 mm: the same section reads two different boxes at
z 0 and z 2.5. `Shape.optimalBoundingBox()` returns the exact box. `query_mass_properties` uses
the same `BoundBox`, so the looseness is shared, but here it is a new field that claims "the bounding
box of the section edges".

### RT-5 (medium, Q2/Q3): plane coincident with a face

`Shape.section` returns every edge of the coincident faces, including inner edges. `p6.py`,
`p1.py`, `p8.py`:

```
MB z -15.0 {'wires': 1, 'closed_wires': 0, 'area': 199.99999999999994, 'length': 82.36067977499789, ...}   # mesh-derived 10x20x30 box, bottom face
MB z 0.0   {'wires': 1, 'closed_wires': 1, 'area': 200.0, 'length': 60.0, ...}
L z 5.0    {'wires': 2, 'closed_wires': 1, 'area': 199.99999999999997, 'length': 70.0, ...}            # L-block at the step face
hollow at void face {'wires': 2, 'closed_wires': 2, 'area': 399.99999999999994, 'length': 120.0, ...}  # 20^3 box with 10^3 void, plane on void floor
```

On a triangulated face (STL import) the perimeter reads 82.36 instead of 60 and the only wire is
open, but the area is 200. On the void floor the two closed wires bound 300 mm^2 (T-2: "area of
the faces the closed wires bound"), but the area reads 400. The plane at a face is the case the
Story targets (Q3). It is not a false miss, so Q3 holds. The numbers disagree with each other
and with T-2, and the design does not document it.

## Not reproduced (low)

- Wrong area on holes, islands, oblique planes, a plane through the cylinder axis, near-tangent
  planes, small spheres near the pole, a 1e-3 mm box, shapes at 1e9 and 1e12 mm, offsets ±1e300:
  all analytic within 1e-9 relative (`p1.py`).
- Frame: `PartDesign::Body`, a feature inside it, `App::Part`, a `Part::Box` inside `App::Part`,
  `App::Link`, a hidden object: each cut in its own `Shape` frame, as the description states
  (`p4.py`).
- Tangent line (cylinder) reads `wires 1`, `closed 0`, `area null`; plane through one vertex or
  the cone apex reads as a miss with area 0. True area is 0 in both, so no wrong number.
- Edge-touching boxes (compound and fuse) read 2 closed wires and area 200 (`p8.py`).
- `discretize` hang: none at the deflection floor (10,000 sphere wires 24.7 s; 1,500-hole plate
  8.9 s; 9,990-edge wire capped). Floor and `max_points` cap hold.
- Mesh-derived sphere, 4,900 faces: 1.4 s. Separate-box layouts behave as the design measures.
- Refactor: `_named_shape` / `_copied_queryable_shape` / `_refusal_envelope` / `_bbox_record`
  keep the old behaviour by reading; `infc.test_query_tools` 89 tests OK on the worktree copy
  (incl. `QueryInterferenceTest` and mass-properties tests).
- Schema: `gen_schemas --check` OK; `ruff check`, `check_imports`, `check_status_vocab` OK;
  `ruff format --check` on the 4 changed Python files OK; `pytest tests/external -k
  "mcp_surface or readonly_profile or schema"` 148 passed. Input schema units (`mm` only) and
  `max_points` 2..5000 match the code. Output goes through the shared envelope `outputSchema`.

## Verdict

**FAIL.** RT-1 breaks Q6: a valid 3-face coil spring takes 111.8 s to 214.6 s, and a 9,992-face
solid takes 95.7 s, in one call that holds the interpreter lock under the 10,000-face guard.
RT-2 to RT-5 are medium.
