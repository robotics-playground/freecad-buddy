# Epic 1 Context: Verifiable FreeCAD Bridge (Phase 0 · gate G0)

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Epic 1 builds the foundation every later capability calls: a programmatic bridge that lets a developer or MCP client drive FreeCAD — create/open/save/close documents, query model state, capture screenshots, export files — and trust every result through deterministic verification rather than "bytes were written" assumptions. There is no AI in this epic; it is pure infrastructure. It establishes the repo scaffold with enforced architecture rings, the contracts vocabulary all components share, the same tool implementations across three hosts (GUI, headless, FreeCADCmd fallback), the verification core proven against golden models and fault suites, and the mechanical gate runner that will decide every phase exit. Getting this right is what makes later assistant/copilot/designer claims falsifiable instead of vibes-based.

## Stories

- Story 1.1: Repo Scaffold, CI Matrix & Phase 0 Spikes
- Story 1.2: Data Contracts Package
- Story 1.3: Entry Gate G0.E — Golden Models, Fault Suite, Honest-Failing Benchmark
- Story 1.4: Document Lifecycle, Headless Host & First MCP Surface
- Story 1.5: Read-Only Query Tools
- Story 1.6: Verification Core — Fingerprint, Shape, Recompute, Sketch
- Story 1.7: Exports with Paired Verification
- Story 1.8: GUI Host — Addon, RPC Listener & Main-Thread Marshal
- Story 1.9: View-Controlled Screenshots
- Story 1.10: Gate G0 Exit

## Requirements & Constraints

- Documents are targeted only by explicit handle; `ActiveDocument` is never an implicit target. Documents open/close only through `document_*` use cases (harness and supervisor included). Mutating calls on one document serialize (single writer).
- Model state is fully observable read-only: large-tree-safe summarized feature tree (capped node count, `truncated` flag, never a raw dump), object properties + error states via `getStatusString()`, mass properties with explicit units, dependency edges, sketch geometry/constraints, placements, runtime capabilities.
- Screenshots render a constructed scene (include/exclude objects, per-object transparency/color, focus-on-element camera framing, highlight, camera presets) that never mutates the document or the user's viewport — document fingerprint before must equal after. Missing GL/GUI degrades to `render.available: false` with a reason, never a hard failure.
- Every export (STEP, STL, 3MF) counts as done only after its paired re-import verify tool passes with independent oracles; `export_*` results carry `verified: false` until then.
- Verification is deterministic and measured: shape validity/watertightness/volume/bbox/counts, sketch DoF pass signal, recompute-clean sweep, document fingerprint compute/compare, TNP reference audit.
- No validator's scores are citable until it proves sensitivity ≥95% and false-alarm ≤5% on its own ≥10-case fault suite. The producing agent never grades itself — pass/fail comes from deterministic code only.
- Gate ordering (AD-19): the entry-gate artifacts (golden models, fault suites, honest-failing benchmark) land and fail honestly against a stub before any tool code exists. Gate G0 exit is computed mechanically from stored ValidationReports plus run-bound human sign-off tokens — reproducible as a pure function from files alone.
- `debug_exec` is operator-only: absent from the tool list unless an env flag is set, every call audit-logged, permanently off in service mode. An append-only audit log (JSON-lines) records every mutation, exec, preview, approval, and rollback from Phase 0.
- Success metrics for G0: both transports list+call tools; ≥15 tools in the gate namespaces all schema-validated (catalog delivers 17 query/document/export + 7 verify); golden models match within ±0.1%; ≥30 tests green on both blocking CI legs; STEP round-trip verified.
- Provenance policy: shipped benchmark/golden artifacts come only from commercial-clean sources with per-item license checks and documented real-world basis — never reverse-fit to agent ability.

## Technical Decisions

