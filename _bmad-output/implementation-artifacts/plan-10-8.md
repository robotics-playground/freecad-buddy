# Plan: Story 10-8 — UAT Gate 1 run in the container, with the canary fix

Planner: `plan-10-8` (bmad-build Plan phase only). Base commit `6dd8bce8b1a99fc51e054f2af71b0e7f33134038` on `fix/uat-gate-1-failures`. Date 2026-11-18.
No product code, test case or container state was changed. One throwaway container (`mambaorg/micromamba:2.3.3`, `--rm`) ran a dry-run conda solve; `fcb-desktop` got one read-only `ls`.

## 1. Summary

- **Slicing:** three new slices plus a container revision of `spec-10-8-d`. 10-8-e canary fix (new spec with `bmad-spec` first). 10-8-f known test-case defects from run 2026-10-24-01 (before the gate run). 10-8-d revised for the container, G3 GUI replay port inside it. Two frozen-intent lines of `spec-10-8-d` need the user (Q1).
- **Canary cause:** the spec `freecad=1.2` can never solve. No FreeCAD 1.2 exists: after 1.1, FreeCAD numbers releases `26.3` (RC2 on 2026-10-18) and its main branch is `27.1-dev`. conda-forge publishes the dev builds on its `main` label as calendar versions (`2026.09.16`); the `freecad_dev` label is empty. The job failed at the same step on every run since 2026-07-27; `continue-on-error` hid it until `23eb932`.
- **AC1 "CI green":** `ci.yml` is green on `main` (`8e8c187`, run `41397825279`) and on the integration branch (`031d8e8`, run `44231368719`). The canary is not blocking by AD-11. The canary fix is in 10-8 by user choice (decision 19), not by AC1.
- **Gate run:** 255 Gate 1 scenarios (174 Critical, 67 High, 14 Medium) plus 5 TC-99. 72 run through the runner in the container, 183 by Sonnet phase agents. 12 agent phases plus 2 runner-review phases plus G3. Rough cost: about 15 agent sessions, about 20 to 25 h of sequential agent time, 3 working days wall time, plus one likely fix loop.
- **Open user questions:** 8 (section 12). No blocker for planning. Push and any `main` change need the user.

## 2. Evidence read

| Source | What it settles |
| --- | --- |
| `epics.md:1446-1452` | Story 10.8 AC1 text (quoted in section 4) |
| `epics.md:1218-1220` | 10.8 is last; epic acceptance is 10.8 |
| `epic-10-context.md` | Valid by the bmad-build rule: mtime 2026-10-23 09:36, newest planning artifact 2026-10-13 (git: context 2026-10-23, planning 2026-10-22). It predates the container decision (CLAUDE.md section 9), so its runner line "launches FreeCAD non-elevated with a dedicated `-u` profile" is Windows-era text. Not stale by the rule, because its sources did not change |
| `spec-10-8-d-uat-gate-1-run.md:16-43` | Frozen intent; D1 (G3 both forms), D2 (run reports what it finds) |
| `epic-10-decisions.md` rows 5, 8, 17, 19, 20, 23 | New run in the container; user.cfg baseline `b89a9771…85a0`; test cases rewritten (10-10); canary in 10-8; preset and branch |
| `tests/uat/test-plan.md:461-560` | Gate 1, §9 review rule, seed rule (`:525-530`), Gate 2. Gate 1 and Gate 2 sections are byte-equal to `3025e7c` |
| `uat-run-practices.md` | Roles, Sonnet phase agents (`:50`), phase size 12-22 (`:90`), re-run rule (`:95-98`), grading (`:177-200`) |
| `tests/uat/runner/README.md`, `capture.py:42-50` | Container runner command, exit codes, review set; runner parses `cua-driver` JSON and treats `isError` and `status: refused` as errors |
| `freecad-gui-e2e-harness.md:14-34` | Container steps; "The container has its own FreeCAD profile ... recreate the container (`up -d --force-recreate`)" |
| `run/2026-10-23-02/report.md`, `run/2026-10-24-01/lead-notes/`, `lead-log-2026-10-24-uat-fixes.md` | Last gate run (RED, Critical 126/174), partial re-run (R0-R3 only), open owner questions, test-case defects not yet applied |
| `deferred-work.md:1702-1937` | Items that wait on 10-8 (section 10) |
| `canary.yml`, `ci.yml:85-145`, `gh run` logs | Canary cause (section 5) |
| conda-forge `api.anaconda.org/package/conda-forge/freecad`, `conda-forge/freecad-feedstock` `recipe/recipe.yaml`, `FreeCAD/FreeCAD` `version.json` at tags | Package versions, labels and FreeCAD numbering |
| `ARCHITECTURE-SPINE.md:120-127`, `:397`, `:452`; `project-structure.md:127`, `:235`, `:319-321` | AD-11 and CI layout: canary is "1.2-dev weekly", "allowed-to-fail", "conda-forge if published, else weekly AppImage" |

## 3. Slicing

| Slice | Goal | Route | Status |
| --- | --- | --- | --- |
| 10-8-a, -b, -c | Probe docs keep active view; encode 30 runner scenarios; TC-08-07 premise | done | `done` |
| **10-8-e** (new) | Canary installs a current FreeCAD dev build and runs both suites | `bmad-spec`, then `bmad-build` (decision 3 pattern: requirement not in the plan) | to write |
| **10-8-f** (new) | Apply the test-case corrections that run 2026-10-24-01 found and never applied | `bmad-build` (same kind as 10-8-c) | to write; recommended before the gate run (Q5) |
| **10-8-d** (revise) | Gate run in the `fcb-desktop` container; G3 GUI replay port is a setup task inside it | revise Code Map, Tasks, Verification, baseline; frozen lines need the user (Q1) | `in-progress` |

