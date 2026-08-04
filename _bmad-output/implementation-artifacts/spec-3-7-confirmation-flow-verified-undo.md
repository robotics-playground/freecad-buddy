---
title: 'Story 3.7: Confirmation Flow & Verified Undo'
type: 'feature'
created: '2026-07-31'
status: 'done'
baseline_revision: 'd3d9c91'
final_revision: '6c445b7'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-clients.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** The confirm gate is schema-only theater. `_CONFIRM_SCHEMA = {"type": "object"}` (`hosts/tool_catalog.py:228`) is spliced into all 18 `sketch_*`/`feature_*` input schemas, threaded into each usecase's `params` dict, and read by nothing — a client reading the schema infers a gate that does not exist, and `sketch_remove_geometry` executes unconfirmed (DW-85). Story 3.6 mints `preview_id` as `fcb-preview:<random>` (`usecases/preview.py:505`) with no backing store and an `expires_at` nothing enforces, so there is nothing for a gate to validate against. Separately, `document_undo` does not exist anywhere — no usecase, no tool spec — so G2.3 (fingerprint-before == fingerprint-after-undo, 100 %) has no mechanism to measure.

**Approach:** Make `preview_id` a **self-authenticating** token: `preview_dry_run` signs the payload it already computed (`doc` handle, `tool`, a digest of `args`, `fingerprint_before`, an expiry) with a per-process secret, and the mutation gate re-derives that payload from the call it is actually being asked to run plus the live document's current fingerprint. A confirm therefore proves *this op, on this document, in the state that was previewed* — no server-side store, which is what 3.6's "nothing outlives the call" acceptance criterion forbids. The gate fires in the two family helpers `_feature_mutation`/`_sketch_mutation` before the AD-5 bracket opens, so a rejected call writes no snapshot and opens no transaction. Add `document_undo` as a lifecycle op (confirm-exempt per mcp-tools-design §1.4) that undoes, **recomputes** (`Document::undo` does not — `docs/references/FreeCAD/src/App/Document.cpp:174-225`), re-fingerprints, and reports the comparison as its result.

## Boundaries & Constraints

**Always:**
- Fail closed. Missing, malformed, expired, wrong-doc, wrong-op, wrong-state, or bad-signature confirm → `INVALID_INPUT`, no execution, no snapshot, no transaction. A gate that errors on its own logic rejects.
- `hmac.compare_digest` for every signature comparison (the `adapters/rpc_listener.py:276` idiom). Never `==`.
- `autoApprove` is an **operator-set posture, never a client-supplied parameter** (integration-mcp-clients.md:136). It rides `Capabilities` from `FREECAD_BUDDY_AUTO_APPROVE`, mirroring `allow_exec` (`usecases/capabilities.py:23`). A `confirm.autoApprove: true` from the wire is ignored, and the schema does not advertise it.
- Every accepted confirm and every auto-approval writes an `approval` audit record carrying the diff digest the approval covers. `contracts/audit.py:19` already admits `event: "approval"`; `AuditSink` gains the method it needs.
- `document_undo` recomputes after undoing, before reading or fingerprinting anything.
- `contracts/` stays stdlib-only and holds the shapes only; the codec and the gate logic live in `usecases/`. `usecases/` never imports `hosts`/`adapters`.
- Lifecycle ops (`document_save/close/recompute/undo`) stay confirm-exempt. `document_undo` is confirm-exempt.

**Block If:**
- The signing secret cannot be established for a host that must gate (i.e. a host where the secret would have to be shared across two processes and no existing channel carries it) — HALT rather than weakening the gate to a no-op.
- Enforcing the gate turns the existing in-FreeCAD `sketch_*`/`feature_*` test suites red in a way that cannot be fixed by the tests supplying a confirm (i.e. the gate is unreachable from a test without host wiring).

