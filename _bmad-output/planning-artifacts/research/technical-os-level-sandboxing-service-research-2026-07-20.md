---
stepsCompleted: ['step-01-init', 'research', 'synthesis']
inputDocuments: ['docs/intent.md', '_bmad-output/planning-artifacts/research/technical-python-execution-sandbox-policy-research-2026-07-20.md']
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'OS-level sandboxing for a headless FreeCAD agent service (Linux and Windows)'
research_goals: "docs/intent.md Phase 4 lists 'sandboxed execution' as a safety rail without a mechanism. Recommend concrete per-platform OS-level isolation stacks for running FreeCAD worker processes that may execute AI-derived operations, for the single-tenant/local-first Phase 4 service."
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: OS-Level Sandboxing for a Headless FreeCAD Agent Service (Linux and Windows)

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** technical
**Blocks:** Phase 4 safety-rail design (Autonomous Agent — Full Design Loop as a Service)

---

## Research Overview

`docs/intent.md` Phase 4 ("Specific", line 276) names **"sandboxed execution"** as a safety rail for the headless FreeCAD agent service, alongside resource limits, iteration caps, and audit logging — but supplies **no mechanism**. The Phase 4 self-deception table (line 174) and the "no free-form `exec` in mutation path" risk (line 322) establish *what* must be contained; this report establishes *how*, at the OS layer, on the two platforms the project will run on.

This topic is the **OS/VM-level complement** to the sibling report *Python Execution Sandbox Policy* (`technical-python-execution-sandbox-policy-research-2026-07-20.md`). That report's Finding 2 concluded that "real isolation lives at the OS/VM layer" and explicitly handed off the per-platform stack decision to this research. The division of labour is:

- **Sibling report (in-process policy):** typed tools are the only AI mutation path; raw `exec` is a trusted-operator `debug.exec` capability; in-process Python restriction (audit hooks, RestrictedPython, blacklists) is *never* a security boundary.
- **This report (OS-level policy):** given that the security boundary must be external to the interpreter, *which* OS primitives contain a FreeCAD worker process on Linux and on Windows, for the **single-tenant / local-first** service that intent.md scopes (Out of Scope, line 335: "Cloud multi-tenant SaaS hosting … Phase 4 service is single-tenant/local-first").

**Threat model for Phase 4.** The FreeCAD worker executes a plan of typed operations derived from an AI-generated spec. Even with no raw `exec` exposed, the worker (a) runs a full OCCT geometry kernel plus arbitrary parametric expressions, (b) reads a spec and writes exports/reports, and (c) in the agent-to-agent case (line 282) is *driven by another agent* — i.e. the request is untrusted input even if the code path is typed. The realistic threats are therefore: **runaway resource consumption** (a pathological loft/boolean or a self-repair loop that never converges — memory/CPU/disk exhaustion, the "50-job soak, memory growth < 20%" criterion at line 283), **data exfiltration / unexpected egress** (a compromised or manipulated worker phoning home or reading host files outside its job dir), **host filesystem tampering**, and **crash/hang containment** (one bad job must not take down the service). This is *containment and resource governance for a mostly-trusted-code / untrusted-input worker*, not defence against a determined multi-tenant attacker — a distinction that drives the "start lightweight, escalate on demand" recommendation below.

**Methodology.** Evidence gathered from (1) primary tooling docs (nsjail, bubblewrap, Docker seccomp/capabilities, Firecracker/gVisor), (2) Microsoft Learn primary docs on Windows isolation primitives (AppContainer, Win32 app isolation, Windows Sandbox, WSL2/Hyper-V Firewall), (3) 2025-2026 AI-agent-sandboxing practitioner literature, and (4) FreeCAD-specific containerization evidence (FreeCAD FC-Worker, linuxserver/docker-freecad, offscreen-rendering PR). Non-obvious claims are cited inline.

---

## Finding 1 — The isolation ladder is the same everywhere: subprocess → syscall filter → jail → microVM/VM

Across every 2025-2026 source, untrusted-workload isolation is a **ladder ordered by strength and cost**, and the guidance is uniform: *pick the lowest rung that covers your threat model; escalate only when trust decreases.*

