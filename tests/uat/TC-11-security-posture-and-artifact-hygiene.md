# TC-11: Security Posture & Artifact Hygiene

Validates the shipped security controls and the temporary-artifact lifecycle. AD-4 says typed
tools are the only mutation path and `debug_exec` is off unless an operator turns it on. AD-20
says a reserved-prefix temporary document must never outlive the call that made it. This file
also asserts that the bridge writes nothing into the user's document folder on its own, and that
the audit log is append-only.

**Not covered here.** Bearer-token authentication and `Origin` validation on the HTTP endpoint
are AD-3 requirements the code does not implement. They are asserted as expected failures in
`TC-99-ad-conformance-gaps.md` (TC-99-01 and TC-99-02). The only transport control that ships is
the loopback bind, tested in TC-11-05 and TC-11-06.

## Prerequisites

- [ ] micromamba `fcb` env is H1-capable (verify: `"$USERPROFILE/micromamba/envs/fcb/python.exe" -c "import FreeCAD, mcp"`)
- [ ] `FREECAD_BUDDY_ALLOW_EXEC` is unset in the shell used for the default-posture scenarios (verify: `env | grep FREECAD_BUDDY_ALLOW_EXEC` returns nothing)
- [ ] The host machine has a non-loopback IPv4 address for the bind scenarios (verify: `ipconfig | grep IPv4`)

---

### TC-11-01: debug_exec is unregistered by default

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (exec gating), `mcp-tools-design.md` §5 (tool surface)

**Host**: H1 inline and the H2 proxy. `registered_tools` skips `debug_exec` when
`exec_registered(caps)` is false (`adapters/mcp_server.py:70-75`); the proxy's
`build_proxy_registry` appends `DEBUG_EXEC_SPEC` only under the same condition
(`hosts/gui_external/entry.py:105-107`).

**Preconditions**:
- [ ] `FREECAD_BUDDY_ALLOW_EXEC` is unset

**Steps**:
1. Start the H1 host with a clean environment and list the tools:
   ```bash
   uv run python scripts/automation/run_mcp_e2e.py
   ```
2. Call `debug_exec` directly by name anyway, bypassing `tools/list`.

**Checkpoints**:
- [ ] CP1: the surface lists 44 tools — verify: the `tools/list` result length is `44`
- [ ] CP2: `debug_exec` is absent from the listing — verify: no listed tool has `name` equal to `debug_exec`
- [ ] CP3: a direct call is refused — verify: the returned envelope `status` is `INVALID_INPUT`
- [ ] CP4: the refusal names the flag — verify: `detail.message` is exactly `debug_exec is disabled (set FREECAD_BUDDY_ALLOW_EXEC=1 to enable)`
- [ ] CP5: the denied attempt is still audited — verify: `grep '"event": "exec"' freecad-buddy-audit.jsonl` returns a before/after pair for the refused call
- [ ] CP6: no code was executed — verify: the document fingerprint is unchanged across the refused call
- [ ] CP7: the proxy surface matches — verify: a `tools/list` against `http://127.0.0.1:8765/mcp` also returns 44 tools with no `debug_exec`

**Cleanup**:
```bash
rm -f _automation/scratch.FCStd
```

---

### TC-11-02: debug_exec appears only with the exact flag value

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (operator flag), `mcp-tools-design.md` §5

**Host**: H1 inline. `Capabilities.from_env` (`usecases/capabilities.py:27-31`) compares the
environment value to the string `"1"` with `==`, so any other value disables the flag.

**Preconditions**:
- [ ] The operator accepts enabling arbitrary code execution for the duration of this scenario

**Steps**:
1. Start the host once for each value and list the tools:
   ```bash
   FREECAD_BUDDY_ALLOW_EXEC=1    uv run python -m freecad_buddy.hosts.main serve --transport stdio --mode inline
   FREECAD_BUDDY_ALLOW_EXEC=true uv run python -m freecad_buddy.hosts.main serve --transport stdio --mode inline
   FREECAD_BUDDY_ALLOW_EXEC=yes  uv run python -m freecad_buddy.hosts.main serve --transport stdio --mode inline
   FREECAD_BUDDY_ALLOW_EXEC=0    uv run python -m freecad_buddy.hosts.main serve --transport stdio --mode inline
   ```
