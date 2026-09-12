# Drift Review 2 — Lens A: intent.md vs ARCHITECTURE-SPINE.md

**Scope.** `docs/intent.md` (341 lines) against `ARCHITECTURE-SPINE.md` (350 lines, AD-1..AD-24).
**Type.** Re-review. Every claim below is checked against the current text, not against the prior pass.
**Method.** Full read of both files, then a coverage walk over every intent element named in the task, then five drift passes.

---

## Findings

| Severity | intent anchor | spine anchor | Finding | Suggested fix |
|---|---|---|---|---|
| HIGH | L131: "`freecad-troubleshooting` specifically: Phase 1 error-diagnosis cases pass rate with skill ≥ 9/10 at n=10 (vs the baseline 8/10 criterion), escalating to the full n=30 run on a 10/10 result (Wilson CI reported)." | AD-14 L149: "the G1 error-diagnosis gate uses the ladder from intent.md — grade n=10 first (pass ≥8/10), escalate to the sealed n=30 run only on a 10/10 result (Wilson CI reported); below 10/10 the gate concludes at n=10 and is flagged low-confidence." | The two thresholds in L131 are **mutually unreachable** under AD-14's single ladder. L131 sets the skill bar at ≥9/10 but escalation fires only at 10/10. A skill run scoring exactly 9/10 satisfies L131's stated bar, yet AD-14 stops it at n=10 and flags it low-confidence — so the L131 criterion can be "met" and simultaneously be non-citable. AD-14 carries only the **baseline** ladder (which matches L217 exactly); it never states what the *skill* leg must score. This is not the simple 9-vs-8 mismatch the task hypothesised: AD-14's ≥8/10 is the baseline figure from L217, correctly quoted. The real gap is the missing skill-leg rule. | Add one sentence to AD-14: state whether the skill leg escalates on 10/10 (same ladder, so ≥9/10 at n=10 is a pass but low-confidence) or on ≥9/10 (skill-specific ladder). Then reconcile L131's wording to whichever is chosen. |
| MEDIUM | L168: "The gate itself is timeboxed to ~20% of the phase timebox (e.g. ~1 week of a 6-week phase); it is part of the phase, not an addition to it." | AD-19 L189 lists the five gate artifacts and the ≥20 % human audit, but states no timebox. Grepped the spine for `timebox` — **no matches**. Grepped for `20 %` — matches only AD-19's audit sample and AD-24's memory-growth budget. | Silent weakening. Intent binds the gate to ~20 % of the phase; the spine drops it with no amendment note. The number matters: without it the gate can expand and eat the phase, which is exactly the "Phase slippage" risk at L333. | Add the ~20 % gate timebox to AD-19's Rule, or add a one-line note saying the spine deliberately leaves gate scheduling to planning artifacts. |
| MEDIUM | L132: "Each skill has an owner-reviewed accuracy pass against current FreeCAD documentation (version-pinned, same versions as CI matrix)." | Grepped the spine for `accuracy`, `owner-reviewed`, `stale` — **no matches**. AD-15 L157 governs skill shape, loading, routing and budgets only. AD-11 L125 owns the CI version matrix but says nothing about skill content. | UNHOMED. This is the sole mitigation for the intent risk at L332 ("Skills become stale or plausible-but-wrong lore"), whose mitigation has three legs: ablation rule, version-pinned accuracy review, failure-analysis feedback. The ablation leg is homed (AD-14 + AD-15). The **accuracy-review leg and the failure-feedback leg are both unhomed.** | Extend AD-15's Rule with a skill-content freshness clause: each `SKILL.md` records the FreeCAD version it was reviewed against, and a version bump in the AD-11 matrix opens a review obligation. |
| MEDIUM | L332 risk mitigation, third leg: "failure analyses feed corrections back". Same rule at L134 ("every Phase 2/3 failure analysis feeds a skill") and L265 ("every benchmark failure analyzed and, where generalizable, fed back into a skill"). | Grepped the spine for `failure analys`, `feed back`, `fed back` — **no matches**. | UNHOMED. Intent states this three times, including inside a binding Phase 3 exit criterion (L265). The spine has no AD, Conventions row, or Deferred row for the benchmark-failure → skill feedback path. | Either home it in AD-15 (skills store) or AD-13 (harness) as a required harness output, or record it in Deferred with a phase gate. |
| LOW | L196: "≥ 15 tools implemented across `query.*`, `document.*`, `export.*`, each with a JSON schema and docstring." L198: "suite ≥ 30 tests, all green." | Grepped the spine for `15 tools`, `30 tests` — **no matches**. Conventions L237 fixes the tool-name namespaces and L240 requires a per-tool `outputSchema`; the Structural Seed L306 fixes the two test worlds. | Counts unhomed. Defensible: AD-24 L229 is the spine's declared home for gate-criterion numbers, and it carries three of intent's numbers (15 s, 10 min, 50-job/20 %) but not these two. The split is arbitrary rather than principled. | Either state in AD-24 that it covers only performance budgets and count criteria stay in intent, or add the Phase 0 counts. A one-line scope sentence on AD-24 fixes it. |
| LOW | L218: "Feature-tree explanation works on documents with ≥ 50 features without exceeding context limits (uses summarized tree queries, not raw dumps)." | Grepped the spine for `context limit`, `summariz`, `tree_summary`, `50 features` — **no matches**. AD-10 L117 governs **image** token budgets; AD-15 L157 governs the **skill** token budget (≤~10K). Neither covers tool-result text size. | UNHOMED. Intent states an architectural constraint — tool results must be summarized, not raw dumps — and the spine has no text-payload budget anywhere. AD-10's "image token blow-ups" prevention shows the spine thinks about token budgets, but only for images. | Add a Conventions row for tool-result payload size (summarized tree queries, no raw dumps), or extend AD-10's budget rule to text payloads. |
| LOW | L68 Reuse Map, second half: "existing LLM eval frameworks evaluated before building \| Only the CAD-specific fault-injection + sensitivity reporting, if no framework fits". | Stack L259: "pytest \| current — harness runner (external process only)". Grepped the spine for `eval framework` — **no matches**. AD-13 L141 mandates the fault-injection suite; AD-14 L145 points at a stats module. | Half-homed. The pytest half is in the Stack; the "evaluate existing LLM eval frameworks first" half is nowhere. The spine goes straight to a built stats module (AD-14) and a built fault-injection suite (AD-13) without recording that the survey happened or came up empty — which is what the Conventions row at L248 demands ("anything built from scratch records why nothing existing fit"). | Add the eval-framework survey to the Phase 0 or Phase 1 reuse-survey obligation, or record the rejection in Deferred alongside the Implicit-CAD rejection precedent (L347). |
| LOW | L108-116: Skill Catalog is Track A (6) + Track B (6) + Track C (5 candidate). L138: "Track C is scoped as part of Phase 4/5 planning." | AD-15 L157: "*(Catalog: the 12 Track A+B parametric-CAD skills, plus a Phase-5 robot-description/sourcing group — `urdf-export`, `sdf-export`, `part-sourcing` — added when Phase-5 lands, AD-22/AD-23.*" | The spine adds a **fourth** skill group that exists in no intent track. It is correctly Phase-5-scoped and traced to AD-22/AD-23, so it is not scope creep. But intent's Skill Catalog now under-describes the planned catalog, and Track C (DFM, machining, mechanical conventions, assembly strategy, spec interpretation) is never mentioned in the spine at all. | One line in AD-15 noting Track C remains intent-owned and unscoped, plus an intent-side note that Phase 5 adds a robot-description skill group. Low urgency — no binding phase is affected. |

