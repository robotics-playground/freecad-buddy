# Run Report — 2026-09-13-02

**Operator:** agent-executed
**Scope requested:** TC-05 .. TC-14 (fresh run; prior-run findings not carried over)
**Scope completed:** 70 scenarios — 66 PASS, 4 FAIL — across TC-05 (4), TC-06 (2), TC-07 (12),
TC-08 (11), TC-09 (15), TC-11 (7), TC-12 (3), TC-13 (7), TC-14 (9)
**Outcome:** **3 product defects** — two in Epic 8's `view_fit_viewport` (both high), one in Epic 1's
render lighting (medium). Epic 3's mutation, rollback, TNP and confirm-token surfaces, and Epic 1's
export/verification pairing, passed everything run against them, visuals included.

## Build banner

| Field | Value |
| --- | --- |
| FreeCAD | 1.1.1 |
| `element_map_available` | `true` (`15.70200.5`) |
| `serializer` | `exportBinary` |
| `render` | `gui_constructed` |
| `exec_enabled` | **`false`** — every `debug_exec`-gated scenario is not-exercised |
| Host | GUI addon + auto-spawned H2 proxy on `:8765` |
| FreeCAD pid / window | 26912 / 398030 |

## Harness gate

Both capabilities verified before authoring, per `manual-testing` §0:

- **Control** — `cua-driver` drives the live FreeCAD window (`launch_app`, `click` on the
  **Fit All** toolbar button returned `route: "accessibility"` and reframed the view).
- **Observation** — `get_window_state` writes real window pixels to
  `evidence/*.png`, which the agent `Read`s and judges.

## Results