2. For the `=1` run, call `query_capabilities` and read the startup log.

**Checkpoints**:
- [ ] CP1: with `=1` the surface lists 45 tools — verify: the `tools/list` result length is `45`
- [ ] CP2: with `=1` `debug_exec` is present — verify: a listed tool has `name` equal to `debug_exec`
- [ ] CP3: with `true` the tool is absent — verify: that run's `tools/list` length is `44`
- [ ] CP4: with `yes` the tool is absent — verify: that run's `tools/list` length is `44`
- [ ] CP5: with `0` the tool is absent — verify: that run's `tools/list` length is `44`
- [ ] CP6: capabilities report the enabled state — verify: the `query_capabilities` envelope's `structured_content` reports `exec_enabled` as `true` on the `=1` run only
- [ ] CP7: the operator is warned at startup — verify: the `=1` run's stderr contains `SECURITY: debug_exec ENABLED by operator flag`
- [ ] CP8: the warning is absent otherwise — verify: the `true`, `yes` and `0` runs' stderr do not contain that string

**Cleanup**:
```bash
unset FREECAD_BUDDY_ALLOW_EXEC
```

---

### TC-11-03: Every debug_exec call is audit-logged with a params digest

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (audit of exec), `data-contracts-design.md` §audit-record

**Host**: H1 inline. `AuditSink._record` (`adapters/audit_log.py:49-66`) writes
`event:"exec"` and additionally persists the executed `code` string, not only its digest.

**Preconditions**:
- [ ] `FREECAD_BUDDY_ALLOW_EXEC=1` for this scenario only
- [ ] A known audit-log path is set (verify: `echo $FREECAD_BUDDY_AUDIT_LOG`)

**Steps**:
1. Point the audit log at a scratch file and run one `debug_exec`:
   ```bash
   FREECAD_BUDDY_AUDIT_LOG=_automation/tc11-audit.jsonl FREECAD_BUDDY_ALLOW_EXEC=1 \
     uv run python -m freecad_buddy.hosts.main serve --transport stdio --mode inline
   ```
2. Read the resulting audit lines:
   ```bash
   python3 -c "import json;[print(json.loads(l)['event'], json.loads(l)['tool'], json.loads(l).get('params_digest')) for l in open('_automation/tc11-audit.jsonl')]"
   ```

**Checkpoints**:
- [ ] CP1: two lines were written for the one call — verify: `grep -c '"tool": "debug_exec"' _automation/tc11-audit.jsonl` returns `2`
- [ ] CP2: both carry the exec event — verify: both lines have `"event": "exec"`
- [ ] CP3: both carry a params digest — verify: each line's `params_digest` is a 64-character hexadecimal string
- [ ] CP4: the digests match each other — verify: the `before` and `after` lines carry the same `params_digest`
- [ ] CP5: the executed source is persisted — verify: the lines carry a `code` field equal to the submitted code string
- [ ] CP6: the after line carries the verdict — verify: the second line has a non-null `verify_verdict`
- [ ] CP7: each line is a valid audit record — verify: each line's `schema` is `fcb.audit-record/1`

**Cleanup**:
```bash
rm -f _automation/tc11-audit.jsonl
unset FREECAD_BUDDY_ALLOW_EXEC
```

---

### TC-11-04: Typed tools are the only mutation path

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (AD-4), `mcp-tools-design.md` §5 (previewable operations)

**Host**: H1 inline. `preview_op_table` (`hosts/tool_catalog.py:909-927`) is built from the
`sketch_*` and `feature_*` spec lists only, so `debug_exec` is excluded structurally rather than
by a name list.

**Preconditions**:
- [ ] `FREECAD_BUDDY_ALLOW_EXEC` is unset

