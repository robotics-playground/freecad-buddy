---
title: 'Story 10.8 (goal 2): Encode the Remaining Runner Scenarios'
type: 'chore'
created: '2026-10-23'
status: 'done'
baseline_commit: '5939504d885dd25dc19438695f5f4fe73e2f8391'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-10-7b-r-scripted-uat-runner.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-10-7b-v-replay-run-2026-10-03-04.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The part V replay left 30 runner-expressible scenarios with no scenario file (`tests/uat/run/2026-10-23-01/replay-notes.json`, `coverage: not encoded`). Without them the Story 10.8 gate run executes those scenarios by agent instead of by script.

**Approach:** Write one scenario file per id in `tests/uat/scenarios/`, following the current test-case text and the part V file pattern. Prove every new file runs live on FreeCAD 1.1.4 through the runner before the gate run.

## Decisions

- **D1 — Partial files hand their left-out Thens to the agent.** Each existing scenario file that encodes only part of its deterministic Thens (the 35 ids with `left_out` in `tests/uat/run/2026-10-23-01/replay-notes.json`) gets an `agent_check` naming every left-out Then and its reason. When the file already has an `agent_check`, the text is appended. The runner makes the scenario `ESCALATE`, so test-plan §9 has the agent check those Thens in the gate run; a scripted `PASS` never stands for a Then the file does not check.

Ids: TC-03-01, -02, -03, -04, -08, -10, -11, -12, -14, -16, -18, -21; TC-04-01, -08, -11, -12, -14, -18, -20; TC-08-04, -07, -09, -10, -11, -15, -16; TC-09-06; TC-14-04, -06, -08.

## Boundaries & Constraints

**Always:**
- Every deterministic Then of an encoded scenario is in the file. A Then the schema cannot state means the id is not runner-expressible: it is not encoded, and the Implementation Notes name it with its closed-set reason.
- A Then is never encoded as an approximation of another check (no `approx` range standing in for an inequality, no fixed index standing in for a set check).
- Each file ends with a fit before its capture, per the test-case ordering rules.
- A live run that finds a file defect (fixture, path, field name) is fixed in the file; a product defect found live is a finding in the Implementation Notes, not edited around.

**Never:**
- Change the runner, the probe, the scenario schema or the test-case markdown.
- Commit the validation run folder; the gate run is the committed record.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Valid file | each new file | `scenario.load_all` accepts it; file name is the lower-cased id | invalid file: test fails naming file and key |
| Live run | the 30 files on FreeCAD 1.1.4 | every scenario has a verdict and a capture; no run error | a FAIL is a product finding or a file defect, never retried |
| Not expressible | a Then needs a check kind the schema lacks | id not encoded; named in Implementation Notes with its reason | N/A |

</frozen-after-approval>

## Code Map

- `tests/uat/runner/scenario.py:3-57` -- schema; `$PROJECT_ROOT`, `$RUN_DIR`, `$step.path` references
- `tests/uat/scenarios/tc-05-15.json`, `tc-03-07.json` -- part V patterns for preview/confirm (`AUTO_APPROVE=0` launch) and sketch fixtures
- `tests/uat/testcases/TC-03-*.md`, `TC-04-*.md`, `TC-08-*.md`, `TC-09-*.md`, `TC-14-*.md` -- sources; each scenario's Given, When, Then
- `tests/uat/run/2026-10-23-01/replay-notes.json` -- the 30 `not encoded` ids
- `tests/external/test_uat_runner.py` -- `test_Should_validate_every_file_When_the_committed_scenarios_are_read` and the heading test already cover every committed file
- `tests/uat/runner/README.md` -- live run command; preflight refuses while another FreeCAD runs

## Tasks & Acceptance

**Execution:**
- [x] `tests/uat/scenarios/tc-*.json` -- one file per expressible id above -- goal 2
- [x] live validation run of the new files into a scratch folder; fix file defects; record verdicts, captures read and findings in Implementation Notes -- goal 2
- [x] the 35 partial files -- `agent_check` per D1, text taken from `left_out` -- D1
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- mark the goal 2 entry resolved -- consistency

**Acceptance Criteria:**
- Given the committed scenario folder, when `uv run pytest tests/external/test_uat_runner.py` runs, then every file validates.
- Given the live validation run, when it ends, then every new scenario has a verdict and a capture the agent read, no FreeCAD started by the runner remains, and `:8765` is free.

## Implementation Notes

