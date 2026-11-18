# Story 10-8-e verification: canary on the next FreeCAD development line

Verifier: verifier-10-8-e (claude-opus-5-5). Date: 2026-11-18.
Commit under test: `be3e5a16bea47679a8529656c7b852fc9a900cfd` (branch `story/10-8-e-canary-dev-freecad`), base `9aee2bf`.
Detached copy: `D:\Work\Personal\Sources\fcb-verify-10-8-e` (removed after the run).

**Verdict: FAIL — one reason, documentation only.** Task 5 is not met. 5 of the 10 new `deferred-work.md` entries give no unblock condition, and no entry names its blocker in a separate statement. All of Q1 to Q10 pass. The canary job proof agrees with the builder: the same 15 In-FreeCAD failures.

Note: the Story branch head moved to `72488ba` during this run. That commit changes `tests/external/test_canary_workflow.py` and `build-10-8-e.md` only. `canary.yml` is the same, so the job proof still applies. The new test file at `72488ba` is **not verified**.

## 1. Gates at be3e5a1

| Command | Result |
| --- | --- |
| `uv run ruff check .` | `All checks passed!` |
| `uv run python scripts/check_imports.py` | `check_imports OK`, exit 0 |
| `uv run pytest tests/external/test_canary_workflow.py tests/external/test_ci_workflow.py -q` | `8 passed` (5 canary + 3 ci) |
| `uv run pytest tests/external -q` run 1 | `1 failed, 1813 passed, 4 skipped` |
| `uv run pytest tests/external -q` run 2 | `1814 passed, 4 skipped` |

The run 1 failure is `tests/external/test_marshal_self_submit.py::test_submitting_to_a_loop_this_thread_must_pump_deadlocks`:

```
tests/external/test_marshal_self_submit.py:48
    assert time.monotonic() - start >= 0.2, "the caller waits out its whole budget"
E   assert (29965.1128937 - 29964.9129753) >= 0.2      # 0.19992 s
```

It passed 3 of 3 when run alone, and the full run 2 was green. The diff does not touch this test or `marshal`. It is a timing flake: the measured wait is 0.08 ms short of 0.2 s. The epic Environment block does not name this test (it names `test_managed_venv`, which passed in both runs). Finding F3.

Setup note: the first gate runs used the global `pytest.exe`, because a plain `uv sync` does not install the `dev` extra (`pyproject.toml:22`). That gave 5 collection errors (`No module named 'mcp.client.streamable_http'`, global `mcp`). After `uv sync --extra dev`, the counts above are from the venv `pytest`.

## 2. Falsification

Each mutation was applied to `canary.yml` in the copy, then `test_canary_workflow.py` was run, then the file was restored (`git diff --quiet` checked after each one).

| # | Mutation | Red test |
| --- | --- | --- |
| M1 | `continue-on-error: true` on step `External suite` | `test_should_not_hide_a_failure_when_canary_yml_is_read` |
| M1b | `continue-on-error: true` on the job | same |
| M2 | `freecad>=2026` → `freecad=1.2` | `test_should_ask_a_dev_freecad_from_conda_forge_only_when_the_environment_is_solved` |
| M3 | add channel `conda-forge/label/freecad_dev` | same |
| M4 | `pytest tests/external \|\| true` | `test_should_not_hide_a_failure_when_canary_yml_is_read` |
| M5 | add `push:` trigger | `test_should_run_only_on_schedule_and_dispatch_when_canary_yml_is_read` |
| M6 | drop `"mcp>=1.28,<2"` from the install line | `test_should_install_the_ci_headless_dependency_line_when_the_package_is_installed` |
| M7 | remove the `if:` from `External suite` | `test_should_run_the_external_suite_after_a_failed_in_freecad_suite_when_canary_yml_is_read` |
| R1 | builder mutation re-sampled: drop `"lib3mf==2.*"` | `test_should_install_the_ci_headless_dependency_line_...` (matches builder row `build-10-8-e.md:74`) |

Each mutation turned exactly one test red (`1 failed, 4 passed`).

Gap found (low, F4): `if: ${{ !cancelled() }}` on both suites, without `&& steps.install.outcome == 'success'`, gives `5 passed`. The guard at `canary.yml:47` and `:51` is explained in the comment at `canary.yml:38-41`, but no test pins it.

## 3. Job proof (E2E, local container)

