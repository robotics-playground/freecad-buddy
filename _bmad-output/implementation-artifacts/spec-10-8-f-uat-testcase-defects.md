---
title: 'Story 10.8 (goal 1c): Fix Known UAT Test-Case Defects'
type: 'chore'
created: '2026-11-18'
status: 'done'
baseline_commit: '9aee2bf'
route: 'dispatch'
review_loop_iteration: 2
context:
  - '{project-root}/_bmad-output/implementation-artifacts/plan-10-8.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/uat-run-practices.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Run 2026-10-24-01 found eight defects in the text of UAT test cases and one scenario file. Each makes a scenario fail or mislead for a reason that is not a product defect. Gate 1 needs Critical scenarios to pass.

**Approach:** Edit the eight items in `tests/uat/` only. Each Then that changes cites the design line that proves the designed behaviour. Run each changed scenario file once in the `fcb-desktop` container and read the captures.

## Boundaries & Constraints

**Always:** Keep every Then observable except the lines this spec lists (epic decision 23). Keep two trailing spaces on each Given/When/Then/And line. Run the changed scenarios in the container, never on the host.

**Decisions:** Leader decision 38 adds TC-02-02 line 106 (same reader defect, same proof). Each Then change cites its design line in the AC map below.

**Never:** Weaken a Then to make a product defect pass (report it to the leader). Edit `src/`, runner code, container files or an earlier run folder. Touch TC-02-08.

## I/O & Edge-Case Matrix

| Item | Before | After |
|------|--------|-------|
| TC-02-02, TC-02-05, TC-02-14 | Then reads `structured_content.shown` / `.matches` of text-only `query_tree_summary` | reads `<S> shown` and `<M> matches` in the first text line `OK: <N> objects, <S> shown, <M> matches.` |
| TC-11-18 | visual Then "identical to before" while the new `tc11-18` view is in front | When activates the golden view with the `Next` leaf of the Windows menu before the closing fit |
| TC-12-05 | compares the whole tree text | compares the tree lines only, not the `OK:` and `framing:` header lines |
| TC-08-04 JSON | `"\bFillet\b"` is a backspace | `"\\bFillet\\b"` |
| TC-06-01 Cleanup | `p.RemoveInt` | `p.RemInt` |
| TC-08-17 line 680 | restore `Visibility: true` | restore the value read before the toggle |
| TC-09-01 Given | no `hosts.main` process | no H1 (`--mode inline --transport stdio`) `hosts.main` process |

</frozen-after-approval>

## Code Map

- `tests/uat/testcases/TC-02-document-ingestion-and-handles.md` -- lines 232-239 (TC-02-05 Thens), 583-585 (TC-02-14), 106 (TC-02-02, added by leader decision 38)
- `src/freecad_buddy/usecases/queries.py:46-48` -- `summarize_tree` builds `<N> objects, <S> shown[, <M> matches]`; `adapters/mcp_server.py:127-138` `_plain_text` puts it after `OK: `
- `mcp-tools-design.md:60` -- text-only tool, no `outputSchema`, no `structuredContent`; `:282` header lines
- `tests/uat/testcases/TC-11-security-posture-and-artifact-hygiene.md:867-887` -- TC-11-18 When and visual Then; model the new step on `TC-09:403` (`Next` leaf, `list_windows` title names `box-10-20-30`; spine AD-31)
- `tests/uat/testcases/TC-12-gui-workflows.md:329-332` -- TC-12-05 tree comparisons
- `tests/uat/scenarios/tc-08-04.json:487` -- the only scenario with a control character (checked over all 72 files)
- `tests/uat/testcases/TC-06-render-and-gui-visual-fidelity.md:131` -- Cleanup; `docs/references/FreeCAD/src/Base/ParameterPy.cpp:242` registers `RemInt`
- `tests/uat/testcases/TC-08-preview-confirm-and-undo.md:680` -- TC-08-17 carve-out step
- `tests/uat/testcases/TC-09-error-contract-and-fault-injection.md:46` -- TC-09-01 Given; the GUI proxy runs `serve --mode rpc --transport http` (`bootstrap.py:240`), H1 runs `serve --mode inline --transport stdio` (`scripts/automation/run_mcp_e2e.py:77-98`)
- No scenario file mirrors TC-02-05, 02-14, 06-01, 08-17, 09-01, 11-18 or 12-05. Do not change `src/`, runner code or other scenario files.

