# freecad-buddy — Manual UAT Plan (Epics 1-3 · Phases 0-2, plus Epic 8)

## 1. Overview

This suite validates the **shipped** tool surface of the FreeCAD MCP bridge: the **45 typed tools**
returned by `tool_specs()`, plus `script_exec`. `script_exec` is on by default. It is off when
`FREECAD_BUDDY_SCRIPT_EXEC=0` is set or the **Allow script_exec** preference is cleared, and when
`FREECAD_BUDDY_UNATTENDED=1` is set without `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`. A run reads
the tool count from `tools/list` (46 by default) and the FreeCAD version from
`query_capabilities.freecad_version`; no test case writes either as a literal. It covers the
work of Epics 1-3 (Phases 0-2) across all three hosts: the GUI addon path, the H1 headless host
(a front process and a FreeCAD worker), and the H2 external HTTP proxy on
`http://127.0.0.1:8765/mcp`.

The suite is driven by an agent operating the real application. MCP calls go through the connected
`mcp__freecad-buddy__*` tools; **every FreeCAD GUI action goes through `cua-driver`** against the
live FreeCAD window. Two existing scripts are wrapped as evidence producers, not re-derived:
`scripts/automation/run_mcp_e2e.py` (`_automation/e2e_report.json`) and
`scripts/automation/run_mcp_edge_cases.py` (`_automation/edge_report.json`).

`tests/uat` is the single home for manual UAT, per `CLAUDE.md` §9.

## 2. Layout

```
tests/uat/
  test-plan.md                 this file — scope, format contract, gates
  README.md                    how to execute a run
  coverage-matrix.md           tool/invariant → scenario traceability
  APPENDIX-A-deferred-coverage.md
  APPENDIX-B-environment-setup.md
  fixtures/                    fixture inventory
  testcases/
    TC-NN-<slug>.md            one file per test case
  run/
    <YYYY-MM-DD>-<NN>/         one folder per run, never reused
      report.md                verdicts per scenario
      bugs.md                  findings raised by this run
      evidence/                screenshots, renders, logs, json
```

**One run, one folder.** A run folder is written once and never edited by a later run. The folder
name is the run date plus a two-digit sequence (`2026-09-13-01`, `2026-09-13-02`). Evidence paths
inside a test case are written relative to `$RUN_DIR`, which the executing agent sets to that
folder before the first scenario.

## 3. Test case format

Every test case file has this shape, and nothing else:

```markdown
# TC-NN: <title>

<short statement of what the case proves and why it exists>

**Host**: <GUI via H2 proxy | H1 headless | both — and which scenarios use which>

## Preconditions
- [ ] <state that must exist before ANY scenario in this file>  (verify: <command>)

---

### TC-NN-MM: <scenario title, one behaviour>

**Priority**: Critical | High | Medium
**Design Ref**: <doc §section; source `file:line`>

**Given** <starting state>
**And** <more starting state>

**When** <the single action under test>
**And** <a following action, only if the behaviour needs a sequence>

**Then** <assertion> — verify: `<command producing a checkable result>`
**And** <assertion> — verify: `<command>`
**And** *(visual)* `view_fit_viewport { doc: "<handle>" }` returns `OK`
**And** *(visual)* the viewport captured with `cua-driver` shows <what the agent must see>
  — verify: `cua-driver call get_window_state` with
  `screenshot_out_file: "$RUN_DIR/evidence/tc-NN-MM-after.png"`, then `Read` it and judge

**Cleanup**:
```
<commands that restore state>
```
```

### Rules the format enforces

1. **Given / When / Then only.** No separate "Steps" and "Checkpoints" blocks. The sequence and the
   assertions live in one scenario so a reader never has to map step 3 onto CP5.
2. **One behaviour per scenario.** If a scenario needs two `When` blocks for two unrelated actions,
   it is two scenarios.
3. **Every `Then` is verifiable.** Each carries a command, a file path, or an exact string that can
   falsify it. "Works correctly" is not a `Then`.
4. **Every scenario ends with a visual `Then`, judged as a human.** Non-visual assertions (schema
   shape, exit code, audit line, error string) stay as ordinary `Then` lines in the same scenario;
   they are not padded with meaningless screenshots. The closing visual `Then` is what makes the
   scenario's effect — or its deliberate absence of effect — observable in the human's window. The
   agent `Read`s the PNG and judges the **pixels**, exactly as the user would: what shape is on
   screen, is it whole, is it clipped, is it the right thing. The judgement never cites an MCP
   field, a status, or a number as its evidence. **A `PASS` on a visual `Then` means the agent
   looked at the image and saw it.** If the image was not read, the scenario is `FAIL`.
