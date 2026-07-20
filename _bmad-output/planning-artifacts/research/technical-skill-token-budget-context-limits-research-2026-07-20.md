---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: ['docs/intent.md', '.claude/skills/**/SKILL.md']
workflowType: 'research'
lastStep: 5
research_type: 'technical'
research_topic: 'Skill token budget vs LLM context limits: loading 12 CAD knowledge skills into agent context'
research_goals: 'Determine the realistic token footprint of the 12-skill Track A+B library, the context limits of candidate local models (mid-2026), a selective loading/routing architecture, long-context degradation risk, and how the ablation harness constrains loading design. Recommend a skill loading architecture + budget. Blocks Skills Track SMART goal and Phase 1/2 ablation harness.'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical — Skill Token Budget vs LLM Context Limits

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** technical (deep dive)

---

## Research Overview

FreeCAD Buddy's `docs/intent.md` commits to a **12-skill Track A+B library** (6 Track A "FreeCAD operating knowledge" + 6 Track B "design thinking") that is "loaded into context" (architecture diagram, line 34) and must be "loadable by at least 2 different agent harnesses" including "one local model" (Skills SMART goal line 124; Phase 1 exit line 217). The intent also mandates an **ablation harness**: "any benchmark can run with a declared skill subset, and reports per-skill deltas" (line 125).

Those three constraints — a fixed 12-document library, a portability requirement onto a local model with a bounded context window, and an ablation harness that must load *arbitrary subsets* — jointly determine the skill loading architecture. This report quantifies the token footprint, sizes it against realistic mid-2026 local-model context budgets, factors in long-context performance degradation ("context rot"), and recommends a loading architecture and budget.

**Methodology.** Two evidence streams: (1) **primary web sources** — Anthropic's Agent Skills engineering post and Claude platform docs (skill format, progressive disclosure, size limits), 2026 open-weights local-model surveys (context windows), and the Chroma "Context Rot" study plus the NoLiMa benchmark (long-context degradation); (2) **local measurement** — actual byte/word counts of the 49 `SKILL.md` files already in this repo's `.claude/skills/` (BMAD workflow skills), used as an empirical size baseline for real-world Claude-Code-format skills, since the FreeCAD Track A/B skills do not yet exist.

---

## Key Findings

### 1. The Claude-Code skill format is explicitly a progressive-disclosure, three-tier loader

Anthropic's Agent Skills design ([Anthropic engineering](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills); [platform docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)) loads skills in three levels:

| Level | What loads | When | Token cost (published guidance) |
|-------|-----------|------|----------------------------------|
| 1 — Discovery | `name` + `description` frontmatter of **every** installed skill | Always, at session start (injected into system prompt) | **~100 tokens per skill** |
| 2 — Activation | The full `SKILL.md` body | Only when the model judges the skill relevant to the task | **up to ~5,000 tokens per skill** (body guidance: < 500 lines / ~1,500–2,000 words) |
| 3 — Execution | Files in `references/`, `scripts/`, `assets/` referenced by the body | On demand, by name, only as needed | Unbounded but pay-per-use |

Two hard format facts: the `description` must be **< 1,024 characters**, and the recommended `SKILL.md` **body is < 500 lines / ~1,500–2,000 words (≈ 5K tokens)**; anything longer is meant to be split into Level-3 companion files ([best-practices docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)). The critical property for us: **"Once a skill loads, its rendered content stays in context for the rest of the session, so every line is a recurring token cost."** Activation is sticky, not transient.

The headline claim of the format — "you can have dozens or even hundreds of skills installed, and the overhead is negligible" — is **only true at Level 1**. It assumes the model activates a *small relevant subset* per task. Our design is exactly the case that stresses that assumption: a domain where *many* skills are plausibly relevant to *every* design task.

### 2. Measured baseline from this repo's real Claude-Code skills

I measured all 49 `SKILL.md` files currently in `.claude/skills/` (BMAD skills — same format the FreeCAD skills will use):

- **Median SKILL.md body: ~640 words (~4.6 KB)** → roughly **850–1,000 tokens**.
- **Typical range: 350–2,000 words** (≈ 470–2,700 tokens); most cluster at **600–950 words**.
- **Outliers exist**: `bmad-retrospective` is 7,539 words (~10K tokens) — 4× over the recommended body cap, i.e. what happens when authors *don't* push detail into Level-3 files.
- **Aggregate across all `*.md` in the skill tree** (bodies + references + assets): ~150,000 words — but that is the whole Level-1/2/3 corpus; only a fraction is ever resident.

