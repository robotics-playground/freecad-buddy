---
title: 'Story 2.3 — Local Backend + ReAct Fallback Adapter'
type: 'feature'
created: '2026-07-24'
status: 'done'
baseline_revision: '6a11855eaa06c53f233cbb1ca3910537fe1caca7'
final_revision: '5883d9a'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-2-2-assistant-claude-backend.md'
warnings: [oversized]
---

<intent-contract>

## Intent

**Problem:** Story 2.2 landed the read-only assistant profile (G1.6) + the G1 actor-run harness (`Backend` protocol, tiered n10→n30 escalation, deterministic grader, offline `ScriptedBackend`) and proved the bridge model-agnostic on ONE backend (Claude-as-MCP-client). G1.4 requires the *same* eval run to complete through the *identical* tool surface on a **second** backend — a fully local model (llama.cpp + Qwen3-30B-A3B over HTTP) — AND through a **ReAct text-parse adapter** driving any OpenAI-compatible endpoint over the same tool registry. Neither exists: there is no ReAct adapter, and `gate.yaml` has no second actor descriptor.

**Approach:** Build a ring-pure **ReAct adapter** in `adapters/` (in-process, no MCP transport per clients-design §3.3): it renders the read-only tools' names + JSON input schemas (injected from `contracts/`-owned schemas, single source of truth) into a system prompt, runs the ReAct loop (model emits a fenced JSON tool-call block → adapter parses → dispatches through the same tool registry → appends the `ResultEnvelope` text mirror → repeats until a final answer), and enforces the parser/safety contract (malformed JSON → one structured re-prompt → typed `INVALID_INPUT`; question-instead-of-tool → one re-prompt; confirmation posture = no-elicitation matrix row, fail-closed/token). The chat-completion transport is an **injected callable** so the adapter carries no HTTP dep and CI drives it against a scripted chat double offline. A thin `benchmarks/` `Backend` wrapper plugs the adapter into the 2.2 actor-run so `runner.py --gate G1 --actor-run` proves G1.4 through the ReAct path. The live local (llama.cpp) run is **operator-gated + CI-skipped** exactly as 2.2's live Claude run — the pinned model + constrained-decoding config is documented, not asserted by an unattended green.

## Boundaries & Constraints

**Always:**
- Ring purity (AD-1/AD-12): the ReAct adapter lives in `adapters/`, imports **contracts + stdlib only** — never `hosts/` (`check_imports.py` forbids `adapters → hosts`). Tool schemas + descriptions + the dispatch callable + the chat-completion callable are all **injected**, not imported from `hosts/tool_catalog`. Any live HTTP/model client is external-only + optional, never an in-FreeCAD import.
- Same tool surface as production (G1.4, clients-design §3.3): the adapter dispatches through the **same read-only `MethodRegistry`** the FastMCP server + the 2.2 actor use — never a private code path, never a mutation tool.
- Parser contract (clients-design §3.3): scan model text for a fenced JSON object matching the tool-call shape `{tool, args}`; malformed JSON → **one** structured re-prompt, then typed `INVALID_INPUT` (a `ResultEnvelope` from `contracts`) — never a silent retry loop. Question-detector: if the model asks the user instead of calling a tool, re-prompt **once** to use a tool.
- Confirmation posture (clients-design §4 no-elicitation row): fail-closed / token fallback. No mutations exist in Phase 1, but the adapter's posture must already be correct so it holds when mutations arrive in Epic 3 — the adapter never issues an elicitation and never fabricates a confirm.
- Schemas from `contracts/` single source of truth: the prompt renders each tool's `input_schema` (the same dict `mcp_server.registered_tools` surfaces), never a hand-authored copy.
- No self-grading (AD-13): the ReAct backend is an **actor**; grading stays with the 2.1 deterministic grader via the existing `GraderClient` seam. The gate `actor:` descriptor for this backend must resolve to a model id `≠` the grader's (NFR1 preflight stays green).
- Conventional Commits; no AI attribution. Never commit without approval **except** the pre-approved per-story bmad-loop commit to the current branch.

**Block If:**
- Placing the ReAct adapter ring-pure would require importing `hosts/` (e.g. tool schemas cannot be injected and must be imported from `tool_catalog`) — that is an AD-1/AD-12 contradiction; stop, cite `check_imports.py` + component-design, do not silently place it in `hosts/` or weaken the ring rule.
- Landing green unattended would require a live model endpoint, API key, GPU, or a downloaded GGUF in CI — that violates harness-design §6 (secrets/hardware human-only, mirrors 2.2 decision 010). HALT rather than wire a live-model CI path.
- The identical-surface requirement cannot hold because a read-only tool's `input_schema` is unrenderable into the ReAct prompt without a mutation/private path — surface it, do not diverge.

