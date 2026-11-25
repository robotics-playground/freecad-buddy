# Story 13-19: quality bar

Base: 6e15f063 (story/13-19-skill-routing-part-loft-placement). Plan: builder-13-19 plan message 2026-11-26; spec `spec-13-19-skill-routing-part-loft-placement.md` (wt-13-19).

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | Every operation a typed tool now covers (Part primitives and booleans, loft, sweep, placement and string writes, expression-driven write failure) routes to that tool in gap-list.md, tool-selection, design-decomposition, freecad-partdesign and code-cad-conversion; no skill still sends it to `script_exec` | SPEC CAP-1, CAP-9; plan 13-19 | grep of every skill for the covered operations; reviewer read |
| Q2 | Every tool name, parameter name, enum value, refusal code and limit in a skill example matches `tool_catalog.py` / the tool specs of 13-16, 13-17 (decision 51), 13-18 | lessons from 13-12 review rounds | scratch payload validator against `tool_specs()` after the 13-17 merge; reviewer read |
| Q3 | The generator route and the T-14 traced-outline route stay for shapes typed tools cannot make, with the boundary stated | plan 13-19 risk; tool-contracts.md:274 | doc read |
| Q4 | A typed refusal (`untrusted_shape`, `too_complex`, `empty_result`, `invalid_result`) is a stop with a repair, never bypassed through `script_exec` | lessons L1, L2; decision 45 | doc read |
| Q5 | gap-list rows: covered rows added, covered gaps removed, row 42 narrowed (link or file property), remaining gaps stated (Wedge, Prism, Ellipsoid, Helix, thickness, sweep modes, ...) | deferred entries from 13-16, 13-17 | doc read; deferred-work resolution lines |
| Q6 | `deferred-work.md` Part::Common entry (~:1655) and the 13-16 gap-list entry resolved with resolution lines | plan 13-19 | doc diff |
| Q7 | Skill shape: 4 sections, each SKILL.md at most 1,500 words; references hold the moved detail | AD-15 | `check_skill_shape.py` |
| Q8 | Gates pass with counts (check_skill_shape, ruff, tests/external) | epic-13-status.md Environment | verifier |
| Q9 | Live routing (CAP-6): in a Claude Code session with the MCP connected, a "make a box with a hole as a Part boolean" request uses the typed tools, not `script_exec` | SPEC CAP-6 | epic-close live check |

Levels marked RUN: Unit (skill tests, payload validator). Integration/E2E: BLOCKED for docs (no code path). UAT: live routing check at epic close.
