# Phase Gates — Agent-Executable Validation Contracts

Companion to `SPEC.md`. One gate per phase (G0–G4) plus the Skills track (GS). Each gate = **goal**, **entry gate** (the AD-19 Validation Design Gate that must land before phase implementation — always: threat list, benchmark runnable against a stub and failing honestly, ≥10-case fault-injection suite at the sensitivity bar, grading rubric where judgment is needed, and a recorded reuse survey), and an **exit criteria table** whose checks an AI agent executes and whose verdict it computes mechanically.

## Global protocol — how an agent validates a gate

1. **Run** each criterion's check via the gate runner (`benchmarks/`); every check emits the contracts-owned `ValidationReport` (AD-17) with the report banner (FreeCAD version, `ElementMapVersion`, validator sensitivity, Wilson CI where a rate is claimed).
2. **Read** the reports; a criterion passes only by its stated pass rule evaluated on report fields — never on log absence, exit-code-0 alone, or the producing agent's claims (AD-13).
3. **Verdict:** gate = PASS iff (a) every non-human criterion passes, (b) every cited validator's current fault-injection run shows sensitivity ≥95 % / false-alarm ≤5 %, (c) exit runs used the sealed held-out set at R≥10 with majority-of-R scoring and dev/held-out gap ≤15pp (AD-14), and (d) the human-only steps below carry a recorded sign-off token in the gate report.
4. **Human-only steps** (agent checks *presence of the recorded artifact*, never performs them): spot-audit of ≥20 % of passing results (any false pass invalidates the run — fix validator, re-run, re-audit), grading-rubric authorship/review, GUI-host smoke check, skills accuracy review (GS.5).
5. **Self-deception counters:** each phase lists its threat→counter map; the counter must exist as a planted case in that phase's fault suite before the gate can be cited.

Statistics shorthand used below — **[stats]** = majority-of-R scoring, Wilson 95 % CI reported beside the rate, R=5 dev runs / R≥10 sealed exit runs, per-repeat distribution attached.

---

## G0 — Phase 0: Bridge & Test Harness

**Goal:** FreeCAD programmatically drivable and verifiable via MCP, identically in-GUI and headless. No AI.

**Entry gate G0.E:** verify-tool fault-injection suite (≥10 planted faults: wrong volume, non-watertight, dropped solid, unit lie, degenerate face…) lands and scores sensitivity ≥95 % / FA ≤5 % against 5 hand-made reference models; golden-model benchmark runs against a stub bridge and fails honestly; reuse survey recorded.

| ID | Criterion | Agent-executable check | Pass rule |
| --- | --- | --- | --- |
| G0.1 | MCP server reachable in both hosts | Headless: connect via stdio, `tools/list`, call one tool per namespace. GUI: same over streamable HTTP against addon-started listener | Both transports list + call successfully; GUI leg additionally carries human smoke token |
| G0.2 | ≥15 tools across `query_`/`document_`/`export_` | Introspect tool registry; validate every tool has JSON schema + docstring | count ≥15 ∧ 100 % schema-valid |
| G0.3 | `verify_shape` correct on golden models | Run golden suite: 5 reference models with known volume/bbox/counts | All fields within ±0.1 % on all 5 |
| G0.4 | Headless CI green on matrix | Query CI run for HEAD: legs 1.0.x + 1.1.x | ≥30 tests, all green, both blocking legs |
| G0.5 | STEP round-trip fidelity | Run round-trip test: create → export STEP → re-import → compare | Volume ±0.1 %, `isValid`, topology counts equal |

**Threats → counters:** "tool returned OK but geometry wrong" → G0.3 golden values authored independently from implementation; "works in dev, dies headless" → G0.4 runs only under FreeCADCmd.

---

## G1 — Phase 1: Read-Only Assistant

**Goal:** LLM answers questions about the open document correctly using read-only tools; zero mutation tools exposed.

**Entry gate G1.E:** 50-question eval set + written grading rubric with worked pass/fail examples (human-authored, independent-grader-executable) land; a 30-case broken-document fixture set is built (gate grades n=10 first, escalates to n=30 on 10/10 — G1.2); planted wrong-but-confident answer cases prove the grader flags them (sensitivity run); eval runs against a stub assistant and fails honestly.

| ID | Criterion | Agent-executable check | Pass rule |
| --- | --- | --- | --- |
| G1.1 | Answer quality | Run 50-question eval, R=3; independent grader model scores per rubric [stats] | pass rate ≥80 % |
| G1.2 | Error diagnosis | 30-case fixture set; grade first n=10 (grader checks *the* failing object + cause named); escalate to full n=30 only when n=10 is 10/10 | n=10 ≥8/10 to pass; 10/10 escalates to n=30 with Wilson CI; below 10/10 concludes at n=10 (low-confidence flag, Wilson CI attached) |
| G1.3 | Large-tree handling | Run tree-explanation on 50+-feature docs; measure context + latency | No context overflow; summarized queries used; median latency ≤15 s over eval set |
| G1.4 | Model-agnostic bridge | Re-run G1.1 sample on second backend (local model, same tools) | Both backends complete the eval through identical tool surface |
| G1.5 | Skills drafted + loaded | Check `skills/` for `freecad-fundamentals`, `freecad-troubleshooting` (4-section shape, AD-15); eval logs show them loaded | Present, CI shape-check green, load recorded in run logs |
| G1.6 | Read-only guarantee | Introspect tool registry exposed to the assistant | Zero mutation tools registered |

