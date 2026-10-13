# TC-14: Viewport Framing & Auto-Fit

Validates Epic 8 (FR24-FR26, AD-29..AD-33): the framing read that measures whether the targeted
document's model fits its live viewport, the `view_fit_viewport` tool that moves the human's
camera to fix it, the warning sentence a non-fitting verdict appends to a tool result, and the
CI alias gap story 8.5 closed.

This is the only test case whose subject is the **human's own camera**. Every other case treats the
viewport as an output to read; here it is the state under test. That inverts the suite's standard
auto-fit rule: elsewhere the fit is setup that happens before a visual `Then`, here the fit is the
action under test, so each scenario states where it sits relative to the capture.

**How framing is read.** `query_tree_summary` returns plain text (`mcp_server.py:127-150`): a
`<STATUS>: <summary>` line, the framing warning sentence after a blank line when the model does
not fit, a `framing:` line when a viewport is open, then the tree. The `framing:` line is
`framing: <fits|does not fit|unknown>[, ratio R], <computed|cached|unavailable>[, <reason>]`
(`_framing_line`, `mcp_server.py:141-149`). Below, "fits", "ratio", "checked" and "reason" name
the parts of that line. Structured tools such as `view_fit_viewport` carry the same verdict as a
`framing` object.

**`view_fit_viewport` is the code under test in this file, so it can never be the evidence that it
worked.** Its `status`, its `fitted` flag, and the `framing` verdict are all claims produced by the
thing being judged. Commit `636fb8a` fixed a defect in which every one of those claims was correct
while the part occupied about 5 % of the viewport. The evidence is the `cua-driver` pixel capture of
the real window, `Read` and judged as a user would judge it. Where a scenario needs the model framed
*before* it can judge something else — and the MCP fit is unavailable, refused, or itself suspect —
frame it with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code
under test.

**Host**: GUI through the H2 proxy for every scenario except TC-14-09 and TC-14-12, which run on
the H1 headless host to prove the honest-degradation path, and TC-14-14, which runs its suspect
document on H1. TC-14-15 is a repo-level CI check and needs no host.

## Preconditions

- [ ] FreeCAD 1.1.x installed (verify: `ls "$FREECAD_EXE"`); the build under test is the live version: `query_capabilities.freecad_version`, read once at the start of the run and written `<live version>` below
- [ ] FreeCAD GUI is running with a 3D view open (verify: `mcp query_capabilities {}` returns `render: "gui_constructed"`)
- [ ] Proxy is LISTENING on `:8765` (verify: `netstat -ano | grep :8765` shows a LISTENING line)
- [ ] `FREECAD_BUDDY_AUDIT_LOG` resolves to a writable absolute path, per APPENDIX-B step 6a (verify: a scratch `feature_body_create` returns `status: "OK"`)
- [ ] Golden models are present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` returns a `QOpenGLWidget`)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)
- [ ] Golden and fault `.FCStd` files have no `GuiDocument.xml` and open with every object hidden. After each `document_open` of such a file, and before any fit or render of it, run **Show All**: `cua-driver call invoke_menu { pid, window_id, path: ["View","Visibility","Show All Objects"] }`. A fit before it returns `SPEC_FAILED view_fit.nothing_to_frame`. In this file every `document_open` of a golden model is followed by Show All unless the scenario says otherwise.

---

### TC-14-01: view_fit_viewport ships on the wire with the confirm-exempt mutating shape

**Priority**: Critical
**Design Ref**: spine §AD-31, §AD-33; `spec-8-3-view-fit-viewport-tool.md` §Boundaries

**Given** the bridge answers over MCP — verify: `mcp query_capabilities {}` returns `status: "OK"`  
**And** a golden model is open so the closing visual has a subject — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle, then run Show All  

**When** the advertised schema is read off the live proxy  
```bash
uv run python -c "
import asyncio, json
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
async def main():
    async with streamablehttp_client('http://127.0.0.1:8765/mcp') as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            t = [x for x in (await s.list_tools()).tools if x.name == 'view_fit_viewport'][0]
            json.dump(t.inputSchema, open('$RUN_DIR/evidence/tc-14-01-schema.json','w'), indent=1)
            print(json.dumps(t.inputSchema, indent=1))
asyncio.run(main())
"
```

**Then** the tool is advertised — verify: the command prints a schema rather than raising `IndexError`  
**And** `doc` is the only property — verify: `python -c "import json;s=json.load(open('$RUN_DIR/evidence/tc-14-01-schema.json'));print(sorted(s['properties']))"` prints `['doc']`  
**And** `doc` is required — verify: the same file's `required` is `["doc"]`  
**And** there is **no** `confirm` property — verify: `grep -c confirm "$RUN_DIR/evidence/tc-14-01-schema.json"` returns `0`. This is the confirm-exempt shape; a `confirm` key here would mean the camera move wrongly demands a `preview_id`.  
**And** the schema is closed — verify: `additionalProperties` is `false`  
**And** it is absent from the read-only profile — verify: start the assistant read-only surface and confirm `view_fit_viewport` is not listed (`READ_ONLY_PROFILE` is an opt-in allow-list at `tool_catalog.py:1032`)  
**And** *(visual)* the advertised tool actually drives the window — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`  
**And** *(visual)* the FreeCAD window shows the whole box — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-01-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one box-shaped solid, all of it inside the viewport rectangle, no edge running off a border. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-14-02: A fit on a framed document returns OK and reports the camera it recorded

