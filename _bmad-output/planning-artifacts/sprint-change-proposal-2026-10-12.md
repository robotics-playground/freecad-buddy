---
title: 'Sprint Change Proposal: script_exec as an official tool'
date: '2026-10-12'
author: TanNT
scope: Major
status: approved
---

# Sprint Change Proposal: script_exec as an official tool

## 1. Issue Summary

The typed MCP tools (`sketch_*`, `feature_*`, `document_*`, `query_*`, `verify_*`, `export_*`) do not
cover all of FreeCAD. When an agent needs an operation that no typed tool has, it cannot do the work.
The bridge already has a Python exec tool, `debug_exec`, but AD-4 keeps it operator-only and off by
default:

> `ARCHITECTURE-SPINE.md:69` — "`debug_exec` is operator-only: disabled by default, enabled by
> human-set env flag, unregistered from the MCP tool list when off, append-only audit-logged, and
> never enabled in an unattended run — the flag is a human act, and no agent may set it."

**Change requested (TanNT, 2026-10-12):** make the exec tool an official agent tool. Rename it to
`script_exec` and turn it on by default.

Issue type: new requirement from use. The typed surface is not complete enough to be the only path.

### Decisions (human, 2026-10-12)

- **D1 — Rename.** `debug_exec` becomes `script_exec`. The old name is deleted, not aliased.
- **D2 — On by default.** New switch `FREECAD_BUDDY_SCRIPT_EXEC` and preference `ScriptExec`
  (default on). The old `FREECAD_BUDDY_ALLOW_EXEC` and `AllowExec` are deleted. A stale
  `AllowExec=false` in `user.cfg` is ignored, so every user gets the new default.
- **D3 — Unattended marker.** No host can tell an attended run from an unattended one today
  (`Capabilities.service_mode` is never set to `True` by any caller). So the operator marks an
  unattended run with `FREECAD_BUDDY_UNATTENDED=1`. In a marked run `script_exec` is off, unless the
  operator also sets `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`.
- **D4 — Raw exec.** `script_exec` keeps today's body: no AD-5 transaction, no fingerprint, no
  rollback. AD-5 gets a named exception for it.

### Security posture after this change

With the default on, any client that holds the `:8765` bearer token can run any Python with the
user's rights: read files, use the network, start processes. A prompt injection that reaches the
agent can do the same. Today this needs a human to turn on `AllowExec`. The repo ships no sandbox
(AD-35, `mcp-tools-design.md` §5 item 4), so the operator's environment stays the only isolation.
This proposal records that as an accepted risk. The README keeps the advice to run an unattended
agent on an isolated computer or account.

## 2. Impact Analysis

### Epics and stories

- **Epics 1–3, 8, 9, 11 (done):** not reopened (AD-19). FR19 is rewritten for the living document.
  Done story specs keep their text, because they are history.
- **Epic 10 (in progress):** Story 10.6 bounds the exec tool on the headless host
  (`spec-10-6-headless-bounded-execution.md` is `status: 'draft'`; `epics.md:1343` AC2). It must use
  the new name. Story 10.7 maintains the UAT suite. It takes the UAT test case rewrite.
- **New Epic 12, Story 12.1:** implements the change. It runs before Story 10.6, because both edit
  the exec wiring in `hosts/tool_catalog.py` (`bound_off_main_thread` at line 1546).
- **Epic 5 (backlog, unattended operation):** inherits the unattended marker. The dead
  `service_mode` gate stays as it is. It is Epic 5 scope.
- **Gates:** no gate measurement changes. G1 uses `build_readonly_profile`
  (`tool_catalog.py:1583`), which keeps excluding the exec tool. The G0 and G2 scorers run inside
  FreeCAD and do not use MCP.

### PRD and intent

No PRD file exists. `docs/intent.md:210` lists "operator-only `debug_exec`" in the Phase 0 scope.

### Architecture

