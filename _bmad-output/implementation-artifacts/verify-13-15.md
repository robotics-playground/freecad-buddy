# Verify 13-15: TNP audit accepts expected re-attachment moves

Verifier: verifier-13-15. Date 2026-11-25. SHA tested: `5115b2ac` (branch
`story/13-15-tnp-expected-reattachment`, worktree `freecad-buddy-wt-13-15`).

## Verdict

**PASS.** Every quality-bar row Q1-Q11 is met with a test or a live case. All gates are green
(one known unstable test, passes alone). Seven mutants are all red. Container UAT TC-18: 4 of 4
PASS.

One defect against the deferred ledger item R1-D1 (D-1, medium, not a regression, not blocking
Q1-Q11). One observation about uncommitted edits by another agent in the worktree (O-1). Read it
before you commit the case files.

## Gates (on 5115b2ac, worktree clean at start)

| Gate | Command | Result |
| --- | --- | --- |
| ruff | `uv run ruff check .` | All checks passed |
| imports | `uv run python scripts/check_imports.py` | `check_imports OK` |
| status vocab | `uv run python scripts/check_status_vocab.py` | `check_status_vocab OK` |
| schemas | `uv run python scripts/gen_schemas.py --check` | `gen_schemas --check OK` |
| skill shape | `uv run python scripts/check_skill_shape.py` | exit 0 |
| provenance | `uv run python scripts/check_provenance.py` | `check_provenance OK` |
| external | `uv run --extra dev pytest tests/external -q -p no:cacheprovider` (Git Bash) | 1 failed, 2108 passed, 6 skipped. The failure is the known unstable `test_managed_venv.py::test_Should_start_an_external_interpreter_When_freecad_set_pythonhome`; alone: 1 passed |
| infc | `FREECAD_USER_HOME=<scratch>/fchome freecadcmd.exe -u <scratch>/cfg/user.cfg -s <scratch>/cfg/system.cfg tests/run_tests.py` | `Ran 1293 tests`, `OK (skipped=1)`; 98 `test_tnp_guard` tests in the run |
| G2 | `FREECAD_BUDDY_RUN_FAULT_SCORER=1 freecadcmd ... benchmarks/g2/fault-injection/score_g2_infc.py` in the detached copy | `audit_references planted= 3 controls= 6 detected= 3 flagged= 0 sensitivity=1.000 false_alarm=0.000`. The written `validators.yaml` has no content diff against the commit, so `validator_sha` `6aaac472...` reproduces. Exit 1 comes from other validators (`run_mutation` not scored, `fingerprint` and `verify_sketch` 0 cases), not touched by this story |

Builder claims confirmed: infc 1293 OK (1 skipped); tnp_guard 98; external 2108 passed + the known
unstable test; G2 3/6, 1.000/0.000.

## Falsification (mutants)

Location: detached worktree `<scratch>\verifier-13-15\mut` at `5115b2ac` (scratch =
`C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\17c8e5ee-89aa-4e27-ba05-1fe1774e804a\scratchpad\verifier-13-15`).
Driver `mutate.py` edits `src/freecad_buddy/usecases/tnp_guard.py` there, runs
`infc.test_tnp_guard` + `infc.test_feature_tools.SetParametersTest` under freecadcmd (private cfg and
`FREECAD_USER_HOME`; the run prints the imported `tnp_guard.__file__`, which is the mutant copy), then
restores the file. Removed after: `git worktree remove --force` + `prune`; `git worktree list` shows
no verifier entry.

| Mutant | Change | Result (111 tests) |
| --- | --- | --- |
| BASE | none | 0 red |
| M1 excuse always true | `return True` in `_follows_support` | 16 red (all `not_excuse` units, `:216`, `:303`, `:574`, every `flag_repointed` integration test) |
| M2 bound dropped | `return same_element and support_moved` | 7 red, incl. `:303` `test_a_missing_entry_does_not_suppress_a_repoint_on_the_same_record` and `:1238` |
| M3 sign dropped | `abs(shift) <= max(abs(s) ...)` | 2 red (`:1350`, `:1659`) |
| M4 history equality dropped | remove the two `history` terms | 4 red (`:1281`, `:1294`, `:1669`, `:1691`) |
| M5 support-moved dropped | `return same_element and inside_support_shift` | 1 red (`:1616` unit only) |
| M6 written baseline swapped | `_grade_entries(doc, record, record, live)` at `:885` | 4 red (`:1387` and three `WrittenValueExemptionTest`) |
| M7 mapped equality dropped | remove the two `mapped` terms | 1 red (`:1680` unit only) |

