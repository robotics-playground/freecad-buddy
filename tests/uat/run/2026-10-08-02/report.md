# UAT run 2026-10-08-02: Epic 11 smoke test

FreeCAD 1.1.4 GUI. freecad-buddy on `ba1ead6`, junction install (`Mod/FreeCADBuddy/freecad_buddy` → `src/freecad_buddy`). Driven with `cua-driver`; tool calls over the live MCP HTTP bridge with `evidence/tc16_calls.py`, which records the raw content blocks and their char counts. Headless legs under the `fcb` env (`evidence/h1_posture.py`). The drawer is a copy of `kiwibox-drawer-rebuild.FCStd` (178 objects); the original was not opened, and the copies are deleted after the run.

Scope: new `TC-16` (Epic 11 claims) plus the existing scenarios that cover Epic 11 changes: TC-05-01, -02, -05, -06, -13, TC-08-18, TC-11-08. Per-phase detail: `evidence/tc16-A-results.md`, `evidence/phaseB-results.md`, `evidence/phaseB2-results.md`.

## Launches

| Phase | Posture | Scenarios |
|---|---|---|
| A | auto-approve on (unset); audit `evidence/audit.jsonl` | TC-16-01, -02, -03, -04, -06 |
| B | `FREECAD_BUDDY_AUTO_APPROVE=0`; audit `evidence/audit-B.jsonl` | TC-16-07, TC-05-01, -02, -05, -06, -13 |
| B2 | H1 headless, 4 flag values; GUI of phase B for the visual | TC-08-18, TC-11-08 |
| C | GUI macro `time_mutation_overhead.py`, 2 launches | TC-16-05 |

## Verdicts

| Scenario | Verdict | Measured |
|---|---|---|
| TC-16-01 rotation listed in `changed` | PASS | tilt 30° → 120°: `changed` = `Body`, `Pad` (volume 3000.0, com [0,0,5]), `Sketch`; volume, area, com unchanged; digests differ. Window: bar turned a quarter turn, same size and centre |
| TC-16-02 compact result | PASS | `feature_pad` result 1 block, 1,402 chars, compact JSON; `fcb.mutation/2`; no `transaction_id`, `verify_verdict`, `params_digest`, `snapshot_path`; preview `diff.op` = `{"tool":"feature_pad"}` |
| TC-16-03 one call, audited | PASS | `feature_pad` without `confirm` `OK` in 0.16 s; approval `mode: auto_approve`, `source: FREECAD_BUDDY_AUTO_APPROVE`; approval and mutation `fingerprint_before` equal |
| TC-16-04 drawer rollback by proof | **FAIL** | `duct_pilot.Length` 0 mm: `RECOMPUTE_ERROR`, `rolled_back_via_snapshot`, 38.4 s. `changed` = `[]`, Length still 6 mm, window unchanged |
| TC-16-05 bridge overhead ≤ 10 s GUI | timing PASS, abort **FAIL**, visual NOT RUN | median overhead 9.38 s and 9.30 s; abort check `rolled_back_via_snapshot`, `closeDocument` called, 32.5 s and 32.9 s |
| TC-16-06 drawer tree in one result | PASS | 2 blocks, 296 + 650 = 946 chars (run 2026-10-07-03: 11,612); Model panel children equal |
| TC-16-07 visibility-only edit under gate | PASS | `Visibility` only: `OK`, audit `mode: display_state`; with `Length`: `INVALID_INPUT` "requires a confirm"; volume 12000.0; window: prism hidden |
| TC-05-01 full bracket | PASS | 1,401 chars, `fcb.mutation/2` |
| TC-05-02 snapshot lifecycle | PARTIAL | snapshot folder seen and removed on commit; its content not readable from outside FreeCAD (owner-only folder, about 108 ms) |
| TC-05-05 proven rollback | PASS | 500 mm fillet: `rolled_back_verified`, `changed` = `[]`, 0.12 s; window unchanged |
| TC-05-06 snapshot escalation | **FAIL** | escalation not reached (CONDITIONAL). Reproducer 1 (900 mm pocket) committed an empty solid; see `bugs.md` B2 |
| TC-05-13 fingerprint tag, determinism | PASS | equal digests on two copies; `exportBinary` on both sides |
| TC-08-18 headless posture | PASS | unset and `=1` approve; `=0` and `=true` refuse with the exact string; 1 approval line; window bytes identical |
| TC-11-08 auto-approve audit | PASS | warning on unset only; 1 approval line; `params_digest` equal on approval, before, after lines |

Totals: 14 scenarios. 10 PASS, 1 PARTIAL, 3 FAIL (TC-16-04, TC-16-05 abort line, TC-05-06).

## Epic 11 targets

| Claim (story) | Result |
|---|---|
| 11.1 mass properties see a rotation about the centre of mass | PASS (TC-16-01) |
| 11.2 result ≤ 10K chars, compact, digests not records | PASS. Largest result in this run 2,786 chars (an `INVALID_INPUT` refusal, most of it the traceback, `bugs.md` B4); largest OK result 2,304 chars (a preview); mutation results 1,274 to 1,891 |
| 11.3 one call per mutation by default; `=0` gate; display-state carve-out | PASS (TC-16-03, TC-16-07, TC-08-18, TC-11-08) |
| 11.4 overhead ≤ 10 s GUI | PASS (9.38 s, 9.30 s) |
| 11.4 failed mutation on the drawer proves its rollback, no reopen | **FAIL** in the GUI, 3 of 3 (TC-16-04 over MCP, TC-16-05 × 2 in the macro) |
| 11.5 skills shape, no stale tool names | PASS (`check_skill_shape.py` exit 0; `grep verify_references\|verify_fingerprint skills` no match) |
| 11.6 AC2 largest result (FAIL in run 2026-10-07-03) | The failing call now returns 946 chars. A new full build session was not measured |

## Automated checks (same tree)

- `uv run pytest tests/external`: 1,330 passed.
- `ruff check .`, `gen_schemas.py --check`, `check_imports.py`, `check_skill_shape.py`: clean (`evidence/static-checks.txt`).

## Test-case changes made for this run

- New `testcases/TC-16-lean-agent-loop.md`; index row in `test-plan.md`.
- TC-05: 8 lines still asserted `fcb.mutation/1` (`transaction_id`, null `snapshot_path`, per-object `objects`, digest equality after rollback). Updated to the Story 11.2 and 11.4 wire before the run.
- TC-16 after phase A: Top view order (an MCP fit leaves an isometric camera; FreeCAD 1.1.4 has no Top toolbar button), audit key `fingerprint_before`, and the reopen check (a `document_list` name check cannot see a reopen).

Test-case defects found and not yet fixed are listed in `bugs.md` (T1 to T9).

## Not verified

- A new full agent build session (Story 11.6 AC2 end to end).
- The content of a snapshot folder during the bracket (TC-05-02).
- The visual after the timing macro: the macro blocks the GUI while it runs and exits FreeCAD when its abort check fails.
