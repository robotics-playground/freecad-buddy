---
title: 'MCP Client Integration Design — Claude Code, Local LLM, Future Agent Clients'
status: draft
date: '2026-07-21'
ad-refs: [AD-3, AD-4, AD-10, AD-12, AD-15, AD-17, AD-20]
sources:
  - ../ARCHITECTURE-SPINE.md
  - ../../../research/technical-local-llm-mcp-tool-use-research-2026-07-20.md
  - ../../../research/technical-headless-preview-diff-channel-research-2026-07-20.md
  - ../../../research/technical-freecad-mcp-servers-survey-research-2026-07-20.md
---

# MCP Client Integration Design

One FastMCP server object serves every client; transport is a run flag (AD-3). Clients differ only in transport, confirmation mechanism, skills delivery, and image handling. This document fixes those per-client rules so no client-specific logic leaks into `usecases/` (AD-1) and no client gets a weaker safety posture than AD-10 allows.

## 1. Client Contexts

| Context | Transport (AD-3) | Phase |
| --- | --- | --- |
| Claude Code / Claude Desktop, headless bridge | stdio | 0+ |
| Claude Code / Claude Desktop, GUI-attached bridge | streamable HTTP (localhost) | 0+ |
| Local backend: llama.cpp `llama-server` (native MCP client) | streamable HTTP (localhost) | 1+ |
| ReAct / system-prompt-injection fallback (any OpenAI-compatible endpoint) | in-process adapter — no MCP transport | 1+ |
| Headless CI harness | stdio or in-process | 0+ |
| External agent (Phase 4) | streamable HTTP | 4 |

SSE never (AD-3). HTTP and RPC bind localhost; remote bind is explicit operator opt-in (AD-3).

## 2. Claude Code / Claude Desktop Wiring

### 2.1 stdio (dev / headless bridge)

Project `.mcp.json` (Claude Code) or `claude_desktop_config.json` (Desktop):

```json
{
  "mcpServers": {
    "freecad-buddy": {
      "command": "uv",
      "args": [
        "run", "--project", "D:/Work/Personal/Sources/freecad-buddy",
        "freecad-buddy", "serve", "--transport", "stdio", "--mode", "inline"
      ]
    }
  }
}
```

stdio discipline: stdout carries protocol frames only; all logging to stderr (AD-3). The external process owns all third-party deps via uv (AD-12).

### 2.2 Streamable HTTP (GUI-attached)

The FreeCAD addon starts the RPC listener AND **auto-spawns the external MCP HTTP server** as a child process — opening FreeCAD is the whole setup. It serves long-lived on `http://127.0.0.1:8765/mcp` and relays to the in-GUI RPC listener (AD-2, AD-3). The client config below is a plain HTTP entry with no `command`/`serve`/`rpc` in it; the operator never launches the server by hand (that CLI is a debug-only fallback).

```json
{
  "mcpServers": {
    "freecad-buddy": {
      "type": "http",
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

Equivalent CLI: `claude mcp add --transport http freecad-buddy http://127.0.0.1:8765/mcp`.

### 2.3 Tool discovery

Standard `tools/list`. Names follow the underscore convention (`query_*`, `verify_*`, `preview_*`, …) — dots are illegal in MCP tool names (spine Consistency Conventions). Every tool ships `outputSchema`; results carry `structuredContent` plus text mirror (AD-17, conventions). `debug_exec` is unregistered from the tool list unless the operator env flag is set (AD-4) — Claude clients never see it by default.

### 2.4 Skills loading (AD-15)

One skill store (`skills/`, `SKILL.md` + `references/`). For Claude Code, the production metadata-first router maps directly onto the native skill mechanism: skill descriptions resident, 2–5 bodies loaded per task on trigger. Delivery = expose the store to Claude Code as native skills (symlink or generated `.claude/skills/` entries pointing at the single store — no second copy of skill bodies). The routed subset is logged per AD-15; the ≤~10K token skill budget applies.

Ablation runs against Claude Code use the forced-subset injection path with native auto-activation disabled — same mechanism as the local backend (§3.4), which is what makes it the portable second harness.

### 2.5 Elicitation flow

Mutation confirm rides MCP elicitation (spec ≥2025-06-18; AD-10, Stack MCP row):