**Steps**:
1. List the tool surface and inspect every name.
2. Ask `preview_dry_run` to preview `debug_exec` and read the refusal.
3. Ask `preview_dry_run` to preview a name that is not a tool at all.

**Checkpoints**:
- [ ] CP1: no generic script or eval tool exists — verify: `grep -riE '"(exec|eval|script|run_python|run_code)"' src/freecad_buddy/hosts/tool_catalog.py` matches only the gated `debug_exec` spec
- [ ] CP2: every mutating tool is a typed `document_*`, `sketch_*`, `feature_*` or `export_*` — verify: the 44 listed names contain no other mutating prefix
- [ ] CP3: `debug_exec` is not previewable — verify: previewing it returns `status=INVALID_INPUT` with `detail.message` starting `not a previewable mutation tool:`
- [ ] CP4: the refusal lists what IS previewable — verify: `detail.message` contains `(previewable: ` followed by `sketch_`/`feature_` names only
- [ ] CP5: an unknown name is refused the same way — verify: step 3 returns `status=INVALID_INPUT` with the same `not a previewable mutation tool:` prefix
- [ ] CP6: every input schema is closed — verify: `python3 -c "import json;s=json.load(open('.../tool_surface.json'));print(all(t['input_schema'].get('additionalProperties') is False for t in s))"` returns `True`
- [ ] CP7: an untyped extra argument is rejected — verify: any tool called with an undeclared key returns an MCP protocol rejection, not an envelope

**Cleanup**:
```bash
# No files written.
```

---

### TC-11-05: The RPC listener binds loopback only

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §2 (loopback bind), `integration-mcp-freecad.md` §2.4

**Host**: the in-FreeCAD RPC listener. `RpcListener.__init__` defaults `host="127.0.0.1"`
(`adapters/rpc_listener.py:109`) and `_bind` binds exactly that
(`adapters/rpc_listener.py:141-150`).

**Preconditions**:
- [ ] FreeCAD GUI is running with the addon loaded
- [ ] The machine's LAN IPv4 address is known

**Steps**:
1. Read the listener port from the discovery file.
2. Confirm the bound address:
   ```bash
   netstat -ano | grep ":<port>" | grep LISTENING
   ```
3. Attempt a TCP connect to `<LAN-IP>:<port>`.

**Checkpoints**:
- [ ] CP1: the listener is bound to `127.0.0.1`, not `0.0.0.0` — verify: the `netstat` line shows the local address as `127.0.0.1:<port>`
- [ ] CP2: the discovery record agrees — verify: the `host` field in `rpc-<pid>.json` is `127.0.0.1`
- [ ] CP3: a LAN-IP connect is refused — verify: the connect raises `ConnectionRefusedError` or times out with no handshake
- [ ] CP4: a loopback connect still succeeds — verify: a connect to `127.0.0.1:<port>` completes `rpc_hello` and returns `contract_version` `"1"`
- [ ] CP5: no other interface is listening on that port — verify: the `netstat` output shows exactly one LISTENING line for that port

**Cleanup**:
```bash
# No files written.
```

---

### TC-11-06: The MCP HTTP endpoint binds loopback only

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §2 (loopback bind), `integration-mcp-clients.md` §transport

**Host**: the H2 GUI proxy. `_HOST = "127.0.0.1"` and `_PORT = 8765` are module constants
(`hosts/gui_external/entry.py:38-39`) and `run()` passes them straight into the uvicorn config
(`hosts/gui_external/entry.py:182`). There is no `--host` or `--port` CLI flag to change them.

**Preconditions**:
- [ ] The proxy is serving (verify: `netstat -ano | grep ":8765" | grep LISTENING`)

**Steps**:
1. Confirm the bound address for port 8765.
2. Attempt an HTTP POST to `http://<LAN-IP>:8765/mcp`.
3. Confirm no CLI flag can rebind:
   ```bash
   uv run python -m freecad_buddy.hosts.main serve --transport http --mode rpc --host 0.0.0.0
   ```

