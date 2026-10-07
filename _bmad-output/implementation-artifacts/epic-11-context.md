# Epic 11 Context: Lean Agent Loop

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Let an agent build a part with fewer calls and a small context, while every mutation still runs every check. The server checks everything; a result reports what changed and what failed, not every value that passed. With auto-approve on, a mutation applies in one call. Skills stop asking for checks the mutation result already reports. On a large document a change should freeze the GUI for FreeCAD's own recompute, not for bridge overhead. Trigger: three kiwibox-drawer build sessions on 2026-10-06 (`eacac40d`, `ff604ce5`, `0320ba38`) used 98-310 FreeCAD calls, reached 797K-820K context tokens, and compacted 8 times in the longest; 86 % of FreeCAD output was full fingerprints and PASS findings that no caller read. The epic closes on numbers: Story 11.6 measures one real build against that baseline. Opens no gate and reopens no epic (AD-19).

## Stories

- Story 11.1: Mass Properties That Tell Shapes Apart
- Story 11.2: Quiet Result Envelope
- Story 11.3: One Call per Mutation
- Story 11.4: Cheap, Correct Rollback Proof and Fingerprints
- Story 11.5: Build-Loop Skills
- Story 11.6: Measured Build Session

## Requirements & Constraints

- **No check removed or weakened.** Each story proves that the AD-5 bracket, the AD-6 rollback proof, the AD-7 audit and the AD-8 sketch signal still run and still fail a bad change. Checks decide on full data; only the serialized result shrinks. Re-run validator scores whose sources change. G2 fault suite fails or flags exactly as before. Never open `benchmarks/*/heldout`.
- **CAP-3 unchanged:** preview, confirm, auto-verify and provable rollback stay; `preview_dry_run` stays available.
- **Out of scope:** agent-decides `on_failure: "keep"` and a generic typed batch tool (rejected); sketch primitives, composite profile tool, clearance tool, TNP Layer 1 scoping, MCP elicitation (deferred until Story 11.4 and 11.6 numbers exist).
- **Reference document:** a copy of `kiwibox-drawer.FCStd` (184 objects); never edit the original.

### Story 11.6 measurement (epic acceptance)

- **Metrics script** goes in `scripts/automation/`. It reads Claude Code session transcripts and reports per session: FreeCAD calls, `preview_dry_run` calls, FreeCAD output chars, largest result, spilled results, peak context, compactions.
- **Transcript facts** (from Story 11.2): transcripts are `*.jsonl` under `C:/Users/thuan/.claude/projects/<project>/`; baseline ones live under `D--Work-3D-Printers-Ender-3V2---Klipper/`. A result is a `user` record with `tool_result` content joined to its `tool_use` id; FreeCAD tools are named `mcp__freecad-buddy__*`. A spilled result (over the client size limit) holds a stub that names a `tool-results/*.txt` file. `scripts/automation/replay_result_sizes.py` already parses this format.
- **Session under test:** Stories 11.1-11.5 done, auto-approve on, updated skills installed in the user project; an agent builds a part of the drawer size class (about 100+ objects) in the FreeCAD GUI.
- **Targets against `0320ba38`:**

| Measure | Baseline | Target |
|---|---|---|
| FreeCAD output chars per FreeCAD call | 9,590 | ≤ 1,440 (15 %) |
| Spilled results | 15 | 0 |
| Largest FreeCAD result | 109K | ≤ 10K |
| FreeCAD calls per feature (median) | 6 | ≤ 2 |
| Bridge overhead per mutation (median) | ~15 s apply / ~50 s preview + apply | ≤ 3 s (see conflict below) |
| Checks per mutation (AD-5/6/7/8) | all | all |

