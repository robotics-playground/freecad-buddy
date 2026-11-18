# Story 10-9: findings ledger

Quality bar: `_bmad-output/implementation-artifacts/quality-bar-10-9.md`. Round 1 detail: spec "Review Triage Log". Leader triage: `triage-10-9-r1.md`.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-9 | Q10 | high | Blind Hunter r1 `a877e24789249d4fa` | fixed-unproven | `PYTHONPATH` names the installed addon; verifier to confirm the sweeps test `Mod/FreeCADBuddy` |
| R1-1 | Q6 | medium | Blind, Edge, Gap r1 | fixed-unproven | test `Should_delete_the_discovery_files_of_every_started_pid_When_readiness_failed`; verifier to show it red on the old code |
| R1-2 | Q3 | medium | Edge r1 `a1339bc70a7f1b862` | fixed-unproven | silencing rule last in `launch_environment` and `fcb-freecad`; env tests |
| R1-3 | Q7 | medium | Blind r1 | fixed-unproven | `capture.invoke_menu` waits for the enabled flag; 2 tests |
| R1-5 | Q7 | medium | Blind r1 | fixed-unproven | first-press redelivery in `run.menu`, 2 tests; new code found in the round, reviewed by nobody yet |
| R1-11 | Q11 | medium | Blind, Gap r1 | fixed-unproven | 2 positive tests for `wait_until_ready` and `freecad()` |
| R1-10 | Q12 | medium | Blind r1 | fixed-unproven | 32 lines in 15 TC files (step, Given, When only); `scripts/automation/fcb_py.sh`; each variable run in the container per builder; verifier to confirm no Then changed |
| R1-23 | Q9 | medium | Edge r1 | fixed-unproven | watchdog reads `<workdir>/tmp/FCB_TMP_session_*/`; AC9 rerun 0, 0 (old /tmp not counted), 1, 1; 4 unit tests |
| R1-25 | Q12 | medium | builder, while fixing R1-10 | fixed-unproven | starting AppRun with a file skipped the logging rule and hung FreeCAD; `fcb-freecad start` takes file arguments |
| R1-26 | outside the bar | medium | builder, R1-10 search | deferred | 737 lines of Windows-only commands (`tasklist`, `netstat`, `$APPDATA`, PowerShell `cua-driver`) remain in `tests/uat/testcases/`. Blocker: a test-case rewrite outside the 10-9 AC; unblock: a container rewrite of the test cases before Story 10-8 starts |
| R1-24 | Q4 | medium | Edge r1 | deferred | blocker `cua-driver` 0.28.1 `invoke_menu` on Qt top-level menus; AC4 PARTIAL |
| R1-4, 6, 12, 14, 15, 17 | outside the bar | low | Blind, Edge r1 | fixed-unproven | builder patch |
| R1-7, 8, 13, 16, 18, 19, 20, 21, 22 | outside the bar | low / false | Blind, Edge, Gap r1 | rejected | reasons in the spec triage log, accepted by the leader |

| R2-1..R2-13 (10 medium, 3 low) | Q6, Q7, Q9, Q11 | medium / low | round 2 lenses | fixed-unproven | builder mutation proofs: no wait in `invoke_menu` fails 2 tests; stop without process group fails 1; `fcb_py` rewrite removed fails 1; watchdog test red on old code. Detail: spec triage log R2-1..R2-16 |
| R2-14 | outside the bar | medium | round 2 lenses | deferred | joins R1-26 (TC-10 worker-pid steps, TC-11-19) |
| R2-15, R2-16 | outside the bar | low | round 2 lenses | rejected | reasons in the spec triage log |
| R2-3 note | Q14 | — | leader | accepted | a menu redelivery after "delivered, no effect" is recorded in `attempt_log`, not escalated. Accepted: it is the Story 10.7b Show All retry rule (Q7), each repeat is recorded, and the effect is still checked by the probe; it does not turn a failed result into a pass |

| V-1 | Q10 | medium | verifier-10-9 at `9019b76`; fixed in `73c84d4` by builder-10-9-b | fixed-proven (verifier re-run at `73c84d4`: test red with the fix removed, 1 failed 33 passed; planted path exit 1) | wrong `GOLDEN_DIR`: edge sweep "4/4 edge checks passed", exit 0; `run_mcp_edge_cases.py:45-50` skips missing fixtures (leader read the code) |
| V-2 | Q1 | medium | verifier-10-9 at `9019b76`; fixed in `73c84d4` | fixed-proven by mechanism (verifier: not reproducible; failed run 7.7 s vs pass 11.1-11.3 s fits an early false match; new check 10/10 full runs; D-Bus wait removed 4 of 4 red) |
| V-3 | Q10 | low | verifier-10-9 at `73c84d4` | fixed-proven (`f23d58d`; test red with the branch removed, 1 failed 36 passed) | the non-OK-open branch of `_open_golden` has no test |
| V-4 | Q1 | low | verifier-10-9 at `73c84d4` | deferred (deferred-work.md) | the V-2 unit test checks the script text only |
| R3-5 | Q15 | medium | verifier-10-9 | fixed-proven | verifier: broken pattern exit 1, no swap; committed script exit 0 | cause per builder-10-9-b: the check matched a forked, not-yet-exec'd child by cmdline (`bash -c <script>` holds "cua-driver mcp") and read its empty environ; `fcb-cua-mcp` itself was right; fix matches `/proc/<pid>/exe`; 10 full runs green; D-Bus wait removed: 3 of 3 red |
| Verifier proof | — | — | verifier-10-9 | — | proven at `9019b76`: gates (pytest 1752, infc 866), mutants (a) D-Bus wait, (b) logging rule, (c) 4 launch mutants, (d) old /tmp watchdog all red; 9 builder mutation claims reproduced red; R1-10: 0 Then lines changed; Q16 hash equal. Detail: `verify-10-9.md` |

