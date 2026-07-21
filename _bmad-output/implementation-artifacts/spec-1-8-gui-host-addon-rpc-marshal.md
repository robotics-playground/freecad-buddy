---
title: 'Story 1.8 — GUI Host: Addon, RPC Listener & Main-Thread Marshal'
type: 'feature'
created: '2026-07-22'
status: 'done'
review_loop_iteration: 1
followup_review_recommended: false
baseline_revision: '9f799b1853b477a2e2a13dabd2194afdae3bce08'
final_revision: 'a7bca0b1fa6c2140015bdab40b37e01d00ad2f33'
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-clients.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** The bridge only runs headless (H1 stdio, inline marshal). A FreeCAD GUI user cannot reach the same tools against their live session: there is no addon, no RPC listener, no Qt main-thread marshal, and no external RPC client. Every FreeCAD call in GUI mode MUST execute on the Qt main thread (off-thread calls crash), gated by a per-session token on a localhost-only socket (G0.1 GUI leg).

**Approach:** Implement the GUI topology from integration-mcp-freecad.md §2–4: an in-FreeCAD NDJSON JSON-RPC listener (`adapters/rpc_listener.py`, stdlib-only) that enforces the `rpc_hello` handshake + `hmac.compare_digest` token and dispatches every call through the existing `Marshal`; a Qt `QtMainThreadExecutor` pump (`hosts/gui_addon/pump.py`, QtCore only) so the marshal runs callables on the main thread via `postEvent`; a deferred-start addon (`InitGui.py` + `bootstrap.py`) that starts the listener only after `FreeCAD.GuiUp`, mints a `secrets.token_urlsafe(32)` token, and writes a 0600 discovery file; an external `adapters/rpc_client.py` that discovers the listener, handshakes, and turns tool calls into `ResultEnvelope`s; and `--mode rpc` wiring so the external MCP server serves those tools. Reuse `Marshal`, `MethodRegistry`, `build_registry`, `build_server`, and `contracts/rpc.py` unchanged.

## Boundaries & Constraints

**Always:**
- In-FreeCAD code (`adapters/rpc_listener.py`, `hosts/gui_addon/*`) imports **stdlib + FreeCAD API only**; Qt only in `hosts/**` and the two named `adapters/` exemptions. `check_imports.py` MUST stay green. `adapters/__init__.py` and `hosts/__init__.py` stay byte-empty.
- Listener enforces: first frame MUST be `rpc_hello` (else `-32002`, close); token compared with `hmac.compare_digest` (mismatch → `-32000`, close); `contract_version` mismatch → `-32004` with supported list, close. Requests processed strictly sequentially (single in-flight globally, AD-20).
- Every dispatched method runs through `marshal.call(...)`; on the GUI executor that means the Qt main thread via `postEvent`/`customEvent`. Tool-level failures return a `ResultEnvelope` (closed AD-17 status set); only protocol failures use JSON-RPC `error` codes.
- Marshal timeout → the listener returns envelope `TIMEOUT` with `detail.data.maybe_still_running: true` (reuse `rpc_dispatch` mapping) AND marks that document **document-suspect**: the next mutating call on that doc is refused with `INVALID_INPUT` until a `query_*` fingerprint/read call on that doc clears the flag.
- Bind `127.0.0.1` only; port from `FREECAD_BUDDY_RPC_PORT` if set else ephemeral (`bind(0)`). Discovery file at `<FreeCAD user appdata>/freecad-buddy/rpc-<pid>.json`, mode `0600`, deleted by the listener on clean stop; external client picks the newest file whose `pid` is alive and skips stale ones.
- Addon start is deferred + gated: `QTimer.singleShot(0, _deferred_start)`, re-poll every 500 ms until `FreeCAD.GuiUp`, give up + stderr warning after 60 s. `start_bridge()` is idempotent.
- All logging stderr-only; no `print()` in `src/` (ruff T201). Tokens/tracebacks never on stdout.

**Block If:**
- The MCP SDK pin (`mcp>=1.28,<2`) does not expose a usable streamable-HTTP serve entry for `hosts/main.py --transport http` — HALT with the missing API and options, do not silently fall back to stdio.
- FreeCAD's user-appdata path cannot be resolved without importing a GUI module (would break the stdlib-only listener rule) — HALT with the constraint.