| Document | What changes |
| --- | --- |
| `ARCHITECTURE-SPINE.md` | AD-4 rule; Config row (line 385) |
| `design/mcp-tools-design.md` | §2 table row (line 200), G0.2 count text (lines 219–221), §5 rules, `query_capabilities` row (line 135) |
| `design/security-and-service-design.md` | §1 (all four layers), phase threat model (lines 78–81), trust diagram (line 105), key reading (line 108), rejected-mechanism table (lines 118–119) |
| `design/integration-mcp-freecad.md` | lines 56, 60, 99, 141, 266 |
| `design/integration-mcp-clients.md` | line 70 |
| `design/component-design.md` | lines 43, 83, 194 |
| `design/project-structure.md` | lines 62, 331 |
| `design/data-contracts-design.md` | line 182 (example tool name) |
| `design/sequence-diagrams.md` | line 25, §8 |

AD-5 also changes: it gets a named exception for `script_exec`.

### Code (Story 12.1)

| File | Today |
| --- | --- |
| `usecases/debug_exec.py` | module, function, docstring, `ValidationError("debug_exec requires 'code'")` |
| `usecases/capabilities.py:23-44` | `allow_exec=environ.get("FREECAD_BUDDY_ALLOW_EXEC") == "1"`; `exec_registered` |
| `usecases/operator_settings.py:17,25,56,76` | `ALLOW_EXEC_VARIABLE`, overlay, set-rule |
| `usecases/shim.py:31,415` | `ALLOW_EXEC_KEY = "AllowExec"` |
| `hosts/gui_addon/preferences.py:48-55,100,114,144` | "Allow debug_exec" checkbox and red warning |
| `hosts/tool_catalog.py:26,1051-1073,1545,1595` | `DEBUG_EXEC_SPEC`, inner bound, read-only exclusion |
| `adapters/mcp_server.py:5,75,80,219,239,271,319` | gate, startup warning, denied envelope |
| `adapters/rpc_dispatch.py:58,63` | `method.name == "debug_exec"` audit rule |
| `adapters/rpc_listener.py:331`, `adapters/audit_log.py:3-7,81` | comments and docstrings |
| `hosts/gui_addon/bootstrap.py:154` | `exec_enabled` capability (name stays) |

Tests: `tests/external/test_mcp_surface.py` (49 references), `test_operator_settings.py`,
`test_rpc_listener.py`, `test_confirm_contract.py`, `test_assistant_readonly_profile.py`,
`test_gui_external_proxy.py`, `tests/infc/test_bootstrap_settings.py`, `tests/infc/test_preview.py`.

### Agent context, operator docs, skills

- `README.md:183,194,230,237,270-272`, `AGENTS.md:269,438`, `CLAUDE.md` section 16 (operator settings
  line), `_bmad-output/project-context.md:95,144`.
- `skills/freecad-scripting-idioms/SKILL.md:53-56` and `:109-111` tell the agent never to use
  free-form code. That must change, or the agent will not use the new tool.

### UAT test cases (Story 10.7)

`TC-11-security-posture-and-artifact-hygiene.md` (28 references), `TC-05` (12), `TC-08` (3),
`TC-01` (3), `TC-09` (1), `coverage-matrix.md`, `APPENDIX-B-environment-setup.md`,
`test-plan.md`. Past run reports under `tests/uat/run/` are history and keep their text.

### Deferred work that this change makes more important

- **DW-19** (`deferred-work.md:158`): the audit `before` record stores only `params_digest`, not the
  executed source. `security-and-service-design.md` §1 item 3 already requires the full source. With
  agents running scripts by default, the audit log cannot show what an agent ran.
- **GUI freeze** (`deferred-work.md:610`): a script that never returns keeps the Qt main thread.
  The listener returns `TIMEOUT`, but FreeCAD stays frozen. An agent can now cause this with one
  loop. Story 10.6 fixes only the headless host; goals B–D (GUI) stay deferred.
- **Registry lock** (`deferred-work.md:598`): an abandoned exec body holds the `DocumentRegistry`
  lock. Story 10.6 handles this on the headless host.

