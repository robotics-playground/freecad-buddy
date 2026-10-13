# Story 10.7 Edit Inventory

Planning-time audit of the UAT suite against HEAD `b792cad`. One row per edit still needed:
`id | file:line | current text | required change | reason`. Each row is a hypothesis: re-read the
line and the cited source before you edit. Line numbers drift as edits land; search by text.

Shared terms used below:

- **live version**: read `freecad_version` from `query_capabilities`; never write a version literal.
- **live count**: read the tool count from `tools/list` (45 typed tools + `script_exec` when on = 46 by default).
- **Show All**: View > Visibility > Show All Objects before any fit or render. Golden and fault FCStd files have no `GuiDocument.xml`, so they open hidden and `view_fit_viewport` returns `SPEC_FAILED view_fit.nothing_to_frame` (the run saw the older `view_fit.unverified`).
- **session temp path**: `<workdir>/tmp/FCB_TMP_session_<pid>_<token>/`, not `$TEMP` (`documents.py:61-73`, `transaction.py:107`). The shell may get "Access is denied"; list it in-process with `script_exec` or take the folder from `snapshot_path`/`resource_link`.
- **schema refusal**: accept `Input validation error: …` where the MCP input schema pre-empts the product message and the input is still refused.
- **busy Given**: a raw `rpc_hello` while the proxy holds the session gets `bridge busy: another client session is active` (AD-26). Stop the proxy first, restart it after.
- **script_exec posture**: on by default; off with `FREECAD_BUDDY_SCRIPT_EXEC=0`; off with `FREECAD_BUDDY_UNATTENDED=1`; on again with `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`. `FREECAD_BUDDY_ALLOW_EXEC` and `AllowExec` are deleted; preference is **Allow script_exec** (`ScriptExec`). Refusal text: `script_exec is off: FREECAD_BUDDY_SCRIPT_EXEC or the ScriptExec preference turned it off, or FREECAD_BUDDY_UNATTENDED=1 is set without FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1` (`mcp_server.py:322-326`). Through the proxy when off: `unknown method: script_exec`.
- **Touched route**: `script_exec` sets a property and does not recompute (`script_exec.py:19-67`), e.g. `doc.getObject('Pad').Length=12; result=doc.getObject('Pad').State` → `['Touched']`. `verify_recompute` recomputes first (`verify.py:435-437`), so it can never see Touched. `script_exec` opens no transaction: `document_undo` does not revert it; close without saving.
- **UndoMode 0 recipe**: `script_exec` sets `doc.UndoMode=0` and patches `shim.enable_undo` to return `False` (`documents.py:630`, `transaction.py:622`); restore in Cleanup.
- **redundancy rule** (Story 10.2 D1/D2): full redundancy is a hard fail (mutation returns `RECOMPUTE_ERROR`, rolled back); partial redundancy warns.
- **rollback proof** (Story 10.3 D4): on the snapshot path assert `mutation.changed == []`; digests never match after a reopen.

## TC-01

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| pre | :19 | "FreeCAD 1.1.1 installed" | live version | AC1 |
| all | 24 lines (:62, :96, :140 …) | "refused on FreeCAD 1.1.1 with `menu_path_unavailable`" | "on FreeCAD 1.1.x" or drop version | AC1 |
| 01..09,11,12,14,15 | :52,82,115,160,194,228,266,305,346,414,456,586 | golden open, then fit | Show All | AC1 |
| 01 | :57 | "owning pid equals the pid in the spawn line" | equal or child (port owner is the uv base pythonw, child of the spawn pid) | run note |
| 03 | :109,134,139 | "exactly 45" | live count | AC1 |
| 03 | :136 | "`debug_exec` is absent while its flag is unset" | `script_exec` present by default; absent under the off postures | AC7 |
| 04 | :159 | "`FREECAD_BUDDY_ALLOW_EXEC` … Allow debug_exec preference is off" | `FREECAD_BUDDY_SCRIPT_EXEC` unset, Allow script_exec at default (on) | AC7 |
| 04 | :176 | "exec is disabled by default … `false`" | `exec_enabled:true` by default; busy Given for the direct `rpc_hello` | AC7, 10.6b |
| 04 | :168,171,178 | `invoke_menu ["Help","About FreeCAD"]` (`1.1.1`) | modal through invoke_menu is forbidden: compare window-title version to live version | AC4, AC1 |
| 05 | :207 | "with `debug_exec` ungated … exactly `document_create` … `query_placement`" | drop the debug_exec clause; the 30 s set has 11 names, add `view_fit_viewport` (`tool_catalog.py:931-944`) | run note |
| 06/07/08 | :235,273,312 | `sorted(glob(...rpc-*.json))[-1]` | open `rpc-<freecad pid>.json` | run note |
| 09 | :362 | "(`1.1.1`)" | live version | AC1 |
| 09 | :363 | `rpc_hello` with this token returns a `result` | busy Given | 10.6b |
| 13 | :497 | `launch_app { … env: {…} }` | `launch_app` has no env field: `.cmd` wrapper sets the variable | run note |
| hdr | :10-13 | H2 lacks the non-string-`doc` guard and suspect-document logic | stale: `rpc_listener.py:417-424` has both | source |

