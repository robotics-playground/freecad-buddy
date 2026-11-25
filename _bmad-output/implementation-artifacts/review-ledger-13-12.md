# Story 13-12: findings ledger

Quality bar: `quality-bar-13-12.md` (this folder). Lens triage: spec in branch story/13-12-skill-routing-measure.

| Round | Head | Lenses (session ids) | Open high + medium: before → after | Closed with proof | Notes |
| --- | --- | --- | --- | --- | --- |
| r1 | 4333288b | blind a8d10f0df9005f43c; edge ac65055ef1639a4f0; gap ae38f3db770d95a84 | 3 high + 8 medium → 0 | builder patches | |
| rt/verify | 4333288b | redteam-13-12; verifier-13-12 | RT-1, RT-2 high; RT-3..RT-6, D1, D2 medium | | touching parts routed to a `common()` script that reads 0; Delete marked covered |
| r2 | 1d1150d0, b4f2f49c | gap af3056df8334e5b19 | → 0 high; R2-1 medium | RT-1..RT-10, D1-D5 (verifier r2 live: 7 contact cases read 0 with a valid fuse; overlaps read true volume; mid-Body delete script keeps and relinks) | |
| r3 | 5ad4fe3e, fc96975c | none (text) | R2-1 → 0 | verifier r3: generator steps run as written; fuse script verbatim | O-R3 delete example fixed in fc96975c |
