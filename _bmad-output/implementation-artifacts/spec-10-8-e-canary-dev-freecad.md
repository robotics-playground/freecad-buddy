---
title: 'Canary installs a current FreeCAD dev build and runs both suites'
type: 'bugfix'
created: '2026-11-18'
status: 'done'
baseline_commit: '9aee2bf40bbd3b13dc6f21e8f4484475c264c2c7'
route: 'dispatch'
review_loop_iteration: 3
context:
  - '{project-root}/_bmad-output/implementation-artifacts/plan-10-8.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-10-decisions.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The weekly `canary` job asks conda-forge for `freecad=1.2`. That version never existed, so micromamba fails with `freecad =1.2 * does not exist` and the job never installs FreeCAD or runs a test (all 13 kept logs, 2026-08-24 to 2026-11-16). Commit `23eb932` removed `continue-on-error`, which showed the failure. AD-11 (`ARCHITECTURE-SPINE.md:126`) wants an allowed-to-fail leg on the next FreeCAD line. The architecture documents also name that line "1.2-dev".

**Approach:** Target `freecad>=2026` from conda-forge `main` (version `2026.09.16` is 26.3.0 dev), install the dependency line of `ci.yml:106`, and run both suites. Dev-line test failures become `deferred-work.md` findings. Rename "1.2-dev" in six architecture clauses (decision 37, tier architecture, approved by the user 2026-11-18) and three detail clauses (decision 39: `project-structure.md:321` label `main`, `epics.md:114,276`). Prove the job locally; no push.

## Boundaries & Constraints

**Always:** Channel `conda-forge` only; spec `freecad>=2026`; Python not pinned. Install line `--no-deps -e .` plus `"mcp>=1.28,<2" "trimesh==4.*" "lib3mf==2.*" pytest jsonschema pyyaml`. Triggers stay `schedule` and `workflow_dispatch`. The rule in AD-11 does not change (allowed-to-fail canary; conda-forge if published, else weekly AppImage). Doc edit is the smallest clause: "1.2-dev" becomes "the next FreeCAD development line (weekly builds)" in `ARCHITECTURE-SPINE.md:126,397,452` and `design/project-structure.md:127,235,321`, and in `epics.md:114,276`. `project-structure.md:321` also names label `main` instead of the dev label. A proposal pair (`sprint-change-proposal-2026-11-18-ad11-dev-line.md` and `.html`) records the doc edit.

**Never:** No `continue-on-error` and no `|| true` in `canary.yml`. No AppImage fallback. No change to `ci.yml`, to `src/`, `tests/uat/`, or the container compose files. No change to product code for dev-line failures. No push, no merge. No wording change beyond the nine clauses. `docs/decisions/016-freecad-1-1-only.md` stays unchanged (historical record). The GitHub `workflow_dispatch` run is `NOT RUN`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| New spec solves | micromamba 2.3.3, `conda-forge`, `freecad>=2026` | `+ freecad 2026.*`, env created | N/A |
| Old spec fails | `freecad=1.2`, channels `freecad_dev` then `conda-forge` | `freecad =1.2 * does not exist`, `Could not solve`, exit non-zero | proves the check can go red |
| Suites run | env plus the install line | In-FreeCAD `Ran N tests` line, External pytest summary line | a failing test is a `deferred-work.md` entry |
| Doc residue | both architecture documents and `epics.md` | `grep "1.2-dev"` returns 0 lines; diff is 9 clauses | N/A |

</frozen-after-approval>

## Code Map

- `.github/workflows/canary.yml` -- header comment, the `setup-micromamba` step (`create-args`, `condarc`), the install step, the build-name step and the two suite steps. The only workflow file to change.
- `.github/workflows/ci.yml` -- `headless` job (`:80` on): the pattern (`create-args`, install line `:106`, two suite steps, two-process step `:118-123`). Read only.
- `tests/external/test_ci_workflow.py` -- reads `ci.yml` only, not `canary.yml`. Read only; no new test (tests are outside this slice).
- `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/ARCHITECTURE-SPINE.md:126,397,452` and `design/project-structure.md:127,235,321` -- the six architecture clauses plus clause 7 (`:321` label). Already edited and verified: `grep "1.2-dev"` = 0 lines.
- `_bmad-output/planning-artifacts/sprint-change-proposal-2026-11-18-ad11-dev-line.{md,html}` -- written; HTML checked well formed.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- append-only ledger; entry format `source_spec` / `summary` / `evidence`.
- `_bmad-output/planning-artifacts/epics.md:114,276` -- clauses 8 and 9, edited. Kept as history, named in the proposal: `docs/decisions/016-freecad-1-1-only.md:6,39`, memlogs, research and review notes.

