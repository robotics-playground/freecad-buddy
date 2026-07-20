---
stepsCompleted: ['init', 'research', 'synthesis']
inputDocuments: ['docs/intent.md']
workflowType: 'research'
lastStep: 3
research_type: 'technical'
research_topic: 'CAD dataset licenses and convertibility to FreeCAD parametric operations (Fusion 360 Gallery, DeepCAD, ABC, text-to-CAD benchmarks)'
research_goals: 'Determine license terms (commercial/derivative), data format, and realistic convertibility to FreeCAD Sketcher/PartDesign operation sequences for published CAD datasets and FreeCAD-native sources; recommend sources per phase and estimate conversion effort. Blocks Phase 2/3 benchmark provenance requirements.'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** Technical
**Research Topic:** CAD dataset licenses and convertibility to FreeCAD parametric operations

---

## Research Overview

This report investigates whether the CAD-generation datasets referenced in the FreeCAD Buddy **Reuse Map** (`docs/intent.md`, "Benchmark specs & golden models" row) can legally and practically seed benchmark specifications and golden models for Phases 2 and 3. The Validation-First Discipline (principle 5, "Realism over convenience") mandates that every benchmark documents its provenance and derives from real-world parts. Two questions therefore gate the phases:

1. **Legal:** Can each dataset be used, modified, and (in a solo/hobby-to-possibly-commercial project) distributed for our benchmark purposes? What are the commercial/derivative-use terms?
2. **Practical:** What is the data format, and how much engineering effort is required to convert a dataset sample into a **FreeCAD Sketcher + PartDesign parametric operation sequence** with a machine-checkable acceptance spec?

**Methodology.** Primary web research against dataset repositories, license files, source papers, and dataset landing pages (priority-1 evidence per task brief), cross-referenced with `docs/intent.md` requirements. Each license claim is sourced to the actual LICENSE file or terms page where reachable. The critical provenance chain (Onshape -> ABC -> DeepCAD -> Text2CAD) was traced explicitly because it determines the real license ceiling for three of the four dataset families.

**Key headline.** The four "famous" datasets are **format-rich but license-constrained and hard to convert**; the cleanest fit for FreeCAD Buddy's provenance requirement is **FreeCAD-native sources** (the official Parts Library, community tutorial models, and a newly-published FreeCAD-native generation dataset) plus **hand-authored specs**. The big datasets are best used as *inspiration and geometry-oracle references*, not as the parametric golden models themselves.

---

## 1. Dataset-by-Dataset Findings

### 1.1 Fusion 360 Gallery (Autodesk AI Lab)

- **Contents:** ~8,625 designs in the Reconstruction subset, each an ordered **sketch-and-extrude construction sequence**; plus Segmentation and Assembly subsets (joint/hierarchy data). Ships a "Fusion 360 Gym" reconstruction environment. This is the *only* one of the four with genuinely clean, human-authored **sequential design history** in a documented schema.
- **Format:** JSON construction sequences (sketch profiles + extrude operations), with per-operation segmentation and B-rep/mesh outputs. Semantically the **closest to FreeCAD Sketcher -> PartDesign Pad/Pocket** of any dataset here.
- **License — the blocker:** Custom Autodesk license. Verbatim: *"You may access, use, reproduce and modify the Dataset ... only for non-commercial research purposes."* No full redistribution (portions/modifications only, under an equally-restrictive license, pointing back to the repo). Explicit no-re-identification clause and an indemnification clause.
- **Convertibility:** *High semantic fit, low legal fit.* The sketch-extrude schema maps almost 1:1 onto FreeCAD sketch + pad/pocket, so a converter is realistic (parse profile geometry -> Sketcher geometry+constraints; parse extrude -> PartDesign feature). But the **non-commercial-only** term is a hard ceiling: if FreeCAD Buddy ever moves toward the Phase 4 "as a service" / any commercial framing, derived benchmarks carry the restriction. Safe only as **non-commercial research provenance**, and even then benchmark artifacts derived from it cannot ship in a commercial distribution.