**Never:**
- Never run the live local (llama.cpp/Qwen) eval in unattended CI or fake its pass-rate; the G1.4 re-run figure is a *measured operator run*, not a green job.
- Never add an OpenAI/Anthropic SDK or HTTP client as a required (non-optional) dep, and never import it inside FreeCAD-process code.
- Never route the adapter through anything but the injected read-only registry; never register or call a geometry-mutation tool.
- Not in scope: the sealed held-out exit run + human tokens (Story 2.4); skills authoring (Epic 6); constrained-decoding grammar files for the native-MCP local path (that is llama-server config, operator-owned, documented not coded); any model-backed grader.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Well-formed tool call | Model emits one fenced ```json {tool, args}``` block | Adapter parses, dispatches through the read-only registry, appends the `ResultEnvelope.text` mirror to the transcript, loops | n/a |
| Final answer emitted | Model emits prose with no tool-call block | Loop ends; `AnswerResult.final_answer` = the prose, `tool_calls` = recorded dispatches | n/a |
| Malformed JSON tool call | Fenced block present but unparseable / missing `tool` | **One** structured re-prompt ("your tool call was malformed, resend valid JSON"); if still malformed → typed `INVALID_INPUT` envelope, loop terminates, `final_answer=None` | typed `INVALID_INPUT`, never a silent retry loop |
| Question to user instead of tool | Model asks the user a question, no tool call | **One** re-prompt to use a tool; if it repeats → treated as no-final-answer typed fail | one re-prompt then typed fail |
| Off-profile / unknown tool named | Model names a tool not in the read-only allow-list | Registry `dispatch` returns `INVALID_INPUT` (unknown method); mirror appended, loop continues (model can recover) | typed `INVALID_INPUT` from registry |
| Max iterations reached | Loop exceeds a bounded step cap without a final answer | Terminate with `final_answer=None` (harness grades as `SPEC_FAILED`), never an infinite loop | bounded cap, typed no-answer |
| Offline scripted chat double | CI: `ChatCompletion` callable replays recorded turns | Adapter drives loop deterministically end-to-end; grader + escalation + reports build with no network | n/a |
| Actor-run over ReAct backend | `runner.py --gate G1 --actor-run` with ReAct backend | Per-case `ValidationReport`s emitted through the identical surface; summarized-tree used, no raw dump | n/a |
| Live local backend absent in CI | No endpoint/key/GGUF | ReAct backend runs against the scripted double; the *live local* leg is skipped, explicit + logged, never silently green | skip is explicit, not error |

</intent-contract>

## Code Map

