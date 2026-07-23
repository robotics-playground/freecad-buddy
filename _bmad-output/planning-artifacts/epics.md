---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - _bmad-output/specs/spec-freecad-buddy/SPEC.md
  - _bmad-output/specs/spec-freecad-buddy/phase-gates.md
  - _bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/project-structure.md
  - _bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/component-design.md
  - _bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md
  - _bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/skills-structure-design.md
  - _bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md
  - _bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-clients.md
  - _bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md
  - _bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/validation-harness-design.md
  - _bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/data-contracts-design.md
  - _bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/security-and-service-design.md
  - docs/intent.md
  - _bmad-output/planning-artifacts/research/index.md   # + 18 research reports as implementation supplement
---

# freecad-buddy - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for freecad-buddy, decomposing the requirements from the SPEC package (PRD-equivalent), phase gates, and Architecture spine + design docs into implementable stories. Research reports (`_bmad-output/planning-artifacts/research/`) are attached as implementation supplement — each story cites the reports its implementer should read.

## Requirements Inventory

### Functional Requirements

#### Bridge foundation — CAP-1

- **FR1** — A programmatic client can create, open, save, and close FreeCAD documents via MCP tools using explicit document handles — never implicit `ActiveDocument`. *(AD-20)*
- **FR2** — A client can query model state read-only: summarized feature tree (large-tree safe), object properties + error states, mass properties, dependency edges, sketch geometry/constraints, placements, runtime capabilities.
- **FR3** — A client can capture view-controlled screenshots — include/exclude objects, per-object transparency/color, focus-on-element camera framing, highlight, camera presets — via constructed-scene render that never mutates the document or user viewport.
- **FR4** — A client can export STEP, STL, and 3MF; every export completes only through its paired re-import verify tool with independent oracles. *(AD-9)*
- **FR5** — A client can verify geometry deterministically: shape validity/watertightness/volume/bbox/counts, sketch DoF + `FullyConstrained` pass signal, recompute-clean sweep, document fingerprint compute/compare, TNP reference audit. *(AD-6/7/8)*
- **FR6** — The same tool implementations serve three hosts: FreeCAD GUI (addon + RPC listener + main-thread marshal + auto-spawned external MCP proxy so opening FreeCAD is the only startup step), single-process headless, and FreeCADCmd-hosted RPC fallback. *(AD-2)*

#### Assistant — CAP-2

- **FR7** — An assistant answers document questions (tree explanation, error diagnosis, next-tool guidance) through read-only tools, on ≥2 LLM backends including a local model with ReAct fallback adapter.

#### Copilot — CAP-3

- **FR8** — A copilot executes one natural-language mutation at a time through typed `sketch_`/`feature_`/`document_` tools; every mutation runs the uniform transaction protocol: fingerprint snapshot → transaction → recompute → post-verify → commit, or hash-proven rollback with saveCopy fallback. *(AD-4/5)*
- **FR9** — Before any Phase 2 mutation, a dry-run on a TempDoc copy returns a structured geometry diff (+ optional before/after renders with view control); execution is confirmation-gated: MCP elicitation, `preview_id` token fallback, or fail-closed headless with audit-logged `autoApprove`. *(AD-10)*
- **FR10** — Bridge-owned undo restores exact prior state, verified by fingerprint comparison in 100 % of cases. *(AD-6)*
- **FR11** — A TNP guard snapshots all reference-holding subsystems before each mutation and audits after recompute — flags broken (`?`-marker), silently re-pointed, and dropped references; reports `UNSUPPORTED` (never clean) without an element map. *(AD-7)*

#### Designer — CAP-4

- **FR12** — A designer loop turns a written part spec into a parametric part: plan (human-approved once) → execute Phase 2 tools → measure against compiled spec assertions in a declared anchor frame → self-repair ≤3 iterations; convergence = geometry assertions PASS ∧ visual judge PASS. *(AD-13/21)*
- **FR13** — An independent visual judge (vision model, never the actor) verifies the standard visual set — 3D iso render + focus views + dimensioned TechDraw front/top/right projections — against the spec checklist; conjunctive with geometry, fail-closed when render/drawing/judge unavailable. *(AD-21)*
- **FR14** — Generated parts expose driving dimensions as named parameters (VarSet with Spreadsheet fallback façade); editing one parameter recomputes clean. *(AD-11)*

#### Autonomous service — CAP-5

- **FR15** — A headless job API accepts spec submissions and delivers validated model + supervisor-re-executed ValidationReport + STEP/STL/3MF + rendered views; supports revision requests preserving unrelated geometry; completes an agent-to-agent submit → inspect → revise → accept cycle. *(AD-17/18)*

#### Skills library — CAP-6

- **FR16** — A skills library of 12 Track A+B skills (4 mandatory sections, ≤1,500 words each) loads via two modes: production metadata-first router (2–5 bodies, ≤10K tokens) and ablation forced explicit-subset injection with auto-activation disabled. *(AD-15)*

#### Validation harness — CAP-7

- **FR17** — A gate runner executes phase-gate criteria (G0–G4, GS) against benchmarks, emits contracts-owned ValidationReports, and computes gate verdicts mechanically: pass rules on report fields + validator sensitivity currency + sealed held-out R≥10 + human sign-off tokens. *(AD-19)*
- **FR18** — A fault-injection framework validates every validator (planted defects + clean controls) and tracks per-validator sensitivity/false-alarm with source-hash staleness. *(AD-13)*

#### Cross-cutting

- **FR19** — `debug_exec` exists as operator-only capability: env-flag gated, unregistered when off, permanently off in service mode, every call audit-logged. *(AD-4)*
- **FR20** — An append-only audit log records every mutation, exec, preview, approval, and rollback from Phase 0 using the contracts-owned record type. *(AD-17)*

### NonFunctional Requirements

