# UAT run 2026-10-08-02 — Phase B2 results (TC-08-18, TC-11-08)

Date: 2026-10-08. Branch `feat/epic-4-spec-to-part`.
RUN_DIR: `D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-08-02`.

## Summary

| Scenario | Result |
|----------|--------|
| TC-08-18 Headless auto-approves by default; any value other than "1" turns the gate on | **PASS** (all 14 assertions) |
| TC-11-08 Auto-approve warns at startup and audits every auto-approved mutation | **PASS** (all 10 assertions) |

No product defect found for the behaviour under test. Two test-case defects (stale `file:line`
references, a cleanup step that deletes evidence) and three side observations are listed at the end.

## Environment

- GUI: FreeCAD 1.1.4, pid 10600, window_id 595056. Started with `FREECAD_BUDDY_AUTO_APPROVE=0`.
  Proof: `addon.log` lines of the latest launch (`2026-10-08 11:50:50`–`11:50:51`) have no
  `SECURITY: mutation auto-approve ENABLED` line. The two earlier launches (10:54, 11:40) have it.
  GUI was not restarted or quit. It is still running, with no document open.
- GUI bridge: `:8765` LISTENING (pid 27632). Calls through `tc16_calls.py`, logged in `phaseB2-calls.jsonl`.
- H1 host: `C:/Users/thuan/micromamba/envs/fcb/python.exe -m freecad_buddy.hosts.main serve --transport stdio --mode inline`.
  fcb env FreeCAD is 1.1.3. `import FreeCAD, mcp` succeeds (`tc-08-18-given-fcb-import.txt`).
  `freecad_buddy` resolves to `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy`, a junction to
  `D:\Work\Personal\Sources\freecad-buddy\src\freecad_buddy`, so it is the same source.
- Driver: `evidence/h1_posture.py`. It runs from the repo uv env, starts H1 with
  `mcp.client.stdio.stdio_client`, and captures stderr per run. The child env is a full copy of
  `os.environ` with `FREECAD_BUDDY_AUTO_APPROVE` removed (`env.pop`) and then set only when the
  posture is not `unset`. Each run prints `present=False value=None` for the unset runs and
  `present=True value='1'|'0'|'true'` for the others.
- **Operator acceptance (TC-11-08 Given):** running mutations without a confirm token was
  **accepted by operator for UAT run 2026-10-08-02**.

## Deviations

1. **H1 interpreter (TC-11-08).** The scenario writes `uv run python -m freecad_buddy.hosts.main serve ...`.
   The uv env has no FreeCAD. H1 ran under the fcb interpreter, same as TC-08-18.
2. **Fixture is a saved file, opened in each H1 process.** TC-08-18 Given says "a saved document".
   Building the fixture inside each posture run would write three extra `approval` lines
   (`feature_body_create`, `sketch_create`, `sketch_add_geometry`) into the audit file, and the
   "exactly one approval line" assertions could not be judged. So one H1 process per TC built the
   fixture (body + 20x20 mm sketch, `post_verify.fully_constrained: true`) and saved it, with its own
   audit file. Each posture run is then a new H1 process: `document_open` the fixture,
   `feature_pad` (30 mm) with no `confirm`. No handle crosses a process.
   Fixtures: `tc-08-18-fixture.FCStd`, `tc-11-08-fixture.FCStd`. Fixture audit: `tc-*-fixture-audit.jsonl`.
3. **Separate audit files for the other postures.** Unset run → the file the scenario names
   (`tc-08-18-approve.jsonl`, `tc-11-08-approve.jsonl`). `=1`, `=0`, `=true` runs →
   `tc-08-18-audit-eq1.jsonl`, `tc-*-audit-eq0.jsonl`, `tc-*-audit-eqtrue.jsonl`.
4. **Golden box made visible.** `box-10-20-30.FCStd` opens with `Box` hidden (`query_tree_summary`
   line `- [FEATURE] Box`). Before each before-capture, a Visibility-only
   `feature_set_parameters {feature:"Box", parameters:{Visibility:true}}` was sent over the GUI bridge.
   The `=0` GUI gate allowed it (display-state path, `usecases/confirm.py:310-321`). Status `OK`,
   `fingerprint_before == fingerprint_after` (`554070c8...`). The file on disk is unchanged
   (`git status benchmarks/` is clean).
