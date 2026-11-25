# Story 13-fu: verification

SHA tested: `8049378d` (`story/13-followups`, worktree `freecad-buddy-wt-13-fu`). Verifier: verifier-13-fu, 2026-11-25.

## Verdict

**PASS**, with two low test-gap findings (F1, F2) for the leader. Every gate is green. Every requested mutant turns a named test red. TC-17 passes live in `fcb-desktop` after two test-case fixes. No product defect found.

## 1. Gates (at 8049378d)

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | `All checks passed!` |
| `check_imports.py` | `check_imports OK` |
| `check_status_vocab.py` | `check_status_vocab OK` |
| `gen_schemas.py --check` | `gen_schemas --check OK` |
| `check_skill_shape.py` | exit 0, no output |
| `check_provenance.py` | `check_provenance OK` |
| `uv run --extra dev pytest tests/external -q` (Git Bash) | `2109 passed, 6 skipped, 6 warnings in 239.84s` |
| freecadcmd `tests/run_tests.py`, temp `-u/-s` cfg, temp `FREECAD_USER_HOME` | `Ran 1266 tests in 143.835s`, `OK (skipped=1)` |

Builder counts reproduced exactly (infc 1266 / 1 skipped; external 2109 / 6).

## 2. Mutants

Location: detached `git worktree` at 8049378d in `scratchpad\verifier-13-fu\mut` (removed after the run). Runner `scratchpad\verifier-13-fu\scripts\mutant.sh` + `run_some.py`: one string edit, freecadcmd on the named class with temp cfg and temp `FREECAD_USER_HOME`, `git checkout -- .`. Every run printed `QUERIES_FILE=...verifier-13-fu/mut\src\freecad_buddy\usecases\queries.py`, so the copy's code ran. Baselines: `QueryInterferenceTest` fail=0 run=44; `SweepTest` fail=0 run=47.

| Mutant | Edit | Result |
| --- | --- | --- |
| m1 tolerance loosened | `_TOUCH_VOLUME_REL_TOL = 1e-9` | 3 red: `..._boxes_overlap_by_a_depth_that_leaves_common_empty`, `..._the_overlap_is_just_above_the_tolerance` (100 mm, 1000 mm) |
| m2 tolerance loosened | `1e-11` | 2 red: `..._just_above_the_tolerance` (both cases) |
| m3 fuse always accepted | `_fuse_proves_touching` returns `True` | 9 red (gap boundary, 1e-7 depth, common raises at 0, fuse invalid, fuse loses volume, fuse raises, NaN, 2 x just above tolerance) |
| m8 fuse never accepted | returns `False` | 6 red (face, edge, vertex touch; pin in hole; common raises + valid fuse; gap boundary) |
| m4 fuse validity not checked | `bool(fused.isValid())` -> `True` | 1 red: `..._the_fuse_is_not_a_valid_shape` |
| m5 fuse also at unknown distance | `if distance is not None and _fuse_proves_touching` -> `if _fuse_proves_touching` | **survives** (F1) |
| m6 negative gap accepted | `abs(gap) <=` -> `gap <=` | **survives** (F2) |
| m7 no finite check | drop `math.isfinite(gap)` | survives; near-equivalent: NaN and finite-total infinities already fail `abs(gap) <= tol * total` |
| s1 sweep limit 10,000 | `_SWEEP_MAX_COST = 10000` | 1 red: `test_Should_refuse_a_sweep_costing_one_unit_above_3000_When_the_real_limit_is_used` |
| s2 sweep limit 2,999 | `2999` | 2 red: the refuse test and `test_Should_cost_3000_units_within_the_real_limit_When_a_circle_runs_along_3000_lines` |
| s3 sweep limit 3,001 | `3001` | 1 red: the refuse test |

## 3. Quality bar map

| Q | Status | Evidence |
| --- | --- | --- |
| Q1 touch reads 0, not failed | met | `tests/infc/test_query_tools.py:601` (face, edge, vertex subtests), `:625` pin in hole wall; mutant m8; live TC-17 |
| Q2 empty-common overlap never 0 above 1e-12; fuse invalid/raise/non-finite/gap -> failed | met | `:639` 1e-3 mm3 at depth 1e-7, `:657` just above tolerance (100 mm, 1,000 mm), `:679` solid inside another, `:712` invalid fuse, `:737` raise and NaN, `:813` boundary; mutants m1, m2, m3, m4; live Big1/Big2 |
| Q3 fuse only for trusted pairs inside bounds; unknown distance -> no fuse | met in code, test gap F1 | `queries.py:903` face product checked before any pair, `:949` deadline before each pair, `:939` trust per object, `:856` fuse only with a distance; test `:768` does not detect a fuse run (m5 survives) |
| Q4 read-only | met | `:851` fresh digest equal; live digest `207fd393...` before and after |
| Q5 docs state the touching rule and tolerance limit; no drift | met | T-2 `tool-contracts.md:83-89`, `mcp-tools-design.md:132` (§2 row), `:344` (§3.2.3), `tool_catalog.py:1673-1682`, `skills/verification-thinking/SKILL.md:64-66`, `measuring-clearance-and-sections.md`, `verification-kit.md`, `gap-list.md:36`; `gen_schemas --check`, `check_skill_shape`, external drift tests green |
| Q6 sweep limit pinned at 3,000 | met | `tests/infc/test_feature_tools.py:3330`, `:3345`; mutants s1, s2, s3 |
| Q7 closed-loft sentence and timings | met | `features.py:845-846` (13.2 s, 10.6 s, 13.7 s), `:855` (9.3 s), `mcp-tools-design.md:734` (8 squares smooth valid), `:738` all equal `verify-13-18.md` round-2 table (13.18, 10.56, 13.69, 9.29 s) and R2-F2 |
| Q8 gates with counts | met | section 1 |
| Q9 live container | met | section 4 |

