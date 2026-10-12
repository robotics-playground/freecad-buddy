## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

**Artifacts hold latest state, not history.** Intent, specs, plans, and source record what the
system *is* — never progress notes, status updates, change logs, or decision narration. History
lives in git.

**Comments explain a non-obvious why.** No obvious comments. No provenance, no ticket numbers, no
"changed from X" notes. A tuned constant is the exception worth documenting: state the mechanism
and the measurement that justified the value, because the next reader will otherwise retune it
blind. [Reference](.knowledge-base/technical/standards/global/commenting.md).

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Communication

**Scope: this section governs chat replies AND every document you write.** Code follows section 9
and the standards, not this section.

| Output | Style |
|--------|-------|
| Chat replies, reports, plans, option lists | Caveman + ASD-STE100 |
| Docs: PRD, architecture, designs, epics, stories, specs, README, knowledge-base | Caveman + ASD-STE100 |
| Code, code comments, doc comments | `.knowledge-base/technical/standards/` + `typescript-clean-code` for TypeScript |
| Commit messages, PR descriptions | Conventional Commits, normal prose |

### Plain English

**Write for a reader fluent in the domain, not a native English speaker.** Difficulty should come from the problem, never from the wording.

- **Report and write documents in ASD-STE100 Simplified Technical English.** Approved plain words, active voice, and one instruction or idea per sentence. Small words, short sentences, short paragraphs. If a big word is unavoidable, explain it right after. This forbids idioms, figurative language, hedges, and rare vocabulary — say the literal thing.
- **Technical content is never simplified.** API names, code, error strings, `file:line`, and standard acronyms (HTTP, JSON, CI) stay verbatim. Simpler English never means a dropped caveat or a vaguer claim.
- A term of art with no plain equivalent: use it, define it once in a short clause.

The rules in this section are the complete reporting style. There is no separate style file.

### Caveman concise

Respond terse like smart caveman. All technical substance stay. Only fluff die.

- Drop: articles (a/an/the), filler (just/really/basically), pleasantries, hedging.
- Fragments OK. Short synonyms. Technical terms exact. Code unchanged.
- Pattern: `[thing] [action] [reason]. [next step].`
- Not: "Sure! I'd be happy to help you with that."
- Yes: "Bug in auth middleware. Fix:"

Switch level: `/caveman lite|full|ultra`. Stop: "stop caveman" or "normal mode".

Auto-clarity: drop caveman for security warnings, irreversible actions, or when the user is confused. Resume after.

**Documents get caveman too**, with two limits that keep them usable months later:
- Headings, tables, lists, links, code fences, and required field names keep their normal form.
- Do not drop a word if that makes the sentence ambiguous. Clarity beats brevity in a document.

### Code style is not caveman

Code is written for the standards, never compressed:

- Follow `.knowledge-base/technical/standards/` — see the applicable backend, frontend, global, and testing files.
- Load `typescript-clean-code` before you write or review TypeScript. It is reference-first:
  read the `references/<topic>/rules.md` it points to before you give advice or write code, and
  cite the rule you applied.
- Identifiers stay full words. No invented short forms.
- Code comments follow `.knowledge-base/technical/standards/global/commenting.md`, in normal prose.
- Commit messages and PR descriptions stay normal prose.

### Show real code, not descriptions

**The reader has not read this source.** Assume they can read code fluently but have never opened the file you are discussing.

- When you name code, give `file:line` and quote the line. A bare symbol name costs the reader a lookup.
- Show the real value, before and after. A 5-line trace beats a 5-sentence description.
- Describing code in prose when you could quote it is the mistake.

## 6. Project Operating Model

- Before substantive work:
  1. Read `.knowledge-base/technical/standards/index.md`.
  2. Read `.knowledge-base/technical/application-design/index.md`.
  3. Read `ARCHITECTURE-SPINE.md` and every design document that covers the area you will
   touch. Both are catalogued in section 15. The spine holds the `AD-n` decisions; each design
   document lists in its front matter the `AD-n` it implements. Do not write code or a spec for
   an area whose design document you have not read. If no design document covers the area,
   say so before you start.
  4. Read the project branch's own `docs/` and `README.md` — they define the scope, and
   they win any conflict about what the assistant should do.
  5. Read the branch's `.knowledge-base/` research only when you need the *evidence*
   behind a decision, or when touching a selector or endpoint.
  6. Load skills applicable to the task and technology (see section 13).