- Encoded: 27 new files (TC-03 x10, TC-04 x7, TC-08 x7, TC-09 x1, TC-14 x2); the committed folder holds 72. Not encoded, reason `comparison op`:
  - TC-03-01: its Then "query_placement reports a rotation distinct from PlateProfileXY" is an inequality between two step results, and the schema has no not-equal check.
  - TC-03-04: its Then "the same envelope carries a passed check with id=sketch.fully_constrained and expected=true" is a set check; the schema selects list items only by `name` or index, and an index stands in for a set check.
  - TC-14-04: its Then "the ratio on the `framing:` line is `>= 0.85`" is an inequality; a digit-range regex on the line stands in for it, and the schema has no inequality check. The drafted file ran (PASS) and is removed.
- D1: the 35 `left_out` files carry `The script does not check these Thens; check each one in the gate run: <then> (<reason>); ...`, appended after an existing `agent_check`.
- Encoding rules used in the new files:
  - Fixtures the test case leaves open are built with typed tools and checked where the Given has a verify: plates, holes and patterns follow the 2026-10-03-04 evidence scripts (`tc04lib.py`); the TC-03-03 cylindrical face comes from the golden `cylinder-r5-h20.FCStd`, opened and closed inside the scenario.
  - A Then that would change the model the visual Then judges runs in a second document that the scenario closes: TC-03-10 cascade sketch, TC-04-11 default `originals`, TC-04-18 valid pattern, TC-08-09/15/16 fresh token.
  - "Same objects as the Given" (TC-03-21, TC-04-18): the tree's framing line changes between reads, so both reads must match one regex of the full object listing after the framing line (TC-04-18), or the object-count line plus the object line (TC-03-21).
  - TC-14-06 and TC-14-08 read "ratio unchanged" as `framing.ratio` of a structured read on the same document, the verdict the tree's `framing:` line renders. TC-14 files end without a final fit: the fit is the action under test (TC-14 ordering rule).
  - "Schema refusal or product message" Thens (TC-08-15, TC-08-16, TC-14-08) encode the schema-refusal branch the product takes.
  - Fixed positions are kept only where the Then names one measured fact of a list the product builds in a fixed literal order: TC-04-14 `checks.1` (`shape.bbox`) and TC-04-20 `checks.2` (`shape.solid_count`), `verify.py:193-199`, each paired with its `id`.
  - TC-03-12 encodes "no `sketch.partially_redundant` warning" as `warnings == []`: that warning is the only one `verify_sketch` can emit (`verify.py:397-406`).
  - TC-03-02 does not assert the fit status: a document holding only an empty sketch returns `SPEC_FAILED view_fit.nothing_to_frame`, and the visual Then's fallback (GUI Fit All) is in its `agent_check`.
- Live validation, FreeCAD 1.1.4, HEAD `5939504` (dirty: these files), scratch runs outside the repo:
  - Run 1, all 29 files, 2 launch groups (default x22, `FREECAD_BUDDY_AUTO_APPROVE=0` x7), about 5 min: 3 PASS, 2 FAIL, 24 ESCALATE (`agent_check` only), no run error. TC-04-01 Show All was delivered on attempt 2.
  - File defects fixed, form only: TC-04-18 `huge` refusal now a regex (product adds `, got 5000`; the Then says "naming"); TC-04-18 `TREE_PLACEHOLDER` replaced by the "same objects as the precondition" listing check on both reads, with no-line checks for the four names the Then lists. Before the run, quantity readbacks were set to the product's `str` form (`"25.0 mm"`, `queries.py:222-226`).
  - Run 2, the changed TC-04-18 (and a TC-03-04 draft since removed): ESCALATE (`agent_check` only).
  - TC-03-04 was drafted and ran (run 1 ESCALATE `agent_check` only, with its set Then read at `checks.0`; run 2 with that Then in `agent_check`). Both drafts break Boundaries (an index standing in for a set check, then a Then left out of a new file), so the file is removed and the id is not encoded (above).
  - Final verdicts of the 27 committed files (as run, before the review fixes below): PASS TC-04-01, TC-04-12; FAIL TC-08-07; every other file ESCALATE with only its `agent_check`. After each run: no FreeCAD, nothing listening on `:8765`.
