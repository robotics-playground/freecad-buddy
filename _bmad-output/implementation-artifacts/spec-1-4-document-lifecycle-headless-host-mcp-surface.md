---
title: 'Story 1.4 — Document Lifecycle, Headless Host & First MCP Surface'
type: 'feature'
created: '2026-07-21'
status: 'done'
baseline_revision: 'dfba1204f6d26ec44817dd134a48572c1150ccb9'
final_revision: 'd4dc223'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/docs/decisions/005-mcp-sdk-pin.md'
  - '{project-root}/docs/decisions/006-host-model-h1-h2.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** The bridge has contracts (Story 1.2) and a gate (Story 1.3) but no live surface: no MCP server, no document-targeting tools, no runtime capability probes, no audit sink. Every later tool (queries, verify, exports, screenshots) targets a document by handle and needs this foundation first (AD-20).

**Approach:** Land the H1 headless path — a single conda-env process that imports FreeCAD inline (no RPC), serves the official `mcp` SDK over stdio, and exposes the Phase-0 `document_*` set (create/open/save/close/list/recompute) + `query_capabilities`. Documents are targeted only by explicit opaque handle from a session registry (single-writer serialized). Turn the `usecases/shim.py` conservative stubs into real runtime capability probes. Wire an append-only JSON-lines audit sink (`fcb.audit-record/1`) for every lifecycle mutation and every `debug_exec` call; `debug_exec` is registered only when `FREECAD_BUDDY_ALLOW_EXEC=1`.

## Boundaries & Constraints

**Always:**
- Ring discipline (AD-1): tool impls + shim in `usecases/` (stdlib + FreeCAD App API only); registry/marshal/mcp-server/audit-sink in `adapters/`; host entry in `hosts/`; the `mcp` SDK import lives ONLY in `adapters/mcp_server.py` + `hosts/` (external uv process — AD-12). `check_imports.py` must stay green.
- Every tool returns the contracts-owned `ResultEnvelope` (`fcb.result-envelope/1`); status from the closed set only. Phase-0 use-case outcomes emit `OK | SPEC_FAILED | RECOMPUTE_ERROR | INVALID_INPUT`; `dispatch` is the single error boundary mapping exceptions onto that set.
- Explicit handle only (AD-20): a call that omits `doc` (except create/open/list) or uses a stale/unknown handle → `INVALID_INPUT`. `ActiveDocument` is never an implicit target. Documents open/close only through these usecases.
- Single-writer (AD-20): mutating calls on a document serialize. A global in-flight lock is acceptable for Phase 0 (per-doc queue is a later optimization).
- Capability reporting is runtime probes only, never version-string comparison (AD-11). Shim probes cached with `lru_cache`.
- stdio transport: stderr-only logging; `print()` banned in `src/` (ruff T201). Audit log is a separate append-only file, never stdout/stderr.
- `debug_exec` off by default: absent from `tools/list` unless `FREECAD_BUDDY_ALLOW_EXEC` is exactly `"1"` (read once at startup into an immutable capability record; any other value is off). Every `debug_exec` and every lifecycle mutation appends an `fcb.audit-record/1` line before and after.
- In-FreeCAD code (usecases/shim, document ops) stays third-party-free; those behaviors are tested under FreeCADCmd in `tests/infc/` with stdlib `unittest`. The MCP-surface/registry/audit behaviors are tested in `tests/external/` under pytest.

**Block If:**
- On a CI headless leg the conda interpreter cannot `import FreeCAD` (would force the H2/`FreeCADCmd` RPC fallback, whose RPC listener + token + handshake transport is owned by Story 1.8). HALT — H2's transport is out of scope here.
- The pinned `mcp` SDK's public API for stdio serving + `tools/list` with `inputSchema`/`outputSchema` cannot be resolved from the installed package (decision 005 pin still open in a way that blocks a working server). HALT with the resolved import surface findings.

