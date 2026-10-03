---
title: 'Skills Library Structure Design'
status: final
date: '2026-07-21'
ad-refs: ['AD-14', 'AD-15', 'AD-12', 'AD-1']
sources:
  - 'docs/intent.md (Skills Library section)'
  - '_bmad-output/specs/spec-freecad-buddy/phase-gates.md (GS)'
  - '_bmad-output/planning-artifacts/research/technical-skill-token-budget-context-limits-research-2026-07-20.md'
---

# Skills Library Structure Design

Implementation-ready design for the `skills/` store, the SKILL.md authoring contract, the two-mode loader (AD-15), the starter routing table, the CI shape check (GS.E / G1.5 / G2.6), and the token budgets. Ablation reporting follows AD-14.

## 1. Directory Layout

One directory per skill, named exactly as cataloged in intent.md. SKILL.md is mandatory; `references/` is optional and holds the long tail (Level-3, loaded on demand only).

```text
skills/
  # Track A — FreeCAD operating knowledge
  freecad-fundamentals/        SKILL.md  references/
  freecad-sketcher/            SKILL.md  references/
  freecad-partdesign/          SKILL.md  references/   # per-feature failure tables live in references/
  freecad-datums-references/   SKILL.md  references/
  freecad-troubleshooting/     SKILL.md  references/   # symptom→cause→fix catalog lives in references/
  freecad-scripting-idioms/    SKILL.md  references/
  # Track B — design thinking
  design-decomposition/        SKILL.md  references/
  sketch-strategy/             SKILL.md  references/
  tool-selection/              SKILL.md  references/
  design-intent/               SKILL.md  references/
  parametric-patterns/         SKILL.md  references/
  verification-thinking/       SKILL.md  references/
  # Track R — robot-description & sourcing (Phase 5, AD-22/AD-23)
  urdf-export/                 SKILL.md  references/
  sdf-export/                  SKILL.md  references/
  part-sourcing/               SKILL.md  references/
```

Rules:

- Directory name == frontmatter `name` (CI-checked). The Phase-5 Track R skills (robot-description/sourcing, AD-22/AD-23) join the same layout; a later Track C (domain judgment, Phase 4/5) would too. The catalog is Track A+B, the three Track W workflow skills (`design-loop`, `visual-review`, `spec-to-assertions`), plus these — the router's resident-description count and the budget table grow with it.
- `references/` files are per-operation and transient: a body may point to its **own** `references/` files by relative path, never to another skill's directory (AD-15: no cross-skill *path* dependency; the §6 check forbids any `references/` link escaping the skill's own dir). A body may still name a sibling skill in prose as a routing pointer (AD-15) — that is not a path dependency.
- A skill directory may carry **read-only helper scripts** under `scripts/` — geometry checkers, assertion evaluators, report formatters — run by the driving agent's own shell, never by the bridge (AD-15). Three limits apply: a helper reads and computes but never mutates (no document mutation, and no writes outside the AD-25 run workdir); a helper contains no model call and no credential; and a helper answers one question per invocation and never decides the next action. Anything that decides the next action is the loop, and the loop lives in the agent (AD-35).
- The store is consumed by the external-process loader only (AD-15 binds skills library + agent harnesses); nothing under `skills/` is imported by in-FreeCAD code (AD-12 untouched).

## 2. SKILL.md Template

Frontmatter + exactly four H2 body sections in fixed order (AD-15). Body ≤1,500 words; the `check_skill_shape.py` CI check that enforces this is **not yet built** (Story 6.1) — until it lands the cap is convention only (§6).

```markdown
---
name: freecad-sketcher
track: A
description: >-
  Use when creating or editing a sketch, adding or fixing constraints,
  driving a sketch to fully-constrained (DoF = 0), choosing geometry vs
  construction geometry, or attaching external references. Covers the
  constraint solver's behavior, redundant vs conflicting constraints, and
  the risks of external-geometry references. Do NOT use for feature
  operations on solids (see freecad-partdesign) or for planning which
  sketches a part needs (see sketch-strategy).
version: 0.1.0
freecad-versions: ['1.1']
---

## Scope

One short paragraph: what this skill teaches, what it explicitly does not
cover, and which task types trigger it. No FreeCAD lore yet — boundary only.

## Decision Rules

The judgment core. Imperative if/then rules an agent can apply directly:
"Constrain construction geometry first; dimension what the spec states,
derive the rest." Each rule carries its *why* in one clause. This section
is what the ablation must prove earns its tokens.

## Worked Examples

1–2 complete, small examples showing the rules applied end-to-end
(task → reasoning → tool calls → verification read). More examples go in
`references/`, linked by relative path from here.

## Anti-Patterns

Named traps with symptom and correction: what a naive agent does, why it
fails (recompute error, TNP break, unconstrained sketch), what to do
instead. Sourced from FreeCAD community lore and our own benchmark
failure analyses (intent.md: every Phase 2/3 failure feeds a skill).
---
```

