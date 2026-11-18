# Sprint Change Proposal 2026-11-18: Story 10.8 accepts a smoke run, not the full suite

## 1. Issue summary

Story 10.8 AC1 requires a full UAT run (TC-01..TC-14, TC-99, G3 replay) with Gate 1 green. The user chose a smoke run: "Just pick some main test case for smoke testing. I don't want to rerun whole uat test set again" (decision 45, 2026-11-18). The run `2026-11-18-01` followed that scope. AC1 as written is not met by it.

Trigger: Story 10-8, UAT run `2026-11-18-01`. Approval: the user, 2026-11-18 (decision 48, option "Change AC to smoke"). Scope: decisions 45 and 49.

Evidence (`tests/uat/run/2026-11-18-01/report.md`): 111 of 255 scenarios ran. 101 PASS, 10 FAIL. 0 product defects. 17 of 17 fix areas PASS. G3 replay unchanged. The 10 FAIL are test-case defects (fix in Story 10-8-g, decision 49).

## 2. Impact analysis

- Epic impact: Epic 10 closes on the smoke acceptance after Story 10-8-g merges. No Epic or Story changes scope.
- Artifact conflicts: `epics.md` (3 lines). The PRD, architecture and UX documents do not change.
- Technical impact: none. No change in `src/`.
- Tier: **PRD direction** (an acceptance criterion). All three clauses need approval. Approved by the user on 2026-11-18 (decision 48). Decision 31 (container run) stays a detail-tier decision.
- Effect: Gate 1 is **not measured** on the full suite. Windows GUI behaviour is **not measured** (the run uses the Linux container, decision 31). The report states both.

## 3. Recommended approach

Direct adjustment. Replace the full-suite requirement with the smoke scope of decision 45. Smallest clause change. Keep the Given/When/Then shape.

## 4. Detailed change proposals

Owner Story: 10.8. Blocks a Story: no. Status: applied in worktree `fcb-cc-10-8` (branch `docs/10-8-ac-smoke`).

| # | Tier | Where | OLD | NEW |
| --- | --- | --- | --- | --- |
| 1 | PRD direction | `epics.md:1220` | `Story 10.8 — a full UAT run with Gate 1 green.` | `Story 10.8 — a smoke UAT run (scope in its AC1) with 0 product defects, every fix-area scenario PASS and the G3 replay unchanged.` |
| 2 | PRD direction | `epics.md:1453-1454` (Story 10.8 AC1 When and Then) | When: `the full suite TC-01..TC-14, TC-99 and the G3 live replay run on FreeCAD 1.1.4 through the Story 10.7b runner, with agent review per the updated §9 and the desktop free (or the GUI lane in an isolated Windows session)`. Then: `Gate 1 is green (Critical 100 %, High ≥ 95 %), Gate 2 matches its documented deviations, and the G3 replay is unchanged; the report is committed under tests/uat/run/` | When: `the smoke run executes on FreeCAD 1.1.4 in the fcb-desktop container through the Story 10.7b runner: the runner set (all 72 scenario files) with agent review per the updated §9, TC-01 agent-driven, a smoke set of one Critical scenario per fix area of run 2026-10-23-02 plus one core Critical scenario per test case, and the G3 replay (headless on all cases, GUI on a control and one planted/reverted pair)`. Then: `there are 0 product defects, every fix-area scenario is PASS, the G3 replay is unchanged, and the test-case defects are fixed (Story 10-8-g); the report is committed under tests/uat/run/` |
| 3 | PRD direction | `epics.md:1448` (Story 10.8 user story) | `**I want** a full UAT run that proves Gate 1 green before Epic 4 resumes.` | `**I want** a smoke UAT run that proves 0 product defects before Epic 4 resumes.` |

Rationale: the user does not want the full UAT set re-run (decision 45). The smoke scope covers each fixed area and each test case once.

## 5. Implementation handoff

Scope: minor. The leader marks Story 10-8 done in `sprint-status.yaml` after Story 10-8-g merges. This change does not edit `sprint-status.yaml`.

Success criteria: Story 10-8-g merged; no Story 10.8 line in `epics.md` still requires a full UAT run.
