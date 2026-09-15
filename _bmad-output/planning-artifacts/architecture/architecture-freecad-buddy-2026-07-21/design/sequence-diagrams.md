---
title: 'Scenario Sequence Diagrams'
status: draft
date: '2026-09-15'
ad-refs: ['AD-35', 'AD-2', 'AD-3', 'AD-4', 'AD-5', 'AD-10', 'AD-13', 'AD-17', 'AD-21', 'AD-25']
sources:
  - 'ARCHITECTURE-SPINE.md'
  - 'docs/intent.md'
  - 'src/freecad_buddy/ (call paths read, not inferred)'
---

# Scenario Sequence Diagrams

Runtime call paths for every scenario FreeCAD Buddy supports. Each diagram is drawn from the
shipped code, and every message name is a real tool, function or wire frame.

**The boundary AD-35 draws is the reason these diagrams exist.** Read them for one thing above all:
which participant holds the loop. In every scenario the answer is the **driving agent**, never a
box inside this repo. A diagram that showed `src/` deciding what to do next would be a design
defect, not a drawing choice.

**The agent never calls a use case directly. Every call crosses the MCP protocol.** There is no
in-process path from an agent to `usecases/`, no Python import, no direct function call — the MCP
surface is the *only* way in, for every caller: the interactive agent, a spawned subagent, a
benchmark actor, and the operator driving `debug_exec`. Scenario 2 draws that crossing in full
(Proxy → Listener → Marshal → use case); the later diagrams collapse it to one **MCP surface**
participant so the scenario's own logic stays readable, but the hop is always there. An arrow drawn
from an agent straight to a use case would misstate the architecture — the protocol boundary is
what makes the bridge agent-agnostic, and it is where authentication (AD-3), the typed-tool
restriction (AD-4), and the envelope contract (AD-17) are enforced.

## Participants, and what each one may do

| Participant | Is | May never |
| --- | --- | --- |
| **Agent** | The driving AI (Claude Code, opencode, any MCP client). Holds the plan, the repair decision, the visual verdict, the stop condition | — |
| **Skills** | `skills/` — knowledge + Track W workflow + read-only helper scripts the agent's own shell runs | Call a model; mutate a document; decide the next action |
| **MCP surface** | The protocol boundary, collapsed for readability: Proxy → Listener → Marshal in GUI mode, one in-process hop when headless. **Every** agent call crosses it | Be bypassed — there is no other way into `usecases/` |
| **Proxy** | The external MCP protocol server (`adapters/mcp_server.py`), auto-spawned by the addon | Import FreeCAD |
| **Listener** | The in-FreeCAD RPC listener (`adapters/rpc_listener.py`), stdlib only | Touch FreeCAD off the main thread |
| **Marshal** | `adapters/marshal.py` — hops every call onto the Qt main thread | Import Qt (the pump lives in `hosts/gui_addon/pump.py`) |
| **Usecases** | `usecases/` — tool implementations, the AD-5 mutation protocol, verification | Import Qt; hold a plan, an iteration count, or a done-predicate |
| **FreeCAD** | The App-layer kernel | — |

```mermaid
flowchart LR
  A["Agent<br/><i>owns the loop</i>"] -- loads --> S["Skills"]
  A -- "MCP over HTTP" --> P["Proxy"]
  P -- "JSON-RPC + session token" --> L["Listener"]
  L -- "postEvent hop" --> M["Marshal"]
  M -- "main thread" --> U["Usecases"]
  U --> F["FreeCAD App API"]
```

---

## 1. Bridge start — opening FreeCAD is the only operator step

`hosts/gui_addon/bootstrap.py:82 start_bridge`. The addon starts the listener **and** spawns the
proxy; nothing is launched by hand (AD-2).

