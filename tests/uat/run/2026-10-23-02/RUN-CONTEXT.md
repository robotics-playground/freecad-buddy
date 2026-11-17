# Run context: UAT gate run 2026-10-23-02

Story 10.8 goal 3. Spec: `_bmad-output/implementation-artifacts/spec-10-8-d-uat-gate-1-run.md`.

| Field | Value |
| --- | --- |
| Commit | `3025e7c` (tree clean except the spec file) |
| FreeCAD | 1.1.4, `C:\Program Files\FreeCAD 1.1\bin\freecad.exe` |
| Developer `user.cfg` SHA-256 before | `ccf87cfe7650daa8d9f533b0e10c5dc7ae1db0c7a3aa68df3a44a04c0973832b` |
| Preflight | no `freecad.exe`, nothing listening on `:8765` |

## Phases

The run is executed in phases, one at a time, because there is one FreeCAD and one desktop.

| Phase | Scope |
| --- | --- |
| P0 | runner run of `tests/uat/scenarios` into `runner/`; §9 review of the review set and every ESCALATE |
| P1 | agent-driven TC-01 |
| P2 | agent-driven TC-02, TC-03 |
| P3 | agent-driven TC-04 |
| P4 | agent-driven TC-05 |
| P5 | agent-driven TC-06, TC-08 |
| P6 | agent-driven TC-07 |
| P7 | agent-driven TC-09 |
| P8 | agent-driven TC-10 |
| P9 | agent-driven TC-11 |
| P10 | agent-driven TC-12 |
| P11 | agent-driven TC-13 |
| P12 | agent-driven TC-14, TC-99 |
| P13 | G3 replay, GUI and headless (spec D1) |

An agent-driven scenario is a current `### TC-xx-yy` scenario with no file in `tests/uat/scenarios/`.

## Evidence

- Evidence files go to `evidence/` named `tc-xx-yy-<what>.<ext>` (captures `.png`, MCP calls `-mcp.jsonl`, checks `-checks.txt`).
- Each phase keeps a launch log line per FreeCAD launch in `evidence/launch-log.tsv`: phase, start time, pid, profile, env, end time.
- Each phase returns its verdict rows as text; the lead writes `report.md` and `bugs.md`.
