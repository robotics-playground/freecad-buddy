"""TC-99-03: a second RPC client while the addon's proxy holds the listener.

Holds the second socket open (if it connects) until a file `tc-99-03-release` appears or 120 s pass,
so the GUI capture can be taken while the second client is blocked.
"""
import json, os, socket, sys, time
from pathlib import Path

E = Path(__file__).resolve().parent
rec = json.loads(Path(sys.argv[1]).read_text())
host, port, token = rec["host"], rec["port"], rec["token"]
out = {"host": host, "port": port}
t0 = time.monotonic()
try:
    s = socket.create_connection((host, port), timeout=5)
    out["connect"] = "ok"
    out["connect_s"] = round(time.monotonic() - t0, 3)
except Exception as exc:  # noqa: BLE001
    out["connect"] = repr(exc)
    out["connect_s"] = round(time.monotonic() - t0, 3)
    s = None
if s is not None:
    hello = {"jsonrpc": "2.0", "id": 1, "method": "rpc_hello",
             "params": {"contract_version": "1", "client": "tc-99-03-second", "token": token}}
    s.sendall((json.dumps(hello) + "\n").encode())
    s.settimeout(10)
    t1 = time.monotonic()
    try:
        data = s.recv(65536)
        out["first_frame"] = data.decode("utf-8", "replace")[:500]
    except socket.timeout:
        out["first_frame"] = None
        out["first_frame_note"] = "no frame within 10 s deadline"
    except Exception as exc:  # noqa: BLE001
        out["first_frame"] = repr(exc)
    out["read_s"] = round(time.monotonic() - t1, 3)
(E / "tc-99-03-probe.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out), flush=True)
release = E / "tc-99-03-release"
deadline = time.monotonic() + 120
while s is not None and not release.exists() and time.monotonic() < deadline:
    time.sleep(0.5)
if s is not None:
    s.close()
print("closed", flush=True)
