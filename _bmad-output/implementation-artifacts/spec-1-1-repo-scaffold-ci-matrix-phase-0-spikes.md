---
title: 'Story 1.1 — Repo Scaffold, CI Matrix & Phase 0 Spikes'
type: 'chore'
created: '2026-07-21'
status: 'done'
baseline_revision: 'ec284a864255fa25d0880d33d4950a44cfbec842'
final_revision: 'UNCOMMITTED (working tree — commit withheld per user no-auto-commit policy; branch=main protected)'
review_loop_iteration: 1
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
warnings: []
---

<intent-contract>

## Intent

**Problem:** The repo has no source tree. Every later Epic 1 story assumes an enforced architecture-ring skeleton, a blocking two-leg headless CI matrix, and recorded answers to the five Phase 0 unknowns (AR9) — none exist yet. Without them later stories can silently violate the spine (AD-1/AD-12) or cite undecided serializer/host/render/dimension/SDK choices.

**Approach:** Lay down the `src/freecad_buddy` ring layout per `project-structure.md §1` (packages present, `adapters/__init__.py` and `hosts/__init__.py` EMPTY), a `pyproject.toml` (hatchling src-layout, `requires-python=">=3.11"`, external deps + extras), a working AST-based `scripts/check_imports.py` that fails naming file+rule, `ci.yml` (arch-checks + blocking {1.0.x/py3.11, 1.1.x/py3.12} headless matrix + non-blocking render leg) and `canary.yml` (weekly allowed-to-fail 1.2-dev), and five spike decision notes under `docs/decisions/` that later stories cite. No contracts, tool, or usecase logic — skeleton only.

## Boundaries & Constraints

**Always:**
- Match `project-structure.md §1` tree exactly: `contracts/ usecases/ adapters/ hosts/` rings, `skills/ benchmarks/ tests/infc + tests/external scripts/ addon/`.
- `adapters/__init__.py` and `hosts/__init__.py` stay EMPTY (byte-empty). `src/freecad_buddy/__init__.py` holds a version string only, zero imports.
- `contracts/` importable code is stdlib-only; anything running inside FreeCAD (usecases, adapters/rpc_listener, marshal, hosts) imports zero third-party. `mcp`/`trimesh`/`lib3mf`/`pytest` live only in the external uv process (extras/dev groups).
- Qt/`FreeCADGui`/`PySide*` whitelist = `hosts/`, `adapters/marshal.py`, `adapters/render_probe.py` ONLY — enforced by `check_imports.py`.
- Both headless CI legs blocking (`fail-fast: false`); render leg `continue-on-error: true`; canary weekly `continue-on-error: true`. `heldout/` excluded from every routine CI job.
- Per-leg interpreter matches the leg's FreeCAD build (3.11 ↔ 1.0.x, 3.12 ↔ 1.1.x); code syntax floor = 3.11 (no 3.12-only syntax).
- Each of the 5 spikes gets a decision note in the repo; the note names the downstream decision it drives (serializer id / H1-vs-H2 host / render ladder / dimension façade / MCP SDK pin) and separates "resolved by research" from "runtime-confirm in later spike".
- Conventional Commits; NEVER auto-commit without explicit user approval; no AI attribution.

**Block If:**
- `project-structure.md` cannot be located (tree layout unknowable → cannot scaffold correctly).

**Never:**
- Implement contract types, tool handlers, verification, fingerprint, RPC, or MCP server logic — those are stories 1.2+. Only empty/placeholder module stubs where the tree requires a file to exist.
- Add FreeCAD as a pyproject dependency (it comes from the host/conda env).
- Invent conda FreeCAD patch pins or an MCP SDK version number: use `1.0.0` / `1.1.0` (conda-forge-verified) and record the MCP pin as an open Phase-0 decision, not a fabricated number.
- Fabricate empirical spike results requiring a live FreeCAD runtime (no FreeCAD on this dev box); record the research-backed decision + the runtime-confirmation checklist instead.

