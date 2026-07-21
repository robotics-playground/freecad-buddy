---
project_name: 'freecad-buddy'
user_name: 'TanNT'
date: '2026-07-21'
sections_completed:
  ['technology_stack', 'ring_import_rules', 'freecad_api_traps', 'verification_discipline', 'testing_ci_rules', 'wire_schema_rules', 'security_rules', 'workflow_rules', 'dont_miss_rules']
status: 'complete'
rule_count: 62
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

- Python: match the CI leg's bundled FreeCAD interpreter — 3.11 (FreeCAD 1.0.x leg) / 3.12 (1.1.x leg). `requires-python = ">=3.11"`; no 3.12-only syntax until the 1.0.x leg retires.
- FreeCAD: 1.0.x floor + 1.1.x primary (both blocking in CI, conda-forge via micromamba); 1.2-dev weekly canary allowed-to-fail. 0.21 unsupported — never write compat code for it.
- MCP: official `mcp` python-sdk, spec ≥2025-06-18 (elicitation required by preview flow). Exact pin decided at Phase 0 gate after SDK v2 — check `pyproject.toml`, don't assume.
- PrefectHQ `fastmcp` ≠ official SDK `FastMCP` class — distinct projects; the repo pins one, check before importing.
- Export oracles: trimesh + lib3mf (required); admesh optional Linux-only secondary (dormant upstream).
- Tooling: uv (external process deps only — never for in-FreeCAD code), pytest (external tests only), stdlib `unittest` (in-FreeCAD tests), ruff, hatchling.
- CI: GitHub Actions + `mamba-org/setup-micromamba` cached per FreeCAD pin; render leg = xvfb + `LIBGL_ALWAYS_SOFTWARE=1`, non-blocking.

FreeCAD comes from the host (GUI install or conda env), never from pyproject. Interpreter version is per-leg, not global.

## Critical Implementation Rules

### Architecture Ring & Import Rules (AD-1, AD-12)

- Dependency rule inward-only: `contracts/` ← `usecases/` ← `adapters/` ← `hosts/`. Never import outward or sideways across rings.
- `contracts/`: stdlib ONLY. No FreeCAD, no third-party, no pydantic — TypedDict + Literal + dataclass.
- `usecases/`: stdlib + FreeCAD App modules (`FreeCAD`, `Part`, `Sketcher`, `PartDesign`, `Mesh`, `MeshPart`) — and version-sensitive calls go through `usecases/shim.py`, never direct.
- `FreeCADGui`/`PySide`/Qt: ONLY in `hosts/`, `adapters/marshal.py` (QtCore only), `adapters/render_probe.py`. `scripts/check_imports.py` enforces; don't fight it, fix the placement.
- Anything running inside the FreeCAD process (rpc_listener, marshal, all usecases/contracts) = zero third-party imports. mcp/trimesh/lib3mf/pytest exist only in the external uv process.
- Import Qt symbols inside functions in `marshal.py` (module import stays clean for headless).
- `adapters/__init__.py` and `hosts/__init__.py` stay EMPTY — import discipline depends on it.
- One package serves three hosts (GUI addon path, headless inline, FreeCADCmd RPC) — never branch on host identity in usecases; branch on capability probes.

### FreeCAD API Traps

