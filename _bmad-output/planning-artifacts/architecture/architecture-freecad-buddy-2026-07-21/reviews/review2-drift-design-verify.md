# Drift Re-Review — Verification / Validation / Skills / Service / Phase-5 Axis

**Lens C, pass 2.** Re-review after a prior fix pass. Every claim below is checked against the
current text of the file named. Quoted text is verbatim.

**Documents read completely:**

- `docs/intent.md` (repo root — **not** under the architecture base dir; see F-01)
- `ARCHITECTURE-SPINE.md` (350 lines, AD-1 … AD-24)
- `design/verification-design.md`
- `design/validation-harness-design.md`
- `design/skills-structure-design.md`
- `design/security-and-service-design.md`
- `design/robot-description-and-sourcing-design.md`

**Headline:** the prior fix pass did its job on the items it touched. Every AD-13 / AD-14 /
AD-15 / AD-17 / AD-18 / AD-21 / AD-22 / AD-23 / AD-24 number that appears in more than one
document agrees, with **one** exception (F-02, the Phase-5 skill count). The remaining findings
are **omissions**, not contradictions: two numbers the spine binds are absent from the design doc
that is named as their owner (F-03, F-04). Nothing found is a silent weakening of an AD.

---

## 1. Findings Table

| # | Severity | Doc + line + quoted text | Conflicting anchor + line + quoted text | Finding | Suggested fix (which side changes) |
|---|---|---|---|---|---|
| F-01 | LOW | Task brief and `ARCHITECTURE-SPINE.md:12` — `sources: ['docs/intent.md', '_bmad-output/planning-artifacts/research/index.md']` | Actual file location: `D:\Work\Personal\Sources\freecad-buddy\docs\intent.md`. No `intent.md` exists under `…/architecture-freecad-buddy-2026-07-21/docs/`. | The spine's `sources:` path `docs/intent.md` is repo-root-relative, while every other path in the spine (`design/component-design.md`, `design/verification-design.md`) is relative to the spine's own directory. Two different bases in one frontmatter field. Not a content conflict — the file exists and was read — but a reader following the link from the spine directory hits nothing. | **Spine changes.** Make the base explicit: `sources: ['/docs/intent.md', …]` or `'../../../../docs/intent.md'`. Same treatment for `spec-refs` in `validation-harness-design.md:6` (`_bmad-output/specs/…`, also repo-root-relative). |
| F-02 | MEDIUM | `skills-structure-design.md:113` — "A body **may also** name a sibling skill in prose as a routing pointer (AD-15, amended — **all 12 skills ship together**)"; and `:114` — "chosen to be disjoint **across the 12 skills** where possible" | `skills-structure-design.md:44` (same doc) — "The catalog is the **12 Track A+B plus these** — the router's resident-description count and the budget table grow with it"; `ARCHITECTURE-SPINE.md:157` — "*(Catalog: the 12 Track A+B parametric-CAD skills, **plus a Phase-5 robot-description/sourcing group** — `urdf-export`, `sdf-export`, `part-sourcing` …)*" | Three places in `skills-structure-design.md` still say the catalog is exactly 12 after Phase 5 lands: line 113 ("all 12 skills ship together" — the stated *justification* for the in-body routing-pointer amendment), line 114 ("disjoint across the 12 skills"), line 124 ("**Resident always:** the 12 `name` + `description` pairs (Level 1, ~1.2K tokens)"), and line 196 ("production loads a routed subset, never all 12"). The doc's own §1 (line 44) and the spine both say the store becomes 15 (12 + `urdf-export`, `sdf-export`, `part-sourcing`). The §7 budget table row "Ablation `--skills all` \| 12 bodies \| ~25K" (line 188) inherits the same stale count. The §1 carve-out ("the budget table grow with it") tells the reader the table is wrong but does not fix it. | **Design changes.** In `skills-structure-design.md`, replace the hard "12" at lines 113, 114, 124, 188, 196 with a catalog-relative phrase — "all catalogued skills ship together", "the resident `name` + `description` pairs (12 at Phase 3, 15 after Phase 5)". Keep line 44 as the single place that states the count and its growth rule. Leave `validation-harness-design.md:253` at `×12 skills` — it is GS.5-scoped (Track A+B ablation), which really is 12. |
| F-03 | MEDIUM | `validation-harness-design.md:145` — banner is "(FreeCAD version, `ElementMapVersion`, validator sensitivity, Wilson CI where a rate is claimed)". `validation-harness-design.md` contains **no** occurrence of `AD-24`, `15 s`, `10 min`, or a latency/wall-clock budget anywhere (verified by grep over the whole file). | `ARCHITECTURE-SPINE.md:225` — "> Detailed design: [Validation & Benchmark Harness Design](design/validation-harness-design.md) (**timing capture, report banner**)"; `:229` — "These are gate criteria measured by the harness, never self-reported by the acting agent, and **each is reported in the standard banner alongside its n**. One timing basis for all of them: wall-clock from tool-call entry to envelope return, model time included. Budgets are pass/fail at the gate, not advisory."; spine Consistency Conventions `:242` — "Every verification/benchmark report carries a banner: FreeCAD version, `ElementMapVersion`, validator sensitivity, Wilson CI (where a rate is claimed), and **the AD-24 budget measured for that gate with its n**." | AD-24 names `validation-harness-design.md` as the owner of "timing capture, report banner", and the spine convention makes the AD-24 budget a **mandatory banner field**. The harness design's banner definition (line 145) lists the other four fields and omits the AD-24 budget. It also never defines the timing basis it is told to own, and §3.2 step 6 ("Verdict — gate = PASS iff all four legs") lists no budget leg, so ≤15 s / ≤10 min / 50-job-soak are not pass/fail anywhere in the runner as designed. Not a contradiction of a number — an unimplemented binding. The spine says "pass/fail at the gate"; the harness design has no gate mechanism for it. | **Design changes.** Add the AD-24 budget to the banner field list at `validation-harness-design.md:145` and to the report blocks in §4 ("alongside its n"). Add §3.2's timing capture: one wall-clock measurement from tool-call entry to envelope return, model time included, per AD-24. Add a fifth verdict leg to §3.2 step 6: "(e) the gate's AD-24 budget is met at the stated n". Do **not** change the spine — AD-24's numbers are correct and uncontested. |
| F-04 | MEDIUM | `validation-harness-design.md:22` — `dev/  #   50-question eval + 30 broken-doc cases (**tiered n=10->n=30, decision 008**)`. That comment is the file's only mention of the ladder; grep for `n=10`, `8/10`, `10/10`, `escalat` over `design/` returns nothing else. | `ARCHITECTURE-SPINE.md:149` — "**Tiered gate screens:** the G1 error-diagnosis gate uses the ladder from intent.md — **grade n=10 first (pass ≥8/10), escalate to the sealed n=30 run only on a 10/10 result** (Wilson CI reported); below 10/10 the gate concludes at n=10 and is flagged low-confidence."; `docs/intent.md:217` — "the gate grades the first n=10 (pass ≥ 8/10), and only a 10/10 result escalates to the full n=30 run (Wilson CI reported); below 10/10 the gate concludes at n=10, low-confidence flagged"; `docs/decisions/008-g1-eval-tiered-n10-n30.md:42` — "Drives … **The G1.2 / GS.4 gate-runner escalation logic** (grade 10, escalate on 10/10, report Wilson CI)." | The ladder's numbers are consistent everywhere they appear (intent 217 = spine 149 = decision 008). But the harness design — the document that specifies the gate runner — carries the ladder only as a directory comment. §3.2 "Execution flow" runs "Run cases ×R" over the whole set with no n=10 screen, no 10/10 escalation branch, and no low-confidence flag. Decision 008 explicitly names the gate-runner escalation logic as the thing it drives; that logic has no design. Also unrecorded in the harness: the GS.4 variant threshold **≥9/10** (decision 008 line 10; intent.md:131 "pass rate with skill ≥ 9/10 at n=10"), which is the only place the skill-loaded bar differs from the base gate. | **Design changes.** Add the escalation branch to `validation-harness-design.md` §3.2 as a G1-specific step: grade the first 10 cases; `<10/10` → conclude at n=10, attach Wilson CI, stamp low-confidence; `10/10` → unseal and run the full n=30, report Wilson CI on n=30. State both thresholds (G1.2 ≥8/10, GS.4 ≥9/10) and cite decision 008. Spine and intent are correct and need no change. |
| F-05 | LOW | `skills-structure-design.md:51` — "Body ≤1,500 words; the `check_skill_shape.py` CI check that enforces this is **not yet built** (Story 6.1) — until it lands the cap is convention only (§6)"; `:171` — "\| Body word count \| ≤1,500 words (frontmatter excluded) \| AD-15 — **checker unbuilt (Story 6.1)** \|" | `ARCHITECTURE-SPINE.md:157` — "(`SKILL.md` body ≤1,500 words — enforcement by `scripts/check_skill_shape.py` in CI is **required and not yet built** (Story 6.1); until it lands the cap is convention only" | **Clean on the status claim** — the design doc does not claim the checker exists; it repeats the spine's "not yet built (Story 6.1)" in both places. One residual inconsistency: §6's heading and framing still read as a built component — `:166` "One script (external process, runs in the existing CI workflow), **blocking on both matrix legs**" and `:190` "Budget guard: the shape check's 1,500-word cap **is the enforcement mechanism** for every row". Present tense describing an unbuilt script. Only the word-count row is annotated unbuilt; the other four rows (frontmatter, four sections, no cross-skill deps, description shape) carry no status marker, so a reader takes them as live CI. Per spine AD-15 the whole script is unbuilt, not just its word-count rule. | **Design changes.** Put one status line at the top of `skills-structure-design.md` §6: "Status: `scripts/check_skill_shape.py` is **not yet built** (Story 6.1, AD-15). Every rule below is the specification for that script, and convention-only until it lands." Change `:190` to future tense. Then the per-row "checker unbuilt" annotation at `:171` is redundant and can go. Spine unchanged. |
| F-06 | LOW | `security-and-service-design.md:119` — "`max_tasks_per_child=1` default: each worker imports FreeCAD App modules once (warm), runs exactly one job, exits … **[DEFERRED-DETAIL]** K (likely 2–4) and any recycle N>1 are set empirically by the G4 soak test; N=1 ships as the safe default (spine Deferred table)" | `ARCHITECTURE-SPINE.md:181` — "recycle default one task per worker (`max_tasks_per_child=1` on `ProcessPoolExecutor`)"; spine Deferred `:336` — "Worker pool tuning (K warm workers, recycle N) \| Soak test at Phase 4 sets empirically; **N=1 safe default stands**" | **Clean.** Value, mechanism, default, and deferral status all agree across the three places. Recorded as verified, no action. |
| F-07 | LOW | `verification-design.md:363` — "**Robot-description export (Phase 5, AD-22):** planted wrong-frame axis, cyclic kinematic tree, second root, negative/implausible inertia, unresolved mesh, mm-as-m unit lie — each must be caught by the `verify_export_urdf`/`verify_export_sdf` re-parse leg"; `robot-description-and-sourcing-design.md:194-198` — "wrong-frame axis, second root, cyclic tree, **child with two parents**, negative/implausible inertia, **non-normalized axis**, **continuous-with-fake-limits**, unresolved mesh, mm-as-m unit lie, **SDF pose with unresolvable `relative_to`**" | — | The Phase-5 fault lists differ in length: `verification-design.md` lists 6 faults, `robot-description-and-sourcing-design.md` lists 10. The 6 are a strict subset of the 10, so there is no contradiction, and AD-13's bar is "≥10-case", which only the Phase-5 doc's list satisfies on its own. A reader working from `verification-design.md` §9 alone would build a 6-case suite and miss the AD-13 floor. | **`verification-design.md` changes.** At `:363`, after the 6 named faults, add a pointer: "— the full ≥10-case list is in robot-description-and-sourcing-design.md §7." No number changes. |
| F-08 | LOW | `verification-design.md:344` — Mesh volume band "`(2/3) · linear_deflection · surface_area` (chordal-sag bound), **never ±0.1 %** and never bbox-relative \| AD-9 fixed rule" | `ARCHITECTURE-SPINE.md:109` — "Mesh volume tolerance derives from deflection, never ±0.1 %." | **Clean.** The design doc states the concrete formula the spine leaves abstract, and repeats the spine's ban verbatim. Elaboration without weakening. Recorded as verified. |

