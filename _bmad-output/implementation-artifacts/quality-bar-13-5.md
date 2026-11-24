# Story 13-5: quality bar

Base: 6c60a23. Plan: builder-13-5 plan + `spec-13-5-multi-object-export.md` (worktree wt-13-5), approved 2026-11-24.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | `export_step`, `export_3mf`, `export_stl` accept `objects` with more than one name; the "export supports a single object" refusal is gone | T-5 tool-contracts.md:180-182 | infc tests; container UAT TC-07 |
| Q2 | Omitted `objects` = all visible solids per `mcp-tools-design.md` §3.5 (the plan's rule: not consumed by another candidate, not inside a Body/Part group as a separate entry); an empty selection is refused with `INVALID_INPUT` | §3.5, M-7 | infc tests incl. a Body with several features (only the Body tip exports) |
| Q3 | STEP: one solid set per object, `Label` as the STEP product name (read back from the written file) | tool-contracts.md:186 | infc test reads product names from the file |
| Q4 | 3MF: one mesh object per input object, `name` = `Label` (stdlib post-write rewrite of `3D/3dmodel.model`), and the archive stays a valid 3MF (lib3mf opens it; other parts unchanged) | tool-contracts.md:187; leader decision 20 | external + infc tests; lib3mf read-back |
| Q5 | STL: one merged mesh | tool-contracts.md:188 | infc test |
| Q6 | `verify_export_step` and `verify_export_3mf` compare per-object volume and the total; a per-object mismatch fails the verdict and names the object; STL verifies total only | tool-contracts.md:190-191; decision 6 | external oracle tests with a planted per-object mismatch that turns the verdict red |
| Q7 | Single-object export and verify keep their numbers and messages (K-1) | keep-problem-try.md K-1 | existing tests unchanged and green |
| Q8 | An object with no shape/solid in the selection is refused with `INVALID_INPUT` naming it | epic-13-plan.md 13-5 risk | test |
| Q9 | Schema changes additive (AD-28); FreeCAD only via `usecases/shim.py` (AD-1) | AD-28, AD-1 | `gen_schemas.py --check`; `check_imports.py` |
| Q10 | `verification-design.md` §6 and `mcp-tools-design.md` §3.5 describe the shipped behaviour (per-object checks, 3MF name step, STEP order matching) | T-5 authorises §6 | read |
| Q11 | Three-body document exported to each format in the container passes its `verify_export_*` with per-object volumes; the file opens in FreeCAD GUI (visual check) | CAP-3, done_checkpoint | container UAT (verifier); user review at the done checkpoint |

Levels marked RUN: Unit (`uv run pytest tests/external -q`), Integration (freecadcmd `tests/run_tests.py`), UAT (container TC-07 by the verifier).
