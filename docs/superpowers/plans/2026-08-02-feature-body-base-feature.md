# `feature_body_create` base-feature adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `feature_body_create` an optional `base_feature` argument so a Body can adopt an existing solid, which is what the 35 blocked G2 dev cases need.

**Architecture:** One optional argument on an existing use case, plus one resolver that owns the validation FreeCAD does not do. No new tool, no new machinery — the existing `_feature_mutation` bracket carries preview, confirm, snapshot and rollback.

**Tech Stack:** Python 3.11, FreeCAD 1.1 App API, stdlib `unittest` under `FreeCADCmd`, pytest under `uv`.

## Global Constraints

- Ring rule: `usecases/` may import stdlib + FreeCAD App only; `hosts/` may import Qt/`FreeCADGui`. Enforced by `uv run python scripts/check_imports.py`.
- Any FreeCAD enum, property name or API semantic must be confirmed against `docs/references/FreeCAD/` before use — never assumed.
- Comments and docstrings document what the code does and its params/returns/raises. No requirement ids, no spec-section citations, no design rationale inline.
- Two test worlds, never mixed: `tests/infc/` runs under `FreeCADCmd`, `tests/external/` under pytest.
- Commit messages use Conventional Commits, no AI attribution, no `Co-Authored-By`.
- Surgical changes: every changed line traces to this goal. Do not "improve" adjacent code.

**Commands used throughout** (run from the repo root, `D:\Work\Personal\Sources\freecad-buddy`):

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py

