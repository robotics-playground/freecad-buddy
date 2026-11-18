# Story 10-8-f: red team report

Scope: diff `9aee2bf...19473e4` on `story/10-8-f-uat-testcase-defects`. Method: `bmad-code-review` lenses run by one agent (blind, edge case, acceptance), then live reproduction. Work copy: detached worktree at `19473e4` (removed). Container `fcb-desktop` used after the leader handed it over: FreeCAD started (pid 2550), one scratch document `rt1008f`, closed, FreeCAD stopped (`fcb-freecad status`: no pid).

Verdict: **FAIL**. Counts: high 0, medium 1, low 0 reproduced; 6 low not reproduced or reproduced only as format facts.

## Reproduced

### RT-1 — medium — Q6 — TC-08-17 carve-out restore leaves the Fillet hidden

File: `tests/uat/testcases/TC-08-preview-confirm-and-undo.md:680` (the display-state carve-out Then).

Text at `19473e4`:

> first read `structured_content.properties.Visibility` of `mcp query_object { doc: <handle>, object: "Pad" }` and record it as `<V0>`; then `mcp feature_set_parameters { ..., feature: "Pad", parameters: { Visibility: <the opposite of <V0>> } }` ... restore `<V0>` with `{ Visibility: <V0> }` ... before the after-capture

Cause. FreeCAD's PartDesign view provider hides every other PartDesign feature of the Body when one feature becomes visible. `docs/references/FreeCAD/src/Mod/PartDesign/Gui/ViewProvider.cpp:279-296`:

```cpp
if (prop == &Visibility && Visibility.getValue()) {
    ...
    // hide all features in the body other than this object
    for (App::DocumentObject* obj : body->Group.getValues()) {
        if (obj->isDerivedFrom<PartDesign::Feature>() && obj != getObject()) {
            ...
            if (vpd && vpd->Visibility.getValue()) {
                vpd->Visibility.setValue(false);
```

The TC-08-17 Given holds Body, Sketch, Pad and Fillet. With the Fillet as tip, the Pad is hidden, so `<V0>` is `false`. That is the case the R1-B6 fix was written for. The carve-out call writes `true`: the Pad shows and FreeCAD hides the Fillet. The restore writes `false`: the Pad hides again, and nothing shows the Fillet again. No solid is visible after the restore. The after-capture then differs from the before-capture (filleted solid gone), so the "visually IDENTICAL" Then fails on a correct product. If the Sketch is hidden too, the closing `view_fit_viewport` can also return `SPEC_FAILED view_fit.nothing_to_frame`.

Reproduction (container `fcb-desktop`, FreeCAD 1.1.4 pid 2550, MCP server `freecad-buddy-docker`):

1. `document_create { label: "rt1008f" }`. `script_exec` builds Body, a fully constrained 20 x 20 `Sketch`, `Pad` (10 mm) and `Fillet` (Edge1, r 2) in one transaction. Result: `{'Sketch': (True, True, True), 'Pad': (False, False, True), 'Fillet': (True, True, True)}, 'Fillet', 0` (object Visibility, view-provider Visibility, valid; tip; sketch DoF).
2. `query_object { object: "Pad" }`: `"Visibility":false`, so `<V0>` = `false`.
   `query_tree_summary { focus: "Body" }`:
   ```
   |-- - [PAD] Pad (+1)
   `-- v [FILLET] Fillet *tip
   ```
3. `feature_set_parameters { feature: "Pad", parameters: { Visibility: true } }`: `status OK`, `"changed":[]`, `Mutation committed`. Tree:
   ```
   |-- v [PAD] Pad (+1)
   `-- - [FILLET] Fillet *tip
   ```
