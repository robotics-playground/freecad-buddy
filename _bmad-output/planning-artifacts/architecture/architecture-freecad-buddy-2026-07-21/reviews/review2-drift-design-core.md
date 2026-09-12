---
title: 'Drift Re-Review — Lens B: Spine vs Core Design Docs'
date: '2026-09-12'
scope: 'ARCHITECTURE-SPINE.md vs design/{project-structure, component-design, mcp-tools-design, data-contracts-design, integration-mcp-freecad, integration-mcp-clients}.md'
kind: re-review
---

# Drift Re-Review — Design Core (Lens B)

Re-review after a prior fix pass. Every claim below quotes current text. Code was
checked where two docs disagreed, because the spine says installed CODE wins.

## Findings

| # | Severity | Doc + line + quoted text | Conflicting anchor + line + quoted text | Finding | Suggested fix |
| --- | --- | --- | --- | --- | --- |
| 1 | HIGH | `design/project-structure.md:56-60` — `│       └── hosts/` / `│           ├── __init__.py           # EMPTY` / `│           ├── InitGui.py            # addon entry source-of-truth; copied to addon root at build (§2.2)` / `│           ├── gui_addon.py          # deferred start (GuiUp + QTimer.singleShot), listener wiring (AD-2)` / `│           └── main.py               # CLI: serve --mode inline\|rpc --transport stdio\|http; headless entry` | `ARCHITECTURE-SPINE.md:303` — `    hosts/         # gui_addon/ (InitGui, bootstrap, pump), gui_external/, headless/, main.py, tool_catalog.py`; also `ARCHITECTURE-SPINE.md:29` — `Hosts \| \`src/freecad_buddy/hosts/\` \| GUI addon (\`gui_addon/\`), external GUI host, headless entry, \`main.py\`, \`tool_catalog.py\` (shared tool surface)` | The project-structure tree is the only place still showing a FLAT `hosts/gui_addon.py` module plus a top-level `hosts/InitGui.py`, and it omits `gui_addon/bootstrap.py`, `gui_addon/pump.py`, `gui_external/`, `headless/` and `tool_catalog.py` entirely. Every other doc uses the package form: `integration-mcp-freecad.md:114` `### 3.1 Addon lifecycle (\`hosts/gui_addon/InitGui.py\`)`, `:130` `from freecad_buddy.hosts.gui_addon.bootstrap import start_bridge`, `:179` `# hosts/gui_addon/pump.py — Qt allowed here (AD-1)`, `:27` `\`hosts/gui_addon/*\`, \`hosts/headless/run_server.py\``. Actual code has `src/freecad_buddy/hosts/{gui_addon/, gui_external/, headless/, main.py, tool_catalog.py}`. | **project-structure.md changes.** It is the outlier against spine + two design docs + code. Replace the four flat `hosts/` lines with the package tree: `gui_addon/` (`InitGui.py`, `bootstrap.py`, `pump.py`), `gui_external/`, `headless/` (`entry.py`, `run_server.py`), `main.py`, `tool_catalog.py`. Also fix `:145` `├── InitGui.py            # copied from src/freecad_buddy/hosts/InitGui.py` and `:151` `…deferred call into \`freecad_buddy.hosts.gui_addon.start()\`` to the `gui_addon/` path and `bootstrap.start_bridge()` entry that `integration-mcp-freecad.md:130` names. |
| 2 | MEDIUM | `design/project-structure.md:39` — `│       │   ├── transactions.py       # AD-5 mutation protocol skeleton (Phase 0: stub + tests)` | `design/component-design.md:34` — `\| \`transaction.py\` \| P0 \| Uniform mutation protocol (AD-5) — every mutation tool runs through \`run_mutation()\`…`; also `component-design.md:47` `# transaction.py — AD-5; the only mutation path` | File name differs by one letter: `transactions.py` vs `transaction.py`. Code has `src/freecad_buddy/usecases/transaction.py` (singular). | **project-structure.md changes** to `transaction.py`. Component-design and code already agree. |
| 3 | MEDIUM | `design/project-structure.md:54-55` — `│       │   ├── export_oracles.py     # trimesh / lib3mf / admesh checks (AD-9) [ext-only]` and `│       │   └── harness.py            # benchmark-runner glue, ValidationReport emission [ext-only]` | `ARCHITECTURE-SPINE.md:302` — `    adapters/      # mcp_server, rpc_client/listener/dispatch, marshal, render_probe, audit_log, export oracles` (no `harness.py`) | Two mismatches. (a) `export_oracles.py` is plural in project-structure and `component-design.md:84` `\| \`export_oracles.py\` \| P0 \|…`, but the installed module is `adapters/export_oracle.py` (singular) plus `adapters/export_verdict.py`, which no design doc lists. (b) `adapters/harness.py` appears in project-structure `:55` and `component-design.md:85` / `:188`, but the spine adapters line does not name it and no `harness.py` exists in the code. | **Both design docs change.** Rename to `export_oracle.py` and add `export_verdict.py` to the adapters inventory in project-structure §1 and component-design §3. For `harness.py`, decide once: either add it to the spine adapters line (it is a real AD-13/AD-14 component with a ring home) or move the gate runner wholly under `benchmarks/`. Do not leave it named in two design docs and absent from the spine. |
| 4 | MEDIUM | `design/component-design.md:85` — `Thin CLI lives in \`benchmarks/run_gate.py\` (SPEC assumption)`; repeated `component-design.md:188` `\| Gate runner \| \`adapters/harness.py\` + \`benchmarks/run_gate.py\` CLI \|` | `ARCHITECTURE-SPINE.md:305` — `  benchmarks/      # runner.py + harness/; specs + assertions; g0/ g1/ g2/, sealed heldout/, _registry/`; `design/project-structure.md:68` — `│   ├── runner.py                     # gate runner CLI → contracts ValidationReport (SPEC assumption)` | The gate CLI file is `run_gate.py` in component-design and `runner.py` in the spine and project-structure. `validation-harness-design.md:119` reconciles the *console-script* spelling only: `` `gate` is a console-script alias of `benchmarks/runner.py` (project-structure §1/§5 invokes it as `python benchmarks/runner.py --gate G0` in CI — same entry point, two spellings).`` — it says nothing about `run_gate.py`. | **component-design.md changes** to `benchmarks/runner.py` in both places. The spine, project-structure and validation-harness already agree on `runner.py`. |
| 5 | MEDIUM | `design/mcp-tools-design.md:34-46` — `{ "$defs": { "Selector": { "oneOf": [ { "type": "object", "properties": { "by": { "const": "mapped_name" }, "object": …, "element": … }, "required": ["by", "object", "element"] }, { … "by": { "const": "geo_query" } … "query": … } ] }` | `design/data-contracts-design.md:235-253` — `class GeometricSelector(TypedDict, total=False):` / `    kind: Literal["geometric"]` … `class MappedNameSelector(TypedDict, total=False):` / `    kind: Literal["mapped_name"]` / `    mapped_name: str` … `Selector = GeometricSelector \| MappedNameSelector` | The same wire object has two incompatible shapes: discriminator key `by` vs `kind`; geometric tag `geo_query` vs `geometric`; mapped-name field `element` vs `mapped_name`. Data-contracts also carries `element_type`, `expect`, and `element_map_version` that the mcp-tools fragment omits. Installed code (`src/freecad_buddy/contracts/document.py:19,27,29`) has `kind: Literal["geometric"]`, `kind: Literal["mapped_name"]`, `mapped_name: str` — data-contracts is right. | **mcp-tools-design.md changes.** Contracts owns wire types (AD-17 / spine Conventions line 233 names data-contracts-design as the owner of "wire types, versioning"). Replace the §1.2 `$defs.Selector` fragment with a `$ref` to the contracts-generated selector schema, or restate it with `kind`/`geometric`/`mapped_name`. Note the consequence: `mcp-tools-design.md:498` example `focus: {by: geo_query, object: Body, query: {…}}` must become `{kind: "geometric", …}`, and `data-contracts-design.md:213` already writes `"reference": Selector` inside `tnp_precheck.flagged`, so the corrected form propagates. |
| 6 | LOW | `design/mcp-tools-design.md:115` — `\| \`document_object_delete\` \| 2 \| Delete an object (and report orphaned dependents) under AD-5 \| yes \|` | `ARCHITECTURE-SPINE.md:237` — `\| Tool names (wire) \| Underscore + namespace prefix: \`query_\`, \`document_\`, \`export_\`, \`verify_\`, \`sketch_\`, \`feature_\`, \`preview_\`, \`debug_\`. …` | Not a violation — `document_object_delete` carries the `document_` prefix and underscores. Recorded only because it is the one three-segment tool name in the catalog and reads as a different pattern from its siblings (`document_create`, `document_close`). AD-20 binds documents, not objects, so the namespace choice is a judgment call the spine does not constrain. | **No change required.** If the spine owner wants one pattern, `feature_delete` (object mutation, AD-5 bracket, not a lifecycle op) is the more consistent home, since `mcp-tools-design.md:98` already exempts the four `document_` lifecycle ops from the confirm gate while this tool is `yes` without the `(L)` marker. Flag for owner, do not silently rename. |
| 7 | LOW | `design/project-structure.md:69-74` — `│   ├── golden/                       # 5 reference models (G0.3): gNN_<name>/{model.FCStd, expected.json, PROVENANCE.md}` / `│   ├── dev/                          # dev split (AD-13/16); per-phase subdirs (phase0/, phase2/ …)` / `│   ├── heldout/` / `│   └── fault-injection/` | `ARCHITECTURE-SPINE.md:305` — `  benchmarks/      # runner.py + harness/; specs + assertions; g0/ g1/ g2/, sealed heldout/, _registry/`; `design/validation-harness-design.md:17` — `  g0/                       # per-gate dirs mirror phase-gates.md (g0..g4, gs)` / `:18` `    golden-models/          #   5 hand-made reference models (.FCStd + expected.yaml)` / `:37` `  _registry/` | Two different `benchmarks/` layouts. Project-structure nests by artifact kind (`golden/`, `dev/`, `fault-injection/` at top level, phase subdirs inside `dev/`); the spine and validation-harness nest by gate (`g0/` containing `golden-models/`, `dev/`, `heldout/`, `fault-injection/`) and add `_registry/`, which project-structure does not mention. Fixture file extension also differs: `expected.json` vs `expected.yaml`. | **project-structure.md changes** to the gate-first layout, and adds `_registry/`. The spine names `_registry/` and `g0/ g1/ g2/` explicitly; validation-harness-design is the detailed owner of the harness layout and matches the spine. Settle `expected.json` vs `expected.yaml` in validation-harness-design and mirror it. |
| 8 | LOW | `design/integration-mcp-clients.md:36-47` — `      "command": "uv",` / `      "args": [ "run", "--project", "D:/Work/Personal/Sources/freecad-buddy", "freecad-buddy", "serve", "--transport", "stdio", "--mode", "inline" ]` | `design/project-structure.md:199` — `` `uv run freecad-buddy serve --mode rpc --transport http` `` | Flag order differs between the two examples (`--transport` first vs `--mode` first). Both use the same verb and flag names, so this is cosmetic, not a contract conflict. The CLI itself is declared once at `project-structure.md:60` `# CLI: serve --mode inline\|rpc --transport stdio\|http; headless entry` and both examples are inside it. | **No change required.** Order is not part of the contract. Recorded so a later reader does not read it as two CLIs. |