---

## 2. Number Reconciliation Table

Every number the brief named, with its value in each document that states it. Blank = the
document does not state this number (not a mismatch unless flagged).

| # | Number | `docs/intent.md` | `ARCHITECTURE-SPINE.md` | `verification-design.md` | `validation-harness-design.md` | `skills-structure-design.md` | `security-and-service-design.md` | `robot-…-sourcing-design.md` | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Validator sensitivity | `:152` "≥ 95%"; `:164` "≥ 95%" | AD-13 `:141` "≥95 %"; AD-19 `:189`; AD-21 `:205` "≥95 %" | `:334` "≥ 95 %"; `:330` "≥95 %"; `:365` "≥ 95 %" | `:142` "≥95 %"; `:150` "≥95 %"; `:220` "bar: >=95%" | — | `:173` "≥95%" | `:194` "≥95 %" | **AGREE** (7 docs) |
| 2 | False-alarm rate | `:152` "≤ 5%"; `:164` "≤ 5%" | AD-13 `:141` "≤5 %"; AD-21 `:205` "≤5 %" | `:334` "≤ 5 %"; `:330` "FA ≤5 %"; `:365` "≤ 5 %" | `:142` "FA ≤5 %"; `:150`; `:221` "bar: <=5%" | — | `:173` "≤5% false alarm" | `:194` "FA ≤5 %" | **AGREE** (7 docs) |
| 3 | Fault-injection suite size | `:164` "≥ 10 planted-failure cases" | AD-13 `:141` "≥10-case"; AD-19 `:189` "≥10-case" | `:334` "≥10-case" | `:19` ">=10 planted-fault cases"; `:217` "Every suite mixes ≥10 planted defects with clean controls" | — | `:173` "≥ the four canonical faults" (G4-specific, additive to the ≥10 floor — not a competing value) | `:194-198` lists 10 named faults | **AGREE** |
| 4 | Human spot-audit fraction | `:156` "≥ 20%" | AD-19 `:189` "≥20 %" | — | `:251` "≥20 % of passing results at random per AD-19"; `:244` example `"fraction_of_passing": 0.25` (a sample value ≥ the floor, not a competing rule) | — | — | — | **AGREE** |
| 5 | Dev / held-out overfit gap | `:153` "> 15 points" | AD-14 `:149` ">15pp = overfitting — the phase does not exit" | — | `:150` "dev/held-out gap ≤15pp (AD-14 — gap >15pp = overfitting, no exit)" | — | — | — | **AGREE** |
| 6 | McNemar significance | — | AD-14 `:149` "exact McNemar two-sided p<0.05" | — | `:165` exact, two-sided, "Never the chi-square asymptotic"; `:194` "p<0.05"; `:189` worked example p=0.039 | `:144` "exact McNemar two-sided p<0.05" | — | — | **AGREE** |
| 7 | Wilson CI level | — | AD-14 `:149` "95 % Wilson CI … excluding 0"; conventions `:242` | — | `:158` "Wilson 95 % CI … z=1.96"; `:194` | `:144` "Wilson 95% CI on the paired difference excluding 0" | — | — | **AGREE** |
| 8 | R default (dev) | — | AD-14 `:149` "R=5 default" | — | `:122` "dev iteration: R=5" | `:144` "R=5 dev" | — | — | **AGREE** |
| 9 | R, Phase 1 answer eval | — | AD-14 `:149` "R=3 Phase 1 answer eval" | — | *(absent)* | *(absent)* | — | — | **AGREE** (no conflicting value stated; see note A) |
| 10 | R, sealed held-out / pp-claims | — | AD-14 `:149` "R≥10 for sealed held-out runs and any pp-threshold claim" | — | `:128` "forces R>=10"; `:150` "R≥10"; `:194` "at R≥10" | `:144` "R≥10 sealed/pp-claims" | — | — | **AGREE** |
| 11 | pp-threshold set size | `:130` "≥ 15 percentage points" (the claim) | AD-14 `:149` "dedicated n≥40 paired set" | — | `:35` "n>=40 dedicated set"; `:194` "dedicated n≥40 paired set at R≥10"; `:185` worked example "n=40 paired specs, R=10" | `:144` "dedicated n≥40 paired set" | — | — | **AGREE** |
| 12 | Tiered ladder — first tier n | `:217` "first n=10 (pass ≥ 8/10)" | AD-14 `:149` "grade n=10 first (pass ≥8/10)" | — | `:22` "tiered n=10->n=30, decision 008" (comment only — **no pass rule, no escalation logic**) | — | — | — | **AGREE on value; OMITTED in harness → F-04** |
| 13 | Tiered ladder — escalation trigger | `:217` "only a 10/10 result escalates" | AD-14 `:149` "escalate to the sealed n=30 run only on a 10/10 result" | — | *(absent)* | — | — | — | **AGREE on value; OMITTED → F-04** |
| 14 | Tiered ladder — second tier n | `:217` "full n=30 run (Wilson CI reported)" | AD-14 `:149` "sealed n=30 run" | — | `:22` "n=30" (in comment); `:22` "30 broken-doc cases" | — | — | — | **AGREE** |
| 15 | Skill-loaded ladder bar (GS.4) | `:131` "≥ 9/10 at n=10 (vs the baseline 8/10 criterion)" | *(not stated — spine states only the base ≥8/10)* | — | *(absent)* | *(absent)* | — | — | **AGREE** (no conflict; harness omission, F-04) |
| 16 | STEP round-trip volume | `:199` "volume ±0.1%"; `:197` "±0.1% tolerance" | AD-9 `:109` "±0.1 %" | `:257` "**±0.1 %** of source"; `:342` "STEP round-trip volume \| ±0.1 %" | — | — | — | — | **AGREE** |
| 17 | Mesh volume band (the anti-number) | — | AD-9 `:109` "Mesh volume tolerance derives from deflection, never ±0.1 %" | `:262` "within the deflection-derived band (§8 — never ±0.1 %)"; `:344` "`(2/3) · linear_deflection · surface_area` … **never ±0.1 %**" | — | — | — | — | **AGREE** |
| 18 | Fingerprint quantization | — | AD-6 `:85` "@1e-6"; conventions `:245` "fingerprint quantization 1e-6" | `:102` "`Q = 1e-6  # quantization step (spine convention)`"; `:338` "1e-6 (absolute, per component) \| AD-6 fixed; not calibratable" | — | — | — | — | **AGREE** |
| 19 | AD-10 user-facing render cap | — | AD-10 `:117` "≤1920 px … the **user-facing** budget" | `:325` names the exclusion: "the AD-10 *user-facing* render budget does not apply" (does not restate 1920) | — | — | — | — | **AGREE** (also `integration-mcp-clients.md:140` "≤1920 px longest edge" — outside this lens, checked, agrees) |
| 20 | AD-21 judge legibility floor | — | AD-21 `:205` "legibility floor of **≥2048 px** page width" | `:325` "≥2048 px page width … the ≥2048 px floor is fixed in AD-21" | *(§8 describes the judge wiring; does not restate the px floor — no conflict)* | — | — | — | **AGREE** |
| 21 | AD-24 Phase 1 latency | `:219` "≤ 15 s median" | AD-24 `:229` "Phase 1 answer latency ≤15 s median" | — | *(absent — F-03)* | — | — | — | **AGREE on value; OMITTED in the named owner → F-03** |
| 22 | AD-24 Phase 3 wall-clock | `:264` "≤ 10 minutes" | AD-24 `:229` "Phase 3 per-part wall-clock ≤10 min median" | — | *(absent — F-03)* | — | — | — | **AGREE on value; OMITTED → F-03** |
| 23 | AD-24 soak run size | `:286` "50-job soak run" | AD-24 `:229` "50-job soak" | — | `:269` defers G4 soak specifics to the Phase 4 gate (consistent) | — | `:172` "50-job soak through the job API" | — | **AGREE** |
| 24 | AD-24 memory growth | `:286` "memory growth < 20% over the run" | AD-24 `:229` "memory growth <20 %" | — | — | — | `:172` "RSS growth <20%" | — | **AGREE** |
| 25 | Skill body word cap | `:124` (four sections, no word cap stated) | AD-15 `:157` "≤1,500 words" | — | — | `:51` "≤1,500 words"; `:171` "≤1,500 words (frontmatter excluded)"; `:190` "1,500-word cap" | — | — | **AGREE** |
| 26 | Skill token budget | — | AD-15 `:157` "≤~10K token skill budget" | — | — | `:124` "≤~10K total skill budget (AD-15)"; `:185` "**≤~10K hard budget (AD-15)**" | — | — | **AGREE** (also `integration-mcp-clients.md:75,125` "≤~10K" — agrees) |
| 27 | Routed bodies per task | — | AD-15 `:157` "2–5 bodies routed per task" | — | — | `:124` "**Routed per task:** 2–5 SKILL.md bodies"; `:131` "never injects more than 5 bodies"; `:162` "capped at 5 bodies" | — | — | **AGREE** |
| 28 | Resident description count | `:124` "the Track A and Track B catalogs (12 skills)" | AD-15 `:157` "the 12 Track A+B … plus a Phase-5 … group"; "the resident-description count **grows with the catalog**" | — | `:253` "×12 skills, GS.5" (GS-scoped — correct) | `:44` "the 12 Track A+B **plus these**"; but `:124` "the **12** `name` + `description` pairs"; `:113` "all **12** skills ship together"; `:114`; `:188`; `:196` | — | `:37-39` adds `urdf-export`, `sdf-export`, `part-sourcing` | **MISMATCH → F-02** (12 vs 12+3 within `skills-structure-design.md` itself) |
| 29 | `max_tasks_per_child` | — | AD-18 `:181` "`max_tasks_per_child=1`" | — | — | — | `:119` "`max_tasks_per_child=1` default"; "N=1 ships as the safe default" | — | **AGREE** |
| 30 | Closed status set (7 members) | — | AD-17 `:173` "`OK \| SPEC_FAILED \| RECOMPUTE_ERROR \| TIMEOUT \| OOM_KILLED \| WORKER_CRASHED \| INVALID_INPUT`" | `:72` "status per AD-17 closed set" (no variant defined) | `:142` uses `INVALID_INPUT` | — | `:120` `WORKER_CRASHED`; `:139` `TIMEOUT`/`OOM_KILLED`; `:165` "terminal status comes only from the closed AD-17 set"; `:173` all four | `:159` `SPEC_FAILED`, `RECOMPUTE_ERROR`-class | **AGREE** — no document invents a status outside the set |