## Tasks & Acceptance

**Execution:**
- [x] `.github/workflows/canary.yml` -- set `freecad>=2026`, channels `conda-forge` only, the `ci.yml:106` install line; update comments (line 3 and 15-17: next development line, weekly builds, conda-forge `main`) -- fixes the solve and gives both suites their imports
- [x] local proof in container `fcb-canary-10-8-e` (`mambaorg/micromamba:2.3.3`, `--rm`, repo read-only, writes under `/tmp`) -- run the old spec (must fail), the new spec solve, the install line, both suites; keep logs under the scratchpad
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- one new entry per distinct dev-line failure cause, with evidence
- [x] `_bmad-output/implementation-artifacts/build-10-8-e.md` -- report, committed
- [x] gates -- `uv run ruff check .`, `uv run python scripts/check_imports.py`, `uv run pytest tests/external/test_ci_workflow.py -q`

**Acceptance Criteria:**
- Given the new `canary.yml` spec, when the job steps run in the micromamba 2.3.3 container, then the solve shows `+ freecad 2026.*` and both suites print their summary lines.
- Given the old spec, when the same solve runs, then it exits non-zero with `does not exist`.
- Given a failing test on the dev line, when it is not a product fix in this slice, then it is a `deferred-work.md` entry.
- Given the two architecture documents and `epics.md`, when searched for `1.2-dev`, then no line matches.
- Given `canary.yml`, when read, then it has no `continue-on-error` and no `|| true`.

## Implementation Notes

- Decision 39 widened the doc edit: `project-structure.md:321` now says label `main`; `epics.md:114,276` carry the new wording (tier detail, boundary AD-11 as corrected). `docs/decisions/016` is kept as a historical record.
- Job id `canary-1_2-dev` renamed `canary-dev-line` (it carried the false name; no workflow or test file references it; `epic-10-status.md:10` names the old id as a dated record).
- `create-args` is split on spaces with no shell and no quote handling (`setup-micromamba` `options.ts`, `util.ts`), so `freecad>=2026` is unquoted.
- Review r2 patches: the build-name step lists freecad, occt and python; later steps run after an earlier failure but not after a failed setup or install (`steps.<id>.outcome`); `actionlint` passes. Gates run: `ruff check .` pass, `check_imports.py` OK, `test_ci_workflow.py` 3 passed. The `if:` behaviour runs only on GitHub (`NOT RUN`).
- Local proof: old spec fails the solve (`freecad =1.2 * does not exist`); new spec `+ freecad 2026.09.16`, `+ occt 8.0.1`, `+ python 3.14.10`; In-FreeCAD `Ran 866 tests`, `FAILED (failures=15, skipped=28)` (same 15 on two runs); External `1809 passed, 4 skipped`. The 15 failures are 13 `deferred-work.md` entries (7 failure entries, 4 entries on missing checks, 2 document entries).

## Spec Change Log

- Decision 41 (leader, fix round E1 to E3) added `tests/external/test_canary_workflow.py` (5 tests), the `project-context.md:21` clause and the `ARCHITECTURE-SPINE.md:452` file attribution (proposal clauses 10 and 11, tier detail), and removed the three matching `deferred-work.md` entries. Doc clause count is now 11. KEEP: the red proof of each assertion in `build-10-8-e.md`.

- Decision 39 (human, 2026-11-18) widened the doc edit from 6 to 9 clauses before review. The frozen text was updated to match; no review finding caused it. KEEP: `docs/decisions/016` unchanged; tier split architecture (1-6) and detail (7-9).

## Review Triage Log

Round 1. Sessions: blind `ad2184936896516b1` (opus, high), edge `af54240701619b998` (opus, high), gap `aa3765257a2dff9b9` (sonnet, medium). Routes: patch, defer, reject.

