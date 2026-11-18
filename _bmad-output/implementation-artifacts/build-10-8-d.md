# Build report: Story 10-8-d preparation

Branch `story/10-8-d-uat-gate-1-container`. Review base `c66b80e`. Spec `spec-10-8-d-uat-gate-1-run.md` (status `in-progress`: the run tasks stay open for the run lead). Quality bar `quality-bar-10-8-d-prep.md`.

The proofs below are not a gate result. Scratch folder: `tests/uat/run/2026-11-18-10-8-d-prep/`.

## What changed

| File | Change |
| --- | --- |
| `spec-10-8-d-uat-gate-1-run.md` | Frozen block: only D1 (G3 GUI script copied into the new run folder in container form) and the profile line (decision 36 wording). `baseline_commit` stays `3025e7c`. Code Map and Tasks in container form; phases, run folder layout, records, re-run rule (decision 35), TC-02-08 as written (decision 34). Host lines removed. AC2 now says "in the container, its `:8765` is free" |
| `tests/uat/g3-gui/g3_gui_replay.py`, `gui.py` | New. G3 GUI replay in container form. The run lead copies both into `$RUN_DIR/evidence/g3-gui/` |
| `tests/uat/run/2026-11-18-10-8-d-prep/` | Proof records |

No edit to `src/`, runner, test cases, scenarios, container files, earlier run folders. `benchmarks/*/heldout` not opened (see finding F3).

## Port diff against the source (Q5)

Full diff: `evidence/g3-gui-port.diff`. AST check per function: `evidence/g3-gui-ast-check.txt`.

`g3_gui_replay.py`
- `gui`, `replay`: AST equal to the source.
- `REPO`: `Path(r"D:\Work\...")` becomes `git rev-parse --show-toplevel`.
- MCP URL: `http://127.0.0.1:8765/mcp` becomes `http://127.0.0.1:18765/mcp`.
- Header text: container wording and how the run lead uses the file.
- Added after review (finding row 1 of the triage log): `gui_error()` and one line in `build` (`row["gui_error"] = gui_error(row)`), plus `row.get("gui_error")` in the `main` print. It flags a row whose fit, view or capture step did not run. The grading code (`verify_shape` call, `classify_planted`, `volume`) is unchanged.

`gui.py`
- `cua-driver` call: `["cua-driver", tool]` becomes `docker exec -i -u cua fcb-desktop bash -c 'eval "$(fcb-session-env)"; exec /usr/local/bin/cua-driver call "$@"' _ <tool>` (the command inside `scripts/automation/fcb_cua.sh`).
- Capture path: `screenshot_out_file` is the container path `/repo/<path relative to the git root>` (`_container_path`); a stale PNG is deleted first.
- Button role: `"Button"` becomes `BUTTON_ROLE = "push button"`. The Linux accessibility bridge names the toolbar button `push button`; the hidden menu item `Fit All` has role `menu item`. The first container attempt failed on this (`evidence/g3-gui/attempt1-role-mismatch/`: `fit` = "no Button labelled 'Fit All'"). This is part of the Fit All route that decision 36 allows, not replay logic.
- Both files are reformatted with `ruff format` and wrapped to 100 columns, because `tests/uat/g3-gui/` is inside `ruff check .` (CI), while `tests/uat/run/` is excluded. The AST check shows the logic functions equal.

## Proofs (container `fcb-desktop`, image `sha256:ccccd43b...dddc4`)

S0, once (`evidence/s0-*.log`, started 2026-11-18T18:49+0700):
- `build_addon.py --release` exit 0; wheel `freecad_buddy-0.1.1-py3-none-any.whl` SHA-256 `d40a271b...e8c` (`addon-wheel-sha256.txt`).
- `compose up -d --build --force-recreate` exit 0; image id in `image-id.txt`.
- H1 line: `H1 ok 1.1.4`.
- `run_mcp_e2e.py` 29/29, exit 0. `run_mcp_edge_cases.py` 14/14, exit 0.
- `run_faults.py`: detected 5/5, false alarms 0/2. `pixel_faults.py`: detected 4/4, false alarms 0/2.
- Developer `user.cfg` SHA-256 `b89a9771...85a0` equals decision 8 (`user-cfg-sha256.txt`). I hashed it after the proofs, not before S0; the baseline is the decision 8 value.

