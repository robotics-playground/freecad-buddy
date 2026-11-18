# Story 10-10: quality bar

Spec: `spec-10-10-uat-testcases-in-container.md` (approved, decision 23). Base `031d8e8`.

A finding blocks the merge when it breaks one of these rows. Other findings are low.

| Q | Rule | Proof |
| --- | --- | --- |
| Q1 | No `Then` or `And` observable changes, except TC-01:368 (D2) and TC-09:403 (route only, accepted as B-1) | `then-check.py` in the proof folder: equal heads, equal counts; red on a planted head edit |
| Q2 | A changed verify clause checks the same thing as before | `then-verify-diff.txt`: every line tagged `rule:K<n>` or `hand` with a reason; verifier reads all `hand` lines and a sample of the `rule` lines |
| Q3 | No host-only command remains (census K1..K9 = 0, or a named exception) | `census.sh` before and after |
| Q4 | Every rewritten command kind ran once in the container with FreeCAD started by `fcb-freecad start` | `tests/uat/run/2026-11-18-10-10-proof/<kind>.txt`, command line first; output matches the check text |
| Q5 | `fcb_cua.sh` maps paths with a boundary and shares the `fcb_py.sh` mapping | wrapper tests, red on a mapping without the boundary (RT-4 cases) |
| Q6 | No invented check: a scenario with no container check left is `NOT APPLICABLE` with a reason | build notes list; verifier reads each |
| Q7 | Format holds: two-space hard breaks, no machine path, file and `### TC-` counts equal | the "Always" greps |
| Q8 | No change in `src/`, `tests/uat/scenarios/`, `tests/uat/runner/`, the watchdog, existing run folders | `git diff --stat 031d8e8` |
| Q9 | Gates green | ruff check, check_imports, ruff format --check on changed .py, pytest tests/external |
| Q10 | Developer `user.cfg` unchanged | SHA-256 equals decision 8 |
