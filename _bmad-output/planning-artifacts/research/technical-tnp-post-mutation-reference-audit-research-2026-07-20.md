---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: ['docs/intent.md', 'docs/references/FreeCAD/src']
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'Topological Naming Problem (TNP): automated post-mutation reference audit in FreeCAD 1.x'
research_goals: "Assess feasibility of docs/intent.md's flagship TNP guard — after every mutation, verify all existing feature references still resolve. Map FreeCAD 1.x element-map internals, the APIs to enumerate references (sketch external geometry, feature attachments, expressions) and to detect broken/re-mapped references after recompute; conclude whether the guard is implementable as specified and sketch the mechanism. Blocks Phase 2 exit criteria."
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical — TNP Post-Mutation Reference Audit in FreeCAD 1.x

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** Technical (deep dive)
**Blocks:** Phase 2 exit criteria (`docs/intent.md`) — "TNP guard: after each mutation, all existing feature references re-resolve; benchmark includes 5 TNP-provoking scenarios and the guard flags all of them."

---

## Research Overview

`docs/intent.md` lists the **automated post-mutation reference audit** (the "TNP guard") as one of five *genuine inventions* (Reuse Map, final row): *"FreeCAD 1.x built-in TNP mitigation; datum-based modeling practice … Our re-resolve guard tooling on top — the automated post-mutation reference audit appears not to exist."* This report answers the feasibility question decisively against the **actual FreeCAD source** shipped in the repo (`docs/references/FreeCAD/src`, internal version **26.3.0-dev ≈ FreeCAD 1.1-dev**, which contains the toponaming mitigation fully merged into mainline), cross-checked against realthunder / Ondsel primary documentation.

**Methodology.** Evidence was gathered in priority order: (1) direct reading and grepping of the local FreeCAD C++/`.pyi` source — the decisive source; (2) targeted web corroboration of the FreeCAD 1.0 toponaming design (realthunder wiki, Ondsel milestone blogs). Every mechanism claim below is anchored to a concrete class/method and file path so it can be re-verified and turned directly into bridge code.

**Bottom line (stated up front).** The guard is **implementable exactly as specified in Phase 2**, and more cheaply than the intent doc assumes. FreeCAD 1.1 already does most of the work internally: after a recompute it (a) re-resolves every stored subelement reference through the element map, (b) sets an explicit **`Missing`** flag / **`?`** name-prefix on references it could not re-resolve, and (c) marks the owning object with an **`Error`** status whose description is retrievable per-object. The novel part — and it *is* novel — is a **thin, uniform audit layer** that snapshots references before a mutation, enumerates them across all three reference-holding subsystems after recompute, and reports a structured pass/fail per reference. All required primitives are exposed to Python and therefore reachable from the bridge with **no C++ changes**.

---

## 1. Background: what "TNP" means in FreeCAD 1.1 and why it changes the guard

The Topological Naming Problem is that OCCT (the geometry kernel) assigns face/edge/vertex identifiers (`Edge3`, `Face5`) by iteration order, which is **not stable across recompute**. A feature that stored "fillet Edge5" can silently fillet a *different* edge — or fail — after an upstream sketch edit renumbers the topology.

FreeCAD 1.0/1.1 mitigates this with realthunder's **element map**: alongside the raw indexed name, each element gets a **mapped name** — a hashed string derived from the element's *construction history* (e.g. `;g1v2;SKT;:H1:8,E`), which is designed to remain stable across recomputes because it encodes *how* the element was made rather than *where* it landed in the iteration order. Corroborated by realthunder's algorithm wiki and Ondsel's phase-2 milestone writeup; the exact classes named there (`IndexedName`, `MappedName`, `MappedElement`, `ElementMap`) are all present locally:

- `docs/references/FreeCAD/src/App/IndexedName.h` / `.cpp`
- `docs/references/FreeCAD/src/App/MappedName.h` (referenced by `MappedElement`)
- `docs/references/FreeCAD/src/App/MappedElement.h` / `.cpp`
- `docs/references/FreeCAD/src/App/ElementMap.h` / `.cpp`
- `docs/references/FreeCAD/src/App/ElementNamingUtils.h` / `.cpp`
- `docs/references/FreeCAD/src/App/StringHasher.h` / `.cpp`

