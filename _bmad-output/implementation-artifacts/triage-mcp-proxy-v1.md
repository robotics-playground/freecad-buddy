# MCP cache proxy: triage, verifier round 1

Base: uncommitted work on `feat/mcp-cache-proxy`. Verifier report: `verify-mcp-proxy.md` (FAIL, 1 high, 1 medium, 1 low; evidence `tests/uat/run/2026-11-18-mcp-proxy-verify/`). Leader note: a pytest of `test_mcp_cache_proxy.py` started 14:03 by the builder's session was still running at 16:25 (hung for over 2 hours; the leader killed it). It is likely the same hang as D1.

| Id | Severity | Required fix | Proof required |
| --- | --- | --- | --- |
| D1 | high | `mcp_cache_proxy.py:259`, `:161-163`: a `freecad-buddy-docker` (HTTP) call never answers when the upstream connection ends after the request is sent (SDK 1.28.1 swallows the SSE stream end). Also hangs: port closed within 5 s of last use (6/6), upstream crash with slow calls in flight (4/4). Every call must answer: race the request against the end of the connection owner task, and detect a dead HTTP upstream while a call is in flight (for example a periodic cheap probe of the port or `/healthz`, or a ping on a separate session). A call whose connection ended after the send returns the "outcome unknown" error, never a resend. Do not add a total call timeout that would cut a long legitimate FreeCAD call | Tests (HTTP and stdio): connection dies after send; port closes right after a call; crash with 3 slow calls in flight. Each answers within about 10 s; tool execution count stays 1. The tests must hang or fail on the current code (show it). Live: `fcb-freecad stop` then an immediate `query_capabilities` answers with the error |
| D2 | medium | `:366-379`, `:327`: the refresh loop must never die: catch and log every error and continue. Cache writes use a unique temp file per write in the same folder, then an atomic replace | Test: an error inside one refresh cycle; the next cycle still runs. Test: concurrent writes give 0 errors |
| D3 | low | `:319-323`: a cache file that is valid JSON but not a tool list is treated as no cache (logged), not an error on `tools/list` | Test |
| T1 | — | Mutant M6 (no reconnect lock) survives the tests; mutant M8 (no liveness ping) survives. Add tests that kill both | Each mutant red |
| H1 | — | Every test has a bounded runtime (pytest timeout per test or `anyio.fail_after`), so a hang fails the test instead of blocking the suite | Show a hang mutant fails within the bound |

## After the fixes

The leader commits. The same verifier re-runs D1-D3, T1, H1 and the live stop-then-call case.
