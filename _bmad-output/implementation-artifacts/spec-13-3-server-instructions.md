---
title: 'Story 13-3: Server instructions that put typed tools first'
type: 'feature'
created: '2026-11-24'
status: 'done'
baseline_commit: '905e038df5508a9083e8db952089b97739f31fc7'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The MCP `initialize` result carries no `instructions`. A client reaches `script_exec` before it knows which typed tool families exist (CAP-6).

**Approach:** Both MCP servers send one shared, client-neutral instruction text (T-10, at most 250 words). The `script_exec` description points to it.

## Boundaries & Constraints

**Always:** Plain text, identical for every client. Tool families named in the text exist in `tool_specs()`. The gap list is named by skill (`freecad-scripting-idioms`), never copied. `contracts/` ← `usecases/` ← `adapters/` ← `hosts/` import direction holds.

**Never:** Client-specific tool-loading text (no `ToolSearch` line; decision 10). Tools that do not exist yet. A change to the `script_exec` description beyond the one pointer sentence (Story 13-13 rewrites it). Edits to design docs, `skills/**`, planning documents.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| In-FreeCAD server | `build_server(...)` init options | `instructions` equals the shared text | N/A |
| GUI proxy server | `build_proxy_server(...)` init options | `instructions` equals the same text | N/A |
| Size | the shared text | at most 250 words | test fails above 250 |
| Client neutrality | the shared text | no `ToolSearch`, no `select:` | test fails on a match |
| Drift | each family prefix in the text | at least one real tool name starts with it | test fails on none |
| Cache relay | upstream sends `instructions`; relay refreshes; later relay starts with upstream down | relay `initialize` carries the cached upstream text | no cache or unreadable file: no `instructions` |
| script_exec | `SCRIPT_EXEC_SPEC.description` | contains "check the typed tool families in the server instructions" | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/adapters/mcp_server.py:231` -- `Server(name)`; add `instructions=SERVER_INSTRUCTIONS` and the constant.
- `src/freecad_buddy/hosts/gui_external/entry.py:55` -- `Server("freecad-buddy-gui-external")`; import the constant from `mcp_server`.
- `src/freecad_buddy/hosts/tool_catalog.py:1064-1068` -- `script_exec` description.
- `tests/external/test_mcp_surface.py`, `tests/external/test_gui_external_proxy.py` -- test homes.
- `scripts/automation/mcp_cache_proxy.py` -- UAT relay (`CacheProxy`, `Upstream._own`): stores upstream `instructions`, caches them beside the tool cache, sends them in its own `initialize`. Added by leader instruction (2026-11-24).
- `tests/external/fake_mcp_upstream.py` -- `--instructions` option for the relay test.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/adapters/mcp_server.py` -- add `SERVER_INSTRUCTIONS`, pass to `Server` -- CAP-6, T-10
- [x] `src/freecad_buddy/hosts/gui_external/entry.py` -- pass same constant -- M-4
- [x] `src/freecad_buddy/hosts/tool_catalog.py` -- append pointer sentence to `script_exec` description -- T-10
- [x] `scripts/automation/mcp_cache_proxy.py`, `tests/external/test_mcp_cache_proxy.py`, `tests/external/fake_mcp_upstream.py` -- relay passes upstream instructions through a cache file -- relay sees the container before it runs only through the cache
- [x] both test files -- tests for each matrix row -- verification

**Acceptance Criteria:**
- Given either server is built, when its initialization options are read, then `instructions` is the shared text.
- Given the shared text, when counted, then it has at most 250 words and no client-specific loading text.

## Implementation Notes

- `SERVER_INSTRUCTIONS` lives in `adapters/mcp_server.py` (143 words). `gui_external/entry.py` imports it.
- Relay option chosen: cache file `<server>.instructions.txt` beside the tool cache. The relay builds its `initialize` result once at start, before any upstream connection exists when the container is down, so it reads the text saved by the last refresh. The first run after this change has no cached text; the second relay start carries it. Works for both upstreams (`freecad-buddy-docker`, `cua-driver-docker`) without the relay importing source.
- Gates run: ruff check, check_imports, gen_schemas --check, `pytest tests/external` (1857 passed, 4 skipped).
- Not run here (verifier): live `initialize` against the container proxy and the relay (rebuild `dist/addon` and the image first), and Q9, whether a headless Claude Code session sees the instructions before its first tool load (`SPEC.md:93`). The relay needs one earlier run to cache the text.

## Spec Change Log

- Leader added the relay pass-through (matrix row, Code Map entry, task) after approval of the plan; no code was written before that approval.

## Review Triage Log

| Finding | Lens | Verdict | Route | Evidence |
|---|---|---|---|---|
| Text names `script_exec` when it is off | blind, edge | low | rejected | T-10 fixes one text for every client; `ScriptExec` is on by default; a per-capability text adds branching the contract does not ask for |
| Relay sends old text at first start | blind | low | rejected | the relay builds `initialize` once before any upstream connection exists; inherent to the cache-first design; README now states it |
| Failed text write blocks tool cache update | blind, edge | medium | patch | `_cache_instructions` now catches `OSError` and logs |
| Text file not written atomically | blind, edge | medium | patch | shared `_replace_file` with the Windows retry |
| Relay keeps stale text when upstream stops sending | blind, edge, gap | medium | patch | `None` removes the file; test added |
| Empty-string instructions rewrite every cycle | edge | low | patch | `initialized.instructions or None` |
| Drift test hard-codes the family list; `verify_export_` unchecked | blind, edge, gap | medium | patch | test parses the families from the text and compares with the expected nine |
| First T-10 sentence untested | blind | low | patch | test asserts both sentences and skill names |
| Client product names unchecked | blind | low | patch | `Claude`, `Cursor`, `Codex`, `Gemini` added |
| `script_exec` description change not pinned | blind, gap | low | patch | test asserts start, one pointer, and `endswith` |
| Relay tests miss changed text and unusable file | gap | medium | patch | three tests added |
| No real `initialize` round trip | gap | low | verifier | quality bar Q2, Q3, Q9 assign it to the live check |
| Spec lacks live checks; word count wrong; README silent | blind | low | patch | spec notes and `tests/close-loop/README.md` updated |

## Verification

**Commands:**
- `uv run ruff check .` -- expected: no findings
- `uv run python scripts/check_imports.py` -- expected: OK
- `uv run python scripts/gen_schemas.py --check` -- expected: OK
- `uv run pytest tests/external -q` -- expected: pass (known flaky tests re-run alone)
