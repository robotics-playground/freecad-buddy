# PartDesign feature prerequisites and failure modes

Load this when a specific feature fails or you need its exact prerequisites and
control properties. The property and enum names below are the actual FreeCAD
property names — confirm a specific value at runtime with `query_object`, because
FreeCAD's enums do not always match the order the GUI dropdown shows and a guessed
member is a silent wrong-behavior bug.

## Additive / subtractive from a profile

| Feature | Prerequisite | Key properties | Common failure → fix |
| --- | --- | --- | --- |
| Pad | one closed profile (sketch/face) | `Type` (mode), `Length`, `Length2`, `Midplane`, `Reversed`, `UpToFace`/`UpToShape` | open profile → null face (close it); coincident up-to face → overshoot or use up-to mode |
| Pocket | closed profile inside the solid | `Type`, `Length`, `Midplane`, `Reversed`, `UpToFace`/`UpToShape` | profile outside target → nothing removed (place inside); coincident cut face → overshoot/through-all |
| Revolution | closed profile + an axis not crossing the profile | `Angle`, `Axis`, `Midplane`, `Reversed` | axis intersects profile → self-intersecting solid (move the axis) |

**Pad `Type` enum**: `Length`, `UpToLast`, `UpToFirst`, `UpToFace`, `TwoLengths`,
`UpToShape`.
**Pocket `Type` enum**: `Length`, `ThroughAll`, `UpToFirst`, `UpToFace`,
`TwoLengths`, `UpToShape`.
Note the two enums differ — pad has `UpToLast`, pocket has `ThroughAll`. Never
carry one feature's mode list onto the other. `Midplane` and `Reversed` apply to
both (they belong to the shared sketch-based extrude behavior).

A pad that overlaps nothing adds the same volume in either direction, so a matching
volume never proves the side. Prove it with a point probe on each side of the
sketch plane (`Shape.isInside`) before accepting `Reversed`.

## Hole

Prerequisite: a sketch of hole center points. Properties:
`Diameter`, `DepthType`, `Depth`, `Threaded`, `ThreadDiameter`, `HoleCutType`,
`HoleCutDiameter`, `HoleCutDepth`, `ThreadDepthType`, `ThreadDepth`. The thread and
head-cut properties are descriptive metadata — a verification must measure the
actual cut geometry (bore diameter, through-condition, counterbore depth), never
trust the property values as proof.

## Loft and sweep

| Feature | Prerequisite | Key properties | Common failure → fix |
| --- | --- | --- | --- |
| Loft | ≥2 profiles in order | `Sections`, `Ruled`, `Closed` | mismatched profile vertex counts or wildly different orientation → twisted/failed surface (reorder, align, or add intermediate sections) |
| Sweep (Pipe) | a spine path + section(s) | `Sections`, `Spine`, `SpineTangent`, `AuxiliarySpine` | self-intersecting or sharply-kinked spine, or a section larger than the spine's turn radius → boolean failure (smooth the spine, shrink the section) |

## Dress-up: fillet and chamfer

| Feature | Prerequisite | Key properties | Common failure → fix |
| --- | --- | --- | --- |
| Fillet | selected edges on a valid solid | `Radius` | radius > local geometry → no solution (reduce radius); edges re-labelled by a later boolean → dropped edges (apply last, select by intent) |
| Chamfer | selected edges on a valid solid | `Size`, `Size2`, `Angle`, `ChamferType` | size > local geometry → no solution; wrong `ChamferType` for the given inputs (match the equal-distance / two-distance / distance-angle variant to what you set) |

Dress-up features (fillet, chamfer) are the last step in a body. A dress-up
silently drops edges that lose their two adjacent faces during recompute, so a
fillet that "worked" can quietly round fewer edges than intended — compare the
edge count, not just the error state, when auditing.

A concave fillet near another wall merges into it and adds less volume than the
analytic value (2π · centroid radius · spandrel area per round base). Measure each
instance in a bounding ring rather than accepting the total: a shortfall at one
instance is overlap, at all instances it is a dropped or wrong edge.

A feature added by script with `body.newObject(...)` goes after the current Tip and
becomes the Tip, so a later dress-up or an added rib can sit after features it does
not depend on. The geometry is the same; state the tree order in the report.

## Pattern and mirror

| Feature | Prerequisite | Key properties | Common failure → fix |
| --- | --- | --- | --- |
| Linear pattern | ≥1 original feature | `Occurrences`, direction, length | spacing × occurrences overruns the body or overlaps → invalid solid (reduce count/spacing) |
| Polar pattern | ≥1 original feature + an axis | `Occurrences`, angle, axis | occurrences over 360° collide (close the angle or reduce count) |
| Mirror | ≥1 original feature + a plane/datum | mirror plane | mirror plane not on a symmetry datum → overlap or gap at the seam (mirror across a real datum plane) |

`Occurrences` counts the *total* instances including the original, not the added
copies — an edit that means "one more" is `Occurrences + 1`.

## The general repair order

When a feature fails: read the recompute error, classify which row above it
matches, make the smallest change (shrink a radius, close a profile, overshoot a
cut, re-select edges by intent), recompute, then re-measure. The full
read → classify → smallest-change → rerun → re-check-dependents loop is owned by
freecad-troubleshooting.