**Consequence for the guard, and for the intent doc's Guiding Principle.** The intent doc says *"reference by datum planes/named features where possible, verify references after every recompute."* The datum-preference is still sound guidance (Track A skill `freecad-datums-references`), but the element map means **face/edge references are now auditable too** — the mapped name gives us a stable key to check against, and FreeCAD itself flags when a mapped name fails to re-resolve. The guard therefore does not need to *reimplement* stability detection; it needs to *harvest* the signals FreeCAD already produces.

---

## 2. How references are stored (the three subsystems the guard must cover)

Every "feature reference" that TNP can break is, under the hood, an `App::PropertyLink*` variant that stores an object pointer plus subelement name strings, with a **shadow** copy holding the mapped/indexed name pair. This uniformity is the single most important finding: **one audit strategy covers all three subsystems.**

### 2.1 The shared storage primitive: PropertyLinkSub / PropertyLinkSubList + "shadow"

- `docs/references/FreeCAD/src/App/PropertyLinks.h` / `.cpp`
- `docs/references/FreeCAD/src/App/ElementNamingUtils.h`

Each linked subelement is stored **twice**: the user-facing subname string (`_lSubList`) *and* a `ShadowSub` (`= ElementNamePair`, a struct of `{ std::string newName; std::string oldName; }` — `ElementNamingUtils.h:14-35`). `newName` is the mapped name (leading `;`, `ELEMENT_MAP_PREFIX`); `oldName` is the indexed name (`Edge3`). Accessors: `PropertyLinkSubList::getShadowSubs()` (`PropertyLinks.h:1140`), `PropertyLinkSub::getShadowSub()`.

The core re-resolution routine is **`PropertyLinkBase::_updateElementReference(...)`** (`PropertyLinks.cpp:421-540`). On recompute it:
1. Resolves the element via `GeoFeature::resolveElement(...)` (`PropertyLinks.cpp:444`).
2. If resolution fails or the element name is empty → keeps the old name and **returns false** (reference broken) (`PropertyLinks.cpp:452-456`).
3. Detects a missing element via `GeoFeature::hasMissingElement(oldName)` and attempts geometry-based recovery through `geo->searchElementCache(...)` (`PropertyLinks.cpp:473-504`).
4. If recovery fails, logs `FC_WARN` and stores the broken `oldName` prefixed as missing (`PropertyLinks.cpp:518-531`).
5. `PropertyLinkSub::referenceChanged()` returns true when a mapping was updated (`PropertyLinks.cpp:1634`) — i.e. a reference *silently re-pointed* (the dangerous, non-error case).

**Missing-element marker.** `ElementNamingUtils`: `MISSING_PREFIX = "?"`; `Data::hasMissingElement(subname)` returns true when the (last dotted segment of the) subname starts with `?` (`ElementNamingUtils.cpp:101-111`). This `?Edge5` marker is the **primary machine-checkable broken-reference signal** and it appears uniformly across all three subsystems.

### 2.2 Sketcher external geometry

- `docs/references/FreeCAD/src/Mod/Sketcher/App/SketchObject.h` — `App::PropertyLinkSubList ExternalGeometry` (`:103`), `Part::PropertyGeometryList ExternalGeo` (`:106`, the projected copies).
- `docs/references/FreeCAD/src/Mod/Sketcher/App/ExternalGeometryExtension.h` — per-external-geometry **`Flag`** enum (`:75-84`): `Defining`, `Frozen`, `Detached`, **`Missing`**, `Sync`.
- `docs/references/FreeCAD/src/Mod/Sketcher/App/SketchObjectExternal.cpp` — `rebuildExternalGeometry()` (`:2297`) re-resolves each reference; the detection loop (`:2685-2700`) sets **`ExternalGeometryExtension::Missing`** and `FC_ERR("... missing reference: ...")` when a stored ref is not in the current ref set, and **throws `Base::RuntimeError("Missing external geometry reference")`** (`:2727`) → the SketchObject enters `Error` state on recompute.
- **Report-out API:** `getGeometryReference(GeoId)` returns the ref string prefixed with `"? "` when the `Missing` flag is set (`SketchObjectExternal.cpp:2921-2953`).
- **Auto-repair (already built):** `fixExternalGeometry()` (`:2750-2800`) searches related elements via `Part::Feature::getRelatedElements(...)` and rewrites the ref to the element-map form.

