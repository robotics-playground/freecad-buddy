---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments:
  - docs/intent.md
  - docs/references/FreeCAD (v26.3-dev source, src/ + tests/)
workflowType: 'research'
lastStep: 5
research_type: 'technical'
research_topic: 'MCP server embedding inside the FreeCAD GUI process'
research_goals: 'Determine how to run an MCP server inside the FreeCAD GUI process without freezing/crashing it: transport choice (stdio vs SSE vs streamable HTTP), Qt event loop integration, Python GIL constraints, FreeCAD thread-safety rules (which APIs must run on main thread), asyncio-in-Qt patterns (qasync etc.), and how the same server also runs headless under FreeCADCmd. Blocks Phase 0 of docs/intent.md (bridge must run in-GUI AND headless).'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical — MCP Server Embedding Inside the FreeCAD GUI Process

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** technical (deep dive)
**Blocks:** Phase 0 of `docs/intent.md` — the FreeCAD Bridge must run **inside the FreeCAD GUI process AND headless** under `FreeCADCmd`.

---

## Research Overview

This report determines how to run an MCP (Model Context Protocol) server that drives FreeCAD from inside the running FreeCAD GUI process without freezing or crashing it, and how the same server implementation runs headless in `FreeCADCmd` for CI and agent use. It answers five coupled questions: (1) transport choice (stdio vs SSE vs streamable HTTP); (2) Qt event-loop integration; (3) Python GIL constraints; (4) FreeCAD thread-safety rules — which APIs must run on the main thread; (5) the asyncio-in-Qt pattern (qasync / QtAsyncio) and the single-server-two-modes packaging.

**Methodology.** Claims are grounded first in the **local FreeCAD source** at `docs/references/FreeCAD` — this is a very recent build, **v26.3-dev** (post-1.0 continuous versioning; see `docs/references/FreeCAD/version.json`), which is significant because it contains a *formal async-recompute threading contract* that older FreeCAD (0.21/1.0) did not. Web sources (FastMCP docs, qasync, MCP transport guidance, and two existing community FreeCAD-MCP addons) supplement and cross-check. Every load-bearing thread-safety and event-loop claim carries a `src/...` file citation. Confidence is flagged where a claim rests on a single source or on inference.

---

## Technical Research Scope Confirmation

**Research Topic:** MCP server embedding inside the FreeCAD GUI process
**Research Goals:** (see frontmatter)

**Technical Research Scope:**
- Architecture Analysis — in-process embed vs external-process + in-FreeCAD RPC; single-server-two-modes
- Implementation Approaches — main-thread marshaling, deferred start, transport selection
- Technology Stack — MCP Python SDK / FastMCP, Qt (PySide) event loop, qasync/QtAsyncio, FreeCAD Python API
- Integration Patterns — stdio vs streamable HTTP vs SSE; RPC bridge to FreeCAD's main thread
- Performance / Safety Considerations — GIL, Qt thread affinity, async recompute worker threads, GUI responsiveness

**Research Methodology:** current web data + rigorous verification against the local FreeCAD v26.3-dev source; multi-source validation for critical claims; confidence levels for uncertain items.

**Scope Confirmed:** 2026-07-20 (autonomous run — interactive confirmation gate skipped per task instructions; answers pre-supplied).

---

## 1. Executive Summary — The Recommendation

**Do NOT embed the MCP protocol server (FastMCP/stdio) directly inside the FreeCAD GUI process and let it call FreeCAD APIs from its own async/worker thread. That is exactly the crash mode.** FreeCAD's GUI, 3D view (Coin3D/Quarter), and — as of v26.3-dev — even parts of document recompute are **thread-affine**: touching them off the Qt main thread throws or crashes.

**Recommended architecture (split the process boundary from the thread boundary):**