| ID | Requirement | Source |
| --- | --- | --- |
| **NFR1** | The producing agent never grades itself — pass/fail comes from deterministic code or independent graders/judges only | AD-13 |
| **NFR2** | Every validator proves sensitivity ≥95 % / false-alarm ≤5 % on its fault suite before its scores are citable; suites land before phase implementation | AD-13, AD-19 |
| **NFR3** | Statistics discipline: majority-of-R scoring (R=5 dev / R≥10 exit), Wilson 95 % CI beside every rate, exact McNemar for ablations, pp-threshold claims on n≥40 sets, dev/held-out gap >15pp blocks exit | AD-14 |
| **NFR4** | All suites run headless in CI on the FreeCAD 1.0.x (Py 3.11) + 1.1.x (Py 3.12) blocking matrix + 1.2-dev canary; version-sensitive calls live in one shim behind capability probes | AD-11 |
| **NFR5** | In-FreeCAD code imports stdlib + FreeCAD API only; all third-party deps live in the uv-managed external process | AD-12 |
| **NFR6** | Clean Architecture dependency rule enforced by CI import checks; Qt only in `hosts/` + the two named adapter exemptions | AD-1 |
| **NFR7** | Security posture: localhost-only binds, per-session RPC token, stderr-only logging on stdio, no free-form exec in any AI path | AD-3, AD-4 |
| **NFR8** | Benchmark artifacts only from commercial-clean, per-item license-checked sources with documented real-world provenance — never reverse-fit to agent ability | AD-16 |
| **NFR9** | Performance: Phase 1 median response ≤15 s; Phase 3 median ≤10 min/part; Phase 4 50-job soak <20 % memory growth, no crash/hang | phase gates |
| **NFR10** | All wire schemas (ResultEnvelope, ValidationReport, JobStatus, AuditRecord, GeometryDiff, RPC frames) are contracts-owned, stdlib-only, additive-only within a major | AD-17 |
| **NFR11** | Phase ordering: entry gate (validators + benchmark vs stub + fault suite + rubric + reuse survey) lands before phase implementation; previous gate fully green before next phase starts | AD-19 |
| **NFR12** | Skills shape enforced by CI: 4 exact sections, ≤1,500-word bodies, <1,024-char routing descriptions, no cross-skill body dependencies | AD-15 |
| **NFR13** | Reuse before invention: adopted components wrapped not forked; from-scratch builds record why nothing existing fit | spine conventions |

### Additional Requirements

#### Scaffold & packaging

- **AR1** — No starter template. Greenfield custom scaffold per project-structure design: src-layout `freecad_buddy` package (`contracts/`, `usecases/`, `adapters/`, `hosts/`), `skills/`, `benchmarks/`, `tests/` (in-FreeCAD stdlib-unittest + external pytest), `scripts/` (`check_imports`, `check_skill_shape`, `build_addon`), dual CI workflows (`ci.yml` matrix + `canary.yml` weekly).
- **AR2** — Dual packaging: uv pyproject for the external process (mcp, trimesh, lib3mf; admesh optional Linux); build-script-assembled FreeCAD addon (`package.xml` + thin `InitGui.py` + full package copy) with `FREECAD_BUDDY_SRC` dev override.
- **AR3** — `contracts/` is built first — every other component consumes its types; `jsonschema/` generated + drift-checked in CI.

#### Bridge internals

- **AR4** — RPC wire: NDJSON JSON-RPC 2.0 over localhost TCP; `rpc_hello` handshake (contract_version + token); discovery file `<FreeCAD appdata>/freecad-buddy/rpc-<pid>.json` (0600); method registry with per-method timeouts; marshal timeout → document-suspect session state.
- **AR5** — Version shim module: `AttachmentSupport` accessor, `element_map_available()` probe, type-string table, driving-dimension façade, capability banner.
- **AR6** — Render stack: constructed-scene renderer (`subgraphFromObject` + `SoQtOffscreenRenderer`); detection ladder `gui_constructed`/`offscreen`/`none`; CI render leg = xvfb + `LIBGL_ALWAYS_SOFTWARE=1`, isolated non-blocking.

#### Harness mechanics

- **AR7** — Held-out sealing: age-encrypted archive + `SEAL.json` manifest, human-held key, unseal only via gate-exit run, burned-set rule on failed exits.
- **AR8** — Human sign-off tokens (`spot_audit`, `rubric_review`, `gui_smoke`, `skills_accuracy`) as run-bound JSON artifacts the runner verifies.

#### Phase-specific

- **AR9** — Phase 0 spike items (first week): `exportBinary` Python exposure, conda FreeCADCmd path edge, `renderToImage` vs Xvfb, VarSet exposure on 1.1, MCP SDK v2 pin.
- **AR10** — Phase 4 direction (deferred detail): supervisor never imports FreeCAD; spawn pool `maxtasksperchild=1`; `run_job_in_sandbox` wrapper (nsjail/bwrap Linux, WSL2-preferred Windows); egress deny-by-default; `jobs/<id>/` data plane.

#### Research supplement — implementer reading list per story area

| Story area | Research reports to read |
| --- | --- |
| Bridge / RPC / embedding | MCP embedding in GUI process; FreeCAD MCP servers survey |
| CI setup | Headless FreeCAD in CI |
| Verification (rollback, TNP, sketch, assertions, exports) | Undo/transaction geometry hashing; TNP post-mutation audit; sketch DoF query; geometry-to-spec assertions; 3MF export fidelity |
| Harness / benchmarks | Benchmark statistics small-n; CAD dataset licenses |
| Skills | Skill token budget / context limits |
| Phase 1 local backend | Local LLM MCP tool-use |
| Phase 2 preview/confirm | Headless preview/diff channel |
| Phase 4 service | OS-level sandboxing; process-per-job isolation; Python execution sandbox policy |
| Render / screenshots | Offscreen screenshot FreeCADCmd |
| Version shim | FreeCAD version matrix |
| Tool authoring reference | FreeCAD features & functionalities catalog |

### UX Design Requirements

None — no UX design contract exists yet (deliberate: no UI before the Phase 1/2 GUI panel; UX workflow to run before Phase 2 panel work).

### FR Coverage Map

