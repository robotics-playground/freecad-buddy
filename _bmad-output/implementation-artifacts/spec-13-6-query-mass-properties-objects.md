---
title: 'query_mass_properties for several objects'
type: 'feature'
created: '2026-11-24'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '116377ed5d9b5ac0e6698013106e114a11832df3'
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/.knowledge-base/technical/standards/freecad/source-verify.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `query_mass_properties` takes one `object`. An agent that needs mass data for many parts makes one call per part, or falls back to `script_exec` (CAP-1). The record also has no validity flag.

**Approach:** Add input `objects` (1 to 50 names) beside `object`. Each record gains `is_valid`. Schema change is additive (AD-28).

## Boundaries & Constraints

**Always:** Exactly one of `object` and `objects` is given, otherwise `INVALID_INPUT`. Records come in input order, one per input name, duplicates kept. Look up each object by immutable `Name`. A record keeps today's fields and today's non-solid rule (DW-28): `volume` and `com` are `null` for a non-solid. `is_valid` is `bool(shape.isValid())`. The `object` path returns today's record plus `is_valid`, and still raises `INVALID_INPUT` for an object with no shape. `objects` output is `{"objects": [record, ...]}`. A record for an object with no shape (or a null shape) is `{"name": <Name>, "shape": null}`, and the call stays `OK`.

**Never:** Add a `solids` field (`counts.solids` holds it; decision 8). Remove or rename `object`. Change any other tool. A name that does not exist in the document is not a no-shape case: it fails the whole call with `INVALID_INPUT`, as `object` does today.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Single object | `object: "Box"` | today's record plus `is_valid: true` | N/A |
| Several objects | `objects: ["Box","Shell"]` | `{objects:[boxRecord, shellRecord]}`, input order, each with `is_valid` | N/A |
| Non-solid in list | `objects` includes a shell | its record has `volume: null`, `com: null`, `solid: false` | N/A |
| No shape in list | `objects` includes a Group | `{name:"Group", shape:null}`; other records unaffected; status `OK` | N/A |
| Both given | `object` and `objects` | none | `INVALID_INPUT` |
| Neither given | no `object`, no `objects` | none | `INVALID_INPUT` |
| Bad list | empty, over 50, non-string item, not a list | none | `INVALID_INPUT` |
| Unknown name in list | `objects` includes a missing name | none | `INVALID_INPUT` naming it |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/queries.py:570-621` -- `query_mass_properties`: extract the per-object record into one helper, add `objects`, `is_valid`, argument validation. `summarize_mass_properties` (`:89`) gives the text line.
- `src/freecad_buddy/hosts/tool_catalog.py:1252` -- spec: input schema gains `objects`; `required` becomes `["doc"]`; description names both forms. Dispatch passes args as keywords, so no adapter change.
- `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md:131` -- §2 row; new §3.2.2 schema after §3.2.1 (`:284`).
- `tests/infc/test_query_tools.py` -- in-FreeCAD tests (box, sketch fixture exists in `setUp`). Dispatch cases at `:189-200` stay valid.
- `tests/external/test_mcp_surface.py:60`, `tests/external/test_assistant_readonly_profile.py:46` -- list the tool name only; check they still pass.
- Do not change: `shape_metrics` (`:125`), other tools in `tool_catalog.py`, export specs (Story 13-5).

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/queries.py` -- add `objects` param, one-of validation, per-object record helper with `is_valid`, null-shape record, summary lines -- implements T-2
- [x] `src/freecad_buddy/hosts/tool_catalog.py` -- `query_mass_properties` input schema and description -- additive wire change
- [x] `mcp-tools-design.md` -- §2 row text and §3.2.2 schema -- design matches code
- [x] `tests/infc/test_query_tools.py` -- one test per matrix row, plus a dispatch test for both/neither -- covers edge cases

**Acceptance Criteria:**
- Given the box fixture, when `object: "Box"` is queried, then every previous field is unchanged and `is_valid` is `true`.
- Given 50 names, when queried through dispatch, then 50 records return in order.
- Given the catalog, when `gen_schemas --check`, `check_imports`, `ruff` and `pytest tests/external` run, then all pass.

## Implementation Notes

## Spec Change Log

## Review Triage Log

| # | Lens | Finding | Verdict | Route and evidence |
|---|------|---------|---------|--------------------|
| 1 | BH, EC, VG | No test for `is_valid` false or INVALID summary | medium | patch: new test with a self-intersecting face; asserts false and summary text |
| 2 | BH, EC, VG | No `object` vs `objects` parity or direct shape read | medium | patch: parity and `BoundBox`/`Volume`/`isValid` test |
| 3 | BH, EC, VG | 50 names not tested through dispatch | medium | patch: dispatch test with 50 mixed names; bad-input dispatch cases added |
| 4 | BH, EC | Empty name gives message about `object` | low | patch: message names `objects`; empty name rejected in `_mass_object_names` |
| 5 | BH | Design doc `$ref` unresolved, sub-keys undescribed | low | patch: `$defs/MassRecord`, key descriptions |
| 6 | BH | No `oneOf` in schema, not explained | low | patch: sentence in design doc §3.2.2 |
| 7 | BH | Skills say one object per call | medium | defer: skills Story |
| 8 | BH | `tool-contracts.md` T-2 stale | low | defer: leader-owned contract |
| 9 | BH, EC | `isValid()` cost and 30 s budget; duplicate names recomputed | maybe-false | defer: unverified medium, container timing; duplicate cache rejected (contrived, adds state) |
| 10 | EC | One shape raising fails the whole call | false | same as today's single call; the dispatch maps unexpected errors to an error envelope by design |
| 11 | BH | Only first unknown name reported | low | rejected: fix adds a loop and message format for a rare case |
| 12 | BH | Spec Verification lacks UAT step | low | rejected: fix edits this build's spec; verifier runs container UAT |

## Design Notes

Empty compound (red team RT-4): in `objects` it gives `{name, shape: null}`; the `object` path keeps today's response (AD-28, no change to an existing response).

Record helper sketch (no new ring crossing, `usecases` only):

```
{"name": "Group", "shape": null}                       # no shape
{"name": "Box", "solid": true, "volume": {...}, ..., "counts": {...}, "is_valid": true}
```

## Verification

**Commands:**
- `uv run ruff check .` -- expected: no errors
- `uv run ruff format --check <changed files>` -- expected: no changes
- `uv run python scripts/check_imports.py` -- expected: OK
- `uv run python scripts/gen_schemas.py --check` -- expected: no drift
- `uv run pytest tests/external -q` -- expected: pass
- `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` -- expected: pass