**Priority**: Critical
**Design Ref**: `usecases/view_fit.py:300-312` (`_fitted_envelope`)

**Given** a golden model is open with a live 3D view — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle and the document `Name`, then run Show All  

**When** the document is fitted into its own viewport  
```
mcp view_fit_viewport { doc: "<handle>" }
```

**Then** status is `OK` — verify: the envelope's `status` is exactly `"OK"`  
**And** `fitted` is true — verify: `structured_content.fitted` is `true`  
**And** the resolved document name is reported, not the handle — verify: `structured_content.document` equals the document's `Name`  
**And** the pre-fit camera was captured — verify: `structured_content.camera_recorded` is `true`  
**And** the text mirrors the action — verify: `text` is exactly `fitted the live viewport to '<Name>'`  
**And** `detail` is null on success — verify: `detail` is `null`  
**And** *(visual)* the window agrees with the `fitted: true` claim — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-02-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a box-shaped solid, wholly visible, roughly centred in the viewport. An `OK` envelope over a window showing empty space is the exact defect this scenario catches, so do not reason from the envelope to what the picture must contain. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-14-03: The fit actually moves the camera

**Priority**: Critical
**Design Ref**: `usecases/view_fit.py:103-130` (`_fit_all`), §AD-31

**Given** a golden model is open — verify: `document_open` on `box-10-20-30.FCStd` returns `OK`, then run Show All  
**And** the camera has been deliberately zoomed in through the GUI (`invoke_menu ["View","Zoom","Zoom In"]`, backed off with `Zoom Out` until the line carries a ratio) so a no-op would be visible — verify: the `framing:` line of `mcp query_tree_summary { doc: "<handle>" }` reads `does not fit, ratio R`; record R as `ratio_before`. A hard zoom gives `does not fit` with no ratio (corners discarded as implausible, `framing.py`), which has nothing to compare  
**And** the wrong starting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-03-before.png"}' | & cua-driver call get_window_state`  

**When** the document is fitted  
```
mcp view_fit_viewport { doc: "<handle>" }
```
**And** the framing is re-read  
```
mcp query_tree_summary { doc: "<handle>" }
```

**Then** the model fits after the fit — verify: the `framing:` line reads `fits`  
**And** the verdict was freshly measured, not served from cache — verify: the `framing:` line carries `computed`, not `cached`. A cached `true` would prove nothing: the camera moved, so the cache key must have changed.  
**And** the fit landed inside its own call — verify: the two assertions above hold on the **first** read after the fit, with no intervening delay or extra call. This is the animation-suspension contract (`view_fit.py:132-165`); a fit that only lands after the event loop runs again would fail here.  
**And** the framing is not merely inside but filling — verify: the ratio on the `framing:` line is between `0.85` and `1.0`. `_FILL_FRACTION = 0.95` (`view_fit.py:35`) targets 95 % of the binding axis; a ratio near `0.05` would mean the sphere-framing shrinkage was not cancelled.  
**And** the ratio improved — verify: the new `ratio` is closer to `1.0` than `ratio_before`  
**And** *(visual)* the window changed and now shows the whole model — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-03-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what each shows: the before image a clipped or off-screen model, the after image a whole box inside the frame. The judgement is on the pixels alone — no MCP status, `framing:` line or ratio may stand in for looking at the images.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-14-04: A tall bar fills the viewport, not 5 % of it

**Priority**: Critical
**Design Ref**: `usecases/view_fit.py:168-191` (`_fill_factor`), commit `636fb8a`

This is the regression guard for the shipped fix. A 40x40x800 bar has a space diagonal far larger
than its isometric silhouette, so FreeCAD's sphere-based framing lands it at roughly 5 % of the
viewport. The factor cancels exactly that shrinkage.

**Given** a scratch document exists — verify: `mcp document_create { label: "tc14bar" }` returns `OK`  
**And** a 40x40x800 bar exists in it, built through the shipped feature tools as a pad named `BarPad` — verify: `mcp query_mass_properties { doc: "<handle>", object: "BarPad" }` returns a volume of `1280000.0` mm³ within 0.1 %  

**When** the bar is fitted, exactly once  
```
mcp view_fit_viewport { doc: "<handle>" }
```
**And** the framing is read  
```
mcp query_tree_summary { doc: "<handle>" }
```

