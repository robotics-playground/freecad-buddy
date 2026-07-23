# Sprint Change Proposal — Robot-Description Export & Part Sourcing

**Date:** 2026-07-23 · **Author:** TanNT · **Mode:** Batch
**Scope classification:** Major (new capability + new phase + new ADs + spine update)

---

## Section 1 — Issue Summary

**Trigger.** While adapting an external CAD/robotics agent-skills repo (`docs/references/text-to-cad/`) into the project's skill library, five reference-repo skill domains were found that sit outside the ratified FreeCAD-parametric catalog: **URDF, SRDF, SDF, Implicit CAD, step.parts**. The user asked whether FreeCAD can support them and, on the evidence, ruled: **scope in URDF/SDF/step.parts, drop Implicit CAD, defer SRDF.**

**Issue type:** New requirement (strategic capability expansion), emerged during the Skills-track work — not a technical failure.

**Discovery context.** The 12-skill Track A+B catalog (all parametric-CAD) was authored and shape-verified this session; these five domains have no home in it. Rather than force or silently drop them, feasibility was checked against the FreeCAD source under `docs/references/FreeCAD/`.

**Evidence (source-verified, not asserted):**
- **Native solid inertials** exist on `TopoShapeSolidPy`: `getCenterOfMass`, `getMatrixOfInertia`, `getStaticMoments`, `getPrincipalProperties`, `getMomentOfInertia`, `Mass` (via `GProp`). → supplies URDF/SDF `<inertial>` with no addon.
- **Native Assembly workbench with joints**: `AssemblyObject`, `AssemblyLink`, `AssemblyUtils` (joint handling). → supplies the kinematic link/joint tree URDF/SDF need.
- **Native STEP import**: `ImportOCAF`/`ImportOCAF2`/`ReaderStep`. → supplies off-the-shelf part import.
- **The in-tree `Robot` workbench is NOT a URDF exporter** — it is a 6-axis trajectory/simulation tool (`Robot6Axis`, `PropertyTrajectory`, `Simulation`); **zero `urdf` references**. → URDF/SDF **export is our code** (emit XML from the Assembly tree + native inertials + mesh export, or wrap the external CROSS addon), never a FreeCAD built-in.
- **Implicit CAD** requires an F-rep / signed-distance-field kernel. FreeCAD is OCCT **B-rep**; the project's entire verify stack (AD-6 fingerprint over B-rep shape bytes, AD-9 export/verify pairing, assertion vocabulary) assumes B-rep solids. Kernel mismatch — **out**.
- **SRDF** is MoveIt planning semantics (groups, disabled-collision matrix), normally produced by MoveIt Setup Assistant; no native FreeCAD path. Derives from an exported URDF + external MoveIt — **deferred**.

---

## Section 2 — Impact Analysis

### Epic impact

| Epic | Status | Impact |
| --- | --- | --- |
| Epic 1 (Bridge, G0) | **done** | None. No rollback. New export tools are Phase-5 additions to the same rings, not changes to shipped code. |
| Epics 2–4 (Assistant/Copilot/Designer) | backlog | None. Parametric-CAD scope unchanged. |
| Epic 5 (Autonomous service, G4) | backlog | Minor forward note: the job API's deliverables (`ResultEnvelope`, `JobStatus`, exports) will later include URDF/SDF artifacts. AD-17 schemas already accommodate new export kinds additively; no rework. |
| Epic 6 (Skills, GS) | in progress (this session) | The catalog gains new skills (`urdf-export`, `sdf-export`, `part-sourcing`). GS ablation scope grows from 12 to ~15 skills. |
| **New Epic 7 (Robot-Description Export & Sourcing, Phase 5)** | **to add** | New epic. Sits on/after Assemblies (Phase 5). Delivers `export_urdf`/`export_sdf`/part-import MCP tools + their verify tools + the 3 skills. |

**Epic order/priority:** unchanged for 1–6 (gate-sequential per AD-19). Epic 7 is Phase 5, after Epic 5. Assemblies (already a Phase-5 candidate in intent.md) is a **prerequisite** for URDF/SDF and must be scoped alongside or before Epic 7.

### Artifact conflict analysis

**PRD-equivalent (`docs/intent.md`):**
- Phase 5 "Advanced (exploratory)" lists Assemblies/Drawings/Optimization/Vision/Reverse-tasks. **Add** robot-description export + part sourcing as a named Phase-5 direction. No conflict with Phases 0–4 (untouched). MVP (Phases 0–4) **unaffected** — this is post-MVP.
- Reuse Map: **add** rows — URDF/SDF export (evaluate CROSS addon before hand-rolling XML; wrap not fork per reuse rule), off-the-shelf STEP catalogs (import-only). **Add** an explicit "Implicit CAD — rejected, kernel mismatch" note so it isn't re-litigated.

