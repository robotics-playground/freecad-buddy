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

- **FR7** — An assistant answers document questions (tree explanation, error diagnosis, next-tool guidance) through read-only tools, driven from ≥2 external agent harnesses including one on a local model, all over MCP.

#### Copilot — CAP-3

- **FR8** — A copilot executes one natural-language mutation at a time through typed `sketch_`/`feature_`/`document_` tools; every mutation runs the uniform transaction protocol: fingerprint snapshot → transaction → recompute → post-verify → commit, or hash-proven rollback with saveCopy fallback. *(AD-4/5)*
- **FR9** — Before any Phase 2 mutation, a dry-run on a TempDoc copy returns a structured geometry diff (+ optional before/after renders with view control); execution is confirmation-gated: MCP elicitation, `preview_id` token fallback, or fail-closed headless with audit-logged `autoApprove`. *(AD-10)*
- **FR10** — Bridge-owned undo restores exact prior state, verified by fingerprint comparison in 100 % of cases. *(AD-6)*
- **FR11** — A TNP guard snapshots all reference-holding subsystems before each mutation and audits after recompute — flags broken (`?`-marker), silently re-pointed, and dropped references; reports `UNSUPPORTED` (never clean) without an element map. *(AD-7)*

#### Spec-to-part — CAP-4

- **FR12** — An agent turns a written part spec into a parametric part: plan (human-approved once) → execute the Phase 2 tools → measure against compiled spec assertions in a declared anchor frame → repair, within the cap the `design-loop` skill sets. Convergence is the measurements agreeing, never an iteration count. This repository ships the assertion primitives and the skill; it ships no loop. *(AD-13/21/35)*
- **FR13** — The bridge produces the standard visual set — 3D iso render, focus views, and dimensioned front/top/right projections generated from the part's driving parameters on a TempDoc copy at a ≥2048 px legibility floor — and the `visual-review` skill's checklist. The driving agent performs the review and writes its findings to the run workdir; no judge model, credential, or verdict-producing code exists in the source tree. *(AD-21/35)*
- **FR14** — Generated parts expose driving dimensions as named parameters (VarSet with Spreadsheet fallback façade); editing one parameter recomputes clean. *(AD-11)*

#### Unattended operation — CAP-5

- **FR15** — An operator starts an agent against the headless bridge and leaves. Every reported validation field is a re-executed check rather than an echoed claim, every mutation lands in the append-only audit log, and a failed run is reconstructable from its `run_id` workdir alone. Revisions are graded against a declared scope, and a diff that cannot be read fails closed. *(AD-17/25/35)*

#### Skills library — CAP-6

- **FR16** — A skills library of 15 skills — 12 Track A+B plus the three Track W workflow skills (`design-loop`, `visual-review`, `spec-to-assertions`) that carry the design loop the code does not — each with 4 mandatory sections, ≤1,500 words, loading via two modes: production metadata-first router (2–5 bodies, ≤10K tokens) and ablation forced explicit-subset injection with auto-activation disabled. *(AD-15)*

#### Validation harness — CAP-7

- **FR17** — A gate runner executes phase-gate criteria (G0–G2, GS) against benchmarks, emits contracts-owned ValidationReports, and computes gate verdicts mechanically: pass rules on report fields + validator sensitivity currency + sealed held-out R≥10 + human sign-off tokens. *(AD-19)*
- **FR18** — A fault-injection framework validates every validator (planted defects + clean controls) and tracks per-validator sensitivity/false-alarm with source-hash staleness. *(AD-13)*

#### Cross-cutting

- **FR19** — `debug_exec` exists as operator-only capability: env-flag gated, unregistered when off, permanently off in service mode, every call audit-logged. *(AD-4)*
- **FR20** — An append-only audit log records every mutation, exec, preview, approval, and rollback from Phase 0 using the contracts-owned record type. *(AD-17)*

#### Robot-description & sourcing — CAP-8 *(Phase 5)*

- **FR21** — A parametric assembly exports to URDF — links, joints, limits, inertials (from native mass properties), and collision/visual meshes — completing only through a paired re-parse + schema + kinematic-tree-sanity verify; the mm/deg→m/kg/rad conversion is explicit and every origin records its frame. *(AD-22)*
- **FR22** — The same assembly exports to SDF (model-level) through its own paired verify, sharing the tessellation source with URDF. *(AD-22)*
- **FR23** — Off-the-shelf STEP parts are sourced (external search) and imported/placed only through the bridge's document/import path, with mating frames measured from geometry, never assumed, and provenance recorded for shipped fixtures. *(AD-23)*

#### Viewport framing — CAP-9

- **FR24** — The bridge can read whether the targeted document's model is fully visible in the live FreeCAD viewport, by projecting the 8 corners of the union bounding box of the visible shape-bearing objects and testing containment against the viewport rectangle. The read lives behind a `ViewportPort` injected from a GUI host; where no viewport exists the capability reports unavailable rather than guessing. *(AD-29, AD-30)*
- **FR25** — An agent can call `view_fit_viewport` to fit the targeted document's model into the live viewport on its own judgement — no preview token — and every call is audit-logged with the prior camera so the move is traceable and reversible. The human owns the camera: the bridge never fits spontaneously. *(AD-31, AD-33)*
- **FR26** — When the model does not fully fit, a tool result carries a structured `framing` verdict whose warning sentence guides the agent to run the fit tool. The verdict is computed on change rather than per call, is rendered from the structured block by one shared helper rather than appended per tool, and never claims a freshness the bridge cannot prove. *(AD-32)*

#### Viewport & render correctness — CAP-9 (defect requirements, Epic 9)

Derived from UAT run `2026-09-13-02` (`tests/uat/run/2026-09-13-02/bugs.md`) and the 2026-09-13 spine
amendment. These correct **shipped** behaviour: FR24–FR26 (Epic 8) and FR3 (story 1-9) are implemented
and their stories are `done`, so each DR names the defect rather than a new capability. Every DR was
reproduced live against FreeCAD 1.1.1 before it was written.

- **DR-1** — `view_fit_viewport` frames the model using the **same 8-corner projection that produces the framing verdict**, not a second analytic estimate, and it may not report `fitted: true` when its own post-fit projection returns `fits: false`. The fit is three passes inside one animation-suspended block (measure → `fitAll(factor)` on AD-32's binding axis → re-project to verify); a fit that cannot suspend animation cannot verify itself and fails honestly. *(AD-30, AD-31; defect R2-01 — a 40 mm cube measured `ratio 1.0978` with `fitted: true`, bottom vertex clipped, two consecutive fits never converging)*
- **DR-2** — The wrong-document guard actually fires: `view_fit_viewport` refuses a handle that does not name the document the live viewport is showing, comparing against `ViewportPort.showing_document_name()` rather than a view resolved from the target's own name. `FreeCADGui.ActiveDocument` stays banned in every ring. *(AD-29, AD-31; defect R2-02 — with `r2other` on screen a fit targeting `r2repro` returned `fitted: true` and rescaled the on-screen document's view from `8.68 × 4.14 mm` to `79.39 × 59.55 mm`)*
- **DR-3** — The fit's post-fit `SPEC_FAILED` **carries its `framing` block** — the single carve-out in AD-32's omission rule — so the failure names the measured ratio it is about. Without it the new failure envelope is strictly less informative than the defect it replaces. *(AD-31, AD-32; not independently shippable — lands with DR-1)*
- **DR-4** — Every named camera renders a face tone separable from the background, verified by a **two-sided** band: mean interior tone differs from background by ≥ 24/255 on at least one channel and lies within `[20, 235]` on every channel, over ≥ 500 interior samples. *(AD-34; defect R2-03 — `iso` fills `rgb(159,164,169)`, while `front`/`top`/`right`/`back` render the face at `rgb(255,255,255)`, identical to the background)*
- **DR-5** — Every temp file the bridge writes is created **inside** the session workdir, so the AD-25 sweep can see it; the reserved `FCB_TMP_` prefix marks files only and never the in-memory probe documents that share it. *(AD-25; defect R2-04 — 392 leaked `FCB_TMP_shot_*` files across exited sessions, plus 10 empty `FCB_TMP_snap_*` directories from a swallowed `rmdir` failure)*

**Closed as invalid — no story:** R2-05 (`export_*` "creates missing parent directories") is not a
defect. `usecases/exports.py:151` calls `shape.exportStep(path)` and no `makedirs` exists anywhere in
the module; the reported directory pre-existed the run. Retested at one missing level on two drives —
both returned `RECOMPUTE_ERROR` and created nothing. The residual nit (a missing parent should be
`INVALID_INPUT` per AD-17, not `RECOMPUTE_ERROR` with `unexpected: true` and a raw traceback) is
deferred-work, not a fix story.

### NonFunctional Requirements

