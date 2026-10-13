---
title: 'Story 10.6a: Two-process headless host'
type: 'refactor'
created: '2026-10-13'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '60b49d517d5aa0e31f4f264a97d2fa82ac56bbc7'
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md'
  - '{project-root}/_bmad-output/planning-artifacts/sprint-change-proposal-2026-10-13.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The headless H1 host runs the MCP server and FreeCAD in one process. FreeCAD never releases the GIL during a C++ operation, so no thread in that process can bound a call (sprint-change-proposal-2026-10-13, AD-2). Story 10.6 needs a process boundary first.

**Approach:** `freecad-buddy serve --transport stdio --mode inline` becomes a front process that serves MCP over stdio, never imports FreeCAD, and spawns one FreeCAD worker child with `sys.executable`. The worker runs today's H1 registry behind `RpcListener.serve_forever_inline()`. The front forwards every tool call over RPC. Behaviour seen by the MCP client does not change; the time bound is Story 10.6.

**Decisions (human, 2026-10-13):**
- D1 — Audit writers. The front keeps `mcp_server.build_server` with the audit sink and writes the adapter pairs, including the audited `script_exec`-off denial (Story 12.1 AC2), the non-string `doc` refusal and the document-suspect refusal. The worker sets only `confirm.set_approval_sink` and `view_fit.set_audit_sink` for bracket and camera records; its listener gets no `audit`. Both processes append to the same file, one call at a time, so records stay identical to the single-process host. Design §4.1 changes to say this.

## Boundaries & Constraints

**Always:**
- Same CLI, same stdio protocol, same tool list, same envelopes, same audit records as the single-process host.
- The front never imports `FreeCAD`; the worker never imports `mcp` (AD-12).
- The token goes from the front to the worker over the worker's stdin pipe. The worker writes no discovery file. The RPC hop requires the token (AD-3).
- Stdout of the front carries only the MCP protocol; all logs go to stderr (AD-3).
- GUI behaviour does not change; the GUI tests pass unchanged (D7).

