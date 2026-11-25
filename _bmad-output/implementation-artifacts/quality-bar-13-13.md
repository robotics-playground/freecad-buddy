# Story 13-13: quality bar

Base: 7549c1d4 (story/13-13-script-exec-bracket after merging feat @ 3df33fbd). Plan: builder-13-13 plan message 2026-11-25; spec `spec-13-13-script-exec-bracket.md` (approved, decisions 42, 43).

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | A script that writes one property: `OK`, `changed` names the object, `undo_steps` 1; one `document_undo` with `expect_fingerprint` = `fingerprint_before` gives `matches_pre_op` true | spec AC1; T-6; AD-5 | infc bracket test (cases 1, 19); container UAT |
| Q2 | A read-only script leaves `App.getActiveTransaction()` None and `undo_steps` 0 | spec AC2; decision 38 | infc (cases 2-6, 8) |
| Q3 | `SystemExit` / any `BaseException` in the script -> `INVALID_INPUT` `exec.python_error` with exception + traceback (cut), and the next call is served | spec AC3; T-6 | external listener test (real use case) + infc |
| Q4 | A script that breaks a pad -> `RECOMPUTE_ERROR` with `new_errors`, change kept (not aborted) | spec AC4; AD-27 wording (decision 43) | infc case 15 |
| Q5 | 30 objects x 406 faces: call under 30 s | spec AC5; L2 | infc timing test |
| Q6 | Bracket-phase failure statuses: fingerprint_before fails -> `SPEC_FAILED` `exec.bracket_failed`, script not run; recompute/commit/fingerprint_after fails -> `RECOMPUTE_ERROR` `exec.bracket_failed` with `data.phase`; closed document -> `OK` with null `fingerprint_after` | spec cases 10-12; decision 42 | infc with faked failures |
| Q7 | A pending change in another document (case 8) is kept, not aborted, by the close step | spec case 8; deviation (a) accepted by leader | infc case 8 |
| Q8 | `recompute: false` input honoured; `recompute` in `input_schema`; schemas regenerated | decision 4; T-6 | external schema test; `gen_schemas --check` |
| Q9 | Framing read after `script_exec` is fresh, not the cached verdict | spec case 20; decision 42 | infc `test_framing` |
| Q10 | TIMEOUT: the late return commits; nothing aborts it (AD-27 text and code agree) | decision 43; spec case 17 | infc Marshal timeout test; spine diff |
| Q11 | Audit `after` line for `exec` carries `fingerprint_before` and `fingerprint_after` | spec code map; security-and-service-design §1 | external audit/listener test |
| Q12 | Skill and design text no longer say `script_exec` "runs raw"; AD-5 other-document sentence corrected; `undo_steps`, `exec.bracket_failed` documented | decision 43; L11 | `grep -rn "raw" skills/ design/`; `check_skill_shape` |
| Q13 | No contract version bump; existing version tests unchanged | spec case 21; AD-28 | external version tests |
| Q14 | All gates pass with counts | epic-13-status.md Environment | verifier |
| Q15 | Live container: write script, then `document_undo` restores; failing script returns `INVALID_INPUT` and bridge stays up; GUI undo stack shows one named entry | spec UAT fixtures | container UAT |

Levels marked RUN: Unit, Integration (freecadcmd), E2E (MCP over HTTP to container), UAT (container).
