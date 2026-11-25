# Verify: Epic 13 close

Head: `feat/epic-13-mcp-usage-improvement` @ `96894ab0`, worktree `freecad-buddy-int`.
Verifier: verifier-epic-13 (opus). Date: 2026-11-26.
Evidence: `tests/uat/run/epic-13-close/evidence/` (new, uncommitted).

## Verdict

**PASS.** One change waits for the leader to commit: `benchmarks/_registry/validators.yaml`.
The export validator hash was stale on the head, and the scorers refreshed it. No score dropped.

## 1. Validator re-score

Currency check before the re-score (runner `_validator_src_hasher` against the committed `validator_sha`):

| Validator | Committed head | Cause |
| --- | --- | --- |
| `verify_export_step` (cited by G0.5) | **STALE** (`ac477d9a…` committed, `f78af8ca…` live) | Epic 13 changed `usecases/exports.py` and `adapters/export_oracle.py` (commits `3527cc20`, `80e0b004`, `9af2ac84`). On `main` the hash is `ac477d9a…`, so the drift came from Epic 13 |
| `verify_export_stl`, `verify_export_3mf` | same old hash | Same sources. The runner has no source map for them, so no gate reads them |
| `verify_render_tone` | no runner source map | Not cited by a gate |
| all other 8 | CURRENT | — |

Scorers run (host FreeCAD 1.1.4 `freecadcmd` with private `-u`/`-s` cfg and private `FREECAD_USER_HOME`; uv env for the rest):

| Scorer | Exit | Result |
| --- | --- | --- |
| `g0/export-fault-injection/score_export_verify.py` (freecadcmd) | 0 | `verify_export_step` sensitivity 1.000, false alarm 0.000, Wilson [0.741, 1.000] |
| same (uv) | 0 | `verify_export_stl` and `verify_export_3mf` 1.000 / 0.000, Wilson [0.722, 1.000] |
| `g0/fault-injection/score_verify_shape.py` | 0 | planted 11, detected 11, false alarm 0 |
| `g2/fault-injection/score_g2_infc.py` | 1 | `assertions` 8/8, 0 of 3 controls flagged; `audit_references` 3/3, 0 of 6 flagged. Exit 1 is the known `NOT SCORED` set: `fingerprint`, `verify_sketch` (no cases), `run_mutation` (2 planted cases not driveable on 1.1.x). Same as verify-13-14 and verify-13-15 |
| `g1/fault-injection/score_grader.py` | 0 | planted 16, detected 16 |
| `g0/render-fault-injection/score_render_tone.py` | 0 | planted 6, detected 6 |
| `g2/fault-injection/score_g2_validators.py` (structural) | 0 | suite sound |
| `g3/fault-injection/score_g3_validators.py` | 0 | G3.E.4 OK (1.0 / 0.0, `validator_sha ec64cb67c715`) |
| `g3/fault-injection/score_g3_replay.py` | NOT RUN | Needs an interpreter with FreeCAD and `mcp`. `spec_assertions` is CURRENT, so its score stays valid |

`validators.yaml` diff (uncommitted, LF line endings, 25 lines):
- `validator_sha` of `verify_export_step`, `verify_export_stl` and `verify_export_3mf`: `ac477d9a…` → `f78af8ca27973b39d8da4418a2a48fe8a74c4656542a5b6a815a31fb521c0235`.
- `run_id` and `date` of every scored block → `2026-11-26`.
- No `sensitivity`, `false_alarm` or `wilson_ci` value changed.

After the re-score: all runner-mapped validators CURRENT. `check_provenance OK`.
`pytest tests/external/test_gate_g2_exit.py test_gate_verdict.py test_harness_g1.py`: 126 passed.
The full external run left `validators.yaml` byte-equal to the re-scored copy.

Note: `score_verify_shape.py` and `score_g2_infc.py` import `score_export_verify.py`. With `FREECAD_BUDDY_RUN_EXPORT_SCORER=1` set, the import runs the export scorer and exits, so the intended scorer does not run. Set only the flag of the scorer you run.

