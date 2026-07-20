---
stepsCompleted: ['init', 'evidence-gathering', 'analysis', 'recommendation']
inputDocuments: ['docs/intent.md', 'docs/references/FreeCAD (local source)']
workflowType: 'research'
lastStep: 4
research_type: 'technical'
research_topic: 'Preview/diff confirmation channel for AI CAD operations (GUI and headless clients)'
research_goals: 'Recommend a preview design that works for FreeCAD GUI panel, external MCP clients, and headless CI — unblocking Phase 2 UX design.'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** Technical (deep dive)
**Topic:** Preview/diff confirmation channel for AI CAD operations (GUI and headless clients)

---

## Research Overview

Phase 2 (Copilot) of FreeCAD Buddy commits to a human-in-the-loop rule: before executing any
mutation, the AI must show a **preview/diff** — the `docs/intent.md` Phase 2 spec says "shows a
preview/diff (before/after screenshot + parameter list), executes on confirmation, then runs
automatic post-verification." The problem: that description assumes a GUI. External MCP clients
(Claude Desktop, an agent SDK) and headless CI runs (`FreeCADCmd`) have **no FreeCAD 3D view** to
screenshot and **no panel** to render a before/after image into.

This research answers: *what does the preview/confirmation channel actually look like across three
delivery contexts* — the in-process FreeCAD GUI panel, an external MCP client, and a fully headless
CI/agent run — and recommends a single design that degrades gracefully across all three.

**Guiding constraints from `docs/intent.md`:**
- *"Human in the loop by default, autonomy by opt-in."* Early phases require confirmation for every mutation (Guiding Principles; Phase 2 exit criterion: "executes on confirmation").
- *"Verify, don't trust."* The preview is not just cosmetic — it is the human's leverage point, and it must be backed by real geometry queries, not echoed agent claims (Validation-First Discipline, principle 1: "the actor never grades itself"; Phase 4 threat: "HTTP 200 + well-formatted report for a bad part").
- *"Reuse before invention."* The Reuse Map already flags OCCT mass-property built-ins and existing community FreeCAD MCP servers as things to stand on.

### Methodology & Sources

Two evidence streams, in priority order:

1. **Web** — the MCP specification (2025-11-25 tool result content types, elicitation), and the
   real-world behavior of existing FreeCAD MCP servers and MCP image-content token handling.
2. **Local FreeCAD source** — `docs/references/FreeCAD`, for the concrete APIs that make a
   dry-run-on-a-copy, a structured geometry diff, and an offscreen render possible. All local
   claims are cited by absolute file path.

---

## Key Findings

### Finding 1 — The MCP protocol *already* has both halves of a preview channel: image content in tool results, and a formal confirmation primitive (elicitation)

**Image content in tool results is a first-class, standardized content type.** A `tools/call`
result carries a `content` array that may contain `image` items alongside `text`:

```json
{ "type": "image", "data": "<base64>", "mimeType": "image/png",
  "annotations": { "audience": ["user"], "priority": 0.9 } }
```

(Source: MCP spec 2025-11-25, *Tools* → Tool Result → Image Content.) So an offscreen before/after
render can be shipped to *any* MCP client as native image content — no GUI panel required on the
client side. The spec also defines `structuredContent` (a JSON object validated against the tool's
`outputSchema`) which is the ideal transport for a **structured parameter/geometry diff**. The spec
explicitly recommends returning structured content *and* a serialized text copy for backward
compatibility.

**Confirmation is also standardized, via *elicitation*.** Introduced in the 2025-06-18 revision
(form mode) and extended 2025-11-25 (URL mode), elicitation lets a server **pause tool execution
and request structured input from the user through the client**. The response carries an `action`
field of `accept` / `decline` / `cancel`, plus a `content` object present only on `accept`. This is
the exact "propose → wait for human → execute or abort" shape Phase 2 needs, and it is
client-portable. The spec's Tools page reinforces this at the SHOULD level: clients "**SHOULD**
prompt for user confirmation on sensitive operations" and "show tool inputs to the user before
calling the server."

