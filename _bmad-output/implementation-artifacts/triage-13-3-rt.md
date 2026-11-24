# Story 13-3 triage: red team

Base: 010a92b on `story/13-3-server-instructions`. Source: `redteam-13-3.md` (same folder). Verifier `verify-13-3.md`: PASS.

| Id | Source | Required fix |
| --- | --- | --- |
| RT-1 (medium, false-pass test) | red team | Add a test that finds every token in `SERVER_INSTRUCTIONS` shaped like a tool name with a family prefix (e.g. regex `\b(document|query|verify|export|sketch|feature|preview|view)_[a-z0-9_]+\b`, excluding the bare family prefixes `document_`, … and `verify_export_`) and asserts each is in `tool_specs()` names or is `script_exec`. Prove it: the red team's mutation (add `feature_loft, query_section` to the text) must fail the new test. Regression risk: none on product; keep the family-line test. |
| RT-2 (low) | red team | Relay instructions cache: write and read the file without newline translation (`newline=""` / binary + utf-8) so an upstream `\r\n` text comes back unchanged. Test from the red team's repro. |
| RT-3 (low) | red team | Relay: decide whether to rewrite the cache file by comparing the upstream text with the file content, not only the in-memory copy. Test from the red team's repro. Do not change the pre-existing tool-cache behaviour in this Story. |
| RT-4 (low) | red team | Relay: a cache path that cannot be replaced must not stall the event loop (~0.9 s per refresh with `time.sleep`) every refresh. Fix the smallest correct way: run the blocking retry off the event loop (`asyncio.to_thread`) or give up after the first failure for this text and update `_instructions` so it does not retry each refresh. Test: the red team's ticker repro stays under 0.2 s. Regression: the tool cache still updates when the instructions write fails. |

## Not fixed, with the reason

- Red team "Not reproduced" items: no reproduction; cache trust level is unchanged from before this Story.

## After the fixes

Commit on your branch (no trailer). Product change is small: no lens round unless the relay change grows past about 60 lines. Run `uv run pytest tests/external -q` and ruff on changed files; reply with SHA and counts in at most 6 lines.
