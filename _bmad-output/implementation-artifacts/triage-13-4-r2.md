# Story 13-4 triage: round 2 (verifier + red team)

Base: 1bc4795 on `story/13-4-skill-routing-gap-list`. Sources: `verify-13-4.md` (D1..D5), `redteam-13-4.md` (RT1..RT3 and lows), both in `D:\Work\Personal\Sources\freecad-buddy\_bmad-output\implementation-artifacts\`. Use their proposed wording unless a row says otherwise.

| Id | Source | Required fix |
| --- | --- | --- |
| D3 = RT1 (high) | verifier, red team | `code-cad-conversion/references/verification-kit.md:91-92`: an `App::Link` is measured by `query_mass_properties` and `verify_shape` (placement applied; measured volume 1000 in FreeCAD 1.1.4). Route the link's volume and validity to them; remove the `script_exec` route and the false reason. |
| D1 | verifier | `freecad-scripting-idioms/references/gap-list.md:28`: `feature_set_parameters` sets a VarSet property value (measured 5 → 4 mm). Move that operation to the covered rows; keep only what is still a gap (creating a VarSet, adding a property, binding an expression). |
| D2 = RT2 | verifier, red team | `gap-list.md:29`: `query_object` returns bound expressions (`ExpressionEngine`). Move reading expressions to the covered rows. |
| D4 = RT3 | verifier, red team | `gap-list.md:33`: `Lock` is not a Sketcher constraint type. A GUI lock is `DistanceX` + `DistanceY`, which `sketch_add_constraint` takes: covered row, not a gap. Fix the example. |
| D5 | verifier | `gap-list.md:60-61`: the `App::Part` container from a multi-body STEP import has a shape. Correct the sentence. |
| RT-L1 | red team (low) | Gap list vs `freecad-scripting-idioms/SKILL.md:88-93`: the action when `script_exec` is off must be the same in both places. Use the SKILL.md wording. |
| RT-L2 | red team (low) | `part-sourcing` must not link into another skill's `references/` (AD-15): name the skill (`freecad-scripting-idioms`, gap list) instead of the file path. |
| RT-L3 | red team (low) | `scripts/check_skill_shape.py` counts `##` lines inside code fences as sections. Small and low risk: fix it (skip fenced blocks) with a test in `tests/external`, as a separate commit (`fix(scripts): ...`). Re-run it over all skills: no skill may change from pass to fail. |

## Not fixed, with the reason

- RT-L4: `urdf-export` / `sdf-export` name tools that do not exist. Pre-existing, Phase 5 scope (SPEC non-goal). Leader records it in `deferred-work.md`.
- Red-team "Not reproduced" (expect_volume rounding): refuted by the red team itself.

## After the fixes

1. Re-run the D1..D5 FreeCAD checks you need through the same use-case path the verifier used, or cite the verifier's runs.
2. Commit on your branch (Conventional Commits, no trailer); the shape-checker fix as its own commit.
3. Run `bmad-build`'s three lenses again as fresh subagents (round 2) on 1bc4795..HEAD with `quality-bar-13-4.md`. Patch high/medium; commit.
4. `check_skill_shape.py` output, word counts, Q1 grep counts. Reply with head SHA, lens ids, counts in at most 10 lines.
