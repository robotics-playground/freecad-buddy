# UAT run 2026-10-07-03: Story 11.6 measured build session

FreeCAD 1.1.4 GUI, freecad-buddy at `31d9318` (Stories 11.1-11.5). Auto-approve on (`addon.log`: `SECURITY: mutation auto-approve ENABLED`). Skills copied from `skills/` into `D:/Work/3D Printers/Ender 3V2 - Klipper/.claude/skills` before the session.

## Session under test

- Claude Code session `a3153685` (Opus 5.5, `bypassPermissions`, the same mode as the baseline), started by the developer agent through `cua-driver` in the Ender 3V2 project.
- Prompt: `evidence/build-prompt.txt` (exact text). The prompt asks for a rebuild of the kiwibox drawer from scratch into a new file, `cad/kiwibox-drawer-rebuild.FCStd`. It follows plan Tasks 4, 5, 5a, 6, 7, 7a and the model steps of 8a. It forbids changes to existing files, exports, commits, and subagents for FreeCAD work. The human told the developer agent to run the session itself, so the agent that knew the targets wrote the prompt. The prompt names no target and gives no rule about calls, previews, verification or screenshots.
- Result: 178 objects, 5 bodies. FreeCAD calls ran 15:10-15:38 UTC (27 min). The SHA-256 of every file in `cad/` and `exports/` is unchanged.
- The task is different from the baseline. `0320ba38` was an iterative edit session on the same drawer, driven by user requests, with a screenshot after many features (44 in total). This session is a rebuild from a written plan, and a rebuild needs fewer looks at the model. Read the drop in calls per feature and in previews with that difference in mind. The output-size rows (chars per call, spilled, largest) depend on the result envelope, not on the task. The other two sessions from 2026-10-06 are in the table as extra reference.

## Transcript metrics (AC1, AC2)

Script: `scripts/automation/session_metrics.py`. Output: `evidence/baseline-metrics.txt`, `evidence/build-metrics.txt`. The baseline is the first 310 FreeCAD results of `0320ba38`; the transcript grew to 424 after the change proposal.

| Measure | Proposal (`0320ba38`) | Script, baseline `0320ba38` | Script, new `a3153685` | Target | Verdict | Reference `eacac40d` | Reference `ff604ce5` |
|---|---|---|---|---|---|---|---|
| FreeCAD calls | 310 | 310 | 220 | — | — | 98 | 107 |
| `preview_dry_run` calls | 77 | 77 | 2 | — | — | 36 | 39 |
| Output chars per FreeCAD call | 9,590 | 9,583 | 1,413 | ≤ 1,437 (15 %) | PASS | 5,434 | 7,167 |
| Spilled results | 15 | 14 | 0 | 0 | PASS | 0 | 1 |
| Largest result | 109K | 110,267 | 11,612 | ≤ 10,000 | **FAIL** | 14,407 | 55,105 |
| FreeCAD calls per feature (median) | 6 | 7.5 | 3 | ≤ 3 | PASS | 6.0 | 6.0 |
| Peak context (tokens) | 820K | 819,990 | 582,489 | — | — | 817,762 | 797,499 |
| Compactions | 8 | 4 | 0 | — | — | 0 | 0 |

- Output chars are the text the agent received. A spilled result counts its stub; its size from the stub counts for "largest". Image blocks count 0 chars (the new session has 3 `query_screenshot` calls, the baseline 44).
- Proposal and script differ in three rows:
  - Compactions: the proposal counted 8 because it counted each `compact_boundary` record and its summary record. The script counts the boundaries only.
  - Calls per feature: the proposal's 6 is the call chain of one typical feature (`DRY(sketch_create) > sketch_create > … > feature_pocket`). It is not a measured median.
  - Spilled results: the proposal reported 15 and the script finds 14. The cause was not found.
- Calls per feature: a feature is an `OK` result of a `feature_*` tool other than `feature_set_parameters`. Its calls are every FreeCAD call since the previous feature, so the first feature gives no sample. The rule counts bodies and datums as features. With bodies and datums excluded (`evidence/solid_feature_median.py`, output `evidence/secondary-median.txt`), the median is 3 over 51 features against 10 for the baseline. The verdict does not depend on that choice.
- Largest result: `query_tree_summary` with `root: front_plate_piece`, `depth: 3` and no type filter returned 11,612 chars; its compact `tree` is 11,115 of them. No mutation result exceeded 3,236 chars.
- A mutation result is 1.2K-1.5K chars. Of that, about 280 chars are the two `fingerprint_*` digest objects. The rest is `post_verify` (one `tnp_audit` count line), `changed`, `sketch_state` or `feature_state`, and `framing`.

### Checks per mutation

The session made 190 mutation-tool calls (`sketch_*`, `feature_*`):
- 189 returned `OK`. Each carried `post_verify` with `recompute_clean`, `is_valid`, `fully_constrained` and `tnp_audit`, and every `tnp_audit` was `CLEAN`.
- 1 `feature_body_create` (FreeCAD call 139) was refused with `INVALID_INPUT`, `base_feature drawer is already adopted by a Body`. The input check refused it before any transaction, so it changed nothing.

