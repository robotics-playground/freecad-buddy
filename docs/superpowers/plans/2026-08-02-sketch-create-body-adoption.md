# `sketch_create` body adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `sketch_create` an optional `body` argument so a profile sketch lives inside the Body that consumes it, instead of at document root.

**Architecture:** One optional argument on an existing use case, applied to both creation branches, with a local Body resolver in `sketches.py`. No new tool, no new machinery — the existing `_sketch_mutation` bracket already carries preview, confirm, snapshot and rollback.

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

Baseline before this plan: **573 in-FreeCAD tests pass (1 skipped), 874 external pass.**

---

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `src/freecad_buddy/usecases/sketches.py` | the `sketch_create` use case | Modify — one constant, one resolver, one argument, adoption on both branches |
| `src/freecad_buddy/hosts/tool_catalog.py` | wire schema for `sketch_create` | Modify — add one optional property |
| `tests/infc/test_sketch_tools.py` | in-FreeCAD behaviour tests | Modify — add one `BodyAdoptionTest` class |
| `tests/external/test_sketch_contract.py` | wire contract | Modify — add one schema test |

No tool is added, so the tool-count sets in `test_mcp_surface.py`, `test_sketch_contract.py` and `test_confirm_contract.py` are all unaffected. Do not touch them.

---

## Task 1: Optional `body` on the use case

**Files:**
- Modify: `src/freecad_buddy/usecases/sketches.py` — `sketch_create` at line 576, its `precheck` at 604, its `op` at 613
- Test: `tests/infc/test_sketch_tools.py`

**Interfaces:**
- Consumes: `_sketch_mutation(registry, doc, sketch, label, tool, params, op, audit_sink, precheck) -> ResultEnvelope`, `ValidationError`, `_selector_subelement`, `_require_planar_face`, `shim.set_attachment` — all already in `sketches.py`.
- Produces: `sketch_create(registry, doc=None, name=None, plane=None, face=None, body=None, confirm=None, audit_sink=None) -> ResultEnvelope`. Task 2 registers the `body` field on the wire.

- [ ] **Step 1: Write the failing tests**

Add this class to `tests/infc/test_sketch_tools.py`, immediately before `class NoTransactionLeftOpenTest`:

```python
class BodyAdoptionTest(_SketchFixture):
    """A profile sketch belongs inside the Body that consumes it.

    Without adoption the sketch sits at document root and PartDesign reports the pad's profile
    link as out of the allowed scope, because those link properties are LinkScope::Child.
    """

    def geometry_count(self):
        sketch = self.document().getObject("Prof")
        return None if sketch is None else int(sketch.GeometryCount)

    def make_body(self, name="Bracket"):
        document = self.document()
        body = document.addObject("PartDesign::Body", name)
        document.recompute()
        return body

    def test_a_sketch_created_with_a_body_is_adopted_into_it(self):
        body = self.make_body()

        envelope = sketches.sketch_create(
            self.registry, doc=self.handle, name="Prof", plane="XY", body="Bracket"
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIn("Prof", [obj.Name for obj in body.Group])

    def test_a_sketch_created_without_a_body_stays_at_document_root(self):
        body = self.make_body()

        envelope = sketches.sketch_create(
            self.registry, doc=self.handle, name="Prof", plane="XY"
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertNotIn("Prof", [obj.Name for obj in body.Group])

    def test_a_face_attached_sketch_is_adopted_too(self):
        # The two creation branches return separately, so a fix applied to the base-plane path
        # alone would leave this one unadopted.
        body = self.make_body()
        document = self.document()
        box = document.addObject("Part::Box", "Box")
        document.recompute()

        envelope = sketches.sketch_create(
            self.registry,
            doc=self.handle,
            name="Prof",
            face={"kind": "mapped_name", "object": "Box", "mapped_name": "Face1"},
            body="Bracket",
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIn("Prof", [obj.Name for obj in body.Group])

    def test_adopting_a_sketch_leaves_the_body_tip_unset(self):
        # Body.addObject advances Tip for a solid feature; a sketch is not one.
        body = self.make_body()

        sketches.sketch_create(
            self.registry, doc=self.handle, name="Prof", plane="XY", body="Bracket"
        )

        self.assertIsNone(body.Tip)

    def test_an_unknown_body_is_rejected_before_the_bracket(self):
        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_create,
            self.registry,
            doc=self.handle,
            name="Prof",
            plane="XY",
            body="NoSuchBody",
        )

    def test_a_body_naming_a_non_body_object_is_rejected_before_the_bracket(self):
        document = self.document()
        document.addObject("Part::Box", "Box")
        document.recompute()

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_create,
            self.registry,
            doc=self.handle,
            name="Prof",
            plane="XY",
            body="Box",
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)|FAIL:|ERROR:"
```

