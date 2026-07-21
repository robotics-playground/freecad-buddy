# Review — Version & Reality Check Lens

**Artifact:** `ARCHITECTURE-SPINE.md` (architecture-freecad-buddy-2026-07-21)
**Lens:** Every committed decision must be web-researched or reality-checked, not asserted from training data — current versions, technologies still exist and fit, live defaults confirmed.
**Reviewed:** 2026-07-21
**Method:** (a) Traced spine claims to the 18 research reports in `_bmad-output/planning-artifacts/research/` (dated 2026-07-20, web-verified against FreeCAD source + web); spot-checked Sources sections of the MCP-embedding, preview-diff, 3MF-export, headless-CI, and version-matrix reports. (b) 3 targeted WebSearches (2026-07-21) on claims not covered by the reports or likely to have moved: MCP python-sdk/FastMCP release status, admesh maintenance, FreeCAD 1.1 bundled Python.

## Verdict

**Mostly well-grounded — the large majority of committed decisions trace directly to yesterday's web-verified research. Three stack-table claims are stale or unverified and need fixes before Phase 0 pin; none invalidate any AD invariant.**

---

## Findings

### HIGH

#### H-1. Stack pins Python 3.11, but the primary target (FreeCAD 1.1) bundles Python 3.12

- **Spine claim (Stack table):** `Python | 3.11 (FreeCAD 1.x bundled interpreter)`.
- **Reality (web, 2026-07-21):** FreeCAD 1.1's LibPack 3.1.x pins **Python 3.12.x** (3.1.1.3 ships Python 3.12.10); conda-forge also publishes 1.0 builds against py312 (`freecad-1.0.0-py312...`). Only FreeCAD 1.0-era bundles were py311. The version-matrix report explicitly says the 1.1 notes call out *no* Python bump — but that report never asserted 3.11 either; "3.11" appears to come from the 1.0 AppImage naming in the CI report (`...py311.AppImage`) generalized to "1.x". Not verified anywhere for 1.1.
- **Why it matters:** AD-11 makes 1.1.x the *primary blocking* leg; AD-12 code runs inside FreeCAD's bundled interpreter. A 3.11 assumption baked into contracts/usecases (syntax floor, stdlib features, wheel targets for the external env matching in-process behavior) is wrong on the primary leg.
- **Fix:** Change the stack row to: "Python — match bundled interpreter per matrix leg: 3.11 (FreeCAD 1.0.x conda builds) / 3.12 (1.1.x); code floor = 3.11 syntax. External uv env pins independently at Phase 0." Verify actual interpreter version per conda-forge build variant during the Phase 0 spike week (fits the existing "conda `FreeCADCmd` path edge" spike item).
- Sources: [FreeCAD-LibPack releases](https://github.com/FreeCAD/FreeCAD-LibPack/releases), [conda-forge freecad](https://anaconda.org/conda-forge/freecad), [FreeCAD forum py3.12 thread](https://forum.freecad.org/viewtopic.php?t=83356).

#### H-2. MCP SDK row ignores imminent churn: official SDK v2 + a NEW spec (2026-07-28) land within days; "FastMCP" is ambiguous between two diverging projects

- **Spine claim (Stack table):** `MCP Python SDK / FastMCP | current, spec ≥2025-06-18 ... targeting 2025-11-25 — pin exact at Phase 0`.
- **Reality (web, 2026-07-21):**
  - Official `modelcontextprotocol/python-sdk` shipped **v2.0.0b1 on 2026-06-30**; stable v2 is targeted **2026-07-27**, aligned with a **new MCP spec release 2026-07-28** — i.e., both land roughly when Phase 0 would pin. In v2 the `FastMCP` class is **renamed `MCPServer`**.
  - The standalone PrefectHQ **`fastmcp`** package is now **v3.x** (v3.2.4 in April 2026); it began adopting the 2025-11-25 spec at 2.14 (SSE polling SEP-1699, multi-select elicitation SEP-1330, tool-name validation SEP-986).
  - The research reports (embedding report) cite `gofastmcp.com` docs while calling FastMCP "the official SDK" — conflating the official SDK's bundled `FastMCP` class with the separate PrefectHQ project. The spine inherits this ambiguity.
- **Why it matters:** AD-3 (transport run-flag), AD-10 (elicitation, `outputSchema`, `resource_link`), and the Consistency Conventions ("dots illegal in tool names" = SEP-986) all bind to specific SDK surface. Pinning "FastMCP" without naming the package risks importing the wrong API family; pinning v1 the week v2 goes stable risks immediate legacy status; "targeting 2025-11-25" may already be one spec revision behind at pin time.
- **Fix:** In the stack row, name the exact distribution and add a decision note: "Package decided at Phase 0 pin between (a) official `mcp` python-sdk — v2/`MCPServer` goes stable ~2026-07-27 with the 2026-07-28 spec — and (b) standalone `fastmcp` v3.x. Required capabilities regardless of package: streamable HTTP + stdio, elicitation, `outputSchema`/structured output, resource links (spec ≥2025-06-18; prefer ≥2025-11-25)." Also update "targeting 2025-11-25" to "≥2025-11-25; re-evaluate against the 2026-07-28 spec at pin".
- Sources: [python-sdk releases](https://github.com/modelcontextprotocol/python-sdk/releases), [FastMCP updates](https://gofastmcp.com/updates), [fastmcp PyPI](https://pypi.org/project/fastmcp/), [FastMCP vs MCP SDK v2 (AgenticWire)](https://www.agenticwire.news/article/fastmcp-vs-mcp-python-sdk).

#### H-3. admesh is dormant and has no Windows wheels — "current at Phase 0 pin" doesn't hold

- **Spine claim (Stack + AD-9):** `trimesh, admesh, lib3mf | current at Phase 0 pin — export oracles`; AD-9 requires admesh as the second independent STL oracle.
- **Reality (web, 2026-07-21):** PyPI `admesh` latest is **0.98.9** — Python bindings that have not been released in years (effectively unmaintained), with wheels published for **Linux and macOS only**. The dev environment (Environments section) is "Windows/Linux desktop"; `pip install admesh` on Windows means a source build against the ADMesh C library — likely to fail out of the box. The 3MF report itself hedged ("`pip install admesh`, or CLI") but never verified platform coverage or maintenance.
- **Why it matters:** AD-9's independent-oracle rule is sound, but the named oracle can't be assumed installable on half the dev matrix, and "current" misrepresents a dormant package.
- **Fix:** Amend the stack row: "admesh — dormant (0.98.9, no Windows wheels): use as **admesh CLI** oracle and/or Linux-CI-only leg; Windows dev falls back to trimesh + second-source check. Confirm alternative (e.g. `numpy-stl` or ADMesh CLI binary) at Phase 0 pin." AD-9's principle (two independent checkers, disagreement = fail) stands unchanged.
- Sources: [admesh PyPI](https://pypi.org/project/admesh/), [admesh on libraries.io](https://libraries.io/pypi/admesh).

### MEDIUM

#### M-1. conda-forge lags FreeCAD point releases — "1.1.x latest patch" may not be installable in CI

The CI research report verified conda-forge carries **1.1.0** (feedstock updated 2026-05-31), while the version-matrix report confirms **1.1.1 released 2026-04-15**. So as of the last verification, conda-forge (the spine's CI channel, AD-11 + Environments) had *not* picked up 1.1.1 despite it being ~6 weeks old. The version-matrix report's "1.1.x (latest patch)" is therefore aspirational on the conda channel. The CI report itself flags release-lag monitoring as an open risk — the spine should carry that caveat. **Fix:** in AD-11 or the Stack table, note "CI pins the latest conda-forge-available patch (currently 1.1.0; 1.1.1 not yet on conda-forge as of last check) — track feedstock lag."

#### M-2. lib3mf pip platform coverage not verified

The 3MF report verified lib3mf exists (`pip install lib3mf`, v2.x, BSD, 3MF Consortium) but neither the report nor this review verified Windows/Linux wheel coverage for current Python versions. Since it's a mandatory 3MF oracle in AD-9, add wheel-availability to the Phase 0 pin checklist (no spine text change strictly required; a one-word "verify wheels" note in Deferred would do).

#### M-3. "1.2-dev weekly" canary naming vs research's own labeling

The version-matrix report describes the local checkout (weekly-2026.07.15, internal v26.3) as both "the 1.1 development line" and "heading toward 1.2". The spine commits to a "1.2-dev weekly" CI leg. Before wiring that leg, confirm what the weekly artifacts are actually published as on `FreeCAD/FreeCAD-Bundle` and conda channels (weekly builds are AppImage-first; a conda-forge "1.2-dev" package may not exist, forcing the canary leg onto AppImage instead of micromamba). Fold into the existing Phase 0 spike list.

### LOW

- **L-1. Client capability assumptions (elicitation/image rendering in Claude Code/Desktop):** research explicitly caveats that not all clients support elicitation or render image content; AD-10 already has fail-closed + fallback, so this is verified-and-mitigated — just ensure the Phase 0 smoke test exercises the fallback path against the actual pinned client.
- **L-2. Deferred LLM pin (llama.cpp + Qwen3-30B-A3B):** correctly deferred to the Phase 1 gate; both existed and were current per the 2026-07-20 report. Re-verify currency at the gate (model lines move fast); no spine change needed.
- **L-3. uv / pytest / micromamba rows:** all actively maintained, low drift risk, and pinned-at-Phase-0 by policy. No action.

## Verified clean (no action)

Traced to web-verified 2026-07-20 reports with primary sources: FreeCAD 1.0/1.1 release dates and additive API delta (blog.freecad.org + local source at weekly-2026.07.15); drop-0.21 rationale; conda-forge freecad availability across 5 platforms + micromamba action; MCP spec 2025-06-18 (elicitation, structured output) and 2025-11-25 (URL-mode elicitation, image content, tool-name validation — the "dots illegal" convention matches SEP-986); SSE deprecation; `FullyConstrained` as sketch pass signal; FreeCAD bug #6031 undo distrust; TNP element-map audit feasibility (`?`-markers, `FeatureDressUp` drop, `ElementMapVersion`); Mod/Web `postEvent` marshaling pattern (local source); RestrictedPython-is-not-a-boundary; nsjail/bubblewrap/AppContainer posture; dataset license traps (Onshape/DeepCAD/Fusion 360 Gallery); Wilson/McNemar statistics; skill token-budget findings.

## Summary of required spine edits

1. Stack: Python row → per-leg 3.11/3.12 (H-1).
2. Stack: MCP row → name exact package, note SDK v2 + 2026-07-28 spec landing at pin time (H-2).
3. Stack: admesh → dormant, CLI/Linux-only oracle with named fallback (H-3).
4. AD-11/Stack: conda-forge patch-lag caveat (M-1).
5. Deferred/spike list: lib3mf wheel check, 1.2-dev weekly channel check (M-2, M-3).
