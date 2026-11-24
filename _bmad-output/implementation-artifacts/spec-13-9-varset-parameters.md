---
title: 'VarSet parameters and query_parameters'
type: 'feature'
created: '2026-11-24'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '28586faa3fb3c316b361e48df2a626ef0cf55a0e'
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/.knowledge-base/technical/standards/freecad/source-verify.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** An agent that wants driving dimensions in a VarSet runs `addProperty` and `setExpression` in `script_exec` (CAP-2), and a parameter named after a unit symbol (`W`, `T`, `mm`) adds fine but every expression that reads it fails with `Failed to parse expression`. Nothing reads parameters and bindings back.

**Approach:** New mutation `feature_parameters_define` creates the `App::VarSet` when missing and adds or updates typed properties in one AD-5 bracket. New read-only `query_parameters` lists VarSet and Spreadsheet parameters and every expression binding. Schemas are new, so additive (AD-28).

## Boundaries & Constraints

**Always:** `feature_parameters_define` input `doc`, `varset` (object Name, pattern `^[A-Za-z_][A-Za-z0-9_]*$`), `parameters` (1 to 100 items `{name, type, value, group?, description?}`), `confirm`. `type` maps `length` to `App::PropertyLength` (value `{value, unit: "mm"}`), `angle` to `App::PropertyAngle` (`{value, unit: "deg"}`), `float` (finite number), `integer` (int within -2147483647..2147483647, not bool), `bool`, `string`. A missing name is added, with `group` default `Parameters`; an existing property of the same type is updated (`group` and `description` change only when given). Output `varset`, `added`, `updated` (names, request order) and the `mutation` block; the names are reported only when the status is `OK`. The VarSet is created when missing (Name and Label = `varset`). Runs through `_feature_mutation` and `run_mutation`; the mutation diff and `document_undo` work. Everything below is refused as `INVALID_INPUT` before the bracket (no snapshot, no transaction), each with its own `detail.code`: `parameters.unit_symbol_name` (name equals a lexer unit symbol or constant of `Expression.l`, list in code with the source named), `parameters.reserved_name` (a VarSet built-in property: `ExpressionEngine`, `Label`, `Label2`, `Visibility`, read from a probe, not typed), `parameters.type_conflict` (existing property of another type), `parameters.not_a_varset` (`varset` names a non-VarSet object), `parameters.duplicate_name`, plus bad name, value, unit or group. `varset_available()` false: `INVALID_INPUT` naming the build. `query_parameters` input `doc` only; output `varsets` (`{object, label, parameters: [{name, type, value, unit, group, description}]}`, every non-built-in property), `spreadsheets` (aliased cells: `{object, label, parameters: [{name, cell, contents, value, unit}]}`), `bindings` (`[{object, path, expression}]` from every `ExpressionEngine`), and `truncated` with the per-list totals when a list is cut at 500 rows. A value that cannot be read is null with its reason, never 0. It reads on the live objects without recompute, without a property write and with the document fingerprint unchanged. Added to `READ_ONLY_PROFILE`. The catalog, `preview_op_table`, `mcp-tools-design.md` (§2 rows, schemas, counts) and the `parametric-patterns` skill line 41 unit list agree with the code list.

