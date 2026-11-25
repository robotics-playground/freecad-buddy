# Story 13-fu: re-verification (round 2)

SHA tested: `04adaafa` (`story/13-followups`, worktree `freecad-buddy-wt-13-fu`; fixes `6aa611dd` + `04adaafa`). Verifier: verifier-13-fu, 2026-11-25.

## Verdict

**FAIL: one product defect (D1, medium).** The section shortcut added in `6aa611dd` reports `min_distance` 0 for disjoint solids with a real gap at an edge, a vertex or a curved surface, when the gap is inside the section tolerance. The base `8049378d` reports the true distance for the same pairs, so this is a regression. The leader's check "a real gap of 1.5e-7 mm and 1e-3 mm (tolerance 1e-2) -> distance NOT 0" fails for these layouts; it passes only for face-to-face gaps. Everything else passes: all gates, all requested mutants red, nested spheres flagged, lid x200 in 1.44 s, touches at overlap 0, box-in-box volume, and TC-17 live.

## 1. Gates (at 04adaafa)

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | `All checks passed!` |
| `check_imports.py` | `check_imports OK` |
| `check_status_vocab.py` | `check_status_vocab OK` |
| `gen_schemas.py --check` | `gen_schemas --check OK` |
| `check_skill_shape.py` | exit 0 |
| `check_provenance.py` | `check_provenance OK` |
| `uv run --extra dev pytest tests/external -q` (Git Bash) | `2109 passed, 6 skipped, 6 warnings in 204.38s` |
| freecadcmd `tests/run_tests.py`, temp cfg, temp `FREECAD_USER_HOME` | `Ran 1275 tests in 133.686s`, `OK (skipped=1)`; `QueryInterferenceTest` 53 tests |

## 2. Mutants

Location: detached `git worktree` at `04adaafa` in `scratchpad\verifier-13-fu\mut` (removed after the run). Runner `scratchpad\verifier-13-fu\scripts\mutant.sh` (one string edit, freecadcmd `QueryInterferenceTest`, restore). Baseline `fail=0 error=0 run=53`; each run printed the copy's `queries.py` path.

| Mutant | Edit | Red tests |
| --- | --- | --- |
| mu1 interpenetration probe removed | drop `and not _solids_interpenetrate(shape_a, shape_b)` | 3: nested spheres r10, r100 (`test_query_tools.py:836`), fuse keeps two unmerged nested spheres |
| mu2 section shortcut without the fuse proof | `if _boundaries_meet(...)`: `return 0.0, 0.0, False` directly | 8: 1e-7 depth, nested r10 and r100, above stated limit, just above tolerance (100, 1000 mm), gap inside section tolerance (both cases) |
| mu3 tolerance 3e-12 | `_TOUCH_VOLUME_REL_TOL = 3e-12` | 1: `test_Should_flag_a_failed_boolean_When_the_overlap_is_above_the_stated_limit` (`:1027`) |
| mu4 tolerance 5e-13 | `5e-13` | 1: `test_Should_report_zero_overlap_When_the_overlap_is_below_the_stated_limit` (`:1010`) |
| mu5 `abs` dropped | `abs(gap) <=` -> `gap <=` | 3: fuse volume above the sum (`:939`), gap inside section tolerance (both cases) |
| mu6 fuse at unknown distance (old F1) | `if fuse_proof is None:` | 1: `test_Should_not_run_the_fuse_When_the_distance_is_unknown` (`:787`); F1 closed |
| mu7 section always false | `return False` in `_boundaries_meet` | 3: skip-distance test (`:878`), gap inside section tolerance (both cases) |
| mu8 probe one direction | `for direction in (1.0,):` | 3: the nested-sphere tests |

No survivor.

## 3. Real-geometry attack probes (host freecadcmd 1.1.4, private cfg + `FREECAD_USER_HOME`)

Probe `tests/uat/run/13-fu-r2/evidence/attack.py` (full `query_interference` call through `DocumentRegistry`, on `wt-13-fu/src`; log `attack.log`). Format: `common_volume / min_distance / boolean_failed`, time, fingerprint equal.

