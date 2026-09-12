# TC-99: Architecture-Decision Conformance Gaps (EXPECTED-FAIL)

**This file is the CONFORMANCE GATE, not the release gate. It is NOT part of the green suite.**

Every scenario below asserts a behavior an architecture decision specifies and the shipped code
does NOT implement. **Every scenario here is expected to FAIL against the current build.** A run
that reports all eight failing is the correct, expected result.

**A scenario that starts PASSING means the code gained the behavior.** That is a win, not a
regression: promote the scenario into the green gate (TC-10 or TC-11 as the table at the end
directs) and delete it from this file.

Each scenario names four things: the AD, what the AD specifies, what the code actually does
today, and the `file:line` evidence. Every citation below was read in the source before it was
written here. Each scenario carries a `**Shipped behavior today**:` section — a deliberate
addition to the house template, following the precedent of TC-06's `**Divergence handling**:`
section.

## Prerequisites

- [ ] The repository is at the revision under test (verify: `git rev-parse HEAD`)
- [ ] FreeCAD GUI is running with the addon loaded (verify: `netstat -ano | grep ":8765" | grep LISTENING`)
- [ ] `curl` is available (verify: `curl --version`)

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

**Preconditions**:
- [ ] The proxy is serving on `127.0.0.1:8765`

**Steps**:
1. Send an unauthenticated request and record the HTTP status:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8765/mcp \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   ```
2. Complete a full unauthenticated MCP session: `initialize`, then the
   `notifications/initialized` notification, then `tools/list`, carrying the
   `Mcp-Session-Id` returned by `initialize` and **no credential of any kind**. Use an MCP
   client against `http://127.0.0.1:8765/mcp` rather than raw `curl` for this step.
3. Repeat step 2 with a deliberately WRONG `Authorization: Bearer <garbage>` header.
4. From that same unauthenticated session, call a mutating tool.

**Checkpoints** (all EXPECTED TO FAIL today):
- [ ] CP1: the unauthenticated request is refused with an auth challenge — verify: the step 1 status is `401` or `403`. **Expected failure: it is `307`, and following the redirect yields `400` with `-32600 Bad Request: Missing session ID` — an MCP protocol requirement, NOT authentication. Record the exact status and code; a `400/-32600` is the documented deviation, and any auth-shaped refusal is a real change.**
- [ ] CP2: no tool list is disclosed without credentials — verify: the step 2 `tools/list` result contains no tool names. **Expected failure: the full 44-tool list is returned to a caller that presented no credential.**
- [ ] CP3: a wrong bearer token is refused — verify: the step 3 session is rejected with `401`. **Expected failure: the `Authorization` header is ignored entirely and the session succeeds.**
- [ ] CP4: an unauthenticated mutation is refused — verify: the step 4 call is rejected with `401` and the document fingerprint is unchanged. **Expected failure: the mutation runs and the fingerprint changes.**
- [ ] CP5: an authentication middleware exists — verify: `grep -n "middleware\|AuthenticationMiddleware\|Bearer" src/freecad_buddy/hosts/gui_external/entry.py` returns a match. **Expected failure: it returns nothing.**
- [ ] CP6: the refusal is logged — verify: `grep -i "unauthorized\|401" "$APPDATA/FreeCAD/v1-1/freecad-buddy/mcp-proxy.log"` returns a line. **Expected failure: nothing is logged.**

**Cleanup**:
```bash
# Close any document the step 3 mutation created.
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

**Preconditions**:
- [ ] The proxy is serving on `127.0.0.1:8765`

**Steps**:
1. Send a request carrying a foreign `Origin`:
   ```bash
   curl -s -i -X POST http://127.0.0.1:8765/mcp \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -H "Origin: https://attacker.example" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   ```
2. Repeat with `Origin: http://localhost:3000`.
3. Send a CORS preflight `OPTIONS` request with the foreign origin.

**Checkpoints** (all EXPECTED TO FAIL today):
- [ ] CP1: the foreign origin is refused — verify: the step 1 response status is `403`. **Expected failure: the request is served.**
- [ ] CP2: no tool list is disclosed to the foreign origin — verify: the step 1 body contains no tool names. **Expected failure: the full list is returned.**
- [ ] CP3: a localhost origin is allowed — verify: the step 2 response status is a success code. **Expected failure: this passes for the wrong reason — everything is allowed.**
- [ ] CP4: the preflight refuses the foreign origin — verify: the step 3 response carries no `Access-Control-Allow-Origin` naming `attacker.example`. **Expected failure: no CORS handling exists, so no header is emitted and the check cannot distinguish refusal from absence.**
- [ ] CP5: an allowlist exists in source — verify: `grep -rn "Origin" src/freecad_buddy/hosts/ src/freecad_buddy/adapters/` returns an HTTP header check. **Expected failure: it returns nothing.**

