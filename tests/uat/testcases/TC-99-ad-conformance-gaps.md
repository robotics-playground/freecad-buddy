# TC-99: Architecture-Decision Conformance Gaps (EXPECTED-FAIL)

**This file is the CONFORMANCE GATE (test-plan §9 Gate 2), not the release gate. It is NOT part of
the green suite.**

Every scenario below asserts a behavior an architecture decision specifies and the shipped code
does NOT implement. **Every scenario here is expected to FAIL against the current build.** A run
that reports all five failing is the correct, expected result.

The parts of AD-25 that the code implements are in the green gate, in TC-11: the workdir and the
per-host session temp folder (TC-11-18), and the start sweep (TC-11-19). This file keeps only the
AD-25 parts the code does not implement: the `snap/ exports/ audit.log tmp/` layout and a
session-named workdir (TC-99-04), snapshot location and naming (TC-99-05), and the audit log
location (TC-99-06).

Reading the result:
- A scenario that **fails** is the recorded, accepted state. It does not block the release.
- A scenario that **starts passing** is a **promotion signal**: the code gained the behavior. Move
  the scenario into the green gate — TC-11, where the AD-3 and AD-25 checks live — close the gap
  in the spine, and delete it from this file. It is **not** a regression and must never be reported
  as one.
- A scenario that fails **differently** than documented is a real finding. The documented deviation
  is part of the assertion.

Each scenario names four things: the AD, what the AD specifies, what the code actually does today,
and the `file:line` evidence. Every citation below was read in the source before it was written
here. Each scenario carries a `**Shipped behavior today**:` section and an `**Expected result**:`
line — deliberate additions to the house template, following the precedent of TC-06's
`**Divergence handling**:` section. The `**Expected result**:` line is what lets an executor tell
"failed as documented" from "failed differently".

**Host**: GUI through the H2 proxy for every scenario. TC-99-04 and TC-99-06 also start H1
headless, to show the headless default locations:
`"$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline`. The probes are
transport, filesystem and concurrency probes with no visible model effect, so each scenario opens
a golden model as an untouched baseline and its closing visual asserts the probe left the running
application coherent and unchanged.

**Evidence hierarchy (test-plan §3).** We are BUILDING the MCP bridge, so its own output can never
be the test result. Commit `636fb8a` fixed a defect where the bridge reported a successful fit
while the part occupied about 5 % of the viewport — a correct-looking report over a wrong reality.

| Rank | Artifact | Trust |
| --- | --- | --- |
| 1 | A `cua-driver` pixel capture of the real FreeCAD window, `Read` and judged by the agent | The test result |
| 2 | Filesystem, exit codes, `curl` status lines, socket behaviour observed directly | Corroborating |
| 3 | MCP envelope fields, statuses, `query_screenshot` renders | **Claims under test, never evidence** |

For TC-99 rank 2 carries most of the weight, which is correct: the `Then` lines below assert HTTP
status lines, `grep` results, socket errors and directory listings observed directly. The closing
visual is rank 1 and is judged on pixels alone. `mcp view_fit_viewport` is itself code under test,
so every auto-fit below carries a GUI fallback through the **Fit All** toolbar button, which touches none of
the code under test. Both the `before.png` and the `after.png` are captured after that same fit, so
the two images share a camera and a difference between them is a real change, not a camera move.

## Preconditions

- [ ] The repository is at the revision under test (verify: `git rev-parse HEAD`)
- [ ] FreeCAD 1.1.x installed (verify: `ls "$FREECAD_EXE"`); the build under test is the live version: `query_capabilities.freecad_version`, read once at the start of the run and written `<live version>` below
- [ ] Golden and fault `.FCStd` files have no `GuiDocument.xml` and open with every object hidden. After each `document_open` of such a file, and before any fit or render of it, run **Show All**: `cua-driver call invoke_menu { pid, window_id, path: ["View","Visibility","Show All Objects"] }`. A fit before it returns `SPEC_FAILED view_fit.nothing_to_frame`.
- [ ] micromamba `fcb` env is H1-capable, for the headless legs of TC-99-04 and TC-99-06 (verify: `"$FCB_PYTHON" -c "import FreeCAD, mcp"`)
- [ ] FreeCAD GUI is running with the addon loaded (verify: `netstat -ano | grep ":8765" | grep LISTENING`)
- [ ] `curl` is available (verify: `curl --version`)
- [ ] Golden models are present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)
- [ ] `cua-driver` can drive the FreeCAD window (verify: `'{"pid":<pid>,"window_id":<wid>}' | & cua-driver call get_window_state` returns a `QOpenGLWidget`)
- [ ] `$RUN_DIR/evidence/` exists and is writable (verify: `ls "$RUN_DIR/evidence"`)

