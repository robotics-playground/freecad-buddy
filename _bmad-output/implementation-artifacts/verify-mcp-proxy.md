# Verify: MCP cache proxy

Subject: `scripts/automation/mcp_cache_proxy.py` (uncommitted, branch `feat/mcp-cache-proxy`), tests
`tests/external/test_mcp_cache_proxy.py`, `tests/external/fake_mcp_upstream.py`, docs.
Date: 2026-11-18. Verifier independent of the builder. Evidence:
`tests/uat/run/2026-11-18-mcp-proxy-verify/` (`scripts/`, `logs/`).

## Verdict

**FAIL.** One high defect (D1): on the HTTP upstream (`freecad-buddy-docker`), a call whose
connection fails after the request was sent never answers. Conditions 3, 4, 5 are proven.
Conditions 1 and 2 hold for stdio and for the restart case, but not for HTTP when the connection
dies during or just before a call.

## Leader conditions

| # | Condition | Result | Decisive evidence |
|---|-----------|--------|-------------------|
| 1 | No resend after send; `isError` "outcome unknown" | PARTIAL | Counting fake (`fake_counting_upstream.py`): tool writes a count line, then `os._exit(1)`. stdio: answer in 0.0 s, `isError=True`, "may or may not have run", count 1. HTTP (delay 0 s and 1 s): count 1, but **NO ANSWER after 40 s** (`logs/verify-crash.log`). Mutant M2 (resend after `CONNECTION_CLOSED`) is caught by the builder test. |
| 2 | One reconnect at a time; parallel calls get an answer | PARTIAL | Restart case: 6 parallel calls all answer, 1 transport opened. Port closed for good, calls within 5 s of last use: **6 of 6 hang 40 s**. Crash with 3 slow calls in flight: **4 of 4 hang**. Live P3b below. Mutant M6 (no lock) survives the builder tests. |
| 3 | No process spawn per poll while down | PROVEN | Live, both proxies, container down 120 s, process tree sampled every 50 ms (1,796 samples): 0 `docker.exe` started (`logs/live.log`). `refresh_loop` 3 s at 10 ms poll, closed port: 0 transports opened. Mutant M4 caught. |
| 4 | Streamable-HTTP fake test fails when pass-through breaks | PROVEN | Mutant M1 (drop `structuredContent`): 5 tests fail, 3 of them over HTTP (`logs/mutants.log`). |
| 5 | `list_changed` on the wire | PROVEN | Cache deleted, container up, proxies started with the `.mcp.json` command: client received `notifications/tools/list_changed` 0.3 s after start for both servers; then 46 tools listed. Mutant M5 caught. |

## Live run (`logs/live.log`)

- Container down: `initialize` 0.59 s, `tools/list` 0.61 s (46 and 60 cached tools). One call each:
  `isError=True`, cause and three start commands, 0.5 s.
- `fcb-freecad start` right after `compose up`: exit 0, "started", with the line
  `fcb-session-env: no xfce4-session is running; the desktop has not started`. FreeCAD (pid 22) did
  start. `healthz` showed `freecad_pid` only about 2 minutes later.
- Same proxy processes, container up: `query_capabilities` and `list_windows`, `isError=False` with
  `structuredContent`.
- P3b: `fcb-freecad stop`, then `query_capabilities` at once: **NO ANSWER after 90 s**.
- P3c: after more than 5 s idle: answer in 0.0 s, `isError=True`, "not reachable ...
  RemoteProtocolError". Correct.
- P3d: FreeCAD started again, same proxies: both calls answer, `isError=False`.
- Raw stdout of both proxies, container up, 5 requests: 4 lines, all JSON-RPC
  (`logs/raw-stdout.log`). Upstream cua-driver banner goes to stderr only.
- `.gitignore:40` `.cache/` matches; `git status` shows no cache file.

## Defects

### D1 high: HTTP call hangs forever when the transport fails after the send

- Where: `mcp_cache_proxy.py:259`
  `result = await connection.session.send_request(request, types.CallToolResult)` has no watch on
  the end of the connection. `mcp_cache_proxy.py:161-163` swallows the end of the owner task with
  no log.