---

## Coverage walk — checked and present

Each item below was verified as correctly homed. Absence from the findings table means checked and clean, not unchecked.

### 1. Guiding Principles (L20-25)

| Principle | Homed at |
|---|---|
| L20 Verify, don't trust | AD-5 (post-verify in every mutation), AD-9 (export/verify pairing), AD-13 (deterministic verdict), AD-21 (dual channel). L20's "a recompute error, a null shape, or an unconstrained sketch is a failure even if the code ran" maps to AD-5's post-verify triple and AD-8. |
| L21 Parametric first | AD-11 L125 "VarSet-with-Spreadsheet-fallback driving-dimension façade"; Conventions L238 "Generated features get intent-bearing names (tree reads like a build plan)". The "must remain editable by a human in the FreeCAD GUI" clause has no dedicated AD, but AD-6 bans mesh/tessellation as an identity oracle and AD-21 requires TechDraw from driving parameters, which both presuppose it. Judged homed. |
| L22 Human in the loop by default, autonomy by opt-in | AD-10 L117: "headless is fail-closed unless an explicit `autoApprove` flag, and every auto-approval is audit-logged". Exact match for "by opt-in". |
| L23 Incremental and demoable | No AD, correctly — this is a planning property, not an architecture invariant. The Capability → Architecture Map (L316-326) is the spine's expression of per-phase deliverability. |
| L24 TNP awareness "from Phase 2 onward" | AD-7 (three-layer audit), AD-5 (TNP audit inside every mutation), Conventions L247 (bare `Face6` resolved to mapped names, never stored). AD-7 binds "every mutation tool", and mutations start at Phase 2 — consistent with intent, not stricter. |
| L25 Reuse before invention | Conventions L248 verbatim: "Survey first; adopted components are wrapped, not forked; anything built from scratch records why nothing existing fit (phase reuse survey, AD-19)." Matches intent L58 "wrapped, not forked". AD-19 L189 makes the reuse survey a gate artifact. |

