# Story 13-17: quality bar

Base: wt-13-17 after merging feat @ b3b54e63 and story/13-16. Plan: builder-13-17 plan message 2026-11-25; spec `spec-13-17-part-primitive-boolean.md` (approved, decision 44).

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | `feature_part_primitive` makes each kind (box, cylinder, cone, sphere, torus, ...) at document level with the given dimensions and placement; volumes match analytic values | spec table; T-9; CAP-9 | infc tests |
| Q2 | Primitive refusals: missing/extra/non-mm/non-finite fields, values <= 0, cone with both radii 0, torus `radius2 >= radius1`, name taken -> `INVALID_INPUT` with a code, before any write | spec; decision 44 | infc tests |
| Q3 | `feature_part_boolean` cut/fuse/common with 1-20 tools builds the spec's objects (several-tool cut -> `<name>_tools` + Cut); `refine` honoured; inputs and the intermediate fuse hidden | spec table; decision 44 | infc tests |
| Q4 | Boolean refusals before any write: non-top-level input, duplicates, base in tools, untrusted input shape (reversed, self-intersecting, shell, face, empty) with the reason, cost limits (3,000 faces; 1,000 solid pairs; 20 tools) at their boundaries | spec; lessons L1, L2; decision 44 | infc tests incl. boundary values |
| Q5 | An empty, zero-volume or invalid boolean result -> `RECOMPUTE_ERROR` (`part_boolean.empty_result` / `part_boolean.invalid_result`) and full rollback (fingerprint and Visibility equal pre-op) | T-9; AD-5; leader answer (c) | infc tests + mutant |
| Q6 | Undo restores inputs' Visibility and removes the result and `<name>_tools` | AD-5; lessons L7 | infc test |
| Q7 | Confirm gate and `preview_dry_run` work for both tools | AD-17 | infc/external tests |
| Q8 | Shared `shape_trust.is_measurable_solid` used by `query_interference` and the boolean tool; query results unchanged | spec Open Question 5 | existing query tests; check_imports |
| Q9 | Placement via 13-16's `_placement_value` | decision 44 Q6; decision 50 | infc test |
| Q10 | `docs/intent.md:254`, `mcp-tools-design.md` §2/§3.7, tool descriptions and schemas match the code; `part_boolean.*` codes reach `detail.code` | decision 44; T-9 | external schema/dispatch tests; gen_schemas --check |
| Q11 | A near-limit case stays under 60 s | decision 45; L2 | infc timing test |
| Q12 | All gates pass with counts; G2 validator hashes re-scored if `queries.py` moves code | epic-13-status.md Environment; check_provenance | verifier |
| Q13 | Live container: primitives and each boolean op visible and correct in the GUI; empty result refused and rolled back | SPEC CAP-9 | container UAT |

Levels marked RUN: Unit, Integration (freecadcmd), E2E (MCP over HTTP to container), UAT (container).
