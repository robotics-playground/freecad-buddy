# Epic 13 decisions

| # | Question | Answer | Source | Date |
| --- | --- | --- | --- | --- |
| 1 | Integration branch | `feat/epic-13-mcp-usage-improvement` from `bd122f2`; Story branches `story/13-<n>-<slug>` merge into it | user: "Q1: yes" to planner Q-1 recommendation (b) | 2026-11-23 |
| 2 | Meaning of `spec_checkpoint` / `done_checkpoint` | `spec_checkpoint` (Stories 2, 13, 15, 17): user approves the Story spec before code. `done_checkpoint` (5, 12, 16, 20): user reviews the result and the container UAT batch since the last done checkpoint | user: "Q2: Yes" | 2026-11-23 |
| 3 | Success-signal targets (`SPEC.md:97`) | Accepted (≤15% `script_exec`, ≤5% read-only scripts, zero multi-object refusals, ≤5% `text`). Epic closes on CAP-1..CAP-9; action item about 2026-12-23: run `usage_report.py` on the following month | user: "Q3: yes" | 2026-11-23 |
| 4 | `script_exec` automatic recompute vs Touched fixtures | Recompute as T-6 says, plus optional additive input `recompute: false` for fixtures | user: "Q4: yes" (option c) | 2026-11-23 |
| 5 | Script that opens its own transaction | Document the limit in the tool description and `freecad-scripting-idioms`; reverse `skills/freecad-scripting-idioms/SKILL.md:57` in Story 13 | user: "Q5: Yes" | 2026-11-23 |
| 6 | STL per-object verify | STL verifies total volume only; STEP and 3MF verify per object (narrows CAP-3 for STL) | user: "Q6: Yes" | 2026-11-23 |
| 7 | Instruction files in the user's other projects (cause C-1) | User updates them after Stories 12 and 19, from the gap list | user: "Q7: ok" | 2026-11-23 |
| 8 | `query_mass_properties` `solids` field (M-5) | Add only `is_valid`; `counts.solids` already holds the solid count (`usecases/queries.py:167`); CAP-8 "every value appears once" (`SPEC.md:54`) | leader; contract:SPEC.md:54 | 2026-11-23 |
| 9 | `script_exec` `fingerprint_before` (M-11) | Add `fingerprint_before` (additive) so one-step undo is provable with `document_undo expect_fingerprint` | leader; contract:usecases/documents.py:597-616 | 2026-11-23 |
| 10 | Companion conflicts M-1, M-2 | Follow `tool-contracts.md`: no client-specific loading text; `verify_shape` `object` stays optional | leader; contract:SPEC.md:66-68 | 2026-11-23 |
| 11 | Other planner resolutions M-3..M-25 | Adopt each "Proposed resolution" in `epic-13-plan.md` Contract check, unless a Story plan finds new evidence | leader; contract:epic-13-plan.md#contract-check | 2026-11-23 |
| 12 | Story 13 re-slice (RS-1) | No re-slice; Story 13 stays one Story | leader | 2026-11-23 |
| 13 | Commit and merge autonomy | Granted: the leader commits each verified Story and merges its branch into `feat/epic-13-mcp-usage-improvement` without asking. Merge to `main`, push, history rewrite and scope change still need the user | user: "1. Yes" (2026-11-24) | 2026-11-24 |
| 14 | Story 13-2 spec, O-1, O-4 | Spec approved; remove `debug_` from the wire-prefix lists (spine:375, mcp-tools-design.md:18); SPEC.md:120 adds "for typed tools, observe-only bracket for script_exec" | user: "2. yes" (2026-11-24) | 2026-11-24 |
| 15 | Story 13-2 O-2 (transaction after TIMEOUT), O-3 (plan named wrong line) | O-2: AD-5 says only "TIMEOUT follows AD-27"; Story 13-13 decides commit or abort at its spec checkpoint. O-3: edit integration-mcp-freecad.md:102, leave :279 | leader | 2026-11-24 |
| 16 | `<N chars>` rule in design text (13-1 deferred R1-6) | Added to Story 13-2 scope: one sentence at mcp-tools-design.md:60 (detail; boundary: :60 "a compact key: value flattening") | leader; contract:mcp-tools-design.md:60 | 2026-11-24 |
| 17 | Verify round artifact while commits were not allowed | Frozen patch file per round; from Story 13-2 on, the leader commits each round on the Story branch | leader | 2026-11-24 |
| 18 | `script_exec` fingerprint shape (13-2 RT-8) | `fingerprint_before` / `fingerprint_after` are top-level bare digest strings, like the flat lifecycle tools, so the AD-32 framing cache key (`hosts/tool_catalog.py:1469-1484`) keeps working | leader; contract:hosts/tool_catalog.py:1469-1484 | 2026-11-24 |
| 19 | `script_exec` audit writer (13-2 RT-10) | The adapter writes the before/after pair as today; the after line takes both fingerprints from the result; the use case writes none | leader; contract:adapters/rpc_dispatch.py:68-80 | 2026-11-24 |