- `src/freecad_buddy/adapters/react_adapter.py` -- **new**: ring-pure ReAct adapter. Exposes a `ReactAdapter` (or `react_answer(...)`) that, given injected `tool_schemas: dict[str, dict]`, `tool_descriptions: dict[str, str]`, a `chat: ChatCompletion` callable (protocol: takes the running message list → returns assistant text), and a `dispatch: Callable[[str, dict], dict]` (a `ToolInvoker`), builds the system prompt from the schemas, runs the ReAct loop, parses fenced JSON tool calls, dispatches, appends the `ResultEnvelope` text mirror, handles malformed-JSON (one re-prompt → typed terminal `INVALID_INPUT` **surfaced on the result**) + question-detector (one re-prompt), and returns a final answer + recorded tool calls. `ReactResult` carries `final_answer: str | None`, `tool_calls`, and `error: ResultEnvelope | None` (the malformed-terminal envelope, else `None`) — the malformed envelope must be observable, not built-and-dropped. A well-formed block naming an **unknown/off-profile** tool is dispatched through the registry (typed `INVALID_INPUT` mirror appended) and the loop **continues** (the I/O-matrix recovery row), NOT routed to the terminal malformed path. Imports `contracts` (envelope/status helpers for the typed `INVALID_INPUT`) + stdlib (`json`, `re`) ONLY. No HTTP dep.
- `src/freecad_buddy/adapters/mcp_server.py` -- reference only for how a tool's `input_schema`/`outputSchema` is surfaced (`registered_tools`/`_tool_for`); the ReAct prompt renders the same `input_schema` dict. No change.
- `benchmarks/harness/react_backend.py` -- **new**: a `Backend` (2.2 `harness/actor.py` protocol) wrapper adapting `ReactAdapter` to `answer(case_id, question, tools, invoke)`. Builds the injected `tool_schemas` from `tool_specs()` filtered to the read-only allow-list (this module is `benchmarks/` non-ring tooling and MAY import `hosts/tool_catalog`, like `harness/actor.py`), wires the adapter's `dispatch` to the actor's `invoke`, and passes a `chat` callable (the scripted double offline; a live OpenAI-compatible client when operator-supplied). A `ScriptedChat` test double replays recorded assistant turns per case.
- `benchmarks/g1/gate.yaml` -- add a **second actor descriptor** for the local/ReAct backend (e.g. `actor_local:` or an `actors:` list entry) with a model id `≠` the grader's (NFR1 preflight stays green). Leave the 2.2 Claude `actor:`, the `grader:`, tokens, and `verdict.heldout: sealed` intact.
- `benchmarks/runner.py` -- extend the `--actor-run` path so `--gate G1` can select the ReAct/local backend (e.g. an existing/new flag or the `FREECAD_BUDDY_G1_ACTOR_BACKEND` env respected exactly as 2.2: unset/`offline` → scripted; any other non-empty → operator-gated hard-fail in CI). Build the ReAct `Backend` (scripted chat offline) and run `run_actor_eval` unchanged. Preserve `--stub` honest-fail. **Extend `_preflight_actor_grader`** so it collision-checks the grader model against EVERY actor descriptor — the existing `actor:` AND the new `actor_local:` (generalise to all `actor*` keys / an `actors:` list) — not just `actor:`. Otherwise `actor_local.model == grader.model` slips past the NFR1 guard and self-grading leaks. Add a test that a gate whose `actor_local.model` collides with `grader.model` hard-fails exit 2.
- `tests/external/test_react_adapter.py` -- **new**: pytest — the adapter contract against a `ScriptedChat`: well-formed call dispatches + mirror appended; final-answer ends the loop; malformed JSON → one re-prompt then `INVALID_INPUT` (assert exactly one re-prompt, typed status); question-to-user → one re-prompt; max-iteration cap → `final_answer=None`; schemas rendered into the system prompt come from the injected dict (assert the prompt contains each tool name + a schema property).
- `tests/external/test_react_backend_actor_run.py` -- **new**: pytest — the ReAct `Backend` drives the 2.2 actor-run offline: identical read-only surface (assert `tool_calls` ⊆ allow-list, `query_tree_summary` used not a raw dump), per-case `ValidationReport`s emitted, tiered escalation fires via the shared `run_actor_eval`, live-local absent → scripted (skip is explicit).
- `.github/workflows/ci.yml` -- `arch-checks`: run the offline ReAct adapter + ReAct-backend actor-run tests; confirm the live local eval is skipped; add no key/secret/network/GGUF step.
- `pyproject.toml` -- no new required dep; any live OpenAI-compatible client stays external-only + optional (`[project.optional-dependencies]`); confirm ring/import checks stay green.
- `docs/decisions/011-react-adapter-injected-transport-local-eval-out-of-ci.md` -- **new** decision note: ReAct adapter is ring-pure with an injected chat-completion transport (why no SDK dep, how schemas come from `contracts` not `hosts`); the local llama.cpp/Qwen live eval is operator-gated + CI-skipped (mirrors decision 010); the reuse survey (existing ReAct/agent libs vs a stdlib parse loop) and why G1.4's re-run number is a measured operator run.

## Tasks & Acceptance

**Pre-Work: Load Standards and Skills (MANDATORY — re-execute at every stage, do NOT mark done)**
  - Read `.knowledge-base/technical/standards/index.md` and `.knowledge-base/technical/application-design/index.md` (language-agnostic rules; Python ring).
  - Re-read `integration-mcp-clients.md` §3.3 (ReAct adapter contract: prompt build, loop, parser, question-detector, safety parity), §3.1–3.2 (local stack + constrained decoding), §4 (confirmation matrix no-elicitation row), §6 (backend capability matrix), §7 (latency / summarized-tree).
  - Re-read `project-context.md` "Architecture Ring & Import Rules" (adapters may not import hosts; in-FreeCAD zero third-party), "Verification & Validation Discipline" (actor never grades itself), "Wire & Schema Rules" (closed status set; tool names underscore; `ResultEnvelope.text` server-derived).
  - Re-read Story 2.2's spec Code Map + Design Notes (`Backend` protocol, `Actor`, `ScriptedBackend`, `run_actor_eval`, the offline env-var discipline, live-eval-operator-gated pattern) and decision `010`.
  - Load `typescript-clean-code` for naming/commenting discipline (zero obvious comments), applied to Python.

