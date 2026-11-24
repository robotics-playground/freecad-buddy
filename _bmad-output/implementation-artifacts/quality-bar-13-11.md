# Story 13-11: quality bar

Base: 3c8efd8d. Plan: builder-13-11 plan + `spec-13-11-object-delete.md` (wt-13-11), approved 2026-11-24 with decision 36.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | `document_object_delete` deletes the named objects inside the AD-5 bracket; returns `deleted`, `dependents`, `mutation` | T-4; CAP-3 | infc tests |
| Q2 | Dependents rule: an object with dependents outside the delete set is refused (`delete.has_dependents`, naming them) unless `with_dependents`; Origin objects refused (`delete.origin_object`) | T-4 | infc tests |
| Q3 | Body delete removes its group, Origin and Origin features; a feature of a surviving Body goes through `Body.removeObject` so Tip and BaseFeature stay valid | T-4 | infc tests (Tip delete, mid-feature delete, whole Body) |
| Q4 | TNP: a vanished owner is excused only when it is in the delete set the op wrote AND absent; any other vanished owner stays BROKEN (decision 014 style) | R-11; decision 014 | infc tests incl. a planted unrelated vanish |
| Q5 | Rollback is proven for shape-less deletes too (`state_probe` over names, labels, OutList, Tip, Group) | L5; AD-5 | forced-failure test |
| Q6 | One `document_undo` restores the deleted objects completely: names, Group, Tip, BaseFeature, Visibility, expressions AND their dependency links (an expression-driven property still follows its source after undo); the same holds after an AD-5 abort | CAP-3; L6/L7; decision 36 | infc tests with an expression owner (Pad.Length = VS.L), for undo and for abort |
| Q7 | Expression re-link (decision 36) adds no undo step and does not break redo; if it cannot, the result says so (`expressions_relinked: false`) and the tool description warns | decision 36 | infc tests on UndoCount/RedoCount |
| Q8 | `preview_dry_run` reaches the delete (preview op table) and leaves the document unchanged | T-4; M-19 | infc test |
| Q9 | Shared-code changes (`run_mutation` `deleted` set, `tnp_guard`, `document_undo` helper) change no other tool's envelope | L12 | envelope comparison against base |
| Q10 | `mcp-tools-design.md` row planned → shipped and §3 schema match code; AD-1, AD-17 (`detail.code`), AD-28 | T-4 | read; gates |

Levels marked RUN: Unit, Integration (freecadcmd). UAT: container run by the verifier (delete with and without dependents, undo, visual check).