## Checked and consistent

These cross-doc items were verified against current text and agree. No fix needed.

**Result envelope shape and version tag.** One contracts-owned type with one tag.
`data-contracts-design.md:86` `    schema: Literal["fcb.result-envelope/1"]`;
`mcp-tools-design.md:59` "The envelope shape is contracts-owned (`fcb.result-envelope/1`, see
data-contracts-design.md §4) — this catalog consumes it, never redefines it";
`mcp-tools-design.md:65` `"schema": { "const": "fcb.result-envelope/1" }`;
`integration-mcp-freecad.md:62` "**`result` is always a `ResultEnvelope`** (contracts-owned, AD-17
closed status set)"; `data-contracts-design.md:300` `{"jsonrpc": "2.0", "id": 41, "result":
{"schema": "fcb.result-envelope/1", "status": "OK", ...}}`. Matches `AD-17`
(`ARCHITECTURE-SPINE.md:173`): "The `ResultEnvelope`, `ValidationReport`, `JobStatus`, and
audit-record types are owned by `contracts/` from Phase 0". Code agrees
(`contracts/envelope.py:24`, `contracts/rpc.py:13`).

**Envelope required-field set.** `mcp-tools-design.md:72` `"required": ["status",
"structured_content", "text"]` matches the three fields data-contracts marks required in comments
(`data-contracts-design.md:86-90`: `status … # required`, `structured_content … # required`,
`text … # required`). `detail` is required non-null only on non-OK in both.