| Scenario | Verdict | Note |
| --- | --- | --- |
| TC-05-01 | **FAIL** | Every envelope assertion passed; the closing visual failed. `view_fit_viewport` left the solid clipped at the bottom viewport border. Finding **R2-01**. |
| TC-05-04 | **PASS** | `touched` = `["Fillet","Body"]`, `Sketch` absent, preview set equals apply set. Pixels show exactly one rounded edge. |
| TC-05-05 | **PASS** | Rollback proven and visually confirmed: envelope, document state, and pixels all agree the impossible fillet left no trace. |
| TC-05-09 | **PASS** | Follow-up mutation succeeded after a failure path, own bracket (`transaction_id: "0"`), `document_undo` reverted the follow-up (`undone: "buddy: feature_fillet GoodFillet"`, `matches_pre_op: true`), zero snapshots leaked. |
| TC-14-01 | **FAIL** | Schema assertions all pass — 45 tools, `doc` the only property, `required: ["doc"]`, `additionalProperties: false`, no `confirm`. Closing visual fails for **R2-01**. |
| TC-14-04 | **PASS** | The 40x40x800 bar (the regression guard for `636fb8a`) fits: `ratio` 0.8137, `fits: true`, pixels show the whole bar at ~78 % of viewport height. |
| TC-14-07 | **PASS** | Unknown handle refused `INVALID_INPUT` at `documents.py:148`, before any viewport work. |
| TC-14-08 | **PASS** | Unknown key `zoom` hard-rejected: `isError: true`, "Additional properties are not allowed". |
| TC-14-10 | **PASS** | Every camera move audited with the verbatim pre-fit `OrthographicCamera` block it replaced. |
| TC-14-11 | **PASS** | A non-fitting model appends the framing warning to ordinary tool results (observed on `feature_pad`, `query_mass_properties`, `query_tree_summary`). |
| TC-14-06 | **FAIL** | A handle naming a document the viewport is not showing was **not** refused — it returned `fitted: true` and moved the camera. Finding **R2-02**. |
| TC-14-09 | **PASS** (partial) | A document with no visible shape-bearing object degrades honestly: `fits: null`, `checked: "unavailable"`, named `stale_reason`, never a guess. The headless leg of this scenario was not run. |
| TC-14-16 | **PASS** | Repeated fits altered no geometry: volume 64000.0, bbox 40x40x40, 6/12/8 counts unchanged. |
| TC-08-02 | **PASS** | The preview computed a full diff while the live document stayed at its prior volume — the TempDoc never leaked into the live state. |
| TC-08-07 | **PASS** | Token single-use: reuse refused, `confirm.preview_id has already authorized a mutation` (`confirm.py:260`). |
| TC-08-08 | **PASS** | Token bound to its minting tool: `was issued for 'feature_set_parameters', not 'feature_pad'` (`confirm.py:266`). |
| TC-08-09 | **PASS** | Token bound to its arguments: `was issued for different arguments` (`confirm.py:270`). |
| TC-08-13 | **PASS** | A refused call does not spend its token — the same token survived four distinct refusals and then committed successfully. |
| TC-08-14 | **PASS** | Tampered signature refused as `carries an invalid signature` (`confirm.py:174`), checked before any payload claim is trusted. Four refusal messages are mutually distinct. |
| TC-08-15 | **PASS** | Undeclared confirm field `approved` refused: "Additional properties are not allowed", never silently dropped. |
| TC-08-16 | **PASS** | `elicitation_action: "decline"` refused: `'decline' is not one of ['accept']`. |
| TC-08-17 | **PASS** | A gated mutation with no `confirm` fails closed with actionable guidance (`confirm.py:195`). |
| TC-08-19 | **PASS** | Previewing `query_tree_summary` refused, listing all 19 previewable tools (11 `feature_*`, 8 `sketch_*`). |
| TC-08-20 | **PASS** | `operation.args` carrying `doc` refused (`preview.py:382`). |
| TC-06-01 | **PASS** | MCP iso render matches the live iso viewport: same silhouette, same camera corner, proportions match the 10x20x30 bbox, three faces shaded with no black side, one object with no Body/Sketch/Origin leak. AA configured `4`. |
| TC-06-02 | **FAIL** | Orientation is correct — `front` renders 1:3 (10x30), `top` 1:2 (10x20), matching the bbox. But all four axis-aligned cameras render the face **pure white**, indistinguishable from the background. Finding **R2-03**. |
| TC-07-01 | **PASS** | All five assertion types graded with their arithmetic shown: volume 6000.0 exact, bbox 10/20/30 exact, solid_count, valid, watertight. |
| TC-07-05 | **PASS** | `export_step` returns `verified: false` — it never self-certifies. |
| TC-07-06 | **PASS** | STL and 3MF both report 12 facets from one tessellation source (`linear` 0.1, `angular` 0.5). |
| TC-07-07 | **PASS** | `verify_export_step` re-imported and graded against source: volume 6000.0, valid, topology 6/12/1 all matching. |
| TC-07-08 | **PASS** | `verify_export_stl` merged three legs — `trimesh_stl`, `stl2`, `self_read` — 12 checks, `oracle.agreement` true. Volume band ±146.67 (deflection-derived, not a percentage). |
| TC-07-09 | **PASS** | `verify_export_3mf` merged the `lib3mf` container layer (parses, unit=mm, manifold, metadata) with `trimesh_3mf` geometry and self-read. |
| TC-07-12 | **PASS** | An omitted `objects` exported the document's sole object (same 6854 bytes as the explicit form). |
| TC-07-13 | **PASS** | Compound round-tripped with **both** solids preserved (`solids: 2 vs 2`, volume 2000.0, `com: null` as the fixture specifies). Genus-1 `box40-hole-r5` measured 15214.601836 against the hand-computed 15214.6018. |
| TC-07-16 | **PASS** | A FAILED export left **no file and no directory** at the target path; the failure came back as an envelope, not a raised error. |
| TC-07-18 | **PASS** | A STEP `export_id` passed to the STL verifier refused: `is not a stl export` (`exports.py:385`). |
| TC-07-20 | **PASS** | The discriminating pair holds: `wrong-volume` DETECTED (`SPEC_FAILED`, 7200 vs 6000) and `clean-control` PASSED (`OK`) — detection, not indiscriminate rejection. `non-watertight-open-shell` also detected (watertight `false vs true`, solids `0 vs 1`). |
| TC-07-21 | **PASS** | An export never self-reports verified; only the paired verify completes it. |
| TC-09-02 | **PASS** (partial) | Every status observed this run — `OK`, `SPEC_FAILED`, `RECOMPUTE_ERROR`, `INVALID_INPUT` — is inside the closed 7-member set at `contracts/status.py:12-18`. `TIMEOUT`/`OOM_KILLED`/`WORKER_CRASHED` were not reachable without the destructive scenarios. |
| TC-09-03 | **PASS** | Missing required field: `'doc' is a required property`. |
| TC-09-04 | **PASS** | Wrong JSON type: `'two' is not of type 'integer'`. |
| TC-09-05 | **PASS** | Unknown key rejected on every tool tried (`max_nodes`, `zoom`, `approved`). |
| TC-09-06 | **PASS** | Every field declaring `minItems: 1` rejects `[]` with `should be non-empty` (`sketch_add_geometry.geometry`, `feature_fillet.edges`, `sketch_remove_geometry.geo_ids`). `export_*.objects` declares no `minItems`, so the rule does not apply there. |
| TC-09-07 | **PASS** | `depth: 0` refused: `0 is less than the minimum of 1`. |
| TC-09-11 | **PASS** | Retired `max_nodes` is a schema rejection, not a silent ignore. |
| TC-09-12 | **PASS** | Unknown doc handle returns `INVALID_INPUT` (`documents.py:148`). |
| TC-09-13 | **PASS** | Unknown object name returns `INVALID_INPUT`: `unknown object: NoSuchObject`. |
| TC-09-15 | **PASS** | Non-string `doc` rejected before dispatch: `123 is not of type 'string'`. |
| TC-09-16 | **PASS** | Nonexistent open path returns `INVALID_INPUT` naming the path and FreeCAD's own reason. |
| TC-09-20 | **PASS** | Audit log is append-only: 3818 lines, all parseable as one JSON object per line, size never shrank, first line unchanged. |
| TC-09-21 | **PASS** | Client errors log exactly **one INFO line** each; the full traceback stays in the envelope's `detail.data`. |
| TC-09-22 | **PASS** | **Zero** ERROR, CRITICAL or Traceback lines in `addon.log` across the whole session, despite ~20 deliberate error paths. |
| TC-09-23 | **PASS** | The server answers normally after the entire abnormal sweep; all four open handles remained valid. |
| TC-11-01 | **PASS** | `debug_exec` is genuinely **unregistered**, not merely erroring: `unknown method: debug_exec`. The two internal RPC-only tools are also filtered from `tools/list`. |
| TC-11-04 | **PASS** | With `debug_exec` unregistered, typed tools are the only mutation path on this host. |
| TC-11-06 | **PASS** | The MCP HTTP endpoint binds `127.0.0.1:8765` only; no `0.0.0.0` listener exists. |
| TC-11-07 | **PASS** (caveat) | The discovery file carries a 43-char session token and its Windows ACL grants only SYSTEM, Administrators and the owning user — no `Users`/`Everyone`. But `AreAccessRulesProtected: False`, so the protection is **inherited from `%APPDATA%`**, not set explicitly by the addon. |
| TC-11-10 | **PASS** | No reserved-prefix TempDoc leaked into `document_list` despite many `preview_dry_run` calls. |
| TC-11-15 | **PASS** | Audit log append-only (see TC-09-20). |
| TC-11-16 | **PASS** | The session token appears in **zero** audit lines, report files and evidence files. |
| TC-12-02 | **PASS** | A GUI-created document was adopted by MCP with a fresh handle, unprompted. |
| TC-12-05 | **PASS** | A GUI visibility toggle was observed by `query_tree_summary` (`visibility: false` -> `true`). |
| TC-12-13 | **PASS** | Closing a document in the GUI invalidated its handle cleanly. |
| TC-13-01 | **PASS** | The GUI tree roots match `document_list` exactly, in the same order. |
| TC-13-02 | **PASS** | Object identity parity: MCP `name`/`type`/`error` agree with the GUI tree item. |
| TC-13-13 | **PASS** | `document_close` via MCP removed the root from the GUI tree. |
| TC-13-14 | **PASS** | A GUI visibility toggle was observed by MCP. |
| TC-13-15 | **PASS** | A GUI label rename was observed by MCP — and the evidence came from `query_tree_summary` **after the commit** (`label: "RenamedViaGui"`, `name` still the immutable `BoxHole`), never from the editor echoing its own value. This is the checkpoint the coverage matrix flags as worth protecting. |
| TC-13-16 | **PASS** | A GUI-opened/created document is seen by MCP and gets a handle. |
| TC-13-18 | **PASS** | A GUI-side close removed the document from MCP and invalidated the handle (`INVALID_INPUT`, not a stale read). |