Expected: 5 errors — `TypeError: sketch_create() got an unexpected keyword argument 'body'` — and `test_a_sketch_created_without_a_body_stays_at_document_root` PASSING, since that is today's behaviour. If that sixth test fails too, stop and read it.

- [ ] **Step 3: Write the implementation**

Add the constant beside the other module constants near the top of `sketches.py` (the group holding `_BASE_PLANES`):

```python
_BODY_TYPE = "PartDesign::Body"
```

Add the resolver immediately before `def sketch_create`:

```python
def _resolve_body(document: object, name: str) -> object:
    """Return the ``PartDesign::Body`` named ``name``, or raise ``ValidationError``.

    Kept local rather than imported from the feature tools: this module does not otherwise
    depend on them, and one predicate is not worth coupling the two tool families.
    """
    obj = document.getObject(name)
    if obj is None:
        raise ValidationError(f"unknown object in body: {name}")
    if str(getattr(obj, "TypeId", "")) != _BODY_TYPE:
        raise ValidationError(f"object is not a PartDesign Body: {name}")
    return obj
```

Change the signature — add `body` after `face`, keeping every other parameter in place:

```python
def sketch_create(
    registry: DocumentRegistry,
    doc: str | None = None,
    name: str | None = None,
    plane: str | None = None,
    face: dict | None = None,
    body: str | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
```

Extend the docstring's `:raises:` line to mention the new rejection, and add one sentence to the body describing the argument:

```
    ``body`` optionally names a ``PartDesign::Body`` to adopt the new sketch into, so a profile
    consumed by a feature lives inside the Body that consumes it. Omitted, the sketch is created
    at document level.
```

In `precheck`, add the body check after the existing name check:

```python
    def precheck(document: object) -> None:
        if document.getObject(name) is not None:
            raise ValidationError(f"an object named {name} already exists")
        if body is not None:
            _resolve_body(document, body)
        if support is not None:
            target = document.getObject(support[0])
            if target is None:
                raise ValidationError(f"unknown object in face selector: {support[0]}")
            _require_planar_face(target, support[1])
```

In `op`, adopt on BOTH branches. The base-plane branch returns early, so the adoption call must come before that return:

```python
    def op(document: object) -> list[str]:
        import FreeCAD

        sketch = document.addObject("Sketcher::SketchObject", name)
        if sketch.Name != name:
            raise ValidationError(f"{name} is not a usable FreeCAD object name")
        if body is not None:
            _resolve_body(document, body).addObject(sketch)
        if support is None:
            sketch.Placement = FreeCAD.Placement(
                FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation(*_BASE_PLANES[plane])
            )
            return [name]
        target = document.getObject(support[0])
        if target is None:
            raise ValidationError(f"unknown object in face selector: {support[0]}")
        _require_planar_face(target, support[1])
        shim.set_attachment(sketch, [(target, [support[1]])], "FlatFace")
        return [name]
```

Add `body` to the recorded params so the audit line and the preview digest carry it:

```python
    params = {
        "doc": doc,
        "name": name,
        "plane": plane,
        "face": face,
        "body": body,
        "confirm": confirm,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)|FAIL:|ERROR:"
```

Expected: `Ran 579 tests`, `OK (skipped=1)` — the 573 baseline plus these 6.

- [ ] **Step 5: Verify the tests can fail (falsifiability)**

Two separate checks, because they guard different things:

1. Temporarily delete the `if body is not None: _resolve_body(document, body).addObject(sketch)` line from `op`. Re-run. Expected: **exactly two** failures — `test_a_sketch_created_with_a_body_is_adopted_into_it` and `test_a_face_attached_sketch_is_adopted_too`. Restore.
2. Temporarily delete the `if body is not None: _resolve_body(document, body)` line from `precheck`. Re-run. Expected: **exactly two** failures — the two `_rejected_before_the_bracket` tests. Restore.

If either check produces a different count, stop and report — a test is not guarding what it claims.

- [ ] **Step 6: Commit**

```bash
git add src/freecad_buddy/usecases/sketches.py tests/infc/test_sketch_tools.py
git commit -m "feat(sketches): adopt a new sketch into an optional Body

sketch_create added its sketch at document level, so a profile consumed by a pad
lived outside the Body that padded it and PartDesign reported the link as out of
the allowed scope — those link properties are LinkScope::Child, so a link is
expected to resolve inside the owner's group.

Measured on FreeCAD 1.1.1 before changing anything: the geometry is identical
either way. Same volume, both valid and Up-to-date, and the unadopted case
survives save and reopen with its profile link still resolving. The cost is
structural rather than geometric — the sketch sits outside the tree a user
expects — which is why this is an optional argument rather than a forced change
of behaviour.

Adoption is applied to both creation branches: the base-plane path returns early,
so a fix on that path alone would leave a face-attached sketch unadopted."
```

