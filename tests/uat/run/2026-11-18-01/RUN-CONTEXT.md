# Run context — 2026-11-18-01 (Story 10-8-d, UAT Gate 1 run)

## Code state

| Item | Value |
| --- | --- |
| Branch | `story/10-8-d-gate-1-run` |
| Commit | `2db195ceaee52796280ab1cb3c8f47d88f8f0bc4` (integration head: 10-8-e, 10-8-f, 10-8-d preparation merged) |
| Uncommitted at run start | `M _bmad-output/implementation-artifacts/epic-10-status.md` (leader file), `?? .leader.json`, `?? _bmad-output/specs/spec-mcp-usage-improvement/`. No file under `src/`, `tests/uat/runner/`, `tests/uat/scenarios/`, `tests/uat/testcases/` or `scripts/` differs from the commit (`evidence/s0-git-status.txt`). The code under test is the commit |
| Addon build | `uv run python scripts/build_addon.py --release` exit 0 (`evidence/s0-build.log`) |
| Addon wheel SHA-256 | `d40a271bf1a9c8e8f5b84bb6a601ecea858a6bc6ea77ae8afb1f7b26a5e3fe8c` `freecad_buddy-0.1.1-py3-none-any.whl` (`evidence/addon-wheel-sha256.txt`) |
| Image id | `sha256:ccccd43b5b3df8ee1eaaf547643570184c90099415298be0b98bd6cc103dddc4` (`evidence/image-id.txt`), container recreated at 2026-11-18T19:30+0700 with `up -d --build --force-recreate` (clean container profile) |
| FreeCAD | 1.1.4 Linux AppImage `/opt/freecad/AppRun` in container `fcb-desktop` (`fcb-py` prints `H1 ok 1.1.4`, `evidence/s0-h1.txt`) |
| Developer `user.cfg` SHA-256 before | `b89a97711941619bb0ba74ae04fb888025e82f49ff48174fbebb42aed28d85a0` = decision 8 baseline (`evidence/user-cfg-sha256.txt`) |
| Run start | `2026-11-18T19:29:00+0700` (watchdog `--since` value) |

Environment note (decision 31): this run drives FreeCAD 1.1.4 on Linux (X11, Mesa software OpenGL) in the container. It does not measure Windows GUI behaviour.

## Harness gate (S0)

| Check | Result | Evidence |
| --- | --- | --- |
| H1 host | `H1 ok 1.1.4` | `evidence/s0-h1.txt` |
| `run_mcp_e2e.py` | exit 0, 29/29 | `evidence/s0-e2e.log`, `evidence/e2e_report.json` |
| `run_mcp_edge_cases.py` | exit 0, 14/14 | `evidence/s0-edge.log`, `evidence/edge_report.json` |
| Probe fault set `run_faults.py` | detected 5/5, false alarms 0/2 | `evidence/s0-probe-faults.log` |
| Pixel fault set `pixel_faults.py` | detected 4/4, false alarms 0/2 | `evidence/s0-pixel-faults.log` |
| G3 GUI scripts copied | git blob ids equal to `tests/uat/g3-gui/` | `evidence/g3-gui-script-blob-ids.txt` |

## Scope

260 scenarios: TC-01..TC-14 (255; 174 Critical, 67 High, 14 Medium) and TC-99 (5, Gate 2). TC-15 and TC-16 are out of scope (`spec-10-8-d` Intent). Lists: `lead-notes/scenario-priority.txt`, `lead-notes/runner-ids.txt` (72), `lead-notes/agent-ids.txt` (183 + 5 TC-99).

| Phase | Scenarios | Driver |
| --- | --- | --- |
| R0 | 72 scenario files of `tests/uat/scenarios/` (TC-02..TC-14) | runner, drawn seed |
| R0a | §9 review of R0 for TC-02..TC-04 files | agent |
| R0b | §9 review of R0 for TC-05..TC-14 files | agent |
| P1 | TC-01 (15) | agent |
| P2 | TC-02 (8), TC-03 (6) | agent |
| P3 | TC-04 (14) | agent |
| P4 | TC-05 (14), TC-06 (8) | agent |
| P5 | TC-07 (18) | agent |
| P6 | TC-08 (10) | agent |
| P7 | TC-09 (18) | agent |
| P8 | TC-10 (14) | agent |
| P9 | TC-11 (17) | agent |
| P10 | TC-12 (14) | agent |
| P11 | TC-13 (16) | agent |
| P12 | TC-14 (11), TC-99 (5) | agent |
| G3 | GUI replay (`evidence/g3-gui/`) and headless scorer | lead + one reader agent |

Selection rule: every scenario runs once. A FAIL is never retried to get a PASS (spec D2). Agent execution fault only: one re-run from the Given, both runs kept (`uat-run-practices.md` §7).

## Evidence naming

- Agent-driven: `evidence/tc-xx-yy-<what>.<ext>`; launches in `evidence/launch-log.tsv` (phase, start, pid, profile, env, end).
- Runner: `runner/` (R0, never written again after R0 ends); a §9 re-run of a launch group that did not start writes `runner-rerun-<n>/` (decision 44).
- §9 agent_check re-runs: `evidence/r0a-*`, `evidence/r0b-*`.
- G3: `evidence/g3-gui/`, `evidence/g3-headless/`.
- Phase reports: `lead-notes/phase-<id>-report.md`; lead grades: `lead-notes/lead-grades.md`.

## Re-run rule

