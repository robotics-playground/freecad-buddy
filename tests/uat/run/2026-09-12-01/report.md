# Run Report — Runbook Smoke + Conformance Gate (TC-99)

**Date:** 2026-09-12
**Operator:** agent-executed, main session
**Scope:** `APPENDIX-B` environment runbook, then the conformance gate (TC-99) only.
The green gate (TC-01..TC-12) was **not** run in this session.

## Build banner

Captured from `query_capabilities` against the live GUI bridge. Every result below is only
interpretable against this banner.

| Field | Value |
| --- | --- |
| FreeCAD (GUI host) | 1.1.1 |
| FreeCAD (H1 headless leg) | **1.1.0** — note the skew from the GUI host |
| `element_map_available` | `true` |
| `serializer` | `exportBinary` |
| `varset_backend` | `varset` |
| `render` | `gui_constructed` |
| `sketcher_available` / `partdesign_available` | `true` / `true` |
| `exec_enabled` | `false` |
| RPC `contract_version` | `1` |
| FreeCAD pid / window | 29764 / 393368, Session 1 |
| MCP proxy pid | 28680 (child of 24468), `pythonw.exe -m freecad_buddy.hosts.main serve --mode rpc --transport http` |
| RPC listener | `127.0.0.1:54604` |

## Part 1 — Runbook smoke (`APPENDIX-B`)

| Step | Result | Note |
| --- | --- | --- |
| 1 — cua-driver daemon | **PASS** | pid 3584, SessionId 1. One checkpoint was defective, see below. |
| 2 — Addon install | **PASS** | Junction `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy` → repo `src\freecad_buddy`; `package.xml` present. |
| 3 — H1 legs | **PASS (after fix)** | H1 imports only with the PYTHONPATH patch. Verify command was wrong, see below. |
| 4 — Launch FreeCAD | **PASS** | Already running; pid 29764, Session 1, title `FreeCAD 1.1.1`. |
| 5 — Proxy auto-spawn | **PASS** | `:8765` LISTENING. `addon.log` records `spawned MCP proxy (pid 24468)`. No manual `serve` was run, so TC-01-01 remains valid. |
| 6 — Tool surface | **PASS** | Live `tools/list` returns **44**, family counts `document_ 7, query_ 8, verify_ 6, export_ 3, sketch_ 8, feature_ 11, preview_ 1`. `debug_exec`, `export_self_read_stl`, `export_self_read_3mf` all absent. Wire set is identical to `tool_specs()`. |
| 7 — Build banner | **PASS** | Recorded above. |

### Two runbook defects found and fixed

Both were faults in the *runbook*, not in the product. Both are now corrected in `APPENDIX-B`.

1. **Step 1 — `Test-Path \\.\pipe\cua-driver` always returns `False`.** PowerShell's provider
   cannot stat a named pipe. The daemon was healthy throughout. Replaced with a real call
   (`cua-driver call list_apps '{}'`), which is the only sound liveness check.
2. **Step 3 — the H1 verify command could never pass.** A bare
   `"$FCB/python.exe" -c "import FreeCAD"` raises `ModuleNotFoundError`; `FreeCAD.pyd` lives in
   `Library/bin` and is not on the default `sys.path`. The env is fine — `run_mcp_e2e.py` applies
   the same PYTHONPATH patch in `_fcb_env`. The verify command now includes the patch and warns
   against "fixing" the env in response to the bare-import failure.

### Environment note recorded for future runs

The H1 leg is FreeCAD **1.1.0** while the GUI host is **1.1.1**. Any comparison of a
version-sensitive value (fingerprint digest, element map) between hosts must record which host
produced it. This skew is now called out in `APPENDIX-B` Step 3.

## Part 2 — Conformance gate (TC-99)

**Expected outcome: every scenario fails. Result: every scenario failed, as documented.**
No scenario passed, so nothing is eligible for promotion into the green gate.

