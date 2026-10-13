---
title: 'Story 10.6 goal C: the addon never adopts an orphan or foreign server on :8765'
type: 'bugfix'
created: '2026-10-13'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'feabd506f53972999210370b688c062d5accceb1'
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/sequence-diagrams.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** After an unclean FreeCAD kill, the MCP proxy it spawned keeps running and keeps `:8765`. The relaunched addon sees the port served, logs `MCP proxy already on …; not spawning`, and the orphan then serves the new FreeCAD through discovery. The addon also adopts any foreign server on `:8765` the same way (F-26; TC-01-14, TC-10-12, TC-12-15, TC-99-08; Story 10.6 AC4). AD-2 and AD-24 require the opposite: the proxy is bound to the FreeCAD that spawned it and exits when that FreeCAD is gone, it serves `/healthz` with its identity, and the addon's already-served check probes `/healthz` so a foreign or stale server is an error surfaced to the operator, never a silent reuse.

**Approach:** The proxy pins the discovery record it first connects to (listener pid and token). It reconnects only to that record and exits once that pid is gone. It serves `GET /healthz` with its service name, the pinned FreeCAD pid and a session id derived from the token, never the token. At start, when `:8765` is served, the addon probes `/healthz` and does not reuse what it finds.

**Decisions (human, 2026-10-13):**
- D1 — Orphan at start: the addon waits up to 10 s for `:8765` to free, then spawns as normal. If it is still held, it logs ERROR (an orphan proxy from an older build; end it by hand) and does not spawn.

## Boundaries & Constraints

**Always:**
- `/healthz` discloses no secret: no token, no path, no environment.
- The RPC listener comes up in every case; a proxy problem never stops it.
- The addon never kills a process it did not spawn, and never acts on a pid read from `/healthz`.

**Never:**
- No MCP bearer token or Origin check (AD-3 HTTP auth is separate work).
- No change to the `:8765` port or `.mcp.json`.
- No new environment variable or preference.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal start | `:8765` free | addon spawns the proxy as today | N/A |
| Healthz | `GET /healthz` on a running proxy | `200`, JSON `service`, `freecad_pid`, `session_id` | no token in the body |
| FreeCAD killed | proxy's pinned pid exits | proxy exits within a few seconds; `:8765` freed | logged once in `mcp-proxy.log` |
| Pinned reconnect | proxy loses its connection; another FreeCAD's record is newer | proxy reconnects only to its pinned record; calls return `WORKER_CRASHED` once that pid is gone | no adoption |
| Orphan at start | `:8765` held by a freecad-buddy proxy whose `freecad_pid` is dead | addon waits up to 10 s for the port to free, then spawns | still held: ERROR in `addon.log`, not spawned, listener up |
| Other FreeCAD's proxy | `:8765` held by a freecad-buddy proxy whose `freecad_pid` is alive and not this process | not spawned; listener up | ERROR in `addon.log` naming the other pid |
| Foreign server | `:8765` served, `/healthz` absent or not freecad-buddy | not spawned; listener up | ERROR in `addon.log`: port held by another program |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/hosts/gui_addon/bootstrap.py:221-225` -- `_port_open` (0.3 s TCP probe). `:324-388` `_start_mcp_proxy` and `_provision_and_spawn` both skip the spawn with `MCP proxy already on …; not spawning` when the port answers. `:391-406` `_spawn_mcp_proxy`. `:409-430` `stop_bridge` terminates only its own child. The listener and discovery file are written before the proxy spawns (`start_bridge`, `:116-180`).
- `src/freecad_buddy/hosts/gui_external/entry.py:60-68` -- `build_app`: `Starlette(routes=[Mount("/mcp", …)])`; add the `/healthz` route here. `:71-95` `run`: builds `RpcClient()` with discovery; the watchdog and the pin start here.
- `src/freecad_buddy/adapters/rpc_client.py:118-135` -- `discover` returns the newest live record. `RpcClient._record` calls it on every reconnect; the pin goes here (an optional pinned pid, GUI defaults otherwise unchanged).
- `src/freecad_buddy/usecases/process.py:12` -- `pid_alive`, Windows-safe.
- The addon's spawn goes through a venv launcher on Windows (`.venv\Scripts\python.exe` starts a second python), so the proxy's parent pid is not FreeCAD; use the discovery record's `pid`.
- Tests: `tests/external/test_gui_external_proxy.py`, `tests/external/test_rpc_client.py`, the bootstrap tests (`grep -l _start_mcp_proxy tests/external`).
- UAT: `tests/uat/testcases/TC-99-ad-conformance-gaps.md` TC-99-08 lists `/healthz` as a gap; TC-01-14, TC-10-12, TC-12-15 record F-26.
- Design: `ARCHITECTURE-SPINE.md` AD-2 and AD-24 already state the rule; `design/sequence-diagrams.md:60-92` shows the boot probe.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/adapters/rpc_client.py` -- `RpcClient` can pin the first record it connects to and then reconnect only to a live record with the same pid and token.
- [x] `src/freecad_buddy/hosts/gui_external/entry.py` -- pin, a watchdog that exits the proxy once the pinned pid is gone (log once), and `GET /healthz`.
- [x] `src/freecad_buddy/hosts/gui_addon/bootstrap.py` -- replace both "already served" skips with a `/healthz` probe and the matrix rows, using stdlib `http.client` with a short timeout. `start_bridge` runs on the Qt main thread, so the probe and the D1 wait run on a daemon thread, as `_provision_and_spawn` does, and `stop_bridge` cancels and joins it.
- [x] `tests/external/` -- a test per matrix row; the bootstrap rows with a stub HTTP server on a free port (patch `_MCP_PORT`).
- [x] `tests/uat/testcases/` -- TC-99-08 and the F-26 expectations in TC-01-14, TC-10-12, TC-12-15.
- [x] `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md` -- the proxy pin, watchdog and `/healthz` in the GUI section.