- Cause, from SDK `mcp` 1.28.1:
  - The upstream dies during the call: `client/streamable_http.py` `_handle_sse_response` catches
    the stream error, logs at debug level and returns. No response and no error reach the session.
  - The POST fails (port closed, relay reset): the transport task group ends, the owner task ends.
    `BaseSession._receive_loop` runs its `finally` in a cancelled scope. The `CONNECTION_CLOSED`
    error does not reach the pending request (debug: owner done, `_response_streams` still `[2]`).
- When: any upstream death during a call (`fcb-freecad stop`, `compose down`, proxy crash), and
  any call within `LIVENESS_IDLE_SECONDS = 5.0` of the last use after the upstream went away.
- Effect: Claude Code waits until its idle timeout for stdio MCP servers, 30 minutes by default
  (`CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`, code.claude.com/docs/en/env-vars). The hung call also keeps
  `in_flight > 0`, so a retired connection stays open.
- Doc that is false for HTTP: `tests/close-loop/README.md`, "A call whose connection fails after
  the request was sent returns an error that says the outcome is unknown."
- Test gap: the after-send test (`flaky`) runs over stdio only. Mutant M8 (no liveness ping) also
  survives, so the ping path has no test that needs it.
- Fix direction (builder decides): race `send_request` against the end of `connection.owner`, and
  ping during a long call. If either fails, raise `OutcomeUnknown` without a resend. Log the
  exception that ends the owner task.

### D2 medium: `refresh_loop` stops for good on a cache-write error

- Where: `mcp_cache_proxy.py:366-379` catches only `UpstreamUnavailable`. `mcp_cache_proxy.py:327`
  uses one temporary name, `<server>.tmp`, for every process.
- Evidence: one simulated `PermissionError` in `_write_cache` stops the loop (`DEAD`, cache never
  written). Two writers on one cache path, 200 writes each: 155 `PermissionError` and 8
  `FileNotFoundError` on Windows.
- When: two Claude Code sessions in this repo run a proxy for the same server, and both write at
  the same time (for example, both start with an empty cache and see the container come up).
- Effect: no cache refresh and no `list_changed` for the rest of that process, with no log line.
- Fix direction: a temporary name per process (pid suffix). Catch and log any exception in the loop.

### D3 low: a cache that is valid JSON but not a tool list makes `tools/list` fail

- Where: `mcp_cache_proxy.py:319-323` checks only that the JSON parses.
- Evidence: `[1, 2]` and `[{"x": 1}]` give `McpError` on every `tools/list` until a refresh with
  the upstream up rewrites the cache. Garbage, empty and `{}` give 0 tools with no crash.

## Other checks

- Upstream that never answers: the proxy hangs forever on stdio and HTTP (30 s probes). It sets no
  timeout, so Claude Code's 30-minute idle timeout for stdio servers is the bound. That is
  acceptable for a tool that is only slow. With D1 it also applies to dead connections, and that
  is not acceptable.
- `_retire`: with one call in flight, the stdio upstream process stays alive until the call ends,
  then exits within 2 s (`in_flight=0`, owner done). With a hung call, the process stays until the
  waiter is cancelled, then exits.
- Cache write: `tmp` + `os.replace` is atomic for readers. A corrupt file does not crash startup.
- Mutants (scratch copies outside the repo, builder tests): M0 clean 11 passed. Caught: M1, M2, M3,
  M4, M5, M7 (M7 by a hang). Survived: M6 (no lock), M8 (no liveness ping).

## Gates

- `uv run ruff check .`: all checks passed.
- `uv run python scripts/check_imports.py`: OK.
- `uv run ruff format --check` on the 3 changed `.py` files: already formatted.
- `uv run pytest tests/external -q`: 1795 passed, 4 skipped.
- `%APPDATA%\FreeCAD\v1-1\user.cfg` SHA-256 `b89a9771...d85a0`: unchanged.
- End state: FreeCAD stopped and the container removed (`compose down`). No proxy process started
  by this verifier is left.

## Re-run at 0eae6f8

Commit `0eae6f8` on `feat/mcp-cache-proxy` (fix round 1). Triage:
`triage-mcp-proxy-v1.md`. Evidence: `tests/uat/run/2026-11-18-mcp-proxy-verify/rerun-0eae6f8/`.

### Verdict

**PASS.** D1, D2, D3, T1 and H1 are fixed and proven. No new defect of high or medium severity.
One low test gap (mutant M7 survives).

### Rows

