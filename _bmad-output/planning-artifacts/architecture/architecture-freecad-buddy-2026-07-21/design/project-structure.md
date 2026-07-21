---
title: 'FreeCAD Buddy — Project Structure Design'
status: draft
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
├── src/
│   └── freecad_buddy/
│       ├── __init__.py               # version string only; no imports
│       ├── contracts/                # stdlib only (AD-1); CI-enforced; layout owned by data-contracts-design.md
│       │   ├── __init__.py
│       │   ├── status.py             # closed terminal-status set + ErrorDetail (AD-17)
│       │   ├── envelope.py           # ResultEnvelope, ImageRef (AD-17)
│       │   ├── report.py             # ValidationReport, ReportBanner, Check, WilsonCI
│       │   ├── job.py                # JobStatus
│       │   ├── audit.py              # AuditRecord (JSON-lines)
│       │   ├── diff.py               # GeometryDiff preview payload (AD-10)
│       │   ├── document.py           # DocHandle + sub-element selectors (AD-20; no bare Face6)
│       │   ├── fingerprint.py        # FingerprintRecord (AD-6)
│       │   ├── rpc.py                # JSON-RPC frame types + rpc_hello handshake, both sides import (AD-2)
│       │   ├── assertions.py         # assertion vocabulary + anchor-frame derivation set (AD-13)
│       │   └── jsonschema/           # generated per-tool/per-type schemas, drift-checked in CI
│       ├── usecases/                 # stdlib + FreeCAD App via shim (AD-1, AD-12)
│       │   ├── __init__.py
│       │   ├── shim.py               # ALL version-sensitive calls; capability probes (AD-11)
│       │   ├── fingerprint.py        # single fingerprint() impl, serializer-tagged (AD-6)
│       │   ├── transactions.py       # AD-5 mutation protocol skeleton (Phase 0: stub + tests)
│       │   ├── tnp_guard.py          # snapshot/audit_references (AD-7; capability-gated via shim)
│       │   ├── documents.py          # document_* lifecycle, explicit handles (AD-20)
│       │   ├── queries.py            # query_* (tree, object, shape props, recompute status)
│       │   ├── exports.py            # export_step / export_stl / export_3mf; unit pinned per call
│       │   └── verify.py             # verify_shape, verify_sketch, in-FreeCAD leg of verify_export_* (AD-8, AD-9)
│       ├── adapters/
│       │   ├── __init__.py           # EMPTY — import discipline (§2.3)
│       │   ├── mcp_server.py         # FastMCP server + tool registry; stdio/HTTP flag (AD-3) [ext-only]
│       │   ├── rpc_listener.py       # in-FreeCAD listener; stdlib only; localhost + session token (AD-2/3)
│       │   ├── marshal.py            # main-thread marshal (postEvent pattern; Qt at call time — §7)
│       │   ├── rpc_client.py         # external-side RPC client over contracts/rpc.py
│       │   ├── render_probe.py       # render capability probe (sole Qt exception in adapters, AD-1)
│       │   ├── skills_loader.py      # router + forced-subset modes (AD-15) [ext-only]
│       │   ├── export_oracles.py     # trimesh / lib3mf / admesh checks (AD-9) [ext-only]
│       │   └── harness.py            # benchmark-runner glue, ValidationReport emission [ext-only]
│       └── hosts/
│           ├── __init__.py           # EMPTY
│           ├── InitGui.py            # addon entry source-of-truth; copied to addon root at build (§2.2)
│           ├── gui_addon.py          # deferred start (GuiUp + QTimer.singleShot), listener wiring (AD-2)
│           └── main.py               # CLI: serve --mode inline|rpc --transport stdio|http; headless entry
├── addon/
│   └── package.xml                   # Addon Manager metadata (§2.2)
├── skills/                           # one dir per skill (AD-15); Phase 0: empty + shape check wired
│   └── <skill-name>/
│       ├── SKILL.md                  # 4 sections, ≤1,500 words (CI-enforced)
│       └── references/
├── benchmarks/
│   ├── runner.py                     # gate runner CLI → contracts ValidationReport (SPEC assumption)
│   ├── golden/                       # 5 reference models (G0.3): gNN_<name>/{model.FCStd, expected.json, PROVENANCE.md}
│   │   ├── g01_plate/  … g05_bracket/
│   ├── dev/                          # dev split (AD-13/16); per-phase subdirs (phase0/, phase2/ …)
│   ├── heldout/                      # SEALED: sha256 MANIFEST + SEALED marker; runner refuses without --gate-exit
│   └── fault-injection/
│       └── verify_shape/             # G0.E: ≥10 planted-fault cases: fNN_<fault>/{model.FCStd, fault.json}
├── tests/
│   ├── run_tests.py                  # FreeCADCmd entry; one process, stdlib unittest only (conventions)
│   ├── infc/                         # in-FreeCAD suites (stdlib unittest, AD-12)
│   │   ├── test_shim.py
│   │   ├── test_documents.py
│   │   ├── test_queries.py
│   │   ├── test_exports.py
│   │   ├── test_verify.py
│   │   ├── test_fingerprint.py
│   │   └── test_rpc_listener.py      # listener loopback, no MCP deps
│   └── external/                     # pytest, uv env; no FreeCAD needed except where marked
│       ├── conftest.py
│       ├── test_contracts.py
│       ├── test_rpc_frames.py        # frame round-trip vs contracts/rpc.py
│       ├── test_mcp_server.py        # tools/list, schema validity (G0.2 pre-check)
│       └── test_export_oracles.py
├── scripts/
│   ├── check_imports.py              # AST no-Gui/no-third-party ring check (AD-1/12) — CI job
│   ├── check_skill_shape.py          # 4-section + word-count check (AD-15) — CI job
│   ├── build_addon.py                # assembles dist/addon/FreeCADBuddy/ (§2.2); stdlib only
│   └── install_addon_dev.py          # dev copy/junction into FreeCAD Mod/ (§4.1)
└── .github/
    └── workflows/
        ├── ci.yml                    # blocking matrix + arch checks + render leg (§5)
        └── canary.yml                # weekly 1.2-dev allowed-to-fail leg (AD-11)
