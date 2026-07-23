# 012 — G1 Held-Out Sealing Uses a Stdlib Cipher, Not `age`; It Seals a Placeholder

## Decision

The Gate G1 held-out sealing ceremony (`benchmarks/harness/seal.py`) encrypts the archive with a
**stdlib-only symmetric cipher** — a `hashlib`-derived keystream XOR'd over the `tarfile` bytes —
and names the file `heldout.tar.enc`, NOT the `heldout.tar.age` the design names. No `age` binary
and no `pyrage`/third-party encryption dependency is added. The runner-enforced contract is
cipher-independent: a SHA-verified sealed archive whose key is human-held (read only from
`FREECAD_BUDDY_UNSEAL_KEY`), unsealed exclusively by `gate run G1 --exit`, with an appended
`unseal_events` audit trail and a burn stamp on a failed exit, and a hard refusal from every dev
run. The runner only ever checks `archive_sha256` + the manifest, never the cipher internals — so
an operator who wants true `age` at the real exit can supply it through the same `key` seam.

There are **no live held-out cases yet**, so this story seals a `case_count: 0` **placeholder**.
The machinery (seal → unseal → burn, leg-c R≥10 + gap math, key-absent refusal, dev-run
heldout-blindness) is what CI proves offline; the live ≥80% / second-backend pass numbers stay the
operator exit ceremony (decisions 010/011), never asserted by an unattended job.

## Rationale

- **No gratuitous required dep (CLAUDE.md §2 simplicity).** The env has neither an `age` binary nor
  a `pyrage` module, and neither is in `pyproject.toml`. Adding an encryption binary/library as a
  required dependency to satisfy a file-name choice is speculative weight the auditable contract
  does not need. `benchmarks/` is external tooling, but even there a stdlib solution that fully
  satisfies the enforced contract is preferred over pulling a new dependency tree.
- **The contract is cipher-independent.** What the gate actually enforces is: (1) the archive's
  `archive_sha256` matches before extraction (tamper detection), (2) the key is human-held and
  never committed/CI-secret, (3) only `--exit` unseals, into a temp dir it deletes, (4) each unseal
  appends an audit event and a failed exit burns the set, (5) no dev run touches `heldout/`. A
  `hashlib` keystream XOR makes the archive non-plaintext and key-bound — sufficient for every one
  of those properties. The name is honored as `.enc`.
- **Deterministic under test.** `sealed_at`, the unseal `timestamp`, and `git_sha` are injected by
  the runner (the runner reads the clock / `git rev-parse`), so `seal.py` never calls
  `datetime.now()` or spawns a subprocess — it stays a pure, FreeCAD-free, deterministic helper,
  mirroring how `actor_run` takes `repeats` and injected doubles.
- **Placeholder, not a fabricated split.** Authoring an independent held-out eval split is a human
  ceremony, not code this story synthesizes (Block-If). A `case_count: 0` manifest is a valid
  sealed placeholder, so the shippable, CI-provable deliverable is the machinery exercised over an
  empty archive — not a live number.
- **`--exit` is not an offline shortcut.** A genuine exit needs the operator backend at R≥10
  (decision 010). Offline, `--exit` still enforces the key gate + the full ceremony; running the
  scripted double under `--exit` is a clearly-labelled machinery dry-run, never presented as the
  operator's measured pass-rate.

## Reuse survey (vendor `age` vs a stdlib cipher)

- **Surveyed: vendor the `age` binary / add `pyrage`.** Rejected as a required dep: it pulls an
  external binary or a native-extension wheel into what is otherwise a stdlib-only `benchmarks/`
  tool, for no gain the enforced contract can observe (the runner checks the SHA + manifest, not
  the ciphertext format). It would also make the ceremony non-runnable anywhere the binary is
  absent — the opposite of the reproducible-without-secrets discipline the entry gate is built on.
- **Surveyed: a stdlib symmetric cipher (`hashlib` keystream XOR over `tarfile`).** Adopted — zero
  new dependency, deterministic, key-bound, and it satisfies every property the runner enforces.
  The `key` seam still accepts an operator's stronger tool at the real exit if they want one.
- **Surveyed: reuse the existing verdict / report / Wilson-CI machinery.** Adopted — leg-c reads
  `banner["wilson_ci"]["r"]` off the stored exit reports (the CI already carries `r`/`n`) and the
  dev/held-out gap from `dev_rate.json`; it forks no stats and adds no `contracts/` type.

## Boundaries

- The unseal key is read ONLY from `FREECAD_BUDDY_UNSEAL_KEY` — never committed, never a CI secret,
  never an env file at rest. `seal` / `run --exit` without it is a clean exit-2 UsageError naming
  the var, never a traceback and never an offline fallback.
- Only `gate run G1 --exit` unseals `g1/heldout/`; `seal`, `run`, `--actor-run`, `--stub`, and CI
  never extract it. The unseal always targets a temp dir the runner deletes in a `finally`.
- A failed exit (verdict FAIL) burns the set; a later `--exit` on a burned set refuses (exit-2)
  until a fresh `seal`.
- No key/secret/GGUF/network ever enters CI; the gate-exit workflow is `workflow_dispatch`-only and
  asserts NO live pass-rate.

## Drives

- `benchmarks/harness/seal.py` (`seal_heldout` / `unseal_heldout` / `burn_seal` / `read_manifest`).
- The `verdict.check_exit_run` leg-c (R≥10 banners + `dev_rate.json` gap) wired into
  `compute_verdict` for a `verdict.heldout: sealed` gate.
- The runner's `seal` subcommand + `run --exit` ceremony (key gate → unseal → R≥10 eval →
  reports + `dev_rate.json` → verdict → burn-on-FAIL → temp cleanup).
- The `workflow_dispatch`-only `gate-exit.yml` and the CI `arch-checks` offline machinery step.
