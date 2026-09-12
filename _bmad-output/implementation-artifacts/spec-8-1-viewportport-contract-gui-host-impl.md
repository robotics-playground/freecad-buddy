---
title: 'Story 8.1: ViewportPort Contract & GUI-Host Implementation'
type: 'feature'
created: '2026-09-12'
status: 'done'
baseline_revision: '07dce396f56db27a1496193bfc24e93312d387b5'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-8-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/ARCHITECTURE-SPINE.md'
warnings: [oversized]
deferred:
  - summary: >-
      build_readonly_profile does not accept or forward viewport_port, so the read-only
      assistant profile can never receive a live viewport port.
    evidence: |-
      hosts/tool_catalog.py:1368-1374 takes render_port but no viewport_port, and calls
      build_inline_handlers without one. Harmless today because no tool reads the port; it
      becomes a real gap the moment story 8.2/8.4 threads it to a consumer.
    location: >-
      src/freecad_buddy/hosts/tool_catalog.py:1368
    severity: medium
  - summary: >-
      scripts/check_imports.py FREECAD_MODULE_ALIASES omits FreeCADGui, so
      FreeCADGui.ActiveDocument passes CI while violating the AD-20 implicit-target ban.
    evidence: |-
      check_imports.py:41 reads frozenset({"FreeCAD", "App"}). This is a live pre-existing
      defect and is explicitly story 8.5 AC2's scope, not this story's. It matters here
      because hosts/gui_addon/viewport.py is the first code in the tree to call
      FreeCADGui.getDocument, and its correctness argument rests on not using ActiveDocument.
      The test fake's ActiveDocument property now raises, which guards this story's code only.
    location: >-
      scripts/check_imports.py:41
    severity: medium
  - summary: >-
      ruff check reports 9 pre-existing E501 errors, so the CI lint leg is red independently
      of this change.
    evidence: |-
      All 9 are in scripts/automation/run_mcp_e2e.py, run_mcp_edge_cases.py and
      tests/external/test_check_imports.py:312 — no line this diff touched. Confirmed the
      count is identical before and after this story's changes.
    location: >-
      scripts/automation/run_mcp_e2e.py:8
    severity: low
---

<intent-contract>

## Intent

**Problem:** The bridge cannot see the human's live FreeCAD viewport. `adapters/render_probe.py` builds its own Coin scene and self-frames via `viewAll`, so an MCP render is never mis-framed by construction — only the human's screen can be, and nothing in the tree can read it.

**Approach:** Declare the live-camera capability as a second injected port, `ViewportPort`, in `contracts/render.py` beside `RenderPort`, plus the `FramingVerdict` TypedDict that stories 8.2/8.4 fill. Implement it in a new `hosts/gui_addon/` module that reaches `FreeCADGui`, and inject it at the host wiring seam — the GUI addon injects a live port, headless injects `None`.

## Boundaries & Constraints

**Always:**
- `ViewportPort` is a **separate** `@runtime_checkable` Protocol in `contracts/render.py`, never an extension of `RenderPort`. Extending `RenderPort` puts live-camera code in `adapters/` (its only implementation lives there) and forces a second Qt exemption.
- `ViewportPort` has its **own** availability predicate, answered per document. `OffscreenRenderPort.available()` answers "can this process render offscreen" via `setupWithoutGUI()` — orthogonal to "a live viewport exists".
- `contracts/` stays stdlib-only. `usecases/` stays Gui-free. The implementation lives in `hosts/gui_addon/`, where `FreeCADGui` is already permitted (`check_imports.py:83-84` returns `True` for `ring == "hosts"` unconditionally).
- `FreeCADGui` is imported **function-locally inside a guarded `try`**, matching `bootstrap.py:50-56` / `:73-78`, so the module imports cleanly with no GUI.
- The view is resolved through `FreeCADGui.getDocument(<resolved Name>).ActiveView`, never `FreeCADGui.ActiveDocument` (AD-20 implicit-target ban).
- Unavailable is reported as a `(False, reason)` tuple with a non-empty reason — the shipped fail-honest shape, never an exception and never a fabricated verdict.

