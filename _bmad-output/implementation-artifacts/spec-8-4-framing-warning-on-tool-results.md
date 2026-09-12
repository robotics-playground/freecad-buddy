---
title: 'Story 8.4: Framing Warning on Tool Results'
type: 'feature'
created: '2026-09-12'
status: 'done'
baseline_revision: 'fb965b07720f91d970390c59fa571e9865706103'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-8-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-8-2-framing-read-exact-projection-test.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-8-3-view-fit-viewport-tool.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** The bridge can measure framing (story 8.2) and fix it (story 8.3), but an agent never learns it is needed. It would have to poll for a verdict it has no reason to ask for, so a pad that pushes the model off the human's screen returns a clean `OK` and the agent moves on.

**Approach:** Attach the verdict to the tool result the agent already reads — an optional top-level `framing` key on `ResultEnvelope`, plus a warning sentence rendered by one shared helper. Attachment happens at a single wrapper in the handler-build path, so no tool appends the sentence itself.

## Boundaries & Constraints

**Always:**
- The verdict rides a **new optional top-level `ResultEnvelope` key** named `framing`, never a key inside `structured_content`, and `result-envelope.schema.json` is regenerated in the same change. Additive under AD-28: `required` is unchanged.
- The warning sentence is rendered from the block by **one shared helper in `contracts/`**, called from the single attachment point. No `summarize_*` function in `usecases/` is edited, and no tool appends the sentence itself.
- On **any** non-`OK` terminal status the block is **omitted**. One rule, no either/or — a cached verdict on a `TIMEOUT` invites a reader to treat it as current, and rolled-back geometry must never be measured.
- Three no-verdict states discriminated by `checked`, never by absence alone: no viewport for this document → **omitted**; projection attempted and failed → `fits: null` + `checked: "unavailable"` + reason; success → a real bool with `"computed"`/`"cached"`.
- The verdict describes **the document the call targeted**, never whichever document is on screen.
- The read happens **outside** the AD-5 bracket, after `commitTransaction`, so a pad that grew the model past the edge warns on its own call. Attaching after the handler returns satisfies this by construction — every exit from `run_mutation` is already outside the bracket.
- The framing read is a GUI main-thread round trip, so it must run **inside** the marshal wrapper, on the same thread as the tool body. Running it outside would touch Qt off the main thread.
- Cache key is the four-tuple `(fingerprint, camera_string, viewport_size, active_view_id)`. A cached verdict whose key differs in any component is reported `checked: "cached"` with the differing component named in `stale_reason`.
- **When a key component cannot be read cheaply, the verdict is reported `checked: "cached"` with a stated `stale_reason` — never as fresh.** This is AD-32's own escape clause and it is what makes the geometry component affordable (see Design Notes).

**Never:**
- Do **not** call `usecases/fingerprint.py:fingerprint()` to build a cache key. It serializes every shape in the document and is the most expensive read in the codebase; per-call use would defeat the cost budget this cache exists to protect.
- Do **not** widen `HandlerFactory` or any `make_handler`. The attachment point has `doc_registry`, `viewport_port` and `params` already in lexical scope.
- Do **not** use a geometry-only staleness trigger. A window resize or splitter drag changes `getSize()` while `getCamera()` is untouched, so geometry-only staleness returns `fits: true, stale_reason: null` for a viewport that now clips the model.
- Do **not** edit the five duplicated `_ok_envelope` helpers, and do **not** regenerate `text` from `structured_content` — every real tool hand-writes `text`, so the sentence is appended to the finished string.
- Do **not** attach a verdict to `view_fit_viewport`'s own result in a way that reports the pre-fit state. Either measure after the fit or omit; a stale "does not fit" on the call that just fixed it is worse than silence.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Model fits, `OK` status | Live viewport, all corners inside | `framing` present, `fits: true`, `checked: "computed"`; `text` carries **no** warning sentence | No error expected |
| Model overflows, `OK` status | One corner outside | `framing` present, `fits: false`; `text` ends with the shared warning sentence naming `view_fit_viewport` | No error expected |
| Any non-`OK` status | `TIMEOUT`, `INVALID_INPUT`, `RECOMPUTE_ERROR`, … | **No** `framing` key at all, regardless of what the read would have returned | Block omitted |
| No viewport for this document | Headless host, or GUI document with no 3D view | **No** `framing` key (AD-32 state 1) | `read_framing` returns `None` |
| Projection failed | `getPointOnViewport` raised | `framing` present, `fits: null`, `checked: "unavailable"`, reason in `stale_reason` | Caught upstream |
| Repeat call, nothing changed | Same camera, size, view id and geometry proxy | `checked: "cached"`, verdict reused, no re-projection | No error expected |
| Window resized between calls | `getSize()` changed, `getCamera()` did not | Verdict **not** fresh: recomputed, or `checked: "cached"` with `"viewport_size"` named in `stale_reason` | No error expected |
| Splitter dragged / view switched | `active_view_id` changed | Same as above, differing component named | No error expected |
| Two-document session | Call targets `DocA` while viewport shows `DocB` | Verdict describes `DocA`; since `DocA` has no view, the block is omitted — never a warning about `DocB` | Not an error |
| Mutation that overflows the viewport | A pad grows the model past the edge | That **same** call's result carries `fits: false` — measured after commit | No error expected |