Decision 35: after a red run, only the affected scenarios re-run into a new folder when the fixes touch only test cases or the harness (same image id, no `src/` change); a `src/` change re-runs the whole gate.

## Scope change: smoke run (decision 45)

From 2026-11-18 about 21:00 this run is a smoke run, not a full run (`epic-10-decisions.md` decision 45). Gate 1 is not measured on the full suite. Kept: S0, R0 (72 runner scenarios, seed `423616651`) and its review R0a-1..R0b-3, P1 (TC-01, 15 scenarios, plus the P1-R re-run of TC-01-10). Phases P2..P12 of the table above do not run. TC-99 (Gate 2) does not run: no fix area of the smoke list needs it.

### Smoke list (24 agent-driven scenarios, 2 phases)

Priority (a): one Critical scenario per fix area that FAILED in run 2026-10-23-02 (`tests/uat/run/2026-10-23-02/report.md`) and was fixed in Epic 10 (fix groups W1..W8 in `lead-log-2026-10-24-uat-fixes.md` §3, §5; bug ids from that report). Priority (b): one core Critical scenario for each TC-02..TC-14 that (a) does not reach; TC-13 and TC-14 get two, because no agent-driven TC-13 or TC-14 scenario ran in 2026-10-23-02 (P11 and P12 did not run).

| Phase | Scenario | Priority | Set | Reason |
| --- | --- | --- | --- | --- |
| S1 | TC-02-09 | Critical | b | TC-02 core: `document_list` adopts a GUI-opened document |
| S1 | TC-03-04 | Critical | b | TC-03 core: rectangle reaches FullyConstrained in one flow |
| S1 | TC-04-16 | Critical | a | W4 test-case fix: rollback proof by mass properties (`rolled_back_verified`), not equal digests. Same area as TC-04-23 |
| S1 | TC-04-21 | Critical | a | W4 test-case fix: quoted `feature_set_parameters` refusal text |
| S1 | TC-05-06 | Critical | a | W4 test-case fix: snapshot-escalation reproducers (old reproducer had no `length`) |
| S1 | TC-05-17 | Critical | a | W4/W8 test-case fix: TNP Layer-0 BROKEN owner (Story 10.3) |
| S1 | TC-06-01 | Critical | a | B-10 harness limit, W8 profile rule: anti-aliasing of the live profile vs the render |
| S1 | TC-06-09 | Critical | a | W4 test-case fix: render temp files on a clean document |
| S1 | TC-07-05 | Critical | b | TC-07 core: `export_step` both AP schemas, never self-verified (Story 10.5 area) |
| S1 | TC-08-01 | Critical | a | W4 test-case fix: diff schema `fcb.geometry-diff/2` |
| S1 | TC-08-02 | Critical | a | B-03 product fix (W2b): a failing preview posts no GUI notification (AD-31/AD-33) |
| S2 | TC-09-01 | Critical | a | B-01 harness fix (W3): edge sweep reads the text-only tree result. TC-01-02 (P1 PASS) covers the e2e sweep; TC-09-02, TC-09-22, TC-10-01 are the same area |
| S2 | TC-10-03 | Critical | a | W5 test-case fix (stale discovery glob) and Story 10.6b busy refusal (AD-26) |
| S2 | TC-10-07 | Critical | a | W3 test-case fix (quarantine read from a text-only tool) and Story 10.6 bounded execution (AD-27) |
| S2 | TC-11-11 | Critical | a | W5 test-case fix (`detail` on an `OK` preview); preview TempDoc removal after the W2b mute change |
| S2 | TC-11-14 | Critical | a | W5 test-case fix: save backup `.FCBak` allowed in the explicit-path listing |
| S2 | TC-12-04 | Critical | a | W6 test-case fix: GUI tree selection route |
| S2 | TC-12-05 | Critical | a | W6 harness limit fixed (container element route): GUI Visibility toggle |
| S2 | TC-12-06 | Critical | a | W6 test-case and harness fix (Story 10.10): GUI Undo label |
| S2 | TC-12-14 | Critical | a | B-04 product fix (W2b): teardown line `freecad-buddy bridge stopped` on quit |
| S2 | TC-13-01 | Critical | b | TC-13 core: tree parity, MCP node set equals the GUI Model tree |
| S2 | TC-13-10 | Critical | b | TC-13 core: `feature_pad` via MCP appears in the GUI tree and viewport |
| S2 | TC-14-03 | Critical | b | TC-14 core: the fit moves the camera |
| S2 | TC-14-05 | Critical | b | TC-14 core: fitted viewport and MCP render agree |

Fix areas covered by earlier phases, not repeated: B-01 e2e sweep (TC-01-02, P1 PASS); TC-01-13 and TC-01-15 visual Then (P1 PASS); proxy identity and orphan exit, Story 10.6c (TC-01-14, TC-01-15, P1 PASS); TC-08-13 elicitation refusal (runner file, R0). Not chosen: TC-02-08 (decision 34; not needed, leader brief); TC-04-23 (same area as TC-04-16); TC-09-02, TC-09-22, TC-10-01 (same area as TC-09-01); TC-11-15 (W5 grep wording, phase size); TC-09-15 (human intervention, no fix); High and Medium FAILs (TC-02-08, TC-08-12, TC-09-09, TC-12-08, TC-12-10, TC-12-11).

### G3 (smoke)

Headless scorer: all 14 cases (spec Code Map command). GUI replay: one control and one planted/reverted pair only.
