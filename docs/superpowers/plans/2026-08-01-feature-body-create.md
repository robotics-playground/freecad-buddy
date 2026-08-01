# `feature_body_create` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one mutation tool that creates an empty `PartDesign::Body`, so the ten existing `feature_*` tools become reachable over MCP.

**Architecture:** A use case in `usecases/features.py` beside its siblings, run through the existing `_feature_mutation` bracket so it inherits preview, confirm, snapshot, rollback proof and audit with no new machinery. Registered in `hosts/tool_catalog.py` through the same `_feature_method`/`_feature_schema` helpers every feature tool uses.

**Tech Stack:** Python 3.11, FreeCAD 1.1 App API, stdlib `unittest` under `FreeCADCmd` for in-FreeCAD tests, pytest under `uv` for external tests.

## Global Constraints

- Ring rule: `usecases/` may import stdlib + FreeCAD App only; `hosts/` may import Qt/`FreeCADGui`. Enforced by `uv run python scripts/check_imports.py`.
- Any FreeCAD enum, property name or API semantic must be confirmed against `docs/references/FreeCAD/` before use — never assumed.
- Comments and docstrings document what the code does and its params/returns/raises. No requirement ids, no spec-section citations, no design rationale inline.
- Two test worlds, never mixed: `tests/infc/` runs under `FreeCADCmd`, `tests/external/` under pytest.
- Commit messages use Conventional Commits, no AI attribution, no `Co-Authored-By`.

**Commands used throughout** (run from the repo root, `D:\Work\Personal\Sources\freecad-buddy`):

```bash
# in-FreeCAD suite (bash; PATH must carry the fcb env's Library/bin or FreeCAD fails 0xC0000135)
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py

# external suite
uv run pytest tests/external -q

# gates
uv run python scripts/check_imports.py
uv run ruff check src/freecad_buddy tests/infc tests/external
```

Baseline before this plan: **568 in-FreeCAD tests pass (1 skipped), 873 external pass.**

---

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `src/freecad_buddy/usecases/features.py` | the `feature_body_create` use case | Modify — add one function |
| `src/freecad_buddy/hosts/tool_catalog.py` | wire-surface registration | Modify — add one `_feature_method` entry |
| `tests/infc/test_feature_tools.py` | in-FreeCAD behaviour tests | Modify — add one `BodyCreateTest` class |
| `tests/external/test_feature_contract.py` | feature-tool catalog contract | Modify — extend `FEATURE_TOOLS`, rename two "ten" tests |
| `tests/external/test_mcp_surface.py` | wire-surface tool list | Modify — extend `EXPECTED_FEATURE_TOOLS` |

---

## Task 1: The `feature_body_create` use case

**Files:**
- Modify: `src/freecad_buddy/usecases/features.py` (add after `feature_datum`, which ends at line 1568)
- Test: `tests/infc/test_feature_tools.py`

**Interfaces:**
- Consumes: `_feature_mutation(registry, doc, feature, label, tool, params, op, audit_sink, precheck) -> ResultEnvelope`; `_name_available(document, name) -> str`; `_require_partdesign() -> None`; `_BODY_TYPE = "PartDesign::Body"` — all already in `features.py`.
- Produces: `feature_body_create(registry, doc=None, name=None, confirm=None, audit_sink=None) -> ResultEnvelope`. Task 2 registers this exact signature.

- [ ] **Step 1: Write the failing tests**

Add this class to `tests/infc/test_feature_tools.py`, immediately before `class SetParametersTest`:

```python
class BodyCreateTest(_FeatureFixture):
    """The Body creator: every feature_* tool needs a Body no other tool could make.

    _FeatureFixture.empty_body builds one with document.addObject directly, which is why the
    gap never surfaced in these tests — nothing here went through the tool surface.
    """

    def test_a_created_body_is_an_empty_partdesign_body(self):
        envelope = features.feature_body_create(
            self.registry, doc=self.handle, name="Bracket"
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        body = self.document().getObject("Bracket")
        self.assertIsNotNone(body)
        self.assertEqual(body.TypeId, "PartDesign::Body")
        self.assertEqual(body.Label, "Bracket")
        self.assertIsNone(body.Tip)
        self.assertEqual(list(body.Group), [])

    def test_a_pad_succeeds_against_a_body_this_tool_created(self):
        # The end-to-end proof that the gap is closed: before this tool existed, no MCP caller
        # could reach feature_pad at all, because nothing could produce its 'body' argument.
        created = features.feature_body_create(
            self.registry, doc=self.handle, name="Bracket"
        )
        self.assertEqual(created["status"], "OK", created.get("detail"))
        body = self.document().getObject("Bracket")
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)

        envelope = features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Bracket",
            profile="Profile",
            name="Block",
            length=mm(5.0),
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        pad = self.document().getObject("Block")
        self.assertTrue(pad.isValid())
        self.assertAlmostEqual(pad.Shape.Volume, 8.0 * 16.0 * 5.0, places=6)

    def test_a_name_already_in_use_is_rejected_before_the_bracket(self):
        # FreeCAD uniquifies a duplicate to "Bracket001" rather than raising, so an unchecked
        # collision would hand back an object under a name the caller never asked for.
        first = features.feature_body_create(self.registry, doc=self.handle, name="Bracket")
        self.assertEqual(first["status"], "OK", first.get("detail"))

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_body_create,
            self.registry,
            doc=self.handle,
            name="Bracket",
        )

    def test_a_name_freecad_would_rewrite_is_rejected_before_the_bracket(self):
        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_body_create,
            self.registry,
            doc=self.handle,
            name="1Bracket",
        )

    def test_the_bodys_origin_children_stay_out_of_the_fingerprint(self):
        # A Body brings App::Origin plus its Plane/Line/Point children. They are datum features,
        # which fingerprint() already skips; asserted here so a later change cannot let the
        # infinite-extent planes back into the digest.
        features.feature_body_create(self.registry, doc=self.handle, name="Bracket")
        document = self.document()

        origin_types = {o.TypeId for o in document.Objects if o.TypeId.startswith("App::")}
        self.assertTrue(origin_types, "a Body must bring its Origin children")
        record = fingerprint.fingerprint(document)

        self.assertEqual([entry["name"] for entry in record["objects"]], [])
```

`tests/infc/test_feature_tools.py:22` currently reads `from freecad_buddy.usecases import confirm, features, transaction`. The last test needs `fingerprint`, so extend that line to:

```python
from freecad_buddy.usecases import confirm, features, fingerprint, transaction
```