Frontmatter fields:

| Field | Req. | Rule |
| --- | --- | --- |
| `name` | yes | == directory name; kebab-case |
| `track` | yes | `A` \| `B` \| `R` (robot-description/sourcing, Phase 5); a later `C` (domain judgment) reserved |
| `description` | yes | <1,024 chars; routing metadata per §3 |
| `version` | yes | semver; bumped on any body change (ablation results cite skill versions — a delta measured on 0.1.0 is not evidence for 0.2.0) |
| `freecad-versions` | yes | versions the content was accuracy-reviewed against (GS.5 owner review is version-pinned; matches the CI FreeCAD build, AD-11) |

Section-order and heading names are exact (`Scope`, `Decision Rules`, `Worked Examples`, `Anti-Patterns`) — the CI check matches them literally.

## 3. Description-Writing Rules (load-bearing routing metadata)

Descriptions are the router's only input in production Level-1 state and drive native Claude activation. A vague description silently breaks selective loading — treat these rules as part of the skill's correctness, reviewed at GS.5.

1. **Lead with "Use when …" in task terms** the agent will actually see in a spec or command: operation names, error text, artifact types ("diagnosing a recompute error", "adding a fillet", "DoF > 0"). Not topic labels ("about sketching").
2. **State the negative boundary** with a pointer: "Do NOT use for X (see other-skill)". The description is the *primary* home for cross-skill routing (Level-1 metadata, so it never pollutes ablation deltas). A body **may also** name a sibling skill in prose as a routing pointer (AD-15 — all catalogued skills ship together); keep such in-body pointers minimal and to disjoint-scope siblings so the coupling stays negligible.
3. **Enumerate 3–6 concrete trigger phrases**, chosen to be disjoint across the catalogue where possible; overlap is allowed only where co-loading is intended (e.g. `freecad-sketcher` + `sketch-strategy`).
4. **No claims of quality or importance** ("essential", "comprehensive") — routers don't read marketing, and every wasted character crowds out a trigger term (<1,024-char hard cap).
5. Description edits are version bumps: routing behavior is measurable behavior.

## 4. Loader Design