**Execution:**
- [x] `src/freecad_buddy/adapters/react_adapter.py` -- add the ring-pure `ReactAdapter` (injected `tool_schemas`/`descriptions`/`chat`/`dispatch`): system-prompt render from schemas, ReAct loop, fenced-JSON parse, dispatch + `ResultEnvelope.text` mirror, malformed→one re-prompt→typed terminal `INVALID_INPUT` **surfaced as `ReactResult.error`**, unknown/off-profile tool → dispatch through registry + mirror + **loop continues** (not terminal), question-detector one re-prompt, bounded iteration cap; contracts + stdlib imports only. -- ReAct model-agnostic path (AC2). `_parse_tool_call` no longer consults the allow-list; `ReactResult.error` set on the malformed-twice branch.
- [x] `benchmarks/harness/react_backend.py` -- add the `Backend` wrapper adapting `ReactAdapter` to `answer(...)`, building read-only `tool_schemas` from `tool_specs()`∩allow-list, wiring `dispatch`→actor `invoke`, injecting the `chat` callable (scripted offline / live operator); add a `ScriptedChat` double. -- backend seam driving the identical surface (AC1/AC2).
- [x] `benchmarks/g1/gate.yaml` -- add the second (local/ReAct) actor descriptor, model id ≠ grader; leave Claude actor/grader/tokens/heldout intact. -- second-backend pin (AC1). `actor_local.model: llama-qwen3-30b-a3b`.
- [x] `benchmarks/runner.py` -- extend `--actor-run` for `--gate G1` to select the ReAct backend (scripted offline; operator-gated live per the 2.2 env-var discipline), run `run_actor_eval`; preserve `--stub`; **generalise `_preflight_actor_grader` to collision-check the grader against every actor descriptor (`actor:` + `actor_local:`), not just `actor:`**. -- runner ReAct path + NFR1 preflight (AC1/AC2). New `_actor_descriptors` iterates all `actor*` keys + `actors:` list.
- [x] `tests/external/test_react_adapter.py` -- cover the I/O matrix rows against a `ScriptedChat`: well-formed→dispatch+mirror, final-answer→loop end, malformed→one re-prompt then terminal `INVALID_INPUT` **asserted via `ReactResult.error`**, unknown/off-profile tool→dispatch+mirror+**loop continues** (recovery), question→one re-prompt, max-iter→None, prompt renders injected schemas, **no geometry-mutation tool in the prompt built from the REAL `readonly_tool_schemas()`** (not a synthetic stub). Also add a runner/preflight test that an `actor_local.model == grader.model` gate hard-fails exit 2. -- adapter contract + NFR1 (AC2).
- [x] `tests/external/test_react_backend_actor_run.py` -- ReAct `Backend` over the 2.2 actor-run: identical surface (tool_calls ⊆ allow-list, summarized-tree used), reports emitted, escalation fires, live-local absent→scripted. -- G1.4 identical-surface proof offline (AC1).
- [x] `.github/workflows/ci.yml` -- `arch-checks`: run the offline ReAct adapter + ReAct-backend actor-run tests; confirm live local eval skipped; add no key/secret/network/GGUF. -- CI-enforced offline coverage.
- [x] `docs/decisions/011-react-adapter-injected-transport-local-eval-out-of-ci.md` -- record injected-transport ring-purity + local-eval-operator-gated + reuse survey; state the malformed→`INVALID_INPUT` is the adapter's client-contract return (`ReactResult.error`), separate from the 2.2 eval's `SPEC_FAILED` no-answer verdict. -- decision artifact.

**Final Task: Quality Checks**
- [x] `uv run python scripts/check_imports.py` -- `check_imports OK` (react_adapter contracts+stdlib only; react_backend in benchmarks/ imports hosts).
- [x] `uv run ruff check` (story files) -- `All checks passed!`.
- [x] `uv run pytest tests/external -q` -- 285 passed (4 pre-existing trimesh warnings unrelated).
- [ ] `"FreeCADCmd" tests/run_tests.py` -- not run: no FreeCAD in env + no in-FreeCAD code changed (react_adapter is external-process adapter, react_backend is benchmarks tooling). Prior infc suites unaffected.

**Acceptance Criteria:**
- Given the pinned local stack (llama.cpp + Qwen3-30B-A3B, constrained decoding ON) OR the ReAct adapter against an OpenAI-compatible endpoint, when the G1.1 sample re-runs, then it completes through the **identical read-only tool surface** the 2.2 actor uses (same `MethodRegistry`, zero mutation tools) — proven offline by the ReAct `Backend` actor-run, and documented as an operator-gated live run for the local model (never faked in CI).
- Given the ReAct adapter (in `adapters/`, same tool registry, schemas injected from `contracts/`), when a model emits tool calls, then well-formed fenced-JSON calls parse and dispatch, malformed JSON triggers exactly one structured re-prompt then a typed `INVALID_INPUT` (never a silent retry loop), a question-to-user triggers one re-prompt, and the confirmation posture is fail-closed/token (no elicitation) — matching the no-elicitation matrix row.
- Given no operator-supplied local endpoint/key/GGUF, when the actor-run runs in unattended CI, then the ReAct backend runs against the scripted chat double, the live local eval is skipped (explicit + logged, not silently green, not errored), and no key/secret/GGUF ever enters CI.

## Spec Change Log

### 2026-07-24 — bad_spec loopback (iteration 1)