### 2. Reuse Map rows (L60-74), both halves each

| Row | Candidate half | Invent-only-if half |
|---|---|---|
| L62 MCP plumbing | Stack L256 (official `mcp` python-sdk, spec ≥2025-06-18, SDK v2 rename noted, PrefectHQ `fastmcp` flagged as a distinct Phase 0 call) | AD-4 + the whole `verify_*` family = the verify-first tool layer intent reserved as ours |
| L63 Geometry validity checks | AD-5 L77 `Shape.isValid()`; AD-6 L85 mass-property tuple; AD-13 L141 `Face.Surface` typing | "Never" honoured — spine composes kernel checks, defines no geometry kernel |
| L64 Mesh/export validation | AD-9 L109 trimesh + admesh; Stack L257-258. Open3D is absent by name, but AD-9 leaves the second oracle open: "fallback second oracle chosen at the Phase 0 gate" | "Never for the checks themselves" honoured |
| L65 Headless FreeCAD in CI | Stack L261 "GitHub Actions + micromamba \| CI, cached conda env per pinned FreeCAD version"; Environments L310 | "Only thin CI glue scripts" honoured — `run_tests.py` is the only glue named |
| L66 Benchmark specs & golden models | AD-16 L165 names FreeCAD Parts Library, wiki tutorials, permissive HF datasets | AD-16 L165 keeps DeepCAD/ABC/Text2CAD/Fusion 360 Gallery as "methodology references and import-only geometry oracles — never shipped". This is the evaluate-first rule producing a *reject* outcome, which intent L58 explicitly permits ("confirms, updates, or rejects the relevant rows"). Not a contradiction. |
| L67 Agent harness & skill format | AD-15 L157 two loader modes; "The injection path is the portable second-harness mechanism" homes intent L127's 2-harness criterion | "skills *content* is largely our invention" — consistent, AD-15 governs shape not content |
| L68 Eval/ablation runner | Stack L259 pytest | **See findings** — survey half unhomed |
| L69 FreeCAD knowledge source | Deferred L339: "Phase 1 doc-citation channel (skills `references/` vs doc-retrieval tooling over local wiki clone) \| Phase 1 gate" | "Distillation into skills is our work" — AD-15 store |
| L70 Printability/DFM (Phase 4+) | Capability Map L322 "verify tools (rule layer) + slicer CLI oracle"; Deferred L338 | "Only the rule layer" honoured verbatim — L322 says "(rule layer)" |
| L71 TNP mitigation | AD-11 L125 `element_map_available()` probe, AD-7 L93 `ElementMapVersion` | AD-7's three-layer audit is the "automated post-mutation reference audit" intent reserved as invention |
| L72 Robot-description export (Phase 5) | AD-22 L213 + Stack L262-264 (Assembly WB, CROSS addon, schema/parse lib). AD-22 repeats intent's exact caveat: "the in-tree FreeCAD `Robot` workbench is a trajectory/simulation tool, not a URDF exporter" | AD-22 L213 "Every `export_urdf`/`export_sdf` completes **only** through its paired `verify_export_*`" = the verify-first export layer; CROSS "evaluated first per the reuse rule and wrapped, not forked, if it fits" |
| L73 Off-the-shelf part sourcing (Phase 5) | AD-23 L221 `ImportOCAF`/`ReaderStep`; Deferred L345 catalog integration | "Never for the import/placement (native); the catalog search adapter only" — AD-23 L221 "Catalog **search** is an external concern" |
| L74 Implicit / SDF-kernel — **Not adopted** | Deferred L347: "Implicit CAD — **rejected, not deferred** \| OCCT B-rep vs F-rep/SDF kernel mismatch... Recorded so it is not re-litigated". Intent's "recorded to avoid re-litigation" is honoured word-for-word. | n/a |

