---
title: 'feature_set_expression tool'
type: 'feature'
created: '2026-11-24'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '3c8efd8da1aefc95496f9d832f3e700dd9585ec6'
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/.knowledge-base/technical/standards/freecad/source-verify.md'
  - '{project-root}/docs/decisions/014-tnp-intended-target-is-what-the-op-wrote.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** An agent binds a VarSet parameter to a sketch constraint, a feature length or an attachment offset with `obj.setExpression(...)` in `script_exec` (CAP-2). FreeCAD accepts several wrong bindings without an error: a binding of `5 deg` to a length, `1mm/0`, a path such as `Length.x` that resolves to nothing, and an expression of about 1,000 chained terms that kills the FreeCAD process (SIGSEGV).

**Approach:** New mutation `feature_set_expression` binds or clears expressions on property paths, all entries in one AD-5 bracket. Refusals before the bracket carry `detail.code` (AD-17). The schema is new, so additive (AD-28).

## Boundaries & Constraints

**Always:** Input `doc`, `expressions` (1 to 100 items `{object, path, expression}`, no other keys), `confirm`. `object` is an object Name. `path` matches `^\.?[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*|\[[0-9]+\])*$`, a leading dot is the same path as none. `expression` is a string (bind) or `null` (clear). Output `bound`, `cleared`, `unchanged` (lists of `{object, path, value}` in request order, `value` the property's value read after the recompute as `{value, unit}` or a scalar, null with a `reason` when it cannot be read) and `undo_steps`, then the `mutation` block. Runs through `_feature_mutation` and `run_mutation`; `state_probe` reads `ExpressionEngine` of every object, so the rollback proof sees an expression-only change (L5). Refused as `INVALID_INPUT` before the bracket, each with a `detail.code`: `expression.invalid_path` (bad pattern, unknown property, a path that does not resolve to a value), `expression.unsupported_property` (the property does not hold a number, a quantity or a bool), `expression.invalid_text` (empty, a character FreeCAD cuts or rewrites, longer than `_MAX_EXPRESSION_LENGTH`), `expression.invalid_expression` (parse error or unresolved reference, with FreeCAD's message), `expression.not_finite` (evaluates to inf or nan), `expression.unit_mismatch` (a quantity of another dimension than the property), `expression.duplicate_path`. An unknown object is `INVALID_INPUT` without a code. A cycle that FreeCAD refuses at `setExpression`, or that fails the recompute, rolls back with the AD-5 proof. A call that changes nothing (clear of an unbound path, the stored text again) opens no transaction, has no `mutation` block and returns `undo_steps: 0`; otherwise `undo_steps` is the measured undo count the call added. `tnp_guard` treats a binding the op cleared as intended (decision 014): only when the record is an `ExpressionEngine[...]` record, the owner still exists, and the post-op reading lacks it. The catalog, `preview_op_table`, `mcp-tools-design.md` (row, counts, schema, refusals) agree. `tool-contracts.md` is leader-owned and is not edited; the leader aligns T-3 at merge from the deviation list in Implementation Notes.

