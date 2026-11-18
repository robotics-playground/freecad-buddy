# Story 10-9: triage, red team

Base: `73c84d4` on `story/10-9-uat-runner-in-container`. Red team: `redteam-10-9`, verdict FAIL (5 medium, 1 low or medium, 0 high). Every row below was reproduced by the red team; the leader read the code for RT-1 (`uat_watchdog.py:86` reads `reply.get("active")`) and RT-5 (`tests/uat/probe/run_faults.py:29` defaults to `C:\Program Files\FreeCAD 1.1\bin\freecad.exe`).

| Id | Q | Required fix | Proof required |
| --- | --- | --- | --- |
| RT-1 | Q9 | `uat_watchdog.py` `check_cua_session` must read the cua-driver 0.28.1 `get_session` reply shape: `{"session": ..., "state": "active", ...}`. A live session is active; anything else is lapsed. Update the test double to the real reply shape (the old fake hid this) | A test that feeds the real reply shape: red on the old code, green after. Live: `--no-revive` with a live session exits 0; with the session ended it exits 1 and names it |
| RT-2 | Q9 | `--since` with no UTC offset must not be read in container time while operators pass host time. Either require an offset (refuse a naive time with exit 2 and a clear message) or convert host-local time explicitly. Update `tests/uat/README.md:102` and the runner README to give a command that produces the right value | A test for a naive and an offset time. Live: the planted-folder case with a host-local time `+07:00` cutoff exits 1 and names the folder |
| RT-3 | Q12 | `tests/uat/README.md` lines 72, 74, 102, 113 (and any other stale line found by grep for "shows no widgets", "NOT RUN", "until story 10-9", "Windows host session"): state the container truth, as the other docs already do | Grep output after the fix shows no stale claim |
| RT-4 | Q10 | `scripts/automation/fcb_py.sh:30`: the backslash-prefix rewrite needs the same boundary check as the forward-slash one (the next character after the root must be a separator or the end). Also rewrite or warn on a backslash root that follows a `--flag=` prefix | Tests for `<root>-other`, `<root>2`, and `--out=<root-with-backslashes>\x`: red on the old script, green after |
| RT-5 | Q5 | Port `tests/uat/probe/run_faults.py` to the container (scope item 2: "port ... its FreeCAD probe"): no host `freecad.exe`, no `%APPDATA%`; discovery file and launch through the same container path the runner uses. Update `tests/uat/probe/README.md:139,166` | Live in the container: `run_faults.py` reports its fault cases detected and no false alarms (give the counts), exit 0; one planted fault-detection break goes red |
| RT-6 | Q3 | `tests/close-loop/check_harness.py:190` must find File, Edit and View as menu-bar items (role and parent), not any element with that label | With the menu-bar View removed from a captured tree, the check fails; the live tree passes |
| V-3 | Q10 | Add the missing test for a golden file that exists but does not open (`_open_golden` non-OK branch) | Test red with that branch removed |

Not fixed now (red team "Not reproduced"): keep as low in the ledger; no change.

## After the fixes

One commit on the Story branch. The verifier re-runs every row above with its proof, plus the full gates and one full `check_harness` and sweep pass. The red team does not run again (once per Story). If the verifier passes, the leader merges into `fix/uat-gate-1-failures` (decision 16).
