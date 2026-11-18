---
title: 'Story 10.8 (goal 3): UAT Gate 1 Run'
type: 'chore'
created: '2026-10-23'
status: 'in-progress'
baseline_commit: '3025e7c60b41d69cb93fdf39d265274202947566'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/tests/uat/test-plan.md'
  - '{project-root}/tests/uat/README.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md'
  - '{project-root}/tests/uat/runner/README.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 10 closes only when a full UAT run on FreeCAD 1.1.4 shows Gate 1 green (Critical 100 %, High >= 95 %), Gate 2 matching its documented deviations, and the G3 live replay unchanged (epics.md Story 10.8 AC1). No full run has happened since 2026-10-03-04, and Stories 10.1-10.7b changed the product, the test cases and the harness since then.

**Approach:** Run all 255 scenarios of TC-01..TC-14 and the 5 of TC-99 on FreeCAD 1.1.4: the 72 scenario files through `tests/uat/runner/run.py` with a drawn seed, the other 183 by agent through MCP and `cua-driver`, then the G3 replay. Write one run folder `tests/uat/run/2026-10-23-02/` (or the next free id) with `report.md` in the 2026-10-03-04 layout, `bugs.md`, `evidence/` and the runner output, and commit it.

## Decisions

- **D1 — G3 replay in both forms.** The GUI replay with `g3_gui_replay.py`, copied from `tests/uat/run/2026-10-03-04/evidence/g3_gui_replay.py` into the new run folder in container form (repo root, port `18765`, capture route only changed), on the run's FreeCAD 1.1.4, and the headless scorer `benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.1.x --check --frames-check benchmarks/g3/fault-injection/frames-reference.json` on 1.1.4. "Unchanged" means 4/4 controls OK, 10/10 reverted OK, 10/10 planted DETECTED (the `g3r-2026-10-08-1.1.3` scores: sensitivity 1.0, false alarm 0.0), and every anchor frame equal to `frames-reference.json`. `--check` writes no `validators.yaml`.
- **D2 — The run reports what it finds.** Each FAIL is a finding in `bugs.md` and one new `deferred-work.md` entry. Gate 1 is reported red when its thresholds miss, and Story 10.8 stays open. Fixes are separate changes; after them the affected test cases are re-run into a new run folder, which the gate then counts. No product fix inside this run.

## Boundaries & Constraints

**Always:**
- Test-plan §9 governs runner captures: the agent reads the review set and every `ESCALATE`, including each `agent_check`. A before-capture or between-step Given named in an `agent_check` is taken by re-running that scenario's steps by MCP up to the named step and capturing there (deferred-work goal 3 rule).
- Every agent-driven scenario closes with a fit and a `cua-driver` capture that the agent reads (§3 rule 4). No MCP field, status or render stands as visual evidence.
- Agent-driven FreeCAD starts with `fcb-freecad start` on a container recreated at run start (clean profile); the runner uses a temporary `-u`/`-s` profile; record the developer `user.cfg` SHA-256 before and after.
- A failed check is a finding with request, output and `file:line`, never a retry to get a PASS. Every runner run and every FreeCAD launch made for the gate is listed in `report.md` with its run folder or log line.
- `report.md` verdicts are final; Gate 1 is computed from them by priority.
- Never open `benchmarks/*/heldout`. No edit to `src/freecad_buddy`, the runner or the test cases during the run.

**Never:**
- Report a scenario PASS whose visual Then was skipped or inferred.
- Change gate thresholds or the §9 review rule.

</frozen-after-approval>

## Code Map