| FR | Epic | Note |
| --- | --- | --- |
| FR1–FR6 | Epic 1 | Bridge tools: documents, queries, screenshots, exports, verify family, three hosts |
| FR17, FR18 | Epic 1 | Gate runner core + fault-injection framework (G0 slice; extended per later gate) |
| FR19, FR20 | Epic 1 | debug_exec gating; append-only audit log from Phase 0 |
| FR7 | Epic 2 | Read-only assistant on ≥2 backends |
| FR8–FR11 | Epic 3 | Typed mutations + transaction protocol; preview/confirm; verified undo; TNP guard |
| FR12–FR14 | Epic 4 | Designer loop (geometry ∧ visual convergence); visual judge; named parameters |
| FR15 | Epic 5 | Headless job API, revisions, agent-to-agent cycle |
| FR16 | Epic 6 | 12-skill library + two-mode loader + ablation |

All 20 FRs mapped; none orphaned. NFR1–NFR13 bind cross-epic and are enforced per story via gate criteria and CI checks.

---

## Epic List

### Epic 1: Verifiable FreeCAD Bridge (Phase 0 · gate G0)

A developer or MCP client can programmatically drive FreeCAD — documents, queries, screenshots, exports — and trust every result through deterministic verification. No AI; the foundation every later epic calls.

**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR17, FR18, FR19, FR20

### Epic 2: Read-Only Model Assistant (Phase 1 · gate G1)

A FreeCAD user can ask questions about their open model — tree explanation, error diagnosis, next-tool guidance — and get graded-correct answers on Claude or a local model. Zero mutation risk.

**FRs covered:** FR7

### Epic 3: Confirmed Copilot (Phase 2 · gate G2)

A user can issue one natural-language modeling command, see a structured preview diff, confirm, and get a verified operation — with proven rollback, exact undo, and TNP guarding on failure.

**FRs covered:** FR8, FR9, FR10, FR11

### Epic 4: Spec-to-Part Designer (Phase 3 · gate G3)

A user hands over a written part spec and receives an editable parametric part that measurably meets it — geometry assertions ∧ independent visual judge, self-repaired without babysitting.

**FRs covered:** FR12, FR13, FR14

### Epic 5: Autonomous Design Service (Phase 4 · gate G4)

Any agent or human submits specs to a headless job API and gets validated models, exports, reports, and revisions — no GUI, no human in the loop, sandboxed.

**FRs covered:** FR15

### Epic 6: CAD Skills Library & Ablation (parallel track · gate GS)

Any LLM harness gains measurable CAD judgment from 12 curated skills — each proven by ablation to move a benchmark number or cut. Runs alongside Epics 2–4; needs Epic 1's harness.

**FRs covered:** FR16

**Dependency chain:** 1 → 2 → 3 → 4 → 5 (gate-sequential per AD-19); 6 parallel after 1.

---

## Epic 1: Verifiable FreeCAD Bridge (Phase 0 · gate G0)

A developer or MCP client can programmatically drive FreeCAD — documents, queries, screenshots, exports — and trust every result through deterministic verification. No AI; the foundation every later epic calls.

> **Story context convention:** every story below implements against the architecture spine (AD-refs cited inline) and its design docs; *Read* lines name the design docs + research reports the implementer loads first (per the Research supplement table).

### Story 1.1: Repo Scaffold, CI Matrix & Phase 0 Spikes

> **As** a bridge developer, **I want** a clonable repo with enforced architecture rings, both CI workflows, and the Phase 0 unknowns resolved, **so that** every later story lands on a structure that cannot silently violate the spine.

**Acceptance Criteria:**

1. **Given** a fresh clone  
   **When** I run `uv sync --all-extras` and `uv run pytest tests/external`  
   **Then** the environment builds and the (initially small) external suite passes  
   **And** the tree matches project-structure.md §1 (contracts/usecases/adapters/hosts, skills/, benchmarks/, tests/infc+external, scripts/, addon/)

2. **Given** a module that imports `FreeCADGui` from `usecases/` or a third-party lib from `contracts/`  
   **When** `scripts/check_imports.py` runs (locally or in CI)  
   **Then** the build fails naming file + rule (AD-1, AD-12; Qt whitelist = `hosts/`, `adapters/marshal.py`, `adapters/render_probe.py`)

3. **Given** a push to any branch  
   **When** `ci.yml` runs  
   **Then** `arch-checks` (uv-only) and `headless` matrix legs {FreeCAD 1.0.*/Py 3.11, 1.1.*/Py 3.12} execute with cached micromamba envs, both blocking (NFR4)  
   **And** `canary.yml` exists as weekly allowed-to-fail 1.2-dev leg

4. **Given** the five Phase 0 spike questions (AR9: `exportBinary` Python exposure, conda `FreeCADCmd` path edge, `renderToImage` vs Xvfb, VarSet exposure on 1.1, MCP SDK v2 pin)  
   **When** the story completes  
   **Then** each spike has a recorded answer in the repo (decision note), and the serializer/H1-vs-H2/render-ladder/dimension-façade/SDK choices used by later stories cite it

**References:** project-structure.md; headless-freecad-ci, freecad-version-matrix research.

### Story 1.2: Data Contracts Package

> **As** a bridge developer, **I want** the complete `contracts/` package with generated JSON Schemas and contract tests, **so that** every component built afterward consumes one schema vocabulary and none invents its own (AD-17).

**Acceptance Criteria:**

1. **Given** the modules per data-contracts-design.md §1 (status, envelope, report, job, audit, diff, document, fingerprint, rpc, assertions)  
   **When** `pytest tests/external/test_contracts.py` runs  
   **Then** all cross-contract invariants pass: single status vocabulary (grep-enforced), banner required on every ValidationReport, text-mirror round-trip, diff/audit vocabulary identity, fingerprint cross-tag comparison raises, DocHandle required on document-touching objects

2. **Given** the TypedDict definitions  
   **When** the schema generator runs  
   **Then** `contracts/jsonschema/*.schema.json` regenerate byte-identical (drift = CI failure)

3. **Given** any wire object  
   **When** serialized  
   **Then** it carries its `schema: "fcb.<name>/1"` tag; the status enum is the closed AD-17 set; stdlib-only imports throughout (NFR5, NFR10)