1. **In-FreeCAD side (runs in the GUI process AND headless):** a thin **RPC listener** started by the addon/workbench. It accepts a request, **marshals the actual FreeCAD work onto the Qt main thread**, executes it there (holding the GIL), and returns the result. This is precisely the pattern FreeCAD's own `Mod/Web` server uses (`QTcpServer` + `QCoreApplication::postEvent` → `customEvent` runs on the main thread).
2. **MCP protocol side:** the **FastMCP server** — either an **external process** (`uvx freecad-mcp` style, the pattern both surveyed community addons use) or, if truly in-process, run via `run_async()` on a **qasync/QtAsyncio loop that shares the Qt main thread**. It translates MCP tool calls into RPC requests to the in-FreeCAD listener.
3. **Transport to the MCP client:** **streamable HTTP** for the long-lived, embedded, possibly multi-client, GUI-and-headless server. Use **stdio only** for the pure-headless `FreeCADCmd` "client spawns server as subprocess" case. **Avoid SSE** — deprecated March 2025 in favor of streamable HTTP.

**One-line rule that governs everything below:** *the network/async I/O can live on any thread, but every call that reads or mutates FreeCAD document/GUI state must be executed on the Qt main thread, under the GIL.*

**Confidence: High** for the thread-affinity constraint and the marshaling pattern (direct primary-source evidence in FreeCAD v26.3-dev). **Medium** for the exact FastMCP-in-process wiring (inferred from FastMCP docs + qasync; not yet proven in a shipped FreeCAD addon).

---

## 2. FreeCAD Thread-Safety Rules — What MUST Run on the Main Thread

This is the crux and the highest-confidence section, because v26.3-dev makes the rules **explicit in the source** rather than folklore.

### 2.1 There is now a formal async-recompute threading contract (NEW in this FreeCAD line)

`docs/references/FreeCAD/src/Doc/AsyncRecompute.dox` is a first-class design document. Key verbatim rules:

> "Async recompute allows some document recomputes to run on a worker thread." (line 7)
>
> "Code that touches Qt widgets, view providers, FreeCADGui APIs, event loops, **timers, network callbacks**, or any other thread-affine state **must stay on the main thread**." (lines 27–29)
>
> "Python execute() implementations **must not access Qt UI or FreeCADGui objects from a worker thread**." (line 45)
>
> "Worker-thread GUI access should **fail fast** through the guarded FreeCADGui and ViewObject entry points instead of proceeding silently." (lines 47–48)

Implication for the bridge: this is direct evidence that an MCP server's own I/O thread is **not** allowed to call `FreeCADGui`, view providers, or even timers/network-callbacks that mutate thread-affine state. It also names *network callbacks* explicitly — an in-process socket server's read callback must hop to the main thread before touching FreeCAD.

### 2.2 The main-thread guard is real, and it throws

`src/Gui/Application.cpp` defines a guard that is called from ViewProvider operations:

```cpp
void requireMainThread(const char* api) {
    if (App::MainThreadSignalConfig::isMainThread()) { return; }
    Base::Console().error("GUI API '%s' may only be used from the main thread.\n", api);
    throw Base::RuntimeError(std::string("GUI API '") + api
        + "' may only be used from the main thread");
}
```
(`src/Gui/Application.cpp`, ~lines 180–190; called at ~1723/1732/1741). So a background-thread GUI call now **raises a catchable Python exception** in the best case — and crashes in the worst (native Coin3D/Qt access with no guard). Confirmed guard usages exist across `src/Gui/ViewProviderDocumentObject.cpp`, `src/Gui/ApplicationPy.cpp`, `src/App/DocumentObjectPyImp.cpp`.

### 2.3 The main-thread marshaling primitive the bridge should reuse

`src/App/MainThreadSignal.h` is the mechanism FreeCAD itself uses to hop work back to the main thread. `MainThreadSignalConfig` (lines 45–90) exposes:

- `isMainThread()` — `true` iff on the GUI/main thread (returns `true` when no GUI hooks installed, i.e. **headless**).
- `invoke(std::function<void()>&& fn, bool blocking)` — run `fn` on the main thread, optionally blocking until done.

