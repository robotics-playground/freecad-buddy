---
title: 'Story 10.7b (part S): UAT Review Sampling Rule'
type: 'chore'
created: '2026-10-23'
status: 'done'
baseline_commit: 'd78ad033ab0b67df9b8172839642dda174ab850b'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-10-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-10-7b-r-scripted-uat-runner.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `tests/uat/test-plan.md` requires the agent to read the window capture of every scenario. With the part R runner, the scripted pixel check grades each capture against probe geometry, so a full read of about 250 captures costs agent time and adds little. Story 10.7b AC8 replaces the full read with a sampling rule.

**Approach:** Update `tests/uat/test-plan.md` §9 to the AC8 rule: the agent reads the capture for every `FAIL`, every probe/MCP disagreement, the first scenario of each test case and a random 20 % sample of the rest; the scripted pixel check grades every other scenario against its stored capture. Align every other UAT text that states the old "agent reads every capture" rule, so the suite does not contradict itself.

Scope is part S of Story 10.7b (epics.md AC8). Part V (replay) stays deferred.

## Decisions

- **D1 — Every reviewed capture gets a complete visual comparison.** The sampling rule reduces how many captures the agent reads, never how it reads them. For each capture in the review set the agent applies the §3 rule 4 standard to every visual `Then` of the scenario: reads the image, states what is on screen (part present, whole, not clipped, the right shape, no dialog), compares it with the scenario's expected visual and with the golden capture when one exists, and records that judgement per scenario in `report.md`. A glance or a judgement that cites an MCP field is not a review.
- **D2 — The runner draws the review set.** `run.py` writes the review set before the agent sees any capture (AD-13). Reasons: `fail`, `escalate`, `no pixel check` (a scenario file with no `pixel` block), `first of TC-xx`, `sample`. The sample is 20 % of the remaining scenarios, rounded up, drawn with a seed recorded in `results.json`.
- **D3 — `first of TC-xx` is the first `PASS` scenario of each test case by id** that is not already in, so each test case has at least one agent-read `PASS`.
- **D4 — The pixel check proves its sensitivity (AD-13).** An offline planted-fault set of synthetic captures: empty view, part clipped at an edge, part moved off its sample points, part too small; plus clean controls. It must detect every fault with no false alarm. §9 states what the pixel check does not see (dialogs, wrong shape, colour).
- **D5 — Seed source.** `results.json` records `sample_seed` and `sample_seed_source` (`drawn` or `given`). A gate run (Story 10.8) uses a drawn seed; `--seed` is for debugging and replay only.

## Boundaries & Constraints

**Always:**
- The rule applies only to scenarios the runner executes from a scenario file. A scenario with no scenario file keeps the full agent read.
- Every scenario still has a capture. A scripted `PASS` never stands without its capture (AC6).
- An `ESCALATE` (including every `agent_check`) is read by the agent, the same as a `FAIL`.
- When the agent's reading of a sampled capture contradicts a scripted `PASS`, the window wins: the scenario is `FAIL`, the pixel-check defect is a finding in `bugs.md`, and the agent reads every remaining capture of that test case.
- Past run reports keep their text.

**Never:**
- Let an MCP field, status or `query_screenshot` render grade a visual `Then` (rank 3 in §3 stays claims under test).
- Change Gate 1 or Gate 2 thresholds.
- Change runner checks, verdict rules or exit codes.
- Edit `CLAUDE.md`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Mixed run | TC-02 x7 (1 FAIL), TC-14 x3 (1 ESCALATE) | review: the FAIL, the ESCALATE, first PASS of TC-02 and of TC-14 (if not already in), then 20 % of the remaining PASS rounded up | N/A |
| No pixel block | PASS scenario, no `pixel`, no `agent_check` | reason `no pixel check` | N/A |
| First is FAIL | first TC-02 scenario by id is FAIL, second is PASS | first: `fail`; second: `first of TC-02` | N/A |
| TC with no PASS | every TC-14 scenario FAIL or ESCALATE | no `first of TC-14` | N/A |
| Replay | same scenarios and verdicts, `--seed` = past `sample_seed` | same review set, `sample_seed_source: given` | N/A |
| Default seed | no `--seed` | seed drawn, `sample_seed_source: drawn`; that seed redraws the same set | N/A |
| All in already | every scenario is in by another reason | sample empty | N/A |
| Bad seed | `--seed abc` | argparse refuses, exit 2, nothing launched | message names the value |
| Pixel faults | the planted-fault set | every fault detected, 0 false alarms on controls | a miss fails the test |

</frozen-after-approval>

## Code Map