**Never:**
- No time bound, quarantine or per-call read timeout (Story 10.6).
- No automatic worker restart. No new environment variable, flag or CLI option.
- No change to the GUI addon (`hosts/gui_addon/`).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Start | `serve --transport stdio --mode inline` | front spawns one worker; MCP `initialize` works | N/A |
| FreeCAD missing | interpreter cannot `import FreeCAD` | worker exits 2 with today's message; front exits 2 | message on stderr |
| Tool call | any tool | same envelope as single-process host | N/A |
| stdin EOF, worker idle | client closes | worker and front exit 0 | log once at INFO |
| stdin EOF, worker busy | worker has not exited 5 s after its stdin closes | front ends it, exits 1 | log once at ERROR |
| Worker died | worker process exited | each next call `WORKER_CRASHED`, message says restart the headless host | no restart |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/hosts/headless/entry.py:37-108` -- `FreeCADUnavailable`, `verify_freecad_importable`, `build_registry`, `run()`. Becomes the front. `build_registry` and the FreeCAD check move to the worker.
- `src/freecad_buddy/adapters/rpc_listener.py:142-164` -- `_bind` always calls `_write_discovery`; `serve_forever_inline` binds then loops, so the caller cannot learn the port first. `:101-131` constructor; `:305-352` request handling with its own suspect state (never fires with an inline marshal).
- `src/freecad_buddy/adapters/rpc_client.py:129-235` -- `RpcClient` finds its endpoint through `discover()` (`:148`); fixed `read_timeout_s` (`:137`, default 130 s). `call` never raises; a dropped connection gives `WORKER_CRASHED` "listener connection dropped".
- `src/freecad_buddy/hosts/gui_external/entry.py:43-134` -- `_MESH_VERIFY_SELF_READ`, `_mesh_verify_proxy_handler`, `build_proxy_registry`: forward each tool over one locked `RpcClient`; mesh verifiers RPC only the self-read leg and run the oracles locally (AD-9). The front reuses these.
- `src/freecad_buddy/adapters/mcp_server.py:59-66,213-292,329-338` -- `configure_stderr_logging`, `build_server` (suspect, audit, exec denial, timeout wording), `serve_stdio`. Imports `mcp`, so the worker must not import this module.
- `src/freecad_buddy/adapters/rpc_dispatch.py:128-136` -- `dispatch` runs `envelope.setdefault("display_decimals", shim.display_decimals())`; the argument is evaluated even when the key exists. `shim.display_decimals` (`usecases/shim.py:384-400`) does `import FreeCAD`, which would load FreeCAD into the front.
- `src/freecad_buddy/hosts/gui_addon/bootstrap.py:133-172` -- the GUI wiring of registry, token, capabilities and listener; the worker mirrors it with `gui:false, qt_loop:false`.
- `src/freecad_buddy/hosts/tool_catalog.py:1487-1583` -- `build_inline_handlers`. With a `Marshal(InlineExecutor())` it keeps today's 30 s `script_exec` bound (`ThreadExecutor`) inside the worker. Do not change (Story 10.6 replaces it).
- Tests importing `build_registry` from `hosts.headless.entry`: `tests/external/test_mcp_surface.py:36`, `test_confirm_contract.py`, `test_viewport_port.py:483-496`. `tests/external/test_rpc_listener.py:33` `SingleThreadExecutor` and a fake registry for listener tests.
- H1 launchers (unchanged CLI, regression checks): `benchmarks/g3/fault-injection/score_g3_replay.py:423-449` (CI `headless` job, `.github/workflows/ci.yml:123-131`), `scripts/automation/run_mcp_e2e.py:240-250`.
- Run in-FreeCAD code with the `fcb` env python: `%USERPROFILE%\micromamba\envs\fcb`, `PYTHONPATH=<env>\Library\bin`, `PATH=<env>\Library\bin;<env>\Library\lib;…` (Story 10.5).

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/adapters/rpc_listener.py` -- add constructor kwarg `discovery: bool = True` (False: `_bind` writes no file); make `_bind` public as `bind()`; `serve_forever_inline` binds only when not yet bound. GUI path unchanged.
- [x] `src/freecad_buddy/adapters/rpc_client.py` -- add constructor kwarg `endpoint: dict | None = None` (`host`, `port`, `token`; used instead of `discover()`); accept `read_timeout_s=None` for a blocking read.
- [x] `src/freecad_buddy/usecases/shim.py` -- `display_decimals` reads `sys.modules.get("FreeCAD")` and returns the default when FreeCAD is not loaded, so a preference read never loads FreeCAD into a process that has none.
- [x] `src/freecad_buddy/hosts/rpc_proxy.py` (new) -- move `_MESH_VERIFY_SELF_READ`, `_mesh_verify_proxy_handler`, `build_proxy_registry` here from `gui_external/entry.py`, which imports them. Shared by both proxy hosts without loading uvicorn into the stdio front.
- [x] `src/freecad_buddy/hosts/headless/worker.py` (new, stdlib + FreeCAD only) -- `run()`: stderr logging; FreeCAD check (exit 2, today's message); read the token line from stdin; sweep; caps from env; warm-up called directly; `build_registry(DocumentRegistry(), caps, Marshal(InlineExecutor()))` (moved here); bracket and camera sinks per D1 (`AuditSink(default_audit_path().resolve())`); `RpcListener(..., discovery=False, capabilities={gui:false, qt_loop:false, exec_enabled})`; `bind()`; write `{"port": N}` line to stdout and flush; `os.dup2(2, 1)` so later stray output cannot fill the pipe; daemon thread calls `listener.stop()` on stdin EOF; `serve_forever_inline()`; return 0. Runnable as `python -m freecad_buddy.hosts.headless.worker`.
- [x] `src/freecad_buddy/hosts/headless/entry.py` -- front `run()`: stderr logging; spawn the worker (`stdin`/`stdout` pipes, `stderr` inherited); write `secrets.token_urlsafe(32)`; read the port line (EOF: return the worker's exit code); `RpcClient(endpoint=…, read_timeout_s=None)` wrapped in a client whose `call` returns `WORKER_CRASHED` ("headless worker exited with code N; restart the headless host") once the worker has exited; `build_proxy_registry`; `build_server` with the audit sink; `serve_stdio`. Shutdown: close the client and the worker stdin, wait 5 s, else kill the worker, log once at ERROR, return 1. Keep `KeyboardInterrupt`. Update the module docstring.
- [x] `tests/external/` -- update the `build_registry` imports to `hosts.headless.worker`. New `test_headless_two_process.py`: listener with `discovery=False` writes no file and serves an `RpcClient(endpoint=…)`; a wrong token is refused; the exited-worker client returns the restart message without RPC; shutdown returns 0 for a stub worker that exits on stdin EOF and 1 with one ERROR log for one that ignores it (grace injected); `display_decimals` with FreeCAD not loaded returns the default. Under an interpreter with FreeCAD (skip otherwise): stdio end-to-end through the CLI — `initialize`, `tools/list` equal to the in-process registry's names, `query_capabilities` `OK`, a `script_exec` round trip; and two subprocess probes: the front's import set after building its stack holds no `FreeCAD`, the worker module's holds no `mcp`.
- [x] Design docs -- `integration-mcp-freecad.md` §4.1 audit sentence per D1; `project-structure.md` adds `hosts/rpc_proxy.py`.

**Acceptance Criteria:**
- Given the `fc`/`fcb` env, when `score_g3_replay.py --check` and `run_mcp_e2e.py` run over the CLI, then they pass as on the single-process host.
- Given the GUI tests (`test_rpc_listener.py`, `test_rpc_client.py`, `test_gui_external_proxy.py`), when they run, then they pass with no change to their expectations.
- Given the front and the worker, when their imports are probed, then the front has no `FreeCAD` and the worker has no `mcp`.

## Implementation Notes

- Worker sends its stdout to stderr (`os.dup2(2, 1)`) at the start and writes the port line to a saved copy of the pipe, so warm-up or FreeCAD console output cannot corrupt the port line. The front closes the worker's stdout after the port line.
- Worker exits 1 when stdin closes before a token arrives; an empty token would pass `hmac.compare_digest("", "")`.
- `RpcListener.stop()` calls `sock.shutdown(SHUT_RDWR)` before `close()`: on Linux `close()` alone does not wake an `accept()` on another thread (checked in WSL), so every Linux shutdown would take the 5 s kill path. Windows refuses `shutdown()` on a listening socket; the error is caught.
- `worker._configure_stderr_logging` copies the format of `mcp_server.configure_stderr_logging`, which the worker cannot import (AD-12).
- Baseline failures, same at `60b49d5`: `run_mcp_e2e.py` 4/9 (`tree_summary:*` rows read `structuredContent`, which `query_tree_summary` does not send; `run_mcp_e2e.py:57`); fcb pytest `test_render_probe.py::test_render_capability_reports_none_with_reason_when_gui_absent` (assumes no FreeCAD); `ruff format --check .` flags 28 files outside this diff.

## Spec Change Log

## Review Triage Log

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | CI never runs the 3 FreeCAD-only tests (`ci.yml:111` sets no `PYTHONPATH`; `find_spec("FreeCAD")` is `None` in `fc`) | medium | `score_g3_replay.py:427-436` adds `lib` by hand; the CI step does not. The import-probe AC is unverified in CI. Setting it on the whole step would turn on `test_render_probe` (known no-FreeCAD assumption), so a separate step is needed. | patch |
| 2 | `ci.yml:101-103` comment says H1 is a single process | low | Comment text is now false; direct correction. | patch |
| 3 | `display_decimals` no-load test passes on old code without FreeCAD | medium | Old `import FreeCAD` raises `ImportError` in uv/`fc` and returns the default; nothing enters `sys.modules`. Test cannot fail. | patch |
| 4 | Audit parity (D1) untested; e2e sets `FREECAD_BUDDY_AUDIT_LOG` but never reads it (blind + verification-gap) | medium | Deleting `confirm.set_approval_sink` in `worker.run` loses bracket records and no test fails. | patch |
| 5 | Linux `shutdown()` wake in `RpcListener.stop` only checked through a race | medium | Test at `test_headless_two_process.py:97-105` stops before the thread re-enters `accept()`. | patch |
| 6 | `shut_down_worker` returns 0 after the worker crashed with a non-zero code (edge-case) | medium | `worker.wait(timeout)` returns at once for a dead worker; `return 0`. A crashed session ends as a clean exit. | patch |
| 7 | e2e test can hang on `readline()` and leaves host + worker running on failure (blind + edge-case) | low | No `finally: process.kill()`; EOF gives `JSONDecodeError`. Direct fix. | patch |
| 8 | `start_threaded` / `stop` docstrings still say the discovery file is always written/deleted | low | `rpc_listener.py` docstrings vs `discovery` flag; direct correction. | patch |
| 9 | `shim.display_decimals` docstring names the headless front (use-case ring documents a host) | low | AD-1 ring rule; wording-only fix. | patch |
| 10 | `serve_forever_inline` returns configured host, not `getsockname()` host | low | Only caller (`worker.py:133`) ignores the value; fix adds state. | reject |
| 11 | Local process can hold the worker's single connection before the front's first handshake (no handshake timeout) | medium | `_handshake` has no `settimeout`; `_accept_loop` serves one connection at a time. Same in GUI mode, where the discovery file publishes the port. Pre-existing listener design. | defer |
| 12 | `run()` wiring of `WorkerClient` not tested with a real dead worker (blind + verification-gap) | medium | Only a fake `_ExitedProcess` test. Needs a CLI + FreeCAD test; Story 10.6 drives the same path. | defer |
| 13 | Malformed port line / no `try` around spawn-to-serve (blind + edge-case) | low | A front traceback closes the worker's stdin, so the worker exits; a stray fd-1 write needs a `.pth` print before `run()`. Fix adds guards. | reject |
| 14 | Front read unbounded (`read_timeout_s=None`) can hang both processes | false | Frozen Never: "No ... per-call read timeout (Story 10.6)". Status quo of the single-process host. | reject |
| 15 | Front waits forever for the port line if worker startup hangs | low | Single-process host also blocked in `import FreeCAD` before serving. Status quo. | reject |
| 16 | macOS `accept()` may not wake on `close()` | low | No macOS CI leg (`ci.yml` is `ubuntu-latest` only); worst case is the 5 s kill path, not a hang. | reject |
| 17 | `stop()` change touches GUI listener untested | low | GUI tests pass unchanged; Windows `shutdown()` error is caught. | reject |
| 18 | `WorkerClient` passed where `RpcClient` is annotated | low | Duck-typed `call`; no type-check gate in `pyproject`; fix adds a Protocol. | reject |
| 19 | Front imports private `_worker_crashed` | low | Works; renaming changes `rpc_client` surface for one caller. | reject |
| 20 | Design §4.1 front bullet names read timeout and quarantine not built yet | false | Design records the target after Story 10.6 (`epics.md` sequencing 10.6a -> 10.6); the spec states the bound is Story 10.6. | reject |
| 21 | `endpoint` is a loose dict; error text says "discovery record" | low | Same dict shape as the discovery record already used; message wording only misleads in a programmer error. | reject |
| 22 | No INFO log of worker PID and port | low | Improvement, not a defect. | reject |

## Design Notes

```
front (stdio MCP, no FreeCAD)                     worker (python -m …headless.worker)
build_server(build_proxy_registry(client))  --RPC-->  RpcListener(registry, Marshal(Inline)).serve_forever_inline()
  stdin pipe: token line, then EOF = shut down       stdout pipe: {"port": N}, then dup2(stderr)
```

The front's read is unbounded, as the single-process host's call is today; Story 10.6 adds the bound. While a call is in flight the front's event loop is blocked, so it sees stdin EOF only after the call returns, as today; the 5 s shutdown rule covers a worker that stays busy afterwards, for example an abandoned `script_exec` body that holds the GIL. The listener's own suspect state never fires, because its inline marshal never times out; the front's `build_server` keeps today's suspect rule and wording. The worker reads the same `FREECAD_BUDDY_AUDIT_LOG` and working directory as the front, so both resolve the same audit file.

## Verification

**Commands:**
- `uv run pytest tests/external -q` -- expected: all pass (FreeCAD-only tests skip).
- `fcb` env: `python -m pytest tests/external -q` and `freecadcmd tests/run_tests.py` -- expected: all pass.
- `fcb` env: `python benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.1.x --run local --check --frames-check benchmarks/g3/fault-injection/frames-reference.json` -- expected: pass.
- `fcb` env: `python scripts/automation/run_mcp_e2e.py` -- expected: report all pass.
- `uv run ruff check . && uv run ruff format --check . && uv run python scripts/check_imports.py` -- expected: clean.