`Gui` installs the actual hooks; the marshaling is implemented (per the source dig) with `QMetaObject::invokeMethod(..., Qt::BlockingQueuedConnection)` (blocking) or `Qt::QueuedConnection` (async) via a `MainThreadInvoker` QObject living on the GUI thread (`src/Gui/Application.cpp`, `qtInvokeOnMain()` ~lines 435–447). Document-scoped signals (`signalRecomputed`, `signalChanged`, etc.) are declared as `App::MainThreadSignal<...>` in `src/App/Document.h` and deliver on the main thread automatically; **raw `App::DocumentObject` signals stay same-thread and GUI code must NOT subscribe to them** (`AsyncRecompute.dox` lines 32–35).

**Design takeaway:** the bridge does not need to invent marshaling. The in-FreeCAD RPC handler enqueues the FreeCAD work onto the main thread (mirroring `qtInvokeOnMain` / `Mod/Web`'s `postEvent`), and only I/O plumbing lives off-thread.

### 2.4 Which specific FreeCAD-Buddy tools are affected

| Phase-0 tool group (`docs/intent.md`) | Thread rule | Evidence |
|---|---|---|
| `document.*` (new/open/save), object-tree inspect | Main thread (App document mutation + main-thread signals) | `src/App/Document.h`, `MainThreadSignal.h` |
| Geometry `query.*` / `verify.shape` (Volume, BoundBox, isValid) | Prefer main thread; some pure-OCCT reads on a *copied* shape may be worker-safe only if the object opts in via `canRecomputeOnWorker()` | `AsyncRecompute.dox` §scope; treat as main-thread by default |
| **Screenshot / 3D view capture** | **Main thread, hard requirement** (Coin3D/Quarter/SoQt view is GUI-thread-affine; `requireMainThread` applies) | `src/Gui/View3DInventor*.cpp`, `Gui/Quarter/*`, `src/Gui/Application.cpp` guard |
| Python execution sandbox (`FreeCAD.exec`) | Main thread + hold GIL; if it can touch GUI it MUST be main thread | `src/Gui/PythonConsole.cpp`, §3 below |
| `export.*` (STEP/STL) | Main thread by default (document read + OCCT writers) | `src/App/Document.cpp` |

**Confidence: High** — every row is backed by the v26.3-dev source.

---

## 3. Python GIL Constraints

- FreeCAD acquires/releases the GIL from C++ via RAII wrappers in `src/Base/Interpreter.h`: **`Base::PyGILStateLocker`** (`PyGILState_Ensure`/`Release`, ~lines 183–202) and **`Base::PyGILStateRelease`** (`PyEval_SaveThread`/`RestoreThread`, ~lines 213–234). The bridge's C++-adjacent paths, and any place it calls Python from a non-Python thread, must take `PyGILStateLocker`.
- **Recompute keeps the GIL for its whole duration** so Python-backed features stay serialized even when recompute runs on a worker thread (`src/App/Document.cpp` ~line 2838, plus the comment block ~2832–2838; and `AsyncRecompute.dox` lines 39–41: *"The GIL is kept for the duration of document recompute so Python execution stays serialized, but that does not make GUI access worker-safe."*). **Critical nuance: GIL-held ≠ thread-safe for GUI.** Holding the GIL does not make it legal to touch Qt/Coin from that thread.
- **Practical consequence for an in-process asyncio server:** Python asyncio and Qt both run on the main thread; while a synchronous FreeCAD call runs under the GIL on the main thread, the event loop is blocked for that duration. Long operations (big recompute, STEP export) will freeze the async loop unless offloaded — but they can only be offloaded to a worker if the object is `canRecomputeOnWorker()`-safe; otherwise they run on the main thread and *will* pause GUI/async responsiveness. Keep tool calls short, or run the whole MCP server out-of-process (recommended) so only the RPC round-trip blocks, not the client.

**Confidence: High.**

---

## 4. Qt Event-Loop Integration & the GUI-vs-Headless Split

### 4.1 GUI mode has a Qt event loop; `FreeCADCmd` does NOT

- **GUI (`src/Main/MainGui.cpp` → `Gui::Application::runApplication()`):** creates `QApplication`, schedules startup with `QTimer::singleShot(0, ...)`, and blocks in **`QApplication::exec()`** (`src/Gui/Application.cpp` ~line 2583, inside `tryRunEventLoop`). A running Qt event loop exists and owns the main thread.
- **Headless (`src/Main/MainCmd.cpp`):** grep confirms it calls only `Application::runApplication();` (line 135) with **no `QApplication` and no `exec()`**. `App::Application::runApplication()` in Cmd mode does not start a Qt event loop. **There is no Qt event loop in `FreeCADCmd` by default.** (`MainThreadSignalConfig::isMainThread()` correctly returns `true` here because no GUI hooks are installed — every call is "on the main thread" trivially.)

**This single fact forces the "one server, two run-modes" design:** you cannot assume a Qt loop to attach asyncio to in headless mode.

### 4.2 asyncio-in-Qt: qasync / QtAsyncio (for the in-GUI case)

- **qasync** implements PEP-3156 so `asyncio` coroutines run **directly inside the Qt event loop, on the main thread** — one loop, GUI stays responsive while awaits run (`github.com/CabbageDevelopment/qasync`). PySide6 ships an equivalent, **`QtAsyncio`**.
- **Caveat (Medium confidence):** the documented qasync setup has qasync **own the loop from startup** (`asyncio.run(main(app), loop_factory=QEventLoop)` on 3.11+, or `qasync.run(...)`). It does **not** clearly document attaching asyncio to an **already-running** `app.exec()` loop — which is exactly the FreeCAD-embed situation, because FreeCAD already called `QApplication::exec()` before the addon loads. Attaching to an already-running Qt loop is fragile.
- **The robust in-GUI pattern is therefore NOT "start an asyncio loop"** but the FreeCAD-native one: run the async/socket server on its **own thread**, and use `QTimer.singleShot(0, fn)` / `QMetaObject.invokeMethod(..., QueuedConnection)` to marshal each FreeCAD call onto the already-running main loop. This sidesteps the "attach-to-running-loop" problem entirely and matches FreeCAD's own `MainThreadInvoker`.

### 4.3 The proven in-process server precedent: `Mod/Web`

FreeCAD already embeds a TCP server that executes Python **on the main thread**:
- `src/Mod/Web/App/Server.h`: `class AppServer : public QTcpServer`.
- `src/Mod/Web/App/Server.cpp`: `readClient()` either handles directly or `QCoreApplication::postEvent(this, event)`; `customEvent()` runs **on the main thread** and calls `runPython(msg)`; `getRequest()` takes `Base::PyGILStateLocker` before touching Python.

This is the template for the in-FreeCAD RPC listener: accept off-thread, `postEvent`/`invokeMethod` to the main thread, execute FreeCAD work there under the GIL, reply.

**Confidence: High** (Web precedent, entry points) / **Medium** (qasync attach caveat).

### 4.4 Deferred start — the documented crash and its fix

The community addon `spkane/freecad-addon-robust-mcp-server` (v0.6.2 release notes) documents the exact failure this research must prevent, verbatim:

> "Fixed race condition where the bridge could start before `FreeCAD.GuiUp` was `True`, causing Qt operations to run on a background thread and crash FreeCAD."
> "Auto-start is now deferred with `QTimer.singleShot()` to allow the GUI to stabilize."

**Mandatory for Phase 0:** gate auto-start on `FreeCAD.GuiUp` and defer initialization via `QTimer.singleShot()` so the GUI is fully up and the server's main-thread marshaling target exists before any tool can fire.

---

## 5. Transport Choice — stdio vs SSE vs Streamable HTTP

FastMCP (`gofastmcp.com/deployment/running-server`) selects transport via `mcp.run(transport=...)`:
- **stdio** (default): client **spawns the server as a subprocess** and talks JSON-RPC over stdin/stdout. Zero infra; single local client; "the client cannot outrace it." **Rule: never log to stdout** (corrupts the stream) — log to stderr.
- **streamable HTTP** (`transport="http"`): server runs on a URL, **multiple concurrent clients**, bidirectional, resumable (`Last-Event-ID`), auth-capable. The 2025-03-26+ spec standard.
- **SSE**: legacy two-endpoint 2024-11-05 design, **deprecated March 2025** in favor of streamable HTTP — **do not use for new work**.

**Mapping to FreeCAD-Buddy's two modes:**

| Run mode | Recommended transport | Why |
|---|---|---|
| **In-GUI, long-lived** (FreeCAD open, addon serving; possibly a desktop client + CI agent both connecting) | **Streamable HTTP** | Server outlives any single client; a subprocess-spawned stdio server can't attach to an *already-running* GUI process. HTTP lets an external MCP client connect to the live FreeCAD. Multi-client + resumable. |
| **Headless `FreeCADCmd` for CI / one-shot agent jobs** | **stdio** (or HTTP if a persistent job service, per Phase 4) | Client spawns `FreeCADCmd -c run_server.py` as a subprocess; stdio is simplest and needs no ports. Phase 4's "job API as a service" later graduates this to HTTP. |
| **Never** | SSE | Deprecated. |

**Async wiring:** FastMCP's `run()` "cannot be called from inside an async function because it creates its own event loop." Inside an existing loop use **`await mcp.run_async(transport="http", ...)`**, or mount the ASGI app via **`mcp.http_app()`** into a host ASGI server (uvicorn/Starlette). For the recommended out-of-process design this is irrelevant (the MCP process owns its own loop with `run()`); it only matters if you insist on truly in-process embedding with qasync/QtAsyncio, where you'd `run_async()` on the shared loop.

**Confidence: High.**

---

## 6. Recommended Architecture (Phase-0 blueprint)

```
                 MCP client (Claude Code / agent)
                          │  MCP over  ── stdio (headless subprocess)
                          │            └─ streamable HTTP (in-GUI, long-lived)
                 ┌────────▼─────────┐
                 │  FastMCP server  │   tool layer: query.* document.* export.* verify.*
                 │  (FastMCP SDK)   │   • external process (recommended), OR
                 └────────┬─────────┘   • in-process on qasync/QtAsyncio (advanced)
                          │  RPC (localhost TCP / QLocalServer)
        ┌─────────────────▼──────────────────┐
        │  In-FreeCAD RPC listener (addon)    │  off-thread accept
        │  ── marshal to Qt main thread ──►   │  QTimer.singleShot / invokeMethod
        │     (mirror Mod/Web postEvent)      │  (headless: call inline, no loop)
        └─────────────────┬──────────────────┘
                          │  MAIN THREAD, GIL held (PyGILStateLocker)
              ┌───────────▼────────────┐
              │  FreeCAD Python API     │  App/Gui/Part/Sketcher/PartDesign
              └────────────────────────┘
```

**Rules baked in:**
1. **Process split ≠ thread split.** Even a fully in-process FastMCP must marshal FreeCAD calls to the Qt main thread (§2.3, §4.3).
2. **Single tool layer, two transports.** One FastMCP `mcp` object; `transport` chosen by a flag/env: `http` when `FreeCAD.GuiUp`, `stdio` when headless. Shared tool implementations.
3. **Headless has no Qt loop (§4.1)** → the RPC "marshal to main thread" step degrades to a direct in-line call (`isMainThread()` is trivially true). Same code path, no Qt dependency required in `FreeCADCmd`.
4. **Deferred, guarded start (§4.4):** auto-start only after `FreeCAD.GuiUp` via `QTimer.singleShot`.
5. **Every FreeCAD call is short or offloaded.** Long ops block the main thread and the async loop; keep tools atomic (aligns with Phase-2 "one operation per confirmation").

### Reuse-Map alignment (per `docs/intent.md`)
- MCP plumbing: **adopt FastMCP** (official SDK) — matches the intent's "partial reuse: their transport/embedding patterns, our tool layer."
- Embedding pattern: **adopt FreeCAD's own `Mod/Web` main-thread marshaling** and the community addons' `QTimer.singleShot` + `GuiUp` guard rather than inventing.
- Two surveyed community servers (`neka-nat/freecad-mcp`, `spkane/...`) both use **external MCP process + in-FreeCAD RPC (XML-RPC/socket)** — this validates the recommended split as the field-proven pattern; adopt the pattern, keep the verify-first tool taxonomy as the genuine invention.

---

## 7. Risks & Open Questions

| Risk / open question | Mitigation / next step | Confidence |
|---|---|---|
| Async recompute (v26.3-dev) may run object `execute()` on a worker; a tool that reads mid-recompute could see inconsistent state | Default all tools to main-thread execution; only opt specific pure-read shape queries into worker via `canRecomputeOnWorker()` after testing | High risk-is-real / Medium on mitigation detail |
| qasync/QtAsyncio attaching to FreeCAD's **already-running** `exec()` loop is under-documented | Prefer external-process FastMCP + RPC (avoids the problem). If in-process needed, prototype `QtAsyncio` attach on a spike and fall back to a server-thread + `invokeMethod` | Medium |
| Version drift: these guards/`AsyncRecompute.dox` are **v26.3-dev-specific**; 0.21/1.0 lack them (calls may crash silently instead of throwing) | Pin CI matrix; keep a thin adapter; treat "main-thread only" as the rule on ALL versions (safe superset) | High |
| stdio + accidental stdout logging corrupts protocol | Enforce stderr-only logging in the server bootstrap; lint for `print()` | High |
| Blocking a long export/recompute freezes GUI + async loop | Out-of-process server (only RPC blocks) + atomic tools; progress via `signalRecomputed` main-thread signal | High |
| Two community addons' RPC uses XML-RPC (heavier); is a leaner `QLocalServer`/JSON-RPC better? | Benchmark in Phase 0; `Mod/Web` shows `QTcpServer`/`postEvent` is sufficient and native | Low priority |

---

## 8. Sources

**Primary — local FreeCAD v26.3-dev source (`docs/references/FreeCAD/`):**
- `version.json` — confirms v26.3-dev (post-1.0).
- `src/Doc/AsyncRecompute.dox` — formal async-recompute threading contract (worker-safety, main-thread-only GUI/timer/network rules, fail-fast).
- `src/App/MainThreadSignal.h` — `MainThreadSignalConfig::isMainThread()/invoke()` marshaling primitive.
- `src/Gui/Application.cpp` — `requireMainThread()` guard; `qtInvokeOnMain()` / `MainThreadInvoker`; `tryRunEventLoop()` → `QApplication::exec()`.
- `src/App/Document.cpp` / `src/App/Document.h` — recompute GIL hold; `App::MainThreadSignal<>` document signals.
- `src/Base/Interpreter.h` — `PyGILStateLocker` / `PyGILStateRelease`.
- `src/Gui/PythonConsole.cpp` — Python execution under GIL on GUI thread.
- `src/Main/MainGui.cpp` vs `src/Main/MainCmd.cpp` — GUI event loop vs no-event-loop headless (`runApplication();`, line 135).
- `src/Mod/Web/App/Server.{h,cpp}` — `QTcpServer` + `postEvent`/`customEvent` main-thread execution precedent.

**Web:**
- [Running a FastMCP Server — transports, run_async, http_app](https://gofastmcp.com/deployment/running-server)
- [MCP stdio vs HTTP vs SSE — which to choose (2026)](https://startdebugging.net/2026/07/mcp-stdio-vs-http-vs-sse-transport-which-to-choose/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [qasync — asyncio in Qt](https://github.com/CabbageDevelopment/qasync)
- [neka-nat/freecad-mcp — external MCP process + in-FreeCAD RPC](https://github.com/neka-nat/freecad-mcp)
- [spkane/freecad-addon-robust-mcp-server — GuiUp race fix, QTimer.singleShot deferred start](https://github.com/spkane/freecad-addon-robust-mcp-server/releases)
- [ATOI-Ming/FreeCAD-MCP — in-FreeCAD MCP server + GUI panel](https://github.com/ATOI-Ming/FreeCAD-MCP)
