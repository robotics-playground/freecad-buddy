# Story 13-19: findings ledger

Quality bar: quality-bar-13-19.md.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| RT-1..RT-3 | Q1-Q4 | medium (doc) x3 | redteam-13-19 | fixed-proven (22e96c4d; verifier r2 probes) | missing cross-skill link; worked example placements unbound (coverage script not []); parked additive fit tool gives 2 solids / 2400 |
| RT-4..RT-7, L-1..L-3 | various | low | redteam-13-19, verifier-13-19 | fixed (22e96c4d, 3a993adf, 075c77fe) | see triage |
| R1/R2 | various | per spec triage log | builder lenses r1 (blind, edge, gap), r2 (edge) | fixed / rejected | see wt-13-19 spec triage log |
| B-1 | Q1, Q9 | medium (routing) | builder-13-19 | fixed (f42cde8a) | MCP server instructions named no loft/sweep/Part tools |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| r1-r2 | ba41f0be -> f42cde8a -> merge 135fd94c -> f151a456 | builder-run lenses (ids in the wt-13-19 spec) | n/a -> 0 | - | - | 0 |
| RT | f151a456 | redteam-13-19; verifier-13-19 (PASS) | 0 -> 3 (doc mediums) | 0 | 3 medium + 7 low | 0 |
| v2 | 22e96c4d -> 3a993adf -> 075c77fe | verifier-13-19 r1 (f151a456 PASS) + r2 (3a993adf PASS; L-5, L-6 fixed text-only in 075c77fe) | 3 -> 0 | 3 | 0 | 0 |

Closed; merged into feat. Q9 (live routing) runs at epic close.
