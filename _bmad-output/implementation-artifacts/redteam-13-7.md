# Story 13-7: red team report

Diff: `bda755e...8e381d9` (branch `story/13-7-query-interference`). Copy: detached worktree at `8e381d9`, removed after the run.
Probes: host `freecadcmd.exe` 1.1.4 with private `-u`/`-s` cfg files in the scratchpad. Every probe purges `freecad_buddy` from `sys.modules` and inserts the worktree `src` first; the probe prints `queries from D:\Work\Personal\Sources\fcb-redteam-13-7\src\freecad_buddy\usecases\queries.py`, so the installed addon copy does not shadow the code under test.
Known items (ledger R1-*, R1-D1..D3, spec triage rows 1-18) are not re-reported.

Probe command form (all rows below):

```
"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" -u <scratch>\user.cfg -s <scratch>\system.cfg <scratch>\probeN.py
```

## Reproduced

| RT | Severity | Q | File:line | Finding |
| --- | --- | --- | --- | --- |
| RT-1 | high | Q5, CAP-1 | `usecases/queries.py:767` | A real failed boolean with one shape inside the other reads as disjoint, `boolean_failed` false |
| RT-2 | high | Q4, CAP-1 | `usecases/queries.py:756` | A reversed solid (`Part::Reverse`, `isValid()` true) gives a wrong common volume, and 0 with a positive distance when the other part is inside it |
| RT-3 | medium | Q3, Q6 | `usecases/queries.py:767-770` | A closed shell (mesh converted to shape) that contains a solid reads disjoint 40 mm; a shell that crosses a solid reads 0 / 0 / false, with no signal in the record that an input is not a solid |
| RT-4 | low | Q12 | `contracts/numbers.py:27`, `usecases/queries.py:687` | Through the MCP adapter, a common volume below 1e-9 mm^3 becomes `0.0` in `structuredContent` while `text` counts the pair as overlapping |
| RT-5 | low | Q11 | `hosts/tool_catalog.py:1307`, `mcp-tools-design.md` §3.2.3 | A PartDesign feature inside a moved Body is measured in Body-local frame; the description and design name only `App::Part` and `App::Link` |

### RT-1 (high, Q5): the distance fallback does not detect containment, so a failed boolean reads as clearance

The safety rule rests on one assumption: when the shapes overlap, `distToShape` returns 0. That is false when one shape is invalid. OCC `BRepExtrema_DistShapeShape` finds an inner solution only for a valid solid. For an invalid solid, and for a `Compound`, it returns the distance to the boundary.

The bowtie solid is the same planted failed boolean that the Story's infc test uses. Place a box inside one lobe of the bowtie material: `common` returns an empty Compound, and `distToShape` returns the box-to-edge distance 7.07 mm. `_measure_interference` then takes the branch at `queries.py:767`:

```python
    if distance is not None and distance > _CONTACT_DISTANCE_MM:
        return 0.0, distance, False
```

Reproduction (`probe4.py`, through `queries.query_interference`):

```python
corners = [(0, 0), (100, 100), (100, 0), (0, 100), (0, 0)]
wire = Part.makePolygon([V(x, y, 300) for x, y in corners])
feat("Bowtie", Part.Face(wire).extrude(V(0, 0, 100)))
feat("InLobe", Part.makeBox(10, 10, 10, V(70, 40, 340)))   # fully inside the right lobe
queries.query_interference(reg, doc=h, pairs=[["Bowtie", "InLobe"]])
```

Output:

```
{"a": "Bowtie", "b": "InLobe", "common_volume": {"value": 0.0, "unit": "mm^3"}, "min_distance": {"value": 7.0710678118654755, "unit": "mm"}, "boolean_failed": false}
5 pair(s), 4 overlapping, 0 boolean failed.
```

Raw kernel values (`probe3.py`): `bowtie isValid False Volume 0.0`; `bowtie vs inner box: common Compound 0 0.0 dist 7.0710678118654755`. The same bowtie with a box that crosses its boundary gives `(None, 0.0, True)`, which is the only case the infc test covers.

