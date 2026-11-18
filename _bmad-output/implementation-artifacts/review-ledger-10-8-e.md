# Story 10-8-e: findings ledger

Quality bar: `quality-bar-10-8-e.md`.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-H1 | Q4 | high | r1 lenses | fixed-proven | External step `if: !cancelled() && steps.install.outcome == 'success'`; local run shows External suite after In-FreeCAD failure (`1809 passed`) |
| R2-M* | Q7, Q8 | medium | r1-r2 lenses | fixed-proven | clause count 9, proposal rows, build-under-test step, setup guard; spec `## Review Triage Log` |
| RT1 | Q4 | medium | redteam-10-8-e | fixed-proven | test passes with In-FreeCAD step deleted or External narrowed; fix E4 |
| RT2 | Q5 | medium | redteam-10-8-e | fixed-proven | test passes `\|\| exit 0`, `shell: bash {0}`, `set +e`; fix E4 |
| RT3 | Q4, Q6 | medium | redteam-10-8-e | fixed-proven | `!cancelled()` substring check; job-level `if:` unchecked; fix E4 |
| RT4 | Q6 | low | redteam-10-8-e | fixed-proven | duplicate `if:` key passes; fix E4 |
| RT5 | Q1 | low | redteam-10-8-e | fixed-proven | `environment-file` channel input unchecked; fix E4 |
| V-F6 | Q4, Q5 | medium | verifier-10-8-e (re-run at 72488ba) | fixed-proven | `env: PYTEST_ADDOPTS: --co` passes the test and runs 0 tests; verifier fixes (step/job key allowlist, `$GITHUB_ENV` write rejected) |
| RT1-RT5 | Q1, Q4-Q6 | medium/low | redteam-10-8-e | fixed-proven | verifier-10-8-e re-run at 72488ba: all red-team mutants RED, E1 x7 RED, no over-fit (7 green) |
| V-F1 | outside the bar | low | verifier-10-8-e | fixed-proven | verifier re-run at 78fd1a5: 11 entries with blocker/unblock (`deferred-work.md:1989-2049`) |
| V-L1 | outside the bar | low | verifier-10-8-e | fixed-proven | flake entry at `deferred-work.md:2049` |
| V-F7 | outside the bar | low | verifier-10-8-e | rejected | blank-only lines, no content change; a revert adds risk to a shared ledger for no reader gain (decision 42) |
| L1 | Q6 | medium | leader triage | fixed-proven | `test_canary_workflow.py` added at `be3e5a1`; red team showed false passes (RT1-RT3) |
| L2 | Q7 | low | builder note | fixed-proven | `project-context.md:21` wording (E2) |
| L3 | outside the bar | low | builder deferral | fixed-proven | `ARCHITECTURE-SPINE.md:452` names `ci.yml` (E3) |
| D1 | outside the bar | low | builder | deferred | 15 dev-line failures, 7 groups; AD-11 allowed-to-fail (decision 41) |
| D2 | outside the bar | low | builder | deferred | conda-forge lag; two-process step; known-failure baseline (decision 41) |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | pre-b527d92 | Blind ad2184936896516b1, Edge af54240701619b998, Gap aa3765257a2dff9b9 | 1 → 0 | 1 high | 1 high, mediums | 0 |
| 2 | pre-b527d92 | Blind adf1bba2c02831e55, Edge a2cff3d8bb61ff425, Gap a9b49cc4f584d4671 | 0 → 0 | mediums | mediums | 0 |
| 3 | b527d92 | Blind aab8bcc1503d87dcf, Edge a67501a4588bd52c2, Gap a17ea58fa33ef4736 | 0 → 0 | comment/doc patches | 0 high/medium | 0 |
| E4 | 72488ba | none (test file only); verifier-10-8-e re-run pending | test medium 3 (RT1-RT3) → pending proof | builder: 12 red-team mutants red | — | — |
| E | be3e5a1 | none (test + doc text; verifier-10-8-e + redteam-10-8-e) | 1 → pending proof (L1) | builder: 7 mutations red on `test_canary_workflow.py` | — | — |
| E5 | 78fd1a5 | none (text); verifier re-run PASS on F1 | 0 → 0 | 2 (V-F1, V-L1) | 1 medium (V-F6), 1 low (V-F7) | 0 |
| V | 2038990 | verifier-10-8-e test fix + proof | 1 → 0 | V-F6: 3 variants red, 22 earlier mutants red, 4 no-over-fit green | 0 | 0 |

Closed: merged into `fix/uat-gate-1-failures` at `97a35d1` (2026-11-18); `deferred-work.md` merge conflict with 10-8-f resolved by keeping both blocks. Post-merge: canary + ci + runner tests 196 passed, ruff clean, check_imports OK. GitHub canary dispatch: NOT RUN (needs a push).