uv run pytest tests/external -q
uv run python scripts/check_imports.py
uv run ruff check src/freecad_buddy tests/infc tests/external
```

Baseline before this plan: **579 in-FreeCAD tests pass (1 skipped), 875 external pass.**

---

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `src/freecad_buddy/usecases/features.py` | the `feature_body_create` use case | Modify — one resolver, one argument, one assignment |
| `src/freecad_buddy/hosts/tool_catalog.py` | wire schema for `feature_body_create` | Modify — add one optional property |
| `tests/infc/test_feature_tools.py` | in-FreeCAD behaviour tests | Modify — extend `BodyCreateTest` |
| `tests/external/test_feature_contract.py` | wire contract | Modify — extend the existing `feature_body_create` schema test |

No tool is added, so the tool-count sets in `test_feature_contract.py`, `test_mcp_surface.py` and `test_confirm_contract.py` are all unaffected. **Do not touch them.**

---

## Task 1: `base_feature` on the use case

**Files:**
- Modify: `src/freecad_buddy/usecases/features.py` — `feature_body_create` at line 1567
- Test: `tests/infc/test_feature_tools.py` — the existing `BodyCreateTest` class

**Interfaces:**
- Consumes: `_feature_mutation`, `_name_available`, `_require_partdesign`, `_resolve_object`, `_BODY_TYPE`, `ValidationError` — all already in `features.py`.
- Produces: `feature_body_create(registry, doc=None, name=None, base_feature=None, confirm=None, audit_sink=None) -> ResultEnvelope`. Task 2 registers `base_feature` on the wire.

**The point of this task:** FreeCAD validates none of the malformed inputs. Measured on 1.1.1 — a sketch, a shapeless object, and a solid already adopted by another Body are all **accepted silently**, producing either a null-shaped Body or two Bodies claiming the same geometry. The precheck owns all of it.

- [ ] **Step 1: Write the failing tests**

Add these methods to the existing `class BodyCreateTest` in `tests/infc/test_feature_tools.py`:

```python
    def test_a_body_adopts_an_existing_solid_as_its_base_feature(self):
        document = self.document()
        document.addObject("Part::Box", "Box")
        document.recompute()

        envelope = features.feature_body_create(
            self.registry, doc=self.handle, name="Bracket", base_feature="Box"
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        body = document.getObject("Bracket")
        self.assertIsNotNone(body.Tip)
        self.assertAlmostEqual(body.Shape.Volume, 10.0 * 10.0 * 10.0, places=6)

    def test_a_pad_on_an_adopted_body_adds_to_the_adopted_solid(self):
        # The arithmetic the 35 blocked G2 dev cases encode: the expected volume is the
        # fixture's solid plus the feature, not the feature alone.
        document = self.document()
        document.addObject("Part::Box", "Box")
        document.recompute()
        created = features.feature_body_create(
            self.registry, doc=self.handle, name="Bracket", base_feature="Box"
        )
        self.assertEqual(created["status"], "OK", created.get("detail"))
        body = document.getObject("Bracket")
        self.rect_sketch(body, "Profile", 2.0, 2.0, 4.0, 4.0, z=10.0)

        envelope = features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Bracket",
            profile="Profile",
            name="Block",
            length=mm(5.0),
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        pad = document.getObject("Block")
        self.assertAlmostEqual(pad.Shape.Volume, 1000.0 + 4.0 * 4.0 * 5.0, places=6)

    def test_omitting_base_feature_still_creates_an_empty_body(self):
        envelope = features.feature_body_create(
            self.registry, doc=self.handle, name="Bracket"
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        body = self.document().getObject("Bracket")
        self.assertIsNone(body.Tip)
        self.assertTrue(body.Shape.isNull())

    def test_a_sketch_as_base_feature_is_rejected_before_the_bracket(self):
        # FreeCAD accepts this silently and leaves the Body with a null shape and status
        # 'Touched', so nothing downstream would report it.
        document = self.document()
        document.addObject("Sketcher::SketchObject", "Sketchy")
        document.recompute()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_body_create,
            self.registry,
            doc=self.handle,
            name="Bracket",
            base_feature="Sketchy",
        )

    def test_a_shapeless_object_as_base_feature_is_rejected_before_the_bracket(self):
        document = self.document()
        document.addObject("App::FeaturePython", "NoShape")
        document.recompute()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_body_create,
            self.registry,
            doc=self.handle,
            name="Bracket",
            base_feature="NoShape",
        )

    def test_a_solid_another_body_already_adopted_is_rejected(self):
        # Measured: FreeCAD permits this and leaves BOTH Bodies reporting the same volume,
        # which no later check in this bridge would catch.
        document = self.document()
        document.addObject("Part::Box", "Box")
        document.recompute()
        first = features.feature_body_create(
            self.registry, doc=self.handle, name="First", base_feature="Box"
        )
        self.assertEqual(first["status"], "OK", first.get("detail"))

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_body_create,
            self.registry,
            doc=self.handle,
            name="Second",
            base_feature="Box",
        )

    def test_an_unknown_base_feature_is_rejected_before_the_bracket(self):
        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_body_create,
            self.registry,
            doc=self.handle,
            name="Bracket",
            base_feature="NoSuchObject",
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)|FAIL:|ERROR:"
```

Expected: 6 errors — `TypeError: feature_body_create() got an unexpected keyword argument 'base_feature'` — and `test_omitting_base_feature_still_creates_an_empty_body` PASSING, since that is today's behaviour. If that seventh test fails, stop and read it.

- [ ] **Step 3: Write the implementation**

Add the constant beside `_BODY_TYPE` near the top of `features.py`:

```python
_FEATURE_BASE_TYPE = "PartDesign::FeatureBase"
```

Add the resolver immediately before `def feature_body_create`:

```python
def _resolve_base_feature(document: object, name: str) -> object:
    """Return the object ``name`` for adoption as a Body's ``BaseFeature``.

    FreeCAD accepts an unusable target silently — a sketch or a shapeless object leaves the Body
    with a null shape, and a solid a second Body already adopted leaves both Bodies reporting the
    same geometry — so each is rejected here rather than committed.

    Adoption is read from the candidate's ``InList``: an adopted object gains a
    ``PartDesign::FeatureBase`` entry there, which a merely referenced object does not.

    :raises ValidationError: the object is unknown, carries no usable shape, or is already
        adopted by another Body.
    """
    target = _resolve_object(document, name, "base_feature")
    shape = getattr(target, "Shape", None)
    if shape is None or shape.isNull():
        raise ValidationError(f"base_feature {name} carries no shape to adopt")
    owners = [str(getattr(obj, "TypeId", "")) for obj in target.InList]
    if _FEATURE_BASE_TYPE in owners:
        raise ValidationError(f"base_feature {name} is already adopted by a Body")
    return target