`evidence/build-audit.jsonl` has 189 `approval` lines: 188 with mode `auto_approve` and 1 with `display_state`. Two read-only calls were also refused with `INVALID_INPUT`: a `preview_dry_run` with a `geometric` edge selector, and a `verify_shape` check without `expect`. No mutation was rolled back in this session, so it does not show a rollback. The G2 runs of Stories 11.1-11.4 cover rollback.

## Bridge overhead (AC3)

Method: Story 11.4, `scripts/automation/time_mutation_overhead.py` as a GUI macro on a copy of the rebuilt part. The script changes `duct_pilot.Length` from 6.0 to 5.5 mm (a Pocket the agent made), takes the median of 5, and starts each call with a warm gate. Overhead = tool time T − plain recompute R. The process is separate from the build session (human decision).

| Run | Median T | Median R | Median T − R | Samples T − R | Abort run |
|---|---|---|---|---|---|
| GUI (`gui-timing-rebuild.json`) | 25.13 | 15.71 | **9.34** | 15.77, 9.59, 9.29, 9.20, 9.34 | `rolled_back_via_snapshot`, document closed and reopened |
| GUI repeat (`gui-timing-rebuild-repeat.json`) | 25.33 | 15.86 | **9.48** | 16.17, 9.53, 9.41, 9.44, 9.48 | `rolled_back_via_snapshot`, document closed and reopened |
| Headless (`headless-timing-rebuild.json`) | 24.34 | 15.02 | 9.27 | 15.34, 9.27, 9.58, 9.17, 9.18 | `rolled_back_verified`, same document |
| Story 11.4 GUI, original drawer | 24.89 | 15.54 | 9.40 | — | `rolled_back_verified`, same document |

Criterion ≤ 10 s GUI: **PASS** (9.34 s and 9.48 s). The first sample is high because its gate is cold: the script fingerprints untimed only after each `R`, so the first `T`, right after the document opens, fingerprints every object. The median of 5 includes that sample, as in Story 11.4.

**Finding: the abort-path proof falls back to the snapshot in the GUI on this document.** It happened in 2 of 2 GUI runs. In the headless run on the same file, the proof passed on mass properties. A headless diagnostic (plain `abortTransaction` + `recompute` + fresh fingerprint) found 0 objects whose mass properties changed. The rollback was still proven, so no change was kept. The cost is a close and reopen (31.8 s and 32.1 s against 22.3 s headless), and the document object changes. The root cause is not known. The audit log does not name the objects that did not match. Each GUI run ended in `sys.exit(1)` from the script, which quits FreeCAD; that was not a crash.

## Native validation and visual check (AC4)

Per `freecad-native-validation.md`, driven with `cua-driver` in the build session's FreeCAD:

| Body | Check Geometry | Solids | Native volume (mm³) | r2 STL volume (mm³) | Verdict |
|---|---|---|---|---|---|
| front_plate_piece | 0 invalid shapes, No errors | 1 | 17,175.57 | 17,175.5 | PASS |
| tray_piece | 0 invalid shapes, No errors | 1 | 50,230.91 | 50,245.6 | PASS (−0.03 %) |
| rear_module_piece | 0 invalid shapes, No errors | 1 | 12,703.28 | 12,703.6 | PASS |
| duct_cover | 0 invalid shapes, No errors | 1 | 11,224.91 | 11,227.8 | PASS (−0.03 %) |
| drawer (master, hidden) | 0 invalid shapes, No errors | 1 | 79,410.62 | — | PASS |

The reference volumes are computed from the r2 STL exports committed in the Ender 3V2 project (`evidence/r2-stl-volumes.txt`). The volume band was ±0.5 %, set before the check. It allows for STL tessellation and for the build agent's notes on how it read the plan. Every piece is within 0.03 %.

The macro rows (`evidence/native-fc_measure.json`) give the same volumes and give the bounding boxes. Screenshot `native-cg-tray_piece.png` shows the Check Geometry result. The Shape Content text for each body is in `native-shape-content-*.txt`.

Visual check by the developer agent: `native-fitall-iso-all.png` (FreeCAD Fit all, isometric), compared with `docs/images/kiwibox-drawer-r2-board-iso.png` in the Ender project. The layout matches: front plate with SMA boss, duct cover with the notch and 3 countersunk holes (`native-fitsel-iso-duct_cover.png`), tray with rail ribs (`native-fitsel-iso-tray_piece.png`), and rear module with the vent comb. The curved duct wall is under the cover plate and does not show from this angle; its volume agrees within 0.03 %. Several yellow datum planes stay visible and cover part of the view. That is display state only.

## Other findings

- The build agent made the pieces without `Part::Common`, because no MCP tool makes one. Each piece body starts from a base-feature copy, and pockets remove the other regions. `tray_piece` and `rear_module_piece` take their base from another piece. In every recompute, FreeCAD logs `Link(s) to object(s) 'BaseFeature' go out of the allowed scope 'tray_piece'`.
- The agent reported a 0.05 mm wall at the duct cover countersink (X 11.5, Y 6.7). The spec values cause it.

## Verdict

| AC | Result |
|---|---|
| AC1 metrics script | PASS: reproduces the baseline; 9 unit tests |
| AC2 targets | 3 of 4 PASS; largest result 11,612 > 10,000 FAIL |
| AC3 overhead ≤ 10 s GUI | PASS (9.34 s, 9.48 s); abort-path proof falls back to the snapshot in the GUI on this document |
| AC4 visual + Check Geometry | PASS |
| AC5 report | this file |