| Case | Result | Expected | Verdict |
| --- | --- | --- | --- |
| rt1 sphere r10 in r10+1e-6, offset 1e-6 | `None / 1.699e-08 / True`, 0.01 s | failed | PASS |
| rt1 sphere r100 in r100+5e-7, offset 5e-7 | `None / 8.495e-09 / True` | failed | PASS |
| touch face / edge / vertex (10 mm boxes) | `0.0 / 0.0 / False` each | 0 / 0 / false | PASS |
| sphere on box (point), cylinder on box (line), sphere on sphere (point) | `0.0 / 0.0 / False` each | 0 / 0 / false | PASS |
| box 5 inside box 10, sharing 3 faces (common non-empty) | `124.99999999999997 / 0.0 / False` | 125 | PASS |
| rt5 lid on 100 boxes | `0.0 / 0.0 / False`, 0.56 s | correct, < 40 s | PASS |
| rt5 lid on 200 boxes | `0.0 / 0.0 / False`, 1.44 s | correct, < 40 s | PASS |
| thin nested shell (wall 5e-5 mm) in sphere 1e-6 larger | `None / 1.699e-08 / True` | failed (or documented limit) | PASS |
| gap face 1.5e-7, 2e-7, 1e-6 (default tolerance) | distance 1.5e-7, 2e-7, 1e-6 | gap | PASS |
| gap face 1e-3, 5e-3 (tolerance 1e-2) | distance 1e-3, 5e-3 | gap | PASS |
| **gap edge 1.5e-7** (true 2.12e-7) | `0.0 / 0.0 / False` | 2.12e-7 | **FAIL** |
| **gap vertex 1.5e-7** (true 2.6e-7) | `0.0 / 0.0 / False` | 2.6e-7 | **FAIL** |
| **gap sphere-sphere 1.5e-7, 2e-7** | `0.0 / 0.0 / False` | gap | **FAIL** |
| **gap sphere-box 1.5e-7, 2e-7** | `0.0 / 0.0 / False` | gap | **FAIL** |
| **gap edge 2e-7** (true 2.83e-7) | `0.0 / 0.0 / False` | 2.83e-7 | **FAIL** |
| gap edge/vertex/sphere 1e-6 (default tolerance) | true distance | gap | PASS |
| **tolerance 1e-2: gap edge, vertex, sphere-sphere, sphere-box 1e-3 and 5e-3** | `0.0 / 0.0 / False` (all eight) | gap | **FAIL** |

Every probe left the fresh fingerprint digest equal.

Base comparison (`evidence/gapsweep.py`, `_measure_interference` direct; `gapsweep-head.log` at 04adaafa, `gapsweep-base.log` at 8049378d):

| Pair | `distToShape` | 04adaafa | 8049378d |
| --- | --- | --- | --- |
| edge gap 1.5e-7 | 2.121e-07 | `(0.0, 0.0, False)` | `(0.0, 2.12e-07, False)` |
| sphere-sphere gap 2e-7 | 2e-07 | `(0.0, 0.0, False)` | `(0.0, 2.0e-07, False)` |
| tol 1e-2, sphere-sphere gap 0.009 | 0.009 | `(0.0, 0.0, False)` | `(0.0, 0.009, False)` |
| tol 1e-2, sphere-sphere gap 0.015 | 0.015 | `(0.0, 0.0, False)` | `(0.0, 0.015, False)` |
| tol 1e-2, sphere-sphere gap 0.02 | 0.02 | `(0.0, 0.0, False)` | `(0.0, 0.02, False)` |
| tol 1e-2, vertex gap 0.009 (true 0.0156) | 0.01559 | `(0.0, 0.0, False)` | `(0.0, 0.0156, False)` |
| tol 1e-2, vertex gap 0.015 (true 0.026) | 0.02598 | `(0.0, 0.026, False)` | same |
| tol 1e-3, sphere-box gap 0.002 | 0.002 | `(0.0, 0.0, False)` | `(0.0, 0.002, False)` |

## 4. Defect D1 (medium, product, regression from 6aa611dd)

