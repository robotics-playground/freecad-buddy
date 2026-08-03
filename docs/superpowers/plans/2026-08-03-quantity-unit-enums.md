# Quantity unit enums Implementation Plan — DW-82

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the wire schema reject the units the use cases reject, so a caller cannot send `in` or `cm` and learn only from a runtime rejection.

**Architecture:** Split one shared quantity schema into three by dimension, in `hosts/tool_catalog.py`. No use-case change — the accepted units are already `mm` and `deg` and stay exactly so.

**Tech Stack:** Python 3.11, pytest under `uv`. No FreeCAD needed for the change itself.

## Global Constraints

- Ring rule: `hosts/` may import Qt/`FreeCADGui`; `usecases/` may not. Enforced by `uv run python scripts/check_imports.py`.
- Comments and docstrings document what the code does and its params/returns/raises. No requirement ids, no spec-section citations, no design rationale inline.
- Two test worlds, never mixed: `tests/infc/` under `FreeCADCmd`, `tests/external/` under pytest.
- Commit messages use Conventional Commits, no AI attribution, no `Co-Authored-By`.
- Surgical changes: every changed line traces to this goal.

**Commands** (from the repo root, `D:\Work\Personal\Sources\freecad-buddy`):

```bash
uv run pytest tests/external -q
uv run python scripts/check_imports.py
uv run ruff check src/freecad_buddy tests/external

FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py
```

Baseline: **590 in-FreeCAD tests pass (1 skipped), 875 external pass.**

---

## Task 1: Split the quantity schema by dimension

**Files:**
- Modify: `src/freecad_buddy/hosts/tool_catalog.py` — `_QUANTITY_SCHEMA` at line 209, and its 20 use sites
- Test: `tests/external/test_sketch_contract.py`

**Interfaces:**
- Produces: `_LENGTH_QUANTITY_SCHEMA`, `_ANGLE_QUANTITY_SCHEMA`, and a rewritten `_QUANTITY_SCHEMA` accepting both.

- [ ] **Step 1: Write the failing tests**

Add to `tests/external/test_sketch_contract.py`:

```python
def test_a_length_field_accepts_only_millimetres():
    schema = _specs_by_name()["sketch_add_geometry"].input_schema
    radius = schema["properties"]["geometry"]["items"]["properties"]["radius"]

    assert radius["properties"]["unit"]["enum"] == ["mm"]


def test_an_angle_field_accepts_only_degrees():
    schema = _specs_by_name()["sketch_add_geometry"].input_schema
    start = schema["properties"]["geometry"]["items"]["properties"]["start_angle"]

    assert start["properties"]["unit"]["enum"] == ["deg"]


def test_a_constraint_value_accepts_either_unit():
    """The dimension depends on the constraint's type, resolved at call time.

    ``_ANGLE_TYPES`` takes degrees and ``_LENGTH_TYPES`` millimetres, so narrowing this field to
    one unit would refuse a call the use case accepts.
    """
    schema = _specs_by_name()["sketch_set_datum"].input_schema

    assert sorted(schema["properties"]["value"]["properties"]["unit"]["enum"]) == ["deg", "mm"]


def test_no_quantity_field_leaves_its_unit_unconstrained():
    """Walks every tool spec rather than a hand-listed set, so a new field cannot skip the rule."""
    offenders = []

    def walk(node, path):
        if not isinstance(node, dict):
            return
        properties = node.get("properties")
        if isinstance(properties, dict):
            unit = properties.get("unit")
            if isinstance(unit, dict) and "enum" not in unit:
                offenders.append(path)
            for key, child in properties.items():
                walk(child, f"{path}.{key}")
        items = node.get("items")
        if isinstance(items, dict):
            walk(items, f"{path}[]")

    for spec in tool_specs():
        walk(spec.input_schema, spec.name)

    assert offenders == []
```

`tool_specs` and `_specs_by_name` are already available in this file — add no imports.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/external/test_sketch_contract.py -q
```

Expected: all four fail — the three `enum` reads raise `KeyError`, and the walker lists every quantity field.

- [ ] **Step 3: Write the implementation**

In `src/freecad_buddy/hosts/tool_catalog.py`, replace the single `_QUANTITY_SCHEMA` definition at line 209 with three:

```python
def _quantity_schema(units: list[str]) -> dict:
    """A ``{value, unit}`` quantity whose unit is restricted to ``units``.

    The use cases accept millimetres for lengths and degrees for angles, so the boundary carries
    the same restriction rather than advertising an open string it will later refuse.
    """
    return {
        "type": "object",
        "properties": {
            "value": {"type": "number"},
            "unit": {"enum": units, "description": "explicit unit"},
        },
        "required": ["value", "unit"],
        "additionalProperties": False,
    }