**Cleanup**:
```bash
# No files written.
```

---

### TC-99-03: A second client is refused -32000 with a busy detail

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §2.4 (AD-26 single-client listener)

**What AD-26 specifies**: the listener serves one client at a time. A second client that
presents a valid session token while the first is connected is refused with JSON-RPC error
`-32000` and a detail saying the bridge is busy, so the second client fails fast instead of
waiting.

**Shipped behavior today**: `_accept_loop` at `src/freecad_buddy/adapters/rpc_listener.py:217`
is a plain sequential loop. Line 222 is `conn, _addr = sock.accept()`, line 227 is
`self._serve_conn(conn)`, and the loop only returns to `accept()` after that connection has
closed. While the first client is served the loop is never at `accept()`, so the second client's
connection sits in the listen backlog (`sock.listen(1)` at
`src/freecad_buddy/adapters/rpc_listener.py:145`) and is eventually served in full. There is no
busy path: `-32000` (`RPC_ERROR_WORKER_CRASHED`) is only ever emitted for `auth failed` at
`src/freecad_buddy/adapters/rpc_listener.py:283`. The shipped serialization behavior is pinned in
TC-10-03.

**Observed on 2026-09-12 (FreeCAD 1.1.1, GUI host, proxy connected):** the shipped behavior is
**worse than "B waits"**. Because the accept loop is inside `_serve_conn` for the whole life of the
first connection, the `sock.listen(1)` backlog fills, and Windows then **refuses the TCP connect
outright** with `WinError 10061 (ConnectionRefusedError)`. This was verified twice, and a
single-client baseline connect to the same port was refused identically while the addon's own MCP
proxy held the listener. So a second client does not block and does not get `-32000` — it cannot
connect at all, and the error it sees is indistinguishable from "the bridge is not running".

**Preconditions**:
- [ ] The GUI addon is running and its MCP proxy holds the RPC listener (verify:
      `netstat -ano | findstr <listener-port>` shows one `ESTABLISHED` pair owned by the proxy pid)
- [ ] The listener port and token are read from the discovery file
      `%APPDATA%\FreeCAD\v1-1\freecad-buddy\rpc-<pid>.json`

**Steps**:
1. Read `host`, `port` and `token` from the discovery file.
2. While the proxy holds the listener, open a TCP connection to that port with a 5 s timeout and,
   if it connects, send a valid `rpc_hello`.
3. Record whether the connect succeeded, and if so read the first reply frame with a 10 s deadline.

**Checkpoints** (all EXPECTED TO FAIL today):
- [ ] CP1: the second client can connect at all — verify: `socket.create_connection((host, port), timeout=5)` succeeds. **Expected failure: `ConnectionRefusedError [WinError 10061]`. The backlog is full, so the connect is refused before any protocol frame is exchanged.**
- [ ] CP2: the reply is a JSON-RPC error — verify: the first frame carries an `error` object. **Expected failure: no frame is ever exchanged; there is no connection to carry one.**
- [ ] CP3: the error code is `-32000` — verify: `error.code` is `-32000`. **Expected failure: no error frame is sent.**
- [ ] CP4: the detail says the bridge is busy — verify: `error.message` names the busy condition. **Expected failure: no such message exists in source.**
- [ ] CP5: the refusal is distinguishable from a dead bridge — verify: the second client can tell "busy" from "not running". **Expected failure: both present as `ConnectionRefusedError` on the same port. This is the practical harm of the gap — a client cannot diagnose why it failed.**
- [ ] CP6: a busy path exists in source — verify: `grep -n "busy" src/freecad_buddy/adapters/rpc_listener.py` returns a match. **Expected failure: it returns nothing.**
- [ ] CP7: the listen backlog admits a waiting client — verify: `grep -n "listen(" src/freecad_buddy/adapters/rpc_listener.py` shows a backlog greater than 1. **Expected failure: `sock.listen(1)` at line 145.**

