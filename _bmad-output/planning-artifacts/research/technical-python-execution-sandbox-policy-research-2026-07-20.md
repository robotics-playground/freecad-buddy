---
stepsCompleted: ['step-01-init', 'research', 'synthesis']
inputDocuments: ['docs/intent.md', 'docs/references/FreeCAD/src']
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'Python execution sandbox policy for an AI-driven FreeCAD bridge'
research_goals: "Resolve the contradiction between Phase 0's 'Python execution sandbox' tool and the Risks section's 'no free-form exec in mutation path'. Recommend what exec capability to expose, in which phases, with which guardrails."
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Python Execution Sandbox Policy for an AI-Driven FreeCAD Bridge

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** technical
**Blocks:** Phase 0 tool design (FreeCAD Bridge & Test Harness)

---

## Research Overview

`docs/intent.md` contains an unresolved contradiction that blocks Phase 0 tool design:

- **Phase 0 "Specific"** (line 189) lists a **"Python execution sandbox"** as one of the bridge tools to build.
- **Risks & Mitigations** (line 322) mandates a **"Typed tool layer (no free-form `exec` in mutation path)"** to mitigate LLM API hallucination.
- **Phase 4 "Specific"** (line 276) again lists **"sandboxed execution"** as a safety rail for the autonomous service.

These are not actually in conflict once "sandbox" is defined precisely. The word is doing two different jobs: in Phase 0 it means *"a tool that runs Python against the FreeCAD API"*, and in the Risks table it means *"do not let the LLM's raw output become the mutation path."* The real question this research answers is: **what execution capability should the bridge expose, in which phases, and behind which guardrails — given that a truly secure in-process Python sandbox does not exist?**

This report establishes four findings from web sources and the local FreeCAD source tree, then gives a concrete, phase-gated policy.

**Methodology.** Evidence was gathered from (1) primary Python security documentation and CPython issue trackers, (2) the RestrictedPython project and its CVE history, (3) recent (2025-2026) MCP-security and untrusted-code-execution literature, and (4) direct reading of the local FreeCAD source at `docs/references/FreeCAD/src` to establish how FreeCAD itself executes user macros. Every non-obvious claim is cited.

---

## Finding 1 — In-process Python "sandboxing" is not a security boundary

The consensus across primary sources is unambiguous: **you cannot securely sandbox untrusted Python inside the same interpreter that runs your trusted code.** Dynamic-language introspection defeats every language-level restriction.

### 1a. Audit hooks (`sys.addaudithook`) are monitoring, not enforcement

Python's audit-hook mechanism (PEP 578) is frequently proposed as a sandbox. The CPython maintainers explicitly reject this use:

> "Audit hooks are not suitable for implementing a 'sandbox'. ... malicious code can trivially disable or bypass hooks added using this function." — CPython issue #87604 / bugs.python.org #43438; PEP 578.

Audit hooks are *advisory notification*: useful for logging and intrusion detection, useless as a security boundary because the sandboxed code shares the interpreter and can unregister or route around the hook. PEP 551 states that any security-sensitive hook must be installed via the C API `PySys_AddAuditHook()` **before** the runtime initializes and that modules permitting arbitrary memory access (e.g. `ctypes`) must be removed entirely — a bar a plugin-embedded bridge cannot meet.

### 1b. RestrictedPython is a "trusted-environment helper", not a sandbox

The RestrictedPython project (Zope/Plone) is the most mature language-level restrictor, and its own documentation is careful:

> "RestrictedPython is **not a sandbox system** or a secured environment, but it helps to define a trusted environment and execute untrusted code inside of it." — RestrictedPython docs / Plone security docs.

It restricts *at compile time* (custom AST compile + a security manager checking every attribute access and call). It still ships CVEs against exactly the class of bypass it is meant to prevent — e.g. **CVE-2024-47532** (information leakage via `AttributeError.obj` and the `string` module) and prior `safer_getattr` breakout fixes. A restrictor that keeps patching introspection escapes is proof the attack surface is open-ended.

### 1c. Blacklisting builtins/imports is trivially bypassable

