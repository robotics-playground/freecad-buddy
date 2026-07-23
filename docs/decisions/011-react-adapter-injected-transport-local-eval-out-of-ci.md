# 011 — ReAct Adapter Is Ring-Pure via an Injected Transport; Its Local Live Eval Is Out of CI

## Decision

The Phase-1 ReAct fallback adapter (`adapters/react_adapter.py`) is a **ring-pure** MCP-less client:
it imports `contracts` + stdlib (`json`, `re`) only. The chat-completion transport
(`chat: ChatCompletion`), the tool-dispatch callable (`dispatch: ToolInvoker`), and the tool
schemas + descriptions are all **injected**, so the adapter carries no HTTP/model dependency and
`check_imports` stays clean (`adapters/ → hosts/` is forbidden). The schemas rendered into the
system prompt are the same `input_schema` dicts the MCP server surfaces, sourced from
`contracts`-owned tool metadata — a hand-authored copy is never used.

The **live local eval run is operator-gated and skipped in unattended CI** — the pinned local stack
(llama.cpp + Qwen3-30B-A3B, constrained decoding ON) or any OpenAI-compatible endpoint is an
operator wiring, needing a downloaded GGUF / endpoint / GPU that cannot be an unattended-CI green
(harness-design §6: hardware + secrets are human-only). CI instead drives the adapter and the
`benchmarks/harness/react_backend.py` `Backend` against a deterministic `ScriptedChat` double. The
G1.4 model-agnostic re-run figure is a **measured operator run**, never asserted by a green job.
This mirrors decision 010's Claude-backend discipline.

## Rationale

- **Injected transport, not an SDK dep.** The adapter must work "against any OpenAI-compatible
  endpoint" (clients-design §3.3) AND stay ring-pure. Both fall out of making the chat call a
  `chat: ChatCompletion` callable the caller supplies: offline CI passes a `ScriptedChat` (replays
  recorded assistant turns, zero network); an operator passes a `urllib`/`openai` wrapper. No
  required dep, no in-FreeCAD violation.
- **Adapter in `adapters/`, composition in `benchmarks/`.** The adapter is a genuine ring client and
  is ring-pure via injection. Wiring it to the actor-run needs the read-only tool **schemas**, which
  come from `tool_specs()` in `hosts/tool_catalog.py` — and `adapters/ → hosts/` is forbidden. So
  the composition (read schemas, filter to the allow-list, hand them to the adapter) lives in
  `benchmarks/harness/react_backend.py`, exactly where `harness/actor.py` already imports the
  profile builder. The adapter takes schemas as data; benchmarks supplies them.
- **Malformed → `INVALID_INPUT` is the adapter's CLIENT-CONTRACT return, not the eval verdict.** On
  the malformed-terminal path (a fenced block that is unparseable JSON / not an object /
  missing-or-non-string `tool`, twice in a row) the adapter builds the typed `ResultEnvelope`
  (`status: INVALID_INPUT`, `detail.code = invalid_input.malformed_tool_call`, `text` derived via
  the contracts `mirror_text` helper — never hand-authored) and **surfaces it on
  `ReactResult.error`** with `final_answer=None`. This is the client-contract return value
  (clients-design §3.3) and is asserted by `tests/external/test_react_adapter.py`. It is a SEPARATE
  concern from how the **2.2 actor-run eval grades a no-final-answer case**: that harness
  (`actor_run._build_case_report`, already `done`/reviewed) deliberately maps a `None` answer to
  `spec_failed.no_final_answer` → `SPEC_FAILED`, and this story does NOT change that mapping. A
  no-answer case grades `SPEC_FAILED`, not `INVALID_INPUT`; the `error` envelope is the adapter's
  own return, observable to any direct caller.
- **Unknown/off-profile tool is NOT the malformed path.** A well-formed fenced block naming a tool
  absent from the allow-list is a valid tool-call SHAPE: `_parse_tool_call` accepts any string
  `tool` with a dict-or-absent `args` regardless of the allow-list. It is dispatched **through the
  registry** (which returns a typed `INVALID_INPUT` "unknown method" envelope), the mirror is
  appended, and **the loop continues** so the model can recover — per the I/O-matrix recovery row.
  The registry is the sole authority on tool existence; conflating "valid shape" with "registered
  tool" would deny the model its recovery turn.
- **Zero GEOMETRY-mutation tools.** The read-only profile deliberately includes
  `document_open`/`document_close` (`mutating=True`, geometry-inert) so the assistant can load the
  fixture it answers about. The adapter's mutation-absence test builds the prompt from the REAL
  read-only schemas (`readonly_tool_schemas()`) and asserts the geometry-mutation set
  (`sketch_*`/`feature_*`/`preview_*`/`document_create`/`document_save`/`debug_exec`) is absent —
  never against a synthetic stub.

## Reuse survey (existing ReAct/agent libs vs a stdlib parse loop)

- **Surveyed: an off-the-shelf ReAct/agent framework (LangChain agents, llama-index ReActAgent,
  etc.).** Rejected for the adapter: each pulls a heavy third-party dependency tree and its own
  transport/HTTP client into what must be a ring-pure `contracts`+stdlib component, and each imposes
  its own tool-call wire format instead of the bridge's `{tool, args}` fenced-JSON shape over the
  shared registry. A ~150-line stdlib parse loop (last-fenced-block `json.loads`, one-reprompt
  discipline, bounded cap) is smaller, dependency-free, and dispatches the exact registry the MCP
  server uses.
- **Surveyed: reuse the 2.2 `Backend` protocol + actor-run.** Adopted wholesale — `ReactBackend`
  implements the same `answer(case_id, question, tools, invoke)` seam, wires the adapter's
  `dispatch` to the actor's `invoke`, and runs through the UNCHANGED `run_actor_eval` (tiered
  n10→n30 escalation, deterministic grader, Wilson CI). No fork.
- **Surveyed: reuse the contracts envelope/mirror helper (`mirror_text`).** Adopted — the typed
  `INVALID_INPUT` envelope's `text` is server-derived via `mirror_text`, never hand-authored.

## Boundaries

- No API key, model secret, endpoint, or GGUF ever enters CI, env files, or the repo. The live path
  is gated behind `FREECAD_BUDDY_G1_ACTOR_BACKEND` (any value other than the explicit `offline`
  opt-in), which is **not wired** in the harness — it exits with a clean operator-gated usage error
  rather than a fake green.
- Any live OpenAI-compatible client (`react-local` optional extra) is external-only and never
  required; the in-FreeCAD process never imports it.
- Grading stays with the independent Story 2.1 grader; the actor never grades itself. The runner's
  actor≠grader preflight now collision-checks EVERY actor descriptor (`actor:` + `actor_local:` +
  any `actors:` list entry) so a second backend cannot slip an identity collision past NFR1.

## Drives

- The ring-pure ReAct adapter + the `benchmarks/harness/react_backend.py` composition + the
  `gate.yaml` `actor_local:` pin (`llama-qwen3-30b-a3b`, ≠ grader).
- The CI `arch-checks` offline ReAct adapter + backend actor-run step (live eval skipped, no
  secret/network/GGUF).
- The generalised `_preflight_actor_grader` over all actor descriptors + its collision test.
- The Story 2.4 sealed exit is where the measured G1.4 second-backend run is recorded, not here.