</intent-contract>

## Code Map

- `src/freecad_buddy/contracts/envelope.py:23-29` -- `ResultEnvelope(TypedDict, total=False)`; `images` at `:29` has no `# required` marker and is the existing precedent for an optional top-level key. Add `framing: FramingVerdict | None` the same way. The module has no `__all__`.
- `src/freecad_buddy/contracts/envelope.py:32-52` -- `summary_text` / `mirror_text`. The new shared sentence helper belongs here (or beside `FramingVerdict` in `contracts/render.py`); it must be the only place the sentence text exists.
- `src/freecad_buddy/contracts/render.py:79-111` -- `FramingVerdict`, already carrying all four fields and the three-state rule in its docstring.
- `src/freecad_buddy/hosts/tool_catalog.py:1308-1345` -- **the attachment point.** The `wrap` closure and the registration loop have `doc_registry`, `viewport_port` and `**params` (carrying `doc`) all in lexical scope. Apply a `with_framing(raw)` wrapper around `raw` *inside* `wrap(...)` so the framing read runs on the marshaled main thread.
- `src/freecad_buddy/hosts/tool_catalog.py:1279` -- `viewport_port` is already a parameter; story 8.3 threaded it into `HandlerFactory`, so it is available without further widening.
- `src/freecad_buddy/usecases/framing.py:133-138` -- `read_framing(registry, viewport_port, doc)`, returning `FramingVerdict | None`. `None` already means AD-32 state 1, so "attach only when not `None`" is the whole omission rule for that case. `_viewport_size(view)` at `:190` is reusable as one component of the cache key.
- `src/freecad_buddy/adapters/rpc_dispatch.py:108-114` -- `MethodRegistry.dispatch`, the one function every host's tool call returns through. Considered and **rejected** as the attachment point: it has no `doc_registry` or `viewport_port` in scope.
- `src/freecad_buddy/usecases/transaction.py:547-574` -- `run_mutation`'s commit and every exit path. All are already outside the AD-5 bracket, so attaching after the handler returns needs no transaction reasoning.
- `src/freecad_buddy/usecases/transaction.py:562` -- `fp_after = fingerprint(document)`, already computed on the mutation path and stored at `structured_content["mutation"]["fingerprint_after"]["digest"]` — free to read there, absent on the query path.
- `src/freecad_buddy/usecases/fingerprint.py:142` -- `fingerprint(doc)`: serializes every shape. **Do not call it for a cache key.**
- `src/freecad_buddy/contracts/status.py:11-19` -- `TerminalStatus`. There is no `is_ok()` helper; the shipped idiom is `envelope.get("status") == "OK"` (`transaction.py:122`, `mcp_server.py:85`).
- `src/freecad_buddy/contracts/jsonschema/result-envelope.schema.json:102-107` -- `required` is `["schema","status","structured_content","text"]` and stays unchanged. `scripts/gen_schemas.py:52` registers `("result-envelope", ResultEnvelope)`; `:69` holds its required list. `FramingVerdict`'s four fields are marked required in `render.py:108-111`, so add a `"FramingVerdict"` entry to `REQUIRED_FIELDS`.
- `src/freecad_buddy/usecases/screenshot.py:404-414` -- `summarize_screenshot`, an f-string summary. Representative of every real tool: `text` is hand-written, so the sentence is appended to the finished string, never regenerated.
- `tests/external/test_envelope_summary.py` -- 15 lines covering only `summary_text` with hand-made dicts. It never builds an envelope, which is why AD-32 requires a **new** contract test rather than trusting this one.
- `src/freecad_buddy/adapters/mcp_server.py:89` -- `_SuspectDocuments`, a plain class holding a `set`, documented as lock-free because the tool-call boundary processes one call at a time. Match this shape for the framing cache; there is no other keyed cache in the tree.

## Tasks & Acceptance