5. **Auto-fit precedes every visual `Then`.** A visual assertion is preceded by a fit, so the
   object is inside the frame. An object outside the frame produces a screenshot that proves
   nothing, and a "nothing visible" reading indistinguishable from a real defect. Where the
   scenario's subject **is** the camera (TC-14), the fit is the action under test and the ordering
   is stated explicitly in that scenario.
   - Default fit: `mcp view_fit_viewport { doc: "<handle>" }`.
   - **When the fit itself is untrusted or unavailable** — the MCP surface is the thing under test,
     the scenario is proving a framing defect, the proxy is deliberately down, or the fit returns
     anything but `OK` — fit through the GUI instead. This path touches none of the code under test.

     **On FreeCAD 1.1.x the GUI fit is a toolbar click, not a menu call.**
     `invoke_menu(["View","Fit All"])` and `["View","Fit all"]` are both **refused** with
     `menu_path_unavailable`: Fit All is under `View > Standard Views`. Use the **Fit All** toolbar button
     resolved by `element_token` from a fresh `get_window_state` snapshot, which returns
     `route: "accessibility"` and demonstrably reframes the view. Element tokens are per-snapshot
     and keyed on `(pid, window_id)`, so take the snapshot immediately before the click.
   - **Show All before a fit of a golden or fault model.** Golden and fault `.FCStd` files have no
     `GuiDocument.xml` and open with every object hidden, so `view_fit_viewport` returns
     `SPEC_FAILED view_fit.nothing_to_frame`. Run
     `invoke_menu(["View","Visibility","Show All Objects"])` first; it resolves in the background.
   - A scenario that asserts the window is **unchanged** takes its `before.png` after the same fit,
     so the two captures are comparable.
6. **GUI interaction is `cua-driver` only.** Clicking, typing, menu invocation, window geometry, and
   screenshots go through `cua-driver`. No hand-rolled Qt calls, no `pyautogui`, no RPC socket
   written by hand.
7. **Preconditions and Cleanup are kept.** Preconditions are file-level (shared by every scenario)
   plus scenario-level `Given` lines. Cleanup is per scenario and runs only when every `Then` in
   that scenario passed.
8. **Screenshots land in `$RUN_DIR/evidence/`.** `cua-driver` writes them with
   `screenshot_out_file` so image bytes stay out of the agent's context until the agent chooses to
   `Read` one.
9. **Tree lines.** A `query_tree_summary` result is one text block. Its first line reads `<STATUS>: <N> objects, <M> shown[, <K> matches][, truncated][. Errors: ...]`; a `framing:` line follows when a 3D view is open. The **tree lines** are the lines after those. Results round floats to FreeCAD's `Decimals` preference (default 2), so a value check names the displayed value or a band of at least 0.01.

### Why the visual `Then` is not optional

**The MCP bridge is the thing under test. Its own output can never be the test result.**

Every status, envelope field, fingerprint, framing verdict, and rendered image comes from the code
this suite exists to judge. A bridge that reports `status: "OK"` and `fitted: true` while the
window shows an empty viewport passes every numeric assertion and fails the user completely. That
is not a hypothetical: the defect fixed in `636fb8a` reported a correct fit while the part occupied
about 5 % of the viewport.

`docs/intent.md` §Validation-First Discipline names this as the project's primary failure mode —
*the agent believing it did well when it did not* — and gives two counters: "end-artifact checks,
not process checks" and **"the actor never grades itself"**. An MCP render is a constructed scene
produced by the actor. Accepting it as proof is the actor grading itself.

So the evidence hierarchy in this suite is fixed:

| Rank | Artifact | Trust |
| --- | --- | --- |
| 1 | A `cua-driver` pixel capture of the real FreeCAD window, `Read` and judged by the agent | The test result. Independent of the code under test. |
| 2 | Filesystem, exit codes, audit lines, re-imported export files read by an outside tool | Corroborating. Produced outside the bridge's reporting path. |
| 3 | MCP envelope fields, statuses, `framing` verdicts, `query_screenshot` renders | **Claims under test, never evidence.** |

