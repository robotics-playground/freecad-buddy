# Story 13-fu: verification round 3

SHA tested: `1c21724b` (`story/13-followups`, worktree `freecad-buddy-wt-13-fu`; the section shortcut is removed, and `distToShape` runs for every trusted pair). Verifier: verifier-13-fu, 2026-11-25.

## Verdict

**PASS.** D1 (gap read as distance 0) is closed: every gap layout now gives the true distance. All gates are green. A mutant that restores the shortcut turns the new gap test red. TC-17 passes live. Remaining known gap: RT-5 cost, which is deferred. A lid on 200 boxes takes 96.9 s for one pair, above the 60 s budget.

## 1. Gates (at 1c21724b)

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | `All checks passed!` |
| `check_imports.py` | `check_imports OK` |
| `check_status_vocab.py` | `check_status_vocab OK` |
| `gen_schemas.py --check` | `gen_schemas --check OK` |
| `check_skill_shape.py` | exit 0 |
| `check_provenance.py` | `check_provenance OK` |
| `uv run --extra dev pytest tests/external -q` (Git Bash) | `2109 passed, 6 skipped, 6 warnings in 196.39s` |
| freecadcmd `tests/run_tests.py`, temp cfg, temp `FREECAD_USER_HOME` | `Ran 1273 tests in 134.607s`, `OK (skipped=1)`; `QueryInterferenceTest` 51 tests |

## 2. Mutant

Detached worktree at `1c21724b` in `scratchpad\verifier-13-fu\mut` (removed). Baseline `QueryInterferenceTest` `fail=0 error=0 run=51`.

| Mutant | Edit | Result |
| --- | --- | --- |
| Shortcut restored | before `distToShape`: `section = shape_a.section(shape_b)`; if it has edges or vertices and `_fuse_proves_touching` passes, `return 0.0, 0.0, False` | 3 red: `test_Should_report_the_gap_When_disjoint_solids_lie_across_a_small_gap` (edge gap just above the contact distance; sphere gap just above the contact distance; edge gap with a loose shape tolerance) |

## 3. Real-geometry probes (host freecadcmd 1.1.4, private cfg + `FREECAD_USER_HOME`)

Probe `tests/uat/run/13-fu-r3/evidence/probe_r3.py` runs the full `query_interference` call on `wt-13-fu/src`. Its output confirms `has _boundaries_meet: False`. Log: `probe_r3.log`. Each row also checks that the fresh fingerprint digest is unchanged. 29 of 29 PASS.

| Case | Result (`common_volume / min_distance / boolean_failed`) |
| --- | --- |
| edge gap 1.5e-7 (true 2.121e-7) | `0.0 / 2.1213e-07 / False` |
| sphere-sphere gap 2e-7 | `0.0 / 2.0000e-07 / False` |
| sphere-box gap 1.5e-7; vertex gap 1.5e-7 (true 2.598e-7); face gap 1.5e-7 | true distance each |
| tolerance 1e-2: edge, vertex, sphere-sphere, face gaps 1e-3, 5e-3, 0.02 (12 cases) | true distance each, for example sphere 0.02 -> `0.0199999...`, vertex 0.02 -> `0.034641` |
| nested sphere r10 / r100 | `None / 1.699e-08 / True`; `None / 8.495e-09 / True` |
| touch face, edge, vertex, sphere on box, cylinder line on box | `0.0 / 0.0 / False` each |
| 100 mm boxes overlapping 1e-7 (common empty) | `None / 0.0 / True` |
| box 5 inside box 10, shared faces | `124.99999999999997 / 0.0 / False` |
| lid on 100 boxes | `0.0 / 0.0 / False`, **16.24 s** |
| lid on 200 boxes | `0.0 / 0.0 / False`, **96.94 s** (RT-5, deferred; above the 60 s budget; the 40 s deadline is checked only between pairs) |

Another agent's `freecadcmd` (pid 5540) was running at the same time, so the lid times may be a little high.

Docs: T-2 (`tool-contracts.md:97`) now says `distToShape` runs for every trusted pair and has no cost bound (13.6 s and 108 s). The design §3.2.3 says "that shortcut is not used". The `deferred-work.md:2345` entry holds the RT-5 evidence. No stale shortcut text is left in `src`, the specs, the design, the skills or `tests/infc`.

## 4. UAT (container `fcb-desktop`)

Setup: `build_addon.py --release` in wt-13-fu. Compose ran from wt-13-fu. `docker inspect` showed `freecad-buddy-wt-13-fu -> /repo (ro)` and `...\tests\uat\run -> /repo/tests/uat/run (rw)`. The installed `queries.py` SHA-256 `d59c6a6e...29c66aa` equals `dist/addon` and `src`. The first `fcb-freecad start` aborted (known); the second was ready (healthz `freecad_pid` 580).

| Case | Verdict | Observed |
| --- | --- | --- |
| TC-17-01 (5 pairs) | PASS | A/Face, A/Edge, A/Vertex `0.0 / 0.0 / false`; Big1/Big2 `null / 0.0 / true`; Ball/Shell `null / 1.7e-08 / true`; text `5 pair(s), 0 overlapping, 2 boolean failed.`; digest `5d4f4c81...` equal before and after; eight objects, no `!`. Screenshot read: two large cubes sharing a face, four small cubes in the face, edge and corner layout, one sphere behind Big2. No visible overlap |

The case needed no fix this round. Evidence: `tests/uat/run/13-fu-r3/` (`RUN-CONTEXT.md` with the grading, MCP JSON, PNGs and crops, client and probe scripts, logs). These files are left uncommitted, as the leader asked.

## 5. Clean-up

FreeCAD stopped. `compose down`: the container and network are removed, and the image is kept. The mutant worktree is removed. The developer `user.cfg` SHA-256 `a8d0bb82...0468c2` is unchanged. Container `addon.log` has 0 error lines. No `freecadcmd` of mine is running.
