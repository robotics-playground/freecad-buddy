"""Send the exact handshake frames a TC-01 scenario names to an RPC listener, and log them.

    p1_rpc.py <tag> <rpc-<pid>.json> '<frame>' [--reads N] [--connect-only]

<frame> is the JSON object of the test case, or a raw string sent as is (e.g. "not json"); a
newline is appended. "$TOKEN" inside it is replaced by the record's token, "$CONTRACT" by its
contract_version. One connection per call; after the send it reads N lines (default 2, so the
second read shows whether the listener closed the socket). With --connect-only it only connects
(timeout 5 s) and reports the outcome. Every frame sent and every line received goes to
evidence/<tag>-rpc.jsonl with the token replaced by "<token>", plus the elapsed time.
"""

import json
import socket
import sys
import time
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent


def main():
    tag, record_path, frame = sys.argv[1], sys.argv[2], sys.argv[3]
    reads = int(sys.argv[sys.argv.index("--reads") + 1]) if "--reads" in sys.argv else 2
    record = json.loads(Path(record_path).read_text(encoding="utf-8"))
    token = record["token"]
    payload = frame.replace("$TOKEN", token).replace("$CONTRACT", record["contract_version"])
    log = (EVIDENCE / f"{tag}-rpc.jsonl").open("a", encoding="utf-8")

    def write(entry):
        text = json.dumps(entry, ensure_ascii=False).replace(token, "<token>")
        log.write(text + "\n")
        print(text)

    target = {"host": record["host"], "port": record["port"], "record": Path(record_path).name}
    started = time.monotonic()
    try:
        connection = socket.create_connection((record["host"], record["port"]), timeout=5)
    except OSError as exc:
        write({**target, "connect": f"refused: {type(exc).__name__} {exc}",
               "elapsed": round(time.monotonic() - started, 2)})
        return
    if "--connect-only" in sys.argv:
        write({**target, "connect": "connected", "elapsed": round(time.monotonic() - started, 2)})
        connection.close()
        return
    connection.sendall((payload + "\n").encode())
    write({**target, "sent": payload})
    reader = connection.makefile("r", encoding="utf-8")
    for number in range(1, reads + 1):
        try:
            line = reader.readline()
        except OSError as exc:
            line = f"<read error {type(exc).__name__}: {exc}>"
        write({"read": number, "line": line, "elapsed": round(time.monotonic() - started, 2)})
    connection.close()


if __name__ == "__main__":
    main()