**RPC wire — ownership.** `data-contracts-design.md:292` states outright: "Frame layout, method
registry, error codes, timeouts, and the discovery file are designed in integration-mcp-freecad.md
§2 (the authoritative wire design); `rpc.py` carries its types." That is the deference the task
asked for, and it is present.

**RPC framing.** `integration-mcp-freecad.md:35` "**NDJSON over TCP, localhost**: one JSON-RPC 2.0
object per line, UTF-8, `\n`-terminated" = `data-contracts-design.md:290` "Transport:
newline-delimited JSON-RPC 2.0 frames over localhost TCP; stdlib-encodable only". Both cite AD-2's
"stdlib-encodable JSON-RPC frames + versioned handshake" (`ARCHITECTURE-SPINE.md:53`).

**RPC handshake.** Method name, first-frame rule and reject code agree.
`integration-mcp-freecad.md:40` "First frame on every connection MUST be `rpc_hello`; anything else
→ error `-32002`, connection closed"; `data-contracts-design.md:310` "**Handshake** — first frame on
every connection MUST be `rpc_hello` (else `-32002`, closed)". `contract_version` `"1"` in both
(`integration-mcp-freecad.md:45`, `data-contracts-design.md:314`); mismatch → `-32004` in both
(`integration-mcp-freecad.md:55`, `data-contracts-design.md:322`).

