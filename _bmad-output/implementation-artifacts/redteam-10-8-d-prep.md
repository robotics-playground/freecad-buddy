# Story 10-8-d (preparation): red team report

Diff `c66b80e...6e640c4`, branch `story/10-8-d-uat-gate-1-container`. Work copy: detached worktree at `6e640c4` (removed after the work). Quality bar `quality-bar-10-8-d-prep.md`. Ledger rows B-M1, B-M2, B-M3, F3 and the spec triage rows are known and not reported again.

No live run in `fcb-desktop`. All reproductions are static runs in the worktree. The container was not requested: no candidate needed it to reach medium or high.

## Reproduced

| RT | Severity | Q | Where | Finding |
| --- | --- | --- | --- | --- |
| RT1 | medium | Q4 | `spec-10-8-d-uat-gate-1-run.md:49`, `tests/uat/runner/run.py:576-592` | The Code Map gives one fixed runner folder `--out /repo/tests/uat/run/<run>/runner`. Test-plan §9 needs a second runner run when a launch group did not start (a `not_run` scenario is "first run again by re-running its launch group"). The spec also says "list every runner run in `report.md`". `run.py` does `mkdir(exist_ok=True)` and then overwrites `results.json` and `summary.md`. A second run into the Code Map folder replaces the R0 record of all 72 files, and the R0 `sample_seed`, with the subset run. §9 says each runner run keeps "its run folder", so that a run repeated until a good draw leaves a trace. The spec gives no folder for the second run, so this trace is lost when the lead follows the spec as written |
| RT2 | low | Q3 | `spec-10-8-d-uat-gate-1-run.md:59` | `tests/uat/test-plan.md:342-441 -- Gate 1 and Gate 2 rules` is out of date. At `6e640c4` those lines are §6 "GUI routes in the container" and §7 "Test Case Index". The gate rules are at `test-plan.md:457-561` (`### Gate 1` at :461, `### Gate 2` at :540). The line was already in the spec before this diff, but this diff rewrote the Code Map and kept it. The run lead is pointed to the wrong section for the gate rules |
| RT3 | low | Q9 | `spec-10-8-d-uat-gate-1-run.md:57` | `tar --exclude=heldout` excludes only path parts that are exactly `heldout`. The host tree that `/repo` mounts has the git-ignored folder `benchmarks/gate-artifacts/g2/devrun-heldout-blind`. The command copies that folder, and all of `benchmarks/gate-artifacts/`, into `/tmp/g3r`. The scorer does not need them. This is not the `benchmarks/*/heldout` pattern, so Q9 is not broken. But the name says it holds held-out run output, and a copy of it goes into the container |
| RT4 | low | — | `tests/uat/g3-gui/g3_gui_replay.py:15,28` | The documented use is `uv run python g3_gui_replay.py`. The script imports `yaml`, and `pyyaml` is only in the `dev` extra (`pyproject.toml:22`). In a uv env without that extra, the script stops at import. The main tree `.venv` has `pyyaml 6.0.3`, so the planned run in the main checkout works. A fresh checkout or a fresh worktree fails |

### Reproductions

RT1. Script `runner_overwrite.py` (scratchpad). It imports the real `run.main` and replaces only the FreeCAD parts (preflight, `run`, `mark_review`, `summary`). It then calls `main` twice with the same `--out`, the second time with one scenario, as a launch-group re-run does:

```
first run : 280774582 ['TC-02-01', 'TC-02-02', 'TC-03-02']
after rerun: 2930299628 ['TC-03-02']
files in --out: ['results.json', 'summary.md']
```

The first seed and the first verdict set are gone. Nothing in the folder shows that an earlier run existed.

RT2.
```
$ grep -n "Gate 1\|Gate 2\|^## " tests/uat/test-plan.md
415:## 7. Test Case Index
457:## 9. Pass/Fail Criteria
461:### Gate 1 — Green gate (TC-01 .. TC-14)
540:### Gate 2 — Conformance gate (TC-99 only)
$ git show 3025e7c:tests/uat/test-plan.md | sed -n 342p
### Gate 1 — Green gate (TC-01 .. TC-14)
```
`sed -n 330,415p tests/uat/test-plan.md` at `6e640c4` shows "### Pixel points", "### Tree row toggle", "### GUI routes in the container", "### Process commands" and the start of §7.

