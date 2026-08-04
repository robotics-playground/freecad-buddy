# Required-field parity with FreeCAD — DW-104

## Problem

The wire schemas impose required fields the application does not, and omit requirements the
application does impose. Neither direction was ever checked. The operator's principle, recorded in
CLAUDE.md: **a field FreeCAD accepts as optional is optional on the wire, a field it requires is
required, and fields the bridge invents are ours to decide.**

## What "FreeCAD requires it" means here

A property having a default is not the test — `PartDesign::Revolution.ReferenceAxis` defaults to
`None` and the feature is then `Invalid` with no shape. The test used throughout this audit is
**does the feature recompute to a valid solid with the field left at its default**. Measured on
FreeCAD 1.1.1 by creating each type bare, wiring only the operands, and recomputing.

## Measured defaults

Every value below was read off a freshly created object on FreeCAD 1.1.1.

| type | property | default |
| --- | --- | --- |
| `PartDesign::Pad` | `Length` / `Length2` / `Type` | `10.0 mm` / `10.0 mm` / `Length` |
| `PartDesign::Pocket` | `Length` / `Length2` / `Type` | `5.0 mm` / `5.0 mm` / `Length` |
| `PartDesign::Revolution` | `Angle` / `Type` / `ReferenceAxis` | `360.0 deg` / `Angle` / `None` |
| `PartDesign::Hole` | `Diameter` / `Depth` / `DepthType` | `6.0 mm` / `25.0 mm` / `Dimension` |
| `PartDesign::Fillet` | `Radius` | `1.0 mm` |
| `PartDesign::Chamfer` | `Size` / `Angle` / `ChamferType` | `1.0 mm` / `45.0 deg` / `Equal distance` |
| `PartDesign::LinearPattern` | `Occurrences` / `Length` / `Offset` / `Mode` / `Direction` | `2` / `100.0 mm` / `10.0 mm` / `Extent` / `None` |
| `PartDesign::PolarPattern` | `Occurrences` / `Angle` / `Offset` / `Axis` | **`3`** / `360.0 deg` / `120.0 deg` / `None` |
| `PartDesign::Mirrored` | `MirrorPlane` | `None` |
| `PartDesign::Plane` | `AttachmentSupport` / `MapMode` | `[]` / `Deactivated` |
| `PartDesign::Body` | `BaseFeature` / `Group` | `None` / `[]` |

**`Occurrences` differs by pattern kind — 2 for linear, 3 for polar.** DW-104's own text records
"defaults `Occurrences=2`", which is true only of the linear case. A single wire default would be
wrong for one of the two kinds, which is an argument for omitting the field rather than
defaulting it on the wire.

## Measured recompute-without-the-field

| feature | field left at default | result |
| --- | --- | --- |
| Fillet | `Radius` = 1.0 mm | `valid=True`, `Up-to-date`, volume 997.854 |
| Chamfer | `Size` = 1.0 mm | `valid=True`, `Up-to-date`, volume 995.0 |
| LinearPattern | `Occurrences` = 2 | `valid=True`, `Up-to-date`, volume 250.0 |
| PolarPattern | `Occurrences` = 3 | `valid=True`, `Up-to-date`, volume 375.0 |
| Revolution | `ReferenceAxis` = None | `valid=False`, `Touched, Invalid`, no shape |
| Mirrored | `MirrorPlane` = None | `valid=False`, `Touched, Invalid`, no shape |
| Pad | `Profile` = None | `valid=False`, `Touched, Invalid`, no shape |
| Plane | `AttachmentSupport` = [] | `valid=True`, but `MapMode='Deactivated'`, placement at origin |

## Per-field rulings

### Drop from `required` — FreeCAD completes the op without them

| tool | field | why |
| --- | --- | --- |
| `feature_fillet` | `radius` | FreeCAD's 1.0 mm produces a valid fillet |
| `feature_chamfer` | `size` | FreeCAD's 1.0 mm produces a valid chamfer |
| `feature_pattern` | `occurrences` | FreeCAD's 2 (linear) / 3 (polar) produce valid patterns |

Each of these is required by the **use case** as well as the wire — `_positive_length(radius,
"radius")` raises on `None`, and `feature_pattern` rejects a non-integer `occurrences` before it
reaches the bracket. Dropping the field from the schema alone would move the rejection one layer
later without changing the answer. **Both layers change together**: the use case writes the
property only when the caller supplied it, and leaves FreeCAD's default in place otherwise.

`feature_pattern` already does exactly this for `angle` — its `validate_dimensions` docstring
says "a polar one may omit it to take the build's default sweep" — so the change makes `length`
and `occurrences` consistent with a rule the same function already follows.

### Keep required — FreeCAD produces an invalid feature without them