**Note A (row 9).** `R=3 Phase 1 answer eval` appears only in AD-14. `validation-harness-design.md`
§3.1 shows `R=5` as the dev default and `-R 1` as a quick-loop override, so the R=3 leg has no
design, but it also has no competing value. Lower risk than F-04 because the ladder (F-04) carries
a pass rule and a branch; R=3 is a single parameter. Worth folding into the F-04 fix.

---

## 3. Directed Checks From the Brief

**2 — AD-13 / AD-14 / AD-19 / AD-21 vs the two harness docs. Clean.**
No contradiction and no silent weakening found.

- AD-13 "never by the producing agent" → `validation-harness-design.md:11` "it never lets the
  producing agent grade itself (AD-13)"; §8 `:259` "preflight **hard-fails** if they resolve to the
  same model id + same context".
- AD-13 "held-out is sealed until phase exit" → §1.1 makes it mechanical: `:65` "`gate run --exit`
  is the **only** code path that unseals", plus the burn rule. This is *stronger* than the AD, which
  is allowed.
- AD-13 "sub-element index selectors are banned in specs" → `verification-design.md:280` repeats it;
  `:285` "`HoleSelector` — a geometric query …, **never an index**".
- AD-13 "Whole-shape similarity (Chamfer/IoU) is never a primary metric" → `verification-design.md:303`
  verbatim.