- BMAD writes generated artifacts to `.ai-artifacts/`. Planning artifacts go to
  `.ai-artifacts/planning-artifacts/`, implementation records to
  `.ai-artifacts/implementation-artifacts/`.
- Design conflicts with code or requirements → stop, cite evidence, propose correction, and
  get agreement. Never silently diverge.
- Never auto commit without approval from the user.
- Never include a `Co-Authored-By` trailer in a commit message.

## 7. Brainstorm

**Understand problem before designing solution.**

- Inspect existing project context before proposing changes.
- Establish intent, users, constraints, assumptions, and measurable success criteria.
- Ask focused questions when ambiguity could change the result.
- Present 2-3 viable approaches with trade-offs and a recommendation.
- Prefer smallest solution that satisfies current need.
- Get agreement on direction before architecture or implementation. Simple task may need only short design, but still needs explicit shared understanding.

## 8. Architect

**Design against intended contracts and actual code.**

- Treat PRD, architecture, UX, designs, diagrams, and wireframes as intended-system contract.
- Compare intended contract with current implementation before deciding.
- For structural code questions, read the current source before deciding. Do not rely on memory of a previous branch.
- Define module boundaries, interfaces, data flow, failure behavior, migration impact, security concerns, and test strategy.
- Follow the patterns the experiment already uses unless documented evidence supports a change. For a TypeScript service, that means the Clean Architecture and dependency-injection patterns in the knowledge base. 
- Record decisions and trade-offs. Make design implementation-ready: no hidden choices left for developer.

## 9. Develop

### Testing standards

- **Test naming:** `Should <expected outcome> When <condition>`.
- **Test structure:** every body divided by `// Arrange`, `// Act`, `// Assert`, in that order. A phase that would be empty → hoist inputs into named variables so the phase is real. Throwing call → Act assigns the thunk (`const act = () => fn(input)`), Assert applies the matcher.
- **Conventions:** the system under test is named `target`; mocks are `mockXxx`.
- **Specs live beside their subject** as `*.spec.ts`.
- **Pure functions get fixture-driven unit specs.** Fixture coverage is defined per
  project branch; keep captures redacted.
- Manual smoke test of the FreeCAD GUI is agent work: drive the real application with
  `cua-driver` (see section 17). Only steps that need a human decision — accepting a visual
  result, approving a destructive action — stay with the operator.

**Detail:**
- `.knowledge-base/technical/standards/testing/unit-testing.md`
- `.knowledge-base/technical/standards/testing/e2e-testing.md`
- `skill(name="typescript-unit-testing")`
- `skill(name="typescript-e2e-testing")`

**UAT:**
- `skill(name="manual-testing")`
- `skill(name="cua-driver")`
- Directory: `tests/uat`
- GUI end-to-end harness — launch, install modes, MCP over HTTP, canary, visual check, shutdown: [freecad-gui-e2e-harness](.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md). Read it before you launch FreeCAD for any test.
- Native FreeCAD validation — prove a built part with FreeCAD's own Check Geometry, an in-FreeCAD kernel macro and Fit all screenshots, driven with `cua-driver`; includes a subagent brief and troubleshooting: [freecad-native-validation](.knowledge-base/technical/standards/testing/freecad-native-validation.md). Use it whenever a result must not rest on MCP output alone.
- FreeCAD GUI operations:
  - Shutdown all FreeCAD instances before starting the tests. Verify that no FreeCAD processes are running.
  - Ensure no documents are open in the FreeCAD GUI before running UAT tests.
  - Use absolute paths for any file operations to avoid issues with FreeCAD's working directory.
  - Agent always needs to do the visual check, never trust automated verification alone or the MCP results.

### Commands

Quality checks after any implementation or bug fix, in this order:

```bash
npm run lint
npm run format
npm run typecheck
```

## 10. Smell Check

**Twelve guide words. Run them on your own diff before you say done.**

Fowler's smells (*Refactoring*, 1999). You already know each one and its
refactoring. The value is the checklist, not the definition: without names, a
diff "looks fine"; with names, you find the shape.

