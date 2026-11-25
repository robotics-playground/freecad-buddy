# Story 13-15: findings ledger

Quality bar: quality-bar-13-15.md.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| R1-1 | Q4, Q6 | medium (product) | blind ac46ce7983f872c54 / edge a6c640398f275a239 / gap ae06149357a2a30d3 | fixed-proven | bound ignored direction (5 mm X shift beside 5 mm Z support move excused); now per axis; mutant "one maximum" -> 1 red (builder) |
| R1-2 | Q1, Q6 | medium (test gap) | r1 lenses | fixed-proven (r2 found it could not fail on a swap: R2-2) | written-baseline branch untested; 2 tests added (audit with written; feature_set_parameters end to end) |
| R1-4 | Q6 | medium (test gap) | r1 lenses | fixed-proven | history-equality mutant survived; layer assertion + 3 unit cases; mutant now 4 red (builder) |
| RT3-1 | outside the diff (AD-5 written baseline) | medium (pre-existing; base 538db0be also CLEAN) | redteam-13-15c | deferred | w1_inner_recompute.py: an op that recomputes inside the bracket (feature_fillet/chamfer) makes refs_written a post-recompute reading, so a pending edit's re-point grades CLEAN; not via the excuse |
| RT3-L1 | Q4 | low | redteam-13-15c | open (builder: real-geometry count-guard test if one exists) | count guard mutant killed only by the synthetic tampered-count test |
| RT3-L2 | Q7 | low | redteam-13-15c | accepted | all 200 refs moved: audit 0.323 s (base 0.152 s) |
| RT2-1 | Q5, Q6 | high | redteam-13-15b | fixed-proven (6d6bdc60: count guard + instance-index forms; PatternGridTest red first; redteam-13-15c: 96 edit runs, no excused re-point) | p13_grid_index.py: 2-direction LinearPattern grid, L 60 -> 100: OK/CLEAN, datum moves boss (3,7) -> (42,17); base SPEC_FAILED/REPOINTED; MultiTransform p14 same |
| RT2-L1 | Q7 | low | redteam-13-15b | fixed (lineage at grading time; p15 audit 0.241 s, all-moved 0.323 s) | snapshot 0.641 s vs 0.081 s at base (80 features, 200 refs) |
| R5-1 | Q5, Q6 | high | r5 blind ab10f8369b8d24a17 + edge a67d4bffa3a56a461 (both reproduced) | fixed-proven (redteam-13-15b: lineage across 1-4 pass-through features holds) | two pass-through features hash the older name part, `;:M3` disappears from name and history source; datum x 16 -> 33 CLEAN; fix: refuse when any name in `getElementHistory(recursive=True)` carries a counter or the chain is unreadable; cost 0.022 -> 0.034 s |
| R5-2 | Q6 | medium (product) | r5 lenses | fixed | `;:G0#` form not detected |
| R5-3 | Q6 | medium (test) x5 | r5 gap a2efbad7520524d06 | fixed | two-digit indexes, `;:G` sibling half, history-source check, cache key, `;D` lookahead |
| R5-D | outside the bar | low x3 | r5 lenses | deferred (decision 017 residuals) | `;:L#id` lower-element hashing; `(...)` multi-source without hasher; no e2e sibling-refusal test |
| D-1 | Q11 | medium (safe-side false positive, pre-existing) | verifier-13-15 | fixed (e7f9d717, WitnessMeshTest red first; GUI case to re-run in container) | GUI display-mesh BoundBox: curved-face datum REPOINTED after Length edit (tc-18-04b) |
| RT-1 | Q5, Q6 | high | redteam-13-15 | fixed-proven (builder-13-15b: counter detector + lineage check; p6c test red first; detector-false mutant 3 red) | p6c_datum_point.py: story OK/CLEAN, datum x 16 -> 33; base SPEC_FAILED/REPOINTED |
| R3-1 | outside the bar (residual of decision 40 (2)) | medium -> accepted residual (leader) | r3 blind abf6e79051bccc7c4 / edge a47b1fe47c6fc41c9 / gap a4ef51292407550fa | deferred | inward-tapered Pad Length edit: top-face datum REPOINTED (support box does not move); same verdict before the Story; safe side; decision 017 + deferred entry |
| R3-2 | outside the bar (residual) | medium -> accepted residual (leader) | r3 lenses | deferred | Revolution.Angle end face, Pad.Reversed toggle: REPOINTED; same before the Story; safe side |
| R3-3 | outside the bar (residual) | medium -> accepted residual (leader) | r3 lenses | deferred | datum on vertical pad edge: mapped-name hash changes, outside the witness rule; same before the Story |
| R3-L | various | low x7 | r3 lenses | 4 fixed, 3 rejected | shrink/midplane tests, snapshot stub test, doc text; rejected e2e proxy assert, fillet baseline recompute (pre-existing), scale-only |
| R2-1 | Q4, Q6 | medium (product) | r2 blind a172c9cd0ce68edcc / edge a2faf83417d32a91a / gap a93d74c86da8d3dcb | fixed-proven | bound ignored sign (element -5 beside support +5 excused); test red first, signed per-axis face shifts; mutant abs shifts -> 4 red |
| R2-2 | Q1, Q6 | medium (test) | r2 lenses | fixed-proven | written-baseline test could not fail on a baseline swap; NaN planted in written support only; swap mutant -> 4 red |
| R2-L | various | low x8 | r2 lenses | fixed | NaN guard position, cross-axis audit test, raising-Shape test, minimum-face and reversed-pad tests, e2e datum record, decision 017 text, design residual text, alias placement |
| R2-R | outside the bar | low | r2 lenses | rejected | rotated support: safe-side false positive, documented in 017 |
| R1-L | various | low x6 | r1 lenses | fixed | NaN test, fillet invalid assert, docstrings, sketch width checks, decision 017 links, unreadable target keeps record |
| R1-R | outside the bar | low x3 | r1 lenses | rejected | Layer 2 must run (spec); scorer ran, sensitivity 1.0; support ShapeType change is safe side |
| R1-D1 | Q11 | low (maybe-false) | r1 lenses | deferred to verifier | curved element under GUI mesh deflection: container probe by verifier-13-15 |
| R1-D2 | Q9 | low | r1 lenses | deferred | design RefRecord block drift, pre-existing |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1 | 0a9904ba -> fix 851e7a7c | blind ac46ce7983f872c54, edge a6c640398f275a239, gap ae06149357a2a30d3 | 3 -> 3 (fixes unproven by review) | 0 | 3 | 0 |

