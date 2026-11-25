# Story 13-11 triage: round 2 (verifier + red team)

Base: 4ee8c26b on `story/13-11-object-delete`. Sources (this folder): `verify-13-11.md` (F1, F2), `redteam-13-11.md` (RT-1 .. RT-3). Use their reproductions as failing tests first.

| Id | Source | Required fix |
| --- | --- | --- |
| RT-1 (high) | red team | The Group exemption (`features.py:2377`, `held <= Group`) skips `PartDesign::Boolean`, which keeps its tool Bodies in `Group` but depends on them. Deleting a tool Body returns OK, TNP CLEAN, and the Body keeps the deleted volume. Restrict the exemption to pure containers (PartDesign::Body, App::Part, App::DocumentObjectGroup — verify the list in FreeCAD source); every other holder is a dependent. Test with a PartDesign::Boolean; also with `with_dependents`. |
| RT-2 (medium) | red team | A container with an expression on its own member (`Body.Placement.Base.z = Pad2.Length`) is not counted as a dependent; the delete ends `RECOMPUTE_ERROR` and `with_dependents` cannot recover. Count expression references (ExpressionEngine targets) as dependency edges even from containers; with `with_dependents`, the expression owner is a dependent (or the binding is reported). Test. |
| F1 (medium) | verifier, container GUI | After a Tip delete the new Tip stays hidden (`features.py:2486/2489` bypass PartDesign `ViewProvider::onDelete`, `ViewProvider.cpp:345-350`), so the Body shows no solid in the GUI. Do what the GUI delete does: make the new Tip visible inside the transaction (headless-safe: `Visibility` is an App property). Test headless that the new Tip's `Visibility` is true; the verifier re-checks the GUI. |
| RT-3 (low) | red team | Deleting an `App::Link` array with ShowElement leaves its `App::LinkElement` children (FreeCAD detaches them). State it in the tool description and the result (`detached` list), or delete the elements with the array if FreeCAD's GUI does — check `ViewProviderLink` delete behaviour and match it. |
| F2 (low) | verifier | `tool_catalog.py:1039`: the `preview_dry_run` argument text still says "sketch_/feature_"; add `document_object_delete`. |

## After the fixes

1. Commit on your branch yourself (no trailer).
2. The dependents rule changed: run three fresh lenses (round 2) on 4ee8c26b..HEAD with `quality-bar-13-11.md`. Patch high/medium; commit.
3. External (Git Bash, `uv run --extra dev`) and infc (FREECAD_USER_HOME temp) counts; reply with SHA, lens ids, counts in at most 8 lines.