**Cleanup**:
```bash
# Close both test sockets.
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

**Preconditions**:
- [ ] FreeCAD has just been started with the addon loaded
- [ ] The session id is recorded

**Steps**:
1. Search for a session workdir under the FreeCAD appdata directory:
   ```bash
   ls -R "$APPDATA/FreeCAD/v1-1/freecad-buddy/"
   ```
2. Run one mutation, one preview, one screenshot and one export.
3. Enumerate every file the bridge created during step 2 and record its directory.

**Checkpoints** (all EXPECTED TO FAIL today):
- [ ] CP1: a session workdir exists — verify: a session-named directory is present in the step 1 listing. **Expected failure: only `addon.log`, `mcp-proxy.log` and `rpc-<pid>.json` are there.**
- [ ] CP2: it contains `snap/` — verify: the subdirectory exists. **Expected failure: absent.**
- [ ] CP3: it contains `exports/` — verify: the subdirectory exists. **Expected failure: absent.**
- [ ] CP4: it contains `tmp/` — verify: the subdirectory exists. **Expected failure: absent.**
- [ ] CP5: it contains `audit.log` — verify: the file exists. **Expected failure: absent; the audit log is CWD-relative, see TC-99-06.**
- [ ] CP6: the snapshot landed inside `snap/` — verify: the step 2 snapshot path is under the workdir. **Expected failure: it is under the process temp directory.**
- [ ] CP7: the preview copy landed inside `tmp/` — verify: the preview path is under the workdir. **Expected failure: it is under the process temp directory.**
- [ ] CP8: a workdir constant exists in source — verify: `grep -rniE "session_dir|workdir|session_root" src/freecad_buddy/` returns a match. **Expected failure: it returns nothing.**

**Cleanup**:
```bash
rm -rf "$TEMP"/FCB_TMP_*
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

**Preconditions**:
- [ ] The process temp directory is known and its `FCB_TMP_snap_*` count is recorded

**Steps**:
1. Run a mutation that fails post-verify with an unproven rollback, so the snapshot is kept.
2. Read the reported snapshot path from the envelope:
   ```bash
   python3 -c "import json,sys;print(json.load(sys.stdin)['structured_content']['mutation']['snapshot_path'])"
   ```
3. Compare that path's parent chain to the session workdir from TC-99-04.

**Checkpoints** (all EXPECTED TO FAIL today):
- [ ] CP1: the snapshot path is under a session workdir — verify: the step 2 path starts with the session workdir. **Expected failure: it starts with the process temp directory.**
- [ ] CP2: its immediate parent is named `snap` — verify: the path's parent directory basename is `snap`. **Expected failure: it is `FCB_TMP_snap_<random>`.**
- [ ] CP3: all of a session's snapshots are in one directory — verify: two failed mutations put their snapshots in the same parent. **Expected failure: each gets its own fresh `mkdtemp` directory.**
- [ ] CP4: no snapshot is written to the process temp directory — verify: the `FCB_TMP_snap_*` count under `$TEMP` is unchanged. **Expected failure: the count increases by one per kept snapshot.**
- [ ] CP5: the source names a session snap directory — verify: `grep -n "snap/" src/freecad_buddy/usecases/transaction.py` returns a match. **Expected failure: it returns nothing; line 94 is `tempfile.mkdtemp`.**

**Cleanup**:
```bash
rm -rf "$TEMP"/FCB_TMP_snap_*
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

**Preconditions**:
- [ ] `FREECAD_BUDDY_AUDIT_LOG` is unset, so the default path is exercised

**Steps**:
1. Start the host from directory `A` and run one mutation.
2. Stop it. Start the host from a different directory `B` and run one mutation.
3. Locate every `freecad-buddy-audit.jsonl` on the machine:
   ```bash
   find / -name "freecad-buddy-audit.jsonl" 2>/dev/null
   ```
4. Compare both locations to the session workdir from TC-99-04.

**Checkpoints** (all EXPECTED TO FAIL today):
- [ ] CP1: the audit log is under the session workdir — verify: the step 1 log path starts with the session workdir. **Expected failure: it is `A/freecad-buddy-audit.jsonl`.**
- [ ] CP2: the filename carries a date — verify: the basename contains an ISO date. **Expected failure: the basename is the fixed `freecad-buddy-audit.jsonl`.**
- [ ] CP3: the path does not depend on the working directory — verify: the step 1 and step 2 log paths are in the same parent. **Expected failure: they are `A/` and `B/` respectively.**
- [ ] CP4: two sessions do not share one file — verify: the step 1 and step 2 records are in different files. **Expected failure: they share a file whenever `A` equals `B`.**
- [ ] CP5: each record names its session — verify: every audit line carries a session identifier field. **Expected failure: `AuditSink._record` (`src/freecad_buddy/adapters/audit_log.py:49-66`) writes `schema`, `ts`, `actor`, `event`, `tool`, `params_digest` and optionally `doc` and `code` — no session field.**
- [ ] CP6: the default is absolute — verify: the default path in source is absolute. **Expected failure: line 24 supplies a bare relative filename.**

**Cleanup**:
```bash
rm -f ./freecad-buddy-audit.jsonl
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

**Preconditions**:
- [ ] FreeCAD is stopped
- [ ] At least one orphan `FCB_TMP_snap_*` directory exists under `$TEMP`, containing an `.FCStd`

**Steps**:
1. Create or leave two orphan snapshot directories under the process temp directory.
2. Record their paths and the count.
3. Start FreeCAD with the addon loaded, and let the bridge come up.
4. Count the orphan directories again.

