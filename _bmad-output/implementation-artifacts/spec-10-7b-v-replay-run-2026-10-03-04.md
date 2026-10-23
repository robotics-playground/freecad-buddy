---
title: 'Story 10.7b (part V): Replay of UAT Run 2026-10-03-04 Through the Runner'
type: 'feature'
created: '2026-10-23'
status: 'done'
baseline_commit: '3ca2addc3fb2cf38dac63b1745a62ce9dbabc45a'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-10-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-10-7b-r-scripted-uat-runner.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-10-7b-s-uat-review-sampling-rule.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The runner from part R has 12 pilot scenarios. Story 10.7b AC9 asks for proof that the runner reproduces the verdicts of UAT run 2026-10-03-04 for every deterministic Then it covers, and that every difference is explained. Story 10.8 needs the runner to cover the suite.

**Approach:** Encode the scenarios of TC-01..TC-14 that the runner can express as scenario files. Run them live on FreeCAD 1.1.4. Compare each runner verdict with the 2026-10-03-04 verdict and explain each difference in a committed replay report under `tests/uat/run/`.

Scope is part V of Story 10.7b (epics.md AC9).

## Decisions

- **D1 — Product under replay is HEAD.** Each 2026-10-03-04 product FAIL whose defect a 10.x story fixed is a `product fixed (F-xx, story)` difference. The runner and probe run as built.
- **D2 — Proof subset.** Encode every runner-expressible scenario that was `FAIL` in 2026-10-03-04, plus at least 3 runner-expressible `PASS` or `PARTIAL` scenarios per test case TC-01..TC-14 (all of them when a test case has fewer). Keep the 12 pilots. Story 10.8 encodes the rest.
- **D3 — Show All delivery retry.** When `cua-driver` refuses `View > Visibility > Show All Objects` (`menu_path_unavailable`), the runner delivers it again, up to 3 attempts in total, and confirms each attempt through the probe. Only menu delivery is retried; a check failure or a probe/MCP disagreement is never retried. `results.json` records the attempt count of the step.
- **D4 — Calibration read.** The agent reads every capture of this replay once. The report lists each scenario where the scripted pixel check and the agent reading disagree, as a pixel false alarm or a pixel miss, with counts.

## Boundaries & Constraints

**Always:**
- A scenario is in scope only when every deterministic Then fits the part R schema (envelope `expect`, `probe`, `cross`, `pixel`, allow-listed `menu`). Every other scenario is listed in the replay report as `not covered`, with one reason from a closed set: `H1 host`, `raw RPC or second client`, `process kill or relaunch`, `log or audit read`, `file check`, `GUI action`, `timing bound`, `comparison op`.
- Each difference has one class: `product fixed (F-xx, story)`, `test case changed (10.7 edit)`, `runner limit`, `harness`, `unexplained`. An `unexplained` difference blocks AC9.
- The old verdict word maps to a runner verdict before comparison: `PASS` and `PARTIAL` map to `PASS` or `ESCALATE` with `agent_check`; `FAIL` maps to `FAIL`; `BLOCKED` and `SKIP` map to no comparison.
- Every replay capture gets agent review per test-plan §9.
- Past run reports keep their text. Test-case markdown stays the human source.

**Never:**
- Change runner checks, verdict rules or exit codes, except D3.
- Add a check kind to the runner schema.
- Open `benchmarks/*/heldout`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Same verdict | old PASS, runner PASS | row `same` | N/A |
| Product fixed | old FAIL on F-01, runner PASS | row `differs`, class `product fixed (F-01, 10.1)` | N/A |
| Visual only | old PARTIAL, runner ESCALATE `agent_check` | row `same` | N/A |
| Not covered | scenario needs the H1 host | row `not covered`, reason `H1 host` | N/A |
| New id | TC-11-17 (added in 10.7) | row `new`, no old verdict | N/A |
| Old id missing | old id with no current scenario | row `removed`, cites 10.7 edit inventory | N/A |
| Unparsed table | `report.md` row the parser cannot read | compare tool exits 2 | message names the line |
| Not encoded | runner-expressible, outside D2 subset | row `not encoded`, left to Story 10.8 | N/A |
| Show All refused once | first delivery `menu_path_unavailable`, second succeeds | step passes, attempts 2 | after 3 refusals: `ESCALATE` naming the refusal |

</frozen-after-approval>

## Code Map

