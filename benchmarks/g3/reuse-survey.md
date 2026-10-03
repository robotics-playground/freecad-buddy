# G3 entry gate — reuse survey

`phase-gates.md:3` requires a recorded reuse survey in every entry gate. This is the G3.E record
(`gate.yaml` entry `G3.E.7`, owner Story 4.1). Source surveyed: commit `bb42999`, a Phase 3
implementation that put a designer loop in the repository and was reverted (AD-35). Rule: reuse
pure data only; restore no loop, judge, designer or actor code.

## Reused

| What | Where now | Form | Why |
| --- | --- | --- | --- |
| 20 dev specs | `dev/*/case.yaml` | restored, then amended (see below) | Written from documented real parts before any implementation, with hand-derived assertions. Rewriting them would lose that provenance. |
| 20 dev provenance manifests | `_registry/provenance/g3-dev-*.yaml` | byte-identical | The commercial-clean record for each spec. |
| 7-case sealed held-out split | `heldout/SEAL.json`, `heldout/heldout.tar.enc` | byte-identical, `unseal_events: []` | Re-sealing would need new held-out specs; the existing seal is unspent. |
| 14 corrupted-plan cases | `fault-injection/corrupted-plan/` | rewritten | The defect taxonomy (value, frame, topology, insertion, omission, ordering) and the pairing with clean controls carry over. The plant mechanism did not: it named reverted code. |
| `check_provenance` `part-spec` rule | `scripts/check_provenance.py` | re-applied | A spec ships no `.FCStd`, so its manifest must bind to the case file. |

Amendments to reused data, all made after the reverted code existed and disclosed in each file
and in `README.md`:

- `g3-dev-007`, `g3-dev-011`: position and axis checks (DW-122).
- `g3-dev-002`: its clearance hole was already added in `bb42999` (DW-127, DW-129); the audit
  adds a placement sentence and two edge-distance checks.
- `g3-dev-019`: the datum's name and corner stated in the prose, plus edge-distance checks.
- `g3-dev-008`, `g3-dev-017` and 14 more specs: checks for requirements the prose states but no
  check enforced. Audit test: can a part that violates a stated requirement pass every check?

## Rejected

| What | Why rejected |
| --- | --- |
| `usecases/designer_loop.py`, `contracts/designer.py`, `designer-run.schema.json` | The plan → execute → measure → repair loop belongs to the agent (AD-35). |
| `usecases/verify_visual.py`, `contracts/visual.py`, `adapters/visual_judge_client.py`, `benchmarks/g3/judge.py`, `benchmarks/harness/judge_double.py`, `judge-verdict.schema.json` | The visual review is performed by the agent through the `visual-review` skill; no judge or model client lives in the source tree. |
| `benchmarks/g3/actor_run.py`, `make_actor_plans.py`, `actor-plans/`, `actor-results.json` | Plans pre-authored for an actor run measure a replay, not an actor (DW-130). The G3 actor is an external agent harness (Story 4.5). |
| `fault-injection/planted_plans.py`, `score_g3_infc.py` | Planted faults as `plan_shape` builder steps driven through the designer loop. Replaced by recorded `{tool, args}` plans over the real MCP tools. |
| `fault-injection/visual-judge/` (8 cases, renders, rubric, grading) | They grade the reverted judge. Drawing-generator fault cases are owned by Story 4.3. |
| `fault-injection/assertions/` (7 cases) | Driven through `planted_plans.py`. The assertion primitives and their scoring land in Story 4.2. |
| `fault-injection/recompute/` (20 cases), `planted_recomputes.py`, `score_recompute_infc.py` | Planted through the designer loop. A `verify_recompute` suite is owned by the editability story (DW-124). |
| `corrupted_plan.json`, `g3_assertions.json`, `verify_recompute.json`, `visual_judge.json` | Measured results over reverted code. A sensitivity number is current only for the code it was measured on. |
| `validators.yaml` rows `corrupted_plan`, `g3_assertions`, `visual_judge`, `verify_recompute` | Same reason; no row is reused. |
| `check_provenance` `driven-by-designer-loop` / `driven-by-mutation-bracket` exemptions | They exempt fixtures planted by reverted drivers. G3 fault cases declare `fixture: pending`. |

## Not reused by 4.1, open to the owning story

These are not loop code, but they are implementation, and Story 4.1 lands data only. Each owning
story decides whether to start from them or not.

| What in `bb42999` | Owner |
| --- | --- |
| `benchmarks/harness/assertions.py` (11 primitives, anchor-frame resolver, DW-123 bounding fix) | 4.2 |
| `usecases/techdraw.py`, `contracts/techdraw.py`, `drawing-sheet.schema.json`, `adapters/render_probe.py` | 4.3 |
| `usecases/parameters.py`, `contracts/parameters.py`, `benchmarks/harness/editability.py` | 4.4 |
