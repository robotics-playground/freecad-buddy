---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: ['docs/intent.md']
workflowType: 'research'
lastStep: 5
research_type: 'technical'
research_topic: 'Statistical rigor for small-n LLM agent benchmarks (20-40 cases): defining measurable margins'
research_goals: 'Define statistically defensible margins, repeat counts, confidence-interval methods, and paired-comparison tests for the intent doc''s 20-50-case benchmarks and the 15-percentage-point skill-ablation criterion.'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Statistical Rigor for Small-n LLM Agent Benchmarks

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** technical

---

## Research Overview

**The problem.** `docs/intent.md` judges every phase on benchmarks of 20-50 cases (Phase 1: 50 questions + 10 error cases; Phase 2: 40 commands; Phase 3: 20 specs; Phase 4: 20 specs + 15 revisions; Skills track: ablation deltas). It requires that a skill "improve the pass rate ... by a **measurable margin**" (intent §"How skills are validated"), and it pins one hard number: `design-decomposition` must lift Phase 3 first-plan success by "**≥ 15 percentage points** with the skill loaded vs without" (intent exit criteria). But "measurable margin" is never defined, no repeat count is specified, and no confidence-interval or significance method is named. At n=20-50 with a stochastic LLM agent, a difference of a few cases is inside the noise — so as written, the ablation rule and several phase exit judgments are not decidable.

**This document delivers.** (1) The run-to-run variance reality for agent benchmarks and how many repeats are needed; (2) which confidence interval to report for a small-n pass rate (Wilson); (3) which test decides an ablation (exact McNemar on paired cases); (4) computed minimum detectable effects at n=20/40/50 — including the finding that **the intent's +15pp criterion is undetectable at n=20 and marginal at n=50**; (5) a concrete reporting format and a set of drop-in edits for the intent doc.

**Methodology.** Primary sources: Anthropic/Evan Miller *Adding Error Bars to Evals* (arXiv:2411.00640) for the eval-as-experiment framework, paired-difference analysis, and power analysis; ReasonBENCH (arXiv:2512.07795) for measured agent run-to-run variance; the binomial-proportion CI literature (Wilson vs Clopper-Pearson) for small-n interval choice; and the McNemar paired-test literature for ablations. All effect-size, CI, and power numbers below were computed directly (exact binomial / Wilson closed form) and are reproducible from the formulas given.

---

## Technical Research Scope Confirmation

**Research Topic:** Statistical rigor for small-n LLM agent benchmarks (20-40 cases): defining measurable margins
**Research Goals:** Turn "measurable margin" and the 15-pp skill criterion into statistically defensible, computable rules; recommend repeat counts, CI method, paired test, and a reporting format for the intent's benchmarks.

**Scope covered:**
- Run-to-run variance of LLM agent benchmarks and required repeat counts
- Confidence intervals for small-n pass rates (Wilson vs Clopper-Pearson vs Wald)
- Paired comparison tests for ablations (McNemar, exact vs asymptotic)
- Minimum detectable effect (MDE) at n = 20 / 40 / 50
- Published LLM-eval-statistics guidance (Anthropic error-bars work; eval-variance papers)
- A concrete margin definition, repeat protocol, and reporting format for the intent

**Scope Confirmed:** 2026-07-20 (autonomous run — scope taken from the provided research goals; no interactive confirmation gate).

---

## Key Findings (Executive Summary)

1. **Single-run agent scores are noisy enough to flip rankings.** ReasonBENCH (30 trials × 12 models × 6 tasks) found the best strategy wins only **77% of head-to-head runs** against its nearest competitor; run-to-run variability is "often large enough to change model/method rankings relative to single-run averages" (arXiv:2512.07795). A single benchmark run is therefore not a measurement — it is one draw from a distribution.