## Tasks & Acceptance

**Execution:**
- [x] TC-02 file -- replace `structured_content` readers with first-line text readers -- text-only tool
- [x] TC-11 file -- add the Windows-menu activation step -- AD-31
- [x] TC-12 file -- compare tree lines only -- header lines change by design
- [x] `tc-08-04.json` -- fix the regex escape
- [x] TC-06, TC-08, TC-09 files -- one-line fixes above
- [x] `tests/external/test_uat_runner.py` -- one case that fails on a control character in a committed regex -- AC 2 needs a check that can fail
- [x] Container run of `tc-08-04.json` -- into `tests/uat/run/2026-11-18-10-8-f-check/`, labelled not a gate run

**Acceptance Criteria:**
- Given `tc-08-04.json`, when the runner runs it in the container, then the Fillet-explanation check passes.
- Given the 72 scenario files, when the runner validate step loads them, then all load and none holds a control character.
- Given each edited test-case line, when read, then it names a source that exists at `9aee2bf`.
- Given each text-only edit, when its new reader runs in the container, then request and output are recorded in the check run folder (first line of `query_tree_summary`, `pgrep`, `RemInt`, TC-11-18 `Next` activation with one capture of the golden in front, TC-12-05 tree-line compare).

## Implementation Notes

Implemented directly by the builder (no dispatch subagent): short edits to nine items, each tied to a live container check.

Design line per Then change (AC map):

