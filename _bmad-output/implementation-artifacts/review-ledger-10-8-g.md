# Story 10-8-g: findings ledger

Quality bar: `quality-bar-10-8-g.md`.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| B-r1 | Q1-Q8 | mixed | lenses r1 (Blind 13, Edge 12, Gap 0) | fixed | 16 items patched; triage log in `spec-10-8-g-smoke-testcase-defects.md` |
| RT-1 | Q6 | medium | redteam-10-8-g | fixed-proven | `tc-02-17.json:128` agent_check lacks "non-empty"/`detail.code`; two empty tails pass; reproduced with `mcp_server._to_call_result` |
| RT-2 | Q6 | medium | redteam-10-8-g | fixed-proven | `tc-09-12.json:225` agent_check and `expect` regex accept any `INVALID_INPUT:` line with the handle; case `TC-09:504` needs the exact line; reproduced |
| RT-3 | Q6 | low | redteam-10-8-g | fixed-proven | `tc-03-03` agent_check omits the camera read-back |
| RT-4 | Q8 | low | redteam-10-8-g | fixed-proven | `deferred-work.md:2089` cites missing `tc-03-03-iso-edit.png` (real: `tc-03-03-after.png`) |
| RT-5 | Q8 | low | redteam-10-8-g | fixed-proven | resolved entries do not name `56e746b` (leader adds at merge) |
| RT-6 | Q6 | low | redteam-10-8-g | fixed-proven | `TC-03:131` MCP call with edit mode open, against `TC-03:31` |
| RT-7 | Q5 | low | redteam-10-8-g | fixed-proven | TC-07-05 cites `envelope.py:111`; append is at `:124` |
| L-1 | Q6 | low | leader | accepted | added steps of TC-03-03 and TC-07-03 are And lines inside the Then block (MCP Thens need edit mode closed); acceptable only if no Then expectation changed; verifier and red team check (decision 51) |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 56e746b | Blind af4f65ab21c1cd22f, Edge ab8b395e8dd77b7e1, Gap a46b46f80caec3fdd | 0 → 0 (test text only) | 16 patched | — | 0 |
| V/RT | 56e746b | verifier-10-8-g PASS (4 cases live, runner 7/7, falsify TC-03-20 and TC-07-05); redteam-10-8-g FAIL (RT-1, RT-2) | test medium 0 → 2 | — | 2 medium, 5 low | 0 |
| G1 | df5572f | none (scenario/text < 60 lines); verifier-10-8-g re-run PASS (5 wrong outputs give findings, 2 correct pass; live tc-02-17, tc-09-12 0 FAIL) | test medium 2 → 0 | 7 | 0 | 0 |

Closed: merged into `fix/uat-gate-1-failures` at `091c29c` (2026-11-18). Post-merge: runner + canary tests 193 passed, ruff clean.