**Then** the bar fits — verify: the `framing:` line reads `fits`  
**And** the bar fills the viewport — verify: the ratio on the `framing:` line is `>= 0.85`. **This is the assertion the fix earns.** A ratio near `0.05` is the pre-fix behaviour and a regression.  
**And** one call was enough — verify: both assertions hold after that **single** `view_fit_viewport` call. The tool's contract is one call, not a converging loop.  
**And** the fit did not overshoot into clipping — verify: the `framing:` line reads `fits`, not merely a high ratio. A ratio above `1.0` with `does not fit` means the factor overshot.  
**And** *(visual)* the human's window shows a large bar, not a speck — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-04-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a long bar whose long axis spans the clear majority of the viewport's binding dimension, both ends inside the frame. **This is the assertion that actually catches the `636fb8a` defect** — `ratio >= 0.85` and a speck on screen would both be reported, and only the picture tells you which happened. The judgement is on the pixels alone — no MCP status or `ratio` may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-14-05: The fitted viewport and the MCP render agree on what the human sees

**Priority**: Critical
**Design Ref**: test-plan §3 (why the visual `Then` is not optional), §9 Visual; `integration-mcp-freecad.md`

Numbers are not sufficient here, and neither is an MCP render on its own: the MCP render is a
**constructed scene** produced by the code under test, not a capture of the human's viewport. This
scenario is where the two artifacts are compared against each other.

**Given** the 40x40x800 bar from TC-14-04 is open, or rebuilt — verify: `mcp query_mass_properties { doc: "<handle>", object: "BarPad" }` returns `1280000.0` mm³ within 0.1 %  
**And** `cua-driver` has the FreeCAD `pid` and `window_id` — verify: `cua-driver call list_windows` returns them  
**And** the camera has been moved off the part through the GUI so the starting state is plainly wrong — verify: the `framing:` line of `query_tree_summary` reads `does not fit`  
**And** the wrong starting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-05-before.png"}' | & cua-driver call get_window_state`  

**When** the bar is fitted  
```
mcp view_fit_viewport { doc: "<handle>" }
```
**And** the real window is captured  
```bash
'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-05-after.png"}' | & cua-driver call get_window_state
```
**And** the MCP render of the same document is taken  
```
mcp query_screenshot { doc: "<handle>" }
```

**Then** the after image differs from the before image — verify: `cmp "$RUN_DIR/evidence/tc-14-05-before.png" "$RUN_DIR/evidence/tc-14-05-after.png"` reports a difference  
**And** *(visual)* the whole bar is visible in the real window — verify: `Read "$RUN_DIR/evidence/tc-14-05-after.png"` and say what is on screen; both ends of the bar are inside the viewport rectangle and no part is cut off by an edge  
**And** *(visual)* the bar is not a speck — verify: in the same image, the bar's long axis spans the clear majority of the viewport's binding dimension. This is the human-visible half of what TC-14-04 measures numerically.  
**And** *(visual)* the orientation is isometric — verify: the after image shows three faces of the bar, not a single face. `_view_isometric` (`view_fit.py:220-230`) swings the camera to the TOP/FRONT/RIGHT corner so a tall part shows its real extent rather than its end face.  
**And** *(visual)* the MCP render is judged against the window — verify: `Read` the render returned by `query_screenshot` and compare it to the window capture on shape, orientation, and framing: the same whole bar, isometric, with three faces visible. **The window is the referent; the render is the thing being judged.** The render is produced by the code under test, so where the two disagree on those points the window wins: record the disagreement in `$RUN_DIR/bugs.md` as a finding against the render, and never re-read the envelope to decide which image is right. Face tone is excluded from the comparison: the render is a constructed scene whose lighting is set by the AD-34 tone band, not by viewport match (sprint-change-proposal-2026-10-04 decision 4). Check only that no face of the render is black or white and each face is separable from the background. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the window image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-14-06: A handle naming a document the viewport is not showing is refused, naming both

**Priority**: Critical
**Design Ref**: `usecases/view_fit.py:291` (`_require_same_document`),
`hosts/gui_addon/viewport.py:59` (`showing_document_name`), §AD-20, §AD-29

**Given** two documents are open, `DocA` and `DocB` — verify: `mcp document_list {}` lists both; record both handles  
**And** both have an open 3D view, so the refusal cannot be mistaken for "`DocA` has no viewport" — verify: `mcp view_fit_viewport { doc: "<DocA handle>" }` returned `OK` while `DocA` was still the focused tab, before `DocB` was opened  
**And** the live viewport is showing `DocB` — verify: `cua-driver call list_windows` reports an active window title naming `DocB`  
**And** `DocB` is fitted so its framing is a known baseline — verify: `mcp view_fit_viewport { doc: "<DocB handle>" }` returns `OK`; record the ratio on the `framing:` line of `mcp query_tree_summary { doc: "<DocB handle>" }` as `ratio_before`  

**When** the fit targets the document the viewport is **not** showing  
```
mcp view_fit_viewport { doc: "<DocA handle>" }
```

