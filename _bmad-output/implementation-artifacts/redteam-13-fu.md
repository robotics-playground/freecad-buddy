# Story 13-fu: red team report

Target: `story/13-followups`, diff 3df33fbd...8049378d (fix batch 65acb437...8049378d first). Read at 8049378d from a detached scratch worktree (removed after the run).
Method: `bmad-code-review` adversarial lens, run by one agent; every claim below has a probe or test run on host FreeCAD 1.1.4 (`freecadcmd.exe`, private `-u`/`-s` cfg, private `FREECAD_USER_HOME`). Container not used.

Probe folder: `C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\17c8e5ee-89aa-4e27-ba05-1fe1774e804a\scratchpad\redteam-13-fu\`. Shell wrappers there: `run2.sh <probe> <src dir>` runs one probe against a `src` tree; `run3.sh` runs named infc tests with `RT_TESTS` and an optional constant mutant `RT_MUTANT=<module>:<constant>:<value>`. To run again, re-create the head tree first: `git -C D:/Work/Personal/Sources/freecad-buddy-wt-13-fu worktree add --detach <scratch>/redteam-13-fu/copy 8049378d`. `src_base/` is the same tree with `queries.py` from 3df33fbd (the base, no fuse check).

## Reproduced

| Id | Severity | Q | Where | Summary |
| --- | --- | --- | --- | --- |
| RT-1 | high (introduced by this Story) | Q2, T-2 | `src/freecad_buddy/usecases/queries.py:856`, `:861-877` | A solid fully inside another reads `common_volume` 0, `boolean_failed` false |
| RT-2 | medium | Q2, Q5 | `queries.py:699-700`, `tool_catalog.py:1679`, `tool-contracts.md:90`, design §3.2.3 | Stated limit "overlap below 1e-12 reads as touching" is wrong: overlaps up to about 1.5e-12 read as touching |
| RT-3 | medium (test, false pass) | Q2 | `tests/infc/test_query_tools.py:679` | The Inner/Outer fake fuse "loses the inner volume"; the real kernel does the opposite on the nested case of RT-1 |
| RT-4 | medium (test double, per brief rule) | Q2 | `tests/infc/test_query_tools.py:567` | Pre-existing `RaisingShape` fake has no `fuse()`; test passes only because the new `except Exception` swallows `AttributeError` |
| RT-5 | medium (pre-existing, 13-7 code, outside the Story diff) | Q3 | `queries.py:708-713` | One touching pair at face product 7,200 (limit 150,000) takes 108 s in one call, above the 60 s budget |
| RT-6 | low | Q2 | `test_query_tools.py:657`, `:813` | Tolerance mutant 3e-12 (3x looser) keeps all 44 interference tests green |
| RT-7 | low | Q9 | `tests/uat/testcases/TC-17-query-interference-touching.md:28-29` | New setup step has a raw line break inside the `script_exec` code string |

### RT-1 (high): a solid inside another reads as touching through the fuse cross-check

Mechanism. Two spheres, the inner one inside the outer and internally tangent: radius 10 at the origin, radius 10 + 1e-6 centred at (1e-6, 0, 0). The surfaces are 0 to 2e-6 mm apart. `common` is empty (OCC misclassifies the nested pair). `distToShape` gives 1.7e-8 mm, which is at or below the contact distance 1e-7, so the new fuse cross-check runs. The fuse makes the same misclassification: it returns both solids unmerged (2 solids, valid), with volume exactly equal to the sum. `_fuse_proves_touching` then returns True. The real overlap is the whole inner sphere (4,188.79 mm^3; 4,188,790 mm^3 for radius 100). Before the Story the same pair gave `boolean_failed` true. So the Story turns a safe "unmeasured" into a false "no overlap". This is the failure T-2 forbids ("an empty result must never read as no overlap").

Code (queries.py:856 and :869-875):

```python
    if distance is not None and _fuse_proves_touching(shape_a, shape_b):
        return 0.0, distance, False