Rank-3 items are still asserted — that is most of what the `Then` lines do — but they are asserted
*as the bridge's claims*, and the closing visual is what decides whether a claim was true. Where an
MCP render and the window capture disagree, the window wins and the disagreement is written to
`$RUN_DIR/bugs.md`. Where the MCP fit tool is itself suspect, the fit is performed through the GUI
menu instead, so the framing that sets up the capture owes nothing to the code under test.

**Judge as the user, not as a program.** Read the image and say what is on the screen: is the part
there, is it whole, is it clipped at an edge, is it the shape the scenario asked for, did a dialog
appear. Do not reason from the envelope to what the picture must contain. A scenario whose visual
`Then` was skipped, inferred, or satisfied by an MCP render alone is reported **FAIL**, never
PASS-with-note.

## 4. Scope

### In-Scope
- All 45 shipped tools: `document_*` (7), `query_*` (8), `verify_*` (6), `export_*` (3),
  `sketch_*` (8), `feature_*` (11), `preview_dry_run` (1), `view_fit_viewport` (1)
- `script_exec` on by default, and its off postures (`FREECAD_BUDDY_SCRIPT_EXEC=0`,
  `FREECAD_BUDDY_UNATTENDED=1`) with the refusal they give
- Invariants AD-4, AD-5, AD-6, AD-7, AD-8, AD-9, AD-10, AD-17, AD-20, AD-24, AD-26, AD-27, AD-28
- The implemented part of AD-25: one `FCB_TMP_session_<pid>_<token>` temp folder per host under
  the workdir, and the session-start sweep (TC-11)
- The GUI addon path: auto-started RPC listener plus auto-spawned MCP HTTP proxy
- H1 headless host (`serve --transport stdio --mode inline`)
- H2 HTTP proxy host (`serve --transport http --mode rpc`) on `127.0.0.1:8765`
- GUI workflows driven with `cua-driver`: menus, tree, viewport, dialogs
- Visual fidelity of MCP renders against real FreeCAD viewport screenshots

### Out-of-Scope
- Epics 4-7 work: designer loop, repair loop, `verify_visual`, TechDraw judging, Phase-4 service.
  Every deferred item and its reason is listed in `APPENDIX-A-deferred-coverage.md`.
- The known AD conformance gaps (AD-3, and the remaining part of AD-25). They are recorded in TC-99 as
  expected-fail scenarios and are **not** part of the green gate.
- The two internal RPC-only tools `export_self_read_stl` and `export_self_read_3mf`. They are
  filtered out of `tools/list` by design; their absence is asserted in TC-01, nothing else.

## 5. Design References

| Document | Path | Covers |
| --- | --- | --- |
| Project intent | `docs/intent.md` | vision, validation-first discipline, phase gates |
| MCP tools design | `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/mcp-tools-design.md` | tool surface, envelopes, read-only profile |
| Verification design | `.../design/verification-design.md` | fingerprint, verify_shape/export, bands, oracles |
| Data contracts | `.../design/data-contracts-design.md` | ResultEnvelope, closed status set, fingerprint |
| MCP↔FreeCAD integration | `.../design/integration-mcp-freecad.md` | offscreen render, subgraph, AA |
| Architecture spine | `_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/ARCHITECTURE-SPINE.md` | AD-1..AD-33 decision records |
| Automation & verification standard | `.knowledge-base/technical/standards/testing/freecad-automation-verification.md` | H1 harness, env, invariants, traps |
| FreeCAD source-verify standard | `.knowledge-base/technical/standards/freecad/source-verify.md` | how to confirm FreeCAD behavior from source |

Design documents have drifted from the code. The installed code wins. Where a `Then` quotes a
message string, a schema, or a tool count, that value was read from the source, not from a design
document.

## 6. Test Environment

### Prerequisites
- FreeCAD 1.1.x installed; `$FREECAD_EXE` points at its launcher. The build under test is the
  live version, read from `query_capabilities.freecad_version` at the start of the run