5. **Fit.** `view_fit_viewport` returned `OK` for all four fits, so the GUI Fit All toolbar path was
   not needed and was not exercised.
6. **Cleanup keeps evidence.** Both cleanups say `rm -f ... approve.jsonl`. The audit files were
   kept as run evidence. H1 hosts are stopped (each run's `stdio_client` context exits; a process
   scan for `freecad_buddy.hosts.main` finds no server left). The GUI golden box was closed after
   each passing scenario (`document_close` → `closed: true`; final `document_list` → `0 open document(s)`).
7. **Precondition note (TC-08 file).** `ls -d "$TEMP"/FCB_TMP_prev_*` is not empty: one stale
   `FCB_TMP_prev_rtoduji3` (created 2026-09-13 11:06, `Permission denied` on listing). It is older
   than this run and not made by it. It has no effect on TC-08-18, which runs no preview.

## TC-08-18 — PASS

Golden box GUI handle: `fcb-doc:Vg_6ax-ivwXipuFchtxzlQ`.
H1 handles: unset run `fcb-doc:l3PVQIMsQGe2u8-7071rTQ`.

### Given

| Given | Result | Actual |
|-------|--------|--------|
| `"$FCB_PYTHON" -c "import FreeCAD, mcp"` succeeds | PASS | `FCB import ok` |
| Saved document with body + fully constrained 20x20 sketch | PASS | `tc-08-18-fixture.FCStd`; `sketch_add_geometry` `post_verify.fully_constrained: true`, `recompute_clean: true`, `is_valid: true` |
| Golden model open in GUI | PASS | `document_open` → `OK`, handle above |
| Framed before capture | PASS | `view_fit_viewport` → `OK`, `fitted: true` |
| Before capture | PASS | `tc-08-18-before.png` |

### Then

| # | Assertion | Result | Actual |
|---|-----------|--------|--------|
| 1 | Unset approves | PASS | `unset/pad-noconfirm`: no `confirm` in args, `status: "OK"`, `mutation.schema: "fcb.mutation/2"`, `changed: [Body, Pad]`, `post_verify.passed: true` |
| 2 | Sent token checked under auto-approve | PASS | `unset/pad-forged` (`confirm: {preview_id: "fcb-preview:forged.AAAA"}`): `status: "INVALID_INPUT"`, message `confirm.preview_id carries an invalid signature` |
| 3 | `=1` approves | PASS | `eq1/pad-noconfirm`: no `confirm`, `status: "OK"`, `changed: [Body, Pad]` |
| 4 | `0` turns the gate on | PASS | `eq0/pad-noconfirm`: `INVALID_INPUT`, `this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id` |
| 5 | Other value turns the gate on | PASS | `eqtrue/pad-noconfirm`: same `INVALID_INPUT` and same exact string |
| 6 | Startup posture announced | PASS | unset stderr line 3 and `=1` stderr line 3: `WARNING freecad_buddy.mcp_server: SECURITY: mutation auto-approve ENABLED (FREECAD_BUDDY_AUTO_APPROVE unset or 1; set it to 0 to require preview_id)`. `grep -c` on `=0` and `=true` stderr: `0` |
| 7 | Approval audited | PASS | `grep '"mode": *"auto_approve"' tc-08-18-approve.jsonl` → 1 line: `tool: "feature_pad"`, `doc.handle` and `approval.doc` = `fcb-doc:l3PVQIMsQGe2u8-7071rTQ`, `approval.source: "FREECAD_BUDDY_AUTO_APPROVE"` |
| 8 | Audited approval carries no token | PASS | `approval.args_digest: "6f69c5d2...5eec"` present; `grep -c preview_id tc-08-18-approve.jsonl` → `0` |
| 9 | Forged-token call wrote no approval | PASS | `grep -c '"event": "approval"'` → `1`. The forged call wrote only a `mutation` before/after pair with `verify_verdict: "INVALID_INPUT"`, `fingerprint_before: null` |
| 10 | (visual) framed with same camera | PASS | `view_fit_viewport` → `OK`, `fitted: true` |
| 11 | (visual) GUI window not touched | PASS | See visual judgement below |