- **Clean Architecture, dependencies inward only.** Rings: `contracts/` (stdlib only) → `usecases/` (stdlib + FreeCAD App API via the version shim) → `adapters/` → `hosts/`. `FreeCADGui`/Qt/Coin are importable only in `hosts/`, with exactly two `adapters/` exemptions: the render capability probe and the main-thread marshal (QtCore primitives only, imported inside functions). CI (`check_imports.py`, AST walk) enforces this and fails naming the file + rule.
- **In-FreeCAD code is dependency-free.** Anything running inside the FreeCAD process imports stdlib + FreeCAD API only. All third-party deps (mcp/FastMCP, trimesh, lib3mf, admesh, pytest) live in the external uv-managed process. Dual packaging: uv pyproject for the external process; a build-script-assembled addon that copies the whole package (in-FreeCAD code simply never imports the ext-only modules).
- **Three hosts, one implementation.** GUI mode = external MCP server process + thin in-FreeCAD RPC listener that marshals every FreeCAD call to the Qt main thread (postEvent pattern); addon start deferred until `FreeCAD.GuiUp` via `QTimer.singleShot`. Headless mode = single process calling the tool core inline. Fallback where the external interpreter cannot `import FreeCAD` = FreeCADCmd-hosted RPC listener with inline dispatch. The MCP protocol server is always external; the addon only starts the RPC listener.
- **Contracts built first.** Every other component consumes contract types; nothing invents its own. Closed terminal-status set (`OK | SPEC_FAILED | RECOMPUTE_ERROR | TIMEOUT | OOM_KILLED | WORKER_CRASHED | INVALID_INPUT`). `ResultEnvelope`, `ValidationReport` (with mandatory banner: FreeCAD version, `ElementMapVersion`, validator sensitivity, Wilson CI where a rate is claimed), `JobStatus`, `AuditRecord`, `GeometryDiff`, `DocHandle`/selectors, `FingerprintRecord`, JSON-RPC frame types + `rpc_hello` handshake. Every wire object carries a `schema: "fcb.<name>/1"` tag; schemas are generated into `jsonschema/` and drift-checked in CI (regeneration must be byte-identical). All wire schemas are stdlib-only and additive-only within a major.
- **Fingerprint (AD-6):** exactly one `fingerprint()` implementation. SHA-256 over per-object shape bytes (objects sorted by immutable `Name`) plus a quantized mass-property tuple (volume, area, bbox, COM, principal moments @1e-6) as an independent cross-oracle. The serializer is shim-probed (`exportBinary`, else `exportBrep` stream) and every hash is tagged with its serializer id — cross-tag comparison is banned. Document-XML/FCStd and tessellation hashing are banned as identity oracles.
- **Sketch pass signal (AD-8):** PASS ⇔ `sketch.FullyConstrained == True` read after `doc.recompute()`. Hard fail on conflicting/malformed/over-/under-constrained/degenerate; redundant constraints warn only; `solve()` return codes are logging-only.
- **TNP audit (AD-7):** `snapshot_references` before, `audit_references` after recompute. Layer 0 = `isValid()`/`getStatusString()` sweep; Layer 1 = mapped-name diff flagging `?`-markers, silent re-points, count drops (the FeatureDressUp silent-drop trap); Layer 2 (`getElementHistory`) only where Layer 1 is ambiguous. No element map → report `UNSUPPORTED`, never clean. An `ElementMapVersion` bump re-baselines, it does not fail.
- **Export/verify pairing (AD-9):** STEP is canonical round-trip (AP242, `write.step.unit=MM` pinned per call, ±0.1%). One tessellation source (`MeshPart.meshFromShape`, linear + angular deflection) feeds both STL and 3MF. Oracles: trimesh primary + one independent second checker for STL; lib3mf + trimesh + FreeCAD self-read for 3MF. Independent-oracle disagreement = FAIL. Mesh volume tolerance derives from the deflection used, never ±0.1%.
- **Version shim (AD-11).** All version-sensitive calls live in one module: `AttachmentSupport`/`Support` accessor, `element_map_available()` probe (hard-gates the TNP layer), `addObject` type-string table, VarSet-with-Spreadsheet-fallback driving-dimension façade, capability banner. Behavior is gated by runtime capability probes, never version-string comparison. Supported: FreeCAD 1.0.x (floor, Py 3.11) and 1.1.x (primary, Py 3.12), both blocking CI; 1.2-dev is a weekly allowed-to-fail canary.
- **RPC wire:** NDJSON JSON-RPC 2.0 over localhost TCP; `rpc_hello` handshake carries contract_version + a per-session `secrets.token_urlsafe(32)` token compared with `hmac.compare_digest`; discovery file at `<FreeCAD appdata>/freecad-buddy/rpc-<pid>.json` (0600 perms); per-method timeouts. A marshal timeout returns envelope `TIMEOUT` with `maybe_still_running: true` and puts the session in document-suspect state (next mutation refused until a fingerprint check). Wrong/missing token → `-32000`, connection closed.
- **Transport policy:** stdio for headless/dev/CI (logging to stderr only, `print()` to stdout banned); streamable HTTP for in-GUI long-lived serving; SSE never. Localhost-only binds by default; any remote bind is explicit operator opt-in.
- **Conventions:** underscore tool names with namespace prefixes (`query_`, `document_`, `export_`, `verify_`, `sketch_`, `feature_`, `preview_`, `debug_`) — dots illegal on the wire. Script against immutable `Name`, display `Label`; generated features get intent-bearing names. Internal units mm/deg; params/results carry explicit units; export calls pin units per call. Tool results = `structuredContent` validated by per-tool `outputSchema` + text mirror. Sub-element inputs are selector objects (geometric query or TNP mapped name); bare indexed names (`Face6`) resolve to mapped names at call time and are never stored. Tests inside FreeCADCmd use stdlib `unittest` only; pytest orchestrates from the external process.
- **Reuse before invention:** survey first; adopted components are wrapped, not forked; from-scratch builds record why nothing existing fit.
- **Phase 0 spikes to resolve and record (AR9):** `exportBinary` Python exposure (fallback `exportBrep`), conda FreeCADCmd path edge, `renderToImage` vs Xvfb, VarSet exposure on 1.1, MCP SDK v2 pin. Later stories cite these recorded decisions.
- **CI:** `ci.yml` runs `arch-checks` (uv-only) plus a blocking `headless` matrix {1.0.x/py3.11, 1.1.x/py3.12} on cached micromamba conda-forge envs, plus a non-blocking `render` leg (xvfb + `LIBGL_ALWAYS_SOFTWARE=1`, isolated). `canary.yml` runs the weekly 1.2-dev allowed-to-fail leg. The sealed `heldout/` split is excluded from every routine CI job.