**RPC method names.** `integration-mcp-freecad.md:60` "**Method names mirror the use-case surface**
(spine naming convention): `query_*`, `document_*`, `sketch_*`, `feature_*`, `export_*`, `preview_*`,
`verify_*` …, `debug_exec` (gated), plus `rpc_hello`, `rpc_ping`, `rpc_capabilities`" =
`data-contracts-design.md:295` "// request — method names mirror the use-case surface directly (no
call_usecase wrapper)" with `"method": "feature_pocket"`. No wrapper method in either doc.

**RPC token.** `integration-mcp-freecad.md:54` "Token: `secrets.token_urlsafe(32)`, generated once
per listener start … compared with `hmac.compare_digest`. Mismatch → `-32000`, close. (AD-3)" =
`data-contracts-design.md:324` "Localhost bind + per-session `token` (discovery file, mode 0600) per
AD-3; token travels in `params`, never in a URL." Both match AD-3
(`ARCHITECTURE-SPINE.md:61`): "the RPC channel carries a per-session token generated at addon start".

**RPC error split and status mapping.** `integration-mcp-freecad.md:63` "**JSON-RPC `error` is
protocol-layer only:**" with the code table at `:66-71` = `data-contracts-design.md:323`
"**Error mapping (normative):** tool-level failures always arrive as a `result` `ResultEnvelope`
with non-OK status — JSON-RPC `error` is reserved for the channel itself (codes: integration doc
§2.3)." Channel→status mapping is stated once, in data-contracts, and points back to the
integration doc for codes.

**Marshal timeout behavior.** `integration-mcp-freecad.md:82` "Marshal timeout returns an envelope
`status:\"TIMEOUT\"` with `detail:{\"marshal_timeout\":true,\"maybe_still_running\":true}` — see §7"
= `data-contracts-design.md:303` `{"jsonrpc": "2.0", "id": 41, "result": {"schema":
"fcb.result-envelope/1", "status": "TIMEOUT", "detail": {"marshal_timeout": true,
"maybe_still_running": true}}}`. Same field names, same shape.