```

Deferred (dirs reserved, no Phase 0 files): `hosts/phase4/` supervisor (AD-18), `benchmarks/dev/phase{1,2,3}/`, per-phase fault suites (AD-19 lands each at its entry gate).

## 2. Packaging

### 2.1 External process — uv

```toml
# pyproject.toml
[project]
name = "freecad-buddy"
version = "0.0.1"
requires-python = ">=3.11"
dependencies = [
    "mcp==1.26.*",        # placeholder — pin EXACT at Phase 0 gate after SDK v2 (spine Stack); spec ≥2025-06-18
    "trimesh==4.*",       # export oracle (AD-9)
    "lib3mf==2.*",        # 3MF oracle (AD-9)
]

[project.optional-dependencies]
stl-oracle = ["admesh ; sys_platform == 'linux'"]   # optional 2nd oracle; fallback chosen at Phase 0 gate (AD-9)
dev = ["pytest>=8", "ruff>=0.5", "jsonschema>=4"]

[project.scripts]
freecad-buddy = "freecad_buddy.hosts.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/freecad_buddy"]
```

- `uv sync --all-extras` creates the dev venv; `uv.lock` committed.
- No FreeCAD dependency in pyproject — FreeCAD comes from the host (GUI install or conda env, §4).

### 2.2 FreeCAD addon

`scripts/build_addon.py` assembles the installable addon (nothing hand-maintained twice):

```text
dist/addon/FreeCADBuddy/
├── package.xml           # copied from addon/package.xml
├── InitGui.py            # copied from src/freecad_buddy/hosts/InitGui.py
└── freecad_buddy/        # full package copy from src/freecad_buddy/
```

- FreeCAD adds each `Mod/<addon>/` dir to `sys.path` → `import freecad_buddy` resolves in-process with zero path hacks.
- The full package is copied, including `[ext-only]` modules; AD-12 holds because in-FreeCAD code never *imports* them (§2.3). Copying whole beats a curated subset: no drift between two package layouts.
- `InitGui.py` is thin (≈20 lines): optional dev-source path override (§4.1), then `QTimer.singleShot` deferred call into `freecad_buddy.hosts.gui_addon.start()` once `FreeCAD.GuiUp` (AD-2). No logic lives in it.

```xml
<!-- addon/package.xml (load-bearing fields) -->
<package format="1" xmlns="https://wiki.freecad.org/Package_Metadata">
  <name>FreeCAD Buddy</name>
  <description>Verify-first MCP bridge for FreeCAD</description>
  <version>0.0.1</version>
  <freecadmin>1.0</freecadmin>
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

