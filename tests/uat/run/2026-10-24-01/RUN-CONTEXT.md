# Run context: UAT re-run 2026-10-24-01

Re-run of run 2026-10-23-02 after the fixes on branch `fix/uat-gate-1-failures` (spec `_bmad-output/implementation-artifacts/spec-10-8-d-uat-gate-1-run.md`, D2). Fix record: `_bmad-output/implementation-artifacts/lead-log-2026-10-24-uat-fixes.md`.

| Field | Value |
| --- | --- |
| Commit | `3025e7c` plus the uncommitted fix diff (not committed: the owner approves every commit) |
| Tracked diff | `evidence/baseline-tracked.diff` (SHA-256 recorded in `evidence/baseline-untracked.txt` header line below) |
| New untracked files | `evidence/baseline-untracked.txt` (SHA-256 per file) |
| FreeCAD | 1.1.4, `C:\Program Files\FreeCAD 1.1\bin\freecad.exe` |
| Developer `user.cfg` SHA-256 before | `4c415695ea8006ae1515001702c2bdf31674508d9a7705c7c73c9ce987d56b75` |

## Scope

| Phase | Scope |
| --- | --- |
| R0 | H1 env setup; runner run of all 72 files of `tests/uat/scenarios` into `runner/`; §9 review of the review set and every ESCALATE |
| R1 | agent-driven: TC-01-02, 13, 15; TC-02-05, 07, 08, 09, 10, 11, 14, 18; TC-04-16, 21, 23; TC-05-06, 17; TC-06-01, 09 |
| R2 | agent-driven: TC-08-01, 02, 05, 06, 12, 17, 18, 19, 20, 21; TC-09-01, 02, 09, 15, 22; TC-10-01, 03, 07; TC-11-11, 14, 15, 18 |
| R3 | agent-driven: TC-12-01, 03, 04, 05, 06, 08, 10, 11, 12, 13, 14, 15 |
| R4 | agent-driven: TC-13 (16 scenarios: 01, 02, 03, 05, 07-18) |
| R5 | agent-driven: TC-14-01, 03, 04, 05, 09-15; TC-99-01, 02, 04, 05, 06 |
| R7 | full regression, agent-driven scenarios that PASSed in 2026-10-23-02 and are not above (104): TC-01 (12), TC-03 (6), TC-04 (11), TC-05 (12), TC-06 (6), TC-07 (18), TC-09 (13), TC-10 (11), TC-11 (13), TC-12-02, 09; list in the lead scratchpad `rerun/regression-list.txt` |
| R6 | G3 GUI replay (`tests/uat/run/2026-10-03-04/evidence/g3_gui_replay.py`) and headless scorer per spec D1 |

Selection: every scenario of TC-01..TC-14 and TC-99, so that the gate rests on one code state: the runner runs all 72 files, and R1-R5 plus R7 run all agent-driven scenarios. Phase agents from R3 on run on the Sonnet model (owner request, 2026-10-24); the lead re-checks key captures.

## Evidence

Same naming as 2026-10-23-02: `evidence/tc-xx-yy-<what>.<ext>`; one line per FreeCAD launch in `evidence/launch-log.tsv` (phase, start, pid, profile, env, end).
