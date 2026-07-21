# Adversarial Review — ARCHITECTURE-SPINE.md (freecad-buddy)

Lens: construct two phase-level builders who each obey every AD to the letter yet build incompatibly. Every constructible pair is a hole. Units considered: Phase 0 tool authors, Phase 2 mutation-tool authors, Phase 3 loop author, harness/benchmark authors, skills authors, Phase 4 supervisor author.

Verdict: **Spine invariants are strong on verification semantics but leave four load-bearing contracts unowned (RPC wire shape, result/report/job envelope, document lifecycle, fingerprint fallback), each of which admits two fully-compliant, mutually incompatible builds. 9 real holes found; 3 critical.**

---

## CRITICAL

### C-1. RPC contract between MCP server and in-FreeCAD listener has no owner and no wire shape

- **Units:** MCP-server author (adapters, external uv process, all third-party deps available) vs RPC-listener author (adapters, in-FreeCAD, stdlib-only per AD-12).
- **Incompatible builds both ADs permit:** AD-2 fixes topology ("external MCP server + thin in-FreeCAD RPC listener") and threading; AD-3 fixes only the *MCP* transport; AD-12 fixes the listener's dependency budget. Nothing fixes the internal RPC. Build A: server author, free to use third-party libs, ships msgpack-over-ZeroMQ with a `{method, params, request_id}` framing. Build B: listener author, stdlib-only, ships `xmlrpc.server` or JSON-lines over `socketserver` TCP with `{tool, args}` framing. Both are AD-compliant; the Structural Seed's `fast -- RPC localhost --> listener` edge does not compose. Secondary clash: which layer's types cross the wire — raw tool args or contracts-ring envelopes? If the listener deserializes into ad-hoc dicts while the server serializes contracts dataclasses, every tool call needs a hand-written translation shim that drifts per tool.
- **Tightening:** New AD (or amend AD-2): the RPC contract is a named module in `contracts/` (stdlib-serializable: JSON-lines over localhost TCP, length-prefixed or newline-delimited — pick one), request/response shapes are the contracts-ring envelopes verbatim, a versioned handshake message is exchanged at connect, and both `adapters/mcp_server` and `adapters/rpc_listener` import the shape from that one module. CI check: listener imports nothing outside stdlib + `contracts/`.

### C-2. Tool-result envelope, validation report, and Phase 4 job status: one closed status *vocabulary*, three unowned *schemas*

- **Units:** Phase 0 tool author + harness/validation-report author + Phase 4 supervisor author (three-way, any pair clashes).
- **Incompatible builds both ADs permit:** AD-17 closes the terminal-outcome *value set* and the Consistency Conventions require per-tool `outputSchema` — but no AD names the envelope fields or their nesting. Build A (tool author): `{"status": "OK", "detail": {...}, "data": {...}}` at top level. Build B (harness author): validation report `{"outcome": "SPEC_FAILED", "checks": [{...}]}` — same vocabulary, different key, per-check statuses nested. Build C (supervisor author): job API `{"state": "OK", ...}` and, because AD-17's set is explicitly "terminal outcomes" only, invents in-band non-terminal states (`QUEUED`, `RUNNING`, `CANCELLING`) that collide with or shadow the closed set. AD-17's own promise ("schema binds from Phase 0") is unfulfillable because there is no schema, only an enum. Bonus fork inside the same hole: one tool author signals `INVALID_INPUT` via the envelope, another via the MCP protocol error channel (`isError`) — the harness's re-run logic (AD-17: "supervisor/harness re-runs them") sees two different failure surfaces for the same condition.
- **Tightening:** Amend AD-17: `contracts/` owns three named schemas — `ResultEnvelope` (field names fixed: `status`, `detail`, `data`), `ValidationReport` (embeds `ResultEnvelope` per check + the AD-banner fields), `JobStatus` (a *separate* non-terminal lifecycle enum + terminal field typed as the closed set). All per-tool `outputSchema`s extend `ResultEnvelope`. Rule: closed-set values appear only in the `status`/terminal field; MCP `isError` is reserved for protocol/transport faults, never for domain outcomes.

### C-3. Document lifecycle has no owner: tools, harness, preview, and supervisor all open/close documents by different rules