**Checkpoints**:
- [ ] CP1: the endpoint is bound to `127.0.0.1:8765` — verify: the `netstat` line shows the local address as `127.0.0.1:8765`
- [ ] CP2: a LAN-IP POST fails at the transport — verify: `curl` to `http://<LAN-IP>:8765/mcp` reports connection refused
- [ ] CP3: a loopback POST is served — verify: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/mcp` returns a real HTTP status code
- [ ] CP4: there is no host override flag — verify: the step 3 command exits non-zero with an unrecognized-argument error
- [ ] CP5: the bind is hard-coded, not read from the environment — verify: `grep -n "_HOST\|_PORT" src/freecad_buddy/hosts/gui_external/entry.py` shows literal values with no `os.environ` lookup
- [ ] CP6: loopback bind is the ONLY control on this endpoint — verify: `grep -riE "Bearer|Authorization|Origin|CORS" src/freecad_buddy/hosts/gui_external/entry.py` returns nothing (this gap is TC-99-01 and TC-99-02)

**Cleanup**:
```bash
# No files written.
```

---

### TC-11-07: The discovery file is 0600 and carries the session token

**Priority**: High
**Design Ref**: `security-and-service-design.md` §2 (discovery file), `integration-mcp-freecad.md` §2.4 (handshake)

**Host**: the in-FreeCAD RPC listener. `_write_discovery` (`adapters/rpc_listener.py:182-203`)
writes the record then calls `os.chmod(path, 0o600)`. **On Windows `chmod` only toggles the
read-only bit**, which the source states at lines 197-198: the real controls are the loopback
bind plus the per-session token. Grade CP2 accordingly on this platform.

**Preconditions**:
- [ ] FreeCAD GUI is running with the addon loaded

**Steps**:
1. Locate the discovery file:
   ```bash
   ls -l "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-"*.json
   ```
2. Read its contents.
3. Attempt a handshake with a wrong token.

**Checkpoints**:
- [ ] CP1: exactly one discovery file exists per live listener pid — verify: the filename is `rpc-<pid>.json` where `<pid>` is the running FreeCAD pid
- [ ] CP2: the file is not world-readable — verify: on POSIX `stat -c %a` returns `600`; on Windows record that `chmod` only set the read-only bit and the enforced control is the token
- [ ] CP3: the record carries a token — verify: the parsed JSON has a non-empty `token` string
- [ ] CP4: the record carries the contract version — verify: `contract_version` is `"1"`
- [ ] CP5: a wrong token is refused — verify: the handshake reply is an error frame with `message` exactly `auth failed`
- [ ] CP6: the refusal discloses nothing — verify: that error frame carries no `data.supported` and no capabilities
- [ ] CP7: the file is removed when the listener stops — verify: after FreeCAD quits, `ls "$APPDATA/FreeCAD/v1-1/freecad-buddy/rpc-<pid>.json"` returns not-found

**Cleanup**:
```bash
# The addon removes the file on quit.
```

---

### TC-11-08: Auto-approve warns at startup and audits every auto-approved mutation

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (auto-approve), `mcp-tools-design.md` §5 (confirm gate)

**Host**: H1 inline. `build_server` logs the warning when `auto_approve_enabled(caps)` is true
(`adapters/mcp_server.py:161-162`). `AuditSink.approval` (`adapters/audit_log.py:86-101`) writes
one `event:"approval"` line naming what the approval covered.

**Preconditions**:
- [ ] The operator accepts running mutations without a confirm token for this scenario

**Steps**:
1. Start the host with auto-approve on and a scratch audit log:
   ```bash
   FREECAD_BUDDY_AUTO_APPROVE=1 FREECAD_BUDDY_AUDIT_LOG=_automation/tc11-approve.jsonl \
     uv run python -m freecad_buddy.hosts.main serve --transport stdio --mode inline
   ```
2. Run one geometry mutation with NO `confirm` argument.
3. Repeat with `FREECAD_BUDDY_AUTO_APPROVE=true`.

**Checkpoints**:
- [ ] CP1: the operator is warned at startup — verify: stderr contains `SECURITY: mutation auto-approve ENABLED by operator flag`
- [ ] CP2: the mutation runs without a confirm token — verify: the envelope `status` is `OK` and no `this mutation requires a confirm` message appears
- [ ] CP3: one approval record was written — verify: `grep -c '"event": "approval"' _automation/tc11-approve.jsonl` returns `1`
- [ ] CP4: the approval names the tool — verify: that line's `tool` is the mutating tool name
- [ ] CP5: the approval carries the pre-mutation fingerprint — verify: that line's `fingerprint_before` matches the mutation's own `before` line
- [ ] CP6: the approval digest matches the mutation's digest — verify: the approval line's `params_digest` equals the `before`/`after` lines' digest
- [ ] CP7: `true` does not enable it — verify: the step 3 run's stderr lacks the warning and the same unconfirmed mutation is refused with `this mutation requires a confirm; call preview_dry_run and pass the preview_id it returns as confirm.preview_id`

**Cleanup**:
```bash
rm -f _automation/tc11-approve.jsonl
unset FREECAD_BUDDY_AUTO_APPROVE
```

---

### TC-11-09: The session token is regenerated per listener start

**Priority**: High
**Design Ref**: `security-and-service-design.md` §2 (per-session token), `integration-mcp-freecad.md` §2.4

**Host**: the in-FreeCAD RPC listener.

**Preconditions**:
- [ ] The operator can restart FreeCAD

**Steps**:
1. Record the token from the discovery file.
2. Quit FreeCAD and restart it.
3. Record the new token.
4. Attempt a handshake against the new listener using the OLD token.

**Checkpoints**:
- [ ] CP1: the second token differs from the first — verify: the two recorded `token` values are not equal
- [ ] CP2: the old token is refused — verify: the step 4 handshake reply is an error frame with `message` exactly `auth failed`
- [ ] CP3: the connection is closed after refusal — verify: the next `recv` on that socket returns zero bytes
- [ ] CP4: the new token is accepted — verify: a handshake with the step 3 token returns `contract_version` `"1"`
- [ ] CP5: auth is checked before version — verify: a handshake carrying the OLD token AND an unsupported `contract_version` still returns `auth failed`, not `contract version unsupported`
- [ ] CP6: the stale discovery file did not survive — verify: the pre-restart `rpc-<old pid>.json` no longer exists

**Cleanup**:
```bash
# No files written.
```

---

### TC-11-10: Reserved-prefix temporary documents never leak into document_list

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-20 TempDoc lifecycle), `mcp-tools-design.md` §5 (preview)

**Host**: H1 inline and the H2 proxy. `_discard_tempdoc` (`usecases/preview.py:338-351`) closes
the copy and removes its directory on the success, failure and exception paths alike. The
docstring states why: a leaked TempDoc is adopted by `document_list` and surfaced to the caller
mislabeled.

**Preconditions**:
- [ ] A document with at least one body is open
- [ ] `document_list` currently reports no `FCB_TMP_` handles

**Steps**:
1. Record the `document_list` result.
2. Run one `preview_dry_run` that succeeds.
3. Run one `verify_export_step` (which re-imports into a fresh `FCB_TMP_` document).
4. Record `document_list` again.

**Checkpoints**:
- [ ] CP1: the baseline list has no temp handles — verify: no returned name starts with `FCB_TMP_`
- [ ] CP2: the preview returned a terminal envelope — verify: the `status` is in the closed set
- [ ] CP3: no preview TempDoc remains — verify: no returned name starts with `FCB_TMP_prev_`
- [ ] CP4: no export re-import document remains — verify: no returned name starts with `FCB_TMP_`
- [ ] CP5: the list is identical to the baseline — verify: the step 4 handle set equals the step 1 handle set
- [ ] CP6: the user's own documents were untouched — verify: each pre-existing document's fingerprint digest is unchanged
- [ ] CP7: no temp directory remains on disk — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null` returns nothing