| Rung | Mechanism (Linux) | What it contains | Overhead | Fit for single-tenant FreeCAD worker |
|------|-------------------|------------------|----------|--------------------------------------|
| 0 | **Separate subprocess** + `setrlimit` + wall-clock timeout | Crash / hang / resource; **not** a security boundary alone | negligible | Mandatory baseline for every headless job |
| 1 | **seccomp-bpf** syscall allowlist | Kernel attack surface | near-zero | Strong, cheap add-on |
| 2 | **cgroups v2** (CPU, memory, pids, IO) | Resource exhaustion, fork bombs | near-zero | Directly satisfies line 283 soak/leak criterion |
| 3 | **Jail: nsjail / bubblewrap** (namespaces + cgroups + rlimits + seccomp, no daemon) | Filesystem, network, PIDs, syscalls | near-zero | **Recommended primary for local-first Linux** |
| 4 | **Container: Docker/OCI** (same primitives, packaged + reproducible image) | As above + dependency pinning | low | Recommended for CI and reproducible worker image |
| 5 | **gVisor** (userspace kernel, ~20 host syscalls) | Host kernel almost entirely | 10-30% I/O, ~0 compute | Optional hardening if agent-to-agent trust drops |
| 6 | **microVM (Firecracker) / Kata / full VM** — one guest kernel per job | Full hardware-virt boundary | ~125 ms boot, <5 MiB, higher | Reserve for future multi-tenant (explicitly Out of Scope now) |

Northflank's 2026 agent-sandboxing guide ranks these identically (Firecracker strongest → hardened containers weakest) and stresses hardened containers are "for **only trusted, reviewed code** … kernel vulnerabilities enable container escape." Firecracker boots in ~125 ms with <5 MiB overhead per microVM; gVisor "adds 10-30% overhead on I/O-heavy workloads but minimal on compute-heavy tasks." (Northflank; Aleinikov; agent-sandboxing guides, 2026.)

**Implication for intent.md.** The single-tenant/local-first scope (line 335) means the project does **not** need rungs 5-6 for launch. Phase 4's "sandboxed execution" should be delivered at **rungs 0-4** — a subprocess worker under seccomp + cgroups, wrapped in a jail (nsjail/bubblewrap) or a hardened OCI container — with gVisor/microVM documented as the **escalation path** for the day agent-to-agent use becomes genuinely multi-tenant. This matches the sibling report's Finding 2 ladder exactly and closes the "mechanism unstated" gap.

---

## Finding 2 — Linux primary stack: a rootless jail (nsjail or bubblewrap) is the sweet spot for local-first

For a single-tenant local service, the daemonless jails are a better first choice than a full container runtime because they are lightweight, require no root, and stitch exactly the primitives the threat model needs.

**nsjail** (Google) "wraps a single process (or process tree) in a combination of kernel-level isolation mechanisms: namespaces, cgroups, rlimits, and seccomp-bpf syscall filters … without a container runtime or virtual machine." Its protobuf config exposes every knob directly. A representative untrusted-code profile sets `time_limit: 30`, `max_cpus: 1`, all namespace flags (`clone_newuser/newnet/newns/newpid/newipc/newuts/newcgroup`), `cgroup_mem_max`, and `cgroup_pids_max` — i.e. **network namespace with no interfaces (deny-by-default egress), a chroot/pivot_root filesystem exposing only a scratch dir, memory/pid/CPU caps, and a syscall allowlist**, all in one wrapper. It has sub-20 ms startup and is used in production for AI-agent workloads (Windmill). (google/nsjail README; nsjail.dev; Morph, *nsjail for AI Code Execution*, 2026.)

**bubblewrap** (`bwrap`, the engine behind Flatpak) is the other strong option and is favoured where **unprivileged operation and simplicity** matter most: it "runs inside unprivileged user namespaces with **no privileged binary to attack**." This is a real security advantage over the profile-driven alternatives — Firejail's SUID-root binary produced CVE-2022-31214 (local root via its `join.c`). bubblewrap ships no profiles and gives fine-grained bind-mount/namespace control, which suits a worker whose exact filesystem needs (FreeCAD libs read-only, one scratch dir read-write) are known and fixed. (Bubblewrap docs; Firejail-vs-bubblewrap discussion #4522; CVE-2022-31214.)

**Firejail** is *not* recommended as the enforcement boundary here: it is desktop-app-oriented and its SUID-root design has a worse security track record. Useful as a reference for profile ideas, not as the Phase 4 mechanism.

