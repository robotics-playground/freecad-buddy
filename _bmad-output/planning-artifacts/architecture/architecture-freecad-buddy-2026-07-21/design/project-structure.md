---
title: 'FreeCAD Buddy — Project Structure Design'
status: final
date: '2026-07-21'
ad-refs: [AD-1, AD-2, AD-3, AD-4, AD-6, AD-9, AD-11, AD-12, AD-13, AD-15, AD-16, AD-17, AD-19, AD-20]
binds-to: ../ARCHITECTURE-SPINE.md
---

# Project Structure Design

Expands the spine's structural seed to Phase 0 file level: repo tree, dual packaging (uv external process + FreeCAD addon), Python/FreeCAD version legs, environments, CI workflow layout.

## 1. Repository Tree (Phase 0)

```text
freecad-buddy/
├── pyproject.toml                    # uv-managed external process (§2.1)
├── uv.lock
├── LICENSE                           # MIT, TanNT
├── release-please-config.json        # release-please on main; version files it bumps (§2.4)
├── .release-please-manifest.json
├── .claude-plugin/
│   └── marketplace.json              # Claude Code marketplace: plugin source ./skills + MCP entry (§2.4)
├── src/
│   └── freecad_buddy/
│       ├── __init__.py               # version string only; no imports
│       ├── contracts/                # stdlib only (AD-1); CI-enforced; layout owned by data-contracts-design.md
│       │   ├── __init__.py
│       │   ├── status.py             # closed terminal-status set + ErrorDetail (AD-17)
│       │   ├── envelope.py           # ResultEnvelope, ImageRef (AD-17)
│       │   ├── report.py             # ValidationReport, ReportBanner, Check, WilsonCI
│       │   ├── audit.py              # AuditRecord (JSON-lines)
│       │   ├── diff.py               # GeometryDiff preview payload (AD-10)
│       │   ├── document.py           # DocHandle + sub-element selectors (AD-20; no bare Face6)
│       │   ├── fingerprint.py        # FingerprintRecord (AD-6)
│       │   ├── rpc.py                # JSON-RPC frame types + rpc_hello handshake, both sides import (AD-2)
│       │   ├── assertions.py         # assertion vocabulary + anchor-frame derivation set (AD-13)
│       │   ├── capabilities.py       # capability-map wire type
│       │   ├── confirm.py            # preview_id confirm token (AD-10)
│       │   ├── mutation.py           # shared mutation-request shapes
│       │   ├── sketch.py             # sketch geometry/constraint wire types
│       │   ├── feature.py            # feature parameter wire types
│       │   ├── render.py             # ImageRef + view-control types (AD-10)
│       │   ├── numbers.py            # display rounding of result floats and check deviations
│       │   └── jsonschema/           # generated per-tool/per-type schemas, drift-checked in CI (AD-28)
│       ├── usecases/                 # stdlib + FreeCAD App via shim (AD-1, AD-12)
│       │   ├── __init__.py
│       │   ├── shim.py               # ALL version-sensitive calls; capability probes (AD-11); preference keys
│       │   ├── operator_settings.py  # PreferenceValues + resolve_env_overlay: env wins, else preference, else default
│       │   ├── fingerprint.py        # single fingerprint() impl, serializer-tagged (AD-6)
│       │   ├── transaction.py        # AD-5 mutation protocol: run_mutation(), the only mutation path
│       │   ├── tnp_guard.py          # snapshot/audit_references (AD-7; capability-gated via shim)
│       │   ├── documents.py          # document_* lifecycle, explicit handles (AD-20); owns the AD-25 session workdir
│       │   ├── queries.py            # query_* (tree, object, shape props, recompute status)
│       │   ├── sketches.py           # sketch_* typed mutations (AD-5 bracket)
│       │   ├── features.py           # feature_* typed mutations incl. feature_body_create
│       │   ├── exports.py            # export_step / export_stl / export_3mf; unit pinned per call
│       │   ├── preview.py            # preview_dry_run on a FCB_TMP_ TempDoc (AD-10, AD-20)
│       │   ├── screenshot.py         # constructed-scene render; _MAX_DIM = 1920 (AD-10)
│       │   ├── capabilities.py       # runtime capability map surfaced by query_capabilities
│       │   ├── confirm.py            # preview_id confirm-token issue/validate (AD-10)
│       │   ├── debug_exec.py         # operator-only, off by default, audit-logged (AD-4)
│       │   ├── stats.py              # Wilson/McNemar rate statistics (AD-14); stdlib-only so the
│       │   │                         #   in-FreeCAD G2 scorer can import it too
│       │   └── verify.py             # verify_shape, verify_sketch, in-FreeCAD leg of verify_export_* (AD-8, AD-9)
│       ├── adapters/
│       │   ├── __init__.py           # EMPTY — import discipline (§2.3)
│       │   ├── mcp_server.py         # MCP low-level Server + tool registry; stdio/HTTP flag (AD-3) [ext-only]
│       │   ├── rpc_listener.py       # in-FreeCAD listener; stdlib only; localhost + session token (AD-2/3)
│       │   ├── marshal.py            # main-thread marshal (postEvent pattern; no Qt import — pump is in hosts/gui_addon/pump.py)
│       │   ├── rpc_client.py         # external-side RPC client over contracts/rpc.py
│       │   ├── rpc_dispatch.py       # single AD-17 error boundary: exceptions → closed status set
│       │   ├── render_probe.py       # render capability probe + SoQtOffscreenRenderer (sole Qt exception in adapters, AD-1)
│       │   ├── audit_log.py          # append-only JSON-lines writer (AD-17)
│       │   ├── export_oracle.py      # trimesh / lib3mf / admesh checks (AD-9) [ext-only]
│       │   ├── export_verdict.py     # oracle-agreement verdict (disagreement = fail, AD-9) [ext-only]
│       │                             #   transport, contracts + stdlib only (decision 011) [ext-only]
│       └── hosts/
│           ├── __init__.py           # EMPTY
│           ├── tool_catalog.py       # shared tool surface: schemas, timeouts, mutating flags, audit events
│           ├── main.py               # CLI: serve --mode inline|rpc --transport stdio|http
│           ├── gui_addon/
│           │   ├── InitGui.py        # addon entry source-of-truth; copied to addon root at build (§2.2)
│           │   ├── bootstrap.py      # start_bridge: deferred start (GuiUp + QTimer), listener + MCP auto-spawn (AD-2)
│           │   ├── pump.py           # Qt event pump — Qt lives here, not in adapters (AD-1)
│           │   ├── managed_venv.py   # release install: find uv, provision the proxy venv from the bundled wheel; stdlib only
│           │   └── preferences.py    # FreeCAD Buddy page in Edit > Preferences (rounding + operator settings)
│           ├── gui_external/
│           │   └── entry.py          # external GUI host
│           └── headless/
│               └── entry.py          # headless entry (FreeCADCmd / import FreeCAD)
├── addon/
│   └── package.xml                   # Addon Manager metadata (§2.2)
├── skills/                           # one dir per skill (AD-15); 18 target (12 Track A/B + 3 Track W + 3 Phase-5)
│   └── <skill-name>/
│       ├── SKILL.md                  # 4 sections, ≤1,500 words (check_skill_shape.py)
│       └── references/
├── benchmarks/                       # per-gate layout, not a flat dev/heldout split
│   ├── runner.py                     # gate runner CLI → contracts ValidationReport ( `gate` console alias)
│   ├── harness/                      # actor, assertions, evidence, seal, verdict, report_build, scripted_backend …
│   ├── g0/                           # each gate dir carries its own splits + gate.yaml
│   │   ├── golden-models/            # 5 reference models (G0.3): {model.FCStd, expected.yaml, PROVENANCE.md}
│   │   ├── dev/
│   │   ├── heldout/                  # SEALED per gate; runner refuses without `gate run --exit`
│   │   └── fault-injection/          # ≥10 planted-fault cases per validator (AD-13)
│   ├── g1/  g2/                      # same shape
│   ├── _registry/                    # validators.yaml + provenance/*.yaml (CI-gated, AD-16)
│   └── gate-artifacts/               # <gate>/<run-id>/ — verdicts recomputed from these (AD-25 retention)
├── tests/                            # two worlds that never mix; the split is the rule, not the file list
│   ├── run_tests.py                  # FreeCADCmd entry; one process, stdlib unittest only (decision 002)
│   ├── infc/                         # 22 in-FreeCAD suites (stdlib unittest, AD-12); never collected by pytest
│   └── external/                     # 29 pytest suites, uv env; `testpaths = ["tests/external"]`
├── scripts/
│   ├── check_imports.py              # AST ring check: no Gui, no third-party, no ActiveDocument (AD-1/12/20) — CI job
│   ├── check_status_vocab.py         # holds the AD-17 closed status set — CI job
│   ├── check_provenance.py           # benchmark provenance manifests (AD-16) — CI job
│   ├── gen_schemas.py                # generates contracts/jsonschema/, `--check` drift-fails CI (AD-28)
│   ├── build_addon.py                # assembles dist/addon/ (§2.2); --release adds the wheel + zip; stdlib only
│   └── automation/                   # run_mcp_e2e.py, run_mcp_edge_cases.py — live MCP manual harness
│
│   # check_skill_shape.py (AD-15): 4 sections + word cap; front-matter, description and cross-skill rules are Story 6.1.
└── .github/
    └── workflows/
        ├── ci.yml                    # blocking matrix + arch checks + render leg (§5)
        ├── canary.yml                # weekly 1.2-dev allowed-to-fail leg (AD-11)
        └── release.yml               # release-please on main; uploads wheel, sdist, addon zip (§2.4)
```

