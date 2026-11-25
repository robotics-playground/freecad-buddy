# Story 13-9: quality bar

Base: 28586faa. Plan: builder-13-9 plan + `spec-13-9-varset-parameters.md` (main tree), approved 2026-11-24 with decision 32.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | `feature_parameters_define` creates a VarSet and adds or updates typed properties per T-3; output `varset`, `added`, `updated` on OK | T-3; CAP-2 | infc tests |
| Q2 | Runs inside the AD-5 bracket; on a failure the VarSet property state is restored, and the rollback is PROVEN by reading the properties back against a pre-op snapshot (the shape fingerprint cannot see VarSet-only changes) | AD-5 "rollback success is measured"; decision 32 | infc test that forces a failure after a write and asserts real state + the proof flag |
| Q3 | Refusals before the bracket, each with `detail.code`: unit-symbol name (list taken from `Expression.l`, test that every lexer symbol is in the list), reserved name, type conflict, not a VarSet, duplicate name; `varset_available()` false → `INVALID_INPUT` | T-3 "Refuse a parameter named after a unit symbol"; AD-17 | tests per code |
| Q4 | Value types: length/angle as `{value, unit}`; integer bound ±2147483647 (probed C long on Windows); no silent truncation | builder probe | tests |
| Q5 | `document_undo` reverts one `feature_parameters_define`; `preview_dry_run` reaches it (preview op table) | T-3; M-19 | infc test |
| Q6 | `query_parameters` reads VarSets, aliased spreadsheet cells and every `ExpressionEngine` binding; 500-row cap with `truncated`; unreadable cell → `null` + reason (never a made-up value); no recompute; fresh fingerprint unchanged; in `READ_ONLY_PROFILE` | T-3; 13-7 lessons | infc tests |
| Q7 | A VarSet value change that drives geometry through an expression shows the geometry change in `changed` (AD-6) | CAP-2 | infc test with a padded sketch bound to a VarSet |
| Q8 | `mcp-tools-design.md` rows/schemas/counts match code; skill line `parametric-patterns/SKILL.md:41` consistent; AD-1 rings; AD-28 additive | T-3; AD-1, AD-28 | read; gates |

Levels marked RUN: Unit, Integration (freecadcmd). UAT: container run by the verifier (build, edit, read back, undo through the bridge).
