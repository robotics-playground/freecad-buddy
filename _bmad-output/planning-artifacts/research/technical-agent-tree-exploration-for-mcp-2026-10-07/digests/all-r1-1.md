# Digest — all dimensions, round 1 (inline, lead)

Accessed 2026-10-07.

| # | Claim | Source | Publisher | Pub date | Confidence | Class |
|---|---|---|---|---|---|---|
| 1 | MCP list operations paginate with an opaque `cursor` / optional `nextCursor`; page size is set by the server; clients must not parse cursors; invalid cursor → error -32602. Spec lists `resources/list`, `resources/templates/list`, `prompts/list`, `tools/list` as paginated operations. | https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/pagination | MCP project | 2025-06-18 (spec version) | high | protocol |
| 2 | The MCP reference filesystem server offers `list_directory` (one level, `[FILE]`/`[DIR]` prefixes), `list_directory_with_sizes` (one level plus totals), `directory_tree` (recursive JSON `{name,type,children}`, `excludePatterns`), and `search_files` (recursive glob, returns paths). | https://github.com/modelcontextprotocol/servers/blob/main/src/filesystem/README.md | MCP project | main branch, accessed 2026-10-07 | high | pattern |
| 3 | Anthropic advises tools to return high-signal information, avoid low-level identifiers, and combine pagination, range selection, filtering and truncation with sensible defaults; Claude Code limits tool responses to 25,000 tokens by default. | https://www.anthropic.com/engineering/writing-tools-for-agents | Anthropic | 2025-09-11 | high | guidance |
| 4 | Same source: a `response_format` enum (`concise`/`detailed`) lets the agent choose detail; its example: 72 tokens concise vs 206 detailed. | same | Anthropic | 2025-09-11 | high | guidance |
| 5 | Same source: when truncating, steer the agent with instructions toward small targeted calls instead of one broad call. | same | Anthropic | 2025-09-11 | high | guidance |
| 6 | FreeCAD's tree view shows a group's `Group` values as its children (`ViewProviderGroupExtension::extensionClaimChildren`). | FreeCAD `src/Gui/ViewProviderGroupExtension.cpp:174-184`, commit 4fd3bf3 | FreeCAD project | 2026-09-28 | high | primary-source |
| 7 | A PartDesign sketch-based feature claims only its `Profile` sketch as a tree child, not its base or previous feature (`ViewProviderSketchBased::claimChildren`). | FreeCAD `src/Mod/PartDesign/Gui/ViewProviderSketchBased.cpp:75-84`, commit 4fd3bf3 | FreeCAD project | 2026-09-28 | high | primary-source |

Looked for, not found: the FreeCAD wiki page `Std_Group` (blocked by a bot check); an MCP-wide convention for paginating *tool results* (the spec paginates list operations only).

Leads: LSP `textDocument/documentSymbol` hierarchical outline (not pursued, budget).
