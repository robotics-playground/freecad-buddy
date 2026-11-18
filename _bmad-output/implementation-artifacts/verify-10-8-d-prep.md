# Story 10-8-d (preparation): verification

Verifier: verifier-10-8-d (claude-opus-5-5). Commit verified: `6e640c4d45ab781ac324ac1a480429d885e28344`. Base: `c66b80e`.
Evidence folder: `tests/uat/run/2026-11-18-10-8-d-verify/` (uncommitted).

## Verdict

**PASS.** No blocker. Four low findings (F1-F4) below. None needs a change before the run lead starts.

## 1. Gates (detached worktree at `6e640c4`, main `.venv` interpreter)

| Gate | Command | Result |
| --- | --- | --- |
| ruff | `.venv/Scripts/python.exe -m ruff check .` | `All checks passed!`, exit 0 |
| imports | `.venv/Scripts/python.exe scripts/check_imports.py` | `check_imports OK`, exit 0 |
| pytest | `.venv/Scripts/python.exe -m pytest tests/external -q -p no:cacheprovider` | `1814 passed, 4 skipped, 6 warnings in 128.84s`, exit 0 |

The main `.venv` has an editable install of the main checkout `src/`. The main checkout is at `6e640c4` with no `src/` change, so the imported code equals the commit.

## 2. Q1/Q2: frozen block and baseline

- `git diff c66b80e 6e640c4 -- spec-10-8-d-uat-gate-1-run.md`: inside `<frozen-after-approval>` (`:16-43`), only `:26` and `:34` change. A line-by-line diff of `:1-43` shows those two lines and nothing else.
- `:34` is the decision-36 wording: "Agent-driven FreeCAD starts with `fcb-freecad start` on a container recreated at run start (clean profile); the runner uses a temporary `-u`/`-s` profile; record the developer `user.cfg` SHA-256 before and after."
- `:26` says the script is "copied ... into the new run folder in container form (repo root, port `18765`, capture route only changed)". Decision 36: "(repo root, port `18765`, capture route only)". Same meaning.
- The G3 "unchanged" rule (`"Unchanged" means ...` to end of line 26) is byte-equal: SHA-256 `3ef3e1a2...e438` at both commits.
- `:6` `baseline_commit: '3025e7c60b41d69cb93fdf39d265274202947566'` unchanged. `:47` "Run baseline: the integration head at run start, recorded in `RUN-CONTEXT.md`."

## 3. Q3/Q4: container forms, phases, records, rules

- Grep of Code Map and Tasks (`:45-80`) for `launch_env`, `non-elevated`, `uv run python tests`, `cua-driver serve`: no match. Remaining host commands are host by design: `uv run python scripts/build_addon.py --release` (`:69`, CLAUDE.md §9 builds on the host) and the G3 GUI replay "from the host `uv` env" (`:55`, plan §6.4).
- Runner `:49` and watchdog `:54` are `docker exec -u cua fcb-desktop fcb-py /repo/...`; scorer `:57` is the `tar --exclude=heldout` temp-copy form.
- Phases `:69-74` (S0, R0, R0a/R0b, P1-P12, G3, End) equal plan §6.3. Layout `:58` equals plan §6.2 plus `addon-wheel-sha256.txt` (plan §3.3 asks for the wheel SHA-256).
- Records: image id, wheel SHA-256, developer `user.cfg` SHA-256 at `:69`, `:34`, Verification section.
- Decision 35 at `:76`; decision 34 at `:72` ("TC-02-08 runs as written and a FAIL is a product finding, deferred (decision 34)").

## 4. Q5: ported scripts against the 2026-10-03-04 source

Method: format the source copies with `ruff format` (line length 100) in a scratch folder, then diff against `tests/uat/g3-gui/`. This removes the line-wrap hunks, so only the hunks below are left.

`g3_gui_replay.py`:

| Hunk | Port line | Class |
| --- | --- | --- |
| Docstring line 1, 4, new paragraph `:10-14` | 1-14 | Text only (F1) |
| `REPO = Path(r"D:\Work\...")` to `git rev-parse --show-toplevel` | `:32-40` | Repo root (allowed) |
| New `gui_error()` | `:68-81` | `gui_error` flag (allowed) |
| `row["gui_error"] = gui_error(row)` | `:157` | `gui_error` flag (allowed) |
| `:8765` to `http://127.0.0.1:18765/mcp` | `:167` | MCP URL (allowed) |
| `row.get("gui_error")` in the print | `:190` | `gui_error` flag (allowed) |

`gui.py`:

| Hunk | Port line | Class |
| --- | --- | --- |
| Docstring lines 1, 5, 11, 12 | 1-12 | Text only (F1) |
| `REPO`, `_container_path()` | `:25-33`, `:40-41` | Repo root and capture path (allowed) |
| `BUTTON_ROLE = "push button"` and its two uses | `:36`, `:85`, `:124` | `push button` role (allowed) |
| `CONTAINER_CALL` and the `docker exec ... cua-driver call` argv in `_cua` | `:37`, `:53-69` | cua-driver route (allowed) |
| `shot()`: `host_path.unlink(missing_ok=True)` then capture to `_container_path(host_path)` | `:96-102` | Capture path; the `unlink` is an extra line (F1) |

Not changed after the normalization: `replay()`, the `verify_shape` call and `checks` grading, `classify_planted` call, `query_mass_properties`, the planted/reverted build loop, `_ids`, `_snapshot`, `main` dispatch of `gui.py`. The builder's AST check agrees (`g3-gui-ast-check.txt`: `gui`, `replay` same).

## 5. Q6/Q7: independent live proof in `fcb-desktop`

Container: up, image `sha256:ccccd43b5b3d...dddc4` (equal to the prep `image-id.txt`).

### Headless scorer

Command (spec `:57`, run `g3r-verify-1.1.4`):
```
docker exec -u cua fcb-desktop sh -c 'rm -rf /tmp/g3r && mkdir /tmp/g3r && tar -C /repo --exclude=heldout -cf - benchmarks src | tar -C /tmp/g3r -xf - && echo "heldout count before scorer: $(find /tmp/g3r -name heldout | wc -l)" && sha256sum .../validators.yaml && cd /tmp/g3r && fcb-py benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.1.x --run g3r-verify-1.1.4 --check --frames-check benchmarks/g3/fault-injection/frames-reference.json'
```
Result (`evidence/g3-headless-run.log`):
- `heldout count before scorer: 0`.
- 14 cases. `planted=10 detected=10 controls=14 flagged=0 sensitivity=1.000 false_alarm=0.000`.
- `cases.jsonl`: 4 controls `PASS_CLEAN` (clean build `OK`); 10 planted `DETECTED` with reverted build `OK` / `PASS_CLEAN`.
- `frames-check: OK vs benchmarks/g3/fault-injection/frames-reference.json`; `validators.yaml not written`; `validators.yaml` SHA-256 `9f993f61...29b0` before and after the scorer.
- H1 child: `score_g3_replay.py:439` `command=sys.executable`; under `fcb-py` that is the AppImage Python (`/opt/freecad/AppRun python`). `server.stderr.log` shows `freecad-buddy headless MCP server starting (stdio)` with the audit log under `/tmp/g3r`. Exit 0, 30 s.
- Artifacts copied to `evidence/g3-headless/`; `/tmp/g3r` removed.

### GUI port, planted case `blind-hole-made-through` (builder used `wrong-hole-diameter` and a control)

`fcb-freecad start`, `/healthz` `freecad_pid: 8141`, `list_windows` window `41943138`. Scripts copied to `evidence/g3-gui/`; SHA-256 equal to `tests/uat/g3-gui/` (`gui.py` also equal to the committed blob; see F2 for `g3_gui_replay.py`). Command: `FC_PID=8141 FC_WIN=41943138 uv run python g3_gui_replay.py blind-hole-made-through`. Exit 0, 20 s.

Rows against `2026-10-03-04/evidence/g3-replay.jsonl`:

| Field | planted | reverted |
| --- | --- | --- |
| status | `SPEC_FAILED`, equal | `OK`, equal |
| classification | `DETECTED`, equal | `None`, equal |
| failed checks | `assert.expect_volume`, `assert.hole_through`; full check id/passed list equal | none; equal |
| steps, error | equal | equal |
| volume | `59672.57` vs `59672.56661176919` (equal at 2 decimals) | `60803.54` vs `60803.53996706151` (equal at 2 decimals) |
| frame | origin `[0,0,-25]` and axes equal; `entity` toponame string differs (`:H105a` vs `:Hc5d`) | same; `:Hfb7` vs `:Hafa` |
| gui_error | `None` | `None` |

The volume and toponame differences come from the product output (volume rounding and the topological-name hash), not from the port: the port does not touch these fields. The builder's prep rows show the same rounding.

Captures read by me:
- `g3-blind-hole-made-through-planted.png`: FreeCAD 1.1.4, top view, square plate fitted in the view, the centre hole shows the background through it (through hole). Tab `g3-fault-plan-blind-hole-made-through-planted : 1*`.
- `g3-blind-hole-made-through-reverted.png`: same plate and view, the centre circle is filled with the part colour (blind hole floor). This matches the planted fault "blind hole made through".

After the run, `document_list` returned `0 open document(s)`. FreeCAD stopped (`fcb-freecad status`: no pid).

## 6. Falsification

| Break | Where | Row result |
| --- | --- | --- |
| `BUTTON_ROLE = "Button"` (the Windows role) | worktree `gui.py`, copy run from `evidence/falsify-role/` | `gui_error: fit: {"error": "no Button labelled 'Fit All' in snapshot", "count": 661}` |
| Wrong `FC_WIN=12345` | committed scripts, `evidence/falsify-capture/` | `gui_error: fit: {... "count": null}`; `capture.exists: false`, no PNG |
| Capture-only failure: scripts run from the worktree path, which `/repo` does not mount | worktree `tests/uat/run/2026-11-18-10-8-d-verify-falsify/`, row copied to `evidence/falsify-worktree-capture/` | fit succeeded; `gui_error: capture: file missing: {..., "exists": false}` |

In each case the row names the failed GUI step. The row `status` stays `OK` and the process exit stays 0 (F3).

## 7. Builder F3: sealed folders in the container

- `find /tmp /var/tmp /root /home -name heldout`: no result (each folder searched, `/home` 25 s).
- `/tmp/g3r` absent after my run; `ls /tmp` shows no other copy.
- I did not open or copy any `benchmarks/*/heldout` path. My scorer copy used `--exclude=heldout` and the count was 0 before the scorer started.

## 8. AC map

| Q | Result | Evidence |
| --- | --- | --- |
| Q1 | PASS | spec `:26`, `:34` only changed in `:16-43`; unchanged-rule SHA-256 equal |
| Q2 | PASS | spec `:6` `3025e7c...`; `:47` run baseline line |
| Q3 | PASS | spec `:48-49`, `:54-55`, `:57`, `:69-70`; no host runner or `launch_env.sh`; F4 |
| Q4 | PASS | spec `:58` layout, `:69-74` phases, `:69` records, `:72` decision 34, `:76` decision 35 |
| Q5 | PASS | section 4; F1 |
| Q6 | PASS | builder capture `prep/evidence/g3-gui/g3-control-faithful-mounting-plate-control.png`; my planted proof section 5 |
| Q7 | PASS | section 5 headless; `score_g3_replay.py:439`; no scorer edit (`git diff --stat c66b80e 6e640c4` has no `benchmarks/` path) |
| Q8 | PASS (records read, not re-run) | prep `s0-build.log` exit 0; `s0-compose.log` "Recreated"; `image-id.txt`; `s0-h1.txt` `H1 ok 1.1.4`; `s0-e2e.log` 29/29; `s0-edge.log` 14/14; `s0-probe-faults.log` 5/5, 0/2; `s0-pixel-faults.log` 4/4, 0/2; `user-cfg-sha256.txt` equal to decision 8 |
| Q9 | PASS | diff stat: `build-10-8-d.md`, the spec, `tests/uat/g3-gui/*`, the prep run folder only. The builder's first copy of `heldout` (their F3) is a reported process slip; no trace remains |
| Q10 | PASS | section 1 |

## 9. UAT per check

