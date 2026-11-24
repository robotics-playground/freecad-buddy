# Story 13-2: quality bar

Base: bd122f2. Head: a913b51 on `story/13-2-script-exec-role-docs` (worktree `D:\Work\Personal\Sources\freecad-buddy-wt-13-2`). Spec: `_bmad-output/implementation-artifacts/spec-13-2-script-exec-role-docs.md` (in that worktree), approved by the user 2026-11-24.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | AD-4, AD-5, `mcp-tools-design.md` §1.4/§5 rules 4 and 7, `data-contracts-design.md`, `spec-freecad-buddy/SPEC.md:120` state one role: typed tools first, `script_exec` for listed gaps, one observe-only bracket | CAP-7, tool-contracts.md T-11 | cross-read |
| Q2 | The bracket text matches T-6 plus decisions 4 (`recompute: false`), 5 (own-transaction limit), 9 (`fingerprint_before`): fingerprint before, bridge transaction opened first, run, recompute unless false, commit, fingerprint after, `changed`, `new_errors`; no post-verify, TNP audit or rollback | tool-contracts.md T-6; epic-13-decisions.md | cross-read |
| Q3 | Statuses: OK; RECOMPUTE_ERROR for new errors; INVALID_INPUT + `detail.code` `exec.python_error` (with exception and traceback) when the script raised, changes kept; TIMEOUT per AD-27. No new status (AD-17) | T-6, AD-17 | `check_status_vocab.py`; read |
| Q4 | Zero matches of the raw-exec pattern over the nine named files (baseline 10) | spec AC 1 | grep |
| Q5 | `debug_` removed from both wire-prefix lists; no dangling reference to a `debug_` group anywhere in spine or design | decision 14 (O-1) | grep |
| Q6 | AD-5 TIMEOUT text says only that it follows AD-27; no new commit/abort rule | decision 15 (O-2) | read |
| Q7 | `security-and-service-design.md` §1 audit sample matches the record the code writes (`adapters/audit_log.py`) | deferred-work.md:1714 | compare sample keys with code |
| Q8 | `mcp-tools-design.md:60` states the `<N chars>` rule as the code implements it (`contracts/envelope.py` at 905e038) | decision 16 | compare with code |
| Q9 | No history narration, no "implemented" claim; dates and front matter per file convention | CLAUDE.md section 3 | read |
| Q10 | No text contradicts other spine ADs (AD-6 diff, AD-27 timeout, AD-28 additive schema) or the remaining design docs (search all of `design/` and the spine for script_exec wording not edited) | CAP-7 | grep `script_exec` over spine + design |

Levels marked RUN: Unit-equivalent document checks (`check_status_vocab.py`, `check_skill_shape.py`, greps). Integration/E2E/UAT: BLOCKED — documents only; Story 13-13 implements the bracket.