1. Client calls `preview_dry_run` → structured diff on TempDoc (AD-10, AD-20).
2. Client calls the mutation tool; server issues an elicitation request carrying the diff summary; proceeds only on `action: "accept"`; `decline`/`cancel` abort with a typed status (AD-17 closed set).
3. On accept, the op re-runs on the live document under the AD-5 transaction protocol.

Capability detection at `initialize`: if the client does not declare elicitation support, the server switches that session to the client-confirm fallback — the mutation tool requires an explicit `preview_id` (confirm token) issued by the matching `preview_dry_run` result, and the client's own tool-approval prompt (an MCP-spec SHOULD) is the human gate. A mutation call without a valid token in a no-elicitation session is rejected, not silently executed.

## 3. Local Backend (Phase 1 second backend)

> **Phase 1 pin decision** (spine Deferred: "Local LLM backend pin"). Research is settled; the exact model + harness versions are pinned at the Phase 1 gate and thereafter gated on the eval set.

### 3.1 Recommended stack

**llama.cpp `llama-server` (native MCP client, merged Apr 2026) running Qwen3-30B-A3B-Instruct at Q4_K_M** (~16–19 GB VRAM, single RTX 3090/4090; ~73–196 tok/s), connected to the bridge over streamable HTTP.

```bash
llama-server \
  -m Qwen3-30B-A3B-Instruct-Q4_K_M.gguf \
  --jinja --ctx-size 32768 -ngl 99 --port 8080
# llama-server web UI / agent config: register MCP server
#   http://127.0.0.1:8765/mcp  (freecad-buddy bridge, HTTP transport)
```

Why this pair: different vendor, different transport, fully local — a clean model-agnosticism proof vs the Claude leg; Qwen3 has the lowest dropped-tool-call rate among local models; headless `llama-server` pins a GGUF and scripts for the reproducible eval/CI run. Alternatives (LM Studio for interactive dev with per-call confirm dialogs; Ollama for fast demo, version-pinned) are acceptable substitutes, not the eval backend.

### 3.2 Constrained decoding — required

The local leg MUST run with grammar/JSON-Schema-constrained sampling for tool calls (llama.cpp grammars). This drives tool-call format errors from 15–25% to ~0%, decoupling Phase 1 pass rates from model formatting quirks. An unconstrained local run is a diagnostic configuration, never an eval configuration.

### 3.3 ReAct / system-prompt-injection fallback adapter

The model-agnostic proof path, built regardless of model choice. An adapter in `adapters/` (external process) that presents the same tool interface the MCP path uses:

- **Prompt build:** render tool names + JSON schemas + calling convention into the system prompt (schemas sourced from `contracts/` — single source of truth).
- **Loop:** ReAct — model emits a fenced JSON tool-call block → adapter parses → dispatches through the same tool registry the FastMCP server uses → appends the `ResultEnvelope` text mirror to the transcript → repeats until a final answer.
- **Parser:** scans text for JSON objects matching the tool-call shape; malformed JSON → one structured re-prompt, then typed failure (`INVALID_INPUT`), never silent retry loops.
- **Question detector:** if the model asks the user instead of calling a tool, re-prompt once to use the tool.
- **Safety parity:** the adapter is a client like any other — typed tools only (AD-4), confirmation per §4 (no elicitation ⇒ token fallback or fail-closed), explicit document handles (AD-20).

This adapter works against any OpenAI-compatible `/v1/chat/completions` endpoint (llama-server, Ollama, vLLM), so backend #2 is proven twice: native MCP tool-calling and text-parse injection over the same tool interface.

### 3.4 Skills loading (AD-15)

No native skill mechanism exists on this path. Skills are delivered by injection: the bridge-side skills loader (router mode) selects 2–5 bodies and prepends them to the system prompt within the ≤~10K token budget; ablation mode injects a forced explicit subset. Same store, no forked content.

## 4. Confirmation Matrix (AD-10)