## 3. Recommended Approach

**Direct adjustment with a spine change.** Rewrite AD-4 and add an AD-5 exception, then add one
story that renames the tool, flips the default, adds the unattended marker, and updates the skill.

- **Effort:** one story, medium. Most of it is a rename across 10 source files and 8 test files.
  New logic: two env variables and one registration rule.
- **Risk:** security risk as stated in §1, accepted by D2. Technical risk is low: the exec body,
  timeout, audit pair, and suspect-set rules do not change.
- **Timeline:** Story 12.1 is added before Story 10.6. Epic 10 is delayed by one story.
- **Included by recommendation (remove in review if not wanted):** Story 12.1 AC7 closes DW-19,
  so the audit log stores each script's source. Without it, the audit log cannot show what an
  agent ran.

## 4. Detailed Change Proposals

### 4.1 Architecture spine — `ARCHITECTURE-SPINE.md`

**AD-4 title and rule**

OLD title: `AD-4 — Typed tools are the only AI mutation path [ADOPTED]`

NEW title: `AD-4 — Typed tools first, script_exec for the rest [ADOPTED]`

OLD Prevents: `LLM free-form exec becoming the mutation path (host RCE + unverifiable ops)`

NEW Prevents: `free-form exec replacing a typed tool that exists; an exec surface the operator cannot turn off or audit`

OLD Rule:
> AI-visible mutations exist only as typed `sketch_*`/`feature_*`/`document_*` tools. `debug_exec` is operator-only: disabled by default, enabled by human-set env flag, unregistered from the MCP tool list when off, append-only audit-logged, and never enabled in an unattended run — the flag is a human act, and no agent may set it. In-process Python restriction (RestrictedPython, audit hooks, blacklists) is never called a security boundary; this repo ships no isolation boundary of its own, so the operator's environment is the only one — which is why the default-off posture is load-bearing.

NEW Rule:
> Typed `sketch_*`/`feature_*`/`document_*` tools are the verified mutation path; an agent uses one whenever one covers the operation. `script_exec` runs agent-supplied Python inside FreeCAD for the operations no typed tool covers. It is on by default (`FREECAD_BUDDY_SCRIPT_EXEC`, GUI preference `ScriptExec`), unregistered from the MCP tool list when off, and append-only audit-logged with its source. A run the operator marks unattended (`FREECAD_BUDDY_UNATTENDED=1`) leaves it unregistered unless the operator also sets `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`. No tool, RPC call, or wire field can change these switches at runtime. `script_exec` runs outside the AD-5 bracket (see AD-5), is never a `preview_dry_run` operation, and is never in the read-only assistant profile. In-process Python restriction (RestrictedPython, audit hooks, blacklists) is never called a security boundary; this repo ships no isolation boundary of its own, so the operator's environment is the only one. Accepted risk: with the default on, any holder of the HTTP bearer token, and any prompt injection that reaches the agent, can run code with the user's rights.

**AD-5 — add an exception sentence** at the end of the Rule:

NEW: `Exception: script_exec runs raw. It opens no bridge transaction, takes no fingerprint, and has no rollback; a script that changes geometry is checked by the agent with the verify_* tools afterwards. Its changes are in the undo history only when the script opens and commits its own transaction.`

**Consistency Conventions, Config row (line 385)**

OLD: `` Capability flags via env vars set by the human operator (`FREECAD_BUDDY_ALLOW_EXEC`, off unless `1`; `FREECAD_BUDDY_AUTO_APPROVE`, on unless set to another value than `1`); ``
… `` (`AutoApprove`, `AllowExec`, `AutoStartMcp`, `McpCommand`, `UvPath`, `AuditLogPath`) ``

NEW: `` Capability flags via env vars set by the human operator (`FREECAD_BUDDY_SCRIPT_EXEC` and `FREECAD_BUDDY_AUTO_APPROVE`, each on unless set to another value than `1`; `FREECAD_BUDDY_UNATTENDED` and `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED`, each off unless `1`, env only); ``
… `` (`AutoApprove`, `ScriptExec`, `AutoStartMcp`, `McpCommand`, `UvPath`, `AuditLogPath`) ``

