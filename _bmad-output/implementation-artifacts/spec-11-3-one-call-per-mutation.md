---
title: 'One call per mutation'
type: 'feature'
created: '2026-10-07'
status: 'done'
baseline_commit: 'bf1ce5f2644182b33f3effa30d74cedffddb2456'
route: 'dispatch'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Attended GUI work spends a `preview_dry_run` round trip on every mutation. The auto-approve posture exists in code but is off unless the operator sets a variable, nothing proves it in the live GUI, and nothing documents it. Hiding or showing an object through `feature_set_parameters` needs a preview token, although it changes no geometry.

**Approach:** Make auto-approve the default posture of every host: a mutation without `confirm` applies in one call under the full AD-5 bracket, and `FREECAD_BUDDY_AUTO_APPROVE=0` restores the confirm gate. Add one gate carve-out: a `feature_set_parameters` call without `confirm` whose `parameters` has only `Visibility` is approved as display state. Document the operator setup and prove both in the GUI.

**Decisions (human, 2026-10-07):**
- D1 — Auto-approve is ON by default in every host (GUI, external proxy, headless, CI). `Capabilities.from_env`: unset or `"1"` → on; any other value (`"0"`, `"false"`, `""`) → off. Code-constructed `Capabilities(...)` and the unarmed `confirm._AUTO_APPROVE` keep `False`; only the environment reading changes. This reverses the AD-10 headless fail-closed rule; spine, design documents and `epics.md` Story 11.3 AC1/AC4 are updated to match.
- D2 — Audit records follow the change proposal and Epic 11: an auto-approved `approval` line carries `source: "FREECAD_BUDDY_AUTO_APPROVE"`. The other drift between `data-contracts-design.md` `AuditRecord.approval` and the shipped record (mode names, `diff_digest`) is logged in `deferred-work.md`, not fixed here.
- D3 — Create a root `README.md` holding an "Operator setup" section; the GUI harness standard gets the same setup.
- D4 (review, 2026-10-07) — Auto-approve covers only a call with no `confirm`. A call that sends `confirm` takes the full token check in every posture: a stale, expired, forged or wrong-document token is refused with `INVALID_INPUT`, and an accepted one is logged `preview_token`.

## Boundaries & Constraints

**Always:**
- Every approved call, carve-out included, runs `run_mutation` and writes one `approval` audit line.
- The posture comes only from the environment, read once at host start. A wire field never sets it (`_CONFIRM_SCHEMA` keeps no `autoApprove`; a client-sent `autoApprove` stays refused).
- With `FREECAD_BUDDY_AUTO_APPROVE=0`, every mutation other than the carve-out needs a valid `preview_id`. `preview_dry_run` stays available in both postures.