| Id | Finding | Verdict | Route and evidence |
|----|---------|---------|--------------------|
| B1 | Frozen intent says six clauses, diff has nine | medium | patch: spec updated for decision 39 (human); see Spec Change Log |
| B2 | Code Map and I/O row stale (six, epics unchanged) | low | patch: updated with B1 |
| B3 | `1.2-dev` check omits `epics.md` | medium | patch: AC and Verification include `epics.md` |
| B4 | Tasks unchecked at in-review; report file not in diff | low | patch: tasks ticked; report is written after review (task 4) |
| B5 | Proposal row 6 and After diagram show text that never existed | medium | patch: row 6 now covers only the name; diagram After shows `label main` |
| B6 | Impact table counts epics twice; "two files" rollback | low | patch: separate Epics row, "three files" |
| B7 | HTML script and CSS unused | low | reject: template mandates the CSS and script (review-pack.md); no harm |
| B7b | Shared localStorage key | false | reject: the key carries project slug and date; no checkboxes exist |
| B8 | Literal backticks in HTML | low | patch: plain `main` |
| B9 | Wording varies across clauses (3, 4 lack "(weekly builds)") | low | reject: same meaning; fix adds nothing a reader needs |
| B10 | create-args comment misplaced | low | patch: moved above `create-args` |
| B11 | Comments narrate history and dated facts | medium | patch: dated version and "no 1.2 release" removed |
| B12 | Canary does not print the build under test | medium | patch: `micromamba list -n fc "^freecad$"` step; proven locally |
| B13 | conda-forge lags weekly builds; no fallback trigger | medium | defer: new `deferred-work.md` entry (needs an age rule decision) |
| B14 | Canary omits the two-process host step | medium | defer: new entry |
| B15 | Q6 names a test that does not read `canary.yml` | medium | defer: new entry (tests outside slice); Q6 correction sent to leader |
| B16 | Two failures in one deferred entry; guessed cause | low | patch: entry split, hypothesis marked |
| B17 | Proof logs and harness differences not kept | low | patch: key lines in the report; harness difference stated there |
| B18 | `ARCHITECTURE-SPINE.md:452` says `ci.yml` holds the canary | low | defer: pre-existing wrong attribution outside the nine clauses; named in the report |
| E1 | External suite skipped when In-FreeCAD fails (default `success()`) | high | patch: `if: ${{ !cancelled() }}` on the External suite |
| E2 | Stale build is not detected | medium | defer: same as B13 |
| E3 | AppImage fallback never triggers | medium | defer: same as B13 |
| E4 | Known failures hide a new one | medium | defer: new entry |
| E5 | Proposal After diagram says dev label | medium | patch: same as B5 |
| E6 | Rollback says two files | low | patch: same as B6 |
| E7 | Backticks in HTML | low | patch: same as B8 |
| E8 | AC "both suites print" fails in the GitHub job because of E1 | high | patch: same as E1 |
| E9 | Frozen text says six, diff nine | medium | patch: same as B1 |
| E10 | "resolves to the newest" overstated | low | patch: wording is now "lets the solver pick the newest solvable build" |
| G1 | Nothing tests `canary.yml` | medium | defer: same entry as B15 |
| G2 | Canary always red hides new regressions | medium | defer: same entry as E4 |
| G3 | Two-process step omitted, not recorded | medium | defer: same entry as B14 |
| G4 | Unused HTML script | low | reject: same as B7 |
| G5 | Local checks confirm grep and masking absent | none | no action: confirms Q5, Q7 |

Round 2. Sessions: blind `adf1bba2c02831e55` (opus, high), edge `a2cff3d8bb61ff425` (opus, high), gap `a9b49cc4f584d4671` (sonnet, medium).

| Id | Finding | Verdict | Route and evidence |
|----|---------|---------|--------------------|
| R2-1 | External suite runs after a failed setup or install (also edge 1, 2, 3, gap 1) | medium | patch: `setup` and `install` ids, `steps.<id>.outcome == 'success'` on list and both suites; `actionlint` exit 0 |
| R2-2 | Baseline sentence says six entries; there are seven | low | patch: reworded |
| R2-3 | Local-proof and gates tasks unticked | low | patch: ticked; gate output in Implementation Notes |
| R2-4 | Report ticked but absent | low | reject: the report is written and committed with this batch (task 4) |
| R2-5 | B18 deferred without an entry | low | patch: entry added |
| R2-6 | `_bmad-output/project-context.md:21` says 1.2-dev | medium | defer: entry added; outside decisions 37 and 39, the leader widens the list |
| R2-7 | Proposal cites decision 37 only | low | patch: decision 39 added to MD and HTML |
| R2-8 | "probably accounts for 4 skipped" hedge | low | patch: states the reasons were not recorded |
| R2-9 | No skip baseline against 1.1.3 | low | defer: sentence added to the known-failures entry |
| R2-10 | Build-name step omits occt and python | low | patch: regex `^(freecad\|occt\|python)$` |
| R2-11 | Local harness uses micromamba 2.3.3; the action installs the latest | low | reject: `ci.yml` does not pin either; stated in the report; GitHub run is NOT RUN |
| R2-12 | `freecad>=2026` assumes calendar versions | medium | defer: added to the lag entry |
| R2-13 | "next FreeCAD development line" may become ambiguous when 26.3 ships | low | reject: wording set by decision 37; the canary targets conda-forge weekly builds |
| R2-14 | First failure entry groups three modules under one guess | low | patch: states the grouping is unverified |
| R2-15 | "will not exist" unsourced | low | reject: `plan-10-8.md` section 5 says "'1.2' was never released and will not be" |
| R2-16 | Code Map line numbers stale | low | patch: line numbers removed or corrected |
| R2-17 | Header comment too wide | low | patch: rewrapped |
| R2-18 | Build-name step failure would skip the In-FreeCAD suite (edge) | low | patch: same as R2-1 |
| R2-19 | Spec says no file references the old job id; `epic-10-status.md:10` does | low | patch: note names it as a dated record |
| R2-20 | `if:` guard has no test (gap) | medium | defer: added to the `canary.yml` test entry |
| R2-21 | "git diff shows only nine clauses" scope | low | patch: says the three planning documents |

