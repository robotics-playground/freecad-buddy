---
title: 'Quiet result envelope'
type: 'feature'
created: '2026-10-07'
status: 'done'
baseline_commit: 'ffd493e5a6502ce4cf3b0182fe620cf282926a4b'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/data-contracts-design.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A mutation or preview result carries two full `FingerprintRecord`s and every TNP finding, PASS included, as indented JSON. On the three 2026-10-06 sessions, 529 FreeCAD results total 6.80M chars, 171 are over 10K, 22 spilled to files; no caller reads the per-object records or the PASS findings.

**Approach:** One pure projection module in `usecases/` turns the full internal block into the wire shape the design documents already state: `fcb.mutation/2` (digests + `changed`), `fcb.geometry-diff/2` (`op = {tool}`), audit blocks with `counts` and non-PASS findings. The full records stay in a bounded digest-keyed cache that `document_undo` reads. `adapters/mcp_server.py` writes compact JSON. A replay script proves the size drop on the recorded results.

**Decisions (human, 2026-10-07):**
- D1 — AC8 replay: a recorded result whose text is not valid JSON (Claude Code cut it and kept no spill file) is excluded and named in the report. AC8 is measured on the 528 parseable results of the 529 set; the excluded one is the `0320ba38` `feature_set_parameters` SPEC_FAILED result.
- D2 — `fcb.mutation/2` also drops `transaction_id` (always `"0"`), `verify_verdict` (same as the envelope `status`) and `params_digest` (the audit log keeps it); `snapshot_path` is present only when not null. `rolled_back` and `rollback_proven` stay on every block, as the design example shows. The audit log keeps all of these: it is written from the full block before projection.
- D3 (during implementation) — G2.3 semantics: a digest string the cache resolves is compared like a record (digest, else `massprops_equal`), so a pad-over-sketch undo reports `matches_pre_op: True` while the digests differ (DW-97 fix option (b) for published digests). `tests/infc/test_g2_driver.py:166` is rewritten to assert `matches_pre_op` True AND `fingerprint_before != fingerprint_after`. The closed G2 gate is not re-run; DW-97 gets a note.
- D4 (during implementation) — AC8 replay input: the recorded records predate `inertia`, and the strict rule then lists every object as changed. Production keeps the one strict rule. The replay script alone fills a missing `inertia` with the same placeholder on both sides before projecting, and its report states it. Known limit: a recorded object whose only change was a rotation is not listed. D1 also excludes non-envelope results (the 113-char `query_screenshot` client validation error).

## Boundaries & Constraints

**Always:**
- Every check still runs on the full data: `post_verify` decides on the full finding list, the rollback proof compares full records. Only the serialized result shrinks.
- Projection is pure and stdlib-only (imports `contracts/` only), so the replay script and pytest run it without FreeCAD.
- `changed` uses the same per-object invariants as `massprops_equal` (`volume`, `area`, `com`, `principal_moments`, `inertia`).
- `/1` schemas stay on disk for audit replay (AD-28).