```

Change the signature — add `base_feature` after `name`:

```python
def feature_body_create(
    registry: DocumentRegistry,
    doc: str | None = None,
    name: str | None = None,
    base_feature: str | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
```

Add one sentence to the docstring body and extend the `:raises:` line:

```
    ``base_feature`` optionally names an existing solid for the Body to adopt, so later features
    modify that solid instead of building from nothing.

    :raises ValidationError: the name is missing, already in use, or one FreeCAD would rewrite;
        or ``base_feature`` is unknown, carries no shape, or is already adopted by another Body.
```

Extend `precheck` and `op`:

```python
    def precheck(document: object) -> None:
        _name_available(document, name)
        if base_feature is not None:
            _resolve_base_feature(document, base_feature)

    def op(document: object) -> list[str]:
        body = document.addObject(_BODY_TYPE, name)
        if body.Name != name:
            raise ValidationError(f"{name} is not a usable FreeCAD object name")
        body.Label = name
        if base_feature is not None:
            body.BaseFeature = _resolve_base_feature(document, base_feature)
        return [body.Name]
```

Add `base_feature` to the recorded params:

```python
    params = {"doc": doc, "name": name, "base_feature": base_feature, "confirm": confirm}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)|FAIL:|ERROR:"
```

Expected: `Ran 586 tests`, `OK (skipped=1)` — the 579 baseline plus these 7.

- [ ] **Step 5: Verify the tests can fail (falsifiability)**

Two separate checks, because they guard different things:

1. Temporarily delete the two lines `if base_feature is not None: body.BaseFeature = ...` from `op`. Re-run. Expected: **exactly two** failures — `test_a_body_adopts_an_existing_solid_as_its_base_feature` and `test_a_pad_on_an_adopted_body_adds_to_the_adopted_solid`. Restore.
2. Temporarily delete the two lines `if base_feature is not None: _resolve_base_feature(...)` from `precheck`. Re-run. Expected: **exactly four** failures — the four `_rejected` tests. Restore.

If either check produces a different count, stop and report — a test is not guarding what it claims.

- [ ] **Step 6: Commit**

```bash
git add src/freecad_buddy/usecases/features.py tests/infc/test_feature_tools.py
git commit -m "feat(usecases): let a new Body adopt an existing solid

35 of the 40 G2 dev cases name a body their fixture does not contain, and an
empty Body cannot serve them: every expected volume is the fixture's solid plus
the feature, so g2-dev-006-pad expects 6640 = box 6000 + pad 640. A Body that
adopts the fixture solid as its BaseFeature produces exactly that arithmetic,
measured on FreeCAD 1.1.1 as 6360.0 for a 6x12x5 pad on the box.

The precheck owns the validation because FreeCAD does none of it. Measured: a
sketch and a shapeless object are both accepted silently, leaving the Body with a
null shape and status Touched, and a solid a second Body adopts is also accepted,
leaving both Bodies reporting the same geometry. Adoption is detected from the
candidate's InList, where an adopted object gains a PartDesign::FeatureBase entry
that a merely referenced object does not."
```

---

## Task 2: Expose `base_feature` on the wire schema

**Files:**
- Modify: `src/freecad_buddy/hosts/tool_catalog.py` — the `feature_body_create` registration
- Test: `tests/external/test_feature_contract.py` — the existing `test_feature_body_create_takes_only_a_name`

**Interfaces:**
- Consumes: `features.feature_body_create` from Task 1; `_feature_schema`, `_FEATURE_NAME_SCHEMA`.
- Produces: `feature_body_create`'s input schema carrying an optional `base_feature` string.

**An existing test pins the exact property set and will fail until it is updated** — that is the intended safety net:

```python
# tests/external/test_feature_contract.py, test_feature_body_create_takes_only_a_name
assert set(schema["properties"]) == {"doc", "name", "confirm"}
```

- [ ] **Step 1: Update the existing test to its new contract**

Rename it and extend it — the tool no longer takes "only a name":

```python
def test_feature_body_create_takes_a_name_and_an_optional_base_feature():
    """The Body creator needs no body argument — it is what produces one."""
    schema = _specs_by_name()["feature_body_create"].input_schema

    assert set(schema["properties"]) == {"doc", "name", "base_feature", "confirm"}
    assert schema["required"] == ["doc", "name"]
    assert schema["properties"]["base_feature"]["type"] == "string"
    assert "body" not in schema["properties"]
