# Mutation-block contract honesty Implementation Plan — DW-78 and DW-79

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `post_verify` reporting unmeasured values as measurements, and make the type checker agree with the schema about which fields are required.

**Architecture:** Two changes to the same four contract blocks, done as one pass because both touch `contracts/mutation.py` and its generated schema. A `"not_measured"` sentinel for the short-circuit paths, and required keys moved into `total=True` base classes with the schemas closed.

**Tech Stack:** Python 3.11, FreeCAD 1.1 App API, stdlib `unittest` under `FreeCADCmd`, pytest under `uv`.

## Global Constraints

- Ring rule: `contracts/` is stdlib-ONLY (no FreeCAD import); `usecases/` may import stdlib + FreeCAD App; `hosts/` may import Qt/`FreeCADGui`. Enforced by `uv run python scripts/check_imports.py`.
- Any FreeCAD enum, property name or API semantic must be confirmed against `docs/references/FreeCAD/` before use — never assumed.
- Comments and docstrings document what the code does and its params/returns/raises. No requirement ids, no spec-section citations, no design rationale inline.
- Two test worlds, never mixed: `tests/infc/` under `FreeCADCmd`, `tests/external/` under pytest.
- Commit messages use Conventional Commits, no AI attribution, no `Co-Authored-By`.
- Surgical changes: every changed line traces to this goal.
- **Never hand-edit a file under `src/freecad_buddy/contracts/jsonschema/`.** Regenerate with `uv run python scripts/gen_schemas.py`; if the output is not what you expect, fix the generator input.
- **Stage files by explicit path, never `git add -A`.** A blanket add in an earlier task swept unrelated in-progress work into a commit whose message described something else.

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

Baseline: **596 in-FreeCAD tests pass (1 skipped), 880 external pass.**

---

## The two defects, both measured

**DW-78.** `post_verify` short-circuits on the first failure and still fills every field, with values nothing measured:

| path (`transaction.py`) | reports | truth |
| --- | --- | --- |
| `verify_shape` raised or failed (lines 227, 231) | `fully_constrained=None` | the contract reads `None` as *no sketch involved*, but the sketch loop never ran |
| `verify_sketch` raised (line 239) | `is_valid=True` | no shape was graded |

**DW-79.** Run, not argued:

```
empty MutationBlock accepted by the type system : True
schema rejects it: 'transaction_id' is a required property
additionalProperties: absent
```

A producer omitting `rollback_proven` type-checks clean and fails at wire validation. A misspelled field validates while the real one silently defaults.

**A third disagreement, found while planning.** `PostVerifyBlock.fully_constrained` is listed in `REQUIRED_FIELDS` and emitted as `required` in the schema, but its TypedDict line carries no `# required` comment. The comment is the wrong one — the code emits the field on every path. Moving the required keys into a `total=True` base makes this class of drift impossible rather than merely fixing this instance.

---

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `src/freecad_buddy/contracts/mutation.py` | the four blocks | Modify — split each into a `total=True` base + `total=False` subclass; widen two field types |
| `scripts/gen_schemas.py` | schema generator | Modify — add a `CLOSED_TYPES` manifest and emit `additionalProperties: false` |
| `src/freecad_buddy/usecases/transaction.py` | `post_verify` | Modify — four short-circuit call sites |
| `tests/external/test_contracts.py` | contract/manifest agreement | Modify — extend the anti-drift guard, add schema tests |
| `tests/infc/test_mutation_protocol.py` | in-FreeCAD behaviour | Modify — add the not-measured tests |
| `src/freecad_buddy/contracts/jsonschema/mutation.schema.json` | generated | Regenerated, never hand-edited |
| `src/freecad_buddy/contracts/jsonschema/geometry-diff.schema.json` | generated | Regenerated — it `$ref`s `TnpAuditBlock`, so it closes too |

---

## Task 1: The `total=True` split and closed schemas (DW-79)

**Files:**
- Modify: `src/freecad_buddy/contracts/mutation.py` — `RefFinding` at line 28, `TnpAuditBlock` at 38, `PostVerifyBlock` at 44, `MutationBlock` at 53
- Modify: `scripts/gen_schemas.py` — `REQUIRED_FIELDS` at line 67, `_register_def` at 277
- Test: `tests/external/test_contracts.py`