**Acceptance Criteria:**
- Given FreeCAD with its proxy, when FreeCAD is killed uncleanly and relaunched, then the old proxy has exited or is refused per Q1, and the new FreeCAD's tools answer through a proxy whose `/healthz` names the new pid (cua-driver screenshot of the relaunched window).
- Given a foreign HTTP server on `:8765`, when FreeCAD starts, then `addon.log` has one ERROR, no proxy is spawned, and the listener is up.

## Implementation Notes

- Pin is eager: `run` calls `RpcClient.pin()` before it serves, so a proxy that never gets a tool call still has a pid for its watchdog. A proxy started before any FreeCAD pins on its first connect.
- Watchdog waits `_EXIT_GRACE_S` (1 s) after it sees the pid gone, then `os._exit(0)`. The grace lets a call that failed with the FreeCAD deliver its `WORKER_CRASHED` reply (TC-10-12). Measured with real processes: kill to proxy exit and port free = 2.2 s.
- `session_id` = first 16 hex of SHA-256(token). Service name lives in `contracts/rpc.MCP_PROXY_SERVICE`, shared by proxy and addon.
- A healthz body with `freecad_pid: null` is an unpinned proxy. Its watchdog never ends it, so the addon logs one ERROR at once, with no wait.
- A holder without `/healthz` (another program, or a proxy of an older build) gets the D1 wait too: up to 10 s for the port to free, then spawn or ERROR.
- `bootstrap._provisioner` / `_cancel_provisioning` keep their names (the infc bootstrap tests patch them) but now also hold the port-probe thread.
- Tests: `tests/external/test_gui_addon_proxy_start.py` (bootstrap rows), `tests/external/test_gui_external_identity.py` (healthz, watchdog), `tests/external/test_rpc_client.py` (pin). The PySide stub moved from `test_viewport_port.py` into the `stub_qt` fixture in `tests/external/conftest.py`.
- TC-99-08 now passes, so it moved to the green gate as TC-01-15, per the TC-99 promotion rule.

- GUI check on FreeCAD 1.1.4 (junction install, 2026-10-13):
  - Unclean kill: FreeCAD started from the agent shell (pid 8432; `Stop-Process` and `kill_app` are refused on a FreeCAD that `cua-driver launch_app` started at a higher integrity level). `/healthz` named `freecad_pid: 8432`. After `Stop-Process -Force`, the proxy exited and `:8765` was free 1.53 s later, with one `mcp-proxy.log` WARNING `FreeCAD pid 8432 has exited; the MCP proxy exits and frees port 8765`.
  - Relaunch: new FreeCAD pid 7524 spawned its own proxy; `/healthz` named `7524`; `document_list` returned `OK`; the window screenshot shows the Start page painted, no `Not Responding`, no modal.
  - Foreign server: a stub `http.server` held `:8765` (`/healthz` 404). FreeCAD started its listener, then after 10.0 s logged one ERROR `MCP proxy not started: port 8765 is still held by another program, or by an MCP proxy from an older freecad-buddy build … The RPC listener is up.`; no proxy was spawned.

## Spec Change Log