The classic escape: even with `os` deleted and `__import__` blocked, attacker code walks the class tree —
`().__class__.__bases__[0].__subclasses__()` — to recover a class whose module globals still hold `os`/`subprocess`, then reconstructs arbitrary execution. As one primary write-up puts it, dynamic languages "allow you to do funky things, like walking up a class tree and dancing across frames," and securing this inside CPython would mean auditing 126,000+ lines of C — the reason the historical `pysandbox` project was abandoned as unfixable (Healey, *Running Untrusted Python Code*).

**Implication for the bridge.** Any "sandbox" implemented by filtering strings, deleting builtins, or installing audit hooks *in the FreeCAD process* provides **defense-in-depth at best and false security at worst.** It must never be the sole control, and it must never be described in the intent doc as a security boundary.

---

## Finding 2 — Real isolation lives at the OS/VM layer (and this is what Phase 4 needs)

Every serious source converges on the same answer: to run untrusted code safely, **restrict what the OS lets the process do**, not what the language exposes.

The recommended ladder, from the untrusted-code and MCP-security literature (Fly.io, Morph/nsjail, gVisor docs, MCP security guides, 2025-2026):

| Mechanism | What it isolates | Overhead | Fit for FreeCAD Buddy |
|-----------|------------------|----------|-----------------------|
| **Separate subprocess** + `setrlimit` (CPU/mem/file) + timeout | Crash/hang/resource containment; **not** a security boundary alone | negligible | Baseline for all headless exec |
| **seccomp-bpf** syscall filter (allow ~`read/write/exit/sigreturn`) | Kernel attack surface | near-zero | Strong add-on on Linux CI |
| **nsjail** (namespaces + cgroups + rlimits + seccomp) | Filesystem, network, PIDs, syscalls | near-zero | Good for CI job runners |
| **gVisor** (userspace kernel, ~20 host syscalls) | Host kernel almost entirely | 5-20% CPU | Recommended for untrusted code / multi-tenant |
| **microVM** (Firecracker) / container per job | Full VM boundary | higher | Phase 4 service, per-job |

Key guidance from the MCP-security corpus (arXiv 2602.15945 / 2606.29073, CSA Agentic MCP Best Practices, NSA/CISA MCP security guidance 2026):

> "MCP servers should execute in isolated runtime environments — containers, micro-VMs, or restricted language runtimes with system-call filtering — with controls enforced at the container or hypervisor layer **rather than relying on server-side self-enforcement.**"

The same literature identifies **Arbitrary Code Execution (ACE)** as a top MCP risk class and prescribes: least privilege, tool allowlisting, input/output validation, explicit user consent for sensitive actions, and full audit logging — the exact rails Phase 4 already names.

**Implication.** The "sandboxed execution" rail in Phase 4 (line 276) is legitimate and must be an **OS/VM-level** sandbox (subprocess + rlimits + seccomp/nsjail, escalating to gVisor/microVM-per-job for the public/agent-to-agent service), *not* an in-process Python trick.

---

## Finding 3 — FreeCAD itself runs macros with ZERO sandboxing (full trust)

Direct reading of the local FreeCAD source confirms there is **no** language-level sandbox to inherit, adapt, or rely on. FreeCAD treats every macro and scripted command as fully trusted host code.

- **`InterpreterSingleton::runString`** (`docs/references/FreeCAD/src/Base/Interpreter.cpp:233-250`) loads the `__main__` module, gets its dict, and calls `PyRun_String(sCmd, Py_file_input, dict, dict)` — i.e. user code executes **in the real `__main__` namespace with the full standard builtins**, sharing state with FreeCAD itself.
- **`runFile`** (`Interpreter.cpp:436-476`) does the same via `PyRun_File(... Py_file_input, dict, dict)` for `.FCMacro` files.
- **Macro execution** (`docs/references/FreeCAD/src/Gui/Macro.cpp:403`) simply calls `Base::Interpreter().runFile(sName, this->localEnv)` — the GUI "Execute macro" path is a thin wrapper over that same unrestricted run.
- A repo-wide grep for `addaudithook`, `audit`, `RestrictedPython`, `sandbox`, or `untrusted` in `src/Base/Interpreter.cpp` returns **no matches**. FreeCAD ships no execution sandbox at all.
- The only restricted-evaluation surface in FreeCAD is the **expression engine** (`src/App/Expression.cpp`), which is a *custom, non-Python* parser/evaluator that even there notes "For security reason, restrict supported types" (`Expression.cpp:1373,1396`). This is a deliberately tiny typed grammar, not sandboxed Python — a useful precedent for our typed-tool design, not for exec.

