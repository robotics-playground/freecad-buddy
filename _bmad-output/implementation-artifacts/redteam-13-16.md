# Story 13-16: red team report

Head: 15a097d6 (`story/13-16-set-parameters-placement-strings`). Diff attacked: bde93e33...15a097d6 without the integration merge 0253cdd7 (story diff = `git diff 547542cd 15a097d6`). Method: `bmad-code-review` lenses (adversarial, edge case, verification gap) run by one agent. Every claim below has a probe run on host `freecadcmd.exe` 1.1.4 with private `-u`/`-s` cfg and private `FREECAD_USER_HOME`, through the real handler (`MethodRegistry.dispatch` -> `feature_set_parameters` -> `run_mutation`). No container, no ports 6901/18765.

Probe sources (kept): `C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\17c8e5ee-89aa-4e27-ba05-1fe1774e804a\scratchpad\redteam-13-16\probes\rt1.py` to `rt8.py`; runner `...\redteam-13-16\run.sh <module>`; raw logs `...\redteam-13-16\rt1.log` to `rt8.log`. The probes import the 13-16 fixtures (`_PlacementFixture`, `padded_body`, `dispatch`) from the exported copy at 15a097d6. The copy is removed.

Verdict: **FAIL** (1 high, 3 medium).

## Reproduced

### RT-1 — high — Q6 — rollback reported as failed although it succeeded (R2-H1 class, fix incomplete)

`src/freecad_buddy/usecases/features.py:2456`:

```
    them back from the saved file, which keeps 16 digits, so an exact comparison fails on a
```

`features.py:2473`:

```
    return "nan" if number != number else float(f"{number:.15g}")
```

The premise is wrong. FreeCAD saves a float with 16 **decimals**, not 16 significant digits. A value below 0.1 reopens with fewer than 15 significant digits, so the 15-significant-digit probe reading of the restored document differs from the pre-mutation reading. The snapshot restore is then reported as unproven: `SPEC_FAILED`, `rolled_back: false`, snapshot kept on disk, text "Mutation failed and its rollback could not be proven". The document is in fact restored.

Save format (probe `rt1.test_p1_save_format`, `saveCopy` + `openDocument`):

```
P1 ratio before 0.0003333333333333333 after 0.0003333333333333
P1 base before (0.0003333333333333333, 1e-20, 0.0) after (0.0003333333333333, 0.0, 0.0)
P1 Q before (0.0, 0.0, 0.004363309284746571, 0.9999904807207345) after (0.0, 0.0, 0.004363309284746547, 0.9999904807207345)
P1 comparable equal? False False
```

Production path, no mocks (`rt2._p8`): Body from `padded_body()`, `Body.Placement` set, `setExpression(".Placement.Base.y", "3 mm")`, then `dispatch("Body", {"Visibility": False, "Placement": base(y=9.0)})`. The expression overwrites y (`value_overwritten`), the abort does not restore `Visibility` (spec row 17), so the bracket takes the snapshot restore:

```
P8a plain          RECOMPUTE_ERROR rolled_back True  proven rolled_back_via_snapshot   (Base x=1, no rotation)
P8b x=1/3000       SPEC_FAILED     rolled_back False proven None
P8b after  {'vis': True, 'base': (0.0003333333333333, 3.0, 0.0), ... 'expr': [('.Placement.Base.y', '3 mm')]}
P8b probe equal False {'Placement': (0.000333333333333333, 3.0, ...)} {'Placement': (0.0003333333333333, 3.0, ...)}
P8b snapshots left ['...\\FCB_TMP_snap_u492wl95']
P8c rot 0.5deg     SPEC_FAILED     rolled_back False proven None
P8c probe equal False {... 0.00436330928474657 ...} {... 0.00436330928474655 ...}
P8d rot 30deg about (1,2,3) RECOMPUTE_ERROR rolled_back True proven rolled_back_via_snapshot
```

Mutant that isolates the probe as the only cause (`rt3.test_b_mutant_12_digits`, `_stable_float` patched to 12 significant digits, same setup as P8c):

```
P8 mutant 12 sig digits RECOMPUTE_ERROR True rolled_back_via_snapshot snapshots 0
P8 control SPEC_FAILED False None snapshots 1 vis now True y 3.0
P8 control text Mutation failed and its rollback could not be proven: ...\FCB_TMP_snap_4gqt9jmv\feature_tools.FCStd.
```