## 2. Gates on the final head

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `check_imports.py` | OK |
| `check_status_vocab.py` | OK |
| `gen_schemas.py --check` | OK |
| `check_skill_shape.py` | exit 0 |
| `check_provenance.py` | OK |
| `uv run --extra dev pytest tests/external -q` (Git Bash) | **2122 passed, 6 skipped, 0 failed** in 139.8 s. No timing-unstable test failed |
| `freecadcmd -u <tmp>/user.cfg -s <tmp>/system.cfg tests/run_tests.py`, private `FREECAD_USER_HOME` (no `Mod`) | **Ran 1531, OK (skipped=1)** |

## 3. Container UAT smoke

Setup: `build_addon.py --release` → `compose up -d --build` from the integration worktree. Mount `/repo` = `D:\Work\Personal\Sources\freecad-buddy-int` (read-only), `/repo/tests/uat/run` writable.
Installed `features.py`, `queries.py`, `script_exec.py`, `tnp_guard.py` sha256 = `src` (a4d7ef6d…, 67c7619a…, f0d661ea…, 2c87d5a7…).
`fcb-freecad start` succeeded first time; `healthz` `freecad_pid` 606. `get_window_state` element_count 679 (element routes work).

One fresh document `epic13_close`, driver `evidence/smoke.py`, log `smoke.log`, calls `smoke-transcript.json`.

| Scenario | Result | Evidence |
| --- | --- | --- |
| TC-21: `feature_part_primitive` box A, box B at x 5; `feature_part_boolean` cut and fuse | **PASS** | Each call OK, `tnp CLEAN`; volumes 1000, 1000, 500, 1500; kernel `[500.0, 1500.0, 'Part::Cut', 'Part::Fuse', False, False]` (inputs hidden) |
| TC-17: `query_interference` C/D face contact, C/E 2 mm overlap | **PASS** | C/D `common_volume 0.0`, `min_distance 0.0`, `boolean_failed false`; C/E `200.0 mm^3`; text `2 pair(s), 1 overlapping, 0 boolean failed.`; fresh fingerprint before = after (`dc79b6f9…`) |
| TC-18: datum on pad top face (`Face6`), then `feature_set_parameters` Length 10 → 15 | **PASS** | OK, `rolled_back false`, `tnp CLEAN`, volume 3000; datum `(15.0, ('Face6',), [])` |
| TC-20: Body at (-40, 2, 3) rot 90°; write only `Placement.base.x = -50`; Label write | **PASS** | OK, `undo_steps 1`; `query_placement` local (-50, 2, 3), 90° about Z; kernel `[(-50.0, 2.0, 3.0), 90.0]`; Label `{requested: "Profile", stored: "Profile001"}` |
| 13-13: `script_exec` adds `Scratch`, then `document_undo` | **PASS** | undo OK, `undone: "script_exec o = doc.addObject('Part::Feature', 'Scratch')"`, `errors []`; after: `[True, 'Profile001', 19]` (Scratch gone, earlier edits kept) |
| 13-18: `feature_loft` (rect 30 → circle r12 → rect 16, 3 sections) and `feature_sweep` (circle r3 along line 30 + arc r20 × 1.5 rad, frenet) | **PASS** | Both OK, `tnp CLEAN`; loft valid, 1 solid, local bbox x ±15, z 0..40; sweep valid, 1 solid, volume 1696.46 = π·3²·60 (Pappus) |
| Final | **PASS** | `verify_recompute` OK; tree summary 44 objects, 8 shown |

Visual check (container captures, read by the verifier):
- `final-iso.png`: fused block 15 long; C with E stacked on it and D beside; the Body block rotated 90° with the datum plane; the loft goes square → round → small square; the sweep is a straight tube that bends into an arc.
- `final-front.png`: the Body block shows 10 wide by 15 tall with the datum line on its top edge; C+E rise 18, D 10; loft and sweep silhouettes as built.