Order: 10-8-e and 10-8-f are independent and can run in parallel (no shared file; 10-8-e is non-GUI). 10-8-d starts after 10-8-f merges, so the gate runs on the corrected test cases. 10-8-e need not finish before 10-8-d; it must finish before Story 10.8 closes (decision 19).

### 3.1 Slice 10-8-e — canary fix

Files:
- `.github/workflows/canary.yml:15-28` — replace `freecad=1.2` with `freecad>=2026` and the channel list with `conda-forge` only; replace the install line with the `ci.yml:106` dependency line (`"mcp>=1.28,<2" "trimesh==4.*" "lib3mf==2.*" pytest jsonschema pyyaml`). Without that line the External suite fails on `import mcp` even after the solve. Update the comment lines 3 and 15-17.
- Only with the user's agreement (Q2): `ARCHITECTURE-SPINE.md:126` and `:397`, `:452`; `project-structure.md:127`, `:235`, `:321`, which name "1.2-dev". The decision (an allowed-to-fail canary on the next dev line) stays; only the version name is wrong.

Tasks:
1. `bmad-spec`: write `spec-10-8-e-canary-dev-freecad.md` with the cause evidence of section 5; send to the leader.
2. Pre-push proof (no push): dry-run solve in a throwaway container, old spec and new spec (section 5 shows the result).
3. Push the branch (user, Q4), then `gh workflow run canary.yml --ref <branch>`. `workflow_dispatch` is present (`canary.yml:8`), and a dispatch on a ref runs the workflow file of that ref.
4. Read the dispatch log; grade per Q3.

### 3.2 Slice 10-8-f — known test-case defects

Each item was found and graded in run 2026-10-24-01 and is still in the text at `6dd8bce`. Each Then rewrite must cite the design line that proves the product behaviour (uat-run-practices §8, `:206-207`).

| Item | Priority | Where | Defect (source) |
| --- | --- | --- | --- |
| TC-02-05 | Critical | `TC-02-document-ingestion-and-handles.md:232`, `:237` | Then reads `structured_content.shown` / `.matches` of `query_tree_summary`, a text-only tool (`mcp-tools-design.md`: no `outputSchema`) — lead-grades R1 |
| TC-02-14 | Medium | TC-02 from `:561` | same reader defect — lead log R1 |
| TC-11-18 | Critical | `TC-11-security-posture-and-artifact-hygiene.md:840` ff., visual Then "identical to `tc-11-18-before.png`" | When creates `tc11-18`, its view comes to the front, no step activates the golden again — lead log R2-F1 |
| TC-12-05 | Critical | `TC-12-gui-workflows.md:330`, "the tree text equals the pre-toggle one" | header lines change by design (`mcp-tools-design.md:282`); compare object lines only — lead log R3-F1 |
| TC-08-04 | High | `tests/uat/scenarios/tc-08-04.json:487` `"\bFillet\b"` | JSON `\b` is a backspace; runner FAIL on every run — R0-F1 |
| TC-06-01 | Critical (Cleanup only) | `TC-06-render-and-gui-visual-fidelity.md:131` `p.RemoveInt` | FreeCAD has `RemInt` — R1 |
| TC-08 | none | `TC-08-preview-confirm-and-undo.md:680` "restore with `{ Visibility: true }`" | restore the value read before — R2-F2 |
| TC-09 | none | `TC-09-error-contract-and-fault-injection.md:46` "no `freecad_buddy.hosts.main` process" | the GUI proxy is such a process — R2-F3 |

Verification: `uv run pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q`; all 72 files load (runner validate step); each changed scenario runs once in the container (not committed; the gate run is the record).

### 3.3 Slice 10-8-d — what changes in the spec

Frozen block (`spec-10-8-d:16-43`) — two lines do not fit the container. Each change needs the user (Q1):
- `:34` "FreeCAD is started non-elevated with a temporary `-u` profile (Story 10.7b AC7)". The runner still does this (`runner/README.md:52-56`). Agent-driven launches use `fcb-freecad start` (`tests/close-loop/docker/bin/fcb-freecad:28`, no `-u`), which uses the container user's profile. The purpose, "the developer's `user.cfg` is unchanged", holds by construction (harness `:33-34`). Proposed wording: "Agent-driven FreeCAD starts with `fcb-freecad start` on a container recreated at run start (clean profile); the runner uses a temporary `-u`/`-s` profile; record the developer `user.cfg` SHA-256 before and after."
- `:26` D1 names `tests/uat/run/2026-10-03-04/evidence/g3_gui_replay.py`. That script cannot run in the container as written: `REPO = Path(r"D:\Work\...")` (`:27`), MCP at `http://127.0.0.1:8765/mcp` (`:124`; the container is `:18765` from the host), Windows `gui.py` helper (`:44-49`), and it writes into its own folder `2026-10-03-04/evidence/` (`:39-41`), which breaks "never edit an earlier run folder" (`uat-run-practices.md:66-68`). Proposed wording: "the same replay logic, copied into the new run folder in container form". The "unchanged" criterion stays word for word.