| ID | Requirement | Source |
| --- | --- | --- |
| **NFR1** | The producing agent never grades itself in a cited number — pass/fail comes from deterministic code or an independent grader only | AD-13 |
| **NFR2** | Every validator proves sensitivity ≥95 % / false-alarm ≤5 % on its fault suite before its scores are citable; suites land before phase implementation | AD-13, AD-19 |
| **NFR3** | Statistics discipline: majority-of-R scoring (R=5 dev / R≥10 exit), Wilson 95 % CI beside every rate, exact McNemar for ablations, pp-threshold claims on n≥40 sets, dev/held-out gap >15pp blocks exit | AD-14 |
| **NFR4** | All suites run headless in CI on the blocking FreeCAD 1.1.x leg (Py 3.11) + 1.2-dev canary; version-sensitive calls live in one shim behind capability probes | AD-11 |
| **NFR5** | In-FreeCAD code imports stdlib + FreeCAD API only; all third-party deps live in the uv-managed external process | AD-12 |
| **NFR6** | Clean Architecture dependency rule enforced by CI import checks; Qt only in `hosts/` + the two named adapter exemptions | AD-1 |
| **NFR7** | Security posture: localhost-only binds, per-session RPC token, stderr-only logging on stdio, no free-form exec in any AI path | AD-3, AD-4 |
| **NFR8** | Benchmark artifacts only from commercial-clean, per-item license-checked sources with documented real-world provenance — never reverse-fit to agent ability | AD-16 |
| **NFR9** | Performance: Phase 1 median response ≤15 s | phase gates |
| **NFR10** | All wire schemas (ResultEnvelope, ValidationReport, AuditRecord, GeometryDiff, RPC frames) are contracts-owned, stdlib-only, additive-only within a major | AD-17 |
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
| FR12–FR14 | Epic 4 | Assertion primitives, render/drawing path, parametric parameters — the agent's loop lives in `design-loop` |
| FR15 | Epic 5 | Audit, retention, re-executed reports, scope-graded revisions |
| FR16 | Epic 6 | 15-skill library (Track A+B+W) + two-mode loader + ablation (+ 3 Phase-5 skills, stories 6.8–6.10) |
| FR21–FR23 | Epic 7 | URDF/SDF export with paired verify; off-the-shelf part sourcing/import *(Phase 5)* |
| FR24–FR26 | Epic 8 | Viewport framing read, agent-invoked fit tool, change-driven framing warning |
| DR-1, DR-3 | Epic 9 (story 9.1) | Shared 8-corner projection; `fitted: true` requires the post-fit verdict to agree; that failure carries its `framing` block |
| DR-2 | Epic 9 (story 9.2) | `showing_document_name()` makes the wrong-document refusal actually fire |
| DR-4 | Epic 9 (story 9.3) | Two-sided tone band so every named camera renders a face separable from the background |
| DR-5 | Epic 9 (story 9.4) | Temp files created inside the session workdir so the AD-25 sweep can see them |

All FRs mapped; none orphaned. NFR1–NFR13 bind cross-epic and are enforced per story via gate criteria and CI checks. FR21–FR23 are post-MVP (Phase 5) and additive. FR24–FR26 are additive and parallel-eligible after Epic 1 — they add a new tool and an optional envelope field, and weaken no existing AD.

All 5 DRs mapped; none orphaned. R2-05 from the same UAT run is deliberately absent — closed invalid, no story. The DRs correct **shipped** behaviour (Epic 8 and story 1-9 are `done`), so they open no gate and reopen no closed epic.

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

### Epic 4: Spec-to-Part (Phase 3 · gate G3)

A user hands over a written part spec and an agent returns an editable parametric part that measurably meets it — geometry assertions plus a visual review, repaired without babysitting. This repository supplies what the agent measures and looks at; the loop is the agent's.

**FRs covered:** FR12, FR13, FR14

### Epic 5: Unattended Operation (Phase 4 · gate G4)

An operator starts an agent and walks away, and comes back to a part, exports, a validation report whose every field was re-executed, and a run workdir that reconstructs what happened. No service, no job API, no worker pool.

**FRs covered:** FR15

### Epic 6: CAD Skills Library & Ablation (parallel track · gate GS)

Any LLM harness gains measurable CAD judgment from curated skills — each proven by ablation to move a benchmark number or cut. Runs alongside Epics 2–3; needs Epic 1's harness.

**FRs covered:** FR16 (+ FR21–FR23 skill support in stories 6.8–6.10, Phase 5)

### Epic 7: Robot-Description Export & Part Sourcing (Phase 5 · gate G5-robot)

A parametric assembly exports to validated URDF and SDF, and off-the-shelf STEP parts are sourced and placed under the bridge. Post-MVP; sits on a Phase-5 Assemblies capability.

**FRs covered:** FR21, FR22, FR23

### Epic 8: Viewport Framing & Auto-Fit

An agent working in a live FreeCAD session can tell when its work has grown beyond what the human can see, is told so in the tool result it already reads, and can fit the view itself — without ever taking the camera away from the human unasked.

**FRs covered:** FR24, FR25, FR26

### Epic 9: Viewport & Render Correctness

When the bridge says the human can see the model, the human can actually see it — and when it cannot, the agent is handed a measured number it can act on rather than a success it must not trust. A render from any camera angle shows the part instead of a white rectangle, and the bridge stops leaving files behind.

**DRs covered:** DR-1, DR-2, DR-3, DR-4, DR-5

**Dependency chain:** 1 → 2 → 3 → 4 → 5 (gate-sequential per AD-19); 6 parallel after 1; 7 is Phase 5, after 5 and after a Phase-5 Assemblies capability. Skills stories 6.8–6.10 pair with Epic 7. **8 is parallel-eligible after Epic 1** — it adds a tool and an optional envelope field on top of the shipped bridge and weakens no existing AD, so it does not reopen the closed G0/G2 gates. **9 corrects shipped Epic 8 + story 1-9 behaviour**: it opens no gate, and Epic 8 stays `done` rather than being reopened (AD-19 keeps a passed gate closed). Within Epic 9, 9.1 → 9.2 are ordered because both edit `usecases/view_fit.py`; 9.3 and 9.4 touch disjoint files and are parallel-eligible with either.

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
   **Then** `arch-checks` (uv-only) and the `headless` leg {FreeCAD 1.1.*/Py 3.11} executes with a cached micromamba env, blocking (NFR4)  
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
   **Then** verdict follows AD-8 exactly: PASS ⇔ `solve()` returns 0, `FullyConstrained` and DoF 0; hard-fail on conflicting/malformed/fully redundant/over/under/degenerate; partially redundant = WARN only; DoF never inferred from `solve()`

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
   **When** `python benchmarks/runner.py --gate G0` runs on the blocking 1.1.x leg  
   **Then** G0.1–G0.5 all PASS on report fields: both transports list+call (G0.1), ≥15 tools in gate namespaces all schema'd (G0.2 — catalog delivers 17), golden models ±0.1 % (G0.3), ≥30 tests green on the 1.1.x leg (G0.4), STEP round-trip (G0.5)

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

> **As** a project owner, **I want** the 50-question eval, a 30-case broken-document fixture set (gate grades n=10 first, escalates to n=30 on 10/10), human-authored rubric, and a fault-tested independent grader before assistant code exists, **so that** answer quality is decided by a validated grader, never the assistant (AD-19, NFR1).

**Acceptance Criteria:**

1. **Given** `benchmarks/g1/`  
   **When** inspected  
   **Then** 50 questions + expected findings, a 30-case broken-recompute fixture set with *the* failing object/cause named (gate grades n=10 first, escalates to n=30 only on 10/10 — see phase-gates G1.2), `rubric.md` with worked pass/fail examples, and dev/held-out split sealed per AR7 exist — all provenance-manifested

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
   **Then** the assistant names the failing object and cause via `verify_recompute` + `getStatusString` diagnostics (G1.2 target: n=10 ≥8/10, escalate to n=30 on 10/10)

### Story 2.3: Local Backend Over Native MCP

> **As** a project owner, **I want** the same assistant running on a local model through native MCP, **so that** the bridge is proven model-agnostic rather than tuned to one vendor.

**Acceptance Criteria:**

1. **Given** the pinned local stack (llama.cpp + Qwen3-30B-A3B per Phase 1 pin, constrained decoding ON)
   **When** the G1.1 sample re-runs
   **Then** it completes through the identical tool surface over HTTP

2. **Given** a second external agent harness (one non-Claude)
   **When** it drives the same read-only surface over MCP
   **Then** the confirmation posture matches the no-elicitation path and no tool schema, envelope field, or confirmation path depends on one client's capabilities

3. **Given** AD-35
   **When** model agnosticism is evidenced
   **Then** it is evidenced by driving the bridge from external harnesses — this repository ships no chat loop, no model client, and no model-vendor dependency

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
   **When** it completes on the 1.1.x leg  
   **Then** G2.1–G2.6 pass (≥85 % commands, 100 % post-verify+rollback, 100 % undo, 5/5 TNP, ≥90 % FullyConstrained, ablation deltas reported); gap ≤15pp; `spot_audit` token bound

---


## Epic 4: Spec-to-Part (Phase 3 · gate G3)

A user hands over a written part spec and an agent returns an editable parametric part that measurably meets it. This repository supplies the assertion primitives the agent measures with, the render and drawing path it looks at, and the `design-loop` / `visual-review` / `spec-to-assertions` skills that tell it how. It supplies no loop: no plan-execute-repair function exists in the source tree (AD-35).

### Story 4.1: Entry Gate G3.E — Spec Set, Assertions & Fault Suite

**Acceptance Criteria:**

1. **Given** the written spec set with its compiled assertions, authored from the spec prose before any part exists
   **When** the gate runs against a stub
   **Then** every criterion fails honestly with `INVALID_INPUT`, never a vacuous pass

2. **Given** the corrupted-plan fault suite (≥10 planted recorded plans plus clean controls, every G3 threat countered by a planted case)
   **When** the structural check runs
   **Then** it passes, and it fails naming the case or threat when any of those properties is broken

3. **Given** the G3 entry gate
   **When** its entry items are read
   **Then** a recorded reuse survey exists, naming what was reused from earlier work, what was rejected, and why

### Story 4.2: Assertion Primitives

**Acceptance Criteria:**

- The spec assertion vocabulary measures geometry — surface typing, axis/radius/spacing, bbox/volume — in the declared anchor frame, through one shared resolver.
- Feature metadata is a diagnostic hint only; sub-element index selectors are refused in a spec.
- An assertion that cannot be evaluated reports a failing `INVALID_INPUT` check, never a silent skip.
- **Given** each spec's declared anchor frame (named datum | base sketch plane | largest planar face with its tie-break)
  **When** the frame of each built part resolves on FreeCAD 1.1.x
  **Then** it equals the committed 1.1.x reference frame, or the spec is broken rather than the part failing