- `tests/uat/runner/run.py:198-243` -- `check_pixel(config, snapshot, image, window)`: findings on `view`, `samples.*`, `extent.fraction`, `extent.touches_edge`. The fault set calls it unchanged
- `tests/uat/runner/run.py:360-390` -- `run()` returns records in scenario order; each record has `id`, `tc`, `verdict`, `capture`
- `tests/uat/runner/run.py:413-440` -- `summary()`; add `## Agent review` after the escalation queue, with the seed and its source
- `tests/uat/runner/run.py:440` -- `main()`: add `--seed` (`type=int`); write `sample_seed`, `sample_seed_source` into `run` metadata
- `tests/uat/runner/png.py:14` -- decoded image class (`width`, `height`, `channels`, `rows`); the fault set builds images in memory
- `tests/external/test_uat_runner.py:47` (`_encode_png`), `_scene()` -- synthetic capture helpers to reuse in tests
- `tests/uat/probe/run_faults.py`, `tests/uat/probe/faults/cases.json` -- precedent for a fault set that prints detected and false-alarm counts
- `tests/uat/test-plan.md:15-19` (§1), `:95-102` (§3 rule 4), `:136-169` (evidence ranks), `:327-343` (§9) -- old full-read rule
- `tests/uat/README.md:32-36`, `:78-80` (rule 8), Reporting section -- old rule; `report.md` is the run's verdict record
- `tests/uat/runner/README.md:1-6`, `:108-127` -- "agent gets only the escalation queue"; `results.json` fields
- Iteration-1 diff `C:/Users/thuan/AppData/Local/Temp/claude/D--Work-Personal-Sources-freecad-buddy/1d05bc05-6255-4b66-ad49-2004ccbeed34/scratchpad/part-s-iteration-1.patch` is a usable start for the docs and `mark_review`; it lacks D2's fifth reason, D3, D4, D5 and the carried fixes
- Do not edit `tests/uat/run/*` or `testcases/TC-*.md`

## Tasks & Acceptance

**Execution:**
- [x] `tests/uat/runner/run.py` -- `mark_review(results, items, seed)` per D2/D3: sample = `rest` ranked by SHA-256 of `f"{seed}:{id}"`, first `ceil(n * 20 / 100)` (stable across Python versions and argument order); `--seed`; `sample_seed`, `sample_seed_source`; `summary.md` `## Agent review` lists seed, source and one line per reviewed scenario -- AC8, D5
- [x] `tests/uat/runner/pixel_faults.py` -- builds synthetic captures in memory, runs `check_pixel` on each case, prints detected and false-alarm counts, exits non-zero on a miss or a false alarm; cases per D4 plus 2 controls (flat and gradient background) -- D4
- [x] `tests/external/test_uat_runner.py` -- one test per matrix row; the pixel fault set passes -- AC8, D4
- [x] `tests/uat/test-plan.md` -- §9 rule with D1-D5, the Always rules, what the pixel check does not see, the `report.md` line per reviewed scenario (`id`, reason, what is on screen, verdict), `report.md` verdict is final over `results.json`, a reviewed scenario with no capture follows the AC6 ladder (agent captures through `cua-driver`); §1, §3 rule 4 and evidence ranks aligned; one sentence: §9 decides who reads runner captures over the per-test-case evidence tables -- AC8
- [x] `tests/uat/README.md` -- format summary and rule 8 point to §9 -- consistency
- [x] `tests/uat/runner/README.md` -- review set and reasons, `--seed` (same set only for same scenarios and verdicts), new `results.json` fields, `pixel_faults.py`; lines wrapped at 100 -- consistency

**Acceptance Criteria:**
- Given `test-plan.md`, when read top to bottom, then no sentence requires an agent read of every runner capture, and §9 states the five reasons, the pixel-check limits and the gate seed rule.
- Given both READMEs and the `run.py` docstring, when compared with §9, then none states a different rule.

## Implementation Notes

## Spec Change Log

## Review Triage Log

