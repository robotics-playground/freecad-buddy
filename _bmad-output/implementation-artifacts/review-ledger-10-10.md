# Story 10-10: findings ledger

Quality bar: `quality-bar-10-10.md`. Spec: `spec-10-10-uat-testcases-in-container.md` (Build Notes hold the lens findings and their fixes).

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| B-1 | Q1 | — | builder-10-10 | accepted by leader | second observable change TC-09:403: the numbered `Windows` menu entry exposes only `Activates this window`, so the step uses the `Next` leaf until the title names the document; observable "view brought to the front" unchanged (leader read the diff) |
| B-2 | Q7 | — | builder-10-10 | accepted | TC-16:23 user project path `D:/Work/...` is in the base `031d8e8` too; unchanged |
| B-3 | Q4 | — | builder-10-10 | closed by verifier | Undo `ctrl+z` works; Recompute and Toggle Visibility fail: D1, D2 |
| D1 | Q4 | medium | verifier-10-10 at `b5064f1` | fixed-proven (`355690e`, verifier re-run) | Toggle Visibility route fails as written: token click does not select; `press_key space` exits 0 with `GrabFocus returned false` (TC-13:221-223, :744, TC-06:330, TC-02:240, TC-12:46, test-plan:333, APPENDIX-B:262) |
| D2 | Q4 | medium | verifier-10-10 | fixed-proven (`355690e`, verifier re-run) | Recompute shortcut is `F5`, not `ctrl+r`; Box stays `Touched`; leaf is listed while dirty |
| D3 | Q2 | medium | verifier-10-10; leader read the line | fixed-proven (`355690e`, verifier re-run) | TC-01:639 greps a host `addon.log`: check always passes. Class sweep required |
| D4 | Q2 | low | verifier-10-10 | fixed-proven (`355690e`, verifier re-run) | TC-01:361 dropped the legacy `Mod` sub-check without reason |
| D5 | Q2 | low | verifier-10-10 | fixed-proven (`355690e`, verifier re-run) | TC-01:578 `LISTENING` |
| N1 | Q4 | medium | verifier-10-10 at `355690e` | fixed-proven (`5ee4824`, verifier re-run) | TC-13:797-802 F2 rename editor has no element |
| N2 | Q1/Q4 | medium | verifier-10-10 | fixed-proven (`5ee4824`, verifier re-run) | TC-12:89, :272, :307 `selected` field absent in container tree |
| N3 | Q2 | low | verifier-10-10 | fixed-proven (`5ee4824`, verifier re-run) | TC-99:205, :223, :318, :333 Windows workdir form |
| N4 | Q2 | low | verifier-10-10 | fixed-proven (`5ee4824`, verifier re-run) | test-plan:332, APPENDIX-B:261, TC-12:47 menu-listed conditions wrong |
| N5 | Q4 | low | verifier-10-10 | fixed-proven (`5ee4824`, verifier re-run) | TC-02:240 Body must be expanded |
| C1 | Q4 | — | leader | fixed-proven (`5ee4824`, verifier re-run) | class sweep: action census of every cua-driver tool, action and tree field |
| R1 | Q2 | low | verifier-10-10 at `5ee4824` | fixed-proven (`498b53d`, verifier final re-run, text copied exactly) | test-plan.md:365 Document Recovery "can show"; button order Cleanup, Delete/Yes |
| R2 | Q4 | low | verifier-10-10 | fixed-proven (`498b53d`, verifier final re-run, text copied exactly) | `"$FCB_CUA" list_windows` prose with no stdin waits on cat (TC-01:363, TC-10:43/:146, TC-14:191/:229/:466/:484, TC-15:137/:154) |
| V-Q2 | Q2 | — | verifier-10-10 | accepted | TC-12-06 (TC-12:388-395): Undo dropdown never opens in the container; entry text read from `doc.UndoNames`; enabled Undo button and after-capture stay as GUI evidence |
| RT-1 | Q2 | medium | redteam-10-10 at `5ee4824` | fixed-proven (`498b53d`, verifier final re-run, text copied exactly) | TC-10:185, :260, :558, :595 `ss -ltnp ... ESTABLISHED` always empty |
| RT-2 | Q2/Q4 | medium | redteam-10-10; leader read the output | fixed-proven (`498b53d`, verifier final re-run, text copied exactly) | `script_exec` without `doc`: `'doc' is a required property` (TC-12:97, :273, TC-13:226, :359, test-plan:347) |
| RT-3 | Q4 | medium | redteam-10-10 | fixed-proven (`498b53d`, verifier final re-run, text copied exactly) | pixel clicks use window coordinates, screenshot is scaled 0.98: wrong row below y 450 |
| RT-4 | Q5 | medium | redteam-10-10 | fixed-proven (`498b53d`, verifier final re-run, text copied exactly) | fake docker always exits 0; `|| true` mutant passes 19 tests |
| RT-5 | Q2 | medium | redteam-10-10 (line from Story 10-9) | fixed-proven (`498b53d`, verifier final re-run, text copied exactly) | TC-01:83 pgrep pattern matches the GUI proxy: cannot pass |
| RT-low | — | low | redteam-10-10 | fixed-proven (`498b53d`, verifier final re-run, text copied exactly) | cua-driver exits 0 on tool errors |
| RT-tool | Q1/Q2 | low | redteam-10-10 | recorded | proof tools have blind spots: `then-check.py` sees only Then heads, `census.sh` only host words (neither sees RT-1..RT-3); `then-check.py` gives a `hand` line a reason by kind automatically, so a weakened hand edit still gets a reason. Covered by the verifier reading every `hand` line by eye |
| V1 | Q4 | low | verifier-10-10 at `498b53d` | deferred (deferred-work.md) | "Pixel points": scroll a row into view first |
| RT-nr | — | low | redteam-10-10 | recorded, no change | `fcb_paths.sh` no left boundary; bad JSON ignored (not reproduced) |
| D6 | Q1 | low | verifier-10-10 | fixed (leader) | quality bar Q1 now lists TC-09:403 |
| D7 | Q2 | low | verifier-10-10 | fixed-proven (`355690e`, verifier re-run) | TC-11:312 curl text `Couldn't connect` |