**Then** the call is refused — verify: `status` is `INVALID_INPUT`  
**And** the message names **both** documents — verify: `detail.message` contains both `DocA` and `DocB`. An agent told only "wrong document" cannot tell which of its handles is stale.  
**And** the message states the remedy — verify: `detail.message` matches `the live viewport is showing '<DocB>', not the targeted '<DocA>'; call view_fit_viewport with the handle for '<DocB>', or open a 3D view for '<DocA>'`  
**And** the camera did **not** move — verify: `mcp query_tree_summary { doc: "<DocB handle>" }` returns a `framing:` line whose ratio equals `ratio_before`. The fit is never redirected to the active document.  
**And** the refusal came from the on-screen name, not from a missing viewport — verify: `detail.message` names `DocB`, which no per-document accessor keyed on `DocA` could produce. R2-02 failed this scenario because the guard compared `DocA` against a view resolved from `DocA`'s own name: a name against itself. A refusal citing only `DocA`, or one reading `no live 3D view`, means the guard is answering the wrong question again.  
**And** `DocA` was **not** brought forward to resolve the comparison — verify: the window capture below still shows `DocB`'s tab active. The on-screen name is read from the focused MDI sub-window; activating or raising `DocA` would be the unrequested GUI change AD-31 forbids.  
**And** *(visual)* the window still shows `DocB`, unchanged — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-06-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: `DocB`'s model at the same size and position as before, its name in the title bar and its tab active — `DocA` was not silently brought forward. The judgement is on the pixels alone — no MCP status or `ratio` may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<DocA handle>" }
mcp document_close { doc: "<DocB handle>" }
```

---

### TC-14-07: An unknown, stale, or missing handle is INVALID_INPUT before any viewport work

**Priority**: Critical
**Design Ref**: `usecases/documents.py:139` (`_resolve`); `view_fit.py:78-80`

**Given** the bridge answers — verify: `mcp query_capabilities {}` returns `OK`  
**And** a golden model is open and fitted, so the viewport has a known, stable subject — verify: `document_open` on `box-10-20-30.FCStd` returns `OK`, Show All is run, and `mcp view_fit_viewport { doc: "<good handle>" }` returns `OK`  
**And** a second document was opened and closed, leaving a stale handle — record it as `<stale handle>`  

**When** the fit is called with a handle that was never issued  
```
mcp view_fit_viewport { doc: "no-such-handle" }
```
**And** with the stale handle  
```
mcp view_fit_viewport { doc: "<stale handle>" }
```
**And** with `doc` omitted entirely  
```
mcp view_fit_viewport { }
```

**Then** an unknown handle is refused — verify: the first call returns `INVALID_INPUT`  
**And** the message names the offending handle — verify: `detail.message` contains `no-such-handle`  
**And** a stale handle is refused — verify: the second call returns `INVALID_INPUT`  
**And** a missing handle is a schema reject — verify: the third call is refused with `Input validation error: 'doc' is a required property` (schema refusal) or `INVALID_INPUT`; the input is refused either way, because `doc` is in `required`  
**And** the handle is resolved **before** the viewport is consulted — verify: none of the three messages mentions a viewport or a missing 3D view. A bad handle must read as a bad handle on every host, not be masked by a "no viewport" answer the caller cannot act on.  
**And** *(visual)* no refusal disturbed the window — verify: `mcp view_fit_viewport { doc: "<good handle>" }` returns `OK`; if it does not, frame through the GUI with the **Fit All** toolbar button by `element_token`, since the three refusals under test may have left the MCP fit unusable. Then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-07-after.png"}' | & cua-driver call get_window_state`; `Read` the PNG and say what is on screen: the golden model still there and whole, no dialog or error popup raised by the three refusals. The judgement is on the pixels alone — no MCP status may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<good handle>" }
```

---

### TC-14-08: An unknown key is hard-rejected

**Priority**: High
**Design Ref**: test-plan §9 Contract; `tool_catalog.py:931` (`view_fit_viewport` schema, `additionalProperties: False`)

**Given** a document is open and fitted — verify: `document_open` returns `OK` and Show All is run; `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; record the ratio on the `framing:` line of `query_tree_summary` as `ratio_before`  

**When** a key the schema does not declare is passed  
```
mcp view_fit_viewport { doc: "<handle>", factor: 0.5 }
```
**And** the confirm key the tool deliberately does not take is passed  
```
mcp view_fit_viewport { doc: "<handle>", confirm: true }
```

**Then** the unknown key is rejected — verify: the first call is refused with `Input validation error: Additional properties are not allowed ('factor' was unexpected)` (schema refusal) or `INVALID_INPUT`, not a silently-ignored extra key; the input is refused either way  
**And** `confirm` is rejected too — verify: the second call is refused the same way, naming `'confirm'`. The tool is confirm-exempt, so `confirm` is an unknown key here, not an accepted no-op.  
**And** no camera moved on either reject — verify: the ratio on the `framing:` line of `query_tree_summary` equals `ratio_before`  
**And** *(visual)* the window is untouched by both rejects — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-08-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and compare it to the `Given`'s capture: the model at the same size, position, and orientation, no dialog raised. A schema reject that nevertheless moved the camera is exactly what this catches, and only the two pictures show it. The judgement is on the pixels alone — no MCP status or ratio may stand in for looking at the images.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-14-09: A host with no viewport degrades honestly and touches no camera

