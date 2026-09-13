# UAT Bug Ledger — Run 2026-09-13

Bugs found while executing the green gate (TC-01..TC-14) against the live application.
Recorded for later fixing; nothing in this run fixes product code.

**Status vocabulary:** `open` = found, unfixed. `invalid` = not a product defect (test or
environment fault). `duplicate` = already recorded elsewhere.

**Severity:** `blocker` = stops the suite. `high` = a shipped contract is wrong.
`medium` = wrong behaviour with a workaround. `low` = cosmetic or documentation.

---

## Summary

| ID | Severity | Area | Title | Status |
| --- | --- | --- | --- | --- |
| UAT-01 | low | test | TC-01-05 CP3 expected-timeout list omits `view_fit_viewport` | open |
| UAT-02 | low | test | TC-01-03 CP1 snippet is missing `asyncio.run(main())` | open |
| UAT-03 | medium | test | TC-01-06/07/08 and TC-01-09 CP7 are unrunnable while the proxy is attached | open |
| UAT-04 | medium | env | `cua-driver` MCP session dies mid-run; `kill_app` refuses foreign processes | open |
| UAT-05 | **high** | product | `query_tree_summary` filters gate at the root, hiding matching descendants | open |
| UAT-06 | medium | product | `document_save` silently creates missing parent directories | open |
| UAT-07 | medium | product | `document_save` to an existing directory writes a sibling `.FCStd` instead of refusing | open |
| UAT-08 | low | test | TC-02-13 CP5/CP6 expect a Label that FreeCAD overwrites from the filename | open |
| UAT-09 | low | test | TC-02-17 CP4 expects two indistinguishable FreeCAD errors to differ | open |
| UAT-10 | low | test | TC-02-18 CP1 omits `RECOMPUTE_ERROR` from its expected status set | open |
| UAT-11 | medium | coverage | No MCP tool writes a Placement or creates `App::Part`/`App::Link` | open |
| UAT-12 | **high** | product | `sketch_add_constraint` rejects FreeCAD's native 3-argument `DistanceX`/`DistanceY` | open |
| UAT-13 | low | product | `sketch_set_datum` surfaces a misleading "Invalid constraint index" for an unsolvable datum | open |
| UAT-14 | low | test | TC-03-05 uses `start` for a `point`; the implementation reads `center` | open |
| UAT-15 | medium | test | TC-03-06 and TC-03-14 preconditions require an under-constrained commit, which AD-8 forbids | open |
| UAT-16 | low | test | TC-03-13 CP3 asserts `findings=[]` on a `CLEAN` TNP status | open |
| UAT-17 | low | test | TC-03-16 CP1 expects `SPEC_FAILED` where an over-constrained sketch yields `RECOMPUTE_ERROR` | open |
| UAT-18 | low | test | TC-03-19 CP1 needs a stale `geo_id`, which FreeCAD's index compaction makes unconstructible | open |
| UAT-19 | **high** | product | `feature_pad` `second_length` sets `Length2` but never enables `SideType`, so it silently no-ops | open |
| UAT-20 | medium | product | `feature_set_parameters` on read-only `Shape` returns `SPEC_FAILED`, not `INVALID_INPUT` | open |
| UAT-21 | low | test | TC-04-07 hole volume omits FreeCAD's default 118-degree drill point | open |
| UAT-22 | low | test | TC-04-09 hardcoded edge names are not the four vertical corners on this build | open |
| UAT-23 | low | test | Non-finite numeric rejection is unreachable through the JSON MCP transport | open |
| UAT-24 | medium | env | The MCP client does not reattach after FreeCAD restarts, stranding the run | open |
| UAT-25 | low | test | TC-04-10/13/17 use enum spellings and an edge name that do not exist on this build | open |
| UAT-26 | medium | test | A face-attached sketch's local frame is not the global frame; TC-04 offsets land outside the solid | open |
| UAT-27 | medium | product | `query_mass_properties` reports a Body volume that ignores a non-overlapping Pocket without warning | open |
| UAT-28 | **high** | product | A large `feature_pattern` blocks FreeCAD's main thread and takes the whole bridge down unrecoverably | open |
| UAT-29 | **high** | product | The fingerprint is not stable across save/reopen, so EVERY snapshot rollback reports a false "could not be proven" | open |
| UAT-30 | medium | product | `FCB_TMP_snap_*` directories leak into the temp directory; 9 found | open |

---

## Findings

### UAT-01 — TC-01-05 CP3 expected-timeout list omits `view_fit_viewport`

- **Severity:** low
- **Area:** test (not a product defect)
- **Found in:** TC-01-05 CP3
- **Status:** open

**What happened.** CP3 pins the 30-second timeout set at 10 named tools. The live catalog has
**11** — `view_fit_viewport` also carries `timeout_s=30.0` (`tool_catalog.py:906`).

**Why it is a test bug.** The catalog is correct; the checkpoint's list is stale. `view_fit_viewport`
is the shipped 45th tool (Epic 8, commit `636fb8a`). The stale-44 correction pass before this run
updated `APPENDIX-B` step 6, `TC-01-03`, `test-plan.md`, `README.md` and `coverage-matrix.md`, but
missed this checkpoint because it names tools rather than a count.

**Fix.** Add `view_fit_viewport` to the CP3 expected list in
`tests/uat/TC-01-session-lifecycle-and-transport.md`.

**Evidence.** `_automation/uat/tc0105_dump.txt` line `view_fit_viewport 30.0 True`.

---

### UAT-02 — TC-01-03 CP1 snippet is missing `asyncio.run(main())`

- **Severity:** low
- **Area:** test (not a product defect)
- **Found in:** TC-01-03 CP1
- **Status:** open