**Read-through for the 12 CAD skills:** these skills are content-dense (constraint systems, failure-mode recipes, decision rules, worked examples). Expect each to sit at or *above* the recommended body cap. Plan on **~1,000 tokens (lean) to ~2,500 tokens (rich) per activated Level-2 body**, with Level-3 companions (e.g. `freecad-troubleshooting`'s symptom→cause→fix catalog, `freecad-partdesign`'s per-feature failure tables) holding the long tail.

### 3. Token budget for the 12-skill library — three loading regimes

Using **~100 tokens/skill (Level 1)** and a planning figure of **~2,000 tokens/skill (Level 2 activated body)** for content-rich CAD skills:

| Regime | What's resident | Level-1 cost | Level-2 cost | **Skill total** |
|--------|-----------------|-------------|--------------|-----------------|
| **A. Metadata-only (idle)** | 12 descriptions | 12 × 100 = 1,200 | 0 | **~1.2K tokens** |
| **B. Selective subset (typical design task)** | 12 descriptions + 4 activated bodies | 1,200 | 4 × 2,000 = 8,000 | **~9.2K tokens** |
| **C. All-12 loaded ("brain fully on")** | 12 descriptions + 12 bodies | 1,200 | 12 × 2,000 = 24,000 | **~25.2K tokens** |
| **C-worst.** All-12, rich bodies at ~3K + some Level-3 | | 1,200 | ~36,000 + refs | **~40K+ tokens** |

This skill budget is **on top of** the other resident context: base system prompt, the MCP tool schemas (intent commits to ≥ 15 tools in Phase 0, growing to sketch/feature/verify tools — realistically **5–15K tokens of tool definitions**), the tree-summary/query results, screenshots, and the running conversation. A realistic Phase 2/3 working context is therefore **skills + ~15–30K tokens of everything else**.

**Conclusion:** loading **all 12 skills at ~25–40K tokens is affordable on a 128K-context model in isolation, but it is the single largest fixed cost you control, and it is permanently resident.** The question is not "does it fit" (it fits) but "does it *degrade the model* and *cost per token* enough that selective loading wins" — see Finding 5.

### 4. Local-model context windows in mid-2026 are not the binding constraint — but the *usable* window is smaller than the advertised one