| tool | field | why |
| --- | --- | --- |
| `feature_revolve` | `axis` | `ReferenceAxis=None` recomputes `Invalid`, no shape |
| `feature_mirror` | `mirror_plane` | `MirrorPlane=None` recomputes `Invalid`, no shape |
| `feature_pad` / `feature_pocket` / `feature_revolve` / `feature_hole` | `profile` | `Profile=None` recomputes `Invalid`, no shape |
| every feature tool | `body` | the container the feature is added to; no feature exists without one |
| `feature_fillet` / `feature_chamfer` | `base` | the feature whose edges are dressed |
| `feature_fillet` / `feature_chamfer` | `edges` | `UseAllEdges=False` by default, so an empty selection dresses nothing |
| `feature_set_parameters` | `feature`, `parameters` | the operand and the edit; neither has a FreeCAD counterpart to default |
| every sketch tool | `sketch` | the operand |
| `sketch_add_geometry` | `geometry` | the operand |
| `sketch_remove_geometry` / `sketch_toggle_construction` | `geo_ids` | the operand |
| `sketch_add_constraint` / `sketch_remove_constraint` | `constraints` | the operand |
| `sketch_add_external_geometry` | `edge` | the operand |
| `sketch_set_datum` | `constraint` | the operand |
| `feature_pattern` | `kind` | selects the FreeCAD type; there is no type to default |

### Keep required — bridge-invented, ours to decide

`name`, on every tool that creates an object.

FreeCAD auto-names (`Sketch`, `Pad`, `Body`) so by the letter of the parity principle `name`
could be dropped. It is kept required deliberately: the field is bridge-invented — it sets both
the `Label` and the object `Name` so a later call can address the object by the name the caller
chose. An auto-named `Pad001` is addressable only by reading it back, and every downstream tool
(`feature_fillet.base`, `feature_pattern.originals`, `feature_pad.profile`) takes a Name. Making
it optional would create objects the caller cannot then refer to without an extra round trip.

### Keep required — the tool's own semantics, narrower than FreeCAD's type

`feature_datum.attachment`.

`PartDesign::Plane` recomputes valid with `AttachmentSupport=[]`, but the result is an unattached
datum sitting at the origin with `MapMode='Deactivated'`. `feature_datum` defaults `map_mode` to
`FlatFace`, which is an attachment mode and needs a reference. The tool builds attached datums;
an unattached one is a different object, not a defaulted version of the same one. If unattached
datums are wanted later that is a new capability, not a relaxed required list.

## The inverse defect: a requirement the wire does not state

`feature_pattern.direction` (linear) and `feature_pattern.axis` (polar) are **not** in the wire
`required` list, yet `_resolve_direction` raises `ValidationError` on `None`, and FreeCAD leaves
`Direction`/`Axis` as `None` which recomputes `Invalid`. So the wire is silent about a field both
FreeCAD and the code demand — the mirror image of the defect DW-104 reports.

It cannot be stated with a flat `required` list because which of the two is needed depends on
`kind`. JSON Schema expresses that with `if`/`then`, and **the catalog uses no conditional
schemas anywhere today** (`grep` for `allOf`/`oneOf`/`"if"` in `tool_catalog.py` returns
nothing). Adding the first one is a larger change than this pass, and the current behaviour is
not wrong — a missing selector is rejected with a clear `ValidationError` naming the field. It is
recorded as its own follow-up rather than fixed here.

## Failure behaviour

| call | before | after |
| --- | --- | --- |
| `feature_fillet` with no `radius` | rejected at the schema gate | 1.0 mm fillet, FreeCAD's default |
| `feature_chamfer` with no `size` | rejected at the schema gate | 1.0 mm chamfer |
| `feature_pattern` linear, no `occurrences` | rejected at the schema gate | 2 occurrences |
| `feature_pattern` polar, no `occurrences` | rejected at the schema gate | 3 occurrences |
| `feature_fillet` with `radius` | unchanged | unchanged |
| `feature_pattern` with `occurrences` | unchanged | unchanged |

No accepted call changes behaviour. Three calls FreeCAD would accept stop being refused.

## Testing

In-FreeCAD (`tests/infc/test_feature_tools.py`), because each assertion is about what FreeCAD
actually builds:

1. `feature_fillet` with no `radius` commits and the feature's `Radius` is 1.0 mm.
2. `feature_chamfer` with no `size` commits and the feature's `Size` is 1.0 mm.
3. `feature_pattern` linear with no `occurrences` commits with `Occurrences == 2`.
4. `feature_pattern` polar with no `occurrences` commits with `Occurrences == 3`.
5. Each still honours an explicit value — a `radius` of 2.0 mm yields 2.0, not 1.0. Without this,
   tests 1-4 would pass against an implementation that ignored the field entirely.

External (`tests/external/test_feature_contract.py`):

6. `radius`, `size` and `occurrences` are absent from their tools' `required` lists, and the
   fields are still declared in `properties` — a drop that also removed the property would make
   the field unsendable, which `additionalProperties: False` turns into a rejection.

Test 5 is the one that can falsify a lazy implementation; 1-4 pin the defaults and 6 pins the
schema.

## Risks

A caller that omitted the field expecting a rejection now gets a feature built to FreeCAD's
default. That is the intent, and it matches what the same caller would get in the GUI, where the
dialog opens pre-filled with exactly these values.

`Occurrences` differing by kind (2 vs 3) means a caller omitting it gets a different count
depending on `kind`. This is FreeCAD's behaviour, not something introduced here, and it is why no
single wire-level default is declared.
