# Build report: Story 10-8-e (canary installs a dev FreeCAD)

Branch `story/10-8-e-canary-dev-freecad`, base `9aee2bf`. Spec: `spec-10-8-e-canary-dev-freecad.md` (status `in-review`, review loop 3). Proposal pair: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-11-18-ad11-dev-line.{md,html}`.

## Result

The canary job now resolves `freecad>=2026` from conda-forge `main`, installs the `ci.yml:106` dependency line, names the build under test, and runs both suites. It ran locally to the end. 15 In-FreeCAD tests fail on the dev line; they are 7 entries in `deferred-work.md`. The GitHub `workflow_dispatch` run is `NOT RUN` (needs a push, decision 28).

Changes:
- `.github/workflows/canary.yml`: `freecad>=2026`, channel `conda-forge` only, install line of `ci.yml:106`, step ids `setup` and `install`, step `Build under test` (`micromamba list` for freecad, occt, python), `if: ${{ !cancelled() && ... }}` so the External suite runs after an In-FreeCAD failure, job `timeout-minutes: 60`, job id `canary-1_2-dev` renamed `canary-dev-line`, comments rewritten.
- 9 wording clauses (decisions 37 and 39): `ARCHITECTURE-SPINE.md:126,397,452`, `design/project-structure.md:127,235,321` (two clauses on `:321`), `epics.md:114,276`. `docs/decisions/016` kept as a historical record.
- Proposal pair, spec, 13 new `deferred-work.md` entries (7 failure, 4 missing checks, 2 document), this report.

## Local job proof (quality bar Q1 to Q4, Q10)

Container `fcb-canary-10-8-e`, image `mambaorg/micromamba:2.3.3`, `--rm`, repo mounted read-only at `/repo`, writes under `/tmp`. The container is gone; `docker ps -a` shows none.

| Check | Result |
| --- | --- |
| Old spec (`freecad=1.2`, channel `freecad_dev` then `conda-forge`) | `freecad =1.2 * does not exist`, `critical libmamba Could not solve for environment specs`, `SOLVE_EXIT=1` (check can go red) |
| New spec solve | `+ freecad 2026.09.16 py314h1b0b3cc_0`, `+ occt 8.0.1`, `+ python 3.14.10`, `Total download: 792MB`, `SOLVE_EXIT=0` |
| Install line | `Successfully installed freecad-buddy-0.1.1`; dependency line installed (mcp, trimesh, lib3mf 2.5.0, jsonschema, pyyaml, pytest); no import error in the External suite |
| Build step | `micromamba list -n fc "^(freecad\|occt\|python)$"` lists freecad 2026.09.16, occt 8.0.1, python 3.14.10 |
| In-FreeCAD suite | `Ran 866 tests in 10.180s`, `FAILED (failures=15, skipped=28)`, `INFC_EXIT=1` |
| External suite | `1809 passed, 4 skipped, 20 warnings in 87.81s`, `EXT_EXIT=0` |
| Repeat | the same 15 failures in 3 full runs (`new2.log`, `new3.log`, `new4.log`) |
| `actionlint` (`rhysd/actionlint:latest`) | exit 0 on `canary.yml` |

Gates: `uv run ruff check .` pass; `uv run python scripts/check_imports.py` `check_imports OK`; `uv run pytest tests/external/test_ci_workflow.py -q` 3 passed. `grep "1.2-dev"` on the two architecture files and `epics.md`: no line. `grep "continue-on-error\|\|\| true"` on `canary.yml`: no line. Triggers: `schedule` and `workflow_dispatch` only.

Not proven locally: the `if:` conditions and the `setup-micromamba` action path (unquoted `create-args`, read from the action source, not run). The local harness uses micromamba 2.3.3; the action installs the latest and `ci.yml` does not pin it either. Levels: Unit (`test_ci_workflow.py`) RUN; E2E (job steps in Linux) RUN; UAT BLOCKED (CI workflow, no GUI); GitHub canary run NOT RUN.

## The 15 dev-line failures (deferred-work.md)

FreeCAD 2026.09.16 (26.3.0 dev), OCCT 8.0.1, Python 3.14.10. Causes not investigated (Python 3.14 and OCCT 8 are not separable here).

| Group | Tests | Count |
| --- | --- | --- |
| Undo and rollback | `test_document_undo.RefusalTest` (2), `test_g2_driver.DrivenCaseTest` (1), `test_mutation_protocol.RollbackProofTest` (2) | 5 |
| Fingerprint byte fixture | `test_document_undo.ExpectFingerprintRecordTest` | 3 |
| Spent token digest | `test_confirm_gate.SpentTokenTest` | 1 |
| STEP error text | `test_export_tools.ExportStepSchemaTest` | 2 |
| TNP guard layer 1 | `test_tnp_guard.LayerOneTest` | 2 |
| Sketch left `Touched` | `test_verify_tools.VerifySketchTest` | 1 |
| Tie break | `test_assertion_primitives.LargestPlanarFaceTieBreakTest` | 1 |

## Review

Three rounds, each with the three lenses as fresh subagents (a subagent cannot take a name, so the session ids below stand for the names `review-<lens>-r<n>-s10-8-e`).

| Round | Blind Hunter (opus, high) | Edge Cases Hunter (opus, high) | Verification Gap Finder (sonnet, medium) |
| --- | --- | --- | --- |
| r1 | `ad2184936896516b1` | `af54240701619b998` | `aa3765257a2dff9b9` |
| r2 | `adf1bba2c02831e55` | `a2cff3d8bb61ff425` | `a9b49cc4f584d4671` |
| r3 | `aab8bcc1503d87dcf` | `a67501a4588bd52c2` | `a17ea58fa33ef4736` |

Every finding has a row in the spec `## Review Triage Log`. Summary:
- High, patched (r1): the External suite step was skipped when an In-FreeCAD test failed (default `success()`). Fixed with `if: ${{ !cancelled() && steps.install.outcome == 'success' }}`.
- Medium, patched: frozen intent said six clauses (now nine, decision 39); proposal rows showed text that never existed; dated facts and history in comments; build under test not named; later steps ran after a failed setup (r2).
- Deferred (entries in `deferred-work.md`): conda-forge lag and the calendar-version assumption of `freecad>=2026`; the omitted two-process step; no test reads `canary.yml` (also covers the `if:` guard); the known-failure baseline and skip counts; `ARCHITECTURE-SPINE.md:452` names `ci.yml` as the canary file (pre-existing); `_bmad-output/project-context.md:21` still says "1.2-dev".
- Rejected with evidence: `freecadcmd` exit code (`INFC_EXIT=1`), template script and CSS, wording variants, micromamba version pin, "next line" ambiguity.
- r3 patches were comments, a step name, a job timeout and document text; they were verified with `actionlint`, the gates and the final run, with no fourth round.