**Recommended Linux profile for the FreeCAD worker (rungs 0-3):**
- **Filesystem:** read-only bind of the FreeCAD/OCCT install + Python env; a single read-write **job scratch dir** (spec in, exports/report out); everything else masked. No host `$HOME`, no `/etc` secrets.
- **Network:** a **network namespace with no interfaces** = deny-by-default egress. FreeCAD geometry work needs zero network; the LLM/MCP transport lives in the *orchestrator*, not the worker. This is the single highest-value control against exfiltration.
- **Resources (cgroups v2):** hard memory cap, CPU quota, `pids_max` (kills fork bombs), IO weight; plus `setrlimit` for `RLIMIT_AS`, `RLIMIT_CPU`, `RLIMIT_FSIZE`, `RLIMIT_NOFILE`. Directly implements the "resource limits" rail (line 276) and the "memory growth < 20% over 50-job soak" criterion (line 283).
- **Syscalls:** seccomp allowlist; deny `ptrace`, `mount`, `keyctl`, `kexec_load`, namespace-creation, `perf_event_open`. Docker's default profile (blocks ~44-50 of 300+ syscalls) is a good starting allowlist to adapt.
- **User:** run as unprivileged UID inside a user namespace; drop all capabilities.
- **Lifetime:** hard wall-clock timeout + the Phase 4 iteration cap → SIGKILL; one job = one fresh jail (no state carried between jobs).

---

## Finding 3 — Docker/OCI is the right *packaging and CI* layer, hardened the same way

The jail (Finding 2) is the runtime boundary; a **container image** is the reproducibility and distribution boundary — and intent.md already leans on containers for headless CI ("Community Docker images … in CI runners", line 65; FreeCAD/FC-Worker is the official *Containerized Headless FreeCAD Runner*). The two compose: run the worker inside an OCI container **and** apply the same hardening, or run nsjail *inside* the container for defence-in-depth.

Hardened-container hygiene, from primary Docker security docs and the OWASP Docker cheat sheet, applied to the FreeCAD worker:
- **`--network none`** (deny-by-default egress — same effect as the empty netns) unless a specific endpoint is genuinely needed.
- **`--cap-drop ALL`**, add back nothing (geometry work needs no Linux capabilities).
- **`--read-only` root filesystem** + a `tmpfs` or a single mounted scratch volume; "immune to most code drops … creates multiple defense layers."
- **`--security-opt seccomp=<profile>`** — keep the default profile (denies ~44 syscalls incl. `kexec_load`, `perf_event_open`, `add_key`, namespace-creation); tighten toward an allowlist for the worker.
- **`--memory`, `--cpus`, `--pids-limit`** for cgroup caps; **`--user` non-root** (rootless daemon preferred).
- **no-new-privileges**, drop inter-container networking (internal network only).

**FreeCAD-specific caveat (rendering).** The worker needs **screenshots / rendered views** (Phase 4 deliverable, line 281; "rendered views"). Headless FreeCAD offscreen rendering works in a container but historically needs either a virtual display (`xvfb`) or FreeCAD's offscreen path (FreeCAD PR #6808), and modern GUI stacks can trip Docker's syscall restrictions — the linuxserver image documents needing `--security-opt seccomp=unconfined` on older kernels/libseccomp. **Recommendation:** prefer FreeCAD's true offscreen renderer over a full GL/Xvfb stack to keep the syscall/capability surface minimal; if a virtual display is required, add exactly the syscalls it needs to the allowlist rather than disabling seccomp wholesale. GPU is **not required** — software OpenGL (Mesa/llvmpipe) or the offscreen path is sufficient for thumbnail/report views and avoids the GPU-passthrough attack surface and the dummy-plug/DRM complications the GPU path introduces (linuxserver docs). Keep the worker **GPU-none** for launch.

---

## Finding 4 — Windows primary stack: AppContainer (zero capabilities) + Job Object + restricted token

Windows has no single equivalent to a Linux jail; the practitioner-validated pattern is a **layered combination** of primitives, and Microsoft explicitly designates **AppContainer as a security boundary**. A production reference implementation (FastRender) and Microsoft's own docs converge on the same stack:

- **AppContainer with *zero* capabilities** = the primary boundary. Microsoft: AppContainer is "a security boundary … limited to a specific set of Windows APIs by default and can't inject code into any process operating at a higher integrity level." With **no `internetClient`/`internetClientServer` capability, network access is blocked** and filesystem/registry access is drastically reduced ("access to a local host isn't allowed" for app containers). This is the Windows analogue of the empty network namespace + minimal-filesystem jail. (Microsoft Learn, *Application Isolation*; FastRender windows_sandbox.md.)
- **Job Object** = resource + lifetime governance: **kill-on-close** (no orphaned workers if the orchestrator dies), **active-process-limit = 1** (blocks child-process spawning), optional **memory caps** and **UI restrictions**. This is the Windows analogue of cgroups + `pids_max` and directly serves the soak/leak criterion. (FastRender.)
- **Restricted / write-restricted token + Low Integrity Level** = the fallback when AppContainer is unavailable — but FastRender warns this mode is **weaker**: "Network is not reliably blocked" and filesystem access "reduced, but not eliminated," and "should not be assumed production-grade." So restricted-token-only is a degraded fallback, not the target.
- **Process mitigations** (defence-in-depth): Win32k lockdown, dynamic-code prohibition, image-load hardening, extension-point disable; **handle allowlisting** via `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` (fail-closed — only explicitly approved handles cross the boundary). (FastRender.)

**Microsoft's own trajectory confirms this stack.** At Build 2026 Microsoft open-sourced **MXC (Microsoft eXecution Container)**, a sandbox for running untrusted code, whose Windows backend "enforce[s] policy through **AppContainer capability SIDs and Job Object UI limits**" — i.e. exactly the AppContainer + Job Object pairing recommended here — escalating to Hyper-V micro-VMs for stronger isolation. (MXC internals; Windows 11 Security Book.)

**When AppContainer-packaging the FreeCAD worker is impractical**, the two strong-boundary alternatives on Windows are:
- **Windows Sandbox** — a disposable Hyper-V-backed desktop environment; "any untrusted Win32 app … stays only in the sandbox," and state is permanently discarded on close. Heavier (full VM), but a genuine hardware-virt boundary and a good match for *per-job disposable* execution when the AppContainer packaging cost is too high.
- **WSL2** — run the **Linux stack from Findings 2-3 inside WSL2**, gaining nsjail/seccomp/cgroups on Windows hosts. WSL2 adds **Hyper-V Firewall** (inbound/outbound filtering for WSL containers) and DNS-tunneling/auto-proxy controls for egress governance. This is the **most attractive Windows option for this project**: it reuses one Linux hardening profile across both platforms instead of maintaining a separate native-Windows sandbox. (Microsoft Learn, *Application Isolation* — WSL section; Hyper-V Firewall docs.)

**Recommended Windows profile:**
1. **Preferred (unify on Linux):** run the worker in the **Linux jail/container stack inside WSL2**, with Hyper-V Firewall enforcing egress deny-by-default. One hardening profile, both OSes.
2. **Native alternative:** **AppContainer (zero capabilities, no internet) + Job Object (kill-on-close, process-limit 1, memory cap) + restricted token/Low IL + process mitigations + handle allowlist.**
3. **Disposable heavy option:** **Windows Sandbox** per job when AppContainer packaging is not feasible.
4. Restricted-token-only is a **last-resort fallback**, documented as non-production-grade for network isolation.

---

## Finding 5 — Network egress is the highest-leverage control, and it belongs in the worker, not the orchestrator

Every source that ranks controls puts **deny-by-default egress** at or near the top: "Block all outbound connections by default. Whitelist only required API endpoints" (Northflank); nsjail's `clone_newnet` empty netns; Docker `--network none`; AppContainer without `internetClient`; WSL2 Hyper-V Firewall. The MCP-security corpus cited in the sibling report reaches the same conclusion (exfiltration is a top ACE consequence).

