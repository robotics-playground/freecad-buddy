"""Raw RPC socket probes for the TC-11 listener scenarios (phase P9), on p8_rpc's Client/Log.

    p9_rpc.py s05 <pid> <lan ip>    TC-11-05: TCP connect to <lan ip>:<port>; loopback rpc_hello with the record token
    p9_rpc.py s07 <pid>             TC-11-07: masked token, contract_version, wrong-token hello, next recv
    p9_rpc.py s09 <pid>             TC-11-09: hold the token in memory, wait for a new rpc-<pid>.json of a different
                                    FreeCAD (the restart; its pid in evidence/tc-11-09-newpid.txt), then compare tokens
                                    and send the OLD-token hellos; the NEW-token hello waits for
                                    evidence/tc-11-09-proxystopped.txt
    p9_rpc.py s16 <pid>             TC-11-16: loopback hello result keys; grep the token in the given files (verdicts only)

Every frame goes to evidence/<tag>-rpc.jsonl with the token replaced by "<token>". Tokens are printed only masked:
first four characters and the length.
"""
import json
import socket
import sys
import time
from pathlib import Path

from p8_rpc import APPDATA, Client, Log, check, record_for

EVIDENCE = Path(__file__).resolve().parent


def mask(token):
    return f"{token[:4]}...(len {len(token)})"


def s05(pid, lan_ip):
    record = record_for(int(pid))
    log = Log("tc-11-05", record["token"])
    check("record host / port", [record["host"], record["port"]])
    started = time.monotonic()
    try:
        sock = socket.create_connection((lan_ip, record["port"]), timeout=5)
        check("LAN connect", f"CONNECTED (unexpected) after {round(time.monotonic() - started, 3)} s")
        sock.close()
    except OSError as exc:
        check("LAN connect raised", f"{type(exc).__name__}: {exc} after {round(time.monotonic() - started, 3)} s")
    client = Client("L", record, log)
    frame = client.hello()
    check("loopback hello", frame)
    client.close()


def s07(pid):
    record = record_for(int(pid))
    log = Log("tc-11-07", record["token"])
    token = record.get("token")
    check("record keys", sorted(record))
    check("token non-empty string / masked", [isinstance(token, str) and bool(token), mask(token)])
    check("contract_version", record.get("contract_version"))
    client = Client("W", record, log)
    frame = client.hello(token="wrong-" + "x" * 16)
    check("wrong-token frame", frame)
    error = (frame or {}).get("error") or {}
    check("error.message / data / result present", [error.get("message"), error.get("data"), "result" in (frame or {})])
    check("next recv", repr(client.read(5)))


def s09(pid):
    old = record_for(int(pid))
    old_token = old["token"]
    log = Log("tc-11-09", old_token)
    check("old record pid / masked token", [old["pid"], mask(old_token)])
    (EVIDENCE / "tc-11-09-waiting.txt").write_text("holding the old token in memory; waiting for a new FreeCAD\n")
    deadline = time.monotonic() + 1800
    new = None
    while time.monotonic() < deadline:
        go = EVIDENCE / "tc-11-09-newpid.txt"
        if go.exists() and go.read_text().strip():
            new_pid = int(go.read_text().strip())
            if (APPDATA / f"rpc-{new_pid}.json").exists():
                new = record_for(new_pid)
                break
        time.sleep(1)
    if new is None:
        check("restart", "no new FreeCAD within 30 min")
        return
    log.token = old_token
    new_log = Log("tc-11-09", new["token"])
    check("new record pid / masked token", [new["pid"], mask(new["token"])])
    check("tokens differ", old_token != new["token"])
    check("old rpc file exists", (APPDATA / f"rpc-{old['pid']}.json").exists())
    client = Client("OLD", new, log)
    client.log = _TwoTokenLog(old_token, new["token"])
    frame = client.hello(token=old_token)
    check("OLD-token frame", _redact(frame, old_token, new["token"]))
    nxt = client.read(5)
    check("next recv after refusal", repr(nxt))
    client2 = Client("OLDV", new, log)
    client2.log = _TwoTokenLog(old_token, new["token"])
    client2.send({"jsonrpc": "2.0", "id": 1, "method": "rpc_hello",
                  "params": {"token": old_token, "contract_version": "999"}}, show="rpc_hello old token, version 999")
    check("OLD-token + unsupported version frame", _redact(client2.read(), old_token, new["token"]))
    stopped = EVIDENCE / "tc-11-09-proxystopped.txt"
    while not stopped.exists() and time.monotonic() < deadline:
        time.sleep(1)
    client3 = Client("NEW", new, new_log)
    client3.log = _TwoTokenLog(old_token, new["token"])
    check("NEW-token hello", client3.hello())
    client3.close()
    (EVIDENCE / "tc-11-09-waiting.txt").unlink()
    stopped.unlink()


class _TwoTokenLog(Log):
    def __init__(self, old_token, new_token):
        super().__init__("tc-11-09", new_token)
        self.old_token = old_token

    def write(self, entry):
        text = json.dumps(entry, ensure_ascii=False).replace(self.old_token, "<old token>").replace(self.token, "<new token>")
        self.handle.write(text + "\n")
        self.handle.flush()
        print(text[:1500])


def _redact(value, *tokens):
    text = json.dumps(value)
    for token in tokens:
        text = text.replace(token, "<token>")
    return json.loads(text)


def s16(pid, *files):
    record = record_for(int(pid))
    token = record["token"]
    log = Log("tc-11-16", token)
    check("masked token", mask(token))
    for name in files:
        path = Path(name)
        found = token.encode() in path.read_bytes() if path.exists() else "missing"
        check(f"token in {path.name}", found)
    client = Client("H", record, log)
    frame = client.hello()
    check("hello frame", frame)
    check("hello result keys", sorted(((frame or {}).get("result") or {}).keys()))
    client.close()


if __name__ == "__main__":
    {"s05": s05, "s07": s07, "s09": s09, "s16": s16}[sys.argv[1]](*sys.argv[2:])