**Implication.** Running arbitrary Python "inside FreeCAD" means running it with FreeCAD's full OS privileges. There is nothing to lean on inside the process. This is why comparable projects that expose `execute_python` are effectively granting host RCE (Finding 4), and why our isolation must come from outside the interpreter.

---

## Finding 4 — Comparable AI-CAD / agent projects expose exec unsafely; the safe minority use typed tools + namespace escape hatch

Surveying the existing FreeCAD/CAD MCP ecosystem (neka-nat, bonninr, proximile, contextform, sergiudanstan; plus blender-mcp) shows a clear split and a clear lesson.

**The common (unsafe) pattern — arbitrary `execute_python`:**
- `freecad_execute_python` / `execute_code` tools "allow arbitrary Python execution by design — only use in trusted environments." Code flows LLM → MCP socket → FreeCAD addon → `exec()` with **full FreeCAD Python API and, by extension, full host OS access.**
- `blender-mcp` issue #207 documents exactly this: `execute_blender_code` runs LLM-supplied Python via `exec()` "with no sandboxing, validation, or restriction," yielding host RCE. This is the failure mode our Risks table is trying to prevent.

**The naive mitigation that does NOT work — import blacklists:**
- Some servers add "security checks to prevent dangerous module imports (`os`, `subprocess`, etc.)." Per **Finding 1c**, an import/builtin denylist inside the interpreter is bypassable via `__subclasses__` traversal. Do not rely on it as the boundary.

**The pattern worth copying — typed tools + a *namespaced* escape hatch:**
- The most mature server exposes **~165 typed tools across 15 modules** (documents, primitives, booleans, sketching, PartDesign, mesh, FEM, BIM…), and treats `execute_code` as "**the escape hatch** that makes everything not covered by the typed tools possible." That is the right architecture: typed tools are the default surface; raw code is a narrow, explicit, separately-governed fallback.
- The recommended hardening for that fallback (from the blender-mcp and LLM-agent-sandbox literature) is **namespace restriction** — run against only the CAD API modules — but this is treated as *reduction of accidental blast radius*, not as a security boundary. The security boundary is still the OS/VM layer per Finding 2.

**Implication.** Prior art validates intent.md's own instinct: the **typed tool layer is the correct primary surface** (matching the `query.*/sketch.*/feature.*/verify.*` taxonomy at lines 50, 232). Free-form exec, where offered, must be (a) opt-in, (b) OS-isolated, (c) audited, and (d) kept out of the confirmed mutation path.

---

## Synthesis — Resolving the Contradiction

The contradiction dissolves once "sandbox" is split into its two meanings and mapped onto the tool taxonomy:

| intent.md phrase | What it actually means | Verdict |
|------------------|------------------------|---------|
| Phase 0 "Python execution sandbox" (l.189) | A tool that runs Python against the FreeCAD API for bring-up/testing | **Keep, but rename and scope it** as `debug.exec` — trusted-operator only, never the AI mutation path |
| Risks "no free-form `exec` in mutation path" (l.322) | The LLM's raw output must not directly drive geometry mutation | **Enforce** — mutations go only through typed `sketch.*/feature.*` tools |
| Phase 4 "sandboxed execution" (l.276) | OS/VM isolation of the headless service | **Keep** — implement at subprocess/seccomp/gVisor layer, not in-process |

These are complementary, not contradictory: a **trusted operator-only exec tool** (for developer bring-up and Phase 1 read-only introspection) can coexist with a hard rule that **the AI's design mutations flow exclusively through typed tools**, all wrapped by **OS-level isolation** once the bridge runs untrusted/agent-driven workloads.