*Implication:* the preview channel does **not** require inventing a bespoke protocol. It maps onto
MCP primitives that already exist: `structuredContent` (the diff), `image` content (the renders),
and `elicitation` (the confirm gate). This satisfies "reuse before invention."

*Caveat (Finding 5):* not every client renders `image` content natively or supports elicitation
yet — so the design must degrade to text/structured-only.

Sources: [MCP Tools spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools),
[MCP 2025-06-18 spec update (elicitation)](https://forgecode.dev/blog/mcp-spec-updates/),
[MCP elicitation human-in-the-loop (Glama)](https://glama.ai/blog/2025-09-03-elicitation-in-mcp-bridging-the-human-ai-gap),
[MCP Framework — Elicitation](https://www.mcp-framework.com/docs/tools/elicitation).

### Finding 2 — A true dry-run ("simulate on a copy, diff, apply on confirm") is achievable with FreeCAD's document-copy and transaction APIs, and it is the only preview approach that works identically headless and in-GUI

Two viable dry-run mechanisms exist in the local source:

- **Copy-document dry-run.** `Document::copyObject(...)` copies objects (recursively with
  dependencies) into another document; a document can be flagged `TempDoc` (status bit, value 9) so
  it is transient and never saved; `Document::saveCopy(path)` snapshots to disk without touching the
  live doc. (`docs/references/FreeCAD/src/App/Document.h`; Python surface in
  `docs/references/FreeCAD/src/App/Document.pyi`.) The mutation is executed on the copy, geometry is
  measured, a diff is computed, and only on confirm is it replayed on the real document.
- **Transaction rollback dry-run.** `openTransaction(name)` / `abortTransaction()` /
  `commitTransaction()` bracket a mutation so it can be executed, measured, then rolled back
  (`docs/references/FreeCAD/src/App/Document.h`; `AutoTransaction` RAII helper at
  `docs/references/FreeCAD/src/App/AutoTransaction.h`). This is the same mechanism Phase 2's
  "Undo restores the exact prior state" exit criterion already relies on.

**Trade-off:** the copy-document approach is *safer for preview* (the live document is never
mutated, so a preview can never leave a half-applied state or dirty the undo stack), at the cost of
copying the feature tree. The transaction approach is cheaper but mutates-then-rolls-back the live
document, which can perturb the `Touched` set, observers, and the GUI's undo history mid-preview.
**Recommendation leans copy-document for the preview render/measure, transaction for the final
apply** — see Recommendation.

Both mechanisms are pure-`App` layer (no `Gui` dependency), so they run **identically in
`FreeCADCmd` headless and inside the GUI.** This is the decisive property: the *diff computation* is
context-independent; only the *render* and the *confirmation UI* vary by context.

Sources (local): `docs/references/FreeCAD/src/App/Document.h`,
`docs/references/FreeCAD/src/App/Document.pyi`,
`docs/references/FreeCAD/src/App/AutoTransaction.h`,
`docs/references/FreeCAD/src/App/Transactions.h`.

### Finding 3 — A structured geometry diff is cheap, deterministic, headless-safe, and is the primary preview payload; the render is secondary

Every metric needed for a "what changes" diff is exposed on `Part.TopoShape` and via OCCT mass
properties, all Python-accessible and **all headless-capable** (they operate on the shape, not the
view):

| Diff dimension | API | File (local) |
|---|---|---|
| Volume delta | `TopoShape.Volume` | `src/Mod/Part/App/TopoShape.pyi` |
| Surface-area delta | `TopoShape.Area` | `src/Mod/Part/App/TopoShape.pyi` |
| Bounding-box delta (size + center shift) | `TopoShape.getBoundBox()` / `getBoundBoxOptimal()` → `Base::BoundBox3d` | `src/Mod/Part/App/TopoShape.h`, `src/Base/BoundBox.h` |
| Center-of-mass shift | `TopoShape.getCenterOfGravity()` | `src/Mod/Part/App/TopoShape.h` |
| Topology counts (faces/edges/vertices/solids ± ) | `TopoShape.Faces/Edges/Vertexes/Solids` | `src/Mod/Part/App/TopoShape.pyi` |
| Full mass properties (vol, area, COG, inertia) | `CalculateMassProperties(...)` → `MassPropertiesData` | `src/Mod/Measure/App/MassPropertiesResult.h` |
| Validity gate | `TopoShape.isValid()` / `check()` | `src/Mod/Part/App/TopoShape.h` |

The diff is computed as `metrics(after) − metrics(before)`, where `before` is the live shape and
`after` is the shape on the dry-run copy. This directly answers the intent's *"predicted volume/bbox
delta"* and — critically for the Validation-First discipline — it is produced by **deterministic
geometry queries the acting agent cannot fake**. It is the same OCCT built-in family the Reuse Map
already blesses ("Never invent — kernel-level checks are a solved problem").

FreeCAD additionally exposes change-tracking that scopes *which objects* a mutation touched, so the
diff can list new/changed/deleted feature-tree nodes, not just aggregate geometry:
`Document.getTouched()`, `signalChangedObject` / `signalNewObject` / `signalDeletedObject`, the
`DocumentObserver` family, and the recompute-failure log (`_RecomputeLog`) for surfacing errors the
mutation would introduce (`src/App/Document.h`, `src/App/DocumentObserver.h`,
`src/App/private/DocumentP.h`). This lets the preview also flag a **TNP risk** (a reference that
fails to re-resolve on the copy) *before* the user confirms — aligning with the Phase 2 TNP-guard
exit criterion.

*Why structured-diff-first matters:* it is the one preview payload that works in **all three**
contexts with zero rendering, zero GPU, zero display server. A headless CI run and a text-only MCP
client get a full, trustworthy preview from it alone.

### Finding 4 — Offscreen before/after renders work, but headless rendering is the hard part and needs an explicit strategy (truly-headless renderer vs. virtual framebuffer)

There are three render paths, in decreasing GUI-dependence:

1. **GUI view screenshot** — `View3DInventorViewer` / the Python `View3DInventor.saveImage(...)`
   (`src/Gui/View3DPy.cpp`, `src/Gui/View3DInventorViewer.cpp`). Requires a real 3D view; this is
   what existing FreeCAD MCP servers use, and it is why they return an error in headless mode (see
   Finding 6). Fine for the **in-GUI panel** context only.
2. **Truly-headless offscreen render (Qt FBO path)** — FreeCAD PR #6808 (merged 2022-06-21) exposed
   Qt-off-screen-rendering-plus-framebuffer-objects to Python, explicitly to produce "high-quality
   images of a scene **in true headless mode**," with anti-aliasing and transparent backgrounds.
   Locally, the offscreen renderer is `SoFCOffscreenRenderer` (`src/Gui/SoFCOffscreenRenderer.cpp/.h`,
   `writeToImageFile(...)`) and the viewer exposes `renderToImage(width, height, samples,
   includeViewerLighting) -> QImage` (`src/Gui/View3DViewerPy.cpp:156-158,740-771`). This is the
   preferred path for headless renders **but still needs an OpenGL/GPU context** and, in practice,
   a GUI-document/view-provider to build the scene graph — which `FreeCADCmd` does not create.
3. **Virtual framebuffer (Xvfb / `QT_QPA_PLATFORM`)** — the pragmatic CI answer. Run FreeCAD's
   **GUI** binary under `xvfb-run` (or set `QT_QPA_PLATFORM=offscreen`), set `DISPLAY`, and call the
   normal `saveImage()` path against an in-memory X server. This is the documented community recipe
   for FreeCAD screenshots in Docker/CI and needs no code changes to the render call.

**Net:** the render is a *nice-to-have that is genuinely harder headless*, whereas the structured
diff (Finding 3) is the *must-have that is trivially headless*. The design must not make the
confirmation gate depend on a render succeeding.

Sources: [FreeCAD PR #6808 — offscreen rendering](https://github.com/FreeCAD/FreeCAD/pull/6808),
[Headless FreeCAD docs](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Headless_FreeCAD.md),
[Std ViewScreenShot](https://wiki.freecadweb.org/index.php?title=Std_ViewScreenShot),
[Rendering without display / Xvfb (ScientificComputing)](https://scicomp.ethz.ch/wiki/Rendering_without_display),
[Xvfb in CI](https://latchkey.dev/learn/packages-in-ci/run-xvfb-virtual-display-in-ci);
local: `src/Gui/SoFCOffscreenRenderer.cpp`, `src/Gui/View3DViewerPy.cpp`, `src/Gui/View3DPy.cpp`.

### Finding 5 — Images in MCP tool results are a token/UX hazard; treat renders as attachments/resource links with a strict pixel budget, not as unconditional inline base64

A well-documented failure mode: some MCP clients count the base64 payload of an `image` content
block as *text* tokens, so a single 800×600 PNG can burn 15,000–25,000 tokens instead of the
~600–1,600 an image should cost — a 10–20× waste, and large screenshots have tripped 25k-token tool-
result limits and context overflows in real clients (Claude Code, Codex, Kiro issues). The image is
also *for the human*, not primarily for the model.

Design consequences:
- Annotate render content with `"audience": ["user"]` so clients know it is for human display, not
  model consumption.
- Prefer **`resource_link`** (a URI to the saved PNG) over inline base64 when the client can fetch
  resources, and offer inline image only on request or for small thumbnails.
- Enforce a **pixel/byte budget** (e.g. ≤ 1024 px longest edge, PNG) at the server, independent of
  client.
- Never block the confirmation on the render; the structured diff is the load-bearing payload.

Sources: [claude-code #31208 — ImageContent token waste](https://github.com/anthropics/claude-code/issues/31208),
[claude-code #9152 — image token limit](https://github.com/anthropics/claude-code/issues/9152),
[Kiro #6292 — base64 context overflow](https://github.com/kirodotdev/Kiro/issues/6292),
[codex #11845 — base64 overcount](https://github.com/openai/codex/issues/11845).

### Finding 6 — Existing FreeCAD MCP servers confirm the gap: they screenshot the *active GUI view* and error out headless; none ship a dry-run before/after diff channel

Survey of the field (per the Reuse Map's "study/adapt existing community FreeCAD MCP servers"):

- **neka-nat/freecad-mcp** exposes a `get_view` tool ("get a screenshot of the active view"); the
  demo runs in GUI mode and the agent uses the screenshot as a post-hoc visual verification loop.
- Multiple servers (contextform, spkane's 150+-tool robust server, sandraschi, theosib) expose
  screenshot/view tools; the consistent limitation reported is that **screenshot/view features
  require GUI mode and return an error headless.**
- The workflow they implement is **after-the-fact** ("screenshot after each operation so the agent
  can verify its own work") — *not* a **before-execution preview/diff with a confirmation gate**.

So the reuse verdict for Phase 2: **adopt** their transport/embedding patterns and the
`saveImage`-based GUI screenshot, but the **dry-run-on-copy + structured geometry diff +
elicitation-gated confirm** is the genuine delta FreeCAD Buddy must build — consistent with the
intent's stance that the verify-first tool taxonomy is a genuine invention.

Sources: [neka-nat/freecad-mcp](https://github.com/neka-nat/freecad-mcp),
[contextform/freecad-mcp](https://github.com/contextform/freecad-mcp),
[spkane/freecad-addon-robust-mcp-server](https://github.com/spkane/freecad-addon-robust-mcp-server),
[FreeCAD MCP guide 2026](https://mcp.directory/blog/freecad-mcp-complete-guide-2026).

---

## Analysis — Preview Across Three Contexts

The preview channel has **three separable payloads**, and each context consumes a different subset.
The insight that unblocks the UX design: **decouple the payloads from the delivery, and make the
structured diff the mandatory core.**

| Payload | How produced | GUI panel | External MCP client | Headless CI |
|---|---|---|---|---|
| **Structured diff** (params + Δvolume/Δbbox/Δcog, feature-tree add/change/delete, TNP/validity flags) | Dry-run on `copyObject` temp doc → OCCT metrics diff | Rich table in panel | `structuredContent` (+ text mirror) | JSON in log / job report |
| **Before/after render** (2 images) | `saveImage` (GUI) or offscreen/Xvfb (headless) | Inline in panel | `image` content or `resource_link`, `audience:["user"]`, budgeted | PNG artifacts saved to job dir; optional, best-effort |
| **Confirm gate** | — | Native panel buttons (Apply/Cancel) | MCP **elicitation** (`accept`/`decline`/`cancel`) or client tool-confirm | Policy: auto-approve under opt-in autonomy, or fail-closed |

**Why the structured diff is the spine:** it is the only payload that is (a) deterministic and
agent-un-fakeable — satisfying "the actor never grades itself"; (b) identical across all three
contexts with no GPU/display; (c) machine-checkable, so the same diff object doubles as the input to
Phase 2's automatic post-verification and as the audit-log record. The render is a human-comfort
overlay; the confirm gate is a delivery detail. Building the channel diff-first means headless CI
and text-only clients are first-class from day one, not degraded afterthoughts.

**Dry-run engine choice (copy vs. transaction).** Use **copy-document** for the *preview* (live doc
untouched → a preview can never corrupt state or pollute undo history, and a failed dry-run is
discarded by deleting the temp doc). Use the **transaction/undo** path for the *actual apply* after
confirm, because Phase 2 already requires exact undo. Two engines, one shared "measure + diff"
function run against whichever shape is current.

**Headless render decision.** Do not depend on truly-headless Coin/Qt offscreen rendering being
available on every runner. Make the render **capability-detected and optional**: try
`renderToImage`/`saveImage`; if no GL context, fall back to **Xvfb-wrapped GUI binary** in the CI
image; if that too is unavailable, **omit the render** and ship diff-only. The confirmation never
waits on pixels.

---

## Recommendation — `preview.dryRun` + elicitation-gated `feature.apply`

Design a single server-side preview primitive that all three contexts share, plus a context-aware
confirmation layer.

### 1. One preview tool, three-payload result

`query.preview` (a.k.a. `preview.dryRun`) — takes the proposed operation spec, and:

1. `copyObject` the affected subtree into a `TempDoc`.
2. Execute the operation on the copy; recompute; capture recompute log.
3. Compute the **structured diff** vs. the live shape (Volume/Area/BBox/COG deltas, face/edge/solid
   count deltas, validity, TNP re-resolve check, list of touched/new/deleted feature nodes).
4. If a render context is available, render before (live) and after (copy) to two budgeted PNGs.
5. Return an MCP result: `structuredContent` = the diff (validated by an `outputSchema`); `content`
   = a text summary + optional `image`/`resource_link` renders annotated `audience:["user"]`.
6. Discard the temp doc.

This one tool serves the GUI panel (which renders the struct into a table + shows the images), the
external client (which gets structured + image content natively), and CI (which logs the JSON and
saves PNG artifacts).

### 2. Confirmation, delivered per context

- **GUI panel:** render the diff + images in the FreeCAD dock; Apply/Cancel buttons.
- **External MCP client:** the mutation tool issues an **elicitation** request carrying the diff
  summary; proceeds only on `action: "accept"`. Fall back to the client's own tool-confirmation
  prompt if elicitation is unsupported (spec SHOULD).
- **Headless CI / agent-to-agent:** confirmation is a **policy**, matching the intent's "autonomy by
  opt-in." Default fail-closed (no human ⇒ no mutation) unless an explicit `autoApprove`/autonomy
  flag is set for that job; every auto-approval writes the diff to the audit log.

### 3. Apply path

On confirm, execute the *same* operation on the *live* document inside an
`openTransaction`/`commitTransaction` bracket (so the existing undo/rollback exit criteria hold),
then run Phase 2 post-verification — reusing the very diff/metrics code the preview used.

### 4. Rendering strategy (explicit, capability-gated)

- In-GUI: `View3DInventor.saveImage(...)`.
- Headless: attempt `renderToImage` (Qt FBO, PR #6808); if unavailable, run the GUI binary under
  **Xvfb** / `QT_QPA_PLATFORM=offscreen` in the CI/Docker image; else omit render (diff-only).
- Always budget images (≤ ~1024 px, PNG), annotate `audience:["user"]`, prefer `resource_link` over
  inline base64 to avoid the token blow-up (Finding 5).

### 5. What to reuse vs. build

- **Reuse:** OCCT mass-property/bbox/validity built-ins (diff metrics); FreeCAD `copyObject` +
  transactions (dry-run); `saveImage`/`renderToImage` + Xvfb (render); MCP `structuredContent`,
  `image` content, and `elicitation` (transport + confirm); existing FreeCAD MCP servers' screenshot
  plumbing as a starting point.
- **Build (the genuine delta):** the dry-run-on-copy + structured-geometry-diff engine and its
  `outputSchema`, the TNP re-resolve pre-check on the copy, and the capability-detected
  headless-render fallback ladder. None of the surveyed servers provide these.

### Open items to close during Phase 2 UX design

1. Confirm on the CI runner whether `renderToImage` (PR #6808) actually works with no
   GUI-document/view-provider, or whether Xvfb is mandatory — spike this early; it determines the
   Docker image.
2. Decide the diff's canonical `outputSchema` (fields + tolerances) — it is shared by preview,
   post-verification, and audit log, so lock it once.
3. Pick the temp-doc lifecycle (in-memory `TempDoc` vs. `saveCopy` to a scratch path) based on
   feature-tree copy cost measured on the benchmark models.

---

## Sources

**MCP specification & ecosystem**
- [MCP Tools spec (2025-11-25) — content types, image content, structuredContent](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [MCP 2025-06-18 spec update — structured output & elicitation](https://forgecode.dev/blog/mcp-spec-updates/)
- [Elicitation: human-in-the-loop for MCP (Glama)](https://glama.ai/blog/2025-09-03-elicitation-in-mcp-bridging-the-human-ai-gap)
- [MCP Framework — Elicitation](https://www.mcp-framework.com/docs/tools/elicitation)
- [claude-code #31208 — MCP ImageContent token waste](https://github.com/anthropics/claude-code/issues/31208)
- [claude-code #9152 — image token limit exceeded](https://github.com/anthropics/claude-code/issues/9152)
- [Kiro #6292 — base64 image context overflow](https://github.com/kirodotdev/Kiro/issues/6292)
- [codex #11845 — base64 token overcount](https://github.com/openai/codex/issues/11845)

**FreeCAD MCP servers (field survey)**
- [neka-nat/freecad-mcp](https://github.com/neka-nat/freecad-mcp)
- [contextform/freecad-mcp](https://github.com/contextform/freecad-mcp)
- [spkane/freecad-addon-robust-mcp-server](https://github.com/spkane/freecad-addon-robust-mcp-server)
- [FreeCAD MCP complete guide 2026](https://mcp.directory/blog/freecad-mcp-complete-guide-2026)

**FreeCAD rendering / headless**
- [FreeCAD PR #6808 — offscreen rendering to Python (true headless)](https://github.com/FreeCAD/FreeCAD/pull/6808)
- [Headless FreeCAD documentation](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Headless_FreeCAD.md)
- [Std ViewScreenShot / saveImage](https://wiki.freecadweb.org/index.php?title=Std_ViewScreenShot)
- [Rendering without a display (Xvfb)](https://scicomp.ethz.ch/wiki/Rendering_without_display)
- [Running Xvfb in CI](https://latchkey.dev/learn/packages-in-ci/run-xvfb-virtual-display-in-ci)

**Local FreeCAD source (cited inline above)**
- `docs/references/FreeCAD/src/App/Document.h`, `Document.pyi`, `AutoTransaction.h`, `Transactions.h`, `DocumentObserver.h`, `private/DocumentP.h`
- `docs/references/FreeCAD/src/Mod/Part/App/TopoShape.h`, `TopoShape.pyi`; `src/Base/BoundBox.h`; `src/Mod/Measure/App/MassPropertiesResult.h`
- `docs/references/FreeCAD/src/Gui/SoFCOffscreenRenderer.cpp/.h`, `View3DViewerPy.cpp` (`renderToImage`, lines 156-158/740-771), `View3DPy.cpp`, `View3DInventorViewer.cpp`
