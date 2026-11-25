# Story 13-18: red team report

Head attacked: `d8968a1e` (merge of feat over `8a3cf206`), detached worktree. Host FreeCAD 1.1.4 `freecadcmd.exe` with private `-u`/`-s` cfg and a temp `FREECAD_USER_HOME`; `features.__file__` asserted to load from the red-team worktree.

Probe scripts and runner: `C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\50958ed8-8fcb-4d26-a32d-c7025b2780ae\scratchpad\redteam-13-18\` (`rt.py` harness, `run.sh <probe> [timeout]`, `pN_*.py`). Run from Git Bash in that folder: `RT_...=... bash run.sh <probe>.py <seconds>`. Probes call `features.feature_loft` / `feature_sweep` through a `DocumentRegistry` with auto-approve on, as the infc tests do.

Timing note: a verifier `freecadcmd` ran on the same host during part of the loft timings. The direct-recompute timings (no tool) agree with the tool timings, so the load did not change the conclusion.

## Reproduced

| Id | Severity | Q | Where | Finding |
| --- | --- | --- | --- | --- |
| RT-1 | high | Q6 | `features.py:843`, `features.py:933-934` | Loft cost is quadratic in edges per section; the guard counts edges linearly. Calls far under 8,000 units hold the interpreter for minutes. |
| RT-2 | high | Q5 | `feature_sweep` (`features.py`, no `recompute_check`); `transaction.py:291-293`; `verify.py:280` | A sweep with a degenerate or self-intersecting result returns `OK`: zero volume, BOP self-intersection, `is_valid: false`, and a subtractive sweep that leaves the Body at volume 0. |
| RT-3 | medium | Q1 | `features.py:984` | `feature_loft(subtractive=true)` in an empty Body adds material and returns `OK`. |
| RT-4 | medium | Q6 | `features.py:1058-1085` | A thread helix of 120 turns or more is refused as `sweep.degenerate_spine`; FreeCAD builds it valid in 0.85 s. |
| RT-5 | low | Q4 | `features.py:1039` | An unresolvable spine selector (`Edge9`, `Nonsense`) is refused without `detail.code`. |
| RT-6 | low | none | `feature_loft`, `feature_sweep` | A subtractive loft or sweep that misses the solid returns `OK` with the Body volume unchanged. |

### RT-1 (high, Q6): loft cost grows with the square of edges per section

`_loft_cost` adds edges (`features.py:933-934`):

```python
def _loft_cost(shapes: list[object]) -> int:
    return sum(_edge_poles(edge) or 1 for shape in shapes for edge in shape.Edges)
```

The measurements beside `_LOFT_MAX_COST = 8000` (`features.py:843`) use many sections of at most 300 edges. OCC `ThruSections` cost grows with the square of edges per section, and more when the edge counts differ.

Reproduction (`p5_loft_cost.py`; `big` = two N-gons 20 mm apart, `mismatch` = circle to N-gon; sketches unconstrained, so the call ends `SPEC_FAILED` after the OCC build):

```
RT_KIND=big      RT_N=1 RT_P=3999 bash run.sh p5_loft_cost.py 1200
RT_KIND=mismatch RT_N=1 RT_P=4000 bash run.sh p5_loft_cost.py 1200
RT_SKIPTOOL=1 RT_DIRECT=1 RT_KIND=<kind> RT_N=1 RT_P=<n> bash run.sh p5_loft_cost.py 300   # OCC only
```

Output:

```
cost 7998 limit 8000 edges/section [3999, 3999]
  feature_loft: status=SPEC_FAILED code=mutation.spec_failed in 110.85s
cost 4001 limit 8000 edges/section [1, 4000]
  feature_loft: status=SPEC_FAILED code=mutation.spec_failed in 317.31s
direct AdditiveLoft recompute (no tool):
  mismatch 1,000 -> 8.32s   mismatch 2,000 -> 47.62s
  big 2x1,000   -> 6.25s    big 2x2,000   -> 23.72s
