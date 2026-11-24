# Story 13-11: red team report

Diff: `3c8efd8d...4ee8c26b` (branch `story/13-11-object-delete`). Own worktree at `4ee8c26b`, removed after the run.
Probes: host `freecadcmd.exe` 1.1.4 with private `-u`/`-s` cfg and `FREECAD_USER_HOME` in scratchpad `redteam-13-11\`. The probes import the worktree `src` (printed `PKG D:\Work/Personal/Sources/fcb-redteam-13-11/src\freecad_buddy\__init__.py`) and reuse the `_DeleteFixture` from `tests/infc/test_object_delete.py`: a Body of Sketch1, Pad1 (`Length = VS.L`), Sketch2, Pad2, and a VarSet `VS`.

Probe scripts: `C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\50958ed8-8fcb-4d26-a32d-c7025b2780ae\scratchpad\redteam-13-11\probes.py`, `probes2.py`, `probes3.py`, `probes4.py` (same folder). Command for each:

```
FREECAD_USER_HOME=<S>/home "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" -u <S>/user.cfg -s <S>/system.cfg <S>/probesN.py [p_case]
```

## Reproduced

| Id | Severity | Q | File:line | Finding |
| --- | --- | --- | --- | --- |
| RT-1 | high | Q2 | `src/freecad_buddy/usecases/features.py:2377` | A `PartDesign::Boolean` holds its tool Bodies in `Group`. The Group rule says it is not a dependent. Deleting the tool Body returns `OK`, TNP `CLEAN`, and the Boolean keeps the old fused shape: the deleted Body's volume stays in the surviving Body, also after a full recompute. `with_dependents` true does the same. |
| RT-2 | medium | Q2 | `src/freecad_buddy/usecases/features.py:2377` | A container with an expression on one of its own Group members is not counted as a dependent (`held <= Group`). The delete then fails in the bracket as `RECOMPUTE_ERROR` / `mutation.recompute_error`, not as `delete.has_dependents` naming the container. `with_dependents` true fails the same way, so the documented recovery does not work. The rollback is proven, so the document is safe. |
| RT-3 | low | Q1 | `src/freecad_buddy/usecases/features.py:2348` | Deleting an `App::Link` array with `ShowElement` true deletes only the array. Its `App::LinkElement` children stay in the document as orphan objects that still link to the source. FreeCAD's `LinkBaseExtension::detachElements` (`App/Link.cpp:2455`) detaches them and does not delete them. `deleted` correctly reports `['Arr']`, but the tool description and §3.7.2 do not say that the elements stay. |

### RT-1 reproduction (`probes2.py p_boolean_recompute`, `probes4.py p_boolean_with_deps`)

Fixture plus `Body2` (Sketch 10x10 at x=30, PadB 10). `Bool = Body.newObject("PartDesign::Boolean")`, `Bool.addObjects([Body2])`. Then `document_object_delete(objects=["Body2"])`. Then touch every object and recompute.

```
before: Body vol 5124.999999999999 XMax 40.0 Body2.InList ['Bool']
delete Body2 ('OK', None, ['Body2', 'Origin002', 'X_Axis001', ..., 'SketchB', 'PadB'], [], False, None, 'CLEAN')
after full recompute: Body vol 5124.999999999999 (Body1 alone = 4125) XMax 40.0 Bool state ['Up-to-date'] Body2 present False
--
delete Body2 with_dependents OK []
after vol 5124.999999999999 Bool.Group [] (Body1 alone 4125)
```

Cause: `features.py:2377` `if held and not held <= _names(getattr(obj, "Group", None)):` exempts `Bool`, because `Body2` is only in `Bool.Group`. `FeatureBoolean.cpp:79-82` returns `StdReturn` when `Group` is empty and does not write `Shape`, so the Boolean keeps the fused result. The design text (§3.7.2, `mcp-tools-design.md:636`) has the same rule: "A container that holds the object only in its `Group` (a Body, Part or group) is not a dependent". A `PartDesign::Boolean` is not a passive container: its `Group` is its operand list.

### RT-2 reproduction (`probes4.py p_body_expression_on_child`)

Fixture plus `Body.setExpression("Placement.Base.z", "Pad2.Length")`. Then `document_object_delete(objects=["Pad2"])`, and again with `with_dependents=True`.

```
delete Pad2 while Body.Placement.z = Pad2.Length RECOMPUTE_ERROR {'code': 'mutation.recompute_error', 'message': "recompute left 1 object(s) invalid: Body: Document object 'Pad2' not found in 'Pad2.Length'\nin property binding 'feature_tools#Body.Placement'"} True rolled_back_verified Pad2 present True
with_dependents RECOMPUTE_ERROR mutation.recompute_error
```

`Body.OutList` holds `Pad2` from the Group and from the expression. `held = {Pad2}` is a subset of `Group`, so the expression edge is hidden. The cheapest fix is to test `held <= Group` against the expression and link edges, not against the name set. It must also cover RT-1.

### RT-3 reproduction (`probes4.py p_link_array_orphans`)

`Arr = App::Link` to `Box`, `ShowElement = True`, `ElementCount = 3`. Then `document_object_delete(objects=["Arr"])`.

```
delete Arr OK ['Arr']
Arr_i0 present True Box [] App::LinkElement
Arr_i1 present True Box [] App::LinkElement
Arr_i2 present True Box [] App::LinkElement
```

After `document_undo`, all names and `Arr.ElementList` come back (`restored equal True ElementList ['Arr_i0', 'Arr_i1', 'Arr_i2']`).

## Checked and held (no defect)

- **Q6 undo and abort completeness.** `probes3.py` compares a full state dump before the delete and after `document_undo`, and also after a forced abort (`post_verify` patched to raise). Per object, the dump holds Label, Visibility, OutList, InList, ExpressionEngine, Placement, State, Body Tip/Group, other Group, BaseFeature and volume. Ten scenarios, each run both ways: whole Body; `VS` with dependents; `Sketch1` with dependents; `Pad2` Tip; Body with hidden members; Boolean tool Body; `App::Part` holding Body and VS; Body inside a Part; a Spreadsheet alias driving Pad2 (`SS` with dependents); `VS` driving SS driving Pad2. Every case gave `DIFF: none`. Every abort gave `rolled_back_verified`, and the expression chain still follows `VS` after each one.
- **Spreadsheet cells.** A cell `=VS.L` keeps its dependency after undo and after abort (`VS.L=7 -> SS.w = 7.0 mm`). A cell `=Pad2.Length` makes SS a dependent of Pad2 (refused).
- **Sketch constraint expressions** (`.Constraints.w = VS.L * 2`) follow after undo (`Sketch1 width 30.0`, `Pad1.Length 15.0`).
- **Links.** `App::Link` to a Box with `Length = VS.L`: refused alone, deleted with dependents, then restored by undo (`LinkedObject Box`, `Box.InList ['Lnk']`, the Link follows `VS.L=33`).
- **References.** External geometry and a datum attached to a deleted face: both restored (`ExternalGeometry [(Pad2, ('Edge1',))]`, `DP support [('Pad2', ('Face6',))]`, `Pad2.InList` holds `DP`).
- **Group order.** `DocumentObjectGroup` membership order is restored (`['V2', 'V3']`).
- **Q7 undo stack.** After an abort with one earlier undo step, Undo/Redo stays `(1, 0)` → `(1, 0)`, and the next `document_undo` reverts the earlier step. Delete → `document_undo` → `redo` → `document_undo` gives counts `(1,0)`, `(0,1)`, `(1,0)`, `(0,1)`, Tip `Pad2`, and Pad1 still follows `VS`.
- **Q4 TNP exemption.** It excuses a record only when `paired is None`, the owner is in `deleted`, and `getObject(owner)` is `None`. Any owner that FreeCAD failed to delete raises the survivors `RuntimeError` first. A surviving owner pairs and is graded as before. No probe found a broken survivor reference that was excused.
- **Q8 preview.** `preview_dry_run` of `VS` with dependents returns `OK`. The document names, `(UndoCount, RedoCount)` `(0,0)` and Pad1's binding are unchanged, and Pad1 still follows `VS`.
- **L12 shared code.** `document_undo` of a `feature_set_parameters` call returns the same key set as before (`doc, errors, fingerprint_after, fingerprint_before, matches_pre_op, name, restored_objects, undo_count, undone`) and `errors []`.
- **Body BaseFeature wrapper.** Deleting a Body's `PartDesign::FeatureBase` wrapper alone returns `OK`. FreeCAD clears `Body.BaseFeature` and leaves the Box. The state is consistent.

## Not reproduced

| Id | Severity | Q | Note |
| --- | --- | --- | --- |
| NR-1 | low | Q5 | `_object_state` (`features.py`) does not read `Visibility`, `ExpressionEngine` text, or the `Group` of a non-Body container. An abort that lost one of these would still read as proven. No probe produced such a loss: every abort diff was empty. |
| NR-2 | low | Q6 | `shim.relink_expressions` clears and sets each binding again. A restored binding whose text no longer parses (cross-document target, R1-D1) would be cleared and only reported in `errors`. I did not test this, because cross-document links are deferred (R1-D1). |
| NR-3 | low | Q7 | The relink in the GUI host can open an auto-transaction. This is already in the ledger as R1-U1, for the container verifier. I did not test it. |
| NR-4 | low | outside the bar | An aborted mutation on a document that was not recomputed before the call (a `VS.L` change without recompute) ends in `SPEC_FAILED` "rollback could not be proven", with the document replaced from the snapshot. This comes from the bracket's pre-op fingerprint, which existed before this Story; it is not new in this diff. |

## Verdict

**FAIL.** RT-1 breaks Q2: a Boolean that depends on the deleted Body is not refused, and the call returns `OK` with stale geometry. RT-2 is a second gap in the same Q2 rule. The Q3-Q9 attacks held.