## Rounds
| Round | Head | Lenses | Result |
| --- | --- | --- | --- |
| 1 | uncommitted, then `b5064f1` | Blind, Edge Case, Verification Gap (inside `bmad-build`, builder-10-10) | fixes in Build Notes |
| verifier 1 | `b5064f1` | verifier-10-10 (opus/medium) | FAIL: 3 medium, 4 low; triage `triage-10-10-v1.md` |
| fix 1 | `355690e` | none (batch +73/-58 outside proof, past 60 lines; D1 route widened to every tree-row site) | verifier re-run, then red team on the whole diff |
| verifier 2 | `355690e` | verifier-10-10 | FAIL: D1-D7 proven fixed; 2 new medium, 3 low (same class); triage `triage-10-10-v2.md` with class sweep C1 and a stop rule |
| fix 2 | `5ee4824` | none (+95/-67 outside proof; C1 census 48 routes, 40 newly measured, 9 failing routes fixed) | verifier re-run |
| verifier 3 | `5ee4824` | verifier-10-10 | PASS: N1-N5, C1 proven (5 rows run by verifier); 2 new low (R1, R2); stop rule not triggered. Red team next |
| red team | `031d8e8...5ee4824` | redteam-10-10 (opus/high) | FAIL: 5 medium reproduced; triage `triage-10-10-rt.md` (with R1, R2) |
| fix 3 (red team) | `498b53d` | none (+61/-32 outside proof) | final verifier re-run, text copied exactly |
| final | `498b53d` | verifier-10-10 | PASS: RT-1..RT-5, R1, R2 proven by copying the text; 1 new low (V1, deferred). Verifier incident: a planted edit landed in the working tree after a failed `git worktree add`; restored, tree equal to `498b53d` (leader checked `git diff 498b53d`) |
