---
stepsCompleted: ['init', 'evidence-gathering', 'synthesis', 'recommendation']
inputDocuments: ['docs/intent.md']
workflowType: 'research'
lastStep: 4
research_type: 'technical'
research_topic: 'Local LLM backends with reliable MCP tool-use for a CAD assistant'
research_goals: 'Identify local-LLM harnesses that support MCP clients with reliable tool calling, which open-weight models have adequate tool-use quality (mid-2026), minimum practical model size/VRAM, latency vs the 15s median criterion, and a plain system-prompt fallback. Recommend a concrete second backend stack to satisfy Phase 1 exit criterion (>= 2 LLM backends).'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical — Local LLM Backends with Reliable MCP Tool-Use for a CAD Assistant

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** Technical (deep dive)
**Project:** freecad-buddy

---

## Research Overview

**Driving question.** FreeCAD Buddy Phase 1 (Assistant) exit criteria require the read-only bridge to run "against at least 2 LLM backends (e.g. Claude API + one local model) to prove the bridge is model-agnostic" (`docs/intent.md`, Phase 1). The architecture direction commits to MCP as the tool protocol and to an agent-agnostic design where "any MCP client" can drive the FreeCAD bridge. This research identifies the concrete **second backend** — a local, open-weight stack — that can call the bridge's `query.*` / `verify.*` tools reliably enough to pass the Phase 1 evaluation, within the phase's latency budget (**≤ 15 s median response**) and on hardware a solo developer plausibly owns.

**Scope of the decision.** Phase 1 exposes **read-only tools only** and needs correct answers on a 50-question eval plus error-diagnosis on 10 broken-recompute cases. The tool-use burden is therefore modest: a handful of `query.*` calls per turn (tree summary, object properties, recompute status), not long-horizon multi-tool planning. This matters — the local-model bar for Phase 1 is "reliably emit a valid tool call and read back the result", which is comfortably inside 2026 open-weight capability, well below the harder multi-turn agentic regime that still challenges even frontier models.

**Methodology.** Web-sourced evidence (July 2026) across four axes: (1) harness/runtime MCP-client support (Ollama, llama.cpp, LM Studio, vLLM); (2) open-weight tool-use quality via the Berkeley Function Calling Leaderboard (BFCL) and model release notes; (3) practical model size / VRAM at usable quantization; (4) generation latency vs the 15 s criterion. Cross-checked against the project's own reuse discipline (`docs/intent.md` Reuse Map: "MCP client ecosystem; plain system-prompt injection for other LLMs").

---

## Key Findings

### Finding 1 — The MCP-client-in-the-runtime problem is solved as of 2026

