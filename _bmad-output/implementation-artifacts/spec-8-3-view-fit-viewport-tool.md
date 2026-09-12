---
title: 'Story 8.3: view_fit_viewport Tool'
type: 'feature'
created: '2026-09-12'
status: 'done'
baseline_revision: 'c0ad907652a97c65ed6316d7af7dff25cc6fef89'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-8-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-8-2-framing-read-exact-projection-test.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** An agent can now measure that its work has grown past the edge of the human's viewport (story 8.2), but it has no way to fix it. Nothing in the tool surface moves the live camera, so the human is left staring at the corner of a face.

**Approach:** A `view_fit_viewport` tool that fits the targeted document's model into its own live viewport via the view's `fitAll`. It is confirm-exempt but audited, refuses a document it is not actually showing, and takes the same explicit `doc` handle every other tool takes.

## Boundaries & Constraints

**Always:**
- `mutating=True` with **no `confirm` property** in its input schema, built with its own literal `ToolSpec` outside the `_feature_schema`/`_sketch_*` builders. This is the exact shipped shape of `document_save`/`document_recompute`/`document_undo`.
- The tool is **absent from `READ_ONLY_PROFILE`**. That set is an opt-in allow-list, so absence is achieved by adding nothing — do not edit it.
- The audit record carries a new **optional** `AuditRecord.camera_before` holding the verbatim `getCamera()` string, and `audit-record.schema.json` is regenerated in the same change.
- `camera_before` is **never** folded into `params_digest` (it is not a tool parameter, and the digest is irreversible) nor into `fingerprint_before` (a geometry digest under AD-6). It rides its own field.
- The view is resolved as `FreeCADGui.getDocument(<resolved Name>).ActiveView` — through the existing `ViewportPort`, never `FreeCADGui.ActiveDocument`.
- When the `doc` handle is not the document the live viewport is showing, return `INVALID_INPUT` **naming both documents**. Never fit the active document instead; never activate the named one.
- A quarantined ("document-suspect") document refuses the fit. This is free: both hosts gate the refusal on `mutating`, which this tool is.
- Story 8.3 is the seam's first tool consumer, so it threads `viewport_port` from `build_inline_handlers` into `make_handler` and drops the `# noqa: ARG001` at `tool_catalog.py:1279`.

**Never:**
- Do **not** demand a `preview_id` and do **not** route through `run_mutation`. The confirm gate is the explicit `confirm.gate_mutation` call inside `usecases/features.py`/`sketches.py`; routing this tool through that path to obtain an audit record would wrongly trigger the gate.
- Do **not** declare it non-mutating to dodge the confirm question — that would silently drop it from the audit log, the opposite of the intent.
- Do **not** add the `framing` envelope key or the warning sentence — story 8.4.
- Do **not** change `is_audited`. `mutating=True` alone already audits it under the default `audit_event="mutation"`.
- Do **not** add a fingerprint precondition to make concurrent camera moves safe. Camera moves are last-writer-wins by design; the audit log is the reconstruction path.
- Do **not** move the camera on any host without a viewport. No port, or `available()` false, degrades honestly.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Successful fit | `doc` handle whose document has a live view | `OK`; the view is fitted; an audit record carries `camera_before` with the pre-fit camera string | No error expected |
| Handle names a different document than the viewport shows | Viewport shows `DocB`, call targets `DocA` | `INVALID_INPUT` whose message names **both** documents | `ValidationError` |
| Unknown or stale handle | `doc` not in the registry | `INVALID_INPUT` naming the handle | `ValidationError` from `_resolve` |
| Missing handle | `doc` omitted | `INVALID_INPUT` — the handle is required | `ValidationError` |
| No viewport port injected | Headless host, `viewport_port=None` | A non-`OK` terminal status with a stated reason; the camera is not touched | Degrades honestly |
| Port reports unavailable | GUI document with no open 3D view | Same as above, reason names the missing view | Degrades honestly |
| Quarantined document | A prior call timed out on this handle | Refused before dispatch with the document-suspect message | Host-level, gated on `mutating` |
| `getCamera()` unavailable | The view has no readable camera string | The fit still proceeds; `camera_before` is omitted rather than fabricated | Caught; field omitted |
| `fitAll` raises | The view rejects the fit | A non-`OK` terminal status naming the failure | Exception caught |