- Run baseline: the integration head at run start, recorded in `RUN-CONTEXT.md`.
- Environment: the `fcb-desktop` container (CLAUDE.md §9, `tests/close-loop/README.md`); never the host FreeCAD. Host shell: `export MSYS_NO_PATHCONV=1`, `PROJECT_ROOT`, `RUN_DIR`, `FCB_PYTHON=$PROJECT_ROOT/scripts/automation/fcb_py.sh`, `FCB_CUA=$PROJECT_ROOT/scripts/automation/fcb_cua.sh` (`tests/uat/test-plan.md` §6). MCP `http://127.0.0.1:18765/mcp` (server `freecad-buddy-docker`); GUI server `cua-driver-docker` or `$FCB_CUA`; tool arguments use `/repo/...` paths.
- `tests/uat/runner/run.py` -- `docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/runner/run.py /repo/tests/uat/scenarios --out /repo/tests/uat/run/<run>/runner` after `fcb-freecad stop`; no `--seed` (§9 gate rule); exit 0/1/2/3. This is run R0; its folder is never written again after R0 ends. A §9 re-run of a launch group that did not start passes only that group's scenario files and its own folder `--out /repo/tests/uat/run/<run>/runner-rerun-<n>` (`n` = 1, 2, ...), never the R0 folder (`run.py` overwrites `results.json` and `summary.md` in `--out`). `report.md` lists every runner run with its folder, `run.sample_seed` and `sample_seed_source: drawn`. The gate count and the §9 review read the R0 rows, except for the scenarios of the re-run group: their R0 `not_run` rows are replaced by the rows of the re-run folder, and the review of those scenarios uses the re-run folder's review set. When a launch group is re-run more than once, the highest-numbered `runner-rerun-<n>` folder that started the group wins for that group's rows; earlier re-run folders stay as records and are listed in `report.md`
- `tests/uat/scenarios/` -- 72 files; 2026-10-23-01 `replay-notes.json` and spec-10-8-b notes list the Thens each partial file hands to `agent_check`
- `tests/uat/testcases/TC-01..TC-14`, `TC-99` -- 255 + 5 scenarios; 174 Critical, 67 High, 14 Medium; agent-driven per TC: 01:15, 02:8, 03:6, 04:14, 05:14, 06:8, 07:18, 08:10, 09:18, 10:14, 11:17, 12:14, 13:16, 14:11
- H1 (headless stdio host) scenarios: TC-06-11, TC-08-05/18, TC-09-01/02/15/19-22, TC-10-01/02/05/07-11, 14 in TC-11, TC-14-09/12/14, TC-99-04/06
- `.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md`, `uat-run-practices.md` -- container preflight, launch (`fcb-freecad start`, ready when `/healthz` shows a number in `freecad_pid`), shutdown, roles, grading, records
- `docker exec -u cua fcb-desktop fcb-py /repo/scripts/automation/uat_watchdog.py --pid <pid> --window <wid> --since "<run start ISO with host UTC offset>"` -- between test cases; a surviving `FCB_TMP_snap_*` stops the run (`tests/uat/README.md:91-116`)
- `tests/uat/g3-gui/g3_gui_replay.py`, `gui.py` -- the G3 GUI replay in container form; the run lead copies both into `$RUN_DIR/evidence/g3-gui/` at run start and runs them there with `uv run --extra dev python g3_gui_replay.py [case-substring ...]` (`pyyaml` is in the `dev` extra of `pyproject.toml`) with container FreeCAD started (`FC_PID`, `FC_WIN` from `/healthz` and `list_windows`; both change at each FreeCAD start). Compare the copies with `tests/uat/g3-gui/` by git blob id (`git hash-object <file>`), not by working-copy SHA-256, because a working copy can have CRLF line endings. A row with `gui_error` set is NOT RUN for the G3 GUI form and never counts as unchanged; the script then prints `NOT RUN` and exits 1, and a run with only clean rows exits 0
- `tests/uat/run/2026-10-03-04/report.md` -- layout: Status, Build banner, Harness gate, Execution notes, `## TC-01`..`## TC-14` (Scenario | Priority | Verdict | Evidence | Note), TC-99 (Scenario | AD | Verdict | Observed), Gate 1 summary (TC | Scenarios | PASS | PARTIAL | FAIL | BLOCKED | SKIP + by priority), Gate 2, G3 replay, Findings, Human interventions, Teardown
- `benchmarks/g3/fault-injection/score_g3_replay.py`, `frames-reference.json`; `benchmarks/_registry/validators.yaml:175-189`; `.github/workflows/ci.yml:138-145`. `/repo` is read-only, so the scorer runs from a container temp copy that leaves out every path with `heldout` in its name: `docker exec -u cua fcb-desktop sh -c 'rm -rf /tmp/g3r && mkdir /tmp/g3r && tar -C /repo --exclude='*heldout*' -cf - benchmarks src | tar -C /tmp/g3r -xf - && cd /tmp/g3r && fcb-py benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.1.x --run g3r-<run>-1.1.4 --check --frames-check benchmarks/g3/fault-injection/frames-reference.json'`, then `docker cp fcb-desktop:/tmp/g3r/benchmarks/gate-artifacts/g3/g3r-<run>-1.1.4 $RUN_DIR/evidence/g3-headless` and remove `/tmp/g3r`
- Run folder `tests/uat/run/<run date>-<NN>/` (first free `NN`; never reused): `RUN-CONTEXT.md`, `report.md`, `bugs.md`, `runner/`, `evidence/` (`launch-log.tsv`, `user-cfg-sha256.txt`, `image-id.txt`, `addon-wheel-sha256.txt`, `e2e_report.json`, `edge_report.json`, `g3-headless/`, `g3-gui/`), `lead-notes/`
- `tests/uat/test-plan.md:457-561` -- Gate 1 and Gate 2 rules

