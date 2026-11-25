# Story 13-7 triage: red team

Base: 8e381d9 on `story/13-7-query-interference`. Source: `redteam-13-7.md` (this folder). Use its reproductions as failing tests first (red), then fix.

The safety property (Q5, CAP-1) is broken for shapes whose measurement FreeCAD cannot be trusted. The fix rule (leader decision 26): **a pair is measured only when both shapes are valid, closed, correctly oriented solids. Otherwise the pair record has `boolean_failed: true`, `common_volume: null`, and `min_distance` only if `distToShape` is trustworthy for that shape, else null.** Never report volume 0 with `boolean_failed: false` for such a pair.

| Id | Source | Required fix |
| --- | --- | --- |
| RT-1 (high) | red team | Invalid solid (the planted bowtie) with a box inside one lobe reads volume 0, distance 7.07, not failed. Apply decision 26: `isValid()` false on either shape → `boolean_failed` true. Test with the red team's case. |
| RT-2 (high) | red team | `Part::Reverse` (valid but reversed solid): common gives 875 vs true 125; a contained box reads volume 0, distance 40. Detect reversed orientation (negative signed volume per solid, or solid orientation check verified against OCCT/FreeCAD source) → `boolean_failed` true. Remove or justify the earlier `abs()` patch; test with real shapes, not fakes. |
| RT-3 (medium) | red team | A closed mesh shell (no solid) containing a solid reads disjoint at 40 mm. Non-solid shapes (no `Solids`, shells, faces, meshes converted to shells) → `boolean_failed` true. Test. |
| RT-4 (low) | red team | The MCP adapter rounds a volume below 1e-9 to 0.0 in `structuredContent` while the text counts the pair as overlapping. Make the text and the structured value agree (derive the text from the rounded value, or never round a non-zero overlap to 0 — choose the smallest fix in `adapters/` that is consistent with display-precision rules) and test. |
| RT-5 (low) | red team | Design and tool description: the frame note must say every object is measured in its own container frame, incl. a feature inside a moved Body, not only App::Part and App::Link. |

## Not fixed, with the reason

- Touching solids (`boolean_failed` true at distance 0): waits for the user's answer on the fuse cross-check (option b). Do not change now.

## After the fixes

1. Commit on your branch (no trailer).
2. Product change in the core rule: run `bmad-build`'s three lenses again as fresh subagents (round 2) on 8e381d9..HEAD with `quality-bar-13-7.md` (this folder). Patch high/medium; commit.
3. External and infc counts; reply with SHA, lens ids, counts in at most 8 lines. Wait for tests in the foreground.

## Addendum: verifier findings (verify-13-7.md)

| Id | Source | Required fix |
| --- | --- | --- |
| F2 (medium) | verifier, container | Two 900-box compounds: TIMEOUT after 130 s (proxy read timeout), then `WORKER_CRASHED` "handshake rejected" for about 8 minutes while FreeCAD stayed alive; `distToShape` likely holds the GIL so the marshal timeout cannot fire. Add a measured complexity guard before measuring a pair (for example total faces of the two shapes, or solid count of a compound) and refuse above it with `INVALID_INPUT` and a `detail.code` such as `interference.too_complex` naming the pair (AD-17: no new status). Set the threshold from a measurement on the host (largest input that finishes well inside the 60 s budget), document the measurement next to the constant (CLAUDE.md tuned-constant rule), and test both sides. Leader decision 27. |
| F1 (low) | verifier | `Shape.common()` clears a BREP flag on the input shapes, so a fresh fingerprint digest changes after a read-only call. Run the booleans and the distance on copies (`shape.copy()`) so the document's shapes are untouched; test that a fresh fingerprint digest is equal before and after. |
| e1 (low) | verifier | The 21-object bound test uses names that do not exist, so "unknown object" hides the bound. Use 21 existing objects. |