Genuine-inventions list (L76) — all five homed: verify-first taxonomy (AD-4 + `verify_*`), machine-checkable spec assertions (AD-13), fault-injection harness (AD-13 L141, AD-19 L189), post-mutation TNP audit (AD-7), design-thinking skills (AD-15).

### 3. Skills-Track SMART exit criteria (L127-132)

| Criterion | Homed at |
|---|---|
| L127 12 skills, 2 harnesses | AD-15 L157: "ablation = forced explicit-subset injection with auto-activation disabled. The injection path is the portable second-harness mechanism." |
| L128 Ablation harness, per-skill deltas | AD-15 L157 (two loader modes); AD-14 L145 stats module; Capability Map L325 "Skills track \| skills/ + ablation runner \| AD-14, AD-15" |
| L129 ≥8 of 12 show measurable improvement | "Measurable" is defined by AD-14 L149: "exact McNemar two-sided p<0.05 **and** 95 % Wilson CI on the paired difference excluding 0". The 8/12 count is a gate number the spine does not restate — same class as the L196/L198 counts in the findings table. |
| L130 `design-decomposition` +15pp | AD-14 L149 verbatim: "Any specific pp-threshold claim (e.g. `design-decomposition` +15pp) runs on a dedicated n≥40 paired set." AD-14 L148 names the problem it solves: "the +15pp-at-n=20 undecidable criterion". Strengthening, correctly recorded. |
| L131 `freecad-troubleshooting` tiered eval | **See findings — HIGH** |
| L132 Owner-reviewed accuracy pass | **See findings — MEDIUM, unhomed** |

Also checked: intent L124's four required skill sections ("scope statement, decision rules, worked examples, and anti-patterns") match AD-15 L157 exactly: "the same four sections: scope statement, decision rules, worked examples, anti-patterns." AD-15's amendment note on in-body sibling routing is explicit and reasoned — not silent, and the trade-off it accepts ("a body that leans on a sibling's content is not cleanly ablatable in isolation") is stated rather than hidden. Scored fine.

### 4. Validation-First principles (L150-156) and Gate checkboxes (L162-166)

| Item | Homed at |
|---|---|
| L150 Actor never grades itself | AD-13 L141: "Pass/fail is decided by deterministic `verify_*` code or an independent grader — never by the producing agent." AD-21 L205 extends the same separation rule to the visual judge. AD-17 L173: "agent claims are never echoed as results." AD-24 L229: "never self-reported by the acting agent." Four independent homes. |
| L151 Validate the validator (fault injection) | AD-13 L141 "Every validator ships a ≥10-case fault-injection suite"; AD-19 L189 makes it a gate artifact; AD-21 L205 applies it to the judge itself. |
| L152 Sensitivity ≥95 %, false-alarm ≤5 % | AD-13 L141 exact: "sensitivity ≥95 % / false-alarm ≤5 % before its scores are citable". AD-21 L205 repeats both numbers for the judge. Conventions L242 requires validator sensitivity in every report banner — this homes intent's "only reportable alongside its validator's current sensitivity number". |
| L153 Held-out sets; >15-point gap = no exit | AD-13 L141 "held-out is sealed until phase exit"; AD-14 L149 "A dev/held-out gap >15pp = overfitting — the phase does not exit." Exact. |
| L154 Realism over convenience; provenance | AD-16 L165: "Hand-authored specs must derive from documented real-world parts or user requests — never reverse-engineered to fit what the agent already does well." Near-verbatim from intent. |
| L155 End-artifact checks, not process checks | AD-9 (re-import round-trips), AD-13 L141 (geometry assertions, "feature metadata is diagnostic hint only"), AD-21 (visual leg), AD-17 L173 (re-executed checks). Intent's "surviving a parameter edit" maps to the Phase 3 editability criterion; no AD restates it, but AD-11's VarSet façade is its architectural enabler. |
| L156 Human audit ≥20 % | AD-19 L189 exact: "a human spot-audit of ≥20 % of passing results — any audit-found false pass invalidates the run (fix validator, re-run, re-audit)." |
| L162 Threat list | AD-19 L189 "threat list" |
| L163 Benchmark runnable against a stub, failing honestly | AD-19 L189 verbatim: "benchmark + assertions runnable (against a stub, failing honestly)" |
| L164 ≥10 fault cases, 95/5 | AD-19 L189 "≥10-case fault-injection suite passing the AD-13 sensitivity bar" |
| L165 Grading spec / rubric | AD-19 L189 "written grading rubric"; AD-21 L205 names the Phase 1 grader as the separation precedent |
| L166 Reuse survey | AD-19 L189 "and a reuse survey"; Conventions L248 |
| L168 Gate timebox ~20 % | **See findings — MEDIUM, unhomed** |