| Client context | Preview delivery | Confirm mechanism | On no-confirm |
| --- | --- | --- | --- |
| GUI panel (FreeCAD dock) | Diff table + renders in panel | Native Apply/Cancel buttons | Abort, TempDoc discarded |
| MCP client with elicitation (Claude Code/Desktop) | `structuredContent` + text mirror (+ render per §5) | Elicitation `accept`/`decline`/`cancel` | `decline`/`cancel` → typed abort |
| MCP client without elicitation (llama.cpp, LM Studio, ReAct adapter) | `structuredContent` + text mirror | `preview_id` (confirm token) from `preview_dry_run` + client's own tool-approval prompt | Missing/stale token → reject |
| Headless CI / agent-to-agent | Diff JSON in job log / report | **Fail-closed**: no mutation without explicit `autoApprove` flag; every auto-approval audit-logged with its diff (AD-10, AD-17) | Mutation rejected |

Invariants: the structured diff is the mandatory payload in every row; confirmation never gates on a render succeeding; `autoApprove` is an operator-set env flag (conventions), never a client-supplied parameter.

## 5. Image / Render Delivery Rules (AD-10)

Renders are optional and capability-gated (GUI `saveImage` → offscreen/Xvfb → omit). Budget: ≤1024 px longest edge, PNG, annotated `audience: ["user"]`.

| Client | Delivery | Rationale |
| --- | --- | --- |
| GUI panel | Local file path, shown in panel | No token cost |
| Claude Code / Desktop | `resource_link` preferred; inline base64 only for small thumbnails or on explicit request | Known client-side base64-as-text token blow-up (10–20×; 25k tool-result limits) |
| llama.cpp / LM Studio / ReAct adapter | `resource_link` only; never inline | Local context is the scarcest resource; image is for the human, not the model |
| Headless CI | PNG artifact saved to job dir; path in report | Best-effort; absence is not a failure |

## 6. Backend Capability Matrix

| Backend | Transport | Elicitation | Native skills | Structured output | Confirm path |
| --- | --- | --- | --- | --- | --- |
| Claude Code | stdio / HTTP | Yes (spec ≥2025-06-18; verify exact client support at Phase 0 pin) | Yes — skill store exposed natively (§2.4) | `structuredContent` + `outputSchema` consumed | Elicitation |
| Claude Desktop | stdio | Verify at Phase 0 pin | No — router-injected summaries | `structuredContent` + text mirror | Elicitation, else token fallback |
| llama.cpp `llama-server` | HTTP | No | No — prompt injection | Native Qwen3 tool templates + **constrained decoding (required)** | Token fallback |
| LM Studio (dev convenience) | stdio (`mcp.json`) | No | No — prompt injection | Native tool templates | Per-call confirm dialog (client-confirm) + token |
| ReAct fallback adapter | none (in-process) | No | No — prompt injection | Text-parse of fenced JSON | Token fallback / fail-closed |
| Headless CI harness | stdio / in-process | No | Forced-subset injection (ablation) | JSON report (AD-17 envelopes) | Fail-closed + `autoApprove` |

Capability probes at session start, never client-name sniffing (mirrors the AD-11 probe discipline).

## 7. Latency Budget (Phase 1: ≤15 s median)

- Turn shape: short reasoning + 1–3 `query_*` calls + paragraph answer ≈ 300–800 output tokens. Qwen3-30B-A3B at ≥73 tok/s completes well under 15 s; pessimistic dense-32B (~30 tok/s) is the ceiling case to avoid.
- **Summarized-tree dependency is load-bearing:** local generation throughput drops ~75% from 4K to 131K context, so `query_*` tools must return summarized trees, never raw dumps. This is a tool-contract property, not client configuration — every backend benefits.
- Skill injection stays inside the AD-15 ≤~10K token budget; renders never inline on the local leg (§5) — both protect the same context budget.
- Recompute dominates in-FreeCAD time (survey §6); the RPC hop is negligible. Eval runs report median + distribution per AD-14 repeat rules.

## 8. Open Items

| Item | Closes at |
| --- | --- |
| Exact model + llama.cpp version pin; eval-gated upgrades | Phase 1 gate (spine Deferred) |
| Claude Code / Desktop elicitation support verification against pinned SDK (2025-11-25 target) | Phase 0 SDK pin |
| `preview_id` (confirm token) TTL and single-use semantics in the mutation tool contract | Phase 2 UX design (with preview `outputSchema` lock, spine Deferred) |
| Native-skill exposure mechanics (symlink vs generated stubs) for Claude Code | Phase 1 skills-track setup |
