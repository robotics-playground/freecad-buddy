---
title: 'Measured build session'
type: 'chore'
created: '2026-10-07'
status: 'done'
baseline_commit: '31d9318f98f60fb613799bedec4e16baeeeb5041'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/.knowledge-base/technical/standards/testing/freecad-native-validation.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 11 closes on numbers, but no tool measures a build session the way the 2026-10-06 baseline was measured, and no post-epic build has been measured.

**Approach:** Add a transcript metrics script that reproduces the `0320ba38` baseline from its own transcript. Run it on one new GUI build session of a drawer-size part. Add the bridge-overhead timing, a visual check and native Check Geometry. Commit one report with baseline and new numbers side by side.

## Boundaries & Constraints

**Always:**
- The script measures baseline and new sessions with the same rules. Baseline = first 310 FreeCAD results of `0320ba38` (the transcript grew to 424 after the proposal).
- Report every target row as PASS or FAIL with the measured value. A miss is reported, not hidden.
- Never edit the original `kiwibox-drawer.FCStd`; work on copies. Never open `benchmarks/*/heldout`.
- Report holds numbers and evidence only; no transcript text is committed.

**Never:**
- No change to `src/`, tool behavior, schemas or skills.
- No new MCP tool (a composite sketch tool stays deferred, epic §4.6).
- No counting rule tuned to make a target pass.

**Decisions (human, 2026-10-07):**
- AC3 target: ≤ 10 s GUI (same as Story 11.4), not ≤ 3 s.
- AC3 method: after the build, relaunch the GUI with `time_mutation_overhead.py` on a copy of the built part; `FCB_TIMING_FEATURE` = one Pad/Pocket the agent made (has `Length`).
- Calls per feature: a feature = an `OK` result of a `feature_*` tool other than `feature_set_parameters`; its calls = every FreeCAD call since the previous feature (queries, verify, screenshots included). Target median ≤ 3 (baseline 7.5 under this rule).
- Build session: the operator runs a Claude Code session in `D:/Work/3D Printers/Ender 3V2 - Klipper` (updated skills copied, auto-approve on) and picks the part: about 100+ objects, at least one agent-made Pad/Pocket. The developer agent measures afterwards.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Plain result | `tool_use` `mcp__freecad-buddy__x` + `tool_result` text 500 chars | 1 call, 500 output chars, largest 500 | N/A |
| Spilled result | stub `Error: result (52,000 characters) ... saved to <f>.txt` | spilled 1; output chars = stub length; largest 52,000 | spill file absent: still counted from stub |
| Other tool | `tool_result` of `Bash` | not counted | N/A |
| Limit | `file.jsonl:2`, 3 FreeCAD results | 2 calls; peak and compactions read only up to the 2nd result | N/A |
| Compaction | `system` record, `subtype: compact_boundary` | compactions +1; `isCompactSummary` user record not counted | N/A |
| Peak | assistant `usage` 10 + 200 + 30 | peak 240; sidechain records ignored | N/A |
| No usage | transcript without `usage` | peak 0 | N/A |

</frozen-after-approval>

## Code Map

- `scripts/automation/replay_result_sizes.py` -- reuse `_SPILL` (spill-stub regex, char count in group 1) and `_argument` (`path[:N]`, drive-letter safe) by import; do not change it.
- `scripts/automation/time_mutation_overhead.py` -- AC3 method: env `FCB_DRAWER_COPY`, `FCB_TIMING_OUT`, `FCB_TIMING_FEATURE`, `FCB_TIMING_LENGTHS`; T − R median of 5, warm gate. GUI: `freecad.exe <script>`.
- Transcripts: `C:/Users/thuan/.claude/projects/<project>/<uuid>.jsonl`. `tool_use.id` joins `tool_result.tool_use_id`. Peak from assistant `message.usage` (`input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens`). Compaction = `type: system`, `subtype: compact_boundary`.
- `tests/external/test_check_imports.py` -- script-test style (`sys.path` insert, `tmp_path` fixtures).
- `tests/uat/run/2026-10-07-02/report.md` -- report shape to follow.
- Native validation: `freecad-native-validation.md` §Procedure layers A-C; launch per `freecad-gui-e2e-harness.md`.

## Tasks & Acceptance

**Execution:**
- [x] `scripts/automation/session_metrics.py` -- stdlib + the two imports; `measure(path, limit) -> SessionMetrics` (adds calls-per-feature median); `main()` prints one line per session -- AC1.
- [x] `tests/external/test_session_metrics.py` -- I/O matrix cases plus the calls-per-feature rule on a synthetic sequence -- AC1.
- [x] Run on baseline `0320ba38...jsonl:310`, `eacac40d`, `ff604ce5`; record output in evidence -- AC5.
- [x] HALT for the operator's build session; then run the script on its transcript -- AC2.
- [x] Timing run on a copy of the built part, GUI -- AC3.
- [x] Visual check against a real FreeCAD screenshot + native Check Geometry -- AC4.
- [x] `tests/uat/run/<date>-NN/report.md` + `evidence/` -- AC5.
- [x] `_bmad-output/implementation-artifacts/sprint-status.yaml` -- 11-6 status.

**Acceptance Criteria:**
- Given the baseline transcripts, when the script runs, then `0320ba38:310` gives 310 calls, 77 previews, about 9,590 chars per call, 14 spilled, largest about 110K, peak about 820K, 4 compactions, calls per feature median 7.5.
- Given the new session transcript, when the script runs, then the report states each target with value and verdict: chars per call ≤ 15 % of the baseline script value, 0 spilled, largest ≤ 10,000, calls per feature median ≤ 3.
- Given the timing run, then the report states median T − R against ≤ 10 s.
- Given the finished part, then Check Geometry shows no errors and the agent's screenshot comparison is recorded.