**Which layer originates each status.** Three docs state it identically.
`data-contracts-design.md:69` "`TIMEOUT`/`WORKER_CRASHED` originate only from
transport/supervision layers (marshal timeout, RPC listener unreachable — from Phase 0; see
integration-mcp-freecad.md §7) and `OOM_KILLED` only from the Phase 4 sandbox; use-case code maps
its own failures to `SPEC_FAILED | RECOMPUTE_ERROR | INVALID_INPUT`";
`mcp-tools-design.md:76` "Phase 0–2 use-case outcomes emit `OK | SPEC_FAILED | RECOMPUTE_ERROR |
INVALID_INPUT`; the transport layer additionally emits `TIMEOUT` (marshal timeout) and
`WORKER_CRASHED` (RPC listener unreachable) from Phase 0 — see integration-mcp-freecad.md §7;
`OOM_KILLED` is Phase 4 supervisor-only"; `integration-mcp-freecad.md:323` gives the
`WORKER_CRASHED` + `{"rpc":"unreachable"}` row. Cross-references are correct in both directions.

**Status set membership.** `data-contracts-design.md:54-57` `TerminalStatus = Literal[ "OK",
"SPEC_FAILED", "RECOMPUTE_ERROR", "TIMEOUT", "OOM_KILLED", "WORKER_CRASHED", "INVALID_INPUT", ]`
is exactly AD-17's set (`ARCHITECTURE-SPINE.md:173`: "`OK | SPEC_FAILED | RECOMPUTE_ERROR | TIMEOUT
| OOM_KILLED | WORKER_CRASHED | INVALID_INPUT`") and exactly the `mcp-tools-design.md:66` enum.
Seven members, no extras, no omissions. `JobState` correctly adds `QUEUED`/`RUNNING` outside the
terminal set only (`data-contracts-design.md:58`, `:153`).

**Tool count per phase.** Three statements of the same numbers, all consistent.
`mcp-tools-design.md:206` `| **Total** | **25** | **2** | **22** | **49** |`;
`mcp-tools-design.md:208` "Phase 0 = **17** tools across `query_`/`document_`/`export_` (8+6+3) …
**24** including `verify_`"; `mcp-tools-design.md:531` repeats 17 and 24;
`project-structure.md:277` "The authoritative Phase 0 tool catalog is **mcp-tools-design.md** (§2):
25 Phase 0 tools, of which 17 fall in the gate's literal `query_`/`document_`/`export_` namespace
set (≥15, G0.2 satisfied), plus 7 `verify_` tools." The namespace column totals verify:
document_ 6+2=8, query_ 8+2=10, export_ 3, verify_ 7+1=8, sketch_ 8, feature_ 10, preview_ 1,
debug_ 1 → 49. P0 column 6+8+3+7+0+0+0+1 = 25. Arithmetic is sound. `verify_visual` is correctly
excluded and marked `mcp-tools-design.md:152` "*(Phase 3 — outside the P0–P2 count table.)*".

**Tool names.** Every name in the §2 inventory uses underscore + one of the eight prefixes AD-1's
conventions table fixes (`ARCHITECTURE-SPINE.md:237`). No dot form survives in these six docs;
`mcp-tools-design.md:18` states the rule and `integration-mcp-clients.md:71` restates it: "Names
follow the underscore convention (`query_*`, `verify_*`, `preview_*`, …) — dots are illegal in MCP
tool names". `query_object` (`mcp-tools-design.md:122`) is used, not `query_shape`. The installed
MCP tool list matches these names.

**TempDoc reserved prefix.** `mcp-tools-design.md:27` "Preview TempDocs use reserved prefix
`FCB_TMP_`, are flagged transient, and are cleaned only by `preview_dry_run` (their creator)" =
`data-contracts-design.md:231` `transient: bool         # True for preview TempDocs (reserved name
prefix "FCB_TMP_", cleaned only by their creator — AD-20)` = `mcp-tools-design.md:446` "TempDoc
prefix FCB_TMP_, cleaned by this tool (AD-20)". Matches AD-20 (`ARCHITECTURE-SPINE.md:197`):
"Preview TempDocs use a reserved name prefix, are flagged transient, and are cleaned by their
creator". Code uses `_TEMPDOC_PREFIX = "FCB_TMP_prev_"` (`usecases/preview.py:33`) — a prefix that
starts with the reserved one, so the reservation holds.

**Preview/confirm token name.** One name everywhere: `preview_id`.
`mcp-tools-design.md:432` `"preview_id": { "type": "string", "description": "pass back as
confirm.preview_id on apply" }`; `mcp-tools-design.md:504` `"preview_id": { "type": "string",
"description": "from preview_dry_run" }`; `integration-mcp-clients.md:87` "the mutation tool
requires an explicit `preview_id` (confirm token) issued by the matching `preview_dry_run` result";
`integration-mcp-clients.md:133` "`preview_id` (confirm token) from `preview_dry_run`";
`integration-mcp-clients.md:175` "`preview_id` (confirm token) TTL and single-use semantics".
Code agrees (`contracts/confirm.py:17`).

**Confirmation policy.** `mcp-tools-design.md:510` "mutation tool called without valid `confirm` in
a confirm-required context → `INVALID_INPUT`, no execution. GUI panel and MCP elicitation produce
the `accept`; headless is fail-closed unless `autoApprove`" =
`integration-mcp-clients.md:134` "**Fail-closed**: no mutation without explicit `autoApprove` flag;
every auto-approval audit-logged with its diff (AD-10, AD-17)" =
`integration-mcp-clients.md:136` "`autoApprove` is an operator-set env flag (conventions), never a
client-supplied parameter". All three match AD-10 (`ARCHITECTURE-SPINE.md:117`): "headless is
fail-closed unless an explicit `autoApprove` flag, and every auto-approval is audit-logged".
`data-contracts-design.md:183` closes the loop: "Every AD-10 headless `autoApprove` writes an
`approval` record with `mode:\"auto_approve\"` and the `diff_digest`".

