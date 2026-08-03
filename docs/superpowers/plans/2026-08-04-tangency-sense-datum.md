# Tangency-sense datums Implementation Plan — DW-86

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `sketch_set_datum` set a tangency sense on `Tangent` and `Perpendicular` constraints, which FreeCAD accepts and the tool currently refuses.

**Architecture:** One optional `sense` argument on an existing use case, mapped to the radian value FreeCAD reads. The dimensional path is untouched; the two input kinds are mutually exclusive.

**Tech Stack:** Python 3.11, FreeCAD 1.1 App API, stdlib `unittest` under `FreeCADCmd`, pytest under `uv`.

## Global Constraints

- Ring rule: `usecases/` may import stdlib + FreeCAD App only; `hosts/` may import Qt/`FreeCADGui`. Enforced by `uv run python scripts/check_imports.py`.
- Any FreeCAD enum, property name or API semantic must be confirmed against `docs/references/FreeCAD/` before use — never assumed.
- Comments and docstrings document what the code does and its params/returns/raises. No requirement ids, no spec-section citations, no design rationale inline.
- Two test worlds, never mixed: `tests/infc/` under `FreeCADCmd`, `tests/external/` under pytest.
- Commit messages use Conventional Commits, no AI attribution, no `Co-Authored-By`.
- Surgical changes: every changed line traces to this goal.

**Commands** (from the repo root, `D:\Work\Personal\Sources\freecad-buddy`):

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py

uv run pytest tests/external -q
uv run python scripts/check_imports.py
uv run ruff check src/freecad_buddy tests/infc tests/external
```

Baseline: **590 in-FreeCAD tests pass (1 skipped), 879 external pass.**

---

## The FreeCAD behaviour this rests on

`SketchObjectConstraints.cpp:194-197`:

```cpp
// for tangent, value==0 is autodecide, value==Pi/2 is external and value==-Pi/2 is internal
if (!vals[ConstrId]->isDimensional() && type != Tangent && type != Perpendicular)
    return -1;
