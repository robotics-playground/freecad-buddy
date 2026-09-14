# UAT run 2026-09-13-07 — TC-16 Headless TechDraw Capability Boundary

**Story**: 4.1 Entry Gate G3.E
**Suite**: `tests/uat/testcases/TC-16-techdraw-capability-boundary.md`
**Build**: FreeCAD 1.1.1, Libs 1.1.1R20260414 (Git shallow)
**Driver**: `cua-driver` 0.28.1 against the live GUI (pid 1456) + `FreeCADCmd` for the headless leg
**Verdict**: **PASS** — the capability boundary `docs/decisions/016-headless-techdraw-export.md`
records holds against the running application. Two findings below; neither invalidates the
verdict, and both matter to Story 4.3.

## Preconditions

| Check | Result |
| --- | --- |
| No document open at start | PASS — `document_list` reported `0 open document(s).` |
| FreeCAD 1.1.1 is the build under test | PASS — banner and `App.Version()` both report 1.1.1 |
| `cua-driver` daemon interactive | PASS — `cua-driver doctor`: session 1 has an attached interactive desktop |
| Absolute paths used | PASS |

One deviation from the written preconditions: a FreeCAD GUI process (pid 1456) was **already
running, minimized**, rather than started fresh. It held no open documents, so the "no document
open" precondition was met. It was restored and used rather than killed and relaunched. This
affects no assertion below — every result was read from that process or from a separate fresh
`FreeCADCmd`.

## Scenario results

### TC-16-01 — headless leg — PASS

`FreeCADCmd tests/run_tests.py` over `HeadlessTechDrawBoundaryTest`: **6 tests, all OK**
(evidence: `evidence/tc-16-01-headless.txt`).

| Assertion | Measured |
| --- | --- |
| `TechDrawGui` unimportable in a fresh console subprocess | PASS — `ImportError: Cannot load Gui module in console application` |
| Headless `TechDraw` registers no `exportPage*` | PASS — `[]` |
| `projectToSVG`, `viewPartAsSvg`, `makeExtentDim`, `makeDistanceDim` present | PASS — all four |
| `projectToSVG` returns non-empty SVG carrying `<path` for front/top/right | PASS |
| 30x20x10 block projected down Z measures 30 x 20 | PASS |
| Full headless page path builds; `viewPartAsSvg` non-empty over the built view | PASS |

### TC-16-02 — `TechDrawGui` IS importable in the GUI process — PASS

Run inside the GUI process via the Macro dialog (evidence: `evidence/tc-16-02-03-gui.txt`):

```
TC-16-02 import TechDrawGui: SUCCESS -> <module 'TechDrawGui' from 'C:\Program Files\FreeCAD 1.1\lib\TechDrawGui.pyd'>
TC-16-02 exportPageAsSvg/exportPageAsPdf: (True, True)
```

Both page exporters exist in the GUI; neither exists headless. That is the boundary.

### TC-16-03 — the GUI produces the same projection as the headless path — PASS

```
TC-16-03 projected extent XLength=30.000000 YLength=20.000000 (headless measured 30.0 / 20.0)
```

Exact agreement to six decimal places. `viewPartAsSvg` in the GUI returns 308 bytes of real path
geometry whose first path is `M -15 10 L -15 -10` — a 30 x 20 rectangle centred on the origin,
matching the block (see Finding 1 for why the first reading was empty).

**Visual check, performed by the agent** (`evidence/tc-16-03-page.png`,
`tc-16-03-page-open.png`, `tc-16-03-page-fit.png`):

- The 3D viewport, navigation cube reading TOP, shows a grey rectangle of clearly 3:2 proportions
  — the 30 x 20 silhouette the numbers describe, in the orientation they describe.
- The TechDraw Page opened in the TechDraw workbench with Template, Views=View, Scale 1.00.
- The page sheet **appeared blank at first**. Clicking inside it selected `tc16.View.Face0`
  (status bar) and the whole sheet turned selection-green, which shows the view IS present and
  drawn — it is scaled so its single projected face covers the entire sheet, so its outline falls
  outside the visible page and the interior reads as empty white. Not a missing view.

### TC-16-04 — the two legs disagree exactly where the decision says — PASS

| | Fresh `FreeCADCmd` | GUI process |
| --- | --- | --- |
| `import TechDrawGui` | ImportError | SUCCESS |
| `TechDrawGui.exportPageAsSvg` / `exportPageAsPdf` | n/a | `(True, True)` |
| `TechDraw` `exportPage*` names | `[]` | `[]` |
| `projectToSVG` / `viewPartAsSvg` / `makeExtentDim` / `makeDistanceDim` | all present | all present |

The load-bearing comparison holds: **no headless page exporter exists** in either process, while
the Gui module has two. Story 4.3 must compose a page from view-level SVG.

## Findings

Recorded in `bugs.md`. Neither changes the TC-16 verdict.

1. `viewPartAsSvg` returns an empty string when read in the same pass that creates the view (GUI
   only).
2. A DrawViewPart at Scale 1.00 on the default template overflows the sheet, which reads as a
   blank page.

## Cleanup

The `tc16` document created by the macro was **closed without saving** via
`mcp document_close`; `document_list` is back to `0 open document(s).`, the state the run started
in. One macro remains in the user macro directory (`tc16_boundary.FCMacro`) as the executable
record of this run; the throwaway `tc16_svg_retry.FCMacro` was deleted after its measurement was
captured in `evidence/tc-16-03-svg-retry.txt`.