### 1.2 DeepCAD (Columbia)

- **Contents:** ~178,238 models with CAD construction sequences (sketch-extrusion language). The de-facto standard for CAD-generation research and the substrate under most text-to-CAD work.
- **Format:** `cad_json` (construction sequences parsed from Onshape) + `cad_vec` (vectorized). Compact sketch-extrude command language — again a **good structural match** to FreeCAD sketch+pad/pocket.
- **License — deceptive:** The **DeepCAD repo/code is MIT** (permissive, commercial OK *on the code*). **But** the *data* was "parsed from Onshape public documents using links from the ABC dataset." The MIT license covers the authors' code and parsing scripts, **not** the underlying CAD geometry, whose copyright remains with the original Onshape creators (see 1.3 / 1.5). So the headline "MIT" is misleading for the *models themselves*.
- **Convertibility:** *Good structural fit, murky legal fit.* The command language is convertible to FreeCAD operations with moderate effort (similar converter to Fusion 360 Gallery, arguably simpler since it is a normalized abstract language rather than Fusion's richer schema — but it loses constraint semantics: profiles are geometric, not constrained, so reaching **DoF = 0** in FreeCAD requires re-inferring constraints, which is exactly the Phase 2 hard problem). Legal ceiling is set by **Onshape terms + per-model creator copyright**, not by MIT.

### 1.3 ABC — "A Big CAD Model Dataset" (Deep Geometry)

- **Contents:** ~1,000,000 CAD models — the most-used B-rep dataset in academia.
- **Format:** STEP + Parasolid (parametric B-rep), STL/OBJ (mesh with GT normals/curvature), and a **FeatureScript** "feature" format that captures the Onshape generation process. Note: ABC is primarily a **geometry** dataset — the dominant, clean signal is B-rep, *not* a FreeCAD-style ordered feature history.
- **License — the real ceiling:** Dataset packaging is **MIT**, but the landing page is explicit: *"The copyright of the CAD models is owned by their creators,"* and points to **Onshape Terms of Use 1.g.ii**. So, as with DeepCAD, MIT covers wrappers/scripts, not the models.
- **Convertibility:** *Low for parametric intent.* ABC gives you B-rep solids, not sketch/feature sequences suitable for a parametric golden tree. Converting a STEP solid into a *parametric* FreeCAD feature tree is the **reverse-engineering / feature-recognition** problem (Phase 5 "reverse tasks"), which is far harder than replaying a construction sequence. ABC is most useful as a **geometry oracle** (import STEP -> query volume/bbox/face counts as an independent reference to assert against) rather than as parametric golden models.

### 1.4 Text-to-CAD benchmark family (Text2CAD, CADPrompt, and 2025-2026 successors)

- **Text2CAD (Khan et al., 2024):** ~660k natural-language annotations (beginner->expert) layered **on top of DeepCAD samples** via an LLM/VLM pipeline. It inherits DeepCAD's data provenance (and therefore its Onshape license ceiling). Value for us: **the spec-text pairing** — it demonstrates how to attach natural-language prompts to construction sequences, which is directly relevant to Phase 3 "free-text part specification."
- **CADPrompt (Alrashedy et al., 2025):** 200 expert-written NL instructions over DeepCAD samples — an out-of-distribution generalization test. Small, curated, human-written prompts; useful as a **style reference for authoring Phase 3 specs**.
- **2025-2026 successors seen in search (BenchCAD, Text2CAD-Bench, MUSE, HistCAD, CadBench, Parametric CAD Bench):** the field is moving toward *history-based, constraint-aware, manufacturability-graded* benchmarks (HistCAD explicitly targets constraint-aware parametric history; MUSE grades manufacturable/assemblable output). These are newer and worth a licence-by-licence check at each phase's Reuse survey, but most still build on DeepCAD/Fusion lineage and thus inherit the same provenance ceilings.
- **Convertibility:** The *annotations* are text and easy to reuse conceptually; the *underlying geometry* carries the same DeepCAD/Onshape constraints. Net: **borrow the annotation methodology, not the licensed pairs**, for anything that must ship.

### 1.5 The provenance chain that sets the real ceiling

Three of the four families collapse to the same source:

```
Onshape public documents (per-model creator copyright; Onshape ToU governs)
        └─> ABC (MIT wrapper; models NOT MIT)
                └─> DeepCAD (MIT code; data parsed from Onshape via ABC links)
                        └─> Text2CAD / CADPrompt (NL annotations over DeepCAD)
```

Onshape's own terms confirm the risk: **Free-plan documents are public**, and Onshape explicitly requires a **paid subscription for commercial IP creation**; public models can be viewed/copied by others but that does not grant a clean commercial redistribution license, and **each model's copyright stays with its creator**. So an "MIT" label two hops downstream does **not** launder the models into commercial-clean assets. For a project that may become a service, this is the decisive finding.

---

## 2. FreeCAD-Native Sources (the recommended provenance backbone)

These were under-weighted in the Reuse Map and are the strongest fit for the Validation-First "realism + documented provenance" requirement.

### 2.1 FreeCAD Official Parts Library

- **License: CC-BY 3.0**, each part attributed to its author. Commercial-friendly with attribution — **no non-commercial ceiling**.
- **Format:** native **`.FcStd`** (parametric feature trees!) plus `.stp`, optionally `.stl`. Because parts are native FreeCAD documents, **zero conversion** is needed — the parametric tree, sketches, and constraints already exist and can be queried directly by the Phase 0 bridge.
- **Convertibility: effectively N/A (already native).** Ideal as golden models: open `.FcStd`, read the expected feature tree / DoF / volume, author assertions.

### 2.2 FreeCAD wiki tutorial models

- Official manual/wiki tutorials (documentation is GFDL/CC on the FreeCAD wiki) come with **step-by-step operation sequences** — i.e., a human-authored, reproducible Sketcher->PartDesign build plan *and* a target geometry. This is the single best match for a **Phase 2/3 golden model with a documented, real-world provenance and a checkable build sequence**. Effort is in transcribing the tutorial steps into an assertion spec, not in format conversion.

### 2.3 Community/printables-style part libraries

- Individual community models (Printables/Thingiverse/OSE Part Library, etc.) vary per-item (often CC-BY / CC-BY-SA / CC0). **License must be checked per model** — no blanket statement possible. CC-BY-SA introduces share-alike obligations; CC0/CC-BY are cleanest. Many community parts are **STL-only (mesh)**, which is *not* a parametric source and lands in the same reverse-engineering bucket as ABC. Prefer items that ship native `.FcStd` or STEP with a documented build.

### 2.4 New: FreeCAD-native generation dataset (2026)

- Search surfaced a **`cad-gen-freecad` dataset published to Hugging Face (~May 2026)**: native FreeCAD parts with **parametric feature history, design specs, and renderings**, explicitly aimed at text->parametric FreeCAD generation. Also surfaced a **FreeCAD parametric-part agent benchmark** scoring multi-step agentic loops for geometric correctness vs. spec across multiple model/vendor combinations.
- **Why it matters:** this is the first source that is *both* FreeCAD-native *and* spec-paired — potentially a near-drop-in for Phase 3 provenance. **License and quality must be verified at the Phase 3 Reuse survey** (HF datasets carry heterogeneous licenses), but if its license is permissive this is the highest-value newly-available reuse candidate and materially de-risks the Phase 3 benchmark. Treat as *evaluate-first*, high-priority.

---

## 3. Convertibility & Effort Summary

| Source | License (commercial?) | Format | Parametric history? | Convert-to-FreeCAD effort | Best role |
|---|---|---|---|---|---|
| Fusion 360 Gallery | Non-commercial research only | JSON sketch+extrude seq | Yes (clean) | Medium (converter; constraints must be re-inferred for DoF=0) | Non-commercial inspiration + geometry oracle |
| DeepCAD | Code MIT; **data = Onshape ceiling** | JSON sketch-extrude cmd lang | Yes (abstract, no constraints) | Medium (converter + constraint inference) | Reference geometry; methodology |
| ABC | Wrapper MIT; **models = Onshape ceiling** | STEP/Parasolid, mesh, FeatureScript | No (B-rep, not FreeCAD history) | High (reverse-engineering / feature recognition) | Geometry oracle (import->assert), not golden trees |
| Text2CAD / CADPrompt / 2026 benches | Inherits DeepCAD/Onshape ceiling | NL text over DeepCAD geometry | Via DeepCAD | Text reusable; geometry not | Spec-authoring methodology |
| **FreeCAD Parts Library** | **CC-BY 3.0 (commercial OK + attribution)** | **`.FcStd`** + STEP | **Yes (native)** | **~None (native)** | **Golden models** |
| **FreeCAD wiki tutorials** | GFDL/CC (doc) | Step-by-step + target | **Yes (human build plan)** | Low (transcribe to assertions) | **Golden models + build-plan provenance** |
| Community libs (Printables/etc.) | Per-item (CC0/CC-BY/CC-BY-SA) | Often STL; some FcStd/STEP | Only if FcStd/STEP | None-to-High (varies) | Supplementary, check each license |
| **cad-gen-freecad (HF, 2026)** | **Verify at Phase 3** | FreeCAD-native + specs | **Yes (native)** | Low if usable | **High-value Phase 3 candidate (evaluate-first)** |

**Two recurring conversion facts that matter for Phase 2:**
1. Sketch-extrude datasets give **geometric profiles, not constrained sketches**. Replaying them into FreeCAD yields a shape, but reaching the intent's **DoF = 0 / fully-constrained** exit criterion (Phase 2: >=90% fully constrained) requires *inferring* constraints — that inference is itself part of what the agent/skills are being tested on, so importing these as "golden" risks circularity.
2. B-rep/mesh sources (ABC, most community STLs) carry **no** parametric intent; converting them to a parametric tree is a Phase 5 reverse-engineering task, not a Phase 2/3 shortcut.

---

## 4. Recommendation by Phase

**Phase 2 (Copilot — single-op benchmark, 40 commands, 8 op types):**
- **Primary provenance:** **FreeCAD Parts Library (CC-BY)** + **hand-authored operations on simple reference models**. These are native, license-clean, and give known-good parametric baselines to run single ops against and assert deltas.
- **Secondary (non-shipping):** Use Fusion 360 Gallery / DeepCAD sequences as *idea sources* for realistic op mixes and parameter ranges — do **not** ship derived artifacts if commercial framing is possible. Author the actual benchmark models natively.
- **Effort:** low-to-medium; the work is authoring assertions, not format conversion.

**Phase 3 (Designer — 20 written part specs with machine-checkable assertions):**
- **Primary provenance:** **FreeCAD wiki tutorial models** (real-world, documented build plans -> natural spec + golden geometry) + curated **Parts Library** parts (brackets/plates/flanges/spacers match the intent's target classes).
- **Evaluate-first, high-value:** the **`cad-gen-freecad` HF dataset (2026)** — if its license is permissive it can supply spec-paired native FreeCAD parts and materially de-risk this benchmark. Verify license + quality in the Phase 3 Reuse survey before adopting.
- **Spec-authoring methodology:** borrow the **Text2CAD/CADPrompt** annotation approach (beginner->expert NL prompts) to write our 20 specs — reuse the *method*, not their licensed pairs.
- **Do NOT** attempt to convert ABC B-reps into parametric golden trees for Phase 3 — wrong tool, wrong phase.

**Phase 4 (service, possibly commercial framing):**
- Restrict provenance to **commercial-clean** sources only: **CC-BY Parts Library** (with attribution retained in the repo) + our own hand-authored specs + any *verified*-permissive HF dataset. **Exclude** Fusion 360 Gallery (non-commercial), and exclude DeepCAD/ABC/Text2CAD *models* (Onshape creator-copyright ceiling). Their *methods/geometry-oracle* use remains fine.

**Cross-cutting (ABC's best use, all phases):** use ABC/STEP imports purely as an **independent geometry oracle** for validator fault-injection and false-alarm testing (principle 2, "validate the validator") — import a known STEP, and confirm `verify.shape` reports match — without treating them as parametric golden models.

---

## 5. Risks & Provenance Gotchas

- **The "MIT" trap.** DeepCAD and ABC advertise MIT, but MIT covers only code/wrappers; the **models inherit Onshape creator copyright**. Do not treat MIT-labeled CAD datasets as commercially clean without tracing provenance. (Highest-impact finding.)
- **Non-commercial lock-in.** Fusion 360 Gallery is non-commercial-only *and* forbids full redistribution — any benchmark derived from it constrains the whole project's future commercial optionality.
- **Constraint loss.** Sketch-extrude datasets don't encode constraints; imported profiles won't be DoF=0, and forcing them there is circular with what Phase 2 is testing.
- **Mesh dead-ends.** STL-only community models and ABC B-reps are not parametric provenance; treat as oracle geometry, not golden trees.
- **Per-model license variance.** Community libraries must be checked item-by-item (CC0/CC-BY/CC-BY-SA differ materially; SA adds share-alike).
- **HF dataset licenses are heterogeneous.** The promising 2026 `cad-gen-freecad` set must have its license read directly before Phase 3 adoption.

---

## Sources

- [Fusion360GalleryDataset LICENSE.md (Autodesk AI Lab)](https://github.com/AutodeskAILab/Fusion360GalleryDataset/blob/master/LICENSE.md)
- [Fusion360GalleryDataset repo](https://github.com/AutodeskAILab/Fusion360GalleryDataset)
- [Fusion 360 Gallery paper (Autodesk Research)](https://www.research.autodesk.com/publications/fusion-360-gallery/)
- [DeepCAD paper (arXiv 2105.09492)](https://arxiv.org/abs/2105.09492)
- [DeepCAD project page (Columbia)](https://www.cs.columbia.edu/cg/deepcad/)
- [DeepCAD repo (ChrisWu1997)](https://github.com/ChrisWu1997/DeepCAD)
- [ABC Dataset landing page](https://deep-geometry.github.io/abc-dataset/)
- [ABC: A Big CAD Model Dataset (paper)](https://www.researchgate.net/publication/333207311_ABC_A_Big_CAD_Model_Dataset_for_Geometric_Deep_Learning)
- [Text2CAD (NeurIPS 2024)](https://proceedings.neurips.cc/paper_files/paper/2024/file/0e5b96f97c1813bb75f6c28532c2ecc7-Paper-Conference.pdf)
- [Text2CAD-Bench (arXiv 2605.18430)](https://arxiv.org/html/2605.18430)
- [HistCAD (arXiv 2602.19171)](https://arxiv.org/pdf/2602.19171)
- [MUSE benchmark (arXiv 2605.28579)](https://arxiv.org/html/2605.28579)
- [Parametric CAD Bench (gnucleus.ai)](https://www.gnucleus.ai/cad-bench)
- [FreeCAD Parts Library (GitHub, CC-BY 3.0)](https://github.com/FreeCAD/FreeCAD-library)
- [FreeCAD official addons](https://www.freecad.org/addons.php?lang=en)
- [Onshape Terms of Use](https://www.onshape.com/en/legal/terms-of-use)
- [Onshape free-user public/commercial restrictions (BigGo)](https://biggo.com/news/202508021942_Onshape_Free_License_Restrictions)