Deferred (dirs reserved, no Phase 0 files): `benchmarks/dev/phase{1,2}/`, per-phase fault suites (AD-19 lands each at its entry gate).

## 2. Packaging

### 2.1 External process — uv

```toml
# pyproject.toml
[project]
name = "freecad-buddy"
version = "0.0.1"
description = "Verify-first MCP bridge that lets AI agents build and check FreeCAD models"
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
authors = [{ name = "TanNT" }]
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.28,<2",       # official MCP python-sdk, CLOSED at the Phase 0 gate (decision 005); low-level Server,
                          #   NOT PrefectHQ fastmcp; <2 caps below the SDK v2 rename. Spec ≥2025-06-18
    "trimesh==4.*",       # export oracle (AD-9)
    "lib3mf==2.*",        # 3MF oracle (AD-9)
]

[project.optional-dependencies]
stl-oracle = ["admesh ; sys_platform == 'linux'"]   # optional 2nd oracle; fallback chosen at Phase 0 gate (AD-9)
dev = ["pytest>=8", "ruff>=0.5", "jsonschema>=4", "pyyaml>=6"]  # pyyaml: external harness only (AD-12)
stl-oracle = ["admesh ; sys_platform == 'linux'"]               # optional 2nd STL oracle (AD-9)

[project.scripts]
freecad-buddy = "freecad_buddy.hosts.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/freecad_buddy"]

[tool.hatch.build.targets.sdist]
include = ["/src/freecad_buddy", "/addon", "/README.md", "/LICENSE"]
```

