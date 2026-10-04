---
title: 'Story 10.1: Documents and Queries'
type: 'bugfix'
created: '2026-10-04'
status: 'done'
route: 'dispatch'
baseline_commit: 'd5b47a9'
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-10-context.md'
  - '{project-root}/tests/uat/run/2026-10-03-04/report.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Document and query tools misreport the document (UAT run `2026-10-03-04`, findings F-01, F-02, F-03, F-12, F-20, F-25, F-30; all reproduced headless on FreeCAD 1.1.3). Tree filters return nothing for nested matches, save accepts bad targets or fails with a catch-all status, undo accepts a malformed fingerprint and states a false "did NOT restore", a handle to a GUI-closed document fails with `RECOMPUTE_ERROR`, and the temp sweep deletes files it does not own, including a live GUI's.

**Approach:** Fix each at its root cause in `usecases/queries.py` and `usecases/documents.py`, each with a regression test, keeping G2.3 gate behaviour unchanged.

**Decisions (2026-10-04, user):**
- **D1 — F-01.** A filtered `query_tree_summary` searches the whole tree regardless of `depth`. A node that fails the filter is dropped, and its matching descendants are returned in its place, deduplicated by `Name`. The search descends only through a node that fails `types`, `name_pattern` or `renderable_only`. A node that fails `visible_only` or `exclude_types` removes its whole subtree, and a failing `App::Link` hoists nothing (its target is not searched).
- **D2 — F-02.** Accept FreeCAD's behaviour: `saveAs` sets the label to the file stem, as GUI Save As does. `document_save` and `document_create` with a path report the resulting `label` in their result. Epic 10 Story 10.1 AC2 is corrected to say this; TC-02-13 is corrected in Story 10.7.
- **D3 — F-20.** `matches_pre_op` stays the byte comparison for the string form (G2.3 unchanged). Only the message changes: it states what was measured and never claims the restore failed.
- **D4 — F-30.** The sweep removes only `FCB_TMP_` entries. Each host gets its own session folder `tmp/FCB_TMP_session_<pid>_<token>/` and sweeps only session folders whose pid is dead (AD-25 session-scoped workdir).

## Boundaries & Constraints

**Always:**
- Input faults return `INVALID_INPUT` with a message naming the bad value (AD-17); no catch-all `RECOMPUTE_ERROR` for them.
- A refused call changes nothing: no undo runs, no file or folder is written.
- Every fix has a regression test that fails on the current code.
- The ring rule holds: `_pid_alive` moves inward (out of `adapters/`) so a use case can call it; `adapters/rpc_client.py` imports it from there.

**Never:**
- No global `OSError` mapping in `rpc_dispatch.py`: the unexpected `export_stl` to `Z:/` path stays `RECOMPUTE_ERROR` (TC-09-21).
- No change to the `matches_pre_op` value for either undo form, or to the G2 collector.
- No change to UAT test-case files (Story 10.7) beyond what a regression test here needs.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Nested filter | Body→Sketch→Pad; `types:["PartDesign::Pad"]`, `name_pattern:"^Pad"`, or `renderable_only` | Pad returned (no Body node); each Name once | — |
| Pruning filters | hidden Body + `visible_only`; `exclude_types:["PartDesign::Body"]`; failing `App::Link` | nothing from the Body subtree; nothing from the link target | — |
| Save-as label | `document_save {path: new.FCStd}` | `OK`; result `label` = file stem | — |
| Save to missing folder | parent folder absent | `INVALID_INPUT` naming the folder; nothing created | — |
| Save to a directory | `path` is an existing directory | `INVALID_INPUT` naming the path; nothing written | — |
| Save read-only | existing read-only file | `INVALID_INPUT` naming the path; document `FileName` unchanged | — |
| Malformed fingerprint | record without matching `serializer`, non-str `digest`, bad entries; or a string that is not 64 hex chars | `INVALID_INPUT`; `UndoCount` and the Pad unchanged | — |
| String-form undo | valid 64-hex digest, undo restores | `matches_pre_op:false`; message says the digest differs on byte comparison and recommends the record form; no "did NOT restore" | — |
| GUI-closed handle | document closed outside the registry | `INVALID_INPUT` "unknown or stale document handle"; all aliases dropped | — |
| Sweep | tmp holds `user_notes.txt`, `not_prefixed/`, a live session's folder, a dead session's folder | only the dead session's folder and stray `FCB_TMP_` entries of dead sessions removed | — |

</frozen-after-approval>

## Code Map

