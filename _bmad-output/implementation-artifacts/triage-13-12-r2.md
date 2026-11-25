# Story 13-12 triage: round 2 (red team; verifier may add an addendum)

Base: 4333288b on `story/13-12-skill-routing-measure`. Source: `redteam-13-12.md` (this folder). Use its reproductions.

| Id | Source | Required fix |
| --- | --- | --- |
| RT-1 (high) | red team | Touching parts give `boolean_failed: true` from `query_interference`; `verification-kit.md:183-191` then sends the agent to a script that runs the same `common()` and reads the empty result as 0. The skill must say: `boolean_failed` means unmeasured, never zero; for parts that may touch, the fallback check is a fuse-volume test (fused volume equals the sum of volumes → no overlap; this is the cross-check proposed as option b, still waiting for the user), not `common()`. Fix every place that routes the fallback. |
| RT-2 (high) | red team | `gap-list.md:22` says Delete is covered, but deleting a mid-Body feature is refused (`delete.has_dependents`) and `with_dependents` deletes every later feature. Keep a gap row: "delete a mid-Body feature and keep the later features (relink BaseFeature)" → documented `script_exec` route with a transaction and `verify_*` after; the covered row covers whole objects, Tip features and independent objects only. Make the delete guidance in every skill say this. |
| RT-3 (medium) | red team | The Housing/Lid example always gives `boolean_failed` (the parts touch); the reference then tells the agent to look for a broken shape. Fix the example (touching contact) and the interpretation text. |
| RT-4 (medium) | red team | The generator-kit params stage still creates the VarSet, binds expressions and deletes objects through `script_exec` (Q1). Route those three steps to `feature_parameters_define`, `feature_set_expression`, `document_object_delete`; leave Part primitive/boolean generation for Story 13-19. |
| RT-5 (medium) | red team | `parametric-patterns:56` points into another skill's `references/` (AD-15). Name the skill instead. |
| RT-6 (medium) | red team | `urdf-export:43` still says `query_mass_properties` returns mass and inertia. Fix to what the tool returns. |
| RT-7..RT-10 (low) | red team | Fix each if it is a wording change in this Story's files (plane_on_face offset vs face tolerance; `com` null for compounds; snapshot-packet-sizing routes; stale kit text); otherwise list with the reason in the spec. |

## After the fixes

Commit on your branch yourself (no trailer). Skill text only: run one fresh Verification Gap Finder lens on 4333288b..HEAD (not all three). `check_skill_shape.py`, word counts, your schema validation script. Reply with SHA and counts in at most 6 lines.

## Addendum: verifier findings (verify-13-12.md)

D1 = RT-1 and D2 = RT-6 (same defects). Add:

| Id | Source | Required fix |
| --- | --- | --- |
| D3 (low) | verifier | `verification-kit.md:68` VarSet enum write still in script form: keep it as a script only if enumeration types are a listed gap (they are: `feature_parameters_define` has no enum type); say so in the line. |
| D4 (low) | verifier | `failure-table.md:13` reads ExpressionEngine with a script: route to `query_parameters` (bindings) or `query_object`. |
| D5 (low) | verifier | `verification-kit.md:150` stale "recompute included" note: correct it. |