Container `fcb-canary-verify-10-8-e`, image `mambaorg/micromamba:2.3.3` (`sha256:36c78ef8c25f...`), `--rm`. The copy was mounted read-only at `/src` and copied to `/tmp/work`. `MAMBA_ROOT_PREFIX=/tmp/mamba`, `CONDARC` lists `conda-forge` only. The script runs each `canary.yml` step command. I did not read the builder logs before this run. The SHA-256 of `canary.yml` in the container (`c019d0b0...`) equals the file at `be3e5a1`.

| Step | Result |
| --- | --- |
| Old spec, dry run: `-c conda-forge/label/freecad_dev -c conda-forge "freecad=1.2"` | exit 1: `freecad =1.2 * does not exist (perhaps a typo or a missing channel).` / `critical libmamba Could not solve for environment specs` |
| setup: `micromamba create -n fc "freecad>=2026"` | exit 0: `+ freecad  2026.09.16  py314h1b0b3cc_0  conda-forge` / `+ occt 8.0.1` / `+ python 3.14.10` |
| install (`canary.yml:37`) | exit 0, `Successfully installed ... lib3mf-2.5.0 mcp-1.30.0 ... trimesh-4.12.2 ...` |
| Build under test | `freecad 2026.09.16`, `occt 8.0.1`, `python 3.14.10` |
| In-FreeCAD suite | exit 1: `Ran 866 tests in 10.822s` / `FAILED (failures=15, skipped=28)` |
| External suite | exit 1: `1 failed, 1813 passed, 4 skipped` |

The 15 In-FreeCAD failures, compared with the 7 failure entries in `deferred-work.md` (lines 1937-1963 at `be3e5a1`):

| deferred-work entry | My failing tests | Match |
| --- | --- | --- |
| Undo and rollback (5) | `test_document_undo.RefusalTest` ×2, `test_g2_driver...undoing_a_padded_sketch`, `test_mutation_protocol.RollbackProofTest` ×2 | yes |
| Fingerprint byte divergence (3) | `test_document_undo.ExpectFingerprintRecordTest` ×3 | yes |
| Confirm gate (1) | `test_confirm_gate.SpentTokenTest...digest_unmoved` | yes |
| STEP error text (2) | `test_export_tools.ExportStepSchemaTest` ×2 | yes |
| TNP guard (2) | `test_tnp_guard.LayerOneTest` ×2 | yes |
| verify_sketch Touched (1) | `test_verify_tools.VerifySketchTest...solved_file_sketch_is_verified` | yes |
| Largest planar face tie (1) | `test_assertion_primitives.LargestPlanarFaceTieBreakTest...` | yes |

The set is the same, 15 of 15.

The External suite is different. One test failed that `deferred-work.md` does not list:

```
FAILED tests/external/test_rpc_listener.py::test_should_close_a_silent_connection_and_serve_others_when_the_hello_deadline_passes
```

Second container run, same image and same solve (`freecad 2026.09.16`, `python 3.14.10`): that test passed 10 of 10 alone, the whole file `34 passed` 3 of 3, and the full External suite `1814 passed, 4 skipped`, exit 0. It is a timing flake (the test sets `_HELLO_TIMEOUT_S` to 0.3 s at `test_rpc_listener.py:827`). It is not a failure caused by the dev line. It can still turn a weekly canary run red with no new regression. Finding F2.

The 4 External skips have one recorded reason (from `-rs`). All 4 are in `tests/external/test_headless_two_process.py` (lines 612, 706, 812, 825): `needs an interpreter that can import FreeCAD`. The deferred entry at line 1973 says this reason was not recorded. This report records it.

actionlint: `rhysd/actionlint:1.7.7` (pinned tag), `-no-color .github/workflows/canary.yml`: no output, exit 0.

## 4. AC map (quality bar Q1-Q10)