**Priority**: High
**Design Ref**: `usecases/view_fit.py:81-88`, `315-333` (`_unavailable_envelope`)

**Host**: H1 headless. The closing visual asserts the GUI window was **not** touched by an H1 call.

**Given** the H1 headless host is runnable — verify: APPENDIX-B step 3 reports `H1 ok`  
**And** the GUI still has its own document open and fitted — verify: `mcp view_fit_viewport { doc: "<gui handle>" }` returns `OK`  
**And** the GUI's framed state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-09-before.png"}' | & cua-driver call get_window_state`  

**When** the H1 host is started, a golden model is opened on it, and the fit is called  
```
H1: view_fit_viewport { doc: "<h1 handle>" }
```

**Then** the status is terminal and not `OK` — verify: `status` is `SPEC_FAILED`  
**And** the reason is stated, not blank — verify: `detail.code` is `view_fit.no_viewport` and `detail.message` is `this host has no live viewport: no camera to fit`  
**And** `fitted` is false — verify: `structured_content.fitted` is `false` and `structured_content.reason` carries the same sentence  
**And** no traceback reached stderr — verify: the H1 server stderr log holds no traceback for this call. An absent viewport is a stated outcome, not a fault.  
**And** the handle still resolves afterwards — verify: a following `query_tree_summary` on the same H1 handle returns `OK`. The refusal must not quarantine the document.  
**And** *(visual)* the separate GUI window was not touched by the headless call — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-09-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and compare: the GUI viewport shows the same model at the same size, position, and orientation. No fit is issued between the two captures — a fit would move the very camera this scenario says was left alone. A headless refusal that reached across into the human's camera would be a serious defect. The judgement is on the pixels alone — no MCP status may stand in for looking at the images.  

**Cleanup**: stop the H1 host.
```
mcp document_close { doc: "<gui handle>" }
```

---

### TC-14-10: The camera move is audited, carrying the camera it replaced

**Priority**: Critical
**Design Ref**: §AD-31; `usecases/view_fit.py:285-297` (`_audit`); `contracts/audit.py` (`camera_before`)

**Given** `FREECAD_BUDDY_AUDIT_LOG` points at `$RUN_DIR/evidence/tc-14-10-audit.jsonl` and the file is absent or empty — verify: `ls "$RUN_DIR/evidence/tc-14-10-audit.jsonl"` fails, or the file has zero lines  
**And** a document is open with a live view — verify: `document_open` returns `OK` and Show All is run  
**And** the camera is deliberately off the model — verify: the `framing:` line of `query_tree_summary` reads `does not fit`; record the pre-fit camera string as `camera_pre` from `script_exec` (`import FreeCADGui; result = FreeCADGui.getDocument(doc.Name).ActiveView.getCamera()`)  

**When** the document is fitted  
```
mcp view_fit_viewport { doc: "<handle>" }
```
**And** the audit log tail is read  
```bash
tail -5 "$RUN_DIR/evidence/tc-14-10-audit.jsonl"
```

**Then** the fit is audited — verify: the log gains at least one record whose tool is `view_fit_viewport`  
**And** a record carries `camera_before` — verify: one of the new records has a non-empty `camera_before` string  
**And** `camera_before` is the verbatim pre-fit camera — verify: its value equals `camera_pre`, not the post-fit camera  
**And** `camera_before` is **not** in `params_digest` — verify: the digest is unchanged from a fit on the same handle from a different starting camera. The digest hashes tool params only; the camera is not a param.  
**And** `camera_before` is **not** in `fingerprint_before` — verify: `fingerprint_before` is a geometry digest under AD-6 and carries no camera text  
**And** the generic bracket also logged — verify: the dispatch bracket's own before/after lines are present. A fit is audited twice by design: once generically, once with the camera.  
**And** `camera_before` is absent from the generated schema's required list — verify: `grep -A5 '"required"' src/freecad_buddy/contracts/jsonschema/audit-record.schema.json` does not list `camera_before`; it is optional  
**And** *(visual)* the audited move is the move the human received — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-10-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and compare it to the `Given`'s off-model capture: the model is now whole inside the frame, where before it was not. An audit record for a camera move that never reached the window is a false record, and the audit log cannot reveal that — only the picture can. The judgement is on the pixels alone — no MCP status or audit line may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-14-11: A non-fitting model appends the framing warning to a tool result

**Priority**: Critical
**Design Ref**: §AD-33; `contracts/envelope.py:82-117` (`framing_warning`, `with_framing_text`)

**Given** a document is open and Show All is run, and the camera is zoomed so the model does **not** fit — verify: the `framing:` line of `mcp query_tree_summary { doc: "<handle>" }` reads `does not fit`  
**And** the non-fitting state is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-11-before.png"}' | & cua-driver call get_window_state`  

