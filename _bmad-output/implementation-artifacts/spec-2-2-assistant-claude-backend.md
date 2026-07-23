---
title: 'Story 2.2 — Assistant on the Claude Backend'
type: 'feature'
created: '2026-07-24'
status: 'done'
baseline_revision: '7144c04a037e7ec6dae7696a19ed69abffc9a8a5'
final_revision: '55eeff6'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-2-1-entry-gate-g1e-eval-rubric-grader.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** Epic 1 shipped the read-only `query_*`/`verify_*` tool surface and Story 2.1 landed the G1 eval set + tiered broken-doc fixtures + validated deterministic grader that fail honestly against a stub. Nothing yet drives a real backend through that surface: there is no read-only assistant profile (G1.6), no actor-run harness that runs the eval questions through a model and grades the answers, and no tiered n10→n30 error-diagnosis escalation logic. The gate runner only supports `--stub`.

**Approach:** Land the read-only assistant and its actor-run harness in the external process. Build a **read-only tool profile** (explicit allow-list; zero geometry-mutation tools registered — G1.6) and a **G1 actor-run harness** that, given a backend, drives each eval question through the profile's MCP tool surface, collects the final answer, grades it with the Story 2.1 grader, applies the tiered n10→n30 escalation (decision 008), and emits one `ValidationReport` per case×repeat with Wilson CI. The Claude backend is Claude Code / Claude Desktop over MCP (the design's "Claude backend" is the client, not a bespoke SDK client). The live-model eval run is operator-gated (requires an API-capable backend + key) and is **skipped in unattended CI**; everything else — the read-only profile, the escalation logic, the summarized-tree usage, the grader wiring, the honest-fail behaviour — is deterministic and CI-tested offline against a scripted backend double.

## Boundaries & Constraints

**Always:**
- Read-only guarantee (G1.6): the assistant profile registers **zero geometry-mutation tools**. The profile is an explicit read-only allow-list — `query_*` (all 7), read-only `verify_*` (`verify_shape`, `verify_sketch`, `verify_recompute`), and the non-mutating document-lifecycle tools needed to open/inspect/close a fixture (`document_open`, `document_close`, `document_list`). No `sketch_*`/`feature_*`/`preview_*`/`document_create`/`document_save`/`debug_exec`. Introspecting the profile is itself a gate check.
- No self-grading (AD-13, hard invariant): pass/fail comes only from the Story 2.1 grader (or a model-backed grader plugged into the same `GraderClient` seam). The actor never grades itself. The grader input is the actor's **final answer** (not scratch reasoning) + `rubric.md` + the case's `expected_findings`.
- Actor drives the **same MCP tool surface as production** (harness-design §7 step 3) — the read-only profile registry, never a private code path.
- Summarized-tree queries only (`query_tree_summary`, bounded `max_nodes`) — never raw tree dumps (latency + context invariant, G1.3 groundwork, load-bearing per clients-design §7).
- Tiered escalation (decision 008): grade n=10 first (the 10 `tier: n10` broken-doc cases); pass = ≥8/10; escalate to the full n=30 **only** on a perfect 10/10. Report Wilson CI on the rate.
- In-FreeCAD purity (AD-12): the actor harness, any model client, and MCP libs live in the **external uv process** under `benchmarks/`/`adapters/harness/`. In-FreeCAD code stays stdlib + FreeCAD API only.
- Confirmation posture: no mutations exist in Phase 1, but the harness/adapter posture stays fail-closed / token-fallback (no-elicitation matrix row) so it is correct when mutations arrive in Epic 3.
- Conventional Commits; no AI attribution. Never commit without explicit approval **except** the pre-approved per-story bmad-loop commit to the current branch.

**Block If:**
- A design contract must change to place the read-only profile (e.g. `mutating` semantics vs an explicit allow-list conflict surfaces a spine/AD contradiction) — stop, cite the AD/design doc, do not silently diverge.
- Landing the story green unattended would require putting an API key or model secret into CI, env files, or the repo — that violates harness-design §6 (secrets human-only) and cannot be decided unattended. HALT rather than wire a live-key CI path.
- The read-only profile cannot be built without registering a mutation tool (i.e. an eval question genuinely requires a mutating tool) — this contradicts the read-only guarantee; stop and surface it.