**Architecture spine (`ARCHITECTURE-SPINE.md`):**
- **AD-15 (skills):** amend catalog — the fixed 12 becomes 12 + 3 Phase-5 skills. (Already amended this session to allow in-body sibling refs; this is a second, separate amendment to the catalog size/tracks.)
- **New AD (robot-description export):** URDF/SDF export is our code emitting XML from the Assembly tree + native inertials; export is done only via a paired verify (re-parse + schema + kinematic sanity) mirroring AD-9's export/verify-pairing discipline; units pinned (meters/kg/radians for URDF/SDF vs the internal mm/deg — an explicit conversion boundary); frame-semantics rigor (every link/joint origin carries a documented reference frame). Binds Phase-5 export tools.
- **New AD (part sourcing/import):** off-the-shelf parts enter only through the `document_*`/import path (never raw `App.open` alongside the bridge, per AD-20); a sourced part's geometry is measured before its mating frames are trusted (imported geometry's origin/orientation not assumed); catalog *search* is external, *placement* is standard bridge flow.
- **Capability→Architecture map & Stack:** add Phase-5 rows; add Assembly workbench + (optional) CROSS to the stack with version pins verified at the Phase-5 gate.
- **Deferred table:** add SRDF (MoveIt-derived, revisit post-URDF); note Implicit CAD as rejected.
- **AD-6/AD-9/AD-11/AD-12/AD-17/AD-18/AD-20/AD-21** — no change; the new tools reuse them (fingerprint still B-rep; new exports get their own verify pairing under the AD-9 pattern; shim owns any version-sensitive Assembly/inertial calls; in-FreeCAD code stays stdlib+FreeCAD; envelopes/status reused; supervisor re-checks apply).

**Design docs:** `mcp-tools-design.md` gains a Phase-5 tool section (`export_urdf`, `export_sdf`, `verify_export_urdf`, `verify_export_sdf`, part-sourcing/import tools). `verification-design.md` gains the URDF/SDF verify legs (re-parse, schema-valid, kinematic-tree sanity, inertial plausibility, mesh-resolves). `skills-structure-design.md` catalog/budget table updated for the new skills. `component-design.md` phase-availability table gains an Epic-7 row.

**UI/UX:** N/A — no UX contract exists yet (deliberate, per epics.md).

**Secondary artifacts:** CI gains an Assembly/robot-export leg (deferred detail, Phase-5 gate); `sprint-status.yaml` gains Epic 7 + Epic 6 skill additions; provenance rules (AD-16) apply to any shipped robot-description fixtures.

---

## Section 3 — Recommended Path Forward

**Selected: Option 1 — Direct Adjustment (additive), hybrid with a new epic.**

- **Not rollback** (Option 2): nothing shipped is wrong; Epic 1 stands.
- **Not MVP review** (Option 3): the MVP (Phases 0–4) is untouched; this is post-MVP expansion.
- **Direct adjustment**: add a new Phase-5 Epic 7 and 3 skills, amend the spine additively (new ADs, stable IDs), update intent.md's Phase 5 + Reuse Map. No existing AD is weakened; no phase 0–4 code changes.

**Rationale:** additive, gate-deferred to Phase 5, reuses the ratified verify-first machinery (export/verify pairing, document lifecycle, shim). Effort concentrated at the Phase-5 gate (real bridge work: Assembly tool exposure, XML emit or CROSS wrap, new verify legs). **Effort: High** (new domain + tools + Assembly dependency). **Risk: Medium** (URDF/SDF export is our code; CROSS-vs-hand-roll and Assembly-Python-exposure are Phase-5-gate spikes). Timeline: no impact on Phases 0–4.

---

## Section 4 — Detailed Change Proposals

Grouped by artifact. All additive; AD IDs stable.

### 4a. Spine — `ARCHITECTURE-SPINE.md`

1. **Amend AD-15 Rule** (catalog size): the fixed catalog is "Track A+B (12) plus Phase-5 additions"; add the robot-description/sourcing skills as a named group. (Second amendment this session; keep AD-15 ID.)
2. **Add AD-22 — Robot-description export (URDF/SDF).** *Binds:* Phase-5 export tools. *Prevents:* an unverified XML dump counted as success; silent unit/frame errors. *Rule:* URDF/SDF are emitted from the Assembly kinematic tree + native solid inertials + mesh export (our code; CROSS evaluated first per reuse rule); every `export_urdf`/`export_sdf` completes only through a paired `verify_export_*` (re-parse, schema-valid, single-root acyclic kinematic tree, joint axes finite/normalized in joint frame, inertials positive/plausible, mesh refs resolve); the mm/deg→m/kg/rad conversion is an explicit pinned boundary, never ambient; every link/joint/inertial origin records its reference frame.
3. **Add AD-23 — Off-the-shelf part sourcing/import.** *Binds:* Phase-5 sourcing tools. *Prevents:* raw imports bypassing the bridge; assuming an imported part's origin. *Rule:* sourced parts enter only via the `document_*`/import path (AD-20); catalog search is external, placement is standard bridge flow; an imported part's mating frames are derived from measured geometry, never assumed; provenance/license recorded per AD-16 for anything shipped.
4. **Stack:** add native Assembly workbench; add CROSS addon (optional, version pinned at Phase-5 gate) as an evaluate-first reuse candidate.
5. **Capability→Architecture map:** add Phase-5 rows (robot export, part sourcing) → governed by AD-22/AD-23 + reused AD-9/AD-17/AD-20.
6. **Deferred table:** add "SRDF (MoveIt-derived; revisit after URDF lands)"; add "Implicit CAD — rejected: OCCT B-rep vs F-rep kernel mismatch."