### 4.2 `design/mcp-tools-design.md`

- §2 row (line 200). OLD: `` | `debug_exec` | 0 | Trusted-operator Python exec for bring-up/CI-authored scripts; see §5 | yes | ``
  NEW: `` | `script_exec` | 0 | Agent Python exec inside FreeCAD for operations no typed tool covers; raw, outside the AD-5 bracket; see §5 | yes | ``
- Line 135 (`query_capabilities`): `debug_exec` state → `script_exec` state.
- Lines 219–221. Replace "plus operator-only `debug_exec` (unregistered by default, never counted in
  the AI-visible registry)" with "plus `script_exec` (registered by default, gated by §5, kept
  outside `tool_specs()` so the G0.2 count is unchanged)". Replace `DEBUG_EXEC_SPEC` with
  `SCRIPT_EXEC_SPEC`.
- §5 heading and rules. NEW text:

  > ## 5. `script_exec` Registration Rules (AD-4)
  >
  > 1. **On by default.** Registered unless the operator sets `FREECAD_BUDDY_SCRIPT_EXEC` to a value other than `1`, or — GUI host, variable unset — clears the **Allow script_exec** preference (`ScriptExec`). When off it is *unregistered*: absent from `tools/list`, not present-and-refusing.
  > 2. **Unattended runs.** With `FREECAD_BUDDY_UNATTENDED=1` it is unregistered unless `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`. Both variables are read once at start, env only, exactly `"1"` is on.
  > 3. **Typed tools first.** Excluded from `preview_dry_run.operation.tool`, from the confirm flow, from the read-only assistant profile, and from every benchmark and gate toolset. `FREECAD_BUDDY_AUTO_APPROVE` does not gate it; an operator who wants per-call control turns `ScriptExec` off.
  > 4. **Raw.** No AD-5 bracket, fingerprint, or rollback (AD-5 exception). `mutating=True`, so a `TIMEOUT` marks the document suspect and the call writes an audit pair.
  > 5. **Audited.** Every call appends a `before` record carrying the full source ahead of execution, and an `after` record (AD-17).
  > 6. **Not a sandbox.** Namespace reduction (FreeCAD API globals only) is hygiene, never described as a security boundary (AD-35, exec-sandbox research Finding 1).

### 4.3 `design/security-and-service-design.md`

- Line 15 and §1 heading: `debug_exec` gating → `script_exec` gating.
- §1 opening. OLD: "`debug_exec` is a trusted-operator bring-up tool, never an AI capability. Four
  enforcement layers, all Phase 0:" NEW: "`script_exec` is the agent's Python path for operations no
  typed tool covers. It is on by default. Four layers control it:"
- Layer 1, rewrite: the switch is `FREECAD_BUDDY_SCRIPT_EXEC` or the **Allow script_exec**
  preference (`ScriptExec`, default on); on unless set to another value than `"1"`; the red risk text
  stays on the page; `FREECAD_BUDDY_UNATTENDED` and `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED` as in
  `mcp-tools-design.md` §5. Keep the sentences on immutable startup capture and on `user.cfg`
  persistence, with `AllowExec` → `ScriptExec` and `debug_exec` → `script_exec`.
- Layer 2 code block. NEW:

  ```python
  def register_tools(server, caps: Capabilities):
      for tool in TYPED_TOOLS:                      # query_*, document_*, sketch_*, ...
          server.add_tool(tool)
      if exec_registered(caps):
          server.add_tool(script_exec)
          log_stderr("SECURITY: script_exec ENABLED")

  def exec_registered(caps: Capabilities) -> bool:
      unattended_ok = not caps.unattended or caps.script_exec_unattended
      return caps.script_exec and unattended_ok and not caps.service_mode
  ```

  Replace the paragraph under it: "`unattended` is the operator's marker for a run with no human
  present (`FREECAD_BUDDY_UNATTENDED=1`). The bridge cannot detect it; the operator sets it. In a
  marked run `script_exec` stays unregistered unless the operator also sets
  `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`. Belt-and-suspenders: a call that reaches the tool while
  it is off returns `INVALID_INPUT` (defense against registration-logic bugs; not the boundary)."
