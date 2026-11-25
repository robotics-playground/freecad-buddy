# Story 13-18 triage: round 2 (red team + verifier)

Base: d8968a1e on `story/13-18-loft-sweep`. Sources (this folder): `redteam-13-18.md` (RT-1 .. RT-6), `verify-13-18.md` (F1, N1). Use their reproductions as failing tests first. Leader decision 39.

| Id | Source | Required fix |
| --- | --- | --- |
| RT-1 (high) | red team | Loft cost grows with the square of edges per section (two 3,999-gons: 111 s; circle to 4,000-gon: 317 s; OCC recompute itself). Replace the linear edge-unit guard with a measured model, e.g. the sum over adjacent section pairs of edges(i) × edges(i+1) (plus the profile), and set the limit from timings so the worst accepted loft stays well inside the budget. Document the measurement beside the constant; test both sides with the red team's sections. |
| F1 (medium) | verifier | Sweeps at the 10,000-unit limit take 13–32 s (circle along a 10,000-segment polyline), not the 5.8 s the design cites. Lower or remodel the sweep limit so the worst accepted sweep is measured and documented truthfully (aim for the same margin as the loft). |
| RT-2 (high) | red team | A sweep returns OK for degenerate results (spine in the profile plane, a spine that reverses at a vertex → volume 0; subtractive leaves the Body at volume 0; a self-intersecting sweep OK, frenet `is_valid` false with 2 solids). After recompute, check the new feature's own shape: valid, one solid, positive volume added (additive) or removed (subtractive); otherwise `RECOMPUTE_ERROR` with a `detail.code` (reuse `transaction.RecomputeFailure`), rollback proven. Apply the same post-check to loft. Test every case. |
| RT-3 (medium) | red team | A subtractive loft in an empty Body adds 4,666 mm³ and returns OK (sweep refuses it). Refuse subtractive loft with no base solid, like sweep. Test. |
| RT-6 (low) | red team | A subtractive loft or sweep that misses the solid returns OK and removes nothing. Covered by the RT-2 post-check (removed volume must be positive) → `RECOMPUTE_ERROR` with a code. Test. |
| RT-4 (medium) | red team | A valid `Part::Helix` thread of 120+ turns is refused as `sweep.degenerate_spine` (FreeCAD builds it valid in 0.85 s). Make the degenerate-spine check accept helices (or measure tangent reversal correctly on long helical spines) without letting the 280 s doubling-back spine through; keep both tests. |
| RT-5 (low) | red team | An unresolvable spine selector (`Edge9`) is refused without a `detail.code`. Add one. |
| N1 (cosmetic) | verifier | Profile and spine sketches stay visible after a subtractive sweep; the GUI hides them. Hide the profile and spine sketches after a successful loft/sweep (in the transaction), as the GUI does; test the Visibility. |

## After the fixes

1. Commit on your branch yourself (no trailer).
2. Core checks changed: run three fresh lenses (round 2) on d8968a1e..HEAD with `quality-bar-13-18.md`; patch high/medium; commit.
3. External (Git Bash, `uv run --extra dev`), infc (FREECAD_USER_HOME temp); reply with SHA, lens ids, counts and the new limits with timings in at most 10 lines.