**Never:**
- No H2 RPC listener / token / connection-file / handshake implementation (Story 1.8 owns the RPC transport; here `--mode rpc` returns a clear "not available until Story 1.8" error).
- No GUI addon, no marshal Qt pump, no screenshots/render (`query_capabilities` reports `render: "none"`).
- No Phase-2 `document_undo` / `document_object_delete`, no preview/confirm gate, no mutation AD-5 snapshot bracket for lifecycle ops (they are audit + serialize only, exempt per mcp-tools §1.4).
- No new wire types — reuse `contracts/` (`ResultEnvelope`, `AuditRecord`, `DocHandle`, `TerminalStatus`, `ErrorDetail`). No committed fingerprint hashes.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| create→save→close | `document_create{label}` then save/close with returned `doc` | Each `ResultEnvelope status=OK`, `structured_content.doc` echoes the handle; audit line per mutation | — |
| stale/unknown handle | mutating call with a `doc` not in the registry | `ResultEnvelope status=INVALID_INPUT`, ErrorDetail message | fail-closed |
| missing handle | mutating call (save/close/recompute) omitting `doc` | `INVALID_INPUT` | fail-closed |
| tools/list, exec off | `FREECAD_BUDDY_ALLOW_EXEC` unset | list = 6 `document_*` + `query_capabilities`, each with inputSchema+outputSchema+docstring; `debug_exec` absent | — |
| tools/list, exec on | `FREECAD_BUDDY_ALLOW_EXEC=1` | `debug_exec` present and callable; each call writes pre+post audit lines | — |
| query_capabilities | called on either CI leg | reports freecad_version, element_map_available, serializer tag, varset_backend, render="none", exec_enabled — all via probes | — |
| concurrent mutations | two mutating calls on one doc | serialized (single-writer) | — |
| H1 unavailable | interpreter cannot `import FreeCAD` | host reports the condition and refuses (H2 transport deferred) | Block If |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/shim.py` -- REPLACE conservative stubs with real runtime probes: `export_binary_available()`/serializer detection, `element_map_available()`, `varset_available()` + backend name, add `freecad_version() -> str` and `capability_banner() -> dict`. FreeCAD imported lazily inside functions; `lru_cache` the boolean probes.
- `src/freecad_buddy/usecases/documents.py` -- NEW. `DocumentRegistry` (mint opaque `fcb-doc:<token>` handles, map handle↔FreeCAD doc, transient flag, single-writer lock) + the six lifecycle ops (`document_create/open/save/close/list/recompute`) returning `ResultEnvelope`. Raises typed validation errors for unknown/missing handles.
- `src/freecad_buddy/usecases/queries.py` -- NEW. `query_capabilities()` builds the capability payload from shim probes; returns `ResultEnvelope`.
- `src/freecad_buddy/usecases/debug_exec.py` -- NEW. Operator `debug_exec(doc, code)` handler (`stdout`/`value_repr`/`fingerprint_after`); bypasses AD-5 typing by definition; audited by the caller boundary.
- `src/freecad_buddy/adapters/marshal.py` -- REPLACE stub: `Executor` Protocol, `InlineExecutor` (`submit(fn)=fn()`), `Marshal.call(fn, timeout_s)`, `MarshalTimeout`. Stdlib only.
- `src/freecad_buddy/adapters/rpc_dispatch.py` -- NEW. `RpcMethod` dataclass + `MethodRegistry.register/dispatch`; `dispatch` is the single error boundary mapping use-case exceptions onto the closed status set, attaching machine detail (class/message/truncated traceback → stderr).
- `src/freecad_buddy/adapters/audit_log.py` -- NEW. `AuditSink` writing `fcb.audit-record/1` JSON-lines append-only (`"a"`), one `event:"mutation"` line pre + post per lifecycle op, `event:"exec"` for `debug_exec`. Location: session workdir, operator-configurable; never truncates/rotates/reads.
- `src/freecad_buddy/adapters/mcp_server.py` -- NEW (imports the `mcp` SDK — external only). Registers each registry method as an MCP tool with JSON `inputSchema`+`outputSchema`+docstring, underscore names; gates `debug_exec` on the startup capability record; wires stderr-only logging; serves over the requested transport (stdio for Phase 0).
- `src/freecad_buddy/hosts/headless/__init__.py`, `entry.py` -- NEW (H1). Path setup, verify `import FreeCAD` (else Block-If condition), build `MethodRegistry` → `Marshal(InlineExecutor())` → `mcp_server`, serve stdio, stderr logging.
- `src/freecad_buddy/hosts/main.py` -- WIRE `serve --transport stdio --mode inline` to `hosts.headless.entry`; `--mode rpc` → clear "H2 RPC transport not available until Story 1.8" error (exit non-zero).
- `tests/external/test_mcp_surface.py` -- NEW pytest: tools/list = 6 `document_*` + `query_capabilities`, each has inputSchema+outputSchema+docstring, underscore names; `debug_exec` absent when flag unset, present when `=1`; dispatch maps a raised validation error → `INVALID_INPUT` envelope; audit sink appends valid `fcb.audit-record/1` lines (schema-checked) for a lifecycle mutation and an exec call.
- `tests/infc/test_document_lifecycle.py` -- NEW stdlib unittest under FreeCADCmd: real `DocumentRegistry` create/save/close round-trip; unknown/missing handle → `INVALID_INPUT`; `query_capabilities` returns freecad_version + element_map + serializer + varset backend from live probes; `ActiveDocument` never targeted.
- `pyproject.toml` -- resolve/confirm the `mcp` pin against decision 005 (record the closed pin + import surface); no in-FreeCAD dep additions.
- `.github/workflows/ci.yml` -- run the new external + infc tests via existing discovery; ensure `mcp` is installed in the arch-checks/external envs.
- `docs/decisions/005-mcp-sdk-official-pin-deferred.md` -- UPDATE: record the pin closed at this Phase-0 gate + the confirmed import surface (`FastMCP` vs `MCPServer`), per decision's own "closed at the Phase-0 gate" clause.

## Tasks & Acceptance

**Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)**
  - Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md`.
  - Re-read `integration-mcp-freecad.md` §1, §4.1 (H1), §4.3 (capability flags), §5 (shim); `mcp-tools-design.md` §1.1–1.4, §2 (document_ inventory), §3.1 (document_create), §5 (debug_exec); `security-and-service-design.md` §1–§3; `component-design.md` (ring placement).
  - Re-read `project-context.md` "Architecture Ring & Import Rules", "FreeCAD API Traps" (ActiveDocument banned, Name vs Label, transactions), "Security Rules", "Wire & Schema Rules".
  - Load `typescript-clean-code` (naming/commenting discipline, applied to Python).
  - Read decisions `005` (MCP SDK) + `006` (H1/H2 host model).

