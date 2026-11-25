# Story 13-10: red team report

Head: f2a19ce8 (branch story/13-10-set-expression). Base: 3c8efd8d. Red team: redteam-13-10 (claude-opus-5-5, effort high).
Quality bar: `quality-bar-13-10.md`. Known items not re-reported: review-ledger-13-10.md (R1-*, R1-S1, R1-D1, R1-D2) and the spec triage log (rows 1-23).

Method: `bmad-code-review` layers (blind read of the diff, edge cases, acceptance against Q1-Q9), applied by this agent. Every probe drives the product function `features.feature_set_expression` (or a sketch tool) through the real `run_mutation` bracket under host `freecadcmd.exe` 1.1.4 (private `-u`/`-s` cfg, `FREECAD_USER_HOME` in scratch), with `sys.path` set to the red-team worktree `src` (printed `PKG ...fcb-redteam-13-10\src\freecad_buddy\__init__.py`). Base comparisons ran the same probe on a `git archive 3c8efd8d` copy. Probe scripts: scratchpad `redteam-13-10\` (`harness.py` plus one `p_*.py` per probe; run as `PROBE=<p_x.py> freecadcmd -u user.cfg -s system.cfg harness.py`).

Fixture (`harness.py`): VarSet `Params` (`width` Length 12 mm, `tilt` Angle 30 deg, `count` Integer 4, `ratio` Float 0.5, `flag` Bool), `Part::Box` `Box`, sketch `Sketch` with named constraint `span` (DistanceX 10 mm), all recomputed.

## Reproduced

| Id | Severity | Q | Where | Finding |
| --- | --- | --- | --- | --- |
| RT-8 | high | Q5 (L2) | `features.py:2316`, `features.py:2484` | A 31-character range expression on a spreadsheet cell held one call for 1,087 s; the 400-character cap bounds parser depth, not evaluation cost |
| RT-1 | medium | Q1, Q6 (L6) | `features.py:2642` | `undo_steps: 0` while FreeCAD recorded one undo step, when the document holds touched objects |
| RT-2 | medium | Q5 (L8) | `features.py:2431` | Integer property: values outside int32 are stored as `-2147483648` and reported `bound`, status `OK` |
| RT-3 | medium | Q2 (L8) | `features.py:2466` | A spreadsheet cell property (`Sheet.A1`) is bound: dependent cells ignore it, and save + reopen drops the binding |
| RT-4 | medium | Q5 (L8) | `features.py:2413` | Property range constraints are bypassed: `Part::Revolution.Angle` 400 builds a 40 deg solid reported as 400; `Pad.Length` -5 mm flips the pad below the sketch (`feature_set_parameters` refuses both) |
| RT-5 | low | Q4 (R1-S1 check) | `tnp_guard.py:834-848` | Shared exemption changes `sketch_remove_geometry`: base rolls back, head commits and drops a driving binding; the result names it only as `counts: {PASS: 1}` |
| RT-6 | low | outside the bar (R1-D1 scope) | `features.py:2484` | Pre-batch check misses rounding and int32 overflow caused by a sibling item or by an existing dependent binding, not only non-finite values |
| RT-7 | low | Q5 | `features.py:2466` | `.Shape.Volume` and `.Placement.Base.Length` pass the precheck as numbers and fail in the bracket (`RECOMPUTE_ERROR`, rolled back) instead of `INVALID_INPUT` |

### RT-8 (high): the character cap does not bound evaluation cost (L2)

Spreadsheet range functions parse only in a `Spreadsheet::Sheet` context, and RT-3 shows a cell property of a sheet is an accepted target. A range is evaluated cell by cell, up to `ZZ16384` (702 x 16,384 cells), while the call holds the GIL. Reproduction (`p_range2.py`, `p_range3.py`, sheet with `A1 = 1`, `B1 = 2`):

```
RANGE Sheet sum(A1:ZZ2000) -> 6 in 2.48s
ONE range eval 0 48.2s                                  # sh.evalExpression("sum(C1:ZZ16384)")
TOOL 2 ranges 31 chars {"status": "OK", "bound": [{"object": "Sheet", "path": "B1", "value": 0}], "undo_steps": 1, ...} 1087.4s
FULL text length 399 (cap 400) ranges 25
```

One call with `sum(C1:ZZ16384)+sum(C1:ZZ16384)` (31 characters) ran 1,087 s: 1,087 s divided by 96 s for one two-range evaluation gives about 11 evaluations per call (inferred, not counted; the code evaluates it at least in the no-change check, the precheck and the recompute). A 399-character text holds 25 ranges, about 20 minutes per evaluation by the same rate (not run). The binding is then stored, so each later recompute of the sheet re-evaluates it (expected, not measured). The bridge timeout cannot fire while the GIL is held (L2). Fix direction: refusing spreadsheet cell targets (RT-3) closes this route, because a range does not parse in any other object's context (`sum(Sheet.A1:Sheet.A100)` and `sum(<<Sheet>>.A1:A100)` from `Params` are `ParserError`); state the cost basis beside `_MAX_EXPRESSION_LENGTH`.

### RT-1 (medium): `undo_steps: 0` is false when the document has touched objects

Path: an in-bracket no-op (equivalent text `Params.width*2` for stored `Params.width * 2`, spec change log (c)). The bracket recompute runs inside the transaction. When an object is touched before the call (a property edit not yet recomputed), that recompute writes properties inside the transaction and FreeCAD commits it as a step named `buddy: set expressions`. `report` computes `undo_steps` from `applied` only:

```python
content["undo_steps"] = 1 if applied and document.UndoMode else 0
```

Reproduction (`p_undo3.py`, undo mode on, user step `P.tilt = 45` committed and NOT recomputed, then one call):

```
U box equivalent-text undo_steps 0 mutation block True | UndoCount 1 -> 2 ['buddy: set expressions', 'user step']
U sketch equivalent-text undo_steps 0 mutation block True | UndoCount 1 -> 2 ['buddy: set expressions', 'user step']
```

Same probe with `d.recompute()` after the user step (no touched objects): `UndoCount 1 -> 1`. So the defect needs a touched document. `p_undo2.py` shows the effect: after the call, `document_undo` pops the empty `buddy:` step and the user step survives (`ratio now 0.9`), which contradicts the tool text "so document_undo would revert an earlier step". The fast path (exact same text) has no bracket and is correct. Fix direction: measure the step (compare `UndoNames[0]`/`UndoCount` around the commit, guarded for the full 20-step stack), or treat "no item applied" as an abort of the transaction.

### RT-2 (medium): int32 overflow stored and reported as bound

`_value_problem` refuses only fractions on an `int` property. FreeCAD `PropertyInteger::setPathValue` converts the double with `setValue(boost::math::round(...))` into a C `long` (FreeCAD source `src/App/PropertyStandard.cpp:150-151`), and `long` is 32 bit on Windows, so an out-of-range double converts to `INT_MIN`. Reproduction (`p_values.py`, `p_rev2.py`):

```
CASE ('Params', 'count', '3000000000')  -> status OK, bound value -2147483648 | live: -2147483648
CASE ('Params', 'count', '-3000000000') -> status OK, bound value -2147483648 | live: -2147483648
INT 1e10       -> status OK, bound value -2147483648
INT 2147483648 -> status OK, bound value -2147483648
INT 2147483647 -> status OK, bound value 2147483647
```

The stored value differs from the expression value with no refusal (L8). Not checked on the Linux container (there `long` is 64 bit, so the threshold differs by platform).

### RT-3 (medium): spreadsheet cell property binding is accepted and later lost

`Spreadsheet::Sheet` exposes each cell as a dynamic property, so `object: Sheet, path: A1` resolves to a number and passes every check. The cell keeps its own content. Reproduction (`p_sheet.py`, cell `A1 = 1`, `B1 = =A1*10`):

```
SH bind {"status": "OK", "bound": [{"object": "Sheet", "path": "A1", "value": 7}], "undo_steps": 1, ...}
   A1 value 7 A1 contents 1 B1 10 EE [('A1', '7')]
   after unrelated cell edit: A1 7 B1 10
   after reopen: A1 1 B1 10 EE []
