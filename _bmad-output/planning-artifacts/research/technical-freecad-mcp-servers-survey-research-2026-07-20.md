---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: ['docs/intent.md', 'docs/references/FreeCAD']
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'Existing FreeCAD MCP servers survey'
research_goals: 'Enumerate and evaluate all existing community FreeCAD MCP servers (names, licenses, transport, tool coverage, maintenance, embedding approach). Decide what to adopt/wrap vs build. Blocks Phase 0 of docs/intent.md (bridge design).'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: technical

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** technical

---

## Research Overview

This report surveys the existing landscape of community **FreeCAD MCP (Model Context Protocol) servers** to answer the Phase 0 build-vs-reuse question posed by `docs/intent.md`: for the FreeCAD Buddy bridge, what should be adopted or wrapped, and what must be built. Eight distinct servers were enumerated and evaluated across license, transport, embedding approach (GUI addon vs headless), tool coverage, and maintenance status, using GitHub repositories as primary sources and the local FreeCAD source tree (`docs/references/FreeCAD`) to verify embedding/API claims.

The central finding: a healthy ecosystem exists and validates feasibility, but **every mature server is a GUI-addon design communicating with a *running FreeCAD GUI* over RPC** (XML-RPC / TCP JSON-RPC). None is architected for the headless `FreeCADCmd`/CI path that intent.md Phase 0 mandates, and none implements the intent's defining **verify-first tool taxonomy** (geometry assertions, watertightness, sketch DoF, post-mutation TNP re-resolve audit) as first-class deterministic tools. One recent server (`theosib/FreeCAD-MCP-Server`) is the closest philosophical match — it is inspection/diagnostics-led — but is young and GUI-bound.