**Execution:**
- [x] `pyproject.toml` + `docs/decisions/005-*.md` -- resolve the `mcp` pin against the installed SDK, confirm the stdio-serve + tools/list import surface, record the closed pin in decision 005. -- unblock a working MCP server (decision 005 Phase-0-gate clause).
- [x] `src/freecad_buddy/usecases/shim.py` -- real runtime probes (element_map, serializer, varset backend) + `freecad_version()` + `capability_banner()`; lazy FreeCAD import, `lru_cache`. -- AC4 runtime capability reporting (AD-11).
- [x] `src/freecad_buddy/usecases/documents.py` -- `DocumentRegistry` + six lifecycle ops; opaque handles; single-writer lock; explicit-handle enforcement. -- AC2, AC3 (AD-20).
- [x] `src/freecad_buddy/usecases/queries.py` -- `query_capabilities()` from shim probes. -- AC4.
- [x] `src/freecad_buddy/usecases/debug_exec.py` -- operator `debug_exec` handler. -- AC5.
- [x] `src/freecad_buddy/adapters/marshal.py` -- `InlineExecutor`/`Marshal`/`MarshalTimeout`/`Executor`. -- mode-agnostic execution (AD-2).
- [x] `src/freecad_buddy/adapters/rpc_dispatch.py` -- `RpcMethod` + `MethodRegistry`; dispatch error boundary → closed status set. -- AC2 error mapping (AD-17).
- [x] `src/freecad_buddy/adapters/audit_log.py` -- append-only `fcb.audit-record/1` JSON-lines sink; pre+post lifecycle mutation lines + exec lines. -- AC5 audit (AD-17).
- [x] `src/freecad_buddy/adapters/mcp_server.py` -- register tools with inputSchema+outputSchema+docstring; gate `debug_exec` on startup flag; stderr logging; stdio serve. -- AC1, AC5 (AD-3, AD-4).
- [x] `src/freecad_buddy/hosts/headless/entry.py` (+ `__init__.py`) -- H1 wiring: verify `import FreeCAD` (else Block-If), build registry→marshal→server, serve stdio. -- AC1 (AD-2).
- [x] `src/freecad_buddy/hosts/main.py` -- wire `serve --transport stdio --mode inline` → H1 entry; `--mode rpc` → deferred-to-1.8 error. -- entry command (AC1).
- [x] `tests/external/test_mcp_surface.py` -- tools/list contents + schemas + docstrings; debug_exec absent/present by flag; dispatch→INVALID_INPUT; audit lines schema-valid. -- AC1, AC2, AC5 (non-tautological: real registry + real exit behavior).
- [x] `tests/infc/test_document_lifecycle.py` -- FreeCADCmd lifecycle round-trip; stale/missing handle→INVALID_INPUT; live `query_capabilities` probes. -- AC2, AC3, AC4.
- [x] `.github/workflows/ci.yml` -- new suites run via existing discovery; `mcp` available in external/arch-checks envs. -- CI coverage.