**Never:**
- No preview registry, no server-side preview store, no TTL sweeper — 3.6 pinned that the TempDoc and every trace of the call are gone before the envelope is built.
- Do not widen `HandlerFactory`. Do not touch the 18 per-tool `params` assemblies or the 18 usecase signatures.
- Do not promote a preview result to the live document; apply re-runs the op under AD-5 (AD-10).
- No MCP elicitation implementation. The SDK's elicitation API is unused repo-wide and reaching client capabilities needs `request_context` plumbing that is not this story. The gate implements the **token fallback** and the **headless fail-closed** rows of the confirmation matrix; the elicitation row is satisfied by the same token because an elicitation `accept` produces one.
- Do not add `document_object_delete` (also unregistered — separate scope).
- Do not quote or move any G2 pass rate, touch `benchmarks/g2/` scorers, or open `heldout/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Preview → apply | `preview_dry_run` returns `preview_id`; same op, same args, same doc, unchanged doc | Mutation executes under AD-5; `approval` audit record written with the diff digest | No error expected |
| No confirm | `feature_pad(...)` with `confirm` absent, no auto-approve posture | `INVALID_INPUT`; no snapshot file created; no transaction opened | Envelope `detail.code` names the missing confirm |
| Malformed confirm | `confirm={}`, or `elicitation_action` != `"accept"`, or `preview_id` not a string | `INVALID_INPUT`, no execution | Rejected before doc resolution where the shape allows |
| Forged token | `preview_id` with a valid-looking payload and a wrong/absent signature | `INVALID_INPUT`, no execution | `hmac.compare_digest` mismatch |
| Expired token | Token whose `exp` is in the past | `INVALID_INPUT` naming expiry | Clock read once per check |
| Wrong document | Token minted for doc A, replayed on doc B | `INVALID_INPUT` naming the doc mismatch | Compared against the resolved handle |
| Wrong operation | Token minted for `feature_pad`, replayed on `feature_pocket`, or same tool with different args | `INVALID_INPUT` naming the op mismatch | `args` digest compared, not `args` identity |
| Stale document state | Valid token, but the document changed since the preview (fingerprint differs) | `INVALID_INPUT` naming the state change; caller must re-preview | Digest compare; cross-serializer-tag compare must not be attempted |
| Replay after apply | Same valid token used a second time | `INVALID_INPUT` — the token already authorized a mutation | The gate records each spent token id until its own expiry |
| Headless auto-approve | `FREECAD_BUDDY_AUTO_APPROVE=1`, no `confirm` supplied | Mutation executes; `approval` record written recording that it was auto-approved and the params digest it covered | No error expected |
| Client-supplied autoApprove | `confirm={"autoApprove": true}` with no operator posture | `INVALID_INPUT` — the flag is not client-supplied | Treated as a missing confirm |
| Lifecycle op | `document_save`/`document_recompute`/`document_undo` with no confirm | Executes; confirm-exempt per §1.4 | No error expected |
| `document_undo` restores | Mutate a doc, then `document_undo` | `OK`; `fingerprint_before`/`fingerprint_after` reported, `matches_pre_op: true` when the post-undo digest equals the digest before the mutation | No error expected |
| `document_undo` with empty stack | Fresh document, nothing to undo | Typed rejection naming that there is nothing to undo — **not** a silent `OK` | `Document.undo()` is a no-op on an empty stack (`DocumentPyImp.cpp:657-665`); check `UndoCount` first |
| `document_undo` with undo off | Document reports `UndoMode == 0` (headless default) | Typed rejection naming undo unavailable, no state change claimed | `shim.enable_undo` reads the value back; `setUndoMode` ignores its argument (`DocumentPyImp.cpp:987`) |
| `document_undo` did not restore | Undo ran but the digest differs from the pre-op reading | `OK` envelope reporting `matches_pre_op: false` with both digests — reported, never claimed restored | Never escalate to snapshot restore here; undo is not the AD-5 bracket |

</intent-contract>

## Code Map

- `src/freecad_buddy/hosts/tool_catalog.py:227-228` -- `_CONFIRM_SCHEMA = {"type": "object"}` with the "not enforced" comment; spliced at `:295` (`_sketch_schema`) and `:455` (`_feature_schema`). Narrow to `{preview_id, elicitation_action}`, `additionalProperties: False`. **`autoApprove` must not appear** (integration-mcp-clients.md:136).
- `src/freecad_buddy/hosts/tool_catalog.py:45-47,50-60` -- `HandlerFactory` (4 positional args, `caps` third and currently discarded via `# noqa: ARG001` at `:308`/`:468`) and `ToolSpec` (`mutating`, `audit_event`). `caps` is the injection point for the auto-approve posture — no signature widening.
- `src/freecad_buddy/hosts/tool_catalog.py:308-309,468-469` -- `_sketch_method`/`_feature_method` `make`: `lambda **p: fn(doc_registry, **p)`. Where the posture is closed over.
- `src/freecad_buddy/hosts/tool_catalog.py:680-684,898-966` -- `_doc_method` and `tool_specs()`; the six registered `document_*` specs (`document_undo` is absent). New spec goes here.
- `src/freecad_buddy/hosts/tool_catalog.py:774-809,860-872` -- `READ_ONLY_PROFILE`; `document_undo` must stay out of it.
- `src/freecad_buddy/usecases/features.py:342-393` -- `_feature_mutation(registry, doc, feature, label, tool, params, op, audit_sink, precheck)`; `precheck(document)` at `:369-370` runs inside `with_document` with the resolved doc, **before** `run_mutation`. The gate's call site: the 10 `feature_*` tools funnel here (9 call sites; `feature_pad`/`feature_pocket` share `_extrude_tool`).
- `src/freecad_buddy/usecases/sketches.py:516-560` -- `_sketch_mutation`, same shape; the 8 `sketch_*` tools funnel here. Second call site.
- `src/freecad_buddy/usecases/features.py:488-501` -- one of the 18 `params` literals; `"confirm": confirm` at `:500`. `params` is already the carrier — the gate reads `params["confirm"]`, so no signature changes.
- `src/freecad_buddy/usecases/transaction.py:430-543` -- `run_mutation`; `:467-474` pre-transaction (digest, `enable_undo`, `fingerprint`, audit before, refs snapshot, `saveCopy`). The gate must fire before `:473` writes a snapshot — hence the `precheck` site, not here.
- `src/freecad_buddy/usecases/preview.py:504-510` -- where `preview_id` is minted and `expires_at` computed; `_PREVIEW_TTL_SECONDS = 900` at `:37`. `_diff` (`:534-565`) already carries `op{tool,args}`, `doc{handle}`, `fingerprint_before` — the exact payload to sign.
- `src/freecad_buddy/usecases/fingerprint.py:128` -- `fingerprint(doc) -> FingerprintRecord` (`digest` key). `contracts/fingerprint.py:35` `fingerprints_equal` **raises** `ValueError` across serializer tags or on a missing digest; `:68` `massprops_equal` raises nothing.
- `src/freecad_buddy/usecases/shim.py:253-266` -- `enable_undo(doc)`: writes `UndoMode = 1`, reads it back, returns what the doc actually reports. `document_undo` must consult it.
- `src/freecad_buddy/usecases/documents.py:92-102,109-141,152-293` -- `DocumentRegistry`: `_resolve` (`:109`, raises `ValidationError`), `with_document` (`:121`, **non-reentrant lock**), `rebind` (`:127`), and the five lifecycle usecases. `document_undo` lands here as a method (the `_doc_method` factory forwards by `getattr`). None of them fingerprint today.
- `src/freecad_buddy/usecases/capabilities.py:12-30` -- `Capabilities(allow_exec, service_mode)`, `from_env` reading `== "1"`, and `exec_registered`. The auto-approve posture mirrors this exactly.
- `src/freecad_buddy/contracts/audit.py:15-29` -- `AuditRecord`; `event` literal at `:19` already admits `"approval"`; `approval: dict | None` at `:28` is never populated.
- `src/freecad_buddy/adapters/audit_log.py:33-95` -- `AuditSink.before(event, tool, doc, params, fingerprint_before=None)` / `.after(..., verdict, fingerprint_before, fingerprint_after, rollback=None)`. Neither takes `approval=`; recording an approval needs a method or kwarg.
- `src/freecad_buddy/adapters/mcp_server.py:164-212,227-237` -- `_call_tool` and `_invalid_input_envelope(message)`; `:169-174` is the `debug_exec` fail-closed deny path to mirror in shape. `:199-200`/`:208-209` are where `audit.before`/`after` fire.
- `src/freecad_buddy/adapters/rpc_dispatch.py:108-128` -- `dispatch`; `ValidationError` → `INVALID_INPUT` at `:115-116`. Raising `ValidationError` from the gate is the idiomatic path to an `INVALID_INPUT` envelope.
- `src/freecad_buddy/adapters/rpc_listener.py:276` -- `hmac.compare_digest(str(token), self._token)`; the comparison idiom.
- `src/freecad_buddy/hosts/headless/entry.py:62-93` and `hosts/gui_addon/bootstrap.py:81-127` -- both call `Capabilities.from_env(dict(os.environ))` (`:71` / `:88`) then `build_inline_handlers`/`build_server`. Where the posture is read.
- `tests/infc/test_mutation_protocol.py:37,86-368` -- `_MutationFixture` and the commit/rollback/post-verify/undo-probe/audit classes; `UndoProbeTest:307` is the only undo test today. Undo coverage joins it or gets a sibling file.
- `tests/infc/test_document_lifecycle.py` -- behavioural coverage of `document_*`; `document_undo`'s tests belong beside it.
- `tests/external/test_mcp_surface.py:39-46,121-129` -- `EXPECTED_DOCUMENT_TOOLS` and the **exact-equality** surface assert; adding `document_undo` requires editing the set or the assert fails.
- `tests/external/test_assistant_readonly_profile.py` -- guards `READ_ONLY_PROFILE`; a new tool absent from the profile may need adding to an exclusion set (the `preview_dry_run` precedent, spec-3-6 Code Map).
- `_bmad-output/implementation-artifacts/deferred-work.md:835-842` -- DW-85, whose reassessment states the (a)/(b) choice this story must take explicitly and notes `expires_at` enforcement is 3.7's.
- `docs/references/FreeCAD/src/App/Document.cpp:174-225` -- `Document::undo`: **no recompute**, `:191-193` returns `false` on an empty stack. `:771-796` `getAvailableUndos` — **counts the open transaction**, so `UndoCount` inside a bracket overstates by one.
- `docs/references/FreeCAD/src/App/DocumentPyImp.cpp:657-665,987` -- `undo()` guarded by `getAvailableUndos()`, so an empty stack raises nothing; `setUndoMode` **ignores its argument**.
- `docs/references/FreeCAD/src/App/Document.pyi:38-53,373` -- `UndoMode`, `UndoCount`, `UndoNames`, `undo()`.

