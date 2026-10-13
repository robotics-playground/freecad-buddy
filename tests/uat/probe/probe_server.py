"""Test-only UAT probe: a read-only JSON view of FreeCAD state on localhost.

FreeCAD loads it only through ``freecad -M tests/uat/probe`` (see README.md). The HTTP thread
never touches FreeCAD: it queues each read and waits, and a Qt timer runs the read on the main
thread. Imports stdlib, FreeCAD, FreeCADGui and PySide only, never ``freecad_buddy``.
"""

import contextlib
import hmac
import json
import os
import queue
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import FreeCAD
import FreeCADGui
import snapshot
from PySide import QtCore

MAIN_THREAD_TIMEOUT_S = 10.0
POLL_INTERVAL_MS = 50
TOKEN_HEADER = "X-Probe-Token"

_jobs = queue.Queue()
# The server and the poll timer must outlive start(); Qt drops a timer with no Python reference.
_running = {}


class MainThreadTimeout(Exception):
    pass


class _Job:
    def __init__(self, read):
        self.read = read
        self.done = threading.Event()
        self.abandoned = False
        self.result = None
        self.error = None


def _run_queued_jobs():
    while True:
        try:
            job = _jobs.get_nowait()
        except queue.Empty:
            return
        if job.abandoned:
            continue
        try:
            job.result = job.read()
        except Exception as exc:
            job.error = f"{type(exc).__name__}: {exc}"
        finally:
            job.done.set()


def run_on_main_thread(read):
    job = _Job(read)
    _jobs.put(job)
    if not job.done.wait(MAIN_THREAD_TIMEOUT_S):
        job.abandoned = True
        raise MainThreadTimeout()
    if job.error is not None:
        raise RuntimeError(job.error)
    return job.result


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        sent = self.headers.get(TOKEN_HEADER, "").encode("utf-8")
        if not hmac.compare_digest(sent, self.server.token.encode("utf-8")):
            self._reply(403, {"error": "bad token"})
        elif self.path == "/health":
            self._reply(200, {"status": "ok", "pid": os.getpid()})
        elif self.path == "/snapshot":
            self._reply_snapshot()
        else:
            self._reply(404, {"error": f"unknown path {self.path}"})

    def _reply_snapshot(self):
        try:
            body = run_on_main_thread(lambda: snapshot.take_snapshot(FreeCAD, FreeCADGui))
        except MainThreadTimeout:
            self._reply(504, {"error": "main thread did not answer"})
        except RuntimeError as exc:
            self._reply(500, {"error": str(exc)})
        else:
            self._reply(200, body)

    def _reply(self, status, body):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass


def discovery_path(pid):
    return os.path.join(FreeCAD.getUserAppDataDir(), "fcb-uat-probe", f"probe-{pid}.json")


def _write_discovery(path, record):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    partial = path + ".tmp"
    with open(partial, "w", encoding="utf-8") as handle:
        json.dump(record, handle)
    os.replace(partial, path)


def _stop():
    _running["timer"].stop()
    _running["server"].shutdown()
    _running["server"].server_close()
    with contextlib.suppress(FileNotFoundError):
        os.remove(_running["discovery"])


def start():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    server.token = secrets.token_hex(16)
    timer = QtCore.QTimer()
    timer.timeout.connect(_run_queued_jobs)
    timer.start(POLL_INTERVAL_MS)
    threading.Thread(target=server.serve_forever, name="fcb-uat-probe", daemon=True).start()

    pid = os.getpid()
    port = server.server_address[1]
    path = discovery_path(pid)
    _write_discovery(path, {"pid": pid, "port": port, "token": server.token})
    _running.update(server=server, timer=timer, discovery=path)
    QtCore.QCoreApplication.instance().aboutToQuit.connect(_stop)
    FreeCAD.Console.PrintMessage(f"fcb-uat-probe listening on 127.0.0.1:{port}, {path}\n")