**Interfaces:**
- Produces: the same four public names, each now with `__required_keys__` populated. Nothing that imports them changes — `MutationBlock` is still `MutationBlock`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/external/test_contracts.py`:

```python
MUTATION_BLOCKS = ("MutationBlock", "PostVerifyBlock", "TnpAuditBlock", "RefFinding")


@pytest.mark.parametrize("name", MUTATION_BLOCKS)
def test_mutation_block_required_keys_match_the_manifest(name):
    """The TypedDict states what is required; the manifest must agree, or they drift.

    A `# required` comment is prose the type checker cannot read, which is how a producer could
    omit a mandatory field, type-check clean, and fail only at wire validation.
    """
    from freecad_buddy.contracts import mutation

    block = getattr(mutation, name)

    assert set(block.__required_keys__) == set(gen_schemas.REQUIRED_FIELDS[name])


@pytest.mark.parametrize("name", MUTATION_BLOCKS)
def test_mutation_block_schemas_are_closed(name):
    """A misspelled field must be rejected, not silently defaulted."""
    schema = _load("mutation")
    body = schema if name == "MutationBlock" else schema["$defs"][name]

    assert body["additionalProperties"] is False


def _valid_mutation_block() -> dict:
    """A block that satisfies every required key, so a test can introduce exactly one defect."""
    return {
        "transaction_id": "0",
        "fingerprint_before": {
            "schema": "fcb.fingerprint/1",
            "serializer": "exportBinary",
            "objects": [],
            "digest": "d",
        },
        "fingerprint_after": None,
        "post_verify": {
            "recompute_clean": True,
            "is_valid": True,
            "fully_constrained": None,
            "tnp_audit": {"status": "CLEAN", "element_map_version": None, "findings": []},
            "passed": True,
        },
        "rolled_back": False,
        "rollback_proven": None,
    }


def test_a_valid_mutation_block_is_accepted():
    """Guards the fixture itself: if this fails, the misspelling test proves nothing."""
    jsonschema.Draft202012Validator(_load("mutation")).validate(_valid_mutation_block())


def test_a_misspelled_mutation_field_is_rejected():
    block = _valid_mutation_block()
    block["roled_back"] = True

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_load("mutation")).validate(block)
```

**The nested blocks must be fully populated, and this is the point of the test.** A first draft
used `fingerprint_before: {}` and `post_verify: {}`. Those fail their own nested `required` checks,
so the block was rejected whether or not `MutationBlock` was closed — the test passed for the wrong
reason and could not falsify the closure. Measured: with valid nested blocks the typo alone is
rejected when the root is closed and **accepted** when it is open, which is what makes the Step 7
check meaningful.

`test_a_valid_mutation_block_is_accepted` exists to catch that class of mistake directly: if the
fixture stops being valid, it fails loudly instead of quietly weakening its neighbour.

`pytest`, `gen_schemas` and `_load` are already available in this file. `jsonschema` is NOT imported by name — the file imports `Draft202012Validator` directly — so add `import jsonschema` for the test code above to run.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/external/test_contracts.py -q
```

Expected: the required-keys tests fail because `__required_keys__` is empty on a `total=False` TypedDict; the closure tests fail with `KeyError: 'additionalProperties'`; the misspelling test fails because nothing rejects it.

- [ ] **Step 3: Split the four blocks**

In `src/freecad_buddy/contracts/mutation.py`, rewrite each block as a required base plus an optional subclass. Drop the `# required` comments — the type now states it:

```python
class _RefFindingRequired(TypedDict):
    owner: str
    prop: str
    verdict: RefVerdict
    layer: int


class RefFinding(_RefFindingRequired, total=False):
    mapped_before: str | None
    state_after: str | None
    detail: str | None


class _TnpAuditRequired(TypedDict):
    status: TnpStatus
    element_map_version: str | None  # None ⇔ no element map
    findings: list[RefFinding]


class TnpAuditBlock(_TnpAuditRequired, total=False):
    pass


class _PostVerifyRequired(TypedDict):
    recompute_clean: bool
    is_valid: bool
    fully_constrained: bool | None  # None ⇔ no sketch involved
    tnp_audit: TnpAuditBlock
    passed: bool


class PostVerifyBlock(_PostVerifyRequired, total=False):
    explanation: str | None


class _MutationRequired(TypedDict):
    transaction_id: str
    fingerprint_before: FingerprintRecord
    fingerprint_after: FingerprintRecord | None
    post_verify: PostVerifyBlock
    rolled_back: bool
    rollback_proven: RollbackProof | None  # None ⇔ no rollback ran


class MutationBlock(_MutationRequired, total=False):
    schema: Literal["fcb.mutation/1"]
    snapshot_path: str | None
    verify_verdict: TerminalStatus | None
    params_digest: str | None
    touched: list[str]  # Names the op reported creating or modifying
```

