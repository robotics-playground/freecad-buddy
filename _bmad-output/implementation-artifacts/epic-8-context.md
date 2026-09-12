# Epic 8 Context: Viewport Framing & Auto-Fit

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

The bridge has never been able to see the human's live FreeCAD viewport. The MCP render builds its own scene and self-frames, so a render is by construction never mis-framed — only the human's screen can be. An agent can therefore grow a solid past the edge of the user's viewport, read a perfectly framed render of its own, and never know the human is staring at the corner of a face. Epic 8 closes that hole: the bridge measures whether the targeted document's model is fully visible, reports the verdict in the tool result the agent already reads, and gives the agent one tool to fit the view itself. The bridge never fits on its own — the human owns the camera; the bridge warns and defers.

## Stories

- Story 8.1: `ViewportPort` contract and GUI-host implementation
- Story 8.2: Framing read — exact projection test
- Story 8.3: `view_fit_viewport` tool
- Story 8.4: Framing warning on tool results
- Story 8.5: Enforcement — framing contract test and CI alias gap

## Requirements & Constraints

- The bridge must answer "is the targeted document's model fully visible in the live viewport" without guessing. Where no viewport exists, the capability reports unavailable rather than fabricating a verdict.
- An agent must be able to fit the model into the live viewport on its own judgement, with no preview token and no round trip, and every such call must be audit-logged with the prior camera so the move is traceable and reversible.
- When the model does not fully fit, the tool result must carry a structured verdict plus a warning sentence that guides the agent to the fit tool. The verdict is computed on change, not on every call, and never claims a freshness the bridge cannot prove.
- The epic is additive and parallel-eligible after Epic 1: one new tool plus one optional envelope field. It weakens no existing decision and must not reopen the closed G0 or G2 gates.
- Cost budget: a per-call GUI round trip plus a main-thread marshal hop is not affordable against the ≤15 s tool budget. Caching exists for that reason.
- **Reviewer note:** the decisions behind this epic failed a safety gate on first draft, and three load-bearing claims were refuted. Read AD-29 through AD-33 in the architecture spine in full before implementing — the summaries below are orientation, not the contract.

## Technical Decisions

**Port placement (AD-29).** Live-camera read and write sit behind a *second* injected port, `ViewportPort`, declared in `contracts/render.py` beside `RenderPort` and implemented in `hosts/gui_addon/`. It is NOT an extension of `RenderPort`: the only `RenderPort` implementation lives in `adapters/`, so extending it would put live-camera code there and force a second Qt exemption. The exemption list must stay at exactly one entry and the offscreen render port must stay untouched. Hosts with no viewport inject `None`. Framing availability is its own predicate — the offscreen render port's availability answers "can this process render offscreen", which is orthogonal; a headless leg can render and still have no view.

**Framing test (AD-30).** Exact, never heuristic: project the 8 corners of the union bounding box of the visible shape-bearing objects through `View3DInventor.getPointOnViewport` and test containment against `getSize()`. `fits` is false iff any corner falls outside. Use `getPointOnViewport`, not its `getPointOnScreen` alias — the `Screen` name invites bogus DPI/window-origin offsets. Three source-verified hazards: the projection is unclamped (that is what makes the test possible — do not "fix" it); the return wraps sign on `short` overflow, so any coordinate whose magnitude exceeds 4× the corresponding viewport dimension is treated as *outside* and discarded; Y is inverted relative to Qt, which does not affect containment but must be stated for any reported pixel coordinate. No `devicePixelRatio` correction — `getSize()` and the projection share one pixel space.

**Shared visibility predicate.** The framing read reuses the render's existing "default renderable" predicate rather than re-deriving one. A second plausible filter is exactly how the render and the warning end up describing different scenes. Known limitation, to state and not gloss: that predicate tests an object's own visibility flag only, so a visible child in a hidden container counts as on-screen for both. Do not fix it in one place only.