- Baseline 6 calls per feature = `DRY(sketch_create) > sketch_create > DRY(sketch_add_geometry) > sketch_add_geometry > DRY(feature_pocket) > feature_pocket`. The docs do not define how the script counts a "feature", how it detects a compaction, or how it reads peak context; the story must choose and state each rule.
- **Bridge-overhead method (Story 11.4):** `scripts/automation/time_mutation_overhead.py`; change `duct_pilot.Length` on the drawer copy; T = tool time, R = plain set + `recompute()` time; overhead = T − R; median of 5; warm gate (document fingerprinted untimed before each T). Story 11.4 result: 17.6 s headless, 9.4 s GUI (baseline `118e765`: 49.4 s headless). First call after open pays a cold fingerprint (31.6 s headless, 15.9 s GUI).
- **Visual and native proof:** the agent checks the finished part against a real FreeCAD screenshot, and native Check Geometry passes, per `.knowledge-base/technical/standards/testing/freecad-native-validation.md`. Launch per `freecad-gui-e2e-harness.md`.
- **Report:** baseline numbers beside new numbers, committed under `tests/uat/run/<date>-NN/`.
- Not verified by the proposal: baseline timings came from a headless probe; the GUI adds thumbnail render on save and view updates. "Fewer calls = less wall-clock time" assumes model time scales with turns.

## Technical Decisions

- **Mass properties (AD-6):** from the shape's solids; `MassProps.inertia` = `Ixx, Iyy, Izz, Ixy, Ixz, Iyz` about the COM in document axes. Moments and tensor round to a per-object step; `massprops_equal` compares `volume`, `area`, `com`, `principal_moments`, `inertia`. Documented limit: point reflection, 180° turn about a principal axis, symmetric-inertia rotations, and no-solid compounds stay equal.
- **Rollback proof (AD-5):** abort path proves by digest equality, else `massprops_equal` over the same object names; only an invariant mismatch restores the `saveCopy` snapshot. Gate fingerprint reused as `fp_before`; proof record reused as `fingerprint_after`; per-object fingerprint entry cache, rollback proofs compute fresh.
- **Wire projection (AD-6, AD-7, AD-17):** built in `usecases/`. `fcb.mutation/2` carries digests + serializer tag and `changed: [{name, volume, area, com}]` (adds before/after `MassProps` on failure). `fcb.geometry-diff/2`: `op = {tool}`. Audit blocks = `{status, element_map_version, counts, findings: [non-PASS only]}`. `changed` has no size cap; Story 11.6 measures it live.
- **Tool-results convention:** silent on pass, loud on fail; no echo of request arguments; compact JSON.
- **Auto-approve (AD-10):** `FREECAD_BUDDY_AUTO_APPROVE`, read at host start; on by default (unset or `1` = on, other values = off). A mutation without `confirm` applies in one call under the full AD-5 bracket and writes an audit `approval` with `mode: "auto_approve"`. Visibility-only `feature_set_parameters` is confirm-exempt display state.
- **Skills (AD-15):** per feature, read `post_verify`, `sketch_state`, `changed`; per milestone, one `verify_shape` and one screenshot packet (800 px default). No headless scripts on the live model. Derived pieces (print splits) stay out of the edit loop. `scripts/check_skill_shape.py` enforces 4 sections, ≤ 1,500 words.

## Cross-Story Dependencies

- Stories 11.1-11.5 are implemented (sprint status: review). Story 11.6 is last and depends on all of them.
- **Open conflict for 11.6 AC3:** a human decision (2026-10-07) replaced the Story 11.4 ≤ 3 s target with ≤ 18 s headless / ≤ 10 s GUI. Story 11.6 AC3 and the change proposal still say ≤ 3 s. The deferred-work ledger states 11.6 AC3 needs the same decision before it runs. Remaining overhead (cold-gate profile): `fingerprint` × 2 11.2 s, `verify_shape` `isValid` 5.3 s, `features._feature_state` 5.5 s, `saveCopy` 2.5 s.
- **Method gap for 11.6 AC3:** the 11.4 method times a scripted leaf change with a separate recompute measurement; AC3 asks for it "in the same session". The story must state how T − R is obtained for live agent mutations.
- Epic 10: Story 10.7 starts after 11.1-11.4; UAT cases TC-05 and TC-08 move to the `/2` shapes there.
- Operator: re-copy updated skills into the user project before the 11.6 session; leave auto-approve on.
