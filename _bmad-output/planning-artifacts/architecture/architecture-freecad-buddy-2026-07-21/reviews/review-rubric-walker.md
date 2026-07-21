# Rubric-Walker Review — ARCHITECTURE-SPINE.md (freecad-buddy)

- Reviewer: rubric-walker
- Date: 2026-07-21
- Artifact: `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/ARCHITECTURE-SPINE.md` (status: draft)
- Inputs consulted: spine (full), `docs/intent.md` (full)
- Altitude judged: initiative (keeps phases/features coherent)

## Verdict

**Approve with required fixes.** This is a strong spine: 19 ADs, nearly all with concrete, falsifiable rules and named enforcement (CI import checks, word caps, statistical thresholds, gate ordering). The mutation/verification core (AD-5..9) is tight enough that two independently built Phase 2 mutation tools would agree on transaction shape, pass signals, fingerprints, and TNP auditing. But three divergence points that the ADs do *not* fix are silent rather than deferred — sub-element addressing for mutation inputs, document targeting, and the process placement of `verify_export_*` — and each would let two conforming units diverge in ways that are expensive to reconcile later. Fix those before Phase 0 exit; everything else is refinement.

---

## Checklist walk

### 1. Does it fix the real divergence points, and miss none?

Largely yes. The classic divergence traps for this project are all nailed: geometry identity (AD-6 names the exact hash inputs and bans the tempting alternatives), "fully constrained" (AD-8 gives one boolean read at one moment), rollback semantics (AD-5 makes rollback *measured*), TNP verdicts (AD-7 layers + capability gate), stats hygiene (AD-14), and grader independence (AD-13). The two-units test passes for those.

Three misses, detailed as findings C-1, H-1, H-2 below:

- **Sub-element addressing for mutation tool inputs.** A fillet/chamfer/hole/mirror tool must accept edge/face targets. AD-13 bans index selectors (`Edge3`) *in benchmark specs only*. Nothing governs tool parameters. One Phase 2 builder will take OCC index strings (TNP-fragile — the exact trap the project exists to avoid), another will invent a semantic selector (e.g. "top face", geometric query filters). Both obey every AD; the tool surface forks at its most TNP-sensitive point.
- **Document targeting.** No convention says whether tools operate on `FreeCAD.ActiveDocument` implicitly or take an explicit document handle/name parameter. Two tools can diverge Phase 0 week one. Also interacts with concurrency: the structural seed shows three simultaneous client classes hitting one FastMCP server, but nothing states mutations are serialized per document (the main-thread marshal serializes *calls*, not multi-call transactions — an AD-5 transaction interleaved with another client's mutation breaks the snapshot/re-hash logic).
- **Where geometry truth is computed for the harness.** AD-13 says deterministic `verify_*` code decides pass/fail, but the harness lives in the external pytest process (AD-12) and could grow its own geometry evaluators (trimesh-side bbox/volume) that drift from the in-FreeCAD `verify_*` implementations. The spine never says "the `verify_*` tools are the *only* geometry oracle the harness may consult (plus the named export oracles)."

### 2. Is every Rule enforceable and divergence-preventing?

Yes, with distinction — this is the spine's best quality. Spot checks:

- AD-1: mechanically enforceable (CI no-`Gui`-import check named).
- AD-5: each step is observable; "re-hash and compare to prove rollback" converts an aspiration into a measurement.
- AD-8: single boolean, single read point — cannot be interpreted two ways.
- AD-14: exact tests (McNemar, Wilson), exact R values, exact n floor. Falsifiable.
- AD-19: gate artifacts are enumerable; "runnable against a stub, failing honestly" is checkable.

Minor softness (L-4): AD-15's "≤~10K token skill budget" is approximate ("~") where everything else is exact; and AD-17's "machine-readable detail" has no schema owner named (acceptable at this altitude, but say who locks it — presumably the same Phase 2 lock as the diff schema, see M-1).

### 3. Could anything under Deferred let two units diverge in the meantime?

Mostly no — the deferrals are well-chosen and most state why interim work is unaffected (e.g. router rules deferred because forced-subset mode is the ablation mechanism; sandbox *profiles* deferred while *posture* is fixed by AD-18). Two exceptions:

- **M-1:** "Preview diff `outputSchema` field list — locked once at Phase 2" but the row itself says the schema is "shared by preview, post-verify, and audit". Post-verify results and the append-only audit log exist from Phase 0 (AD-17: "audit log of every mutation and exec exists from Phase 0"; Phase 0 ships `document_*` mutations). So Phase 0/1 code writes audit/verify records in an unlocked shape, then Phase 2 locks a shared schema — exactly the "schema rework" AD-17 exists to prevent, in miniature.
- **L-1:** The `exportBinary` Phase 0 spike can invalidate AD-6's fingerprint definition (fallback `exportBrep` produces different bytes). Acceptable because it's week-one and pre-mutation-tools, but AD-6 should state the fallback ordering now so the spike outcome amends one line instead of reopening the AD.

Everything else deferred (LLM pin, router rules, sandbox profiles, worker tuning, slicer job, DFM layer, doc-citation channel, assembly wrapper, tolerance calibration) is safely fenced.

### 4. Named tech plausible-current?

Plausible overall (deep verification is another reviewer's job). Notes:

- MCP spec `2025-06-18` genuinely introduced elicitation + structured output; `2025-11-25` as the targeted revision is consistent with the spec cadence. Correct that SSE transport is deprecated and dots are illegal in tool names. Good.
- FreeCAD 1.0.x floor / 1.1.x primary / 1.2-dev canary, Python 3.11 bundled, conda-forge + micromamba CI: all plausible for mid-2026.
- **L-2 (flag):** `admesh` — the Python binding on PyPI has historically been barely maintained. As one of three STL oracles it's redundant-by-design, but the Phase 0 pin should confirm it installs on Python 3.11/Windows or name a substitute (e.g. `numpy-stl` or trimesh-only + FreeCAD self-read).
- llama.cpp + Qwen3-30B-A3B (deferred row): real, current-plausible.

### 5. Brownfield conflicts

N/A — greenfield confirmed. The one "legacy contract" is `docs/intent.md` itself, and the spine handles its only conflict correctly: AD-2 explicitly amends the Phase 0 wording ("MCP server starts inside FreeCAD") and says so inline. Model behavior.

### 6. Dimension sweep — decided / deferred / open / SILENT

| Dimension | Status | Note |
| --- | --- | --- |
| Deployment/environments | Decided | Environments line: dev / CI / Phase 4 service |
| CI | Decided | AD-11 matrix, workflows in seed, xvfb leg isolated non-blocking |
| Error handling | Decided | AD-17 closed set + conventions row |
| Config | Decided | Env-var + capability-probe convention |
| Logging | Decided | stderr-only, append-only JSON-lines audit |
| Security — exec & isolation | Decided | AD-4, AD-18 |
| Security — transport/auth | **SILENT** | See H-3: localhost RPC listener and streamable-HTTP endpoint have no stated auth/bind posture |
| Data ownership/persistence | **SILENT** | See M-2: where documents, job artifacts, audit logs, benchmark results live; retention; who owns the FCStd during a session |
| Observability (service) | Partially silent | See M-3: Phase 4 exit criteria require measuring memory growth/soak health, but no metrics/health decision or Deferred row exists |
| Versioning/compat of the two-process pair | **SILENT** | See L-3: addon (in-FreeCAD listener) and external server ship separately; no compat handshake stated |
| Concurrency/session model | **SILENT** | Folded into H-1: multi-client seed with no per-document mutation serialization statement |

### 7. Internal consistency

Good overall; ADs reinforce each other (AD-6 quantization ↔ conventions tolerance row; AD-12 ↔ stdlib-unittest convention; AD-4 ↔ AD-18 on "never call in-process restriction a boundary"). Two tensions:

- **H-2:** AD-9 vs AD-12. AD-9's export oracles (trimesh, admesh, lib3mf) are third-party → external process only (AD-12). But `verify_export_*` is listed as a use-case-ring tool (`export_*`/`verify_*` in `usecases/`), and AD-9 also requires a "FreeCAD self-read" oracle → in-process. So `verify_export_*` necessarily spans both processes and the spine doesn't say how it composes. Two builders could (a) put mesh oracles in usecases, violating AD-12, or (b) build two half-verifiers with different aggregation semantics. The seed's `fast --- core2` headless edge sharpens this: in headless mode the "external" process *is* the FreeCAD process (imports FreeCAD into the uv env), which blurs AD-12's "code that runs inside the FreeCAD process" test.
- **L-5:** AD-3 assigns "stdio for headless/dev/CI" while the Environments line says dev = GUI addon + external server "(HTTP)". Reconcilable (GUI-attached dev = in-GUI serving = HTTP), but "dev" appears on both sides of the split; one clarifying clause removes the ambiguity.

---

## Findings

### Critical

**C-1 — Sub-element (edge/face) addressing for mutation tool inputs is silent.**
Two Phase 2 mutation tools can both obey AD-4..8 yet fork the tool surface at its most TNP-sensitive point: one taking `"Edge3"` index strings, another a semantic/geometric selector. AD-13's index-selector ban covers benchmark specs only. This is the project's core risk (TNP) surfacing in the tool contract, and it is neither decided nor in Deferred nor an open question.
**Fix:** Add an AD (or extend AD-7): define the single sub-element addressing vocabulary for tool parameters — e.g. semantic selectors (geometric predicates: normal direction, extremal position, adjacency to named feature) resolved server-side to transient OCC names at execution time; raw index strings accepted only in `debug_*`; the resolved mapping recorded in the audit entry. If the vocabulary itself needs Phase 2 design, decide the *constraint* now ("no raw sub-element indices in any AI-visible tool schema; selector vocabulary lives in `contracts/`") and put the vocabulary in Deferred with a Phase 2 lock.

### High

**H-1 — Document targeting and per-document mutation serialization are silent.**
No convention says tools take an explicit document handle vs. implicit `ActiveDocument`; the seed shows three concurrent client classes but nothing serializes AD-5 transactions per document, so two clients' interleaved mutations can corrupt the snapshot→verify→commit sequence both are individually obeying.
**Fix:** Add a conventions row: every tool takes an explicit document identifier (default = active document resolved and echoed back in the result); one AD-5 transaction holds an exclusive per-document lock end-to-end; concurrent mutation requests queue or fail with `INVALID_INPUT`/busy detail.

**H-2 — `verify_export_*` placement contradicts the ring/process split (AD-9 vs AD-12).**
Export oracles are external-only by AD-12, FreeCAD self-read is in-process, yet `verify_export_*` is drawn as a single use-case tool. Undefined composition = two conforming-but-divergent implementations, or an AD-12 violation.
**Fix:** State it in the spine: `verify_export_*` is an adapter-orchestrated composite — in-FreeCAD use case produces the export + self-read report; external oracle runners (trimesh/admesh/lib3mf) run in the MCP process; the adapter merges per AD-9's disagreement-is-fail rule. Also add one sentence resolving AD-12's meaning in headless mode (where the uv process imports FreeCAD): the restriction keys on *code shipped as the addon/listener*, not on which process happens to host FreeCAD.

**H-3 — Transport/auth security posture for the RPC listener and streamable-HTTP endpoint is silent.**
An unauthenticated localhost RPC listener that marshals mutations (and, when enabled, `debug_exec`) into FreeCAD is reachable by any local process; same for the long-lived in-GUI HTTP transport. AD-4/AD-18 cover exec gating and Phase 4 isolation but not this surface.
**Fix:** Add a rule or conventions row: RPC listener and HTTP transport bind loopback only; shared-secret token generated per session (env/file handshake between addon and server); Phase 4 job API auth deferred to the Phase 4 gate with the posture ("no unauthenticated mutation endpoint, ever") fixed now.

### Medium

**M-1 — Deferred diff-schema lock leaks divergence into Phases 0–1.**
The preview-diff field list is "shared by preview, post-verify, audit", but audit records exist from Phase 0 (AD-17) and post-verify from first mutation. Interim record shapes will be invented, then reworked at the Phase 2 lock — the AD-17 anti-pattern in miniature.
**Fix:** Lock the *envelope* now in `contracts/` (record type, status, fingerprints-before/after, detail blob keyed by schema-version) and defer only the diff *field list*; note in the Deferred row that Phase 0/1 records must carry a schema-version field so the Phase 2 lock is additive.

**M-2 — Data ownership/persistence dimension is silent.**
No statement on where job artifacts, exports, audit logs, benchmark results, and session documents live; retention; or ownership of the open FCStd during a GUI session (user's file vs. bridge-managed copy — this interacts with AD-5's `saveCopy` restore path writing over what?).
**Fix:** Add a short "Data & artifacts" conventions row: per-job/session workspace directory layout, audit log location, benchmark results as CI artifacts, and the rule that the bridge never writes the user's on-disk file except via an explicit `document_save` tool; defer Phase 4 retention policy to the Phase 4 gate.

**M-3 — Phase 4 service observability has no decision or Deferred row.**
Phase 4 exit criteria (intent.md soak: memory growth <20%, no silent failures) require metrics/health instrumentation the spine never mentions; AD-17 covers job results, not service health.
**Fix:** Add a Deferred row: "Service health/metrics (worker RSS, job latency, queue depth; health endpoint) — Phase 4 gate; AD-17 status set already fixes the failure taxonomy they report."

### Low

**L-1 — AD-6 depends on the unspiked `exportBinary` exposure.** State the fallback ordering in AD-6 now (`exportBinary`, else `exportBrep` bytes, same sort/quantization rules) so the spike amends one word, not the AD.
**L-2 — `admesh` oracle may be stale/unmaintained on Python 3.11/Windows.** Confirm at Phase 0 pin or pre-name the substitute. (Deep verification: other reviewer.)
**L-3 — No compatibility handshake between addon (RPC listener) and external server.** Solo project, but one stale-addon session will burn a day. Fix: listener reports a protocol version on connect; server refuses mismatches.
**L-4 — Two soft spots in otherwise-exact rules.** AD-15 "≤~10K token" — pick a number and the counting method (CI-countable). AD-17 "machine-readable detail" — name where its schema locks (same Phase 2 lock as M-1).
**L-5 — AD-3 "dev = stdio" vs Environments "dev … (HTTP)".** Add a clause: "dev against GUI addon = HTTP; dev headless = stdio."

---

## What is verified vs. not

Verified: full spine text; full `docs/intent.md`; internal cross-references between ADs, conventions, seed, and deferrals; intent-vs-spine coverage of phases/capabilities. Not verified (out of scope per rubric): live currency of stack versions/dates, the 18 research reports' content, MCP spec field-level claims.