- **Units:** Phase 0/2 tool authors (own `document_*` tools) vs harness author (opens fixture docs, cleans up between cases) vs Phase 2 preview author (creates `copyObject` TempDocs per AD-10) vs Phase 4 supervisor author (per-job docs).
- **Incompatible builds both ADs permit:** AD-4 restricts only *AI-visible* mutations to typed tools — the harness is not the AI, so a harness author lawfully calls `FreeCAD.openDocument`/`closeDocument` directly. Build A: tool author maintains a tool-side active-document registry, assumes every live doc entered via `document_*`; harness-opened fixtures are invisible to it → tools resolve "active document" to the wrong doc, or `document_close` double-closes. Build B: preview author names TempDocs `preview_<uuid>` and relies on apply/decline to clean them; harness author's between-case cleanup sweeps "all docs not in my fixture list" and kills a live preview TempDoc mid-elicitation (GUI dev mode: harness and interactive session share one FreeCAD process). Build C: supervisor assumes worker recycling (AD-18 `maxtasksperchild=1`) makes cleanup moot; GUI/dev mode has no recycling, so the same tool code leaks docs there. AD-10 specifies TempDoc creation but not naming, registry, or cleanup responsibility; AD-5's fingerprint snapshots silently assume a stable well-known target doc identity.
- **Tightening:** New AD "Document lifecycle ownership": a session-scoped document registry lives in `usecases/`; *every* open/close — tool, harness, preview, supervisor — goes through it (harness calls the same use-case functions, not `FreeCAD.openDocument`). TempDocs use a reserved prefix (`__fcb_tmp_`), are registered with creator + TTL, creator cleans on all exit paths, and generic cleanup may sweep only the reserved prefix. Tool calls address documents by explicit registry handle, never by ambient `ActiveDocument`.

---

## HIGH

### H-1. Fingerprint fallback fork: `exportBinary` availability handled differently at different call sites

- **Units:** Phase 2 mutation-protocol author (AD-5 snapshot/re-hash) vs revision-diff / undo-verification author (AD-6 lists them as separate bind targets) — and CI legs on different FreeCAD versions.
- **Incompatible builds both ADs permit:** AD-6 mandates `TopoShape.exportBinary`; the Deferred table concedes `exportBinary` Python exposure is an unresolved spike with "fallback `exportBrep`". Build A: mutation author's fingerprint falls back to `exportBrep` text bytes when `exportBinary` is absent. Build B: revision-diff author raises `UNSUPPORTED` instead, or falls back to the mass-property tuple alone. Same document, two "AD-6 fingerprints" that never compare equal — and AD-5's rollback proof ("re-hash and compare") silently compares a Build-A hash against a Build-B hash if snapshot and re-hash are taken through different helpers. Cross-version: a 1.0.x leg without `exportBinary` and a 1.1.x leg with it produce incomparable fingerprints for identical geometry, and nothing in AD-6 says a fingerprint records which serializer produced it.
- **Tightening:** Amend AD-6: exactly one `fingerprint(doc)` function, in one named `usecases/` module, capability-probed via the AD-11 shim; the returned value is tagged with its serializer + algorithm version (`fp1-exportBinary:<sha256>` / `fp1-brep:<sha256>`); equality comparison is defined only between same-tag values; cross-tag comparison falls back to the mass-property oracle and is reported as `DEGRADED`, never as clean equality. AD-5 amended: snapshot and re-hash MUST use the same function instance/config within one transaction.

### H-2. Anchor-frame derivation: two graders, two frames, opposite verdicts on the same part

- **Units:** benchmark/spec author (AD-13) vs independent grader author (AD-13) — or dev grader vs sealed held-out grader, or grader vs AD-17 harness re-execution.
- **Incompatible builds both ADs permit:** AD-13 requires assertions "in an explicit anchor frame" but never defines how a frame is derived or where it is declared. Build A: grader evaluates in the document world frame — a geometrically perfect part built rotated 90° fails "hole axis ∥ Z". Build B: grader canonicalizes to a principal-axes/COM or bbox-aligned frame — the same part passes. Both frames are "explicit". Dev and held-out graders (deliberately independent implementations) fork here silently; AD-14's statistics then compare pass rates measured in different geometries. The fault-injection suite won't catch it: both graders individually hit ≥95 % sensitivity against their *own* frame convention.
- **Tightening:** Amend AD-13: the anchor frame is part of the assertion vocabulary in `contracts/` — each spec declares one frame from a closed derivation set (`world`, `bbox-canonical` with documented axis-ordering tie-break rules, `named-datum(<Name>)`), graders MUST evaluate in the spec-declared frame, and the frame identifier appears in the report banner. Specs with no declared frame are invalid, not defaulted.

