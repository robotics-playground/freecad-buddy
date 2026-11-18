# Verify report: Story 10-8-f (known UAT test-case defects)

Verifier: verifier-10-8-f. SHA tested: `19473e4` (branch `story/10-8-f-uat-testcase-defects`), base `9aee2bf`. Date 2026-11-18.

**Verdict: PASS.** All gates are green. Both mutants turn the new test red. Every Q1-Q10 row maps to a check. Four live checks in the container pass. No Then hides a product defect. No product defect found. No test-case fix was needed, so this report has no commit.

Terms: a *Then* is an assertion line of a test case. A *reader* is the part of a Then that says where the value is read. `query_tree_summary` is a *text-only* tool: it returns one plain text block (`OK: <N> objects, <S> shown[, <M> matches].` line, optional `Warning:` sentence, optional `framing:` line, then the tree), with no `structuredContent` (`mcp-tools-design.md:60`). *H1* is the headless stdio MCP host. The *GUI proxy* is the MCP HTTP process that the addon starts.

## 1. Gates at `19473e4`

| Command | Result |
|---------|--------|
| `uv run pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q` | `182 passed in 3.63s` |
| `uv run ruff check .` | `All checks passed!` |
| Runner validate: `scenario.load_all(['../scenarios'])` from `tests/uat/runner/` (the step `run.py:566` runs before preflight; there is no validate-only flag) | `loaded 72`, no `ScenarioError` |
| Decoded scan of all 72 scenario files for characters below 32 | 0 offenders |
| GWT hard-break check on the six edited TC files (`grep ... \| grep -v '  $'`) | no output |
| `git diff --stat 9aee2bf 19473e4 -- src tests/uat/runner tests/close-loop scripts addon` | empty (0 lines) |
| Run folders in the diff | only the new `2026-11-18-10-8-f-check`; no earlier run folder |
| Scenario files in the diff | only `tests/uat/scenarios/tc-08-04.json` |

## 2. Falsification

Worktree `D:\Work\Personal\Sources\fcb-verify-10-8-f` at `19473e4` (detached), tests run with the main repo `.venv` Python; the test resolves `SCENARIO_DIR` from its own file (`test_uat_runner.py:23`), so it read the worktree files. Worktree removed after the run (`git worktree list` no longer shows it).

Target: `test_Should_hold_no_control_character_in_a_string_When_the_committed_scenarios_are_decoded` (`tests/external/test_uat_runner.py:1232`).

| Run | Mutation | Result |
|-----|----------|--------|
| Baseline | none | `1 passed` |
| Mutant 1 | `tc-08-04.json:487` back to `"regex": "\bFillet\b"` | `1 failed`: `AssertionError: assert [('tc-08-04.j...8Fillet\x08')] == []` |
| Mutant 1, runner validate | same | `load_all` still loads 72: the runner accepts the bad regex. This confirms the deferred entry (runner code is out of scope) |
| Mutant 2 | `tc-02-02.json:75` regex `"^OK: 1 objects, 1 shown\\."` to `"^OK: 1 objects,\f1 shown\\."` (a form feed, different file, different escape) | `1 failed`: `Left contains one more item: ('tc-02-02.json', '^OK: 1 objects,\x0c1 shown\\.')` |
| Restored | both files checked out | `1 passed` |

Limit: the test allows `\n`, `\r` and `\t` (`test_uat_runner.py:45`). A `\t` or `\n` escape written by mistake inside a regex is not caught. Low; no committed scenario needs a different rule today.

## 3. AC map (quality bar Q1-Q10)