`fully_constrained` is in the required base because the manifest and the schema already require it — its missing `# required` comment was the error, not its presence in the required set. Verify that against `REQUIRED_FIELDS["PostVerifyBlock"]` before writing it.

`TnpAuditBlock` has no optional fields; keep the `total=False` subclass with `pass` so all four blocks read the same way and a later optional field has an obvious home.

- [ ] **Step 4: Teach the generator to close a schema**

In `scripts/gen_schemas.py`, add the manifest beside `REQUIRED_FIELDS`:

```python
# Types emitted with ``additionalProperties: false``. A closed type rejects an unknown field
# rather than silently defaulting the real one, which is a breaking change for any producer
# sending an extra key — so closure is opt-in per type rather than a blanket default.
CLOSED_TYPES: frozenset[str] = frozenset(
    {"MutationBlock", "PostVerifyBlock", "TnpAuditBlock", "RefFinding"}
)
```

In `_register_def`, honour it:

```python
    body: dict = {"type": "object", "properties": properties}
    if required:
        body["required"] = required
    if name in CLOSED_TYPES:
        body["additionalProperties"] = False
    defs[name] = body
```

The wire root is built separately from `_register_def`. `build_schema` (line 412) assembles it and never calls `_register_def` for the root type, so the same rule must be applied there too — otherwise `MutationBlock` closes as a `$def` in other schemas but stays open as its own wire root, which is the one place it actually matters:

```python
    if tp.__name__ in CLOSED_TYPES:
        schema["additionalProperties"] = False
```

Place it after the `required` block and before the conditional merge, so the clash check still sees the final key set.

- [ ] **Step 5: Regenerate and inspect**

```bash
uv run python scripts/gen_schemas.py
git diff --stat src/freecad_buddy/contracts/jsonschema/
git diff src/freecad_buddy/contracts/jsonschema/mutation.schema.json | head -40
```

Expected: **two** schema files change.

`mutation.schema.json` gains `additionalProperties: false` on the root plus the `PostVerifyBlock`, `TnpAuditBlock` and `RefFinding` `$defs` — note `MutationBlock` is the root, not a `$def`.

`geometry-diff.schema.json` also gains it, in two places, and that is **correct rather than a leak**. `GeometryDiff.tnp_precheck` is typed `TnpAuditBlock` (`contracts/diff.py:86`), which embeds `RefFinding`, and `_register_def` registers `$defs` by type name — so closing a type closes it everywhere it is referenced. Both schemas describe the same block produced by the same code (`preview._tnp_precheck` returns a `TnpAuditBlock`), so a misspelled field should be rejected in both. Closing it in one and not the other would be the defect.

If a schema changes that carries NEITHER a type from `CLOSED_TYPES` nor a `$ref` to one, stop and report — that would be a real leak.

- [ ] **Step 6: Run everything**

```bash
uv run pytest tests/external -q
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)|FAIL:|ERROR:"
uv run python scripts/check_imports.py
uv run ruff check src/freecad_buddy tests/infc tests/external scripts
```

Expected: external up by the new tests; `Ran 596 tests`, `OK (skipped=1)`; `check_imports OK`; ruff reports only the pre-existing `E501` in `tests/external/test_check_imports.py:302`.

A producer inside this repo that omits a now-required key will surface here as a type error or a schema failure. If one appears, fix the producer — do not widen the contract back.

- [ ] **Step 7: Verify the tests can fail (falsifiability)**

Remove `"MutationBlock"` from `CLOSED_TYPES`, regenerate, re-run the external suite. Expected: **exactly two** failures — `test_mutation_block_schemas_are_closed[MutationBlock]` and `test_a_misspelled_mutation_field_is_rejected`.