...
        fused = shape_a.fuse(shape_b)
        total = float(shape_a.Volume) + float(shape_b.Volume)
        gap = total - float(fused.Volume)
        return (
            bool(fused.isValid())
            and math.isfinite(gap)
            and abs(gap) <= _TOUCH_VOLUME_REL_TOL * total
```

The fuse does not check that the result merged anything. A fuse that returns the two inputs side by side has zero gap and passes.

Reproduction: `probes/rt1_nested_sphere_e2e.py`, through `query_interference` with a real document.
Command: `sh run2.sh rt1_nested_sphere_e2e.py <scratch>/redteam-13-fu/copy/src` (head) and `... src_base` (base).

Output at head 8049378d:

```
status: OK
text: 2 pair(s), 0 overlapping, 0 boolean failed.
{'a': 'Inner10', 'b': 'Outer10', 'common_volume': {'value': 0.0, 'unit': 'mm^3'}, 'min_distance': {'value': 1.6990694870391636e-08, 'unit': 'mm'}, 'boolean_failed': False} | inner volume 4188.79 | analytic: inner inside outer: True | fuse solids: 2
{'a': 'Inner100', 'b': 'Outer100', 'common_volume': {'value': 0.0, 'unit': 'mm^3'}, 'min_distance': {'value': 8.495334744997274e-09, 'unit': 'mm'}, 'boolean_failed': False} | inner volume 4188790.205 | analytic: inner inside outer: True | fuse solids: 2
fingerprint equal: True objects: True undo: True
```

Output at base 3df33fbd (same probe, `src_base`):

```
text: 2 pair(s), 0 overlapping, 2 boolean failed.
{'a': 'Inner10', 'b': 'Outer10', 'common_volume': None, 'min_distance': {'value': 1.6990694870391636e-08, ...}, 'boolean_failed': True}
{'a': 'Inner100', 'b': 'Outer100', 'common_volume': None, 'min_distance': {'value': 8.495334744997274e-09, ...}, 'boolean_failed': True}
```

Range (probe `probes/p4_nested_tangent.py`, spheres radius 10): the radius gap `dr` from 5e-7 to 1e-6 mm with the centre offset 0.9 to 1.0 times `dr` reads as touching through the fuse. `dr` 3e-7 and 2e-6 and above give a correct non-empty `common`. Probe `probes/p5_nested_general.py`: same false zero for radius 100; a torus inside a torus with minor radius +5e-7 also gives a false zero, through the older positive-distance path (see the next paragraph).

Same root cause on the pre-existing path, not new: with the centres equal (no tangency) the distance is 5e-7 to 1e-6 mm, above 1e-7, and the code returns `(0.0, distance, False)` at `queries.py:852-853` without any fuse. For example, sphere 10 inside concentric sphere 10 + 1e-6 gives `(0.0, 9.999999961463139e-07, False)` at head and at base. So T-2 is already breakable at a positive distance below about 1e-6 mm. That path is outside this Story. The Story adds the contact band to it.

Fix direction (not applied): require the fuse to merge, for example `len(fused.Solids)` below the input solid count when the shapes are in contact, or a classification check (`isInside` of a point of each solid in the other). A fix also needs a decision for the positive-distance path below about 1e-6 mm.

### RT-2 (medium): the stated tolerance is wrong by a factor of 1.5

The fuse of a sub-tolerance box overlap loses only 2/3 of the overlap volume. The code compares the fuse gap, not the overlap, with 1e-12 of the sum. So overlaps up to about 1.5e-12 of the sum read as touching. Code comment `queries.py:699`, catalog `tool_catalog.py:1679`, T-2 `tool-contracts.md:90`, design §3.2.3 and the skill references all state "less than 1e-12". This breaks the number in Q2 ("never read as no overlap above the stated tolerance (1e-12 relative)") by a factor of 1.5. The volumes involved are very small (3e-3 mm^3 for boxes of 1,000 mm). The builder's own note confirms the factor: 1e-7 mm depth on 100 mm boxes is 5e-10 relative overlap and gives a 3.3e-10 gap.

Probe `probes/rt2_tolerance_factor.py`, command `sh run2.sh rt2_tolerance_factor.py <copy>/src`. Output (trimmed):

```
size 100 depth 2.8e-10 true overlap 2.8e-06 mm3 = 1.4 x limit | common empty=True fuse gap/overlap=0.667 -> (0.0, 2.799964704536251e-10, False) READS TOUCHING
size 100 depth 2.9e-10 true overlap 2.9e-06 mm3 = 1.45 x limit | common empty=True fuse gap/overlap=0.667 -> (0.0, 2.900009121731273e-10, False) READS TOUCHING
size 100 depth 3.2e-10 true overlap 3.2e-06 mm3 = 1.6 x limit | common empty=True fuse gap/overlap=0.667 -> (None, 3.200000264769187e-10, True) flagged
size 1000 depth 2.9e-09 true overlap 0.0029 mm3 = 1.45 x limit | common empty=True fuse gap/overlap=0.667 -> (0.0, 0.0, False) READS TOUCHING
size 1000 depth 3.2e-09 true overlap 0.0032 mm3 = 1.6 x limit | common empty=True fuse gap/overlap=0.667 -> (None, 0.0, True) flagged
```

Side note from the same output: for 100 mm boxes that overlap, `min_distance` is positive (2.8e-10 mm, equal to the depth), not 0 as T-2 says ("0 when the shapes touch or overlap"). The value is far below 1e-7, so it does not change the result.

Fix direction: state the limit as 1.5e-12 (3e-3 mm^3 for 1,000 mm boxes), or set the constant to 2/3e-12. The skill recipe `a.Volume + b.Volume - f.Volume` "is the overlap volume" (verification-kit.md, measuring-clearance-and-sections.md) also reads 2/3 of a sub-tolerance overlap.

### RT-3 (medium, test false pass): the Inner/Outer fake contradicts the real kernel

`test_Should_flag_a_failed_boolean_When_the_fuse_loses_the_volume_of_a_solid_inside_another` (`test_query_tools.py:679`) fakes `common` raising and a fuse whose volume is the outer volume (27.0 against a sum of 35.0). It is the only test for "a solid inside another" through the fuse. The real kernel, on a nested pair where `common` is empty (RT-1), returns both solids unmerged with the full summed volume. The fake encodes the behaviour the design relies on. The real `Part.Shape.fuse` does not give that behaviour in the one case where the cross-check runs, so the test passes while the product is wrong.

Probe `probes/rt3_fake_vs_real.py`:

```
real nested pair: common volume 0.0 | fuse valid True solids 2 volume 8377.581666209968 | inner+outer 8377.58166620997 | outer alone 4188.791461423578
fake (test_Should_flag_a_failed_boolean_When_the_fuse_loses_the_volume_of_a_solid_inside_another): fuse volume 27.0 = outer alone, sum 35.0
```

Fix: a real-geometry test with the RT-1 spheres (expect `boolean_failed` true). It fails at 8049378d.

### RT-4 (medium per the brief rule, low impact): fake without `fuse()`

`test_Should_flag_a_failed_boolean_When_common_raises_and_the_distance_is_zero` (`test_query_tools.py:567`, pre-existing) uses `RaisingShape`, which has no `fuse` method. Real `Part.Shape` always has one. After this Story the result depends on the fuse, and the test passes only because `_fuse_proves_touching` catches the `AttributeError` (`queries.py:876`). The test name now also states a rule that is no longer true (common raising at distance 0 can read 0 when the fuse proves contact). `test_Should_flag_a_failed_boolean_When_the_fuse_raises_or_has_no_finite_volume` covers the fuse-raises case on purpose, so the coverage loss is small.

Probe `probes/rt4_fake_without_fuse.py`:

```
RaisingShape has fuse: False
fuse call raises: AttributeError 'RaisingShape' object has no attribute 'fuse'
_fuse_proves_touching -> False
_measure_interference -> (None, 0.0, True)
```

Fix: give the fake a `fuse` that raises, or rename the test so it states the fuse condition.

### RT-5 (medium, pre-existing): one pair far below the face-product limit exceeds the 60 s budget

A 200 x 1 x 1 lid on a row of 200 unit boxes that it touches: faces 6 x 1,200 = 7,200, about 5% of the 150,000 limit. `distToShape` on the many contact solutions takes about 100 s. The call deadline is checked only between pairs, so one pair runs 108 s while it holds the interpreter lock. The comment at `queries.py:709-711` says a pair at the limit takes about 12 s. The new comment at `:712-713` says the fuse adds little against 19 s of `distToShape`. The fuse is indeed cheap here (0.26 s at 100 boxes, 0.57 s at 200), so the Story does not cause this. The cost bound that Q3 depends on does not hold. Same cost at base (the pair goes through `distToShape` before and after the Story).

Probe `probes/rt5_pair_cost.py`, command `timeout 590 sh run2.sh rt5_pair_cost.py <copy>/src`:

```
faces 6 x 1200 = 7200 limit 150000 deadline 40.0
one pair, whole call 108.4 s OK [{'a': 'Lid', 'b': 'Row', 'common_volume': {'value': 0.0, 'unit': 'mm^3'}, 'min_distance': {'value': 0.0, 'unit': 'mm'}, 'boolean_failed': False}]
```

Step timings (`probes/p6_cost.py`, log `p6.log`): 100 boxes: common 0.08 s, distToShape 12.1 s, fuse 0.26 s. 200 boxes: common 0.34 s, distToShape 100.4 s, fuse 0.57 s. 400 boxes: `distToShape` did not finish within the 500 s probe limit.

Recommendation: a deferred entry for 13-7 (decision 28). Face product is not a bound for `distToShape` when there are many contacts.

### RT-6 (low): the tolerance is pinned only within a factor of 3.4

Runner `probes/rt_mutant_runner.py` through `run3.sh`, `RT_TESTS=infc.test_query_tools.QueryInterferenceTest`:

```
== mutant []                                      RESULT run=44 failures=0 errors=0
== mutant [queries:_TOUCH_VOLUME_REL_TOL:3e-12]   RESULT run=44 failures=0 errors=0
== mutant [queries:_TOUCH_VOLUME_REL_TOL:3.4e-12] RESULT run=44 failures=2 errors=0
```

The real-geometry "just above" cases (`:657`) sit at 5e-12 relative overlap (3.3e-12 fuse gap). The fake gap test (`:813`) scales with the constant, so it follows any mutant.

### RT-7 (low): TC-17 setup step breaks the code string

`TC-17-query-interference-touching.md:28-29` at 8049378d:

```
**And** the `Big1/Big2` overlap leaves `common` empty — verify: `mcp script_exec { doc: <handle>, code: "c = doc.Big1.Shape.common(doc.Big2.Shape)
result = c.isNull() or not c.Volume" }` returns `true`
```

Every other step writes `\n` inside the code string. Here the line break is a real newline inside a JSON string (invalid JSON if copied as is), and the inline code span breaks across two lines.

## Checked and holding

- Q4 read-only: RT-1 probe also checks a fresh fingerprint digest, the object count and `UndoCount` before and after the call: `fingerprint equal: True objects: True undo: True`.
- Q6 sweep limit: `RT_TESTS` = the two new SweepTest boundary tests. Mutant 2999: 2 red. Mutant 10000: 1 red. Mutant 3001: 1 red. No mutant: 2 green. The tests use the real constant and the real 3,000/3,001-line spines. The `>` comparison is pinned by the older test `test_Should_accept_a_sweep_at_the_cost_limit_and_refuse_one_below_it`.
- Large shape tolerance (`fixTolerance` 1e-3 to 0.5 on one or both boxes, overlap up to 4,500 mm^3 with empty `common`): all flagged `boolean_failed` true (`probes/p1_tolerance.py`).
- Tangent and slightly overlapping cylinders and spheres, NURBS copies of boxes, cylinders and spheres, coplanar faces, nested boxes and cylinders, a box inside a sphere and a torus inside a sphere: `common` non-empty or a correct touch (`probes/p2_geom.py`, `p3_nested.py`, `p5_nested_general.py`).
- Q3 order: the fuse runs only when the distance is not None, after the face-product check and inside the per-pair loop that the deadline check precedes (`queries.py:856`, `:943-955`).

## Not reproduced

- The fuse doubles the boolean cost on pairs where `common` dominates (measured fuse/common ratio 1.7x to 3x on touching box rows); no pair found where this alone passes the 60 s budget.
- A self-intersecting or compound-internal overlap through the fuse path: documented non-goal, not probed further.
- Large coordinate offsets with an overlap that the fuse merges into a gap below 1e-12: not found; offsets were covered only by the builder's measurements.
- TC-17 runs `common` and `fuse` on live document shapes in setup, which clears a BREP flag (design §3.2.3); this could change the fresh digest if the "before" digest is read before those steps. The step order reads it after, so not a defect; the container was not used to check it.

## Verdict

FAIL. RT-1 is a reproduced high introduced by this Story: a fully nested solid (4,188.79 mm^3 and 4,188,790 mm^3 overlap) reads `common_volume` 0, `boolean_failed` false through the new fuse cross-check, where the base read `boolean_failed` true. RT-2 is a product medium (the stated limit is wrong by 1.5x). RT-5 is a pre-existing product medium outside the Story diff.