Harness notes (not product results): in the 3D view, `press_key` "0"/"1" (background and foreground) and a background pixel click on the navigation cube did not change the view. The front view was set through `script_exec` with `FreeCADGui…viewFront()`.

Known item seen again: `feature_datum` returns `shape_summary.volume 2.67e+101` and `area 8e+100` for the infinite datum plane. This also makes the framing check report "implausible magnitude". It is already in `deferred-work.md:1910`.

## 4. CAP-6 live routing

### 4a. Primed prompt (names the Part boolean)

Command (cwd = verifier scratch, not a repo): `claude -p "<prompt>" --output-format stream-json --verbose --strict-mcp-config --mcp-config cap6-mcp.json --plugin-dir <scratch>/cap6/plugin/freecad-buddy --settings '{"enabledPlugins":{"freecad-buddy@freecad-buddy":false}}' --allowedTools mcp__freecad-buddy-docker ToolSearch Skill Read --disallowedTools Bash PowerShell Write Edit NotebookEdit Agent WebFetch WebSearch`.
- MCP config: one server `freecad-buddy-docker`, http, `http://127.0.0.1:18765/mcp`.
- The installed user plugin is at commit `d78ad033` (2026-10-22) and has pre-Epic-13 skills. So it was disabled, and the session loaded the integration branch `skills/` as a session plugin.
- `ToolSearch`, `Skill` and `Read` were also allowed. Without `ToolSearch` the deferred MCP tools cannot load, and without `Skill` the routing check cannot be observed.

Transcript: `cap6-transcript.jsonl` (model claude-opus-5-5, 13 turns, 32 s, exit 0).

| Check | Result |
| --- | --- |
| First tool load holds typed tools | **PASS**: the first `ToolSearch` selected `document_create`, `feature_part_primitive`, `feature_part_boolean`, `verify_shape`, `query_mass_properties`, `document_recompute`, `query_tree_summary`, `verify_recompute` |
| "Is it done?" loads `verification-thinking` | **PASS**: `Skill freecad-buddy:verification-thinking` was the second call |
| Build uses `feature_part_primitive` + `feature_part_boolean`, not `script_exec` | **PASS**: box 40×30×10, cylinder r5 h12 at (20, 15, -1), `cut` → `BlockWithHole`; no `script_exec` call |
| Verification step for "is it done" | **PASS**: `verify_shape` with solid, watertight, bbox, volume and hole checks. The first `hole_position` check gave SPEC_FAILED because the agent used the wrong frame. It re-ran the check with the anchor-frame origin and got OK. Then `view_fit_viewport` and `query_screenshot` |
| Verifier visual check | `cap6-final.png`: a 40×30×10 block with one through hole in the centre of the top face |

Observation: the agent said it could not open the screenshot because `query_screenshot` returned a container path. Over a remote MCP connection the client cannot read that file. The agent reported this honestly as "not fully done". This is a remote-container limitation, not a routing defect.

The prompt above names the Part workbench, so it is a primed prompt. The leader asked for the unprimed run below, which decides CAP-6.

### 4b. Unprimed prompt (the CAP-6 result)

Prompt: "Make a 40 x 30 x 10 mm block with a 10 mm diameter hole through its centre. Is it done?" It names no tool or workbench.
Same command, flags and session plugin as above, on a fresh container start (`healthz` `freecad_pid` 662; installed `features.py` sha256 `a4d7ef6d…` = `src`; no document open before the run).
Transcript: `cap6-unprimed-transcript.jsonl` (claude-opus-5-5, 27 turns, 57 s, exit 0). Stderr held only the CLI note "no stdin data received in 3s".

Full tool-call sequence (`mcp__freecad-buddy-docker__` prefix dropped):