**Cleanup**:
```bash
rm -rf "$TEMP"/FCB_TMP_prev_*
```

---

### TC-11-11: A preview TempDoc is removed on every exit path

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (AD-20), `mcp-tools-design.md` §5 (preview)

**Host**: H1 inline. The prefix is `FCB_TMP_prev_` (`usecases/preview.py:33`) and it is carried by
the directory AND the filename, because the reopened document takes its `Name` from the file stem
(`usecases/preview.py:312-320`).

**Preconditions**:
- [ ] The temp directory is writable and its current `FCB_TMP_prev_*` count is recorded

**Steps**:
1. Run a preview whose operation SUCCEEDS.
2. Run a preview whose operation FAILS its post-verify, for example a pad on an unconstrained
   sketch that leaves an invalid object.
3. Run a preview whose operation RAISES, for example a feature naming an object that does not
   exist.
4. Count the remaining temp directories after each.

**Checkpoints**:
- [ ] CP1: the success path leaves nothing — verify: `ls -d "$TEMP"/FCB_TMP_prev_* 2>/dev/null | wc -l` is unchanged from the baseline after step 1
- [ ] CP2: the failure path leaves nothing — verify: the same count is unchanged after step 2
- [ ] CP3: the exception path leaves nothing — verify: the same count is unchanged after step 3
- [ ] CP4: the failure still returned an envelope — verify: step 2's `status` is `SPEC_FAILED` or `RECOMPUTE_ERROR`, not a raised exception
- [ ] CP5: the exception still returned an envelope — verify: step 3's `status` is a closed-set value with a `detail.message`
- [ ] CP6: cleanup never masked the outcome — verify: each step's `detail.message` names the real cause, not a cleanup failure
- [ ] CP7: no TempDoc is left open in FreeCAD — verify: `document_list` reports no `FCB_TMP_prev_` handle after any of the three

