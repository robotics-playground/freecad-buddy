# Story 10-9: triage, round 1 leader rows

Base: `97fac62` plus the uncommitted Story work presented at 2026-11-17 23:22. Builder triage log: `spec-10-9-uat-runner-in-container.md` "Review Triage Log" (24 findings).

| Id | Source | Required fix | Regression risk and neighbour test |
| --- | --- | --- | --- |
| R1-10 | Blind Hunter, finding 10 | Fix now, do not defer. The test cases and `test-plan.md` use `$FCB_PYTHON` (24), `$FCB_ENV` (8), `$FREECAD_EXE` (21), which name host paths that no longer exist. Give each a container equivalent in `test-plan.md` (for example `fcb-py`, `/opt/freecad/...`), and replace the uses in the step and Given text of `tests/uat/testcases/TC-*.md`. Do not change any Then (spec D3). Blocker named by the builder: none; the scope is G4 | A replaced command must still run: run one rewritten Given or step per variable in the container and paste its output |
| R1-23 | Edge Case Hunter, finding 23 | Fix now, do not defer. The watchdog is ported in this Story (AC9) and counts `FCB_TMP_snap_*` under `/tmp`, while the bridge writes `<workdir>/tmp` (Story 9-4). Make it check the directory the bridge actually uses in the container | The AC9 three-case proof must still hold: re-run clean (exit 0), FreeCAD stopped (exit 1), planted folder in the real temp directory (exit 1), plus one planted folder in the old `/tmp` path that must no longer count |
| R1-24 | Edge Case Hunter, finding 24 | Accept the deferral. Blocker: `cua-driver` 0.28.1 `invoke_menu` refuses Qt top-level menu items ("menu path segment 0 has no safe activation action"). Unblock: a `cua-driver` release that activates `ShowMenu` items, or a test-case rewrite to the token route. Record AC4 as PARTIAL in the spec: `element_index` and token menu clicks work; test-case steps written as `invoke_menu` do not | none |

## Not fixed, with the reason

Rejected findings 7, 8, 13, 16, 18, 19, 20, 21, 22 keep the builder's reasons from the spec triage log; the leader read each and accepts them.

## After the fixes

The builder reports the diff size of this batch. Next: the verifier runs the gates and its own mutants, then one red-team pass, as long as no new high or product-medium finding appears.
