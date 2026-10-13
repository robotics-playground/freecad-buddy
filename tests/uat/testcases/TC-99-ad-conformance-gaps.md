# TC-99: Architecture-Decision Conformance Gaps (EXPECTED-FAIL)

**This file is the CONFORMANCE GATE (test-plan §9 Gate 2), not the release gate. It is NOT part of
the green suite.**

Every scenario below asserts a behavior an architecture decision specifies and the shipped code
does NOT implement. **Every scenario here is expected to FAIL against the current build.** A run
that reports all seven failing is the correct, expected result.

Reading the result:
- A scenario that **fails** is the recorded, accepted state. It does not block the release.
- A scenario that **starts passing** is a **promotion signal**: the code gained the behavior. Move
  the scenario into the green gate (TC-10 or TC-11 as the table at the end directs), close the gap
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

**Host**: GUI through the H2 proxy for every scenario. The probes are transport, filesystem and
concurrency probes with no visible model effect, so each scenario opens a golden model as an
untouched baseline and its closing visual asserts the probe left the running application coherent
and unchanged.

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
so every auto-fit below carries a GUI fallback through **View → Fit All**, which touches none of
the code under test. Both the `before.png` and the `after.png` are captured after that same fit, so
the two images share a camera and a difference between them is a real change, not a camera move.

## Preconditions

- [ ] The repository is at the revision under test (verify: `git rev-parse HEAD`)
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
`build_app` returns `Starlette(routes=[Mount("/mcp", app=_handle)], lifespan=_lifespan)` at
`src/freecad_buddy/hosts/gui_external/entry.py:157` — a bare mount with no `middleware=` argument,
no authentication dependency, and no token check anywhere in the module. An unauthenticated POST
to `http://127.0.0.1:8765/mcp` is served and can call every one of the 44 tools, including every
mutating one. The loopback bind (`_HOST = "127.0.0.1"`,
`src/freecad_buddy/hosts/gui_external/entry.py:38`) is the only control that ships. Any local
process, and any local browser page that can reach the port, is fully authorized.

**Given** the proxy is serving on `127.0.0.1:8765`  
**And** a golden model is open as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
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
**And** no tool list is disclosed without credentials — verify: the unauthenticated session's `tools/list` result contains no tool names. **Expected failure: the full 44-tool list is returned to a caller that presented no credential.**  
**And** a wrong bearer token is refused — verify: the wrong-`Authorization` session is rejected with `401`. **Expected failure: the `Authorization` header is ignored entirely and the session succeeds.**  
**And** an unauthenticated mutation is refused — verify: the mutating call is rejected with `401` and the document fingerprint is unchanged. **Expected failure: the mutation runs and the fingerprint changes.**  
**And** an authentication middleware exists — verify: `grep -n "middleware\|AuthenticationMiddleware\|Bearer" src/freecad_buddy/hosts/gui_external/entry.py` returns a match. **Expected failure: it returns nothing.**  
**And** the refusal is logged — verify: `grep -i "unauthorized\|401" "$APPDATA/FreeCAD/v1-1/freecad-buddy/mcp-proxy.log"` returns a line. **Expected failure: nothing is logged.**  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the unauthenticated traffic left the application coherent and unchanged — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-01-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: one box drawn in the viewport, all edges inside the frame, the viewport fully painted with no blank or torn region, no modal dialog or error popup covering it, no "Not Responding" in the title bar, and the after image showing the same box at the same size and position as the before image. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Expected result**: FAIL. `:8765` accepts the unauthenticated session and serves the full 44-tool  
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
CORS middleware either; `build_app` (`src/freecad_buddy/hosts/gui_external/entry.py:145-157`)
constructs the Starlette application with routes and a lifespan only. A request carrying
`Origin: https://attacker.example` is served identically to one with no `Origin`.

**Given** the proxy is serving on `127.0.0.1:8765`  
**And** a golden model is open as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
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
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
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

### TC-99-04: Every file the bridge writes lives under a session workdir

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-25 session workdir)

**What AD-25 specifies**: the bridge creates one session-scoped working directory at start, laid
out as `snap/ exports/ audit.log tmp/`, and every file it writes lands inside it. That makes the
whole footprint of a session findable, sweepable and attributable to one session.