- **Triggering findings:**
  1. The I/O matrix "Off-profile / unknown tool named" row said "dispatch returns `INVALID_INPUT`, mirror appended, loop continues (model can recover)", but the Code Map/Design Notes did not distinguish *unknown-tool* from *malformed-JSON*, so the first implementation routed an unknown/off-profile tool name into the **terminal** malformed path (one re-prompt → typed `INVALID_INPUT`, loop ends) — contradicting the matrix and denying the model its recovery turn.
  2. Design Notes claimed the malformed path's typed `INVALID_INPUT` envelope is such that "a report built from this envelope classifies as `INVALID_INPUT`". Impossible against the already-`done` 2.2 harness (`actor_run._build_case_report` maps a `None` answer to `spec_failed.no_final_answer` → `SPEC_FAILED`). The implementation consequently built `_malformed_envelope` and dropped it (dead append) — the "typed" status was never observable to any caller.
  3. Spec repeated "zero mutation tools" loosely; the real `READ_ONLY_PROFILE` deliberately includes `document_open`/`document_close` (`mutating=True`, geometry-inert). The mutation-absence test was written against a synthetic 2-tool stub and proved nothing.
  4. Spec said the "actor≠grader preflight" applies but named no mechanism; `_preflight_actor_grader` only reads the `actor:` key, so the new `actor_local:` model was never collision-checked against the grader (NFR1 hole).
- **Amended (all OUTSIDE `<intent-contract>`):** Code Map (adapter `ReactResult.error` surfaces the malformed envelope; unknown-tool dispatched through registry + loop continues; runner preflight generalised to all actor descriptors); Design Notes (rewrote the `INVALID_INPUT` note to separate the adapter *client-contract return* from the 2.2 *eval verdict*; added an explicit unknown-tool-vs-malformed note; added a "zero GEOMETRY-mutation" note mirroring 2.2); Tasks (adapter surfaces `error` + unknown-tool recovery; runner preflight over all actors + collision test; adapter test asserts `ReactResult.error`, unknown-tool recovery, and mutation-absence against the REAL `readonly_tool_schemas()`; decision-011 states the layering).
- **Known-bad state avoided:** an unknown tool typo aborting a whole answer; a "typed `INVALID_INPUT`" that no caller can observe (built-and-dropped); a vacuous G1.6 mutation test; an NFR1 self-grading leak via `actor_local`.
- **KEEP (must survive re-derivation):** ring-pure adapter (contracts+stdlib, injected `chat`/`dispatch`/`schemas`) with `check_imports` clean; `benchmarks/harness/react_backend.py` composing schemas from `hosts/tool_catalog` (the only place allowed to import hosts) + `ScriptedChat` double; the offline env-gate discipline (`FREECAD_BUDDY_G1_ACTOR_BACKEND` unset/`offline`→scripted, any other non-empty→exit-2 hard-fail) with no secrets/GGUF in CI; escalation via the **unchanged** shared `run_actor_eval` (10/10→n30, 90 reports); `--stub` honest-fail exit 1 unchanged; `actor_local` descriptor with model≠grader; bounded iteration cap + one-reprompt discipline + last-fenced-block parse; `_malformed_envelope`'s server-derived `text` mirror via the contracts helper.

## Review Triage Log

### 2026-07-24 — Follow-up review pass (fresh, iteration reset to 0)
- intent_gap: 0
- bad_spec: 0
- patch: 0
- defer: 1
- reject: 15
- addressed_findings:
  - none
- notes: Parallel Blind Hunter + Edge Case Hunter over the full baseline diff (`6a11855..working`). No new caused-by-this-change defect. The two reviewers' "highest-priority" items were adjudicated against real source and rejected: (1) `ReactBackend.answer` returning `tool_calls=[]` is NOT an accidental off-profile-guard bypass — `Actor.run` records every dispatch through its own `invoke` wrapper (`actor.py:82-91`), identical to the settled `ScriptedBackend` pattern; (2) `ReactResult.error` dropped by the backend is by-design — `AnswerResult` has no `error` field and the spec/decision-011 explicitly separate the adapter's client-contract `error` (asserted by adapter unit tests) from the eval's `SPEC_FAILED` no-answer verdict; (3) the malformed-detail/non-str-chat AttributeError/TypeError paths are unreachable through the only dispatch seam (`MethodRegistry.dispatch` always returns a well-formed closed-status envelope) and the live chat wrapper is operator bring-your-own — guarding them is defending against impossible states (CLAUDE.md §2). One genuine finding deferred (pre-existing, not caused here): the `FREECAD_BUDDY_G1_ACTOR_BACKEND=live` doc/code contradiction (docstrings say `=live` wires a live backend; runner hard-fails on any non-`offline` value) — present at the 2.2 baseline, only its error message was reworded this story. Remaining 14 (uniform scripted turns, `cause_keywords[0]` double authoring, `openai>=1` unbounded optional extra, CI-step isolation naming, `_is_question` "?"-heuristic, iteration-cap-vs-error, empty-tool-name recovery, independent re-prompt budgets, double case-load, final-answer-with-json-block, malformed/question interleave) rejected as noise/by-design/prior-rejected. Verify re-run green: `check_imports OK`, ruff clean on story files, 19/19 new external tests pass.