Non-frozen sections (leader may approve):
- `baseline_commit`: the commit after 10-8-f merges.
- Code Map: container commands (section 6), `$FCB_PYTHON` and `$FCB_CUA`, `:18765`, watchdog with `--since <ISO with offset>`, image rebuild, G3 container routes. Remove `uv run python tests/uat/runner/run.py` (host form, `:47`) and the `_automation/uat/launch_env.sh` line (`:51`).
- Tasks: preflight in container form; G3 GUI port task; R0 review split into two agents; 12 agent phases (section 6).
- Verification: add the image id and the `dist/addon` wheel SHA-256 to the run record.

## 4. AC1 boundary: is the container a detail?

Boundary line, `epics.md:1450-1452`:

> **When** the full suite TC-01..TC-14, TC-99 and the G3 live replay run on FreeCAD 1.1.4 through the Story 10.7b runner, with agent review per the updated §9 and the desktop free (or the GUI lane in an isolated Windows session)
> **Then** Gate 1 is green (Critical 100 %, High ≥ 95 %), Gate 2 matches its documented deviations, and the G3 replay is unchanged; the report is committed under `tests/uat/run/`

Test, part by part:
- "on FreeCAD 1.1.4": the container runs FreeCAD 1.1.4 (decision 4; `tests/close-loop/README.md:6`). No OS is named.
- "through the Story 10.7b runner": the same runner, ported to the container in 10-9 (`runner/README.md:3-5`).
- "the desktop free (or the GUI lane in an isolated Windows session)": a condition on isolation, with one option given in brackets. The container desktop is used by nothing but the run, so "the desktop free" holds literally. The bracket is an alternative, not a requirement.

Verdict: running in the container is inside the AC1 boundary (detail tier). Support: CLAUDE.md section 9, "**UAT environment: the `fcb-desktop` container, never the host.** Every UAT gate, re-run ... drives FreeCAD 1.1.4 inside the Linux container", and decision 5. Limit to state in the report: a Linux run does not measure Windows GUI behaviour; AC1 does not ask for it. The only approval-tier items are the two frozen lines of `spec-10-8-d` (section 3.3, Q1), because the frozen block is human-owned.

## 5. Canary: cause, fix, proof

Cause, with evidence:
- Run `43894158176` log: `└─ freecad =1.2 * does not exist (perhaps a typo or a missing channel).`, then `critical libmamba Could not solve for environment specs`. The `ENOENT ... micromamba-shell` line and the submodule warning `No url found for submodule path 'docs/references/FreeCAD'` come after it and are post-step noise.
- The same `does not exist` line is in every canary log still kept: 13 runs, 2026-08-24 to 2026-11-16. Logs of the 4 runs from 2026-07-27 to 2026-08-17 expired (HTTP 410), but run `32004044904` shows `X Run mamba-org/setup-micromamba@v2` and the same micromamba exit 1. The canary never installed FreeCAD and never ran a test. Runs before 2026-10-26 show "success" only because the job had `continue-on-error: true`; commit `23eb932` removed it ("Canary drops continue-on-error so a 1.2-dev failure shows red"), and it reached `main` with the 0.1.x releases.
- conda-forge `freecad` labels: `broken, cf201901, cf202003, freecad_rc, main`. The `freecad_dev` label repodata is empty (`"packages":{}`). Versions on `main`: `1.1.0`, `1.1.3`, `2026.09.16` (uploaded 2026-09-23, OCCT 8.0.1, builds for Python 3.11-3.14). No `1.1.4`, no `1.2*`.
- Feedstock `recipe/recipe.yaml` on `main`: `version: "2026.09.16"`, source `releases/download/weekly-${{ version }}/freecad_source_weekly-${{ version }}.tar.gz`. The feedstock `development` branch has had no change since 2024-11-06.
- FreeCAD `version.json`: tag `weekly-2026.09.16` is `26.3.0 dev`; tag `26.3rc2` (2026-10-18) is `26.3.0 RC2`; tag `weekly-2026.11.18` is `27.1.0 dev`. "1.2" was never released and will not be.

Reproduced locally (throwaway container, `micromamba` 2.3.3):
- `-c conda-forge/label/freecad_dev -c conda-forge "freecad=1.2"` → `freecad =1.2 * does not exist`, `critical libmamba Could not solve`.
- `-c conda-forge "freecad>=2026"` → `+ freecad 2026.09.16 py314h1b0b3cc_0`, `+ occt 8.0.1`, `+ python 3.14.10`, `+ qt6-main 6.11.3`, total download 792 MB.

Smallest fix: section 3.1 (two values and one install line in one file). Options and trade-offs are Q2.

Must it land on `main`? GitHub runs a `schedule` trigger only from the default branch, so the weekly canary stays red until the fix is on `main`. For AC1 it need not: AD-11 (`ARCHITECTURE-SPINE.md:126`) "1.2-dev weekly is an allowed-to-fail canary", and `project-structure.md:235` "Blocking: no (allowed-to-fail)". AC1 "CI green" is met by the blocking `ci.yml` jobs, which are green on `main` (`8e8c187`: arch-checks, render, headless (1.1.3, 3.11), g0-verdict all success) and on `031d8e8`. No `src/` or `.github/` file changed between `031d8e8` and `6dd8bce`, but the unpushed commits add tests that CI has not run yet. Q4 covers push and `main`.