## 3. Python / FreeCAD version strategy per CI leg (AD-11, spine Stack)

| Leg | FreeCAD | Python (matches bundled interpreter) | Source | Blocking |
| --- | --- | --- | --- | --- |
| floor | 1.0.x latest patch on conda-forge | 3.11 | micromamba conda-forge | yes |
| primary | 1.1.x latest patch on conda-forge | 3.12 | micromamba conda-forge | yes |
| canary | 1.2-dev weekly | as shipped (do not pin) | conda-forge if published, else weekly AppImage | no (allowed-to-fail) |
| render | 1.1.x (same env as primary) | 3.12 | micromamba + xvfb + Mesa sw GL | no (isolated) |
| arch/fast | none | 3.12 | uv only | yes |

`requires-python = ">=3.11"`; no 3.10-or-lower syntax; 3.12-only syntax banned until the 1.0.x leg retires.

## 4. Environments

### 4.1 Dev (Windows/Linux desktop) — GUI + external server

1. Install FreeCAD 1.1.x GUI (official installer).
2. `uv sync --all-extras` in repo root.
3. `python scripts/install_addon_dev.py` — copies `package.xml` + `InitGui.py` into `<FreeCAD user dir>/Mod/FreeCADBuddy/` and writes a `buddy_dev.pth`-style pointer: `InitGui.py` checks env var `FREECAD_BUDDY_SRC`; when set (dev), it `sys.path.insert(0, $FREECAD_BUDDY_SRC)` so the live repo `src/` is used — no re-copy per edit. Unset = vendored copy (release behavior).
4. Start FreeCAD → addon starts RPC listener on localhost with per-session token (AD-2/3).
5. `uv run freecad-buddy serve --mode rpc --transport http` → external MCP server bridging to the listener (AD-3: HTTP for long-lived GUI serving).

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
| `arch-checks` | — (uv, py3.12) | `uv sync` → `check_imports.py` → `check_skill_shape.py` → `ruff check` → `pytest tests/external` (no-FreeCAD subset) | yes |
| `headless` | `{freecad: 1.0.x/py3.11, 1.1.x/py3.12}` `fail-fast: false` | micromamba (cached) → pip layer-in → `FreeCADCmd tests/run_tests.py` → `pytest tests/external` → `benchmarks/runner.py --gate G0` | yes (both legs, G0.4) |
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
          - { freecad: "1.0.*", python: "3.11" }
          - { freecad: "1.1.*", python: "3.12" }
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

The authoritative Phase 0 tool catalog is **mcp-tools-design.md** (§2): 25 Phase 0 tools, of which 17 fall in the gate's literal `query_`/`document_`/`export_` namespace set (≥15, G0.2 satisfied), plus 7 `verify_` tools. Names, schemas, and counts live there — this doc only maps them to files (`usecases/` per §1).

## 7. Conflicts

No AD is contradicted by this design. The AD-1 marshal wording gap flagged during authoring has since been **resolved in the spine**: AD-1 now names both `adapters/` Qt exemptions explicitly (render capability probe + main-thread marshal, QtCore only). `check_imports.py` whitelists exactly `hosts/`, `adapters/marshal.py`, `adapters/render_probe.py` for Qt; `marshal.py` imports Qt symbols inside functions so module import stays clean.
