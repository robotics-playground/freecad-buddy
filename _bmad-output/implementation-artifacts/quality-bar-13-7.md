# Story 13-7: quality bar

Base: bda755e. Plan: builder-13-7 plan + `spec-13-7-query-interference.md` (main tree, branch story/13-7-query-interference), approved 2026-11-24.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | Input schema exactly as T-2: `objects` 2..20 (every pair measured), `pairs` ≤100 of 2-name arrays, exactly one of them; `additionalProperties: false` | tool-contracts.md T-2 query_interference; decision 23 | schema test; gen_schemas |
| Q2 | Each pair record has `a`, `b`, `common_volume` (Quantity or null), `min_distance` (Quantity), `boolean_failed` | T-2 output schema | infc test |
| Q3 | Separated shapes: `min_distance` > 0, `common_volume` 0, `boolean_failed` false | T-2 | infc test with known gap |
| Q4 | Overlapping shapes: `common_volume` equals the analytic overlap volume within tolerance; `min_distance` 0 | T-2; CAP-1 | infc test with known overlap |
| Q5 | `common` raises or returns an empty shape while `min_distance` is 0 → `boolean_failed` true and `common_volume` null; never volume 0 | T-2; CAP-1 "a failed boolean never reads as zero overlap" | infc test with a planted failed boolean |
| Q6 | Touching solids: measured behaviour of `Shape.common` decides. A non-empty common result (face/edge) with zero volume → volume 0, `boolean_failed` false; a truly empty result at distance 0 → `boolean_failed` true (contract, safe side). The spec records the probe result | decision 24 | infc test + FreeCAD probe |
| Q7 | Object with no or empty shape, unknown name, self pair → `INVALID_INPUT` naming it | builder plan; decision 24 | infc tests |
| Q8 | Read-only: no transaction, no document change (fingerprint equal before and after); tool in `READ_ONLY_PROFILE` | T-2 "read-only"; M-21 | infc test; profile test |
| Q9 | 20 objects (190 pairs) of realistic parts finish within the 60 s query budget, measured | decision 23; plan risk | timing in infc or verifier container run |
| Q10 | Numbers only; no "done"/pass-fail verdict on the part | AD-35 | read |
| Q11 | `mcp-tools-design.md` §2 row, §3 schema and counts match code; AD-1 rings; AD-17 (no new status) | stories.yaml 7; AD-1; AD-17 | read; check_imports; check_status_vocab |
| Q12 | Values equal a script reading `common().Volume` and `distToShape()` on the same pairs (CAP-1 replay) | SPEC CAP-1 success | verifier container replay |

Levels marked RUN: Unit, Integration (freecadcmd). UAT: container replay by the verifier.