**Final Task: Quality Checks**
- [x] `uv run python scripts/check_imports.py` -- rings clean (mcp import only in adapters/mcp_server + hosts).
- [x] `uv run ruff check .` -- clean (T201 print-ban honored).
- [x] `uv run pytest tests/external -q` -- all green.
- [x] `"FreeCADCmd" tests/run_tests.py` -- infc lifecycle + capability probes green (local FreeCAD 1.1).

**Acceptance Criteria:**
- Given `uv run freecad-buddy serve --transport stdio --mode inline`, when an MCP client runs `tools/list`, then the six `document_*` tools + `query_capabilities` are listed, each with JSON inputSchema + outputSchema + docstring, underscore names, all logging on stderr.
- Given `document_create` then `document_save`/`document_close` with the returned handle, when called, then each returns a `fcb.result-envelope/1` echoing the handle; a call omitting `doc` or using a stale handle returns `INVALID_INPUT`; `ActiveDocument` is never targeted implicitly.
- Given two concurrent mutating lifecycle calls on one document, when dispatched, then they serialize (single-writer).
- Given the version shim, when `query_capabilities` runs on both CI legs, then it reports FreeCAD version, element_map_available, serializer tag, varset backend, render="none", exec_enabled — all via runtime probes.
- Given `FREECAD_BUDDY_ALLOW_EXEC` unset, when `tools/list` runs, then `debug_exec` is absent; set to `1` → present and every call writes append-only `fcb.audit-record/1` lines; the audit sink records `fcb.audit-record/1` JSON-lines for all lifecycle mutations.

## Spec Change Log

## Review Triage Log

### 2026-07-22 — Review pass (follow-up 2)
- intent_gap: 0
- bad_spec: 0
- patch: 11: (high 1, medium 3, low 7)
- defer: 3
- reject: 6
- addressed_findings:
  - `[high]` `[patch]` `_call_tool` returned the raw envelope `dict`, so the SDK normalized every result to `CallToolResult(isError=False)` — an `INVALID_INPUT`/`RECOMPUTE_ERROR`/`TIMEOUT` envelope reached the client marked as a successful tool call. Now wraps the envelope via `_to_call_result`, setting `isError = status != "OK"` and returning an explicit `CallToolResult` (structuredContent + JSON text content). Added `test_call_tool_ok_status_is_not_error` / `test_call_tool_non_ok_status_sets_is_error` driving the real SDK call-tool handler.
  - `[medium]` `[patch]` `document_open` on an already-open path minted a second handle for the same FreeCAD document; closing one handle stranded the other on a closed object. Now reuses the existing handle when the opened document is already tracked, and `document_close` releases every handle bound to the document. Added `test_reopen_same_path_reuses_handle`.
  - `[medium]` `[patch]` `FreeCAD.newDocument`/`openDocument` raising on a bad label/path escaped as `RECOMPUTE_ERROR(unexpected)`; a bad label/path is caller-side invalid input. Both are now wrapped to raise `ValidationError` → `INVALID_INPUT`.
  - `[medium]` `[patch]` `query_capabilities` reported `exec_enabled = caps.allow_exec`, so in service mode (exec unregistered) the banner claimed exec was enabled while the tool was unreachable. Now reports `exec_registered(caps)`.
  - `[low]` `[patch]` module-load of `_RESULT_ENVELOPE_SCHEMA` had no guard; a missing/malformed schema file failed the whole host import with a raw `FileNotFoundError`/`JSONDecodeError`. Now raises a clear `RuntimeError` naming the file.
  - `[low]` `[patch]` `serve_stdio` was run via a bare `asyncio.run` in `entry.run`; a transport error or `KeyboardInterrupt` propagated as an unhandled traceback. Now caught: interrupt → clean exit 0, other errors → logged, exit 1.
  - `[low]` `[patch]` `debug_exec` distinguished a bound `result` via `value is not None`, conflating an explicit `result=None` with an unset one. Now uses an `_UNSET` sentinel. Also captured stdout is now preserved on the exception message when the exec body raises.
  - `[low]` `[patch]` `debug_exec` reached into `registry._lock`/`registry._resolve` (private). Added a public `DocumentRegistry.with_document(doc, fn)` that resolves and runs under the lock; `debug_exec` uses it, decoupling from the private lock/resolver.
  - `[low]` `[patch]` `RpcMethod.output_schema` was a dead field (never read; `_tool_for` uses the shared envelope schema). Removed it.
  - `[low]` `[patch]` `hosts/main.py` forwarded the full `argv` (including the `serve` token) to `entry.run`, which ignores it; now calls `run()`.
  - `[low]` `[patch]` docstrings and comments across the changed `src/` and `tests/` files carried requirement-traceability provenance (AD/NFR ids, `mcp-tools §…`, ring/story back-references) forbidden by CLAUDE.md §0.1. Stripped to plain what-it-does code documentation.

