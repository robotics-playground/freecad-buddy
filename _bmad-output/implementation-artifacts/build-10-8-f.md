# Build report: Story 10-8-f (known UAT test-case defects)

Branch `story/10-8-f-uat-testcase-defects`, base `9aee2bf`. Spec: `spec-10-8-f-uat-testcase-defects.md` (status done).

## Result

Nine items fixed in `tests/uat/`. All eight items of plan section 3.2 were still present at `9aee2bf`; none was dropped. Leader decision 38 added TC-02-02 `:106`.

| Item | Change |
|------|--------|
| TC-02-02 `:106`, TC-02-05, TC-02-14 | Counts read from the `OK: <N> objects, <S> shown[, <M> matches].` line of the text-only `query_tree_summary`; tree lines defined at TC-02-05 `:232` (without `OK:`, `Warning:` sentence and blank line, `framing:`, `path:`, steering line); whole-text compares became tree-line compares |
| TC-11-18 | New When step: `Next` leaf of the Windows menu until the title names `box-10-20-30`, at most once per open tab (`Start` counts), else NOT RUN; visual Then names the 3D view and the golden tree entry and says the `tc11-18` tab stays |
| TC-12-05 | Tree-line compare; `<ObjectB>` line must differ for the live-flag Then |
| `tc-08-04.json:487` | `"\\bFillet\\b"` |
| TC-06-01 Cleanup | `RemInt` |
| TC-08-17 `:680` | Read `<V0>` first, write the opposite value, restore `<V0>` |
| TC-09-01 Given | `pgrep -fc` over both H1 flag orders and the worker, prints `0` |
| `tests/external/test_uat_runner.py` | New case: no control character in any string of any committed scenario (baseline `tc-08-04.json` fails it; fixed file passes) |

## Tests

- `uv run pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q`: 182 passed (181 before, plus the new case).
- `uv run ruff check .`: clean. `ruff format` leaves `test_uat_runner.py` unchanged (27 other files were already unformatted; not touched).
- Runner validate: 72 scenario files load.
- Container, `tc-08-04.json` once: 0 PASS, 0 FAIL, 1 ESCALATE (agent_check only), 0 run errors. Capture read: pad, sharp edges, no error colouring.
- Live readers in the container, each with request and output in `tests/uat/run/2026-11-18-10-8-f-check/readers-check.md`: first-line counts (golden, two boxes, Body/Pad, `App::Part`/`App::Link`), `RemInt`, `pgrep` (0 now; count 2 for a fake H1), TC-11-18 `Next` activation, TC-12-05 header versus tree lines, TC-08-17 carve-out.
- TC-11-18 captures: `evidence/tc-11-18-before.png` and `evidence/tc-11-18-after.png`, both read: same box, same camera; the golden view in front after the step; the `tc11-18` tab and tree entry also show in `after` until Cleanup. Before the step, `view_fit_viewport` on the golden returned INVALID_INPUT (viewport shows `tc11_18`).
- Container FreeCAD stopped; no process, watch loop or temp file left.

## Review

Three rounds, nine fresh subagents (no names: the harness refuses a name for a teammate's subagent). Ids: round 1 Blind a293b15c6e2011c61, Edge a4c57c00e6a4f8622, Gap af9d379c3ee552c35; round 2 Blind aabd4f32da2b1096b, Edge a7e488e97ba4894aa, Gap ad9a3af54cefa8095; round 3 Blind a0bcb60459e202f32, Edge a4a3cbea7402f7b26, Gap ad6e1dfad12f8a37f. Models as ordered: Blind and Edge opus high, Gap sonnet medium. Full triage in the spec `## Review Triage Log`.

Patched: `pgrep` flag order and worker; "first line" wording and header definition; whole-text compares; TC-11-18 stop limit and Then title; TC-08-17 read order and the opposite-value write; a backspace byte in the spec; AC 2 check (a raw scan could not see the JSON escape; replaced by the decoded-string test); run-folder notes.
Rejected: committed run folder versus plan "not committed" (leader condition (b) wants the records); frozen "eight defects" count; `pgrep` exit code; extra live records for TC-02-14 `depth: 5`.
Deferred (two entries in `deferred-work.md`; the design entry unblocks with the epic-10 close correct-course batch):
1. `scenario.py` still accepts a control character in a regex in any file. Unblock: a story that may edit runner code.
2. `mcp-tools-design.md:249` says `structured_content` carries counts and the client gets `content[1]`; section 1.3 says text-only. Unblock: a design correction the leader approves.
(A third entry, TC-09 `:313` and TC-12 `:659`, `:660`, was fixed in round F1 and removed.)

## For the leader

- The TC-11-18 visual Then title changed from "the window is identical" to "the 3D view and the `box-10-20-30` tree entry are identical", with the tab note. This is the line decision 23 lists; veto it if you want the old text.
- The step needed two `Next` presses with two documents: the `Start` tab is in the cycle (inference from the tab strip; the first press left the frame title unchanged).
- I changed `tests/external/test_uat_runner.py` (the intent names `tests/uat/` only; the spec Tasks list names this test; `src/`, runner code and container files are untouched).
- TC-02-05 `:234` and TC-02-14 `:583`, `:585` said "first line is `path:`" before this slice; this slice reworded them to "tree text below the header lines" (leader to veto if unwanted).
- Implemented directly, not through a dispatch subagent (ten short edits tied to live checks).

## Fix round F1 (leader triage)

TC-09 `:313`, `:314` (and the `<M> shown` label at `:358`, `:475`) and TC-12 `:659`, `:660` now read the `OK:` line (`<S> shown`, `<M> matches`, `, truncated.`). Live calls on a 30-box and a 250-box document are in `readers-check.md` (39 shown at depth 3; 200 shown with `, truncated.` and the steering line). Neighbouring Thens re-read and still hold (listed in `readers-check.md`). pytest 182 passed, ruff clean. No new lens round (leader decision).
