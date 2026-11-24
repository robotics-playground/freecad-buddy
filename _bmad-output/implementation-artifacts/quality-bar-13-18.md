# Story 13-18: quality bar

Base: dd7e8355. Plan: builder-13-18 plan + `spec-13-18-loft-sweep.md` (wt-13-18), approved 2026-11-24.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | `feature_loft` input per T-9 (`body`, `profile`, `sections` ≥1, `ruled`, `closed`, `subtractive`, `name`, `confirm`) creates `PartDesign::AdditiveLoft` or `SubtractiveLoft` | T-9 | infc tests, additive and subtractive |
| Q2 | `feature_sweep` input per T-9 (`spine` oneOf sketch name / Selector, `mode` standard/frenet, `subtractive`) creates `AdditivePipe` or `SubtractivePipe`; mode map checked against `FeaturePipe.cpp` | T-9 | infc tests, both modes, both kinds, both spine forms |
| Q3 | Each call runs in the AD-5 bracket, returns a mutation diff, and one `document_undo` reverts it | CAP-9 | infc undo round trip |
| Q4 | Refusals before the bracket with `detail.code` (non-sketch inputs, null shape, profile in sections, duplicate section, wire-count mismatch, `closed` with <2 sections that FreeCAD would silently reset, bad spine) | builder plan; L8, L9 | tests per code |
| Q5 | A result with no solid (open sections) → `RECOMPUTE_ERROR` with proven rollback; no undo step left behind (L14) | AD-5; L14 | infc test incl. undo after the refusal |
| Q6 | Cost guard measured (sections × edges, BSpline profiles, helical spines) and refused above it with `loft.too_complex` / `sweep.too_complex`; measurement beside the constant; worst accepted call well inside the budget | L2 | tests both sides; verifier timing |
| Q7 | TNP audit CLEAN on a normal loft/sweep; preview reaches both tools | AD-5; M-19 | infc tests |
| Q8 | `mcp-tools-design.md` §2 rows and §3 schemas match code; no shared-code edits (L12) | T-9 | read; diff |

Levels marked RUN: Unit, Integration (freecadcmd). UAT: container build of a lofted and a swept part with a visual check by the verifier.