`[project.urls]` names the GitHub repository. The repository is private, so there is no PyPI publish; the wheel and sdist ship only as GitHub release assets (§2.4).

- `uv sync --all-extras` creates the dev venv; `uv.lock` committed.
- No FreeCAD dependency in pyproject — FreeCAD comes from the host (GUI install or conda env, §4).

### 2.2 FreeCAD addon

`scripts/build_addon.py` assembles the installable addon (nothing hand-maintained twice):

```text
dist/addon/
├── package.xml           # copied from addon/package.xml
├── InitGui.py            # generated shim: puts the package on sys.path, imports hosts/gui_addon/InitGui.py
├── repo-root.txt         # dev build only: absolute repo path; lets a copied install find the project .venv
├── wheels/               # --release only: freecad_buddy-<ver>-py3-none-any.whl for the managed venv
└── freecad_buddy/        # full package copy from src/freecad_buddy/
```

- `build_addon.py --release [--wheel PATH]` builds the release tree: the wheel goes in `wheels/` (built with `uv build --wheel` when `--wheel` is absent) and no marker is written. `package_zip` then writes `dist/FreeCADBuddy-<ver>.zip` with the top folder `FreeCADBuddy/`, so extracting it into `Mod/` gives `Mod/FreeCADBuddy/`. On first start the addon provisions `<FreeCAD user app data>/FreeCADBuddy/venv` from that wheel with `uv` and runs the MCP proxy from it (integration-mcp-freecad §3.1).

