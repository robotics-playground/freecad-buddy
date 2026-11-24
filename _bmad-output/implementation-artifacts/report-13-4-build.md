# Report: Story 13-4 build

Branch `story/13-4-skill-routing-gap-list` (worktree `D:\Work\Personal\Sources\freecad-buddy-wt-13-4`), base 905e038. Result: edits done and verified, NOT committed (see Commit).

## Result
- New `skills/freecad-scripting-idioms/references/gap-list.md`: covered table (7 rows), gap table (18 rows), STEP import script, traced outline route.
- `freecad-scripting-idioms/SKILL.md`: gap-list pointer plus rule "state the missing typed tool before `script_exec`". Line 57 untouched.
- `code-cad-conversion`: `verification-kit.md` routes validity, solid count, volume to `verify_shape`/`query_mass_properties`/`verify_recompute`; scripts keep overlap, reference volume, VarSet set and restore; limit test is case script, typed checks, restore per case. `SKILL.md` two lines follow.
- `part-sourcing/SKILL.md`: no import path; import is `script_exec` (gap list script), `exec_enabled: false` means blocked.
- `verification-thinking`: no edit.
- Spec and triage log: `_bmad-output/implementation-artifacts/spec-13-4-skill-routing-gap-list.md` (written after the edits as a oneshot spec).

## Review (agent ids)
Blind Hunter adde9f60f12d90587 (opus-5-5/high, 9 findings); Edge Case Hunter a4a5f8f3b1cb416a1 (opus-5-5/high, 14); Verification Gap Finder a03bf1cac40ec12c5 (sonnet-5-5/medium, none). 13 groups patched, 2 rejected, 0 deferred. Details: spec Review Triage Log.

## Checks
- `uv run python scripts/check_skill_shape.py`: no output, exit 0 (before and after).
- Body words before/after: scripting-idioms 1292/1310, code-cad-conversion 1416/1424, part-sourcing 845/862, verification-thinking 1494/1494 (all at most 1,500).
- Grep `BoundBox|.Volume|isValid` in `skills/`: 10 lines before, 7 after. The 7 remaining: reference STEP volume and `common()` overlap (4 in verification-kit, no typed tool), interference and hole probe (2), gap-list row (1). Grep with `bbox|bounding box` added: 23 before, 22 after; the rest are spec text, not routes to `script_exec`.
- Q5: each tool and key shown checked against `tool_catalog.py` and `usecases/assertions.py`/`verify.py` (`fn`, `expect`, `tol.rel`, `expect_solid_count`, `verify_recompute`).

## Unverified
- `feature_set_parameters` on a VarSet is not tested; the gap row says only that it targets features.
- `Import.insert` snippet and the Groove/AdditiveBox type names are FreeCAD API from memory, not run in the container.
- CAP-6 live-session check batched with Stories 12/19 (quality bar).

## Commit
Not made. `CLAUDE.md` rule 1 needs the user's explicit approval per commit, and decision 13 is still open. Files changed: 4 modified under `skills/`, 1 new reference, 2 artifacts under `_bmad-output/implementation-artifacts/`. Suggested message: `docs(skills): route covered reads to typed tools and add the gap list`.