- **Given** the corrupted-plan fault suite (≥10 planted spec violations plus clean controls)
  **When** scored
  **Then** sensitivity ≥95 % and false-alarm ≤5 %, recorded with the validator hash

### Story 4.3: Drawing Generator

**Acceptance Criteria:**

- Dimensioned front/top/right projections compose onto one sheet from the part's driving parameters, on a reserved-prefix TempDoc copy that leaves the part document byte-identical.
- The sheet renders at ≥2048 px page width; below that floor the visual set is incomplete and the part is not done.
- One sheet-wide scale, stated on the sheet as a ratio, so proportions are comparable between views.

### Story 4.4: Parametric Editability

**Acceptance Criteria:**

- Driving dimensions are exposed as named parameters through the VarSet façade with its Spreadsheet fallback.
- Changing one parameter recomputes clean and the change is reflected in the geometry, verified by re-running the spec's assertions.

### Story 4.5: Gate G3 Exit

**Acceptance Criteria:**

1. **Given** all G3 criteria and an external agent harness as the actor
   **When** the exit runs against the sealed held-out split at R≥10
   **Then** G3.1–G3.6 pass their rules with Wilson CIs reported, the dev/held-out gap is ≤15pp, the `spot_audit` token is present and run-bound, and the report banner names the actor's exact model id

---

## Epic 5: Unattended Operation (Phase 4 · gate G4)

An operator starts an agent against the headless bridge and leaves. Nothing here schedules, supervises or parallelizes that run — the agent holds the loop and spawns subagents if the work fans out. What this epic owes is everything that makes such a run safe and auditable with nobody watching.

### Story 5.1: Entry Gate G4.E — Revision Fault Suite

**Acceptance Criteria:**

1. **Given** the revision fault suite (a change that moves what was asked *and* silently breaks an unrelated feature, plus clean controls)
   **When** scored
   **Then** sensitivity ≥95 % and false-alarm ≤5 %, recorded with the validator hash

2. **Given** the gate runs against a stub
   **When** executed
   **Then** every criterion fails honestly rather than passing vacuously

### Story 5.2: Re-Executed Validation Reports

**Acceptance Criteria:**

- Every field of a delivered validation report is produced by re-running its check against the artifacts on disk; an agent's account of its own work is never echoed as a result (AD-17).
- A check that cannot be re-run reports as not-run rather than as passing.

### Story 5.3: Scope-Graded Revisions

**Acceptance Criteria:**

- A revision carries a declared scope and is graded against it: the check fails when the geometry diff touches, adds or deletes anything the request did not name.
- A diff that cannot be read fails closed — an unproven revision, never a passing one.

### Story 5.4: Run Traceability

**Acceptance Criteria:**

- Every run carries a `run_id` threaded through every `ResultEnvelope`, `AuditRecord` and `ValidationReport` it produces.
- The plan, per-iteration discrepancy vectors, visual-review findings with their images, and repair decisions are written to the session workdir as the run proceeds, so a run that dies mid-iteration still leaves everything up to that point.
- A failed run is reconstructable from its workdir alone, without the agent's context.

### Story 5.5: Gate G4 Exit

**Acceptance Criteria:**

1. **Given** all G4 criteria
   **When** the exit runs with no human input after kickoff
   **Then** G4.1–G4.5 pass their rules, the full build → inspect → revise → accept cycle completes, and every failure carries a structured AD-17 status

---

## Epic 6: CAD Skills Library & Ablation (parallel track · gate GS)

Any LLM harness gains measurable CAD judgment and workflow from curated skills — each Track A+B skill proven by ablation to move a benchmark number or cut, and Track W carrying the design loop itself. Runs alongside Epics 2–4 after Epic 1.

### Story 6.1: Entry Gate GS.E — Ablation Harness & Shape Check

**Acceptance Criteria:**

- Forced explicit-subset injection mode (`--skills a,b|none|all`) with auto-activation disabled and complement-absence asserted via transcript check
- Clean A/B demonstrated on the dummy skill
- `check_skill_shape.py` (4 sections, ≤1,500 words, description rules, no cross-skill deps) blocking in CI.

### Story 6.2: First Track A Skills — Fundamentals & Troubleshooting

**Acceptance Criteria:**

- `freecad-fundamentals` + `freecad-troubleshooting` authored per the SKILL.md template (shape-check green), loadable via native activation AND forced injection
- Consumed by Epic 2's eval runs (G1.5)
- Troubleshooting re-run on G1.2 tiered cases targets n=10 ≥9/10, escalating to n=30 on 10/10 (GS.4, CI attached).

### Story 6.3: Remaining Track A Skills

**Acceptance Criteria:**

- `freecad-sketcher`, `freecad-partdesign`, `freecad-datums-references`, `freecad-scripting-idioms` authored + shape-checked + dual-path loadable
- Drafted against the pinned FreeCAD versions
- Long tails in `references/`.

### Story 6.4: Track B Skills

**Acceptance Criteria:**

- `design-decomposition`, `sketch-strategy`, `tool-selection`, `design-intent`, `parametric-patterns`, `verification-thinking` authored + shape-checked + dual-path loadable
- `verification-thinking` encodes the dual-channel done protocol (geometry ∧ visual) and discrepancy-vector reading.

### Story 6.5: Track W Workflow Skills

**Acceptance Criteria:**

- `design-loop`, `visual-review`, `spec-to-assertions` authored + shape-checked + dual-path loadable.
- `design-loop` encodes the plan → execute → measure → repair cycle: one plan approval, what to verify after each step, how to read a discrepancy, the repair cap, and what "done" means (assertions pass **and** the part looks right).
- `visual-review` encodes the per-part checklist: which views to request, what a mirrored or wrong-face part looks like, what is a shading artefact rather than a defect, and the requirement to write findings into the run workdir.
- `spec-to-assertions` encodes authoring machine-checkable assertions **before** building, so the measurement exists before the part does.
- A skill may carry read-only helper scripts under `scripts/` (AD-15): reads and computes, never mutates; no model call, no credential; answers one question per invocation and never decides the next action.
- Track W is exempt from the AD-14 ablation cut — without `design-loop` no loop exists to measure, so it is validated by the spec benchmark running at all.

### Story 6.6: Production Router

**Acceptance Criteria:**

- Metadata-first router live (15 descriptions resident, 2–5 bodies routed, ≤10K budget, routed subset logged)
- Starter routing table shipped as replaceable seed
- Native Claude activation + local-backend injection both served from the single store.

### Story 6.7: Ablation Campaign & Gate GS Exit

**Acceptance Criteria:**

- Per-skill paired ablations on Phase 2/3 benchmarks in AD-14 format
- ≥8/12 significant (McNemar p<0.05 ∧ CI excludes 0), rest revised/cut with below-detection reported honestly (GS.3)
- `design-decomposition` ≥+15pp on its dedicated n≥40 set at R≥10 (GS.6)
- `skills_accuracy` tokens ×15 + `spot_audit` bound
- Gate verdict green.

### Story 6.8: URDF-Export Skill *(Phase 5 · with Epic 7)*

**Acceptance Criteria:**

- `urdf-export` skill authored per the SKILL.md template (shape-check green), teaching how to drive an assembly → URDF through the bridge's Phase-5 export tools (`export_urdf`/`verify_export_urdf`), frame-semantics discipline, unit conversion, and the verify-first done rule (AD-22)
- Ablated once GS infra + Epic-7 tools exist.

### Story 6.9: SDF-Export Skill *(Phase 5 · with Epic 7)*

**Acceptance Criteria:**

- `sdf-export` skill authored (shape-check green), teaching assembly → SDF export, model-vs-world scope, and the paired verify (AD-22)
- Ablated once GS infra + Epic-7 tools exist.

### Story 6.10: Part-Sourcing Skill *(Phase 5 · with Epic 7)*

**Acceptance Criteria:**

- `part-sourcing` skill authored (shape-check green), teaching off-the-shelf STEP part search → import → placement under the bridge, measured (not assumed) mating frames, and provenance (AD-23)
- Ablated once GS infra + Epic-7 tools exist.

---

## Epic 7: Robot-Description Export & Part Sourcing (Phase 5 · gate G5-robot)

A parametric assembly exports to validated URDF and SDF — links, joints, inertials, and meshes — and off-the-shelf STEP parts are sourced, imported, and placed under the bridge. Post-MVP; sits on top of a Phase-5 Assemblies capability. *(Committed skeleton — expand at the G5-robot entry gate before create-story, per AD-19.)*

**FRs covered:** FR21, FR22, FR23

> **Prerequisite:** a Phase-5 **Assemblies** capability (native Assembly workbench Python-exposure; the `JointObject` gap in intent.md). URDF/SDF export consumes the kinematic link/joint tree that capability produces — Epic 7 cannot complete before it. Recommend scoping Assemblies as the first Phase-5 epic and Epic 7 after it.

### Story 7.1: Entry Gate G5-robot.E — Fixtures, Verify Legs & Build-Path Spikes

**Acceptance Criteria:**

- Golden robot-description fixtures (a simple 2–3 link arm) with known link/joint/inertial expected values, provenance-manifested (AD-16)
- Fault suite: planted wrong-axis, cyclic tree, negative inertia, missing mesh, wrong-unit cases; verify-leg sensitivity ≥95 % / FA ≤5 %
- Spikes resolved and recorded: CROSS-addon-vs-hand-rolled-XML decision, Assembly-workbench Python-exposure of the joint tree, the URDF/SDF schema/parse library for the verify leg
- Benchmark runs against a stub and fails honestly.

### Story 7.2: URDF Export & Paired Verify

**Acceptance Criteria:**