## I/O & Edge-Case Matrix

`check_imports.py` is the one behavioral artifact with meaningful I/O; everything else is static scaffold.

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Clean tree | All modules obey ring + Qt-whitelist rules | Exit 0, no output (or "OK" summary) | No error expected |
| Outward import | `usecases/x.py` imports `hosts...` | Exit non-zero; message names file + violated rule | Report, do not raise traceback |
| Qt outside whitelist | `usecases/x.py` imports `FreeCADGui`/`PySide2` | Exit non-zero; names file + Qt-whitelist rule | Report file + rule |
| Third-party in contracts | `contracts/x.py` imports `trimesh` | Exit non-zero; names file + stdlib-only rule | Report file + rule |
| Whitelisted Qt | `adapters/marshal.py` imports `QtCore` | Exit 0 (allowed) | n/a |

</intent-contract>

## Code Map

- `pyproject.toml` -- hatchling src-layout, name `freecad-buddy`, `requires-python=">=3.11"`, runtime deps (`mcp`,`trimesh`,`lib3mf`) + `optional-dependencies` (`dev`, `stl-oracle`), `[project.scripts] freecad-buddy=...`, ruff config (target py311, T201 print-ban).
- `src/freecad_buddy/__init__.py` -- version string only.
- `src/freecad_buddy/contracts/__init__.py` -- present (stdlib-only ring).
- `src/freecad_buddy/usecases/__init__.py`, `usecases/shim.py` -- shim holds capability-probe stubs cited by spikes (`export_binary_available`, `varset_available`, `render_available`, `element_map_available`).
- `src/freecad_buddy/adapters/__init__.py` -- MUST be empty.
- `src/freecad_buddy/hosts/__init__.py` -- MUST be empty; `hosts/main.py` -- console-script entry stub (`main()`).
- `scripts/check_imports.py` -- AST-walk ring + Qt-whitelist enforcer.
- `.github/workflows/ci.yml` -- arch-checks + headless matrix + render leg.
- `.github/workflows/canary.yml` -- weekly 1.2-dev allowed-to-fail.
- `tests/external/test_scaffold.py` -- pytest: tree + empty-init + check_imports pass.
- `tests/external/test_check_imports.py` -- pytest: violation detection cases from the I/O matrix.
- `tests/infc/`, `tests/run_tests.py` -- in-FreeCAD stdlib-unittest runner stub.
- `docs/decisions/00{1..6}-*.md` -- decision notes: the 5 named Phase-0 spikes (serializer / H1-vs-H2 host / render / dimension / SDK) plus the conda-`FreeCADCmd` test-driver decision.
- `benchmarks/`, `skills/`, `addon/package.xml` -- reserved dirs + addon metadata stub.

## Tasks & Acceptance