## Notes carried by this run

- **TC-05 fillet scenarios use an unsupported selector.** TC-05-04/05/06/08/09 write
  `edges: [{kind: "geometric", object: "Pad", subelement: "Edge1"}]`. The shipped tools reject
  that: `edges[0] kind must be 'mapped_name'; 'geometric' is not resolvable by a feature tool`
  (`usecases/features.py:141-169` — `geometric` is rejected until a query resolver lands). The
  working form is `{kind: "mapped_name", object: "Pad", mapped_name: "Edge1"}`. This is a **test
  bug**, recorded here rather than in `bugs.md`, which holds product findings.
- **Stale snapshot directories could not be cleared.** 10 `FCB_TMP_snap_*` directories predating
  this run sit in `%TEMP%`; their ACLs are unreadable and removal is denied even unsandboxed, so
  TC-05's "no stale snapshots" precondition cannot be met literally. Snapshot assertions in this
  run are therefore made against **directories created after 13:30:32**, recorded in
  `evidence/pre-run-stale-snapshots.txt`. Zero new directories had been created as of TC-05-05.

## Scenarios NOT run

These are unverified, **not** passing.

| Scope | Why |
| --- | --- |
| TC-05-03, 05-06, 05-07, 05-08, 05-10 .. 05-14, 05-17 | Not reached. TC-05-10/11/12 additionally need `debug_exec`, and `exec_enabled` is `false` on this host — they are **not-exercised** by the file's own CONDITIONAL rule, not failures. |
| **TC-10 (all 14)** | **Not run.** Concurrency, timeout and quarantine need a second client and deliberate FreeCAD kills, which strand the MCP client mid-session. |
| TC-06-03 .. 06-12 | Not reached (styles, focus/highlight, resolution cap, dirty-document render, AA tracking). |
| TC-07-02, 03, 04, 10, 11, 14, 15, 17, 19 | Not reached. TC-07-11 needs a genuinely multi-object document; `two-box-compound` holds two solids in **one** object, so it exercised TC-07-13 instead. |
| TC-08-01, 03, 04, 05, 06, 10, 11, 12, 18, 21 | Not reached. TC-08-18's headless auto-approve leg needs the H1 host. |
| TC-09-01, 08, 09, 10, 14, 17, 18, 19 | Not reached. |
| TC-11-02, 03, 05, 08, 09, 11, 12, 13, 14 | Not reached. TC-11-02/03/08 need `FREECAD_BUDDY_ALLOW_EXEC=1` and auto-approve postures this host does not run. |
| TC-12-01, 03, 04, 06 .. 12, 14, 15 | Not reached. TC-12-14/15 are destructive (quit / unclean kill). |
| TC-13-03 .. 12, 17 | Not reached. |
| TC-14-02, 03, 05, 12, 13, 14, 15 | Not reached. TC-14-09/12's headless leg and TC-14-15's CI check need hosts this session did not start. |
| TC-99 (conformance gate) | Out of scope for this run. |