`mm`, `rect_sketch`, `object_count`, `document` and `assert_rejected_pre_bracket` are all already defined in this file — add nothing else.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)|FAIL:|ERROR:"
```

Expected: 5 errors, each `AttributeError: module 'freecad_buddy.usecases.features' has no attribute 'feature_body_create'`. If any test fails for a different reason, stop and read it — the fixture may differ from what this plan assumed.

- [ ] **Step 3: Write the implementation**

Add to `src/freecad_buddy/usecases/features.py`, immediately after `feature_datum` ends (before `_parameter_writes`):

```python
def feature_body_create(
    registry: DocumentRegistry,
    doc: str | None = None,
    name: str | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Create an empty PartDesign Body, the container every feature tool builds into.

    The new Body carries no solid: its ``Tip`` is unset and its ``Shape`` is null until a
    feature is added, which FreeCAD reports as valid and up to date. It brings an ``App::Origin``
    and that origin's plane, line and point children, all of which the fingerprint and the render
    set already exclude as datum features.

    :raises ValidationError: the name is missing, already in use, or one FreeCAD would rewrite.
    """
    _require_partdesign()

    def precheck(document: object) -> None:
        _name_available(document, name)

    def op(document: object) -> list[str]:
        body = document.addObject(_BODY_TYPE, name)
        if body.Name != name:
            raise ValidationError(f"{name} is not a usable FreeCAD object name")
        body.Label = name
        return [body.Name]

    params = {"doc": doc, "name": name, "confirm": confirm}
    return _feature_mutation(
        registry,
        doc,
        name,
        f"create body {name}",
        "feature_body_create",
        params,
        op,
        audit_sink,
        precheck,
    )
```

This deliberately does not call `_add_feature`: that helper runs `body.addObject(feature)` to insert a feature *into* a Body, which has no meaning when the Body is what is being created.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)|FAIL:|ERROR:"
```

Expected: `Ran 573 tests`, `OK (skipped=1)` — the 568 baseline plus these 5.

- [ ] **Step 5: Verify the tests can fail (falsifiability)**

Temporarily change the `precheck` body to `pass`, re-run, and confirm **exactly two** tests fail: `test_a_name_already_in_use_is_rejected_before_the_bracket` and `test_a_name_freecad_would_rewrite_is_rejected_before_the_bracket`. Then restore `_name_available(document, name)`.

A test that still passes with its guard removed is not testing the guard.

- [ ] **Step 6: Commit**

```bash
git add src/freecad_buddy/usecases/features.py tests/infc/test_feature_tools.py
git commit -m "feat(usecases): create an empty PartDesign Body

The ten feature_* tools each require a body argument, and nothing in the tool
surface could produce one, so the whole feature surface was unreachable over MCP.
Measured: feature_pad returned INVALID_INPUT 'unknown object in body: Body' on a
fresh document, and none of the five golden models contains a Body.

An empty Body is valid and up to date with a null Shape, so the post_verify
validity sweep and the fingerprint's null-shape skip both handle it unchanged.
FreeCAD uniquifies a duplicate name to Bracket001 instead of raising, so the
precheck rejects a name already in use rather than returning an object under a
name the caller never asked for."
```

---

## Task 2: Register the tool on the wire surface

**Files:**
- Modify: `src/freecad_buddy/hosts/tool_catalog.py` (insert after the `feature_datum` entry, which ends at line 1694)
- Modify: `tests/external/test_feature_contract.py:27-38` (`FEATURE_TOOLS`), `:195`, `:203`
- Modify: `tests/external/test_mcp_surface.py:84-95` (`EXPECTED_FEATURE_TOOLS`)

**Interfaces:**
- Consumes: `features.feature_body_create` from Task 1; `_feature_method(name, fn, schema, description)`; `_feature_schema(properties, required)`; `_FEATURE_NAME_SCHEMA` — all already in `tool_catalog.py`.
- Produces: a tool named `feature_body_create` in `tool_specs()`, `mutating=True`, absent from `READ_ONLY_PROFILE`.

**Two existing tests assert exact equality over the feature-tool set and will FAIL until both sets are updated** — this is the intended safety net, not a surprise:
- `test_feature_contract.py:204` `assert registered == FEATURE_TOOLS`
- `test_mcp_surface.py:123` `assert names == (... | EXPECTED_FEATURE_TOOLS | ...)`

Both files also hardcode "ten" in test names, which must be renamed to stay truthful.

- [ ] **Step 1: Write the failing test**

Add to `tests/external/test_feature_contract.py`, after `test_no_feature_tool_entered_the_read_only_profile`:

```python
def test_feature_body_create_takes_only_a_name():
    """The Body creator needs no body argument — it is what produces one."""
    schema = _specs_by_name()["feature_body_create"].input_schema

    assert set(schema["properties"]) == {"doc", "name", "confirm"}
    assert schema["required"] == ["doc", "name"]
    assert "body" not in schema["properties"]
```

`_specs_by_name` and `READ_ONLY_PROFILE` are already defined/imported in this file; add no imports.

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/external/test_feature_contract.py -q
```

Expected: FAIL — `KeyError: 'feature_body_create'` on the new test. The two equality tests still pass at this point, because the tool is not registered yet.

- [ ] **Step 3: Write the implementation**

Insert into `src/freecad_buddy/hosts/tool_catalog.py`, immediately after the `feature_datum` `_feature_method(...)` block closes and before the `feature_set_parameters` block:

```python
        _feature_method(
            "feature_body_create",
            features.feature_body_create,
            _feature_schema(
                {"name": _FEATURE_NAME_SCHEMA},
                ["name"],
            ),
            "Create an empty PartDesign Body, the container every feature_* tool builds into. "
            "It holds no solid until a feature is added.",
        ),
```

- [ ] **Step 4: Update both exact-equality sets**

Registering an eleventh tool breaks the two equality assertions until their sets grow. Add `"feature_body_create"` to:

- `tests/external/test_feature_contract.py` `FEATURE_TOOLS` (line 27)
- `tests/external/test_mcp_surface.py` `EXPECTED_FEATURE_TOOLS` (line 84)

Then rename the two tests whose names now state the wrong count, so the names stay truthful:

```python
# tests/external/test_feature_contract.py:195
def test_every_feature_tool_is_registered_as_mutating():

# tests/external/test_feature_contract.py:203
def test_the_catalog_registers_exactly_the_expected_feature_tools():
```

Do not relax either assertion to `<=`. The exact equality is what catches an accidentally-registered or accidentally-dropped tool; widening it would remove the guard that just did its job.

Note `test_every_creating_feature_tool_requires_an_intent_bearing_name` (line 227) iterates `FEATURE_TOOLS - {"feature_set_parameters"}` and asserts `"name" in schema["required"]`. `feature_body_create` requires `name`, so it passes unchanged — no edit needed there.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
uv run pytest tests/external -q
```

Expected: `874 passed` — the 873 baseline plus the new contract test.

- [ ] **Step 6: Run the full gate set**

```bash
uv run python scripts/check_imports.py
uv run ruff check src/freecad_buddy tests/infc tests/external
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)"
```

Expected: `check_imports OK`; ruff reports only the pre-existing `E501` in `tests/external/test_check_imports.py:302` (do not fix it — it is not part of this change); `Ran 573 tests`, `OK (skipped=1)`.

- [ ] **Step 7: Commit**

```bash
git add src/freecad_buddy/hosts/tool_catalog.py \
        tests/external/test_feature_contract.py \
        tests/external/test_mcp_surface.py
git commit -m "feat(hosts): register feature_body_create on the tool surface

Registered through the same _feature_method/_feature_schema helpers as its
siblings, so it is gated by confirm, carries the 120 s mutation timeout and stays
out of the read-only assistant profile.

Two catalog tests assert exact equality over the feature-tool set, so both sets
grew by one rather than being relaxed to a subset check — that equality is what
catches an accidentally registered or dropped tool. The two test names that
hardcoded a count of ten were renamed instead of being left to lie."
```

---

## Task 3: Verify the gap is closed over live MCP

**Files:** none — this task changes no code. It is the check that the tool works through the real transport, not only through the use case.

**Interfaces:**
- Consumes: the registered `feature_body_create` from Task 2.

- [ ] **Step 1: Reload the addon**

The GUI host imports the package at startup, so a running FreeCAD holds the pre-change modules. Quit FreeCAD and start it again.

Confirm the reload took: compare the source mtime against the process start time. A source file newer than the process means the old code is still loaded.

```bash
powershell -NoProfile -Command "'freecad started: ' + (Get-Process -Name freecad).StartTime; 'features.py mtime: ' + (Get-Item 'D:\Work\Personal\Sources\freecad-buddy\src\freecad_buddy\usecases\features.py').LastWriteTime"
```

Expected: the process start time is **later** than the file mtime.

- [ ] **Step 2: Drive the tool over MCP**

Using the `mcp__freecad-buddy__*` tools:

1. `document_create(label="body_tool_check")`
2. `preview_dry_run(doc, operation={"tool": "feature_body_create", "args": {"name": "Bracket"}}, render="off")` → expect `status: OK`, `new: ["Bracket"]`, all volume/face deltas `0`.
3. `feature_body_create(doc, name="Bracket", confirm={"preview_id": <from step 2>, "elicitation_action": "accept"})` → expect `status: OK`.
4. `query_object(doc, object="Bracket")` → expect `type: PartDesign::Body`, `error: null`.
5. `document_close(doc)`.

Expected: every call returns `OK`. Step 3 failing with `unknown object in body` would mean the addon did not reload — return to Step 1.

- [ ] **Step 3: Record the result**

State plainly what was verified over MCP and what was not. In particular: this task proves a Body can be created and read back; it does not prove a full sketch-and-pad chain over MCP, because `preview_dry_run` requires a separate preview per mutation and the pad chain is already covered by Task 1's `test_a_pad_succeeds_against_a_body_this_tool_created`.

No commit — this task produces no artifact.

---

## Follow-up, deliberately not in this plan

The 35 G2 dev cases that need a Body stay undriveable after this work: their fixtures are `Part::Feature` golden models with no Body, and this tool creates an empty one rather than adopting an existing solid. Making that split runnable needs its own decision — rebuild the fixtures to contain a Body, or have each case call this tool first — and is tracked separately.

Record it in `_bmad-output/implementation-artifacts/deferred-work.md` as a new entry when this plan lands, so it is not lost.
