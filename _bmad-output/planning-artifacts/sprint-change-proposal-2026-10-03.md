# Sprint Change Proposal — FreeCAD 1.1 Only (2026-10-03)

Mode: batch. Author: Developer agent, for TanNT.

## 1. Issue Summary

**Trigger.** User decision, 2026-10-03: the project supports FreeCAD 1.1 only. FreeCAD 1.0 support is dropped.

**Category.** Strategic change of scope (supported platform), not a defect.

**Context.** The change came during Story 4.2b. FreeCAD 1.0.0 failed 2 in-FreeCAD tests and 1 more errored at baseline `479e44e` (version-specific defaults and enum spellings), so the 1.0.x CI leg stopped before its later steps. The user chose to stop supporting 1.0 instead of keeping two legs green.

**Already implemented.** Commit `753ea93` (spec `implementation-artifacts/spec-drop-freecad-1-0-support.md`, decisions D1–D6):
- CI runs one headless leg: FreeCAD 1.1.3, Python 3.11 (linux-64). The render job uses the same build.
- G0.4 requires only the 1.1.x leg; a 1.0.x evidence file is ignored.
- G3.E.3 reads "every built part's anchor frame equals the committed 1.1.x reference".
- Pattern modes accept only `Extent` and `Spacing`.
- `addon/package.xml` `<freecadmin>1.1</freecadmin>`; every `SKILL.md` declares `freecad-versions: ['1.1']`.
- `docs/references/FreeCAD` is pinned to tag `1.1.4`.

**Evidence that 1.1.3 meets the rest of the plan** (local env `fcb`, FreeCAD 1.1.3, Python 3.12.14):
- In-FreeCAD suite 674 run, OK; external suite 1202 passed (5 known G1 grader-hash failures).
- G3 replay 10/10 detected, 0/14 false alarms, frames equal to the reference.
- Capability probes: `export_binary_available() = True`, `varset_backend() = varset`, `element_map_available() = True`; H1 (`import FreeCAD` in the env interpreter) works.

**What is left.** The planning artifacts and decision notes still state a 1.0.x floor. This proposal corrects them.

## 2. Impact Analysis

**Epics.** No epic is added, removed or resequenced. Wording changes only, in NFR4 and in the ACs of Stories 1.1, 1.10, 3.8 and 4.2. Stories 1.1, 1.10 and 3.8 are done; their ACs change from "both legs" to "the 1.1.x leg", which is how the gates now read. No story status changes. `sprint-status.yaml` needs no edit.

**Requirements (SPEC.md, phase-gates.md).** The MVP is not affected. CAP-1 success, the CI rule and G0.4 / G2.4 wording change from a two-leg matrix to the 1.1.x leg.

**Architecture.**
- AD-11 (version support): supported set becomes FreeCAD 1.1.x plus the 1.2-dev canary.
- AD-13 (anchor frames): "resolves identically on the floor and primary legs" becomes "equals the committed 1.1.x reference frame".
- Stack table, repository tree comment, project-structure CI tables, shim section, banner example, skills field rules.

**UX.** None (no UX document).

**Other artifacts.** `project-context.md` (agent rules), `docs/intent.md` (risk table), ADRs 001, 002 and 006 (open per-leg questions now answered for 1.1.3), new ADR 016.

**Not edited (historical records).** Implementation specs, epic contexts, retros, architecture reviews, research, earlier sprint change proposals, `.memlog.md`, UAT run reports.

## 3. Recommended Approach

**Option 1 — Direct adjustment (selected).** Edit the normative documents to match the implemented decision. Effort: low. Risk: low. Timeline: no impact.

**Option 2 — Rollback.** Not viable: the user decided to drop 1.0, and the code change is verified.

**Option 3 — MVP review.** Not needed: no capability, gate or phase changes scope.

**Rationale.** The code already runs on 1.1 only. The documents are now the only place that claims a 1.0 floor, and agents read them as rules (`project-context.md` tells agents to keep "both blocking CI legs" green). Leaving them invites an agent to restore 1.0 compatibility code.

## 4. Detailed Change Proposals

Paths: `A/` = `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/`.

### 4.1 Architecture — `A/ARCHITECTURE-SPINE.md`

**E1. AD-11 Rule (line 125).**

OLD:
> Supported: FreeCAD 1.0.x (floor, blocking CI) and 1.1.x (primary, blocking); 1.2-dev weekly is an allowed-to-fail canary; 0.21 unsupported. … Round-trip fixtures are authored on 1.0.