Proof that can fail: the dispatch log must show (1) the solve line with `+ freecad 2026.*`, (2) the In-FreeCAD suite step with its `Ran N tests` line, (3) the External suite step with its pytest summary line. A run without step 2 or 3 does not prove the fix, even when the job is green. Expected result risk: OCCT 8 and Python 3.14 can make the suites fail (Q3).

## 6. Run plan for the Gate 1 run (revised 10-8-d)

### 6.1 Scope and counts (measured at `6dd8bce`)

| TC | Scenarios | Critical / High / Medium | Runner files | Agent-driven |
| --- | --- | --- | --- | --- |
| TC-01 | 15 | 8 / 6 / 1 | 0 | 15 (9 use H1) |
| TC-02 | 18 | 11 / 5 / 2 | 10 | 8 |
| TC-03 | 21 | 14 / 7 / 0 | 15 | 6 |
| TC-04 | 24 | 18 / 5 / 1 | 10 | 14 |
| TC-05 | 18 | 15 / 3 / 0 | 4 | 14 |
| TC-06 | 12 | 7 / 4 / 1 | 4 | 8 |
| TC-07 | 21 | 14 / 4 / 3 | 3 | 18 |
| TC-08 | 21 | 16 / 4 / 1 | 11 | 10 |
| TC-09 | 23 | 15 / 6 / 2 | 5 | 18 |
| TC-10 | 14 | 8 / 6 / 0 | 0 | 14 |
| TC-11 | 19 | 16 / 3 / 0 | 2 | 17 |
| TC-12 | 15 | 9 / 3 / 3 | 1 | 14 |
| TC-13 | 18 | 13 / 5 / 0 | 2 | 16 |
| TC-14 | 16 | 10 / 6 / 0 | 5 | 11 |
| **Gate 1** | **255** | **174 / 67 / 14** | **72** | **183** |
| TC-99 (Gate 2) | 5 | — | 0 | 5 |

Counts equal `spec-10-8-d:49`. `NOT APPLICABLE` scenarios after 10-10: 0. Runner files with `agent_check`: 67 of 72 (so almost all go `ESCALATE` and into the review set). Files with no `pixel` block: 26. Launch groups: default 56, `FREECAD_BUDDY_AUTO_APPROVE=0` 15, `FREECAD_BUDDY_SCRIPT_EXEC=0` 1.
TC-15 (7) and TC-16 (7) are outside AC1 and outside Gate 1 (`test-plan.md:461` "TC-01 .. TC-14"); not run. `test-plan.md:433` lists TC-16 in the index as Critical and TC-15 is not listed: a doc inconsistency for `deferred-work.md`, not a gate item.

### 6.2 Run folder and records

- Run folder: `tests/uat/run/<run date>-<NN>/`, first free `NN` on the run date (no `2026-11-18-NN` gate folder exists yet). Never reuse.
- Layout: `RUN-CONTEXT.md`, `report.md` (2026-10-03-04 layout, `spec-10-8-d:53`), `bugs.md`, `runner/` (`results.json`, `summary.md`, `captures/`, `audit-group-<n>.jsonl`), `evidence/` (`tc-xx-yy-<what>.<ext>`, `launch-log.tsv`, `user-cfg-sha256.txt`, `image-id.txt`, `e2e_report.json`, `edge_report.json`, `g3-headless/`, `g3-gui/`), `lead-notes/` (`RULES.md`, phase rows `rN.txt`, `lead-grades.txt`).
- Lead log: `_bmad-output/implementation-artifacts/lead-log-<date>-uat-gate-1-container.md`.
- Developer `user.cfg` (decision 8): `%APPDATA%\FreeCAD\v1-1\user.cfg` SHA-256 `b89a97711941619bb0ba74ae04fb888025e82f49ff48174fbebb42aed28d85a0` at run start, at each phase end, after every host FreeCADCmd call, at run end. Nothing in the container can write it; the only host writer is the in-FreeCAD suite, which runs only with `-u <tmp>\user.cfg -s <tmp>\system.cfg`.

### 6.3 Phases

One FreeCAD, one desktop, one phase agent at a time (`uat-run-practices.md:48-49`). Phase agents use `model: "sonnet"`. The lead keeps grading and re-reads every FAIL capture, every capture a visual PASS rests on alone, and one sample per test case (`:53-54`).

| Phase | Who | Scope | Count |
| --- | --- | --- | --- |
| S0 setup | lead | build, image, preflight, H1 proof, sweeps, user.cfg hash, `RUN-CONTEXT.md` | — |
| R0 runner | lead | `run.py` on all 72 files, drawn seed | 72 |
| R0a review | agent | §9 review set and every `ESCALATE` of TC-02..TC-04 runner scenarios, incl. `agent_check` re-runs to the named Given | 35 |
| R0b review | agent | same for TC-05..TC-14 runner scenarios | 37 |
| P1 | agent | TC-01 | 15 |
| P2 | agent | TC-02, TC-03 | 14 |
| P3 | agent | TC-04 | 14 |
| P4 | agent | TC-05, TC-06 | 22 |
| P5 | agent | TC-07 | 18 |
| P6 | agent | TC-08 | 10 |
| P7 | agent | TC-09 | 18 |
| P8 | agent | TC-10 | 14 |
| P9 | agent | TC-11 | 17 |
| P10 | agent | TC-12 | 14 |
| P11 | agent | TC-13 | 16 |
| P12 | agent | TC-14, TC-99 | 11 + 5 |
| G3 | lead runs both scripts; one agent reads the 24 GUI captures | D1 both forms | 14 cases |
| End | lead | `report.md`, `bugs.md`, gate counts from rows, deferred-work, end checklist (`uat-run-practices.md:231-241`) | — |