**References:** data-contracts-design.md; preview-diff-channel, process-per-job, undo-hashing research (schema sources).

### Story 1.3: Entry Gate G0.E — Golden Models, Fault Suite, Honest-Failing Benchmark

> **As** a project owner, **I want** the Phase 0 validators' test artifacts to exist and fail honestly before any tool code exists, **so that** AD-19's ordering holds and no tool is ever graded by an untested validator.

**Acceptance Criteria:**

1. **Given** `benchmarks/g0/golden-models/`  
   **When** inspected  
   **Then** it contains 5 hand-made reference models (.FCStd + expected.yaml with known volume/bbox/counts) each with a provenance manifest passing the AD-16 closed-source-kind check

2. **Given** `benchmarks/g0/fault-injection/`  
   **When** inspected  
   **Then** it contains ≥10 planted-defect cases (wrong volume, non-watertight, dropped solid, unit lie, degenerate face…) plus clean controls, each with `fault.kind` + `expectation`, and `_registry/validators.yaml` binds them to the verify-tool ids

3. **Given** no bridge implementation yet  
   **When** `python benchmarks/runner.py --gate G0 --stub` runs  
   **Then** every criterion FAILS honestly with structured ValidationReports (never green, never crash)

**References:** validation-harness-design.md; benchmark-statistics, cad-dataset-licenses research.

### Story 1.4: Document Lifecycle, Headless Host & First MCP Surface

> **As** an MCP client (human or agent), **I want** to connect over stdio and create/open/save/close FreeCAD documents by explicit handle, **so that** the first end-to-end tool calls work and every later tool has a document-targeting contract (AD-20).

**Acceptance Criteria:**

1. **Given** `uv run freecad-buddy serve --transport stdio --mode inline` (H1 host, or H2 fallback per spike 1.1)  
   **When** an MCP client runs `tools/list`  
   **Then** the `document_*` set + `query_capabilities` are listed, every tool with JSON inputSchema + outputSchema + docstring, names underscore-convention, all logging on stderr (AD-3)

2. **Given** `document_create` then `document_save`/`document_close` with the returned handle  
   **When** called  
   **Then** each returns a `fcb.result-envelope/1` with the handle echoed; a call omitting `doc` or using a stale handle returns `INVALID_INPUT` — `ActiveDocument` is never targeted implicitly

3. **Given** two concurrent mutating lifecycle calls on one document  
   **When** dispatched  
   **Then** they serialize (single-writer, AD-20)

4. **Given** the version shim (`usecases/shim.py`)  
   **When** `query_capabilities` runs on both CI legs  
   **Then** it reports FreeCAD version, `element_map_available`, serializer tag, varset backend, render=none-for-now, exec_enabled — all via runtime probes, never version-string comparison (AD-11)

5. **Given** `FREECAD_BUDDY_ALLOW_EXEC` unset  
   **When** `tools/list` runs  
   **Then** `debug_exec` is absent; set to `1` → present and every call writes append-only audit records (AD-4, FR19/20); audit sink writes `fcb.audit-record/1` JSON-lines for all lifecycle mutations

**References:** integration-mcp-freecad.md, component-design.md, security-and-service-design.md §1–3; mcp-embedding, python-sandbox-policy research.

### Story 1.5: Read-Only Query Tools

> **As** an MCP client, **I want** to inspect any document — tree, objects, mass properties, dependencies, sketches, placements, **so that** model state is fully observable without mutation risk.

**Acceptance Criteria:**

1. **Given** a document with >50 features  
   **When** `query_tree_summary` runs with default caps  
   **Then** it returns ≤`max_nodes` summarized nodes with `truncated: true`, per-node error states via `getStatusString()`, never a raw dump (G1.3 groundwork)

2. **Given** any object  
   **When** `query_object`, `query_mass_properties`, `query_dependencies`, `query_placement`, `query_sketch_info` run  
   **Then** each returns schema-valid envelopes with explicit units; sketch info lists geometry + constraints with 1-based ids mapped to names

3. **Given** the Phase 1 registry profile  
   **When** the registry is introspected  
   **Then** zero mutation tools are exposed in that profile (G1.6 groundwork)

**References:** mcp-tools-design.md §2–3; freecad-features catalog research.

### Story 1.6: Verification Core — Fingerprint, Shape, Recompute, Sketch

> **As** a bridge developer, **I want** deterministic verification tools proven against golden models and the fault suite, **so that** "the bridge says PASS" is backed by measured sensitivity, not hope (NFR1/2).

**Acceptance Criteria:**

1. **Given** the 5 golden models  
   **When** `verify_shape` runs with their expected.yaml bands  
   **Then** all fields (volume/bbox/counts/validity) match within ±0.1 % on both CI legs (G0.3)

2. **Given** the G0 fault-injection suite  
   **When** `python benchmarks/runner.py --gate G0 --criterion faults` (or `gate faults g0`) runs  
   **Then** sensitivity ≥95 % and false-alarm ≤5 %, recorded in `_registry/validators.yaml` with validator source hash (NFR2)

3. **Given** one document fingerprinted twice without change  
   **When** `fingerprint()` runs (serializer per spike 1.1, tagged)  
   **Then** digests are identical; a 1 µm dimension change, added hole, or mirror produces a different digest; cross-tag comparison raises (AD-6)

4. **Given** a sketch in any state  
   **When** `verify_sketch` runs after recompute  
   **Then** verdict follows AD-8 exactly: PASS ⇔ `FullyConstrained`, hard-fail on conflicting/malformed/over/under/degenerate, redundant = WARN only, `solve()` codes logging-only

5. **Given** a document with a deliberately broken object  
   **When** `verify_recompute` runs  
   **Then** the failing object + `getStatusString()` reason appear in the report; every report carries the banner (FreeCAD version, `ElementMapVersion`, validator sensitivity)

**References:** verification-design.md §2/4/5; undo-hashing, sketch-dof, tnp-audit research.

### Story 1.7: Exports with Paired Verification