```mermaid
sequenceDiagram
  autonumber
  actor Operator
  participant GUI as FreeCAD GUI
  participant Boot as gui_addon/bootstrap
  participant L as RpcListener
  participant Proxy as MCP proxy (child process)
  participant Agent

  Operator->>GUI: launch FreeCAD
  GUI->>Boot: InitGui
  Note over Boot: start deferred until FreeCAD.GuiUp<br/>via QTimer.singleShot (AD-2)
  Boot->>Boot: token = secrets.token_urlsafe(32)
  Boot->>L: start on ephemeral localhost port
  L-->>Boot: bound port
  Boot->>Boot: probe :8765 /healthz for own session id
  alt foreign or stale listener on :8765
    Boot-->>Operator: error surfaced — never a silent reuse
  else port free
    Boot->>Boot: _mcp_proxy_command() — resolve project venv<br/>from the addon's own install path
    Boot->>Proxy: Popen (detached, no console)
    Boot->>Boot: write connection file (token + addon PID)
  end
  Agent->>Proxy: MCP initialize (bearer token, Origin checked)
  Proxy-->>Agent: tool list
  Note over Proxy,L: proxy exits once the PID it was spawned for is gone
```

**Why the PID is in the connection file:** a fast FreeCAD restart otherwise leaves an orphan proxy
owning the port and wired to a dead listener — which the client experiences as a hang rather than
a status (AD-2).

---

## 2. Read-only query — the Phase 1 shape

No mutation, no transaction. The marshal hop is the only thing that distinguishes GUI mode from
headless.

```mermaid
sequenceDiagram
  autonumber
  participant Agent
  participant Proxy
  participant L as Listener
  participant M as Marshal
  participant U as usecases/queries
  participant F as FreeCAD

  Agent->>Proxy: query_tree_summary
  Proxy->>L: JSON-RPC frame + session token
  L->>M: call(fn, timeout_s)
  Note over M: off-thread accept, main-thread execute<br/>(the documented crash mode otherwise)
  M->>U: query_tree_summary(doc)
  U->>F: read Document / objects
  F-->>U: tree
  U-->>M: ResultEnvelope{status, structured, text}
  M-->>L: envelope
  L-->>Proxy: frame
  Proxy-->>Agent: envelope
  Note over Agent: the agent decides what this means<br/>and what to call next — nothing here does
```

Headless (`FreeCADCmd`) is the same diagram with Proxy, Listener and Marshal collapsed: one
process, `InlineExecutor`, use cases called inline. Same `usecases/` code on every path.

---

## 3. Confirmed mutation — preview, confirm, apply, prove rollback

The AD-5 protocol in full. This is the scenario the repo is built around.

```mermaid
sequenceDiagram
  autonumber
  participant Agent
  participant MCP as MCP surface
  participant U as usecases
  participant C as usecases/confirm
  participant T as usecases/transaction
  participant F as FreeCAD

  Agent->>MCP: preview_dry_run(op, args)
  MCP->>U: dispatch
  U->>F: copyObject onto TempDoc
  U->>F: run op, recompute
  F-->>U: diff — Δvolume/area/bbox/COM, counts, validity, TNP pre-check
  U->>C: sign token over (op, doc, args digest, fingerprint)
  C-->>MCP: preview_id + structured diff (+ optional render ≤1920px)
  MCP-->>Agent: envelope

  Note over Agent: the agent shows the diff and gets a human yes,<br/>or runs under an audited auto-approve posture

  Agent->>MCP: feature_pocket(args, confirm={preview_id})
  MCP->>U: dispatch
  U->>C: verify token — re-derive all four, check id not spent
  alt token invalid, spent, or fingerprint moved
    C-->>MCP: INVALID_INPUT — no mutation attempted
    MCP-->>Agent: envelope
  else token good
    C-->>T: authorized
    T->>F: fingerprint + snapshot_references + saveCopy snapshot
    T->>F: openTransaction
    T->>F: typed op
    T->>F: recompute()
    T->>T: post_verify — recompute clean, isValid(), DoF, TNP audit
    alt post_verify passes
      T->>F: commitTransaction
      T->>T: delete snapshot
      T-->>MCP: OK + audit record
      MCP-->>Agent: envelope
    else post_verify fails
      T->>F: abortTransaction, recompute()
      T->>T: re-hash and compare to pre-mutation fingerprint
      alt hash matches
        T-->>MCP: rolled_back
        MCP-->>Agent: envelope
      else undo did not restore (FreeCAD #6031)
        T->>F: close doc, openDocument(snapshot), recompute
        T->>T: re-assert equality
        T-->>MCP: rolled_back_via_snapshot
        MCP-->>Agent: envelope
      end
    end
  end
```

