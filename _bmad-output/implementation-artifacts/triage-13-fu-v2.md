# Story 13-fu verifier round 2: leader triage

Base: 3287bd29 (story/13-followups; product code = 04adaafa). Report: `verify-13-fu-r2.md` (D1).
Each non-doc fix needs a test that fails first.

| # | Source | Finding | Required fix |
| --- | --- | --- | --- |
| T1 | verifier-13-fu r2 D1 (medium, product regression) | The section shortcut (`queries.py:871-874`) skips `distToShape` when `section` shows the boundaries meet and the fuse "proves touching". Across a small real gap at an edge, a vertex or a curved surface the fuse keeps two solids with volume = sum, so the proof passes and `min_distance` reads 0: edge gap 1.5e-7 (true 2.12e-7); sphere-sphere / sphere-box 1.5e-7 and 2e-7; with shape tolerance 1e-2, edge/vertex/sphere gaps 1e-3, 5e-3 and sphere gaps up to 0.02 mm read 0. Base 8049378d returns the true distance. The comment at `:866-868` is wrong for these layouts; test `:966` covers face gaps only. | Remove the section shortcut (leader decision: smallest reversible step; the fuse proof cannot tell a tiny gap from contact without `distToShape`). `distToShape` runs again for every trusted pair; the fuse runs only when it returns <= 1e-7, as at 8049378d. Keep T1 (interpenetration probe), T2 (1.5e-12 limit) and T3-T6 from triage-13-fu-rt.md. Add infc tests from the verifier's gap sweep (edge gap 1.5e-7, sphere gap 2e-7, tolerance-1e-2 edge gap 1e-3) asserting the true distance (red at 04adaafa, green after). Restore RT-5 as a `deferred-work.md` entry (blocker: no measured cost bound for `distToShape` with many contact solutions; unblock: a bound that keeps the true distance, or the AD-27 worker decision 45) and state the cost gap in the T-2 cost text and the code comment. Remove the now-dead counter test of the shortcut. Regression risk: nested/touching results change — neighbours: nested sphere tests, face/edge/vertex touch tests, TC-17. |

## After the fix
Gates: full infc, `tests/external` (Git Bash), ruff, check_imports, check_status_vocab, gen_schemas --check, check_skill_shape, check_provenance. The fix removes code: no new lens round. verifier-13-fu re-runs the gap sweep and TC-17 in the container.
