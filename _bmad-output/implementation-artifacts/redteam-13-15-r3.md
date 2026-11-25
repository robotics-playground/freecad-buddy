# Story 13-15: third red team report (r3)

Scope: fix batch `e7f9d717...6d6bdc60` on `story/13-15-tnp-expected-reattachment` (count guard, lineage walk at grading time, `optimalBoundingBox(False, False)` witness). Whole Story diff `538db0be...6d6bdc60` as context. Code read at `6d6bdc60` from a detached copy; base from a detached copy of `538db0be`. Host `freecadcmd.exe` (FreeCAD 1.1.4), private `-u`/`-s` cfg files, private `FREECAD_USER_HOME`. Container not used.

Probe folder: `C:/Users/thuan/AppData/Local/Temp/claude/3d3814eab912640f/17c8e5ee-89aa-4e27-ba05-1fe1774e804a/scratchpad/redteam-13-15c/probes/` (below: `<probes>`). Runner: `sh <probes>/../run.sh <probe>`. `boot.py` imports `tnp_guard` from the `6d6bdc60` copy, or from `RT_SRC` (the base copy), and asserts which copy it loaded. The copies are removed after this report. To re-run, re-create them: `git worktree add --detach <scratch>/copy 6d6bdc60` and `<scratch>/base 538db0be`.

Terms used here:
- **excuse**: `_follows_support` (`tnp_guard.py:319`) turns a moved witness into `PASS` when the same element rode its moved support.
- **count guard**: `_same_element_count` (`tnp_guard.py:514`), applied in `shift_for` (`tnp_guard.py:981-984`). No excuse unless the support holds as many faces/edges/vertices of the referenced type before and after.
- **written path**: `_grade_record` (`tnp_guard.py:1050-1052`). When the live entry names equal the post-op, pre-recompute reading (`refs_written`), the entry is graded against that reading instead of the snapshot.
- **SUSPECT** (harness label): an element the 6d6bdc60 rules excuse while its old exact box is still occupied by another element in the after shape. That is the shape of every earlier real re-point (the old element survives, the name moves).

## Verdict

**PASS for the fix batch.** No edit was found after which the count guard, the name detector and the lineage walk together excuse a real re-point. 96 graded edit runs over the models in the attack log gave 0 SUSPECT elements. The harness is sensitive: with the three defences switched off it reports the RT2-1 grid re-point as SUSPECT (`hcheck.py`).

One real re-point that commits `CLEAN` was reproduced, **RT3-1 (medium, outside the batch, pre-existing)**. It does not use the excuse. The base `538db0be` also gives `CLEAN`, so by the brief's rule it is not a Story high. It breaks AD-5 ("a real re-point must not pass"), so the leader must route it.

## Reproduced

### RT3-1 — medium (pre-existing, not Story-introduced) — an op that recomputes inside the bracket makes every reference "written", so the audit compares the after state with itself

- Code: `src/freecad_buddy/usecases/transaction.py:729-733` reads `refs_written = tnp_guard.snapshot_references(document)` right after `op(document)`, as the post-op, **pre-recompute** reading. `src/freecad_buddy/usecases/features.py:1668`: the dress-up op (`feature_fillet`, `feature_chamfer`, via `_dressup_tool`) calls `document.recompute()` inside `op`:
  ```python
  apply_sizes(feature)
  document.recompute()
  _check_dressed_every_edge(feature, subelements, before)
  ```
  So `refs_written` is a post-recompute reading. `tnp_guard.py:1050` then sets `intended = _entry_values(live) == _entry_values(written)`. That is true for every reference, also the ones the op never wrote, and each is graded against the already re-pointed state (`tnp_guard.py:1052`).