---

### TC-99-01: The HTTP endpoint requires a bearer token

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §2 (AD-3 transport authentication)

**What AD-3 specifies**: every request to the MCP HTTP endpoint must present a bearer token, and
a request without one is refused before any tool is reached.

**Shipped behavior today**: there is no authentication of any kind on `:8765`.
`build_app` returns
`Starlette(routes=[Route("/healthz", _healthz, methods=["GET"]), Mount("/mcp", app=_handle)], lifespan=_lifespan)`
at `src/freecad_buddy/hosts/gui_external/entry.py:122-125` — a health route and a bare mount, with
no `middleware=` argument, no authentication dependency, and no token check anywhere in the module.
An unauthenticated POST to `http://127.0.0.1:8765/mcp` is served and can call every tool in the
live count, including every mutating one and `script_exec`, which is on by default. The loopback
bind (`_HOST = "127.0.0.1"`, `src/freecad_buddy/hosts/gui_external/entry.py:44`) is the only
control that ships. Any local
process, and any local browser page that can reach the port, is fully authorized.

**Given** the proxy is serving on `127.0.0.1:8765`  
**And** a golden model is open as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the framed baseline is captured, after that same fit, so both images share a camera — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-01-before.png"}' | & cua-driver call get_window_state`  

**When** an unauthenticated request is sent and the HTTP status is recorded  
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8765/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```
**And** a full unauthenticated MCP session is completed: `initialize`, then the  
`notifications/initialized` notification, then `tools/list`, carrying the
`Mcp-Session-Id` returned by `initialize` and **no credential of any kind**. Use an MCP
client against `http://127.0.0.1:8765/mcp` rather than raw `curl` for this step.
**And** that session is repeated with a deliberately WRONG `Authorization: Bearer <garbage>` header.  
**And** from that same unauthenticated session, a mutating tool is called.  

**Then** the unauthenticated request is refused with an auth challenge — verify: the unauthenticated `curl` status is `401` or `403`. **Expected failure: it is `307`, and following the redirect yields `400` with `-32600 Bad Request: Missing session ID` — an MCP protocol requirement, NOT authentication. Record the exact status and code; a `400/-32600` is the documented deviation, and any auth-shaped refusal is a real change.**  
**And** no tool list is disclosed without credentials — verify: the unauthenticated session's `tools/list` result contains no tool names. **Expected failure: the full tool list (the live count, 46 by default) is returned to a caller that presented no credential.**  
**And** a wrong bearer token is refused — verify: the wrong-`Authorization` session is rejected with `401`. **Expected failure: the `Authorization` header is ignored entirely and the session succeeds.**  
**And** an unauthenticated mutation is refused — verify: the mutating call is rejected with `401` and the document fingerprint is unchanged. **Expected failure: the mutation runs and the fingerprint changes.**  
**And** an authentication middleware exists — verify: `grep -n "middleware\|AuthenticationMiddleware\|Bearer" src/freecad_buddy/hosts/gui_external/entry.py` returns a match. **Expected failure: it returns nothing.**  
**And** the refusal is logged — verify: `grep -i "unauthorized\|401" "$APPDATA/FreeCAD/v1-1/freecad-buddy/mcp-proxy.log"` returns a line. **Expected failure: nothing is logged.**  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the unauthenticated traffic left the application coherent and unchanged — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-01-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: one box drawn in the viewport, all edges inside the frame, the viewport fully painted with no blank or torn region, no modal dialog or error popup covering it, no "Not Responding" in the title bar, and the after image showing the same box at the same size and position as the before image. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Expected result**: FAIL. `:8765` accepts the unauthenticated session and serves the full tool  
list; the `Authorization` header is ignored; no middleware and no refusal log line exist. Only the
visual closer passes: the window is untouched.