NEW:
> Supported: FreeCAD 1.1.x (blocking CI; the latest patch on conda-forge, 1.1.3 at 2026-10-03); 1.2-dev weekly is an allowed-to-fail canary; 1.0.x and 0.21 are unsupported (decision 016). … Round-trip fixtures authored on 1.0 still load on 1.1; new fixtures are authored on 1.1.

(The middle of the rule — one shim module, capability probes, never version-string comparisons — is unchanged.)

Rationale: user decision; CI and code already match.

**E2. AD-13 Rule (line 141), three sentences.**

OLD:
> it resolves to exactly one frame for a given shape on every supported FreeCAD leg, or it raises. `largest_planar_face` therefore carries a mandatory tie-break (…), because `Shape.Faces` order differs across legs and an untied frame flips the origin on a symmetric part. … A spec whose anchor frame does not resolve identically on the floor and primary legs is a broken spec, not a failing part — otherwise AD-14 reads the leg gap as overfitting.

NEW:
> it resolves to exactly one frame for a given shape on the supported FreeCAD build, or it raises. `largest_planar_face` therefore carries a mandatory tie-break (…), because `Shape.Faces` order is not a stable contract across builds and an untied frame flips the origin on a symmetric part. … A spec whose built part's anchor frame does not equal its committed 1.1.x reference frame is a broken spec, not a failing part — otherwise a frame that moves after a FreeCAD update reads as a failing part.

Rationale: G3.E.3 is now the single-leg reference check (spec D5).

**E3. Stack table (lines 393–394).**

OLD:
> | Python | matches the bundled interpreter per FreeCAD leg: 3.11 (1.0.x) / 3.12 (1.1.x); external process pins per CI leg |
> | FreeCAD | 1.0.x floor / 1.1.x primary (latest patch **available on conda-forge** — feedstock lags point releases) / 1.2-dev canary (…) |

NEW:
> | Python | floor 3.11 (`requires-python >=3.11`); CI runs the FreeCAD 1.1.x conda-forge build on 3.11; a local Windows env may run 3.12 because conda-forge ships no win-64 1.1.3 build for 3.11 |
> | FreeCAD | 1.1.x (latest patch **available on conda-forge** — feedstock lags point releases; 1.1.3 at 2026-10-03) / 1.2-dev canary (…) |

**E4. Repository tree comment (line 449).**

OLD: `.github/workflows/  # ci.yml: matrix {1.0.x, 1.1.x} blocking + 1.2-dev canary`
NEW: `.github/workflows/  # ci.yml: one blocking 1.1.x leg + 1.2-dev canary`

### 4.2 Architecture — `A/design/project-structure.md`

**E5. Addon metadata example (line 180).** OLD `<freecadmin>1.0</freecadmin>` → NEW `<freecadmin>1.1</freecadmin>`.

**E6. Version table (lines 202–208).**

OLD:
> | floor | 1.0.x latest patch on conda-forge | 3.11 | micromamba conda-forge | yes |
> | primary | 1.1.x latest patch on conda-forge | 3.12 | micromamba conda-forge | yes |
> | render | 1.1.x (same env as primary) | 3.12 | micromamba + xvfb + Mesa sw GL | no (isolated) |

NEW:
> | headless | 1.1.x latest patch on conda-forge (1.1.3) | 3.11 | micromamba conda-forge | yes |
> | render | 1.1.x (same build as headless) | 3.11 | micromamba + xvfb + Mesa sw GL | no (isolated) |

(The canary and arch/fast rows are unchanged. Section heading "per CI leg" stays.)

**E7. Syntax rule (line 210).**

OLD: `requires-python = ">=3.11"`; no 3.10-or-lower syntax; 3.12-only syntax banned until the 1.0.x leg retires.
NEW: `requires-python = ">=3.11"`; no 3.10-or-lower syntax; 3.12-only syntax banned while the CI 1.1.x leg runs Python 3.11.

**E8. CI job table (line 247).**

OLD: `| headless | {freecad: 1.0.x/py3.11, 1.1.x/py3.12} fail-fast: false | … | yes (both legs, G0.4) |`
NEW: `| headless | {freecad: 1.1.x/py3.11} | … | yes (G0.4) |`

**E9. CI YAML example (lines 258–260).** Replace the two `include` rows with `- { freecad: "1.1.*", python: "3.11" }`.

### 4.3 Architecture — other design documents

**E10. `A/design/integration-mcp-freecad.md` §5 (lines 248–253).**

