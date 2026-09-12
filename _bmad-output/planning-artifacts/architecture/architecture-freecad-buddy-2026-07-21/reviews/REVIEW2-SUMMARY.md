---
title: 'Architecture Drift Re-Review — Consolidated Findings'
date: '2026-09-12'
intent: validate
scope: 'docs/intent.md + ARCHITECTURE-SPINE.md (24 ADs) + 11 design docs + installed code'
status: report-only
---

# Drift Re-Review — Consolidated

Five lenses ran in parallel against current text. No file was edited. Every claim below is
quoted from the file named; code claims were read from source, not assumed.

Per-lens detail:
[intent-spine](review2-drift-intent-spine.md) ·
[design-core](review2-drift-design-core.md) ·
[design-verify](review2-drift-design-verify.md) ·
[code-reality](review2-drift-code-reality.md) ·
[adversary + gaps](review2-adversary-and-gaps.md)

## Verdict

The verification core is solid. 30 numbers were reconciled across 7 documents and 29 agree.
All 24 ADs trace to intent; no orphan architecture. All 4 Out-of-Scope rows are clean.
The same-day fix pass closed what it touched — envelope tag, status-origin split, marshal Qt
exemption, `preview_id`, auto-spawn topology all now read the same way everywhere.

Drift now sits in four places, none of them the verify stack:

1. **Two live security/state holes** that no AD closes (C1, C2).
2. **Documents describing a system the code has moved past** — a stale tool inventory and three
   stale repo-layout inventories (C3, C4), plus four claims where a decision is already made and
   written down in `docs/decisions/` (H1-H3).
3. **Eleven structural dimensions the spine never names** — 8 genuinely undecided, 3 decided
   in a design doc but unbound by the spine.
4. **Three compliant-but-incompatible unit pairs** the ADs permit (H6).

Direction of the doc-vs-code drift is consistent: in 15 of 16 code-reality findings the **code is
right and the document is stale**. This is a documentation-maintenance problem, not an
architecture violation — the invariants hold in code.

## Priority findings

### C1 — HTTP proxy `:8765` is unauthenticated. CRITICAL

AD-3 (spine:61) scopes the credential to one hop: "the **RPC channel** carries a per-session
token generated at addon start". The outer hop has none.

Verified in code:
- `adapters/rpc_listener.py:281` — `if not hmac.compare_digest(str(token), self._token):` — inner hop guarded.
- `adapters/mcp_server.py` — grep for `Authorization|bearer|token|Origin` returns **zero hits**.
- `.mcp.json` — `{"type": "http", "url": "http://127.0.0.1:8765/mcp"}`, no credential field.

That port is the complete mutation surface: every `feature_*`, `document_save`, `export_*`.
Any local process can drive the user's live FreeCAD GUI with no credential. This is live in
the documented dev topology today, not a Phase 4 concern. The RPC token sits *behind* the
proxy, not in front of it.

Two units diverge on this legally: the addon author reads AD-3 and leaves HTTP open (localhost
bind is the stated protection); the Phase 4 author reads AD-18 and adds a bearer token. Both
comply. They cannot both be the default on one server object.

**Fix:** amend AD-3 to put a bearer token on the HTTP endpoint with the same lifecycle as the
RPC session token, written to the connection file, plus an `Origin` allowlist for DNS-rebinding
defense. Binding in all phases, not a Phase 4 addition.

### C2 — `saveCopy` snapshot has no path, owner, or cleanup rule. CRITICAL

AD-5 (spine:77) mandates the snapshot and the restore — "restore from the pre-mutation
`saveCopy` snapshot" — and fixes no location. The Consistency Conventions table (spine:235-248)
has no file-location row at all. `verification-design.md:35` adds a deletion *condition* but
still no path.

Two compliant choices: beside the user's document, or in the job workdir. Both legal, and the
failure is silent either way — in GUI mode the bridge litters the user's document folder with
orphan `.FCStd` files after any crash; across a worker recycle the restore path finds nothing
and **rollback proof degrades to "abort succeeded"**, which is precisely what AD-5 says is
never assumed.