Corroborating: `=1` audit has 1 approval line; `=0` and `=true` audit files have 0 approval lines.

**Visual judgement (pixels).** `tc-08-18-before.png`: FreeCAD 1.1.4 window, title
`* box-10-20-30`. Model tree: `box-10-20-30` > `Box`, eye icon on. Viewport: one grey rectangular
box in isometric view, tall along Z, whole, centred, not clipped. Tasks panel "Start Part / New
Body" at right. No dialog. `tc-08-18-after.png`: the same window, the same single box at the same
size and position, the same tree with one `Box`, the same Tasks panel. No Body, no Pad, no new
object, no dialog. By eye the two images are identical. (Corroborating: `cmp` says the PNG bytes
are identical; GUI `document_list` after the runs holds only the box handle.)

## TC-11-08 — PASS

Golden box GUI handle: `fcb-doc:Z7wOQoP6Y4SwyKMbsaUVbA`.
H1 unset-run handle: `fcb-doc:i_rP_Y8Aa2SLcJAM1uAzBA`.

### Given

| Given | Result | Actual |
|-------|--------|--------|
| Operator acceptance recorded | PASS | "accepted by operator for UAT run 2026-10-08-02" (this report) |
| Golden model open in GUI | PASS | `document_open` → `OK` |
| Framed before capture | PASS | `view_fit_viewport` → `OK` |
| Before capture | PASS | `tc-11-08-before.png` |

### Then

| # | Assertion | Result | Actual |
|---|-----------|--------|--------|
| 1 | Operator warned at startup | PASS | `tc-11-08-stderr-unset.log` line 3: `SECURITY: mutation auto-approve ENABLED (FREECAD_BUDDY_AUTO_APPROVE unset or 1; set it to 0 to require preview_id)` |
| 2 | Mutation runs without a token | PASS | `feature_pad` no `confirm`: `status: "OK"`; the result blocks contain `requires a confirm` 0 times |
| 3 | One approval record | PASS | `grep -c '"event": "approval"' tc-11-08-approve.jsonl` → `1` |
| 4 | Approval names tool and switch | PASS | `tool: "feature_pad"`, `approval.mode: "auto_approve"`, `approval.source: "FREECAD_BUDDY_AUTO_APPROVE"` |
| 5 | Approval carries pre-mutation fingerprint | PASS | approval `fingerprint_before` = `14aed585...d7ae` = `feature_pad` mutation `before` line `fingerprint_before` = envelope `mutation.fingerprint_before.digest` |
| 6 | Approval digest = mutation digest | PASS | approval `params_digest` = before line = after line = `83d9f61f16ea6f7c58cf2f815e1be8328d9460879663e96f96b023a0f92c3ec3` |
| 7 | `0` turns gate on | PASS | `=0` stderr: warning count `0`; `feature_pad` → `INVALID_INPUT` with the exact confirm-required string |
| 8 | Other value turns it on | PASS | `=true`: warning count `0`, same `INVALID_INPUT` and same string; 0 approval lines |
| 9 | (visual) framed | PASS | `view_fit_viewport` → `OK`, `fitted: true` |
| 10 | (visual) window identical to before | PASS | See visual judgement below |

**Visual judgement (pixels).** `tc-11-08-before.png`: FreeCAD window, tree `box-10-20-30` > `Box`
(visible), one grey box in isometric view, whole and framed, Tasks panel "Start Part / New Body",
no dialog. `tc-11-08-after.png`: the same single box, same size and position, same tree, no new
object in viewport or tree, no dialog. By eye identical to the before image. (Corroborating: `cmp`
says identical bytes.)

## Defects and observations

### Product defects