**What happened.** The Python block defines `async def main()` but never runs it. Pasted literally
it exits 0, prints nothing, and writes no `_automation/tools_list.json` — so CP2..CP6, which all
grep that file, would read a stale or absent file.

**Why it matters.** A checkpoint that silently does nothing reports a pass it did not earn.

**Fix.** Append `asyncio.run(main())` to the snippet.

---

### UAT-03 — TC-01-06/07/08 and TC-01-09 CP7 cannot run while the proxy is attached

- **Severity:** medium
- **Area:** test harness design (product behaviour is the already-known AD-26 gap)
- **Found in:** TC-01-06, TC-01-07, TC-01-08 (22 checkpoints), TC-01-09 CP7
- **Status:** open

**What happened.** All four need a second raw socket to the RPC port to drive a handshake
(wrong `contract_version`, bad token, non-`rpc_hello` first frame). Every attempt was refused with
`ConnectionRefusedError [WinError 10061]`, reproducible 3/3.

**Root cause, verified in source by the main agent, not taken on report.**
`adapters/rpc_listener.py:146` binds `sock.listen(1)`, and `_accept_loop` (`:218-236`) is strictly
serial: `accept()` -> `_serve_conn()` -> `close()` -> loop. `_serve_conn` holds one connection for
its whole lifetime. The MCP proxy holds exactly such a persistent connection, so the backlog of
depth 1 is saturated and no second client is ever accepted.

