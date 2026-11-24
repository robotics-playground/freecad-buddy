# Story 13-20: quality bar

Base: b8fd4e0c. Plan: builder-13-20 plan (approved 2026-11-24), `epic-13-plan.md` section 13-20.

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | `usage_report.py --since D --until D <folder>...` prints the `usage-evidence.md` tables: totals, per-tool outcome (incl. typed tools with 0 calls), script classes, failure classes, tool loading, `text` share | tool-contracts.md T-12; CAP-7 | unit tests on redacted synthetic transcripts |
| Q2 | On 2026-10-18..2026-11-18 over the two evidence project folders the report reproduces the `usage-evidence.md` totals (1,221 calls, 10 sessions, 34% `script_exec`, 26% `text` share); every difference is listed with its cause, no tuning to hide it | stories.yaml 20; SPEC Success signal | builder run + verifier independent re-run |
| Q3 | Counts are not inflated or lost: dedup by `tool_use.id`, subagent transcripts counted, spill files read, the date boundary rule stated (UTC timestamp of the tool_use record, inclusive) | builder plan | unit tests |
| Q4 | Stale-handle message is exactly "unknown or stale document handle: <doc>; call document_list for the current handles" at both sites, from one constant; UAT/infc cases that match the old text exactly are updated | T-12 | infc test; grep for the old text |
| Q5 | Bridge start deletes `rpc-<pid>.json` only when the JSON pid is an int and `pid_alive(pid)` is False; keeps own pid, live pid, unreadable JSON, non-int pid | T-12; deferred-work.md:1778 risk | unit tests (dead, live, corrupt, own) |
| Q6 | Report is a dev tool: not in `dist/addon` (build_addon output) and not imported by `src/` | T-12 | check build_addon file list; check_imports |
| Q7 | Test fixtures hold no user content (redacted) | epic-13-plan.md 13-20 risk | read fixtures |
| Q8 | AD-1 rings (`process.py` usage ring-legal) | AD-1 | `check_imports.py` |

Levels marked RUN: Unit, Integration (freecadcmd for the documents change), E2E (report run on real transcripts). UAT: the done checkpoint shows the user the report output.