**Cleanup**:
```bash
rm -rf "$TEMP"/FCB_TMP_prev_*
```

---

### TC-11-12: The snapshot directory is removed on commit, abort and error

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (snapshot lifecycle), `verification-design.md` §rollback

**Host**: H1 inline. `temp_snapshot_path` mints `tempfile.mkdtemp(prefix="FCB_TMP_snap_")`
(`usecases/transaction.py:94`) and `_delete_snapshot` (`usecases/transaction.py:98-117`) empties
and removes it.

**Two keep-cases are deliberate, not leaks.** (a) Unproven rollback: `RollbackNotProven` keeps
the snapshot and names it in `mutation.snapshot_path`, because it is the only pre-mutation copy
and restoring is an operator decision (`usecases/transaction.py:584-601`). (b) Committed but
unhashable: the commit landed and cannot be fingerprinted, so `rolled_back` is `False`, the
status is `SPEC_FAILED`, and the snapshot is kept and named
(`usecases/transaction.py:375-391`). Both MUST retain the directory.

**Preconditions**:
- [ ] The temp directory `FCB_TMP_snap_*` count is recorded as the baseline

**Steps**:
1. Run a mutation that COMMITS.
2. Run a mutation that FAILS post-verify and rolls back provably.
3. Run a mutation whose commit raises.
4. Count `FCB_TMP_snap_*` directories after each.

**Checkpoints**:
- [ ] CP1: a committed mutation leaves no snapshot — verify: the directory count equals the baseline after step 1
- [ ] CP2: the committed envelope reports no snapshot path — verify: `structured_content.mutation.snapshot_path` is `null`
- [ ] CP3: a proven rollback leaves no snapshot — verify: the count equals the baseline after step 2
- [ ] CP4: the rolled-back envelope names its proof — verify: `mutation.rollback_proven` is `rolled_back_verified` or `rolled_back_via_snapshot`
- [ ] CP5: a failed commit leaves no snapshot — verify: the count equals the baseline after step 3
- [ ] CP6: an UNPROVEN rollback deliberately KEEPS its snapshot — verify: the envelope `text` starts `Mutation failed and its rollback could not be proven: ` and the named `mutation.snapshot_path` directory still exists on disk
- [ ] CP7: a committed-but-unhashable result deliberately KEEPS its snapshot — verify: the envelope has `mutation.rolled_back` `false`, `status` `SPEC_FAILED`, and a non-null `mutation.snapshot_path` that exists on disk
- [ ] CP8: both keep-cases are named to the operator — verify: `mutation.snapshot_path` is an absolute path the operator can act on