**This is not a new product bug.** It is the documented **AD-26** deviation already recorded as
conformance case TC-99-03 ("a second client blocks in the accept backlog instead of receiving a
`-32000` busy error"). The product behaves as the conformance gate says it does.

**The test bug is that TC-01 does not know that.** Four green-gate checkpoints are written against
a concurrency the shipped listener does not have, so they can never pass in the shipped topology.

**Fix options.** Either (a) run these scenarios against a dedicated test-only RPC listener with no
proxy attached, or (b) re-scope them to the pre-attach window, or (c) mark them blocked-by-AD-26
and cross-reference TC-99-03. Do not "fix" the listener for these tests alone — AD-26 is a spine
decision, not an oversight.

---

### UAT-04 — cua-driver MCP session dies mid-run; kill_app refuses foreign processes

- **Severity:** medium
- **Area:** environment / tooling (not a freecad-buddy defect)
- **Found in:** TC-01-13, TC-01-14 (14 checkpoints skipped); earlier disruption in TC-01-04 CP1
- **Status:** open

**What happened.** Two distinct failures in the GUI driver:

1. **Session death.** Every `mcp__cua-computer-use__*` tool began returning
   `this session has ended; call session explicitly to reuse its label` — including for a
   nonexistent pid, which proves a session-lifecycle failure rather than a per-process check.
   `start_session` with a fresh label did not recover it. The plain `cua-driver call ...` CLI kept
   working throughout, and is the reliable fallback.
2. **`kill_app` refuses a foreign process.** The CLI path returns
   `foreign_process_termination_denied` — "standard mode may terminate only a process proven to
   have been launched by this Cua runtime". TC-01-14 needs an unclean kill and explicitly forbids
   `taskkill /F` as a substitute, so the scenario has no legal path in standard mode.

**Related earlier symptom.** In TC-01-04, opening FreeCAD's About dialog left its Qt window with an
unresponsive UIA provider (`UIA provider unresponsive on hwnd 0x7046e, class 'Qt683QWindowIcon'`),
hanging `invoke_menu`/`list_windows`/`health_report` for a full timeout. Escape recovered it
temporarily. Do not open modal FreeCAD dialogs through the driver during a run.

**Fix.** Run the kill-requiring scenarios with the driver in an escalated mode, or relaunch FreeCAD
through the Cua runtime so it counts as runtime-launched and `kill_app` is permitted. Record the
About-dialog trap in `APPENDIX-B`.

---

### UAT-05 — `query_tree_summary` filters gate at the tree root, hiding matching descendants

- **Severity:** high
- **Area:** product
- **Found in:** TC-02-05 CP5, CP8, CP10
- **Status:** open

**What happened.** On a `Body -> Sketch -> Pad` tree, asking for only the Pad returns an empty tree:

```
query_tree_summary { doc, depth: 3, filters: { types: ["PartDesign::Pad"] } }
-> tree: []
```

The `Pad` exists and is within `depth`. It is dropped because its **root** (`Body`) is not a
`PartDesign::Pad`. The same root-gating breaks `renderable_only` and `name_pattern`.

**Root cause, confirmed in source by the main agent.**
`src/freecad_buddy/usecases/queries.py:358`:

```python
tree = [build(o, depth) for o in roots if _node_passes(o, effective)]
```

A root that fails the filter is never built, so its whole subtree disappears. `_node_passes`
(`queries.py:200-218`) is a correct per-object predicate — the defect is where it is applied. The
recursive step has the same shape at `queries.py:352-354`, so the filter prunes branches rather
than selecting nodes.

**Why it is high severity.** This is the primary discovery tool for an agent inspecting a model.
`types` is the natural way to ask "where are the pads in this document", and it silently answers
"there are none" for the most common PartDesign layout, where every feature sits under a Body. An
empty result is indistinguishable from a genuinely empty document.

**Fix direction.** Filters should select which nodes are *returned*, not which branches are
*walked*. Walk the full tree to `depth`, then keep a node when it passes, or when a descendant
does. Decide deliberately whether a kept descendant carries its ancestor chain for context.

---

### UAT-06 — `document_save` silently creates missing parent directories

- **Severity:** medium
- **Area:** product
- **Found in:** TC-02-18 CP3
- **Status:** open

**What happened.** Saving to a path whose parent does not exist succeeds and creates the directory:

```
document_save { doc, path: "_automation/no-such-dir/out.FCStd" }
-> status: "OK", saved: true
```

Confirmed on disk by the main agent: `_automation/no-such-dir/out.FCStd`, 3693 bytes.

**Root cause.** `src/freecad_buddy/usecases/documents.py:246` calls `document.saveAs(path)` with no
pre-check of the parent directory.

**Why it matters.** A typo in a path silently scatters files into new directories instead of being
refused. The checkpoint expects a refusal because an agent cannot see the filesystem and has no way
to notice.

---

### UAT-07 — `document_save` to an existing directory writes a sibling file instead of refusing

- **Severity:** medium
- **Area:** product
- **Found in:** TC-02-18 CP4
- **Status:** open

**What happened.** Passing an existing **directory** as the save path succeeds:

```
document_save { doc, path: "_automation" }
-> status: "OK", saved: true
```

FreeCAD appended `.FCStd` and wrote `_automation.FCStd` **next to** the directory. Confirmed on
disk by the main agent: 3695 bytes at the repo root.

**Root cause.** Same line as UAT-06, `documents.py:246` — no check that the target is not a
directory.

**Why it matters.** The file lands somewhere the caller did not name. An agent that later reads
`_automation/` finds nothing and concludes the save failed, while a stray file accumulates at the
repo root.

---

### UAT-08 — TC-02-13 CP5/CP6 expect a Label that FreeCAD overwrites from the filename

- **Severity:** low
- **Area:** test (not a product defect)
- **Found in:** TC-02-13 CP5, CP6
- **Status:** open

**What happened.** A document labelled with Unicode, saved and reopened, comes back labelled from
the **filename** (`uat-unicode`), not the original label.

**Why it is a test bug.** The executing agent falsified the Unicode hypothesis with a control: a
plain ASCII label (`plain-ascii-label-test`) saved to a differently-named file also returned the
filename-derived label. So this is `FreeCAD.openDocument()`'s own behaviour, not an encoding fault.
`usecases/documents.py:236` returns `document.Label` verbatim — a faithful passthrough.

**Fix.** Re-scope the checkpoint to assert what FreeCAD actually guarantees: the Unicode label must
survive in the **live session** (CP1-CP4, which passed), and a reopened document takes its label
from the filename.

---

### UAT-09 — TC-02-17 CP4 expects two indistinguishable FreeCAD errors to differ

- **Severity:** low
- **Area:** test (not a product defect)
- **Found in:** TC-02-17 CP4
- **Status:** open

**What happened.** CP4 wants a non-FCStd text file and a corrupt zip to be distinguishable. Both
produce the identical FreeCAD message apart from the filename:

```
Invalid project file '<path>': ios_base::failbit set: iostream stream error
```

**Why it is a test bug.** `usecases/documents.py:225` passes the FreeCAD exception through verbatim;
nothing discards distinguishing detail, because FreeCAD never produced any. The checkpoint asserts a
distinction the underlying library does not make.

**Fix.** Assert that both are refused with a non-`OK` status naming the offending path, and drop the
requirement that the two differ from each other.

---

### UAT-10 — TC-02-18 CP1 omits `RECOMPUTE_ERROR` from its expected status set

- **Severity:** low
- **Area:** test (not a product defect)
- **Found in:** TC-02-18 CP1
- **Status:** open

**What happened.** Saving over a read-only file returns `RECOMPUTE_ERROR`. CP1 names only
`INVALID_INPUT` or `WORKER_CRASHED`.

**Why it is a test bug.** The result is never `OK`, and `RECOMPUTE_ERROR` is a real member of the
closed status set (also observed in TC-02-06). The refusal is correct; the checkpoint's accepted set
is incomplete.

**Worth a second look during triage.** `RECOMPUTE_ERROR` is a poor description of a permission
failure. Deciding the right status for "the file could not be written" is a product question, even
though the refusal itself is right.

---

### UAT-11 — No MCP tool writes a Placement or creates `App::Part`/`App::Link`

- **Severity:** medium
- **Area:** tool-surface coverage
- **Found in:** TC-02-08 CP5/CP7, TC-02-14 (all 8 checkpoints)
- **Status:** open

**What happened.** Two coverage gaps made 10 checkpoints unrunnable:

1. **No placement write.** `feature_set_parameters` accepts only `App::PropertyAngle` or
   length-quantity values (`usecases/features.py:1668-1683`); a Placement dict fails with
   `Placement value value must be a number, got None`. So `query_placement`'s local-vs-global
   distinction cannot be exercised — nothing can move an object.
2. **No `App::Part` / `App::Link` creation.** No `feature_*` or `sketch_*` tool creates either, so
   the nested-assembly tree TC-02-14 measures cannot be built through the bridge.

**Why it matters.** These are read tools with no matching write, so their interesting behaviour is
untestable through the bridge alone. Decide deliberately whether that is intended scope (Phase-5
Assemblies owns links) or a gap to close; if intended, record it in `APPENDIX-A-deferred-coverage.md`
so the checkpoints stop being written against it.

---

### UAT-12 — `sketch_add_constraint` rejects FreeCAD's native 3-argument `DistanceX`/`DistanceY`

- **Severity:** high
- **Area:** product
- **Found in:** TC-03-05 CP1-CP4, TC-03-06 step 2; forced workarounds in TC-03-10, 14, 15, 19
- **Status:** open

**What happened.** Dimensioning a single point's X or Y position from the sketch origin is refused:

```
sketch_add_constraint { type: "DistanceX", first: 0, first_pos: 1, value: {value: 60, unit: "mm"} }
-> INVALID_INPUT
   "DistanceX with a first_pos also requires 'second' and 'second_pos'"
```

**Root cause, confirmed in source by the main agent.**
`src/freecad_buddy/usecases/sketches.py:441-444` raises whenever `first_pos` is present without
`second`. But FreeCAD's own binding implements exactly that overload —
`docs/references/FreeCAD/src/Mod/Sketcher/App/ConstraintPyImp.cpp:441-451`:

```cpp
else if (strcmp("DistanceX", ConstraintType) == 0) {
    FirstPos = SecondIndex;
    SecondIndex = -1;
    constraint->Type = DistanceX;
    constraint->FirstPos = static_cast<Sketcher::PointPos>(FirstPos);
}
```

`SecondIndex = -1` is FreeCAD deliberately encoding "no second geometry". The shipped validator
treats a legal arity as a caller error.

**Why it is high severity.** Locating a circle or arc centre relative to the origin is a routine
sketching move and the natural way to pin a hole pattern. Every affected scenario had to be reworked
around it, so the blast radius is wider than the four failing checkpoints.

**Fix direction.** Accept `first` + `first_pos` with no `second` for `DistanceX`/`DistanceY`
specifically, mapping to FreeCAD's 3-argument form. Keep the existing requirement for the other
constraint types, where a lone `first_pos` really is incomplete.

---

### UAT-13 — `sketch_set_datum` surfaces a misleading "Invalid constraint index"

- **Severity:** low
- **Area:** product (observability; data integrity is intact)
- **Found in:** TC-03-15
- **Status:** open

**What happened.** A legal datum value that makes the sketch unsolvable reports an index error:

```
sketch_set_datum { constraint: "HoleSpacing", value: {value: -5, unit: "mm"} }
-> SPEC_FAILED, explanation: "ValueError: Invalid constraint index: 2"
```

The constraint index was valid. The solver simply could not converge.

**Root cause.** FreeCAD's `SketchObject::setDatum`
(`SketchObjectConstraints.cpp:184-220`) returns the **solver's** return code as its error code, and
the Python binding (`SketchObjectPyImp.cpp:913-940`) maps `err == -1` unconditionally to
"Invalid constraint index".

**Why it is still worth recording.** The rollback is correct and proven — no data is harmed. But the
message sends the caller to check an index that was never wrong, instead of reporting that the value
made the sketch unsolvable. An agent acting on this message will retry with a different index and
fail again.

**Fix direction.** The failure originates upstream in FreeCAD, so wrap rather than patch it: when
`setDatum` fails and the constraint reference resolved successfully, report that the value could not
be solved and keep FreeCAD's text as machine detail.

---

### UAT-14 — TC-03-05 uses `start` for a `point`; the implementation reads `center`

- **Severity:** low
- **Area:** test (not a product defect)
- **Found in:** TC-03-05 setup
- **Status:** open

**What happened.** The script passes `{ "kind": "point", "start": [10, 30] }`. `sketches.py:205`
reads `spec.get("center")`, so the call fails with
`geometry[3].center must be a list of 2 or 3 numbers, got None`. Using `center` is accepted.

**Fix.** Change the TC's point specs from `start` to `center`.

---

### UAT-15 — TC-03-06 and TC-03-14 preconditions require a commit that AD-8 forbids

- **Severity:** medium
- **Area:** test (not a product defect)
- **Found in:** TC-03-06 CP1-CP4, CP8; TC-03-14 CP1-CP4
- **Status:** open

**What happened.** Both scenarios need a sketch left **persisted and under-constrained**, so that
later calls can add the first constraints. That state cannot exist: AD-8 hard-fails and rolls back
any sketch mutation leaving `dof > 0`, enforced for every sketch tool through the shared
`_sketch_mutation` helper (`sketches.py:532` onward). Adding the 6 geometry items alone yields
`dof=20` and `status=SPEC_FAILED`, rolled back.

**Why it is a test bug.** The product is behaving exactly as AD-8 requires. The scenarios were
written against a workflow the invariant forbids — confirmed empirically across three
geometry+constraint combinations, none of which survived with `dof > 0`.

**Fix.** Rewrite both to reach their target state within a single fully-constrained mutation, or to
assert the AD-8 rollback itself, which is the real shipped behaviour.

---

### UAT-16 — TC-03-13 CP3 asserts `findings=[]` on a `CLEAN` TNP status

- **Severity:** low
- **Area:** test (not a product defect)
- **Found in:** TC-03-13 CP3
- **Status:** open

**What happened.** CP3 requires `findings` to be empty when `status` is `CLEAN`. The shipped guard
returns all findings including `PASS`-verdict entries: `tnp_guard.py:457-459` sets
`"status": "FLAGGED" if failing else "CLEAN"` and never filters the list.

**Why it is a test bug.** `CLEAN` means nothing failed, not that nothing was checked. A non-empty
all-`PASS` findings list is the evidence the check ran.

**Fix.** Assert that every finding's verdict is `PASS` when the status is `CLEAN`.

---

### UAT-17 — TC-03-16 CP1 expects `SPEC_FAILED` where an over-constrained sketch yields `RECOMPUTE_ERROR`

- **Severity:** low
- **Area:** test (not a product defect)
- **Found in:** TC-03-16 CP1
- **Status:** open

**What happened.** A conflicting constraint set returns `RECOMPUTE_ERROR`, not `SPEC_FAILED`.

**Why it is a test bug.** The distinction is deliberate: `transaction.py:272-275` classifies a native
FreeCAD recompute failure ("Over-constrained sketch") as `RECOMPUTE_ERROR`, reserving `SPEC_FAILED`
for AD-8's own `dof` check after a clean recompute. Both roll back correctly; CP1 names the wrong one.

**Fix.** Expect `RECOMPUTE_ERROR` for the over-constrained case, and state why the two differ so the
next reader does not "correct" it back.

---

### UAT-18 — TC-03-19 CP1 needs a stale `geo_id` that cannot be constructed

- **Severity:** low
- **Area:** test (not a product defect)
- **Found in:** TC-03-19 CP1, CP2
- **Status:** open

**What happened.** CP1 wants a `geo_id` that no longer exists after a removal. FreeCAD's Sketcher
compacts and reindexes geometry on every removal, leaving no tombstone — so after removing `geo_id`
1, index 1 addresses valid but **different** geometry. Confirmed empirically.

**Why it is a test bug.** A "stale but in-range" id is indistinguishable from a live one by design.
Genuinely out-of-range ids are already covered by other checkpoints.

**Fix.** Drop CP1/CP2, or re-scope them to assert the reindexing behaviour itself — that a removal
shifts later ids, which is the real hazard an agent must know about.

---

### UAT-19 — `feature_pad` `second_length` sets `Length2` but never enables two-sided extrusion

- **Severity:** high
- **Area:** product
- **Found in:** TC-04-04 CP4
- **Status:** open

**What happened.** Padding with `second_length` accepts the argument, reports `OK`, and produces a
**single-sided** pad. The committed volume stayed 6000 mm³ instead of exceeding it.
`query_object` on the result shows `Length2: "4.0 mm"` alongside `SideType: "One side"`.

**Root cause, confirmed in source by the main agent.**
`src/freecad_buddy/usecases/features.py:485-486`:

```python
if second_length is not None:
    feature.Length2 = _length_mm(second_length, "second_length")
```

`SideType` is never assigned. A grep for `SideType` across the whole file returns **no hits** — the
property that makes `Length2` take effect is nowhere in the codebase. FreeCAD ignores `Length2`
while `SideType` remains `"One side"`.

**Why it is high severity.** The call reports success and the verification passes, because the shape
really is valid — just not the shape that was asked for. The agent has no signal that its second
extrusion length was discarded. A silently-ignored parameter is worse than a rejected one.

**Fix direction.** Set `SideType` to the two-sided value when `second_length` is supplied. Confirm
the exact enum spelling against FreeCAD's `PartDesign::Pad` (the capability banner's `enums` block
reports `Type`, not `SideType`, so read the property's own enumeration). Add a volume assertion, not
just a status assertion, so a future regression cannot pass silently again.

---

### UAT-20 — `feature_set_parameters` on the read-only `Shape` returns `SPEC_FAILED`, not `INVALID_INPUT`

- **Severity:** medium
- **Area:** product
- **Found in:** TC-04-21 CP2, CP5
- **Status:** open

**What happened.** Writing the read-only `Shape` property returns
`SPEC_FAILED (TypeError: type must be 'Shape', not int)` instead of the contracted
`INVALID_INPUT` naming `BlockPad.Shape is read-only`. The refusal happens **inside** the transaction
rather than before it.

**Root cause.** `src/freecad_buddy/usecases/features.py:1662-1663`:

```python
if "ReadOnly" in list(feature.getEditorMode(prop) or []):
    raise ValidationError(f"{feature.Name}.{prop} is read-only")
```

`getEditorMode("Shape")` on a `PartDesign::Pad` does not report `ReadOnly` — FreeCAD enforces
`Shape` immutability at the C++ property-type level, not through editor mode. So the guard passes
and the raw write fails later.

**Mitigating.** The transaction opens and rolls back correctly, fingerprint-verified, with no
snapshot leak. No data was corrupted; the defect is in the status contract and the timing of the
refusal.

**Fix direction.** Do not rely on editor mode alone. Reject writes to known-immutable properties
(`Shape` first among them) before the transaction opens, so the caller gets `INVALID_INPUT` with an
actionable message.

---

### UAT-21 — TC-04-07's hole volume omits FreeCAD's default 118-degree drill point

- **Severity:** low
- **Area:** test (not a product defect)
- **Found in:** TC-04-07 CP2
- **Status:** open

**What happened.** CP2 expects `volume = 11928.7`, assuming a flat-bottomed bore. Measured
`11915.6393`. The difference is exactly the cone left by FreeCAD's default
`PartDesign::Hole` `DrillPoint = "Angled"` (a 118-degree drill tip): the measurement matches
`12000 - (cylinder + 118-degree cone)` analytically.

**Why it is a test bug.** The tool faithfully produced FreeCAD's default hole. The checkpoint's
analytic formula models a different hole.

**Fix.** Either correct the expected volume to include the drill-point cone, or set
`DrillPoint` explicitly in the scenario so the flat-bottom formula is the right one. Prefer setting
it explicitly — an expectation that silently depends on a FreeCAD default will drift again.

---

### UAT-22 — TC-04-09's hardcoded edge names are not the four vertical corners

- **Severity:** low
- **Area:** test (not a product defect)
- **Found in:** TC-04-09
- **Status:** open

**What happened.** The scenario fillets `Edge1, Edge3, Edge5, Edge7` as "the four vertical corners".
On this build's `PlatePad` those are two 5 mm verticals plus one 60 mm and one 40 mm edge. The real
four verticals are `Edge1, Edge2, Edge5, Edge8` — established by filleting each edge individually
and matching the removed volume to an analytic prediction.

With the corrected edges the result is `11982.831853071797`, matching the checkpoint's own expected
`11982.8` exactly. So the fillet tool is correct; only the edge list is wrong.

**Why it matters beyond this test.** Hardcoded `EdgeN` names are exactly what topological naming
breaks. A checkpoint pinned to them will rot on any FreeCAD version change.

**Fix.** Use the corrected names, and add a step that derives the vertical edges from geometry
rather than naming them, so the scenario survives a renumbering.

---

### UAT-23 — Non-finite numeric rejection is unreachable through the JSON MCP transport

- **Severity:** low
- **Area:** test / coverage
- **Found in:** TC-04-19 CP7; also TC-03-15 CP6
- **Status:** open

**What happened.** Both checkpoints require sending `Infinity` (or `1e999`) to prove the
"must be finite" guard rejects it. Standard JSON has no literal for a non-finite number, so the
value cannot cross the MCP transport. Other encodings (`null`, a string) hit different validation
paths and prove nothing about the finite check.

**The guard does exist** — `sketches.py:124-125` implements it — but it cannot be reached from a
conforming client.

**Fix.** Cover the finite check with an external unit test that calls the usecase directly, and
remove the checkpoint from the UAT suite, recording the reason in
`APPENDIX-A-deferred-coverage.md`. A checkpoint no conforming client can trigger is not a UAT
concern.

---

### UAT-24 — The MCP client does not reattach after FreeCAD restarts

- **Severity:** medium
- **Area:** environment / tooling (blocks UAT execution)
- **Found in:** between TC-04 and TC-05
- **Status:** open

**What happened.** FreeCAD (pid 27632) and its proxy exited mid-run. The main agent relaunched
FreeCAD through `cua-driver` and the addon auto-spawned a new proxy — verified healthy:

```
netstat -ano | grep 8765   -> 127.0.0.1:8765 LISTENING 16988
mcp-proxy.log              -> "freecad-buddy GUI-external MCP server on http://127.0.0.1:8765/mcp"
curl -X POST .../mcp       -> 307 (the expected redirect)
```

But the `mcp__freecad-buddy__*` tools never came back. `ToolSearch` reports no match for any of the
45 names. The bridge is up; the **client** is not reconnected.

**Why it matters for a long UAT run.** The suite's own topology makes this likely rather than rare:
TC-01-10, TC-01-12, TC-01-13 and TC-01-14 all deliberately stop FreeCAD or the proxy, and TC-10 and
TC-14 stress the same paths. Each restart risks stranding the client for the rest of the session.

**Workaround for the operator.** Restart the Claude Code session, or otherwise force an MCP
reconnect, after any scenario that restarts FreeCAD. The bridge itself needs no repair — only the
client connection does.

**Fix direction.** Have the MCP client retry a dropped HTTP transport rather than giving up
permanently, since the addon deliberately re-serves the same fixed `127.0.0.1:8765` endpoint after a
restart. Until then, treat "restarts FreeCAD" as a run-ending scenario and schedule those cases
last.

---

### UAT-25 — TC-04-10/13/17 use enum spellings and an edge name that do not exist on this build

- **Severity:** low
- **Area:** test (not a product defect)
- **Found in:** TC-04-10, TC-04-13, TC-04-17
- **Status:** open

Three literal values in the scenarios do not match FreeCAD 1.1.1. Each was confirmed by probing the
live build, and each scenario passed once corrected:

| Scenario | Written | Actual on this build |
| --- | --- | --- |
| TC-04-10 | `"Distance and angle"` | `"Distance and Angle"` (capital A) |
| TC-04-13 | `map_mode: "ObjectXY"` / `"ObjectOrigin"` for edge/vertex attachment | `Tangent` for axis-on-edge, `Vertex` for point-on-vertex |
| TC-04-17 | seam edge `Edge2` | `Edge3` |

The `ChamferType` spelling is confirmable from the capability banner, which reports
`"Distance and Angle"` in its `enums` block — the test should be generated from that rather than
transcribed.

**Fix.** Correct the three literals. For the chamfer enum, prefer asserting against the banner's
`enums` so a FreeCAD spelling change is caught rather than transcribed wrong again.

---

### UAT-26 — A face-attached sketch's local frame is not the global frame

- **Severity:** medium
- **Area:** test (not a product defect) — but it invalidated a severe-looking bug report
- **Found in:** TC-04-08, TC-04-11, TC-04-24
- **Status:** open

**What happened.** A subagent reported that `feature_pocket` and `feature_hole` "do not cut material
on a box-based Body" — reproduced across three documents, with `status: OK`, clean recompute, and an
unchanged volume. It looked like a severe product defect.

**It is not.** The main agent built a minimal reproduction
(`_automation/uat/probe_pocket.py`): a 60x40x5 plate, then a 20x10 slot pocket 2 mm deep, attached
to the pad's top face by mapped name.

```
volume after pad    = 12000.0   (expect 12000.0)
volume after pocket = 11600.0   (expect 11600.0 for a 20x10x2 cut)
VERDICT: POCKET CUT
```

**The pocket cuts correctly, to the exact analytic value.**

**The real cause.** In the failing document, the slot sketch's world-space bounding box is

```
xmin -10.0  xmax 0.0   ymin -10.0  ymax 0.0   z 5.0
```

while the plate spans `x: 0..60, y: 0..40`. The slot lies entirely **outside** the solid, touching
only at the corner point `(0,0)`. A pocket that overlaps nothing removes nothing — FreeCAD is right
to report success and change no volume.

`Face6`'s local coordinate frame has its origin at the far corner with axes pointing outward, so the
scenario's positive `(10,10)` offsets landed at negative world coordinates.

**Two lessons worth keeping.**
1. **For the suite:** a scenario that sketches on a face must pin its profile against the face's own
   frame, or verify the profile's world bbox lies inside the target solid before cutting. Add that
   as an explicit precondition wherever TC-04 attaches to a face.
2. **For the process:** the "OK status, unchanged volume" symptom is identical for a genuine
   no-op bug and a mis-placed profile. Only an independent minimal reproduction separates them.

---

### UAT-27 — A Pocket that overlaps nothing reports OK with no warning

- **Severity:** medium
- **Area:** product (observability)
- **Found in:** discovered while investigating UAT-26
- **Status:** open

**What happened.** A `feature_pocket` whose profile lies entirely outside the base solid commits
with `status: OK`, `post_verify.passed: true`, `recompute_clean: true`, and a **completely unchanged
volume**. The resulting `PartDesign::Pocket` simply passes the base shape through.

**Why it is worth fixing even though FreeCAD is behaving correctly.** The agent asked to remove
material and was told the operation succeeded. Nothing in the envelope distinguishes
"cut 400 mm³ as intended" from "cut nothing at all". The verification layer exists precisely to
catch a result that does not match the intent, and here it reports a pass.

This is the same failure shape as UAT-19 (`second_length` silently ignored): the tool reports
success while doing nothing.

**Fix direction.** A subtractive feature that produces zero volume change is almost never what the
caller meant. Treat it the way AD-8 treats an under-constrained sketch: fail the post-verify with a
message naming the likely cause (the profile does not overlap the solid), and include the profile's
world bbox against the solid's so the caller can see the mismatch. If a zero-change cut must stay
legal, it should at minimum carry a warning in `text`, not a bare `OK`.

---

### UAT-28 — A large `feature_pattern` blocks FreeCAD's main thread and kills the bridge

- **Severity:** high
- **Area:** product (resilience)
- **Found in:** TC-05-06, reproducer 2
- **Status:** open

**What happened.** `feature_pattern` with `occurrences: 200` never returned. Observed by the main
agent:

- FreeCAD's resident memory climbed to **6.1 GB**.
- The in-FreeCAD RPC listener stopped accepting, so every later call returned
  `WORKER_CRASHED` with `detail.message: "connect refused"` and `data.rpc: "unreachable"`.
- Memory drained back to ~3.2 GB over several minutes as the operation unwound, but the listener
  **never resumed**. The process had to be killed and FreeCAD relaunched.
- The orphaned proxy then held `:8765` as a zombie and resisted `taskkill /F` (access denied); only
  `Invoke-CimMethod -MethodName Terminate` cleared it.

**Why it is high severity.** The failure is not confined to the offending call. The RPC listener
runs on FreeCAD's main thread, so any operation that blocks that thread takes down the entire
bridge: the tool that issued it, every other tool, and the run. There is no timeout that saves it —
the per-tool budget cannot fire, because the thread that would enforce it is the blocked one.

An agent has no way to know that `occurrences: 200` is dangerous while `occurrences: 20` is fine.
Nothing in the schema bounds it, and the failure mode is a dead bridge rather than a refused call.

**Fix direction, in order of value.**
1. **Bound the input.** Give `feature_pattern.occurrences` a schema maximum. A pattern large enough
   to freeze the GUI is not a useful modelling request, and a refusal is infinitely better than a
   dead process.
2. **Pre-check the cost.** `preview_dry_run` already builds the operation on a temp document — it is
   the natural place to refuse a pattern whose occurrence count or resulting solid count exceeds a
   stated ceiling.
3. **Consider the general case.** `occurrences` is the instance found; the class is "any argument
   that scales the work FreeCAD does on the main thread". Audit the mutation surface for other
   unbounded multipliers.

**Test-suite consequence.** Until this is bounded, no scenario should pass a large occurrence count.
TC-05-06's reproducer 2 must be re-scoped to ~20, which exercises the same code path.

---

### UAT-29 — Snapshot rollback cannot reproduce the pre-mutation fingerprint

- **Severity:** high
- **Area:** product
- **Found in:** TC-05-06 (`feature_set_parameters` escalation reproducer)
- **Status:** open

**What happened.** A mutation failed its recompute, the snapshot-restore path ran, and the restored
document **did not digest back to the pre-mutation fingerprint**:

```
status: SPEC_FAILED
detail.code: mutation.spec_failed
detail.message: "recompute left 1 object(s) invalid: Fillet: BRep_API: command not done;
                 rollback could not be proven: the snapshot-restored document does not match
                 the pre-mutation fingerprint 30995a6ca971fd952dbbe0c94aea8bf84332ae80c35a1f0f..."
rolled_back:      false
rollback_proven:  null
snapshot_path:    C:\Users\thuan\AppData\Local\Temp\FCB_TMP_snap_yjuiim6p\tc0506.FCStd
```

**What the product got right.** It refused to claim a rollback it could not prove. `rolled_back` is
`false` rather than a comfortable lie, the failure is escalated rather than swallowed, and the
snapshot is preserved on disk for recovery. That is AD-5 behaving exactly as intended, and it is why
this was caught at all.

**Why it is still high severity.** The whole point of the snapshot path is to restore the document
when the in-memory abort cannot. Here it ran and produced something that is *not* the original. The
document is left in a state the bridge itself cannot vouch for, and the caller is handed a raw
Windows temp path in `text` with no instruction for what to do with it.

**Main-agent verification of the resulting document state:**

```
tree:         [["Body", "PartDesign::Body"]]
recompute:    OK, failing_objects: []
verify_shape: OK
```

So the document is **valid** — not corrupt, not broken. The geometry recomputes and the shape
checks out. The mismatch is between the restored document's *digest* and the recorded
pre-mutation digest.

**That distinction is the thing to investigate.** Two very different causes fit the evidence:
1. The restore genuinely lost or changed something (a real data-integrity bug), or
2. The fingerprint is not stable across a save/reload cycle — the snapshot round-trips the document
   through `saveCopy` and reopen, and some serialized detail (an element map, a touched flag, an
   object ordering) differs even though the geometry is identical.

Cause 2 would make the escalation a **false alarm** that fires on every snapshot restore, which
would be bad in a different way: it trains a reader to ignore the one signal that means "your
document may be damaged". Determine which it is before designing a fix — compare the restored
document's fingerprint against a freshly-saved-and-reloaded copy of a known-good document.

---

### UAT-30 — `FCB_TMP_snap_*` directories leak into the temp directory

- **Severity:** medium
- **Area:** product (hygiene)
- **Found in:** observed while investigating UAT-29
- **Status:** open

**What happened.** **Nine** `FCB_TMP_snap_*` directories were found under
`C:\Users\thuan\AppData\Local\Temp\` after this run:

```
ls -d "$TEMP"/FCB_TMP_snap_* | wc -l   ->  9
```

TC-05-02 CP3 asserts no stale snapshot directory survives a completed mutation, and that checkpoint
passed for the mutations it watched — so the leak is not on the normal path.

**Likely sources, in order of confidence.**
1. **The escalation path (UAT-29).** That snapshot is *deliberately* preserved so the document can be
   recovered, so it is correct that it survives — but nothing ever cleans it up afterwards, and no
   tool tells the operator it is safe to delete.
2. **Crashed or killed runs.** FreeCAD was force-killed twice during this session (UAT-28). A
   snapshot taken mid-transaction has no owner left to remove it.

**Why it matters.** Each snapshot is a full `.FCStd` copy of the working document. On a long
session with large models this consumes real disk, and the directories are permission-restricted
(reading one back required elevation), so ordinary temp cleanup may not reclaim them.

**Fix direction.** Sweep orphaned `FCB_TMP_snap_*` directories at bridge start, which is where a
crashed predecessor's leftovers can be identified safely. This is close to the AD-25 session-working-
directory gap already recorded as TC-99-04 — a per-session directory would make both problems one
problem. Snapshots deliberately kept for recovery should be moved somewhere the operator is told
about, not left in the process temp directory.

---

### UAT-29 addendum — experiment result: cause 2 CONFIRMED, cause 1 refuted

The two candidate causes were separated by direct experiment
(`_automation/uat/probe_fp_roundtrip.py`, `peek_stable.py`, `peek_which.py`).

**Experiment 1 — is the digest stable in place?** Three consecutive reads of the same untouched
document:

```
call 1: 37d925dbeba5031903d8da9d17cfcaa3b1ec4111f2943894f8870a38df80c996
call 2: 37d925dbeba5031903d8da9d17cfcaa3b1ec4111f2943894f8870a38df80c996
call 3: 37d925dbeba5031903d8da9d17cfcaa3b1ec4111f2943894f8870a38df80c996
STABLE IN PLACE
```

The same value also reproduced on a separately rebuilt, identical plate — so the digest is
deterministic for identical geometry within a session.

**Experiment 2 — does it survive the snapshot's own mechanism?** Build a 40x25x15 plate, save to a
fresh path, close, reopen. **No mutation at any point.**

```
digest BEFORE save  = 37d925dbeba5031903d8da9d17cfcaa3b1ec4111f2943894f8870a38df80c996
digest AFTER reopen = 8ccdfa4df4f671cea1100b49c6afed4a9421ba34775fe0501529484f5b725a3d
```

**Experiment 3 — did anything observable actually change?** Every measurable property is identical:

```
objects identical: True   [B/Body, P1/Pad, S1/Sketch]
volume identical : True   15000.0
area identical   : True   3949.999999999999
com identical    : True
```

**Verdict: the restore is not losing data. The fingerprint cannot survive its own snapshot
mechanism.**

Since the snapshot path is `saveCopy` -> reopen, and the digest changes across exactly that
round trip while the geometry does not, **every snapshot-based rollback reports
`rollback_proven: null` and "could not be proven"** — regardless of whether the document was
correctly restored. The escalation seen in TC-05-06 is a false alarm.

**Why this matters more, not less, than a restore bug.** The message is alarming and names a real
recovery path, so a reader who sees it on a genuinely-correct rollback learns to discount it. The
one signal that should mean "your document may be damaged" fires when nothing is wrong, which is
how a real occurrence gets ignored.

**Where the instability must be.** `fingerprint()` (`usecases/fingerprint.py:142-175`) hashes, per
object in `Name` order, `{name, brep_sha256, massprops}`. Experiment 3 shows `name` order and the
mass properties are preserved, so the moving part is `brep_sha256` — the SHA-256 of
`_serialize(shape)`, which is `shape.exportBinary` on this build (banner: `serializer: exportBinary`).
`fingerprint.py:67` calls that format "byte-deterministic", and it is **within** a session; the
evidence here is that it is not byte-identical for a shape that has been through a
save/reopen cycle.

**Fix direction.** Do not weaken the rollback proof to make the symptom go away — the proof is the
valuable part. Either:
1. Make the comparison serialization-stable: compare the *structured* fingerprint entries
   (geometry, mass properties, object identity) rather than raw serialized bytes, so a re-read
   shape with identical geometry compares equal; or
2. Re-read the pre-mutation fingerprint through the same save/reopen path used for the snapshot, so
   both sides of the comparison have the same provenance.

Option 1 is the sounder fix: a fingerprint whose value depends on whether the document has been
reloaded is surprising anywhere it is used, not only in rollback. Note AD-6 requires the fingerprint
be a geometry digest — a digest that changes without a geometry change arguably already violates it.

**Suite consequence.** Any checkpoint asserting `rollback_proven: "rolled_back_verified"` will pass
only on the **in-memory abort** path (which does not round-trip and is what TC-05-05 exercises), and
will fail on the **snapshot restore** path. Those two paths must be asserted separately.
