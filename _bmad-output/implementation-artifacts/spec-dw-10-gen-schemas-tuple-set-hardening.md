---
title: 'gen_schemas: emit proper array schemas for tuple/set type forms'
type: 'bugfix'
created: '2026-07-24'
status: 'done'
baseline_revision: '6af48dfc6aeeb7de88f293cbd76808483e01f304'
final_revision: 'ae59f2ad45bd034b06df4a63ebe052ae890e7981'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
---

<intent-contract>

## Intent

**Problem:** `scripts/gen_schemas.py` `_schema_for` falls through to a silent over-permissive empty schema (`{}`) for `tuple[...]` and `set[...]` type forms. `contracts/render.py` already uses `tuple[float, ...]` fields, so a `tuple` reaching a wire root would emit a schema that validates anything — a latent correctness defect that fails open, not closed.

**Approach:** Add explicit `tuple` and `set` handling to `_schema_for`. `tuple` maps to a JSON-Schema array (variadic → `items`; fixed-length → `prefixItems` + `minItems`/`maxItems`; empty tuple → `maxItems: 0`; bare `tuple` → untyped array). `set` maps to a `uniqueItems: true` array. Cover with generator unit tests.

## Boundaries & Constraints

**Always:**
- Stdlib only; no new imports beyond `typing` helpers already in the module.
- Emit Draft 2020-12 vocabulary (`prefixItems`, not the deprecated positional `items` list form).
- Preserve deterministic output (existing serialize/sort ordering unchanged).
- Existing wire-root schemas on disk must regenerate byte-identical (no contract uses tuple/set today, so no schema file should change).
- Recurse through nested element types via `_schema_for` (so `tuple[FooTypedDict, ...]` registers the `$def`).

**Block If:**
- Adding tuple/set support would change any existing `*.schema.json` on disk (would signal an unintended contract-shape change).

**Never:**
- Do not add tuple/set fields to any contract; this is generator hardening only.
- Do not remove or alter the terminal `return {}` fall-through for genuinely unknown forms beyond what is needed — but see Design Notes: the truly-unknown fall-through remains, only tuple/set are lifted out of it.
- Do not touch `render.py` or `WIRE_ROOTS`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Variadic tuple | `tuple[float, ...]` | `{"type":"array","items":{"type":"number"}}` | No error |
| Fixed tuple | `tuple[float, float, float]` | `{"type":"array","prefixItems":[{"type":"number"},{"type":"number"},{"type":"number"}],"minItems":3,"maxItems":3}` | No error |
| Bare tuple | `tuple` | `{"type":"array"}` | No error |
| Empty tuple | `tuple[()]` | `{"type":"array","maxItems":0}` | No error |
| Parameterized set | `set[str]` | `{"type":"array","uniqueItems":true,"items":{"type":"string"}}` | No error |
| Bare set | `set` | `{"type":"array","uniqueItems":true}` | No error |
| Nested TypedDict in tuple | `tuple[SomeTypedDict, ...]` | array whose `items` is `{"$ref":"#/$defs/SomeTypedDict"}` and the `$def` is registered | No error |

</intent-contract>

## Code Map

- `scripts/gen_schemas.py` -- `_schema_for` is the type→schema converter; the tuple/set branches go here, beside the existing `list` branch (~lines 118-136). Uses `get_origin`/`get_args` already imported.
- `tests/external/test_contracts.py` -- external pytest suite that already imports `gen_schemas`; add `_schema_for` unit tests here.
- `src/freecad_buddy/contracts/render.py` -- reference only: the `tuple[float, ...]` usage that makes the gap reachable. Not edited.

## Tasks & Acceptance

**Execution:**
- [x] `scripts/gen_schemas.py` -- in `_schema_for`, add a `tuple` branch (origin `tuple` and bare `tuple`) emitting the array forms from the I/O matrix, and a `set` branch (origin `set`/`frozenset` and bare `set`/`frozenset`) emitting a `uniqueItems: true` array. Recurse element types through `_schema_for(defs=...)`. Place before the terminal `return {}`.
- [x] `tests/external/test_contracts.py` -- add unit tests calling `gen_schemas._schema_for(tp, {})` for every I/O-matrix scenario, plus a nested-TypedDict-in-tuple case asserting the `$ref` and that the `$def` was registered into the passed `defs`.

**Acceptance Criteria:**
- Given a `tuple[float, ...]` annotation, when passed to `_schema_for`, then it returns `{"type":"array","items":{"type":"number"}}`.
- Given a fixed-length `tuple[float, float, float]`, when passed to `_schema_for`, then it returns an array with `prefixItems` of length 3 and `minItems == maxItems == 3`.
- Given a `set[str]`, when passed to `_schema_for`, then it returns `{"type":"array","uniqueItems":true,"items":{"type":"string"}}`.
- Given the existing contracts, when `gen_schemas.check()` runs, then it returns `[]` (no drift — no on-disk schema changed).

## Design Notes

Verified on CPython 3.14 (`get_args`/`get_origin`): bare `tuple` → `origin=None, args=()`; `tuple[()]` → `origin=tuple, args=()`; `tuple[float, ...]` → `origin=tuple, args=(float, Ellipsis)`; `tuple[a,b,c]` → `origin=tuple, args=(a,b,c)`. So the bare-vs-empty distinction is by **origin**, both having empty args.

