# Verify 13-15 r2: TNP audit accepts expected re-attachment moves (fix batch)

Verifier: verifier-13-15. Date 2026-11-25. SHA tested: `6d6bdc60`. Gates, mutants and probes ran
in detached worktrees of `6d6bdc60` under my scratch (`<scratch>` =
`C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\17c8e5ee-89aa-4e27-ba05-1fe1774e804a\scratchpad\verifier-13-15`):
`<scratch>\g6d` (gates, G2) and `<scratch>\mut2` (mutants). Both were removed after the run (`git
worktree list` shows no verifier entry). The container was built from wt-13-15 at `1c459a8a`. That
commit changes docs only, and `src` is equal to `6d6bdc60`. The installed hash proves it.

## Verdict

**PASS.** All gates are green with no failures. Five of the six mutants fail tests; the
lineage-walk mutant survives (test gap, low). The four red-team probes hold. TC-18 01-04 PASS in
the container. D-1 from r1 (mesh-based witness) is fixed: the 04b witness is now exact. 04b still
grades `REPOINTED`, now for a different reason: the positional-name detector refuses the excuse on
`;:M`. That result is on the safe side, and the reason is recorded below (R-1).

## Gates at 6d6bdc60

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `scripts/check_imports.py` | `check_imports OK` |
| `scripts/check_status_vocab.py` | `check_status_vocab OK` |
| `scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| `scripts/check_skill_shape.py` | exit 0 |
| `scripts/check_provenance.py` | `check_provenance OK` |
| `uv run --extra dev pytest tests/external -q -p no:cacheprovider` (Git Bash) | 2109 passed, 6 skipped. The known unstable test passed in this run |
| infc: `freecadcmd -u/-s <private cfg> tests/run_tests.py`, private `FREECAD_USER_HOME` | `Ran 1314 tests`, `OK (skipped=1)`; 119 `test_tnp_guard` tests |
| G2: `FREECAD_BUDDY_RUN_FAULT_SCORER=1 ... score_g2_infc.py` | `audit_references planted= 3 controls= 6 detected= 3 flagged= 0 sensitivity=1.000 false_alarm=0.000`. The written `validators.yaml` has no content diff against `6d6bdc60` (sha reproduces). Exit 1 is the same as in r1: `run_mutation`, `fingerprint` and `verify_sketch` are not scored, and this story does not touch them |

## Mutants (infc.test_tnp_guard + SetParametersTest, 132 tests; BASE 0 red)

| Mutant | Change | Red |
| --- | --- | --- |
| X1 excuse always true | `_follows_support` returns `True` | 21 |
| X2 count guard removed | `return support_shift` in `shift_for` (`tnp_guard.py:984`) | 1 (`test_Should_flag_repointed_When_the_support_element_count_changed`) |
| X3 detector always false | `_has_positional_counter` returns `False` (`:266`) | 3 |
| X3b split-sibling detector false | `_has_split_siblings` returns `False` (`:286`) | 3 (`SplitSiblingTest`) |
| X4 lineage check removed | `_lineage_has_counter` returns `False` (`:291`) | **0, survives** |
| X5 witness back to `BoundBox` | `bbox = element.BoundBox` (`:218`) | 1 (`WitnessMeshTest.test_Should_read_the_exact_extreme_When_the_curved_face_was_tessellated`) |

**X4 survives.** No infc test fails when the lineage walk always returns "no counter".
`FollowsSupportTest` (`tests/infc/test_tnp_guard.py:1766`) sets `lineage_counter=True` by hand, so
it tests the clause in `_follows_support`, not the walk (`_lineage_has_counter`) or its wiring in
`_grade_entry`. The walk does work on real geometry: red-team probe `p11_lineage.py` at
`6d6bdc60` prints `lineage_counter True` for a name whose counter is hidden behind a hash. In p11
the count guard also catches the re-point, which is why the suite stays green. This is a test gap
like RT3-L1 for the count guard. Low: no case was found where the walk is the only defence. Fix
option: an infc test that calls `_lineage_has_counter` on the p11 fixture and expects `True`.

## Red-team probes at 6d6bdc60

Run with my copy of the red-team runner (`<scratch>\rtrun.sh`: own cfg and home,
`RT_SRC=<scratch>\g6d\src`; `boot.py` asserts that the imported `tnp_guard` is from `RT_SRC`). The
probes in `redteam-13-15c/probes/` were only read, not changed. Logs: `<scratch>\r2\probe-*.log`.

| Probe | Result | Expected |
| --- | --- | --- |
| p6c datum point (RT-1 slotted plate) | `status SPEC_FAILED tnp_audit FLAGGED`, `DatumPoint ... REPOINTED 1` | holds |
| p3 pattern of slots | `story status FLAGGED`; `D_Face4`, `D_Face8`, `D_Face12` `story=('REPOINTED', 1)`; `D_Face16` (did not move) `PASS 2`, the same with the excuse off | holds |
| p13 grid, bracket | `status SPEC_FAILED tnp_audit FLAGGED`; `BossPlane` and `BossPoint` `REPOINTED 1` | holds |
| p14 MultiTransform sweep | `MT excused 13`, all plate faces and edges (`#16:<n>;:H8f3,F`, `#d:`/`#36:` edges); no excused name carries `;_<n>` or `;:H,` | holds |