- `export_urdf` emits URDF from the assembly tree + native inertials + mesh export (via CROSS or our XML per the spike); mm/deg → m/kg/rad conversion pinned and explicit
- `verify_export_urdf` re-parses the file: schema-valid, single-root acyclic kinematic tree, joint axes finite/normalized in joint frame, inertials positive/plausible, mesh refs resolve — export is done only when this passes (AD-22)
- Every link/joint/inertial origin records its reference frame.

### Story 7.3: SDF Export & Paired Verify

**Acceptance Criteria:**

- `export_sdf` emits model-level SDF from the same assembly source; `verify_export_sdf` mirrors the URDF verify leg
- Shared tessellation/mesh source with URDF so the two cannot silently diverge.

### Story 7.4: Part Sourcing, Import & Placement

**Acceptance Criteria:**

- Off-the-shelf STEP parts enter only through the `document_*`/import path (AD-20, AD-23); catalog search is external and swappable
- An imported part's mating frames are derived from measured geometry (`query_mass_properties`/`query_placement`), never assumed
- Any shipped fixture records provenance + license (AD-16).

### Story 7.5: Gate G5-robot Exit

**Acceptance Criteria:**

- A parametric assembly round-trips: export URDF/SDF → verify legs green on the golden fixtures → re-parse clean
- Fault suite caught ≥95 %; `spot_audit` token bound
- Gate verdict green from stored reports.

---

## Epic 8: Viewport Framing & Auto-Fit

An agent working in a live FreeCAD session can tell when its work has grown beyond what the human can see, is told so in the tool result it already reads, and can fit the view itself — without ever taking the camera away from the human unasked.

**Why now:** the bridge has never been able to see the human's viewport. `adapters/render_probe.py` builds its own Coin scene and always self-frames (`camera.viewAll`), so an MCP render is by construction never mis-framed — only the human's screen can be. An agent can therefore pad a solid past the edge of the viewport, read a perfectly framed render of its own, and never know the user is staring at the corner of a face.

**Sequencing:** parallel-eligible after Epic 1. Additive — one new tool plus one optional envelope field — so it does not reopen gates G0 or G2.

**Read AD-29 through AD-33 in full, not their summaries** — their carve-outs are load-bearing for these stories.

### Story 8.1: `ViewportPort` Contract & GUI-Host Implementation

> **As** a bridge developer, **I want** the live-camera read and write behind a second injected port implemented in a GUI host, **so that** `usecases/` stays Gui-free and AD-1's single adapters Qt exemption is not widened (AD-29, FR24).

**Acceptance Criteria:**

1. **Given** `contracts/render.py`
   **When** inspected
   **Then** a `ViewportPort` Protocol sits beside `RenderPort` with its own availability answer, and a `FramingVerdict` TypedDict is declared for the AD-32 block

2. **Given** the GUI addon
   **When** the bridge starts
   **Then** a `hosts/gui_addon/` implementation is injected; hosts with no viewport inject `None` and the usecase reports the capability unavailable

3. **Given** `scripts/check_imports.py`
   **When** CI runs
   **Then** `QT_EXEMPT_ADAPTERS` still holds exactly one entry (`adapters/render_probe.py`) and `OffscreenRenderPort` is untouched — adding framing code to it would force a second exemption and is a defect

4. **Given** a headless `FreeCADCmd` leg that can render offscreen
   **When** framing availability is asked
   **Then** it answers unavailable. `OffscreenRenderPort.available()` probes offscreen *render* capability via `setupWithoutGUI()`, which is orthogonal to "a live viewport exists"; reusing it as the framing predicate reports available in headless and then finds no `ActiveView`

### Story 8.2: Framing Read — Exact Projection Test

> **As** an agent, **I want** an exact, non-heuristic answer to "is the model fully visible", **so that** two implementations can never disagree about the same scene (AD-30, FR24).

**Acceptance Criteria:**

1. **Given** a document with a visible solid
   **When** the framing read runs
   **Then** it projects the 8 corners of the union bbox via `View3DInventor.getPointOnViewport` and tests containment against `getSize()`; `fits` is false iff any corner falls outside

2. **Given** the object set to measure
   **When** resolved
   **Then** it reuses `usecases/screenshot.py:51 _is_default_renderable` — the render and the warning must never describe different scenes, so a re-derived visibility filter is a defect

3. **Given** a corner projected far off-screen
   **When** its coordinate exceeds 4× the corresponding viewport dimension
   **Then** it is treated as **outside** and the coordinate discarded. `getPointOnViewport` returns `SbVec2s` through an unchecked `short()` cast (`View3DInventorViewer.cpp:3823-3824`) that wraps sign for a distant corner, so a wrapped value must never read as inside

4. **Given** a `ratio` is reported
   **When** computed
   **Then** it is the larger of the two `extent / viewport_extent` quotients over the 2D axis-aligned hull of the 8 projected corners, and is `None` (with `fits:false`) whenever any coordinate was discarded — a fabricated ratio would report a wildly wrong camera as a hair's-breadth miss

5. **Given** a HiDPI display
   **When** the test runs
   **Then** no `devicePixelRatio` correction is applied: `getSize()` and the projection share one render-manager pixel space, and the DPI divide exists only in `toQPoint`, which this path never calls

### Story 8.3: `view_fit_viewport` Tool

> **As** an agent, **I want** to fit the model into the viewport on my own judgement without a preview round trip, **so that** the human sees the result of work I just did (AD-31, AD-33, FR25).

**Acceptance Criteria:**

1. **Given** the tool spec
   **When** registered
   **Then** it is `mutating=True` with **no `confirm` property**, is built outside the `features.py`/`sketches.py` mutation wrappers, and is absent from `READ_ONLY_PROFILE`

2. **Given** a call
   **When** it executes
   **Then** no `preview_id` is demanded. The confirm gate is the explicit `confirm.gate_mutation` call at `usecases/features.py:369`/`sketches.py:561`, which this tool never reaches; routing it through `run_mutation` to get an audit record would wrongly trigger that gate

3. **Given** a successful fit
   **When** the audit record is written
   **Then** a new optional `AuditRecord.camera_before` carries the verbatim `getCamera()` string, `audit-record.schema.json` is regenerated in the same change, and the camera is never folded into `params_digest` (irreversible, defeating the point) nor `fingerprint_before` (a geometry digest under AD-6)

4. **Given** a `doc` handle that is not the document the live viewport is showing
   **When** called
   **Then** it returns `INVALID_INPUT` naming both documents — it must not fit the active document instead, and must not activate the named one

5. **Given** the implementation resolves the view
   **When** reviewed
   **Then** it uses `FreeCADGui.getDocument(<resolved Name>).ActiveView`, never `FreeCADGui.ActiveDocument`

6. **Given** a quarantined document (AD-27)
   **When** a fit is attempted
   **Then** it is refused, so quarantine keeps one meaning across the whole tool surface

### Story 8.4: Framing Warning on Tool Results

> **As** an agent, **I want** the warning to reach me in the tool result I already read, **so that** I learn the model is off-screen without polling for it (AD-32, FR26).

**Acceptance Criteria:**

1. **Given** a `framing` verdict
   **When** attached
   **Then** it rides a new **optional top-level `ResultEnvelope` key** (`contracts/envelope.py`), not a key inside `structured_content`, and `result-envelope.schema.json` is regenerated (additive under AD-28)

2. **Given** `fits` is false
   **When** the summary is built
   **Then** the sentence is rendered from the block by **one shared helper in `contracts/`** called from the envelope assembly path, never appended by an individual tool's summary function

3. **Given** a repeated query with no geometry or visibility change
   **When** framing is reported
   **Then** the cached verdict is reused; the cache key is `(fingerprint, camera_string, viewport_size, active_view_id)`, and a verdict whose key differs in any component is reported `checked:"cached"` with the differing component named in `stale_reason`

4. **Given** the human resizes the window or drags the tree/3D-view splitter
   **When** the next tool is called
   **Then** the verdict is not reported as fresh. `getSize()` changed while `getCamera()` did not, so a geometry-only staleness trigger would return `fits:true, stale_reason:None` for a viewport that now clips the model

5. **Given** any non-`OK` terminal status
   **When** the envelope is built
   **Then** the `framing` block is **omitted** — one rule, no either/or, so two implementations cannot differ on the same `TIMEOUT` and rolled-back geometry is never measured

6. **Given** the three no-verdict states
   **When** a reader inspects the result
   **Then** they are discriminated by `checked`, never by absence alone: no viewport for this document → omitted; projection attempted and failed → `fits:null` + `checked:"unavailable"` + reason; success → a real bool with `"computed"`/`"cached"`

7. **Given** a two-document session
   **When** framing is reported
   **Then** the verdict describes the **document the call targeted**, never whichever document is on screen — a warning about a document the human is not looking at is not actionable

8. **Given** the pad that grew the model past the edge
   **When** its own call returns
   **Then** that call warns: the verdict describes state after the call's own effect, read **outside** the AD-5 bracket after `commitTransaction` (`usecases/transaction.py:549`)

### Story 8.5: Enforcement — Framing Contract Test & CI Alias Gap

> **As** a project owner, **I want** the framing rules enforced by CI rather than by convention, and the pre-existing AD-20 evasion closed, **so that** these ADs are self-enforcing (AD-32, AD-20).

**Acceptance Criteria:**

1. **Given** a new contract test
   **When** CI runs
   **Then** it asserts that for every tool whose envelope carries a `framing` block with `fits:false` the rendered `text` contains the sentence, and that no tool appends it independently. Without it the AD-32 shared-helper rule is convention only: `tests/external/test_envelope_summary.py` covers just the generic `mirror_text` fallback, and real tools hand-write `text` (`usecases/screenshot.py:400-410`)