**Never:**
- Never call FreeCAD/Qt from the listener accept thread directly — everything goes through the marshal. Never `QApplication.processEvents()` in a dispatched call (re-entrancy). Never start the MCP protocol server inside the addon (addon starts only the RPC listener).
- No live-GUI smoke test in this story (that is the human `gui_smoke` token in story 1.10); prove the path with a real-socket loopback using the inline/threaded executor.
- No remote bind, no auth bypass, no second copy of use-case logic, no branching on host identity inside `usecases/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Handshake OK | first frame `rpc_hello` with correct `contract_version` + token | `RpcHelloResult` with `freecad_version` + `capabilities`; connection proceeds | none |
| First frame not `rpc_hello` | any other method first | JSON-RPC `error` `-32002`, connection closed, attempt logged to stderr | protocol error |
| Bad/missing token | `rpc_hello` token ≠ session token | `error` `-32000`, connection closed | `hmac.compare_digest` false |
| Version mismatch | `contract_version` ≠ server's | `error` `-32004`, `data` lists supported versions, closed | protocol error |
| Normal tool call | valid `document_create` frame post-handshake | `result` = `ResultEnvelope` OK, echoed handle; ran via `marshal.call` | none |
| Marshal timeout | dispatched call exceeds method `timeout_s` | `result` envelope `TIMEOUT`, `maybe_still_running: true`; doc marked suspect | not a JSON-RPC error |
| Mutation after timeout | mutating call on a document-suspect doc | envelope `INVALID_INPUT` (`detail.message` cites document-suspect); no execution | fail closed |
| Read clears suspicion | `query_*` on the suspect doc succeeds | suspect flag cleared; subsequent mutation allowed | none |
| Unknown method | method not in registry | envelope `INVALID_INPUT` (`unknown method: …`) via `dispatch` | not a protocol error |
| Discovery: live listener | one `rpc-<pid>.json`, pid alive | client connects to it | none |
| Discovery: stale file | newest `rpc-<pid>.json` pid dead | client skips it, tries next / reports unreachable | envelope `WORKER_CRASHED` `{rpc:"unreachable"}` |
| Discovery: none | no discovery file | client reports listener-down | envelope `WORKER_CRASHED` |

</intent-contract>

## Code Map

- `src/freecad_buddy/adapters/rpc_listener.py` -- **stub to implement**: `RpcListener` (handshake/token/framing/dispatch, `start_threaded`/`serve_forever_inline`/`stop`), discovery-file write, session-suspect tracking.
- `src/freecad_buddy/adapters/rpc_client.py` -- **new**: external NDJSON client — discovery-file read, connect, handshake+token, `call(method, params) -> ResultEnvelope`, unreachable → `WORKER_CRASHED` envelope. Third-party allowed (external process).
- `src/freecad_buddy/adapters/marshal.py` -- existing `Marshal`/`Executor`/`InlineExecutor`/`MarshalTimeout`; reused unchanged (verify no edit needed).
- `src/freecad_buddy/adapters/rpc_dispatch.py` -- existing `MethodRegistry`/`RpcMethod`; already maps `MarshalTimeout`→`TIMEOUT`. Reused.
- `src/freecad_buddy/contracts/rpc.py` -- existing wire types + error codes; add `RPC_ERROR_AUTH`/`RPC_ERROR_SHUTDOWN` constants only if missing (currently `-32000` reused as WORKER_CRASHED — see Design Notes for the -32000 auth vs worker-crashed decision).
- `src/freecad_buddy/hosts/gui_addon/InitGui.py` -- **new**: workbench + deferred `_deferred_start` gate.
- `src/freecad_buddy/hosts/gui_addon/bootstrap.py` -- **new**: `start_bridge()` — build executor → registry → token → listener → discovery file; shutdown hook.
- `src/freecad_buddy/hosts/gui_addon/pump.py` -- **new**: `QtMainThreadExecutor` (QtCore `postEvent`/`customEvent`).
- `src/freecad_buddy/hosts/gui_addon/__init__.py` -- **new**, byte-empty is not required here (it is a host subpackage, not the ring root), but keep it minimal/import-free.
- `src/freecad_buddy/hosts/main.py` -- extend: `--mode rpc` / `--transport http` now build the external RPC-backed MCP server instead of erroring.
- `src/freecad_buddy/hosts/gui_external/entry.py` -- **new**: external GUI-attached server — `rpc_client` → `MethodRegistry`-shaped proxy → `build_server` → streamable-HTTP serve.
- `scripts/build_addon.py` -- **new**: assemble the FreeCAD addon (copy package + `addon/package.xml` + `InitGui.py`); honor `FREECAD_BUDDY_SRC` dev override.
- `addon/package.xml` -- existing metadata; verify `classname`/`subdirectory` match the assembled addon layout.
- `tests/external/test_rpc_listener.py` -- **new** pytest: real-socket loopback (listener + client), handshake/token/version/framing, timeout→suspect→clear, discovery liveness. Uses a threaded executor + fake registry (no FreeCAD).
- `tests/external/test_rpc_client.py` -- **new** pytest: discovery-file selection + unreachable envelope.
- `tests/external/test_check_imports.py` -- existing; extend expectation that new host/listener files stay clean.

## Tasks & Acceptance

**Execution:**
- [x] **Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)**
  - Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md` if present; else read `_bmad-output/project-context.md` (authoritative rules here).
  - Load `typescript-clean-code` is N/A (Python project); instead honor `project-context.md` ring/import/wire/security rules.
  - Read `integration-mcp-freecad.md` §2–4 and `integration-mcp-clients.md` §1–2 (mandatory context).
