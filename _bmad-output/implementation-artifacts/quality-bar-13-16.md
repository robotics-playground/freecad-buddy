# Story 13-16: quality bar

Base: bde93e33 (story/13-16-set-parameters-placement-strings). Plan: builder-13-16 plan message 2026-11-25; spec `spec-13-16-set-parameters-placement-strings.md` (wt-13-16).

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | `feature_set_parameters` writes `App::PropertyPlacement` from `{base:{x,y,z}, rotation:{axis, angle}}`; omitted components keep the current value; result reads back the stored placement | tool-contracts.md `feature_set_parameters` clause (~:167-176); plan 13-16 | infc tests |
| Q2 | Malformed placement (unknown key, non-finite, zero axis, wrong unit) -> `INVALID_INPUT` before any transaction | T-3 conventions; L-lessons | infc tests |
| Q3 | String properties incl. `Label` written; FreeCAD's unique-label rename reported as `label: {requested, stored}`; strings FreeCAD cannot store -> `parameters.invalid_string` | plan 13-16; decision 34 | infc tests |
| Q4 | A placement FreeCAD marks read-only (attached Sketch, Pad in a Body) -> `INVALID_INPUT` before the bracket, value untouched, message points to `AttachmentOffset` (leader accepted deviation); a written value that recompute overwrites (expression, Python feature) -> `RECOMPUTE_ERROR` `parameters.value_overwritten` naming `<obj>.<prop>`, rolled back | plan risk "Placement of an attached object is overwritten"; AD-5 | infc tests (attached Sketch, Pad in Body) |
| Q5 | `AttachmentOffset` on an object with MapMode Deactivated refused (`parameters.not_attached`) | leader answer Q1 (a); decision 38 rule | infc test |
| Q6 | Rollback is proven by reading the written properties back against a pre-op snapshot (`state_probe`), not by the AD-6 fingerprint alone | decisions 32, 46; AD-5 "rollback success is measured" | infc rollback test + mutant |
| Q7 | All-placement/string no-op: no transaction, `unchanged`, `undo_steps: 0`; other OK results carry `undo_steps` from the undo list | lessons L6; decision 38 | infc tests |
| Q8 | `Visibility` carve-out unchanged; a `Label`-only call still requires the confirm gate | mcp-tools-design.md:104 | infc/external test |
| Q9 | Placement parser reusable by 13-17 with `current=None` defaults (base 0, no rotation) and the 13-17 spec input shape | decision 44; 13-17 spec Open Question 6 | unit test of the parser |
| Q10 | Design rows, tool description and `SKILL.md:74-78` match the code | plan 13-16 files | doc diff; `check_skill_shape`; schema tests |
| Q11 | All gates pass with counts | epic-13-status.md Environment | verifier |
| Q12 | Live container: move a Body by placement, rename a feature by Label, write to an attached sketch's Placement -> refused and rolled back; GUI shows the new placement | SPEC CAP | container UAT |

Levels marked RUN: Unit, Integration (freecadcmd), E2E (MCP over HTTP to container), UAT (container).