- AD-14 "below-detection … not as failures" → `validation-harness-design.md:168` "`BELOW_DETECTION_AT_N`,
  never 'no effect' and never a win"; the b+c<6 MDE guard is an added mechanism, not a weakening.
- AD-19 "before any phase code exists, the benchmark runs against a stub and fails honestly" →
  `security-and-service-design.md:172` "built against a stub first, failing honestly"; `:169`
  "Phase 4 implementation may not begin until its Validation Design Gate lands".
- AD-19 fault-injection-before-implementation → `verification-design.md:365` "Each suite must show
  sensitivity ≥ 95 % / false-alarm ≤ 5 % **before phase implementation begins** (AD-19)".
- The only AD-14 / AD-24 items with no design are F-04 and F-03 — omissions, not weakenings.

**3 — AD-15 vs `skills-structure-design.md`.** One mismatch (F-02), one presentation issue (F-05);
the rest clean.

- Store shape: `:18` "One directory per skill … SKILL.md is mandatory; `references/` is optional" — matches AD-15.
- Four mandatory sections: `:106` "Section-order and heading names are exact (`Scope`, `Decision
  Rules`, `Worked Examples`, `Anti-Patterns`)" — matches AD-15 `:157` "scope statement, decision
  rules, worked examples, anti-patterns", in the same order.
- Two loader modes: §4.1 production metadata-first router, §4.2 forced explicit subset with
  `:142` "**auto-activation is disabled**" — matches AD-15 exactly, including `:133` "The injection
  path is the portable common denominator".
- Sibling-mention routing-pointer rule: `:45` "A body may still name a sibling skill in prose as a
  routing pointer (AD-15 amended) — that is not a path dependency", and the §6 check row `:173`
  "the check does **NOT** flag sibling names. It still flags any `references/` link or file path
  that escapes the skill's own dir." This is the amended AD-15 `:157` read correctly — prose
  mention allowed, path dependency banned. **Clean.**
- `check_skill_shape.py` status: **the design does not claim it exists.** `:51` and `:171` both say
  unbuilt / Story 6.1, matching spine `:157` "required and not yet built (Story 6.1)". Residual
  present-tense framing → F-05 (LOW).
- Catalog size: → **F-02**.

**4 — AD-17 / AD-18 / AD-24 vs `security-and-service-design.md`.** Clean except the AD-24 gap,
which lands on the harness doc, not this one.

- Closed status set: no invented member anywhere (table row 30). `:165` "terminal status comes only
  from the closed AD-17 set with machine-readable detail" — and the corollary "A worker that
  crashed, timed out, or was OOM-killed can **never** surface as `OK`".
- Audit log from Phase 0: `:38` "every mutation tool call (**AD-17 requires this from Phase 0**)
  appends one JSON line"; `:46` "opened append-only … the bridge exposes **no tool that reads,
  truncates, or rotates it**" — stronger than AD-17 `:173` "An append-only audit log … exists from
  Phase 0". Allowed.
- Worker recycling: table row 29, **AGREE** (F-06).
- Sandbox posture: `:135`–`:137` matches AD-18 `:181` item for item — nsjail/bubblewrap or hardened
  `--network none` container on Linux; WSL2-preferred on Windows with AppContainer + Job Object as
  the native alternative; `:141` "Workers are also **GPU-none**"; `:141` egress deny-by-default.
  Every concrete number carries **[DEFERRED-DETAIL]**, matching spine Deferred `:335`.
- `spawn` and supervisor-never-imports-FreeCAD: `:118`–`:119` both explicit.
- Soak + memory instrumentation: `:172` "50-job soak … RSS growth <20%" — matches AD-24. The
  **leak-baseline experiment** at `:171` ("single long-lived interpreter, M iterations — evidence
  record for N=1 vs N>1") is the memory instrumentation AD-24 `:228` demands ("a soak claim with no
  memory instrumentation"). **Clean.**
- `debug_exec` permanently off in service: `:31` `if caps.allow_exec and not caps.service_mode:` and
  `:36` "**permanently disabled in the Phase 4 service** even if the env flag is present" — matches
  AD-4 `:69`.

**5 — AD-22 / AD-23 vs `robot-description-and-sourcing-design.md`.** Clean.

- Export/verify pairing: `:106` "Each `export_*` carries `verified: false` until its pair passes";
  schema `:131` `"verified": { "const": false, "description": "completes ONLY via
  verify_export_urdf (AD-9)" }`; `:160` "the verify leg re-parses the written file from scratch —
  'bytes were written' is never success." Matches AD-22 `:213` and AD-9 `:109`.
- Unit/frame boundary: §2 table `:61`–`:66` pins mm→m (÷1000), deg→rad (×π/180), and the composed
  inertia conversion; `:58` "Fixed here, pinned per call, never ambient" — matches AD-22 `:213`
  "an explicit, pinned boundary, never an ambient default". Frame rules `:67`–`:74` give the
  URDF parent-link / joint-frame / link-frame split and the SDF `relative_to` rule, and `:73`
  "Every emitted origin records … the frame it was expressed in" matches AD-22's frame-semantics
  requirement.
- Inertials API surface: §4 `:94`–`:97` `Mass`, `CenterOfMass`, `MatrixOfInertia` /
  `PrincipalProperties` via shim `solid_inertials(obj)` — matches AD-22 `:213` "native solid
  inertials (`TopoShapeSolidPy` mass-property surface)" and AD-11 shim ownership (`:49` lists the
  new probes as shim extensions).
