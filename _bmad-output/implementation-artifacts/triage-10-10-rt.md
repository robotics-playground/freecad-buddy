# Story 10-10: triage, red team

Base: `5ee4824`. Red team `redteam-10-10`: FAIL, 5 medium reproduced (report `redteam-10-10.md`, evidence `tests/uat/run/2026-11-18-10-10-redteam/`). Leader read the RT-2 reproduction: `script_exec { code: ... }` without `doc` returns `Input validation error: 'doc' is a required property`. The verifier's N2 run used its own call form, not the text as written: every re-run below copies the test-case text exactly.

| Id | Q | Required fix | Proof required |
| --- | --- | --- | --- |
| RT-1 | Q2 | TC-10:185, :260, :558, :595: `ss -ltnp \| grep ... \| grep ESTABLISHED` always prints nothing (`-l` lists only listening sockets; `ss` prints `ESTAB`). Use `ss -tnp` and `ESTAB` | Each site run as written with a held session: the established row prints |
| RT-2 | Q2/Q4 | TC-12:97, :273, TC-13:226, :359, `test-plan.md:347`: add `doc:<handle>` to every `script_exec` call; sweep every `script_exec` in the test cases for the same miss | Sweep output (0 calls without `doc`); TC-12:273 and the test-plan read run as written |
| RT-3 | Q4 | `test-plan.md:345`, TC-12:599: pixel clicks take screenshot pixels (screenshot 1568x930 for a 1600x949 window). State the conversion (frame point times screenshot width / window width), or take the point from the screenshot; sweep the other pixel-click sites | Row below window y 450 (B16 on a 40-box document) selected by the written route |
| RT-4 | Q5 | `tests/external/test_fcb_cua_wrapper.py:23-27`: the fake `docker` always exits 0. Add a fake that exits non-zero and a test that the wrapper returns that code | The `\|\| true` mutant of the wrapper turns the new test red |
| RT-5 | Q2 | TC-01:83 (from Story 10-9): `pgrep -af freecad_buddy.hosts.main` "returns nothing" also matches the GUI proxy the same Given needs, so it cannot pass. Narrow the pattern to what the step means | Run as written with the GUI proxy up: passes; with a stray headless host: fails |
| R1 | Q2 | `test-plan.md:365`: Document Recovery "can show"; button order as measured (Cleanup, then Delete / Yes) | text |
| R2 | Q4 | `"$FCB_CUA" list_windows` prose with no stdin (TC-01:363, TC-10:43, :146, TC-14:191, :229, :466, :484, TC-15:137, :154): add `echo '{}' \|`; sweep every `"$FCB_CUA"` call without stdin | Sweep output 0 |
| RT-low | — | `test-plan.md` §6: one sentence that `cua-driver` exits 0 on a tool error (dead pid, missing `window_id`), so a step is judged by the printed text, not the exit code | text |

Not fixed: `fcb_paths.sh` left boundary and silently ignored bad JSON (red team: not reproduced, low). Recorded in the ledger.

## After the fixes

One commit (leader). The verifier re-runs every row by copying the test-case text exactly, plus full gates and `then-check.py`. The red team does not run again (once per Story). PASS: merge into `fix/uat-gate-1-failures` (decision 21).
