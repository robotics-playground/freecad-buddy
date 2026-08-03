# Tangency-sense datums — DW-86

## Problem

`sketch_set_datum` refuses any constraint outside `_DIMENSIONAL`:

```python
if constraint_type not in _DIMENSIONAL:
    raise ValidationError(f"constraint {index + 1} is a {constraint_type}, not a dimensional constraint")
```

FreeCAD admits two more. `SketchObjectConstraints.cpp:194-197`, verbatim:

```cpp
// for tangent, value==0 is autodecide, value==Pi/2 is external and value==-Pi/2 is internal
if (!vals[ConstrId]->isDimensional() && type != Tangent && type != Perpendicular)
    return -1;
```

Confirmed live on FreeCAD 1.1.1 against a real `Tangent` between two circles: `setDatum` accepts
`0.0`, `+pi/2` and `-pi/2`, and the sketch stays valid after each. So the bridge makes a
source-documented capability unreachable.

## Decision already taken

The operator ruled: follow FreeCAD and reach all of its functionality — the capability must be
exposed, not documented away.

The sense is expressed as a **named enum**, not the shared `{value, unit}` quantity. On every
other datum the quantity means a measurement; here `0 / +pi/2 / -pi/2` is a three-way selector
wearing a number's clothes. Reusing the quantity field would make one input mean a size in most
places and a sense in two, which is the inconsistency this entry warned about. A named enum cannot
be mistaken for a measurement.

## Solution

`sketch_set_datum` gains an optional `sense`:

```
sketch_set_datum(doc, sketch, constraint, value=None, sense=None)
```

| target constraint type | accepts | rejects |
| --- | --- | --- |
| dimensional (`Distance`, `Radius`, `Angle`, …) | `value` | `sense` |
| `Tangent`, `Perpendicular` | `sense` | `value` |
| anything else | neither — unchanged rejection | |

`sense` takes `"autodecide"`, `"external"` or `"internal"`, mapped to the radian value FreeCAD
reads:

| `sense` | passed to `setDatum` |
| --- | --- |
| `autodecide` | `0.0` |
| `external` | `+math.pi / 2` |
| `internal` | `-math.pi / 2` |

The mapping lives in the use case, from the C++ comment above. It is not a caller concern, and a
caller must never be able to send a raw radian value for these types — that is what makes the
input honestly typed.

Radians are already this function's convention: the existing angle path converts degrees to
radians because `setDatum` reads a bare float as radians, so the sense values need no further
conversion.

`value` becomes optional in the signature, but **exactly one of `value` and `sense` is required**,
enforced in the use case. The wire schema keeps neither in `required` and states the rule in the
tool description, matching how `sketch_create` already handles its mutually exclusive
`plane`/`face` pair.

## Failure behaviour

| input | result |
| --- | --- |
| neither `value` nor `sense` | `INVALID_INPUT`: exactly one is required |
| both | `INVALID_INPUT`: exactly one is required |
| `sense` on a dimensional constraint | `INVALID_INPUT`: that type takes a value, not a sense |
| `value` on a `Tangent` | `INVALID_INPUT`: that type takes a sense, not a value |
| `sense` on a non-driving constraint | `INVALID_INPUT`, unchanged — the existing driving check runs first |
| `sense` outside the three names | rejected at the schema gate by the enum |

Every rejection is pre-bracket, matching the rest of the module.

## Testing

In-FreeCAD (`tests/infc/test_sketch_tools.py`), driven against a real `Tangent` between two
circles, which is the fixture measured above:

1. `sense="external"` on a `Tangent` commits and the sketch stays valid.
2. `sense="internal"` and `"autodecide"` likewise — all three reachable, not just the first.
3. `value` on a `Tangent` is rejected pre-bracket.
4. `sense` on a `Distance` is rejected pre-bracket.
5. Neither, and both, are each rejected pre-bracket.
6. A dimensional datum with `value` still commits unchanged — pins that the widening did not
   disturb the existing path.

External: `sense` is on the schema with `enum: ["autodecide", "external", "internal"]`, and
neither `value` nor `sense` is in `required`.

Test 2 is the one that earns its place: a mapping that sent every sense to the same radian value
would pass test 1 alone.

## Risks

`value` moving out of `required` on the wire is a loosening, so no existing call breaks. The
mutual-exclusion rule is enforced in the use case rather than the schema — JSON Schema can express
it with `oneOf`, but the generator has no support for that shape and `sketch_create`'s
`plane`/`face` pair already sets the precedent of enforcing it in code.

`Perpendicular` is included because the C++ admits it in the same condition, but its practical use
is narrower than `Tangent`. It is covered by the same tests through the type list rather than by
its own fixture.
