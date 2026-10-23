# Replay comparison

Old run: `tests/uat/run/2026-10-03-04`. Replay: `tests/uat/run/2026-10-23-01` (commit `3ca2addc3fb2cf38dac63b1745a62ce9dbabc45a`, `git_dirty: true`, FreeCAD 1.1.4).

Verdict map: old `PASS` and `PARTIAL` match runner `PASS`, or `ESCALATE` whose only reason is an `agent_check`; old `FAIL` matches runner `FAIL`; old `BLOCKED` and `SKIP` are not compared (row `new`).

255 rows: 32 same, 12 differs, 174 not covered, 30 not encoded, 7 new, 0 removed. Unexplained: 0.

| Scenario | Old verdict | Runner verdict | Row | Class or reason | Explanation |
|----------|-------------|----------------|-----|-----------------|-------------|
| TC-01-01 | PASS | - | not covered | log or audit read | Thens grep addon.log for the listener and proxy spawn lines |
| TC-01-02 | PASS | - | not covered | H1 host | runs run_mcp_e2e.py on its own H1 stdio host |
| TC-01-03 | PASS | - | not covered | raw RPC or second client | tools/list from a second MCP client session |
| TC-01-04 | PARTIAL | - | not covered | raw RPC or second client | direct rpc_hello on the discovery record with the proxy stopped |
| TC-01-05 | PASS | - | not covered | file check | Thens read a catalog dump written to disk |
| TC-01-06 | PASS | - | not covered | raw RPC or second client | raw rpc_hello with contract_version 99 |
| TC-01-07 | PASS | - | not covered | raw RPC or second client | raw socket with a wrong or missing token; addon.log count |
| TC-01-08 | PASS | - | not covered | raw RPC or second client | raw first frame that is not rpc_hello |
| TC-01-09 | PASS | - | not covered | raw RPC or second client | rpc_hello with the discovery token; discovery file and netstat |
| TC-01-10 | PASS | - | not covered | process kill or relaunch | File > Exit (outside the menu allow-list) and process exit |
| TC-01-11 | PASS | - | not covered | raw RPC or second client | raw connect to a dead pid's port |
| TC-01-12 | PASS | - | not covered | process kill or relaunch | Stop-Process on the proxy, then a manual proxy restart |
| TC-01-13 | PASS | - | not covered | process kill or relaunch | launch with FREECAD_BUDDY_NO_AUTO_MCP and no proxy; CLI exit codes |
| TC-01-14 | PASS | - | not covered | process kill or relaunch | TerminateProcess on FreeCAD, then a relaunch |
| TC-01-15 | - | - | new | raw RPC or second client | curl /healthz, a foreign holder on :8765 and a relaunch; moved from TC-99-08 in 10.7 |
| TC-02-01 | PASS | PASS | same | - | Not checked: handle is not the FreeCAD Name (doc != name) (comparison op); save-as writes a non-empty file (ls -l) (file check); saved file still exists after the close (ls -l) (file check). |
| TC-02-02 | PASS | PASS | same | - | Not checked: every property value is JSON-safe, no repr of a live FreeCAD pointer (comparison op). |
| TC-02-03 | PASS | PASS | same | - | Not checked: Given: the save-as target does not exist before the save (file check); new file written, non-empty (ls -l) (file check); golden file mtime and size unchanged (file check); reopen yields a handle different from the first (comparison op). |
| TC-02-04 | PASS | PASS | same | - | Not checked: query on A returns Box while B is active after a sphere tree-item click (GUI action); handle A and handle B are different strings (comparison op). |
| TC-02-05 | FAIL | - | not covered | GUI action | Pad hidden by a tree click and Space |
| TC-02-06 | PASS | PASS | same | - | Not checked: Given: healthy state captured before the break (tc-02-06-before.png) (GUI action). |
| TC-02-07 | PASS | - | not covered | comparison op | key-set, membership and no-duplicate Thens |
| TC-02-08 | PASS | - | not covered | comparison op | global differs from local in at least one axis |
| TC-02-09 | PASS | - | not covered | process kill or relaunch | File > Exit, then a relaunch with the file argument |
| TC-02-10 | PASS | - | not covered | GUI action | tree click and Windows menu |
| TC-02-11 | PASS | - | not covered | raw RPC or second client | reads the advertised input schema from tools/list |
| TC-02-12 | PASS | ESCALATE | same | - | Not checked: Given: whole-document query_dependencies total_edges >= 2 (not encoded) (comparison op); Given: model framed with GUI Fit All and a before capture (GUI action). |
| TC-02-13 | FAIL | ESCALATE | differs | test case changed (10.7 edit) | Old FAIL on F-02 (save-as renames the label to the file stem). The product kept that behaviour (Story 10.1 D2); 10.7 changed the Then: the label after reopen is the stem and the Unicode check moves before the save. All scripted checks pass; agent_check only. Not checked: Given: the save-as target does not exist (file check). |
| TC-02-14 | PASS | - | not covered | timing bound | returns within its 30 s budget |
| TC-02-15 | PASS | ESCALATE | same | - | Not checked: query_tree_summary refusal carries schema and detail.code (text only on the wire) (raw RPC or second client); addon.log has no access violation, segfault or swig line (log or audit read); Given: baseline framed with GUI Fit All and a before capture (GUI action). |
| TC-02-16 | PASS | ESCALATE | same | - | Not checked: no orphan MDI child in the window after the double close (GUI action); addon log records no traceback for the second close (log or audit read); sphere-r10.FCStd size unchanged (ls -l) (file check); reopen returns a handle different from the released one (comparison op). |
| TC-02-17 | FAIL | ESCALATE | differs | test case changed (10.7 edit) | Old disputed FAIL (non-FCStd and corrupt zip share one refusal text). 10.7 made the shared text the expected behaviour (SCP 2026-10-04 decision 2). The pilot's checks pass; agent_check only. Not checked: Given: not-fcstd.txt and corrupt.FCStd prepared with printf (README.md stands in for the first) (file check); corrupt zip refused with 'document_open failed for ...corrupt.FCStd' (file check); non-FCStd file and corrupt zip share one refusal tail (file check); addon log records no unhandled traceback (log or audit read); Given: baseline framed with GUI Fit All and a before capture (GUI action). |
| TC-02-18 | FAIL | - | not covered | file check | sha256sum of the target and ls of the folder |
| TC-03-01 | PASS | - | not encoded | not encoded | all Thens are MCP reads; left to Story 10.8 |
| TC-03-02 | PASS | - | not encoded | not encoded | all Thens are MCP reads; left to Story 10.8 |
| TC-03-03 | PASS | - | not encoded | not encoded | MCP reads with a script_exec fixture; left to Story 10.8 |
| TC-03-04 | PASS | - | not encoded | not encoded | all Thens are MCP reads; left to Story 10.8 |
| TC-03-05 | FAIL | ESCALATE | differs | product fixed (F-04, 10.2) | Old FAIL on F-04 (point read from center), F-05 (single-point DistanceX refused) and F-06 (redundancy result depended on order); Story 10.2 fixed all three, and 10.7 changed the arc constraints and type names. All scripted checks pass; agent_check only. |
| TC-03-06 | FAIL | ESCALATE | differs | product fixed (F-05, 10.2) | Old FAIL on F-05 and on test data (geo 5 outside the Given). Story 10.2 accepts the single-point form; 10.7 rewrote the Given into per-type groups. All 102 expect checks pass; agent_check only. |
| TC-03-07 | PASS | ESCALATE | same | - | Not checked: Given: starting state captured (tc-03-07-before.png) (GUI action). |
| TC-03-08 | PASS | - | not encoded | not encoded | all Thens are MCP reads; left to Story 10.8 |
| TC-03-09 | PASS | - | not covered | file check | lists FCB_TMP_snap_* folders in the session temp folder |
| TC-03-10 | PASS | - | not encoded | not encoded | cascade counts are known values; left to Story 10.8 |
| TC-03-11 | PASS | - | not encoded | not encoded | all Thens are MCP reads; left to Story 10.8 |
| TC-03-12 | PASS | - | not encoded | not encoded | all Thens are MCP reads; left to Story 10.8 |
| TC-03-13 | PASS | ESCALATE | same | - | Not checked: Given: pre-projection state captured (tc-03-13-before.png) (GUI action); tnp_audit counts.PASS >= 1 (not encoded) (comparison op); whole-document query_dependencies has edge BossProfile -> PlatePad (encoded as the object form, out_list equals [PlatePad]) (comparison op). |
| TC-03-14 | PARTIAL | - | not encoded | not encoded | all Thens are MCP reads; left to Story 10.8 |
| TC-03-15 | PARTIAL | - | not covered | file check | no snapshot is orphaned: folder listing |
| TC-03-16 | PASS | - | not encoded | not encoded | prior count by $step reference; left to Story 10.8 |
| TC-03-17 | PASS | - | not covered | file check | snapshot folder listing in Given and Then |
| TC-03-18 | PASS | - | not encoded | not encoded | schema refusals; left to Story 10.8 |
| TC-03-19 | PASS | - | not covered | file check | no snapshot left behind: folder listing |
| TC-03-20 | PARTIAL | ESCALATE | same | - | Not checked: Given: whole-document query_dependencies has edge BossProfile -> PlatePad (encoded as the object form) (comparison op); Given: intact state captured (tc-03-20-before.png) (GUI action); some finding is REPOINTED, owner BossProfile, prop AttachmentSupport (checked at findings.0 only) (comparison op). |
| TC-03-21 | PASS | - | not encoded | not encoded | schema refusals and tree regex; left to Story 10.8 |
| TC-04-01 | PASS | - | not encoded | not encoded | envelope and tree-text reads; left to Story 10.8 |
| TC-04-02 | PASS | PASS | same | - | - |
| TC-04-03 | PASS | ESCALATE | same | - | - |
| TC-04-04 | FAIL | - | not covered | comparison op | volume larger than 6000.0 and different from 6000.0 |
| TC-04-05 | PASS | - | not covered | comparison op | face_count higher than the plate's 6 |
| TC-04-06 | PARTIAL | - | not covered | comparison op | out_list membership |
| TC-04-07 | PASS | - | not covered | comparison op | face_count higher than the plate's 6 |
| TC-04-08 | PASS | - | not encoded | not encoded | enum readbacks and refusal messages; left to Story 10.8 |
| TC-04-09 | PASS | ESCALATE | same | - | Not checked: Given: topology oracle lists the four 5 mm Z-parallel edges as Edge1/2/5/8 (comparison op). |
| TC-04-10 | PASS | - | not covered | comparison op | face_count one higher than its base feature's |
| TC-04-11 | PASS | - | not encoded | not encoded | analytic volumes fixed by the fixture; left to Story 10.8 |
| TC-04-12 | PASS | - | not encoded | not encoded | exact solid counts and bbox; left to Story 10.8 |
| TC-04-13 | PARTIAL | - | not covered | comparison op | out_list lists PlatePad |
| TC-04-14 | PASS | - | not encoded | not encoded | needs an agent_check for the before/after capture; left to Story 10.8 |
| TC-04-15 | PARTIAL | - | not covered | comparison op | out_list lists BasePad |
| TC-04-16 | PASS | - | not covered | file check | snapshot folder listing |
| TC-04-17 | PARTIAL | - | not covered | file check | snapshot folder listing |
| TC-04-18 | PARTIAL | - | not encoded | not encoded | tree text equals an earlier read; left to Story 10.8 |
| TC-04-19 | PASS | - | not covered | file check | snapshot folder listing |
| TC-04-20 | PASS | - | not encoded | not encoded | MCP reads; left to Story 10.8 |
| TC-04-21 | FAIL | - | not covered | file check | snapshot folder listing |
| TC-04-22 | PASS | - | not covered | file check | snapshot folder listing |
| TC-04-23 | FAIL | - | not covered | file check | snapshot folder listing |
| TC-04-24 | PASS | - | not covered | file check | snapshot folder listing |
| TC-05-01 | PASS | - | not covered | comparison op | digests not equal; text carries a digest prefix of a step value |
| TC-05-02 | PASS | - | not covered | file check | snapshot and .FCBak listing of the session temp folder |
| TC-05-03 | FAIL | PASS | differs | product fixed (F-09, 10.3) | Old FAIL: a pad on an under-constrained sketch committed (F-09). Story 10.3 D3 grades the sketch a pad consumes; the pad now rolls back with SPEC_FAILED. Capture: the sketch outline only, no solid. Not checked: Given: pre-mutation window framed and captured (tc-05-03-before.png) (GUI action). |
| TC-05-04 | PASS | - | not covered | comparison op | touched contains / does not contain; set difference |
| TC-05-05 | PASS | - | not covered | file check | snapshot folder check after rollback |
| TC-05-06 | FAIL | - | not covered | file check | snapshot folder check |
| TC-05-07 | PASS | - | not covered | file check | os.path.exists on the snapshot path |
| TC-05-08 | FAIL | PASS | differs | product fixed (F-11, 10.3) | Old FAIL: with UndoMode 0 the envelope claimed rolled_back_verified while the broken fillet stayed (F-11, with F-10). Story 10.3 D4/D5 prove the snapshot rollback; the fillet now reports rolled_back_via_snapshot. Capture: the 20 x 20 x 30 pad, whole. Not checked: Given: pre-mutation window framed and captured (tc-05-08-before.png) (GUI action). |
| TC-05-09 | PASS | - | not covered | file check | snapshot folder check |
| TC-05-10 | PASS | - | not covered | file check | snapshot folder check |
| TC-05-11 | PASS | - | not covered | file check | os.path.exists on the snapshot path |
| TC-05-12 | PASS | - | not covered | file check | snapshot folder check |
| TC-05-13 | PASS | - | not covered | comparison op | two handles and two digests differ |
| TC-05-14 | FAIL | PASS | differs | product fixed (F-12, 10.1) | Old FAIL: an incomparable expect_fingerprint ran the undo and returned matches_pre_op false (F-12). Story 10.1 validates the record before the undo; both refusals now match the test case. Capture: the pad, unchanged. Not checked: Given: a second FreeCAD build with the other serializer (process kill or relaunch); Given: pre-attempt window framed and captured (tc-05-14-before.png) (GUI action); CONDITIONAL two-build: a cross-build comparison raises (process kill or relaunch). |
| TC-05-15 | FAIL | PASS | differs | test case changed (10.7 edit) | Old FAIL: a Pad Length edit broke the fillet reference and the TNP audit reported CLEAN although it did not run (F-13, fixed by Story 10.3 D6). 10.7 changed the When from the Pad Length edit to a fillet radius edit (2 to 3 mm), so the F-13 path is not exercised here. Capture: the pad with the 3 mm fillet. Not checked: Given: query_dependencies shows Fillet depends on Pad (comparison op); Given: pre-mutation window framed and captured (tc-05-15-before.png) (GUI action); every tnp_audit finding is RE_BASELINED (encoded as the other counts absent) (comparison op); tnp_audit counts.PASS >= 1 (encoded as present) (comparison op). |
| TC-05-16 | FAIL | - | not covered | comparison op | findings contains an entry with REPOINTED; layer is 1 or 2 |
| TC-05-17 | FAIL | - | not covered | comparison op | a BROKEN entry's owner is Fillet in an unordered list |
| TC-05-18 | FAIL | - | not covered | comparison op | scan of every tnp block for CLEAN with a null element_map_version |
| TC-06-01 | PARTIAL | - | not covered | file check | tone band read from the render PNG file; user.cfg read |
| TC-06-02 | PASS | - | not covered | GUI action | each camera set with the Standard Views toolbar |
| TC-06-03 | FAIL | ESCALATE | differs | product fixed (F-14, 10.4) | Old FAIL: include of a Body rendered a blank PNG (F-14). Story 10.4 D1 renders the Body Tip. Agent read (D4) of the render copies: tc-06-03-include-a.png shows PadA only, tc-06-03-exclude-a.png BoxB only, tc-06-03-include-body.png the BodyA Tip solid (not blank), tc-06-03-default.png both solids; no datum in any. agent_check only. |
| TC-06-04 | PARTIAL | ESCALATE | same | - | Agent read (D4) of the render copies: tc-06-04-red.png BoxA red, BoxB grey; tc-06-04-red-t80.png BoxA red and translucent with BoxB seen through it; tc-06-04-t0.png shows BoxA and tc-06-04-t100.png hides it, so the two differ where BoxA is drawn. Not checked: Given: untouched viewport captured (tc-06-04-before.png) (GUI action); viewport capture after the second call shows ObjectA in its own colour (GUI action). |
| TC-06-05 | PASS | ESCALATE | same | - | Agent read (D4) of the render copies: tc-06-05-focused.png fills more of the frame with BoxA than tc-06-05-unfocused.png; tc-06-05-highlight.png draws BoxA orange, BoxB grey. |
| TC-06-06 | PASS | - | not covered | GUI action | hides the object with a tree click and Space |
| TC-06-07 | PASS | ESCALATE | same | - | Agent read (D4) of the render copies: tc-06-07-custom.png shows the same view as tc-06-07-iso.png. |
| TC-06-08 | PASS | - | not covered | file check | PNG size read from the file |
| TC-06-09 | PASS | - | not covered | file check | lists FCB_TMP_shot_*.png in the temp folders |
| TC-06-10 | BLOCKED | - | new | file check | PNG on disk larger than zero bytes |
| TC-06-11 | SKIP | - | new | H1 host | runs on the headless H1 host |
| TC-06-12 | PARTIAL | - | not covered | file check | reads AntiAliasing from user.cfg |
| TC-07-01 | PASS | PASS | same | - | Not checked: checks holds the named id set (encoded as a fixed index order) (comparison op). |
| TC-07-02 | PASS | PASS | same | - | Not checked: checks holds exactly the named ids (encoded as a fixed index order) (comparison op). |
| TC-07-03 | FAIL | ESCALATE | differs | product fixed (F-17, 10.2) | Old FAIL: verify_sketch reported dof 0 for an under-constrained sketch opened from file (F-17). Story 10.2 D4 solves before it reads DoF; the scenario reads dof 4. agent_check only. Not checked: failed check ids include sketch.fully_constrained (checked at checks.0 only) (comparison op). |
| TC-07-04 | PASS | - | not covered | comparison op | element_map_version is an integer or null: a type check |
| TC-07-05 | FAIL | - | not covered | file check | grep FILE_SCHEMA in the STEP file; stat bytes |
| TC-07-06 | PASS | - | not covered | file check | stat and trimesh facet count |
| TC-07-07 | PASS | - | not covered | file check | outside-witness re-import reads the file |
| TC-07-08 | PASS | - | not covered | file check | truncates the STL, then a trimesh read |
| TC-07-09 | PASS | - | not covered | file check | lib3mf and trimesh read the file |
| TC-07-10 | PASS | - | not covered | file check | ls of the floor file; trimesh |
| TC-07-11 | PASS | - | not covered | file check | ls checks for partial files |
| TC-07-12 | PASS | - | not covered | file check | ls checks that no compound STEP exists |
| TC-07-13 | PASS | - | not covered | file check | trimesh Euler number |
| TC-07-14 | PASS | - | not covered | file check | ls and stat on the Unicode path |
| TC-07-15 | PASS | - | not covered | file check | stat after each write |
| TC-07-16 | PASS | - | not covered | file check | ls, find -size 0, ls -d |
| TC-07-17 | PASS | - | not covered | file check | trimesh reads the stale STL |
| TC-07-18 | PASS | - | not covered | file check | stat sizes and trimesh |
| TC-07-19 | PASS | - | not covered | file check | re-import of own.step |
| TC-07-20 | PASS | - | not covered | file check | trimesh on the exported fault STLs |
| TC-07-21 | PASS | - | not covered | file check | truncates the STL file; re-import |
| TC-08-01 | PASS | - | not covered | comparison op | diff.touched / diff.new contains Pad: set membership |
| TC-08-02 | PASS | - | not covered | file check | TempDoc check is a folder listing |
| TC-08-03 | PASS | PASS | same | - | Not checked: Given: framed fit and before capture before the pad (GUI action). |
| TC-08-04 | PASS | - | not encoded | not encoded | MCP reads; left to Story 10.8 |
| TC-08-05 | PASS | - | not covered | H1 host | headless no-render-port step |
| TC-08-06 | FAIL | - | not covered | comparison op | fingerprints differ from each other; restored_objects does not list Pad |
| TC-08-07 | PASS | - | not encoded | not encoded | MCP reads; left to Story 10.8 |
| TC-08-08 | PASS | PASS | same | - | Not checked: Given: framed fit and before capture before the preview (GUI action). |
| TC-08-09 | PASS | - | not encoded | not encoded | MCP reads; left to Story 10.8 |
| TC-08-10 | PASS | - | not encoded | not encoded | MCP reads; left to Story 10.8 |
| TC-08-11 | PARTIAL | - | not encoded | not encoded | MCP reads; left to Story 10.8 |
| TC-08-12 | PASS | - | not covered | timing bound | waits 901 s for the token to expire |
| TC-08-13 | PASS | PASS | same | - | Not checked: Given: framed fit and before capture before the preview (GUI action); decline refused with 'elicitation_action must be accept' (the MCP schema refuses it first) (raw RPC or second client). |
| TC-08-14 | FAIL | ESCALATE | differs | test case changed (10.7 edit) | Old disputed FAIL (3 distinct token messages, not 4). 10.7 asserts the shipped codec: fcb-preview:a.a gives 'is not decodable', four distinct messages (SCP 2026-10-04 decision 2). All scripted checks pass; agent_check only. Not checked: Given: framed fit and before capture before the variants (GUI action). |
| TC-08-15 | PASS | - | not encoded | not encoded | MCP reads; left to Story 10.8 |
| TC-08-16 | PASS | - | not encoded | not encoded | MCP reads; left to Story 10.8 |
| TC-08-17 | PASS | - | not covered | log or audit read | audit approval line mode display_state |
| TC-08-18 | PASS | - | not covered | H1 host | four H1 flag postures |
| TC-08-19 | PASS | - | not covered | file check | TempDoc folder check |
| TC-08-20 | PASS | - | not covered | file check | TempDoc folder check |
| TC-08-21 | PARTIAL | - | not covered | GUI action | a transaction left open by the GUI |
| TC-09-01 | PASS | - | not covered | H1 host | runs run_mcp_edge_cases.py on H1 |
| TC-09-02 | PASS | - | not covered | H1 host | Thens read the H1 sweep report |
| TC-09-03 | PASS | PASS | same | - | Not checked: Given: untouched window captured after the fit (tc-09-03-before.png) (GUI action). |
| TC-09-04 | PASS | - | not covered | file check | nothing was written: ls |
| TC-09-05 | PASS | - | not covered | file check | reads the tool surface JSON written from tools/list |
| TC-09-06 | PASS | - | not encoded | not encoded | refusals and envelope reads; left to Story 10.8 |
| TC-09-07 | PASS | - | not covered | log or audit read | no ValidationError traceback in stderr or addon log |
| TC-09-08 | FAIL | - | not covered | file check | grep -c AP242 on the written file |
| TC-09-09 | PASS | - | not covered | log or audit read | no handshake or frame-size error in the addon log |
| TC-09-10 | FAIL | - | not covered | log or audit read | grep RecursionError in stderr and the addon log |
| TC-09-11 | PASS | - | not covered | H1 host | reads the H1 edge report |
| TC-09-12 | PASS | PASS | same | - | Not checked: Given: untouched window captured after the fit (tc-09-12-before.png) (GUI action); query_tree_summary unknown handle: status and detail.code (text prefix only on the wire) (raw RPC or second client). |
| TC-09-13 | FAIL | - | not covered | file check | failed export wrote nothing: ls |
| TC-09-14 | PASS | - | not covered | log or audit read | addon log carries one INFO line per refusal |
| TC-09-15 | PASS | - | not covered | H1 host | same call on H1 and on H2 |
| TC-09-16 | PASS | - | not covered | H1 host | reads the H1 edge report |
| TC-09-17 | PASS | ESCALATE | same | - | Not checked: at least one check recompute.object with passed false (checked at checks.0 only) (comparison op); _RECOMPUTE_ERROR_STATES at verify.py:22 includes Touched (encoded as measured equals Touched) (file check). |
| TC-09-18 | PASS | ESCALATE | same | - | Not checked: Pad's recompute.object check picked by index checks.1 (comparison op). |
| TC-09-19 | PASS | - | not covered | H1 host | starts an H1 server with an unwritable audit path |
| TC-09-20 | PASS | - | not covered | H1 host | H1 audit file |
| TC-09-21 | PASS | - | not covered | H1 host | edge sweep stderr |
| TC-09-22 | PASS | - | not covered | H1 host | both sweeps and their stderr |
| TC-09-23 | PASS | - | not covered | file check | lists the session temp folder; tools/list count |
| TC-10-01 | PASS | - | not covered | H1 host | run_mcp_e2e.py on H1 plus a span-timing client |
| TC-10-02 | PASS | - | not covered | H1 host | H1 latency sweep |
| TC-10-03 | PASS | - | not covered | raw RPC or second client | clients B and C on raw listener sockets |
| TC-10-04 | PASS | - | not covered | raw RPC or second client | raw clients A, B and C with the proxy stopped |
| TC-10-05 | PASS | - | not covered | H1 host | 100 s preview_dry_run on an H1 session |
| TC-10-06 | FAIL | - | not covered | raw RPC or second client | raw listener sessions A and B |
| TC-10-07 | PASS | - | not covered | H1 host | H1 script_exec timeout and quarantine |
| TC-10-08 | PASS | - | not covered | H1 host | same H1 session |
| TC-10-09 | PASS | - | not covered | H1 host | same H1 session |
| TC-10-10 | PASS | - | not covered | H1 host | same H1 session; audit Thens |
| TC-10-11 | FAIL | - | not covered | H1 host | H1 verify_recompute read timeout |
| TC-10-12 | FAIL | - | not covered | raw RPC or second client | tools/list and /healthz after a FreeCAD kill |
| TC-10-13 | PARTIAL | - | not covered | raw RPC or second client | raw socket closed mid-frame |
| TC-10-14 | PASS | - | not covered | raw RPC or second client | 17 MiB stream and a non-UTF-8 frame on raw sockets |
| TC-11-01 | PASS | PASS | same | - | Not checked: H1 tools/list length is the typed count + 1 (H1 host); script_exec listed on H1, and the proxy tools/list matches (H1 host); H1 stderr has the SECURITY script_exec ENABLED warning (H1 host); GUI addon.log has the same SECURITY warning (log or audit read); exec_enabled true on H1 query_capabilities (H1 host); script_exec on an H1 document returns value_repr '0' (the scenario runs it on the GUI box: '1') (H1 host); H1 audit has two exec lines, the second verify_verdict OK (H1 host); grep of src/ for ALLOW_EXEC, AllowExec, debug_exec finds nothing (file check); Given: addon.log operator settings line has FREECAD_BUDDY_SCRIPT_EXEC='1' (log or audit read); Given: framed baseline captured (tc-11-01-before.png) (GUI action). |
| TC-11-02 | PASS | - | not covered | H1 host | six H1 starts |
| TC-11-03 | PASS | - | not covered | H1 host | H1 plus an audit read |
| TC-11-04 | PASS | - | not covered | H1 host | H1 surface and preview |
| TC-11-05 | PASS | - | not covered | raw RPC or second client | LAN connect and raw rpc_hello |
| TC-11-06 | PASS | - | not covered | raw RPC or second client | curl to the LAN address |
| TC-11-07 | PASS | - | not covered | raw RPC or second client | wrong-token handshake; discovery file |
| TC-11-08 | FAIL | - | not covered | H1 host | auto-approve audit on H1 |
| TC-11-09 | PASS | - | not covered | raw RPC or second client | old-token handshake after a relaunch |
| TC-11-10 | PASS | - | not covered | H1 host | runs on H1 and H2; temp-folder listing |
| TC-11-11 | PASS | - | not covered | H1 host | workdir counts on H1 |
| TC-11-12 | PARTIAL | - | not covered | H1 host | H1 fault patches |
| TC-11-13 | PASS | - | not covered | file check | helpers in a separate interpreter; file existence |
| TC-11-14 | PASS | - | not covered | H1 host | folder mtimes on H1 and H2 |
| TC-11-15 | PASS | - | not covered | H1 host | two H1 batches and the audit file |
| TC-11-16 | PASS | - | not covered | raw RPC or second client | rpc_hello; log greps |
| TC-11-17 | - | FAIL | new | - | New in 10.7. FAIL on the pixel finding 'view: expected a 3D view, observed null': the first query_capabilities of a launch leaves the probe with no active 3D view (open product finding in deferred-work.md, shim.py opens its probe documents without hidden=True). Agent read: the window shows the box whole and framed, no dialog. Not checked: H1 refuses with INVALID_INPUT and the exact 'script_exec is off: ...' message (H1 host); H1 audit has two exec lines, the second verify_verdict INVALID_INPUT (H1 host); H1 query_tree_summary has no Leak line (H1 host); GUI audit log line count unchanged (log or audit read); Given: addon.log has FREECAD_BUDDY_SCRIPT_EXEC='0' and no SECURITY ENABLED line (log or audit read); Given: GUI audit.jsonl line count recorded (log or audit read); Given: framed baseline captured (tc-11-17-before.png) (GUI action). |
| TC-11-18 | - | - | new | H1 host | H1 workdir session folder; added in 10.7 from parts of TC-99-04/05 |
| TC-11-19 | - | - | new | H1 host | start sweep needs a relaunch and addon.log; moved from TC-99-07 in 10.7 |
| TC-12-01 | PASS | - | not covered | GUI action | model built through menus and clicks |
| TC-12-02 | PASS | - | not covered | GUI action | File > New Document |
| TC-12-03 | PASS | - | not covered | process kill or relaunch | quit and relaunch with a file argument |
| TC-12-04 | PASS | - | not covered | GUI action | tree-row selection click |
| TC-12-05 | PASS | - | not covered | GUI action | row click plus a visibility toggle |
| TC-12-06 | PASS | - | not covered | GUI action | Undo dropdown and Edit > Undo |
| TC-12-07 | PARTIAL | ESCALATE | same | - | Not checked: Given: toolbar Recompute button reads disabled (GUI action); GUI dirty state: Recompute enabled and the touched marker in the tree (GUI action). |
| TC-12-08 | PASS | - | not covered | file check | LastWriteTime and Test-Path |
| TC-12-09 | PASS | - | not covered | GUI action | modal dialog read through list_windows |
| TC-12-10 | PASS | - | not covered | GUI action | workbench combo clicks |
| TC-12-11 | PASS | - | not covered | GUI action | tree scroll |
| TC-12-12 | PARTIAL | - | not covered | GUI action | Start-page card double-click |
| TC-12-13 | FAIL | - | not covered | GUI action | Windows menu plus File > Close |
| TC-12-14 | PASS | - | not covered | process kill or relaunch | File > Exit and restart |
| TC-12-15 | FAIL | - | not covered | process kill or relaunch | forced FreeCAD kill |
| TC-13-01 | PASS | - | not covered | GUI action | TreeItem set from the accessibility tree |
| TC-13-02 | PARTIAL | - | not covered | GUI action | tree-row click, status bar, face hover |
| TC-13-03 | FAIL | - | not covered | GUI action | Space keystroke toggles visibility |
| TC-13-04 | PASS | ESCALATE | same | - | - |
| TC-13-05 | PASS | - | not covered | GUI action | row select to fill the property panel |
| TC-13-06 | FAIL | ESCALATE | differs | test case changed (10.7 edit) | Old FAIL only on the shading clause (F-29). 10.7 replaced it with the AD-34 tone band; a different tone order is not a defect (SCP 2026-10-04 decision 4). All scripted checks pass; agent_check only. Not checked: scene.rendered_objects contains BoxHole (encoded as index 0 equals BoxHole) (comparison op). |
| TC-13-07 | PARTIAL | - | not covered | GUI action | expand Body and select the Pad row |
| TC-13-08 | PASS | - | not covered | GUI action | TreeItem sets before and after |
| TC-13-09 | PASS | - | not covered | GUI action | TreeItem rows |
| TC-13-10 | PASS | - | not covered | GUI action | expand Body by a click; Fit All button |
| TC-13-11 | PASS | - | not covered | GUI action | property panel Length row |
| TC-13-12 | PASS | - | not covered | GUI action | property panel Length row |
| TC-13-13 | PASS | - | not covered | GUI action | TreeItem sets before and after |
| TC-13-14 | PASS | - | not covered | GUI action | Space keystroke |
| TC-13-15 | PARTIAL | - | not covered | GUI action | F2 rename and Ctrl+Z |
| TC-13-16 | PARTIAL | - | not covered | GUI action | double-click on the Start page |
| TC-13-17 | BLOCKED | - | new | GUI action | Recompute button enabled state from the accessibility tree |
| TC-13-18 | PASS | - | not covered | GUI action | Windows menu and File > Close |
| TC-14-01 | PASS | - | not covered | raw RPC or second client | reads the schema with a second MCP client |
| TC-14-02 | PASS | PASS | same | - | - |
| TC-14-03 | PASS | - | not covered | GUI action | View > Zoom is outside the menu allow-list |
| TC-14-04 | PASS | - | not encoded | not encoded | ratio bound as a regex on the framing line; left to Story 10.8 |
| TC-14-05 | PARTIAL | - | not covered | file check | cmp of the before and after PNGs |
| TC-14-06 | PASS | - | not encoded | not encoded | ratio equality through framing.ratio; left to Story 10.8 |
| TC-14-07 | PASS | PASS | same | - | - |
| TC-14-08 | PASS | - | not encoded | not encoded | schema refusals by regex; left to Story 10.8 |
| TC-14-09 | PASS | - | not covered | H1 host | headless host |
| TC-14-10 | PASS | - | not covered | log or audit read | reads the audit log tail |
| TC-14-11 | PASS | - | not covered | GUI action | camera zoomed through the GUI |
| TC-14-12 | PASS | - | not covered | H1 host | headless host |
| TC-14-13 | FAIL | - | not covered | GUI action | window resize with set_window_frame |
| TC-14-14 | PASS | - | not covered | H1 host | headless host |
| TC-14-15 | PASS | - | not covered | file check | writes a file under src/ and greps it |
| TC-14-16 | PARTIAL | PASS | same | - | Not checked: Modified state unchanged across the fit, read from the window title (GUI action). |