The architectural key for FreeCAD Buddy: **the geometry worker needs no network at all.** The LLM/MCP transport, spec intake, and result delivery live in the **orchestrator/job-API layer** (intent.md's bridge/service front). The worker receives a spec file and emits exports+report through the **scratch dir**, not a socket. Therefore the worker can and should be run **fully network-isolated (deny-all egress)** on both platforms with zero functional loss — the single cheapest, highest-value safety rail available, and one that cleanly satisfies the Phase 4 "sandboxed execution" intent without touching FreeCAD's functionality.

---

## Synthesis — Filling the Phase 4 "sandboxed execution" gap

| intent.md safety rail (line 276/283) | Concrete mechanism (this report) |
|--------------------------------------|----------------------------------|
| "sandboxed execution" | **Linux:** nsjail/bubblewrap jail (or hardened OCI container), rungs 0-3. **Windows:** Linux stack in WSL2 *or* AppContainer(0-cap)+Job Object. Escalate to gVisor/microVM only if it becomes multi-tenant. |
| "resource limits" | cgroups v2 (mem/CPU/pids/IO) + `setrlimit` (Linux); Job Object memory + process limits (Windows) |
| "iteration caps" | orchestrator-enforced N-iteration cap → SIGKILL/terminate the jailed worker |
| "full audit log of every operation" | orchestrator writes append-only log outside the jail (as the sibling report's Phase 0 logging already provides) |
| "memory growth < 20% over 50-job soak" (l.283) | one fresh jail/container per job (no state carried); hard memory cgroup cap; kill-on-close (Windows Job Object) |
| implicit: no exfiltration / host tamper | **deny-by-default egress** (empty netns / `--network none` / AppContainer no-internet / Hyper-V Firewall) + read-only rootfs + single scratch dir |

The mechanism is **complementary to the sibling report, not overlapping**: sibling = "typed tools are the only AI mutation path, in-process restriction is not a boundary"; this report = "the boundary is the OS jail around the worker, configured as above." Together they fully specify Phase 4's execution safety.

---

## Recommendation — Per-Platform Sandboxing Stack for the Single-Tenant Phase 4 Service

### The policy in one line
**Run each FreeCAD job in a fresh, network-isolated, resource-capped worker process: on Linux, an unprivileged nsjail/bubblewrap jail (or hardened `--network none` OCI container) with seccomp + cgroups + read-only rootfs + one scratch dir; on Windows, that same Linux stack inside WSL2 (preferred) or a native AppContainer(zero-capability) + Job Object; keep the worker GPU-none and egress-deny-by-default; reserve gVisor/microVM-per-job as the escalation path if the service ever becomes genuinely multi-tenant (currently Out of Scope).**

### Linux (primary target — CI and local-first host)
1. **Baseline (rung 0):** worker subprocess, `setrlimit` (AS/CPU/FSIZE/NOFILE), hard wall-clock timeout, iteration cap → SIGKILL.
2. **Jail (rungs 1-3):** **nsjail** (config-file driven, best fit for a fixed worker profile) or **bubblewrap** (simplest unprivileged, no SUID attack surface). Namespaces: user + net(empty) + mount + pid + ipc + uts + cgroup. Filesystem: RO FreeCAD/Python, one RW scratch dir. cgroups v2: mem/CPU/pids/IO caps. seccomp allowlist (adapt Docker default). Drop all capabilities, unprivileged UID.
3. **Container (rung 4, for CI + reproducibility):** package the worker as an OCI image (align with FreeCAD/FC-Worker), run `--network none --cap-drop ALL --read-only --pids-limit --memory --cpus --user <nonroot> --security-opt seccomp=<profile>`. nsjail-inside-container for defence-in-depth if desired.
4. **Rendering:** use FreeCAD's **offscreen renderer** (avoid full Xvfb/GL where possible); **GPU-none**, software GL. Only widen the seccomp allowlist for the exact display syscalls needed — never `seccomp=unconfined`.
5. **Escalation (documented, not built now):** gVisor for cheap kernel-surface reduction; Firecracker/Kata microVM-per-job if agent-to-agent traffic becomes multi-tenant.

### Windows
1. **Preferred:** run the **Linux stack inside WSL2**; enforce egress with **Hyper-V Firewall** (outbound deny-by-default). One hardening profile for both OSes — lowest maintenance.
2. **Native alternative:** **AppContainer with zero capabilities** (no `internetClient` → no network, minimal FS/registry) + **Job Object** (kill-on-close, active-process-limit 1, memory cap) + **restricted/write-restricted token, Low Integrity Level** + process mitigations (Win32k lockdown, dynamic-code prohibition) + **handle allowlisting** (`PROC_THREAD_ATTRIBUTE_HANDLE_LIST`).
3. **Disposable heavy option:** **Windows Sandbox** per job (Hyper-V-backed, state discarded on close) when AppContainer packaging is impractical.
4. **Avoid** relying on restricted-token-only (network not reliably blocked — non-production-grade per FastRender).

### Cross-cutting (both platforms)
- **Egress deny-by-default in the worker** — the worker needs no network; keep all transport in the orchestrator. Highest-value single control.
- **One fresh sandbox per job** — no carried state; satisfies the soak/leak criterion.
- **Resource caps + hard timeout + iteration cap** — the "resource limits / iteration caps" rails, enforced by the OS not by the app.
- **Audit log lives outside the sandbox** (orchestrator side), append-only, per the sibling report.

### Concrete doc edits proposed for `docs/intent.md`
- **Line 276 (Phase 4 "sandboxed execution"):** expand to *"sandboxed execution — each job runs in a fresh, **network-isolated, resource-capped worker**: Linux = nsjail/bubblewrap jail or hardened `--network none` OCI container (seccomp + cgroups + read-only rootfs + scratch dir); Windows = same stack in WSL2, or AppContainer(zero-capability)+Job Object. GPU-none. gVisor/microVM-per-job reserved for any future multi-tenant use."*
- **Line 285 (Phase 4 "Achievable"):** note that sandboxing is **configuration of existing OS primitives**, not new engineering — no bespoke sandbox to build.
- **Line 335 (Out of Scope):** cross-reference that the single-tenant scope is *why* rungs 5-6 (gVisor/microVM) are deferred; record them as the documented escalation trigger.

---

## Sources

**Linux jails & primitives (primary docs)**
- google/nsjail (namespaces + cgroups + rlimits + seccomp-bpf; config.proto): https://github.com/google/nsjail , https://nsjail.dev/
- Morph, *nsjail: Lightweight Linux Sandboxing for AI Code Execution* (2026): https://www.morphllm.com/nsjail-sandbox
- Bubblewrap — unprivileged sandboxing (Flatpak engine): https://siddhanttiwary.medium.com/sandboxing-untrusted-code-with-bubblewrap-52ab55d113b1 , https://botmonster.com/self-hosting/sandbox-linux-apps-cli-tools-bubblewrap/
- Firejail vs bubblewrap (SUID risk, CVE-2022-31214): https://github.com/netblue30/firejail/discussions/4522 , https://firejail.wordpress.com/2025/08/20/how-to-sandbox-linux-apps-with-firejail-and-bubblewrap/

**Container hardening (primary docs)**
- Docker seccomp default profile: https://docs.docker.com/engine/security/seccomp/
- OWASP Docker Security Cheat Sheet (network none, cap-drop, read-only, pids-limit): https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html
- Docker security hardening (rootless, seccomp, AppArmor, read-only rootfs): https://www.virtua.cloud/learn/en/tutorials/docker-security-hardening-rootless-seccomp , https://systeminternals.dev/docker/security/

**microVM / gVisor comparison**
- Northflank, *How to sandbox AI agents in 2026* (Firecracker/gVisor/Kata ranking, overhead): https://northflank.com/blog/how-to-sandbox-ai-agents , https://northflank.com/blog/kata-containers-vs-firecracker-vs-gvisor
- Aleinikov, *Firecracker vs gVisor: Which Sandbox in 2026*: https://www.alekseialeinikov.com/en/blog/topics/devops/microvms-firecracker-vs-gvisor-secure-workloads-2026

**Windows isolation (primary + practitioner)**
- Microsoft Learn, *Windows 11 Security Book — Application Isolation* (AppContainer, Win32 app isolation, Windows Sandbox, WSL/Hyper-V Firewall): https://learn.microsoft.com/en-us/windows/security/book/application-security-application-isolation
- Microsoft Learn, *AppContainer isolation*: https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation
- FastRender, *Windows sandbox design* (AppContainer 0-cap + Job Object + handle allowlist; restricted-token fallback caveats): https://github.com/wilsonzlin/fastrender/blob/main/docs/windows_sandbox.md
- Origin, *MXC Internals* (Microsoft eXecution Container — AppContainer SIDs + Job Object UI limits): https://www.originhq.com/research/mxc-execution-containers-internals

**FreeCAD-specific containerization**
- FreeCAD/FC-Worker — official Containerized Headless FreeCAD Runner: https://github.com/FreeCAD/FC-Worker
- linuxserver/docker-freecad (seccomp/GUI caveats): https://docs.linuxserver.io/images/docker-freecad/
- FreeCAD offscreen rendering PR #6808: https://github.com/FreeCAD/FreeCAD/pull/6808

**Complementary project research**
- Sibling report (in-process policy, OS-layer handoff): `_bmad-output/planning-artifacts/research/technical-python-execution-sandbox-policy-research-2026-07-20.md`
- `docs/intent.md` — Phase 4 safety rails (l.276, l.283), Out of Scope single-tenant/local-first (l.335), Risks "no free-form exec in mutation path" (l.322)