| RT-1 | Q9 | medium | redteam-10-9 at `73c84d4` | fixed-proven (`f23d58d`; verifier re-run, red on the old code or planted break; `verify-10-9.md` "Re-run at f23d58d") | watchdog reads `active`; cua-driver 0.28.1 replies `state: "active"`: a lost session is never reported (leader read `uat_watchdog.py:86`) |
| RT-2 | Q9 | medium | redteam-10-9 | fixed-proven (`f23d58d`; verifier re-run, red on the old code or planted break; `verify-10-9.md` "Re-run at f23d58d") | naive `--since` read as container UTC; host-local cutoff misses a planted folder (exit 0) |
| RT-3 | Q12 | medium | redteam-10-9 | fixed-proven (`f23d58d`; verifier re-run, red on the old code or planted break; `verify-10-9.md` "Re-run at f23d58d") | `tests/uat/README.md:72,74,102,113` still state the pre-port limits |
| RT-4 | Q10 | medium | redteam-10-9 | fixed-proven (`f23d58d`; verifier re-run, red on the old code or planted break; `verify-10-9.md` "Re-run at f23d58d") | `fcb_py.sh:30` backslash prefix has no boundary: `<root>-other` becomes `/repo-other`; regression next to R3-4 |
| RT-5 | Q5 | medium | redteam-10-9 | fixed-proven (`f23d58d`; verifier re-run, red on the old code or planted break; `verify-10-9.md` "Re-run at f23d58d") | `tests/uat/probe/run_faults.py:29,45` still host `freecad.exe` and `%APPDATA%`; in the container 0/5 detected, exit 1 (leader read line 29) |
| RT-6 | Q3 | low-medium | redteam-10-9 | fixed-proven (`f23d58d`; verifier re-run, red on the old code or planted break; `verify-10-9.md` "Re-run at f23d58d") | `check_harness.py:190` matches any "View" label; passes with the menu-bar View removed |
| D-1 | Q5 | low | verifier-10-9 at `f23d58d` | deferred (deferred-work.md) | `run_faults.py` has no preflight: with the container FreeCAD running every case reads "no verdict: :8765 still held" (0/5, exit 1); failure is visible, README:154 says stop FreeCAD first |
| D-2 | Q12 | low | verifier-10-9 at `f23d58d` | deferred (deferred-work.md) | `tests/uat/probe/README.md:28,41` still show the Windows `freecad.exe` launch and `%APPDATA%` path |
| RT not reproduced | — | low | redteam-10-9 | recorded | `launch.stop` raise in `finally`; `fcb-session-env` exit 0 without D-Bus line; qt-build apt packages unpinned; identical guard PNG hashes; disabled menu items omitted vs fake `enabled: False` |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| 1 (patch batch after the lenses about 300 lines, unreviewed: round 2 required) | `97fac62` + uncommitted | Blind Hunter `a877e24789249d4fa` (opus/high), Edge Case Hunter `a1339bc70a7f1b862` (opus/high), Verification Gap `a774d1e6d3d58efee` (sonnet/medium) | 9 → 2 open (R1-10, R1-23) + 6 fixed-unproven | 0 (verifier pending) | 1 (R1-5 menu first-press defect, found and fixed in the round) | 0 |
| 2 (fix batch after the lenses 228 lines: round 3 required, the last allowed) | `97fac62` + uncommitted (37 files +856/-395) | Blind Hunter `a55189f6b4591cf43` (opus/high), Edge Case Hunter `a940d1f7bcc1ffe03` (opus/high), Verification Gap `a749ce62c03bc176e` (sonnet/medium) | high 0; medium 11 new, 10 fixed with mutation or red-test proof, 1 deferred | 10 (builder proof; verifier to confirm) | 11 medium, 5 low | 0 |
| 3 — NOT PASSED (1 high, 6 harness medium); round limit reached, user decides | `97fac62` + uncommitted, frozen at 37 files +856/-395 | Blind Hunter `a2c265bf9c9c321a7` (opus/high), Edge Case Hunter `a2c8f2089769c1af2` (opus/high), Verification Gap `a0226a6bd4a5811a6` (sonnet/medium) | high 1 + medium 6, all fixed with reproduction or test proof; low 1 fixed, 5 rejected, 1 deferred (R3-11) | 7 (builder proof) | 7 | 1 (R3-1: the watchdog failed on a fresh FreeCAD with no `<workdir>/tmp`; introduced by the R1-23/R2-6 fixes) |

Trend of new high + harness medium per round: R1 9 → R2 11 → R3 7. Red team at `73c84d4`: 5 medium + 1 low-medium. RT fix batch `f23d58d`: +250/-73 (about 120 lines harness code), past the 60-line rule; no round 4 (user decision 2026-11-18), so the verifier re-run includes one defect read of that diff. Verifier re-run at `f23d58d`: PASS (all RT rows and V-3 proven; diff read found no wrong process, hidden failure or retry; 2 new low, deferred). Fix batch after round 3: about 340 lines (tracked +54/-1; the rest are new tests and the `fcb_py.sh` wrapper), not reviewed by any lens.
