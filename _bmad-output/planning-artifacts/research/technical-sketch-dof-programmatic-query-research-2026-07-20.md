---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - docs/intent.md
  - docs/references/FreeCAD/src/Mod/Sketcher (weekly-2026.07.15, 1.1-dev)
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'Programmatic sketch degrees-of-freedom query in FreeCAD (headless)'
research_goals: 'Determine how to query sketch DoF programmatically (solve() semantics, FullyConstrained, constraint introspection, redundant/conflicting/malformed detection, solver diagnostics) and whether all of it works headless under FreeCADCmd. Recommend the exact verify.sketch tool primitive set. Blocks Phase 2 verification tooling.'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Programmatic Sketch Degrees-of-Freedom Query in FreeCAD (Headless)

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** technical
**Primary source:** FreeCAD source tree at `docs/references/FreeCAD`, pinned at `weekly-2026.07.15-122-gfc135718a4` (the 1.1 development line). All C++/`.pyi` citations below are from `src/Mod/Sketcher/App` in that tree.

---

## Research Overview

FreeCAD Buddy's **Phase 2 exit criteria** require that AI-generated sketches be *fully constrained* — degrees of freedom (DoF) = 0 — in **≥ 90 % of sketch benchmark cases**, and that this be **verified automatically** (`docs/intent.md`, Phase 2 Measurable criteria; the Architecture `verify.*` tool taxonomy; the Validation-First Discipline that demands "the actor never grades itself"). Phase 3 raises the same bar ("all sketches DoF = 0") and the Skills Track uses "fully constrained sketch rate" as a named ablation sub-metric.

This report answers, from primary source: **how do you query a sketch's DoF and constraint health programmatically, and does every piece of it run headless under `FreeCADCmd` (no GUI)?** The answer is decisive and favorable: **all DoF and diagnostic state lives in the Sketcher *App* module, is exposed as read-only Python properties on `SketchObject`, is computed on every document recompute, and has zero GUI/Coin3D/Qt-Widgets coupling.** A `verify.sketch` primitive can therefore be built entirely on documented, headless-safe Python properties — no solver re-implementation, no GUI process, no screen-scraping.

**Methodology.** Primary evidence is the local FreeCAD source (`SketchObject.pyi`, `SketchObject.h`, `SketchObjectPyImp.cpp`, `SketchObjectConstraints.cpp`, `Sketch.cpp`, `SketchAnalysis.*`), traced getter-by-getter and confirmed for GUI-independence by grepping the solve/DoF/diagnostics code paths for any `Gui`/`Inventor`/`Coin`/`QtWidgets` dependency. This is corroborated by the FreeCAD SourceDoc API reference and wiki. Per the project's Reuse principle, the recommendation *composes existing kernel-level checks* rather than inventing any.

---

## 1. Technical Overview — the DoF and diagnostic surface

### 1.1 The core Python properties (all on `Part.Sketcher.SketchObject` / a PartDesign body's `Sketch`)

Every property below is declared in `src/Mod/Sketcher/App/SketchObject.pyi` and is `Final` (read-only from Python). These are the load-bearing primitives.

| Python attribute | Type | Meaning (verbatim from `SketchObject.pyi`) |
|---|---|---|
| `sketch.DoF` | `int` | "Return the DoFs of the current solved sketch" (`SketchObject.pyi:53`) |
| `sketch.FullyConstrained` | `bool` (PropertyBool) | "Sketch is fully constrained" — set to `lastDoF == 0` on a clean solve (see §1.3) |
| `sketch.ConflictingConstraints` | `List[int]` | "list of integers indicating the constraints detected as conflicting" (`:56`) |
| `sketch.RedundantConstraints` | `List[int]` | "constraints detected as redundant" (`:59`) |
| `sketch.PartiallyRedundantConstraints` | `List[int]` | "constraints detected as partially redundant" (`:62`) |
| `sketch.MalformedConstraints` | `List[int]` | "constraints detected as malformed" (`:65`) |
| `sketch.ConstraintCount` | `int` | "Number of Constraints in this sketch" (`:41`) |
| `sketch.GeometryCount` | `int` | "Number of geometric objects in this sketch" (`:44`) |
| `sketch.OpenVertices` | `List` | vertices positions of open (non-closed) wire endpoints (`:38`) |