- `tests/uat/runner/scenario.py:3-57` -- schema: `id`, `tc`, `title`, `launch` (env map), `steps` (`mcp` or allow-listed `menu`), `expect` (`equals`, `approx`, `regex`, `absent`), `probe`, `cross`, `pixel`, `agent_check`; `$PROJECT_ROOT`, `$RUN_DIR`, `$step.path` references
- `tests/uat/scenarios/tc-11-01.json` -- shortest pilot, the pattern for new files; 12 pilots exist (TC-02 x7, TC-11 x2, TC-14 x3)
- `tests/uat/runner/run.py:24-27` -- exit codes; `:528-535` `results.json` shape (`run`, `scenarios[].verdict`, `reasons`, `review`)
- `tests/uat/runner/run.py:96-106`, `:266-268`, `capture.py:42-44,86-89` -- Show All step: a refusal raises `CuaError`, the scenario is `ESCALATE`; probe confirmation `_active_shapes_shown` (`run.py:65-69`)
- `tests/uat/run/2026-10-03-04/report.md:37-389` -- per-TC tables `Scenario | Priority | Verdict | Evidence | Note`, verdict words at `:32`; Gate 1 summary `:373-389` (251: 190 PASS, 24 PARTIAL, 34 FAIL, 2 BLOCKED, 1 SKIP); findings `:478-512`; disputed `:514-520`
- `tests/uat/run/2026-10-03-04/evidence/tc-NN-results.json` -- per-TC verdict copies; prefer over parsing markdown when complete
- `_bmad-output/implementation-artifacts/spec-10-7-edit-inventory.md:21-299` and `spec-10-7-uat-suite-and-harness-maintenance.md:96-98,178` -- 10.7 test-case edits and old to new id moves (TC-99-07 to TC-11-19, TC-99-08 to TC-01-15, TC-99-03 to TC-10-03)
- `_bmad-output/implementation-artifacts/sprint-status.yaml:161-168` -- Stories 10.1-10.7 done; finding to story map is in each 10.x spec
- `tests/uat/run/2026-10-04-01`, `2026-10-05-01`, `2026-10-08-02` -- partial re-runs after 10.1, 10.4, Epic 11; supporting evidence for `product fixed`
- Not runner-expressible (from the test cases): H1 host (TC-09-01/02/15/19..22, TC-10-01/02/05/07..11, TC-11-01..04 part), raw RPC (TC-01-06/07/08/11, TC-10-03/04/13/14), kills (TC-01-12/14, TC-10-12, TC-12-15), logs (TC-01-07/08/13), GUI actions (most of TC-12, TC-13)
- Do not edit `tests/uat/run/2026-10-03-04/*`, `tests/uat/testcases/TC-*.md`, `src/freecad_buddy`

## Tasks & Acceptance

**Execution:**
- [x] `tests/uat/scenarios/tc-*.json` -- encode the D2 subset; one file per scenario, named by id; scenario steps follow the current test-case text -- AC9, D2
- [x] `tests/uat/runner/compare.py` -- read the old verdicts (`evidence/tc-NN-results.json`, else `report.md` tables) and a runner `results.json`, apply the verdict map, write `replay.md` rows `same | differs | not covered | not encoded | new | removed`, exit 2 on an unparsed row; class, reason and explanation come from a `replay-notes.json` the agent writes -- AC9
- [x] `tests/uat/runner/run.py`, `capture.py` -- D3 retry of Show All delivery, attempt count in the step record -- D3
- [x] `tests/external/test_uat_runner.py` -- every matrix row for `compare.py` and D3; schema validation of every committed scenario file -- AC9
- [x] `tests/uat/run/<date>-NN/` -- live replay: `results.json`, `summary.md`, captures, `replay-notes.json`, `replay.md`, `report.md` with the D4 calibration read and pixel disagreement counts -- AC9, D4
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- mark the part V, Show All and pixel false-alarm entries resolved with the replay run id -- consistency
- [x] `tests/uat/runner/README.md` -- `compare.py` usage -- consistency

**Acceptance Criteria:**
- Given the committed replay report, when read, then every scenario of TC-01..TC-14 at `bece7ac` and every current scenario has one row, and no row is `unexplained`.
- Given the live replay, when it ends, then no FreeCAD started by the runner remains, `:8765` is free, and the developer `user.cfg` is unchanged.

## Implementation Notes