**Shipped behavior today**: no session workdir exists anywhere in the code. There is no
directory-creation call at bridge start and no layout constant. Files are scattered by mechanism
instead: snapshots go to `tempfile.mkdtemp(prefix="FCB_TMP_snap_")`
(`src/freecad_buddy/usecases/transaction.py:94`), preview copies to
`tempfile.mkdtemp(prefix="FCB_TMP_prev_")` (`src/freecad_buddy/usecases/preview.py:318`),
fingerprint scratch to `tempfile.mkstemp(prefix="FCB_TMP_fp_")`
(`src/freecad_buddy/usecases/fingerprint.py:73`), screenshots to
`tempfile.mkstemp(prefix="FCB_TMP_shot_")` (`src/freecad_buddy/usecases/screenshot.py:168`), the
audit log to a CWD-relative default (`src/freecad_buddy/adapters/audit_log.py:24`), and exports
to whatever `path` the caller supplied. The only directory the bridge owns is the discovery
directory `<appdata>/freecad-buddy` (`src/freecad_buddy/adapters/rpc_listener.py:178-180`), which
holds the discovery file only.

**Given** FreeCAD has just been started with the addon loaded  
**And** the session id is recorded  
**And** a golden model is open as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the framed baseline is captured, after that same fit, so both images share a camera — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-04-before.png"}' | & cua-driver call get_window_state`  

**When** a session workdir is searched for under the FreeCAD appdata directory  
```bash
ls -R "$APPDATA/FreeCAD/v1-1/freecad-buddy/"
```
**And** one mutation, one preview, one screenshot and one export are run  
**And** every file the bridge created during those four calls is enumerated and its directory recorded  

**Then** a session workdir exists — verify: a session-named directory is present in the `ls -R` listing. **Expected failure: only `addon.log`, `mcp-proxy.log` and `rpc-<pid>.json` are there.**  
**And** it contains `snap/` — verify: the subdirectory exists. **Expected failure: absent.**  
**And** it contains `exports/` — verify: the subdirectory exists. **Expected failure: absent.**  
**And** it contains `tmp/` — verify: the subdirectory exists. **Expected failure: absent.**  
**And** it contains `audit.log` — verify: the file exists. **Expected failure: absent; the audit log is CWD-relative, see TC-99-06.**  
**And** the snapshot landed inside `snap/` — verify: the mutation's snapshot path is under the workdir. **Expected failure: it is under the process temp directory.**  
**And** the preview copy landed inside `tmp/` — verify: the preview path is under the workdir. **Expected failure: it is under the process temp directory.**  
**And** a workdir constant exists in source — verify: `grep -rniE "session_dir|workdir|session_root" src/freecad_buddy/` returns a match. **Expected failure: it returns nothing.**  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the four probe calls left the application coherent and the baseline unchanged — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-04-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: the baseline box drawn whole inside the frame, the viewport fully painted with no blank or torn region, no modal dialog or error popup left behind by the mutation, preview, screenshot or export, no "Not Responding" in the title bar, and the after image showing the same box at the same size and position as the before image. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Expected result**: FAIL. The appdata directory holds only `addon.log`, `mcp-proxy.log` and  
`rpc-<pid>.json`; no session directory, no `snap/ exports/ tmp/ audit.log`. Snapshot and preview
paths resolve under the process temp directory, and no workdir constant exists in `src/`. Only the
visual closer passes.

**Cleanup**:
```bash
rm -rf "$TEMP"/FCB_TMP_*
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-99-05: Snapshots live in the session workdir's snap/

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-25 snapshot location)

**What AD-25 specifies**: a pre-mutation `saveCopy` snapshot is written under the session
workdir's `snap/` subdirectory, so an operator recovering from a failed mutation knows exactly
one place to look and a session's snapshots are never confused with another session's.

**Shipped behavior today**: `temp_snapshot_path` calls
`tempfile.mkdtemp(prefix=_SNAPSHOT_PREFIX)` at
`src/freecad_buddy/usecases/transaction.py:94`, where `_SNAPSHOT_PREFIX = "FCB_TMP_snap_"` is
defined at `src/freecad_buddy/usecases/transaction.py:39`. That places each snapshot in a fresh
directory under the operating system's process temp directory, not under any session directory.
The snapshot path is reported in `mutation.snapshot_path` when it is kept, so it is discoverable
per call, but the set of a session's snapshots is not enumerable from one location.

**Given** the process temp directory is known and its `FCB_TMP_snap_*` count is recorded  
**And** a golden model is open as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the framed baseline is captured, after that same fit, so both images share a camera — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-05-before.png"}' | & cua-driver call get_window_state`  