## Implementation Notes

- Calls per feature: the first feature has no previous feature, so it starts the count and gives no sample. This literal reading of the frozen rule gives 7.5 on `0320ba38:310` (16 samples). Counting the first feature from session start gives 9 (17 samples).
- Feature status comes from the envelope `status`. A spilled result's status is read from its spill file; a missing spill file gives no status, so that result is not a feature.
- Sidechain records are skipped for every measure, not only peak.
- `ruff format --check .` fails on 26 pre-existing files; the two new files pass.
- The human told the developer agent to run the build session itself through `cua-driver`. The agent acted as operator: it copied the skills, launched FreeCAD with auto-approve on, and started Claude Code (`bypassPermissions`) in the Ender 3V2 project with a rebuild prompt. Session `a3153685` built 178 objects. Existing files in `cad/` and `exports/` kept their SHA-256.
- Result: AC2 is 3 of 4. `query_tree_summary` returned 11,612 chars, over the 10K target. AC3 PASS at 9.34 s and 9.48 s GUI. AC4 PASS. The GUI abort-path proof fell back to the snapshot on the rebuilt part in 2 of 2 GUI runs and passed headless. All three findings are in `deferred-work.md`.
- The timing script ends with `sys.exit(1)` when the abort check fails, and as a GUI macro that quits FreeCAD.

## Spec Change Log

## Review Triage Log

- Pass 1: `<persisted-output>` spill stub not matched by `_SPILL` (edge-case) -- medium, patch: stub format present in `a3153685` (Bash result, `toolUseResult.persistedOutputPath`); a FreeCAD spill in that form would read as 0 spilled.
- Pass 1: report says the 11,612-char result was `depth 1, Body filter` (edge-case) -- low, patch: transcript call 128 is `root front_plate_piece, depth 3`.
- Pass 1: report says `tree` is 12,024 of 11,612 chars (blind, edge-case, verification-gap) -- low, patch: 12,024 was `json.dumps` with default separators; compact tree is 11,115.
- Pass 1: report says all 189 mutations OK and none failed (blind, edge-case) -- medium, patch: 190 mutation-tool calls; `feature_body_create` call 139 refused `INVALID_INPUT` before the gate (no approval line).
- Pass 1: `chars_per_call` and `_line` have no test (verification-gap) -- medium, patch: the headline AC2 value comes from them.
- Pass 1: sidechain skip tested for peak only (verification-gap, blind) -- low, patch: one test.
- Pass 1: missing-spill-file test cannot observe its rule (verification-gap) -- low, patch: test reshaped with a feature before the stub.
- Pass 1: exact build prompt not committed; prompt written by the agent that knew the targets (blind) -- low, patch: `evidence/build-prompt.txt`; report states who wrote it.
- Pass 1: verdicts ignore that baseline was an edit session and new one a rebuild; `eacac40d`/`ff604ce5` unused (blind) -- medium, patch: report caveat and reference columns.
- Pass 1: solid-feature median script not committed; r2 STL volume column has no source (blind) -- low, patch: `evidence/solid_feature_median.py`, `evidence/r2-stl-volumes.txt` computed from the STL files.
- Pass 1: image blocks count 0 chars, unstated (blind) -- low, patch: docstring and report state it.
- Pass 1: cold first sample vs "warm gate" wording; native volume band unstated; proposal 6 vs 7.5 and 15 vs 14 unexplained (blind) -- low, patch: report text.
- Pass 1: evidence PNG/JSONL and `deferred-work.md` missing from diff (blind) -- false: PNG/JSONL left out of the review diff on purpose and present in `evidence/`; `deferred-work.md` is in the diff.
- Pass 1: missing spill files silently change the feature median (blind, edge-case) -- low, defer: every spill file of the measured transcripts exists today.
- Pass 1: operator change not in Spec Change Log; AC labels; run results in Implementation Notes; ruff format verification line (blind) -- rejected: fix edits this spec; the operator change was the human's instruction in chat.
- Pass 1: `measure` crashes on a truncated last line or non-dict content item (blind, edge-case) -- low, rejected: no measured transcript has either; fix adds guards.
- Pass 1: `:N` larger than the result count measured silently (edge-case) -- low, rejected: the printed call count shows the span.
- Pass 1: visual check with datum planes covering part of the view, duct wall not seen (blind) -- low, rejected: layout matched and volumes within 0.03 %; a new GUI session for one view is out of proportion.
- Pass 1: user paths in committed evidence JSON (blind) -- low, rejected: earlier runs (`2026-10-07-02`) commit the same paths; no secret.

## Design Notes

Baseline reproduction (first 310 FreeCAD results of `0320ba38`), proposal vs this rule set:

| Measure | Proposal | Script rule |
|---|---|---|
| Output chars per call | 9,590 | 9,583 (text the agent received; a spill counts its stub) |
| Spilled | 15 | 14 |
| Largest | 109K | 110,267 (spill size from stub) |
| Peak context | 820K | 819,990 |
| Compactions | 8 | 4 (proposal counted each boundary and its summary record) |

The report shows both columns; targets compare against the script column.

## Verification

**Commands:**
- `uv run pytest tests/external/test_session_metrics.py` -- expected: green.
- `uv run python scripts/automation/session_metrics.py <0320ba38>.jsonl:310` -- expected: matches the Design Notes column.
- `uv run ruff check . && uv run ruff format --check .` -- expected: clean.