Not limited to placements (`rt3.test_d_float_property`): `Block.FuzzyTolerance = 1/3000`, `Length` expression-bound, `dispatch("Block", {"Visibility": False, "FuzzyTolerance": 0.5, "Length": mm(7.0)})`:

```
P10 float prop SPEC_FAILED False None ... rollback could not be proven: the snapshot-restored document does not match the pre-mutation fingerprint ... or the pre-mutation property state
```

Scope: any written float, quantity or placement component whose pre-mutation value is below about 0.01 in magnitude and carries full double precision. For a rotation that means a quaternion component below 0.01, for example any rotation under about 1.15 degrees about a principal axis. Trigger: any failed call that escalates to the snapshot restore (a `Visibility` write in the same call is enough). The test `Should_prove_the_snapshot_restore_When_a_float_and_a_length_hold_17_digits` only uses values of 0.3 and 1.2e8, where 16 decimals keep at least 15 significant digits, so it passes.

### RT-2 — medium (product) — Q2 — out-of-range integer in a placement quantity gives `RECOMPUTE_ERROR`, not `INVALID_INPUT`

`features.py:117` (reached from the new parser through `features.py:2554`):

```
    if not math.isfinite(float(magnitude)):
```

`float(10**400)` raises `OverflowError`, which is not a `ValidationError`. The dispatcher maps it to `RECOMPUTE_ERROR` with a traceback. No transaction opens (it raises in the no-op check). Probe `rt1.test_p7_huge_int`:

```
dispatch("Body", {"Placement": base(x=10**400)})
P7 base  {"status": "RECOMPUTE_ERROR", "detail": {"code": "RECOMPUTE_ERROR", "message": "int too large to convert to float", "data": {"exception": "OverflowError", ...
dispatch("Body", {"Placement": {"rotation": {"axis": [0, 0, 1], "angle": deg(10**400)}}})
P7 angle {"status": "RECOMPUTE_ERROR", "detail": {"code": "RECOMPUTE_ERROR", "message": "int too large to convert to float", ...
```

Q2 requires `INVALID_INPUT`. R1-M fixed the same failure for the axis only (`"axis beyond the float range"` case); the base and angle quantities were not covered. The helper is shared, so other tools that take a quantity have the same pre-existing defect; within this Story it breaks Q2.

### RT-3 — medium (product) — Q2, Q6 — an unbounded finite base commits a document the bracket cannot fingerprint

The parser bounds the axis length (`_MAX_AXIS_LENGTH = 1e100`, `features.py:2333`) but not the base. Probe `rt6.test_large`, `dispatch("Body", {"Placement": base(x=1e150)})`:

```
P6c 1e+150 SPEC_FAILED False FreeCADError: Unknown exception while reading attribute 'PrincipalProperties' of object 'TopoShape' stored 1e+150 undo0 ['buddy: set parameters on Body 1']
P6c text Mutation failed and its rollback could not be proven: ...\FCB_TMP_snap_dvtx8ds3\feature_tools.FCStd.
```

`post_verify` passes, the commit lands, then the after-fingerprint raises (`transaction.py` `_unhashable_commit_envelope`). The document keeps `Base.x = 1e150` and the call's own undo step heads the stack, but the result is `SPEC_FAILED` with no `undo_steps` and a text that speaks of a rollback. `rt1.test_p6_large_values` gives the same for 1e308; 1e300 returned `OK`. A caller cannot tell from the result that the change is committed and that one `document_undo` reverts it.

### RT-4 — medium (test double) — Q4 — the integer-clamp fake models a clamp FreeCAD never does

`tests/infc/test_set_parameters_placement.py:539`:

```
        stored = _Stub(Count=2**31 - 1)
```

The test (ledger R3-M2, "fixed-proven") asserts that `_holds_written` tells 2**31 from a stored 2**31 - 1. Real `App::PropertyInteger` never stores a clamped 2**31 - 1: the C long conversion fails inside `setattr`, after the snapshot is written and the transaction is open. Probe `rt7.test_int_out_of_range_real` (`Count = 5`, then `dispatch("Py", {"Count": 2**31})`):

```
P2d SPEC_FAILED {'code': 'mutation.spec_failed', 'message': 'SystemError: <built-in function setattr> returned a result with an exception set'} rolled_back True rolled_back_verified Count 5
```