> **As** an MCP client, **I want** STEP/STL/3MF exports that only count as done when independently re-verified, **so that** "the file was written" can never masquerade as success (AD-9).

**Acceptance Criteria:**

1. **Given** a golden model  
   **When** `export_step` (AP242, unit=MM pinned per call) then `verify_export_step` run  
   **Then** re-import into a fresh document shows volume ±0.1 %, `isValid`, topology counts equal (G0.5)

2. **Given** the same solid  
   **When** `export_stl` and `export_3mf` run  
   **Then** both consume one tessellation (`MeshPart.meshFromShape`, linear + angular deflection); `export_*` results carry `verified: false` until the paired verify passes

3. **Given** the mesh exports  
   **When** `verify_export_stl` (trimesh + second oracle per Phase 0 pin) and `verify_export_3mf` (lib3mf + trimesh + FreeCAD self-read via the in-FreeCAD leg) run  
   **Then** oracle disagreement forces FAIL; mesh volume tolerance derives from the deflection used, never ±0.1 %; the 3MF unit/`type="model"` lies from the fault suite are caught

4. **Given** the export fault cases (dropped solid, unit lie, hole, flipped normals, non-manifold, corrupt container)  
   **When** the fault run executes  
   **Then** sensitivity ≥95 % / FA ≤5 % for the export verifiers

**References:** verification-design.md §6; 3mf-export-fidelity research.

### Story 1.8: GUI Host — Addon, RPC Listener & Main-Thread Marshal

> **As** a FreeCAD GUI user, **I want** the bridge reachable from an external MCP client while FreeCAD is open, without freezes-crashes or open ports to strangers, **so that** the same tools work against my live session (G0.1 GUI leg).

**Acceptance Criteria:**

1. **Given** the built addon (`scripts/build_addon.py` output installed, or `FREECAD_BUDDY_SRC` dev mode)  
   **When** FreeCAD GUI starts  
   **Then** the listener starts only after `FreeCAD.GuiUp` via deferred `QTimer.singleShot`, binds 127.0.0.1, writes the 0600 discovery file with `secrets.token_urlsafe(32)` token (AD-2/3)

2. **Given** the external server (`--transport http --mode rpc`)  
   **When** an MCP client calls any tool  
   **Then** frames follow `contracts/rpc.py` (`rpc_hello` handshake, contract_version, token via `hmac.compare_digest`); every FreeCAD call executes on the Qt main thread through the postEvent marshal; wrong/missing token → `-32000`, closed

3. **Given** a marshal timeout  
   **When** it fires  
   **Then** the client receives envelope `TIMEOUT` with `maybe_still_running: true` and the session goes document-suspect (next mutation refused until a fingerprint check)

4. **Given** the RPC listener module  
   **When** `check_imports.py` runs  
   **Then** listener = stdlib-only, marshal = QtCore-only (AD-12, AD-1 exemptions)

5. **Given** FreeCAD GUI starts with the addon installed  
   **When** the bridge boots  
   **Then** after the listener is up the addon **auto-spawns the external MCP proxy** (`serve --mode rpc --transport http`, `:8765`) as a child process, using the project venv python **auto-discovered from the addon's own install path** (no env vars required; the addon never imports `mcp`); it is skipped when `FREECAD_BUDDY_NO_AUTO_MCP` is set or `:8765` is already served, and terminated on FreeCAD quit — so an MCP client reaches the live session with no manual `serve` command and no configuration. The manual `serve --mode rpc` CLI is a debug/troubleshoot fallback only.

**References:** integration-mcp-freecad.md §2–4, integration-mcp-clients.md §2; mcp-embedding, mcp-servers-survey research.

### Story 1.9: View-Controlled Screenshots

> **As** an MCP client, **I want** renders with include/exclude, transparency, focus-on-element, and camera presets, **so that** visual context is available and noise-free — without ever mutating the model.

**Acceptance Criteria:**

1. **Given** any document and render capability present  
   **When** `query_screenshot` runs with `view: {include, exclude, styles, focus, highlight, camera}` options  
   **Then** a PNG `resource_link` ≤1024 px returns; the constructed scene honors every option; document fingerprint before == after (nothing mutated); user viewport untouched in GUI mode

2. **Given** a `focus` selector resolving to one hole wall  
   **When** the render completes  
   **Then** the camera frames that element's bbox +margin and `scene.focused_on` echoes the resolution

3. **Given** no GL / no FreeCADGui importable  
   **When** `query_screenshot` runs  
   **Then** `render.available: false` with reason — never a hard failure; capability flag reports `none`

4. **Given** the CI render leg (xvfb + `LIBGL_ALWAYS_SOFTWARE=1`, non-blocking)  
   **When** it runs  
   **Then** a known box renders to a non-empty, correctly-sized PNG on the 1.1 leg

**References:** integration-mcp-freecad.md §6, mcp-tools-design.md §3.9; offscreen-screenshot research.

### Story 1.10: Gate G0 Exit

> **As** a project owner, **I want** the full G0 verdict computed mechanically from stored reports plus the human smoke token, **so that** Phase 0 exits exactly the way every later phase will — no self-grading, no vibes (FR17, AD-19).

**Acceptance Criteria:**

1. **Given** all prior stories merged  
   **When** `python benchmarks/runner.py --gate G0` runs on both blocking legs  
   **Then** G0.1–G0.5 all PASS on report fields: both transports list+call (G0.1), ≥15 tools in gate namespaces all schema'd (G0.2 — catalog delivers 17), golden models ±0.1 % (G0.3), ≥30 tests green both legs (G0.4), STEP round-trip (G0.5)

2. **Given** the GUI leg  
   **When** the human performs the smoke check (§4.1 dev flow + `tools/list` via a real client)  
   **Then** a `gui_smoke` token exists, run-bound (`binds_reports_sha256` matches), verified by `gate verdict`

3. **Given** the stored ValidationReports  
   **When** `gate verdict G0 --run <id>` re-runs standalone  
   **Then** the same verdict reproduces from files alone (pure function; an auditing agent could run it)  
   **And** every cited validator's sensitivity run is current (source-hash match, ≥95 %/≤5 %)

