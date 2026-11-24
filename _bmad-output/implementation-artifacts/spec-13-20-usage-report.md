---
title: 'Story 13-20 Usage report and bridge hygiene'
type: 'feature'
created: '2026-11-24'
status: 'done'
route: 'dispatch'
baseline_commit: 'b8fd4e0c822f90dc4a5e0ad7ecbb9e0ff68b3924'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/tool-contracts.md'
  - '{project-root}/_bmad-output/specs/spec-mcp-usage-improvement/usage-evidence.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** No repeatable measure of `script_exec` use exists. The stale-handle message does not name the fix. Orphan `rpc-<pid>.json` files pile up (about 90).

**Approach:** Dev tool `scripts/automation/usage_report.py` prints the `usage-evidence.md` tables for a date range. One constant gives the stale-handle message. The RPC listener removes dead-pid discovery files at start. Plan approved by leader 2026-11-24.

## Boundaries & Constraints

**Always:** Date rule: UTC date of the `tool_use` record timestamp, inclusive. Dedup by `tool_use.id`. Count subagent transcripts. Read spill files. Delete a discovery file only when its JSON pid is an int and `pid_alive` is False. Fixtures hold no user content. Print the call counts on the two boundary days under UTC+7.

**Never:** Ship the report in the addon. Import it from `src/`. Tune the report to match the evidence. Delete a file on doubt (own pid, live pid, corrupt JSON, non-int pid).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Repeated tool_use id | Resumed session repeats lines | Counted once | N/A |
| Out-of-range record | Timestamp outside range | Not counted | N/A |
| Spilled result | Stub names a file | Status and text read from file | Missing file: no status |
| Unknown handle | Any `doc` handle | INVALID_INPUT with the T-12 text | N/A |
| Dead pid file | `rpc-<dead>.json` | Deleted at bind | OSError ignored |
| Live, own, corrupt, non-int pid file | present | Kept | N/A |

</frozen-after-approval>

## Code Map

- `scripts/automation/usage_report.py` -- new; reuses `session_metrics._text`/`_spill`, `replay_result_sizes._SPILL`.
- `src/freecad_buddy/usecases/documents.py:390,405` -- stale-handle message, one constant.
- `src/freecad_buddy/adapters/rpc_listener.py:233-258` -- `_write_discovery`; add the sweep before the own file is written.
- `src/freecad_buddy/usecases/process.py:12` -- `pid_alive`, reused.
- `tests/uat/testcases/TC-02-...md:628,664`, `TC-09-...md:504` -- exact-message cases.
- `scripts/build_addon.py:73` -- copies only `src/freecad_buddy`; the report stays out of the addon.

## Tasks & Acceptance

**Execution:**
- [ ] `scripts/automation/usage_report.py`, `tests/external/test_usage_report.py` -- report and tests
- [ ] `documents.py`, `tests/infc/test_document_lifecycle.py`, UAT TC-02/TC-09 -- message
- [ ] `rpc_listener.py`, `tests/external/test_rpc_listener.py`, `deferred-work.md` -- sweep

**Acceptance Criteria:**
- Given the evidence folders and 2026-10-18..2026-11-18, when the report runs, then totals match `usage-evidence.md` or each difference is listed with its cause.

## Implementation Notes

## Spec Change Log

## Review Triage Log

| Lens | Finding | Verdict | Route | Evidence |
|------|---------|---------|-------|----------|
| blind | own-pid test cannot fail | medium | patch | test now calls `_sweep_orphan_discovery` directly |
| blind, edge | result in a later file loses its outcome | medium | patch | `pending` now shared across files |
| blind, edge | partial last line aborts the report | medium | patch | line skipped on `JSONDecodeError` |
| blind, edge | wrong folder or since after until gives an empty report | medium | patch | `FileNotFoundError` and `parser.error` |
| blind | zero-call list uses the installed catalog | low | patch | line names the catalog |
| blind | `cannot write` class matches any tool | medium | patch | class needs `feature_set_parameters` |
| blind | no row for unclassified failures | medium | patch | row added |
| blind | missing spill file shows as no status | low | rejected | already visible as no status; a fix adds a counter |
| blind, edge | spill path with a space | low | defer | pre-existing pattern in `session_metrics` and `replay_result_sizes` |
| blind, gap | tests missing: persisted format, three classes, bad line, cross-file | medium | patch | tests added |
| blind | blob test passes for the wrong reason | medium | patch | blob given a timestamp; reader skips by type |
| blind | `query_tree_summary` counts 0 text chars; row order | low | rejected | the evidence totals include it; order is a display choice |
| blind | default offset 7 | low | rejected | leader asked for UTC+7 |
| blind | sweep writes no log line | low | rejected | adds code with no named harm |
| blind | design docs describe old lifecycle | medium | patch | both docs edited |
| blind | other stubs copy the old message; constant placement | low | rejected | fakes are test doubles; placement is cosmetic |
| edge | huge pid raises OverflowError in bind | medium | patch | sweep keeps the file; test added |
| edge | sweep races `rpc_client` stat | low | defer | tiny window; pre-existing fragility in `rpc_client` |
| edge | spilled tree summary status | medium | patch | body read from the spill file |
| edge, gap | tool loading ignores the date range and repeats | medium | patch | batches filtered and deduplicated |
| edge | newline or backtick breaks the table | low | patch | message normalised |
| gap | `_lookup` path of the message untested | medium | patch | two infc tests assert the full text |

## Verification

**Commands:**
- `uv run ruff check .`, `uv run python scripts/check_imports.py`, `uv run pytest tests/external -q`

Round 2 (triage-13-20-r2.md RT-1..RT-6, G-1; lenses blind `a744a79b3af10f7c5`, edge `ac14355a21fd06f64`, gap `a7bb6b77aec3aaddf`):

| Lens | Finding | Verdict | Route | Evidence |
|------|---------|---------|-------|----------|
| red team | loft class misses PartDesign types | medium | patch | regex covers Additive/Subtractive Loft, Pipe, Helix, Thickness, Part::Sweep; 2 on the evidence range |
| red team | timeout class counts every tool | medium | patch | `FailureClass` gates on tool and status |
| red team | other servers dropped | medium | patch | any server containing `freecad-buddy`; totals list servers |
| red team | nested JSON stops bridge start | medium | patch | per-file `except Exception`, one log line |
| red team | mutation after `;` read-only | low | patch | `ast` assignment scan with a statement fallback |
| red team | result in an earlier-sorting file lost | low | patch | orphan results replayed for calls and ToolSearch |
| verifier | date filter test checks count only | low | patch | asserts which tools count |
| edge, blind | `==`, chain, annotation, f-string `=`, string `;` and `#` misread | medium | patch | `ast` scan; parametrized cases |
| edge | FIFO or large discovery file blocks read | low | patch | regular file under 64 KiB only |
| gap | ToolSearch orphan, loft shapes, operators, glob OSError untested | low | patch | tests added |
| blind | missing mutators (setDatum, ...) | low | rejected | `usage-evidence.md` fixes the keyword set; changing it breaks comparison |
| blind | typed timeout now unclassified | low | rejected | intended: counted in its tool row |
| blind | unpaired results uncounted, orphan memory | low | rejected | 0 such results on real data |
| blind | sibling scripts use the narrow prefix | low | rejected | outside this story |
| blind | positional `FailureClass` args | low | patch | keywords |