**Cleanup**:
```bash
# Close any document the unauthenticated mutation created.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-99-02: Origin is validated against a localhost allowlist

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §2 (AD-3 DNS-rebinding defense)

**What AD-3 specifies**: the endpoint validates the `Origin` header against a localhost
allowlist, so a page served from a foreign origin cannot drive the bridge through the user's
browser (DNS rebinding).

**Shipped behavior today**: no `Origin` check exists. A repository-wide search for the header
finds only FreeCAD's unrelated `App::Origin` object type and an `origin` geometry field in
`src/freecad_buddy/contracts/assertions.py:15` — no HTTP header handling at all. There is no
CORS middleware either; `build_app` (`src/freecad_buddy/hosts/gui_external/entry.py:107-125`)
constructs the Starlette application with routes and a lifespan only. A request carrying
`Origin: https://attacker.example` is served identically to one with no `Origin`.

**Given** the proxy is serving on `127.0.0.1:8765`  
**And** a golden model is open as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the framed baseline is captured, after that same fit, so both images share a camera — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-02-before.png"}' | & cua-driver call get_window_state`  

**When** a request carrying a foreign `Origin` is sent  
```bash
curl -s -i -X POST http://127.0.0.1:8765/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Origin: https://attacker.example" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```
**And** the same request is repeated with `Origin: http://localhost:3000`.  
**And** a CORS preflight `OPTIONS` request is sent with the foreign origin.  

**Then** the foreign origin is refused — verify: the foreign-`Origin` response status is `403`. **Expected failure: the request is served.**  
**And** no tool list is disclosed to the foreign origin — verify: the foreign-`Origin` body contains no tool names. **Expected failure: the full list is returned.**  
**And** a localhost origin is allowed — verify: the `localhost:3000` response status is a success code. **Expected failure: this passes for the wrong reason — everything is allowed.**  
**And** the preflight refuses the foreign origin — verify: the `OPTIONS` response carries no `Access-Control-Allow-Origin` naming `attacker.example`. **Expected failure: no CORS handling exists, so no header is emitted and the check cannot distinguish refusal from absence.**  
**And** an allowlist exists in source — verify: `grep -rn "Origin" src/freecad_buddy/hosts/ src/freecad_buddy/adapters/` returns an HTTP header check. **Expected failure: it returns nothing.**  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the foreign-origin traffic left the application coherent and unchanged — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-02-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: one box drawn in the viewport, all edges inside the frame, the viewport fully painted with no blank or torn region, no modal dialog or error popup covering it, no "Not Responding" in the title bar, and the after image showing the same box at the same size and position as the before image. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Expected result**: FAIL. Every `Origin` is served identically, including  
`https://attacker.example`; the preflight produces no CORS headers at all; no header check exists
in source. The localhost checkpoint passes vacuously. Only the visual closer passes.

**Cleanup**:
```bash
# No files written.
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-99-04: The session workdir is session-named and laid out as snap/ exports/ audit.log tmp/

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-25 session workdir), `project-structure.md` §6

**What AD-25 specifies**: the bridge creates one session-scoped working directory at start, laid
out as `snap/ exports/ audit.log tmp/`, and every file it writes lands inside it. That makes the
whole footprint of a session findable, sweepable and attributable to one session.

**Shipped behavior today**: a workdir exists, but it is one shared folder, not one per session.
`workdir_root` returns `FREECAD_BUDDY_WORKDIR`, else the cwd-relative `freecad-buddy-workdir`
(`src/freecad_buddy/usecases/documents.py:42-52`). The GUI addon sets the variable to
`<FreeCAD user app data>/freecad-buddy/workdir` when it is unset
(`src/freecad_buddy/usecases/operator_settings.py:89`), so every GUI session shares that one
folder. A headless host started without the variable uses `freecad-buddy-workdir` under its own
working directory. Inside the workdir only `tmp/` exists. It holds one
`FCB_TMP_session_<pid>_<token>` folder per host process (`documents.py:61-73`), and every bridge
temp file is minted there (that part passes, in TC-11-18). There is no `snap/` and no `exports/`,
and the audit log is outside the workdir (TC-99-06).

**Given** FreeCAD has just been started with the addon loaded and `FREECAD_BUDDY_WORKDIR` unset — verify: the `operator settings:` line in `addon.log` contains `FREECAD_BUDDY_WORKDIR='<FreeCAD user app data>\freecad-buddy\workdir' (default)`  
**And** a golden model is open as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the framed baseline is captured, after that same fit, so both images share a camera — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-04-before.png"}' | & cua-driver call get_window_state`  