---

## Recommendation — Phase-Gated Exec Policy

### The policy in one line
**Typed tools are the only mutation path for the AI. Raw Python exec is a trusted-operator debug capability behind a capability flag, is never exposed to the model in the confirmed-mutation path, and — once the bridge runs untrusted or agent-driven code (Phase 4) — is executed only inside OS/VM isolation with rlimits, seccomp, timeouts, and full audit logging.**

### What to expose, per phase

**Phase 0 — Foundation**
- Build the typed `query.*`, `document.*`, `export.*`, `verify.*` tools as the real surface.
- Rename the "Python execution sandbox" tool to **`debug.exec`** and scope it explicitly:
  - Disabled by default; enabled only by a bridge config/env flag (e.g. `FREECAD_BUDDY_ALLOW_EXEC=1`) set by the human operator, never by the model.
  - Not registered in the MCP tool list when the flag is off, so an LLM cannot discover or call it.
  - Every call written to an **append-only audit log** (code + timestamp + caller) from day one — Phase 4 requires this anyway.
  - Purpose: developer bring-up, reproducing bugs, and executing the golden-model test scripts in CI (which are trusted, authored by us).
- Document in intent.md: *`debug.exec` is a trusted-operator tool, not a security boundary and not an AI capability.*

**Phase 1 — Assistant (read-only)**
- No exec exposed to the model. If any introspection needs Python, it runs through **read-only typed `query.*` tools**, not raw exec. Keeps the "zero mutation tools" guarantee (line 210) literally true.

**Phase 2 — Copilot (first mutations)**
- Mutations flow **only** through typed `sketch.*/feature.*` tools — this is the direct implementation of "no free-form exec in mutation path."
- The typed layer gives the deterministic per-op geometry assertions, TNP re-resolve checks, and exact-undo that Phase 2 exit criteria demand (lines 236-238). Raw exec cannot offer those guarantees and is therefore architecturally excluded from the mutation path, not merely discouraged.
- `debug.exec` remains operator-only and out of the model's toolset.

**Phase 3 — Designer**
- Same rule: the plan is a sequence of **typed operations**, executed and verified per step. No raw exec in the loop.

**Phase 4 — Autonomous headless service (untrusted / agent-to-agent)**
- This is where OS/VM isolation becomes mandatory, because the caller may be another agent, i.e. untrusted:
  - Run each job's FreeCAD execution in a **separate process** with `setrlimit` (CPU time, memory, file size) and a hard wall-clock **timeout** + **iteration cap** (already named at line 276).
  - Add a **seccomp-bpf / nsjail** profile on Linux CI: no network, restricted filesystem (scratch dir only), minimal syscalls.
  - For the public / multi-tenant-ish or fully agent-driven surface, escalate to **gVisor or a microVM/container per job** (the untrusted-code standard from Finding 2).
  - **`debug.exec` stays disabled** in the service; if a break-glass exec is ever needed operationally, it runs inside the same OS sandbox and is audit-logged.
  - Structured error on every failed job; audit log of every operation (line 276) — satisfied by the Phase 0 logging built early.

### Guardrails summary (defense-in-depth, ordered by strength)

1. **Architectural (primary):** typed tool layer is the sole AI mutation path; raw exec is not a model-facing tool in any AI phase.
2. **Capability-gating:** `debug.exec` off by default, human-flag-enabled, never auto-listed to the model.
3. **OS/VM isolation (the real security boundary):** subprocess + rlimits + timeout → seccomp/nsjail → gVisor/microVM per job as trust decreases (Phase 4).
4. **Namespace reduction (defense-in-depth only):** if `debug.exec` runs, restrict globals to FreeCAD API modules — reduces accidental blast radius, **not** a boundary (Finding 1c).
5. **Audit + limits:** append-only log of all exec/mutations; iteration caps; resource caps — from Phase 0.
6. **Explicitly rejected as boundaries:** in-process `sys.addaudithook`, RestrictedPython, and import/builtin blacklists. Permitted only as *monitoring/hardening*, never described as the sandbox.

