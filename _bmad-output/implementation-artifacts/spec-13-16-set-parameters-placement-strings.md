---
title: 'feature_set_parameters writes placement and strings'
type: 'feature'
created: '2026-11-25'
status: 'done'
baseline_commit: 'bde93e330636e418eb0da4b341a9d9f6ca46fb15'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-13-lessons.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-13-decisions.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `feature_set_parameters` refuses `App::PropertyPlacement` and `App::PropertyString` (`features.py:_property_family` returns `None`). An agent that must place a Body or rename a Label drops to `script_exec` (CAP-3, T-4).

**Approach:** Add two value families to `_parameter_value`: `placement` (shared parser `_placement_value`, reused by Story 13-17) and `string` (including `Label`). Prove rollback of property-only writes with a `state_probe`, and read each written placement or string back after the recompute so a value FreeCAD overwrites is never reported as stored.

## Boundaries & Constraints

**Always:**
- Placement wire shape: `{ "base": {"x": Q, "y": Q, "z": Q}, "rotation": { "axis": [x, y, z], "angle": Q } }`; `Q` is `{value, unit}` (length units for `base`, angle units for `angle`). Every key is optional and an omitted key keeps the current value, per component (`x`, `y`, `z`; `axis`; `angle`). With no current value (Story 13-17) the defaults are base (0, 0, 0) and no rotation.
- `axis` is three finite numbers, not all zero. Unknown keys, non-finite values, a wrong unit or a wrong type are `INVALID_INPUT` before the transaction opens.
- A string FreeCAD cannot store unchanged is refused with `parameters.invalid_string` (existing `_storable_text`). The `Label` result block `label: {requested, stored}` is returned because FreeCAD makes a label unique (`Pad` becomes `Pad001`).
- A placement or string that the recompute leaves different from the request (attachment, expression, a PartDesign feature) rolls the call back as `RECOMPUTE_ERROR`, `detail.code` `parameters.value_overwritten`, naming `<object>.<property>`. `Label` is exempt from the string check.
- A call whose writes are all placement or string and all equal the current values opens no transaction: `OK`, `unchanged: [...]`, `undo_steps: 0`, no `mutation` block (L6). Every other `OK` result gains `undo_steps`, measured from `UndoNames`.
- A `state_probe` reads the written properties back for the AD-5 proof (decisions 32, 46).
- `AttachmentOffset` on an object with `MapMode` Deactivated (FreeCAD hides and ignores it) is refused with `parameters.not_attached` (leader decision, same rule as decision 38).
- The no-op shortcut covers only calls whose writes are all placement or string (leader decision); numeric, bool and enum calls keep today's behaviour.
- `Visibility` stays the only display-state carve-out (`confirm._is_display_state`): a `Label` or placement write keeps the confirm gate.