_LENGTH_QUANTITY_SCHEMA = _quantity_schema(["mm"])
_ANGLE_QUANTITY_SCHEMA = _quantity_schema(["deg"])
# The dimension of a constraint datum depends on the target constraint's type, resolved at call
# time, so this one field legitimately takes either unit.
_QUANTITY_SCHEMA = _quantity_schema(["mm", "deg"])
```

Then retarget each use site. Keep `_QUANTITY_SCHEMA` on the two dimension-ambiguous fields ONLY:

| line | field | use |
| --- | --- | --- |
| 302 | `constraints[].value` (sketch geometry/constraint tools) | `_QUANTITY_SCHEMA` — unchanged |
| 453 | `sketch_set_datum.value` | `_QUANTITY_SCHEMA` — unchanged |
| 262 | `radius` | `_LENGTH_QUANTITY_SCHEMA` |
| 263, 264 | `start_angle`, `end_angle` | `_ANGLE_QUANTITY_SCHEMA` |
| 536, 537 | `length`, `second_length` | `_LENGTH_QUANTITY_SCHEMA` |
| 542 | `taper_angle` | `_ANGLE_QUANTITY_SCHEMA` |
| 575, 576 | `angle`, `second_angle` (revolve) | `_ANGLE_QUANTITY_SCHEMA` |
| 594, 595, 599, 600 | `diameter`, `depth`, `cut_diameter`, `cut_depth` | `_LENGTH_QUANTITY_SCHEMA` |
| 617 | `radius` (fillet) | `_LENGTH_QUANTITY_SCHEMA` |
| 633, 634 | `size`, `second_size` (chamfer) | `_LENGTH_QUANTITY_SCHEMA` |
| 635 | `angle` (chamfer) | `_ANGLE_QUANTITY_SCHEMA` |
| 658 | `length` (pattern) | `_LENGTH_QUANTITY_SCHEMA` |
| 659 | `angle` (pattern) | `_ANGLE_QUANTITY_SCHEMA` |
| — | `offset` (**pattern**) | `_QUANTITY_SCHEMA` — **both units**, see below |
| 694 | `offset` (datum) | `_LENGTH_QUANTITY_SCHEMA` |

**`feature_pattern`'s `offset` is the third dimension-ambiguous field.** It is a length for a
linear pattern and an angle for a polar one, chosen at runtime by `kind` — `features.py:1356`
calls `_positive_length(offset, "offset")` while `:1358` calls
`_bounded_angle(offset, "offset", 0.0, 360.0, include_high=True)`. Narrowing it to `mm` would
refuse every polar pattern that steps by offset.

Do not confuse it with `feature_datum`'s `offset` (line 694), which is a length only.

Line numbers are from the pre-change file and shift as you edit — match on the surrounding field name, not the number.

Cross-check each against the use case before changing it: `features.py` and `sketches.py` call `_length_mm` for length fields and `_angle_degrees` for angle fields. If a field's use-case call disagrees with the table, stop and report rather than guessing.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/external -q
```

Expected: `879 passed` — the 875 baseline plus these 4.

- [ ] **Step 5: Run the in-FreeCAD suite and the gates**

```bash
uv run python scripts/check_imports.py
uv run ruff check src/freecad_buddy tests/external
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)"
```

Expected: `check_imports OK`; ruff reports only the pre-existing `E501` in `tests/external/test_check_imports.py:302`; `Ran 590 tests`, `OK (skipped=1)` — no in-FreeCAD test changes, because no accepted call changed.

If an in-FreeCAD test fails, a field was retargeted to the wrong dimension. Read which field and fix the mapping.

- [ ] **Step 6: Verify the tests can fail (falsifiability)**

Temporarily revert one field — put `_QUANTITY_SCHEMA` back on `taper_angle`. Re-run the external suite. Expected: `test_no_quantity_field_leaves_its_unit_unconstrained` still passes (the field still has an enum, just a wider one), and no other test fails.

That is a real gap in the test set, and worth knowing: the walker pins that every unit is constrained, not that each is constrained *correctly*. Record it in the report. Then restore.

- [ ] **Step 7: Commit**

```bash
git add src/freecad_buddy/hosts/tool_catalog.py tests/external/test_sketch_contract.py
git commit -m "feat(hosts): constrain quantity units at the wire boundary

The shared quantity schema typed unit as an open string while the use cases
accept only mm for lengths and deg for angles, so cm, in, m and rad passed the
input-schema gate and were refused later by the use case. An agent working in
inches got a rejection the schema gave it no way to anticipate.

Split into three schemas by dimension. Two fields legitimately take either unit —
a sketch constraint's value and sketch_set_datum's, both resolved from the target
constraint's type at call time — and keep the wider enum, because narrowing them
would refuse calls the use case accepts.

No accepted call changes: mm and deg remain exactly as valid as before. A length
field now also refuses deg at the boundary, which it previously accepted there
and failed on later."
```

---

## Task 2: Verify over live MCP

**Files:** none.

- [ ] **Step 1: Reload the addon**

Quit FreeCAD and start it again. Confirm the reload took by comparing full timestamps **including the date** — a clock-time comparison across a date boundary is misleading:

```bash
powershell -NoProfile -Command "\$p=Get-Process -Name freecad; \$f=Get-Item 'D:\Work\Personal\Sources\freecad-buddy\src\freecad_buddy\hosts\tool_catalog.py'; 'started: '+\$p.StartTime.ToString('yyyy-MM-dd HH:mm:ss'); 'mtime  : '+\$f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'); 'file newer than process: '+(\$f.LastWriteTime -gt \$p.StartTime)"
```

Expected: `file newer than process: False`.

- [ ] **Step 2: Confirm the boundary rejects what the code rejects**

Read `tools/list` and confirm a length field's `unit` carries `enum: ["mm"]`.

Then drive the contrast:

- `feature_pad` with `length: {"value": 5, "unit": "mm"}` → `OK`
- `feature_pad` with `length: {"value": 5, "unit": "in"}` → refused **at the schema gate**, an MCP protocol error with no `ResultEnvelope`, not an `INVALID_INPUT` envelope

The second is the point: before this change that call reached the use case and returned an envelope. Record which layer refused it.

- [ ] **Step 3: Record the result**

State what was verified. This proves the boundary refuses a bad unit; it does not prove anything about unit *conversion*, which was deliberately not implemented.

No commit.