| Q | Criterion | Change at `19473e4` | Design line re-read | Check | Result |
|---|-----------|---------------------|---------------------|-------|--------|
| Q1 | TC-02-02, -05, -14 read counts from the `OK:` line | `TC-02:106`, `:232`, `:233`, `:234`, `:237`, `:239`, `:583`, `:584`, `:585` | `mcp-tools-design.md:60` (text-only, `<STATUS>: <text>` line first, no `structuredContent`); `usecases/queries.py:46-48` (`head = f"{...} objects, {...} shown"`, `+= f", {sc['matches']} matches"`); `adapters/mcp_server.py:133` (`lines = [f"{body.get('status')}: ..."]`) | Live, section 4.2 | PASS |
| Q2 | TC-11-18 brings the golden view to the front before the closing fit | `TC-11:874` new `And` (`Next` leaf of `Windows`, at most once per tab, else NOT RUN); `:885` visual Then | Spine AD-31 (fit refused when another document's view is in front; spine lines 269-271); same route as `TC-09:403` | Text review; builder captures not re-run by me | PASS with note (section 5, N1) |
| Q3 | TC-12-05 compares tree lines only | `TC-12:329`, `:331`, `:332` | `mcp-tools-design.md:60` (line order), `:282` (`text` format); spine AD-32 (`ratio` measures visible shape-bearing objects, spine line 277) | Live framing line changes between identical reads (section 4.2: `computed` then `cached, served from cache; ...`), so header exclusion is needed; `:332` now needs the `<ObjectB>` tree line to differ | PASS |
| Q4 | `tc-08-04.json` regex is `\\bFillet\\b`; no control character in 72 files | `tc-08-04.json:487` | JSON escape rule | Runner run in container (section 4.4); decoded scan (section 1); pytest case plus two mutants (section 2) | PASS |
| Q5 | TC-06-01 Cleanup uses `RemInt` | `TC-06:131` | `docs/references/FreeCAD/src/Base/ParameterPy.cpp:242` `add_varargs_method("RemInt", &ParameterGrpPy::remInt, "RemInt()")` | Live, section 4.3 | PASS |
| Q6 | TC-08-17 restores the Visibility value read before | `TC-08:680` (read `<V0>`, write the opposite, restore `<V0>`) | no design change; stronger than before | Text review | PASS |
| Q7 | TC-09-01 Given counts no H1 process; proxy not counted | `TC-09:46` | `hosts/gui_addon/bootstrap.py:240` `_SERVE_ARGS = [..., "serve", "--mode", "rpc", "--transport", "http"]`; `scripts/automation/run_mcp_e2e.py:94-99` (`serve --mode inline --transport stdio`); `hosts/headless/entry.py:43` `_WORKER_MODULE = "freecad_buddy.hosts.headless.worker"` | Live, section 4.1 (0 with proxy, 3 with fakes, 0 after) | PASS |
| Q8 | No Then weakened to hide a product defect | all changed Thens | decision 23, 38, 40 | Diff review, section 5 | PASS |
| Q9 | Runner tests, lint, 72 files load | — | — | Section 1 | PASS |
| Q10 | No edit to `src/`, runner code, container files, earlier run folder | — | — | Section 1 | PASS |

The F1 fix round also changed `TC-09:313`, `:314`, `:358`, `:475` and `TC-12:659`, `:660` (decision 40). I re-read each against `queries.py:46-53`: `<S> shown` and `, truncated` before the period are the code form. PASS.

## 4. Live checks (UAT level, container `fcb-desktop`)

Image `fcb-desktop:local` = `sha256:ccccd43b5b3df8ee1eaaf547643570184c90099415298be0b98bd6cc103dddc4`, built 2026-11-17T17:06:28Z. `git log --since` that time `-- src` is empty, and the slice has no `src/` change, so no rebuild. FreeCAD 1.1.4. Records: `tests/uat/run/2026-11-18-10-8-f-verify/` (`live-checks.md`, `evidence/`, `runner/`, `runner-console.txt`). I did not read the builder's run folder before these checks.

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| 4.1 | TC-09-01 `pgrep` Given with the GUI proxy up | PASS. Proxy pid 2072 runs `serve --mode rpc --transport http`; the Given prints `0`. Positive control: 3 fake H1-named processes (both flag orders and the worker) print `3`; after `pkill`, `0` | `evidence/tc-09-01-pgrep.txt` |
| 4.2 | TC-02-05 `OK:` line reader (8 calls of the When, Body/Sketch/Pad fixture) | PASS. `depth: 1` `OK: 11 objects, 1 shown.` with 1 tree line; `depth: 3` 11 shown; focus starts `path: Body`; `types` PAD and TypeId both `2 shown, 1 matches` with equal tree lines; AND-stack `1 shown, 0 matches` with the depth-1 tree line | `live-checks.md` table; capture `evidence/tc-02-05-fixture.png` read |
| 4.3 | TC-06-01 `RemInt` Cleanup | PASS. `SetInt(...,2)` then `RemInt('AntiAliasing')`: key gone from `GetInts()`, `GetInt` returns `-1`; `hasattr(p,'RemoveInt')` is `False` (old line raised). Key absent before and after | `live-checks.md` |
| 4.4 | tc-08-04 runner scenario | PASS for the slice. Exit 0, `0 PASS, 0 FAIL, 1 ESCALATE`, `run errors: 0`, `findings: []`. Explanation `recompute left 1 object(s) invalid: Fillet: BRep_API: command not done` matches `\bFillet\b`. ESCALATE comes only from the scenario's `agent_check` | `runner/summary.md`, `runner/results.json`, capture `runner/captures/TC-08-04.png` read: one framed pad, sharp edges, no error colouring, tree `TC0804` > `Body`, no dialog |
| 4.4b | tc-08-04 `agent_check` before/after compare | NOT RUN: the runner takes no before capture. This is gate-run work, not part of this slice | — |

Command note: from Git Bash the runner command needs `MSYS_NO_PATHCONV=1`; without it the first try failed with `can't open file '/home/cua/C:/Program Files/Git/repo/...'` and ran nothing. The README form is correct for a POSIX shell.

## 5. Q8 review: no weakened Then

Each changed Then, before and after:

- `TC-02:106`: `structured_content.total_objects is 1 and shown is 1` (could never pass: no `structuredContent`) -> `OK: 1 objects, 1 shown.`. Same values.
- `TC-02:232-239`, `:583-585`: whole-text compares -> tree-line compares plus the same counts. The excluded header lines are the `OK:` line (its counts are checked separately), the `Warning:` sentence and the `framing:` line, which changes between identical calls (section 4.2). Not weaker.
- `TC-09:46`: "no `hosts.main` process" (always failed while the GUI proxy runs) -> a pattern that counts H1 fronts and workers only. Positive control shows it still detects H1.
- `TC-09:313`, `:314`, `:358`, `:475`, `TC-12:659`, `:660`: reader moved to the `OK:` line; same quantities.
- `TC-12:329`, `:331`: framing line excluded (designed to change with the visible set, AD-32). `TC-12:332`: was satisfiable by the ratio change alone; now the `<ObjectB>` line must differ. Stronger.
- `TC-08:680`: stronger (the carve-out call now always writes a change).
- `TC-11:885`: scope narrowed from "the window" to "the 3D view and the `box-10-20-30` tree entry". The `tc11-18` tab exists because the scenario creates that document and closes it in Cleanup, by design; the Then still catches a new object in the golden view. Leader decision 40 accepted it.

No changed Then covers a product defect. The original failures were test-text defects (wrong reader, JSON escape, wrong method name, wrong process pattern, wrong active view).

## 6. Deferred-work entries added by this slice

`deferred-work.md:1937-1943`:

| Entry | Blocker | Unblock condition |
|-------|---------|-------------------|
| `scenario.py` accepts a control character in a regex | Stated by implication: "the runner still accepts such a regex", and the slice may not edit runner code (spec Never list; decision 40) | "a story that may edit runner code adds the reject in `scenario.py`" |
| `mcp-tools-design.md:249` contradicts §1.3 | Stated by implication: a design edit is outside the slice | "epic-10 close correct-course batch" |

Both name an unblock condition. Neither entry states its blocker in a separate sentence (N2).

## 7. Notes (not blocking)

- N1: Q2 says the TC-11-18 visual Then "stays identical"; the line now limits "identical" to the 3D view and the golden tree entry. Decision 40 accepts this. I did not re-run TC-11-18 live (not in my task list); the builder's captures exist at `tests/uat/run/2026-11-18-10-8-f-check/evidence/`.
- N2: the two deferred entries give the blocker only by implication. One clause each ("blocked: the slice may not edit runner code" / "blocked: design edits are outside the slice") would make them complete.
- N3: the spec triage row B'3 still says "defer: DW entry", but fix round F1 fixed those lines and removed the entry. The build report says so; the spec log is out of date.
- N4: `TC-12:659` says the `OK:` line "ends `, truncated.`". When an object is in error, `queries.py:52` appends ` Errors: ...` after the period, so the line does not end there. `TC-09:313` has the same limit ("before the final period"). Low: the TC-12-14 and TC-09-07 fixtures have no errored object.
- N5: the new pytest case allows `\t` in a string (section 2, limit).

## 8. Clean state

Container FreeCAD stopped (`fcb-freecad status`: no pid, healthz unreachable). Fake `pgrep` control processes killed (no match left). Document `verify1085` closed before stop. Worktree `fcb-verify-10-8-f` removed. No temp files outside the run folder. The run folder `tests/uat/run/2026-11-18-10-8-f-verify/` and this report are uncommitted. I did not touch `D:\Work\Personal\Sources\fcb-redteam-10-8-f` (a different agent's worktree), `fcb-10-8-e`, `fcb-canary-10-8-e` or host `:8765`.

## Re-run at a61c315

Fix round F2, base `19473e4`, head `a61c315` (one commit). Findings under test: RT-1, V-1, RT-low2, V-2 (`review-ledger-10-8-f.md`). **Verdict: PASS.** RT-1 is fixed and proven live. The guard now catches DEL, C1 characters and dict keys. The text fixes hold. The carve-out order wording that was left unchanged can give a false fail, not a false pass (R4).

### R1. Gates (worktree `fcb-verify-10-8-f` at `a61c315`, main `.venv` Python; worktree removed)

| Command | Result |
|---------|--------|
| `pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q` | `186 passed in 4.03s` (182 + 4 parametrized cases); matches the builder's claim |
| `ruff check .` | `All checks passed!` |
| `scenario.load_all(['../scenarios'])` | `loaded 72` |
| `git diff --stat 19473e4 a61c315` | test text, `test_uat_runner.py`, spec, `deferred-work.md`, check run folder; no `src/`, runner code or container file |

### R2. F2-3 guard mutants (worktree copy, each restored with `git checkout`)

Target: `test_Should_hold_no_control_character_in_a_string_When_the_committed_scenarios_are_decoded`.

| Mutant in `tc-02-01.json` | Result |
|---------------------------|--------|
| DEL: `"label": "uat-round\u007ftrip"` | `1 failed`: `Left contains one more item: ('tc-02-01.json', 'uat-round\x7ftrip')` |
| C1: `"regex": "^fcb\u009b-doc:"` | `1 failed`: `('tc-02-01.json', '^fcb\x9b-doc:')` |
| Bad dict key: `"la\bbel": "uat-roundtrip"` | `1 failed`: `('tc-02-01.json', 'la\x08bel')`. The runner validate still loads all 72 with this key (runner gap stays in the deferred entry) |
| All restored | `1 passed` |

The guard uses `unicodedata.category(...) == "Cc"` and yields dict keys (`test_uat_runner.py`, `_strings_of`). `\n`, `\r`, `\t` are still allowed (N5 stays, low).

### R3. F2-1 live: TC-08-17 carve-out on the tip `Fillet`

Container `fcb-desktop`, FreeCAD 1.1.4 pid 2972, started with `docker exec -e FREECAD_BUDDY_AUTO_APPROVE=0 -u cua fcb-desktop fcb-freecad start`. `addon.log` for that launch: `FREECAD_BUDDY_AUTO_APPROVE='0' (env)` and no `SECURITY: mutation auto-approve ENABLED` line, so the gate is on as the TC-08-17 Given requires.

Fixture `vr1708` (`script_exec`, one transaction): Body, fully constrained 20 x 20 `Sketch` (DoF 0), `Pad` 10 mm, `Fillet` on `Edge1` r 2. State: `{'Sketch': (True, True, True), 'Pad': (False, False, True), 'Fillet': (True, True, True)}`, tip `Fillet` (same state as the red team's reproduction).

Sequence as the new `TC-08:680` text says:

1. `view_fit_viewport` OK (ratio 0.95); capture `evidence/tc-08-17-before.png`.
2. `query_tree_summary { depth: 4 }`: Body block ends `|-- - [PAD] Pad`, `|   `-- v [SKETCH] Sketch`, `` `-- v [FILLET] Fillet *tip ``.
3. `query_object Fillet`: `"Visibility":true`, so `<V0>` = `true`.
4. `feature_set_parameters { feature: "Fillet", parameters: { Visibility: false } }`, no confirm: `status OK`, `changed: []`, fingerprint unchanged (`e145e759...` before and after). Tree: Pad `-`, Sketch `v`, Fillet `-`.
5. Restore `{ Visibility: true }` on `Fillet`: `status OK`, `changed: []`. Tree at `depth: 4`: all 12 lines equal to step 2 (same `v`/`-` marks).
6. Audit: two `approval` lines with `"mode": "display_state"`, `"tool": "feature_set_parameters"`.
7. `view_fit_viewport` OK; capture `evidence/tc-08-17-after.png`.

Captures read: both show one 20 x 20 x 10 block in isometric view with one rounded vertical edge (left), the sketch outline at the base, tree `vr1708` > `Body`, no dialog. Pixel compare (PIL `ImageChops.difference`): bbox `None`, so the images are identical. RT-1 is closed: the restore brings back the same visible state.

Neighbouring Thens checked in the same session:

- Refusal message: `feature_set_parameters { Fillet, Radius 4 mm }` with no confirm returns `INVALID_INPUT`, `this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id` (`:674` holds).
- Previewed sample (`:679`): `preview_dry_run` for the same call returns OK with a `preview_id`; the call with `confirm.preview_id` returns OK, `changed` Body and Fillet, volume 3991.42 -> 3965.66. The Fillet-Radius advice in `:679` holds.
- The carve-out on `Fillet` does not change the "nothing was mutated" Then (`:676`): fingerprint is unchanged across the carve-out.

### R4. "Carve-out order versus previewed sample" (left as written): false fail, not false pass

The text gives two time rules. `:680` says the carve-out and restore run "before the after-capture". `:682` says the after-capture is taken "immediately after the 19 refused calls and BEFORE the previewed sample". The Thens are listed in the order sample (`:679`), carve-out (`:680`), fit (`:681`), capture (`:682`). The only order that meets both rules is: 19 refusals, carve-out and restore, fit, capture, sample. The text does not state it.

- Reading A, a tester runs the listed order and takes the capture last: the sample mutations are in the after-capture. Live: after the confirmed Radius 2 -> 4 sample I took `evidence/tc-08-17-listed-order.png`. Pixel compare with the before image: bbox `(530, 337, 593, 670)`, 16445 changed pixels; read: the rounded edge is clearly larger. The "visually IDENTICAL" Then fails on a correct product. **False fail.** A sample with `feature_pad Pad2` or `sketch_create` gives a larger difference.
- Reading B, a tester takes the capture before the sample (as `:682` says) and runs the carve-out after it: the carve-out runs after the capture. The capture still shows the state right after the 19 refusals, and the carve-out has its own tree-mark check, so nothing is hidden. No false result.
- False pass: not possible from the order. The only way the carve-out could hide something from the image is the PartDesign rule (`ViewProvider.cpp:279-296`): making `Fillet` visible hides other Body features, which could hide a leaked visible feature. A leak would then also change the tree marks (the carve-out Then fails) and the node list (`:676` fails). So the scenario still fails on a gate defect.

Severity low (wording, existed before this Story). Fix, if the leader wants it: one sentence in `:680` such as "run it after the 19 refusals and before the after-capture, so before the previewed sample".

### R5. Text checks F2-2, F2-4

- F2-2: `TC-09:313` now says "`, truncated` in that line"; `TC-12:659` says "the `OK:` line contains `, truncated`". Both hold with the `. Errors: ...` suffix (`queries.py:50-53`). V-1 and RT-low closed.
- F2-4: both `deferred-work.md` entries (`:1937`, `:1941`) now have a `Blocker:` sentence and an `Unblock:` sentence. Spec triage row B'3 (`spec-10-8-f-uat-testcase-defects.md:126`) now says "fixed in F1 (`19473e4`)". V-2 closed.
- `ViewProvider.cpp:279-296` cited in `:680` exists and holds the "hide all features in the body other than this object" loop.

### R6. Clean state

Container FreeCAD stopped (`fcb-freecad status`: no pid). Document `vr1708` closed before stop. Worktree `fcb-verify-10-8-f` removed. New evidence in `tests/uat/run/2026-11-18-10-8-f-verify/evidence/`: `tc-08-17-before.png`, `tc-08-17-after.png`, `tc-08-17-listed-order.png`. Nothing committed.

### R7. Order wording fix (test-case edit by the verifier, on the Story branch working tree)

`TC-08:680` now starts: "run the carve-out and its restore after the 19 refused calls and before the fit and the after-capture below, so before the previewed sample above (a confirmed sample changes the model, and the after-capture must show only the state the refusals left)." The rest of the line is unchanged. This fixes the order to: 19 refusals, carve-out and restore, fit (`:681`), after-capture (`:682`), previewed sample (`:679`).

Evidence:

- Old order (sample before the capture): `evidence/tc-08-17-listed-order.png` differs from `evidence/tc-08-17-before.png` (bbox `(530, 337, 593, 670)`, 16445 pixels, larger rounded edge). False fail on a correct product.
- New order: the capture the new wording takes is `evidence/tc-08-17-after.png` (taken after the carve-out and restore and the fit, before the sample). It equals `evidence/tc-08-17-before.png` (PIL difference bbox `None`), read by eye: same filleted block, same camera, no dialog.

Checks after the edit: `uv run pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q` gives `186 passed`; `uv run ruff check .` gives `All checks passed!`; the GWT hard-break check on the TC-08 file prints nothing. No scenario file mirrors TC-08-17.

Not committed: the user's global rule requires the user's explicit approval for every commit, and a message from an agent is not that approval. The edit is in the working tree of `story/10-8-f-uat-testcase-defects`, ready for a commit `fix(uat): fix the TC-08-17 carve-out order before the after-capture` once the user approves.