**Fix:** new AD-25 fixing a session-scoped workdir for every file the bridge writes (`snap/`,
`exports/`, `audit.log`, `tmp/`), with naming, per-transaction deletion on every exit path, and
a sweep at bridge start. This one AD also closes the retention gap, the snapshot-lifecycle gap,
and the still-open `review-rubric-walker.md:115` finding.

### H1 — Spine still says FastMCP; code uses the low-level `Server`. HIGH

The SDK question is closed in writing (`docs/decisions/005-mcp-sdk-pin.md`) and in code:

- `adapters/mcp_server.py:22` — `from mcp.server.lowlevel import Server`
- `pyproject.toml:11` — `"mcp>=1.28,<2",  # official MCP python-sdk (NOT PrefectHQ fastmcp)`

The spine contradicts this in four places: AD-3 (spine:61) "one FastMCP server object";
AD-12 (spine:133) "mcp/FastMCP"; seed mermaid (spine:278) `fast[FastMCP server + tool registry]`;
and the Stack row (spine:256) still calls the choice "a **Phase 0 call**" that is already made.
Code wins per the CLAUDE.md §15 precedence rule.

### H2 — Deferred row says "no code shaped by it"; 224 lines of it ship. HIGH

Spine Deferred (spine:332) — "Local LLM backend pin … **no code shaped by it**".

Reality: `adapters/react_adapter.py` (224 lines) is the system-prompt-injection second-harness
path, with an `openai>=1` optional extra (`pyproject.toml:22`) and its own decision note (011).
`integration-mcp-clients.md` §3.3 documents it properly — the design doc is right and the spine
row is stale.

This matters beyond bookkeeping: intent L220 requires ≥2 LLM backends to prove the bridge is
model-agnostic, which is an *architectural* property (tool-schema portability, no
Claude-specific elicitation dependency), not a model pin. AD-10 makes MCP elicitation the
confirmation mechanism with a "client-confirm fallback" — the ReAct path is exactly the
fallback, and it ships. The property deserves an AD or Conventions row; only the model choice
should stay deferred.

### C3 — Tool inventory does not match the registry. CRITICAL

The design docs describe a tool surface the code does not have, in both directions.

- `mcp-tools-design.md:212-223` totals **49** tools; `hosts/tool_catalog.py:995 def tool_specs()`
  returns **44**, plus the separate `DEBUG_EXEC_SPEC` (`tool_catalog.py:975`) = **45**.
- **Six doc-named tools have zero occurrences in `src/`** — verified by direct grep:
  `document_object_delete`, `query_tree_children`, `query_parameters`, `verify_fingerprint`,
  `verify_references`, `verify_visual`. These are Phase 1/2/3 scope, but the table reads as a
  shipped inventory.
- **`feature_body_create` ships and no design doc names it.** Code registers 11 `feature_*`
  tools; `mcp-tools-design.md:175-187` lists 10. Confirmed three ways: the catalog source, and
  the live `mcp__freecad-buddy__*` tool list. Under AD-4 the typed tool list **is** the whole AI
  mutation surface, so an unlisted shipped mutation tool is a genuine inventory gap, not a
  bookkeeping slip.
- `project-structure.md:277` is internally broken: "25 Phase 0 tools, of which 17 … plus 7
  `verify_`" — 17+7=24, and `mcp-tools-design.md:225` explicitly excludes `debug_exec` from the
  count.

**Fix:** add `feature_body_create` to the `feature_` table and bump the counts; mark each of the
six absent tools with its phase and "not yet implemented"; correct the `project-structure.md:277`
arithmetic to 24 AI-visible + 1 operator-only.

### C4 — `project-structure.md` describes a repo layout that never shipped. CRITICAL

Three whole inventories in that doc point at missing files. Probed each:

- `hosts/`: doc lists flat `InitGui.py` and `gui_addon.py` — **both missing**. Real layout is
  packages (`gui_addon/{InitGui,bootstrap,pump}.py`, `gui_external/`, `headless/`, `main.py`,
  `tool_catalog.py`). The spine ring table and seed are already correct; only this doc is stale.
- `adapters/`: `export_oracles.py` (real name is singular `export_oracle.py`), `harness.py`
  (**never landed** — the gate runner is `benchmarks/runner.py` + `benchmarks/harness/`), and
  `skills_loader.py` (**no hits anywhere in the repo**; genuinely unbuilt).
