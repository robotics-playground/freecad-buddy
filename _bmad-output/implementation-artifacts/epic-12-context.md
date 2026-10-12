# Epic 12 Context: Script Execution Tool

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Let an agent do any FreeCAD operation. The agent uses a typed tool (`sketch_*`, `feature_*`, `document_*`, `query_*`, `verify_*`, `export_*`) when one covers the operation, and uses `script_exec` when none does. Today the typed tools do not cover all of FreeCAD, and the only Python exec tool (`debug_exec`) is operator-only and off by default. This epic renames that tool to `script_exec`, turns it on by default, adds an operator marker for unattended runs, stores each script's source in the audit log, and teaches agents (through the skill) when and how to use it. The architecture and design documents already describe the new posture; the code, tests, skill and operator docs do not yet.

## Stories

- Story 12.1: script_exec as an Official Tool

## Requirements & Constraints

- **Rename, no alias.** `debug_exec` becomes `script_exec` everywhere in `src/`, tests, skill and operator docs. The old tool name must not appear in `tools/list`. Envelope stays the same: input `{doc, code}` (explicit doc handle required), result `{doc, stdout, value_repr, fingerprint_after: null}`.
- **Switch, on by default.** `FREECAD_BUDDY_SCRIPT_EXEC`: on unless set to a value other than `"1"`. GUI host: preference `ScriptExec` ("Allow script_exec", default on) fills the value only when the variable is unset; a set variable wins.
- **Old switch deleted.** `FREECAD_BUDDY_ALLOW_EXEC` and `AllowExec` are read nowhere in `src/`. A stale `AllowExec=false` in `user.cfg` is ignored, so `script_exec` is registered.
- **Unattended marker.** `FREECAD_BUDDY_UNATTENDED=1` leaves `script_exec` unregistered unless `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1` is also set. Both are env only, read once at start; any value other than exactly `"1"` is off.
- **Off means unregistered.** When off, `script_exec` is absent from `tools/list`. A direct call that still reaches it returns `INVALID_INPUT` naming the switch, and is audit-logged (defense against registration bugs, not the boundary).
- **Exclusions.** Never in the read-only assistant profile (`build_readonly_profile`), never accepted as a `preview_dry_run` operation, not in the confirm flow, not in any benchmark or gate toolset. `FREECAD_BUDDY_AUTO_APPROVE` does not gate it.
- **Audit with source (DW-19, done 2026-07-23 in `audit_log.py`; keep it).** Every call writes a `before` record that carries the full `code` (plus `code_sha256`), written ahead of execution so it survives a call that never returns; then an `after` record.
- **GUI preference page** shows "Allow script_exec" (default on) with the red risk text. The `addon.log` `operator settings:` line lists `FREECAD_BUDDY_SCRIPT_EXEC`, `FREECAD_BUDDY_UNATTENDED` and `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED` with their sources.
- **Skill `freecad-scripting-idioms`** must say: use a typed tool when one covers the operation, else `script_exec`; open and commit a transaction in the script (`doc.openTransaction(...)` ... `doc.commitTransaction()`) so `document_undo` covers it; check geometry with `verify_*` afterwards; never loop without an exit, because a script that does not return freezes the GUI host. Replace the current "never free-form code" rule and its failure-mode entry. `check_skill_shape.py` must pass.
- **Operator docs** (`README.md`, `AGENTS.md`, `CLAUDE.md` section 16, `_bmad-output/project-context.md`) describe the new name, default and variables. README keeps the advice to run an unattended agent on an isolated computer or account.
- **Tests:** one passing test per switch case: default on; off with `FREECAD_BUDDY_SCRIPT_EXEC=0`; off with `FREECAD_BUDDY_UNATTENDED=1`; on again with `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1` added.
- **Done when** these pass: `uv run ruff check .`, `uv run pytest tests/external`, the `infc` suite under `FreeCADCmd`, `scripts/check_imports.py`, `scripts/check_skill_shape.py`, `scripts/gen_schemas.py --check`. Live check: an agent creates an object with `script_exec` in the GUI and the FreeCAD window shows it.
- **Grep check:** no file under the architecture folder (except `reviews/`), `docs/intent.md`, `README.md`, `AGENTS.md`, `CLAUDE.md` or `skills/` names `debug_exec`, `FREECAD_BUDDY_ALLOW_EXEC` or `AllowExec`.

## Technical Decisions

- **AD-4 (typed tools first, script_exec for the rest).** No tool, RPC call or wire field can change the switches at runtime. All switches are captured once at startup into an immutable capability record.
- **Registration rule:**
  ```python
  def exec_registered(caps) -> bool:
      unattended_ok = not caps.unattended or caps.script_exec_unattended
      return caps.script_exec and unattended_ok and not caps.service_mode
  ```
  `service_mode` is a dead gate (no caller sets it). Keep it as it is; it is Epic 5 scope.
- **AD-5 exception: raw exec.** `script_exec` opens no bridge transaction, takes no fingerprint, has no rollback. It stays `mutating=True`, so a `TIMEOUT` marks the document suspect and the call writes an audit pair. Exec body, timeout, audit pair and suspect-set rules do not change.
- **G0.2 count unchanged.** `SCRIPT_EXEC_SPEC` (renamed from `DEBUG_EXEC_SPEC`) stays outside `tool_specs()`; `tool_specs()` returns 45, 46 registered specs with `SCRIPT_EXEC_SPEC`.
- **Capability name `exec_enabled` stays.** Its source becomes `FREECAD_BUDDY_SCRIPT_EXEC`, the `ScriptExec` preference, and the unattended marker. `query_capabilities` reports `script_exec` state.
- **Not a sandbox (AD-35).** Namespace reduction to FreeCAD globals is hygiene only, never called a security boundary. Accepted risk: with the default on, any holder of the `:8765` bearer token, and any prompt injection reaching the agent, can run code with the user's rights.
- **Preference persistence.** `ScriptExec` lives in `user.cfg` under `User parameter:BaseApp/Preferences/Mod/FreeCADBuddy`. GUI bridge reads it once at start and writes the effective value into its own environment, so the MCP proxy child inherits it.
- **Ring placement (AD-1):** env reading and capability record in `usecases/` (`capabilities.py`, `operator_settings.py`, `shim.py`); registration gate and denied envelope in `adapters/` (`mcp_server.py`, `rpc_dispatch.py` audit rule); preference UI and bootstrap in `hosts/gui_addon/`; spec and read-only exclusion in `hosts/tool_catalog.py`.

## Cross-Story Dependencies

- **Before Story 10.6.** Both edit the exec wiring in `hosts/tool_catalog.py` (the inner bound `bound_off_main_thread`). After 12.1 lands, the 10.6 spec (`status: draft`) replaces `debug_exec` with `script_exec` in its Problem paragraph and Code Map line; its intent does not change.
- **Story 10.7** owns the UAT test case rewrite (TC-01, TC-05, TC-08, TC-09, TC-11, coverage matrix, Appendix B, test plan). Story 12.1 does not edit `tests/uat/`. Past run reports keep their text.
- **Epic 5 (backlog)** inherits the unattended marker and the dead `service_mode` gate.
- **Known open risks this epic makes more likely, not fixed here:** a script that never returns freezes the GUI Qt main thread (listener returns `TIMEOUT`, FreeCAD stays frozen); an abandoned exec body holds the `DocumentRegistry` lock. Story 10.6 fixes both on the headless host only.
- Opens no gate and reopens no done epic (AD-19). G1 uses the read-only profile, so gate measurements do not change.
