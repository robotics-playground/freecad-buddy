---
title: 'Story 8.5: Enforcement — Framing Contract Test & CI Alias Gap'
type: 'feature'
created: '2026-09-12'
status: 'done'
baseline_revision: 'f086447e480c767505853735d356b95a621fecec'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-8-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-8-4-framing-warning-on-tool-results.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Two rules this epic relies on are enforced by convention, not by CI. The AD-20 implicit-target ban does not match `FreeCADGui.ActiveDocument` at all — a live pre-existing defect — and the checker's own diagnostics still advertise a Qt exemption that no longer exists, so an implementer reading them would believe `adapters/marshal.py` may import Qt.

**Approach:** Close the alias gap in `scripts/check_imports.py`, prove it closed with a planted fixture, and correct the checker's stale self-description. The framing shared-helper rule is enforced by the contract test story 8.4 delivered.

## Boundaries & Constraints

**Always:**
- `FREECAD_MODULE_ALIASES` includes `FreeCADGui` alongside `FreeCAD` and `App`, so `FreeCADGui.ActiveDocument` and `FreeCADGui.setActiveDocument` are flagged by the existing ban.
- A **planted** `FreeCADGui.ActiveDocument` access in a test fixture is asserted to be flagged, so the gap is proven closed rather than assumed. A test that only asserts the alias set's membership does not prove the checker acts on it.
- Every stale `adapters/marshal.py` Qt-exemption claim is corrected. It appears in **four** places: the module docstring (`:11`), an inline comment (`:86`), and two violation messages (`:251`, `:323`). `QT_EXEMPT_ADAPTERS` holds exactly one entry and the diagnostics must say so.
- The AD-32 deferred thresholds — the `fitAll` margin and the near-miss tolerance — are recorded with the mechanism and the measurement that justified each value, per the commenting standard for tuned constants.

**Never:**
- Do **not** add a second entry to `QT_EXEMPT_ADAPTERS`, and do **not** relax any existing rule to make the new alias pass.
- Do **not** rewrite the `_check_active_document` matching logic. The ban already matches `<alias>.<attr>`; only the alias set is wrong.
- Do **not** re-implement the framing contract test if story 8.4 already delivered one. Verify it exists and actually fails when the rule is broken; add it only if missing.
- Do **not** rename `Gui` as an alias. The checker matches the bound module name, and `import FreeCADGui as Gui` is an aliased import — state the limitation rather than silently half-solving it.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Planted `FreeCADGui.ActiveDocument` | A fixture tree containing that access | `check_tree` returns a violation naming it | Flagged, exit 1 |
| Planted `FreeCADGui.setActiveDocument` | Same, the setter form | Flagged the same way | Flagged, exit 1 |
| Existing `FreeCAD.ActiveDocument` ban | The already-banned form | Still flagged — the change is additive | Flagged, exit 1 |
| A non-module `registry.ActiveDocument` | An attribute on something that is not a FreeCAD module binding | **Not** flagged; it is not the banned form | No violation |
| The real tree | `src/freecad_buddy/**` as shipped | `check_imports OK` — the alias fix flags nothing existing | Exit 0 |
| Qt in `adapters/marshal.py` | A fixture importing Qt there | Flagged, and the message names only `adapters/render_probe.py` as exempt | Flagged, exit 1 |

</intent-contract>

## Code Map

- `scripts/check_imports.py:41` -- `FREECAD_MODULE_ALIASES = frozenset({"FreeCAD", "App"})`. **The live defect.** Add `"FreeCADGui"`.
- `scripts/check_imports.py:42` -- `ACTIVE_DOCUMENT_ATTRS = frozenset({"ActiveDocument", "setActiveDocument"})`; both forms come along for free once the alias is added.
- `scripts/check_imports.py:149-169` -- `_check_active_document`; the match at `:162` is `isinstance(base, ast.Name) and base.id in FREECAD_MODULE_ALIASES`. Logic is correct; only the set is wrong. Note this matches the **bound name**, so `import FreeCADGui as Gui` then `Gui.ActiveDocument` still evades it — state that limitation, do not paper over it.
- `scripts/check_imports.py:11` -- module docstring: `"Qt / FreeCADGui / PySide* allowed ONLY in hosts/**, adapters/marshal.py, adapters/render_probe.py."` **Stale.**
- `scripts/check_imports.py:86` -- inline comment referencing `adapters/sub/marshal.py`; re-word so it does not imply `marshal.py` is exempt.
- `scripts/check_imports.py:251` and `:323` -- two violation messages repeating `"hosts/**, adapters/marshal.py, adapters/render_probe.py"`. **Stale in both.**
- `scripts/check_imports.py:79` -- `QT_EXEMPT_ADAPTERS = frozenset({"adapters/render_probe.py"})`; already pinned by `tests/external/test_check_imports.py:95` (added in story 8.1).
- `tests/external/test_check_imports.py` -- the fixture-tree style: `_make_tree(tmp_path, {...})` then `check_imports.check_tree(root)`. `:92` `test_qt_in_marshal_flagged` and `:96` `test_qt_in_render_probe_allowed` are the models for the new planted-access tests. `:310-314` already covers the `registry.ActiveDocument` non-module case.
- `src/freecad_buddy/hosts/gui_addon/viewport.py:15, :75` -- the only mentions of `FreeCADGui.ActiveDocument` in `src/`, both docstring prose stating the rule. Confirms the alias fix flags no existing code, which is why the planted fixture is the only proof available.
- `src/freecad_buddy/usecases/view_fit.py` -- where the `fitAll` margin lives (story 8.3); the near-miss tolerance lives with the framing verdict in `usecases/framing.py`.

