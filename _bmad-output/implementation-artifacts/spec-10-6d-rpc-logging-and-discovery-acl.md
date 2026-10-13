---
title: 'Story 10.6 goal D: RPC logging levels and discovery-file ACL comment'
type: 'bugfix'
created: '2026-10-13'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: 'd9895cee90179310a53a5afddbc5b545a5806e1f'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The RPC hop logs its normal and abnormal connection ends at the wrong level (Story 10.6 AC5, AC6). A client that closes or resets its socket makes the listener log `ERROR frame read failed` with a traceback (F-31). A first frame that is not JSON is refused with no log line (F-31). A call whose connection drops in flight returns `WORKER_CRASHED "listener connection dropped"` but `rpc_client` logs nothing, so `mcp-proxy.log` has no line for it (F-24). The comment in `RpcListener._write_discovery` says the file is 0600, but on Windows `chmod` cannot do that; the folder ACL is what protects it (F-32).

**Approach:** Each event is logged once, without a traceback, at the level that matches it:
- client closed or reset its connection: `INFO`;
- frame over the cap, not UTF-8, cut mid-frame, or any other read error: `WARNING`;
- first frame not valid JSON: `WARNING` (as for a JSON frame that is not `rpc_hello` today);
- a reply that cannot be sent because the client has gone: `WARNING`, and the connection ends, so the following read does not log a second line;
- an in-flight call whose connection drops: `WARNING` in `rpc_client`, naming the method.

Unexpected exceptions (`connection handler crashed`, `malformed request`, `audit write failed`) keep `logger.exception`. The discovery-file comment states what each platform applies: owner-only mode on POSIX; on Windows the read-only bit stays clear and the file inherits the FreeCAD user appdata folder ACL (owner, SYSTEM, Administrators); the loopback bind and per-session token are the enforced posture on both. No behaviour other than logging changes.

</frozen-after-approval>

## Implementation Notes

- `src/freecad_buddy/adapters/rpc_listener.py`: new `_read_line` logs a `ConnectionError` at INFO and any other read error at WARNING, both without traceback; the handshake and the serve loop share it. A non-JSON first frame logs one WARNING. `_write_frame` returns False and logs one WARNING when the client has gone, and the serve loop then ends the connection. The discovery comment states the POSIX mode and the inherited Windows ACL.
- `src/freecad_buddy/adapters/rpc_client.py`: a dropped in-flight call logs one WARNING naming the method.
- Tests: 5 in `tests/external/test_rpc_listener.py` and 1 in `tests/external/test_rpc_client.py`. The 5 that check new behaviour fail on the baseline; "a clean close logs nothing" passed before and guards it. A TCP reset is made with `SO_LINGER` 0 (`HH` on Windows, `ii` elsewhere).
- The worker `frame read failed` lines seen after an abandoned body in Story 10.6 are gone from the fcb run.
- Review patch: a clean EOF now logs one INFO `client closed the connection`, and a reset logs `client reset the connection`, matching the Intent's "closed or reset: INFO". `_handshake` returns the result of `_write_frame`, so a failed hello reply also ends the connection with one line. The tests prove each handler has returned by completing a second handshake (the accept loop serves one connection at a time) instead of sleeping.

## Review Triage Log

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| 1 | `_handshake` ignores `_write_frame`'s result, so a failed hello reply is followed by a second log line | low | `rpc_listener.py` returned `True` after `_write_frame`; the serve loop then read the dead socket. One-word fix. | patch |
| 2 | Clean EOF logged nothing, but the Intent says closed or reset logs INFO | medium | `read_line` returns `None` at EOF and `_read_line` returned it silently; the test locked the silence in. | patch |
| 3 | `_write_frame` test used a closed socket (EBADF); no test drove a failed reply through the serve loop | medium | The claim "a failed send ends the connection with one line" had no test. Replaced with a reset-before-reply test on a slow method. | patch |
| 4 | Non-UTF-8 and over-cap frames untested | low | Non-UTF-8 test added (one `sendall`). Over-cap shares the same `ValueError` branch; rejected. | patch |
| 5 | Tests relied on fixed sleeps; `_records_after` hid timeouts | medium | `records == []` could pass before the handler ran. Now a second completed handshake proves the handler returned. | patch |
| 6 | Windows ACL claim holds only for the default appdata folder | low | Comment now says the file inherits its folder's ACL and names the default folder's grants. | patch |
| 7 | Client WARNING does not say whether the send or the reply failed | low | Both phases mean the outcome is unknown to the caller; recovery is the same. Fix adds branches. | reject |
| 8 | Client logs nothing for read timeout, connect refused, handshake rejected or a malformed reply | low | Outside AC5 (dropped in-flight call); recorded for later. | defer |
| 9 | POSIX discovery file is created with the umask mode before `chmod`, and a `chmod` failure is silent | low | Pre-existing (`write_text` then `os.chmod`); not caused by this change. | defer |
| 10 | UAT test cases do not check the new levels or the absence of tracebacks | low | `TC-10-concurrency-timeout-and-quarantine.md` only greps the old messages. Test-case update for the next UAT run. | defer |
| 11 | Listener log lines carry no peer address | low | Improvement; plumbing `_addr` through adds parameters. | reject |