(`rt2.test_f_int` gave `OverflowError: Python int too large to convert to C long` on the same path; `2**31 - 1` stores as `OK`.) The fake skips FreeCAD's real range check, so the red mutant proves a path that cannot happen, and the real behavior of an out-of-range integer (late `SPEC_FAILED` with a raw interpreter message, not `INVALID_INPUT` before the bracket) is untested. The integer family itself is pre-existing; the false proof is in this Story.

## Low

- **L-1 (Q1).** An `OK` placement write carries no stored placement. `rt5.test_ok_result_content`: keys `['feature', 'feature_state', 'mutation', 'undo_steps']`; `feature_state.shape_summary.bbox` is `[8.0, 16.0, 5.0]` (size, not position). Q1 says "result reads back the stored placement"; the contract (`tool-contracts.md:188-197`) asks only for the stored `Label`. The read-back check exists; only the reporting is absent.
- **L-2 (test).** `ReadBackRuleTest.test_Should_accept_the_offset_When_an_attached_object_has_a_hidden_offset_status` uses `_Stub.getPropertyStatus`, which the code no longer calls. The real case works: `rt7.test_hidden_offset_real` (sketch attached to a Box face before the Box had a shape) gives `P16 status ['Hidden'] MapMode FlatFace`, then `P16 tool OK None placement z 12.0`. No product defect; the test name describes a state the stub does not build.

## Attacked, no defect found (with probe)

| Attack | Probe | Result |
| --- | --- | --- |
| Label rename rewrites `<<Py>>` in another object's expression; abort path | `rt1.test_p4_*` | `P4 after [('Height', '<<Py>>.Placement.Base.x + 5 mm')] Py label Py`, `rolled_back_verified` |
| Same, snapshot path (with `Visibility`) | `rt1.test_p4b_*` | expression and label restored |
| Label OK then `document_undo` restores the other object's expression | `rt1.test_p4c_*` | `<<Main>>` -> undo -> `<<Block>>` |
| Expression on `Label` | `rt1.test_p3_*` | write stored `New`, `OK`, no revert |
| Strings CR, CRLF, LF, TAB, U+0085, U+2028, spaces, XML text, astral, 200 000 chars: write and save/reopen | `rt5.test_strings`, `test_label_strings` | all `OK`, all `same` after reopen |
| Body move and rotation with a sketch on a Pad face; `AttachmentOffset` of the profile | `rt1.test_p5_*` | `OK`, `undo_steps 1` |
| Body move with a cross-body sketch on its face | `rt3.test_e_*`, `rt4` | `tnp_audit CLEAN, PASS 3`; the other sketch does not follow, which is the same with a manual set + recompute (FreeCAD behavior) |
| `MapMode` Translate: Placement not read-only (`AttachExtension.cpp:768`) | `rt3.test_f_*` | base write -> `value_overwritten` with the AttachmentOffset hint; rotation write `OK` |
| `PropertyIntegerConstraint` clamp | `rt2.test_g_*` | `Polygon 1` -> `RECOMPUTE_ERROR value_overwritten`, value 6 kept |
| Expression-bound placement without `Visibility` | `rt3.test_a_*` | `rolled_back_verified` |
| Units | code `features.py:35-36` | only `mm` and `deg` accepted; `m` and `rad` refused |
| Confirm gate for Label-only and Placement-only calls | `test_confirm_gate.py` diff | tests use the real gate; no-op before the gate is the accepted rule (spec rows 3, 37) |

## Not reproduced

- Rotation residue such as `Base.y = 6.1e-16` triggering RT-1: `rt8.test_residue` composed a 90-degree turn with a translation and FreeCAD stored `(0.0, 10.000000000000002, 3.0)`; the call rolled back via snapshot and was proven. The RT-1 class still holds for any genuine small value (P8b, P8c, P10).
- A Python feature that resets `Label` in `execute`: the result would be `OK` with `label.stored` showing the old value, because `Label` is exempt from the read-back by design. Not probed; low.

## Cleanup

Exported copy removed with `git worktree remove`. Own snapshot session folder `FCB_TMP_session_42588_fdfef686` and temp `rt1316_*.FCStd` files deleted. Other `FCB_TMP_session_*` folders in `%LOCALAPPDATA%\freecad-buddy-workdir\tmp` were left because their owner is not certain. No process left running.