**When** a mutation is run that fails post-verify with an unproven rollback, so the snapshot is kept  
**And** the reported snapshot path is read from the envelope  
```bash
python3 -c "import json,sys;print(json.load(sys.stdin)['structured_content']['mutation']['snapshot_path'])"
```
**And** that path's parent chain is compared to the session workdir from TC-99-04  

**Then** the snapshot path is under a session workdir — verify: the reported path starts with the session workdir. **Expected failure: it starts with the process temp directory.**  
**And** its immediate parent is named `snap` — verify: the path's parent directory basename is `snap`. **Expected failure: it is `FCB_TMP_snap_<random>`.**  
**And** all of a session's snapshots are in one directory — verify: two failed mutations put their snapshots in the same parent. **Expected failure: each gets its own fresh `mkdtemp` directory.**  
**And** no snapshot is written to the process temp directory — verify: the `FCB_TMP_snap_*` count under `$TEMP` is unchanged. **Expected failure: the count increases by one per kept snapshot.**  
**And** the source names a session snap directory — verify: `grep -n "snap/" src/freecad_buddy/usecases/transaction.py` returns a match. **Expected failure: it returns nothing; line 94 is `tempfile.mkdtemp`.**  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the failed mutation and its kept snapshot left the application coherent and the baseline unchanged — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-05-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: the baseline box drawn whole inside the frame with no added, removed or deformed feature from the rolled-back mutation, the viewport fully painted with no blank or torn region, no modal dialog or error popup, no "Not Responding" in the title bar, and the after image showing the same box at the same size and position as the before image. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Expected result**: FAIL. `mutation.snapshot_path` resolves under `$TEMP` with a parent named  
`FCB_TMP_snap_<random>`; each kept snapshot raises the `$TEMP` count by one and lands in its own
fresh directory; `grep` finds no `snap/` in `transaction.py`. Only the visual closer passes.

**Cleanup**:
```bash
rm -rf "$TEMP"/FCB_TMP_snap_*
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-99-06: The audit log is written per session to a dated file under the workdir

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-25 audit location), `security-and-service-design.md` §1 (audit)

**What AD-25 specifies**: each session writes its audit records to a dated file inside that
session's workdir, so the audit trail is attributable to a session and its location does not
depend on how the host was launched.

**Shipped behavior today**: `default_audit_path` returns
`Path(os.environ.get("FREECAD_BUDDY_AUDIT_LOG", "freecad-buddy-audit.jsonl"))` at
`src/freecad_buddy/adapters/audit_log.py:24`. The fallback is a bare relative filename, so the
audit log lands in whatever the host process's current working directory happened to be at start.
Launched from the repository root it lands in the repository; launched by the GUI addon it lands
wherever FreeCAD's working directory points. There is no session scoping and no date in the
name, so two sessions started in the same directory append into the same file with nothing
distinguishing their records by session.

**Severity is higher than a misplaced log — verified 2026-09-12.** When the working directory is
not writable, the audit append raises and **every mutation tool fails**. A GUI FreeCAD launched
normally has `C:\Program Files\FreeCAD 1.1\bin` as its working directory, which is not writable,
so with `FREECAD_BUDDY_AUDIT_LOG` unset the entire mutation surface is unusable:

```
feature_body_create -> SPEC_FAILED  mutation.spec_failed
                       OSError: Failed to write all data to file Permission denied
