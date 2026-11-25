# Story 13-10: quality bar

Base: 3c8efd8d. Plan: builder-13-10 plan + `spec-13-10-set-expression.md` (main tree), approved 2026-11-24 with decision 37.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | `feature_set_expression` binds or clears expressions on property paths, batched in one AD-5 transaction; output `bound`, `cleared`, `unchanged`, `undo_steps` | T-3; CAP-2 | infc tests |
| Q2 | CAP-2 paths work: `.Constraints.<name>` of a sketch, a pad length, and the numeric leaf `.AttachmentOffset.Base.z` (sub-paths to numeric leaves of a Placement are allowed; binding a whole Placement is refused) | stories.yaml 10; decision 37 | infc tests; verifier container CAP-2 build with typed tools only |
| Q3 | A cycle (self reference or closing cycle) refused by `setExpression` and a bad reference that fails at recompute both roll back with proof (ExpressionEngine read back, L5) | plan 13-10 risk; AD-5 | infc tests, one per path |
| Q4 | TNP: clearing an expression does not grade BROKEN; the exemption is keyed to the written ExpressionEngine record (owner still exists, record removed by this op); an unrelated vanished owner still grades BROKEN | decision 014; plan risk | infc tests (test first, red) |
| Q5 | Refusals before the bracket with `detail.code`: invalid_path, unsupported_property, invalid_text, invalid_expression, not_finite, unit_mismatch, duplicate_path; expression length cap 400 chars with the crash measurement beside the constant | decision 37; L8, L2 | tests per code; the 900-term crash input is refused before FreeCAD sees it |
| Q6 | No-op (same text rebind, clear of an unbound path) opens no transaction and returns `undo_steps: 0` | L6 | infc test with an earlier user step that must survive |
| Q7 | One `document_undo` reverts one call; the bound value change shows in `changed` when geometry moves | CAP-2; AD-6 | infc test |
| Q8 | `queries._scalar_reading` made public without changing `query_*` outputs | L12 | existing query tests green |
| Q9 | `mcp-tools-design.md` row/schema/counts match code; AD-1, AD-17, AD-28 | T-3 | read; gates |

Levels marked RUN: Unit, Integration (freecadcmd). UAT: container CAP-2 build by the verifier.