```

Do not weaken the `==` to a subset check. The exact property set is what catches an accidentally added or dropped field.

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/external/test_feature_contract.py -q
```

Expected: FAIL — the property set is still `{"doc", "name", "confirm"}`.

- [ ] **Step 3: Write the implementation**

In `src/freecad_buddy/hosts/tool_catalog.py`, extend the `feature_body_create` schema. `required` stays `["name"]`:

```python
            _feature_schema(
                {
                    "name": _FEATURE_NAME_SCHEMA,
                    "base_feature": {
                        "type": "string",
                        "description": "existing solid Name for the Body to adopt",
                    },
                },
                ["name"],
            ),
            "Create a PartDesign Body, the container every feature_* tool builds into. Empty by "
            "default; pass 'base_feature' to adopt an existing solid so later features modify it.",
```

- [ ] **Step 4: Run the full suites**

```bash
uv run pytest tests/external -q
uv run python scripts/check_imports.py
uv run ruff check src/freecad_buddy tests/infc tests/external
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)"
```

Expected: `875 passed` external (the count is unchanged — the test was renamed, not added); `check_imports OK`; ruff reports only the pre-existing `E501` in `tests/external/test_check_imports.py:302` (do not fix it); `Ran 586 tests`, `OK (skipped=1)`.

- [ ] **Step 5: Commit**

```bash
git add src/freecad_buddy/hosts/tool_catalog.py tests/external/test_feature_contract.py
git commit -m "feat(hosts): expose feature_body_create's optional base_feature

Optional and additive: 'required' is unchanged, so a call omitting it still
creates an empty Body. The contract test's exact property-set assertion was grown
rather than relaxed, and renamed — the tool no longer takes only a name."
```

---

## Task 3: Verify adoption over live MCP

**Files:** none — this task changes no code.

**Interfaces:** consumes the registered `base_feature` field from Task 2.

- [ ] **Step 1: Reload the addon**

The GUI host imports the package at startup, so a running FreeCAD holds the pre-change modules. Quit FreeCAD and start it again, then confirm the reload took by ordering:

```bash
powershell -NoProfile -Command "'freecad started: ' + (Get-Process -Name freecad).StartTime; 'features.py mtime: ' + (Get-Item 'D:\Work\Personal\Sources\freecad-buddy\src\freecad_buddy\usecases\features.py').LastWriteTime"
```

Expected: the process start time is **later** than the file mtime.

- [ ] **Step 2: Drive the real case arithmetic**

Open a golden model and reproduce what a blocked dev case needs:

1. `document_open(path=".../benchmarks/g0/golden-models/box-10-20-30.FCStd")` — the fixture is a single `Part::Feature` named `Box`, volume 6000.0.
2. `feature_body_create(name="Bracket", base_feature="Box")` via `preview_dry_run` then the confirmed call.
3. `query_mass_properties(object="Bracket")` → expect volume **6000.0**: the Body now reports the adopted solid.
4. `sketch_create(name="Prof", plane="XY", body="Bracket")`, then `sketch_add_geometry` for a 6×12 rectangle fully constrained, then `feature_pad(body="Bracket", profile="Prof", name="Block", length=5mm)`.
5. `query_mass_properties(object="Block")` → expect **6360.0**, the fixture-plus-feature arithmetic.

Close the document **without saving** — the golden models are committed fixtures and must not be modified.

- [ ] **Step 3: Record the result**

State what was verified and what was not. This proves adoption works over the real transport against a real fixture. It does **not** mean the 35 dev cases now run: they still need the command resolver G2.1 reports, and their `case.yaml` files carry no `tool`/`args` for a driver (DW-96). This removed the fixture blocker only.

No commit — this task produces no artifact.