Shotgun Surgery · Feature Envy · Data Clumps · Long Method · Divergent Change ·
Duplicated Code · Large Class · Long Parameter List · Primitive Obsession ·
Message Chains · Dead Code · Speculative Generality

### Rules of use

- **When.** After tests pass, before the completion report. Also when reading
  unfamiliar code, to judge whether a change is safe.
- **How.** Read your own diff, one pass per smell. Answer yes or no.
- **A yes is a question, not a verdict.** Some are correct on purpose. An
  undefended yes is a defect.
- **Named, not vague.** Report the smell name, `file:line`, and the quoted line.
  "Feature Envy at `handler.ts:42`" is actionable. "Could be cleaner" is not.
- **Scope stays surgical.** Section 3 wins. Fix smells your diff created. Name
  pre-existing smells in the report; do not fix them unasked.
- **Owner rules beat Fowler.** On conflict, `.knowledge-base/technical/standards/`
  and `typescript-clean-code` (`references/smells/rules.md`) win. Three that
  already decide cases here: models are classes (Data Clumps), delete do not
  deprecate (Dead Code), no abstraction for a single caller (Speculative
  Generality).
- **Report what you found.** List the smells you fixed, and any you accepted
  with the reason.

## 11. Critical Guardrails

### Verification

- Verification must be able to falsify the completion claim.
- Test exact reported failure mode, not convenient proxy metric.
- Inspect actual artifact: code diff, rendered UI, logs, emitted event, API response, or persisted data as applicable.
- Treat another agent's “done” report as hypothesis. Re-run or re-inspect material result independently.
- State what was verified and what remains unverified.

### Git Safety

- Never commit, merge, rebase, reset, or push directly to `main`, `master`, `develop`, `dev`, `stage`, `staging`, `release`, `test`, `uat`, `prod`, or `production` without explicit confirmation naming that branch and operation.
- Commit messages and pull requests contain no AI attribution or `Co-Authored-By` trailer.
- Use Conventional Commits. Keep workspace commit and service-repository commits separate.

## 12. Repo Structure

Full tree, packaging, environments, and CI layout:
[design/project-structure.md](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/project-structure.md).
The summary below is the working map; that document decides any disagreement about layout.

Single installable package, four Clean Architecture rings (AD-1). Imports cross ring boundaries **inward only**: `contracts/` ← `usecases/` ← `adapters/` ← `hosts/`. `check_imports.py` enforces it; don't fight it, fix the placement.

- `src/freecad_buddy/contracts/` — wire types, stdlib ONLY (no FreeCAD, no third-party). `status` `envelope` `report` `job` `audit` `diff` `document` `fingerprint` `rpc` `assertions` `render` `numbers`; `jsonschema/` generated + drift-checked.
- `src/freecad_buddy/usecases/` — tool impls, stdlib + FreeCAD App via `shim.py`. `documents` `queries` `verify` `exports` `screenshot` `fingerprint` `capabilities` `script_exec` `stats` `shim`.
- `src/freecad_buddy/adapters/` — MCP + RPC + oracles, external-process deps live here. `mcp_server` `rpc_client` `rpc_listener` `rpc_dispatch` `marshal` (QtCore only) `render_probe` (Qt) `audit_log` `export_oracle` `export_verdict`.
- `src/freecad_buddy/hosts/` — entry points; Qt/`FreeCADGui` legal here. `gui_addon/` (`InitGui` `bootstrap` `pump` `preferences`), `gui_external/`, `headless/`, `main.py`, `tool_catalog.py`.
- `contracts/` ← `usecases/` ← `adapters/` ← `hosts/`; `adapters/__init__.py` + `hosts/__init__.py` stay EMPTY.
- `benchmarks/` — gate runner + data. `runner.py`, `harness/`, `g0/` (golden-models, fault-injection, cases), `heldout/` (SEALED — never open outside `gate run --exit`), `_registry/` (validators + provenance).
- `tests/` — two worlds, never mixed. `infc/` runs under `FreeCADCmd` with stdlib `unittest` (via `run_tests.py`); `external/` runs under pytest in uv env.
- `scripts/` — durable repo commands: `check_imports` `check_skill_shape`/`check_status_vocab`/`check_provenance` `gen_schemas` `build_addon`, `automation/`.
- `skills/` — one dir per skill (AD-15): `SKILL.md` (4 sections, ≤1,500 words) + `references/`. Agent-agnostic knowledge, never imported by code.
- `addon/` — `package.xml` addon metadata; `dist/` — built addon output (`build_addon.py`).
- `docs/decisions/` — Phase 0 decision notes; `docs/references/` — FreeCAD source/wiki, freecad-mcp, text-to-cad.
- `_bmad-output/` — planning artifacts (spine, design docs, epics, sprint-status); `_automation/` — live MCP manual harness.