- Layer 3: `debug_exec` → `script_exec` in the text and in the JSON example.
- Layer 4: `debug_exec` → `script_exec`.
- CI check line. NEW: "CI check: a test asserts `tools/list` includes `script_exec` when no variable
  is set, excludes it when `FREECAD_BUDDY_SCRIPT_EXEC=0`, excludes it when
  `FREECAD_BUDDY_UNATTENDED=1`, and includes it again when `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`
  is added."
- Threat model row 0 (line 78): "`script_exec` on by default, unregistered when off (AD-4)".
  Unattended row (line 81): "`script_exec` off unless the operator sets
  `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`".
- Diagram edge (line 105): `ScriptExec preference or FREECAD_BUDDY_SCRIPT_EXEC<br/>script_exec, off in a marked unattended run unless opted in`.
- Key reading (line 108). OLD ending: "which is why `debug_exec` is default-off and never enabled
  unattended." NEW: "`script_exec` is on by default; an attended operator accepts that risk, and an
  unattended run is protected only by the operator's marker and the operator's environment."
- Rejected-mechanism table (lines 118–119): `debug_exec` → `script_exec`.

### 4.4 Other design documents (rename, plus the new posture where stated)

- `integration-mcp-freecad.md:56` — "`exec_enabled` reflects AD-4 registration (`script_exec` is
  unregistered when false)". `:60` — `debug_exec` (gated) → `script_exec` (gated). `:99` — "`script_exec` is
  registered unless the operator turns it off — `FREECAD_BUDDY_SCRIPT_EXEC`, or in GUI mode the
  **Allow script_exec** preference with the variable unset — or the run is marked unattended without
  opt-in (AD-4)". `:141` table row: `| Allow script_exec | ScriptExec | on | FREECAD_BUDDY_SCRIPT_EXEC |`.
  `:266`: `exec_enabled` source → `FREECAD_BUDDY_SCRIPT_EXEC`, the `ScriptExec` preference, and the
  unattended marker (AD-4).
- `integration-mcp-clients.md:70` — "`script_exec` is in the tool list unless the operator turns it
  off or marks the run unattended (AD-4). Agents use it only when no typed tool covers the
  operation."
- `component-design.md:43` — `` | `script_exec.py` | P0 | Agent Python exec (AD-4): on by default, unregistered when off or unattended without opt-in, raw (AD-5 exception), audit-logged | contracts, shim | ``. `:83` — "gates `script_exec` registration (AD-4)". `:194` — `debug_exec` → `script_exec`.
- `project-structure.md:62` — `├── script_exec.py        # agent Python exec, on by default, raw, audit-logged (AD-4)`. `:331` — "24 AI-visible Phase 0 tools + `script_exec` (registered by default, outside `tool_specs()`)".
- `data-contracts-design.md:182` — example `"debug_exec"` → `"script_exec"`.
- `sequence-diagrams.md:25` — "the operator driving `debug_exec`" → "an agent calling `script_exec`".
  §8 retitled `Script path — script_exec`; intro: "On by default; unregistered when the operator turns
  it off, or in a marked unattended run without opt-in (AD-4). Raw: no AD-5 bracket." Diagram: actor
  `Operator` keeps the switch arrow ("sets the switches at start, never a wire field"); a new
  participant `Agent` makes the `script_exec(Python)` call; `U` is `usecases/script_exec`; note after
  the result: "no fingerprint or rollback — the agent checks with verify_* afterwards".

### 4.5 `epics.md`