**When** the GUI workdir is listed after one mutation, one preview, one screenshot and one export on a scratch document. The agent shell may get "Access is denied" for the session folder: list it in-process with `script_exec`  
```bash
ls -R "$APPDATA/FreeCAD/v1-1/freecad-buddy/"
```
**And** H1 headless is started in a scratch directory `A` with `FREECAD_BUDDY_WORKDIR` unset, one `query_screenshot` is run on it, and `A` is listed. The `serve` command below is the server command that an MCP stdio client spawns with working directory `A` (`StdioServerParameters(..., cwd=A)`); it does not return while the session is open. The client runs its call and exits, which stops H1, and `A` is listed after that  
```bash
mkdir -p "$RUN_DIR/evidence/tc-99-04-A"
# spawned by the stdio client, cwd = $RUN_DIR/evidence/tc-99-04-A, FREECAD_BUDDY_WORKDIR removed from env:
"$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline
# after the client has exited:
ls -R "$RUN_DIR/evidence/tc-99-04-A"
```

**Then** the workdir is named for its session — verify: the workdir path carries a session identifier. **Expected failure: the GUI workdir is the fixed `<FreeCAD user app data>\freecad-buddy\workdir`, shared by every GUI session; only `tmp/FCB_TMP_session_<pid>_<token>/` is per host.**  
**And** it contains `snap/` — verify: the subdirectory exists. **Expected failure: absent.**  
**And** it contains `exports/` — verify: the subdirectory exists. **Expected failure: absent.**  
**And** it contains `tmp/` — verify: the subdirectory exists. This checkpoint passes; TC-11-18 covers it.  
**And** it contains the audit log — verify: an audit file exists inside the workdir. **Expected failure: absent; the GUI audit log is `<FreeCAD user app data>\freecad-buddy\audit.jsonl`, beside the workdir, see TC-99-06.**  
**And** the headless default does not depend on the working directory — verify: the H1 workdir is not under `A`. **Expected failure: H1 created `A/freecad-buddy-workdir/tmp/FCB_TMP_session_<worker pid>_<token>/` (`documents.py:43`).**  
**And** the layout exists in source — verify: `grep -rnE '"snap"|"exports"' src/freecad_buddy/usecases/documents.py` returns a match. **Expected failure: it returns nothing.**  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the probe calls left the application coherent and the baseline unchanged — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-04-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: the baseline box drawn whole inside the frame, the viewport fully painted with no blank or torn region, no modal dialog or error popup left behind by the mutation, preview, screenshot or export, no "Not Responding" in the title bar, and the after image showing the same box at the same size and position as the before image. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Expected result**: FAIL. The GUI workdir is one shared, fixed folder with only `tmp/` inside it;
no `snap/`, no `exports/`, no audit log inside. H1 without `FREECAD_BUDDY_WORKDIR` puts its
workdir under its own working directory. The `tmp/` checkpoint and the visual closer pass.

**Cleanup**:
```bash
# Stop the H1 host first.
rm -rf "$RUN_DIR/evidence/tc-99-04-A"
```
```
mcp document_close { doc: "<scratch handle>" }
mcp document_close { doc: "<handle>" }
```

---

### TC-99-05: Snapshots live in the session workdir's snap/ and are named by transaction

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-25 snapshot location)

**What AD-25 specifies**: a pre-mutation `saveCopy` snapshot is written under the session
workdir's `snap/` subdirectory and named `<doc-Name>.<transaction-id>.FCStd`, so an operator
recovering from a failed mutation knows exactly one place to look, and a session's snapshots are
enumerable from that one place.

**Shipped behavior today**: `temp_snapshot_path` calls
`tempfile.mkdtemp(prefix=_SNAPSHOT_PREFIX, dir=temp_dir())` and returns
`os.path.join(directory, f"{doc.Name}.FCStd")`
(`src/freecad_buddy/usecases/transaction.py:107-108`), with
`_SNAPSHOT_PREFIX = "FCB_TMP_snap_"` at `src/freecad_buddy/usecases/transaction.py:43`. The
snapshot is inside the host's session temp folder (that part passes, in TC-11-18), but each one
gets its own fresh `FCB_TMP_snap_<random>` directory, there is no shared `snap/` directory, and
the file name carries no transaction id. A kept snapshot is reported in `mutation.snapshot_path`,
so it is discoverable per call, but not from one location.

