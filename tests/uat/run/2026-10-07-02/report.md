# UAT run 2026-10-07-02: Story 11.4 rollback proof and fingerprint cost

FreeCAD 1.1.4. Document: copies of `kiwibox-drawer.FCStd` (184 objects) in the session scratchpad. The original file is unchanged.
Script: `scripts/automation/time_mutation_overhead.py` (headless with FreeCADCmd; GUI as a macro passed to `freecad.exe`).

## Timing

Change: `duct_pilot.Length` 6.0 -> 5.5 mm. Median of 5, in seconds. Overhead = tool time (T) minus a plain recompute of the same change (R). Each T starts with a warm gate: the script fingerprints the document untimed after R, as the previous call does in an agent loop.

| Run | T | R | T − R | Abort run |
| --- | --- | --- | --- | --- |
| Headless, baseline `118e765` | 80.05 | 30.16 | 49.43 | 84.2 s, `rolled_back_via_snapshot`, document closed and reopened |
| Headless, Story 11.4 | 44.47 | 26.87 | 17.60 | 40.0 s, `rolled_back_verified`, same document, no close |
| GUI, Story 11.4 | 24.89 | 15.54 | 9.40 | 23.1 s, `rolled_back_verified`, same document, no close |

Criterion: ≤ 18 s headless and ≤ 10 s GUI: **met**. The first call after open pays a full fingerprint (headless 31.6 s, GUI 15.9 s). Cold-gate profile of the rest (`headless-profile-new.txt`): `fingerprint` × 2 11.2 s, `verify_shape` `isValid` 5.3 s, `features._feature_state` 5.5 s, `saveCopy` 2.5 s.

## Checks

- Audit (`gui-audit.jsonl`): on all 5 calls, the approval line and both mutation lines carry the same `fingerprint_before`.
- Abort run: `rolled_back_verified` with differing digests (`592161694ed1` before, `bbf15e831fd6` after), so the proof passed on mass properties.
- After the run: `query_object duct_pilot` gives Length 6.0 mm; `verify_recompute` gives "Recompute clean: no errors."
- G2 per-case verdicts equal the baseline run (`g2-score-baseline.txt`, `g2-score-new.txt`). `verify_shape` re-score 11/11 (`g0-verify-shape-score-new.txt`).

## Visual check

`gui-01-fit-all-after-abort.png`, checked by the agent after `view_fit_viewport` (isometric, Part workbench so the Part Design task box is empty): the full drawer is in frame (front plate, tray, rear module, duct cover), the tree has no error marks, and no dialog is open. The tab is still `kiwibox-drawer-copy-gui : 1*`, so the document was not reopened from a snapshot.

Verdict: rollback proof, document identity and overhead criterion PASS.
