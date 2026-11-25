# TC-17: query_interference reads touching solids as zero overlap

Proves decision 41 in the live GUI: two valid solids that only touch read `common_volume` 0 and
`boolean_failed` false, and a tiny overlap whose `common` is empty is still flagged. The envelope is
a claim of the code under test. The result is the FreeCAD window captured with `cua-driver` and
read by the agent, and the volumes read back with `script_exec` (FreeCAD's own `Shape.fuse`).

**Host**: GUI through the H2 proxy. `script_exec` is on (the default).

## Preconditions

- [ ] The installed addon is the image's copy of the code under test (verify: `docker exec -u cua fcb-desktop sha256sum $FCB_USER_DIR/Mod/FreeCADBuddy/freecad_buddy/usecases/queries.py` equals the `sha256sum` of `dist/addon/freecad_buddy/usecases/queries.py` on the host after `scripts/build_addon.py --release`)
- [ ] No document is open in the GUI (verify: `mcp document_list` returns no document)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `echo '{"pid":<pid>,"window_id":<wid>}' | "$FCB_CUA" get_window_state` returns an element tree)

---

### TC-17-01: Touching solids read zero overlap; a 1e-7 mm overlap is flagged

**Priority**: High
**Design Ref**: `mcp-tools-design.md` §3.2.3; `tool-contracts.md` T-2; decision 41

**Given** a new document `tc17_touch` with six Part boxes built by one call — verify: `mcp script_exec` returns `OK` and `mcp query_tree_summary { doc: <handle> }` lists `A`, `Face`, `Edge`, `Vertex`, `Big1`, `Big2`  
```
mcp script_exec { doc: <handle>, code: "import Part, FreeCAD as App\nV = App.Vector\ndef add(n, s):\n    o = doc.addObject('Part::Feature', n); o.Shape = s\nadd('A', Part.makeBox(10, 10, 10))\nadd('Face', Part.makeBox(10, 10, 10, V(10, 0, 0)))\nadd('Edge', Part.makeBox(10, 10, 10, V(10, 10, 0)))\nadd('Vertex', Part.makeBox(10, 10, 10, V(10, 10, 10)))\nadd('Big1', Part.makeBox(100, 100, 100, V(0, 100, 0)))\nadd('Big2', Part.makeBox(100, 100, 100, V(100 - 1e-7, 100, 0)))\ndoc.recompute()\nresult = 'built'" }
```
**And** FreeCAD's own kernel agrees the contact pairs touch — verify: `mcp script_exec { doc: <handle>, code: "a = doc.A.Shape\nresult = [round(a.Volume + doc.getObject(n).Shape.Volume - a.fuse(doc.getObject(n).Shape).Volume, 9) for n in ('Face', 'Edge', 'Vertex')]" }` returns `[0.0, 0.0, 0.0]`  
**And** the `Big1/Big2` overlap leaves `common` empty — verify: `mcp script_exec { doc: <handle>, code: "c = doc.Big1.Shape.common(doc.Big2.Shape)
result = c.isNull() or not c.Volume" }` returns `true`  
**And** the before image is captured — verify: `mcp view_fit_viewport { doc: <handle> }` returns `OK`, then `echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-17-01-before.png"}' | "$FCB_CUA" get_window_state`  

**When** every pair is measured  
```
mcp query_interference { doc: <handle>, pairs: [["A", "Face"], ["A", "Edge"], ["A", "Vertex"], ["Big1", "Big2"]] }
```

**Then** the call succeeds — verify: `status` is `OK`  
**And** the three contacts read zero overlap — verify: for `A/Face`, `A/Edge`, `A/Vertex`, `boolean_failed` is `false`, `common_volume.value` is `0.0` and `min_distance.value` is `0.0`  
**And** the 1e-7 mm overlap of `Big1/Big2` (1e-3 mm^3, `common` empty) is not read as zero — verify: `boolean_failed` is `true` and `common_volume` is `null`  
**And** the text counts agree — verify: `text` starts with `4 pair(s), 0 overlapping, 1 boolean failed.`  
**And** the document is unchanged — verify: `mcp query_tree_summary { doc: <handle> }` lists the same six objects with no `!` marker, and a fresh fingerprint digest read through `script_exec` (`from freecad_buddy.usecases.fingerprint import fingerprint; result = fingerprint(doc, fresh=True)["digest"]`) before and after the `query_interference` call is equal  
**And** *(visual)* the viewport shows the boxes the numbers describe — verify: `echo '{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-17-01-after.png"}' | "$FCB_CUA" get_window_state`, then `Read` both PNGs and list what the viewport shows: `A` with `Face`, `Edge` and `Vertex` meeting it face to face, edge to edge and corner to corner, and `Big1` beside `Big2`. A pair that the picture shows overlapping by more than a sliver, or a missing box, is a finding against the fixture or the tool. The judgement is on the pixels alone  

**Cleanup**: `mcp document_close { doc: <handle> }`
