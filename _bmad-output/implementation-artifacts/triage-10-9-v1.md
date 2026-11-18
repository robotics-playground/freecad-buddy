# Story 10-9: triage, verifier round 1

Base: `9019b76` on `story/10-9-uat-runner-in-container`. Verifier report: `_bmad-output/implementation-artifacts/verify-10-9.md` (verdict FAIL, 2 medium).

| Id | Source | Required fix | Regression risk and neighbour test |
| --- | --- | --- | --- |
| V-1 | verifier-10-9, AC10 / Q10 | The edge sweep must fail when a golden fixture is missing. Today `_open_golden` (`scripts/automation/run_mcp_edge_cases.py:45-50`) returns `None` for a missing file or a non-OK open, and its callers (`:65`, `:166`) skip their checks, so a wrong `GOLDEN_DIR` gives "4/4 edge checks passed" and exit 0. Record a missing or unopenable fixture as a FAILED check (or stop the sweep with a non-zero exit), never as a skip. Pre-existing at `97fac62`, but AC10 states the planted-wrong-path rule for both sweeps | Add a pure test that a missing fixture is reported as a failure. Re-run the planted wrong `GOLDEN_DIR` live: non-zero exit for the edge sweep. Re-run both sweeps with the right path: e2e 29/29, edge 14/14 |
| V-2 | verifier-10-9, AC1 / Q1 | `check_harness.py` check `mcp-session-env` reads red on the committed `fcb-cua-mcp` in 3 of 6 full `check_harness` runs and green in 22 of 22 direct calls. Cause unknown. Diagnose first with `ultrathink-protocol`: decide with evidence whether the check reads the wrong process (for example a `cua-driver mcp` started by another client, or a process still starting before its `exec`), or whether `fcb-cua-mcp` really can start without the address. Fix the side that is wrong. Do not add a retry to the check to get a pass (spec Never list, Q14) | The fix must keep the falsification: with the D-Bus wait removed, `mcp-session-env` reads red every time. Show 10 full `check_harness` runs green on the fixed tree, with counts |
| R3-5 | verifier-10-9: not proven | Prove the round-3 fix of `tests/close-loop/docker/swap-qt-gui.sh` (no `\|\| true` hiding a grep error): run the script with a broken grep pattern and show it stops with a non-zero exit; restore it and show the swap passes | none beyond the proof |
| V-low | verifier-10-9 | TC-01 lines 391, 530, 615, 650 still use `invoke_menu File > Exit`. Part of the accepted deferral R1-24 (AC4 PARTIAL); add these line numbers to that deferred-work entry, no other change | none |

## After the fixes

Commit on the Story branch with a Conventional Commit. The fix batch is small and targeted, so no new lens round runs unless the batch passes about 60 changed lines of harness code. The same verifier re-runs V-1 and V-2, then the red team attacks the whole diff.