| Q | Check | Evidence | Result |
| --- | --- | --- | --- |
| Q1 | spec `freecad>=2026`, channel `conda-forge` only, solve gives `+ freecad 2026.*` | `canary.yml:28-32`; test at `test_canary_workflow.py:54-64`; job proof solve line `+ freecad 2026.09.16` | PASS |
| Q2 | old spec fails the solve | job proof: `freecad =1.2 * does not exist`, exit 1 | PASS |
| Q3 | install line equals `ci.yml:106`; External suite imports work | `canary.yml:37` = `ci.yml:106` (grep); test at `test_canary_workflow.py:67-75`; job proof External suite collected and ran 1818 tests, no import error | PASS |
| Q4 | both suites run on the dev build | `Ran 866 tests ... FAILED (failures=15, skipped=28)`; `1 failed, 1813 passed, 4 skipped` (re-run `1814 passed`) | PASS |
| Q5 | each dev-line failure is an entry; no `continue-on-error`, no `\|\| true` | 15 of 15 in 7 entries (section 3); `canary.yml` has neither (test at `:78-93`, M1/M1b/M4 red) | PASS |
| Q6 | triggers `schedule` and `workflow_dispatch` only | `canary.yml:6-9`; test at `:43-51` (M5 red); actionlint exit 0 | PASS |
| Q7 | wording replaced; `project-structure.md:321` names label `main`; no other wording change; `docs/decisions/016` unchanged | `git diff -U0 9aee2bf be3e5a1` on the 4 files: 9 changed lines (spine 126, 397, 452; project-structure 127, 235, 321; epics 114, 276; project-context 21). Each maps to proposal clauses 1-11 (452 = clauses 3+11; 321 = clauses 6+7). No other changed line. `grep "1.2-dev"` on the 4 files and the workflows: no match. `git diff --stat 9aee2bf be3e5a1 -- docs/decisions/`: empty | PASS |
| Q8 | proposal pair records tier, citation and approval per clause | `.md:24-36`: 11 rows with tier; `.md:14` approval (decision 37 for 1-6, 39 for 7-9, 41 for 10-11). `.html` appendix rows 1-11 with tier and boundary; decisions confirmed in `epic-10-decisions.md` rows 37, 39, 41 | PASS (F5 minor) |
| Q9 | gates green | section 1 | PASS (F3 flake not caused by the diff) |
| Q10 | GitHub dispatch run reported NOT RUN | `build-10-8-e.md:7` | PASS |

## 5. New deferred-work entries: blocker and unblock condition

Lines refer to `deferred-work.md` at `be3e5a1`.

| Line | Entry | Blocker named | Unblock condition |
| --- | --- | --- | --- |
| 1937 | undo and rollback (5 tests) | implied: "Cause not investigated" | yes: "investigate on a dev-line FreeCAD, then fix the shim or the tests" |
| 1941 | fingerprint byte divergence (3) | no | **no** |
| 1945 | confirm gate digest (1) | no | **no** |
| 1949 | STEP error text (2) | no (a fix is named) | **no** |
| 1953 | TNP guard (2) | implied | yes: "reproduce on the dev line and decide whether the guard needs a new capability probe" |
| 1957 | verify_sketch Touched (1) | no | **no** |
| 1961 | largest planar face tie (1) | no | **no** |
| 1965 | known-failure baseline | yes (the 15 failures) | yes |
| 1969 | conda-forge lag | implied (decision needed) | yes: "decide an age limit ..." |
| 1973 | two-process step omitted | yes: "Decision 32 asked for the two suites only" | yes |

Result: **FAIL.** 5 of 10 entries (1941, 1945, 1949, 1957, 1961) have no unblock condition. No entry names a blocker as its own statement. For the 7 failure entries the shared blocker is the same: AD-11 allows the canary to fail, and decision 41 deferred the 15 failures out of slice 10-8-e. Proposed fix (text only, `deferred-work.md`): add one `Blocker:` and one `Unblock:` statement to each of the 5 entries, for example "Blocker: deferred by decision 41 (AD-11 allowed-to-fail). Unblock: reproduce on a dev-line FreeCAD, then fix the shim or the test."

## 6. Findings

| ID | Severity | Finding |
| --- | --- | --- |
| F1 | medium (fails task 5) | 5 of 10 new `deferred-work.md` entries have no unblock condition, and none names its blocker (section 5). Owner: builder; text edit only. |
| F2 | low | `test_rpc_listener.py::test_should_close_a_silent_connection_and_serve_others_when_the_hello_deadline_passes` failed once in the canary environment and then passed 10 of 10, 3 of 3 (file) and full suite. It can turn a canary run red with no regression. It is not in `deferred-work.md`. Proposed: a deferred entry, or add it to the known-unstable list. |
| F3 | low | `test_marshal_self_submit.py:48` failed once on the host (0.19992 s < 0.2 s), then passed. Not caused by this diff. It is not in the Environment known-unstable list. |
| F4 | low | No test pins the `steps.install.outcome == 'success'` guard at `canary.yml:47,51`. Dropping it from both suites keeps `5 passed`. |
| F5 | low | Proposal `.html:105` status badges name decisions 37 and 39 only. Clauses 10 and 11 (decision 41) are not in that row; `.html:121` and `:180` do name decision 41. Also `build-10-8-e.md:12` says "13 new entries", but `:81` and the ledger show 10. |