**When** a tool that carries the framing key is called while the model does not fit  
```
mcp query_tree_summary { doc: "<handle>" }
```
**And** the document is fitted and the same tool is called again  
```
mcp view_fit_viewport { doc: "<handle>" }
mcp query_tree_summary { doc: "<handle>" }
```

**Then** the warning is present while the model does not fit — verify: the first call's text carries `Warning: the model does not fully fit the live viewport, so the human is seeing only part of it. Call view_fit_viewport to fit it, if they need to see this change.` right after the status line, before the `framing:` line  
**And** the wording is exact — verify: the sentence matches `envelope.py:110-113` verbatim. This is the only place the text exists; a second wording is a defect.  
**And** the warning is appended, not substituted — verify: the `OK: <summary>` status line still precedes it, separated by a blank line  
**And** the warning disappears after the fit — verify: the second call's `text` carries no `Warning:` sentence  
**And** a fitting model earns no sentence — verify: with a `framing:` line that reads `fits`, no warning is produced. Only `does not fit` warns.  
**And** an unmeasurable verdict earns no sentence — verify: a document whose `framing:` line reads `unknown, unavailable, <reason>` (for example a golden model before Show All: `no visible shape-bearing objects to measure`) produces no `Warning:` text. A measurement failure is not a framing problem, and `unknown` must never warn.  
**And** *(visual)* the warning told the truth both times — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-11-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what each shows: the before image a model genuinely cut off at a viewport edge, the after image the same model whole. **This is the assertion that grades the warning itself** — the sentence claims the human is seeing only part of the model, and only the picture says whether that claim was true. A warning that fires over a fully visible model, or stays silent over a clipped one, is the defect. The judgement is on the pixels alone — no MCP status or `framing:` line may stand in for looking at the images.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```

---

### TC-14-12: The framing block is omitted entirely where no viewport exists

**Priority**: High
**Design Ref**: §AD-32 state 1; `usecases/framing.py:179-191`

The distinction under test: **omitted** means there was no viewport at all; a `framing:` line that reads `unknown, unavailable`
means a viewport existed and the projection could not be completed. Collapsing the two would make
`unavailable` meaningless.

**Host**: H1 headless for the omission, GUI for the contrast.

**Given** the H1 headless host is runnable — verify: APPENDIX-B step 3 reports `H1 ok`  
**And** a document is open on the GUI host with a live view — verify: `document_open` returns `OK` and Show All is run; record the handle  

**When** a golden model is opened on H1 and its tree is read  
```
H1: query_tree_summary { doc: "<h1 handle>" }
```
**And** the tree is read on the GUI host for the document with a live view  
```
mcp query_tree_summary { doc: "<gui handle>" }
```

**Then** H1 omits the line — verify: the H1 text has **no** `framing:` line at all, rather than one that reads `unknown, unavailable`  
**And** H1 emits no warning sentence — verify: the H1 text carries no `Warning:` text  
**And** the GUI host emits the line — verify: the GUI text has a `framing:` line that ends `computed` or `cached` (a cached line may add a reason after it)  
**And** `fits` is never a guess — verify: across both, the first part of a `framing:` line is only ever `fits`, `does not fit`, or `unknown`; `unknown` is always followed by `unavailable` and a non-empty reason  
**And** *(visual)* the GUI host's block describes a real window — verify: `mcp view_fit_viewport { doc: "<gui handle>" }` returns `OK`, or failing that frame with the **Fit All** toolbar button by `element_token`; then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-12-after.png"}' | & cua-driver call get_window_state`; `Read` the PNG and say what is on screen: a real 3D view with the model drawn in it. That viewport's existence is the whole reason the two hosts answer differently, so it is confirmed by looking rather than by trusting the block that claims it. The judgement is on the pixels alone — no MCP status or `framing:` line may stand in for looking at the image.  

**Cleanup**: stop the H1 host.
```
mcp document_close { doc: "<gui handle>" }
```

---

### TC-14-13: The framing cache re-measures when the viewport is resized

**Priority**: High
**Design Ref**: §AD-32 four-tuple key, §AD-30 (bound); `usecases/framing.py:194-238`; `spec-10-4-render-and-framing.md` D8

A geometry-only cache key is the specific mistake this guards. A window resize changes `getSize()`
while the camera node is untouched, so a geometry-only key would keep serving `fits` for a
viewport that now clips the model.

The framing bound is the whole 3D view, `getSize()` (AD-30). A FreeCAD window so small that the MDI
area shows scrollbars and scrolls part of the 3D view off screen is out of scope: the bridge does
not measure the visible part of a scrolled view (Story 10.4 D8; F-27 is not a defect). FreeCAD also
clamps the window height (a request for 640 x 400 landed as 640 x 643 in run `2026-10-03-04`). So
the resize below keeps the whole 3D view on screen.