**DocHandle.** `mcp-tools-design.md:24` "Every tool input carries an explicit `doc` handle (opaque
string, e.g. `\"fcb-doc:7f3a…\"`)" and `data-contracts-design.md:227-232` `class
DocHandle(TypedDict, total=False):` / `    handle: str             # opaque id issued by
document_open/document_create; required.` The mcp-tools view is the flattened wire form of the
contracts type, and `data-contracts-design.md:334` states the invariant that ties them:
"`DocHandle.handle` is required on every document-touching wire object (AD-20)". Not a conflict —
one is the JSON field, the other the Python type. Both match AD-20 (`ARCHITECTURE-SPINE.md:197`).

**Bare-index resolution rule.** `mcp-tools-design.md:53` "A caller-supplied bare `Face6` is resolved
to a mapped name at call time and never persisted" = `data-contracts-design.md:256` "Bare indexed
names (`Face6`) are accepted **only** as call-time input sugar … contracts objects (audit records,
diffs, reports, specs) never store an indexed name" = spine conventions
(`ARCHITECTURE-SPINE.md:247`): "Bare indexed names (`Face6`) are resolved to mapped names at call
time and never stored."

**CLI entry point spelling.** `project-structure.md:125` `freecad-buddy =
"freecad_buddy.hosts.main:main"` names the console script; `project-structure.md:60` fixes the verb
and flags: `# CLI: serve --mode inline|rpc --transport stdio|http`. Both usages in the other docs
spell it the same way (`project-structure.md:199`, `integration-mcp-clients.md:42-45`). The
auto-spawn command matches: `integration-mcp-freecad.md:136` "**auto-spawn the external MCP HTTP
proxy** (`freecad-buddy serve --mode rpc --transport http`, port 8765)" =
`component-design.md:93` "(`serve --mode rpc --transport http`, `:8765`)".

