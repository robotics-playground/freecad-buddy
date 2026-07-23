# FreeCAD Logic — Verify Against Source Before Implementing

**Rule:** Any code that depends on a FreeCAD enum value, preference key, parameter name, API
signature, or documented semantic MUST be confirmed against the FreeCAD source under
`docs/references/FreeCAD/` **before** it is written. Never assume ordering, naming, numeric
values, or behavior from memory — FreeCAD's public Python surface is thin and its C++ internals
routinely contradict the obvious guess.

## Why

FreeCAD enums are frequently **non-sequential** and their stored preference values are the enum's
numeric value, not an array index. Guessing produces code that looks right and silently does the
wrong thing.

**Worked example (the rule's origin).** The 3D-view anti-aliasing preference stores the
`Gui::AntiAliasing` enum value at `User parameter:BaseApp/Preferences/View` → `AntiAliasing`.
The obvious assumption — "value = position in the dropdown" — is wrong. From
`docs/references/FreeCAD/src/Gui/Multisample.h`:

```cpp
enum class AntiAliasing { None = 0, MSAA1x = 1, MSAA2x = 2, MSAA4x = 3, MSAA6x = 5, MSAA8x = 4 };
```

`MSAA8x = 4` and `MSAA6x = 5` — swapped relative to their visual order. A user with **MSAA 8×**
selected stores `Value="4"`. Mapping `4 → 6×` (index assumption) under-samples the render. The
correct sample map, read from `Gui/Multisample.cpp`'s `textMSAA` table, is
`{0:0, 1:1, 2:2, 3:4, 4:8, 5:6}`.

## How to apply

1. **Locate the authority in source.** Grep `docs/references/FreeCAD/src/` for the enum, key, or
   symbol. Read the actual definition (`.h` for enum values, `.cpp` for read/write and mapping).
2. **Confirm the exact value/semantic** — enum numeric values, the preference group/key strings,
   the units, the return convention (e.g. `writeToImage` returns `None` on success on some builds).
3. **Encode a source-cited mapping**, not an inferred one. A comment naming the source file is
   the receipt (e.g. `# Gui/Multisample.h — enum is non-sequential`).
4. **When the source is ambiguous, probe the running FreeCAD** (read the actual stored value from
   `user.cfg` / `FreeCAD.ParamGet`) and cross-check against the source before trusting either.

Applies to: enum-to-value maps, `ParamGet` keys, view-provider / Coin API calls, offscreen-render
setup, export/tessellation parameters, and any place a FreeCAD-side assumption drives behavior.
