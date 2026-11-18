# Re-run at 0eae6f8

Report: `_bmad-output/implementation-artifacts/verify-mcp-proxy.md`, section "Re-run at 0eae6f8".
Verdict PASS.

| File | Shows |
| --- | --- |
| `logs/verify-crash-long-parallel.log` | D1 cases answer, count 1; 60 s call not cut; probe counts |
| `logs/verify-c3-cache-concurrent-loop-retire.log` | D2, D3, retire, closed-port poll |
| `logs/mutants.log` | M0-M13 on scratch copies; M9 = hang mutant fails at the 30 s bound |
| `logs/live.log` | Live: down, up, P5 long call + `/healthz` samples, P3b stop then call, P6, P7 FreeCAD kill, P8 proxy kill |
| `logs/gate-*.txt` | Gates |
| `scripts/` | Probe scripts, fake, mutant runner, live drivers |

`kill_proxy_mid_call.py` logs "a 40 s script_exec"; the script sleeps 25 s (the label was not updated).
The driver's client close prints a `RuntimeError` traceback from its own `AsyncExitStack` after all calls.