**As landed:**

- `src/freecad_buddy/contracts/confirm.py:14,19,27` -- **new**, stdlib-only. `Confirm` (the wire shape: `preview_id`, `elicitation_action`), `PreviewTokenPayload` (`doc`, `tool`, `args_digest`, `fingerprint_before`, `exp`), `ApprovalRecord` (`mode: preview_token|auto_approve|preview_copy`).
- `src/freecad_buddy/usecases/confirm.py` -- **new**, the story's core. `mint_preview_token` (`:74`) signs the payload with a per-process `secrets.token_bytes(32)`; `decode_preview_token` (`:80`) verifies via `hmac.compare_digest`; `verify_confirm` (`:134`) checks expiry then doc/tool/args/fingerprint, each with `compare_digest`; `gate_mutation` (`:209`) is what the family helpers call; `preview_exemption` (`:247`) is a context manager scoping the gate off for a preview's run on its own copy while capturing the digest the token is signed over. Every rejection raises `ValidationError` (→ `INVALID_INPUT` via `rpc_dispatch:115`). `_CONFIRM_FIELDS` (`:49`) makes an undeclared field a rejection, so a wire `autoApprove` is refused rather than dropped.
- `src/freecad_buddy/usecases/features.py:24,371-374` + `sketches.py:23,543-546` -- `confirm.gate_mutation` then `confirm.audit_approval` inside `call()`, before `precheck` and `run_mutation`. Two edit sites cover all 18 tools; no usecase signature and no `params` literal moved.
- `src/freecad_buddy/usecases/capabilities.py:16,28,38` -- `Capabilities.auto_approve`, read in `from_env` from `FREECAD_BUDDY_AUTO_APPROVE == "1"`, plus `auto_approve_enabled`.
- `src/freecad_buddy/hosts/tool_catalog.py:227-244` -- `_CONFIRM_SCHEMA` narrowed to the two fields, `additionalProperties: False`, `required: ["preview_id"]`, no `autoApprove`. `:1188` applies the posture from `caps` at `build_inline_handlers`.
- `src/freecad_buddy/usecases/preview.py:471-473,509-529` -- the op runs inside `preview_exemption`; `preview_id` is now `mint_preview_token` over the captured digest, and `expires_at` and the token's `exp` come from one deadline.
- `src/freecad_buddy/usecases/documents.py:283-340` -- `document_undo`: refuses on `UndoMode == 0` and on `UndoCount < 1`, fingerprints, `undo()`, **`recompute()`**, re-fingerprints; reports `fingerprint_before`/`after`, `matches_pre_op` (`None` without `expect_fingerprint`), `restored_objects`, `undo_count`. `:56` `summarize_document_undo`.
- `src/freecad_buddy/hosts/tool_catalog.py:961-980` -- the `document_undo` `ToolSpec` (`mutating=True`, 120 s, absent from `READ_ONLY_PROFILE`).
- `src/freecad_buddy/adapters/audit_log.py:85-94` -- `AuditSink.approval(tool, doc, approval)` writes `event: "approval"` and populates `AuditRecord.approval`. `adapters/mcp_server.py:157-161` and `adapters/rpc_listener.py:126-130` install the real sink, so the approval path runs in production and not only under test injection.
- `tests/infc/test_confirm_gate.py` -- **new**, 39 tests. `assert_refused_without_touching_the_document` (`:116`) counts `temp_snapshot_path` mints, compares the object set, and asserts `UndoCount == 0` — a rejection is proven to have done nothing, not merely to have raised.
- `tests/infc/test_document_undo.py` -- **new**, 17 tests. `tests/external/test_confirm_contract.py` -- **new**, 32 tests including AST ring checks. `test_mcp_surface.py:46` + `test_assistant_readonly_profile.py:63` add `document_undo`.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- DW-85 closed with a resolution naming choice (a), why (b) was rejected, and what enforces the expiry.