## Review Triage Log

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | An unpinned proxy (`freecad_pid: null`) never exits; the addon waits 10 s and logs a wrong "orphan" ERROR; design row is wrong (blind, edge-case, verification-gap) | medium | `exit_when_freecad_exits` acts only on an int pid. | patch |
| 2 | A holder with no `/healthz` gets the ERROR at once; frozen D1 says wait up to 10 s first (edge-case) | low | D1 names the older-build orphan, which has no `/healthz`. Waiting runs on a background thread. | patch |
| 3 | `stop_bridge` can cancel after the port frees and before the spawn (edge-case) | low | `_resolve_and_spawn(on_thread=True)` does not re-check the cancel event. | patch |
| 4 | Cancel test cannot tell cancel from the 10 s timeout (blind) | medium | Both end with no spawn; the test checks only that. | patch |
| 5 | No test for a holder that never answers HTTP, or for an unpinned watchdog (blind, edge-case) | low | Probe timeout and unpinned-watchdog paths untested; tests are cheap. | patch |
| 6 | `entry.run` wiring (pin at start, watchdog start) has no test (blind, verification-gap) | medium | Removing either line fails no test; it is the main fix. | patch |
| 7 | `/healthz` test would pass a `token[:16]` leak (verification-gap) | medium | It checks only a non-empty string and the full token's absence. | patch |
| 8 | Pin tests never vary the token (verification-gap) | medium | A pid-only match passes both tests. | patch |
| 9 | Sequence diagram draws the connection file after the spawn; hand-run proxy behaviour undocumented (blind) | low | The pin needs the record first; the debug fallback now exits with its FreeCAD. | patch |
| 10 | UAT appendices still say `/healthz` is absent and the addon does not double-spawn (blind) | low | `APPENDIX-A:26`, `APPENDIX-B:119`. | patch |
| 11 | TC-01-15 records the `uv` MSYS pid, not the port holder's pid (blind) | low | Cleanup can leave `:8765` held for later scenarios. | patch |
| 12 | Coverage-matrix CP counts and §5 rows not updated (blind, edge-case) | low | TC-01-15 added, TC-99-08 removed. | patch |
| 13 | The pin takes the newest record, so another FreeCAD writing a record before the spawn wins the race (blind, edge-case) | low | Needs two FreeCADs starting within about 1 s. Passing the addon pid to the child needs a new CLI option or variable, outside this spec. | defer |
| 14 | Pid reuse, or `pid_alive` returning True on access denied, keeps an orphan alive; the addon then names an unrelated pid (blind, edge-case) | medium | `process.py:25,33`. A second liveness signal is needed; probing the listener port from the watchdog would log a line every second. | defer |
| 15 | Pin kept when its first connect fails (edge-case) | low | Needs a live FreeCAD pid whose listener is gone; calls then return `WORKER_CRASHED`, which is accurate. | reject |
| 16 | Two FreeCADs that start together both spawn; the second proxy cannot bind and no ERROR is logged (edge-case) | low | Same as before this change. | reject |
| 17 | ERROR reaches only `addon.log`, not the operator (blind) | false | `bootstrap.py:82-84`: addon logs reach the Report View; the file mirrors them. | reject |
| 18 | AD-2 says the addon probes `/healthz` "for the session id", but the code classifies by service and pid; `session_id` has no reader (blind) | low | At addon start no own proxy exists yet, so a session-id compare can only mismatch; spine wording is the owner's call. | defer |
| 19 | CLAUDE.md and AGENTS.md §16 still say the addon does not double-spawn (blind, implementer) | low | Agent-context files; the owner asked for the edit, made in this change. | patch |
| 20 | UAT has no scenario for "another live FreeCAD's proxy" or the forced orphan wait (blind) | low | Story 10.7 maintains the suite. | defer |
| 21 | `/healthz` is unauthenticated, with no Origin check, and reveals the FreeCAD pid (blind) | low | The AD-3 HTTP auth gap (TC-99-02) covers the whole port; the spec excludes it. | defer |
| 22 | Provisioning path with a held port is untested (verification-gap) | low | Needs a release-install setup; the post-provision port check was untested before too. | defer |
| 23 | `pin` names both a constructor flag and a method (blind) | low | Naming only. | reject |
| 24 | Bridge stop and start inside one FreeCAD may leave the old proxy pinned (verification-gap) | maybe-false | Not shown reachable; a clean File > Exit freed `:8765` in the 10.6b GUI run. | reject |

## Verification

**Commands:**
- `uv run pytest tests/external -q` -- expected: all pass.
- `uv run ruff check . && uv run python scripts/check_imports.py` -- expected: clean.

**Manual checks:**
- GUI (cua-driver, `freecad-gui-e2e-harness.md`): kill FreeCAD with `Stop-Process`, confirm the old proxy exits, relaunch, check `/healthz` names the new pid and `fcb.py document_list` answers; then hold `:8765` with a stub server, start FreeCAD, check the ERROR line and that no proxy spawned.