M5 and M7 are caught only by unit tests. M7 is expected: a changed mapped name is graded earlier in
`_grade_entry`, so the `mapped` terms in `_follows_support` only guard the `None` case. M5 has no
integration test that keeps the support still while the element moves within tolerance: a weak
spot, not a defect.

## AC map (file:line at 5115b2ac; tests under `tests/infc/`)

| Q | Evidence |
| --- | --- |
| Q1 datum follows Pad length | `test_tnp_guard.py:1138` `test_Should_pass_the_datum_When_pad_length_moves_the_face_it_is_attached_to`; `test_feature_tools.py:2079` (typed `feature_set_parameters`, `CLEAN`, datum z 8.0); TC-18-01 PASS |
| Q2 sketch width | `test_tnp_guard.py:1153`; TC-18-02 PASS (side and top datums) |
| Q3 one mechanism | `test_tnp_guard.py:1171` external geometry, `:1197` `Pad.Profile`, `:1217` `Fillet.Base` (moving edge passes, renumbered stay BROKEN). Code: `tnp_guard.py:404` captures `target_witness` for every link-sub record; `:818` and `:785` grade every entry the same way; no property-name list |
| Q4 bound kept | `:303` unchanged (diff starts at line 1077); `:1238`; unit `:1637`; mutant M2 red; live TC-18-03c (`Reversed`) REPOINTED and rolled back |
| Q5 planted tamper | `:216`, `:303`, `:574` unchanged and green; `:1253`; live TC-18-03a and 03b REPOINTED |
| Q6 never excused | mapped name `:1267`, `:1680`; missing history `:1281`, `:1669`; other history source `:1294`, `:1691`; NaN support `:1307`, `:1545`; mutants M4, M7 red |
| Q7 cost | `tnp_guard.py:402-404`: `support_witnesses` dict, one `_support_witness` call per target name per walk; `_support_witness` (`:307`) reads `BoundBox` once through `_witness` (`:178`). infc total 162 s |
| Q8 G2 | scorer run above: 3 planted, 6 controls, 1.000 / 0.000, sha reproduces |
| Q9 doc | `verification-design.md` §3.2 Layer 1 text matches `_follows_support` (`:219`): equal mapped name and history source, neither unreadable, support changed, per-axis signed range spanned by zero and both support face shifts, NaN not excused; `RefRecord` has `target_witness`. The `entries` field list (`history` absent in the design block) is ledger R1-D2, pre-existing |
| Q10 gates | table above |
| Q11 live | TC-18-01 PASS |

## UAT (container `fcb-desktop`)

Setup: `build_addon.py --release`; `compose up -d --build` from wt-13-15; mounts read back
`freecad-buddy-wt-13-15 -> /repo (ro)` and `.../tests/uat/run -> /repo/tests/uat/run (rw)`. Installed
`tnp_guard.py` SHA-256 = `dist/addon` = `src` = `git show 5115b2ac:` = `bec0a8c6...e275`. First
`fcb-freecad start` came before the XFCE session (1 AT-SPI element); restarted: pid 795, 349
elements. Case file (new): `tests/uat/testcases/TC-18-tnp-support-follow.md`; index row added in
`tests/uat/test-plan.md`. Evidence: `tests/uat/run/13-15-r1/` (`RUN-CONTEXT.md`, `evidence/`).

| Case | Verdict | Observed |
| --- | --- | --- |
| TC-18-01 Pad Length 10 -> 15, datum on top face | PASS | `OK`, `rolled_back` false, `tnp_audit` `CLEAN` `{PASS: 2}`, no findings; datum z 10.0 -> 15.0, support still `('Face6',)`; audit log `feature_set_parameters` `verify_verdict` `OK`, `rolled_back` false. Visual: `tc-18-01-after-front.png` (front view) shows the datum line on the top edge of a 20 x 15 outline; the status bar reads `TopDatum (17.05 mm, -2.78 mm, 15.00 mm)` |
| TC-18-02 sketch Width 20 -> 30, datums on top and side face | PASS | `sketch_set_datum` `OK`, `CLEAN` `{PASS: 3}`; top z 10.0, side x 30.0, block XMax 30.0, no invalid object |
| TC-18-03 negatives | PASS | 03a planted re-attach (in-FreeCAD guard call, installed copy): `REPOINTED` L1 "now maps to a different element"; 03b witness tamper, support still: `REPOINTED` L1 "witness moved"; 03c `Reversed` true: `SPEC_FAILED`, rolled back, `REPOINTED` (z 10 -> -10), state restored; 03d datum axis on a vertical edge, Length 10 -> 15: `SPEC_FAILED`, rolled back, `REPOINTED` by mapped name `#10:4;:G;XTR;:H1205:7,E -> #10;:G;XTR;:H1205:7,E` (the residual decision 017 records) |
| TC-18-04 R1-D1 curved face | PASS (04a `CLEAN`); 04b safe-side FLAG, see D-1 | 04a datum point on the cylinder side of a r5 pad: `CLEAN` `{PASS: 2}`, point z 5.0 -> 7.5. The face box is mesh-based (y -4.990133642 -> -4.988343846, true value -5.0), but the support box drifts the same way because this face is the support's extreme |