### 2026-07-22 — Review pass (follow-up)
- intent_gap: 0
- bad_spec: 0
- patch: 4: (high 1, medium 1, low 2)
- defer: 1
- reject: 4
- addressed_findings:
  - `[high]` `[patch]` `document_recompute` keyed per-object error detection on `"Error" in obj.State`, but FreeCAD emits `"Invalid"` for an errored object (`DocumentObjectPyImp::getState` → `isError()`→`"Invalid"`; `"Error"` is never produced). The AC "report per-object error states" was silently under-reporting every recompute failure. Changed the marker to `"Invalid"` and bound `state` once (verified against `docs/references/FreeCAD/src/App/DocumentObjectPyImp.cpp`).
  - `[medium]` `[patch]` a marshal timeout was mapped to `RECOMPUTE_ERROR` (`unexpected=True`) via the generic boundary, contradicting integration-mcp-freecad §7 which mandates `status:"TIMEOUT"` with `detail.data.marshal_timeout`/`maybe_still_running` (document-suspect session). Added a `MarshalTimeout` branch in `dispatch` mapping to the closed-set `TIMEOUT` with those detail fields (adapters→adapters import; ring stays green). Latent under `InlineExecutor` but the dispatch boundary this story owns now matches the design for the GUI/RPC hosts.
  - `[medium]` `[patch]` `debug_exec` resolved the handle and ran arbitrary mutating `exec` OUTSIDE the `DocumentRegistry` single-writer lock (AD-20), so an exec body could interleave with concurrent `document_*` ops. Now wraps resolve+exec in `registry._lock`.
  - `[low]` `[patch]` tool input schemas lacked `additionalProperties: false`, so an unknown client key passed SDK validation then hit `handler(**params)` → raw `TypeError` → `INVALID_INPUT` with a Python-repr message. Added `additionalProperties: false` to all Phase-0 tool schemas so the SDK rejects unknown keys with a clean schema error before dispatch.

