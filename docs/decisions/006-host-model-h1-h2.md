# 006 — Host Model: H1 Canonical (`import FreeCAD`) with H2 (`FreeCADCmd`) Fallback

## Decision

Headless host model = **H1 canonical** (per AD-2): a single process where the external MCP
server + usecases + `import FreeCAD` as a module all live in the conda env, and every FreeCAD
call is a direct in-proc inline call (no RPC, no listener, no token). Use `InlineExecutor` so
use cases stay mode-agnostic.

**H2** (`FreeCADCmd hosts/headless/run_server.py`) is the FALLBACK host for environments whose
interpreter cannot `import FreeCAD` (AppImage / interpreter mismatch). H2 is the GUI topology
minus Qt: the same RPC listener runs a single-threaded inline serve loop. The research-backed
expectation (research-resolved, `integration-mcp-freecad.md §1`) is that this serve loop IS the
process main thread and `FreeCADCmd` has no Qt loop, so inline dispatch needs no marshal — but
the marshal-free property depends on `FreeCADCmd` runtime behavior and is confirmed at runtime
(see Runtime-confirm), not fabricated here. The external MCP process connects exactly as in GUI
mode (connection file, token, handshake); capability flags report `gui:false, qt_loop:false`.

Same use-case implementations in all topologies (AD-2). Source: `integration-mcp-freecad.md §1`.

## Drives

- Story 1.4 transport/host wiring in `hosts/` — H1 default, H2 fallback host selection
  (`hosts/headless/entry.py` for H1, `hosts/headless/run_server.py` for H2).

## Runtime-confirm

- Can the conda-env interpreter `import FreeCAD` on the **1.0.0 / py3.11** leg (H1 viable)?
- Can the conda-env interpreter `import FreeCAD` on the **1.1.0 / py3.12** leg (H1 viable)?
  (the feedstock `PYTHONPATH`/`.pth` edge — issue #21 — is what would force H2)
- Does `FreeCADCmd hosts/headless/run_server.py` serve inline on the main thread without a Qt
  loop (H2 viable) when `import FreeCAD` is unavailable? Confirm the serve loop runs on the
  process main thread so inline dispatch is genuinely marshal-free (the H2 marshal-free premise).
- To be confirmed on the CI headless legs; record per leg which host (H1 default vs H2 fallback)
  the leg resolves to.

## Superseded in part by 016 (2026-10-03)

The 1.0.0/py3.11 question is retired. On FreeCAD 1.1.3, H1 is viable: the env interpreter imports FreeCAD, and the G3 corrupted-plan replay runs over the H1 stdio host.
