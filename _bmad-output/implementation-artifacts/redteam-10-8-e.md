# Story 10-8-e: red team report

Target: diff `9aee2bf...be3e5a1`, branch `story/10-8-e-canary-dev-freecad`. Work copy: detached worktree `fcb-redteam-10-8-e` at `be3e5a1` (removed after the run). Method: `bmad-code-review` lenses (adversarial, edge cases, verification gap), run by one red-team agent. Quality bar: `quality-bar-10-8-e.md`. Ledger rows R1-H1, R2-M*, L1-L3, D1, D2 are not reported again.

## Harness

- Mutation driver: loads `tests/external/test_canary_workflow.py`, points its module global `CANARY_WORKFLOW` at a mutated copy of `canary.yml` in a temp directory, and calls all 5 test functions. The tracked file is not changed.
- Command: `uv run --extra dev python <scratchpad>/rt/mutate.py .` in the worktree. (`pyyaml` is in the optional extra `dev`, `pyproject.toml:22`; a plain `uv run` cannot import the test.)
- GitHub parser check: `docker run --rm rhysd/actionlint:latest -no-color -shellcheck= <mutant>`.
- Shell semantics: throwaway container `fcb-canary-redteam-10-8-e` (`mambaorg/micromamba:2.3.3`, `--rm`). GitHub's default `run` shell on Linux is `bash --noprofile --norc -eo pipefail {0}`; `shell: bash {0}` drops `-e` and `pipefail`.
- Action source: `mamba-org/setup-micromamba` tag `v2`, `src/options.ts`, `src/main.ts`, `src/util.ts` (read with `gh api`).

Mutation results (5 tests each; actionlint exit code on the same file):

| Mutant | Change to `canary.yml` | Test result | actionlint |
| --- | --- | --- | --- |
| M0 | none (baseline) | ALL 5 PASS | 0 |
| M1 | delete step `In-FreeCAD suite` (`:46-49`) | ALL 5 PASS | 0 |
| M2 | External `if: ${{ !cancelled() && false }}` | ALL 5 PASS | 0 |
| M3 | job `if: false` | ALL 5 PASS | 1 (`constant expression "false" in condition`) |
| M3b | job `if: github.event_name == 'push'` | ALL 5 PASS | 0 |
| M4 | External `run: ... pytest tests/external \|\| exit 0` | ALL 5 PASS | 0 |
| M7 | External `shell: bash {0}` + `run: \|` with a trailing `echo done` | ALL 5 PASS | 0 |
| M8 | workflow `defaults: run: shell: bash {0}` + `set +e` in In-FreeCAD `run` | ALL 5 PASS | 0 |
| M9 | External `run: ... pytest tests/external/test_canary_workflow.py` | ALL 5 PASS | 0 |
| M10 | setup `with:` adds `environment-file: ci/canary-env.yml` | ALL 5 PASS | 0 |
| M12 | second `if:` key on External suite | ALL 5 PASS | 1 (`key "if" is duplicated`) |
| M13 | External `run: ... \|\| /bin/true` | ALL 5 PASS | 0 |

Gates on `be3e5a1`: `uv run --extra dev ruff check .` → `All checks passed!`; `uv run python scripts/check_imports.py` → `check_imports OK`; `uv run --extra dev pytest tests/external/test_canary_workflow.py tests/external/test_ci_workflow.py -q` → `8 passed`; `ruff format --check` on the new test → `1 file already formatted`.

## Reproduced

### RT1 — medium — Q4 — test passes a canary that runs one suite or a narrowed suite

- Where: `tests/external/test_canary_workflow.py:96-104` checks only the `if:` of the step named `External suite`. No test reads the `run:` of either suite, or checks that the step `In-FreeCAD suite` exists.
- Reproduction: M1 (In-FreeCAD step deleted) and M9 (External suite runs one file) → `ALL 5 PASS`; actionlint exit 0 on both, so GitHub accepts both files.
- Effect: Q4 ("both suites run on the dev build") can break with a green unit test. The ledger row L1 (decision 41, E1) is closed on this test, but the test does not pin Q4.

### RT2 — medium — Q5 — test passes exit-code masks other than the literal `|| true`

- Where: `tests/external/test_canary_workflow.py:19` (`_OR_TRUE = re.compile(r"\|\|\s*true\b")`) and `:78-93`. The module docstring (`:5`) claims the canary must "never hide a failing exit code"; the test checks only `continue-on-error` and `|| true`.
- Reproduction: M4 (`|| exit 0`), M13 (`|| /bin/true`), M7 (step `shell: bash {0}` with a trailing command), M8 (workflow `defaults.run.shell: bash {0}` + `set +e`) → `ALL 5 PASS`; actionlint exit 0 on all four.
- Shell proof in `fcb-canary-redteam-10-8-e` (a step body `false` then `echo done`, where `false` stands for a failing suite):