## Tasks & Acceptance

**Preparation (builder; the run lead starts after it is verified):**
- [x] `spec-10-8-d` in container form
- [x] `tests/uat/g3-gui/g3_gui_replay.py` and `gui.py` -- G3 GUI replay in container form; proven on one control case
- [x] S0 proof and G3 headless proof in `tests/uat/run/2026-11-18-10-8-d-prep/` (not a gate result)

**Execution (run lead; phases in order, one phase agent at a time, phase agents on model `sonnet`):**
- [ ] S0 setup: `git status --short` (only the run folder is new); `uv run python scripts/build_addon.py --release`; `docker compose -f tests/close-loop/docker/compose.yaml up -d --build --force-recreate` (clean container profile); record image id, `dist/addon/wheels/*.whl` SHA-256, developer `user.cfg` SHA-256 (`%APPDATA%\FreeCAD\v1-1\user.cfg`); `fcb-py` prints `H1 ok 1.1.4`; `uv run python scripts/automation/run_mcp_e2e.py` and `uv run python scripts/automation/run_mcp_edge_cases.py` exit 0; `docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/probe/run_faults.py` detects 5/5 with 0/2 false alarms; `uv run python tests/uat/runner/pixel_faults.py` detects 4/4 with 0/2 false alarms; write `RUN-CONTEXT.md` -- harness
- [ ] R0 runner: `fcb-freecad stop`, then the runner command of the Code Map on all 72 files with a drawn seed; list every runner run in `report.md` -- §9
- [ ] R0a and R0b review: two agents apply §9 to the review set and every ESCALATE (R0a: TC-02..TC-04 files, R0b: TC-05..TC-14 files; TC-01 has no runner file), including each `agent_check` re-run to its named Given -- §9
- [ ] P1 TC-01; P2 TC-02, TC-03; P3 TC-04; P4 TC-05, TC-06; P5 TC-07; P6 TC-08; P7 TC-09; P8 TC-10; P9 TC-11; P10 TC-12; P11 TC-13; P12 TC-14 and TC-99 -- the 183 agent-driven scenarios and the 5 TC-99 scenarios, watchdog between test cases; compare TC-99 with the Gate 2 documented deviations; TC-02-08 runs as written and a FAIL is a product finding, deferred (decision 34) -- AC1
- [ ] G3 per D1: GUI replay from `$RUN_DIR/evidence/g3-gui/` and the headless scorer from a container temp copy; one agent reads the GUI captures -- AC1
- [ ] End: `tests/uat/run/<id>/report.md`, `bugs.md`, `evidence/`; Gate 1 and Gate 2 tables from the rows; per D2 for any FAIL; the end checklist of `uat-run-practices.md` §10 -- AC1
- [ ] `_bmad-output/implementation-artifacts/deferred-work.md` -- resolve the goal 3 entry, or add one entry per open finding -- consistency
- [ ] After a red run: re-run only the affected scenarios into a new folder when the fixes touch only test cases or the harness (same image id, no `src/` change); a `src/` change re-runs the whole gate (decision 35); record the choice in `RUN-CONTEXT.md` and `report.md`

**Acceptance Criteria:**
- Given the committed run folder, when `report.md` is read, then every one of the 260 scenarios has one verdict with evidence, Gate 1 and Gate 2 are computed from those verdicts, and the G3 result is stated against its reference.
- Given the run's end, when the machine is checked, then no FreeCAD started for the run remains in the container, its `:8765` is free, and the developer `user.cfg` SHA-256 is unchanged.

## Implementation Notes

## Spec Change Log

## Review Triage Log

Lenses: Blind Hunter `a8c8aa7b63e4c504a` (BH, opus, high), Edge Case Hunter `ad07e289463dd768b` (EC, opus, high), Verification Gap `a572992f9c6a84fd9` (VG, sonnet, medium). Diff base `c66b80e`.