Round 3. Sessions: blind `aab8bcc1503d87dcf` (opus, high), edge `a67501a4588bd52c2` (opus, high), gap `a17ea58fa33ef4736` (sonnet, medium). No high or medium finding that is new.

| Id | Finding | Verdict | Route and evidence |
|----|---------|---------|--------------------|
| R3-1 | Comment says all steps skip after a failed install; the build-name step needs only the environment | low | patch: comment split per step |
| R3-2 | Comment says `main` publishes weekly builds; one build is shown | low | patch: "has published dev builds" |
| R3-3 | Triage row R2-10 shows the regex without `\|` | low | patch: row corrected; `new4.log` shows the output |
| R3-4 | Verification command hides the proof commands | low | patch: script path and text go to `build-10-8-e.md`; command written out |
| R3-5 | `actionlint` claimed but not in Verification | low | patch: command added |
| R3-6 | Deferred entry says `ci.yml:117-124`; the step is `:118-123` | low | patch: corrected |
| R3-7 | Entry count 7 plus 4 omits the 2 document entries | low | patch: 13 entries stated |
| R3-8 | Proposal MD "4 lines" for project-structure | low | patch: "4 clauses on 3 lines" |
| R3-9 | Proposal MD summary names two sources | low | patch: names `epics.md` |
| R3-10 | HTML process diagram cites decision 37 only | low | patch: "decisions 37, 39" |
| R3-11 | HTML says "Agent behaviour: No change" while agents read the documents | low | patch: "Intended change" |
| R3-12 | Lag evidence is the same-day weekly build | low | patch: cites the 2026-09-23 upload and `26.3rc2` on 2026-10-18 |
| R3-13 | Build-name step has no `name:` | low | patch: `name: Build under test` |
| R3-14 | `freecadcmd` may exit 0 on test failure | false | reject: `INFC_EXIT=1` in `new2.log`, `new3.log` after `FAILED (failures=15)` |
| R3-15 | Setup and install steps have no timeout | low | patch: job `timeout-minutes: 60` |
| R3-16 | Report ticked but absent (also gap) | low | reject: written and committed with this batch |
| R3-17 | `new4.log` empty when read; "run twice" unverifiable | low | reject: `new4.log` is filled after the run; three runs show the same 15 |
| R3-18 | No test for `canary.yml` (gap) | medium | carried: R2-20 |

## Verification

**Commands:**
- `docker run --rm --name fcb-canary-10-8-e -v <worktree>:/repo:ro -v <script>:/job.sh:ro --entrypoint bash mambaorg/micromamba:2.3.3 /job.sh old|new` -- expected: solve, suites, old-spec failure as above. The script text is in `build-10-8-e.md`; it copies the repo to `/tmp` because the mount is read-only.
- `docker run --rm -v <worktree>:/repo:ro rhysd/actionlint:latest -color=false /repo/.github/workflows/canary.yml` -- expected: exit 0
- `uv run ruff check .` -- expected: no findings
- `uv run python scripts/check_imports.py` -- expected: exit 0
- `grep -n "1.2-dev" <the two architecture files> epics.md` -- expected: no output

**Manual checks (if no CLI):**
- GitHub `workflow_dispatch` run: `NOT RUN` (needs a push, decision 28).