**Threats → counters:** fluent-plausible-wrong → rubric keyed to exact expected findings + planted confident-wrong cases; diagnosis names *an* object not *the* object → grader matches expected object identity.

---

## G2 — Phase 2: Copilot (Confirmed Single Operations)

**Goal:** One NL command → one verified operation: structured-diff preview, confirm, execute, auto-verify, provable rollback.

**Entry gate G2.E:** 40-command benchmark with per-command geometry assertions (authored before implementation) lands and fails honestly against a stub; fault suite covers wrong-parameter runs, the 5 TNP-provoking scenarios, the dress-up silent-drop and coincidental-hash cases, and rollback-boundary (#6031-pattern) cases; sensitivity ≥95 % / FA ≤5 %.

| ID | Criterion | Agent-executable check | Pass rule |
| --- | --- | --- | --- |
| G2.1 | Command benchmark | Run 40 commands × 8 op types on reference models, R=5; per-command geometry assertions [stats] | ≥85 % first-attempt pass |
| G2.2 | Universal post-verify + rollback | Inject failing ops; read audit log + reports | 100 % of executed ops show post-verify record; every failed verify shows automatic rollback + human-readable explanation |
| G2.3 | Exact undo | For every benchmark op: fingerprint before, mutate, undo, fingerprint after (AD-6) | Hash-identical in 100 % of cases (snapshot-restore path counts, and is reported when taken) |
| G2.4 | TNP guard | Run 5 TNP-provoking scenarios through the guard | 5/5 flagged; zero false-clean; `UNSUPPORTED` never reported on matrix legs |
| G2.5 | Fully constrained sketches | Run sketch benchmark; read `verify_sketch` reports | `FullyConstrained == True` in ≥90 % (AD-8 pass signal; redundants warn only) |
| G2.6 | Skills + ablation harness | Shape-check 6 newly drafted skills; run ablation with declared subsets | Harness reports per-skill paired deltas in AD-14 format |

**Threats → counters:** "op ran but wrong geometry" → assertions check intent (right pocket, right place, right depth), not recompute success; "rollback assumed" → G2.3 hash proof; "silent reference re-point" → G2.4 mapped-name diff incl. count-drop.

---

## G3 — Phase 3: Designer (Spec-to-Part)

**Goal:** Written spec → plan → verified multi-step build → measured against spec assertions → self-repair ≤3 iterations → clean parametric part.

**Entry gate G3.E:** 20 written specs (real-world provenance per AD-16) each compiled to assertion primitives (AD-13 vocabulary: `count_cylindrical_holes`, `hole_spacing`, `expect_bbox`, anchor-frame declared per spec), split dev/held-out and sealed; 10 corrupted-plan fault cases; assertion-layer sensitivity ≥95 % / FA ≤5 % on planted-wrong parts (missing hole, wrong diameter, mirrored, off-spacing). **Visual judge (AD-21) landed and fault-tested**: independent vision model + structured checklist over the standard visual set (3D iso + focus views + **dimensioned TechDraw front/top/right projections** auto-generated from driving parameters on a TempDoc); planted visually-wrong parts (mirrored part, missing flange, wrong proportions, feature on wrong face) **+ planted wrong-dimension-callout drawings** — judge sensitivity ≥95 % / FA ≤5 % before its verdicts count. **Headless TechDraw page-export spike** resolved (TechDrawGui dependency risk) before implementation.

| ID | Criterion | Agent-executable check | Pass rule |
| --- | --- | --- | --- |
| G3.1 | Spec benchmark | Run 20 specs end-to-end, human approves plan once; convergence = **geometry assertions pass ∧ visual judge PASS** (AD-21; never iteration cap); sealed held-out at exit, R≥10 [stats] | ≥70 % pass within ≤3 self-repairs; dev/held-out gap ≤15pp |
| G3.2 | Artifact hygiene | For every generated part read verify reports | 100 %: valid watertight solid, recompute-clean, all sketches `FullyConstrained`, driving dimensions exposed as named parameters |
| G3.3 | Editability | Script one driving-parameter change per passing part; recompute; verify | ≥90 % recompute without errors |
| G3.4 | Self-verification catches faults | Run 10 corrupted-plan cases through the loop | ≥9/10 spec violations detected; zero silent bad parts |
| G3.5 | Throughput | Read wall-clock from run reports | Median ≤10 min per part |
| G3.6 | Skills track convergence | See GS; `design-decomposition` claim on its dedicated n≥40 set | GS criteria met per AD-14 |
| G3.7 | Visual verification leg (AD-21) | For every passing part read the `verify_visual` report: independent judge (never the actor), standard visual set (iso + focus + dimensioned TechDraw per-axis projections) + spec checklist, temperature 0 | 100 % of passing parts carry visual judge PASS; render/drawing/judge unavailable → not done (operator waiver audit-logged only) |

**Threats → counters:** "measures what it built, not what was asked" → assertions authored at G3.E, independent of any plan; "loop declares convergence by cap" → convergence defined as assertion-∧-visual pass in the runner itself; "plausible plan, deviant part" → artifact-level geometry assertions primary; "geometry passes but part visually/semantically wrong" → independent visual judge, conjunctive (AD-21); "actor grades own render" → judge model/context separation enforced at preflight.

---

## G4 — Phase 4: Autonomous Service

**Goal:** Phase 3 loop as a headless single-tenant service: job API, revisions, validation reports, sandboxed workers.

**Entry gate G4.E:** soak + fault harness lands first and fails honestly against a stub service: planted infinite-loop → `TIMEOUT`, unbounded-alloc → `OOM_KILLED` (sandbox, not host OOM), OCCT segfault → `WORKER_CRASHED` + pool refill, wrong-part-with-pretty-report → supervisor re-check flags `SPEC_FAILED`; ≥95 % caught. Revision-diff checker fault-tested (unrelated-feature change planted → flagged).

| ID | Criterion | Agent-executable check | Pass rule |
| --- | --- | --- | --- |
| G4.1 | Headless parity | Run the 20-spec Phase 3 benchmark via job API on CI, zero GUI [stats] | ≥70 % maintained |
| G4.2 | Revisions | Run 15 modification requests against prior results; geometry diff vs request scope | ≥70 % succeed with diff confined to the requested change |
| G4.3 | Deliverables complete | For every job read `ValidationReport` + exports | Report schema-valid with supervisor-re-executed check fields **including the AD-21 visual judge verdict** (rendered views ship with the job); STEP + STL present and re-import clean |
| G4.4 | Agent-to-agent proof | External MCP-client agent drives submit → inspect → revise → accept | Full cycle completes with zero human input |
| G4.5 | Robustness soak | 50-job soak run; sample supervisor+worker RSS at job boundaries | No crash/hang; memory growth <20 %; every failure carries a closed-set structured status (AD-17), none silent |

**Threats → counters:** "HTTP 200 for a bad part" → G4.3 supervisor re-executes checks; "revision breaks unrelated feature silently" → G4.2 confined-diff assertion; "leak hidden by restart luck" → G4.5 boundary sampling per job.

---

## GS — Skills Track (runs alongside Phases 1–3)

**Goal:** 12 Track A+B skills that measurably move benchmark metrics; loadable by ≥2 harnesses.

**Entry gate GS.E:** ablation harness (forced explicit-subset injection, auto-activation disabled, AD-15) lands and demonstrates a clean A/B on a dummy skill; skill shape check (4 sections, ≤1,500 words) wired into CI.

| ID | Criterion | Agent-executable check | Pass rule |
| --- | --- | --- | --- |
| GS.1 | 12 skills authored, dual-harness | Shape-check all 12; load each via native activation AND forced injection; run one benchmark case per path | All 12 pass shape check and load on both paths |
| GS.2 | Ablation harness operational | Run any benchmark with `--skills <subset>`; verify complement excluded from context | Declared subset in, complement out, per-skill paired deltas reported in AD-14 format |
| GS.3 | Measurable lift | Run per-skill ablations on Phase 2/3 benchmarks | ≥8/12 skills significant per AD-14 (McNemar p<0.05 ∧ CI excludes 0); rest revised or cut; sub-detection effects reported as such |
| GS.4 | `freecad-troubleshooting` | Re-run G1.2 tiered cases with skill loaded, R≥10; grade n=10 first, escalate to n=30 only when n=10 is 10/10 | n=10 ≥9/10 to pass; 10/10 escalates to n=30 with Wilson CI; below 10/10 concludes at n=10 (low-confidence flag, CI attached) |
| GS.5 | Accuracy review | Check for recorded owner review vs version-pinned FreeCAD docs | Human sign-off token present for all 12 |
| GS.6 | `design-decomposition` | Run dedicated ≥40-spec paired ablation, R≥10 | ≥+15pp first-plan success, McNemar p<0.05, CI excludes 0 |

**Threats → counters:** "skill sounds authoritative, measures nothing" → GS.3 ablation rule; "activation nondeterminism pollutes A/B" → forced injection with auto-activation disabled; "skill helps only via another skill" → no cross-skill body deps (AD-15) + per-skill isolation in deltas.
