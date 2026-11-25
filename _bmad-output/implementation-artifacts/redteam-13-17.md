# Story 13-17: red team report

Head: `deaa2b25` (branch `story/13-17-part-primitive-boolean`). Story commits: `88b52fc4`..`deaa2b25` (12, no merges).
Method: `bmad-code-review` adversarial lens, run alone. Every claim below has a probe that drives the real handlers (`features.feature_part_boolean`, `features.feature_part_primitive`) under host `freecadcmd.exe` 1.1.4 with private `-u`/`-s` cfg files and a private `FREECAD_USER_HOME`. The import path was checked: `features.__file__` is the exported copy of `deaa2b25`.
Probe scripts: `C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\17c8e5ee-89aa-4e27-ba05-1fe1774e804a\scratchpad\redteam-13-17\probes\` (`h.py` harness, `p1.py`..`p12.py`).

Verdict: **FAIL**. 2 high, 1 medium, 2 low.

## Reproduced

### RT-1 — high — Q4, Q5 (also Q11): a stale dependency bypasses the trust and cost refusals; a wrong volume is reported OK

Where: `src/freecad_buddy/usecases/features.py:4252`

```python
        stale = _FAILED_STATES & set(obj.State)
```

The stale check reads only the State of each input. When an object that an input is built from is `Touched`, the input itself reads `Up-to-date`. The prechecks then measure the old shape of the input. The bracket recompute rebuilds the input before the boolean runs, so the boolean runs on a shape that no check has seen. This is the same failure class that round 2 fixed for a `Touched` input (Cut 1500 where 500 is right), one level deeper.

Probe A, `p2.py` (wrong result reported OK). `A = Part::Reverse(Mid)`, `Mid = Part::Reverse(Box0)`: A is a proper 10 mm cube. Then `Mid.Source = Rev` (a reversed cube), with no recompute:

```
[before: A volume, trusted] [999.9999999999998, true]
[states after edit] {"Box0": ["Up-to-date"], "Rev": ["Up-to-date"], "Mid": ["Touched"], "A": ["Up-to-date"], "B": ["Up-to-date"]}
[cut A - B (analytic 500 for a proper cube)] {"status": "OK", ... "volume": 1500.0, "solid_count": 1 ...}
[A after: volume, trusted] [-999.9999999999998, false]
```

The tool reports `OK` with volume 1500 for the cut of a reversed solid. This is the exact wrong number that `part_boolean.untrusted_shape` exists to prevent. The result check (`_part_boolean_result_check`) does not catch it: 1500 is positive and the shape is valid.

Probe B, `p3b.py 40` (cost limit bypassed). Two `Part::Compound` inputs wrap two Draft ortho arrays of crossing cylinders (the shipped `crossing_family` layout, plate 400 x 400 x 10). The arrays have 2 elements when the document is recomputed. Then `NumberX`/`NumberY` are set to 40, with no recompute:

```
[before edit: solids] [2, 2]
[states] {"Array": ["Touched"], "Array001": ["Touched"], "FamX": ["Up-to-date"], "FamY": ["Up-to-date"]}
[cut plate by stale families] {"status": "OK", "t": 63.17, ... "face_count": 4807 ...}
[after: solids] [40, 40]
[fresh guard] ["PartToolRefusal", "part_boolean.too_complex", "the inputs hold 246 faces (limit 3000), 1680 solid pairs across the inputs ..."]
```

The guard counted 8 pairs on the old shapes. It accepted 1,680 pairs, and the call held the bridge for 63.2 s. With 100 elements per array (`p3b.py`, 10,200 pairs) the call ran longer than 180 s (killed by the probe timeout).

How a document gets there: `script_exec` (on by default) or a GUI property edit without a recompute, the same route that makes the round-2 `Touched` input. Fix direction: refuse when any object in `getOutListRecursive()` of an input is `Touched`/`Invalid`/`Error` (or `obj.mustRecompute()` is true), or recompute and re-check before the bracket.

### RT-2 — high — Q11: crossing families at a small angle pass the limits and run longer than 300 s

Where: `src/freecad_buddy/usecases/features.py:4161-4162` (limits) and the cost comment above them.

Two families of n parallel cylinders (radius 1, pitch 3) cross each other at 2 degrees (`p12.py n fuse 2`). The families are single-face-per-solid cylinders, not the decision-52 comb (one solid with many faces). The guard runs and passes on every case below:

| n | faces | pairs (across + inside) | op | result | time |
|---|---|---|---|---|---|
| 10 | 60 | 100 + 45 | fuse | `RECOMPUTE_ERROR` `invalid_result`, rolled back | 5.2 s |
| 15 | 90 | 225 + 105 | fuse | `RECOMPUTE_ERROR` `invalid_result`, rolled back | 37.7 s |
| 20 | 120 | 400 + 190 | fuse | no answer | > 130 s (killed) |
| 25 | 150 | 625 + 300 | fuse | no answer | > 300 s (killed) |
| 25 | 150 | 625 + 300 | cut | `RECOMPUTE_ERROR` `invalid_result`, rolled back | 7.9 s |
| 30 | 180 | 900 + 0, 90 degrees (shipped fixture) | fuse | OK | 7.6 s |

Output for n = 25 (`p12a.out`):

```
[guard passed; n/op/angle/faces/inside f2] [25, "fuse", 2.0, 150, 300]
[call starts at] "02:29:17"
exit=124   (timeout 300 s, 02:34:16)
```

Every timing test in `PartBooleanCostTest` uses perpendicular crossings (cut and common), so the suite does not see this. The pair count does not bound the cost when the intersection curves are long (grazing crossings). If the leader decides this belongs to the decision-52 class (cost not bounded by counts), record it there with this probe; as the bar reads now (Q11, other than the comb faces), it breaks the row.

### RT-3 — medium — Q4: a normal cut is refused as too complex because rotated solids have loose bounding boxes

Where: `src/freecad_buddy/usecases/features.py:4217` and `:4226`

```python
    boxes = [solid.BoundBox for solid in shape.Solids]
    ...
            if b.YMin <= a.YMax and a.YMin <= b.YMax and b.ZMin <= a.ZMax and a.ZMin <= b.ZMax:
```

Probe `p9.py 60`: a plate cut by one tool compound of 60 disjoint slanted slots (boxes 2 x 200 x 20, rotated 45 degrees about z, 6 mm apart, smallest gap 2.243 mm). This is a louvre or vent pattern, for example a Draft array of one rotated slot.

```
[n, faces, min gap between slots, bbox pairs] [60, 366, 2.243, 1104]
[tool] {"raised": "PartToolRefusal", "code": "part_boolean.too_complex", "msg": "the inputs hold 366 faces (limit 3000), 60 solid pairs across the inputs and at least 941 overlapping inside one input ... the kernel call would hold the bridge for tens of seconds or more ..."}
[raw Part::Cut] [0.81, 390294.3725152292, 61, true, ["Up-to-date"]]
[analytic] 390294.3725152286
```

No solid touches another, but each slot's axis-aligned box overlaps those of about 18 neighbours. The same cut takes 0.81 s in FreeCAD and gives the analytic volume. The refusal message says "tens of seconds or more", which is false for this input. Splitting the tool does not help: the cross-input term counts every pair of solids in two tools. The only route is several boolean calls. Fix direction: confirm a bbox hit with a cheap exact test (for example `distToShape` > 0 on the pair, or an oriented box) before counting it, within a time cap.

### RT-4 — low — Q9: a very large finite angle gives an identity rotation with no error

Where: shared 13-16 parser `_placement_value`, used by `feature_part_primitive`.

Probe `p4.py`, box 10 x 20 x 30 with `rotation {axis [0, 0, 1], angle 1e20 deg}`:

```
[placement angle 1e20] ["OK", "Placement [Pos=(0,0,0), Yaw-Pitch-Roll=(0,0,0)]", ["BoundBox", "(0,", "0,", "0,", "10,", "20,", "30)"]]
```

1e20 is exact in a double and `1e20 % 360` is 280, so the box should turn 280 degrees. The parser bounds the axis length (1e-100 to 1e100) but not the angle; above about 1e15 degrees the angle has no precision left and the stored rotation is arbitrary. The input is absurd, so low. Fix direction: bound `angle` (for example to plus or minus 1e6 degrees) or reduce it modulo 360 before the conversion.

### RT-5 — low — Q10: the tool description does not name the stale-input refusal

`src/freecad_buddy/hosts/tool_catalog.py` `feature_part_boolean` description lists `part_boolean.untrusted_shape` as "reversed, invalid, non-solid input". The code also uses that code for an input in a `Touched`/`Invalid`/`Error` state ("recompute the document first", `features.py:4252-4258`). An agent that reads the description cannot tell that a recompute fixes this refusal. Static read only; no probe needed for the text.

## Not reproduced (checked, no defect)

Item 1, the last fix batch (`ae2b07c3`, `deaa2b25`):
- Nested compounds: `Compound([Compound([c1, Compound([c2])]), c3])` gives 3 solids and 1 overlapping pair (`p1.py`).
- Boxes that only touch (`b.XMin == a.XMax`) count as overlapping: 1. This is conservative, not a defect.
- Solids that share one x range and are apart in y: 50-sphere column counts 0.
- Cap 0: returns 1 on the first overlap; `budget = 1000 - across` cannot go negative because the pass runs only when `across <= 1000`.
- Quadratic pass cost: any input that passes the cross-input term holds at most about 1,000 solids (two inputs minimum), so the pass stays below 1,000^2 / 2 bbox tests. No slow case found.

Item 2, the quality-bar rows:
- Q3/Q5 semantics with compounds, all analytic (`p1.py`): common with a compound tool 400 (400); MultiCommon with a compound tool 400 (400); common with a compound base 200 (200); MultiCommon with a compound base 100 (100); several-tool cut with a compound tool 300 (300); cut by a compound tool 600 (600); fuse of a compound base 700 (700).
- `App::Link` as a tool: cut 500 (500). `Part::Compound` as a tool: empty result, `part_boolean.empty_result`, rolled back (`p5.py`).
- Q6 undo and redo of a several-tool cut (`p5.py`): undo removes `Result` and `Result_tools` and restores Visibility true on all three inputs; redo brings both back, inputs hidden, volume 1400 (1400). Undo stack holds one step `buddy: part cut Result`.
- Rollback leaves no pending transaction: after an empty common, `HasPendingTransaction` false, `UndoNames` [], inputs visible and `Up-to-date`.
- Name collisions: Label `Result_tools` on another object does not block a fuse (no intermediate is made, correct); Label `Result001` does not block `Result`.
- A reopened document (`p10.py`): all objects `Up-to-date` after `document_open`; cut and a fuse with a Body both OK. No false stale refusal.
- Tangent cylinders on a plate, 30 and 100 cylinders: 0.4 s and 1.2 s, volumes analytic (`p6.py`).
- Crossing cylinders at 5 degrees, 20 x 20: common 5.8 s, cut 7.0 s (`p11.py`).
- Primitives at sizes FreeCAD cannot build (box 1e-9, 1e200, 1e300; sphere, torus, cylinder 1e-9): `RECOMPUTE_ERROR` `mutation.recompute_error` with a proven rollback, no object left (`p4.py`). This is the round-1 rejected "tiny-size tolerance" item, not re-reported. Cone with equal radii: valid, volume 785.398 (analytic). `-0.0` refused; `True` as a value and `cm` unit refused with a plain error.
- Placement axis 1e-200 and 1e308: refused by the 13-16 parser. Base only, empty placement: correct bboxes.

Item 3, test doubles (`tests/infc/test_feature_part.py`):
- The spies (`transaction.run_mutation` at `:549`, `features._placement_value` at `:186`, `features._require_partdesign` at `:284` and `:1295`, `features._overlapping_solid_pairs` at `:1060`) wrap or replace a function only to record the call; each test that needs the real behaviour calls the original. The limit overrides (`_PART_BOOLEAN_MAX_FACES`, `_PART_BOOLEAN_MAX_SOLID_PAIRS`) run the real code on real shapes. All fixtures are real FreeCAD objects. No fake skips a real check.
- Coverage gap (feeds RT-1 and RT-2, not a separate finding): no test has a stale dependency of an input, and no cost test has a fuse or a non-perpendicular crossing.

## Environment notes

- One probe (`p3.py`, 100 x 100 families on a plate tangent to the cylinders) grew to 11.7 GB and was stopped by `Stop-Process` at about 190 s; that geometry is not used as evidence. Every other probe ended at its own `timeout`. No `freecadcmd.exe` started by this agent is left running.
- Timings were taken on the shared host while `verifier-13-17` ran its own `freecadcmd` tests, so they carry noise; the over-limit results are several times the 60 s bound.