```
== GitHub default shell for run: bash --noprofile --norc -eo pipefail {0}
default-shell step exit=1
== shell: bash {0}
done
bash-{0} step exit=0
== '|| exit 0' under default shell
exit=0
```

- Effect: a canary with a failing suite shows green. Q5 lists only the two literal forms, so the row text holds; the test's stated contract does not.

### RT3 — medium — Q4, Q6 — `if:` checks are a substring test and miss the job level

- Where: `tests/external/test_canary_workflow.py:104` (`assert "!cancelled()" in condition`) and `:43-51` (triggers read, job `if:` not read).
- Reproduction: M2 (External `if: ${{ !cancelled() && false }}`) and M3b (job `if: github.event_name == 'push'`) → `ALL 5 PASS`; actionlint exit 0 on both. With M3b the job never runs on `schedule` or `workflow_dispatch`, and GitHub shows the skipped job, not a red run. With M2 the External suite never runs.
- Effect: the canary can run nothing, or skip the External suite, while the triggers test and the `!cancelled()` test pass.

### RT4 — low — Q6 — test passes a file GitHub rejects; no CI step runs actionlint

- Where: `tests/external/test_canary_workflow.py:23-24` (`yaml.safe_load` keeps the last of two duplicate keys); `grep -n actionlint .github/workflows/*.yml` → no line.
- Reproduction: M12 → `ALL 5 PASS`; actionlint: `key "if" is duplicated in element of "steps" section. previously defined at line:51,col:9 [syntax-check]`, exit 1.
- Effect: low, because GitHub shows a workflow-file error, not a green run. The Q6 "actionlint" check exists only as a manual step in the build report.

### RT5 — low — Q1 — channel added through the `environment-file` input passes the solve test

- Where: `tests/external/test_canary_workflow.py:54-64` reads only `create-args` and `condarc`.
- Reproduction: M10 → `ALL 5 PASS`; actionlint exit 0. The action adds the file to the create command: `src/main.ts` `if (options.environmentFile) { commandStr += \` -f ${options.environmentFile}\` }`, so channels in that file join the solve. The effect on a real solve was not run.

## Not reproduced

- `MAMBA_CHANNELS` in job `env:`: in micromamba 2.3.3, `micromamba config list channels --rc-file /tmp/.condarc` shows only `conda-forge` with and without the variable. No effect seen.
- `; true` after a suite: under GitHub's default `-e` shell the step still exits 1 (`false; true` → `exit=1`). Not a mask.
- Unquoted `|| :` is invalid YAML (all 5 tests raise `ScannerError`); a quoted form is the same class as RT2 and was not run.
- `create-args` splitting: the action splits on one space (`options.ts` `.split(' ')`) and runs micromamba with an argument array (`util.ts` `exec(cmd[0], cmd.slice(1))`); the test uses Python `str.split()` (any whitespace). They differ only for tabs or non-breaking spaces, and there the action passes a bad spec and the solve fails red. The `canary.yml:26-27` comment ("splits on spaces with no shell and no quote handling") matches the source.
- Local harness versus the action path: the proof used `micromamba create -c conda-forge` with micromamba 2.3.3; the action uses `--rc-file` with the `condarc` input, exports `CONDARC`, and downloads micromamba `latest`. Needs a GitHub run (Q10, already NOT RUN).
- Job `timeout-minutes: 60` against an uncached 792 MB solve on `ubuntu-latest`: not measured on GitHub.
- `schedule` runs only from the default branch: the new `canary.yml` takes effect only after merge to `main`. Q10 already reports the GitHub run as NOT RUN.
- YAML anchors and merge keys: PyYAML resolves them as GitHub does; a `continue-on-error` brought in through `<<: *base` is still seen by the test. No divergence found.
- Doc clauses 1-11: each replaces "1.2-dev" or names label `main` or the file `canary.yml`; no clause changes a rule (allowed-to-fail, conda-forge if published, else weekly AppImage, schedule and dispatch only). Clause 11 is a detail-tier edit inside `ARCHITECTURE-SPINE.md:452`; the file `canary.yml` exists, so the code supports it. Proposal §5 says "those three planning documents" while four documents changed (wording only).

## Verdict

FAIL. Counts: high 0, medium 3 (RT1, RT2, RT3), low 2 (RT4, RT5). All three mediums are false passes of `tests/external/test_canary_workflow.py`: the workflow on `be3e5a1` is correct, but the test that closes ledger row L1 does not pin Q4 or the "never hide a failing exit code" contract it states.
