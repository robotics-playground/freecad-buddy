# Story 13-12: quality bar

Base: 04574455. Plan: builder-13-12 plan (approved 2026-11-25).

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | No `skills/**` text routes a covered operation (measure several objects, interference/clearance, section, VarSet create/write, expression bind, parameter read, delete) to `script_exec` | CAP-6; T-1 step two | grep table before/after with counts; reviewer read |
| Q2 | Every tool name, argument and payload a skill shows validates against the tool's real input schema in `tool_specs()`; refusal codes and limits named match the code | AD-4; decisions 21-38 | scratch validation script; reviewer check |
| Q3 | The gap list drops exactly the rows the new tools cover (Delete, VarSet/expression, measure across objects, section/slice incl. the `shape.slice` advice) and keeps every row still a gap (spreadsheet cell writes, enumeration properties, Part primitives/booleans, loft/sweep until 13-19, placement until 13-16) | T-1; usage-evidence.md | cross-check gap list vs tool_specs() |
| Q4 | `verification-thinking` and every edited SKILL.md keep 4 sections and ≤1,500 words; moved detail lands in `references/` with a pointer | AD-15; R-12 | check_skill_shape.py; word counts |
| Q5 | Guidance on tool results is correct: `boolean_failed` / null area = unmeasured (never zero), `undo_steps: 0` = no step recorded, `plane_on_face` = offset the plane | decisions 24-34 | reviewer read against code |
| Q6 | Verification-kit checks still measure what they measured before (no lost check); the parameter-limit test restores values | 13-4 Q8 | reviewer read; snippet run where a script remains |
| Q7 | The four deferred items naming Story 13-12 are resolved in `deferred-work.md` with a resolution line | Story scope | read |

Levels marked RUN: Unit-equivalent document checks (`check_skill_shape.py`, greps, schema validation script). Integration/E2E: BLOCKED (skill text). UAT: the CAP-6 live-session check runs after Story 13-19.