**Fit tool (AD-31, AD-33).** `view_fit_viewport` is `mutating=True` with **no `confirm` property**, built with its own tool spec outside the geometry mutation wrappers, and absent from the read-only profile. The confirm gate is a call site inside those wrappers, not a schema or flag — so routing this tool through the mutation path to obtain an audit record would wrongly demand a `preview_id`. Declaring it non-mutating would silently drop it from the audit log, the opposite of the intent. Its audit record comes from the mutating branch of RPC dispatch. A new optional `camera_before` field on the audit record carries the verbatim camera string; the audit schema is regenerated in the same change. The camera is never folded into the params digest (irreversible) nor the geometry fingerprint. It takes an explicit `doc` handle, resolves the view through the GUI document for that handle's resolved `Name`, and refuses with `INVALID_INPUT` naming both documents when the handle is not the document the viewport shows — never silently redirecting, never activating the named document. Fits are refused on a quarantined document. In multi-client mode the actor field must name the issuing session; camera moves are last-writer-wins by design and the audit log is the only reconstruction path — do not add a fingerprint precondition to "fix" that.

**Framing block on results (AD-32).** A `FramingVerdict` TypedDict in `contracts/render.py` rides a new **optional top-level envelope key** `framing` — not a key inside `structured_content` — and the envelope schema is regenerated in the same change. Fields: `fits: bool | None` (`None` only when uncomputable, never a guess); `ratio: float | None` (larger of the two extent/viewport-extent quotients over the 2D axis-aligned hull of the 8 projected corners; `None` with `fits:false` whenever any coordinate was discarded); `checked` in `"computed" | "cached" | "unavailable"`; `stale_reason: str | None`.

- Cache key is a four-tuple: geometry fingerprint, camera string, viewport size, active view id. A geometry-only trigger returns a fresh-looking `fits:true` after a window resize or splitter drag, because the size changes while the camera node does not. A cached verdict whose key differs in any component is reported `checked:"cached"` with the differing component named. If those cheap GUI scalars cannot be re-read, report cached with a stated reason — never fresh.
- The warning sentence is rendered from the block by **one shared helper in `contracts/`**, called from the envelope assembly path, never appended by an individual tool's summary function. Today `text` is hand-written per tool and the existing envelope-summary test covers only the generic fallback, so a new contract test is required or this rule is convention only.
- Three no-verdict states, discriminated by `checked` and never by absence alone: no viewport for this document → block omitted; projection attempted and failed → `fits:null` + `checked:"unavailable"` + reason; success → a real bool.
- On any non-`OK` terminal status the block is **omitted** — one rule, no either/or. This subsumes the quarantine case.
- The verdict always describes the document the call targeted, never whichever document is on screen.
- The verdict describes state *after* the call's own effect, read **outside** the transaction bracket after commit — so a pad that overflows the viewport warns on that same call. Reading inside the bracket would measure uncommitted geometry, leak abandoned state on rollback paths, and lengthen the window in which the Qt loop is blocked.

**Enforcement (Story 8.5).** A pre-existing live defect must be closed in this epic: the import checker's FreeCAD module alias set does not include `FreeCADGui`, so a `FreeCADGui.ActiveDocument` access passes CI today while violating the implicit-target ban. Add the alias, prove the gap closed with a planted fixture, and correct the checker's own error message and docstring, which still advertise a second Qt-exempt adapter that no longer exists. The `fitAll` margin and the near-miss tolerance are deferred thresholds: calibrate against real parts and record the values, or the warning fires on every call and becomes noise.

## UX & Interaction Patterns

Framing is **advisory, never blocking**. The bridge warns; only the agent's explicit `view_fit_viewport` call moves the camera. Skill guidance limits that call to after the agent changed geometry the human must see — not as a reflex on every warning, so a deliberately-zoomed viewport can reasonably be left alone. Camera ownership does not loosen under auto-approve or unattended runs: auto-approve governs the confirm gate, not the camera, and an unattended run must not behave differently here.

## Cross-Story Dependencies

- Epic 8 depends on Epic 1 (the shipped bridge: envelope, audit log, tool catalog, import checker, render port). It is parallel-eligible thereafter and gates no other epic.
- Story 8.1 supplies the port and the verdict type that 8.2, 8.3, and 8.4 all build on.
- Story 8.2's projection result is what 8.3's fit and 8.4's envelope block both report.
- Story 8.4 depends on 8.3's tool existing, since the warning sentence points the agent at it.
- Story 8.5 enforces rules introduced by 8.1 (single Qt exemption), 8.3 (Gui `ActiveDocument` ban), and 8.4 (shared summary helper); it must land with them, not after.
- Two generated schemas must be regenerated inside this epic's changes or the CI drift check fails: the audit record (new camera field) and the result envelope (new framing key).
