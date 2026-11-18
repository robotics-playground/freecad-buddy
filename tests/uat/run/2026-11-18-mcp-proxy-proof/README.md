# MCP cache proxy proof, 2026-11-18

Code: `scripts/automation/mcp_cache_proxy.py`. Tests: `tests/external/test_mcp_cache_proxy.py`.

## Plan and conditions (approved by the leader)

- One stdio proxy per upstream (`--server freecad-buddy-docker|cua-driver-docker`). `tools/list` comes from `.cache/mcp-proxy/<server>.json` (git-ignored). `tools/call` goes to the real upstream and the result passes through unchanged.
- Docs check: Claude Code docs (code.claude.com/docs/en/mcp, "Dynamic tool updates"): "In an interactive terminal session, Claude Code fetches the updated list from that server, so you don't need to reconnect it." Failed stdio servers are not retried automatically (only `/mcp` Reconnect).
- C1 retry safety: resend once only when the request provably was not delivered (a liveness ping fails before the send, or the HTTP upstream answers "Session terminated"). A connection that breaks after the send returns an error that says the outcome is unknown. Both paths have tests.
- C2 concurrency: one reconnect at a time (lock). A replaced connection closes only after its in-flight calls finish. Test: two parallel calls across a lost session.
- C3 polling cost: a poll while the container is down is one TCP connect (6901 for cua-driver, 18765 for freecad-buddy), no process start. Test: no transport starts while the port is closed.
- C4 transports: real FastMCP fakes over stdio and over streamable HTTP.
- C5 `list_changed` proof: the notification is logged on the client wire in `proof3-*.log`.

## Files

| File | Shows |
| --- | --- |
| `drive_proxy.py` | Client that starts the proxy exactly as `.mcp.json` does (cwd `C:\`) and times it |
| `lifecycle_proof.py`, `proof1-2-3-lifecycle.log` | Proofs 1 and 2, plus a container restart with the same proxy processes |
| `proof3-cua-fresh-clone.log`, `proof3-freecad-fresh-clone.log` | Proof 3: cache deleted, container down, then started |
| `proof2-*.log` | Single calls against the running container |
| `claude-mcp-list-*.txt` | `claude mcp list` output |

## Results

- Startup: `initialize` answered in 0.6 s and `tools/list` at 0.65 s with the container down, with the command from `.mcp.json` (`uv run --no-sync`), working directory `C:\`.
- Proof 1 (`proof1-2-3-lifecycle.log` phase 1, `claude-p-container-down.txt`): container down, cached lists of 46 and 60 tools; a call returns `isError=True` with the cause and the three start commands (0.5 s). `claude -p --mcp-config` (container down) shows both servers `connected` with 106 `mcp__` tools. `claude mcp list` (`claude-mcp-list-container-down.txt`) shows `Pending approval` for the changed project entries: the user must approve them once in an interactive `claude`; not done here.
- Proof 2 (phase 2): the same proxy processes, no restart, forward `query_capabilities` and `list_windows`; both return `isError=False` with `structuredContent`. Phase 3: container and FreeCAD restarted, same processes, both calls answered again.
- Proof 3 (`proof3-*.log`): cache deleted, container down: `tools/list` gives 0 tools. After the container started, cua-driver sent `notifications/tools/list_changed` (60 tools) at 15:06:53; freecad-buddy sent it (46 tools) at 15:08:17, 30 s after FreeCAD answered, because the connect retry delay grows to 30 s while the port is open but FreeCAD is not up. Not proven here: that interactive Claude Code reloads the list on the notification (the docs say it does); the user confirms once.
- Failure seen on the way: starting FreeCAD right after `compose up` aborts (Qt xcb plugin, desktop session not ready). `lifecycle_proof.py` waits for `fcb-session-env` first.

## Fix round 1 (verifier D1, D2, D3, T1, H1)

- D1: a running call races the answer against the end of the connection task and a probe of the upstream every 2 s (two failures end the call). `freecad-buddy-docker` probes `/healthz` (numeric `freecad_pid`, session id must not change); `cua-driver-docker` probes TCP 6901. A call whose probe already fails before the send gets the "not reachable" error. Live: `d1-live-stop-then-call.log` (`fcb-freecad stop`, then a call at once: answered in 0.0 s with the not-reachable error; FreeCAD restarted, same proxy answers).
- D2, D3, T1, H1: see the tests named in the leader report. Every scenario runs under `asyncio.wait_for` (30 s).
