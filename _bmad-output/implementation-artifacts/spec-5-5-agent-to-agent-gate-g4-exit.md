---
title: 'Story 5.5: Agent-to-Agent Proof & Gate G4 Exit'
type: 'feature'
created: '2026-09-15'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '_bmad-output/implementation-artifacts/g4-exit-record-2026-09-15.md'
  - '_bmad-output/implementation-artifacts/g3-visual-leg-blocker-2026-09-15.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** The Phase 4 service exists but nothing proves an external agent can drive it without
a human, nothing measures whether it survives sustained load, and the G4 gate has no collectors —
every criterion fails `INVALID_INPUT` regardless of what the service can actually do.

**Approach:** Add a health surface that samples RSS at job boundaries, run the 50-job soak and the
agent-to-agent cycle, wire G4 collectors that read the recorded evidence, and run the exit
ceremony. Report what it produces.

## Boundaries & Constraints

**Always:**
- Measure, then report. A criterion's collector reads a recorded artifact rather than re-running
  the measurement, so a gate verdict is reproducible over committed files.
- Every verdict is derived from checks, never asserted. A self-graded report could not fail.
- A criterion that cannot be measured names the SPECIFIC gap. A generic "no collector" reads as
  missing wiring rather than a blocked measurement.
- The soak mix includes failures. Fifty clean jobs measure the happy path fifty times and would
  miss the leak a killed worker leaves behind.
- RSS comes from the health surface at job boundaries, never from a post-hoc log parse.

**Never:**
- Do not add `psutil`. The supervisor's flat memory is the measurement's foundation, and a
  third-party package in that process works against it.
- Do not mint the `spot_audit` token. It attests a HUMAN audited the results; `attest_command`
  verifies nothing about who ran it, so an agent minting one fabricates the audit.
- Do not seal a G4 held-out split. G4 declares `heldout: inert` and has none.
- Do not write the spec-to-plan translator to make G4.1 pass. That is the actor the G3 gate
  grades, and authoring it here would be grading our own work.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| RSS sampled | A live pid | Positive byte count | Zero when unreadable, never raises |
| RSS of a dead process | A pid that does not exist | `0` | Visible as a zero in the report |
| Growth with a reclaimed peak | Samples rise then fall | Growth measured against the PEAK | A reclaimed leak still happened |
| Soak runs | 50 mixed jobs | Every job resolves to a closed-set status | A hang is a job never resolved |
| Agent cycle | submit/inspect/revise/accept | All four complete, zero human input | A step outside the closed set fails the cycle |
| Auto-approve set | Global flag on during the cycle | Cycle marked NOT passing | The flag is a human's standing approval |
| Criterion measurable | Evidence artifact present | Report derives `OK` | — |
| Criterion blocked | Parity artifact present, gap open | Not-collected naming the gap | Never a bare failure |
| Artifact absent | No evidence file | Not-collected naming the command | Never opaque |

</intent-contract>

## Code Map

- `src/freecad_buddy/hosts/phase4/health.py` — new. `rss_bytes` via `/proc/<pid>/statm` on POSIX
  and `GetProcessMemoryInfo` through `ctypes` on Windows; `SoakReport.supervisor_growth` measures
  against the peak.
- `benchmarks/g4/run_soak.py` — new. 50 jobs over a mix including `crash`, `hard_exit` and
  `sleep`; writes `soak-results.json`.
- `benchmarks/g4/run_agent_cycle.py` — new. Drives the four-step cycle; writes
  `agent-cycle-results.json`.
- `benchmarks/runner.py` — `_collect_g4` and `_G4_ARTIFACTS`; `_g4_parity_gap` names why each of
  G4.1/G4.2/G4.3 is unmeasured. Reports go through `evidence_report` so the verdict derives.
- `benchmarks/g4/THREATS.md`, `_bmad-output/implementation-artifacts/g4-exit-record-2026-09-15.md`
  — what was measured and what remains blocked.

## Tasks & Acceptance

**Execution:** all landed; see the Code Map.

**Acceptance Criteria:**
- Given 50 mixed jobs, when the soak runs, then supervisor growth is under 20%, hangs and silent
  failures are zero, and every job resolves inside the closed status set. **Met: 2.00% growth,
  0 hangs, 0 silent, statuses `{OK: 43, TIMEOUT: 2, WORKER_CRASHED: 5}`.**
- Given an agent client, when it drives submit → inspect → revise → accept, then all four complete
  with zero human input and no process-global auto-approve. **Met.**
- Given the recorded evidence, when the gate runs, then G4.4 and G4.5 report `OK` and the
  remaining criteria name their specific blocker. **Met.**
- Given the exit ceremony, when the verdict is computed, then it is honest about the gate's state.
  **Met: G4 is RED, recorded in the exit record.**

## Design Notes

**Why the soak mix is not all-passing.** Killing workers is the normal condition of a service
running untrusted specs, and the leak that only appears after a kill is exactly the one a
clean-only soak would miss. "No crash or hang" is therefore read as the SERVICE never crashing or
hanging; a job resolving to a structured failure is the service working.

**Why growth is measured against the peak.** A leak reclaimed just before the run ends still
happened. Comparing only first and last samples would report it as zero.

**Why the spot_audit token stays unminted.** Leg-d attests that a human audited at least 20% of
passing results. `attest_command` stamps `signed_by` from the environment and verifies nothing
about who ran it, so the boundary is procedural. An agent minting the token would fabricate the
audit, and the gate reporting `spot_audit token absent` is the correct outcome.

## Verification

**Commands:**
- `uv run pytest tests/external/test_gate_g4_exit_ceremony.py -q` — 21 pass.
- `uv run pytest tests/external -q` — 1591 pass.
- `uv run python benchmarks/g4/run_soak.py` — PASS, 2.00% growth.
- `uv run python benchmarks/g4/run_agent_cycle.py` — PASS, exit 0.
- `uv run python benchmarks/runner.py run G4 --run <id>` then `verdict G4 --run <id>` — G4.4 and
  G4.5 PASS; gate RED.
- `uv run python scripts/check_imports.py` — OK.
