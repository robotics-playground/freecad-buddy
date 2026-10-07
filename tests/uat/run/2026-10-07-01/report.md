# UAT Run 2026-10-07-01 — Story 11.3 one call per mutation

Status: COMPLETE. 11 of 11 scenarios PASS.

## Build banner

| Field | Value |
| --- | --- |
| FreeCAD GUI | 1.1.4 (window title `FreeCAD 1.1.4`) |
| Addon install | Junction `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy` → `src\freecad_buddy` |
| Code under test | `bf1ce5f` plus the uncommitted Story 11.3 diff. Runs A and B ran before the review fixes (D4, GUI start-up line); run C ran after them. |
| Audit log | `FREECAD_BUDDY_AUDIT_LOG` per launch: `evidence/a-audit.jsonl`, `b-audit.jsonl`, `c-audit.jsonl` |
| Harness | `cua-driver` daemon; MCP over HTTP from the uv env (`evidence/uat.py`, `_automation/uat/fcb.py`) |

## Launch

`cua-driver launch_app` takes no environment. For each launch `cua-driver` started `cmd.exe`, which set the variables and started FreeCAD. The helper was first written as `evidence/launch_env.sh`, then moved to `_automation/uat/launch_env.sh`, which the GUI harness standard cites. It is no longer in `evidence/`.

- Run A: `FREECAD_BUDDY_AUTO_APPROVE` unset (`a-launch.txt`).
- Run B: `=0` (`b-launch.txt`).
- Run C: unset (`c-launch.txt`).

`a0-pad-default-cwd.png` is from a first launch without `FREECAD_BUDDY_AUDIT_LOG`. The pad applied, but the audit file went to a working directory the run could not find, so run A was repeated with the variable set.

## Results

| Scenario | Verdict | Evidence | Note |
| --- | --- | --- | --- |
| A1 body, sketch, geometry, `feature_pad` without `confirm` | PASS | `a-uat.txt` | All OK; pad post-verify passed, not rolled back, volume 1000 mm³ |
| A2 approval lines | PASS | `a-uat.txt`, `a-audit.jsonl` | `mode: auto_approve`, `source: FREECAD_BUDDY_AUTO_APPROVE` on all four mutations |
| A3 visual | PASS | `a-01-pad.png` | Agent verdict: document `uat_11_3_a` with `Body` in the tree; a 20 × 10 × 5 plate fills the iso view; no dialog |
| B1 setup through `preview_dry_run` | PASS | `b-uat.txt` | four approvals, `mode: preview_token` |
| B2 `feature_pad` without `confirm` | PASS | `b-uat.txt` | `INVALID_INPUT` "this mutation requires a confirm; …" |
| B3 `{Visibility: false, Length: 7 mm}` without `confirm` | PASS | `b-uat.txt` | `INVALID_INPUT`; no approval line (5 lines total) |
| B4 `{Visibility: false}` without `confirm` | PASS | `b-uat.txt`, `b-audit.jsonl` | OK, `changed: []`, not rolled back; `mode: display_state`, no `source` |
| B5 visual | PASS | `b-01-hidden.png` | Agent verdict: the plate solid is hidden; only the 20 × 10 profile sketch outline remains; `Body` still in the tree; no dialog |
| C1 GUI start-up line | PASS | `c-launch.txt` | `addon.log`: `SECURITY: mutation auto-approve ENABLED (FREECAD_BUDDY_AUTO_APPROVE unset or 1; set it to 0 to require preview_id)` |
| C2 forged token under auto-approve (D4) | PASS | `c-d4-forged-token.txt`, `c-audit.jsonl` | forged `preview_id` → `INVALID_INPUT` "invalid signature"; same call without `confirm` → OK, one `auto_approve` line |
| H1 headless start-up line | PASS | `h1-security-line.txt` | unset: SECURITY line on stderr; `=0`: none. Captured before the text change, so it shows the old wording "ENABLED by operator flag" |

## Findings

- Before the review fixes, the GUI addon and the MCP proxy wrote no start-up line for the posture. The addon now writes it to `addon.log` (C1).
- A `cua-driver` launch without `FREECAD_BUDDY_AUDIT_LOG` writes the audit log to an unknown working directory.

Teardown after each run: documents closed, File > Exit, 0 FreeCAD processes, no `:8765` listener.
