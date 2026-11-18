# Story 10-8-f reader check (not a gate run)

Container `fcb-desktop`, FreeCAD 1.1.4 pid 336, 2026-11-18. Each block is a request and its output; a block marked condensed is shortened by hand. The agent that edited the test cases ran these by hand through the `freecad-buddy-docker` and `cua-driver-docker` MCP servers.

## TC-02-02, TC-02-05, TC-02-14: counts are in the first text line

Request: `query_tree_summary { doc: <golden box-10-20-30> }`
```
OK: 1 objects, 1 shown.
framing: unknown, unavailable, no visible shape-bearing objects to measure
- [FEATURE] Box
```
Request: `query_tree_summary { doc: <two boxes>, filters: { types: ["BOX"] } }`
```
OK: 2 objects, 2 shown, 2 matches.
framing: fits, ratio 0.95, cached, served from cache; unverified key component(s): geometry
v [BOX] ObjectA
v [BOX] ObjectB
```
Request: same, `filters: { types: ["BOX"], name_pattern: "zzz" }`
```
OK: 2 objects, 2 shown, 0 matches.
```
Result: `<S> shown` and `<M> matches` read from the first line; `, 0 matches.` ends the first line of the AND-stack case. Source: `usecases/queries.py:46-48`.

## TC-06-01 Cleanup: `RemInt`

Request: `script_exec`: `p = FreeCAD.ParamGet('User parameter:BaseApp/Preferences/View'); p.SetInt('FcbProbe', 7); a = p.GetInt('FcbProbe', -1); p.RemInt('FcbProbe'); result = (a, p.GetInt('FcbProbe', -1), hasattr(p, 'RemInt'), hasattr(p, 'RemoveInt'))`
Output: `value_repr: (7, -1, True, False)`
Result: `RemInt` removes the key (read back `-1` default); `RemoveInt` does not exist.

## TC-09-01 Given: H1 process count

Request: `docker exec -u cua fcb-desktop sh -c "pgrep -fc 'freecad_buddy.hosts.main serve --mode inl[i]ne'"`
Output: `0` (exit 1, no match). With the GUI proxy running, `ps` shows `... -m freecad_buddy.hosts.main serve --mode rpc --transport http`, which the pattern does not count.

Review round 1 widened the pattern to `'hosts.main serve --transport stdi[o]|hosts.main serve --mode inl[i]ne|hosts.headless.worke[r]'` (either flag order, and the worker). Positive test in `fcb-desktop`: a process started with `exec -a 'python -m freecad_buddy.hosts.main serve --transport stdio --mode inline' sleep 8` made the count 2; after it exited the count was 0.

## TC-11-18: Windows `Next` activation

1. Opened `/repo/benchmarks/g0/golden-models/box-10-20-30.FCStd`; Show All Objects leaf pressed by `element_token`; `view_fit_viewport` OK; capture `evidence/tc-11-18-before.png`.
2. `document_create { label: "tc11-18" }` OK. `list_windows` title: `* tc11-18 - FreeCAD 1.1.4`. `view_fit_viewport { doc: <golden> }` returns INVALID_INPUT: `the live viewport is showing 'tc11_18', not the targeted 'box_10_20_30'` (the defect the new step removes).
3. Pressed the `Next` leaf of the Windows menu by `element_token`. First press: `route: accessibility`, title still `* tc11-18`. Second press (new snapshot, new token): title `* box-10-20-30 - FreeCAD 1.1.4`.
4. `view_fit_viewport { doc: <golden> }` OK. Capture `evidence/tc-11-18-after.png`.

Visual read (agent read both PNGs): the 3D view is the same box, same camera, whole and framed, in both; no dialog. The `after` image also shows the `tc11-18` tree entry and tab, because the document stays open until Cleanup. The new step text says so.

## TC-12-05: compare tree lines

Two boxes `ObjectA`, `ObjectB`, fitted. Visibility of `ObjectB` toggled with `FreeCADGui` (not the tree-row route; this checks the reader, not the toggle route).
```
before:  OK: 2 objects, 2 shown. / framing: fits, ratio 0.95, computed / v [BOX] ObjectA / v [BOX] ObjectB
hidden:  OK: 2 objects, 2 shown. / framing: fits, ratio 0.54, computed / v [BOX] ObjectA / - [BOX] ObjectB
restore: OK: 2 objects, 2 shown. / framing: fits, ratio 0.95, computed / v [BOX] ObjectA / v [BOX] ObjectB
```
Result: the `framing:` line changes with the visible set (0.95 to 0.54); the tree lines differ only in the first character of the `ObjectB` line, and equal the pre-toggle lines after the restore.

## Review round 1: second live session (Body/Pad and App::Part fixtures)

Container FreeCAD restarted (pid 1535). Document `tc02-05-check`: `Body` (11 objects at first) with a fully constrained 20 x 20 `Sketch` and a 10 mm `Pad`, plus `OuterPart` > `InnerPart` > `LinkTarget` and `BoxLink` (App::Link). Outputs are as returned unless marked condensed. The `Body` queries ran on `tc02-05-check`; the `App::Part` queries ran on the same document after the objects were added, so its object count is 31, not 11.

