# Phase Gates — Agent-Executable Validation Contracts

Companion to `SPEC.md`. One gate per phase (G0–G2) plus the Skills track (GS). Phase-5 work carries its own gate (`G5-robot`), specified when that phase is scoped. Each gate = **goal**, **entry gate** (the AD-19 Validation Design Gate that must land before phase implementation — always: threat list, benchmark runnable against a stub and failing honestly, ≥10-case fault-injection suite at the sensitivity bar, grading rubric where judgment is needed, and a recorded reuse survey), and an **exit criteria table** whose checks an AI agent executes and whose verdict it computes mechanically.

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

## GS — Skills Track (runs alongside Phases 1–3)

**Goal:** 15 skills — 12 Track A+B that measurably move benchmark metrics, plus the three Track W workflow skills that carry the design loop; all loadable by ≥2 harnesses.

**Entry gate GS.E:** ablation harness (forced explicit-subset injection, auto-activation disabled, AD-15) lands and demonstrates a clean A/B on a dummy skill; skill shape check (4 sections, ≤1,500 words) wired into CI.

| ID | Criterion | Agent-executable check | Pass rule |
| --- | --- | --- | --- |
| GS.1 | 15 skills authored, dual-harness | Shape-check all 15; load each via native activation AND forced injection; run one benchmark case per path | All 15 pass shape check and load on both paths |
| GS.2 | Ablation harness operational | Run any benchmark with `--skills <subset>`; verify complement excluded from context | Declared subset in, complement out, per-skill paired deltas reported in AD-14 format |
| GS.3 | Measurable lift | Run per-skill ablations on the Phase 2 and spec benchmarks | ≥8/12 Track A+B skills significant per AD-14 (McNemar p<0.05 ∧ CI excludes 0); rest revised or cut; sub-detection effects reported as such. Track W is exempt — without `design-loop` no loop exists to ablate against, so it is validated by the spec benchmark running at all |
| GS.4 | `freecad-troubleshooting` | Re-run G1.2 tiered cases with skill loaded, R≥10; grade n=10 first, escalate to n=30 only when n=10 is 10/10 | n=10 ≥9/10 to pass; 10/10 escalates to n=30 with Wilson CI; below 10/10 concludes at n=10 (low-confidence flag, CI attached) |
| GS.5 | Accuracy review | Check for recorded owner review vs version-pinned FreeCAD docs | Human sign-off token present for all 12 |
| GS.6 | `design-decomposition` | Run dedicated ≥40-spec paired ablation, R≥10 | ≥+15pp first-plan success, McNemar p<0.05, CI excludes 0 |

**Threats → counters:** "skill sounds authoritative, measures nothing" → GS.3 ablation rule; "activation nondeterminism pollutes A/B" → forced injection with auto-activation disabled; "skill helps only via another skill" → no cross-skill body deps (AD-15) + per-skill isolation in deltas.