**Given** the golden model is open as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the framed baseline is captured, after that same fit, so both images share a camera — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-05-before.png"}' | & cua-driver call get_window_state`  

**When** the snapshot path the bracket would use is read twice in-process, the same call `_bracket` makes before `saveCopy` (`transaction.py:637-639`), without running a mutation  
```
script_exec { doc: "<handle>", code: "from freecad_buddy.usecases import transaction; result = (transaction.temp_snapshot_path(doc), transaction.temp_snapshot_path(doc))" }
```

**Then** the snapshot path is under a `snap/` directory — verify: each path's parent directory basename is `snap`. **Expected failure: it is `FCB_TMP_snap_<random>`.**  
**And** all of a session's snapshots are in one directory — verify: the two paths share a parent. **Expected failure: each gets its own fresh `mkdtemp` directory.**  
**And** the name carries the transaction id — verify: each basename matches `<doc Name>.<transaction id>.FCStd`. **Expected failure: it is `<doc Name>.FCStd`.**  
**And** the snapshot is inside the host's session folder — verify: each path starts with the `temp_dir()` folder. This checkpoint passes; TC-11-18 covers it.  
**And** the source names a session snap directory — verify: `grep -n '"snap"' src/freecad_buddy/usecases/transaction.py` returns a match. **Expected failure: it returns nothing; line 107 is `tempfile.mkdtemp`.**  
**And** *(visual)* the model is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the probe left the application coherent and the baseline unchanged — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-05-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: the baseline box drawn whole inside the frame with no added, removed or deformed feature, the viewport fully painted with no blank or torn region, no modal dialog or error popup, no "Not Responding" in the title bar, and the after image showing the same box at the same size and position as the before image. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Expected result**: FAIL. Each path is `<session folder>/FCB_TMP_snap_<random>/<doc Name>.FCStd`,
the two paths have different parents, and `grep` finds no `"snap"` in `transaction.py`. The
session-folder checkpoint and the visual closer pass.

**Cleanup**:
```
script_exec { doc: "<handle>", code: "import os, shutil; [shutil.rmtree(os.path.dirname(p)) for p in (<path 1>, <path 2>)]" }
mcp document_close { doc: "<handle>" }
```

---

### TC-99-06: The audit log is written per session to a dated file under the workdir

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-25 audit location), `security-and-service-design.md` §1 (audit)

**What AD-25 specifies**: each session writes its audit records to a dated file inside that
session's workdir, so the audit trail is attributable to a session and its location does not
depend on how the host was launched.

**Shipped behavior today**: the audit log is one undated file outside the workdir, shared by every
session, with no session field. `default_audit_path` returns
`Path(os.environ.get("FREECAD_BUDDY_AUDIT_LOG", "freecad-buddy-audit.jsonl"))`
(`src/freecad_buddy/adapters/audit_log.py:24-26`). The GUI addon sets the variable, when the
**Audit log file** preference is empty, to `<FreeCAD user app data>/freecad-buddy/audit.jsonl`
(`src/freecad_buddy/usecases/operator_settings.py:88`): an absolute path beside the workdir, not
inside it, and the same file for every GUI session. A headless host started without the variable
falls back to the bare relative name, so its audit log lands in its own working directory.
`AuditSink._record` (`src/freecad_buddy/adapters/audit_log.py:51-69`) writes `schema`, `ts`,
`actor`, `event`, `tool`, `params_digest` and optionally `doc` and `code` — no session field.

**Given** `FREECAD_BUDDY_AUDIT_LOG` is unset and the **Audit log file** preference is empty, so the default paths are exercised — verify: the `operator settings:` line in `addon.log` contains `FREECAD_BUDDY_AUDIT_LOG='<FreeCAD user app data>\freecad-buddy\audit.jsonl' (default)`  
**And** a golden model is open as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: run Show All, then `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the framed baseline is captured, after that same fit, so both images share a camera — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-06-before.png"}' | & cua-driver call get_window_state`  

