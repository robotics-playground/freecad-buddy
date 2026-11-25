# Switches and fit decisions

Keep every source switch and every fit decision live in `Params`, so an edit that changes the
part count still matches the source.

## Switches

A bool becomes `App::PropertyBool` in a ternary on a numeric size:
`COUNTERSINK ? CSK_D / 2 : HOLE_D / 2` on the cone's `Radius2` (`Radius1 == Radius2` is
valid). A text choice (`"insert"` / `"tap"`) becomes `App::PropertyEnumeration`, compared by
index: `FASTEN == 0 ? 4 : 2.5`. A string compare (`FASTEN == <<insert>>`) is always false,
with no error. No typed tool creates the enumeration: one `script_exec` call does
(`generator-kit.md`, "Run it" step 4).

## Fit decisions

A Python `if` on parameter values that decides whether a feature exists
(`if y + 1.5 < WALL + MB_IN_W - ...`) becomes a ternary: park the tool out of the part
(`fits ? MB_FLOOR + 6 : -1000` bound to its `Placement.Base.z`) or set a size that cuts
nothing. A fixed decision breaks equality as soon as an edit changes the count. Loop counts
over literal ranges stay fixed; list them in the build notes (the generator header on the
generator route).