- Addon linked at `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy` (a symlink to the repo
  `src/freecad_buddy`). Note `%APPDATA%\FreeCAD\Mod\` is legacy and empty.
- micromamba `fcb` env at `$FCB_ENV` (FreeCAD + `mcp` in one interpreter) for the H1 legs
- Repo `uv` env (`$PROJECT_ROOT/.venv`, Python 3.12.12) for the client and the sweep scripts
- `cua-driver` daemon running in an interactive session (Session ID ≥ 1)
- Golden models under `$PROJECT_ROOT/benchmarks/g0/golden-models/*.FCStd`
- Fault fixtures under `$PROJECT_ROOT/benchmarks/g0/fault-injection/` and
  `$PROJECT_ROOT/benchmarks/g0/export-fault-injection/`
- No FreeCAD process running before the run starts, and no document open once it is launched

Full step-by-step setup with per-step verify commands is in `APPENDIX-B-environment-setup.md`.

### Setup Commands
```bash
# H1-capable interpreter check
"$FCB_PYTHON" -c "import FreeCAD, mcp; print('H1 ok')"

# cua-driver daemon check (SessionId must be >= 1)
cua-driver status

# Proxy must be LISTENING with no manual serve command
netstat -ano | findstr :8765
```

### Environment Variables

**No test case hardcodes a machine path.** Every location is written as a variable, so the suite
runs on any checkout. Export these before the first scenario:

```bash
export PROJECT_ROOT="$(git rev-parse --show-toplevel)"
export RUN_DIR="$PROJECT_ROOT/tests/uat/run/$(date +%F)-01"     # absolute; pick the next free -NN
export FREECAD_EXE="C:/Program Files/FreeCAD 1.1/bin/freecad.exe"
export FCB_ENV="$USERPROFILE/micromamba/envs/fcb"
export FCB_PYTHON="$FCB_ENV/python.exe"
mkdir -p "$RUN_DIR/evidence"
```

`RUN_DIR` is **absolute**, because MCP `path` arguments must be absolute (a relative path resolves
against FreeCAD's own working directory, `C:\Program Files\FreeCAD 1.1\bin`, and the call fails).

The GUI host reads its operator settings once, at bridge start, from Edit > Preferences >
**FreeCAD Buddy**. A `FREECAD_BUDDY_*` variable that is set in the environment FreeCAD inherits wins
over the matching preference. The `operator settings:` line in `addon.log` gives each effective
value and its source (`env`, `preference`, `default` or `unset`). A change to either needs a FreeCAD restart;
only **Round numbers to FreeCAD display precision** applies at once.

| Variable | Purpose | Example |
| --- | --- | --- |
| `PROJECT_ROOT` | repository checkout root; every fixture and golden-model path is written against it | `D:/Work/.../freecad-buddy` |
| `RUN_DIR` | this run's folder, absolute; every evidence path is written against it | `$PROJECT_ROOT/tests/uat/run/2026-09-13-01` |
| `FREECAD_EXE` | FreeCAD launcher, passed to `cua-driver call launch_app` | `C:/Program Files/FreeCAD 1.1/bin/freecad.exe` |
| `FCB_ENV` | micromamba env holding FreeCAD **and** `mcp` in one interpreter, for the H1 legs | `$USERPROFILE/micromamba/envs/fcb` |
| `FCB_PYTHON` | that env's interpreter | `$FCB_ENV/python.exe` |
| `FREECAD_BUDDY_SCRIPT_EXEC` | `script_exec` switch: unset or `"1"` = on; any other value (use `"0"`) = off. Overrides the **Allow script_exec** preference (`ScriptExec`, default on) | `0` |
| `FREECAD_BUDDY_UNATTENDED` | marks an unattended run; exactly `"1"` turns `script_exec` off unless `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED=1`. Any other value is off | `1` |
| `FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED` | operator opt-in that keeps `script_exec` on in an unattended run; must be exactly `"1"` | `1` |
| `FREECAD_BUDDY_AUTO_APPROVE` | auto-approve posture: `"1"` = on, a mutation without `confirm` applies; any other value (use `"0"`) = confirm gate on. Overrides the **Auto-approve mutations** preference (default on). A sent `confirm` is checked in both postures | `0` |
| `FREECAD_BUDDY_AUDIT_LOG` | audit log path. Overrides the **Audit log file** preference. GUI default `%APPDATA%\FreeCAD\v1-1\freecad-buddy\audit.jsonl`; the headless default is cwd-relative `freecad-buddy-audit.jsonl` | `$RUN_DIR/evidence/audit.jsonl` |
| `FREECAD_BUDDY_WORKDIR` | session workdir. GUI default `%APPDATA%\FreeCAD\v1-1\freecad-buddy\workdir`; the headless default is cwd-relative `freecad-buddy-workdir` | `$RUN_DIR/workdir` |
| `FREECAD_BUDDY_LOG_FILE` | addon log path | `%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log` |
| `FREECAD_BUDDY_RPC_PORT` | fix the RPC listener port; a non-int value warns and falls back to ephemeral | `47111` |
| `FREECAD_BUDDY_RPC_DIR` | directory for the RPC discovery file (mode `0o600`) | `%TEMP%\fcb-rpc` |
| `FREECAD_BUDDY_MCP_CMD` | verbatim proxy launch command; space-split, no quoting support. Overrides the **MCP command** preference | `C:\path\python.exe -m ...` |
| `FREECAD_BUDDY_REPO` | legacy `uv` fallback for proxy launch | `$PROJECT_ROOT` |
| `FREECAD_BUDDY_SRC` | source root override | `D:\...\src` |
| `FREECAD_BUDDY_NO_AUTO_MCP` | suppress proxy auto-spawn; evaluated for **truthiness**, not `"1"`. Overrides the **Start the MCP server with FreeCAD** preference (default on) | `1` |

## 7. Test Case Index

| TC-ID | Name | Priority | Category | Design Ref |
| --- | --- | --- | --- | --- |
| TC-01 | Session lifecycle & transport | Critical | Session/Core | mcp-tools-design, spine §AD-2, §AD-12 |
| TC-02 | Document ingestion & handles | Critical | Session/Core | mcp-tools-design §documents |
| TC-03 | Sketch authoring | Critical | Modelling | mcp-tools-design §sketch |
| TC-04 | Feature modelling | Critical | Modelling | mcp-tools-design §feature |
| TC-05 | Mutation protocol & rollback | Critical | Mutation | verification-design §1 (run_mutation), §2, §3 |
| TC-06 | Render & GUI visual fidelity | Critical | Quality/Output | integration-mcp-freecad |
| TC-07 | Verification & export pairing | Critical | Verification | verification-design §6 |
| TC-08 | Preview/confirm & undo | Critical | Mutation | mcp-tools-design §3.8, §4 (Confirm) |
| TC-09 | Error contract & fault injection | Critical | Error handling | data-contracts-design §status |
| TC-10 | Concurrency, timeout & quarantine | High | Resilience | spine §AD-26, §AD-27 |
| TC-11 | Security posture & artifact hygiene | High | Security | spine §AD-3, §AD-25, global/security |
| TC-12 | GUI workflows (maximal) | High | GUI | integration-mcp-freecad, cua-driver |
| TC-13 | GUI ↔ MCP parity | Critical | GUI/Parity | mcp-tools-design §1.1, integration-mcp-freecad |
| TC-14 | Viewport framing & auto-fit (Epic 8) | Critical | Quality/Output | spine §AD-29..§AD-33, FR24-FR26 |
| TC-16 | Lean agent loop (Epic 11) | Critical | Mutation/Output | spine §AD-5, §AD-6, §AD-7, §AD-10, §AD-17 |
| TC-99 | AD conformance gaps (EXPECTED-FAIL) | Informational | Conformance | spine §AD-3, §AD-25 |

## 8. Test Data

Golden models under `benchmarks/g0/golden-models/`, with analytic expectations:

| Model | Expected volume (mm³) | Notes |
| --- | --- | --- |
| `box-10-20-30` | 6000.0 | single solid |
| `cylinder-r5-h20` | 1570.7963 | single solid |
| `sphere-r10` | 4188.7902 | single solid |
| `box40-hole-r5` | 15214.6018 | genus-1 |
| `two-box-compound` | 2000.0 | 2 solids; **centre of mass is `null`** |

Fault fixtures:
- `benchmarks/g0/fault-injection/wrong-volume/`
- `benchmarks/g0/fault-injection/non-watertight-open-shell/`
- `benchmarks/g0/export-fault-injection/`

Each fault fixture `case.yaml` carries reference `assertions.checks`. Those checks **must** be
passed into `verify_shape`. A bare `verify_shape` with no `checks` lets a wrong-but-valid shape
pass, so a fault scenario that omits them proves nothing.

## 9. Pass/Fail Criteria

This suite has **two independent gates**. A run reports both. They are never merged into one number.

### Gate 1 — Green gate (TC-01 .. TC-14)

This gate must be green for the suite to pass.

| Category | Pass Criteria |
| --- | --- |
| Functional | Golden volumes within 0.1 %; STEP round-trip plus STL/3MF oracle agreement |
| Quality | P0 (Critical) scenarios 100 % pass; P1 (High) scenarios ≥ 95 % |
| Resilience | Every invalid input and every planted fault returns the correct closed status; zero unhandled tracebacks in stderr |
| Contract | Exact message strings match the source verbatim; unknown keys are hard-rejected (`additionalProperties: false` on every input schema) |
| **Visual (mandatory)** | Every scenario closes with a visual `Then`, preceded by a fit. The evidence is a `cua-driver` pixel capture of the real FreeCAD window, `Read` and judged by the agent as a human would judge it. The MCP bridge is under test, so no MCP field, status, or render may stand as the visual evidence (§3). A scenario whose visual `Then` was skipped, inferred from the envelope, or satisfied by an MCP render alone is reported **FAIL**, never PASS-with-note. |

A failure in TC-01 .. TC-14 is a **regression**. It blocks the release.

### Gate 2 — Conformance gate (TC-99 only)

TC-99 holds scenarios that are **expected to fail**. Each names the AD it tests and the shipped
behaviour that deviates from it:

- **AD-3** — `:8765` has no authentication. `gui_external/entry.py` is a bare Starlette
  `Mount("/mcp")` with no middleware, no bearer check, no `Origin` check, no CORS. The loopback
  bind is the only control.
- **AD-25** (remaining part) — the per-host session temp folder and the start sweep are
  implemented and tested in TC-11. The gap: there is no `snap/ exports/ audit.log tmp/` layout; a
  snapshot is `<Name>.FCStd` in its own `mkdtemp` folder, not `<Name>.<txid>.FCStd`; the workdir
  is one shared folder, not session-named; the headless workdir default is cwd-relative
  (`usecases/documents.py:43`); the audit log is one undated shared file outside the workdir with
  no session field (`adapters/audit_log.py:24-26`).

Reading the result:
- A TC-99 scenario that **fails** is the recorded, accepted state. It does not block the release.
- A TC-99 scenario that **starts passing** is a signal to **promote** it into the green gate and
  close the gap in the spine. It is not a regression and must never be reported as one.
- A TC-99 scenario that fails **differently** than documented is a real finding. The documented
  deviation is part of the assertion.

## 10. Known Limitations

- **Retired parameter.** `query_tree_summary.max_nodes` is retired. Passing it now is a schema
  reject. So are the retired `root` parameter and the retired filters `exclude_types`,
  `renderable_only` and `visible_only`. The live filter object is closed and accepts exactly
  `types, name_pattern`.
- **Broken harness reader.** `_automation/live_mcp_manual.py` reads `tree["nodes"]`, but the
  response key is now `"tree"`. It returns `None` silently instead of failing. Do not treat a
  `None` from that harness as an empty tree.
- **Render needs GL.** The render leg requires a GL context. Render `Then` lines are reported SKIP
  when the render ladder reports `none`; the `cua-driver` window capture is still required, because
  the human's window exists whether or not the offscreen render does.
- **Module caching.** A running FreeCAD caches imported modules. A render-code change needs a
  FreeCAD restart in GUI mode before it takes effect.
- **H2 and H1 refuse the same way.** The GUI RPC listener behind the H2 proxy carries the
  non-string `doc` guard and the document-suspect logic (`adapters/rpc_listener.py:417-424`) and
  writes the audit pairs (`:426-449`). The MCP input schema types `doc` as a string on both hosts,
  so a non-string `doc` usually gets the schema refusal first. A `Then` on an audit line still
  names its host: on H1 the front writes the adapter pairs and the worker writes the bracket
  records.
- **cua element tokens do not persist.** `element_token` values are keyed on `(pid, window_id)` and
  are per-snapshot. `replay_trajectory` cannot re-resolve them across sessions, so a recorded
  trajectory is regression evidence only, never a re-runnable scenario step.
- **`--transport http --mode inline` is refused.** The CLI exits 2 with
  `transport '{t}' is not available yet; use --transport stdio.` This is by design, not a defect.
- **Client errors are quiet.** `INVALID_INPUT` and `TIMEOUT` log one INFO line, not a traceback.
  The full traceback stays in the envelope's machine `detail.data`. Unhandled faults
  (`RECOMPUTE_ERROR`, `WORKER_CRASHED`) still write a stderr traceback.
- **Default render honours visibility.** The default render (no `include`) omits objects with
  `Visibility=false`, mirroring the viewport. An explicit `include` still renders a named hidden
  object.
- **Dirty documents still render.** `query_screenshot` renders a document with a pending or broken
  recompute instead of hard-failing. The response carries `render.dirty_document: true`, and the
  before-equals-after read-only guard is skipped for an already-unstable document.
