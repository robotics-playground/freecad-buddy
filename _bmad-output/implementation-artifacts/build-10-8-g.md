# Build report: Story 10-8-g (test-case defects of smoke run 2026-11-18-01)

SHA: uncommitted (CLAUDE.md requires user approval per commit; the leader commits under decision 28). Base `ffd131df7ac5071d81792940b0ed4c7984417f2c`, branch `story/10-8-g-smoke-testcase-defects`. Spec: `spec-10-8-g-smoke-testcase-defects.md` (status in-review).

## Files changed

- Test cases: `TC-02-document-ingestion-and-handles.md` (TC-02-15, TC-02-17), `TC-03-sketch-authoring.md` (TC-03-03, TC-03-20), `TC-07-verification-and-export-pairing.md` (TC-07-03, TC-07-05), `TC-09-error-contract-and-fault-injection.md` (TC-09-12), `TC-13-gui-mcp-parity.md` (TC-13-04, TC-13-10).
- Scenario `agent_check` strings only: `tc-02-15`, `tc-02-17`, `tc-03-03`, `tc-03-20`, `tc-07-03`, `tc-09-12`, `tc-13-04`. No `expect` block changed (they already read the text form).
- `deferred-work.md`: nine entries get a `resolution:` line (TC-02-13 untouched).
- New: spec, this report, `tests/uat/run/2026-11-18-10-8-g-check/`. No edit to `src/`, runner code, container files, or an earlier run folder.

## Review

Lens ids: Blind Hunter `af4f65ab21c1cd22f` (opus, high) 13 findings; Edge Case Hunter `ab8b395e8dd77b7e1` (opus, high) 12 findings; Verification Gap Finder `a46b46f80caec3fdd` (sonnet, medium) 0 findings. Triage table is in the spec. Patched: full baseline SHA, claim wording, `resetEdit` in the TC-03-03 and TC-03-20 Cleanups, camera tolerance in TC-03-03, 8 s settle wait with reason (also in TC-13-04 and TC-13-10), re-snapshot before the second Isometric press, TC-07-05 fit fallback and `framing.fits`, `non-empty` tails in TC-02-17, capture-name mapping. Rejected: quality bar Q6 (see below), camera read-back in the other four cases (the visual Then judges the camera on the pixels). One review round; the patches are text edits, not re-reviewed.

Decision for the leader: Q6 says added steps are When/Given only. The edit-mode and Isometric steps of TC-03-03 and TC-07-03 are `And` lines in the Then block, after the MCP Thens, because those Thens need edit mode closed (`TC-03:31`). TC-03-20 uses the Given (before) and a Then-block `And` (after); TC-13-04 and TC-13-10 use the When. No Then expectation changed.

## Live check (run `tests/uat/run/2026-11-18-10-8-g-check/`, not a gate run)

Runner: 7 scenarios, 0 FAIL, 7 ESCALATE (agent checks), 0 run errors. Agent-driven steps and every capture read are in the run folder `README.md`.

| Case | Result |
|------|--------|
| TC-02-15, TC-09-12 | PASS: refusal is a text line `INVALID_INPUT: unknown or stale document handle: <handle>`; runner expects OK |
| TC-02-17 | PASS: three bad opens read; text file and corrupt zip equal after path replace (Linux text `basic_ios::clear: iostream error`); runner expects OK |
| TC-03-03 | PASS: edit mode, Isometric by token, Fit All: thick plate, axes on top face (`evidence/tc-03-03-after.png`) |
| TC-03-20 | PASS: before and after in edit mode with one Isometric camera; R5 then R4; REPOINTED rollback; magenta line on the plate edge |
| TC-07-03 | PASS: edit mode shows the green segment, label and glyph; the segment has no height so Fit All puts it on the lower edge |
| TC-07-05 | PASS: unfitted export carries the warning; after Show All and `view_fit_viewport`, `text` equals the STEP line (AP242 and AP214) |
| TC-13-04 | PASS: window (Isometric) and MCP render show the same plate, hole and camera |
| TC-13-10 | PASS: before sketch outline and after 30 x 20 x 5 slab, thickness visible in Isometric |

Measured: `setEdit` turns the camera to `[0,0,0,1]`; Isometric gives `[0.425, 0.176, 0.34, 0.82]` and stays in edit mode; `resetEdit` restores the camera from before edit mode.

## Tests

`uv run pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q`: 186 passed. `uv run ruff check .`: clean. 72 scenario files load. Trailing-two-space guard on added Given/When/Then/And lines: no violation.

## Deferred and unverified

- TC-02-13: unchanged harness limit (no emoji font); deferred entry stays open. Blocker: image has no emoji font. Unblock: install a font in `tests/close-loop/docker/`, rebuild, re-run.
- The tc-02-15 and tc-02-17 runner captures are unframed (the runner cannot press GUI Fit All); the agent-driven visual of those two cases was not re-run, since only their text readers changed.
- TC-07-05 and TC-13-10 have no scenario file, so only the agent-driven steps cover them.
- Container FreeCAD is stopped. Leader still adds the commit SHA to the nine `resolution:` lines.
