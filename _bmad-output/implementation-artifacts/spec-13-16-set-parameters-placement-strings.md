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

- `src/freecad_buddy/usecases/features.py:2253-2335` -- `_parameter_writes`, `_property_family`, `_parameter_value`: add `placement` and `string` families.
- `src/freecad_buddy/usecases/features.py:2339-2390` -- `feature_set_parameters`: no-op shortcut, `state_probe`, `recompute_check`, `report`, unique transaction label.
- `src/freecad_buddy/usecases/features.py:2459-2480` -- `ParameterRefusal`, `_storable_text`: reuse for strings; `:2869` `_EXPRESSION_CALLS`, `:3095` unattached-offset rule: model.
- `src/freecad_buddy/usecases/features.py:358-420` -- `_feature_mutation` (`report` replaces `feature` and `feature_state`; `report` must return both).
- `src/freecad_buddy/usecases/transaction.py:82` `RecomputeFailure`, `:368-424` state proof: reuse.
- `src/freecad_buddy/hosts/tool_catalog.py:871-890` -- `feature_set_parameters` schema text only.
- `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md:104,192,576` -- row, carve-out note, validation line.
- `skills/freecad-scripting-idioms/SKILL.md:74-78` -- the typed-tool list; `references/gap-list.md:33,42` rows stay for Story 19.
- Probes (FreeCAD 1.1.4): a sketch `Placement` write on an attached sketch and on a Pad is reset to 0 by the recompute; a Body `Placement` write holds; `Label` `Pad` becomes `Pad001`; a NUL cuts a label; `doc.undo()` restores both properties.

## Tasks & Acceptance

**Execution:**
- [ ] `features.py` -- `_placement_value(raw, what, current=None)`, `string` family, helpers for equality, probe, read-back -- shared parser, Story 13-17 reuses it
- [ ] `features.py` -- `feature_set_parameters`: no-op shortcut, `state_probe`, `recompute_check`, `report` (`label`, `undo_steps`) -- L5, L6, L8
- [ ] `tool_catalog.py` -- `feature_set_parameters` description and `parameters` schema text -- agents discover the new types
- [ ] `mcp-tools-design.md`, `SKILL.md` -- row, validation line, carve-out note, typed-tool list -- design and skill match the code
- [ ] `tests/infc/test_set_parameters_placement.py`, `tests/infc/test_confirm_gate.py` -- cases below, each `test_Should_<outcome>_When_<condition>` -- every matrix row, planted rollback mismatch, undo, confirm gate
- [ ] `tests/uat/testcases/TC-20-set-parameters-placement-strings.md` -- placement and label cases for the container verifier

**Acceptance Criteria:**
- Given a Body, when `Placement` with only `base.x` is written, then y, z and rotation equal their previous values and `document_undo` restores the old placement.
- Given a forced failure after a placement write, when the bracket rolls back, then the state probe equals its pre-op reading and a planted mismatch turns the proof false.
- Given a `Label`-only call without `confirm` under `AUTO_APPROVE=0`, then the call is refused (the gate stays).

## Implementation Notes

- Probe (FreeCAD 1.1.4): the `Placement` of an attached sketch and of a Pad inside a Body is `ReadOnly` in `getEditorMode`, so the existing read-only refusal catches them before the bracket (the message now names `AttachmentOffset`). The read-back (`parameters.value_overwritten`) remains for a value an expression or a Python feature rewrites; the tests use an expression-bound Body and a `Part::FeaturePython` that resets its placement.
- Mutants (each turns the named tests red): skipping `recompute_check` fails the Python-feature, expression and rollback-proof tests; `state_probe=None` fails the rollback-proof test.
- `_feature_mutation` gained `keep_state` so a `report` adds fields without dropping `feature` and `feature_state` from a failed result.

## Spec Change Log

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

## Verification

**Commands:**
- `uv run ruff check .` and the gates in `epic-13-status.md` -- expected: pass
- `freecadcmd` `tests/run_tests.py` with private cfg and `FREECAD_USER_HOME` -- expected: all pass
- `uv run --extra dev pytest tests/external -q` (Git Bash) -- expected: pass
