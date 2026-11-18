# Phase P1-R report — TC-01-10 re-run (agent execution fault re-run, both runs kept)

| Scenario | Priority | Verdict | Evidence | Note |
| --- | --- | --- | --- | --- |
| TC-01-10 | High | PASS | evidence/tc-01-10-rerun-before.png; no after.png (capture of dead pid refused) | All Givens met on a fresh addon-spawned proxy (pid 17421). All 7 Thens met on the single check. |

## Givens
- Fresh start: FreeCAD pid 17331, /healthz freecad_pid 17331. addon.log offset before start 1909; new line: `spawned MCP proxy (pid 17421)`. `ss -ltnp`: `:8765 LISTEN ... pid=17421`. rpc-17331.json present. 5 rpc-*.json before quit (4 other pids).
- Document box-10-20-30 opened, shown (Show All Objects leaf, tree `v` marker), Fit All toolbar pressed by token, waited 22 s. Capture read: Part Design window, box whole in the 3D view (top view rectangle), no dialog, status bar 66.37 x 37.42 mm.
- Document closed with document_close; document_list shows 0 documents.

## When
Exit leaf pressed 2026-11-18T22:00:46+07:00; process gone after 3 s.

## Thens (raw, 2026-11-18T22:00:49+07:00)
1. pgrep: no output, exit=1
2. ls rpc-17331.json: No such file or directory, exit=2
3. ps -p 17421 -o pid=: no output, exit=1
4. ss -ltnp | grep :8765: no output, exit=1
5. other rpc files: rpc-2077, 3584, 4468, 5328 = 4 (4 before)
6. list_windows: Xfdesktop and Xfce4-panel only, no FreeCAD window; get_window_state on pid 17331: "stale or no longer running"

## Launch
P1-R 2026-11-18T21:58:23+07:00 pid 17331, clean quit via Exit menu (row in evidence/launch-log.tsv).

## user.cfg sha256
Before and after: 63fa48cfe55eb515b30113b21e4732da70a1aa0b877c51dab3b8a4e979b9bd2a (equal).

## End state
`fcb-freecad status`: no FreeCAD pid. FreeCAD stopped.