**Checkpoints** (all EXPECTED TO FAIL today):
- [ ] CP1: the orphans are removed at start — verify: the step 4 `FCB_TMP_snap_*` count is `0`. **Expected failure: the count is unchanged.**
- [ ] CP2: the sweep is logged — verify: `grep -i "swept\|orphan" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line. **Expected failure: nothing is logged.**
- [ ] CP3: the sweep only touches reserved prefixes — verify: a non-prefixed sibling directory is untouched. **Expected failure: no sweep runs, so this passes vacuously and proves nothing.**
- [ ] CP4: a sweep routine exists in source — verify: `grep -rniE "sweep|reap|cleanup_orphan" src/freecad_buddy/hosts/ src/freecad_buddy/adapters/` returns a match. **Expected failure: it returns nothing.**
- [ ] CP5: no user-document copy outlives a session — verify: no `.FCStd` remains under any `FCB_TMP_snap_*` after start. **Expected failure: the copies remain.**

**Cleanup**:
```bash
rm -rf "$TEMP"/FCB_TMP_snap_*
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

**Preconditions**:
- [ ] The proxy is serving on `127.0.0.1:8765`

**Steps**:
1. Probe the health route:
   ```bash
   curl -s -i http://127.0.0.1:8765/healthz
   ```
2. Search the source for any health route:
   ```bash
   grep -rn "healthz" src/
   ```
3. Occupy port 8765 with an unrelated process and start the addon, observing whether it detects
   the impostor.

**Checkpoints** (all EXPECTED TO FAIL today):
- [ ] CP1: `/healthz` returns a success status — verify: the step 1 response status is `200`. **Expected failure: Starlette returns `404`; the only route is `/mcp`.**
- [ ] CP2: the body carries a session id — verify: the response body contains a session identifier. **Expected failure: the body is a 404 page.**
- [ ] CP3: the route exists in source — verify: the step 2 grep returns a match. **Expected failure: it returns nothing.**
- [ ] CP4: the already-served check probes `/healthz` — verify: the addon bootstrap's port check issues an HTTP request to `/healthz`. **Expected failure: it performs a raw TCP connect only.**
- [ ] CP5: an impostor on the port is detected — verify: the addon reports that `:8765` is held by a process that is not this bridge. **Expected failure: the raw connect succeeds, so the addon treats the impostor as its own bridge and does not spawn.**

**Cleanup**:
```bash
# Release the impostor process from port 8765.
```

---

## Gap summary

| AD | Scenario | Shipped evidence (`file:line`) | What must change to make it pass |
|----|----------|--------------------------------|----------------------------------|
| AD-3 | TC-99-01 bearer token | `hosts/gui_external/entry.py:157` — bare `Mount("/mcp")`, no `middleware=` | Add authentication middleware to `build_app`; mint and check a per-session bearer token |
| AD-3 | TC-99-02 Origin allowlist | `hosts/gui_external/entry.py:145-157` — no CORS, no header check anywhere in `src/` | Add `Origin` validation against a localhost allowlist before the mount handles the request |
| AD-26 | TC-99-03 second-client refusal | `adapters/rpc_listener.py:217-234` sequential loop; `:145` `sock.listen(1)`; `-32000` used only at `:283` for `auth failed` | Track the in-flight connection and answer a second `rpc_hello` with `-32000` plus a busy detail |
| AD-25 | TC-99-04 session workdir | No workdir in `src/`; writes scattered across `usecases/transaction.py:94`, `usecases/preview.py:318`, `usecases/fingerprint.py:73`, `usecases/screenshot.py:168`, `adapters/audit_log.py:24` | Create a session-scoped workdir at bridge start with `snap/ exports/ audit.log tmp/`, and route every write through it |
| AD-25 | TC-99-05 snapshots in `snap/` | `usecases/transaction.py:94` `tempfile.mkdtemp(prefix=_SNAPSHOT_PREFIX)`; prefix at `:39` | Replace the `mkdtemp` with a path under the session workdir's `snap/` |
| AD-25 | TC-99-06 per-session dated audit log | `adapters/audit_log.py:24` — CWD-relative `freecad-buddy-audit.jsonl` default; `:49-66` record carries no session field | Default the audit path to a dated file under the session workdir and add a session field to the record |
| AD-25 | TC-99-07 start-of-session sweep | No sweep in `src/`; `usecases/transaction.py:584-601` and `:375-391` deliberately keep snapshots with no later cleaner | Sweep reserved-prefix orphans at bridge start, logging what was removed |
| AD-24 | TC-99-08 `/healthz` | Zero `healthz` hits in `src/`; the only route is `hosts/gui_external/entry.py:157` | Add a `/healthz` route returning the session id, and make the AD-2 already-served check probe it instead of a raw TCP connect |