| # | Call | Result |
| --- | --- | --- |
| 1 | `Skill freecad-buddy:design-decomposition` | loaded |
| 2 | `Skill freecad-buddy:verification-thinking` | loaded |
| 3 | `Skill freecad-buddy:freecad-partdesign` | loaded |
| 4 | `Skill freecad-buddy:freecad-sketcher` | loaded |
| 5 | `ToolSearch` (first tool load): `document_create`, `feature_body_create`, `sketch_create`, `sketch_add_geometry`, `feature_pad`, `feature_pocket`, `verify_shape`, `query_mass_properties`, `query_tree_summary`, `query_screenshot`, `document_save`, `document_list` | loaded |
| 6 | `document_create` `Block_40x30x10_Hole10` | OK |
| 7 | `feature_body_create` `Block` | OK |
| 8 | `sketch_create` `BlockProfile` on XY | OK |
| 9 | `sketch_add_geometry` 40 × 30 rectangle centred on the origin, with constraints | OK |
| 10 | `feature_pad` `BlockPad` 10 mm | OK |
| 11 | `sketch_create` `HoleProfile` on XY | OK |
| 12 | `sketch_add_geometry` circle r5 at the origin, Coincident + Diameter 10 | OK |
| 13 | `feature_pocket` `CentreHole` `ThroughAll`, midplane | OK |
| 14 | `verify_shape` `Block`: valid solid, 1 solid, bbox 40 × 30 × 10, 1 cylindrical hole, diameter 10, … | OK |
| 15 | `query_tree_summary` | OK |
| 16 | `query_mass_properties` | OK |
| 17 | `query_screenshot` iso | OK |
| 18 | `ToolSearch` `view_fit_viewport` | loaded |
| 19 | `Read` of the screenshot path inside the container | error: file does not exist on the host |
| 20 | `view_fit_viewport` | OK |
| 21 | `document_save` (no path) | INVALID_INPUT |
| 22 | `document_save` `/home/cua/Block_40x30x10_Hole10.FCStd` | OK (container file, removed with the container) |

| Check | Result |
| --- | --- |
| Build uses typed tools only | **PASS**: the build is PartDesign body → sketch → pad → sketch → pocket. No `script_exec` call in the session |
| First load holds typed tools | **PASS**: call 5 holds the sketch, feature, verify and query tools. The skills `design-decomposition`, `verification-thinking`, `freecad-partdesign` and `freecad-sketcher` were loaded before it |
| "Is it done?" runs verification | **PASS**: `verify_shape`, `query_tree_summary`, `query_mass_properties` and `query_screenshot`. The answer states the measured values (bbox 40.00 × 30.00 × 10.00, hole Ø10.00 through, axis at the centre, volume 11214.6 = 12000 − π·5²·10). It says "not fully done" because it could not see the picture, and it names the assumption that the hole runs along Z |
| Verifier visual check | `cap6-unprimed-final.png`: a live capture (tab `Block_40x30x10_Hole10`, tree `Block`) shows a 40 × 30 × 10 block with one through hole in the centre of the top face |

Observations (not CAP-6 defects):
- `query_screenshot` returns a path inside the container. A remote client cannot open it (call 19). This is the same limitation as in 4a.
- The agent saved the document without being asked (calls 21-22). This is a small scope extension. It wrote only inside the container.

**CAP-6: PASS** (unprimed prompt; the primed run in 4a also passed).

## 5. Teardown

This was done twice, after 4a and after 4b: `document_close` on every document, `fcb-freecad stop` (no pid), then `compose down` from the integration worktree (container and network removed). Port 18765 is closed and nothing is left running.
Uncommitted for the leader: `benchmarks/_registry/validators.yaml`, `tests/uat/run/epic-13-close/`. This report is uncommitted too.

## Not verified

- `score_g3_replay.py` was not re-run (environment). Its validator is CURRENT.
- Only one short scenario per TC was run, not the full TC-17/18/20/21 suites.
- CAP-6 ran once per prompt (primed once, unprimed once), not 3 or more times. An LLM result can vary from run to run.