### 4b. Intent — `docs/intent.md`

7. **Phase 5 section:** add "Robot-description export (URDF/SDF) from parametric assemblies" and "Off-the-shelf part sourcing/import" as named Phase-5 directions (each gets a SMART goal when selected).
8. **Reuse Map:** add rows — URDF/SDF export (CROSS addon evaluate-first; else emit from Assembly tree), STEP part catalogs (import-only), and an explicit Implicit-CAD-rejected note.

### 4c. Design docs

9. `mcp-tools-design.md`: Phase-5 tool section — `export_urdf`, `export_sdf`, `verify_export_urdf`, `verify_export_sdf`, `part_search`/`part_import` (names TBD at Phase-5 design).
10. `verification-design.md`: URDF/SDF verify legs (§ new) under the AD-9 pattern.
11. `skills-structure-design.md`: catalog + token-budget tables include the 3 new skills.
12. `component-design.md`: phase-availability table gains an Epic-7 (P5) row.

### 4d. Epics — `epics.md`

13. **Add Epic 7 — Robot-Description Export & Part Sourcing (Phase 5 · gate G5-robot).** FRs: export URDF from a parametric assembly (links/joints/inertials/meshes, verified by re-parse+schema+kinematic sanity); export SDF likewise; source and import off-the-shelf STEP parts and place them under the bridge. Depends on a Phase-5 **Assemblies** capability (prerequisite — scope alongside).
14. **Epic 6:** add stories 6.7–6.9 for the 3 new skills (authored after the parametric 12; ablated when GS infra exists).

### 4e. Skills — `skills/`

15. Author (user's call on timing — now as ablation-ready drafts, or at Phase 5): `urdf-export`, `sdf-export`, `part-sourcing` — same authoring contract (4 sections, ≤1500 words, MCP-prereq line, no source paths, sibling refs allowed). These reference Phase-5 tools (`export_urdf` etc.) forward-named until built.

### 4f. Memlog

16. Append the scope ruling + FreeCAD-reality constraint + AD-22/AD-23 decisions to the architecture `.memlog.md` (history record).

---

## Section 5 — Implementation Handoff

**Scope: Major** → Product Manager / Solution Architect involvement.

| Change | Owner | When |
| --- | --- | --- |
| Spine amendments (AD-15 catalog; add AD-22, AD-23; Stack/map/Deferred) + memlog | Architect (`bmad-architecture` update) | Now (this session, on approval) |
| intent.md Phase 5 + Reuse Map | Architect / PM | Now |
| epics.md Epic 7 + Epic 6 stories 6.7–6.9 | PM (`bmad-create-epics-and-stories`) | Now / next |
| Design-doc Phase-5 sections | Architect | Phase-5 design gate |
| sprint-status.yaml (Epic 7 + skill stories) | PO/Dev | On approval |
| 3 new skills authored | Dev (skills) | Now as ablation-ready drafts, or at Phase 5 — user's call |
| MCP tools (`export_urdf`/`export_sdf`/part import) + verify legs + Assembly exposure | Dev | Phase-5 implementation (gated) |

**Prerequisite flagged:** URDF/SDF need a Phase-5 **Assemblies** capability (intent.md already flags the `JointObject.py`/Assembly gap). Epic 7 cannot complete before an assembly capability exists. Recommend scoping Assemblies as the first Phase-5 epic, Epic 7 after it.

**Success criteria:** a parametric assembly exports a URDF that re-parses, is schema-valid, has a single acyclic kinematic tree with normalized joint axes and plausible inertials, and whose meshes resolve — proven by `verify_export_urdf`, not by "the file was written." Same for SDF. A named catalog part imports and places under the bridge with measured (not assumed) mating frames.

---

## Deferred / Rejected (recorded so they aren't re-litigated)

- **SRDF** — deferred. No native FreeCAD path; MoveIt planning semantics derive from an exported URDF + external MoveIt Setup Assistant. Revisit if/when URDF lands and MoveIt integration is wanted.
- **Implicit CAD** — rejected. FreeCAD is OCCT B-rep; implicit modeling needs an F-rep/SDF kernel the project has no reason to add and whose outputs the B-rep verify stack can't validate.