### 2026-07-24 — Review pass (iteration 1, post-loopback)
- intent_gap: 0
- bad_spec: 0
- patch: 5: (high 0, medium 3, low 2)
- defer: 1
- reject: 12
- addressed_findings:
  - `[medium]` `[patch]` The geometry-mutation-absence test padded its set with `sketch_*`/`feature_*`/`preview_*` names that do not exist in the Phase-1 catalog (5/8 assertions trivially true) and missed the real excluded mutating tool. Now derives `{s.name for s in tool_specs() if s.mutating} - READ_ONLY_PROFILE` dynamically (breaks if a real mutating tool is ever added to the profile) and asserts that plus the static set.
  - `[medium]` `[patch]` On an unknown/failed dispatch the adapter appended only the registry's empty `"{}"` text mirror, dropping `detail.message`, so the advertised "model can recover" turn carried no failure signal. Added `_dispatch_mirror`: on a non-OK status it prepends `[STATUS] detail.message`. New `test_failed_dispatch_mirror_carries_recovery_signal` pins it (unknown-method envelope → mirror carries `INVALID_INPUT` + `unknown method: bogus_tool`, loop recovers to a final answer).
  - `[medium]` `[patch]` `_preflight_actor_grader` silently skipped a scalar-shaped `actor*`/`actors[]` entry (NFR1 self-grading leak for a malformed descriptor) and would spuriously hard-fail when grader+actor both omit `model` (`None==None`). `_actor_descriptors` now raises `UsageError` on a non-dict actor entry; the preflight returns inert when `grader.model` is absent. Three new guard tests.
  - `[low]` `[patch]` A live OpenAI-compatible endpoint returning `content: null` would crash the loop (`re.findall(None)`). Guarded with `self._chat(messages) or ""`.
  - `[low]` `[patch]` `envelope["text"]` KeyError on a generic dispatch seam lacking a `text` key. `_dispatch_mirror` uses `.get("text", "")`.
  - Deferred (1): the fail-closed/no-elicitation confirmation posture (AC2) holds structurally (the adapter has no elicitation code path in Phase 1) but is not pinned by a test asserting the adapter emits only system/user/assistant roles — worth a guard before mutations land in Epic 3.
  - Rejected (12, noise/by-design/prior-rejected): `_is_question` "?"-heuristic (diagnoses rarely bare-`?`; prompt forbids questions); ScriptedChat exhaustion `""`→wrong_diagnosis (offline-double authoring); `detail.code` dotted-subcode "divergence" (the dotted form is the correct `derive_verdict` convention, not a bug); `ReactBackend.answer` ignores `tools` param / schema-registry drift (both derive from the provenance-fixed `READ_ONLY_PROFILE`); collision-test substring couples to key order (test passes, low); `react-local` extra ships no wrapper (bring-your-own per decision 011); three-terminal-causes-only-malformed-observable (by design — spec surfaces only the malformed envelope); fence-tag case-sensitivity (prompt instructs lowercase `json`; accepted limitation); the two live-seam `content=None`/missing-`text` items beyond the guards already added.

### 2026-07-24 — Review pass (iteration 0)
- intent_gap: 0
- bad_spec: 4: (high 0, medium 3, low 1)
- patch: 0
- defer: 0
- reject: 11
- addressed_findings:
  - `[medium]` `[bad_spec]` Unknown/off-profile tool name was routed into the terminal malformed path, contradicting the I/O-matrix recovery row. Spec amended to distinguish unknown-tool (dispatch through registry, loop continues) from malformed-JSON (terminal).
  - `[medium]` `[bad_spec]` The malformed `INVALID_INPUT` envelope was built and dropped (dead append), and Design Notes falsely claimed it drives an `INVALID_INPUT` report verdict. Spec amended: adapter surfaces it as `ReactResult.error` (client-contract return), and the note now separates that from the 2.2 eval's `SPEC_FAILED` no-answer verdict.
  - `[medium]` `[bad_spec]` `_preflight_actor_grader` only checked `actor:`, leaving `actor_local.model` unchecked against the grader (NFR1 hole). Spec amended to require preflight over every actor descriptor + a collision test.
  - `[low]` `[bad_spec]` "Zero mutation tools" wording was literally false for `document_open`/`document_close`; the mutation-absence test used a synthetic stub. Spec amended to "zero GEOMETRY-mutation tools" (mirroring 2.2) and to assert against the real `readonly_tool_schemas()`.
  - Rejected (11, noise/by-design): dispatch-raises crash (the registry error boundary never raises — returns typed envelopes); `_is_question` "?"-heuristic false pos/neg (eval answers are diagnoses; prompt forbids questions); multiple-fenced-blocks + question-with-block (prompt says exactly one block); iteration-cap-with-pending-reprompt (cap=8 vs 1–3 expected calls); empty-string→wrong_diagnosis (cosmetic report-code nit on a mis-scripted double); CI duplicate step (test asserts detail, shell asserts no-secret gate — intentional); `react-local` extra ships no wrapper (bring-your-own per decision 011); `chat_for` double-lambda style; ScriptedChat exhaustion `""` (offline-double authoring, not shipped behaviour); args-default-`{}` (registry validates required args); `tools`-list drift filtering (allow-list is provenance-fixed).

