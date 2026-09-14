# TC-16-04 — Observed capability matrix vs decision 016

Measured 2026-09-14 on this machine. Headless leg = micromamba `fcb` env, **FreeCAD 1.1.0**.
GUI leg = `C:\Program Files\FreeCAD 1.1\bin\freecad.exe`, **FreeCAD 1.1.1**. Both legs recorded
beside each result, so a version difference is distinguishable from a real boundary change.

| Entry point | Module | Headless (1.1.0) | GUI (1.1.1) | Decision 016 claims | Agrees |
| --- | --- | --- | --- | --- | --- |
| `TechDrawGui` (import) | Gui | **ImportError** | **SUCCESS** | Gui-only | yes |
| `exportPageAsSvg` | Gui | unreachable | **present** | Gui-only | yes |
| `exportPageAsPdf` | Gui | unreachable | **present** | Gui-only | yes |
| `exportPage*` on App module | App | **`[]`** | **`[]`** | none registered | yes |
| `projectToSVG` | App | present | present | headless-reachable | yes |
| `viewPartAsSvg` | App | present | present | headless-reachable | yes |
| `makeExtentDim` | App | present | present | headless-reachable | yes |
| `makeDistanceDim` | App | present | present | headless-reachable | yes |
| `writeDXFPage` | App | present | present | headless, DXF only | yes |

## Verbatim evidence

Headless, fresh process (`tc-16-01-import.txt`):

```
ImportError: Cannot load Gui module in console application.
exit=1
```

Headless App module (`tc-16-01-app-module.txt`):

```
FreeCAD version: 1.1.0
TechDraw imported OK: TechDraw
exportPage* names on App module: []
  has projectToSVG     : True
  has viewPartAsSvg    : True
  has makeExtentDim    : True
  has makeDistanceDim  : True
  has writeDXFPage     : True
```

GUI process (`tc-16-02-gui-import.txt`):

```
FreeCAD version in GUI process: 1.1.1
TechDrawGui import: SUCCESS (C:\Program Files\FreeCAD 1.1\lib\TechDrawGui.pyd)
  hasattr exportPageAsSvg: True
  hasattr exportPageAsPdf: True
TechDraw (App) exportPageAsSvg present: False
TechDraw (App) exportPage* names: []
```

## Verdict

**No divergence.** Every row of decision 016's table matches the installed builds. The split is
between **modules** (`TechDrawGui` vs `TechDraw`), not between processes — proven by the GUI leg,
where `TechDrawGui` imports and exposes both exporters while the App module in that *same process*
still registers no `exportPage*` name at all. Story 4.3's premise — that a headless page export does
not exist and the sheet must be composed from view-level SVG — holds against the running application.

No defect recorded for this run's `bugs.md` from TC-16.

## What this run did not establish

- The 1.1.0 / 1.1.1 version difference between legs is real but did not matter here: the App module
  registers no `exportPage*` on **either** leg, so the boundary is not a version artifact.
- No vision model read a composed sheet — no credentials exist (decision 017), so the judge's
  ability to interpret these drawings is still unmeasured.