**Cleanup**:
```bash
# Remove ONLY the directories the deliberate keep-cases created, after the operator
# has decided whether to restore from them.
rm -rf "$TEMP"/FCB_TMP_snap_*
```

---

### TC-11-13: Cleanup only touches reserved-prefix paths

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (cleanup scope), `verification-design.md` §rollback

**Host**: H1 inline. Both cleanup helpers gate on the directory's basename prefix before emptying
it: `_delete_snapshot` (`usecases/transaction.py:105-111`) and `_remove_tempdir`
(`usecases/preview.py:327-336`). A non-prefixed path has only the single file removed
(snapshot case) or is left entirely alone (preview case).

**Preconditions**:
- [ ] A scratch directory with a non-reserved name containing two files is prepared

**Steps**:
1. Create `"$TEMP"/not-reserved/` holding `keep-a.txt` and `keep-b.txt`.
2. Drive the snapshot cleanup helper against `"$TEMP"/not-reserved/keep-a.txt`:
   ```bash
   uv run python -c "from freecad_buddy.usecases.transaction import _delete_snapshot; _delete_snapshot(r'<TEMP>/not-reserved/keep-a.txt')"
   ```
3. Drive the preview cleanup helper against a file inside the same directory:
   ```bash
   uv run python -c "from freecad_buddy.usecases.preview import _remove_tempdir; _remove_tempdir(r'<TEMP>/not-reserved/keep-b.txt')"
   ```
4. List the directory.

**Checkpoints**:
- [ ] CP1: the named snapshot file was removed — verify: `keep-a.txt` no longer exists
- [ ] CP2: the sibling file survived — verify: `keep-b.txt` still exists after step 2
- [ ] CP3: the non-reserved directory survived — verify: `"$TEMP"/not-reserved/` still exists
- [ ] CP4: the preview helper removed nothing — verify: `keep-b.txt` still exists after step 3
- [ ] CP5: neither helper raised — verify: both commands exit `0`
- [ ] CP6: a reserved-prefix directory IS emptied — verify: repeating the snapshot call against a real `FCB_TMP_snap_*` directory removes the directory and all its contents

**Cleanup**:
```bash
rm -rf "$TEMP"/not-reserved
```

---

### TC-11-14: The bridge writes into the user's document folder only via an explicit path

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §3 (write scope), `mcp-tools-design.md` §5 (exports)

**Host**: H1 inline and the H2 proxy.

**Preconditions**:
- [ ] A user document folder is chosen and its full file listing plus modification times are recorded

**Steps**:
1. Record the folder listing with modification times.
2. Run the full read-only sweep: `document_open`, every `query_*`, every `verify_*`,
   `preview_dry_run`, `document_close`.
3. Record the folder listing again.
4. Run one `export_stl` with an explicit `path` INSIDE that folder, and one `document_save`.
5. Record the folder listing a third time.

**Checkpoints**:
- [ ] CP1: reads created no file — verify: the step 3 listing has the same file names as step 1
- [ ] CP2: reads modified no file — verify: every modification time in step 3 equals its step 1 value
- [ ] CP3: `preview_dry_run` wrote nothing there — verify: no `FCB_TMP_prev_` file appears in the step 3 listing
- [ ] CP4: no snapshot was written there — verify: no `FCB_TMP_snap_` entry appears in the step 3 listing
- [ ] CP5: the explicit export wrote exactly one new file — verify: the step 5 listing adds only the requested `path`
- [ ] CP6: `document_save` touched only the document — verify: only the `.FCStd` file's modification time changed, plus its `.FCBak` if FreeCAD writes one
- [ ] CP7: no audit log was written there — verify: no `freecad-buddy-audit.jsonl` appears in the folder unless `FREECAD_BUDDY_AUDIT_LOG` explicitly named it (see TC-99-06)