## Tasks & Acceptance

**Execution:**
- [ ] **Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)** -- Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md`; read `_bmad-output/project-context.md`; read `mcp-tools-design.md §1.4` + `§4` and `integration-mcp-clients.md §4`. Confirm every FreeCAD API name and semantic against `docs/references/FreeCAD/` **and** by live probe under `FreeCADCmd` before writing code — `Document.undo()` does not recompute, is a silent no-op on an empty stack, and `UndoCount` includes an open transaction.
- [x] `src/freecad_buddy/contracts/confirm.py` (new) -- Declare the wire shape of `confirm` (`preview_id: str`, `elicitation_action: Literal["accept"]`) and the signed-token payload TypedDict (`doc`, `tool`, `args_digest`, `fingerprint_before`, `exp`) -- the token's payload is a wire type in everything but transport, and `contracts/` is where a closed shape cannot drift from the code that reads it.
- [x] `src/freecad_buddy/usecases/confirm.py` (new) -- Implement the codec and the gate: `mint_preview_token(payload) -> str`, `verify_confirm(confirm, *, tool, args, doc_handle, document, posture) -> ApprovalRecord`, a per-process secret (`secrets.token_bytes`), `hmac.compare_digest` comparison, expiry check against `exp`, and the digest comparisons for doc/tool/args/fingerprint. Reject on every failure by raising `ValidationError`; return the record an accepted or auto-approved call must audit -- stdlib-only, so it is importable in-FreeCAD and from the external process alike.
- [x] `src/freecad_buddy/usecases/preview.py:504-510` -- Replace the random `preview_id` with `mint_preview_token` over the payload `_diff` already assembled (`op.tool`, an `args` digest, `doc.handle`, `fingerprint_before`) and derive `expires_at` from the same `exp` the token carries, so the advertised deadline and the enforced one are one value -- today's advertised expiry is enforced nowhere and the token binds to nothing (DW-85).
- [x] `src/freecad_buddy/usecases/capabilities.py:12-25` -- Add the auto-approve posture field, read it in `from_env` from `FREECAD_BUDDY_AUTO_APPROVE` with the exact-`"1"` idiom, and add the predicate next to `exec_registered` -- `autoApprove` is an operator flag, never client-supplied (integration-mcp-clients.md:136), and `allow_exec` is the established precedent for exactly this.
- [x] `src/freecad_buddy/usecases/features.py:342-393` + `src/freecad_buddy/usecases/sketches.py:516-560` -- Call the gate from both family helpers before `run_mutation`, using the already-resolved document and the `confirm` value already sitting in `params`, and thread the posture in from the handler -- these two helpers are the choke point all 18 geometry-mutation tools (8 `sketch_*` + 10 `feature_*`) pass through, and firing here means a rejected call writes no snapshot and opens no transaction.
- [x] `src/freecad_buddy/hosts/tool_catalog.py:227-228,308-309,468-469` -- Narrow `_CONFIRM_SCHEMA` to the two-field shape with `additionalProperties: False` and no `autoApprove`, and close the posture from `caps` into the sketch/feature `make` closures -- the schema currently advertises a gate that does not exist (DW-85's stated fix), and `caps` is already the third handler-factory argument.
- [x] `src/freecad_buddy/usecases/documents.py` -- Add `document_undo(doc=None)` as a `DocumentRegistry` method: refuse when undo is unavailable or the stack is empty, fingerprint before, `undo()`, **`recompute()`**, fingerprint after, and report both digests plus whether the post-undo digest matches -- `Document::undo` never recomputes (`Document.cpp:174-225`) so verifying before the recompute reads stale state, and an empty stack is a silent no-op that would otherwise be reported as a successful undo.
- [x] `src/freecad_buddy/hosts/tool_catalog.py:898-966` -- Register the `document_undo` `ToolSpec` via `_doc_method` (`mutating=True`, lifecycle, confirm-exempt), keep it out of `READ_ONLY_PROFILE`, and give it its input schema and description -- §1.4 lists it as a Phase 2 lifecycle tool and G2.3 cannot be measured through a tool that is not on the surface.
- [x] `src/freecad_buddy/contracts/audit.py` + `src/freecad_buddy/adapters/audit_log.py:33-95` -- Give `AuditSink` the means to write an `approval` record carrying the approval detail, and populate `AuditRecord.approval` -- the `"approval"` event and the `approval` field are declared and never written, and AD-10 requires every auto-approval to be audit-logged with the diff it accepted.
- [x] `src/freecad_buddy/hosts/headless/entry.py` + `src/freecad_buddy/hosts/gui_addon/bootstrap.py` (+ `adapters/mcp_server.py` / `adapters/rpc_listener.py` as the wiring requires) -- Ensure the approval record reaches a real sink on a production call and that the posture read at startup reaches the handlers -- an audit path that only runs when a test injects a sink is not an audit path (the finding Story 3.6 recorded against its own preview audit).
- [x] `src/freecad_buddy/contracts/jsonschema/` via `scripts/gen_schemas.py` -- Regenerate if any wire root or nested TypedDict changed, adding `REQUIRED_FIELDS` entries for anything new -- a `$def` with no required list validates `{}` (the DW-12 defect), and `--check` must stay byte-identical.
- [x] `tests/infc/test_confirm_gate.py` (new) -- stdlib `unittest` covering every confirm row of the I/O matrix on documents the test builds: accepted token, missing/malformed/forged/expired token, wrong doc, wrong op, wrong args, stale state, replay, auto-approve posture, client-supplied `autoApprove` ignored, lifecycle exemption, **and that a rejected call left no reserved-prefix snapshot file and no open transaction** -- fail-closed is only proven by a test that shows the rejected path did nothing.
- [x] `tests/infc/` (undo coverage, beside `test_mutation_protocol.py` / `test_document_lifecycle.py`) -- Cover mutate → undo → fingerprint-equal, the empty-stack refusal, the undo-unavailable refusal, and the did-not-restore report -- G2.3 is a 100 % claim and nothing but an executable in-FreeCAD test can support it.
- [x] `tests/external/test_mcp_surface.py:39-46` + `tests/external/test_assistant_readonly_profile.py` + a confirm contract test -- Add `document_undo` to the pinned surface, keep it out of the read-only profile, and assert the narrowed `_CONFIRM_SCHEMA` shape, that `autoApprove` is absent from every published schema, and the ring-import legality of the new modules by AST -- the surface assert is exact-equality and will otherwise fail; the schema/import claims are testable outside FreeCAD.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- Close DW-85 with a resolution naming the binding choice taken and what enforces the expiry, or state exactly what remains -- Stories 3.4–3.6 established the reassess-don't-skip precedent.
- [x] **Final Task: Quality Checks** -- Run `python scripts/check_imports.py`, `uv run python scripts/gen_schemas.py --check`, `uv run pytest tests/external`, `uv run python scripts/check_provenance.py`, `uv run ruff check`, and the in-FreeCAD suite via `FreeCADCmd tests/run_tests.py`.

**Acceptance Criteria:**
- Given the published tool schemas, when any `sketch_*` or `feature_*` input schema is read, then `confirm` declares exactly `preview_id` and `elicitation_action`, `additionalProperties` is false, and `autoApprove` appears in no published schema.
- Given a `preview_dry_run` result and an immediately following call to the same tool with the same args on the same unchanged document carrying that `preview_id`, when the mutation runs, then it executes under the full AD-5 bracket and the envelope carries the usual `mutation` block.
- Given the registered mutation tools, when each is called with no `confirm` and no operator auto-approve posture, then every one returns `INVALID_INPUT` and none of them created a document object, a snapshot file, or an open transaction.
- Given the operator auto-approve posture is set, when a mutation runs with no `confirm`, then it executes and an `approval` audit record records that the approval was automatic together with the digest it covered.
- Given a token that is valid in every respect except that the live document has changed since the preview, when the mutation is attempted, then it is rejected and the message names the state change rather than the token.
- Given `document_undo` on a document whose undo stack is empty or whose `UndoMode` reports undo unavailable, when it is called, then it returns a typed rejection and never reports a successful undo.
- Given a mutation committed through `run_mutation` followed by `document_undo`, when the undo returns, then the post-undo fingerprint is reported alongside the pre-mutation one and their equality is stated as a measured result, not assumed.
- Given `tools/list` with exec off, when the surface is read, then `document_undo` is present and absent from the read-only assistant profile.
- Given the whole change, when `python scripts/check_imports.py` runs, then the new confirm modules import nothing outward from their ring.

## Spec Change Log

**1. The preview could not reach its own operation under the fail-closed default.** The spec placed the gate in `_feature_mutation`/`_sketch_mutation`, but `preview_dry_run` calls the op use case on its TempDoc — so the preview, the only source of tokens, refused itself. Measured directly: `[this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns]`. Resolved with `preview_exemption` (`usecases/confirm.py:247`), a context manager scoped to exactly the one op call, entered and left inside the `try` before anything touches the live document, restoring the previous value in `__exit__` so a raising op cannot leak it. Known-bad state avoided: exempting by tool name, or requiring the operator posture for previews, either of which makes the fail-closed default unusable. Pinned by `test_the_exemption_does_not_outlive_the_preview_call` and `test_an_exemption_left_open_by_a_raising_op_is_still_released`.

**2. The token must be signed over the gate's normalized args, not the preview's raw args.** Signing `operation.args` made the apply fail with `issued for different arguments`. Measured cause: the preview's args are the caller's sparse input (`{body, profile, name, length}`) while the gate sees the tool's fully-defaulted `params` (`+ second_length: null, reversed: false, …`). `preview_exemption` therefore captures the digest the gate itself computed. Known-bad state avoided: stripping falsy keys, which silently equates an explicit `reversed: false` with an omission and breaks for any tool whose default is non-falsy.

**3. The posture and the approval sink are process-wide.** The spec forbade widening `HandlerFactory` and the 18 usecase signatures, and every host constructs the sink *after* `build_registry`. Both are set once at startup — the posture at `build_inline_handlers`, the sink at `build_server`/`RpcListener.__init__` — matching what `Capabilities` already is: one environment read per process.

**4. `matches_pre_op` is `None` without an `expect_fingerprint`.** `document_undo` never sees the pre-mutation state; its own `fingerprint_before` is post-mutation. An optional `expect_fingerprint` parameter lets G2.3 supply the pre-op digest. Known-bad state avoided: a two-state boolean, which would force the call to make a claim it cannot measure.

**5. FreeCAD undo semantics, corrected against this spec's own Code Map by live probe.** The Code Map cited `DocumentPyImp.cpp:987` for `setUndoMode` ignoring its argument; **the 1.1.1 build honours it** (`UndoMode` reads 0 initially and takes both writes). Two further measured behaviours the spec did not state: writing `UndoMode = 0` **discards the undo stack permanently** (turning it back on does not restore it), and `UndoCount` counts an open transaction only *after* that transaction records its first change, not at `openTransaction` — the transaction is allocated lazily. Both are pinned by tests. The spec's core undo rules (no recompute, silent no-op on an empty stack) were confirmed and hold.

**6. A preview whose op bypasses the gate emits `preview_id: None`.** Three pre-existing `test_preview.py` tests inject stub op tables that never reach the gate. Rather than fail those previews, the diff is still reported with no token — measuring a change and authorizing it are separate answers.

## Review Triage Log

### 2026-07-31 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 4: (high 1, medium 2, low 1)
- defer: 4: (medium 3, low 1)
- reject: 8: (medium 2, low 6)
- addressed_findings:
  - `[high]` `[patch]` `_EXEMPT` was a process-wide module global, so a `preview_dry_run` whose body overran its marshal timeout (`marshal.py:35-37` documents that an abandoned body keeps running, and `rpc_listener.py:335-336` only marks a document suspect `if mutating` — previews are `mutating=False`) left the gate disabled for every later call. Made the slot thread-local (`usecases/confirm.py:_EXEMPT_STATE`, `_active_exemption`), confining a leaked exemption to the thread that leaked it.
  - `[medium]` `[patch]` `document_undo` reported the wrong transaction name whenever the undo stack was deeper than one. `Document::getAvailableUndoNames` builds the list with `rbegin()` (`docs/references/FreeCAD/src/App/Document.cpp:318-330`), i.e. most-recent-first, but the code read `names[-1]`. Confirmed by live probe on FreeCAD 1.1.1: `UndoNames == ['t2','t1']`, `undo()` removed the `t2` object, and the code reported `t1`. Fixed to `names[0]` and pinned by a new depth-2 regression test, which was verified to fail against the old expression (`AssertionError: 'buddy: add cylinder' != 'buddy: resize box'`).
  - `[medium]` `[patch]` `test_a_refused_undo_leaves_the_document_untouched` swallowed the `ValidationError` without asserting one was raised, and used a document with an empty undo stack, so it passed via the empty-stack guard rather than the branch it named. Rewritten to commit a transaction first, assert the refusal is raised, and compare the object set as well as the digest.
  - `[low]` `[patch]` `test_confirm_gate.py:381` asserted `assertEqual(record["fingerprint_before"], record["fingerprint_before"])`, a tautology that can never fail, leaving the approval record's fingerprint binding untested. Replaced with a comparison against the live document's pre-mutation digest.

Rejected as factually wrong, disproved by live probe on the shipped FreeCAD 1.1.1 build: the claim that `document_undo`'s "undo unavailable" refusal is unreachable dead code because `DocumentPyImp.cpp:982-988` shows `getUndoMode` returning a hardcoded `1` and `setUndoMode` as a no-op. The vendored source does not match the shipped binary — probed directly, `UndoMode` reads `0` on a fresh document, accepts both writes, and writing `0` permanently discards the undo stack (`UndoCount` 1 → 0, and turning it back on does not restore it). The branch is reachable and the two dependent test findings fall with it; the one real consequence (a skip guard that could never fire) was removed so the test now asserts instead of skipping. Also rejected: the lifecycle-op exemption for `document_undo` and `debug_exec` bypassing the gate, both of which are the deliberate, spec'd design (mcp-tools-design §1.4; `debug_exec` is operator-only and excluded from every AI-facing registry), and four style-level findings about introspection coupling and a hardcoded tool count.

### 2026-07-31 — Review pass (follow-up)
- intent_gap: 0
- bad_spec: 0
- patch: 6: (high 1, medium 4, low 1)
- defer: 7: (medium 5, low 2)
- reject: 6: (medium 2, low 4)
- addressed_findings:
  - `[high]` `[patch]` Any second registry build silently flipped the process-wide auto-approve posture. `build_readonly_profile` (`tool_catalog.py:1294`) calls `build_inline_handlers`, which applied `confirm.set_auto_approve(auto_approve_enabled(caps))` unconditionally — so building the read-only assistant profile with unrelated capabilities re-armed or disarmed the gate for every mutation the main host served afterwards. Measured in a live interpreter: posture `False`, then `True` after a profile build carrying `auto_approve=True`. Added an `apply_posture` parameter defaulting to `True`, passed `False` from `build_readonly_profile`, and pinned it with `test_building_the_readonly_profile_does_not_touch_the_posture`.
  - `[medium]` `[patch]` `document_undo` would undo the wrong transaction when one was already open. `getAvailableUndoNames` **prepends** the active transaction (`docs/references/FreeCAD/src/App/Document.cpp:318-330`) and `getAvailableUndos` counts it (`:791-794`), while `Document::undo` commits it first and then reverts the transaction *beneath* it (`:188-195`) — so the call would revert one transaction and report a different one. Added a `HasPendingTransaction` refusal (attribute confirmed at `Document.pyi:62`, `DocumentPyImp.cpp:652`) and a regression test verified to fail against the unguarded code.
  - `[medium]` `[patch]` The approval audit line could not be joined to the mutation it authorized. `AuditSink.approval` digested the approval record itself into `params_digest` (`audit_log.py:92`), producing a value unrelated to the `before`/`after` lines of the same call, with no correlation id on either. `approval()` and `audit_approval()` now take the call's own `params`, so the approval line carries the same `params_digest` as its mutation; pinned by an assertion that the params reach the sink.
  - `[medium]` `[patch]` `restored_objects` omitted every shape-less object, contradicting the docstring that presents it as the way to tell an OCCT re-serialization apart from an object the undo failed to restore. `fingerprint()` skips objects with a null `Shape` (`fingerprint.py:138-141`), so a `Body`, `Origin`, datum, or empty `Sketch` never appeared. Now read from `document.Objects`.
  - `[medium]` `[patch]` `verify_confirm` compared a `None` live fingerprint against the literal string `"None"` via `str()` on both sides, so a payload carrying `"fingerprint_before": "None"` verified against an unread document. Not reachable through `gate_mutation` (which passes `None` only under the posture, which short-circuits first), but `verify_confirm` is a public, separately-tested entry point. Now an explicit rejection.
  - `[low]` `[patch]` The published `confirm` schema gave a client no signal that the field is mandatory. It cannot go in `required` — the specs are built before the capability record is read, and a host under the auto-approve posture legitimately accepts a call without one — so the requirement is stated in the schema's own `description`, which is what a client reads when planning a call.

Rejected: the claim that `confirm` must be added to each tool's `required` list (it would make the advertised contract wrong under the operator auto-approve posture, and input schemas are advertisement — nothing validates them server-side); the claim that the thread-local exemption needs handle scoping (`_resolve_operation` rejects a `doc` in args, so an op only ever reaches its own resolved document); two findings about `hmac.compare_digest` raising on non-ASCII and an `ensure_ascii` mismatch between the minting and digest paths (both fail closed through `rpc_dispatch:124`, and neither is reachable with `token_urlsafe` handles and ASCII tool names); and two style-level findings about `int()` vs `math.ceil()` on the token expiry and a test whose fixture cannot exercise the branch it names.

One reviewer finding was investigated, reproduced, and deliberately left unpatched: a preview whose operation fails on the copy still mints a valid apply token. Patching it turned `test_a_failing_op_still_returns_an_ok_envelope` (`tests/infc/test_preview.py:411`) red, and spec 3-6's I/O matrix pins the `OK` envelope for that row while saying nothing about the token. Whether a preview that proved an op breaks the solid should also authorize applying it is an undecided design question spanning both stories, so it went to the ledger rather than being settled here.

### 2026-07-31 — Review pass (follow-up 2)
- intent_gap: 0
- bad_spec: 0
- patch: 3: (high 1, medium 2)
- defer: 4: (medium 3, low 1)
- reject: 9: (medium 4, low 5)
- addressed_findings:
  - `[high]` `[patch]` The gate raised past its own boundary when it could not read the document it must compare against, turning a refusal into an unexpected internal error. `gate_mutation` called `fingerprint(document)["digest"]` unguarded; `fingerprint()` raises `SerializerUnavailable` (a `RuntimeError`, `usecases/fingerprint.py:26`) on a build exposing neither `exportBinary` nor `exportBrep`, and OCCT can raise from `_serialize` on a degenerate B-rep. Measured under FreeCAD 1.1.1 with the serializer stubbed to raise: the exception escaped as `SerializerUnavailable`, which `rpc_dispatch.py:127-128` maps to `RECOMPUTE_ERROR` with `unexpected=True` rather than the `INVALID_INPUT` every other gate failure produces — contradicting the intent contract's "A gate that errors on its own logic rejects". Now converted to a `ValidationError` naming the unreadable state, pinned by a regression test verified to fail against the unguarded code.
  - `[medium]` `[patch]` `document_undo` reported `OK` after its mandatory recompute without checking whether that recompute left objects in an error state, while `document_recompute` sweeps for exactly that and returns `RECOMPUTE_ERROR` (`documents.py:262-278`). An undo that left the document broken was reported as a successful undo whose digest merely happened not to match. Measured on FreeCAD 1.1.1 with a `Part::Fillet` carrying no `Base` present across the undo: status was `OK` with the object in `State: ['Invalid']`. The same sweep now decides the status, pinned by a regression test plus a clean-undo test proving the sweep does not turn an ordinary undo into a failure.
  - `[medium]` `[patch]` A non-string `expect_fingerprint` was reported as `matches_pre_op: false` — "the undo did not restore" — for what is a caller type error. Measured: `document_undo(doc=h, expect_fingerprint=12345)` returned `OK` with `matches_pre_op: False`, because a non-string can never equal a digest and nothing validates the input server-side (input schemas are advertisement, as this spec's previous pass established). Now an explicit `ValidationError` naming the parameter, leaving the document untouched.

Rejected as disproved by direct measurement or as design already settled: the claim that `document_undo` must itself carry a confirm (it is a spec'd confirm-exempt lifecycle op per mcp-tools-design §1.4, and was rejected on the same grounds in the previous pass); the claim that `UndoNames` can be empty while `UndoCount >= 1`, leaving `undone: None` on a destructive call (probed on 1.1.1 — an unnamed transaction reports `'<empty>'` and an empty-string name reports `'Command'`, so the list is never empty when the count is positive); the claim that tools can publish the confirm schema while routing around the gate (verified by source inspection of all 18 entries in `preview_op_table()` — every one reaches `_feature_mutation` or `_sketch_mutation`, `feature_fillet`/`feature_chamfer` via `_dressup_tool`); the claim that `_CONFIRM_FIELDS = frozenset(Confirm.__annotations__)` can evaluate empty and refuse every mutation (probed: it reads `['elicitation_action', 'preview_id']`, and a `TypedDict` populates `__annotations__` from its evaluated class body regardless of `from __future__ import annotations`); the claim that `HasPendingTransaction`'s `getattr` default of `False` silently skips a safety check (the attribute is present on both supported legs — `Document.pyi:62`, `DocumentPyImp.cpp:652` — and the project bans version-string branching in favour of capability probes); and four style-level findings about a NaN expiry, a clock moving backwards, `rpartition` versus `partition` on the token separator, and posture-setter ownership guards, none of which name a reachable input.

## Design Notes

**Why a signed token rather than a preview registry.** DW-85's reassessment left the choice explicit: (a) bind the token to a digest 3.7 recomputes, or (b) introduce a preview registry. (b) is rejected on two counts. It contradicts Story 3.6's landed acceptance criterion that nothing outlives the preview call (`TempDocCleanupTest`), and the GUI topology splits the MCP proxy (external process) from the RPC listener (in-FreeCAD), so a registry in one process is invisible to the other. (a) needs no shared state at all: the payload is signed on the way out and re-derived on the way in.

Payload shape, signed with a per-process secret:

```
{doc: "fcb-doc:…", tool: "feature_pad", args_digest: sha256(canonical(args)),
 fingerprint_before: "<digest>", exp: <epoch seconds>}