Self-deception table (L172-178) also checked. Phase 1 row → AD-21's grader-separation reference. Phase 2 row → AD-13 (assertions before implementation) + AD-19 ordering. Phase 3 row → AD-21 L205 (semantically-wrong parts) + AD-13 ("Spec assertions ... authored independently"); intent's "convergence = assertions pass, never 'loop finished'" is homed in AD-21's conjunctive done-condition. Phase 4 row → AD-17 L173 ("HTTP 200 for a bad part" is AD-17's named Prevents) + AD-6 (geometry diff on revisions). Skills row → AD-14/AD-15.

### 5. Phase exit criteria

**Phase 0 (L195-199).** L195 MCP server starts inside FreeCAD + headless → AD-2 L53, with an **explicit amendment note**: "*Deliberate amendment of intent.md Phase 0 wording ('MCP server starts inside FreeCAD'): the addon starts the RPC listener AND **auto-spawns the external MCP protocol server** as a child process...*". Not silent; the reasoning (AD-12 forbids importing `mcp` inside FreeCAD) is sound and the operator experience is preserved. L196 ≥15 tools → findings. L197 `verify.shape` fields + 5 reference models ±0.1 % → AD-9 L109 pins ±0.1 % for STEP round-trip and correctly excludes mesh ("Mesh volume tolerance derives from deflection, never ±0.1 %"); the 5-model count is unhomed like the other counts. L198 CI ≥30 tests → findings. L199 Round-trip STEP ±0.1 % → AD-9 L109 exact: "STEP is the canonical round-trip (AP214/AP242, `write.step.unit=MM` pinned per call, ±0.1 %)".

**Phase 1 (L216-221).** L216 50 questions ≥80 % → AD-14 L149 sets R=3 for "Phase 1 answer eval" and Conventions L242 requires the Wilson CI banner. L217 tiered n=10→n=30 → AD-14 L149 **matches exactly**: both say grade n=10 first, pass ≥8/10, escalate to the sealed n=30 only on 10/10, Wilson CI reported, below 10/10 concludes at n=10 flagged low-confidence. Verified word by word — clean. L218 ≥50 features / context limits → findings. L219 latency ≤15 s median → AD-24 L229 exact. L220 ≥2 LLM backends → Structural Seed L274 `local[llama.cpp local backend]` + L290 `local -- stdio --> fast`; Deferred L332 pins the choice at the Phase 1 gate. Homed. L221 Track A drafting starts → AD-15 store; Adapters row L28 marks the skills loader "*(planned, Phase 1)*". Consistent phasing.

**Phase 2 (L238-243).** L238 40 commands ≥85 % → threshold not restated in spine (count class). L239 100 % post-verification + automatic rollback → AD-5 L77 makes post-verify and abort unconditional in every mutation; "Rollback success is measured, never assumed" is stronger than intent. L240 Undo restores exactly, verified by geometry hash → AD-6 L85 (single `fingerprint()` definition) + AD-5 ("re-hash and compare to prove rollback"). Intent's "verified by geometry hash" is exactly AD-6's reason to exist — AD-6 is not an orphan. L241 TNP guard, 5 provoking scenarios → AD-7 L93. L242 DoF = 0 in ≥90 % → AD-8 L101: "PASS ⇔ `sketch.FullyConstrained == True`, read after `doc.recompute()`". L243 Track A remainder + Track B drafts + ablation deltas → AD-15.