- Gate-decided items: `:32` build path (CROSS vs own XML), `:64` density source, `:85` URDF ball
  joint, `:179` catalog choice — all carry **[GATE-DECIDED]**, and all four are in the spine's
  Deferred table (`:344`, `:345`) or AD-22's "Empirically-gated items land at the G5-robot gate"
  (`:209`). No item is decided in the design that the spine defers.
- AD-23: `:180` import "through the document lifecycle (AD-20)"; `:172` "measured … the basis for
  mating frames (**never the assumed origin**)"; `:175` provenance/license "(AD-16)". All three
  AD-23 rules present.

**6 — Does any design claim a capability the spine defers, or defer something the spine binds?**
No on the first; one instance of the second, and it is correct.

- Checked every **[GATE-DECIDED]** and **[DEFERRED-DETAIL]** marker against the spine Deferred table
  (`:330`–`:349`). Every one has a matching row or an AD clause authorizing the deferral.
- `skills-structure-design.md:149` defers final router rules — spine Deferred `:334` "Skill router
  rules (task→subset map) \| Tuned from ablation data". `:195` "Deferred honored: final router rules
  stay deferred per the spine; §5 is explicitly a starter seed." **Correct deferral.**
- `verification-design.md:272` defers slicer-acceptance + lib3mf-fallback-writer to the Phase 4
  realism gate — spine Deferred `:337`. **Correct.**