## TC-02

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| all | :28 + 22 lines | "refused on FreeCAD 1.1.1" | drop version | AC1 |
| 02,03,04,09,10,16,17,18 | :109,146,193,378,416,653,670,737 | golden open, then fit | Show All | AC1 |
| 01 | :68 | title bar `uat-roundtrip` | `tc-02-01-uat-roundtrip` (label = file stem) | 10.1 D2 |
| 06 | :259-261 | `feature_set_parameters … Length 0 … confirm` | rolls back, Pad stays healthy: break the Pad through the property editor or `script_exec` (`Pad.Length=0`) | run note |
| 08 | :322 | Body Placement non-identity + "feature attached to a datum plane" | name routes: Placement through Edit > Placement; datum object is a `feature_datum` plane (`sketch_create` cannot attach to a datum) | AC1 fixtures |
| 09 | :358 | `["File","Open..."]` | modal through invoke_menu forbidden; use a non-modal route (Start-page Recent Files, or launch with the file argument) | AC4 |
| 09 | :364 | `"expect":{"title_contains":…}` | `verify_state` needs a predicate list | run note |
| 10 | :403 | `["Windows","two-box-compound"]` | entry reads `3 two-box-compound : 1` (numbered) | AC1 menus |
| 13 | :527-528,531 | "label survives save and reopen" | label after reopen is `tc-02-13-uat-unicode`; Unicode on-screen check moves before the save | 10.1 D2 |
| 14 | :548 | "GUI … or over MCP" | no MCP tool makes App::Part / App::Link: GUI or `script_exec` | AC1 fixtures |
| 15 | :617, hdr :16-19 | `INVALID_INPUT doc handle must be a string` | schema refusal `… is not of type 'string'`; hdr stale (H2 has the guard) | AC1 |
| 16 | :646 | `name` `sphere-r10` | `sphere_r10` | run note |
| 17 | :663,689 | "the three refusals are distinguishable" | missing file is distinct; non-FCStd and corrupt zip share `Invalid project file <path>: ios_base::failbit set…`; cite SCP 2026-10-04 decision 2 | AC2 |

