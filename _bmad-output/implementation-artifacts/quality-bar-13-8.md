# Story 13-8: quality bar

Base: 90303e36. Plan: builder-13-8 plan + `spec-13-8-query-section.md` (main tree, branch story/13-8-query-section), approved 2026-11-24 with decision 29.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | Input as T-2: `doc`, `object`, `plane {normal x|y|z|[nx,ny,nz], offset Quantity}`, optional `points {deflection, max_points ≤5000}`; zero normal, NaN, deflection below the floor → `INVALID_INPUT` | tool-contracts.md T-2 query_section; plan 3 | tests |
| Q2 | Output `wires`, `closed_wires`, `area`, `length`, `bbox`; values equal a script's `Shape.section` / `common` on the same plane (analytic cases: box, cylinder, plate with holes, bullseye islands) | T-2; CAP-1 | infc tests; verifier container replay |
| Q3 | A plane that misses → `OK`, `wires: 0`, `area: 0`, `length: 0`, `bbox: null`. A plane within 1e-5 mm of a face, or at a face, is not a false miss | T-2; builder probe (`slice` false miss) | infc tests at the probed offsets |
| Q4 | `area` is never 0 for an unmeasured section: when closed wires exist but the area cannot be measured → `area: null` | T-2 spirit (CAP-1 safety); plan 4 | test with a planted failure |
| Q5 | Untrusted input: invalid or reversed shapes → `INVALID_INPUT` `section.untrusted_shape`. Valid non-solid shapes (shell, face) are cut: wires, length, bbox measured, `area: null` | decision 29 | tests (invalid, reversed, valid shell) |
| Q6 | Cost: >10,000 faces → `INVALID_INPUT` `section.too_complex` before any cut; measurement beside the constant; one call stays well inside the 60 s budget | plan 2; 13-7 lesson | test both sides; verifier timing |
| Q7 | `points`: polylines in mm, stop at `max_points` total with `truncated` true; deflection floor prevents the `discretize(Deflection=0)` hang | T-2; plan 3 | tests |
| Q8 | Read-only: runs on `shape.copy()`; fresh fingerprint equal before and after; tool in `READ_ONLY_PROFILE` | T-2; 13-7 F1 lesson | tests |
| Q9 | Frame: the object's own shape frame (as `query_interference`), stated in the tool description and design | 13-7 RT-5 lesson | read |
| Q10 | Numbers only (AD-35); AD-17 closed set; AD-1 rings; `mcp-tools-design.md` §2/§3/counts match code; the small refactor keeps `query_interference` tests green | AD-35, AD-17, AD-1 | gates; infc |

Levels marked RUN: Unit, Integration (freecadcmd). UAT: container replay by the verifier.