- `verification-design.md:334` defers exact tolerance values to per-phase fault calibration — spine
  Deferred `:348`. **Correct.**
- The **reverse** direction — deferring something the spine binds — is where F-03 and F-04 sit. The
  harness design does not *say* it defers AD-24 budgets or the tiered ladder; it simply has no
  mechanism for either, while the spine binds both as gate criteria. That is why both are MEDIUM
  and not LOW: silence reads as deferral to an implementer.

**7 — Is the AD-21 visual judge fault-tested to the AD-13 bar before its verdicts are citable? Yes.**
Verified on both sides, and the loop is closed.

- AD-21 `:205`: "The judge is itself a validator under AD-13/AD-19: fault-injected (planted
  visually-wrong parts) to sensitivity ≥95 % / false-alarm ≤5 % **before its verdicts are citable**."
- `verification-design.md:330`: "**Judge as validator (AD-13/AD-19):** fault-suite of planted
  visually-wrong parts — mirrored part, missing flange, feature on wrong face, grossly wrong
  proportions — plus clean controls; sensitivity ≥95 % / FA ≤5 % **before verdicts are citable**;
  rubric/checklist edits invalidate prior sensitivity runs (hash-staleness rule)."
- `validation-harness-design.md:265`: "The judge **registers in `_registry/validators.yaml`** with
  its planted visually-wrong-part fault suite (mirrored, missing flange, wrong-face feature, wrong
  proportions + clean controls); checklist edits stale its sensitivity run."