**Never:**
- No change to `script_exec.py`, `tnp_guard.py`, `confirm.py`, or any `tool_catalog.py` block except `feature_set_parameters`.
- No link, file, font or `Part::PropertyPartShape` writes; numeric, bool and enum behaviour does not change.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Place a Body | `Placement: {base: {x: 10 mm}}` | x = 10, y and z and rotation kept; `OK`; `undo_steps: 1` | N/A |
| Rotate | `Placement: {rotation: {axis: [0,0,1], angle: 90 deg}}` | base kept, rotation set | N/A |
| Same value | `Placement` equal to current | `OK`, `unchanged: ["Placement"]`, `undo_steps: 0` | no step recorded |
| Attached sketch | `Placement` on a sketch with `MapMode` FlatFace | rolled back, value unchanged | `RECOMPUTE_ERROR` `parameters.value_overwritten` |
| Feature in a Body | `Placement` on a Pad | rolled back | same |
| Bad axis | `axis: [0,0,0]` or `[1,2]` or unknown key | nothing written | `INVALID_INPUT` |
| Label unique | `Label: "Pad"` while another object holds it | stored `Pad001`; `label: {requested: "Pad", stored: "Pad001"}` | N/A |
| Label NUL | `Label: "a\u0000b"` | nothing written | `INVALID_INPUT` `parameters.invalid_string` |
| Unattached offset | `AttachmentOffset` on a Body | refused, nothing written | `INVALID_INPUT` `parameters.not_attached` |
| Undo | `document_undo` after a placement or label write | prior value back | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/features.py` -- `_parameter_writes`, `_property_family`, `_parameter_value`: add `placement` and `string` families.
- `src/freecad_buddy/usecases/features.py` -- `feature_set_parameters`: no-op shortcut, `state_probe`, `recompute_check`, `report`, unique transaction label.
- `src/freecad_buddy/usecases/features.py` -- `ParameterRefusal`, `_storable_text`: reuse for strings; `_EXPRESSION_CALLS` and the unattached-offset rule of `feature_set_expression`: model.
- `src/freecad_buddy/usecases/features.py` -- `_feature_mutation` (`keep_state` keeps `feature` and `feature_state` beside a `report`).
- `src/freecad_buddy/usecases/transaction.py` -- `RecomputeFailure`, the state proof in `_prove_rollback`: reuse.
- `src/freecad_buddy/hosts/tool_catalog.py` -- `feature_set_parameters` schema text only.
- `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md` -- row, carve-out note, validation bullet and the after-validation paragraph.
- `skills/freecad-scripting-idioms/SKILL.md` -- the typed-tool list; `references/gap-list.md` rows 26, 33, 42 stay for Story 19.
- Probes (FreeCAD 1.1.4): a sketch `Placement` write on an attached sketch and on a Pad is reset to 0 by the recompute; a Body `Placement` write holds; `Label` `Pad` becomes `Pad001`; a NUL cuts a label; `doc.undo()` restores both properties.

## Tasks & Acceptance

**Execution:**
- [x] `features.py` -- `_placement_value(raw, what, current=None)`, `string` family, helpers for equality, probe, read-back -- shared parser, Story 13-17 reuses it
- [x] `features.py` -- `feature_set_parameters`: no-op shortcut, `state_probe`, `recompute_check`, `report` (`label`, `undo_steps`) -- L5, L6, L8
- [x] `tool_catalog.py` -- `feature_set_parameters` description and `parameters` schema text -- agents discover the new types
- [x] `mcp-tools-design.md`, `SKILL.md` -- row, validation line, carve-out note, typed-tool list -- design and skill match the code
- [x] `tests/infc/test_set_parameters_placement.py`, `tests/infc/test_confirm_gate.py` -- cases below, each `test_Should_<outcome>_When_<condition>` -- every matrix row, planted rollback mismatch, undo, confirm gate
- [x] `tests/uat/testcases/TC-20-set-parameters-placement-strings.md` -- placement and label cases for the container verifier

**Acceptance Criteria:**
- Given a Body, when `Placement` with only `base.x` is written, then y, z and rotation equal their previous values and `document_undo` restores the old placement.
- Given a forced failure after a placement write, when the bracket rolls back, then the state probe equals its pre-op reading and a planted mismatch turns the proof false.
- Given a `Label`-only call without `confirm` under `AUTO_APPROVE=0`, then the call is refused (the gate stays).

## Implementation Notes

- Probe (FreeCAD 1.1.4): the `Placement` of an attached sketch and of a Pad inside a Body is `ReadOnly` in `getEditorMode`, so the existing read-only refusal catches them before the bracket (the message now names `AttachmentOffset`). The read-back (`parameters.value_overwritten`) remains for a value an expression or a Python feature rewrites; the tests use an expression-bound Body and a `Part::FeaturePython` that resets its placement.
- Mutants (each turns the named tests red): skipping `recompute_check` fails the Python-feature, expression and rollback-proof tests; `state_probe=None` fails the rollback-proof test.
- `_feature_mutation` gained `keep_state` so a `report` adds fields without dropping `feature` and `feature_state` from a failed result.

## Spec Change Log

- Round 1 and 2 (leader-authorised, after approval): the read-back covers every written family (numeric, boolean, enumeration, placement, string except `Label`), not only placement and string, so an expression-bound or clamped numeric write fails as `parameters.value_overwritten`; this narrows the Always rule "numeric, bool and enum behaviour does not change" for a value the recompute reverts and changes nothing for a value that holds. A rotation axis outside 1e-100..1e100 and an `axis` without an `angle` while the current rotation is zero are refused (silent changes of the stored value, L8). Matrix row "Unattached offset" names a Body, which has no `AttachmentOffset` property; the refusal applies to an attachable object with `MapMode` Deactivated (property status `Hidden`), tested on an unattached sketch. Rows 4 and 5 of the matrix: the attached sketch and the Pad are refused before the bracket as `INVALID_INPUT` (read-only `Placement`), accepted by the leader. KEEP: pre-bracket read-only refusal, read-back after the recompute, `state_probe`, no-op before the gate.

## Review Triage Log

Round 1 (blind a91118f7dae0452aa, edge ae707f991cc5f9719, gap a33ff8044dd65939f):

| # | Finding | Verdict | Route and evidence |
|---|---------|---------|--------------------|
| 1 | gap-list rows 33 and 42 still route placement and Label to `script_exec` | low | defer: the plan assigns the row removal to Story 13-19 |
| 2 | failed call loses `feature` and `feature_state` (`report` replaced them) | medium | patch: `_feature_mutation(keep_state=True)`; test `Should_name_the_feature_and_its_state_When_the_call_rolls_back` |
| 3 | no-op path runs before the confirm gate and writes no audit line | low | patch: same order as `feature_parameters_define` and `feature_set_expression`; design row states it; test in `test_confirm_gate.py` |
| 4 | design doc has no output contract for `label`, `unchanged`, `undo_steps` | low | patch: added to the `mcp-tools-design.md` validation bullet |
| 5 | `value_overwritten` sits under the `INVALID_INPUT` list; `AttachmentOffset` hint wrong for a Pad | low | patch: doc names the after-bracket status and the Body case |
| 6 | read-back covers placement and string only; an expression-bound numeric still reverts | medium | patch (round 2, leader): the read-back covers every written family; test Should_roll_back_When_an_expression_drives_a_numeric_property |
| 7 | exact `isSame` versus rounded probe | false | exact equality holds: test `Should_store_the_rotation_exactly_When_the_axis_is_not_a_unit_vector`; the probe is rounded only to survive a snapshot reload |
| 8 | schema text lacks the `axis` list shape and the no-bare-number rule | low | patch: `tool_catalog.py` text |
| 9 | TC-20 setup incomplete; coverage matrix row missing | low | patch |
| 10 | `ParameterRefusal` docstring | low | patch |
| 11 | duplicated undo-step code | low | patch: `_recorded_undo_steps`, used by both tools |
| 12 | test structure: no Arrange marker; `{}` placement; string overwrite; unattached precondition | low | patch |
| 13 | axis length beyond about 1e154 or below 1e-154, or a huge int, becomes Z or raises `OverflowError` | medium | patch: refuse outside 1e-100..1e100; probed bounds in a comment; test |
| 14 | axis without angle while the current rotation is zero is dropped | medium | patch: refuse |
| 15 | empty Label stored | low | reject: FreeCAD accepts it and undo restores it; a guard adds a rule the contract does not state |
| 16 | `MapMode` and `AttachmentOffset` in one call checked against the pre-call state | low | reject: the refusal names the cause and a second call works |
| 17 | `Visibility` is not restored by abort, so the probe escalates to a snapshot restore | low | reject: the probe reports the true state; the escalation restores it |
| 18 | repeated Label write already made unique runs the bracket | low | reject: reports `undo_steps: 0` truthfully; rare |
| 19 | preview of a Label-only call shows no fingerprint change | low | reject: decision 46 (AD-6 blind to property-only changes) |
| 20 | Tasks name `test_feature_tools.py` | low | patch: spec Tasks text corrected |

Round 2 (blind a81d9eb183201e75f, edge a34a89c4e42a1344f, gap a1943a2149033081f), carried rows are the same claim as round 1:

| # | Finding | Verdict | Route and evidence |
|---|---------|---------|--------------------|
| 21 | plain float with 17 digits reopens as 16 digits, so the snapshot-restore probe reads a mismatch (SPEC_FAILED) | high | patch: `_comparable` rounds floats; test `Should_prove_the_snapshot_restore_When_a_float_and_a_length_hold_17_digits`; mutant red |
| 22 | no passing test of the read-back for an angle or a unitless float; quantity branch of the probe untested | medium | patch: `NumericWriteTest` and the rollback test above |
| 23 | read-only `Placement` of a feature in a Body gives no next step | low | patch: hint "move the Body"; test asserts it |
| 24 | catalog text omits `value_overwritten` | low | patch |
| 25 | design bullet mixes before-bracket refusals with after-bracket and output rules; `DuplicateLabels`; transaction name counter | low | patch: separate paragraph |
| 26 | spec record: tasks unchecked, Change Log empty, Code Map lines stale, frozen rules contradicted | low | patch: Change Log entry, tasks checked, Code Map without line numbers |
| 27 | Placement-only call has no gate test | low | patch: `Should_keep_the_gate_When_only_a_placement_is_written` |
| 28 | TC-20 claims undo of the label and a visual for the offset without a step | low | patch |
| 29 | `Visibility` abort escalates to a snapshot restore | low | carried (r1 #17) |
| 30 | `MapMode` Deactivated and `AttachmentOffset` in one call | low | carried (r1 #16) |
| 31 | empty `Label` | low | carried (r1 #15) |
| 32 | angle-only rotation on a zero rotation turns about Z | low | reject: Z is the axis of the identity rotation; the stored value is the one requested |
| 33 | refuse an expression-bound target before the bracket and name the expression | low | reject: the leader chose the read-back; a pre-check adds a second mechanism |
| 34 | no-op uses exact equality | low | carried (r1 #7) |
| 35 | gap-list row 42 says "string or link"; narrow it, do not remove it | low | defer: Story 13-19 owns the gap list; deferred entry corrected |
| 36 | decisions log has no 13-16 entry | low | leader owns `epic-13-decisions.md`; noted in the report |
| 37 | validation runs before the confirm gate in the no-op path | low | carried (r1 #3) |

Round 3 (blind a6bfb8fa3172353c2, edge a1d2efbdedff6878a, gap a39c40cbf481743d3), the last round:

| # | Finding | Verdict | Route and evidence |
|---|---------|---------|--------------------|
| 38 | `not_attached` tested the `Hidden` property status; an object attached before its support had a shape keeps the offset hidden and still applies it, so a valid write was refused | medium | patch: test `MapMode`, as the spec says; stub tests; mutant (back to `Hidden`) red |
| 39 | `isclose` rel 1e-9 accepts an integer that a clamp moved by one part in a billion (2**31 against 2**31 - 1) | medium | patch: integers compare exactly; test; mutant red |
| 40 | 9-decimal rounding in the probe hides a 1e-7 to 1.001e-7 change and NaN never equals itself | low | patch: 15 significant digits, NaN read as "nan"; test; mutant red. The large-value claim is false: FreeCAD saves fixed decimals, so a 1e8 value reloads exactly |
| 41 | failure message blames an expression for a clamp; no AttachmentOffset hint when an attached object's Placement is not ReadOnly | low | patch: message names a limit of the property, and the attached hint; clamp test (cylinder angle 400 -> RECOMPUTE_ERROR) |
| 42 | skills still say an expression-bound write resets with no error (`verification-kit.md:141`, `gap-list.md:26`) | low | patch the kit; gap-list line added to the Story 13-19 deferred entry |
| 43 | read-only hint omits the sketch `AttachmentOffset` option | low | patch |
| 44 | TC-20-02 visual has no before image | low | patch |
| 45 | Code Map line numbers; Always rules still read "numeric behaviour does not change" | low | patch the Code Map; the frozen text is covered by the Change Log entry |
| 46 | no-op shortcut still excludes numeric writes | low | carried (leader decision, Always rule) |
| 47 | tests for the boolean, enumeration and integer read-back | low | reject: existing success-path tests (`Type`, `Occurrences`, `Visibility`) run through the same read-back and pass |
| 48 | negative length passes validation and fails after the bracket | low | reject: the call fails with a rollback and names the property; a pre-bracket rule would add a numeric rule outside the Story |

### Red-team round (`redteam-13-16.md`)

| # | Finding | Sev | Outcome |
| --- | --- | --- | --- |
| T1 | rollback probe reads floats at 15 significant digits; FreeCAD stores 16 decimals, so a value near 1/3000 or 0.5 deg reads as a failed rollback | high | patch: `_Reading` compares each float pair within `1e-15 * max(1, abs(a), abs(b))`. Measured over 300 random placements (1e-8 to 1e12) plus 1/3000, 0.5 deg and 0.1 + 0.2, saved and reopened: largest error 5.6e-17 absolute, 18 times inside the rule. Red first: `RollbackProofTest` small-values case |
| T2 | base x or angle 10**400 raised `OverflowError` -> `RECOMPUTE_ERROR` | med | patch: `_is_finite` catches `OverflowError`; `INVALID_INPUT` naming the field; parser and bare-number tests |
| T3 | no bound on a base component; 1e150 commits, then the fingerprint fails | med | patch: `parameters.out_of_range` above 1e9 mm. Measured: the fingerprint raises `FreeCADError` at 1e118 mm on a Body and a `Part::Box`, mass properties still read; 1e9 mm is nine orders inside |
| T4 | stub test models a clamp FreeCAD never does; a real write of 2**31 fails inside the bracket | med | patch: integer writes beyond +-2147483647 refused before the bracket (`parameters.out_of_range`); stub test replaced by a real-property test; a recompute that lowers 2**31-1 by one is still reported (exact compare) |
| T5 | OK placement result does not report the stored placement | low | patch: `placements: {property: {requested, stored}}`, stored in the wire shape |
| L-2 | hidden-offset test uses a stub | low | comment states why the real state is not built |

## Verification

**Commands:**
- `uv run ruff check .` and the gates in `epic-13-status.md` -- expected: pass
- `freecadcmd` `tests/run_tests.py` with private cfg and `FREECAD_USER_HOME` -- expected: all pass
- `uv run --extra dev pytest tests/external -q` (Git Bash) -- expected: pass
