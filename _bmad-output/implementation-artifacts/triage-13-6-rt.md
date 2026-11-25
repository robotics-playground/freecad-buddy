# Story 13-6 triage: red team

Base: 61dd01f on `story/13-6-mass-properties-objects`. Source: `redteam-13-6.md` (this folder).

| Id | Source | Required fix |
| --- | --- | --- |
| RT-1 (high by the bar, doc) | red team | `mcp-tools-design.md:131` §2 row: remove "/inertia" — the record has no inertia field. Check the rest of the row and §3.2.2 against the real record keys. |
| RT-2 (low) | red team | Add a test that pins the empty-name check in `_mass_object_names` (a mutant without it must go red). |
| RT-4 (low) | red team | In the `objects` path, an empty shape (null shape or an empty compound with no sub-shapes, which today gives an inverted ±1.797e308 bbox) gives the `{name, shape: null}` record. Test with an empty compound. Leave the single `object` path's behaviour as it is today (AD-28: no change of an existing response) and say so in the spec. |

## Not fixed, with the reason

- RT-3 (low, pre-existing on the `object` path): an object in Invalid state that keeps its last good shape reads `is_valid: true` and the old volume. Reporting object state in the record is a contract addition outside T-2. Leader records it in `deferred-work.md`.

## After the fixes

Commit on your branch (no trailer). Small change: no lens round. Run the infc query tests and `pytest tests/external -q`; reply with SHA and counts in at most 5 lines. The verifier's report may add rows to this round.