- The enforcement is mechanical, not aspirational: §3.2 preflight `:142` aborts the gate with
  `INVALID_INPUT` unless "**every validator cited by this gate** must have a *current* fault-suite
  run (same validator version) at sensitivity ≥95 % / FA ≤5 %". Because the judge is a registry
  entry, a stale judge blocks the gate automatically.
- Fault-case count: the named list is 4 planted defects + controls. AD-13's floor is ≥10 cases.
  Neither doc states a judge-suite case count. Not raised as a separate finding — the "≥10-case"
  rule is stated generally in both docs (`verification-design.md:334`,
  `validation-harness-design.md:217` "Every suite mixes ≥10 planted defects with clean controls"),
  so the judge suite inherits it. Worth noting only that the 4 examples are illustrative, not the
  suite. Same pattern as F-07 and resolved the same way if the F-07 fix is applied.
- Conjunctive rule held in both: `verification-design.md:317` "Conjunctive only — the judge can
  never pass a part geometry failed"; `validation-harness-design.md:265` "Part-done verdict in the
  runner = geometry checks ∧ `visual.judge` pass (AD-21 conjunction)".
- Fail-closed held in both: `verification-design.md:329` "part is **not done**; the only bypass is
  an explicit operator waiver flag, audit-logged"; `validation-harness-design.md:265`
  "`visual.unavailable` blocks done unless an audit-logged operator waiver is present".