2. **Report a Wilson score interval, not a bare pass rate.** For n = 20-50 with proportions near 0.7-0.85, the **Wilson score interval** gives near-nominal coverage while staying tighter than the conservative Clopper-Pearson exact interval; the Wald/normal interval is unsafe this small. A single 20-case run at 70% has a Wilson 95% CI of roughly **[0.48, 0.85]** — a ±19pp band. That band *is* the honest answer to "how measurable is this."

3. **Decide ablations with the exact McNemar test on paired cases, not by comparing two pass rates.** Because the with-skill and without-skill runs use the *same* cases, the paired test removes case-difficulty variance and looks only at the cases the skill flips (Anthropic Rec. #4; McNemar literature). Only the *discordant* cases (skill fixes vs skill breaks) carry signal.

4. **Computed MDE (this report):** with a clean paired design (skill only helps, ≥1 case regresses rarely), the smallest **net** improvement that reaches two-sided p < 0.05 by exact McNemar is: **+30pp at n=20, +15pp at n=40, +12-14pp at n=50.** With realistic regressions it is worse. **The intent's headline +15pp criterion is NOT statistically detectable at n=20 (best-case exact p = 0.25); it is exactly on the significance boundary at n=40 and only comfortably clears at n≈50+.**

5. **Concrete recommendations.** (a) Define "measurable margin" as **exact-McNemar two-sided p < 0.05 AND a Wilson 95% CI on the paired difference that excludes 0**, not a raw pass-rate gap. (b) Run **each benchmark case R = 5 repeats** (R = 3 minimum for cheap phases, R ≥ 10 for the sealed held-out exit run and for the 15pp skill claim); score a case as pass on **majority-of-R** for pass-rate reporting and record per-repeat outcomes for variance. (c) For the `design-decomposition` +15pp claim specifically, **raise its ablation set to n ≥ 40** (ideally 50) or restate it as an effect that is achievable and testable at n=20 (needs ~+30pp) — as written on Phase 3's 20-spec set it cannot be proven. (d) Adopt the reporting template in this doc for every phase-exit and ablation result.

---

## 1. Run-to-Run Variance: Why One Run Is Not a Measurement

LLM agents are stochastic (sampling temperature, tool-call ordering, non-determinism in the environment). The eval literature now treats a benchmark score as **an experiment**, i.e. a sample from a distribution over possible questions *and* possible runs, not a fixed property of the system (Anthropic/Miller, arXiv:2411.00640).

**Measured magnitudes:**
- **ReasonBENCH** (arXiv:2512.07795): 30 independent trials per cell; run-to-run variability is "substantial, benchmark-dependent, and often large enough to change model/method rankings." Best strategy wins only 77% of head-to-head runs vs its nearest rival — meaning a single run silently misranks systems ~1 time in 4. Variance is *structured*: a hierarchical decomposition attributes ~three-quarters of score variance to benchmark/system/item structure, with a residual "run noise" that single-run evaluation silently absorbs.
- Practitioner guidance for **browser/tool agents** converges on **5-10 runs per task** to capture variance, and **20+ for noisy or production-critical flows** (humanbrowser.cloud, 2026). GIS-agent benchmarking uses a **3-run baseline** for stable rankings. Aggregating run-noise across ~50 tasks tightens bootstrap CIs to roughly ±0.02-0.05, but *cell-level* single-run conclusions shift by similar margins in either direction.

**Implication for this project.** FreeCAD Buddy's benchmarks (20-50 cases) are *smaller* than the 50-task aggregations above, so single-run noise is *larger* relative to the score. The variance is also concentrated in a minority of unstable cases (a spec the agent sometimes plans right, sometimes wrong), which is exactly where an ablation delta of "2 more cases passed" can be pure noise. **Repeats are not optional for a project whose central risk (intent §Validation-First Discipline) is "the agent believing it did well when it did not."**

### How many repeats?

Repeating each case R times and averaging shrinks the standard error of the mean pass rate. Treating repeats as (approximately) independent Bernoulli draws, SE(mean) ≈ √(p(1-p)/(nR)). At p = 0.75:

| n  | R=1 SE / 95% halfwidth | R=3 | R=5 | R=10 |
|----|------------------------|-----|-----|------|
| 20 | 9.7pp / ±19pp | 5.6pp / ±11pp | 4.3pp / ±8.5pp | 3.1pp / ±6pp |
| 40 | 6.8pp / ±13pp | 4.0pp / ±7.7pp | 3.1pp / ±6pp | 2.2pp / ±4.2pp |

(This is an upper bound on precision — it ignores within-case correlation across repeats, so real gains are somewhat smaller. Anthropic Rec. #3: resample answers per question and use the question-level average as the input; the Inspect framework's `epochs` parameter does exactly this.)

**Recommendation:**
- **R = 5 repeats per case** as the project default (good variance/cost trade-off; halves the n=20 error band vs a single run).
- **R = 3** allowed for the cheapest, fastest phases (Phase 1 answer eval) where cost dominates.
- **R ≥ 10** for (a) the sealed held-out exit run of each phase and (b) any skill-ablation claim that must clear a specific pp threshold (the 15pp `design-decomposition` claim, the `freecad-troubleshooting` 9/10 claim).
- **Report the per-repeat pass distribution**, not just the mean — per ReasonBENCH, the *spread* is itself a result (a skill that makes the agent more *consistent* at the same mean is still a real win).

---

## 2. Confidence Intervals for a Small-n Pass Rate

A pass rate k/n is a binomial proportion. Three candidate intervals:

- **Wald / normal approximation** (`p ± 1.96·√(p(1-p)/n)`): **do not use** at n ≤ 50. It undercovers badly near 0 and 1 and can produce bounds outside [0,1]. Most "±X%" numbers quoted casually are Wald and are wrong here.
- **Clopper-Pearson exact**: guarantees ≥ nominal coverage but is **conservative** — coverage of a "95%" interval can sit near 99%, so the interval is wider than necessary. Use only when a guaranteed-coverage floor is contractually required.
- **Wilson score interval**: near-nominal coverage even at n = 10-20 and near the 0/1 boundaries; tighter than Clopper-Pearson. **Recommended default** (binomial-proportion CI literature; Wikipedia "Binomial proportion confidence interval"; Statistics-How-To; TDS "Five Confidence Intervals for Proportions").

**Wilson formula** (95%, z = 1.96), for k passes of n:

```
center = (p + z²/2n) / (1 + z²/n)
half   = (z / (1 + z²/n)) · √( p(1-p)/n + z²/4n² )
CI     = center ± half,   where p = k/n
```

**Computed Wilson 95% CIs (this report):**

| n  | p    | Wilson 95% CI     | ± halfwidth |
|----|------|-------------------|-------------|
| 20 | 0.70 | [0.48, 0.85]      | ~19pp |
| 20 | 0.85 | [0.64, 0.95]      | ~15pp |
| 40 | 0.70 | [0.55, 0.82]      | ~14pp |
| 40 | 0.85 | [0.71, 0.93]      | ~11pp |
| 50 | 0.70 | [0.56, 0.81]      | ~12pp |
| 50 | 0.84 | [0.71, 0.92]      | ~10pp |

**Reading these for the intent's gates.** Phase 3 requires "≥ 70%" on 20 specs. A run scoring exactly 70% (14/20) has a Wilson CI of [0.48, 0.85] — the true rate could be below 50%. So **"passed the gate" on a single 20-case run at threshold is not evidence the true capability is ≥ 70%.** Two fixes, both recommended: (a) run repeats (Section 1) to tighten the band; (b) judge the gate on the **lower Wilson bound clearing a margin below threshold**, or accept the threshold as "point estimate ≥ target" while *reporting* the CI so the reader sees the uncertainty. The intent already mandates reporting validator sensitivity next to every score (§Principle 3); it should mandate reporting the Wilson CI next to every pass rate the same way.

---

## 3. Paired Comparison for Ablations: Exact McNemar

The ablation compares the *same* benchmark cases **with** vs **without** a skill. This is **paired binary data**, and the correct test is **McNemar's test**, not a two-sample comparison of the two pass rates (Anthropic Rec. #4 "analyze paired differences"; McNemar literature — Raschka 2018; Howard 2024).

**Why paired, not two-proportion.** The same cases seen by both configurations means case difficulty cancels out. Only the **discordant** cases matter — the 2×2 table:

```
                        with-skill PASS   with-skill FAIL
baseline PASS                a                 b   (skill BROKE these)
baseline FAIL                c                 d   (skill FIXED these)
```

`a` and `d` (both agree) carry no information about the *difference*. The test asks: among the b+c cases the skill flipped, are the fixes (c) significantly more than the breaks (b)? Comparing raw pass rates instead throws away this pairing and needs a far larger n to see the same effect.

**Use the EXACT (binomial) McNemar test, not the chi-square asymptotic version**, because b+c (discordant count) will be tiny at n=20-50. Exact test: under H₀, c ~ Binomial(b+c, 0.5); two-sided p = 2·P(X ≤ min(b,c)).

**Computed significance thresholds (this report, two-sided p<0.05):**

| discordant pattern | exact p | significant? |
|--------------------|---------|--------------|
| 5 fixes, 0 breaks  | 0.0625  | **no** (just misses) |
| 6 fixes, 0 breaks  | 0.0312  | **yes** |
| 7 fixes, 0 breaks  | 0.0156  | yes |
| 8 fixes, 1 break (net +7) | 0.039 | yes |
| 10 fixes, 2 breaks (net +8) | 0.039 | yes |
| 12 fixes, 3 breaks (net +9) | 0.035 | yes |

**Key rule of thumb:** with **zero regressions**, a skill needs to fix **≥ 6 cases the baseline missed** to be statistically significant. Every regression the skill introduces raises that bar by ~2 fixes.

---

## 4. Minimum Detectable Effect at n = 20 / 40 / 50

Combining Section 3's exact-McNemar thresholds with each benchmark size gives the **smallest net pass-rate improvement provable at that n** (best case: all improvement is discordant, zero regressions):

| n  | min discordant fixes for p<0.05 | net pp improvement that = significance |
|----|--------------------------------|----------------------------------------|
| 20 | 6 | **+30pp** (6/20) |
| 40 | 6 | **+15pp** (6/40) |
| 50 | 6 | **+12pp** (6/50) |

(With regressions, shift each up: e.g. n=20 needs +35-40pp net once a couple of cases break.)

### The intent's +15pp `design-decomposition` criterion — verdict

The intent requires `design-decomposition` to lift Phase 3 first-plan success by **≥ 15pp on the 20-spec benchmark**. Computed exact-McNemar result:

| n  | +15pp equals | best-case exact McNemar p | detectable? |
|----|--------------|---------------------------|-------------|
| **20** | 3 net cases | **p = 0.25** | **NO — nowhere near significant** |
| 40 | 6 net cases | p = 0.031 | yes (just clears) |
| 50 | ~8 net cases | p = 0.008 | yes (comfortable) |

**On Phase 3's own 20-spec set, a +15pp lift is 3 cases — a coin-flip-level result that cannot be distinguished from noise (p = 0.25).** This is a direct contradiction inside the intent: the criterion is unprovable on the benchmark it is attached to. Three ways to resolve (pick one, Section 6):
1. **Raise the ablation n to ≥ 40** (ideally 50) for this specific claim — then +15pp becomes exactly the MDE (n=40) or comfortably detectable (n=50).
2. **Restate the threshold to the n=20 MDE** — require ~+30pp (6 of 20 specs fixed, 0 regressions) if the 20-spec set is fixed. This is a large, arguably unrealistic ask.
3. **Run heavy repeats (R≥10) and evaluate on the per-repeat paired outcomes**, expanding the effective paired sample; this is a partial mitigation but does not fully substitute for more distinct cases.

The same MDE table applies to *every* ablation in the Skills track: **on a 20-case set, only skills that move ≥ 6 cases (≥ 30pp) can be called "measurable"; on a 40-case set the floor drops to ≥ 15pp; on 50 cases, ~12pp.** Skills with genuine but small effects (< these floors) are real but **unprovable at these sample sizes** — the honest report is "effect below detection threshold at this n," not "no effect."

### Power note

Anthropic Rec. #5 frames this as power analysis: to *reliably* (80% power, not just 50%) detect an effect, you need meaningfully more than the bare-significance n above. The tables here give the **significance boundary** (the effect that *just* reaches p<0.05 if it lands perfectly); to have 80% power to detect a true +15pp effect, n=40 is underpowered and n≈60-100 paired cases is the honest target. This reinforces recommendation (a): where a specific pp threshold must be *proven*, size the set for power, not just for point-estimate significance.

---

## 5. Recommended Reporting Format

Every phase-exit and every ablation result should report this block (extends the intent's existing "score + validator sensitivity" rule):

**For a single pass rate (phase gate):**
```
Phase 3 held-out: 15/20 passed = 75.0%
  Wilson 95% CI: [53.1%, 88.8%]        <- honest uncertainty band
  Repeats: R=10 per case; per-case pass distribution attached
  Validator sensitivity: 96% (per intent §Principle 3)
  Verdict vs "≥70%" gate: point estimate clears; lower CI bound 53% < 70% -> flagged low-confidence, N too small for a firm claim
```

**For an ablation (skill on vs off), the load-bearing format:**
```
Skill: design-decomposition | Benchmark: Phase 3 first-plan success | n=40 paired specs, R=10
  Without skill: 22/40 (55.0%)
  With skill:    30/40 (75.0%)   -> +20.0pp raw
  Paired 2x2: agree-pass=20, agree-fail=8, skill-fixed(c)=10, skill-broke(b)=2
  Net discordant: +8  | Exact McNemar two-sided p = 0.039  -> SIGNIFICANT
  Wilson 95% CI on paired difference: [+3pp, +34pp] (excludes 0)
  VERDICT: measurable margin met (p<0.05 AND CI excludes 0)
```

**Rules baked in:**
- Always report **n, R, the 2×2 discordant table, exact McNemar p, and a paired-difference CI**.
- "Measurable margin" = **exact McNemar p < 0.05 AND paired-difference 95% CI excludes 0**. A raw pp gap alone is never sufficient.
- If discordant count < 6, state explicitly: **"effect below detection threshold at this n"** — do not report the raw gap as a win or a loss.
- Report the **per-repeat spread**; a consistency improvement at equal mean is a reportable result.

---

## 6. Concrete Edits for `docs/intent.md`

1. **Define "measurable margin"** in §"How skills are validated (the ablation rule)". Replace "improve the pass rate ... by a measurable margin" with: *"improve the pass rate (or named sub-metric) such that a **paired exact McNemar test on the same cases gives two-sided p < 0.05 and the 95% Wilson CI on the paired difference excludes zero**. Skills whose effect is below the detection threshold for the benchmark's n are reported as 'below detection at this n', not as failures, and are candidates for testing on a larger set."*

2. **Fix the +15pp `design-decomposition` contradiction** (Skills-track exit criteria). Either (a) change "Phase 3 benchmark" to a **dedicated ≥ 40-spec (ideally 50) `design-decomposition` ablation set** — because +15pp on the 20-spec set is undetectable (exact p = 0.25); or (b) if the 20-spec set must be reused, raise the threshold to **≥ +30pp (≥ 6 of 20 specs)**, which is the true n=20 detection floor. Option (a) is recommended.

3. **Add a repeats rule** to §Validation-First Discipline (new principle): *"Every benchmark case is run R times (R=5 default; R=3 for Phase 1 answer eval; R≥10 for the sealed held-out exit run and for any ablation asserting a specific pp threshold). Pass rate is majority-of-R; the per-repeat pass distribution is reported alongside the mean."*

4. **Add a CI-reporting rule** parallel to the existing sensitivity rule (§Principle 3): *"Every reported pass rate is accompanied by its Wilson 95% confidence interval. A phase gate judged near threshold on a single small-n run is flagged low-confidence."* Note the Phase 1 "≥ 8 of 10" error-diagnosis and `freecad-troubleshooting` "≥ 9/10" criteria are **n=10** — a one-case change (8→9) is not significant (Wilson CI for 9/10 is [0.56, 0.99]); either enlarge that set to ~20-30 error cases or treat 9/10 as a soft target with the CI reported.

5. **Cross-reference the MDE table** in the Skills-track SMART goal so future skills are scoped to move ≥ 6 cases on whatever benchmark validates them, and skill-validating benchmarks default to n ≥ 40 where a specific pp claim is made.

---

## Sources

**Primary:**
- Evan Miller / Anthropic — *Adding Error Bars to Evals: A Statistical Approach to Language Model Evaluations*, arXiv:2411.00640 (Nov 2024). [Blog](https://www.anthropic.com/research/statistical-approach-to-model-evals) · [arXiv](https://arxiv.org/abs/2411.00640) — eval-as-experiment; SEM/CLT; clustered SEs; within-question resampling (Inspect `epochs`); paired-difference analysis; power analysis for question count.
- *ReasonBENCH: Benchmarking the (In)Stability of LLM Reasoning*, arXiv:2512.07795 (Dec 2025). [arXiv](https://arxiv.org/abs/2512.07795) · [HTML](https://arxiv.org/html/2512.07795v1) — 30-trial protocol; best strategy wins only 77% head-to-head; variance decomposition; single-run misranking.

**Confidence intervals (binomial proportion):**
- [Binomial proportion confidence interval — Wikipedia](https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval) — Wilson vs Clopper-Pearson vs Wald coverage.
- [Wilson CI — Statistics How To](https://www.statisticshowto.com/wilson-ci/); [Five Confidence Intervals for Proportions — Towards Data Science](https://towardsdatascience.com/five-confidence-intervals-for-proportions-that-you-should-know-about-7ff5484c024f/) — Wilson recommended for small n / boundary proportions; Clopper-Pearson conservative.
- [Confidence Intervals for the F1 Score, arXiv:2309.14621](https://arxiv.org/pdf/2309.14621) — CI method comparison in ML metric context.

**Paired comparison / McNemar:**
- Raschka — *Model Evaluation, Model Selection, and Algorithm Selection in Machine Learning*, arXiv:1811.12808 / [blog part 4](https://sebastianraschka.com/blog/2018/model-evaluation-selection-part4.html) — McNemar for paired classifier comparison, exact vs chi-square.
- [Howard — McNemar's Test: The Hidden Gem for Paired Binary Data (2024)](https://jameshoward.us/2024/12/17/mcnemars-test-the-hidden-gem-for-paired-binary-data).

**Power / MDE / variance (agents):**
- [Sample Size, MDE & Power — M. Brenndoerfer](https://mbrenndoerfer.com/writing/sample-size-minimum-detectable-effect-power-analysis-mde-underpowered-studies); [Two-proportion Z-test — Wikipedia](https://en.wikipedia.org/wiki/Two-proportion_Z-test).
- [Benchmarking LLM browser agents 2026 — humanbrowser.cloud](https://humanbrowser.cloud/blog/benchmark-llms-browser-agents-2026) — 5-10 runs/task, 20+ for noisy flows.

**Computed values** (Wilson CIs, exact-McNemar p-values, MDE tables, repeat-SEM table) were derived directly from the closed-form Wilson and exact-binomial McNemar formulas stated in this document and are reproducible.

---

*Autonomous technical-research run for freecad-buddy. Interactive scope/continuation gates skipped per run instructions; all five research phases (scope, overview, deep-dive on variance/CIs/paired-tests, MDE computation, synthesis) completed non-interactively.*