### Branch prefixes

Follow release-please patterns

## 13. Skill Catalog

Load the required skill BEFORE you start the task, not after.

### By task type

| Task type | Required skill |
| --- | --- |
| Implement any feature or bugfix | `bmad-build` |
| Debug a bug, test failure, or odd runtime behavior | `bmad-build` + `ultrathink-protocol` |
| A fix failed twice, or the cause is still unknown | `ultrathink-protocol` (verify cause before any fix) |
| New feature or behavior change | `bmad-brainstorming` (before design) |
| Turn an idea or notes into a spec | `bmad-spec` |
| Design architecture across parts of a system | `bmad-architecture` |
| Multi-step work from a spec | `bmad-spec` (break into stories), then `bmad-build` |
| Execute an implementation plan | `bmad-build` or `bmad-build-auto` (unattended) |
| Investigate an external system | `bmad-deep-recon` |
| Claim work complete / fixed / passing | `bmad-review` |
| Pre-merge or major-feature review | `bmad-code-review` |
| Walk the user through a change for human review | `bmad-walkthrough` |
| Run the whole implementation pipeline, or check status / resume | `bmad-auto` |

### By technology

| Task type | Required skill |
| --- | --- |
| Write or review TypeScript. Code design, refactoring, TDD, bug fix, PR review | `typescript-clean-code` |
| Write or run unit tests | `typescript-unit-testing` |
| Write or run end-to-end tests | `typescript-e2e-testing` |
| Plan, write, or run manual tests | `manual-testing` |
| Manual test the FreeCAD GUI, or drive any native application | `cua-driver` |
| Automate a browser | `playwright-cli` |

Every other BMAD skill is installed but not catalogued here. Invoke one by name only when the
user names it.

## 14. Knowledge Base Catalog

`.knowledge-base/index.json` holds the machine-readable catalog with tags and descriptions.
Read `.knowledge-base/technical/standards/index.md` first — it maps standards to roles.

### Global — applies to all work

| Standard | Covers |
|----------|--------|
| [code-quality](.knowledge-base/technical/standards/global/code-quality.md) | Quality gates and review bar |
| [commenting](.knowledge-base/technical/standards/global/commenting.md) | When a comment earns its place. See section 3 |
| [conventions](.knowledge-base/technical/standards/global/conventions.md) | Naming and file conventions |
| [security](.knowledge-base/technical/standards/global/security.md) | Security rules for code and requirements |
| [tech-stack](.knowledge-base/technical/standards/global/tech-stack.md) | Approved stack and versions |

### Backend

| Standard | Covers |
|----------|--------|
| [coding-style](.knowledge-base/technical/standards/backend/coding-style.md) | Naming, SOLID, TypeScript, formatting |
| [api](.knowledge-base/technical/standards/backend/api.md) | REST endpoint naming, versioning, status codes |
| [error-handling](.knowledge-base/technical/standards/backend/error-handling.md) | Error handling patterns |
| [error-codes](.knowledge-base/technical/standards/backend/error-codes.md) | Error code scheme |
| [logging](.knowledge-base/technical/standards/backend/logging.md) | What and how to log |
| [validation](.knowledge-base/technical/standards/backend/validation.md) | Input validation patterns |
| [models](.knowledge-base/technical/standards/backend/models.md) | Model rules. Models are classes |
| [usecases](.knowledge-base/technical/standards/backend/usecases.md) | Use-case layer rules |
| [queries](.knowledge-base/technical/standards/backend/queries.md) | Query layer rules |
| [migrations](.knowledge-base/technical/standards/backend/migrations.md) | Schema migration rules |
| [domain-events](.knowledge-base/technical/standards/backend/domain-events.md) | Event structure, publishing, naming, anti-patterns |
| [kafka](.knowledge-base/technical/standards/backend/kafka.md) | Kafka usage |
| [telemetry](.knowledge-base/technical/standards/backend/telemetry.md) | Tracing and metrics |
| [design-pattern-factory](.knowledge-base/technical/standards/backend/design-pattern-factory.md) | Factory with array injection, O(1) strategy lookup |
| [design-pattern-factory-and-explorer](.knowledge-base/technical/standards/backend/design-pattern-factory-and-explorer.md) | Factory with decorator auto-discovery |
| [design-pattern-chain-of-repository](.knowledge-base/technical/standards/backend/design-pattern-chain-of-repository.md) | Chain of Responsibility + Repository for data enrichment |