- [x] `src/freecad_buddy/adapters/rpc_listener.py` -- implement `RpcListener`: NDJSON framing (16 MiB cap, `\n`-terminated, UTF-8), sequential per-connection dispatch, `rpc_hello` enforcement, `hmac.compare_digest` token check, `contract_version` check, **exactly one** `marshal.call(lambda: registry.dispatch(name, params), method.timeout_s)` per request (the dispatched registry MUST hold un-marshaled handlers — see Design Notes), `start_threaded()->(host,port)`, `serve_forever_inline()`, `stop()`; write/delete the 0600 discovery file. Per-connection exception isolation: a malformed frame (non-dict `params`, unhashable/`None` `doc`, non-UTF-8, non-JSON, >16 MiB) replies `INVALID_INPUT` (or closes just that connection) and NEVER kills the accept loop. Document-suspect: add handle on a mutating `TIMEOUT`; clear only on a non-mutating `OK` whose `doc` equals that handle. Optional injected `AuditSink` writes before/after records for `mutating`/`exec` methods. -- core GUI transport + robustness + audit (AC1, AC2, AC3, AC4).
- [x] `src/freecad_buddy/hosts/headless/entry.py` (or a small `hosts/tool_catalog`/registry helper) -- add an **un-marshaled** registry builder for the listener path: same shared catalog + handlers that call the usecase directly (no inner `marshal.call`), while the existing headless `build_registry` (self-marshaling handlers over `Marshal(InlineExecutor())`) stays unchanged. -- fixes the double-marshal (AC2).
- [x] `src/freecad_buddy/adapters/rpc_client.py` -- external NDJSON client: newest-live-pid discovery, TCP connect (2 s), `rpc_hello`, `call(method, params)`; **never raises** — catch decode/JSON/`KeyError`/`ValueError`/`OSError` and synthesize an envelope; per-call read timeout so a wedged listener yields `TIMEOUT`/`WORKER_CRASHED`; connect-refused/stale/handshake → `WORKER_CRASHED {rpc:"unreachable"}`. -- external leg of AC2.
- [x] `src/freecad_buddy/hosts/gui_addon/pump.py` -- `QtMainThreadExecutor(QtCore.QObject)` with `_CallEvent`/`customEvent`. -- main-thread marshal (AC2).
- [x] `src/freecad_buddy/hosts/gui_addon/bootstrap.py` -- `start_bridge()` idempotent: `QtMainThreadExecutor` on the main thread, `Marshal(executor)`, the **un-marshaled** listener registry, mint token, `AuditSink`, `RpcListener(...).start_threaded()`; register `stop_bridge` on FreeCAD shutdown (`QCoreApplication.aboutToQuit`/`atexit`) so the listener + discovery file don't leak. -- addon wiring + lifecycle (AC1).
- [x] `src/freecad_buddy/hosts/gui_addon/InitGui.py` + `__init__.py` -- workbench class (registration only) + `_deferred_start` re-poll on `FreeCAD.GuiUp` (500 ms, 60 s cap) calling `start_bridge()`. -- deferred start (AC1).
- [x] `src/freecad_buddy/hosts/gui_external/entry.py` + `hosts/main.py` -- external GUI-attached MCP server: proxy `MethodRegistry` forwarding to `RpcClient` over the shared catalog, served over streamable HTTP; `--mode rpc --transport http` invokes it. Serialize `RpcClient.call` (lock or per-call client) and run it off the asyncio event loop so one call can't block the ASGI server. -- AC2 external path.
- [x] `scripts/build_addon.py` -- assemble the installable addon (package copy + `package.xml` + `InitGui.py` shim); `FREECAD_BUDDY_SRC` dev-mode override. -- AC1 packaging.
- [x] `tests/external/test_rpc_listener.py`, `tests/external/test_rpc_client.py` -- cover every I/O-matrix row over a real socket (threaded executor + fake registry). ADD: (a) a **double-marshal regression** — an executor that runs submitted callables inline on a single dedicated thread + an un-marshaled registry → a mutating call returns `OK`, not `TIMEOUT`; (b) malformed-frame isolation — non-dict `params` / unhashable `doc` / non-JSON line → `INVALID_INPUT` reply AND the listener still serves the next valid frame; (c) `rpc_client` never-raises on a discovery record with missing `host`/non-int `port` and on a listener that accepts then sends garbage; (d) suspect clears only on a read of the same handle. -- falsifiable proof of AC2/AC3/AC4 + the loop-1 fixes.
- [x] **Final Task: Quality Checks** -- run `python scripts/check_imports.py`, `ruff check src scripts tests`, `ruff format --check`, `python -m pytest tests/external`; report exact output.