---

## 4. Summary Count

| Severity | Count | Findings |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 3 | F-02 (skill catalog count, internally inconsistent), F-03 (AD-24 budgets absent from their named owner), F-04 (tiered ladder has no gate-runner design) |
| LOW | 5 | F-01 (intent.md path base), F-05 (§6 present tense on unbuilt script), F-06 (verified clean), F-07 (Phase-5 fault list subset), F-08 (verified clean) |
| **Total** | **8** | of which **2 are clean-area confirmations** (F-06, F-08) |

**Numbers checked: 30. Mismatches: 1** (row 28, skill catalog count → F-02). **Omissions where the
value agrees but the named owner document does not carry it: 4** (rows 12, 13, 21, 22 → F-03, F-04).
Every other number agrees across every document that states it.

**Clean areas, stated as clean:** the AD-13 sensitivity/false-alarm bar (7 documents, identical);
AD-14 statistics (McNemar, Wilson, R ladder, n≥40, 15pp gap); AD-17 closed status set (no document
invents a member); AD-18 isolation posture in full; AD-21 judge independence, conjunction,
fail-closed degradation, and validator-of-the-validator loop; AD-22 pairing, unit/frame boundary,
inertials surface, and gate-decided markers; AD-23 all three rules; the AD-15 store shape, four
sections, two loader modes, and sibling-mention rule; and the `check_skill_shape.py` unbuilt status,
which the design doc reports honestly.

**Priority if only one fix is made:** F-03. AD-24 says "Budgets are pass/fail at the gate, not
advisory", and names `validation-harness-design.md` as the owner. As written, no gate can fail on a
budget, so the criterion the spine calls pass/fail is unenforceable — exactly the failure AD-24's
"Prevents" clause names: "measurable exit criteria discovered unmet at phase exit".
