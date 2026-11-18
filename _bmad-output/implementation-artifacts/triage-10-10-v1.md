# Story 10-10: triage, verifier round 1

Base: `b5064f1` on `story/10-10-uat-testcases-in-container`. Verifier report: `verify-10-10.md` (verdict FAIL, 3 medium, 4 low). Leader read TC-01:639 (D3): `grep "spawned MCP proxy" addon.log` runs on the host, where no such file exists.

| Id | Q | Required fix | Proof required |
| --- | --- | --- | --- |
| D1 | Q4 | Toggle Visibility: a token click on a tree item does not select it, and `press_key space` with a token prints `GrabFocus returned false` and exits 0. Rewrite TC-13:221-223, TC-13:744, TC-06:330, TC-02:240, TC-12:46, `test-plan.md:333`, `APPENDIX-B:262` to a route that works as measured (verifier: foreground pixel click on the tree row, then window-level `press_key space` with foreground), or another route you measure. The step must also say how to see that the press had an effect (an exit 0 alone proves nothing) | Run each rewritten step as written in the container; save the output and the visibility state before and after |
| D2 | Q4 | Recompute: the shortcut is `F5`, not `ctrl+r`; the Recompute leaf and toolbar button are listed while the document is dirty. Fix `test-plan.md:333`, `TC-12:46`, `APPENDIX-B:262` and the "Recompute is not listed" claim (spec Build Notes, proof) | Run once: Box `Touched` before, not after |
| D3 | Q2 | TC-01:639 greps a host `addon.log`, so the check always passes. Run it in the container on `$FCB_USER_DIR/freecad-buddy/addon.log`. This is a class of defect: sweep every test case for a file check that names a FreeCAD-state file (`addon.log`, `mcp-proxy.log`, `rpc-*.json`, `user.cfg`, `system.cfg`, `/tmp/...`, `FCB_TMP_*`, `workdir`) without `docker exec` or the container path, and fix each | The sweep command and its output (0 hits after); TC-01:639 run once with a planted proxy line: the check fails |
| D4 | Q2 | TC-01:361 dropped the "legacy `Mod` folder is empty" sub-check with no reason. Restore its container form (measure where the legacy folder would be in the container) or tag the line `hand` with the reason it has no container meaning | `then-verify-diff.txt` line updated |
| D5 | Q2 | TC-01:578 still says `LISTENING`; `ss` prints `LISTEN` | grep |
| D7 | Q2 | TC-11:312: `curl` prints `Couldn't connect`, not `connection refused`. Match the measured text | Run once, save output |
| D6 | Q1 | Leader: quality bar Q1 now also allows TC-09:403 (B-1, accepted) | none (leader edit) |

## After the fixes

One commit on the Story branch (the leader commits; builder reports the batch). If the batch passes about 60 changed lines outside the proof folder, say so. The same verifier re-runs D1-D7, then the red team attacks the whole Story diff.