None for the behaviour under test. Code matches the scenarios:
`usecases/capabilities.py:37` `auto_approve=environ.get(AUTO_APPROVE_VARIABLE, "1") == "1"`;
`adapters/mcp_server.py:176-177` logs `AUTO_APPROVE_WARNING`;
`usecases/confirm.py:248-256` auto-approves only when `confirm is None`;
`usecases/confirm.py:183` raises `confirm.preview_id carries an invalid signature`.

### Test-case defects

1. **TC-11-08 Design Ref line numbers are stale.** It cites `adapters/mcp_server.py:161-162` and
   `adapters/audit_log.py:86-101`. Current code: warning at `mcp_server.py:176-177`
   (`if auto_approve_enabled(caps): logger.warning(AUTO_APPROVE_WARNING)`); `AuditSink.approval`
   at `audit_log.py:88-103`.
2. **TC-11-08 Host / When command.** `uv run python -m freecad_buddy.hosts.main serve ...` cannot
   start H1: the uv env has no FreeCAD. It should use `"$FCB_PYTHON"` as TC-08-18 does.
3. **Cleanup deletes evidence.** Both scenarios `rm -f` the approve audit file, which is the
   corroborating evidence for the run. Kept here.
4. **Fixture construction is implicit (both scenarios).** "Exactly one approval line" holds only
   when the fixture is built outside the audited process (or loaded from a saved file). TC-11-08
   does not say so. Building the fixture in the audited process gives 4 approval lines.

### Side observations (not assessed by these scenarios)

1. **Refusal envelope returns a full traceback to the MCP client.** Every `INVALID_INPUT` result
   carries `detail.data.traceback` with absolute local paths
   (`D:\Work\Personal\Sources\freecad-buddy\src\...`). Source: `adapters/rpc_dispatch.py:87`
   `data: dict = {"exception": type(exc).__name__, "traceback": tb[:_TRACEBACK_LIMIT]}`.
   The stderr side already keeps client errors to one line (`rpc_dispatch.py:80-86`). Candidate for
   a TC-11 information-disclosure review.
2. **`query_sketch_info` has no `fully_constrained` field.** Its `structured_content` holds only
   `sketch`, `geometry`, `constraints`. TC-08-01 Given asserts `fully_constrained: true` from this
   call. The fixture's full constraint was proved from `sketch_add_geometry`
   `post_verify.fully_constrained: true` instead. Not judged here.
3. **Session-start sweep.** Every H1 start logs `session-start sweep removed 1 leftover temp
   artifact(s)`, while `%TEMP%` still holds many `FCB_TMP_*` entries (some from 2026-09-13) and the
   undeletable `FCB_TMP_prev_rtoduji3`. Not investigated.

## Evidence files

All under `D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-08-02/evidence/`:

- Driver: `h1_posture.py`
- TC-08-18: `tc-08-18-before.png`, `tc-08-18-after.png`, `tc-08-18-approve.jsonl`,
  `tc-08-18-audit-eq1.jsonl`, `tc-08-18-audit-eq0.jsonl`, `tc-08-18-audit-eqtrue.jsonl`,
  `tc-08-18-stderr-{unset,eq1,eq0,eqtrue}.log`, `tc-08-18-calls.jsonl`, `tc-08-18-fixture.FCStd`,
  `tc-08-18-fixture-audit.jsonl`, `tc-08-18-fixture-stderr.log`, `tc-08-18-given-fcb-import.txt`
- TC-11-08: `tc-11-08-before.png`, `tc-11-08-after.png`, `tc-11-08-approve.jsonl`,
  `tc-11-08-audit-eq0.jsonl`, `tc-11-08-audit-eqtrue.jsonl`, `tc-11-08-stderr-{unset,eq0,eqtrue}.log`,
  `tc-11-08-calls.jsonl`, `tc-11-08-fixture.FCStd`, `tc-11-08-fixture-audit.jsonl`, `tc-11-08-fixture-stderr.log`
- GUI bridge calls: `phaseB2-calls.jsonl` (labels `08-18-*`, `11-08-*`)
