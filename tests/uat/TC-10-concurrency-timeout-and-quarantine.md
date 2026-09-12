# TC-10: Concurrency, Timeout Budget & Document Quarantine

Validates what the bridge does when a call runs longer than its budget, when a second client
arrives, and when the transport dies mid-call. The rule under test is AD-27: a marshal timeout
returns `TIMEOUT`, the operation body may still be running, and the bridge NEVER re-issues the
mutation. AD-24's latency budget is measured here too. Two hosts exist and they do NOT behave
alike — every scenario names which one it targets.

**Host divergence (applies to the whole file).** The inline H1 host
(`adapters/mcp_server.py:174-220`) carries the document-suspect set, the non-string-`doc` guard,
and audit writes. The H2 GUI proxy (`hosts/gui_external/entry.py:136-140`) has its own
`_call_tool` that does none of those things — it only dispatches and wraps. A suspect-document
scenario run against `http://127.0.0.1:8765/mcp` will NOT reproduce. The in-FreeCAD listener
(`adapters/rpc_listener.py:304-343`) carries its own suspect set with DIFFERENT wording.

## Prerequisites

- [ ] micromamba `fcb` env is H1-capable (verify: `"$USERPROFILE/micromamba/envs/fcb/python.exe" -c "import FreeCAD, mcp"`)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/box-10-20-30.FCStd`)
- [ ] For the H2 scenarios only: FreeCAD GUI running with the addon loaded (verify: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/mcp` returns a non-`000` code)

---

### TC-10-01: One client's calls are strictly serialized

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §2.4 (single marshal), `component-design.md` §RPC listener

**Host**: H1 inline (stdio) and the in-FreeCAD listener.

**Preconditions**:
- [ ] No stale H1 server holding the golden files (verify: `ls _automation/*.lock 2>/dev/null` returns nothing)

**Steps**:
1. Open one document and issue six reads back to back on a single connection, recording entry and
   exit timestamps per call:
   ```bash
   uv run python scripts/automation/run_mcp_e2e.py
   ```
2. Read the per-call ordering out of the report:
   ```bash
   python3 -c "import json;r=json.load(open('_automation/e2e_report.json'));print([c['tool'] for c in r['checks']])"
   ```

**Checkpoints**:
- [ ] CP1: every call returned before the next one started — verify: the recorded `[start, end]` spans in `_automation/e2e_report.json` do not overlap
- [ ] CP2: results arrive in request order — verify: the `tool` sequence printed in step 2 matches the request sequence in `scripts/automation/run_mcp_e2e.py`
- [ ] CP3: exactly one marshal call per request — verify: `grep -c "marshal" _automation/server.stderr.log` shows no nested-call warnings
- [ ] CP4: the sweep gate is green — verify: `python3 -c "import json;print(json.load(open('_automation/e2e_report.json'))['all_passed'])"` returns `True`
- [ ] CP5: no interleaving traceback — verify: `grep -iE "reentrant|deadlock|already in marshal" _automation/server.stderr.log` returns nothing

**Cleanup**:
```bash
rm -f _automation/*.step _automation/*.stl _automation/scratch.FCStd
```

---

### TC-10-02: Read-only latency budget (AD-24)

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §7 (latency budget), `mcp-tools-design.md` §timeouts

**Host**: H1 inline.

The measurement point is tool-call entry to envelope return, not wall time of the whole sweep.
The budget is median <= 15 s over the read-only profile. The per-tool marshal timeouts are
larger (30 s for most `query_*`, 60 s for `query_screenshot` / `verify_shape` / `verify_sketch`,
120 s for `verify_recompute`) — the budget is a performance assertion, the timeout is a contract.