addon.log           -> PermissionError: [Errno 13] Permission denied: 'freecad-buddy-audit.jsonl'
```

The envelope message names the write, not the audit log, so the failure presents as a snapshot or
`saveAs` problem. It is neither: `document_save` to an absolute path on the same drive succeeds
while the mutation fails, and no `FCB_TMP_snap_*` directory is ever created — the bracket never
reaches the snapshot. The workaround is `APPENDIX-B` Step 6a; the fix is for the bridge to default
the audit log to a writable, session-scoped location rather than to the process working directory.

**Given** `FREECAD_BUDDY_AUDIT_LOG` is unset, so the default path is exercised  
**And** a golden model is open as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. This scenario stops and restarts the host, so expect the menu path to be the usable one.  
**And** the framed baseline is captured, after that same fit, so both images share a camera — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-06-before.png"}' | & cua-driver call get_window_state`  

**When** the host is started from directory `A` and one mutation is run  
**And** it is stopped, the host is started from a different directory `B`, and one mutation is run  
**And** every `freecad-buddy-audit.jsonl` on the machine is located  
```bash
find / -name "freecad-buddy-audit.jsonl" 2>/dev/null
```
**And** both locations are compared to the session workdir from TC-99-04  

**Then** the audit log is under the session workdir — verify: the directory-`A` log path starts with the session workdir. **Expected failure: it is `A/freecad-buddy-audit.jsonl`.**  
**And** the filename carries a date — verify: the basename contains an ISO date. **Expected failure: the basename is the fixed `freecad-buddy-audit.jsonl`.**  
**And** the path does not depend on the working directory — verify: the directory-`A` and directory-`B` log paths are in the same parent. **Expected failure: they are `A/` and `B/` respectively.**  
**And** two sessions do not share one file — verify: the directory-`A` and directory-`B` records are in different files. **Expected failure: they share a file whenever `A` equals `B`.**  
**And** each record names its session — verify: every audit line carries a session identifier field. **Expected failure: `AuditSink._record` (`src/freecad_buddy/adapters/audit_log.py:49-66`) writes `schema`, `ts`, `actor`, `event`, `tool`, `params_digest` and optionally `doc` and `code` — no session field.**  
**And** the default is absolute — verify: the default path in source is absolute. **Expected failure: line 24 supplies a bare relative filename.**  
**And** *(visual)* the model is framed — verify: fit through the GUI with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. The host was stopped and restarted during the `When`, so `mcp view_fit_viewport` may have no live session to answer on; use it only if it returns `OK`.  
**And** *(visual)* the two host restarts left the application coherent and the baseline unchanged — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-06-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: the baseline box drawn whole inside the frame, the viewport fully painted with no blank or torn region, no permission-error dialog or error popup raised by the failing audit write, no "Not Responding" in the title bar, and the after image showing the same box at the same size and position as the before image. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Expected result**: FAIL. The audit log follows the process working directory —  
`A/freecad-buddy-audit.jsonl` then `B/freecad-buddy-audit.jsonl` — with a fixed undated basename,
no session field in any record, and a bare relative default at `audit_log.py:24`. On a GUI FreeCAD
whose working directory is not writable, the mutations themselves fail with
`SPEC_FAILED mutation.spec_failed`. Only the visual closer passes.

**Cleanup**:
```bash
rm -f ./freecad-buddy-audit.jsonl
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-99-07: Snapshots surviving into a new session are swept at bridge start

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-25 start-of-session sweep)

**What AD-25 specifies**: at bridge start, any snapshot left behind by a previous session is
swept, so a crash or a deliberate keep-case does not accumulate copies of the user's documents on
disk indefinitely.

**Shipped behavior today**: no start-of-session sweep exists. The only removal path is
`_delete_snapshot` (`src/freecad_buddy/usecases/transaction.py:98-117`), which is called inline
by `run_mutation` for the call that created the snapshot — on commit
(`src/freecad_buddy/usecases/transaction.py:569`), on proven rollback
(`src/freecad_buddy/usecases/transaction.py:603`), on setup failure
(`src/freecad_buddy/usecases/transaction.py:530`) and on commit failure
(`src/freecad_buddy/usecases/transaction.py:368`). Two paths deliberately KEEP the snapshot: the
unproven rollback (`src/freecad_buddy/usecases/transaction.py:584-601`) and the
committed-but-unhashable case (`src/freecad_buddy/usecases/transaction.py:375-391`). Those kept
directories, and anything left by a process that died mid-mutation, are never cleaned up by a
later start. They persist under the process temp directory until the operating system or the
operator removes them. Each one is a full copy of a user document.

**Given** FreeCAD is stopped  
**And** at least one orphan `FCB_TMP_snap_*` directory exists under `$TEMP`, containing an `.FCStd`  

**When** two orphan snapshot directories are created or left under the process temp directory  
**And** their paths and count are recorded  
**And** FreeCAD is started with the addon loaded, and the bridge is allowed to come up  
**And** a golden model is opened as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. The bridge has only just come up, so expect the menu path to be the usable one.  
**And** the framed baseline is captured, after that same fit, so both images share a camera — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-07-before.png"}' | & cua-driver call get_window_state`  
**And** the orphan directories are counted again  