## Design Notes

- **Why the transport is injected, not an SDK dep.** The adapter must work "against any OpenAI-compatible endpoint" (clients-design §3.3) AND stay ring-pure (contracts+stdlib). Both fall out of making the chat-completion call a **`chat: ChatCompletion` callable** the caller supplies: offline CI passes a `ScriptedChat` (replays recorded assistant turns, zero network — same discipline as 2.2's `ScriptedBackend`); an operator passes a stdlib-`urllib` or `openai`-client wrapper. The adapter never imports an HTTP/model library, so no required dep and no in-FreeCAD violation. Mirrors decision 010's "live is operator-gated, CI is offline".
- **Why `react_adapter.py` is in `adapters/` but `react_backend.py` is in `benchmarks/`.** The adapter is a genuine client (a ring component) and is ring-pure via injection. But wiring it to the actor-run needs the read-only tool **schemas**, which come from `tool_specs()` in `hosts/tool_catalog.py` — and `adapters/ → hosts/` is forbidden. So the *composition* (read schemas from the catalog, filter to the allow-list, hand them to the adapter) lives in `benchmarks/harness/react_backend.py`, exactly where `harness/actor.py` already imports the profile builder. The adapter takes schemas as data; benchmarks supplies them. If a reviewer reads §3.3's "adapter in `adapters/`" as "must import the catalog," that is the ring contradiction to surface, not resolve by moving the import.
- **Tool-call wire shape.** Prompt instructs the model to emit exactly one fenced ```json block ``{"tool": "<name>", "args": {...}}``. Parser: locate the last fenced ```json block, `json.loads`, require a `tool` key present in the injected tool set. Missing block ⇒ treat remaining text as the final answer. Present-but-unparseable ⇒ malformed path (one re-prompt → `INVALID_INPUT`). Keep the shape minimal; do not invent a multi-call batch format.
- **`INVALID_INPUT` is a `contracts` envelope the adapter RETURNS, not one it builds and drops.** On the malformed terminal path the adapter must make the typed `ResultEnvelope` (`status: "INVALID_INPUT"`, `detail.code = invalid_input.malformed_tool_call`, `text` derived via the contracts envelope helper — never hand-authored) **observable to its caller**: `ReactResult` carries an optional `error: ResultEnvelope | None` field set on this path (final_answer stays `None`). A `ReactResult` whose `error` envelope was built but never surfaced is a bug — the whole point of the typed status is that the caller can see it. NOTE the layering: the adapter's `INVALID_INPUT` is the *client-contract* return value (clients-design §3.3). It is a SEPARATE concern from how the **2.2 actor-run eval grades a no-final-answer case** — that harness (`actor_run._build_case_report`, already `done`/reviewed) deliberately maps a `None` answer to `spec_failed.no_final_answer` → `SPEC_FAILED`, and this story does NOT change that mapping. So do not claim "a report built from this envelope classifies as INVALID_INPUT" (it does not; the eval verdict for no-answer is `SPEC_FAILED` by 2.2's contract). The `error` field is asserted by the adapter unit tests (`test_react_adapter.py`), not by the actor-run report verdict.
- **Unknown / off-profile tool name is NOT the malformed path.** A well-formed fenced block naming a tool absent from the injected allow-list is dispatched **through the registry** (which returns a typed `INVALID_INPUT` "unknown method" envelope), the mirror is appended, and **the loop continues** so the model can recover on the next turn — per the I/O matrix "Off-profile / unknown tool named" row. Only a block that is *unparseable JSON* or *not a JSON object* or *missing/non-string `tool`* is the malformed path (one re-prompt → typed terminal `INVALID_INPUT`). Keep the parser's "is this a syntactically valid tool call" check separate from the registry's "is this tool registered" check — conflating them (routing unknown-tool into the terminal malformed path) denies the model its recovery turn and contradicts the matrix. `_parse_tool_call` therefore accepts any well-formed `{tool, args}` shape (string `tool`, dict-or-absent `args`) regardless of whether the name is in the allow-list; the registry is the sole authority on tool existence.
- **"Read-only" means zero GEOMETRY-mutation tools, not `all(not mutating)`.** Mirrors 2.2's settled reading: the read-only profile (`READ_ONLY_PROFILE`) deliberately includes `document_open`/`document_close`, which carry `mutating=True` in the catalog but perform no geometry/model mutation (the assistant needs `document_open` to load the fixture it answers about). So every "zero mutation tools" / "never a mutation tool" phrasing in this spec means the **geometry-mutation set** (`sketch_*`, `feature_*`, `preview_*`, `document_create`, `document_save`, `debug_exec`). The G1.6 / no-mutation assertion in the adapter tests must check the rendered prompt against the **real** `readonly_tool_schemas()` output (asserting the geometry-mutation set is absent), never against a synthetic 2-tool stub dict (which proves nothing).