| # | Layer | Finding | Verdict | Evidence | Route |
|---|-------|---------|---------|----------|-------|
| 1 | blind, edge, verification | a PASS scenario with no `pixel` block and no `agent_check`, outside the review set, has a visual Then nothing grades, while the docs say the pixel check grades every other capture | medium | `run.py` runs `check_pixel` only `if "pixel" in item`; `verdict_of` gives `PASS`; `tc-02-01.json` has neither key | intent_gap (D2 fixes four reasons) |
| 2 | blind | the pixel check, now the only grader for most runner scenarios, has no planted-fault sensitivity proof (AD-13) | medium | no pixel fault fixtures under `tests/uat`; epic context AD-13 line | intent_gap |
| 3 | blind, edge | "first of TC-xx" is the first scenario in run order; the matrix says "first PASS of TC-02"; a test case can end with no agent-read PASS | medium | `mark_review` `first_of` ignores verdict; matrix row "Mixed run" | intent_gap (frozen wording ambiguous) |
| 4 | blind | operator can choose `--seed` and rerun until a doubtful capture leaves the sample; source of the seed not recorded | medium | `main()` accepts any int; `results.json` stores only `sample_seed` | intent_gap |
| 5 | verification | default-seed path (`--seed` omitted) untested: recorded seed not checked to reproduce the review set | medium | only `--seed 4242` test asserts `sample_seed` | patch (carry) |
| 6 | blind | docs equate the pixel check with an agent read; it checks sample points and extent only, not dialogs or shape | medium | `check_pixel` checks samples, `fraction`, `touches_edge` | patch (carry: state coverage in §9) |
| 7 | blind, edge | `--seed` "replays from a past results.json" overclaims: it re-runs the suite; same set only with same scenarios and verdicts | low | `main()` never reads `results.json` | patch (carry: wording) |
| 8 | blind | `random.Random(seed).sample` not guaranteed stable across Python versions; selection depends on list order | low | Python `random` docs guarantee only seeding and `random()` | patch (carry: rank by SHA-256 of seed and id) |
| 9 | edge | `first of TC-xx` follows argument order when files are passed one by one | low | `load_all` keeps argument order | patch (carry: first by id) |
| 10 | blind | reviewed scenario with no capture has no rule | low | `ESCALATE` no capture, `not_run` | patch (carry: §9 points to the AC6 ladder, agent captures through `cua-driver`) |
| 11 | blind | "window wins" leaves `results.json`/`summary.md` at PASS; record for Gate 1 not named | low | §9 text | patch (carry: `report.md` verdict is final, as `tests/uat/README.md` Reporting says) |
| 12 | blind | no required per-scenario review line in `report.md` | low | D1 names `report.md` but no format | patch (carry: one-line format in §9) |
| 13 | blind | `testcases/TC-*.md` keep the old rank-1 text | low | 13 hits in 10 files | patch (carry: precedence sentence in `test-plan.md`) |
| 14 | blind | seed absent from `summary.md` | low | `summary()` | patch (carry) |
| 15 | blind | `runner/README.md` bullet past the 100-column wrap | low | rewritten `scenarios` bullet | patch (carry) |
| 16 | blind | `epic-10-context.md` change outside scope | false | regenerated by this build's step 1 because a planning file was newer; required by the workflow | reject |
| 17 | blind | pixel-check defect may span every scenario with the same `pixel` config, not one test case | low | Always rule fixes the scope to one test case | reject (frozen; part of question for finding 2) |
| 18 | verification | no test that a different seed draws a different sample, or that two drawn seeds differ; a seed dropped from the hash or a constant drawn seed passes every test | medium | tests use one seed per comparison (`test_uat_runner.py` sample and replay tests) | patch |
| 19 | blind, edge | `"pixel": {}` passes validation and counts as pixel-checked; `check_pixel` then checks only the view, no sample | medium | `scenario.py:204-220` accepts `{}`; `mark_review` tests key presence only; test helper `_items` uses `{}` | patch (no `samples` = `no pixel check`) |
| 20 | edge | `## Agent review` follows "Empty: every scenario passed." with no blank line | low | `summary()` empty-queue branch | patch |
| 21 | blind | fault set has 4 faults and synthetic controls only; false-alarm rate on real FreeCAD captures (nav cube, axis, Tasks overlay) unmeasured | medium | `pixel_faults.py` CASES; no real capture is committed (part R D2) | defer (D4 fixes the set; real captures come with part V) |
| 22 | blind | fault set skips guard findings and capture scaling | false | guards and `Placement` scaling are covered by part R tests (`test_uat_runner.py:529` and the view None/clipped tests) | reject |
| 23 | blind | no rule when the agent sees a correct part on a scripted pixel `FAIL` | medium | §9 "window wins" covers only a contradicted `PASS` | patch (doc: window wins both ways for pixel findings; false alarm is a pixel-check finding) |
| 24 | blind | extra reads after a contradiction have no reason value for the `report.md` line | low | §9 line format lists the five runner reasons only | patch (doc: reason `test case re-read`) |
| 25 | blind | a `not_run` scenario cannot be judged by a window capture | low | `_not_run` gives `ESCALATE`, `capture: None`; §9 no-capture rule says capture the window | patch (doc: re-run the group first) |
| 26 | blind | golden difference is not a review reason | low | no golden is committed; D2 fixes the five reasons | reject |
| 27 | blind | gate seed rule not auditable: re-runs until a favourable draw leave no trace | medium | §9 seed rule has no reporting duty | patch (doc: `report.md` states `sample_seed`, its source, and every runner run made for the gate) |
| 28 | blind | spec Code Map narrates history and points to a scratchpad patch | low | fix edits this build's spec | reject |
| 29 | blind | `epic-10-context.md` lines lack citations | low | file is generated by the build's context compile; outside this change | reject |
| 30 | blind | `mark_review` raises `KeyError` for a record not in `items`; a test changed to per-id files | low | `main()` builds records from `items`, so the case is unreachable | reject |

## Verification

**Commands:**
- `uv run pytest tests/external/test_uat_runner.py` -- expected: all pass
- `uv run python tests/uat/runner/pixel_faults.py` -- expected: every fault detected, 0 false alarms, exit 0
- `uv run ruff check .` -- expected: clean
- `rg -n "not read|judges the visual, always|grades every other|grades the rest" tests/uat --glob '!run/**'` -- expected: every hit is consistent with §9

**Manual checks:**
- Read §1, §3 and §9 of `test-plan.md` and both READMEs in sequence; confirm one review rule.