**Execution:**
- `src/freecad_buddy/contracts/envelope.py` -- add the optional top-level `framing` key to `ResultEnvelope`, and add the shared sentence renderer that turns a `FramingVerdict` into the warning text -- one source for the sentence, so no tool can diverge.
- `src/freecad_buddy/contracts/jsonschema/result-envelope.schema.json` -- regenerate via `scripts/gen_schemas.py`, adding `FramingVerdict` to `REQUIRED_FIELDS` -- the CI drift check fails otherwise.
- `src/freecad_buddy/usecases/framing.py` -- add the cache: a small keyed store on `(geometry_proxy, camera_string, viewport_size, active_view_id)` that returns `checked: "cached"` with the differing component named in `stale_reason`, and reports cached-with-reason rather than fresh whenever a component cannot be read -- AD-32's staleness rule, including its escape clause.
- `src/freecad_buddy/hosts/tool_catalog.py` -- add the `with_framing` wrapper applied inside `wrap` in the registration loop: on `status == "OK"` only, call `read_framing`, attach the block when it is not `None`, and append the shared sentence to `text` when `fits` is false -- the single attachment point AD-32 requires.
- `tests/external/test_framing_envelope.py` -- new pytest module covering every I/O matrix row through a built registry, including the non-`OK` omission rule for several statuses and the resize-vs-camera staleness case.
- `tests/external/test_framing_contract.py` -- new contract test: for every tool whose envelope carries a `framing` block with `fits: false`, the rendered `text` contains the shared sentence, and **no** tool's own summary function contains that sentence text -- without it the shared-helper rule is convention only.

**Acceptance Criteria:**
- Given a tool result with `fits: false`, when the envelope is read, then `framing` is a top-level key (absent from `structured_content`) and `text` ends with the shared sentence.
- Given any non-`OK` terminal status, when the envelope is built, then no `framing` key is present — proven across at least `TIMEOUT` and `INVALID_INPUT`.
- Given the window is resized between two otherwise identical calls, when the second verdict is reported, then it is not reported as fresh and `stale_reason` names the viewport size.
- Given a grep of the diff, when the sentence text is searched for, then it appears in exactly one place in `src/` — the `contracts/` helper.
- Given `scripts/gen_schemas.py --check`, when CI runs, then it passes, and `required` in `result-envelope.schema.json` is unchanged from its four entries.

## Spec Change Log

## Review Triage Log

## Design Notes

**The geometry component of the cache key, decided.** AD-32 names `fingerprint` as the first element of the four-tuple, but `fingerprint()` serializes every shape and is the costliest read in the tree — calling it per tool result would defeat the very budget the cache protects. AD-32 anticipates this and supplies the rule: *"If even that cheap read is refused, the verdict is reported `checked:"cached"` with `stale_reason:"camera/viewport not re-read"` unconditionally — never as fresh."* So: on the **mutation path**, read the digest already computed at `transaction.py:562` out of the envelope's mutation block — free and exact. On the **pure-query path**, no geometry digest is available cheaply, so a cached verdict is reported `checked: "cached"` with the geometry component named as unverified in `stale_reason`. The bridge never claims a freshness it cannot prove, which is the failure the rule exists to prevent. A pure query cannot change geometry anyway, so the only way a stale verdict survives is a mutation by another client — exactly the case `stale_reason` names.

**Why the wrapper and not dispatch.** `MethodRegistry.dispatch` is the one function every host returns through, which makes it the obvious seam, but it has neither `doc_registry` nor `viewport_port` in scope; reaching them would mean threading two new constructor arguments through `MethodRegistry` and every host. The registration loop in `build_inline_handlers` already holds all three components, and it sits above `run_mutation`, so the AD-5 bracket rule is satisfied without any transaction reasoning.

**Marshal ordering is load-bearing.** The framing read touches Qt. It must be wrapped *inside* the marshal call (`wrap(with_framing(raw))`), not outside it, so it executes on the FreeCAD main thread with the tool body. Inverting the two is the one wiring mistake that would appear to work in the external test leg and fail only in the live GUI.

## Verification

**Commands:**
- `uv run python scripts/gen_schemas.py --check` -- expected: `gen_schemas --check OK`. Load-bearing: fails if the `framing` key was added to the TypedDict without regenerating the schema.
- `uv run python scripts/check_imports.py` -- expected: `check_imports OK`.
- `uv run pytest tests/external/test_framing_envelope.py tests/external/test_framing_contract.py tests/external/test_framing.py -q` -- expected: all pass.
- `uv run pytest tests/external -q` -- expected: no regressions across the suite.
- `grep -rn "view_fit_viewport" src/freecad_buddy/usecases/ src/freecad_buddy/contracts/ --include=*.py` -- expected: the warning sentence naming the tool appears in exactly one module (`contracts/`), proving no tool appends it independently.
- `uv run ruff check .` -- expected: 9 pre-existing errors, none in a file this diff touches.