## Cross-Story Dependencies

- Story 1.2 (contracts) is a hard prerequisite for every other story — all tool results, reports, RPC frames, and audit records consume its types.
- Story 1.1 (scaffold + CI + spike answers) gates the rest: the ring structure, import checks, and the serializer/host/render/dimension/SDK spike decisions are cited by later stories.
- Story 1.3 (entry gate G0.E: golden models + fault suite + honest-failing benchmark) must land before verification implementation (1.6) and exports (1.7) — those stories are graded by the artifacts 1.3 produces (AD-19 ordering).
- Story 1.4 (document lifecycle + first MCP surface + version shim + audit sink) underpins queries (1.5), verification (1.6), exports (1.7), and screenshots (1.9), which all target documents by handle.
- Story 1.8 (GUI host: addon, RPC listener, marshal) provides the transport for the GUI CI leg and the FreeCAD self-read leg used by 3MF export verification (1.7).
- Story 1.10 (G0 exit) depends on all prior stories being merged and their ValidationReports stored, plus the human `gui_smoke` token bound to that run.
- Epic-level: Epics 2→3→4→5 are gate-sequential and all depend on Epic 1's bridge and harness; Epic 6 (skills) runs parallel after Epic 1. Several stories note "groundwork" for later Phase 1 gate criteria (summarized tree, zero-mutation registry profile), meaning their contracts must anticipate downstream consumption.

## Reference Documents

The technical decisions above are distilled from these authoritative sources. The spine ADs are the binding contract; the design docs are the implementation-ready expansion. Read the relevant doc before implementing — it is mandatory context, not a suggestion. `project-context.md` (in every story's context) carries a full Design Document Index with per-doc "open it when" guidance.

**Architecture root:** `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/`

- Spine (21 ADs): `ARCHITECTURE-SPINE.md`
- Spec + phase gates (G0 criteria): `_bmad-output/specs/spec-freecad-buddy/`

**Design docs** (all under the architecture root's `design/`):

| Doc | Covers | Binding ADs |
| --- | --- | --- |
| `design/project-structure.md` | Repo tree, dual packaging, version legs, CI layout | AD-1, AD-11, AD-12 |
| `design/component-design.md` | Per-ring components, interfaces, call-path flows, phase availability | AD-1, AD-2 |
| `design/data-contracts-design.md` | `contracts/` types, versioning, cross-contract invariants | AD-6, AD-17, AD-20 |
| `design/mcp-tools-design.md` | Tool catalog, per-tool schemas, `debug_exec` rules | AD-4, AD-20 |
| `design/integration-mcp-freecad.md` | Topology, RPC wire, marshal, shim surface, render | AD-2, AD-3, AD-11 |
| `design/integration-mcp-clients.md` | Per-client wiring, confirm matrix, image delivery | AD-3, AD-10, AD-15 |
| `design/verification-design.md` | Mutation protocol, fingerprint, TNP guard, `verify_*`, tolerances | AD-5, AD-6, AD-7, AD-8, AD-9, AD-13 |
| `design/validation-harness-design.md` | Gate runner, benchmarks, sealing, stats, fault-injection, grader | AD-13, AD-14, AD-16, AD-19 |
| `design/skills-structure-design.md` | Skill store, loader, routing, budgets | AD-15 |
| `design/security-and-service-design.md` | `debug_exec` gating, RPC posture, audit log, Phase 4 sandbox | AD-4, AD-17, AD-18 |

**Per-story primary references** (Epic 1):

- **1.1 Scaffold/CI/spikes** → `design/project-structure.md`, spine Stack + Deferred
- **1.2 Contracts** → `design/data-contracts-design.md`, `design/component-design.md` §1
- **1.3 Entry gate G0.E** → `design/validation-harness-design.md`, spec phase-gates
- **1.4 Doc lifecycle / headless / MCP surface** → `design/integration-mcp-freecad.md`, `design/mcp-tools-design.md`, `design/component-design.md`
- **1.5 Read-only query tools** → `design/mcp-tools-design.md` §2 (`query_`), `design/data-contracts-design.md`
- **1.6 Verification core** → `design/verification-design.md` §1–§5, `design/data-contracts-design.md` §10
- **1.7 Exports + paired verify** → `design/verification-design.md` §6, `design/mcp-tools-design.md` (`export_`/`verify_export_`)
- **1.8 GUI host / RPC / marshal** → `design/integration-mcp-freecad.md` §3, `design/component-design.md` §3–§4
- **1.9 View-controlled screenshots** → `design/mcp-tools-design.md` §3.9, `design/integration-mcp-freecad.md` §6
- **1.10 Gate G0 exit** → `design/validation-harness-design.md` §3/§7, spec phase-gates (G0 exit)