RT3. The exact tar filter, run on a test tree that has the same two folder shapes:
```
$ tar -C $S --exclude=heldout -cf - benchmarks src | tar -tf -
benchmarks/
benchmarks/g3/
benchmarks/gate-artifacts/
benchmarks/gate-artifacts/g2/
benchmarks/gate-artifacts/g2/devrun-heldout-blind/
benchmarks/gate-artifacts/g2/devrun-heldout-blind/cases.jsonl
src/
src/a.py
$ find benchmarks src -iname '*heldout*' -prune -print     # main tree, names only
benchmarks/g1/heldout
benchmarks/g2/heldout
benchmarks/g3/heldout
benchmarks/gate-artifacts/g2/devrun-heldout-blind
benchmarks/heldout
$ git check-ignore -v benchmarks/gate-artifacts/g2/devrun-heldout-blind
.gitignore:29:benchmarks/gate-artifacts/	benchmarks/gate-artifacts/g2/devrun-heldout-blind
```
I did not open the real folder or any `heldout` folder.

RT4.
```
$ uv run --exact python tests/uat/g3-gui/g3_gui_replay.py nothing
    import yaml
ModuleNotFoundError: No module named 'yaml'
```

## Checked and found correct (no finding)

- Q1: the frozen block diff changes only D1 (`:26`) and the profile line (`:34`). The `:34` text is word for word decision 36. The D1 "Unchanged means ..." sentence is word for word the old one.
- Q5: diff of the port against `tests/uat/run/2026-10-03-04/evidence/`. `replay`, the `verify_shape` call, `classify_planted`, the volume read and the case loop are the same. Additions: `gui_error` (ledger B-M1), `BUTTON_ROLE` (spec triage BH7), the repo root, port `18765`, the `docker exec` route and the capture path. No other change.
- Gate numbers: 255 `### TC-` headings in TC-01..TC-14. Priorities 174 Critical, 67 High, 14 Medium. 72 scenario files. Agent-driven count per TC = headings minus runner files, for all 14 test cases (sum 183). TC-02-08 is High. 95 % of 67 = 63.65, so 3 non-PASS are allowed (decision 34). `uat-run-practices.md` §3 keeps TC-99 out of Gate 1.
- Seed rule: `run.py` writes `sample_seed_source: drawn` when no `--seed` is given (`run.py:576-587`).
- Re-run rule and image id: `build_addon.py --release`, run twice in the worktree, gives a byte-identical `dist/addon/` (85 files, same SHA-256s). The wheel SHA-256 `d40a271b...e8c` is equal to the prep record. So "same image id" can hold after a fix that touches only test cases.
- Headless scorer: `--frames-check` adds a drift line for a missing build and for a build that is not in the reference, and it returns exit 1 on any drift (`score_g3_replay.py:375-396,532-552`). `--check` skips the only repo write (`validators.yaml`), and all other writes go under `ARTIFACTS` in `/tmp/g3r`.
- GUI frames: the prep GUI rows `control-faithful-mounting-plate` and `wrong-hole-diameter#reverted` give no drift against `frames-reference.json` with `compare_frames`.
- Prep captures: I read the planted and reverted PNGs. The plate is whole and fitted. The planted plate has 4 larger holes with a ring, and the reverted plate has 4 plain holes. The Tasks panel does not cover the plate.
- `ruff check .` passes, `ruff format --check tests/uat/g3-gui` passes, `check_imports.py` passes (worktree).

## Not reproduced

- low: the headless H1 child takes `PYTHONPATH=/tmp/g3r/src` first (`score_g3_replay.py:432`), so the headless G3 grades the copied `src/`, not the addon in the image (`fcb_py.sh` uses the image addon). These are the same only when the tree is clean at S0. Needs a live `freecad_buddy.__file__` print.
- low: `G3_VIEW_BUTTON=Isometric` cannot work if the toolbar has no `push button` with that label (builder note). The 2026-10-03-04 run used `-iso` captures for `hole-on-wrong-face` and `wrong-plate-thickness`, and a top view cannot show those faults. `test-plan.md` says `Isometric` works by token in the container. Needs a live snapshot.
- low: D1 can be read as "every anchor frame equal" for the GUI form too. The spec has no step that compares the GUI rows' frames with the reference. The two prep rows match.
- low: `gui()` uses `timeout=120`, and `fitall` can take two 60 s `cua-driver` calls. A `TimeoutExpired` stops the whole replay and leaves a document open. This is the same in the source.
- low: when only one of `FC_PID` and `FC_WIN` is set, `_ids()` falls back to `fc.json` with no warning. D1 says to copy from the 2026-10-03-04 folder, and that folder has a stale `fc.json`. A stale id gives `gui_error`, not a false PASS.
- low: S0 "fcb-py prints `H1 ok 1.1.4`" gives no command in the spec. The command is in `uat-run-practices.md:74`.

## Verdict

FAIL: one reproduced medium (RT1), no high.