The same gap exists for a valid `Compound`: `Part.makeCompound([big]).distToShape(small)[0]` is `40.0` for a small box inside `big`, while `big.distToShape(small)[0]` is `0.0` (`probe3.py`: `compound(big) vs small: ... dist 40.0`). Here `common` succeeds (volume 1000), so no false reading was produced with a valid compound; but the design statement "`min_distance` ... is 0 when the shapes touch or overlap" (`mcp-tools-design.md` §3.2.3, T-2) is false for a compound that contains the other shape.

Effect: an empty `common` produced by a failed boolean reads as "no overlap, 7 mm clearance". This is the exact false pass that CAP-1 forbids. The Q5 row text ("empty while `min_distance` is 0") is met literally, but the property it protects is broken. Possible fix direction (not applied): treat an empty `common` as failed when either input fails `isValid()`, or test one vertex of each shape with `isInside` against the other before trusting a positive distance.

### RT-2 (high, Q4): a reversed solid is intersected as its complement

`Part::Reverse` (Part workbench "Reverse shapes") outputs a solid with `Orientation` `Reversed`. It passes `isValid()` and `check(True)`, and its `Volume` is negative. OCC Boolean treats a reversed solid as the material outside its faces. So `common` returns the other shape minus the overlap, not the overlap. The `abs()` at `queries.py:756` (triage row 5, "a solid with reversed orientation reports a negative volume for a real overlap") does not fix this: the volume of the real result is positive and wrong. The triage-5 test uses a fake shape object and never meets this kernel behaviour.

Reproduction (`probe3.py`, raw shapes):

```python
rb = Part.makeBox(100, 100, 100).reversed()
print("reversed isValid", rb.isValid(), "Volume", rb.Volume)
print(queries._measure_interference(box().reversed(), box(5, 5, 5)))   # analytic overlap 125
```

Output:

```
reversed isValid True Volume -999999.9999999999 check ok
1b tool reversed vs overlap 125: (875.0000000000001, 0.0, False)
```

Reproduction through the document and the RPC dispatch (`probe2.py`): `Big` is a 100 mm box, `Rev` is `Part::Reverse` of `Big`, `Small` is a 10 mm box inside `Big`.

```
Rev shape Solid Reversed -999999.9999999999
{"a": "Rev", "b": "Small", "common_volume": {"value": 0.0, ...}, "min_distance": {"value": 40.0, ...}, "boolean_failed": false}
{"a": "Big", "b": "Small", "common_volume": {"value": 999.9999999999998, ...}, "min_distance": {"value": 0.0, ...}, "boolean_failed": false}
```

Same geometry, two answers: `Big` gives 1000 mm^3 overlap; `Rev` gives no overlap and 40 mm clearance. Q4 ("`common_volume` equals the analytic overlap volume") fails for a valid input, and in the contained case the overlap reads as zero.

### RT-3 (medium, Q3/Q6): a closed shell reads as clearance when it contains a solid

Part > "Create shape from mesh" outputs a closed `Shell`, not a `Solid` (`mesh shape type Shell True`). The design covers a shell whose `common` is non-empty with zero volume, but not containment. With a solid inside the shell, `common` is empty and `distToShape` measures to the faces.

Reproduction (`probe2.py`, through dispatch): `MeshShell` from `MeshPart.meshFromShape` of a 100 mm box plus `makeShapeFromMesh`; `Inside` is a 10 mm box inside it.

```
{"a": "MeshShell", "b": "Inside", "common_volume": {"value": 0.0, "unit": "mm^3"}, "min_distance": {"value": 40.0, "unit": "mm"}, "boolean_failed": false}
```

Raw (`probe1.py`): `2b closed shell partly overlaps solid | common ('Compound', 1, 0.0) | dist 0.0 | tool (0.0, 0.0, False)`. That 0 / 0 / false record is identical to a record for a face that touches. The record carries no flag that an input is not a solid, so the agent cannot tell "touching" from "the shell crosses the part".

### RT-4 (low, Q12): MCP rounding turns a tiny real overlap into `0.0`

`round_floats` sets a magnitude below `_ZERO_FLOOR = 1e-9` (`contracts/numbers.py:27`) to `0.0`. This applies to `structuredContent`, which is the only part Claude Code reads. Triage row 14 rejected the text-only form with "structured value is exact"; through the adapter it is not.

