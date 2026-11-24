# Report: Story 13-1 build

Status: done, uncommitted. Route: oneshot. Spec: `_bmad-output/implementation-artifacts/spec-13-1-result-text-dedup.md`.

## Result
`summary_text` (`src/freecad_buddy/contracts/envelope.py`) renders a `str` longer than `INLINE_STRING_LIMIT` (80), or holding `\n` or `\r`, as `key: <N chars>`. Dict, list and other scalars unchanged. Bespoke summaries untouched.

## Changed files (uncommitted)
- `src/freecad_buddy/contracts/envelope.py`
- `tests/external/test_envelope_summary.py` (2 old tests kept, 8 new)
- `tests/external/test_mcp_surface.py` (1 new test for regeneration after rounding with a long string)
- `_bmad-output/implementation-artifacts/spec-13-1-result-text-dedup.md` (new)
- `_bmad-output/implementation-artifacts/report-13-1-build.md` (this file)
Working-copy files are CRLF; git normalizes to LF (`.gitattributes`).

## Review (round 1)
Subagents could not carry names (teammates cannot spawn named agents), so ids stand in for `review-<lens>-r1-s13-1`:
- Blind Hunter (opus, high): abe375c3f095947aa
- Edge Cases Hunter (opus, high): a095ca7c121083085
- Verification Gap Finder (sonnet, medium): ae4dec70edfb954c5
Patched: `\r` line break guard plus test; constant comment reworded (no unmeasured claim); docstring no longer repeats 80; script_exec test uses the real key set; rounding-path test with long string.
Rejected or false: non-JSON value types, short `value_repr` inline (by T-13), marker collision, plain-text tool, addon/proxy copy skew (verifier rebuilds), handler-level script_exec test (needs FreeCAD; Q4 live check by verifier).
Full triage: spec `## Review Triage Log`.
Round 2 of the lenses was not run on the patches (small, each covered by a test). Run it if the leader wants it.

## Deferred
- Design text (`design/mcp-tools-design.md:60`, `data-contracts-design.md`) does not state the `<N chars>` rule. Blocker: design edits need approval. Unblock: leader decides whether to add one sentence.
- Q8 (text share <=5%) is not reachable by this Story alone: `document_save` and `export_stl` use bespoke summaries (usage-evidence). Story 13-20 measures.

## Tests
- Gates: `ruff check .` pass; `ruff format --check` on 3 changed files pass; `check_imports` OK; `gen_schemas --check` OK; `check_status_vocab` OK.
- `pytest tests/external -q`: 1829 passed, 4 skipped, 0 failed (after patches). The first run (before patches) had 1 failure in `test_mcp_cache_proxy.py::test_should_answer_both_calls_when_two_parallel_calls_meet_a_lost_session`; it passes alone, also with my changes stashed (flaky, pre-existing).
- infc not run: no infc test reads a long string from generated `text`; the infc `text` assertions (`test_document_undo.py`, `test_preview.py`) use bespoke summaries.
- Not touched: `sprint-status.yaml`, epic-13 files, quality-bar, review-ledger. Sprint-status sync skipped (leader owns it).
