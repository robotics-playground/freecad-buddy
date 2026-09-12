# Review — Doc vs Code Reality Drift

Scope: `ARCHITECTURE-SPINE.md` (dated 2026-07-21) against the installed code tree.
Rule applied: **the installed CODE wins over any document — verify, then propose a doc correction.**

Verdict summary: the spine's **invariants (AD-1..AD-23) hold in code**. The drift is concentrated
in the **descriptive sections** — Structural Seed tree, Stack table, and the Design Paradigm ring
table — which describe a 2026-07-21 plan the code has moved past.

Totals: 12 findings. 0 CRITICAL. 4 HIGH, 5 MEDIUM, 3 LOW.
Code violates architecture in **0** findings. Doc needs amendment in **11**. 1 is a code cleanup
(dead exemption).

---

## Findings

| Severity | Doc anchor | Code anchor (file:line) | What doc says | What code does | Suggested fix |
| --- | --- | --- | --- | --- | --- |
| HIGH | Structural Seed, spine:294 | `src/freecad_buddy/adapters/` (no such file) | `adapters/     # mcp_server, rpc_listener, marshal, skills_loader, harness glue` | No `skills_loader` exists anywhere in the repo. `grep -rln 'skills_loader\|skill_loader\|SkillLoader' src/ scripts/ benchmarks/ tests/` returns nothing. `skills/` (15 dirs) is agent-consumed markdown, never imported by code. Also no "harness glue" in adapters — the harness lives in `benchmarks/harness/`. | **Amend doc.** CODE is right. Replace the seed line with the real inventory: `adapters/  # mcp_server, rpc_client, rpc_listener, rpc_dispatch, marshal, render_probe, audit_log, export_oracle, export_verdict, react_adapter`. Note AD-15's loader is an unbuilt Phase-1 item, not a shipped adapter. |
| HIGH | Structural Seed, spine:295 | `src/freecad_buddy/hosts/` tree | `hosts/        # InitGui.py (addon), headless entry, phase4 supervisor` | Three-way split: `hosts/gui_addon/{InitGui.py,bootstrap.py,pump.py}`, `hosts/gui_external/entry.py`, `hosts/headless/entry.py`, plus `hosts/main.py` (CLI) and `hosts/tool_catalog.py` (1,397 lines — the shared tool surface). **No phase4 supervisor exists** (`grep -rln 'supervisor\|Supervisor' src/` → empty). `gui_external/` is a whole host the doc never names. | **Amend doc.** CODE is right. Seed must list `gui_addon/`, `gui_external/`, `headless/`, `main.py`, `tool_catalog.py`; mark the Phase-4 supervisor as not-yet-built. |
| HIGH | Design Paradigm ring table, spine:29 | `hosts/tool_catalog.py:995` `def tool_specs() -> list[ToolSpec]:` | Hosts ring "Contains: GUI addon (`InitGui.py`), headless entry, Phase 4 supervisor" | `hosts/tool_catalog.py` is the single **shared** tool-surface definition (schemas, timeouts, mutating flags, audit events) consumed by all three hosts. It is the largest module in the package and has no place in the doc's ring table, which implies the tool surface lives in adapters. | **Amend doc.** CODE is right and the placement is sound (hosts is the only ring that may see all three host wirings). Add "shared tool catalog (schemas + registry construction)" to the Hosts row. |
| HIGH | Stack table, spine:248 | `pyproject.toml:11` `"mcp>=1.28,<2",  # official MCP python-sdk (NOT PrefectHQ fastmcp)` | "SDK v2 (`FastMCP`→`MCPServer` rename) lands ~2026-07-27 — **pin exact at Phase 0** after v2 stabilizes. PrefectHQ `fastmcp` is a distinct project; the choice between the two is a **Phase 0 call**" | Both open questions are **closed**: official `mcp` python-sdk chosen, range-pinned `>=1.28,<2` (v1 line, cap below the v2 rename). Decided in `docs/decisions/005-mcp-sdk-pin.md`. Further, the code uses the **low-level** `mcp.server.lowlevel.Server` (`adapters/mcp_server.py:170` `@server.list_tools()`), **not FastMCP** — yet the spine says "one FastMCP server object" (AD-3, spine:61) and "FastMCP server + tool registry" (Structural Seed mermaid, spine:270). | **Amend doc.** CODE is right. Replace the Stack row with the closed pin, and replace every "FastMCP" mention in AD-3 and the seed mermaid with "the MCP python-sdk low-level `Server`". The FastMCP wording is now factually wrong about the code. |
| MEDIUM | Stack table, spine:249 | `pyproject.toml:12-13` `"trimesh==4.*"`, `"lib3mf==2.*"` | "trimesh, lib3mf | current at Phase 0 pin — export oracles" | Pinned to major-version ranges `4.*` / `2.*`. | **Amend doc.** CODE is right. Record the actual pins in the Stack table so the table stops saying "at Phase 0 pin" for a pin that already landed. |
| MEDIUM | Stack table (absent rows) | `pyproject.toml:17,22` `dev = ["pytest>=8", "ruff>=0.5", "jsonschema>=4", "pyyaml>=6"]` and `react-local = ["openai>=1"]` | Stack table lists `pytest` ("current") and `uv`, and no other external deps. | Four dependencies present in code but **absent from the Stack table**: `ruff>=0.5` (the lint/print-ban gate, run in CI at `.github/workflows/ci.yml:65`), `jsonschema>=4` (schema drift check), `pyyaml>=6` (external harness only), `openai>=1` (optional ReAct-eval transport, decision 011). `pytest` is now pinned `>=8`, not "current". | **Amend doc.** CODE is right. Add rows for ruff, jsonschema, pyyaml, and optional openai; change the pytest row to `>=8`. |
| MEDIUM | Structural Seed, spine:298 | `tests/infc/` (23 files) and `tests/external/` (29 files); `pyproject.toml:37` `testpaths = ["tests/external"]` | `tests/          # unit + golden-model suites (run via FreeCADCmd in CI)` — one world, all under FreeCADCmd. | **Two separate worlds that never mix.** `tests/infc/` runs under `FreeCADCmd tests/run_tests.py` with stdlib `unittest` (AD-12 posture); `tests/external/` runs under pytest in the uv env and is the **default** pytest collection target — a bare `pytest` must not collect `infc/`. CI runs them as distinct steps (`ci.yml:97` FreeCADCmd; `ci.yml:100` pytest). | **Amend doc.** CODE is right; the split is the correct expression of AD-12 and of the Consistency Convention at spine:238 ("Tests under FreeCADCmd: stdlib `unittest` only; pytest orchestrates from the external process"). The seed line contradicts a convention the same document states. Replace with `tests/infc/` + `tests/external/`. |
| MEDIUM | Structural Seed, spine:297 | `benchmarks/` tree | `benchmarks/   # specs + assertions; dev/ and heldout/ splits; fault-injection/` | Organized **per gate**, not as a flat dev/heldout split: `benchmarks/g0/`, `g1/`, `g2/` each carry their own `gate.yaml`, `dev/`, `heldout/`, `fault-injection/`; plus top-level `runner.py`, `harness/` (9 modules incl. `seal.py`, `verdict.py`, `evidence.py`), `_registry/` (`validators.yaml` + `provenance/`), `gate-artifacts/`. | **Amend doc.** CODE is right — the per-gate layout is what AD-19 (gate ordering) and AD-13 (per-validator fault injection) actually require. Update the seed line. |
| MEDIUM | AD-15, spine:157 | `scripts/` listing; `.github/workflows/ci.yml` | "One skill store (`SKILL.md` body ≤1,500 words, **CI-enforced**…)" | **No skill-shape check exists.** `scripts/` holds `check_imports.py`, `check_provenance.py`, `check_status_vocab.py`, `gen_schemas.py`, `build_addon.py` — no `check_skill_shape.py`, and `ci.yml` runs no skill check. (Note: the repo `CLAUDE.md` §12 also names a `check_skill_shape` script that does not exist.) The invariant currently holds by luck: all 15 `SKILL.md` bodies measure 876–1,186 words, comfortably under the cap. | **Fix code (or downgrade the doc claim).** DOC is right about the intent; the "CI-enforced" clause is presently false. Either add `scripts/check_skill_shape.py` + a CI step, or amend AD-15 to say the cap is currently a convention with an enforcer pending. Recommend the former — AD-15's whole purpose is preventing context rot, and a cap nobody measures drifts silently. |
| LOW | AD-1, spine:45 | `scripts/check_imports.py:79` `QT_EXEMPT_ADAPTERS = frozenset({"adapters/marshal.py", "adapters/render_probe.py"})` vs `adapters/marshal.py:13-14` (only `import threading`, `from typing import ...`) | "two named `adapters/` exemptions: the render capability probe, and the **main-thread marshal** (QtCore primitives only)" | Only **one** exemption is live. `render_probe.py` genuinely imports Qt (`render_probe.py:60 import FreeCADGui`, `:124 from PySide import QtGui`, `:150 import FreeCADGui`). `marshal.py` imports **no Qt at all** — the Qt pump was extracted to `hosts/gui_addon/pump.py:13 from PySide import QtCore`. The marshal docstring still claims "QtCore may be imported here… inside functions at call time", which the module no longer does. The enforcer's `marshal.py` exemption is therefore dead, and `tests/external/test_check_imports.py:32` keeps it alive by asserting on a synthetic `adapters/marshal.py` fixture. | **Both, small.** CODE improved on the doc: moving Qt entirely out of adapters is *stricter* than AD-1 requires. Amend AD-1 to a **single** named exemption (render probe), and remove the now-dead `adapters/marshal.py` entry from `QT_EXEMPT_ADAPTERS` plus its test fixture. Also fix the stale `marshal.py` docstring. Leaving a dead exemption open is a standing hole for a future Qt import to slip through unnoticed. |
| LOW | Consistency Conventions, spine:229 | `hosts/tool_catalog.py:1341-1344` `for leg_name, leg_fn in (("export_self_read_stl", exports.export_self_read_stl), ("export_self_read_3mf", exports.export_self_read_3mf),)` … `internal=True` | Tool-name namespace prefixes: `query_`, `document_`, `export_`, `verify_`, `sketch_`, `feature_`, `preview_`, `debug_`. | Two names exist in the registry that appear in **no** design doc: `export_self_read_stl` / `export_self_read_3mf`. They carry the legal `export_` prefix but are **RPC methods only, never MCP tools** (`internal=True`), because the third-party oracles must run outside FreeCAD (AD-9/AD-12). They correctly do **not** reach the MCP surface — the live `mcp__freecad-buddy__*` list has 40 tools and neither appears. | **Amend doc.** CODE is right and the comment at `tool_catalog.py:1340` explains why. Add a line to the conventions table (or the MCP Tool Catalog Design) recording that the registry carries `internal=True` RPC-only methods which are deliberately not MCP tools. |
| LOW | Capability Map, spine:313 | `src/freecad_buddy/hosts/` (no supervisor); `usecases/stats.py:1` `"""FreeCAD-free rate statistics for validator scoring."""` | "Phase 4 service | hosts/phase4 supervisor"; AD-14 stats module is designed as harness-side. | No `hosts/phase4/` exists — correct, Phase 4 is unbuilt. Separately, the AD-14 Wilson/rate statistics live at `usecases/stats.py`, not in the harness — a placement the spine's ring table does not anticipate (the Use-cases row lists only tool implementations, mutation protocol, TNP guard, fingerprint). The file is deliberately FreeCAD-free so it imports under pytest without FreeCAD. | **Amend doc.** CODE is right (a stdlib-only pure function in `usecases/` satisfies AD-1 trivially, and both the in-FreeCAD and external sides can call it). Add `stats` to the Use-cases ring row; mark the Phase-4 supervisor Capability-Map row as not-yet-implemented. |