**Never:**
- Never run the live Claude/model eval in unattended CI or fake its pass-rate numbers. The ≥80% figure is *measured* by an operator run, not asserted by a green CI job.
- Never register a geometry-mutation tool in the assistant profile, and never route the actor through anything but the typed read-only tool surface.
- Never grade an answer with the actor's own model/context (preflight already hard-fails actor==grader).
- Not in scope: the local llama.cpp backend + ReAct adapter (Story 2.3), the sealed held-out exit run + human tokens (Story 2.4), the skills authoring (Epic 6), any model-backed (fuzzy) grader — the deterministic grader from 2.1 is used as-is via its seam.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Read-only profile built | Phase-1 assistant profile requested | Registry exposes only the read-only allow-list; enumerating it lists zero geometry-mutation tools (G1.6) | n/a |
| Mutation tool absent from profile | Profile introspected for `pad`/`pocket`/`feature_*`/`document_save`/`debug_exec` | None present | n/a |
| Error-diagnosis case, actor names *the* object+cause | Broken-recompute fixture; actor answers via `verify_recompute` + `getStatusString` | Grader `pass=True`, `matched_expected=True`; report `OK` | n/a |
| Error-diagnosis case, confident-wrong answer | Actor names wrong/other object | Grader `pass=False`; report `SPEC_FAILED` | n/a |
| Tiered escalation, n10 ≥8/10 but <10/10 | 10 n10 cases graded | Pass at n=10; **no** escalation to n30; Wilson CI reported | n/a |
| Tiered escalation, perfect 10/10 | 10 n10 cases all pass | Escalate to full n=30; grade the 20 n30 cases; Wilson CI on n=30 | n/a |
| Tiered escalation, n10 <8/10 | e.g. 6/10 | Fail at n=10; no escalation | n/a |
| Live backend unavailable in CI | No API key / offline harness run | Actor-run skips (xfail/skip), never errors the suite; offline deterministic checks still run | Skip is explicit + logged, not silent green |
| Scripted backend double (offline) | Recorded/scripted answers per question | Harness drives grader + escalation + report build deterministically end-to-end | n/a |
| Backend returns malformed / no final answer | Actor loop yields no parseable final answer | Case graded as fail (`SPEC_FAILED`), not a crash | Typed failure, one report per case |

</intent-contract>

## Code Map