`test_a_valid_mutation_block_is_accepted` must still PASS: opening the root cannot make a valid block invalid. If it fails, the fixture is wrong, not the closure.

Restore, regenerate, confirm green.

- [ ] **Step 8: Commit**

```bash
git add src/freecad_buddy/contracts/mutation.py \
        scripts/gen_schemas.py \
        src/freecad_buddy/contracts/jsonschema/mutation.schema.json \
        tests/external/test_contracts.py
git commit -m "fix(contracts): state the mutation blocks' required keys in the type

The four mutation blocks were total=False, so every field was optional to the
type checker while the schema marked six of MutationBlock's required. Measured:
an empty MutationBlock type-checks clean and the schema rejects it with
'transaction_id is a required property'. A producer omitting rollback_proven
therefore failed only at wire validation, which is how params_digest stayed
unpopulated while a test pinned it.

Required keys move into a total=True base per block, so the type states what a
'# required' comment only claimed, and a parametrized test pins the type against
the generator's manifest so the two cannot drift.

The schemas also close with additionalProperties: false, which the generator had
no support for. Closure is opt-in per type via a CLOSED_TYPES manifest rather
than a blanket default, because closing a type is a breaking change for any
producer sending an extra field and the other contract types have not been
audited for that.

PostVerifyBlock.fully_constrained was already required by the manifest and the
schema while carrying no '# required' comment — a third disagreement found while
planning, and the reason to make this class of drift impossible rather than
fixing the instances."
```

---

## Task 2: The not-measured sentinel (DW-78)

**Files:**
- Modify: `src/freecad_buddy/contracts/mutation.py` — the two field types
- Modify: `src/freecad_buddy/usecases/transaction.py` — `_block` at line 164, its short-circuit call sites at 227, 231, 239
- Test: `tests/infc/test_mutation_protocol.py`

**Interfaces:**
- Consumes: the split blocks from Task 1.
- Produces: `fully_constrained` and `is_valid` may now be the string `"not_measured"`.

**The boundary to hold.** `"not_measured"` belongs ONLY where the loop never ran. Three existing tests read `fully_constrained` — `test_mutation_protocol.py:330`, `test_sketch_tools.py:420` and `:1601` — and two use `assertFalse`, which passes for `None` but FAILS for a truthy string. All three drive the `verify_sketch` failure path at line 253, where the value is the measured conjunction and stays a real `False`. **If one of them starts failing, the sentinel leaked onto a path that did measure — a defect, not an expected update.**

- [ ] **Step 1: Write the failing tests**

Add to `tests/infc/test_mutation_protocol.py`:

```python
    def test_a_shape_failure_reports_the_sketch_grade_as_not_measured(self):
        """The sketch loop never ran, so its verdict is unmeasured rather than inapplicable.

        ``None`` means no sketch was involved. Reporting it here would claim a measurement of a
        sketch the op touched but never graded.
        """
        block = self._block_from_failed_shape_with_a_touched_sketch()

        self.assertEqual(block["post_verify"]["fully_constrained"], "not_measured")

    def test_a_sketch_grading_failure_reports_validity_as_not_measured(self):
        block = self._block_from_raised_verify_sketch()

        self.assertEqual(block["post_verify"]["is_valid"], "not_measured")

    def test_a_successful_mutation_reports_real_booleans(self):
        # Pins the boundary: the sentinel must not leak onto a path that did measure.
        block = self._block_from_successful_mutation()

        self.assertIsInstance(block["post_verify"]["is_valid"], bool)
        self.assertIsInstance(block["post_verify"]["fully_constrained"], (bool, type(None)))
```

The three helpers do not exist. Build them from the fixtures already in that file: this suite drives `post_verify` through `transaction.run_mutation` with planted failures, and `_run` plus the existing failing-op patterns are the model. Read the file's existing tests before writing them, and drive the real paths rather than constructing a block by hand — a hand-built block would test nothing.

If a path cannot be driven from this fixture, STOP and report rather than asserting on a fabricated block.

- [ ] **Step 2: Run to verify they fail**

Expected: three failures on the reported value, not errors. If any errors instead, the helper does not drive the path it claims.

- [ ] **Step 3: Widen the two field types**

In `contracts/mutation.py`:

```python
class _PostVerifyRequired(TypedDict):
    recompute_clean: bool
    is_valid: bool | NotMeasured
    fully_constrained: bool | None | NotMeasured
    tnp_audit: TnpAuditBlock
    passed: bool
```

