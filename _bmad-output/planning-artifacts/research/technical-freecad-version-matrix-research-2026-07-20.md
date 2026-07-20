---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - docs/intent.md
  - docs/references/FreeCAD (local source, weekly-2026.07.15 / internal v26.3 dev == 1.1 dev line)
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'FreeCAD version support matrix: 0.21 vs 1.x API and TNP divergence'
research_goals: 'Determine concrete Python API differences between FreeCAD 0.21, 1.0, and 1.1 relevant to the FreeCAD Buddy bridge (document/sketcher/partdesign, Assembly, element maps/TNP, VarSet, datums); quantify adapter-layer cost; recommend which versions to pin/support and whether to drop pre-1.0; unblock Phase 0 CI matrix design and Phase 2 TNP guard comparability.'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: technical

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** technical

---

## Research Overview

FreeCAD Buddy's `intent.md` plans a CI matrix "across FreeCAD versions (0.21/1.0+)" and a Phase 2 TNP guard that re-resolves references after every mutation. This research resolves the tension between those two plans: the entire mechanism the TNP guard depends on — the topological-naming **element map** (persistent `MappedName` identities for faces/edges/vertices) — exists **only in FreeCAD 1.0 and later**. FreeCAD 0.21 has no element map, no `getElementHistory`, and no stable `MappedName` API. Supporting 0.21 in the same CI matrix as 1.x therefore does not merely cost a "thin adapter"; it forks the project's core verification premise into two incomparable regimes and makes Phase 2's headline metric ("TNP guard flags all provoking scenarios") unmeasurable on the 0.21 leg.

Evidence is drawn primarily from the local FreeCAD source checked into this repo (`docs/references/FreeCAD`, git `weekly-2026.07.15-122-gfc135718a4`, internal version 26.3 dev — the **1.1 development line**), cross-checked against FreeCAD's official release announcements (1.0 released 2024-11-18; 1.1 released 2026-03-25) and the 1.1 release-notes wiki. The source confirms the element-map machinery (`src/App/ElementMap.*`, `MappedName.*`, `ComplexGeoData.pyi`, `TopoShape.pyi::getElementHistory`), the 1.0 additions the bridge would use (`App::VarSet`, `App::LocalCoordinateSystem`, the integrated `Assembly` workbench), and the one hard breaking rename every macro hits: `Support` → `AttachmentSupport`.

The recommendation, developed in full in the Research Synthesis (Section 8) below: **pin 1.0.x as the floor and make 1.1.x the primary target; drop 0.21 from the mainline support matrix.** Keep 0.21 only as an optional, clearly-labelled "legacy/no-TNP-guard" CI leg if a concrete user need appears — never as a comparability baseline for TNP metrics. See the Executive Summary and Section 8 for the pinning table and adapter-layer scope.

---

# FreeCAD Buddy's Version Floor: Why the TNP Guard Forces a 1.0+ Support Matrix

## Executive Summary

FreeCAD Buddy bets its entire verification story on being able to detect broken topological references after a recompute (`intent.md` Guiding Principles: "TNP awareness"; Phase 2 exit criterion: "after each mutation, all existing feature references re-resolve … the guard flags all of them"). That capability is not a bridge feature we build — it is a **kernel feature that only exists in FreeCAD 1.0+**. The realthunder/Ondsel topological-naming rework shipped as FreeCAD **1.0** on 2024-11-18 (it was significant enough that the release was renumbered from the planned 0.21 successor straight to 1.0). FreeCAD **0.21** predates it entirely: no element map, no persistent `MappedName`, no `getElementHistory`. A "TNP guard" on 0.21 can only fall back to the fragile positional names (`Face6`, `Edge3`) that *are* the topological naming problem — so it cannot be validated against the 1.x guard, and Phase 2's comparability breaks.

The concrete API surface the bridge needs beyond TNP is likewise 1.0-gated: `App::VarSet` (driving-dimension container the intent's `parametric-patterns` skill and Phase 3 "spreadsheet/VarSet of driving dimensions" depend on), the integrated `Assembly` workbench (Phase 5), and `App::LocalCoordinateSystem` all arrive in 1.0. Meanwhile the single most disruptive *breaking* change between 0.21 and 1.0 is small and mechanical — the attachment property `Support` was renamed to `AttachmentSupport` — but it is on the hot path of every datum-attachment and sketch-attachment call the `freecad-datums-references` skill teaches. 1.0 → 1.1 is comparatively benign for scripting: no Python API removals documented, additive Sketcher/PartDesign/Assembly tooling, and a file-format forward-break (1.1 files won't open in 1.0) driven by the new **core datums**.

**Key Technical Findings:**