**Then** the orphans are removed at start — verify: the post-start `FCB_TMP_snap_*` count is `0`. **Expected failure: the count is unchanged.**  
**And** the sweep is logged — verify: `grep -i "swept\|orphan" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line. **Expected failure: nothing is logged.**  
**And** the sweep only touches reserved prefixes — verify: a non-prefixed sibling directory is untouched. **Expected failure: no sweep runs, so this passes vacuously and proves nothing.**  
**And** a sweep routine exists in source — verify: `grep -rniE "sweep|reap|cleanup_orphan" src/freecad_buddy/hosts/ src/freecad_buddy/adapters/` returns a match. **Expected failure: it returns nothing.**  
**And** no user-document copy outlives a session — verify: no `.FCStd` remains under any `FCB_TMP_snap_*` after start. **Expected failure: the copies remain.**  
**And** *(visual)* the model is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** *(visual)* the restarted bridge came up coherent with the baseline shown — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-07-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: the baseline box drawn whole inside the frame, the viewport fully painted with no blank or torn region, no startup error dialog or addon-failure popup, no "Not Responding" in the title bar, and the after image showing the same box at the same size and position as the before image. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Expected result**: FAIL. The orphan `FCB_TMP_snap_*` count after start equals the count before,  
their `.FCStd` copies remain, `addon.log` holds no sweep line, and no sweep routine exists in
`hosts/` or `adapters/`. The reserved-prefix checkpoint passes vacuously and proves nothing. Only
the visual closer passes.

**Cleanup**:
```bash
rm -rf "$TEMP"/FCB_TMP_snap_*
```
```
mcp document_close { doc: "<handle>" }
```

---

### TC-99-08: The bridge exposes /healthz returning the session id

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §7 (AD-24 liveness), `integration-mcp-clients.md` §transport (AD-2 already-served check)

**What AD-24 specifies**: the bridge serves a `/healthz` route that returns the session id, and
AD-2's already-served check probes that route so the addon can tell its own live bridge from an
unrelated process holding port 8765.

**Shipped behavior today**: no `healthz` route exists. A repository-wide search for the string
across `src/` returns zero hits. The Starlette application is built with exactly one route:
`Starlette(routes=[Mount("/mcp", app=_handle)], lifespan=_lifespan)` at
`src/freecad_buddy/hosts/gui_external/entry.py:157`. There is no session id to return either —
see TC-99-04, where no session-scoped concept exists at all. The only liveness signal the addon
has is a raw TCP connect to `127.0.0.1:8765`, which cannot distinguish this bridge from any other
process that happens to hold the port, and which therefore cannot tell a healthy bridge from a
stale one.

**Given** the proxy is serving on `127.0.0.1:8765`  
**And** a golden model is open as an untouched baseline — verify: `mcp document_open { path: "<abs>/benchmarks/g0/golden-models/box-10-20-30.FCStd" }` returns `OK`; record the handle  
**And** the baseline is framed — verify: `mcp view_fit_viewport { doc: "<handle>" }` returns `OK`; if it does not, or if this scenario is testing the fit itself, fit through the GUI instead with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test  
**And** the framed baseline is captured, after that same fit, so both images share a camera — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-08-before.png"}' | & cua-driver call get_window_state`  

**When** the health route is probed  
```bash
curl -s -i http://127.0.0.1:8765/healthz
```
**And** the source is searched for any health route  
```bash
grep -rn "healthz" src/
```
**And** port 8765 is occupied with an unrelated process and the addon is started, observing whether it detects the impostor  

