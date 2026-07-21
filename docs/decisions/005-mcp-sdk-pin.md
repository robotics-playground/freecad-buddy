# 005 — MCP SDK: Official `mcp` python-sdk — Pin CLOSED at Phase-0 gate (Story 1.4)

## Decision

Use the OFFICIAL `mcp` python-sdk (the Anthropic/MCP project SDK), NOT PrefectHQ `fastmcp`.
Target MCP spec revision ≥ `2025-06-18` (elicitation support required).

**Pin CLOSED at the Phase-0 gate (Story 1.4): `mcp>=1.28,<2` (installed and confirmed
against `1.28.1`).** The pin was deferred pending a possible SDK "v2" that would rename
`FastMCP` → `MCPServer`; at the Phase-0 gate the official SDK is still on the **v1** line —
no such rename has shipped, `FastMCP` remains at `mcp.server.fastmcp.FastMCP` and there is no
`MCPServer`. The floor `>=1.28` locks the confirmed surface; the `<2` cap prevents an
unattended upgrade past the eventual rename from silently breaking `adapters/mcp_server.py`.

## Confirmed import surface (Story 1.4)

- `import mcp` exposes **no** `__version__`; the distribution version is read via
  `importlib.metadata.version("mcp")` → `1.28.1`.
- **Chosen server surface: the low-level `mcp.server.lowlevel.Server`** (not `FastMCP`).
  Rationale: our tool schemas are contracts-owned JSON (AD-1/AD-17); `FastMCP.add_tool`
  *derives* input/output schemas from Python type hints, which would force us to re-express
  the contracts as typed function signatures. `Server` accepts explicit `types.Tool` objects
  with hand-authored `inputSchema` + `outputSchema` + `description`, which maps 1:1 onto the
  contracts. Confirmed live: `@server.list_tools()` returns `types.Tool` carrying
  `inputSchema`, `outputSchema`, and `description`; `@server.call_tool()` validates
  `structuredContent` against `outputSchema`.
- stdio transport: `from mcp.server.stdio import stdio_server` → async ctx manager yielding
  `(read_stream, write_stream)` passed to `Server.run(...)`. Available and confirmed.
- `types.Tool` fields present: `name, title, description, inputSchema, outputSchema, icons,
  annotations, meta, execution` — `outputSchema` is a first-class field (spec ≥2025-06-18).

## Drives

- Story 1.4 MCP surface (`adapters/mcp_server.py`).
- The `mcp` entry in `pyproject.toml` `[project.dependencies]` — now pinned `>=1.28,<2`.

## Runtime-confirm (resolved)

- ~~SDK v2 stable release available?~~ Not shipped as of the Phase-0 gate; SDK still v1.
- Required capabilities present: stdio transport ✓, `outputSchema` on `Tool` ✓, streamable
  HTTP transport ✓ (`FastMCP.run_streamable_http_async`, unused in Phase 0). Elicitation /
  resource links: present in the type surface, exercised by later stories (Phase 2+).
- Import surface confirmed: `FastMCP` (not `MCPServer`); Phase 0 server built on low-level
  `Server`.