- `benchmarks/`: doc's flat `golden/ dev/ fault-injection/` — **all three missing**. Real layout
  is per-gate (`g0/ g1/ g2/` each with their own splits) plus `_registry/` and `gate-artifacts/`.

Also actionable for an operator today: `project-structure.md:197` step 3 tells a contributor to
run `python scripts/install_addon_dev.py`, which **does not exist**. The dev-setup instructions
cannot be followed as written.

### H3 — Four resolved Phase-0 spikes still listed as open. HIGH

Spine Deferred (spine:349) lists `exportBinary` exposure, `renderToImage` without a GUI
document, VarSet exposure, and the conda `FreeCADCmd` path edge as "Empirical checks, first
week of Phase 0". All four are decided and written up: `docs/decisions/001` (serializer probe +
tag + degrade), `002` (FreeCADCmd-driven tests), `003` (render ladder), `004` (VarSet with
Spreadsheet fallback). The row should carry the outcomes or go.

### H4 — AD-24 budgets are unenforceable as written. HIGH

AD-24 (spine:229) says budgets "are **pass/fail at the gate**, not advisory" and (spine:225)
names `validation-harness-design.md` as owner of "timing capture, report banner". The spine
convention (spine:242) makes the AD-24 budget a mandatory banner field.

The harness design carries none of it: grep over the whole file for `AD-24`, `15 s`, `10 min`
returns nothing; the banner definition at `:145` lists the other four fields and omits it; and
§3.2's verdict ("gate = PASS iff all four legs") has no budget leg. So no gate can fail on a
budget — the exact failure AD-24's Prevents clause names, "measurable exit criteria discovered
unmet at phase exit".

### H5 — The skill-leg eval ladder has no rule. HIGH

intent L131 sets the skill-loaded bar at **≥9/10** at n=10; AD-14 (spine:149) carries only the
baseline ladder (**≥8/10**, escalate on 10/10), correctly quoted from L217. The two thresholds
are mutually unreachable under one ladder: a run scoring exactly 9/10 meets L131 and is
simultaneously stopped at n=10 and flagged low-confidence, so the criterion can be met and
non-citable at once. AD-14 never states what the skill leg must score.

### H6 — Three more compliant-but-incompatible pairs. HIGH

- **Visual-judge cadence.** AD-21 (spine:205) says both "judge findings feed the repair loop"
  (requires running before the loop ends) and "the visual leg runs per part, not per mutation".
  A repair iteration is neither. Per-iteration vs terminal differ ~4× in wall-clock on the same
  AD-24 gate criterion, and report different iteration counts against intent L260's ≤3 cap.
