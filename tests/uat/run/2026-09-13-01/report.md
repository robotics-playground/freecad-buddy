# Run Report — Green Gate, 2026-09-13

> **Superseded format.** This run executed the previous `Steps`/`Checkpoints` test cases, before the
> suite moved to `testcases/` with Given/When/Then scenarios and a mandatory visual `Then`. The
> verdicts are kept as history; the `CPn` identifiers referenced here no longer resolve. A `PASS`
> recorded below is not evidence under the current gate, which requires a `cua-driver` pixel capture
> judged by the agent — see `tests/uat/test-plan.md` §3. Findings are in `bugs.md` beside this file.

**Operator:** agent-executed, autonomous mode
**Scope requested:** full green gate, TC-01 .. TC-14
**Scope completed:** TC-01, TC-02, TC-03, and TC-04 partially (13 of 24 scenarios)
**Outcome:** **BLOCKED** — the MCP client lost its connection to the bridge and could not reattach.

## Build banner

Captured from `query_capabilities` against the live GUI bridge. Every result below is only
interpretable against this banner.

| Field | Value |
| --- | --- |
| FreeCAD (GUI host) | 1.1.1 |
| FreeCAD (H1 headless leg) | 1.1.0 — note the skew |
| `element_map_available` | `true` |
| `serializer` | `exportBinary` |
| `varset_backend` | `varset` |
| `render` | `gui_constructed` |
| `sketcher_available` / `partdesign_available` | `true` / `true` |
| `exec_enabled` | `false` |
| element map version | `15.70200.5` |
| Tool surface | **45** tools (`document_` 7, `query_` 8, `verify_` 6, `export_` 3, `sketch_` 8, `feature_` 11, `preview_dry_run` 1, `view_fit_viewport` 1) |

## Preparation done before the run

The suite claimed **44** tools. The live catalog has **45** — `view_fit_viewport`, shipped with
Epic 8 (commit `636fb8a`) and absent from every test file. Two corrections were made first:

1. **TC-14 was authored** — `TC-14-viewport-framing-and-auto-fit.md`, 16 scenarios covering the
   Epic 8 surface: the fit tool, the framing read and its cache, the warning sentence, the AD-20
   alias enforcement from story 8.5, and a mandatory visual check. It was registered in
   `test-plan.md`, `README.md` and `coverage-matrix.md`.
2. **Stale counts were corrected** to 45 in `APPENDIX-B` step 6, `TC-01-03`, `test-plan.md`,
   `README.md` and `coverage-matrix.md`. The matrix's own verification command now reports
   `shipped: 45 missing: none`.

Environment setup per `APPENDIX-B` passed end to end, including the blocking step 6a: a mutation was
proven to commit (`preview_dry_run` then `feature_body_create`, `post_verify.passed: true`) before
any scenario ran.

## Results

| TC | Scenarios run | Verdict | Notes |
| --- | --- | --- | --- |
| TC-01 | 14 of 14 | PARTIAL | 4 scenarios blocked by AD-26; 2 blocked by the cua driver |
| TC-02 | 18 of 18 | PARTIAL | 3 product bugs, 3 test bugs, 1 coverage gap |
| TC-03 | 21 of 21 | PARTIAL | 13 fully pass; 2 product bugs, 5 test bugs |
| TC-04 | 13 of 24 | PARTIAL | 2 product bugs, 2 test bugs; 11 scenarios unexecuted |
| TC-05 .. TC-14 | 0 | **NOT RUN** | blocked, see below |

**No TC-05 through TC-14 scenario was executed.** They are unverified, not passing.

## Why the run stopped

FreeCAD and its proxy exited between TC-04 and TC-05. The bridge was restored — FreeCAD relaunched
(pid 9756), the addon auto-spawned a new proxy on `:8765`, and the endpoint was verified healthy by
three independent checks (`netstat` LISTENING, the proxy log's own bind line, and a `curl` returning
the expected 307).

The `mcp__freecad-buddy__*` tools never came back. The MCP **client** connection died with the old
process and does not reattach to the new one, and nothing inside the session can force a reconnect.
Recorded as **UAT-24**.

This is likely to recur: TC-01-10, TC-01-12, TC-01-13 and TC-01-14 all deliberately stop FreeCAD or
the proxy, and TC-10 and TC-14 stress the same paths.

## To resume

1. Restart the Claude Code session so the MCP client reconnects to `http://127.0.0.1:8765/mcp`.
   The bridge needs no repair.
2. Confirm the surface: `query_capabilities` returns `OK` and `tools/list` returns 45.
3. Re-run `APPENDIX-B` step 6a — prove a mutation commits before testing resumes.
4. Continue with the TC-04 remainder (TC-04-08, 10, 11, 12, 13, 14, 15, 17, 18, 20, 22, 23, 24),
   then TC-05 onward.
5. Schedule the FreeCAD-restarting scenarios **last**, so a stranded client ends a run that is
   already finished rather than one in progress.

## Findings

24 findings recorded in `bugs.md` beside this file: 7 product bugs, 13 test bugs, 2 environment
faults, 2 coverage gaps. Every product-bug claim was verified against the source by the main agent
rather than accepted from a subagent's report.

**The product bugs that matter most:**

- **UAT-05 (high)** — `query_tree_summary` filters gate at the tree root, so asking for the pads in a
  normal Body-rooted document returns an empty tree. `queries.py:358`.
- **UAT-12 (high)** — `sketch_add_constraint` rejects FreeCAD's own 3-argument `DistanceX`/`DistanceY`,
  blocking the routine move of dimensioning a point from the origin. `sketches.py:441-444`.
- **UAT-19 (high)** — `feature_pad`'s `second_length` sets `Length2` but never `SideType`, which is
  absent from the entire codebase, so a two-sided pad silently stays one-sided while reporting `OK`.
  `features.py:485-486`.

All three report success while doing something other than what was asked, which is what makes them
worse than an error would be.

## Gate status

**The green gate is neither passed nor failed — it is incomplete.** 10 of 14 test cases never ran.
Do not read the passing scenarios as a release signal.

The conformance gate (TC-99) was not run in this session. Its last recorded result is
`../2026-09-12-01/report.md`, where all 8 cases failed as documented.