## UAT (container, run `tests/uat/run/13-15-r2/`)

Setup: `build_addon.py --release`, `compose up -d --build` from wt-13-15. Mounts read back
`wt-13-15 -> /repo (ro)` and `tests/uat/run` rw. Installed `tnp_guard.py` = `dist` =
`git show 6d6bdc60:` = `2c87d5a7...c867`. FreeCAD pid 364, 346 AT-SPI elements. The driver and
cases are unchanged from r1.

| Case | Verdict | Observed |
| --- | --- | --- |
| TC-18-01 | PASS | `OK`, not rolled back, `CLEAN` `{PASS: 2}`, datum z 10 -> 15; audit log `OK`/`rolled_back` false. Screenshot `tc-18-01-after-front.png` inspected: the datum line (yellow) runs along the top edge of the 20 x 15 front outline |
| TC-18-02 | PASS | `CLEAN` `{PASS: 3}`; top z 10, side x 30, block XMax 30 |
| TC-18-03 | PASS | planted re-point `REPOINTED` (installed copy); witness tamper `REPOINTED`; `Reversed` `SPEC_FAILED` + rollback + restored; vertical-edge axis `REPOINTED` by mapped name |
| TC-18-04 | PASS (04a `CLEAN`, point z 7.5); 04b safe-side FLAG, see R-1 | 04b twice: `SPEC_FAILED`, rolled back; witness `(7.0, 2.0, 10.0, 13.0, 8.0, 15.0) -> (7.0, 2.0, 10.0, 13.0, 8.0, 20.0)`: y is exact now (r1: 2.0164), so D-1's mesh cause is fixed |

Teardown: `fcb-freecad stop`, `compose down`, no container left; `addon.log` no `ERROR`/`Traceback`;
developer `user.cfg` unchanged (`a8d0bb82aa39569...`).

## R-1: why 04b is still REPOINTED (safe side, reason recorded)

`evidence/probe04b_reason.py` runs the installed guard around the same Boss edit in FreeCAD:
`{'mapped': '#23:1;:M;FUS;:H-85b:7,F', 'history': (2138, 'g1;SKT'), 'counter': True, 'lineage':
True, 'counts': {'Face': 8, 'Edge': 15, 'Vertex': 10}, 'shipped': [('BossPoint', 'REPOINTED', 1)],
'detector_off': [('BossPoint', 'PASS', 2)]}`.

The fuse with the block marks the Boss side face as modified piece 1 (`;:M`).
`_POSITIONAL_COUNTER` (`tnp_guard.py:68-70`) treats every `;:M` as positional, also the bare form
with no indexed sibling. For `;:G` and `;:U`, by contrast, the bare form counts only with siblings
(`_split_sibling_stems`). The face count did not change. With the detector and the lineage walk
off, the entry passes at Layer 2. So the only cause now is the name rule of decision 017, and the
result is on the safe side. Consequence for users: a reference to any face that a later boolean
modified (a boss fused onto a block, a face that a pocket trimmed) keeps the r1 false positive and
rolls back the edit. Whether bare `;:M` with no sibling may be excused, like bare `;:G`/`;:U`, is a
decision for the leader or user. It is not a defect against Q1-Q11.

## Case and evidence files (uncommitted in wt-13-15)

- `tests/uat/run/13-15-r2/` (`RUN-CONTEXT.md`, `evidence/`)
- `tests/uat/testcases/TC-18-tnp-support-follow.md`: TC-18-04b `Then` now checks the exact y bounds
  and the recorded reason (with `probe04b_reason.py`) instead of the r1 mesh expectation.