Watchdog between test cases and before every exit:
`docker exec -u cua fcb-desktop fcb-py /repo/scripts/automation/uat_watchdog.py --pid <pid> --window <wid> --since "$(date +%Y-%m-%dT%H:%M:%S%z)"` (offset needed: container clock zone differs, `tests/uat/README.md:114-116`).

### 6.4 Commands (container forms)

S0 setup, in order:
```bash
export MSYS_NO_PATHCONV=1
git status --short                          # only the run folder may be new
uv run python scripts/build_addon.py --release
docker compose -f tests/close-loop/docker/compose.yaml up -d --build --force-recreate   # clean container profile
docker image inspect fcb-desktop:local --format '{{.Id}}' > "$RUN_DIR/evidence/image-id.txt"
docker exec -u cua fcb-desktop fcb-py -c "import FreeCAD, mcp; print('H1 ok', '.'.join(FreeCAD.Version()[:3]))"   # H1 ok 1.1.4
uv run python scripts/automation/run_mcp_e2e.py        # exit 0, 29/29 at 10-9
uv run python scripts/automation/run_mcp_edge_cases.py # exit 0, 14/14 at 10-9
docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/probe/run_faults.py   # detected 5/5, false alarms 0/2
uv run python tests/uat/runner/pixel_faults.py
sha256sum "$APPDATA/FreeCAD/v1-1/user.cfg"
```
R0 (container FreeCAD stopped first; the runner starts its own):
```bash
docker exec -u cua fcb-desktop fcb-freecad stop
docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/runner/run.py /repo/tests/uat/scenarios --out /repo/tests/uat/run/<run>/runner
```
No `--seed` (`test-plan.md:526-528`). Record `run.sample_seed` and `sample_seed_source: drawn`, and every runner run made for the gate.

Agent phases: `docker exec -u cua fcb-desktop fcb-freecad start`, wait for a number in `freecad_pid` at `http://127.0.0.1:18765/healthz`; MCP server `freecad-buddy-docker`, GUI server `cua-driver-docker` or `$FCB_CUA`; H1 legs through `$FCB_PYTHON`; tool arguments use `/repo/...` paths (`test-plan.md:136-141`).

G3 headless (D1 second form). The scorer writes `REPO_ROOT/benchmarks/gate-artifacts/g3/<run>` (`score_g3_replay.py:50-55`, `:507-508`), but `/repo` is mounted read-only (`compose.yaml:24`). Run it from a container temp copy; no source change:
```bash
docker exec -u cua fcb-desktop sh -c 'rm -rf /tmp/g3r && mkdir /tmp/g3r && cp -r /repo/benchmarks /repo/src /tmp/g3r/ \
  && cd /tmp/g3r && fcb-py benchmarks/g3/fault-injection/score_g3_replay.py --leg 1.1.x --run g3r-<run>-1.1.4 --check \
     --frames-check benchmarks/g3/fault-injection/frames-reference.json'
docker cp fcb-desktop:/tmp/g3r/benchmarks/gate-artifacts/g3/g3r-<run>-1.1.4 "$RUN_DIR/evidence/g3-headless"
```
`pyyaml` 6.0.3 is in the AppImage Python (`/opt/freecad/usr/lib/python3.11/site-packages/yaml`, checked read-only). That the scorer's H1 child starts under `fcb-py` is not proven; prove it on one case first.

G3 GUI (D1 first form, after Q1): copy `g3_gui_replay.py` and `gui.py` from `2026-10-03-04/evidence/` into `$RUN_DIR/evidence/g3-gui/` and change only: repo root from `git rev-parse --show-toplevel`; MCP `http://127.0.0.1:18765/mcp`; Fit All and capture through `$FCB_CUA` (Fit All toolbar button by `element_token`, `get_window_state` with `screenshot_out_file` under `/repo/tests/uat/run/<run>/`); output file in the new folder. Replay logic, `verify_shape` grading and classification stay. Run from the host `uv` env with the container FreeCAD started. "Unchanged" stays as `spec-10-8-d:26` states it: 4/4 controls OK, 10/10 reverted OK, 10/10 planted DETECTED, every anchor frame equal to `frames-reference.json`.

### 6.5 Rough cost

| Item | Basis | Estimate |
| --- | --- | --- |
| S0 + R0 runner | 2026-10-24-01 R0: runner 8 min on host | 1 h |
| R0a + R0b review | 2026-10-24-01 R0 review hit the session limit (14:29-15:46, resumed 18:00) | 3-4 h, 2 sessions |
| P1-P12 | 2026-10-24-01: R2 22 scenarios in 64 min, R3 12 scenarios in 91 min | 1-1.5 h each, 12-18 h |
| G3 | 14 cases, 24 GUI builds | 1-1.5 h |
| Lead grading and report | about 20 % on top | 3-4 h |
| **Total** | | **about 20-25 h sequential, about 15 agent sessions, 3 working days with session limits** |

Plan for one fix loop: the first container run of whole scenarios is likely to find route defects (10-10 measured routes, not scenarios; `deferred-work.md:1930`).

## 7. AC-to-test map