**Acceptance Criteria:**
- Given a built/dev-mode addon, when FreeCAD GUI starts, then the listener starts only after `FreeCAD.GuiUp` (deferred `QTimer.singleShot`), binds `127.0.0.1`, and writes a 0600 discovery file carrying a `secrets.token_urlsafe(32)` token. *(AC1)*
- Given the external server started `--transport http --mode rpc`, when an MCP client calls any tool, then frames follow `contracts/rpc.py` (`rpc_hello`, `contract_version`, token via `hmac.compare_digest`); every FreeCAD call executes on the Qt main thread through the `postEvent` marshal; a wrong/missing token yields `-32000` and a closed connection. *(AC2)*
- Given a dispatched call that exceeds its marshal budget, when the timeout fires, then the client receives envelope `TIMEOUT` with `maybe_still_running: true` and the document goes document-suspect (next mutation on it refused until a fingerprint/read check clears it). *(AC3)*
- Given the RPC listener and marshal modules, when `check_imports.py` runs, then the listener is stdlib-only and the marshal imports QtCore only — no violations; `adapters/__init__.py` and `hosts/__init__.py` remain byte-empty. *(AC4)*
- Given the loopback test suite, when `pytest tests/external` runs, then every I/O-matrix row passes over a real socket without FreeCAD installed.

## Spec Change Log