- Encoding: 33 new scenario files plus the 12 pilots (45). Per test case (old FAIL / PASS-PARTIAL encoded): TC-01 0/0, TC-02 1/3 (+6 partial pilots), TC-03 2/3, TC-04 0/3, TC-05 4/0, TC-06 1/3, TC-07 1/2, TC-08 1/3, TC-09 0/4, TC-10 0/0, TC-11 0/0 (+2 partial pilots), TC-12 0/1, TC-13 1/1, TC-14 0/3. Under 3 means fewer are runner-expressible: TC-05 old PASS each need a snapshot-folder file check or a != / membership Then; TC-07-04..21 read the exported file; TC-12 and TC-13 need GUI actions; TC-01, TC-10, TC-11 need H1, raw RPC, kills or logs.
- `compare.py` takes `left_out` per id in `replay-notes.json` (closed-set reason per Then) and prints it as `Not checked: ...` in the row, so a `same` row of a partly encoded scenario names what it did not check (team lead request). 35 rows carry it; the TC-06 render Thens the agent read are in the explanation instead.
- Old `BLOCKED` and `SKIP` (TC-06-10, TC-06-11, TC-13-17) have no comparison; `compare.py` gives them row `new`, as for an id with no old verdict.
- `capture.py` is unchanged: the `menu_path_unavailable` test is the constant `run.MENU_UNAVAILABLE`. D3 retries only a path with a probe effect (Show All); `Edit > Recompute` has no probe confirmation and is not retried. After a refusal the runner polls the probe every `POLL_S` for up to `4 * POLL_S` and delivers again only when the effect is still absent.
- Scenario fix before any live run: the four TC-06 files fit before their renders (TC-06 ordering rule), found by an audit of the files against the test-case text. After the live run, review removed two inequality checks encoded as an `approx` range (TC-02-12 `total_edges` >= 2, TC-03-13 `counts.PASS` >= 1); both are now `left_out` as `comparison op`. The committed run executed them (both passed); the run was not repeated.
- Live: a scratch run and then `tests/uat/run/2026-10-23-01`, same 45 verdicts (21 PASS, 1 FAIL, 23 ESCALATE `agent_check` only). The scratch run had one Show All refusal, delivered on attempt 2 (TC-02-04). TC-11-17 FAIL is the open deferred product finding (probe reads no active 3D view after the first `query_capabilities`). After each run: no FreeCAD, `:8765` free, developer `user.cfg` SHA-256 unchanged.
- `replay.md`: 255 rows, 32 same, 12 differs (7 `product fixed`, 5 `test case changed (10.7 edit)`; TC-05-15 is `test case changed` because 10.7 moved its When from the Pad Length edit to a fillet radius edit), 174 not covered, 30 not encoded, 7 new, 0 removed, 0 unexplained.
- D4: the agent read all 45 captures and the 13 TC-06 render copies. 32 pixel-checked scenarios: the agent judged the visual Then met on 27, in part on 2 (TC-03-07, TC-03-20), not from the capture on 2 (TC-03-13, TC-12-07); 1 pixel false alarm (TC-11-17); 0 misses. 13 scenarios have a visual Then the capture cannot settle and 2 are settled in part: their `agent_check` asks for a live action the replay did not take (GUI Fit All, Sketcher edit mode, a capture before the save or between steps, the MCP render kept); that follow-up is left to Story 10.8.

## Spec Change Log

## Review Triage Log

