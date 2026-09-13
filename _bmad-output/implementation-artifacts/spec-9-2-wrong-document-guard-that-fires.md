---
title: 'Story 9.2: A Wrong-Document Guard That Can Actually Fire'
type: 'bugfix'
created: '2026-09-13'
status: 'done'
baseline_revision: '55078d0f2a963fde2aae12e03187e2c0cae90496'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-9-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-9-1-shared-projection-self-verifying-fit.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** `view_fit_viewport`'s wrong-document guard compares the target against the view it
resolved *from the target's own name*, so the comparison tests a name against itself and returns
early every time. R2-02 reproduced the consequence: with `box_10_20_30` on screen, a fit targeting
`tc14bar` returned `fitted: true` and rewrote the camera of the document the human was looking at.

**Approach:** Give `ViewportPort` a third method, `showing_document_name() -> str | None`, that
names the one document on screen from a source independent of the target handle — the focused Qt
MDI sub-window inside the GUI addon host. Compare the target against that.

## Boundaries & Constraints

**Always:**
- `showing_document_name()` is **session-wide** and takes **no document**. It answers "which
  document is on screen", which no per-document accessor can answer.
- The GUI implementation reads the focused MDI sub-window. Verified live on FreeCAD 1.1.1: the
  hierarchy is `Gui::MainWindow.QMdiArea.QMdiSubWindow.Gui::View3DInventor`, reachable from
  `FreeCADGui.getMainWindow()`, which `ApplicationPy.cpp:345` exposes as a wrapped `QMainWindow`.
- `None` means "could not read the on-screen name" and the fit **proceeds** — an unreadable name is
  no evidence of a mismatch.
- `None` carries **no reason string**, deliberately unlike `available()`: "no viewport" and "name
  unreadable" are treated identically, and a reason would invite a caller to branch on a
  distinction with no consequence.
- A refusal names **both** documents and moves **no** camera.
- The `ViewportPort` docstring's "Both answers are per document" sentence is corrected — the new
  method falsifies it exactly where an implementer reads it.
- `showing_document_name()` governs the **fit refusal only**. The framing verdict still describes
  the targeted document's own view.

**Never:**
- Do not use `FreeCADGui.ActiveDocument` or `setActiveDocument` in any ring, including `hosts/`.
  `scripts/check_imports.py:53` bans both with no layer filter, and R2-02 is the implicit-target
  defect that ban exists to prevent. Weakening the enforcer to make this fix easier inverts the
  control.
- Do not activate, raise, or otherwise touch the named document's view to resolve the comparison.
- Do not re-open story 9.1's measurement work; the fit body is settled. This story changes the
  guard and the port only.
- Do not import Qt or `FreeCADGui` into `usecases/` — the name arrives through the port.
- Do not make the framing verdict depend on the on-screen document.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Match | Target A, A on screen | Fit proceeds normally | No error expected |
| Mismatch | Target A, B on screen | `ValidationError` naming **both** A and B; no camera moves | `INVALID_INPUT` |
| Unreadable name | `showing_document_name()` returns `None` | Fit proceeds | No reason string attached |
| Headless | Port is `None`, or host has no viewport | Unchanged shipped envelope | Existing codes preserved |
| Framing target | Target A exists but B is focused | Verdict still describes **A**'s view | Verdict unaffected by the refusal rule |
| No 3D view on screen | Only a non-3D sub-window focused (e.g. `StartView`) | `None`, so the fit proceeds | Treated as unreadable |

</intent-contract>

## Code Map

- `src/freecad_buddy/contracts/render.py:130` -- `ViewportPort` Protocol. `available():140`,
  `view():143`. Add the third method here. The class docstring at `:132-138` ends with "Both
  answers are per document, because one GUI session can hold a document with an open 3D view
  beside one without" — that sentence must be corrected, not deleted wholesale; the per-document
  claim is still true of the first two methods.
- `src/freecad_buddy/hosts/gui_addon/viewport.py:12` -- `GuiViewportPort`. `available():20`,
  `view():47` (resolves `gui.getDocument(name).ActiveView` at `:54`), `_import_gui():59`,
  `_document_name():72`. The new method goes here and must **not** use `_document_name`, which
  reads a handle it will not be given.
- `src/freecad_buddy/usecases/view_fit.py:288` -- `_require_same_document(document, view)`, the
  tautological guard. Its own docstring admits the shape: "The port resolves a view through
  `getDocument(<Name>)`, so a view handed back for document A belongs to A." Rewrite it to take the
  port's session-wide name instead of the view. `_view_document()` becomes unused once it does —
  remove it, since story 9.1's smell pass applies here too.
- `src/freecad_buddy/usecases/view_fit.py:96` -- the `fit()` closure calls the guard after
  resolving the view. The refusal must happen **before** any camera write; the existing call site
  is already before `_read_camera`/`_fit_all`, so keep that ordering.