Reproduction: `probe2.py` boxes `C1` at `(0,0,500)` and `C2` at `(10-5e-4, 10-5e-4, 510-5e-4)`, 10 mm each (corner overlap 5e-4 mm per axis); envelope written to JSON, then passed through `adapters.mcp_server._to_call_result` from the `uv` env (`mcpround.py`).

```
raw:  {"a": "C1", "b": "C2", "common_volume": {"value": 1.2499999999734967e-10, ...}, "min_distance": {"value": 0.0, ...}, "boolean_failed": false}
MCP structuredContent: {"a": "C1", "b": "C2", "common_volume": {"value": 0.0, "unit": "mm^3"}, "min_distance": {"value": 0.0, ...}, "boolean_failed": false}
MCP text: 5 pair(s), 3 overlapping, 0 boolean failed. ... C1/C2: common volume 0.0 mm^3.
```

Sub-micron overlap, so low; but the text and the structured content disagree on whether the pair overlaps.

### RT-5 (low, Q11): Body-local frame for PartDesign features is not named

`probe5.py`: `PartDesign::Body` at `(100,0,0)` with a 10 mm `PartDesign::AdditiveBox` `ABox`; `Obstacle` at `(105,0,0)`.

```
ABox.Shape bbox BoundBox (0, 0, 0, 10, 10, 10) Body.Shape bbox BoundBox (100, 0, 0, 110, 10, 10)
{"a": "Body", "b": "Obstacle", "common_volume": {"value": 499.9999999999999, ...}, "min_distance": {"value": 0.0, ...}, "boolean_failed": false}
{"a": "ABox", "b": "Obstacle", "common_volume": {"value": 0.0, ...}, "min_distance": {"value": 95.0, ...}, "boolean_failed": false}
```

The frame limit is known (R1-D1, triage row 6). The gap is that the tool description says "container-local frame" and the design text names only `App::Part` and `App::Link`; a feature name inside a Body is the most common PartDesign input and reads as 95 mm clearance. A sentence that says "name the Body, not its features" closes it.

## Not reproduced or checked clean

| Area | Result |
| --- | --- |
| Order of a/b | Every probe pair gives the same record in both orders (`probe1.py` "reversed-order tool" column) |
| Self pair, Origin, unknown name | `['Body','Body']` → `ValidationError a pair must name two different objects: Body`; `Origin` → `object has no queryable shape: Origin` |
| Label vs Name | Pair `["Body","ABox"]` with `Obstacle.Label == "ABox"` resolves the object whose Name is `ABox` (Name only, as specified) |
| Hidden object | `Big.Visibility = False` still measured (1000 mm^3) |
| Read-only (Q8) | `UndoCount` 0 and no `Touched` object before and after a 5-pair call (`probe2.py`) |
| Self-overlapping `Part::Compound` | Correct volumes (1000, 250); a coincident-face compound gives `boolean_failed` true (safe) |
| Tolerance | Gap 5e-4 mm → disjoint 5e-4; overlap 1e-4 mm → 0.01 mm^3; overlap 1e-8 mm → `boolean_failed` true (safe) |
| NaN volume or distance | Not reproduced with a real shape; code path covered only by fake-shape tests (low) |
| Duplicate pairs | Accepted and measured twice; triage row 13 (known) |
| Q9 timing | Not run here; R1-D2 open with the verifier |
| Datum axis as input | `X_Axis` is accepted and gives 0 / 0 / false against the Body; meaningless but not unsafe (low) |
| `query_mass_properties` regression | Diff adds code after it and changes no line of it; 44/44 `infc.test_query_tools` pass on worktree source |
| Gates | `ruff check` pass, `check_imports` OK, `check_status_vocab` OK, `gen_schemas --check` OK, `pytest tests/external -k "mcp_surface or readonly_profile"` 96 passed |
| Schema through adapter | `_tool_for` passes `input_schema` as is; nested `pairs` items, bounds and `additionalProperties: false` match T-2 plus `minItems: 1` (triage row 3) |

## Verdict

**FAIL.** RT-1 and RT-2 make a real overlap read as "no overlap with positive clearance" (`common_volume` 0, `boolean_failed` false), which is the false pass CAP-1 and Q5 exist to prevent. RT-2 also breaks Q4 on a valid shape. Both rest on the same unchecked assumption: that an empty `common` with a positive `distToShape` proves the shapes are apart.