- **Export self-verification.** AD-9 (spine:109) fixes the *relation* ("completes only through
  its paired `verify_export_*`") but not the *invoker*, and its own orchestration-split sentence
  supports the caller-invokes reading. Result: two export tools with opposite failure semantics
  in one document — one returns `SPEC_FAILED` and deletes, the other returns `OK` and leaves a
  bad file. That reintroduces "bytes were written counted as success" through an ownership gap.
- **Anchor-frame tie-break.** AD-13 (spine:141) requires "one shared implementation" but not a
  *total, deterministic* derivation. `largest_planar_face` on a plate with two equal-area faces
  resolves by `Shape.Faces` order, which differs per FreeCAD leg — the same part passes on 1.1.x
  and fails on 1.0.x, and AD-14 reads the leg gap as overfitting (>15pp, no exit).

## Dimension sweep — what the spine never names

26 dimensions walked. **12 DECIDED, 3 PARTIAL, 11 SILENT, 0 covered by a Deferred row** —
every Deferred entry is a capability or a tuning value, never a structural dimension.

Three of the eleven need only a spine pointer, since the design docs already decide them fully:
the RPC wire compatibility rule (`integration-mcp-freecad.md` §2.2), contracts schema evolution
(`data-contracts-design.md:44`, additive-only within a major), and schema generation + drift
checking (`data-contracts-design.md:39`). The spine is what binds, so the pointer is still owed.

Eight are genuinely undecided: Addon Manager submission, our own package versioning/release,
metrics and health, persisted-state migration, retention and cleanup, data locations (C2),
HTTP auth (C1), and production-run observability.

One of these carries a conflict worth naming now: AD-12 puts `mcp` in an external venv that the
addon auto-discovers from its install path (AD-2, spine:53) — but an Addon-Manager install has
no sibling repo and no `.venv`, so auto-spawn resolution fails by construction for every store
user. The spine mentions "broken Addon Manager installs" only as a *Prevents* clause (spine:132).

## Counts

| Lens | CRITICAL | HIGH | MEDIUM | LOW | Total |
|---|---|---|---|---|---|
| intent vs spine | 0 | 1 | 3 | 4 | 8 |
| spine vs design core | 0 | 1 | 4 | 3 | 8 |
| spine vs design verify | 0 | 0 | 3 | 5 | 8 |
| code reality | 3 | 4 | 4 | 5 | 16 |
| adversary (divergence pairs) | 2 | 3 | 2 | 0 | 7 |
| **Total actionable** | **5** | **9** | **16** | **17** | **47** |

Code-reality carries the largest count because it checks two directions at once — doc claims
with no code, and shipped code no doc names. Its CRITICALs (C3, C4 above, plus the `hosts/`
layout) are all **doc-wrong**: in 15 of 16 findings the code is right and the document is stale.
The single exception is finding 10, the dead `check_imports.py` exemption, where code owes work.

Proposed spine changes: **1 new AD** (AD-25 data and artifact locations) and **amendments to
AD-2, AD-3, AD-9, AD-13, AD-14, AD-17, AD-21, AD-24**, plus Stack/Deferred/seed corrections for
the four stale claims.

## Clean areas — checked, stated clean

Recorded so absence of a finding is not mistaken for an unchecked item.

- **All 24 ADs trace to intent.** No orphan architecture, no speculative AD.
- **All 4 Out-of-Scope rows clean.** Grepped `fine-tun`, `training`, `CAM`, `toolpath`,
  `photorealistic`, `SaaS`, `multi-tenant` — zero violations. Environments (spine:310) positively
  confirms "single-tenant local-first".
- **Both Phase-5 pull-forwards carry explicit amendment notes** (AD-21 TechDraw and vision
  feedback). Not silent creep.
- **AD-13 sensitivity/false-alarm bar identical across 7 documents** (≥95 % / ≤5 %).
- **AD-17 closed status set** — 7 members, verified in `contracts/status.py:12-18`, no document
  invents a member.
- **AD-10 render cap 1920 px** matches `usecases/screenshot.py:34` and `tool_catalog.py:198`.
- **The AD-21 judge is genuinely fault-tested before its verdicts are citable**, and the
  enforcement is mechanical — the judge is a `_registry/validators.yaml` entry, so a stale
  sensitivity run blocks the gate automatically.
- **AD-22/AD-23 clean in full** — pairing, unit/frame boundary, inertials API, gate-decided markers.
- **RPC wire agrees across docs** — framing, `rpc_hello` handshake, `contract_version`, token,
  error-code split, marshal-timeout envelope shape, status origination layer.
- **Tool counts arithmetically sound** — 25 P0 / 49 total, verified by column sum.
- **AD-15's `check_skill_shape.py` status is reported honestly** as required-and-not-yet-built;
  confirmed no such script in `scripts/` and no skill step in `ci.yml`.

## Two items knowingly left open by the prior pass

Both confirmed still open, both need code not docs:

- `scripts/check_imports.py:79` — `QT_EXEMPT_ADAPTERS` still lists `adapters/marshal.py`, which
  imports no Qt. A dead exemption is a standing hole for a future Qt import to slip through.
- `scripts/check_skill_shape.py` — does not exist; AD-15's cap is convention only (Story 6.1).

One related note: AD-21 requires judge images ≥2048 px, but the render path hard-caps at 1920 in
two places (`usecases/screenshot.py:34`, `tool_catalog.py:198`) and `2048` appears nowhere in
`src/` or `benchmarks/`. AD-21 is Phase 3 and the cap is Phase 0, so this is latent rather than
broken — but the bypass path AD-21 assumes does not exist yet.