- **TNP element maps are 1.0+ only.** Verified in local source: `src/App/ElementMap.cpp/.h`, `MappedName.h`, `ComplexGeoData.pyi` (`ElementMap`, `ElementMapVersion`, `getElementName`), `Mod/Part/App/TopoShape.pyi::getElementHistory`, `Mod/Part/App/PartFeature.pyi::getElementHistory(recursive=True)`. None of this exists in 0.21. The bridge's TNP guard is a thin composition **on top of** these APIs — exactly as `intent.md`'s Reuse Map assumes ("FreeCAD 1.x built-in TNP mitigation … our re-resolve guard tooling on top").
- **The one unavoidable breaking rename is `Support` → `AttachmentSupport`** (`src/Mod/Part/App/AttachExtension.cpp` lines 506–519 still carry the migration shim). It affects every datum/sketch attachment. Old files auto-migrate on load; **macros do not** — the bridge must branch on `hasattr(obj, 'AttachmentSupport')`.
- **VarSet, integrated Assembly, and LocalCoordinateSystem are 1.0 additions.** `App::VarSet` (`src/App/VarSet.*`), `Assembly::AssemblyObject` (`src/Mod/Assembly`, Ondsel solver), `App::LocalCoordinateSystem` (`src/App/Datums.*`). All absent in 0.21.
- **1.0 → 1.1 is additive for the bridge.** 1.1 release notes list **no removed/changed Python API of substance**; Sketcher gains `Projection`/`Intersection` external-geometry tools (external geometry now defaults to real, not construction), PartDesign Hole gains Whitworth/BSP threads, Assembly gains `InsertNewPart`/`CreateSimulation` and core-datum joint attachment. New **core datums** cause a one-way file-format break (1.1-created files won't open in 1.0).
- **Assembly has weak Python scripting support in both 1.0 and 1.1.** `Assembly::AssemblyObject` exposes `solve()`, `getJoints()`, etc., but **joint creation is command/GUI-driven** — no clean `addObject('Assembly::Joint', …)`. Phase 5 assembly automation will need a `JointObject.py`-wrapper adapter regardless of version.

**Technical Recommendations:**

1. **Pin the floor at FreeCAD 1.0.x; make 1.1.x the primary/default target.** CI matrix = {1.0.x (latest patch, e.g. 1.0.2), 1.1.x (latest patch), 1.2-dev weekly (allowed-to-fail canary)}. This is a 2-real-version supported matrix, not 3+.
2. **Drop 0.21 from the mainline matrix.** The TNP guard — the project's core trust mechanism — cannot exist on 0.21, so 0.21 can never provide a comparable Phase 2 baseline. Re-scope the `intent.md` risk-row wording from "0.21/1.0+" to "1.0/1.1+".
3. **Build the adapter layer as a small version-shim module, not a compat framework.** Concrete scope is tiny: (a) `Support`/`AttachmentSupport` property accessor; (b) a capability probe (`element_map_available()`) that hard-gates the TNP guard; (c) an `addObject` type-string table (stable across 1.0/1.1); (d) a VarSet/Spreadsheet driving-dimension abstraction. Estimated < 1 file, ~150–250 LOC.
4. **Gate the TNP guard on a runtime capability check, not a version string.** Probe for `Part.TopoShape.getElementHistory` / non-empty `Shape.ElementMap`; if absent, the guard reports `UNSUPPORTED` (never a false "clean"). This keeps Phase 2's "no silent bad output" invariant even if a 0.21 legacy leg is ever added.
5. **Treat Assembly (Phase 5) as needing its own adapter regardless of version** — plan a `JointObject.py`-style wrapper now so Phase 5 scoping isn't surprised by the missing scripting API.

---

## Table of Contents

1. Technical Research Introduction and Methodology
2. FreeCAD Version Landscape and the TNP Divergence
3. Element Maps / TNP: the 1.0+ Capability the Bridge Stands On
4. Version-by-Version Python API Delta (0.21 → 1.0 → 1.1)
5. Bridge-Relevant Feature Matrix (document / sketcher / partdesign / assembly / VarSet / datums)
6. Adapter-Layer Cost Analysis
7. Community Adoption and Version Share
8. Research Synthesis: Version-Pinning Recommendation and CI Matrix Design
9. Risk Assessment and Impact on `intent.md` Phases
10. Research Methodology and Source Verification
11. Appendix: API Reference Tables (with local source paths)

---

## 1. Technical Research Introduction and Methodology

### Technical Research Significance

`intent.md` names version drift as a first-class risk ("FreeCAD version drift (API changes between 0.21/1.0+) → Bridge breakage → Pin supported versions, CI matrix across versions, thin adapter layer over version-sensitive calls") and simultaneously makes TNP mitigation a Guiding Principle and a Phase 2 exit gate. These two commitments collide: the TNP mitigation the guard is built on **is the** defining difference between 0.21 and 1.x. Resolving which versions to pin is therefore not a packaging detail — it decides whether Phase 2's central metric is even well-defined. This blocks Phase 0 (CI matrix design) and Phase 2 (TNP guard comparability), exactly as stated in the task brief.

### Technical Research Methodology

- **Technical Scope:** Python-facing API surface of the FreeCAD bridge — `Document`/`DocumentObject` lifecycle, `Sketcher`, `PartDesign`, `Part`/`TopoShape`, the integrated `Assembly` workbench, element maps / topological naming, `VarSet`, and datum/attachment APIs — across FreeCAD 0.21, 1.0, and 1.1.
- **Data Sources (priority order):**
  1. **Local FreeCAD source** checked into this repo at `docs/references/FreeCAD` — git tag `weekly-2026.07.15-122-gfc135718a4`, `version.json` = major 26 / minor 3 / suffix `dev`, i.e. the **FreeCAD 1.1 development line** (post-1.1.x, heading toward 1.2). This is the authoritative source for *current* API shape and for confirming which APIs exist. Cited by absolute path throughout.
  2. **Official FreeCAD release channels** — `blog.freecad.org` (1.0 released 2024-11-18; 1.1 released 2026-03-25; 1.1.1 2026-04-15), the `FreeCAD-documentation` release-notes wiki for 1.1, and FreeCAD GitHub issues/PRs for the `Support`→`AttachmentSupport` rename (PR #12714) and VarSet exposure (issue #12531).
  3. **Community/adoption signals** — Ondsel user survey, download statistics, forum migration threads.
- **Analysis Framework:** For each bridge-relevant capability, establish (a) does it exist in 0.21? (b) what is the exact Python API name/type-string in 1.x? (c) did it change 1.0 → 1.1? (d) what does the bridge adapter need to do about it?
- **Time Period:** Current as of 2026-07 (FreeCAD 1.1.1 stable is latest release; 1.2 is in weekly dev).
- **Technical Depth:** API-level, with exact `addObject` type strings, property names, and file paths so Phase 0 can implement directly.

### Technical Research Goals and Objectives

**Original Technical Goals:** Determine concrete Python API differences between 0.21/1.0/1.1 relevant to the bridge; quantify what breaks and adapter-layer cost; assess community/version share; recommend which versions to pin/support and whether to drop pre-1.0; unblock Phase 0 CI design and Phase 2 TNP guard comparability.

**Achieved Technical Objectives:**

- Established that the element-map/TNP API is 1.0+ exclusive (verified in local source), which is decisive for the pin recommendation. ✔
- Enumerated the breaking and additive API deltas 0.21→1.0 and 1.0→1.1 with exact names/paths. ✔
- Scoped the adapter layer to a small, concrete shim rather than an open-ended compat framework. ✔
- Produced a defensible CI matrix and pin recommendation with the `intent.md` risk-row rewording. ✔
- Surfaced two second-order findings the intent under-specifies: Assembly's weak scripting API (affects Phase 5) and VarSet's limited external exposure (affects Phase 3 driving-dimension design). ✔

---

## 2. FreeCAD Version Landscape and the TNP Divergence

FreeCAD's release history has one discontinuity that dominates this entire analysis:

| Version | Released | Defining trait for the bridge | Element map / TNP |
|---------|----------|-------------------------------|-------------------|
| **0.21.x** | 2023-08 (0.21.0), last of the 0.x line | Legacy topological naming (positional `Face6`/`Edge3`); `Support` attachment property; no VarSet, no integrated Assembly | **Absent** |
| **1.0.x** | 2024-11-18 | realthunder/Ondsel TNP mitigation merged; `AttachmentSupport` rename; `App::VarSet`; integrated `Assembly`; `App::LocalCoordinateSystem` | **Present** (`ElementMapVersion` schema) |
| **1.1.x** | 2026-03-25 (1.1.0), 1.1.1 2026-04-15 | Additive: Sketcher `Projection`/`Intersection`, core datums, Hole thread standards, Assembly `InsertNewPart`/`CreateSimulation` | Present; core-datum file-format forward break |
| **1.2-dev** | weekly (this repo's checkout, internal v26.3) | Canary only | Present |

The 0.21 → 1.0 jump was renumbered from a planned "0.22" specifically because the TNP rework was too large to be a point release (confirmed in FreeCAD News "Toponaming and 0.21 status update" and the 1.0 announcement). **This is the version boundary that matters.** Everything the bridge does that is "TNP-aware" lives on the 1.0 side of it.

_Sources: https://blog.freecad.org/2024/11/19/freecad-version-1-0-released/ ; https://blog.freecad.org/2026/03/25/freecad-version-1-1-released/ ; https://blog.freecad.org/2023/07/14/toponaming-and-0-21-status-update/ ; local `docs/references/FreeCAD/version.json`._

---

## 3. Element Maps / TNP: the 1.0+ Capability the Bridge Stands On

This is the core finding. The `intent.md` TNP guard ("after each mutation, all existing feature references re-resolve") is a composition over the following kernel APIs — **all introduced with the 1.0 TNP rework, none present in 0.21**. Verified in local source (paths absolute):

| Capability | Local source path | Python API | Note |
|-----------|-------------------|-----------|------|
| Persistent element identity map | `…\src\App\ElementMap.cpp` / `ElementMap.h` | (internal) exposed via `ComplexGeoData` | Stores `MappedName ↔ IndexedName` |
| Mapped name type | `…\src\App\MappedName.h`, `MappedElement.h` | (internal) | The persistent name that survives recompute |
| Element map on any geo data | `…\src\App\ComplexGeoData.pyi` | `ElementMap`, `ElementReverseMap`, `ElementMapVersion`, `ElementMapSize`, `getElementName(name, direction)`, `getElementMappedName()`, `getElementIndexedName()` | `TopoShape` inherits `ComplexGeoData` |
| Resolve element → subshape | `…\src\Mod\Part\App\TopoShape.pyi` | `getElement(name, silent=False)` | Raises / returns None on broken ref |
| Trace element lineage | `…\src\Mod\Part\App\TopoShape.pyi` | `getElementHistory(name)` → `(sourceTag, sourceName, [intermediates])` or None | The audit primitive the guard uses |
| Recursive cross-object history | `…\src\Mod\Part\App\PartFeature.pyi` | `getElementHistory(name, recursive=True, sameType=False, showName=False)` | Traces a reference through the feature tree |
| Broken-reference markers | `…\src\App\ElementNamingUtils.h` | prefixes: `;` (mapped), `?` (**missing/broken**), history postfixes `;:H ;:T ;:X ;:C ;:M ;:G` | `?`-prefixed name == broken reference signal |
| Schema versioning | `…\src\App\ComplexGeoData.pyi` | `ElementMapVersion` | Bumped when the naming algorithm changes — the guard should record it |

**Implications for the bridge:**

- The TNP guard is genuinely a *thin* layer, exactly as the Reuse Map predicts — it calls `getElementHistory` / inspects `Shape.ElementMap` and flags `?`-prefixed or unresolvable names. This confirms `intent.md`'s "our re-resolve guard tooling on top" is correctly scoped as invention-light.
- On **0.21 there is nothing to compose over.** A 0.21 "guard" would inspect raw positional names (`Face6`) whose meaning silently shifts on recompute — i.e. it would exhibit precisely the failure the guard is meant to catch, and could not distinguish "reference intact" from "reference now points at a different face." Phase 2's fault-injection sensitivity target (≥95%) is unattainable on 0.21.
- **`ElementMapVersion` should be captured in the TNP guard's report** so that a future 1.x algorithm bump (which happened once already inside the 1.x line) is visible rather than silently changing comparability.

_Source: local FreeCAD source (paths above); realthunder Topological Naming Algorithm wiki https://github.com/realthunder/FreeCAD_assembly3/wiki/Topological-Naming-Algorithm ._

---

## 4. Version-by-Version Python API Delta (0.21 → 1.0 → 1.1)

### 4.1 The one breaking rename that touches everything: `Support` → `AttachmentSupport`

The attachment property carried by every datum and every attached sketch was renamed from `Support` to `AttachmentSupport` in the 1.0 line (PR #12714, to avoid a name clash with base-feature properties like ShapeBinder's). The migration shim is still visible in the current source:

`…\src\Mod\Part\App\AttachExtension.cpp` (lines 506–519): `// Support -> AttachmentSupport` … `if (strcmp(PropName, "Support") == 0) { … AttachmentSupport.setValue(...) }`.

- **Files** created in 0.21 auto-migrate on open. **Macros/scripts do not.** A bridge that writes `obj.Support = [...]` works on 0.21 and **throws on 1.x**; `obj.AttachmentSupport = [...]` works on 1.x and **throws on 0.21**.
- This is the single highest-frequency version-sensitive call in the bridge (every `feature.attach*`, every datum placement, `freecad-datums-references` skill examples). It **must** be behind an adapter accessor.

### 4.2 Additive in 1.0 (absent in 0.21) — all bridge-relevant

| Feature | Type string / API | Local source | Bridge use in intent |
|---------|-------------------|--------------|----------------------|
| Variable set | `doc.addObject('App::VarSet', name)` + `.addProperty(...)` | `…\src\App\VarSet.cpp/.h` | Phase 3 "spreadsheet/VarSet of driving dimensions"; `parametric-patterns` skill |
| Integrated Assembly | `addObject('Assembly::AssemblyObject', …)`; `solve()`, `getJoints()` | `…\src\Mod\Assembly` (Ondsel/`MbD` solver) | Phase 5 assemblies |
| Local coordinate system | `addObject('App::LocalCoordinateSystem', …)`; `getOrigin()/getX()/…` | `…\src\App\Datums.cpp/.h` | `freecad-datums-references`, datum-based referencing (TNP defense) |
| App-level datums | `App::Plane` / `App::Line` / `App::Point` (as `DatumElement`) | `…\src\App\Datums.*` | Datum-based referencing |

### 4.3 Delta 1.0 → 1.1 (from release notes + source): additive, low-risk for scripting

- **No removed or substantively changed Python API** documented in the 1.1 release notes (the "Removed/Changed Python API" sections are effectively empty of bridge-affecting items).
- **Sketcher:** new `Sketcher_Projection` and `Sketcher_Intersection` external-geometry tools; **external geometry now defaults to real (defining) geometry, not construction** — a behavioral default the `freecad-sketcher` skill and any external-reference logic must note (affects DoF/what counts as profile geometry). Group dragging added.
- **PartDesign:** Hole tool gains Whitworth/BSP/NPT thread standards; Internal Face Generator; `Std_ToggleFreeze` available. Origin features now use **core datums** → **files saved by 1.1 will not open in 1.0** (one-way forward break); this is a *file-format* concern, not an API-break, but it matters for round-trip tests that share fixtures across the CI matrix.
- **Assembly:** `Assembly_InsertNewPart`, `Assembly_CreateSimulation`; core datums usable as joint attachments. Still command-centric (see §5.4).
- **Toolchain:** no Python/Qt/OCCT minimum-version bump called out in the 1.1 notes.

_Sources: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Release_notes_1.1.md ; https://github.com/FreeCAD/FreeCAD/pull/12714 ; local source paths above._

---

## 5. Bridge-Relevant Feature Matrix

Legend: ✅ present & stable · ⚠️ present but caveated · ❌ absent · ↔ unchanged across 1.0/1.1.

| Bridge capability | 0.21 | 1.0 | 1.1 | Version-sensitive call the bridge makes |
|-------------------|:----:|:---:|:---:|------------------------------------------|
| **document.* / DocumentObject lifecycle** (`newDocument`, `addObject`, `recompute`) | ✅ | ✅ | ✅ ↔ | none — stable across all three |
| **Sketcher core** (`Sketcher::SketchObject`, `addGeometry`, `addConstraint`, `Constraint(...)`) | ✅ | ✅ | ✅ (+external-geo tools) | none for core; note 1.1 external-geo default change |
| **PartDesign features** (`PartDesign::Body/Pad/Pocket/Revolution/Fillet/Chamfer/Hole`, `.Profile`, `.BaseFeature`) | ✅ | ✅ | ✅ ↔ (+Hole threads) | type strings stable |
| **Part / TopoShape geometry queries** (`Volume`, `BoundBox`, `isValid`, `check`) | ✅ | ✅ | ✅ ↔ | none — the `verify.shape` core is version-stable |
| **Element map / TNP** (`ElementMap`, `getElementHistory`, mapped names) | ❌ | ✅ | ✅ ↔ | **guard must be capability-gated** |
| **Attachment property** (`Support` vs `AttachmentSupport`) | `Support` | `AttachmentSupport` | `AttachmentSupport` | **breaking rename — adapter accessor required** |
| **VarSet** (`App::VarSet`) | ❌ | ⚠️ (limited external exposure, issue #12531) | ⚠️ | driving-dimension abstraction; fall back to Spreadsheet |
| **LocalCoordinateSystem / core datums** | ❌ | ✅ | ✅ (reworked core datums; file forward-break) | datum-based referencing |
| **Integrated Assembly** (`Assembly::AssemblyObject`) | ❌ | ⚠️ weak scripting | ⚠️ weak scripting | Phase 5 needs `JointObject.py` wrapper adapter |

### 5.4 Assembly's weak Python API (both 1.0 and 1.1)

`Assembly::AssemblyObject` exposes solver-side methods (`solve(enableUndo=False)`, `getJoints()`, `isPartConnected()`, `exportAsASMT()`), but **joint *creation* is driven through GUI commands / the `JointObject.py` FeaturePython wrapper**, not a clean `addObject('Assembly::Joint', …)` factory. 13 joint types exist (Fixed, Revolute, Cylindrical, Slider, Ball, Distance, Parallel, Perpendicular, Angle, RackPinion, Screw, Gears, Belt). **Consequence:** Phase 5 assembly automation needs its own wrapper regardless of the version pinned — this is a scripting-maturity gap in FreeCAD itself, not a version-selection problem, and should be flagged in Phase 5 scoping now.

_Source: local `…\src\Mod\Assembly` (`AssemblyObjectPyImp.cpp`, `JointObject.py`, `CommandCreateAssembly.py`)._

---

## 6. Adapter-Layer Cost Analysis

`intent.md` budgets a "thin adapter layer over version-sensitive calls." This research confirms that budget is correct **if and only if** the matrix is 1.0/1.1 (two close versions). Concrete scope:

| Adapter concern | What it does | Effort |
|-----------------|--------------|--------|
| **Attachment property** | `set_attachment(obj, refs)` / `get_attachment(obj)` that picks `AttachmentSupport` (1.x) — and `Support` only if a 0.21 leg is ever added | ~20 LOC |
| **Element-map capability probe** | `element_map_available(shape) -> bool` via `hasattr(shape, 'getElementHistory')` + non-empty `ElementMap`; **hard-gates the TNP guard** | ~15 LOC |
| **TNP guard core** | Inspect `getElementHistory` / flag `?`-prefixed & unresolvable names; record `ElementMapVersion` | (Phase 2 feature, not adapter) |
| **addObject type-string table** | Central map of `PartDesign::Pad` etc.; stable across 1.0/1.1 so this is mostly documentation/constants | ~40 LOC |
| **Driving-dimension abstraction** | `driving_dimensions` façade over `App::VarSet` (preferred) with **Spreadsheet fallback** (VarSet external-exposure is limited per issue #12531) | ~60 LOC |
| **Version/capability banner** | Report FreeCAD version + `ElementMapVersion` + capability flags in every job's validation report | ~20 LOC |

**Total ≈ 150–250 LOC, one module.** This holds for a **1.0/1.1** matrix. Adding a **0.21** leg roughly triples the conceptual cost (not the LOC): the TNP guard, VarSet, LocalCoordinateSystem, and integrated Assembly all become "unsupported on this leg," so the 0.21 leg runs a **strictly smaller, non-comparable** capability set — a second product, not a config flag. The adapter can express "0.21 = TNP guard UNSUPPORTED," but the *test harness and metrics* cannot meaningfully compare a leg with no element map against a leg with one.

---

## 7. Community Adoption and Version Share

- FreeCAD 1.0 was a watershed: ~20M GitHub downloads by end-2025, ~200% search-interest growth 2020→2025; 1.0 is broadly credited as the release that made FreeCAD "professionally adoptable" precisely because it fixed TNP. New users overwhelmingly land on 1.0/1.1.
- No authoritative public survey breaks down 0.21-vs-1.0 *installed* share by percentage (Ondsel's 650-respondent survey predates or doesn't segment cleanly on this). The signal is directional but strong: **the community and all upstream momentum are on the 1.x line**; 0.21 is legacy and receives no new feature work.
- FreeCAD's own release cadence (1.0 → 1.1 in ~16 months, 1.2 already in weekly dev) means engineering effort spent chasing 0.21 compatibility is spent tracking a frozen, declining base.
- Practical inference for a *new* project starting in 2026: there is no adoption argument for a 0.21 floor. Any user still on 0.21 can install 1.1 (it is a free, packaged upgrade with automatic file migration).

_Sources: https://en.wikipedia.org/wiki/FreeCAD ; https://www.ondsel.com/blog/freecad-user-survey-results-part-1/ ; https://blog.freecad.org/2025/08/06/freecad-1-0-2-released/ ._

---

## 8. Research Synthesis: Version-Pinning Recommendation and CI Matrix Design

### 8.1 Recommendation

> **Pin FreeCAD 1.0.x as the hard floor. Make 1.1.x the primary/default target. Drop 0.21 from the mainline support matrix.**

Rationale chain: the project's central trust mechanism (verify-first + TNP guard) is *defined* by a kernel capability that exists only at 1.0+. Supporting 0.21 does not extend reach cheaply; it forks the verification premise and makes Phase 2's headline metric unmeasurable on one leg. The adoption data gives no countervailing reason to hold a 0.21 floor. Therefore 0.21 is out; 1.0 is the floor because it is the first version with element maps, VarSet, integrated Assembly, and LocalCoordinateSystem — the full set the intent's phases and skills assume.

### 8.2 CI Matrix (Phase 0)

| Leg | Version | Role | Gating |
|-----|---------|------|--------|
| 1 | **1.1.x** (latest patch, e.g. 1.1.1) | **Primary** — default dev + full benchmark suite | Blocking |
| 2 | **1.0.x** (latest patch, e.g. 1.0.2) | **Floor** — full suite, guarantees the pinned minimum works | Blocking |
| 3 | **1.2-dev weekly** (this repo's checkout line) | Canary — early warning on upstream breakage | **Allowed-to-fail** |
| (opt) | 0.21.x | *Only if* a concrete paying/user need appears | Non-blocking, TNP-guard = `UNSUPPORTED`, clearly labelled "legacy/no-TNP" |

- Use conda-forge / official AppImage pins per leg (matches `intent.md` Reuse Map "Community Docker images / conda-forge / AppImage").
- **Do not share round-trip fixture files across the 1.0 and 1.1 legs blindly** — 1.1 core-datum files won't open in 1.0. Generate fixtures per-leg or keep them 1.0-authored (forward-compatible into 1.1).

### 8.3 `intent.md` edits this unblocks

- **Risks table, version-drift row:** change "API changes between 0.21/1.0+" → **"API changes across 1.0 / 1.1+"**; change mitigation "CI matrix across versions" → "CI matrix across 1.0.x (floor) and 1.1.x (primary) + 1.2-dev canary."
- **Phase 0 CI:** the "≥30 tests headless on every push" suite runs on legs 1+2 (blocking) and leg 3 (canary).
- **Phase 2 TNP guard:** its comparability baseline is now unambiguous — both blocking legs have element maps, so the "guard flags all 5 TNP-provoking scenarios" criterion is measurable identically on 1.0 and 1.1. Gate the guard on the runtime capability probe (§6) so it degrades to `UNSUPPORTED` (never false-clean) if ever run elsewhere.

### 8.4 What stays version-agnostic (good news)

The bulk of Phase 0/1 tooling — `document.*`, `query.*` geometry (`Volume`/`BoundBox`/`isValid`/`check`), Sketcher core, PartDesign feature type-strings, STEP/STL export — is **stable across 1.0/1.1** and needs no adapter. The version-sensitivity is concentrated in exactly the five items in §6.

---

## 9. Risk Assessment and Impact on `intent.md` Phases

| Risk | Likelihood | Impact | Mitigation (this research) |
|------|:----------:|--------|----------------------------|
| Attempting 0.21 comparability silently degrades Phase 2 TNP metrics | High if 0.21 kept | Phase-2 exit criteria become meaningless on one leg | Drop 0.21 from mainline; capability-gate the guard |
| `Support`/`AttachmentSupport` divergence crashes the bridge on a leg | High without adapter | Every datum/sketch attachment call | Single adapter accessor (§6) |
| 1.1 core-datum file forward-break corrupts shared CI fixtures | Medium | Round-trip tests fail spuriously across legs | Author fixtures on 1.0 (forward-compatible) or per-leg |
| VarSet external-exposure limits Phase 3 driving-dimension design | Medium | Parametric API less clean than hoped (issue #12531) | Spreadsheet fallback in the driving-dimension abstraction |
| Assembly has no clean joint-creation scripting API | High (both 1.0/1.1) | Phase 5 assembly automation harder than intent implies | Flag now; plan `JointObject.py` wrapper adapter in Phase 5 scoping |
| 1.2 upstream introduces a real API break | Medium (dev line) | Future breakage | Canary leg (allowed-to-fail) gives early warning |

---

## 10. Research Methodology and Source Verification

### Primary sources (highest confidence)

- **Local FreeCAD source**, `docs/references/FreeCAD`, git `weekly-2026.07.15-122-gfc135718a4`, `version.json` v26.3 dev (1.1 dev line). Used to *confirm existence and exact shape* of every API cited. Key files: `src/App/{ElementMap,MappedName,MappedElement,ComplexGeoData,VarSet,Datums,ElementNamingUtils}.*`, `src/Mod/Part/App/{TopoShape,PartFeature,AttachExtension}.*`, `src/Mod/{Sketcher,PartDesign,Assembly}`.
- **FreeCAD official release announcements & docs:** 1.0 (2024-11-18), 1.1 (2026-03-25), 1.1.1 (2026-04-15), and the 1.1 release-notes wiki.
- **FreeCAD GitHub:** PR #12714 (`Support`→`AttachmentSupport`), issue #12531 (VarSet exposure), toponaming status blog (2023-07-14).

### Confidence levels

- **High:** existence/absence of element maps, VarSet, integrated Assembly, LocalCoordinateSystem per version; the `Support`→`AttachmentSupport` rename; 1.0/1.1 release dates. (Verified in source and/or official docs.)
- **Medium:** exact 0.21 behavior of specific calls (inferred from source migration shims + release history rather than a 0.21 checkout on hand); precise adapter LOC estimate (engineering judgment).
- **Directional (not precise):** version-share percentages (no authoritative segmented survey found).

### Limitations / further investigation

- No 0.21 source checkout was inspected directly; 0.21 claims rest on the current source's backward-compat shims and official release history. If a 0.21 leg is ever seriously considered, check out 0.21.2 and confirm the absence of `getElementHistory`/`ElementMap` empirically.
- VarSet's external-exposure resolution status (issue #12531) was not confirmed closed for 1.1 — treat the Spreadsheet fallback as the safe default until verified against a 1.1 runtime.

### Search queries used

`FreeCAD 1.0 release date topological naming element maps realthunder 0.21` · `FreeCAD 1.1 release notes changelog new features 2025 2026` · `FreeCAD 0.21 vs 1.0 Python API breaking changes Support AttachmentSupport VarSet` · `FreeCAD version usage share survey 2025 0.21 vs 1.0 adoption`; plus local-source greps for `ElementMapVersion`, `AttachmentSupport`, `VarSet`, `getElementHistory`.

---

## 11. Appendix: API Reference Tables (with local source paths)

### 11.1 Element-map / TNP API (1.0+ only)

| Python API | Local source | Returns / note |
|-----------|--------------|----------------|
| `Shape.ElementMap` | `src/App/ComplexGeoData.pyi` | `dict[mappedName → indexedName]` |
| `Shape.ElementMapVersion` | `src/App/ComplexGeoData.pyi` | schema version string |
| `Shape.getElementName(name, direction)` | `src/App/ComplexGeoData.pyi` | mapped ↔ indexed |
| `TopoShape.getElement(name, silent=False)` | `src/Mod/Part/App/TopoShape.pyi` | subshape / None (broken ref) |
| `TopoShape.getElementHistory(name)` | `src/Mod/Part/App/TopoShape.pyi` | `(tag, sourceName, [intermediates])` / None |
| `PartFeature.getElementHistory(name, recursive=True,…)` | `src/Mod/Part/App/PartFeature.pyi` | cross-object lineage |
| broken-ref marker `?`, mapped `;`, history `;:H/;:T/;:X/;:C/;:M/;:G` | `src/App/ElementNamingUtils.h` | name-prefix semantics |

### 11.2 Bridge object type-strings (stable across 1.0/1.1)

`Sketcher::SketchObject` · `PartDesign::Body` · `PartDesign::Pad` · `PartDesign::Pocket` · `PartDesign::Revolution` · `PartDesign::Groove` · `PartDesign::Fillet` · `PartDesign::Chamfer` · `PartDesign::Hole` · `PartDesign::LinearPattern` · `PartDesign::PolarPattern` · `PartDesign::Mirrored` · `PartDesign::Plane/Line/Point/CoordinateSystem` · `App::VarSet` · `App::LocalCoordinateSystem` · `App::Plane/Line/Point` · `Assembly::AssemblyObject`. (Source: `src/Mod/PartDesign`, `src/Mod/Sketcher`, `src/App`, `src/Mod/Assembly`.)

### 11.3 Version-sensitive calls the adapter must own

1. Attachment: `AttachmentSupport` (1.x) / `Support` (0.21) — `src/Mod/Part/App/AttachExtension.cpp:506–519`.
2. TNP guard capability gate: `getElementHistory` / `ElementMap` presence.
3. Driving dimensions: `App::VarSet` (1.x, limited exposure) with Spreadsheet fallback.
4. Assembly joint creation: `JointObject.py` wrapper (both 1.0/1.1) — no clean factory.

---

## Technical Research Conclusion

### Summary of Key Technical Findings

The 0.21 → 1.0 boundary is not a normal version bump the bridge can span with a thin shim — it is the boundary at which the project's core verification capability (topological element maps) comes into existence. Every TNP-aware behavior in `intent.md` is a composition over 1.0+ kernel APIs verified present in the local source and absent in 0.21. The 1.0 → 1.1 delta, by contrast, is additive and low-risk for scripting, with one mechanical breaking rename (`Support`→`AttachmentSupport`) already handled by a tiny adapter accessor.

### Strategic Technical Impact Assessment

Pinning **1.0.x floor / 1.1.x primary** and dropping 0.21 keeps the adapter layer at the ~150–250 LOC the intent budgeted, makes Phase 2's TNP metrics well-defined and comparable across both blocking CI legs, and aligns the project with where the entire FreeCAD community and upstream momentum already are. Two under-specified items surfaced for downstream planning: Assembly's weak scripting API (Phase 5) and VarSet's limited exposure (Phase 3).

### Next Steps Technical Recommendations

1. Update `intent.md` risk-row and Phase-0 CI wording per §8.3.
2. Implement the version-shim module (§6) as the first Phase-0 utility, with the element-map capability probe gating the Phase-2 TNP guard.
3. Author CI legs 1.1.x (primary) + 1.0.x (floor) blocking, 1.2-dev canary allowed-to-fail; generate round-trip fixtures 1.0-authored.
4. Add `ElementMapVersion` + FreeCAD version to every validation report banner.
5. Flag Assembly scripting-maturity gap in Phase 5 scoping.

---

**Technical Research Completion Date:** 2026-07-20
**Research Period:** current comprehensive technical analysis (FreeCAD 1.1.1 stable / 1.2 weekly)
**Source Verification:** primary = local FreeCAD source (v26.3 dev); secondary = FreeCAD official releases/docs, GitHub PRs/issues
**Technical Confidence Level:** High for API existence/absence and version boundaries; directional for adoption share

_This document is the deliverable for the FreeCAD version support-matrix research and unblocks Phase 0 CI design and Phase 2 TNP-guard comparability._