OLD:
> All version-matrix findings (1.0.x floor / 1.1.x primary; `Support`→`AttachmentSupport` rename PR #12714; VarSet limited exposure issue #12531) reduce to:
> … probes hasattr(obj, 'AttachmentSupport') (1.x), falls back to 'Support' (legacy leg only). Raises ShimUnsupported if neither exists.

NEW:
> All version findings for the supported FreeCAD 1.1.x build (the `Support`→`AttachmentSupport` rename PR #12714 predates 1.1; VarSet limited exposure issue #12531) reduce to:
> … probes hasattr(obj, 'AttachmentSupport'). Raises ShimUnsupported if it does not exist.

**E11. `A/design/data-contracts-design.md` line 105.** OLD `# e.g. "1.0.2" — required` → NEW `# e.g. "1.1.3" — required`.

**E12. `A/design/skills-structure-design.md`.**
- Line 66: OLD `freecad-versions: ['1.0', '1.1']` → NEW `freecad-versions: ['1.1']`.
- Line 104: OLD `(… matches CI matrix, AD-11)` → NEW `(… matches the CI FreeCAD build, AD-11)`.
- Line 168: OLD `blocking on both matrix legs` → NEW `blocking on the 1.1.x CI leg`.

### 4.4 Requirements — `_bmad-output/specs/spec-freecad-buddy/`

**E13. `SPEC.md` line 22 (CAP-1 success).** OLD `≥30 CI tests green on the 1.0/1.1 matrix` → NEW `≥30 CI tests green on the FreeCAD 1.1.x CI leg`.

**E14. `SPEC.md` line 122.** OLD `on the FreeCAD 1.0.x + 1.1.x matrix (AD-11)` → NEW `on the FreeCAD 1.1.x CI leg (AD-11)`.

**E15. `phase-gates.md` line 28 (G0.4).**

OLD: `| G0.4 | Headless CI green on matrix | Query CI run for HEAD: legs 1.0.x + 1.1.x | ≥30 tests, all green, both blocking legs |`
NEW: `| G0.4 | Headless CI green | Query CI run for HEAD: leg 1.1.x | ≥30 tests, all green, on the blocking 1.1.x leg |`

**E16. `phase-gates.md` line 65 (G2.4).** OLD `UNSUPPORTED never reported on matrix legs` → NEW `UNSUPPORTED never reported on the 1.1.x leg`.

### 4.5 Epics — `_bmad-output/planning-artifacts/epics.md`

**E17. NFR4 (line 114).**

OLD: All suites run headless in CI on the FreeCAD 1.0.x (Py 3.11) + 1.1.x (Py 3.12) blocking matrix + 1.2-dev canary; …
NEW: All suites run headless in CI on the blocking FreeCAD 1.1.x leg (Py 3.11) + 1.2-dev canary; …

**E18. Story 1.1 AC (line 275).**

OLD: `headless` matrix legs {FreeCAD 1.0.*/Py 3.11, 1.1.*/Py 3.12} execute with cached micromamba envs, both blocking (NFR4)
NEW: the `headless` leg {FreeCAD 1.1.*/Py 3.11} executes with a cached micromamba env, blocking (NFR4)

**E19. Story 1.10 AC (lines 483–484).** OLD `runs on both blocking legs` → NEW `runs on the blocking 1.1.x leg`; OLD `≥30 tests green both legs (G0.4)` → NEW `≥30 tests green on the 1.1.x leg (G0.4)`.

**E20. Story 3.8 AC (line 654).** OLD `**When** it completes on both legs` → NEW `**When** it completes on the 1.1.x leg`.

**E21. Story 4.2 AC (lines 687–689).**

OLD:
> **Given** each spec's declared anchor frame (…)
> **When** the frame resolves on the floor and primary FreeCAD legs
> **Then** it resolves identically on both, or the spec is broken rather than the part failing

NEW:
> **Given** each spec's declared anchor frame (…)
> **When** the frame of each built part resolves on FreeCAD 1.1.x
> **Then** it equals the committed 1.1.x reference frame, or the spec is broken rather than the part failing

### 4.6 Agent rules — `_bmad-output/project-context.md`

**E22. Lines 20–21.**

OLD:
> - Python: match the CI leg's bundled FreeCAD interpreter — 3.11 (FreeCAD 1.0.x leg) / 3.12 (1.1.x leg). `requires-python = ">=3.11"`; no 3.12-only syntax until the 1.0.x leg retires.
> - FreeCAD: 1.0.x floor + 1.1.x primary (both blocking in CI, conda-forge via micromamba); 1.2-dev weekly canary allowed-to-fail. 0.21 unsupported — never write compat code for it.

NEW:
> - Python: `requires-python = ">=3.11"`; CI runs FreeCAD 1.1.x on Python 3.11, so no 3.12-only syntax. A local Windows env may run 3.12 (no win-64 1.1.3 build for 3.11).
> - FreeCAD: 1.1.x only (blocking in CI, conda-forge via micromamba); 1.2-dev weekly canary allowed-to-fail. 1.0.x and 0.21 unsupported — never write compat code for them.

**E23. Line 77.** OLD `Both blocking CI legs (1.0.x + 1.1.x) must stay green` → NEW `The blocking CI leg (1.1.x) must stay green`.

**E24. Line 79.** OLD `Round-trip fixtures are authored on FreeCAD 1.0 (1.1 core-datum files won't open in 1.0).` → NEW `Round-trip fixtures authored on FreeCAD 1.0 still load on 1.1; author new fixtures on 1.1.`

### 4.7 Intent — `docs/intent.md`

**E25. Line 352 (risk table).** OLD mitigation `Pin supported versions, CI matrix across versions, thin adapter layer over version-sensitive calls` → NEW `Pin the supported version (FreeCAD 1.1.x), CI on that build, thin adapter layer over version-sensitive calls`.

**E26. Line 150.** OLD `(version-pinned, same versions as CI matrix)` → NEW `(version-pinned, same version as CI)`.

### 4.8 Decision notes — `docs/decisions/`

**E27. New `016-freecad-1-1-only.md`.** Decision: FreeCAD 1.1.x is the only supported build; 1.0.x is dropped. Records: CI pin 1.1.3 / Python 3.11 (linux-64); local Windows env Python 3.12; reference source tag 1.1.4; G0.4 and G3.E.3 single-leg definitions; capability probes kept; rationale (1.0.0 failures, cost of two green legs); supersedes the 1.0 parts of AD-11, ADRs 001, 002 and 006. Same section layout as ADR 015.

**E28. ADRs 001, 002, 006 — append one section, keep the original text.**
- 001: "Superseded in part by 016 (2026-10-03): 1.0.0 is no longer a leg. On FreeCAD 1.1.3 `shim.export_binary_available()` returns `True`."
- 002: "Superseded in part by 016 (2026-10-03): one CI leg, FreeCAD 1.1.3. Its conda-forge linux-64 build runs Python 3.11; the local win-64 env runs 3.12.14."
- 006: "Superseded in part by 016 (2026-10-03): the 1.0.0/py3.11 question is retired. On FreeCAD 1.1.3, H1 is viable: the env interpreter imports FreeCAD, and the G3 replay runs over the H1 stdio host."

## 5. Implementation Handoff

**Scope: Minor.** Documentation edits only; the code change is done and verified (`753ea93`).

**Recipient:** Developer agent (this session). Apply E1–E28 exactly, edit no historical record, and commit after user approval.

**Success criteria:**
- `grep -rniE "1\.0\.x|floor leg|both legs|both blocking|floor and primary|1\.0/1\.1" ` over `_bmad-output/planning-artifacts/architecture`, `_bmad-output/planning-artifacts/epics.md`, `_bmad-output/specs`, `_bmad-output/project-context.md` and `docs/intent.md` returns no hit that describes a supported 1.0 leg.
- ADR 016 exists; ADRs 001, 002 and 006 carry the superseded-in-part note.
- `sprint-status.yaml` unchanged (no epic or story added, removed or renumbered).

## Checklist Record

| Item | Status | Note |
|---|---|---|
| 1.1 Trigger story | [x] | Story 4.2b; user decision 2026-10-03 |
| 1.2 Problem | [x] | Strategic change of supported platform |
| 1.3 Evidence | [x] | 1.0.0 baseline failures; 1.1.3 verification in §1 |
| 2.1–2.5 Epics | [x] | No epic change; wording in NFR4 and 4 story ACs |
| 3.1 PRD/SPEC | [x] | E13–E16; MVP unaffected |
| 3.2 Architecture | [x] | E1–E12 |
| 3.3 UX | [N/A] | No UX document |
| 3.4 Other artifacts | [x] | E22–E28; CI already changed in `753ea93` |
| 4.1 Direct adjustment | Viable | Selected |
| 4.2 Rollback | Not viable | — |
| 4.3 MVP review | Not viable | Not needed |
| 5.x Proposal | [x] | This document |
| 6.4 sprint-status | [N/A] | No epic or story change |

## Approval and Execution

- Approved by TanNT on 2026-10-03 (batch mode).
- Applied the same day: E1–E28, plus `epics.md` line 483 (Story 1.10 AC, added to E19 during execution).
- Success-criteria grep: the only remaining hits state that 1.0.x is unsupported (spine AD-11, `project-context.md`), or use "legs" for the geometry and visual-review channels (`design/sequence-diagrams.md:254`).
- `sprint-status.yaml`: unchanged.
