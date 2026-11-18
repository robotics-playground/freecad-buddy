# Story 10-8-d (preparation): findings ledger

Quality bar: `quality-bar-10-8-d-prep.md`.

| Id | Q | Severity | Source | Status | Proof |
| --- | --- | --- | --- | --- | --- |
| B-M1 | Q6 | medium | builder lenses r1 | fixed-proven | swallowed GUI failures: `gui_error` flag; proof re-run from committed bytes (`build-10-8-d.md`) |
| B-M2 | Q9 | medium | builder lenses r1 | fixed-proven | scorer temp copy took `heldout` folders; now `tar --exclude=heldout`; proof re-run |
| B-M3 | Q6, Q7 | medium | builder lenses r1 | fixed-proven | proofs re-run from the committed bytes |
| F3 | Q9 | low | builder self-report | fixed-proven | first headless proof copied sealed `heldout` folders into a container temp dir (no file read, not unsealed); deleted; command fixed. Verifier confirms no `heldout` path left (decision 43) |
| RT1 | Q4 | medium | redteam-10-8-d | fixed-proven | spec `:49` single runner `--out`; a §9 launch-group re-run overwrites `results.json`/`summary.md` and loses the R0 record and drawn seed; reproduced with two `run.main` calls |
| RT-L1 | Q4 | low | redteam-10-8-d | fixed-proven | spec `:59` cites test-plan `:342-441`; gate rules now at `:457-561` |
| RT-L2 | Q9 | low | redteam-10-8-d | fixed-proven | `--exclude=heldout` still copies git-ignored `benchmarks/gate-artifacts/g2/devrun-heldout-blind` into `/tmp/g3r` |
| RT-L3 | Q6 | low | redteam-10-8-d | fixed-proven | `g3_gui_replay.py` needs `pyyaml`, only in the dev extra; spec command must load it |
| V-F3 | Q6 | medium | verifier-10-8-d | fixed-proven | GUI row with `gui_error` keeps status OK and exit 0; harness can pass without a capture; fix D2 |
| V-F1 | Q5 | low | verifier-10-8-d | rejected (kept: unlink stops a stale capture passing; docstrings fix stale :8765 text) | extra docstring and `unlink` hunks in the port; fix D7 |
| V-F2 | Q5 | low | verifier-10-8-d | fixed-proven | CRLF working copy hash differs from blob; record blob hash; fix D8 |
| V-F4 | Q8 | low | verifier-10-8-d | fixed-proven | S0 line lacks `run_faults.py` / `pixel_faults.py` commands; fix D6 |
| B-low | — | low | builder lenses r1 | fixed / rejected | 5 patched, 10 rejected; `build-10-8-d.md` |

## Rounds
| Round | Head | Lenses (session ids) | Open high + product medium: before → after | Closed with proof | New | Regressed |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 6e640c4 | Blind 14, Edge 14, Gap 3 findings (ids in `build-10-8-d.md`) | 0 → 0 (no product code); harness medium 3 → 0 | 3 | 3 | 0 |
| V/RT | 6e640c4 | verifier-10-8-d PASS (Q1-Q10); redteam-10-8-d FAIL (RT1) | harness medium 0 → 2 (RT1, V-F3) | — | 2 medium, 6 low | 0 |
| D | c928eb5 | none (port +8 lines); verifier-10-8-d re-run PASS (R0 results byte-equal after re-run; wrong window exit 1; 0 heldout paths) | harness medium 2 → 0 | 2 medium, 5 low | 1 low (F5, decision 44) | 0 |
