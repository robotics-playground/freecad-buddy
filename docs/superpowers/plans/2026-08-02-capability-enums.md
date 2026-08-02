# Live property enumerations in the capability banner — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Report the live `getEnumerationsOfProperty` reading for every property the feature tools validate, so a client can discover the legal values for the build it is talking to.

**Architecture:** One cached probe in `shim.py` beside the existing capability probes, folded into `capability_banner`. `query_capabilities` needs no new logic. The contract grows one required field, which three separate places must be kept in step.

**Tech Stack:** Python 3.11, FreeCAD 1.1 App API, stdlib `unittest` under `FreeCADCmd`, pytest under `uv`.

## Global Constraints

- Ring rule: `contracts/` is stdlib-only; `usecases/` may import stdlib + FreeCAD App; `hosts/` may import Qt/`FreeCADGui`. Enforced by `uv run python scripts/check_imports.py`.
- Any FreeCAD enum, property name or API semantic must be confirmed against `docs/references/FreeCAD/` before use — never assumed.
- Comments and docstrings document what the code does and its params/returns/raises. No requirement ids, no spec-section citations, no design rationale inline.
- Two test worlds, never mixed: `tests/infc/` runs under `FreeCADCmd`, `tests/external/` under pytest.
- Commit messages use Conventional Commits, no AI attribution, no `Co-Authored-By`.
- Surgical changes: every changed line traces to this goal.

**Commands** (from the repo root, `D:\Work\Personal\Sources\freecad-buddy`):

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py

