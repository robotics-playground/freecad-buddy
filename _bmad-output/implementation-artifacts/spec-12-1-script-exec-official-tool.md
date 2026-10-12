---
title: 'script_exec as an official tool, on by default'
type: 'feature'
created: '2026-10-12'
status: 'done'
route: 'dispatch'
baseline_commit: 'e1c977f9a7003a7ea3ab216db24d2a0e00c64926'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-12-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/security-and-service-design.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The typed MCP tools do not cover all of FreeCAD, and the only Python exec tool, `debug_exec`, is operator-only and off by default (`FREECAD_BUDDY_ALLOW_EXEC=1` or `AllowExec`). An agent cannot do an operation no typed tool covers.

**Approach:** Rename `debug_exec` to `script_exec` and register it by default. One switch turns it off (`FREECAD_BUDDY_SCRIPT_EXEC`, GUI preference `ScriptExec`). An operator marker for unattended runs turns it off unless the operator opts in. The exec body, timeout, audit pair and suspect rules stay as they are. The skill tells agents to prefer typed tools.

**Decisions (human, 2026-10-12, sprint-change-proposal-2026-10-12):**
- D1: rename, no alias. `FREECAD_BUDDY_ALLOW_EXEC` and `AllowExec` are deleted; a stale `AllowExec=false` is ignored.
- D2: `FREECAD_BUDDY_SCRIPT_EXEC` is on unless set to a value other than `"1"` (same rule as `FREECAD_BUDDY_AUTO_APPROVE`). Preference `ScriptExec` defaults on.
- D3: `FREECAD_BUDDY_UNATTENDED=1` unregisters it unless `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`. Both env-only; exactly `"1"` is on.
- D4: raw exec, outside the AD-5 bracket. `FREECAD_BUDDY_AUTO_APPROVE` does not gate it.

## Boundaries & Constraints

**Always:**
- Switches are read once at start into the frozen `Capabilities` record.
- Off means unregistered: absent from `tools/list`; a direct call still gets the `INVALID_INPUT` denied envelope and an audit pair.
- `script_exec` stays out of `READ_ONLY_PROFILE`, `preview_dry_run`, and `tool_specs()` (G0.2 count stays 45).
- `mutating=True`, `audit_event="exec"`, `timeout_s=30.0`, and the inner `bound_off_main_thread` layer keep their current behaviour.

