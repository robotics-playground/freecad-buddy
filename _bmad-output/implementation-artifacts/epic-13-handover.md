# Epic 13 handover

Handover for the next leader run of `SPEC-mcp-usage-improvement` (`_bmad-output/specs/spec-mcp-usage-improvement/SPEC.md`). Written 2026-11-25. Start the next run with `/bmad-leader resume` and read this file first, then `epic-13-status.md` (Environment block) and `epic-13-decisions.md`.

## State at handover

| Item | Value |
| --- | --- |
| Integration branch | `feat/epic-13-mcp-usage-improvement`, checked out in worktree `D:/Work/Personal/Sources/freecad-buddy-int` (the leader merges there). Not pushed. |
| Main tree | `D:/Work/Personal/Sources/freecad-buddy` on a Story branch (builders use it). |
| Base of the epic | `bd122f2` on `fix/uat-gate-1-failures` (65 commits ahead of `main`, unmerged). A merge to `main` and any push need the user. |
| Stories done (merged) | 13-1, 13-2, 13-3, 13-4, 13-5, 13-6, 13-7, 13-8, 13-9, 13-10, 13-11, 13-14, 13-20 (13 of 20) |
| Stories in review | 13-12 (skills, branch `story/13-12-skill-routing-measure` @ 4333288b), 13-18 (loft/sweep, branch `story/13-18-loft-sweep` @ d8968a1e, worktree `wt-13-18`). The leader finishes these two in this run if time allows; check `sprint-status.yaml` and the ledgers for their final state. |
| Specs waiting for the user | 13-13 (`wt-13-13` @ f2887033), 13-15 (`wt-13-15` @ bfc02cf3), 13-17 (`wt-13-17` @ 88b52fc4). No product code on those branches. |
| Not started | 13-16 (depends on 13-15), 13-19 (depends on 13-16, 13-17, 13-18) |
| Last full gate run on the integration head | after the 13-10 merge: ruff, check_imports, gen_schemas, check_provenance pass; external 2106 passed / 1 intermittent timing failure (deferred); infc 1186 OK |

## Decisions waiting for the user

Ask these in one message at the start of the next run (each has a recommendation):

| # | Decision | Recommend | Where |
| --- | --- | --- | --- |
| 1 | Story 13-15 TNP rule: approve; apply to every sub-element link; accept that an element moving farther than its support stays REPOINTED | yes, yes, yes | `wt-13-15/_bmad-output/implementation-artifacts/spec-13-15-tnp-expected-reattachment.md` |
| 2 | Story 13-7 touching solids: (a) keep `boolean_failed` for touching pairs, or (b) add a fuse cross-check so touching reads overlap 0 (changes one T-2 line) | (b) | `verify-13-7.md`, decision 24 |
| 3 | Approve the Story 13-13 spec (21 measured cases; `undo_steps`; no framing cache for `script_exec`; bracket-failure statuses) | yes | `wt-13-13/_bmad-output/implementation-artifacts/spec-13-13-script-exec-bracket.md` |
| 4 | Spine edits (architecture tier): AD-27 late return commits for `script_exec`; correct the AD-5 sentence about changes in other documents | yes | same spec |
| 5 | Approve the Story 13-17 spec incl. the `docs/intent.md:254` phase-list edit, `RECOMPUTE_ERROR` for an empty boolean result (reuse 13-10's `transaction.RecomputeFailure`), inputs hidden after a boolean, measured cost limits | yes | `wt-13-17/_bmad-output/implementation-artifacts/spec-13-17-part-primitive-boolean.md` |
| 6 | Architecture item (deferred): bridge recovery after one long GIL-holding OCC call (AD-27) | decide direction | `deferred-work.md` entry from spec-13-8 |
| 7 | Architecture item (deferred): AD-6 fingerprint blind to VarSet/spreadsheet/property-only changes (decision 32 works around it per tool) | decide direction | `deferred-work.md` entry from spec-13-9 |

## Order for the next run

1. Get the user's answers to the table above.
2. 13-13: a fresh builder implements the approved spec (spine edits first if decision 4 is yes). Note: 13-10 already added `transaction.RecomputeFailure` and the application-transaction close in `run_mutation` (L14); 13-13 reuses them.
3. 13-15: a fresh builder implements the approved rule. Then 13-16 (placement and string writes in `feature_set_parameters`; placement shape shared with 13-17).
4. 13-17: a fresh builder implements the approved spec (after 13-16 for the placement parser).
5. 13-19: skill routing to Part, loft, sweep and placement tools; closes `deferred-work.md:1654`; finishes the gap list; the `docs/intent.md` edit lands with 13-17.
6. If decision 2 is (b): a small follow-up on `query_interference`.
7. Epic close: re-score validators once on the final head; full gates; container UAT smoke of the new tools; CAP-6 live Claude Code session (first tool load holds typed tools; "is it done?" loads `verification-thinking`); retrospective (`bmad-retrospective`); action item about 2026-12-23: run `scripts/automation/usage_report.py` on the following month (decision 3 targets).

## Process that worked (keep it)

- One fresh builder per Story (`bmad-build`, model sonnet), the leader approves the plan and writes a quality bar; then a fresh verifier (opus, container UAT) and a fresh red team (opus) in parallel; one triage file per round; same verifier re-runs.
- The red team and the container UAT found real high defects in almost every tool Story (wrong numbers on untrusted shapes, GIL-holding calls, no-op undo deleting an earlier step, app-level transaction left open, GUI-only 3MF defect). Do not skip either.
- Builders read `epic-13-lessons.md` (L1-L15) before planning; it cut repeat defects.
- Before re-verifying a Story that touches shared code (`transaction.py`, `tnp_guard.py`, `rpc_dispatch.py`), have its builder merge the integration branch into the Story branch first.
- Merges into the integration branch conflict mostly in `deferred-work.md` and test files where both sides append: keep both sides; re-run all gates on the merged head.
- Agents that only wait for a user decision are shut down; a fresh agent continues from the committed spec.
- Idle notices often arrive before a message lands: check `ListAgents` before acting. An idle notice that says "waiting for tests" is a stall: nudge the agent to wait in the foreground. Run a 10-minute heartbeat timer.

## Key files

| File | Purpose |
| --- | --- |
| `epic-13-status.md` | Current status and the Environment block (shell, gates, container, known flaky tests, worktree rules) |
| `epic-13-decisions.md` | Decisions 1-38 with sources |
| `epic-13-lessons.md` | L1-L15 defect lessons for builders |
| `epic-13-plan.md`, `epic-13-context.md` | Story plan and contract check |
| `quality-bar-13-*.md`, `review-ledger-13-*.md`, `triage-13-*.md`, `verify-13-*.md`, `redteam-13-*.md` | Per-Story review records |
| `deferred-work.md` | Deferred items with blocker and unblock condition (search "spec-13-") |
| `sprint-status.yaml` | Epic 13 Story states |
| `tests/uat/run/13-*/` | Live container evidence per Story |

## Open risks

- Two intermittent timing tests (`test_marshal_self_submit`, `test_mcp_cache_proxy` lost-session) — deferred; CI must not hide failures.
- `validators.yaml` hashes change with shared code; several Stories re-scored them. Re-score once at epic close and confirm `check_provenance` and the runner currency check.
- The relay `mcp_cache_proxy` caches tool schemas and instructions: a client connected before a rebuild sees old schemas until it reconnects.