## 4. UAT (container `fcb-desktop`)

Harness gate: control yes (MCP over HTTP + container `cua-driver`, 346 AT-SPI elements); observation yes (window pixels through `cua-driver`, kernel volumes through `script_exec`).

Setup: `build_addon.py --release` in wt-13-fu; `docker compose -f tests/close-loop/docker/compose.yaml up -d --build` run from wt-13-fu. The compose file uses paths relative to itself, so no override was needed; `docker inspect` showed `freecad-buddy-wt-13-fu -> /repo (ro)` and `...wt-13-fu\tests\uat\run -> /repo/tests/uat/run (rw)`. Installed `queries.py` SHA-256 `f1ffb5ee...bc5f95` equals `dist/addon` and `src`. First `fcb-freecad start` aborted (Qt xcb plugin, known); second start ready, healthz `freecad_pid` 1202. Client: small `mcp` streamable-HTTP client (`evidence/mcpcall.py`).

| Case | Verdict | Observed |
| --- | --- | --- |
| TC-17-01 | PASS (attempt 2) | A/Face, A/Edge, A/Vertex: `common_volume 0.0`, `min_distance 0.0`, `boolean_failed false`. Big1/Big2 (1e-7 mm overlap, `common` empty): `common_volume null`, `boolean_failed true`. Text `4 pair(s), 0 overlapping, 1 boolean failed.`. Fresh digest equal before and after. Screenshot: six boxes, the contacts as designed, no visible overlap |

Attempt 1: MCP values identical; screenshots not taken (my client's `subprocess` `bash` resolved to WSL: agent execution fault); kernel check gave `[0.0, -0.0, 0.0]`. Kept as `evidence/*-attempt1.json`.

Case fixes in `tests/uat/testcases/TC-17-query-interference-touching.md` (test-case defects): `abs(...)` around the kernel fuse gap (FreeCAD gives `-0.0` for the edge pair); the `Big1/Big2` inline code had a raw line break inside the code span, now `\n`, and expected `True` (Python `value_repr`).

Evidence: `tests/uat/run/13-fu-r1/` in wt-13-fu (`RUN-CONTEXT.md`, `evidence/tc-17-01-mcp.json`, `tc-17-01-before.png`, `tc-17-01-after.png`, `tc-17-01-after-small-pairs-zoom.png`, cleanup JSON, client scripts, `baseline-tracked.diff`). The platform refused a `report.md` in the run folder; the grading is in this file.

## 5. Findings

**F1 (low, test gap, Q3).** `tests/infc/test_query_tools.py:768` `test_Should_not_run_the_fuse_When_the_distance_is_unknown` guards with `raise AssertionError("the fuse must not run without a distance")` inside the fake `fuse`, but `_fuse_proves_touching` catches it: `queries.py:876` `except Exception:  # noqa: BLE001 -- a fuse the kernel cannot build leaves the overlap unproven` returns `False`, so the result stays `(None, None, True)` either way. Mutant m5 (fuse at unknown distance) survives; under it a pair with an unknown distance and a fuse with the summed volume would read `common_volume 0`, `boolean_failed false`, `min_distance null`. Product code is correct today. Fix: let the fake fuse record the call (or return a valid summed-volume fuse) and assert it was not called / the result is still failed.

**F2 (low, test gap, Q2).** No test gives a fuse volume above the summed volume; mutant m6 (`abs(gap)` -> `gap`) survives. Fix: one fake case with `Fused.Volume = total * (1 + 2 * tolerance)` expecting `boolean_failed true`.

**Note.** m7 (`math.isfinite(gap)` dropped) survives because the abs comparison already rejects NaN and infinite gaps for a finite total; the check matters only for an infinite summed volume, which the trust check makes unlikely. No action proposed.

## 6. Clean-up

FreeCAD stopped (`fcb-freecad: stopped`); `docker compose ... down`: container and network removed, image `fcb-desktop:local` kept. Mutant worktree removed (`git worktree list` shows none of mine). No `freecadcmd` of mine running (pid 27976 belongs to `redteam-13-fu` and was left alone). Developer `user.cfg` SHA-256 `a8d0bb82...0468c2` unchanged. Host `:8765` not touched.

Not committed: `tests/uat/testcases/TC-17-query-interference-touching.md` (modified) and `tests/uat/run/13-fu-r1/` (new) are left uncommitted in wt-13-fu. The user's global rule forbids a commit without the user's own approval, and an agent message is not that approval. Commit after the user approves.