**Never:** Pass or verdict (AD-35). Add a status value (new failures use `detail.code`, AD-17). Change `feature_set_parameters` or other tools. Import FreeCAD outside the AD-1 whitelist. Write a spreadsheet. Bind expressions (Story 13-10).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Create | doc without VarSet, 3 params | VarSet exists, `added` 3, `updated` [], values readable | N/A |
| Update | existing `width` length 12 -> 20 mm | `updated` [width], value 20 mm | N/A |
| Mixed | one new, one existing | both lists filled | N/A |
| Unit symbol | `W`, `T`, `mm`, `deg`, `e`, `in` | none | `INVALID_INPUT` `parameters.unit_symbol_name` |
| Built-in | `Label`, `Visibility` | none | `INVALID_INPUT` `parameters.reserved_name` |
| Type conflict | existing float `n`, request integer | unchanged | `INVALID_INPUT` `parameters.type_conflict` |
| Not a VarSet | `varset` names a Box | none | `INVALID_INPUT` `parameters.not_a_varset` |
| Bad value | integer 2^31, bool as integer, `nan`, `cm` as length | none | `INVALID_INPUT` naming the parameter |
| Rollback | op fails after one write | VarSet and property state as before | rollback, no leftover |
| Undo | `document_undo` after create | VarSet gone | N/A |
| No VarSet build | `varset_available()` false | none | `INVALID_INPUT` |
| Query | VarSet, Sheet alias, Box bound to `Sheet.width` | one row each, binding `{Box, Length, Sheet.width}` | N/A |
| Query unreadable cell | alias cell with a cell error | `value` null, reason given | N/A |
| Query read-only | any call | fingerprint and touched state unchanged | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/features.py:343` -- `_feature_mutation` (always sets `feature` and `feature_state`): add optional `report` hook that replaces both and runs only on `OK`. Reuse `_quantity_value`, `_length_mm`, `_angle_degrees` (`:89-116`), `_resolve_object` (`:175`), `_OBJECT_NAME` (`:35`), `_add_feature`-style Name check (`:247`), `_require_partdesign` pattern (`:83`). `feature_set_parameters` (`:1792`) is the model for `precheck`/`op`.
- `src/freecad_buddy/usecases/shim.py:133-149` -- VarSet probe; add a cached `varset_builtin_properties()` from the same scratch-document probe and warm it in `warm_capability_probes` (`:464`).
- `src/freecad_buddy/usecases/queries.py` -- `_ok_envelope` (`:31`), `_quantity` (`:120`), registry lock pattern of `query_object`; new `query_parameters` and helpers beside, apart from the `query_section` helpers.
- `src/freecad_buddy/hosts/tool_catalog.py:613` (`_feature_specs`, after `feature_set_parameters` `:794`), `_query_method` after `query_section` (`:1320`), `READ_ONLY_PROFILE` (`:1032`), `_feature_schema` (`:517`), `preview_op_table` (`:986`) finds the function in `features`.
- `mcp-tools-design.md` `:133` area, `:140` (planned to shipped), `:190`, `:211`, `:223` counts; new §3 schemas. `skills/parametric-patterns/SKILL.md:41`.
- FreeCAD source: `docs/references/FreeCAD/src/App/Expression.l` (UNIT and CONSTANT tokens, 116 ASCII symbols). Probed 1.1.4: `addProperty("W")` succeeds and `setExpression("VS.W")` raises `ParserError`; built-ins `['ExpressionEngine','Label','Label2','Visibility']`; `PropertyInteger` raises `OverflowError` above C long (32-bit on Windows); `undo` removes added properties and the VarSet.
- Tests: `tests/infc/test_feature_tools.py` (new class), `tests/infc/test_query_tools.py` (new class), `tests/external/test_mcp_surface.py:61,105`, `tests/external/test_feature_contract.py:38`, `tests/external/test_assistant_readonly_profile.py`, new `tests/external` lexer-list test (skips when `docs/references` is absent).
- Do not change: `feature_set_parameters`, `confirm.py`, fingerprint.

## Tasks & Acceptance

**Execution:**
- [x] `shim.py` -- `varset_builtin_properties()` probe, warmed
- [x] `features.py` -- unit-symbol set, `feature_parameters_define`, precheck, `report` hook on `_feature_mutation`
- [x] `queries.py` -- `query_parameters`, VarSet, Spreadsheet and binding readers, caps
- [x] `tool_catalog.py` -- two specs, profile entry
- [x] design doc, skill line 41 -- rows, schemas, counts, symbol list
- [x] tests -- one per matrix row, fingerprint unchanged, rollback by real state, undo, dispatch, preview table, lexer list

**Acceptance Criteria:**
- Given a name in `Expression.l`, when defined, then `INVALID_INPUT` with the code, and every lexer ASCII symbol is in the code list.
- Given a defined parameter, when a Box length is bound to it with `setExpression` and recomputed, then the Box takes the value.
- Given the catalog, when `gen_schemas --check`, `check_imports`, `ruff` and `pytest tests/external` run, then all pass.

## Implementation Notes

Decision 32 (leader): the rollback proof also reads the VarSet back. `run_mutation` and `_prove_rollback` take a `state_probe`; `features._varset_state` reads type, group, documentation, value and expression of every property. Planted tests: an abort that restores nothing ends in `rolled_back_via_snapshot`; a restore that restores nothing ends `SPEC_FAILED`. Removing the probe fails both (checked). `PARAMETER_PROPERTY_TYPES` lives in `usecases/parameter_types.py` because the writer and the reader share it. `benchmarks/_registry/validators.yaml` re-scored with `score_g2_infc.py` because `run_mutation`'s source hash changed. `touched` for the mutation is the VarSet only; bound objects are checked by the recompute sweep. `skills/parametric-patterns/SKILL.md:41` already listed symbols that are in the code list (test added); its Decision Rule that says no typed tool writes VarSet properties is stale and belongs to Story 13-12.

## Spec Change Log

Red-team round (decision 34), deviations from the frozen text: (a) `unchanged` and `undo_steps` in the output, and a call that changes nothing opens no transaction and has no `mutation` block (FreeCAD records no undo step for a same-value string write, so the next `document_undo` reverted the step before the call); (b) group and description are set when a parameter is created only, a change on an existing one is refused as `parameters.metadata_immutable` (FreeCAD does not undo them); (c) `parameters.invalid_string` for NUL and other characters FreeCAD cuts or rewrites; (d) the VarSet name is checked like a parameter name on creation; (e) `Shape` and `ElementMapVersion` are reserved names (read by `post_verify` and the fingerprint from every object); (f) `rpc_dispatch` reads `code` from `CodedValidationError` only, as a non-empty string; (g) the state probe compares only the types this tool writes (a Python-object property has an address in its repr); (h) the unproven-rollback message names the property state only for a tool that has a probe.

Review round 1 (deviations from the frozen text, approved scope unchanged): (a) a new refusal code `parameters.bound_by_expression` for an update of a property an expression binds, because the next recompute applies the expression over the written value (probed: 99 mm written, 20 mm read) and `updated` would then name a value that did not stick; (b) `length` must not be negative and `angle` must lie within +-360 deg, because both properties clamp silently (probed: -5 mm reads 0 mm, 720 deg reads 360 deg); (c) `parameters.reserved_name` also covers attributes of the VarSet object (a property named `TypeId` shadows it) and the `ObjectIdentifier` pseudo-property names (`_pla`, `_self`, ...); (d) a ReadOnly property update and a trailing newline in a name are refused before the bracket; (e) coded refusals are raised as `ParameterRefusal` and `rpc_dispatch` reads `code`, so a refusal is an exception like every other tool's and the preview path sees it; (f) the call is refused when the built-in probe read nothing.

## Review Triage Log

Lenses: Blind Hunter a9139ba6fdd856c99 (opus, high), Edge Case Hunter ab08a795c3fe82313 (opus, high), Verification Gap a82fabc13f0aed9ae (sonnet, medium) on 28586faa..working tree.

| # | Lens | Finding | Verdict | Route and evidence |
|---|------|---------|---------|--------------------|
| 1 | BH, EC | Out-of-range length or angle clamped silently, status OK | high | patch: probe `-5 mm` reads 0, `720 deg` reads 360; refused, boundary tests |
| 2 | BH | Names `_pla`, `_self`, ... resolve to pseudo-properties | medium | patch: `ObjectIdentifier.cpp:1231-1244` read; refused as `reserved_name`, test |
| 3 | EC | A property named `TypeId`, `Name` shadows an attribute | medium | patch: attribute names read from the probe; test |
| 4 | EC | Existing VarSet already holding a property named `TypeId` breaks the precheck and the query | low | defer: needs `script_exec` to create; same class as 3, pre-existing hazard |
| 5 | EC | `getValueAs("")` on a dimensionless quantity returns 1.1e308 | high | patch: probed; unit empty reads `Value`, `unit` null; test |
| 6 | BH, EC | Update of an expression-bound property reports `updated`, recompute restores the old value | medium | patch: probed; refused with `parameters.bound_by_expression`; logged as deviation |
| 7 | BH | Refusal envelope copied from `queries._refusal_envelope`; two error channels | low | patch: refusals now raise `ParameterRefusal`, `rpc_dispatch` reads `code`; no copy left |
| 8 | BH | Non-length unit follows the user unit schema, doc says "as stored" | low | patch: doc states the value is in the unit named beside it |
| 9 | BH, VG | 500-row cap tested for VarSet rows only; no constraint-binding test | medium | patch: spreadsheet, binding and sketch-path tests |
| 10 | BH | Design text line lacks the truncation sentence | low | patch: doc |
| 11 | BH, EC | Empty built-in set cached after one failed probe turns reserved-name off | medium | patch: refuse when the set is empty; test |
| 12 | BH | Unrelated reformat in `test_feature_contract.py` | low | patch: reverted |
| 13 | BH | Tests miss Arrange/Act/Assert comments and the parameter name in the message | low | patch: refusal tests rewritten through the dispatcher, message asserted |
| 14 | BH | No G2 fault case measures the new proof | medium | defer: new fault suite case, not asked here |
| 15 | BH | Query rows carry no staleness marker | low | defer: spec says no recompute; nothing asked |
| 16 | BH | General fingerprint gap lacks a deferred-work entry | medium | defer: entry written |
| 17 | EC | Snapshot-restore state compare could mismatch on a 17-digit float | false | probed: a float saved and reopened reads `0.30000000000000004` unchanged |
| 18 | EC | Label already taken: FreeCAD adds a suffix, doc says Label equals `varset` | low | patch: doc wording |
| 19 | EC | A refused op through `preview_dry_run` mints a preview token | medium | patch: refusals raise now (7); preview sees an error |
| 20 | EC | `float(10**400)` raises `OverflowError`, mapped to RECOMPUTE_ERROR | medium | patch: `OverflowError` refused as INVALID_INPUT; test |
| 21 | EC | Name `"W\n"` passes `match` and bypasses the unit refusal | medium | patch: `fullmatch`; test |
| 22 | EC | ReadOnly property update fails inside the bracket | low | patch: refused before the bracket; test |
| 23 | EC | Unknown keys in a parameter item are ignored on the preview path | low | reject: a guard for a path other tools share |
| 24 | VG | Lexer drift tests skip when `docs/references` is absent (not tracked) | high | patch: infc test sets every listed name as a property and requires the parser to refuse it |
| 25 | VG | Probe-raises paths of `state_restored` untested | low | defer: the differing-state paths are covered; a raise gives False |
| 26 | VG | `op` validates the parameters a second time | low | reject: the bracket must not trust a value read before it |
| 27 | VG | `validators.yaml` run_id bump unverifiable | low | false: `score_g2_infc.py` run on 2026-11-24, sha of `run_mutation` changed with `transaction.py` |

Red-team round (triage-13-9-r2.md, decision 34):

| # | Source | Finding | Verdict | Route and evidence |
|---|--------|---------|---------|--------------------|
| RT1 | red team | Same-value define records no undo step; undo reverts an earlier step | high | patch: no-op detected before the bracket, `unchanged`, `undo_steps` 0; unchanged values never written; tests with a user box |
| RT2 | red team | Group and description not undone | high | patch: set at create only; `parameters.metadata_immutable`; undo-after-create test |
| RT3 | red team | NUL cuts a string, status OK | high | patch: `parameters.invalid_string`; probed which characters survive a save and reopen; round-trip test |
| RT4 | red team | `exc.code` from any exception | medium | patch: `CodedValidationError` only, non-empty str; tests with `OSError(5)`, a `code` method, an int code |
| RT5 | red team | VarSet named `W` or `mm` | medium | patch: checked on creation; test |
| RT6 | red team | Parameter `Shape` ends SPEC_FAILED | medium | patch: `Shape`, `ElementMapVersion` reserved (read with getattr from every object in `transaction`, `fingerprint`, `tnp_guard`); test |
| RT7 | red team | Python-object property: correct restore reads as unproven | low | patch: only the types the tool writes are compared; test with a `PropertyPythonObject` |
| RT8 | red team | Unproven message names property state for every tool | low | patch: only when a probe is given; two tests |

## Design Notes

The shape fingerprint ignores VarSet and Spreadsheet state, so a parameters-only mutation leaves the digest unchanged and the AD-5 rollback proof compares equal trivially. The tests therefore assert the real property state after a rollback, and the gap is reported, not fixed here.

## Verification

**Commands:**
- `uv run ruff check .` -- expected: pass
- `uv run ruff format --check <changed files>` -- expected: pass
- `uv run python scripts/check_imports.py` -- expected: pass
- `uv run python scripts/gen_schemas.py --check` -- expected: pass
- `uv run pytest tests/external -q` (Git Bash) -- expected: pass
- `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` -- expected: pass