**Cleanup**:
```bash
rm -f "<user document folder>/tc11-export.stl"
```

---

### TC-11-15: The audit log is append-only

**Priority**: Critical
**Design Ref**: `security-and-service-design.md` §1 (audit), `data-contracts-design.md` §audit-record

**Host**: H1 inline. `AuditSink._write` (`adapters/audit_log.py:43-47`) opens the file in `"a"`
mode under a lock and writes one line. The module docstring states the sink never truncates,
rotates, or reads it.

**Preconditions**:
- [ ] A scratch audit-log path is set

**Steps**:
1. Run a batch of mutations against a scratch audit log and record the line count and a digest of
   the whole file.
2. Run a second batch against the same file.
3. Compare the file to the recorded state.
4. Search the source for any read, truncate or rotate of the audit path.

**Checkpoints**:
- [ ] CP1: the second batch only appended — verify: the first N lines of the file are byte-identical to the step 1 content
- [ ] CP2: the line count grew — verify: the step 3 line count is greater than the step 1 count
- [ ] CP3: no line was rewritten — verify: the digest of the first N lines equals the step 1 digest
- [ ] CP4: the file is opened append-only — verify: `grep -n 'open(self._path, "a"' src/freecad_buddy/adapters/audit_log.py` returns line 46
- [ ] CP5: no bridge tool reads the audit log — verify: `grep -rn "FREECAD_BUDDY_AUDIT_LOG\|audit.jsonl" src/freecad_buddy/usecases/ src/freecad_buddy/contracts/` returns nothing
- [ ] CP6: no rotation or truncation exists — verify: `grep -rniE "rotate|truncate|\"w\"|'w'" src/freecad_buddy/adapters/audit_log.py` returns nothing
- [ ] CP7: writes are serialized — verify: the file after a concurrent two-writer run contains no interleaved partial line; every line parses as JSON

**Cleanup**:
```bash
rm -f _automation/tc11-append.jsonl
```

---

### TC-11-16: The session token never appears in results, artifacts or reports

**Priority**: High
**Design Ref**: `security-and-service-design.md` §2 (token handling), `data-contracts-design.md` §envelope

**Host**: the in-FreeCAD RPC listener plus the H2 proxy. The token leaves the listener only via
the discovery file (`adapters/rpc_listener.py:182-203`); the handshake result carries
`contract_version`, `freecad_version` and `capabilities` only (`adapters/rpc_listener.py:294-298`).

**Preconditions**:
- [ ] The current session token is recorded from the discovery file

**Steps**:
1. Run a representative set of tools covering `query_*`, `verify_*`, `export_*`, one mutation,
   and `query_screenshot`.
2. Search every produced envelope, every render artifact, the audit log, and both log files for
   the token string.

**Checkpoints**:
- [ ] CP1: no envelope carries the token — verify: `grep -F "<token>" _automation/e2e_report.json` returns nothing
- [ ] CP2: no render artifact carries it — verify: `grep -aF "<token>" _automation/*.png` returns nothing
- [ ] CP3: the audit log does not carry it — verify: `grep -F "<token>" freecad-buddy-audit.jsonl` returns nothing
- [ ] CP4: the addon log does not carry it — verify: `grep -F "<token>" "$APPDATA/FreeCAD/v1-1/freecad-buddy/addon.log"` returns nothing
- [ ] CP5: the proxy log does not carry it — verify: `grep -F "<token>" "$APPDATA/FreeCAD/v1-1/freecad-buddy/mcp-proxy.log"` returns nothing
- [ ] CP6: the handshake reply does not echo it — verify: the `rpc_hello` result object has exactly the keys `contract_version`, `freecad_version`, `capabilities`
- [ ] CP7: `query_capabilities` does not expose it — verify: the envelope's `structured_content` contains no field whose value equals the token

**Cleanup**:
```bash
# No files written.
```
