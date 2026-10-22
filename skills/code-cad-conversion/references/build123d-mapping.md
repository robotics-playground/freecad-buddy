# build123d / CadQuery to FreeCAD Part mapping

Each row: source construct, FreeCAD object, and the property that carries the expression.
CadQuery uses the same OCC kernel; its `Workplane.box`, `.cylinder`, `.hole`, `.cskHole`,
`.union`, `.cut` and `Location` map to the same rows.

## Solids

| build123d / CadQuery | FreeCAD object | Expression properties | Notes |
| --- | --- | --- | --- |
| `Box(x, y, z, align=...)` / `.box()` | `Part::Box` | `Length`, `Width`, `Height`, `Placement.Base.*` | FreeCAD box origin is its MIN corner; align C / MAX becomes a corner offset expression (`at - size/2`, `at - size`) |
| `Cylinder(r, h, align=...)` | `Part::Cylinder` | `Radius`, `Height` | origin at the bottom center; build123d default align is CENTER in z |
| `Cylinder(r, h, rotation=(-90, 0, 0), align=MIN)` (axis +y), `rotation=(0, 90, 0)` (axis +x) | `Part::Cylinder` with a fixed rotation (kit `cyl(..., axis="y")`) | `Radius`, `Height`, `Placement.Base.*` | build123d aligns before it rotates: `align` acts along the cylinder's own axis |
| `Cone(r_bottom, r_top, h)`, countersink | `Part::Cone` | `Radius1` (bottom), `Radius2` (top), `Height` | `Radius1 == Radius2` is valid, so a ternary can turn a countersink into a plain hole |
| `.hole(d)` / `.cboreHole` / `.cskHole` | `Part::Cylinder` (+ `Part::Cylinder` or `Part::Cone`) in a `Part::Cut` | as above | keep it CSG; a PartDesign Hole needs a sketch and loses the one-to-one map |
| `Sphere(r)` | `Part::Sphere` | `Radius` | |
| `Torus(R, r)`, ring swept along an arc | `Part::Torus` | `Radius1`, `Radius2`, `Angle3` (sweep) | start angle in `Placement.Rotation.Angle` |
| `loft` between two parallel rectangles | `Part::Wedge` (kit `taper_z`) | `Xmin..Zmax`, `X2min..Z2max`, `Ymin`, `Ymax` | a ruled solid between two rectangles along its local Y; rotate 90 deg about x so local Y is world z and local Z is world -y |
| extruded triangle (gusset) | `Part::Wedge` with one end degenerate | as above | winding of an extruded polygon flips under a mirror; a wedge does not |
| `RegularPolygon(r, n)` extruded | `Part::Prism` | `Circumradius`, `Height` | first vertex on local +x; rotate 90 deg for a vertex at +y |
| `offset(face, kind=ARC)` then extrude | `Part::RegularPolygon` or sketch -> `Part::Face` -> `Part::Offset2D` (`Join = "Arc"`) -> `Part::Extrusion` | `Offset2D.Value`, `Extrusion.LengthFwd` | set `Extrusion.DirMode = "Custom"`, `Dir`, `Solid = True` |
| `offset(..., kind=INTERSECTION)` of an equilateral triangle | `Part::Prism`, `Circumradius = 2 * (inradius + offset)` | `Circumradius` | sharp offset |
| pie / sector polygon from an origin | `Part::Cylinder` with `Angle` | `Angle`, `Placement.Rotation.Angle` | ray angles with `atan2()` expressions |
| 2D booleans, then `extrude` | the same booleans on 3D prisms of equal height | | 3D instead of 2D |
| `fillet`, `chamfer` on CSG edges | `Part::Fillet` / `Part::Chamfer` | `Radius` per edge | edge lists are indices: last step only; re-check after every parameter edit |

## Booleans and order

| Source | FreeCAD |
| --- | --- |
| `body = a + b + c`, `body += x` | `Part::MultiFuse` (`Shapes`, `Refine = True`) |
| `body -= x` | `Part::Cut` (`Base`, `Tool`); several consecutive tools fused first |
| `a & b`, `intersect` | `Part::MultiCommon` |
| loop of `body -= hole` | one `Part::Cut` with all holes fused as the tool, labelled `<part>_stepN` |

## Placement

| Source | FreeCAD |
| --- | --- |
| `Pos(x, y, z) * shape` | `Placement.Base.x/y/z` expressions |
| `Rot(0, 0, deg)` with fixed deg | fixed `App.Rotation` on the primitive |
| `Rot` with a parameter angle | `Placement.Rotation.Angle` expression (axis fixed) |
| `Location((tx, ty, 0), (0, 0, deg)) * part` | frame `(tx, ty, deg)`: every primitive gets a `Placement.Rotation.Angle` expression `deg` (start from a non-zero rotation about z to fix the axis) and base `tx + x*cos(deg) - y*sin(deg)`, `ty + x*sin(deg) + y*cos(deg)`; or one `App::Link` (`LinkTransform = True`) / `App::Part` with that placement |
| `loc.inverse() * shape` | link with the inverse placement |
| assembly of parts | `App::Link` to each part, `LinkTransform = True`, placement by expressions |
| purchased part (STEP) | load once into a hidden `Part::Feature`; place with `App::Link`; only the placement is a parameter |

## Expression syntax

| Python | FreeCAD expression |
| --- | --- |
| `a if c else b` | `c ? a : b` |
| `min`, `max`, `abs`, `sqrt` | same names |
| `math.cos(math.radians(d))` | `cos(d)` (degrees) |
| `math.degrees(math.atan2(y, x))` | `atan2(y, x)` (degrees) |
| `True` / `False` variable | `App::PropertyBool`, used as the condition |
| text choice (`FASTEN = "insert"`) | `App::PropertyEnumeration`; compare the index: `Params.FASTEN == 0`. A string compare (`== <<insert>>`) is always false, with no error |
| `if a < b:` deciding whether a tool exists | `a < b ? z : -1000` on the tool's base z: a parked tool cuts nothing |
| tuple constant `RAIL_Z = (0.0, 39.0)` | one variable per item: `RAIL_Z_0`, `RAIL_Z_1` |

Variable names that are unit symbols fail to parse (`Failed to parse expression 'Params.W * 3'`).
Seen in FreeCAD 1.1: `W`, `T`, `A`, `V`, `N`, `C`, `K`, `J`, `H`, `F`, `S`, `m`, `g`, `s`.
`L`, `P`, `R`, `D`, `X` parse. Rename to a longer name (`PLATE_W`) and keep a name map.