**Rollback success is measured, never assumed** — that re-hash is the whole point of AD-5. The
snapshot path exists because FreeCAD's undo can fail to restore the pre-`openTransaction`
boundary.

**A token authorizes one mutation.** The fingerprint comparison proves the document is still in the
state the preview measured; it does not prove the token is unused, because a property written its
existing value commits without moving the fingerprint. Hence the spent-id set
(`usecases/confirm.py:7-12`).

---

## 4. Spec to part — the loop, held by the agent

The loop is the agent following `design-loop`; the repo supplies measurements and images and
decides nothing.

```mermaid
sequenceDiagram
  autonumber
  actor Human
  participant Agent
  participant Sk as Skills (Track W)
  participant MCP as MCP surface
  participant U as usecases
  participant F as FreeCAD

  Human->>Agent: written spec
  Agent->>Sk: load design-loop, spec-to-assertions, design-decomposition
  Agent->>Agent: author machine-checkable assertions BEFORE building
  Agent->>Human: proposed plan
  Human-->>Agent: approve (once — nothing after this is supervised)

  loop until done, or the agent stops (design-loop sets the cap)
    Agent->>MCP: sketch_* / feature_* per plan step (each via scenario 3)
    MCP->>U: dispatch
    U-->>MCP: envelopes
    MCP-->>Agent: per-step envelopes

    Agent->>MCP: verify_shape / verify_sketch / query_mass_properties
    MCP->>U: dispatch
    U-->>MCP: measurements + per-check pass/fail
    MCP-->>Agent: envelope
    Note over U: returns CHECKS, never an aggregate "done" (AD-35)

    Agent->>Sk: run helper script (reads workdir, computes, answers one question)
    Sk-->>Agent: e.g. hole spacing vs spec

    alt all geometry checks pass
      Agent->>MCP: query_screenshot (iso, focus) + TechDraw sheet ≥2048px
      MCP->>U: dispatch
      U-->>MCP: image artifacts
      MCP-->>Agent: envelope carrying paths
      Agent->>Sk: load visual-review checklist
      Agent->>Agent: LOOK at the images — mirrored? wrong face? proportions?
      Note over Agent: the reviewer IS the actor.<br/>Independence deliberately traded away (AD-21)
      Agent->>Agent: write findings to the AD-17 run workdir
    else a check failed
      Agent->>Agent: read the discrepancy, decide a repair
    end
  end

  Agent-->>Human: part + validation report + workdir evidence trail
```

**Both legs are required for done** — geometry assertions *and* a performed visual review. Nothing
at runtime enforces the conjunction: `derive_verdict` reads checks alone and no code may produce a
visual verdict. A run whose workdir carries no visual evidence is an **incomplete run**, caught
after the fact by AD-19's ≥20 % human spot-audit. Detectability is therefore after the fact rather
than at runtime — the accepted cost of AD-35.

---

## 5. Unattended operation, and delegation

There is **no job API, no supervisor and no worker pool**. Unattended
means an operator starts an agent and walks away — the same agent, the same MCP surface, the same
skills as scenario 4, with no human in the loop. **Delegation is the agent's own mechanism:** an
agent that wants to parallelize spawns a **subagent**, which operates the same MCP surface with the
same skills.

```mermaid
sequenceDiagram
  autonumber
  actor Operator
  participant Agent as Lead agent
  participant Sub as Subagent
  participant Sk as Skills
  participant MCP as MCP surface
  participant U as usecases
  participant Audit as adapters/audit_log

  Operator->>Agent: start unattended (cron, CLI, queue)
  Note over Agent: holds the loop — scenario 4,<br/>with no human in it

  opt the lead agent chooses to delegate
    Agent->>Sub: spawn with a scoped task
    Note over Agent,Sub: the agent harness's mechanism,<br/>never this repo's (AD-35)
    Sub->>Sk: load the same skills
    Sub->>MCP: tool calls — the same surface, the same protocol
    MCP->>U: dispatch
    U-->>MCP: envelopes
    MCP-->>Sub: envelopes
    Sub-->>Agent: finished work
  end

  Agent->>MCP: tool calls
  MCP->>U: dispatch
  U->>Audit: append-only record per mutation
  U-->>MCP: envelopes carrying measurements
  MCP-->>Agent: envelopes

  Agent->>MCP: verify_shape / verify_export_step / query_mass_properties
  MCP->>U: dispatch
  Note over U: every reported field is a RE-EXECUTED check,<br/>never an agent claim (AD-17)
  U-->>MCP: validation report
  MCP-->>Agent: envelope

  Agent-->>Operator: finished work + run workdir + audit trail
```

