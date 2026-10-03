# 016 — FreeCAD 1.1 Only: The 1.0.x Floor Leg Is Dropped

## Decision

FreeCAD 1.1.x is the only supported build. FreeCAD 1.0.x is no longer supported, tested or
gated. The 1.2-dev weekly canary stays allowed-to-fail; 0.21 stays unsupported.

- **CI** runs one blocking headless leg: `freecad=1.1.3`, `python=3.11` (conda-forge, linux-64).
  The render job uses the same build. 1.1.3 is the latest 1.1 patch conda-forge ships; there is
  no 1.1.4 package.
- **Local envs** run `freecad=1.1.3` on Python 3.12, because conda-forge ships no win-64 1.1.3
  build for Python 3.11 (its builds are py310, py312, py313, py314).
- **Python floor** stays `requires-python >=3.11` with ruff `py311`, because the CI build runs 3.11.
- **Reference source** `docs/references/FreeCAD` is pinned to tag `1.1.4` for source checks.
- **Gates.** G0.4 requires only the 1.1.x leg evidence and ignores a 1.0.x file. G3.E.3 reads
  "every built part's anchor frame equals the committed 1.1.x reference": a frame that changes
  between runs or after a FreeCAD update fails it.
- **Code.** Pattern modes accept only the 1.1 members `Extent` and `Spacing`. The capability
  probes (exportBinary/exportBrep, VarSet/Spreadsheet, element map) stay: they are probes, not
  1.0 branches.

## Rationale

1. **The user decided it** on 2026-10-03, during Story 4.2b.
2. **Two legs cost more than they protect.** On FreeCAD 1.0.0 the in-FreeCAD suite had 2
   failures and 1 error at baseline `479e44e`: a linear pattern's default occurrences and the
   pattern `Mode` spellings (`length`/`offset` against `Extent`/`Spacing`) differ from 1.1. The
   1.0 leg stopped before its later steps, including the G3 replay, and every new feature had to
   be written and tested twice.
3. **1.1.3 meets the plan.** On FreeCAD 1.1.3 the in-FreeCAD suite runs 674 tests OK, the
   external suite passes apart from 5 known G1 grader-hash tests, and the G3 corrupted-plan
   replay detects 10/10 planted defects with 0/14 false alarms and frames equal to the
   reference. `shim.export_binary_available()` is `True`, `shim.varset_backend()` is `varset`,
   `shim.element_map_available()` is `True`, and H1 (`import FreeCAD` in the env interpreter)
   works.

## Consequences

- AD-11 lists FreeCAD 1.1.x plus the 1.2-dev canary. AD-13 compares each built part's anchor
  frame with the committed 1.1.x reference instead of comparing two legs.
- Round-trip fixtures authored on 1.0 still load on 1.1; new fixtures are authored on 1.1.
- Moving to a later 1.1 patch, or to 1.2, is a deliberate edit of `ci.yml`, followed by a
  re-run of every scorer and of the G3 frame check.
- `addon/package.xml` declares `<freecadmin>1.1</freecadmin>`; every `SKILL.md` declares
  `freecad-versions: ['1.1']`.

## Related

- Supersedes the 1.0 parts of AD-11 and of decisions 001, 002 and 006.
- Implementation: commit `753ea93`, spec
  `_bmad-output/implementation-artifacts/spec-drop-freecad-1-0-support.md`.
- Sprint change proposal: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-10-03.md`.