**Given** a document is open, Show All is run, and the model is fitted — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK` and the `framing:` line of `query_tree_summary` reads `fits, ratio R, computed`; record R as `ratio_before`  
**And** the original window size is recorded — verify: `cua-driver call list_windows` reports `<orig_w>` and `<orig_h>`  

**When** the tree is read a second time with nothing changed  
```
mcp query_tree_summary { doc: "<handle>" }
```
**And** the FreeCAD window is narrowed to about 60 % of its width, with its height unchanged, so the 3D view changes size and aspect but stays wholly visible  
```bash
'{"pid":<pid>,"window_id":<wid>,"frame":{"width":<0.6 × orig_w>,"height":<orig_h>}}' | & cua-driver call set_window_frame
```
**And** the tree is read again  
```
mcp query_tree_summary { doc: "<handle>" }
```

**Then** the second identical read is served from cache — verify: its `framing:` line carries `cached`  
**And** a cached verdict names its unverified components — verify: on the pure-query path the cached line ends with a reason that names `geometry`, since no cheap digest is available there  
**And** the window geometry was really applied — verify: `cua-driver call list_windows` reports the requested width and height. A `set_window_frame` that did not land makes the next two assertions meaningless  
**And** the 3D view stays wholly on screen — verify: the after capture below shows no scrollbar in the MDI area. If one shows, the size is out of scope for this scenario: restore the window and repeat with a larger width  
**And** the resize invalidates the cache — verify: the third read's `framing:` line carries `computed`, not `cached`  
**And** the re-measured verdict reflects the narrower view — verify: the third read's ratio differs from `ratio_before`; record both. With the width now the binding axis, the same model fills more of the view, so the ratio is expected to be larger, and above `1.0` the line reads `does not fit`  
**And** *(visual)* the narrower window shows the model as the verdict says — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-13-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: a visibly narrower window with no MDI scrollbar, and whether the model is whole inside the 3D view or cut off at its left or right edge. That must agree with `fits` or `does not fit` on the third read. Judge by looking at the image, not by comparing the reported ratios. The judgement is on the pixels alone — no MCP status or ratio may stand in for looking at the image.  

**Cleanup**:
```bash
'{"pid":<pid>,"window_id":<wid>,"frame":{"width":<orig_w>,"height":<orig_h>}}' | & cua-driver call set_window_frame
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-14-14: A suspect document refuses the fit

**Priority**: High
**Design Ref**: `spec-8-3` §Boundaries (quarantine is free via `mutating`); `adapters/mcp_server.py:255-272`; AD-27

**Host**: H1 headless (`hosts/headless/entry.py` front plus worker). The front runs
`adapters/mcp_server.py`, which marks a document suspect when a mutating call on it times out, and
refuses every later mutating call on it before dispatch (`mcp_server.py:264-272`). The GUI listener
has its own suspect set (`rpc_listener.py:420-424`), but a timed-out body on the GUI holds the
human's window, so this runs on H1. A `script_exec` busy body makes the timeout; `script_exec` is
on by default.

**Given** the H1 host is started with `FREECAD_BUDDY_AUDIT_LOG` pointing at `$RUN_DIR/evidence/tc-14-14-audit.jsonl`, and a golden model is open on it — verify: `H1: document_open` returns `OK`; record `<suspect handle>`  
**And** the document is made suspect by a timed-out mutating call — verify: `H1: script_exec { doc: "<suspect handle>", code: "import time\ntime.sleep(45)" }` returns `TIMEOUT` after about 30 s, and its message says `the document is now suspect`  
**And** the GUI window's current state is captured before the attempt — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-14-before.png"}' | & cua-driver call get_window_state`  
**And** the audit log tail position is recorded — verify: `wc -l "$RUN_DIR/evidence/tc-14-14-audit.jsonl"`  

**When** the fit is attempted on the suspect handle, at once, while the abandoned body may still run. Send no `query_*` read on that handle first: a read that returns `OK` clears the suspect flag.  
```
H1: view_fit_viewport { doc: "<suspect handle>" }
```

**Then** the fit is refused — verify: `status` is `INVALID_INPUT` and `detail.message` is `document-suspect: a prior call timed out on this document and its body may still be running; run a query_* read to confirm the document still responds before mutating`  
**And** it is refused **before** dispatch — verify: the call returns in under 1 s, and the audit lines past the recorded tail are only the boundary's own `view_fit_viewport` pair (a `before` line and an `after` line with `INVALID_INPUT`); no record carries `camera_before`, which only a dispatched fit writes  
**And** the host is named in the result record — verify: the run report states this ran under the H1 host  
**And** *(visual)* the GUI camera did not move — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-14-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and compare: the same view at the same size, position, and orientation, no dialog raised. **No fit is performed first here, by either route** — the MCP fit is the very action the suspect check must refuse, and a GUI fit would move the camera and destroy the comparison. The judgement is on the pixels alone — no MCP status may stand in for looking at the images.  

**Cleanup**: wait until the abandoned body has returned (`H1: query_capabilities {}` returns `OK` instead of `TIMEOUT` with `quarantined: true`), clear the suspect flag with a read (`document_close` is mutating, so it is refused while the flag is set), close the document, then stop the H1 host.
```
H1: query_tree_summary { doc: "<suspect handle>" }
H1: document_close { doc: "<suspect handle>" }
```

---

### TC-14-15: check_imports.py flags FreeCADGui.ActiveDocument (story 8.5 alias gap)

**Priority**: High
**Design Ref**: §AD-20; `spec-8-5-enforcement-framing-test-ci-alias-gap.md`; `scripts/check_imports.py:52`

Story 8.5 closed a live pre-existing defect: `FREECAD_MODULE_ALIASES` omitted `FreeCADGui`, so
`FreeCADGui.ActiveDocument` evaded the AD-20 implicit-target ban in CI.

**Host**: none — this is a repo-level CI gate. Its closing visual asserts the planted probe file
never reached the running application.

**Given** the source tree is clean — verify: `git status --porcelain src` is empty. The gate reads only `src/`; run artifacts elsewhere in the tree do not matter here  
**And** a document is open and fitted in the GUI, as the untouched baseline — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`  
**And** that baseline is captured — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-15-before.png"}' | & cua-driver call get_window_state`  