2. **Given** `scripts/check_imports.py`
   **When** the alias set is inspected
   **Then** `FREECAD_MODULE_ALIASES` (`:41`) includes `FreeCADGui` alongside `FreeCAD`/`App`. **This is a live pre-existing defect:** the `ActiveDocument` ban at `:149-169` does not match `FreeCADGui.ActiveDocument`, so that access passes CI today while violating AD-20

3. **Given** a planted `FreeCADGui.ActiveDocument` access in a test fixture
   **When** the checker runs
   **Then** it is flagged, proving the gap is closed rather than assumed

4. **Given** the checker's own diagnostics
   **When** read
   **Then** the error message (`:250-252`) and module docstring (`:11`) do not advertise `adapters/marshal.py` as Qt-exempt. `QT_EXEMPT_ADAPTERS` holds one entry and the message must say so, or an implementer will believe `marshal.py` may import Qt

5. **Given** the AD-32 deferred thresholds
   **When** implementation begins
   **Then** the `fitAll(factor)` margin and the near-miss tolerance are calibrated against real parts and recorded — a hair-trigger warning on every call is noise

---

## Epic 9: Viewport & Render Correctness

When the bridge says the human can see the model, the human can actually see it — and when it cannot, the agent is handed a measured number it can act on rather than a success it must not trust. A render from any camera angle shows the part instead of a white rectangle, and the bridge stops leaving files behind.

**Why now:** UAT run `2026-09-13-02` reproduced four defects against the shipped bridge (FreeCAD 1.1.1, GUI addon + H2 proxy). Three of them are *the spine already being right and the code not matching it* — AD-30 fixes an exact projection test that `usecases/view_fit.py` re-approximates analytically, AD-31 requires a wrong-document refusal that the shipped guard can never reach, and `design/integration-mcp-freecad.md:306` specifies a render rig the shipped `_add_lighting` silently diverged from. The fourth is a hygiene contract AD-25 states and the render path never joined.

**Sequencing:** corrects shipped Epic 8 + story 1-9 behaviour. **Opens no gate and reopens no epic** — Epic 8 stays `done`, because AD-19 keeps a passed gate closed and these corrections carry forward rather than backward. 9.1 → 9.2 are ordered (both edit `usecases/view_fit.py`); 9.3 and 9.4 touch disjoint files and are parallel-eligible with either.

**Acceptance for the epic:** the four reproducers in `tests/uat/run/2026-09-13-02/bugs.md` re-run clean, each against the regression fixture its story adds. There is no gate-exit story — this is correction work, not a phase boundary.

**Read AD-25, AD-29, AD-30, AD-31, AD-32 and AD-34 in full** — the carve-outs are load-bearing and the summaries drop them. Note in particular the one narrow carve-out where a `SPEC_FAILED` from `view_fit_viewport` does carry its `framing` block.

### Story 9.1: One Projection for Fit and Verdict, and a Fit That Verifies Itself

> **As** an agent, **I want** the fit to frame the model with the same measurement it later grades itself by, **so that** `fitted: true` means the human can actually see the part rather than that the call ran (AD-30, AD-31, AD-32; DR-1, DR-3).

**Acceptance Criteria:**

1. **Given** the corner projection
   **When** the fit computes its factor and the framing read computes its verdict
   **Then** both call **one shared routine**, and no analytic silhouette estimate remains. The shipped `usecases/view_fit.py:168 _fill_factor` takes the largest *face* diagonal over the space diagonal, which understates the true projected extent by up to 1.155× — the divergence AD-30's Prevents clause names, realised inside one file pair

2. **Given** a 40 mm cube, a 20×20×30 box, a 40×40×80 bar, a 40×25×15 plate and a 40×40×800 bar
   **When** each is fitted once
   **Then** every one lands inside the band and none clips. These span the aspect range the old tuning missed: the estimate's error runs 1.155 (cube) down to 0.856 (long bar), so **a cube and a 20×20×30 box must both be fixtures** — the two cases the shipped tuning never sampled

3. **Given** the fit has moved the camera
   **When** the envelope is built
   **Then** `fitted: true` requires the post-fit projection to return `fits: true`; a contradiction returns **`SPEC_FAILED`**. Shipped today is `{"fitted": true}` beside `framing: {"fits": false, "ratio": 1.0978}` — a tool reporting success over a window that contradicts it

4. **Given** that `SPEC_FAILED`
   **When** the caller reads it
   **Then** it **carries its `framing` block** — the single carve-out in AD-32's omission rule, because `ratio` lives nowhere else in the contract and `hosts/tool_catalog.py:1337` short-circuits non-`OK` before attaching it. Without this the new failure is strictly less informative than the defect it replaces. The ratio is **not** hand-written into the prose reason, which would put the sentence in a tool summary

5. **Given** the projection needs a camera and the camera needs the factor
   **When** the fit runs
   **Then** it is **three passes inside one animation-suspended block** — measure the pre-fit extent, `fitAll(factor)` scaling it to `_FILL_FRACTION` on **AD-32's binding axis**, then re-project through the written camera to verify

6. **Given** `setAnimationEnabled(False)` fails
   **When** the fit proceeds
   **Then** it returns `SPEC_FAILED` rather than an unverifiable `fitted: true`. Animation suspension is a **precondition**, not best-effort: with animation on, both camera writes land after the call returns and pass 3 silently re-reads the pre-fit camera — the same defect, restored

7. **Given** the factor is derived
   **When** the binding axis is chosen
   **Then** it is AD-32's (`max` of the two `extent / viewport_extent` quotients), not `fitAll`'s sphere radius. The two differ on any non-cubic part, and only the former satisfies AD-31's post-fit check

8. **Given** the comment at `usecases/view_fit.py:182-186`
   **When** the estimate is removed
   **Then** the comment goes with it. It argues the widest thing on screen is a face diagonal "looking down a cube corner" — the error is **worst** for a cube, so a reader left with it will re-derive the bug

9. **Given** the same model fitted twice
   **When** the second call returns
   **Then** the verdict is stable and within the band. Two consecutive fits on a 40 mm cube both returned `ratio 1.0978` today — non-convergent, because a geometry-derived factor cannot improve by repetition

### Story 9.2: A Wrong-Document Guard That Can Actually Fire

> **As** a human with two documents open, **I want** a fit aimed at the document I am not looking at to be refused, **so that** an agent cannot rewrite the camera of the document on my screen (AD-29, AD-31; DR-2).

**Acceptance Criteria:**

1. **Given** `ViewportPort`
   **When** inspected
   **Then** it carries **`showing_document_name() -> str | None`** beside `available()` and `view()`, implemented in `hosts/gui_addon/` off the focused Qt MDI sub-window

2. **Given** the guard compares names
   **When** it decides
   **Then** it compares the target against `showing_document_name()`, **not** against the view it resolved from the target's own name. `GuiViewportPort.view()` resolves through `getDocument(<target Name>).ActiveView`, so the shipped comparison at `usecases/view_fit.py:234-250` tests a name against itself and returns early every time

3. **Given** document A is open and document B is active on screen
   **When** a fit targets A
   **Then** it is refused naming **both** documents, and **no camera moves**. Reproduced today: with `r2other` on screen, a fit targeting `r2repro` returned `fitted: true` and rescaled the on-screen view from `8.68 × 4.14 mm` to `79.39 × 59.55 mm`

4. **Given** `showing_document_name()` cannot read the on-screen name
   **When** it returns `None`
   **Then** the fit **proceeds** — an unreadable name is no evidence of a mismatch. It carries no reason string, deliberately unlike its sibling `available()`, because both causes are treated identically and a reason would invite a caller to branch on a distinction with no consequence

5. **Given** `scripts/check_imports.py`
   **When** CI runs
   **Then** `FreeCADGui.ActiveDocument` remains banned **in every ring including `hosts/`** — `_check_active_document` is invoked at `:227` and `:306` with no layer filter. The ban is not relaxed to make this fix easier; R2-02 is the implicit-target bug the ban exists to prevent, so weakening the enforcer would invert the control

6. **Given** the `ViewportPort` class docstring
   **When** the third method lands
   **Then** its "Both answers are per document" sentence is corrected — the new method is session-wide and takes no document, so leaving that sentence makes the contract contradict itself exactly where an implementer reads it

7. **Given** a targeted document whose view exists but is not the focused one
   **When** framing is reported
   **Then** the verdict still describes the **targeted** document's own view. `showing_document_name()` governs the fit refusal only, never the framing verdict's target

### Story 9.3: Every Camera Renders a Visible Part

> **As** an agent checking my work from a named view, **I want** a render whose faces I can actually see, **so that** I can tell a successful render from an empty scene (AD-34; DR-4).

**Acceptance Criteria:**

1. **Given** each of the named cameras plus `custom`
   **When** the golden box is rendered
   **Then** every one produces a shaded interior. Today `iso` fills `rgb(159,164,169)` while `front`, `top`, `right` and `back` render the face at `rgb(255,255,255)` — identical to the background, so the PNG carries no shape information beyond its outline

2. **Given** the lighting rig
   **When** reviewed
   **Then** the headlight is offset off the pure view axis (or a second fill light is added), so a face whose normal is anti-parallel to the camera still receives a diffuse term. `adapters/render_probe.py:91-98` aims a single `SoDirectionalLight` **along** the view direction, leaving only `ambientIntensity` 0.7, which saturates the near-white default material to pure white

3. **Given** the acceptance test
   **When** it runs
   **Then** it is **two-sided**: mean interior tone differs from background by **≥ 24/255 on at least one channel** *and* lies within **`[20, 235]` on every channel**. One-sidedness is how this shipped — `_add_lighting`'s docstring states its purpose as "so no face renders black", it closed the black end and opened the white end, and a test asserting only "not black" passes the current defect

4. **Given** the interior is sampled
   **When** the assertion runs
   **Then** it excludes the outer 10 % of the span on each axis and requires **≥ 500 interior samples**. The `front` defect yielded only ~138 samples, all anti-aliased edge pixels, so a sample-count floor is part of the assertion rather than a harness detail

