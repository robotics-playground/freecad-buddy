# Story 13-15: red team report

Scope: whole Story diff `538db0be...5115b2ac` (branch `story/13-15-tnp-expected-reattachment`), last fix batch `a835c153...5115b2ac` first. Read at `5115b2ac` from a detached copy. Base comparison from a detached copy of `538db0be`. Host `freecadcmd.exe` (FreeCAD 1.1) with private `-u`/`-s` cfg and a private `FREECAD_USER_HOME`. Container not used.

Probe folder: `C:/Users/thuan/AppData/Local/Temp/claude/3d3814eab912640f/17c8e5ee-89aa-4e27-ba05-1fe1774e804a/scratchpad/redteam-13-15/probes/` (below: `<probes>`). Runner: `<probes>/../run.sh <probe>` (freecadcmd with private cfg). `boot.py` imports `tnp_guard` from the copy at `5115b2ac`, or from `RT_SRC` when set (base copy at `538db0be`), and asserts which copy was imported.

## Verdict

**FAIL.** One reproduced high: the new excuse grades a real re-point CLEAN and lets the op commit.

## Reproduced

### RT-1 — high — a real re-point is excused (positional `;:M<k>` split-piece names)

- Q row: Q5/Q6 and the Story contract (decision 40 (2), AC2: a real re-point must stay `REPOINTED`). Lead rule: "a real re-point excused is high".
- Code: `src/freecad_buddy/usecases/tnp_guard.py:235-247` (`_follows_support`: `same_element` = equal mapped name and equal history source) and `tnp_guard.py:785` (the excuse applied in `_grade_entry`).
- Mechanism: when one face is split into several pieces, FreeCAD 1.1 names the pieces with a positional counter, `;:M`, `;:M2`, `;:M3`, ... on the same source element. The counter counts pieces in result order, not by role. An edit that changes the piece count shifts every counter, so the same mapped name and the same history source now name a different piece. When the edit also grows the support box in the same direction, the jump lies inside the support's per-axis travel and `_follows_support` excuses it. Layer 2 then passes it, because both pieces have the same history source.
- Fixture (realistic parametric design): plate Pad from a sketch with named length `L = 40`; a 2 mm groove Pocket; a LinearPattern of the groove with `Length = L - 12 mm` and `Occurrences = floor(L / 13 mm)` (expressions). A datum point (`PartDesign::Point`, MapMode `CenterOfMass`) is attached to the back top edge of strip 1 (the strip between groove 1 and groove 2, x 10..22). One op: `sketch_set_datum` sets `L = 60` (through the real bracket, auto-approve on).
- Probe: `<probes>/p6c_datum_point.py`. Commands:
  - story: `sh <probes>/../run.sh <probes>/p6c_datum_point.py`
  - base: `RT_SRC=<redteam-13-15>/base/src sh <probes>/../run.sh <probes>/p6c_datum_point.py`
- Output at `5115b2ac` (story):
  ```
  fillet edge Edge39 #60:3;:M3;CUT;:Hd71:8,E;:Hd73,E bbox x 10.0 22.0 strip 1 grooves [8.0, 22.0, 36.0]
  datum line before Vector (16.0, 10.0, 10.0) True
  status OK tnp_audit CLEAN grooves [8.0, 24.0, 40.0, 56.0]
  datum line now on Edge43 #60:3;:M3;CUT;:Hd71:8,E;:Hd73,E bbox x 26.0 40.0 strip 2 line valid True
  datum line after Vector (33.0, 10.0, 10.0) ('Edge43',)
  ```
  (The labels say "line"; the object is the datum point.) The datum was at the centre of strip 1 (x 16). After the edit it sits at the centre of strip 2 (x 33), between groove 2 and groove 3. Strip 1 still exists at x 10..24 (centre 17). The reply is `OK` with `tnp_audit CLEAN`, and the op commits.
- Output at `538db0be` (base, same probe):
  ```
  status SPEC_FAILED tnp_audit FLAGGED grooves [8.0, 22.0, 36.0]
   finding DatumPoint AttachmentSupport REPOINTED 1 DatumPoint.AttachmentSupport entry Edge39 resolves to a sub-shape whose witness moved: ('Edge', 10.0, 10.0, 10 ...
  ```
  Before the Story the guard flagged the same edit `REPOINTED` at layer 1 and rolled it back. The Story turns a caught re-point into a silent pass.