- **FR19 (line 72).** OLD: "`debug_exec` exists as operator-only capability: env-flag gated,
  unregistered when off, permanently off in service mode, every call audit-logged. *(AD-4)*"
  NEW: "`script_exec` lets an agent run Python inside FreeCAD for operations no typed tool covers. On
  by default; unregistered when the operator turns it off, or in a run marked unattended without
  opt-in; permanently off in service mode; every call audit-logged with its source. *(AD-4)*"
- Coverage table (line 173): `debug_exec gating` → `script_exec gating`.
- Story 1.x AC5 (lines 346–348): done story, kept as history. No edit.
- **Story 10.6 AC2 (line 1343).** OLD: "**Given** a `debug_exec` that timed out" NEW: "**Given** a
  `script_exec` that timed out".
- **Story 10.7: add AC.** "**Given** the change to `script_exec` (sprint-change-proposal-2026-10-12)
  **When** the UAT suite is updated **Then** TC-01, TC-05, TC-08, TC-09, TC-11, `coverage-matrix.md`,
  `APPENDIX-B-environment-setup.md` and `test-plan.md` use `script_exec`, test it on by default, off
  with `FREECAD_BUDDY_SCRIPT_EXEC=0`, off with `FREECAD_BUDDY_UNATTENDED=1`, and on again with
  `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`; past run reports keep their text."
- **New epic**, after Epic 11:

  > ## Epic 12: Script Execution Tool
  >
  > An agent can do any FreeCAD operation: typed tools when they cover it, `script_exec` when they do not.
  >
  > **Why now:** the typed tools do not cover all of FreeCAD, and the exec tool was operator-only (sprint-change-proposal-2026-10-12).
  >
  > **Sequencing:** 12.1 runs before Story 10.6 (both edit the exec wiring in `hosts/tool_catalog.py`). **Opens no gate and reopens no epic** (AD-19).
  >
  > ### Story 12.1: script_exec as an Official Tool
  >
  > > **As** an agent, **I want** `script_exec` on by default, so that I can do an operation no typed tool covers.
  >
  > **Acceptance Criteria:**
  >
  > 1. **Given** no `FREECAD_BUDDY_*` exec variable and no preference stored **When** `tools/list` runs **Then** `script_exec` is present and `debug_exec` is absent; a call `script_exec(doc, code)` returns the same envelope `debug_exec` returned (`doc`, `stdout`, `value_repr`, `fingerprint_after: null`).
  > 2. **Given** `FREECAD_BUDDY_SCRIPT_EXEC=0`, or the GUI preference `ScriptExec` off with the variable unset **When** `tools/list` runs **Then** `script_exec` is absent, and a direct call returns `INVALID_INPUT` naming the switch and is audit-logged.
  > 3. **Given** `FREECAD_BUDDY_UNATTENDED=1` **When** `tools/list` runs **Then** `script_exec` is absent; with `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1` also set it is present. Any value other than exactly `"1"` is off for both variables.
  > 4. **Given** a `user.cfg` that stores `AllowExec=false` **When** the GUI bridge starts **Then** `script_exec` is registered; `FREECAD_BUDDY_ALLOW_EXEC` and `AllowExec` are read nowhere in `src/`.
  > 5. **Given** the GUI preference page **When** it opens **Then** it shows **Allow script_exec** (default on) with the red risk text, and the `addon.log` `operator settings:` line lists `FREECAD_BUDDY_SCRIPT_EXEC`, `FREECAD_BUDDY_UNATTENDED` and `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED` with their sources.
  > 6. **Given** the read-only assistant profile and `preview_dry_run` **When** they are built or called **Then** neither includes or accepts `script_exec`.
  > 7. **Given** a `script_exec` call **When** its `before` audit record is written **Then** the record carries the full `code`, ahead of execution (closes DW-19).
  > 8. **Given** the skill `freecad-scripting-idioms` **When** an agent reads it **Then** it says: use a typed tool when one covers the operation; else use `script_exec`; open and commit a transaction in the script so `document_undo` covers it; check geometry with `verify_*` afterwards; never loop without an exit, because a script that does not return freezes the GUI host. `check_skill_shape.py` passes.
  > 9. **Given** `README.md`, `AGENTS.md`, `CLAUDE.md` section 16 and `_bmad-output/project-context.md` **When** read **Then** they describe the new name, default and variables.
  > 10. The CI checks pass: `uv run ruff check .`, `uv run pytest tests/external`, the `infc` suite under `FreeCADCmd`, `scripts/check_imports.py`, `scripts/check_skill_shape.py` and `scripts/gen_schemas.py --check`.