---

## Invariants verified clean (no drift)

These were checked against code and found to match the spine. Recorded so a later reader does not
re-check them.

**AD-17 — closed status set. CLEAN, and machine-enforced.**
`contracts/status.py:11-19` defines exactly the seven spine values:

```python
TerminalStatus = Literal[
    "OK", "SPEC_FAILED", "RECOMPUTE_ERROR", "TIMEOUT",
    "OOM_KILLED", "WORKER_CRASHED", "INVALID_INPUT",
]
```

No value outside the set was found. Stronger than the doc promises: `scripts/check_status_vocab.py`
AST-scans the whole package and fails CI on any `Literal[...]` outside `contracts/status.py` whose
members intersect the set — and derives the set at runtime from `contracts.status`, so the enforcer
cannot drift from the source. Wired at `ci.yml:15`. `contracts/rpc.py:24` maps RPC error codes
*into* the set (`RPC_ERROR_WORKER_CRASHED: "WORKER_CRASHED"`) rather than inventing new ones.
**Suggested spine addition:** AD-17 should mention the enforcer — it is the reason this invariant
has not rotted.

**AD-12 — in-FreeCAD code is dependency-free. CLEAN.**
Grep for `mcp|trimesh|pydantic|lib3mf|requests|numpy|yaml|openai|pytest` across `usecases/`,
`adapters/rpc_listener.py`, `adapters/rpc_dispatch.py`, `adapters/marshal.py`, and
`hosts/gui_addon/` returns **zero** hits. Filtering `usecases/*.py` imports against the stdlib list
leaves one line, `usecases/confirm.py:27 import hmac` — stdlib. Enforced at `check_imports.py:266-274`
(usecases allow stdlib + the six-module FreeCAD-App whitelist only) and run at `ci.yml:13`.