| AC1 clause | Check | Evidence |
| --- | --- | --- |
| Given Stories 10.1-10.7b done | `sprint-status.yaml:163-171` all `done` (also 10-9, 10-10) | read at plan time: true |
| Given CI green | `gh run list --workflow ci.yml` on `main` and on the pushed integration head; all four jobs `success` | `41397825279` (`8e8c187`), `44231368719` (`031d8e8`); head `6dd8bce` not pushed |
| full suite TC-01..TC-14 | one `report.md` row per scenario, 255 rows, each once | lead recount from rows |
| TC-99 | 5 rows, Gate 2 table | `report.md` Gate 2 |
| G3 live replay | both D1 forms, criterion of `spec-10-8-d:26` | `evidence/g3-headless/`, `evidence/g3-gui/` |
| on FreeCAD 1.1.4 | `query_capabilities.freecad_version`, `results.json` `run.freecad_version` | build banner |
| through the 10.7b runner | `runner/results.json`, drawn seed | `run.sample_seed_source: drawn` |
| agent review per §9 | one review line per reviewed scenario (`test-plan.md:504-509`) | `report.md` |
| desktop free | container used only by the run; one phase agent at a time | `launch-log.tsv` |
| Gate 1 green | Critical 174/174, High ≥ 64/67 (95.5 %) | `report.md` Gate 1 summary |
| Gate 2 matches | each TC-99 row EXPECTED-FAIL as documented; a different failure is a finding; a pass is a promotion signal | `test-plan.md:540-560` |
| report committed | commit with the user's approval | `git log -- tests/uat/run/<run>` |
| decision 19 (not AC1) | canary dispatch log shows solve and both suite steps | slice 10-8-e |

## 8. Test pyramid

Status today: nothing below ran in this plan session except the canary dry-run solve. Status planned is for the build.

| Level | Check | Command | Planned |
| --- | --- | --- | --- |
| UAT | Gate run R0, R0a-b, P1-P12, G3 GUI | section 6.4 | RUN (container) after Q1, Q5 |
| UAT | Native validation (escalation ladder, Check Geometry) | `freecad-native-validation.md` in container | RUN only on escalation |
| E2E | H1 sweeps over the image addon | `uv run python scripts/automation/run_mcp_e2e.py`, `run_mcp_edge_cases.py` | RUN in S0 |
| E2E | Close-loop harness | `uv run python tests/close-loop/check_harness.py`, `uv run python tests/close-loop/journey_box.py` | RUN in S0 |
| E2E | Canary on dev FreeCAD | `gh workflow run canary.yml --ref <branch>` | BLOCKED: needs a pushed branch (user, Q4) |
| Integration | In-FreeCAD suite at the run baseline | `"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" -u <tmp>\user.cfg -s <tmp>\system.cfg tests/run_tests.py` | RUN (host, not UAT) |
| Integration | G3 headless scorer on 1.1.4 | section 6.4 | RUN (container) |
| Integration | Probe and pixel fault sets | `run_faults.py`, `pixel_faults.py` | RUN in S0 |
| Integration | CI headless leg at the run head (1.1.3) | push → `ci.yml` | BLOCKED: needs push (user, Q4) |
| Integration | Canary dependency solve | dry-run in `mambaorg/micromamba:2.3.3` | RUN once by the planner (section 5); repeat in 10-8-e |
| Unit | Repo gates | `uv run ruff check .`, `uv run python scripts/check_imports.py`, `uv run pytest tests/external -q` | RUN at each slice merge and at the run baseline |
| Unit | Runner tests after 10-8-f | `uv run pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q` | RUN |
| Unit | Canary YAML | none possible for a workflow value; the dispatch run is the test | NOT RUN (no harness) |

Known unstable test: `test_managed_venv.py::test_Should_start_an_external_interpreter_When_freecad_set_pythonhome` (fails in a full run, passes alone; Environment block).

## 9. Each planned check can fail

| Check | How it fails | Proof it is sensitive |
| --- | --- | --- |
| Gate 1 thresholds | one Critical FAIL makes it red | 2026-10-23-02 was red (Critical 126/174) |
| Runner verdicts | FAIL on `expect`/`probe`/`pixel`; ESCALATE on disagreement | `tc-08-04.json:487` failed every run; runner reproduced 2026-10-03-04 verdicts (`replay.md`, 0 unexplained) |
| Pixel check | empty, clipped, moved, too small | `pixel_faults.py` planted set |
| Probe | planted bad state | `run_faults.py` 5/5 detected, 0/2 false alarms (10-9) |
| §9 agent review | agent read contradicts scripted PASS → FAIL (`test-plan.md:514-518`) | rule; lead re-reads samples |
| G3 headless | MISSED planted, FALSE_ALARM control, frame drift, INVALID_INPUT exit non-zero | scorer rules `score_g3_replay.py:18-27`; sensitivity 1.0 on 10 planted (`validators.yaml:175-189`) |
| G3 GUI port | same classification as headless; a broken port changes counts away from 4/10/10 | criterion is exact counts, not "no error" |
| Watchdog | exit 1 on lapsed session, dead window, failed `initialize`, surviving `FCB_TMP_snap_*` | 10-9: exit 0, 1, 1 on three cases; `check_temp` now scans `<workdir>/tmp` (`uat_watchdog.py:150-173`) |
| user.cfg hash | any write changes SHA-256 | 2026-10-24 incident `4c415695…` |
| Canary | missing solve line or missing suite lines | old spec reproduced the failure locally |
| CI green | any job not `success` | jobs are blocking (`project-structure.md:278-284`) |

