---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: ['docs/intent.md', 'docs/references/FreeCAD (upstream source + CI)']
workflowType: 'research'
lastStep: 4
research_type: 'technical'
research_topic: 'Running headless FreeCAD in CI (GitHub Actions)'
research_goals: 'Identify the best way to run FreeCAD headless in GitHub Actions CI: candidate Docker images, conda-forge freecad packages, AppImage approaches; QT_QPA_PLATFORM=offscreen viability; version pinning strategy; startup time and runner cost; how FreeCADCmd vs freecad --console differ. Recommend a concrete CI setup. Blocks Phase 0 of docs/intent.md (CI pipeline exit criterion) and every later phase''s benchmark runs.'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Running Headless FreeCAD in CI (GitHub Actions)

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** technical

---

## Research Overview

This report determines the best way to run FreeCAD **headless** in GitHub Actions so that FreeCAD Buddy's bridge/test suite can execute on every push. It directly unblocks the **Phase 0 exit criterion** in `docs/intent.md`:

> *"CI pipeline (GitHub Actions) runs the full tool test suite headless on every push; suite ≥ 30 tests, all green."*

and the standing project risk *"Headless vs GUI behavior differences → Every phase's suite runs headless in CI from Phase 0 onward"*, plus the FreeCAD version-drift risk (*"Pin supported versions, CI matrix across versions, thin adapter layer"*).

**Methodology.** Two evidence streams, per the research brief's priority order:

1. **Primary — the upstream FreeCAD source vendored at `docs/references/FreeCAD`** (version 26.3.0-dev / the `1.x` line's dev tree). Studied its own CI: `.github/workflows/`, `pixi.toml`, `tests/CMakeLists.txt`, and `src/Mod/Test/`. This is the strongest evidence because it is *how the FreeCAD project itself runs headless tests in GitHub Actions today*.
2. **Secondary — web search** across conda-forge (anaconda.org, freecad-feedstock), the FreeCAD-Bundle AppImage releases, the official wiki, the FreeCAD forum, and community FreeCAD-MCP projects, to cover the *installation* options (our project consumes a prebuilt FreeCAD; it does not build from source like upstream does).

A key framing distinction drives the whole recommendation: **upstream builds FreeCAD from source and then tests; FreeCAD Buddy needs to *install a prebuilt FreeCAD* and test against it.** The *test-execution* mechanics transfer directly from upstream; the *acquisition* method is what we choose.

---

## Key Findings

### 1. How upstream FreeCAD runs headless tests (primary evidence)

The vendored source shows the canonical, currently-used invocation. From `docs/references/FreeCAD/.github/workflows/sub_buildPixi.yml`:

```yaml
# Headless CLI (console) tests — no display at all:
testCommand: pixi run ${{ env.builddir }}/bin/FreeCADCmd -t 0

# GUI tests — need a virtual X server (Linux), via xvfb-run:
testCommand: pixi run xvfb-run ${{ env.builddir }}/bin/FreeCAD -t 0

# Visual/screenshot tests — xvfb with an explicit screen geometry:
pixi run xvfb-run -a -s "-screen 0 1024x768x24" "${builddir}/bin/FreeCAD" -t TestCoinNodeSnapshots
```

And for the C++ Qt unit tests, from `docs/references/FreeCAD/tests/CMakeLists.txt` (lines 36-45) and `.github/workflows/actions/runCPPTests/runSingleQtTest/action.yml` (line 28):

```
set_tests_properties(... PROPERTIES LABELS "Qt" ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
# and in CI:  env: QT_QPA_PLATFORM: offscreen
```

**What this tells us — three distinct headless tiers, in order of preference:**

| Tier | Command pattern | Needs a display? | What runs |
|------|-----------------|------------------|-----------|
| **A. Pure console** | `FreeCADCmd -t 0` | **No** — no X, no Qt platform plugin | Everything not importing `FreeCADGui` (kernel, `Part`, `Sketcher`, `PartDesign` scripting, geometry queries, STEP/STL export) |
| **B. Qt offscreen** | `QT_QPA_PLATFORM=offscreen <exe>` | No X server, but Qt initialises against the offscreen platform plugin | Code that constructs `QApplication`/Qt objects but needs no real pixels (C++ QtTest suites) |
| **C. Virtual framebuffer** | `xvfb-run FreeCAD -t 0` | Yes — a virtual X display via Xvfb | Full GUI code paths, `FreeCADGui`, 3D-view rendering, screenshots |

The `-t` flag is FreeCAD's **built-in test runner**: `-t 0` runs the entire registered unittest suite; `-t <Name>` runs one test module; `-t` with no arg lists them (confirmed against the official wiki *Start-up and Configuration* page). The suite is registered in `src/Mod/Test/TestApp.py`. **This is the exact hook FreeCAD Buddy's bridge tests should register into** — write bridge tests as standard Python `unittest` cases and either add them to the Test module or invoke them via `FreeCADCmd your_test_runner.py`, so the same `-t`/console mechanism the whole ecosystem uses drives our suite too.

**Note (upstream-specific, do NOT copy):** upstream uses `pixi` + `conda-forge` to build FreeCAD *from source* (see `pixi.toml`: `occt >=7.8,<7.9`, `python >=3.11,<3.12`, `qt6-main >=6.8,<6.9`, `pyside6`, `noqt5`). That is a compiler toolchain, not an install method. Their `GUI tests on install` step is even disabled with the comment *"currently broken on Qt6 builds"* (`sub_buildPixi.yml` line 243) — a caution that the **GUI (Xvfb) path is the fragile one; the console path is the robust one.**

### 2. FreeCADCmd vs `freecad --console` — the distinction that matters

From the official wiki and the forum evidence:

- **`FreeCADCmd` (a.k.a. `freecadcmd`)** is a *separate executable* whose default behaviour **is** `--console`. It starts a Python REPL/script host with the full FreeCAD API **except `FreeCADGui`**. It does **not** require a display or a Qt GUI platform plugin. This is the headless-native binary.
- **`freecad --console` / `freecad -c`** is the *GUI executable* asked to behave like a console. It still links the GUI stack and, in several packagings (notably AppImage — forum thread #71349 and issue #7421), still tries to connect to a display and errors with `qt.qpa.xcb: could not connect to display` unless `QT_QPA_PLATFORM=offscreen` (or an Xvfb display) is provided.

**Implication:** prefer `FreeCADCmd` for our headless suite. It sidesteps the entire Qt-platform-plugin problem for everything that does not need `FreeCADGui` — which is all of Phase 0's tools (document lifecycle, object-tree inspection, Python-exec sandbox, geometry queries, STEP/STL export). Screenshot capture (a Phase 0 tool) is the one exception that needs Tier B/C — see §5.

### 3. Installation options compared (the actual decision)

Three ways to get a prebuilt FreeCAD onto a GitHub Actions runner:

#### Option 1 — conda-forge `freecad` package (RECOMMENDED)

- **Availability (verified on anaconda.org/conda-forge/freecad):** versions **1.1.0 (latest), 1.0.0, 1.0rc3, 0.21.2, 0.21.1** are published for **all five platforms** (linux-64, linux-aarch64, osx-64, osx-arm64, win-64). Feedstock last updated **2026-05-31** — actively maintained and current with the 1.x line.
- **Install in CI** via a mamba/conda setup action (e.g. `mamba-org/setup-micromamba` or `conda-incubator/setup-miniconda`), then `micromamba create -n fc freecad=1.0.* -c conda-forge`.
- **Version pinning is first-class:** `freecad=1.1.0` or a range pins exactly; a CI matrix (`freecad: [1.0.0, 1.1.0]`) directly implements the intent.md *"CI matrix across versions"* mitigation.
- **Cross-platform:** same mechanism gives Windows and macOS runners too (useful because FreeCAD Buddy's bridge must also run inside the GUI on developer machines across OSes).
- **Headless-clean:** the conda package ships `FreeCADCmd`; `python -c "import FreeCAD"` works in the env without a display. Known wrinkle (feedstock issue #21 / FreeCAD issue #9804): if importing as a bare module rather than via `FreeCADCmd`, you may need the env's `lib` on `PYTHONPATH` or a `.pth` file — avoided entirely by driving tests through `FreeCADCmd` rather than a foreign Python.
- **Caching:** the conda env is cacheable (`actions/cache` keyed on the pinned version), keeping warm-run install time low.

#### Option 2 — FreeCAD-Bundle AppImage (Linux only; viable fallback)

- Official prebuilt AppImages are published per release at `FreeCAD/FreeCAD-Bundle` (naming like `FreeCAD_1.0.0-conda-Linux-x86_64-py311.AppImage`).
- Run headless by extracting (`--appimage-extract`) and either invoking the bundled `FreeCADCmd`, or setting `QT_QPA_PLATFORM=offscreen`, `DISPLAY=`, `FREECAD_CONSOLE=1` before `AppRun` (per the Maskset blog and forum threads).
- **Gotchas:** AppImage has been reported to *ignore* a shell-set `QT_QPA_PLATFORM` in some versions (search evidence), requires FUSE or `--appimage-extract` on runners, and pins you to whatever Python the bundle shipped. Linux-only. More moving parts than conda for pinning and multi-OS.
- **Verdict:** good as a *secondary* matrix leg to prove the AppImage that real users download also passes the suite — not the primary.

#### Option 3 — Docker image (heaviest; use only if the toolchain grows)

- Community images exist (e.g. `amrit3701/freecad-cli`, and several FreeCAD-MCP projects ship Docker-headless setups — proximile/FreeCAD-MCP, spkane's robust MCP server, the pixi-based headless runner noted in search). The FreeCAD project itself publishes a pixi+xvfb container pattern.
- **Cost:** image pull + container startup adds wall-clock and maintenance; you own the base image's freshness. Justified only when the environment needs many system deps beyond FreeCAD (slicers, CalculiX/gmsh for later phases). conda-forge already provides `calculix`, `smesh`, `pythonocc-core`, etc., so Docker's advantage is small early on.
- **Verdict:** defer. Revisit at Phase 4 (the "service" phase) where a reproducible container is a deliverable anyway.

### 4. `QT_QPA_PLATFORM=offscreen` viability

**Viable and recommended as the default Qt platform for any code that touches Qt but not real rendering.** Upstream uses exactly this for its C++ Qt test suites (`tests/CMakeLists.txt`). `offscreen` is a stock Qt platform plugin (confirmed present alongside `minimal`, `vnc`, `xcb`, etc.). It removes the X-server dependency for Qt initialisation.

**Limits to know:**
- `offscreen` gives no GL context suitable for real 3D-view rendering. For actual **screenshot capture of the 3D view** (a Phase 0 export tool and a Phase 5 vision channel), `offscreen` may produce blank/incomplete renders — that path wants **Xvfb** (Tier C) with a real (virtual) framebuffer, optionally plus Mesa software GL (`LIBGL_ALWAYS_SOFTWARE=1`).
- Some packagings ignore a shell-exported value (AppImage caveat above). With the conda `FreeCADCmd` path this is a non-issue because no Qt GUI plugin is loaded at all.

**Practical rule for FreeCAD Buddy:**
- Geometry/query/export tests → `FreeCADCmd` (no Qt platform needed).
- Any Qt-object test without pixels → `QT_QPA_PLATFORM=offscreen`.
- 3D-view screenshot tests → `xvfb-run` (+ software GL), Linux CI only.

### 5. Startup time & runner cost

- **`FreeCADCmd` cold start** is a few seconds (module + kernel load); negligible per-invocation. Prefer **one process running the whole suite** (`FreeCADCmd -t 0` or one runner script that imports FreeCAD once and runs all bridge tests) over spawning a process per test — avoids repeated startup cost. This matches upstream, which runs the entire suite in a single `-t 0` call.
- **Install time dominates, and is cacheable.** A cold conda solve+download of `freecad` is the largest single cost (tens of seconds to a couple of minutes); cache the env keyed on the pinned version so warm runs are near-instant. Upstream caches aggressively (ccache) for the same reason.
- **Runner choice:** `ubuntu-latest` is the cheapest and the natural home for the headless suite (Xvfb available, conda-forge fully covered). Keep Linux as the required gate; make Windows/macOS legs optional/scheduled to control minutes, since GitHub bills non-Linux runners at higher multipliers.
- Use per-step `timeout-minutes` (upstream uses 10-15 min) so a hung headless process fails fast instead of burning the job's full budget.

---

## Recommendation — concrete CI setup for Phase 0

**Primary pipeline (required check): conda-forge FreeCAD, headless via `FreeCADCmd`, on `ubuntu-latest`, with a version matrix.**

Rationale: it satisfies every relevant intent.md constraint — headless from Phase 0, explicit version pinning, a version matrix for the drift risk, cross-OS capability — with the fewest moving parts and the most robust (console, no-Qt) execution path, mirroring how upstream itself gates headless tests.

Sketch (`.github/workflows/ci.yml`):

```yaml
name: CI
on: [push, pull_request]
jobs:
  headless-tests:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        freecad: ["1.0.0", "1.1.0"]   # pin + drift matrix (intent.md risk)
    steps:
      - uses: actions/checkout@v4
      - uses: mamba-org/setup-micromamba@v2
        with:
          environment-name: fc
          create-args: >-
            python=3.11 freecad=${{ matrix.freecad }} trimesh pytest
          condarc: |
            channels: [conda-forge]
          cache-environment: true      # cache the solved env per pinned version
      - name: Headless bridge test suite
        shell: bash -l {0}
        timeout-minutes: 15
        run: FreeCADCmd run_tests.py    # registers/loads bridge unittest suite
```

Where `run_tests.py` imports `FreeCAD` (+ `Part`, `Sketcher`, `PartDesign`), imports the bridge and its `unittest` cases, and runs them in-process (one FreeCAD startup for the whole suite). Assert on geometry (`Shape.isValid()`, `Volume`, `BoundBox`) per the verify-first taxonomy — deterministic, no GUI.

**Add when needed:**
- **Screenshot / 3D-view tests** → a separate Linux step: `xvfb-run -a -s "-screen 0 1024x768x24" FreeCAD -t TestScreenshots` with `LIBGL_ALWAYS_SOFTWARE=1`. Isolate it so its fragility can't block the core geometry gate (upstream even disabled its GUI-on-install leg).
- **Cross-OS confidence** → optional `windows-latest` / `macos-latest` legs (same conda recipe), scheduled or on-label rather than every push, to cap runner minutes.
- **AppImage smoke leg** (Linux) → optionally run the same suite against the official FreeCAD-Bundle AppImage to prove the artifact users actually download passes.

**Version pinning strategy:** pin exact versions in the matrix (`1.0.0`, `1.1.0`); FreeCAD 1.0 is the first release with built-in TNP mitigation (intent.md Reuse Map), so 1.0 is the sensible floor and 1.1 the current head. Keep a thin adapter layer over version-sensitive API calls (already an intent.md mitigation) and let the matrix catch drift.

**Defer Docker** until Phase 4's service packaging, where a reproducible container is a deliverable in its own right.

---

## Reuse-Map alignment (intent.md)

This confirms the intent.md row *"Headless FreeCAD in CI → Community Docker images / conda-forge FreeCAD packages / AppImage in CI runners → Invent only thin CI glue scripts."* Finding: **conda-forge is the pick, not Docker/AppImage, for Phase 0.** Only thin glue is invented: `run_tests.py` and the workflow YAML. No geometry-kernel or test-runner invention — FreeCAD's own `-t` runner and `unittest` are reused directly.

---

## Open Questions / Follow-ups

1. **conda import edge case** — confirm on a real runner whether bridge tests driven by `FreeCADCmd run_tests.py` need any `PYTHONPATH`/`.pth` fix (feedstock issue #21). Expected: no, because `FreeCADCmd` sets up its own paths; verify in the Phase 0 spike.
2. **Screenshot fidelity under Xvfb+software GL** — validate that `verify`/`query` screenshot tools produce non-blank 3D renders headlessly before relying on them for the Phase 5 vision channel.
3. **conda-forge release lag** — monitor how quickly a new FreeCAD 1.x point release lands on conda-forge vs the AppImage bundle, in case a needed fix appears in one channel first.

---

## Sources

Primary (vendored upstream source, cited by path):
- `docs/references/FreeCAD/.github/workflows/sub_buildPixi.yml` — headless test invocations (`FreeCADCmd -t 0`, `xvfb-run FreeCAD -t 0`, screenshot xvfb geometry; GUI-on-install disabled comment)
- `docs/references/FreeCAD/.github/workflows/sub_buildUbuntu.yml` — same patterns on the Ubuntu (non-pixi) build path
- `docs/references/FreeCAD/.github/workflows/actions/runCPPTests/runSingleQtTest/action.yml` — `QT_QPA_PLATFORM: offscreen`
- `docs/references/FreeCAD/tests/CMakeLists.txt` — `ENVIRONMENT "QT_QPA_PLATFORM=offscreen"` on Qt-labelled tests
- `docs/references/FreeCAD/.github/workflows/actions/runPythonTests/action.yml` — how the Python test command + report is wrapped
- `docs/references/FreeCAD/pixi.toml`, `version.json` — pinned deps (occt 7.8, python 3.11, qt6, pyside6) and version (26.3.0-dev, i.e. the 1.x dev line)
- `docs/references/FreeCAD/src/Mod/Test/TestApp.py` — the `-t` test registry our suite hooks into

Web:
- [freecad — conda-forge (anaconda.org)](https://anaconda.org/conda-forge/freecad) — versions 1.1.0/1.0.0/0.21.2 across 5 platforms, updated 2026-05-31
- [conda-forge/freecad-feedstock](https://github.com/conda-forge/freecad-feedstock) and [issue #21 "freecad not importable"](https://github.com/conda-forge/freecad-feedstock/issues/21)
- [FreeCAD wiki — Start up and Configuration](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Start_up_and_Configuration.md) — `--console`/`-c`, `-t`/`--run-test`, FreeCAD vs FreeCADCmd
- [Scripting FreeCAD from an AppImage — Maskset](https://www.maskset.net/blog/2023/03/22/scripting-freecad-from-an-appimage/) — AppImage extract + headless env vars
- [FreeCAD forum #71349](https://forum.freecad.org/viewtopic.php?f=3&t=71349) and [FreeCAD issue #7421](https://github.com/FreeCAD/FreeCAD/issues/7421) — `qt.qpa.xcb: could not connect to display` under headless `freecad -c`
- [FreeCAD/FreeCAD-Bundle releases](https://github.com/FreeCAD/FreeCAD-Bundle/releases) — official AppImages
- [FreeCAD issue #9804](https://github.com/FreeCAD/FreeCAD/issues/9804) — `import FreeCAD` path caveat
- Community FreeCAD-MCP CI/headless references: [proximile/FreeCAD-MCP](https://github.com/proximile/FreeCAD-MCP), [spkane/freecad-addon-robust-mcp-server](https://github.com/spkane/freecad-addon-robust-mcp-server), [sergiudanstan/freecad-mcp](https://github.com/sergiudanstan/freecad-mcp) (headless `freecadcmd` fallback)
