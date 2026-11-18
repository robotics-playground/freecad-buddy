---
title: 'Story 10.8 (goal 1d): Fix Test-Case Defects Found by the Smoke Run'
type: 'chore'
created: '2026-11-18'
status: 'in-review'
baseline_commit: 'ffd131df7ac5071d81792940b0ed4c7984417f2c'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-10-8-f-uat-testcase-defects.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/uat-run-practices.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** UAT smoke run 2026-11-18-01 failed nine scenarios for reasons in the test-case text, not in the product (`report.md`, `bugs.md` B-11..B-17). Five visual Thens need a camera or edit mode the scenario never sets. Two read a text-only tool as an envelope. One expects MSVC error text. One expects an exact `text` that the framing warning extends.

**Approach:** Edit the nine cases in `tests/uat/` only. Each camera or edit-mode fix adds the missing step through a route measured in the `fcb-desktop` container. Each Then that changes cites the design line that proves the product behaviour. Run each changed scenario once in the container and read every capture. TC-02-13 (no emoji font) is a harness limit and stays as it is.

## Boundaries & Constraints

**Always:** Keep every Then observable and as strict as before (decision 49, `uat-run-practices.md` section 8). Keep two trailing spaces on each Given/When/Then/And line. Run in the container only, MCP only on `:18765`.

**Never:** Weaken a Then to make a product defect pass. Edit `src/`, runner code, container files or an earlier run folder. Install fonts. Touch TC-02-13.

</frozen-after-approval>

## Code Map

- `tests/uat/testcases/TC-02-document-ingestion-and-handles.md` -- TC-02-15 (`:596`), TC-02-17 (`:680`)
- `tests/uat/testcases/TC-09-error-contract-and-fault-injection.md` -- TC-09-12 (`:484`)
- `tests/uat/testcases/TC-03-sketch-authoring.md` -- TC-03-03 (`:109`), TC-03-20 (`:862`)
- `tests/uat/testcases/TC-07-verification-and-export-pairing.md` -- TC-07-03 (`:109`), TC-07-05 (`:185`)
- `tests/uat/testcases/TC-13-gui-mcp-parity.md` -- TC-13-04 (`:257`), TC-13-10 (`:531`)
- `tests/uat/scenarios/` -- `tc-02-15`, `tc-02-17`, `tc-03-03`, `tc-03-20`, `tc-07-03`, `tc-09-12`, `tc-13-04`: `expect` blocks already read the text form; only the `agent_check` strings mirror the changed Thens
- `mcp-tools-design.md:60` -- `query_tree_summary` text-only: `<STATUS>: <text>` line, `detail.message` replaces `text` when not OK, no `structuredContent`
- `src/freecad_buddy/contracts/envelope.py:111` -- framing warning appended to `text`; spine AD-32 (`ARCHITECTURE-SPINE.md:376`)
- `tests/uat/test-plan.md` section 6 -- Isometric push button by token, Sketch edit mode via `script_exec`

## Tasks & Acceptance

**Execution:**
- [x] TC-02-15, TC-09-12 -- the `query_tree_summary` refusal is read as the text line `INVALID_INPUT: <message>`; other tools keep the envelope Thens -- text-only tool
- [x] TC-02-17 -- tails compared with each other and by prefix, the platform text recorded not required -- FreeCAD passes its own text through
- [x] TC-03-03, TC-03-20, TC-07-03, TC-13-04, TC-13-10 -- add the camera or edit-mode step before the capture -- the Then is met by the scenario's own steps
- [x] TC-07-05 -- fit first in the Given (or accept the documented suffix) -- AD-32
- [x] seven scenario `agent_check` strings -- mirror the changed text
- [x] `deferred-work.md` -- nine entries resolved (each names this spec; the leader adds the commit SHA after the commit)

**Acceptance Criteria:**
- Given each changed case, when its steps run in the container on the correct product, then every Then passes.
- Given the 72 scenario files, when the runner validates them, then all load.
- Given the runner tests and ruff, when run, then they pass.

## Implementation Notes

Implemented directly by the builder: short text edits to nine cases and seven scenario `agent_check` strings, each tied to a live container check. Added camera and edit-mode steps sit where the case already puts its visual set-up lines (`And` lines in the Then block for TC-03-03 and TC-07-03, because the MCP Thens before them need edit mode closed; the Given for the TC-03-20 before capture; the When for TC-13-04 and TC-13-10). No Then expectation changed. Only the readers of TC-02-15, TC-09-12 and TC-02-17 changed what a Then checks; the visual Thens of TC-03-03, TC-03-20 and TC-07-03 gained a lead-in clause that names the state (edit mode, Isometric view) set by the new step, with the judged picture unchanged.

Design line per change:

| Case | Change | Proof |
|------|--------|-------|
| TC-02-15, TC-09-12 | `query_tree_summary` refusal read as its text line | `mcp-tools-design.md:60` (text-only tool, no `structuredContent`); live read of both handles |
| TC-02-17 | `Invalid project file <path>:` prefix and equal tails stay hard; platform literal dropped | `usecases/documents.py:496-499` (FreeCAD text passed through); Windows text `ios_base::failbit set: iostream stream error`, Linux text `basic_ios::clear: iostream error` |
| TC-03-03, TC-03-20 | edit mode, `Isometric` push button by token, `Fit All`, 8 s | `test-plan.md` section 6 (named view buttons work by token); `resetEdit` restores the earlier camera, measured |
| TC-07-03 | `setEdit(Sketch)` and GUI `Fit All` before the capture | `TC-03:31` (constraint colour and glyphs draw only in edit mode) |
| TC-07-05 | `Show All` then `view_fit_viewport` in the Given | `envelope.py:105-113` (warning appended when `fits` is false), spine AD-32 (`ARCHITECTURE-SPINE.md:376`), `TC-14:399`; live: warning present unfitted, absent fitted |
| TC-13-04, TC-13-10 | `Isometric` push button before `Fit All` | render uses `camera:"iso"`; live captures |

Live record: `tests/uat/run/2026-11-18-10-8-g-check/README.md`. Runner: 7 scenarios, 0 FAIL, 0 run errors. Pytest 186 passed, ruff clean, 72 scenarios load.

## Spec Change Log

## Review Triage Log

Round 1 lenses: Blind Hunter BH1-BH13 (opus, high), Edge Case Hunter EC1-EC12 (opus, high), Verification Gap Finder 0 findings (sonnet, medium).

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| BH1 | `baseline_commit` has 39 hex digits | low | `git rev-parse ffd131d` ends in `c` | patch: full SHA |
| BH2, EC12 | deferred entries carry no SHA; Task box ticked | low | the leader commits (decision 28) | patch: Task text says the leader adds the SHA; resolution lines name the spec |
| BH3, EC9 | quality bar Q6 says When/Given only; steps sit in Then-block `And` lines | low | MCP Thens before them need edit mode closed (`TC-03:31`); the suite already holds its visual set-up lines there | reject: placement kept, stated in Implementation Notes and the report |
| BH4 | Notes claim no Then text changed | medium | three visual Thens got a lead-in clause | patch: Notes reworded |
| BH5, EC1 | read-only `script_exec` while edit mode is open | low | measured: call returns OK in edit mode | patch: step says it is read-only |
| BH6, EC2 | TC-03-03 and TC-03-20 close the document with edit mode open | medium | `TC-07-03` got `resetEdit` in Cleanup | patch: `resetEdit` added to both Cleanups |
| BH7, EC3 | camera check weak (any non-top quaternion passes); no read-back in other cases | medium | measured iso `[0.425, 0.176, 0.34, 0.82]` | patch: tolerance 0.01 around the measured value in TC-03-03. Other cases: reject, their visual Then judges the camera on the pixels (render against window) |
| BH8, EC5, EC6 | 8 s wait unexplained; absent in TC-13 | medium | animation; stable at 6 s and 8 s in the run | patch: reason stated; `sleep 8` added to TC-13-04 and TC-13-10 blocks |
| BH9, EC11 | capture names differ between case text and check run | low | | patch: `tc-03-03-after.png` renamed; README maps the TC-13 states |
| BH10 | Tasks panel hides the plate right end | low | seen in the capture | patch: set-up step says what stays visible |
| BH11, EC7 | TC-07-05 Given has no branch when `view_fit_viewport` fails, no check of `framing.fits` | low | `TC-07` Preconditions give the GUI fallback | patch: fallback and `framing.fits` true added |
| BH12 | `agent_check` of tc-13-04 cites no source for the iso camera | low | `view_fit.py` `_view_isometric` (`TC-14:211`) | patch: citation added |
| BH13 | README does not say TC-07-05 and TC-13-10 have no scenario | low | | patch |
| EC4 | wrong reason for the camera after `resetEdit` | medium | `setEdit` turns to the sketch plane regardless | patch: wording changed |
| EC-snapshot | After step presses Isometric without a fresh snapshot | low | tokens go stale after `setEdit` | patch: re-snapshot named |
| EC8 | equal empty tails would pass TC-02-17 | low | | patch: `non-empty` added |
| EC10 | TC-07-03 case text cites no source for edit-mode drawing | low | | patch: points to TC-03 Preconditions |

## Verification

**Commands:**
- `uv run pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q` -- expected: all pass
- `uv run ruff check .` -- expected: no finding
- `grep -n '^\*\*\(Given\|When\|Then\|And\)\*\*' <edited TC files> | grep -v '  $'` -- expected: no new output

**Manual checks:**
- One live run per changed case into `tests/uat/run/2026-11-18-10-8-g-check/`; every capture read.