**What the repo still owes an unattended run**, with no service to provide it: the append-only
audit log and `run_id` traceability (AD-17), artifact retention in the session workdir (AD-25), and
verification whose every field is re-executed rather than echoed. None of that needs a worker.

**There is no crash containment of our own.** A segfault in the geometry kernel takes down whatever
process the agent is driving. This repository offers no boundary — the operator's environment is the
boundary, which is why the audit log matters: it is what makes such a failure legible afterwards.

---

## 6. Revision — change one thing, prove nothing else moved

```mermaid
sequenceDiagram
  autonumber
  actor Human
  participant Agent
  participant Sk as Skills
  participant MCP as MCP surface
  participant U as usecases

  Human->>Agent: "make the flange 5 mm taller"
  Agent->>Sk: load design-loop — revision section
  Agent->>Agent: DECLARE THE SCOPE before touching anything
  Agent->>MCP: fingerprint + query_mass_properties (the before state)
  MCP->>U: dispatch
  U-->>MCP: baseline
  MCP-->>Agent: envelope

  Agent->>MCP: feature_set_parameters (via scenario 3)
  MCP->>U: dispatch
  U-->>MCP: result
  MCP-->>Agent: envelope
  Agent->>MCP: verify_shape, query_dependencies, query_mass_properties
  MCP->>U: dispatch
  U-->>MCP: post-revision geometry
  MCP-->>Agent: envelope

  Agent->>Agent: compare against the declared scope
  alt diff confined to the declared scope
    Agent->>Agent: visual review of the changed region (AD-21)
  else diff touched, added or deleted anything unnamed
    Agent-->>Human: REJECT — name what moved that should not have
  else the diff cannot be read
    Agent-->>Human: FAIL CLOSED — an unproven revision, not a passing one
  end
  Agent-->>Human: revised part + scope evidence in the run workdir
```

**Without a declared scope there is nothing to be out of**, and "confined to the requested change"
would reduce to whatever the result happened to touch — a check that can never fail. That reasoning
lives in the `design-loop` skill, and its deterministic half — comparing two fingerprints and
reporting what moved — belongs in `usecases/verify_*` where any caller can re-run it.

---

## 7. Gate run — spawning the actor with the Claude Agent SDK

**Open question:** whether gates keep scoring end-to-end production at all is recorded in the
spine's Deferred table.

**The runner spawns the actor as a Claude Agent SDK process** (`claude-agent-sdk` /
`@anthropic-ai/claude-agent-sdk`). That SDK *is* the Claude Code harness packaged as a library: it
supplies the agent loop, context management, subagents, and built-in tools, and the caller supplies
only a prompt and options. The runner therefore holds **no loop of its own** — it hands over a spec
and waits, which is what keeps it on the right side of AD-35's `benchmarks/` scope.

```mermaid
sequenceDiagram
  autonumber
  participant Runner as benchmarks/runner
  participant SDK as Claude Agent SDK process (Sonnet)
  participant Sk as skills/
  participant Bridge as MCP bridge (headless)
  participant V as Validators

  Runner->>Runner: load gate.yaml criteria (never hardcoded)
  loop per case, R repeats
    Runner->>SDK: query(spec, options)
    Note over Runner,SDK: options carry the MCP server, the allowed<br/>tool list and the skills — never a plan,<br/>an iteration count or a repair rule (AD-35)
    SDK->>Sk: load design-loop, visual-review, spec-to-assertions
    SDK->>Bridge: MCP tool calls over http://127.0.0.1:8765/mcp
    Bridge-->>SDK: envelopes carrying measurements and images
    Note over SDK: the SDK owns the loop —<br/>plan, repair, visual review, stop
    SDK-->>Runner: finished artifacts + run workdir
    Runner->>V: re-execute assertions against the artifacts
    V-->>Runner: per-check pass/fail
  end
  Runner->>Runner: Wilson CI, majority-of-R, dev/held-out gap
  Runner-->>Runner: verdict — citable only where recomputable<br/>from stored measurements (AD-13)
```