| Item | Line changed | Design or source line that proves it |
|------|--------------|--------------------------------------|
| TC-02-02, -05, -14 | `:106`, `:232`-`:239`, `:583`-`:585` | `mcp-tools-design.md` §1.3 (`query_tree_summary` is text-only: `<STATUS>: <text>` line, no `structuredContent`); `usecases/queries.py:46-48` |
| TC-11-18 | new When `And` before the Then block | spine AD-31 (bridge never activates another document's view); same wording as `TC-09:403` |
| TC-12-05 | `:329`, `:331`, `:332` | `mcp-tools-design.md` §1.3 (line format); spine AD-32 (`ratio` measures the visible objects); live: ratio 0.95 vs 0.54 |
| TC-06-01 | Cleanup | `docs/references/FreeCAD/src/Base/ParameterPy.cpp:242` (`RemInt`) |
| TC-08-17 | `:680` | PartDesign `ViewProvider.cpp:279-296`: making one Body feature visible hides every other feature, so the carve-out runs on the tip `Fillet` and the Body's `v`/`-` tree marks must match before and after |
| TC-09-01 | `:46` | `bootstrap.py:240` proxy args; `run_mcp_e2e.py:77-98` H1 args (`run_mcp_edge_cases.py` imports `server_parameters` from it) |
| `tc-08-04.json` | `:487` | JSON escape: a JSON string needs a doubled backslash to carry the regex word boundary |

AC 3 check: the cited design and spine lines, `queries.py`, `bootstrap.py`, `run_mcp_e2e.py` and `ParameterPy.cpp:242` exist on disk; tracked paths are unchanged since `9aee2bf` (`git diff 9aee2bf -- src scripts` is empty).

Live record: `tests/uat/run/2026-11-18-10-8-f-check/` (`README.md`, `readers-check.md`, `runner/`, `evidence/`). `tc-08-04.json`: 0 FAIL. Pytest 182 passed, ruff clean, 72 scenarios validate.

The TC-11-18 visual Then still says "identical". The closing image holds the same 3D view, but it also shows the `tc11-18` tab and tree entry until Cleanup. The new step says the comparison is of the 3D view and the golden tree entry.

## Spec Change Log

## Review Triage Log

Round 1 lenses: Blind Hunter B1-B11, Edge Case Hunter E1-E11, Verification Gap G1.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| B1, E1, E2 | TC-09-01 `pgrep` misses `serve --transport stdio --mode inline` order and the worker | medium | `TC-01:83` uses `hosts.main serve --transport stdio\|hosts.headless.worker`; `entry.py:43` worker module | patch: pattern covers both orders and the worker; positive test with a fake `exec -a` process printed 2, then 0 |
| B2, E5, E6 | "first line" in my new readers contradicts unchanged `path:` / "second line" Thens (`OK:` line is first) | medium | `_plain_text` puts `OK:` first; the `path:` Thens predate this slice | patch: my readers say "the `OK:` line"; the pre-existing `path:` wording is deferred |
| B3, E3, E4 | whole-text comparisons in TC-02-05 `:237`, `:239` and TC-02-14 `:584` include header lines | medium | `framing:` varies between calls (`computed` vs `cached`) | patch: compare tree lines below the header lines |
| B4 | TC-12-05 "live flag" Then now passes on the `framing:` ratio alone | low | ratio 0.95 vs 0.54 in `readers-check.md` | patch: the `<ObjectB>` tree line must differ |
| B5, E8, E9 | TC-11-18 visual Then says "identical" while the `tc11-18` tab stays; `Next` step has no limit | medium | `after.png` shows the extra tab and entry; sequence needed two presses because the `Start` tab is in the cycle | patch: Then states the tab and entry are not a difference; step bounded at one press per tab, else NOT RUN |
| B6, E10, E11 | TC-08-17 restore points to a read no step makes; no live check | medium | no Given reads `Visibility` | patch: step reads `structured_content.properties.Visibility` first (`queries.py:554-562` returns every property); source-verified, not run live |
| B7 | spec holds a literal backspace byte in the AC map | low | `od -c` | patch: reworded |
| B8 | plan says the check run is not committed; this diff adds it | low | leader condition (b) requires the records in that folder | reject: leader's instruction governs; flagged in the report |
| B9 | spec counts and Code Map text disagree with the diff | low | "ten edits", "question above" | patch for non-frozen text; the frozen "eight defects" stays (fix edits the frozen block) |
| B10 | AC 2 and AC 3 have no verification command | medium | no control-character scan | patch: scan added to Verification |
| B11 | `mcp-tools-design.md:249` says `structured_content` carries counts and the client gets `content[1]`; §1.3 says text-only | medium | design edit is outside the slice boundary | defer: DW entry |
| G1 | no committed test rejects a control character in a scenario `regex` | medium | `scenario.py:180-184` only compiles the regex | defer: the intent forbids runner code edits; DW entry |
| carried B2 | `path:` / "second line" Thens at TC-02-05 `:234-235`, TC-02-14 `:583`, `:585` read the tree text lines, not the response lines | low | predates this slice | defer: DW entry |

Round 3 lenses: Blind Hunter 13, Edge Case Hunter 7, Verification Gap 0. Patched: TC-08-17 writes the opposite of `<V0>` (a hidden Pad would make the carve-out write the current value); TC-12-05 header definition names the blank line; TC-02-14 `:584` points to the TC-02-05 definition; the deferred entry cites `:313` and the `<M>` label at `:314`; the scan test walks every string; run-folder notes made current; Verification names the six edited files. Rejected: reviewer ask for live `depth: 5` and repeat-call records of TC-02-14 (low; the same tree-line equality is recorded for the filters), `pgrep` default-flag order (a plain `serve` has a worker child, which the pattern names), citations inside each test-case line (the AC map is the required form), intent versus the new test (the Tasks list names it; the leader's boundary excludes only `src/`, runner code and container files).

Round 2 lenses: Blind Hunter B'1-B'11, Edge Case Hunter E'1-E'8, Verification Gap G'1. Review loop iteration 1.

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| B'1, E'5 | the control-character scan reads raw JSON, where a bad escape is two ASCII characters | high | baseline file scans clean raw, offends decoded | patch: replaced by a pytest case that decodes first; baseline regex offends (a backspace on each side of `Fillet`), fixed file passes; suite 182 passed |
| B'2, G'1 | no automated check for the regex defect class | medium | `scenario.py:180-184` only compiles | patch (test only; runner code stays untouched); runner reject stays in the deferred entry |
| B'3 | same reader defect left in TC-09 `:313`, `:314` and TC-12 `:659`, `:660` | medium | `shown`, `truncated`, `matches` read as fields of a text-only tool | fixed in F1 (`19473e4`): readers rewritten, live record in `readers-check.md` |
| B'4, deferred wording | TC-02-14 `:583` says the result "starts `path:`" next to an `OK:` line I wrote; the DW entry cites `:235` | medium | `:235` is the unknown-focus Then | patch: `:234`, `:583`, `:585` name the tree text below the header lines; the DW entry removed |
| B'5, E'2 | "tree lines = everything below the framing line" is wrong with `path:`, a cap steering line or no `framing:` line | medium | `queries.py:367`, `tree_text.py` steering line, `mcp_server.py:136` | patch: `:232` names the excluded lines |
| B'6, E'1, E'6 | TC-08-17: read is in the same sentence after the call; restore may match the current value; no live run | medium | grader order; restore of `<V0>` is the fix | patch: the read is the first step and records `<V0>`; live run recorded |
| B'7, B'11 | `readers-check.md` lacks the AND-stack tree lines, the Body/Pad fixture and the nested `App::Part` fixture | medium | AND-stack block shows only the `OK:` line | patch: second live session recorded |
| B'8 | spec front matter (`dispatch`), frozen "eight", log round count | low | counts only | reject: the fix edits the frozen block; flagged to the leader |
| B'9, E'8 | TC-11-18 title says "identical" while the tab differs; long When sentence | medium / low | `after.png` | patch: Then title names the 3D view and the golden tree entry; the sentence length is left (low, no named harm) |
| B'10 | TC-12-05 `:329` cites §1.3 for a ratio change it does not state | low | §1.3 gives only the format | patch: cites spine AD-32 as well |
| B'12 | Code Map cites `run_mcp_e2e.py` for TC-09-01, which runs the edge sweep | low | import in `run_mcp_edge_cases.py:27-39` | patch: Code Map names the import |
| E'3 | `:239` requires the line to end `, 0 matches.` | low | an `Errors:` or `truncated` suffix breaks it | patch: `containing `, 0 matches`` |
| E'4 | `:237` dropped the equal-`matches` check of the old whole-text compare | low | | patch: the Then says the same `<M> matches` count |
| E'7, G' | AC map missed `:584` | low | | patch |
| G' note | `pgrep` exit 1 on count 0 | false | the Given reads the printed `0`, not the exit code | reject |

## Verification

**Commands:**
- `uv run pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q` -- expected: all pass
- `uv run ruff check .` -- expected: no finding
- `grep -n '^\*\*\(Given\|When\|Then\|And\)\*\*' <the six edited TC files> | grep -v '  $'` -- expected: no output (TC-15 has wrapped lines that predate this slice)

**Manual checks:**
- Read each capture of the container run of `tc-08-04.json`.
- The pytest case `test_Should_hold_no_control_character_in_a_string_When_the_committed_scenarios_are_decoded` rejects a control character in any string of any committed scenario. It decodes the JSON first, so it catches the baseline `tc-08-04.json` regex (checked: the baseline decodes to a backspace around `Fillet`).

## Fix round F2

- F2-1 (TC-08-17 `:680`): the carve-out moved from `Pad` to the tip `Fillet`; the Body's tree marks must be equal before and after. Live proof (scratch Body/Sketch/Pad/Fillet): tree lines equal before and after, captures `evidence/tc-08-17-before.png` and `-after.png` read and equal.
- F2-2: TC-09 `:313` and TC-12 `:659` say the `OK:` line contains `, truncated`.
- F2-3: the control-character guard covers every Unicode `Cc` character (DEL and C1 included) and dict keys; four parametrized cases prove it flags a bad file.
- F2-4: the deferred entries state the blocker.
- Left as written (pre-existing wording, not changed by this story): TC-09 port check for H1, tree-line count, 201 lines when capped, filter `shown` versus depth 3. TC-08-17 order of the carve-out against the previewed sample (RT-1 second point, low) is also left.