## 7. Levels

| Level | Status |
| --- | --- |
| Unit (`test_canary_workflow.py`, `test_ci_workflow.py`) | RUN, `8 passed`, 9 mutations red |
| E2E (canary job steps in a local micromamba container) | RUN, section 3 |
| Integration | covered inside E2E (In-FreeCAD suite, 866 tests) |
| UAT | BLOCKED: CI workflow, no user-visible GUI |
| GitHub `workflow_dispatch` run | NOT RUN: needs a push (decision 28) |

## 8. Re-run at 72488ba

Commit: `72488ba` (fix round E4, base `be3e5a1`). `git diff be3e5a1 72488ba -- .github/` is empty, so the job proof in section 3 still applies. New detached copy `fcb-verify-10-8-e` at `72488ba`, `uv sync --extra dev`.

**Verdict for 72488ba: FAIL.** All of the requested mutants are red and the test does not over-fit. My own mutation found one new false pass (V-F6, medium, a test gap). F1 (section 5) is still open, because `72488ba` does not change `deferred-work.md`.

### 8.1 Gates

| Command | Result |
| --- | --- |
| `uv run ruff check .` | `All checks passed!` |
| `uv run ruff format --check tests/external/test_canary_workflow.py` | `1 file already formatted` |
| `uv run python scripts/check_imports.py` | `check_imports OK` |
| `uv run pytest tests/external/test_canary_workflow.py tests/external/test_ci_workflow.py -q` | `10 passed` (7 canary + 3 ci) |
| actionlint 1.7.7 on the real `canary.yml` | exit 0 |

### 8.2 Mutations

Driver: `mutate72.py` in the scratchpad. It writes each mutant over `canary.yml` in the copy, runs `pytest tests/external/test_canary_workflow.py`, and restores the file in a `finally` block. `git status --porcelain` was empty after the run.

| Group | Mutant | Result | Red tests |
| --- | --- | --- | --- |
| E1 | add `push:` trigger | RED | triggers |
| E1 | `freecad=1.2` | RED | solve |
| E1 | add channel `conda-forge/label/freecad_dev` | RED | solve |
| E1 | drop `"lib3mf==2.*"` | RED | install line |
| E1 | `continue-on-error: true` on External | RED | no hidden failure |
| E1 | `\|\| true` on External | RED | suite commands; no hidden failure |
| E1 | remove `if:` from External | RED | suite conditions |
| RT1 | M1 delete step `In-FreeCAD suite` | RED | suite commands; suite conditions |
| RT1 | M9 External runs one file | RED | suite commands |
| RT2 | M4 `\|\| exit 0` | RED | suite commands; no hidden failure |
| RT2 | M13 `\|\| /bin/true` | RED | suite commands; no hidden failure |
| RT2 | M7 step `shell: bash {0}` + trailing `echo done` | RED | suite commands; no hidden failure |
| RT2 | M8 workflow `defaults.run.shell: bash {0}` + `set +e;` | RED | suite commands; no hidden failure |
| RT3 | M2 External `if: ${{ !cancelled() && false }}` | RED | suite conditions |
| RT3 | M3b job `if: github.event_name == 'push'` | RED | suite conditions |
| RT4 | M12 second `if:` key | RED | all 7 (duplicate-key loader) |
| RT5 | M10 `environment-file` input | RED | solve |
| own | External `if: ${{ always() }}` | RED | suite conditions |
| own | job `env: PYTEST_ADDOPTS: --co` | **GREEN** (`7 passed`) | none |
| own | step `env: PYTEST_ADDOPTS: --co` on External | **GREEN** | none |
| own | new step `echo PYTEST_ADDOPTS=--co >> "$GITHUB_ENV"` | **GREEN** | none |
| no change in meaning | comment text changed | green | none |
| no change in meaning | job `timeout-minutes` 60 → 90 | green | none |
| no change in meaning | `if:` key written before `name:` on External | green | none |
| no change in meaning | cron Monday → Tuesday | green | none |

