---
name: 'freecad-buddy'
type: architecture-spine
purpose: build-substrate
altitude: initiative
paradigm: 'clean-architecture'
scope: 'FreeCAD Buddy full system: MCP bridge (GUI + headless), verify-first tool taxonomy, skills library, validation/benchmark harness, Phase 4 service'
status: final
created: '2026-07-21'
updated: '2026-09-12'
binds: []
sources: ['docs/intent.md', '_bmad-output/planning-artifacts/research/index.md']
companions: []
---

# Architecture Spine — freecad-buddy

## Design Paradigm

> Detailed design: [Component Design](design/component-design.md) (ring inventory, interfaces, flows) · [Project Structure Design](design/project-structure.md) (repo tree, packaging).

**Clean Architecture.** Dependencies point inward only. FreeCAD's App-layer Python API is treated as the domain kernel; `FreeCADGui`/Qt are outer-ring drivers.

| Ring | Directory | Contains | May import |
| --- | --- | --- | --- |
| Contracts | `src/freecad_buddy/contracts/` | Tool schemas, result envelopes, diff/report/status types, assertion vocabulary | stdlib only |
| Use cases | `src/freecad_buddy/usecases/` | Tool implementations (`query_*`, `verify_*`, `sketch_*`, `feature_*`, `export_*`, `preview_*`), mutation protocol, TNP guard, fingerprint, capabilities, confirm, screenshot, `stats` (stdlib-only rate statistics, importable from both sides) | contracts, FreeCAD **App** modules (via version shim) |
| Adapters | `src/freecad_buddy/adapters/` | MCP server, RPC client/listener/dispatch, main-thread marshal, render probe, audit log, export oracle + verdict, ReAct adapter (second-harness path); skills loader *(planned, Phase 1)* | usecases, contracts |
| Hosts | `src/freecad_buddy/hosts/` | GUI addon (`gui_addon/`), external GUI host, headless entry, `main.py`, `tool_catalog.py` (shared tool surface — schemas, timeouts, mutating flags); Phase 4 supervisor *(planned)* | adapters |

```mermaid
graph LR
  hosts --> adapters --> usecases --> contracts
  usecases --> shim[version shim]
  shim --> fcapp[FreeCAD App API]
  hosts -. Gui/Qt allowed here only .-> fcgui[FreeCADGui / Qt]
```

## Invariants & Rules

### AD-1 — Clean Architecture dependency rule [ADOPTED]

- **Binds:** all
- **Prevents:** GUI-coupled core that silently kills headless CI; adapters reaching into FreeCAD directly
- **Rule:** Imports cross ring boundaries inward only. `FreeCADGui`, Qt widgets, and Coin are importable **only** in `hosts/` — with one named `adapters/` exemption: the render capability probe (`adapters/render_probe.py`). The main-thread marshal (`adapters/marshal.py`) holds no Qt import at all; the Qt event pump lives in `hosts/gui_addon/pump.py`, where it needs no exemption. `contracts/` imports stdlib only. CI enforces a no-`Gui`-import check on `contracts/`, `usecases/`, and the RPC listener.

### AD-2 — Process topology & main-thread marshaling [ADOPTED]

> Detailed design: [Integration Design — MCP ↔ FreeCAD](design/integration-mcp-freecad.md).

- **Binds:** adapters, hosts
- **Prevents:** background-thread FreeCAD/Qt calls (the documented crash mode); in-process asyncio-in-Qt fragility
- **Rule:** GUI mode = external MCP server process + thin in-FreeCAD RPC listener; the listener accepts off-thread and marshals every FreeCAD call to the Qt main thread (Mod/Web `postEvent` pattern); addon start is deferred until `FreeCAD.GuiUp` via `QTimer.singleShot`. Headless mode = single process, tool core called inline (no Qt loop exists); where the external interpreter cannot `import FreeCAD`, the documented fallback is the GUI topology minus Qt — `FreeCADCmd`-hosted RPC listener with inline dispatch. Same use-case implementations in all modes. The RPC wire contract (stdlib-encodable JSON-RPC frames + versioned handshake) is defined in `contracts/` — both sides import it; neither invents framing; its compatibility rule is AD-28. The connection file records the session token **and the addon PID**: the proxy validates both on every reconnect and exits once the PID it was spawned for is gone, and the addon's already-served check on `:8765` must confirm the listener is its own live proxy (probe `/healthz` for the session id) — a foreign or stale listener is an error surfaced to the operator, never a silent reuse. Without that check, a fast FreeCAD restart leaves an orphan proxy owning the port and wired to a dead listener, which the client sees as a hang rather than a status. *Deliberate amendment of intent.md Phase 0 wording ("MCP server starts inside FreeCAD"): the addon starts the RPC listener AND **auto-spawns the external MCP protocol server** as a child process — using the project venv interpreter **auto-discovered from the addon's own install path** (no env vars; it never imports `mcp`, AD-12) — so opening FreeCAD is the only operator step to reach the bridge over MCP. The internal `serve --mode rpc` CLI that runs that server is a debug/troubleshoot fallback for when auto-start is disabled or unresolvable — never the normal path.*

### AD-3 — Transport policy [ADOPTED]

> Detailed design: [Integration Design — MCP ↔ FreeCAD](design/integration-mcp-freecad.md) (RPC wire, bind/token) · [MCP Client Integration Design](design/integration-mcp-clients.md) (per-client transport).

- **Binds:** adapters
- **Prevents:** transport lock-in; deprecated-SSE adoption; stdout protocol corruption
- **Rule:** stdio for headless/dev/CI; streamable HTTP for in-GUI long-lived serving and the Phase 4 service; SSE never. Transport is a run flag on one MCP python-sdk low-level `Server` object. On the stdio path, logging goes to stderr only — `print()` to stdout is banned in server code. RPC listener and HTTP endpoint bind localhost by default; any remote bind is an explicit operator opt-in. **Both hops authenticate, in every phase.** The RPC channel carries a per-session token generated at addon start. The HTTP endpoint carries a bearer token on the same lifecycle — generated at addon start, written to the connection file, required on every request; a request without it gets 401, and `Origin` is validated against a localhost allowlist (DNS-rebinding defense). Localhost bind is not by itself an access control: the HTTP port is the complete mutation surface, so an unauthenticated `:8765` would let any local process drive the live document. Client configs read the token from the connection file; this is not a Phase 4 addition.

### AD-4 — Typed tools are the only AI mutation path [ADOPTED]