**The bridge is already an MCP server, so no glue is needed.** `.mcp.json` declares it as a plain
HTTP entry (`http://127.0.0.1:8765/mcp`); the Agent SDK attaches it the same way any MCP client
does. The runner's job reduces to: start the process, point it at that endpoint, collect what it
wrote.

**The benchmark actor runs on Sonnet**, and the gate's `actor.model` names the exact model id used.
Two reasons it is the right default here rather than a cost compromise: a gate is run at R≥10 across
27 cases, so the actor is the dominant spend in the harness; and the gate measures **the bridge and
the skills**, not the frontier of model capability — a weaker actor that still passes is stronger
evidence that the tool surface and `design-loop` carry the work. The floor this sets is a floor, not
a ceiling: an operator driving the same bridge on a larger model should do at least as well.

Two constraints travel with that choice. **A cited rate is only valid for the actor that produced
it** — AD-14's banner already carries the model, and a Sonnet-measured pass rate may not be quoted
for an Opus-driven run or the reverse. And **a gate failure now has two candidate causes**: the
bridge or skills are inadequate, or the actor was. Distinguishing them needs a re-run on a stronger
actor, which is a diagnostic step, not a new gate result.

**Three properties this shape must preserve**, each of which a hand-rolled runner tends to lose:

| Property | Why the SDK gives it for free |
| --- | --- |
| The runner holds no loop | The harness lives in the SDK process, not in `benchmarks/` |
| The actor is a real agent, not a simulation | Same harness a human operator drives — the gate measures what ships |
| No model client in this repo | The SDK carries its own credential; `benchmarks/` never imports a model SDK |

**The actor identity in `gate.yaml` must name the real thing.** Today it reads
`model: claude-mcp-client`, a placeholder. Under this shape it names the exact Sonnet model id the
SDK ran, because AD-13's independence guard compares that descriptor against the grader — a
placeholder makes the guard vacuous. **G3's independence is unaffected by the Sonnet choice**: its
`grader` is `deterministic-geometry-assertions` (`harness/assertions.py`), deterministic code rather
than a model, so no actor model can collide with it. The guard still matters for any gate whose
grader *is* a model — G1's `deterministic-expected-findings` is likewise code, but AD-21's visual
reviewer is now the actor by design, which is the trade AD-21 records rather than a collision to
resolve.

**What may not be cited:** any figure whose value depends on a judgement the producing agent made.
"Mean repairs to convergence" is not citable — convergence is where the agent decided to stop.
"Count of parts whose assertions passed" over the same runs is. A derived statistic inherits the
status of its least-citable input.

---

## 8. Operator escape hatch — `debug_exec`

Off by default, unregistered from the tool list when off, and never enabled in an unattended run —
the flag is a human act, and no agent may set it (AD-4).

```mermaid
sequenceDiagram
  autonumber
  actor Operator
  participant Boot as bootstrap
  participant Cat as tool_catalog
  participant MCP as MCP surface
  participant U as usecases/debug_exec
  participant Audit as adapters/audit_log

  Operator->>Boot: set the enabling env flag (human, never a wire field)
  Boot->>Cat: register debug_exec
  Note over Cat: when off, the tool is absent from the list —<br/>not present-and-refusing
  Operator->>MCP: debug_exec(arbitrary Python)
  Note over MCP: still a typed MCP tool — the operator<br/>drives it through the same surface an agent would
  MCP->>U: dispatch
  U->>Audit: append-only record (before execution)
  U-->>MCP: result
  MCP-->>Operator: envelope
  Note over U: in-process restriction is never called a security<br/>boundary — this repo ships NO boundary of its<br/>own, so the operator's environment is it
```

---

## What no diagram shows, deliberately

Three shapes are absent because AD-35 forbids them. Their absence is the design.

| Absent shape | Why |
| --- | --- |
| A `src/` box deciding the next action | The loop is the agent's. Any arrow returning "do this next" from inside the repo is a violation |
| A judge participant with a model API | The reviewer is the agent. No model client, no credential, no verdict-producing code |
| A service endpoint that takes a spec and returns a part | That is the loop in the code wearing a service's clothes. Scenario 5 submits *FreeCAD work*, not a design task |