## 10. Platform differences

| Item | Windows host | `fcb-desktop` container | GitHub runner |
| --- | --- | --- | --- |
| Role | lead shell, `uv` env (Python 3.12), host gates, in-FreeCAD suite | UAT target: GUI, runner, watchdog, H1 host, G3 | `ci.yml` blocking legs, canary |
| FreeCAD | 1.1 at `C:\Program Files\FreeCAD 1.1\bin\`, never for UAT | 1.1.4 AppImage, Qt `libQt6Gui`/`libQt6XcbQpa` rebuilt with AT-SPI | conda-forge 1.1.3 (no 1.1.4 on conda-forge); canary `2026.09.16` (26.3-dev, OCCT 8.0.1) |
| Python | 3.12 (`uv`) | 3.11 (`fcb-py`, numpy 1.26.4) | 3.11 (headless); canary unpinned → 3.14 |
| GUI driver | none for UAT | `cua-driver` 0.28.1; `invoke_menu` refused on Qt menu bar; tree/combo selection by foreground pixel click | xvfb + Mesa for render tests only |
| Paths | `$PROJECT_ROOT` host path; `MSYS_NO_PATHCONV=1` in Git Bash | `/repo` read-only, `tests/uat/run/` writable | checkout dir |
| MCP | `http://127.0.0.1:18765/mcp` (relay) | proxy on `127.0.0.1:8765` | H1 stdio only |
| Rendering | — | Mesa software GL, Linux fonts, 1600x1000; compare captures only with the same image | Mesa software GL |
| Clock | UTC+7 | other zone; watchdog `--since` needs an offset | UTC |
| Profile | developer `user.cfg` (guarded) | container profile, clean on `--force-recreate` | throwaway |

## 11. Deferred items 10-8 settles or unlocks

The ledger has ids only for DW-1..DW-5; later entries are cited by the line of their `summary:`.

| `deferred-work.md` line | Item | 10-8 action |
| --- | --- | --- |
| 1791 | Story 10.8 goal 3: full gate run | resolve with the run folder |
| 1805 | `agent_check` that names a before-capture: re-run steps by MCP to that step | apply in R0a/R0b |
| 1838 | P11 TC-13, P12 TC-14/TC-99, G3 GUI never ran; Gate 2 has no result | run P11, P12, G3 |
| 1834 | TC-08-12, TC-09-15 need a re-run only | run in P6, P7 |
| 1842 | TC-11-18 BLOCKED: H1 env without `pivy` | container `fcb-py` has FreeCAD's pivy; settle in P9 |
| 1809 | Display freeze (Windows GPU windows) | container has no Windows desktop; record whether any stale display appears (live display check, `uat-run-practices.md:169-171`) |
| 1738 | Watchdog `check_temp` blind to workdir snapshots | already fixed in code (`uat_watchdog.py:168-173`); confirm live, then resolve |
| 1742 | Unclean-kill and open routes unconfirmed (Windows integrity level) | container routes: `kill -KILL`, `fcb-freecad start <file>`; settle in P10 (TC-12-15) |
| 1746 | TC-12-09 modal Preferences through `QTimer`, route never run | run in P10; a stall is a finding |
| 1777 | Pixel check false-alarm rate on real captures | container captures give a new measure; record in `report.md` |
| 1926 | "Pixel points": scroll the row into view first | watch item for P10, P11 |
| 1930 | 10-10 proof tools have blind spots; 10-8 runs every scenario | the run is the check |
| 1934 | `cua-driver` exits 0 on a tool error | phase rule: judge `$FCB_CUA` steps by text (`test-plan.md:203-204`) |
| 1904 | `invoke_menu` refused (driver limit stays) | leaf token route only |
| 1813, 1817, 1821, 1846-1878 | product findings of 2026-10-23-02 with no Then | not settled by 10-8; re-observe only |

Doc drift seen, not in scope: `freecad-native-validation.md:15-17` still says the container shows only the top-level window (false since 10-9).

## 12. Open questions for the user

**Q1. Two frozen lines of `spec-10-8-d` (section 3.3).**
- A (recommended): approve both changes as worded in section 3.3. Purpose of each line stays; the run can execute in the container.
- B: approve A for the profile line, but run the G3 GUI form as agent-driven MCP calls by a phase agent instead of a script. More agent time; same criterion.
- C: keep the frozen text. The G3 GUI form and the `-u` line cannot be met in the container; the run would report them NOT RUN.

**Q2. Canary target and doc correction.**
- A (recommended): `freecad>=2026` from conda-forge `main` (calendar weekly builds). One-file change; matches the design route "conda-forge if published". Limit: conda-forge uploads lag (latest `2026.09.16`, 8 weeks old). Correct "1.2-dev" to the next dev line in AD-11 and `project-structure.md` with your agreement.
- B: FreeCAD weekly AppImage from GitHub releases (the design fallback, never wired). Always current (`27.1-dev` today); about 20 more lines (download, extract, pip layer into the AppImage Python).
- C: track the 26.3 release candidates. No conda-forge package exists for them (`freecad_rc` label stops at `1.0rc3`); only the AppImage route works.