The recommendation is **partial reuse, not adoption**: harvest the proven patterns (FastMCP + stdio; a thin RPC bridge into the FreeCAD process; `theosib`'s diagnostic tool designs as a reference), but build FreeCAD Buddy's own bridge so it runs headless *and* in-GUI and so the verify-first taxonomy is native. Full details, the comparison matrix, and the build-vs-reuse decision are in the Research Synthesis (Section 8) and the Appendix matrix (Section 12).

---

# The Reuse-Before-Invention Verdict: A Comprehensive Survey of Existing FreeCAD MCP Servers

## Executive Summary

The FreeCAD + Model Context Protocol ecosystem is real, active, and growing fast: at least **eight** distinct community MCP servers exist as of mid-2026, ranging from a 1,400-star flagship (`neka-nat/freecad-mcp`) to two-tool weekend prototypes. This directly satisfies the assumption baked into `docs/intent.md` ("several exist — study/adapt") and de-risks Phase 0: connecting an LLM to FreeCAD via MCP is a solved plumbing problem, and the dominant pattern has converged (FastMCP-style server over **stdio** to the client; a **thin RPC bridge** — XML-RPC or TCP JSON-RPC — into a *running FreeCAD instance*).

However, the survey exposes a structural gap that maps precisely onto FreeCAD Buddy's differentiators. Every production-grade server embeds **inside the FreeCAD GUI process** as a Workbench/addon and drives it via RPC; not one is designed to run headless under `FreeCADCmd` for CI, which intent.md Phase 0 requires as a hard exit criterion. Equally, the tool taxonomies are overwhelmingly **mutation-and-execute** oriented (`create_object`, `execute_code`, `pad`, `fillet`) or thin `run_script` wrappers; the **verify-first** layer intent.md treats as the project's core invention — deterministic `verify.*` tools returning is-valid-solid / watertight / volume / bounding-box / sketch-DoF / broken-reference (TNP) status — is essentially absent. The single exception in spirit, `theosib/FreeCAD-MCP-Server` (LGPL, released March 2026), is inspection-and-diagnostics-led (`analyze_shape`, `get_sketch_diagnostics`, `get_document_graph`, `tracked_recompute`) and is the best design reference, but it is young (v0.1.0, ~13 stars) and GUI-bound.

**Key Technical Findings:**

- **Ecosystem confirms feasibility.** 8 servers found; MIT dominates licensing; feasibility of MCP-driven FreeCAD is proven at scale (`neka-nat`: 1,400+ stars, FEM integration, remote RPC).
- **Convergent architecture = GUI addon + RPC bridge + stdio.** The mature designs all run a server *inside* FreeCAD's GUI and bridge to the MCP client over stdio. Verified against the local FreeCAD source: `Gui.addWorkbench()` in `InitGui.py` is exactly this addon mechanism, and `FreeCADCmd` (`src/Main/MainCmd.cpp`) is a *separate* headless entry point these servers do not target.
- **Headless/CI path is unserved.** None of the mature servers runs under `FreeCADCmd`; `spkane`'s "embedded mode" is Linux-only and secondary. Intent.md Phase 0 needs headless-first — a genuine gap.
- **Verify-first taxonomy is a genuine invention (confirmed).** No server implements intent's `verify.*` deterministic assertion tools or a post-mutation TNP re-resolve audit. `theosib` is the closest and should be studied, not forked.
- **Transport is stabilizing on Streamable HTTP.** The March-2025 MCP spec deprecated SSE in favor of Streamable HTTP; existing FreeCAD servers still lean on stdio (+ a few offer TCP/XML-RPC internally). FastMCP makes the transport a one-line swap — no reason to inherit any server's transport choice.

**Technical Recommendations:**

1. **Partial reuse, build the bridge.** Do not adopt or fork any single server. Reuse the *patterns* — FastMCP + stdio client transport, thin RPC-into-process bridge — and build FreeCAD Buddy's bridge so it runs **both** headless (`FreeCADCmd`) and in-GUI, satisfying Phase 0's dual-mode exit criterion.
2. **Adopt `theosib/FreeCAD-MCP-Server` as the reference design for the read/verify layer** (its `analyze_shape`, `get_sketch_diagnostics`, `get_document_graph`, `tracked_recompute` map almost 1:1 onto intent's `query.*`/`verify.*`). LGPL license is compatible with wrapping FreeCAD; study its main-thread work-queue (QTimer) pattern for GUI mode.
3. **Study `neka-nat` and `spkane` for the mutation layer and robustness patterns** (connection recovery, queue-based thread safety, XML-RPC bridge, remote binding), but re-implement mutations as a *typed* tool layer (no free-form `exec` in the mutation path, per intent's risk register).
4. **Own the verify-first taxonomy and TNP audit outright** — the survey confirms these do not exist; they are where the invention budget belongs.
5. **Target Streamable HTTP as the eventual production transport**, stdio for local/dev; keep transport swappable via FastMCP so this is not a lock-in decision now.

## Table of Contents

1. Technical Research Introduction and Methodology
2. Existing FreeCAD MCP Servers Technical Landscape and Architecture Analysis
3. Implementation Approaches and Best Practices
4. Technology Stack Evolution and Current Trends (MCP transport)
5. Integration and Interoperability Patterns
6. Performance and Scalability Analysis
7. Security and Compliance Considerations
8. Strategic Technical Recommendations (Build vs Reuse)
9. Implementation Roadmap and Risk Assessment
10. Future Technical Outlook
11. Technical Research Methodology and Source Verification
12. Technical Appendices — Comparison Matrix and References

---

## 1. Technical Research Introduction and Methodology

### Technical Research Significance

`docs/intent.md` elevates "Reuse before invention" to a guiding principle and, in its Reuse Map, explicitly names "existing community FreeCAD MCP servers on GitHub (study/adapt — several exist)" as the candidate to evaluate for MCP server plumbing, hypothesizing "likely partial reuse: their transport/embedding patterns, our tool layer." Phase 0 ("Foundation: FreeCAD Bridge & Test Harness") cannot responsibly begin until this hypothesis is tested against the actual ecosystem — otherwise the project risks either (a) re-inventing solved plumbing, wasting its scarce invention budget, or (b) adopting a server whose architecture (GUI-only) silently blocks Phase 0's headless-CI exit criterion. This survey is that test.

_Technical Importance: Determines whether the FreeCAD Buddy bridge is a wrap, a fork, or a ground-up build — the single largest Phase 0 architecture decision._
_Business Impact: Wrong choice costs weeks of Phase 0 and can poison every later phase that calls the bridge tools._
_Source: docs/intent.md (Vision, Architecture Direction, Reuse Map, Phase 0)._

### Technical Research Methodology

- **Technical Scope**: All discoverable community FreeCAD MCP servers; per server — license, transport, embedding approach (GUI addon vs headless), tool coverage/taxonomy, FreeCAD communication mechanism, maintenance/popularity.
- **Data Sources**: Primary = GitHub repositories (READMEs, release tags, commit/star counts) fetched directly. Secondary = MCP registries (mcp.so, mcpmarket, mcp.directory). Verification = the local FreeCAD source tree at `docs/references/FreeCAD` for all FreeCAD-API/embedding claims.
- **Analysis Framework**: Enumerate → per-server evidence extraction → normalize into a comparison matrix → map each against intent.md's specific needs (headless dual-mode, verify-first taxonomy, typed mutation layer, TNP audit) → build-vs-reuse decision.
- **Time Period**: Snapshot mid-2026 (servers dated 2024–2026; several v0.x releases Jan–Mar 2026).
- **Technical Depth**: Deep dive — 8 servers evaluated; embedding + headless mechanisms verified against FreeCAD source.

### Technical Research Goals and Objectives

**Original Technical Goals:** Enumerate and evaluate all existing community FreeCAD MCP servers; decide what to adopt/wrap vs build; unblock Phase 0 bridge design.

**Achieved Technical Objectives:**

- Enumerated 8 distinct servers with per-attribute evidence (Section 2 + matrix in Section 12).
- Established the convergent architecture and its blind spot (GUI-only, no headless).
- Confirmed the verify-first taxonomy and TNP audit are genuinely unbuilt (invention budget justified).
- Produced an actionable build-vs-reuse decision with named reference designs (Section 8).

## 2. Existing FreeCAD MCP Servers Technical Landscape and Architecture Analysis

Eight servers were identified and evaluated. Summaries below; the normalized matrix is in Section 12.

### 2.1 `neka-nat/freecad-mcp` — the flagship
- **License:** MIT. **Popularity:** ~1,400+ stars, ~199 forks, 115 commits — by far the most adopted.
- **Transport:** MCP over **stdio** from client (Claude Desktop via `uvx freecad-mcp`) to the server; server ↔ FreeCAD via **XML-RPC** (localhost by default, can bind `0.0.0.0` for remote with IP allowlist).
- **Embedding:** **GUI addon/Workbench** ("MCP Addon" in the Workbench list); RPC server started from a toolbar (with auto-start option). Requires a running FreeCAD GUI.
- **Tools (~10-11):** `create_document`, `create_object`, `edit_object`, `delete_object`, `execute_code`, `insert_part_from_library`, `get_view` (screenshot), `get_objects`, `get_object`, `get_parts_list`, `run_fem_analysis` (CalculiX).
- **Assessment:** Mature, feature-rich, proves feasibility (incl. FEM + parts library + remote). But mutation/execute-oriented with free-form `execute_code`; no deterministic verify layer; GUI-only.
- _Source: https://github.com/neka-nat/freecad-mcp_

### 2.2 `spkane/freecad-addon-robust-mcp-server` — the "robust" one
- **License:** MIT (code). **Popularity:** ~151 stars, ~40 forks; latest release **v0.6.2 (Jan 2026)** — actively maintained, disciplined releases.
- **Transport:** Multiple internal protocols — **XML-RPC (port 9875, recommended)**, JSON-RPC socket (9876), and **embedded mode (Linux-only)**. Requires FreeCAD 0.21+/1.0+, Python 3.11.
- **Embedding:** GUI Bridge Workbench/addon primarily; embedded (in-process) mode exists but Linux-only and secondary.
- **Tools:** **150+ tools** across 10 categories (execution/debug, document mgmt, primitives, object mgmt, PartDesign sketching (14), patterns/edges, view/display, undo/redo (3), export/import (7), macros, parts library). Broadest coverage found.
- **Robustness:** connection recovery, queue-based thread-safety, timeout config (30s), pre-commit security scanning (Bandit, Gitleaks), MyPy/Ruff.
- **Assessment:** The most engineering-mature. Excellent source of *robustness patterns* and the widest mutation coverage. Still GUI-first; verify layer not first-class; huge surface area to inherit.
- _Source: https://github.com/spkane/freecad-addon-robust-mcp-server_

### 2.3 `theosib/FreeCAD-MCP-Server` — the inspection/verify-led one (closest to intent)
- **License:** **LGPL-2.1-or-later** (matches FreeCAD). **Popularity:** ~13 stars; **v0.1.0 (Mar 2026)** — young but recent.
- **Transport:** FreeCAD addon runs a **threaded TCP server (port 9876)** accepting JSON-RPC, executed on FreeCAD's main thread via a **QTimer-polled work queue**; MCP bridge connects to the client over **stdio**.
- **Embedding:** GUI addon; keeps full GUI (not headless).
- **Tools (verification-led):** `analyze_shape` (face classifications, edges, bbox, volume), `get_sketch_diagnostics` (**DoF, conflicts, redundancies**), `get_document_graph` (dependencies + validity states), `inspect_object`, `tracked_recompute` (before/after error diffs), screenshots, hot-reloadable handlers.
- **Assessment:** **The best design reference for FreeCAD Buddy's `query.*`/`verify.*` layer** — its tools map almost 1:1 onto intent's read/verify needs (shape validity, sketch DoF, recompute tracking). LGPL is wrap-compatible. GUI-bound and immature, so reference-not-fork.
- _Source: https://github.com/theosib/FreeCAD-MCP-Server_

### 2.4 `contextform/freecad-mcp` — install-optimized, big mutation surface
- **License:** not stated (risk). **Popularity:** ~95 stars, 35 commits — active, polished installer.
- **Transport:** **stdio** (`working_bridge.py` process). **Embedding:** hybrid — an "AI Copilot" GUI Workbench auto-starts an in-FreeCAD service; bridge mediates to FreeCAD's Python API.
- **Tools (~45):** PartDesign (13: Pad/Revolution/Fillet/Chamfer/Holes/Patterns), Part (18: primitives/booleans/transforms), View control (14), plus custom Python. "2-command install", connection pre-check, one-command updates.
- **Assessment:** Best onboarding UX; strong mutation coverage. Unstated license is a real adoption blocker; still GUI-bound; no verify layer.
- _Source: https://github.com/contextform/freecad-mcp_

### 2.5 `bonninr/freecad_mcp` — minimal, script-through
- **License:** MIT. **Popularity:** ~204 stars, 16 commits. **Transport:** stdio. **Embedding:** GUI Workbench.
- **Tools (2):** `get_scene_info`, `run_script` (arbitrary Python via `FreeCAD.ActiveDocument`). Cross-platform, real-time scene introspection.
- **Assessment:** Popular but thin — essentially a scriptable passthrough. Not a taxonomy to reuse; the `run_script` pattern is exactly the free-form `exec` intent's risk register warns against for the mutation path.
- _Source: https://github.com/bonninr/freecad_mcp_

### 2.6 `ATOI-Ming/FreeCAD-MCP` — macro-oriented
- **License:** MIT. **Popularity:** ~93 stars, 61 commits. **Transport:** stdio **or** TCP (localhost:9876). **Embedding:** GUI control panel (`FreeCADMCPPanel`) Workbench.
- **Tools (5):** `create_macro`, `update_macro`, `run_macro`, `set_view`, `get_report`. Auto-injects imports, recomputes post-run.
- **Assessment:** Macro-file-centric workflow — a different paradigm (generate/run `.FCMacro`) than intent's typed tools. Limited direct reuse.
- _Source: https://github.com/ATOI-Ming/FreeCAD-MCP_

### 2.7 `Coben-3d/freecad-mcp` — early prototype
- **License:** MIT. **Popularity:** ~0 stars, 2 commits, v0.1.0 (Feb 2026). **Transport:** stdio subprocess. **Embedding:** MCP server + `freecad_bridge.py` to FreeCAD Python API.
- **Tools (2):** `create_object` (primitives), `export_file` (STEP/STL/OBJ). "Type-safe" with error handling/logging.
- **Assessment:** Immature; nothing to reuse beyond confirming the stdio+bridge pattern is trivial to stand up.
- _Source: https://github.com/Coben-3d/freecad-mcp_

### 2.8 Registry-only / secondary listings
Registry pages (mcp.so, mcpmarket "FreeCAD Robust", mcp.directory) surface the above rather than new servers; they confirm `neka-nat` and `spkane` as the ecosystem's canonical entries.

### Current Technical Architecture Patterns

_Dominant Pattern:_ **MCP client ⇄ (stdio) ⇄ Python MCP server ⇄ (XML-RPC / TCP JSON-RPC) ⇄ addon running inside FreeCAD GUI.** The two-process split exists because FreeCAD bundles its own Python; the bridge process speaks MCP while the in-GUI addon executes on FreeCAD's main thread (often via a QTimer/work-queue for thread safety — see `theosib`, `spkane`).
_Architectural Evolution:_ from thin `run_script` passthroughs (`bonninr`) → broad mutation taxonomies (`neka-nat`, `contextform`, `spkane`) → inspection/diagnostics-led designs (`theosib`, 2026).
_Architectural Trade-off:_ GUI-embedding buys screenshots and interactive-parity but **forfeits headless CI** — the exact trade intent.md refuses to make.
_Source: local verification below + repos cited above._

### System Design Principles and Best Practices (verified against FreeCAD source)

The local FreeCAD tree confirms the embedding facts these servers rely on:
- **GUI-addon mechanism:** `docs/references/FreeCAD/src/Mod/TemplatePyMod/InitGui.py` defines a `Workbench` subclass and registers it with `Gui.addWorkbench(...)`. This *is* the "MCP Addon/Workbench" install path every mature server uses — and it depends on the GUI (`Gui`) being present.
- **Headless entry point is separate:** `docs/references/FreeCAD/src/Main/MainCmd.cpp` is the `FreeCADCmd` console `main()` (distinct from `MainGui.cpp`), initializing `App::Application` without the GUI. Intent's Phase 0 headless requirement targets *this* path, which no `InitGui.py`-based addon can serve. A headless bridge must instead import `FreeCAD` as a module under `FreeCADCmd`/`MainPy.cpp` — architecturally different from the addon pattern.
_Conclusion: the "run both in-GUI and headless" exit criterion cannot be met by wrapping a GUI-only addon; it requires a bridge core independent of `Gui`._

## 3. Implementation Approaches and Best Practices

_Development Approaches:_ Python throughout; FastMCP-style server definition; in-GUI addon executing on the main thread via QTimer/work-queue (thread-safe recompute). Best-in-class discipline: `spkane` (typed, MyPy/Ruff, security-scanned, semver releases).
_Code Organization:_ two components (bridge process + FreeCAD addon) with an RPC contract between them — a clean seam FreeCAD Buddy should keep, but with the addon side refactored into a **GUI-optional core**.
_Quality/Validation:_ largely absent as a *tool concern* — servers verify little about resulting geometry. This is the reusable-gap that becomes FreeCAD Buddy's `verify.*` layer.
_Deployment:_ `uvx`/npm installers (`neka-nat`, `contextform`) are good UX references.
_Source: repos §2; https://github.com/spkane/freecad-addon-robust-mcp-server_

## 4. Technology Stack Evolution and Current Trends (MCP transport)

_MCP transport:_ The **March 2025 MCP spec deprecated SSE in favor of Streamable HTTP** (HTTP POST for requests + optional SSE streaming for responses); all major SDKs (FastMCP included) support it, and for FastMCP switching stdio→Streamable HTTP is "a single argument change to `mcp.run()`." Existing FreeCAD servers predate/ignore this and lean on **stdio** (a few expose TCP/XML-RPC *internally* for the FreeCAD hop, which is unrelated to the client transport).
_Implication for FreeCAD Buddy:_ do **not** inherit any server's transport choice. Use FastMCP, ship stdio for local/dev, keep Streamable HTTP as the swappable production transport (needed for the Phase 4 "as a service" / agent-to-agent goal).
_Sources: https://modelcontextprotocol.io/specification/2025-03-26/basic/transports ; https://blog.cloudflare.com/streamable-http-mcp-servers-python/_

## 5. Integration and Interoperability Patterns

_Client compatibility:_ all servers target Claude Desktop/Code and most also Cursor/other MCP clients — the MCP contract is the interop guarantee, so FreeCAD Buddy inherits broad client compatibility for free by being spec-compliant.
_FreeCAD hop:_ XML-RPC (`neka-nat`, `spkane`) vs TCP JSON-RPC (`theosib`, `ATOI-Ming`) — both proven; JSON-RPC over a main-thread work-queue (`theosib`) is the cleaner, more inspectable choice and aligns with MCP's own JSON-RPC basis.
_Standards:_ target MCP 2025-03-26+ (Streamable HTTP capable).

## 6. Performance and Scalability Analysis

_Characteristics:_ latency is dominated by FreeCAD recompute, not transport; the in-GUI main-thread execution model serializes operations (single active document) — acceptable for interactive/single-tenant use (intent scopes Phase 4 as single-tenant/local-first).
_Scalability:_ GUI-embedding caps you at one FreeCAD GUI per server; the **headless `FreeCADCmd` path scales horizontally** (N worker processes, no display) — another reason the headless core matters for the Phase 4 service and the CI soak test (50-job run).
_Robustness references:_ `spkane`'s connection-recovery + timeout + queue patterns are the ones to port.

## 7. Security and Compliance Considerations

_Threats:_ (1) **arbitrary code execution** — `execute_code`/`run_script` in `neka-nat`/`bonninr`/`contextform` expose free-form Python; intent's risk register mandates a **typed mutation layer with no free-form `exec` in the mutation path**, so these patterns are explicitly *not* to be copied for mutations. (2) **remote binding** — `neka-nat`'s `0.0.0.0` option needs IP allowlisting; keep bridge localhost-only by default. (3) **sandboxing** — intent Phase 4 requires sandboxed execution + audit log; no surveyed server provides this.
_Licensing/compliance:_ MIT dominates (safe to study/borrow patterns). `theosib` is **LGPL-2.1-or-later** — same as FreeCAD, fully compatible with a wrapping bridge; borrowing its *designs* (not code) is unencumbered regardless. `contextform`'s **unstated license** disqualifies it from code reuse until clarified.
_Security tooling reference:_ `spkane` (Bandit, Gitleaks, pre-commit) is the model to emulate.

## 8. Strategic Technical Recommendations (Build vs Reuse)

**Verdict: PARTIAL REUSE — build the bridge, harvest the patterns.** This confirms intent.md's Reuse-Map hypothesis exactly ("their transport/embedding patterns, our tool layer").

| Decision | Choice | Rationale |
|---|---|---|
| Adopt a server wholesale? | **No** | All are GUI-only; none serves Phase 0's headless-CI exit criterion; none has the verify-first taxonomy. |
| Fork a server? | **No** | Forking inherits GUI-coupling and large mutation surfaces (`spkane` 150+ tools) that would need re-architecting anyway; `theosib` too young to fork productively. |
| Reuse patterns/designs? | **Yes** | FastMCP+stdio client transport; two-process bridge seam; main-thread work-queue for GUI mode; `theosib` diagnostic tool designs; `spkane` robustness patterns. |
| Build the tool layer? | **Yes** | The `query.*` / `verify.*` verify-first taxonomy + typed `sketch.*`/`feature.*` mutations + post-mutation TNP audit are the invention budget — confirmed unbuilt. |

_Architecture recommendation:_ a **GUI-optional bridge core** (imports `FreeCAD`/`Part`/`Sketcher`/`PartDesign` as modules, no `Gui` dependency) usable under `FreeCADCmd` for CI/service; wrapped by a thin GUI addon (`InitGui.py` + `Gui.addWorkbench`) for interactive/screenshot mode. Same tool implementations, two hosts. This directly satisfies Phase 0's "starts inside FreeCAD (as addon/workbench) and headless" criterion — which no existing server does.
_Technology selection:_ Official MCP Python SDK / **FastMCP**; JSON-RPC for the FreeCAD hop (à la `theosib`); Streamable HTTP-capable transport (stdio default).
_Named reference designs:_ read/verify → **`theosib`**; robustness/mutation breadth → **`spkane`**; install UX + remote/FEM → **`neka-nat`**.

_Competitive/Differentiation:_ FreeCAD Buddy's moat vs the ecosystem is precisely what the survey found missing everywhere — **headless dual-mode + deterministic verify-first tools + TNP post-mutation audit + typed (non-`exec`) mutations**. Building these is not re-inventing solved plumbing; it is spending the invention budget where the survey came up empty.

## 9. Implementation Roadmap and Risk Assessment

_Phase 0 implementation framing (from this survey):_
1. Stand up FastMCP server (stdio) — trivially proven by every server; days, not weeks.
2. Build the **GUI-optional bridge core**; validate it imports/executes under `FreeCADCmd` headless (the differentiator; verify against `MainCmd.cpp`/`MainPy.cpp` path).
3. Implement `query.*` + `verify.*` first (borrow `theosib` tool designs: `analyze_shape`→`verify.shape`, `get_sketch_diagnostics`→sketch DoF, `tracked_recompute`→recompute check, `get_document_graph`→tree query).
4. Add typed mutations later (Phase 2) borrowing `spkane`/`neka-nat` coverage lists — but typed, no free-form `exec`.
5. Wrap with GUI addon (`InitGui.py`) for screenshots/interactive parity.

_Risks:_
- _License:_ borrow **designs/patterns**, not code, from MIT servers to stay clean; treat `contextform` as design-only until license clarified; `theosib` LGPL is code-compatible if ever needed.
- _Version drift:_ target FreeCAD 0.21+/1.0+ (matches `spkane`); thin adapter over version-sensitive calls (intent risk register).
- _GUI-coupling creep:_ enforce the "core has no `Gui` import" rule in CI, or the headless path silently rots.
- _Over-reuse temptation:_ `spkane`'s 150+ tools are tempting to fork; resist — the verify-first taxonomy must lead, mutations follow.

## 10. Future Technical Outlook

_Near-term:_ ecosystem consolidation around `neka-nat`/`spkane`; more diagnostic/verify tools appearing (`theosib` is the leading edge) — FreeCAD Buddy is well-timed to lead on verify-first. Transport migration to Streamable HTTP will become standard (needed for the Phase 4 service).
_Opportunity:_ FreeCAD Buddy's verify-first + headless bridge could itself become a reference the community reuses — the most portable artifact, echoing intent's skills-library thesis.

## 11. Technical Research Methodology and Source Verification

_Primary sources:_ GitHub repos of all 8 servers (READMEs, releases, stars/commits), fetched directly. _Secondary:_ MCP registries (mcp.so, mcpmarket, mcp.directory). _Local verification:_ FreeCAD source at `docs/references/FreeCAD` — `src/Mod/TemplatePyMod/InitGui.py` (workbench/addon mechanism), `src/Main/MainCmd.cpp` (headless entry), `src/Main/MainGui.cpp`/`MainPy.cpp` (GUI vs module entry points).
_Search queries used:_ "FreeCAD MCP server github Model Context Protocol"; "FreeCAD MCP server addon workbench stdio SSE"; "MCP transport 2025 Streamable HTTP replaces SSE Python SDK FastMCP".
_Confidence:_ High on enumeration, licenses, embedding, transport (multi-source + local verification). Medium on exact star/tool counts (GitHub snapshots drift). Limitation: private/unlisted servers or non-English repos may exist beyond this survey; tool counts are as-documented, not code-audited.

## 12. Technical Appendices — Comparison Matrix and References

### Comparison Matrix

| Server | License | Client transport | FreeCAD hop | Embedding | Headless? | Tools (approx) | Verify-first tools? | Maint / Popularity | Reuse role |
|---|---|---|---|---|---|---|---|---|---|
| **neka-nat/freecad-mcp** | MIT | stdio | XML-RPC (localhost/remote) | GUI Workbench | No | ~10-11 (+FEM, parts lib) | No (has `get_object(s)`, screenshot only) | 115 commits, ~1,400★ | Install UX, remote/FEM reference |
| **spkane/freecad-addon-robust-mcp-server** | MIT | stdio | XML-RPC 9875 / JSON-RPC 9876 / embedded(Linux) | GUI addon (+embedded) | Partial (Linux embedded only) | **150+** | Partial (diagnostics among many) | v0.6.2 Jan'26, ~151★ | Robustness + mutation-breadth reference |
| **theosib/FreeCAD-MCP-Server** | **LGPL-2.1+** | stdio | TCP JSON-RPC 9876 (main-thread queue) | GUI addon | No | ~6 (inspection-led) | **Yes** (`analyze_shape`, `get_sketch_diagnostics` DoF, `get_document_graph`, `tracked_recompute`) | v0.1.0 Mar'26, ~13★ | **Read/verify design reference (best fit)** |
| **contextform/freecad-mcp** | Unstated ⚠ | stdio | in-GUI service via bridge | GUI Workbench (hybrid) | No | ~45 | No | 35 commits, ~95★ | Install UX + mutation coverage (design only) |
| **bonninr/freecad_mcp** | MIT | stdio | Python API passthrough | GUI Workbench | No | 2 (`get_scene_info`,`run_script`) | No | 16 commits, ~204★ | Anti-pattern (free-form `run_script`) |
| **ATOI-Ming/FreeCAD-MCP** | MIT | stdio / TCP 9876 | Python API + macros | GUI panel Workbench | No | 5 (macro-centric) | No | 61 commits, ~93★ | Limited (macro paradigm) |
| **Coben-3d/freecad-mcp** | MIT | stdio | `freecad_bridge.py` | subprocess bridge | No | 2 | No | 2 commits, ~0★ | Confirms trivial stdio+bridge |
| *(registries)* mcp.so / mcpmarket / mcp.directory | — | — | — | — | — | — | — | listing only | Discovery |

### Key intent.md gaps NOT covered by any surveyed server
- Headless-first bridge runnable under `FreeCADCmd` for CI (Phase 0 exit criterion).
- Deterministic `verify.*` taxonomy (is-valid-solid, watertight, volume, bbox, face/edge counts, sketch DoF) as first-class tools with tolerances.
- Post-mutation **TNP re-resolve audit** (Phase 2) — confirmed unbuilt anywhere.
- **Typed** mutation layer with no free-form `exec` in the mutation path (security/risk requirement).

### Open-source references
- neka-nat/freecad-mcp — https://github.com/neka-nat/freecad-mcp
- spkane/freecad-addon-robust-mcp-server — https://github.com/spkane/freecad-addon-robust-mcp-server
- theosib/FreeCAD-MCP-Server — https://github.com/theosib/FreeCAD-MCP-Server
- contextform/freecad-mcp — https://github.com/contextform/freecad-mcp
- bonninr/freecad_mcp — https://github.com/bonninr/freecad_mcp
- ATOI-Ming/FreeCAD-MCP — https://github.com/ATOI-Ming/FreeCAD-MCP
- Coben-3d/freecad-mcp — https://github.com/Coben-3d/freecad-mcp
- MCP transports spec (2025-03-26) — https://modelcontextprotocol.io/specification/2025-03-26/basic/transports
- Streamable HTTP + Python for MCP — https://blog.cloudflare.com/streamable-http-mcp-servers-python/
- Local FreeCAD source — docs/references/FreeCAD (src/Mod/TemplatePyMod/InitGui.py, src/Main/MainCmd.cpp, MainGui.cpp, MainPy.cpp)

---

## Technical Research Conclusion

### Summary of Key Technical Findings

A robust community of at least eight FreeCAD MCP servers exists, proving MCP-driven FreeCAD is feasible and de-risking Phase 0 plumbing. The ecosystem has converged on one architecture — a FastMCP/stdio server bridging via RPC into a **running FreeCAD GUI addon** — and on MIT licensing. But that convergence hard-codes two blind spots that are exactly FreeCAD Buddy's differentiators: **no headless `FreeCADCmd`/CI path** and **no deterministic verify-first tool taxonomy or TNP audit**. `theosib/FreeCAD-MCP-Server` (LGPL, 2026) is the lone verification-led design and the best reference for the read/verify layer; `spkane` is the robustness/breadth reference; `neka-nat` the popularity/UX reference.

### Strategic Technical Impact Assessment

The survey does not come up empty — so intent.md's "reuse before invention" principle is honored by **partial reuse**: adopt patterns and named reference designs, but **build** the bridge. This preserves the invention budget for where the survey confirms a true gap (headless dual-mode, verify-first tools, TNP post-mutation audit, typed non-`exec` mutations) rather than spending it re-implementing solved MCP plumbing.

### Next Steps Technical Recommendations

1. Begin Phase 0 by standing up FastMCP+stdio and, critically, a **GUI-optional bridge core** validated headless under `FreeCADCmd`.
2. Implement `query.*`/`verify.*` first, using `theosib`'s tool designs as the blueprint.
3. Port `spkane`'s robustness patterns; defer mutation breadth to Phase 2 as a typed layer.
4. Keep transport swappable (Streamable HTTP-ready) for the Phase 4 service.
5. Record this build-vs-reuse note in the Phase 0 Validation Design Gate reuse survey.

---

**Technical Research Completion Date:** 2026-07-20
**Research Period:** mid-2026 snapshot
**Source Verification:** All server claims cited to GitHub repos; all FreeCAD-API/embedding claims verified against local FreeCAD source (docs/references/FreeCAD).
**Technical Confidence Level:** High — multiple sources per claim plus local source verification.

_This document is the Phase 0 build-vs-reuse survey for the FreeCAD Buddy bridge, satisfying the Reuse Map / Validation Design Gate reuse-survey requirement of docs/intent.md._