**References:** validation-harness-design.md §3/6/7; phase-gates.md G0.

---

## Epic 2: Read-Only Model Assistant (Phase 1 · gate G1)

A FreeCAD user can ask questions about their open model — tree explanation, error diagnosis, next-tool guidance — and get graded-correct answers on Claude or a local model. Zero mutation risk. *(Depends on Epic 1; G1.5 consumes the two skills drafted in Story 6.2.)*

### Story 2.1: Entry Gate G1.E — Eval Set, Rubric & Grader Validation

> **As** a project owner, **I want** the 50-question eval, 10 broken-document cases, human-authored rubric, and a fault-tested independent grader before assistant code exists, **so that** answer quality is decided by a validated grader, never the assistant (AD-19, NFR1).

**Acceptance Criteria:**

1. **Given** `benchmarks/g1/`  
   **When** inspected  
   **Then** 50 questions + expected findings, 10 broken-recompute documents with *the* failing object/cause named, `rubric.md` with worked pass/fail examples, and dev/held-out split sealed per AR7 exist — all provenance-manifested

2. **Given** planted confident-wrong answers  
   **When** `gate faults g1` runs the grader over them  
   **Then** grader sensitivity ≥95 % / FA ≤5 %; `g1/gate.yaml` declares `actor:` ≠ `grader:` and preflight hard-fails on identity

### Story 2.2: Assistant on the Claude Backend

> **As** a FreeCAD user, **I want** to ask about my open document in natural language and get correct, cited answers, **so that** I understand my model and errors without digging through the tree myself.

**Acceptance Criteria:**

1. **Given** the Phase 1 registry profile (zero mutation tools — G1.6)  
   **When** the assistant answers eval questions via `query_*` tools  
   **Then** dev-set pass rate trends toward ≥80 % (grader-scored, R=3 [stats]) with median latency ≤15 s using summarized tree queries (G1.1/G1.3)

2. **Given** a document with a broken recompute  
   **When** asked "what's wrong?"  
   **Then** the assistant names the failing object and cause via `verify_recompute` + `getStatusString` diagnostics (G1.2 target 8/10)

### Story 2.3: Local Backend + ReAct Fallback Adapter

> **As** a project owner, **I want** the same assistant running on a local model through native MCP and through the ReAct text-parse adapter, **so that** the bridge is proven model-agnostic (G1.4).

**Acceptance Criteria:**

1. **Given** the pinned local stack (llama.cpp + Qwen3-30B-A3B per Phase 1 pin, constrained decoding ON)  
   **When** the G1.1 sample re-runs  
   **Then** it completes through the identical tool surface over HTTP

2. **Given** the ReAct adapter (`adapters/`, same tool registry, schemas from contracts)  
   **When** run against an OpenAI-compatible endpoint  
   **Then** tool calls parse from fenced JSON, malformed JSON → one re-prompt then `INVALID_INPUT`; confirmation posture matches the no-elicitation matrix row

### Story 2.4: Gate G1 Exit

> **As** a project owner, **I want** the sealed held-out eval run with all G1 criteria green plus human tokens, **so that** Phase 1 exits mechanically.

**Acceptance Criteria:**

1. **Given** all G1 criteria  
   **When** `gate run g1 --exit` executes (held-out unsealed, R≥10, majority-of-R)  
   **Then** G1.1–G1.6 pass their rules with Wilson CIs reported; dev/held-out gap ≤15pp; `rubric_review` + `spot_audit` tokens present and run-bound

---

## Epic 3: Confirmed Copilot (Phase 2 · gate G2)

A user can issue one natural-language modeling command, see a structured preview diff, confirm, and get a verified operation — with proven rollback, exact undo, and TNP guarding on failure.

### Story 3.1: Entry Gate G2.E — Command Benchmark & Mutation Fault Suites

> **As** a project owner, **I want** the 40-command benchmark with per-command geometry assertions and the mutation fault suites landed before any mutation tool exists, **so that** Phase 2 code is born graded (AD-19).

**Acceptance Criteria:**

1. **Given** `benchmarks/g2/`  
   **When** inspected  
   **Then** 40 commands × 8 op types with assertions authored independently of implementation, dev/held-out split sealed, and fault cases covering wrong-parameter runs, the 5 TNP-provoking scenarios, the dress-up silent-drop trap, coincidental-hash, and #6031 rollback-boundary patterns

2. **Given** the stub bridge  
   **When** `gate run g2 --stub` executes  
   **Then** every criterion fails honestly

### Story 3.2: Mutation Protocol Runtime

> **As** a bridge developer, **I want** every mutation flowing through `run_mutation()` with hash-proven rollback and saveCopy fallback, **so that** no operation can leave the document in an unverified state (AD-5/6, FR8).

**Acceptance Criteria:**

1. **Given** any typed op wrapped by `run_mutation`  
   **When** post-verify fails or an exception raises  
   **Then** abort → recompute → re-hash proves restoration, escalating to saveCopy restore on mismatch; the result envelope reports `rolled_back` + proof path; audit records written (FR20)

2. **Given** the #6031-pattern fault case  
   **When** executed  
   **Then** the hash-mismatch path fires and the snapshot restore re-verifies (planted-fault caught)

### Story 3.3: Sketch Tools

> **As** a copilot user, **I want** NL-driven sketch creation, geometry, and constraints through typed tools, **so that** sketches reach `FullyConstrained` verifiably (G2.5).

**Acceptance Criteria:**

1. **Given** `sketch_create/add_geometry/add_constraint/set_datum/…` calls  
   **When** each executes  
   **Then** it runs under AD-5, returns `sketch_state` (embedded verify_sketch summary) + mutation block; conflicting/malformed constraint sets roll back automatically with solver diagnostics mapped to names

### Story 3.4: Feature Tools

> **As** a copilot user, **I want** pad/pocket/revolve/hole/fillet/chamfer/pattern/mirror/datum through typed tools with intent-bearing names, **so that** the feature tree reads like a build plan and every op is verified.

**Acceptance Criteria:**