---

## Task 2: Expose `body` on the wire schema

**Files:**
- Modify: `src/freecad_buddy/hosts/tool_catalog.py:356-368` (the `sketch_create` registration)
- Test: `tests/external/test_sketch_contract.py`

**Interfaces:**
- Consumes: `sketches.sketch_create` from Task 1; `_sketch_schema(properties, required)` already in `tool_catalog.py`.
- Produces: `sketch_create`'s input schema carrying an optional `body` string.

No tool is added, so no tool-count set changes. Do not edit `test_mcp_surface.py`, `test_confirm_contract.py`, or the `SKETCH_TOOLS` set.

- [ ] **Step 1: Write the failing test**

Add to `tests/external/test_sketch_contract.py`, after the existing per-tool schema tests:

```python
def test_sketch_create_takes_an_optional_body():
    """A profile sketch can name the Body that will consume it; omitting it is still valid."""
    schema = {spec.name: spec for spec in tool_specs()}["sketch_create"].input_schema

    assert schema["properties"]["body"]["type"] == "string"
    assert "body" not in schema["required"]
```

`tool_specs` is already imported in this file; add no imports.

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/external/test_sketch_contract.py -q
```

Expected: FAIL with `KeyError: 'body'`.

- [ ] **Step 3: Write the implementation**

In `src/freecad_buddy/hosts/tool_catalog.py`, extend the `sketch_create` schema properties. The `required` list stays `["name"]`:

```python
            _sketch_schema(
                {
                    "name": {"type": "string"},
                    "plane": {"enum": ["XY", "XZ", "YZ"]},
                    "face": _SUBELEMENT_SELECTOR_SCHEMA,
                    "body": {
                        "type": "string",
                        "description": "PartDesign Body Name to adopt the sketch into",
                    },
                },
                ["name"],
            ),
```

Extend the description string to mention it:

```python
            "Create a sketch on a base plane (XY/XZ/YZ) or attached to a planar face. "
            "A new sketch is empty, so it commits fully constrained. Pass 'body' to place it "
            "inside the Body that will consume it.",
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

Expected: `875 passed` external (874 baseline plus this one); `check_imports OK`; ruff reports only the pre-existing `E501` in `tests/external/test_check_imports.py:302` (do not fix it); `Ran 579 tests`, `OK (skipped=1)`.

- [ ] **Step 5: Commit**

```bash
git add src/freecad_buddy/hosts/tool_catalog.py tests/external/test_sketch_contract.py
git commit -m "feat(hosts): expose sketch_create's optional body on the wire

Optional and additive: 'required' is unchanged, so every existing call continues
to produce the tree it produces today."
```

---

## Task 3: Verify over live MCP that the warning is gone

**Files:** none — this task changes no code.

**Interfaces:** consumes the registered `body` field from Task 2.

- [ ] **Step 1: Reload the addon**

The GUI host imports the package at startup, so a running FreeCAD holds the pre-change modules. Quit FreeCAD and start it again, then confirm the reload took by ordering:

```bash
powershell -NoProfile -Command "'freecad started: ' + (Get-Process -Name freecad).StartTime; 'sketches.py mtime: ' + (Get-Item 'D:\Work\Personal\Sources\freecad-buddy\src\freecad_buddy\usecases\sketches.py').LastWriteTime"
```

Expected: the process start time is **later** than the file mtime. If not, the old code is still loaded.

- [ ] **Step 2: Drive the chain and assert the tree**

Build `feature_body_create` → `sketch_create(body=...)` → `sketch_add_geometry` → `feature_pad`, each mutation preceded by its own `preview_dry_run` for the confirm token.

**Do not try to assert on the warning text.** It was measured on FreeCAD 1.1.1 and does not reach the addon log, `getStatusString()`, or `State` — it is emitted to the GUI Report View only, so there is nothing to grep. The observable consequence is tree membership, which is what to assert:

- `query_tree_summary(doc, depth=3)` shows the sketch nested under the Body, not as a sibling at document root.
- The pad returns `status: OK` with a volume matching the profile area times the length.

Then repeat the chain once with `body` omitted and confirm the sketch appears at root instead — that contrast is what proves the argument is doing the work, rather than the tree happening to look right.

- [ ] **Step 3: Record the result**

State what was verified and what was not. This task proves adoption changes the committed tree over the real transport. It does not prove the Report View warning is gone, because that warning is not observable from any API this bridge can read — if you want that confirmed, it needs a human looking at the FreeCAD Report View.

No commit — this task produces no artifact.