</intent-contract>

## Code Map

- `src/freecad_buddy/hosts/tool_catalog.py:777-790` -- `_doc_method`, the factory behind the three confirm-exempt mutating tools; `document_save`'s call site at `:1022` shows the shape (`mutating=True`, no `confirm` in `properties`, `additionalProperties: False`).
- `src/freecad_buddy/hosts/tool_catalog.py:519` -- `{"doc": _DOC_SCHEMA, **properties, "confirm": _CONFIRM_SCHEMA}`: the schema builder that *adds* `confirm`. The fit tool must not call it. The only wire difference between a gated and an exempt mutating tool is this key.
- `src/freecad_buddy/hosts/tool_catalog.py:55-63` -- `ToolSpec` fields: `name`, `make_handler`, `input_schema`, `description`, `timeout_s`, `mutating=False`, `audit_event="mutation"`.
- `src/freecad_buddy/hosts/tool_catalog.py:974` -- `DEBUG_EXEC_SPEC`, the closest model for a hand-written one-off `ToolSpec`; `_screenshot_spec` at `:856` is the closest model for a view-related spec with a custom handler closure.
- `src/freecad_buddy/hosts/tool_catalog.py:50` -- `HandlerFactory`, currently 4 parameters. **This story widens it** and every `make(...)` at `:352, :544, :780, :796, :812, :826, :840, :857, :939, :976`, plus the single call site at `:1332`. Story 8.2 deferred this deliberately (see its Spec Change Log); 8.3 is the first tool that needs the port in a handler.
- `src/freecad_buddy/hosts/tool_catalog.py:955` -- `READ_ONLY_PROFILE`, an opt-in `frozenset`; filter at `:1392`. `tests/external/test_assistant_readonly_profile.py:76` pins it exactly, so adding nothing keeps that test green.
- `src/freecad_buddy/contracts/audit.py:15-30` -- `AuditRecord(TypedDict, total=False)`. Add `camera_before: str | None` here.
- `src/freecad_buddy/adapters/audit_log.py:49-66` -- `AuditSink._record` builds the common fields; `_digest` at `:27` hashes **the tool params only**, so a field never placed in `params` cannot enter the digest. `before()` at `:68` already takes an optional `fingerprint_before` the dispatch sites do not pass — the same keyword shape works for the camera.
- `src/freecad_buddy/usecases/confirm.py:242` -- `approval_sink`: the shipped precedent for a **usecase** writing its own audit record rather than relying on the dispatch bracket. The fit usecase follows it, because dispatch has no camera knowledge and must not gain any.
- `src/freecad_buddy/adapters/rpc_listener.py:319-328` -- the live-GUI dispatch path: `if mutating and self._is_suspect(doc)` refusal, then the `audit.before`/`after` bracket. `adapters/mcp_server.py:199-216` is the proxy-path twin.
- `src/freecad_buddy/adapters/rpc_dispatch.py:50` -- `is_audited`: `mutating` alone qualifies. `:115` maps `ValidationError` to an `INVALID_INPUT` envelope; `:77` puts `str(exc)` in `detail.message`.
- `src/freecad_buddy/usecases/documents.py:151` -- `with_document(doc, fn)` resolves the handle under the registry lock and is the public entry every tool uses; `_resolve` at `:139` raises the `ValidationError`s for missing/unknown handles. The resolved name is `document.Name`.
- `src/freecad_buddy/usecases/framing.py:133-138` -- `read_framing(registry, viewport_port, doc)`: the established signature shape for a usecase taking the port as its second positional parameter.
- `src/freecad_buddy/hosts/gui_addon/viewport.py:12-56` -- `GuiViewportPort.available(document)` / `.view(document)`.
- `scripts/gen_schemas.py:51-67` -- `WIRE_ROOTS` already registers `("audit-record", AuditRecord)`, so the schema regenerates automatically; `REQUIRED_FIELDS` at `:72` lists `AuditRecord`'s required names — **do not add `camera_before` there**, it is optional.

## Tasks & Acceptance

