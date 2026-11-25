# Story 13-6: red team report

Diff: `116377e...61dd01f` (branch `story/13-6-mass-properties-objects`). Copy: detached worktree at `61dd01f`, removed after the run.
Probes: host `freecadcmd.exe -u <scratch>\user.cfg -s <scratch>\system.cfg <script>`. Every probe imported the worktree `src` (checked: `queries.__file__` = `D:\Work\Personal\Sources\fcb-redteam-13-6\src\freecad_buddy\usecases\queries.py`). No container, no port 8765/18765.

Baseline gates at `61dd01f`: `ruff check` clean; `check_imports OK`; `gen_schemas --check OK`; `ruff format --check` on the 3 changed code files clean; `pytest tests/external -q` 1864 passed, 4 skipped; in-FreeCAD `tests/run_tests.py` 875 tests OK (skipped=1), all 9 new `test_Should_*` mass tests ok.

## Reproduced

| RT | Severity | Q | file:line | Finding |
| --- | --- | --- | --- | --- |
| RT-1 | high (by the bar rule; fix is one word) | Q8 | `mcp-tools-design.md:131` | §2 row says `Volume/area/bbox/COM/inertia + topology counts + is_valid`. The record has no inertia field. |
| RT-2 | low | Q1 | `usecases/queries.py` `_mass_object_names` (`all(isinstance(name, str) and name ...)`) | No test pins the empty-name check from triage #4. A mutant without it passes both input tests. |
| RT-3 | low | Q6 | `usecases/queries.py` `_queryable_shape` / `_mass_record` | A feature in error that keeps its last shape gives an `OK` record, `is_valid: true` and the old volume. Nothing marks the error. Same on the `object` path (it existed before this Story). |
| RT-4 | low | Q3 | `usecases/queries.py` `_queryable_shape` | An empty compound is not null in OCC. It gives a full record with an inverted bbox (`xmin 1.797e308`, `xmax -1.797e308`) and `is_valid: true`, not `shape: null`. Same on the `object` path (it existed before this Story). |

### RT-1 reproduction

```
$ git show 116377e:<design>/mcp-tools-design.md | grep -n query_mass_properties
131:| `query_mass_properties` | 0 | Volume/area/bbox/COM/inertia + topology counts for an object | no |
$ git show 61dd01f:<design>/mcp-tools-design.md | sed -n 131p
| `query_mass_properties` | 0 | Volume/area/bbox/COM/inertia + topology counts + `is_valid` for one object, or for 1 to 50 objects (`objects`) | no |
$ grep -n "inertia\|Inertia\|Matrix" src/freecad_buddy/usecases/queries.py
(no output)
```

The record keys are `name, solid, volume, area, bbox, com, counts, is_valid` (`_mass_record`; §3.2.2 `MassRecord` agrees). The wrong word was already in the row before this Story. The Story rewrote the row and kept it, so Q8 ("§2 row ... match code") fails for this row. Fix: delete `/inertia`.

### RT-2 reproduction

Probe `mutant.py`: replace `queries._mass_object_names` with a copy that has no empty-name check (`isinstance(name, str)` only), then run the two input tests.

```
test_Should_map_both_or_neither_to_invalid_input_When_dispatched ... ok
test_Should_raise_validation_error_When_the_input_form_or_list_is_wrong ... ok
MUTANT empty-name check removed: wasSuccessful = True
```

`objects: ["Box", ""]` still returns `INVALID_INPUT` through `_resolve_object("")`, but the message is `missing required 'object' name`. Triage #4 patched that message. No test asserts the message, so the patch is not covered. Behaviour stays correct.

### RT-3 reproduction

Probe `probe2.py`: valid Pad (volume 500), then `Length = 0`, recompute.

```
before ['Up-to-date'] 499.9999999999999
Pad: Cannot create a pad with a total length of zero.
after ['Touched', 'Invalid'] False 499.9999999999999
STATUS OK
REC Pad <has shape> {'value': 499.9999999999999, 'unit': 'mm^3'} True
REC Body <has shape> {'value': 499.9999999999999, 'unit': 'mm^3'} True
```

The values equal what a script reading `Shape` gets, so Q7 holds. But `is_valid: true` on a feature in `Invalid` state can make an agent believe the part is good. A feature in error that never computed (`Pad001`, `State ['Touched','Invalid']`, probe1) gives `{name, shape: null}`, the same record as a Group.

### RT-4 reproduction

Probe `probe2.py`: `Part::Feature` "CN" with `Shape = Part.Compound([])`.

```
REC2 CN OK {"name": "CN", "solid": false, "volume": null, "area": {"value": 0.0, ...}, "bbox": {"xmin": {"value": 1.7976931348623157e+308, ...}, "xmax": {"value": -1.7976931348623157e+308, ...
OBJ2 CN OK True
```

Also, an infinite plane (`Part.Plane().toShape()`) gives `area 8e+100` and bbox `±1e+100`, status `OK`, on both paths. Both cases existed on the `object` path before this Story.

## Attacks that held (reproduced, no defect)

- Parity `object` vs `objects` for the same object (probe1): `True` for Box, App::Link, Pad, Sketch, hidden Cylinder, Vertex, Part::Compound, App::Line datum. For Group, App::Origin, an empty App::Part, a Body whose tip failed, and a never-computed failed Pad, `object` raises `no queryable shape` and `objects` gives `{name, shape: null}`. Q3 and Q5 require this.
- App::Link to a Box gives the linked solid (volume 1000). An App::Part that holds a Box gives the Box's record (probe4). A hidden object is measured the same as a visible one.
- Inputs at the use case (probe1): Label `MyBox` → `unknown object: MyBox`. `" Box"` → unknown. `[..., None]`, `[["Box"]]`, a tuple, `object=None, objects=None`, `object="" + objects` → all `ValidationError`. Duplicates are kept, in order (infc test).
- Real `tool_catalog` handler through `MethodRegistry.dispatch` (probe3): 50 names → `OK`, 50 records. 51 names, neither, both, `object` on a Group, an unknown name, `object: ["Box"]` → all `INVALID_INPUT` with the expected message.
- MCP gate (`schema_probe.py`; SDK `mcp` 1.28.1 runs `jsonschema.validate` on `inputSchema`): empty, 51, non-string item, a string, `null`, nested list → rejected. Neither, both and `["a", ""]` pass the schema and the use case rejects them. A `{"objects": [{name, shape: null}, record]}` structured content goes through `_to_call_result`. Floats round to `display_decimals` (`999.9999999999998` → `1000.0`), and `None` stays `None`. `structured_content` is `{"type": "object"}` in the envelope output schema.
- The GUI proxy passes `params` to the listener unchanged (`rpc_client.call`), so the same gate and use case apply. This was not run live: the brief forbids the container.
- No other `src` caller of `query_mass_properties`, `summarize_mass_properties` or the new helpers. `test_preview` and `tests/external/test_tool_summaries.py` stay green.

## Not reproduced

None.

## Verdict

**FAIL** on Q8 alone: RT-1, a one-word design-doc fix at `mcp-tools-design.md:131`. Q1 to Q7 hold under every attack above. RT-2, RT-3 and RT-4 are low.