Teardown: `fcb-freecad stop` (status shows no pid), `compose down`, no `fcb` container. `addon.log`:
no `ERROR`, no `Traceback`. Developer `user.cfg` SHA-256 still starts `a8d0bb82aa39569`.

## Defects

### D-1 (medium): a curved face inside the support's box grades REPOINTED in the GUI after a size edit

- Case: TC-18-04b (probe for ledger R1-D1), run twice with the same result.
- Steps: block 20 x 10 x 10; Boss pad (circle centre (10, 5), r 3, Length 15) in the same Body;
  datum point `BossPoint` (`CenterOfMass`) on the Boss cylindrical face; `view_fit_viewport`;
  `feature_set_parameters { feature: "Boss", parameters: { Length: 20 mm } }`.
- Expected: the edit commits with `CLEAN` (the face rides its support up in z), as in TC-18-01.
- Observed: `SPEC_FAILED`, `rolled_back` true, `BossPoint.AttachmentSupport REPOINTED L1 ... witness
  moved: ('Face', 7.0, 2.0, 10.0, 13.0, 8.0, 15.0) -> ('Face', 7.0, 2.01643431389518, 10.0, 13.0,
  7.98356568610482, 20.0)`. The support box y is `0.0 .. 10.0` before and after.
- Cause (measured, not proven in source): in the GUI, `BoundBox` of a face reads its display mesh.
  The mesh is coarser on the larger part: 2.0164 = 10 - 3 - 3·cos 6°, so the nodes sit 6° off the
  circle's y extreme. The y shift +0.0164 lies outside `[0, 0] ± 1e-7`, the range of a support that
  did not move in y, so `_follows_support` does not excuse it. In 04a the same drift is excused
  only because the face is the support's own y extreme.
- Suspected code: `src/freecad_buddy/usecases/tnp_guard.py:178` `bbox = element.BoundBox` (and the
  support witness through the same `_witness`). A possible direction, not tested here:
  `optimalBoundingBox(False)`, which does not use the mesh. The 04a probe printed the default
  `optimalBoundingBox()` (mesh on): `-5.009866458`, not the exact value either.
- Scope: not a regression (before this story every witness move was `REPOINTED`). It is a residual
  false positive in the class this story fixes, and it can also hit an edit that does not move the
  face, when the part size change alters the mesh. Headless infc runs have no mesh and do not show
  it. Evidence: `tests/uat/run/13-15-r1/evidence/tc-18-04b-mcp.json`, `tc-18-04b-mcp-repeat.json`,
  `tc-18-04b-after-rollback.png`.

## Observations

- **O-1: another agent edits wt-13-15 now.** After the UAT ended (files written 22:02 local), `git
  status` shows uncommitted changes in `src/freecad_buddy/usecases/tnp_guard.py` (+27: a
  `_POSITIONAL_COUNTER` regex, `_has_positional_counter`, and a debug line `import sys;
  sys.stderr.write("NAMES " ...)` in `_follows_support`) and `tests/infc/test_tnp_guard.py` (+156). I
  did not make or touch them. My results apply to `5115b2ac` only: the container ran the committed
  file (hash above), and the mutants and G2 ran in the detached copy. The infc and pytest runs from
  wt-13-15 finished before those files changed (their mtime is after the build). Any commit after
  `5115b2ac` needs its own gate run. Commit only my files: `tests/uat/testcases/TC-18-*`, the
  `test-plan.md` row and `tests/uat/run/13-15-r1/`.
- TC-18-03d documents a safe-side false positive that remains: a datum on a vertical edge rolls back
  a plain Length edit (decision 017 calls it out of scope).
- Mutants M5 and M7 are caught only by unit tests (see above).