The single biggest de-risking event since the intent doc was written: **llama.cpp merged a native MCP client into `llama-server` / its web UI in April 2026**, turning the inference engine into an agent runtime that connects directly to MCP tool servers — the same protocol Claude uses. Models with native tool-calling templates (Qwen3 family, Qwen3-Coder) use them out of the box ([jasonmoon.dev](https://jasonmoon.dev/blog/2026-04-15-mcp-v21-llama-cpp-local-agents), [localaimaster.com](https://localaimaster.com/blog/llama-cpp-mcp-server), [Buttondown](https://buttondown.com/insiderllm/archive/this-week-in-local-ai-llamacpp-gets-mcp-qwen3/)).

Three viable harness routes now exist, each an MCP **host/client** that can consume the FreeCAD bridge (an MCP **server**):

| Harness | MCP client role | Best fit for freecad-buddy | Notes |
|---|---|---|---|
| **LM Studio** (v0.3.17+; v0.4.11 Apr 2026) | Built-in MCP **host**; `mcp.json` config; per-call confirmation dialog with argument editing | **Interactive dev + human-in-the-loop** — matches Phase 1/2 "confirm every mutation" principle | OAuth for MCP servers; OpenAI-compatible API; GUI ([lmstudio.ai/docs](https://lmstudio.ai/docs/app/mcp), [lmstudio.ai/blog](https://lmstudio.ai/blog/lmstudio-v0.3.17)) |
| **llama.cpp** (`llama-server` + MCP client, Apr 2026) | Native MCP client in server/web UI; constrained decoding available | **Headless CI / reproducible eval** — pin a GGUF, script it, no daemon lock-in | Closest to the metal; OpenAI-compatible endpoint ([localaimaster.com](https://localaimaster.com/blog/llama-cpp-mcp-server)) |
| **Ollama** (native tools 0.3.0+, streaming tool calls added) | Tool calling via API; MCP via external clients (e.g. `jonigl/mcp-client-for-ollama`) + growing native support | **Fastest to first demo** — one-line model pulls, huge ecosystem | New structural (non-JSON-greedy) tool-call parser improves reliability; some configs still break between releases ([docs.ollama.com](https://docs.ollama.com/capabilities/tool-calling), [ollama.com/blog](https://ollama.com/blog/streaming-tool)) |
| **vLLM** | OpenAI-compatible tool API | Only if multi-user / high-throughput serving is needed | Overkill for single-user Phase 1; GPU-heavy production throughput ([Red Hat](https://developers.redhat.com/articles/2026/06/15/llamacpp-vs-vllm-choosing-right-local-llm-inference-engine)) |

**Security note worth flagging for Phase 4:** MCP v2.1 made tool sandboxing a **mandatory** spec requirement after research found command-injection vulnerabilities in 43% of v2.0 implementations ([localaimaster.com](https://localaimaster.com/blog/llama-cpp-mcp-server)). freecad-buddy's typed-tool layer (no free-form `exec` in the mutation path) already aligns with this; keep the bridge on MCP ≥ 2.1.

### Finding 2 — Open-weight tool-use quality is comfortably adequate for Phase 1 (and much of Phase 2)

BFCL (the Gorilla/UC-Berkeley standard for tool-call accuracy) as of mid-2026 shows open-weight Chinese frontier models leading the public function-calling board:

- **GLM-4.5 (Zhipu/Z.ai): 77.8%**, **GLM-4.5-Air: 76.4%** (BFCL V3, June 2026)
- **LongCat-Flash-Thinking (Meituan): 74.4%**
- **Qwen3 family: ~71–72%** cluster; Qwen3.x Max leads BFCL-V4 at 0.750
  ([llm-stats.com/BFCL-v3](https://llm-stats.com/benchmarks/bfcl-v3), [pricepertoken.com](https://pricepertoken.com/leaderboards/benchmark/bfcl-v3), [llm-stats.com/BFCL-v4](https://llm-stats.com/benchmarks/bfcl-v4))

Two caveats the leaderboards themselves surface, both of which *favour* the Phase 1 use case:
1. Top models "excel at single-turn function calling but continue to face challenges with memory management, long-horizon reasoning, and determining when *not* to invoke tools." Phase 1 is dominated by **single-turn, read-a-property** calls — the regime where open models are strongest.
2. **Reliability ≠ raw benchmark rank.** Independent "dropped tool call" testing (Morph LLM) puts the **Qwen3 series as the most stable local tool-caller** — lowest rate of ignored tools / invalid JSON — which for an assistant that must *actually fire* `query.*` every turn matters more than a 5-point BFCL edge ([webscraft.org](https://webscraft.org/blog/yaku-model-ollama-obrati-dlya-agenta-z-tool-calling-porivnyannya-i-benchmarki?lang=en), [localaimaster.com](https://localaimaster.com/blog/ollama-function-calling-tools)).

An important reliability lever independent of model choice: **constrained decoding** (grammar/JSON-Schema-constrained sampling, available in llama.cpp and vLLM) "reduces JSON parsing error rates from 15–25% with prompt-based methods to nearly 0%" ([dev.to](https://dev.to/kuroko1t/what-happens-when-local-llms-fail-at-tool-calling-testing-7-models-with-a-rust-coding-agent-cep)). This turns "the model formats the tool call wrong" from a model problem into a solved harness-config problem — critical for hitting Phase 1 pass rates without babysitting.

### Finding 3 — Minimum practical size/VRAM: two clean tiers

**Recommended primary tier — Qwen3-30B-A3B (MoE, ~3B active):** best speed/quality/VRAM balance for a solo dev.
- 30.5B total params, MoE with only ~3B active per token → dense-quality answers at small-model speed.
- Q4_K_M ≈ **16–19 GB** VRAM; fits a 24 GB card (RTX 3090/4090) with room for context. Q4_K_M retains ~99% of BF16 quality on code-gen evals (Unsloth).
- Native tool-calling templates; Qwen3-Coder-30B-A3B tool-calling explicitly fixed to work in llama.cpp / Ollama / LM Studio / Jan ([unsloth.ai/qwen3-coder](https://unsloth.ai/docs/models/tutorials/qwen3-coder-how-to-run-locally), [HF Qwen3-30B-A3B](https://huggingface.co/Qwen/Qwen3-30B-A3B), [compute-market.com](https://www.compute-market.com/blog/qwen-3-local-hardware-guide-2026)).

**Budget tier — 8B–14B dense (8–16 GB VRAM):** for developers on a laptop / 8–12 GB card.
- Hermes-3-Llama-3.1-8B called out as "the best 8B option for tool use; runs on 8 GB VRAM"; Qwen3-14B-class fits 16 GB at Q4 ([lmstudio.ai/docs](https://lmstudio.ai/docs/app/mcp)). Adequate for Phase 1's simple single-tool calls; expect to lean on constrained decoding.

**Ceiling tier — GLM-4.5-Air (106B MoE, 12B active):** highest tool-use quality that still fits one workstation-class GPU.
- INT4 ≈ **12–16 GB**, FP8 on a single H100. Purpose-built for agentic multi-step tool use — the natural upgrade if/when Phase 3–4 need stronger planning locally ([apxml.com/glm-45-air](https://apxml.com/models/glm-45-air), [digitalocean.com](https://www.digitalocean.com/community/tutorials/glm-agentic-reasoning-coding-model)).

**Floor:** don't go below ~8B for tool use; sub-8B models "still struggle with multi-tool reasoning" (Ollama ecosystem reports, April 2026).

### Finding 4 — Latency clears the 15 s median criterion with wide margin

Phase 1 requires **≤ 15 s median** end-to-end response. Local generation speeds on a single RTX 4090 (24 GB):
- **Qwen3-30B-A3B (MoE): ~73–196 tok/s** depending on context (196 tok/s light context; ~73–87 tok/s for the Coder variant under load).
- Dense 14B: ~78 tok/s at 16K context; dense 32B: ~30–45 tok/s.
  ([mustafa.net](https://mustafa.net/llm-tokens-per-second-benchmarks/), [hardware-corner.net](https://www.hardware-corner.net/gpu-llm-benchmarks/rtx-4090/))

A Phase 1 assistant turn is a short reasoning trace + 1–3 tool calls + a paragraph answer — call it 300–800 output tokens. Even the pessimistic 30 tok/s dense-32B case yields ~10–27 s for a *single* long generation; the recommended **Qwen3-30B-A3B at 73+ tok/s completes a full turn (including tool round-trips) in well under 15 s**. The known latency killer is **context length** (generation drops ~75% from 4K to 131K context) — which is exactly why the intent doc's requirement to use **summarized tree queries, not raw dumps** (Phase 1 criterion 3) is load-bearing for latency, not just context limits. Keep prompts tight and the budget is comfortable.

### Finding 5 — The plain system-prompt fallback is real, cheap, and worth building anyway

The intent doc's Reuse Map lists "plain system-prompt injection for other LLMs" as the fallback path, and the Skills Track requires skills be "loadable by at least 2 different agent harnesses (e.g. Claude Code skill + plain system-prompt injection)." This fallback is well-established:
- A **fallback parser** scans the model's text for JSON objects matching the tool-call format and executes them — covering models without native function calling.
- A **question detector** catches when the model asks instead of acting and re-prompts it to use the tool (a real failure mode for weaker local models).
- The **ReAct** loop (analyze → emit `tool_call` JSON → execute → feed result back) is the portable protocol underneath ([dev.to](https://dev.to/kuroko1t/what-happens-when-local-llms-fail-at-tool-calling-testing-7-models-with-a-rust-coding-agent-cep)).

For freecad-buddy this fallback doubles as the **model-agnosticism proof** the Phase 1 criterion actually wants: a bridge that works via (a) native MCP tool-calling *and* (b) system-prompt-injected ReAct is demonstrably not coupled to any one model's tool API. Build the ReAct/text-parse adapter behind the same tool interface the MCP path uses.

---

## Recommendation — Concrete Second Backend Stack

**Primary recommendation (adopt for Phase 1 exit):**

> **llama.cpp `llama-server` (MCP client, constrained decoding) running Qwen3-30B-A3B-Instruct at Q4_K_M**, connected to the FreeCAD MCP bridge.

Rationale, mapped to Phase 1 exit criteria:
- **Model-agnostic proof (the actual criterion):** llama.cpp is a *different vendor, different transport, fully local* MCP client vs the Claude API path — a clean second backend. Same bridge, no Claude-specific code.
- **Reliable tool calling:** Qwen3 is the most stable local tool-caller (lowest dropped-call rate); constrained decoding drives JSON-format errors to ~0%, decoupling pass rate from model quirks.
- **Latency:** MoE ~73–196 tok/s on a 24 GB GPU → full turn ≪ 15 s median.
- **Hardware realism:** Q4_K_M ≈ 16–19 GB → single RTX 3090/4090; no cloud dependency for the "local model" leg.
- **CI-friendly:** headless `llama-server` pins a GGUF and scripts cleanly for the eval harness (unlike a GUI-first tool).

**Secondary / developer-ergonomics option:** **LM Studio + Qwen3-30B-A3B** for interactive Phase 1/2 work — its per-tool-call confirmation dialog (review/edit arguments before execution) directly implements the intent doc's "human in the loop by default" principle. Use LM Studio for hands-on dev, llama.cpp for the reproducible eval/CI run.

**Fast-demo option:** **Ollama + Qwen3-30B-A3B** if you want a one-command start before wiring llama.cpp; acceptable for the eval, just pin the Ollama version (configs can break between releases).

**Upgrade path (Phase 3–4):** if local planning quality becomes the bottleneck for spec-to-part, move the local leg to **GLM-4.5-Air (INT4)** — top open-weight agentic tool-use, still single-GPU.

**Build regardless of model:** the **system-prompt / ReAct text-parse fallback adapter**, behind the same tool interface. It (a) satisfies the Skills-Track "≥ 2 harnesses" loadability requirement, (b) future-proofs against any model lacking native tool calling, and (c) is itself the cleanest demonstration of model-agnosticism.

**Explicitly not recommended for Phase 1:** vLLM (throughput engine, overkill for single-user), and any sub-8B model (multi-tool reasoning too weak — risks failing the error-diagnosis 8/10 gate).

### Risks & Mitigations (backend-specific)

| Risk | Mitigation |
|---|---|
| Qwen3 tool-call stability regressions between point releases | Pin exact model + harness versions in the CI matrix (already a stated intent-doc discipline); gate upgrades on the eval set |
| Local JSON/tool-format errors inflate failure rate | Enable constrained decoding (llama.cpp grammar / JSON-Schema) — near-0% format errors |
| Long feature-tree prompts blow latency and context | Enforce summarized tree queries (Phase 1 criterion 3); cap context; MoE model keeps headroom |
| Harness churn ("configs break between releases") | Prefer llama.cpp for CI (most stable, most controllable); treat Ollama as convenience only |
| MCP tool-injection surface (Phase 4) | Stay on MCP ≥ v2.1 (mandatory sandboxing); keep typed tools, no free-form exec in mutation path |

---

## Sources

- Ollama — Tool calling docs: https://docs.ollama.com/capabilities/tool-calling
- Ollama — Streaming tool calls blog: https://ollama.com/blog/streaming-tool
- Ollama tool-calling reliability / best models: https://localaimaster.com/blog/ollama-function-calling-tools , https://webscraft.org/blog/yaku-model-ollama-obrati-dlya-agenta-z-tool-calling-porivnyannya-i-benchmarki?lang=en
- mcp-client-for-ollama (jonigl): https://github.com/jonigl/mcp-client-for-ollama
- llama.cpp MCP client merge: https://jasonmoon.dev/blog/2026-04-15-mcp-v21-llama-cpp-local-agents , https://buttondown.com/insiderllm/archive/this-week-in-local-ai-llamacpp-gets-mcp-qwen3/ , https://localaimaster.com/blog/llama-cpp-mcp-server
- llama.cpp vs vLLM (Red Hat): https://developers.redhat.com/articles/2026/06/15/llamacpp-vs-vllm-choosing-right-local-llm-inference-engine
- LM Studio MCP host: https://lmstudio.ai/docs/app/mcp , https://lmstudio.ai/blog/lmstudio-v0.3.17
- BFCL leaderboards (V3/V4): https://llm-stats.com/benchmarks/bfcl-v3 , https://llm-stats.com/benchmarks/bfcl-v4 , https://pricepertoken.com/leaderboards/benchmark/bfcl-v3
- Qwen3-30B-A3B model card + VRAM: https://huggingface.co/Qwen/Qwen3-30B-A3B , https://www.compute-market.com/blog/qwen-3-local-hardware-guide-2026 , https://unsloth.ai/docs/models/tutorials/qwen3-coder-how-to-run-locally
- GLM-4.5-Air specs/VRAM: https://apxml.com/models/glm-45-air , https://www.digitalocean.com/community/tutorials/glm-agentic-reasoning-coding-model
- Local LLM latency benchmarks (RTX 4090): https://mustafa.net/llm-tokens-per-second-benchmarks/ , https://www.hardware-corner.net/gpu-llm-benchmarks/rtx-4090/
- Tool-calling fallback / constrained decoding / ReAct: https://dev.to/kuroko1t/what-happens-when-local-llms-fail-at-tool-calling-testing-7-models-with-a-rust-coding-agent-cep

---

*Prepared for FreeCAD Buddy Phase 1 exit-criteria planning. Primary project reference: `docs/intent.md` (Phase 1 exit criteria; Architecture Direction; Reuse Map).*