5. **Given** the `iso` tone the tuning comment records
   **When** the fix lands
   **Then** `iso` still reads near `rgb(158,165,169)` — the fix must not brighten the case that already matches the live viewport

6. **Given** the render is a validator under AD-13
   **When** the fault suite runs
   **Then** a planted all-white render is caught by the suite, not only by a human spot-check

7. **Given** `design/integration-mcp-freecad.md:306`
   **When** the rig changes
   **Then** that line is updated with it. It still specifies a bare `coin.SoDirectionalLight()` with no aiming and no ambient — the shipped divergence was never recorded, which is why it was never reviewed

### Story 9.4: Temp Files the Sweep Can See

> **As** an operator, **I want** every file the bridge writes to land where its own cleanup can find it, **so that** a long-running install does not accumulate orphans (AD-25; DR-5).

**Acceptance Criteria:**

1. **Given** a render or fingerprint temp file
   **When** it is created
   **Then** it is created **inside the session workdir** (`tempfile.mkstemp(..., dir=<workdir>/tmp)`). `usecases/screenshot.py:172` passes no `dir=`, so outputs land in the OS temp directory — outside the tree AD-25 scopes the sweep to, which is why 392 `FCB_TMP_shot_*` files accumulated across already-exited sessions

2. **Given** the session-start sweep
   **When** it runs
   **Then** its scope stays **exactly the session workdir**. It must not scan the OS temp directory: on a shared or multi-user host that is another session's territory, and deleting from it would break the "a caller may still be reading the link" guarantee

3. **Given** N renders followed by closing every document
   **When** the temp directory is counted
   **Then** the session's own artifacts are gone at next session start. Pre-existing strays outside the workdir are a one-time operator cleanup, not a bridge responsibility

4. **Given** the reserved `FCB_TMP_` prefix
   **When** the sweep walks it
   **Then** it treats the prefix as marking **files only**. `FCB_TMP_prev_`, `FCB_TMP_varset_probe`, `FCB_TMP_partdesign_probe` and `FCB_TMP_type_probe` name **in-memory FreeCAD documents**, are released with `closeDocument`, and must never be handed to `unlink`

5. **Given** a snapshot directory whose `rmdir` fails
   **When** the failure is swallowed
   **Then** the directory is still removable at next session start rather than orphaned silently. `usecases/transaction.py:111-116` removes the files then catches `OSError` and passes, which is why 10 empty `FCB_TMP_snap_*` directories survive today despite the deletion contract

6. **Given** the swallowed-error path
   **When** it is exercised
   **Then** the failure is surfaced (logged) rather than discarded, so the next occurrence is diagnosable. *(The survivors correlate with the snapshot-restore path, where `transaction.py:290 FreeCAD.openDocument` holds the file open; a forced undo-path rollback leaked nothing. Cause is indicated but **unverified** — do not encode it as fact without reproducing it.)*

---

## Epic 10: UAT Gate 1 Green

The bridge does what the design says when a real agent drives it through the real FreeCAD window: queries return what matches, mutations that should fail do fail, rollback is proven, and every report states what actually happened. The UAT suite and its harness describe the product as it is.

**Why now:** UAT run `2026-10-03-04` (HEAD `bece7ac`, FreeCAD 1.1.4) was the first to execute all of TC-01..TC-14. Gate 1 is red: 34 of 251 scenarios fail, 29 of them on product defects F-01..F-33 (`tests/uat/run/2026-10-03-04/report.md`, "Findings"). Most are the spine already being right and the code not matching it. The user requires Gate 1 green before Story 4.3.

**Sequencing:** corrects shipped behaviour in Epics 1-3, 8 and 9. **Opens no gate and reopens no epic** (AD-19). 10.2 -> 10.3 are ordered (both edit post-verify); Epic 11 Stories 11.1-11.4 -> 10.7 (the test cases are written once, against the new envelope); 10.7 -> 10.7b (the runner encodes the corrected test cases); the other stories are parallel-eligible; 10.8 is last.

**Acceptance for the epic:** Story 10.8 — a full UAT run with Gate 1 green.

**Rules for every story:** treat each finding as a hypothesis: reproduce it first (the report gives the request and the output), then fix with a regression test. A finding that does not reproduce is closed with evidence, not fixed. Re-run any validator score whose sources change.

### Story 10.1: Documents and Queries

> **As** an agent, **I want** document and query tools to report exactly what is in the document, **so that** I never act on a silently filtered tree or a stale handle.

**Acceptance Criteria:**

1. **Given** a Pad inside a Body
   **When** `query_tree_summary` runs with `types`, `name_pattern` or `renderable_only` filters
   **Then** matching children of a non-matching container are returned (F-01, `usecases/queries.py:352-358`; TC-02-05, TC-12-11)
2. **Given** `document_save` or `document_create` with a new path
   **When** it runs
   **Then** the label becomes the file stem, as GUI Save As does, and the result reports that `label` and the written `path` (F-02, TC-02-13)
3. **Given** `document_save` to a missing folder, to a directory, or to a read-only file
   **When** it runs
   **Then** each case returns `INVALID_INPUT` naming the path, never a catch-all `RECOMPUTE_ERROR` and never a silent folder creation (F-03, TC-02-18)
4. **Given** `document_undo` with a malformed `expect_fingerprint`, or with the string form
   **When** it runs
   **Then** a malformed fingerprint is refused before the undo, and the string form never states a false "did NOT restore" (F-12, F-20; TC-05-14, TC-08-06)
5. **Given** a document closed in the GUI
   **When** a stale handle is used
   **Then** it returns `INVALID_INPUT`, not `RECOMPUTE_ERROR` (F-25, TC-12-13)
6. **Given** `sweep_temp_dir`
   **When** it runs
   **Then** it removes only `FCB_TMP_` entries: session folders of dead hosts and prefixed entries outside every session folder, never a non-prefixed sibling and never a live host's session folder (F-30; TC-02-15, TC-99-07)

### Story 10.2: Sketch and Verify Correctness

> **As** an agent, **I want** sketch tools and `verify_*` to accept what FreeCAD accepts and report what FreeCAD measures, **so that** a verdict can be trusted.

**Acceptance Criteria:**

1. **Given** `sketch_add_geometry {kind:"point", start:[x,y]}`
   **When** it runs
   **Then** the point is created (F-04, TC-03-05)
2. **Given** a single-point `DistanceX`/`DistanceY` constraint
   **When** it is added
   **Then** it is accepted as FreeCAD accepts it (F-05, TC-03-05/06)
3. **Given** the same constraint set added in any order
   **When** the sketch is verified
   **Then** the verdict is the same; full redundancy fails like FreeCAD; partial redundancy warns (F-06, `verification-design.md` §4.2)
4. **Given** an under-constrained sketch opened from a file
   **When** `verify_sketch` runs
   **Then** the reported DoF is the solver's value after solving (F-17, TC-07-03)
5. **Given** a sketch that FreeCAD marks in error
   **When** a mutation's post-verify runs
   **Then** `recompute_clean` is false (F-19)
6. **Given** `verify_shape` with a nested `fn` mapping or `object: ""`
   **When** it runs
   **Then** both return `INVALID_INPUT` with the closed-vocabulary message (F-22, F-23; TC-09-10, TC-09-13)

### Story 10.3: Feature Tools and the Mutation Protocol

> **As** an agent, **I want** a mutation either to commit verified or to roll back with proof, **so that** AD-5 holds on every path.

**Acceptance Criteria:**

1. **Given** `feature_pad` with `second_length`, or the `TwoLengths` type
   **When** it runs
   **Then** the pad builds both lengths, or the input is refused before the transaction (F-07, TC-04-04)
2. **Given** `feature_set_parameters` with a wrong-typed value
   **When** it runs
   **Then** it is refused before a transaction opens (F-08, TC-04-21)
3. **Given** a pad on an under-constrained sketch
   **When** it runs
   **Then** post-verify covers the sketch the feature consumes, and the mutation is refused (F-09, AD-8; TC-04-23, TC-05-03)
4. **Given** a failed mutation restored from its snapshot
   **When** the rollback is proven
   **Then** the proof compares a representation that survives reopening, and `rolled_back_via_snapshot` is reached (F-10, TC-05-06)
5. **Given** UndoMode 0 and a broken feature
   **When** the rollback is verified
   **Then** null shapes are part of the fingerprint, and a broken Tip is never reported `rolled_back_verified` (F-11, TC-05-08)
6. **Given** a TNP audit that did not run, or a reference that broke
   **When** the mutation reports
   **Then** the audit status is never `CLEAN` (F-13, TC-05-15..18)
7. **Given** auto-approve
   **When** the audit log is written
   **Then** approval and mutation lines share one `params_digest` and carry `fingerprint_before` (F-21; TC-08-18, TC-11-08)

### Story 10.4: Render and Framing

> **As** an agent, **I want** a render and a framing verdict that describe what the window shows, without changing the document.

**Acceptance Criteria:**

1. **Given** `query_screenshot` with `include` naming a Body
   **When** it renders
   **Then** the PNG shows the Body, or the envelope reports `empty_scene: true` (F-14, TC-06-03)
2. **Given** an `include` naming a hidden object
   **When** it renders
   **Then** the live document's visibility and modified state are unchanged (F-15, TC-13-03)
3. **Given** a style with `transparency` and no colour
   **When** it renders
   **Then** the transparency applies (F-16, TC-06-04)
4. **Given** a window of any size
   **When** framing is measured or `view_fit_viewport` runs
   **Then** the bound is the whole 3D view (`getSize()`, AD-30), whatever its size; a FreeCAD window so small that the MDI area scrolls part of the 3D view off screen is outside the bridge's scope (F-27 is not a product defect; TC-14-13 is corrected in Story 10.7)
