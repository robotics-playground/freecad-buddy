---
title: 'Result text without duplicated long strings'
type: 'feature'
created: '2026-11-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `summary_text` (`src/freecad_buddy/contracts/envelope.py:66-81`) prints a long or multi-line `str` in full in `text`. `script_exec` `value_repr` and `stdout` then appear twice: in `structured_content` and in `text`. `text` was 26% of result characters (SPEC CAP-8).

**Approach:** Per `tool-contracts.md` T-13: a `str` longer than 80 characters, or holding a newline, renders `key: <N chars>`. Other values stay as today. Bespoke summaries are not touched.

</frozen-after-approval>

## Implementation Notes

Files: `src/freecad_buddy/contracts/envelope.py`, `tests/external/test_envelope_summary.py`.
Quality bar: `_bmad-output/implementation-artifacts/quality-bar-13-1.md`.

## Review Triage Log

Lenses: Blind Hunter (opus, high), Edge Cases Hunter (opus, high), Verification Gap Finder (sonnet, medium); round 1. Subagent ids: abe375c3f095947aa, a095ca7c121083085, ae4dec70edfb954c5.

- A bare carriage return (backslash-r) not treated as a line break (Blind, Edge): medium, patched; guard and test added.
- Comment claimed a measured 80 limit and "paths readable" (Blind, Edge, Gap): low, patched; comment now cites T-13 and says long paths are elided.
- Docstring repeated the value 80 (Blind): low, patched.
- script_exec test used an invented key set (Blind): low, patched; real keys now.
- No rounding-path test with a long string (Blind, Gap): medium, patched; `test_mcp_surface.py` test added.
- Tuple, set, bytes top-level values (Edge): false; `structured_content` is JSON, only str, int, float, bool, None, dict, list are reachable.
- Short `value_repr` such as `42` stays inline (Edge claim): false; T-13 sets the limit at 80 on purpose.
- Marker `<N chars>` collides with a real string (Blind): low, rejected; fix would change the T-13 format.
- Plain-text tool loses long strings (Blind): false for now; the only such tool has its own summary.
- Design documents omit the new rule (Blind): deferred to the leader; design edits need approval.
- Addon and proxy run different `summary_text` copies (Blind, Edge): low, rejected; the verifier rebuilds `dist/addon/` and the image before UAT.
- Handler-level `script_exec` test (Gap): rejected here; needs FreeCAD; the verifier checks one live result (Q4).
- Q8 depends on `document_save` and `export_stl` bespoke summaries (Blind): noted; Story 13-20 measures.