```

The tool reports `A1 = 7`, but `B1` still computes from content `1`, and after save and reopen the binding is gone and `A1` reads 1 again. A binding FreeCAD accepts and then silently drops. Fix direction: refuse cell properties of a `Spreadsheet::Sheet` (`expression.unsupported_property`); cells are set through cell contents.

### RT-4 (medium): property range constraints bypassed through the expression path

FreeCAD applies an expression value through `setPathValue`, which does not clamp to the property's constraint range. The precheck has no range check. Reproduction (`p_rev.py`, `p_rev2.py`):

```
REV 400 -> status OK, bound value 400.0 | after 400.0 valid True vol 43.86   (full 360 deg revolve: vol 394.78; 400 deg sweeps 40 deg)
PADNEG before bbox BoundBox (0, 0, 0, 20, 10, 5)
PADNEG -> status OK, bound value -5.0 mm | after bbox BoundBox (0, 0, -5, 20, 10, 0) Length -5.0 mm
```

`Part::Revolution.Angle` (range +-360) reports 400 while the solid is a 40 deg sweep. `Pad.Length` -5 mm moves the pad to the other side of the sketch. `feature_set_parameters` refuses both inputs ("A length must not be negative and an angle must be within +-360 deg"). `PartDesign::Revolution` 400 deg fails the recompute and rolls back, so it is safe. Fix direction: read the property's constraint range (`getPropertyStatus` / type `*Constraint`, or the same limits `feature_set_parameters` uses) and refuse out-of-range values.

### RT-5 (low): R1-S1 check: the shared exemption changes `sketch_remove_geometry`

Reproduction (`p_tnp2.py`): fully constrained sketch with a circle whose named radius `hole_r` is bound to `Params.width / 4`; `sketch_remove_geometry(geo_ids=[4])` removes the circle and its three constraints.

```
head: T2 {"status": "OK", "mut": {"rolled_back": false}}  after: geo 4 constraints 12 EE []
      post_verify.tnp_audit: {"status": "CLEAN", "counts": {"PASS": 1}, "findings": []}