E1 discrepancy: `build-10-8-e.md` (E4 section) says the 7 E1 mutants "stay red". That was an argument, not a run. I ran all 7 at `72488ba`: all are red. The claim holds, so there is no finding.

### 8.3 New finding

| ID | Severity | Finding |
| --- | --- | --- |
| V-F6 | medium (test gap; `canary.yml` itself is correct) | The allowlist checks the keys `continue-on-error`, `shell` and `defaults`, the suite `run` text and the `if:` text. It does not check `env:` at workflow, job or step level, and it does not check extra steps (`test_canary_workflow.py:132-145`). With `PYTEST_ADDOPTS: --co`, the External suite collects and runs no test. pytest exits 0 (`7 tests collected`, exit 0, checked locally), and actionlint accepts the file (exit 0). The step is green, and the test gives `7 passed`. This contradicts the module docstring at `test_canary_workflow.py:4-6`: "a change that runs nothing, narrows a suite or hides an exit code fails here". The effect class is the same as RT1/RT2, which the red team rated medium. Possible fix: allowlist the step keys (`name`, `id`, `if`, `uses`, `with`, `run`, `timeout-minutes`) and the job keys, and reject `env` unless it is on an allowlist. Leader decision: fix it, or narrow the docstring claim. |

## 9. Re-run at 78fd1a5

Commit: `78fd1a5b7d094979966281a3f6c083cf1c52f347` (fix round E5). It changes `deferred-work.md` only; `git diff be3e5a1 78fd1a5 -- .github/` is empty, so the job proof in section 3 still applies and was not run again. New detached copy `fcb-verify-10-8-e` at `78fd1a5`, `uv sync --extra dev`, removed after the run.

**Verdict for 78fd1a5: all requested checks PASS, and F1 is closed. The slice stays FAIL for one reason: V-F6 (medium, section 8.3) is still open.** `test_canary_workflow.py` did not change after `72488ba`. Ledger row V-F6 names the verifier as the owner of the fix. I have had no instruction to make it, so I made no change and no commit.

### 9.1 Gates

| Command | Result |
| --- | --- |
| `uv run ruff check .` | `All checks passed!` |
| `uv run pytest tests/external/test_canary_workflow.py tests/external/test_ci_workflow.py -q` | `10 passed` |

### 9.2 Mutations

Driver: `mutate78.py` in the scratchpad (same method as section 8.2). `git status --porcelain` was empty after the run.

| Group | Mutant | Result | Red tests |
| --- | --- | --- | --- |
| RT1 | M1 delete step `In-FreeCAD suite` | RED | suite commands; suite conditions |
| RT2 | M7 step `shell: bash {0}` + trailing `echo done` | RED | suite commands; no hidden failure |
| RT3 | M3b job `if: github.event_name == 'push'` | RED | suite conditions |
| E1 | add `push:` trigger | RED | triggers |
| E1 | `freecad=1.2` | RED | solve |
| E1 | remove `if:` from External | RED | suite conditions |
| own | External `if:` guards on `steps.setup.outcome` in place of `steps.install.outcome` | RED | suite conditions |
| F4 (earlier gap) | both suites `if: ${{ !cancelled() }}` (install-outcome guard dropped) | RED | suite conditions — F4 closed |
| V-F6 | job `env: PYTEST_ADDOPTS: --co` | GREEN (`7 passed`) | none — V-F6 still open |
| no change in meaning | comment text changed | green (`7 passed`) | none — no over-fit |

### 9.3 Defect F1: deferred-work.md text

Every entry of this slice (`source_spec` = `spec-10-8-e-canary-dev-freecad.md`) now has a `blocker:` line and an `unblock:` line: 11 of 11, at `deferred-work.md` lines 1989, 1995, 2001, 2007, 2013, 2019, 2025, 2031, 2037, 2043 and 2049 at `78fd1a5`. The flake entry exists at line 2049. It names `test_rpc_listener` (hello deadline, 10 of 10 on re-run) and `test_marshal_self_submit.py:48` (0.19992 s against 0.2 s), with blocker "wall-clock timing with no margin" and unblock "widen the bounds or make the clock injectable". F1 is closed. Ledger row V-L1 (flakes not recorded) is also closed by line 2049.

Two entries (1989 and 2013) still have an older `Unblock:` sentence in `evidence:` beside the new `unblock:` line. The two texts differ but do not conflict.

### 9.4 New finding