```

A call at half the limit holds the interpreter for 317 s. The 120 s marshal timeout cannot stop it (L2). Extrapolated from the measured slope, a circle to a 7,999-gon (7,999 units, accepted) needs more than 20 minutes. A loft with fully constrained sketches spends the same OCC time and then returns `OK`.

### RT-2 (high, Q5): degenerate and self-intersecting sweeps return `OK`

Spec, Always clause (`spec-13-18-loft-sweep.md:31`): "A recompute that gives no solid (open sections, a self-intersecting sweep) returns `RECOMPUTE_ERROR` with proven rollback". Post-verify calls `verify_shape` with no checks (`transaction.py:291-293`), which marks every measured fact as passed (`verify.py:280`: `{"id": "shape.valid", "measured": bool(shape.isValid()), "passed": True}`). `feature_sweep` passes no `recompute_check`. No test covers a self-intersecting sweep. The only no-solid test is an open profile.

Reproduction: `p2_reversal_variants.py`, `p4_tangent_profile.py`, `p8_subtractive_empty.py`, `p9_degenerate.py`. All sketches are fully constrained (`Block`).

```
spine in the profile plane (circle r=3 in XY, line along X):
  feature_sweep: status=OK ... vol=0.0 faces=3
  (BSpline variant in the plane: status=OK vol=-1.412246872442233e-13)
spine that runs up 10 mm and back down (two line edges, Part::Feature or sketch):
  feature_sweep: status=OK ... vol=0.0 faces=2
  check: BOP check found ... Error in Face: BOPAlgo SelfIntersect
spine up 10 mm then back 5 mm:
  feature_sweep: status=OK ... vol=15.70796326794896   (a 5 mm cylinder, not the 10 mm swept path)
subtractive sweep, spine in the profile plane, on a 2,000 mm3 pad:
  feature_pad: status=OK ... vol=1999.9999999999995
  feature_sweep: status=OK ... vol=0.0 faces=3
  Body volume 0.0
profile r=10 along an arc of radius 2:
  feature_sweep: status=OK ... vol=1884.9555921538754   BOP: BOPAlgo SelfIntersect
  then the same with mode=frenet on top:
  feature_sweep: status=OK ... solids=2 valid=False vol=4239.1967651705445   BOP: Unorientable shape
```

The `sweep.degenerate_spine` guard samples only inside BSpline edges. A wire that reverses at a vertex passes untouched. The design doc says that case "did not hang", but its result is a zero-volume shape reported as `OK`. The subtractive case removes all material from the Body and reports `OK`.

### RT-3 (medium, Q1): subtractive loft in an empty Body adds material

`FeatureLoft.cpp:329-337` writes the loft solid as the feature shape when there is no base, for any add/sub type. `FeaturePipe` refuses the same case ("Pipe: There is nothing to subtract from"). The tool does not refuse a subtractive loft with no base.

Reproduction: `bash run.sh p8_subtractive_empty.py 300`

```
== subtractive loft, empty Body
  feature_loft: status=OK ... vol=4666.666666666666
   TypeId PartDesign::SubtractiveLoft Body.Tip Cut Body volume 4666.666666666666 solids 1
== subtractive sweep, empty Body (comparison)
  feature_sweep: status=RECOMPUTE_ERROR code=mutation.recompute_error ... 'Cut: Pipe: There is nothing to subtract from'
== feature_pocket, empty Body (comparison)
  feature_pocket: status=OK ... vol=499.9999999999999
```

The tool docstring says "`subtractive` removes the lofted solid from the Body". The result adds 4,666.67 mm3. `feature_pocket` shows the same behaviour; that is pre-existing and outside this Story.

### RT-4 (medium, Q6): a long thread helix is refused as doubling back

`_check_spine_tangents` takes 400 samples per edge (`_SPINE_TANGENT_SAMPLES`) regardless of how far the edge turns. `Part::Helix` is one BSpline edge. At about 100 turns or more, two samples are a quarter turn or more apart, the dot product goes negative, and the call is refused with a false reason.

Reproduction: `bash run.sh p12_thread_helix.py 900` (Part::Helix pitch 1 mm, radius 5 mm, profile circle r=0.3, `mode="frenet"`)

```
height 100: helix edges 1 poles [3395]  feature_sweep: status=OK ... in 0.91s
height 120: helix edges 1 poles [3330]  feature_sweep: RAISED LoftSweepRefusal code=sweep.degenerate_spine ...
   FreeCAD direct: valid=True volume=992.142 in 0.85s
height 150: helix edges 1 poles [7165]  feature_sweep: RAISED LoftSweepRefusal code=sweep.degenerate_spine ...
   FreeCAD direct: valid=True volume=1275.480 in 0.91s