1. **Given** each `feature_*` tool on benchmark models  
   **When** executed with selector-addressed references and explicit-unit Quantities  
   **Then** post-op geometry matches the command's assertions (drives G2.1 ≥85 %); sub-element inputs resolve to mapped names, never stored indexed names

### Story 3.5: TNP Guard Layers 1–2

> **As** a copilot user, **I want** silent reference breakage caught after every mutation, **so that** my model never corrupts quietly (FR11, G2.4).

**Acceptance Criteria:**

1. **Given** the 5 TNP-provoking scenarios  
   **When** the guard audits post-mutation  
   **Then** 5/5 flagged (BROKEN/REPOINTED/DROPPED), the dress-up count-drop caught, `ElementMapVersion` bump re-baselines instead of failing, and no-element-map reports `UNSUPPORTED` never clean

### Story 3.6: Preview Dry-Run & Structured Diff

> **As** a copilot user, **I want** to see exactly what an operation would change before it touches my model, **so that** I confirm from evidence, not faith (FR9, AD-10).

**Acceptance Criteria:**

1. **Given** `preview_dry_run` with any registered mutation op  
   **When** executed  
   **Then** the TempDoc (FCB_TMP_) diff returns all mandatory `fcb.geometry-diff/1` fields incl. TNP pre-check; live doc fingerprint unchanged; TempDoc cleaned by creator; optional renders honor `view` control

### Story 3.7: Confirmation Flow & Verified Undo

> **As** a copilot user, **I want** mutations gated on my confirmation and undo that provably restores state, **so that** I stay in control (G2.2/G2.3).

**Acceptance Criteria:**

1. **Given** the three confirm contexts (elicitation / `preview_id` token / headless fail-closed)  
   **When** a mutation is attempted without valid confirm  
   **Then** `INVALID_INPUT`, no execution; `autoApprove` uses are audit-logged with diff digest

2. **Given** `document_undo` after any benchmark op  
   **When** executed  
   **Then** fingerprint matches the pre-op hash in 100 % of cases (snapshot-restore path reported when taken)

### Story 3.8: Gate G2 Exit

> **As** a project owner, **I want** all G2 criteria green on the sealed set, **so that** Phase 2 exits mechanically.

**Acceptance Criteria:**

1. **Given** `gate run g2 --exit` (R≥10)  
   **When** it completes on both legs  
   **Then** G2.1–G2.6 pass (≥85 % commands, 100 % post-verify+rollback, 100 % undo, 5/5 TNP, ≥90 % FullyConstrained, ablation deltas reported); gap ≤15pp; `spot_audit` token bound

---

## Epic 4: Spec-to-Part Designer (Phase 3 · gate G3)

A user hands over a written part spec and receives an editable parametric part that measurably meets it — geometry assertions ∧ independent visual judge (iso + focus + dimensioned TechDraw per-axis projections), self-repaired without babysitting.

### Story 4.1: Entry Gate G3.E — Specs, Assertions, Judge & TechDraw Spike

> **As** a project owner, **I want** 20 real-world specs compiled to assertions, the corrupted-plan suite, the visual judge fault-tested, and the headless TechDraw export spike resolved — before designer code, **so that** Phase 3's "done" is defined before anything tries to reach it (AD-19/21).

**Acceptance Criteria:**

1. **Given** `benchmarks/g3/`  
   **When** inspected  
   **Then** 20 specs (AD-16 provenance, real-world basis) with compiled assertion sets + declared anchor frames, dev/held-out sealed, 10 corrupted-plan cases; assertion-layer sensitivity ≥95 %/≤5 % on planted-wrong parts

2. **Given** the visual judge config (vision model ≠ actor)  
   **When** its fault suite runs (mirrored, missing flange, wrong-face feature, wrong proportions, wrong-dimension-callout drawings + controls)  
   **Then** judge sensitivity ≥95 % / FA ≤5 %; headless TechDraw page-export spike answer recorded

### Story 4.2: Assertion Primitives

> **As** a bridge developer, **I want** the full AD-13 vocabulary implemented (holes, spacing, bbox, angles, anchor frames, disambiguation), **so that** any spec compiles to deterministic artifact-level checks.

**Acceptance Criteria:**

1. **Given** the primitive set per verification-design §7  
   **When** run against golden + planted-wrong parts  
   **Then** hole-vs-boss, coaxial grouping, fillet filtering, countersink recognition behave per the normative rules; measurements evaluate in the declared anchor frame; feature metadata is hint-only

### Story 4.3: TechDraw Drawing Generator

> **As** a visual judge, **I want** dimensioned front/top/right TechDraw projections auto-generated from driving parameters on a TempDoc, **so that** per-axis dimensioned drawings exist for every part-done check without polluting the part document.

**Acceptance Criteria:**

1. **Given** a finished candidate part  
   **When** `techdraw_for_judge` runs  
   **Then** a TempDoc gains page + three projections + parameter-sourced dimensions, exports ≥2048 px images, and is discarded; part document fingerprint unchanged

### Story 4.4: Visual Judge (`verify_visual`)

> **As** a project owner, **I want** the independent judge verdict over the standard visual set, **so that** done = geometry ∧ visual (AD-21, FR13).

**Acceptance Criteria:**

1. **Given** iso render + focus views + dimensioned TechDraw projections + spec checklist  
   **When** `verify_visual` runs (judge ≠ actor, temperature 0)  
   **Then** a structured `{pass, findings}` verdict lands in the ValidationReport as check `visual.judge`; callout-vs-spec mismatches block done and are re-checked against `verify_*` measurements; render/drawing/judge unavailable → not done (waiver audit-logged only)

### Story 4.5: Designer Loop

> **As** a user, **I want** to hand over a spec, approve the plan once, and receive a passing part within ≤3 self-repairs, **so that** design happens without step-by-step babysitting (FR12, G3.1).

**Acceptance Criteria:**

1. **Given** a spec from the dev set  
   **When** the loop runs (plan → Phase 2 tools → measure → repair)  
   **Then** convergence is declared only by geometry-∧-visual pass; repair input = discrepancy vector + judge findings; corrupted-plan cases detected ≥9/10 (G3.4); median wall-clock ≤10 min (G3.5)