**The green gate is incomplete.** 70 of 259 scenarios ran (27 %). Do not read the passes above as a
release signal. Every destructive scenario (TC-10, TC-12-14/15, TC-14 restart paths) and every
`debug_exec`-gated scenario remains unverified.

## Findings

Five product defects — two high, one medium, two low. See `bugs.md` for the full write-ups and
`fix-plan.md` for the proposed work on the first three.

- **R2-01** — `view_fit_viewport` returns `fitted: true` while leaving the model clipped, and
  repeated calls never converge. Root cause: `_fill_factor` (`usecases/view_fit.py:168-191`)
  estimates the silhouette from the largest face diagonal, which is too small for compact models.
  Worst for a cube (ratio 1.0978). The 40x40x800 tuning case still passes, so this is a gap in the
  approximation's range, not a full regression of `636fb8a`.
- **R2-02** — the wrong-document guard can never fire, so a fit moves the camera of a document the
  human is not looking at. Root cause: `_require_same_document` (`view_fit.py:234-250`) compares the
  target against a view resolved *from the target's own name* (`hosts/gui_addon/viewport.py:54`), so
  the comparison is always true.

- **R2-03** (medium, Epic 1) — every axis-aligned camera (`front`/`top`/`right`/`back`) renders the
  model as a **pure white silhouette**, the same RGB as the background, while `iso` shades correctly.
  Measured by pixel count: `iso` 66789 shaded samples, each orthogonal view ~307 (anti-aliased edges
  only). Root cause: `_add_lighting` (`adapters/render_probe.py:81-100`) aims the headlight along the
  view direction, so a face perpendicular to the camera gets no diffuse term and ambient 0.7
  saturates it to white.

