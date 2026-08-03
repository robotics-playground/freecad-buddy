# Quantity units: make the schema reject what the code rejects — DW-82

## Problem

`_QUANTITY_SCHEMA` types `unit` as an open string:

```python
"unit": {"type": "string", "description": "explicit unit, e.g. mm or deg"},
```

The use cases accept only two values — `_LENGTH_UNITS = {"mm"}` and `_ANGLE_UNITS = {"deg"}`, declared identically in both `sketches.py` and `features.py`. So `cm`, `in`, `m` and `rad` all pass the MCP input-schema gate and are then rejected by the use case.

An agent working in inches will reasonably send `in` and get a rejection the schema gave it no way to anticipate. The boundary advertises more than the code honours.

## Decision already taken

The operator ruled option **A**: put the enum on the schema so the boundary rejects what the use case rejects. Keep millimetres and degrees as the only accepted units.

Option B — accept other units and convert — was considered and rejected. It is genuinely available: measured on FreeCAD 1.1.1, `Base.Quantity` converts natively, `1 in → 25.4 mm`, `2 cm → 20 mm`, `0.5 m → 500 mm`, `1.5708 rad → 90.0002 deg`. But it converts silently at 20 call sites and needs its own rounding decision — note the radian case does not land on exactly 90. That is a separate change with its own risks; this one makes the contract truthful about what exists today.

## Solution

Split the shared `_QUANTITY_SCHEMA` into three, by dimension:

| schema | `unit` | used by |
| --- | --- | --- |
| `_LENGTH_QUANTITY_SCHEMA` | `enum: ["mm"]` | radius, length, depth, size, offset, diameter, … |
| `_ANGLE_QUANTITY_SCHEMA` | `enum: ["deg"]` | start_angle, end_angle, taper_angle, angle, … |
| `_QUANTITY_SCHEMA` | `enum: ["mm", "deg"]` | the two dimension-ambiguous fields below |

**Two fields legitimately accept either**, and must keep the wider enum rather than being forced into one:

- `sketch_add_constraint` / `sketch_add_geometry` `constraints[].value` — the dimension depends on the constraint's *type*, decided at runtime: `_ANGLE_TYPES = {"Angle"}` takes degrees, `_LENGTH_TYPES = {Distance, DistanceX, DistanceY, Radius, Diameter}` takes millimetres.
- `sketch_set_datum` `value` — same, resolved from the target constraint.

Narrowing either to one unit would refuse a call the code accepts, which is the mirror of the defect being fixed.

`feature_set_parameters`' `parameters` map is untouched: it takes arbitrary property values, not a fixed quantity, and its dimension check reads the live property type.

## Failure behaviour

| input | before | after |
| --- | --- | --- |
| `{"value": 5, "unit": "in"}` on a length | passes schema, `INVALID_INPUT` from the use case | rejected at the schema gate |
| `{"value": 90, "unit": "deg"}` on a length | passes schema, `INVALID_INPUT` from the use case | rejected at the schema gate |
| `{"value": 90, "unit": "deg"}` on a constraint value | accepted | accepted, unchanged |

The second row is a real gain beyond the reported defect: a length field currently accepts `deg` at the boundary and fails later. After the split it is refused where the mistake is made.

## Testing

External (`tests/external/test_sketch_contract.py`, `test_feature_contract.py`):

1. A length field's schema carries `enum: ["mm"]`; an angle field's carries `enum: ["deg"]`.
2. A constraint `value` carries both, so neither unit is refused at the boundary.
3. Every field the tools declare as a quantity uses one of the three schemas — no field keeps a bare `{"type": "string"}` unit. Asserted by walking the specs rather than by a hand-listed set, so a future field cannot quietly skip it.

Test 3 is the one that matters: 1 and 2 pin the fields that exist today, while 3 pins the rule.

## Risks

A client sending a unit the code never accepted now fails earlier, with a schema error instead of an `INVALID_INPUT` envelope. That is the intent, but it is a different error surface: the rejection arrives as an MCP protocol error with no `ResultEnvelope`, the same layer that already rejects a missing required field.

No accepted call changes behaviour — `mm` and `deg` remain exactly as valid as before.
