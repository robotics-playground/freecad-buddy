# Sprint Change Proposal 2026-11-18: AD-11 names the dev line, not "1.2-dev"

## 1. Issue summary

AD-11, the project-structure design and `epics.md` call the canary line "1.2-dev". FreeCAD never released "1.2". The weekly build `weekly-2026.09.16` is `26.3.0 dev`; the weekly build `weekly-2026.11.18` is `27.1.0 dev`. The canary workflow asked conda-forge for `freecad=1.2` and failed on every run (plan-10-8 section 5). The name misleads a reader and a builder.

Trigger: Story 10-8, slice 10-8-e. Decision 37 (user approval, 2026-11-18).

## 2. Impact analysis

- Epic impact: Epic 10, Story 10.8 only. No Epic or Story changes scope.
- Artifact conflicts: `ARCHITECTURE-SPINE.md` (3 lines), `design/project-structure.md` (4 clauses on 3 lines), `epics.md` (2 lines), `_bmad-output/project-context.md` (1 line).
- Technical impact: none in `src/`. `.github/workflows/canary.yml` changes in the same slice (spec-10-8-e).
- Tier: clauses 1 to 6 **architecture**, approved by the user on 2026-11-18 (decision 37). Clauses 7 to 9 **detail**, boundary = AD-11 as corrected by decision 37, plus decision 32 for clause 7 (decision 39). Clauses 10 and 11 **detail** (decision 41): clause 10 boundary = AD-11 as corrected by decision 37; clause 11 boundary = the canary row of `design/project-structure.md` (`:127`, `:235`) and `canary.yml` itself.

## 3. Recommended approach

Direct adjustment. Replace the clause "1.2-dev" with "the next FreeCAD development line (weekly builds)". The rule does not change: allowed-to-fail canary, conda-forge if published, else weekly AppImage. Smallest clause only. Clause 7 also names the conda-forge label the canary reads. Clauses 8 and 9 restate AD-11 in `epics.md`. Effort: eleven one-clause edits. Risk: none; no code reads these words. Rollback: one commit.

## 4. Detailed change proposals

Root `A` = `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/`. Owner Story: 10.8 (slice 10-8-e). Blocks a Story: no. Status: applied in the worktree `fcb-10-8-e`.

| # | Tier | Where | OLD | NEW |
| --- | --- | --- | --- | --- |
| 1 | architecture | `A/ARCHITECTURE-SPINE.md:126` | `1.2-dev weekly is an allowed-to-fail canary` | `the next FreeCAD development line (weekly builds) is an allowed-to-fail canary` |
| 2 | architecture | `A/ARCHITECTURE-SPINE.md:397` | `/ 1.2-dev canary (conda-forge if published, else weekly AppImage)` | `/ canary on the next FreeCAD development line, weekly builds (conda-forge if published, else weekly AppImage)` |
| 3 | architecture | `A/ARCHITECTURE-SPINE.md:452` | `ci.yml: one blocking 1.1.x leg + 1.2-dev canary` | `ci.yml: one blocking 1.1.x leg + canary on the next FreeCAD development line` |
| 4 | architecture | `A/design/project-structure.md:127` | `weekly 1.2-dev allowed-to-fail leg (AD-11)` | `weekly allowed-to-fail leg on the next FreeCAD development line (AD-11)` |
| 5 | architecture | `A/design/project-structure.md:235` | `\| canary \| 1.2-dev weekly \|` | `\| canary \| next FreeCAD development line (weekly builds) \|` |
| 6 | architecture | `A/design/project-structure.md:321` | `resolve FreeCAD 1.2-dev` | `resolve the next FreeCAD development line, weekly builds` |
| 7 | detail (AD-11 corrected, decision 32) | `A/design/project-structure.md:321` | `(conda-forge dev label if published` | `` (conda-forge label `main` if published `` |
| 8 | detail (restates AD-11) | `epics.md:114` | `+ 1.2-dev canary;` | `+ canary on the next FreeCAD development line (weekly builds);` |
| 9 | detail (restates AD-11) | `epics.md:276` | `weekly allowed-to-fail 1.2-dev leg` | `weekly allowed-to-fail leg on the next FreeCAD development line (weekly builds)` |
| 10 | detail (restates AD-11) | `_bmad-output/project-context.md:21` | `1.2-dev weekly canary allowed-to-fail.` | `a canary on the next FreeCAD development line (weekly builds) is allowed-to-fail.` |
| 11 | detail (file attribution) | `A/ARCHITECTURE-SPINE.md:452` | `# ci.yml: one blocking 1.1.x leg + canary on the next FreeCAD development line` | `# ci.yml: one blocking 1.1.x leg; canary.yml: canary on the next FreeCAD development line` |

Rationale for clause 11: the canary lives in `canary.yml`; the line before this batch named `ci.yml` as the canary file. Rationale for clauses 1 to 6 and 8 to 10: "1.2" never existed and will not exist; the line is named by its weekly builds. Rationale for clause 7: the canary reads label `main` (the `freecad_dev` label is empty), so the design names that label.

Kept: historical record, still says "1.2-dev": `docs/decisions/016-freecad-1-1-only.md:6` and `:39` (a dated decision record), `sprint-change-proposal-2026-10-03.md`, the architecture `.memlog.md`, the research notes and the review notes.

## 5. Implementation handoff

Scope: Minor. Developer agent applies the edits (done). Success criteria: `grep "1.2-dev"` on the two architecture documents and `epics.md` returns no line; `git diff` of those three planning documents shows only the eleven clauses (the grep also covers `_bmad-output/project-context.md`).