### 2.3 Attachment (datum planes/LCS) and PartDesign features

- Attachment: `docs/references/FreeCAD/src/Mod/Part/App/AttachExtension.h` — `App::PropertyLinkSubList AttachmentSupport` (`:92-95`). `AttachEngine` holds parallel `subnames` (old) + `shadowSubs` (mapped) (`Attacher.h:415-418`).
  - `docs/references/FreeCAD/src/Mod/Part/App/Attacher.cpp`: `extractSubShape(...)` throws `AttachEngineException("... subshape not found ...")` when a subname no longer resolves (`:1012-1073`); `verifyReferencesAreSafe(...)` throws when a linked object was deleted (`:1093-1110`); `calculateAttachedPlacement(...)` checks `Data::hasMissingElement(sub)` and attempts `Part::Feature::getRelatedElements()` recovery (`:1135-1204`).
  - `docs/references/FreeCAD/src/Mod/Part/App/AttachExtension.cpp`: `positionBySupport()` (`:347-404`) catches and **re-throws** on failure → object `Error`.
- PartDesign profile/dressup: `docs/references/FreeCAD/src/Mod/PartDesign/App/FeatureSketchBased.h` — `PropertyLinkSub Profile` (`:55-65`); `FeatureDressUp.h` — `PropertyLinkSub Base` for fillet/chamfer edges (`:45-46`).
  - **Caveat (found, must be tested in the guard's fault-injection suite):** `FeatureDressUp::getContinuousEdges(...)` (`FeatureDressUp.cpp:114-189`) **silently drops** an edge from `SubNames` when it no longer has exactly two adjacent faces (`:143-144`) — i.e. a dress-up can *lose* an edge without erroring. This is exactly the "operation runs without error but produces wrong geometry" self-deception mode the intent doc's Phase-2 threat list warns about. The guard must therefore also compare **reference counts / mapped-name sets before vs after**, not only rely on `Error` status.

### 2.4 Expression engine

- `docs/references/FreeCAD/src/App/ObjectIdentifier.h` / `.cpp` — `ObjectIdentifier` stores `documentObjectName`, `subObjectName`, a `components` path, and its own `ElementNamePair shadowSub` (`:1570`). `ResolveResults` (`:1443-1479`) + **`resolveErrorString()`** (`ObjectIdentifier.cpp:1924-1959`) produce a human-readable reason ("Document object '…' not found", "Property '…' not found").
- `docs/references/FreeCAD/src/App/Expression.cpp` — `VariableExpression::getProperty()` throws `Expression::Exception(var.resolveErrorString())` when unresolved (`:2890-2898`); `Expression::getDeps()` / `getDepObjects()` enumerate dependencies (`:926-976`).
- `docs/references/FreeCAD/src/App/PropertyExpressionEngine.cpp` — `execute()` (`:638-768`) evaluates in dependency order and propagates the exception to `Document::_recomputeFeature()`; `depsAreTouched()` (`:795-804`).

---

## 3. How FreeCAD detects and reports broken references after recompute

The recompute pipeline already aggregates every per-subsystem signal into two document-level surfaces the guard can read directly.

**Recompute + error log.**
- `docs/references/FreeCAD/src/App/Document.cpp` — `recompute()` (`:2825-2944`) topo-sorts and recomputes; `_recomputeFeature()` (`:3234-3289`) wraps each feature's `ExpressionEngine.execute()` + `recompute()` in try/catch, and on any `Base::Exception` calls `addRecomputeLog(e.what(), Feat)` and returns error (`:3263`), otherwise `Feat->resetError()` (`:3280`). The per-object error text is retrievable via `findRecomputeLog(Obj)` (`:3230`).

**Per-object status (the queryable result).**
- `docs/references/FreeCAD/src/App/DocumentObject.h` — `ObjectStatus` enum (`Touch`, `Error`, `Recompute`, `Enforce`, …); `isError()` (`:361`), `isValid()` (`:367`), `isTouched()`, `purgeTouched()`.
- `docs/references/FreeCAD/src/App/DocumentObject.cpp` — **`getStatusString()`** (`:312-327`) returns, in order of precedence, `getDocument()->getErrorDescription(this)` when `isError()`, else `"Freezed"`, `"Touched"`, or `"Valid"`. **This is the single call that yields the per-object, human-readable failure reason the guard reports.**

**Enumerating failures after a mutation** is therefore: `doc.recompute()`, then iterate `doc.Objects` and collect any with `not obj.isValid()` plus its `getStatusString()`. This catches the *error* class (external geometry missing, attachment subshape not found, expression unresolvable). The *silent re-point* class (§2.3 dress-up drop, `referenceChanged()==true`) requires the before/after mapped-name diff described in §4.

---

## 4. Is the guard implementable as specified? — Yes. Proposed mechanism.

**Verdict: feasible with zero C++ changes.** Every primitive the guard needs is exposed to Python and callable from the bridge (verified against the `.pyi` binding stubs shipped in the source):

| Guard primitive needed | Python API (verified in source) | File |
|---|---|---|
| Recompute a document | `Document.recompute(objs=None, force=False, check_cycle=False)` | `App/Document.pyi:421` |
| Is object broken? | `DocumentObject.isValid()` / `State` | `App/DocumentObject.pyi:52, 164` |
| Why is it broken? | `DocumentObject.getStatusString()` | `App/DocumentObject.pyi:154` |
| Any pending recompute? | `Document.mustExecute()`, `DocumentObject.MustExecute` | `App/Document.pyi:435`, `DocumentObject.pyi:62` |
| Resolve a subelement (does the ref still point somewhere?) | `DocumentObject.getSubObject(...)`, `resolveSubElement(subname, append, type)`, `getSubObjectList` | `App/DocumentObject.pyi:170, 206, 308` |
| Full element map (stable-name keys) | `ComplexGeoData.ElementMap` (dict), `ElementReverseMap`, `ElementMapSize` | `App/ComplexGeoData.pyi:155-158` |
| Map indexed↔mapped name (bidirectional) | `ComplexGeoData.getElementName(name, direction)`, `getElementMappedName`, `getElementIndexedName` | `App/ComplexGeoData.pyi:117-135` |
| Element construction history (deep audit / re-point detection) | `TopoShape.getElementHistory(name) -> (sourceTag, sourceName, [intermediate])` | `Mod/Part/App/TopoShape.pyi:1087` |
| Resolve element by mapped name, silently | `TopoShape.getElement(name, silent=True)` | `Mod/Part/App/TopoShape.pyi:1035` |
| Element map version (did shape-build logic change?) | `GeoFeature.ElementMapVersion`, `DocumentObject.getElementMapVersion(prop)` | `App/GeoFeature.pyi:21`, `DocumentObject.pyi:327` |

### 4.1 Proposed guard algorithm (bridge-side, `verify.references` tool)

The guard is a **snapshot-mutate-audit** wrapper around any Phase-2 mutation. Three layers, in increasing depth:

**Layer 0 — Error sweep (necessary, cheap, catches the hard-fail class).**
1. Before mutation: nothing needed.
2. Mutate → `doc.recompute()`.
3. `broken = [(o.Name, o.getStatusString()) for o in doc.Objects if not o.isValid()]`.
4. Non-empty → fail + rollback (undo, per Phase-2 exit criterion). This alone catches missing external geometry (§2.2 throw), unresolvable attachment (§2.3 throw), and broken expressions (§2.4 throw).

**Layer 1 — Reference re-resolution audit (the specified guard; catches silent re-point + `?` markers).** This is the invention.
1. **Snapshot** (pre-mutation): walk every object; for each reference-holding property (`ExternalGeometry`, `AttachmentSupport`, `Profile`, `Base`, expression deps), record `{owner, prop, [(mappedName, indexedName, resolvesTo_globalPlacement_or_shapeHash)]}`. Mapped names come from `getShadowSubs()` (exposed) / `getElementMappedName`; resolution target from `getSubObject`/`getPlacementOf`.
2. **Mutate → recompute.**
3. **Audit** (post-mutation): for each snapshotted reference:
   - **Dangling:** subname now begins with `?` (`Data.hasMissingElement`) or `getElement(mapped, silent=True)` returns null → **FAIL (broken)**.
   - **Silently re-pointed:** reference still resolves, but the *mapped name changed* or the resolved element's geometry hash/placement differs from the snapshot while the reference was *not* the mutation's intended target → **FAIL (re-pointed)**. (`referenceChanged()` is the internal corroborator; externally we diff mapped-name sets and resolved-target hashes.)
   - **Count drop:** a `PropertyLinkSubList` (e.g. dress-up `Base`) lost entries vs snapshot → **FAIL (dropped edge)** — the specific silent-loss path found at `FeatureDressUp.cpp:143-144`.
   - Otherwise **PASS**.
4. Any FAIL → automatic rollback + human-readable report keyed to `owner.prop.oldReference → newState`.

**Layer 2 — History cross-check (optional, highest fidelity).** For a resolved-but-suspect reference, `TopoShape.getElementHistory(mappedName)` confirms the current element descends from the same source element/tag it did pre-mutation. Divergent history on an unchanged reference = re-point even when hashes coincidentally match. Use only for the 5 TNP-provoking benchmark scenarios where Layer 1 is ambiguous.

### 4.2 Mapping to Phase-2 exit criteria

- *"after each mutation, all existing feature references re-resolve"* → **Layer 0 + Layer 1** deliver exactly this, uniformly across the three subsystems (§2), because they all funnel through `PropertyLinkSub` shadow + the `Missing`/`?` marker + `Error` status.
- *"benchmark includes 5 TNP-provoking scenarios and the guard flags all of them"* → each scenario type is directly reachable: (a) upstream sketch edge insertion renumbering a filleted edge → dress-up `?Edge` / count-drop; (b) datum/face deletion under an attachment → `verifyReferencesAreSafe` throw → `Error`; (c) external-geometry source topology change → `Missing` flag / `"? "` ref; (d) object rename breaking an expression → `resolveErrorString`; (e) boolean-op re-ordering re-pointing a face reference (the known residual-TNP case from realthunder/Ondsel) → Layer 1 mapped-name diff / Layer 2 history divergence.
- The intent doc's Validation-First discipline (fault injection, sensitivity ≥ 95%, false-alarm ≤ 5%) applies to the guard itself: the `FeatureDressUp` silent-drop path and the "coincidental hash match" case are the two false-negative risks to plant tests against; a naive Layer-0-only guard would miss both.

---

## 5. Reuse assessment (updates `docs/intent.md` Reuse Map, TNP row)

The intent doc's claim — *"the automated post-mutation reference audit appears not to exist"* — is **correct as a packaged capability** but should be **narrowed**: FreeCAD 1.1 ships all the *detection primitives* and even partial auto-repair (`fixExternalGeometry`, `getRelatedElements`, `_updateElementReference` recovery). What does not exist is:
1. A **uniform enumerate-all-references-across-subsystems** pass (the three subsystems are audited internally but never jointly reported).
2. A **before/after snapshot diff** that catches *silent re-point* and *silent count-drop* (FreeCAD surfaces hard errors well, silent re-mapping poorly — `referenceChanged()` exists but is not aggregated into any user/agent-facing audit).
3. A **structured, machine-readable per-reference verdict** suitable for the agent verify-loop and rollback trigger.

So the invention budget is spent correctly, but **smaller than assumed**: the guard is a **~200-line bridge tool composing existing Python APIs**, not a reimplementation of TNP detection. This strengthens the "Reuse before invention" principle — adopt FreeCAD's `Missing`/`?`/`Error`/`getElementHistory` signals, invent only the cross-subsystem snapshot-diff-report layer.

**Risk / caveat carried forward:** the mapped element name is stable *by construction history*, not guaranteed; realthunder/Ondsel and FreeCAD issue #17041 ("face/edge IDs change after recompute") confirm residual TNP cases (notably Boolean/array-fed references) survive in 1.x. The guard's value is precisely to *catch* these residual cases — it must be validated against them (Layer 2 history check), not assumed away. `ElementMapVersion` drift (`GeoFeature.ElementMapVersion`) is a second-order signal: if a feature's shape-build logic version changes, all its mapped names may re-hash legitimately — the guard must treat a version bump as "expected re-map, re-baseline snapshot" rather than a failure, or it will false-alarm on FreeCAD upgrades.

---

## 6. Recommendation

**Proceed. Build the guard as a bridge-side `verify.references` tool; no FreeCAD fork or C++ patch is required.** Sequence:

1. **Phase 0 addition:** expose a `snapshot_references(doc)` and `audit_references(doc, snapshot)` pair in the bridge, built on the verified Python APIs in §4. Implement Layer 0 + Layer 1 first.
2. **Phase 2 gate:** wrap every mutation tool in snapshot → mutate → recompute → audit → (rollback on FAIL). Wire the 5 TNP-provoking scenarios as the benchmark; add fault-injection cases for the two false-negative risks (dress-up silent drop; coincidental hash match) to prove sensitivity ≥ 95% before the guard is trusted.
3. **Layer 2 (history)** only if Layer 1 misses any benchmark scenario.
4. **Feed findings into skills:** `freecad-datums-references` (why datum refs audit cleaner) and `freecad-troubleshooting` (mapping `getStatusString`/`?`-marker/`Missing`-flag → cause → fix) — the guard's failure taxonomy is directly reusable as skill content.

**Feasibility: HIGH. Novelty: MODERATE (composition layer, not detection). Blocking risk to Phase 2 exit: cleared.**

---

## Sources

**Local FreeCAD source (decisive; version 26.3.0-dev ≈ 1.1-dev), all under `docs/references/FreeCAD/src/`:**
`App/ElementNamingUtils.{h,cpp}`, `App/PropertyLinks.{h,cpp}`, `App/ElementMap.h`, `App/IndexedName.*`, `App/MappedElement.*`, `App/StringHasher.*`, `App/ComplexGeoData.pyi`, `App/DocumentObject.{h,cpp,pyi}`, `App/GeoFeature.pyi`, `App/Document.{cpp,pyi}`, `App/ObjectIdentifier.{h,cpp}`, `App/Expression.cpp`, `App/PropertyExpressionEngine.cpp`, `Mod/Sketcher/App/SketchObject.{h,cpp}`, `Mod/Sketcher/App/SketchObjectExternal.cpp`, `Mod/Sketcher/App/ExternalGeometryExtension.h`, `Mod/Part/App/AttachExtension.{h,cpp}`, `Mod/Part/App/Attacher.{h,cpp}`, `Mod/PartDesign/App/FeatureSketchBased.h`, `Mod/PartDesign/App/FeatureDressUp.{h,cpp}`, `Mod/Part/App/TopoShape.pyi` (`getElementHistory`, `getElement`).

**Web (corroboration of the 1.0 toponaming design):**
- [Topological Naming Algorithm — realthunder/FreeCAD_assembly3 wiki](https://github.com/realthunder/FreeCAD_assembly3/wiki/Topological-Naming-Algorithm)
- [FreeCAD's topological naming problem is (officially) history — Ondsel](https://www.ondsel.com/blog/toponaming-problem-is-history/)
- [Milestone: Ondsel and FreeCAD team complete phase 2 of the toponaming fix — Ondsel](https://www.ondsel.com/blog/milestone-toponaming-fix-phase-2-done/)
- [\[Issue\] TopoNaming Phase 1 — create MappedElement class (#8767)](https://github.com/FreeCAD/FreeCAD/issues/8767)
- [Toponaming: face/edge IDs change after recompute (Regression) (#17041)](https://github.com/FreeCAD/FreeCAD/issues/17041)