- Fixture: the RT2-1 grid (plate `L = 60`, `W = 0.4 * L`, boss, two-direction `LinearPattern`, `Occurrences2 = floor(L / 20 mm)`). A `BossPoint` (`CenterOfMass`) sits on the top face of boss `_3` at (3, 7). A pending edit: `Sketch` constraint `L` set to 100 mm with no recompute (what a `script_exec` gap-fill or a GUI property edit leaves behind; `touched ['Sketch']`). Then one typed op: `feature_fillet` on the plate corner edge of the Tip `Grid`, radius 0.5 mm, through the real bracket.
- Probe: `<probes>/w1_inner_recompute.py`. Commands: `MODE=fillet sh run.sh probes/w1_inner_recompute.py`; control `MODE=setdatum ...`; base `MODE=fillet RT_SRC=<scratch>/base/src ...`.
- Output at `6d6bdc60`:
  ```
  tip Grid point before Vector (5.0, 9.0, 8.0)
  touched ['Sketch']
  MODE fillet status OK tnp_audit CLEAN detail None
  N2 5 L 100.0 mm
  point now on Face55 at (42.0, 17.0) point after Vector (44.0, 19.0, 8.0)
  before entry Face31 ('Face', 3.0, 7.0, 8.0, 7.0, 11.0, 8.0)
  written entry Face55 ('Face', 42.0, 17.0, 8.0, 46.0, 21.0, 8.0)
  re-audit with written CLEAN [('PASS', 2)]
  re-audit without written FLAGGED [('REPOINTED', 1)]
  ```
  The point leaves the boss at (3, 7), which still exists, and lands on a new boss at (42, 17). The op commits.
- Control, same pending edit, op that does not recompute inside (`sketch_set_datum` L = 100):
  ```
  MODE setdatum status SPEC_FAILED tnp_audit FLAGGED
   finding REPOINTED 1 BossPoint.AttachmentSupport entry Face31 resolves to a sub-shape whose witness moved: ('Face', 3.0, 7.0, 8.0, 7.0, 11.0, 8.0) -> ('Face', 42.0, 17.0, ...
  ```
- Base `538db0be`: `MODE fillet status OK tnp_audit CLEAN`, point on `Face55` at (42, 17). Same result, so the hole predates the Story. The Story diff does not touch `transaction.py` or `features.py`.
- Possible direction (not tested): read `refs_written` before any recompute the op runs (split the dress-up op so its recompute happens after the reading), or compute `intended` only for records the op reports it wrote, never from value equality alone.

## Confirmations asked by the leader

| Check | Probe | Output at `6d6bdc60` | Result |
|---|---|---|---|
| RT-1 slotted plate | `p6c_datum_point.py` | `status SPEC_FAILED tnp_audit FLAGGED`, `DatumPoint ... REPOINTED` | holds |
| RT-1 pattern of slots | `p3_pattern_expr.py` | `D_Face4`, `D_Face8`, `D_Face12`: `story=('REPOINTED', 1)`; `D_Face16` did not move: `PASS 2` (same with the excuse off) | holds |
| RT2-1 grid, bracket | `p13_grid_index.py` | `status SPEC_FAILED tnp_audit FLAGGED`, BossPlane and BossPoint `REPOINTED` | holds |
| RT2-1 MultiTransform sweep | `p14_multitransform.py` | 13 excused, all plate faces/edges (`#16:1;:Hc55,F;...`); 0 excused names carry `;_<n>` or `;:H,` | holds |
| Story positives | `run_subset.py` (`infc.test_tnp_guard` + `infc.test_feature_tools`, from the copy) | `Ran 292 tests ... OK` | pass |
| Cost, p15 as written (NF 80, ND 200, nothing moves) | `p15_cost.py` | snapshot median 0.178 s, audit 0.241 s (base 0.082 / 0.152 s) | below 0.3 s |
| Cost, same model, all 200 references moved (pad 10 -> 12) | `p15_moved.py` | audit 0.323 s, 362 PASS (base 0.152 s, 9 REPOINTED false positives) | see RT3-L2 |

## Attack log (no real re-point excused)

Every run grades every face, edge and vertex of the target as `_grade_entry` does at `6d6bdc60` (count guard, `_lineage_has_counter` on the live entry, sibling flags, `_follows_support`) with `<probes>/g3.py`, and labels SUSPECT as defined above.