> **`FullyConstrained` is a real headless property, not a GUI-only concept.** It is declared `App::PropertyBool FullyConstrained;` on `SketchObject.h:107` and registered in `SketchObject.cpp:98` with type `Prop_Output | Prop_ReadOnly | Prop_Hidden` and the docstring "Sketch is fully constrained". The GUI merely *reads* it (`ViewProviderSketch::isSketchFullyConstrained()` at `Gui/ViewProviderSketch.cpp:5260` returns `getSketchObject()->FullyConstrained.getValue()`), so a headless client gets exactly the same value the GUI would show.

### 1.2 `solve()` return-code semantics (the critical caveat)

`SketchObject.pyi:68-83` documents `sketch.solve() -> int`:

> Returns **0** on success, otherwise (in this order of priority):
> **-4** over-constrained, **-3** conflicting constraints, **-5** malformed constraints, **-1** solver error, **-2** redundant constraints.

Two caveats that matter for a verifier, both confirmed in source and corroborated by the FreeCAD API docs:

1. **A `0` return means "solved," NOT "fully constrained."** An under-constrained sketch (DoF > 0) solves successfully and returns `0`. *You cannot infer DoF = 0 from `solve() == 0`.* You must read `sketch.DoF` (or `FullyConstrained`) separately. This is the single most common self-deception mode for this check — exactly the "operation runs without error but the intent is unmet" trap the Phase 2 threat list warns about.
2. **`-2` (redundant) is a low-priority, non-fatal status.** A sketch with redundant constraints still solves and can still be DoF = 0 and perfectly usable; redundancy is a warning, not a failure. Whether Phase 2 treats redundancy as a benchmark failure is a *policy* decision (recommendation: warn, don't fail — see §5).

### 1.3 How the numbers are produced (C++ trace — confirms correctness and freshness)

- `SketchObjectPyImp.cpp:2745` — `getDoF()` returns `getSketchObjectPtr()->getLastDoF()`, i.e. the stored member `lastDoF` (`SketchObject.h:721`).
- `lastDoF` is assigned in `SketchObject::solve()` at `SketchObjectConstraints.cpp:93`:
  `lastDoF = solvedSketch.setUpSketch(getCompleteGeometry(), Constraints.getValues(), getExternalGeometryCount());`
  — the value is `GCSsys.dofsNumber()` from the App-module GCS (Geometric Constraint Solver), a QR-decomposition DoF count independent of the numeric iterate.
- The four diagnostic lists + boolean flags are filled by `retrieveSolverDiagnostics()` (`SketchObjectConstraints.cpp:65-75`): `lastHasConflict/lastConflicting`, `lastHasRedundancies/lastRedundant`, `lastHasPartialRedundancies/lastPartiallyRedundant`, `lastHasMalformedConstraints/lastMalformedConstraints`.
- `FullyConstrained.setValue(lastDoF == 0)` is set at `SketchObjectConstraints.cpp:169` **only when the solve returned `err == 0`** (no conflict/redundancy/malformed/over-constraint). So `FullyConstrained == True` is a *stronger* guarantee than `DoF == 0` alone — it also implies a clean solve.
- The `-1..-5` return mapping lives in `SketchObjectConstraints.cpp:110-136` (over-constrained is literally `lastDoF < 0`).

**Freshness guarantee — this is why the verifier is simple:** `SketchObject::execute()` (`SketchObject.cpp:189`) calls `this->solve(true)` on **every document recompute** (`SketchObject.cpp:216`). Therefore, after `doc.recompute()` (or `sketch.recompute()`), `DoF`, `FullyConstrained`, and all four diagnostic lists are guaranteed current — **no explicit `solve()` call is required by the verifier.** `onChanged()` also refreshes DoF/diagnostics via `setUpSketch()` after edits. Reading the properties post-recompute is the canonical, safe pattern.

### 1.4 Constraint / geometry introspection

- `sketch.Constraints` (inherited property) is the full `List[Constraint]`; each `Constraint` (`Constraint.pyi`) exposes `.Type` (e.g. `Coincident`, `Distance`, `Horizontal`, `Vertical`, `Radius`, `Equal`, `Symmetric`), `.First/.Second/.Third` geo-ids, `.FirstPos/.SecondPos/.ThirdPos`, `.Value`, `.Name`, `.IsDriving`, `.IsActive`. This lets a verifier report *which* constraints are conflicting/redundant by index and by type/name.
- The diagnostic lists (`ConflictingConstraints`, etc.) return **1-based** constraint IDs (`Sketch.cpp:2562` pushes `cid + 1`), so map them back to `sketch.Constraints[id-1]` for human-readable reporting.
- `sketch.getGeometryWithDependentParameters()` (`SketchObject.pyi:844`) returns `List[(geoId, posId)]` of the elements the solver still regards as free — i.e. **it pinpoints *what* is under-constrained**, which is exactly the diagnostic an agent needs to add the missing constraint. This is the headless equivalent of the GUI's "white vs green" element coloring.

---

## 2. Integration Patterns — using this from the headless bridge

### 2.1 Canonical query sequence (`FreeCADCmd`)

```python
import FreeCAD as App
doc = App.openDocument(path)      # or App.newDocument() + build
doc.recompute()                    # triggers SketchObject.execute() -> solve(true)
sk = doc.getObject("Sketch")       # a Sketcher::SketchObject

result = {
    "dof": sk.DoF,                                   # 0 == fully constrained
    "fully_constrained": bool(sk.FullyConstrained),  # stronger: DoF==0 AND clean solve
    "geometry_count": sk.GeometryCount,
    "constraint_count": sk.ConstraintCount,
    "conflicting": list(sk.ConflictingConstraints),          # 1-based ids
    "redundant": list(sk.RedundantConstraints),
    "partially_redundant": list(sk.PartiallyRedundantConstraints),
    "malformed": list(sk.MalformedConstraints),
    "open_vertices": len(sk.OpenVertices),
    "under_constrained_elements": sk.getGeometryWithDependentParameters(),
}
```

No GUI, no `import FreeCADGui`. Runs under `FreeCADCmd script.py` and inside the CI headless container from the Reuse Map ("Headless FreeCAD in CI").

### 2.2 Two solve models (avoid double-counting)

- **Recompute-driven (recommended for verification):** after `doc.recompute()`, just *read* the properties. Deterministic, matches what the GUI/user sees, no side effects on your intent.
- **Explicit `sk.solve()`:** returns the status code and, with `updateGeoAfterSolving=True` (default), writes solved geometry back into the `Geometry` property. Per the FreeCAD API docs and `SketchObject.pyi`, **`solve()` does NOT trigger a document recompute** — it is lower-level. Use it only when you need the status *code* in the same call; otherwise prefer recompute + property read. Do not rely on `solve()`'s return code as a DoF signal (see §1.2, caveat 1).

### 2.3 Where the sketch lives (PartDesign vs standalone)

In Phase 2/3 sketches are typically inside a PartDesign `Body`. `sk` is still a `Sketcher::SketchObject`; the DoF properties are identical whether the sketch is standalone or consumed by a Pad/Pocket. Query the `SketchObject` directly (via `body.Group` or `doc.getObject(name)`), not the resulting feature.

---

## 3. Architectural Patterns — headless-safety proof

**Claim: the entire DoF/diagnostic pipeline is GUI-free.** Verified by grepping the solve/DoF/diagnostics code paths:

- `SketchObjectPyImp.cpp` — **no** `Gui`/`Inventor`/`Coin`/`Qt*` includes anywhere. The Python getters read only App-module members.
- `Sketch.cpp`, `Sketch.h` — **no** GUI/Inventor/`FC_USE_GUI` matches. The GCS solver is pure App.
- `SketchObject.cpp` — the only `Gui` token is a **string literal** `"SketcherGui::ViewProviderPython"` (`:2215`), the view-provider *class name* returned for the GUI to look up — not a link/include dependency. No GUI headers.
- `SketchObjectConstraints.cpp` and `Sketch.cpp` use `QtCore` (`QCoreApplication::translate`, `QT_TRANSLATE_NOOP`) for message strings only. **QtCore is not a GUI dependency** — it links and runs under `FreeCADCmd`. No `QtGui`/`QtWidgets`/Coin3D scene-graph (`So*`) usage in any solve path.

**Consequence:** DoF, `FullyConstrained`, and all four diagnostic lists are computed by the App-module GCS solver during `execute()` and are fully readable in a headless process. The GUI is a pure *consumer* of already-computed values (`ViewProviderSketch.cpp:4423` reads `getLastDoF()` for the DoF label; `:4989`/`:5260` read `FullyConstrained` for coloring). This directly satisfies the project's cross-cutting requirement that "every phase's suite runs headless in CI from Phase 0 onward."

**Malformed vs conflicting vs redundant — precise definitions (from `Sketch.cpp`):**
- *Malformed*: a constraint that failed to be added to the GCS at all (bad indices / impossible reference) — pushed during `addConstraints` (`Sketch.cpp:2562/2584`). Highest-severity data problem; also surfaced by `evaluateConstraints()` (`SketchObject.pyi:906`, returns `True` if invalid indices exist) and repairable via `validateConstraints()`.
- *Conflicting*: constraints that cannot be simultaneously satisfied (the sketch is over-defined in an inconsistent way) — from `GCSsys.getConflicting()`.
- *Redundant / partially redundant*: constraints that add no new information (the DoF they remove is already removed) — from `GCSsys.getRedundant()` / `getPartiallyRedundant()`. Non-fatal.

---

## 4. Implementation Research — supporting primitives for the `verify.sketch` tool

Beyond the read-only status, the App module offers headless helpers the verifier and the repair loop can use (all in `SketchObject.pyi` unless noted):

| Primitive | Use in verification / repair |
|---|---|
| `evaluateConstraints() -> bool` (`:906`) | Cheap pre-check: `True` means malformed/invalid-index constraints exist. Catches data corruption before trusting DoF. |
| `validateConstraints()` (`:913`) | Repair: removes invalid-index constraints (use before re-solve). |
| `autoRemoveRedundants(update)` (`:919`) | Repair: drop solver-detected redundants — supports "warn then auto-clean" policy. |
| `getGeometryWithDependentParameters()` (`:844`) | Localize *which* elements/points are still free (drives targeted constraint addition). |
| `detectDegeneratedGeometries(tol) -> int` / `removeDegeneratedGeometries(tol)` (`:152/:167`) | Catch zero-length/degenerate geometry that silently breaks constraining. |
| `detectMissing*Constraints()` + `Missing*Constraints` props (`:858-902`, `:26-36`) | `SketchAnalysis`-backed autoconstraint hints: coincident, horizontal/vertical, equality, radius — proposes constraints to reach DoF = 0. |
| `autoconstraint()` (`:852`) | Full auto-constrain pass (last-resort repair; use cautiously — can add unintended intent). |
| `calculateConstraintError(index) -> float` (`:819`) | Signed/RMS error per constraint — quantify *how* violated a conflicting constraint is. |
| `Constraint.Type` / `.IsDriving` / `.Name` (`Constraint.pyi`) | Human-readable diagnostic mapping from the 1-based diagnostic ids. |

All of the above are App-module methods available under `FreeCADCmd`. `SketchAnalysis.cpp`/`.h` (which back the `detect*`/`autoconstraint` family) contain no GUI dependency; `SketchAnalysis::solvesketch()` (`:835`) mirrors the same DoF/over-constrained logic (`dofs < 0` ⇒ over-constrained).

**Fault-injection alignment (Validation-First).** The verifier can be validated per `intent.md` §"Validate the validator": plant faults and confirm each is flagged — leave a line unconstrained (`DoF > 0`, `FullyConstrained == False`), add a duplicate dimension (`RedundantConstraints` non-empty), over-define (`DoF < 0` / `ConflictingConstraints` non-empty), inject a bad-index constraint (`evaluateConstraints() == True` / `MalformedConstraints` non-empty), and add a zero-length edge (`detectDegeneratedGeometries > 0`). Each maps to a distinct, deterministic property signal — ideal for the ≥ 95 % sensitivity gate.

---

## 5. Recommendation — the `verify.sketch` primitive set

**Recommended tool: `verify.sketch(sketch_ref) -> SketchVerification`** (one deterministic, read-only tool; recompute first, then read properties). Returns:

```jsonc
{
  "dof": 0,                          // sk.DoF
  "fully_constrained": true,         // sk.FullyConstrained  <-- the Phase-2 PASS signal
  "geometry_count": 4,               // sk.GeometryCount
  "constraint_count": 8,             // sk.ConstraintCount
  "conflicting": [],                 // sk.ConflictingConstraints (1-based ids -> names)
  "redundant": [],                   // sk.RedundantConstraints
  "partially_redundant": [],         // sk.PartiallyRedundantConstraints
  "malformed": [],                   // sk.MalformedConstraints (+ evaluateConstraints())
  "degenerate_geometry_count": 0,    // sk.detectDegeneratedGeometries(tol)
  "open_vertices": 0,                // len(sk.OpenVertices)
  "under_constrained_elements": [],  // sk.getGeometryWithDependentParameters()
  "solver_status_code": 0            // optional: sk.solve() code, for logging only
}
```

**Pass/fail policy for the Phase 2 "DoF = 0 in ≥ 90 %" gate (the deterministic grader, actor-independent):**

- **PASS ⇔ `fully_constrained == True`.** Use `FullyConstrained`, not a bare `DoF == 0`, because it additionally guarantees a clean solve (no conflict/malformed) — a stricter, single-boolean pass signal that matches the GUI's own verdict.
- **HARD FAIL** on any non-empty `conflicting` or `malformed`, or `evaluateConstraints() == True`, or `DoF < 0` (over-constrained), or `DoF > 0` (under-constrained), or `degenerate_geometry_count > 0`. These are correctness failures.
- **WARN (not fail)** on `redundant` / `partially_redundant`. Redundancy does not violate "DoF = 0"; treat as a quality warning and optionally auto-clean with `autoRemoveRedundants()`. (Make this policy explicit in the Phase 2 threat-list/grading spec so the metric is unambiguous.)

**Mandatory usage contract (encode in the tool/skill):**
1. `doc.recompute()` **before** reading — properties are only guaranteed fresh post-recompute/`execute()`.
2. **Never** infer DoF from `solve() == 0`; always read `DoF`/`FullyConstrained`.
3. Map 1-based diagnostic ids to `sketch.Constraints[id-1]` (`.Name`/`.Type`) for human-readable reports.
4. For the repair loop, feed `getGeometryWithDependentParameters()` + `detectMissing*` back to the agent to add exactly the missing constraints.

**Reuse verdict (per `intent.md` Reuse principle):** *reuse, do not invent.* The DoF count, `FullyConstrained` flag, and all four diagnostic categories are solved, kernel-level, headless-safe FreeCAD facilities. `verify.sketch` is a thin composition/reporting layer over documented Python properties — the only "invention" is the pass/fail policy and the JSON report shape, which belong to the project's verify-first tool taxonomy. No solver code, no GUI, no forking required.

**Version caveat (Risk: "FreeCAD version drift").** This is verified against the 1.1-dev tree (`weekly-2026.07.15`). `DoF`, `FullyConstrained`, `ConflictingConstraints`, `RedundantConstraints`, `MalformedConstraints`, and `GeometryCount`/`ConstraintCount` also exist in FreeCAD 1.0 and 0.21; `PartiallyRedundantConstraints`, `MalformedConstraints`, and the malformed `-5` return code are newer (1.0+). Pin the supported version in CI and keep the diagnostic-list reads defensive (`getattr(sk, "MalformedConstraints", [])`) behind the thin adapter the intent's version-drift mitigation already calls for.

---

## Sources

**Primary (decisive) — local FreeCAD source, `weekly-2026.07.15-122-gfc135718a4`:**
- `docs/references/FreeCAD/src/Mod/Sketcher/App/SketchObject.pyi` — Python API surface: `DoF` (53), diagnostic lists (56-65), `solve()` return codes (68-83), `Constraint/Geometry Count` (41/44), introspection/repair methods.
- `docs/references/FreeCAD/src/Mod/Sketcher/App/SketchObject.h` — `FullyConstrained` property (107); `getLastDoF()` and `getLast*` accessors (721-774).
- `docs/references/FreeCAD/src/Mod/Sketcher/App/SketchObject.cpp` — `FullyConstrained` registration (98); `execute()` → `solve(true)` on recompute (189/216).
- `docs/references/FreeCAD/src/Mod/Sketcher/App/SketchObjectConstraints.cpp` — `solve()`: `lastDoF` assignment (93), `retrieveSolverDiagnostics()` (65-75), return-code logic (110-136), `FullyConstrained.setValue(lastDoF==0)` (169).
- `docs/references/FreeCAD/src/Mod/Sketcher/App/SketchObjectPyImp.cpp` — `getDoF()` (2745) and diagnostic getters (2752-2802).
- `docs/references/FreeCAD/src/Mod/Sketcher/App/Sketch.cpp` — GCS DoF (`setUpSketch` → `dofsNumber()`), conflicting/redundant population (353-355), 1-based malformed ids (2562/2584).
- `docs/references/FreeCAD/src/Mod/Sketcher/App/SketchAnalysis.{h,cpp}` — autoconstraint/missing-constraint/degenerate helpers; `solvesketch()` DoF logic (835).
- `docs/references/FreeCAD/src/Mod/Sketcher/Gui/ViewProviderSketch.cpp` — GUI *consumes* the same values (4423, 4989, 5260) — proves the App-side computation is authoritative and GUI-independent.

**Corroborating (web):**
- [Sketcher::SketchObject Class Reference — FreeCAD SourceDoc](https://freecad.github.io/SourceDoc/d9/dad/classSketcher_1_1SketchObject.html) — `solve()` return codes and "does not trigger a recompute" note.
- [FreeCAD Sketcher Workbench documentation (wiki)](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Sketcher_Workbench.md) — fully-constrained concept and constraint types.