### H-3. Transaction protocol does not compose: tool-calls-tool and preview/apply both break AD-5's "every mutation" quantifier

- **Units:** Phase 2 mutation-tool authors (a `feature_*` tool that internally invokes `sketch_*` use cases) vs the AD-5 protocol itself; also preview author (AD-10) vs mutation author (AD-5).
- **Incompatible builds both ADs permit:** AD-5 binds "every mutation tool" to snapshot → `openTransaction` → op → verify → commit. Build A: a composite `feature_pocket_from_profile` calls the sketch use case internally; the inner call, being a mutation, dutifully opens its own transaction inside the outer one — FreeCAD transactions do not nest cleanly, so inner commit/abort corrupts the outer rollback proof. Build B: the composite author, to avoid nesting, calls the sketch op *without* the protocol — now a mutation ran outside the full per-op protocol and AD-5's letter is arguably violated or arguably satisfied "at the tool boundary", depending on which author you ask. Preview fork: AD-10's TempDoc ops are literally mutations; one preview author wraps TempDoc edits in the full AD-5 protocol (fingerprint + transaction on a throwaway doc), another treats TempDoc as exempt — and if apply composes "run preview for the diff, then mutate live", the two authors disagree on whether one or two transactions open. Additionally, AD-7's `snapshot_references` baseline is taken on the TempDoc by one author and on the live doc at apply-time by the other, so the confirmed diff and the applied-result audit are computed against different baselines.
- **Tightening:** Amend AD-5: the transaction protocol applies exactly once, at the outermost tool boundary; a re-entrancy guard makes nested use-case invocations join the open transaction (no inner open/commit/abort); TempDoc operations are explicitly exempt from AD-5 (failure handling = discard doc), stated in AD-10; apply MUST take its AD-7 reference snapshot on the live document at apply time, and the user-confirmed diff is re-validated against the live-doc post-verify before commit.

### H-4. Capability probes outside the shim: two compliant probes, two different answers, contradictory TNP verdicts

