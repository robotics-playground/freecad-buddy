# Sprint Change Proposal — Addon Auto-Starts MCP; RPC Demoted to Debug Fallback

- **Date:** 2026-07-23
- **Author:** TanNT (via Developer correct-course)
- **Scope classification:** Minor (doc alignment + already-implemented code)
- **Trigger:** User request — "opening FreeCAD should launch MCP in the addon; never run RPC by hand as the normal path."

## 1. Issue Summary

Reaching the FreeCAD bridge over MCP required **two manual steps**: open FreeCAD (addon starts the in-process RPC listener) AND separately run `freecad-buddy serve --mode rpc --transport http` to start the external MCP HTTP server on `:8765`. When that second step was skipped, the MCP client hit `ConnectionRefused at http://127.0.0.1:8765/mcp` — exactly what the user observed. The docs described the manual `serve --mode rpc` launch as the normal operator flow.

**User ruling:** opening FreeCAD must be the only step; the internal RPC channel stays (it is how the external proxy talks to the in-FreeCAD listener — the AD-2 topology), but the manual `serve --mode rpc` CLI is **only for debugging/troubleshooting when MCP is unavailable**, never the normal path.

## 2. Impact Analysis

- **Epic Impact:** Epic 1 (Verifiable FreeCAD Bridge) — FR6 and Story 1.8 (GUI host) describe the GUI startup flow.
- **Story Impact:** Story 1.8 gains an acceptance criterion for the auto-spawn; already-`done`, so this is a retroactive contract clarification, not a re-open.
- **Artifact Conflicts:** ARCHITECTURE-SPINE AD-2 amendment note; design docs component / project-structure / integration-mcp-freecad / integration-mcp-clients; `.memlog`; `CLAUDE.md`; `docs/tests/TC-06`.
- **Technical Impact:** `gui_addon/bootstrap.py` implemented this session — `start_bridge` auto-spawns the proxy, `stop_bridge` terminates it. AD-2 (external MCP server) + AD-12 (no `mcp` import in FreeCAD) preserved: the addon spawns a child process in the external interpreter, never imports `mcp`. Verified live: MCP client → `:8765` → listener → live GUI, 23 tools + `document_list` returned the live session.
- **Follow-up correction (same day):** the first cut required an env var (`FREECAD_BUDDY_REPO`/`MCP_CMD`) to locate the external interpreter — bad UX. Reworked `_mcp_proxy_command` to **auto-discover the project `.venv`/`venv` python from the addon's own install path** (walk `__file__` → repo root), so no env var is required: install addon, `uv sync`, open FreeCAD. Env vars remain only as an optional override/legacy fallback. Verified: with all env cleared the resolver finds `.venv\Scripts\python.exe` and the direct spawn brings up `:8765`.

## 3. Recommended Approach

**Direct Adjustment.** No rollback, no scope cut. The RPC wire contract, listener, marshal, and error taxonomy are unchanged and correct — only the *operator startup story* changes (auto-spawn) and the manual RPC CLI is reframed as a debug fallback. The internal proxy↔listener RPC transport is untouched.

- Effort: doc-only (code already landed this session).
- Risk: low. The auto-spawn is guarded (opt-out env `FREECAD_BUDDY_NO_AUTO_MCP`, `:8765`-in-use skip, best-effort spawn that never breaks listener/GUI start).

## 4. Detailed Change Proposals

### Architecture
- **ARCHITECTURE-SPINE.md AD-2** — amendment note now: addon starts the listener AND auto-spawns the external MCP server (child process, external interpreter, never imports `mcp`); `serve --mode rpc` is a debug fallback.
- **design/component-design.md** — InitGui/bootstrap row: auto-spawn responsibility added.
- **design/project-structure.md §4.1** — dev flow step 4 = auto-spawn; step 5 = debug-only manual launch.
- **design/integration-mcp-freecad.md §3.1** — `start_bridge()` auto-spawns the proxy; launch resolution + opt-out documented.
- **design/integration-mcp-clients.md §2.2** — addon auto-spawns; `.mcp.json` is a plain HTTP url, no manual launch.
- **.memlog.md** — decision entry appended.

### Stories
- **epics.md FR6** — GUI host includes the auto-spawned external MCP proxy.
- **epics.md Story 1.8** — new AC5: addon auto-spawns the proxy (guards + teardown); manual `serve --mode rpc` = debug fallback.

### Ops / Guidance
- **CLAUDE.md §12 "Running the MCP Bridge"** — opening FreeCAD is the only step; use `mcp__freecad-buddy__*`; do not hand-run `serve --mode rpc` or raw RPC sockets; `.mcp.json` = plain HTTP; RPC is debug-only.
- **docs/tests/TC-06** — prerequisite reworded: proxy auto-spawned on FreeCAD start.

## 5. Implementation Handoff

- **Scope:** Minor → Developer agent (self). Code already implemented + verified this session; this proposal records the design-contract alignment.
- **Success criteria:** install the addon, `uv sync`, open FreeCAD → the addon auto-discovers the project `.venv` and brings up `:8765` with **zero env vars / zero manual commands**; the MCP client connects straight through. Env overrides (`FREECAD_BUDDY_MCP_CMD`, legacy `FREECAD_BUDDY_REPO`+`uv`) remain optional for non-standard installs; `serve --mode rpc` remains available for debugging. All architecture/epic/ops docs consistent with auto-start (no-env) + RPC-as-debug-fallback.
- **Follow-up:** none blocking. Commit awaits user approval (per repo rules).

## What was NOT changed (deliberate)

The RPC *wire-contract* docs stay as-is — they describe the internal proxy↔listener transport, which is unchanged and still the AD-2 topology:
`data-contracts-design.md §11` (RPC frames), `security-and-service-design.md §2` (bind/token), `mcp-tools-design.md`, the review docs, the mcp-embedding research, and the historical `spec-1-*` implementation specs. Ripping "RPC" out of these would corrupt the (correct) transport design.