| Leader candidate | Probe | Result |
|---|---|---|
| Pattern `Reversed` + plate grows 40 mm in -x | `s5.py` | 10 excused, all plate faces; pattern instance names not excused (`;_<n>`/`;:H,`) |
| Pattern `Length` with fixed `Occurrences` | `s1.py` | 0 excused |
| Mirrored plane `V_Axis` -> `H_Axis` | `s1.py` | 0 excused (support shift x +50, y -20) |
| MultiTransform order swap | `s5.py` | 0 excused |
| Sketch geometry reorder: second rectangle moves, ids stay | `s2.py` | 14 excused, all on the moved rectangle (same geometry id), 0 SUSPECT |
| Delete one circle, add one circle, plate grows (count net zero) | `s5.py` | 9 excused, all plate faces; new circle gets a new id (`ids.py`: id reuse needs both end points of a deleted geometry, `SketchObject.cpp:791-806`, `geoHistoryLevel = 1`) |
| Swap two hole circles (Pocket, Hole feature), hole diameter | `s1.py`, `s2.py` | 0 excused |
| Pocket `Reversed`; slot moved across the part (`sx45`, `sx5_L100`, `sx_over_boss`) | `s1.py`, `s4.py` | 0 excused |
| Fillet radius 1 -> 3; chamfer size 1 -> 2 | `s1.py`, `s4.py` | 0 excused |
| Pad `Midplane` / `SideType Symmetric` toggle | `s1.py`, `s5.py` | same faces excused, 0 SUSPECT; with a boss the face count changes (11 -> 12) and nothing is excused |
| `Two sides` and `Symmetric` + `Reversed`, with and without Length change, with taper | `s2.py`, `s3.py` | the `FAC` and `;:G0` caps swap ends on `Reversed`, but the swap is longer than the support travel, so never excused (stays `REPOINTED`, decision 47). Taper twins carry `;D<hex>` (flagged) |
| Body `BaseFeature` Box -> Box2 (larger), Box2 -> Cylinder | `s5.py` | 0 excused (history source differs) |
| Groove moved along the axis | `s2.py` | count changes, 0 excused |
| Two edits in one op (boss move + plate grow, slot move + plate grow, L + W + H) | `s4.py` | 0 SUSPECT in 68 runs over 4 model variants (plain, fillet, chamfer, both) |
| Support is an `App::Link` with placement | `l1_link.py` | Link has a `Shape`; grid re-point through the link -> `SPEC_FAILED`, `REPOINTED` |

Harness sensitivity: `hcheck.py` builds the RT2-1 grid and grows L and W. `OFF=1` (count guard, name detector, lineage walk all off) gives `SUSPECT Face7 -> Face39 (3.0, 7.0, ...) -> (42.0, 17.0, ...) | old box now ('Face7', ...)`; with the defences on: `excused 0 suspect 0`.

## Not reproduced / low

- **RT3-L1 — low — the count guard has no real-geometry test of its own.** Mutant A (`stable = True` at `tnp_guard.py:983`, in my copy only): `Ran 292 ... FAILED (failures=1)`, only `test_Should_flag_repointed_When_the_support_element_count_changed` (`tests/infc/test_tnp_guard.py:1258`), which forces the counts by editing the snapshot. `PatternGridTest` (`:2042`) and `p13` stay `REPOINTED` under the mutant, because the `;_<n>` detector catches them first. The triage T1 asked for "mutant: count guard removed -> p13 red"; that is not what kills the mutant. Not a defect: the guard is a backstop, and the synthetic test does kill the mutant.
- **RT3-L2 — low — cost with moved references.** `p15_moved.py`, NF 80, ND 200, pad 10 -> 12: audit 0.323 s at `6d6bdc60` vs 0.152 s at base (x 2.1); the lineage walk now runs for every moved element. The p15 case as written (nothing moves) stays at 0.241 s.
- **Bare `;:U` with a hidden sibling — not reproduced.** `_has_split_siblings` reads only the live element map, and a later feature hashes the indexed sibling away (`s6.py`: fillet `#21:1;:U;FLT` / `#21:1;:U2;FLT` on one face, the slot pocket after it leaves `tip U edges 0`). In that fixture the lineage walk still flags the edge (`lineage_counter True`), because the intermediate name of the upper face carries `;:M;FLT`. A U-index swap with an unchanged count and a jump inside the support travel was not found; a corner-to-corner jump is always longer than the growth on the far side.
- **Dropped before-side lineage check — not reproduced.** `StringHasher::lastID()` (`App/StringHasher.cpp:244-252`) returns the highest live id, and a freed id is erased (`:94`), so ids can be reused. Reuse needs every holder of the before name's id gone first. The target's old shape holds its `ElementIDRefs` until its own recompute ends, and every new id is above the ids still held. No case where an equal before and after name hides different text was found.
- **Container, MCP over HTTP, GUI: not run.** All runs use the host `freecadcmd` and the real use-case brackets (`sketch_set_datum`, `feature_fillet`).