- `scripts/check_imports.py:53` -- `ACTIVE_DOCUMENT_ATTRS` freezes `ActiveDocument` and
  `setActiveDocument`. `:47-52` explains `FreeCADGui` is in the banned-module set deliberately.
  Read-only for this story; the new code must pass it unchanged.
- `tests/external/test_viewport_port.py` -- exercises the real `GuiViewportPort` against a
  monkeypatched fake `FreeCADGui` module (teeth-check at `:192`). The new method's host tests
  belong here and need a fake main window exposing the MDI chain.
- `tests/external/test_view_fit.py:66` -- `_FakeViewportPort` gains the third method. Every
  existing fake must grow it or the Protocol check fails; `test_framing.py:99` and
  `test_framing_envelope.py:102` define their own and are `read_framing` callers, so confirm
  whether the Protocol's `runtime_checkable` isinstance is asserted against them anywhere.
- `tests/uat/testcases/TC-14-viewport-framing-and-auto-fit.md` -- TC-14-06 is R2-02's scenario and
  currently documents the behaviour that failed. Update it, and add the regression to TC-15.

## Tasks & Acceptance

**Execution:**

- `src/freecad_buddy/contracts/render.py` -- add `showing_document_name(self) -> str | None` to
  `ViewportPort` with a docstring stating it is session-wide, takes no document, and that `None`
  means unreadable and is not a refusal; correct the "Both answers are per document" sentence to
  scope that claim to `available()` and `view()` -- a contract that contradicts itself where the
  implementer reads it is the defect this story is fixing one layer up (AC1, AC6).
- `src/freecad_buddy/hosts/gui_addon/viewport.py` -- implement the method off
  `FreeCADGui.getMainWindow()`, walking to the focused `QMdiArea` sub-window and reading the
  document of the view it hosts; return `None` on any missing hop, non-3D sub-window, or raise --
  the on-screen name must come from a source independent of the target handle (AC1).
- `src/freecad_buddy/usecases/view_fit.py` -- rewrite `_require_same_document` to compare the
  target's name against `viewport_port.showing_document_name()`, raising `ValidationError` naming
  both documents; delete `_view_document`, now unused -- the shipped comparison tests a name
  against itself (AC2, AC3).
- `src/freecad_buddy/usecases/view_fit.py` -- keep the guard's call site before any camera write,
  and leave the framing verdict keyed on the targeted document -- a refusal must move no camera,
  and the verdict's target is not the on-screen document (AC3, AC7).
- `tests/external/test_viewport_port.py` -- add host tests for the new method against the
  monkeypatched `FreeCADGui`: names the focused 3D sub-window's document, returns `None` for a
  non-3D sub-window, `None` when any hop is missing, and `None` rather than raising on error.
- `tests/external/test_view_fit.py` -- add the third method to `_FakeViewportPort`; add the
  mismatch row asserting `ValidationError` naming both documents with `fit_calls == 0`, the match
  row, and the `None`-proceeds row -- R2-02's exact reproduction.
- `tests/uat/testcases/TC-14-viewport-framing-and-auto-fit.md` -- update TC-14-06 to the behaviour
  this story lands, so the suite stops documenting the defect as expected.

**Acceptance Criteria:**

- Given two open documents with B focused, when a fit targets A, then it raises
  `ValidationError` naming both A and B and no `fitAll` reaches any view.
- Given `showing_document_name()` returns `None`, when a fit runs, then it proceeds and no reason
  string is attached anywhere in the result.
- Given `uv run python scripts/check_imports.py`, when the change is done, then it still reports
  clean -- no ring gained a `FreeCADGui.ActiveDocument` access.
- Given `grep -n "_view_document" src/freecad_buddy/usecases/view_fit.py`, when the change is done,
  then it returns nothing.
- Given the `ViewportPort` docstring, when read, then no sentence claims all three answers are per
  document.
- Given story 9.1's suite, when it runs, then every test still passes -- this story changes the
  guard, not the measurement.

## Verification

**Commands:**
- `uv run ruff check <the changed files>` -- expected: clean.
- `uv run pytest tests/external/test_view_fit.py tests/external/test_viewport_port.py -q` --
  expected: all pass, including the new mismatch, match and `None` rows.
- `uv run pytest -q` -- expected: no new failures; story 9.1's 1061 remain green.
- `uv run python scripts/check_imports.py` -- expected: `check_imports OK`.
- `grep -n "_view_document" src/freecad_buddy/usecases/view_fit.py` -- expected: no output.

**Manual checks (if no CLI):**
- The live-GUI reproducer (R2-02) is a UAT step: open document A with a solid, open document B so B
  becomes the focused tab, then fit A. The call must be refused naming both documents, and a
  `cua-driver` capture must show B's camera **unchanged**. Automated verification alone is not
  sufficient.