### 2026-07-21 — Review pass (iteration 1)
- intent_gap: 0
- bad_spec: 0
- patch: 9: (medium 3, low 6)
- defer: 5
- reject: 14
- addressed_findings:
  - `[medium]` `[patch]` `debug_exec` was registered into the `MethodRegistry` unconditionally (gate lived only in the presenting adapter) — a direct `registry.dispatch("debug_exec", …)` could reach the live exec path. Moved the gate to registration in `build_registry` (`exec_registered(caps)`), so the executable handler never enters the registry when disabled (AD-4 "unregistered when off"); adapter guards kept as defense in depth.
  - `[medium]` `[patch]` audit `before`/`after` were called OUTSIDE the dispatch error boundary in `_call_tool`; an audit I/O failure (disk full / permission) or a non-JSON-serializable arg in `_digest` would escape as a raw exception, breaking AD-17 "every tool returns a ResultEnvelope". Wrapped audit writes in `_audit_safe` (log to stderr, never break the call) and made `_digest` tolerant (`default=repr`).
  - `[low]` `[patch]` a denied `debug_exec` attempt (flag off) returned without any audit line (AD-4 "every call audited"). Now audits the denial (`event:"exec"`, INVALID_INPUT) via an explicit `_denied_exec_envelope` (dropped the `__debug_exec_disabled__` fake-method sentinel that leaked an internal name).
  - `[low]` `[patch]` `document_create`/`document_open` leaked an orphan FreeCAD document if post-create bookkeeping raised after `newDocument`/`openDocument` (unreachable via the registry, only via banned `ActiveDocument`). Now close the doc on partial failure before re-raising.
  - `[low]` `[patch]` `document_recompute` error collection re-fetched each object via `document.getObject(obj.Name).State` (redundant; `.State` on a `None` return raises). Simplified to read `obj.State` directly with a None-safe guard.
  - `[low]` `[patch]` `document_save` without a path on a transient (never-saved) doc raised a generic FreeCAD exception → mislabeled `RECOMPUTE_ERROR`. Now raises `ValidationError` → `INVALID_INPUT` with a clear message.
  - `[low]` `[patch]` `document_create(path=…)` set `transient=False` but never wrote the file (the `transient` flag lied vs mcp-tools §3.1 "optional .FCStd save target"). Now `saveAs(path)` when a path is given.
  - `[low]` `[patch]` `_RESULT_ENVELOPE_SCHEMA` was hand-duplicated in the adapter, drifting from the contracts-owned closed status set (AD-17). Now loads `contracts/jsonschema/result-envelope.schema.json`.
  - `[low]` `[patch]` audit-log default path was CWD-relative with no startup visibility. Now resolves to an absolute path and logs it at startup (env override kept).

## Design Notes

- **`doc` on the wire is an opaque string; `contracts.DocHandle` is the richer internal shape.** mcp-tools §3.1 defines the tool `doc` field as `{"type":"string"}` (e.g. `fcb-doc:7f3a…`), while `contracts/document.py::DocHandle` is a TypedDict `{handle, name?, transient?}`. Resolve: the wire/tool `structured_content.doc` echoes the opaque string; `document_list` returns the richer per-doc objects (`doc`, `name`, `label`, `transient`). The registry maps opaque-string ↔ FreeCAD `App.Document`. Do not put the FreeCAD Name into the opaque handle (script against immutable `Name` internally; the handle is a session token).
- **H1 only; H2 transport deferred to Story 1.8.** Decision 006 makes H1 canonical (no RPC, no listener, no token, `InlineExecutor`). H2's RPC listener + per-session token + handshake + connection-file transport is the same machinery Story 1.8 builds for the GUI host; landing it here would duplicate/pre-empt 1.8. So `--mode inline` (H1) is fully built; `--mode rpc` returns a clear deferral error. On the CI legs FreeCAD imports (local dev already runs FreeCADCmd + FreeCAD 1.1), so H1 resolves and AC1 ("H1 host, or H2 fallback per spike 1.1") is met by H1. If a leg cannot `import FreeCAD`, that is the Block-If.
- **Lifecycle ops are audit + serialize only, not AD-5 mutations.** Per mcp-tools §1.4, `document_save/close/recompute` change state but carry no geometric intent — they are exempt from the AD-5 snapshot/verify bracket and the preview/confirm gate. They still audit-log and serialize under the single-writer rule. The full `run_mutation()` bracket lands with the geometry mutations (Story 1.6+), not here.
- **Shim probes must be real now (AC4).** The current shim returns conservative `False`; AC4 requires runtime-probed values on both legs. Turn `element_map_available`, serializer detection, and the varset backend into genuine `hasattr`/probe-shape checks (never version strings), and add `freecad_version()`/`capability_banner()`. These run in-FreeCAD, so they are validated in `tests/infc` under FreeCADCmd.
- **Audit record shape:** reuse `contracts.AuditRecord` verbatim — `event ∈ {mutation, exec, ...}`, `actor`, `ts`, `tool`, `doc`, `params_digest`, `fingerprint_before/after`, `verify_verdict`. `debug_exec` → `event:"exec"`; lifecycle ops → `event:"mutation"`, one line before and one after each op. Validate lines against `contracts/jsonschema/audit-record.schema.json` in the external test.