| Row | Result | Decisive evidence |
|-----|--------|-------------------|
| D1 | FIXED | Counting fake, HTTP: upstream dies after the send (delay 0 s and 1 s): answer in 7.1 s, `isError`, "may or may not have run", count 1. stdio: answer in 0.0 s, count 1. Port closed within 5 s of the last call: 6 of 6 parallel calls answer "not reachable" in 3.1-5.6 s. Crash with 3 slow calls in flight: 4 of 4 answer in 5.0-7.1 s (`logs/verify-crash-long-parallel.log`). Live P3b: `fcb-freecad stop`, then an immediate call: answer in 0.0 s, "not reachable" (old code: no answer after 90 s). Live P8: in-container MCP proxy killed with `pkill -9` during a `script_exec`: outcome-unknown answer 3.0 s after the kill (`logs/live.log`). |
| D1, long call | NOT CUT | Fake HTTP tool that sleeps 60 s on a healthy upstream: answer after 60.0 s, `isError=False`. Live P5: `script_exec` with `time.sleep(25)` on the FreeCAD main thread: answer after 25.2 s, status `OK`. |
| D2 | FIXED | One failed cache write: the loop keeps running and writes the cache on the next cycle. Two writers, 200 writes each, one path: 0 errors, final file valid. Mutants M11 and M12 caught. |
| D3 | FIXED | `[1, 2]`, `[{"x": 1}]`, `{}`, garbage, empty: constructor OK, `tools/list` gives 0 tools. Mutant M13 caught. |
| T1 | FIXED | M6 (no lock) is red: `test_should_open_one_transport_when_parallel_calls_meet_a_lost_session`. M8 (no liveness ping) is red: `test_should_reconnect_before_send_when_idle_stdio_upstream_died`. |
| H1 | FIXED | Hang mutant M9 (no in-flight watch): 2 HTTP tests fail at 32.7 s each (30 s bound plus close); the suite ends in 86 s. |

### Probe cost

- In flight: 30 probes during a 60 s call (period 2 s). Idle: 0 probes in 20 s from the call path.
  Each call also runs one probe before the send.
- Freecad probe is an HTTP GET of `/healthz`. Cua probe is a TCP connect to 6901. Neither starts
  a process. Live: 0 `docker.exe` started in 30 s with the container down.
- `/healthz` while FreeCAD is busy: 50 host samples during the 25 s `script_exec`, slowest
  0.032 s, all with a numeric `freecad_pid`. `/healthz` reads the pinned record in the proxy
  (`src/freecad_buddy/hosts/gui_external/entry.py:78-85`). Tool calls run in a worker thread, so
  `/healthz` does not wait for FreeCAD.

### Other live observations

- P7: FreeCAD killed with `pkill -9` during a call. The in-container proxy answers itself at once
  with `WORKER_CRASHED` ("listener connection dropped"), and the cache proxy passes it through.
- P6: `fcb-freecad stop` during a 25 s `script_exec` waits for the window close, prints
  "window close timed out; killing", and the call finished first with `OK`. This is the container
  helper, not the proxy.
- `fcb-freecad start` right after `compose up` printed "started" with
  `no xfce4-session is running`. FreeCAD started, but `/healthz` was ready only after about 85 s.
- Same proxy processes across down, up, two FreeCAD restarts and a kill: every call answered.

### Mutants (`logs/mutants.log`, scratch copies outside the repo)

M0 clean: 25 passed. Red: M1, M2, M2b (resend after connection end), M3, M4, M5, M6, M8, M9, M10
(no probe before send), M11, M12, M13. Survived: M7 (close a replaced connection while calls are
in flight).

### Findings

- Low, test gap: M7 survives. No test needs `if connection.in_flight == 0`
  (`mcp_cache_proxy.py:251`). The watcher now turns such an early close into outcome-unknown
  instead of a hang, so the effect is a false outcome-unknown answer for a parallel call, not a
  hang.

### Gates

- `uv run ruff check .`: all checks passed.
- `uv run python scripts/check_imports.py`: OK.
- `uv run ruff format --check` on the 3 changed `.py` files: already formatted.
- `uv run pytest tests/external -q`: 1809 passed, 4 skipped.
- `user.cfg` SHA-256 `b89a9771...d85a0`: unchanged.
- End state: container removed, no proxy or fake process left by this verifier.