Branch order inside `_schema_for`:
- `origin is tuple`: if `args == ()` → `{"type":"array","maxItems":0}` (empty tuple); elif last arg is `Ellipsis` → variadic `{"type":"array","items":_schema_for(args[0])}`; else fixed → `prefixItems` + `minItems`/`maxItems == len(args)`.
- `origin in (set, frozenset)`: `{"type":"array","uniqueItems":true, "items":_schema_for(args[0])}` (omit `items` if no args — parameterized set always has one arg, so `items` present in practice).
- `tp in (tuple,)` (bare) → `{"type":"array"}`; `tp in (set, frozenset)` (bare) → `{"type":"array","uniqueItems":true}`.

`set`/`frozenset` both map identically (JSON has no set; array + `uniqueItems` is the faithful projection). This is a principled emit, not a `raise`: the generator stays fail-closed only for genuinely unmodelled forms, and tuple/set are now modelled.

`typing.Tuple`/`typing.Set`/`typing.FrozenSet` aliases carry a concrete `origin` (e.g. `get_origin(typing.Set)` is `set`) with empty args, so bare-alias `tp in (...)` checks precede the origin branches (mirroring the existing `typing.Dict` precedent) — otherwise a bare alias would crash (`get_args(tp)[0]` IndexError) or emit `maxItems: 0`. Misplaced `Ellipsis` (e.g. `tuple[int, ..., str]`) raises rather than falling through to a permissive `{}` prefix item.

## Review Triage Log

### 2026-07-24 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 3: (high 0, medium 2, low 1)
- defer: 0
- reject: 3
- addressed_findings:
  - `[medium]` `[patch]` Bare `typing.Set`/`typing.FrozenSet` aliases crashed with IndexError (`get_origin` returns concrete `set`/`frozenset`, empty args → `get_args(tp)[0]`). Added bare-alias `tp in (set, frozenset, typing.Set, typing.FrozenSet)` check before the origin branch, mirroring the `typing.Dict` precedent.
  - `[medium]` `[patch]` Bare `typing.Tuple` emitted `{"maxItems": 0}` (collided with the `tuple[()]` empty case). Added `tp in (tuple, typing.Tuple)` bare check before the origin branch.
  - `[low]` `[patch]` Misplaced `Ellipsis` (`tuple[int, ..., str]`) fell to the fixed branch and re-introduced a silent permissive `{}` for the `Ellipsis` prefix item. Now raises `ValueError`. Added tests for frozenset (param/bare), `typing.*` aliases, single-element and heterogeneous fixed tuples, and the Ellipsis raise (6 new tests; would have caught the two crashes).

## Verification

**Commands:**
- `uv run pytest tests/external/test_contracts.py -q` -- expected: all tests pass, including new `_schema_for` cases.
- `uv run python scripts/gen_schemas.py --check` -- expected: `gen_schemas --check OK` (no drift).
- `uv run ruff check scripts/gen_schemas.py tests/external/test_contracts.py` -- expected: clean.

## Auto Run Result

**Change:** Hardened `gen_schemas.py` `_schema_for` so `tuple` and `set`/`frozenset` type forms emit proper JSON-Schema array fragments instead of silently falling through to an over-permissive `{}`. Tuple → array (variadic `items`; fixed `prefixItems`+`minItems`/`maxItems`; empty `tuple[()]` → `maxItems:0`; bare → untyped array). Set/frozenset → `uniqueItems:true` array. `typing.Tuple`/`typing.Set`/`typing.FrozenSet` aliases handled via bare-`tp in (...)` checks placed before the origin branches (the aliases carry a concrete origin), mirroring the existing `typing.Dict` precedent. Misplaced `Ellipsis` raises rather than re-introducing a silent `{}`.

**Files changed:**
- `scripts/gen_schemas.py` — tuple/set/frozenset branches added to `_schema_for` (incl. alias handling + Ellipsis-placement guard).
- `tests/external/test_contracts.py` — 13 `_schema_for` unit tests (I/O-matrix rows + frozenset, `typing.*` aliases, single-element/heterogeneous fixed tuples, misplaced-Ellipsis raise, nested-TypedDict `$def` registration); added `import typing`.

**Review findings:** patch 3 (medium ×2: alias IndexError crash, bare-`typing.Tuple` wrong `maxItems:0`; low ×1: misplaced-Ellipsis silent `{}` + test-coverage gaps) — all fixed. intent_gap 0, bad_spec 0, defer 0, reject 3 (pre-existing NoneType-element/element-`{}` fallthrough not caused by this change; lint-evidence already clean).

**Follow-up review recommended:** false — fixes localized to one function, mechanical alias-parity + fail-closed guard, fully test-covered.

**Verification:** `uv run pytest tests/external/test_contracts.py -q` → 53 passed. `uv run python scripts/gen_schemas.py --check` → `gen_schemas --check OK` (no on-disk schema drift). `uv run ruff check` → All checks passed. Alias/Ellipsis paths re-executed directly to confirm no crash and correct output.

**Residual risk:** None reachable today (no WIRE_ROOT contract field uses tuple/set); the block is forward-looking hardening. Element-type fallthrough to `{}` for genuinely unmodelled inner types remains pre-existing generator behavior, unchanged by this story.