- **Units:** Phase 0 tool author (uses shim's `element_map_available()`) vs Phase 2 mutation author (probes `hasattr`/attribute presence directly at point of use).
- **Incompatible builds both ADs permit:** AD-11 puts "version-sensitive calls" in the shim and enumerates a table — but "version-sensitive" is judged by each author, and the Consistency Conventions command "capability probes at runtime, never version sniffing", which a *direct* `hasattr(shape, 'ElementMap')` probe satisfies to the letter without touching the shim. The shim's probe and the local probe can disagree (different attribute, different object, different FreeCAD build quirk): one tool reports AD-7 `UNSUPPORTED`, its sibling reports a clean TNP audit on the same document in the same session. AD-7's hard gate is only as consistent as the probe it consults, and nothing forces one probe.
- **Tightening:** Amend AD-11: *all* capability probes are shim exports (closed, named set: `element_map_available()`, `export_binary_available()`, `varset_available()`, `render_available()`, …); `hasattr`/`getattr`-with-default against FreeCAD objects outside the shim is banned for capability decisions and CI-grepped; AD-7 and AD-6 name the specific shim probe that gates them.

---

## MEDIUM

### M-1. Skills router and forced-subset injection can both be live in one session

- **Units:** skills-loader author (production metadata-first router on the one FastMCP server object) vs ablation-harness author (forced explicit-subset injection, AD-15's "portable second-harness mechanism").
- **Incompatible builds both ADs permit:** AD-15 defines two loader *modes* but never says what a mode is scoped to (server? session? request?) or who enforces exclusivity. The router author ships routing enabled by default on the shared server; the ablation author injects a forced subset via the injection path into a session on that same server. Each obeys its half of AD-15; the ablation session receives forced subset ∪ routed bodies, the measured delta is contaminated, and the "routed subset logged" line makes the run *look* clean because the harness never reads the router's log. AD-14's carefully-policed statistics are then computed over a corrupted treatment condition.
- **Tightening:** Amend AD-15: loader mode is a per-session attribute declared at session initialization; the server MUST refuse router activation for any session declared `ablation` (hard error, not silent skip); every report banner (Consistency Conventions row) additionally records loader mode + effective loaded-skill set as observed *server-side*.

### M-2. Audit log: one mandate, two writers, no schema

- **Units:** Phase 2 mutation-tool author (AD-5/AD-17 mutation audit) + AD-4 `debug_exec` author + AD-10 auto-approval author vs Phase 4 supervisor author (consumes the log to re-verify claims per AD-17).
- **Incompatible builds both ADs permit:** Three ADs (4, 10, 17) each independently mandate append-only audit entries; the Conventions fix only "JSON-lines per job/session". No record schema, no owner, no designated writing process. Build A: mutation audit written by the use case *inside* FreeCAD as `{ts, tool, fp_before, fp_after}`. Build B: exec audit written by the external MCP server as `{time, code, operator}` to a different file. Build C: auto-approvals logged by the harness in its own run log. The Phase 4 supervisor, promised a unified audit trail "from Phase 0", finds three shapes in three places written by two processes — and in GUI mode the in-FreeCAD writer and external writer can interleave on one file without append coordination.
- **Tightening:** New AD (or amend AD-17): `AuditRecord` schema lives in `contracts/` (fields: `ts`, `session`, `kind ∈ {mutation, exec, auto_approve, rollback}`, `tool`, `fingerprint_before/after`, `outcome`, `detail`); exactly one writer per session — the external adapter process persists, in-FreeCAD code *returns* audit payloads over the RPC channel (C-1) rather than writing files; file path derivation is fixed by convention.

---

## LOW

### L-1. AD-17's terminal set has no home for cancel/decline outcomes

- **Units:** Phase 2 preview author (AD-10 `accept`/`decline`/`cancel` elicitation) vs harness/job-API authors (AD-17 closed set).
- **Incompatible builds both ADs permit:** a declined/cancelled mutation is a terminal outcome that is none of `OK | SPEC_FAILED | … | INVALID_INPUT`. One author maps decline → `INVALID_INPUT` (misleading), another → `OK` with a detail flag (an "HTTP 200 for a not-done part" — the exact pathology AD-17 exists to prevent), a third invents `DECLINED` off-set.
- **Tightening:** Amend AD-17: add `CANCELLED` (or `DECLINED`) to the closed set now — the set is explicitly closed, so late additions are schema breaks at every consumer.

### L-2. "Internal mm/deg" vs FreeCAD-native radians at the boundary

- **Units:** any two tool authors. Conventions fix mm/deg for tool params/results, but FreeCAD constraint/placement APIs are radians in places; each author picks their own conversion point (at the envelope? in the use case? in a helper?), producing double-conversion or none when use cases call each other (see H-3 composition).
- **Tightening:** One conversion rule in Conventions: contracts-ring values are always mm/deg; conversion happens exactly once, in the use-case boundary decorator/helper named in `usecases/`; internal use-case-to-use-case calls pass FreeCAD-native units.

---

## Summary table

| ID | Tier | Hole | Fix target |
| --- | --- | --- | --- |
| C-1 | Critical | RPC wire contract unowned between server and listener | New AD / amend AD-2 |
| C-2 | Critical | Envelope vs report vs job status: vocabulary closed, schemas unowned | Amend AD-17 |
| C-3 | Critical | Document open/close + TempDoc lifecycle has four uncoordinated owners | New AD; amend AD-10 |
| H-1 | High | Fingerprint `exportBinary` fallback forks per call site and per version | Amend AD-6 (+AD-5) |
| H-2 | High | Anchor frame derivation undefined — graders fork | Amend AD-13 |
| H-3 | High | AD-5 doesn't compose: nested tools and preview/apply double-transaction | Amend AD-5, AD-10 |
| H-4 | High | Capability probes legal outside shim — contradictory gates | Amend AD-11 |
| M-1 | Medium | Router + forced-injection co-active in one session pollutes ablation | Amend AD-15 |
| M-2 | Medium | Audit log: 3 mandates, 2 writer processes, 0 schemas | New AD / amend AD-17 |
| L-1 | Low | No terminal status for declined/cancelled mutations | Amend AD-17 |
| L-2 | Low | Unit-conversion point unspecified at use-case boundary | Amend Conventions |