**AD-1 — ring rule. CLEAN, and enforced beyond what AD-1 states.**
`check_imports.py` enforces the inward-only rule across all four rings including relative imports
(`_resolve_relative_rings`), plus three rules AD-1 never mentions:
`contracts/` stdlib-only; a ban on raw `pivy.coin.SoOffscreenRenderer` (`check_imports.py:172`,
decision 003); and a ban on `FreeCAD.ActiveDocument`/`setActiveDocument` anywhere
(`check_imports.py:149`), which is the mechanical enforcement of **AD-20**'s "ActiveDocument is
never an implicit target". **Suggested spine addition:** AD-20 should cite this enforcer.

**AD-2 — auto-spawn. CLEAN, matches the amended wording exactly.**
`hosts/gui_addon/bootstrap.py:34 _MCP_PORT = 8765`; three-step resolution at `:188 _mcp_proxy_command()`
— `FREECAD_BUDDY_MCP_CMD` verbatim override → auto-discovered `.venv`/`venv` python walked from the
addon install path (`:177 for venv in (".venv", "venv")`) → legacy `FREECAD_BUDDY_REPO` + `uv`
fallback (`:207`). Opt-out honored at `:226 if os.environ.get("FREECAD_BUDDY_NO_AUTO_MCP")`, and the
spawn is skipped when 8765 is already served. `.mcp.json` is the plain HTTP entry the design implies.

