---
title: 'Story 10.8 (goal 3): UAT Gate 1 Run'
type: 'chore'
created: '2026-10-23'
status: 'in-progress'
baseline_commit: '3025e7c60b41d69cb93fdf39d265274202947566'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/tests/uat/test-plan.md'
  - '{project-root}/tests/uat/README.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md'
  - '{project-root}/tests/uat/runner/README.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 10 closes only when a full UAT run on FreeCAD 1.1.4 shows Gate 1 green (Critical 100 %, High >= 95 %), Gate 2 matching its documented deviations, and the G3 live replay unchanged (epics.md Story 10.8 AC1). No full run has happened since 2026-10-03-04, and Stories 10.1-10.7b changed the product, the test cases and the harness since then.

**Approach:** Run all 255 scenarios of TC-01..TC-14 and the 5 of TC-99 on FreeCAD 1.1.4: the 72 scenario files through `tests/uat/runner/run.py` with a drawn seed, the other 183 by agent through MCP and `cua-driver`, then the G3 replay. Write one run folder `tests/uat/run/2026-10-23-02/` (or the next free id) with `report.md` in the 2026-10-03-04 layout, `bugs.md`, `evidence/` and the runner output, and commit it.

## Decisions

- **D1 — G3 replay in both forms.** The GUI replay with `tests/uat/run/2026-10-03-04/evidence/g3_gui_replay.py` on the run's FreeCAD 1.1.4, and the headless scorer `benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.1.x --check --frames-check benchmarks/g3/fault-injection/frames-reference.json` on 1.1.4. "Unchanged" means 4/4 controls OK, 10/10 reverted OK, 10/10 planted DETECTED (the `g3r-2026-10-08-1.1.3` scores: sensitivity 1.0, false alarm 0.0), and every anchor frame equal to `frames-reference.json`. `--check` writes no `validators.yaml`.
- **D2 — The run reports what it finds.** Each FAIL is a finding in `bugs.md` and one new `deferred-work.md` entry. Gate 1 is reported red when its thresholds miss, and Story 10.8 stays open. Fixes are separate changes; after them the affected test cases are re-run into a new run folder, which the gate then counts. No product fix inside this run.

## Boundaries & Constraints

**Always:**
- Test-plan §9 governs runner captures: the agent reads the review set and every `ESCALATE`, including each `agent_check`. A before-capture or between-step Given named in an `agent_check` is taken by re-running that scenario's steps by MCP up to the named step and capturing there (deferred-work goal 3 rule).
- Every agent-driven scenario closes with a fit and a `cua-driver` capture that the agent reads (§3 rule 4). No MCP field, status or render stands as visual evidence.
- FreeCAD is started non-elevated with a temporary `-u` profile (Story 10.7b AC7), so the developer's `user.cfg` is unchanged; record its SHA-256 before and after.
- A failed check is a finding with request, output and `file:line`, never a retry to get a PASS. Every runner run and every FreeCAD launch made for the gate is listed in `report.md` with its run folder or log line.
- `report.md` verdicts are final; Gate 1 is computed from them by priority.
- Never open `benchmarks/*/heldout`. No edit to `src/freecad_buddy`, the runner or the test cases during the run.

**Never:**
- Report a scenario PASS whose visual Then was skipped or inferred.
- Change gate thresholds or the §9 review rule.

</frozen-after-approval>

## Code Map

- `tests/uat/runner/run.py` -- `uv run python tests/uat/runner/run.py tests/uat/scenarios --out <run>/runner`; no `--seed` (§9 gate rule); exit 0/1/2/3
- `tests/uat/scenarios/` -- 72 files; 2026-10-23-01 `replay-notes.json` and spec-10-8-b notes list the Thens each partial file hands to `agent_check`
- `tests/uat/testcases/TC-01..TC-14`, `TC-99` -- 255 + 5 scenarios; 174 Critical, 67 High, 14 Medium; agent-driven per TC: 01:15, 02:8, 03:6, 04:14, 05:14, 06:8, 07:18, 08:10, 09:18, 10:14, 11:17, 12:14, 13:16, 14:11
- H1 (headless stdio host) scenarios: TC-06-11, TC-08-05/18, TC-09-01/02/15/19-22, TC-10-01/02/05/07-11, 14 in TC-11, TC-14-09/12/14, TC-99-04/06
- `.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md:38-131,227-240` -- preflight, non-elevated `cua-driver serve`, `_automation/uat/launch_env.sh`, launch readiness, shutdown
- `scripts/automation/uat_watchdog.py` -- between test cases; a surviving `FCB_TMP_snap_*` stops the run (`tests/uat/README.md:91-105`)
- `tests/uat/run/2026-10-03-04/report.md` -- layout: Status, Build banner, Harness gate, Execution notes, `## TC-01`..`## TC-14` (Scenario | Priority | Verdict | Evidence | Note), TC-99 (Scenario | AD | Verdict | Observed), Gate 1 summary (TC | Scenarios | PASS | PARTIAL | FAIL | BLOCKED | SKIP + by priority), Gate 2, G3 replay, Findings, Human interventions, Teardown
- `benchmarks/g3/fault-injection/score_g3_replay.py`, `frames-reference.json`; `benchmarks/_registry/validators.yaml:175-189`; `.github/workflows/ci.yml:138-145`
- `tests/uat/test-plan.md:342-441` -- Gate 1 and Gate 2 rules

## Tasks & Acceptance

**Execution:**
- [ ] preflight: no FreeCAD, `:8765` free, `cua-driver` daemon non-elevated, `user.cfg` SHA-256, `git status` clean -- harness
- [ ] runner run of the 72 files; §9 agent review of the review set and every ESCALATE -- §9
- [ ] agent-driven run of the 183 other scenarios, test case by test case, watchdog between test cases -- AC1
- [ ] TC-99 run; compare with the Gate 2 documented deviations -- AC1
- [ ] G3 replay per D1 -- AC1
- [ ] `tests/uat/run/<id>/report.md`, `bugs.md`, `evidence/`; Gate 1 and Gate 2 tables; per D2 for any FAIL -- AC1
- [ ] `_bmad-output/implementation-artifacts/deferred-work.md` -- resolve the goal 3 entry, or add one entry per open finding -- consistency

**Acceptance Criteria:**
- Given the committed run folder, when `report.md` is read, then every one of the 260 scenarios has one verdict with evidence, Gate 1 and Gate 2 are computed from those verdicts, and the G3 result is stated against its reference.
- Given the run's end, when the machine is checked, then no FreeCAD started for the run remains, `:8765` is free, and the developer `user.cfg` SHA-256 is unchanged.

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Verification

**Manual checks:**
- Every agent-driven capture and every §9 review-set capture is read and described in `report.md`.
- Gate counts in `report.md` match the per-TC tables.