G3 headless (`evidence/g3-headless-run.log`, `evidence/g3-headless/`):
- The scorer has no case filter, so all 14 cases ran, 17 s, from a container temp copy with `--leg 1.1.x --check --frames-check`. Its H1 child starts under `fcb-py` (the plan risk is closed).
- Result: planted=10 detected=10, controls=14 (4 controls and 10 reverted) flagged=0, sensitivity 1.000, false_alarm 0.000, `frames-check: OK`, `validators.yaml not written`, exit 0. The copy held 0 `heldout` folders.

G3 GUI (`evidence/g3-gui/`, scripts byte-identical to the committed ones: `g3-gui-script-sha256.txt`):
- Cases `control-faithful-mounting-plate` and `wrong-hole-diameter` (planted and reverted builds), PID 5898, window 41943138, 3 builds.
- Rows equal to the 2026-10-03-04 rows: control OK, volume 28229.8; planted `INVALID_INPUT` with classification DETECTED, volume 27593.63; reverted OK, volume 28229.8. `gui_error` None on all three.
- I read all three captures. Control and reverted: an 80 x 60 plate, 4 plain round holes, fitted (view 177.71 x 100.18 mm). Planted: same plate and view, 4 larger holes with a visible ring. The Tasks panel covers none of the plate.
- Fit All returns `effect: unverifiable` (route accessibility); the capture is the proof that the fit happened.

Gates: `uv run ruff check .` pass; `uv run python scripts/check_imports.py` OK; `uv run pytest tests/external -q` 1814 passed, 4 skipped (run before the final small patches; those touched only `tests/uat/g3-gui/` and the spec, and `ruff check .` was run again after them).

## Review

Lenses (fresh subagents, base `c66b80e`): Blind Hunter `a8c8aa7b63e4c504a` (opus, high, 14 findings), Edge Case Hunter `ad07e289463dd768b` (opus, high, 14), Verification Gap `a572992f9c6a84fd9` (sonnet, medium, 2 plus 1 other). Triage rows: spec `## Review Triage Log`.

- Patched: swallowed GUI failures (medium); `heldout` copied by the scorer temp copy (medium); committed bytes differed from the proven copy and only one build form was proven (medium, re-proved); `user.cfg` record form, spec history sentence, TC-01 note, stale PNG (low).
- Rejected (false or low and unlikely, fix adds code): 10 rows, reasons in the log.
- Deferred: none.
- Not re-reviewed after the patches (step-04 has no second round without a leader request).

## Findings for the leader

- F1. In the container the toolbar role is `push button`, not `Button`. Any older GUI helper that filters on `Button` finds nothing.
- F2. `FC_PID` and `FC_WIN` change at every FreeCAD start (window 41943133 then 41943138). The run lead sets them after each start.
- F3. My first headless proof used `cp -r /repo/benchmarks`, which copied the sealed `heldout` folders inside the container. I read no file in them. The command is now `tar --exclude=heldout`, and the proof was run again. The first copy was deleted. Judge whether this needs a note in the ledger.
- F4. `tests/uat/run/2026-10-03-04/evidence/` was only read. `_automation/*_report.json` were rewritten by the two sweeps (ignored by git).

## Not verified

- The full 14-case GUI replay (24 builds) and the iso view option (`G3_VIEW_BUTTON`): the toolbar has no `Isometric` push button (it is in the `Standard Views` menu), so that option does nothing useful in the container. The gate does not need it.
- Planted cases other than `wrong-hole-diameter`.

## State at report time

No FreeCAD running in the container; no `/tmp/g3r`; no process of mine. The container `fcb-desktop` is up and was recreated at S0 (clean profile). The commit contains: the spec, `tests/uat/g3-gui/`, the prep folder and this report.
