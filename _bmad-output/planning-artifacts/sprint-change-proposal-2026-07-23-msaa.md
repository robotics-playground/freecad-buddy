# Sprint Change Proposal — 2026-07-23 (render AA + FreeCAD source-verify)

## Section 1: Issue Summary

The manual-test session added config-driven anti-aliasing to the offscreen render
(`render_probe`): the multisample count is read from FreeCAD's own 3D-view preference instead of
being hard-coded. Building it surfaced a trap — FreeCAD's `Gui::AntiAliasing` enum is
**non-sequential** (`MSAA8x=4`, `MSAA6x=5`), so the initial index-based mapping was wrong. Reading
`docs/references/FreeCAD/src/Gui/Multisample.h` caught it (user's config `AntiAliasing=4` =
MSAA 8×, matching their dropdown).

## Section 2: Impact Analysis

- **Epic/Story impact:** none — no scope change; the render code is implemented and verified live
  via MCP against the user's FreeCAD.
- **Artifact conflicts:** the render design doc described the offscreen path without AA; no
  standing rule captured "verify FreeCAD logic against source first."
- **Technical impact:** documentation + a new standard. Code already correct.

## Section 3: Recommended Approach

**Direct Adjustment** (Minor). Document the config-driven AA behavior and codify the
source-verify rule so the enum-assumption bug class cannot recur. No rollback, no MVP change.

## Section 4: Detailed Change Proposals

### E1 — Render AA behavior — `design/integration-mcp-freecad.md` §6

Added `setNumPasses(configured_msaa_samples())` to the offscreen sketch and a paragraph: sample
count read from `Preferences/View/AntiAliasing`, non-sequential enum
(`None=0,MSAA1x=1,MSAA2x=2,MSAA4x=3,MSAA6x=5,MSAA8x=4`) → samples `{0:0,1:1,2:2,3:4,4:8,5:6}`,
`setNumPasses` sets the FBO+GL sample count (`Gui/SoFCOffscreenRenderer.cpp`), fallback to 1
sample. Cites the source-verify standard.

### E2 — New standard — `.knowledge-base/technical/standards/freecad/source-verify.md`

NEW. Rule: any FreeCAD enum value / preference key / param name / API semantic MUST be confirmed
against `docs/references/FreeCAD/` before implementing — never assume. Uses the AA enum as the
worked example; gives a 4-step how-to (locate authority in source, confirm exact value, encode a
source-cited mapping, probe the running FreeCAD when ambiguous).

### E3 — `CLAUDE.md`

§1 "Think Before Coding": added a bullet mandating source-verification of FreeCAD
enums/keys/APIs, citing the non-sequential AA enum. §12 References: added a link to the new
standard.

### E4 — `.knowledge-base/.../testing/freecad-automation-verification.md`

Added a "Render anti-aliasing comes from FreeCAD's own preference" section (enum map + the
module-cache/restart note) and a pointer to the source-verify standard.

## Section 5: Implementation Handoff

- **Scope:** Minor. Recipient: Developer (self) — applied directly this run.
- **Success criteria:** design doc + standards match the shipped config-driven AA behavior; the
  source-verify rule is discoverable from CLAUDE.md and enforced going forward.

## Not changed

Code (`render_probe.py`) already correct and verified live (config `AntiAliasing=4` → 8 samples →
`setNumPasses(8)`), rendered against the user's FreeCAD via MCP.
