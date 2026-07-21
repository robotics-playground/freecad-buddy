# 005 — MCP SDK: Official `mcp` python-sdk, Pin Deferred

## Decision

Use the OFFICIAL `mcp` python-sdk (the Anthropic/MCP project SDK), NOT PrefectHQ `fastmcp`.
Target MCP spec revision ≥ `2025-06-18` (elicitation support required).

The EXACT version pin is an OPEN Phase-0 gate decision — deliberately deferred until SDK v2
stabilizes, because v2 renames `FastMCP` → `MCPServer` and the import surface will change. No
version number is fabricated here; `pyproject.toml` carries `mcp` unpinned with a comment
pointing to this note. The pin is recorded and closed at the Phase-0 gate.

## Drives

- Story 1.4 MCP surface (`adapters/mcp_server.py`).
- The `mcp` entry in `pyproject.toml` `[project.dependencies]` (placeholder pending this note).

## Runtime-confirm

- SDK v2 stable release available? (unblocks the exact pin decision at the Phase-0 gate)
- Required capabilities present in the chosen version: streamable HTTP transport, stdio
  transport, elicitation, `outputSchema`, resource links.
- Confirm import surface (`MCPServer` vs `FastMCP`) once v2 pin is chosen.