5. **Given** a document whose only geometry is a datum plane, a sketch or a mesh
   **When** `view_fit_viewport` runs
   **Then** it fits that geometry or reports why it cannot, never `OK` with `ratio: 0.0` (F-28; TC-02-08, TC-04-12/13)

### Story 10.5: STEP Export Schema

> **As** an agent, **I want** `export_step {ap:"AP242"}` to write AP242.

**Acceptance Criteria:**

1. **Given** `export_step` with `ap: "AP242"`, and with the default
   **When** the file is written
   **Then** its `FILE_SCHEMA` names AP242, and the paired verify checks it (F-18; TC-07-05, TC-09-08)

### Story 10.6: Session, Transport and Bounded Execution

> **As** an operator, **I want** the bridge to bound every call, own its port and log what happens, as AD-26 and AD-27 state.

**Acceptance Criteria:**

1. **Given** any tool in the headless host
   **When** it runs past its registry `timeout_s`
   **Then** it returns `TIMEOUT` and the session is quarantined per AD-27 (TC-10-11, `design/integration-mcp-freecad.md` §2.4)
2. **Given** a `debug_exec` that timed out
   **When** the next call arrives
   **Then** it is refused or served without waiting on the abandoned body's registry lock (F-33)
3. **Given** a second RPC client
   **When** it connects while a session is active
   **Then** it gets the AD-26 busy error, never a hang (TC-99-07)
4. **Given** an unclean FreeCAD kill
   **When** FreeCAD relaunches
   **Then** the addon does not adopt an orphan or foreign server on `:8765`; it verifies `/healthz` session identity (F-26; TC-01-14, TC-10-12, TC-12-15, TC-99-08)
5. **Given** a malformed first frame, a clean exit, or an in-flight call dropped by a kill
   **When** the listener and proxy log
   **Then** each event is logged once at the right level, with no traceback on a clean exit (F-24, F-31)
6. **Given** the discovery file on Windows
   **When** it is written
   **Then** the code comment states the ACL protection actually applied (F-32)

### Story 10.7: UAT Suite and Harness Maintenance

> **As** a tester, **I want** the UAT test cases and harness to describe the shipped product and run without human rescue.

**Acceptance Criteria:**

1. **Given** the test-case defects in the report
   **When** the test cases are updated
   **Then** they read the build version and the tool count from the live bridge, use current field names, accept the MCP schema-layer refusal where the input is still refused, show golden models before fitting, use FreeCAD 1.1.4 edge numbering and menu labels, and build fixtures the bridge allows
2. **Given** disputed TC-02-17, TC-08-14, TC-10-06, and TC-06-01 / TC-13-06 (render shading)
   **When** the test cases are updated
   **Then** they assert the shipped behaviour, citing the decision in the sprint change proposal of 2026-10-04
3. **Given** TC-99-03/04/05 (AD-25 partly implemented)
   **When** the test cases are updated
   **Then** the implemented parts are promoted to Gate 1 and only the remaining gap stays expected-fail
4. **Given** the harness findings
   **When** the GUI harness standard is updated
   **Then** it forbids opening modal dialogs through `invoke_menu`, requires FreeCAD to run at the agent shell's integrity level, and documents the background-input routes that work on 1.1.4
5. **Given** `scripts/automation/uat_watchdog.py --since` with an offset-aware timestamp
   **When** it runs
   **Then** it does not crash
6. **Given** TC-06-10 and TC-13-17 (BLOCKED: no route to a Touched document)
   **When** the test cases are updated
   **Then** they build the Touched state through a route the bridge offers, or are retired with the reason

### Story 10.7b: Scripted UAT Runner and FreeCAD Probe

> **As** a tester, **I want** the deterministic Thens measured by scripts through a channel independent of the bridge, with `cua-driver` kept for captures, re-checks and troubleshooting, **so that** a full UAT run takes minutes of scripted work plus targeted agent review instead of about 10 hours, without losing accuracy.

**Why:** UAT run `2026-10-03-04` took about 10 h of active work for 251 scenarios. An LLM agent reasoned through every scenario, FreeCAD was relaunched 31 times (`evidence/launch-log.tsv`), the session limit stopped the run twice, UIA automation timed out and froze on modal dialogs, and desktop use forced background-only input.

**Acceptance Criteria:**

1. **Given** a running FreeCAD GUI
   **When** the test-only probe is queried
   **Then** it returns, read-only and from FreeCAD's own kernel and GUI state, each object's type, visibility, `Shape` validity, volume and bounding box, the document's modified flag, the active document, the camera and the visible view size; the probe shares no code with `src/freecad_buddy`, is not shipped in the addon, and loads only under the UAT launch profile
2. **Given** a saved document
   **When** it must be checked offline
   **Then** a FreeCADCmd reader measures it from the `.FCStd` file without loading the bridge
3. **Given** the probe's own fault set (planted wrong visibility, wrong volume, modified flag, wrong active document, clipped view)
   **When** the probe runs against each planted state
   **Then** it detects every one (the AD-13 sensitivity discipline applied to the oracle)
4. **Given** a test-case scenario
   **When** it is encoded as an executable scenario file (request, expected envelope fields, probe assertions, pixel checks)
   **Then** the runner executes it with no LLM call, and the test-case markdown stays the human-readable source
5. **Given** a window capture taken through `cua-driver` at a fixed window size and DPI
   **When** it is graded
   **Then** a scripted pixel check measures the non-background extent against the frame and colour samples at points projected from the probe's geometry, and compares against a golden capture where one exists
6. **Given** a scripted check that fails, or a probe measurement that disagrees with the MCP output
   **When** the runner reports it
   **Then** the scenario goes to the escalation ladder: re-check through `cua-driver` (property panel or tree read, Part > Check Geometry, agent-read capture), then troubleshoot by driving FreeCAD with `cua-driver`; a disagreement is a finding, never a retry, and a scripted pass never stands without its capture
7. **Given** scenarios that need different launch settings (auto-approve, exec, audit-log path)
   **When** the runner schedules them
   **Then** it groups them by launch configuration, launches FreeCAD non-elevated with a dedicated UAT profile (`-u`) so the developer's `user.cfg` is untouched, and never opens a modal dialog through `invoke_menu`
8. **Given** `tests/uat/test-plan.md` §9
   **When** it is updated
   **Then** the agent reads the capture for every FAIL, every probe/MCP disagreement, the first scenario of each test case, and a random 20 % sample of the rest; every other scenario is graded by the scripted pixel check against its stored capture
9. **Given** the 2026-10-03-04 run
   **When** the runner replays every deterministic Then it covers
   **Then** it reproduces the recorded verdicts, and any difference is explained

### Story 10.8: UAT Gate 1 Re-run

> **As** the team, **I want** a full UAT run that proves Gate 1 green before Epic 4 resumes.

**Acceptance Criteria:**

1. **Given** Stories 10.1-10.7b done and CI green
   **When** the full suite TC-01..TC-14, TC-99 and the G3 live replay run on FreeCAD 1.1.4 through the Story 10.7b runner, with agent review per the updated §9 and the desktop free (or the GUI lane in an isolated Windows session)
   **Then** Gate 1 is green (Critical 100 %, High ≥ 95 %), Gate 2 matches its documented deviations, and the G3 replay is unchanged; the report is committed under `tests/uat/run/`

## Epic 11: Lean Agent Loop

An agent builds a part with fewer calls and a small context: every mutation still runs every check, and its result reports what changed and what failed, not every value that passed. The operator can run attended GUI work with one call per mutation. The skills stop asking for checks the mutation result already gives. A change on a large document freezes the GUI only for FreeCAD's own recompute, not for bridge overhead.

**Why now:** three build sessions on 2026-10-06 (`eacac40d`, `ff604ce5`, `0320ba38`) used 98-310 FreeCAD calls, reached 797K-820K context tokens, and compacted 8 times in the longest one. 86 % of FreeCAD output was full fingerprints and PASS findings that no caller reads. The spine Tool-results convention already forbids raw dumps. On a copy of `kiwibox-drawer.FCStd` one change costs about 65 s with preview, of which FreeCAD's recompute is 29 s and the rest is bridge overhead (`sprint-change-proposal-2026-10-06.md` §1).

**Sequencing:** 11.1 -> 11.2 and 11.1 -> 11.4 (11.2 makes mass properties the visible change record, and 11.4 makes them the abort-path rollback proof, so they must be right first). 11.3 and 11.4 are parallel-eligible with 11.2; 11.4 edits `usecases/transaction.py`, so it merges after 11.2. 11.1-11.4 finish before Story 10.7. 11.5 is parallel-eligible. 11.6 is last. **Opens no gate and reopens no epic** (AD-19).

**Acceptance for the epic:** Story 11.6: a measured build session meets the targets in its acceptance criteria.

**Rules for every story:** no check is removed or weakened. Each story proves that the AD-5 bracket, the AD-6 rollback proof, the AD-7 audit and the AD-8 sketch signal still run and still fail a bad change. Re-run any validator score whose sources change.

### Story 11.1: Mass Properties That Tell Shapes Apart

> **As** the bridge, **I want** every fingerprint's mass properties computed from the shape's solids and sensitive to orientation, so that `massprops_equal`, the identity check in 4 of 5 comparison sites, sees a rotation or mirror about the centre of mass.

**Evidence (2026-10-06, headless probe on a copy of `kiwibox-drawer.FCStd`):** `principal_moments` is `[0, 0, 0]` on 74 of 144 hashed objects, all `Compound` shapes without `PrincipalProperties`; the solid inside has real moments, for example `(3.4e8, 1.9e8, 1.8e8)`. Principal moments are eigenvalues of the inertia tensor, so even real values do not change under a rotation or mirror about the centre of mass.