- `usecases/queries.py:352-358` -- `_node_passes` gates the recursion in `build`; separate walking from filtering, hoist passing descendants, dedupe by `Name`. Tests: `tests/infc/test_tree_summary.py` (`:36` `App::Link` depth-1 case must still pass).
- `usecases/documents.py:319` (`saveAs` in `document_save`) and `:263-264` (`document_create` with path) -- add one shared path check before `saveAs`: directory → refuse; missing parent → refuse; existing file without `os.access(W_OK)` → refuse; wrap `saveAs` so `OSError` becomes `ValidationError` naming the path; report the resulting `label`. FreeCAD appends `.FCStd` (`Document.cpp:1677-1696`) — keep that and report the actual path.
- `usecases/documents.py:394-407` -- `expect_fingerprint` validation before the lock: record needs `serializer == shim.serializer_tag()` (reuse the `fingerprints_equal` message), `str` `digest`, entries with `name` and `massprops`; string needs 64 hex chars.
- `usecases/documents.py:126-136` (`summarize_document_undo`) and `:164-176` (`_matches_pre_op`) -- string-form message only (D3).
- `usecases/documents.py:212-222` (`_resolve`) -- probe `document.Name`; on `ReferenceError` drop every alias of that document and raise `ValidationError`. Prune today happens only via `document_list` (`:493` → `_prune_closed` `:511`).
- `usecases/documents.py:37-43` (`workdir_root`), `:59-95` (`sweep_temp_dir`) -- session folder per host, prefix filter, dead-pid sweep. `_pid_alive` (with its Windows `GetExitCodeProcess` check) is at `adapters/rpc_client.py:~58`; move it to a stdlib module under `usecases/`.
- Tests pinning current text: `tests/infc/test_document_undo.py:276-287` (asserts "did NOT restore" for the string form). Must keep: `tests/infc/test_g2_driver.py:166-185`, `tests/external/test_gate_g2_exit.py:432` (string form `False`).
- `_bmad-output/planning-artifacts/epics.md` Epic 10 Story 10.1 AC2 -- correct to D2.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/queries.py` -- D1 filter walk -- F-01.
- [x] `src/freecad_buddy/usecases/documents.py` -- save path check and `OSError` wrap, result `label`, fingerprint validation, string-form message, stale-handle resolve, session folder and sweep -- F-02, F-03, F-12, F-20, F-25, F-30.
- [x] `src/freecad_buddy/usecases/<process module>.py` + `adapters/rpc_client.py` -- move `_pid_alive` inward; rpc_client imports it.
- [x] `tests/infc/test_tree_summary.py`, `tests/infc/test_document_lifecycle.py`, `tests/infc/test_document_undo.py`, `tests/external/test_session_workdir.py` (new or existing) -- one test per I/O row; update the "did NOT restore" assertion.
- [x] `_bmad-output/planning-artifacts/epics.md` -- Story 10.1 AC2 per D2.
- [x] Re-run any validator score whose sources change (check `benchmarks/runner.py` `_VALIDATOR_SOURCES`).

**Acceptance Criteria:**
- Given each I/O row, when its regression test runs on FreeCAD 1.1.3, then it passes, and it fails on HEAD `d5b47a9`.
- Given the full suites, when run, then in-FreeCAD and external tests pass (5 known G1 failures are now fixed: expect 0), ruff, `check_imports`, `gen_schemas --check` and `check_provenance` pass, and CI is green.

## Implementation Notes

## Spec Change Log

- **Review 1 (intent gap, resolved by user).** Trigger: edge-case finding that `matching()` descends through a node failing `visible_only`/`exclude_types` (a hidden Body's Pad reported visible) and through a failing `App::Link` into its target, possibly in another document. Amended: D1 and a "Pruning filters" matrix row. Known-bad state avoided: hidden or excluded containers leaking their contents; cross-document objects shown as children. KEEP: all other code and tests from review 0; only `matching()` changes, so the diff is patched in place, not reverted.

## Review Triage Log

| # | Source | Finding | Verdict | Route / evidence |
|---|--------|---------|---------|------------------|
| 1 | edge | Descent through `visible_only`/`exclude_types` failures and through `App::Link` | medium | intent_gap; resolved by user into D1. `_node_passes` (`queries.py:211`) reads the object's own `Visibility`, so a hidden Body's Pad passes. |
| 2 | blind, edge | Failed `saveAs` leaves `FileName`/`Label` changed | high | patch. `Document.cpp:1704-1710` sets both before `save()`; `_save_as` does not restore them. |
| 3 | edge | `path + ".FCStd"` an existing directory is not refused up front | medium | patch. `_check_save_target` tests `isdir(path)` only. |
| 4 | blind | Plain `document_save` raises raw `OSError` (`RECOMPUTE_ERROR`) | medium | patch. Same F-03 mode on the no-path branch. |
| 5 | blind | Save `text` omits the new label and path | low | patch. D2: result reports the label; `summarize_document_save` ignores it. One-line fix. |
| 6 | blind | Tool descriptions omit the new save/filter/fingerprint rules | low | patch. `tool_catalog.py` text is what agents read. |
| 7 | blind | AD-25 and Story 10.1 AC6 do not describe per-host session folders | low | patch (docs). Also `mcp-tools-design.md` §3.1/§3.2. |
| 8 | gap | No test for a read-only target given without `.FCStd` or with trailing `.` | medium | patch. Reverting `_fcstd_path` fails no test. |
| 9 | gap | Undo `text` not pinned for record mismatch or match | medium | patch. Moving the `digest_only` branch fails no test. |
| 10 | blind | Closed-handle test does not assert `handle` itself removed | low | patch. One assertion. |
| 11 | edge | `rebind` leaves other aliases bound to the dead original, now dropped as stale | medium | patch. `_resolve` probe turns the pre-existing dead alias into a deleted alias. |
| 12 | edge | Overlong pid in a session folder name: `OverflowError` escapes the sweep on POSIX | low | patch. Bound `\d{1,10}` in `_SESSION_DIR`. |
| 13 | edge | `OpenProcess` access-denied reads a live process as dead; sweep then deletes its folder | medium | patch. New destructive consumer of `pid_alive`. |
| 14 | blind | `_live_pid` uses `os.getppid()`, `_dead_pid` a reaped pid | low | patch. Start a sleeping child, stop it at cleanup. |
| 15 | blind, edge | Name repeats across levels at `depth>=2` | false | Dedupe applies to the set that replaces a dropped node. Unfiltered baseline already shows Sketch under Body and under Pad at depth 3 (`OutList` shape). |
| 16 | blind | `children_count` can differ from hoisted `children` length | low | rejected. Counts are direct `OutList` sizes; filtered lists already differed from them. |
| 17 | blind, edge | Recycled pid keeps a dead folder until that process exits | low | rejected. Disk leftover only; fix needs start-time tracking. |
| 18 | blind, edge | Top-level `FCB_TMP_` strays of a live older-build host deleted | low | rejected. Transitional only; matrix row removes strays. |
| 19 | blind | `_check_expectation` relies on `fingerprints_equal` raising | false | Code Map directs reuse of its message. |
| 20 | blind | `digest_only` flag argument on `summarize_document_undo` | low | rejected. Adding a wire field is new public surface. |
| 21 | blind | No test for `CheckExtension=False` | low | rejected. Preference path rarely changed; adds fixture. |
| 22 | blind | `_release` and `_prune_closed` overlap | low | rejected. Different triggers (use vs. listing). |
| 23 | blind | `freecad-buddy-workdir/` not git-ignored | low | defer. Pre-existing cwd-relative default. |
| 24 | blind | Pid-token comment overstates protection | false | Comment states the naming guarantee only, which holds. |
| 25 | edge | `matching()` unbounded walk under the lock | low | rejected. Bounded by document size. |
| 26 | edge | Reserved-name sweep test does not observe `rmtree` deletes | low | rejected. Reserved names are documents, never directory entries. |
| 27 | edge | Read-only test fails under root | false | CI runs as the `runner` user, not root. |
| 28 | edge | Evidence script `tc-01r-11-pidalive.py` calls removed `_pid_alive` | false | Historical record pinned to `bece7ac`; never edited. |
| 29 | edge | Save-as to the current path keeps a custom label | false | Result reports the actual `Label`; AC2 covers a new path. |
| 30 | gap | TC-02-13 and TC-15 contradict the new label and temp layout | low | defer to Story 10.7 (spec boundary: no UAT test-case edits here). |
| 31 | gap | `ExpectFingerprintRecordTest` defined after `unittest.main()` | low | rejected. Pre-existing; `run_tests.py` discovery runs it. |

## Verification

**Commands:**
- `freecadcmd tests/run_tests.py` in env `fcb` (FreeCAD 1.1.3) -- expected: OK.
- `uv run pytest tests/external` -- expected: all pass.
- `uv run ruff check .`, `uv run python scripts/check_imports.py`, `uv run python scripts/gen_schemas.py --check`, `uv run python scripts/check_provenance.py` -- expected: pass.
- `uv run python -m benchmarks.runner faults G2` -- expected: validators current.
