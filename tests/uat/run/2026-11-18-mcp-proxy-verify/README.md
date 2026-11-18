# MCP cache proxy verification, 2026-11-18

Report: `_bmad-output/implementation-artifacts/verify-mcp-proxy.md`. Verdict FAIL (D1 high).

| File | Shows |
| --- | --- |
| `scripts/fake_counting_upstream.py` | Fake MCP upstream (stdio or HTTP) that counts each tool run, then crashes, hangs or answers |
| `scripts/verify_proxy.py` | Probes against the unchanged proxy: crash after send, hang, parallel, retire, closed port, cache, refresh loop, concurrent writers |
| `scripts/debug_down.py` | State dump for a call on a dead HTTP transport (owner task done, request still pending) |
| `scripts/mutants.py` | Copies the proxy and the builder tests to scratch, applies M0-M8, runs the tests |
| `scripts/live_driver.py` | Starts both proxies with the `.mcp.json` command (cwd `C:\`) through the container lifecycle |
| `scripts/raw_stdout.py` | Raw stdout check: every line is JSON-RPC |
| `logs/verify-crash.log` | Condition 1: count stays 1; stdio answers, HTTP does not answer |
| `logs/verify-c3-cache-concurrent-hang-loop-parallel-retire.log` | Conditions 2 and 3, hang, retire, cache, D2 |
| `logs/mutants.log` | Mutant results |
| `logs/live.log` | Live run: down, up, FreeCAD stop/start (P3b hang), fresh cache with `list_changed` |
| `logs/proxy-*.stderr.log` | Proxy stderr during the live run |
| `logs/raw-stdout.log` | Stdout cleanliness |
| `logs/gate-*.txt` | Gate results |

The driver's own client close prints a `RuntimeError` traceback (cancel scope in a different task).
It comes from the driver's `AsyncExitStack`, after all calls finished, not from the proxy.