## Verification

**Commands:**
- `uv run python scripts/check_imports.py` -- expected: exit 0 (mcp import confined to adapters/mcp_server + hosts).
- `uv run ruff check .` -- expected: clean.
- `uv run pytest tests/external -q` -- expected: all pass (mcp surface + prior suites).
- `"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" tests/run_tests.py` -- expected: infc lifecycle + capability probes green.
- `uv run freecad-buddy serve --transport stdio --mode inline` -- expected: starts an stdio MCP server (manual/smoke); `--mode rpc` exits non-zero with the Story-1.8 deferral message.

**Manual checks:**
- `tools/list` over the running stdio server shows exactly the 6 `document_*` + `query_capabilities` (no `debug_exec`) with flag unset; `debug_exec` appears with `FREECAD_BUDDY_ALLOW_EXEC=1`.
- The audit file grows by append-only `fcb.audit-record/1` lines across a create/save/close sequence and is never written to stdout/stderr.



## Auto Run Result

Status: done (follow-up review pass 2)

**Summary:** Independent follow-up review of the already-landed Story 1.4 surface. Two adversarial reviewers (general + edge-case) ran against the full diff since the baseline. No intent gaps and no spec deviations were found; 11 implementation-level patches were applied and 3 new deferrals were logged. The headline fix corrects the MCP protocol `isError` flag — error-status envelopes were previously delivered to clients as successful tool calls.

**Files changed (this pass):**
- `src/freecad_buddy/adapters/mcp_server.py` — wrap results as `CallToolResult` with `isError` from status; guard schema load; strip provenance from docs.
- `src/freecad_buddy/usecases/documents.py` — reuse handle on re-open of an already-open path; release all aliases on close; map bad label/path to `INVALID_INPUT`; add public `with_document`; strip provenance.
- `src/freecad_buddy/usecases/debug_exec.py` — use `with_document` (drop private-lock access); `_UNSET` sentinel for `result`; preserve stdout on exec error; strip provenance.
- `src/freecad_buddy/usecases/shim.py` — guard probe bodies (`makeBox`/`newDocument`) against raising; strip provenance.
- `src/freecad_buddy/usecases/queries.py` — strip provenance.
- `src/freecad_buddy/adapters/rpc_dispatch.py` — remove dead `RpcMethod.output_schema`; strip provenance.
- `src/freecad_buddy/adapters/marshal.py`, `adapters/audit_log.py` — strip provenance.
- `src/freecad_buddy/hosts/headless/entry.py` — report `exec_registered(caps)` in the banner; guard `asyncio.run`; strip provenance.
- `src/freecad_buddy/hosts/main.py` — call `run()` without forwarding the parsed argv; strip provenance.
- `tests/external/test_mcp_surface.py` — add SDK call-tool `isError` seam tests; strip provenance.
- `tests/infc/test_document_lifecycle.py` — add re-open handle-dedup test; strip provenance.
- `_bmad-output/implementation-artifacts/deferred-work.md` — 3 new deferrals (inline-exec no effective timeout; recompute non-`Invalid` under-report; audit fingerprints/after-payload).

**Review findings breakdown:** 11 patches applied (1 high, 3 medium, 7 low), 3 items deferred, 6 rejected as noise. No bad_spec loopback; no intent gap.

**Verification performed:**
- `ruff check src/ tests/` — clean.
- `ruff format` (changed files only) — applied.
- `python scripts/check_imports.py` — `check_imports OK` (ring discipline intact; `mcp` still confined to `adapters/mcp_server` + `hosts/`).
- `pytest tests/external -q` — 109 passed (including the new `isError` seam tests).
- `tests/infc/` (FreeCADCmd) — NOT run locally (no FreeCADCmd on this machine); relies on the CI 1.0.x/1.1.x legs. The new `test_reopen_same_path_reuses_handle` and the existing lifecycle/probe tests execute there.

**Residual risks:**
- The in-FreeCAD suite (incl. the new re-open dedup test) is unverified locally and must pass on the CI FreeCAD legs.
- Three logged deferrals remain open (inline-exec unbounded runtime; recompute under-report for non-`Invalid` states; audit fingerprint/after-payload emptiness) — all gated on later stories (1.6/1.8).