- **Case:** two disjoint valid solids whose closest features are an edge, a vertex or a curved surface, with a gap above the 1e-7 mm contact distance but inside the section tolerance.
- **Expected:** `min_distance` is the gap (T-2: `min_distance` uses `distToShape`; the code comment says the section "also finds boundaries across a real gap inside the shapes' tolerance (1.5e-7 mm, or 1e-3 mm on shapes with a tolerance of 1e-2), where the fuse proof fails and ``distToShape`` still runs").
- **Observed:** `min_distance` 0 (`common_volume 0.0`, `boolean_failed false`), so the pair reads as contact. Examples above: edge gap 1.5e-7 mm (true 2.12e-7); with shape tolerance 1e-2, sphere gaps up to 0.02 mm (twice the tolerance) and vertex gaps up to 0.0156 mm; with tolerance 1e-3, a 0.002 mm sphere-box gap.
- **Cause:** `queries.py:871-874`: `if _boundaries_meet(shape_a, shape_b):` then `fuse_proof = _fuse_proves_touching(...)`, `if fuse_proof: return 0.0, 0.0, False`. The fuse proof fails across a face gap only because the fuse fills the gap slab and the volume rises above the sum (mutant mu5 shows `abs` carries that test). At an edge, a vertex or a tangent point the filled volume is negligible, the fuse proof passes, and `distToShape` never runs. The comment at `queries.py:866-868` is true only for face gaps.
- **Tests:** `test_query_tools.py:966` `test_Should_report_the_gap_When_disjoint_solids_lie_inside_the_section_tolerance` covers face gaps only, so it stays green.
- **Evidence:** `tests/uat/run/13-fu-r2/evidence/attack.log`, `gapsweep-head.log`, `gapsweep-base.log`.
- **Severity:** medium. The error is bounded by about twice the shapes' tolerance and is on the "contact" side, not "no overlap". With default tolerance it is about 1e-7 to 3e-7 mm. On shapes with a loose tolerance (imported STEP can carry 1e-3 to 1e-2), a real clearance of up to 0.02 mm reads as 0, and the T-2 text does not state it.
- **Options for the builder (not applied):** (a) add edge, vertex and sphere gap cases to `:966` first, so they fail. (b) Keep the shortcut only when the contact is proven independently of the tolerance. One example: each section vertex lies within 1e-7 mm of both shapes, measured by a point `distToShape`, which costs little. (c) Or document in T-2, the design and the catalog that `min_distance` is 0 for gaps inside the section tolerance, and give the measured bound. The leader decides.

## 5. UAT (container `fcb-desktop`)

Setup: `build_addon.py --release` in wt-13-fu. `docker compose ... up -d --build` from wt-13-fu. `docker inspect` showed `freecad-buddy-wt-13-fu -> /repo (ro)` and `...\tests\uat\run -> /repo/tests/uat/run (rw)`. The installed `queries.py` SHA-256 `1c4b3729...6e730d` equals `dist/addon` and `src`. The first `fcb-freecad start` aborted (known); the second was ready (healthz `freecad_pid` 663).

| Case | Verdict | Observed |
| --- | --- | --- |
| TC-17-01 (extended, 5 pairs) | PASS | A/Face, A/Edge, A/Vertex `0.0 / 0.0 / false`; Big1/Big2 `null / 0.0 / true`; Ball/Shell `null / 1.7e-08 / true`; text `5 pair(s), 0 overlapping, 2 boolean failed.`; digest `5d4f4c81...` equal before and after; eight objects, no `!`. Screenshot read: two large cubes sharing a face, four small cubes in the face, edge and corner layout, and one sphere behind Big2 (Ball hidden in Shell). No visible overlap |

Case fix (test-case defect): the new `Ball/Shell` check had raw line breaks inside its inline code (the same defect as RT-7), and expected `[true, 2]`. It now uses `\n` and expects `[True, 2]`, the Python `value_repr`. The case does not cover D1: its pairs are touching, overlapping or nested, not gaps.

Evidence: `tests/uat/run/13-fu-r2/` (`RUN-CONTEXT.md` with the grading, `evidence/tc-17-01-mcp.json`, PNGs and crops, client scripts, probe scripts and logs, `baseline-tracked.diff`). These files and the TC-17 edit are left uncommitted, as the leader asked.

## 6. Clean-up

FreeCAD stopped. `compose down`: the container and network are removed, and the image is kept. The mutant worktree is removed. The developer `user.cfg` SHA-256 `a8d0bb82...0468c2` is unchanged. Container `addon.log` has 0 error lines. No `freecadcmd` of mine is running.
