---
title: 'Typed verify_shape check schema'
type: 'feature'
created: '2026-11-24'
status: 'done'
route: 'dispatch'
baseline_commit: '28586faa3fb3c316b361e48df2a626ef0cf55a0e'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-13-decisions.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `verify_shape` declares `checks.items` as a bare `{"type": "object"}` (`hosts/tool_catalog.py:1431`). An agent that sends `{"type": "is_valid_solid"}` reaches the use case and fails late, and an omitted `object` silently measures `document.Objects[0]` (`usecases/verify.py:243`), which may be a sketch.

**Approach:** Generate `checks.items` as a `oneOf`, one branch per `fn`, from per-fn key data that moves into `contracts/assertions.py` (decision 11, M-6). An omitted `object` on a document with more than one shape-bearing object raises `INVALID_INPUT`. `object` stays optional (AD-28, decision 10).

## Boundaries & Constraints

**Always:** `contracts/` stays stdlib only (AD-1). The 11 primitive names and `ANCHOR_FRAME_KINDS` keep their values. The use case keeps its own validation (`validate_check`); the schema is a first filter, not a replacement. A new failure kind carries `detail.code` (AD-17).

**Never:** Do not make `object` required. Do not put `oneOf` at the schema top level (some MCP clients reject it). Do not change check semantics or measured values. Do not edit validator source beyond what the story needs (`validator_sha` hashes `verify.py` and `assertions.py`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Typed check | `{"fn":"expect_volume","expect":6000}` | measured as before | N/A |
| Wrong key | `{"type":"is_valid_solid"}` | rejected by schema before dispatch | MCP validation error |
| Foreign key | `{"fn":"is_valid_solid","expect":true,"tol":{}}` | rejected by schema (`additionalProperties: false`) | MCP validation error |
| Omitted object, one shape object | document with one shape-bearing object | that object is measured | N/A |
| Omitted object, several | document with N>1 shape-bearing objects | none measured | `INVALID_INPUT` "object is required: document has N shape objects" |
| Omitted object, none | document with no shape-bearing object | unchanged from today | unchanged `ValidationError` |
| Object given | any document | unchanged | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/contracts/assertions.py:12-26` -- `AssertionFn`, `ASSERTION_FNS`; add shape-check fns and per-fn key tables here.
- `src/freecad_buddy/contracts/__init__.py:8,121` -- re-exports; add new names.
- `src/freecad_buddy/usecases/assertions.py:65-79` -- `_COMMON_KEYS`, `_KEYS` move to contracts; `validate_check` (`:215`) reads them.
- `src/freecad_buddy/usecases/verify.py:184,239-269` -- `_ASSERTIONS` holds the 3 extra fns; object fallback `:239-245`; fn gate `:254`.
- `src/freecad_buddy/hosts/tool_catalog.py:1426-1452` -- `verify_shape` spec; build `checks` from contract data plus JSON fragments per key.
- `tests/external/test_mcp_surface.py:245-258` -- existing schema assertions for `verify_shape`.
- `tests/infc/test_verify_tools.py:496-660` -- `VerifyShapeTest`; add omitted-object cases.
- Design: `mcp-tools-design.md` section 3.3 (`omit = the document's first object`), `verification-design.md` section 5.
- Callers with `object` set (no change): `benchmarks/g3/fault-injection/score_g3_replay.py:257`, `tests/uat/g3-gui/g3_gui_replay.py:128`, `benchmarks/g0/fault-injection/score_verify_shape.py:217`, `features.py:318`, `transaction.py:270`.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/contracts/assertions.py` -- add `SHAPE_CHECK_FNS`, `VERIFY_SHAPE_FNS`, `CHECK_OPTIONAL_KEYS`, `CHECK_REQUIRED_KEYS` -- one source for the vocabulary and key tables
- [x] `src/freecad_buddy/contracts/__init__.py` -- export the new names
- [x] `src/freecad_buddy/usecases/assertions.py` -- replace `_COMMON_KEYS`/`_KEYS` with the contract tables -- no duplicate
- [x] `src/freecad_buddy/usecases/verify.py` -- use `SHAPE_CHECK_FNS` for the fn gate; refuse an omitted `object` on several shape objects with `detail.code`
- [x] `src/freecad_buddy/hosts/tool_catalog.py` -- generate `checks.items` `oneOf`
- [x] tests -- contract table, schema branches (accept/reject), use-case matrix rows
- [x] design docs -- `mcp-tools-design.md` 3.3 and `verification-design.md` 5 describe the rule

**Acceptance Criteria:**
- Given the tool input schema, when `{"type":"is_valid_solid"}` is validated, then it fails; when each valid check of the 14 fns is validated, then it passes.
- Given a document with 2+ shape-bearing objects, when `verify_shape` omits `object`, then the envelope is `INVALID_INPUT` naming the count.
- Given `contracts/`, when imports are checked, then no non-stdlib import appears.

## Implementation Notes

- Added `SHAPE_CHECK_FNS`, `VERIFY_SHAPE_FNS`, `CHECK_COMMON_KEYS`, `CHECK_OPTIONAL_KEYS`, `CHECK_REQUIRED_KEYS` to `contracts/assertions.py`; `usecases/assertions.py` reads them.
- `hole_spacing` has two schema branches (pitch form, pair form) because its valid `expect` depends on whether a pair is given.
- Shape-bearing excludes `App::Line`, `App::Plane`, `App::Point` (the origin elements): a Body document otherwise counts 10, with 7 unusable candidates.
- `usecases/verify.py` now validates the three shape-fact checks (foreign key, missing or mistyped `expect`); before, `bool(expect)`/`int(expect)` accepted anything.
- Validator hashes refreshed by the scorers: `score_verify_shape.py` and `score_g2_infc.py` under host freecadcmd (private cfg, `FREECAD_USER_HOME` temp), `score_g3_replay.py` under a Python 3.11 venv with `mcp` and FreeCAD's `bin` on `PYTHONPATH`. `validators.yaml` changes: `verify_shape`, `assertions`, `verify_sketch`, `spec_assertions` `validator_sha`; `run_id` and `date` of the G2 blocks and `verify_shape`. No rate changed.
- `tests/uat/testcases/TC-12-gui-workflows.md` first scenario now passes `object:"<Fillet>"` to `verify_shape`.

## Spec Change Log

## Review Triage Log

| Lens | Finding | Verdict | Route | Evidence |
|---|---|---|---|---|
| Blind | Body document has 10 shape objects, origin elements are candidates | high | patch | Reproduced by Blind (FreeCADCmd); fixed with `_ORIGIN_TYPE_IDS`; test asserts the exact 3-name message |
| Blind | UAT TC-12 calls `verify_shape` with no `object` on a PartDesign document | high | patch | `TC-12-gui-workflows.md:144,151` read; `object:"<Fillet>"` added |
| Blind | Schema accepts checks the use case refuses (7 cases) | high | patch | Reproduced; two `hole_spacing` branches, hole-only sides, zero-vector `not`; new value-level tests. `expect_solid_count: -1` is not a disagreement (use case accepts it, check fails) |
| Blind | `count_cylindrical_holes` `expect: 2.0` passes `integer` but the use case refuses a float | low | rejected | JSON has no int/float split; a client sending `2.0` is unlikely and the fix adds a branch to the use case |
| Blind | Shape-fact fns not validated in use case | medium | patch | `_validate_shape_check` added; infc subTests |
| Blind | `oneOf` error text unreadable | medium | patch | Confirmed locally ("is not valid under any of the given schemas"); `items.description` now lists each fn's keys; `oneOf` kept per spec T-7; verifier to judge (Q8) |
| Blind | Refusal envelope duplicates `queries._refusal_envelope`; candidates only in text | low / medium | patch for `detail.objects`; duplicate accepted | `detail.objects` added; the other helper is private to `queries.py` and builds no `objects` |
| Blind | Single-object test passes on old code | medium | patch | Group is now added first |
| Blind | No regression test over stored checks (Q5) | medium | patch | `test_Should_accept_every_stored_benchmark_check_...` (G0 and G3 cases) |
| Blind | Docstrings stale | low | patch | Module and `read_shape` docstrings updated, wrap fixed |
| Blind | Value rules exist twice (schema and use case) | low | defer | Recorded in `deferred-work.md`; tests cover agreement |
| Edge | `hole_spacing` agreement test fails | high | patch | Fixture fixed; passing |
| Edge | `hole_spacing` face side, pair-only, `select`+pair, array+pair | high | patch | Same as Blind finding 3 |
| Edge | `tol: null` rejected by schema | high | patch | `tol` type is `["object","null"]`; test added |
| Edge | zero vector accepted by schema | medium | patch | `_DIRECTION_SCHEMA` |
| Edge | Body plus Sketch with null Body shape measures the sketch | medium | rejected | The spec defines the rule as exactly one shape-bearing object; the sketch is then the only measurable object. Named in report |
| Edge | `_ASSERTIONS` vs `SHAPE_CHECK_FNS` can drift | low | rejected | Both are static; the fix is a guard with no observed trigger |
| Gap | Schema/use-case disagreement on `hole_spacing` | high | patch | As above |
| Gap | No test through the real MCP call path (Q8) | medium | defer | Verifier's live call covers it for this story; recorded in `deferred-work.md` |
| Gap | Shape-fn agreement not tested | medium | patch | Use-case validation and infc test |
| Gap | No corpus regression test | medium | patch | As above |

## Design Notes

Schema fragment for one branch (generated):
`{"type":"object","properties":{"fn":{"const":"expect_volume"},"expect":{"type":"number"},"tol":{...}},"required":["fn","expect"],"additionalProperties":false}`.
Shape-bearing = `Shape` attribute present and not null, the rule `transaction._shape_bearing` uses. A Body, its Sketch and its Pad each count, so a PartDesign document needs `object`.

## Verification

**Commands:**
- `uv run ruff check .` -- expected: clean
- `uv run ruff format --check <changed files>` -- expected: clean
- `uv run python scripts/check_imports.py` -- expected: OK
- `uv run python scripts/gen_schemas.py --check` -- expected: no drift
- `uv run pytest tests/external -q` -- expected: pass
- in-FreeCAD suite with host freecadcmd and private temp cfg -- expected: pass