```

A 120 mm M10-style thread is a normal sweep. The message tells the agent that the spine "doubles back on itself", which is false. Also seen: `Part.makeHelix(5, 2500, 10)` (500 turns, 392 poles, cost 40) is refused the same way.

### RT-5 (low, Q4): unresolvable spine selector carries no code

`features.py:1039`: `raise ValidationError(f"unresolvable spine selector {subelement!r}: {exc}") from exc`.

Reproduction: `bash run.sh p11_codes.py 120`

```
-- edge index out of range
  feature_sweep: RAISED ValidationError code=None ...: unresolvable spine selector 'Edge9': Shape index 9 out of bound 1
-- garbage subelement
  feature_sweep: RAISED ValidationError code=None ...: unresolvable spine selector 'Nonsense': Invalid shape name Nonsense
-- vertex
  feature_sweep: RAISED LoftSweepRefusal code=sweep.invalid_spine ...
```

Q4 lists "bad spine" among the coded refusals. A `Vertex1` selector gets `sweep.invalid_spine`; an `Edge9` selector gets no code.

### RT-6 (low): subtractive call that misses the solid returns `OK`

Reproduction: `bash run.sh p7_scope_rollback.py 300`, cases g and h.

```
== g subtractive sweep that misses the solid
  feature_sweep: status=OK ... vol=499.9999999999999
   body volume before 499.9999999999999 after 499.9999999999999
== h subtractive loft that misses the solid
  feature_loft: status=OK ... vol=499.9999999999999
   body volume before 499.9999999999999 after 499.9999999999999
```

The call records an undo step (a new feature), so L6 does not apply. The caller gets no signal that nothing was removed.

## Not reproduced

| Attack | Result |
| --- | --- |
| Hang through a fold hidden between two of the 400 tangent samples (2,000-pole BSpline on a line, fold at pole 1000, `p3_hidden_fold.py`) | The check is evaded: a dense scan finds `dot -1.0` at parameters 998.8 and 1000.19, and `_check_spine_tangents` accepts. OCC fails in 0.07 s (`BRep_API: command not done`), `RECOMPUTE_ERROR`, `rolled_back=True`. No hang. Low. |
| Loft BSpline sections with different knot vectors (21 periodic BSplines of 380 poles, 7,980 units) | 2.13 s; the same sections with equal knots 0.60 s. Inside the budget. |
| Sweep at 2,000 units: 2,000-edge spine polygon 3.86 s; 2,000-edge profile on a circle 2.84 s | Inside the budget. |
| Frenet sweep along a 100-turn `Part::Helix` (3,395 poles) | `OK` in 0.91 s. |
| Profile 100 mm from the spine start | `OK`, valid, BOP clean (FreeCAD does not move the profile; this is FreeCAD's documented behaviour). |
| Loft twist: square to a square rotated 45 (ruled), 90 and 180 degrees (smooth); flipped section normal | All `OK`, valid, BOP clean. |
| Coplanar sections | `RECOMPUTE_ERROR` ("Segments of a Loft/Pad do not have sufficient separation"), rolled back. |
| Sections, profile or spine from another Body | Accepted with FreeCAD's "go out of the allowed scope" warning. `feature_pad` does the same (pre-existing), and the spec triage judged "Spine outside the Body not refused" as false. Not re-reported. |
| Spine on an edge of the same Body's Tip, subtractive; undo; FreeCAD redo | `OK`, undo `OK`, redo restores the feature, no invalid object. |
| L14: subtractive sweep refused at recompute, then `feature_pad`, then `document_undo` | Covered by the existing test. Loft (`p7` case f): the call commits, then `feature_pad`, then `document_undo` returns `OK` and removes only the pad. |
| Merge `d8968a1e` keeps 13-10 and 13-11 behaviour | `git diff 57e9bdac d8968a1e -- src tests` removes one line only (a test count). `infc.test_feature_expressions` + `infc.test_object_delete` on the worktree: `Ran 114 tests ... OK`. |

## Verdict

FAIL. RT-1 breaks Q6: an accepted loft holds the interpreter for 111 s at the limit and 317 s at half of it. RT-2 breaks Q5 and the spec's Always clause: self-intersecting and zero-volume sweeps return `OK`.