- `src/freecad_buddy/hosts/tool_catalog.py` -- has `tool_specs()` (ordered `ToolSpec` list, each with `mutating` flag) + `build_inline_handlers()`. **Add a read-only profile selector** (allow-list of read-only tool names) that yields the assistant's `MethodRegistry`; do not change existing specs. `query_*` are `mutating=False`; `verify_shape/sketch/recompute` are `mutating=False`; `document_open/close/list` are `mutating=True` today but are non-geometry-mutating lifecycle — the profile is an **explicit allow-list**, not a `mutating` negation (see Design Notes).
- `src/freecad_buddy/adapters/mcp_server.py` -- `registered_tools(registry, caps)` filters `internal`/`exec_enabled`. The assistant profile registry passes through here unchanged; the profile is applied when *building* the registry, not by a new server filter.
- `benchmarks/harness/actor.py` -- **new**: the `Backend` protocol (drive a question → final answer over the read-only tool registry) + the ReAct-agnostic actor-loop primitives shared with 2.3. Lives in `benchmarks/` (outermost, non-ring external tooling — like `runner.py`), NOT in `adapters/`, because it must import the read-only profile builder from `hosts/tool_catalog.py` and `adapters/` may not import `hosts/` (`check_imports.py`). A `ScriptedBackend` test double (answers from a recorded map) lives beside it or in the test module for offline determinism.
- `benchmarks/g1/actor_run.py` -- **new**: the G1 actor-run harness. Given a `Backend` + the read-only profile registry + `eval-questions.yaml` + `broken-docs/`, run each case ×R (R=3 dev), collect final answers, grade via `benchmarks/g1/grader.py` `DeterministicGrader` (through `GraderClient`), apply the tiered n10→n30 escalation, and emit one `ValidationReport` per case×repeat with majority-of-R + Wilson CI. Live backend gated behind an explicit flag/env; absent → skip.
- `benchmarks/g1/gate.yaml` -- update `actor:` block from `placeholder-actor-model` to the real Claude-backend descriptor (still ≠ grader model; NFR1 preflight must stay green). Keep grader block + tokens + `verdict.heldout: sealed` intact.
- `benchmarks/runner.py` -- add the `--actor-run` (non-stub) path for `--gate G1`: build the read-only profile, resolve the backend from `gate.yaml actor:` (live if operator-supplied, else the scripted double for offline), invoke `benchmarks/g1/actor_run.py`, emit reports. Preserve `--stub` honest-fail behaviour and the G1 actor≠grader preflight unchanged.
- `benchmarks/g1/dev/eval-questions.yaml` / `broken-docs/<case>/case.yaml` -- consumed read-only (schema from 2.1: `expected_findings {object, cause}`; `tier: n10|n30`). No change unless a fixture gap is found.
- `tests/external/test_assistant_readonly_profile.py` -- **new**: pytest — the profile registers zero geometry-mutation tools (G1.6); the expected read-only allow-list is exactly present; `document_save`/`feature_*`/`debug_exec` absent.
- `tests/external/test_actor_run_g1.py` -- **new**: pytest — with a `ScriptedBackend`: (a) correct answer → grader pass → report `OK`; (b) confident-wrong → `SPEC_FAILED`; (c) tiered escalation table (8/10 passes no-escalate; 10/10 escalates to 30; 6/10 fails); (d) malformed/no-final-answer → typed fail not crash; (e) live-backend-absent → skip not error; (f) actor uses `query_tree_summary` not a raw dump (assert on the recorded tool calls).
- `.github/workflows/ci.yml` -- `arch-checks`: run the offline actor-run (scripted backend) + the read-only-profile test; assert the live eval is skipped (no key in CI). Do NOT add any key/secret or network step.
- `pyproject.toml` -- no new in-FreeCAD dep. Any model-client dep (if a live Claude SDK path is added) is external-only + optional; confirm ring/import checks stay green.
- `docs/decisions/010-claude-backend-live-eval-out-of-ci.md` -- **new** decision note: the Claude backend is the MCP client (not a bespoke SDK actor); the live eval is operator-gated + CI-skipped while the read-only profile + escalation + grader wiring ship CI-tested offline; the reuse survey (MCP client-as-actor vs custom loop) and why the ≥80% number is a measured operator run, not an unattended CI gate.

## Tasks & Acceptance

**Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)**
  - Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md` (language-agnostic rules; Python ring).
  - Re-read `validation-harness-design.md` §7 (gate execution flow, "actor runs drive the same MCP tool surface") + §8 (independent grader wiring) and `integration-mcp-clients.md` §2 (Claude wiring), §6 (backend capability matrix), §7 (latency budget / summarized-tree dependency).
  - Re-read `project-context.md` "Verification & Validation Discipline" (actor never grades itself; heldout sealed) + "Testing & CI Rules" (two test worlds) + "Architecture Ring & Import Rules" (harness/model client external-only, AD-12).
  - Re-read Story 2.1's spec Code Map + Design Notes (grader `GraderClient` seam, `GraderVerdict {pass, matched_expected, rationale}`, tiered-fixture shape) and decision `008` (tiered n10→n30).
  - Load `typescript-clean-code` for naming/commenting discipline (zero obvious comments), applied to Python.

**Execution:**
- [x] `src/freecad_buddy/hosts/tool_catalog.py` -- add a read-only assistant profile selector (explicit allow-list → `MethodRegistry` with zero geometry-mutation tools) reusing existing specs + `build_inline_handlers`; no change to existing specs. -- read-only profile (AC1/G1.6).
- [x] `benchmarks/harness/actor.py` -- add the `Backend` protocol + actor-loop primitives (shared with 2.3) driving a question→final answer over the read-only registry; benchmarks/ non-ring tooling beside `harness/stats.py` (imports `hosts/tool_catalog` profile builder — cannot live in `adapters/`). -- actor surface (AC1).
- [x] `benchmarks/g1/actor_run.py` -- G1 actor-run harness: run each eval + broken-doc case ×R=3 through the profile, grade via the 2.1 `DeterministicGrader`, apply tiered n10→n30 escalation, emit one `ValidationReport` per case×repeat with majority-of-R + Wilson CI; live backend gated, absent→skip. -- eval + diagnosis run + escalation (AC1/AC2).
- [x] `benchmarks/g1/gate.yaml` -- set `actor:` to the real Claude-backend descriptor (≠ grader model; NFR1 preflight stays green); leave grader/tokens/heldout intact. -- actor pin (AC1).
- [x] `benchmarks/runner.py` -- add the `--actor-run` non-stub path for `--gate G1` (build profile, resolve backend, invoke `actor_run.py`, emit reports); preserve `--stub` + actor≠grader preflight. -- runner actor path (AC1/AC2).
- [x] `tests/external/test_assistant_readonly_profile.py` -- assert the profile is exactly the read-only allow-list and registers zero geometry-mutation tools (`feature_*`/`sketch_*`/`preview_*`/`document_save`/`document_create`/`debug_exec` absent). -- G1.6 read-only guarantee.
- [x] `tests/external/test_actor_run_g1.py` -- with a `ScriptedBackend`, cover I/O matrix rows: correct→OK, confident-wrong→SPEC_FAILED, escalation table (8/10 no-escalate, 10/10→30, 6/10 fail), malformed answer→typed fail, live-absent→skip, summarized-tree used (assert recorded calls). -- actor-run behaviour (AC1/AC2).
- [x] `.github/workflows/ci.yml` -- `arch-checks`: run the offline scripted-backend actor-run + the read-only-profile test; confirm the live eval is skipped; add no key/secret/network. -- CI-enforced offline coverage.
- [x] `docs/decisions/010-claude-backend-live-eval-out-of-ci.md` -- record the Claude-backend-is-MCP-client + live-eval-operator-gated decision + reuse survey. -- decision artifact.

**Final Task: Quality Checks**
- [x] `uv run python scripts/check_imports.py` -- rings clean (harness/actor/backend external; import contracts only).
- [x] `uv run ruff check <story files>` -- clean (repo-wide `.` red on pre-existing E501 in untouched files — deferred).
- [x] `uv run pytest tests/external -q` -- all green (profile + actor-run offline + prior suites).
- [x] `"FreeCADCmd" tests/run_tests.py` -- prior infc suites stay green (no in-FreeCAD change expected).

**Acceptance Criteria:**
- Given the Phase-1 assistant profile, when its registered tool surface is enumerated, then it contains zero geometry-mutation tools and exactly the read-only allow-list (`query_*` + read-only `verify_*` + non-mutating document lifecycle) — G1.6 holds and is proven by the profile test.
- Given the offline scripted-backend actor-run over `benchmarks/g1/`, when `benchmarks/runner.py --gate G1 --actor-run` executes, then each eval + broken-doc case is graded by the independent 2.1 grader (never the actor), the tiered n10→n30 escalation fires exactly per decision 008 (pass at n=10 ≥8/10, escalate only on 10/10), summarized-tree queries are used (not raw dumps), and one schema-valid `ValidationReport` per case×repeat is emitted with a Wilson CI.
- Given no operator-supplied backend/key, when the actor-run runs in unattended CI, then the live eval is skipped (not silently green, not errored), the offline deterministic coverage still runs, and no API key/secret ever enters CI.

## Spec Change Log

_No bad_spec loopback occurred. The review pass produced only patches + one defer; the `<intent-contract>` was never amended._

## Review Triage Log

### 2026-07-24 — Follow-up review pass (iteration 0)
- intent_gap: 0
- bad_spec: 0
- patch: 2: (high 0, medium 1, low 1)
- defer: 1
- reject: 10
- addressed_findings:
  - `[low]` `[patch]` The read-only-profile source comment claimed `document_open`/`close`/`list` all carry `mutating=True`, but `document_list` is `mutating=False` in the catalog. Corrected the comment to `document_open`/`close` (the test set was already right).
  - `[medium]` `[patch]` The "one ValidationReport per case×repeat" contract had no count assertion — only per-report verdicts/schema were checked, so a per-repeat drop/duplication would pass green. Added `len(result.reports) == 10*3` (n10-only) and `== 30*3` (escalated) assertions to the escalation tests.

### 2026-07-24 — Review pass (iteration 0)
- intent_gap: 0
- bad_spec: 0
- patch: 8: (high 1, medium 6, low 1)
- defer: 1
- reject: 3
- addressed_findings:
  - `[high]` `[patch]` `N10_PASS_THRESHOLD` (≥8/10) was defined but never used — the actor-run exit code and summary were all-or-nothing, so an honest live 8–9/10 tier pass (or 24–29/30) would have reported FAIL. Added a `passed` flag to `TierResult` (n10 ≥8/10; escalated n30 ≥80%), drove the exit code + summary off the tier verdict.
  - `[medium]` `[patch]` The real `build_readonly_profile` (the function enforcing G1.6 on the production registry) had zero test coverage — offline used a parallel stub. Added a test that builds the real profile and asserts it equals the allow-list with no mutation tool.
  - `[medium]` `[patch]` The geometry-mutation exclusion test was vacuous (no assertion the mutation tools exist in the catalog). Added a pin that every name in the absence set is a real catalog tool.
  - `[medium]` `[patch]` A broken-doc case with a missing/mistyped `tier` was silently dropped from both tiers. `_load_broken_cases` now raises on invalid tier, empty set, malformed case, and duplicate id.
  - `[medium]` `[patch]` A blank expected-object / empty cause-keyword fixture made the grader raise `ValueError`, crashing the whole run instead of a typed fail. Wrapped the grade call to a typed fail verdict.
  - `[medium]` `[patch]` `FREECAD_BUDDY_G1_ACTOR_BACKEND=1`/`true` (operator intending live) silently ran the offline scripted double — a fake green. Hardened: any non-empty value that is not the explicit `offline` opt-in hard-fails exit 2.
  - `[medium]` `[patch]` The n10 count was hardcoded to 10 with no guard; the majority-of-R tie boundary (2/3) was untested. Added a data-driven `!= 10` guard and 2/3-pass / 1/3-fail tie-boundary tests.
  - `[low]` `[patch]` Four read-only (`mutating=False`) tools (`query_screenshot`, `verify_export_*`) were excluded from the profile with no rationale and no test. Documented why (export verifiers need a prior export; screenshot not needed under the latency budget) and pinned the full read-only-surface partition.
  - Also inverted the raw-dump `_tree`-suffix heuristic to an allow-list check (any off-profile call flags), so a differently-named dump cannot evade it.

## Design Notes

- **Why the profile is an explicit allow-list, not `mutating=False`.** `document_open`/`close`/`list` carry `mutating=True` in the catalog (they open/close docs), but they perform no *geometry* mutation and the assistant needs `document_open` to load the fixture it answers about. A naive `mutating=False` filter would strip `document_open` and leave the assistant unable to read any doc. G1.6's "zero mutation tools" is the geometry/model-mutation set (`sketch_*`, `feature_*`, `preview_*`, `document_create`, `document_save`, `debug_exec`). So the read-only profile is an **explicit read-only allow-list**, and the G1.6 test asserts the absence of the geometry-mutation set rather than `all(not mutating)`. If a reviewer reads G1.6 as literally "no `mutating=True` spec," that is a spec-vs-contract question to surface, not silently resolve.
- **The Claude backend is the MCP client, not a bespoke SDK actor.** Per `integration-mcp-clients.md` §2/§6 the "Claude backend" is Claude Code / Claude Desktop driving the registered tools over MCP. This story builds the read-only *profile* those clients register and the *harness* that runs the eval through a `Backend`; it does not hand-roll an Anthropic SDK agent loop. A live run is an operator wiring the bridge into Claude Code and running the eval — reproducible, but not an unattended-CI artifact.
- **Live eval is operator-gated, CI-tests are offline — mirrors 2.1's discipline.** 2.1 shipped a *deterministic* grader precisely so the entry gate is reproducible in CI without secrets/network (harness-design §6: keys are human-only). The same constraint binds the actor: a live Claude eval needs an API-capable backend + key, which cannot be an unattended-CI green. So CI exercises the profile, the escalation logic, the grader wiring, and the report shape against a `ScriptedBackend` double; the ≥80% pass-rate (AC1 says "*trends toward*" — the hard gate is Story 2.4 exit) is a *measured operator run*, not asserted by a green job. This is the honest reading that lets the story land green unattended without faking numbers.
- **`GraderVerdict` mapping.** Reuse 2.1's `DeterministicGrader` via the `GraderClient` seam: `grade(question, final_answer, rubric, expected)` → `{pass_, matched_expected, rationale}`. The harness maps `pass_=True`→check passed→`OK`; `pass_=False`→`SPEC_FAILED`. No new grader, no `contracts/` type — the actor-run builds the same `ValidationReport` the stub path does.

## Verification

**Commands:**
- `uv run python benchmarks/runner.py --gate G1 --actor-run` -- expected (offline scripted backend): per-case reports emitted, escalation applied, exit 0 when the scripted answers pass; live eval skipped when no operator backend.
- `uv run python benchmarks/runner.py --gate G1 --stub` -- expected: unchanged from 2.1 — every criterion `INVALID_INPUT`, exit 1 (regression guard).
- `uv run pytest tests/external/test_assistant_readonly_profile.py tests/external/test_actor_run_g1.py -q` -- expected: all pass.
- `uv run python scripts/check_imports.py` -- expected: exit 0 (harness/actor/backend outside rings; contracts-only imports).
- `uv run ruff check <story files>` -- expected: clean. (Repo-wide `ruff check .` is red on 10 pre-existing E501 in `scripts/automation/*` + `tests/external/test_check_imports.py`, unrelated to this story — deferred.)
- `uv run pytest tests/external -q` -- expected: all pass (new + prior suites).

**Manual checks:**
- Enumerate the assistant profile registry and confirm zero geometry-mutation tools + the exact read-only allow-list.
- Confirm `benchmarks/g1/gate.yaml` `actor:` ≠ `grader:` model (NFR1 preflight green) and grader/tokens/heldout blocks unchanged.

## Auto Run Result

### 2026-07-24 — Follow-up review pass

**Change under review:** Story 2.2 — read-only assistant profile (G1.6) + G1 actor-run harness (tiered n10→n30 escalation, deterministic grader wiring, offline scripted backend, live eval operator-gated/CI-skipped). Follow-up review of the already-`done` story (`followup_review_recommended: true`).

**Files changed this pass:**
- `src/freecad_buddy/hosts/tool_catalog.py` — corrected the profile source comment: `document_list` is `mutating=False`, not `mutating=True` (only `document_open`/`close` are mutating lifecycle).
- `tests/external/test_actor_run_g1.py` — added `len(result.reports)` assertions (30 for n10-only, 90 for escalated) to verify the "one ValidationReport per case×repeat" contract.
- `_bmad-output/implementation-artifacts/deferred-work.md` — one new defer entry (malformed-fixture INVALID_INPUT classification).

**Review findings breakdown:** 2 patches applied (1 medium: report-count coverage gap; 1 low: comment factual error), 1 deferred (malformed-fixture grade classification), 10 rejected (impossible-scenario input hardening on provenance-manifested fixtures; off-profile-guard live-actor limitation that the registry surface already enforces structurally; scripted-double green-by-construction and n=30-includes-n10 statistic, both by-design per decision 008; misleading `--case`/`--criterion` CLI messaging, cosmetic; "vacuous G1.6" — false: the real existing mutation set is pinned by `test_geometry_mutation_tools_exist_in_catalog`).

**Verification performed (all green):**
- `uv run pytest tests/external/test_actor_run_g1.py tests/external/test_assistant_readonly_profile.py -q` → 23 passed.
- `uv run python benchmarks/runner.py --gate G1 --actor-run` → offline scripted backend, live eval skipped, 10/10 → escalated n=30 30/30, 90 reports, exit 0.
- `uv run ruff check` (changed files) → All checks passed.
- `uv run python scripts/check_imports.py` → check_imports OK.

**Residual risks:** The offline CI actor-run only ever exercises the all-pass/escalate branch (scripted answers are synthesized from `expected`); the fail-exit branches live only in pytest, never in the shipped `runner.py --actor-run` gate job. The live ≥80% figure remains a measured operator run, not CI-asserted (by design, decision 010). One low-consequence defer logged (DW). No behavior/API/security/data change this pass.