**Tool catalog — namespace prefixes. CLEAN.** All 40 MCP tools carry a legal prefix. Full surface:
7 `document_*` (create/open/save/close/recompute/undo/list), 8 `query_*` (capabilities, screenshot,
tree_summary, object, mass_properties, dependencies, sketch_info, placement), 6 `verify_*` (shape,
sketch, recompute, export_step, export_stl, export_3mf), 3 `export_*` (step, stl, 3mf),
8 `sketch_*` (create, add_geometry, remove_geometry, add_constraint, remove_constraint, set_datum,
toggle_construction, add_external_geometry), 11 `feature_*` (pad, pocket, revolve, hole, fillet,
chamfer, pattern, mirror, datum, body_create, set_parameters), 1 `preview_dry_run`, 1 `debug_exec`
(gated — `mcp_server.py:73` unregisters it when `not exec_registered(caps)`, satisfying AD-4's
"unregistered from the MCP tool list when off"). Every `export_*` has its paired `verify_export_*`
per AD-9. No tool in code lacks a namespace prefix; no prefix in the convention table is unused
except the RPC-only internal legs (finding above).

**AD-15 — skill catalog size. CLEAN.** 15 skill directories: the 12 Track A+B skills plus the
Phase-5 group `urdf-export`, `sdf-export`, `part-sourcing` — exactly the catalog AD-15's parenthetical
describes. All bodies 876–1,186 words, under the 1,500 cap (but unenforced — see MEDIUM finding).

**AD-21 — visual verification leg. NOT YET BUILT, and correctly so.**
`grep -rn 'verify_visual\|visual_judge\|TechDraw' src/ benchmarks/ scripts/` returns nothing. AD-21
binds Phase 3 / gates G3-G4; the repo is at G0-G2 (`benchmarks/g0/ g1/ g2/`). This is scheduling,
not drift — recorded so it is not mistaken for a missing implementation.

---

## Root pattern

Every HIGH/MEDIUM finding is in a **descriptive** section — the Structural Seed tree, the Stack
table, the ring table's "Contains" column, the Capability Map. Every **normative** section — the 23
ADs and the Consistency Conventions — holds. The ADs held because three of them (AD-1, AD-12, AD-17)
have executable enforcers wired into CI; the descriptive sections have none and drifted within eight
weeks of authoring.

Two structural consequences worth acting on:

1. The Structural Seed tree is the single most-wrong artifact in the spine (4 of 12 findings). It was
   a *seed* — a starting shape, not a contract — but it is formatted identically to the binding
   sections. Recommend relabeling it "Structural Seed (as-authored 2026-07-21; see
   `design/project-structure.md` for the current tree)" or regenerating it from the real tree.
2. AD-15's "CI-enforced" claim is the one place a doc asserts an enforcer that does not exist. That
   is the inverse of the usual drift and the only finding where the doc is right and the code owes
   work.