**Execution:**
- `src/freecad_buddy/contracts/audit.py` -- add optional `camera_before: str | None` to `AuditRecord`, documented as the verbatim pre-fit camera string -- AD-31 requires a visible camera change leave an audit trace.
- `src/freecad_buddy/contracts/jsonschema/audit-record.schema.json` -- regenerate via `scripts/gen_schemas.py` in this same change -- the CI drift check fails otherwise.
- `src/freecad_buddy/adapters/audit_log.py` -- add a `camera_before` keyword to the sink method the fit uses, placed on the record directly and never into `params` -- keeps it out of `params_digest` by construction.
- `src/freecad_buddy/usecases/view_fit.py` -- new module: resolve the handle, ask the port for availability and the view, verify the view is showing **this** document and raise `ValidationError` naming both when not, read `getCamera()` best-effort, call `fitAll`, write the audit record, return an `OK` envelope.
- `src/freecad_buddy/hosts/tool_catalog.py` -- widen `HandlerFactory` and every `make(...)` signature with the viewport port, drop the `# noqa: ARG001`, and register a literal `view_fit_viewport` `ToolSpec` with `mutating=True` and a schema of `{"doc"}` only -- the confirm-exempt mutating shape.
- `tests/external/test_view_fit.py` -- new pytest module covering every I/O matrix row with fakes, including a `_FakeView` recording `fitAll` calls and a camera string, a wrong-document case asserting **both** names appear in the message, and an audit-sink fake asserting `camera_before` is present while `params_digest` is unchanged by it.
- `tests/external/test_mcp_surface.py` -- assert `view_fit_viewport` is registered, is `mutating`, has **no** `confirm` property, and is absent from `READ_ONLY_PROFILE` -- the AD-31 wire shape, enforced rather than assumed.

**Acceptance Criteria:**
- Given the registered tool spec, when inspected, then `mutating` is `True`, `input_schema.properties` has no `confirm` key, and the name is absent from `READ_ONLY_PROFILE`.
- Given a successful fit, when the audit record is read, then `camera_before` holds the pre-fit camera string and the record's `params_digest` equals the digest of the tool arguments alone.
- Given a `doc` handle that is not the document the viewport shows, when the tool is called, then the result is `INVALID_INPUT`, both document names appear in the message, and no fit occurred.
- Given the whole diff, when reviewed, then no `preview_id` is demanded, `run_mutation` is not called, `is_audited` is unchanged, and `usecases/view_fit.py` imports no `FreeCADGui`.
- Given `scripts/gen_schemas.py --check`, when CI runs, then it passes — proving the regenerated audit schema was committed with the contract change.

## Spec Change Log

## Review Triage Log

## Design Notes

**Why the usecase writes its own audit record.** AD-31 says the record comes from the mutating branch of RPC dispatch, but neither dispatch site has camera knowledge: `rpc_listener.py:328` and `mcp_server.py:209` pass only `(event, tool, doc, params)`. Teaching dispatch to read a camera would put Gui knowledge in an adapter and give every tool a camera field it does not have. `usecases/confirm.py:242` already establishes the alternative — a usecase writing its own record for something dispatch cannot see. The dispatch bracket still writes its own `before`/`after` lines, so the fit is audited twice: once generically, once with the camera.

**Why "is the viewport showing this document" is checkable.** `ViewportPort.view(document)` resolves through `getDocument(<Name>)`, so a view returned for handle A belongs to document A. The wrong-document case is therefore not "the port lied" but "the GUI has no view for A while showing B" — detected as `available()` false, or as a view whose own document name differs. Name both in the message so the agent can act.

## Verification

**Commands:**
- `uv run python scripts/gen_schemas.py --check` -- expected: `gen_schemas --check OK`. This is the load-bearing one: it fails if `camera_before` was added to the TypedDict without regenerating the schema.
- `uv run python scripts/check_imports.py` -- expected: `check_imports OK`. Proves `usecases/view_fit.py` stayed Gui-free and `QT_EXEMPT_ADAPTERS` still holds one entry.
- `uv run pytest tests/external/test_view_fit.py tests/external/test_mcp_surface.py tests/external/test_assistant_readonly_profile.py -q` -- expected: all pass; the read-only profile test proves the tool did not leak into the assistant surface.
- `uv run pytest tests/external -q` -- expected: no regressions.
- `uv run ruff check .` -- expected: 9 pre-existing errors, none in a file this diff touches.