`query_tree_summary { depth: 1 }`, model not fitted:
```
OK: 11 objects, 1 shown.
<blank>
Warning: the model does not fully fit the live viewport, so the human is seeing only part of it. Call view_fit_viewport to fit it, if they need to see this change.
framing: does not fit, computed
v [BODY] Body (+2)
```
Result: a `Warning:` sentence and a blank line sit between `OK:` and `framing:`; the tree-line definition at TC-02 `:232` names them. `<S> shown` is 1 and `Body` ends `(+2)`.

`depth: 3`: `OK: 11 objects, 11 shown.` and 11 tree lines (Body, Origin and 7 children, Pad, Sketch); `shown` equals the tree line count.

After `view_fit_viewport`, `focus: "Body", depth: 2`:
```
OK: 11 objects, 11 shown.
framing: fits, ratio 0.95, computed
path: Body
v [BODY] Body
|-- - [ORIGIN] Origin ... (7 children) ... `-- v [PAD] Pad *tip / `-- v [SKETCH] Sketch
```
Result: `path:` comes after `framing:`, is not counted in `shown`, and the next line is the `[BODY] Body` line.

Filters, same tree lines, same count:
```
types ["PAD"]:            OK: 11 objects, 2 shown, 1 matches.  /  v [BODY] Body (+1 more)  /  `-- v [PAD] Pad (+1) *tip
types ["PartDesign::Pad"]: OK: 11 objects, 2 shown, 1 matches.  /  (same two tree lines)
types ["PAD"], name_pattern "zzz": OK: 11 objects, 1 shown, 0 matches.  /  v [BODY] Body (+2)
```
Result: the zzz tree line equals the `depth: 1` tree line (`v [BODY] Body (+2)`); the `OK:` line contains `, 0 matches`.

`focus: "InnerPart", depth: 3` on the nested fixture: `OK: 31 objects, 10 shown.`, Warning and `framing:` header lines, then `path: OuterPart > InnerPart`, `v [PART] InnerPart`, its `[ORIGIN]` first, then `v [BOX] LinkTarget`; 10 tree lines. `depth: 1` showed `v [PART] OuterPart (+3)`.

## TC-08-17 carve-out, live

`query_object { object: "Pad" }`: `structured_content.properties.Visibility` is `true` (`<V0>`). `feature_set_parameters { feature: "Pad", parameters: { Visibility: false } }` without `confirm`: `status OK`, `mutation.changed: []`, `Mutation committed`; the tree line for `Pad` then starts `- `. `{ Visibility: true }` (`<V0>`) restores it: `status OK`, framing ratio back to 0.95. (A first attempt with an unconstrained sketch was rolled back by `verify_sketch`, which is a fixture error, not the carve-out.)

## Fix round F1: TC-09 `:313`, `:314` and TC-12 `:659`, `:660`

Container FreeCAD restarted (pid 1774). Document `tc12-11-check`: `App::Part` `Assembly` holding 30 `Part::Box` named `Pad00` to `Pad29`. Document `tc09-07-check`: 250 top-level `Part::Box` `B000` to `B249`. Tree bodies are shortened to the first and last lines where marked.

TC-12-11 reader (`<S> shown`, `<M> matches`, `, truncated.`):
```
query_tree_summary { doc: tc12-11-check }                    (depth 1)
OK: 39 objects, 1 shown.                    ... v [PART] Assembly (+31)
query_tree_summary { depth: 3, filters: {} }                 (condensed: 39 tree lines)
OK: 39 objects, 39 shown.
query_tree_summary { filters: { types: ["BOX"] } }           (condensed: Assembly and 30 Pad lines)
OK: 39 objects, 31 shown, 30 matches.       ... v [PART] Assembly (+1 more)
```
Result: depth 3 shows 39 > 1; the filtered call shows 31 < 39 and reports `30 matches` in the `OK:` line.

TC-09-07 reader (`depth: 2147483647`, cap):
```
query_tree_summary { doc: tc09-07-check, depth: 2147483647 } (condensed: B000 to B199)
OK: 250 objects, 200 shown, truncated.
... 50 more lines; narrow with focus or a smaller depth
```
Result: `<S> shown` is 200, the `OK:` line ends `, truncated.`, and the last tree line is the steering line. A document under the cap (the 39-object one) shows `39 shown` at depth 3 with no `truncated`.

Neighbouring Thens re-read with these outputs: TC-09 `:314` (`<S> shown` equals the tree line count at depth 1; no connector line; `Assembly (+31)` is the only line), TC-09 `:358`, `:475` (same reader, label now `<S>`), TC-12 `:658` (first read returns top-level lines only), TC-12 `:661` ff. (schema refusal and budget Thens do not read counts). All still hold.