### Concrete doc edits proposed for `docs/intent.md`

- **Line 189:** replace "Python execution sandbox" with "**trusted-operator Python exec tool (`debug.exec`, disabled by default, audit-logged; not an AI mutation path)**".
- **Line 322 (Risks):** already correct — reinforce that typed tools are the *only* AI mutation path and that exec isolation is an OS/VM concern, cross-referencing Phase 4.
- **Line 276 (Phase 4):** clarify "sandboxed execution" = **OS/VM isolation (subprocess + rlimits + seccomp/nsjail, gVisor/microVM per job for agent-to-agent)**, not in-process restriction.

---

## Sources

**Primary Python security documentation**
- CPython issue #87604 / bugs.python.org #43438 — `sys.addaudithook()` limitations: https://github.com/python/cpython/issues/87604 , https://bugs.python.org/issue43438
- PEP 551 – Security transparency in the Python runtime: https://peps.python.org/pep-0551/
- Python `sys` docs (audit hooks): https://docs.python.org/3.10/library/sys.html

**RestrictedPython**
- RestrictedPython (Zope) — "not a sandbox system": https://github.com/zopefoundation/RestrictedPython , https://restrictedpython.readthedocs.io/
- Plone Sandboxing & RestrictedPython: https://5.docs.plone.org/develop/plone/security/sandboxing.html
- RestrictedPython on PyPI (CVE history incl. CVE-2024-47532): https://pypi.org/project/RestrictedPython/

**Untrusted-code execution / OS isolation**
- Healey, *Running Untrusted Python Code* (`__subclasses__` bypass, pysandbox failure, seccomp/rlimit/microVM): https://healeycodes.com/running-untrusted-python-code
- Fly.io, *Sandboxing and Workload Isolation*: https://fly.io/blog/sandboxing-and-workload-isolation/
- Morph, *nsjail: Lightweight Linux Sandboxing for AI Code Execution*: https://www.morphllm.com/nsjail-sandbox
- Container runtime security (gVisor / Kata / crun): https://www.systemshardening.com/articles/linux/linux-container-runtime-alternatives/

**MCP / agent-tool security**
- *From Tool Orchestration to Code Execution: A Study of MCP Design Choices* (arXiv 2602.15945): https://arxiv.org/html/2602.15945v1
- *Benchmarking Security Invariants in MCP-Style Agent Runtimes* (arXiv 2606.29073): https://arxiv.org/html/2606.29073
- CSA Agentic MCP Security Best Practices: https://labs.cloudsecurityalliance.org/agentic/agentic-mcp-security-best-practices-v1/
- NSA/CISA-hosted MCP security considerations (2026): https://media.defense.gov/2026/Jun/02/2003943289/-1/-1/0/CSI_MCP_SECURITY.PDF

**Comparable AI-CAD / agent projects**
- neka-nat/freecad-mcp: https://github.com/neka-nat/freecad-mcp
- bonninr/freecad_mcp: https://github.com/bonninr/freecad_mcp
- proximile/FreeCAD-MCP (Docker-containerized headless exec): https://github.com/proximile/FreeCAD-MCP
- blender-mcp issue #207 — unrestricted arbitrary code execution via `execute_blender_code`: https://github.com/ahujasid/blender-mcp/issues/207
- dida.do, *Setting Up a Secure Python Sandbox for LLM Agents*: https://dida.do/blog/setting-up-a-secure-python-sandbox-for-llm-agents

**Local FreeCAD source (cited inline)**
- `docs/references/FreeCAD/src/Base/Interpreter.cpp` — `runString` (l.233-250), `runFile` (l.436-476): unrestricted `PyRun_String/PyRun_File` in `__main__`
- `docs/references/FreeCAD/src/Gui/Macro.cpp:403` — macro execution wraps `runFile`
- `docs/references/FreeCAD/src/App/Expression.cpp:1373,1396` — FreeCAD's only restricted (non-Python, typed) evaluation surface