with, beside the other aliases near the top:

```python
# A field whose step never ran. Distinct from None, which means the step ran and found the
# question inapplicable — no sketch was involved.
NotMeasured = Literal["not_measured"]
NOT_MEASURED: NotMeasured = "not_measured"
```

- [ ] **Step 4: Apply it at the three sites**

In `transaction.py`, import `NOT_MEASURED` from the contracts and change only the short-circuit calls:

| line | current | becomes |
| --- | --- | --- |
| 227 | `_block(True, False, None, ...)` | `_block(True, False, NOT_MEASURED, ...)` |
| 231 | `_block(True, False, None, ...)` | `_block(True, False, NOT_MEASURED, ...)` |
| 239 | `_block(True, True, None, ...)` | `_block(True, NOT_MEASURED, NOT_MEASURED, ...)` |

**Line 220 also changes, and I resolved this rather than leaving it open.** Reading the code: line 220 returns from the `if invalid:` branch, which sits *above* both the shape loop (line 222) and the sketch loop (line 233), so neither ran. Its `recompute_clean=False` and `is_valid=False` are genuinely measured — `_invalid_objects` graded them — but `fully_constrained` is not:

| line | current | becomes |
| --- | --- | --- |
| 220 | `_block(False, False, None, ...)` | `_block(False, False, NOT_MEASURED, ...)` |

So four call sites change, not three, and `is_valid` at line 220 stays a real `False`.

Line 253 keeps its real `fully_constrained` — that value is measured.

Update `_block`'s signature types to match.

- [ ] **Step 5: Regenerate the schema and run everything**

```bash
uv run python scripts/gen_schemas.py
uv run pytest tests/external -q
FCB="$USERPROFILE/micromamba/envs/fcb"
PYTHONUTF8=1 PYTHONPATH="$FCB/Library/bin" PATH="$FCB/Library/bin:$FCB/Library/lib:$PATH" \
  "$FCB/python.exe" tests/run_tests.py 2>&1 | grep -E "^(Ran|OK|FAILED)|FAIL:|ERROR:"
```

The three named existing tests must still pass. If any fails, see the boundary note above.

- [ ] **Step 6: Verify the tests can fail (falsifiability)**

Revert the three call sites to `None`/`True`. Expected: **exactly two** failures — the two not-measured tests. `test_a_successful_mutation_reports_real_booleans` still passes, because that path was never changed. Restore.

- [ ] **Step 7: Commit**

```bash
git add src/freecad_buddy/contracts/mutation.py \
        src/freecad_buddy/usecases/transaction.py \
        src/freecad_buddy/contracts/jsonschema/mutation.schema.json \
        tests/infc/test_mutation_protocol.py
git commit -m "fix(transaction): report an ungraded step as not_measured

post_verify short-circuits on the first failure and still filled every field.
On the verify_shape paths it reported fully_constrained None, which the contract
reads as 'no sketch involved' even when the op touched one and the sketch loop
never ran; on the verify_sketch raise path it reported is_valid True with no
shape graded. Both are unmeasured values presented as measurements, which the
module docstring says it never does.

Both fields gain an explicit not_measured value, distinct from None. No verdict
changes: every affected block already carried passed=false and a naming
explanation."
```

---

## Task 3: Verify over live MCP

**Files:** none.

- [ ] **Step 1: Reload the addon**

Quit FreeCAD and start it again. Confirm with a date-aware comparison:

```bash
powershell -NoProfile -Command "\$p=Get-Process -Name freecad; \$f=Get-Item 'D:\Work\Personal\Sources\freecad-buddy\src\freecad_buddy\usecases\transaction.py'; 'file newer than process: '+(\$f.LastWriteTime -gt \$p.StartTime)"
```

Expected: `False`.

- [ ] **Step 2: Drive a failing mutation and read the block**

Drive a mutation that fails `verify_shape` while touching a sketch, and confirm the returned
`mutation.post_verify.fully_constrained` is `"not_measured"` rather than `null`.

Then drive a successful mutation and confirm both fields are real booleans.

- [ ] **Step 3: Record the result**

State what was verified. Note that the wire value is now a string on some paths, which any
external consumer reading it as a boolean must be told about.

No commit.