| Check | Result |
| --- | --- |
| Headless scorer, 14 cases, heldout-free copy | PASS |
| GUI port, planted + reverted `blind-hole-made-through`, captures read | PASS |
| GUI falsification (fit, capture) | PASS |
| `/tmp` free of `heldout` | PASS |
| Developer `user.cfg` SHA-256 before/after = `b89a9771...85a0` | PASS |
| S0 preflight re-run | NOT RUN (read the builder's records; not in my task list) |

## 10. Findings

- **F1 (low, accepted):** the port has hunks beyond the six allowed classes: docstring text in both files and `host_path.unlink(missing_ok=True)` in `gui.py:97`. The `unlink` makes `exists` mean "written by this capture", so `gui_error` cannot pass on a stale PNG. The text hunks change no behaviour. The review ledger records both. Also, the whole files are reformatted by `ruff format` (line wraps only).
- **F2 (low, no action):** the working copy of `tests/uat/g3-gui/g3_gui_replay.py` has CRLF line ends; the committed blob is LF (`git ls-files --eol`: `i/lf w/crlf`). SHA-256 of the working file `ff873a9c...` differs from the blob `be1083ab...`; with CR removed they are equal. `g3-gui-script-sha256.txt` records the CRLF working-copy value. A run lead who compares hashes against the blob gets a mismatch.
- **F3 (low, advisory for the run lead):** a GUI failure sets only `gui_error`. The row `status` stays `OK` and the script exits 0 (source behaviour). The G3 reader must check `gui_error` on all 24 rows, not only `status`.
- **F4 (low, advisory):** spec `:69` names `run_faults.py` and `pixel_faults.py` but gives no command form. Plan §6.4 has them (`run_faults.py` through `docker exec ... fcb-py`; `pixel_faults.py` from the host `uv` env). No host-form error, only an omitted command.

## 11. Cleanup

FreeCAD in the container stopped (`freecad pids:` empty). Worktree `fcb-verify-10-8-d` removed. Container `/tmp/g3r` removed. No harness file edited. The worktree `fcb-redteam-10-8-d` is not mine and stays.

## Re-run at c928eb5

Commit verified: `c928eb5` (base `6e640c4`, fix round 1 D1-D8). New detached worktree, removed after. Evidence: `tests/uat/run/2026-11-18-10-8-d-verify/evidence/` (`rerun_check.py`, `round2-wrong-window/`, `round2-clean/`, `round2-g3r-copy.log`).

**Verdict: PASS.** No blocker. One new low finding (F5).

### Gates (worktree at `c928eb5`, main `.venv`)

| Gate | Result |
| --- | --- |
| `ruff check .` | `All checks passed!`, exit 0 |
| `ruff format --check tests/uat/g3-gui` | `2 files already formatted` |
| `check_imports.py` | `check_imports OK` |
| `pytest tests/external -q` | `1814 passed, 4 skipped, 6 warnings in 125.85s`, exit 0 |

Frozen block `:1-43`: identical to `6e640c4` (`diff` empty). Fix-round changes are at spec `:49`, `:55`, `:57`, `:59`, `:69` and the triage log only.

### D1 (RT1): runner re-run folders

Spec `:49` now says: R0 folder is never written again; a §9 launch-group re-run passes only that group's files with `--out .../runner-rerun-<n>`; `report.md` lists each runner run with folder and seed; the gate count and §9 review read R0 rows, except the re-run group, whose R0 `not_run` rows are replaced by the re-run rows.

Reproduction (`evidence/rerun_check.py`): imports the real `run.main` and the real `run.run` from the worktree runner; stubs only `launch.preflight`, the session (the `FREECAD_BUDDY_AUTO_APPROVE=0` group raises at launch in R0) and `run_scenario`. Real `mark_review`, `summary`, `results.json` writer.
```
R0 exit 3 seed 4176870498 drawn [('TC-02-01', 'PASS', False), ('TC-02-02', 'PASS', False), ('TC-05-03', 'ESCALATE', True)]
rerun exit 0 seed 3402884353 [('TC-05-03', 'PASS', False)]
R0 results.json unchanged: True R0 files: ['results.json', 'summary.md']
gate rows 3 R0 ids 3 duplicates 0 [('TC-02-01', 'PASS', False), ('TC-02-02', 'PASS', False), ('TC-05-03', 'PASS', False)]
```
R0 `results.json` (bytes) and its seed survive. Applying the spec rule (R0 rows minus re-run ids, plus re-run rows) gives one row per scenario; the script asserts no id is added twice. The rule replaces rows, so it cannot double count.

### D2 (V-F3): GUI step error fails the run (live, `fcb-desktop`, FreeCAD pid 11031, window 41943138)

Scripts copied from `tests/uat/g3-gui/`; `git hash-object` of the copies = committed blobs `a2b43c52...` / `eb67d351...`. Command `uv run --extra dev python g3_gui_replay.py control-faithful-mounting-plate`.

| Run | Output | Exit |
| --- | --- | --- |
| `FC_WIN=12345` | `... fit: {"error": "no Button labelled 'Fit All' in snapshot", "count": null}` then `NOT RUN (a GUI step failed): g3-fault-plan-control-faithful-mounting-plate control`; no PNG | 1 |
| `FC_WIN=41943138` | `... control OK None None None []` | 0 |

Clean capture `round2-clean/g3-control-faithful-mounting-plate-control.png` (202446 bytes), read by me: FreeCAD 1.1.4, top view, rectangular mounting plate fitted in the view, four corner holes show the background through them. Tab `g3-fault-plan-control-faithful-mounting-plate-control : 1*`. `document_list` after both runs: 0 open documents.

### D4 (RT3): scorer temp copy

Spec `:57` command run as written up to the copy: `paths with heldout: 0` from `find /tmp/g3r -path '*heldout*'`; `benchmarks/gate-artifacts` copied with `g0 g1 g2 g3`. The only change from the round-1 copy is the wider exclude, so I did not re-run the scorer. `/tmp/g3r` removed.

To compare the two filters I listed both on the host (`tar ... | tar -tf -`): the old `--exclude=heldout` filter includes paths under `benchmarks/gate-artifacts/g2` (the `devrun-heldout-blind` folder RT3 names); the new filter does not. That listing read the git-ignored `devrun-heldout-blind` folder through a pipe (names only, nothing printed beyond `benchmarks/gate-artifacts/g2`). It is not a `benchmarks/*/heldout` folder; sealed folders were excluded in both listings.

### D3, D5, D6, D7, D8: text and command checks

| Item | Check | Result |
| --- | --- | --- |
| D3 | spec `:59` `test-plan.md:457-561`; `test-plan.md` `## 9` at 457, `### Gate 1` 461, `### Gate 2` 540, `## 10` 562 | PASS (build note says `## 10` at 563; it is 562, no effect on the spec range) |
| D5 | in the fresh worktree: `uv run --exact --extra dev python -c "import yaml, mcp"` prints `yaml 6.0.3`; without `--extra dev`: `ModuleNotFoundError: No module named 'yaml'`; `pyproject.toml:22` has `pyyaml>=6` in `dev` | PASS |
| D6 | spec `:69` names all four commands; the four script paths exist | PASS |
| D7 | docstring and `unlink` kept, reason recorded in the triage log | Accepted (my F1 was low, accepted) |
| D8 | spec `:55` says compare by `git hash-object`; `fix-round-1/script-blob-ids.txt` values equal my `git hash-object` and `git rev-parse c928eb5:<path>` | PASS |

F2 and F3 are closed by D8 and D2. F4 is closed by D6.

### New finding

- **F5 (low, advisory):** spec `:49` names `runner-rerun-<n>` but does not say which folder wins when the same group is re-run twice (`-1` then `-2`). The intended reading is the latest re-run; one sentence ("the highest `n` for that group") would close it. Also, the fix round edited `prep/evidence/g3-gui-port.diff`, an existing file in the builder's own prep folder, and left the superseded `g3-gui-script-sha256.txt` in place; the build note states it is superseded.

### Cleanup

Container FreeCAD stopped (`freecad pids:` empty). `/tmp/g3r` removed; `find /tmp /var/tmp /root -path '*heldout*'` count 0. Worktree removed. Developer `user.cfg` SHA-256 `b89a9771...85a0`, equal to decision 8.