| # | Layer | Finding | Verdict | Evidence | Route |
|---|-------|---------|---------|----------|-------|
| 1 | verification | `_agent_check_only` disqualifiers `disagreements`, `findings`, `capture=None` untested | low | only negative case uses `errors`; deleting either guard leaves 139 tests green | patch |
| 2 | verification | `replay.md` summary line (counts, `Unexplained: N`) untested | low | no assertion on `render` output line; report and deferred-work quote it | patch |
| 3 | verification, edge, blind | empty or wrong `--testcases` folder: every old id `removed`, exit 0 | medium | `current_ids` returns `[]`; `removed` rows get `REMOVED_DEFAULT`, class `-` | patch |
| 4 | edge | `removed` row never `unexplained`, not checked against edit inventory | low | 0 removed rows; check adds a file read and branch | reject |
| 5 | verification, edge, blind | malformed `results.json`, evidence JSON or notes raise uncaught, exit 1 not 2 | low | inputs are runner- and agent-written; fix adds type guards | reject |
| 6 | edge, blind | note for unknown id, `coverage` on replayed id, `class` on non-`differs` row ignored | low | a row the note should explain still reads `unexplained`, exit 1 | reject |
| 7 | edge | old verdict word outside the five is compared | low | such a row reads `differs` with no class, `unexplained`, exit 1 | reject |
| 8 | edge | same id in two report tables, last wins | false | findings rows start `| F-`; TC-99 filtered; all 14 `tc-NN-results.json` exist and win over `report.md` | reject |
| 9 | edge | evidence JSON omits ids `report.md` lists, ids read `new` | false | the 7 `new` rows are the 4 10.7 additions and 3 `BLOCKED`/`SKIP`; none omitted | reject |
| 10 | edge | cp1252 console breaks the refusal print | maybe-false | needs a non-ASCII refusal on a cp1252 console; low if true | reject |
| 11 | edge | stale `replay.md` stays after an exit-2 compare | low | operator re-runs; churn | reject |
| 12 | edge, blind | Show All retry has no pause between attempts; docstring claims a late effect is not resent | medium | `run.py` reads the probe once right after the refusal, then delivers again at once | patch |
| 13 | edge | probe raise in the refusal branch hides the refusal text | low | rare; message only | reject |
| 14 | edge | refusal over 500 chars hides `menu_path_unavailable` | maybe-false | code appears near the start of the JSON; low if true | reject |
| 15 | blind | calibration "31 agree" counts NOT JUDGED (TC-03-13, TC-12-07) and PARTIAL (TC-03-07, TC-03-20) | medium | `report.md` agent review list; same number in `deferred-work.md` resolution | patch |
| 16 | blind | `agent_check`-only ESCALATE counts `same` with no agent result | false | frozen verdict map defines it; AC9 covers deterministic Thens; `report.md` lists each NOT JUDGED id | reject |
| 17 | blind | no deferred-work entry for the 30 `not encoded` ids and the 15 open agent checks handed to 10.8 | medium | `deferred-work.md` diff adds only `resolution:` lines | patch |
| 18 | blind | TC-06-03/04/05/07 `left_out` says the renders are not checked; the agent read them | low | `replay.md:109-113` against `report.md` agent review | patch |
| 19 | blind | `replay.md` header names `3ca2add`, hides `git_dirty: true` | low | `render` prints commit only | patch |
| 20 | verification, blind | live D3 refusal only in the scratch run | low | disclosed in `report.md` and the resolution text; unit tests cover the branches | reject |
| 21 | blind | `tc-03-13.json` encodes `counts.PASS >= 1` as `approx 50.5 ± 49.5` | medium | fails a correct product above 100; the Then is already in `left_out` | patch |
| 22 | blind | set Thens encoded by fixed index are order-sensitive | low | listed in `left_out` as `comparison op`; MCP order is deterministic | reject |
| 23 | blind | `new` row with runner FAIL has class `-` | low | TC-11-17 row explains it; `bugs.md` B1 | reject |
| 24 | blind | `results.json`, captures, renders missing from the run folder | false | present on disk and not gitignored; the review diff left binaries and `results.json` out | reject |
| 25 | blind | `summary.md` writes absolute capture paths | low | part R runner behaviour, not this change | reject |
| 26 | blind | `compare.main` untested for empty `--testcases` | low | no test; pairs with 3 | patch |
| 27 | blind | "runner-expressible" spelling, `README.md:120` not wrapped | low | direct correction outside the frozen block | patch |
| 28 | blind | `class` holds one finding id | low | other ids are in the explanation | reject |
| 29 | step-03 audit | TC-05-15 classed `product fixed (F-13)` though 10.7 changed its When | medium | old FAIL: `Length` edit broke the fillet link; replay edits the fillet radius, so F-13's path is not exercised | patch |
| 30 | step-03 audit | 25 new files have CRLF line endings | low | git warnings on the review diff | patch |

## Verification

**Commands:**
- `uv run pytest tests/external/test_uat_runner.py` -- expected: all pass, every scenario file validates
- `uv run pytest tests/external` -- expected: no new failure
- `uv run ruff check .` -- expected: clean
- `uv run python tests/uat/runner/run.py tests/uat/scenarios --out tests/uat/run/<date>-NN` -- expected: a verdict per scenario, exit 0 or 1
- `uv run python tests/uat/runner/compare.py tests/uat/run/2026-10-03-04 tests/uat/run/<date>-NN` -- expected: `replay.md` written, no `unexplained` row

**Manual checks:**
- Read every replay capture (D4); confirm each verdict matches the pixels.