- Proof that the counter has no fixed meaning (`<probes>/p5_sweep.py`, story copy; support shift `((0.0, 20.0), (0.0, 0.0), (0.0, 0.0))`):
  ```
  EXCUSED Edge3 -> Edge7   (38.0, 0.0, 10.0, 40.0, 0.0, 10.0) -> (42.0, 0.0, 10.0, 56.0, 0.0, 10.0) #4c:1;:M3;CUT;...
  EXCUSED Edge31 -> Edge35 (24.0, 10.0, 10.0, 36.0, 10.0, 10.0) -> (42.0, 10.0, 10.0, 56.0, 10.0, 10.0) #60:3;:M2;CUT;...
  EXCUSED Edge39 -> Edge43 (10.0, 10.0, 10.0, 22.0, 10.0, 10.0) -> (26.0, 10.0, 10.0, 40.0, 10.0, 10.0) #60:3;:M3;CUT;...
  ```
  On the y = 10 side the counter runs from the right end, so each added strip moves every name one strip to the right: `M3` goes from strip 1 to strip 2 and `M2` from strip 2 to strip 3. On the y = 0 side, `M3` goes from the 2 mm end strip (x 38..40) to an interior 14 mm strip (x 42..56). All are excused.
- Same result with a datum plane on the top-face pieces (`<probes>/p3_pattern_expr.py`): story `CLEAN`, excuse switched off (monkeypatched `_follows_support` = False, which is the pre-Story rule) `FLAGGED`. Three of four datums change from `REPOINTED` to `PASS`. The 2 mm end-strip face `D_Face4` now resolves to the interior strip x 42..56. Its datum plane does not move, because the pieces are coplanar, but the reference is on a different face.
- Why the bound does not stop it: the jump (+16 mm for both faces of the edge) is smaller than the support growth (+20 mm). The bound checks how far an element moved, not whether the element is still the same piece.
- Scope: this occurs wherever FreeCAD gives several pieces of one source element a counter (split faces and edges after a cut, pattern or boolean), and an edit changes the piece count while the support box grows. The probe file `<probes>/p1_split.py` shows the counter also shifts with an Occurrences change alone (support box unchanged; the guard still flags that case, correctly).
- Possible directions for the builder (not tested): do not excuse a mapped name that carries a split-piece counter (`;:M<n>` / `;:G<n>` duplicate postfix), or excuse only when the element's extent along the moved axis keeps its size or its contact with the moved support face.

## Not reproduced (low)

- Q7 cost: no regression. `<probes>/p7_cost.py`: 200 datums on a 186-face pocketed plate, `snapshot_references` median 0.022 s at both `5115b2ac` and `538db0be` (204 records).
- Tampered witness inside the support range is excused: known and documented in the `_follows_support` docstring and decision 017. Not re-reported.
- Written baseline (post-op, pre-recompute) and the 13-10 expression-written path: by code read, the written record carries a pre-recompute `target_witness`, and expression records carry `target_witness: None`, so expressions are never excused. No break found.
- NaN, infinite, unreadable or empty witnesses: `_axis_shifts` returns `None`, so the move is never excused (code read; already covered by tests).
- Part::Feature with no element map (`Part::Box`, `ElementMapSize == 0`): `mapped` is `None`, so the move is never excused (code read).
- Test doubles: `FollowsSupportTest` uses dict entries for a pure function, and the two `_UnreadableShape`/`_Target` fakes only raise on `Shape`. None of them skips a real check the production path depends on. No false-pass test found.
- Support witness cache keyed by target `Name` per walk: a name collision across documents is not reachable, because `PropertyLinkSub`/`PropertyLinkSubList` do not link across documents and `PropertyXLink*` is outside the audited types. Not probed.
- Mirrored features, multiple solids, `App::Part`/link placements: not probed. RT-1 already shows the class.

## Not run

- No container or E2E run: the verifier owns them. RT-1 runs through the real `sketch_set_datum` bracket on the host freecadcmd.
