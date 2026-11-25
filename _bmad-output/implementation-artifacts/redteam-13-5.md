# Story 13-5: red team report

Head: 3527cc2 (branch story/13-5-multi-object-export). Base: 6c60a23. Copy: detached worktree, removed after the run.
Probes: host `freecadcmd.exe -u <tmp>\user.cfg -s <tmp>\system.cfg` with the worktree `src` first on `sys.path` (asserted through `freecad_buddy.__file__`). Oracles: worktree `uv` env, with the same calls as `hosts/tool_catalog.py:_mesh_verify_handler` (`stl_oracle`, `StdlibStlOracle`, `mesh3mf_oracle`, `assemble_export_verdict`).
Probe scripts and outputs are in the session scratchpad (`rt135/p1.py` to `p9.py`, `k1.py`, `oracle_run.py`, `out/*.json`). Each reproduction below quotes the setup and the output.

## Reproduced

| RT | Severity | Q | Where | Finding |
| --- | --- | --- | --- | --- |
| RT-1 | high | Q2 | `src/freecad_buddy/usecases/exports.py:117-118` | A hidden Body does not consume its features. Its tip, which keeps `Visibility=True`, exports as a separate entry. A Part boolean of two Bodies therefore exports the Cut plus both Body tips. |
| RT-2 | medium | Q2 | `exports.py:118`, `exports.py:132` | A visible `Part::Mirroring` source is "consumed" and dropped from the default export. The GUI Mirror command leaves the source visible, so the user sees two solids and gets one. |
| RT-3 | medium | Q4 | `exports.py:62`, `exports.py:438`; test `tests/external/test_exports_3mf_names.py:104` | A Label with a tab or newline gives a 3MF that lib3mf refuses. The E17 patch writes `&#9;` and `&#10;`, and lib3mf rejects every numeric character reference. The test checks only the string, so it passes while the file fails (false-pass test). |
| RT-4 | medium | Q3 | `src/freecad_buddy/usecases/shim.py:533` | Two objects that share one shape (Part "simple copy", or an explicitly selected `App::Link`) get the same STEP `PRODUCT` name, the first object's Label. The second Label survives only as the occurrence name. FreeCAD re-imports the second object as `Box001`. |
| RT-5 | medium | Q6, K-4 | `shim.py:533` (`exportHidden=True`) against `exports.py` source facts from `obj.Shape` | Selecting an `App::Part` that has a hidden child, together with another object: STEP writes the hidden child, but the recorded facts leave it out. A correct request then always FAILs, and the failed per-object check names the wrong object (`Free`, not `Asm`). |
| RT-6 | low | Q4 | `exports.py:432-438` | A Label with another control character (`\x07`) is written raw. The XML is not well-formed and FreeCAD's self-read reads 0 facets. Verify FAILs, so there is no false pass. |
| RT-7 | low | Q6 | `exports.py` `_object_volume_checks` and `_selection_facts` | Two multi-path false FAILs. A BooleanFragments object fails `topology_counts`; this also happens in the single-object path, so it is not new. An object whose compound holds a solid plus a loose face fails its volume checks: the face becomes its own 0-solid product, and `Shape.Volume` of the mixed compound is not the solid volume. |
| RT-8 | low | Q3 | OCCT STEP writer | A non-ASCII Label is written to STEP as raw UTF-8, not in the ISO 10303-21 `\X2\` encoding. FreeCAD reads it back correctly. Other readers may show the wrong characters. |

### RT-1 reproduction (p6, p5 `bodies_cut`)

Setup: a `PartDesign::Body` "Body" holding `AdditiveBox` "Pad", plus a visible `Part::Sphere` "Free". Then `Body.Visibility=False`. This is the same state the GUI leaves: `Gui/ViewProviderGeoFeatureGroupExtension.h:63-70` overrides `extensionShow` and `extensionHide` so that they do not change the children of a Body or an App::Part. Both exports are called with `objects` omitted.

```
"state": {"Body": ["PartDesign::Body", false], "Pad": ["PartDesign::AdditiveBox", true], "Free": ["Part::Sphere", true]}
"step": ["Pad", "Free"]
"3mf":  ["Pad", "Free"]
3MF objects: ['<object id="1" type="model" name="Pad">', '<object id="2" type="model" name="Free">']
```

Second setup (p5): Bodies B1 and B2 (hidden, as the GUI boolean leaves them), `Part::Cut` Cut(B1, B2), and a visible Body "Other".

```
"exported": ["X1", "X2", "Cut", "Other"]   verify: OK
```

The file holds the Cut plus both uncut input boxes, which overlap the Cut, and the verify passes because the facts come from the same wrong selection. Q2 says a feature inside a Body is never a separate entry. Cause: `consumed` is built from candidates only, so a hidden Body consumes nothing.

### RT-2 reproduction (p5 `mirror_visible_source`)

Setup: a `Part::Box` "Box" and a `Part::Mirroring` "Mirror" with `Source=Box`, both visible. This is the state the GUI leaves: `Mod/Part/Gui/Mirroring.cpp:367-390` sets `Source` and copies the visual properties, but does not hide the source.

```
"exported": ["Mirror"], "visible_solids": ["Box", "Mirror"], verify: OK
```

A mirror does not contain its source. The spec matrix covers only inputs that the consumer contains ("covered by those"). The verify passes, so nothing tells the agent that the export lost a solid.

### RT-3 reproduction (p8 + lib3mf variants)

Setup: two boxes, Label of A = `"a\tb"` and then `"line1\nline2"`, exported with `export_3mf(objects=["A","B"])`. Verified with the handler's oracle calls.

```
tab 3mf SPEC_FAILED [('lib3mf.parses', 'Lib3MFException 5: XML contains an invalid escape character.')]
newline 3mf SPEC_FAILED [('lib3mf.parses', 'Lib3MFException 5: XML contains an invalid escape character.')]
tab '<object id="1" type="model" name="a&#9;b">'
```

Edited copies of the same file, read with lib3mf:

```
charref_x ERR Lib3MFException 5: XML contains an invalid escape character.     (&#xA;)
raw_newline OK 'line1\nline2'
charref_amp65 ERR Lib3MFException 5: XML contains an invalid escape character. (&#65;)
```

lib3mf refuses every numeric character reference and keeps a raw newline. The E17 patch therefore turns a label that worked into a file that the project's own oracle refuses. The test at `test_exports_3mf_names.py:104` asserts `name="one&#10;two&#9;three"` and never opens the result with lib3mf. Labels with only `&`, `<`, `>`, `"`, `'` or unicode pass (`specials`, `amp_only`, `quote_only`, `unicode`: OK).

### RT-4 reproduction (p1, p2)

Setup: `Part::Box` "Box", and `Part::Feature` "Copy" with `Copy.Shape = Box.Shape` (what Part > Create a copy > Create simple copy does) and `Placement.Base=(40,0,0)`. Export with `export_step(objects=["Box","Copy"])`. The same happens for `App::Link` "Link" → Box.

```
== shared_tshape
PRODUCT('shared_tshape'
PRODUCT('Box'
NEXT_ASSEMBLY_USAGE_OCCURRENCE('1','Box'
NEXT_ASSEMBLY_USAGE_OCCURRENCE('2','Copy'
== link
PRODUCT('Box'
NEXT_ASSEMBLY_USAGE_OCCURRENCE('8','Link'
re-import labels: "Box", "Box001"   verify: OK
```

`ExportOCAF2.cpp:480-489` reuses the prototype label when it finds the same shape (`FindShape`), so both objects become instances of one product. Nothing in `verify_export_step` reads the names, so the result is silent. Positions survive: the re-imported bounding boxes are `(0..10)` and `(40..50)`, and `(100..110)` for the Link.

### RT-5 reproduction (p9)

Setup: `App::Part` "Asm" holding In1 (visible) and In2 (hidden), plus a `Part::Sphere` "Free". Export with `export_step(objects=["Asm","Free"])`, then verify.

```
"asm_solids_in_shape": 1
status SPEC_FAILED, failed: export_step.volume, export_step.topology_counts, export_step.object_volume:Free, export_step.objects_matched
"export_step.object_volume:Free": [999.9999999999998, 523.5987755982989]
"export_step.objects_matched": [3, 2]
```

The STEP holds 3 solids, because `exportHidden=True` writes the hidden In2. The recorded facts hold 2, because `Asm.Shape` leaves the hidden child out. The 3MF and STL paths mesh `Asm.Shape`, so the three formats do not contain the same geometry. The default selection exports `Asm` too (p5 `app_part`: `["Asm","Free"]`), so an omitted `objects` hits the same false FAIL whenever an assembly has a hidden part.

### RT-6 reproduction (p3 `ctrl`)

Label `"bell\x07x"`, `export_3mf(objects=["A","B"])` returns success. Model part: `<object id="1" type="model" name="bell\x07x"`. `xml.dom.minidom`: `not well-formed (invalid token): line 5, column 40`. Verify: `SPEC_FAILED [('self_read.facet_count', 0), ('self_read.vertex_count', 0)]`.

### RT-7 reproduction (p1, p2)

- `boolfrag`: BooleanFragments(A,B) + Sphere gives `SPEC_FAILED ['export_step.topology_counts']`, measured `faces 25` against expected `19`. `bf_single`, with BF alone through the single path, also gives `SPEC_FAILED ['export_step.topology_counts']`, so this part is not new.
- `solid_plus_face`: a compound of a box and a loose plane, plus a sphere, gives `SPEC_FAILED ['export_step.volume', 'export_step.object_volume:Mix']`, `object_volume:Mix [999.99, 964.29]`. The leaves are `box (1 solid), face (0 solids, volume 0), sphere`.

### RT-8 reproduction (p1 `labels`)

The STEP text read as latin-1 shows `PRODUCT('KhÃ¡Â»Â\x91i Ã\x83Â¸ ...` (raw UTF-8 bytes). FreeCAD re-import gives the Label `Khối ø — 1` back.

## Checked and held (no finding)

- R1-H1, the per-object STL weld. Touching boxes A|B with a cylinder on A: `fc=[12,12,100]`, total 124, STL `OK`, 3MF `OK`. Exploded BooleanFragments pieces that touch: `fc=[12,12,12]`, STL `OK`. Diverse selection (torus pre-tessellated finer, a 2-solid Fuse, a sphere): `fc=[1508,24,514]`. Each facet range's bounding box equals its object's bounding box (`Tor [-11.93..12] z 78..82`, `Fuse 0..60`, `Sph y 75..85`), so the facet order follows the object order. I found no case where the per-object counts and the compound mesh disagree.
- 3MF order and names: objects `["R","L"]` give `name="Right"` with x 40..50, then `name="Left"` with x 0..10. A planted per-object volume error (Left ×1.5) gives `SPEC_FAILED ['trimesh_3mf.object_volume:L', 'trimesh_3mf.volume_band']`, and the message names `object_volume:L`.
- STEP missing object: export [A,B,C], then overwrite the file with [A,B]. Verify fails `object_volume:C` and `objects_matched`. Extra object: fails `objects_matched`.
- K-1 / Q7: single-object export and verify for a Cylinder, a Body (AdditiveBox) and a hidden sole Sphere, with base 6c60a23 against head, all three formats. After removing ids and paths, the only difference is the added `"objects": [...]` key in the export results. Check ids, numbers and messages are equal.
- Default selection: a Body with AdditiveBox, SubtractiveCylinder, Fillet and a datum plane exports `["Body"]`. A Draft clone of a visible box exports both (`["Box","Clone"]`), which is correct. An App::Part with two visible children exports `["Asm","Free"]`.
- Gates on head: `check_imports OK`, `gen_schemas --check OK`, `pytest tests/external -k "export or mcp_surface or check_imports or 3mf or proxy"`: 211 passed.

## Not reproduced (low)

- Facet-count drift between the compound mesh and the per-object meshes (non-manifold input, zero-area facets, cached finer triangulation): not produced. The sum guard would fall back to one weld, which gives a false FAIL, never a false pass.
- An unrelated 3MF archive part that the rewrite changes, or a large model part: not tested beyond the existing byte-identity test.
- STEP unit or schema statics in the multi path: not attacked beyond the existing test `test_Should_write_millimetres_and_the_schema_When_several_objects_go_to_step`.
- Overlapping (interpenetrating) objects in one merged STL pass with a volume that is the sum of the parts. Decision 6 accepts this (total only). Noted, not a defect.

## Verdict

**FAIL.** RT-1 breaks Q2 for a common GUI state (a hidden Body, or a Part boolean of Bodies) and the verify still passes. RT-2 to RT-5 are product defects in Q2, Q3, Q4 and Q6 / K-4. One of them, RT-3, also includes a false-pass test.
