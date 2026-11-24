# Story 13-4: quality bar

Base: 905e038. Plan: builder-13-4 plan (approved 2026-11-24), `epic-13-plan.md` section 13-4.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | No `skills/**` text routes bounding box, volume, validity or solid count of a document object to `script_exec`; each routes to `query_mass_properties` or `verify_shape` | tool-contracts.md:280-281, CAP-6 SPEC.md | grep before/after with counts; reviewer read |
| Q2 | `freecad-scripting-idioms` holds the full current gap list (every `usage-evidence.md` script class with no typed tool today), one table row per operation, including the traced-outline route (helper module by `script_exec`, transaction, `verify_*` after, no typed equivalent claimed) and STEP import | tool-contracts.md:272, usage-evidence.md classes table | reviewer cross-check list vs classes table |
| Q3 | Rule present: name the missing typed tool before calling `script_exec` | tool-contracts.md:272 | read |
| Q4 | `part-sourcing` names no non-existent import path; import is stated as a gap | tool-contracts.md:278 | grep + read |
| Q5 | Every tool name a skill routes to exists in `tool_specs()` today, with the arguments the skill shows (e.g. `query_mass_properties` takes one `object`; `verify_shape` check names/keys match `usecases/assertions.py`) | AD-4; hosts/tool_catalog.py | reviewer check each named tool and argument against code |
| Q6 | Each `SKILL.md` keeps 4 sections and ≤1,500 words | AD-15 | `uv run python scripts/check_skill_shape.py`; word counts |
| Q7 | `skills/freecad-scripting-idioms/SKILL.md:57` (own-transaction rule) unchanged | decision 5 (Story 13-13 owns it) | diff |
| Q8 | Verification-kit snippets still measure what they measured (overlap vs reference STEP, reference volume, VarSet set/restore) with no lost check | code-cad-conversion verification kit | reviewer read of before/after |

Levels marked RUN: Unit (`check_skill_shape.py`, greps). Integration/E2E: BLOCKED (skill text, no code). UAT: CAP-6 live-session check is batched with Story 13-12 / 13-19 skill routing.