base: T2 {"status": "SPEC_FAILED", "msg": "TNP audit flagged 1 reference(s): R.ExpressionEngine[.Constraints.hole_r] BROKEN", "mut": {"rolled_back": true}}
```

The change is the documented rule (mcp-tools-design.md:662, triage row 22), and it removes a base false positive. Two gaps remain: no test covers another tool (only `ExpressionBindingTest` in `test_tnp_guard.py`), and the envelope does not say a driving binding was dropped (PASS findings are projected away). Other checks of the exemption held: a binding removed during the recompute, an owner removed from the document, and `written=None` still grade `BROKEN` (existing tests); `script_exec` does not call `audit_references`; no typed tool removes and re-creates an object under the same Name, so the owner-presence check cannot be fooled through a typed tool. An index-addressed binding (`.Constraints[14]`) that a geometry removal shifts out of range fails the recompute and rolls back at base and head alike (`p_tnp3.py`, `Array out of bound: 14, 12`).

### RT-6 (low): R1-D1 root is wider than non-finite values

The precheck evaluates each expression against pre-batch values (`features.py:2484`). Reproduction (`p_sib.py`):

```
SIB int  [ratio="0.3", count="Params.ratio * 8"] -> OK, bound count 2   (exact 2.4; not_integer bypassed)
SIB dep2 [count already bound to Params.ratio * 8; call binds ratio="0.3"] -> OK, count now 2
SIB dep3 [same, ratio="1e9"] -> OK, count now -2147483648
```

The deferred R1-D1 names only non-finite values; rounding and int32 overflow reach the document by the same route. Route to R1-D1 (shared post-recompute check).

### RT-7 (low): non-writable numeric sub-paths reach the bracket

Reproduction (`p_values.py`):

```
('Box', '.Shape.Volume', '5')          -> RECOMPUTE_ERROR "Attribute 'Volume' of object 'TopoShape' is read-only", rolled_back true
('Box', '.Placement.Base.Length', '5') -> RECOMPUTE_ERROR "Cannot set length of null vector", rolled_back true
```

Safe (proven rollback, bindings empty after), but the spec "Never: bind ... a Shape" expects an `INVALID_INPUT` refusal before the bracket, and the caller gets a recompute status for an input error.

## Not reproduced (attacks that held)

| Attack | Result |
| --- | --- |
| Crash below the 400-char cap (Windows host) | `1*` x 600 terms (1,201 chars) evaluates; crash (exit 139) between 600 and 1,000 terms; `1<` crashes at 900 terms; `1^` x 600, `!` x 1,500 pass; nested `(`, `-`, `sin(`, `1?1:` at <= 400 chars are parser errors, no crash. The cap holds on the host with more margin than the comment states. Linux container stack not measured. |
| Units | `1 m` on a length reads 1000 mm; `30`, `30 deg`, `0.5 rad` on a sketch Angle constraint read 30, 30, 28.648 deg and move the geometry to match; `.Placement.Rotation.Angle` `30` reads 30 deg; a unitless VarSet float on an angle reads 0.5 deg (documented rule: a plain number takes the property unit). `Part::Revolution.Angle` (plain float) refuses `400 deg` as `unit_mismatch` (usability only). |
| Reference (non-driving) constraint | `setExpression` raises "Reference constraints cannot be set!", call `SPEC_FAILED`, rolled back, binding absent. |
| Read-only and attached placements | `Pad.Placement`, attached sketch `Placement` refused `unsupported_property`; `.AttachmentOffset.Base.z` binds and moves the sketch. |
| Clamped Part properties | `Part::Cylinder.Angle` 400/-30 deg, `Radius` -2 mm, `RegularPolygon.Polygon` 2, `Part::Sphere.Angle1` -100 deg, `Box.Length` 0/-5 mm, `PartDesign::Revolution.Angle` 400/720 deg: recompute error, rolled back, value and bindings restored. |
| Rollback of shapeless values (triage row 8) | A sibling binding `Params.ratio = 42` with a failing `Box.Length = 0 mm`: ratio 0.5 and no binding after rollback; a clear plus rebind plus failure restores `ratio` 2.0, `count` 4 and `[('ratio', 'count / 2')]`. |
| Undo and redo of a 3-item batch | One `document_undo` restores Box 10 mm, span 10 mm, all three bindings empty; `redo` restores all three. |
| Index vs name spelling no-op on a clean document | `.Constraints[2]` with the text stored under `.Constraints.span`: `unchanged`, `undo_steps` 0, `UndoCount` unchanged. |
| `.Placement.Rotation.Yaw`, `.Placement.Matrix.A14` | Bind and read back as bound (45 deg yaw, x = 7). `.Placement.Rotation.Axis.x = 2` stores 2.0 with no effect at angle 0 (meaningless input, not a defect). |
| Bool fraction | `flag = 0.3` reads False: left as FreeCAD does it by triage row 6, not re-reported. |
| L12 regressions | `scalar_reading` rename has no stale caller; targeted infc suites `test_feature_expressions`, `test_tnp_guard`, `test_sketch_tools`, `test_query_tools`, `test_feature_parameters`: 382 run, 0 fail; `pytest tests/external -k "expression or feature_contract or confirm_contract or mcp_surface"`: 187 passed; `check_provenance` OK. |

## Verdict

FAIL. One high: RT-8 breaks Q5 (the cap is meant to keep FreeCAD alive and responsive, L2; a 31-character expression held one call for 18 minutes). Four product mediums are open: RT-1 (wrong `undo_steps` on a touched document, L6), RT-2 (int32 overflow stored, L8), RT-3 (spreadsheet cell binding accepted, then lost), RT-4 (range constraints bypassed, L8). Refusing spreadsheet cell targets fixes RT-3 and RT-8 together.