**Never:** Pass or verdict (AD-35). A new status value. Change other tools. Create VarSet parameters (Story 13-9). Bind a string, a whole Placement or a Shape (a numeric leaf such as `.AttachmentOffset.Base.z` is bound). Exempt a record from the TNP audit because its owner was touched.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Bind | `Box.Length = Params.width * 2` | `bound` value 24 mm after recompute | N/A |
| Sketch constraint | `Sketch`, `.Constraints.width`, `Params.width` | constraint reads the parameter | N/A |
| Attachment offset | `.AttachmentOffset.Base.z` | placement z follows | N/A |
| Clear | expression `null` on a bound path | `cleared`, binding gone, value kept | N/A |
| Rebind | new text on a bound path | `bound`, text replaced | N/A |
| No change | clear unbound, or stored text | `unchanged`, `undo_steps` 0, no transaction | N/A |
| Cycle | A to B, then B to A | whole call rolled back | status not OK, rollback proof, bindings as before |
| Bad reference | `Nope.x` | none | `INVALID_INPUT` `expression.invalid_expression` |
| Unit mismatch | `5 deg` on a length | none | `expression.unit_mismatch` |
| Division by zero | `1mm / 0` | none | `expression.not_finite` |
| Dead path | `Length.x` | none | `expression.invalid_path` |
| Too long | 1,000 terms | none, no crash | `expression.invalid_text` |
| Undo | `document_undo` after bind and after clear | binding and value as before | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/features.py` -- add `feature_set_expression` after `feature_parameters_define` (`:2225`). Reuse `_feature_mutation` (`:343`, `report`, `state_probe`), `_resolve_object` (`:175`), `_unstorable` (`:1915`), `ParameterRefusal` pattern (`:1924`, a new `ExpressionRefusal(CodedValidationError)` beside it), `_unchanged_envelope` shape (`:2186`).
- `src/freecad_buddy/usecases/queries.py:1473` -- `_scalar_reading` reads a Quantity as `(value, unit, reason)`; the new code needs the same reading, so it is made public as `scalar_reading` (two call sites) rather than copied.
- `src/freecad_buddy/usecases/tnp_guard.py:726` -- `_grade_record`: a cleared binding grades `BROKEN` ("owner no longer present") because the record is absent from the live reading; add the narrow exemption. A new binding is not in the snapshot; a rebind grades `PASS`.
- `src/freecad_buddy/hosts/tool_catalog.py:831` -- `_feature_specs`, next to `feature_parameters_define`; `preview_op_table` finds the function in `features`.
- `mcp-tools-design.md` rows `:190-191`, counts `:213-224`, schemas near `:576`; 
- Tests: `tests/infc/test_feature_expressions.py` (new), `tests/infc/test_tnp_guard.py` (clear case), `tests/external/test_confirm_contract.py` (count 20 to 21), `test_feature_contract.py`, `test_mcp_surface.py`, a new `tests/external` contract file.
- Probed on FreeCAD 1.1.4: `setExpression` raises for a self reference and for a closing cycle, accepts `Nope.x`, `5 deg` on a length (reads 5 deg), `1mm/0` (reads inf) and `Length.x`; `Placement.Base.x` is stored as `.Placement.Base.x`; a same-text rebind and a clear of an unbound path record no undo step; `undo` restores bind and clear; a sum of 900 terms or 600 chained `*` terms ends the process (exit 139) inside parse; `evalExpression(".Constraints.width")` reads the path from the object's own context.
- Do not change: `run_mutation`, `confirm.py`, `feature_set_parameters`, fingerprint.

## Tasks & Acceptance

**Execution:**
- [x] `tests/infc/test_feature_expressions.py` -- one test per matrix row, rollback proved by `ExpressionEngine` read back, undo, dispatcher codes, preview table
- [x] `src/freecad_buddy/usecases/tnp_guard.py` -- cleared-binding exemption; test in `tests/infc/test_tnp_guard.py` first, red
- [x] `src/freecad_buddy/usecases/queries.py` -- `_scalar_reading` public
- [x] `src/freecad_buddy/usecases/features.py` -- `ExpressionRefusal`, spec and precheck helpers, `feature_set_expression`
- [x] `src/freecad_buddy/hosts/tool_catalog.py` -- spec entry; counts in `tests/external`
- [x] `mcp-tools-design.md` -- row, counts, schema, refusals; `benchmarks/_registry/validators.yaml` re-score only if a hashed source changed

**Acceptance Criteria:**
- Given `.Constraints.<name>` and `.AttachmentOffset.Base.z` bound to VarSet properties, when the document is recomputed, then both follow a VarSet edit made with `feature_parameters_define`.
- Given the catalog, when `gen_schemas --check`, `check_imports`, `ruff` and `pytest tests/external` run, then all pass.

## Implementation Notes

Decision 37 (leader): numeric only means the path must resolve to a number, a quantity or a bool; a sub-path to a numeric leaf of a Placement (`.AttachmentOffset.Base.z`, `.Placement.Base.x`) and `.Constraints.<name>` are bound. T-3 deviations for the leader: refusal codes `expression.*`; `bound`, `cleared`, `unchanged`, `undo_steps` outputs; expression length at most 400; numeric properties only; no-change call has no `mutation` block.

## Spec Change Log

Review round 1 (deviations from the frozen text, approved scope unchanged): (a) the op does not recompute, because the bracket reads `refs_written` right after the op and a recompute inside it makes every live reference equal its written reading, which hides a silent edge drop from the TNP audit; a value that turns infinite only through another item of the same batch is therefore not refused (deferred); (b) `undo_steps` is 1 when an item changed a binding and the document records undo, else 0, because the document's step count stops at 20; (c) an item whose text FreeCAD stores as the bound expression, or a clear by another spelling of the stored path, is found inside the bracket, so a call made only of those has a `mutation` block with `undo_steps` 0; (d) a clear checks only the object, so a dead or non-numeric binding can be removed; (e) new refusals `expression.not_integer`, a path ending in `.Value` (`invalid_path`), a `ReadOnly` property (`unsupported_property`), and a dimensioned quantity on a plain-number property (`unit_mismatch`); (f) two spellings of one stored binding abort the call inside the bracket. KEEP: the exemption keyed to the written reading and the owner's presence; the `state_probe` read-back; the 400 character cap.

Round 2 (verifier V1..V5, red team RT-1..RT-8, leader decision 38; deviations from the frozen text): (a) `run_mutation` closes the application-level transaction after every commit and abort (`shim.close_pending_transaction`), and gains an optional `recompute_check` hook and `removed_bindings`; the op may raise `transaction.RecomputeFailure(code, message)`, which maps to `RECOMPUTE_ERROR` with that `detail.code`; (b) a cycle is `RECOMPUTE_ERROR` / `expression.cycle`; (c) new codes `expression.range_unsupported` and `expression.value_out_of_range`; spreadsheet targets, shape roots and the `AttachmentOffset` of an unattached object are `expression.unsupported_property`; (d) a value that turns infinite or wrong through a sibling item or an existing binding rolls back after the recompute (closes the first deferred entry for this tool); (e) `undo_steps` is read from the undo list: each call names its transaction with a running number; (f) the TNP exemption for a removed binding is keyed to the bindings this op reported removing, so `sketch_remove_geometry` grades as before. KEEP: no recompute inside the op; the written-reading rule; the 400 character cap.

## Review Triage Log

Lenses: Blind Hunter aa27ed9c6e117ea3a (opus, high), Edge Case Hunter a1e6daed23b7deb99 (opus, high), Verification Gap a8f1916c11f603145 (sonnet, medium) on 3c8efd8d..working tree.

| # | Lens | Finding | Verdict | Route and evidence |
|---|------|---------|---------|--------------------|
| 1 | BH, EC | `op` recompute makes `refs_written` post-recompute, so the TNP entry-count check never runs for this tool | high | patch: recompute removed; EC probe `Fillet.Base` flagged pre-recompute, clean post |
| 2 | BH | A binding removed by the recompute grades PASS (same root as 1) | high | patch with 1; the test builds `written` before the clear, which is now the real order |
| 3 | BH, EC | Equivalent text (`a*2`) lands in `bound`, opens a transaction, `undo_steps` 0 | medium | patch: bindings compared before and after each write; test asserts `unchanged` and the earlier step surviving |
| 4 | BH, EC | `undo_steps` reads 0 when the 20-step undo stack is full | medium | patch: outcome and `UndoMode` decide; test with 24 earlier calls |
| 5 | BH, EC | `Constraints[2]` and `.Constraints.<name>` are one stored binding; clear by index does nothing, duplicates pass | medium | patch: conservative clear shortcut, stored-key duplicate check in the bracket, two tests |
| 6 | BH, EC | Integer rounding and unit loss on a float property accepted | medium | patch: `expression.not_integer`, `unit_mismatch` on a plain-number property, tests; bool conversion left as FreeCAD does it |
| 7 | BH | A dead or non-numeric binding cannot be cleared | medium | patch: clear checks the object only; test |
| 8 | BH | Rollback proof reads bindings, not values of shapeless objects | low | reject: values derive from bindings on the abort recompute; bindings read back equal |
| 9 | BH | `validators.yaml` hash changed without a run | false | `score_g2_infc.py` ran on 2026-11-24 (same run id and date, only the sha changed) |
| 10 | BH | No G2 fault case for the new rule | low | defer: entry written |
| 11 | BH, GAP | In-op value check has no code and no test | medium | moot: the check went with the recompute (1) |
| 12 | BH | Q7 `changed` has no test | low | patch: test reads `touched` and the digest change |
| 13 | BH | Self-reference rollback test omits the proof | low | patch: proof and leftovers asserted |
| 14 | BH | Limit measured on three operators | low | patch: `^` and nested `sin(` measured and named in the comment; test uses `+` x 1000 |
| 15 | BH, EC | Read-only property accepted | medium | patch: refused as `unsupported_property`; test |
| 16 | BH | Unrelated reformat in `test_feature_contract.py` | low | patch: reverted |
| 17 | BH | Rows echo the caller's path, not the stored one | low | reject: the row correlates with the request item |
| 18 | EC | A numeric dead path is stored and reported `bound` | false | probes on `Axis.x`, `Angle`, `.Constraints[0]` all read the bound value after recompute |
| 19 | EC | Later items can make existing or sibling bindings infinite | medium | defer: shared `post_verify` or fingerprint (entry written); reported `SPEC_FAILED`, not silent |
| 20 | EC | No-op fast path skips `confirm` and the audit | low | reject: 13-9 decided a no-change call needs no confirm |
| 21 | EC | Race between the fast-path lock and the bracket lock | low | reject: effect is an extra `mutation` block with `undo_steps` 0 |
| 22 | GAP | The TNP rule covers every tool, not only this one | medium | accept: it is decision 014's rule (the op's own write); design text now says so |
| 23 | GAP | Equivalent-text test compares `UndoCount` with itself | low | patch: rewritten (3) |

## Design Notes

`_MAX_EXPRESSION_LENGTH` = 400 characters. Measured on 1.1.4 (private temp cfg, `evalExpression` then `setExpression` then recompute): `1*` x 600 terms (1,200 chars) and `1&&` x 550 end the process; `1+` x 900 and `1mm+` x 800 pass 800 and fail at 900/1000; nested parentheses and unary minus are refused by the parser at any depth. 400 characters allow 200 two-character terms, 2.7 times below the lowest crash.

## Verification

**Commands:**
- `uv run --extra dev ruff check .` and `ruff format --check <changed files>` -- expected: clean
- `uv run python scripts/check_imports.py`, `gen_schemas.py --check`, `check_provenance.py` -- expected: pass
- `uv run --extra dev pytest tests/external -q` (Git Bash) -- expected: pass
- `freecadcmd -u <tmp>/user.cfg -s <tmp>/system.cfg tests/run_tests.py` with `FREECAD_USER_HOME` set to a temp folder -- expected: pass

Round 2. Verifier V1-V5, red team RT-1..RT-8 (triage-13-10-r2.md), then lenses Blind a196bc6602c80f3ce (opus, high), Edge Case adff17f15a8cf2ba4 (opus, high), Verification Gap aaf3ec8e6d09a8775 (sonnet, medium) on f2a19ce8..eca29153.

| # | Source | Finding | Verdict | Route and evidence |
|---|--------|---------|---------|--------------------|
| r2-1 | V1 | A no-write call leaves the application transaction open | high | patch: `shim.close_pending_transaction(name)` after commit and abort; tests for every exit path and the next undo |
| r2-2 | RT-8, RT-3 | Spreadsheet range held a call 1,087 s; cell binding ignored and lost on save | high | patch: sheet targets and range text refused; range bindings skipped in the sweep |
| r2-3 | V3 | Unattached `AttachmentOffset` reports bound, moves nothing | medium | patch: refused when the property is Hidden |
| r2-4 | RT-4, RT-2, RT-6, RT-7 | Range clamps bypassed, int32 overflow, sibling-driven values, `.Shape.Volume` | medium | patch: type rules, scratch probe (dynamic properties added), `recompute_check`, shape root refused |
| r2-5 | RT-1 | `undo_steps` 0 while a step was recorded | medium | patch: read from the undo list with a numbered transaction name |
| r2-6 | RT-5 | Exemption changed `sketch_remove_geometry` | low | patch: keyed to `removed_bindings`; test shows BROKEN as at base |
| r2-7 | V4 | Cycle was `SPEC_FAILED` | low | patch: `RecomputeFailure`, `RECOMPUTE_ERROR`, `expression.cycle` |
| r2-8 | V2 | Stale `validator_sha` | high (gate) | patch: both scorers re-run after the last source edit |
| r2-9 | BH, EC | `close_pending_transaction` aborts a foreign transaction under a GUI guard; close inside the commit try | medium | patch: closes only the bracket's own name, outside the try; two tests |
| r2-10 | BH | `RecomputeFailure` block claims unmeasured `is_valid false`; unproven path drops the code | low | patch: `NOT_MEASURED`, code passed on |
| r2-11 | BH, EC | The binding sweep evaluates existing range bindings twice per call | medium | patch: range bindings skipped; stub test |
| r2-12 | BH, EC | Baseline by key hides a worsened existing problem; code depends on object order | medium | patch: baseline compares the problem text; sorted keys |
| r2-13 | BH, EC | `_CELL_RANGE` misses `<<Sheet>>` and `Doc#Sheet` prefixes | medium | patch: prefixes added, tests; the ternary over cell-like names stays refused and is documented |
| r2-14 | EC | The probe skips dynamic VarSet properties (Percent, Area) | medium | patch: the property is added to the scratch object; Percent test |
| r2-15 | BH | Refusal tests do not prove "before the bracket" | low | patch: status and snapshot count asserted |
| r2-16 | BH, GAP | `ApplicationTransactionTest` defined after the main guard | low | patch: moved above it |
| r2-17 | BH | Catalog and docstrings omit new codes and the touched-document case | low | patch |
| r2-18 | BH | Test phase comments | low | patch for the new tests |
| r2-19 | BH, EC | The exemption now grades a constraint renumbering `BROKEN` | low | reject: same grade at base; `OtherToolTest` pins the other tools' grading |
| r2-20 | BH | Validator hash without a run | false | scorer ran after the last edit; same date and run id |
| r2-21 | BH | Cycle detection depends on message text | low | reject: the cycle tests assert `expression.cycle` and fail if FreeCAD rewords it |
| r2-22 | EC | A stale baseline on a touched document | low | reject: bindings and values of a touched document are the user's pending edit; GUI edits recompute |
| r2-23 | EC | `undo_steps` when the call joined an existing application transaction | low | reject: only under a GUI guard; the numbered name stays the evidence |