**When** one mutation is run on a scratch document in the GUI, and the GUI audit log is read  
**And** H1 headless is started in directory `A` with the variable unset, one mutation is run, and it is stopped; then the same in directory `B`. Each `serve` command below is the server command that an MCP stdio client spawns with that working directory (`StdioServerParameters(..., cwd=A)`, then `cwd=B`); it does not return while the session is open. The client runs its mutation and exits, which stops H1, and both directories are listed after both clients have exited  
```bash
mkdir -p "$RUN_DIR/evidence/tc-99-06-A" "$RUN_DIR/evidence/tc-99-06-B"
# spawned by the stdio client, cwd = A, then again with cwd = B; FREECAD_BUDDY_AUDIT_LOG removed from env:
"$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline
# after both clients have exited:
ls "$RUN_DIR/evidence/tc-99-06-A" "$RUN_DIR/evidence/tc-99-06-B"
```

**Then** the GUI audit log is under the session workdir — verify: the GUI log path starts with the workdir. **Expected failure: it is `<FreeCAD user app data>\freecad-buddy\audit.jsonl`, beside `workdir\`.**  
**And** the filename carries a date — verify: the basename contains an ISO date. **Expected failure: the basenames are the fixed `audit.jsonl` (GUI) and `freecad-buddy-audit.jsonl` (H1).**  
**And** two GUI sessions do not share one file — verify: the path depends on the session. **Expected failure: every GUI session appends to the same `audit.jsonl`; the path in the `operator settings:` line is the same on every start.**  
**And** the headless path does not depend on the working directory — verify: the `A` and `B` log paths are in the same parent. **Expected failure: they are `A/freecad-buddy-audit.jsonl` and `B/freecad-buddy-audit.jsonl`.**  
**And** each record names its session — verify: every audit line carries a session identifier field. **Expected failure: no line has one.**  
**And** the headless default is absolute — verify: the default path in source is absolute. **Expected failure: `audit_log.py:24-26` supplies a bare relative filename.**  
**And** *(visual)* the model is framed — verify: fit through the GUI with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.x with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. `mcp view_fit_viewport` may be used only if it returns `OK`.  
**And** *(visual)* the probes left the application coherent and the baseline unchanged — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-06-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: the baseline box drawn whole inside the frame, the viewport fully painted with no blank or torn region, no error dialog or popup, no "Not Responding" in the title bar, and the after image showing the same box at the same size and position as the before image. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Expected result**: FAIL. The GUI writes one undated, shared `audit.jsonl` outside the workdir;
H1 follows its working directory (`A/freecad-buddy-audit.jsonl`, then `B/…`); no record carries a
session field. Only the visual closer passes.

**Cleanup**:
```bash
# Stop the H1 hosts first.
rm -rf "$RUN_DIR/evidence/tc-99-06-A" "$RUN_DIR/evidence/tc-99-06-B"
```
```
mcp document_close { doc: "<scratch handle>" }
mcp document_close { doc: "<handle>" }
```

---

## Gap summary

| AD | Scenario | Shipped evidence (`file:line`) | What must change to make it pass |
|----|----------|--------------------------------|----------------------------------|
| AD-3 | TC-99-01 bearer token | `hosts/gui_external/entry.py:122-125` — `/healthz` route and a bare `Mount("/mcp")`, no `middleware=` | Add authentication middleware to `build_app`; mint and check a per-session bearer token |
| AD-3 | TC-99-02 Origin allowlist | `hosts/gui_external/entry.py:107-125` — no CORS, no header check anywhere in `src/` | Add `Origin` validation against a localhost allowlist before the mount handles the request |
| AD-25 | TC-99-04 session-named workdir and layout | `usecases/documents.py:42-52` — one shared workdir, cwd-relative headless default; `usecases/operator_settings.py:89` — fixed GUI workdir; only `tmp/` exists | Name the workdir per session and create `snap/ exports/ audit.log tmp/` in it at bridge start |
| AD-25 | TC-99-05 snapshots in `snap/`, named by transaction | `usecases/transaction.py:107-108` — `tempfile.mkdtemp(prefix=_SNAPSHOT_PREFIX, dir=temp_dir())`, file `<doc.Name>.FCStd` | Write each snapshot to `<session workdir>/snap/<doc-Name>.<transaction-id>.FCStd` |
| AD-25 | TC-99-06 per-session dated audit log | `adapters/audit_log.py:24-26` — cwd-relative headless default; `usecases/operator_settings.py:88` — one shared GUI `audit.jsonl` beside the workdir; `:51-69` record carries no session field | Default the audit path to a dated file under the session workdir and add a session field to the record |