**Acceptance Criteria:**

1. **Given** a compound of solids, **When** `fingerprint()` runs, **Then** `principal_moments` come from its solids and are non-zero for any non-empty solid; a unit test under `tests/infc/` fails on zero moments for a non-empty compound.
2. **Given** any shape, **Then** `MassProps` carries `inertia`: the 6 components of the inertia tensor about the centre of mass in document axes (`Ixx, Iyy, Izz, Ixy, Ixz, Iyz`), computed from the solids, as an optional field added to `fcb.fingerprint/1` (additive, AD-28); `massprops_equal` compares it.
3. **Given** an asymmetric solid rotated 90° about its centre of mass, and the same solid mirrored through a plane through its centre of mass, **When** `massprops_equal(before, after)` runs, **Then** it returns `False` for both (regression tests). A solid with symmetric inertia is a documented limit.
4. **Given** a copy of `kiwibox-drawer.FCStd`, **When** one feature is changed inside a transaction, aborted and recomputed, **Then** `massprops_equal(before, after)` is `True` on every object; the quantization step for `inertia` is set so that this holds, and the story records the step and the measured jitter.

### Story 11.2: Quiet Result Envelope

> **As** an agent, **I want** a mutation or preview result that carries the digest, the changed objects and the non-PASS findings, so that one result costs about 2K chars instead of 30-110K.

**Acceptance Criteria:**

1. **Given** any successful mutation, **When** the result returns, **Then** `mutation.fingerprint_before` and `mutation.fingerprint_after` are digest strings with their serializer tag, and `mutation.changed` lists `{name, volume, area, com}` for each object whose mass-property invariants differ (empty on a no-op).
2. **Given** a mutation that fails or rolls back, **When** the result returns, **Then** `changed` also carries the full before and after `massprops` of each object that differs, and `rolled_back` / `rollback_proven` are as today.
3. **Given** any `tnp_audit` or `tnp_precheck` block, **Then** it is `{status, element_map_version, counts: {<verdict>: n}, findings: [non-PASS only]}`; a FLAGGED audit lists every non-PASS finding.
4. **Given** a preview, **Then** `diff.op` is `{tool}` and `text` does not repeat `preview_id`.
5. **Given** any result, **Then** `adapters/mcp_server.py` writes compact JSON (no `indent=2`).
6. **Given** the full `FingerprintRecord`, **Then** it stays on the server in an in-process cache keyed by digest; `document_undo(expect_fingerprint=<digest>)` uses it for the mass-property comparison, and the hint at `usecases/documents.py:166-168` is removed.
7. **Given** the projection, **Then** it is built in `usecases/` (AD-17), the contracts are `fcb.mutation/2` and `fcb.geometry-diff/2` with `/1` retained for audit replay (AD-28), and the generated schemas pass the drift check.
8. **Given** the 529 recorded results from the three sessions, **When** a replay script projects them through the new code path, **Then** total size drops by ≥ 85 % and no result is over 10K chars.
9. **Given** the G2 fault suite (rollback-boundary, TNP-provoking, dress-up silent drop), **When** it runs, **Then** every case fails or flags exactly as before.

### Story 11.3: One Call per Mutation

> **As** an operator, **I want** attended GUI work to apply a mutation in one call when I have set auto-approve, so that the agent does not spend a preview round trip on every change.

**Acceptance Criteria:**

1. **Given** FreeCAD started without `FREECAD_BUDDY_AUTO_APPROVE` (auto-approve is on by default; unset or `1` is on, any other value is off), **When** an agent calls `feature_pad` without `confirm`, **Then** the pad applies under the full AD-5 bracket and the audit log records an `approval` with `mode: "auto_approve"` and `source: "FREECAD_BUDDY_AUTO_APPROVE"`.
2. **Given** the same posture and a mutation that fails post-verify, **Then** it rolls back and returns its failure status exactly as with a token.
3. **Given** `feature_set_parameters` that writes only `Visibility`, **When** called without `confirm` and without auto-approve, **Then** it applies (display state, same carve-out as `view_fit_viewport`) and is audit-logged; any other property in the same call keeps the gate.
4. **Given** `FREECAD_BUDDY_AUTO_APPROVE=0`, **Then** every other mutation still needs a valid `preview_id` (no regression).
5. The operator setup is documented in `README.md` and in the GUI harness standard.

### Story 11.4: Cheap, Correct Rollback Proof and Fingerprints

> **As** the bridge, **I want** each mutation to do whole-document work only as often as its guarantees need, and to prove a FreeCAD abort without a needless snapshot restore, so that a change on a large document freezes the GUI for FreeCAD's recompute and not for bridge overhead.

**Evidence (2026-10-06, headless, copy of `kiwibox-drawer.FCStd`, 184 objects):** one `fingerprint()` takes 4.5 s (mass properties 3.6 s, B-rep bytes 0.9 s); `saveCopy` 1.2 s; FreeCAD's recompute after one `duct_pilot` change 14.6 s for 23 objects. A live mutation runs 3 fingerprints and a preview 4. After `abortTransaction` + recompute, mass properties matched on every object, but 33 objects had new B-rep bytes. So the digest proof at `usecases/transaction.py:356` fails, and every failed mutation restores the snapshot, which closes and reopens the document.

**Acceptance Criteria:**

1. **Given** a successful live mutation, **When** it runs, **Then** `fingerprint()` runs 2 times, not 3: the gate record (`confirm.gate_mutation`) is passed into `run_mutation` and used as `fp_before`. A test counts the calls.
2. **Given** the abort path, **Then** rollback is proven by digest equality, else by `massprops_equal` over the same object names (Story 11.1 invariants); only an invariant mismatch restores the snapshot. **Given** a mutation on the drawer copy that fails post-verify, **Then** it returns `rolled_back_verified` and the document is never closed or reopened.
3. **Given** the failure path, **Then** the fingerprint computed for the rollback proof is reused as the block's `fingerprint_after`, not recomputed.
4. **Given** a fingerprint, **Then** an object whose shape is unchanged since its last fingerprint reuses its cached entry. The story chooses the unchanged-shape test, and a test proves that a changed shape never reuses its entry. The abort-path and snapshot-restore proofs compute every entry fresh.
5. **Given** `snapshot_references`, **Then** a property value is read only after its type passes the link-type filter (`usecases/tnp_guard.py:322-326`).
6. **Given** the drawer copy and one leaf change (`duct_pilot.Length`), **When** the live mutation is timed (median of 5, headless and in the GUI), **Then** the median bridge overhead (total time minus FreeCAD's recompute) is ≤ 18 s headless (baseline `118e765`: 49.4 s) and ≤ 10 s in the GUI; the timings are recorded in the story file.
7. **Given** the G2 fault suite, **Then** the rollback-boundary (#6031-pattern) cases still escalate to the snapshot restore and pass, and all `test_mutation_protocol.py`, `test_tnp_guard.py` and fingerprint tests pass.

### Story 11.5: Build-Loop Skills

> **As** an agent, **I want** skills that use the checks the mutation result already reports, so that I verify per milestone and not per feature.

**Acceptance Criteria:**

1. `verification-thinking` adds a build-loop rule: per feature, read `post_verify`, `sketch_state` and `changed`, with no `verify_*` call and no screenshot; per milestone (a finished part or feature group), one `verify_shape` with every spec check and one screenshot packet; call `verify_*` again after any change made outside the typed tools. `SKILL.md:68-72` keeps "even when every deterministic check passed" and changes "every part whose geometry changed" to "every milestone".
2. `freecad-sketcher` states that `sketch_state.fully_constrained` and `dof` in the mutation result are the AD-8 signal, and that a separate `verify_sketch` is for a sketch changed outside the typed tools.
3. `freecad-scripting-idioms` forbids editing the live model through headless scripts while the bridge serves it.
4. `design-decomposition` states the CAD plan shape: a parameter table and milestones, one commit per milestone, no per-step checkboxes and no hand-predicted volumes.
5. All 19 references to `verify_references` and `verify_fingerprint` in 9 files point to `post_verify.tnp_audit` and `mutation.fingerprint_*` digests.
6. `verification-thinking/references/snapshot-packet-sizing.md` sets 800 px as the default screenshot size and keeps the AD-21 review floor where it applies.
7. `design-decomposition` states that derived pieces (print splits, `Part::Common` cuts of a master body) stay out of the edit loop: in a separate document, or rebuilt only at milestones. Evidence: on `kiwibox-drawer.FCStd`, 3 split `Part::Common` objects take 7.5 s of the 14.6 s recompute after one change to the master body.
8. `scripts/check_skill_shape.py` passes (4 sections, ≤ 1,500 words per `SKILL.md`).

### Story 11.6: Measured Build Session

> **As** the team, **I want** one real build measured against the 2026-10-06 baseline, so that the epic is closed on numbers.

**Acceptance Criteria:**

1. A transcript metrics script lands in `scripts/automation/` and reports, per session: FreeCAD calls, `preview_dry_run` calls, FreeCAD output chars, largest result, spilled results, peak context, compactions.
2. **Given** Stories 11.1-11.5 done, auto-approve set and the updated skills installed, **When** an agent builds a part of the same size class as the kiwibox drawer (about 100+ objects) in the FreeCAD GUI, **Then** the script reports: FreeCAD output ≤ 15 % of the `0320ba38` value per FreeCAD call, 0 spilled results, no result over 10K chars, and FreeCAD calls per feature ≤ 2 (median).
3. **Given** the same session, **Then** the median bridge overhead per mutation, measured by the Story 11.4 timing method, is ≤ 3 s.
4. The agent visually checks the finished part against a real FreeCAD screenshot, and a native Check Geometry passes (`freecad-native-validation` standard).
5. The report, with the baseline numbers beside the new numbers, is committed under `tests/uat/run/`.
