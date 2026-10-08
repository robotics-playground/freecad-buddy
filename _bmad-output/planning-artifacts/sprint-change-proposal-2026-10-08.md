---
title: 'Sprint Change Proposal: MCP result numbers and tree text'
date: '2026-10-08'
author: TanNT
trigger_commits: ['33543bb', '57d3adb', 'd4ad5e0']
scope: Minor
status: approved
---

# Sprint Change Proposal: MCP result numbers and tree text

## 1. Issue Summary

Three commits on `main` changed the MCP result contract. The code, tests and three design documents
(`mcp-tools-design`, `data-contracts-design`, `integration-mcp-clients`, `verification-design`) are
updated. Other living documents still describe the old contract.

| Commit | Change |
| --- | --- |
| `33543bb` | Every float in a tool result is rounded to FreeCAD's `Decimals` unit preference (default 2), read on every call. Checks compare `round(|measured - expected|)` with the raw band. A FreeCAD Buddy page in Edit > Preferences adds the checkbox `RoundToDisplay` (parameter `BaseApp/Preferences/Mod/FreeCADBuddy`, default on); off keeps every float and every deviation raw. New module `contracts/numbers.py`, new `hosts/gui_addon/preferences.py`. |
| `57d3adb` | Claude Code shows the agent only `structuredContent` when a result carries it, and drops every content block. Evidence: transcript `3275e760` (project `Ender-3V2---Klipper`) and a direct call in this session both received only the JSON; a raw `mcp` client received both blocks. So the `query_tree_summary` tree (second content block) never reached an agent. `RpcMethod.structured_output=False` now removes `outputSchema` and `structuredContent` for that tool. |
| `d4ad5e0` | `query_tree_summary` now returns one plain text block: `<STATUS>: <summary>`, then `framing: ...` when a 3D view is open, then the tree lines. The summary adds `N matches` when `filters` is given. An error is one line `<STATUS>: <message>`. |

Issue type: technical limitation found during use (client behaviour), plus a new operator setting.

## 2. Impact Analysis

- **Epics:** no epic or story changes. Epic 11 (Lean Agent Loop) goals are served, not changed. Done stories keep their text (history).
- **PRD:** no PRD file exists; product scope is not affected.
- **Architecture:** the spine Tool-results and Config conventions are out of date. `component-design`, `project-structure` and `integration-mcp-freecad` do not list the two new modules or the preference page.
- **UAT test cases:** 16 lines cite the tree as `content[1]`; 11 lines check the tree tool by `status: "OK"`, `total_objects`, `shown` or `structured_content.truncated`; TC-16-06 asserts two content blocks. 6 lines compare full-precision floats that results now round (TC-13 `15214.601836602547`, `4957.079632679489`; TC-07:82 `1570.7963` within 0.001, which now FAILS on `1570.8`).
- **Agent context and operator docs:** `CLAUDE.md` and `AGENTS.md` repo maps miss `numbers` and `preferences`. `README.md` operator setup does not name the new preference.
- **Test standard:** `freecad-gui-e2e-harness.md` lacks two findings from this session: a UIA click on a menu item that opens a modal dialog blocks the UIA provider, and session MCP tools show only `structuredContent` while `fcb.py` shows content blocks.
- **Deferred work:** one entry is now answered (Claude Code client behaviour), one entry is fixed by this proposal (repo map), one entry gains an option (G3 frames-check can turn rounding off).

## 3. Recommended Approach

Direct adjustment: edit documents only, no code. Effort low, risk low, no timeline impact.

## 4. Detailed Change Proposals

### 4.1 Architecture spine — `ARCHITECTURE-SPINE.md` Consistency Conventions table

Row **Tool results**, sentence about the tree.

OLD: `A long text body (the query_tree_summary tree) travels in the envelope's text_blocks and is sent as extra raw TextContent after the JSON block, never inside the JSON block or structuredContent.`

NEW: `A long text body (the query_tree_summary tree) travels in the envelope's text_blocks. Such a tool declares no outputSchema and returns one plain text block (status line, framing line, then the body) with no structuredContent, because a client that finds structuredContent (Claude Code) shows the agent only that.`

New row **Numbers**: `Every float in a tool result is rounded to FreeCAD's Decimals unit preference (default 2), read on every call; |x| < 1e-9 reads 0. A check passes when round(|measured - expected|) <= its raw band; echoed tolerances stay raw; fingerprints keep their own quantum (AD-6). The FreeCAD Buddy preference RoundToDisplay (default on) turns rounding off for output and verdicts together.`