4. `feature_set_parameters { feature: "Pad", parameters: { Visibility: false } }` (restore `<V0>`): `status OK`, `"changed":[]`. Tree:
   ```
   |-- - [PAD] Pad (+1)
   `-- - [FILLET] Fillet *tip
   ```
5. `script_exec` reads App and GUI visibility: `{'Sketch': (True, True), 'Pad': (False, False), 'Fillet': (False, False)}`.

Before step 3 the Fillet was visible; after step 4 it is hidden. The text restores only the Pad, so the window is not identical to `tc-08-17-before.png`. The product is correct: the carve-out returned `OK`, `changed: []`, no confirm. The builder's live check (`tests/uat/run/2026-11-18-10-8-f-check/readers-check.md`, "TC-08-17 carve-out, live") used a Body with a Pad and no Fillet, where `<V0>` was `true`. So that check did not cover the `<V0>` = `false` path.

Fix direction (for the builder, not applied): carve out on an object that does not trigger the Body rule, or record the Visibility of every PartDesign feature in the Body (at least `Fillet`) before the carve-out and restore all of them, restoring the tip last; or run the carve-out on the tip (`Fillet`, `<V0>` = `true`): writing `false` hides only the Fillet, and writing `true` back hides the other features, which are already hidden.

A second point on the same Then (text order, not reproduced live): the Then is listed after "each refused tool works once previewed", but it says "before the after-capture", and the visual Then says the after-capture is taken "immediately after the 19 refused calls and BEFORE the previewed sample". The only order that meets both is: 19 refusals, carve-out and restore, fit, after-capture, previewed sample. The text does not say that order. A tester who runs the Thens in listed order runs the carve-out after the previewed sample and after the capture. This wording was there before this Story ("restore with `{ Visibility: true }` before the after-capture"), so it is low.

## Not reproduced (low)

- RT-L1, Q1 and TC-12 `:659`, TC-09 `:313`: with an errored object in the start subtree the `OK:` line ends `, truncated. Errors: <Name>: <status>`, not `, truncated.`. Format check on `summarize_tree` (`usecases/queries.py:46-53`): `OK: 250 objects, 200 shown, truncated. Errors: B007: Invalid`. TC-12-11 "the `OK:` line ends `, truncated.`" then fails on a correct product; TC-09 "`, truncated` before the final period" fails when the status text ends in a period (`... Errors: Pad: Shape is null.`). No fixture in these scenarios is known to carry an error (TC-09-07 uses the 1-object `box40-hole-r5`), so no live false fail.
- RT-L2, Q4: the new pytest guard (`tests/external/test_uat_runner.py`, `_strings_of`) checks only code points below 32. It skips DEL (`\x7f`), C1 controls (`\x80`-`\x9f`) and dict keys. Check: a decoded `"\x7fFillet\u0085"` gives `guard flags it: False`. Scan of all 72 scenario files: no such character today; only `code` strings (`\n`) and `tc-04-18` regexes (escaped newline) carry control characters, both intended. The guard reads files the same way as `scenario.load` (`json.loads(path.read_text(encoding="utf-8"))`, `*.json` glob), so it skips no real loader path.
- RT-L3, Q7: the TC-09-01 Given `pgrep` pattern holds for the real launch lines: `run_mcp_e2e.py:90-99` runs `fcb-py -m freecad_buddy.hosts.main serve --mode inline --transport stdio`, `fcb-py` ends `exec /opt/freecad/AppRun python "$@"`, and the worker is `sys.executable -m freecad_buddy.hosts.headless.worker` (`hosts/headless/entry.py:178-179`), which the third branch counts even for the console script `freecad-buddy serve`. Remaining gap outside the diff: the TC-09 Preconditions line "No stale H1 server holding the fixtures (verify: `ss -ltnp | grep :8765` ...)" still checks a port; an H1 server is stdio and holds no port.
- RT-L4, TC-09 `:314`, `:358`, `:475`: "`<S> shown` equals the number of tree lines" — TC-09 does not define "tree lines"; TC-02-05 `:232` does. A tester who counts the `framing:` line gets 2 lines for `1 shown` on the box. Wording existed before this Story.
- RT-L5, TC-12 `:659`: "at most 200 tree lines; when the cap cuts it ... the last tree line is `... <K> more lines ...`" counts the steering line as a tree line, so a capped result has 201 tree lines. TC-02-05 `:232` excludes the steering line. Wording existed before this Story.
- RT-L6, TC-12 `:660`: "the `<S> shown` of each [filtered call] is smaller than that of the depth-3 call" fails on a correct product when depth 3 is capped at 200 and a filter reveals 200 or more lines (both `200 shown`). Not reachable with a 50-feature Body (about 109 lines at depth 3). Wording existed before this Story.

## Rows with no finding

- Q1, Q3 (TC-02-02, TC-02-05, TC-02-14, TC-12-05): `_plain_text` (`adapters/mcp_server.py:127-138`) puts `OK:` first, then the `Warning:` sentence with its blank line (`contracts/envelope.py:116-124`), then `framing:`, then the `path:` line and tree. The new tree-line definitions name each header. The new Thens are stricter than before: the old "post-toggle result differs" passed on a `framing:` ratio change alone, and the old "same text" for `types` failed on `cached` versus `computed` in the `framing:` line. `, 0 matches` cannot match inside `, 10 matches`.
- Q2 (TC-11-18): QMdiArea creation order with Start, golden, `tc11-18` matches the record (first `Next` lands on Start, second on the golden). The press bound (once per tab) covers at most N-1 presses.
- Q4 (tc-08-04): `"\\bFillet\\b"` decodes to `\bFillet\b`; runner check record shows the explanation `recompute left 1 object(s) invalid: Fillet: BRep_API: command not done` matching.
- Q5: `RemInt` exists, `RemoveInt` does not (record in `readers-check.md`; `ParameterPy.cpp:242`).
- Q9: in the worktree, `uv run pytest tests/external/test_uat_runner.py tests/external/test_uat_runner_container.py -q` gives `182 passed`; `uv run ruff check .` gives `All checks passed!` (after `uv sync --extra dev`; without the extra, `uv run pytest` takes the global Python 3.13 pytest and fails collection on `mcp.client.streamable_http`: environment, not the Story).
- Q10: `git diff --stat 9aee2bf 19473e4` shows no `src/`, runner code, container file or earlier run folder.