**When** the gate is run on the shipped tree  
```bash
uv run python scripts/check_imports.py; echo "exit=$?"
```
**And** a violation is planted in a scratch file under a checked ring, and the gate is re-run  
```bash
printf 'import FreeCADGui\nd = FreeCADGui.ActiveDocument\n' > src/freecad_buddy/usecases/_tc14_probe.py
uv run python scripts/check_imports.py; echo "exit=$?"
```

**Then** the shipped tree passes — verify: the first run exits `0`  
**And** the planted violation is caught — verify: the second run exits non-zero  
**And** the message names the real rule — verify: the output names `ActiveDocument` and the offending file, rather than failing for an unrelated reason  
**And** `FreeCADGui` is in the alias set — verify: `grep -n "FREECAD_MODULE_ALIASES" -A6 scripts/check_imports.py` lists `FreeCADGui`  
**And** the live source is clean of the pattern in code — verify: `grep -rn --include=*.py "FreeCADGui.ActiveDocument" src/` returns only docstring prose (two lines in `hosts/gui_addon/viewport.py` that state the rule), and `uv run python scripts/check_imports.py` passing on the shipped tree confirms no code use  
**And** *(visual)* the running application was never affected by the probe — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`, or failing that frame with the **Fit All** toolbar button by `element_token`; then `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-15-after.png"}' | & cua-driver call get_window_state`; `Read` both PNGs and compare: the same model, whole and unchanged, no error dialog or addon-failure popup. The probe is a static-analysis fixture and must never be imported by the live addon. The judgement is on the pixels alone — no MCP status may stand in for looking at the images.  

**Cleanup**:
```bash
rm -f src/freecad_buddy/usecases/_tc14_probe.py
git status --porcelain src   # must be empty again
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-14-16: The fit does not alter geometry

**Priority**: Critical
**Design Ref**: §AD-6 (fingerprint is a geometry digest); `spec-8-3` §Never

A camera move is not a geometry change. The tool is `mutating=True` only so it is audited and
quarantine-gated — the fingerprint must not move.

**Given** a golden model is open — verify: `document_open` on `box-10-20-30.FCStd` returns `OK`, then run Show All  
**And** the fingerprint is recorded — verify: save the whole `structured_content` of `mcp verify_shape { doc: "<handle>", object: "Box" }` as `fp_before`. `verify_shape` returns no digest field, so its whole measured block stands in for one; `preview_dry_run` `fingerprint_before` is an alternative digest  
**And** the volume is recorded — verify: `mcp query_mass_properties { doc: "<handle>", object: "Box" }` returns `6000.0` mm³ within 0.1 %  
**And** the document's modified state is recorded after Show All — verify: the window title from `list_windows` (Show All itself marks the document `*` modified)  

**When** the document is fitted  
```
mcp view_fit_viewport { doc: "<handle>" }
```
**And** the fingerprint is read again  
```
mcp verify_shape { doc: "<handle>", object: "Box" }
```

**Then** the fingerprint is unchanged — verify: the new `structured_content` equals `fp_before` exactly, unchanged across the fit  
**And** the volume is unchanged — verify: `mcp query_mass_properties { doc: "<handle>", object: "Box" }` still returns `6000.0` mm³ within 0.1 %  
**And** the document's modified state is unchanged across the fit — verify: the window title is the same as the one recorded after Show All  
**And** no recompute was triggered — verify: `mcp verify_recompute { doc: "<handle>" }` returns `OK` with `subject.failing_objects` empty  
**And** *(visual)* the same geometry is on screen, only better framed — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-14-16-after.png"}' | & cua-driver call get_window_state`, then `Read` the PNG and say what is on screen: one box-shaped solid of unchanged proportions, with no added, removed, or deformed feature. An identical fingerprint proves the digest did not change, not that the human is still looking at the same shape. The judgement is on the pixels alone — no MCP status or fingerprint may stand in for looking at the image.  

**Cleanup**:
```
mcp document_close { doc: "<handle>" }
```