## Fix round E1 to E3 (decision 41)

- E1: `tests/external/test_canary_workflow.py`, 5 tests at that commit (7 after E4) beside `test_ci_workflow.py`: triggers exactly `schedule` and `workflow_dispatch`; spec `freecad>=2026` with channel `conda-forge` only; install line equals the `ci.yml` headless install line (read from `ci.yml`); no `continue-on-error` and no `|| true`; the External suite `if:` holds `!cancelled()`. The "no test reads `canary.yml`" deferred entry is removed.
- Red proof (mutated copies of `canary.yml` in a temp directory, each test called on its copy; the tracked file is unchanged). Baseline: all 5 pass.

| Test | Mutation | Result |
| --- | --- | --- |
| triggers | add `push:` | RED |
| solve | spec `freecad=1.2` | RED |
| solve | add channel `conda-forge/label/freecad_dev` | RED |
| install line | drop `"lib3mf==2.*"` | RED |
| no masking | `continue-on-error: true` on External suite | RED (`['External suite']`) |
| no masking | `pytest tests/external \|\| true` | RED (`['External suite']`) |
| `!cancelled()` | remove the `if:` from External suite | RED |

- E2: `_bmad-output/project-context.md:21` now says "a canary on the next FreeCAD development line (weekly builds) is allowed-to-fail" (proposal clause 10, tier detail, boundary corrected AD-11).
- E3: `ARCHITECTURE-SPINE.md:452` now says `# ci.yml: one blocking 1.1.x leg; canary.yml: canary on the next FreeCAD development line` (clause 11, tier detail, boundary: canary row of `project-structure.md` and `canary.yml`). The deferred entry is removed.
- Proposal pair: 11 clauses (6 architecture, 5 detail). `deferred-work.md` now holds 10 entries from this story (7 failure groups, 3 missing checks).

## Fix round E4 (red team RT1 to RT5)