## Verification

**Commands:**
- `uv run pytest tests/external/test_react_adapter.py tests/external/test_react_backend_actor_run.py -q` -- expected: all pass.
- `uv run python benchmarks/runner.py --gate G1 --actor-run` -- expected (offline, ReAct backend selectable): per-case reports emitted through the identical surface, escalation applied, live local skipped, exit 0 when scripted answers pass.
- `uv run python benchmarks/runner.py --gate G1 --stub` -- expected: unchanged from 2.1/2.2 — every criterion `INVALID_INPUT`, exit 1 (regression guard).
- `uv run python scripts/check_imports.py` -- expected: exit 0 (`react_adapter` contracts+stdlib only; `react_backend` outside rings may import hosts).
- `uv run ruff check` (story files) -- expected: clean (repo-wide `.` may stay red on pre-existing unrelated E501 — deferred, note it).
- `uv run pytest tests/external -q` -- expected: all pass (new + prior suites).

**Manual checks:**
- Confirm `benchmarks/g1/gate.yaml` second actor descriptor model id ≠ `grader:` model (NFR1 preflight green) and the Claude actor/grader/tokens/heldout blocks are unchanged.
- Confirm the rendered ReAct system prompt contains each read-only tool name + its injected input schema, and no mutation tool name appears.

## Auto Run Result

Status: done

**Summary:** Follow-up review pass over the already-`done` Story 2.3 (ring-pure ReAct adapter + local-backend actor-run seam). Fresh Blind Hunter + Edge Case Hunter run against the full `6a11855..working` diff. No caused-by-this-change defect found; no code changes made this pass. One pre-existing issue deferred.

**Files changed (baseline `6a11855` → this review):** none by the review itself. The story diff under review comprised:
- `src/freecad_buddy/adapters/react_adapter.py` — ring-pure ReAct loop (contracts+stdlib), fenced-JSON parse, one-reprompt malformed/question discipline, `ReactResult.error`, unknown-tool recovery.
- `benchmarks/harness/react_backend.py` — `ReactBackend` composition + `ScriptedChat` double (reads read-only schemas from `hosts/tool_catalog`).
- `benchmarks/runner.py` — ReAct offline path; `_actor_descriptors` + generalised `_preflight_actor_grader` (NFR1 over every actor descriptor).
- `benchmarks/g1/gate.yaml` — `actor_local: llama-qwen3-30b-a3b` (≠ grader).
- `tests/external/test_react_adapter.py`, `tests/external/test_react_backend_actor_run.py` — adapter contract + actor-run + collision tests.
- `.github/workflows/ci.yml`, `pyproject.toml` (`react-local` optional extra), `docs/decisions/011-*.md`.

**Review findings breakdown:** intent_gap 0, bad_spec 0, patch 0, defer 1, reject 15. The deferred item (pre-existing, incidental): the `FREECAD_BUDDY_G1_ACTOR_BACKEND=live` doc/code contradiction (sibling docstrings + runner comment describe `=live` wiring a live backend, but the runner hard-fails on any non-`offline` value). Present at the 2.2 baseline; this story only reworded the error message. Logged as a new deferred-work entry. The two reviewers' top items (backend `tool_calls=[]`; dropped `ReactResult.error`; unreachable non-str-chat / non-dict-detail crashes; `=live` gate) were adjudicated against real source and rejected as by-design/settled-pattern/impossible-state.

**Verification performed (re-run this pass):**
- `uv run python scripts/check_imports.py` → `check_imports OK`.
- `uv run ruff check` on the six story files → `All checks passed!`.
- `uv run pytest tests/external/test_react_adapter.py tests/external/test_react_backend_actor_run.py -q` → 19 passed.
- `"FreeCADCmd" tests/run_tests.py` — not run (no FreeCAD in env; no in-FreeCAD code in scope — adapter is external-process, backend is `benchmarks/` tooling).

**Residual risks:** the deferred `=live` doc/code contradiction remains open until the live local eval is wired for an operator. The live local (llama.cpp/Qwen) leg itself is operator-gated + CI-skipped by design (never asserted green here). No follow-up review recommended: this pass produced zero review-driven code changes.