Row **Config**, append: `Display rounding is a FreeCAD parameter (BaseApp/Preferences/Mod/FreeCADBuddy, RoundToDisplay), set on the addon's Preferences page.`

Rationale: the spine conventions bind every design document.

### 4.2 Design documents

- `component-design.md` contracts table: add row `numbers.py` — display rounding (`round_display`, `round_floats`, `displayed_deviation`); used by `mcp_server`, `assertions`, `exports`, `export_oracle`. Row `gui_addon/InitGui.py + bootstrap.py`: add "registers the FreeCAD Buddy preference page (`preferences.py`)".
- `project-structure.md` tree: add `numbers.py  # display rounding of result floats and check deviations` under `contracts/`, and `preferences.py  # FreeCAD Buddy page in Edit > Preferences (RoundToDisplay)` under `gui_addon/`.
- `integration-mcp-freecad.md` §3.1: after the code block, add "`InitGui.py` also registers `PreferencesPage` from `preferences.py` with `Gui.addPreferencePage`; tool calls read its `RoundToDisplay` value on every call, so a change applies without a restart."

### 4.3 UAT test cases (`tests/uat/`)

- `test-plan.md` §3: define **tree lines** = the lines of a `query_tree_summary` result after its `<STATUS>:` line and its optional `framing:` line; the first line reads `OK: <N> objects, <M> shown[, <K> matches][, truncated][. Errors: ...]`.
- Replace "the tree text (`content[1]`)" with "the tree lines" at TC-02:104, 144, 187, 188, 375, 414, 734; TC-06:298; TC-09:303, 347, 463; TC-12:262; TC-13:195, 332, 704.
- Tree status checks become first-line checks: `returns status: "OK"` → "its first line starts `OK:`" at TC-01:474, TC-02:192, 453, 615, 734; `status: "OK" with total_objects 1` → "first line starts `OK: 1 objects`" at TC-02:143 (and `0 objects` at :529); "`OK` with `shown` equal to" → "first line `<M> shown` equal to" at TC-09:303, 347, 463; `structured_content.truncated false` → "the first line has no `truncated`" at TC-09:462.
- TC-16-06 Then: "the result is one text block: line 1 `OK: ... shown.`, then a `framing:` line, then the tree lines; it holds no `{`"; the size and body checks read "the block" in place of "block 2".
- Display-rounded values: TC-13:177, 333, 797 `15214.601836602547` → `15214.6`; TC-13:267 → `15214.6` within `rel: 0.001`; TC-13:268 `4957.079632679489` → `4957.08`; TC-07:82 "within 0.001 of `1570.7963`" → "within 0.01 of `1570.7963` (results carry 2 decimals)".

### 4.4 Agent context and operator docs

- `CLAUDE.md` §12 and `AGENTS.md` repo map: contracts list adds `numbers`; `gui_addon/` list becomes (`InitGui` `bootstrap` `pump` `preferences`).
- `README.md` Operator setup: new section **Display rounding** — what is rounded, where the checkbox is, default on, applies on the next call, off keeps raw floats and raw deviations.

### 4.5 Test standard — `.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md`

- §3 table, new row: `UIA click on Edit > Preferences` → "opens the modal dialog, but the click call blocks and the UIA provider stays busy until the dialog closes; later background clicks return `background_unavailable` (`uia_status: busy`); `zoom` still captures pixels. Open modal dialogs only when foreground input is authorized."
- Tools section note: "Session `mcp__freecad-buddy__*` tools show only `structuredContent` when a result has it; `fcb.py` prints the content blocks. Judge what the agent reads with the session tools."

### 4.6 Deferred work — `_bmad-output/implementation-artifacts/deferred-work.md`

- Entry "MCP text content is the whole result envelope as JSON" (Story 11.2): add evidence "Claude Code passes only `structuredContent` to the model when present (verified 2026-10-08); the JSON content block reaches only other clients. `query_tree_summary` now sends no `structuredContent`." Keep the entry open for the other tools.
- Entry "G3 frames-check ... resolution is really 0.005 mm": add option "turn `RoundToDisplay` off for the scorer run".
- Entry "CLAUDE.md / AGENTS.md repo map lists `contracts/` modules without the new `numbers` module": remove (fixed by 4.4).

## 5. Implementation Handoff

- **Scope:** Minor. Developer agent applies sections 4.1-4.6 directly.
- **Success criteria:** each OLD text is gone and each NEW text is present; `git grep -n "content\[1\]" tests/uat/testcases` returns nothing; `git grep -n "15214.601836602547" tests/uat/testcases` returns nothing; `uv run python scripts/check_skill_shape.py` and `uv run pytest tests/external -q` pass; one docs commit after user approval.