### Story 4.6: Parametric Editability

> **As** a user, **I want** driving dimensions exposed as named parameters that survive edits, **so that** the generated part is a real parametric model, not a frozen blob (FR14, G3.2/G3.3).

**Acceptance Criteria:**

1. **Given** any passing part  
   **When** inspected  
   **Then** driving dimensions live in the VarSet/Spreadsheet façade with intent-bearing names, all sketches `FullyConstrained`  
   **And** changing one driving parameter recomputes clean in ≥90 % of passing parts

### Story 4.7: Gate G3 Exit

> **As** a project owner, **I want** the sealed 20-spec run green with audits, **so that** the designer capability is proven, not claimed.

**Acceptance Criteria:**

1. **Given** `gate run g3 --exit` (R≥10, held-out unsealed once)  
   **When** complete  
   **Then** G3.1–G3.7 pass (≥70 % within ≤3 repairs, artifact hygiene 100 %, editability ≥90 %, faults ≥9/10, ≤10 min median, GS convergence, visual leg 100 %); gap ≤15pp; `spot_audit` token bound

---

## Epic 5: Autonomous Design Service (Phase 4 · gate G4)

Any agent or human submits specs to a headless job API and gets validated models, exports, reports, and revisions — no GUI, no human in the loop, sandboxed. *(Detail expanded at the Phase 4 gate per spine Deferred; stories below are the committed skeleton.)*

### Story 5.1: Entry Gate G4.E — Soak & Fault Harness

**Acceptance Criteria:**

- Soak/fault harness lands first and fails honestly vs a stub service
- The four canonical faults (infinite loop → `TIMEOUT` + tree-kill, unbounded alloc → `OOM_KILLED` by sandbox, OCCT segfault → `WORKER_CRASHED` + refill, wrong-part-with-clean-report → supervisor re-check `SPEC_FAILED`) all caught ≥95 %
- Revision-diff checker fault-tested.

### Story 5.2: Supervisor & Worker Pool

**Acceptance Criteria:**

- Supervisor never imports FreeCAD
- Spawn pool `maxtasksperchild=1` with warm refill and bounded queue
- Whole-tree kill on deadline/cap
- Every abnormal exit maps to the closed status set
- `debug_exec` permanently off (`service_mode`).

### Story 5.3: Per-Job Sandbox

**Acceptance Criteria:**

- `run_job_in_sandbox` with Linux (nsjail/bwrap + cgroups + seccomp) and Windows (WSL2-preferred / AppContainer+Job Object) backends
- Egress deny-by-default
- GPU-none
- `jobs/<id>/` sole writable mount
- Concrete profiles per Phase 4 gate decisions.

### Story 5.4: Job API & Revisions

**Acceptance Criteria:**

- Submit → `JobStatus` lifecycle → deliverables (model, STEP/STL/3MF re-import-clean, rendered views, supervisor-re-executed ValidationReport incl. visual verdict — G4.3)
- 15-revision benchmark ≥70 % with geometry diff confined to the requested change (G4.2)
- Phase 3 rate maintained headless (G4.1).

### Story 5.5: Agent-to-Agent Proof & Gate G4 Exit

**Acceptance Criteria:**

- External MCP-client agent completes submit → inspect → revise → accept with zero human input (G4.4)
- 50-job soak: no crash/hang, memory growth <20 %, no silent failures (G4.5)
- `spot_audit` token bound
- Gate verdict green.

---

## Epic 6: CAD Skills Library & Ablation (parallel track · gate GS)

Any LLM harness gains measurable CAD judgment from 12 curated skills — each proven by ablation to move a benchmark number or cut. Runs alongside Epics 2–4 after Epic 1.

### Story 6.1: Entry Gate GS.E — Ablation Harness & Shape Check

**Acceptance Criteria:**

- Forced explicit-subset injection mode (`--skills a,b|none|all`) with auto-activation disabled and complement-absence asserted via transcript check
- Clean A/B demonstrated on the dummy skill
- `check_skill_shape.py` (4 sections, ≤1,500 words, description rules, no cross-skill deps) blocking in CI.

### Story 6.2: First Track A Skills — Fundamentals & Troubleshooting

**Acceptance Criteria:**

- `freecad-fundamentals` + `freecad-troubleshooting` authored per the SKILL.md template (shape-check green), loadable via native activation AND forced injection
- Consumed by Epic 2's eval runs (G1.5)
- Troubleshooting re-run on G1.2 cases targets ≥9/10 (GS.4, CI attached).

### Story 6.3: Remaining Track A Skills

**Acceptance Criteria:**

- `freecad-sketcher`, `freecad-partdesign`, `freecad-datums-references`, `freecad-scripting-idioms` authored + shape-checked + dual-path loadable
- Drafted against the pinned FreeCAD versions
- Long tails in `references/`.

### Story 6.4: Track B Skills

**Acceptance Criteria:**

- `design-decomposition`, `sketch-strategy`, `tool-selection`, `design-intent`, `parametric-patterns`, `verification-thinking` authored + shape-checked + dual-path loadable
- `verification-thinking` encodes the dual-channel done protocol (geometry ∧ visual) and discrepancy-vector reading.

### Story 6.5: Production Router

**Acceptance Criteria:**

- Metadata-first router live (12 descriptions resident, 2–5 bodies routed, ≤10K budget, routed subset logged)
- Starter routing table shipped as replaceable seed
- Native Claude activation + local-backend injection both served from the single store.

### Story 6.6: Ablation Campaign & Gate GS Exit

**Acceptance Criteria:**

- Per-skill paired ablations on Phase 2/3 benchmarks in AD-14 format
- ≥8/12 significant (McNemar p<0.05 ∧ CI excludes 0), rest revised/cut with below-detection reported honestly (GS.3)
- `design-decomposition` ≥+15pp on its dedicated n≥40 set at R≥10 (GS.6)
- `skills_accuracy` tokens ×12 + `spot_audit` bound
- Gate verdict green.