- Every FreeCAD call in GUI mode executes on the Qt main thread via the marshal — never call FreeCAD/Qt from a listener/worker thread (crash mode). Headless has no Qt loop; marshal degrades to inline.
- Sketch pass signal = `sketch.FullyConstrained` read AFTER `doc.recompute()`. NEVER infer from `solve() == 0` (0 means "solved", an under-constrained sketch also returns 0). `solve()` codes are logging only.
- Undo/abort does NOT recompute — always `doc.recompute()` after `abortTransaction`/undo before reading/verifying anything.
- Headless opens no transactions by itself — the bridge always brackets mutations with `openTransaction`/`commitTransaction` (transaction id 0, never nested; a new `openTransaction` silently auto-commits a stray open one and wipes redo).
- Undo is NOT trustworthy alone (bug #6031): rollback success is proven by fingerprint re-hash, escalating to saveCopy restore. Never claim rolled-back without the hash proof.
- Script against immutable `obj.Name`; display `obj.Label`. Never key logic on Label.
- `ActiveDocument` is banned as a target — every operation takes an explicit doc handle.
- Sub-element references: geometric-query or TNP mapped-name selectors. Bare `Face6`/`Edge3` may be resolved at call time but never stored (indices reshuffle on recompute).
- `FeatureDressUp` silently DROPS edges that lose two-adjacent-faces — reference count comparison is mandatory; error state alone misses it.
- No element map (probe fails) → TNP audit reports `UNSUPPORTED`, never clean. `ElementMapVersion` bump → re-baseline, not failure.
- Capability probes (`hasattr`, test render, shim functions), never FreeCAD version-string comparisons.
- Attachment property is `AttachmentSupport` (1.x); access via shim accessor only.
- Renders: constructed scene from `subgraphFromObject` — never mutate `Visibility` or the user's viewport for a screenshot; never use raw `pivy.coin.SoOffscreenRenderer` (use `FreeCADGui.SoQtOffscreenRenderer`); call `setupWithoutGUI()` before any `*Gui` import headless.
- Mesh exports: single tessellation source `MeshPart.meshFromShape` with linear AND angular deflection (linear-only under-tessellates curves, #25311).
- Units: internal mm/deg; every tool param/result carries explicit units; STEP export pins `write.step.unit=MM` per call — never trust ambient defaults.

### Verification & Validation Discipline

- The actor NEVER grades itself (AD-13). Pass/fail comes from deterministic `verify_*` code or an independent grader/judge with separate model/context. Agent output claims are diagnostic input, never results.
- Every mutation flows through `run_mutation()` (AD-5): fingerprint snapshot → saveCopy → transaction → op → recompute → post-verify → commit | proven rollback. No mutation outside this wrapper, ever.
- Exports are done only when the paired `verify_export_*` passes re-import (AD-9). "File was written" is never success. Independent-oracle disagreement = FAIL, never averaged.
- Part-done = geometry assertions PASS ∧ independent visual judge PASS (AD-21). Judge is conjunctive — cannot rescue a geometry failure. Render/judge unavailable → NOT done (operator waiver only, audit-logged).
- A validator's scores are citable only while its fault-suite run is current (source-hash match) at sensitivity ≥95 % / false-alarm ≤5 % (NFR2). Editing a validator stales its run.
- Entry gate before implementation (AD-19): benchmark + assertions + fault suite + rubric land first and fail honestly against a stub.
- Assertions measure geometry in the declared anchor frame; feature metadata (e.g. Hole.Diameter) is hint-only; whole-shape similarity (Chamfer/IoU) is never a primary metric.
- Stats: majority-of-R, Wilson CI beside every rate, exact McNemar for ablations, dev/held-out gap >15pp blocks exit (AD-14). Never report a raw pass-rate delta as a win.
- `benchmarks/*/heldout/` is SEALED — never open, read, or reference it outside a `gate run --exit`. Dev iteration touches `dev/` only.

### Testing & CI Rules

- Two test worlds, never mixed: `tests/infc/` runs under `FreeCADCmd` with stdlib `unittest` ONLY (one process, whole suite via `tests/run_tests.py`); `tests/external/` runs under pytest in the uv env. pytest inside FreeCADCmd = AD-12 violation.
- Both blocking CI legs (1.0.x + 1.1.x) must stay green; a check that passes only in-GUI doesn't count — headless is the gate.
- Render tests are tagged and isolated in the non-blocking xvfb leg — never let a render assert block the core gate.
- Round-trip fixtures are authored on FreeCAD 1.0 (1.1 core-datum files won't open in 1.0).
- Fault-injection cases live beside dev/heldout, never inside them — they validate validators, never count toward pass rates.
- Golden values in tests come from independent references (hand-computed, reference models), never captured from the implementation under test.

### Wire & Schema Rules

- All wire types are contracts-owned (AD-17): ResultEnvelope, ValidationReport, JobStatus, AuditRecord, GeometryDiff, RPC frames. Never define a variant, never add an inline status string — the closed set is `OK|SPEC_FAILED|RECOMPUTE_ERROR|TIMEOUT|OOM_KILLED|WORKER_CRASHED|INVALID_INPUT`.
- Schema evolution: additive-only within a major; enum change = major bump. `jsonschema/` regenerates byte-identical or CI fails.
- Tool names on the wire: underscore + namespace prefix (`verify_shape`). Dots are ILLEGAL in MCP tool names — dot forms in docs are shorthand.
- `ResultEnvelope.text` is server-derived from `structured_content` — never hand-author the mirror.
- stdout on the stdio path is protocol — `print()` banned in server code (ruff T201); logging → stderr; audit log → append-only JSON-lines file.
- Fingerprints carry serializer tags (`exportBinary`/`exportBrep`); comparing across tags raises — never catch-and-ignore it.

### Security Rules

- Typed tools are the ONLY AI mutation path (AD-4). Never route model output through `exec`; `debug_exec` is operator-only (env flag, unregistered when off, permanently off in service mode, every call audit-logged).
- In-process Python restriction (RestrictedPython, audit hooks, import blacklists) is NEVER called or treated as a security boundary — monitoring/hardening only. Real boundaries: typed layer + OS sandbox.
- Binds: 127.0.0.1 only; per-session `secrets.token_urlsafe(32)` in a 0600 discovery file; `hmac.compare_digest` for validation; remote bind = explicit operator opt-in with stderr warning.
- Preview/confirm gate: mutations without valid confirmation (elicitation accept / `preview_id` token / audit-logged `autoApprove`) return `INVALID_INPUT` — fail closed, never fail open.

### Development Workflow Rules

- NEVER commit without explicit user approval. Conventional Commits format. No AI attribution / Co-Authored-By trailers ever.
- Never push/commit directly to protected branches (main/develop/release/...) without explicit confirmation naming branch + operation.
- Design conflict discovered mid-implementation → stop, cite the AD/design doc, propose correction — never silently diverge (spine ADs bind; amendments go through the spine memlog).
- Approved implementation change that alters a design contract → update the authoritative design doc in the same change.
- Reuse before invention: wrap adopted components, don't fork; record why for anything built from scratch.

### Critical Don't-Miss Rules

- Read the story's References line before implementing — design docs + research reports per area are mandatory context, not suggestions.
- TempDocs: reserved prefix `FCB_TMP_`, transient flag, cleaned only by their creator.
- Documents open/close only through `document_*` usecases — harness and supervisor included; raw `App.openDocument` alongside the bridge is a bug.
- Marshal timeout → session is document-suspect: refuse further mutations on that doc until a fingerprint check confirms state. Never blind-retry a mutation.
- Images: ≤1024 px, `audience:["user"]`, resource_link preferred (inline base64 blows client token budgets 10–20×). Exception: visual-judge inputs go direct to the judge API at ≥2048 px.
- Phase 4 workers: never import FreeCAD in the supervisor; `spawn` never `fork`; whole-tree kill, never top-PID-only.

---

## Authoritative Sources

Rules above are distilled; full contracts live in:

- Architecture spine (21 ADs): `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/ARCHITECTURE-SPINE.md`
- Design docs (10): same folder, `design/` — indexed below
- Spec + phase gates: `_bmad-output/specs/spec-freecad-buddy/`
- Epics & stories: `_bmad-output/planning-artifacts/epics.md`
- Research reports (18): `_bmad-output/planning-artifacts/research/`

### Design Document Index

All paths relative to the architecture folder above (`.../architecture-freecad-buddy-2026-07-21/`). Open the doc whose scope matches the work; the spine AD is the binding contract, the design doc is the implementation-ready expansion.

| Design doc (`design/…`) | Covers | ADs | Open it when |
| --- | --- | --- | --- |
| `project-structure.md` | Repo tree (Phase 0 file level), dual packaging (uv external + FreeCAD addon), Python/FreeCAD version legs, environments, CI workflow layout | AD-1, AD-11, AD-12 | Scaffolding, adding a module/dir, touching `pyproject.toml`/`ci.yml`/`canary.yml`, packaging the addon |
| `component-design.md` | Per-ring component inventory, public interfaces, interaction flows (headless/GUI call paths, mutation sequence), phase-availability table | AD-1, AD-2 | Placing a new component in a ring, wiring a usecase↔adapter↔host, checking what ships in which phase |
| `data-contracts-design.md` | `contracts/` types: `ResultEnvelope`, `ValidationReport`, `JobStatus`, `AuditRecord`, `GeometryDiff`, `DocHandle`/selectors, `FingerprintRecord`, RPC frames; versioning/evolution rules; cross-contract invariants | AD-6, AD-17, AD-20 | Adding/changing any wire type, an `outputSchema`, a status/enum, the audit record, or a selector shape |
| `mcp-tools-design.md` | Phase 0–2 tool catalog (49 tools), per-tool input/`outputSchema` fragments, selector + confirm `$defs`, tool counts (G0.2), `debug_exec` registration rules | AD-4, AD-20 | Adding/editing a tool, its schema, name, or the confirm/preview gate; checking the tool inventory |
| `integration-mcp-freecad.md` | Process topology (GUI/H1/H2), RPC wire contract + handshake + error codes + timeouts, main-thread marshal, version shim (`shim.py`) surface, screenshot/render integration, failure modes | AD-2, AD-3, AD-11 | Touching `rpc_listener`/`rpc_client`/`marshal`/`shim.py`, the RPC framing, capability probes, or the render path |
| `integration-mcp-clients.md` | Per-client wiring (Claude Code/Desktop, llama.cpp local, ReAct fallback), transport + elicitation, confirmation matrix, image/render delivery rules, backend capability matrix, latency budget | AD-3, AD-10, AD-15 | Wiring a new MCP client/backend, the confirmation UX per client, or image-delivery decisions |
| `verification-design.md` | Mutation protocol (`run_mutation`), `fingerprint()`, TNP guard (layers 0–2), `verify_sketch`/`verify_shape`/`verify_export_*`, Phase 3 assertion vocabulary, `verify_visual`, tolerance policy | AD-5, AD-6, AD-7, AD-8, AD-9, AD-13, AD-21 | Implementing/editing any `verify_*`, the transaction wrapper, fingerprint, TNP audit, an assertion primitive, or a tolerance |
| `validation-harness-design.md` | Gate runner CLI + execution flow, `benchmarks/` layout, held-out sealing, provenance manifest, stats module (Wilson/McNemar/majority-of-R), fault-injection framework, human-token mechanism, independent grader + visual judge wiring | AD-13, AD-14, AD-16, AD-19 | Working on a gate, benchmark case, fault suite, stats, grader/judge, sealing, or provenance |
| `skills-structure-design.md` | Skill store layout, `SKILL.md` template (4 sections, ≤1,500 words), two-mode loader (router + forced-subset), routing table, CI shape check, token budgets | AD-15 | Authoring/editing a skill, the loader, routing rules, or the skill CI check |
| `security-and-service-design.md` | `debug_exec` gating, RPC bind/token posture, stderr-only enforcement, per-phase threat model, Phase 4 supervisor + per-job sandbox + data plane + re-executed checks, rejected-mechanism table | AD-4, AD-17, AD-18 | Security-sensitive work, `debug_exec`, the audit log, or any Phase 4 supervisor/worker/sandbox code |

---

## Usage Guidelines

**For AI Agents:**

- Read this file before implementing any code
- Follow ALL rules exactly as documented
- When in doubt, prefer the more restrictive option
- Rule conflicts with a design doc → the spine AD wins; surface the conflict, don't pick silently

**For Humans:**

- Keep this file lean and agent-focused; full rationale lives in the authoritative sources above
- Update when the stack pins land at the Phase 0 gate (MCP SDK, second STL oracle, serializer)
- Remove rules that CI now enforces mechanically — enforced rules don't need reminding

Last Updated: 2026-07-21