**Never:**
- Do **not** add framing code to `adapters/render_probe.py`. `QT_EXEMPT_ADAPTERS` (`check_imports.py:79`) must still hold exactly one entry after this change, and `OffscreenRenderPort` must be untouched.
- Do **not** implement the projection test, the ratio, the bbox corner math, or any `fits` computation — that is story 8.2. This story declares `FramingVerdict` and supplies the port shape and view handle only.
- Do **not** add the `framing` key to `ResultEnvelope` or regenerate `result-envelope.schema.json` — that is story 8.4.
- Do **not** add `view_fit_viewport`, the `camera_before` audit field, or any tool spec — that is story 8.3.
- Do **not** widen `HandlerFactory` / `ToolSpec.make_handler` to a 5th positional port. No usecase consumes the viewport port yet; threading it through ~40 unused closures now is speculative. The first consumer (8.2/8.4) threads it.
- Do **not** subclass the Protocol in the implementation — conformance in this tree is structural, proved by `isinstance` (`tests/external/test_render_probe.py:140-141`).
- Do **not** touch `usecases/capabilities.py` — that dataclass holds env-derived flags only and has no port.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Live GUI, document with an open 3D view | `available(doc)` with a resolved handle whose GUI document has an `ActiveView` | `(True, None)` | No error expected |
| Live GUI, document with no open 3D view | Same, `ActiveView` is `None` | `(False, <reason naming the missing view>)` | Caught, returned as reason |
| Headless `FreeCADCmd` that can render offscreen | `available(doc)`, no `FreeCADGui` GUI up | `(False, <reason>)` — must NOT report available | `ImportError`/`AttributeError` caught, returned as reason |
| No port injected (headless host) | `viewport_port is None` at the wiring seam | Capability is unavailable; nothing raises | `None` is a valid injected value |
| `view(doc)` on an unavailable document | Document has no GUI document or no `ActiveView` | Returns `None` | Never raises; never falls back to another document |
| GUI document exists for a *different* document name | `available(docA)` while the viewport shows docB | Answers for docA only, from `getDocument(docA.Name)` | Never reads `FreeCADGui.ActiveDocument` |

</intent-contract>

## Code Map

