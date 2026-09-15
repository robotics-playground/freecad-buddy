# G4 Reuse Survey

What this gate reuses from the existing harness, and what it builds new with the reason. The
survey exists so a fourth parallel scorer is not written by habit.

## Reused unchanged

| Machinery | Where | Why it fits |
| --- | --- | --- |
| Registry read-merge-write | `benchmarks/g0/export-fault-injection/score_export_verify.py` `merge_validators_yaml` | One merge-writer for `validators.yaml`. A gate that wrote the file whole would clobber every other gate's block |
| Wilson CI, sensitivity, false-alarm | `src/freecad_buddy/usecases/stats.py` | The bars and their intervals are gate-independent arithmetic |
| Gate loader and criteria parsing | `benchmarks/runner.py` `_load_gate`, `_load_gate_def` | The runner READS `gate.yaml`; G4 needed a file, not a loader |
| Validator currency rule | `benchmarks/harness/verdict.py` `check_validator_currency` | Leg-b's sha-match plus bars rule is the same for every gate |
| Source-plus-suite digest | `benchmarks/runner.py` `_validator_src_hasher`, `_suite_sources` | The existing hasher already folds a suite in by `targets_validator`; G4 needed a routing branch, not a new hasher |
| Terminal status vocabulary | `src/freecad_buddy/contracts/status.py` | AD-17 keeps one source. All four G4.E fault statuses already existed |
| `JobStatus` shape | `src/freecad_buddy/contracts/job.py` | Already defined in Phase 0 with no producer. G4 is its first consumer |
| Case file schema | `benchmarks/g3/fault-injection/*/case.yaml` | Same keys, same `planted_defect`/`clean_control` pairing, same driver handoff |

## Built new, with the reason

| Thing | Why it could not be reused |
| --- | --- |
| `stub_service.py` | No job-service seam existed. Modeled directly on `benchmarks/g3/judge.py`, which is the same pattern one layer up: fix the contract shape before the implementation, answer honestly until it lands |
| `fault-injection/score_g4_validators.py` | Scorers are per-gate by construction — each declares its own validator source sets, suite map and driver handoff. The structure is copied from `score_g3_validators.py` including the three-way `skipped` / `excluded_unscorable` / `not_scored` distinction |
| `fault-injection/drive_g4_faults.py` | The G2/G3 drivers run inside FreeCAD because their faults need geometry. A G4 fault is a supervisor-level event — a deadline, a memory cap, an abnormal exit — and none needs a document, so this driver runs in the uv environment |
| `_G4_VALIDATORS` / `_G4_SUITE_ROOT` and the hasher branch | The hasher routes a validator to its suite root by gate membership. Without the branch a G4 name falls through to the source-only digest, never folds the suite in, and every G4 row reads stale forever |

## Story 5.3: why the jail is namespaces rather than nsjail or bubblewrap

The design names nsjail or bubblewrap for the Linux jail, with a hardened OCI container as the
CI-reproducibility alternative. Measured on the development host: neither binary is installed,
and `mkdir` under `/sys/fs/cgroup/unified` is permission-denied unprivileged.

A sandbox depending on them would make every containment claim an assertion rather than a
measurement, because nothing could run the test that checks it. What those tools wrap — user,
mount and network namespaces — is reachable unprivileged through `unshare`, which ships with
util-linux everywhere the project runs. Verified working before the backend was written: an
empty network namespace denies egress, and a bind-then-remount sequence leaves `jobs/<id>/` as
the only writable path.

So the posture the design fixes is unchanged and the mechanism is narrower and provable. Seccomp
and cgroup limits stay as hardening the backend detects and uses when available, reported as
`weakened` when it falls back. Revisit if a deployment target ships the tools by default.

## Deliberately NOT built

Story 5.5 owns the exit ceremony. G4 is absent from `_SEALABLE_GATES`, `_EXIT_EVALUATORS` and
`_EXIT_PRECONDITIONS`, and `gate.yaml` declares `verdict.heldout: inert`. A `sealed` declaration
here would engage leg-c against reports no exit run has produced, and sealing a held-out split
before one is authored would burn nothing for nothing.

## One duplication accepted

`score_g4_validators.py` repeats roughly the shape of `score_g3_validators.py`: `_load_case`,
`_suite_case_files`, `_validator_sha`, `_partition`, and the `not_scored` branches are structurally
parallel. Extracting a shared base was considered and rejected: the four existing scorers have each
diverged where their gate needed it (G3 carries a live-call gap, G1 folds a rubric into its digest,
G0's export scorer owns the merge-writer), so a common base would either be a near-empty shell or a
parameter list reproducing every divergence. The duplication is visible and local; the coupling
would not be. Revisit if a fifth gate repeats it again.
