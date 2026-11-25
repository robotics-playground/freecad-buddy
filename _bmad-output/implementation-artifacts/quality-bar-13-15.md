# Story 13-15: quality bar

Base: 538db0be (story/13-15-tnp-expected-reattachment after merging feat @ 3df33fbd). Plan: builder-13-15 plan message 2026-11-25; spec `spec-13-15-tnp-expected-reattachment.md` (approved, decision 40).

| Q | Criterion | Source | Checked by |
| --- | --- | --- | --- |
| Q1 | A datum attached to a Pad face does not grade REPOINTED when Pad.Length changes and the face moves with the Pad; audit not FLAGGED | spec AC1; decision 40 (1) | new infc test "Datum follows Pad" |
| Q2 | Same for a sketch-width change under the support | spec matrix; decision 40 | new infc test "Datum follows sketch width" |
| Q3 | Rule applies to every sub-element link (AttachmentSupport, external geometry, `Fillet.Base`, `Pad.Profile`) through one mechanism, no property-name list | decision 40 (1) | `Fillet.Base` test (Edge4 passes, Edge1/Edge2 renumbered stay BROKEN/flagged); code read |
| Q4 | An element that moves farther than its whole support still grades REPOINTED (distance bound kept) | decision 40 (2) | existing `tnp_guard` :303 test unchanged; mutant: drop bound -> red |
| Q5 | Planted witness tamper with unchanged support still REPOINTED; the three existing planted-witness tests run unchanged | spec AC2; T-8 | existing tests :216 family, :303, :574 |
| Q6 | Mapped name changed, missing history, different history source, or NaN/unreadable witness -> never excused | verification-design.md §3.2 Layer 1; AD-5 safe side | new infc tests; mutant: drop history-equality -> red |
| Q7 | Witness capture cost: one BoundBox read per target per walk | lessons L2 | code read; infc timing unchanged |
| Q8 | G2 fault-injection TNP ops grade as before | benchmarks/g2 planted_ops | gate tests / G2 runner cases |
| Q9 | verification-design.md §3.2 Layer 1 text and RefRecord block match the code | spec tasks; AD-n binding of verification-design | doc diff read |
| Q10 | All gates pass with counts (ruff, check_imports, check_status_vocab, gen_schemas --check, check_skill_shape, pytest external, infc) | epic-13-status.md Environment | verifier |
| Q11 | Live container: datum on a Pad face survives a Pad.Length edit through `feature_set_parameters` with no REPOINTED/FLAGGED in the reply and the audit | SPEC CAP (TNP false positive) | container UAT case |

Levels marked RUN: Unit, Integration (freecadcmd), E2E (MCP over HTTP to container), UAT (container).