**Execution:**
- [x] `pyproject.toml` -- author hatchling src-layout build; name `freecad-buddy`, version `0.0.1`, `requires-python=">=3.11"`; `[project.dependencies]` = `mcp`, `trimesh`, `lib3mf` (mcp version left as a tracked placeholder pending spike 5 — comment referencing decision note); `[project.optional-dependencies]` `dev=[pytest,ruff,jsonschema]`, `stl-oracle=["admesh ; sys_platform=='linux'"]`; `[project.scripts] freecad-buddy="freecad_buddy.hosts.main:main"`; `[tool.ruff]` target-version py311 + T201 in select; `[tool.hatch.build.targets.wheel] packages=["src/freecad_buddy"]`. -- one schema vocabulary + external-only deps.
- [x] `src/freecad_buddy/**` -- create ring package tree: `__init__.py` (version only); `contracts/__init__.py`; `usecases/__init__.py` + `usecases/shim.py` (capability-probe function stubs returning conservative defaults, docstring citing the relevant spike); `adapters/__init__.py` (EMPTY) + placeholder module files only where a later story needs the path reserved (`marshal.py`, `render_probe.py`, `rpc_listener.py` as minimal stubs so the Qt-whitelist has real targets to test); `hosts/__init__.py` (EMPTY) + `hosts/main.py` with `main()` printing-free stub that argparses `serve` and exits. -- enforced-ring skeleton (AD-1/AD-12).
- [x] `scripts/check_imports.py` -- AST-walk every `src/freecad_buddy/**.py`; enforce: contracts stdlib-only; usecases stdlib + FreeCAD-App whitelist via shim; Qt/`FreeCADGui`/`PySide*` allowed only in `hosts/`, `adapters/marshal.py`, `adapters/render_probe.py`; no outward/sideways ring imports. **Files under a non-ring subpackage (any `src/freecad_buddy/**.py` whose first path segment is not a ring — e.g. `freecad_buddy/util/helper.py`, depth ≥ 2 below the package root) MUST NOT be silently skipped: apply the same Qt-ban + stdlib/FreeCAD-App floor that package-root files get, so a stray third-party/Qt import in any non-ring subpackage is flagged, not escaped.** On violation print `path:line -- <rule>` and exit 1; clean = exit 0. Runs FreeCAD-free. -- AC#2.
- [x] `.github/workflows/ci.yml` -- `arch-checks` job (uv, `astral-sh/setup-uv`, `uv sync --all-extras` → `check_imports.py` → `ruff check` → `pytest tests/external`), blocking; `headless` matrix `{freecad:1.0.0/python:3.11, freecad:1.1.0/python:3.12}` via `mamba-org/setup-micromamba@v2` (`environment-name: fc`, `create-args` python+freecad, `condarc` conda-forge, `cache-environment: true`), `fail-fast:false`, both blocking, steps run `FreeCADCmd tests/run_tests.py` + `pytest tests/external`, `timeout-minutes:15`; `render` job (1.1.0 only, `continue-on-error:true`, `xvfb-run -a -s "-screen 0 1024x768x24"` + `LIBGL_ALWAYS_SOFTWARE=1`). -- AC#3, NFR4.
- [x] `.github/workflows/canary.yml` -- weekly `schedule` cron, single job `continue-on-error:true`, resolves FreeCAD 1.2-dev (conda-forge dev label if present, else note AppImage fallback), runs both suites; never blocks. -- AC#3.
- [x] `tests/external/test_scaffold.py` + `tests/external/test_check_imports.py` -- pytest asserting the tree exists, `adapters/__init__.py`+`hosts/__init__.py` are byte-empty, `check_imports.py` exits 0 on the real tree, and each I/O-matrix violation case is detected (use tmp fixtures). -- AC#1 + I/O matrix coverage.
- [x] `tests/run_tests.py` + `tests/infc/__init__.py` -- in-FreeCAD stdlib-`unittest` runner stub that discovers `tests/infc/` and runs in one process (no test cases yet — empty discovery passes). -- two-test-worlds separation.
- [x] `docs/decisions/001-serializer-exportbinary.md` … `006-host-model-h1-h2.md` -- decision notes covering the five named Phase-0 spikes (serializer / **H1-vs-H2 host** / render ladder / dimension façade / MCP SDK pin — the exact five enumerated in the intent-contract Boundaries and AC#4) plus the conda-`FreeCADCmd` test-driver decision, one note per decision: (1) fingerprint serializer = probe `exportBinary`, fallback `exportBrep`, hash tagged, cross-tag banned; (2) conda `FreeCADCmd` path — drive tests via `FreeCADCmd`, not foreign python; runtime-confirm interpreter version per leg; (3) render ladder = `SoQtOffscreenRenderer` + `setupWithoutGUI()` under xvfb+software-Mesa, never raw `SoOffscreenRenderer`; (4) dimension façade = VarSet-with-Spreadsheet-fallback behind `varset_available()` probe, Spreadsheet safe default until 1.1 confirms; (5) MCP SDK = official `mcp` python-sdk (not PrefectHQ `fastmcp`); exact pin deferred to Phase 0 gate after v2 stabilizes (`FastMCP`→`MCPServer` rename) — record as open, no fabricated number; **(6) host model = H1 (canonical single-process `import FreeCAD`, AD-2) with H2 (`FreeCADCmd run_server.py`, no marshal) as the fallback host for interpreters that cannot `import FreeCAD` (AppImage / interpreter mismatch), per `integration-mcp-freecad.md §1`; names the downstream decision it drives (story 1.4 transport/host wiring in `hosts/`) and separates research-resolved from runtime-confirm.** Each note has a "Decision", "Drives", and "Runtime-confirm" section. **AC#4 requires each of the five named spikes — serializer / H1-vs-H2 host / render-ladder / dimension-façade / SDK — to have a citable note; the H1-vs-H2 host choice MUST be recorded (note 006), not omitted.** -- AC#4.
- [x] `benchmarks/`, `skills/`, `addon/package.xml`, `.gitignore` refresh, `uv.lock` -- reserved dirs with `.gitkeep` where empty; `addon/package.xml` minimal Addon Manager metadata stub; ensure `heldout/` marker present + git-excluded from CI globs. -- tree completeness (project-structure §1).

**Acceptance Criteria:**
- Given a fresh clone, when `uv sync --all-extras` and `uv run pytest tests/external` run, then the env builds and the external suite passes, and the tree matches `project-structure.md §1`.
- Given a module importing `FreeCADGui` from `usecases/` or a third-party lib from `contracts/`, when `scripts/check_imports.py` runs, then the build fails naming file + rule (Qt whitelist = `hosts/`, `adapters/marshal.py`, `adapters/render_probe.py`).
- Given a push, when `ci.yml` runs, then `arch-checks` (uv-only) and the `headless` matrix {1.0.0/py3.11, 1.1.0/py3.12} execute cached-micromamba, both blocking, and `canary.yml` exists as a weekly allowed-to-fail 1.2-dev leg.
- Given the five Phase 0 spike questions, when the story completes, then each has a recorded decision note in `docs/decisions/`, and the serializer / H1-vs-H2 / render-ladder / dimension-façade / SDK choices used by later stories cite it.

## Design Notes

- **Spikes on a FreeCAD-less dev box.** Two spikes (exportBinary presence, VarSet external exposure) and per-leg interpreter version need a live FreeCAD runtime that isn't available here. The decision notes therefore record the research-backed decision + a shim capability-probe + an explicit "Runtime-confirm" checklist executed on the CI runner — this satisfies AC#4 ("recorded answer … cited by later stories") without fabricating empirical results. Probes live in `usecases/shim.py` so no downstream code branches on version strings.
- **check_imports stdlib classification.** Use `sys.stdlib_module_names` (py3.11+) to decide stdlib vs third-party; treat `FreeCAD`,`Part`,`Sketcher`,`PartDesign`,`Mesh`,`MeshPart` as the FreeCAD-App whitelist for `usecases/`. Walk with `ast`, resolve top-level module of each `Import`/`ImportFrom`, map file to its ring by path prefix.
- **conda-forge pins.** Only `1.0.0` and `1.1.0` are verified on conda-forge; do not pin `1.0.2`/`1.1.1`. Per-leg python is `3.11` (1.0.x) / `3.12` (1.1.x) — set explicitly in the matrix, do not reuse one value for both legs.
- **Placeholder stubs vs empty inits.** `adapters/__init__.py` + `hosts/__init__.py` must be byte-empty (import discipline). `marshal.py`/`render_probe.py`/`rpc_listener.py` are minimal stubs (module docstring + `pass`) so the Qt-whitelist and ring checks have real files to validate against; their logic lands in stories 1.4/1.8.

## Verification

**Commands:**
- `uv sync --all-extras` -- expected: env builds, no resolution error.
- `uv run python scripts/check_imports.py` -- expected: exit 0 on the scaffolded tree.
- `uv run pytest tests/external -q` -- expected: all tests pass (scaffold + check_imports violation cases).
- `uv run ruff check .` -- expected: clean (T201 print-ban honored — no `print()` in `src/`).
- `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); yaml.safe_load(open('.github/workflows/canary.yml')); print('yaml ok', file=sys.stderr)"` -- expected: both workflow YAMLs parse.

**Manual checks:**
- `adapters/__init__.py` and `hosts/__init__.py` are byte-empty (`wc -c` == 0).
- `docs/decisions/` holds 6 notes (001-006), each with Decision / Drives / Runtime-confirm sections and no fabricated version numbers; the H1-vs-H2 host decision (006) is present.
- `ci.yml` matrix has two headless legs with distinct python per freecad pin, both blocking; render leg `continue-on-error: true`.

## Spec Change Log

### 2026-07-21 — bad_spec loopback (iteration 1)

- **Triggering findings:**
  1. `[high] bad_spec` — Missing **H1-vs-H2 host** decision note. Intent-contract Boundaries (line 33) and AC#4 both enumerate the five Phase-0 spikes as `serializer / H1-vs-H2 host / render ladder / dimension façade / MCP SDK pin`, but task `docs/decisions/…` (outside the intent-contract) enumerated note-2 as the conda-`FreeCADCmd` path and omitted a host-model note. Delivered notes 001-005 therefore have no H1-vs-H2 host decision — AC#4 ("H1-vs-H2 … choices used by later stories cite it") is unmet as literally written. `integration-mcp-freecad.md §1` confirms H1 (canonical single-process `import FreeCAD`) vs H2 (`FreeCADCmd run_server.py` fallback) is a real Phase-0 unknown story 1.4 branches on. Root cause is the outside-contract task text, not the intent → bad_spec, not intent_gap.
  2. `[medium] bad_spec` — `check_imports.py` silently skips non-ring subpackage files at depth ≥ 2 (e.g. `freecad_buddy/util/helper.py`): `_ring_of` returns None, `_check_root_file` bails on `len(parts) != 1`, so `import FreeCADGui` / `import trimesh` in a non-ring subpackage escapes the gate entirely (verified live: returns `[]`). Same bypass class as the package-root gap patched in the prior pass, one level deeper. Task-81/AC#2 says "AST-walk **every** `src/freecad_buddy/**.py`" and enforce the Qt-whitelist — the skip contradicts that. The task text was not explicit that non-ring subpackages must inherit the root floor → bad_spec.

- **Amended (outside `<intent-contract>` only):**
  - Decision-notes task: 5 notes → 6 notes; added note `006-host-model-h1-h2.md` (H1 canonical / H2 fallback) and made the AC#4 host-note requirement explicit. Kept the conda-`FreeCADCmd` note (002) — it is a real, cited decision (`run_tests.py`/CI legs).
  - `check_imports.py` task: added explicit requirement that non-ring subpackage files (first segment not a ring, depth ≥ 2) inherit the package-root Qt-ban + stdlib/FreeCAD-App floor rather than being skipped.
  - Code Map + Manual-check lines updated from 5 → 6 notes.

- **Known-bad state avoided:** shipping a scaffold where (a) later stories citing the H1-vs-H2 host decision have no note to cite, and (b) a third-party or Qt import in any non-ring subpackage silently passes the architecture gate.

- **KEEP (must survive re-derivation):**
  - Existing ring scaffold, byte-empty `adapters/__init__.py` + `hosts/__init__.py`, version-only root init — all correct, do not disturb.
  - All current `check_imports.py` logic (ring direction, relative-import forms incl. names-form + over-climb, package-root `_check_root_file`, Qt whitelist by full path, unparseable-file handling) — correct; ONLY add non-ring-subpackage coverage (extend the depth-1 guard, do not weaken the existing checks).
  - Decision notes 001, 002 (conda-path), 003, 004, 005 — correct as written; keep verbatim, only ADD 006.
  - All 29 existing external tests pass — keep them; add a regression test for the non-ring-subpackage case and bump `test_decision_notes_exist` 5 → 6.
  - CI workflows (`ci.yml`, `canary.yml`), `pyproject.toml`, `addon/package.xml`, `run_tests.py` — untouched, correct.

## Review Triage Log

### 2026-07-21 — Review pass (post-loopback re-review)
- intent_gap: 0
- bad_spec: 0
- patch: 4: (high 0, medium 1, low 3)
- defer: 0
- reject: 3
- addressed_findings:
  - `[medium]` `[patch]` `check_imports.py` `_check_root_file`: broadening it to depth ≥ 2 non-ring subpackage files exposed a new asymmetry — an over-climbing relative import (`from ....escape import x`) that escapes the package root was silently allowed there, though ring files flag it. Added the `_relative_base(...) is None` → "climbs above the package root" check to `_check_root_file`, mirroring `_check_file`; regression test `test_non_ring_subpackage_relative_overclimb_flagged` (verified live: now flagged, level 4).
  - `[low]` `[patch]` violation message said "package-root files allow stdlib + FreeCAD-App whitelist only" for a depth ≥ 2 non-ring subpackage file (not a package-root file). Reworded to "non-ring files allow …"; updated `test_package_root_third_party_flagged` + the new non-ring test assertions accordingly.
  - `[low]` `[patch]` new non-ring regression test asserted only rule substrings, not the offending file (I/O-matrix requires "name file + rule"). Added `assert "util/helper.py" in str(x)` for every violation.
  - `[low]` `[patch]` no test pinned that FreeCAD-App-whitelist imports stay ALLOWED in a non-ring subpackage; a future over-tightening would go uncaught. Added `import Part` to the clean non-ring fixture. Also hedged note 006's "no marshal needed" H2 claim from settled fact into a research-expectation + runtime-confirm item (spec Boundaries: never fabricate empirical spike results).
- rejected (noise / not this story's problem): note 006 "both H1 and H2 fail" escalation branch — not spec-mandated; the AppImage/both-fail path is already tracked via canary + note 002 context, and 006 adequately drives story 1.4. Duplicated parse/walk loop between `_check_file`/`_check_root_file` — maintainability nit, no consumer consequence, pre-existing pattern. New-test `tmp_path` isolation nit — the `/clean` subdir already isolates the scan.

### 2026-07-21 — Review pass (bad_spec loopback, iteration 1)
- intent_gap: 0
- bad_spec: 2: (high 1, medium 1)
- patch: 0
- defer: 2
- reject: 14
- addressed_findings:
  - `[high]` `[bad_spec]` Missing H1-vs-H2 host decision note — intent-contract line 33 + AC#4 name `serializer / H1-vs-H2 host / render / dimension / SDK` as the five spikes, but the outside-contract decision-notes task enumerated conda-path as note-2 and omitted the host-model note, so no note records H1-vs-H2 for story 1.4 to cite. Amended the decision-notes task to 6 notes (added `006-host-model-h1-h2.md`), made AC#4 host-note requirement explicit; loopback to re-derive.
  - `[medium]` `[bad_spec]` `check_imports.py` silently skips non-ring subpackage files (depth ≥ 2, first segment not a ring) — `import FreeCADGui`/`import trimesh` in `freecad_buddy/util/helper.py` escapes the gate (verified live: `[]`). Amended the `check_imports.py` task to require non-ring subpackages inherit the package-root Qt-ban + stdlib/FreeCAD-App floor; loopback to re-derive.

### 2026-07-21 — Follow-up review pass
- intent_gap: 0
- bad_spec: 0
- patch: 3: (high 1, medium 1, low 1)
- defer: 2
- reject: 15
- addressed_findings:
  - `[high]` `[patch]` `check_imports.py` relative-import bypass: `from .. import hosts` / `from . import <ring>` named the target ring via `node.names`, which `_resolve_relative_ring` never inspected — outward relative imports using the names form slipped the ring gate entirely (verified live: NOT FLAGGED). Replaced with `_relative_base` + `_resolve_relative_rings` covering both `node.module` and `node.names`; regression tests `test_relative_names_import_ring_flagged` + `test_relative_names_import_from_top_ring_flagged`.
  - `[medium]` `[patch]` package-root files (`freecad_buddy/util.py`) were skipped by `_ring_of` (head not a ring) → Qt/third-party imports at the package root escaped the gate unchecked (verified: `import FreeCADGui` at root NOT CHECKED). Added `_check_root_file` enforcing the Qt-ban + stdlib/FreeCAD-App floor on direct package-root files; tests `test_package_root_qt_import_flagged`, `test_package_root_third_party_flagged`, `test_package_root_stdlib_and_version_only_clean`.
  - `[low]` `[patch]` over-climbing relative imports (`from ....x import y`) were silently swallowed as "no ring" instead of flagged. `_relative_base` now returns None on over-climb and the caller emits a `relative import climbs above the package root` violation; test `test_relative_climb_above_package_root_flagged`.
- rejected (noise / not this story's problem, sample): `arch-checks` `uv sync --all-extras` "couples the blocking leg to unpinned mcp" — spec-sanctioned; AC#1 requires this leg to prove the env resolves, and it runs on a clean uv/ubuntu env (not FreeCAD's bundled interpreter, where the headless legs correctly avoid it); `__pycache__`/3.14 pyc in worktree — gitignored + untracked, not shipped; addon `<freecadmax>`/icon/maintainer + missing workbench class — intentional skeleton stub; render leg "proves nothing" — spec-mandated Phase-0 placeholder; `test_decision_notes_exist == 5` brittleness, `admesh` name, dead `pass` stubs, missing `permissions:`/`concurrency:` — cosmetic / out of scope.

### 2026-07-21 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 10: (high 2, medium 4, low 4)
- defer: 0
- reject: 6
- addressed_findings:
  - `[high]` `[patch]` `check_imports.py` skipped relative imports (`from ..hosts import x`) — outward relative imports slipped the ring gate. Added `_resolve_relative_ring` + `_flag_outward` so relative `ImportFrom` is direction-checked; regression test `test_relative_outward_import_flagged` (+ inward-allowed case).
  - `[high]` `[patch]` `from freecad_buddy import hosts` (2-segment ImportFrom, ring in `names`) was undetected and inconsistent with the `import` form. Added `_firstparty_target_rings` covering all three forms; regression test `test_from_freecad_buddy_import_ring_flagged`.
  - `[medium]` `[patch]` multi-alias `import freecad_buddy.a, freecad_buddy.hosts` only checked the first alias (`break`). Now collects every target ring; test `test_multi_alias_import_second_ring_flagged`.
  - `[medium]` `[patch]` Qt whitelist matched basename only — nested `adapters/sub/marshal.py` wrongly exempt. Now matches full package-relative path; test `test_nested_marshal_not_qt_exempt`.
  - `[medium]` `[patch]` `ast.parse`/`read_text` unguarded — a malformed/non-UTF8 file crashed the whole check. Wrapped to emit an `unparseable file` violation; test `test_unparseable_file_reported_not_crash`.
  - `[medium]` `[patch]` headless + canary CI legs installed `.[dev]` which pulls the unpinned `mcp` + `trimesh`/`lib3mf` under FreeCAD's bundled interpreter — coupling the blocking gate to unpinned-dep wheel availability (the risk decision 005 defers). Switched to `pip install --no-deps -e . && pip install pytest`.
  - `[low]` `[patch]` canary run steps lacked `timeout-minutes`; added 15-min timeouts matching the headless legs.
  - `[low]` `[patch]` `test_root_init_has_version_only` used a brittle `"import" not in text` substring check. Replaced with an AST walk for import nodes.
  - `[low]` `[patch]` decision notes 001/003/004 used present-tense "Confirmed on the CI …" under Runtime-confirm, overstating stub reality. Reworded to "To be confirmed …".
  - `[low]` `[patch]` enforcer test suite had no relative-import / 2-segment cases (false confidence). Covered by the regression tests above.


## Auto Run Result

Status: done

### 2026-07-21 — Follow-up review run (bad_spec loopback + post-loopback re-review)

**Summary of implemented change.** A `done`-spec follow-up review pass surfaced two real bad_spec deviations, triggered one spec-amendment + implementation loopback (iteration 1), then a post-loopback re-review that patched four residual findings. Net delta over the prior `done` state: added the missing H1-vs-H2 host decision note, closed a `check_imports.py` bypass for non-ring subpackage files (Qt/third-party AND over-climbing relative imports), and tightened the enforcer's violation message + tests.

**Files changed (this run).**
- `docs/decisions/006-host-model-h1-h2.md` — NEW. H1 canonical (`import FreeCAD` single-process, AD-2) with H2 (`FreeCADCmd run_server.py`) fallback host; drives story 1.4 host wiring; marshal-free H2 premise recorded as research-expectation + runtime-confirm (no fabricated results).
- `scripts/check_imports.py` — `_check_root_file` now applies the Qt-ban + stdlib/FreeCAD-App floor to non-ring subpackage files at any depth (was skipped at depth ≥ 2), and flags over-climbing relative imports there; violation message reworded "package-root" → "non-ring".
- `tests/external/test_check_imports.py` — added `test_non_ring_subpackage_qt_and_third_party_flagged` (+ file-name + App-whitelist-clean assertions) and `test_non_ring_subpackage_relative_overclimb_flagged`; updated `test_package_root_third_party_flagged` message assertion.
- `tests/external/test_scaffold.py` — `test_decision_notes_exist` 5 → 6.
- `spec-1-1-…md` — amended decision-notes + check_imports tasks (outside `<intent-contract>`), Spec Change Log iteration-1 entry, two triage-log entries, Code Map + Manual-check note-count 5 → 6.
- `deferred-work.md` — 2 NEW entries (unenforced "no top-level FreeCAD/Qt in usecases/marshal" invariant; runner-interpreter stdlib classification vs the 3.11 floor).

**Review findings breakdown.**
- Loopback pass (iteration 1): bad_spec 2 (high 1 host-note, medium 1 non-ring bypass) → spec amended + re-derived. defer 2. reject 14.
- Post-loopback re-review: patch 4 (medium 1 over-climb, low 3 message/test/note-hedge) → all fixed. defer 0. reject 3. No further loopback.

**Follow-up review recommendation:** `true`. A behavioral change to the architecture-enforcement gate (`check_imports.py`) plus a new decision note later stories cite warrant an independent confirming pass.

**Verification performed.**
- `uv run python scripts/check_imports.py` → `check_imports OK`, exit 0.
- `uv run --with pytest --with jsonschema pytest tests/external -q` → 31 passed.
- `uv run ruff check .` → All checks passed.
- Both workflow YAMLs parse (`yaml.safe_load`).
- `adapters/__init__.py` + `hosts/__init__.py` byte-empty (wc -c == 0/0); `docs/decisions/` holds 6 notes.
- Live falsification: pre-fix `freecad_buddy/util/helper.py` with `import FreeCADGui`/`import trimesh` returned `[]` (bypass); post-fix flagged both, and `from ....escape import x` there now flagged "climbs above the package root".

**Residual risks.**
- Working tree UNCOMMITTED — no commit made (branch `main` is protected; user no-auto-commit policy). Scaffold + this run's changes are untracked/unstaged.
- Spike decisions (serializer / host / render / dimension / SDK) are research-backed, not runtime-confirmed — no live FreeCAD on this dev box; each note carries a Runtime-confirm checklist to close on the CI legs.
- Three deferred `check_imports.py` enforcement gaps remain open in the ledger (top-level FreeCAD/Qt invariant unenforced; runner-vs-3.11 stdlib classification; pivy/coin render-backend ban) — latent, no current code triggers them.
