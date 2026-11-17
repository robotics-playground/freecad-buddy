"""Raw RPC socket clients for the TC-10 listener scenarios (phase R2, from 2026-10-23-02 p8_rpc.py): r2_rpc.py <scenario> <freecad pid> [args].

    s03 <pid>                 TC-10-03: client B (valid hello while the proxy holds the session), client C (wrong token)
    s04 <pid>                 TC-10-04: client A (hello, document_list, close), B (document_list first), C (hello, document_list)
    s06 <pid> <cylinder>      TC-10-06: session A opens the cylinder, B reads, lists and closes it with A's handle
    s13 <pid>                 TC-10-13: a request with no trailing newline then close; a fresh client hello + document_list
    s14 <pid>                 TC-10-14: 17 MiB with no newline; a non-UTF-8 frame; a third client hello + document_list;
                              FreeCAD working set before and after the over-cap stream
    s14m <pid> <doc>          TC-10-14: a mutating call (script_exec) on <doc> over a fresh session

The record is %APPDATA%/FreeCAD/v1-1/freecad-buddy/rpc-<pid>.json. Every frame sent and every
line received goes to evidence/tc-10-<nn>-rpc.jsonl with the token replaced by "<token>", with
seconds since the client's connect.
"""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
APPDATA = Path(os.environ["APPDATA"]) / "FreeCAD" / "v1-1" / "freecad-buddy"


class Log:
    def __init__(self, tag, token):
        self.handle = (EVIDENCE / f"{tag}-rpc.jsonl").open("a", encoding="utf-8")
        self.token = token

    def write(self, entry):
        text = json.dumps(entry, ensure_ascii=False).replace(self.token, "<token>")
        self.handle.write(text + "\n")
        self.handle.flush()
        print(text[:1500])


class Client:
    def __init__(self, name, record, log):
        self.name, self.record, self.log = name, record, log
        self.started = time.monotonic()
        self.sock = socket.create_connection((record["host"], record["port"]), timeout=5)
        self.buf = b""
        self.log.write({"client": name, "connect": "connected", "elapsed": self.elapsed(),
                        "record": f"rpc-{record['pid']}.json", "port": record["port"]})

    def elapsed(self):
        return round(time.monotonic() - self.started, 3)

    def send(self, payload, newline=True, show=None):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.sock.sendall(data + (b"\n" if newline else b""))
        self.sent_at = time.monotonic()
        self.log.write({"client": self.name, "sent": show or data.decode("utf-8", "replace")[:400],
                        "bytes": len(data) + (1 if newline else 0), "newline": newline, "elapsed": self.elapsed()})

    def hello(self, token=None):
        self.send({"jsonrpc": "2.0", "id": 1, "method": "rpc_hello",
                   "params": {"token": self.record["token"] if token is None else token, "contract_version": "1"}})
        return self.read()

    def request(self, method, params, request_id=2):
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        return self.read()

    def read(self, timeout=30):
        self.sock.settimeout(timeout)
        try:
            while b"\n" not in self.buf:
                chunk = self.sock.recv(65536)
                if not chunk:
                    line = self.buf.decode("utf-8", "replace")
                    self.buf = b""
                    self.log.write({"client": self.name, "recv": "<zero bytes: closed by peer>", "partial": line,
                                    "elapsed": self.elapsed()})
                    return None
                self.buf += chunk
        except OSError as exc:
            self.log.write({"client": self.name, "recv": f"<{type(exc).__name__}: {exc}>", "elapsed": self.elapsed()})
            return exc
        line, _, self.buf = self.buf.partition(b"\n")
        since_send = round(time.monotonic() - self.sent_at, 3)
        frame = json.loads(line)
        self.log.write({"client": self.name, "recv": frame, "elapsed": self.elapsed(), "since_last_send_s": since_send})
        return frame

    def close(self):
        self.sock.close()
        self.log.write({"client": self.name, "closed_by_client": True, "elapsed": self.elapsed()})


def record_for(pid):
    record = json.loads((APPDATA / f"rpc-{pid}.json").read_text(encoding="utf-8"))
    record["pid"] = pid
    return record


def check(label, value):
    print(f"CHECK {label}: {json.dumps(value, ensure_ascii=False, default=str)[:3000]}")


def working_set(pid):
    out = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-Process -Id {pid}).WorkingSet64"],
                         capture_output=True, text=True).stdout.strip()
    return int(out)


def s03(pid):
    record = record_for(pid)
    log = Log("tc-10-03", record["token"])
    try:
        connect_started = time.monotonic()
        b = Client("B", record, log)
        check("B connect seconds", round(time.monotonic() - connect_started, 3))
    except OSError as exc:
        check("B connect raised", repr(exc))
        return
    frame = b.hello()
    check("B first frame / seconds after hello", [frame, round(time.monotonic() - b.sent_at, 3)])
    check("B next recv", repr(b.read(5)))
    c = Client("C", record, log)
    frame = c.hello(token="not-the-token")
    check("C first frame", frame)
    check("C next recv", repr(c.read(5)))