**Then** `/healthz` returns a success status — verify: the `curl` response status is `200`. **Expected failure: Starlette returns `404`; the only route is `/mcp`.**  
**And** the body carries a session id — verify: the response body contains a session identifier. **Expected failure: the body is a 404 page.**  
**And** the route exists in source — verify: the `grep -rn "healthz" src/` returns a match. **Expected failure: it returns nothing.**  
**And** the already-served check probes `/healthz` — verify: the addon bootstrap's port check issues an HTTP request to `/healthz`. **Expected failure: it performs a raw TCP connect only.**  
**And** an impostor on the port is detected — verify: the addon reports that `:8765` is held by a process that is not this bridge. **Expected failure: the raw connect succeeds, so the addon treats the impostor as its own bridge and does not spawn.**  
**And** *(visual)* the model is framed — verify: fit through the GUI with the **Fit All** toolbar button resolved by `element_token` from a fresh `get_window_state` snapshot (`invoke_menu(["View","Fit All"])` is refused on FreeCAD 1.1.1 with `menu_path_unavailable`; the toolbar click returns `route: "accessibility"` and reframes the view), which touches none of the code under test. The impostor holds `:8765`, so `mcp view_fit_viewport` may be unreachable; use it only if it returns `OK`.  
**And** *(visual)* the health probe and the impostor left the application coherent and the baseline unchanged — verify: `'{"pid":<pid>,"window_id":<wid>,"screenshot_out_file":"$RUN_DIR/evidence/tc-99-08-after.png"}' | & cua-driver call get_window_state`, then `Read` both PNGs and say what is on screen: the baseline box drawn whole inside the frame, the viewport fully painted with no blank or torn region, no port-conflict dialog or addon-failure popup raised by the impostor, no "Not Responding" in the title bar, and the after image showing the same box at the same size and position as the before image. The judgement is on the pixels alone — no MCP status or render may stand in for looking at the image.  

**Expected result**: FAIL. `/healthz` returns `404` with a 404 body and no session id; `grep -rn  
"healthz" src/` returns nothing; the addon's already-served check is a raw TCP connect that accepts
an impostor on `:8765` as its own bridge and does not spawn. Only the visual closer passes.

**Cleanup**:
```bash
# Release the impostor process from port 8765.
```
```
mcp document_close { doc: "<handle>" }
```

---

## Gap summary

| AD | Scenario | Shipped evidence (`file:line`) | What must change to make it pass |
|----|----------|--------------------------------|----------------------------------|
| AD-3 | TC-99-01 bearer token | `hosts/gui_external/entry.py:157` — bare `Mount("/mcp")`, no `middleware=` | Add authentication middleware to `build_app`; mint and check a per-session bearer token |
| AD-3 | TC-99-02 Origin allowlist | `hosts/gui_external/entry.py:145-157` — no CORS, no header check anywhere in `src/` | Add `Origin` validation against a localhost allowlist before the mount handles the request |
| AD-25 | TC-99-04 session workdir | No workdir in `src/`; writes scattered across `usecases/transaction.py:94`, `usecases/preview.py:318`, `usecases/fingerprint.py:73`, `usecases/screenshot.py:168`, `adapters/audit_log.py:24` | Create a session-scoped workdir at bridge start with `snap/ exports/ audit.log tmp/`, and route every write through it |
| AD-25 | TC-99-05 snapshots in `snap/` | `usecases/transaction.py:94` `tempfile.mkdtemp(prefix=_SNAPSHOT_PREFIX)`; prefix at `:39` | Replace the `mkdtemp` with a path under the session workdir's `snap/` |
| AD-25 | TC-99-06 per-session dated audit log | `adapters/audit_log.py:24` — CWD-relative `freecad-buddy-audit.jsonl` default; `:49-66` record carries no session field | Default the audit path to a dated file under the session workdir and add a session field to the record |
| AD-25 | TC-99-07 start-of-session sweep | No sweep in `src/`; `usecases/transaction.py:584-601` and `:375-391` deliberately keep snapshots with no later cleaner | Sweep reserved-prefix orphans at bridge start, logging what was removed |
| AD-24 | TC-99-08 `/healthz` | Zero `healthz` hits in `src/`; the only route is `hosts/gui_external/entry.py:157` | Add a `/healthz` route returning the session id, and make the AD-2 already-served check probe it instead of a raw TCP connect |