### 2026-07-22 — bad_spec repair (loop 1)
- **Triggering finding:** Double-marshal deadlock (Blind Hunter, high). `bootstrap.py` passed one `Marshal` to BOTH `build_registry` (whose handlers already wrap every call in `marshal.call`) AND to `RpcListener` (which re-wrapped `dispatch` in `marshal.call`). On the single Qt main thread the inner `marshal.call` posts a second event to the same thread and blocks waiting for it — the thread is already blocked in the outer call, so it deadlocks. The inner call always hits `MarshalTimeout` → every GUI tool call returns `TIMEOUT` and every mutating call falsely marks its document suspect. AC2 ("every FreeCAD call executes on the Qt main thread") is therefore not actually met by the delivered wiring, and the loopback tests hid it by using a single `ThreadedExecutor` layer instead of the real nested wiring.
- **Amended:** Design Notes now fixes exactly ONE marshal layer for the GUI/RPC path — the listener owns the marshal; the registry it dispatches must hold **un-marshaled** handlers. Added a task to introduce a `build_rpc_registry`/`build_inline_handlers` split so the RPC path does not double-marshal, and a regression test that drives the listener with a real single-thread (`InlineExecutor`-on-a-dedicated-thread) executor and asserts a mutating call returns OK, not TIMEOUT.
- **Also amended (folded robustness gaps surfaced same pass, all caused by this change):**
  - Malformed-frame resilience: a request whose `params` is not a dict, or whose `doc` is unhashable, or a non-UTF-8 / oversized frame, currently escapes `_serve_conn` and **kills the accept thread** (only `accept()`'s `OSError` is guarded). Spec now requires `_serve_conn`/`_accept_loop` to catch per-connection exceptions, reply `INVALID_INPUT` where a frame is decodable, and never let one bad frame stop the listener.
  - `rpc_client.call` must **never raise**: it currently only catches `OSError`, so a decode/JSON error or a missing/!int `host`/`port` in the discovery record raises past the contract. Spec now requires all read/parse/lookup failures to synthesize an envelope, and a per-call read timeout so a wedged listener yields `TIMEOUT`/`WORKER_CRASHED` rather than hanging forever.
  - Concurrent HTTP sessions share one `RpcClient` (single socket/buffer/`_next_id`, no lock) and the proxy does blocking socket I/O on the asyncio loop. Spec now requires the proxy call to be serialized (a lock or per-call client) and offloaded off the event loop.
  - Audit at the trust boundary: the in-FreeCAD listener currently audits nothing, so a direct token-bearing RPC connection can drive mutations/`debug_exec` with no audit record. Spec now requires the listener to write audit records for mutating/exec calls (AD-17 "every mutation from Phase 0").
  - Suspect-clear precision + lifecycle: clear the suspect flag only on a successful read **of the suspect handle** (not any non-mutating OK), and register `stop_bridge` on FreeCAD shutdown so the discovery file + listener don't leak.
- **Known-bad state avoided:** a bridge that deadlocks on the first real GUI call, a listener a single malformed frame can kill, a client that raises instead of returning an envelope, and unaudited mutation via direct RPC.
- **KEEP (must survive re-derivation):** the whole in-FreeCAD listener design is correct and import-clean — NDJSON 16 MiB framing + `_FrameReader`, the `-32002`/`-32004`/`-32000` handshake order, `hmac.compare_digest` token, 0600 discovery file with `secrets.token_urlsafe(32)`, `start_threaded`/`serve_forever_inline`/`stop`. KEEP `hosts/tool_catalog.py` (the shared-catalog refactor is faithful — headless surface unchanged). KEEP the `RpcClient` discovery logic (newest-live-pid, cross-platform `_pid_alive`) and the `WORKER_CRASHED {rpc:"unreachable"}` synthesis. KEEP the Qt `pump.py` (`postEvent`/`customEvent`) and the deferred-start `InitGui.py`. KEEP all existing loopback tests; they stay valid — add to them, do not replace.

## Review Triage Log

### 2026-07-22 — Review pass
- intent_gap: 0
- bad_spec: 6: (high 3, medium 3)
- patch: 0
- defer: 3: (medium 0, low 3)
- reject: 8
- addressed_findings:
  - `[high]` `[bad_spec]` Double-marshal deadlock — GUI/RPC path double-wraps `marshal.call`; spec now fixes a single marshal layer (listener owns it; registry handlers un-marshaled) + regression test on the real nested wiring.
  - `[high]` `[bad_spec]` Malformed frame (non-dict params / unhashable `doc` / non-UTF-8 / >16 MiB) kills the accept thread — spec now requires per-connection exception isolation.
  - `[high]` `[bad_spec]` `rpc_client.call` raises on decode/parse/missing-key instead of returning an envelope — spec now requires never-raise + per-call read timeout.
  - `[medium]` `[bad_spec]` Concurrent HTTP sessions share one unsynchronized `RpcClient` + blocking socket I/O on the asyncio loop — spec now requires serialization + off-loop execution.
  - `[medium]` `[bad_spec]` Listener performs no audit — direct token'd RPC mutation/exec is unlogged; spec now requires listener-side audit (AD-17).
  - `[medium]` `[bad_spec]` Suspect flag cleared by any non-mutating OK + `stop_bridge` never registered (leak) — spec now requires read-of-the-suspect-handle to clear + shutdown hook.
- deferred (not this story): channel-error → status mapping precision in `rpc_client` (low); discovery-file write atomicity / `os.replace` (low); `build_addon.py` dev-shim guard behind an explicit `--dev` flag (low).
- rejected: `_start_deadline` module-global reset (fresh import resets it; not reachable in practice), second-`rpc_hello`-after-handshake handling (INVALID_INPUT is acceptable), Windows token-file confidentiality (loopback+token is the documented posture; OS ACL is out of Phase-0 scope), pid-reuse liveness (inherent best-effort), temp-dir discovery fallback (only hit when both env vars unset — not a real deployment), fixed-port-in-use crash surfacing (operator-set env, acceptable), `debug_exec` cross-process gate mismatch (fail-closed), snapshot-test-for-tool-surface (nice-to-have, `test_mcp_surface` already exercises the surface).

### 2026-07-22 — Review pass (loop 1 re-review)
- intent_gap: 0
- bad_spec: 0
- patch: 4: (high 0, medium 0, low 4)
- defer: 1: (medium 1)
- reject: 6
- addressed_findings:
  - `[low]` `[patch]` `rpc_client` collapsed every channel error to `WORKER_CRASHED` — now maps via `CHANNEL_ERROR_STATUS` (version/handshake → `INVALID_INPUT`), unmapped → `WORKER_CRASHED`; added `_channel_error_envelope` + two tests.
  - `[low]` `[patch]` listener accepted a wrong-type-but-hashable `doc` (int/bool) — now rejects any non-None non-`str` `doc` with `INVALID_INPUT`; removed the now-orphaned `_is_hashable`.
  - `[low]` `[patch]` handshake checked `contract_version` before the token, disclosing the supported-version list pre-auth — reordered to authenticate first.
  - `[low]` `[patch]` `FREECAD_BUDDY_RPC_PORT` non-integer crashed `start_bridge` — now warns and falls back to an ephemeral port.
- pass-2 verification: all six loop-1 findings independently confirmed FIXED (double-marshal via un-marshaled listener registry, malformed-frame isolation, `rpc_client` never-raises + per-call read timeout, shared-`RpcClient` lock + off-loop offload, listener-side audit, suspect-clear precision + `stop_bridge` shutdown hook).
- deferred (not this story, 1): mesh-verify oracle legs run on the Qt main thread in GUI mode (bounded GUI freeze on `verify_export_stl/3mf`; needs a partial-marshal mechanism — logged to `deferred-work.md`).
- rejected (6): client read-timeout 130s vs server 120s margin (10s slack adequate; deriving from tool timeout is speculative), atexit/aboutToQuit stacking on restart (singleton makes `stop_bridge` idempotent; harmless), shared `RpcClient` not closed on shutdown (OS reclaims FD at process exit), unknown-method marshaled before `INVALID_INPUT` (harmless main-thread hop), FIFO id-correlation in `rpc_client` (safe — every error path closes the socket; latent-only), suspect-not-set-on-dispatch-returned-TIMEOUT (unreachable in the shipped config — mesh-verify is non-mutating).

## Design Notes

**`-32000` reuse.** `contracts/rpc.py` currently defines `RPC_ERROR_WORKER_CRASHED = -32000` and maps it to `WORKER_CRASHED`. integration-mcp-freecad.md §2.3 assigns `-32000` to *auth failed*. Both are transport-close conditions but map to different statuses. Resolve additively per NFR10: keep `-32000` for auth (the AC2 requirement), and represent a dropped/crashed connection client-side by synthesizing a `WORKER_CRASHED` envelope in `rpc_client.py` (no wire code needed — it never reaches the client as a frame). If a distinct auth constant reads clearer, add `RPC_ERROR_AUTH = -32000` as an alias rather than renumbering (additive-only within the major). Do not invent new codes beyond §2.3's table.

**EXACTLY ONE marshal layer (critical — the loop-1 deadlock).** The marshal serializes work onto the Qt main thread; wrapping a call in `marshal.call` twice on that single thread deadlocks (the outer call blocks the thread that must run the inner one). So the RPC/GUI path must marshal at **exactly one** level: the `RpcListener` owns `marshal.call(lambda: registry.dispatch(...), timeout_s)`, therefore the `MethodRegistry` it dispatches must hold **un-marshaled** handlers (handlers that call the usecase directly, no inner `marshal.call`). The current `build_registry` produces *self-marshaling* handlers (each wraps `marshal.call`) — correct for the headless inline host (whose `Marshal(InlineExecutor())` is a no-op passthrough on the same thread) but WRONG behind the listener. Fix by splitting: keep an inline path that marshals in the handler (headless, unchanged) and add an un-marshaled registry builder for the listener. The GUI-external proxy registry is already un-marshaled (its handlers just call `rpc_client.call`), so it is unaffected. The regression guard is a listener test whose executor is a real single dedicated thread running submitted callables *inline on that thread* (mimicking the Qt main thread): a mutating call must return `OK`, never `TIMEOUT`.

**Document-suspect precision.** Per-listener `set[str]` of suspect doc handles. Consult before dispatching a `mutating` method; add the handle on a `mutating` call that returns `TIMEOUT`. Clear it ONLY when a **non-mutating call whose `doc` equals that handle** returns `OK` (a read that actually re-observes the document) — not on any non-mutating OK. Guard against an unhashable `doc` (reply `INVALID_INPUT`, never `in`-test an unhashable value) and a `None` handle (a no-`doc` mutating timeout marks a session-wide suspect flag, not a set entry).

**Robustness — no single frame or call may kill the bridge.** `_accept_loop`/`_serve_conn` must wrap per-connection work so a malformed frame (non-dict `params`, unhashable `doc`, non-UTF-8 bytes, a line that isn't JSON, or a >16 MiB frame) yields an `INVALID_INPUT` reply where decodable and otherwise closes just that connection — it must never propagate out and stop the accept loop. `rpc_client.call` must **never raise**: catch decode/JSON/`KeyError`/`ValueError`/`OSError` and return a synthesized envelope; set a per-call socket read timeout (≥ the tool `timeout_s`) so a wedged listener produces `TIMEOUT`/`WORKER_CRASHED` instead of hanging.

**Listener-side audit (AD-17).** The listener is the trust/execution boundary for a direct RPC connection, so it must write audit records for `mutating`/`exec` methods (before + after, status), mirroring `mcp_server`'s audit pattern. Inject an `AuditSink` into `RpcListener` (constructed in `bootstrap.py` at `_default_audit_path()`); a `None` sink (tests) disables it. This closes the "mutation via direct token'd connection is unlogged" gap without moving audit out of the external server for the proxied path.

**Concurrent HTTP proxy.** The GUI-external server shares one `RpcClient` across MCP sessions; its socket/buffer/`_next_id` are not concurrency-safe. Serialize proxy calls (a `threading.Lock` around `RpcClient.call`, or one client per call) AND run the blocking `rpc_client.call` off the asyncio event loop (e.g. `anyio.to_thread.run_sync`) so one in-flight call can't block the whole ASGI server.

**Testability without a GUI.** `Marshal` abstracts the executor. Tests inject a threaded executor for the real cross-thread timeout path, a single-dedicated-thread inline executor for the double-marshal regression guard, and `InlineExecutor` for the trivial path. The Qt `QtMainThreadExecutor` correctness is its `postEvent`/`customEvent` shape (reviewed vs the design doc), not unit-tested in CI (no Qt in the external env; live proof is the story-1.10 `gui_smoke` token).

Golden shape of the listener request loop (illustrative, ≤12 lines):
```python
def _serve_conn(self, conn):
    if not self._handshake_ok(conn):        # -32002/-32004/-32000 + close
        return
    for line in _iter_ndjson(conn):         # 16 MiB cap, \n framed
        try:
            req = json.loads(line)
            env = self._handle_request(req)  # gate suspect, marshal-once, audit, update suspect
        except Exception:                    # one bad frame never kills the loop
            env = _invalid_input("malformed request")
            self._log(exc_to_stderr)
        _write_frame(conn, {"jsonrpc": "2.0", "id": _safe_id(line), "result": env})
```

## Verification

**Commands:**
- `python scripts/check_imports.py` -- expected: `check_imports OK` (listener stdlib-only, pump/host Qt-only in hosts).
- `python -m pytest tests/external -q` -- expected: all pass, including new `test_rpc_listener.py` / `test_rpc_client.py` covering every I/O-matrix row over a real socket.
- `ruff check src scripts tests` and `ruff format --check src scripts tests` -- expected: clean (no T201/style violations).
- `python -c "import ast,sys; [sys.exit('not empty') for p in ('src/freecad_buddy/adapters/__init__.py','src/freecad_buddy/hosts/__init__.py') if __import__('os').path.getsize(p)]"` -- expected: no output (both byte-empty).

**Manual checks (if no CLI):**
- Qt pump (`pump.py`) reviewed against integration-mcp-freecad.md §3.3: `postEvent` from the listener thread, `customEvent` runs `ev.fn()` on the main thread; no widgets/`FreeCADGui` import. Live-GUI execution is deferred to the story-1.10 `gui_smoke` token.

## Auto Run Result

Status: done

### Summary
Implemented the GUI host topology for the MCP↔FreeCAD bridge: an in-FreeCAD NDJSON JSON-RPC listener that marshals every FreeCAD call onto the Qt main thread behind a per-session `hmac.compare_digest` token on a 127.0.0.1 socket, a Qt `postEvent` pump, a deferred-start addon gated on `FreeCAD.GuiUp`, an external RPC client + streamable-HTTP MCP server for `--mode rpc --transport http`, and an addon build script. A first review pass caught a fatal double-marshal deadlock (plus malformed-frame, client-never-raises, concurrency, audit, and suspect-precision gaps); the spec was amended (single marshal layer: listener owns the marshal, dispatches an un-marshaled registry) and the code re-derived. A second pass confirmed all six fixes and applied four low-severity patches.

### Files changed
- `src/freecad_buddy/adapters/rpc_listener.py` — `RpcListener`: NDJSON framing (16 MiB cap), `rpc_hello` handshake (auth-before-version-disclosure), single `marshal.call` per request, per-connection exception isolation, document-suspect tracking, optional `AuditSink`, 0600 discovery file, `start_threaded`/`serve_forever_inline`/`stop`.
- `src/freecad_buddy/adapters/rpc_client.py` — external NDJSON client: newest-live-pid discovery, never-raises `call` with per-call read timeout, channel-error→status mapping, `WORKER_CRASHED {rpc:"unreachable"}` synthesis.
- `src/freecad_buddy/hosts/tool_catalog.py` — shared tool catalog + `build_inline_handlers(...)` producing marshaled (headless) or un-marshaled (listener) handlers from one source.
- `src/freecad_buddy/hosts/headless/entry.py` — `build_registry` now builds from the shared catalog; surface unchanged.
- `src/freecad_buddy/hosts/gui_addon/{__init__,pump,bootstrap,InitGui}.py` — Qt main-thread executor, idempotent `start_bridge`/`stop_bridge` (+ shutdown hook), deferred-start workbench.
- `src/freecad_buddy/hosts/gui_external/{__init__,entry}.py` + `hosts/main.py` — RPC-proxy MCP server over streamable HTTP (serialized shared client, off-loop dispatch); `--mode rpc --transport http` wiring.
- `scripts/build_addon.py` — addon assembler with `FREECAD_BUDDY_SRC` dev shim.
- `tests/external/test_rpc_listener.py`, `tests/external/test_rpc_client.py` — real-socket loopback across the full I/O matrix + loop-1 regressions (double-marshal, malformed-frame isolation, never-raises, suspect precision, listener audit) + channel-error mapping.

### Review findings
- Loop 1 (bad_spec): 6 findings (3 high, 3 medium) — double-marshal deadlock + malformed-frame + never-raises + concurrency + audit + suspect/leak. Spec amended, code re-derived.
- Loop 1 re-review: 4 low patches applied (channel-error mapping, doc-type guard, token-order, port guard); 1 deferred (mesh-verify oracles on the Qt thread → `deferred-work.md`); 6 rejected.

### Verification
- `python scripts/check_imports.py` → `check_imports OK` (listener stdlib-only; Qt confined to `hosts/gui_addon/**`; `adapters/__init__.py` + `hosts/__init__.py` byte-empty).
- `python -m pytest tests/external -q` → `165 passed, 4 warnings` (4 warnings are pre-existing unrelated trimesh RuntimeWarnings).
- `ruff check src scripts tests` → All checks passed; created/changed files `ruff format`-clean.
- Independently re-inspected: `bootstrap.py` builds the un-marshaled registry; the double-marshal regression test fails against the old wiring and passes against the fix.

### Residual risk
- Live-GUI smoke (real FreeCAD GUI, real MCP client) is out of scope by design — proven later by the story-1.10 `gui_smoke` human token. CI proves the transport via real-socket loopback without FreeCAD/Qt.
- Deferred: GUI freeze while mesh-verify oracle legs run on the Qt main thread (bounded; `verify_export_stl/3mf` only; export/verify are already accepted op-duration freezes).