### Frontend

| Standard | Covers |
|----------|--------|
| [components](.knowledge-base/technical/standards/frontend/components.md) | Component structure |
| [css](.knowledge-base/technical/standards/frontend/css.md) | CSS rules |
| [responsive](.knowledge-base/technical/standards/frontend/responsive.md) | Responsive layout rules |
| [accessibility](.knowledge-base/technical/standards/frontend/accessibility.md) | Accessibility requirements |

### Testing

| Standard | Covers |
|----------|--------|
| [unit-testing](.knowledge-base/technical/standards/testing/unit-testing.md) | Unit test structure and coverage |
| [e2e-testing](.knowledge-base/technical/standards/testing/e2e-testing.md) | End-to-end test rules |

### Application design

| Document | Covers |
|----------|--------|
| [index](.knowledge-base/technical/application-design/index.md) | System design entry point |
| [clean-architecture-nestjs](.knowledge-base/technical/application-design/clean-architecture-nestjs.md) | Clean Architecture layering for NestJS |

## 15. Authoritative References

- [Development standards](.knowledge-base/technical/standards/index.md) — standards by role
- [System design](.knowledge-base/technical/application-design/index.md)
- [Knowledge base catalog](.knowledge-base/index.json) — tags and descriptions for every standard
- [README](README.md) — branching model and contribution rules
- BMAD config: `_bmad/bmm/config.yaml`
- [FreeCAD source-verify standard](.knowledge-base/technical/standards/freecad/source-verify.md)
- [FreeCAD automation & verification](.knowledge-base/technical/standards/testing/freecad-automation-verification.md)
- [Planning artifacts](_bmad-output/planning-artifacts/)
- [FreeCAD Source Code](docs/references/FreeCAD/)
- [FreeCAD Wiki](docs/references/FreeCAD-wiki/)
- [FreeCAD MCP](docs/references/freecad-mcp/)
- [Text to CAD](docs/references/text-to-cad/)

**Precedence when documents disagree:** the installed CODE wins over any document — verify,
then propose a doc correction.

### Design documents

Architecture root: `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/`.
[ARCHITECTURE-SPINE.md](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/ARCHITECTURE-SPINE.md)
holds the decision records `AD-n`. Every design document below binds to it and lists the `AD-n` it
implements in its front matter. Read the design document for the area you touch before you change
code there.

Path prefix for the table: `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/`.

| Document | Covers |
|----------|--------|
| [project-structure](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/project-structure.md) | Repository tree, packaging, Python/FreeCAD version per CI leg, environments, CI workflow layout |
| [component-design](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/component-design.md) | The four rings, each module's responsibility, and the import rules between them |
| [data-contracts-design](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/data-contracts-design.md) | `contracts/` wire types, status vocabulary, result envelope, generated JSON Schemas |
| [mcp-tools-design](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md) | MCP tool catalog for Phases 0–2: names, inputs, outputs, errors |
| [integration-mcp-freecad](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md) | The MCP-to-FreeCAD bridge: hosts, RPC listener, marshal, render rig |
| [integration-mcp-clients](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-clients.md) | Client side: Claude Code, local LLM, future agent clients |
| [verification-design](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md) | Verification subsystem: assertions, tolerances, paired export verdicts |
| [validation-harness-design](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/validation-harness-design.md) | `benchmarks/` gate runner, fault suites, validator registry, provenance |
| [security-and-service-design](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/security-and-service-design.md) | Trust boundaries, bounded execution, service posture |
| [skills-structure-design](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/skills-structure-design.md) | `skills/` library shape: `SKILL.md` sections, size limit, `references/` |
| [sequence-diagrams](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/sequence-diagrams.md) | End-to-end call flows per scenario |
| [robot-description-and-sourcing-design](_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/robot-description-and-sourcing-design.md) | Phase 5: URDF/SDF export and part sourcing |