2026 open-weights surveys ([Pinggy](https://pinggy.io/blog/top_5_local_llm_tools_and_models/); [PromptQuorum](https://www.promptquorum.com/local-llms/qwen-vs-llama-vs-mistral); [AceCloud](https://acecloud.ai/blog/best-open-source-llms/)) show candidate local models cluster at **128K, with 256K increasingly common**:

| Model (mid-2026) | Advertised context | Notes for a local-first, single-GPU deployment |
|------------------|-------------------|-----------------------------------------------|
| Qwen 3.5 / 3.6 (27B) | **256K** (up from 128K) | Strong coding (SWE-bench ~77%); fits 24 GB at Q4 — a realistic local pick |
| Mistral Small 4 (24B) | **256K** | Best quality-per-VRAM (~14 GB); multimodal |
| Gemma 4 26B MoE | **256K** | |
| Qwen 3 (all sizes) | 128K | |
| Llama 4 Scout (17B active MoE) | **10M** | Single-GPU deployable; the long-context outlier |

So the *advertised* window (128K minimum, 256K typical) dwarfs even the ~40K worst-case skill budget. **Context capacity is not the wall.** Two caveats make it matter anyway:

- **Local quantization + VRAM shrink the *practical* KV-cache budget.** A 24 GB consumer GPU running a 24–27B model at Q4 spends most of its VRAM on weights; the KV cache for very long contexts competes for the remainder. Running near the full 128K/256K locally is often impractical even when the model "supports" it. Treat **~32–64K as the comfortable working window on a single-GPU local deployment**, not the advertised number.
- **Advertised ≠ usable quality** (Finding 5).

### 5. Long-context degradation ("context rot") is the real reason to load selectively, not capacity

Independent 2025–2026 research shows model *accuracy* degrades well before the context window fills — often at the exact token counts our all-12 regime hits:

- **Chroma "Context Rot"** ([trychroma.com](https://www.trychroma.com/research/context-rot)): performance declines "consistently as input length increases, even when the task remains trivially simple." Substantial gaps appear between **focused (~300-token)** and **full (~113K-token)** prompts on the same task. **Distractors are the mechanism**: even *one* topically-related-but-irrelevant passage measurably lowers accuracy; four compound it. Claude Sonnet 4 shows accuracy loss as input grows from 25 to 10,000 words. Their #1 recommendation: **"Reduce overall length — simple retrieval remains most reliable at shorter input lengths,"** and **"minimize distractors — remove topically-related but incorrect information."**
- **NoLiMa** ([OpenReview](https://openreview.net/forum?id=0OshX1hiSa)): when literal keyword overlap is removed (forcing latent reasoning — exactly what CAD design planning needs), **11 of 13 models drop below 50% of their short-context baseline by 32K tokens.** Even GPT-4o falls from 99.3% → 69.7%.

**Direct implication for the skill library:** a skill that is *loaded but irrelevant to the current task is a distractor.* Loading all 12 CAD skills for a task that only needs `freecad-sketcher` + `sketch-strategy` doesn't just cost ~24K tokens — it actively injects 10 topically-adjacent documents that context-rot research identifies as accuracy-lowering distractors, and it does so most on the **latent-reasoning** tasks (decomposition, tool selection) the skills exist to improve. **On a local model, whose effective long-context quality is typically weaker than frontier models, this penalty is larger.** This is the strongest single argument in the report: **selective loading is not merely a token-cost optimization; on the local backend it is likely a correctness requirement.**

### 6. The ablation harness *requires* declarative, subset-based loading — which conveniently is also the right architecture

Intent line 125: the harness must "run with a declared skill subset, and report per-skill deltas," and line 127 needs a clean A/B ("with vs without the skill loaded"). This forces three properties that happen to be exactly what Findings 1–5 recommend:

1. **Deterministic, externally-declared loading.** For a clean ablation you cannot rely on the *model* deciding whether to activate a skill (Level-2 auto-activation is nondeterministic and confounds the A/B). The harness must **force** a named subset into context and force the complement *out*. This means bypassing model-invoked activation and injecting the chosen skill bodies directly.
2. **Per-skill isolation.** Skills must be independently loadable units with no hidden cross-references at Level 2 (a skill that only works because another skill's body is also present pollutes the delta). Keep shared material in Level-3 files or a small shared preamble, not baked into pairs of bodies.
3. **Backend-agnostic injection.** The same subset must load into both a Claude Code harness (native skill mechanism) and a local model (no native skill loader). The portable common denominator is **direct system-prompt / context injection of the selected `SKILL.md` bodies** — which is what intent line 124 already names ("plain system-prompt injection for other LLMs").

---

## Recommended Architecture: Metadata-First Router + Forced-Subset Ablation Mode

A single loader with **two modes** over one shared skill store.

### Skill store (authoring rules, apply to all 12)
- Each skill = a directory with `SKILL.md` (frontmatter + lean body **≤ 1,500 words / ~2K tokens**) plus `references/` for the long tail (troubleshooting tables, per-feature failure catalogs, worked examples beyond one or two).
- **Descriptions are load-bearing routing metadata**, not marketing. Write each < 1,024-char `description` to state *when to load* in task terms ("Use when creating or editing a sketch, adding constraints, or diagnosing DoF > 0"). The router (and Claude's native activator) route on these; a vague description breaks selective loading.
- No Level-2 cross-skill dependencies (keeps ablation deltas clean — Finding 6.2).

### Mode 1 — Production loading (agent doing real design work): metadata-first selective
1. **Always resident: 12 descriptions only** (Level 1, ~1.2K tokens). Cheap, keeps all skills discoverable.
2. **Route per task to a subset of 2–5 skills.** Two viable mechanisms, pick per backend:
   - *Claude Code backend:* use native model-invoked activation (Level 2) — the descriptions drive it.
   - *Local backend (and when determinism matters):* a lightweight **router step** (rules or a cheap classification pass on the user spec) selects the subset, then the harness injects those bodies. Rule-of-thumb starting map: sketch tasks → `freecad-sketcher` + `sketch-strategy` + `design-intent`; new-part planning → `design-decomposition` + `tool-selection` + `freecad-partdesign`; error triage → `freecad-troubleshooting` + `freecad-scripting-idioms`.
3. **Target resident skill budget: ≤ ~10K tokens** (Regime B: 12 descriptions + ~4 bodies). This keeps total working context (skills + tools + tree summaries + conversation) comfortably inside the **~32–64K practical local window** and well clear of the NoLiMa/context-rot danger zone.
4. Level-3 files load only when the body references them for the specific operation in flight.

### Mode 2 — Ablation harness: forced explicit subset
- Input: an explicit list, e.g. `--skills freecad-sketcher,sketch-strategy` (or `--skills none` for baseline, `--skills all` for full).
- The harness **forces exactly that set** of `SKILL.md` bodies into context (direct injection), disables model-invoked auto-activation (so nothing outside the declared set leaks in), runs the benchmark, records pass-rate + named sub-metrics.
- Per-skill delta = (score with skill in the set) − (score with it removed), holding everything else fixed. This is the mechanism behind SMART exit criteria "≥ 8/12 show measurable lift" and the `design-decomposition` +15pp / `freecad-troubleshooting` ≥ 9/10 targets.
- **Same injection path serves both backends**, satisfying "loadable by ≥ 2 harnesses."

### Budget summary to design against

| Scenario | Skill tokens resident | Fits 128K local? | Fits ~32–64K *practical* local? | Context-rot risk |
|----------|----------------------|------------------|-------------------------------|------------------|
| Metadata-only (idle) | ~1.2K | Yes | Yes | Negligible |
| **Selective 4-skill (recommended production)** | **~9–10K** | Yes | **Yes** | Low |
| All-12 loaded | ~25–40K | Yes | Tight (crowds tools+conversation) | **Elevated — 8+ resident distractors** |
| Ablation "all" run | ~25–40K | Yes | Tight | Acceptable *for measurement only* |

**Do not ship "all 12 always loaded" as the production default.** It is affordable on capacity but pays a context-rot tax precisely on the latent-reasoning tasks the skills target, and worst on the local backend the SMART goal must satisfy. Reserve all-12 loading for the ablation `--skills all` measurement run.

---

## Risks & Open Questions

| Risk / question | Impact | Mitigation / next step |
|-----------------|--------|------------------------|
| CAD skill bodies grow past the ~2K-token cap (like `bmad-retrospective` did at 10K) | Selective budget blows out; all-12 regime hits 40K+ | Enforce body cap in authoring review; push detail to `references/`; add a CI check on SKILL.md word count |
| Router picks the wrong subset → a needed skill is absent | Silent quality loss; confounds "does the skill help?" with "did we load it?" | Log the routed subset per benchmark run; in ablation mode loading is explicit so this only affects production; tune router rules from ablation data |
| Local model's *usable* long-context quality < advertised | All-12 regime degrades more than measured on Claude | Run the context-rot check locally: benchmark the same task at 4-skill vs 12-skill resident load on the target local model; adopt selective if delta is material |
| Model-invoked (Level 2) activation is nondeterministic | Pollutes ablation A/B | Ablation mode bypasses auto-activation entirely (forced injection); only production Mode 1 uses it |
| Level-3 reference files silently balloon resident context when pulled | Unbudgeted spikes | Reference files are per-operation and transient by design; measure worst-case pull in Phase 2 |
| "≥ 2 harnesses" divergence: native Claude activation vs injected local | Same skill behaves differently across backends | Standardize on **forced injection as the common path** for benchmarking both backends; native activation is a production convenience only |

---

## Conclusion & Recommendation

**The 12-skill library fits every candidate context window with room to spare — capacity was never the constraint. The constraint is context rot and per-token cost, and both point to the same design: metadata-first selective loading.**

Concretely:
1. **Budget: ~100 tokens/skill at Level 1 (12 descriptions ≈ 1.2K always resident); plan ~2K tokens per activated Level-2 body.** Author every skill lean (≤ ~1,500 words), push the long tail to `references/`.
2. **Production default = selective subset (2–5 skills, ~9–10K token skill budget)** routed by description metadata, not all-12. This keeps the working context inside the ~32–64K *practical* local window and out of the measured degradation zone.
3. **Reserve all-12 loading (~25–40K) for the ablation `--skills all` run only.**
4. **Build the loader with two modes over one store:** metadata-first router for production, forced-explicit-subset injection for ablation. The forced-injection path is also the portable common denominator that satisfies the ">= 2 harnesses incl. local model" SMART criterion.
5. **This unblocks** the Skills Track SMART goal (subset-loadable, delta-reporting) and the Phase 1/2 ablation harness directly — the ablation rule and the loading architecture are the *same* mechanism, not two.

---

## Sources

- [Equipping agents for the real world with Agent Skills — Anthropic Engineering](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Agent Skills overview — Claude Platform Docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Skill authoring best practices — Claude Platform Docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Extend Claude with skills — Claude Code Docs](https://code.claude.com/docs/en/skills)
- [Context Rot: Evaluating LLM Performance Degradation with Increasing Input Tokens — Chroma](https://www.trychroma.com/research/context-rot)
- [NoLiMa: Long-Context Evaluation Beyond Literal Matching — OpenReview](https://openreview.net/forum?id=0OshX1hiSa)
- [Top 5 Local LLM Tools and Models in 2026 — Pinggy](https://pinggy.io/blog/top_5_local_llm_tools_and_models/)
- [Qwen 3.6 vs Llama 4 vs Mistral: Local LLM Comparison 2026 — PromptQuorum](https://www.promptquorum.com/local-llms/qwen-vs-llama-vs-mistral)
- [Best Open-Source LLMs (Updated July 2026) — AceCloud](https://acecloud.ai/blog/best-open-source-llms/)
- Local measurement: 49 `SKILL.md` files under `D:\Work\Personal\Sources\freecad-buddy\.claude\skills\` (median ~640 words / ~4.6 KB body; range 350–7,539 words).
</content>
</invoke>