- **R2-04** (low, Epic 1) — `query_screenshot` leaves its `FCB_TMP_shot_*.png` in `%TEMP%`; five
  accumulated across this run. The neighbouring snapshot cleanup contract is honoured (zero
  `FCB_TMP_snap_*` leaked), so this path is the exception.
- **R2-05** (low, Epic 1) — `export_step` with a one-level-missing parent directory returned `OK` and
  **created the directory**, while a two-level-missing path correctly failed and created nothing.
  The contract differs by depth.

R2-01, R2-02 and R2-03 were confirmed against the source and against `cua-driver` pixel captures,
with the GUI's own **Fit All** used as an independent control for R2-01.

## What passed, and what that is worth

The invariants that carry the most risk held under every check run against them, and the visual
evidence agreed with the envelopes in every case:

- **Rollback is honest.** A failed mutation proved its rollback by re-hashing, the document was
  unchanged, and the window showed no trace of the attempt (TC-05-05).
- **The TNP guard works.** Changing a Pad beneath a dependent fillet was caught as `REPOINTED` with
  the witness movement named (`60.0 -> 75.0`), refused as `SPEC_FAILED`, and rolled back with proof
  (TC-05-16, TC-05-18). This is AD-7 doing exactly its job.
- **Confirm tokens are tight.** Single-use, bound to tool, arguments and document, signature-checked
  before any payload claim is trusted, and a refused call does not spend the token — verified by
  spending one successfully after four distinct refusals (TC-08-07/08/09/13/14/15/16/17).
- **Export pairing is real.** STEP re-imported and graded against source (volume, validity,
  topology 6/12/1); STL merged three independent oracle legs; 3MF merged container and geometry
  layers. An export never self-certifies — `verified: false` until the paired verify runs. A failed
  export left no file and no directory (TC-07-05/07/08/09/16/21).
- **The fault fixtures discriminate.** `wrong-volume` was DETECTED (7200 vs 6000) and
  `clean-control` PASSED in the same session — detection, not indiscriminate rejection (TC-07-20).
- **The error contract holds.** Every malformed input was rejected at the schema layer with a
  specific message; every client error logged exactly one INFO line; **zero** ERROR, CRITICAL or
  Traceback lines appeared in `addon.log` across ~20 deliberate error paths, and the server answered
  normally afterwards (TC-09-03 .. 09-23).
- **GUI and MCP agree in both directions.** MCP mutations reached the GUI tree and MCP observed GUI
  creates, closes, visibility toggles and a label rename — the rename read back from
  `query_tree_summary` after the commit, not from the editor echoing itself (TC-13-15).
- **`debug_exec` is unregistered, not merely refused.** `unknown method: debug_exec`, and the two
  internal RPC-only tools are filtered from `tools/list`. The endpoint binds loopback only, and the
  session token appears in zero audit lines, reports or evidence files (TC-11-01/04/06/16).
- **No snapshots leaked.** Zero `FCB_TMP_snap_*` directories were created by this run across every
  success and failure path exercised.