- FreeCAD adds each `Mod/<addon>/` dir to `sys.path` → `import freecad_buddy` resolves in-process with zero path hacks.
- The full package is copied, including `[ext-only]` modules; AD-12 holds because in-FreeCAD code never *imports* them (§2.3). Copying whole beats a curated subset: no drift between two package layouts.
- `InitGui.py` is thin (≈20 lines): optional dev-source path override (§4.1), then `QTimer.singleShot` deferred call into `freecad_buddy.hosts.gui_addon.start()` once `FreeCAD.GuiUp` (AD-2). No logic lives in it.

```xml
<!-- addon/package.xml (load-bearing fields) -->
<package format="1" xmlns="https://wiki.freecad.org/Package_Metadata">
  <name>FreeCAD Buddy</name>
  <description>Verify-first MCP bridge for FreeCAD</description>
  <version>0.0.1</version>
  <freecadmin>1.1</freecadmin>
  <content>
    <workbench>
      <classname>FreeCADBuddyWorkbench</classname>
      <subdirectory>./</subdirectory>
    </workbench>
  </content>
</package>
```

### 2.3 One package, two runtimes — path strategy

| Runtime | How `freecad_buddy` resolves | Allowed imports | Enforced by |
| --- | --- | --- | --- |
| External process (uv venv / conda python) | installed dist (`uv sync` / `pip install -e .`) | anything in pyproject | — |
| FreeCAD GUI process | `Mod/FreeCADBuddy/freecad_buddy/` on `sys.path` | stdlib + FreeCAD API; Qt in hosts/marshal/render_probe only | `scripts/check_imports.py` (AD-1/12) |
| Headless inline (`serve --mode inline`) | external install; process itself does `import FreeCAD` | pyproject deps + FreeCAD module | conda env provides FreeCAD (§4.2) |

Import discipline making this safe: `adapters/__init__.py` and `hosts/__init__.py` are empty; every module imports its own deps at module top; in-FreeCAD code paths (`rpc_listener`, `marshal`, `gui_addon`, all of `usecases/`+`contracts/`) never import an `[ext-only]` module. `check_imports.py` asserts, per AST walk: `contracts/` = stdlib only; `usecases/` = stdlib + {FreeCAD, Part, Sketcher, PartDesign, Mesh, MeshPart} via shim; `rpc_listener.py` = stdlib only; `FreeCADGui`/`PySide*` nowhere outside `hosts/`, `marshal.py`, `render_probe.py` (AD-1 + §7).

### 2.4 Release and plugin

- **release-please** (`.github/workflows/release.yml`, on push to `main`) opens the release PR; the user merges it. `release-please-config.json`: release type `python`, `include-component-in-tag: false` (tag `v<ver>`), `bootstrap-sha` and `release-as` pin the first release. Besides `pyproject.toml` it bumps `src/freecad_buddy/__init__.py` and `addon/package.xml` (generic `x-release-please-version` markers), `.claude-plugin/marketplace.json` (`$.plugins[0].version`) and `uv.lock` (toml). `tests/external/test_version_consistency.py` keeps the four checked-in versions equal.
- When a release is created, the workflow runs `uv build` and `build_addon.py --release`, then `gh release upload` attaches the wheel, the sdist and `FreeCADBuddy-<ver>.zip`.
- **Claude Code plugin.** `.claude-plugin/marketplace.json` holds one plugin, `freecad-buddy`, with `source: "./skills"`, `strict: false` and `skills: "./"`, so the plugin cache gets only the `skills/` folder and no `plugin.json` lives inside `skills/`. The entry also registers the MCP server `freecad-buddy` → `http://127.0.0.1:8765/mcp`.