One loader component (`adapters/skills_loader` per the spine's structural seed — external process, third-party deps allowed per AD-12) with two modes over the single store (AD-15).

### 4.1 Production mode — metadata-first router

**Resident always:** one `name` + `description` pair per catalogued skill (15 core (Track A+B+W), 18 with the Phase-5 group; Level 1). **Routed per task:** 2–5 SKILL.md bodies, ≤~10K total skill budget (AD-15). The routed subset is logged on every run (AD-15: "routed subset logged") — this is what lets production quality issues be traced to "skill absent" vs "skill wrong".

Routing mechanism is per backend:

| Backend | Mechanism |
| --- | --- |
| Claude Code / Claude API | Native model-invoked activation: descriptions resident at Level 1; the model activates bodies itself. Loader's job is only to install the store and log which bodies activated. |
| Local model (llama.cpp, no native skill loader) | Explicit **router step** before the task: deterministic rule table (§5) evaluated against the task text/spec; matched bodies injected into the system prompt by the same injection code path ablation mode uses. Router falls back to the task-type default row when no rule fires; it never injects more than 5 bodies. |

The injection path is the portable common denominator (AD-15: "the injection path is the portable second-harness mechanism") — it is one function, shared by local-backend production and ablation mode, satisfying GS.1's dual-path load requirement.

Level-3 `references/` files load only when a resident body cites them for the operation in flight, and are dropped from context after the operation where the harness controls context (local backend); their pull cost is measured in Phase 2 (research risk table).

### 4.2 Ablation mode — forced explicit subset

Requirements (AD-15, GS.2, GS.E):

- **Input:** explicit skill list. CLI shape: `--skills freecad-sketcher,sketch-strategy` | `--skills none` (baseline) | `--skills all` (measurement-only regime; never a production default).
- **Forced injection:** exactly the declared bodies are injected into context; **auto-activation is disabled** on backends that have it (Claude: the native store is not installed for the run; injection only). The complement is provably absent — the harness asserts post-run that no undeclared skill body text appears in the transcript (GS.2 pass rule: "declared subset in, complement out").
- **Determinism:** injection order = catalog order (Track A then B, alphabetical within track); identical bytes per run; skill `version`s recorded in the run report.
- **Reporting:** per-skill paired deltas in AD-14 format — exact McNemar two-sided p<0.05 AND Wilson 95% CI on the paired difference excluding 0; R per AD-14 (R=5 dev, R≥10 sealed/pp-claims); majority-of-R scoring; below-detection effects reported as "below detection at this n", never as failures. The `design-decomposition` +15pp claim runs only on its dedicated n≥40 paired set (AD-14, GS.6).
- Level-3 references remain available to declared skills (they are part of the skill under test); a skill whose lift depends on its own `references/` is fine — one that depends on another skill's is a §6 violation.

## 5. Starter Routing Table (rule-of-thumb)

Initial rule table for the local-backend router. **Status: starter default** — the spine defers final router rules to tuning from ablation data ("Skill router rules" row, Deferred table); this table is the seed those tunings replace, and forced-subset ablation mode is unaffected by any of it.

| Task type (trigger signals) | Routed subset |
| --- | --- |
| Sketch create/edit/constrain ("sketch", "constraint", "DoF") | `freecad-sketcher`, `sketch-strategy`, `design-intent` |
| New-part planning from spec ("design a…", full-part spec text) | `design-decomposition`, `tool-selection`, `freecad-partdesign`, `verification-thinking` |
| Single feature op ("pad", "pocket", "fillet", "hole", "pattern") | `freecad-partdesign`, `tool-selection` |
| Error triage ("recompute error", "failed", broken document) | `freecad-troubleshooting`, `freecad-scripting-idioms` |
| Reference/datum work ("datum", "attach", "reference", TNP flags) | `freecad-datums-references`, `freecad-fundamentals` |
| Parametrize/edit-robustness ("parameter", "VarSet", "spreadsheet", "make it editable") | `parametric-patterns`, `design-intent` |
| Post-build check ("verify", "measure", "does it match the spec") | `verification-thinking` |
| Fallback (no rule fires) | `freecad-fundamentals`, `tool-selection` |

Rules match on task text; multiple matches union their subsets, capped at 5 bodies (drop lowest-priority row's extras; row order above is priority order).

## 6. CI Shape Check

> **Status: `scripts/check_skill_shape.py` is NOT yet built** (Story 6.1, AD-15). Everything in this section is the specification *for* that script. Until it lands every rule below is convention only, held by review rather than by CI — including the word cap, which currently passes by luck (all 15 bodies measure well under it).

One script (external process, to run in the existing CI workflow), blocking on the 1.1.x CI leg. It backs GS.E ("skill shape check wired into CI"), G1.5, and G2.6. Per SKILL.md:

| Check | Rule | Source |
| --- | --- | --- |
| Frontmatter | All §2 fields present; `name` == dir name; `description` <1,024 chars | format hard cap |
| Body word count | ≤1,500 words (frontmatter excluded) | AD-15 |
| Four sections | Exactly the four H2s of §2, in order, each non-empty | AD-15 |
| No cross-skill code deps | Body contains no path into another skill's directory (`references/` links resolve within own dir). A body **may** name a sibling skill in prose (AD-15 — routing pointer, not a dependency); the check does NOT flag sibling names. It still flags any `references/` link or file path that escapes the skill's own dir. | AD-15 |
| Description shape | Contains "Use when" (case-insensitive) | §3 item 1, lint-level warn→error at GS.1 |

Failure output names the file, the rule, and the measured value (word count, offending link). The check is pure text analysis — no FreeCAD, no LLM — so it runs in seconds on every push.

## 7. Token Budget Table

Planning figures from the research report (~100 tokens/description, ~2K tokens per activated CAD-density body); the ≤~10K production budget is the AD-15 bound.

| Regime | Resident | Skill tokens | Bound / status |
| --- | --- | --- | --- |
| Idle (Level 1 only) | 15 descriptions | ~1.2K | Always-on floor |
| **Production routed (default)** | 12 descriptions + 2–5 bodies | ~5–10K | **≤~10K hard budget (AD-15)**; keeps total working context inside the ~32–64K practical local window |
| Ablation `--skills none` | nothing | 0 | Baseline leg |
| Ablation typical subset | declared 1–3 bodies | ~2–6K | Per-skill delta runs |
| Ablation `--skills all` | all bodies (15 core) | ~25K (cap-compliant) to ~40K (if bodies bloat) | Measurement only — never production (context-rot distractor cost); the §6 word cap is what keeps this at the ~25K end |

Budget guard: once built, the shape check's 1,500-word cap will be the enforcement mechanism for every row — a skill that outgrows it moves content to `references/`, not past the cap.

## 8. Conflicts & Notes

- **No AD conflicts.** This design instantiates AD-15 directly and inherits AD-14 for all delta reporting.
- **Deferred honored:** final router rules stay deferred per the spine; §5 is explicitly a starter seed.
- **Intent.md nuance:** intent's SMART goal says skills are "loaded into context" — per AD-15 and the token-budget research, production loads a routed subset, never the whole catalogue; `--skills all` exists solely so the ablation harness can measure that regime.