**Q3. What "canary fixed" means.**
- A (recommended): the job installs a dev FreeCAD and runs both suites; failing tests on the dev line become `deferred-work.md` findings. Matches AD-11 "allowed-to-fail".
- B: the canary must be green. May need product changes for OCCT 8 and Python 3.14, which grows 10-8 by an unknown amount.

**Q4. Push and `main`.**
- A (recommended): push a fix branch for the canary dispatch proof and push `fix/uat-gate-1-failures` so CI runs on the run baseline; merge the canary fix to `main` together with the epic, later. The weekly canary stays red until then.
- B: also put the canary fix on `main` now (needs your words naming `main` and the operation).
- C: no push. The canary proof stays BLOCKED and CI green rests on `031d8e8`.

**Q5. Fix the known test-case defects before the gate run (slice 10-8-f)?**
- A (recommended): yes. Three Critical scenarios (TC-02-05, TC-11-18, TC-12-05) fail as written, so a run without the fix is red before it starts.
- B: no. Run as written, report the FAILs, fix, then re-run (spec D2). Costs one extra loop.

**Q6. TC-02-08 (High): the fit leaves part of the plate under the floating Tasks panel and reports `fitted: true` (open since 2026-10-24, lead log R1; FreeCAD's own Fit All does the same).**
- A (recommended for 10-8): run as written; a FAIL is recorded as a product finding and deferred. Gate 1 High allows 3 FAILs of 67.
- B: decide now that the area under an overlay panel is not visible: product fix in `view_fit` and a design note; new work in Epic 10.
- C: decide that the area counts as visible: rewrite the Then with a design citation.

**Q7. Re-run rule after a red run whose fixes touch only test cases or the harness (same image id, no `src/` change).**
- A (recommended): re-run only the affected scenarios into a new folder; record the choice in `RUN-CONTEXT.md` and `report.md` (`uat-run-practices.md:95-98` allows an owner choice).
- B: full re-run of every scenario each time.

**Q8. Autonomy for 10-8 (open in the status file).**
- A (recommended): same contract as decisions 16 and 21: the leader commits verified slice work and the run folder on the integration branch and merges slices after verifier PASS. Not granted: push, any change to `main`, history rewrite, scope change.
- B: ask before each commit.

## 13. Risks

| Risk | Effect | Mitigation |
| --- | --- | --- |
| 10-10 measured each route, not whole scenarios | route defects surface as FAILs in the run | count them as test-case defects; Q7 re-run rule; expect one loop |
| Steps that need a human | commit, push, `main`, product decisions (Q6), a disputed visual result | asked once with evidence (`uat-run-practices.md:213-214`); no physical input needed in the container |
| `cua-driver` exits 0 on a tool error | a failed `$FCB_CUA` step looks done | judge by printed text; runner already checks JSON (`capture.py:42-50`) |
| Runner launch group fails (exit 3) | its scenarios are `not_run` | re-run that group, then review (`test-plan.md:510-513`) |
| Container restart in a phase (rebuild after a fix) | cache proxy returns "outcome unknown" for a call in flight (`tests/close-loop/README.md:79`) | never retry a mutation blindly; restart the scenario from its Given |
| Agent session limit in a phase | partial phase | keep rows, resume at the first scenario with no row (`uat-run-practices.md:101-102`) |
| G3 scorer H1 child under `fcb-py` unproven | G3 headless NOT RUN | prove on one case in S0; CI proves the same scorer on 1.1.3 each push (`ci.yml:138-144`) |
| TC-13, TC-14, TC-99 and G3 GUI have no result since 2026-10-03-04 | unknown FAIL count | phases P11, P12, G3 last in order but planned in full |
| Image older than HEAD (built 2026-11-18 00:06) | runner tests the wrong addon | rebuild in S0; record image id and `results.json` `run.addon` |
| Canary goes red on tests after the fix | looks like a failed fix | Q3 sets the bar before the work |
| `tests/uat/run/` is shared | other agents' folders | new folder only; never edit another |

## 14. Brief check (claims the documents do not support)

1. Status file: "Container `fcb-desktop` stopped". At 17:10 on 2026-11-18, `docker ps` showed `fcb-desktop Up 18 minutes`. Someone started it after the status was written.
2. Status file: "includes the weekly `canary` fix on `main` (decision 19)". Decision 19 says "10-8 includes the canary fix"; it does not say `main`.
3. Brief: "Same job failed 2026-10-26, 11-02, 11-09". True, and incomplete: the job failed at the same step on every run since 2026-07-27; earlier "success" was `continue-on-error`.
4. Brief and decision 19: "10.8 AC needs CI green" read as needing the canary. AD-11 and `project-structure.md:235` make the canary non-blocking; blocking CI is green.
5. Brief: "Decisions rows 1-27". Rows are out of order in the file (5 after 16, 15 after 10); all 27 ids exist.
6. Brief: "TC-01..TC-14, TC-99". Correct per AC1; the test plan index also lists TC-16, and TC-15 exists unlisted.
7. Brief: "Find every item ... with ids". Only DW-1..DW-5 carry ids; section 11 cites lines.
8. `epic-10-context.md` is valid by the freshness rule, but its runner line describes the Windows launch; the source documents never changed, so recompiling would not fix it.

## 15. State at report time

- Wrote only this file. Working tree otherwise as found (`epic-10-status.md` modified and `.leader.json` untracked by the leader).
- Nothing left running. The throwaway `mambaorg/micromamba:2.3.3` container ran with `--rm`; its image stays in the local Docker cache. Scratch logs are in the session scratchpad.