**Phase 3 (L260-265).** L260 20 specs ≥70 %, ≤3 self-repairs → Capability Map L320 "Phase 3 designer loop \| plan/execute over Phase 2 tools \| AD-5, AD-13, AD-14, AD-21, AD-24". L261 watertight, recompute-clean, DoF = 0, named parameters → AD-5 + AD-8 + AD-11 VarSet façade. L262 Editability ≥90 % → AD-11. L263 10 corrupted plans, ≥9 detected → AD-13's ≥10-case fault-injection bar covers the mechanism. L264 ≤10 min median → AD-24 L229 exact. L265 12 skills validated → AD-14/AD-15; the failure-feedback clause is in findings.

**Phase 4 (L282-286).** L282 20-spec headless ≥70 % → AD-18 + Capability Map L321. L283 15 revisions ≥70 %, diff confined → AD-6 L83 binds "revision diffs"; AD-17 L173. L284 machine-readable validation report + STEP + STL re-import → AD-17 L173 (`ValidationReport` owned by contracts from Phase 0 — this directly answers intent's "schema rework at Phase 4" risk) + AD-9 pairing. L285 Agent-to-agent cycle → Structural Seed L276 `a2a[external agent - Phase 4]` + L291 `a2a -- HTTP --> fast`; AD-3 L61 routes Phase 4 over streamable HTTP. L286 50-job soak, memory <20 %, structured error never silent → AD-24 L229 exact, including "every failed job still fails with a structured AD-17 status, never silently".

### 6. Phase 5 candidates (L300-306)

| Candidate | Spine home | Creep? |
|---|---|---|
| L300 Assemblies | Deferred L341, with a sequencing note making it the first Phase-5 epic; Deferred L340 (`JointObject.py` wrapper) | No |
| L301 Robot-description export (URDF/SDF) | AD-22, scoped "Phase 5 capability (Epic 7)" at L209; Stack L262-264; Deferred L344 | No. SRDF deferral (intent L301) is mirrored at Deferred L346 with the same reasoning. Implicit-CAD rejection mirrored at L347. |
| L302 Off-the-shelf part sourcing | AD-23, scoped "Phase 5 capability (Epic 7)" at L217; Deferred L345 | No |
| L303 Drawings (TechDraw) | AD-21 L205 pulls dimensioned TechDraw projections into **Phase 3** | **Not silent.** AD-21 L205 carries an explicit note: "*Deliberate amendment of intent.md: 'Drawings — auto-generated TechDraw sheets' is listed there as a Phase 5 candidate, and 'Vision feedback' as exploratory. Both are pulled forward into Phase 3 as a fail-closed done-condition...*" with reasoning and a stated cost ("auto-dimensioning and headless TechDraw export land on the Phase 3 critical path"). Scored fine per the task's amendment rule; the reasoning holds — geometry assertions genuinely cannot catch semantic wrongness. |
| L304 Optimization loops / FEM | Deferred L342, with the correct gate: "Would need a new oracle class (CalculiX/gmsh) under the AD-13 validator rules before any claim is citable" | No |
| L305 Vision feedback | AD-21, same amendment note as L303 | Not silent |
| L306 Reverse tasks | Deferred L343: "inverts the whole verify-first direction (no spec to assert against), so it needs its own validation design before an AD is worth writing" | No |

All seven Phase-5 candidates are accounted for. Two are pulled forward, both under one explicit amendment note.

### 7. Risk rows (L326-333), each mitigation leg

| Risk | Mitigation legs | Homed |
|---|---|---|
| L326 TNP | (a) reference datums/named features → AD-11 shim `AttachmentSupport` accessor + Conventions L238/L247; (b) re-resolve check after every mutation → AD-5 + AD-7; (c) benchmark includes TNP cases → AD-7/AD-13 | All three |
| L327 LLM hallucinates API | (a) no free-form `exec` in mutation path → AD-4 L69 verbatim; (b) per-step geometry verification → AD-5; (c) rollback on failure → AD-5 | All three |
| L328 FreeCAD version drift | (a) pin supported versions → AD-11 L125 + Stack L255; (b) CI matrix → AD-11 + Structural Seed L307; (c) thin adapter layer → AD-11 "All version-sensitive calls live in one shim module". Note: intent names "0.21/1.0+" as the drift span; AD-11 declares 0.21 **unsupported**. That is a scope decision, not drift — intent L328 asks for a pinned matrix, not for 0.21 support, and no intent criterion requires 0.21. | All three |
| L329 Agent self-grades | (a) validation before implementation → AD-19; (b) actor never grades itself → AD-13/AD-21/AD-17/AD-24; (c) held-out sets → AD-13/AD-14; (d) human audit sampling → AD-19 | All four |
| L330 Evals too easy | (a) benchmarks land before phase code → AD-19; (b) real-world provenance → AD-16; (c) sensitivity ≥95 % by fault injection → AD-13 | All three |
| L331 Headless vs GUI differences | "Every phase's suite runs headless in CI from Phase 0 onward" → AD-2 L53 ("Same use-case implementations in all modes"), AD-1, Environments L310 (`FreeCADCmd run_tests.py`), Conventions L246 (stdlib `unittest` under FreeCADCmd) | Yes |
| L332 Skills stale | (a) ablation rule → AD-14/AD-15; (b) version-pinned accuracy review → **unhomed, findings**; (c) failure analyses feed back → **unhomed, findings** | 1 of 3 |
| L333 Scope creep into Phase 5 | "Phase gates: no phase starts until previous exit criteria all checked" → AD-19 L189 ("Phase *N* implementation may not begin until its Validation Design Gate lands"). AD-19 gates on the *Validation Design Gate* landing, not on the previous phase's exits being checked — a slightly different hinge, but intent's phase-gate discipline is stated in the Phases preamble (L184) and AD-19 is its architectural expression. Accepted. | Yes |

### 8. Out-of-Scope rows (L337-340) — violation check

| Out-of-scope item | Grep result | Verdict |
|---|---|---|
| L337 Training / fine-tuning ML models | Grepped `fine-tun`, `training` — **no matches** in the spine | Clean. Stack L256-264 lists no training stack; Deferred L332 pins an *existing* local model (Qwen3-30B-A3B), inference only. |
| L338 CAM / toolpath generation | Grepped `CAM`, `toolpath` — **no matches** | Clean |
| L339 Photorealistic rendering pipelines | Grepped `photorealistic`, `Photoreal` — **no matches**. Rendering in the spine is AD-10 (≤1920 px preview) and AD-21 (≥2048 px judge images, TechDraw projections) — verification renders, not photorealism. Environments L310 uses "software-GL". | Clean |
| L340 Cloud multi-tenant SaaS | Grepped `SaaS`, `multi-tenant` — **no matches**. Environments L310 states the opposite: "Phase 4 service = supervisor + sandboxed worker pool, **single-tenant local-first**". AD-18 L181 reinforces it: workers "network-free (egress deny-by-default)". | Clean, and positively confirmed |

No out-of-scope violations found.

### 9. Orphan-AD pass

Every AD traced to an intent basis. Checked individually:

AD-1 → L49 (runs in GUI and headless). AD-2 → L49 + L192. AD-3 → L49/L279. AD-4 → L327 risk ("no free-form `exec` in mutation path") + L192 ("Python execution sandbox"). AD-5 → L239/L240. AD-6 → L240 ("verified by geometry hash") + L283 (geometry diff). AD-7 → L241/L326 + Reuse Map L71. AD-8 → L242/L262. AD-9 → L199/L284 + Reuse Map L64. AD-10 → L22/L235 (preview/diff, user confirms). AD-11 → L328 risk. AD-12 → L49 + Reuse Map L65. AD-13 → L150/L153/L164. AD-14 → L129/L130/L131/L153/L217. AD-15 → L124/L127/L128. AD-16 → L154 + Reuse Map L66. AD-17 → L284/L286 + L177 (Phase 4 self-deception row). AD-18 → L279 ("resource limits, iteration caps, sandboxed execution, full audit log"). AD-19 → L146/L160-166. AD-20 → L192 (document lifecycle) + L235. AD-21 → L303/L305, pulled forward under an explicit amendment. AD-22 → L301 + Reuse Map L72. AD-23 → L302 + Reuse Map L73. AD-24 → L219/L264/L286.

**No orphan ADs.** The spine invents no architecture without an intent basis.

### 10. Internal-consistency pass inside the spine

Checked pairs that could disagree:

- **AD-10 (≤1920 px) vs AD-21 (≥2048 px).** Not a conflict. AD-10 L117 scopes its cap: "The ≤1920 px cap is the **user-facing** budget — it governs images that travel through client context. Judge-directed images (AD-21 visual set) go straight to the judge API and carry their own legibility floor instead." AD-21 L205 states the reciprocal carve-out. Both sides state it — clean.
- **AD-5 (per-mutation verification) vs AD-21 (visual leg).** AD-21 L205 closes the loop explicitly: "Per-operation verification (AD-5) stays geometry-only — the visual leg runs per part, not per mutation." Clean.
- **AD-14 repeat rules (R≥10) vs AD-14 tiered screen (n=10).** AD-14 L149 separates them: "The R≥10 repeat rules above govern ablation and pp-threshold claims, not this screen." Clean.
- **AD-4 (`debug_exec` operator-only) vs AD-18 (OS-level isolation).** AD-4 L69 defers the boundary to AD-18 by name. Clean.
- **AD-1 (Gui only in hosts) vs Ring table L28 (render probe in adapters).** AD-1 L45 names the single exemption: "with one named `adapters/` exemption: the render capability probe (`adapters/render_probe.py`)", and states that `adapters/marshal.py` holds no Qt import. The Ring table L28 lists `render probe` under Adapters, consistent. Clean.
- **AD-9 (export oracles external) vs AD-12 (in-FreeCAD stdlib-only).** AD-9 L109 resolves it: "`verify_export_*` is orchestrated on the external-process side (that's where the oracles live); the FreeCAD self-read leg runs in-FreeCAD via RPC." Clean.
- **AD-20 (documents only via `document_*`) vs AD-23 (STEP import).** AD-23 L221 cites AD-20 and repeats the ban: "never a raw `App.open` alongside the bridge (AD-20)". Clean.
- **Deferred L341 (Assemblies, Phase 5) vs AD-22 (needs the Assembly tree).** Deferred L341 carries the sequencing note; AD-22 L213 names the same dependency. Clean.
- **Capability Map vs ADs.** Spot-checked all 11 rows against the ADs they cite. L318 "Phase 1 assistant (read-only) \| AD-4 (zero mutation)" matches intent L213 "Zero mutation tools exposed in this phase". L322/L323/L324 all carry "deferred detail" and match their Deferred rows. No row cites an AD that does not govern it.
- **Stack vs ADs.** L255 FreeCAD versions match AD-11 L125. L256 MCP SDK matches AD-3/AD-10. L257-258 oracles match AD-9. L262-264 Phase-5 entries match AD-22. Clean.

One observation, not scored as a finding: AD-15 L157 embeds implementation status inside an invariant — "enforcement by `scripts/check_skill_shape.py` in CI is **required and not yet built** (Story 6.1); until it lands the cap is convention only". This is current state rather than history, so it satisfies the artifact rule, but it will need deleting when Story 6.1 lands or the spine goes stale.

---

## Summary count

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 3 |
| LOW | 4 |
| **Total** | **8** |

By drift class: contradiction 0 · **internal inconsistency 1** (AD-14 skill-leg ladder) · **silent weakening 1** (gate timebox) · **unhomed 5** (accuracy review, failure feedback, context-limit budget, Phase 0 counts, eval-framework survey half) · orphan AD 0 · **scope creep 0** (both Phase-5 pull-forwards carry explicit amendment notes) · out-of-scope violations 0 · **catalog gap 1** (Phase-5 skill group / Track C).

**Verified clean and explicitly checked:** the L217 ↔ AD-14 tiered ladder matches word for word; all five Validation Design Gate checkboxes are homed in AD-19; all seven Validation-First principles are homed; all 13 Reuse Map rows are homed on both halves except L68's survey half; all seven Phase-5 candidates are homed; all four Out-of-Scope rows are clean with zero spine violations; all 24 ADs trace to an intent basis with no orphans; nine potentially-conflicting AD pairs were checked and each states its own carve-out.

**The single highest-value fix** is the AD-14 skill-leg ladder (HIGH). It is one sentence, and until it lands the `freecad-troubleshooting` exit criterion at intent L131 cannot be satisfied and cited at the same time.