uv run pytest tests/external -q
uv run python scripts/gen_schemas.py
uv run python scripts/check_imports.py
uv run ruff check src/freecad_buddy tests/infc tests/external scripts
```

Baseline before this plan: **586 in-FreeCAD tests pass (1 skipped), 875 external pass.**

---

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `src/freecad_buddy/usecases/shim.py` | the probe, cached per process | Modify — one constant, one probe, one banner field |
| `src/freecad_buddy/contracts/capabilities.py` | banner payload type | Modify — one required field |
| `scripts/gen_schemas.py` | schema manifest | Modify — one entry in `REQUIRED_FIELDS` |
| `tests/external/test_contracts.py` | contract/manifest agreement | Modify — one entry in `EXPECTED_REQUIRED` |
| `tests/infc/test_document_lifecycle.py` | in-FreeCAD behaviour (`CapabilityProbeTest`) | Modify — add the probe tests |
| `src/freecad_buddy/contracts/jsonschema/*.json` | generated schemas | Regenerated, never hand-edited |

**Three places carry the banner's field set and must grow together**, or existing tests fail:

1. `CapabilityBanner.__annotations__` (the TypedDict)
2. `gen_schemas.REQUIRED_FIELDS["CapabilityBanner"]`
3. `test_contracts.EXPECTED_REQUIRED["CapabilityBanner"]`

`test_capability_banner_annotations_match_manifest` asserts 1 == 2 exactly. Do not weaken it — that equality is what its docstring calls "no silent rot".

---

## Task 1: The probe and the contract field

**Files:**
- Modify: `src/freecad_buddy/usecases/shim.py` (probe beside the other cached probes; `capability_banner` at line 392)
- Modify: `src/freecad_buddy/contracts/capabilities.py`
- Modify: `scripts/gen_schemas.py` (`REQUIRED_FIELDS["CapabilityBanner"]`, line 75)
- Modify: `tests/external/test_contracts.py` (`EXPECTED_REQUIRED["CapabilityBanner"]`, line 303)
- Test: `tests/infc/test_document_lifecycle.py` — the existing `CapabilityProbeTest` at line 124

**Interfaces:**
- Consumes: `enum_values(obj, prop) -> list[str]` (already in `shim.py`, line 202), `lru_cache`.
- Produces: `shim.property_enums() -> dict[str, dict[str, list[str]]]`, and `capability_banner`'s new `enums` key.

- [ ] **Step 1: Write the failing tests**

They go into the existing `class CapabilityProbeTest` in `tests/infc/test_document_lifecycle.py` (line 124), which already covers the capability probes. That file already has `from freecad_buddy.usecases import queries, shim` at line 16 — **add no imports**. Do not create a new test file.

```python
    def test_every_validated_property_reports_its_live_enumeration(self):
        enums = shim.property_enums()

        for type_id, prop in (
            ("PartDesign::Pad", "Type"),
            ("PartDesign::Pocket", "Type"),
            ("PartDesign::Revolution", "Type"),
            ("PartDesign::Hole", "ThreadType"),
            ("PartDesign::Hole", "HoleCutType"),
            ("PartDesign::Hole", "DepthType"),
            ("PartDesign::Chamfer", "ChamferType"),
            ("PartDesign::LinearPattern", "Mode"),
            ("PartDesign::LinearPattern", "TransformMode"),
            ("PartDesign::PolarPattern", "Mode"),
        ):
            with self.subTest(type_id=type_id, prop=prop):
                self.assertIn(type_id, enums)
                self.assertIn(prop, enums[type_id])
                self.assertTrue(enums[type_id][prop])

    def test_the_reported_values_match_the_live_reading(self):
        """Asserted against the live probe, never a hardcoded list.

        The values differ between supported builds — a linear pattern's Mode is
        ``{"length", "offset"}`` on 1.0.x and ``["Extent", "Spacing"]`` on 1.1.x — so hardcoding
        either spelling would fail the other leg and reintroduce the coupling this removes.
        """
        import FreeCAD

        document = FreeCAD.newDocument("enum_probe", hidden=True)
        try:
            probe = document.addObject("PartDesign::LinearPattern", "Probe")
            live = list(probe.getEnumerationsOfProperty("Mode"))
        finally:
            FreeCAD.closeDocument(document.Name)

        self.assertEqual(shim.property_enums()["PartDesign::LinearPattern"]["Mode"], live)

    def test_a_disabled_marker_value_is_reported_unfiltered(self):
        # Pad.Type carries '?TwoLengths' on this build. Measured: assigning it succeeds and it
        # reads back unchanged, so it is a legal value rather than a member to filter away.
        values = shim.property_enums()["PartDesign::Pad"]["Type"]

        self.assertTrue(
            any(value.startswith("?") for value in values),
            f"expected a '?'-prefixed member in {values}",
        )

    def test_the_banner_carries_the_enums_block(self):
        self.assertIn("enums", shim.capability_banner())
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)|FAIL:|ERROR:"
```

Expected: 4 errors — `AttributeError: module 'freecad_buddy.usecases.shim' has no attribute 'property_enums'` (and the banner test failing on the missing key).

- [ ] **Step 3: Write the probe**

In `src/freecad_buddy/usecases/shim.py`, add the table beside the other module constants:

```python
# The (type_id, property) pairs the feature tools validate against a live enumeration. The
# spellings differ between supported builds, so a caller cannot know the legal set without
# reading it from the running one.
_ENUM_PROPERTIES = (
    ("PartDesign::Pad", "Type"),
    ("PartDesign::Pocket", "Type"),
    ("PartDesign::Revolution", "Type"),
    ("PartDesign::Hole", "ThreadType"),
    ("PartDesign::Hole", "HoleCutType"),
    ("PartDesign::Hole", "DepthType"),
    ("PartDesign::Chamfer", "ChamferType"),
    ("PartDesign::LinearPattern", "Mode"),
    ("PartDesign::LinearPattern", "TransformMode"),
    ("PartDesign::PolarPattern", "Mode"),
)
```

Add the probe beside the other cached probes:

```python
@lru_cache(maxsize=1)
def property_enums() -> dict[str, dict[str, list[str]]]:
    """The live enumeration of every property the feature tools validate, by type and property.

    Values are reported verbatim in FreeCAD's own order. A ``?``-prefixed member is kept: it is
    assignable and reads back unchanged, so filtering it would hide a value a caller may use.

    A pair the build cannot probe is omitted rather than reported empty, so a consumer can tell
    an absent enumeration from one offering no values. A build that cannot run the probe at all
    reports an empty mapping.
    """
    try:
        import FreeCAD

        document = FreeCAD.newDocument("fcb_enum_probe", hidden=True)
        try:
            found: dict[str, dict[str, list[str]]] = {}
            for index, (type_id, prop) in enumerate(_ENUM_PROPERTIES):
                obj = document.addObject(type_id, f"Probe{index}")
                values = enum_values(obj, prop)
                if values:
                    found.setdefault(type_id, {})[prop] = values
        finally:
            FreeCAD.closeDocument(document.Name)
    except Exception:  # noqa: BLE001 - a probe that cannot run reports nothing
        return {}
    return found
```

Add it to the banner:

```python
        "partdesign_available": partdesign_available(),
        "enums": property_enums(),
```

- [ ] **Step 4: Grow the contract in all three places**

`src/freecad_buddy/contracts/capabilities.py` — add after `partdesign_available`:

```python
    enums: dict[str, dict[str, list[str]]]  # required; {type_id: {property: [value, ...]}}
```

`scripts/gen_schemas.py`, `REQUIRED_FIELDS["CapabilityBanner"]` — add `"enums"` to the list.

`tests/external/test_contracts.py`, `EXPECTED_REQUIRED["CapabilityBanner"]` — add `"enums"` to the set.

All three must change together. `test_capability_banner_annotations_match_manifest` asserts the TypedDict and the manifest agree exactly; do not weaken it.

- [ ] **Step 5: Regenerate the schemas**

```bash
uv run python scripts/gen_schemas.py
git diff --stat src/freecad_buddy/contracts/jsonschema/
```

Expected: the capability schema shows `enums`. Never hand-edit a generated schema — if the diff is not what you expect, fix the generator input, not the output.

- [ ] **Step 6: Run everything**

```bash
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)|FAIL:|ERROR:"
uv run pytest tests/external -q
uv run python scripts/check_imports.py
uv run ruff check src/freecad_buddy tests/infc tests/external scripts
```

Expected: `Ran 590 tests`, `OK (skipped=1)`; external passes with its count up by nothing (no external test was added — the three manifest edits are changes to existing tests); `check_imports OK`; ruff reports only the pre-existing `E501` in `tests/external/test_check_imports.py:302` (do not fix it).

- [ ] **Step 7: Verify the tests can fail (falsifiability)**

Temporarily make `property_enums` return `{}` unconditionally. Re-run the in-FreeCAD suite. Expected: **exactly three** failures — the three `property_enums` tests. `test_the_banner_carries_the_enums_block` still passes, because the key is present and empty.

Restore. If the count differs, stop and report.

- [ ] **Step 8: Commit**

```bash
git add src/freecad_buddy/usecases/shim.py \
        src/freecad_buddy/contracts/capabilities.py \
        src/freecad_buddy/contracts/jsonschema/ \
        scripts/gen_schemas.py \
        tests/external/test_contracts.py \
        tests/infc/
git commit -m "feat(capabilities): report the live property enumerations

A feature tool's enumerated properties are spelled differently across the two
blocking CI legs — a linear pattern's Mode is {\"length\", \"offset\"} on 1.0.0 and
['Extent', 'Spacing'] on 1.1.1 — so no literal value a caller sends is valid on
both. The tools already validate against the live reading, so both legs work; the
gap was that a client could not discover the legal set, because the wire schema
types these fields as a bare string.

query_capabilities now carries an enums block for the ten (type_id, property)
pairs the feature tools validate. Values are verbatim in FreeCAD's own order,
including the '?'-prefixed member Pad.Type reports: measured, assigning it
succeeds and it reads back unchanged, so it is legal on this build rather than a
disabled member to filter.

The values are deliberately NOT baked into the tools' JSON schemas. A schema enum
is static while these are build-dependent, so hardcoding one would state as fixed
the very thing that varies."
```

---

## Task 2: Verify over live MCP

**Files:** none — this task changes no code.

- [ ] **Step 1: Reload the addon**

Quit FreeCAD and start it again, then confirm the reload took by ordering:

```bash
powershell -NoProfile -Command "'freecad started: ' + (Get-Process -Name freecad).StartTime; 'shim.py mtime: ' + (Get-Item 'D:\Work\Personal\Sources\freecad-buddy\src\freecad_buddy\usecases\shim.py').LastWriteTime"
```

Expected: the process start time is **later** than the file mtime.

- [ ] **Step 2: Read the block over the wire**

Call `query_capabilities` and confirm the `enums` block is present, that
`PartDesign::LinearPattern.Mode` is listed, and that its values match what this build reports.

Then confirm the block is actionable: take the reported `Mode` value and drive
`feature_pattern` with it, and confirm a value NOT in the list is refused with `INVALID_INPUT`.
That contrast is what shows the block is authoritative rather than decorative.

- [ ] **Step 3: Record the result**

State what was verified and what was not. This proves the block reports the running build's
values. It does **not** prove the 1.0.x spelling, which cannot be checked from a 1.1.1 host —
that leg is covered by CI, not by this check.

No commit — this task produces no artifact.