- `src/freecad_buddy/contracts/render.py` -- 102 lines, stdlib-only. Add `ViewportPort` after `RenderPort:79-92` and `FramingVerdict` before it. `RenderPort` is the exact shape to mirror: `@runtime_checkable` at `:79`, docstring-only method bodies (no `...`/`pass`), `available(self) -> tuple[bool, str | None]` at `:83`. `__all__` at `:95-101` is flat and alphabetical. Imports at `:12-13` are `from dataclasses import ...` / `from typing import Protocol, runtime_checkable` — `TypedDict` must be added there; this file has no TypedDict today.
- `src/freecad_buddy/contracts/capabilities.py:8-13` -- the TypedDict convention to copy for `FramingVerdict`: `class X(TypedDict, total=False):`, one field per line, trailing `# required` on each mandatory field.
- `src/freecad_buddy/contracts/__init__.py:55-61` (import block) and `:94-171` (`__all__`) -- both alphabetical; the two new names must be added to both or the re-export chain breaks.
- `src/freecad_buddy/adapters/render_probe.py:130` -- `OffscreenRenderPort`, the only `RenderPort` implementation. **Read-only for this story.** `:138-141` is its `available()` delegate; `:42-73` is the `@lru_cache(maxsize=1)` ladder whose `setupWithoutGUI()` rung (`:56`) is the offscreen-render predicate that must NOT be reused as the framing predicate.
- `src/freecad_buddy/hosts/gui_addon/` -- target package for the implementation. Current files: `__init__.py` (docstring only, no re-exports), `InitGui.py`, `bootstrap.py`, `pump.py`. New module goes here.
- `src/freecad_buddy/hosts/gui_addon/bootstrap.py:50-56`, `:73-78` -- the established guarded function-local import pattern: `import FreeCAD` inside the function, `except Exception:  # noqa: BLE001 - <stated fallback>`. `:91-94` documents that `start_bridge` already runs on the Qt main thread (AD-2's requirement for touching the view). `:100-102` is the wiring call that must pass the new port.
- `src/freecad_buddy/hosts/gui_addon/InitGui.py:22` -- the only existing `FreeCADGui` import in this package (`import FreeCADGui as Gui`, module-level inside `try`/`except Exception`).
- `src/freecad_buddy/hosts/tool_catalog.py:1271-1298` -- `build_inline_handlers`; `render_port: RenderPort | None = None` at `:1276` and the default-or-injected choice at `:1297` are the exact pattern for the new parameter. `HandlerFactory` at `:50-52` -- **read-only, do not widen.**
- `src/freecad_buddy/hosts/headless/entry.py:55` -- the headless wiring call; must pass `None` for the viewport port (explicitly, so the no-viewport case is stated, not defaulted by omission).
- `src/freecad_buddy/usecases/preview.py:543-553` -- the shipped `port is None` handling shape: `if render_port is None: return {"available": False, "reason": "no render port"}`. Precedent for `None` as a valid injected value.
- `scripts/check_imports.py:79` -- `QT_EXEMPT_ADAPTERS = frozenset({"adapters/render_probe.py"})`; `:82-89` `_qt_allowed` returns `True` for `ring == "hosts"` with no entry needed. **Assert unchanged; do not edit.** (The `:11` docstring's stale `adapters/marshal.py` claim is story 8.5's AC4, not this story's.)
- `tests/external/test_render_probe.py:140-141` -- the conformance-test template: `assert isinstance(render_probe.OffscreenRenderPort(), RenderPort)`. `:71-94` `_FakeRenderPort` is the structural-fake style. pytest, plain `assert`, module-level `def test_*`.
- `tests/infc/test_screenshot.py:31-32`, `:59-61` -- the in-FreeCAD capability-guard style (`self.skipTest` when the capability is present/absent), if an infc leg is added.

## Tasks & Acceptance

**Execution:**
- `src/freecad_buddy/contracts/render.py` -- add `TypedDict` to the typing import; declare `FramingVerdict(TypedDict, total=False)` with `fits: bool | None`, `ratio: float | None`, `checked: Literal["computed", "cached", "unavailable"]`, `stale_reason: str | None` (mark required fields with the trailing `# required` comment per the capabilities.py convention); declare `@runtime_checkable class ViewportPort(Protocol)` after `RenderPort` with `available(self, document: object) -> tuple[bool, str | None]` and `view(self, document: object) -> object | None`, docstring-only bodies; extend `__all__` alphabetically -- the AD-29 port contract and the AD-32 verdict type, in the innermost ring so usecases never see Gui.
- `src/freecad_buddy/contracts/__init__.py` -- add `FramingVerdict` and `ViewportPort` to the `render` import block and to `__all__`, both alphabetically -- the re-export chain every consumer imports through.
- `src/freecad_buddy/hosts/gui_addon/viewport.py` -- new module: a plain (non-subclassing) `GuiViewportPort` implementing both methods. `available` resolves the GUI document for the passed handle's `Name` and answers `(True, None)` only when an `ActiveView` exists, else `(False, <reason>)`; `view` returns that `ActiveView` or `None`. `FreeCADGui` imported function-locally inside `try`/`except Exception:  # noqa: BLE001` -- AD-29 places the live camera in a GUI host so the single adapters Qt exemption is not widened.
- `src/freecad_buddy/hosts/tool_catalog.py` -- add a `viewport_port: ViewportPort | None = None` keyword parameter to `build_inline_handlers`, stored for the first consumer; do NOT widen `HandlerFactory` or any `make_handler` -- the injection seam AC2 requires, without ~40 unused closure signature changes.
- `src/freecad_buddy/hosts/gui_addon/bootstrap.py` -- pass `GuiViewportPort()` at the `build_inline_handlers` call (`:100-102`), with the guarded-import module-load style of the surrounding code -- the GUI host is the one host with a live viewport.
- `src/freecad_buddy/hosts/headless/entry.py` -- pass `viewport_port=None` explicitly at its `build_inline_handlers` call -- states the no-viewport case rather than letting it default silently.
- `tests/external/test_viewport_port.py` -- new pytest module covering the I/O matrix: structural conformance via `isinstance(GuiViewportPort(), ViewportPort)`; no-FreeCADGui returns `(False, <non-empty reason>)`; a document whose GUI document has `ActiveView = None` returns `(False, reason)` and `view(...) -> None`; `available` for document A never consults the GUI document of B. Use monkeypatched fake `FreeCADGui` modules in the `_FakeRenderPort` structural style -- the external leg runs with no FreeCAD, so every GUI object is a fake.
- `tests/external/test_check_imports.py` -- add an assertion that `QT_EXEMPT_ADAPTERS` equals `frozenset({"adapters/render_probe.py"})` -- AC3 is a regression guard; without a test it is convention only.

**Acceptance Criteria:**
- Given `contracts/render.py`, when inspected, then `ViewportPort` is a `@runtime_checkable` Protocol declared beside (not inheriting from) `RenderPort`, with its own `available` answer, and `FramingVerdict` is declared for the AD-32 block.
- Given the GUI addon, when the bridge starts, then a `hosts/gui_addon/` `ViewportPort` implementation is injected at the wiring seam, while the headless host injects `None`.
- Given `scripts/check_imports.py`, when CI runs, then `QT_EXEMPT_ADAPTERS` still holds exactly one entry (`adapters/render_probe.py`), `adapters/render_probe.py` is byte-identical to its pre-change state, and the tree passes the ring check with the new `hosts/gui_addon/viewport.py` present.
- Given a headless leg whose offscreen render probe reports available, when framing availability is asked, then it answers unavailable — the two predicates are independent.
- Given the whole diff, when reviewed, then no `usecases/` file imports `FreeCADGui`, no projection/ratio/`fits` computation exists, no `ResultEnvelope` key was added, and no tool spec was registered.

## Spec Change Log

## Review Triage Log

### 2026-09-12 — Review pass
- verdicts: 34 findings — high 1, medium 6, low 8, false 14, maybe-false 5
- findings:
  - `[medium]` `[patch]` FramingVerdict docstring contradicts AD-32 on `ratio` (omits the discarded-corner rule) — ARCHITECTURE-SPINE.md:305 pins `ratio: None` while `fits: false` when any coordinate is discarded; story 8.2 implements ratio from this docstring. Fixed: discard clause plus the `|coordinate| > 4 ×` constant added.
  - `[medium]` `[patch]` FramingVerdict docstring omits AD-32's "block omitted" state — only 2 of 3 no-verdict states were documented; AD-32:319 names this exact divergence. Fixed: all three states now spelled out, with state 1 vs state 2 called out.
  - `[medium]` `[patch]` `checked` closed `Literal` vs AD-32's open `str`, with no note that a 4th value is an AD-28 major bump — kept the stronger Literal, added the major-bump note.
  - `[low]` `[patch]` `available()` could not distinguish "no GUI" from "document not found"; a handle without `.Name` leaked a raw AttributeError string as a capability reason — verified at runtime. Fixed: ImportError, missing-document, missing-Name and no-view each return a distinct stated reason.
  - `[low]` `[patch]` Tests asserted only `assert reason` (truthiness), never content — a refactor collapsing all reasons to one string would have passed green. Fixed: reason content asserted, plus a test that the three reasons are pairwise distinct.
  - `[medium]` `[patch]` `isinstance` conformance test proves nothing about arity — verified a class whose `available(self)`/`view(self)` take no document still passes `isinstance(..., ViewportPort)`; the per-document answer is this story's point. Fixed: added an `inspect.signature` arity test.
  - `[low]` `[patch]` The ActiveDocument guard had no teeth — the fake set `ActiveDocument` with a `# never read` comment but never asserted it went unread. Fixed: the fake's `ActiveDocument` is now a property that raises, plus a test proving the guard fires.
  - `[medium]` `[patch]` `viewport_port` was positional-or-keyword after `apply_posture`, so a 7th positional silently bound a port into `apply_posture` — fixed with a bare `*`; confirmed `kind: KEYWORD_ONLY`.
  - `[low]` `[patch]` `test_view_returns_the_passed_documents_view` bound `view_b` as a distractor but asserted only `is view_a`, passing even if both documents shared one view — fixed with `is not view_b` and a `requested_names` check.
  - `[high]` `[patch]` GUI injection of `viewport_port=GuiViewportPort()` at bootstrap.py:107 had NO executing test — **proven by experiment**: replacing it with `None` left all 917 external tests and check_imports green. This was the only change in the diff reaching a running process. Fixed: new seam test with stubbed PySide/listener; re-ran the same sabotage and it now fails (`isinstance(None, ViewportPort)`) and passes when restored.
  - `[medium]` `[defer]` `build_readonly_profile` neither accepts nor forwards `viewport_port` — real but inert until a consumer exists (tool_catalog.py:1368).
  - `[medium]` `[defer]` `check_imports.py:41 FREECAD_MODULE_ALIASES` omits `FreeCADGui` — live pre-existing defect, explicitly story 8.5 AC2's scope, not caused by this change.
  - `[low]` `[defer]` 9 pre-existing ruff E501 errors; CI lint leg red independently of this change, no line this diff touched.
  - `[false]` `[reject]` "gui_external host neither injects a port nor states None, leaving its capability undefined" — refuted: `hosts/gui_external/entry.py` contains no `build_inline_handlers` call at all; it builds proxy handlers and forwards over RPC, so there is no wiring seam to state anything at.
  - `[false]` `[reject]` "`total=False` with `# required` comments gives no requiredness, so a producer may omit `fits`/`checked`" — refuted as a defect of this change: `# required` on a `total=False` TypedDict is the shipped convention (contracts/capabilities.py:8-13), and generated schemas enforce requiredness. Changing it here alone would diverge from every other contract.
  - `[false]` `[reject]` "`viewport_port` is accepted then discarded, so the injected port is unreachable" — not a defect: the spec's Never list forbids threading it further because no consumer exists; the verification-gap layer independently confirmed the signature is pinned by the two call sites.
  - `[maybe-false]` `[reject]` "ActiveView exists but its widget is hidden/zero-sized; ratio later divides by zero" — the division lives in story 8.2, which does not exist yet; guarding state this story never demonstrated reachable is not warranted here.
  - `[maybe-false]` `[reject]` "ActiveView is a non-3D view (spreadsheet/TechDraw), so available() is wrongly true" — plausible but unverified against real FreeCAD, and the consumer that would misuse it is story 8.2. Would be settled by checking what `getDocument(name).ActiveView` returns with a spreadsheet tab active in a live session.
  - `[maybe-false]` `[reject]` "document closed between available() and view() leaves a stale True" — `view()` already returns None on any failure and never raises, so a caller that checks the return cannot project through a None view.
  - `[false]` `[reject]` "bootstrap.py:25 module-level import of the viewport module violates the stated guarded-import pattern" — refuted: `viewport.py` is stdlib-only at import time (the `FreeCADGui` import is function-local inside `_active_view`), so the module cannot fail to import; the guarded pattern applies to FreeCAD/Qt imports, which this module has none of at module level.
  - `[false]` `[reject]` "`render_port=object()` in the seam test proves less than it claims" — the test's subject is the viewport seam, not the render port; `object()` as a never-called positional placeholder is the shipped idiom (test_mcp_surface.py:700, test_assistant_readonly_profile.py:133).
  - `[low]` `[reject]` "`issubclass` on runtime_checkable Protocols asserts nothing about separateness" — the assertion is cheap and correct as a regression guard against someone making ViewportPort inherit RenderPort; the added arity test covers the substantive concern.
  - `[false]` `[reject]` "docstring asserts an unimplemented ratio invariant that 8.2 may compute differently" — that is what a contract is for: it binds 8.2. AD-32 requires the invariant be stated where the type lives.
  - `[low]` `[reject]` "no test builds the registry with a live viewport_port injected" — superseded by the new seam test, which asserts exactly that through `start_bridge`.
  - `[maybe-false]` `[reject]` "getDocument raising RuntimeError (non-import failure) is untested" — the except branch is exercised by the missing-document (NameError) and missing-Name (AttributeError) tests; a third exception type through the same branch adds no coverage.
  - `[false]` `[reject]` "headless AC is untestable because no code path asks the framing question" — the AC's subject is the port's answer, which `test_available_false_naming_the_missing_gui_when_freecadgui_is_absent` exercises directly. No consumer existing yet is this story's stated scope, not a verification gap.
  - `[low]` `[reject]` Remaining suggestions to add `getattr` guards for absent `Name`/`ActiveView` attributes — the missing-`Name` case now returns a stated reason; further guards defend states never demonstrated reachable and would add branches for impossible scenarios.
  - `[false]` `[reject]` ×7 additional edge-case rows duplicating the reason-string, arity, keyword-only and ActiveDocument-guard claims already patched above — same defects, counted once each in the patched rows.

## Design Notes

**Why `available` and `view` both take a document.** AD-29 states the availability answer is "per document": a GUI session can have one document with an open 3D view and another without. A process-wide `available()` would answer for the session and then find no view for the specific handle — the exact `fits:null`-vs-omitted confusion AD-32 forbids. Two methods rather than one returning the view: `available` is the honest capability answer stories 8.2/8.4 branch on, `view` is the handle 8.2 projects through.

**Why `object` and not a typed view.** `contracts/` is stdlib-only, so `View3DInventor` cannot be named there. `RenderPort.render` already types its document parameter as `object` (`render.py:86`) for the same reason — this follows the shipped precedent rather than inventing a stub type.

Shape to mirror, from `render.py:79-84`:

```python
@runtime_checkable
class RenderPort(Protocol):
    """The render capability the host injects; the usecase depends only on this shape."""

    def available(self) -> tuple[bool, str | None]:
        """Return ``(is_available, reason)``; ``reason`` is set only when unavailable."""
```

## Verification

**Commands:**
- `uv run python scripts/check_imports.py` -- expected: exits 0, prints `check_imports OK`. Proves `hosts/gui_addon/viewport.py` needs no exemption and `contracts/` stayed stdlib-only.
- `uv run python scripts/gen_schemas.py --check` -- expected: exits 0, no drift. `FramingVerdict` is not embedded in any schema in this story; a drift failure here means a contract was wired up early.
- `uv run pytest tests/external/test_viewport_port.py tests/external/test_render_probe.py tests/external/test_check_imports.py -q` -- expected: all pass, including the untouched `test_render_port_protocol_shape`.
- `uv run pytest tests/external -q` -- expected: no regressions in the external leg.
- `git diff --stat -- src/freecad_buddy/adapters/render_probe.py` -- expected: empty output (the file is untouched).

**Manual checks (if no CLI):**
- The in-FreeCAD leg (`tests/infc/`, run under `FreeCADCmd`) cannot exercise a live viewport, so the live-`ActiveView` true path is not covered by CI. Confirm by inspection that `GuiViewportPort.view` returns `getDocument(<Name>).ActiveView` and that `FreeCADGui.ActiveDocument` appears nowhere in the diff.

## Auto Run Result

Status: done
Blocking condition: none

### Implemented change

The AD-29 live-camera seam. `ViewportPort` is declared as a separate `@runtime_checkable` Protocol beside `RenderPort` in the innermost ring, with `FramingVerdict` for the AD-32 block. A `GuiViewportPort` in the GUI-addon host resolves each document's live 3D view through `FreeCADGui.getDocument(<Name>).ActiveView`, never `FreeCADGui.ActiveDocument`. The GUI host injects a live port at the `build_inline_handlers` seam; the headless host injects `None` explicitly. No usecase consumes the port yet — that is story 8.2/8.4.

### Files changed

- `src/freecad_buddy/contracts/render.py` -- adds `FramingVerdict` (with all three AD-32 no-verdict states, the discarded-corner `ratio` rule and the AD-28 major-bump note) and the `ViewportPort` Protocol.
- `src/freecad_buddy/contracts/__init__.py` -- re-exports both names, alphabetically.
- `src/freecad_buddy/hosts/gui_addon/viewport.py` -- new: `GuiViewportPort`, per-document `available`/`view` with four distinct stated reasons and a function-local guarded `FreeCADGui` import.
- `src/freecad_buddy/hosts/gui_addon/bootstrap.py` -- injects `viewport_port=GuiViewportPort()`.
- `src/freecad_buddy/hosts/headless/entry.py` -- injects `viewport_port=None` explicitly, with the reason stated.
- `src/freecad_buddy/hosts/tool_catalog.py` -- keyword-only `viewport_port` seam; `HandlerFactory` deliberately not widened.
- `tests/external/test_viewport_port.py` -- new: conformance by name and arity, the four unavailable reasons and their distinctness, per-document targeting with an `ActiveDocument` guard that raises, and the GUI/headless wiring seams.
- `tests/external/test_check_imports.py` -- pins `QT_EXEMPT_ADAPTERS` to its single entry (AC3 regression guard).

### Review findings

- Patches applied: 10 (high 1, medium 5, low 4). The `high` was the GUI injection having no executing test.
- Deferred: 3 — `build_readonly_profile` not forwarding the port; the pre-existing `FREECAD_MODULE_ALIASES` `FreeCADGui` gap (story 8.5 AC2); 9 pre-existing ruff E501 errors.
- Rejected: 21, each with its refutation recorded in the Review Triage Log above.

### Follow-up review

`followup_review_recommended: true`. First pass, one `high` entry patched. The specific unverified risk: the GUI-host path cannot be exercised against real FreeCAD in CI. The new seam test drives `start_bridge` with a stubbed `PySide` and a stubbed listener, so it proves a conforming port is *passed* to `build_inline_handlers` — it does not prove `FreeCADGui.getDocument(<Name>).ActiveView` returns what this code expects on a live session. Two rejected `maybe-false` findings sit on that same blind spot: whether `ActiveView` is non-`None` for a non-3D active tab (spreadsheet, TechDraw), and whether a zero-extent view reports available. Story 8.2 is the first code to project through that handle and should settle both against a live GUI.

### Verification performed

- `uv run python scripts/check_imports.py` -- `check_imports OK` (exit 0).
- `uv run python scripts/gen_schemas.py --check` -- `gen_schemas --check OK` (exit 0); confirms no contract was wired into a schema early.
- `uv run pytest tests/external -q` -- 922 passed, 5 warnings. (917 before the review patches, 916 at first implementation.)
- `git diff --stat -- src/freecad_buddy/adapters/render_probe.py` -- empty; AC3's "untouched" requirement holds.
- `uv run ruff check .` -- 9 errors, all pre-existing and none on a line this diff touched (identical count before and after).
- Falsification test for the `high` finding: replacing `viewport_port=GuiViewportPort()` with `None` in `bootstrap.py` made `test_gui_addon_injects_a_live_viewport_port_at_the_wiring_seam` fail on `isinstance(None, ViewportPort)`; restoring it made the suite pass. Before the patch the same sabotage left all 917 tests green.
- Matrix test audit: all six I/O matrix rows have a covering test that ran and passed.

### Residual risks

- The live-`ActiveView` true path is fake-driven only (see Follow-up review above).
- `viewport_port` reaches `build_inline_handlers` and stops; the port is injected but not yet reachable by any tool. This is the spec's stated scope, and it means the seam's end-to-end value is unproven until story 8.2 consumes it.
- Epic 8 stories 8.2-8.5 remain `backlog`. Nothing observable through MCP has changed: no `framing` envelope key, no `view_fit_viewport` tool, no warning sentence.
