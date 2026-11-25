# Story 13-6: quality bar

Base: 116377e. Plan: builder-13-6 plan (approved 2026-11-24), `epic-13-plan.md` section 13-6.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | Input adds `objects: string[]` (1..50); exactly one of `object`/`objects`; both, neither, empty, >50, non-list or non-string items → `INVALID_INPUT` | tool-contracts.md T-2 | infc tests, one per case |
| Q2 | `objects` output `{ "objects": [record...] }` in input order (duplicates kept); each record is today's single-object record plus `is_valid: bool` | T-2; decision 8 (no `solids`) | infc test compares a record with the `object` path record for the same object |
| Q3 | An object with no shape (or a null shape) in `objects` gives `{ "name": N, "shape": null }` and the call stays `OK` | T-2; M-9 | infc test |
| Q4 | An unknown name in `objects` → whole call `INVALID_INPUT` naming it (as `object` today) | leader decision 21 | infc test |
| Q5 | `object` path keeps today's record and errors, plus `is_valid` (no-shape still `INVALID_INPUT`) | T-2; AD-28 additive | existing tests green + is_valid test |
| Q6 | `is_valid` is the shape's own `isValid()`; a planted invalid shape reads `false` | CAP-1 | infc test with an invalid shape (if FreeCAD can build one) or a documented NOT RUN with reason |
| Q7 | Values equal a script reading the same objects (bbox, volume, validity) — CAP-1 replay | SPEC CAP-1 success | infc test or verifier replay |
| Q8 | Schema additive, `gen_schemas.py --check` clean; `mcp-tools-design.md` §2 row and §3 schema match code; AD-1 rings | AD-28, AD-1 | gates; read |

Levels marked RUN: Unit (`uv run pytest tests/external -q`), Integration (freecadcmd `tests/run_tests.py`). UAT: one live call with `objects` in the container, batched with the 13-5 container run if the image is rebuilt from the integration branch after both merge; else by the 13-6 verifier.