| Scenario | AD | Verdict | Evidence |
| --- | --- | --- | --- |
| TC-99-01 | AD-3 bearer token | **FAIL (expected)** | See below — the most serious finding in the run. |
| TC-99-02 | AD-3 Origin allowlist | **FAIL (expected)** | Foreign `Origin: https://attacker.example` served. `OPTIONS` preflight returns 307 with **no** `Access-Control-*` header. Source grep finds no HTTP `Origin` check — the only hits are `originals`, a `feature_pattern`/`feature_mirror` parameter. |
| TC-99-03 | AD-26 busy refusal | **FAIL (expected, and worse than documented)** | See below — scenario text was corrected. |
| TC-99-04 | AD-25 session workdir | **FAIL (expected)** | `%APPDATA%\FreeCAD\v1-1\freecad-buddy\` holds `addon.log`, `mcp-proxy.log` and 7 `rpc-<pid>.json` files. `Get-ChildItem -Directory` count is **0**. `snap/`, `exports/`, `tmp/`, `audit.log` all ABSENT. `grep -rniE "session_dir\|workdir\|session_root" src/` returns nothing. |
| TC-99-05 | AD-25 snapshot location | **FAIL (expected)** | Snapshots use `tempfile.mkdtemp(prefix="FCB_TMP_snap_")` (`transaction.py:94`, prefix at `:39`), i.e. the process temp directory. |
| TC-99-06 | AD-25 audit log location | **FAIL (expected)** | `freecad-buddy-audit.jsonl` (113,393 bytes) sits in the **repository root** — the cwd-relative default from `adapters/audit_log.py:24`. Its location depends on where the host was started. |
| TC-99-07 | AD-25 start-of-session sweep | **FAIL (expected)** | 9 `FCB_TMP_*` entries are still present in `%TEMP%` from earlier sessions. No sweep exists. |
| TC-99-08 | AD-24 `/healthz` | **FAIL (expected)** | `grep -rn "healthz" src/` returns **zero hits**. The only route is `Mount("/mcp")`; the only liveness signal is a raw TCP connect. |

### TC-99-01 — the HTTP surface is unauthenticated (most serious finding)

Verified live, not inferred. A session opened against `http://127.0.0.1:8765/mcp` carrying
**a deliberately invalid bearer token** and **a foreign `Origin`**:

```
Authorization: Bearer totally-invalid-garbage
Origin: https://attacker.example
```

- CP1 — no auth challenge. Status is `307`, then `400 -32600 Bad Request: Missing session ID`.
  That `-32600` is an **MCP protocol** requirement, not authentication.
- CP2 — the full **44-tool** list was disclosed to a caller that presented no valid credential.
- CP3 — the invalid bearer token was **ignored entirely**; the session initialised normally.
- CP4 — a tool call (`document_list`) **succeeded**. **26 mutating tools were reachable.**
- CP5/CP6 — no middleware and no `Origin` check exist in `hosts/gui_external/entry.py`.

The loopback bind is the only control that ships. Any local process — including a browser page
that can reach the port — has full authority over the live document.

### TC-99-03 — corrected against observed behavior

The scenario originally predicted the second client would **block in the accept backlog**.
Observed behavior is worse: because the accept loop sits inside `_serve_conn` for the life of the
first connection, `sock.listen(1)` fills and Windows **refuses the TCP connect outright** with
`ConnectionRefusedError [WinError 10061]`. A single-client baseline connect to the same port was
refused identically while the addon's own proxy held the listener.

Practical harm, now recorded as CP5: a refused-because-busy connection is **indistinguishable from
a bridge that is not running** — both surface as `ConnectionRefusedError` on the same port, so a
client cannot diagnose why it failed. The scenario text and checkpoints were rewritten to match,
and a CP7 was added asserting the `listen()` backlog depth.

## Suite changes made during this run

| File | Change | Reason |
| --- | --- | --- |
| `APPENDIX-B` Step 1 | Replaced the named-pipe `Test-Path` check with a real `cua-driver` call | The check reports `False` on a healthy daemon |
| `APPENDIX-B` Step 3 | H1 verify command now includes the PYTHONPATH patch; added the 1.1.0/1.1.1 skew note | The bare import can never succeed |
| `TC-99-01` | CP1 rewritten to assert the observed `307`/`400 -32600`; steps now require a full unauthenticated MCP session to prove disclosure | The original CP2 would have failed for the wrong reason |
| `TC-99-03` | Scenario, steps and checkpoints rewritten for connection refusal; CP5 reframed; CP7 added | Shipped behavior is more severe than documented |

## What was not run

- **The green gate (TC-01..TC-12), 217 scenarios.** Not attempted in this session.
- Conditional-skip scenarios remain blocked as the suite predicted: this build reports
  `element_map_available: true` and a single `exportBinary` serializer, so TC-05-14 (cross-tag
  fingerprint comparison) and TC-05-18 (TNP `UNSUPPORTED`) cannot be exercised without a second
  FreeCAD build.

## Recommended follow-up

1. **Treat TC-99-01 as a security defect, not a documentation gap.** The unauthenticated
   `:8765` surface reaches 26 mutating tools. AD-3 already specifies the bearer token and the
   `Origin` allowlist; the code does not implement either.
2. Raise the `listen()` backlog and add an explicit busy refusal so a second client can tell
   "busy" from "not running" (TC-99-03 CP5/CP7).
3. Run the green gate next. Expect a mix of real defects and test-authoring bugs on a suite that
   has never executed; triage before cleanup, per the no-auto-cleanup rule.