`tests/external/test_canary_workflow.py` is now an allowlist of the workflow structure (7 tests, was 5):
- RT1: the `In-FreeCAD suite` and `External suite` steps exist and their `run` text equals the `ci.yml` headless commands (read from `ci.yml`).
- RT2: no `continue-on-error`, `shell` or `defaults` key at workflow, job or step level; no `||` or `set +e` in any `run`.
- RT3: each suite `if:` equals `${{ !cancelled() && steps.install.outcome == 'success' }}`; the job has no `if:`.
- RT4: the YAML loader rejects duplicate keys (`have_unique_keys_when_canary_yml_is_parsed`).
- RT5: setup inputs are a subset of `environment-name`, `create-args`, `condarc`, `cache-environment`; spec and channel unchanged.

Red proof: the red team's mutations, applied to a mutated copy of `canary.yml` in a temp directory (module global pointed at the copy; the tracked file is unchanged). Baseline: all 7 pass.

| Mutant | Change | Red tests |
| --- | --- | --- |
| M1 | delete step `In-FreeCAD suite` | suite commands; suite conditions |
| M2 | External `if: ${{ !cancelled() && false }}` | suite conditions |
| M3 | job `if: false` | suite conditions (job `if`) |
| M3b | job `if: github.event_name == 'push'` | suite conditions (job `if`) |
| M4 | External `run: ... \|\| exit 0` | suite commands; no hidden failure |
| M7 | External `shell: bash {0}` | no hidden failure |
| M8 | workflow `defaults: run: shell: bash {0}` | no hidden failure |
| M8b | `set +e;` in the In-FreeCAD `run` | suite commands; no hidden failure |
| M9 | External narrowed to `tests/external/test_canary_workflow.py` | suite commands |
| M10 | setup `environment-file` input | solve inputs |
| M12 | second `if:` key on External | unique keys (and every test that loads the file) |
| M13 | External `run: ... \|\| /bin/true` | suite commands; no hidden failure |

Earlier E1 mutations (push trigger, `freecad=1.2`, `freecad_dev` channel, `lib3mf` dropped, `continue-on-error`, `\|\| true`, `if:` removed) stay red: the triggers, solve, install-line and no-hidden-failure tests keep the same checks.

## For the leader

- The old job id `canary-1_2-dev` remains in `epic-10-status.md:10` as a dated record.
- Next step for the full proof: a push, then `gh workflow run canary.yml --ref story/10-8-e-canary-dev-freecad`; the log must show the solve line, the build step, the `Ran N tests` line and the pytest summary line.

## Proof harness (script run inside the container)

```bash
#!/bin/bash
# runs the canary job steps inside the micromamba container; $1 = old|new
set -u
export MAMBA_ROOT_PREFIX=/tmp/mamba
mode=$1
if [ "$mode" = old ]; then
  micromamba create -y -n fc -c conda-forge/label/freecad_dev -c conda-forge "freecad=1.2" ; echo "SOLVE_EXIT=$?"; exit 0
fi
micromamba create -y -n fc -c conda-forge "freecad>=2026" 2>&1 | grep -E "^\s+\+ (freecad|python|occt) |Total download|critical|does not exist"
echo "SOLVE_EXIT=${PIPESTATUS[0]}"
cp -r /repo /tmp/repo && cd /tmp/repo
micromamba run -n fc python -m pip install --no-deps -e . 2>&1 | tail -2
micromamba run -n fc python -m pip install "mcp>=1.28,<2" "trimesh==4.*" "lib3mf==2.*" pytest jsonschema pyyaml 2>&1 | tail -2
micromamba list -n fc "^(freecad|occt|python)$" 2>&1 | tail -5
echo "=== IN-FREECAD SUITE"
micromamba run -n fc freecadcmd tests/run_tests.py > /tmp/infc.log 2>&1; echo "INFC_EXIT=$?"; grep -E "^(FAIL|ERROR): |^[A-Za-z]*Error: |^Ran |^FAILED|^OK" /tmp/infc.log | cut -c1-260
echo "=== EXTERNAL SUITE"
micromamba run -n fc pytest tests/external -q -p no:cacheprovider > /tmp/ext.log 2>&1; echo "EXT_EXIT=$?"; tail -1 /tmp/ext.log
```

Run: `docker run --rm --name fcb-canary-10-8-e -v <worktree>:/repo:ro -v <job.sh>:/job.sh:ro --entrypoint bash mambaorg/micromamba:2.3.3 /job.sh old` (or `new`). The script copies the repo to `/tmp/repo` because the mount is read-only.