def s04(pid):
    record = record_for(pid)
    log = Log("tc-10-04", record["token"])
    a = Client("A", record, log)
    check("A hello", a.hello())
    check("A document_list", a.request("document_list", {}))
    a.close()
    time.sleep(0.5)
    b = Client("B", record, log)
    b.send({"jsonrpc": "2.0", "id": 1, "method": "document_list", "params": {}})
    check("B first frame", b.read())
    check("B next recv", repr(b.read(5)))
    c = Client("C", record, log)
    check("C hello", c.hello())
    check("C document_list", c.request("document_list", {}))
    c.close()


def s06(pid, cylinder):
    record = record_for(pid)
    log = Log("tc-10-06", record["token"])
    a = Client("A", record, log)
    check("A hello", a.hello())
    opened = a.request("document_open", {"path": cylinder})
    handle = ((opened or {}).get("result", {}).get("structured_content") or {}).get("doc")
    check("A document_open handle", handle)
    a.close()
    time.sleep(0.5)
    b = Client("B", record, log)
    check("B hello", b.hello())
    tree = b.request("query_tree_summary", {"doc": handle})
    names = [line.split(" ")[2] for line in ((tree or {}).get("result", {}).get("text") or "").splitlines()
             if line[:1] in ("v", "-")]
    check("B tree (to name the object)", [(tree or {}).get("result", {}).get("status"), names])
    queried = b.request("query_object", {"doc": handle, "object": names[0] if names else "Cylinder"}, 3)
    result = (queried or {}).get("result", {})
    check("B query_object schema / status / subject", [result.get("schema"), result.get("status"),
                                                       (result.get("structured_content") or {}).get("name"),
                                                       (result.get("structured_content") or {}).get("label")])
    listed = b.request("document_list", {}, 4)
    handles = [d.get("doc") for d in ((listed or {}).get("result", {}).get("structured_content") or {}).get("documents", [])]
    check("B document_list status / contains A's handle", [(listed or {}).get("result", {}).get("status"), handle in handles, handles])
    closed = b.request("document_close", {"doc": handle}, 5)
    check("B document_close status", (closed or {}).get("result", {}).get("status"))
    listed = b.request("document_list", {}, 6)
    handles = [d.get("doc") for d in ((listed or {}).get("result", {}).get("structured_content") or {}).get("documents", [])]
    check("B document_list after close: status / contains A's handle",
          [(listed or {}).get("result", {}).get("status"), handle in handles, handles])
    b.close()


def s13(pid):
    record = record_for(pid)
    log = Log("tc-10-13", record["token"])
    a = Client("A", record, log)
    check("A hello", a.hello())
    a.send({"jsonrpc": "2.0", "id": 2, "method": "document_list", "params": {}}, newline=False)
    a.close()
    time.sleep(1.0)
    try:
        b = Client("B", record, log)
        check("B connect", "succeeded")
    except OSError as exc:
        check("B connect raised", repr(exc))
        return
    check("B hello", b.hello())
    check("B document_list", b.request("document_list", {}))
    b.close()


def s14(pid):
    record = record_for(pid)
    log = Log("tc-10-14", record["token"])
    before = working_set(pid)
    check("ws_before", before)
    a = Client("A", record, log)
    check("A hello", a.hello())
    try:
        a.send(b'{"x":"' + b"A" * (17 * 1024 * 1024), newline=False, show='{"x":"' + "A..." + " (17 MiB, no newline)")
    except OSError as exc:
        check("A send raised", repr(exc))
    check("A next recv", repr(a.read(10)))
    after = working_set(pid)
    check("ws_after / ws_after - ws_before", [after, after - before, (after - before) < 104857600])
    a.sock.close()
    c2 = Client("C2", record, log)
    c2.send(b"\xff\xfe\xfd not utf-8 \xc3\x28", newline=True, show="<raw bytes ff fe fd ' not utf-8 ' c3 28>")
    check("C2 next recv", repr(c2.read(5)))
    c2.sock.close()
    c3 = Client("C3", record, log)
    check("C3 hello", c3.hello())
    check("C3 document_list", c3.request("document_list", {}))
    c3.close()


def s14m(pid, doc):
    record = record_for(pid)
    log = Log("tc-10-14", record["token"])
    m = Client("M", record, log)
    check("M hello", m.hello())
    check("M script_exec", m.request("script_exec", {"doc": doc, "code": "result = len(doc.Objects)"}))
    m.close()


if __name__ == "__main__":
    {"s03": s03, "s04": s04, "s06": s06, "s13": s13, "s14": s14, "s14m": s14m}[sys.argv[1]](int(sys.argv[2]), *sys.argv[3:])