```

Confirmed live on FreeCAD 1.1.1 against a **fully constrained** `Tangent` between two circles:
`setDatum` accepts `0.0`, `+pi/2` and `-pi/2`, and after each the sketch reports
`isValid=True`, `DoF=0`, `FullyConstrained=True`.

The "fully constrained" part is load-bearing and was missed in a first draft of this plan.
`post_verify` requires it on every commit, and a Tangent between two otherwise-free circles leaves
`DoF=5` — so an unpinned fixture fails the commit with `SPEC_FAILED` for a reason that has nothing
to do with the datum being tested. The fixture below pins both circles.

---

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `src/freecad_buddy/usecases/sketches.py` | the `sketch_set_datum` use case | Modify — one constant, one argument, branch on target type |
| `src/freecad_buddy/hosts/tool_catalog.py` | wire schema | Modify — add `sense`, drop `value` from `required` |
| `tests/infc/test_sketch_tools.py` | in-FreeCAD behaviour | Modify — add a `TangencySenseTest` class |
| `tests/external/test_sketch_contract.py` | wire contract | Modify — add one schema test |

---

## Task 1: The `sense` argument

**Files:**
- Modify: `src/freecad_buddy/usecases/sketches.py` — `sketch_set_datum` at line 980, its `_target` at 1001 (verified current)
- Test: `tests/infc/test_sketch_tools.py`

**Interfaces:**
- Consumes: `_resolve_sketch`, `_resolve_constraint_index`, `_positive_datum`, `_DIMENSIONAL`, `_sketch_mutation`, `ValidationError` — all already in `sketches.py`.
- Produces: `sketch_set_datum(registry, doc=None, sketch=None, constraint=None, value=None, sense=None, confirm=None, audit_sink=None)`.

- [ ] **Step 1: Write the failing tests**

Add this class to `tests/infc/test_sketch_tools.py`, immediately before `class NoTransactionLeftOpenTest`:

```python
class TangencySenseTest(_SketchFixture):
    """FreeCAD admits a datum on Tangent and Perpendicular, where it selects a sense.

    SketchObjectConstraints.cpp:194-197 accepts those two alongside the dimensional types, and
    the value chooses the tangency: 0 autodecide, +Pi/2 external, -Pi/2 internal.
    """

    def geometry_count(self):
        sketch = self.document().getObject("Circles")
        return None if sketch is None else int(sketch.GeometryCount)

    def tangent_sketch(self):
        """A fully constrained sketch with a Tangent between two circles; returns its 1-based id.

        The circles are pinned as well as made tangent. ``post_verify`` requires every committed
        sketch to be fully constrained, and a Tangent alone leaves five degrees of freedom, so an
        unpinned pair would fail the commit for a reason unrelated to the datum under test.
        """
        import Part
        import Sketcher

        self.create("Circles", plane="XY")
        document = self.document()
        sketch = document.getObject("Circles")
        sketch.addGeometry(
            Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 5.0), False
        )
        sketch.addGeometry(
            Part.Circle(App.Vector(12, 0, 0), App.Vector(0, 0, 1), 4.0), False
        )
        index = sketch.addConstraint(Sketcher.Constraint("Tangent", 0, 1))
        sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
        sketch.addConstraint(Sketcher.Constraint("Radius", 0, 5.0))
        sketch.addConstraint(Sketcher.Constraint("Radius", 1, 4.0))
        sketch.addConstraint(Sketcher.Constraint("PointOnObject", 1, 3, -1))
        document.recompute()
        self.assertEqual(sketch.DoF, 0, "the fixture must be fully constrained")
        return index + 1

    def test_each_sense_commits_on_a_tangent_constraint(self):
        # All three are asserted, not just the first: a mapping that sent every sense to the
        # same radian value would pass a single-sense test.
        for sense in ("autodecide", "external", "internal"):
            with self.subTest(sense=sense):
                constraint_id = self.tangent_sketch()

                envelope = sketches.sketch_set_datum(
                    self.registry,
                    doc=self.handle,
                    sketch="Circles",
                    constraint=constraint_id,
                    sense=sense,
                )

                self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
                self.assertTrue(self.document().getObject("Circles").isValid())
                self.document().removeObject("Circles")
                self.document().recompute()

    def test_a_value_on_a_tangent_is_rejected_before_the_bracket(self):
        constraint_id = self.tangent_sketch()

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_set_datum,
            self.registry,
            doc=self.handle,
            sketch="Circles",
            constraint=constraint_id,
            value=mm(5.0),
        )

    def test_a_sense_on_a_dimensional_constraint_is_rejected_before_the_bracket(self):
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        self.assert_rejected_pre_bracket(
            lambda: int(self.document().getObject("Rect").GeometryCount),
            sketches.sketch_set_datum,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraint=10,
            sense="external",
        )

    def test_neither_value_nor_sense_is_rejected(self):
        constraint_id = self.tangent_sketch()

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_set_datum,
            self.registry,
            doc=self.handle,
            sketch="Circles",
            constraint=constraint_id,
        )

    def test_both_value_and_sense_is_rejected(self):
        constraint_id = self.tangent_sketch()

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_set_datum,
            self.registry,
            doc=self.handle,
            sketch="Circles",
            constraint=constraint_id,
            value=mm(5.0),
            sense="external",
        )

    def test_a_dimensional_datum_still_commits_with_a_value(self):
        # Pins that widening the tool did not disturb the path that already worked.
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        envelope = sketches.sketch_set_datum(
            self.registry, doc=self.handle, sketch="Rect", constraint=10, value=mm(20.0)
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
```

`mm`, `RECTANGLE_GEOMETRY`, `RECTANGLE_CONSTRAINTS`, `App`, `assert_rejected_pre_bracket`, `create` and `add` are all already in this file — add no imports.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)|FAIL:|ERROR:"
```

Expected: 5 errors — `TypeError: sketch_set_datum() got an unexpected keyword argument 'sense'` — plus `test_a_value_on_a_tangent_is_rejected_before_the_bracket` PASSING, because today's code already refuses a non-dimensional target. `test_a_dimensional_datum_still_commits_with_a_value` also passes: it is today's behaviour.

- [ ] **Step 3: Write the implementation**

Add the constant beside `_DIMENSIONAL` in `sketches.py`:

```python
# SketchObjectConstraints.cpp:194-197 admits a datum on these two alongside the dimensional
# types, where the value selects the tangency rather than a size.
_SENSE_TYPES = frozenset({"Tangent", "Perpendicular"})
# The radian value each named sense maps to, from the same source line.
_SENSE_VALUES = {"autodecide": 0.0, "external": math.pi / 2, "internal": -math.pi / 2}
```

`math` is already imported at the top of the module — confirm before adding it.

Change the signature — add `sense` after `value`:

```python
def sketch_set_datum(
    registry: DocumentRegistry,
    doc: str | None = None,
    sketch: str | None = None,
    constraint: object = None,
    value: dict | None = None,
    sense: str | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
```

Replace the `value is None` guard with the mutual-exclusion rule:

```python
    _require_sketcher()
    if (value is None) == (sense is None):
        raise ValidationError("sketch_set_datum requires exactly one of 'value' and 'sense'")
    if sense is not None and sense not in _SENSE_VALUES:
        raise ValidationError(
            f"sense must be one of {sorted(_SENSE_VALUES)}, got {sense!r}"
        )
```

Rewrite `_target` to branch on the target type:

```python
    def _target(document: object) -> tuple[object, int, float]:
        sketch_obj = _resolve_sketch(document, sketch)
        index = _resolve_constraint_index(sketch_obj, constraint)
        target = sketch_obj.Constraints[index]
        constraint_type = str(getattr(target, "Type", ""))
        if not bool(getattr(target, "Driving", True)):
            raise ValidationError(f"constraint {index + 1} is not driving; its datum is read-only")
        if sense is not None:
            if constraint_type not in _SENSE_TYPES:
                raise ValidationError(
                    f"constraint {index + 1} is a {constraint_type}; a sense applies only to "
                    f"{sorted(_SENSE_TYPES)}"
                )
            return sketch_obj, index, _SENSE_VALUES[sense]
        if constraint_type not in _DIMENSIONAL:
            raise ValidationError(
                f"constraint {index + 1} is a {constraint_type}, not a dimensional constraint"
            )
        datum = _positive_datum(constraint_type, value, f"constraint {index + 1}")
        return sketch_obj, index, datum
```

The driving check moves above the type branch so it applies to both kinds.

Update the docstring's body and `:raises:`:

```
    ``value`` is a ``{value, unit}`` quantity: ``mm`` for a length constraint, ``deg`` for an
    angle. Angles are converted to radians because ``setDatum`` reads a bare float as radians.

    ``sense`` sets the tangency of a ``Tangent`` or ``Perpendicular`` constraint instead:
    ``autodecide``, ``external`` or ``internal``. Exactly one of ``value`` and ``sense`` applies.

    :raises ValidationError: the sketch or constraint is unknown, the target is not driving,
        neither or both of ``value`` and ``sense`` were given, ``sense`` names an unknown
        tangency, or the target's type does not accept the kind of datum given.
```

Add `sense` to the recorded params:

```python
    params = {
        "doc": doc,
        "sketch": sketch,
        "constraint": constraint,
        "value": value,
        "sense": sense,
        "confirm": confirm,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)|FAIL:|ERROR:"
```

Expected: `Ran 596 tests`, `OK (skipped=1)` — the 590 baseline plus these 6.

- [ ] **Step 5: Verify the tests can fail (falsifiability)**

Temporarily make every entry of `_SENSE_VALUES` map to `0.0`. Re-run. Expected:
`test_each_sense_commits_on_a_tangent_constraint` still **passes** — all three senses are legal
values, so a collapsed mapping still commits.

That is a real gap in the test set, and the reason to know it: the in-FreeCAD tests prove each
sense is *accepted*, not that each is *distinct*. Record it in the report, restore the mapping,
and do not attempt to close it here — distinguishing the senses needs a geometric assertion on the
resulting tangency, which is its own piece of work.

Then delete the `if sense is not None:` branch from `_target` and re-run. Expected: **exactly
three** failures — the three-sense test and the two rejection tests that depend on the branch.
Restore.

- [ ] **Step 6: Commit**

```bash
git add src/freecad_buddy/usecases/sketches.py tests/infc/test_sketch_tools.py
git commit -m "feat(sketches): set a tangency sense on Tangent and Perpendicular datums

SketchObjectConstraints.cpp:194-197 admits a datum on those two alongside the
dimensional types, where the value selects the tangency rather than a size: 0
autodecide, +Pi/2 external, -Pi/2 internal. The tool refused them outright, so a
source-documented capability was unreachable.

Verified live on FreeCAD 1.1.1 against a Tangent between two circles before
implementing: setDatum accepts all three values and the sketch stays valid after
each.

The sense is a named enum rather than the shared {value, unit} quantity, because
that field means a measurement on every other datum type; exactly one of value
and sense applies. The driving check moved above the type branch so it guards
both kinds."
```

---

## Task 2: Expose `sense` on the wire

**Files:**
- Modify: `src/freecad_buddy/hosts/tool_catalog.py` — the `sketch_set_datum` registration, currently at line 459
- Test: `tests/external/test_sketch_contract.py`

Line numbers throughout this plan are from the file as it stands now and shift as you edit. Match on the surrounding name — `_sketch_method("sketch_set_datum", ...)` — never on the number.

- [ ] **Step 1: Write the failing test**

```python
def test_sketch_set_datum_takes_a_value_or_a_sense():
    """Exactly one applies, which the use case enforces — the schema requires neither."""
    schema = _specs_by_name()["sketch_set_datum"].input_schema

    assert schema["properties"]["sense"]["enum"] == ["autodecide", "external", "internal"]
    assert "value" not in schema["required"]
    assert "sense" not in schema["required"]
    assert schema["required"] == ["doc", "sketch", "constraint"]
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/external/test_sketch_contract.py -q
```

Expected: FAIL with `KeyError: 'sense'`.

- [ ] **Step 3: Write the implementation**

```python
            _sketch_schema(
                {
                    "sketch": {"type": "string"},
                    "constraint": _CONSTRAINT_REF_SCHEMA,
                    "value": _QUANTITY_SCHEMA,
                    "sense": {
                        "enum": ["autodecide", "external", "internal"],
                        "description": "tangency for a Tangent or Perpendicular constraint",
                    },
                },
                ["sketch", "constraint"],
            ),
            "Change a driving constraint's datum: 'value' for a dimensional constraint (mm for "
            "lengths, deg for angles), or 'sense' for a Tangent or Perpendicular. Exactly one "
            "applies.",
```

Note `value` leaves the required list — a loosening, so no existing call breaks.

- [ ] **Step 4: Run everything**

```bash
uv run pytest tests/external -q
uv run python scripts/check_imports.py
uv run ruff check src/freecad_buddy tests/infc tests/external
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)"
```

Expected: `880 passed` external; `check_imports OK`; ruff reports only the pre-existing `E501` in
`tests/external/test_check_imports.py:302`; `Ran 596 tests`, `OK (skipped=1)`.

- [ ] **Step 5: Commit**

```bash
git add src/freecad_buddy/hosts/tool_catalog.py tests/external/test_sketch_contract.py
git commit -m "feat(hosts): expose sketch_set_datum's tangency sense

'value' leaves the required list so either input is accepted; the use case
enforces that exactly one applies, matching how sketch_create already handles its
mutually exclusive plane/face pair."
```

---

## Task 3: Verify over live MCP

**Files:** none.

- [ ] **Step 1: Reload the addon**

Quit FreeCAD and start it again. Confirm the reload with a date-aware comparison — comparing
clock times alone misleads across a date boundary:

```bash
powershell -NoProfile -Command "\$p=Get-Process -Name freecad; \$f=Get-Item 'D:\Work\Personal\Sources\freecad-buddy\src\freecad_buddy\usecases\sketches.py'; 'started: '+\$p.StartTime.ToString('yyyy-MM-dd HH:mm:ss'); 'mtime  : '+\$f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'); 'file newer than process: '+(\$f.LastWriteTime -gt \$p.StartTime)"
```

Expected: `file newer than process: False`.

- [ ] **Step 2: Drive it**

Build a sketch with two circles and a `Tangent` between them, then call `sketch_set_datum` with
`sense: "external"` through `preview_dry_run` and the confirmed call. Expect `OK`.

Then confirm the enum binds: call the tool **directly** with `sense: "sideways"` and expect a
schema-gate refusal with no envelope.

Note the enum binds a direct call but not one routed through `preview_dry_run`, whose
`operation.args` is a generic object — the same limit recorded in DW-82's closure. Do not report a
preview-routed rejection as proof the enum is enforced.

- [ ] **Step 3: Record the result**

State what was verified and what was not. This proves a sense commits over the real transport and
that the enum binds a direct call. It does **not** prove the three senses produce different
geometry — see the Step 5 gap in Task 1.

No commit.
