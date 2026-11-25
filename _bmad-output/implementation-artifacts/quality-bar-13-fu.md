# Story 13-fu: quality bar

Base: 3df33fbd (story/13-followups). Plan: builder-13-fu plan message 2026-11-25; spec `spec-13-fu-followups.md` (wt-13-fu).

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | Two trusted solids that touch (face, edge, vertex) with empty `common` at distance 0 read `common_volume` 0, `boolean_failed` false | decision 41 (b) | infc `QueryInterferenceTest` touch tests |
| Q2 | An overlap whose `common` is empty is never read as no overlap above the stated tolerance (1e-12 relative); fuse invalid, raising, non-finite, or gap above tolerance -> `boolean_failed` true, volume null | T-2 "empty result must never read as no overlap"; decision 24 | infc empty-common overlap, fuse invalid, fuse raises tests; mutant: loosen tolerance -> red |
| Q3 | Fuse runs only for trusted pairs inside the existing cost bounds (face product 150,000; 40 s between pairs); distance unknown -> no fuse | T-2 cost bounds; L2 | code read; infc test |
| Q4 | Query stays read-only: document fingerprint unchanged | AD-5; T-2 | infc fingerprint test |
| Q5 | T-2 paragraph, design §3.2.3/§2, catalog description and skill text state the touching rule and the tolerance limit; no drift between schema/catalog and design | decision 41; mcp-tools-design §3.2.3 | doc diff; drift/schema tests; `check_skill_shape` |
| Q6 | Sweep cost limit pinned at 3,000: limit 10,000 or 2,999 turns a test red | deferred entry spec-13-18 (1) | infc boundary tests + both mutants |
| Q7 | Closed-loft design sentence and timing comments match verify-13-18 round-2 measurements | deferred entry spec-13-18 (2), (3) | doc/comment diff |
| Q8 | All gates pass with counts | epic-13-status.md Environment | verifier |
| Q9 | Live container: face-touch pair reads overlap 0, not failed; 1e-3 mm3 overlap still flagged | decision 41 | container UAT TC-17 |

Levels marked RUN: Unit, Integration (freecadcmd), E2E (MCP over HTTP to container), UAT (container).