**Never:**
- No edit under `tests/uat/` (Story 10.7) or `dist/` (build output). Past specs and run reports keep their text.
- No change to the exec body, to `service_mode`, or to the GUI-host freeze risk (Story 10.6, deferred work).
- No new preference for the two unattended variables.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Default | no exec variable, no preference | `script_exec` listed; `debug_exec` not listed | N/A |
| Switched off | `FREECAD_BUDDY_SCRIPT_EXEC=0` (or `""`, `"true"`) | not listed | direct call → `INVALID_INPUT` naming the switches, audited |
| Unattended | `FREECAD_BUDDY_UNATTENDED=1` | not listed | as above |
| Unattended opt-in | `UNATTENDED=1` + `SCRIPT_EXEC_UNATTENDED=1` | listed | N/A |
| Marker not exactly 1 | `UNATTENDED=true` | listed (marker off) | N/A |
| Stale preference | `user.cfg` has `AllowExec=false`, no `ScriptExec` | listed | N/A |
| Service mode | `service_mode=True`, all switches on | not listed | as above |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/debug_exec.py` -- `git mv` to `script_exec.py`; rename function, docstring, `ValidationError("script_exec requires 'code'")`.
- `src/freecad_buddy/usecases/capabilities.py:19-44` -- `Capabilities.allow_exec` → `script_exec` (required); add `unattended`, `script_exec_unattended` (default `False`); `from_env` reads the three variables; `exec_registered` takes the epic-context rule. Add `SCRIPT_EXEC_VARIABLE` constants and `SCRIPT_EXEC_WARNING` beside `AUTO_APPROVE_WARNING`.
- `src/freecad_buddy/usecases/operator_settings.py:17-82` -- replace `ALLOW_EXEC_VARIABLE`; add the two unattended variables to `OPERATOR_VARIABLES` (so the `addon.log` `operator settings:` line in `bootstrap.py:195-203` lists them) and to the present-even-empty rule of `variable_is_set`; `PreferenceValues.script_exec = True`; overlay writes only `SCRIPT_EXEC`.
- `src/freecad_buddy/usecases/shim.py:31,415` -- `SCRIPT_EXEC_KEY = "ScriptExec"`.
- `src/freecad_buddy/hosts/gui_addon/preferences.py:16-22,48-55,87,100,114,144` -- checkbox **Allow script_exec**, tooltip, red risk text (new wording below).
- `src/freecad_buddy/hosts/tool_catalog.py:11,26,954,992,1051-1073,1505,1540-1546,1595,1612` -- `SCRIPT_EXEC_SPEC` with new description; rename every mention.
- `src/freecad_buddy/hosts/gui_external/entry.py:35,114-115` -- import and append `SCRIPT_EXEC_SPEC`.
- `src/freecad_buddy/adapters/mcp_server.py:5,75,80,219,239,271,319` -- names; startup log uses `SCRIPT_EXEC_WARNING`; `_denied_exec_envelope` message.
- `src/freecad_buddy/adapters/rpc_dispatch.py:58,63`, `rpc_listener.py:331`, `audit_log.py:3-7,81` -- rename. `audit_log.py:60-65` already persists `code` on `event:"exec"` (DW-19 done 2026-07-23, `72eb277`); keep it.
- Tests to update: `tests/external/test_mcp_surface.py` (334-350, 406, 714, 862, 877), `test_operator_settings.py` (60, 85, 142), `test_rpc_listener.py:510`, `test_confirm_contract.py`, `test_assistant_readonly_profile.py`, `test_gui_external_proxy.py`, `tests/infc/test_bootstrap_settings.py`, `tests/infc/test_preview.py:387`.
- `skills/freecad-scripting-idioms/SKILL.md:53-56,109-111` -- text from proposal §4.8. Body is 1,191 words; limit 1,500.
- `README.md:183,194,230,237,270-272`, `AGENTS.md:269,438`, `CLAUDE.md:269,438`, `_bmad-output/project-context.md:95,144` -- new name, default, variables.
- After 12.1: `spec-10-6-headless-bounded-execution.md` Problem paragraph and `tool_catalog.py` Code Map line → `script_exec`.

## Tasks & Acceptance

**Execution:**
- [x] `usecases/` (capabilities, operator_settings, shim, script_exec) -- switches, rule, rename -- core of D1–D3.
- [x] `adapters/` + `hosts/` files in Code Map -- rename, warning, denied message, preference page -- surface follows the rule.
- [x] tests in Code Map -- rename; replace `test_capabilities_from_env_reads_flag_exactly_one` with one `Should ... When ...` AAA test per matrix row; add stale-`AllowExec` test in `test_bootstrap_settings.py` -- prove D1–D3.
- [x] skill, README, AGENTS.md, CLAUDE.md, project-context -- docs match code.
- [x] `spec-10-6-headless-bounded-execution.md` -- rename -- keep 10.6 accurate.

**Acceptance Criteria:**
- Given the GUI preference page, when it opens, then it shows **Allow script_exec** checked by default with the red risk text, and the `operator settings:` log line lists `FREECAD_BUDDY_SCRIPT_EXEC`, `FREECAD_BUDDY_UNATTENDED` and `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED` with sources.
- Given an enabled server, when `script_exec(doc, code)` runs, then the envelope keeps `doc`, `stdout`, `value_repr`, `fingerprint_after: null`, and the `before` audit line carries `code`.
- Given `src/`, `skills/`, `README.md`, `AGENTS.md`, `CLAUDE.md`, when grepped, then no `debug_exec`, `FREECAD_BUDDY_ALLOW_EXEC`, `allow_exec` or `AllowExec` remains.

## Design Notes

Text the operator and agent read (keep the meaning; wording may be tightened):
- Tool description: "Run Python inside FreeCAD for an operation no typed tool covers. Globals: `FreeCAD`/`App`, `Part`, `doc`; set `result` to return its repr. Raw: no transaction, fingerprint or rollback. Open and commit a transaction in the script so `document_undo` covers it, and check geometry with `verify_*` afterwards. Every call is audit-logged with its source."
- `SCRIPT_EXEC_WARNING`: "SECURITY: script_exec ENABLED: any MCP client of this bridge can run Python with your user rights (to turn it off, clear Allow script_exec in Edit > Preferences > FreeCAD Buddy, or set FREECAD_BUDDY_SCRIPT_EXEC=0)".
- Denied message: "script_exec is off: FREECAD_BUDDY_SCRIPT_EXEC or the ScriptExec preference turned it off, or FREECAD_BUDDY_UNATTENDED=1 is set without FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1".
- Preference risk text: "script_exec runs any Python inside FreeCAD with your user rights, for any MCP client of this bridge. Turn it off when you do not trust the agent or what it reads. For an unattended agent, set FREECAD_BUDDY_UNATTENDED=1 or use an isolated computer."

## Verification

**Commands:**
- `uv run ruff check .` -- expected: clean
- `uv run pytest tests/external -q` -- expected: all pass
- `uv run python scripts/check_imports.py`, `scripts/check_skill_shape.py`, `scripts/gen_schemas.py --check` -- expected: pass
- `FreeCADCmd tests/run_tests.py` (the `infc` suite) -- expected: pass
- `git grep -n -e debug_exec -e ALLOW_EXEC -e allow_exec -e AllowExec -- src skills README.md AGENTS.md CLAUDE.md` -- expected: no output

**Manual checks:**
- Live GUI: open FreeCAD, call `script_exec` through `mcp__freecad-buddy__*` to create a box; the FreeCAD window shows it (visual check required).

## Implementation Notes

- DW-19 was already done (`72eb277`): `audit_log.py` stores `code` on `event:"exec"`. Review found the real tool (`mutating=True`) wrote that `before` line only after dispatch; `mcp_server.py` and `rpc_listener.py` now write it ahead of dispatch when `audit_event == "exec"`, and the two audit tests use `SCRIPT_EXEC_SPEC` settings.
- `bootstrap.start_bridge` logs `SCRIPT_EXEC_WARNING`; before this, no GUI start logged an exec warning.
- Verified: `ruff check` clean; `pytest tests/external` 1431 passed; `FreeCADCmd tests/run_tests.py` 855 OK (1 skipped); `check_imports`, `check_skill_shape`, `gen_schemas --check` pass; old-name grep empty.
- Live GUI (patched tree): `addon.log` has the `SECURITY: script_exec ENABLED` line and the three variables in `operator settings:`; `tools/list` has 46 tools with `script_exec`, no `debug_exec`; a script made a 30x20x10 box (`value_repr` `6000.0`); audit `before` (with `code`) 88 ms ahead of `after`; screenshot shows the box.
- Not checked live: the preference page look (the modal dialog blocks UIA automation).

## Spec Change Log

## Review Triage Log

| # | Source | Finding | Verdict | Evidence | Route |
|---|--------|---------|---------|----------|-------|
| 1 | verification-gap, edge-case | `script_exec` `before` audit line written after dispatch, not ahead | medium | `SCRIPT_EXEC_SPEC.mutating=True` (`tool_catalog.py:1070`); `mcp_server.py:278` and `rpc_listener.py:334` write early only `if ... not mutating`; tests register stubs with `mutating=False` | patch |
| 2 | impl report, verification-gap, edge-case | GUI host logs no `SCRIPT_EXEC_WARNING` | medium | `bootstrap.py:127-129` logs only `AUTO_APPROVE_WARNING`; `build_proxy_server` logs nothing | patch |
| 3 | verification-gap | no test asserts `SCRIPT_EXEC_WARNING` on `build_server` | low | no `caplog`/`assertLogs` on it in `tests/` | patch |
| 4 | verification-gap, blind | GUI proxy registry never tested with exec on | medium | `test_gui_external_proxy.py:65,96` pass `script_exec=False` only; inverting `entry.py:114-115` fails no test | patch |
| 5 | blind, impl report | skill still sends gaps to `freecadcmd` on a closed doc | medium | `SKILL.md:80-84` "The fallback for a gap is a headless script on the closed document" contradicts new rule at 53-59 | patch |
| 6 | blind | skill gives no failure path for an open transaction, no budget note | low | `SKILL.md:56-58` says open/commit only; direct text fix | patch |
| 7 | blind | skill description has no trigger for "no tool covers this" | low | `SKILL.md:4-11` triggers omit it; direct text fix. Version bump part: no named harm | patch |
| 8 | blind | schema/docstring test skips `script_exec` | low | `test_every_tool_has_input_output_schema_and_docstring` builds `Capabilities(script_exec=False)` | patch |
| 9 | blind | no test for `SCRIPT_EXEC=0` with unattended opt-in | low | combination untested; code returns off | patch |
| 10 | blind | denied-call test does not check `code` on the `before` record | low | test asserts event/tool/verdict only | patch |
| 11 | blind | README says unset `SCRIPT_EXEC` is on; GUI unset means preference decides; line wrap | low | `README.md` variable table and lines 71-72 | patch |
| 12 | impl report | `spec-10-6` lines 74, 82 still say `debug_exec` | low | grep shows both, outside frozen block | patch |
| 13 | self | provenance comment "Older releases stored this key" | low | `test_bootstrap_settings.py:280`; commenting standard forbids provenance | patch |
| 14 | blind | denied message lists every cause, not service_mode | false | `service_mode` is never set by any caller; text matches spec Design Notes | reject |
| 15 | blind, edge-case | preference page shows exec checked while unattended marker turns it off | low | real, but GUI + unattended marker is rare and fix adds a branch | reject |
| 16 | blind | audit record shape in design (`exec_call`, `code_sha256`, `caller`) differs from code | medium | pre-existing drift: `audit_log.py` writes `event:"exec"`, `params_digest`, `code` since `72eb277` | defer |
| 17 | blind | `CLAUDE.md`/`AGENTS.md` "headless automation is unaffected" now false; no automation sets the marker | medium | headless `tools/list` now includes `script_exec`; fix edits agent-context files | defer |
| 18 | blind | sprint-status vs spec status, empty Implementation Notes | false | sprint sync to `review` happens at step 5; fix edits this spec | reject |
| 19 | blind | `docs/decisions/010`, `011` still name `debug_exec` | false | decision records are history of a past decision, not current-state docs | reject |
| 20 | impl report | audit `actor` is `"operator"` for agent calls | low | pre-existing default in `AuditSink.__init__`; not caused by this change | defer |
| 21 | impl report | `ruff format --check` flags files not edited | false | pre-existing (`test_bootstrap_settings.py:59` and 4 others); CI runs `ruff check` only | reject |
| 22 | impl report, blind | preference page look not checked live | maybe-false | modal dialog blocks UIA; needs a screenshot with the dialog open | verify at presentation |
| 23 | edge-case | GUI proxy direct call when off returns unknown method, no audit pair | low | pre-existing: `build_proxy_server` has no denied path for `debug_exec` either | defer |
| 24 | edge-case | hand-started or orphan proxy lists `script_exec` while listener has it off | medium | proxy reads its own env (`entry.py:185`); new default makes mismatch reachable when `ScriptExec` is off | defer |
| 25 | edge-case | removed `FREECAD_BUDDY_ALLOW_EXEC=0` ignored without notice | low | real but rare (old default was already off); D1 deletes it; fix adds a startup branch | reject |