## 3. Python / FreeCAD version strategy per CI leg (AD-11, spine Stack)

| Leg | FreeCAD | Python (matches bundled interpreter) | Source | Blocking |
| --- | --- | --- | --- | --- |
| headless | 1.1.x latest patch on conda-forge (1.1.3) | 3.11 | micromamba conda-forge | yes |
| canary | 1.2-dev weekly | as shipped (do not pin) | conda-forge if published, else weekly AppImage | no (allowed-to-fail) |
| render | 1.1.x (same build as headless) | 3.11 | micromamba + xvfb + Mesa sw GL | no (isolated) |
| arch/fast | none | 3.12 | uv only | yes |

`requires-python = ">=3.11"`; no 3.10-or-lower syntax; 3.12-only syntax banned while the CI 1.1.x leg runs Python 3.11.

## 4. Environments

### 4.1 Dev (Windows/Linux desktop) — GUI + external server

1. Install FreeCAD 1.1.x GUI (official installer).
2. `uv sync --all-extras` in repo root.
3. `python scripts/build_addon.py "<FreeCAD user dir>/Mod/FreeCADBuddy"` — assembles the addon (package copy + `package.xml` + generated `InitGui.py` shim) at that path. With no argument it writes to `dist/addon/` instead. The generated shim resolves the package from its own install location, so a junction from `Mod/FreeCADBuddy` to the built dir gives edit-in-place development without a re-copy per change.
4. Start FreeCAD → the addon starts the RPC listener on localhost with a per-session token AND **auto-spawns the external MCP HTTP proxy** on `http://127.0.0.1:8765/mcp`. The proxy interpreter is the project `.venv`/`venv` python, **auto-discovered from the addon's install path** — no env var to set (the addon never imports `mcp`; AD-2/3, AD-12). So the whole setup is: install the addon, `uv sync`, open FreeCAD; the MCP client connects straight to `:8765`. Operator settings live on Edit > Preferences > FreeCAD Buddy; a `FREECAD_BUDDY_*` env var overrides the matching field.
5. **(debug/troubleshoot only)** If the auto-spawned proxy is unavailable, start it by hand: `uv run freecad-buddy serve --mode rpc --transport http`. The `--mode rpc` CLI is a fallback for when auto-start is disabled (`FREECAD_BUDDY_NO_AUTO_MCP`) or no venv is discoverable — never the normal path.

### 4.1a Release install (operator)

1. Install FreeCAD 1.1.x and `uv`.
2. Download `FreeCADBuddy-<ver>.zip` from the GitHub release (needs access to the private repo) and extract it into `<FreeCAD user dir>/Mod/`, which gives `Mod/FreeCADBuddy/`.
3. Start FreeCAD. The first start provisions the managed venv on a background thread (`freecad-buddy/provision.log`), then spawns the proxy on `:8765`. Later starts reuse the venv until the bundled wheel changes.

### 4.2 CI (ubuntu-latest, micromamba conda-forge)