**Never:**
- No change to `usecases/tnp_guard.py`, `usecases/fingerprint.py`, the digest rule, or `confirm.py` / the fingerprint call count (Story 11.4).
- No edit to recorded UAT evidence under `tests/uat/run/`; UAT test-case documents move to the new shape in Story 10.7.
- No skill text changes (Story 11.5).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Pad commits | 1 new object, 1 modified | `fingerprint_*` = `{digest, serializer}`; `changed` has 2 entries `{name, volume, area, com}` with after values | N/A |
| No-op mutation | invariants equal | `changed: []` | N/A |
| Post-verify fails, rollback proven | before ≡ after | `changed: []`, `rolled_back: true`, `rollback_proven` as today | N/A |
| Rollback not proven | invariants differ | each `changed` entry adds `before` and `after` `MassProps` | N/A |
| Object on one side only | deleted, or created then kept after failure | missing side's `MassProps` is `null`; success entry of a deleted object has `volume/area/com` `null` | N/A |
| Setup or commit failure | no after record | `fingerprint_after: null`, `changed: []` | N/A |
| FLAGGED audit | 40 PASS, 2 REPOINTED, 1 RE_BASELINED | `counts {PASS:40, REPOINTED:2, RE_BASELINED:1}`, `findings` = the 3 non-PASS | N/A |
| Undo, cached digest | `expect_fingerprint` = a digest this process published | compared by digest, else `massprops_equal` against the cached record | N/A |
| Undo, unknown digest | digest evicted or from another process | byte comparison only; text says no record was held, no hint to pass a record | N/A |
| Undo, wire object | `{digest, serializer}` | treated as its digest after the serializer check | wrong serializer → `INVALID_INPUT` |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/contracts/mutation.py` -- `TnpAuditBlock` (`:47-53`) gains required `counts: dict[str, int]`; new `WireFingerprint {digest, serializer}`, `ChangedObject {name, volume, area, com, before?, after?}`; `MutationBlock` (`:67-82`) `schema: fcb.mutation/2`, fingerprints `WireFingerprint`, required `changed`; remove `transaction_id`, `verify_verdict`, `params_digest` (D2).
- `src/freecad_buddy/contracts/diff.py:76-89` -- `GeometryDiff.schema` `fcb.geometry-diff/2`; `op` comment `{tool}`.
- `src/freecad_buddy/contracts/fingerprint.py:61-112` -- add `massprops_changed(a, b) -> list[str]` (names whose invariants differ, either side missing, or `inertia` absent); `massprops_equal` returns `not massprops_changed(a, b)` (same semantics).
- `src/freecad_buddy/usecases/transaction.py` -- `_mutation_block` (`:370-391`) and `_bracket` keep building the full block; `run_mutation` (`:580-583`) projects it after `_audit_after`, which reads `verify_verdict`, `snapshot_path` and both records from the full block. `summarize_mutation` (`:469-482`) runs on the full block. `_unrun_tnp_audit` (`:213`); `post_verify` (`:299-308`) keeps deciding on the full audit.
- `src/freecad_buddy/usecases/preview.py` -- `_diff` (`:568-591`) schema `/2`, `op {"tool": tool}` (drop `args` param); `_unrun_audit` (`:239`) adds `counts: {}`; `_tnp_precheck` forwards the copy's already-projected audit; `summarize_preview` (`:399-411`) drops `preview_id`; remember `fp_before` in the cache.
- `src/freecad_buddy/usecases/documents.py` -- `document_undo` (`:547-648`): remember `before`/`after`; resolve a digest through the cache; `_check_expectation` (`:218`) accepts a `{digest, serializer}` dict; `summarize_document_undo` (`:153-176`) loses the hint at `:166-168`; `_matches_pre_op` docstring.
- `src/freecad_buddy/hosts/tool_catalog.py:1138-1145` -- `expect_fingerprint` description: digest (cache-resolved), wire object, or record.
- `src/freecad_buddy/adapters/mcp_server.py:86` -- `json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)`.
- `scripts/gen_schemas.py:60-110` -- field orders and `REQUIRED_FIELDS` for `MutationBlock` (+`changed`), `TnpAuditBlock` (+`counts`), `WireFingerprint`, `ChangedObject`. Orphan check globs `*.schema.json` non-recursively (`:501`), so `jsonschema/retained/` is not an orphan.
- `_bmad-output/.../design/mcp-tools-design.md` §1.4 JSON example shows `transaction_id` -- remove it (D2).
- Consumers that break: `tests/infc/test_mutation_protocol.py:124-125` (schema, `transaction_id`), `tests/infc/test_g2_driver.py:153` (`params_digest` key), `tests/infc/test_preview.py:148` (schema), `tests/infc/test_document_undo.py:424-534` (record form; keep), `tests/external/test_mutation_contract.py:66-93`, `tests/external/test_contracts.py:303,1346-1357`, `tests/external/test_mcp_surface.py:680`, `tests/external/test_rpc_listener.py:461` (fixtures). Compatible: `tool_catalog.py:1434-1438`, `benchmarks/g2/fault-injection/score_g2_infc.py:211-214`, `benchmarks/harness/g2_collect.py`, `benchmarks/g2/case_run.py:155,184`, `adapters/audit_log.py` (digests only).
- Transcripts: `C:/Users/thuan/.claude/projects/D--Work-3D-Printers-Ender-3V2---Klipper/{eacac40d-d1d3-4caa-a7fc-019bcfd5926b,ff604ce5-fdfa-4552-8835-a658b832360e,0320ba38-b810-444d-b672-90a9cb823009}.jsonl`; results are `user` records with `tool_result` content joined to `tool_use` id, tool names `mcp__freecad-buddy__*`; spilled results hold a stub naming a `tool-results/*.txt` file. The 529 set = all results of the first two, first 324 of `0320ba38`. Draft estimator: scratchpad `project_529.py`.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/contracts/mutation.py`, `diff.py`, `fingerprint.py` -- types and `massprops_changed` per Code Map -- AC1-AC3, AC7.
- [x] `src/freecad_buddy/usecases/result_projection.py` (new) -- `remember(record)` / `recall(digest)` over an `OrderedDict` bounded at 64 records; `wire_fingerprint(record | None)` (remembers); `wire_audit(full) -> {status, element_map_version, counts, findings: non-PASS}`; `changed_objects(before, after, failed)`; `project_mutation(full_block) -> MutationBlock` accepting the `/1`-shaped dict (full records, full audit) -- AC1-AC3, AC6.
- [x] `usecases/transaction.py`, `preview.py`, `documents.py`, `hosts/tool_catalog.py`, `adapters/mcp_server.py` -- per Code Map -- AC1-AC6.
- [x] `src/freecad_buddy/contracts/jsonschema/retained/` -- move today's `mutation.schema.json` and `geometry-diff.schema.json` there as `mutation-1.schema.json`, `geometry-diff-1.schema.json`, unchanged; then regenerate with `scripts/gen_schemas.py`; one sentence in `data-contracts-design.md` §2 naming the folder; drop `transaction_id` from the `mcp-tools-design.md` §1.4 example -- AC7, D2.
- [x] `tests/external/test_result_projection.py` (new) -- pure specs for every I/O matrix row except the undo rows, cache bound and eviction, projection of a recorded `/1` block -- AC1-AC3.
- [x] `tests/infc/test_mutation_protocol.py`, `test_preview.py`, `test_document_undo.py` -- schema ids; live `changed` on a pad; FLAGGED audit counts; preview `op` has no `args`, text has no `preview_id`; undo rows of the I/O matrix -- AC1-AC6.
- [x] external fixtures listed in Code Map -- move to `/2` shapes; retained-schema files exist with `/1` ids -- AC7.
- [x] `scripts/automation/replay_result_sizes.py` (new) -- args `<transcript.jsonl>[:<max results>]...`; reads spill files; projects each recorded mutation and diff through `result_projection` and `summarize_preview`, writes text through `mcp_server._to_call_result`; prints per-session before/after/largest, the over-10K list, and each excluded unparseable result (D1) -- AC8.
- [x] Re-score `run_mutation` (sources changed) with `score_g2_infc.py` and `score_g2_validators.py`; update `benchmarks/_registry/validators.yaml` -- AC9.

**Acceptance Criteria:**
- Given a successful mutation, when it returns, then `fingerprint_before/after` are `{digest, serializer}`, `changed` lists each object whose invariants differ, and the block has no `transaction_id`, `verify_verdict`, `params_digest` or null `snapshot_path`, while the audit log line still records them.
- Given a failed or rolled-back mutation, then each `changed` entry also carries `before`/`after` `MassProps`, and `rolled_back`/`rollback_proven` are as today.
- Given any `tnp_audit` or `tnp_precheck`, then it is `{status, element_map_version, counts, findings}` with every non-PASS finding and no PASS finding.
- Given a preview, then `diff.op` is `{tool}` and `text` does not contain `preview_id`.
- Given any result, then the MCP text content is compact JSON.
- Given `document_undo(expect_fingerprint=<digest>)` for a digest this process published, then `matches_pre_op` uses the cached record's mass properties, and the hint text is gone.
- Given the generator, then `gen_schemas.py --check` passes, emitted schemas carry `/2`, and the `/1` files exist under `retained/`.
- Given the replay script on the 529 set less the unparseable results it names (D1), then total size drops ≥ 85 % and no projected result is over 10K chars.
- Given the G2 fault suite, then every case fails or flags exactly as before.

## Implementation Notes

- D3: `tests/infc/test_g2_driver.py` `test_should_match_the_pre_op_state_on_geometry_when_undoing_a_padded_sketch` asserts `matches_pre_op` is True, the post-undo digest differs from the published pre-op digest (`mutation.fingerprint_before.digest`), and the undo's own `fingerprint_before != fingerprint_after`. DW-97 carries the note.
- `fcb.mutation/2` types `fingerprint_before` as `WireFingerprint | None`: a pre-bracket fingerprint failure emits `null`, which `/1` did not declare.
- `gen_schemas.py` takes each root's `$id` from its `schema` literal, so a major bump moves the `$id` with the type.
- AC8 (D1, D4): 527 parseable results, 6,788,571 -> 730,156 chars, drop 89.2 %, largest 4,070, none over 10K; 11,615 recorded entries got the `inertia` placeholder. Per session: eacac40d 71.3 %, ff604ce5 79.8 %, 0320ba38 92.4 %. Excluded: 0320ba38 #257 `query_screenshot` (113 chars), #302 `feature_set_parameters` (10,041 chars).
- AC9: `score_g2_infc.py` per-case verdicts equal the previous run; only the `run_mutation` `validator_sha` changed in `validators.yaml`.

## Spec Change Log

## Review Triage Log

- Pass 1: `run_mutation` and `audit_references` validator source sets omit `result_projection.py`, which now shapes `rollback_proven`, `rolled_back` and `findings` that `score_g2_infc.py:209-214,263-269` reads (verification-gap, blind) -- medium, patch: three copies (`score_g2_infc.py:88-93`, `score_g2_validators.py:45-50`, `runner.py:119-122`); a projection edit leaves the score marked current.
- Pass 1: `document_undo` remembers `before`/`after` before resolving the expectation, so a full cache evicts an expected LRU record (edge-case) -- low, patch: `documents.py:656-658`, reorder.
- Pass 1: `WireFingerprint` and `ChangedObject` are not in `CLOSED_TYPES` (`gen_schemas.py:153`), so a leaked `objects` key passes the schema (blind) -- low, patch.
- Pass 1: `contracts/mutation.py` docstring says full fingerprint records go to the audit log; `audit_log.py:121-138` stores digests only (edge-case claim) -- low, patch. D2's mention of `transaction_id` in the audit log is also wrong (never written); frozen, reported to the human.
- Pass 1: G2.3 check label "ops whose undo reached the pre-op hash" (`g2_collect.py:362`) is false for published digests after D3 (edge-case, blind) -- low, patch: relabel. `gate.yaml` text of the closed gate is not edited (D3).
- Pass 1: no test for a `{digest, serializer}` with this build's serializer and a missing or non-hex digest; deleting the check undoes first, then crashes or reports false (verification-gap; blind same) -- low, patch.
- Pass 1: preview never-ran audit `counts: {}` unchecked (verification-gap) -- low, patch.
- Pass 1: replay script raises on a transcript recorded after this change (`/2` block, `KeyError` on `objects`), on valid non-object JSON, and divides by zero with no results (edge-case, blind) -- low, patch: skip `/2` blocks, exclude non-object JSON, guard the division. Missing spill file and blank JSONL line rejected: unlikely, guards only.
- Pass 1: MCP text content is the whole envelope as JSON, while `mcp-tools-design.md` §1.3 says content carries the `text` summary (blind) -- medium, defer: pre-existing at `mcp_server.py:86`; this story only compacts it (AC5).
- Pass 1: UAT test cases `TC-05` (`:53,119,331,372,479,515,547`) and `TC-08:48` describe the `/1` shape (verification-gap other) -- medium, defer: Story 10.7 owns them (Never bullet); deferred entry lists the steps.
- Pass 1: byte-level undo gap of DW-97 remains for a digest the cache does not hold (restart, eviction) while DW-97 reads done (blind) -- low, defer.
- Pass 1: `changed` has no size cap; a base-feature edit in a large body lists every downstream object (blind) -- low, rejected: replay over 150 recorded mutations on the 144-object drawer peaks at 4,070 chars; about 90 changed objects are needed to pass 10K; a cap adds a field. Story 11.6 measures it live.
- Pass 1: `changed: []` when `fingerprint_after` is null on an unhashable commit (blind, edge-case) -- low, rejected: frozen matrix row "Setup or commit failure"; `fingerprint_after: null` and `SPEC_FAILED` say not measured.
- Pass 1: `changed` and cached-digest undo cannot see invariant-preserving changes (rotation of symmetric parts, solid-less sketches) (blind, edge-case) -- low, rejected: documented AD-6 limit (Story 11.1); the digest still differs on the wire; D3 accepted geometric undo.
- Pass 1: add `compared_by` to undo, `delta` to `changed` entries (blind) -- low, rejected: new public surface; the undo text names the byte-only case.
- Pass 1: cache not reset between infc tests (blind) -- false: the only test that needs a miss clears it (`test_document_undo.py`); every other test resolves a digest it published itself.
- Pass 1: no test for an unrestored undo through a cached digest, `_schema_id` fallback, preview `remember` (blind) -- low, rejected: the cached path calls the same `_matches_pre_op` the record-form tests cover (`test_document_undo.py:531-534`); no root lacks a `schema` literal; the G2 driver test covers preview `remember`.
- Pass 1: `changed` entries alias cached `MassProps` (edge-case) -- low, rejected: no caller mutates a result in-process.
- Pass 1: a dict with `digest` and `serializer` but no `objects` is now accepted (edge-case) -- false: intended wire-object input (I/O matrix row "Undo, wire object").
- Pass 1: `_schema_id` ignores `Optional[Literal]` (edge-case) -- false: no wire root declares one.

## Design Notes

One code path: the bracket still builds the full block (full records, full audit), the audit line and the summary text are written from it, and `project_mutation` turns it into the wire block in `run_mutation`. The replay script feeds recorded `/1` blocks to the same function, so its numbers measure the shipped projection. The preview's `tnp_precheck` is the copy's mutation audit, already projected, so it is forwarded, not projected twice.

Cache bound 64: one drawer record (184 objects) is about 75 KB, so 64 is about 5 MB; an undo targets one of the last few mutations. An evicted digest falls back to byte comparison, which is today's string behaviour.

## Verification

**Commands:**
- `"C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/run_tests.py` -- expected: all infc tests pass.
- `uv run pytest tests/external` -- expected: green.
- `uv run python scripts/gen_schemas.py --check` -- expected: no drift.
- `uv run python scripts/check_imports.py` -- expected: ring rules hold.
- `uv run ruff check .` -- expected: clean.
- `uv run python scripts/automation/replay_result_sizes.py <three transcripts, 0320ba38 with :324>` -- expected: drop ≥ 85 %, nothing over 10K.