r1 had a product medium and the fix batch is 63 product lines in tnp_guard.py -> round 2 with all three lenses on 0a9904ba..851e7a7c.
| r2 | 851e7a7c -> fix a835c153 | blind a172c9cd0ce68edcc, edge a2faf83417d32a91a, gap a93d74c86da8d3dcb | 3 -> 2 | 3 | 2 | 0 |

r2 had a product medium (R2-1); fix 57 product lines -> round 3 (last allowed round) with all three lenses on 851e7a7c..a835c153. If r3 does not pass: stop, fresh builder or user.
| r3 | a835c153 -> fix 5115b2ac | blind abf6e79051bccc7c4, edge a47b1fe47c6fc41c9, gap a4ef51292407550fa | 2 -> 0 | 2 | 0 (3 residual false positives, pre-existing, safe side) | 0 |

r3 passes: no high; the three mediums are false positives that existed before the Story (same verdict at base) and stay on the safe side (FLAGGED, never a missed re-point); leader classifies them as residuals inside decision 40 (2) boundary ("accept that an element ... stays REPOINTED"), deferred with entries. Round-3 product change 8 lines (docstring). Next: verifier-13-15 + redteam-13-15.
| RT (r4) | 5115b2ac | redteam-13-15 | 0 -> 1 (RT-1 high) | 0 | 1 | 0 |

Red team reproduced a high after round 3. Three rounds are used and builder-13-15 ran three fix rounds: hand off to a fresh builder (builder-13-15b) with this ledger and triage-13-15-rt.md; one more review round, then verifier + no second red team unless the fix is larger than a small patch.
| r5 | 5115b2ac -> e82521c1 | blind ab10f8369b8d24a17, edge a67d4bffa3a56a461, gap a2efbad7520524d06 | 1 -> 0 (R5-1 fix unreviewed) | 2 | 1 high + 1 product medium (fixed in round) | 0 |

The lineage fix for R5-1 has no independent review: leader dispatches a second, narrow red team on e82521c1 (justified: an unreviewed fix to a reproduced high), then verifier-13-15 re-runs.
| RT2 | e7f9d717 | redteam-13-15b | 0 -> 1 (RT2-1 high) | 2 (R5-1, D-1) | 1 | 0 |

Fourth real re-point through a naming form. Leader decision 48: close the class by a count guard (same element count before and after), plus the instance-index forms; one more narrow red team; if it reproduces another real re-point, stop and ask the user (fallback: drop the excuse, keep the exact-witness fix).
| RT3 | 6d6bdc60 | redteam-13-15c | 1 -> 0 | 1 (RT2-1) | 0 in the diff (RT3-1 pre-existing, deferred) | 0 |

Third red team PASS for the batch. Next: verifier-13-15 re-run at the final head incl. TC-18 01-04 and 04b in the container.