**The `serve --mode rpc` fallback framing.** All three docs now call the hand-run CLI a debug
fallback, matching the spine amendment at `ARCHITECTURE-SPINE.md:53` ("The internal `serve --mode
rpc` CLI that runs that server is a debug/troubleshoot fallback … never the normal path"):
`project-structure.md:199` "**(debug/troubleshoot only)**"; `integration-mcp-clients.md:54` "the
operator never launches the server by hand (that CLI is a debug-only fallback)";
`integration-mcp-freecad.md:136` "Skipped when `FREECAD_BUDDY_NO_AUTO_MCP` is set or `:8765` is
already served". The venv auto-discovery wording matches the spine's "auto-discovered from the
addon's own install path (no env vars; it never imports `mcp`, AD-12)" in
`project-structure.md:198`, `integration-mcp-freecad.md:136`, and `component-design.md:93`.

**HTTP endpoint.** `http://127.0.0.1:8765/mcp` in `project-structure.md:198`,
`integration-mcp-clients.md:54`, `:63`, `:102`. One port, one path, everywhere.

**Marshal Qt exemption.** The prior fix pass landed. `component-design.md:81` "Holds **no Qt
import** — the Qt event pump lives in `hosts/gui_addon/pump.py`, so this module needs no AD-1
exemption" = `project-structure.md:49` "main-thread marshal (postEvent pattern; no Qt import — pump
is in hosts/gui_addon/pump.py)" = AD-1 (`ARCHITECTURE-SPINE.md:45`): "The main-thread marshal
(`adapters/marshal.py`) holds no Qt import at all; the Qt event pump lives in
`hosts/gui_addon/pump.py`, where it needs no exemption." One residual note: `component-design.md:205`
still argues the older QtCore reading — "`adapters/marshal.py` imports Qt**Core**
(`postEvent`/queued invoke) inside the GUI process" — which contradicts its own `:81` line and the
spine. See the summary note below; it is a stale paragraph in the same doc, listed here because the
binding table rows are correct.

**Render probe as the single adapters carve-out.** `component-design.md:87` "the single adapter Qt
carve-out (AD-1, AD-10)" = `project-structure.md:52` "render capability probe (sole Qt exception in
adapters, AD-1)" = `integration-mcp-freecad.md:283` "the **capability probe** sits in
`adapters/render_probe.py` (the AD-1 carve-out, whitelisted by exact path in
`scripts/check_imports.py`)" = AD-1 (`ARCHITECTURE-SPINE.md:45`): "with one named `adapters/`
exemption: the render capability probe (`adapters/render_probe.py`)".

**Image budget.** `mcp-tools-design.md:78` "Renders follow AD-10 budgets: ≤1920 px,
`audience:[\"user\"]`, `resource_link` preferred over inline base64" =
`data-contracts-design.md:80-82` `data_b64: str           # set when kind == "inline"; server
enforces ≤1920 px longest edge` / `audience: list[str]     # always ["user"] — never
model-directed` = `integration-mcp-clients.md:140` "Budget: ≤1920 px longest edge, PNG, annotated
`audience: [\"user\"]`." `mcp-tools-design.md:480-481` caps `width`/`height` at `"maximum": 1920`.
All match AD-10 (`ARCHITECTURE-SPINE.md:117`).

**Transport policy.** "SSE never" is stated and not contradicted:
`component-design.md:78` "transport run-flag `stdio|http`, SSE never (AD-3)";
`integration-mcp-clients.md:28` "SSE never (AD-3). HTTP and RPC bind localhost; remote bind is
explicit operator opt-in (AD-3)"; `mcp-tools-design.md:524` "One FastMCP server object serves both
transports (stdio headless, streamable HTTP in-GUI; SSE never) per AD-3". Matches
`ARCHITECTURE-SPINE.md:61`.

**stdout discipline.** `integration-mcp-freecad.md:333` "stdout pollution (stdio transport) | CI
lint: no `print()` in server code | All logging stderr-only (AD-3)" =
`integration-mcp-clients.md:50` "stdout carries protocol frames only; all logging to stderr (AD-3)"
= AD-3 (`ARCHITECTURE-SPINE.md:61`): "`print()` to stdout is banned in server code."

**AD-12 in-FreeCAD dependency ban.** `integration-mcp-freecad.md:27` lists the exact in-FreeCAD
module set and the rule; `project-structure.md:177` gives the enforced version:
"`check_imports.py` asserts, per AST walk: `contracts/` = stdlib only; `usecases/` = stdlib +
{FreeCAD, Part, Sketcher, PartDesign, Mesh, MeshPart} via shim; `rpc_listener.py` = stdlib only";
`component-design.md:80` "**Stdlib + FreeCAD only** (AD-12)". Consistent with AD-12
(`ARCHITECTURE-SPINE.md:133`).

**Headless topology vs AD-2.** `integration-mcp-freecad.md:25` explicitly reconciles the H2
fallback with AD-2's "headless = single process" rather than silently diverging: "It is the GUI
topology minus Qt — no marshal needed … It does not contradict AD-2's 'headless = single process'
intent". AD-2 itself sanctions this (`ARCHITECTURE-SPINE.md:53`): "where the external interpreter
cannot `import FreeCAD`, the documented fallback is the GUI topology minus Qt — `FreeCADCmd`-hosted
RPC listener with inline dispatch."

**AD-10 diff-field lock.** Not drift, and correctly declared. The spine defers the field list
(`ARCHITECTURE-SPINE.md:333`: "Preview diff `outputSchema` field list | Locked once at Phase 2 UX
design"); `data-contracts-design.md:346` states the refinement openly: "this document fixes the
field *names and shapes* now … and leaves only tolerances/thresholds to Phase 2 — locking names
early is what the AD-17 reuse rule requires." `mcp-tools-design.md:450` says the same from the other
side: "Field list of `diff` is the Phase 2 UX-locked schema (spine Deferred) — it must reuse the
contracts-owned audit-record vocabulary; the fragment above is the design baseline for that lock."
Declared refinement, not silent extension.

**AD-5 lifecycle-op exemption.** A silent extension would be a finding; this one is declared and
escalated. `mcp-tools-design.md:530` "AD-5's 'every mutation' is read as 'every geometry-intent
mutation'; flagged for spine-owner confirmation." It remains an open owner decision, correctly
surfaced rather than buried.

**AD coverage over these docs' subject matter.** Every AD that binds adapters/hosts/tool-surface
has a detail doc and the spine's pointer resolves: AD-2 → `integration-mcp-freecad.md`
(`ARCHITECTURE-SPINE.md:49`), AD-3 → same + `integration-mcp-clients.md` (`:57`), AD-4 →
`security-and-service-design.md` §1 + `mcp-tools-design.md` §5 (`:65`, present at
`mcp-tools-design.md:512`), AD-10 → `integration-mcp-clients.md` §4/§5 +
`data-contracts-design.md` §8 (`:113`, both present), AD-11 → `integration-mcp-freecad.md` §5 +
`project-structure.md` §3 (`:121`, both present), AD-12 → `project-structure.md` §2.3 (`:129`,
present), AD-17 → `data-contracts-design.md` (`:169`, present), AD-20 → `mcp-tools-design.md` §1.1 +
`data-contracts-design.md` §9 (`:193`, both present). No missing-coverage finding in this lens.

## Summary

| Severity | Count |
| --- | --- |
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 4 |
| LOW | 3 |
| **Total** | **8** |

All eight findings are naming or layout drift in the design docs. None is an AD contradiction, and
none changes a wire contract's behavior. The prior fix pass closed the substantive items: the
envelope tag, the status-origin split, the marshal Qt exemption, the auto-spawn topology, and the
`preview_id` name are now stated the same way in every doc that mentions them.

One extra note outside the table, because it is an internal inconsistency rather than cross-doc
drift: `component-design.md:205` ("`adapters/marshal.py` imports Qt**Core** (`postEvent`/queued
invoke) inside the GUI process") contradicts `component-design.md:81` ("Holds **no Qt import**") in
the same file, and contradicts AD-1 at `ARCHITECTURE-SPINE.md:45`. The §8 paragraph is left over
from before the pump moved to `hosts/gui_addon/pump.py`. Delete it — the AD-1 exemption it argues
for is no longer needed, and `project-structure.md:281` already records the matching cleanup
("`check_imports.py` still whitelists `adapters/marshal.py`; that entry is now dead").