## Tasks & Acceptance

**Execution:**
- `scripts/check_imports.py` -- add `"FreeCADGui"` to `FREECAD_MODULE_ALIASES`, and correct all four stale `adapters/marshal.py` exemption claims (`:11`, `:86`, `:251`, `:323`) to name only `adapters/render_probe.py` -- closes the AD-20 evasion and stops the checker misinforming its own readers.
- `tests/external/test_check_imports.py` -- add planted-fixture tests for `FreeCADGui.ActiveDocument` and `FreeCADGui.setActiveDocument` asserting each is flagged, and assert the Qt violation message no longer names `marshal.py` -- proves the gap is closed rather than assumed.
- `src/freecad_buddy/usecases/view_fit.py` and `src/freecad_buddy/usecases/framing.py` -- record the `fitAll` margin and near-miss tolerance as named constants, each commented with the mechanism and the measurement that justified the value -- an untuned hair-trigger warning on every call is noise, and the next reader would otherwise retune blind.
- `tests/external/test_framing_contract.py` -- verify story 8.4's contract test exists and genuinely fails when a tool appends the sentence itself; add it only if 8.4 did not deliver it -- without a failing-when-broken test the shared-helper rule is convention only.

**Acceptance Criteria:**
- Given a fixture tree containing `FreeCADGui.ActiveDocument`, when `check_tree` runs, then a violation is returned naming that access — and the same fixture returns no violation before the alias change, demonstrating the test detects the fix.
- Given the shipped tree, when `scripts/check_imports.py` runs, then it exits 0: the alias fix flags nothing existing.
- Given any Qt-violation message the checker emits, when read, then it names `adapters/render_probe.py` as the sole adapter exemption and does not mention `adapters/marshal.py`.
- Given the recorded thresholds, when read, then each names the mechanism and the measurement behind its value rather than appearing as a bare number.
- Given the aliased-import limitation (`import FreeCADGui as Gui`), when the checker's documentation is read, then the limitation is stated rather than implied to be covered.

## Spec Change Log

## Review Triage Log

## Design Notes

**Why a planted fixture is the only available proof.** Adding `FreeCADGui` to the alias set flags nothing in the current tree — verified: the only occurrences in `src/` are docstring prose in `hosts/gui_addon/viewport.py`. A test asserting `"FreeCADGui" in FREECAD_MODULE_ALIASES` would pass even if `_check_active_document` ignored the set entirely. The fixture is what connects the set to the behavior.

**The aliased-import hole is real and stays open.** `_check_active_document` matches `ast.Name` against the bound module name, so `import FreeCADGui as Gui` followed by `Gui.ActiveDocument` is not flagged — and `hosts/gui_addon/InitGui.py:22` uses exactly that alias form. Closing it needs import-binding tracking through the AST, which is a larger change than this story. State the limitation in the checker's docstring so the next reader knows the ban's true reach.

## Verification

**Commands:**
- `uv run python scripts/check_imports.py` -- expected: `check_imports OK`, exit 0. Proves the alias fix flags nothing in the shipped tree.
- `uv run pytest tests/external/test_check_imports.py -q` -- expected: all pass, including the new planted-access tests.
- `uv run pytest tests/external -q` -- expected: no regressions.
- `grep -n "adapters/marshal.py" scripts/check_imports.py` -- expected: no line claims it is Qt-exempt. Any surviving hit must be a comment that clearly does not grant an exemption.
- `uv run ruff check .` -- expected: 9 pre-existing errors, none newly introduced.

**Manual checks (if no CLI):**
- Temporarily revert the alias addition and re-run the new planted-fixture test: it must fail. A test that passes both before and after the fix proves nothing.