| Finding | Verdict | Route | Evidence |
| --- | --- | --- | --- |
| BH5, EC1, EC3, EC6, EC7, VG1 -- `fit`, `view` or `capture` failure leaves a row with a capture and no error | medium | patch | `attempt1-role-mismatch/g3-replay.jsonl` has `fit` = "no Button labelled" and `status: OK`. Fixed: `gui_error()` in `g3_gui_replay.py` sets `row["gui_error"]` and `main` prints it; `shot()` deletes a stale PNG first. Proof: second run rows show `gui_error: None` |
| BH8, EC10 -- scorer temp copy `cp -r /repo/benchmarks` copies `benchmarks/*/heldout` | medium | patch | Seen: the first headless proof copied them. Fixed: `tar --exclude=heldout`; re-run shows `find . -name heldout` count 0 and the same 10/10 DETECTED, frames-check OK |
| BH2, EC13 -- `user.cfg` record: only `-after`, escaped sha256sum form, file names differ from the layout, no equality statement | low | patch | Replaced by `user-cfg-sha256.txt` (baseline, after, `equal: yes`); `addon-wheel-sha256.txt` named as the layout says |
| BH1, BH9, BH13 -- prep evidence not in the reviewed diff, no commands recorded | false | rejected | The diff file held only text proofs; the logs, JSONL and captures are in the same folder and the report names each command. The AST check script is `g3-gui-ast-check.py` |
| BH11 -- history narration in the spec | low | patch | Removed "Review base of this preparation: `c66b80e`"; task line reduced to "`spec-10-8-d` in container form" |
| BH10 -- R0a/R0b leave TC-01 out | low | patch | `spec-10-8-d` now says "TC-01 has no runner file" (plan 6.1: runner files 0) |
| BH7, EC12 -- D1 wording "capture route only"; role filter `push button` also changed | false | rejected | The role filter selects the Fit All toolbar button, part of the Fit All and capture route that decision 36 allows. Recorded in the build report |
| BH3, EC5 -- scripts write under `/repo`, which is read-only; run from `tests/uat/g3-gui/` fails | low | rejected | `tests/uat/run/` is the writable mount; the script header says to copy first; a missing file now shows as `gui_error`. A guard adds code for an unlikely misuse |
| BH4 -- worktree differs from the mounted checkout | low | rejected | Covered by `gui_error` (missing file); the run lead works in the mounted checkout |
| BH6, EC4 -- append mode and fixed PNG names mix retries | low | rejected | Unchanged source behaviour; every run uses a new folder (frozen: "Never reuse"); a guard adds complexity |
| BH12 -- prep folder name breaks `<date>-<NN>` | false | rejected | Leader assigned the folder name; S0 `git status` check holds once the build commit exists |
| BH14, EC9 -- `fc.json` or env vars owner | low | rejected | Code Map names `FC_PID` and `FC_WIN` from `/healthz` and `list_windows`; the proof used them |
| BH-status -- status `in-review` ahead of work | false | rejected | bmad-build step-04 sets `in-review` for this build; run tasks stay open |
| EC2 -- `G3_VIEW_BUTTON` click fails but file is renamed `-iso` | low | patch | Covered by the same `gui_error` check on `row["view"]` |
| EC8 -- exception in `gui()` or MCP call leaves a document open | low | rejected | Unchanged source behaviour, unlikely, fix adds a try/finally |
| EC11 -- `docker cp` nests on re-run | low | rejected | The run folder is new at run start, so `g3-headless` does not exist |
| VG2 -- only one control case; committed bytes differ from proven copy | medium | patch | Reformat came after the first proof. Re-run from byte-identical copies (`g3-gui-script-sha256.txt`): control plus the planted and reverted builds of `wrong-hole-diameter`; status, classification and volumes equal to the 2026-10-03-04 rows |
| VG-other -- `shot` returns `exists` only | low | patch | Same fix as the first row (stale PNG removed before capture) |
| Round 2 (leader fix round, redteam and verifier reports) RT1 -- one runner `--out` lets a re-run overwrite R0 | medium | patch | `run.py` overwrites `results.json` in `--out`. Code Map now gives `runner-rerun-<n>` per re-run and says how the gate count reads R0 plus the re-run rows |
| Round 2, V-F3 -- row with `gui_error` keeps status OK, exit 0 | medium | patch | `main` collects rows with `gui_error`, prints `NOT RUN`, exits 1; spec says such a row is NOT RUN. Proof: wrong `FC_WIN` exits 1, clean row exits 0 (`evidence/fix-round-1/`) |
| Round 2, RT2, RT3, RT4, V-F4, V-F2 -- test-plan line reference, `*heldout*` names, `pyyaml` extra, S0 commands, blob ids | low | patch | Spec lines changed; `find -path '*heldout*'` count 0; `uv run --exact --extra dev` runs the script; blob ids in `script-blob-ids.txt` |
| Round 2, V-F1 -- docstring and `unlink` hunks in the port | low | rejected | The docstring corrects the `:8765` and run-id text and tells the run lead how the file is used (leader brief); `unlink` removes a stale PNG that would report `exists` true (Blind Hunter, Verification Gap) |

## Verification

**Manual checks:**
- `report.md` records the image id, the `dist/addon` wheel SHA-256 and the developer `user.cfg` SHA-256 before and after.
- Every agent-driven capture and every §9 review-set capture is read and described in `report.md`.
- Gate counts in `report.md` match the per-TC tables.