## TC-03

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| intro | :6-7 | "Redundant constraints are a warning and must never fail" | redundancy rule | 10.2 |
| pre | :22 | "`query_capabilities {}` lists 44 tools" | live count from `tools/list` | AC1 |
| all | 22 lines | "refused on FreeCAD 1.1.1" | drop version | AC1 |
| 01 | :61, :94, :125, :180 | origin axis crosses, constraint colours | visible only in Sketcher edit mode: open the sketch in edit mode before judging | run note |
| 03, 13 | :109, :513 | `query_object` lists face/edge names | returns properties only: take names from an outside topology oracle (`script_exec` or fcb env) | run note |
| 05 | :227 | `Part::GeomLineSegment` … | shipped values `LineSegment`, `Circle`, `ArcOfCircle`, `Point` (`queries.py:701`) | run evidence |
| 05 | :214-220 | arc pinned by 7 constraints on 5 DoF | now a hard fail: pin exactly (centre X/Y, Radius, start Y, end X) | 10.2 |
| 06 | :248-287 | Given 5 geometries; When uses geo 5; ids 1..16 | Block pins needed (AD-8) so ids start later; constraints on Blocked geometry are redundant (hard fail): per-type fixtures, relative id checks | 10.2, run note |
| 09/15/17/19 | :390,604,654,676,762 | `ls "$TEMP"/FCB_TMP_snap_*` | session temp path | 10.1 D4 |
| 11 | :442 | fixture with a redundant extra constraint | cannot be built: use reference constraints (`driving:false`) as the removable ones | 10.2 |
| 12 | :471-497 | "Redundant constraints warn and commit … OK" | duplicate Horizontal → `RECOMPUTE_ERROR`, `recompute_clean:false`, rolled back, count unchanged | 10.2 (triage #32) |
| 13 | :524 | `status=CLEAN` with `findings=[]` | CLEAN carries PASS findings: assert no non-PASS finding | run note |
| 14 | :544,560 | unpinned rectangle, "dof falls" | bridge rolls back an unpinned sketch: pin in the build call, drop "dof falls" | AD-8 |
| 15 | :603 | `value: 1e999` … `must be finite` | JSON cannot carry Infinity: drop the leg | AC1 fixtures |
| 16 | :631,633 | `SPEC_FAILED` … `verify_sketch failed on PlateProfile (dof=` | `RECOMPUTE_ERROR`, explanation starts `recompute left 1 object(s) invalid: PlateProfile:` | run note |
| 20 | :782-798 | expects `BROKEN`; constrains `BossProfile` geo 0 | Length 30 gives `REPOINTED` (`FLAGGED`, `SPEC_FAILED`); give BossProfile geometry in the Given; no MCP delete route | run note |

## TC-04

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| pre | :24 | lists 44 tools | live count | AC1 |
| all | 33 lines | "refused on FreeCAD 1.1.1" | drop version | AC1 |
| snapshot | :658,676,694,718,787,810,873,902,921,953,971,987,1004,1024 | `$TEMP/FCB_TMP_snap_*` | session temp path | 10.1 D4 |
| 01 | :46,65 / :59 | golden fit / "shows an `App::Origin` child" | Show All / tree line `[ORIGIN] Origin` with its axis and plane lines | AC1 |
| 06, 13, 15 | :249, :559, :634 | `query_object` names a link's target | accept the type string `"<PartDesign::Pad>"` (`queries.py:407`); read the target through `query_dependencies` or a FreeCAD oracle | spec D2 |
| 07 | :285 | `volume=11928.7` | 11915.64 (default `DrillPoint` Angled 118° adds a cone tip) | run note |
| 09 | :349,355-358 | Edge1/3/5/7 vertical | 1.1.4: vertical corners Edge1, Edge2, Edge5, Edge8; use the oracle | AC1 |
| 10 | :411,412 | `Edge5`; `"Distance and angle"` | `Edge17`; `"Distance and Angle"` | AC1 |
| 11 | Given | plate position unstated | place plate at x=40..100 (no overlap with the disc) | run note |
| 12 | :514 | `solid_count=1` for each | PlaneMirror and DatumMirror give 2 solids, FaceMirror 1; place bodies apart | run note |
| 13 | :532,543-550 | EdgeAxis `ObjectXY` on Edge1; CornerPoint `ObjectOrigin` | axis mode valid for an edge (`TwoPointLine`); `Vertex` for the point; oracle face names | run note |
| 15 | :616,623 | query_object face names; `Face5` | define BasePad; oracle; bottom face is Face1 | AC1 |
| 16 | :666 | `Edge1` | `Edge3` (60 mm bottom edge) | AC1 |
| 17 | :693,702,712,722 | seam `Edge2`; "dressed N of M" | seam `Edge3`; mark the under-dressed Then conditional | AC1 |
| 19 | :812 | infinity length | not sendable: drop the leg | AC1 fixtures |
| 20 | :830 | query_object edge names | oracle | run note |
| 21 | :898 | `BlockPad.Shape is read-only` | `BlockPad.Shape is a Part::PropertyPartShape, which feature_set_parameters cannot write` (`features.py:1764`) | 10.3 D2 |
| 23 | :970 | under-constrained Given, no route | build fully constrained, then delete position constraints with `script_exec` | AD-8 |
| 24 | :1003,1007-1010 / :1019 | `SlotPocket Length 500` / `is_valid` not measured | PlatePad → EdgeFillet r=1 on Edge3, then Radius 20 → `RECOMPUTE_ERROR` / `is_valid` is `false`, only `fully_constrained` not measured (`transaction.py:266`) | run note |

## TC-05

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| all | 31 lines | Fit All menu refused on 1.1.1 | live version | AC1 |
| temp | :26,73,78,88,90,97,192,238,262,283,335,372,418,446 | `$TEMP` paths | session temp path | 10.1 D4 |
| golden | :468 | open then fit | Show All | AC1 |
| exec | :18,19,352,353,355,361,391,392,394,399,429,432,438 | `debug_exec`, `ALLOW_EXEC=1`, "Allow debug_exec", `debug_exec is disabled` | script_exec posture | AC7 |
| 01/02/10/11 | :38,74,356,395 | `query_sketch_info … fully_constrained, dof` | `verify_sketch` → `subject.fully_constrained`/`subject.dof` | `queries.py:684-721` |
| 01 | :54 / :58 | audit `mutation` line keeps `transaction_id` / "three times as tall" | delete (`transaction.py:533-552`) / 1.5:1 | source, run |
| 02 | :87 | dir holds `<Doc>.FCStd` | prove in-process with `script_exec os.listdir` | ACL |
| 03 | :107, :120 | dof-4 sketch; "check 4 (TNP) did not run — findings []" | build with `script_exec`; audit runs on every short-circuit: assert `tnp_audit.status` not `UNSUPPORTED`, `counts` present | AD-8, 10.3 D6 |
| 05 | :185 | "not an MCP isError response" | `isError: true` on every non-OK result, envelope in `structuredContent` (`mcp_server.py:110`) | source |
| 06 | :219-220, :228 | 900 mm pocket as failure; `base`/`direction:"X"`; digest equality | pocket commits, move to Given; `feature_pattern` takes `originals:[…]` and a direction object; rollback proof | run, 10.3 D4 |
| 07 | :255-265 | known restore-path doc / `$TEMP` swap watcher | `script_exec` patches `shim.enable_undo`→False and wraps `transaction._restore_from_snapshot` to copy `sphere-r10` over the snapshot | 10.3 D4 |
| 08 | :293, :304 | UndoMode 0 Given; digest equality | UndoMode 0 recipe; rollback proof | 10.3 |
| 09 | :332 | `transaction_id "0"` in audit | not checkable: rely on :333-334 | source |
| 10 | :361 | `type(_d).commitTransaction = _boom` | immutable type: wrap `transaction.run_mutation` with a proxy whose `commitTransaction` raises | run |
| 11 | :399 | `_state['n'] == 2` | `== 1` (gate passes `fp_before` in) | `features.py:372-386` |
| 12 | :436-438,442 | patch first fingerprint call; `fingerprint_before` null | make `tnp_guard.snapshot_references` or `saveCopy` raise; `fingerprint_before` is the full digest | `transaction.py:636-643` |
| 13 | :466-468 | open same path twice | same handle returned: open a byte-identical copy from a second path | `documents.py:500-502` |
| 14 | :500, :509-516 | 1.1.1; `{objects:[],digest:0}` message | live version; expect `INVALID_INPUT expect_fingerprint record: cannot compare fingerprints: serializer tag missing/mismatch…`, undo not run; `{digest:"abc"}` → `expect_fingerprint serializer None does not match this build's …` | F-12 fixed |
| 15 | :535, :538-548 | element-map version; Pad Length 32 harmless | `element_map_available:true`; Length 32 breaks the fillet on 1.1.4: use Fillet Radius 2→3, assert `tnp_audit.counts.PASS ≥ 1` | run, 10.3 |
| 16 | :569-581 | chamfer `base:"Pad"` with Tip=Fillet → FLAGGED | now `INVALID_INPUT` naming Tip `Fillet` before the bracket; REPOINTED via an external-geometry source change (as TC-03-20) | 10.3 D9 |
| 17 | :603-604 | `geometry: [0]` | `geo_ids: [0]`; expect `RECOMPUTE_ERROR`, `FLAGGED`, layer-0 BROKEN finding | AC1 fields |
| 18 | :636, :640-647 | version null; preview `base:"NoSuchFeature"` | `element_map_available:false`; degraded form through a `script_exec` patch on the setup-failure path → `tnp_audit.status "UNSUPPORTED"`, `findings []` | source |

## TC-06

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| all | :29,33,60-62,85 | 1.1.1; garbled Fit All note | live version; menu path refused, toolbar button works | AC1 |
| temp | :463,549,557 | `$env:TEMP …FCB_TMP_shot_*` | session temp path | 10.1 D4 |
| golden | :438,482,536 | open then render/fit | Show All | AC1 |
| 01 | :83-85, :110,112, :632-635 | compare face tone with viewport; "window wins" | assert AD-34 tone band only (no black/white face, separable from background); no viewport shading comparison; cite SCP 2026-10-04 decision 4 and `integration-mcp-freecad.md` lighting rig (headlight 0.80) | AC2 |
| 03 | :194, :199 | default render has no sketch; Body include asserts names only | visible sketch renders, assert no Body/datum/origin; add PNG shows the Tip solid or `empty_scene:true` | 10.4 D1, D5 |
| 04 | :237 | t=0 and t=100 both OK | add: renders differ in pixels, hue kept | 10.4 D3 |
| 05 | :257 | `verify_shape` face count | `query_mass_properties` → `counts.faces` | `queries.py:617` |
| 10 | :482-495 | golden Box; preview `{tool,args:{doc}}`; dirty via `verify_recompute` | Touched route: BoxPad over MCP, `script_exec` Length=25 → State `['Touched']`, `query_screenshot` `dirty_document:true` + `Document dirty (pending/broken recompute)`, `document_recompute` → `dirty_document:false`, volume 5000 | AC6 |
| 12 | :607 | change GUI preference then re-render | modal forbidden: `script_exec` `FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View").SetInt("AntiAliasing",n)`, restore after | AC4 |

## TC-07

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| all | 22 lines | 1.1.1 | live version | AC1 |
| golden | every golden/fault `document_open` | open then fit | one shared precondition: Show All | AC1 |
| pre | :23, :222, :344, :578 | `import trimesh, lib3mf` | `uv run --with networkx --with lxml`; 3MF with `force='mesh'`; `split()` needs networkx | run |
| reimport | :186,223,262,304,345,381,382,449,503,539,579,619,697,734,824 | `document_open` of STEP/STL/3MF | FCStd only (`documents.py:485-499`): `document_create` + `script_exec` (`Part.show(Part.read(p))` / `Mesh.insert`) or fcb env | source |
| 03 | :101-113, :120 | lone line via `sketch_add_geometry`; duplicate Horizontal stays OK | build with `script_exec`, add all three constraints in one call; redundancy rule | AD-8, 10.2 |
| 05 | :183 | `grep -c "AP214"` | grep `AUTOMOTIVE_DESIGN` (AP214) and `AP242_MANAGED_MODEL_BASED_3D_ENGINEERING` (AP242); `verify_export_step` `export_step.schema` passes | 10.5 |
| 07 | :255 | three round-trip checks | four, adding `export_step.schema` | 10.5 |
| 09 / 10 | :343 / :377 | band "< 0.1 % volume" / "far below 0.001·4188.79" | band = (2/3)·linear·area = 52.36 / 8.378 (`verification-design.md:349`) | source |
| 12 | :442-447 | `two-box-compound` multi-object | holds one object: build two shape objects | run |
| 15 | :560, :578 | box at linear 0.5 vs 0.01 | same 12-facet mesh: use `sphere-r10`, volume ≈ 4188.79 | run |
| 20 | :788 | "body with one face missing" | fixture is a single open face | run |

## TC-08

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| all | 43 lines | 1.1.1 | live version | AC1 |
| temp | :27,72,91,93,100,712,733,766 | `$TEMP` paths | session temp path | 10.1 D4 |
| golden | :670 | open then fit | Show All | AC1 |
| exec | :625,719,729 | `debug_exec` | script_exec posture | AC7 |
| 01/08 | :39,289 | `query_sketch_info … fully_constrained` | `verify_sketch` | source |
| 05 | :188,191 | headless returns "no render port" | H1 has an offscreen render port: make conditional | `preview.py:559-562` |
| 06 | :219-227, :237 | record form `{schema, serializer, objects, digest}`; `42` exact message | wire carries `{digest, serializer}` (object form); schema refusal | `result_projection.py:51-55`, AC1 |
| 07 | :273 | fresh preview same operation | name collides: use `Probe2` | run |
| 11 | :414 | unserializable document unreachable | reachable: `script_exec` patches `freecad_buddy.usecases.fingerprint.fingerprint` to raise; expect `cannot read the state of <handle> to authorize the mutation: …` | `confirm.py:347,366-371` |
| 12 | :452-453 | fresh `Probe` | likely collides: unique name | run |
| 14 | :527-531 | `!!!!.!!!!` → `is not decodable`; four strings; `payload is missing`; `12345` | assert shipped: `carries an invalid signature` for both; 3 distinct messages; `payload is missing` unreachable (signature first); schema refusal for 12345; cite SCP 2026-10-04 decision 2 | AC2 |
| 15/16/17/19 | :566-567, :598-599, :643, :731-732 | exact product messages | schema refusal | AC1 |
| 17 | :647 | Pad Length in the sample | use Fillet Radius | run |
| 21 | :787,801,807 | UndoMode 0 "if available" | UndoMode 0 recipe | source |

## TC-09

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| all | 44 lines | "refused on FreeCAD 1.1.1" | build under test, live version | AC1 |
| Givens | :43,78,117,… | fit OK on golden | Show All | AC1 |
| hdr | :20-24 | H2 lacks non-string-`doc` guard | stale (`rpc_listener.py:417-418`); H1 is front + worker | 10.6a |
| 01 | :52-58,64 | reads `$RUN_DIR/evidence/tc-09-01-edge_report.json`; tracebacks expected | copy from `_automation/edge_report.json`, `edge.stderr.log`; one INFO line per client error, no traceback (`rpc_dispatch.py:88-91`) | run |
| 02 | :99-100 | `WORKER_CRASHED` unreachable in-process | H1 front emits it (dead worker; quarantine past 2× budget; `entry.py:72,108`) | 10.6a/10.6 |
| 06 | :231,261,263 | `geometry_count` | `len(geometry)` from `query_sketch_info` | AC1 fields |
| 10 | :409,415,427,429 | untyped checks; 100-level nesting | items typed `object` → schema refusal; nest ~10 levels; expect `unknown assertion fn:` | AC1, F-22 fixed |
| 14 | :562 | `confirm:{preview_id:<P>}` | drop `confirm` (auto-approve default) | source |
| 15 | :586-610 | union type; H2 diverges | `doc` is `{type:string}` on both hosts: schema refusal on both, no divergence | AC1 |
| 16 | :639 | `path: "README.md"` | absolute path to a non-FCStd file | run |
| 17 / 18 | :677,681 / :713,715 | `verify.py:24`; "unbuilt feature" / "graph shows missing target" | `:22`; last valid shape stays drawn, tree error icon / dependency read `OK` with no Pad→Sketch edge | AC1 |
| 19 | :735-738 | env var on `mkdir` | set it on the H1 server command | shell |
| 20 / 21 / 22 | :794 / :830-833 / :865-876 | grep hits docstring; stale line refs; "deliberate tracebacks" | grep code only, open at `:48`; `:25`, `:29`, `:88-91`; 0 tracebacks for client errors, boundary ~`:156` | source |
| 23 | :907,912,914 | "44 tools, plus `debug_exec` only when ALLOW_EXEC=1"; `${TMPDIR}` | live count; session temp path | AC1, AC7 |

## TC-10

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| all | 25 lines | 1.1.1 | live version | AC1 |
| hdr | :16-21 | `mcp_server.py:174-220`, `entry.py:136-140`, `rpc_listener.py:304-343` | `:239-292`, `entry.py:62-66`, `:410-424`; H1 is front + worker; front bounds every call and quarantines | 10.6a/10.6 |
| 01 | :56,59,61,63,69 | report spans; server log path; broad `rm` | time the reads in the script; copy from `_automation/`; narrow the cleanup glob | run |
| 02 | :99,106,112 | `c['duration_s']`; `rm tc-10-02-*.png` | time in the script; keep own visuals | run |
| 04/06/13/14 | :172-178, :242-243, :479-481, :516-525 | raw `rpc_hello` | busy Given | 10.6b |
| 05 | :223 | `$TEMP/FCB_TMP_prev_*` | session temp path | 10.1 D4 |
| 06 | :231,247-251 | handles not shared; B gets `INVALID_INPUT` | shipped: B reads A's handle `OK`, `document_list` lists it (one process-wide registry; TC-01-12 needs handles to survive reconnect); cite SCP 2026-10-04 decision 2 | AC2 |
| 07 | :270-271,284-285 | no preemption; next read terminal | front stops waiting at `timeout_s`, body runs on in the worker; next call `TIMEOUT quarantined:true` "not dispatched…" < 1 s; past 2× budget `WORKER_CRASHED`; served once the body returns; CPU check on the worker | 10.6 D1 |
| 08 | :297,302-305,319 | "quarantines the document"; E not refused | rename document-suspect; while the body runs E gets `TIMEOUT quarantined:true`; per-document suspect only after the body returns; refs `:264-272`, `rpc_listener.py:420-424` | 10.6 |
| 09 | :336,339-340 | "D still quarantined" | Given: abandoned body has returned | 10.6 |
| 10 | :376,379-380,387 | fingerprint via `query_object` | `preview_dry_run.fingerprint_before` or `mutation.fingerprint_after`; add `hosts/headless/entry.py` to the grep | run, 10.6 |
| 11 | :409-418 | mutation issued "immediately" during the 130 s read | under quarantine it gets `TIMEOUT quarantined:true`: assert that, then wait for the body and assert the mutation applies; Host ref `:189-210` | 10.6 D1 |
| 12 | :450,453,457 | "44 tools"; `rm …/rpc-*.json` | live count; delete only the killed pid's `rpc-<pid>.json` | AC1, run |
| 13 | :470-473,488 | `rpc_listener.py:64-83`, :242-247; proxy Then | `:85-110`, `_read_line :330-348`, WARNING no traceback; drop proxy Then or point to TC-10-12 | 10.6d |
| 14 | :508-509,527 | `:36`, :76; zero-byte recv | `:43`, `:96`; accept 0-byte read or `ConnectionResetError` | 10.6d |

## TC-11

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| all | 33 lines | 1.1.1 | live version | AC1 |
| exec | :4,33,47,52,54,57,66,69,71,74,88,103-106,111,116,123,131,139,145,147,155,168,182,185,191,196 | `debug_exec`, `ALLOW_EXEC` | script_exec posture, plan below | AC7 |
| intro, 04 | :3-5,176,194-197 | "Typed tools are the only mutation path"; grep; 44 names | AD-4 is "typed tools first, script_exec for the rest"; grep hits only `SCRIPT_EXEC_SPEC` (`tool_catalog.py:1051-1071`); 46 names, allow `view_fit_viewport` and `script_exec` | 12.1 |
| 02/03/08 | :103-106,147-148,356-357 | `uv run python -m freecad_buddy.hosts.main serve` | `"$FCB_PYTHON" -m …` (worker runs `sys.executable`) | 10.6a |
| 05/09/16 | :239,407,699 | raw `rpc_hello` | busy Given | 10.6b |
| 07 | :299-302,321 | chmod note, lines 197-198 | read-only bit stays clear on Windows; `icacls` shows only owner, SYSTEM, Administrators; ref `rpc_listener.py:233-253` | 10.6d |
| 10 | :440,449 | `verify_export_step` with no prior export; `$TEMP` | `export_step` first; session temp path | run |
| 11 | :472,478,482,485 | pad on unconstrained sketch | oversized fillet; expect `OK` with `diff.validity.status RECOMPUTE_ERROR` | AD-8 |
| 12 | :518,525,533-535 | `$TEMP`; commit-raises and keep-cases | session temp path; drive the three cases with a `script_exec` patch, else retire with the reason | run |
| 15 | :656-658 | "line 46"; greps expect nothing | `:48`; exclude docstring hits | source |
| refs | :52-55,93,136,181,219-221,259-261,345-346,679-680 | stale line refs | `mcp_server.py:78-86`, `rpc_proxy.py:101-102`, `capabilities.py:37-52`, `entry.py:44-45,160`, `:224-225`, `rpc_listener.py:233-253,393-397` | source |

TC-11 `script_exec` plan:

1. Precondition: none of the three variables set; Allow script_exec at default; `addon.log` `operator settings:` shows `FREECAD_BUDDY_SCRIPT_EXEC='1'`.
2. TC-11-01 on by default (H1 and proxy): `tools/list` = live typed count + 1 and includes `script_exec`; stderr has `SECURITY: script_exec ENABLED: …`; `exec_enabled:true`; a call returns `OK` with an `exec` audit pair.
3. TC-11-02 postures (H1, one start each): `SCRIPT_EXEC=0` → off; `UNATTENDED=1` → off; `UNATTENDED=1` + `SCRIPT_EXEC_UNATTENDED=1` → on. Check count, `exec_enabled`, warning only when on. Values other than exactly `1` for the two unattended variables are off.
4. TC-11-02b direct call when off: `INVALID_INPUT` with the exact refusal text, an `exec` audit pair, fingerprint unchanged; through the proxy `unknown method: script_exec`.
5. TC-11-03 on the default posture; TC-11-04 previews `script_exec`; cleanups unset the three variables.
6. Negative check: `grep -rn "ALLOW_EXEC\|AllowExec\|debug_exec" src/` returns nothing.

## TC-12

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| all | :3,24,27,457,727,778 | 1.1.1 titles | live version | AC1 |
| 01/02/03 | :92,145,183 | `["File","New"]`, `["File","Open"]` | `"New Document"`; Open is modal → non-modal route | AC1, AC4 |
| mass | :108,115,192,221-222,231,288,329,375,406,424,512-513,522-523,659 | `query_mass_properties {doc}` | add `object` (required) | schema |
| 02 | :158,161 | `handle`; transient reflects never saved | field is `doc`; `transient` false for GUI-adopted documents | AC1 fields |
| 03/08 | :201,400,429-430 | entry names its file; transient true→false | `document_list` has no `path`: `label` = file stem; drop transient Thens | AC1, 10.1 D2 |
| 04 | :237,240 | selector; render "box only" | role `TreeItem`; Show All | run |
| 06 | :312-313,332-334,339 | `preview_dry_run {tool,args}`; Edit-menu Undo `buddy:` | `operation:{tool,args}`; fillet needs `body`, `name`, `mapped_name` edge; `buddy:` appears in the toolbar Undo dropdown | AC1 menus |
| 07 | :357-383 | bridge sees dirty state; `["Edit","Refresh"]` | Touched route (`script_exec`); no Refresh leaf | AC6 pattern |
| 10 | :518,526 | `set_value` on workbench combo | click the combo item; check `ComboBox` label `Sketcher` | run |
| 11 | :574 | `max_nodes:10` → `INVALID_INPUT` | schema refusal | AC1 |
| 12 | :593,599,612 | recompute > 3 s; Refresh | heavy file open as the long GUI operation | run |
| 13 | :662,670 | `verify_state exists:false`; B framed | driver refuses `exists:false`: judge the PNG; Show All | harness |
| 15 | :760,777,786 | `Stop-Process -Force`; `$env:TEMP` | stop it from the agent shell at the same integrity level (AC4); session temp path | AC4, 10.1 D4 |
| rules | :28, :40-48 | menu bar labels; View submenus never resolve | re-confirm on 1.1.4 (`View > Visibility > Show All Objects` resolved in the run) | run |

## TC-13

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| a | :35,38 | `FreeCAD 1.1.1` title | live version | AC1 |
| e | :137,179,230,274,316,367,410,457,500,557,601,645,688,736,798,849,898,950 | "refused on FreeCAD 1.1.1" | drop version | AC1 |
| rule 5 | :91-97 | golden hidden, render passes `include` | Show All before any fit; where hidden is the subject (13-03 hidden leg, 13-09, 13-14) accept the refusal and use GUI Fit All | AC1 |
| 08 | :457 | `view_fit_viewport {doc:<goldenHandle>}` after `document_create` | `INVALID_INPUT live viewport is showing 'TC13Parity'…` (AD-29): expect it, or fit the active doc | run |
| 07 | :384,404,406 | open-shell fixture carries an error marker | build a real error with `script_exec` (`Pad.Length=0; doc.recompute()`) on a scratch pad | run |
| 11/12 | :573-597, :617-646, :599 | golden `Box` `Length 10→25`; "WITHOUT confirm returns the refusal" | use TC13Pad `Pad` (5→12 mm, 3000→7200); auto-approve on by default: needs `FREECAD_BUDDY_AUTO_APPROVE=0` or delete | run, default |
| touched | :361, :600, :644, :916 | `verify_recompute reports no touched object` | "no error / failing_objects empty" | `verify.py:437` |
| 06 | :366, :341, rule 4 :82-83 | "matching the tone of the same faces"; `["View","Standard views"]` | AD-34 tone band, no viewport match, cite SCP 2026-10-04 decision 4; `Standard Views` | AC2, AC1 |
| 15 | :753,791,794,795 | `reports label BoxHoleRenamed` | tree line `- [FEATURE] BoxHole "BoxHoleRenamed"` | ba1ead6 |
| 18 | :925-929 | `Ctrl+W` | click root TreeItem, `invoke_menu ["File","Close"]` | AC1 |
| 13/18 | :684, :944 | `verify_state … exists:false` | judge the PNG | harness |
| 16 | :816-834 | `Open…` + file dialog | non-modal route | AC4 |
| 17 | :865-903 | Touched via TC-13-11; first `verify_recompute` names touched | Touched route; GUI Edit > Refresh (enabled when `mustExecute`) or `document_recompute` (`touched: N>0` then `0`), volume 7200; drop the `verify_recompute` Then; close without saving | AC6 |

## TC-14

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| e | :19 | 1.1.1 | drop version | AC1 |
| d | 01 :43, 02 :83, 03 :110, 07 :250, 16 :563, 08/10-13 | golden fit expects OK | Show All | AC1 |
| b | 04 :146 | `document_create {name}` | `label` | AC1 fields |
| b | 04 :147, 05 :180, 16 :565,:578 | `query_mass_properties {doc}` | add `object` | schema |
| b | :111,123-127,158-161,182,221,231,285,298,345,377,394-395,450,466-470 | `framing.fits/.ratio/.checked/stale_reason` | plain-text line `framing: fits|does not fit|unknown, ratio R, computed|cached[, reason]` (`mcp_server.py:141-149`) | ba1ead6 |
| 11 | :390-391 | warning at text end; `envelope.py:103-106` | warning follows the status line, before `framing:`; `:110-113` | ba1ead6 |
| 12 | :428,430-431 | H1 envelope has no framing key | H1 has no `framing:` line; GUI line ends `computed`/`cached`; `unknown` with `unavailable` | ba1ead6 |
| 08 | :296-297 | `INVALID_INPUT` for `factor`/`confirm` | schema refusal | AC1 |
| 13 | :459,468,471,475 | 640×400; assert list_windows 640×400 | size where the MDI area shows no scrollbars, assert the size applied; bound is the whole 3D view `getSize()` (AD-30); a window small enough to scroll the view is out of scope (F-27 not a defect) | 10.4 AC4 |
| 14 | :500, :501 | `the document is now suspect: ...`; no audit record | `document-suspect: a prior call timed out…` (`mcp_server.py:267-269`); assert no `camera_before` record | run |
| 15 | :523,547 | `git status --porcelain` | `git status --porcelain src` | run |
| 16 | :564,574,577, :566,579 | `verify_shape` digest; modified state | `preview_dry_run.fingerprint_before` or whole `structured_content`; compare "unchanged across the fit" | run |
| 05 | :203, :198 | disagreement → bugs.md; animation preference | exclude face tone (decision 4); drop the unfalsifiable preference Then | AC2, run |

## TC-99

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| a | :71,96,104 | `44 tools` | live count | AC1 |
| e | :78,101,136,155,197,215,252,267,321,338,386,395 | 1.1.1 | drop version | AC1 |
| d | :77,135,196,251,320,385 | golden fit | Show All | AC1 |
| cite | :68,72,130,417-418 | `entry.py:157`, `:38`, `:145-157` | `Starlette(routes=[Route("/healthz"), Mount("/mcp")])` `entry.py:122-125`; `_HOST` `:44` | b792cad |
| AC3 | 04 :181-221, 05 :242-272, 07 :366-401, gap table :419-422 | "no session workdir", `$TEMP`, "no sweep" | split per spec Decisions | AC3 |
| 06 | :293-345 | cwd-relative default; GUI fails in Program Files | GUI defaults `%APPDATA%\FreeCAD\v1-1\freecad-buddy\audit.jsonl` (`operator_settings.py:88`); deviation becomes "one undated shared file outside the workdir, no session field"; delete the severity paragraph | a07929b |
| hdr | :7, :13 | "all six failing"; "as the table directs" | recount; name TC-11 as target | AC3 |

AC3 implemented parts (promote): workdir set at bridge start (GUI `%APPDATA%\FreeCAD\v1-1\freecad-buddy\workdir`, env `FREECAD_BUDDY_WORKDIR`); one `FCB_TMP_session_<pid>_<token>` folder per host under `tmp/`; every bridge temp file there (snapshot `transaction.py:107`, preview `preview.py:325`, fingerprint `fingerprint.py:120`, screenshot `screenshot.py:187`); nothing in `$TEMP`; session-start sweep (`bootstrap.py:139`, `worker.py:107`) logs `session-start sweep removed N leftover temp artifact(s)`, touches only `FCB_TMP_` entries, removes a session folder only for a dead pid, never scans `$TEMP` (`documents.py:76-115`). TC-99-07 promotes whole once its `$TEMP` expectations go.

AC3 remaining gap (expected-fail): no `snap/` and `exports/`; snapshot named `<Name>.FCStd` in its own `mkdtemp`, not `<Name>.<txid>.FCStd`; workdir is one shared folder, not session-named; headless default is cwd-relative (`documents.py:43`); audit log not in the workdir, not dated, no session field (`audit_log.py:24-26`, `:51-58`) — all of TC-99-06.

## Suite docs

| id | where | current | change | reason |
| --- | --- | --- | --- | --- |
| AC7 | coverage-matrix.md:144,152,179 | `debug_exec (gated)`, "when the flag is unset", `debug_exec gating` | script_exec posture | AC7 |
| cnt | coverage-matrix.md:27-31, :50-51, :55, :189, :210-211 | 258 / 252 / 6, AD-25 gap row | recompute after promotion; AD-25 row names implemented vs gap; `shipped: 45` stays | AC3 |
| AC7 | test-plan.md:5-7, :169, :260 | `45 tools … plus debug_exec … ALLOW_EXEC=1`; env table row | live count; script_exec posture; rows for `SCRIPT_EXEC`, `UNATTENDED`, `SCRIPT_EXEC_UNATTENDED` (preference key `ScriptExec`, `shim.py:32`) | AC7 |
| a | test-plan.md:109, :205 | `On FreeCAD 1.1.1` | live version | AC1 |
| AC3 | test-plan.md:170, :180, :340-342 | invariant list without AD-25/26; Gate 2 AD-25 text | add AD-26 (TC-10), AD-25 implemented part; Gate 2 keeps only the gap | AC3 |
| doc | test-plan.md:365-369 | H2 lacks suspect logic, non-string guard, audit writes | stale: GUI listener has all three (`rpc_listener.py:417-424`, `:437-449`) | source |
| AC7 | APPENDIX-B:130, :134-137, :140, :200 | `exactly 45`; `debug_exec is ABSENT`; `exec_enabled must be false` | live count; script_exec present by default plus off postures and refusal text; `exec_enabled` true by default | AC7 |
| a | APPENDIX-B:66, :73, :196 | `H1 ok 1.1.0`, `GUI is 1.1.1`, `expect 1.1.1` | record both versions live | AC1 |
| AC7 | README.md:3-4, :39 | `45 tools plus the gated debug_exec`; 1.1.1 | live count, script_exec on by default; drop version | AC7 |
| AC3 | APPENDIX-A:54, :56 | AD-25 "No session workdir … no sweep"; `audit_log.py:23`; `§7 Gate 2` | remaining gap only; `:24-26`; `§9` | AC3 |