```

The gate re-derives every field from the call it is being asked to run — the resolved handle, the tool name, the caller's own `args`, and a fresh `fingerprint(document)["digest"]` — and compares. The re-derivation proves "the document is still in the state that preview measured", which a store lookup alone does not.

It does not, on its own, prove the token is unused — staleness and single use are separate properties. Measured on FreeCAD 1.1.1: one token for `feature_set_parameters` writing a property the value it already held was accepted six times, because `fingerprint()` digests shape bytes and quantized mass properties and an op touching neither leaves the digest equal. The payload therefore carries a `jti`, and the gate records each spent id until that token's own expiry — bounded by the expiry it stores, since an expired token is refused before the spent set is consulted. `jti` also makes two previews of the same operation on an unchanged document distinguishable; without it their payloads are equal and they sign to the same token. Note `fingerprints_equal` (`contracts/fingerprint.py:35`) **raises** across serializer tags; the gate compares digests it derived itself and must not hand it two records from different sources.

**Why the gate lives in `_feature_mutation`/`_sketch_mutation` and not in `run_mutation`.** `run_mutation` is the single choke point and already receives `params` and `tool`, but by the time it runs, `_feature_mutation` has resolved the document and is inside the registry lock — and `run_mutation:473-474` writes a `saveCopy` snapshot before any check of its own. Gating there means a rejected call has already touched the filesystem. The two family helpers already run a `precheck(document)` (`features.py:369-370`) in exactly the right place: resolved document, before the bracket. Two edit sites cover all 18 geometry-mutation tools, and neither the 18 usecase signatures nor the 18 `params` literals move.

**Why the posture rides `Capabilities`.** `integration-mcp-clients.md:136` is unambiguous: `autoApprove` is an operator-set flag, never a client parameter. A client-supplied `confirm.autoApprove: true` would be a self-approving mutation, which is the failure the gate exists to prevent. `Capabilities.allow_exec` is the exact precedent — read once from the environment at startup, threaded to the handler factories, never on the wire. `caps` is already the third `HandlerFactory` argument and is currently discarded.

**Why `document_undo` must recompute.** `Document::undo` (`docs/references/FreeCAD/src/App/Document.cpp:174-225`) replays property deltas, fires `onUndoRedoFinished`, emits signals, and returns — there is no `recompute()`, no `touch()`. `transaction.py:503` already carries this rule for the abort path. Fingerprinting before the recompute reads stale shapes and would report a false match. Two further traps: `Document.undo()` from Python is guarded by `getAvailableUndos()` (`DocumentPyImp.cpp:657-665`) so an empty stack raises nothing and returns `None` — indistinguishable from success without a prior `UndoCount` check; and `getAvailableUndos` counts an open transaction (`Document.cpp:792-795`), so the count is only meaningful outside a bracket.

## Verification

**Commands:**
- `python scripts/check_imports.py` -- expected: `OK`; the new confirm modules import nothing outward.
- `uv run python scripts/gen_schemas.py --check` -- expected: byte-identical, or regenerate and re-run to green.
- `uv run pytest tests/external` -- expected: all pass, including the updated surface and read-only profile asserts.
- `uv run ruff check` -- expected: no error in any changed file. The baseline already carries 10 `E501`s in `scripts/automation/` and `tests/external/test_check_imports.py`; they are pre-existing and out of scope.
- `uv run python scripts/check_provenance.py` -- expected: unchanged and passing.
- `FreeCADCmd tests/run_tests.py` -- expected: whole in-FreeCAD suite green, including the new confirm-gate and undo coverage and the pre-existing `sketch_*`/`feature_*` suites, which must supply a confirm or run under the auto-approve posture.

## Auto Run Result

Status: done

**Implemented change.** Follow-up review pass over the landed story 3.7 (confirm gate + verified undo). No intent gap and no spec defect: the three findings that survived verification were all code-level and fixed in place, each pinned by a regression test measured to fail against the unpatched source.

**Files changed:**
- `src/freecad_buddy/usecases/confirm.py` -- `gate_mutation` converts an unreadable document state into a `ValidationError` refusal instead of letting `SerializerUnavailable` escape as an unexpected `RECOMPUTE_ERROR`.
- `src/freecad_buddy/usecases/documents.py` -- `document_undo` rejects a non-string `expect_fingerprint`, and sweeps its mandatory recompute for object error states, returning `RECOMPUTE_ERROR` with an `errors` list when the undo left the document broken.
- `tests/infc/test_confirm_gate.py` -- one test that an unreadable document is refused rather than crashed.
- `tests/infc/test_document_undo.py` -- three tests: the non-string expectation refusal, the post-undo error sweep, and a clean undo reporting no errors.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- four new entries appended.

**Review findings breakdown:** 3 patches applied (1 high, 2 medium); 4 items deferred (3 medium, 1 low); 9 rejected (4 medium, 5 low), six of them disproved by direct probe or source inspection rather than dismissed.

**Verification performed:**
- `FreeCADCmd tests/run_tests.py` -- `Ran 484 tests ... OK (skipped=1)`.
- Falsifiability check: with only the two source files reverted, exactly the four new tests failed and nothing else did.
- `uv run pytest tests/external` -- `758 passed`.
- `python scripts/check_imports.py` -- `check_imports OK`.
- `uv run python scripts/gen_schemas.py --check` -- `gen_schemas --check OK`.
- `uv run python scripts/check_provenance.py` -- `check_provenance OK`.
- `uv run ruff check` -- `Found 10 errors`, all `E501` in `scripts/automation/` and `tests/external/test_check_imports.py`, matching the documented pre-existing baseline; none in any changed file.
- Live probes on FreeCAD 1.1.1 backing the rejections: `UndoNames` never empty while `UndoCount >= 1` (`'<empty>'` / `'Command'` substituted), `_CONFIRM_FIELDS` reads both declared fields, and all 18 `preview_op_table()` entries route through a gated family helper.

**Residual risks:**
- `document_undo` can now return `RECOMPUTE_ERROR` where it previously returned `OK`. This is the intended correction, but it is a status change on a registered tool: a client that treated any non-exception result as a successful undo now sees a non-`OK` status. No test or caller in the repo depended on the old behaviour.
- The gate's stale-state check remains blind to shape-less objects, and replay protection remains conditional on the mutation moving the digest. Both are deferred rather than patched: closing either changes the fingerprint contract or the signed payload, which is beyond a review patch.
- The undecided design question carried from the previous pass is unchanged: a preview whose operation fails on the copy still mints a valid apply token.