| ID | Severity | Finding |
| --- | --- | --- |
| V-F7 | low | The E5 commit adds 53 blank lines between entries of other Stories (`deferred-work.md:557` and lines 1484-1692, for example between the `spec-10-1-documents-and-queries.md` entries at 1480-1491). It adds only blank lines: no line is removed, and `git diff --ignore-blank-lines` shows only the 26 lines of this slice. No text changes meaning, but the change is outside the slice scope (CLAUDE.md section 3). Leader decision: keep it or revert those hunks. |

## 10. V-F6 test fix (verifier, on 78fd1a5)

Worktree `D:\Work\Personal\Sources\fcb-10-8-e`, branch `story/10-8-e-canary-dev-freecad`, base `78fd1a5`. The change is in `tests/external/test_canary_workflow.py` only (22 insertions, 16 deletions). It is **not committed**. The user's CLAUDE.md rule 1 requires the user's own approval for each commit, and an agent message is not that approval. The leader holds the decision-28 grant and can commit the change.

Change:
- Docstring (`:3-8`): it now claims only what the tests check: the triggers, solve inputs, install line, the two suite commands, suite conditions, the allowed keys at each level, and no `||`, `set +e` or `$GITHUB_ENV` in a `run`. It says that other changes to what a step does are not checked.
- `_WORKFLOW_KEYS = {"name", True, "jobs"}`, `_JOB_KEYS = {"runs-on", "timeout-minutes", "steps"}`, `_STEP_KEYS = {"name", "id", "uses", "with", "run", "if", "timeout-minutes"}`, `_MASKING_TEXT = ("||", "set +e", "GITHUB_ENV")`, with a comment that gives the reason (`PYTEST_ADDOPTS: --co`).
- `test_should_not_hide_a_failure_when_canary_yml_is_read`: the denylist `{"continue-on-error", "shell", "defaults"}` is replaced by the three allowlists, and the `run` check now reads `_MASKING_TEXT`.

Proof:

| Check | Result |
| --- | --- |
| `uv run --extra dev ruff check .` | `All checks passed!` |
| `ruff format` | applied (1 file); `--check` then clean |
| `pytest tests/external/test_canary_workflow.py tests/external/test_ci_workflow.py -q` | `10 passed` |
| V-F6 job `env: PYTEST_ADDOPTS: --co` | RED (no hidden failure) |
| V-F6 step `env: PYTEST_ADDOPTS: --co` on External | RED |
| V-F6 new step `echo PYTEST_ADDOPTS=--co >> "$GITHUB_ENV"` | RED |
| All earlier mutants (`mutate72.py`: E1 ×7, RT1-RT5 ×10, own `always()`; `mutate78.py`: own setup guard, F4) | all RED |
| No over-fit: comment text, job timeout 60 → 90, `if:` before `name:`, cron day | all green (`7 passed`) |

`git status` after the mutation runs shows only the test file modified; `canary.yml` is unchanged.

F1 text check at `78fd1a5`: done in section 9.3. 11 of 11 entries have `blocker:` and `unblock:` lines, and the flake entry is at `deferred-work.md:2049`.

V-F7 fix, also not committed: I applied in reverse only the E5 hunks that start before the slice (`git apply -R --unidiff-zero`; each kept hunk was checked to hold only blank lines). That removes 52 blank lines. The E5 diff had 53 blank lines; the 53rd is inside the slice and separates the new flake entry, so it stays. Correction to section 9.4: 52 blank lines were outside the slice, not 53. After the fix, `git diff 72488ba -- deferred-work.md` is one hunk (`@@ -1937,39 +1937,65 @@`), and `--ignore-blank-lines` still shows the 26 slice lines. No text changed.

Gates after both fixes: `ruff check .` → `All checks passed!`; `ruff format --check` on the test → `1 file already formatted`; the two workflow tests → `10 passed`. Tree: ` M deferred-work.md`, ` M tests/external/test_canary_workflow.py` on `78fd1a5`.

## 11. Cleanup

Worktree `fcb-verify-10-8-e` removed after each run (`git worktree list` has no match). Containers `fcb-canary-verify-10-8-e` (2 runs) and `fcb-actionlint-verify-10-8-e` ran with `--rm`; `docker ps -a` shows neither. No commit made. Scripts and logs: `C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\c042ee17-1e94-43bb-bf76-94b15d483a03\scratchpad\canary-job.out` and `C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\c042ee17-1e94-43bb-bf76-94b15d483a03\scratchpad\rpc-rerun.out`.