- FreeCAD from conda-forge per leg (headless-research recommendation); env cached by micromamba keyed on the pin.
- External deps layered into the *same* conda env: `micromamba run -n fc python -m pip install -e ".[dev]"` — pyproject exact pins keep this deterministic; uv stays the dev-machine manager (spine Stack: uv external-process only).
- In-FreeCAD suite: `micromamba run -n fc FreeCADCmd tests/run_tests.py` — one process, whole suite, stdlib unittest (Tier A: no Qt platform at all).
- External suite + G0 checks: `micromamba run -n fc pytest tests/external` and `micromamba run -n fc python benchmarks/runner.py --gate G0`.
- Phase 0 spike verifies the conda `FreeCADCmd` path edge (feedstock issue #21) — spine Deferred.

### 4.3 Local test loop

| Loop | Command | Needs FreeCAD |
| --- | --- | --- |
| fast unit (contracts, frames, oracles) | `uv run pytest tests/external` | no |
| ring/import check | `uv run python scripts/check_imports.py` | no |
| in-FreeCAD suite | `FreeCADCmd tests/run_tests.py` (or `micromamba run -n fc …`) | yes |
| gate dry-run (honest fail vs stub, AD-19) | `uv run python benchmarks/runner.py --gate G0 --stub` | no |
| GUI smoke | §4.1 steps 4–5, then `tools/list` via any MCP client | yes (GUI) |

## 5. CI workflow layout

### 5.1 `ci.yml` — push/PR

| Job | Matrix | Steps | Blocking |
| --- | --- | --- | --- |
| `arch-checks` | — (uv, py3.12) | `uv sync` → `check_imports.py` → `check_status_vocab.py` → `gen_schemas.py --check` → `check_provenance.py` → `check_skill_shape.py` → `ruff check` (T201 print ban) → `pytest tests/external` | yes |
| `headless` | `{freecad: 1.1.x/py3.11}` | micromamba (cached) → pip layer-in → `FreeCADCmd tests/run_tests.py` → `pytest tests/external` → `benchmarks/runner.py --gate G0` | yes (G0.4) |
| `render` | 1.1.x only | same env + `xvfb-run -a -s "-screen 0 1024x768x24"` + `LIBGL_ALWAYS_SOFTWARE=1`, render-tagged tests only | no (`continue-on-error: true`) |

```yaml
# .github/workflows/ci.yml — load-bearing fragment (headless job)
jobs:
  headless:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        include:
          - { freecad: "1.1.*", python: "3.11" }
    steps:
      - uses: actions/checkout@v4
      - uses: mamba-org/setup-micromamba@v2
        with:
          environment-name: fc
          create-args: >-
            python=${{ matrix.python }} freecad=${{ matrix.freecad }}
          condarc: |
            channels: [conda-forge]
          cache-environment: true          # keyed on create-args → per-pin cache
      - run: micromamba run -n fc python -m pip install -e ".[dev]"
      - name: In-FreeCAD suite (stdlib unittest, one process)
        timeout-minutes: 15
        run: micromamba run -n fc FreeCADCmd tests/run_tests.py
      - name: External suite + gate checks
        timeout-minutes: 15
        run: |
          micromamba run -n fc pytest tests/external
          micromamba run -n fc python benchmarks/runner.py --gate G0
```

Isolation rules: render job never gates merges (upstream evidence: GUI/xvfb path is the fragile one); `heldout/` is excluded from every `ci.yml` job — only a manually-dispatched gate-exit workflow (added at first phase exit) may pass `--gate-exit` to the runner (AD-13 sealing).

### 5.2 `canary.yml` — weekly schedule

Single job, `continue-on-error: true`: resolve FreeCAD 1.2-dev (conda-forge dev label if published, else download latest weekly AppImage + `--appimage-extract`), run the same two suites. Failure opens/updates a pinned issue; never blocks (AD-11).

### 5.3 Caching

| What | Mechanism | Key |
| --- | --- | --- |
| conda env per leg | `setup-micromamba` `cache-environment` | env name + create-args (freecad+python pin) |
| uv venv (`arch-checks`) | `astral-sh/setup-uv` built-in cache | `uv.lock` hash |
| pip layer-in | none (seconds; exact pins) | — |

## 6. Tool-count runway (G0.2 ≥15 tools)

The authoritative Phase 0 tool catalog is **mcp-tools-design.md** (§2): **24 AI-visible Phase 0 tools + 1 operator-only** (`debug_exec`, unregistered when off per AD-4). Of the 24, **17** fall in the gate's literal `query_`/`document_`/`export_` namespace set (≥15, G0.2 satisfied) and **7** are `verify_`. Names, schemas, and counts live there — this doc only maps them to files (`usecases/` per §1). The shipped surface is whatever `hosts/tool_catalog.py:tool_specs()` returns; any count in a document is a claim about that function.

## 7. Conflicts

No AD is contradicted by this design. AD-1 names **one** `adapters/` Qt exemption: the render capability probe. `marshal.py` ended up needing no Qt at all — the event pump lives in `hosts/gui_addon/pump.py`, where Qt is legal without an exemption. `check_imports.py` still whitelists `adapters/marshal.py`; that entry is now dead and should be removed when the guard is next touched.