> Detailed design: [Security and Phase 4 Service Design](design/security-and-service-design.md) (§1 `debug_exec` gating) · [MCP Tool Catalog Design](design/mcp-tools-design.md) (§5 registration rules).

- **Binds:** all
- **Prevents:** LLM free-form `exec` becoming the mutation path (host RCE + unverifiable ops)
- **Rule:** AI-visible mutations exist only as typed `sketch_*`/`feature_*`/`document_*` tools. `debug_exec` is operator-only: disabled by default, enabled by human-set env flag, unregistered from the MCP tool list when off, append-only audit-logged, disabled permanently in the Phase 4 service. In-process Python restriction (RestrictedPython, audit hooks, blacklists) is never called a security boundary; isolation is OS-level (AD-18).

### AD-5 — Uniform mutation transaction protocol [ADOPTED]

> Detailed design: [Verification Subsystem Design](design/verification-design.md) (§1 `run_mutation` wrapper).

- **Binds:** every mutation tool
- **Prevents:** per-tool divergent safety handling; trusting undo (FreeCAD bug #6031); silent partial rollback
- **Rule:** Every mutation runs: geohash snapshot → `openTransaction` → typed op → `recompute()` → post-verify (recompute clean, `Shape.isValid()`, `FullyConstrained` where sketches involved, TNP audit) → `commitTransaction`. Any failure: `abortTransaction` → `recompute()` → **re-hash and compare to prove rollback**; on mismatch, restore from the pre-mutation `saveCopy` snapshot and re-verify. Rollback success is measured, never assumed. Undo history is bridge-owned — no mutation outside a bridge transaction. The snapshot's location, naming, and deletion are fixed by AD-25 — a restore that cannot find its snapshot is a failed rollback, never a silent pass.

### AD-6 — Geometry fingerprint definition [ADOPTED]

> Detailed design: [Verification Subsystem Design](design/verification-design.md) (§2 `fingerprint()`) · [Data Contracts Design](design/data-contracts-design.md) (§10 `FingerprintRecord`).

- **Binds:** mutation protocol, undo verification, revision diffs
- **Prevents:** two incompatible "geometry hash" implementations; nondeterministic oracles
- **Rule:** Document fingerprint = SHA-256 over per-object shape bytes, objects sorted by immutable `Name`, plus a quantized mass-property tuple (volume, area, bbox, COM, principal moments @1e-6) as independent cross-oracle. Exactly one `fingerprint()` implementation exists (usecases); the serializer is shim-probed (`exportBinary`, else `exportBrep` stream) and every hash is tagged with its serializer id — comparing hashes across serializer tags is banned. Document-XML/FCStd hashing and tessellation hashing are banned as identity oracles.

### AD-7 — TNP reference audit [ADOPTED]

> Detailed design: [Verification Subsystem Design](design/verification-design.md) (§3 TNP guard, layers 0–2).

- **Binds:** every mutation tool; verification reports
- **Prevents:** silent reference re-point/drop passing as success; false-clean verdicts on unsupported versions
- **Rule:** `snapshot_references` before mutation, `audit_references` after recompute. Layer 0: sweep `isValid()` + `getStatusString()`. Layer 1: diff mapped names — flag `?`-markers, silent re-points, and count drops (the `FeatureDressUp` silent-drop trap). Layer 2 (`getElementHistory`) only where Layer 1 is ambiguous. Capability-gated: no element map → report `UNSUPPORTED`, never clean. Every report records `ElementMapVersion`; a version bump re-baselines, it does not fail.

### AD-8 — Sketch pass signal [ADOPTED]

> Detailed design: [Verification Subsystem Design](design/verification-design.md) (§4 `verify_sketch`).

- **Binds:** verify tools, benchmark graders, repair loops
- **Prevents:** grader and verifier disagreeing on "fully constrained"; inferring DoF from `solve() == 0`
- **Rule:** PASS ⇔ `sketch.FullyConstrained == True`, read after `doc.recompute()`. Hard fail on conflicting/malformed/over-/under-constrained or degenerate geometry; redundant constraints warn, never fail. `solve()` return codes are logging only.

### AD-9 — Export/verify pairing [ADOPTED]

> Detailed design: [Verification Subsystem Design](design/verification-design.md) (§6 `verify_export_*`).

- **Binds:** all export tools
- **Prevents:** "bytes were written" counted as success; STL/3MF silently diverging; format-specific writer bugs shipping
- **Rule:** Every `export_*` completes only through its paired `verify_export_*` re-import check. STEP is the canonical round-trip (AP214/AP242, `write.step.unit=MM` pinned per call, ±0.1 %). One tessellation source — `MeshPart.meshFromShape` with linear **and** angular deflection — feeds both STL and 3MF. Oracles: trimesh primary + one independent second checker (admesh where available — dormant upstream, Linux-leaning; fallback second oracle chosen at the Phase 0 gate) for STL; lib3mf + trimesh + FreeCAD self-read for 3MF. `verify_export_*` is orchestrated on the external-process side (that's where the oracles live); the FreeCAD self-read leg runs in-FreeCAD via RPC. Independent-oracle disagreement = fail. Mesh volume tolerance derives from deflection, never ±0.1 %. **The `export_*` tool itself invokes its verify leg** and returns one envelope: `OK` only when that leg passed, otherwise the leg's status, and a failed export leaves no file at the target path. The standalone `verify_export_*` tools exist to re-check an already-written file; they are never the only thing standing between a write and an `OK`. (Fixing the relation without fixing the invoker would let one export tool return `SPEC_FAILED` and delete while its sibling returns `OK` and leaves a bad file.)

### AD-10 — Preview/confirmation channel [ADOPTED]

> Detailed design: [MCP Client Integration Design](design/integration-mcp-clients.md) (§4 confirmation matrix, §5 image rules) · [Data Contracts Design](design/data-contracts-design.md) (§8 `GeometryDiff`).

- **Binds:** Phase 2+ mutation UX, all three client contexts (GUI panel, MCP client, headless)
- **Prevents:** preview design that assumes a GUI; confirmation gated on pixels; image token blow-ups
- **Rule:** `preview_dry_run` executes on a `copyObject` TempDoc and returns a structured diff (Δvolume/area/bbox/COM, face/edge/solid counts, touched/new/deleted nodes, validity, TNP pre-check) validated by its `outputSchema` — the mandatory payload. Renders are optional and capability-gated (GUI `saveImage` / offscreen-Xvfb / omit), ≤1920 px, `audience:["user"]`, `resource_link` preferred over inline base64. The ≤1920 px cap is the **user-facing** budget — it governs images that travel through client context. Judge-directed images (AD-21 visual set) go straight to the judge API and carry their own legibility floor instead. Confirmation: MCP elicitation (`accept`/`decline`/`cancel`) with client-confirm fallback; headless is fail-closed unless an explicit `autoApprove` flag, and every auto-approval is audit-logged. Apply re-runs the op on the live document under AD-5.

### AD-11 — Version matrix & shim [ADOPTED]

> Detailed design: [Integration Design — MCP ↔ FreeCAD](design/integration-mcp-freecad.md) (§5 `shim.py`) · [Project Structure Design](design/project-structure.md) (§3 version legs).

- **Binds:** all FreeCAD-touching code; CI
- **Prevents:** version-sensitive calls scattered through use cases; incomparable TNP metrics across legs
- **Rule:** Supported: FreeCAD 1.0.x (floor, blocking CI) and 1.1.x (primary, blocking); 1.2-dev weekly is an allowed-to-fail canary; 0.21 unsupported. All version-sensitive calls live in one shim module: `AttachmentSupport`/`Support` accessor, `element_map_available()` probe (hard-gates AD-7), `addObject` type-string table, VarSet-with-Spreadsheet-fallback driving-dimension façade. Capability probes, never version-string comparisons, gate behavior. Round-trip fixtures are authored on 1.0.

### AD-12 — In-FreeCAD code is dependency-free [ADOPTED]

> Detailed design: [Project Structure Design](design/project-structure.md) (§2.3 one package, two runtimes).

- **Binds:** usecases, RPC listener, GUI addon
- **Prevents:** bundled-Python dependency hell; broken Addon Manager installs
- **Rule:** Code that runs inside the FreeCAD process imports stdlib + FreeCAD API only. All third-party dependencies (`mcp`, trimesh, admesh, lib3mf, pytest…) live in the external MCP/harness process, uv-managed.

### AD-13 — Harness independence & assertion style [ADOPTED]

> Detailed design: [Validation & Benchmark Harness Design](design/validation-harness-design.md) (independence, fault-injection, grader) · [Verification Subsystem Design](design/verification-design.md) (§7 assertion vocabulary).

- **Binds:** benchmarks, graders, Phase 3 spec assertions
- **Prevents:** actor grading itself; feature-tree reading validating intent instead of artifact; TNP-fragile selectors
- **Rule:** Pass/fail is decided by deterministic `verify_*` code or an independent grader — never by the producing agent. Spec assertions measure geometry (`Face.Surface` typing, axis/radius/spacing, bbox/volume) in an explicit anchor frame — declared per spec from a closed derivation set (named datum | base sketch plane | largest planar face fallback), resolved by one shared implementation. Every member of that set is **total and deterministic**: it resolves to exactly one frame for a given shape on every supported FreeCAD leg, or it raises. `largest_planar_face` therefore carries a mandatory tie-break (largest area, then lowest centroid along global Z, then lowest sorted mapped name), because `Shape.Faces` order differs across legs and an untied frame flips the origin on a symmetric part. The resolved face's mapped name is recorded in the report banner. A spec whose anchor frame does not resolve identically on the floor and primary legs is a broken spec, not a failing part — otherwise AD-14 reads the leg gap as overfitting. feature metadata (e.g. `PartDesign::Hole.Diameter`) is diagnostic hint only; sub-element index selectors are banned in specs. Every validator ships a ≥10-case fault-injection suite and reports sensitivity ≥95 % / false-alarm ≤5 % before its scores are citable. Benchmarks split dev/held-out; held-out is sealed until phase exit. Whole-shape similarity (Chamfer/IoU) is never a primary metric.

### AD-14 — Benchmark statistics rules [ADOPTED]

> Detailed design: [Validation & Benchmark Harness Design](design/validation-harness-design.md) (§4 stats module).

- **Binds:** every phase gate and ablation claim
- **Prevents:** noise reported as wins; the +15pp-at-n=20 undecidable criterion
- **Rule:** "Measurable margin" = exact McNemar two-sided p<0.05 **and** 95 % Wilson CI on the paired difference excluding 0. Repeats: R=5 default, R=3 Phase 1 answer eval, R≥10 for sealed held-out runs and any pp-threshold claim; a case scores pass on **majority-of-R**, and the per-repeat distribution is reported alongside the rate. Every reported pass rate carries its Wilson 95 % CI. Any specific pp-threshold claim (e.g. `design-decomposition` +15pp) runs on a dedicated n≥40 paired set. Below-detection effects are reported as "below detection at this n", not as failures. A dev/held-out gap >15pp = overfitting — the phase does not exit. **Tiered gate screens:** the G1 error-diagnosis gate uses the ladder from intent.md — grade n=10 first (pass ≥8/10), escalate to the sealed n=30 run only on a 10/10 result (Wilson CI reported); below 10/10 the gate concludes at n=10 and is flagged low-confidence. **The skill-loaded leg (GS.4, `freecad-troubleshooting`) rides the same ladder at a higher bar: ≥9/10 at n=10 to pass** (intent.md L131, vs the baseline 8/10), escalating on the same 10/10 trigger. A 9/10 skill result is therefore a pass that concludes at n=10 flagged low-confidence — the bar and the escalation trigger are deliberately different numbers, and a citation must state which n it concluded at. The R≥10 repeat rules above govern ablation and pp-threshold claims, not this screen.

### AD-15 — Skills loading architecture [ADOPTED]

> Detailed design: [Skills Library Structure Design](design/skills-structure-design.md) (store, loader, routing, budgets).

- **Binds:** skills library, agent harnesses, ablation runner
- **Prevents:** context-rot from all-12 resident loading; nondeterministic ablation A/Bs; cross-skill coupling polluting deltas
- **Rule:** One skill store (`SKILL.md` body ≤1,500 words — enforcement by `scripts/check_skill_shape.py` in CI is **required and not yet built** (Story 6.1); until it lands the cap is convention only; long tail in `references/`; no runtime code-level cross-skill dependency — a body never imports or `references/`-links into another skill's directory). Every skill body carries the same four sections: scope statement, decision rules, worked examples, anti-patterns. A body **may name a sibling skill in prose** to route the reader (all 12 skills are installed together), so long as the two skills' scopes stay disjoint; such a mention is a routing pointer, not a content dependency. *(Amended: the earlier "no Level-2 cross-skill dependencies" wording forbade any sibling mention in a body to keep ablation deltas perfectly attributable; the all-installed runtime makes in-body routing pointers worth their cost. Trade-off accepted: a body that leans on a sibling's content is not cleanly ablatable in isolation — such coupling is minimized and noted so the ablation campaign accounts for it.)* Two loader modes over the store: production = metadata-first router (descriptions resident, 2–5 bodies routed per task, ≤~10K token skill budget, routed subset logged); ablation = forced explicit-subset injection with auto-activation disabled. The injection path is the portable second-harness mechanism. **Cut rule:** ≥8 of the 12 Track A+B skills must clear the AD-14 measurable-margin bar; those below it are revised or removed, never kept on the strength of sounding right. **Freshness:** every `SKILL.md` records the FreeCAD version its claims were verified against (same pins as the AD-11 CI matrix); a matrix version bump opens a re-verification obligation for every skill, and benchmark failure analyses feed skill corrections. These are the two mitigation legs intent.md's stale-skills risk names beside ablation. *(Catalog: the 12 Track A+B parametric-CAD skills, plus a Phase-5 robot-description/sourcing group — `urdf-export`, `sdf-export`, `part-sourcing` — added when Phase-5 lands, AD-22/AD-23. New skills join the same store and shape contract; the resident-description count grows with the catalog.)*

### AD-16 — Benchmark provenance policy [ADOPTED]

> Detailed design: [Validation & Benchmark Harness Design](design/validation-harness-design.md) (§1.2 provenance manifest).

- **Binds:** all shipped benchmark/golden-model artifacts
- **Prevents:** Onshape-lineage copyright and non-commercial terms contaminating the repo
- **Rule:** Shipped artifacts come only from commercial-clean sources: FreeCAD Parts Library (CC-BY, attribution retained), FreeCAD wiki tutorials, hand-authored specs, verified-permissive HF datasets. Hand-authored specs must derive from documented real-world parts or user requests — never reverse-engineered to fit what the agent already does well. DeepCAD/ABC/Text2CAD lineage and Fusion 360 Gallery are methodology references and import-only geometry oracles — never shipped. Every benchmark documents provenance; community models are license-checked per item.

### AD-17 — Job status & report integrity [ADOPTED]

> Detailed design: [Data Contracts Design](design/data-contracts-design.md) (envelope, status, report, job, audit) · [Security and Phase 4 Service Design](design/security-and-service-design.md) (§6.4 supervisor re-checks).

- **Binds:** all tool results, validation reports, Phase 4 job API (schema binds from Phase 0)
- **Prevents:** "HTTP 200 for a bad part"; silent failures; schema rework at Phase 4
- **Rule:** Terminal outcomes use the closed set `OK | SPEC_FAILED | RECOMPUTE_ERROR | TIMEOUT | OOM_KILLED | WORKER_CRASHED | INVALID_INPUT` plus machine-readable detail. The `ResultEnvelope`, `ValidationReport`, `JobStatus`, and audit-record types are owned by `contracts/` from Phase 0 — every surface (tool results, harness reports, Phase 4 job API, audit log) reuses them; no surface defines its own variant. Validation-report fields are backed by re-executed deterministic checks — supervisor/harness re-runs them; agent claims are never echoed as results. An append-only audit log of every mutation and exec exists from Phase 0. **Run traceability:** every Phase 3+ run carries a `run_id` threaded through every `ResultEnvelope`, `AuditRecord`, and `ValidationReport` it produces, and writes its plan, per-iteration geometry discrepancy vector, judge verdicts with their images, and repair decisions to the AD-25 session workdir under that id. A failed production run is reconstructable from its workdir alone, without the agent's context — the same evidence the harness already stores per gate run, through one mechanism rather than two.

### AD-18 — Service isolation posture [ADOPTED]

> Detailed design: [Security and Phase 4 Service Design](design/security-and-service-design.md) (§5–§6 service architecture, sandbox).

- **Binds:** Phase 4 service; constrains earlier phases only via AD-17 schemas
- **Prevents:** in-process "sandboxing" theater; leak-accumulating long-lived workers
- **Rule:** The unit of memory reclamation and crash containment is the worker **process** (supervisor never imports FreeCAD; `spawn` start method; recycle default one task per worker (`max_tasks_per_child=1` on `ProcessPoolExecutor`); whole-tree kill via Job Object / process-group). Security boundary is OS-level (Linux: nsjail/bubblewrap or hardened `--network none` container; Windows: WSL2-hosted Linux stack preferred, else AppContainer + Job Object); workers are network-free (egress deny-by-default) and GPU-none. Concrete profiles are set at the Phase 4 gate.

### AD-19 — Validation Design Gate ordering

> Detailed design: [Validation & Benchmark Harness Design](design/validation-harness-design.md) (gate runner, §6 fault-injection, §7 human tokens).

- **Binds:** every phase; benchmarks, validators, phase implementation code
- **Prevents:** phase code written before its validators exist; flattering self-graded metrics; overfit exits
- **Rule:** Phase *N* implementation may not begin until its Validation Design Gate lands: threat list, benchmark + assertions runnable (against a stub, failing honestly), ≥10-case fault-injection suite passing the AD-13 sensitivity bar, written grading rubric, and a reuse survey. The gate is timeboxed to **~20 % of the phase timebox** and is part of the phase, not an addition to it — an unbounded gate eats the phase it is meant to protect. Each phase's validator ships a known-good reference corpus (Phase 0: ≥5 hand-made models with hand-computed values) against which the ≤5 % false-alarm rate is measured. The reuse survey names the candidates it actually surveyed and the outcome for each — including the community FreeCAD MCP servers that informed AD-2's topology, and the existing LLM eval frameworks weighed before building the AD-14 stats module. Phase exit additionally requires a human spot-audit of ≥20 % of passing results — any audit-found false pass invalidates the run (fix validator, re-run, re-audit).

### AD-20 — Document lifecycle & targeting

> Detailed design: [MCP Tool Catalog Design](design/mcp-tools-design.md) (§1.1 handles, `document_*` tools) · [Data Contracts Design](design/data-contracts-design.md) (§9 `DocHandle`, selectors).

- **Binds:** all tool callers (AI, harness, supervisor, preview)
- **Prevents:** implicit-`ActiveDocument` ambiguity; interleaved mutations mid-transaction; TempDoc leaks and cross-cleanup
- **Rule:** Documents are opened/closed only through the `document_*` use cases — the harness and supervisor included, never raw `App.openDocument` alongside the bridge. Every tool call carries an explicit document handle; `ActiveDocument` is never an implicit target. Mutations on one document are serialized (single writer; AD-5 transactions never interleave). Preview TempDocs use a reserved name prefix, are flagged transient, and are cleaned by their creator — nothing else touches them.

### AD-21 — Visual verification leg (dual-channel done)

> Detailed design: [Verification Subsystem Design](design/verification-design.md) (§7a `verify_visual`) · [Validation & Benchmark Harness Design](design/validation-harness-design.md) (§8 visual judge wiring).

- **Binds:** Phase 3 loop convergence, gates G3/G4, Phase 4 job delivery
- **Prevents:** geometrically-passing but visually/semantically wrong parts shipping; the actor grading its own renders
- **Rule:** A generated **part** is done only when both channels pass: (a) all geometry assertions (AD-13) and (b) an **independent visual judge** — a vision-capable model that is never the acting agent (separate model id or separate context, same separation rule as the Phase 1 grader) — judging the standard visual set against the spec via a structured checklist, temperature 0, structured verdict. Standard visual set: 3D iso render + focus views **+ dimensioned TechDraw projections (front/top/right)** auto-generated from the part's driving parameters on a TempDoc copy (part document never polluted). Judge-directed images travel straight to the judge API, not through client context, so the AD-10 user-facing budget does not apply to them; they carry a legibility floor of **≥2048 px** page width instead — below it the dimension cross-check degrades to noise. The judge is conjunctive, never overriding: it cannot pass a part that geometry failed. Judge findings feed the repair loop as diagnostics. **Cadence:** the visual leg runs once per candidate part **at the end of each repair iteration whose geometry assertions all pass** — never on an iteration geometry already failed (the judge is conjunctive, so it could not change that verdict). A judge failure counts as one repair iteration against the intent.md ≤3 cap, and the AD-24 per-part wall-clock is measured across all iterations including judge and TechDraw generation time. (Left unstated, "feeds the repair loop" and "per part, not per mutation" read as per-iteration and terminal respectively — a ~4× wall-clock difference on the same gate criterion.) Capability-gated fail-closed: render or judge unavailable → part is NOT done; an explicit operator waiver (audit-logged) is the only bypass. The judge is itself a validator under AD-13/AD-19: fault-injected (planted visually-wrong parts) to sensitivity ≥95 % / false-alarm ≤5 % before its verdicts are citable. Per-operation verification (AD-5) stays geometry-only — the visual leg runs per part, not per mutation. *Deliberate amendment of intent.md: "Drawings — auto-generated TechDraw sheets" is listed there as a Phase 5 candidate, and "Vision feedback" as exploratory. Both are pulled forward into Phase 3 as a fail-closed done-condition, because the dominant failure mode is a geometrically-passing part that is semantically wrong, and geometry assertions alone cannot catch it. Accepted cost: auto-dimensioning and headless TechDraw export land on the Phase 3 critical path.*

### AD-22 — Robot-description export (URDF/SDF)

> Scope: Phase 5 capability (Epic 7). Detailed design: [Robot-Description Export & Part Sourcing Design](design/robot-description-and-sourcing-design.md). Empirically-gated items land at the G5-robot gate.

- **Binds:** Phase-5 URDF/SDF export tools and their skills
- **Prevents:** an unverified XML dump counted as success; silent unit/frame errors crossing the CAD→robot boundary
- **Rule:** URDF/SDF are **emitted by our code** from the native Assembly kinematic tree (`AssemblyObject`/`AssemblyLink`/joints) + native solid inertials (`TopoShapeSolidPy` mass-property surface) + mesh export — the in-tree FreeCAD `Robot` workbench is a trajectory/simulation tool, not a URDF exporter, so nothing exports these for us; the external **CROSS** addon is evaluated first per the reuse rule and wrapped, not forked, if it fits. Every `export_urdf`/`export_sdf` completes **only** through its paired `verify_export_*` (re-parse the written file, schema-valid, single-root **acyclic** kinematic tree, joint axes finite and normalized in the joint frame, inertials positive and physically plausible, every mesh reference resolves) — mirroring AD-9's export/verify pairing; "bytes were written" is never success. The internal-mm/deg → **URDF/SDF-native metre/kg/radian** conversion is an explicit, pinned boundary, never an ambient default. Every link, joint, and inertial origin records the reference frame it is expressed in (frame-semantics rigor). Reuses AD-9 (pairing), AD-17 (envelopes/status), AD-20 (document lifecycle), AD-11 (shim owns version-sensitive Assembly/inertial calls), AD-12 (in-FreeCAD code stays stdlib + FreeCAD; XML emit and any schema libs live external).

### AD-23 — Off-the-shelf part sourcing & import

> Scope: Phase 5 capability (Epic 7). Detailed design: [Robot-Description Export & Part Sourcing Design](design/robot-description-and-sourcing-design.md). Empirically-gated items land at the G5-robot gate.

- **Binds:** Phase-5 part-sourcing/import tools and their skill
- **Prevents:** raw imports bypassing the bridge; trusting an imported part's origin/orientation; unlicensed shipped fixtures
- **Rule:** Off-the-shelf parts enter a document **only** through the `document_*`/import use cases (native STEP import via `ImportOCAF`/`ReaderStep`), never a raw `App.open` alongside the bridge (AD-20). Catalog **search** is an external concern; **placement** is standard bridge flow. An imported part's geometry is **measured** (`query_mass_properties`/`query_placement`) before its mating frames are trusted — its origin and orientation are never assumed. Any shipped catalog fixture records provenance and license per AD-16.

### AD-24 — Performance & resource budgets

> Detailed design: [Validation & Benchmark Harness Design](design/validation-harness-design.md) (timing capture, report banner) · [Security and Phase 4 Service Design](design/security-and-service-design.md) (soak run, worker recycling).

- **Binds:** phase gates, harness reporting, Phase 4 service
- **Prevents:** measurable exit criteria discovered unmet at phase exit; each phase inventing its own timing basis; a soak claim with no memory instrumentation
- **Rule:** Phase 1 answer latency ≤15 s median; Phase 3 per-part wall-clock ≤10 min median; Phase 4 survives a 50-job soak with memory growth <20 % and zero crash, hang, or resource leak (every failed job still fails with a structured AD-17 status, never silently). These are gate criteria measured by the harness, never self-reported by the acting agent, and each is reported in the standard banner alongside its n. One timing basis for all of them: wall-clock from tool-call entry to envelope return, model time included. Budgets are pass/fail at the gate, not advisory — the gate runner carries an explicit budget leg in its verdict, so a run that meets every assertion and blows its budget **fails**. **Health surface:** the service exposes `/healthz` returning worker-pool occupancy, per-worker RSS, jobs completed, and the session id; the soak numbers are computed from samples of it, never from a post-hoc log parse. The GUI bridge exposes the same endpoint minus the pool fields — it is also what AD-2's already-served check probes.

### AD-25 — Data & artifact locations

> Detailed design: [Project Structure Design](design/project-structure.md) (§6 session workdir) · [Security and Phase 4 Service Design](design/security-and-service-design.md) (job dirs, retention).

- **Binds:** every component that writes a file — mutation protocol, exports, audit log, preview, harness, Phase 4 workers
- **Prevents:** two implementers choosing different snapshot paths so a restore silently finds nothing; the bridge littering the user's document folder with orphan files; unbounded artifact growth
- **Rule:** Every file the bridge writes lives under a **session-scoped workdir** owned by the `documents` use case: `snap/` (AD-5 snapshots), `exports/`, `audit.log`, `tmp/`. The bridge never writes into the user's document directory except through an explicit `document_save`/`export_*` call carrying an operator-supplied path. Snapshots are named `<doc-Name>.<transaction-id>.FCStd`, are deleted by the transaction that created them on **every** exit path (commit, abort, or error), and any snapshot surviving into a new session is swept at bridge start. A restore reads only from the workdir of its own session. Retention: audit logs are never rotated or truncated by the bridge (append-only, AD-17) but are written per session to a dated file so an operator can archive whole files; job directories are deleted on terminal status unless `keep_artifacts` is set; benchmark run artifacts under `benchmarks/gate-artifacts/<gate>/<run-id>/` are retained indefinitely because gate verdicts are recomputed from them.

### AD-26 — Single client session

- **Binds:** RPC listener, MCP server, preview/apply pairing
- **Prevents:** two clients interleaving intent against one document while each call is individually serialized
- **Rule:** The bridge serves **one client session at a time**. The session token authenticates a session, not a client: a second client presenting it is refused (`-32000`, busy detail) unless the operator explicitly enables multi-client mode. In that mode every `preview_dry_run` → apply pair carries a fingerprint precondition (AD-6) and the apply fails if the document changed in between. Serializing calls is not serializing intent — AD-20's single-writer rule orders individual mutations, and this AD orders the multi-call sequences built from them.

### AD-27 — Post-timeout bridge state

- **Binds:** RPC listener, marshal, all callers including the harness
- **Prevents:** a caller mutating or closing a document while an abandoned operation still runs against it
- **Rule:** `TIMEOUT` is terminal **for the caller, not for the operation** — no preemption exists, so the in-FreeCAD op may still be running. On timeout the listener marks the session **quarantined**: further calls are refused with `TIMEOUT` and no new work is accepted until the in-flight op returns and its AD-5 transaction is aborted with rollback proved. No caller may close, reuse, or mutate a document while a call against it is quarantined. `WORKER_CRASHED` is the escalation when the op never returns. **No mutation is ever automatically retried**: a timed-out mutation is not idempotent — it may have committed — so recovery is an explicit `query_*` plus fingerprint comparison, never a blind re-call.

### AD-28 — Interface & schema evolution

> Detailed design: [Data Contracts Design](design/data-contracts-design.md) (§2 versioning) · [Integration Design — MCP ↔ FreeCAD](design/integration-mcp-freecad.md) (§2.2 frames).

- **Binds:** `contracts/`, the RPC wire, every generated schema, package release
- **Prevents:** a field rename silently breaking a running proxy; audit logs that can no longer be replayed; three version numbers drifting into one ambiguous "version"
- **Rule:** Contracts schemas evolve **additive-only within a major**: new fields are optional with a defined default, readers ignore unknown fields. Any removal, rename, type change, or closed-enum change is a **major bump**, and the old schema is retained for audit-log replay. The AD-17 terminal status set is frozen — adding a member is a major bump on every schema embedding it. Persisted state is never migrated in place: audit records are replayed with the decoder for the major they were written under. JSON Schemas are generated from the contracts types and diff-checked in CI (drift = build failure); per-tool `outputSchema`s compose them by `$ref` and an adapter never hand-writes a field contracts do not define. The RPC `contract_version` is a single integer bumped on any frame or field semantic change, refused at handshake on mismatch (`-32004`) with no negotiation and no compatibility shim. **Three independent numbers** — package version (SemVer, one source of truth in `pyproject.toml`, with `addon/package.xml` generated from it by `build_addon.py` and never hand-edited), RPC `contract_version`, and contracts schema major — each reported in the AD-17 banner.

## Consistency Conventions

> Detailed design: [MCP Tool Catalog Design](design/mcp-tools-design.md) (tool names, envelopes, selectors) · [Data Contracts Design](design/data-contracts-design.md) (wire types, versioning).

| Concern | Convention |
| --- | --- |
| Tool names (wire) | Underscore + namespace prefix: `query_`, `document_`, `export_`, `verify_`, `sketch_`, `feature_`, `preview_`, `debug_`. Dot form (`verify.shape`) is docs shorthand only — dots are illegal in MCP tool names. |
| FreeCAD object identity | Script against immutable `Name`, display `Label`. Generated features get intent-bearing names (tree reads like a build plan). |
| Units | Internal mm/deg; tool params/results carry explicit units; export calls pin units per call (never rely on ambient defaults). |
| Tool results | `structuredContent` validated by per-tool `outputSchema` + text mirror; images per AD-10 budget rules. Text payloads are summarized, never raw dumps — a tree query on a ≥50-feature document returns a summary, so no result can blow the client's context by size alone. |
| Model agnosticism | No tool schema, confirmation path, or result envelope may depend on one client's capabilities. Every Phase 1+ gate runs its eval on ≥2 backends (one non-Claude), exercising the non-elicitation confirmation path rather than assuming it — AD-10's "client-confirm fallback" is a shipped path (`adapters/react_adapter.py`), not a hypothetical. Which local model is pinned stays deferred; the portability property does not. |
| Internal RPC methods | The registry carries `internal=True` methods that are RPC-only and deliberately never MCP tools (e.g. the `export_self_read_*` legs, which exist because the oracles live outside FreeCAD per AD-9/AD-12). They take the same namespace prefixes but never reach the AI surface. |
| Errors | Closed status set (AD-17) + human-readable explanation + machine detail; constraint diagnostics map 1-based solver IDs to `Constraints[id-1]` names. |
| Reports | Every verification/benchmark report carries a banner: FreeCAD version, `ElementMapVersion`, validator sensitivity, Wilson CI (where a rate is claimed), and the AD-24 budget measured for that gate with its n. |
| Config | Capability flags via env vars set by the human operator (`FREECAD_BUDDY_ALLOW_EXEC`, `autoApprove`); capability probes at runtime, never version sniffing. |
| Logging | stderr-only in server code (stdio safety); audit log append-only JSON-lines per job/session. |
| Numeric tolerance | Assertions default absolute + relative bands, fault-injection-calibrated; never tighter than `Shape.getTolerance`; fingerprint quantization 1e-6. |
| Tests under FreeCADCmd | stdlib `unittest` only (AD-12 posture); pytest orchestrates from the external process. |
| Sub-element addressing (tool inputs) | Selector objects: geometric query or TNP mapped name. Bare indexed names (`Face6`) are resolved to mapped names at call time and never stored. |
| Reuse before invention | Survey first; adopted components are wrapped, not forked; anything built from scratch records why nothing existing fit (phase reuse survey, AD-19). |

## Stack

| Name | Version |
| --- | --- |
| Python | matches the bundled interpreter per FreeCAD leg: 3.11 (1.0.x) / 3.12 (1.1.x); external process pins per CI leg |
| FreeCAD | 1.0.x floor / 1.1.x primary (latest patch **available on conda-forge** — feedstock lags point releases) / 1.2-dev canary (conda-forge if published, else weekly AppImage) |
| MCP Python SDK | official `mcp` python-sdk, pinned `>=1.28,<2` — **closed at the Phase 0 gate** (decision 005); PrefectHQ `fastmcp` rejected. Code builds the **low-level `mcp.server.lowlevel.Server`**, not FastMCP. The `<2` cap sits below the SDK v2 rename so an unattended upgrade cannot break the import surface. Spec ≥2025-06-18 (elicitation + structured output; AD-10 depends on it) |
| trimesh, lib3mf | `trimesh==4.*`, `lib3mf==2.*` — export oracles |
| admesh | optional secondary STL oracle (dormant upstream, no Windows wheels); fallback second oracle chosen at Phase 0 gate |
| pytest | `>=8` — harness runner (external process only) |
| ruff | `>=0.5` — lint gate; `T201` enforces the AD-3 `print()` ban in `src/` |
| jsonschema | `>=4` — contracts schema drift check (`gen_schemas.py --check`) |
| pyyaml | `>=6` — external harness only (AD-12) |
| openai | `>=1`, optional `react-local` extra — transport for an operator's live local ReAct eval; never installed in CI (decision 011) |
| uv | dependency management, external process only |
| GitHub Actions + micromamba | CI, cached conda env per pinned FreeCAD version |
| FreeCAD Assembly workbench | native (1.0+); supplies the kinematic link/joint tree for AD-22 — Phase 5 |
| CROSS addon | optional URDF/SDF export addon — evaluate-first reuse candidate for AD-22 (else emit XML ourselves); version pinned at the Phase-5 gate |
| URDF/SDF schema/parse lib | external-process only, for the AD-22 verify leg (re-parse + schema-valid); pinned at the Phase-5 gate |

## Structural Seed

> Detailed design: [Project Structure Design](design/project-structure.md) (repo tree, packaging, CI) · [Component Design](design/component-design.md) (per-ring components).

```mermaid
graph TB
  subgraph clients [MCP clients]
    cc[Claude Code / Desktop]
    local[llama.cpp local backend]
    a2a[external agent - Phase 4]
  end
  subgraph mcpproc [External MCP process - uv env, all third-party deps]
    fast[MCP low-level Server + tool registry]
    harness[benchmark harness / pytest]
    skills[skills loader: router + forced-subset]
  end
  subgraph fcgui [FreeCAD GUI process]
    listener[RPC listener - stdlib only]
    marshal[main-thread marshal]
  end
  subgraph fccmd [Headless FreeCADCmd / import FreeCAD]
    core2[tool use-cases in-proc]
  end
  cc -- stdio/HTTP --> fast
  local -- stdio --> fast
  a2a -- HTTP --> fast
  fast -- RPC localhost --> listener --> marshal
  fast --- core2
  skills --> fast
```

```text
freecad-buddy/
  src/freecad_buddy/
    contracts/     # schemas, envelopes, status set, assertion vocabulary (stdlib only)
    usecases/      # tool impls, mutation protocol, TNP guard, fingerprint, shim.py
    adapters/      # mcp_server, rpc_client/listener/dispatch, marshal, render_probe, audit_log, export_oracle, export_verdict, react_adapter
    hosts/         # gui_addon/ (InitGui, bootstrap, pump), gui_external/, headless/, main.py, tool_catalog.py
  skills/          # 15 skill dirs (12 Track A/B + Phase-5 robot-description/sourcing): SKILL.md + references/
  benchmarks/      # runner.py + harness/; per-gate g0/ g1/ g2/ (each with dev/, heldout/, fault-injection/); _registry/, gate-artifacts/
  tests/           # two worlds: infc/ (FreeCADCmd + stdlib unittest via run_tests.py), external/ (pytest)
  .github/workflows/  # ci.yml: matrix {1.0.x, 1.1.x} blocking + 1.2-dev canary
```

**Environments:** dev = GUI addon + external server (HTTP) on Windows/Linux desktop; CI = `ubuntu-latest`, micromamba conda-forge FreeCAD, `FreeCADCmd run_tests.py`, xvfb + software-GL leg for render tests (isolated, non-blocking); Phase 4 service = supervisor + sandboxed worker pool, single-tenant local-first.

## Capability → Architecture Map

| Capability (intent.md) | Lives in | Governed by |
| --- | --- | --- |
| Phase 0 bridge & tools | usecases + adapters | AD-1..3, AD-9, AD-11, AD-12, AD-20, AD-25 (workdir), AD-26, AD-27, AD-28 |
| Phase 0 test harness/CI | tests + harness | AD-13, AD-11, AD-19 |
| Phase 1 assistant (read-only) | query tools + skills loader *(loader planned)* | AD-4 (zero mutation), AD-15, AD-24 (latency) |
| Phase 2 copilot mutations | mutation tools | AD-4..8, AD-10, AD-25 (snapshots) |
| Phase 3 designer loop | plan/execute over Phase 2 tools | AD-5, AD-13, AD-14, AD-21, AD-24 (wall-clock), AD-17 (run_id) |
| Phase 4 service | `hosts/phase4` supervisor *(not yet built)* | AD-17, AD-18, AD-21, AD-24 (soak, memory, health), AD-25 (retention) |
| Phase 4 DFM / design-rule checks | verify tools (rule layer) + slicer CLI oracle | AD-9, AD-13; deferred detail |
| Phase 5 robot-description export (URDF/SDF) | Phase-5 export tools over the Assembly tree + inertials | AD-22, AD-9, AD-17, AD-20; deferred detail |
| Phase 5 off-the-shelf part sourcing/import | document_*/import + measurement | AD-23, AD-20, AD-16; deferred detail |
| Skills track | skills/ + ablation runner | AD-14, AD-15 |
| Benchmarks/golden models | benchmarks/ | AD-13, AD-14, AD-16 |

## Deferred

| Decision | Why it can wait |
| --- | --- |
| Local LLM backend pin (lean: llama.cpp + Qwen3-30B-A3B, constrained decoding) | Phase 1 gate — **the model choice only**. The portability property it proves is not deferred (Conventions, Model agnosticism) and its mechanism already ships: `adapters/react_adapter.py` with an injected chat transport and the optional `react-local` extra (decision 011) |
| Preview diff `outputSchema` field list | Locked once at Phase 2 UX design; must reuse the contracts-owned audit-record vocabulary that exists from Phase 0 (AD-17) |
| Skill router rules (task→subset map) | Tuned from ablation data; forced-subset mode unaffected |
| Concrete sandbox profiles (nsjail config, AppContainer caps, seccomp allowlist) | Phase 4 gate; posture fixed by AD-18 |
| Worker pool tuning (K warm workers, recycle N) | Soak test at Phase 4 sets empirically; N=1 safe default stands |
| Slicer-acceptance CI job for 3MF; lib3mf as fallback writer | Phase 4 realism gate; triggered by slicer rejects |
| DFM/design-rule layer (min wall, hole-edge distance; slicer CLI mapping) | Phase 4 gate; composes existing verify primitives |
| Phase 1 doc-citation channel (skills `references/` vs doc-retrieval tooling over local wiki clone) | Phase 1 gate; read-only capability, no schema impact |
| Assembly `JointObject.py` wrapper design | Phase 5; native Assembly WB exists (1.0+), Python-exposure of joints is the gap — prerequisite for AD-22 URDF/SDF export |
| Assemblies capability (multi-part mating constraints, cross-part interference detection) | Phase 5, scoped after the Phase 4 retrospective. **Sequencing note:** AD-22 depends on it for the kinematic link/joint tree, so it is the first Phase-5 epic |
| FEM-in-the-loop / optimization / topology suggestions | Phase 5 candidate; no AD shaped by it. Would need a new oracle class (CalculiX/gmsh) under the AD-13 validator rules before any claim is citable |
| Reverse tasks (STEP/mesh → editable parametric reconstruction) | Phase 5 candidate; inverts the whole verify-first direction (no spec to assert against), so it needs its own validation design before an AD is worth writing |
| URDF/SDF export detail (CROSS-addon-vs-hand-rolled-XML; the verify leg's schema/parse lib; URDF vs SDF tool split) | Phase-5 gate; posture fixed by AD-22, empirical CROSS-fit + Assembly-Python-exposure spikes decide the build path |
| Part-sourcing catalog integration (which catalog/API; search surface) | Phase-5 gate; posture fixed by AD-23 (import path + measured frames); search is external and swappable |
| SRDF (MoveIt planning semantics) | Deferred — no native FreeCAD path; derives from an exported URDF + external MoveIt Setup Assistant. Revisit after URDF (AD-22) lands and a MoveIt integration is wanted |
| Implicit CAD — **rejected, not deferred** | OCCT B-rep vs F-rep/SDF kernel mismatch; the verify stack (AD-6 fingerprint, AD-9 pairing) assumes B-rep solids. Recorded so it is not re-litigated |
| Exact tolerance defaults per assertion | Fault-injection calibration during each phase's Validation Design Gate |
| DFM slicer binary | Phase 4 gate — pin a slicer CLI (PrusaSlicer console mode or equivalent) as an external-process oracle. It runs as a **bundled in-sandbox binary**, never a service call, under AD-18's network-free posture. The FEM/CalculiX stress-check leg of the same intent.md reuse row is deferred with it; it needs a new oracle class under AD-13 before any claim is citable |
| Addon Manager submission (FreeCAD-addons index PR, `package.xml` review) | Phase 1 gate. **Open conflict to settle there:** AD-12 puts `mcp` in an external venv the addon auto-discovers from its install path (AD-2), but a store install has no sibling repo and no `.venv`, so auto-spawn resolution fails by construction for every store user. Decide whether the store build vendors a proxy, prompts the operator, or the store is not a supported channel |
| AD-21 judge-image path (≥2048 px) | Phase 3. The AD-10 render path caps at 1920 px in code (`usecases/screenshot.py`, `tool_catalog.py` schema) and the judge bypass AD-21 assumes does not exist yet — the carve-out needs a separate render entry point before the visual leg can run |

## Closed at the Phase 0 Gate

Previously deferred; now decided and implemented. Listed so they are not re-opened, with the
decision note that settles each.

| Item | Outcome |
| --- | --- |
| Fingerprint serializer (`exportBinary` Python exposure) | Probe `exportBinary`, fall back to an `exportBrep` stream, degrade to a mass-property tuple when neither is available; every hash serializer-tagged, cross-tag comparison banned (decision 001, AD-6) |
| Conda `FreeCADCmd` PYTHONPATH edge | Sidestepped, not worked around: in-FreeCAD tests run via `FreeCADCmd tests/run_tests.py`, never a foreign interpreter doing `import FreeCAD` (decision 002) |
| `renderToImage` without a GUI document | `FreeCADGui.setupWithoutGUI()` + `SoQtOffscreenRenderer` + `subgraphFromObject`; raw `pivy.coin.SoOffscreenRenderer` never used; headless runs under `xvfb-run` with `LIBGL_ALWAYS_SOFTWARE=1`, gated by `shim.render_available()` (decision 003) |
| VarSet exposure on the 1.1 runtime | Driving-dimension façade prefers `App::VarSet`, falls back to `Spreadsheet::Sheet`, gated by `shim.varset_available()`; Spreadsheet is the safe default until upstream issue 12531 confirms Python exposure (decision 004) |
| MCP SDK choice and pin | Official `mcp` python-sdk, `>=1.28,<2`, low-level `Server`; PrefectHQ `fastmcp` rejected (decision 005, Stack table) |
| G1 error-diagnosis eval shape | Tiered n=10 → n=30 ladder, thresholds in AD-14 (decision 008) |