**Preconditions**:
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/*.FCStd | wc -l` is >= 5)

**Steps**:
1. Run the happy-path sweep, which records a duration per check:
   ```bash
   uv run python scripts/automation/run_mcp_e2e.py
   ```
2. Compute the median duration over the read-only tools:
   ```bash
   python3 -c "import json,statistics;r=json.load(open('_automation/e2e_report.json'));d=[c['duration_s'] for c in r['checks'] if c['tool'].startswith(('query_','verify_','document_list'))];print(len(d), statistics.median(d))"
   ```

**Checkpoints**:
- [ ] CP1: the median read-only call is at or under 15 s — verify: the second number printed in step 2 is `<= 15.0`
- [ ] CP2: at least 8 read-only calls were sampled — verify: the first number printed in step 2 is `>= 8`
- [ ] CP3: no read-only call returned `TIMEOUT` — verify: `grep -c '"status": "TIMEOUT"' _automation/e2e_report.json` returns `0`
- [ ] CP4: `query_screenshot` stayed inside its own 60 s marshal budget — verify: the `query_screenshot:*` entries in the report show `status=OK`
- [ ] CP5: no call exceeded its declared `timeout_s` — verify: each check's `duration_s` is below the tool's timeout in `src/freecad_buddy/hosts/tool_catalog.py`

**Cleanup**:
```bash
rm -f _automation/*.png
```

---

### TC-10-03: A second client while the first is connected (SHIPPED behavior)

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §2.4 (single-client listener), `security-and-service-design.md` §2 (session)

**Host**: the in-FreeCAD RPC listener.

**This scenario pins what the code does, not what AD-26 specifies.** `_accept_loop`
(`adapters/rpc_listener.py:217-234`) is a plain sequential loop: `sock.accept()` on line 222,
then `self._serve_conn(conn)` on line 227, then close, then loop. While the first connection is
served the loop is never back at `accept()`, so a second client does NOT receive an `-32000`
busy refusal — it sits in the listen backlog (`sock.listen(1)` at line 145) and is served after
the first disconnects. **The AD-26 busy refusal is not implemented; see TC-99-03.**

**Preconditions**:
- [ ] The FreeCAD GUI is running with the addon loaded
- [ ] The discovery file is readable (verify: `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-"*.json`)

**Steps**:
1. Read the host, port and token from the discovery file:
   ```bash
   python3 -c "import glob,json,os;p=glob.glob(os.path.expandvars(r'%APPDATA%/FreeCAD/v1-1/freecad-buddy/rpc-*.json'))[0];r=json.load(open(p));print(r['host'],r['port'],r['token'])"
   ```
2. Open client A, complete `rpc_hello`, then issue a long read and hold the connection open.
3. While A is still connected, open client B to the same port, send its `rpc_hello`, and record
   the time until a reply frame arrives.
4. Close client A. Observe when B's handshake reply lands.

**Checkpoints**:
- [ ] CP1: B's TCP connect succeeds immediately — verify: B's `socket.connect` returns without raising while A is connected
- [ ] CP2: B receives NO reply frame while A is connected — verify: a 5 s `recv` on B's socket times out with no bytes read
- [ ] CP3: B is NOT refused with `-32000` — verify: no frame carrying `"code": -32000` is ever read on B
- [ ] CP4: after A disconnects, B's `rpc_hello` is answered — verify: B reads one frame carrying `result.contract_version` equal to `"1"`
- [ ] CP5: B's served calls behave normally after that — verify: a `document_list` on B returns `status=OK`
- [ ] CP6: the listener logged no crash across the handover — verify: `grep -i "connection handler crashed" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns nothing
- [ ] CP7: the AD-26 gap is recorded — verify: `tests/uat/TC-99-ad-conformance-gaps.md` contains scenario `TC-99-03` asserting the unimplemented `-32000` refusal

**Cleanup**:
```bash
# Close both test sockets; no files are written.
```

---

### TC-10-04: A second client after the first disconnects must handshake afresh

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §2.4 (handshake), `security-and-service-design.md` §2 (session token)

**Host**: the in-FreeCAD RPC listener.

**Preconditions**:
- [ ] No client currently connected (verify: `netstat -ano | grep ":<port>" | grep ESTABLISHED` returns nothing)

**Steps**:
1. Connect client A, send `rpc_hello` with the discovery token, run `document_list`, disconnect.
2. Connect client B and send `document_list` as its FIRST frame, with no `rpc_hello`.
3. Connect client C, send a correct `rpc_hello`, then `document_list`.

**Checkpoints**:
- [ ] CP1: A's handshake is accepted — verify: A reads a result carrying `contract_version`, `freecad_version` and `capabilities`
- [ ] CP2: B is refused for skipping the handshake — verify: B reads an error frame with `message` exactly `handshake required`
- [ ] CP3: B's connection is closed by the listener — verify: B's next `recv` returns zero bytes
- [ ] CP4: C's fresh handshake succeeds — verify: C reads a result carrying `contract_version` equal to `"1"`
- [ ] CP5: C's `document_list` returns `OK` — verify: the envelope `status` field is `OK`
- [ ] CP6: refusing B did not stop the accept loop — verify: C connected AFTER B was refused and was served

**Cleanup**:
```bash
# No files written.
```

---

### TC-10-05: A long-running operation does not starve the listener

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §7 (budget), `mcp-tools-design.md` §5 (preview)

**Host**: H1 inline. `preview_dry_run` carries the largest budget in the surface: 180 s.

**Preconditions**:
- [ ] A document with a body that takes a measurable time to recompute is open

**Steps**:
1. Issue a `preview_dry_run` whose operation takes roughly 100 s to recompute, and hold the
   connection open for its whole duration.
2. While it runs, do not issue anything else on the same connection.
3. When it returns, issue a `document_list` on the same connection.

**Checkpoints**:
- [ ] CP1: the preview returns a terminal envelope, not a dropped connection — verify: one envelope frame is read with `status` in the closed set
- [ ] CP2: the call was not cut at a shorter budget — verify: the measured duration is above 60 s and the status is not `TIMEOUT`
- [ ] CP3: the connection survived — verify: the following `document_list` returns `status=OK` on the SAME socket
- [ ] CP4: no keepalive or idle-timeout close was logged — verify: `grep -iE "timed out|connection reset" _automation/server.stderr.log` returns nothing
- [ ] CP5: the preview TempDoc was cleaned up — verify: `mcp__freecad-buddy__document_list` shows no handle whose name starts with `FCB_TMP_prev_`

**Cleanup**:
```bash
rm -rf "$TEMP"/FCB_TMP_prev_*
```

---

### TC-10-06: Handles are not shared across sessions

**Priority**: High
**Design Ref**: `data-contracts-design.md` §3 (handles), `security-and-service-design.md` §2 (session scope)

**Host**: the in-FreeCAD RPC listener.

**Preconditions**:
- [ ] The GUI has at least one document open

**Steps**:
1. In session A, open a document and record the handle it returns.
2. Disconnect A. Reconnect as session B with a fresh `rpc_hello`.
3. In session B, call `query_object` using session A's handle verbatim.
4. In session B, call `document_list` and compare the handles it reports.

**Checkpoints**:
- [ ] CP1: session A's open returned a handle — verify: the `document_create`/`document_open` envelope carries a non-empty handle string
- [ ] CP2: session B rejects A's handle — verify: the `query_object` envelope `status` is `INVALID_INPUT`
- [ ] CP3: the rejection is a closed-set status, not a raised exception — verify: the envelope has `schema` equal to `fcb.result-envelope/1`
- [ ] CP4: session B's own `document_list` does not contain A's handle — verify: the returned handle list excludes the recorded string
- [ ] CP5: the listener survived the bad handle — verify: a following `document_list` on B returns `status=OK`

**Cleanup**:
```bash
# No files written.
```

---

### TC-10-07: A budget overrun returns TIMEOUT and the body may still run

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §7 (timeout), `data-contracts-design.md` §3 (status closed set)

**Host**: H1 inline. There is NO preemption: `Marshal.call` raises `MarshalTimeout` at the caller
and the queued body keeps running on the Qt main thread.

**Preconditions**:
- [ ] A document whose recompute exceeds the tool's `timeout_s` is available

**Steps**:
1. Issue a mutating call whose body is known to exceed its 120 s budget.
2. Read the returned envelope in full.
3. Record whether the FreeCAD process stays busy after the envelope was returned.

**Checkpoints**:
- [ ] CP1: the envelope status is `TIMEOUT` — verify: the returned `status` field is exactly `TIMEOUT`
- [ ] CP2: the timeout is flagged as a marshal timeout — verify: `detail.data.marshal_timeout` is `true`
- [ ] CP3: the envelope says the body may still be running — verify: `detail.data.maybe_still_running` is `true`
- [ ] CP4: the message names the consequence — verify: `detail.message` contains `the document is now suspect: do not blind-retry, run a query_* read first to confirm `
- [ ] CP5: the call was NOT preempted — verify: the FreeCAD process still shows CPU activity after the envelope arrived
- [ ] CP6: the connection is still usable — verify: a following read-only call on the same connection returns a terminal envelope
- [ ] CP7: the timeout was audit-logged — verify: `grep '"verify_verdict": "TIMEOUT"' freecad-buddy-audit.jsonl` returns at least one line

**Cleanup**:
```bash
# Wait for the running body to finish before the next scenario; do not kill FreeCAD.
```

---

### TC-10-08: A timeout quarantines the document

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §7 (quarantine), `data-contracts-design.md` §3 (INVALID_INPUT)

**Host**: H1 inline ONLY (`adapters/mcp_server.py:199-207`). The in-FreeCAD listener enforces the
same rule with different wording (`adapters/rpc_listener.py:319-323`): `document-suspect: a prior
call timed out on this document; run a query_* read to confirm state before mutating`. The H2
proxy does NOT enforce it at all.

**Preconditions**:
- [ ] TC-10-07 has just run and left document `D` marked suspect

**Steps**:
1. Issue a second MUTATING call on the same document handle `D`.
2. Read the returned envelope.
3. Issue a mutating call on a DIFFERENT document handle `E`.

**Checkpoints**:
- [ ] CP1: the second mutation on `D` is refused — verify: the returned `status` is `INVALID_INPUT`
- [ ] CP2: the refusal names the quarantine — verify: `detail.message` starts with `document-suspect: a prior call timed out on this document and its body may `
- [ ] CP3: the message tells the operator what to do — verify: `detail.message` contains `run a query_* read to confirm the document still responds `
- [ ] CP4: the refusal happened WITHOUT dispatching — verify: no new `before`/`after` pair for the operation body appears in the FreeCAD log between the request and the reply
- [ ] CP5: the refusal is still audit-logged — verify: `grep '"verify_verdict": "INVALID_INPUT"' freecad-buddy-audit.jsonl` returns a line whose `tool` is the refused tool
- [ ] CP6: quarantine is per document — verify: the mutating call on handle `E` is NOT refused with `document-suspect`
- [ ] CP7: the H2 proxy does not carry this rule — verify: `grep -c "document-suspect" src/freecad_buddy/hosts/gui_external/entry.py` returns `0`

**Cleanup**:
```bash
# Leave D quarantined; TC-10-09 clears it.
```

---

### TC-10-09: Quarantine clears only via a non-mutating OK

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §7 (quarantine clearing), `mcp-tools-design.md` §read-only profile

**Host**: H1 inline (`adapters/mcp_server.py:216-217`: clear only when the method is known, not
mutating, and the envelope status is `OK`).

**Preconditions**:
- [ ] Document `D` is still quarantined from TC-10-08

**Steps**:
1. Issue a read-only call on `D` that FAILS, for example `query_object` naming an object that
   does not exist.
2. Issue a mutating call on `D` again.
3. Issue a read-only call on `D` that SUCCEEDS, for example `query_tree_summary`.
4. Issue the mutating call on `D` once more.

**Checkpoints**:
- [ ] CP1: the failing read returns `INVALID_INPUT` — verify: the step 1 envelope `status` is `INVALID_INPUT`
- [ ] CP2: a failing read does NOT clear the quarantine — verify: the step 2 mutation is still refused with `document-suspect: a prior call timed out on this document and its body may `
- [ ] CP3: the passing read returns `OK` — verify: the step 3 envelope `status` is `OK`
- [ ] CP4: the passing read clears the quarantine — verify: the step 4 mutation is no longer refused with `document-suspect`
- [ ] CP5: a mutation can never clear it — verify: the step 2 refusal did not remove `D` from the suspect set, proven by CP2 still holding before step 3
- [ ] CP6: the clearing read was a member of the read-only profile — verify: `grep -A16 "READ_ONLY_PROFILE = frozenset" src/freecad_buddy/hosts/tool_catalog.py` lists `query_tree_summary`

**Cleanup**:
```bash
# D is now clear.
```

---

### TC-10-10: NO automatic mutation retry

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §7 (AD-27 no blind retry), `verification-design.md` §fingerprint

**Host**: H1 inline. The contract is that the BRIDGE never re-issues a timed-out mutation. The
client is told to read and compare fingerprints itself.

**Preconditions**:
- [ ] A mutating call that reliably overruns its budget is available

**Steps**:
1. Record the document fingerprint before the mutation:
   ```bash
   # via query_object / verify_recompute, capture the fingerprint digest
   ```
2. Issue the overrunning mutation and read the `TIMEOUT` envelope.
3. Wait until the FreeCAD process is idle again.
4. Run a `query_*` read and capture the fingerprint digest again.

**Checkpoints**:
- [ ] CP1: the envelope tells the client not to blind-retry — verify: `detail.message` contains `the document is now suspect: do not blind-retry, run a query_* read first to confirm `
- [ ] CP2: exactly ONE dispatch of the mutation occurred — verify: `grep -c '"tool": "<the tool>"' freecad-buddy-audit.jsonl` shows one `before` and one `after` line for the call
- [ ] CP3: the bridge issued no second attempt — verify: no second `before` line for the same `params_digest` appears in `freecad-buddy-audit.jsonl`
- [ ] CP4: the client can decide from the fingerprints — verify: the step 4 digest differs from the step 1 digest if and only if the body landed
- [ ] CP5: a manual retry is the operator's call — verify: re-issuing the mutation after the clearing read returns a normal terminal envelope, proving retry is a client action
- [ ] CP6: no retry loop exists in source — verify: `grep -rniE "retry|re-?issue" src/freecad_buddy/adapters/mcp_server.py src/freecad_buddy/adapters/rpc_listener.py` returns nothing that re-dispatches a call

**Cleanup**:
```bash
# No files written.
```

---

### TC-10-11: A call that attempted no mutation does not mark the document suspect

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §7 (suspect scope), `mcp-tools-design.md` §read-only profile

**Host**: H1 inline (`adapters/mcp_server.py:126-148`, the `marked_suspect=False` wording branch).

**Preconditions**:
- [ ] A read-only call that overruns its budget is available, for example `verify_recompute` on a
      very heavy document

**Steps**:
1. Issue the overrunning READ-ONLY call and read the envelope.
2. Immediately issue a MUTATING call on the same document handle.

**Checkpoints**:
- [ ] CP1: the read-only call returns `TIMEOUT` — verify: the step 1 envelope `status` is `TIMEOUT`
- [ ] CP2: the message states no mutation was attempted — verify: `detail.message` contains `no mutation was attempted, so the document is not marked suspect`
- [ ] CP3: the message still warns the body may run — verify: `detail.message` contains `the body may still be running and `
- [ ] CP4: the following mutation is NOT refused — verify: the step 2 envelope `status` is not `INVALID_INPUT` carrying `document-suspect`
- [ ] CP5: the two wordings are mutually exclusive — verify: the step 1 message does NOT contain `the document is now suspect`
- [ ] CP6: `marshal_timeout` is still set on the read-only timeout — verify: `detail.data.marshal_timeout` is `true`

**Cleanup**:
```bash
# No files written.
```

---

### TC-10-12: FreeCAD killed mid-call surfaces WORKER_CRASHED

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §3 (status closed set), `integration-mcp-freecad.md` §2.4 (transport failure)

**Host**: the H2 GUI proxy plus the in-FreeCAD listener. The proxy's `RpcClient.call` never
raises: a dead peer must become an envelope.

**Preconditions**:
- [ ] FreeCAD GUI is running with the addon loaded, and the operator accepts that this scenario
      terminates that process
- [ ] No unsaved user work is open (verify: every open document reports no unsaved changes)

**Steps**:
1. Issue a long-running call through the proxy at `http://127.0.0.1:8765/mcp`.
2. While the call is in flight, end the FreeCAD process through the operating system.
3. Read what the in-flight call returns, with a hard client-side deadline of 180 s.

**Checkpoints**:
- [ ] CP1: the in-flight call returns rather than hanging — verify: a response arrives inside the 180 s deadline
- [ ] CP2: the status is `WORKER_CRASHED` — verify: the returned envelope `status` is exactly `WORKER_CRASHED`
- [ ] CP3: the client is not left blocked on a socket — verify: the client process exits cleanly after reading the envelope
- [ ] CP4: the proxy did not itself crash — verify: a following `tools/list` against `:8765` either answers or returns a connection error, never a partial/corrupt body
- [ ] CP5: the crash is visible in the proxy log — verify: `grep -i "crash\|connection" "$APPDATA/FreeCAD/v1-1/freecad-buddy/mcp-proxy.log"` shows the failure
- [ ] CP6: the discovery file for the dead pid is stale, not corrupt — verify: the remaining `rpc-<pid>.json` still parses as JSON
- [ ] CP7: restarting FreeCAD restores service — verify: after restart, `tools/list` against `:8765` returns 44 tools

**Cleanup**:
```bash
rm -f "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-"*.json
```

---

### TC-10-13: A socket dropped mid-frame yields WORKER_CRASHED and the listener survives

**Priority**: Critical
**Design Ref**: `integration-mcp-freecad.md` §2.4 (framing), `data-contracts-design.md` §3

**Host**: the in-FreeCAD RPC listener. `_FrameReader.read_line`
(`adapters/rpc_listener.py:64-83`) raises `ValueError("connection closed mid-frame")` when the
peer closes with a partial buffer; `_serve_conn` catches it and closes only that connection
(lines 242-247).

**Preconditions**:
- [ ] The listener is accepting (verify: the discovery file exists and the port accepts a connect)

**Steps**:
1. Connect, complete `rpc_hello`, then write a request with NO trailing newline and close the
   socket immediately.
2. Read the listener log.
3. Connect a fresh client, complete `rpc_hello`, and issue `document_list`.

**Checkpoints**:
- [ ] CP1: the truncated frame closed only that connection — verify: `grep "frame read failed; closing connection" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line
- [ ] CP2: the accept loop kept running — verify: the step 3 connect succeeds
- [ ] CP3: the fresh client's handshake is answered — verify: it reads a result carrying `contract_version` equal to `"1"`
- [ ] CP4: the fresh client's call returns `OK` — verify: the `document_list` envelope `status` is `OK`
- [ ] CP5: the drop was not reported as a document fault — verify: no `document-suspect` string appears in the log for this scenario
- [ ] CP6: through the H2 proxy the same drop surfaces as an envelope — verify: the proxy's corresponding call returns `status=WORKER_CRASHED`, never a raised exception
- [ ] CP7: FreeCAD is still responsive — verify: the GUI window still answers a menu query via `cua-driver`

**Cleanup**:
```bash
# No files written.
```

---

### TC-10-14: An over-cap or non-UTF-8 frame closes only that connection

**Priority**: High
**Design Ref**: `integration-mcp-freecad.md` §2.4 (16 MiB frame cap), `data-contracts-design.md` §3

**Host**: the in-FreeCAD RPC listener. The cap is `_MAX_FRAME_BYTES = 16 * 1024 * 1024`
(`adapters/rpc_listener.py:36`), enforced in `read_line` at line 76.

**Preconditions**:
- [ ] The listener is accepting

**Steps**:
1. Connect, complete `rpc_hello`, then stream more than 16 MiB with no newline:
   ```bash
   python3 -c "import socket,sys;s=socket.create_connection((HOST,PORT));s.sendall(HELLO);s.recv(65536);s.sendall(b'{\"x\":\"'+b'A'*(17*1024*1024))"
   ```
2. Connect a second client and send a frame containing raw bytes that are not valid UTF-8,
   terminated by a newline.
3. Connect a third client normally and issue `document_list`.

**Checkpoints**:
- [ ] CP1: the over-cap connection is closed — verify: the first client's next `recv` returns zero bytes
- [ ] CP2: the cap breach is logged — verify: `grep "frame exceeds 16 MiB cap" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns a line
- [ ] CP3: the non-UTF-8 connection is also closed — verify: the second client's next `recv` returns zero bytes
- [ ] CP4: the accept loop survived both — verify: the third client's connect and handshake succeed
- [ ] CP5: the third client's call returns `OK` — verify: the `document_list` envelope `status` is `OK`
- [ ] CP6: FreeCAD's memory did not grow unboundedly — verify: the FreeCAD process working set after step 1 is within 100 MB of its value before step 1
- [ ] CP7: no document was marked suspect by a framing fault — verify: a mutating call on any open document is not refused with `document-suspect`

**Cleanup**:
```bash
# No files written.
```