Design reviews live beside the designs in `reviews/`. They record drift found between intent,
design, and code. Read one only when you need the evidence behind a design decision.

## 16. Running the MCP Bridge (GUI mode)

**Opening FreeCAD is the only step — the addon starts everything.**

- On FreeCAD GUI start the addon (`gui_addon/bootstrap.start_bridge`) starts the in-FreeCAD **RPC listener** (stdlib, ephemeral localhost port) AND auto-spawns the **external MCP HTTP proxy** on `http://127.0.0.1:8765/mcp` as a child process. Both are torn down on FreeCAD quit.
- **Do NOT run `freecad-buddy serve --mode rpc` by hand** to talk to the live GUI, and do not hand-roll RPC sockets — just open FreeCAD, then use the connected `mcp__freecad-buddy__*` tools. The proxy is spawned for you.
- `.mcp.json` is a plain HTTP entry — no `serve`/`rpc`/`command` in it:
  ```json
  { "mcpServers": { "freecad-buddy": { "type": "http", "url": "http://127.0.0.1:8765/mcp" } } }
  ```
- **Why the proxy is a separate process (AD-2/AD-12):** the MCP/FastMCP libs are third-party and may not be imported inside FreeCAD's bundled Python. The addon spawns the proxy in an **external venv interpreter** (which has `mcp`): the repo venv in a dev install, the managed venv in a release install. It never imports `mcp` itself.
- **No env vars required.** Proxy launch resolution (bootstrap `_mcp_proxy_command`, then `_start_mcp_proxy`): `FREECAD_BUDDY_MCP_CMD` (verbatim override, optional) → else **auto-discover the project `.venv`/`venv` python next to the installed addon** (walk from the package's `__file__` to the repo root; a built copy finds the venv through the `repo-root.txt` marker written by `build_addon.py`) and run the serve module directly → else legacy `FREECAD_BUDDY_REPO`+`uv` fallback → else the **managed venv** `<FreeCAD user app data>/FreeCADBuddy/venv` when its `freecad-buddy-wheel.sha256` marker equals the SHA-256 of the wheel in `<addon>/wheels/` → else, in a release install with `uv` found, **provision** that venv on a daemon thread (`uv venv --clear --python >=3.11`, `uv pip install` the wheel; lock `FreeCADBuddy/venv.lock`, stale after 10 min; log `freecad-buddy/provision.log`) and then spawn → else one log line. So dev setup is "junction the addon, `uv sync`, open FreeCAD"; release setup is "extract `FreeCADBuddy-<ver>.zip` into `Mod`, install `uv`, open FreeCAD". If `:8765` is already served the addon does not double-spawn.
- **Operator settings:** Edit > Preferences > **FreeCAD Buddy** (keys under `User parameter:BaseApp/Preferences/Mod/FreeCADBuddy`): `AutoApprove` (default on), `ScriptExec` (default on; registers `script_exec`), `AutoStartMcp` (default on; off = `FREECAD_BUDDY_NO_AUTO_MCP=1`), `McpCommand`, `UvPath`, `AuditLogPath`. Precedence: a set `FREECAD_BUDDY_*` env var wins → else the preference → else the default. The bridge reads them once at start and writes the result into its own environment, so the proxy child inherits it; restart FreeCAD to apply. `RoundToDisplay` stays per call. Default audit log `<FreeCAD user app data>/freecad-buddy/audit.jsonl`, default workdir `<FreeCAD user app data>/freecad-buddy/workdir`. `addon.log` records the effective values in one `operator settings:` line. Env-only: `FREECAD_BUDDY_UNATTENDED=1` marks an unattended run and turns `script_exec` off unless `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`; for both, any value other than exactly `1` is off.
- Headless automation (CI, the `run_mcp_*` sweeps) is unaffected: it uses the single-process H1 stdio host, not this proxy.