### 4.6 `docs/intent.md:210`

OLD: "operator-only `debug_exec`" NEW: "`script_exec` for operations no typed tool covers".

### 4.7 Story 10.6 spec — `spec-10-6-headless-bounded-execution.md`

The spec is `status: 'draft'`. After Story 12.1 lands, replace `debug_exec` with `script_exec` in
the Problem paragraph and the Code Map line for `tool_catalog.py`. The frozen intent does not change.

### 4.8 Skill — `skills/freecad-scripting-idioms/SKILL.md` (done in Story 12.1)

OLD (lines 53–56):
> - Drive every mutation through the **typed tools** (`sketch_*`, `feature_*`, `document_*`), never through free-form code, because the typed path runs the transaction, verification, and reference audit around the change — raw execution bypasses all of it and leaves an unverified, possibly corrupt document.

NEW:
> - Drive a mutation through a **typed tool** (`sketch_*`, `feature_*`, `document_*`) whenever one covers it, because the typed path runs the transaction, verification, and reference audit around the change. Use `script_exec` only for an operation no typed tool covers. It runs raw: open and commit a transaction in the script (`doc.openTransaction(...)` … `doc.commitTransaction()`) so `document_undo` covers it, then check the result with `verify_*`. A script must always return — one that loops forever freezes FreeCAD.

OLD (lines 109–111):
> - **Free-form execution for a mutation.** Symptom: an unverified or corrupt document that recompiled fine. Why: raw code bypassed the transaction/verify/audit wrapper. Fix: use the typed `sketch_*`/`feature_*`/`document_*` tools.

NEW:
> - **`script_exec` where a typed tool exists.** Symptom: an unverified or corrupt document that recomputed fine. Why: raw code bypassed the transaction/verify wrapper. Fix: use the typed tool; when none exists, wrap the script in a transaction and run `verify_*` after it.

### 4.9 Sprint status — `sprint-status.yaml`

Add after `epic-11-retrospective`:

```yaml
  epic-12: backlog
  12-1-script-exec-official-tool: backlog
  epic-12-retrospective: optional
```

Add a sequencing note: "Epic 12 (sprint-change-proposal-2026-10-12) makes `script_exec` an official
tool. 12-1 runs before 10-6. Opens no gate, reopens no epic."

## 5. Implementation Handoff

**Scope: Major.** An adopted spine decision (AD-4) is reversed and AD-5 gets an exception.

| Who | Does what |
| --- | --- |
| Architect (TanNT approval) | Approves §4.1–§4.4 spine and design edits. Applied with this proposal. |
| PO / SM | Applies §4.5, §4.6, §4.9: FR19, Epic 12, Story 10.6 AC2, Story 10.7 AC, intent, sprint status. Applied with this proposal. |
| Developer (`bmad-build`) | Story 12.1: code, tests, skill, README/AGENTS/CLAUDE/project-context. Then §4.7 rename in the 10.6 spec. |
| Developer, Story 10.7 | UAT test case rewrite. |

**Success criteria**

- `tools/list` on a fresh install shows `script_exec` and no `debug_exec`.
- The four switch cases in Story 12.1 AC1–AC3 each have a passing test.
- No document under `_bmad-output/planning-artifacts/architecture/`, `docs/intent.md`, `README.md`,
  `AGENTS.md`, `CLAUDE.md` or `skills/` names `debug_exec`, `FREECAD_BUDDY_ALLOW_EXEC` or `AllowExec`,
  except review documents under `reviews/` (history).
- A live GUI check: an agent creates an object with `script_exec`, and the FreeCAD window shows it.