- TC-08-07 FAIL, a stale test-case premise, not a product regression: `feature_body_create { name: "Probe" }` moves the document fingerprint (`fingerprint_before` `b083c60b…`, `fingerprint_after` `5d575dcd…`), while the Then says an empty body leaves the digest unchanged. `usecases/fingerprint.py:402-405` records an object with a null `Shape` (an empty Body) as the hash of empty bytes plus zeroed mass properties, so adding an empty body moves the digest by design since Story 10.3 (commit `a1ef9ab`, 2026-10-05); run 2026-10-03-04 predates that and measured equal digests. The replay refusal itself is correct (`has already authorized a mutation`, not a fingerprint complaint). The file keeps the test-case expectation; this goal does not change the test-case text, so the scenario stays FAIL until the test case is corrected.
- Review fixes, offline, not re-run on FreeCAD: TC-08-04 also checks that `diff.validity.explanation` names `Fillet`; TC-14-06 and TC-14-08 also check `ratio_before` `framing.fits` is `true`, so the ratio equality cannot pass as `null == null`; TC-08-11's plant keeps an earlier saved `fingerprint` (`getattr(f, "_saved", f.fingerprint)`); TC-04-14 reads the bbox as three `approx` checks at 0.1 %; TC-05-14's two-build `agent_check` items say `not applicable on a single-build run; record N/A`; TC-09-17's `agent_check` names `_RECOMPUTE_ERROR_STATES` in `usecases/verify.py` instead of a line number.
- Captures read (all 29 run, 27 committed): sketch-only scenarios show the black wire outside edit mode as expected (edit-mode Thens stay with the agent); TC-04-08 shows one small counterbored hole; TC-04-11 two holes on the plate and six on the disc; TC-04-12 two separate blocks per datum and plane mirror, one joined block for the face mirror, the MirrorPlane datum drawn; TC-04-18 one hole; TC-04-20 one round and one bevel on different corners; TC-08 captures show the expected pad or flat sketch; TC-14-04 the 800 mm bar spans the view height with both ends inside; TC-14-06 DocB in the title bar and its tab active. No error dialog in any capture.

## Spec Change Log

## Review Triage Log

| # | Layer | Finding | Verdict | Evidence | Route |
|---|-------|---------|---------|----------|-------|
| 1 | verification | `tc-08-04` checks the preview explanation with `\S`; the Then asks that it name the failing check | medium | regex `\S` passes any non-empty text; 2026-10-03-04 evidence names `Fillet` | patch |
| 2 | blind, edge | `tc-14-04` encodes `ratio >= 0.85` as a digit-range regex; it also misses a 2-decimal `0.9` | medium | Boundaries forbid a range standing in for an inequality; the id is then not runner-expressible | patch: delete file, record not encoded |
| 3 | edge | `tc-14-06`/`tc-14-08` ratio equality passes as `null == null` when framing is unavailable | medium | equality alone, no check that `ratio_before.framing.fits` is true | patch |
| 4 | edge | `tc-08-11` plant saves `_saved` unconditionally; a second plant after a missed restore loses the real `fingerprint` | low | `f._saved = f.fingerprint` | patch: `getattr(f, "_saved", f.fingerprint)` |
| 5 | edge | `tc-08-11` step raising before restore leaves the plant for later scenarios of the group | low | needs a timeout or proxy end, which already breaks the group | reject |
| 6 | verification, blind, edge | TC-08-07 FAILs on every run on a stale test-case premise; no open item tracks the test-case fix | medium | only in the closed goal 2 resolution text | patch: deferred-work entry |
| 7 | blind | no open item for the schema's missing not-equal and set checks (TC-03-01, TC-03-04, TC-14-04) | low | only in Implementation Notes | patch: deferred-work entry |
| 8 | blind | before-capture Givens in `agent_check` cannot be taken after the run; files do not say how | medium | runner hands over after the last step; only `tc-12-07` says to re-run by hand | patch: rule in the goal 3 deferred entry |
| 9 | blind | D1 turns 19 PASS-able files into ESCALATE only | false | the user chose D1 with that cost stated (about 35 more agent reads) | reject |
| 10 | blind | the 35 part V files keep fixed-index set assertions | low | part V triage #22; MCP order is deterministic; the Thens are also in `agent_check` | reject |
| 11 | blind | some reason labels copied from `left_out` are wrong (`tc-02-17`, `tc-02-12`) | low | the agent reads the Then text; label is advisory | reject |
| 12 | blind | appended `agent_check` text repeats the file's own text (`tc-02-12/15/17`, `tc-12-07`) | low | cosmetic | reject |
| 13 | blind | `tc-05-14` hands over CONDITIONAL two-build Thens with no single-build outcome | low | the agent cannot resolve them on one build | patch: say not applicable on a single-build run |
| 14 | blind | `tc-04-14` compares a measured bbox with exact `equals` | low | `tc-04-11/12` use per-component `approx` | patch |
| 15 | blind, edge | `tc-04-12` has no `pixel` block and no criterion | false | a centre sample falls in the gap of two separated blocks (README limit); §9 `no pixel check` puts it in the agent's review set | reject |
| 16 | blind | `tc-04-18` exact escaped tree listing is FreeCAD-output-specific | low | "same objects" is an exact listing by definition | reject |
| 17 | blind | `tc-09-17` `agent_check` cites `verify.py:22` | low | line numbers go stale; name the symbol | patch |

## Verification

**Commands:**
- `uv run pytest tests/external/test_uat_runner.py` -- expected: all pass
- `uv run ruff check .` -- expected: clean
- `uv run python tests/uat/runner/run.py <new files> --out <scratch dir>` -- expected: a verdict and capture per scenario, no run error