**Never:**
- No change to `usecases/transaction.py`, `fingerprint.py`, `tnp_guard.py` or the gate's fingerprint call count (Story 11.4).
- No skill text changes (Story 11.5). No MCP elicitation.
- The carve-out never applies when `confirm` is present (token path), or when `parameters` holds any key besides `Visibility`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Default posture, pad | variable unset, no `confirm` | applies; approval `mode: "auto_approve"`, `source` set | N/A |
| Posture on, post-verify fails | failing op | same `status`, `rolled_back`, `rollback_proven` as the token path | N/A |
| Gate on, Visibility only | `=0`, `{"Visibility": false}`, no `confirm` | applies; approval `mode: "display_state"`; `changed: []` | N/A |
| Posture on, Visibility only | default, same input | applies; approval `mode: "display_state"` | N/A |
| Gate on, Visibility plus other key | `{"Visibility": false, "Length": ...}` | refused, no snapshot | `INVALID_INPUT` |
| Gate on, Visibility bad value | `{"Visibility": "no"}` | refused by precheck | `INVALID_INPUT` |
| Gate on, other tool | `feature_pad`, no `confirm` | refused | `INVALID_INPUT` |
| Posture on, token sent | valid `preview_id` | applies; approval `mode: "preview_token"` | stale/expired/forged: `INVALID_INPUT` |
| Env values | unset / `1` / `0` / `true` / `""` | on / on / off / off / off | N/A |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/usecases/capabilities.py:21-31` -- `from_env` per D1; docstring states the default.
- `src/freecad_buddy/usecases/confirm.py:300-350` -- `gate_mutation`: add the carve-out after the exemption branch and the fingerprint read, before `verify_confirm`. Test: `tool == "feature_set_parameters"`, `params.get("confirm") is None`, `params["parameters"]` a dict with keys exactly `{"Visibility"}`. `verify_confirm` (`:237-244`) adds `source` to the `auto_approve` record. `spend_confirm` and `audit_approval` already handle non-token modes.
- `src/freecad_buddy/contracts/confirm.py:30-35` -- `ApprovalRecord.mode` gains `"display_state"`; `source: NotRequired[str]`. In no generated schema (`audit-record.schema.json` types `approval` as plain object).
- `src/freecad_buddy/usecases/features.py:1697,1785` -- no change: `_parameter_writes` validates `Visibility` as `App::PropertyBool`; precheck runs after the gate.
- `src/freecad_buddy/hosts/tool_catalog.py:249-271,788-806` -- `_CONFIRM_SCHEMA` description: needed only when the operator set `FREECAD_BUDDY_AUTO_APPROVE=0`, except a `Visibility`-only `feature_set_parameters`; `feature_set_parameters` description names the carve-out. Comment at `:249` stays true.
- Reuse, do not rewrite: GUI arms the posture in `hosts/gui_addon/bootstrap.py:92-106` via `build_inline_handlers` (`tool_catalog.py:1476-1477`); approval sink `adapters/rpc_listener.py:130`; SECURITY warning `adapters/mcp_server.py:166` (now logs by default).
- Unaffected by D1: `benchmarks/g2/case_run.py` (no host; module posture stays `False`, records stay `preview_token`); `tests/infc/test_g2_driver.py:80` sets the posture explicitly. `scripts/automation/run_mcp_e2e.py:48` passes `os.environ` to a headless child and does not test refusal.
- Tests: `tests/infc/test_confirm_gate.py` `_GateFixture` (`:52`, posture off), `AutoApprovePostureTest` (`:427`), `ApprovalAuditTest` (`:445`, `_RecordingSink`); `tests/external/test_confirm_contract.py:216-220` (env reading, flips for `{}`), `:87-92` (no published schema names `auto_approve`).
- Planning text to change per D1: `ARCHITECTURE-SPINE.md` AD-10 and `:342`, `:384`; `mcp-tools-design.md` §1.4 (`:101`) and §4 (`:545-553`, also removes the `autoApprove` `Confirm` field the code refuses, `confirm.py:72`); `data-contracts-design.md:195`; `integration-mcp-clients.md:121-123,144`; `component-design.md:78`; `_bmad-output/project-context.md:98`; `epics.md:1477,1480`; `epic-11-context.md` auto-approve bullet. The dated change proposal is a record and is not edited.
- `.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md` §2 Launch (`:49-63`). FreeCAD inherits a variable only from the process that starts it.

## Tasks & Acceptance

**Execution:**
- [x] `usecases/capabilities.py`, `contracts/confirm.py`, `usecases/confirm.py` -- D1 default, D2 `source`, `display_state` carve-out -- AC1-AC4.
- [x] `hosts/tool_catalog.py` -- descriptions per Code Map -- AC3, AC4.
- [x] `tests/infc/test_confirm_gate.py` -- one test per I/O matrix row except env values; the post-verify row runs the same failing call with a token and under the posture and compares `status`, `rolled_back`, `rollback_proven`; carve-out rows read the approval line from `_RecordingSink` and assert a `mutation` block -- AC1-AC4.
- [x] `tests/external/test_confirm_contract.py` -- env-values row; `display_state` in no published schema -- AC1, AC3.
- [x] Planning text per Code Map; `deferred-work.md` entry per D2 -- D1, D2.
- [x] `README.md` (new) and harness standard §2 -- variable, default on, `=0` to require previews, set before FreeCAD starts, Windows `setx` and per-shell forms, `preview_dry_run` stays available -- AC5.
- [x] GUI UAT with `cua-driver` per the harness standard: launch with the variable unset, `feature_pad` without `confirm`, read the `approval` line, visual check; relaunch with `=0`, `Visibility`-only call applies and the object is hidden on screen, `feature_pad` without `confirm` is refused. Evidence under `tests/uat/run/` -- AC1, AC3, AC4.

**Acceptance Criteria:**
- Given FreeCAD started without the variable, when an agent calls `feature_pad` without `confirm` in the GUI, then the pad applies under the full bracket and the audit log has an `approval` line with `mode: "auto_approve"` and `source: "FREECAD_BUDDY_AUTO_APPROVE"`.
- Given the posture on and a mutation that fails post-verify, then it rolls back and returns the same status as the token path.
- Given `FREECAD_BUDDY_AUTO_APPROVE=0` and `feature_set_parameters` writing only `Visibility` without `confirm`, then it applies and is audit-logged; a call that also writes another property is refused.
- Given `FREECAD_BUDDY_AUTO_APPROVE=0`, then every other mutation without a valid `preview_id` returns `INVALID_INPUT`.
- Given `README.md` and the harness standard, then both state the default, the `=0` opt-out, that it must be set before FreeCAD starts, how to set it on Windows, and that `preview_dry_run` stays available.

## Implementation Notes

## Spec Change Log

## Review Triage Log

- Pass 1: under the default posture `verify_confirm` (`confirm.py:243-251`) returns `auto_approve` before reading a supplied `confirm`, so a stale, expired or forged `preview_id` applies unchecked; AD-26 (`ARCHITECTURE-SPINE.md:243`) says the apply fails if the document changed; a `Visibility`-only call with `confirm` is logged `auto_approve`, not `preview_token` (verification-gap other, edge-case) -- medium, intent_gap: two readings; human chose D4 (check a sent token in every posture); fix is one branch, so code was patched, not reverted.
- Pass 1: G3 replay docstring (`score_g3_replay.py:10-11`) says each step is confirmed, but under the default its tokens are not checked (verification-gap other) -- low, resolved by D4: the tokens it sends are checked again.
- Pass 1: UAT documents still require "unset fails closed": `tests/uat/test-plan.md:253`, `coverage-matrix.md:185`, `TC-08:629,659-687` (TC-08-17/18, Critical), `TC-11:356-375`; `TC-03:23-24`, `TC-04:27` need a SECURITY line the GUI never writes (blind, verification-gap other) -- medium, patch.
- Pass 1: `security-and-service-design.md:80,90,98,108` rests the copilot threat model on operator confirmation, false under the default (blind) -- medium, patch.
- Pass 1: SECURITY line `mcp_server.py:166-167` says "by operator flag" on a default start with no flag set (blind, edge-case, verification-gap other) -- low, patch: name the variable and the default.
- Pass 1: GUI host writes no posture line at start; `addon.log` evidence shows none; Design Notes claim a start-up line (blind) -- medium, patch: one `bootstrap.start_bridge` log line.
- Pass 1: no test starts each host entry with the variable unset (blind) -- low, rejected: all three entries call `Capabilities.from_env(dict(os.environ))`; GUI UAT run A and `h1-security-line.txt` show the default live; a per-host start test adds harness code.
- Pass 1: `uat.py` never asserts the object is hidden; its proof line is cut before `Visibility` (blind) -- low, rejected: `b-01-hidden.png` checked visually; one-off evidence script.
- Pass 1: run folder `2026-10-07-01` has no `report.md` with the visual verdict (blind) -- low, patch.
- Pass 1: run A skips a `Visibility` write and a preview under the posture; run B counts 5 approval lines (blind) -- low, rejected: `test_a_visibility_only_write_is_display_state_under_the_posture_too` covers it in FreeCAD; fixed count is one run's evidence.
- Pass 1: harness standard cites `tests/uat/run/2026-10-07-01/evidence/launch_env.sh`; script takes every FreeCAD pid (blind, edge-case) -- medium, patch: move to `_automation/uat/`, first pid only. Stale `:8765` listener and missing `addon.log` (edge-case) -- low, rejected: preflight already shuts every FreeCAD down.
- Pass 1: shared `_CONFIRM_SCHEMA` description publishes the `feature_set_parameters` exception on every mutation tool (blind) -- low, patch: drop the clause.
- Pass 1: `_CONFIRM_SCHEMA` says "only when ... =0" while any value other than `1` turns the gate on (verification-gap other) -- low, patch.
- Pass 1: `data-contracts-design.md` §6 comment (`:187-190`) disagrees with edited `:203` (blind) -- low, rejected: D2 keeps that drift for `deferred-work.md`, entry present.
- Pass 1: `epics.md` AC3 omits the both-postures rule and the mode (blind) -- false: AC3 text stays true of the shipped behaviour; nothing in it is contradicted.
- Pass 1: AC2 test compares outcomes only and never reads the approval line or that the rollback was proven (blind) -- low, patch: two assertions.
- Pass 1: `OneCallPerMutationTest` uses `ApprovalAuditTest._RecordingSink` (blind) -- low, rejected: no harm named.
- Pass 1: `epic-11-context.md` hunk rewrites 11.1/11.2/11.4 text (blind) -- false: step 1 of this run recompiled the stale context file. Recompile dropped the normative cyclic-Jacobi and no-solids `MatrixOfInertia` rules that `verification-design.md` still states (edge-case) -- low, patch: re-add.
- Pass 1: default change is breaking, no upgrade note (blind) -- medium, rejected as a code finding: the commit carries `feat!` and a `BREAKING CHANGE:` footer.
- Pass 1: README does not say where the audit log lands on a Start-menu launch (blind) -- low, patch: tell the operator to set `FREECAD_BUDDY_AUDIT_LOG`. `CLAUDE.md` names README as the branching-rules source (blind) -- low, defer: agent-context file.
- Pass 1: written audit line never checked for `source` or `display_state`; `_RecordingSink` bypasses `AuditSink` (verification-gap) -- medium, patch.
- Pass 1: README posture check reads the first approval line, which can be `display_state` (edge-case) -- low, patch.
- Pass 1: README and harness say `setx FREECAD_BUDDY_AUTO_APPROVE ""` turns auto-approve off; an empty value usually reaches a new process as unset, so it stays on (edge-case) -- medium, patch: remove the claim, use `0`.
- Pass 1: `OneCallPerMutationTest.setUp` leaks the posture if its pad fails (edge-case) -- low, rejected: needs a broken fixture first.
- Pass 1: `uat.py` KeyError on a missing `structured_content` (edge-case) -- low, rejected: one-off evidence script.
- Pass 1: harness `set` statements with a space before `&&` keep the space in `cmd` (edge-case) -- low, patch: one sentence.

## Design Notes

A sketch that is not fully constrained fails post-verify step 3 (`transaction.py:236-241`) for any write to it, so hiding such a sketch rolls back with `SPEC_FAILED`. This is the existing bracket behaviour with a token too; display state does not weaken the bracket.

`source` is always the variable name, also when the posture comes from the default: the record names the switch that controls it, and the host log line at start-up shows the posture.

## Verification

**Commands:**
- `"C:/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" tests/run_tests.py` -- expected: all infc tests pass.
- `uv run pytest tests/external` -- expected: green.
- `uv run python scripts/gen_schemas.py --check` -- expected: no drift.
- `uv run python scripts/check_imports.py` -- expected: ring rules hold.
- `uv run ruff check .` -- expected: clean.

**Manual checks:**
- GUI UAT evidence: audit lines, and FreeCAD screenshots of the pad and of the hidden object.
