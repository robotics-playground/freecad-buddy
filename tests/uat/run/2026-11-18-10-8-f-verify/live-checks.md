# Verifier live checks, Story 10-8-f

Not a gate run. Verifier: verifier-10-8-f. Commit `19473e4`. Container `fcb-desktop`, image `sha256:ccccd43b5b3df8ee1eaaf547643570184c90099415298be0b98bd6cc103dddc4` (built 2026-11-17T17:06:28Z; no `src/` commit after that time). FreeCAD 1.1.4. The builder's run folder was not read before these checks.

## TC-09-01 Given (`pgrep`, GUI proxy up)

Record: `evidence/tc-09-01-pgrep.txt`.

- FreeCAD pid 1989, GUI proxy pid 2072: `... python -m freecad_buddy.hosts.main serve --mode rpc --transport http`.
- The Given command prints `0`. Expected `0`. PASS.
- Positive control: three fake processes (`exec -a`) named `... hosts.main serve --mode inline --transport stdio`, `... hosts.main serve --transport stdio --mode inline`, `... hosts.headless.worker`. The same command prints `3`. After `pkill` it prints `0` again; the proxy is still listed.

## TC-02-05 `OK:` line reader

Fixture: `document_create { label: "verify1085" }`, then `script_exec` builds `Body` > `Sketch` (20 x 10 rectangle) > `Pad` (Length 5). Pad volume 1000 mm^3. Capture `evidence/tc-02-05-fixture.png` (tree shows `verify1085` > `Body`; the pad is zoomed past the view, consistent with `framing: does not fit, ratio 2.72`).

| Call | `OK:` line | Tree lines (below `OK:`, `Warning:` sentence with blank line, `framing:`) |
|------|------------|------|
| `depth: 1` | `OK: 11 objects, 1 shown.` | `v [BODY] Body (+2)` |
| `depth: 3` | `OK: 11 objects, 11 shown.` | `v [BODY] Body`, then 10 connector lines (`Origin` and 7 children, `Pad *tip`, `Sketch`) |
| `focus: "Body", depth: 2` | `OK: 11 objects, 11 shown.` | `path: Body`, then `v [BODY] Body`, then the same 10 lines |
| `expand: ["Pad"]` | `OK: 11 objects, 3 shown.` | `v [BODY] Body (+1 more)`, `` `-- v [PAD] Pad *tip ``, `` `-- v [SKETCH] Sketch `` |
| `types: ["PAD"]` | `OK: 11 objects, 2 shown, 1 matches.` | `v [BODY] Body (+1 more)`, `` `-- v [PAD] Pad (+1) *tip `` |
| `types: ["PartDesign::Pad"]` | `OK: 11 objects, 2 shown, 1 matches.` | same two lines |
| `name_pattern: "^Pad"` | `OK: 11 objects, 2 shown, 1 matches.` | same two lines |
| `types: ["PAD"], name_pattern: "zzz"` | `OK: 11 objects, 1 shown, 0 matches.` | `v [BODY] Body (+2)` |

`framing:` line: first call `framing: does not fit, ratio 2.72, computed`; every later call `framing: does not fit, ratio 2.72, cached, served from cache; unverified key component(s): geometry`. The header line changes between identical reads, so a whole-text compare fails for a reason that is not the tree.

Thens at `TC-02:232-239` graded on these outputs:

- `:232` depth 1: one tree line, ends `(+2)`, no connector, `<S>` = 1 = tree lines. PASS.
- `:233` depth 3: `<S>` 11 > 1, connector lines under `Body`. PASS.
- `:234` focus: first tree-text line below the header lines is `path: Body`, next `v [BODY] Body`, no object outside the Body. PASS.
- `:237` types: PAD and TypeId results have the same tree lines and the same `1 matches`; 1 = number of Pads. PASS.
- `:239` AND-stack: `OK:` line contains `, 0 matches`; tree lines equal the depth-1 tree lines. PASS.

## TC-06-01 Cleanup (`RemInt`)

`script_exec` on `User parameter:BaseApp/Preferences/View`:

```
{'before_present': False, 'before': -1, 'after_set': 2, 'after_rem': -1,
 'present_after_rem': False, 'final': -1, 'has_RemoveInt': False}
```

`SetInt('AntiAliasing', 2)` then `RemInt('AntiAliasing')` removes the key (`GetInts()` no longer lists it; `GetInt` falls back to `-1`). The group has no `RemoveInt` attribute, so the old Cleanup line raised `AttributeError`. The key was absent before and is absent after. PASS.

Document `verify1085` closed (`document_close` OK); FreeCAD stopped before the runner.

## tc-08-04 runner scenario

Command (Git Bash needs `MSYS_NO_PATHCONV=1`, else the container path is rewritten):

```
docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/runner/run.py \
  /repo/tests/uat/scenarios/tc-08-04.json --out /repo/tests/uat/run/2026-11-18-10-8-f-verify/runner
```

Exit 0. `1 scenarios: 0 PASS, 0 FAIL, 1 ESCALATE.`, `run errors: 0` (`runner-console.txt`, `runner/summary.md`). `findings: []`, `disagreements: []`, `errors: []`; the only reason is the scenario's `agent_check`. The preview step's `structured_content.diff.validity.explanation` is `recompute left 1 object(s) invalid: Fillet: BRep_API: command not done`; `\bFillet\b` matches it. `results.json` `git_dirty: true` comes from `git status --porcelain` (`run.py:630`): the modified and untracked leader files and this run folder. `git status --short -- tests src scripts` lists only this run folder, so no tracked test, source or script file differs from `19473e4`.

Capture `runner/captures/TC-08-04.png`, read: one 20 x 20 x 30 pad in isometric view, framed, sharp edges, no rounded edge, grey faces with no error colouring, tree shows `TC0804` > `Body` only, no dialog. The `agent_check` asks for a comparison with a before capture that the runner does not take: that comparison is NOT RUN here (it is gate-run work, not part of this slice).
